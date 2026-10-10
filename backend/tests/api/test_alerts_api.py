"""``POST /api/alerts/{alert_id}/handle`` 的守卫（Plan 03 Task 7）。

**四支**：

* **支 A（三档动作）**：``reduce_20pct`` / ``ignore`` / ``note`` 各自改什么、发什么、
  ``status`` 落到哪一档。
* **支 B（重复处置 → 409）**：简报 Task 7「决定」最后一条逐字要求的
  ``test_handling_an_alert_twice_is_409``，以及它真正要挡的那个失效——
  「减量 20%」被点两次而本周的量被连乘成 ``0.64``。
* **支 C（服务端填的那两格）**：``handled_action`` / ``handled_at`` 客户端伪造不了。
* **支 D（词表与路由）**：三档动作的唯一所有者是 schema 的 ``HANDLE_ACTIONS``；
  本端点与泛型 CRUD 的五个端点**不同形**，故 include 顺序今天不承重（但仍是特例在前）。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律字面写在测试里
（``"handled"`` / ``0.8`` / ``"auto"`` / 那些日期与标题），**不从被测模块读回来**。
"""
import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.api.routers.alerts as alerts_router
from app.api.schemas.alerts import HANDLE_ACTIONS
from app.db import models as M
from app.db.models.feedback import Alert, Notification
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student, Teacher
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, assemble
from app.pipeline.alert_stage import AUTO_REDUCTION_FACTOR, AUTO_SOURCE
from app.pipeline.prescription_stage import training_package_payload
from app.refdata_prescription import exercises as exercise_library
from app.refdata_prescription import templates as template_library

D = dt.date
T = dt.datetime

SEMESTER_START = D(2025, 9, 1)
GENERATED_ON = SEMESTER_START
MICROCYCLE_WEEKS = 4
#: ``valid_to = generated_on + 4 周 − 1 天``（闭区间末日）。
VALID_TO = D(2025, 9, 28)
GREEN_TEMPLATE = "GRN-END-NOR-14"
TEACHER_STAFF_NO = "T2025001"
TEACHER = {"X-Teacher-Staff-No": TEACHER_STAFF_NO}
#: 一个**不在册**的工号（``require_teacher`` 要 403 的那一档）。
NOBODY = {"X-Teacher-Staff-No": "NOBODY"}
STUDENT_NO = "S2025001"
#: 本端点用到的「那一天」：处方第 3 周（``current_week(09-01, 09-15, 4) == 3``）、
#: 学期第 3 周、且落在 ``valid_from..valid_to`` 之内。
AS_OF = "2025-09-15"
MOMENT = T(2025, 9, 15, 14, 30)


@pytest.fixture
def frozen(monkeypatch):
    """把 :func:`app.api.routers.alerts._now_local` 换成一个固定时刻。

    ⚠️ **换的是本模块的那一个绑定**（它是 ``from … import _now_local`` 进来的），
    换 ``app.api.routers.feedback._now_local`` 对本端点毫无作用——那正是
    「时钟住址是模块级的」这件事的一个后果。
    """
    monkeypatch.setattr(alerts_router, "_now_local", lambda: MOMENT)


def _profile() -> StudentProfile:
    return StudentProfile(
        student_id=1, sex=Sex.MALE, birth=D(2005, 3, 4), age=20,
        endurance_score=70.0, bmi=None, body_fat_pct=None, muscle_mass_kg=None,
        muscle_p10=None, measured_hrmax=None,
    )


def _seed(engine, *, level="red", rule_id="RED_RPE_SUSTAINED", status="pending",
          student_id_column=True, with_prescription=True,
          generated_on=GENERATED_ON, valid_to=VALID_TO) -> dict:
    """一套最小可用的行 + **一条待处置的预警**，返回 ``{名字: id}``。"""
    ids: dict = {}
    with Session(engine) as s:
        semester = Semester(name="2025-2026-1", start_date=SEMESTER_START,
                            end_date=D(2025, 12, 22), weeks=16, is_current=True)
        teacher = Teacher(staff_no=TEACHER_STAFF_NO, name="张老师")
        s.add_all([semester, teacher])
        s.flush()
        ids["semester"], ids["teacher"] = semester.id, teacher.id

        section = CourseSection(semester_id=semester.id, teacher_id=teacher.id,
                                name="体育(1)班", grouping_mode="administrative")
        s.add(section)
        s.flush()
        ids["section"] = section.id

        student = Student(student_no=STUDENT_NO, name="学生一", sex="male",
                          birth=D(2005, 3, 4), department=None, grade=1)
        s.add(student)
        s.flush()
        ids["student"] = student.id
        s.add(Enrollment(semester_id=semester.id, student_id=student.id,
                         course_section_id=section.id))

        run = M.DailySyncRun(semester_id=semester.id, business_date=GENERATED_ON,
                             started_at=T(2025, 9, 1, 2, 0), status="success")
        s.add(run)
        s.flush()
        ids["batch"] = run.id

        if with_prescription:
            package = assemble(_profile(), template_library()[GREEN_TEMPLATE],
                               generated_on, exercises=exercise_library())
            row = Prescription(
                student_id=student.id, generated_on=generated_on, batch_id=run.id,
                template_ref=GREEN_TEMPLATE, microcycle_weeks=MICROCYCLE_WEEKS,
                label_at_generation="green",
                training_package=training_package_payload(package),
                assembly_snapshot=dict(package.assembly_snapshot),
                safety_substitutions=[], teacher_overrides=[],
                previous_had_overrides=False, status="active",
                valid_from=generated_on, valid_to=valid_to,
                trigger_reasons=["first_stratification"],
            )
            s.add(row)
            s.flush()
            ids["prescription"] = row.id

        alert = Alert(
            # ⚠️ ck_alert_subject_is_exactly_one：两个作用域列**恰好一个**非空
            student_id=student.id if student_id_column else None,
            course_section_id=None if student_id_column else section.id,
            semester_id=semester.id,
            subject_key=(f"student:{student.id}" if student_id_column
                         else f"section:{section.id}"),
            level=level, rule_id=rule_id,
            trigger_snapshot={"rpe_streak": 3, "rpe_min": 9.0, "streak": 3,
                              "alert_rules_version": "1.0"},
            triggered_at=T(2025, 9, 15, 6, 0), status=status, batch_id=run.id,
            window_key="rpe1",
        )
        s.add(alert)
        s.commit()
        ids["alert"] = alert.id
    return ids


def _adjustments(engine) -> list:
    with Session(engine) as s:
        return list(s.scalars(select(WeeklyAdjustment).order_by(WeeklyAdjustment.id)))


def _notifications(engine) -> list:
    with Session(engine) as s:
        return list(s.scalars(select(Notification).order_by(Notification.id)))


def _alert(engine, alert_id: int) -> dict:
    """按主键读一行并**取出要的字段**（用完即关的会话，故不能返回 ORM 实例）。"""
    with Session(engine) as s:
        row = s.get(Alert, alert_id)
        return {"status": row.status, "handled_action": row.handled_action,
                "handled_at": row.handled_at}


def _post(client, alert_id: int, body: dict, headers=TEACHER, as_of=AS_OF) -> object:
    url = f"/api/alerts/{alert_id}/handle"
    if as_of is not None:
        url = f"{url}?as_of={as_of}"
    return client.post(url, json=body, headers=headers)


# ===========================================================================
# 支 A：三档动作
# ===========================================================================


def test_reduce_20pct_writes_an_auto_adjustment_and_pushes_to_the_student(
        client, engine, frozen):
    """``reduce_20pct``：写调整 + 发消息 + ``status = "handled"``（简报的决定逐字）。"""
    ids = _seed(engine)
    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["action"] == "reduce_20pct"
    assert body["alert"]["status"] == "handled"
    assert body["alert"]["handled_action"] == "reduce_20pct"
    assert body["alert"]["handled_at"] == MOMENT.isoformat()

    # ⚠️ source 是 **"auto"** 而不是 "teacher"：管道在触发那天已经写过一条同键的了，
    #    两个不同的 source 等于两个不同的唯一键，于是同一周会叠成 0.8 × 0.8 = 0.64
    adjustment = body["adjustment"]
    assert adjustment is not None
    assert adjustment["source"] == "auto"
    assert adjustment["factor"] == 0.8
    assert adjustment["reason"] == "RED_RPE_SUSTAINED"
    # current_week(2025-09-01, 2025-09-15, 4) == 3
    assert adjustment["week"] == 3
    assert adjustment["prescription_id"] == ids["prescription"]
    # ⚠️ batch_id 取**处方自己的**（教师手工发起的写入没有自己的批次）
    assert adjustment["batch_id"] == ids["batch"]

    rows = _adjustments(engine)
    assert len(rows) == 1
    assert rows[0].factor == AUTO_REDUCTION_FACTOR
    assert rows[0].source == AUTO_SOURCE

    note = body["notification"]
    assert note is not None
    assert note["recipient_kind"] == "student"
    assert note["recipient_id"] == ids["student"]
    assert note["channel"] == "in_app"
    assert note["title"] == "本周训练量已减 20%"
    assert note["alert_id"] == ids["alert"]
    assert note["prescription_id"] == ids["prescription"]
    assert note["is_read"] is False
    assert len(_notifications(engine)) == 1


def test_reduce_20pct_after_the_pipeline_already_reduced_does_not_multiply(
        client, engine, frozen):
    """**支 B 的要害**：管道已经自动减过了 → 教师再点一次**不再减**，且 HTTP 仍是 200。

    ⚠️ ``adjustment is None`` 是**有信息的一档**、不是失败：教师那一次点击有效的部分是
    「这条预警我看过了、并且推了消息给学生」。前端应渲染成「本周已经减过量了，本次未再减」。
    ⚠️ 少了这一条，学生端本周的量会是 ``0.8 × 0.8 = 0.64``，而教师只点了一次
    「减量 20%」——Review Focus 第 3 条要防的连乘从教师端回来。
    """
    ids = _seed(engine)
    with Session(engine) as s:
        s.add(WeeklyAdjustment(prescription_id=ids["prescription"], batch_id=ids["batch"],
                               week=3, factor=0.8, reason="RED_RPE_SUSTAINED",
                               source="auto", created_at=T(2025, 9, 15, 6, 0)))
        s.commit()

    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["adjustment"] is None, "同一次减量被写了第二遍"
    assert body["alert"]["status"] == "handled"
    # 消息照发：教师点了「减量 20%」，学生就该被告知（哪怕那条调整是管道几天前写的）
    assert body["notification"] is not None

    rows = _adjustments(engine)
    assert len(rows) == 1
    assert rows[0].factor == 0.8, "系数被改了（应当一条都不动）"
    assert rows[0].created_at == T(2025, 9, 15, 6, 0)


def test_handling_an_alert_twice_is_409(client, engine, frozen):
    """**简报逐字点名的一条**：重复处置同一条 alert → **409**。

    ⚠️ 码是 409 而不是 422：请求体本身没有错，错的是**资源的状态**
    （口径同 :data:`app.api.routers.feedback.CODE_RPE_NOT_OPENED`）。
    ⚠️ 而它真正要挡的不是「点两次报错难看」，是「点两次就减两次」——
    第二次若放行，``handled_action`` 会被覆盖、消息会被重发，而若 ``source``
    写的是 ``"teacher"``（见上一条），那条唯一约束根本拦不住它。
    """
    ids = _seed(engine)
    first = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert first.status_code == 200, first.text

    second = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert second.status_code == 409
    body = second.json()["error"]
    assert body["code"] == "alert_not_pending"
    assert "handled" in body["message"]
    assert len(_adjustments(engine)) == 1
    assert len(_notifications(engine)) == 1


def test_an_ignored_alert_cannot_be_reduced_afterwards(client, engine, frozen):
    """``ignored`` 之后也不能再减量：三档动作**共用**「status 必须是 pending」这一条规则。"""
    ids = _seed(engine)
    assert _post(client, ids["alert"], {"action": "ignore"}).status_code == 200
    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "alert_not_pending"
    assert _adjustments(engine) == []


def test_ignore_sets_status_and_sends_nothing(client, engine, frozen):
    ids = _seed(engine)
    response = _post(client, ids["alert"], {"action": "ignore"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alert"]["status"] == "ignored"
    assert body["alert"]["handled_action"] == "ignore"
    assert body["alert"]["handled_at"] == MOMENT.isoformat()
    assert body["adjustment"] is None
    assert body["notification"] is None
    assert _notifications(engine) == []
    assert _adjustments(engine) == []


def test_note_keeps_status_pending_and_writes_no_handled_at(client, engine, frozen):
    """``note`` 那一档**只**记 ``handled_action``，``status`` 保持 ``pending``。

    ⚠️ ``handled_at`` 也**不写**：那一列的名字是「处理时间」，给一条仍然 ``pending``
    的预警填上它，前端就会显示「已处理于 …」而状态是待处理。
    """
    ids = _seed(engine)
    response = _post(client, ids["alert"],
                     {"action": "note", "note": "已与家长沟通，观察一周"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alert"]["status"] == "pending"
    assert body["alert"]["handled_action"] == "已与家长沟通，观察一周"
    assert body["alert"]["handled_at"] is None
    assert body["adjustment"] is None
    assert body["notification"] is None


def test_a_second_note_is_allowed_because_a_note_is_not_a_handling(
        client, engine, frozen):
    """连着记两条备注**不**是重复处置（备注后 status 仍是 pending）。"""
    ids = _seed(engine)
    assert _post(client, ids["alert"], {"action": "note", "note": "第一条"}
                 ).status_code == 200
    second = _post(client, ids["alert"], {"action": "note", "note": "第二条"})
    assert second.status_code == 200
    assert second.json()["alert"]["handled_action"] == "第二条"
    assert _alert(engine, ids["alert"])["status"] == "pending"


def test_a_note_is_appended_to_the_action_of_the_other_two(client, engine, frozen):
    """``reduce_20pct`` / ``ignore`` 也可以带备注：它落在 ``handled_action`` 里，不丢。"""
    ids = _seed(engine)
    response = _post(client, ids["alert"],
                     {"action": "ignore", "note": "学生本周月考"})
    assert response.status_code == 200
    assert response.json()["alert"]["handled_action"] == "ignore: 学生本周月考"


def test_note_without_text_is_422(client, engine, frozen):
    ids = _seed(engine)
    for body in ({"action": "note"}, {"action": "note", "note": ""},
                 {"action": "note", "note": "   "}):
        response = _post(client, ids["alert"], body)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "unprocessable_value"
    assert _alert(engine, ids["alert"])["status"] == "pending"


def test_an_unknown_action_is_422_not_a_silent_no_op(client, engine, frozen):
    """词表外的动作 → **422**，而不是「静默写进 ``handled_action`` 而什么也不做」。

    ⚠️ ``alert.handled_action`` 是 ``Text``、**没有 CHECK**，故 schema 的那道
    ``field_validator`` 是这三档唯一的闸门。少了它，前端拼错一个动作名会得到 200、
    界面显示成功、而训练量一个字没变。
    """
    ids = _seed(engine)
    response = _post(client, ids["alert"], {"action": "reduce_50pct"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "request_validation_failed"
    assert _alert(engine, ids["alert"])["status"] == "pending"
    assert _adjustments(engine) == []


def test_a_class_level_alert_cannot_be_reduced(client, engine, frozen):
    """班级级预警点 ``reduce_20pct`` → **422**：一个教学班没有一张共用的处方。"""
    ids = _seed(engine, level="yellow", rule_id="YELLOW_CLASS_RPE_HIGH",
                 student_id_column=False)
    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 422
    assert "班级级" in response.json()["error"]["message"]
    assert _adjustments(engine) == []
    # 而 ignore 对班级级预警是合法的
    assert _post(client, ids["alert"], {"action": "ignore"}).status_code == 200


def test_reduce_without_a_current_prescription_is_422(client, engine, frozen):
    """那个学生当天没有生效处方 → **422**（``weekly_adjustment.prescription_id`` NOT NULL）。"""
    ids = _seed(engine, with_prescription=False)
    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 422
    assert "没有生效的处方" in response.json()["error"]["message"]
    assert _alert(engine, ids["alert"])["status"] == "pending"


def test_reduce_beyond_the_microcycle_is_422(client, engine, frozen):
    """``current_week`` 返回 ``None`` → **422**，且报的是「不在有效期内」那一档。

    ⚠️⚠️ **可达路径只有一条**（本条测试原先写错了，改后如实记下）：
    ``valid_to`` **有值**且已过期的处方根本到不了这一支——它在
    :func:`_current_prescription` 的 ``valid_to >= as_of`` 那一格就被滤掉了，
    报的是「没有生效的处方」。故这里造的是 ``valid_to IS NULL`` 的那一档
    （``_current_prescription`` 把 NULL 当「不设终点」放行），配一个很久以前的
    ``generated_on``：``current_week(2025-06-01, 2025-09-15, 4)`` = ``16 > 4`` → ``None``。
    口径与 :data:`app.api.routers.prescription.OUTSIDE_MICROCYCLE` 那一格的实测结论
    逐字相同。
    """
    ids = _seed(engine, generated_on=D(2025, 6, 1), valid_to=None)
    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 422
    assert "不在有效期内" in response.json()["error"]["message"]
    assert _adjustments(engine) == []


def test_reduce_when_the_prescription_has_expired_by_valid_to_is_the_other_422(
        client, engine, frozen):
    """**另一半**：``valid_to`` 有值且已过 → 报的是「没有生效的处方」，不是「不在有效期内」。

    ⚠️ 本条与上一条一起钉住「两档消息不同、而它们指的是同一件事的两个入口」——
    只测其中一条的话，把两个 ``raise`` 的消息对调也不会红。
    """
    ids = _seed(engine)
    response = _post(client, ids["alert"], {"action": "reduce_20pct"},
                     as_of="2025-09-29")
    assert response.status_code == 422
    assert "没有生效的处方" in response.json()["error"]["message"]
    assert _adjustments(engine) == []


def test_an_unknown_alert_is_404(client, engine, frozen):
    _seed(engine)
    response = _post(client, 999999, {"action": "ignore"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ===========================================================================
# 支 C：服务端填的那两格
# ===========================================================================


def test_the_client_cannot_forge_handled_action_or_handled_at(client, engine, frozen):
    """请求体里塞 ``handled_action`` / ``handled_at`` → **被忽略**，服务端填的才算。

    ⚠️ ``alert`` 是 RCT 的过程数据（``on_delete="forbid"`` 就是为它定的），
    一条能被客户端改写的处置痕迹等于没有痕迹。
    ⚠️ Pydantic 缺省 ``extra="ignore"``，故多出来的两个键**不报错**、只是不生效——
    本条断言的正是「不生效」。
    """
    ids = _seed(engine)
    response = _post(client, ids["alert"], {
        "action": "ignore",
        "handled_action": "伪造的动作",
        "handled_at": "1999-01-01T00:00:00",
        "status": "pending",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alert"]["handled_action"] == "ignore"
    assert body["alert"]["handled_at"] == MOMENT.isoformat()
    assert body["alert"]["status"] == "ignored"


def test_the_identity_gates_are_the_house_ones(client, engine, frozen):
    """缺头 → 401；工号不在册 → 403（与全仓其余教师端点同一条口径）。"""
    ids = _seed(engine)
    assert _post(client, ids["alert"], {"action": "ignore"}, headers={}
                 ).status_code == 401
    assert _post(client, ids["alert"], {"action": "ignore"}, headers=NOBODY
                 ).status_code == 403
    # 两道闸门都在任何写入之前，故库里一个字都没动
    assert _alert(engine, ids["alert"])["status"] == "pending"


# ===========================================================================
# 支 D：词表与路由
# ===========================================================================


def test_the_three_action_constants_are_the_schema_vocabulary():
    """端点里的三个常量**恰好**是 schema 那一份词表（两侧不同源，硬规矩 #35）。

    ⚠️ 按**集合相等**断言：加第四档动作而忘了接进端点，本条当场红
    （那一档会落到 ``else`` 分支里被当成 ``note`` 处理——一个静默的错误分派）。
    """
    assert {alerts_router.ACTION_REDUCE, alerts_router.ACTION_IGNORE,
            alerts_router.ACTION_NOTE} == set(HANDLE_ACTIONS)
    assert HANDLE_ACTIONS == ("reduce_20pct", "ignore", "note")
    assert len(HANDLE_ACTIONS) == 3


def test_the_handle_route_does_not_collide_with_the_generic_crud_ones(client, engine):
    """``POST /api/alerts/{alert_id}/handle`` 与泛型的五个端点**不同形**，两者并存。

    ⚠️ 泛型工厂给 ``alerts`` 注册的是 ``GET /api/alerts`` 与 ``GET /api/alerts/{alert_id}``
    （``writable=False``，故没有 POST/PATCH/DELETE）。本端点是**三段**，
    与那两条**两段**的路径不可能互相吞掉。
    ⚠️ 而 ``app/api/routers/__init__.py`` 的注释逐字警告过：加任何
    ``GET /api/alerts/<字面>`` 的子路径就会与 ``GET /api/alerts/{alert_id}`` 同形，
    那时 include 顺序立刻变成承重的。本条钉住的是「今天不同形」这个前提。
    """
    ids = _seed(engine)
    spec = client.get("/openapi.json").json()
    assert "/api/alerts/{alert_id}/handle" in spec["paths"]
    assert "post" in spec["paths"]["/api/alerts/{alert_id}/handle"]
    assert set(spec["paths"]["/api/alerts/{alert_id}"]) == {"get"}
    assert set(spec["paths"]["/api/alerts"]) == {"get"}
    # 两个端点各自真的能用（不是只在 spec 里挂着）
    assert client.get(f"/api/alerts/{ids['alert']}", headers=TEACHER).status_code == 200
    assert _post(client, ids["alert"], {"action": "note", "note": "看一眼"}
                 ).status_code == 200


def test_the_handle_endpoint_declares_the_teacher_header_in_openapi(client, engine):
    """``X-Teacher-Staff-No`` 在 OpenAPI 里**声明过**（P4-A5：前端要能从 spec 看出要发它）。"""
    _seed(engine)
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/api/alerts/{alert_id}/handle"]["post"]
    assert operation["security"] == [{"X-Teacher-Staff-No": []}]
    assert "X-Teacher-Staff-No" in spec["components"]["securitySchemes"]


def test_no_notification_row_is_left_behind_when_the_request_is_rejected(
        client, engine, frozen):
    """被拒的请求**一个字都不写**：409 / 422 之后三张表都是原样。

    ⚠️ 这一条钉的是「先判、后写」的顺序：若 ``status`` 的闸门排在写调整之后，
    一次 409 会留下一条已经写好的 ``weekly_adjustment``（响应说没做、库里做了），
    而那正是 Task 4 的覆盖端点逐字警告过的同一个形状（「先算、后写」）。
    """
    ids = _seed(engine, status="handled")
    with Session(engine) as s:
        row = s.get(Alert, ids["alert"])
        row.handled_action = "reduce_20pct"
        row.handled_at = T(2025, 9, 14, 9, 0)
        s.commit()

    response = _post(client, ids["alert"], {"action": "reduce_20pct"})
    assert response.status_code == 409
    assert _adjustments(engine) == []
    assert _notifications(engine) == []
    kept = _alert(engine, ids["alert"])
    assert kept["handled_at"] == T(2025, 9, 14, 9, 0), "原来的处置时刻被改了"
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Alert)) == 1
