"""``app/api/routers/dashboard.py`` 与 Task 8 加在 ``alerts.py`` 里那个端点的守卫。

**分六支**：

* **支 A（教师大屏，spec §9.1）**：四块 + 顶栏元数据；两条阈值线**现读 YAML**、
  两个大屏阈值**现读 domain**，且两组**不相等**（spec §14 #11）；水位线；
  越权（不任教的班 → 403）。
* **支 B（周报读端点）**：按 ``(班, 周次)`` 取存下来的那一行；``week`` 缺省取最新；
  404 有自己的 ``code``。
* **支 C（学生首页，spec §9.2）**：五格齐全；``explanation`` 与 domain 的
  :func:`~app.domain.stratify.explain` **逐字相等**；越权；两档 404 折成 ``null``；
  从未被分层过的学生**仍然**有首页。
* **支 D（P8-A5：教师端读单个学生的训练单）**：与学生侧那个端点**响应体逐字相同**、
  两档 404 的 ``code`` 也相同；学生身份头调它 → **401**；不任教 → **403**；
  **上学期教过、这学期不教** → 403（那一格是 ``semester_id`` 相等的判据）。
* **支 E（通知已读）**：翻 ``is_read``；别人的消息 → 403 + ``not_recipient``；
  不存在的 id → **同一个 403**（不泄露「哪些 id 在册」）；幂等。
* **支 F（前后端对接面）**：五个新端点在 ``/openapi.json`` 里各挂着**对的那一格**
  securityScheme；16 个响应模型的字段集与 domain 的输出**逐字段对账**。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律字面写在测试里；
支 C/支 F 那几条「与 domain 对账」的，另一侧是**在测试里直接调 domain**。

⚠️ 夹具**刻意不复用** ``tests/api/test_alerts_api.py`` / ``test_feedback.py`` 的那一套
（跨测试文件 import 私有夹具会让两个文件互相钉住），故本文件自己有一份 ``_seed``。
"""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as M
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student, Teacher
from app.db.models.prescription import Prescription
from app.domain.derive import BodyCompFlag, DerivedResult, Trend, WeaknessResult
from app.domain.indicators import ScoredItem, Sex
from app.domain.stratify import Layer, RuleId as StratRuleId, StratResult, explain
from app.pipeline.prescription_stage import training_package_payload
from app.domain.prescription.assembler import StudentProfile, assemble
from app.refdata_prescription import exercises as exercise_library
from app.refdata_prescription import templates as template_library

D = dt.date
T = dt.datetime

SEMESTER_START = D(2025, 9, 1)          # 周一
SEMESTER_END = D(2025, 12, 22)
MICROCYCLE_WEEKS = 4
VALID_TO = D(2025, 9, 28)               # generated_on + 4 周 − 1 天
GREEN_TEMPLATE = "GRN-END-NOR-14"       # 每周 2 天（day = [1, 2]）

#: 学期第 2 周 = 09-08..09-14，**周日是 09-14**（周报生成的那一天）。
SUNDAY = "2025-09-14"
WEDNESDAY = "2025-09-10"

TEACHER_NO = "T2025001"
OTHER_TEACHER_NO = "T2025002"
TEACHER = {"X-Teacher-Staff-No": TEACHER_NO}
OTHER_TEACHER = {"X-Teacher-Staff-No": OTHER_TEACHER_NO}
NOBODY = {"X-Teacher-Staff-No": "NOBODY"}
STUDENT_NO = "S2025001"
OTHER_STUDENT_NO = "S2025002"
#: 一位**不在本班名册上**的学生（支 D 的越权那一格用）。
OUTSIDER_NO = "S2025003"


def _student_header(student_id: int) -> dict:
    return {"X-Student-Id": str(student_id)}


def _profile(student_id: int) -> StudentProfile:
    return StudentProfile(
        student_id=student_id, sex=Sex.MALE, birth=D(2005, 3, 4), age=20,
        endurance_score=70.0, bmi=None, body_fat_pct=None, muscle_mass_kg=None,
        muscle_p10=None, measured_hrmax=None,
    )


def _seed(engine, *, with_report=False, with_prev_week=False) -> dict:
    """一套最小可用的行：学期 + 两位教师 + 两个教学班 + 三个学生（含选课）+ 批次 + 处方。

    ``STUDENT_NO`` 与 ``OTHER_STUDENT_NO`` 在**张老师**的班上；
    ``OUTSIDER_NO`` 在**李老师**的班上（支 D 的「不任教」那一格）。
    """
    ids: dict = {}
    with Session(engine) as s:
        semester = Semester(name="2025-2026-1", start_date=SEMESTER_START,
                            end_date=SEMESTER_END, weeks=16, is_current=True)
        teacher = Teacher(staff_no=TEACHER_NO, name="张老师")
        other_teacher = Teacher(staff_no=OTHER_TEACHER_NO, name="李老师")
        s.add_all([semester, teacher, other_teacher])
        s.flush()
        ids["semester"], ids["teacher"] = semester.id, teacher.id
        ids["other_teacher"] = other_teacher.id

        section = CourseSection(semester_id=semester.id, teacher_id=teacher.id,
                                name="体育(1)班", grouping_mode="administrative")
        outside = CourseSection(semester_id=semester.id, teacher_id=other_teacher.id,
                                name="体育(2)班", grouping_mode="administrative")
        s.add_all([section, outside])
        s.flush()
        ids["section"], ids["outside_section"] = section.id, outside.id

        run = M.DailySyncRun(semester_id=semester.id, business_date=SEMESTER_START,
                             started_at=T(2025, 9, 1, 2, 0), status="success")
        s.add(run)
        s.flush()
        ids["batch"] = run.id

        for index, (student_no, home) in enumerate(
            [(STUDENT_NO, section), (OTHER_STUDENT_NO, section), (OUTSIDER_NO, outside)],
            start=1,
        ):
            student = Student(student_no=student_no, name=f"学生{index}", sex="male",
                              birth=D(2005, 3, 4), department=None, grade=1)
            s.add(student)
            s.flush()
            ids[student_no] = student.id
            ids[f"section_of_{student_no}"] = home.id
            s.add(Enrollment(semester_id=semester.id, student_id=student.id,
                             course_section_id=home.id))
            package = assemble(_profile(student.id), template_library()[GREEN_TEMPLATE],
                               SEMESTER_START, exercises=exercise_library())
            row = Prescription(
                student_id=student.id, generated_on=SEMESTER_START, batch_id=run.id,
                template_ref=GREEN_TEMPLATE, microcycle_weeks=MICROCYCLE_WEEKS,
                label_at_generation="green",
                training_package=training_package_payload(package),
                assembly_snapshot=dict(package.assembly_snapshot),
                safety_substitutions=[], teacher_overrides=[],
                previous_had_overrides=False, status="active",
                valid_from=SEMESTER_START, valid_to=VALID_TO,
                trigger_reasons=["first_stratification"],
            )
            s.add(row)
            s.flush()
            ids[f"prescription_{student_no}"] = row.id
        s.commit()
    return ids


# ⚠️ 一份**手写的** input_snapshot：只含 _stratification_payload 真的会读的那些键。
# ⚠️ 它与管道写出来的那一份（28 个键，由 tests/pipeline/test_prescription_stage.py
#    逐字钉住）刻意不同——本文件要测的是「给定一份快照，端点重建出的文案对不对」，
#    而「管道真的会写出这些键」由那一条守卫看着，两处不互相替代。
#    ⚠️ 而「真跑一遍管道也能重建出来」由本文件末尾那条 end-to-end 测试兜住。
SNAPSHOT = {
    "sex": "male",
    "trend": "持续下滑",
    # ⚠️ 两个值都必须落在 ScoredItem 的值域里（实测：bmi / vital_capacity / sprint_50m /
    #    sit_and_reach / standing_jump / pull_up_or_sit_up / distance_run），
    #    而短板判定项是后六个（WEAKNESS_ITEMS，不含 bmi）。写一个值域外的名字
    #    （例如 "endurance_1000m"）会让 ScoredItem(...) 当场 ValueError → 422。
    "weakness_items": ["distance_run", "pull_up_or_sit_up"],
    "W": 2,
    "valid_count": 6,
    "dominant_bucket": "endurance",
    "C": True,
    "body_comp_reasons": ["body_fat_high"],
    "body_fat_pct": 22.4,
    "body_fat_limit": 20.0,
    "annual_change": {"national_total": -8.0},
    "national_total": 62,
    "label": "red",
    "hit_rules": ["R1"],
    "reason": "短板 ≥ 2 项",
}


def _expected_explanation() -> str:
    """**在测试里**用 domain 的纯函数把同一份快照渲染一遍（期望侧，与被测端点不同源）。"""
    derived = DerivedResult(
        sex=Sex(SNAPSHOT["sex"]),
        trend=Trend(SNAPSHOT["trend"]),
        weakness=WeaknessResult(
            items=tuple(ScoredItem(i) for i in SNAPSHOT["weakness_items"]),
            count=SNAPSHOT["W"], valid_count=SNAPSHOT["valid_count"],
            dominant_bucket=SNAPSHOT["dominant_bucket"],
        ),
        body_comp=BodyCompFlag(
            abnormal=SNAPSHOT["C"], reasons=tuple(SNAPSHOT["body_comp_reasons"]),
            body_fat_pct=SNAPSHOT["body_fat_pct"], limit=SNAPSHOT["body_fat_limit"],
        ),
        annual_change=dict(SNAPSHOT["annual_change"]),
        national_total=SNAPSHOT["national_total"],
    )
    result = StratResult(
        label=Layer(SNAPSHOT["label"]),
        hit_rules=tuple(StratRuleId(r) for r in SNAPSHOT["hit_rules"]),
        reason=SNAPSHOT["reason"],
    )
    return explain(result, derived)


def _stratify_row(engine, ids, student_no, computed_on, *, label="red",
                  snapshot=None, batch=None) -> None:
    with Session(engine) as s:
        s.add(M.StratificationResult(
            student_id=ids[student_no], computed_on=computed_on,
            batch_id=ids["batch"] if batch is None else batch,
            label=label, hit_rules=",".join(
                (snapshot or SNAPSHOT)["hit_rules"]),
            input_snapshot=dict(SNAPSHOT if snapshot is None else snapshot),
            percentile_source="school", valid_from=computed_on, valid_to=None,
        ))
        s.commit()


def _class_session(engine, ids, session_date, period=3, *, opened=True,
                   section=None) -> int:
    with Session(engine) as s:
        row = ClassSession(
            course_section_id=ids["section"] if section is None else section,
            session_date=session_date, period=period, rpe_opened=opened,
            rpe_token="tok" if opened else None, batch_id=None,
        )
        s.add(row)
        s.commit()
        return row.id


def _rpe(engine, cs_id, student_id, rpe, submitted_at) -> None:
    with Session(engine) as s:
        s.add(RpeRecord(class_session_id=cs_id, student_id=student_id, rpe=rpe,
                        submitted_at=submitted_at, elapsed_seconds=8.0))
        s.commit()


def _log(engine, student_id, log_date, *, completed=True, late=False,
         is_rest_day=False) -> None:
    with Session(engine) as s:
        s.add(TrainingLog(
            student_id=student_id, log_date=log_date,
            submitted_at=T(log_date.year, log_date.month, log_date.day, 9, 0),
            completed=completed, duration_min=30.0 if completed else None,
            feeling="moderate" if completed else None, is_rest_day=is_rest_day,
            late=late, source="checkin", batch_id=None,
        ))
        s.commit()


#: 全班的折返秒数一律取这一个值 → 所有人**并列** → 班内百分位反查一律 **50.0**，
#: 故 ``composite = (squat_30s_count + 50) / 2``（70 → 60.0、82 → 66.0）。
#: ⚠️ 口径与 ``tests/pipeline/test_report_stage.py`` 的 ``SHUTTLE_TIED`` 逐字相同
#: （两个文件各持一份**字面量**、不互相 import：期望值不从被测函数读回来，硬规矩 #35）。
SHUTTLE_TIED = 30.0


def _mini(engine, ids, student_id, week, *, squat: int,
          shuttle: "float | None" = SHUTTLE_TIED) -> None:
    """一行 ``mini_test``。⚠️ 入参是**原始测量值**而不是综合分：自 Plan 03 Task 9 起
    进步榜读的是 :func:`app.pipeline.report_stage._composite_of` 算出来的综合分，
    ``normalized_score`` 那一列在周报这一侧没有读者了，故这里一律留 ``NULL``
    （那正是「这一列在生产路径上没人写」的真实形状）。
    """
    with Session(engine) as s:
        s.add(MiniTest(
            student_id=student_id, semester_id=ids["semester"], week=week,
            item_combo=["squat_30s", "shuttle_20m"], squat_30s_count=squat,
            shuttle_20m_s=shuttle, normalized_score=None,
            tested_on=SEMESTER_START + dt.timedelta(weeks=week - 1),
            entered_by=TEACHER_NO,
        ))
        s.commit()


def _notification(engine, recipient_id, *, kind="student", title="补练提醒",
                  body="你已经连续 2 个应打卡训练日没有打卡了", is_read=False) -> int:
    with Session(engine) as s:
        row = Notification(recipient_kind=kind, recipient_id=recipient_id,
                           channel="in_app", title=title, body=body,
                           alert_id=None, prescription_id=None,
                           is_read=is_read, created_at=T(2025, 9, 10, 8, 0))
        s.add(row)
        s.commit()
        return row.id


def _alert(engine, ids, *, level, rule_id, student_id=None, section_id=None,
           status="pending", triggered_at=None, window_key="w") -> int:
    with Session(engine) as s:
        subject_section = None if student_id is not None else (
            ids["section"] if section_id is None else section_id)
        row = Alert(
            student_id=student_id, course_section_id=subject_section,
            semester_id=ids["semester"],
            subject_key=(f"student:{student_id}" if student_id is not None
                         else f"section:{subject_section}"),
            level=level, rule_id=rule_id, trigger_snapshot={},
            triggered_at=T(2025, 9, 10, 6, 0) if triggered_at is None else triggered_at,
            status=status, batch_id=ids["batch"], window_key=window_key,
        )
        s.add(row)
        s.commit()
        return row.id


# ===========================================================================
# 支 A：教师大屏（spec §9.1）
# ===========================================================================


def test_the_class_dashboard_returns_the_four_blocks_and_the_header(client, engine):
    """**四块 + 顶栏**：``blocks`` 恰好七个键，顶栏那几格是元数据。

    ⚠️ 七个键的**名字**是字面写在期望侧的（不是从 :mod:`app.pipeline.report_stage`
    读回来），故「大屏少给了一块」与「domain 少算了一个量」不会互相掩盖。
    """
    ids = _seed(engine)
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 10), label="red")
    _stratify_row(engine, ids, OTHER_STUDENT_NO, D(2025, 9, 10), label="green",
                  snapshot={**SNAPSHOT, "label": "green", "hit_rules": ["G1"],
                            "reason": "短板 0 项且体成分正常"})
    cs = _class_session(engine, ids, D(2025, 9, 9))
    _rpe(engine, cs, ids[STUDENT_NO], 9, T(2025, 9, 9, 10, 0))
    _rpe(engine, cs, ids[OTHER_STUDENT_NO], 8, T(2025, 9, 9, 10, 1))
    # 学生二把绿层处方第 1、2 周的四个训练日（09-01 / 09-02 / 09-08 / 09-09）都打了卡，
    # 故他的「连续未打卡」是 0；学生一一趟都没打 → 4 天（跨了两个处方周，
    # 口径逐字同 alert_stage._student_signals）。
    for day in (D(2025, 9, 1), D(2025, 9, 2), D(2025, 9, 8), D(2025, 9, 9)):
        _log(engine, ids[OTHER_STUDENT_NO], day)

    resp = client.get(f"/api/dashboard/class/{ids['section']}?as_of={SUNDAY}",
                      headers=TEACHER)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["blocks"]) == [
        "abnormal_roster", "alert_summary", "checkin_rate_by_layer",
        "layer_distribution", "progress_board", "rpe_summary", "suggestion",
    ]
    assert body["course_section_id"] == ids["section"]
    assert body["semester_name"] == "2025-2026-1"
    assert body["course_section_name"] == "体育(1)班"
    assert body["week"] == 2
    assert body["as_of"] == SUNDAY
    assert body["week_start"] == "2025-09-08"
    assert body["watermark"] == SUNDAY
    # ① 分层饼图：本班名册 2 人
    assert body["blocks"]["layer_distribution"]["by_layer"] == {
        "red": 1, "yellow": 0, "green": 1, "insufficient_data": 0,
    }
    assert body["roster_size"] == 2
    # ② RPE 曲线：横轴恒 7 天，09-09 那一点是 (9 + 8) / 2 = 8.5
    curve = body["blocks"]["rpe_summary"]["curve"]
    assert len(curve) == 7
    assert curve[1] == {"day": "2025-09-09", "mean": 8.5, "submissions": 2}
    assert curve[0] is None
    # ③ 按层完成率：红层那一个人一趟没打 → 0.0（**不是** null：他 measurable、确实没练）；
    #    绿层那一个人四个训练日里落在本学期第 2 周的两天都打了 → 1.0
    assert body["blocks"]["checkin_rate_by_layer"]["red"] == {
        "students": 1, "measured": 1, "rate": 0.0}
    assert body["blocks"]["checkin_rate_by_layer"]["green"] == {
        "students": 1, "measured": 1, "rate": 1.0}
    # ④ 异常名单：只有学生一上榜（连续 4 天未打卡 ≥ 3，且 RPE 峰值 9 > 8）；
    #    学生二 gap=0、峰值 8 不 **>** 8，故两条都不中 → 不在名单上
    assert body["blocks"]["abnormal_roster"] == [{
        "student_id": ids[STUDENT_NO],
        "reasons": ["checkin_gap", "rpe_high"],
        "gap_days": 4,
        "peak_rpe": 9,
    }]


def test_the_two_threshold_pairs_come_from_their_owners_and_differ(client, engine):
    """**spec §14 #11 的可执行落点**：两条预警阈值线现读 YAML、两个大屏阈值现读 domain，
    而**两组不相等**。

    ⚠️ 期望侧的 7.0 / 9 是字面量（``data/alert_rules.yaml`` 里那两个数），
    另一侧是端点返回的；两组阈值相等 → 本条红，而那正是「两套并存」被悄悄合并的形状。
    """
    ids = _seed(engine)
    body = client.get(f"/api/dashboard/class/{ids['section']}?as_of={SUNDAY}",
                      headers=TEACHER).json()
    assert body["rpe_threshold_lines"] == {"class_mean_max": 7.0, "sustained_min": 9.0}
    assert body["screen_thresholds"] == {"gap_days": 3, "rpe_max": 8}
    # ⚠️ 两组刻意不同：预警是「中断 2 天 / RPE 连续 ≥ 9」，大屏是「连续 3 天 / RPE > 8」
    from app.refdata_alerts import alert_rules

    rules = alert_rules()
    assert rules.params_of("YELLOW_CHECKIN_GAP")["gap_days"] == 2
    assert rules.params_of("RED_RPE_SUSTAINED")["rpe_min"] == 9
    assert body["screen_thresholds"]["gap_days"] != 2
    assert body["screen_thresholds"]["rpe_max"] != 9


def test_the_dashboard_agrees_with_the_stored_report_on_the_same_sunday(client, engine):
    """**P8-A2 的落地守卫**：同一个周日、同一个班，「现算的大屏」与「存下来的周报」
    的**六个共有键逐字相等**。

    ⚠️ 本条是整个 Task 8 最要紧的一条：大屏是实时刷新的、周报是周日存下来的，
    两条路径若各自读一遍库、各自调一遍 domain，教师就会看到大屏写「人均 6.9」
    而同一周的周报写「7.1」，而他无从判断哪一个是真的。
    ⚠️ 期望侧是**周报那一行**（从库里读回来的），另一侧是**大屏的响应体**——
    两个不同的来源，故本条真的在比两条路径。
    ⚠️ ``abnormal_roster`` **不在**共有的六个键里：它是 §9.1 的实时筛选器，
    ``weekly_class_report`` 没有它的位置（理由逐字见
    :func:`app.pipeline.report_stage.aggregates_of` 的表）。
    """
    from app.pipeline.report_stage import generate_weekly_reports

    ids = _seed(engine)
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 10), label="yellow",
                  snapshot={**SNAPSHOT, "label": "yellow", "hit_rules": ["Y1"],
                            "reason": "短板 1 项"})
    cs = _class_session(engine, ids, D(2025, 9, 9))
    _rpe(engine, cs, ids[STUDENT_NO], 7, T(2025, 9, 9, 10, 0))
    _mini(engine, ids, ids[STUDENT_NO], 1, squat=70)   # → 综合分 60.0
    _mini(engine, ids, ids[STUDENT_NO], 2, squat=82)   # → 综合分 66.0（+10.0%）
    _alert(engine, ids, level="yellow", rule_id="YELLOW_CLASS_RPE_HIGH",
           triggered_at=T(2025, 9, 10, 6, 0), window_key=f"{ids['semester']}:2")

    with Session(engine) as s:
        generate_weekly_reports(
            s, ids["semester"], ids["batch"], 2,
            as_of=D(2025, 9, 14), now=T(2025, 9, 14, 22, 0),
            exercises=exercise_library(),
        )
        s.commit()
        # ⚠️ 本学期有**两个**教学班（张老师的与李老师的），故要按班过滤——
        #    管道为每一个有名册的班各写一行。
        row = s.scalars(select(WeeklyClassReport).where(
            WeeklyClassReport.course_section_id == ids["section"])).one()
        stored = {
            "layer_distribution": row.layer_distribution,
            "rpe_summary": row.rpe_summary,
            "checkin_rate_by_layer": row.checkin_rate_by_layer,
            "progress_board": row.progress_board,
            "alert_summary": row.alert_summary,
            "suggestion": row.suggestion,
        }

    blocks = client.get(
        f"/api/dashboard/class/{ids['section']}?week=2&as_of={SUNDAY}",
        headers=TEACHER,
    ).json()["blocks"]
    live = {key: blocks[key] for key in stored}
    assert live == stored
    # 班级级黄牌命中 → 建议降量（两侧都是同一个字符串）
    assert stored["suggestion"] == "本周建议整体降量 10%"


def test_the_watermark_clips_the_rest_of_the_week(client, engine):
    """**水位线**：周三去读第 2 周 → 周四那节课的快评不在里面，而横轴仍是 7 天。"""
    ids = _seed(engine)
    wed = _class_session(engine, ids, D(2025, 9, 10), period=3)
    thu = _class_session(engine, ids, D(2025, 9, 11), period=4)
    _rpe(engine, wed, ids[STUDENT_NO], 6, T(2025, 9, 10, 10, 0))
    _rpe(engine, thu, ids[OTHER_STUDENT_NO], 10, T(2025, 9, 11, 10, 0))

    body = client.get(
        f"/api/dashboard/class/{ids['section']}?as_of={WEDNESDAY}", headers=TEACHER
    ).json()
    assert body["watermark"] == WEDNESDAY
    assert body["week"] == 2
    curve = body["blocks"]["rpe_summary"]["curve"]
    assert len(curve) == 7
    assert curve[2] == {"day": "2025-09-10", "mean": 6.0, "submissions": 1}
    assert curve[3] is None, "09-11 在水位线之后"
    assert body["blocks"]["rpe_summary"]["mean"] == 6.0


def test_a_teacher_cannot_read_a_class_they_do_not_teach(client, engine):
    """**越权**（Review Focus 第 1 条的教师侧）：李老师的工号读张老师的班 → **403**。

    ⚠️ 判据是 ``course_section.teacher_id``；两个班的 id 都在响应里说得出来，
    故本条挡的不是「猜 id」，而是「一个在册教师读到别的教师的班」。
    """
    ids = _seed(engine)
    resp = client.get(f"/api/dashboard/class/{ids['section']}?as_of={SUNDAY}",
                      headers=OTHER_TEACHER)
    assert resp.status_code == 403
    assert "不是教师" in resp.json()["error"]["message"]
    # 反过来也一样
    resp2 = client.get(
        f"/api/dashboard/class/{ids['outside_section']}?as_of={SUNDAY}", headers=TEACHER)
    assert resp2.status_code == 403


def test_a_missing_identity_header_is_401_and_a_bad_one_is_403(client, engine):
    """缺头 → **401**（本仓既有口径，不是 ``APIKeyHeader`` 缺省的 403）；
    工号不在册 → **403**。⚠️ 两档的码不同，前端据此区分「登录态坏了」与「越权」。"""
    ids = _seed(engine)
    assert client.get(f"/api/dashboard/class/{ids['section']}").status_code == 401
    resp = client.get(f"/api/dashboard/class/{ids['section']}", headers=NOBODY)
    assert resp.status_code == 403
    assert "不是一个在册教师" in resp.json()["error"]["message"]


def test_a_day_before_the_semester_starts_is_422_not_an_empty_screen(client, engine):
    """``as_of`` 早于开学日 → **422**（一句人话），而不是一份全 0 的大屏。

    ⚠️ 那一天不属于任何学期周，「本周」这个词没有指称；回一份全 0 的屏
    会让教师以为「本班这周一个人都没练」。
    """
    ids = _seed(engine)
    resp = client.get(f"/api/dashboard/class/{ids['section']}?as_of=2025-08-25",
                      headers=TEACHER)
    assert resp.status_code == 422
    assert "早于学期" in resp.json()["error"]["message"]


def test_an_explicit_week_overrides_the_one_derived_from_as_of(client, engine):
    """显式传 ``?week=1`` → 按第 1 周取数，即使 ``as_of`` 落在第 2 周。

    ⚠️ 水位线仍然是 ``min(as_of, 那一周的周日)``，故 ``week=1`` + ``as_of=09-14``
    的水位线是 **09-07**（第 1 周的周日），不是 09-14。
    """
    ids = _seed(engine)
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 5), label="green",
                  snapshot={**SNAPSHOT, "label": "green", "hit_rules": ["G1"],
                            "reason": "短板 0 项且体成分正常"})
    body = client.get(
        f"/api/dashboard/class/{ids['section']}?week=1&as_of={SUNDAY}", headers=TEACHER
    ).json()
    assert body["week"] == 1
    assert body["week_start"] == "2025-09-01"
    assert body["watermark"] == "2025-09-07"
    assert body["blocks"]["layer_distribution"]["by_layer"]["green"] == 1
    # 第 1 周没有上一周 → has_previous 为假、previous 为 null
    assert body["blocks"]["layer_distribution"]["flow"]["has_previous"] is False
    assert body["blocks"]["layer_distribution"]["previous"] is None
    assert body["blocks"]["rpe_summary"]["previous_curve"] is None


# ===========================================================================
# 支 B：周报读端点
# ===========================================================================


def _write_report(engine, ids, week, *, batch=None, suggestion="维持当前强度"):
    with Session(engine) as s:
        row = WeeklyClassReport(
            course_section_id=ids["section"], semester_id=ids["semester"], week=week,
            layer_distribution={"by_layer": {"red": 0, "yellow": 0, "green": 1,
                                             "insufficient_data": 0},
                                "previous": None, "flow": {"has_previous": False}},
            rpe_summary={"curve": [None] * 7}, checkin_rate_by_layer={},
            progress_board={"top_n": 10}, alert_summary={},
            suggestion=suggestion, generated_at=T(2025, 9, 14, 22, 0),
            batch_id=ids["batch"] if batch is None else batch,
        )
        s.add(row)
        s.commit()
        return row.id


def test_the_stored_report_is_returned_by_section_and_week(client, engine):
    """按 ``(班, 周次)`` 取**存下来的**那一行（12 列全给，含 5 个 JSON 列）。"""
    ids = _seed(engine)
    row_id = _write_report(engine, ids, 2)
    resp = client.get(
        f"/api/dashboard/weekly-class-report/{ids['section']}?week=2", headers=TEACHER)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == row_id
    assert body["week"] == 2
    assert body["suggestion"] == "维持当前强度"
    assert sorted(body) == [
        "alert_summary", "batch_id", "checkin_rate_by_layer", "course_section_id",
        "generated_at", "id", "layer_distribution", "progress_board", "rpe_summary",
        "semester_id", "suggestion", "week",
    ]


def test_the_latest_week_is_the_default(client, engine):
    """``week`` 缺省 → **已存下来的最新一周**（``ORDER BY week DESC LIMIT 1``）。

    ⚠️ 教师端的默认视图是「上周的周报」，而前端不该为了拿一个周次先调一次
    ``GET /api/weekly-class-reports``。
    """
    ids = _seed(engine)
    _write_report(engine, ids, 1)
    _write_report(engine, ids, 3, suggestion="本周建议整体降量 10%")
    _write_report(engine, ids, 2)
    body = client.get(
        f"/api/dashboard/weekly-class-report/{ids['section']}", headers=TEACHER).json()
    assert body["week"] == 3
    assert body["suggestion"] == "本周建议整体降量 10%"


def test_a_missing_report_is_404_with_its_own_code(client, engine):
    """没有周报 → **404** 且 ``code == "no_weekly_report"``（不是通用的 ``not_found``）。

    ⚠️ 那一档是**常态**（周报只在周日生成），前端要说的是一句「周日晚上生成，
    先看大屏」，不是一条错误横幅；故它必须能与「id 打错了」区分开。
    """
    ids = _seed(engine)
    resp = client.get(
        f"/api/dashboard/weekly-class-report/{ids['section']}?week=9", headers=TEACHER)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_weekly_report"
    resp2 = client.get(
        f"/api/dashboard/weekly-class-report/{ids['section']}", headers=TEACHER)
    assert resp2.status_code == 404
    assert resp2.json()["error"]["code"] == "no_weekly_report"


def test_the_report_endpoint_is_also_scoped_to_the_teaching_relation(client, engine):
    """周报端点同样过任教关系闸门：李老师的工号读张老师的班的周报 → **403**。"""
    ids = _seed(engine)
    _write_report(engine, ids, 2)
    resp = client.get(
        f"/api/dashboard/weekly-class-report/{ids['section']}?week=2",
        headers=OTHER_TEACHER)
    assert resp.status_code == 403


# ===========================================================================
# 支 C：学生端首页（spec §9.2）
# ===========================================================================


def test_the_home_page_carries_the_five_grids(client, engine):
    """**五格齐全**：分层 + 可解释性、本周训练单、待办卡片、未读红点、勋章。

    ⚠️ **本周完成度刻意不在里面**（它的唯一所有者是
    ``GET …/training-logs/completion-rate``，理由逐字见
    :class:`app.api.schemas.dashboard.StudentHomeRead` 的 docstring）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 10))
    cs = _class_session(engine, ids, D(2025, 9, 9))
    _notification(engine, sid)
    _notification(engine, sid, title="本周电子勋章")
    _notification(engine, sid, title="已读过的那一条", is_read=True)
    _notification(engine, ids[OTHER_STUDENT_NO], title="别人的消息")
    _alert(engine, ids, level="green", rule_id="GREEN_MASTERY", student_id=sid,
           triggered_at=T(2025, 9, 10, 6, 0), window_key=f"{ids['semester']}:2")

    resp = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                      headers=_student_header(sid))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body) == [
        "as_of", "badges", "pending_rpe", "semester_id", "stratification",
        "student_id", "unread_notifications", "week", "weekly_sheet",
    ]
    assert body["student_id"] == sid
    assert body["week"] == 2
    assert body["semester_id"] == ids["semester"]
    # 未读红点：本人 3 条里 2 条未读（别人的那一条不算）
    assert body["unread_notifications"] == 2
    # 勋章：本学期 GREEN_MASTERY 的条数
    assert body["badges"] == {"count": 1, "latest": "2025-09-10T06:00:00"}
    # 待办卡片：09-09 那节课发起了快评、而这个学生没交
    assert body["pending_rpe"] == [
        {"class_session_id": cs, "session_date": "2025-09-09", "period": 3}]
    # 训练单：处方 09-01 生成、4 周微周期，09-14 是它的第 2 周
    assert body["weekly_sheet"] is not None
    assert body["weekly_sheet"]["week"] == 2
    # 可解释性
    assert body["stratification"]["label"] == "red"
    assert body["stratification"]["explanation"] == _expected_explanation()


def test_the_explanation_is_the_same_prose_the_pipeline_would_render(client, engine):
    """**spec §14 #17「做」的落点**：``explanation`` 与
    :func:`app.domain.stratify.explain` 的输出**逐字相等**。

    ⚠️ 两侧不同源：一侧走 HTTP、一侧是 :func:`_expected_explanation` 在测试里
    直接调 domain 的两个纯函数（``StratResult`` + ``DerivedResult`` → ``explain``）。
    ⚠️ 而 ``label`` / ``hit_rules`` / ``reason`` 三格取的是**库里存的那一份**，
    不是重建后重算的那一份（理由逐字见
    :func:`app.api.routers.dashboard._stratification_payload` 的 docstring）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 10))
    got = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                     headers=_student_header(sid)).json()["stratification"]
    assert got["explanation"] == _expected_explanation()
    assert got["label"] == "red"
    assert got["hit_rules"] == ["R1"]
    assert got["reason"] == "短板 ≥ 2 项"
    assert got["percentile_source"] == "school"
    assert got["computed_on"] == "2025-09-10"
    assert got["input_snapshot"] == SNAPSHOT
    # ⚠️ 反空转：那段文案里真的有学生的数值（spec §9.2 的示例文案形状）
    assert "22.4" in got["explanation"]


def test_the_latest_stratification_row_wins(client, engine):
    """**当前**分层 = ``computed_on <= as_of`` 里最大的那一行（不是先插的那一行）。"""
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 3), label="red")
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 10), label="green",
                  snapshot={**SNAPSHOT, "label": "green", "hit_rules": ["G1"],
                            "reason": "短板 0 项且体成分正常"})
    # 水位线之后那一行读不到
    _stratify_row(engine, ids, STUDENT_NO, D(2025, 9, 20), label="yellow",
                  snapshot={**SNAPSHOT, "label": "yellow", "hit_rules": ["Y1"],
                            "reason": "短板 1 项"})
    got = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                     headers=_student_header(sid)).json()["stratification"]
    assert got["label"] == "green"
    assert got["computed_on"] == "2025-09-10"


def test_a_student_who_was_never_stratified_still_gets_a_home_page(client, engine):
    """**从未被分层过** → ``stratification`` 是 ``null``，而**其余四格照常给**。

    ⚠️ 首页是**一屏**：一格缺数据不该让整屏 404。这与
    :func:`app.api.routers.prescription.weekly_sheet` 的 404 刻意不同
    （那一个端点只回答一个问题，答不了就该说答不了）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    _notification(engine, sid)
    resp = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                      headers=_student_header(sid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["stratification"] is None
    assert body["unread_notifications"] == 1
    assert body["badges"] == {"count": 0, "latest": None}


def test_the_pending_cards_skip_the_sessions_already_submitted_and_the_unopened(
    client, engine
):
    """待办卡片**只含**「已发起快评 ∧ 这个学生还没交 ∧ 落在本学期周里 ``<= as_of``」的课。

    四档各造一节：① 已交（不出现）；② 没发起（不出现——那一列的语义是
    「教师点没点『发起课堂快评』」，没点就根本没有待办）；③ 上周的课（不出现）；
    ④ 本周还没交的（出现）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    done = _class_session(engine, ids, D(2025, 9, 8), period=1)
    _rpe(engine, done, sid, 6, T(2025, 9, 8, 10, 0))
    _class_session(engine, ids, D(2025, 9, 9), period=2, opened=False)
    _class_session(engine, ids, D(2025, 9, 3), period=3)      # 上一周
    todo = _class_session(engine, ids, D(2025, 9, 10), period=4)
    _class_session(engine, ids, D(2025, 9, 12), period=5)    # as_of 之后（水位线之外）

    body = client.get(f"/api/students/{sid}/home?as_of={WEDNESDAY}",
                      headers=_student_header(sid)).json()
    assert [card["class_session_id"] for card in body["pending_rpe"]] == [todo]


def test_the_home_page_turns_both_404s_of_the_weekly_sheet_into_null(client, engine):
    """训练单那**两档 404** 在首页上都是 ``null``（⚠️ 硬规矩 #107 的谓词反例）。

    ① 没有生效处方 → ``no_active_prescription``；② 有处方、但 ``as_of`` 落在
    微周期之外 → ``outside_microcycle``。两档都要被折成 ``null``，
    否则一个 ``JSONResponse`` 会被当成训练单塞进 ``weekly_sheet`` 那一格
    （而它是一个 ``{"error": …}`` 形状，前端会渲染出一屏乱码）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    # ① 删掉处方 → no_active_prescription
    with Session(engine) as s:
        s.delete(s.get(Prescription, ids[f"prescription_{STUDENT_NO}"]))
        s.commit()
    body = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                      headers=_student_header(sid)).json()
    assert body["weekly_sheet"] is None
    # 反证：那个端点自己**确实**回 404（否则上面的 null 可能只是「压根没查」）
    direct = client.get(f"/api/students/{sid}/weekly-sheet?as_of={SUNDAY}",
                        headers=_student_header(sid))
    assert direct.status_code == 404
    assert direct.json()["error"]["code"] == "no_active_prescription"

    # ② 把 valid_to 设成 NULL 且 generated_on 推到很久以前 → current_week 返回 None
    #    （⚠️ 这是那一档**唯一**的可达路径：valid_to 有值且已过期时，
    #    _current_prescription 会先把它滤掉、报的是「没有生效的处方」那一档）
    with Session(engine) as s:
        row = s.get(Prescription, ids[f"prescription_{OTHER_STUDENT_NO}"])
        row.generated_on = D(2025, 5, 1)
        row.valid_from = D(2025, 5, 1)
        row.valid_to = None
        s.commit()
    sid2 = ids[OTHER_STUDENT_NO]
    body2 = client.get(f"/api/students/{sid2}/home?as_of={SUNDAY}",
                       headers=_student_header(sid2)).json()
    assert body2["weekly_sheet"] is None
    direct2 = client.get(f"/api/students/{sid2}/weekly-sheet?as_of={SUNDAY}",
                         headers=_student_header(sid2))
    assert direct2.status_code == 404
    assert direct2.json()["error"]["code"] == "outside_microcycle"


def test_a_student_cannot_read_another_students_home(client, engine):
    """**越权**（Review Focus 第 1 条）：学生 A 用 ``X-Student-Id: B`` 读 B 的首页 → **403**。"""
    ids = _seed(engine)
    a, b = ids[STUDENT_NO], ids[OTHER_STUDENT_NO]
    resp = client.get(f"/api/students/{b}/home?as_of={SUNDAY}",
                      headers=_student_header(a))
    assert resp.status_code == 403
    assert "无权访问" in resp.json()["error"]["message"]
    # 缺头 → 401
    assert client.get(f"/api/students/{b}/home").status_code == 401


def test_the_home_page_does_not_carry_a_completion_rate(client, engine):
    """**完成度那一格刻意不在首页**：它的唯一所有者是 ``…/completion-rate`` 端点。

    ⚠️ 本条钉的是「不出现第二个所有者」这件事本身：响应体里一个
    ``completion`` / ``rate`` 形状的键都不该有。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    body = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                      headers=_student_header(sid)).json()
    assert "completion_rate" not in body
    assert not [key for key in body if "completion" in key or "rate" in key]
    # 而那个端点自己是好的（否则「不在首页」可能只是因为它坏了）。
    # ⚠️ 它的 ``semester_id`` 与 ``week`` 都是**必填查询参数**（它要学期第一天
    #    才能定位这一周的 7 天），少了任一个都会 422 —— 本条因此显式传。
    ok = client.get(
        f"/api/students/{sid}/training-logs/completion-rate"
        f"?as_of={SUNDAY}&semester_id={ids['semester']}&week=2",
        headers=_student_header(sid))
    assert ok.status_code == 200, ok.text
    assert "completion_rate" in ok.json()


# ===========================================================================
# 支 D：P8-A5 —— 教师端读单个学生的训练单
# ===========================================================================


def test_the_teacher_and_the_student_variants_return_the_same_body(client, engine):
    """**同一份数据的同一个契约**：教师端与学生端两个端点的响应体**逐字相等**。

    ⚠️ 两侧不同源：一次用 ``X-Teacher-Staff-No``、一次用 ``X-Student-Id``，
    走的是两条不同的路径与两道不同的闸门，而它们必须给出同一个训练单
    （两处共用 :func:`app.api.routers.prescription._weekly_sheet_response`）。
    ⚠️ 而 ``/openapi.json`` 上两个端点指向**同一个** ``WeeklySheetRead``。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    as_student = client.get(f"/api/students/{sid}/weekly-sheet?as_of={SUNDAY}",
                            headers=_student_header(sid))
    as_teacher = client.get(
        f"/api/teacher/students/{sid}/weekly-sheet?as_of={SUNDAY}", headers=TEACHER)
    assert as_student.status_code == 200, as_student.text
    assert as_teacher.status_code == 200, as_teacher.text
    assert as_teacher.json() == as_student.json()

    spec = client.get("/openapi.json").json()
    student_ref = spec["paths"]["/api/students/{student_id}/weekly-sheet"]["get"]
    teacher_ref = spec["paths"]["/api/teacher/students/{student_id}/weekly-sheet"]["get"]
    assert (student_ref["responses"]["200"]["content"]["application/json"]["schema"]
            == teacher_ref["responses"]["200"]["content"]["application/json"]["schema"])
    assert student_ref["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WeeklySheetRead"}


def test_a_student_identity_header_is_401_on_the_teacher_variant(client, engine):
    """**Task 4 留下的那个缺口**：学生身份头调教师端变体 → **401**（缺教师头）。

    ⚠️ 反过来的那一半同样要钉：教师头调**学生侧**那个端点也是 401
    （那个端点刻意不接受 ``X-Teacher-Staff-No``，理由逐字见
    :mod:`app.api.routers.prescription` 的模块 docstring）。
    于是「教师用哪一条路径」这件事在两个方向上都是响亮的。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    assert client.get(f"/api/teacher/students/{sid}/weekly-sheet",
                      headers=_student_header(sid)).status_code == 401
    assert client.get(f"/api/students/{sid}/weekly-sheet",
                      headers=TEACHER).status_code == 401


def test_a_teacher_cannot_read_a_student_outside_their_sections(client, engine):
    """**任教关系校验**（简报 P8-A5 点名的那条链：``enrollment`` + ``course_section.teacher_id``）。

    李老师的班上那个学生，张老师读不到 → **403**。
    ⚠️ 而张老师**自己班上**的两个学生都读得到（反空转：否则本条可能只是因为
    闸门把所有人都挡了）。
    """
    ids = _seed(engine)
    outsider = ids[OUTSIDER_NO]
    resp = client.get(f"/api/teacher/students/{outsider}/weekly-sheet?as_of={SUNDAY}",
                      headers=TEACHER)
    assert resp.status_code == 403
    assert "不在教师" in resp.json()["error"]["message"]
    # 反证：李老师自己读得到
    assert client.get(
        f"/api/teacher/students/{outsider}/weekly-sheet?as_of={SUNDAY}",
        headers=OTHER_TEACHER).status_code == 200
    # 反证：张老师读得到自己班上的两个人
    for student_no in (STUDENT_NO, OTHER_STUDENT_NO):
        assert client.get(
            f"/api/teacher/students/{ids[student_no]}/weekly-sheet?as_of={SUNDAY}",
            headers=TEACHER).status_code == 200


def test_teaching_last_semester_does_not_grant_access_this_semester(client, engine):
    """**``semester_id`` 相等是承重的**：上学期教过他 ≠ 这学期能读他。

    ⚠️ 造法：给同一个学生再加一行**上学期**的选课（另一个学期 + 张老师的另一个班），
    而这学期他在李老师的班上。少了 ``CourseSection.semester_id ==
    Enrollment.semester_id`` 那一格，本条会**绿**（他能读到），而那正是本闸门要挡的形状。
    """
    ids = _seed(engine)
    with Session(engine) as s:
        prev = Semester(name="2024-2025-2", start_date=D(2025, 2, 24),
                        end_date=D(2025, 6, 15), weeks=16, is_current=False)
        s.add(prev)
        s.flush()
        teacher = s.scalar(select(Teacher).where(Teacher.staff_no == TEACHER_NO))
        old_section = CourseSection(semester_id=prev.id, teacher_id=teacher.id,
                                    name="上学期的体育课", grouping_mode="administrative")
        s.add(old_section)
        s.flush()
        outsider = s.scalar(select(Student).where(Student.student_no == OUTSIDER_NO))
        s.add(Enrollment(semester_id=prev.id, student_id=outsider.id,
                         course_section_id=old_section.id))
        s.commit()
        outsider_id = outsider.id

    resp = client.get(
        f"/api/teacher/students/{outsider_id}/weekly-sheet?as_of={SUNDAY}",
        headers=TEACHER)
    assert resp.status_code == 403
    assert "上学期教过他不等于这学期能读他" in resp.json()["error"]["message"]
    # ⚠️ 反空转：同一位教师读**自己本学期班上**的学生仍然是 200，
    #    故上面的 403 不是「闸门把所有人都挡了」
    assert client.get(
        f"/api/teacher/students/{ids[STUDENT_NO]}/weekly-sheet?as_of={SUNDAY}",
        headers=TEACHER).status_code == 200


def test_the_teacher_variant_shares_the_two_404_codes(client, engine):
    """教师端变体的**两档 404** 与学生侧逐字同码（同一个所有者）。"""
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    with Session(engine) as s:
        s.delete(s.get(Prescription, ids[f"prescription_{STUDENT_NO}"]))
        s.commit()
    resp = client.get(f"/api/teacher/students/{sid}/weekly-sheet?as_of={SUNDAY}",
                      headers=TEACHER)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_active_prescription"


def test_a_non_integer_path_parameter_is_422(client, engine):
    """``/api/teacher/students/abc/weekly-sheet`` → **422**（路径参数转 ``int`` 失败）。

    ⚠️ 本条也是「include 顺序」的一个反空转：若本 router 被 include 在
    :mod:`app.api.routers.catalog` **之后**、而某个泛型资源的路径与它同形，
    那一段字面量会被当成别的主键去转 ``int``，得到的报错会指向另一个字段名。
    """
    resp = client.get("/api/teacher/students/abc/weekly-sheet", headers=TEACHER)
    assert resp.status_code == 422
    assert "student_id" in resp.text


# ===========================================================================
# 支 E：通知已读
# ===========================================================================


def test_marking_a_notification_read_flips_is_read(client, engine):
    """``POST /api/notifications/{id}/read`` → **200** + 那一行的 ``is_read`` 翻成 ``True``。

    ⚠️ 回 200 不回 201、不带 ``Location``：这是对已存在的资源做了一次**操作**
    （与本模块的 ``handle``、Task 4 的两个 POST 同一条约定）。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    note = _notification(engine, sid)
    resp = client.post(f"/api/notifications/{note}/read", headers=_student_header(sid))
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_read"] is True
    assert resp.json()["id"] == note
    with Session(engine) as s:
        assert s.get(Notification, note).is_read is True
    # 而首页的红点跟着少了一个
    home = client.get(f"/api/students/{sid}/home?as_of={SUNDAY}",
                      headers=_student_header(sid)).json()
    assert home["unread_notifications"] == 0


def test_marking_twice_is_still_200(client, engine):
    """**幂等**：对一条已读的消息再标一次仍是 200（弱网重试不是错误）。"""
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    note = _notification(engine, sid, is_read=True)
    assert client.post(f"/api/notifications/{note}/read",
                       headers=_student_header(sid)).status_code == 200
    assert client.post(f"/api/notifications/{note}/read",
                       headers=_student_header(sid)).status_code == 200


def test_a_student_cannot_mark_another_students_notification_read(client, engine):
    """**越权**：别人的消息 → **403** + ``not_recipient``，且那一行**一个字都没动**。"""
    ids = _seed(engine)
    a, b = ids[STUDENT_NO], ids[OTHER_STUDENT_NO]
    note = _notification(engine, b)
    resp = client.post(f"/api/notifications/{note}/read", headers=_student_header(a))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "not_recipient"
    with Session(engine) as s:
        assert s.get(Notification, note).is_read is False


def test_an_unknown_notification_id_is_403_not_404(client, engine):
    """**「不存在」与「不是你的」同形**（都是 403 + ``not_recipient``）。

    ⚠️ ``notification.id`` 是**连续的代理键**，故区分两者等于让「扫一遍 id
    看哪些存在」成为一次有效的探测。口径逐字同
    :func:`app.api.deps.require_scope`（那一条也两支都报 403）。
    ⚠️ 「存在但不是你的」那一半由
    :func:`test_a_student_cannot_mark_another_students_notification_read` 钉住，
    本条只钉「不存在」那一半——两条**必须给出同一个码与同一个 message 前缀**，
    否则前端就能按码把两档分开，而那正是本条要防的泄露。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    missing = client.post("/api/notifications/999999/read",
                          headers=_student_header(sid))
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "not_recipient"

    not_mine = _notification(engine, ids[OTHER_STUDENT_NO])
    foreign = client.post(f"/api/notifications/{not_mine}/read",
                          headers=_student_header(sid))
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "not_recipient"
    # ⚠️ 两档**同形**的可观测量：同一个码，且两条 message 都同时说「不是发给你的」
    #    与「或它不存在」——即响应里没有任何一格能让调用方把两档分开。
    for resp in (missing, foreign):
        assert resp.json()["error"]["code"] == "not_recipient"
        assert "不是发给学生" in resp.json()["error"]["message"]
        assert "或它不存在" in resp.json()["error"]["message"]


def test_a_teacher_recipient_notification_cannot_be_marked_by_a_student(client, engine):
    """收件人是**教师**的那一条（``recipient_kind = "teacher"``），学生头标不动。

    ⚠️ ``recipient_id`` **不是外键**、是多态的（``"student"`` 时指 ``student.id``、
    ``"teacher"`` 时指 ``teacher.id``），故一条 ``recipient_kind = "teacher"`` ∧
    ``recipient_id = 1`` 的消息与 ``id = 1`` 的那个学生在库里**同形**。
    ⚠️ 本条因此**刻意**把那条教师消息的 ``recipient_id`` 造成与请求者相同的整数
    （``recipient_id`` 那一列不做外键校验，故写得进去）：少了
    ``recipient_kind = "student"`` 那一格判据，本条会**绿不了**——
    学生 1 就能把「发给教师 1 的班级黄牌通知」标成已读，
    而那位教师大屏上的红点就此消失，且全链路不报错。
    """
    ids = _seed(engine)
    sid = ids[STUDENT_NO]
    note = _notification(engine, sid, kind="teacher", title="课堂 RPE 均值偏高")
    with Session(engine) as s:
        # 反空转：那一行的 recipient_id 确实**等于**请求者的学号代理键
        assert s.get(Notification, note).recipient_id == sid
        assert s.get(Notification, note).recipient_kind == "teacher"

    resp = client.post(f"/api/notifications/{note}/read", headers=_student_header(sid))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "not_recipient"
    with Session(engine) as s:
        assert s.get(Notification, note).is_read is False


def test_the_read_endpoint_requires_the_student_header(client, engine):
    """缺 ``X-Student-Id`` → **401**；教师头调它 → **401**（本端点只做学生侧）。

    ⚠️ **教师侧的「标已读」今天没有端点**（如实记录，硬规矩 #39）：
    spec §9.1 的大屏版面里没有消息中心，而教师确实会收到班级黄牌的通知
    （:func:`app.pipeline.alert_stage._notify`）。已登记为关切，留给 Plan 04 决定
    要不要做——⚠️ 而做它的正确形状是**另一条路径**（教师身份 + ``recipient_kind =
    "teacher"``），不是把本端点改成「学生或教师任一即可」（那要判两条规则，
    而两条规则的失败码不同，理由逐字见 :mod:`app.api.routers.prescription`）。
    """
    ids = _seed(engine)
    note = _notification(engine, ids[STUDENT_NO])
    assert client.post(f"/api/notifications/{note}/read").status_code == 401
    assert client.post(f"/api/notifications/{note}/read",
                       headers=TEACHER).status_code == 401


# ===========================================================================
# 支 F：前后端对接面（P4-A5 的 securityScheme + 响应模型的字段集）
# ===========================================================================


def test_the_five_new_endpoints_declare_the_right_security_scheme(client):
    """五个新端点各挂着**对的那一格** securityScheme（教师侧三个 + 学生侧两个）。

    ⚠️ 全仓那份清单由
    ``tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes``
    持有（本 Task 把它从 12 项扩到 **17** 项）；本条是它的**局部复读**，
    目的是让「Task 8 加了哪五个」在本文件里可读，而不必去另一个文件里翻。
    ⚠️ 两处并存而**不合并**：那一条是「除清单之外无 security」的全仓级断言，
    本条只钉 Task 8 那五个的**方向**（指错一格的话 Swagger 会让教师端点收学生头）。
    """
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    expected = {
        ("/api/dashboard/class/{course_section_id}", "get"): "X-Teacher-Staff-No",
        ("/api/dashboard/weekly-class-report/{course_section_id}", "get"):
            "X-Teacher-Staff-No",
        ("/api/teacher/students/{student_id}/weekly-sheet", "get"):
            "X-Teacher-Staff-No",
        ("/api/students/{student_id}/home", "get"): "X-Student-Id",
        ("/api/notifications/{notification_id}/read", "post"): "X-Student-Id",
    }
    assert len(expected) == 5
    for (key, method), name in expected.items():
        assert paths[key][method]["security"] == [{name: []}], (key, method)


def test_the_response_models_match_the_domain_payloads_field_for_field(client, engine):
    """**16 个响应模型的字段集与 domain 的输出逐字段对账**（两侧不同源）。

    ⚠️ 期望侧是 :mod:`app.domain.report` 那九个函数**现场跑出来**的键集，
    另一侧是 ``/openapi.json`` 里那些 schema 的 ``properties``。
    它挡的是两个方向：① domain 加了一个键而 schema 没跟着加 → Pydantic 会
    **静默丢掉**它（大屏少一块，而响应仍是 200）；② schema 多写了一个键 →
    OpenAPI 上有一个永远为 ``null`` 的字段，前端会为它写一段渲染代码。
    """
    from app.domain import report as domain_report
    from app.domain.report import RpeWeek

    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    # --- layer_distribution / flow -----------------------------------------
    dist = domain_report.layer_distribution({1: "red"}, None)
    assert set(schemas["LayerDistributionRead"]["properties"]) == set(dist)
    flow = domain_report.layer_flow({1: "red"}, None)
    assert set(schemas["LayerFlowRead"]["properties"]) == set(flow)

    # --- rpe_summary / 曲线上的点 -------------------------------------------
    summary = domain_report.rpe_summary(
        RpeWeek(days=("2025-09-08",), values={"2025-09-08": [6]}), None)
    assert set(schemas["RpeSummaryRead"]["properties"]) == set(summary)
    point = domain_report.daily_mean_rpe(("2025-09-08",), {"2025-09-08": [6]})[0]
    assert set(schemas["RpePointRead"]["properties"]) == set(point)

    # --- 按层完成率 / 进步榜 / 异常名单 --------------------------------------
    rate = domain_report.checkin_rate_by_layer({1: 0.5}, {1: "red"})["red"]
    assert set(schemas["LayerRateRead"]["properties"]) == set(rate)
    board = domain_report.progress_board({1: (60.0, 66.0)})
    assert set(schemas["ProgressBoardRead"]["properties"]) == set(board)
    assert set(schemas["ProgressEntryRead"]["properties"]) == set(board["top"][0])
    entry = domain_report.abnormal_roster({1: 4}, {1: [9]})[0]
    assert set(schemas["AbnormalEntryRead"]["properties"]) == set(entry)

    # --- 七个键的那一层 ------------------------------------------------------
    ids = _seed(engine)
    blocks = client.get(
        f"/api/dashboard/class/{ids['section']}?as_of={SUNDAY}", headers=TEACHER
    ).json()["blocks"]
    assert set(schemas["ClassBlocksRead"]["properties"]) == set(blocks)
    assert len(schemas["ClassBlocksRead"]["properties"]) == 7

    # --- 大屏整屏 / 首页 -----------------------------------------------------
    screen = client.get(
        f"/api/dashboard/class/{ids['section']}?as_of={SUNDAY}", headers=TEACHER
    ).json()
    assert set(schemas["ClassDashboardRead"]["properties"]) == set(screen)
    assert set(schemas["ThresholdLinesRead"]["properties"]) == set(
        screen["rpe_threshold_lines"])
    assert set(schemas["ScreenThresholdsRead"]["properties"]) == set(
        screen["screen_thresholds"])
    home = client.get(
        f"/api/students/{ids[STUDENT_NO]}/home?as_of={SUNDAY}",
        headers=_student_header(ids[STUDENT_NO]),
    ).json()
    assert set(schemas["StudentHomeRead"]["properties"]) == set(home)
    assert set(schemas["BadgeRead"]["properties"]) == set(home["badges"])
    assert set(schemas["PendingRpeRead"]["properties"]) == {
        "class_session_id", "session_date", "period"}
    assert set(schemas["StratificationRead"]["properties"]) == {
        "label", "hit_rules", "reason", "explanation", "percentile_source",
        "computed_on", "input_snapshot"}


def test_the_dashboard_schemas_are_not_part_of_the_crud_matrix(client):
    """本模块的 16 个模型**一个都不在** 23 个资源的 CRUD 目录里。

    ⚠️ 那条「14 + 9 × 3 = 41」的算式数的是**资源**（守卫
    ``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned`` 数的是
    ``RESOURCES``），故本 Task 加 16 个模型**不动**它——本条把这句话变成可执行的。
    """
    from app.api.routers.catalog import RESOURCES
    from app.api.schemas import dashboard as dashboard_schemas

    assert len(RESOURCES) == 23
    assert len(dashboard_schemas.__all__) == 16
    resource_models = set()
    for resource in RESOURCES:
        for model in resource["schemas"].__dict__.values():
            if hasattr(model, "__name__"):
                resource_models.add(model.__name__)
    assert not (resource_models & set(dashboard_schemas.__all__)), (
        f"dashboard 的模型混进了 CRUD 三件套：{resource_models & set(dashboard_schemas.__all__)}"
    )


# ===========================================================================
# 支 G：end-to-end —— 真跑一遍管道，再打这四个端点
# ===========================================================================


def test_the_whole_screen_survives_a_real_pipeline_run(client, engine, tmp_path):
    """**真数据上的一整屏**：``seed_database`` + ``run_daily`` 之后，四个端点都好用。

    ⚠️ 本条是 :func:`test_the_explanation_is_the_same_prose_the_pipeline_would_render`
    之外**唯一**能证明「管道真的会写出 :func:`app.api.routers.dashboard._stratification_payload`
    读得回来的那一份 ``input_snapshot``」的守卫：上面那些测试用的都是**手写的**快照
    （只含端点真的会读的键），而管道写的是 28 个键。少了本条，
    ``input_snapshot`` 改一个键名（例如 ``W`` → ``weakness_count``）不会让任何一条
    手写快照的测试变红，而学生首页会在**生产数据**上 500。

    ⚠️ 它也顺带钉住了 P8-A5 那条链在**真实编班**上成立：seed 的 60 人会铺出
    若干个行政班 + 分层班，每个班都挂一位教师、每个学生都有选课行，
    故「教师读自己班上的学生」这一档在真数据上必须 200。

    ⚠️ 数据一律落在 ``tmp_path``（不碰 ``backend/pe.db``，也不往
    ``backend/data/seed/`` 写任何东西；口径逐字同 ``tests/pipeline/test_daily.py``）。
    ⚠️ 2025-09-15 是**周一**，故本条不生成周报（``run_daily`` 的周日判据）；
    周报那一格由 ``tests/pipeline/test_report_stage.py`` 的三条边界测试钉住。
    """
    from app.adapters.mock_lepao import MockLePaoAdapter
    from app.pipeline.daily import run_daily
    from app.seed.config import SeedConfig
    from app.seed.generate import build_dataset, seed_database, write_csv

    cfg = SeedConfig(students=60, weeks=16, seed=20250828)
    csv_dir = tmp_path / "lepao"
    write_csv(build_dataset(cfg), csv_dir)
    with Session(engine) as s:
        seed_database(s, cfg)
        s.commit()
        sem = s.scalar(select(Semester.id).where(Semester.name == "2025-2026-1"))
        run_daily(s, sem, "2025-09-15", MockLePaoAdapter(csv_dir))
        s.commit()
        # 挑一个**被分层过**的学生（insufficient_data 也是分层过）
        row = s.execute(
            select(M.StratificationResult.student_id, M.StratificationResult.label)
            .order_by(M.StratificationResult.student_id).limit(1)
        ).one()
        student_id, label = row
        # 他所在的一个班，与那位班的教师工号
        enrol = s.execute(
            select(CourseSection.id, Teacher.staff_no)
            .join(Enrollment, Enrollment.course_section_id == CourseSection.id)
            .join(Teacher, Teacher.id == CourseSection.teacher_id)
            .where(Enrollment.student_id == student_id)
            .order_by(CourseSection.id).limit(1)
        ).one()
        section_id, staff_no = enrol
        # 周报在周一不生成
        assert s.scalar(select(func.count()).select_from(WeeklyClassReport)) == 0

    headers = {"X-Teacher-Staff-No": staff_no}

    # ① 教师大屏：现算，故周一也有数
    screen = client.get(f"/api/dashboard/class/{section_id}?as_of=2025-09-15",
                        headers=headers)
    assert screen.status_code == 200, screen.text
    blocks = screen.json()["blocks"]
    assert sum(blocks["layer_distribution"]["by_layer"].values()) > 0
    assert blocks["layer_distribution"]["flow"]["has_previous"] is False, (
        "学期第 2 周而第 1 周只跑了一天（09-15 是本学期的第一批），"
        "故上一周没有分层快照 → 「不知道」不得讲成「变化了」"
    )
    assert len(blocks["rpe_summary"]["curve"]) == 7
    assert blocks["progress_board"]["top_n"] == 10
    assert blocks["suggestion"] in (
        "本周建议整体降量 10%", "本周建议整体加量 10%", "维持当前强度")
    assert screen.json()["rpe_threshold_lines"] == {
        "class_mean_max": 7.0, "sustained_min": 9.0}
    assert screen.json()["screen_thresholds"] == {"gap_days": 3, "rpe_max": 8}

    # ② 周报读端点：周一还没生成 → 404 + 自己的 code
    missing = client.get(f"/api/dashboard/weekly-class-report/{section_id}",
                         headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "no_weekly_report"

    # ③ 学生首页：**管道写出来的那份 input_snapshot 能被重建**
    home = client.get(f"/api/students/{student_id}/home?as_of=2025-09-15",
                      headers={"X-Student-Id": str(student_id)})
    assert home.status_code == 200, home.text
    payload = home.json()
    assert payload["stratification"] is not None
    assert payload["stratification"]["label"] == label
    # ⚠️ 本条的牙：explanation 是一段**含学生数值**的中文长文案，不是空串、
    #    也不是一个异常被吞掉之后的占位符
    assert len(payload["stratification"]["explanation"]) > 20
    assert payload["stratification"]["explanation"].startswith(
        ("红色层", "黄色层", "绿色层", "数据不足"))
    # ⚠️ 2025-09-15 − 2025-09-01 = 14 天 → 14 // 7 + 1 = **学期第 3 周**
    #    （第 1 周 = 09-01..07、第 2 周 = 09-08..14、第 3 周 = 09-15..21）
    assert payload["week"] == 3

    # ④ 教师端读单个学生的训练单（P8-A5 那条链在真实编班上成立）
    sheet = client.get(
        f"/api/teacher/students/{student_id}/weekly-sheet?as_of=2025-09-15",
        headers=headers)
    assert sheet.status_code == 200, sheet.text
    # ⚠️ 这一格是**处方**周次，不是学期周次：本条只跑了 09-15 一批，故处方就是
    #    那天生成的（``generated_on = 2025-09-15``），``current_week(09-15, 09-15, 4) = 1``。
    #    两个口径在「处方生成日 ≠ 学期第一天」时就会错开，而那正是真实数据里的常态
    #    （:func:`app.pipeline.alert_stage.semester_week_of` 的 docstring 逐字写了这件事）。
    assert sheet.json()["week"] == 1
    # ⚠️ 与学生侧那个端点**逐字相同**（真数据上的那一次对账）
    as_student = client.get(f"/api/students/{student_id}/weekly-sheet?as_of=2025-09-15",
                            headers={"X-Student-Id": str(student_id)})
    assert as_student.status_code == 200, as_student.text
    assert sheet.json() == as_student.json()
