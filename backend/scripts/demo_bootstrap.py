"""``scripts/demo.ps1`` 的**数据准备**那一半（Plan 03 Task 9）。

一条命令把演示库灌好：``init_db`` → ``seed_database``（组织结构）→ ``run_daily``
（**处方生成日**那一次，见下面第四节）→ ``write_csv``（一学期的体测/体成分/问卷 CSV）
→ ``build_demo_feedback``（反馈三源）→ ``run_daily``（**演示日**那一次：九个阶段全走，
含预警与班级周报）。

--------------------------------------------------------------------------
⚠️⚠️ 为什么它是一个脚本、而不是三条 ``python -m …``
--------------------------------------------------------------------------

本仓有三个 CLI 入口——``app.seed.generate`` / ``app.pipeline.backfill`` /
``app.pipeline.daily``——而它们的 ``main()`` 各自把缺省值写死在**禁区**上：
CSV 目录是 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``，本仓恒为 0 文件、
一个字节都不许动），库是 :data:`app.config.DEFAULT_DB_URL`（``backend/pe.db``，
**不得存在**）。故 ``demo.ps1`` 里**一条 ``python -m …`` 都没有**：本脚本一律
**import 函数、显式传路径**，两个禁区因此结构上碰不到。

⚠️ 于是它也**刻意不调** :func:`app.pipeline.backfill.run_backfill`：回放的语义是
「把一学期的每个业务日都跑一遍」，而演示要的是「今天有一个能点起来的库」——
**两次** :func:`app.pipeline.daily.run_daily` 就够了（理由见下面第四节），
60 人实测每次约 1 秒，而回放 16 周 ×5 个业务日是分钟级。⚠️ 代价（硬规矩 #39）：
演示库里 ``stratification_result`` / ``derived_metrics`` 只有**两天**的行
（:data:`DEMO_RX_AS_OF` 与 :data:`DEMO_AS_OF`，⚠️ 而这两天落在**同一个学期周**里），
故「周环比流动」（:func:`app.domain.report.layer_flow`）在演示库上恒为
``has_previous = False``（上一周一次批处理都没跑）——教师大屏的流动那一块会是空的。
要它非空就得回放至少两个周日，那是 ``run_backfill`` 的活，留给需要它的人手工跑。

--------------------------------------------------------------------------
⚠️ 业务日期取 :data:`DEMO_AS_OF`（一个**周日**）
--------------------------------------------------------------------------

:func:`app.pipeline.report_stage.is_report_day` 只在 ``weekday() == 6`` 为真，
而 :func:`app.pipeline.daily.run_daily` 是按它决定「跑不跑周报阶段」的。
取一个周一的话 ``weekly_class_report`` 一行都不会有，教师大屏的
``GET /api/dashboard/weekly-class-report/{id}`` 就永远 404——演示少一整块。
⚠️ 而它也**不能太早**：``build_demo_feedback`` 往前造 4 个教学周的课次，
而它对「早于开学日」的周**跳过**，于是太早的 ``as_of`` 会让每个学生只剩 2 条快评、
``RED_RPE_SUSTAINED``（要连续 3 次）永远不触发。两个下界的实测与取值理由逐字写在
:data:`DEMO_AS_OF` 的注释里（本脚本用 ``2025-10-12`` = 学期第 6 周的周日）。

--------------------------------------------------------------------------
⚠️⚠️ 为什么跑**两次** ``run_daily``（Plan 03 全分支终审的 I2）
--------------------------------------------------------------------------

只跑一次（``DEMO_AS_OF`` 那一天）的话，演示库上**三层完成率全是 ``rate: 0.0``**、
``notification`` 表 **0 行**、5 条规则只出现 2 条——即「库里有 628 条
``completed=True`` 的打卡，而周报说三层都是 0%」，且 ``measured == students``、
``rate`` 是 ``0.0`` 而不是 ``null``，读起来像「测过了、就是 0%」，
**这违反本项目最响的那条纪律（「不知道」不得讲成「0」）**。

机制是三个各自合理的决定撞在一起（确定性的、与 ``--as-of`` 无关）：

1. ``DEMO_AS_OF`` **必须**是周日（否则一行周报都没有，见上一节）；
2. ``run_daily`` 让 ``prescription.generated_on = as_of``，于是微周期第 1 周的第 1 个
   训练日**就是那个周日**，而报表窗口里 ``<= as_of`` 的训练日**只有它一天**；
3. :mod:`app.demo_data` 的休息日规则是 ``log_date.weekday() >= 5``，周日一律是休息日
   → :func:`app.pipeline.alert_stage._counted_checkin_days` 的四个条件把它剔掉
   → 分子恒 0。

连带：``completion_rate`` 恒 0 → ``GREEN_MASTERY``（要 ``>= 1.0``）永不触发 →
电子勋章流程不可演示；``notification`` 表 0 行 → 学生端消息中心是空的、
``POST /api/notifications/{id}/read`` 无从演示；``YELLOW_CHECKIN_GAP`` 也因
「窗口里只有 1 个已过的训练日」凑不满 ``gap_days = 2``。

**处置取终审给的 (b) 案：让处方生成日早于 ``as_of``**——先在
:data:`DEMO_RX_AS_OF`（= ``DEMO_AS_OF`` 前 6 天 = 报表周的**周一**）跑一次
``run_daily`` 生成处方，再灌反馈三源，再在 ``DEMO_AS_OF`` 跑第二次。
于是报表窗口里 ``<= as_of`` 的训练日变成 3–4 个（周一到周三/周四，**全是工作日**），
分子不再恒 0。

⚠️ **为什么不取 (a) 案（把 ``app/demo_data.py`` 的休息日规则改成「按处方的训练日反推」）**，
两条实测出来的理由：

* **(a) 结构上离不开 (b) 的那次重排**：``build_demo_feedback`` 今天跑在 ``run_daily``
  **之前**，那时库里**一张处方都没有**，「按处方的训练日反推」无从反推。
  故 (a) = (b) 的重排 + 再动一次 ``demo_data`` 的口径，成本严格更高。
* **重排之后 (a) 已经没有收益**：实测 18 套模板的 ``AssembledSession.day`` 恒为
  ``1..N`` 连续（``training_days_of`` 的 docstring 逐字写了这个口径），故
  ``generated_on`` 落在周一时训练日就是周一到周三/周四，**一个周末都不含**——
  「按周末判休息日」与「按处方训练日反推」在这一格上给出同一个答案。
  而 (a) 要付的代价是 ``app/demo_data.py`` 那 4 条测试的口径全变
  （含一条幂等测试「跑三次逐字不变」），换来的是一份重复的判据。

⚠️ ``DEMO_RX_AS_OF`` 因此是**受约束的**，两个约束都写在它的注释里
（改 ``DEMO_AS_OF`` 的人必须回头看一眼）。
⚠️ 代价（硬规矩 #39）：``demo.ps1`` 多跑一次管道。实测那一次约 1 秒
（60 人 / 三源全空 → 预警与周报阶段都是空转），而 ``demo.ps1`` 的 ``elapsed``
哨兵阈值是 90 s、实测 43.96 / 48.37 s（余量 1.86×），故这一秒吃得下。
⚠️ 第二次 ``run_daily`` 的 ``prescription_count`` 是 **0**：处方是上一批生成的、
这一批一个触发都没命中（分层标签没变、处方也没到期）。**那不是失败**，
下面的复核按库里的**总行数**报，故打印时两个数分开写。

--------------------------------------------------------------------------
⚠️ 它**不建表也不删库**
--------------------------------------------------------------------------

「先删掉旧的 ``pe_demo.db``」是 ``demo.ps1`` 的第一步，**不是本脚本的**：
:func:`app.db.session.init_db` 走 ``Base.metadata.create_all``，对**已存在的表原样跳过**
——故一个旧库不会报错、也不会补上新增的 NOT NULL 列，端点会在离真因很远的地方 500
（Plan 03 Task 2 撞过一次，那次是 ``training_log.submitted_at``）。
把「删文件」留在 shell 里，是因为**只有 shell 知道用户想删哪个文件**；
本脚本收到的是一个 URL，它无权替用户决定「这个文件可以删」。
"""
import argparse
import datetime as dt
import os
import pathlib
import sys

# ⚠️ 本文件在 ``backend/scripts/`` 下，而 ``python scripts/demo_bootstrap.py`` 会把
#    ``backend/scripts`` 放进 sys.path[0]、**不是** ``backend``，故显式补一条。
BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.mock_lepao import MockLePaoAdapter  # noqa: E402
from app.db.models.feedback import (  # noqa: E402
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student  # noqa: E402
from app.db.models.prescription import Prescription, WeeklyAdjustment  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.demo_data import build_demo_feedback  # noqa: E402
from app.pipeline.daily import business_now, run_daily  # noqa: E402
from app.seed.config import SeedConfig  # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402

#: 演示的业务日期（**周日**，理由见模块 docstring 第三节）。
#:
#: ⚠️ **它不能太早**，两个下界各有一条理由，都是实测撞出来的：
#:
#: * ``>= 开学日 + 2 周``（即 ``>= 2025-09-15``，实取 4 周后的那个周日）：
#:   :func:`app.demo_data._class_sessions_and_rpe` 对
#:   ``session_date < semester.start_date`` 的周**跳过**（「学期还没开学，那天不可能有课」），
#:   而 ``RED_RPE_SUSTAINED`` 的判据是「连续 **3** 次课堂快评 RPE ≥ 9」。
#:   取 ``2025-09-14``（开学后第 2 周的周日）实测只剩 2 个教学周 → 每个学生 2 条快评
#:   → streak 恒 ≤ 2 → **一条预警都不触发**，演示库里教师端的预警队列是空的。
#: * ``>= 开学日 + 5 周``：:func:`app.demo_data._mini_tests` 取「最近的偶数周」，
#:   而 ``RED_MINITEST_DROP`` 要 **3** 个数据点（spec §8.2 的补齐口径 #2）。
#:   开学后第 6 周才有 6 / 4 / 2 三个偶数周。
#:
#: ``2025-10-12`` 同时满足两条：它是学期 ``2025-2026-1``（开学日 2025-09-01，周一）
#: 的**第 6 周的周日**（``semester_week_of`` 给 6），往前 4 个教学周的课次
#: （10-12 / 10-05 / 09-28 / 09-21）**全部落在学期区间内**。
DEMO_AS_OF = dt.date(2025, 10, 12)

#: **处方生成日相对演示日的偏移天数**（6 天）：:data:`DEMO_RX_AS_OF` =
#: :data:`DEMO_AS_OF` 前 6 天，也就是它那个报表周的**周一**。
#:
#: 它是 I2 那次「跑两次 ``run_daily``」的第一次的业务日期，存在的理由逐字见
#: 模块 docstring 第四节。⚠️⚠️ **它受两个约束，改 :data:`DEMO_AS_OF` 的人必须回头核**：
#:
#: 1. ``0 <= 偏移 <= 6``——否则
#:    :func:`~app.domain.prescription.weekly.current_week` 在 ``DEMO_AS_OF`` 那天
#:    会算出第 2 周（甚至越界返回 ``None``），而演示数据只覆盖第 1 周的训练日；
#: 2. ``DEMO_RX_AS_OF + {0, 1, 2, 3}`` 全部是**工作日**（周一到周四）——
#:    18 套模板的 ``AssembledSession.day`` 恒为 ``1..N`` 连续，故训练日就是
#:    「生成日往后数 N 天」；而 :mod:`app.demo_data` 按
#:    ``log_date.weekday() >= 5`` 判休息日、:func:`_counted_checkin_days`
#:    把休息日从分子里剔掉。**取 6 而不是 5** 就是为了让 4 天的那一档
#:    （周一到周四）也全是工作日；取 4 会让训练日撞上周六、取 3 撞上周日。
#:
#: ⚠️ ``DEMO_AS_OF`` 是周日，故「前 6 天」恒为周一，两个约束同时满足。
#: ⚠️ 守卫是 :func:`main` 复核段的 ``offenders``（三层完成率全 0 → 当场报警 + 返回 1）。
DEMO_RX_OFFSET_DAYS = 6


def rx_as_of_of(as_of: dt.date) -> dt.date:
    """``as_of`` 对应的**处方生成日** = 它前 :data:`DEMO_RX_OFFSET_DAYS` 天。

    ⚠️ 提成一个函数是为了让「那个偏移」只有**一个**住址：:data:`DEMO_RX_AS_OF`
    与 ``--as-of`` 被改过时的实际取值都走它，否则两处各写一个 ``timedelta`` 迟早漂。
    两个约束逐字见 :data:`DEMO_RX_OFFSET_DAYS` 的注释。
    """
    return as_of - dt.timedelta(days=DEMO_RX_OFFSET_DAYS)


#: ``DEMO_AS_OF`` 那一次演示默认的处方生成日（``--as-of`` 被改过时由
#: :func:`rx_as_of_of` 现场算，故本常量只是缺省值的展示）。
DEMO_RX_AS_OF = rx_as_of_of(DEMO_AS_OF)

#: 演示库用的学期名。⚠️ ``seed_database`` 写**两条** ``Semester``
#: （``2024-2025-1`` 与 ``2025-2026-1``），故一律按**名字**取、不用
#: ``scalar(select(Semester))``（不带 ``order_by`` 的 ``scalar`` 实测取到先插入的上学年）。
DEMO_SEMESTER = "2025-2026-1"


def _parse_args(argv: "list[str] | None") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="demo_bootstrap",
        description="把演示库灌好（组织结构 + 体测 CSV + 反馈三源 + 两次每日批处理）",
    )
    parser.add_argument("--db-url", required=True,
                        help="SQLite 的 URL，例如 sqlite:///C:/…/backend/pe_demo.db")
    parser.add_argument("--csv-dir", required=True, type=pathlib.Path,
                        help="三份乐跑 CSV 的落地目录（**不得**是 backend/data/seed/）")
    parser.add_argument("--students", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20250828)
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=DEMO_AS_OF)
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv)

    # ⚠️ 两个禁区的前置守卫：**响亮失败**而不是写进去再让人去查
    #    （``backend/data/seed/`` 恒为 0 文件、``backend/pe.db`` 不得存在）。
    # ⚠️⚠️ 两道都比 Plan 03 Task 9 那版**宽**（终审的 M2）：
    #    * ``--csv-dir`` 从「等于禁区目录」改成「等于**或落在里面**」——
    #      原口径下 ``--csv-dir backend/data/seed/2025`` 会一路放行，而禁区那条纪律是
    #      「``backend/data/seed/`` 恒为 0 文件」，子目录里的文件同样是破禁区；
    #    * ``--db-url`` 从「串以 ``pe.db`` 结尾」改成「用 :func:`make_url` 剥出数据库
    #      文件路径、``resolve()`` 之后做**大小写无关**比较」——原口径有两个洞：
    #      Windows 上 ``…/PE.DB`` 与 ``…/Pe.Db`` 是同一个文件而 ``endswith`` 认不出来；
    #      反过来 ``…/somepe.db`` 会被它误伤（那一档今天恰好无害，但它说明判据选错了）。
    #      ⚠️ 仍然**保留**「basename 恰好是 ``pe.db`` 就拒」这一支：禁区外的同名文件
    #      本来不该管，但那是一个几乎必然是手误的输入，宁可多拒一次。
    forbidden_csv = (BACKEND / "data" / "seed").resolve()
    csv_dir = args.csv_dir.resolve()
    if csv_dir == forbidden_csv or csv_dir.is_relative_to(forbidden_csv):
        raise SystemExit(
            f"--csv-dir 不得是 {forbidden_csv} 或它下面的子目录（本仓禁区，恒为 0 文件）；"
            f"请用一个临时目录或 backend/ 之外的路径"
        )
    forbidden_db = os.path.normcase(str((BACKEND / "pe.db").resolve()))
    database = make_url(args.db_url).database
    db_basename = "" if database is None else pathlib.Path(database).name
    if db_basename == "pe.db" or (
        database and os.path.normcase(str(pathlib.Path(database).resolve())) == forbidden_db
    ):
        raise SystemExit(
            f"--db-url 指向 {args.db_url}（数据库文件 {database!r}），"
            f"而 backend/pe.db 是本仓禁区（不得存在）；"
            f"演示库请走 app.main.DEMO_DB_URL（backend/pe_demo.db）"
        )

    cfg = SeedConfig(students=args.students, weeks=16, seed=args.seed)
    args.csv_dir.mkdir(parents=True, exist_ok=True)
    # ⚠️ 处方生成日跟着 --as-of 走（唯一所有者是 :func:`rx_as_of_of`，两个约束见
    #    :data:`DEMO_RX_OFFSET_DAYS` 的注释）。
    rx_as_of = rx_as_of_of(args.as_of)

    print(f"[1/6] write_csv(build_dataset({args.students} 人 / 16 周 / seed={args.seed})) "
          f"-> {args.csv_dir}")
    write_csv(build_dataset(cfg), args.csv_dir)

    print(f"[2/6] init_db + seed_database -> {args.db_url}")
    engine = create_engine(args.db_url)
    init_db(engine)
    with Session(engine) as session:
        seed_database(session, cfg)
        session.commit()
        semester_id = session.scalar(
            select(Semester.id).where(Semester.name == DEMO_SEMESTER)
        )
    if semester_id is None:
        raise SystemExit(f"seed_database 没有写出学期 {DEMO_SEMESTER!r}")

    # ⚠️⚠️ 第一次 run_daily 的唯一目的是**把处方的 generated_on 钉在演示日之前**
    #    （I2，理由逐字见模块 docstring 第四节）。它跑在三源全空的库上，故预警与
    #    周报两个阶段都是空转（那一天也不是周日）；⚠️ 而 ``now`` 必须注入成
    #    **那一天**的业务时刻（I1）：不注入的话它会落进真实时钟，而重放路径上
    #    「真实时钟」与任何历史报表周都不相交。
    print(f"[3/6] run_daily({rx_as_of.isoformat()}) —— 处方生成日（I2 的第一次）")
    with Session(engine) as session:
        rx_run = run_daily(
            session, semester_id, rx_as_of.isoformat(),
            MockLePaoAdapter(args.csv_dir), now=business_now(rx_as_of),
        )
        session.commit()
        session.refresh(rx_run)
    print(f"       status={rx_run.status} 处方 {rx_run.prescription_count} 张  "
          f"预警 {rx_run.alert_count} 条（三源还空着，应当是 0）")
    if rx_run.status != "success":
        print(f"       ⚠️ error_summary: {rx_run.error_summary}")

    print(f"[4/6] build_demo_feedback(as_of={args.as_of.isoformat()}) —— 反馈三源")
    with Session(engine) as session:
        demo = build_demo_feedback(session, cfg=cfg, as_of=args.as_of)
        session.commit()
    print(f"       batch_id={demo.batch_id} class_session={demo.class_sessions} "
          f"rpe_record={demo.rpe_records} training_log={demo.training_logs} "
          f"mini_test={demo.mini_tests}")

    print(f"[5/6] run_daily({args.as_of.isoformat()}) —— 九个阶段")
    with Session(engine) as session:
        run = run_daily(
            session, semester_id, args.as_of.isoformat(),
            MockLePaoAdapter(args.csv_dir), now=business_now(args.as_of),
        )
        session.commit()
        session.refresh(run)
    print(f"       status={run.status} 抽取 体测/体成分/问卷 = "
          f"{run.extracted_fitness}/{run.extracted_body_comp}/{run.extracted_survey} "
          f"剔除 {run.dropped_count} 修正 {run.corrected_count}")
    print(f"       分层 红/黄/绿/数据不足 = {run.red_count}/{run.yellow_count}/"
          f"{run.green_count}/{run.insufficient_count}  肌肉量缺线组 {run.muscle_line_gaps}")
    # ⚠️ 本批新生成的处方**是 0**：处方是 [3/6] 那一批生成的，这一批一个触发都没命中
    #    （分层标签没变、处方也没到期）。那不是失败，故与库里的总数分开报（见 [6/6]）。
    print(f"       本批新生成处方 {run.prescription_count} 张（处方生成日是 "
          f"{rx_as_of.isoformat()}，见 [3/6]）  预警 {run.alert_count} 条")
    if run.status != "success":
        print(f"       ⚠️ error_summary: {run.error_summary}")

    print("[6/6] 复核（全部从库里数出来，不是自报）")
    with Session(engine) as session:
        def count(model) -> int:
            return int(session.scalar(select(func.count()).select_from(model)))

        rows = [
            ("semester", count(Semester)), ("student", count(Student)),
            ("course_section", count(CourseSection)), ("enrollment", count(Enrollment)),
            ("prescription", count(Prescription)),
            ("weekly_adjustment", count(WeeklyAdjustment)),
            ("class_session", count(ClassSession)), ("rpe_record", count(RpeRecord)),
            ("training_log", count(TrainingLog)), ("mini_test", count(MiniTest)),
            ("alert", count(Alert)), ("notification", count(Notification)),
            ("weekly_class_report", count(WeeklyClassReport)),
        ]
        by_rule = dict(
            session.execute(
                select(Alert.rule_id, func.count(Alert.id)).group_by(Alert.rule_id)
            ).all()
        )
        needs_review = int(session.scalar(
            select(func.count()).select_from(Prescription).where(
                Prescription.status == "needs_review"
            )
        ))
        generated_on = sorted({
            str(day) for day in session.scalars(
                select(Prescription.generated_on)
            ).all()
        })
        # ⚠️ 两个 JSON 列**逐行读回来**（不是自报）：它们是 I1 / I2 两个修复的
        #    验收面，也是下面 ``offenders`` 那三格的输入。
        report_rows = session.execute(
            select(
                WeeklyClassReport.course_section_id,
                WeeklyClassReport.checkin_rate_by_layer,
                WeeklyClassReport.alert_summary,
                WeeklyClassReport.suggestion,
            ).order_by(WeeklyClassReport.course_section_id)
        ).all()
    for name, value in rows:
        print(f"       {name:22s} {value}")
    print(f"       预警按规则            {by_rule}")
    print(f"       处方 generated_on     {generated_on}"
          f"（⚠️ 应当**早于** --as-of={args.as_of.isoformat()}，否则报表窗口里"
          f"「<= as_of 的训练日」只有 as_of 一天、而那一天是周日=休息日 → 三层完成率恒 0，"
          f"理由见模块 docstring 第四节）")
    for section_id, rates, summary, suggestion in report_rows:
        three = {
            layer: (rates.get(layer) or {}).get("rate")
            for layer in ("red", "yellow", "green")
        }
        total = sum(sum(level.values()) for level in summary.values())
        print(f"       周报 班 {section_id}: 三层完成率 {three}  "
              f"预警汇总合计 {total}  建议「{suggestion}」")
    print(f"       处方 status=needs_review {needs_review}"
          f"（⚠️ 它只由「安全规则命中却找不到等价动作」置位；上面那批"
          f"「需要人工复核：addon … 的训练量未指定」的 warning 日志**不**改这一列，"
          f"它们说的是「教师需要用 VOLUME_SCALE 给附加模块定一个量」，"
          f"不是「这张处方不能执行」。两者的差别已登记为待清扫）")
    print(f"       站内消息              {rows[11][1]}"
          f"（⚠️ 两条 RED_* 规则**刻意不自动推送**：spec §8.2 逐字"
          f"「教师端弹『降量建议』→ 教师点击 → 推送『减量 20%』」。"
          f"演示时请在教师端点一次 POST /api/alerts/{{id}}/handle，"
          f"学生端的消息中心会再多一条；而 GREEN_MASTERY 的电子勋章与"
          f" YELLOW_CHECKIN_GAP 的补练提醒是**自动**推的，本数字里已经含它们）")
    # ⚠️ 六个「演示有没有东西可看」的判据：少了任何一个，浏览器点起来就是空的。
    #    后三个是 Plan 03 全分支终审之后加的（此前只有前三个，而它只检查「行数 > 0」，
    #    于是 11 条预警就让它通过了、一条警告都不打）。
    offenders = [
        why for why, ok in (
            ("一张处方都没有（分层全是 insufficient_data？）", rows[4][1] > 0),
            ("一条预警都没有（--as-of 太早？见 DEMO_AS_OF 的注释：课次要凑满 3 周）",
             rows[10][1] > 0),
            ("一份班级周报都没有（--as-of 不是周日？is_report_day 只在 weekday()==6 为真）",
             rows[12][1] > 0),
            # --- I2：三层完成率全 0 ------------------------------------------
            # ⚠️ 这一格挡的不是「算错了」而是「演示没东西可看」：rate 是 0.0 而
            #    measured == students 时，教师大屏读起来像「测过了、就是 0%」，
            #    而那违反本项目最响的那条纪律（「不知道」不得讲成「0」）。
            #    成因与修法逐字见模块 docstring 第四节（处方生成日必须早于 --as-of）。
            ("三层完成率全是 0/null（处方生成日没有早于 --as-of？见模块 docstring "
             "第四节与 DEMO_RX_OFFSET_DAYS 的两个约束）",
             bool(report_rows) and any(
                 (rates.get(layer) or {}).get("rate")
                 for _sid, rates, _sum, _sug in report_rows
                 for layer in ("red", "yellow", "green")
             )),
            # --- I2：notification 0 行 ---------------------------------------
            # 学生端消息中心空的 → POST /api/notifications/{id}/read 无从演示。
            ("notification 表 0 行（GREEN_MASTERY 与 YELLOW_* 都没触发？"
             "学生端消息中心会是空的）", rows[11][1] > 0),
            # --- I1：alert_summary 恒为 9 个 0 -------------------------------
            # ⚠️ 成因不是「演示口径、生产不可达」（本处此前逐字这么写，而那句对
            #    app.pipeline.backfill **不成立**：回放的语义逐字就是「把一学期的
            #    每个业务日都跑一遍」，每一个业务日都是历史日）。真正的原因是
            #    run_daily 的 now 此前不可注入 → alert.triggered_at 落在真实时钟上、
            #    与报表周那个历史窗口恒不相交。现已修（now 可注入 + 本脚本传
            #    business_now(as_of)），故这一格是它的守卫。
            ("weekly_class_report.alert_summary 全是 0（run_daily 的 now 没有注入成 "
             "as_of 派生的时刻？见 app.pipeline.daily.business_now）",
             bool(report_rows) and any(
                 sum(level.values()) > 0
                 for _sid, _rates, summary, _sug in report_rows
                 for level in summary.values()
             )),
        ) if not ok
    ]
    if offenders:
        for why in offenders:
            print(f"       ⚠️ {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
