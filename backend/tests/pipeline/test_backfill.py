"""整学期回放（``run_backfill``）与业务日期展开（``business_dates``）的行为约束。

计划 Step 1 的 5 条（按 Ruling 173/174/177 更正后的版本）+ 本轮补的 1 条 CLI 守卫，分四组：

* **整学期覆盖**两条 + **三层齐全**一条，共享一个 module 级 ``replay`` fixture：
  500 人 ×112 天的完整回放**只跑一次**（实测 ~20 s），三条测试各自断言天数、状态、
  归属学期与标签集合；
* **性能**一条（``test_backfill_500_students_under_60_seconds``）：spec §1.3 的成功标准
  「500 人批量管道回放 < 60 秒」，钉的是两种读法里**严格的那一种**（整学期回放）；
* **口径**两条：``end_date`` 排他故闭区间上界必须减一天（Ruling 174）、以及重放幂等；
* **CLI 缺省**一条（``test_cli_defaults_end_to_one_day_before_the_exclusive_end_date``）：
  「减一天」这个动作住在 ``main()`` 里，上面那条口径测试碰不到它（它自己在测试代码里减），
  故直接调 ``main()`` 量 ``run_backfill`` 实际收到的 ``(semester_id, start, end)``——
  同时是 Ruling 173「按名字查、不取第一条」在执行侧的唯一守卫。

数据一律来自 ``tmp_path_factory`` / ``tmp_path`` 里的独立 sqlite 文件与临时 CSV 目录：
不碰 ``backend/pe.db``，也不往 ``backend/data/seed/`` 写任何东西（Ruling 68 / 179）。

⚠️ ``run_daily`` 返回的实例在会话关闭后 **detached**（Task 10 关切 10），故 ``replay``
的一切字段读取都必须在 fixture 的 ``with Session(...)`` 块内完成——三条测试因此都只经由
fixture 拿到 ``(session, ...)``，不自己开第二个会话。
"""
import datetime as dt
import pathlib, time, pytest
from sqlalchemy import create_engine, select, func
from app.db.session import init_db, Session
from app.db import models as M
from app.adapters.mock_lepao import MockLePaoAdapter
from app.seed.generate import seed_database, build_dataset, write_csv
from app.seed.config import SeedConfig
from app.pipeline.backfill import run_backfill, business_dates

CFG = SeedConfig(students=500, weeks=16, seed=20250828)
SEMESTER_NAME = "2025-2026-1"          # Ruling 173：按名字取，不取「第一条」
START, END = "2025-09-01", "2025-12-21"  # 闭区间 112 天 = 16 周（Ruling 174）


def semester_id(session) -> int:
    """Ruling 173：`seed_database` 写**两条** Semester（上学年 + 本学年），
    `scalar(select(M.Semester))` 不带 order_by 时取到的是**先插入的上学年
    `2024-2025-1`**（控制者实测）。`Semester.name` 是 CLI 与幂等键的查找键
    （`models.py:118`），故一律按名字取——测试要跑的就是 CLI 会跑的那条路径。"""
    return session.scalar(
        select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME)
    )


@pytest.fixture(scope="module")
def seed_dir(tmp_path_factory) -> pathlib.Path:
    d = tmp_path_factory.mktemp("lepao")
    write_csv(build_dataset(CFG), d)     # 实测 0.34 + 0.02 s
    return d


@pytest.fixture(scope="module")
def replay(seed_dir):
    """Ruling 177：整学期回放**只跑一次**，三条测试共享。

    原文让 `test_backfill_covers_every_business_date` 与
    `test_backfill_500_students_under_60_seconds` 各跑一次完整 112 天回放
    （各 ~20 s），而它们的输入完全相同。实测（控制者）：`seed_database` 0.37 s、
    112 天回放 19.7 s，故整个文件的目标是 < 30 s 而不是 < 60 s。
    本轮实测：本 fixture 的 setup 19.50 s，整个文件 6 条 29.15 s（离 30 s 预算只剩 0.85 s）。
    """
    eng = create_engine(f"sqlite:///{seed_dir.parent/'replay.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, CFG)
        sem = semester_id(s)
        t0 = time.perf_counter()
        runs = run_backfill(s, sem, START, END, MockLePaoAdapter(seed_dir))
        elapsed = time.perf_counter() - t0
        yield s, sem, runs, elapsed
        # ⚠️ run_daily 返回的实例在会话关闭后 detached（Task 10 关切 10），
        #    故所有字段读取都必须在这个 with 块内完成。


@pytest.fixture
def session(tmp_path):
    """幂等性测试专用：要数行数，必须有自己的干净库。只跑 7 天（~1.5 s）。"""
    eng = create_engine(f"sqlite:///{tmp_path/'b.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, CFG)
        yield s


def test_backfill_covers_every_business_date(replay):
    s, sem, runs, _elapsed = replay
    assert len(runs) == 112                      # 16 周 × 7 天，闭区间
    assert all(r.status == "success" for r in runs)
    # Ruling 173 的正向断言：运行记录归属**本学年**，不是上学年
    assert {r.semester_id for r in runs} == {sem}
    # ⚠️ 上一行只证明 run_backfill 把 semester_id **透传**给了每一条运行记录；「归属的是
    # 本学年」要按名字回查一个字面量才算数——否则 `semester_id()` 与 `SEMESTER_NAME`
    # 一起改成 "2024-2025-1" 时，上面那行照样绿（它比的是同一个来源的两侧）。
    assert {s.scalar(select(M.Semester.name).where(M.Semester.id == r.semester_id))
            for r in runs} == {"2025-2026-1"}
    assert s.scalar(select(func.count()).select_from(M.DailySyncRun)) == 112


def test_backfill_500_students_under_60_seconds(replay):
    """spec §1.3 成功标准「500 人批量管道回放 < 60 秒」。

    **两种读法都达标**（Ruling 172）：整学期 112 天 **17.6–19.7 s**（3× 余量），
    单个采集日 500 人 **1.95 s**（30× 余量）。本测试钉严格的那一种。
    **不要为它做任何优化重构**：只有 **3 天**抽到新数据（本学年 week1 / week8 / week16
    三个采集日），其余 **109 天** p50 = 0.123 s，Task 10 的「快照按需物化」已经是达标的
    原因——实测 ``percentile_snapshot`` 全学期只有 96 行 = 3 次物化 × 32。
    （Ruling 172/178 写的「4 天 / 128 行」含一次挂在**上学年** semester_id 下的
    ``2025-09-15`` 首跑，即 Ruling 173 那个缺陷；干净的 Step 6 跑法是 3 天 / 96 行，
    推导与实证见 ``app/pipeline/backfill.py`` 的模块 docstring 第 3 条。）
    """
    _s, _sem, runs, elapsed = replay
    assert len(runs) == 112 and elapsed < 60, elapsed


def test_business_dates_is_closed_and_matches_semester_length(session):
    """Ruling 174：`end_date` 是**排他**的，CLI 缺省必须减一天。

    `semester_end_date(current, 16)` = `2025-09-01 + 16 周` = **2025-12-22**（控制者实测），
    而 16 周 × 7 天 = 112 天对应的是闭区间 `2025-09-01..2025-12-21`。
    若 CLI 直接把 `end_date` 当闭区间上界，就会多跑一天（113）。
    """
    sem = session.scalar(select(M.Semester).where(M.Semester.name == SEMESTER_NAME))
    assert sem.end_date == dt.date(2025, 12, 22)           # = start + weeks*7，排他
    assert len(business_dates(START, "2025-12-21")) == CFG.weeks * 7 == 112
    assert len(business_dates(START, (sem.end_date - dt.timedelta(days=1)).isoformat())) == 112


def test_cli_defaults_end_to_one_day_before_the_exclusive_end_date(tmp_path, monkeypatch):
    """Ruling 174 的**执行侧**守卫：CLI 缺省的 ``--end`` 必须比 ``Semester.end_date`` 少一天。

    上面那条 ``test_business_dates_is_closed_and_matches_semester_length`` 钉的是
    ``business_dates`` 的闭区间语义与 ``end_date`` 的排他性，而**「减一天」这个动作本身发生在
    :func:`app.pipeline.backfill.main` 里**，那条测试碰不到它（变异实证：把 ``main`` 里的
    ``- dt.timedelta(days=1)`` 删掉，那条测试**仍然全绿**——它自己在测试代码里减的那一天）。
    故本条直接调 ``main()``，把 ``run_backfill`` 换成探针，量它实际收到的 ``(start, end)``。

    库里只插两行 ``Semester``（日期一律取自 ``app.seed.config`` 这个既有所有者），不跑
    ``seed_database``：本条要守的是**日期换算与按名字查学期**，与组织结构无关，而一次完整
    seed 要 0.4 s、一次真回放要 ~18 s（本文件的 30 s 预算已经只剩 1 s）。
    """
    from app.pipeline import backfill
    from app.seed.config import SEMESTERS, semester_end_date

    db = tmp_path / "cli.db"
    url = f"sqlite:///{db}"
    eng = create_engine(url)
    init_db(eng)
    with Session(eng) as s:
        for plan in SEMESTERS:          # 上学年先插，与 seed_database 的顺序一致
            s.add(M.Semester(
                name=plan.name, start_date=plan.start_date,
                end_date=semester_end_date(plan, CFG.weeks),
                weeks=CFG.weeks, is_current=plan.is_current,
            ))
        s.commit()

    seen: dict = {}

    def probe(_session, sem_id, start, end, _adapter):
        seen.update(semester_id=sem_id, start=start, end=end)
        return []

    monkeypatch.setattr(backfill, "run_backfill", probe)
    assert backfill.main(["--semester", SEMESTER_NAME, "--db", url]) == 0

    assert seen["start"] == "2025-09-01"
    assert seen["end"] == "2025-12-21"        # = end_date(2025-12-22) 减一天
    assert len(business_dates(seen["start"], seen["end"])) == CFG.weeks * 7 == 112
    # Ruling 173 的执行侧：按名字查到的是本学年，**不是**不带 order_by 的第一条（上学年）
    with Session(eng) as s:
        first = s.scalar(select(M.Semester.id))
        want = s.scalar(select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME))
    assert first != want
    assert seen["semester_id"] == want


def test_backfill_is_idempotent(session, seed_dir):
    sem, ad = semester_id(session), MockLePaoAdapter(seed_dir)
    run_backfill(session, sem, "2025-09-01", "2025-09-07", ad)
    n1 = session.scalar(select(func.count()).select_from(M.StratificationResult))
    run_backfill(session, sem, "2025-09-01", "2025-09-07", ad)
    assert session.scalar(select(func.count()).select_from(M.StratificationResult)) == n1
    assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 7


def test_backfill_produces_all_three_layers(replay):
    s, _sem, _runs, _elapsed = replay
    labels = {r.label for r in s.scalars(select(M.StratificationResult))}
    assert {"red", "yellow", "green"} <= labels
