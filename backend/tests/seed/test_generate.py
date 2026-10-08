"""Task 6 仿真数据生成器的测试：24 条 = 简报的 13 条 + 把裁定钉住的 11 条。

简报的 13 条逐字保留，只有两处按裁定/事实更正，且都不是放宽：

* ``test_two_grouping_modes_coexist`` 的「12 个行政班」改成 14——简报正文那三个数互斥
  （12 × 38 = 456 < 500），班数改由 ``students`` 与 ``section_size`` 反推，见该条注释；
* ``test_body_fat_abnormal_rate_in_expected_band`` 跳过被缺测注入置空的单元格，并**新增**
  一条分母守卫（存活单元格必须 > 90%），断言区间 0.20–0.50 一字未改。

新增的 11 条各自对应简报正文或裁定里明确要求钉住的性质：注入列白名单（Ruling 44）、
逐字复制（Ruling 52）、问卷只接受 duplicate（Ruling 34）、四类趋势比例（Step 4）、
正反查往返（Ruling 18/22）、CSV 契约与 students.csv 的有意缺席（Ruling 36/37/38）、
问卷弱相关（Step 6）、注入与清洗的一一对应（Step 6「供 Task 5 交叉验证」）、
入库边界与幂等、隐藏随机源/时钟的源码级守卫、以及「注入比例为 0 时一行不改」。

**规模相关的断言才用 500 人**（``CFG``）：性别比、行政班规模、全员编班、体成分异常率、
得分相关性、注入与清洗的对账都随样本量变化，必须按简报的 500 人跑。与规模无关的断言
（异种子相异、写盘往返、入库边界、正反查往返）用 ``SMALL``（120 人）——120 是能同时
满足「每班 30–38 人」的最小可编班规模，够小以致整套测试仍在秒级完成。
"""
import ast
import csv
import datetime as dt
import json
import pathlib
from collections import Counter

import numpy as np
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters import base
from app.adapters.mock_lepao import MockLePaoAdapter
from app.db import models
from app.db.session import init_db
from app.domain.indicators import (
    WEAKNESS_ITEMS,
    Sex,
    age_group_of,
    score_item,
)
from app.pipeline.clean import (
    BODY_COMP_MEASURE_FIELDS,
    FITNESS_MEASURE_FIELDS,
    WHOLE_RECORD,
    clean_body_comp,
    clean_fitness,
    load_ranges,
)
from app.refdata import DATA_DIR, standard
from app.seed.body_comp import make_body_comp
from app.seed.config import (
    SEMESTERS,
    TIMEPOINT_SEQUENCE,
    SeedConfig,
    current_semester,
)
from app.seed.fitness import latent_profiles, make_fitness_tests
from app.seed.generate import (
    _cell,
    build_dataset,
    inject_dirty,
    seed_database,
    write_csv,
)
from app.seed.population import make_population
from app.seed.sections import make_sections
from app.seed.survey import make_survey

CFG = SeedConfig(students=500, weeks=16, seed=20250828)
# 与规模无关的断言用的小配置；除 students 外与 CFG 完全一致
SMALL = SeedConfig(students=120, weeks=16, seed=20250828)

# 注入只允许作用于测量列（Ruling 44）：白名单从清洗层推导，不在此手抄第二份
MEASURE_COLUMNS = frozenset(FITNESS_MEASURE_FIELDS) | frozenset(BODY_COMP_MEASURE_FIELDS)
DATE_COLUMNS = frozenset({"tested_on", "measured_on", "filled_on"})
IDENTITY_COLUMNS = frozenset({"student_no", "batch_key"})

# 源码级守卫扫描的目录（可复现性：全项目只允许一个带种子的随机数入口、零处时钟调用）
SEED_DIR = pathlib.Path(__file__).parents[2] / "app" / "seed"


def test_population_size_and_sex_ratio():
    pop = make_population(CFG, np.random.default_rng(CFG.seed))
    assert len(pop) == 500
    males = sum(1 for p in pop if p["sex"] == "male")
    assert abs(males / 500 - 0.55) < 0.05
    assert all(18 <= p["age"] <= 22 for p in pop)


def test_same_seed_produces_identical_dataset():
    a = build_dataset(CFG)
    b = build_dataset(CFG)
    assert a == b          # 字节级一致：可复现是研究项目硬要求


def test_different_seed_produces_different_dataset():
    assert build_dataset(SMALL) != build_dataset(
        SeedConfig(**{**SMALL.__dict__, "seed": 1})
    )


def test_two_academic_years_present():
    ds = build_dataset(CFG)
    years = {r["academic_year"] for r in ds["fitness"]}
    assert len(years) >= 2      # 趋势判定需要连续两次体测


def test_three_timepoints_present():
    ds = build_dataset(CFG)
    cur = max(r["academic_year"] for r in ds["fitness"])
    tps = {r["timepoint"] for r in ds["fitness"] if r["academic_year"] == cur}
    assert tps == {"week1", "week8", "week16"}


def test_body_fat_abnormal_rate_in_expected_band():
    ds = build_dataset(CFG)
    pop = {p["student_id"]: p for p in ds["population"]}
    # 缺测注入（Ruling 34 要求 body_comp 也接受 missing，Ruling 44 的白名单里就有
    # body_fat_pct）会把约 4% 的单元格置成 None。本条断言量的是**生成器的分布**，
    # 不是脏数据的分布，故跳过被置空的单元格。断言强度未减：区间仍是 0.20–0.50，
    # 而下面那条分母守卫堵住了「把大多数记录都过滤掉从而让区间失去意义」这条退路。
    measured = [r for r in ds["body_comp"] if r["body_fat_pct"] is not None]
    abnormal = sum(1 for r in measured
        if r["body_fat_pct"] > (20 if pop[r["student_id"]]["sex"] == "male" else 28))
    rate = abnormal / len(measured)
    assert 0.20 <= rate <= 0.50
    assert len(measured) > 0.9 * len(ds["body_comp"])


def test_dirty_data_injected():
    ds = build_dataset(CFG)
    kinds = {e["kind"] for e in ds["dirty_marks"]}
    assert {"missing", "outlier", "unit_error", "duplicate"} <= kinds


def test_two_grouping_modes_coexist():
    # spec §10.3：阶段一行政班 + 阶段二分层班，同一批学生两套编班
    ds = build_dataset(CFG)
    modes = {s["grouping_mode"] for s in ds["course_sections"]}
    assert modes == {"administrative", "stratified"}
    admin = [s for s in ds["course_sections"] if s["grouping_mode"] == "administrative"]
    strat = [s for s in ds["course_sections"] if s["grouping_mode"] == "stratified"]
    # 简报写的「12 个行政班」与它自己的另两条断言互斥：每班上限 38 人时
    # 12 × 38 = 456 < 500，装不下全员（test_every_student_enrolled_in_both_grouping_modes），
    # 也压不进 30–38 的区间（test_administrative_section_size_within_bounds）。
    # 行政班数因此由 students 与 section_size 反推：ceil(500 / 38) = 14。
    assert len(admin) == 14 and len(strat) == 3
    assert {s["name"] for s in strat} == {"提升班", "强化班", "拓展班"}


def test_administrative_section_size_within_bounds():
    ds = build_dataset(CFG)
    admin_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "administrative"}
    sizes = Counter(e["section_id"] for e in ds["enrollments"]
                    if e["section_id"] in admin_ids)
    assert sizes and all(30 <= n <= 38 for n in sizes.values())


def test_every_student_enrolled_in_both_grouping_modes():
    ds = build_dataset(CFG)
    ids = {p["student_id"] for p in ds["population"]}
    admin_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "administrative"}
    strat_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "stratified"}
    in_admin = {e["student_id"] for e in ds["enrollments"] if e["section_id"] in admin_ids}
    in_strat = {e["student_id"] for e in ds["enrollments"] if e["section_id"] in strat_ids}
    assert in_admin == ids and in_strat == ids


def test_survey_has_five_dimensions_on_five_point_scale():
    # spec §10.9 占位量表
    ds = build_dataset(CFG)
    assert ds["survey"]
    for r in ds["survey"]:
        assert len(r["dimensions"]) == 5
        assert all(1 <= v <= 5 for v in r["dimensions"].values())


def test_write_csv_roundtrips_through_adapter(tmp_path):
    ds = build_dataset(SeedConfig(students=40, weeks=16, seed=20250828))
    write_csv(ds, tmp_path)
    ad = MockLePaoAdapter(tmp_path)
    assert len(list(ad.fetch_fitness(None))) > 0
    assert len(list(ad.fetch_body_comp(None))) > 0
    assert len(list(ad.fetch_survey(None))) > 0


def test_indicator_correlation_is_realistic():
    # 潜变量驱动的核心断言：耐力与力量得分应正相关，而非独立随机
    ds = build_dataset(CFG)
    w1 = [r for r in ds["fitness"] if r["timepoint"] == "week1"
          and r["academic_year"] == max(x["academic_year"] for x in ds["fitness"])]
    end = np.array([r["score_endurance_mean"] for r in w1])
    str_ = np.array([r["score_strength_mean"] for r in w1])
    assert np.corrcoef(end, str_)[0, 1] > 0.4


def test_unclamped_body_comp_records_satisfy_the_muscle_mass_identity():
    """Ruling 222：``肌肉量 = SMI × 身高² × 1.5`` 在**未被下界夹取**的记录上恒成立。

    守的是两件事：

    1. **``MUSCLE_MASS_PER_SMI = 1.5`` 这个常量**——它此前在 ``tests/`` 里**零引用**
       （``git grep -n 'MUSCLE_MASS' -- backend/tests/`` 只命中 ``percentile.MUSCLE_MASS``，
       那是另一个常量）。改成 1.6 或 1.4，本条当场红：期望侧写的是**字面量 1.5**、
       不读被测模块的常量（硬规矩 #35：断言两侧不得同源）。
    2. **``body_comp.py`` 模块 docstring 那句「三个量因此内部自洽」的适用边界**——它有一个
       例外：被 ``MUSCLE_MASS_RANGE`` 下界夹住的记录。夹取只改 ``muscle_mass_kg``、
       不回算 ``smi``，故那批记录落盘后恒等式失效。本条把例外**精确地**框出来：
       违例者的 ``muscle_mass_kg`` 必须**恰好**等于下界字面量 ``22.0``，且条数必须是
       **138**（本轮亲跑：clean / 500 人 / ``seed=20250828``，138/3000 = 4.60%）。

    **容差必须是逐记录的舍入传播量，不能是一个固定小数**：落盘的 ``smi`` 只有 1 位小数，
    它的 ±0.05 经 ``× 身高² × 1.5`` 传播成 ±0.05×身高²×1.5 kg（身高 1.72 m 时 ≈ ±0.22 kg），
    ``muscle_mass_kg`` 自己又舍入 ±0.05。本轮实测：用固定容差 0.05 / 0.10 / 0.15 kg 会分别
    报出 **76.5% / 53.4% / 31.4%** 的「违例」，全是舍入噪声造成的假阳性——而用下面的
    逐记录容差，违例数正好等于夹取数（138/138）。**这就是硬规矩 #41 的形状**：
    口径取错会同时产生假阳性与假阴性。

    **零注入**是承重的：缺省注入下 ``inject_dirty`` 会把一部分 ``muscle_mass_kg`` 抬到
    yaml 上限的 1.5 倍（``outlier``）或置空（``missing``），实测违例涨到 161/2786 = 5.78%，
    其中只有 130 条落在下界、另 31 条是注入造成的——那时「违例 ⟺ 被夹」这个等价就不成立了。
    """
    clean_cfg = SeedConfig(
        students=500, weeks=16, seed=20250828,
        dirty={"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0},
    )
    ds = build_dataset(clean_cfg)
    height_of = {p["student_id"]: p["height_cm"] for p in ds["population"]}

    rows = [r for r in ds["body_comp"]
            if r["muscle_mass_kg"] is not None and r["smi"] is not None]
    assert len(rows) == 3000, len(rows)          # 2 学年 × 3 时点 × 500 人，零注入不置空

    clamped, offenders = 0, []
    for r in rows:
        h = height_of[r["student_id"]] / 100.0
        expected = r["smi"] * h * h * 1.5        # 字面量 1.5，不读 MUSCLE_MASS_PER_SMI
        tolerance = 0.05 * h * h * 1.5 + 0.05    # smi 舍入传播 + muscle 自身舍入
        if abs(expected - r["muscle_mass_kg"]) <= tolerance:
            continue
        if r["muscle_mass_kg"] == 22.0:          # 字面量 = MUSCLE_MASS_RANGE[0]
            clamped += 1
        else:
            offenders.append((r["student_no"], r["measured_on"], r["smi"],
                              r["muscle_mass_kg"], round(expected, 3)))
    # offender 一次性报全（Ruling 157：循环里逐条 assert 会在第一例就停、证据被截断）
    assert offenders == [], f"未被下界夹取却违反恒等式的记录: {offenders[:10]}"
    assert clamped == 138, clamped               # 违例**全部**由下界夹取造成，一条不多
    # 反空转：下界确实夹住了记录（否则「除夹取外恒成立」是句空话）
    assert clamped > 0


# ---------------------------------------------------------------------------
# 以下为把简报正文与裁定钉住的补充测试
# ---------------------------------------------------------------------------


def test_dirty_marks_never_touch_date_or_identity_columns():
    """Ruling 44 的承重约束：注入只落在测量列上。

    日期列被置空会让适配器在**抽取阶段**抛 ValueError（Ruling 41 的无条件校验），
    一次本该记进 cleaning_log 的「缺失」于是升级成整条日批处理中断；标识列被改动
    则会让记录归属到不存在的学生。两者都不是「数据质量问题」，而是结构性破坏。
    """
    ds = build_dataset(CFG)
    assert ds["dirty_marks"]
    touched = {m["field"] for m in ds["dirty_marks"]}
    assert touched & DATE_COLUMNS == set()
    assert touched & IDENTITY_COLUMNS == set()
    # duplicate 是记录级条目，field 取清洗层的通配常量而不是某一列名
    assert WHOLE_RECORD in touched
    assert touched - {WHOLE_RECORD} <= MEASURE_COLUMNS


def test_duplicate_injection_copies_the_whole_row_verbatim():
    """Ruling 52：重复行必须是**逐字复制**。

    体测去重键是 ``(student_no, batch_key)``，「保留后者」按输入顺序判定而不是按日期。
    若复制时改动了 ``tested_on``，胜出的可能是较早的那次测量，而 cleaning_log 的 reason
    只能如实印出两个日期、无法声称「取最新」——歧义因此必须在生产方就消灭掉。

    断言方式：把每行序列化成 JSON 后计数，**完全相同的多余行数**必须恰等于 duplicate
    注入条数。改动任何一个字段（包括日期）都会让多余的相同行数为 0 而注入条数 > 0。
    """
    cfg = SeedConfig(
        students=120, weeks=16, seed=7,
        dirty={"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.2},
    )
    ds = build_dataset(cfg)
    marks = [m for m in ds["dirty_marks"] if m["kind"] == "duplicate"]
    assert marks, "20% 的重复率在 120 人 × 7000 行上不可能一条都没注入"
    for source in ("fitness", "body_comp", "survey"):
        rows = ds[source]
        fingerprints = Counter(
            json.dumps(r, sort_keys=True, ensure_ascii=False, allow_nan=False) for r in rows
        )
        extra_identical_rows = sum(n - 1 for n in fingerprints.values() if n > 1)
        expected = sum(1 for m in marks if m["source"] == source)
        assert extra_identical_rows == expected


def test_survey_records_only_ever_receive_duplicate_injection():
    """Ruling 34：``survey`` 只允许 duplicate。

    适配器契约声明的是 ``total: float``、``dimensions: dict[str, float]``，没有 None 的
    位置；空白问卷单元格会让 MockLePaoAdapter 抛 ValueError 并在抽取阶段中断整条管道。
    """
    ds = build_dataset(CFG)
    survey_kinds = {m["kind"] for m in ds["dirty_marks"] if m["source"] == "survey"}
    assert survey_kinds <= {"duplicate"}
    # 三类测量注入必须真的落在 fitness 与 body_comp 上，否则上面那条断言是空转
    measure_kinds = {
        m["kind"] for m in ds["dirty_marks"] if m["source"] in ("fitness", "body_comp")
    }
    assert {"missing", "outlier", "unit_error"} <= measure_kinds


def test_trend_labels_are_injected_at_configured_ratios():
    """Step 4：四类趋势按配置比例注入，且一名学生只有一个标签。"""
    ds = build_dataset(CFG)
    per_student: dict[int, set[str]] = {}
    for r in ds["fitness"]:
        per_student.setdefault(r["student_id"], set()).add(r["trend_label"])
    assert len(per_student) == 500
    assert all(len(labels) == 1 for labels in per_student.values())
    counts = Counter(next(iter(labels)) for labels in per_student.values())
    assert set(counts) == set(CFG.trend_mix)
    # 配额用最大余额法精确分配，故此处是**等号**而不是容差
    for label, ratio in CFG.trend_mix.items():
        assert counts[label] == round(500 * ratio)


def test_generated_raw_values_roundtrip_through_the_official_table():
    """Ruling 18/22：生成器写出的原始值正查回去，必须等于它自己记下的得分。

    这条断言钉住的是「反查得到的原始值」与「记录里带的得分」两者同源同档：
    任何一处偷偷做了插值、舍入或换了方向，这里都会立刻炸开。

    **复核用的龄组按记录所属学年取（Ruling 56）**：``person["age"]`` 是以当前学期
    开学日为参考日的年龄，故上学年该生小一岁。用本学年的龄组去复核上学年的记录，
    对跨 19/20 线的学生会查另一张表——两边「都合法」，只是分数来自不同档位。
    """
    ds = build_dataset(SMALL)
    pop = {p["student_id"]: p for p in ds["population"]}
    table = standard()
    column_of = {
        "vital_capacity": "vital_capacity_ml",
        "sprint_50m": "sprint_50m_s",
        "sit_and_reach": "sit_and_reach_cm",
        "standing_jump": "standing_jump_cm",
        "pull_up_or_sit_up": "strength_count",
        "distance_run": "distance_run_s",
    }
    # 脏数据注入会改掉原始值，往返只对**未被注入**的单元格成立
    dirty = {
        (m["student_no"], m["field"])
        for m in ds["dirty_marks"]
        if m["source"] == "fitness"
    }
    checked = 0
    current_year = current_semester().academic_year
    for r in ds["fitness"]:
        person = pop[r["student_id"]]
        sex = Sex(person["sex"])
        age_group = age_group_of(
            person["age"] if r["academic_year"] == current_year else person["age"] - 1
        )
        for item in WEAKNESS_ITEMS:
            column = column_of[item.value]
            if (r["student_no"], column) in dirty:
                continue
            raw = r[column]
            assert score_item(table, item, raw, sex, age_group) == r[f"score_{item.value}"]
            checked += 1
    assert checked > 1000


def test_write_csv_emits_exactly_the_three_contract_files(tmp_path):
    """Ruling 36/37/38：只写三类 CSV，表头逐列等于契约常量，且缺 students.csv 是有意的。"""
    ds = build_dataset(SMALL)
    write_csv(ds, tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == {
        base.FITNESS_FILENAME, base.BODY_COMP_FILENAME, base.SURVEY_FILENAME
    }
    assert base.STUDENTS_FILENAME not in {p.name for p in tmp_path.iterdir()}
    for filename, columns in (
        (base.FITNESS_FILENAME, base.FITNESS_COLUMNS),
        (base.BODY_COMP_FILENAME, base.BODY_COMP_COLUMNS),
        (base.SURVEY_FILENAME, base.SURVEY_COLUMNS),
    ):
        with (tmp_path / filename).open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        assert tuple(header) == columns
    # Ruling 38：日期列一律零填充 YYYY-MM-DD 且不带时间部分
    with (tmp_path / base.FITNESS_FILENAME).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        assert dt.date.fromisoformat(row["tested_on"]).isoformat() == row["tested_on"]
        assert "T" not in row["tested_on"]
        assert row["batch_key"] == base.make_batch_key(
            *base.parse_batch_key(row["batch_key"])
        )


def test_survey_total_is_weakly_correlated_with_latent_fitness():
    """Step 6：问卷总分与 latent_fitness 弱正相关（约 0.3）。"""
    rng = np.random.default_rng(CFG.seed)
    population = make_population(CFG, rng)
    latents = latent_profiles(population, CFG, rng)
    survey = make_survey(population, latents, CFG, rng)
    latent_of = {p["student_id"]: latents[p["student_id"]]["fitness"] for p in population}
    totals = np.array([r["total"] for r in survey])
    fitness = np.array([latent_of[r["student_id"]] for r in survey])
    corr = float(np.corrcoef(totals, fitness)[0, 1])
    assert 0.15 <= corr <= 0.45


def test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises(tmp_path):
    """写盘 → 适配器读回 → 清洗，注入痕迹与 ``cleaning_log`` 条目**一一对应**。

    这条测试同时钉住两件事，缺任何一件整个演示数据都是自欺：

    1. **每一处注入都真的被清洗层认出来**，且认成期望的那一类
       （missing→missing_dropped、outlier→outlier_corrected、unit_error→unit_normalized、
       duplicate→duplicate_removed）。注入一个清洗层不认得的「脏值」是最坏的失效模式：
       ``dirty_marks`` 声称注入过了，管道却一声不响地放行，Task 5 的交叉验证永远对不上账。
       实测中最容易踩的是 outlier——往下压会落进 ``strength_count`` 的「负数只能来自未测
       哨兵」分支变成 missing_dropped，所以注入一律往上抬（见 inject_dirty 的注释）。
    2. **未被注入的干净数据一条清洗条目都不产生**。生成器若把某个字段的本底分布画到
       ``indicator_ranges.yaml`` 的区间之外，多出来的 ``outlier_corrected`` 会与注入的那批
       混在一起，谁也分不清哪条是谁造成的。

    ``survey`` 不参与比对：按 Ruling 34 第一批没有 ``clean_survey``，问卷的重复由
    ``uq_interest_survey_student_semester_filled_on`` + ``repo.upsert`` 兜住。
    """
    ds = build_dataset(CFG)
    write_csv(ds, tmp_path)
    ranges = load_ranges(DATA_DIR / "indicator_ranges.yaml")
    adapter = MockLePaoAdapter(tmp_path)
    fitness_result = clean_fitness(adapter.fetch_fitness(None), ranges)
    body_comp_result = clean_body_comp(adapter.fetch_body_comp(None), ranges)

    expected_kind = {
        "missing": "missing_dropped",
        "outlier": "outlier_corrected",
        "unit_error": "unit_normalized",
        "duplicate": "duplicate_removed",
    }
    injected = Counter(
        (m["source"], expected_kind[m["kind"]], m["field"])
        for m in ds["dirty_marks"]
        if m["source"] != "survey"
    )
    cleaned = Counter(
        ("fitness", e.kind, e.field) for e in fitness_result.entries
    ) + Counter(("body_comp", e.kind, e.field) for e in body_comp_result.entries)
    assert cleaned == injected
    # 四类注入在本次配置下都非空，否则上面那条等式会退化成「两边都是 0」的空转
    assert {kind for _, kind, _ in injected} == set(expected_kind.values())

    # 去重后剩下的行数 = 注入重复之前的行数（500 人 × 2 学年 × 3 时点）
    expected_rows = CFG.students * len(SEMESTERS) * len(TIMEPOINT_SEQUENCE)
    assert len(fitness_result.fitness) == expected_rows
    assert len(body_comp_result.body_comp) == expected_rows
    # dropped 只数 missing_dropped；corrected 数 outlier_corrected + unit_normalized；
    # duplicate_removed 两个计数都不进（口径见 app/pipeline/clean.py 的 _CORRECTED_KINDS）
    fitness_marks = [(kind, field, n) for (s, kind, field), n in injected.items() if s == "fitness"]
    assert fitness_result.dropped == sum(
        n for kind, _field, n in fitness_marks if kind == "missing_dropped"
    )
    assert fitness_result.corrected == sum(
        n for kind, _field, n in fitness_marks
        if kind in ("outlier_corrected", "unit_normalized")
    )


ORGANISATION_TABLES = ("semester", "teacher", "student", "course_section", "enrollment")
#: **业务数据表**：经适配器与管道流入的仿真数据（Plan 01 的 9 张）+ Plan 02 Task 6 的
#: ``prescription`` 与 ``weekly_adjustment``（**9 → 11**）。
#: ⚠️ 后两张归本分区而不是 :data:`REFERENCE_TABLES`，判据就是下面那段注释里写的
#: 「谁灌它」：它们由 ``app/pipeline/prescription_stage.py``（Task 7）按学生逐日写，
#: 是**管道产物**；``exercise`` / ``prescription_template`` 由 YAML 投影而来，是
#: **专家维护的知识资产在 DB 里的投影**。归错分区的后果是响亮的：
#: :func:`test_seed_database_writes_only_organisation_tables_and_is_idempotent` 对
#: ``DATA_TABLES + REFERENCE_TABLES`` 一律要求 seed 阶段 **0 行**，而处方天然不由
#: ``seed_database`` 写，故两个分区都相容——真正被这条归属钉住的是
#: :func:`test_table_partition_is_exhaustive` 的穷尽性（不归任何分区 → 那两条守卫都对它无感）。
DATA_TABLES = (
    "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
    "percentile_snapshot", "derived_metrics", "stratification_result",
    "daily_sync_run", "cleaning_log", "prescription", "weekly_adjustment",
)
#: **参考数据表**（Plan 02 Task 2 新增的第三个分区，Plan02 账本 P2-A1；Task 3 加第二张）。
#: 它既不是 ``seed_database`` 写的组织结构，也不是经适配器与管道流入的仿真业务数据，
#: 而是「专家维护的知识资产在 DB 里的**投影**」：``exercise`` 由
#: :func:`app.refdata_prescription.sync_exercises` 从 ``backend/data/exercises.yaml`` 灌、
#: ``prescription_template`` 由 :func:`app.refdata_prescription.sync_templates` 从
#: ``backend/data/prescription/*.yaml``（**18 个文件**）灌，唯一所有者都是那些 YAML。
#: ⚠️ **P3-A1（Critical）**：Task 3 的原文要求新建 ``app/seed/prescription.py`` 并改
#: ``seed_database``，那会违反 Global Constraint #10（``app/seed/`` 自 Plan 01 结案后重新
#: 冻结）并撞上下面那条守卫（``assert count == 0``），故照 Task 2 的先例把
#: 灌数据函数放进了 ``app/refdata_prescription.py``。本分区**因此只增表、不增写入方**。
#: ⚠️ **本分区到 Task 6 为止就停在两张**：本段此前预告过「Task 9 加 ``prescription`` 与
#: ``weekly_adjustment`` 时要判它们该进 ``DATA_TABLES`` 还是本分区」——**「届时」已到，
#: 判的结果是 ``DATA_TABLES``**（理由写在 :data:`DATA_TABLES` 的注释里）。本分区是
#: 「YAML 的投影」，而这两张表没有任何 YAML 与之对应，把它们放进来会让
#: ``sync_exercises`` / ``sync_templates`` 之外凭空多出两个不存在的写入方。
#: ⚠️ **本常量被下面 :func:`test_table_partition_is_exhaustive` 末尾那条
#: ``assert REFERENCE_TABLES == (…)`` 字面钉住**（Plan02 账本 P3-A6 第 4 项）：
#: 改一处必须改两处，且新值仍然要**字面写死**（硬规矩 #35：不能改成从
#: ``Base.metadata`` 反推）。
REFERENCE_TABLES = ("exercise", "prescription_template")


def test_table_partition_is_exhaustive():
    """三个分区必须**恰好穷尽** ``Base.metadata`` 的全部表（Plan02 账本 P2-A1）。

    **这条守的是一个此前没人写下来的隐性不变量**：Plan 01 结案时
    ``ORGANISATION_TABLES``（5 个）+ ``DATA_TABLES``（9 个）**恰好**是当时的全部 14 张表，
    于是下面那条「``seed_database`` 只写组织结构」的守卫看起来是全覆盖的。而它其实是
    **枚举式**的：加第 15 张表之后，新表会静默落在**任何**分区之外——``seed_database``
    越界写它也不会红，因为**两条守卫都只遍历「已被分区认领」的表**（下面那条是
    ``DATA_TABLES + REFERENCE_TABLES`` 与 ``ORGANISATION_TABLES`` 两圈），认领之外的表
    两条都看不到。
    （fix round 3 更正两点：① 此前这里把理由写成「那条守卫的遍历对象只有 ``DATA_TABLES``」，
    那是 Plan 02 Task 2 **之前**的口径；Task 2 已把「必须为 0」那一圈扩成 ``DATA_TABLES +
    REFERENCE_TABLES``，见
    :func:`test_seed_database_writes_only_organisation_tables_and_is_idempotent` 的
    docstring 与它的 ``for table in DATA_TABLES + REFERENCE_TABLES:``。② 上一句的「两个
    分区」也是 Task 2 之前的口径，今天是三个，故改成「任何分区」。**结论不变**——不在任何
    分区里的表两条守卫都遍历不到——只是理由要跟上当前的遍历对象。）

    故本条把「穷尽」变成显式断言。它与 :func:`test_seed_database_writes_only_organisation_tables_and_is_idempotent`
    是**一对**：本条保证「每张表都被某个分区认领」，那条保证「认领进
    ``DATA_TABLES`` / ``REFERENCE_TABLES`` 的表 ``seed_database`` 一行都不写」。少了本条，
    那条会对新表完全无感；少了那条，本条只是分类学。

    ⚠️ **本条守不住什么**（硬规矩 #39）：它只保证「每张表都在某个分区里」，**不保证归对了
    分区**。把 ``exercise`` 从 ``REFERENCE_TABLES`` 挪进 ``ORGANISATION_TABLES``，本条仍然
    全绿，而下面那条会红（``assert count > 0`` 说它是组织结构、必须被 ``seed_database``
    写入）——所以那个失效是**响亮的**，只是红在另一条上。
    """
    partitioned = set(ORGANISATION_TABLES) | set(DATA_TABLES) | set(REFERENCE_TABLES)
    actual = set(models.Base.metadata.tables)
    assert partitioned == actual, (
        f"表分区不再穷尽。未归类的表 {sorted(actual - partitioned)}"
        f"（新加的表必须归进三个分区之一，否则「只写组织结构」那条守卫会对它无感）；"
        f"分区里已不存在的表 {sorted(partitioned - actual)}"
    )
    # 三个分区**互不相交**：一张表同时属于两个分区，会让「seed_database 必须写 / 不许写」
    # 两条断言对同一张表给出相反的要求。用「三张清单的长度之和 == 并集大小」来查，
    # 这样交集非空时左边会大于右边。
    assert (
        len(ORGANISATION_TABLES) + len(DATA_TABLES) + len(REFERENCE_TABLES)
        == len(partitioned)
    ), "三个分区相交了，同一张表被归了两类"
    # Task 2 加 ``exercise`` 一张、Task 3 加 ``prescription_template`` 一张；抬这个数请连同
    # 计划 ``:700`` 的归属、以及本文件顶部 ``REFERENCE_TABLES`` 的注释一起改
    # （P3-A6 第 4 项：定义与这条断言是**两处**，改一处必须改两处）
    assert REFERENCE_TABLES == ("exercise", "prescription_template"), REFERENCE_TABLES


def test_seed_database_writes_only_organisation_tables_and_is_idempotent():
    """seed_database 只建组织结构；体测/体成分/问卷必须经适配器与管道流入。

    直接入库会绕过清洗与幂等，Task 10 的管道测试就再也测不到真实路径。

    ⚠️ Plan 02 Task 2 把下面「必须为 0」那一圈的遍历对象从 ``DATA_TABLES`` 扩成
    ``DATA_TABLES + REFERENCE_TABLES``（Plan02 账本 P2-A1）：``exercise`` 是参考数据，
    同样不该由 ``seed_database`` 写——它的灌数据入口是
    :func:`app.refdata_prescription.sync_exercises`。Global Constraint #10 把 ``app/seed/``
    自 Plan 01 结案后重新冻结，故 Task 2 **没有**新建 ``app/seed/prescription.py``、
    也**没有**改 ``seed_database`` 一行。
    ⚠️ **Task 3 是同一件事的第二次**（Plan02 账本 P3-A1，Critical）：Task 3 的原文同样要求
    新建 ``app/seed/prescription.py`` 并改 ``seed_database``——控制者在 Task 2 预检时查出
    这个缺陷并裁了，却没把裁定传导到 Task 3（→ 硬规矩 #75）。故 Task 3 也照 P2-A1 办：
    ``prescription_template`` 的灌数据入口是
    :func:`app.refdata_prescription.sync_templates`，``app/seed/`` 一个字没改，
    本条守卫的遍历对象自动多认一张表（它遍历的是 ``REFERENCE_TABLES``，不是硬编码的表名）。
    **这正是那条「三分区恰好穷尽 ``Base.metadata``」守卫的价值**：加了第 16 张表却忘了认领，
    :func:`test_table_partition_is_exhaustive` 会立刻红；认领进本分区而 ``seed_database``
    真去写了它，本条会红。
    """
    eng = create_engine("sqlite://")
    init_db(eng)
    cfg = SMALL
    with Session(eng) as session:
        seed_database(session, cfg)
        session.commit()
    with Session(eng) as session:
        assert session.scalar(select(func.count()).select_from(models.Student)) == cfg.students
        # 120 人 → ceil(120/38) = 4 个行政班（30 人/班），加 3 个分层班
        assert session.scalar(select(func.count()).select_from(models.CourseSection)) == 4 + 3
        assert session.scalar(
            select(func.count()).select_from(models.Enrollment)
        ) == 2 * cfg.students
        # 两学年各一个学期，当前学期被标记出来
        assert session.scalar(select(func.count()).select_from(models.Semester)) == len(SEMESTERS)
        current = session.scalar(
            select(models.Semester).where(models.Semester.is_current.is_(True))
        )
        assert current is not None and current.name == current_semester().name
        for table in DATA_TABLES + REFERENCE_TABLES:
            count = session.scalar(
                select(func.count()).select_from(models.Base.metadata.tables[table])
            )
            assert count == 0, f"{table} 不该由 seed_database 写入"
        for table in ORGANISATION_TABLES:
            count = session.scalar(
                select(func.count()).select_from(models.Base.metadata.tables[table])
            )
            assert count > 0, f"{table} 是组织结构，seed_database 必须写入"

    # 幂等：重跑一次不得翻倍（repo.upsert 按自然键更新而不是插入）
    with Session(eng) as session:
        seed_database(session, cfg)
        session.commit()
    with Session(eng) as session:
        assert session.scalar(select(func.count()).select_from(models.Student)) == cfg.students
        assert session.scalar(
            select(func.count()).select_from(models.Enrollment)
        ) == 2 * cfg.students


def test_generators_thread_the_callers_rng_and_never_touch_the_clock():
    """可复现性的两条守卫：生成器不得自建 rng，也不得读时钟。

    隐藏的第二个 ``np.random.default_rng()``（**无种子**）是打破「同种子字节级一致」
    最常见的写法；``date.today()`` 则会让同一个 seed 在不同日期产出不同的 birth 列。
    两者都用源码级检查钉住——运行时断言抓不到「恰好这一轮没走到那条分支」。

    全项目只有一个合法的随机数入口：``generate.py`` 里那一个**带种子**的根生成器，
    它被显式传给每一个生成器。除此之外任何 ``default_rng`` 调用、任何 ``np.random.seed``
    全局状态写法、任何「自己造一个 Generator」的写法、任何 ``import random``、以及任何
    ``np.random.<采样函数>`` 旧式全局采样写法（:data:`RNG_GLOBAL_FUNCS`，**含把该模块或该
    函数用 ``as`` 改名之后的写法**，见 :func:`_random_aliases`）都算违规。

    **判据本身由下面四条测试双向钉住**：:func:`test_the_random_source_guard_catches_every_forbidden_writing`
    逐种被禁写法造一个假模块喂给守卫、断言它报警（守卫抓不住任何东西比没有守卫更危险，
    评审 Minor m1）；:func:`test_the_guard_allows_the_single_seeded_root_generator`、
    :func:`test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed` 与
    :func:`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random` 是三条
    负对照（第二条钉住「``rng.normal(...)`` 这类接收者限定的合法采样不得被误判」，第三条
    钉住「别名表不得按名字猜——恰好叫 ``random`` 的根生成器是合法的」）。
    """
    assert _scan(SEED_DIR) == []


# 时钟：判据是**调用的末段属性名**，不是整串精确匹配。上一轮用 7 个精确串
# （"datetime.now"、"dt.date.today" …），于是 ``import datetime`` 之后写
# ``datetime.datetime.now()`` 会被 unparse 成 "datetime.datetime.now"——一个都不匹配，
# 守卫静默放行（评审 Minor m1 的第一种绕道）。末段属性名与导入别名无关，故
# ``dt.datetime.now`` / ``datetime.datetime.now`` / ``from datetime import datetime`` +
# ``datetime.now()`` 三种写法一律抓住。
CLOCK_METHODS = frozenset({"today", "now", "utcnow", "time", "monotonic", "perf_counter"})

# 第二个随机源：``default_rng`` 之外，「自己造一个生成器 / 自己播种 / 自己派生子流」的
# 写法也在列（评审 Minor m1 点名的 ``Generator(PCG64(...))`` 就是这一类）。
RNG_SOURCES = frozenset({
    "RandomState", "Generator", "SeedSequence", "seed",
    "PCG64", "PCG64DXSM", "MT19937", "Philox", "SFC64", "spawn", "fork",
})

# numpy 的**旧式全局采样函数**（评审 Minor-1，fix round 3 必修）。它们从 numpy 遗留的
# 全局单例 ``RandomState`` 取数：未被 ``np.random.seed()`` 播种时由 OS 熵自动播种，故
# **不受 ``cfg.seed`` 控制**，是货真价实的「隐藏第二随机源」——而且失效方式最难查：
# 每次跑都是合法数据，只是每次都不一样，SHA256 取证只能事后发现、定位不到写法。
#
# **与 :data:`RNG_SOURCES` 分开两个集合**，因为语义不同：那一个是「**造**一个源」，
# 这一个是「**用**numpy 的全局源」。混在一起会让违规消息失去指向性（看到 ``seed`` 与
# ``normal`` 并列在同一个集合里，读的人分不清是播种问题还是采样问题）。
# ``default_rng`` 有意**不在**这里——它是全项目唯一合法的随机数入口。
RNG_GLOBAL_FUNCS = frozenset({
    "rand", "randn", "random", "random_sample", "ranf", "sample",
    "normal", "standard_normal", "uniform", "standard_uniform",
    "randint", "integers", "choice", "shuffle", "permutation",
    "binomial", "poisson", "get_state", "set_state",
})


def _is_numpy_random_module(module: str) -> bool:
    """``module`` 是否是 numpy 的全局随机模块（``numpy.random`` 或它的子模块）。"""
    parts = module.split(".")
    return len(parts) >= 2 and parts[0] == "numpy" and parts[1] == "random"


def _default_rng_targets(tree: ast.AST) -> frozenset[str]:
    """被 ``X = …default_rng(…)`` 绑定的名字：那是**合法的根生成器**，不是随机模块的别名。

    单独收集一遍是为了把它从 :func:`_random_aliases` 的模块别名表里**显式剔除**：
    ``from numpy import random`` 之后又 ``random = np.random.default_rng(seed)`` 重绑一次，
    ``random.normal(...)`` 就已经是 ``Generator`` 的方法调用、与 ``rng.normal(...)`` 同形。
    """
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            bound, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            bound, value = [node.target], node.value
        else:
            continue
        if not (
            isinstance(value, ast.Call)
            and ast.unparse(value.func).rsplit(".", 1)[-1] == "default_rng"
        ):
            continue
        targets |= {t.id for t in bound if isinstance(t, ast.Name)}
    return frozenset(targets)


def _random_aliases(tree: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
    """从 **import 语句**收集两张别名表，返回 ``(module_aliases, func_aliases)``。

    * ``module_aliases`` —— 绑定到 numpy 全局随机模块的名字，于是**接收者是别名**的调用点
      也能判违规：``import numpy.random as npr`` → ``npr``（``npr.normal(...)``）、
      ``from numpy import random [as rnd]`` → ``random`` / ``rnd``（``random.normal(...)``）。
      上一轮的判据只认 ``np.random.<fn>`` / ``numpy.random.<fn>`` 两个字面接收者，这两条
      就是它的侧门（fix round 3 关切 ①，探针实测 MISSED）。
    * ``func_aliases`` —— 绑定到某个 numpy 全局采样函数的名字，于是**接收者已经消失**的
      裸调用也能判违规：``from numpy.random import normal`` → ``normal``，
      ``from numpy.random import normal as n`` → ``n``（``n(...)``）。

    **只能由 import 语句填充，绝不按「名字看起来像」填充**：``random =
    np.random.default_rng(0)`` 随后 ``random.normal(...)`` 是本项目唯一合法的根生成器用法，
    名字恰好叫 ``random`` 不构成违规；:func:`_default_rng_targets` 收集到的名字还会从
    ``module_aliases`` 里剔除一次，故「先 import 再重绑成根生成器」也不误伤。两个方向分别由
    :func:`test_the_random_source_guard_catches_every_forbidden_writing`（三种别名写法各两条）
    与 :func:`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random`（两条
    负对照）钉住。

    ``from numpy.random import Generator`` 这类**非采样函数**的导入不进任何一张表：它只作
    类型标注，负对照见 :func:`test_the_guard_allows_the_single_seeded_root_generator`。
    """
    module_aliases: set[str] = set()
    func_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # ``import numpy.random as npr`` 才产生新名字；无别名时绑定的是顶层
                # ``numpy``，``numpy.random.<fn>`` 由字面接收者那条规则负责。
                if alias.asname and _is_numpy_random_module(alias.name):
                    module_aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "numpy":
                # ``from numpy import random [as rnd]``：绑进来的是 numpy.random 模块本身
                for alias in node.names:
                    if alias.name == "random":
                        module_aliases.add(alias.asname or alias.name)
            elif _is_numpy_random_module(module):
                for alias in node.names:
                    if alias.name in RNG_GLOBAL_FUNCS:
                        func_aliases.add(alias.asname or alias.name)
    return frozenset(module_aliases), frozenset(func_aliases)


def _is_global_rng_call(
    text: str, module_aliases: frozenset[str], func_aliases: frozenset[str]
) -> bool:
    """``text``（``ast.unparse(node.func)``）是否是「从 numpy 全局 ``RandomState`` 取数」。

    **判据必须带接收者**，不能只看末段属性名：``Generator`` 对象上同样有 ``.normal()`` /
    ``.uniform()`` / ``.random()`` / ``.choice()`` / ``.shuffle()`` / ``.permutation()`` /
    ``.integers()``，而那是本项目**唯一合法**的采样写法（``generate.py`` 里那一个带种子的
    根生成器被显式传进每个生成器）。按末段名一刀切会把它们全判违规、``app/seed`` 立刻
    全红——一个把全部合法代码判成违规的守卫与一个什么都不判的守卫同样无用。故只有三种
    形状算违规：

    1. **限定到 numpy 的随机模块**：``np.random.<fn>`` / ``numpy.random.<fn>``
       （末段名的前一段是 ``random``、再前一段是 ``np`` / ``numpy``）；
    2. **限定到该模块的一个 import 别名**：``npr.<fn>`` / ``random.<fn>`` / ``rnd.<fn>``，
       其中接收者由 :func:`_random_aliases` 从 import 语句里收集（fix round 4）；
    3. **裸 ``<fn>``**，且 ``<fn>`` 确实在本模块里由 ``from numpy.random import <fn>``
       导入（含 ``as`` 改名后的名字）——此时调用点的接收者已经消失，与第 1 种同形，
       只能靠导入表区分。

    ``rng.normal(...)`` / ``self._rng.uniform(...)`` 上述三种形状都不满足 → 放行。负对照由
    :func:`test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed`
    （样本从 ``app/seed`` 现挖）与
    :func:`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random` 钉住。
    """
    parts = text.split(".")
    if len(parts) == 1:
        return text in func_aliases
    if parts[-1] not in RNG_GLOBAL_FUNCS:
        return False
    if parts[0] in module_aliases:
        return True
    return len(parts) >= 3 and parts[-2] == "random" and parts[-3] in ("np", "numpy")


def _offenders_in(filename: str, source: str) -> list[str]:
    """一段源码里全部「第二个随机源 / 时钟调用 / ``import random``」的违规点。

    抽成函数是为了让它**可被自证测试打**：把违规源码写进 ``tmp_path`` 下的假模块，
    再断言守卫对它返回违规——否则「守卫存在」与「守卫有效」是两件没人分得清的事。
    """
    tree = ast.parse(source)
    # 先扫一遍导入表：``ast.walk`` 是广度优先、不保证源码顺序，而裸调用（``normal(...)``）
    # 与别名限定调用（``npr.normal(...)``）都必须靠 import 语句才能与合法的
    # ``rng.normal(...)`` 区分开。两张表只由 import 填充，``default_rng(...)`` 的赋值目标
    # 再从模块别名表里显式剔除（见 _random_aliases 的 docstring）。
    module_aliases, func_aliases = _random_aliases(tree)
    module_aliases = module_aliases - _default_rng_targets(tree)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [
                f"{filename}:{alias.name}"
                for alias in node.names
                if alias.name.split(".")[0] == "random"
            ]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] == "random":
                offenders.append(f"{filename}:from {module}")
            elif _is_numpy_random_module(module):
                # ``from numpy.random import Generator`` 合法（只作类型标注），
                # 导入**采样函数**才违规——而且要在 import 那一行就报，不能只等调用点。
                offenders += [
                    f"{filename}:from {module} import {alias.name}"
                    for alias in node.names
                    if alias.name in RNG_GLOBAL_FUNCS
                ]
        elif isinstance(node, ast.Call):
            text = ast.unparse(node.func)
            head = text.rsplit(".", 1)[-1]
            if head == "default_rng":
                # 唯一的合法入口：generate.py 里那一个**带种子**的根生成器
                if filename != "generate.py" or not node.args:
                    offenders.append(f"{filename}:{node.lineno}:default_rng")
            elif head in RNG_SOURCES:
                offenders.append(f"{filename}:{node.lineno}:{text}")
            elif _is_global_rng_call(text, module_aliases, func_aliases):
                offenders.append(f"{filename}:{node.lineno}:{text}")
            if head in CLOCK_METHODS:
                offenders.append(f"{filename}:{node.lineno}:{text}")
    return offenders


def _scan(root: pathlib.Path) -> list[str]:
    """扫描一个目录下的全部 ``*.py``。目录不存在时**响亮失败**而不是空转全绿。"""
    assert root.is_dir(), f"目录缺失，守卫将空转全绿: {root}"
    return [
        offender
        for path in sorted(root.rglob("*.py"))
        for offender in _offenders_in(path.name, path.read_text(encoding="utf-8"))
    ]


# (违规源码, 期望出现在 offender 里的 token)。**每一种被禁写法一条**，含评审 Minor m1
# 点名漏掉的三种：无别名的 ``datetime.datetime.now()`` / ``datetime.date.today()``，
# 以及 ``Generator(PCG64(...))`` 这种「自己造一个生成器」。
FORBIDDEN_WRITINGS: tuple[tuple[str, str], ...] = (
    ("import random\nrandom.random()\n", "random"),
    ("from random import Random\nRandom(0).random()\n", "random"),
    ("import numpy as np\nrng = np.random.default_rng()\n", "default_rng"),
    ("import numpy as np\nrng = np.random.default_rng(20250828)\n", "default_rng"),
    ("import numpy as np\nnp.random.seed(0)\n", "seed"),
    ("import numpy as np\nnp.random.RandomState(0)\n", "RandomState"),
    ("import numpy as np\nnp.random.Generator(np.random.PCG64(0))\n", "Generator"),
    (
        "from numpy.random import Generator, PCG64, SeedSequence\n"
        "Generator(PCG64(SeedSequence(0)))\n",
        "Generator",
    ),
    ("import numpy as np\nrng = np.random.default_rng(0)\nrng.spawn(1)\n", "spawn"),
    ("import numpy as np\nrng = np.random.default_rng(0)\nrng.fork(1)\n", "fork"),
    ("import datetime as dt\ndt.datetime.now()\n", "now"),
    ("import datetime\ndatetime.datetime.now()\n", "now"),
    ("from datetime import datetime\ndatetime.now()\n", "now"),
    ("from datetime import datetime\ndatetime.utcnow()\n", "utcnow"),
    ("import datetime as dt\ndt.date.today()\n", "today"),
    ("import datetime\ndatetime.date.today()\n", "today"),
    ("from datetime import date\ndate.today()\n", "today"),
    ("import time\ntime.time()\n", "time"),
    ("import time\ntime.monotonic()\n", "monotonic"),
    ("import time\ntime.perf_counter()\n", "perf_counter"),
    # numpy 的**旧式全局采样函数**（评审 Minor-1，fix round 3 必修）：它们从 numpy 遗留的
    # 全局 RandomState 取数，不受 ``cfg.seed`` 控制 → 「同种子字节级一致」静默失效，而失效
    # 方式是最难查的那种：每次跑都是合法数据，只是每次都不一样。三种写法一律抓住——别名
    # 限定 ``np.random.<fn>``、全名限定 ``numpy.random.<fn>``、以及 ``from numpy.random
    # import <fn>`` 之后的裸调用（最后一种连 ``import`` 那一行本身也要报）。
    # 每一个 :data:`RNG_GLOBAL_FUNCS` 成员各一条，免得下次再靠「枚举一部分函数名」留洞。
    ("import numpy as np\nx = np.random.rand(10)\n", "np.random.rand"),
    ("import numpy as np\nx = np.random.randn(10)\n", "np.random.randn"),
    ("import numpy as np\nx = np.random.random(10)\n", "np.random.random"),
    ("import numpy as np\nx = np.random.random_sample(10)\n", "np.random.random_sample"),
    ("import numpy as np\nx = np.random.ranf(10)\n", "np.random.ranf"),
    ("import numpy as np\nx = np.random.sample(10)\n", "np.random.sample"),
    ("import numpy as np\nx = np.random.normal(0.0, 1.0, 10)\n", "np.random.normal"),
    ("import numpy as np\nx = np.random.standard_normal(10)\n", "np.random.standard_normal"),
    ("import numpy as np\nx = np.random.standard_uniform(10)\n", "np.random.standard_uniform"),
    ("import numpy as np\nx = np.random.uniform(0.0, 1.0, 10)\n", "np.random.uniform"),
    ("import numpy as np\nx = np.random.randint(0, 5, 10)\n", "np.random.randint"),
    ("import numpy as np\nx = np.random.integers(0, 5, 10)\n", "np.random.integers"),
    ("import numpy as np\nx = np.random.choice([1, 2, 3])\n", "np.random.choice"),
    ("import numpy as np\nxs = [1, 2, 3]\nnp.random.shuffle(xs)\n", "np.random.shuffle"),
    ("import numpy as np\nx = np.random.permutation(10)\n", "np.random.permutation"),
    ("import numpy as np\nx = np.random.binomial(10, 0.5, 4)\n", "np.random.binomial"),
    ("import numpy as np\nx = np.random.poisson(1.5, 4)\n", "np.random.poisson"),
    ("import numpy as np\nstate = np.random.get_state()\n", "np.random.get_state"),
    ("import numpy as np\nnp.random.set_state(state)\n", "np.random.set_state"),
    ("import numpy\nx = numpy.random.normal(0.0, 1.0, 10)\n", "numpy.random.normal"),
    # 裸调用：``from numpy.random import normal`` 之后，调用点的接收者已经消失，``text``
    # 就是 ``normal``，与合法的 ``rng.normal(...)`` **末段同形**。token 里的 ``2:`` 钉的是
    # **调用点那一行**（第 1 行的 ``import`` 由下一条用例单独钉住）：少了行号，只报 import
    # 不报调用点的守卫也会让这条用例假绿。
    ("from numpy.random import normal\nx = normal(0.0, 1.0, 10)\n", "2:normal"),
    ("from numpy.random import normal, uniform\n", "from numpy.random import normal"),
    # **import 别名**（fix round 4 必修，上一轮关切 ① 点名的两条侧门）：判据若只认
    # ``np.random.<fn>`` / ``numpy.random.<fn>`` 两个字面接收者，那么把 numpy 的全局随机
    # 模块**换个名字绑进来**就绕过去了——而绕过去的失效方式与 Minor-1 完全一样：每次跑
    # 都是合法数据，只是每次都不一样。三种写法各两条，token 里的 ``2:`` 钉的都是**调用点
    # 那一行**（不是 import 行），少了行号，只报 import 不报调用点的守卫也会假绿。
    # 别名表**只能由 import 语句填充**，负对照见
    # :func:`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random`。
    ("import numpy.random as npr\nx = npr.normal(0.0, 1.0, 10)\n", "2:npr.normal"),
    ("import numpy.random as npr\nx = npr.integers(0, 5, 10)\n", "2:npr.integers"),
    ("from numpy import random\nx = random.normal(0.0, 1.0, 10)\n", "2:random.normal"),
    ("from numpy import random as rnd\nx = rnd.uniform(0.0, 1.0, 10)\n", "2:rnd.uniform"),
    ("from numpy.random import normal as n\nx = n(0.0, 1.0, 10)\n", "2:n"),
    (
        "from numpy.random import uniform as u, choice as c\nx = u(0.0, 1.0, 10)\ny = c([1, 2])\n",
        "2:u",
    ),
)


@pytest.mark.parametrize(
    "source,token",
    FORBIDDEN_WRITINGS,
    ids=[f"{index:02d}-{token}" for index, (_source, token) in enumerate(FORBIDDEN_WRITINGS)],
)
def test_the_random_source_guard_catches_every_forbidden_writing(tmp_path, source, token):
    """守卫的**自证测试**：每种被禁写法都在 ``tmp_path`` 下造一个假模块，断言守卫报警。

    这条测试量的是守卫本身，不是 ``app/seed``。少了它，
    :func:`test_generators_thread_the_callers_rng_and_never_touch_the_clock` 全绿只证明
    「当前源码里没有这几种写法」，不证明「守卫能抓住这几种写法」——而评审实测上一轮的
    守卫对其中三种（无别名 ``datetime`` 的两种 + ``Generator(PCG64(...))``）恰好是瞎的。
    """
    fake = tmp_path / "fake_module.py"
    fake.write_text(source, encoding="utf-8")
    offenders = _scan(tmp_path)
    assert offenders, f"守卫没抓住这种写法：{source!r}"
    assert any(token in offender for offender in offenders), (
        f"守卫报了 {offenders}，但没有一条指向 {token!r}（源码 {source!r}）"
    )


def test_the_guard_allows_the_single_seeded_root_generator(tmp_path):
    """**负对照**：``generate.py`` 里那一个带种子的 ``default_rng`` 是合法的，守卫不得误报。

    没有这条，上面的自证测试全绿也可能只是因为守卫「见 ``ast.Call`` 就报」——一个永远
    报警的守卫会让真正的违规混在噪声里被忽略，与一个永远沉默的守卫同样无用。这里同时
    放行几个**长得像违规但不是**的写法：``Generator`` 只作类型标注、``cfg.seed`` 只作
    属性读取、``timepoint_date(...)`` 的末段属性名不在时钟集合里。
    """
    fake = tmp_path / "generate.py"
    fake.write_text(
        "import datetime as dt\n"
        "import numpy as np\n"
        "from numpy.random import Generator\n"
        "from app.seed.config import timepoint_date\n"
        "\n"
        "def root(cfg) -> Generator:\n"
        "    return np.random.default_rng(cfg.seed)\n"
        "\n"
        "def when(plan, timepoint) -> dt.date:\n"
        "    return timepoint_date(plan, timepoint)\n",
        encoding="utf-8",
    )
    assert _scan(tmp_path) == []


def test_the_guard_allows_a_local_variable_that_happens_to_be_named_random(tmp_path):
    """**负对照**（fix round 4）：别名表只能由 **import 语句**填充，不能由「名字看起来像」填充。

    堵住 ``from numpy import random`` + ``random.normal(...)`` 这条侧门最省事的写法是
    「凡接收者叫 ``random`` 就算违规」——它会当场误伤一个**恰好叫 ``random`` 的合法根生成器**：
    ``random = np.random.default_rng(0)`` 随后 ``random.normal(...)`` 与 ``rng.normal(...)``
    是同一件事（:data:`RNG_GLOBAL_FUNCS` 的判据本来就是「接收者是不是 numpy 的全局
    ``RandomState``」，而 ``Generator`` 实例不是）。一个把合法写法判成违规的守卫会让人
    学会无视它，与一个什么都不判的守卫同样无用。

    两个形状各钉一条：

    * **局部变量**——``def draw(random): return random.normal(...)``，模块里根本没有
      ``from numpy import random``，别名表为空 → 零违规；
    * **先 import 再重绑成根生成器**——``from numpy import random`` 之后
      ``random = np.random.default_rng(0)``：``default_rng(...)`` 的赋值目标被**显式排除**
      出别名表，故随后的 ``random.normal(...)`` 仍零违规。
    """
    local = tmp_path / "local_variable.py"
    local.write_text(
        "import numpy as np\n"
        "\n"
        "def draw(random):\n"
        "    return random.normal(0.0, 1.0, 10), random.permutation(10)\n",
        encoding="utf-8",
    )
    assert _scan(tmp_path) == [], "守卫把一个恰好叫 random 的合法局部变量判成了违规"
    local.unlink()

    rebound = tmp_path / "generate.py"
    rebound.write_text(
        "import numpy as np\n"
        "from numpy import random\n"
        "random = np.random.default_rng(20250828)\n"
        "x = random.normal(0.0, 1.0, 10)\n",
        encoding="utf-8",
    )
    assert _scan(tmp_path) == [], (
        "守卫没有把 default_rng(...) 的赋值目标排除出别名表：重绑之后的 random 已是合法的"
        "根生成器，不得再按 numpy 全局随机模块判违规"
    )


def test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed(tmp_path):
    """**负对照**：``rng.<fn>(...)`` 是本项目**唯一合法**的采样写法，守卫不得误报。

    ``Generator`` 对象上同样有 ``normal`` / ``uniform`` / ``random`` / ``choice`` /
    ``shuffle`` / ``permutation`` / ``integers``，而根生成器被显式传进每一个生成器正是靠
    这些方法——按「末段属性名」一刀切会把它们全判违规、``app/seed`` 立刻全红。一个把全部
    合法代码判成违规的守卫与一个什么都不判的守卫同样无用：真正的违规会混在噪声里被忽略。
    这条与 :func:`test_the_random_source_guard_catches_every_forbidden_writing` 一起把
    :data:`RNG_GLOBAL_FUNCS` 的判据**双向钉住**。

    样本**从 ``app/seed`` 现挖**而不是手抄：手抄的那份会在生成器换了写法之后悄悄失去代表性，
    而这里若哪天挖不到任何调用点，第一条断言会立刻红（负对照也不得空转）。
    """
    calls = sorted({
        ast.unparse(node)
        for path in sorted(SEED_DIR.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in RNG_GLOBAL_FUNCS
    })
    assert calls, "app/seed 里一处 rng.* 采样调用都没有：这条负对照已经空转"
    assert any(call.startswith("rng.normal(") for call in calls), calls
    assert any(call.startswith("rng.uniform(") for call in calls), calls
    assert any(call.startswith("rng.permutation(") for call in calls), calls
    assert any(call.startswith("rng.integers(") for call in calls), calls
    fake = tmp_path / "fitness.py"
    fake.write_text(
        "import numpy as np\n"
        "from numpy.random import Generator\n"
        "\n"
        + "".join(f"probe_{index} = {call}\n" for index, call in enumerate(calls)),
        encoding="utf-8",
    )
    assert _scan(tmp_path) == [], f"守卫把 app/seed 里的合法采样调用判成了违规：{calls}"


def test_cell_never_writes_a_numpy_scalar_repr_into_a_csv(tmp_path):
    """评审 Minor m2：``_cell`` 对 numpy 标量必须写 Python 标量，不写 ``np.float64(1.5)``。

    ``np.float64`` 是 Python ``float`` 的子类，故它会进 ``_cell`` 的 ``repr`` 分支，而
    numpy 2.x 下 ``repr(np.float64(1.5)) == 'np.float64(1.5)'``。那种字符串会原样落进
    CSV，适配器 ``float()`` 解析时抛 ``ValueError`` 并**中断整批抽取**。生成器目前每一处
    都包了 ``float(...)``，所以这条缺陷尚未触发（评审实测 21 个契约列 0 个 numpy 标量）；
    本测试把「将来漏包一次」变成当场红。

    走的是**完整落盘路径**（注入 → ``write_csv`` → 读回文本），不是只调一次 ``_cell``：
    ``inject_dirty`` 的 ``_damage`` 里 ``round(np.float64(...) / 100, 3)`` 会**保持**
    numpy 类型，正是最容易漏包 ``float()`` 的那条路径。
    """
    assert _cell(np.float64(1.5)) == "1.5"
    assert _cell(np.float64(-0.3)) == "-0.3"
    assert _cell(np.int64(7)) == 7
    assert "np.float64(" not in repr(_cell(np.float64(1.5)))

    cfg = SeedConfig(students=40, weeks=16, seed=20250828)
    ds = build_dataset(cfg)
    poisoned = []
    for record in ds["fitness"]:
        row = dict(record)
        for column in FITNESS_MEASURE_FIELDS:
            value = row[column]
            if value is None:
                continue
            # strength_count 是整数次数，其余是浮点测量值；两种 numpy 标量都要试
            row[column] = (
                np.int64(int(value)) if column == "strength_count" else np.float64(float(value))
            )
        poisoned.append(row)
    assert any(isinstance(row[column], np.floating) for row in poisoned for column in ("height_cm",))
    write_csv({"fitness": inject_dirty(poisoned, cfg, np.random.default_rng(1)),
               "body_comp": [], "survey": []}, tmp_path)
    text = (tmp_path / base.FITNESS_FILENAME).read_text(encoding="utf-8")
    assert "np.float64(" not in text and "np.int64(" not in text, (
        "CSV 里出现了 numpy 标量的 repr：适配器 float() 解析会抛 ValueError 并中断整批抽取"
    )
    rows = list(csv.DictReader(text.splitlines()))
    assert len(rows) >= len(poisoned)


def test_cell_covers_every_numpy_float_dtype_and_still_rejects_non_finite_ones(tmp_path):
    """评审 Minor-2（fix round 3 必修）：浮点分支的判据必须是 ``np.floating``，不是 ``float``。

    **只有 ``np.float64`` 是 Python ``float`` 的子类**：``np.float32`` / ``np.float16`` /
    ``np.longdouble`` 都不是，也不是 ``np.integer``，于是在上一条修好之后它们仍然掉进
    ``_cell`` 的兜底分支**原样返回**，一次绕过两件事——

    * ``repr(float(...))``：numpy 2.x 的 ``repr(np.float32(1.5))`` 是 ``'np.float32(1.5)'``，
      这种字符串会原样落进 CSV，适配器 ``float()`` 解析时抛 ``ValueError`` 中断整批抽取；
    * ``math.isfinite``：``np.float32('nan')`` 会把字面量 ``nan`` 写进 CSV。这一条更重，
      因为写侧有限性检查 + ``allow_nan=False`` 是 Ruling 39 的承重设计，被一个 dtype
      整体绕过去就等于这条防线不存在（NaN 能原样写盘、原样读回、全程零报错）。

    docstring 里那句「生成器目前每一处都包了 ``float(...)``，所以这条缺陷尚未触发」正是
    **「尚未触发」不等于「不可达」**：守卫的价值在于把「将来漏包一次」变成结构性不可达。

    落盘取证沿用上一条的手法（走完整 ``write_csv`` 再读回文本）：只断言 ``_cell`` 的返回值
    抓不住「落盘时被别的路径绕过」。
    """
    # 有限值：三种非 float64 的 numpy 浮点都要转成 Python 浮点的 repr，不泄漏 dtype
    assert _cell(np.float32(1.5)) == "1.5"
    assert _cell(np.float16(1.5)) == "1.5"
    assert _cell(np.longdouble(1.5)) == "1.5"
    for dtype in (np.float16, np.float32, np.float64, np.longdouble):
        cell = _cell(dtype(-0.25))
        assert cell == "-0.25", (dtype.__name__, cell)
        assert "np." not in str(cell), (dtype.__name__, cell)

    # 非有限值：一律响亮失败，且消息里含原值（否则定位不到是哪一列造出来的）
    for bad, token in (
        (np.float32("nan"), "nan"),
        (np.float16("nan"), "nan"),
        (np.float64("nan"), "nan"),
        (np.longdouble("nan"), "nan"),
        (np.float32("inf"), "inf"),
        (np.float32("-inf"), "inf"),
        (np.float64("inf"), "inf"),
        (float("nan"), "nan"),  # 既有行为不得回归
        (float("inf"), "inf"),
    ):
        with pytest.raises(ValueError) as excinfo:
            _cell(bad)
        message = str(excinfo.value)
        assert token in message.lower(), (type(bad).__name__, message)
        assert "非有限浮点值" in message

    # 负对照：其余分支一条都不许被这次改动带偏
    assert _cell(np.int64(3)) == 3
    assert _cell(np.int32(3)) == 3
    assert _cell(np.uint8(3)) == 3
    assert _cell(None) == ""
    assert _cell(7) == 7
    assert _cell(2.5) == "2.5"
    assert _cell("abc") == "abc"
    assert _cell({"dimensions": {"height_cm": 170.0}}) == '{"dimensions": {"height_cm": 170.0}}'
    with pytest.raises(ValueError):  # json.dumps(allow_nan=False) 那一侧同样不许放行
        _cell({"dimensions": {"height_cm": float("nan")}})

    # 端到端：整列换成 np.float32 走完整落盘路径，CSV 文本里既无 dtype repr 也无 nan/inf
    cfg = SeedConfig(students=40, weeks=16, seed=20250828)
    dataset = build_dataset(cfg)
    poisoned = []
    for record in dataset["fitness"]:
        row = dict(record)
        for column in FITNESS_MEASURE_FIELDS:
            value = row[column]
            if value is None:
                continue
            row[column] = (
                np.int64(int(value)) if column == "strength_count" else np.float32(float(value))
            )
        poisoned.append(row)
    # build_dataset 已经注入过一轮 missing，故 height_cm 有 None（被上面的 continue 跳过）；
    # 断言只针对**真的被换掉的那些**，且要求它非空（否则这条端到端取证会空转全绿）。
    converted = [row["height_cm"] for row in poisoned if row["height_cm"] is not None]
    assert converted and all(type(value) is np.float32 for value in converted)
    write_csv(
        {
            "fitness": inject_dirty(poisoned, cfg, np.random.default_rng(1)),
            "body_comp": [],
            "survey": [],
        },
        tmp_path,
    )
    text = (tmp_path / base.FITNESS_FILENAME).read_text(encoding="utf-8")
    assert "np.float32(" not in text and "np.int64(" not in text, (
        "CSV 里出现了 numpy 标量的 repr：适配器 float() 解析会抛 ValueError 并中断整批抽取"
    )
    assert "nan" not in text.lower() and "inf" not in text.lower(), (
        "CSV 里出现了非有限浮点字面量：Ruling 39 的写侧守卫被绕过了"
    )
    assert len(list(csv.DictReader(text.splitlines()))) >= len(poisoned)

    # 落盘路径上真的会炸，而不是只在直接调 _cell 时炸
    exploded = dict(poisoned[0])
    exploded["height_cm"] = np.float32("nan")
    with pytest.raises(ValueError, match="非有限浮点值"):
        write_csv({"fitness": [exploded], "body_comp": [], "survey": []}, tmp_path)


def test_inject_dirty_leaves_clean_records_untouched_when_all_rates_are_zero():
    """注入比例为 0 时必须一行不改：这是「注入是唯一脏数据来源」的反向证据。"""
    cfg = SeedConfig(
        students=120, weeks=16, seed=20250828,
        dirty={"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0},
    )
    rng = np.random.default_rng(cfg.seed)
    population = make_population(cfg, rng)
    latents = latent_profiles(population, cfg, rng)
    fitness = make_fitness_tests(population, latents, cfg, rng)
    body_comp = make_body_comp(population, latents, cfg, rng)
    survey = make_survey(population, latents, cfg, rng)
    for records in (fitness, body_comp, survey):
        assert inject_dirty(records, cfg, rng) == records
    sections = make_sections(population, cfg, rng, latents)
    assert set(sections) == {"course_sections", "enrollments"}
