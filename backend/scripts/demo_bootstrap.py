"""``scripts/demo.ps1`` 的**数据准备**那一半（Plan 03 Task 9）。

一条命令把演示库灌好：``init_db`` → ``seed_database``（组织结构）→ ``write_csv``
（一学期的体测/体成分/问卷 CSV）→ ``build_demo_feedback``（反馈三源）→ ``run_daily``
（九个阶段跑一遍：分层 → 处方 → 预警 → 班级周报）。

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
一次 :func:`app.pipeline.daily.run_daily` 就够了（九个阶段全走，含预警与周报），
60 人实测约 1 秒，而回放 16 周 ×5 个业务日是分钟级。⚠️ 代价（硬规矩 #39）：
演示库里 ``stratification_result`` / ``derived_metrics`` 只有**一天**的行，
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
import pathlib
import sys

# ⚠️ 本文件在 ``backend/scripts/`` 下，而 ``python scripts/demo_bootstrap.py`` 会把
#    ``backend/scripts`` 放进 sys.path[0]、**不是** ``backend``，故显式补一条。
BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, func, select  # noqa: E402
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
from app.pipeline.daily import run_daily  # noqa: E402
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

#: 演示库用的学期名。⚠️ ``seed_database`` 写**两条** ``Semester``
#: （``2024-2025-1`` 与 ``2025-2026-1``），故一律按**名字**取、不用
#: ``scalar(select(Semester))``（不带 ``order_by`` 的 ``scalar`` 实测取到先插入的上学年）。
DEMO_SEMESTER = "2025-2026-1"


def _parse_args(argv: "list[str] | None") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="demo_bootstrap",
        description="把演示库灌好（组织结构 + 体测 CSV + 反馈三源 + 一次每日批处理）",
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
    forbidden_csv = (BACKEND / "data" / "seed").resolve()
    if args.csv_dir.resolve() == forbidden_csv:
        raise SystemExit(
            f"--csv-dir 不得是 {forbidden_csv}（本仓禁区，恒为 0 文件）；"
            f"请用一个临时目录或 backend/ 之外的路径"
        )
    if args.db_url.endswith("pe.db"):
        raise SystemExit(
            f"--db-url 指向 {args.db_url}，而 backend/pe.db 是本仓禁区（不得存在）；"
            f"演示库请走 app.main.DEMO_DB_URL（backend/pe_demo.db）"
        )

    cfg = SeedConfig(students=args.students, weeks=16, seed=args.seed)
    args.csv_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] write_csv(build_dataset({args.students} 人 / 16 周 / seed={args.seed})) "
          f"-> {args.csv_dir}")
    write_csv(build_dataset(cfg), args.csv_dir)

    print(f"[2/5] init_db + seed_database -> {args.db_url}")
    engine = create_engine(args.db_url)
    init_db(engine)
    with Session(engine) as session:
        seed_database(session, cfg)
        session.commit()

    print(f"[3/5] build_demo_feedback(as_of={args.as_of.isoformat()}) —— 反馈三源")
    with Session(engine) as session:
        demo = build_demo_feedback(session, cfg=cfg, as_of=args.as_of)
        session.commit()
    print(f"       batch_id={demo.batch_id} class_session={demo.class_sessions} "
          f"rpe_record={demo.rpe_records} training_log={demo.training_logs} "
          f"mini_test={demo.mini_tests}")

    print(f"[4/5] run_daily({args.as_of.isoformat()}) —— 九个阶段")
    with Session(engine) as session:
        semester_id = session.scalar(
            select(Semester.id).where(Semester.name == DEMO_SEMESTER)
        )
        if semester_id is None:
            raise SystemExit(f"seed_database 没有写出学期 {DEMO_SEMESTER!r}")
        run = run_daily(
            session, semester_id, args.as_of.isoformat(),
            MockLePaoAdapter(args.csv_dir),
        )
        session.commit()
        session.refresh(run)
    print(f"       status={run.status} 抽取 体测/体成分/问卷 = "
          f"{run.extracted_fitness}/{run.extracted_body_comp}/{run.extracted_survey} "
          f"剔除 {run.dropped_count} 修正 {run.corrected_count}")
    print(f"       分层 红/黄/绿/数据不足 = {run.red_count}/{run.yellow_count}/"
          f"{run.green_count}/{run.insufficient_count}  肌肉量缺线组 {run.muscle_line_gaps}")
    print(f"       处方 {run.prescription_count} 张  预警 {run.alert_count} 条")
    if run.status != "success":
        print(f"       ⚠️ error_summary: {run.error_summary}")

    print("[5/5] 复核（全部从库里数出来，不是自报）")
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
    for name, value in rows:
        print(f"       {name:22s} {value}")
    print(f"       预警按规则            {by_rule}")
    print(f"       处方 status=needs_review {needs_review}"
          f"（⚠️ 它只由「安全规则命中却找不到等价动作」置位；上面那批"
          f"「需要人工复核：addon … 的训练量未指定」的 warning 日志**不**改这一列，"
          f"它们说的是「教师需要用 VOLUME_SCALE 给附加模块定一个量」，"
          f"不是「这张处方不能执行」。两者的差别已登记为待清扫）")
    print(f"       站内消息              {rows[11][1]}"
          f"（⚠️ 两条 RED_* 规则**刻意不自动推送**：spec §8.2 逐字"
          f"「教师端弹『降量建议』→ 教师点击 → 推送『减量 20%』」。"
          f"演示时请在教师端点一次 POST /api/alerts/{{id}}/handle，"
          f"学生端的消息中心才会有内容）")
    # ⚠️ 一条**演示口径的已知不一致**，写在这里免得演示的人以为大屏坏了：
    #    run_daily 注入给 alert_stage / report_stage 的 ``now`` 是**真实时钟**
    #    （app.pipeline.daily 里那个局部变量），而 ``as_of`` 是 DEMO_AS_OF（2025-10-12）。
    #    于是 alert.triggered_at 落在「今天」，而 class_snapshot 夹 alert 的窗口是
    #    [报表周周一, 水位线 + 1 天) = 2025-10-06 .. 2025-10-13 —— 两者不相交，
    #    故 weekly_class_report.alert_summary 在演示库上**恒为 9 个 0**，
    #    教师大屏的「本周预警汇总」那一块是空的。
    #    ⚠️ 生产上 as_of == 今天，故这一档不可达；它只在**重放一个历史业务日**时出现，
    #    而演示恰恰必须重放（数据集是 seed=20250828 的固定一学期，而学期区间是
    #    2025-09-01..2025-12-22，今天的日期落在它之外）。
    #    已登记为关切并移交 Plan 04：修法是让 run_daily 的 ``now`` 也可注入
    #    （与 ``as_of`` 同源），而那是一次签名变更，不在本 Task 的范围里。
    print("       ⚠️ 演示库的 weekly_class_report.alert_summary 恒为 9 个 0"
          "（重放历史日期时 alert.triggered_at = 真实时钟，落在报表周窗口之外；"
          "生产上 as_of == 今天故不可达。详见本文件那一处注释）")
    # ⚠️ 三个「演示有没有东西可看」的判据：少了任何一个，浏览器点起来就是空的
    offenders = [
        why for why, ok in (
            ("一张处方都没有（分层全是 insufficient_data？）", rows[4][1] > 0),
            ("一条预警都没有（--as-of 太早？见 DEMO_AS_OF 的注释：课次要凑满 3 周）",
             rows[10][1] > 0),
            ("一份班级周报都没有（--as-of 不是周日？is_report_day 只在 weekday()==6 为真）",
             rows[12][1] > 0),
        ) if not ok
    ]
    if offenders:
        for why in offenders:
            print(f"       ⚠️ {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
