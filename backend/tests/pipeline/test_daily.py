"""每日批处理编排（``Extract → Clean → Percentile → Derive → Stratify → Commit``）的行为约束。

计划 Step 1 给的 9 条 + 本 Task 补的 1 条趋势真值对账，分五组：

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

数据一律来自 ``tmp_path`` 里的独立 sqlite 文件与临时 CSV 目录：不碰 ``backend/pe.db``，
也不往 ``backend/data/seed/`` 写任何东西（Ruling 68）。
"""
import pathlib, pytest
from collections import Counter
from sqlalchemy import create_engine, func, select
from app.db.session import init_db, Session
from app.db import models as M
from app.adapters.mock_lepao import MockLePaoAdapter
from app.pipeline.daily import run_daily
from app.seed.generate import seed_database, build_dataset, write_csv
from app.seed.config import SeedConfig

CFG = SeedConfig(students=60, weeks=16, seed=20250828)

# 趋势真值对账专用（Ruling 140 / 75②）：**零注入**。缺省注入下 4% 的缺测会让
# national_total 变成 None → 趋势 INSUFFICIENT（合法状态，但对不了账），0.5% 的越界会把
# 某一项夹到底档、真的改掉那个人的趋势；两种都会让断言测到注入而不是测到口径。
CLEAN_CFG = SeedConfig(
    students=60, weeks=16, seed=20250828,
    dirty={"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0},
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
    sem = session.scalar(select(M.Semester)).id
    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert run.status == "success"
    derived, strat, cleaning, fitness, bodycomp, survey, snapshot = _counts(session)
    assert derived == 60 and strat == 60 and cleaning > 0
    assert fitness > 0 and bodycomp > 0 and survey > 0
    assert snapshot > 0

def test_rerun_same_business_date_is_idempotent(session, seed_dir):
    # Review Focus #5
    sem, ad = session.scalar(select(M.Semester)).id, MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad); first = _counts(session)
    run_daily(session, sem, D, ad); second = _counts(session)
    assert first == second
    assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 1

def test_labels_are_reproducible_across_reruns(session, seed_dir):
    sem, ad = session.scalar(select(M.Semester)).id, MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    a = {(r.student_id, r.label) for r in session.scalars(select(M.StratificationResult))}
    run_daily(session, sem, D, ad)
    b = {(r.student_id, r.label) for r in session.scalars(select(M.StratificationResult))}
    assert a == b

def test_hit_rules_are_persisted(session, seed_dir):
    sem = session.scalar(select(M.Semester)).id
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    rows = list(session.scalars(select(M.StratificationResult)))
    assert all(r.hit_rules for r in rows if r.label != "insufficient_data")

def test_percentile_snapshot_materialized_not_recomputed(session, seed_dir):
    sem, ad = session.scalar(select(M.Semester)).id, MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    n1 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    run_daily(session, sem, "2025-09-16", ad)   # 无新体测数据
    n2 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    assert n1 == n2 and n1 > 0

def test_failure_rolls_back_whole_batch(session, seed_dir, monkeypatch):
    sem = session.scalar(select(M.Semester)).id
    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr("app.pipeline.daily.stratify", boom)
    with pytest.raises(RuntimeError):
        run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    session.rollback()
    assert _counts(session) == (0, 0, 0, 0, 0, 0, 0)   # 派生三表 + 源三表 + 快照，全部回滚

def test_rerun_same_day_does_not_wipe_percentile_snapshot(session, seed_dir):
    # Ruling 32：堵住「先删当日快照、再判定无新数据而跳过」这条能溜过的路径
    sem, ad = session.scalar(select(M.Semester)).id, MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, ad)
    n1 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    run_daily(session, sem, D, ad)          # 同一业务日重跑
    n2 = session.scalar(select(func.count()).select_from(M.PercentileSnapshot))
    assert n1 > 0 and n2 == n1

def test_insufficient_data_students_are_not_stratified(session, seed_dir):
    sem = session.scalar(select(M.Semester)).id
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    labels = {r.label for r in session.scalars(select(M.StratificationResult))}
    assert labels <= {"red", "yellow", "green", "insufficient_data"}

def test_organization_data_never_flows_through_adapter(session, seed_dir):
    # seed_database 已写入组织结构；管道不得重复插入学生
    sem = session.scalar(select(M.Semester)).id
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
    sem = s.scalar(select(M.Semester)).id
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
