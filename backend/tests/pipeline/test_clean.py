"""清洗管道的行为契约：缺测绝不填 0、越界夹取到边界、量纲启发式、重复行去除，全程留痕。

本文件的十条测试逐字来自实施计划 Task 5 Step 1，另加两条钉住计划没定义的东西：
``CleanResult.dropped`` / ``corrected`` 的确切口径，以及 ``load_ranges`` 对 ranges 文件
里字段名写错/漏写的响亮失败。末尾四条对应 Ruling 47/48/49/50：空学号整条剔除、
体成分去重、身高舍入到 0.1 cm、``WHOLE_RECORD`` 常量。
"""
import pathlib

import pytest

from app.adapters.base import RawFitnessRecord, RawBodyCompRecord
from app.pipeline.clean import (
    WHOLE_RECORD,
    clean_body_comp,
    clean_fitness,
    load_ranges,
    normalize_height,
)

RANGES = load_ranges(pathlib.Path(__file__).parents[2] / "data" / "indicator_ranges.yaml")


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
    r = clean_fitness(
        [rec(), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)], RANGES
    )
    assert len(r.fitness) == 1
    assert sorted(e.kind for e in r.entries) == [
        "duplicate_removed", "missing_dropped", "outlier_corrected", "unit_normalized"
    ]
    assert r.dropped == 1
    assert r.corrected == 2


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
