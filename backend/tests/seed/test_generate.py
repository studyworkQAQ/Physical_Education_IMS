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
DATA_TABLES = (
    "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
    "percentile_snapshot", "derived_metrics", "stratification_result",
    "daily_sync_run", "cleaning_log",
)


def test_seed_database_writes_only_organisation_tables_and_is_idempotent():
    """seed_database 只建组织结构；体测/体成分/问卷必须经适配器与管道流入。

    直接入库会绕过清洗与幂等，Task 10 的管道测试就再也测不到真实路径。
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
        for table in DATA_TABLES:
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
    全局状态写法、任何「自己造一个 Generator」的写法、任何 ``import random`` 都算违规。

    **判据本身由下面两条测试双向钉住**：:func:`test_the_random_source_guard_catches_every_forbidden_writing`
    逐种被禁写法造一个假模块喂给守卫、断言它报警（守卫抓不住任何东西比没有守卫更危险，
    评审 Minor m1）；:func:`test_the_guard_allows_the_single_seeded_root_generator` 是负对照。
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


def _offenders_in(filename: str, source: str) -> list[str]:
    """一段源码里全部「第二个随机源 / 时钟调用 / ``import random``」的违规点。

    抽成函数是为了让它**可被自证测试打**：把违规源码写进 ``tmp_path`` 下的假模块，
    再断言守卫对它返回违规——否则「守卫存在」与「守卫有效」是两件没人分得清的事。
    """
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            offenders += [
                f"{filename}:{alias.name}"
                for alias in node.names
                if alias.name.split(".")[0] == "random"
            ]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "random":
                offenders.append(f"{filename}:from {node.module}")
        elif isinstance(node, ast.Call):
            text = ast.unparse(node.func)
            head = text.rsplit(".", 1)[-1]
            if head == "default_rng":
                # 唯一的合法入口：generate.py 里那一个**带种子**的根生成器
                if filename != "generate.py" or not node.args:
                    offenders.append(f"{filename}:{node.lineno}:default_rng")
            elif head in RNG_SOURCES:
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
