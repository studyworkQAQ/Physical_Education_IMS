"""``app/pipeline/alert_stage.py`` 的守卫（Plan 03 Task 7）。

**分五支**，每支钉一件不同的事：

* **支 A（Review Focus 第 3 条）**：同一次触发只落一条 ``alert``、只减一次量。
  这是本 Task 唯一会造成**静默数据损坏**的失效形态（``0.8³ = 0.512``，全程不报错），
  故它有三条测试：同日重跑、streak 继续变长、以及 ``window_key`` 的锚点不被一次
  迟到提交移走。
* **支 B（``weekly_adjustment`` 的 ``auto`` 来源）**：Plan 02 结案时逐字留给 Plan 03 的活。
  含「值对象是写入侧唯一闸门」那条变异靶子（:data:`AUTO_REDUCTION_FACTOR` → ``0.0``）
  与「撞键由 DB 裁判、且不静默改已有行」那条。
* **支 C（P7-A3 的 6 条关切）**：逐条一个可执行的落点。⚠️ 其中第 1 条
  （``*_skip_traces`` 必须有消费者）与第 3 条（``rpe_min`` / ``improve_pct`` 由本 Task
  消费）如果没人读就是**死配置**，故这两支的判据是「换一套阈值，行为跟着变」。
* **支 D（口径的单一所有者）**：``training_days_of`` 全仓只有一份定义（AST 口径）、
  ``AlertRules.params_of`` 有生产调用者、学期周次的两个方向与 api 层逐字相等、
  四个字符串常量都在模型类常量的值域内。
* **支 E（通知与异常分层）**：黄色打卡中断自动发给学生、班级黄牌发给教师、
  绿牌发勋章、**红色一条都不发**（教师点了才推），以及一个学生的失败不掀掉整批。
* **支 E′（Plan 04 收尾波：综合分算出来、不读 ``normalized_score`` 那一列）**：
  一行**生产形状**的 ``mini_test``（那一列 NULL，逐字是 ``POST /api/mini-tests/batch``
  写出来的形状）能喂动 ``RED_MINITEST_DROP`` 与 ``GREEN_MASTERY``；本模块的综合分与
  进步榜那一份（``report_stage._composite_of``）**逐字相等**、且都等于手算的字面量；
  「一个学生在两个班」与「不在任何班」两档口径。
  ⚠️ 连带：本文件的 :func:`_mini` 夹具**不再往那一列灌数**（改之前六条测试全靠它，
  而生产数据上那一条规则恒为 ``insufficient_points``——那正是本波修的陷阱在夹具里的翻版）。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律字面写在测试里
（``0.8`` / ``"RED_RPE_SUSTAINED"`` / ``"student"`` / 那些日期），
**不从被测模块或 YAML 读回来**。要换阈值跑第二遍的那几条（支 C）是**刻意**改注入的
``AlertRules``，不是改断言。
"""
import ast
import datetime as dt
import pathlib

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.pipeline.alert_stage as stage
from app.db import models as M
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student, Teacher
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.db.session import init_db
from app.domain.alerts import AlertRule, AlertRules, RuleId
from app.domain.prescription.assembler import StudentProfile, assemble
from app.domain.prescription.weekly import weekly_training_sheet
from app.domain.indicators import Sex
from app.notify import InAppChannel
from app.pipeline.alert_stage import (
    ALERT_HANDLED,
    ALERT_IGNORED,
    ALERT_PENDING,
    AUTO_REDUCTION_FACTOR,
    AUTO_SOURCE,
    AlertReport,
    _counted_checkin_days,
    evaluate_alerts,
    semester_week_of,
    semester_week_range,
)
from app.pipeline.prescription_stage import (
    effective_package,
    training_package_payload,
    weekly_factors_of,
)
from app.refdata_alerts import alert_rules
from app.refdata_prescription import exercises as exercise_library
from app.refdata_prescription import templates as template_library

D = dt.date
T = dt.datetime

BACKEND = pathlib.Path(__file__).resolve().parents[2]

#: 学期起点。**2025-09-01 是周一**，而 18 套模板的 ``day`` 恒为 ``1..N`` 连续，
#: 故「处方第 1 周」与「学期第 1 周」在这一天完全对齐（口径照 ``tests/api/test_feedback.py``，
#: ⚠️ 但**刻意不复用它的夹具**：跨测试文件 import 私有夹具会让两个文件互相钉住）。
SEMESTER_START = D(2025, 9, 1)
SEMESTER_END = D(2025, 12, 22)
#: 处方生成日 = 学期第一天，微周期 4 周 → ``valid_to = 2025-09-28``（闭区间末日）。
GENERATED_ON = SEMESTER_START
MICROCYCLE_WEEKS = 4
#: 绿层模板：**每周 2 天**（第 N 周的 ``day`` = ``[1, 2]``）。
#: 于是处方第 1 周的训练日是 09-01 / 09-02，第 2 周 09-08 / 09-09，
#: 第 3 周 09-15 / 09-16，第 4 周 09-22 / 09-23。
GREEN_TEMPLATE = "GRN-END-NOR-14"
#: ``alert.triggered_at`` / ``notification.created_at`` / ``weekly_adjustment.created_at``
#: 三处共用的注入时刻。
NOW = T(2025, 9, 15, 6, 0)
STUDENT_NO = "S2025001"
OTHER_NO = "S2025002"
TEACHER_STAFF_NO = "T2025001"


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    return eng


def _profile(student_id: int = 1) -> StudentProfile:
    """个体修正系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。"""
    return StudentProfile(
        student_id=student_id, sex=Sex.MALE, birth=D(2005, 3, 4), age=20,
        endurance_score=70.0, bmi=None, body_fat_pct=None, muscle_mass_kg=None,
        muscle_p10=None, measured_hrmax=None,
    )


def _seed(engine, *, students=(STUDENT_NO,), with_prescription_for=STUDENT_NO,
          generated_on=GENERATED_ON) -> dict:
    """一套最小可用的行：学期 + 教师 + 教学班 + 学生（含选课）+ 一行批次 + 一张处方。"""
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

        for index, student_no in enumerate(students, start=1):
            student = Student(student_no=student_no, name=f"学生{index}", sex="male",
                              birth=D(2005, 3, 4), department=None, grade=1)
            s.add(student)
            s.flush()
            ids[student_no] = student.id
            s.add(Enrollment(semester_id=semester.id, student_id=student.id,
                             course_section_id=section.id))
        s.flush()

        run = M.DailySyncRun(semester_id=semester.id, business_date=GENERATED_ON,
                             started_at=T(2025, 9, 1, 2, 0), status="success")
        s.add(run)
        s.flush()
        ids["batch"] = run.id

        if with_prescription_for is not None:
            package = assemble(_profile(), template_library()[GREEN_TEMPLATE],
                               generated_on, exercises=exercise_library())
            row = Prescription(
                student_id=ids[with_prescription_for], generated_on=generated_on,
                batch_id=run.id, template_ref=GREEN_TEMPLATE,
                # ⚠️ 字面量 4，不读模板（硬规矩 #35）：它是「哪一周算越界」的判据
                microcycle_weeks=MICROCYCLE_WEEKS,
                label_at_generation="green",
                training_package=training_package_payload(package),
                assembly_snapshot=dict(package.assembly_snapshot),
                safety_substitutions=[], teacher_overrides=[],
                previous_had_overrides=False, status="active",
                valid_from=generated_on,
                valid_to=generated_on + dt.timedelta(weeks=MICROCYCLE_WEEKS)
                - dt.timedelta(days=1),
                trigger_reasons=["first_stratification"],
            )
            s.add(row)
            s.flush()
            ids["prescription"] = row.id
        s.commit()
    return ids


def _session_at(engine, session_date: D, period: int = 3, ids=None) -> int:
    with Session(engine) as s:
        row = ClassSession(course_section_id=ids["section"], session_date=session_date,
                           period=period, rpe_opened=True, rpe_token="tok",
                           batch_id=None)
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


#: 全班的折返秒数一律取这一个值 → 所有人**并列** → 班内百分位反查一律 **50.0**，
#: 故 ``composite = (squat_30s_count + 50) / 2``。
#: ⚠️ 口径与 ``tests/api/test_dashboard.py`` 的 ``SHUTTLE_TIED`` /
#: ``tests/pipeline/test_report_stage.py`` 的同名常量逐字相同（三个文件各持一份
#: **字面量**、不互相 import：期望值不从被测函数读回来，硬规矩 #35）。
SHUTTLE_TIED = 30.0


def _squat_for_composite(composite: float) -> int:
    """「想要的标准化综合分」→ 该写进 ``squat_30s_count`` 的次数。

    算式**字面写在这里**（硬规矩 #35：期望侧不调 ``app.domain.report``，否则
    「综合分算得对不对」这件事就没有第二个人在看了）：单人班 + 折返一律
    :data:`SHUTTLE_TIED` → 班内百分位恒 **50.0** → ``composite = (squat + 50) / 2``，
    故 ``squat = 2 × composite − 50``。⚠️ 本文件用到的六格（100 / 102 / 110 / 120 /
    90 / 80）换算出来都是整数、且回代逐格相等（:func:`_mini` 的 docstring 里
    那一条守卫把这个往返钉住）。
    """
    return int(2 * composite - 50)


def _mini(engine, ids, student_id: int, week: int, *, score=None, squat=None,
          shuttle=SHUTTLE_TIED) -> None:
    """一行 ``mini_test``。

    ⚠️⚠️ **``score`` 是「想要的综合分」，它被换算成深蹲次数写进 ``squat_30s_count``，
    而 ``normalized_score`` 那一列一律留 ``NULL``**（Plan 04 收尾波改的）：
    自本波起 ``alert_stage`` **不读那一列**了（完整诊断逐字见
    :func:`app.pipeline.alert_stage._mini_test_composites` 的 docstring 首节），
    而那一列在生产路径上本来就是 ``NULL``（``POST /api/mini-tests/batch`` 显式写
    ``normalized_score=None``）。故继续往它里面灌数会让「测试绿」与「生产能触发」
    变成两件事——**那正是本波要修的那个陷阱在夹具里的翻版**（改之前本文件的
    六条 ``GREEN_MASTERY`` / ``RED_MINITEST_DROP`` 测试全靠它，而生产数据上
    ``RED_MINITEST_DROP`` 恒为 ``insufficient_points``）。

    ⚠️ 于是「三次小测 100 → 90 → 80」这类既有措辞**仍然逐字为真**：
    它们是 ``composites`` 的三个值，只是不再由一列直接给出、而是由原始测量值算出来。

    ⚠️ ``score`` 与 ``squat`` **二选一**（都给就是夹具写错了，当场 ``AssertionError``
    ——两个入参各有一条路径：前者是「我要一个综合分」、后者是「我要一个原始次数」，
    同时给的话后者会被静默覆盖，而那正是本函数要消灭的那种静默）。
    """
    assert not (score is not None and squat is not None), "score 与 squat 只能给一个"
    with Session(engine) as s:
        s.add(MiniTest(
            student_id=student_id, semester_id=ids["semester"], week=week,
            item_combo=["squat_30s", "shuttle_20m"],
            squat_30s_count=(_squat_for_composite(score) if score is not None else squat),
            shuttle_20m_s=shuttle,
            # ⚠️ 一律留 NULL：那一列在生产路径上没有写入方，也不再有读者
            normalized_score=None,
            tested_on=SEMESTER_START + dt.timedelta(weeks=week - 1),
            entered_by=TEACHER_STAFF_NO,
        ))
        s.commit()


def _run(engine, ids, as_of: D, *, rules=None, channel=None, now=NOW):
    """跑一次预警阶段，返回 ``(AlertReport, Session)``。

    ⚠️ **会话留给调用方关**：断言要在同一个会话里读库（内存库 + 用完即关的纪律）。
    """
    session = Session(engine)
    report = evaluate_alerts(
        session, ids["semester"], ids["batch"], as_of,
        rules=alert_rules() if rules is None else rules,
        exercises=exercise_library(),
        now=now,
        channel=channel,
    )
    session.commit()
    return report, session


def _alerts(session, rule_id=None) -> list:
    stmt = select(Alert).order_by(Alert.id)
    if rule_id is not None:
        stmt = stmt.where(Alert.rule_id == rule_id)
    return list(session.scalars(stmt))


def _adjustments(session) -> list:
    return list(session.scalars(select(WeeklyAdjustment).order_by(WeeklyAdjustment.id)))


def _notifications(session) -> list:
    return list(session.scalars(select(Notification).order_by(Notification.id)))


def _three_nines(engine, ids, student_id, days=(D(2025, 9, 1), D(2025, 9, 2),
                                               D(2025, 9, 3))) -> list:
    """连续三节课各交一次 ``rpe = 9``（= 阈值），返回三个 ``class_session_id``（升序）。"""
    out = []
    for index, day in enumerate(days):
        cs = _session_at(engine, day, period=3, ids=ids)
        _rpe(engine, cs, student_id, 9, T(day.year, day.month, day.day, 10, 0))
        out.append(cs)
    return out


def _rules_with(rule_id: RuleId, **params) -> AlertRules:
    """生产那份 YAML 的一个**改过阈值**的副本（支 C 的「换一套参数再跑一遍」）。

    ⚠️ 只改点名的那一条规则的 ``params``，其余原样；``version`` 也原样
    （它进 ``trigger_snapshot``，与判据无关）。
    """
    base = alert_rules()
    store = {}
    for rid, rule in base.rules.items():
        if rid is rule_id:
            rule = AlertRule(rule_id=rid, level=rule.level, scope=rule.scope,
                             params={**rule.params, **params})
        store[rid] = rule
    return AlertRules(version=base.version, rules=store)


# ===========================================================================
# 支 A：Review Focus 第 3 条 —— 同一次触发只落一条 alert、只减一次量
# ===========================================================================


def test_the_same_trigger_raises_one_alert_not_three(engine):
    """**Review Focus 第 3 条的正身**：streak 从 3 长到 4，仍然只有 1 条 alert、1 条调整。

    失效形态逐字照 ``app/domain/alerts.py`` 的模块 docstring：若 ``window_key`` 锚在
    **最后一次**快评上，第 3、4 次触发会得到两个不同的键 → 两行 ``alert`` →
    两条 ``weekly_adjustment(factor=0.8)``，而「本周训练单」是该周全部 factor 的
    **累乘**，于是那一周的量变成 ``0.64``，且全链路不报错。

    ⚠️ 四天全落在**处方第 1 周**（09-01 至 09-04），故 ``week`` 也相同——
    这才能同时验到两道闸门（``alert`` 的四列唯一键、``weekly_adjustment`` 的四列唯一键）。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _three_nines(engine, ids, student_id)

    first, session = _run(engine, ids, D(2025, 9, 3))
    assert first.raised >= 1
    red = _alerts(session, "RED_RPE_SUSTAINED")
    assert len(red) == 1
    # 锚点是**凑满 streak 那一次**的课次 id（domain 取 rpe_session_ids[streak-1]）
    assert red[0].window_key.startswith("rpe")
    assert len(_adjustments(session)) == 1

    # 第 4 节课（仍在处方第 1 周内），streak 变 4
    cs4 = _session_at(engine, D(2025, 9, 4), period=3, ids=ids)
    _rpe(engine, cs4, student_id, 9, T(2025, 9, 4, 10, 0))
    second, session2 = _run(engine, ids, D(2025, 9, 4))
    session.close()

    assert second.deduped >= 1, "撞上去重键的那一次必须计入 deduped，否则它不可观测"
    red2 = _alerts(session2, "RED_RPE_SUSTAINED")
    assert len(red2) == 1, "同一次「连续 ≥ 9」触发了两行 alert"
    assert red2[0].id == red[0].id
    rows = _adjustments(session2)
    assert len(rows) == 1, "同一周被减了两次量（连乘成 0.64）"
    assert rows[0].factor == 0.8
    session2.close()


def test_running_the_same_day_twice_does_not_duplicate_anything(engine):
    """**同一天跑两遍**（没有重放清理）：第二遍 ``raised = 0``、库里行数不变。

    ⚠️ 这一条与上面那条钉的是**不同的**失效：上面那条靠 ``window_key`` 的锚点稳定，
    这一条连锚点都不动（同一批输入），故它专门盯「先 SELECT 后 INSERT」那一段——
    谁把它换成 :func:`app.db.repo.upsert`，第二遍就会走**更新分支**，把一条已经
    ``handled`` 的预警静默改回 ``pending``（教师处置过的痕迹消失）。
    """
    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    first, session = _run(engine, ids, D(2025, 9, 3))
    session.close()
    # 教师处置过它：第二遍若走 upsert 的更新分支，这个 status 会被改回 pending
    with Session(engine) as s:
        row = s.scalars(select(Alert).where(Alert.rule_id == "RED_RPE_SUSTAINED")).one()
        row.status = ALERT_HANDLED
        row.handled_action = "reduce_20pct"
        row.handled_at = NOW
        s.commit()
        handled_id = row.id

    second, session = _run(engine, ids, D(2025, 9, 3))
    assert second.raised == 0
    assert second.deduped >= 1
    kept = session.scalars(select(Alert).where(Alert.rule_id == "RED_RPE_SUSTAINED")).all()
    assert len(kept) == 1
    assert kept[0].id == handled_id
    assert kept[0].status == ALERT_HANDLED, "处置痕迹被一次重跑抹掉了"
    assert kept[0].handled_action == "reduce_20pct"
    assert len(_adjustments(session)) == 1
    session.close()


def test_a_late_submission_does_not_move_the_window_key_anchor(engine):
    """**P7-A3 第 2 条**：``rpe_session_ids`` 必须按**课次时间**升序，不是按提交时刻。

    失效序列（本条钉的就是它）：``submit_rpe`` **刻意不做过期**，故一节早先的课可以在
    一节晚近的课**之后**才被提交。若排序键是 ``submitted_at``，那一节的记录会被排到
    元组**末尾**，于是 ``[streak - 1]`` 锚到另一次快评上 → ``window_key`` 变 →
    同一次「连续 ≥ 9」第二次落库 → 连乘回来。

    ⚠️ 数据刻意造成「课次时间序 ≠ 提交时刻序」：09-01 与 09-03 当场交，
    **09-02 那节课在 09-03 之后才补交**。两种排序于是给出两个不同的锚点：

    * 按课次时间 ``[S1, S2, S3]`` → ``[streak-1]`` = ``S3``（**正确**）；
    * 按提交时刻 ``[S1, S3, S2]`` → ``[streak-1]`` = ``S2``（错，且随一次补交而移动）。

    ⚠️ 期望侧是**字面**的 ``f"rpe{cs3}"``（那一节课的 id 由夹具返回、不是从被测代码读回），
    故把 ``ORDER BY`` 改成 ``submitted_at`` 会让本条红。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    cs1 = _session_at(engine, D(2025, 9, 1), period=3, ids=ids)
    cs2 = _session_at(engine, D(2025, 9, 2), period=3, ids=ids)
    cs3 = _session_at(engine, D(2025, 9, 3), period=3, ids=ids)
    _rpe(engine, cs1, student_id, 9, T(2025, 9, 1, 10, 0))
    _rpe(engine, cs3, student_id, 9, T(2025, 9, 3, 10, 0))
    # ⚠️ 09-02 那节课**迟到**：提交时刻晚于 09-03 那一次
    _rpe(engine, cs2, student_id, 9, T(2025, 9, 4, 23, 0))

    _report, session = _run(engine, ids, D(2025, 9, 4))
    red = _alerts(session, "RED_RPE_SUSTAINED")
    assert len(red) == 1
    assert red[0].window_key == f"rpe{cs3}", (
        f"锚点是 {red[0].window_key}，而它应当是**课次时间**上第 3 次那节课（rpe{cs3}）："
        f"排序键用的是 submitted_at 而不是课次时间，于是同一次触发会落第二条 alert、"
        f"并再减一次量（Review Focus 第 3 条）"
    )
    session.close()


# ===========================================================================
# 支 B：weekly_adjustment 的 auto 来源（Plan 02 留给 Plan 03 的第 2 条）
# ===========================================================================


def test_a_red_alert_writes_an_auto_adjustment_of_0_8(engine):
    """``RED_RPE_SUSTAINED`` → 一条 ``source="auto"`` / ``factor=0.8`` 的调整（spec §8.4）。

    ⚠️ **这是 ``"auto"`` 在本仓的第一个生产写入方**：Plan 02 Task 6 建表时逐字写下
    「``"auto"`` 今天没有生产写入方，它进 ``SOURCES`` 是为了与 Plan 03 的写入方一次对齐」。
    """
    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    report, session = _run(engine, ids, D(2025, 9, 3))
    rows = _adjustments(session)
    assert report.adjustments_written == 1
    assert len(rows) == 1
    row = rows[0]
    assert row.prescription_id == ids["prescription"]
    assert row.source == "auto"
    assert row.factor == 0.8
    # reason 是**裸的 rule_id**：它是四列唯一约束的一列，故必须稳定（见下一条）
    assert row.reason == "RED_RPE_SUSTAINED"
    # 09-03 是处方第 1 周（generated_on = 09-01）
    assert row.week == 1
    assert row.batch_id == ids["batch"]
    assert row.created_at == NOW
    session.close()


def test_the_reason_carries_no_version_so_the_unique_key_stays_stable(engine):
    """``reason`` **不带 YAML 版本号**，而版本号落在 ``alert.trigger_snapshot`` 里。

    ⚠️ 这是对 ``app/domain/alerts.py`` 模块 docstring 那一句（「Task 7 把 version 写进
    weekly_adjustment 的 auto 来源留痕」）的一处**有意偏离**，本条是它的守卫：
    ``reason`` 是 ``uq_weekly_adjustment_prescription_week_reason_source`` 的一列，
    把版本拼进去会让「专家升一次版本号」等价于「同一周可以再减一次量」→ ``0.64``，
    而 Review Focus 第 3 条要防的连乘就从版本号那一侧回来了。
    """
    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    _report, session = _run(engine, ids, D(2025, 9, 3))
    row = _adjustments(session)[0]
    assert "@" not in row.reason and "v" != row.reason[:1]
    assert row.reason == "RED_RPE_SUSTAINED"

    alert = session.scalars(select(Alert).where(
        Alert.rule_id == "RED_RPE_SUSTAINED")).one()
    # 版本号改在快照里留痕：预警行与调整行是同一次触发的两半，故仍然可以离线复核
    assert alert.trigger_snapshot["alert_rules_version"] == "1.0"
    assert alert.trigger_snapshot["prescription_expired"] is False
    # 09-03 在学期第 1 周（开学日 09-01，一周 = 09-01..09-07）
    assert alert.trigger_snapshot["semester_week"] == 1
    session.close()


def test_a_red_minitest_drop_also_writes_an_auto_adjustment(engine):
    """第二条红色规则（``RED_MINITEST_DROP``）走同一条写入路径。

    三次小测 100 → 90 → 80：每次严格低于上一次的 95%（``90 < 95``、``80 < 85.5``），
    且恰好 3 个数据点（``points_needed``）。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _mini(engine, ids, student_id, 2, score=100.0)
    _mini(engine, ids, student_id, 4, score=90.0)
    _mini(engine, ids, student_id, 6, score=80.0)

    report, session = _run(engine, ids, D(2025, 9, 15))
    drops = _alerts(session, "RED_MINITEST_DROP")
    assert len(drops) == 1
    # 锚点是**最后一次**小测的 id（domain 刻意用另一套口径：一次新小测是一次新的观测窗口）
    assert drops[0].window_key.startswith("mt")
    rows = _adjustments(session)
    assert report.adjustments_written == 1
    assert len(rows) == 1
    assert rows[0].reason == "RED_MINITEST_DROP"
    assert rows[0].factor == 0.8
    assert rows[0].source == "auto"
    session.close()


def test_no_adjustment_when_the_prescription_has_expired(engine):
    """处方已到期 → **不写**调整，只在 ``trigger_snapshot`` 里留痕。

    简报 Task 7「决定」第 3 条的理由：给一张已到期的处方写「本周减量」没有意义，
    而 spec §5.2 的触发 3 会在同一天生成新处方。
    ⚠️ 09-29 是 ``generated_on + 28 天`` → ``current_week`` 返回 ``None``
    （``week = 5 > microcycle_weeks = 4``），正是触发 3 该开火的那一天。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _three_nines(engine, ids, student_id,
                 days=(D(2025, 9, 27), D(2025, 9, 28), D(2025, 9, 29)))

    report, session = _run(engine, ids, D(2025, 9, 29))
    red = _alerts(session, "RED_RPE_SUSTAINED")
    assert len(red) == 1, "预警本身照落：到期只影响『要不要减量』，不影响『要不要报』"
    assert red[0].trigger_snapshot["prescription_expired"] is True
    assert _adjustments(session) == []
    assert report.adjustments_written == 0
    session.close()


def test_the_auto_factor_passes_through_weekly_factor_validation(engine, monkeypatch):
    """**变异靶子**（Plan 02 留给 Plan 03 的第 4 条）：把系数改成 ``0.0`` → 本条红。

    ``weekly_adjustment.factor`` 那一列**刻意没有 CHECK**（P8-A6：``(0, 2]`` 是读模型的
    语义、不是数据的形状），故 :class:`~app.domain.prescription.weekly.WeeklyFactor`
    的 ``__post_init__`` 是写入侧**唯一**的闸门。少了「先构造值对象再落库」这一步，
    一个 ``factor = 0`` 会静默落库，然后让学生端打开训练单时在
    :func:`~app.pipeline.prescription_stage.weekly_factors_of` 里抛 ``ValueError`` → 500
    （Plan 02 Task 8 的关切 1 逐字就是这个形状）。
    """
    monkeypatch.setattr(stage, "AUTO_REDUCTION_FACTOR", 0.0)
    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    with pytest.raises(ValueError) as excinfo:
        _run(engine, ids, D(2025, 9, 3))
    assert "WeeklyFactor.factor" in str(excinfo.value)
    with Session(engine) as s:
        assert _adjustments(s) == [], "一个非法系数落库了（值对象那道闸门没生效）"


def test_a_duplicate_auto_adjustment_is_rejected_by_the_db_not_silently_updated(
    engine, monkeypatch
):
    """撞 ``uq_weekly_adjustment_prescription_week_reason_source`` → **DB 当裁判**。

    ⚠️ 这一条钉的是派单逐字点名的那个坑：:func:`app.db.repo.upsert` 撞键时**不抛异常**，
    它走更新分支、把 ``factor`` / ``batch_id`` / ``created_at`` 三个非键列 ``setattr`` 到
    **已有的那一行**上并返回它。于是「一次本该被拒绝的重复写入」变成「静默改掉一条
    已经生效的调整」——而 ``created_at`` 正是
    :func:`~app.pipeline.prescription_stage.weekly_factors_of` 的排序键，改它会让同一周上
    多条调整的**相乘顺序**跟着变。

    故本模块用裸 INSERT + 自己的 SAVEPOINT，撞键只回滚那一个 SAVEPOINT。
    断言的三件事：① 不抛；② 库里仍是一行；③ **已有那一行的三个非键列一个都没被改**。

    ⚠️⚠️ **那个 ``monkeypatch`` 是承重的**（Plan 03 全分支终审之后加的第四道闸门带来的
    连带）：:func:`app.pipeline.alert_stage._auto_adjustment_exists` 现在会在 INSERT 之前
    先按 ``(prescription_id, week, source='auto')`` 查一遍，单进程里本条这一档**到不了**
    ``IntegrityError``（它会被那道 SELECT 先挡下，于是本条测的其实是 SELECT、
    名字里那句「by the db」成了假绿）。把它 patch 成恒 ``False`` 就是在**模拟并发**：
    两个进程同时 SELECT、都没看见对方，然后都去 INSERT——那正是第三道闸门
    （SAVEPOINT + ``IntegrityError``）今天唯一还挡得住的一档，也是它**不能被删掉**的理由。
    """
    monkeypatch.setattr(stage, "_auto_adjustment_exists", lambda *a, **k: False)
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # 先手工插一条同 (prescription, week, reason, source) 的调整，带一个可辨认的时刻
    # 与**另一个真实存在的**批次（batch_id 是 NOT NULL 外键，编一个 999 会当场 FK 违例）
    marker = T(2020, 1, 1, 0, 0)
    with Session(engine) as s:
        other = M.DailySyncRun(semester_id=ids["semester"], business_date=D(2025, 9, 2),
                               status="success")
        s.add(other)
        s.flush()
        other_batch = other.id
        s.add(WeeklyAdjustment(prescription_id=ids["prescription"], batch_id=other_batch,
                               week=1, factor=0.9, reason="RED_RPE_SUSTAINED",
                               source="auto", created_at=marker))
        s.commit()

    _three_nines(engine, ids, student_id)
    report, session = _run(engine, ids, D(2025, 9, 3))

    assert report.adjustments_written == 0, "撞键的那一次不该计入『新写』"
    rows = _adjustments(session)
    assert len(rows) == 1, "同一处方同一周同一原因同一来源写出了第二条 auto 调整"
    assert rows[0].factor == 0.9, "已有那一行被静默改掉了（upsert 的更新分支）"
    assert rows[0].created_at == marker
    assert rows[0].batch_id == other_batch
    # 而预警本身照落（去重是两张表各自的事）
    assert len(_alerts(session, "RED_RPE_SUSTAINED")) == 1
    session.close()


def test_two_different_red_rules_in_the_same_week_reduce_once_not_twice(engine):
    """**C1（Plan 03 全分支终审的 Critical，用户 2026-10-08 裁定选 A）**：
    两条**不同**的红色规则在同一个处方周同时命中 → **只减一次**，本周训练单的
    ``factor`` 是 ``0.8``、不是 ``0.8 × 0.8 = 0.6400000000000001``。

    失效形态逐字照终审的复现：``weekly_adjustment`` 落下**两行**
    （``reason=RED_MINITEST_DROP`` 与 ``reason=RED_RPE_SUSTAINED``，都是 ``source='auto'``），
    而全链路**没有一处报错**——那个四列唯一约束
    ``uq_weekly_adjustment_prescription_week_reason_source`` 把 ``reason`` 也放进键里，
    故「两条不同规则各写一行」在它看来是两行不同的数据。而 spec §8.4 逐字是「减量 20%」。

    ⚠️ 断言的四格各挡一个「修法」：

    ① **``adjustments_written == 1``** —— 挡住「写了两行但只报了一行」；
    ② **``weekly_adjustment`` 只有一行** —— 挡住「多写一行然后读侧只取一条」
       （那会让库里的数据与 spec 不符，而 RCT 要拿它当过程数据）；
    ③ **``weekly_training_sheet(...).factor == 0.8``** —— 这一格是**学生真的看到的数**，
       它走的是生产读侧那一条链（``effective_package`` → ``weekly_factors_of`` →
       ``weekly_training_sheet``），故①②都对而③错也照样红；
    ④ **``alert`` 表仍有那两条红色预警的行** —— 挡住「顺手把第二条预警也吞了」：
       可追溯性不能因为「只减一次」而丢，教师端要能看到两条预警。
       （本条同时把命中的规则清单**字面写死**，于是「别的规则被顺手带出来」也会红。）

    ⚠️ ``reason`` 记的是**第一条**命中的规则：:class:`~app.domain.alerts.RuleId` 的
    声明序里 ``RED_MINITEST_DROP`` 在 ``RED_RPE_SUSTAINED`` 之前，而
    :func:`~app.domain.alerts.evaluate_student` 按声明序返回，故「第一条」是它。
    本条把那个名字**字面写死**（硬规矩 #35）：声明序一旦被翻，本条会红，
    而那正是需要有人过目一眼的改动（它会改掉演示库里那一行的 ``reason``）。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # RED_RPE_SUSTAINED：连续三节课各交一次 rpe = 9（09-01 / 09-02 / 09-03）
    _three_nines(engine, ids, student_id)
    # RED_MINITEST_DROP：三次小测 100 → 90 → 80（每次严格低于上一次的 95%）
    _mini(engine, ids, student_id, 2, score=100.0)
    _mini(engine, ids, student_id, 4, score=90.0)
    _mini(engine, ids, student_id, 6, score=80.0)

    # 09-15 → current_week(generated_on=09-01, as_of=09-15, microcycle=4) == 3，
    # 两条规则命中的是**同一个处方周**（那一周的量因此会被连乘）。
    report, session = _run(engine, ids, D(2025, 9, 15))

    # ④ 两条预警都落库：可追溯性不丢
    assert len(_alerts(session, "RED_MINITEST_DROP")) == 1
    assert len(_alerts(session, "RED_RPE_SUSTAINED")) == 1
    student_level = sorted(a.rule_id for a in _alerts(session)
                           if a.student_id is not None)
    # ⚠️ 第三条 ``YELLOW_CHECKIN_GAP`` 是**预期的**：本条刻意不造任何 ``training_log``，
    #    于是「连续 2 个应打卡训练日未打卡」当然成立。它是黄色规则、**不写**
    #    ``weekly_adjustment``（只有 ``AlertLevel.RED`` 那一支写），故与连乘无关。
    #    把三条**字面写死**（硬规矩 #35）：这一格因此同时钉住「别的规则没被顺手带出来」。
    assert student_level == [
        "RED_MINITEST_DROP", "RED_RPE_SUSTAINED", "YELLOW_CHECKIN_GAP",
    ]

    # ①② 只减一次
    assert report.adjustments_written == 1
    rows = _adjustments(session)
    assert len(rows) == 1, "两条不同的红色规则在同一处方周各写了一行 auto 调整"
    assert rows[0].source == "auto"
    assert rows[0].factor == 0.8
    assert rows[0].week == 3
    assert rows[0].reason == "RED_MINITEST_DROP"

    # ③ 学生真的看到的那个数
    prescription = session.get(Prescription, ids["prescription"])
    factors = weekly_factors_of(session, prescription.id)
    assert len(factors) == 1
    sheet = weekly_training_sheet(
        effective_package(prescription, exercises=exercise_library()), 3, factors
    )
    assert sheet.factor == 0.8, (
        f"本周训练单的 factor 是 {sheet.factor}（两条红色规则各减了一次 → 0.64），"
        f"而 spec §8.4 逐字是「减量 20%」"
    )
    assert sheet.reasons == ("RED_MINITEST_DROP",)
    assert sheet.sources == ("auto",)
    session.close()


def test_the_status_and_source_constants_are_inside_the_model_value_domains():
    """四个字符串常量都在模型类常量的值域内（两侧不同源，硬规矩 #35）。

    ⚠️ 期望侧是 :attr:`Alert.STATUSES` / :attr:`WeeklyAdjustment.SOURCES`（DB 的 CHECK
    就是从它们生成的），被测侧是 ``app.pipeline.alert_stage`` 的常量。
    抄第二份字面串的话，改词表只改一处、另一处静默写不进库。
    """
    assert {ALERT_PENDING, ALERT_HANDLED, ALERT_IGNORED} == Alert.STATUSES
    assert ALERT_PENDING == "pending"
    assert ALERT_HANDLED == "handled"
    assert ALERT_IGNORED == "ignored"
    assert AUTO_SOURCE in WeeklyAdjustment.SOURCES
    assert AUTO_SOURCE == "auto"
    assert AUTO_REDUCTION_FACTOR == 0.8


# ===========================================================================
# 支 C：P7-A3 的 6 条关切
# ===========================================================================


def test_the_skip_traces_are_consumed_not_just_computed(engine):
    """**P7-A3 第 1 条**：``student_skip_traces`` / ``class_skip_traces`` 有消费者。

    Task 6 交付了这两个函数并逐字交代「留痕的消费者是 Task 7，本模块只负责算出它」。
    不读它们就是死配置（与 Plan 02 的 ``Intensity.rpe`` 同型），而「这个学生这周为什么
    没有预警」就仍然无从回答。

    ⚠️ 判据是**计数**，不是「函数被调用过」：一个学生一次小测都没做 →
    ``RED_MINITEST_DROP`` 的留痕是 ``insufficient_points``；一个班本周一次快评都没有 →
    ``YELLOW_CLASS_RPE_HIGH`` 的留痕同样是 ``insufficient_points: 0``。
    两者都必须出现在 :attr:`AlertReport.skipped` 里。
    """
    ids = _seed(engine)
    # 只给一条打卡（于是他进了人群），不给小测、不给快评
    _log(engine, ids[STUDENT_NO], D(2025, 9, 1))

    report, session = _run(engine, ids, D(2025, 9, 3))
    assert report.skipped.get("RED_MINITEST_DROP") == 1, (
        "一个学生一次小测都没做，RED_MINITEST_DROP 必须留下 insufficient_points 的痕"
    )
    assert report.skipped.get("YELLOW_CLASS_RPE_HIGH") == 1, (
        "一个班本周一次快评都没有，那一档必须留痕（「没测」不得讲成「测了且没问题」）"
    )
    # ⚠️ 留痕 ≠ 命中：这一条规则一条 alert 都不该有
    assert _alerts(session, "RED_MINITEST_DROP") == []
    assert _alerts(session, "YELLOW_CLASS_RPE_HIGH") == []
    session.close()


def test_the_skip_traces_reach_the_log_line(engine, caplog):
    """:attr:`AlertReport.skipped` 也进**日志**（P7-A3 第 1 条要求的第二个落点）。"""
    import logging

    ids = _seed(engine)
    _log(engine, ids[STUDENT_NO], D(2025, 9, 1))
    with caplog.at_level(logging.INFO, logger="app.pipeline.alert_stage"):
        _report, session = _run(engine, ids, D(2025, 9, 3))
        session.close()
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "RED_MINITEST_DROP" in text
    assert "判不了" in text


def test_rpe_min_comes_from_the_rules_not_from_a_literal(engine):
    """**P7-A3 第 3 条（前半）**：``rpe_min`` 那个 9 由本 Task 消费。

    domain 拿到的是**已经算好的** ``rpe_streak``，故它无从校验这个阈值被用对了
    （:func:`app.domain.alerts._rpe_sustained` 的 docstring 逐字把消费者点名给本模块）。
    ⚠️ 判据是「换一套阈值，行为跟着变」：把 ``rpe_min`` 降到 5，一个 ``rpe = 6`` 的
    streak 就该触发；生产那份（9）下它不触发。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    for index, day in enumerate((D(2025, 9, 1), D(2025, 9, 2), D(2025, 9, 3))):
        cs = _session_at(engine, day, period=3, ids=ids)
        _rpe(engine, cs, student_id, 6, T(day.year, day.month, day.day, 10, 0))

    _report, session = _run(engine, ids, D(2025, 9, 3))
    assert _alerts(session, "RED_RPE_SUSTAINED") == [], "rpe=6 在生产阈值 9 下不该触发"
    session.close()

    loose = _rules_with(RuleId.RED_RPE_SUSTAINED, rpe_min=5.0)
    _report, session = _run(engine, ids, D(2025, 9, 3), rules=loose)
    assert len(_alerts(session, "RED_RPE_SUSTAINED")) == 1, (
        "把 rpe_min 降到 5 之后 rpe=6 仍然不触发 → 那个阈值没有被读（死配置）"
    )
    session.close()


def test_improve_pct_comes_from_the_rules_not_from_a_literal(engine):
    """**P7-A3 第 3 条（后半）**：``improve_pct`` 那个 3% 由本 Task 消费。

    ``GREEN_MASTERY`` = 完成率 100% **AND** 二次小测提升，而「提升 ≥ 3%」的判定
    发生在 :func:`app.pipeline.alert_stage._mini_test_improved` 里（domain 拿到的是
    已经算好的布尔值）。⚠️ 一个 ``+2%`` 的进步在生产阈值下**不算**提升，
    把阈值降到 ``0.01`` 之后就算——两侧都断言，才排得出「这个数被读过」。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # 两次小测：100 → 102（+2%）
    _mini(engine, ids, student_id, 2, score=100.0)
    _mini(engine, ids, student_id, 4, score=102.0)
    # 处方第 1 周的两个训练日都打了卡（09-01 / 09-02）→ 完成率 1.0
    _log(engine, student_id, D(2025, 9, 1))
    _log(engine, student_id, D(2025, 9, 2))

    _report, session = _run(engine, ids, D(2025, 9, 3))
    assert _alerts(session, "GREEN_MASTERY") == [], "+2% 在生产阈值 3% 下不算提升"
    session.close()

    loose = _rules_with(RuleId.GREEN_MASTERY, improve_pct=0.01)
    _report, session = _run(engine, ids, D(2025, 9, 3), rules=loose)
    green = _alerts(session, "GREEN_MASTERY")
    assert len(green) == 1, "把 improve_pct 降到 1% 之后仍然不触发 → 那个阈值没有被读"
    assert green[0].trigger_snapshot["completion_rate"] == 1.0
    assert green[0].trigger_snapshot["mini_test_improved"] is True
    assert _adjustments(session) == [], "绿牌是正向激励，绝不改训练量"
    session.close()


def test_the_completion_rate_never_exceeds_one(engine):
    """**P7-A3 第 4 条**：完成率夹在 ``[0, 1]``。

    ⚠️ Task 6 顶回 6 那条等价性论证（``>= 1.0`` ≡ ``== 1.0``）**建立在比率不超过 1 之上**，
    越界会让它不再等价（一个 ``1.2`` 会触发而 ``==`` 不会）。
    本条造一个「在**非训练日**也打了卡」的学生，让那个交集**真的**做功：
    分子若不经交集就会是 4、分母是 2 → 比率 2.0。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _mini(engine, ids, student_id, 2, score=100.0)
    _mini(engine, ids, student_id, 4, score=120.0)  # +20% ≫ 3%
    # 处方第 1 周只有 09-01 / 09-02 两个训练日；另外两天是**非**训练日
    for day in (D(2025, 9, 1), D(2025, 9, 2), D(2025, 9, 4), D(2025, 9, 5)):
        _log(engine, student_id, day)

    _report, session = _run(engine, ids, D(2025, 9, 5))
    green = _alerts(session, "GREEN_MASTERY")
    assert len(green) == 1
    rate = green[0].trigger_snapshot["completion_rate"]
    assert 0.0 <= rate <= 1.0, f"完成率越界：{rate}"
    assert rate == 1.0
    session.close()


def test_the_completion_rate_numerator_uses_the_same_four_conditions_as_the_endpoint():
    """**四个条件逐条钉住**，口径与 ``app/api/routers/feedback.py`` 的完成率端点相同。

    ⚠️⚠️ **那四个条件有两个所有者**（本条存在的全部理由）：一份在这里、一份在
    :func:`app.api.routers.feedback.completion_rate` 的分子里。两处**并存而不合并**，
    处置照 :class:`app.domain.alerts.AlertLevel` 与 :attr:`Alert.LEVELS` 的先例
    （那一对也是两份并存、由一条测试钉成逐字相等）：那一处住在 ``app/api/``，
    本模块反向 import 不到，而它是端点响应体的算法本体、抽出来会让端点读不懂。
    **改其中一处而不改另一处，本条与端点那一条会给出两个互相矛盾的完成率。**

    四个条件各造一行违例（``late`` / ``is_rest_day`` / 补卡 / 未完成），
    只有第一行计入。
    """
    day = D(2025, 9, 1)
    ok = TrainingLog(student_id=1, log_date=day, submitted_at=T(2025, 9, 1, 9, 0),
                     completed=True, is_rest_day=False, late=False, source="checkin")
    late = TrainingLog(student_id=1, log_date=D(2025, 9, 2),
                       submitted_at=T(2025, 9, 2, 22, 5), completed=True,
                       is_rest_day=False, late=True, source="checkin")
    rest = TrainingLog(student_id=1, log_date=D(2025, 9, 3),
                       submitted_at=T(2025, 9, 3, 9, 0), completed=True,
                       is_rest_day=True, late=False, source="checkin")
    backfill = TrainingLog(student_id=1, log_date=D(2025, 9, 4),
                           submitted_at=T(2025, 9, 6, 21, 0), completed=True,
                           is_rest_day=False, late=False, source="checkin")
    not_done = TrainingLog(student_id=1, log_date=D(2025, 9, 5),
                           submitted_at=T(2025, 9, 5, 9, 0), completed=False,
                           is_rest_day=False, late=False, source="checkin")

    assert _counted_checkin_days([ok, late, rest, backfill, not_done]) == {day}


def test_checkin_gap_uses_the_looser_reported_definition(engine):
    """中断那一档**刻意**用另一套口径：一个 22:40 才交卡的学生不算「失联」。

    理由逐字见 :func:`app.pipeline.alert_stage._reported_checkin_days` 的 docstring：
    补练提醒是**自动发给学生本人**的（spec §8.2「自动发『补练提醒』，无需教师介入」），
    没有教师能拦下它，而对他说明明交了的卡「你连续 2 天没打卡」是一句当面撒谎。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # 处方第 1 周的两个训练日都**迟交**了（late=True）
    _log(engine, student_id, D(2025, 9, 1), late=True,
         submitted_at=T(2025, 9, 1, 22, 40))
    _log(engine, student_id, D(2025, 9, 2), late=True,
         submitted_at=T(2025, 9, 2, 22, 40))

    _report, session = _run(engine, ids, D(2025, 9, 3))
    assert _alerts(session, "YELLOW_CHECKIN_GAP") == [], (
        "两天都报了到（只是迟了），不该被讲成「打卡中断」"
    )
    session.close()


def test_the_gap_anchor_is_the_day_the_gap_reached_the_threshold(engine):
    """中断的 ``window_key`` 锚在「凑满 ``gap_days`` 那一天」，不是中断的最后一天。

    ⚠️ 与 domain 给 ``RED_RPE_SUSTAINED`` 选 ``rpe_session_ids[streak - 1]`` 是同一条判断：
    字面读法（「那段中断的**结束日**」）会让键**天天变**，于是一个 5 天的中断落 4 条
    alert——Review Focus 第 3 条要防的形状从打卡这一侧回来了。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # 09-01 打了卡（进人群），之后 09-02 / 09-08 / 09-09 三个训练日都没打
    _log(engine, student_id, D(2025, 9, 1))

    _report, session = _run(engine, ids, D(2025, 9, 2))
    gaps = _alerts(session, "YELLOW_CHECKIN_GAP")
    assert len(gaps) == 0, "只中断了 1 个训练日，阈值是 2"
    session.close()

    _report, session = _run(engine, ids, D(2025, 9, 9))
    gaps = _alerts(session, "YELLOW_CHECKIN_GAP")
    assert len(gaps) == 1
    # 中断的训练日升序是 09-02 / 09-08 / 09-09，凑满 2 天那一天是 09-08
    assert gaps[0].window_key == "gap2025-09-08"
    session.close()


def test_params_of_has_a_production_caller():
    """**P7-A3 第 6 条**：``AlertRules.params_of`` 不再是「今天没有生产调用者」。

    ⚠️ AST 口径（硬规矩 #89 再扩写：数「一个名字有几处调用」用 AST，不用正则数源码）。
    期望侧是**字面**的「至少一处、且其中一处在 ``alert_stage.py``」，
    不从被测模块反推。⚠️ ``app/domain/alerts.py`` 里那一处是**定义**，不计入。
    """
    callers = []
    for py in sorted((BACKEND / "app").rglob("*.py")):
        if py.name == "alerts.py" and py.parent.name == "domain":
            continue  # 定义所在的那一份
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "params_of"):
                callers.append(py.relative_to(BACKEND).as_posix())
    assert callers, "params_of 在生产代码里仍然没有调用者（死配置）"
    assert "app/pipeline/alert_stage.py" in callers


def test_training_days_of_has_exactly_one_definition():
    """**P7-A3 第 5 条**：「哪几天是应打卡训练日」全仓只有**一份定义**。

    ⚠️ AST 口径（硬规矩 #89 再扩写：数「一个名字有几份定义」用 AST）。
    它原先是 ``app/api/routers/feedback.py`` 的私有 ``_training_days_of``，而
    ``alert_stage`` 住在 ``app/pipeline/``、反向 import ``app.api`` 被守卫禁止，
    故 Task 7 把它搬到了 :mod:`app.pipeline.prescription_stage`。
    **搬家之后旧的那一份必须真的消失**——留一个平行的副本就是第二个所有者，
    而两份「处方周起点 + day − 1」的算式漂了之后，教师端看到的完成率与学生被预警的
    完成率就不是同一个口径了，且两边各自的测试都还是绿的。
    """
    definitions = []
    for py in sorted((BACKEND / "app").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in (
                "training_days_of", "_training_days_of"
            ):
                definitions.append(
                    (py.relative_to(BACKEND).as_posix(), node.name, node.lineno)
                )
    assert definitions == [
        ("app/pipeline/prescription_stage.py", "training_days_of", definitions[0][2])
    ], f"「应打卡训练日」有 {len(definitions)} 份定义: {definitions}"


def test_the_semester_week_helpers_agree_with_the_api_layer_one():
    """学期周次的两个方向与 ``app/api/routers/feedback.py`` 的那一份**逐字相等**。

    ⚠️ 两侧不同源（硬规矩 #35）：期望侧是 api 层的 :func:`_week_days`
    （它由 ``tests/api/test_feedback.py`` 的完成率那几条独立钉着），
    被测侧是本模块的 :func:`semester_week_of` / :func:`semester_week_range`。
    不合并的理由是分层（``pipeline`` 反向 import ``api`` 被守卫禁止），
    处置照 :class:`app.domain.alerts.AlertLevel` 与 :attr:`Alert.LEVELS` 的先例。
    """
    from app.api.routers.feedback import DAYS_PER_WEEK, _week_days

    assert DAYS_PER_WEEK == 7
    for week in range(1, 17):
        days = _week_days(SEMESTER_START, week)
        assert len(days) == 7
        first, last = semester_week_range(SEMESTER_START, week)
        assert (first, last) == (days[0], days[-1])
        for day in days:
            assert semester_week_of(SEMESTER_START, day) == week
    assert semester_week_of(SEMESTER_START, SEMESTER_START) == 1
    assert semester_week_of(SEMESTER_START, D(2025, 8, 31)) is None


# ===========================================================================
# 支 E：通知与异常分层
# ===========================================================================


def test_a_yellow_gap_sends_a_notification_automatically(engine):
    """``YELLOW_CHECKIN_GAP`` → **自动**发补练提醒给学生（spec §8.2 逐字「无需教师介入」）。"""
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _log(engine, student_id, D(2025, 9, 1))  # 进人群；09-02 起中断

    _report, session = _run(engine, ids, D(2025, 9, 9))
    notes = _notifications(session)
    gaps = _alerts(session, "YELLOW_CHECKIN_GAP")
    assert len(gaps) == 1
    reminder = [n for n in notes if n.title == "补练提醒"]
    assert len(reminder) == 1
    note = reminder[0]
    assert note.recipient_kind == "student"
    assert note.recipient_id == student_id
    assert note.channel == "in_app"
    assert note.alert_id == gaps[0].id
    assert note.is_read is False
    assert note.created_at == NOW
    session.close()


def test_a_red_alert_does_not_notify_until_the_teacher_acts(engine):
    """两条 ``RED_*`` **一条消息都不发**（spec §8.2 逐字「教师端弹『降量建议』→ 教师点击 →
    推送『减量 20%』」）。

    ⚠️ 而 ``weekly_adjustment`` 的 ``auto`` 行**是**自动写的：减量是系统对「练得太苦」的
    保护性动作（spec §8.4），推送是**告诉学生**这件事——后者要教师先看一眼，
    因为他可能知道一个系统不知道的理由（受伤了、这周月考）。
    """
    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    _report, session = _run(engine, ids, D(2025, 9, 3))
    red = _alerts(session, "RED_RPE_SUSTAINED")
    assert len(red) == 1
    assert len(_adjustments(session)) == 1, "减量是自动的（spec §8.4）"
    # ⚠️ 断言的是「**没有一条消息挂在那条红色预警上**」，不是「一条消息都没有」：
    #    同一批数据里 rpe=9 的课也会让班级均值 9.0 > 7.0 触发 YELLOW_CLASS_RPE_HIGH、
    #    而这个学生没打过卡也会触发 YELLOW_CHECKIN_GAP —— 两档黄色**都该发**消息。
    #    把断言写成「一条都没有」会让本条钉住一个错误的口径。
    assert [n for n in _notifications(session) if n.alert_id == red[0].id] == [], (
        "红色预警在教师处置前就推送了"
    )
    session.close()


def test_a_class_level_yellow_alert_goes_to_the_section_teacher(engine):
    """``YELLOW_CLASS_RPE_HIGH`` → 教师端提示（收件人是**该班的教师**，不是学生）。

    全班均值 8.0 > 7.0（严格大于；恰好 7.0 不触发，那是 domain 的判据）。
    """
    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    cs = _session_at(engine, D(2025, 9, 1), period=3, ids=ids)
    for student_no in (STUDENT_NO, OTHER_NO):
        _rpe(engine, cs, ids[student_no], 8, T(2025, 9, 1, 10, 0))
        # 两个人都把处方第 1 周的两个训练日打满：否则 YELLOW_CHECKIN_GAP 也会触发，
        # 于是 by_level["yellow"] 就不是 1、而本条要钉的是「班级级那一条」
        _log(engine, ids[student_no], D(2025, 9, 1))
        _log(engine, ids[student_no], D(2025, 9, 2))

    report, session = _run(engine, ids, D(2025, 9, 3))
    hits = _alerts(session, "YELLOW_CLASS_RPE_HIGH")
    assert len(hits) == 1
    assert hits[0].course_section_id == ids["section"]
    assert hits[0].student_id is None
    assert hits[0].subject_key == f"section:{ids['section']}"
    # 09-03 在学期第 1 周（开学日 09-01）→ window_key = semester_id:week
    assert hits[0].window_key == f"{ids['semester']}:1"
    assert hits[0].trigger_snapshot["mean_rpe"] == 8.0
    assert hits[0].trigger_snapshot["student_count"] == 2
    assert report.by_level.get("yellow") == 1, (
        "本条刻意让两个学生都打满卡，于是这一批**只有**班级级那一条黄牌"
    )

    notes = _notifications(session)
    assert len(notes) == 1
    assert notes[0].recipient_kind == "teacher"
    assert notes[0].recipient_id == ids["teacher"]
    assert _adjustments(session) == [], "班级级预警不改任何一个人的训练量"
    session.close()


def test_green_mastery_sends_a_badge_notification(engine):
    """``GREEN_MASTERY`` → 「生成电子勋章记录」，原型落地为一条站内消息（spec §8.3）。"""
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _mini(engine, ids, student_id, 2, score=100.0)
    _mini(engine, ids, student_id, 4, score=110.0)
    _log(engine, student_id, D(2025, 9, 1))
    _log(engine, student_id, D(2025, 9, 2))

    _report, session = _run(engine, ids, D(2025, 9, 3))
    green = _alerts(session, "GREEN_MASTERY")
    assert len(green) == 1
    assert green[0].level == "green"
    assert green[0].student_id == student_id
    badges = [n for n in _notifications(session) if n.title == "本周电子勋章"]
    assert len(badges) == 1
    assert badges[0].recipient_id == student_id
    assert badges[0].alert_id == green[0].id
    session.close()


def test_a_per_student_failure_does_not_roll_back_the_batch(engine, monkeypatch):
    """**异常分层第 1 档**：一个学生求值失败 → 计入 ``errors`` + 一条 warning，整批不回滚。

    ⚠️ 本阶段跑在 :func:`app.pipeline.daily.run_daily` 的 SAVEPOINT 里，故一个未捕获的
    异常会掀掉一整天的批处理（分层 + 快照 + 派生 + 处方）。口径逐字照
    :mod:`app.pipeline.prescription_stage` 的「异常分层」那一节。
    """
    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    # 两个人**共用**那三节课（一个教学班的课次就是一节课、全班各交一次快评；
    # 而 class_session 上有 (course_section_id, session_date, period) 的唯一约束，
    # 逐人各建一节会当场撞键）
    session_ids = []
    for day in (D(2025, 9, 1), D(2025, 9, 2), D(2025, 9, 3)):
        cs = _session_at(engine, day, period=3, ids=ids)
        session_ids.append(cs)
        for student_no in (STUDENT_NO, OTHER_NO):
            _rpe(engine, cs, ids[student_no], 9, T(day.year, day.month, day.day, 10, 0))

    real = stage.evaluate_student

    def boom(signals, rules):
        if signals.student_id == ids[STUDENT_NO]:
            raise ValueError("这个学生的三源数据里有脏行（测试注入）")
        return real(signals, rules)

    monkeypatch.setattr(stage, "evaluate_student", boom)
    report, session = _run(engine, ids, D(2025, 9, 3))

    assert report.errors == 1
    # 另一个人照常落库：整批没有回滚
    assert report.raised >= 1
    kept = _alerts(session, "RED_RPE_SUSTAINED")
    assert len(kept) == 1
    assert kept[0].student_id == ids[OTHER_NO]
    session.close()


def test_a_per_student_failure_writes_a_warning_line(engine, monkeypatch, caplog):
    """失败必须**留痕**（一条带学生 id / 异常类型 / 消息的 warning），不得静默跳过。"""
    import logging

    ids = _seed(engine)
    _three_nines(engine, ids, ids[STUDENT_NO])

    def boom(signals, rules):
        raise KeyError("normalized_score")

    monkeypatch.setattr(stage, "evaluate_student", boom)
    with caplog.at_level(logging.WARNING, logger="app.pipeline.alert_stage"):
        report, session = _run(engine, ids, D(2025, 9, 3))
        session.close()
    assert report.errors == 1
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert str(ids[STUDENT_NO]) in text
    assert "KeyError" in text


def test_a_date_before_the_semester_starts_yields_an_empty_report(engine, caplog):
    """``as_of`` 早于开学日 → 空报表 + 一条 warning（**不抛**）。

    :func:`app.pipeline.daily.run_daily` **不要求** ``business_date`` 落在
    ``semester_id`` 那个学期内（它的 docstring 逐字写了这件事），而预警的 ``week``
    是学期周次、``window_key`` 的一半就是它。故这一档是一次合法的重放历史日期，
    只是那一天没有「本周」可言。⚠️ ``alert_count = 0`` 在这一档的意思是「没跑」，
    不是「今天没有预警」——那条 warning 就是为了不让 0 被读成后者。
    """
    import logging

    ids = _seed(engine)
    with caplog.at_level(logging.WARNING, logger="app.pipeline.alert_stage"):
        report, session = _run(engine, ids, D(2025, 8, 31))
    assert report == AlertReport(raised=0, deduped=0, by_level={},
                                 adjustments_written=0, skipped={}, errors=0)
    assert _alerts(session) == []
    session.close()
    assert "早于学期" in "\n".join(r.getMessage() for r in caplog.records)


def test_a_batch_from_another_semester_is_rejected_loudly(engine):
    """接错批次 → 响亮失败（复用 :func:`_require_batch_in_semester`，不写第二份消息）。

    ⚠️ 那道校验挡的是接线错误：``_replay_cleanup`` 按 ``batch_id`` 删，接错批次会让
    重放删不到本批的预警行、于是翻倍（Plan 01 Ruling 32 的同源缺陷）。
    """
    ids = _seed(engine)
    with Session(engine) as s:
        other = Semester(name="2024-2025-2", start_date=D(2025, 2, 24),
                         end_date=D(2025, 6, 15), weeks=16, is_current=False)
        s.add(other)
        s.commit()
        other_id = other.id
    with Session(engine) as s:
        with pytest.raises(ValueError) as excinfo:
            evaluate_alerts(s, other_id, ids["batch"], D(2025, 9, 3),
                            rules=alert_rules(), exercises=exercise_library(), now=NOW)
        assert "semester_id" in str(excinfo.value)


def test_an_unknown_batch_is_rejected_loudly(engine):
    ids = _seed(engine)
    with Session(engine) as s:
        with pytest.raises(ValueError) as excinfo:
            evaluate_alerts(s, ids["semester"], 999999, D(2025, 9, 3),
                            rules=alert_rules(), exercises=exercise_library(), now=NOW)
        assert "daily_sync_run" in str(excinfo.value)


def test_a_channel_can_be_injected(engine):
    """``channel`` 可注入：于是「红色一条都不发」这类断言不必去查 ``notification`` 表。"""
    sent = []

    class Spy:
        CHANNEL = "in_app"

        def send(self, session, **kwargs):
            sent.append(kwargs)
            return InAppChannel(now=lambda: NOW).send(session, **kwargs)

    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _log(engine, student_id, D(2025, 9, 1))
    cs = _session_at(engine, D(2025, 9, 1), period=3, ids=ids)
    _rpe(engine, cs, student_id, 8, T(2025, 9, 1, 10, 0))

    _report, session = _run(engine, ids, D(2025, 9, 9), channel=Spy())
    assert [item["recipient_kind"] for item in sent] == ["student"] * len(sent)
    assert len(sent) >= 1
    assert _notifications(session)  # Spy 也真的落了库
    session.close()


def test_the_report_is_frozen_and_has_the_six_documented_fields():
    """:class:`AlertReport` 是 frozen 的，且恰好 6 个字段（运行时口径，硬规矩 #89）。

    ⚠️ 前四格照简报 Interfaces / Produces 逐字；后两格（``skipped`` / ``errors``）
    各有出处：``skipped`` 是 P7-A3 第 1 条要求的消费者，``errors`` 是异常分层第 1 档的
    可观测量（没有它，「一个学生的数据坏掉了」在报表上与「今天没人触发」同形）。
    """
    import dataclasses

    fields = [f.name for f in dataclasses.fields(AlertReport)]
    assert fields == ["raised", "deduped", "by_level", "adjustments_written",
                      "skipped", "errors"]
    report = AlertReport(raised=0, deduped=0, by_level={}, adjustments_written=0,
                         skipped={}, errors=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.raised = 1


def test_the_stage_does_not_touch_the_three_feedback_sources(engine):
    """预警阶段是**只读**三源的：一次求值不得改任何一行 ``rpe_record`` / ``training_log`` /
    ``mini_test``。

    ⚠️ 它们是**用户实时写入**的源数据（三张表都刻意不带 ``batch_id``，
    理由见 :mod:`app.db.models.feedback` 的模块 docstring：删源数据比删派生行严重得多）。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _three_nines(engine, ids, student_id)
    _log(engine, student_id, D(2025, 9, 1))
    _mini(engine, ids, student_id, 2, score=100.0)

    with Session(engine) as before:
        counts = {
            model: before.scalar(select(func.count()).select_from(model))
            for model in (RpeRecord, TrainingLog, MiniTest, ClassSession)
        }
    _report, session = _run(engine, ids, D(2025, 9, 3))
    after = {
        model: session.scalar(select(func.count()).select_from(model))
        for model in (RpeRecord, TrainingLog, MiniTest, ClassSession)
    }
    assert after == counts
    session.close()


# ===========================================================================
# 支 E′：Plan 04 收尾波 —— 综合分「算出来」而不是「读 normalized_score 那一列」
#
# ⚠️ 本支存在的理由（一句话）：改之前 ``GREEN_MASTERY`` 与 ``RED_MINITEST_DROP``
#    读的是 ``mini_test.normalized_score`` 那一列，而它在生产路径上**恒为 NULL**
#    （``POST /api/mini-tests/batch`` 显式写 ``None``）；同时 Plan 03 Task 9 已经把
#    进步榜改成「生成周报时现算」→ 两条路径读的不是同一个数。
#    完整诊断逐字见 :func:`app.pipeline.alert_stage._mini_test_composites`。
# ===========================================================================


def test_the_squat_for_composite_round_trip_is_exact():
    """**夹具自校**：:func:`_squat_for_composite` 的六格换算回代逐格相等。

    ⚠️ 本条守的是**夹具**、不是生产代码（硬规矩 #107 的正面用法：用一个已知反例
    验证谓词——本文件其余六条测试的期望值全部经由这一个换算，它错了那六条的
    「绿」就都是假的）。⚠️ 期望侧是 :data:`SHUTTLE_TIED` 那个「全班并列 →
    百分位恒 50.0」的口径**字面写出来的算式**，不调 ``app.domain.report``。
    """
    for composite in (100.0, 102.0, 110.0, 120.0, 90.0, 80.0):
        squat = _squat_for_composite(composite)
        assert isinstance(squat, int), (composite, squat)
        # 回代：单人班 + 折返并列 → 百分位 50.0 → composite = (squat + 50) / 2
        assert (squat + 50.0) / 2 == composite, (composite, squat)


def test_a_production_shaped_mini_test_row_feeds_the_drop_rule(engine):
    """**本支的靶心（红牌那一半）**：一行**生产形状**的 ``mini_test`` 喂得动
    ``RED_MINITEST_DROP``。

    「生产形状」逐字是 ``POST /api/mini-tests/batch`` 写出来的那一行：
    ``squat_30s_count`` / ``shuttle_20m_s`` 有值、``normalized_score`` 是 **NULL**
    （:mod:`app.api.routers.feedback` 的「刻意不做」第 3 条）。

    ⚠️ **改之前本条是红的**（变异自证见本波报告）：``RED_MINITEST_DROP`` 的判据
    ``StudentSignals.mini_test_scores`` 由「那一列非空的行」筛出来，故生产形状下
    它是**空元组** → domain 记 ``insufficient_points`` → 一条红牌都不落，
    而 ``report.skipped`` 里那一条留痕长得与「他真的只测了一次」**一模一样**。
    """
    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    # 三次小测：综合分 100 → 90 → 80（每次严格低于上一次的 95%），列一律 NULL
    for week, composite in ((2, 100.0), (4, 90.0), (6, 80.0)):
        _mini(engine, ids, student_id, week, score=composite)
    with Session(engine) as s:
        rows = list(s.scalars(select(MiniTest)))
        assert len(rows) == 3
        assert [row.normalized_score for row in rows] == [None, None, None], (
            "夹具必须造出**生产形状**的行（那一列 NULL），否则本条测不到东西"
        )
        assert [row.squat_30s_count for row in rows] == [150, 130, 110]

    # ⚠️ as_of 取 09-15（学期第 3 周），与既有的
    #    ``test_a_red_minitest_drop_also_writes_an_auto_adjustment`` 同一天。
    #    ⚠️ 而三次小测的周次是 2/4/6（其中一个在 as_of 之后）——那是本文件既有夹具的
    #    形状：``alert_stage`` 那一份 ``mini_test`` 查询**不夹周次上界**，与
    #    ``report_stage.class_snapshot`` 的 ``MiniTest.week <= week`` 刻意不同。
    #    ⚠️ 那一格是一处**读未来**，改前就有、已登记为待清扫（完整交代见
    #    :func:`app.pipeline.alert_stage._mini_test_composites` 的 docstring 末段）。
    report, session = _run(engine, ids, D(2025, 9, 15))
    drops = _alerts(session, "RED_MINITEST_DROP")
    assert len(drops) == 1, (
        "生产形状的小测行喂不动 RED_MINITEST_DROP —— 综合分是不是又去读那一列了？"
    )
    # 落库的留痕里那三个分是**算出来的**（100 / 90 / 80），不是列里的 NULL
    assert drops[0].trigger_snapshot["mini_test_scores"] == [100.0, 90.0, 80.0]
    assert report.skipped.get("RED_MINITEST_DROP") is None, (
        "有 3 个数据点却记了 insufficient_points 的留痕"
    )
    session.close()


def test_the_mastery_rule_reads_the_computed_composite_not_the_raw_columns(engine):
    """**本支的靶心（绿牌那一半）**：``GREEN_MASTERY`` 读的是**算出来的综合分**。

    ⚠️ 造法是承重的：他**自己**两次的原始测量值一模一样（深蹲 30、折返 10.0），
    故三个指标里 ``squat_30s_count`` 与 ``shuttle_20m_s`` 的改善率**都是 0%**；
    变的只有**同班的人**（第 2 周班里有人跑得比他快、第 4 周都比他慢）→
    班内百分位从 25.0 涨到 75.0 → 综合分 27.5 → 52.5（+90.9%）。
    于是「``mini_test_improved`` 为真」这件事**只可能**来自综合分那一项。

    ⚠️ **改之前本条是红的**：那一项读的是 ``normalized_score`` 列（NULL → 被
    ``continue`` 跳过），另两项都是 0% → ``mini_test_improved`` 恒假 → 没有绿牌。

    ⚠️⚠️ 而这一格也正是**顶回派单的地方**：派单说「生产数据上 ``GREEN_MASTERY``
    事实上永不触发（``mini_test_improved`` 恒为假）」——实测**不成立**。它是
    「三个指标里**任一**改善 ≥ 3%」，而另两个指标读的是教师批量录入**真的会写**的
    原始列，故只要深蹲或折返有一项涨了 3%，绿牌照发（本文件既有的
    ``test_green_mastery_sends_a_badge_notification`` 在改前改后都绿，就是证据）。
    **真正恒不触发的是 ``RED_MINITEST_DROP``**（它的判据 100% 是那一列）。
    """
    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    sid = ids[STUDENT_NO]
    _mini(engine, ids, sid, 2, squat=30, shuttle=10.0)
    _mini(engine, ids, sid, 4, squat=30, shuttle=10.0)
    # 同班的另一个人：第 2 周 5.0（比他快）、第 4 周 20.0（比他慢）
    _mini(engine, ids, ids[OTHER_NO], 2, squat=40, shuttle=5.0)
    _mini(engine, ids, ids[OTHER_NO], 4, squat=40, shuttle=20.0)
    # 处方第 1 周的两个训练日都打了卡 → 完成率 1.0（另一半判据）
    _log(engine, sid, D(2025, 9, 1))
    _log(engine, sid, D(2025, 9, 2))

    _report, session = _run(engine, ids, D(2025, 9, 3))
    green = [a for a in _alerts(session, "GREEN_MASTERY") if a.student_id == sid]
    assert len(green) == 1, (
        "两个原始指标都是 0%、只有综合分涨了 90.9% —— 综合分没被读进判据"
    )
    assert green[0].trigger_snapshot["mini_test_improved"] is True
    assert green[0].trigger_snapshot["completion_rate"] == 1.0
    session.close()


def test_the_alert_stage_composite_agrees_with_the_report_stage_one(engine):
    """**两条路径读的是同一个数**（本支存在的全部理由）。

    ⚠️ 两侧不同源（硬规矩 #35）：一侧是本模块的
    :func:`app.pipeline.alert_stage._mini_test_composites`，另一侧是进步榜那一份
    :func:`app.pipeline.report_stage._composite_of`，而**第三侧是字面量**
    （``52.5`` / ``37.5``，按 ``shuttle_percentile`` 的口径手算：
    样本 ``[10.0, 14.0]``，10.0 那一个人有 1 个更慢的 + 1 个并列 →
    ``(1 + 0.5) / 2 × 100 = 75.0`` → ``(30 + 75) / 2 = 52.5``；
    14.0 那一个有 0 个更慢的 + 1 个并列 → ``25.0`` → ``(50 + 25) / 2 = 37.5``）。
    ⚠️ 只有字面量那一侧能挡住「两侧一起改错」：前两侧都调
    :func:`app.domain.report.mini_test_scores`，故它们相等这件事**看似恒真**。
    """
    from app.pipeline.report_stage import _composite_of

    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    _mini(engine, ids, ids[STUDENT_NO], 2, squat=30, shuttle=10.0)
    _mini(engine, ids, ids[OTHER_NO], 2, squat=50, shuttle=14.0)

    with Session(engine) as s:
        rows = list(s.scalars(
            select(MiniTest).order_by(MiniTest.student_id, MiniTest.week, MiniTest.id)))
        mini_by_student: dict = {}
        for row in rows:
            mini_by_student.setdefault(row.student_id, []).append(row)
        got = stage._mini_test_composites(s, ids["semester"], mini_by_student)
        # 另一侧：进步榜那一份（同一个班 × 同一周的全部行当样本）
        want = {
            row.student_id: _composite_of(row, rows) for row in rows
        }
    assert got[ids[STUDENT_NO]] == (52.5,)
    assert got[ids[OTHER_NO]] == (37.5,)
    assert got == {sid: tuple([value]) for sid, value in want.items()}


def test_a_student_in_two_sections_is_scored_against_the_lowest_section_id(engine):
    """**一个学生在两个班**（行政班 + 分层班并存）→ 按 ``course_section_id`` 升序取第一个。

    ⚠️ 那一条口径决定的理由是**可复现**（不随一次 SQL 的结果序变），
    而不是「第一个班更有意义」；完整交代见
    :func:`app.pipeline.alert_stage._mini_test_composites` 的 docstring。
    ⚠️ 造法：给 ``STUDENT_NO`` 再加一行选课到**第二个**班（id 更大），
    并让那个班里有另一个人、折返秒数不同 → 两个班给出**不同**的百分位。
    少了「按 id 升序」那一格（``ORDER BY`` + ``setdefault``），本条会随
    SQLite 的结果序**时而绿时而红**，而那正是它要挡的形状。
    """
    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    with Session(engine) as s:
        second = CourseSection(semester_id=ids["semester"], teacher_id=ids["teacher"],
                               name="分层班", grouping_mode="stratified")
        s.add(second)
        s.flush()
        assert second.id > ids["section"], "第二个班的 id 必须更大，否则本条测不到东西"
        third = Student(student_no="S2025003", name="学生3", sex="male",
                        birth=D(2005, 3, 4), department=None, grade=1)
        s.add(third)
        s.flush()
        s.add_all([
            Enrollment(semester_id=ids["semester"], student_id=ids[STUDENT_NO],
                       course_section_id=second.id),
            Enrollment(semester_id=ids["semester"], student_id=third.id,
                       course_section_id=second.id),
        ])
        s.commit()
        third_id = third.id

    # 第一个班（id 较小）：折返 10.0 与 14.0 → 他的百分位 75.0 → 综合分 52.5
    _mini(engine, ids, ids[STUDENT_NO], 2, squat=30, shuttle=10.0)
    _mini(engine, ids, ids[OTHER_NO], 2, squat=50, shuttle=14.0)
    # 第二个班（id 较大）：折返 8.0 → 若按它算，他的百分位是 25.0 → 综合分 27.5
    with Session(engine) as s:
        s.add(MiniTest(
            student_id=third_id, semester_id=ids["semester"], week=2,
            item_combo=["squat_30s", "shuttle_20m"], squat_30s_count=40,
            shuttle_20m_s=8.0, normalized_score=None,
            tested_on=SEMESTER_START + dt.timedelta(weeks=1), entered_by=TEACHER_STAFF_NO,
        ))
        s.commit()
        rows = list(s.scalars(
            select(MiniTest).order_by(MiniTest.student_id, MiniTest.week, MiniTest.id)))
        mini_by_student: dict = {}
        for row in rows:
            mini_by_student.setdefault(row.student_id, []).append(row)
        got = stage._mini_test_composites(s, ids["semester"], mini_by_student)

    assert got[ids[STUDENT_NO]] == (52.5,), (
        f"他在两个班里，实测综合分 {got[ids[STUDENT_NO]]}：按 id 较小的那个班算应当是 52.5，"
        "按 id 较大的那个班算是 27.5"
    )
    # ⚠️ 反空转：第二个班里那个只在一个班的人，综合分按他自己的班算（样本 [10.0, 8.0]
    #    里 8.0 有 1 个更慢的 + 1 个并列 → 75.0 → (40 + 75) / 2 = 57.5）
    assert got[third_id] == (57.5,)


def test_a_student_without_a_section_gets_no_composite(engine):
    """**不在任何教学班的学生 → 综合分一律 ``None``**，而不是「拿无班的人当一个班」。

    ⚠️ 口径逐字同 :func:`app.api.routers.feedback.normalized_scores` 的 ``unassigned``
    那一档：「班内百分位」对他**无定义**，而三种候选处置里只有「点名说判不了」不撒谎
    （当成一个人的班 → 他会拿到 50.0；给 0 → 把「不知道」讲成「最差」）。
    ⚠️ 于是他在 ``RED_MINITEST_DROP`` 上落 ``insufficient_points`` 的留痕。
    ⚠️ 本条同时是那一格 ``if section_id is None`` 的**唯一**覆盖：少了它，
    全部无班的人会被 ``cohort[(None, week)]`` 归成一个假班、各自拿到一个假分。

    ⚠️ **反空转（硬规矩 #50）**：只断「他没有红牌」的话，「闸门把所有人都挡了」
    与「只有他被挡了」在颜色上无法区分（⚠️ 而上面那一条变异自证里，本条正是唯一
    保持绿的一条——因为变异之后**人人**都拿不到分）。故同一次求值里必须有
    **另一个人真的拿到红牌**：``OTHER_NO`` 在班上、同样三次下降 → 他那一条照落。
    """
    ids = _seed(engine, students=(STUDENT_NO, OTHER_NO))
    with Session(engine) as s:
        # ⚠️ 只删**他一个人**的选课行（另一个人仍然在班上）
        for row in s.scalars(select(Enrollment).where(
                Enrollment.student_id == ids[STUDENT_NO])):
            s.delete(row)
        s.commit()
    for week, composite in ((2, 100.0), (4, 90.0), (6, 80.0)):
        _mini(engine, ids, ids[STUDENT_NO], week, score=composite)
        _mini(engine, ids, ids[OTHER_NO], week, score=composite)

    report, session = _run(engine, ids, D(2025, 9, 15))
    drops = _alerts(session, "RED_MINITEST_DROP")
    assert [a.student_id for a in drops] == [ids[OTHER_NO]], (
        f"不在任何班的学生不该拿到一个综合分（「班内百分位」对他无定义），"
        f"而在班上的那一个照落：实测 {[a.student_id for a in drops]}"
    )
    assert report.skipped.get("RED_MINITEST_DROP") == 1, (
        "他必须落 insufficient_points 的留痕，而不是被静默跳过"
    )
    session.close()


# ===========================================================================
# 支 F：接进 daily.py（阶段序列 / alert_count / _replay_cleanup）
# ===========================================================================


def test_replay_cleanup_covers_alert_and_leaves_the_notification_alone(engine):
    """**``_replay_cleanup`` 的清单从五张扩到六张**（加 ``Alert``）。

    ⚠️ 漏掉它的失效形态是**重放翻倍**：``alert`` 上有四列唯一约束，故同日重跑会在
    本模块那一次 SELECT 上命中已有行、计入 ``deduped``——**不翻倍、但静默地不再报**。
    于是「重放那一天」与「那一天真的没人触发」在 ``alert_count`` 上同为 0，
    而重放的定义是「同一批输入得到同一批输出」。

    ⚠️ 同一条钉住 :class:`Notification` 的 ``ON DELETE SET NULL`` **在清理路径上**生效
    （Task 2 顶回 3 的那一列）：``notification`` 刻意不带 ``batch_id``、不在清单里，
    而它指着 ``alert``。少了 ``SET NULL``，本条会当场
    ``IntegrityError: FOREIGN KEY constraint failed``、整批回滚。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    student_id = ids[STUDENT_NO]
    _three_nines(engine, ids, student_id)
    _report, session = _run(engine, ids, D(2025, 9, 3))
    # ⚠️ 这一批里**不止一条**预警（rpe=9 也让班级均值 9.0 > 7.0 触发班级黄牌，
    #    而这个学生没打过卡也触发打卡中断），故按 rule_id 挑那一条红色的。
    alert = session.scalars(select(Alert).where(
        Alert.rule_id == "RED_RPE_SUSTAINED")).one()
    assert alert.batch_id == ids["batch"]
    # 班级黄牌那条是**有**消息的（发给教师），故本条要挑的正是它：
    # 红色预警在教师处置前不发消息，于是 notification 表里那一行属于班级黄牌。
    note_id = session.scalars(select(Notification.id).where(
        Notification.alert_id == session.scalars(select(Alert.id).where(
            Alert.rule_id == "YELLOW_CLASS_RPE_HIGH")).one()
    )).one()

    daily._replay_cleanup(session, ids["batch"])
    session.flush()

    assert session.scalar(select(func.count()).select_from(Alert)) == 0
    assert session.scalar(select(func.count()).select_from(WeeklyAdjustment)) == 0
    # ⚠️ 消息**活下来**、只是断开关联（它是已经推给某个人的东西，重放不该抹掉它）
    kept = session.get(Notification, note_id)
    assert kept is not None
    assert kept.alert_id is None
    session.close()


def test_replay_cleanup_still_does_not_cover_class_session(engine):
    """**反证的一半**：``ClassSession`` 有 ``batch_id`` 却**不得**进那份清单。

    ``rpe_record.class_session_id`` 是 NOT NULL 的外键指向它，而 ``rpe_record`` 是
    **学生实时写入**的、刻意不带 ``batch_id``。按批删课次只有两种结局：当场 FK 违例，
    或者把那一列改成 ``ON DELETE CASCADE`` —— 那会连带删掉学生刚交的快评
    （删源数据 vs 删派生行）。它的幂等手段是 ``repo.upsert`` 按
    ``(course_section_id, session_date, period)`` 更新。
    """
    from app.pipeline import daily

    ids = _seed(engine)
    with Session(engine) as s:
        row = ClassSession(course_section_id=ids["section"], session_date=D(2025, 9, 1),
                           period=3, rpe_opened=True, rpe_token="tok",
                           batch_id=ids["batch"])
        s.add(row)
        s.commit()
        cs_id = row.id

    with Session(engine) as s:
        daily._replay_cleanup(s, ids["batch"])
        s.commit()
        assert s.get(ClassSession, cs_id) is not None, (
            "ClassSession 被按批删了：那一列 batch_id 只用来回答「这一行是哪一次同步"
            "写进来的」，不用来删（理由见 app/db/models/feedback.py 的模块 docstring）"
        )


def test_alert_count_lands_in_daily_sync_run(tmp_path):
    """``daily_sync_run.alert_count`` = ``AlertReport.raised``。

    ⚠️ **这一列是 Plan 01 就建好的、到本 Task 为止从未被写过**（Plan 02 结案时留给
    Plan 03 的第 7 条）。⚠️ 它的列注释逐字警告过「在那之前它恒为 0，读它的人不得把 0
    当成『今天没有预警』」——本条钉的就是「现在它不再恒为 0」。

    ⚠️ **断言不是 ``== 0``**：三张反馈表在回放的既有测试里恒为空，故一条只跑
    ``run_daily`` 的测试会得到 ``0 == 0`` 的恒真式。本条**先注入三节 rpe=9 的课**，
    于是 ``raised >= 1``，再把它与库里那一批的 ``alert`` 行数对账（两侧不同源：
    一侧是 ``daily_sync_run`` 的列，一侧是 ``count(alert)``）。
    """
    from app.adapters.mock_lepao import MockLePaoAdapter
    from app.db.models.organisation import CourseSection
    from app.pipeline.daily import run_daily
    from app.seed.config import SeedConfig
    from app.seed.generate import build_dataset, seed_database, write_csv

    cfg = SeedConfig(students=60, weeks=16, seed=20250828)
    seed_dir = tmp_path / "lepao"
    write_csv(build_dataset(cfg), seed_dir)

    engine = create_engine(f"sqlite:///{tmp_path / 'daily.db'}")
    init_db(engine)
    with Session(engine) as session:
        seed_database(session, cfg)
        semester = session.scalars(
            select(Semester).where(Semester.name == "2025-2026-1")).one()
        section = session.scalars(
            select(CourseSection).where(
                CourseSection.semester_id == semester.id).order_by(CourseSection.id)
        ).first()
        # ⚠️ **不自己插 enrollment**：seed_database 已经把选课关系全量铺好了
        #    （撞 uq_enrollment_semester_student_section），故按那个班**已有的**选课取人。
        student_id = session.scalars(
            select(Enrollment.student_id).where(
                Enrollment.semester_id == semester.id,
                Enrollment.course_section_id == section.id,
            ).order_by(Enrollment.student_id)
        ).first()
        student = session.get(Student, student_id)
        # 三节课各交一次 rpe = 9（= 阈值），日期都 <= AS_OF
        for offset in range(3):
            day = D(2025, 9, 8) + dt.timedelta(days=offset)
            cs = ClassSession(course_section_id=section.id, session_date=day,
                              period=3, rpe_opened=True, rpe_token="tok",
                              batch_id=None)
            session.add(cs)
            session.flush()
            session.add(RpeRecord(class_session_id=cs.id, student_id=student.id,
                                  rpe=9, submitted_at=T(day.year, day.month, day.day, 10, 0),
                                  elapsed_seconds=8.0))
        session.commit()

        run = run_daily(session, semester.id, "2025-09-15", MockLePaoAdapter(seed_dir))
        # ⚠️ 一切字段读取都必须在这个 with 块内完成：run_daily 末尾的 commit 已把它们
        #    expire，会话一关就是 DetachedInstanceError（Task 10 关切 10）。
        assert run.status in ("success", "partial")
        alert_count = run.alert_count
        rows = session.scalar(
            select(func.count()).select_from(Alert).where(Alert.batch_id == run.id)
        )
        assert alert_count == rows
        assert alert_count >= 1, "注入了三节 rpe=9 的课，却一条预警都没落库"
        red = session.scalar(
            select(func.count()).select_from(Alert).where(
                Alert.batch_id == run.id, Alert.rule_id == "RED_RPE_SUSTAINED")
        )
        assert red == 1
        # 红色预警带来一条 auto 减量。⚠️ **写成条件式而不是 ``>= 0`` 那种恒真式**：
        # 那个学生在这一批里**可能**没拿到处方（Z0 闸门 / 模板没匹配上），
        # 而「没有处方就没有可减量的周」正是 _write_auto_adjustment 的那一档。
        # 于是判据是「有处方 ⟺ 有 auto 调整」，两侧都可能是空，但不会同形。
        rx = session.scalar(
            select(Prescription).where(Prescription.student_id == student.id)
        )
        autos = session.scalars(
            select(WeeklyAdjustment).where(WeeklyAdjustment.source == "auto")
        ).all()
        if rx is None:
            assert autos == []
        else:
            assert len(autos) == 1
            assert autos[0].prescription_id == rx.id
            assert autos[0].factor == 0.8
            assert autos[0].reason == "RED_RPE_SUSTAINED"
            assert autos[0].batch_id == run.id
