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
import pathlib, sys, time, pytest
from collections import Counter
from sqlalchemy import create_engine, select, func
from app.db.session import init_db, Session
from app.db import models as M
from app.adapters.mock_lepao import MockLePaoAdapter
from app.seed.generate import seed_database, build_dataset, write_csv
from app.seed.config import SeedConfig
from app.pipeline.backfill import run_backfill, business_dates

CFG = SeedConfig(students=500, weeks=16, seed=20250828)
# 「单日失败」那条专用（Ruling 220②）：要验的是形状不是规模，60 人足够且 < 1 s。
SMALL_CFG = SeedConfig(students=60, weeks=16, seed=20250828)
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

    ⚠️⚠️ **本段这两个区间是 Plan 01 的口径**（「fix round 3」= **Plan 01** 的 fix round 3，
    量的是**接入处方阶段之前**的回放）。Plan 02 Task 7 接入处方阶段之后的实测在**本
    docstring 下面**那一段：``28.86 / 29.05 / 29.59 s``（n=3），最小余量 **2.03×**
    ——即余量从 3.2× 掉到刚过硬规矩 #42 的 2× 线。⚠️ 顺序上先读到的是过期值，故把这句
    时间限定词提到最前面（待清扫第 9 条，Task 9 结案；此前它只在下面那段的 ``⚠️⚠️`` 里）。
    **两种读法都达标**（Ruling 172）：整学期 112 天 **17.98–18.92 s**（3.2–3.3× 余量，
    **Plan 01** fix round 3 n=5 次独立干净跑；历史点值 17.6 / 18.1 / 19.7 s 都是 ``n=1``），
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

    ⚠️ **``elapsed < 60`` 只在**没有 trace 钩子**时才断言**（终审修复轮加的，理由全是实测）。

    spec §1.3 量的是**生产墙钟**，而 ``--cov`` 会装一个全局 trace 钩子，把每一行 Python 都
    记一遍——那时量到的**不是同一个对象**（硬规矩 #36 第二问）。本轮亲跑的
    ``replay`` fixture setup 墙钟（= ``build_dataset`` + ``write_csv`` + ``seed_database``
    + 112 天回放；``--durations=1`` 口径，同一台机器、交错取样）::

        配置                                     n     setup 墙钟区间      对 60 s 的余量
        ---------------------------------------  ----  -----------------  -------------
        基线 ``728325a``，**带** ``--cov=app.domain``  7   54.68 – 63.04 s   1.10× – 0.95×
        本轮 HEAD，**带** ``--cov=app.domain``         5   56.22 – 70.83 s   1.07× – 0.85×
        本轮 HEAD **摘掉** A4 的两条唯一约束，带 cov    2   59.53 – 59.60 s   1.01×
        本轮 HEAD，**不带** ``--cov``                  3   28.40 – 33.95 s   2.1× – 1.8×

    三条结论：① **带 cov 时基线自己就越界**（63.04 s 那个样本 ⇒ ``elapsed`` ≈ 62 s > 60），
    故这不是本轮引入的回归；② 把 A4 的两条 ``UniqueConstraint`` 摘掉**并没有**回到基线水平
    （59.5 s 仍在基线区间上沿），故**不能把带 cov 时的位移归因于唯一约束**；
    ③ 三种配置的组内极差（56.2–70.8 / 54.7–63.0）都**大于**配置之间的差，即带 cov 时
    这条断言的分辨率低于它的噪声。按硬规矩 #42（「余量小于 2× 的时间断言一律是 flaky
    断言」），带 cov 的那一列**本来就不该被断言**；不带 cov 的那一列余量 1.8–2.1×，
    勉强够，故保留。

    ⚠️⚠️ **上面那张表是 Plan 01 的口径**（「本轮 HEAD」指 Plan 01 fix round 3 的 HEAD）：
    「不带 ``--cov`` 28.40–33.95 s」那一行量的是**接入处方阶段之前**的回放。
    **Plan 02 Task 7 接入处方阶段之后本条当场红过一次**，两处优化把它压回基线；
    按硬规矩 #42（余量 < 2× 的时间断言一律是 flaky 断言），fix round 1 把前后值与
    测量条件一并写在这里::

        整学期回放（500 人 ×112 业务日）的 ``elapsed``（= 被断言的那一个量）
        ----------------------------------------------------------------------
        接入处方阶段、**未优化**      52.89 s（另一次亲跑量到 **115.08 s** → 本条当场红）
        两处优化之后（缺省注入）      28.85 s   → 余量 60 / 28.85 = **2.08×**
        两处优化之后（零注入）        28.81 s
        **fix round 1 复测**（n=3）   28.86 / 29.05 / 29.59 s → 最小余量 60 / 29.59 = **2.03×**
        **fix round 1 带 ``--cov``**（n=1） ``elapsed`` = **57.25 s** → 余量 **1.05×**，
                                      被下面那个 ``sys.gettrace()`` 钩子如实 skip
                                      （**钩子今天仍在、仍生效**：skip 出自本文件 ``:182``）

    两处优化都在 ``app/pipeline/prescription_stage.py``（机制逐处写在
    ``_previous_prescriptions`` 与 ``generate_prescriptions`` 的注释里）：

    ① 主查询**同时**按 ``batch_id`` 过滤（那一列 ``index=True``）——只按 ``computed_on``
       单列过滤用不上 ``(student_id, computed_on)`` 那条唯一索引（它**以 ``student_id``
       打头**）→ 全表扫描，而 ``stratification_result`` 到学期末有 **56 000** 行
       （500 × 112）、每行还带一个约 **2 KB** 的 ``input_snapshot``，112 天累计约
       **310 万行**扫描；
    ② 上一张处方的预取用 ``load_only(...)`` 把 4 个大 ``JsonText`` 列**延迟加载**
       ——``training_package`` 是 4 周 ×4 课 ×3 block 的嵌套字典（约 500 个键值对），
       逐人逐日 eager 加载 = 约 **56 000** 次大 JSON 解析，而本阶段**一个字节都不读它**。

    ⚠️ fix round 1 的 **F1-1** 又把 ② 里那次「与 ``stratification_result`` 的连接」整个
    删掉了（触发 2 的标签改从 ``prescription.label_at_generation`` 这一列读，不再回读
    另一张表），故今天 ``load_only`` 留下的是 **7** 个小列。**净效果已含在上面那三行
    28.86 / 29.05 / 29.59 s 里**（它们量的是加列之后的 HEAD）。

    **测量条件**（硬规矩 #42 要求写下）：Windows 10（10.0.26200）/ AMD64 /
    Intel64 Family 6 Model 197 / 16 核，CPython 3.11.1、SQLAlchemy 2.1.3、SQLite 3.39.4、
    pytest 9.1.1、coverage 7.16.2；**本地 SQLite 文件**（不是 ``:memory:``）；
    ``elapsed`` = ``run_backfill`` 那一段的 ``time.perf_counter`` 之差，**不含**
    ``build_dataset`` / ``write_csv`` / ``seed_database``（``--durations`` 口径的
    ``replay`` setup 比它多约 0.4–1.5 s：本轮三次实测 **30.10 / 30.65 / 30.59 s**）；
    n=3 独立干净跑、**不带** ``--cov``、无任何 trace 钩子（探针里 ``assert
    sys.gettrace() is None``）；带 ``--cov=app.domain --cov-branch`` 的那一行是 n=1、
    且**必然**被 skip（1.05× < 2×）。⚠️ 本机墙钟极差本来就大（同一个夹具在优化前
    量到过 52.89 s 与 115.08 s），故 **2.03× 只是刚过硬规矩 #42 的 2× 线**；
    ⚠️ 而它**抓不到「慢但没超 60 s」**——处方阶段若再退化 2×（到约 58 s）本条照样绿。
    上面这些数**一律不被守卫**，被断言的只有 ``elapsed < 60``。

    ``len(runs) == 112`` **无条件断言**——它是口径不是墙钟，与 trace 钩子无关。
    """
    _s, _sem, runs, elapsed = replay
    assert len(runs) == 112
    if sys.gettrace() is not None:
        pytest.skip(
            f"检测到 trace 钩子（coverage / debugger）：本次量到的回放墙钟是 {elapsed:.2f} s，"
            f"而 spec §1.3 的「< 60 秒」指的是**生产墙钟**。带 --cov=app.domain 时同一台机器"
            f"的实测区间是 54.7–70.8 s（基线 728325a 亦然），余量 < 2×，按硬规矩 #42 属"
            f"flaky 断言，故跳过；不带 --cov 时实测 28.4–34.0 s（余量 1.8–2.1×），照常断言"
        )
    assert elapsed < 60, elapsed


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


@pytest.fixture
def small_env(tmp_path):
    """60 人的独立库 + CSV 目录，供「单日失败」那条用。

    **不复用上面的 ``session`` / ``seed_dir``**：那两个是 ``CFG`` = **500 人**，7 天回放实测
    6.02–6.14 s（见 ``session`` 的 docstring），而本条要验的是「中间一天失败」这个**形状**，
    与规模无关。60 人 ×7 天实测 **< 1 s**（Ruling 220 对这四条补测的要求）。
    """
    d = tmp_path / "small"
    write_csv(build_dataset(SMALL_CFG), d)
    eng = create_engine(f"sqlite:///{tmp_path/'small.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, SMALL_CFG)
        yield s, d


def test_a_single_day_failure_is_traced_and_does_not_block_the_rest(small_env, monkeypatch):
    """Ruling 220②：``run_backfill`` 中间某天炸 → 返回长度不变、失败日留痕、后续日照常。

    钉的是 ``backfill.py`` 那条**承重逻辑**——终审 B 亲跑覆盖率：改前 ``203-208`` 六行
    **一行都没被跑过**（``backfill.py`` 整体 76%，Miss ``153, 171, 203-208, 285-293, 305``）。
    它做的事是：吞掉 ``run_daily`` 的重抛、用 ``_traced_failure`` 按幂等键
    ``(semester_id, business_date)`` 把那条 ``status="failed"`` 的运行记录**取回来补进返回列表**、
    然后继续跑下一天；**唯一例外**是连留痕都没写进去时原样重抛真因。

    没有它的后果是二选一，两个都坏：① 让异常穿出去 → 一天炸掉整学期回填，而前面几十天的
    成果留在库里、返回列表却丢了；② 静默跳过 → 返回列表少一项，``Counter(r.status ...)``
    与 ``main()`` 的退出码都看不出那天跑过。

    失败注入点是 ``app.pipeline.daily._stratify_and_persist``（**在它真的写完这一天之后**
    再抛，故本条同时验证 SAVEPOINT 把当天写入撤销干净）。不 ``monkeypatch`` 掉
    ``run_daily`` 本身：那会绕过真的 ``_record_failure``，而本条要验的恰恰是留痕。
    """
    from app.pipeline import daily

    session, seed_dir = small_env
    fail_day = dt.date(2025, 9, 4)
    real = daily._stratify_and_persist

    def flaky(sess, batch_id, as_of):
        labels, gaps = real(sess, batch_id, as_of)     # 先真的写完这一天
        if as_of == fail_day:
            raise RuntimeError(f"boom on {as_of.isoformat()}")
        return labels, gaps

    monkeypatch.setattr(daily, "_stratify_and_persist", flaky)

    runs = run_backfill(session, semester_id(session), "2025-09-01", "2025-09-07",
                        MockLePaoAdapter(seed_dir))

    # ① 返回长度恒等于天数（失败日也在里面），且顺序按业务日期升序
    assert len(runs) == 7
    assert [r.business_date for r in runs] == [dt.date(2025, 9, d) for d in range(1, 8)]
    # ② 只有那一天失败，**后续日照常 success**（失败不阻断）
    assert [r.status for r in runs] == ["success"] * 3 + ["failed"] + ["success"] * 3
    assert dict(Counter(r.status for r in runs)) == {"success": 6, "failed": 1}
    # ③ 失败日留了痕：status + error_summary 都在库里（不是只在返回列表里）
    failed = runs[3]
    assert failed.error_summary is not None and "boom on 2025-09-04" in failed.error_summary
    traced = session.scalar(select(M.DailySyncRun).where(
        M.DailySyncRun.business_date == fail_day))
    assert traced is not None and traced.status == "failed"
    assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 7
    # ④ 失败那天的派生写入被 SAVEPOINT 撤销：7 天里只有 6 天有分层结果，
    #    且失败那天一行都没有（不是「写了半批」）
    per_day = dict(session.execute(
        select(M.StratificationResult.computed_on, func.count())
        .group_by(M.StratificationResult.computed_on)).all())
    assert per_day == {dt.date(2025, 9, d): 60 for d in (1, 2, 3, 5, 6, 7)}
    assert fail_day not in per_day
