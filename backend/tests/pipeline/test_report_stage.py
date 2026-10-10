"""``app/pipeline/report_stage.py`` 的守卫（Plan 03 Task 8）。

**分七支**，每支钉一件不同的事：

* **支 A（周日判据）**：spec §8.5 逐字「每周日批处理生成」。⚠️ ``weekday() == 6`` 是
  周日、``isoweekday() == 6`` 是**周六**，这个 off-by-one 是本 Task 最容易错的一格，
  故用**三个真实的日期字面**钉住（2025-09-13 周六不生成 / 2025-09-14 周日生成 /
  2025-09-15 周一不生成），外加一条把一整周七天逐个过一遍的。
* **支 B（``_replay_cleanup`` 从六张扩到七张）**：按 **AST 口径**数清单的长度与成员
  （硬规矩 #89：数成员用 AST，不用正则数源码），加一条行为面的
  「重放那天周报行真的被按批删掉了」。
* **支 C（spec §8.5 的六个字段）**：五个 ``JsonText`` 列各装什么、
  ``suggestion`` 那一列是自由文本，逐个字段对账。
* **支 D（水位线：读不到未来）**：周中生成第 N 周的周报不得把 N 周剩下的日子算进去；
  一份录进了「未来周次」的小测不得被当成「本次」。
* **支 E（幂等与 ``skipped``）**：同一天重跑不翻倍；名册为空的班**不写行**。
* **支 F（异常分层）**：一个学生的训练包装配不出来 → 他那一格是「判不了」，
  整份周报照生成、整批不回滚。
* **支 G（口径的单一所有者）**：``ALERT_STATUSES`` 与 ``Alert.STATUSES`` /
  ``alert_stage`` 那三个常量对账；``CLASS_RPE_HIGH_RULE`` 与 ``RuleId`` 对账；
  ``_JSON_COLUMNS`` 与 ``WeeklyClassReport`` 的 5 个 ``JsonText`` 列对账。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律**字面**写在测试里
（``"2025-09-14"`` / ``6`` / ``"本周建议整体降量 10%"`` / 那些学生 id 与均值），
**不从被测模块读回来**。支 G 那几条「与另一个所有者对账」的测试，另一侧一律是
**别的模块**（``app.db.models`` / ``app.pipeline.alert_stage`` / ``app.domain.alerts``）。

⚠️ 夹具**刻意不复用** ``tests/pipeline/test_alert_stage.py`` 的那一套
（那里的模块 docstring 逐字写了理由：跨测试文件 import 私有夹具会让两个文件互相钉住），
故本文件自己有一份同形状的 ``_seed`` / ``_rpe`` / ``_log`` / ``_mini``。
"""
import ast
import datetime as dt
import pathlib

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.pipeline.report_stage as stage
from app.db import models as M
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student, Teacher
from app.db.models.prescription import Prescription
from app.db.session import init_db
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, assemble
from app.pipeline.alert_stage import semester_week_of
from app.pipeline.prescription_stage import training_package_payload
from app.pipeline.report_stage import (
    ALERT_STATUSES,
    CLASS_RPE_HIGH_RULE,
    REPORT_WEEKDAY,
    ReportSummary,
    aggregates_of,
    class_snapshot,
    generate_weekly_reports,
    is_report_day,
    labels_at,
    new_cache,
)
from app.refdata_prescription import exercises as exercise_library
from app.refdata_prescription import templates as template_library

D = dt.date
T = dt.datetime

BACKEND = pathlib.Path(__file__).resolve().parents[2]

#: 学期起点。**2025-09-01 是周一**，故「学期第 N 周」= 09-01 + 7×(N−1) 起的那 7 天，
#: 而第 N 周的**周日**是 ``09-07 + 7×(N−1)``（口径照 ``tests/pipeline/test_alert_stage.py``）。
SEMESTER_START = D(2025, 9, 1)
SEMESTER_END = D(2025, 12, 22)
GENERATED_ON = SEMESTER_START
MICROCYCLE_WEEKS = 4
GREEN_TEMPLATE = "GRN-END-NOR-14"   # 绿层模板：每周 2 天（day = [1, 2]）
NOW = T(2025, 9, 14, 22, 30)

#: ⚠️ **三个日期字面是支 A 的全部证据**（``weekday()`` 的 ``Monday == 0``）：
#: 09-13 周六 → ``weekday() == 5``；09-14 周日 → ``6``；09-15 周一 → ``0``。
SATURDAY = D(2025, 9, 13)
SUNDAY = D(2025, 9, 14)
MONDAY = D(2025, 9, 15)

STUDENT_NOS = ("S2025001", "S2025002", "S2025003")
TEACHER_STAFF_NO = "T2025001"


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    return eng


def _profile(student_id: int) -> StudentProfile:
    """个体修正系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。"""
    return StudentProfile(
        student_id=student_id, sex=Sex.MALE, birth=D(2005, 3, 4), age=20,
        endurance_score=70.0, bmi=None, body_fat_pct=None, muscle_mass_kg=None,
        muscle_p10=None, measured_hrmax=None,
    )


def _seed(engine, *, students=STUDENT_NOS, extra_empty_section=False) -> dict:
    """一套最小可用的行：学期 + 教师 + 教学班（含选课）+ 一行批次 + 逐人一张处方。

    ``extra_empty_section=True`` 时再建一个**没有选课**的教学班（支 E 的 ``skipped``）。
    """
    ids: dict = {}
    with Session(engine) as s:
        semester = Semester(name="2025-2026-1", start_date=SEMESTER_START,
                            end_date=SEMESTER_END, weeks=16, is_current=True)
        teacher = Teacher(staff_no=TEACHER_STAFF_NO, name="张老师")
        s.add_all([semester, teacher])
        s.flush()
        ids["semester"], ids["teacher"] = semester.id, teacher.id

        section = CourseSection(semester_id=semester.id, teacher_id=teacher.id,
                               name="体育(1)班", grouping_mode="administrative")
        s.add(section)
        s.flush()
        ids["section"] = section.id

        run = M.DailySyncRun(semester_id=semester.id, business_date=GENERATED_ON,
                             started_at=T(2025, 9, 1, 2, 0), status="success")
        s.add(run)
        s.flush()
        ids["batch"] = run.id

        for index, student_no in enumerate(students, start=1):
            student = Student(student_no=student_no, name=f"学生{index}", sex="male",
                              birth=D(2005, 3, 4), department=None, grade=1)
            s.add(student)
            s.flush()
            ids[student_no] = student.id
            s.add(Enrollment(semester_id=semester.id, student_id=student.id,
                             course_section_id=section.id))
            package = assemble(_profile(student.id), template_library()[GREEN_TEMPLATE],
                               GENERATED_ON, exercises=exercise_library())
            row = Prescription(
                student_id=student.id, generated_on=GENERATED_ON, batch_id=run.id,
                template_ref=GREEN_TEMPLATE,
                # ⚠️ 字面量 4，不读模板（硬规矩 #35）：它是「哪一周算越界」的判据
                microcycle_weeks=MICROCYCLE_WEEKS,
                label_at_generation="green",
                training_package=training_package_payload(package),
                assembly_snapshot=dict(package.assembly_snapshot),
                safety_substitutions=[], teacher_overrides=[],
                previous_had_overrides=False, status="active",
                valid_from=GENERATED_ON,
                valid_to=GENERATED_ON + dt.timedelta(weeks=MICROCYCLE_WEEKS)
                - dt.timedelta(days=1),
                trigger_reasons=["first_stratification"],
            )
            s.add(row)
            s.flush()
            ids[f"prescription_{student_no}"] = row.id

        if extra_empty_section:
            empty = CourseSection(semester_id=semester.id, teacher_id=teacher.id,
                                  name="还没选上的班", grouping_mode="stratified")
            s.add(empty)
            s.flush()
            ids["empty_section"] = empty.id
        s.commit()
    return ids


def _strat(engine, ids, student_id: int, computed_on: D, label: str,
           batch_id=None) -> None:
    with Session(engine) as s:
        s.add(M.StratificationResult(
            student_id=student_id, computed_on=computed_on,
            batch_id=ids["batch"] if batch_id is None else batch_id,
            label=label, hit_rules="G1", input_snapshot={},
            # ⚠️ 值域是 {"school", "national", "none"}（ck_stratification_result_percentile_source），
            #    写字面的 "snapshot" 会当场 CHECK 违例
            percentile_source="school",
            valid_from=computed_on, valid_to=None,
        ))
        s.commit()


def _session_at(engine, ids, session_date: D, period: int = 3,
                section=None) -> int:
    with Session(engine) as s:
        row = ClassSession(
            course_section_id=ids["section"] if section is None else section,
            session_date=session_date, period=period, rpe_opened=True,
            rpe_token="tok", batch_id=None,
        )
        s.add(row)
        s.commit()
        return row.id


def _rpe(engine, class_session_id: int, student_id: int, rpe: int,
         submitted_at: T) -> None:
    with Session(engine) as s:
        s.add(RpeRecord(class_session_id=class_session_id, student_id=student_id,
                        rpe=rpe, submitted_at=submitted_at, elapsed_seconds=8.0))
        s.commit()


def _log(engine, student_id: int, log_date: D, *, completed=True, late=False,
         is_rest_day=False, submitted_at=None) -> None:
    with Session(engine) as s:
        s.add(TrainingLog(
            student_id=student_id, log_date=log_date,
            submitted_at=(T(log_date.year, log_date.month, log_date.day, 9, 0)
                          if submitted_at is None else submitted_at),
            completed=completed, duration_min=30.0 if completed else None,
            feeling="moderate" if completed else None, is_rest_day=is_rest_day,
            late=late, source="checkin", batch_id=None,
        ))
        s.commit()


#: 全班的折返秒数一律取这一个值 → 所有人**并列** → 班内百分位反查一律 **50.0**
#: （``(0 + 0.5 × n) / n × 100``），故 ``composite = (squat_30s_count + 50) / 2``。
#: ⚠️ **它是「让综合分可手算」的构造手段，不是被测函数的一部分**：下面每个调用点写的
#: 深蹲次数与它的期望综合分都能口算对上（70 → 60.0、82 → 66.0、58 → 54.0、
#: 90 → 70.0、130 → 90.0），期望值一律字面写在断言里、不从被测函数读回来
#: （硬规矩 #35）。算式本身的守卫在 ``tests/domain/test_report.py``。
SHUTTLE_TIED = 30.0


def _mini(engine, ids, student_id: int, week: int, *, squat: "int | None",
          shuttle: "float | None" = SHUTTLE_TIED, score=None) -> None:
    """一行 ``mini_test``。

    ⚠️ **入参是原始测量值**（``squat`` = 30 秒深蹲次数、``shuttle`` = 20m 折返秒数），
    不是综合分：自 Plan 03 Task 9 起进步榜读的是
    :func:`app.pipeline.report_stage._composite_of` **算出来的**综合分，
    ``normalized_score`` 那一列在本模块**没有读者**了。
    ⚠️ 故 ``score`` 缺省留 ``NULL``——那正是「这一列在生产路径上没人写」的真实形状
    （它今天的唯一写入方是 :func:`app.demo_data.build_demo_feedback`）。
    要给值只是为了 ``GREEN_MASTERY`` 那几条（它们读的是
    :func:`app.pipeline.alert_stage._mini_test_improved`，那一处**仍读列**）。
    """
    with Session(engine) as s:
        s.add(MiniTest(
            student_id=student_id, semester_id=ids["semester"], week=week,
            item_combo=["squat_30s", "shuttle_20m"], squat_30s_count=squat,
            shuttle_20m_s=shuttle, normalized_score=score,
            tested_on=SEMESTER_START + dt.timedelta(weeks=week - 1),
            entered_by=TEACHER_STAFF_NO,
        ))
        s.commit()


def _alert(engine, ids, *, level, rule_id, status="pending", student_id=None,
           section_id=None, triggered_at=None, window_key="w") -> int:
    """一行 ``alert``。⚠️ **两个作用域列恰好一个非空**（``ck_alert_subject_is_exactly_one``）：
    给了 ``student_id`` 就是学生级（``course_section_id`` 留 ``NULL``），
    否则是班级级（填 ``section_id``，缺省用本夹具那个班）。
    """
    with Session(engine) as s:
        subject_section = None if student_id is not None else (
            ids["section"] if section_id is None else section_id
        )
        row = Alert(
            student_id=student_id,
            course_section_id=subject_section,
            semester_id=ids["semester"],
            subject_key=(f"student:{student_id}" if student_id is not None
                         else f"section:{subject_section}"),
            level=level, rule_id=rule_id, trigger_snapshot={},
            triggered_at=NOW if triggered_at is None else triggered_at,
            status=status, batch_id=ids["batch"], window_key=window_key,
        )
        s.add(row)
        s.commit()
        return row.id


def _generate(engine, ids, week: int, as_of: D, *, now=NOW):
    """跑一次周报阶段，返回 ``(ReportSummary, Session)``。

    ⚠️ **会话留给调用方关**：断言要在同一个会话里读库（内存库 + 用完即关的纪律）。
    """
    session = Session(engine)
    report = generate_weekly_reports(
        session, ids["semester"], ids["batch"], week,
        as_of=as_of, now=now, exercises=exercise_library(),
    )
    session.commit()
    return report, session


def _rows(session, section=None) -> list:
    stmt = select(WeeklyClassReport).order_by(WeeklyClassReport.id)
    if section is not None:
        stmt = stmt.where(WeeklyClassReport.course_section_id == section)
    return list(session.scalars(stmt))


# ===========================================================================
# 支 A：周日判据（spec §8.5 逐字「每周日批处理生成」）
# ===========================================================================


def test_the_report_weekday_constant_is_six_and_six_is_sunday():
    """``REPORT_WEEKDAY == 6``，而 ``6`` 在 ``weekday()`` 的口径下**是周日**。

    ⚠️ 期望侧是**字面量 6** 与 ``dt.date(2025, 9, 14).weekday()``（一个真实的周日），
    不是 ``REPORT_WEEKDAY`` 自己（否则两侧同源、恒绿）。
    ⚠️ 本条钉的是那个 off-by-one：把常量改成 ``5``（周六）或 ``7``
    （``weekday()`` 的值域是 ``0..6``，故 ``7`` 永不成立、周报永远不生成）都会红。
    """
    assert REPORT_WEEKDAY == 6
    assert SUNDAY.weekday() == REPORT_WEEKDAY
    # 反证：isoweekday() == 6 的那一天是**周六**，不是周日
    assert SATURDAY.isoweekday() == 6
    assert SATURDAY.weekday() != REPORT_WEEKDAY


def test_is_report_day_over_one_whole_real_week():
    """**一整周七天逐个过一遍**（2025-09-08 周一 .. 2025-09-14 周日）。

    ⚠️ 七个日期全是**字面写死**的真实日期，期望侧是一个字面的布尔列表。
    只有周日那一格是 ``True``：一条「只有一个是 True」的断言挡不住
    「判据挪到了周六」这一类改动，而逐个列出七天可以。
    """
    days = [D(2025, 9, day) for day in range(8, 15)]
    assert [d.strftime("%a") for d in days] == [
        "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
    ]
    assert [is_report_day(d) for d in days] == [
        False, False, False, False, False, False, True,
    ]


def test_a_saturday_does_not_generate_a_report(engine):
    """**边界格 1/3**：2025-09-13（周六）不生成。

    ⚠️ 这一格与下一条只差**一天**，而它是 ``isoweekday() == 6`` 那个错写法会命中的日子
    ——把判据写成 ``as_of.isoweekday() == 6`` 的话本条当场红、而下一条也红，
    两条一起才指得出真因是「用错了 weekday 家族」。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], SATURDAY.isoformat(), _NullAdapter())
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0


def test_a_sunday_generates_a_report(engine):
    """**边界格 2/3**：2025-09-14（周日）**生成**，且周次算的是**学期第 2 周**。

    ⚠️ 周次那一格是本条的牙：``semester_week_of(2025-09-01, 2025-09-14) == 2``，
    而 09-14 正是第 2 周的**最后一天**。把判据写成 ``isoweekday() == 7`` 也能过本条，
    故它上面还有 :func:`test_is_report_day_over_one_whole_real_week` 那一条逐日钉住。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    assert SUNDAY.weekday() == 6 and SUNDAY.strftime("%A") == "Sunday"
    assert semester_week_of(SEMESTER_START, SUNDAY) == 2
    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], SUNDAY.isoformat(), _NullAdapter())
    with Session(engine) as s:
        rows = _rows(s)
        assert len(rows) == 1, "一个有名册的教学班 → 一份周报"
        assert rows[0].week == 2
        assert rows[0].semester_id == ids["semester"]
        assert rows[0].course_section_id == ids["section"]
        # generated_at 是 run_daily 注入的那一个 now（不是 weekly_class_report 的缺省，
        # 那一列刻意没有缺省：本仓全部表的时钟都由调用方注入）
        assert rows[0].generated_at is not None
        run = s.scalar(select(M.DailySyncRun).where(
            M.DailySyncRun.business_date == SUNDAY))
        assert run.started_at <= rows[0].generated_at
        assert rows[0].batch_id == run.id


def test_a_monday_does_not_generate_a_report(engine):
    """**边界格 3/3**：2025-09-15（周一）不生成。

    ⚠️ 这一格挡的是 ``weekday() == 0``（把 Monday == 0 读成「0 就是周日」）。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], MONDAY.isoformat(), _NullAdapter())
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0


def test_a_sunday_before_the_semester_starts_generates_nothing(engine):
    """**开学日之前的那个周日**（2025-08-31）→ 不生成。

    ⚠️ 挡它的**不是**星期几（那一天确实是周日，:func:`is_report_day` 对它返回
    ``True``），而是 ``semester_week_of`` 返回 ``None``（没有「本学期第几周」可言，
    而 ``weekly_class_report.week`` 是 NOT NULL、且是幂等键的一列）。
    两件事**不互相掩盖**，故两个判据都要在。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    day = D(2025, 8, 31)
    assert day.weekday() == 6, "本条要的就是一个开学前的周日"
    assert is_report_day(day) is True
    assert semester_week_of(SEMESTER_START, day) is None
    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], day.isoformat(), _NullAdapter())
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0


class _NullAdapter:
    """一个**什么都不抽**的适配器：本支要测的只有「星期几」，三源一律为空。

    ⚠️ 三个 ``fetch_*`` 的签名是 ``(since)``（:func:`app.pipeline.extract.extract`
    只调这三个，且各传一个水位线串），返回空元组即可。
    """

    def fetch_fitness(self, since):
        return ()

    def fetch_body_comp(self, since):
        return ()

    def fetch_survey(self, since):
        return ()


# ===========================================================================
# 支 B：_replay_cleanup 从六张扩到七张（AST 口径）
# ===========================================================================

#: **AST 口径**下 ``_replay_cleanup`` 那个元组的成员（按书写序）。
#: ⚠️ 前三个带 ``models.`` 前缀、后四个是裸名——那**不是风格选择**：
#: 前三张在 ``app.db.models`` 的公有导入面上（Ruling 97 的 33 个名字里），
#: 后四张刻意不在，只能走子模块路径 import 进来再用裸名引用。
REPLAY_CLEANUP_SEVEN = [
    "models.DerivedMetrics",
    "models.StratificationResult",
    "models.PercentileSnapshot",
    "WeeklyAdjustment",
    "Prescription",
    "Alert",
    "WeeklyClassReport",
]


def _replay_cleanup_names() -> list:
    """按 **AST** 读出 ``app/pipeline/daily.py`` 里 ``_replay_cleanup`` 那个元组的成员。

    ⚠️ **绝不用正则数源码**（硬规矩 #89）：那个元组的元素既有 ``models.X`` 也有裸名
    ``X``，还有夹在中间的注释，正则要么数错、要么把注释里的名字也数进来。
    AST 读的是**语法树**，故它数到的与运行时真的会迭代的是同一批。
    """
    tree = ast.parse((BACKEND / "app" / "pipeline" / "daily.py").read_text(
        encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_replay_cleanup":
            for sub in ast.walk(node):
                if isinstance(sub, ast.For) and isinstance(sub.iter, ast.Tuple):
                    return [ast.unparse(elt) for elt in sub.iter.elts]
    raise AssertionError("_replay_cleanup 或它那个 for 元组不见了")


def test_the_replay_cleanup_list_is_pinned_to_seven_tables():
    """**清单从六张扩到七张**（加 ``WeeklyClassReport``），按长度与成员逐字钉住。

    ⚠️ **本条是给下一个人看的**（简报 P8-A1 逐字要求）：没有它，加第八张表的人会
    静默改变重放语义——他既可能忘了加（那一行永远停在旧批次上，见
    :func:`app.pipeline.daily._replay_cleanup` 的 docstring），也可能加错位置
    （子表排在父表后面 → 当场 ``FOREIGN KEY constraint failed``）。
    ⚠️ 形状照 ``tests/pipeline/test_alert_stage.py`` 的
    ``test_replay_cleanup_still_does_not_cover_class_session``（那一条钉的是
    「**不得**进清单」的那一张）。
    """
    assert _replay_cleanup_names() == REPLAY_CLEANUP_SEVEN
    assert len(REPLAY_CLEANUP_SEVEN) == 7


def test_the_two_spelling_styles_in_the_list_both_resolve():
    """清单里**两种写法都能解析**（简报 P8-A1 逐字要求核实）。

    前三个是 ``models.<类名>``（``models`` 由顶层 ``from app.db import models`` 绑定到
    ``app.db`` 这个**模块对象**），后四个是裸名（各由自己的
    ``from app.db.models.<子模块> import <类名>`` 绑定到**类对象**）。
    两者在函数体里都能取到一个带 ``__table__`` 的类，故
    :func:`app.db.repo.delete_by_batch` 对两者都成立。

    ⚠️ 期望侧是 ``app.db`` 模块与四个类**自己**（运行时口径），
    不是 ``daily.py`` 的源码文本。
    """
    from app.db import models as models_module
    from app.pipeline import daily

    assert daily.models is models_module
    for name in ("DerivedMetrics", "StratificationResult", "PercentileSnapshot"):
        assert getattr(daily.models, name).__tablename__ == {
            "DerivedMetrics": "derived_metrics",
            "StratificationResult": "stratification_result",
            "PercentileSnapshot": "percentile_snapshot",
        }[name]
    for bare, table in (("WeeklyAdjustment", "weekly_adjustment"),
                        ("Prescription", "prescription"),
                        ("Alert", "alert"),
                        ("WeeklyClassReport", "weekly_class_report")):
        assert getattr(daily, bare).__tablename__ == table


def test_replay_cleanup_covers_weekly_class_report(engine):
    """**行为面的一半**：跑一次 ``_replay_cleanup`` 之后周报行**没了**。

    ⚠️ 漏掉 ``WeeklyClassReport`` 的失效形态**不是翻倍**
    （``uq_weekly_class_report_section_semester_week`` 挡着，``repo.upsert`` 会走
    更新分支），而是更隐蔽的一格：那一行会静默沿用**上一轮**的 ``batch_id``，
    于是下一次重放按新的 ``batch_id`` 删时**删不到它**。故本条断言的不只是
    「行没了」，还断言它此前**确实带着本批的 batch_id**（否则删掉它证明不了什么）。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    report, session = _generate(engine, ids, 2, SUNDAY)
    assert report.generated == 1
    row = _rows(session)[0]
    assert row.batch_id == ids["batch"]
    report_id = row.id

    daily._replay_cleanup(session, ids["batch"])
    session.flush()
    assert session.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0
    assert session.get(WeeklyClassReport, report_id) is None
    session.close()


def test_replaying_a_sunday_keeps_exactly_one_report(engine):
    """**真重放**：同一个周日跑两遍 :func:`app.pipeline.daily.run_daily` → 仍是一行。

    ⚠️ 两遍的 ``batch_id`` 是**同一个**（``daily_sync_run`` 的幂等键是
    ``(semester_id, business_date)``，故重跑命中同一行），而
    :func:`app.pipeline.daily._replay_cleanup` 在第二遍开头就按它删掉了第一遍写的
    周报行、再由 ``repo.upsert`` 重新插一行。
    ⚠️ **「清单里缺 ``WeeklyClassReport``」的直接证据不是本条**，而是
    :func:`test_replay_cleanup_covers_weekly_class_report`（它对着 ``_replay_cleanup``
    本身断言「表空了」）。本条只是整条管道上的可见后果：重放不翻倍。
    ⚠️ 本条**刻意不断言 ``id`` 变了**（前一版这么写、当场红）：SQLite 的 rowid 分配是
    ``max(rowid) + 1``，删掉唯一那一行之后 ``max`` 回到 0，于是重新插入拿到的仍是
    ``1``——「删了再插」与「就地更新」在 ``id`` 上**同形**，故 ``id`` 不是这一档的判据。
    ⚠️ 本条**刻意不**先塞一行 ``stratification_result``：``run_daily`` 自己会为
    名册里的三个人各写一行 ``insufficient_data``（他们没有体测数据 → Z0 闸门），
    而手工塞的那一行会与它撞 ``(student_id, computed_on)`` 唯一约束
    （Ruling 212 的那道响亮失败）。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], SUNDAY.isoformat(), _NullAdapter())
    with Session(engine) as s:
        assert len(_rows(s)) == 1

    with Session(engine) as s:
        daily.run_daily(s, ids["semester"], SUNDAY.isoformat(), _NullAdapter())
    with Session(engine) as s:
        rows = _rows(s)
        assert len(rows) == 1, "重放不得插出第二行"
        run = s.scalar(select(M.DailySyncRun).where(
            M.DailySyncRun.business_date == SUNDAY))
        assert rows[0].batch_id == run.id
        # 夹具自己那一行（business_date = 09-01）+ run_daily 这一行（09-14）= 2
        assert s.scalar(select(func.count()).select_from(M.DailySyncRun)) == 2


# ===========================================================================
# 支 C：spec §8.5 的六个字段
# ===========================================================================


def test_the_report_row_carries_the_six_spec_fields(engine):
    """**spec §8.5 的六项**逐个对账（五个 ``JsonText`` 列的键集 + ``suggestion`` 是文本）。

    ⚠️ 期望侧的键集是**字面写的**（``by_layer`` / ``previous`` / ``flow`` …），
    不从 :mod:`app.domain.report` 读回来——那会让「domain 少给了一个键」与
    「周报少落了一列」两种失效互相掩盖。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    _strat(engine, ids, s1, SUNDAY, "green")
    _strat(engine, ids, s2, SUNDAY, "yellow")
    _strat(engine, ids, s3, SUNDAY, "red")
    cs = _session_at(engine, ids, D(2025, 9, 9))
    _rpe(engine, cs, s1, 6, T(2025, 9, 9, 10, 0))
    _rpe(engine, cs, s2, 8, T(2025, 9, 9, 10, 1))

    _report, session = _generate(engine, ids, 2, SUNDAY)
    row = _rows(session)[0]

    # ① 分层分布 + 周环比流动
    assert sorted(row.layer_distribution) == ["by_layer", "flow", "previous"]
    assert row.layer_distribution["by_layer"] == {
        "red": 1, "yellow": 1, "green": 1, "insufficient_data": 0,
    }
    # 学期第 2 周，而上一周（第 1 周）一行分层都没有 → 「不知道」不得讲成「变化了」
    assert row.layer_distribution["previous"] is None
    assert row.layer_distribution["flow"]["has_previous"] is False
    assert row.layer_distribution["flow"]["entered"] == {
        "red": [], "yellow": [], "green": [], "insufficient_data": [],
    }

    # ② 本周人均 RPE 曲线 + 与上周对比
    assert sorted(row.rpe_summary) == [
        "curve", "delta", "mean", "previous_curve", "previous_mean",
    ]
    assert len(row.rpe_summary["curve"]) == 7, "横轴恒是那 7 天"
    assert row.rpe_summary["mean"] == 7.0
    # ⚠️ 第 2 周**有**上一周（只是上一周一次快评都没有）→ previous_curve 是七个 None
    #    而不是 None 本身。两档刻意可区分：None 说的是「上周不存在」（第 1 周），
    #    七个 None 说的是「上周存在、但一天都没交」，而前端要靠它决定画不画那条虚线
    #    （守卫见 test_the_first_week_leaves_the_three_comparisons_null）。
    assert row.rpe_summary["previous_curve"] == [None] * 7
    assert row.rpe_summary["previous_mean"] is None
    assert row.rpe_summary["delta"] is None
    assert row.rpe_summary["curve"][1] == {
        "day": "2025-09-09", "mean": 7.0, "submissions": 2,
    }
    assert row.rpe_summary["curve"][0] is None, "09-08 一节课都没交 → None 而不是 0"

    # ③ 按层分组的打卡完成率
    assert sorted(row.checkin_rate_by_layer) == [
        "green", "insufficient_data", "red", "yellow",
    ]
    for layer, bucket in row.checkin_rate_by_layer.items():
        assert sorted(bucket) == ["measured", "rate", "students"], layer
        assert bucket["students"] == (1 if layer in ("green", "yellow", "red") else 0)

    # ④ 二次小测进步榜 Top10 与退步名单
    assert sorted(row.progress_board) == [
        "regressed", "top", "top_n", "unchanged", "unmeasured",
    ]
    assert row.progress_board["top_n"] == 10

    # ⑤ 预警汇总（红/黄/绿各若干，已处理/待处理）
    assert sorted(row.alert_summary) == ["green", "red", "yellow"]
    for level, bucket in row.alert_summary.items():
        assert list(bucket) == ["pending", "handled", "ignored"], level

    # ⑥ 算法建议（自由文本，不是 JSON）
    assert isinstance(row.suggestion, str)
    assert row.suggestion == "维持当前强度"
    assert row.generated_at == NOW
    assert row.week == 2
    session.close()


def test_the_previous_week_snapshot_makes_the_flow_real(engine):
    """上一周**有**分层行 → ``has_previous`` 为真、换层的人两个名单都进。"""
    ids = _seed(engine)
    s1, s2 = ids[STUDENT_NOS[0]], ids[STUDENT_NOS[1]]
    # 第 1 周（09-01..07）与第 2 周（09-08..14）各一行
    _strat(engine, ids, s1, D(2025, 9, 3), "red")
    _strat(engine, ids, s2, D(2025, 9, 3), "green")
    _strat(engine, ids, s1, SUNDAY, "green")     # 红 → 绿（升入）
    _strat(engine, ids, s2, SUNDAY, "green")     # 没动

    _report, session = _generate(engine, ids, 2, SUNDAY)
    dist = _rows(session)[0].layer_distribution
    assert dist["previous"] == {
        "red": 1, "yellow": 0, "green": 1, "insufficient_data": 0,
    }
    flow = dist["flow"]
    assert flow["has_previous"] is True
    assert flow["entered"]["green"] == [s1]
    assert flow["left"]["red"] == [s1]
    assert flow["entered"]["yellow"] == []
    assert flow["appeared"] == {
        "red": [], "yellow": [], "green": [], "insufficient_data": [],
    }
    session.close()


def test_the_first_week_leaves_the_three_comparisons_null(engine):
    """**学期第 1 周**（``week == 1``）→ 三个「与上周对比」的格子一律 ``None``。

    ⚠️ 与上一条（第 2 周而上一周没有数据）刻意**可区分**：
    ``previous_curve`` 在第 1 周是 ``None``（上周**不存在**），
    在第 2 周是七个 ``None``（上周存在、但一天都没交）。
    前端靠它决定「画不画那条虚线」——画一条不存在的虚线，教师会以为上周是 0。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, D(2025, 9, 5), "green")
    cs = _session_at(engine, ids, D(2025, 9, 3))
    _rpe(engine, cs, s1, 6, T(2025, 9, 3, 10, 0))

    _report, session = _generate(engine, ids, 1, D(2025, 9, 7))
    row = _rows(session)[0]
    assert row.week == 1
    assert row.rpe_summary["previous_curve"] is None
    assert row.rpe_summary["previous_mean"] is None
    assert row.rpe_summary["delta"] is None
    assert row.rpe_summary["mean"] == 6.0
    assert row.layer_distribution["previous"] is None
    assert row.layer_distribution["flow"]["has_previous"] is False
    session.close()


def test_labels_at_picks_the_latest_row_not_the_first(engine):
    """:func:`labels_at` 取的是 ``computed_on <= watermark`` 里**最大**的那一行。

    ⚠️ 失效形态：取了最小的那一行（或 ``LIMIT 1`` 不带 ``ORDER BY``）的话，
    第 2 周的周报会按**第 1 周**的标签分组，而教师看到的分层饼图与他昨天在大屏上
    看到的不一样——两个都对不上任何一个真实的日子。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, D(2025, 9, 2), "red")
    _strat(engine, ids, s1, D(2025, 9, 9), "yellow")
    _strat(engine, ids, s1, D(2025, 9, 12), "green")
    # 09-20 那一行在水位线之后，不得被读到
    _strat(engine, ids, s1, D(2025, 9, 20), "insufficient_data")
    with Session(engine) as s:
        assert labels_at(s, [s1], SUNDAY) == {s1: "green"}
        assert labels_at(s, [s1], D(2025, 9, 9)) == {s1: "yellow"}
        assert labels_at(s, [s1], D(2025, 8, 1)) == {}


def test_the_checkin_rate_is_grouped_by_layer_and_strict_about_late_logs(engine):
    """按层分组的完成率：分子是 ``_counted_checkin_days``（**迟交不算**），
    分母是「处方训练日 ∩ 学期第 2 周」。

    绿层模板每周 2 天（day = [1, 2]），处方 09-01 生成 → 第 2 周的训练日是
    **09-08 与 09-09**。故：

    * 学生 1：两天都按时交 → ``1.0``；
    * 学生 2：09-08 按时交、09-09 **迟交**（``late=True``）→ ``0.5``
      （spec §8.1 逐字「22:00 后提交仍入库但标记 ``late = true``，**不计入当日完成**」）；
    * 学生 3：一天都没交 → ``0.0``（**不是** ``None``：他确实 measurable、确实没练）。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    for student in (s1, s2, s3):
        _strat(engine, ids, student, SUNDAY, "green")
    _log(engine, s1, D(2025, 9, 8))
    _log(engine, s1, D(2025, 9, 9))
    _log(engine, s2, D(2025, 9, 8))
    _log(engine, s2, D(2025, 9, 9), late=True,
         submitted_at=T(2025, 9, 9, 22, 30))
    _log(engine, s3, D(2025, 9, 10), is_rest_day=True)   # 非训练日的「今日休息」

    _report, session = _generate(engine, ids, 2, SUNDAY)
    by_layer = _rows(session)[0].checkin_rate_by_layer
    assert by_layer["green"] == {"students": 3, "measured": 3, "rate": 0.5}
    session.close()


def test_a_student_without_a_prescription_is_unmeasured_not_zero(engine):
    """没有处方的学生 → ``rate`` 是 ``None``（计入 ``students``、不计入 ``measured``）。

    ⚠️ 把他算成 ``0.0`` 会让「系统还没给他排处方」变成「他一天都没练」，
    而完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    for student in (s1, s2, s3):
        _strat(engine, ids, student, SUNDAY, "red")
    with Session(engine) as s:
        s.delete(s.get(Prescription, ids[f"prescription_{STUDENT_NOS[1]}"]))
        s.commit()
    _log(engine, s1, D(2025, 9, 8))
    _log(engine, s1, D(2025, 9, 9))

    _report, session = _generate(engine, ids, 2, SUNDAY)
    by_layer = _rows(session)[0].checkin_rate_by_layer
    assert by_layer["red"] == {"students": 3, "measured": 2, "rate": 0.5}
    session.close()


def test_the_progress_board_reads_the_two_most_recent_mini_tests(engine):
    """进步榜按**最近两次**小测的标准化综合分相对变化排。

    ⚠️ 综合分自 Plan 03 Task 9 起是 :func:`app.pipeline.report_stage._composite_of`
    **算出来的**（``normalized_score`` 那一列在本模块没有读者了），故本条给的是
    **原始测量值**：全班的折返秒数一律 :data:`SHUTTLE_TIED`（并列 → 百分位一律 50.0），
    于是 ``composite = (深蹲次数 + 50) / 2``，三个人的两次数值都能口算对上：

    学生 1：深蹲 70 → 82，即 60.0 → 66.0 = ``+10.0%``（进步榜第一）；
    学生 2：深蹲 70 → 58，即 60.0 → 54.0 = ``-10.0%``（退步名单）；
    学生 3：只有**一次**小测 → 不在榜上、也**不计** ``unmeasured``
    （``unmeasured`` 说的是「有两次、但分数缺失」，那一档由
    :func:`test_a_missing_measurement_makes_the_student_unmeasured_not_zero` 守）。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    for student in (s1, s2, s3):
        _strat(engine, ids, student, SUNDAY, "green")
    _mini(engine, ids, s1, 1, squat=70)
    _mini(engine, ids, s1, 2, squat=82)
    _mini(engine, ids, s2, 1, squat=70)
    _mini(engine, ids, s2, 2, squat=58)
    _mini(engine, ids, s3, 2, squat=90)

    _report, session = _generate(engine, ids, 2, SUNDAY)
    board = _rows(session)[0].progress_board
    assert board["top"] == [{"student_id": s1, "change_pct": 10.0}]
    assert board["regressed"] == [{"student_id": s2, "change_pct": -10.0}]
    assert board["unchanged"] == 0
    assert board["unmeasured"] == 0
    session.close()


def test_a_missing_measurement_makes_the_student_unmeasured_not_zero(engine):
    """**Plan 03 Task 9 新加**：一次小测缺测 → ``composite`` 为 ``None`` → 进 ``unmeasured``、
    **不进榜**、也**绝不当 0 分**。

    这一档在 Task 9 之前**结构上不可达**：那时 ``mini_pairs`` 直接读
    ``normalized_score`` 那一列，而本文件的 ``_mini`` 助手给的是**非空**的综合分，
    于是「有两次、但分数缺失」只能靠 ``tests/domain/test_report.py`` 的合成 dict 覆盖，
    管道这一侧一条测试都没有。改成「生成时算」之后它变成了真实可达的一档
    （教师只录了深蹲、折返那一格空着），故补本条。

    ⚠️ **缺测的那一项不进百分位样本**（:func:`app.pipeline.report_stage._composite_of`
    的 ①）：学生 2 第 2 周的 ``shuttle_20m_s`` 是 ``NULL``，故那一周的样本只有
    学生 1 一个人 → 学生 1 的百分位是 ``50.0``（``n = 1``，
    :func:`app.domain.report.shuttle_percentile` 的自洽结果），综合分仍是
    ``(82 + 50) / 2 = 66.0`` → 与学生 1 自己第 1 周的 60.0 相比是 ``+10.0%``。
    ⚠️ 若把「没测」当成「最慢的那个」塞进样本，学生 1 的百分位会变成 ``100.0``、
    综合分变成 ``(82 + 100) / 2 = 91.0`` → ``+51.67%``，本条当场红：
    那正是「一个没测的人把全班的百分位一起往上拽」的失效形状。
    """
    ids = _seed(engine)
    s1, s2 = ids[STUDENT_NOS[0]], ids[STUDENT_NOS[1]]
    for student in (s1, s2):
        _strat(engine, ids, student, SUNDAY, "green")
    _mini(engine, ids, s1, 1, squat=70)
    _mini(engine, ids, s1, 2, squat=82)
    _mini(engine, ids, s2, 1, squat=70)
    _mini(engine, ids, s2, 2, squat=90, shuttle=None)   # ← 折返缺测

    _report, session = _generate(engine, ids, 2, SUNDAY)
    board = _rows(session)[0].progress_board
    assert board["unmeasured"] == 1, board
    assert board["top"] == [{"student_id": s1, "change_pct": 10.0}], board
    assert board["regressed"] == [], board
    assert board["unchanged"] == 0, board
    session.close()


def test_a_mini_test_in_a_future_week_is_not_read(engine):
    """**读不到未来**：一份录进了第 3 周的小测不得被第 2 周的周报当成「本次」。

    ⚠️ ``mini_test`` 是教师**批量录入**的，而录入没有「不得录未来周次」的约束
    （``MiniTest.week`` 的列注释逐字写了为什么不加那条 CHECK）。
    不夹上界的话，「最近两次」会变成第 2 与第 **3** 周，本条会算出
    ``66.0 → 90.0 = +36.36%`` 而不是 ``60.0 → 66.0 = +10.0%``，
    而那一天第 3 周还没发生。
    ⚠️ 本 docstring 此前印的是「会算出 ``60 → 90 = +50%``」——**那个数对不上任何一条路径**
    （取的是 ``rows[-2:]``，即最后两行，故被读到的是第 2 与第 3 周而不是第 1 与第 3 周），
    按 Plan 03 Task 9 的实测改写（深蹲 70 / 82 / 130 + 全班折返并列 → 综合分
    60.0 / 66.0 / 90.0，见 :data:`SHUTTLE_TIED` 的注释）。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    _mini(engine, ids, s1, 1, squat=70)     # → 综合分 60.0
    _mini(engine, ids, s1, 2, squat=82)     # → 综合分 66.0
    _mini(engine, ids, s1, 3, squat=130)    # ← 未来（→ 综合分 90.0）

    _report, session = _generate(engine, ids, 2, SUNDAY)
    board = _rows(session)[0].progress_board
    assert board["top"] == [{"student_id": s1, "change_pct": 10.0}]
    session.close()


def test_the_alert_summary_covers_both_scopes_of_the_class(engine):
    """预警汇总同时含**班级级**（``course_section_id``）与**本班学生的学生级**
    （``student_id``）两种作用域的预警，且带**当前状态**。

    ⚠️ 别的班的学生那一条**不得**进来（``or_`` 的两支各自都要收窄）。
    """
    ids = _seed(engine)
    s1, s2 = ids[STUDENT_NOS[0]], ids[STUDENT_NOS[1]]
    _strat(engine, ids, s1, SUNDAY, "green")
    _alert(engine, ids, level="red", rule_id="RED_RPE_SUSTAINED",
           student_id=s1, status="handled", window_key="rpe1")
    _alert(engine, ids, level="yellow", rule_id="YELLOW_CLASS_RPE_HIGH",
           window_key=f"{ids['semester']}:2")
    # 落在窗口之外的那一条（第 1 周触发）不得计入第 2 周的周报
    _alert(engine, ids, level="green", rule_id="GREEN_MASTERY", student_id=s2,
           triggered_at=T(2025, 9, 3, 8, 0), window_key=f"{ids['semester']}:1")

    _report, session = _generate(engine, ids, 2, SUNDAY)
    row = _rows(session, section=ids["section"])[0]
    assert row.alert_summary == {
        "red": {"pending": 0, "handled": 1, "ignored": 0},
        "yellow": {"pending": 1, "handled": 0, "ignored": 0},
        "green": {"pending": 0, "handled": 0, "ignored": 0},
    }
    # 班级级 YELLOW_CLASS_RPE_HIGH 命中 → 算法建议是降量（哪怕人均 RPE 判不了）
    assert row.suggestion == "本周建议整体降量 10%"
    session.close()


def test_the_suggestion_follows_the_low_rpe_branch(engine):
    """未命中班级信号、而人均 RPE ``< 5`` → 建议加量 10%。

    ⚠️ 与 ``alert_stage`` 那一份班级均值**同一个数**：三次快评 4 / 4 / 5 →
    均值 ``4.333…`` < 5.0 → 加量。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    _strat(engine, ids, s1, SUNDAY, "green")
    cs = _session_at(engine, ids, D(2025, 9, 9))
    _rpe(engine, cs, s1, 4, T(2025, 9, 9, 10, 0))
    _rpe(engine, cs, s2, 4, T(2025, 9, 9, 10, 1))
    _rpe(engine, cs, s3, 5, T(2025, 9, 9, 10, 2))

    _report, session = _generate(engine, ids, 2, SUNDAY)
    row = _rows(session)[0]
    assert row.rpe_summary["mean"] == pytest.approx(13 / 3)
    assert row.suggestion == "本周建议整体加量 10%"
    session.close()


# ===========================================================================
# 支 D：水位线（读不到未来）
# ===========================================================================


def test_generating_mid_week_does_not_read_the_rest_of_the_week(engine):
    """**周三**生成第 2 周的周报 → 周四那节课的快评**不在**里面。

    ⚠️ 水位线是 ``min(as_of, week_end)``。失效形态：周三生成、周日重生成，
    两份周报的 ``mean`` 不同，而教师端只留得下最新那一份——
    于是「周三看到的数」在事后**无从复现**（spec §4.3 的可追溯性）。
    ⚠️ 而曲线的**横轴**刻意仍是 7 天（水位线之后的几天是 ``None``），
    否则折线会自己缩短，教师看不出「周四是空的」与「周四不存在」的区别。
    """
    ids = _seed(engine)
    s1, s2 = ids[STUDENT_NOS[0]], ids[STUDENT_NOS[1]]
    _strat(engine, ids, s1, D(2025, 9, 10), "green")
    wednesday = _session_at(engine, ids, D(2025, 9, 10), period=3)
    thursday = _session_at(engine, ids, D(2025, 9, 11), period=4)
    _rpe(engine, wednesday, s1, 6, T(2025, 9, 10, 10, 0))
    _rpe(engine, thursday, s2, 10, T(2025, 9, 11, 10, 0))   # ← 水位线之后

    _report, session = _generate(engine, ids, 2, D(2025, 9, 10))
    row = _rows(session)[0]
    assert row.rpe_summary["mean"] == 6.0, "周四那个 10 不得进来"
    assert len(row.rpe_summary["curve"]) == 7
    assert row.rpe_summary["curve"][2] == {
        "day": "2025-09-10", "mean": 6.0, "submissions": 1,
    }
    assert row.rpe_summary["curve"][3] is None, "09-11 在水位线之后 → None"
    # 分层标签的水位线同理：09-12 那一行读不到
    _strat(engine, ids, s1, D(2025, 9, 12), "red")
    session.close()
    _report2, session2 = _generate(engine, ids, 2, D(2025, 9, 10))
    assert _rows(session2)[0].layer_distribution["by_layer"]["green"] == 1
    session2.close()


# ===========================================================================
# 支 E：幂等与 skipped
# ===========================================================================


def test_a_section_without_a_roster_is_skipped_and_gets_no_row(engine):
    """**名册为空的班 → ``skipped += 1``、不写行**。

    ⚠️ 一份「四个 0 + 三个 None」的周报对教师没有任何信息，而它在
    ``GET /api/dashboard/weekly-class-report/{id}`` 上看起来像
    「这个班本周什么都没发生」——与「这个班还没有人」是两件事。
    """
    ids = _seed(engine, extra_empty_section=True)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    report, session = _generate(engine, ids, 2, SUNDAY)
    assert (report.generated, report.skipped, report.errors) == (1, 1, 0)
    assert [r.course_section_id for r in _rows(session)] == [ids["section"]]
    session.close()


def test_generating_twice_for_the_same_week_updates_the_one_row(engine):
    """同一个 ``(班, 学期, 周次)`` 生成两遍 → 仍是一行，且内容是**第二遍**的。"""
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    first, session = _generate(engine, ids, 2, SUNDAY)
    assert first.generated == 1
    assert _rows(session)[0].suggestion == "维持当前强度"
    session.close()

    cs = _session_at(engine, ids, D(2025, 9, 9))
    for student_no in STUDENT_NOS:
        _rpe(engine, cs, ids[student_no], 9, T(2025, 9, 9, 10, 0))
    second, session = _generate(engine, ids, 2, SUNDAY, now=T(2025, 9, 14, 23, 0))
    assert second.generated == 1
    rows = _rows(session)
    assert len(rows) == 1
    assert rows[0].rpe_summary["mean"] == 9.0
    assert rows[0].generated_at == T(2025, 9, 14, 23, 0)
    session.close()


def test_an_unknown_semester_fails_loudly_not_silently(engine):
    """``semester_id`` 打错 → ``ValueError``，**不是** ``generated = 0``。

    ⚠️ 静默返回空的失效形态：「学期 id 打错了」与「这个学期一个班都没有」
    在 :class:`ReportSummary` 上同形（三个 0），而运维看计数决定要不要重跑。
    ⚠️ 而报错的那一句是**批次不匹配**（复用处方阶段那一道校验，全仓只有一个所有者），
    不是「查无此学期」：``generate_weekly_reports`` 刻意**不再**校验一次学期存在性
    ——那一道过后 ``semester_id`` 必然存在（``daily_sync_run.semester_id`` 是 NOT NULL
    外键），再写一次就是一段不可达的代码（理由逐字见那个函数体内的注释）。
    """
    ids = _seed(engine)
    with Session(engine) as s:
        with pytest.raises(ValueError) as exc:
            generate_weekly_reports(s, 999999, ids["batch"], 2,
                                    as_of=SUNDAY, now=NOW,
                                    exercises=exercise_library())
    assert "批次 1 属于 semester_id=1" in str(exc.value)
    assert "999999" in str(exc.value)


def test_a_batch_from_another_semester_is_rejected(engine):
    """``batch_id`` 与 ``semester_id`` 不是同一次运行 → 拒绝（复用处方阶段那道校验）。

    ⚠️ 接错批次的后果是重放**删不到**本批的行（``_replay_cleanup`` 按 ``batch_id`` 删），
    于是周报行永远停在旧批次上——与「漏掉 ``WeeklyClassReport`` 不进清单」是同一个失效。
    """
    ids = _seed(engine)
    with Session(engine) as s:
        other = Semester(name="2024-2025-1", start_date=D(2024, 9, 2),
                         end_date=D(2025, 1, 5), weeks=16, is_current=False)
        s.add(other)
        s.flush()
        with pytest.raises(ValueError):
            generate_weekly_reports(s, other.id, ids["batch"], 2,
                                    as_of=SUNDAY, now=NOW,
                                    exercises=exercise_library())


# ===========================================================================
# 支 F：异常分层
# ===========================================================================


def test_one_broken_training_package_does_not_kill_the_whole_report(
    engine, monkeypatch
):
    """**按人捕获**：一个学生的训练包装配不出来 → 他那一格是「判不了」，
    整份周报照生成、``errors`` 记 1、整批不回滚。

    ⚠️ 反证的一半：把 :func:`app.pipeline.report_stage._training_days` 的 ``try``
    去掉的话，本条会看到一个抛出来的异常（整份周报消失），而 ``errors`` 那一格
    也就永远数不到「按人」的那一档。
    """
    ids = _seed(engine)
    s1, s2, s3 = (ids[no] for no in STUDENT_NOS)
    for student in (s1, s2, s3):
        _strat(engine, ids, student, SUNDAY, "green")
    _log(engine, s1, D(2025, 9, 8))
    _log(engine, s1, D(2025, 9, 9))

    broken = ids[f"prescription_{STUDENT_NOS[1]}"]
    real = stage.training_days_of

    def spy(session, row, week, *, exercises):
        if row.id == broken:
            raise ValueError("训练包里有一个动作已经从 exercises.yaml 删掉了")
        return real(session, row, week, exercises=exercises)

    monkeypatch.setattr(stage, "training_days_of", spy)
    report, session = _generate(engine, ids, 2, SUNDAY)
    assert (report.generated, report.skipped) == (1, 0)
    assert report.errors == 1, "按人捕获的那一次要计进 errors"
    by_layer = _rows(session)[0].checkin_rate_by_layer
    # 两个人可测（s1 = 1.0、s3 = 0.0），坏的那一个不算 → 均值 0.5
    assert by_layer["green"] == {"students": 3, "measured": 2, "rate": 0.5}
    session.close()


def test_a_section_whose_snapshot_fails_is_skipped_not_fatal(engine, monkeypatch):
    """**按班捕获**：一个班的取数整体失败 → 那个班没有周报，其余班照生成。"""
    ids = _seed(engine, extra_empty_section=True)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    # 给「空名册」那个班也塞一个学生，于是两个班都要生成
    with Session(engine) as s:
        extra = Student(student_no="S2025099", name="学生99", sex="male",
                        birth=D(2005, 3, 4), department=None, grade=1)
        s.add(extra)
        s.flush()
        s.add(Enrollment(semester_id=ids["semester"], student_id=extra.id,
                         course_section_id=ids["empty_section"]))
        s.commit()
        other_id = extra.id
    _strat(engine, ids, other_id, SUNDAY, "red")

    real = stage.aggregates_of

    def spy(snapshot):
        if snapshot.course_section_id == ids["empty_section"]:
            raise KeyError("boom")
        return real(snapshot)

    monkeypatch.setattr(stage, "aggregates_of", spy)
    report, session = _generate(engine, ids, 2, SUNDAY)
    assert (report.generated, report.skipped, report.errors) == (1, 0, 1)
    assert [r.course_section_id for r in _rows(session)] == [ids["section"]]
    session.close()


# ===========================================================================
# 支 G：口径的单一所有者
# ===========================================================================


def test_the_status_vocabulary_matches_both_of_its_owners():
    """:data:`ALERT_STATUSES` 与**两个**所有者对账（两侧不同源，硬规矩 #35）。

    ① ``Alert.STATUSES``（+ DB 的 ``ck_alert_status``）——值域的所有者；
    ② ``alert_stage`` 的三个常量——生产写入方。
    ⚠️ 顺序也钉住：它就是周报载荷里三个键的顺序（前端按它排列三档按钮）。
    """
    from app.pipeline.alert_stage import ALERT_HANDLED, ALERT_IGNORED, ALERT_PENDING

    assert set(ALERT_STATUSES) == Alert.STATUSES
    assert ALERT_STATUSES == (ALERT_PENDING, ALERT_HANDLED, ALERT_IGNORED)
    assert len(ALERT_STATUSES) == 3


def test_the_class_signal_rule_id_is_the_domain_enum_value():
    """:data:`CLASS_RPE_HIGH_RULE` 是 ``RuleId`` 的一个成员的 ``.value``，不是字面串。

    ⚠️ 规则 ID 词表的所有者是 ``data/alert_rules.yaml``（``RuleId`` 与它由 Task 6 的
    一条测试对账）。写成第二份字面串的话，专家把 YAML 里的 ID 改名之后，
    「算法建议」会**静默**永远走「未命中」那一支。
    """
    from app.domain.alerts import AlertScope, RuleId

    assert CLASS_RPE_HIGH_RULE == RuleId.YELLOW_CLASS_RPE_HIGH.value
    assert CLASS_RPE_HIGH_RULE == "YELLOW_CLASS_RPE_HIGH"
    # 它确实是班级级的那一条（spec §8.5 逐字点名「班级级信号」）
    from app.refdata_alerts import alert_rules

    rule = alert_rules().rules[RuleId.YELLOW_CLASS_RPE_HIGH]
    assert rule.scope is AlertScope.CLASS
    assert rule.level.value == "yellow"


def test_the_json_column_list_matches_the_five_jsontext_columns_of_the_table():
    """:data:`app.pipeline.report_stage._JSON_COLUMNS` 与
    ``weekly_class_report`` 的 **5 个 ``JsonText`` 列**逐字相等（按集合）。

    ⚠️ 两侧不同源：一侧是本模块的常量、一侧是 SQLAlchemy 的表元数据
    （``isinstance(column.type, JsonText)`` 现场挑出来）。
    ⚠️ 它挡的是「加了一个聚合量、忘了落库」与「落进了一个不存在的列名」两种失效。
    """
    from app.db.models._shared import JsonText
    from sqlalchemy import Text

    observed = {
        column.name for column in WeeklyClassReport.__table__.columns
        if isinstance(column.type, JsonText)
    }
    assert observed == set(stage._JSON_COLUMNS)
    assert len(stage._JSON_COLUMNS) == 5
    # 而 suggestion 那一列刻意不在里面（它是给人看的自由文本，不是 JSON）
    assert "suggestion" not in observed
    assert isinstance(WeeklyClassReport.__table__.columns["suggestion"].type, Text)


def test_aggregates_of_returns_exactly_the_seven_keys():
    """:func:`aggregates_of` 的**键集**恰好是七个。

    ⚠️ 它是「大屏与周报共用同一批聚合量」这条纪律的可观测量：
    少一个键，某一条路径就得自己再算一遍（那就是第二个所有者）；
    多一个键，就有一个聚合量没有消费者（死配置）。
    """
    ids_keys = {
        "layer_distribution", "rpe_summary", "checkin_rate_by_layer",
        "progress_board", "alert_summary", "suggestion", "abnormal_roster",
    }
    snapshot = ClassSnapshotStub()
    assert set(aggregates_of(snapshot)) == ids_keys
    assert len(ids_keys) == 7


class ClassSnapshotStub:
    """一个**空的**快照（:func:`test_aggregates_of_returns_exactly_the_seven_keys` 用）。

    ⚠️ 它不是 :class:`app.pipeline.report_stage.ClassSnapshot` 的实例，而是**同形状**的
    鸭子：本条要钉的只是「七个键」，故不必建库。⚠️ 而 ``rates`` / ``labels_now``
    一律给空 dict，于是九个 domain 函数各自走「一个人都没有」那一档。
    """

    labels_now: dict = {}
    labels_prev = None
    rpe_now = stage.RpeWeek(days=(), values={})
    rpe_prev = None
    rates: dict = {}
    mini_pairs: dict = {}
    alert_rows: tuple = ()
    class_rpe_high = False
    gap_days: dict = {}
    peak_rpes: dict = {}


def test_class_snapshot_and_new_cache_are_exported_and_usable(engine):
    """:func:`class_snapshot` / :func:`new_cache` 是**公开面**（大屏要调它们）。

    ⚠️ 本条也是「大屏与周报共用同一个取数编排」的可达性守卫：
    若 ``class_snapshot`` 变成私有的，:mod:`app.api.routers.dashboard` 就只能自己写一遍
    SQL，而那正是模块 docstring 第一节要防的分叉。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    with Session(engine) as s:
        cache = new_cache(s, SUNDAY)
        snapshot = class_snapshot(
            s, semester_id=ids["semester"], course_section_id=ids["section"],
            week=2, as_of=SUNDAY, exercises=exercise_library(), cache=cache,
        )
    assert snapshot.roster == tuple(sorted(ids[no] for no in STUDENT_NOS))
    assert len(snapshot.roster) == 3, "名册是选课行，不是被分层过的人"
    assert snapshot.labels_now == {s1: "green"}
    assert snapshot.labels_prev is None
    assert snapshot.watermark == SUNDAY
    assert snapshot.week_start == D(2025, 9, 8)
    assert len(snapshot.rpe_now.days) == 7
    assert set(aggregates_of(snapshot)) == {
        "layer_distribution", "rpe_summary", "checkin_rate_by_layer",
        "progress_board", "alert_summary", "suggestion", "abnormal_roster",
    }


def test_the_cache_memoises_the_training_day_assembly(engine):
    """``ClassCache`` 真的**记忆化**了训练日装配（一个学生只装配一次）。

    ⚠️ 本条钉的是一个**性能决定**（模块 docstring 里给了实测：0.39 ms/次、
    整学期回放省 3.1 s），而性能决定没有守卫就会在下次重构时被顺手删掉。
    判据是「装配次数」，不是「耗时」（耗时会被机器噪声推动）。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")

    calls = []
    real = stage.training_days_of

    def spy(session, row, week, *, exercises):
        calls.append((row.id, week))
        return real(session, row, week, exercises=exercises)

    with Session(engine) as s:
        stage.training_days_of = spy
        try:
            cache = new_cache(s, SUNDAY)
            for _ in range(3):
                class_snapshot(
                    s, semester_id=ids["semester"],
                    course_section_id=ids["section"], week=2, as_of=SUNDAY,
                    exercises=exercise_library(), cache=cache,
                )
        finally:
            stage.training_days_of = real
    # 三次快照 → 装配次数与一次相同（(处方 id, 处方周次) 命中缓存）
    assert len(calls) == len(set(calls)), f"记忆化失效（同一个键被装配了两次）：{calls}"
    # ⚠️ 3 个学生 × 2 个处方周（第 2 周算完成率与中断、第 1 周只被中断判据看）= 6 个键。
    #    期望侧的 6 是**字面量**（3 个人来自 STUDENT_NOS、2 个周次来自绿层模板的
    #    「本周 + 上一周」），不从 calls 反推。
    assert len(calls) == 6, calls
    assert set(week for _pid, week in calls) == {1, 2}


def test_a_fresh_cache_does_not_share_the_memo(engine):
    """**反证的一半**：换一个新的 ``ClassCache`` 就会重新装配。

    ⚠️ 没有本条，上面那条「记忆化生效」可能只是因为 spy 根本没被调
    （例如处方到期 → ``current_week`` 返回 ``None`` → 压根走不到装配）。
    """
    ids = _seed(engine)
    s1 = ids[STUDENT_NOS[0]]
    _strat(engine, ids, s1, SUNDAY, "green")
    calls = []
    real = stage.training_days_of

    def spy(session, row, week, *, exercises):
        calls.append((row.id, week))
        return real(session, row, week, exercises=exercises)

    with Session(engine) as s:
        stage.training_days_of = spy
        try:
            for _ in range(2):
                cache = new_cache(s, SUNDAY)
                class_snapshot(
                    s, semester_id=ids["semester"],
                    course_section_id=ids["section"], week=2, as_of=SUNDAY,
                    exercises=exercise_library(), cache=cache,
                )
        finally:
            stage.training_days_of = real
    assert len(calls) == 2 * len(set(calls)), (
        f"两个独立的 cache 各自装配一遍，故次数应是不同键数的两倍：{calls}"
    )
    assert calls, "本条的前提是装配真的发生过（否则上一条的绿是空转）"


def test_report_summary_has_exactly_three_fields():
    """:class:`ReportSummary` 恰好三格（简报 Interfaces 的两格 + 本 Task 加的 ``errors``）。

    ⚠️ 期望侧是**字面**的三个名字，不是 ``dataclasses.fields`` 的长度
    （那会与实现同源）。多一格 = 一个没有消费者的计数，少一格 = 一档失效没人看见。
    """
    import dataclasses

    assert [f.name for f in dataclasses.fields(ReportSummary)] == [
        "generated", "skipped", "errors",
    ]
