"""清洗管道的行为契约：缺测绝不填 0、越界夹取到边界、量纲启发式识别、重复行去除，全程留痕。

本文件的前十条测试来自实施计划 Task 5 Step 1，另加两条钉住计划没定义的东西：
``CleanResult.dropped`` / ``corrected`` 的确切口径，以及 ``load_ranges`` 对 ranges 文件里
字段名写错/漏写的响亮失败。中间四条对应 Ruling 47/48/49/50：空学号整条剔除、体成分去重、
身高舍入到 0.1 cm、``WHOLE_RECORD`` 常量。末尾三条对应 Ruling 51 与第 2 轮评审的 M1/M3：
``zero_allowed`` 与 ``min > 0`` 的致命组合、``unit_normalized`` 条目的学号回填、
``_parse_range`` 的全部五道守卫。

**两处与 Step 1 原文的偏差**（第 2 轮评审要求，均为「加断言」而非「削断言」）：
``test_outlier_corrected_and_logged`` 补上「整条记录不被丢弃、其余七列与身份列原样」（M2）；
``test_dropped_and_corrected_counters_exclude_duplicate_removed`` 的被丢弃行由干净改为弄脏，
好让「去重先于清洗」这个顺序真的能被钉住（M4）。
"""
import pathlib
from dataclasses import replace

import pytest
import yaml

from app.adapters.base import RawFitnessRecord, RawBodyCompRecord
from app.domain.indicators import CLEANING_FIELDS
from app.pipeline.clean import (
    BODY_COMP_MEASURE_FIELDS,
    FITNESS_MEASURE_FIELDS,
    WHOLE_RECORD,
    clean_body_comp,
    clean_fitness,
    load_ranges,
    normalize_height,
)

RANGES_PATH = pathlib.Path(__file__).parents[2] / "data" / "indicator_ranges.yaml"
RANGES = load_ranges(RANGES_PATH)


def rec(**kw):
    # 字段序与 Ruling 33 后的 RawFitnessRecord 一致：tested_on 是必填的第 3 个位置参数，
    # batch_key 必须是 "<academic_year>|<timepoint>" 格式（parse_batch_key 独占解析）
    base = dict(student_no="S1", batch_key="2025-2026|week1", tested_on="2025-09-04",
        height_cm=175.0, weight_kg=65.0,
        vital_capacity_ml=4200.0, sprint_50m_s=7.2, sit_and_reach_cm=12.0,
        standing_jump_cm=230.0, strength_count=10.0, distance_run_s=240.0)
    return RawFitnessRecord(**{**base, **kw})


def test_unit_error_height_in_meters_normalized():
    # Review Focus #3
    v, entry = normalize_height(1.75)
    assert v == 175.0
    assert entry.kind == "unit_normalized"


def test_outlier_corrected_and_logged():
    r = clean_fitness([rec(sprint_50m_s=3.2)], RANGES)
    assert r.corrected == 1
    assert r.entries[0].kind == "outlier_corrected"
    assert r.entries[0].field == "sprint_50m_s"
    # M2：越界只改这一列，**整条记录必须留在结果里**。丢整行会让队列静默缩水，而缩掉哪些
    # 学生不会是随机的——越界集中在特定项目与特定录入源上，等于按数据质量筛选研究对象。
    assert len(r.fitness) == 1
    survivor = r.fitness[0]
    assert survivor.sprint_50m_s == 5.0 == RANGES["sprint_50m_s"].min   # 夹到最近的边界
    # 其余七列 + 三个身份列一字未动：整条记录 == 原记录只把越界那一列换成下界
    assert survivor == replace(rec(), sprint_50m_s=5.0)
    assert r.dropped == 0                                              # 没丢任何值
    assert [(e.field, e.original_value, e.processed_value) for e in r.entries] == [
        ("sprint_50m_s", 3.2, 5.0)
    ]


def test_body_fat_out_of_range_logged():
    r = clean_body_comp([RawBodyCompRecord("S1", "2025-09-01", 55.0, 62.0, 8.0)], RANGES)
    assert any(e.field == "body_fat_pct" and e.kind == "outlier_corrected" for e in r.entries)


def test_duplicate_record_removed_keeping_newer():
    r = clean_fitness([rec(), rec()], RANGES)
    assert len(r.fitness) == 1
    assert any(e.kind == "duplicate_removed" for e in r.entries)


def test_missing_field_produces_missing_dropped_entry_not_zero():
    # Review Focus #2：缺失字段绝不可被填 0
    r = clean_fitness([rec(vital_capacity_ml=None)], RANGES)
    assert r.fitness[0].vital_capacity_ml is None
    assert any(e.kind == "missing_dropped" and e.field == "vital_capacity_ml" for e in r.entries)


def test_zero_filled_time_field_becomes_missing_not_outlier_corrected():
    # Ruling 21：0 是最常见的缺测占位。若按「修正为区间下界」处理，
    # sprint_50m_s=0.0 会变成 5.0 秒，再经 score_item 低侧夹取得到 100 分——
    # 一个缺测项反而给体能最差的学生送上 20% 权重的满分。必须转 None。
    r = clean_fitness([rec(sprint_50m_s=0.0, distance_run_s=0.0)], RANGES)
    assert r.fitness[0].sprint_50m_s is None
    assert r.fitness[0].distance_run_s is None
    assert all(e.kind == "missing_dropped" for e in r.entries
               if e.field in ("sprint_50m_s", "distance_run_s"))


def test_zero_strength_count_is_a_real_value_not_missing():
    # 引体向上做不起一个 = 0 次，合法真实值，绝不可当缺测
    r = clean_fitness([rec(strength_count=0.0)], RANGES)
    assert r.fitness[0].strength_count == 0.0
    assert not any(e.field == "strength_count" for e in r.entries)


def test_negative_strength_count_is_missing():
    r = clean_fitness([rec(strength_count=-1.0)], RANGES)
    assert r.fitness[0].strength_count is None


def test_negative_sit_and_reach_is_a_real_value():
    # 国标坐位体前屈本就有 −1.3 等负值档
    r = clean_fitness([rec(sit_and_reach_cm=-1.3)], RANGES)
    assert r.fitness[0].sit_and_reach_cm == -1.3
    assert r.entries == []


def test_clean_record_passes_through_untouched():
    r = clean_fitness([rec()], RANGES)
    assert r.entries == [] and r.dropped == 0 and r.corrected == 0


# ---------------------------------------------------------------------------
# 以下两条不在 Step 1 的十条之内：计划声明了 CleanResult.dropped / corrected 却没给
# 定义，也没要求 ranges 文件写错时响亮失败——两者都由控制方在本任务的补充要求中裁定。
# ---------------------------------------------------------------------------


def test_dropped_and_corrected_counters_exclude_duplicate_removed():
    # 钉住三条口径：dropped 只数 missing_dropped；corrected 数 outlier_corrected 与
    # unit_normalized 之和；duplicate_removed 两个计数都不进——被去掉的是重复行，
    # 活下来的那一行本身完好无损，既没丢值也没改值。Task 10 要把这两个数写进
    # daily_sync_run.dropped_count / corrected_count，口径含糊就等于报表口径含糊。
    #
    # M4：**被丢弃那一行故意弄脏**（sprint_50m_s=0.0）。原来这里用的是干净的 rec()，
    # 于是「先去重再清洗」与「先清洗再去重」两种顺序产出的条目数与计数完全相同，把顺序
    # 反过来本测试照样全绿——钉不住任何东西。弄脏之后：正确顺序下这行的 0.0 根本不会进
    # 清洗，条目里没有它的痕迹；错误顺序下它会多产出一条 missing_dropped，
    # kinds 列表与 dropped 同时变红。审计描述一条从未进入结果的记录，比没有审计更糟。
    r = clean_fitness(
        [rec(sprint_50m_s=0.0), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)],
        RANGES,
    )
    assert len(r.fitness) == 1
    assert sorted(e.kind for e in r.entries) == [
        "duplicate_removed", "missing_dropped", "outlier_corrected", "unit_normalized"
    ]
    assert r.dropped == 1
    assert r.corrected == 2
    # 被丢弃那行的脏值（0.0）不得出现在任何条目里：它从未被清洗过
    assert all(e.original_value != 0.0 for e in r.entries)
    # 存活行的 sprint_50m_s 是夹取后的 5.0，不是被丢弃那行转出来的 None
    assert r.fitness[0].sprint_50m_s == 5.0


def test_load_ranges_rejects_unknown_or_omitted_field(tmp_path):
    # ranges 文件是专家手工维护的知识资产：字段名拼错（vital_capacty_ml）或漏写一个
    # 字段，会让那个字段的保护静默失效——正是本任务要防的失效模式，故必须早炸。
    unknown = tmp_path / "unknown_field.yaml"
    unknown.write_text(
        "height_cm: {min: 140, max: 220, non_positive_is_missing: true, zero_allowed: false}\n"
        "vital_capacty_ml: {min: 800, max: 9000, non_positive_is_missing: true, zero_allowed: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="vital_capacty_ml"):
        load_ranges(unknown)

    omitted = tmp_path / "omitted_field.yaml"
    omitted.write_text(
        "height_cm: {min: 140, max: 220, non_positive_is_missing: true, zero_allowed: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sprint_50m_s"):
        load_ranges(omitted)


# ---------------------------------------------------------------------------
# 以下四条对应 Ruling 47/48/49/50（计划 Task 5 Step 4）。
# ---------------------------------------------------------------------------


def brec(**kw):
    base = dict(student_no="S1", measured_on="2025-09-01",
                muscle_mass_kg=45.0, body_fat_pct=22.0, smi=7.0)
    return RawBodyCompRecord(**{**base, **kw})


def test_blank_student_no_drops_the_whole_record_with_an_attributable_reason():
    # Ruling 47：学号为空或全空白的记录无法归属到任何人，既不能入库也不能参与任何计算，
    # 故整条剔除。kind 仍是 missing_dropped——不新增第五个 kind（那会牵动 Task 3 已建的
    # CHECK 约束 ck_cleaning_log_kind），由 field="student_no" 指明缺的是哪一项。
    # original_value 存原始字符串，让 "" 与 "   " 在审计里可区分。
    for blank in ("", "   "):
        r = clean_fitness([rec(student_no=blank), rec(student_no="S2")], RANGES)
        assert [x.student_no for x in r.fitness] == ["S2"]
        hits = [e for e in r.entries
                if e.kind == "missing_dropped" and e.field == "student_no"]
        assert len(hits) == 1
        assert hits[0].original_value == blank
        assert hits[0].processed_value is None
        # reason 必须让读 cleaning_log 的人分清「这项测量缺席」与「整条记录被丢弃」
        assert "整条记录" in hits[0].reason
        assert "无法归属" in hits[0].reason
        assert r.dropped == 1

        b = clean_body_comp([brec(student_no=blank), brec(student_no="S2")], RANGES)
        assert [x.student_no for x in b.body_comp] == ["S2"]
        bhits = [e for e in b.entries
                 if e.kind == "missing_dropped" and e.field == "student_no"]
        assert len(bhits) == 1
        assert bhits[0].original_value == blank
        assert bhits[0].processed_value is None
        assert "整条记录" in bhits[0].reason


def test_body_comp_deduplicates_keeping_later_row_and_never_the_average():
    # Ruling 48：body_composition 上有 UniqueConstraint("student_id", "measured_on")
    # （Ruling 24），不去重会让 Task 10 的 upsert 静默覆盖先前那行且不留痕。
    # 去重键 (student_no, measured_on)、保留靠后的一行——绝不取均值：两条测量的平均
    # 是一个从未被测量过的数，属于 Ruling 21/34 禁止的凭空捏造。
    earlier = brec(muscle_mass_kg=45.0, body_fat_pct=22.0, smi=7.0)
    later = brec(muscle_mass_kg=47.0, body_fat_pct=26.0, smi=7.6)
    r = clean_body_comp([earlier, later], RANGES)
    assert len(r.body_comp) == 1
    survivor = r.body_comp[0]
    assert survivor.body_fat_pct == 26.0
    assert survivor.body_fat_pct != (22.0 + 26.0) / 2   # 不是均值 24.0
    assert survivor.muscle_mass_kg == 47.0 and survivor.smi == 7.6
    dups = [e for e in r.entries if e.kind == "duplicate_removed"]
    assert len(dups) == 1
    assert dups[0].field == WHOLE_RECORD
    assert dups[0].original_value == earlier.measured_on
    assert dups[0].processed_value == later.measured_on
    # 活下来的那行完好无损：既没丢值也没改值，两个计数都不进
    assert r.dropped == 0 and r.corrected == 0


def test_normalize_height_rounds_to_a_tenth_of_a_cm():
    # Ruling 49：身高实测精度即 0.1 cm，×100 会留下浮点残渣。身高经 BMI 参与国标计分，
    # Ruling 18 的就低取档在档位边界上理论上可能被 1e-14 级误差翻档，舍入把这一类风险整体消掉。
    # 注：裁定举例的 1.68 在 CPython 下 *100 恰好等于 168.0（本身无残渣）；真正带残渣的是
    # 2.01 / 1.417 这类值。两组都断言——前者钉住裁定点名的返回值，后者证明 round 确实在做事
    # （去掉 round，后一组立刻变红，前一组不会）。
    assert 2.01 * 100 != 201.0 and 1.417 * 100 != 141.7   # 残渣确实存在
    v, entry = normalize_height(1.68)
    assert v == 168.0
    assert v == round(v, 1)
    assert entry.processed_value == 168.0
    for meters, expected in ((2.01, 201.0), (1.417, 141.7)):
        got, got_entry = normalize_height(meters)
        assert got == expected
        assert got == round(got, 1)
        assert got_entry.processed_value == expected


def test_whole_record_constant_is_exported_and_pins_record_level_entries():
    # Ruling 50：记录级条目没有对应的单个字段名，统一用导出的模块常量占位，
    # 不在多处硬编码字面量；duplicate_removed 的两个值列放被丢弃行与保留行的日期，
    # 便于追溯是哪两条撞了。
    assert WHOLE_RECORD == "*"
    first = rec(tested_on="2025-09-04")
    second = rec(tested_on="2025-09-06")
    r = clean_fitness([first, second], RANGES)
    dups = [e for e in r.entries if e.kind == "duplicate_removed"]
    assert len(dups) == 1
    assert dups[0].field == WHOLE_RECORD
    assert (dups[0].original_value, dups[0].processed_value) == ("2025-09-04", "2025-09-06")


# ---------------------------------------------------------------------------
# 以下三条对应 Ruling 51 与第 2 轮评审的 M1 / M3。
# ---------------------------------------------------------------------------


def _mutated_ranges(tmp_path, field, override):
    """把真实 ranges 文件里 ``field`` 那一段按 ``override`` 改掉、其余原样，写进 ``tmp_path``。

    走 :func:`load_ranges` 的全路径而不是直接调私有的 ``_parse_range``：键集合校验、类型
    校验与自相矛盾校验都在同一条加载链上，测试应当钉住调用方真正会走的那条路。
    """
    raw = yaml.safe_load(RANGES_PATH.read_text(encoding="utf-8"))
    raw[field] = {**raw[field], **override}
    path = tmp_path / "indicator_ranges.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def test_load_ranges_rejects_zero_allowed_true_with_positive_min(tmp_path):
    # Ruling 51（Important）：zero_allowed 声明「0 是合法真实值」，min > 0 却让 0 落在区间
    # 外。后果是连锁的且全程不报错——_placeholder_reason 相信这个声明把 0 放行，越界夹取
    # 接着把 0 夹到 min 并记 outlier_corrected，score_item 对「越小越好」的项再做低侧夹取
    # 就是 100 分。实测过：去掉这道守卫、把 sprint_50m_s 配成
    # {min: 5.0, non_positive_is_missing: false, zero_allowed: true} 之后，
    # clean_fitness(sprint_50m_s=0.0) 返回 5.0，score_item(SPRINT_50M, 5.0) 返回 100，
    # 而转 None 才是唯一安全的处置（score_item(None) 返回 None）。
    # ranges 文件是体育测量学专家手工维护的知识资产，load_ranges 是唯一能拦下坏改动的地方：
    # _clean_measure 拿到的已经是 FieldRange，无从判断它自身是否自洽。
    path = _mutated_ranges(
        tmp_path, "sprint_50m_s",
        {"min": 5.0, "non_positive_is_missing": False, "zero_allowed": True},
    )
    with pytest.raises(ValueError) as excinfo:
        load_ranges(path)
    message = str(excinfo.value)
    assert "sprint_50m_s" in message                      # 指名是哪个字段
    assert "zero_allowed 为 true 时 min 必须 <= 0" in message
    assert "5.0" in message and "满分" in message          # 并说明后果，不只说「配置错了」
    # 对照：仓库自带的 11 个字段全部满足这条约束（zero_allowed 为真的只有下界 −15 的
    # 坐位体前屈与下界 0 的引体向上次数），故这份守卫不改变现有配置的加载结果
    assert len(RANGES) == 11
    assert [name for name, fr in RANGES.items() if fr.zero_allowed and fr.min > 0] == []


def test_unit_normalized_entry_gets_the_records_student_no_backfilled():
    # M1：normalize_height 按 Ruling 45 是单参数的，拿不到记录身份，它构造的条目
    # student_no 是空串；clean_fitness 收条目时用 replace(...) 回填成记录的学号。
    # 回填一旦回归，一条**本可归属**的审计记录就变成无主的（Task 10 里 student_id 解析成
    # NULL），而「只断言 unit_normalized 这个 kind 存在」的测试完全察觉不到。
    _, bare = normalize_height(1.75)
    assert bare.student_no == ""                          # 单参数函数确实拿不到学号
    r = clean_fitness([rec(student_no="S7", height_cm=1.75, vital_capacity_ml=None)], RANGES)
    unit = [e for e in r.entries if e.kind == "unit_normalized"]
    assert len(unit) == 1
    assert unit[0].student_no == "S7"                     # 回填生效
    assert unit[0].field == "height_cm"
    assert (unit[0].original_value, unit[0].processed_value) == (1.75, 175.0)
    # 同一条记录产出的所有条目都带上同一个学号，不得出现「一条有名、一条无主」
    assert {e.student_no for e in r.entries} == {"S7"}


@pytest.mark.parametrize(
    ("field", "override", "expected"),
    [
        # 上下界颠倒
        ("height_cm", {"min": 250}, "区间上下界颠倒"),
        # 布尔类型守卫（两个布尔键各测一次）
        ("height_cm", {"non_positive_is_missing": 1}, "应为布尔值"),
        ("height_cm", {"zero_allowed": "false"}, "应为布尔值"),
        # 数值类型守卫，含 bool 排除：min: true 不得被当成 1 静默通过
        ("height_cm", {"min": True}, "应为数值"),
        ("weight_kg", {"max": "150"}, "应为数值"),
        # non_positive_is_missing 与 zero_allowed 同时为真
        ("sprint_50m_s", {"non_positive_is_missing": True, "zero_allowed": True},
         "non_positive_is_missing 为 true"),
        # zero_allowed 为真而 min > 0（Ruling 51，专项测试见上一条）
        ("sprint_50m_s", {"min": 5.0, "non_positive_is_missing": False, "zero_allowed": True},
         "zero_allowed 为 true 时 min 必须 <= 0"),
    ],
)
def test_load_ranges_rejects_malformed_field_configuration(tmp_path, field, override, expected):
    # M3：_parse_range 的每一道守卫都要有测试——「未测的守卫等于没有守卫」。其中 min: true
    # 这一条正是整套类型守卫存在的理由：bool 是 int 的子类，不排除布尔就会把 true 当成 1
    # 静默通过，区间下界于是变成 1，而任何地方都不会报错。
    path = _mutated_ranges(tmp_path, field, override)
    with pytest.raises(ValueError) as excinfo:
        load_ranges(path)
    message = str(excinfo.value)
    assert expected in message
    assert field in message           # 报错必须指名是哪个字段
    assert str(path) in message       # 以及是哪个文件


# ---------------------------------------------------------------------------
# Plan 02 Task 1：``cleaning_log.field`` 的取值域唯一所有者（Plan01 Ruling 156）
# ---------------------------------------------------------------------------


def test_cleaning_fields_cover_every_produced_field():
    """``app.domain.indicators.CLEANING_FIELDS`` == 清洗层**实际会写进 ``field`` 的**全部值。

    **两侧不同源**（硬规矩 #35）：

    * 左侧是 domain 里那份**字面写死**的 ``frozenset``（13 个字符串，另有一条
      ``tests/domain/test_indicators.py::test_cleaning_fields_is_the_vocabulary_of_cleaning_log_field``
      逐字钉住它）；
    * 右侧是从 ``RawFitnessRecord`` / ``RawBodyCompRecord`` 的**字段声明序**推导出来的
      （``dataclasses.fields()``，与 ``load_ranges`` 的键集合校验同一手法），加上两个
      **记录级**取值 ``student_no``（学号无法归属时整条剔除）与 ``WHOLE_RECORD``
      （整条重复被去除）。

    所以「往记录数据类里加一个测量列而忘了更新 ``CLEANING_FIELDS``」会让本测试当场红——
    而那正是列宽守卫会漏掉新字段名的唯一途径。

    **为什么这一条重要**：``cleaning_log.field`` 是 ``String(32)`` 且**没有 CHECK 约束**，
    故此前没有任何东西保证 32 装得下最长的字段名。SQLite 不强制 ``VARCHAR`` 长度，换
    MySQL / PostgreSQL 会静默截断——与 Plan01 Ruling 144 的
    ``derived_metrics.trend String(16)`` 是同一个缺陷形态（那一列漏了 7 个任务，
    500 人首批实测 209 行 = 41.8% 写的是 17 字符的 ``"insufficient_data"``）。
    列宽那一侧的核对在 ``tests/db/test_models.py`` 的列宽遍历测试里做。
    """
    assert len(FITNESS_MEASURE_FIELDS) == 8, FITNESS_MEASURE_FIELDS
    assert len(BODY_COMP_MEASURE_FIELDS) == 3, BODY_COMP_MEASURE_FIELDS

    produced = (
        set(FITNESS_MEASURE_FIELDS)
        | set(BODY_COMP_MEASURE_FIELDS)
        | {"student_no", WHOLE_RECORD}
    )
    assert CLEANING_FIELDS == produced, (
        f"缺 {sorted(produced - CLEANING_FIELDS)}，"
        f"多 {sorted(CLEANING_FIELDS - produced)}"
    )
    assert len(CLEANING_FIELDS) == 13

    # 两个记录级取值在生产路径上**确实会被写出来**（不是纸面推导）：
    # ① 学号全空白 → 整条剔除，field = "student_no"（Ruling 47）
    blank = clean_fitness([rec(student_no="   ")], RANGES)
    assert {e.field for e in blank.entries} == {"student_no"}
    assert blank.fitness == [] and blank.dropped == 1
    # ② 同学号同批次两行 → 去重，field = WHOLE_RECORD（Ruling 48/50）
    dup = clean_fitness([rec(tested_on="2025-09-04"), rec(tested_on="2025-09-06")], RANGES)
    assert {e.field for e in dup.entries if e.kind == "duplicate_removed"} == {WHOLE_RECORD}
    # ③ 逐字段处置走的是测量列名本身
    missing = clean_fitness([rec(vital_capacity_ml=None)], RANGES)
    assert "vital_capacity_ml" in {e.field for e in missing.entries}
    # ④ 量纲归一是 height_cm 专属的 unit_normalized 写入点
    _, unit_entry = normalize_height(1.75)
    assert unit_entry.field == "height_cm" and unit_entry.kind == "unit_normalized"
