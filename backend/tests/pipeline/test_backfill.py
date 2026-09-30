"""整学期回放（``run_backfill``）与业务日期展开（``business_dates``）的行为约束。

计划 Step 1 的 5 条（按 Ruling 173/174/177 更正后的版本）+ commit ``4da2234`` 补的
1 条 CLI 守卫，分四组：

* **整学期覆盖**两条 + **三层齐全**一条，共享一个 module 级 ``replay`` fixture：
  500 人 ×112 天的完整回放**只跑一次**（fix round 3 实测该 fixture 的 setup = 20.41 / 20.89 s，
  n=2 次独立跑），三条测试各自断言天数、状态、
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
    `2024-2025-1`**（fix round 3 复跑：`seed_database` 之后 `scalar(select(M.Semester))`
    取到 `id=1 / 2024-2025-1`，两行是 `[(1, '2024-2025-1'), (2, '2025-2026-1')]`；本处此前
    只写「控制者实测」，按硬规矩 #6 扩写——要基于它下结论就得自己复现那一次测量）。
    `Semester.name` 是 CLI 与幂等键的查找键（`models.py:118`，行号绑 commit `b6ebaa3`），
    故一律按名字取——测试要跑的就是 CLI 会跑的那条路径。**守卫**：上面那条「按名字取」
    由本文件 `test_backfill_covers_every_business_date` 的按名回查断言钉住；
    「不带 order_by 会取到先插入的上学年」这一句**不被守卫**（它是取名字这个决定的理由）。"""
    return session.scalar(
        select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME)
    )


@pytest.fixture(scope="module")
def seed_dir(tmp_path_factory) -> pathlib.Path:
    d = tmp_path_factory.mktemp("lepao")
    # 实测 build_dataset 0.334–0.350 s + write_csv ~0.02 s（fix round 3 n=3；单次点值会漂，
    # 故写区间。**不被守卫**——没有测试断言这个耗时）
    write_csv(build_dataset(CFG), d)
    return d


@pytest.fixture(scope="module")
def replay(seed_dir):
    """Ruling 177：整学期回放**只跑一次**，三条测试共享。

    原文让 `test_backfill_covers_every_business_date` 与
    `test_backfill_500_students_under_60_seconds` 各跑一次完整 112 天回放
    （各 ~20 s），而它们的输入完全相同。实测（控制者）：`seed_database` 0.37 s、
    112 天回放 19.7 s，故整个文件的目标是 < 30 s 而不是 < 60 s。
    fix round 1 实测：本 fixture 的 setup 19.4–19.6 s；整个文件 6 条 27.02 s（Ruling 187 的
    ``.distinct()`` 之前是 28.71 s，上一轮报的 29.77 s 离 30 s 预算只剩 0.23 s）。

    ⚠️ **上面这些全是单次跑的点值（Ruling 201），fix round 3 在 commit ``b6ebaa3`` 上复测：
    本文件 6 条单跑 = **29.01 / 29.13 s**（n=2），本 fixture 的 setup = **20.41 / 20.89 s**
    （n=2，取自 ``--durations``），``seed_database`` = **0.36–0.38 s**（n=9）。即 27.02 s
    那个数本轮**没有复现**、反而是 29.0–29.1 s，30 s 的软预算只剩 **0.87–0.99 s**。
    这个 30 s **不是断言**（没有任何测试量本文件的墙钟），它是一个目标值；真正被断言的只有
    ``test_backfill_500_students_under_60_seconds`` 里的 ``elapsed < 60``，量的是**回放本身**
    （fix round 3 n=5：17.98–18.92 s，余量 3.2×）。故本段所有耗时**不被守卫**。
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
    """幂等性测试专用：要数行数，必须有自己的干净库。只跑 7 天，但那两遍回放实测
    **6.02–6.14 s**（fix round 3 n=2，取自 ``--durations`` 的 call；Ruling 187 那次是 5.71 s，
    历史区间 5.7–6.1 s 的上界本轮被推到 6.14），加上本 fixture 的 ``seed_database``
    setup **0.54–0.58 s**，**不是计划 Step 0.4 估的 ~1.5 s**（Ruling 187 已把计划的预算改成
    实测值）。**这些耗时不被守卫**：没有测试断言它们。"""
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

    **两种读法都达标**（Ruling 172）：整学期 112 天 **17.98–18.92 s**（3.2–3.3× 余量，
    fix round 3 n=5 次独立干净跑；历史点值 17.6 / 18.1 / 19.7 s 都是 ``n=1``），
    单个采集日 500 人 **2.03–2.16 s**（28–29× 余量，n=5；原印 1.95 s）。本测试钉严格的那一种
    ——**被断言的只有 ``elapsed < 60`` 这一条**，上面这些区间不被守卫。
    **不要为它做任何优化重构**：只有 **3 天**抽到新数据（本学年 week1 / week8 / week16
    三个采集日），其余 **109 天** p50 = **0.125–0.134 s**（n=5；原印 0.123 s），Task 10 的
    「快照按需物化」已经是达标的原因——实测 ``percentile_snapshot`` 全学期只有 96 行
    = 3 次物化 × 32（fix round 3：A 6/6、B 3/3 都是 96）。
    ⚠️ Ruling 172/178 写的「4 天 / 128 行」**不是干净跑法的值**，而 128 行的成因也
    **不是「乱序」**——同样乱序、但把 ``2025-09-15`` 完整回放一遍的库仍是 96 行。
    承重条件是「预跑那天后来有没有以**同一幂等键** ``(semester_id, business_date)``
    再跑过」（Ruling 192/193；fix round 2 在 commit ``13207b2`` 上重跑、fix round 3 在
    ``b6ebaa3`` 上复跑了完整回放与跳过两行，计数逐字复现）::

          runs  snapshot  computed_on 预跑 ``2025-09-15`` 之后
        ----------------------------- ------------------------
           112        96            3 完整回放（含 09-15，同 sem、同幂等键）→ 多余的物化被清掉
           112       128            4 回放时跳过 09-15 → 预跑那次物化留在库里

    写成表而不写成散文是有意的：散文容易被归纳成一个更宽的错条件（Ruling 192 那次
    就是把「预跑 + 跳过」归纳成「乱序」），表格把条件与结果并排钉住。
    完整四场景对照表、机制的代码引用（``daily.py:249-254`` / ``extract.py:89`` /
    ``percentile_stage.py:342``）与实测字节数（MB 与 MiB 两种口径）见
    ``app/pipeline/backfill.py`` 模块 docstring 第 3 条。
    """
    _s, _sem, runs, elapsed = replay
    assert len(runs) == 112 and elapsed < 60, elapsed


def test_business_dates_is_closed_and_matches_semester_length(session):
    """Ruling 174：`end_date` 是**排他**的，CLI 缺省必须减一天。

    `semester_end_date(current, 16)` = `2025-09-01 + 16 周` = **2025-12-22**（fix round 3
    复跑确认；本处此前只写「控制者实测」，而这个数**本测试下面第 3 行就自己断言了**
    ——`assert sem.end_date == dt.date(2025, 12, 22)`，故它由本条守卫，不是无主的散文），
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
    seed 要 0.36–0.38 s、一次真回放要 17.98–18.92 s（n=5；本文件 6 条单跑 fix round 3 实测
    29.01 / 29.13 s，那个 **30 s 预算只剩 0.87–0.99 s**——它是目标值、不是断言）。
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
    # Ruling 187：**数据规模一点没削**（仍是 500 人 ×112 天 ×56000 行），改的只是取那
    # 3 个不同字符串的方式——原来把 56000 行全部物化成 ORM 实例只为做一个集合，现在把
    # DISTINCT 下推给 sqlite。Ruling 187 当时实测这一条 call 1.96 s → 0.06 s、整个文件
    # 28.71 s → 27.02 s（都是单次跑的点值）。fix round 3 复测整个文件是 **29.01 / 29.13 s**
    # （n=2），27.02 那个数没有复现；这条 call 现在**根本不在 ``--durations`` 的前 12 名里**
    # （即 < 0.45 s），下推的收益仍然成立。**不被守卫**：没有测试断言耗时。
    labels = set(s.scalars(select(M.StratificationResult.label).distinct()))
    assert {"red", "yellow", "green"} <= labels
