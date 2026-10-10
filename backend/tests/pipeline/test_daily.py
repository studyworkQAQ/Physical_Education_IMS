"""每日批处理编排（``Extract → Clean → Percentile → Derive → Stratify → Prescribe → Alert → Report → Commit``）的行为约束。

⚠️ **本文件覆盖前五个阶段 + Commit + Plan 03 Task 8 那个 Report 阶段的接线**：
Plan 02 Task 7 插入的 Prescribe 阶段的行为约束住在
``tests/pipeline/test_prescription_stage.py``（含 ``_replay_cleanup`` 扩到五张表之后
那两张处方表的清理与删除顺序），Plan 03 Task 7 的 Alert 阶段住在
``tests/pipeline/test_alert_stage.py``（含清单扩到六张），
Plan 03 Task 8 的 Report 阶段**本体**住在 ``tests/pipeline/test_report_stage.py``
（含清单扩到七张的那条 AST 守卫与周日判据的三格边界）。
本文件只钉 Report 阶段的**接线**：它跑在 Alert 之后、与 Alert 共享同一个 ``now``、
以及非周日一次都不调用。本文件与它们的**另一个交集**是下面那条全表 canonical
sha256——``PIPELINE_TABLES`` 已由 Task 7 从 9 张扩到 11 张（P7-A5），故那一条现在
**同时**守着处方的幂等。

计划 Step 1 给的 9 条 + 后续补的 2 条（趋势真值对账、双路径一致性），分六组：

* **跑通**一条（``test_run_daily_populates_all_stages``）：六个阶段各自的产物都落到了
  该落的那张表里，含七张表的计数；
* **幂等**三条：同业务日重跑七元组逐字相同（Review Focus #5）、标签集合逐人相同、
  以及 Ruling 32 专设的「同日重跑不得把百分位快照清空」；
* **快照按需物化**一条：次日无新体测数据时不重算（``batch_id`` 不同，删不到首日行）；
* **边界与纪律**四条：整批失败全量回滚、``insufficient_data`` 是一个合法标签、
  ``hit_rules`` 非空（Ruling 125：``explain()`` 按 ``hit_rules[-1]`` 取文案，空串会
  ``IndexError``；本条**刻意排除** ``insufficient_data`` 行之外的一切行，故 Z0 那一支的
  非空性由 ``models.py`` 的 docstring 与 Task 9 的变异实证共同承担）、
  以及组织结构不得经适配器重复插入（spec §3.4 骨架先行）；
* **趋势口径**一条（``test_trend_matches_the_generator_oracle_on_week1_anchors``）：
  Ruling 140 的端到端交叉验证，拿 Task 6 生成器的 ``trend_label`` 真值逐人对账。
  计划的 9 条里没有它，而它是「week1-vs-week1、``years = 1.0``」这条最易猜错的口径
  **唯一**的守卫——没有它，把趋势对比改成「两条最新记录」不会让任何断言变红。
* **双路径一致**一条（``test_memory_path_and_db_path_agree_at_the_pinned_business_date``）：
  Ruling 152 的锚点单一所有者守卫，同一批数据分别走 DB 路径与内存路径后逐人对账。
  没有它，「哪个 timepoint 是评估锚点」在两处漂移时上面那条趋势测试**不会红**。

数据一律来自 ``tmp_path`` 里的独立 sqlite 文件与临时 CSV 目录：不碰 ``backend/pe.db``，
也不往 ``backend/data/seed/`` 写任何东西（Ruling 68）。
学期一律按**名字**取（:func:`semester_id`，Ruling 173）：``scalar(select(M.Semester))`` 会
取到先插入的上学年 ``2024-2025-1``，那既不是 CLI 会跑的路径、也不是幂等键该用的那一半。
"""
import csv, datetime as dt, hashlib, json, pathlib, pytest
from collections import Counter
from sqlalchemy import create_engine, func, select
from app.db.session import init_db, Session
from app.db import models as M
from app.adapters.base import FITNESS_COLUMNS, FITNESS_FILENAME
from app.adapters.mock_lepao import MockLePaoAdapter
from app.pipeline import daily
from app.pipeline.daily import require_dates_in_semester, run_daily, semester_by_name
from app.pipeline.extract import previous_watermark
from app.pipeline.run_stratify import stratify_dataset
from app.seed.generate import seed_database, build_dataset, write_csv
from app.seed.config import SEMESTERS, SeedConfig, semester_end_date

CFG = SeedConfig(students=60, weeks=16, seed=20250828)

# 趋势真值对账专用（Ruling 140 / 75②）：**零注入**。缺省注入下 4% 的缺测会让
# national_total 变成 None → 趋势 INSUFFICIENT（合法状态，但对不了账），0.5% 的越界会把
# 某一项夹到底档、真的改掉那个人的趋势；两种都会让断言测到注入而不是测到口径。
CLEAN_CFG = SeedConfig(
    students=60, weeks=16, seed=20250828,
    dirty={"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0},
)

SEMESTER_NAME = "2025-2026-1"    # Ruling 173：CLI（--semester）与幂等键的查找键


def semester_id(session) -> int:
    """按**名字**取本学年的 id，不用 ``scalar(select(M.Semester))``（Ruling 173）。

    ``seed_database`` 写**两条** ``Semester``（``2024-2025-1`` 与 ``2025-2026-1``），而不带
    ``order_by`` 的 ``scalar(select(M.Semester))`` 实测取到的是**先插入的上学年
    ``2024-2025-1``（id=1）**。``run_daily`` 的 docstring 说 ``semester_id`` 只是「运行记录
    与快照的归属，不是数据的归属」，所以那样写功能上不炸、断言也全绿——但**测的不是 CLI
    （``--semester 2025-2026-1``）会跑的那条路径**，而幂等键正是 ``(semester_id,
    business_date)``，``percentile_snapshot.semester_id`` 还从它反查
    （``percentile_stage.run_percentile``）。
    """
    return session.scalar(
        select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME)
    )

@pytest.fixture
def seed_dir(tmp_path) -> pathlib.Path:
    d = tmp_path / "lepao"
    write_csv(build_dataset(CFG), d)      # 体测/体成分/问卷经适配器流入
    return d

@pytest.fixture
def session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, CFG)             # 只写组织结构
        yield s

@pytest.fixture
def clean_env(tmp_path):
    """零注入的 ``(session, seed_dir, dataset)``；同样落在 ``tmp_path`` 的独立 sqlite 文件上。"""
    d = tmp_path / "clean"
    ds = build_dataset(CLEAN_CFG)
    write_csv(ds, d)
    eng = create_engine(f"sqlite:///{tmp_path/'clean.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, CLEAN_CFG)
        yield s, d, ds

D = "2025-09-15"

def _counts(s):
    """Ruling 24 + Ruling 32：必须同时计数三张源表与 percentile_snapshot。

    只数派生表的幂等断言是**假保证**——源表若静默翻倍，派生表照样能算出
    「一致」的结果，而百分位快照、短板判定与趋势计算已全部失真且不报错。

    `PercentileSnapshot` 尤其不可漏（Ruling 32）：Step 3 的重放清理会按
    `batch_id` 删掉当日快照，而 Percentile 阶段「仅在有新体测/体成分数据时
    执行」——于是重跑同一天存在一条能溜过的路径：先删快照、再判定无新数据而
    跳过，快照被清空却没有任何断言变红。`test_percentile_snapshot_materialized
    _not_recomputed` 覆盖的是**次日**（`batch_id` 不同，删不到首日行），同样
    抓不到。
    """
    return tuple(s.scalar(select(func.count()).select_from(m)) for m in (
        M.DerivedMetrics, M.StratificationResult, M.CleaningLog,
        M.FitnessTestResult, M.BodyComposition, M.InterestSurvey,
        M.PercentileSnapshot,
    ))

def test_run_daily_populates_all_stages(session, seed_dir):
    sem = semester_id(session)
    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert run.status == "success"
    derived, strat, cleaning, fitness, bodycomp, survey, snapshot = _counts(session)
    assert derived == 60 and strat == 60 and cleaning > 0
    assert fitness > 0 and bodycomp > 0 and survey > 0
    assert snapshot > 0

def test_rerun_same_business_date_is_idempotent(session, seed_dir):
    # Review Focus #5
    sem, ad = semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad); first = _counts(session)
    run_daily(session, sem, D, ad); second = _counts(session)
    assert first == second
    assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 1

def test_labels_are_reproducible_across_reruns(session, seed_dir):
    sem, ad = semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    a = {(r.student_id, r.label) for r in session.scalars(select(M.StratificationResult))}
    run_daily(session, sem, D, ad)
    b = {(r.student_id, r.label) for r in session.scalars(select(M.StratificationResult))}
    assert a == b

def test_hit_rules_are_persisted(session, seed_dir):
    sem = semester_id(session)
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    rows = list(session.scalars(select(M.StratificationResult)))
    assert all(r.hit_rules for r in rows if r.label != "insufficient_data")

def test_percentile_snapshot_materialized_not_recomputed(session, seed_dir):
    sem, ad = semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    n1 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    run_daily(session, sem, "2025-09-16", ad)   # 无新体测数据
    n2 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    assert n1 == n2 and n1 > 0

def test_failure_rolls_back_whole_batch(session, seed_dir, monkeypatch):
    sem = semester_id(session)
    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr("app.pipeline.daily.stratify", boom)
    with pytest.raises(RuntimeError):
        run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    session.rollback()
    assert _counts(session) == (0, 0, 0, 0, 0, 0, 0)   # 派生三表 + 源三表 + 快照，全部回滚

def test_rerun_same_day_does_not_wipe_percentile_snapshot(session, seed_dir):
    # Ruling 32：堵住「先删当日快照、再判定无新数据而跳过」这条能溜过的路径
    sem, ad = semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    n1 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    run_daily(session, sem, D, ad)          # 同一业务日重跑
    n2 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    assert n1 > 0 and n2 == n1

def test_insufficient_data_students_are_not_stratified(session, seed_dir):
    sem = semester_id(session)
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    labels = {r.label for r in session.scalars(select(M.StratificationResult))}
    assert labels <= {"red", "yellow", "green", "insufficient_data"}

def test_organization_data_never_flows_through_adapter(session, seed_dir):
    # seed_database 已写入组织结构；管道不得重复插入学生
    sem = semester_id(session)
    before = session.scalar(select(func.count()).select_from(M.Student))
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert session.scalar(select(func.count()).select_from(M.Student)) == before == 60

def test_trend_matches_the_generator_oracle_on_week1_anchors(clean_env):
    """Ruling 140 的端到端交叉验证：趋势对比取「**每学年的 week1**」、``years = 1.0``。

    真值是 Task 6 生成器写进每条体测记录的 ``trend_label``（Ruling 75② 明写「趋势判据
    只在 week1 上由构造保证」），故零注入下 60 人**逐人**对得上、分布**恰好**等于
    ``allocate_quota(trend_mix, 60)`` 的精确配额。这不是容差断言：配额走最大余额法，
    按概率抽样才有波动，精确配额让「口径配错了」与「抽样抽歪了」不再互相掩盖。

    **它守卫的是本项目最容易猜错的一处口径**。改成「``<= business_date`` 的两条最新记录」
    会当场红：在 ``D = 2025-09-15`` 下本批含上学年 week1/week8/week16 + 本学年 week1，
    于是 prev 会从上学年 week1(2024-09-02) 变成上学年 week16(2024-12-16)、``years`` 从
    1.0 变成 ≈0.71 的分数，而 Ruling 114 的年均口径 ``Delta / years`` 会把趋势**放大
    1.4 倍**（Y4 触发面随之虚高），且它与 ``trend_label`` 永不可比。
    """
    s, d, ds = clean_env
    sem = semester_id(s)
    assert run_daily(s, sem, D, MockLePaoAdapter(d)).status == "success"

    truth = {row["student_no"]: row["trend_label"] for row in ds["fitness"]}
    no_by_id = {st.id: st.student_no for st in s.scalars(select(M.Student))}
    got = {no_by_id[r.student_id]: r.trend for r in s.scalars(select(M.DerivedMetrics))}
    # ① 逐人对账：零注入 ⇒ 两侧总分都可比 ⇒ 一个 INSUFFICIENT 都不该有
    assert len(got) == 60 and "insufficient_data" not in got.values()
    assert got == truth, [(k, truth[k], got[k]) for k in truth if truth[k] != got[k]]
    # ② 分布因此等于生成器的精确配额
    assert dict(Counter(got.values())) == {
        "持续下滑": 12, "波动大": 9, "稳步提升": 15, "稳定": 24}
    # ③ years 恒为 1.0（Ruling 123：无历史时也传 1.0，不得用 0 做第二重编码）
    assert {r.input_snapshot["years"]
            for r in s.scalars(select(M.StratificationResult))} == {1.0}

def test_memory_path_and_db_path_agree_at_the_pinned_business_date(clean_env):
    """Ruling 152：同一批数据在计划钉住的业务日期上，两条路径给出**逐人相同**的 label 与 trend。

    守的是「**哪个 timepoint 是评估锚点**」只能有一个所有者，以及
    ``run_stratify._from_dataset`` docstring 里那句承诺：「锚点取数据集里最新的那个
    ``week1``：这与 ``daily.py`` 在 ``D = 2025-09-15`` 上选出的锚点逐字相同（``2025-09-01``），
    两条路径因此在计划钉住的那个业务日期上给出同一批结果」。该承诺此前**零测试覆盖**，
    缺口是实测出来的：把 ``WEEK1_TIMEPOINT`` 改成 ``"week8"``，**当时那 418 条**里只有内存路径那条
    （418 是那时的套件规模，fix round 3 是 428 条；这个数字不被守卫，只是变异取证的记录）
    趋势测试红，本文件的 ``test_trend_matches_the_generator_oracle_on_week1_anchors``
    **全绿**——因为锚点当时有两个所有者（那个常量与 ``percentile_stage.assessment_anchor``
    里硬编码的 ``"week1"``），端到端守卫读的是后者。两处已合流到同一个常量，本测试是这道
    合流的守卫：锚点再分道，它当场红。

    **为什么钉在 ``2025-09-15``**：``D`` 更晚时两条路径**会**分道，那是签名限制的必然结果、
    不是算法分叉——DB 路径的体成分按真实 ``business_date`` 取最新一条，而 ``stratify_dataset``
    的签名里没有业务日期、恒停在 week1 那天（``run_stratify._from_dataset`` 的 docstring
    已述）。本数据集的六个采集日（上学年 ``2024-09-02 / 2024-10-21 / 2024-12-16``、
    本学年 ``2025-09-01 / 2025-10-20 / 2025-12-15``）里，``2025-09-15`` 落在本学年 week1
    与 week8 之间，故 ``<= D`` 的最新体成分就是 week1 那条，两侧完全同批。实测
    ``D = 2025-10-21`` 时同一批 60 人里 **12 人的 label 不同、trend 仍逐人相同**（趋势只由
    两个 week1 锚点决定，体成分只进 ``C``）——那正是 week8（``2025-10-20``）的体成分进了
    DB 路径、进不了内存路径。
    """
    s, d, ds = clean_env
    sem = semester_id(s)
    assert run_daily(s, sem, D, MockLePaoAdapter(d)).status == "success"

    no_by_id = {st.id: st.student_no for st in s.scalars(select(M.Student))}
    db_trend = {no_by_id[r.student_id]: r.trend for r in s.scalars(select(M.DerivedMetrics))}
    db_label = {no_by_id[r.student_id]: r.label
                for r in s.scalars(select(M.StratificationResult))}

    no_by_sid = {p["student_id"]: p["student_no"] for p in ds["population"]}
    results = stratify_dataset(ds).results
    mem_trend = {no_by_sid[r["student_id"]]: r["trend"] for r in results}
    mem_label = {no_by_sid[r["student_id"]]: r["label"] for r in results}

    assert len(db_trend) == len(mem_trend) == 60, (len(db_trend), len(mem_trend))
    # offender 一次性报全（Ruling 157：循环里逐条 assert 会在第一例就停、证据被截断）
    offenders = [
        f"{no} trend: DB={db_trend.get(no)!r} 内存={mem_trend.get(no)!r}"
        for no in sorted(set(db_trend) | set(mem_trend))
        if db_trend.get(no) != mem_trend.get(no)
    ] + [
        f"{no} label: DB={db_label.get(no)!r} 内存={mem_label.get(no)!r}"
        for no in sorted(set(db_label) | set(mem_label))
        if db_label.get(no) != mem_label.get(no)
    ]
    assert offenders == []


# ---------------------------------------------------------------------------
# Ruling 220 / 211 / 212 / 218：0 覆盖的运维路径
#
# 终审 B 亲跑 ``--cov=app.pipeline`` 量到 ``daily.py`` 只有 **78%**、``backfill.py`` **76%**，
# 而**四条 Critical/Major 缺陷全部住在那些 0 覆盖的行里**（``daily.py`` 的
# ``302-304 / 340-344 / 366-368`` 三处 ``unattributable += 1``、``87-90`` 的
# ``semester_by_name`` 报错分支；``backfill.py`` 的 ``203-208`` 单日失败留痕）。
# spec §12 只要求 ``domain/`` 100% 分支，所以这**不违反规格**——但「规格没要求 ⇒ 不需要」
# 这个推理被那四条缺陷直接反证。下面四条 + ``test_backfill.py`` 的一条把它们补上。
# ---------------------------------------------------------------------------

ORPHAN_NO = "UNKNOWN999"
SIX_DAYS = [f"2025-09-0{day}" for day in range(1, 7)]


def _append_orphan_fitness_row(seed_dir: pathlib.Path) -> None:
    """往 ``fitness.csv`` 追加一条**学号在 ``student`` 表里查无此人**的合法记录。

    这条记录本身完全合法（八个测量列都在 ``indicator_ranges.yaml`` 的区间内、日期零填充），
    唯一的毛病是学号解析不到人——正是 ``daily.py`` 的 ``_log_unattributable`` docstring
    自己点名预期的那种情况（「新生尚未建档而乐跑已有其体测记录」）。

    **用 Plan 01 自己的生成器造不出这个状态**：``build_dataset`` 与 ``seed_database`` 同源，
    每个学号都解析得到，故 ``tests/pipeline/`` 此前**没有任何一条**走到 ``unattributable``
    分支（Ruling 211 能藏 5 个 Task 的原因）。其余三条可达路径见账本 Ruling 211：
    接真实乐跑（Plan 03）、手工编辑 CSV、用不同 ``--students`` 分别生成 CSV 与库。
    """
    path = seed_dir / FITNESS_FILENAME
    with path.open(newline="", encoding="utf-8") as handle:
        columns = next(csv.reader(handle))
    row = dict.fromkeys(columns, "")
    row.update({
        "student_no": ORPHAN_NO,
        "batch_key": "2025-2026|week1",
        "tested_on": "2025-09-01",
        "height_cm": "175.0", "weight_kg": "70.0", "vital_capacity_ml": "3200.0",
        "sprint_50m_s": "8.5", "sit_and_reach_cm": "12.0", "standing_jump_cm": "215.0",
        "strength_count": "8", "distance_run_s": "300.0",
    })
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerow([row[column] for column in columns])


def test_orphan_student_no_yields_partial_but_still_advances_the_watermark(session, seed_dir):
    """Ruling 211 + 220①：孤儿学号 → ``status="partial"``，而水位线**仍然逐日推进**。

    改前 ``extract.previous_watermark`` 只认 ``status == "success"``，于是一条孤儿学号会让
    **每一天**都停在 ``partial``、水位线**永久冻结在 ``None``**、每天重抽全量，而退出码恒 0
    （Ruling 188 明确让 ``partial`` 不改退出码）→ **全程静默**。本轮亲跑的改前/改后对照
    （60 人、六天、独立临时库）::

        口径                     改前（只认 success）      改后（success + partial）
        ------------------------ ------------------------ --------------------------
        六天 status              partial ×6               partial, success ×5
        次批水位线                None ×6（永久冻结）       09-01 … 09-06（逐日推进）
        extracted_fitness        243 ×6（每天重抽全量）    243, 0, 0, 0, 0, 0
        cleaning_log 行数        804（孤儿学号 6 条）      134（孤儿学号 1 条）
        stratification_result    360                      360（**分层结果一字不差**）

    即代价全在重复劳动与审计噪声上：同一条数据质量问题留下**六条互相矛盾的交代**。

    **``partial`` 为什么该推进水位线**：``run_daily`` 的 docstring 把它定义为「**整批跑完**，
    但有记录因学号解析不到 ``student`` 表而被整条跳过（已在 ``cleaning_log`` 里逐条留痕）」
    ——那一天该入库的东西已经全部入库。``failed`` 才是「什么都没写进去」（本批已被 SAVEPOINT
    撤销），把它当水位线会让那一段数据永久丢失。

    **反例检查**（硬规矩 #23）：本条断言的是「水位线**逐日**推进」而不是「有一天推进了」，
    故「孤儿记录只影响它首次进入抽取窗口那一天」这个替代解释被排除——改前六天**全部**
    ``None``，改后六天**全部**是前一天。
    """
    _append_orphan_fitness_row(seed_dir)
    sem, adapter = semester_id(session), MockLePaoAdapter(seed_dir)

    statuses, watermarks, extracted = [], [], []
    for day in SIX_DAYS:
        run = run_daily(session, sem, day, adapter)
        statuses.append(run.status)
        extracted.append(run.extracted_fitness)
        # 「下一批会拿到的水位线」——这才是承重的那个量，不是本批用的那个
        watermarks.append(
            previous_watermark(session, dt.date.fromisoformat(day) + dt.timedelta(days=1))
        )

    assert statuses == ["partial"] + ["success"] * 5
    assert watermarks == SIX_DAYS, watermarks          # 逐日推进，一个 None 都没有
    assert extracted == [243, 0, 0, 0, 0, 0]           # 只有首批抽到新数据
    # 孤儿学号被跳过但**留了痕**（spec §4.6：必须能交代每一条被剔除的数据）
    orphan_logs = session.scalars(
        select(M.CleaningLog).where(M.CleaningLog.student_no == ORPHAN_NO)
    ).all()
    assert len(orphan_logs) == 1
    assert orphan_logs[0].student_id is None and orphan_logs[0].field == "student_no"
    assert orphan_logs[0].kind == "missing_dropped" and "查无此人" in orphan_logs[0].reason
    # 分层结果不受影响：孤儿记录既不入库也不参与任何计算
    assert session.scalar(select(func.count()).select_from(M.StratificationResult)) == 360


def test_semester_by_name_rejects_an_unknown_name_and_lists_the_existing_ones(session):
    """Ruling 220③：``semester_by_name`` 传错名字 → ``ValueError``，且消息里**列出现有学期名**。

    钉的是 ``daily.py`` 那条报错分支（终审 B 亲跑覆盖率：改前 ``87-90`` 四行 **Miss**；
    账本记的「实现者测过退出码 1」是**手工**测的，不在测试网里）。

    消息必须列出库里现有的学期名，因为 ``--semester`` 最常见的两种写法错误是传成学年
    （``2025-2026``）与传成 id（``2``）——只说「查无此名」等于让运维自己去猜合法值。
    而**不得**退回 ``scalar(select(Semester))`` 取「第一条」（Ruling 173）：那会静默取到
    先插入的上学年 ``2024-2025-1``，运行记录与 ``percentile_snapshot.semester_id``
    于是挂错学期，而六个阶段的计数看起来全都正常。
    """
    with pytest.raises(ValueError) as excinfo:
        semester_by_name(session, "2025-2026")          # 传成学年，漏了学期序号
    message = str(excinfo.value)
    assert "'2025-2026'" in message                     # 报出收到的值
    assert "2024-2025-1" in message and "2025-2026-1" in message    # 列出现有学期名
    assert "幂等键" in message

    # 正向一侧：按名字查得到，且查到的**不是**不带 order_by 的第一条（上学年）
    assert semester_by_name(session, "2025-2026-1").name == "2025-2026-1"
    assert session.scalar(select(M.Semester)).name == "2024-2025-1"


def test_cross_semester_rerun_of_the_same_business_date_fails_loudly(session, seed_dir):
    """Ruling 212 + 220④：同一业务日期在两个 ``semester_id`` 下各跑一次 → **响亮失败**。

    机制：幂等键是 ``(semester_id, business_date)``，而两张派生表的自然键是
    ``(student_id, computed_on)``——**两个键不同维度**，``_replay_cleanup`` 只按 ``batch_id``
    删、跨学期删不到对方。改前这会留下**两套「当前」结果**，而所有自然读法
    （``ORDER BY computed_on DESC LIMIT 1``）都稳定取到**陈旧那一套**（``computed_on`` 相同、
    无二级排序 → SQLite 按 rowid 升序扫 → 预跑那批 id 更小）。终审实测（60 人）：
    ``stratification_result`` 120 行 / 60 学生 / 60 人各有两行同 ``computed_on``、
    ``COUNT(DISTINCT input_snapshot) = 2``。教师大屏 ``WHERE computed_on=? GROUP BY label``
    会把 60 人的班报成 120 人。

    改后有**两道闸**，本条钉第二道（第一道是 CLI 守卫，见下面那条）：
    ``UniqueConstraint("student_id", "computed_on")`` 让第二批在**插入时**炸，而
    ``_stratify_and_persist`` 把底层那句 ``UNIQUE constraint failed: …`` 改写成一句人话
    （底层消息指不出「跨学期重跑」这个真因）。

    ⚠️ 唯一约束只对**新建**的库生效（``init_db`` 用 ``create_all``，对已存在的表不补约束），
    本条用的是 ``tmp_path`` 里的新库，故约束在。
    """
    adapter = MockLePaoAdapter(seed_dir)
    old_sem = session.scalar(select(M.Semester.id).where(M.Semester.name == "2024-2025-1"))
    new_sem = semester_id(session)
    assert old_sem != new_sem

    first = run_daily(session, old_sem, D, adapter)      # 预跑：挂到上学年名下
    assert first.status == "success"
    assert session.scalar(select(func.count()).select_from(M.StratificationResult)) == 60

    with pytest.raises(RuntimeError) as excinfo:
        run_daily(session, new_sem, D, adapter)          # 同一业务日期，换本学期
    message = str(excinfo.value)
    for token in ("(student_id, computed_on) 唯一约束", D, "另一个 semester_id", "Ruling 212"):
        assert token in message, message
    assert isinstance(excinfo.value.__cause__, Exception)   # 底层 IntegrityError 仍在 traceback 里
    session.rollback()

    # 第二批被 SAVEPOINT 全量撤销：预跑那一批**原样存活**，没有被半批写入污染
    rows = session.execute(select(M.StratificationResult.student_id)).all()
    assert len(rows) == 60                               # 60 行，不是 120 行
    assert len({row[0] for row in rows}) == 60           # 一人一行，不是一人两行同 computed_on
    # 失败本身也留了痕（_record_failure 的独立小事务）
    failed = session.scalar(select(M.DailySyncRun).where(
        M.DailySyncRun.semester_id == new_sem, M.DailySyncRun.status == "failed"))
    assert failed is not None and "唯一约束" in failed.error_summary


def test_cli_guards_reject_a_business_date_outside_the_semester_window(tmp_path):
    """Ruling 212 ③：``--date`` / ``--start`` / ``--end`` 必须落在 ``--semester`` 的区间内。

    这道闸住在**两个 ``main()``** 里而不是 ``run_daily`` 里：``semester_id`` 是运行记录与
    快照的归属、不是数据的归属，故函数层面跨学期组合是合法的（``_semester_of`` 会按记录
    自己的日期定位数据的学期）；但 CLI 层面它是**误操作**，而
    ``--semester 2024-2025-1 --date 2025-09-15`` 改前是一个**完全合法**的调用、
    没有任何东西拦它（``semester_by_name`` 只挡不存在的名字，而 ``2024-2025-1`` 存在）。

    库里只插两行 ``Semester``（日期取自 ``app.seed.config`` 这个既有所有者），不跑
    ``seed_database``：本条要守的是**区间校验**，与组织结构无关。
    """
    from app.pipeline import backfill, daily

    url = f"sqlite:///{tmp_path/'guard.db'}"
    eng = create_engine(url)
    init_db(eng)
    with Session(eng) as s:
        for plan in SEMESTERS:
            s.add(M.Semester(
                name=plan.name, start_date=plan.start_date,
                end_date=semester_end_date(plan, CFG.weeks),
                weeks=CFG.weeks, is_current=plan.is_current,
            ))
        s.commit()
        old_sem = semester_by_name(s, "2024-2025-1")
        new_sem = semester_by_name(s, "2025-2026-1")

    # 上学年区间是 [2024-09-02, 2024-12-23)（开学日 + 16 周 = 112 天，end_date 排他）
    assert (old_sem.start_date, old_sem.end_date) == (dt.date(2024, 9, 2), dt.date(2024, 12, 23))

    # ① 单元级：区间外响亮失败、消息给出学期区间与实际日期；区间内放行
    with pytest.raises(ValueError) as excinfo:
        require_dates_in_semester(old_sem, "--date", "2025-09-15")
    message = str(excinfo.value)
    for token in ("--date=2025-09-15", "2024-2025-1", "[2024-09-02, 2024-12-23)", "Ruling 212"):
        assert token in message, message
    require_dates_in_semester(new_sem, "--date", D)                  # 合法：不得抛
    require_dates_in_semester(new_sem, "--start", "2025-09-01", "2025-12-21")

    # ② end_date 是**排他**的（Ruling 174）：上学年最后一天 2024-12-22 合法、12-23 不合法
    require_dates_in_semester(old_sem, "--end", "2024-12-22")
    with pytest.raises(ValueError, match=r"--end=2024-12-23"):
        require_dates_in_semester(old_sem, "--end", "2024-12-23")

    # ③ 执行侧：两个 main() 都真的接上了这道闸（改前它们只查名字、不查区间）
    with pytest.raises(ValueError, match=r"--date=2025-09-15"):
        daily.main(["--semester", "2024-2025-1", "--date", "2025-09-15", "--db", url])
    with pytest.raises(ValueError, match=r"--start=2025-09-01"):
        backfill.main(["--semester", "2024-2025-1", "--start", "2025-09-01",
                       "--end", "2025-09-07", "--db", url])
    # 缺省的 --start/--end 天然落在区间内（start_date 本身、end_date − 1 天），不得被误伤：
    # 这一条由 test_backfill.py 的 test_cli_defaults_end_to_one_day_before_the_exclusive_end_date 守
    assert session_counts_untouched(eng) == 0


def session_counts_untouched(eng) -> int:
    """上面那两次 ``main()`` 必须在**跑任何一批之前**就抛，故库里一行运行记录都不该有。"""
    with Session(eng) as s:
        return s.scalar(select(func.count()).select_from(M.DailySyncRun))


# ---------------------------------------------------------------------------
# Ruling 218：幂等性的**强**断言（全表 canonical sha256）
# ---------------------------------------------------------------------------

# 管道写的 11 张表（5 张组织结构表由 ``seed_database`` 写、不经管道，故不在内；
# ``exercise`` 与 ``prescription_template`` 两张**参考数据**表也不在内——它们由
# ``app.refdata_prescription.sync_*`` 写，而管道不灌参考数据）。
# ⚠️ **Plan 02 Task 7 从 9 张扩到 11 张**（P7-A5：加 ``prescription`` 与
# ``weekly_adjustment``）。理由：那条断言是「幂等性的**强**断言」（Ruling 218），而处方是
# 本计划新加的最大一块派生数据；不覆盖等于「重放翻倍」这个失效形态只被一条较弱的行数断言
# 守着（``weekly_adjustment`` **没有任何唯一约束**，翻倍时连 IntegrityError 都不会有）。
# ⚠️ **连带**：扩表 + ``input_snapshot`` 加两个键之后，账本与 spec §1.3 印着的那个
# canonical sha256（``fe0a44e052c7946b…``）与「行数合计 882」**都过期了**，新实测值记在
# Task 7 报告的第 6 节（P7-A6：本条断言比的是 ``first == second``，不是与字面哈希相等，
# 故它**不会红**，红的是散文）。
PIPELINE_TABLES = (
    "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
    "percentile_snapshot", "derived_metrics", "stratification_result",
    "daily_sync_run", "cleaning_log", "prescription", "weekly_adjustment",
)

# spec §4.6:249 明确要求 ``daily_sync_run`` 有「起止时间」两列，而它们是**执行时刻**、
# 不是业务数据：同一业务日期重跑必然不同。故幂等性的口径是「除这两列外逐字段一致」
# （Ruling 218，spec §1.3 的措辞已按此更正）。
NON_DETERMINISTIC_COLUMNS = {"daily_sync_run.started_at", "daily_sync_run.finished_at"}


def canonical_dump(session) -> tuple[str, dict[str, int]]:
    """11 张表的全部行 → canonical JSON → sha256，另返回逐表行数。

    逐表按**主键升序**取行（主键唯一，故行序是规范序、不依赖插入顺序），每行摊成
    ``{列名: 值}``，整个 payload 用 ``sort_keys=True`` + 最紧凑分隔符序列化后取哈希。
    ``default=str`` 兜住 ``date`` / ``datetime``（它们的 ``str()`` 是零填充 ISO 形状）。

    **这比本文件原有的三条幂等测试强一个量级**：那三条只数行数（``_counts`` 的七元组）
    与比 ``{(student_id, label)}`` 集合，**没有一条比较 ``input_snapshot`` / ``hit_rules`` /
    ``annual_change`` / ``cleaning_log`` 的内容**——一个「行数对但 ``input_snapshot`` 全错」
    的回归改前抓不到。

    代理键 ``id`` **一并入哈希**：SQLite 的 rowid 分配是 ``max(现有 rowid) + 1``，
    而重放策略是「删本批 + 重插」，整批删净后新行仍从 1 起，故两次运行的 ``id`` 逐行相同。
    ⚠️ 这一点是 SQLite 特有的（换 ``AUTOINCREMENT`` 或别的后端会单调递增而不复用），
    届时本函数需要把 ``id`` 一起排除——排除后断言仍然成立，只是弱一档。
    """
    payload = {}
    for name in PIPELINE_TABLES:
        table = M.Base.metadata.tables[name]
        order = [table.c[column.name] for column in table.primary_key.columns]
        rows = session.execute(select(table).order_by(*order)).mappings().all()
        payload[name] = [
            {
                column: value for column, value in row.items()
                if f"{name}.{column}" not in NON_DETERMINISTIC_COLUMNS
            }
            for row in rows
        ]
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest(), {name: len(payload[name]) for name in PIPELINE_TABLES}


def test_rerunning_the_same_business_date_reproduces_every_table(session, seed_dir):
    """Ruling 218：同一业务日期重跑，**除 ``daily_sync_run`` 的起止时间两列外**全表逐字段一致。

    spec §1.3 此前写的是「字节级一致」，而它按字面**不可满足**、且与 spec §4.6:249
    （明确要求 ``daily_sync_run`` 有「起止时间」两列）**互相冲突**。更强的读法
    （**文件级**字节一致）**结构性不可达、与时间戳无关**：终审 B 把 ``datetime.now()``
    冻结成恒返回 ``2026-01-01 00:00:00`` 后，``.db`` 文件三次仍然互不相同——机制是
    SQLite 文件头偏移 24 的 4 字节大端 change counter 每次写事务 +1（实测 19→20→21），
    而重放策略是「删本批 + 重插」，两者都使文件字节必然变化。spec §1.3 的措辞已按此更正。

    本条钉的是**可行且更强**的那一侧：11 张表的全部行按主键排序后 canonical 序列化取
    sha256，两次运行相同。终审 B 亲跑的三次运行（60 人、同一业务日期）在剔除那两列后
    逐字相同（当时是 9 张表、``2ef85d79f7e0f2e15a2f903aded183b025dee3dad3653fd2098baad403d17b92``）；
    **本条不断言那个具体哈希**——它随人数、seed 与注入配置变，钉死它就变成另一条同源断言
    （硬规矩 #35）。断言的是「两次运行相同」这个关系，两侧由两次**独立执行**产生。

    ⚠️ **那个字面哈希已经过期三次**（P7-A6；硬规矩 #26：一个修复改变了另一个修复的取证
    基线）：Task 7 首轮的**扩表**（P7-A5，9 → 11）与 **``input_snapshot`` 加两个键**
    （P7-A1 / P7-A3）各是一次，**fix round 1 给 ``prescription`` 加 ``label_at_generation``
    列**（F1-1，那张表 15 → **16** 列）是第三次。本夹具（``CFG``：60 人 /
    ``seed=20250828`` / 缺省注入，``D = 2025-09-15``）在 fix round 1 之后本轮亲跑
    （``canonical_dump`` 逐字复用，n=1，两遍 ``run_daily``）::

        表集合          sha256                                                            行数合计
        --------------  ----------------------------------------------------------------  --------
        9 张（Plan 01）  1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952   882
        11 张（Task 7）  2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df   942

    两个哈希都在两次运行之间**逐字相同**（``first == second`` 成立）。
    **9 张那一行在 Task 7 首轮变过一次**——不是因为扩表，而是因为
    ``run_stratify.input_snapshot_of`` 加了 ``"bmi"`` 与 ``"snapshot_muscle_p10"`` 两个键
    （P7-A1 / P7-A3），而 ``stratification_result`` 在那 9 张里；**fix round 1 之后它逐字
    未变**（本轮亲验：那一轮只动 ``prescription`` 一张表，而它不在这 9 张里）。
    **11 张那一行两轮各变一次**：首轮是扩表（+60 张处方）与那两个键，fix round 1 是
    ``prescription`` 多了 ``label_at_generation`` 这一列（**列变而行数不变**，仍是
    882 + 60 张处方 + 0 条周微调 = **942**）。
    ⚠️ **这四个值都不被守卫**（本条刻意不断言字面哈希），它们只是一次取证记录；
    账本与 spec §1.3 印着的 ``fe0a44e052c7946b…`` / 「行数合计 882」由控制者按此回填
    （fix round 1 的两个新值也已交回控制者）。
    """
    sem, adapter = semester_id(session), MockLePaoAdapter(seed_dir)

    run_daily(session, sem, D, adapter)
    first, rows_first = canonical_dump(session)
    started_first = session.scalar(select(M.DailySyncRun.started_at))

    run_daily(session, sem, D, adapter)
    second, rows_second = canonical_dump(session)

    assert rows_first == rows_second, (rows_first, rows_second)
    assert sum(rows_first.values()) > 0                  # 反空转：真的 dump 到了行
    assert first == second, "同一业务日期重跑后全表 canonical sha256 不同"

    # 被排除的那两列**确实**变了（否则「排除它们」这个口径就没被证明是必要的，
    # 本条也就退化成一条普通的行数断言）
    assert session.scalar(select(M.DailySyncRun.started_at)) != started_first
    assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 1


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 5：fitness_test_batch.test_date 不得随抽取窗口漂移
# ---------------------------------------------------------------------------

#: 缺省种子数据里本学年 week1 那批的采集日**只有一个**，故先把它摊成多日，
#: 「test_date 随抽取窗口漂移」才可达。5 天 × 60 人 = 每天 12 人。
_SPREAD_DAYS = ("2025-09-01", "2025-09-02", "2025-09-03", "2025-09-04", "2025-09-05")


def _spread_week1_tested_on(seed_dir: pathlib.Path, days: tuple[str, ...]) -> int:
    """把 ``fitness.csv`` 里本学年 ``week1`` 那批记录的 ``tested_on`` 按行序轮转到 ``days`` 上。

    **为什么必须自己造多日批次**：缺省种子数据里一个批次只有一个采集日（实测 60 人 /
    ``seed=20250828``，命令是 ``build_dataset(CFG)`` 之后按 ``parse_batch_key`` 分组数
    ``tested_on`` 的 distinct 值）::

        ('2024-2025', 'week1')   n=60  distinct=['2024-09-02']
        ('2024-2025', 'week8')   n=61  distinct=['2024-10-21']
        ('2024-2025', 'week16')  n=61  distinct=['2024-12-16']
        ('2025-2026', 'week1')   n=60  distinct=['2025-09-01']
        ('2025-2026', 'week8')   n=61  distinct=['2025-10-20']
        ('2025-2026', 'week16')  n=62  distinct=['2025-12-15']

    每组恰好一个值，于是「同一份 CSV、只改执行顺序就得到不同的 ``test_date``」在缺省数据上
    **不可达**——这正是终审 B「构造了反例但没能演示 anchor 真的翻转」的原因，也是它把这条
    定为 Major 而不是 Critical 的原因。真实的乐跑接口不会这么整齐：一次 week1 体测跨好几个
    采集日是常态（院系轮流进场）。
    """
    path = seed_dir / FITNESS_FILENAME
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    touched = 0
    for row in rows:
        if row["batch_key"] == "2025-2026|week1":
            row["tested_on"] = days[touched % len(days)]
            touched += 1
    assert touched == 60, f"本学年 week1 的记录数不是 60，夹具口径变了：{touched}"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FITNESS_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return touched


def test_fitness_batch_folds_test_date_to_the_earliest(session):
    """``_fitness_batch`` 对乱序的日期做 ``min`` 折叠，且四次调用只产生**一行**批次。

    直接喂乱序日期而不走 ``run_daily``：缺省数据造不出多日批次（见
    :func:`_spread_week1_tested_on` 的 docstring），而折叠本身是这个修复的全部内容。

    四次调用的期望值逐个**写死**（硬规矩 #35，不从被测函数读回来）。改回「每条记录都
    PATCH ``test_date``」之后第三次会得到 ``2025-09-05`` 而不是 ``2025-09-01``，当场红。

    ``min`` 折叠而不是「插入时写、更新时不动」：后者仍然依赖执行顺序（先跑的那天赢），
    而 ``min`` 可交换、可结合，任意顺序任意次重放都收敛到同一个值——**这才是选它的理由**，
    与「保守」无关。取「最早」在**可用性**方向上是**提前**、不是延后：``assessment_anchor``
    的判据是 ``test_date <= as_of``（``app/pipeline/percentile_stage.py:133``），``test_date``
    越小满足它的 ``as_of`` 越多。实测（内存库，同一批 5 条成绩横跨 ``2025-09-01..09-05``、
    只改 ``test_date`` 一个值，逐日调用 ``assessment_anchor``）：``test_date=09-01`` 从
    ``as_of=09-01`` 起就被选中，``test_date=09-05`` 要等到 ``as_of=09-05``——两行逐日输出
    见 :func:`app.pipeline.daily._fitness_batch` 的 docstring。这是有意的：批次内更晚的那些
    记录由 ``fitness_test_result.tested_on <= as_of``（``percentile_stage.py:176``）逐行
    截断兜住，故读不到未来数据。
    """
    semester = session.scalar(select(M.Semester).where(M.Semester.name == SEMESTER_NAME))
    assert semester is not None, "夹具应已由 seed_database 建好本学年"
    assert session.scalar(select(func.count()).select_from(M.FitnessTestBatch)) == 0

    calls = (
        (dt.date(2025, 9, 8), dt.date(2025, 9, 8)),   # 首条：插入，用它自己的值
        (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 更早 → 折叠下去
        (dt.date(2025, 9, 5), dt.date(2025, 9, 1)),   # 更晚 → 不动（改回 PATCH 就是 09-05）
        (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 重复 → 幂等
    )
    for given, want in calls:
        batch = daily._fitness_batch(session, semester, "week1", given, "2025-2026")
        session.flush()
        session.expire_all()          # 强制从库里读回，不测内存里的残留值
        assert batch.test_date == want, f"喂 {given.isoformat()} 后应为 {want.isoformat()}"

    assert session.scalar(select(func.count()).select_from(M.FitnessTestBatch)) == 1, (
        "幂等键 (semester_id, timepoint) 失效了：同一个 week1 批次被插出了第二行"
    )


@pytest.mark.parametrize("days_to_run", [
    ("2025-09-15",),                    # 一次跑完整个窗口
    ("2025-09-03", "2025-09-15"),       # 先跑到窗口中间，再跑完
])
def test_batch_test_date_is_the_earliest_tested_on_whatever_the_window(
    session, seed_dir, days_to_run
):
    """生产形状下的同一条不变量：``test_date`` == 该批次全部成绩里**最早**的 ``tested_on``。

    两个参数化用例是「一次跑完」与「分两次跑」；两边都必须得到 ``2025-09-01``。
    期望值 ``2025-09-01`` 是 :data:`_SPREAD_DAYS` 里的最小值、**字面写死**，不从
    ``FitnessTestResult`` 读回来跟自己比（那样两侧同源，硬规矩 #35）；右侧那个
    ``func.min(...)`` 是**独立**用 SQL 从另一张表算出来的同一量，用来交叉核对。

    改回「每条记录都 PATCH ``test_date``」之后两个用例都会得到 ``2025-09-05``
    （CSV 行序轮转 5 天，第 60 行落在 ``_SPREAD_DAYS[59 % 5]`` = 最后一天），当场红。
    """
    _spread_week1_tested_on(seed_dir, _SPREAD_DAYS)
    sem = semester_id(session)
    for day in days_to_run:
        assert run_daily(session, sem, day, MockLePaoAdapter(seed_dir)).status == "success"

    batch = session.scalar(
        select(M.FitnessTestBatch).where(
            M.FitnessTestBatch.semester_id == sem,
            M.FitnessTestBatch.timepoint == "week1",
        )
    )
    assert batch is not None
    assert batch.test_date == dt.date(2025, 9, 1), (
        f"跑了 {days_to_run} 之后 test_date 漂到了 {batch.test_date.isoformat()}"
    )
    earliest = session.scalar(
        select(func.min(M.FitnessTestResult.tested_on))
        .where(M.FitnessTestResult.test_batch_id == batch.id)
    )
    assert earliest == dt.date(2025, 9, 1)
    # 反空转：这个批次真的有跨多日的记录，否则「min == test_date」会退化成平凡真
    distinct = session.execute(
        select(M.FitnessTestResult.tested_on)
        .where(M.FitnessTestResult.test_batch_id == batch.id)
        .distinct()
    ).scalars().all()
    assert sorted(distinct) == [dt.date.fromisoformat(d) for d in _SPREAD_DAYS], distinct


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 4 第 4 项：缺线组数走计数列，不再塞进 error_summary
# ---------------------------------------------------------------------------

def test_muscle_line_gaps_lands_in_its_own_count_column(session, seed_dir):
    """``muscle_line_gaps`` 承载缺线组数，``error_summary`` 在成功运行下保持 ``NULL``。

    ``4`` 是实测值（60 人 / ``seed=20250828`` / 业务日期 ``2025-09-15``，缺省注入）：
    60 人摊到 4 个 (性别 × 年级组) 组，每组约 15 人 < ``MIN_SAMPLE = 30``，而肌肉量
    **没有国标常模可降级**（Ruling 121 第 4 步），故四组全部不产出 P20 判定线。
    字面写死在这里，不从被测列读回来（硬规矩 #35）。

    ``error_summary is None`` 钉住 Plan02 Ruling 13 的「**直接切、不双写**」：谁把那段
    「注意（非错误）：…」自由文本加回去，这一句当场红。切之前自己复验过零消费者
    （``git grep -n "error_summary" -- backend/``：写入点只有 ``daily._record_failure``
    与 ``run_daily`` 的 upsert 归零，读取点只有 ``main()`` 的 CLI 打印与两条断言真错误的
    测试；``git grep -n "注意（非错误）" -- backend/`` 只有写入处一条）。
    """
    sem = semester_id(session)
    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert run.status == "success"
    assert run.muscle_line_gaps == 4
    assert run.error_summary is None

    # 反空转：判定线**确实**缺了，不是「本来就有 4 条线」被误数成 4 个缺口
    assert session.scalar(
        select(func.count()).select_from(M.PercentileSnapshot)
        .where(M.PercentileSnapshot.item == "muscle_mass_kg")
    ) == 0
    # 六项计分项的判定线则照常物化（60 人 < 30 × 2 时也降级为国标常模，但**有**行）
    assert session.scalar(
        select(func.count()).select_from(M.PercentileSnapshot)
    ) > 0

    # 落到了库里，不只是内存对象上
    session.expire_all()
    got = session.get(M.DailySyncRun, run.id)
    assert got.muscle_line_gaps == 4 and got.error_summary is None


# ---------------------------------------------------------------------------
# Plan 03 Task 8：Report 阶段接进来了（第 8 个阶段 = spec §5 的第 9 阶段 Weekly）
# ---------------------------------------------------------------------------

#: **周日**（学期第 2 周的最后一天）。⚠️ 与 :data:`D` = ``2025-09-15``（周一）
#: 只差一天，而 ``CFG`` 的学期起点是 ``2025-09-01``（也是周一），故
#: ``semester_week_of(2025-09-01, 2025-09-14) == 2``。
SUNDAY = "2025-09-14"


def test_the_report_stage_runs_last_and_shares_one_instant_with_the_alert_stage(
    session, seed_dir, monkeypatch
):
    """**阶段序列 + 同一个 ``now``**：Report 跑在 Alert **之后**，且两个阶段拿到的
    是**同一个时刻**。

    两拍，各挡一个失效：

    ① **顺序**：``calls`` 记录两个 spy 被调用的先后。倒过来（Report 在 Alert 之前）
       的话，周报的「预警汇总」与「算法建议」读不到当天刚触发的那些预警
       ——spec §8.5 逐字要求「基于 ``YELLOW_CLASS_RPE_HIGH`` 等班级级信号」给出建议，
       而那一条信号正是同一批里刚写进 ``alert`` 表的。
    ② **同一个 ``now``**：期望侧是 ``evaluate_alerts`` 那个 spy **现场记下来**的
       ``now``（不是 ``weekly_class_report.generated_at`` 自己，否则两侧同源），
       另一侧是库里那一列。两者相等才说明 :func:`app.pipeline.daily.run_daily`
       把**一个** ``dt.datetime.now()`` 的结果喂给了两个阶段。
       ⚠️ 失效形态：两个阶段各调一次 ``now()`` 的话，同一批里
       ``alert.triggered_at`` 与 ``weekly_class_report.generated_at`` 会差几十毫秒，
       而教师端按时刻排序时，一份周报会排在它所汇总的那些预警**之前**
       ——「这份周报怎么可能已经知道那条预警」。

    ⚠️ 全部 ``weekly_class_report`` 行**共享同一个** ``generated_at``（本批一个时刻，
    不是一班一个时刻）：否则同一次运行的 17 份周报会有 17 个时刻，
    而「哪几份是同一批生成的」就无从回答。
    """
    from app.db.models.feedback import WeeklyClassReport
    from app.pipeline import daily as daily_module

    calls: list = []
    seen: dict = {}
    real_alerts = daily_module.evaluate_alerts
    real_reports = daily_module.generate_weekly_reports

    def alert_spy(sess, sem_id, batch_id, as_of, **kwargs):
        calls.append("alert")
        seen["now"] = kwargs["now"]
        return real_alerts(sess, sem_id, batch_id, as_of, **kwargs)

    def report_spy(sess, sem_id, batch_id, week, **kwargs):
        calls.append("report")
        seen["report_now"] = kwargs["now"]
        seen["week"] = week
        return real_reports(sess, sem_id, batch_id, week, **kwargs)

    monkeypatch.setattr(daily_module, "evaluate_alerts", alert_spy)
    monkeypatch.setattr(daily_module, "generate_weekly_reports", report_spy)

    sem = semester_id(session)
    run = run_daily(session, sem, SUNDAY, MockLePaoAdapter(seed_dir))
    assert run.status in ("success", "partial")
    assert calls == ["alert", "report"], f"阶段顺序错了：{calls}"
    assert seen["week"] == 2, "2025-09-14 是学期（2025-09-01 开学）的第 2 周"
    assert seen["report_now"] == seen["now"]

    rows = list(session.scalars(select(WeeklyClassReport)))
    assert rows, "60 人的编班至少有 1 个有名册的教学班"
    assert {row.generated_at for row in rows} == {seen["now"]}
    assert {row.week for row in rows} == {2}
    assert {row.batch_id for row in rows} == {run.id}


def test_a_non_sunday_never_calls_the_report_stage(session, seed_dir, monkeypatch):
    """**非周日不调用**周报阶段（spec §8.5 逐字「每周日批处理生成」）。

    ⚠️ 判据是「spy 一次都没被调用」，**不是**「``weekly_class_report`` 是空表」：
    后者在「调用了、但名册全为空 → ``skipped``」时也是空表，两档同形。
    ⚠️ ``D`` = ``2025-09-15`` 是**周一**，与上面那个周日只差一天。
    """
    from app.db.models.feedback import WeeklyClassReport
    from app.pipeline import daily as daily_module

    calls: list = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("非周日不该调用 generate_weekly_reports")

    monkeypatch.setattr(daily_module, "generate_weekly_reports", spy)
    sem = semester_id(session)
    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert run.status in ("success", "partial")
    assert calls == []
    assert dt.date.fromisoformat(D).weekday() == 0, "D 必须是周一，否则本条空转"
    assert session.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0
