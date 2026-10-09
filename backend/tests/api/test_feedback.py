"""spec §8.1 三源采集的七个**特例端点**（:mod:`app.api.routers.feedback`）。

**本文件分四批**（与 commit ③ 的分组对应）：

* **批次 A —— P5-A1/A3/A6 那三条 schema 变更的行为后果**。它们不是「形状断言」
  （那一部分住在 ``tests/db/test_models.py``），而是**这三条变更各自要解决的问题
  真的被解决了**：用户实时写的行落 ``NULL``、且 ``NULL`` 让它躲过
  :func:`app.db.repo.delete_by_batch`（P5-A1 的整个论证就压在这一条 SQL 语义上，
  故必须有反证，不能只在 docstring 里说）；``source`` 的 CHECK 真的拒收域外值；
  ``RPE_TOKEN_LEN`` 真的是「16」这个数的唯一所有者。
* **批次 B —— 课堂快评那一源**（``open-rpe`` / ``rpe-records`` / ``rpe-status``）。
* **批次 C —— 每日打卡那一源**（``training-logs`` + 完成率）。⚠️ **Review Focus 第 2 条
  的三条 ``late`` 边界住在这里**，它们是 22:00:00 整点算哪边这个口径的唯一守卫。
* **批次 D —— 二次小测那一源**（批量录入 + 标准化得分），含「特例路由不被泛型的
  ``GET /api/mini-tests/{id}`` 抢走」那一条（include 顺序因此是承重的）。

⚠️ **时钟一律经 :func:`app.api.routers.feedback._now_local` 注入**（``monkeypatch``）。
不这么做的话，``late`` 的三条边界测试只能在每天 21:59–22:01 那两分钟里跑
——那不是测试，是彩票。``_now_local`` 是「现在几点」在本模块的**唯一住址**，
故换掉它就换掉了全部端点看到的时钟。

⚠️ **期望值一律字面写死**（硬规矩 #35）：百分位、中位数、完成率都手算一遍写在测试里，
不从被测代码读回来跟自己比。处方那一侧走**真实装配**
（:func:`~app.domain.prescription.assembler.assemble` + 真模板 YAML），
故「分母 = ``len(sheet.sessions)``」这条口径是被真的算出来的、不是被 mock 出来的。

⚠️ **本文件不碰 ``app.seed``、不碰 ``backend/data/`` 的一个字节**：模板与动作库走
:mod:`app.refdata_prescription` 的进程内单例（**只读** YAML）。
"""
import datetime as dt
import statistics

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import refdata_prescription as rp
from app.api.routers import feedback as fb
from app.api.schemas.feedback import (
    MiniTestEntryCreate,
    RpeSubmitCreate,
    RpeStatusRead,
    TrainingLogCreate,
)
from app.db.models import Semester, Student, Teacher
from app.db.models.feedback import ClassSession, MiniTest, RpeRecord, TrainingLog
from app.db.models.ops import DailySyncRun
from app.db.models.organisation import CourseSection, Enrollment
from app.db.models.prescription import Prescription
from app.db.repo import delete_by_batch
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, assemble
from app.domain.prescription.override import OverrideKind, OverrideRecord
from app.pipeline.prescription_stage import (
    override_record_payload,
    training_package_payload,
)

D = dt.date
T = dt.datetime

#: 学期起点。**2025-09-01 是周一**，而 18 套模板的 ``day`` 恒为 ``1..N`` 连续
#: （探针 ``t5_probes/template_probe.py`` 实测：绿层 ``[1, 2]``、黄层 ``[1, 2, 3]``、
#: 红层 ``[1, 2, 3, 4]``），故「处方第 1 周」与「学期第 1 周」在这一天**完全对齐**——
#: 完成率那几条测试因此不必处理错位，而错位那一档由
#: :func:`test_training_days_outside_the_queried_week_do_not_count` 单独看着。
SEMESTER_START = D(2025, 9, 1)
SEMESTER_END = D(2025, 12, 22)  # 排他上界（Ruling 174）= 16 周
#: 处方生成日 = 学期第一天，故 ``current_week(generated_on, 学期第 1 周内任一天, 4) == 1``。
GENERATED_ON = SEMESTER_START
MICROCYCLE_WEEKS = 4
#: ``valid_to = generated_on + 4 周 − 1 天``（闭区间末日）。
VALID_TO = D(2025, 9, 28)

#: 绿层模板：**每周 2 天**（``weekly_frequency = 2``，第 1 周 ``day`` = ``[1, 2]``）。
GREEN_TEMPLATE = "GRN-END-NOR-14"
#: 红层模板：**每周 4 天**。⚠️ 只用在「教师把周天数覆盖成 4」那一条里作对照。
RED_TEMPLATE = "RED-END-NOR-02"

TEACHER_STAFF_NO = "T2025001"
TEACHER_HEADERS = {"X-Teacher-Staff-No": TEACHER_STAFF_NO}
#: 一个**不在册**的工号（``require_teacher`` 要 403 的那一档）。
UNKNOWN_TEACHER = {"X-Teacher-Staff-No": "NOBODY"}

STUDENT_NOS = ("S2025001", "S2025002", "S2025003", "S2025004")
#: 前 **3** 个学生选这个教学班；第 4 个**刻意不选课**——``rpe-status`` 的「未交名单」、
#: 「交了但不在名单里」与 ``mini-tests/normalized`` 的「不在任何教学班」三档都要有一个
#: 不属于这个班的人。
ENROLLED_NOS = ("S2025001", "S2025002", "S2025003")
OUTSIDER_NO = "S2025004"

#: ``rpe-status`` 那几条用的提交耗时。⚠️ **90.0 > PROXY_FILL_SECONDS(60)**，
#: 故它同时是「疑似代填」那一档的样本（spec §8.1「已知局限：无法防代填」）。
FAST_ELAPSED = 8.0
SLOW_ELAPSED = 90.0


def _profile(student_id: int = 1) -> StudentProfile:
    """系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。

    ⚠️ 与 ``tests/domain/test_prescription_weekly.py::_profile`` 同形状而**刻意不复用**：
    跨测试文件 import 一个私有夹具会让两个文件互相钉住，改一边红另一边，
    而它抓不到任何新失效。
    """
    return StudentProfile(
        student_id=student_id, sex=Sex.MALE, birth=D(2005, 3, 4), age=20,
        endurance_score=70.0, bmi=None, body_fat_pct=None, muscle_mass_kg=None,
        muscle_p10=None, measured_hrmax=None,
    )


def _package_payload(template_ref: str) -> tuple[dict, dict]:
    """真模板 → ``(training_package 的 JSON 形态, assembly_snapshot)``。

    走生产的 :func:`~app.domain.prescription.assembler.assemble`，故 payload 的形状
    与批处理写进库的那一份**逐格相同**——完成率那几条测试于是量的是真算法，
    不是一个手搓的假训练包。
    """
    package = assemble(
        _profile(), rp.templates()[template_ref], GENERATED_ON, exercises=rp.exercises()
    )
    return training_package_payload(package), dict(package.assembly_snapshot)


def _prescription(session: Session, student_id: int, batch_id: int,
                  template_ref: str = GREEN_TEMPLATE,
                  generated_on: D = GENERATED_ON,
                  status: str = "active",
                  valid_to: D | None = VALID_TO,
                  overrides: list | None = None) -> Prescription:
    """一张**最小可用**的处方行。

    ⚠️ ``microcycle_weeks`` 写死 **4**（字面量，不读模板）：它是完成率端点
    「哪一周算越界」的判据，两侧同源的话把模板改成 8 周也照样绿（硬规矩 #35）。
    """
    payload, snapshot = _package_payload(template_ref)
    row = Prescription(
        student_id=student_id, generated_on=generated_on, batch_id=batch_id,
        template_ref=template_ref, microcycle_weeks=MICROCYCLE_WEEKS,
        label_at_generation="green", training_package=payload,
        assembly_snapshot=snapshot, safety_substitutions=[],
        teacher_overrides=[] if overrides is None else overrides,
        previous_had_overrides=False, status=status,
        valid_from=generated_on, valid_to=valid_to,
        trigger_reasons=["first_stratification"],
    )
    session.add(row)
    session.flush()
    return row


def _seed(engine, *, students: int = 4, enroll: tuple = ENROLLED_NOS,
          with_prescription: bool = False,
          template_ref: str = GREEN_TEMPLATE) -> dict:
    """往内存库插一套最小可用的行，返回 ``{名字: id}``（**用完即关**，见 conftest）。"""
    ids: dict = {}
    with Session(engine) as session:
        semester = Semester(name="2025-2026-1", start_date=SEMESTER_START,
                            end_date=SEMESTER_END, weeks=16, is_current=True)
        teacher = Teacher(staff_no=TEACHER_STAFF_NO, name="张老师")
        session.add_all([semester, teacher])
        session.flush()
        ids["semester"] = semester.id
        ids["teacher"] = teacher.id

        section = CourseSection(semester_id=semester.id, teacher_id=teacher.id,
                                name="体育(1)班", schedule_text="周一 3-4 节",
                                grouping_mode="administrative")
        session.add(section)
        session.flush()
        ids["section"] = section.id

        for index, student_no in enumerate(STUDENT_NOS[:students], start=1):
            student = Student(student_no=student_no, name=f"学生{index}", sex="male",
                              birth=D(2005, 3, 4), department=None, grade=1)
            session.add(student)
            session.flush()
            ids[student_no] = student.id
            if student_no in enroll:
                session.add(Enrollment(semester_id=semester.id, student_id=student.id,
                                       course_section_id=section.id))
        session.flush()

        run = DailySyncRun(semester_id=semester.id, business_date=GENERATED_ON,
                           started_at=T(2025, 9, 1, 2, 0),
                           finished_at=T(2025, 9, 1, 2, 5), status="success")
        session.add(run)
        session.flush()
        ids["batch"] = run.id

        if with_prescription:
            ids["prescription"] = _prescription(
                session, ids[STUDENT_NOS[0]], run.id, template_ref=template_ref
            ).id
        session.commit()
    return ids


def _class_session(engine, ids, *, session_date=D(2025, 9, 1), period=3,
                   rpe_opened=False, rpe_token=None, batch_id=None) -> int:
    """直接插一个课次行（**绕过** HTTP，给「已经存在一节课」的那些测试用）。"""
    with Session(engine) as session:
        row = ClassSession(course_section_id=ids["section"], session_date=session_date,
                           period=period, rpe_opened=rpe_opened, rpe_token=rpe_token,
                           batch_id=batch_id)
        session.add(row)
        session.commit()
        return row.id


def _freeze(monkeypatch, moment: T) -> None:
    """把 :func:`fb._now_local` 换成一个固定时刻。

    ⚠️ **必须换 ``_now_local`` 而不是 ``dt.datetime``**：后者是全仓共用的类，
    换掉它会连带影响 SQLAlchemy 与 Pydantic 内部对时间的处理。
    ``_now_local`` 是 API 层唯一的时钟住址，故换它一格就够。
    """
    monkeypatch.setattr(fb, "_now_local", lambda: moment)


def _row(engine, model, pk):
    """按主键读一行（用完即关的会话，故返回前先取出要的字段）。"""
    with Session(engine) as session:
        return session.get(model, pk)


# ===========================================================================
# 批次 A —— P5-A1 / A3 / A6 的行为后果
# ===========================================================================


def test_a_session_created_over_http_has_a_null_batch_id_and_survives_replay(engine, client):
    """**P5-A1 的反证**：教师实时建的课次 ``batch_id`` 落 ``NULL``，且躲过按批删除。

    这一条是整个 P5-A1 论证的落点。裁定说的是「``delete_by_batch`` 是
    ``WHERE batch_id = :b``，而 SQL 里 ``NULL = 任何值`` 都不成立 → 实时行天然躲过
    重放」——⚠️ 那是一句关于 **SQL 三值逻辑**的断言，而三值逻辑恰恰是最容易
    「以为成立其实不成立」的一类（某些 ORM 会把 ``col == None`` 翻译成 ``IS NULL``）。
    故这里**真的调一次** :func:`delete_by_batch` 数它删了几行，而不是只读 docstring。
    """
    seeded = _seed(engine)
    created = client.post("/api/class-sessions", json={
        "course_section_id": seeded["section"],
        "session_date": "2025-09-08",
        "period": 5,
    }, headers=TEACHER_HEADERS)
    assert created.status_code == 201, created.text
    new_id = created.json()["id"]
    # 读侧也得认这个 NULL：response_model 若还是 batch_id: int 就会 500
    assert created.json()["batch_id"] is None
    listed = client.get(f"/api/class-sessions/{new_id}")
    assert listed.status_code == 200, listed.text
    assert listed.json()["batch_id"] is None

    # 管道写的那一行带批次；实时写的那一行不带。按批删只该动前者。
    piped_id = _class_session(engine, seeded, session_date=D(2025, 9, 9), period=5,
                              batch_id=seeded["batch"])
    with Session(engine) as session:
        deleted = delete_by_batch(session, ClassSession, seeded["batch"])
        session.commit()
    assert deleted == 1, "只该删掉带批次的那一行"
    with Session(engine) as session:
        assert session.get(ClassSession, piped_id) is None
        assert session.get(ClassSession, new_id) is not None, "实时建的课次必须躲过重放"


def test_a_student_checkin_has_a_null_batch_id_and_survives_replay(engine, client, monkeypatch):
    """打卡那一侧的同一个反证：``source="checkin\"``、``batch_id IS NULL``、躲过重放。"""
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 3, 20, 0))
    student_id = seeded[STUDENT_NOS[0]]
    posted = client.post("/api/training-logs", json={
        "log_date": "2025-09-03", "completed": True, "duration_min": 35.0,
        "feeling": "moderate",
    }, headers={"X-Student-Id": str(student_id)})
    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["batch_id"] is None
    assert body["source"] == "checkin"
    assert body["late"] is False
    assert body["student_id"] == student_id

    # 管道同步的那一行（带批次）该被删掉，学生打的这一行不该
    with Session(engine) as session:
        session.add(TrainingLog(
            student_id=seeded[STUDENT_NOS[1]], log_date=D(2025, 9, 3),
            submitted_at=T(2025, 9, 3, 3, 0), completed=True, duration_min=None,
            feeling=None, is_rest_day=False, late=False, source="lepao",
            batch_id=seeded["batch"],
        ))
        session.commit()
    with Session(engine) as session:
        deleted = delete_by_batch(session, TrainingLog, seeded["batch"])
        session.commit()
    assert deleted == 1
    with Session(engine) as session:
        left = session.scalars(select(TrainingLog).where(
            TrainingLog.student_id == student_id)).all()
        assert len(left) == 1, "学生打的卡必须躲过重放"
        assert left[0].source == "checkin"


def test_the_source_check_rejects_a_value_outside_the_pinned_domain(engine):
    """**P5-A3**：``ck_training_log_source`` 真的拒收域外值（不是只写在 docstring 里）。"""
    seeded = _seed(engine)
    with Session(engine) as session:
        session.add(TrainingLog(
            student_id=seeded[STUDENT_NOS[0]], log_date=D(2025, 9, 3),
            submitted_at=T(2025, 9, 3, 20, 0), completed=True, duration_min=None,
            feeling=None, is_rest_day=False, late=False, source="wechat",
            batch_id=None,
        ))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()
    assert "ck_training_log_source" in str(excinfo.value)
    # 约束文本对**字面量**断言（两侧不同源：一边是 DDL、一边是手写的期望串）
    checks = {c.name: str(c.sqltext) for c in TrainingLog.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_training_log_source"] == "source IN ('checkin', 'demo', 'lepao')"


def test_the_checkin_source_constant_is_inside_the_model_value_domain():
    """端点写的那个 ``source`` 值必须在 :attr:`TrainingLog.SOURCES` 里。

    ⚠️ 两侧不同源：一侧是路由模块的常量、一侧是模型类常量 + DB 的 CHECK。
    少了本条，把常量改成 ``"check_in"``（多个下划线）只会让**每一次打卡**都 409，
    而那看起来像「学生重复提交」。
    """
    assert fb.CHECKIN_SOURCE == "checkin"
    assert fb.CHECKIN_SOURCE in TrainingLog.SOURCES


def test_rpe_token_len_is_the_single_owner_of_the_number_sixteen(engine):
    """**P5-A6**：``16`` 只有一个住址，且生成的口令长度恰好等于列宽。"""
    assert ClassSession.RPE_TOKEN_LEN == 16
    assert ClassSession.__table__.c.rpe_token.type.length == 16
    tokens = {fb._new_rpe_token() for _ in range(40)}
    assert all(len(token) == ClassSession.RPE_TOKEN_LEN for token in tokens)
    assert len(tokens) == 40, "40 次生成撞车说明熵不够（12 字节 = 96 bit）"


# ===========================================================================
# 批次 B —— 课堂快评（open-rpe / rpe-records / rpe-status）
# ===========================================================================


def test_open_rpe_sets_the_flag_and_returns_a_token(engine, client):
    """教师点「发起课堂快评」→ ``rpe_opened=True`` + 一个 16 字符口令。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded)
    response = client.post(f"/api/class-sessions/{cs_id}/open-rpe", headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["class_session_id"] == cs_id
    assert body["rpe_opened"] is True
    assert body["already_open"] is False
    assert len(body["rpe_token"]) == 16
    row = _row(engine, ClassSession, cs_id)
    assert row.rpe_opened is True
    assert row.rpe_token == body["rpe_token"]


def test_open_rpe_twice_keeps_the_first_token(engine, client):
    """**幂等**：教师手抖点两次不该让正在填的学生手里的口令作废。

    ⚠️ 与 Task 4 的 ``regenerate``「幂等 → 200 而不是 409」同一条口径，但这里的
    「幂等」更强一档：**连口令都不换**。换口令的话，第一个学生已经抄在纸上的那串
    会当场失效，而他看到的是「口令错误」——那看起来像他抄错了。
    ``already_open`` 那一格让前端知道要不要重新投屏。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded)
    first = client.post(f"/api/class-sessions/{cs_id}/open-rpe", headers=TEACHER_HEADERS)
    second = client.post(f"/api/class-sessions/{cs_id}/open-rpe", headers=TEACHER_HEADERS)
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json()["already_open"] is False
    assert second.json()["already_open"] is True
    assert second.json()["rpe_token"] == first.json()["rpe_token"]


def test_open_rpe_needs_a_registered_teacher(engine, client):
    """缺头 → **401**；工号不在册 → **403**；课次不存在 → **404**。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded)
    assert client.post(f"/api/class-sessions/{cs_id}/open-rpe").status_code == 401
    denied = client.post(f"/api/class-sessions/{cs_id}/open-rpe", headers=UNKNOWN_TEACHER)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    missing = client.post("/api/class-sessions/999999/open-rpe", headers=TEACHER_HEADERS)
    assert missing.status_code == 404
    # 被拒的那两次一个字节都没写
    assert _row(engine, ClassSession, cs_id).rpe_opened is False


def test_submitting_rpe_fills_submitted_at_server_side(engine, client, monkeypatch):
    """``submitted_at`` 由**服务端**填，请求体里根本没有这个字段。

    ⚠️ 学生端的时钟不可信（它可以被改），而 RPE 的时间戳是 ``RED_RPE_SUSTAINED``
    「连续三次」那个判据的输入，故这一半不能交给客户端——与 Task 4 的
    ``applied_at`` 同一条纪律。守卫分两半：① 模型上**没有**这个字段（结构上不可能
    伪造）；② 库里的值落在「请求前后」那个区间里。
    """
    assert "submitted_at" not in RpeSubmitCreate.model_fields
    assert "student_id" not in RpeSubmitCreate.model_fields

    seeded = _seed(engine)
    opened = client.post("/api/class-sessions", json={
        "course_section_id": seeded["section"], "session_date": "2025-09-08", "period": 3,
    }, headers=TEACHER_HEADERS).json()
    token = client.post(f"/api/class-sessions/{opened['id']}/open-rpe",
                        headers=TEACHER_HEADERS).json()["rpe_token"]

    moment = T(2025, 9, 8, 10, 31, 7)
    _freeze(monkeypatch, moment)
    student_id = seeded[STUDENT_NOS[0]]
    posted = client.post("/api/rpe-records", json={
        "class_session_id": opened["id"], "rpe": 7, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": token,
    }, headers={"X-Student-Id": str(student_id)})
    assert posted.status_code == 201, posted.text
    assert posted.headers["Location"] == f"/api/rpe-records/{posted.json()['id']}"
    assert posted.json()["submitted_at"] == moment.isoformat()
    assert posted.json()["student_id"] == student_id


def test_a_wrong_rpe_token_is_403_and_writes_nothing(engine, client, monkeypatch):
    """口令不对 → **403**，且库里一行都不多（挡「猜 ``class_session_id`` 乱交」）。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    denied = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 6, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": "WRONG-TOKEN-0000",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[0]])})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "invalid_rpe_token"
    with Session(engine) as session:
        assert session.scalars(select(RpeRecord)).all() == []


def test_submitting_to_a_session_that_was_never_opened_is_409(engine, client, monkeypatch):
    """没发起过的课次 → **409** 且 ``code == "rpe_not_opened"``。

    ⚠️ 用 409 不用 422：请求体本身没有错（``class_session_id`` 存在、``rpe`` 合法），
    错的是**资源的状态**。前端按 ``code`` 分支时要能说出「老师还没发起快评」，
    而不是「你填错了」。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded)  # rpe_opened=False、rpe_token=None
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    denied = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 6, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": "whatever",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[0]])})
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "rpe_not_opened"


def test_submitting_rpe_twice_for_the_same_session_is_409(engine, client, monkeypatch):
    """一节课一个学生只能交一次（``uq_rpe_record_session_student``）→ **409**。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    payload = {"class_session_id": cs_id, "rpe": 6, "elapsed_seconds": FAST_ELAPSED,
               "rpe_token": "aB3-_xY9kL2mNpQr"}
    headers = {"X-Student-Id": str(seeded[STUDENT_NOS[0]])}
    first = client.post("/api/rpe-records", json=payload, headers=headers)
    second = client.post("/api/rpe-records", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "integrity_conflict"
    with Session(engine) as session:
        assert len(session.scalars(select(RpeRecord)).all()) == 1


@pytest.mark.parametrize("rpe", [-1, 11])
def test_rpe_outside_zero_to_ten_is_422(engine, client, monkeypatch, rpe):
    """RPE 的值域 **0–10** 由 Pydantic 挡在读侧（422），不是等 DB 的 CHECK 给 409。

    ⚠️ 值域的**所有者**仍是 :attr:`RpeRecord.RPE_MIN` / ``RPE_MAX``：schema 引它、
    不写第三份（``-1`` 与 ``11`` 这两个期望值是手写的字面量，两侧不同源）。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    denied = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": rpe, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": "aB3-_xY9kL2mNpQr",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[0]])})
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "request_validation_failed"
    assert RpeRecord.RPE_MIN == 0 and RpeRecord.RPE_MAX == 10


def test_a_student_cannot_submit_rpe_as_another_student(engine, client, monkeypatch):
    """**Review Focus 第 1 条**：``X-Student-Id`` 与 URL/请求体里的学生不符 → **403**。

    这里的形状是「学生 A 拿着自己的头去替学生 B 交快评」：请求体里**没有**
    ``student_id``（服务端从头取），故越权的唯一入口是那个头本身——
    而 :func:`app.api.deps.require_scope` 的第二支会查库判「这个 id 在不在册」。
    本条钉的是**不在册**那一档（``999999``），在册但替别人交那一档在结构上不可能。
    """
    assert "student_id" not in RpeSubmitCreate.model_fields
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    denied = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 6, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": "aB3-_xY9kL2mNpQr",
    }, headers={"X-Student-Id": "999999"})
    assert denied.status_code == 403
    with Session(engine) as session:
        assert session.scalars(select(RpeRecord)).all() == []


def test_elapsed_seconds_may_be_null_and_a_slow_one_is_still_accepted(engine, client,
                                                                     monkeypatch):
    """``elapsed_seconds`` 可为 ``null``；``> 60`` **不拒绝**（只被单独计数）。

    spec §8.1 明写「**已知局限：无法防代填**」，故后端不能拿耗时当准入门槛
    ——一个真花了 90 秒填的学生不该被拒；``90`` 那一档由 ``rpe-status`` 的
    ``suspected_proxy_count`` 报给教师，由**人**去判断。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    first = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 5, "elapsed_seconds": None,
        "rpe_token": "aB3-_xY9kL2mNpQr",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[0]])})
    second = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 9, "elapsed_seconds": SLOW_ELAPSED,
        "rpe_token": "aB3-_xY9kL2mNpQr",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[1]])})
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["elapsed_seconds"] is None
    assert second.json()["elapsed_seconds"] == SLOW_ELAPSED


def test_rpe_status_splits_the_roster_and_reports_mean_median_and_suspects(engine, client,
                                                                          monkeypatch):
    """**已交/未交名单 + 人均 RPE + 提交耗时中位数 + 疑似代填计数**（spec §8.1）。

    期望值全部手算（硬规矩 #35）：3 个选课的学生里 2 个交了（``rpe=6`` 耗时 ``8.0``、
    ``rpe=9`` 耗时 ``90.0``）→ 未交名单是第 3 个；``90.0 > 60`` 点亮「疑似代填」那一格。
    ⚠️ 于是 ``mean_rpe = (6 + 9) / 2 = 7.5``、``median = (8.0 + 90.0) / 2 = 49.0``
    ——**偶数个样本的中位数取中间两个的均值**，这是 :func:`statistics.median` 的口径；
    期望侧故意用 ``statistics`` 而不是写死 ``49.0``：这里要钉的是「端点用的就是
    中位数这个统计量」，而不是「中位数怎么算」（那是标准库的契约）。

    ⚠️ **名单的分母是选课人数、分子是实际提交数，两者可以不一致**：最后让一个
    **没选这个班**的学生也交上来（他可能是旁听、或选课后被退选），他进「已交」
    但不进「未交」，故 ``len(submitted) = 3`` 而 ``enrolled_count`` 仍是 3、
    未交名单仍是那一个没交的人。教师端要看到的正是这个差
    （spec §8.1「实时显示已提交/未提交名单，可现场催交」）。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    for student_no, rpe, elapsed in ((STUDENT_NOS[0], 6, FAST_ELAPSED),
                                     (STUDENT_NOS[1], 9, SLOW_ELAPSED)):
        posted = client.post("/api/rpe-records", json={
            "class_session_id": cs_id, "rpe": rpe, "elapsed_seconds": elapsed,
            "rpe_token": "aB3-_xY9kL2mNpQr",
        }, headers={"X-Student-Id": str(seeded[student_no])})
        assert posted.status_code == 201, posted.text

    response = client.get(f"/api/class-sessions/{cs_id}/rpe-status", headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    body = RpeStatusRead.model_validate(response.json())
    assert body.class_session_id == cs_id
    assert body.enrolled_count == 3
    assert sorted(s.student_id for s in body.submitted) == sorted(
        seeded[n] for n in ENROLLED_NOS[:2])
    assert body.not_submitted == [seeded[ENROLLED_NOS[2]]]
    assert body.mean_rpe == 7.5
    assert body.median_elapsed_seconds == statistics.median([FAST_ELAPSED, SLOW_ELAPSED])
    assert body.suspected_proxy_count == 1

    # 再让一个**没选课**的学生交上来：他不进「未交名单」，但**进**已交名单
    outsider = client.post("/api/rpe-records", json={
        "class_session_id": cs_id, "rpe": 10, "elapsed_seconds": FAST_ELAPSED,
        "rpe_token": "aB3-_xY9kL2mNpQr",
    }, headers={"X-Student-Id": str(seeded[OUTSIDER_NO])})
    assert outsider.status_code == 201, outsider.text
    again = RpeStatusRead.model_validate(
        client.get(f"/api/class-sessions/{cs_id}/rpe-status",
                   headers=TEACHER_HEADERS).json())
    assert again.enrolled_count == 3
    assert len(again.submitted) == 3
    assert again.not_submitted == [seeded[ENROLLED_NOS[2]]]
    assert again.mean_rpe == 25 / 3
    assert again.suspected_proxy_count == 1


def test_rpe_status_lists_who_has_not_submitted(engine, client):
    """「可现场催交」要的就是这份名单：选课的 2 人一个都没交 → 未交名单是那 2 个 id。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    body = client.get(f"/api/class-sessions/{cs_id}/rpe-status",
                      headers=TEACHER_HEADERS).json()
    assert sorted(body["not_submitted"]) == sorted(seeded[n] for n in ENROLLED_NOS)
    assert body["submitted"] == []
    # ⚠️ 「没人交」时人均与中位数是 **null**，不是 0（「不知道」不得讲成「0」）
    assert body["mean_rpe"] is None
    assert body["median_elapsed_seconds"] is None
    assert body["suspected_proxy_count"] == 0


def test_rpe_status_needs_a_registered_teacher(engine, client):
    """教师端读接口同样要过闸门（缺头 401 / 不在册 403 / 课次不存在 404）。"""
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded)
    assert client.get(f"/api/class-sessions/{cs_id}/rpe-status").status_code == 401
    assert client.get(f"/api/class-sessions/{cs_id}/rpe-status",
                      headers=UNKNOWN_TEACHER).status_code == 403
    assert client.get("/api/class-sessions/999999/rpe-status",
                      headers=TEACHER_HEADERS).status_code == 404


def test_rpe_status_median_ignores_null_elapsed_seconds(engine, client, monkeypatch):
    """耗时为 ``null`` 的那几行**不进**中位数（否则 ``None`` 会让排序 ``TypeError``）。

    ⚠️ 三个人里两个没量到耗时、一个量到 ``8.0`` → 中位数是 ``8.0``，不是「三个数的
    中位数」。全为 ``null`` 那一档由 :func:`test_rpe_status_lists_who_has_not_submitted`
    看着（没人交 → ``null``）；本条钉的是「交了但都没量到耗时」那一档。
    """
    seeded = _seed(engine)
    cs_id = _class_session(engine, seeded, rpe_opened=True, rpe_token="aB3-_xY9kL2mNpQr")
    _freeze(monkeypatch, T(2025, 9, 1, 10, 31))
    for student_no, elapsed in ((STUDENT_NOS[0], None), (STUDENT_NOS[1], FAST_ELAPSED)):
        posted = client.post("/api/rpe-records", json={
            "class_session_id": cs_id, "rpe": 5, "elapsed_seconds": elapsed,
            "rpe_token": "aB3-_xY9kL2mNpQr",
        }, headers={"X-Student-Id": str(seeded[student_no])})
        assert posted.status_code == 201, posted.text
    body = client.get(f"/api/class-sessions/{cs_id}/rpe-status",
                      headers=TEACHER_HEADERS).json()
    assert body["median_elapsed_seconds"] == FAST_ELAPSED
    assert body["mean_rpe"] == 5.0
    assert body["suspected_proxy_count"] == 0


# ===========================================================================
# 批次 C —— 每日打卡（training-logs）与完成率
# ===========================================================================


def _checkin(client, student_id: int, log_date: str, **extra):
    payload = {"log_date": log_date, "completed": True, "duration_min": 30.0,
               "feeling": "moderate"}
    payload.update(extra)
    return client.post("/api/training-logs", json=payload,
                       headers={"X-Student-Id": str(student_id)})


#: **Review Focus 第 2 条的三个时刻**。spec §8.1 逐字「打卡窗口 = 当日 00:00–22:00。
#: 22:00 后提交仍入库但标记 ``late = true``，**不计入当日完成**」，而「22:00 后」
#: 这三个字对 **22:00:00 整点**没有答案——窗口是闭区间 ``[00:00, 22:00]`` 还是
#: 半开 ``[00:00, 22:00)``？本仓的口径是**闭区间**（判定式 ``> time(22, 0)``），
#: 理由：spec 写的是「22:00 **后**」，而 22:00:00 不是「后」。
#: ⚠️ 下面三条**只差一秒**，故它们是那个口径的唯一守卫：把 ``>`` 改成 ``>=``
#: 只有中间那条会红。
LATE_BOUNDARIES = (
    (T(2025, 9, 3, 21, 59, 59), False),
    (T(2025, 9, 3, 22, 0, 0), False),   # ← 整点算闭区间内，**不算迟**
    (T(2025, 9, 3, 22, 0, 1), True),
)


@pytest.mark.parametrize(("moment", "expected_late"), LATE_BOUNDARIES)
def test_the_checkin_deadline_is_a_closed_interval_at_22_00(engine, client, monkeypatch,
                                                           moment, expected_late):
    """``21:59:59`` 不迟、``22:00:00`` **不迟**、``22:00:01`` 迟。

    ⚠️ 三个样本只差一秒，而结论翻了一次——这正是「必须响亮地定一个口径并测边界」
    的意思（Review Focus 第 2 条原文）。口径的住址是
    :data:`app.api.routers.feedback.CHECKIN_DEADLINE` 与它那个 ``>`` 比较。
    """
    assert fb.CHECKIN_DEADLINE == dt.time(22, 0)
    seeded = _seed(engine)
    _freeze(monkeypatch, moment)
    posted = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-03")
    assert posted.status_code == 201, posted.text
    assert posted.json()["late"] is expected_late
    assert posted.json()["submitted_at"] == moment.isoformat()


def test_late_cannot_be_claimed_by_the_client(engine, client, monkeypatch):
    """``late`` 由**服务端**算：请求模型上没有这个字段，多传也被忽略。

    ⚠️ 完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」，故这一半不能交给
    客户端——与 ``submitted_at`` / ``source`` / ``student_id`` / ``batch_id``
    同一条纪律（见 :func:`test_the_request_models_cannot_carry_the_server_filled_fields`）。
    """
    for banned in ("late", "source", "student_id", "batch_id", "submitted_at"):
        assert banned not in TrainingLogCreate.model_fields, banned
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 3, 23, 30))   # 已经过了 22:00
    posted = client.post("/api/training-logs", json={
        "log_date": "2025-09-03", "completed": True, "duration_min": 30.0,
        "feeling": "moderate", "late": False, "source": "lepao",
    }, headers={"X-Student-Id": str(seeded[STUDENT_NOS[0]])})
    assert posted.status_code == 201, posted.text
    assert posted.json()["late"] is True, "客户端声称的 late=false 必须被无视"
    assert posted.json()["source"] == "checkin", "客户端声称的 source 必须被无视"


def test_a_second_checkin_for_the_same_day_is_409(engine, client, monkeypatch):
    """一天一行（``uq_training_log_student_day``）→ **409**，不是覆盖也不是新增。"""
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 3, 20, 0))
    first = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-03")
    second = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-03", completed=False)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "integrity_conflict"
    with Session(engine) as session:
        rows = session.scalars(select(TrainingLog)).all()
        assert len(rows) == 1
        assert rows[0].completed is True, "第一次提交的内容必须原样留着"


def test_a_backfilled_checkin_keeps_both_dates_apart(engine, client, monkeypatch):
    """**补卡入库**，而 ``log_date`` 与 ``submitted_at`` 的日期差就是「补了几天」。

    ⚠️ 这一条是 ``submitted_at`` 那一列存在的理由（P5-A1 之外本 Task 补的列）：
    ``late`` **只**看时刻（21:00 < 22:00 → ``False``），故单看 ``late`` 无法知道
    这是补卡；而完成率要把补卡排除掉，靠的就是这两个日期不一致。
    """
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 5, 21, 0))     # 9 月 5 日晚上 9 点
    posted = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-01")   # 补 9 月 1 日的卡
    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["log_date"] == "2025-09-01"
    assert body["submitted_at"] == T(2025, 9, 5, 21, 0).isoformat()
    assert body["late"] is False, "late 只看时刻，不看是不是补卡"


def test_a_rest_day_checkin_is_accepted_and_flagged(engine, client, monkeypatch):
    """「今日休息」那一键（spec §8.1 的折中方案）：``is_rest_day=True`` 照常入库。"""
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 6, 12, 0))     # 2025-09-06 是周六
    posted = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-06",
                      completed=False, duration_min=None, feeling=None, is_rest_day=True)
    assert posted.status_code == 201, posted.text
    assert posted.json()["is_rest_day"] is True
    assert posted.json()["completed"] is False
    assert posted.json()["duration_min"] is None


def test_a_feeling_outside_the_domain_is_422_not_409(engine, client, monkeypatch):
    """域外的 ``feeling`` 由 Pydantic 挡成 **422**，不是等 DB 的 CHECK 给 409。

    ⚠️ 这正是 :func:`app.api.schemas._base.one_of` 存在的理由（它的 docstring 逐字：
    「前端表单填错一个下拉框会收到 integrity_conflict，于是它会把一个自己的输入错误
    当成『与别人撞了』」）。值域仍引 :attr:`TrainingLog.FEELINGS`、不抄第二份。
    """
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 3, 20, 0))
    denied = _checkin(client, seeded[STUDENT_NOS[0]], "2025-09-03", feeling="轻松")
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "request_validation_failed"
    assert sorted(TrainingLog.FEELINGS) == ["easy", "hard", "moderate"]
    with Session(engine) as session:
        assert session.scalars(select(TrainingLog)).all() == []


def test_a_student_cannot_check_in_as_another_student(engine, client, monkeypatch):
    """**Review Focus 第 1 条**：不在册的 ``X-Student-Id`` → **403**，且一行都不写。"""
    seeded = _seed(engine)
    _freeze(monkeypatch, T(2025, 9, 3, 20, 0))
    denied = _checkin(client, 999999, "2025-09-03")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    with Session(engine) as session:
        assert session.scalars(select(TrainingLog)).all() == []


def test_the_completion_rate_denominator_is_the_prescription_training_days(engine, client,
                                                                          monkeypatch):
    """**分母 = 处方训练日数**（spec §8.1 的折中方案：每日都可打卡，但完成率只按训练日计）。

    绿层模板 ``GRN-END-NOR-14`` 的 ``weekly_frequency = 2``、第 1 周 ``day = [1, 2]``
    （探针 ``t5_probes/template_probe.py`` 实测），而处方 ``generated_on`` =
    学期第一天，故学期第 1 周的训练日就是 **09-01 与 09-02** 两天。
    学生打了 3 天卡（含一个**非训练日** 09-03）→ 分母仍是 **2**、分子 **2**、
    完成率 **1.0**。⚠️ 那第三天正是 ``is_rest_day`` 那一列要解决的形状：
    没有它、或分母按「打卡天数」算，绿层学生的完成率就会被非训练日污染。
    """
    seeded = _seed(engine, with_prescription=True)
    student_id = seeded[STUDENT_NOS[0]]
    for day in ("2025-09-01", "2025-09-02", "2025-09-03"):
        _freeze(monkeypatch, T(int(day[:4]), int(day[5:7]), int(day[8:]), 20, 0))
        posted = _checkin(client, student_id, day)
        assert posted.status_code == 201, posted.text
    # 第三天不是训练日，学生自己标成休息日也一样不进分母
    response = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(student_id)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["denominator"] == 2
    assert body["numerator"] == 2
    assert body["completion_rate"] == 1.0
    assert body["expected_days"] == ["2025-09-01", "2025-09-02"]
    assert body["completed_days"] == ["2025-09-01", "2025-09-02"]
    assert body["prescription_week"] == 1
    assert body["paused"] is False
    assert body["reason"] is None


def test_the_denominator_follows_a_teacher_weekly_frequency_override(engine, client,
                                                                    monkeypatch):
    """**P5-A2 的核心**：教师把周天数从 4 覆盖成 2，分母**跟着变成 2**。

    这一条是「分母 = ``len(sheet.sessions)`` 而不是 ``Template.weekly_frequency``」
    这个裁定的唯一守卫。⚠️ 若读模板值，本条会红成 ``denominator == 4``——
    而 4 看起来完全合理（红层模板确实写着 4），故它是一个**静默**的错：
    教师减了两天训练、学生的完成率分母却没变，于是「两天都练了」被算成 **50%**，
    而真相是 **100%**——过程指标因此把一个**依从性最好**的学生报成半个不及格，
    而 ``YELLOW_CHECKIN_GAP`` / 班级周报都会跟着读它。

    ⚠️ **方向是「减」而不是「加」**（本 Task 实测 :mod:`app.domain.prescription.override`
    的模块表格：``WEEKLY_FREQUENCY`` 的效果逐字是「**保留前 N 课** + 按 N/原课次重量」），
    故把绿层的 2 天覆盖成 4 天**不会**变成 4 课（只有 2 课可保留）。派单的 P5-A2
    举的例子是「教师改了周天数」，本条按那个覆盖**真的能做到的方向**来钉。

    ``weekly_frequency`` 那一格是 ``TrainingPackage`` **没有**的字段（P5-A2 实测），
    故读模板值在本仓根本读不到——这也是裁定改成 ``len(sheet.sessions)`` 的起因。
    """
    seeded = _seed(engine)
    student_id = seeded[STUDENT_NOS[0]]
    record = OverrideRecord(
        kind=OverrideKind.WEEKLY_FREQUENCY, target=None, old_value="4", new_value="2",
        reason="该生本周有集训，减到 2 天", teacher_staff_no=TEACHER_STAFF_NO,
        applied_at=T(2025, 8, 31, 18, 0),
    )
    with Session(engine) as session:
        _prescription(session, student_id, seeded["batch"], template_ref=RED_TEMPLATE,
                      overrides=[override_record_payload(record)])
        session.commit()
    for day in ("2025-09-01", "2025-09-02", "2025-09-03"):
        _freeze(monkeypatch, T(2025, 9, int(day[8:]), 20, 0))
        assert _checkin(client, student_id, day).status_code == 201
    body = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(student_id)}).json()
    # 覆盖之后第 1 周只剩 2 个训练日（红层原本是 day 1..4 = 09-01..09-04）
    assert body["denominator"] == 2
    assert body["numerator"] == 2
    assert body["expected_days"] == ["2025-09-01", "2025-09-02"]
    assert body["completion_rate"] == 1.0


def test_late_rest_day_and_backfilled_rows_do_not_count(engine, client, monkeypatch):
    """分子的三个排除项一次钉住：**迟交**、**休息日**、**补卡**。

    四个训练日（红层模板，``weekly_frequency = 4`` → ``day = [1, 2, 3, 4]`` =
    09-01..09-04）各打一天卡，四种情形：

    * 09-01 当天 20:00 交、``completed=True`` → **计入**；
    * 09-02 当天 **22:30** 交 → ``late=True`` → **不计入**（spec §8.1「不计入当日完成」）；
    * 09-03 当天交但 ``is_rest_day=True`` → **不计入**（学生说这天他休息）；
    * 09-04 那一行是 **09-06 补打的** → ``submitted_at.date() != log_date`` → **不计入**。

    于是分母 4、分子 **1**、完成率 **0.25**。⚠️ 四行**全部** ``completed=True``：
    本条要验的正是「学生说练了」与「算不算完成」是两件事。
    """
    seeded = _seed(engine, template_ref=RED_TEMPLATE)
    student_id = seeded[STUDENT_NOS[0]]
    with Session(engine) as session:
        _prescription(session, student_id, seeded["batch"], template_ref=RED_TEMPLATE)
        session.commit()

    _freeze(monkeypatch, T(2025, 9, 1, 20, 0))
    assert _checkin(client, student_id, "2025-09-01").status_code == 201
    _freeze(monkeypatch, T(2025, 9, 2, 22, 30))          # 迟交
    assert _checkin(client, student_id, "2025-09-02").status_code == 201
    _freeze(monkeypatch, T(2025, 9, 3, 20, 0))
    late_rest = _checkin(client, student_id, "2025-09-03", is_rest_day=True)
    assert late_rest.status_code == 201
    _freeze(monkeypatch, T(2025, 9, 6, 20, 0))           # 补 09-04 的卡
    assert _checkin(client, student_id, "2025-09-04").status_code == 201

    body = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(student_id)}).json()
    assert body["denominator"] == 4
    assert body["numerator"] == 1
    assert body["completed_days"] == ["2025-09-01"]
    assert body["completion_rate"] == 0.25


def test_no_prescription_gives_a_null_rate_and_not_zero(engine, client):
    """**没有处方 → ``completion_rate`` 是 ``null`` 而不是 ``0``**（P5-A2 的裁定）。

    「不知道」不得讲成「0%」（Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）：
    一个刚入学、批处理还没跑过的学生，他的完成率**没有定义**，
    而 ``0`` 会被前端渲染成「一次都没练」——那是关于这个学生的一句假话，
    也会让 ``GREEN_MASTERY`` / 班级周报的分层统计把他算进最差的一档。
    ``reason`` 那一格必须说明为什么是 ``null``。
    """
    seeded = _seed(engine)     # with_prescription=False
    student_id = seeded[STUDENT_NOS[0]]
    body = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(student_id)}).json()
    assert body["completion_rate"] is None
    assert body["denominator"] == 0
    assert body["numerator"] == 0
    assert body["expected_days"] == []
    assert body["prescription_id"] is None
    assert body["reason"] is not None and body["reason"] != ""


def test_an_expired_prescription_gives_a_null_rate_and_not_zero(engine, client):
    """``current_week`` 返回 ``None``（处方已到期）→ 同样是 ``null``，且 ``reason`` 说明。

    ⚠️ 这一档与「没有处方」是**两个不同的问题**（与 Task 4 的
    ``no_active_prescription`` / ``outside_microcycle`` 两个码同一条判断）：
    前者是「批处理还没跑」，后者是「该换处方了」（spec §5.2 触发 3）。
    两者都回 ``null``，但 ``reason`` 与 ``prescription_id`` 不同，前端因此能给出两种提示。

    ⚠️ **造这一档要靠 ``valid_to=None``**（与 Task 4 的 ``OUTSIDE_MICROCYCLE`` 那段注释
    逐字同一条可达路径）：``valid_to`` 是 nullable 的（``needs_review`` 的处方还没有
    确定的有效期），而 :func:`_current_prescription` 把 ``NULL`` 当「不设终点」放行，
    于是一张 ``generated_on = 09-01`` 而 ``valid_to IS NULL`` 的行在第 8 周仍被选中，
    而 ``current_week(09-01, 10-20, 4)`` = ``49 // 7 + 1`` = **8 > 4** → ``None``。
    若把 ``valid_to`` 填成正常的 09-28，那一周根本找不到处方，本条就退化成
    :func:`test_no_prescription_gives_a_null_rate_and_not_zero` 的重复。
    """
    seeded = _seed(engine)
    student_id = seeded[STUDENT_NOS[0]]
    with Session(engine) as session:
        expired = _prescription(session, student_id, seeded["batch"], valid_to=None)
        prescription_id = expired.id
        session.commit()
    # 学期第 8 周 = 09-01 + 7×7 天 = 10-20 起的那 7 天，早已过 4 周微周期
    body = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 8},
        headers={"X-Student-Id": str(student_id)}).json()
    assert body["completion_rate"] is None
    assert body["week"] == 8
    assert body["expected_days"] == []
    assert body["denominator"] == 0
    assert body["prescription_id"] == prescription_id
    assert body["prescription_week"] is None
    assert "微周期" in body["reason"]


def test_a_paused_week_still_reports_its_denominator(engine, client, monkeypatch):
    """``paused=True`` 时**照样算**分母，并把 ``paused`` 单独报出来（P8-A3 的口径）。

    ⚠️ 「暂停」与「本周量为 0」是两件不同的事：:func:`weekly_training_sheet`
    对 ``paused`` 只**抄不判**（sessions 照样带出），故在后端把完成率抹成 ``null``
    或 ``0`` 都是替前端做了一个它自己该做的决定。本端点把 ``paused`` 透出去，
    由前端决定渲染成「本周暂停」还是照常显示百分比。
    """
    seeded = _seed(engine)
    student_id = seeded[STUDENT_NOS[0]]
    record = OverrideRecord(
        kind=OverrideKind.PAUSE, target=None, old_value="false", new_value="true",
        reason="踝伤，本周暂停", teacher_staff_no=TEACHER_STAFF_NO,
        applied_at=T(2025, 8, 31, 18, 0),
    )
    with Session(engine) as session:
        _prescription(session, student_id, seeded["batch"],
                      overrides=[override_record_payload(record)])
        session.commit()
    _freeze(monkeypatch, T(2025, 9, 1, 20, 0))
    assert _checkin(client, student_id, "2025-09-01").status_code == 201
    body = client.get(
        f"/api/students/{student_id}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(student_id)}).json()
    assert body["paused"] is True
    assert body["denominator"] == 2
    assert body["completion_rate"] == 0.5


def test_training_days_outside_the_queried_week_do_not_count(engine, client, monkeypatch):
    """处方周与学期周**错位**时，只数落在所查那一周里的训练日。

    ⚠️ 这一条钉的是分母的一个边界：分母不是无条件的 ``len(sheet.sessions)``，
    而是「那些训练日 ∩ 所查学期周的 7 天」。本夹具让处方在 **09-04**（周四）生成，
    于是处方第 1 周是 09-04..09-10、训练日（绿层 ``day=[1,2]``）是 **09-04 与 09-05**；
    而学期第 1 周是 09-01..09-07 —— 交集是那两天，分母 **2**。
    到了学期**第 2 周**（09-08..09-14），处方第 1 周的训练日一个都不在里面，
    而处方第 2 周（09-11..09-17）的训练日是 09-11 与 09-12，都在第 2 周里 →
    分母仍是 **2**、但 ``expected_days`` 换成了那两天。
    ⚠️ 若分母无条件取 ``len(sheet.sessions)``，第 2 周那一档会把 09-11/09-12
    之外的日子也算进来、或把「这一周一天都没训」讲成「分母 2、分子 0 = 0%」。
    """
    seeded = _seed(engine)
    student_id = seeded[STUDENT_NOS[0]]
    with Session(engine) as session:
        _prescription(session, student_id, seeded["batch"], generated_on=D(2025, 9, 4))
        session.commit()
    url = f"/api/students/{student_id}/training-logs/completion-rate"
    headers = {"X-Student-Id": str(student_id)}
    first = client.get(url, params={"semester_id": seeded["semester"], "week": 1},
                       headers=headers).json()
    assert first["expected_days"] == ["2025-09-04", "2025-09-05"]
    assert first["prescription_week"] == 1
    second = client.get(url, params={"semester_id": seeded["semester"], "week": 2},
                        headers=headers).json()
    assert second["expected_days"] == ["2025-09-11", "2025-09-12"]
    assert second["prescription_week"] == 2
    assert second["denominator"] == 2
    _freeze(monkeypatch, T(2025, 9, 11, 20, 0))
    assert _checkin(client, student_id, "2025-09-11").status_code == 201
    third = client.get(url, params={"semester_id": seeded["semester"], "week": 2},
                       headers=headers).json()
    assert (third["numerator"], third["denominator"]) == (1, 2)
    assert third["completion_rate"] == 0.5


def test_a_student_cannot_read_another_students_completion_rate(engine, client):
    """**Review Focus 第 1 条**：学生 A 读学生 B 的完成率 → **403**。

    完成率是 RCT 的关键过程指标，而它的 URL 里带着 ``{student_id}``——
    没有闸门的话前端把 id 写错就读到别人的数据（计划 Review Focus 第 1 条原文）。
    """
    seeded = _seed(engine, with_prescription=True)
    owner = seeded[STUDENT_NOS[0]]
    intruder = seeded[STUDENT_NOS[1]]
    denied = client.get(
        f"/api/students/{owner}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(intruder)})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    assert client.get(
        f"/api/students/{owner}/training-logs/completion-rate",
        params={"semester_id": seeded["semester"], "week": 1},
        headers={"X-Student-Id": str(owner)}).status_code == 200


# ===========================================================================
# 批次 D —— 二次小测（批量录入 + 标准化得分）与对接面
# ===========================================================================

#: 小测那一组用的三项成绩。**手算好的期望值**（见下面那条百分位测试的 docstring）：
#: ``(学号, 深蹲次数, 折返秒数)``，折返**秒数越少越好**，故深蹲最好的那个折返也最好
#: ——刻意让它们同向，这样「两项等权平均」的结果一眼能核。
MINI_TEST_ROWS = (
    ("S2025001", 30, 30.0),
    ("S2025002", 25, 34.0),
    ("S2025003", 20, 38.0),
)
MINI_TEST_WEEK = 4          # spec §8.1：每两周一次，取偶数周
MINI_TESTED_ON = "2025-09-28"


def _mini_payload(student_id: int, semester_id: int, squat: int, shuttle,
                  week: int = MINI_TEST_WEEK) -> dict:
    return {
        "student_id": student_id, "semester_id": semester_id, "week": week,
        "item_combo": ["squat_30s", "shuttle_20m"],
        "squat_30s_count": squat, "shuttle_20m_s": shuttle,
        "tested_on": MINI_TESTED_ON,
    }


def test_batch_entry_reports_which_rows_failed_and_keeps_the_rest(engine, client):
    """**部分失败要能报告是哪几条**，而 HTTP 状态仍是 **200**（派单逐字钉住的形状）。

    三条里第 2 条（``index=1``）与第 1 条同学生同学期同周 → 撞
    ``uq_mini_test_student_semester_week``。于是 ``created=2``、``failed`` 里恰好一项、
    且它点出了 ``index`` 与 ``student_id``。

    ⚠️ **为什么不是 409、也不是「全有或全无」**：教师是「按教学班列出学生逐个填」
    （spec §8.1 原文）——一次提交三四十行，其中一行因为「这个学生这周已经录过了」
    而让整批回滚，教师就得找出是哪一行、删掉它、再提交一次。逐条独立
    （``SAVEPOINT``）+ 一份失败清单是他真正需要的。
    ⚠️ 而 ``200`` 而不是 ``207``：派单写的是「``207``-风格 …… HTTP 状态仍是 ``200``」，
    故本仓用 ``200`` + 响应体里的 ``failed`` 列表（``207 Multi-Status`` 是 WebDAV 的码，
    前端的 fetch 封装普遍不认它，会被当成错误分支）。
    """
    seeded = _seed(engine)
    semester_id = seeded["semester"]
    first = seeded[STUDENT_NOS[0]]
    payload = [
        _mini_payload(first, semester_id, 30, 30.0),
        _mini_payload(first, semester_id, 31, 31.0),      # ← 与上一条撞唯一键
        _mini_payload(seeded[STUDENT_NOS[1]], semester_id, 25, 34.0),
    ]
    response = client.post("/api/mini-tests/batch", json=payload, headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert len(body["failed"]) == 1
    failure = body["failed"][0]
    assert failure["index"] == 1
    assert failure["student_id"] == first
    assert failure["message"] != ""
    with Session(engine) as session:
        rows = session.scalars(select(MiniTest)).all()
        assert len(rows) == 2
        assert sorted(r.squat_30s_count for r in rows) == [25, 30]


def test_batch_entry_fills_entered_by_from_the_header(engine, client):
    """``entered_by`` 由 ``X-Teacher-Staff-No`` 填，请求体里**没有**这个字段。

    ⚠️ 与 Task 4 的 ``teacher_staff_no`` 同一条纪律：让客户端传等于让它能冒充别的教师，
    而 ``mini_test.entered_by`` 是「谁录的这一行」的唯一痕迹（那一列刻意不是外键，
    见 :class:`app.db.models.feedback.MiniTest` 的注释）。
    """
    assert "entered_by" not in MiniTestEntryCreate.model_fields
    seeded = _seed(engine)
    response = client.post("/api/mini-tests/batch", json=[
        _mini_payload(seeded[STUDENT_NOS[0]], seeded["semester"], 30, 30.0)],
        headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1
    with Session(engine) as session:
        row = session.scalars(select(MiniTest)).one()
        assert row.entered_by == TEACHER_STAFF_NO
        # normalized_score 由**读侧**现算，录入时留 NULL（见下一条）
        assert row.normalized_score is None


def test_batch_entry_needs_a_registered_teacher(engine, client):
    """缺头 401、工号不在册 403；被拒时一行都不写。"""
    seeded = _seed(engine)
    payload = [_mini_payload(seeded[STUDENT_NOS[0]], seeded["semester"], 30, 30.0)]
    assert client.post("/api/mini-tests/batch", json=payload).status_code == 401
    assert client.post("/api/mini-tests/batch", json=payload,
                       headers=UNKNOWN_TEACHER).status_code == 403
    with Session(engine) as session:
        assert session.scalars(select(MiniTest)).all() == []


def test_squat_score_is_the_count_and_shuttle_score_is_the_within_section_percentile(
        engine, client):
    """spec §8.1 的算式：**深蹲得分 = 次数**、**折返得分 = 班内百分位反查**、
    **综合分 = 两项等权平均**。

    班内 3 人的折返秒数是 ``30.0 / 34.0 / 38.0``（越少越好），故百分位反查
    （标准 percentile rank：``(比自己慢的人数 + 0.5 × 并列人数) / 总人数 × 100``）：

    * ``30.0`` → ``(2 + 0.5×1) / 3 × 100 = 83.333…`` → **83.33**
    * ``34.0`` → ``(1 + 0.5×1) / 3 × 100 = 50.0``     → **50.0**
    * ``38.0`` → ``(0 + 0.5×1) / 3 × 100 = 16.666…`` → **16.67**

    综合分用**未 round 的**百分位再平均、最后 round 两位：

    * ``(30 + 83.3333) / 2 = 56.6666…`` → **56.67**
    * ``(25 + 50.0) / 2 = 37.5``        → **37.5**
    * ``(20 + 16.6666) / 2 = 18.3333…`` → **18.33**

    ⚠️ **上面这 6 个数全部手算、字面写死**（硬规矩 #35），不从被测代码读回来比。
    ⚠️ **量纲是混的**（次数 vs 百分位），如实记录为关切：spec §8.1 逐字要求
    「深蹲得分 = 次数（直接用）」，故本端点照它算，**不**擅自把深蹲也转成百分位
    ——那是改 spec 的算法、是专家的活。⚠️ 而它的唯一消费者
    ``RED_MINITEST_DROP``（「连续两次下降 ≥ 5%」）对量纲**不敏感**：两次小测用同一个
    算式，比值就有意义。故混合量纲损害的是「综合分的绝对值可解释性」，
    不是预警规则的正确性。
    """
    seeded = _seed(engine)
    payload = [_mini_payload(seeded[no], seeded["semester"], squat, shuttle)
               for no, squat, shuttle in MINI_TEST_ROWS]
    assert client.post("/api/mini-tests/batch", json=payload,
                       headers=TEACHER_HEADERS).json()["created"] == 3

    response = client.get("/api/mini-tests/normalized",
                          params={"semester_id": seeded["semester"], "week": MINI_TEST_WEEK},
                          headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["semester_id"] == seeded["semester"]
    assert body["week"] == MINI_TEST_WEEK
    assert len(body["sections"]) == 1
    section = body["sections"][0]
    assert section["course_section_id"] == seeded["section"]
    by_student = {e["student_id"]: e for e in section["entries"]}
    assert sorted(by_student) == sorted(seeded[n] for n, _, _ in MINI_TEST_ROWS)
    expected = {
        seeded["S2025001"]: (30.0, 83.33, 56.67),
        seeded["S2025002"]: (25.0, 50.0, 37.5),
        seeded["S2025003"]: (20.0, 16.67, 18.33),
    }
    for student_id, (squat, shuttle, composite) in expected.items():
        entry = by_student[student_id]
        assert entry["squat_score"] == squat, student_id
        assert entry["shuttle_score"] == shuttle, student_id
        assert entry["composite"] == composite, student_id
    assert body["unassigned"] == []


def test_a_null_shuttle_time_stays_out_of_the_percentile_and_gets_a_null_score(engine,
                                                                              client):
    """选了别的测试项组合（``shuttle_20m_s IS NULL``）的那一行：**不进**百分位的样本、
    自己的折返得分与综合分都是 ``null``（**不是 0**）。

    ⚠️ 两个 ``null`` 各有各的理由：① 它不进样本，否则一个「没测」的人会把全班的
    百分位往下拽（他会被当成「最慢的那个」，于是所有人都变好）；
    ② 综合分是两项等权平均，**一项缺失就没有平均可算**——把 ``null`` 当 0
    会让这个学生的综合分变成「深蹲分的一半」，那是关于他的一句假话
    （与 P5-A2「不知道不得讲成 0%」同一条纪律）。
    """
    seeded = _seed(engine)
    payload = [
        _mini_payload(seeded["S2025001"], seeded["semester"], 30, 30.0),
        _mini_payload(seeded["S2025002"], seeded["semester"], 25, 34.0),
        _mini_payload(seeded["S2025003"], seeded["semester"], 20, None),
    ]
    assert client.post("/api/mini-tests/batch", json=payload,
                       headers=TEACHER_HEADERS).json()["created"] == 3
    body = client.get("/api/mini-tests/normalized",
                      params={"semester_id": seeded["semester"], "week": MINI_TEST_WEEK},
                      headers=TEACHER_HEADERS).json()
    by_student = {e["student_id"]: e for e in body["sections"][0]["entries"]}
    # 样本只剩 2 人：30.0 → (1 + 0.5)/2×100 = 75.0；34.0 → (0 + 0.5)/2×100 = 25.0
    assert by_student[seeded["S2025001"]]["shuttle_score"] == 75.0
    assert by_student[seeded["S2025001"]]["composite"] == 52.5     # (30 + 75) / 2
    assert by_student[seeded["S2025002"]]["shuttle_score"] == 25.0
    assert by_student[seeded["S2025002"]]["composite"] == 25.0     # (25 + 25) / 2
    missing = by_student[seeded["S2025003"]]
    assert missing["squat_score"] == 20.0
    assert missing["shuttle_score"] is None
    assert missing["composite"] is None


def test_a_student_with_no_section_is_reported_unassigned_and_gets_no_score(engine, client):
    """有小测、但那个学期**不在任何教学班**的学生 → 进 ``unassigned``、**不给分数**。

    ⚠️ 「班内百分位」在没有任何班的时候**无定义**。三种候选处置里本仓选第三种：
    ① 当成一个只有他一个人的班 → 他会拿到 ``50.0``（标准公式在 ``n=1`` 时的自洽结果），
      而那个 50 看起来像真的算过；② 给 ``0`` → 把「不知道」讲成「最差」；
    ③ **列进 ``unassigned`` 并点名是谁** → 教师看得见「这个学生没编班」，
      而那本来就是要修的数据问题（选课记录漏了）。
    """
    seeded = _seed(engine)
    payload = [_mini_payload(seeded[no], seeded["semester"], squat, shuttle)
               for no, squat, shuttle in MINI_TEST_ROWS]
    payload.append(_mini_payload(seeded[OUTSIDER_NO], seeded["semester"], 15, 42.0))
    assert client.post("/api/mini-tests/batch", json=payload,
                       headers=TEACHER_HEADERS).json()["created"] == 4
    body = client.get("/api/mini-tests/normalized",
                      params={"semester_id": seeded["semester"], "week": MINI_TEST_WEEK},
                      headers=TEACHER_HEADERS).json()
    assert [u["student_id"] for u in body["unassigned"]] == [seeded[OUTSIDER_NO]]
    assert [e["student_id"] for e in body["sections"][0]["entries"]] == [
        seeded[no] for no, _, _ in MINI_TEST_ROWS]
    # ⚠️ 未编班的那一行**不进**班内样本，故三个人的百分位与上一条测试逐字相同
    by_student = {e["student_id"]: e for e in body["sections"][0]["entries"]}
    assert by_student[seeded["S2025001"]]["shuttle_score"] == 83.33


def test_the_normalized_route_is_not_swallowed_by_the_generic_read_route(engine, client):
    """**``GET /api/mini-tests/normalized`` 必须命中特例端点，不是泛型的 read。**

    ⚠️ 这一条钉的是 :mod:`app.api.routers` 的 **include 顺序**，而那个顺序在本 Task
    之前是「不承重」的（它的模块 docstring 逐字这么写，理由是 Task 4 的四个路径与
    23 个资源的五个端点「没有一个同形」）。**本 Task 让它承重了**：
    ``mini-tests`` 是只读资源，故泛型工厂**注册**了 ``GET /api/mini-tests/{mini_test_id}``，
    而 ``normalized`` 与 ``{mini_test_id}`` **同形**（都是两段、末段一个占位）。
    FastAPI 按注册先后取先匹配的，故若把特例 router include 在泛型**之后**，
    ``normalized`` 会被当成 ``mini_test_id`` 去转 ``int`` → **422**。
    ⚠️ 那个 422 尤其阴险：它的 ``detail`` 会说「``mini_test_id`` 不是一个整数」，
    于是下一个人会去修前端传的参、而不是修 include 顺序。
    """
    seeded = _seed(engine)
    response = client.get("/api/mini-tests/normalized",
                          params={"semester_id": seeded["semester"], "week": MINI_TEST_WEEK},
                          headers=TEACHER_HEADERS)
    assert response.status_code == 200, response.text
    assert set(response.json()) >= {"semester_id", "week", "sections", "unassigned"}
    # 泛型的 read 仍然照常工作（两个路由共存，不是「特例抢走了整个前缀」）
    created = client.post("/api/mini-tests/batch", json=[
        _mini_payload(seeded[STUDENT_NOS[0]], seeded["semester"], 30, 30.0)],
        headers=TEACHER_HEADERS)
    assert created.json()["created"] == 1
    with Session(engine) as session:
        pk = session.scalars(select(MiniTest.id)).one()
    assert client.get(f"/api/mini-tests/{pk}").status_code == 200


def test_the_seven_endpoints_are_registered_with_the_documented_methods(app):
    """七个端点的**路径 + 方法**逐个点名（派单 Interfaces / Produces 那一份清单）。

    ⚠️ 期望侧是**手写的字面量清单**、被测侧是 ``app.openapi()["paths"]`` 的运行时口径
    （两侧不同源）。少了本条，把一个路径拼错（``/api/rpe-status`` 而不是
    ``/api/class-sessions/{id}/rpe-status``）只会让前端 404，而后端全绿。

    ⚠️⚠️ **被测侧刻意用 ``openapi()`` 而不是 ``app.routes``**（本 Task 实测踩到的一个坑，
    取证 ``t5_probes/routes_probe.py``）：在 **FastAPI 0.141.1 / Starlette 1.7.0** 上
    ``include_router`` **不再把子路由展平进** ``app.routes``——实测 ``len(app.routes) == 6``，
    其中 4 个是内置的 ``Route``（``/openapi.json`` / ``/docs`` 一类）、
    1 个是 ``/api/health`` 那个 ``APIRoute``，而**全部** include 进来的路由折叠成了
    **一个** ``_IncludedRouter`` 节点。于是「遍历 ``app.routes`` 找 ``/api/`` 前缀」
    在这个版本上只能看见 ``/api/health`` 一条，而 ``openapi()["paths"]`` 里
    ``/api/`` 开头的是 **56** 条（完整）。⚠️ 两种口径都是运行时的，但**前者不完整**，
    故按硬规矩 #103 采后者、并把前者标注为不可用。
    ⚠️ 这也与 Task 3/4 的既有测试一致（``tests/api/test_crud.py`` 的那几条
    OpenAPI 面守卫走的都是 ``openapi()``）。

    ⚠️ 两个 ``POST`` 回 **201 + Location**（它们创建了新资源，与 Task 3 的 23 个资源
    同一约定），另两个 ``POST`` 回 **200**（它们是「对已有资源做了一次操作」，
    与 Task 4 的 ``overrides`` / ``regenerate`` 同一约定）——那一半由各自的
    行为测试钉（``test_submitting_rpe_fills_submitted_at_server_side`` 断言了
    ``Location``），本条只钉「路径 + 方法存在」。
    """
    # ⚠️ ``paths[p]`` 的键**除了方法名还可能有** ``"parameters"``（该路径下全部操作
    # 共享的参数），故按白名单过滤，不能直接 ``for method in ops``。
    methods = {"get", "post", "patch", "put", "delete", "head", "options"}
    observed = {
        (path, method.upper())
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in methods
    }
    expected = {
        ("/api/class-sessions/{class_session_id}/open-rpe", "POST"),
        ("/api/rpe-records", "POST"),
        ("/api/class-sessions/{class_session_id}/rpe-status", "GET"),
        ("/api/training-logs", "POST"),
        ("/api/students/{student_id}/training-logs/completion-rate", "GET"),
        ("/api/mini-tests/batch", "POST"),
        ("/api/mini-tests/normalized", "GET"),
    }
    missing = sorted(expected - observed)
    assert missing == [], f"这七个端点没有全部注册：{missing}"


def test_the_request_models_cannot_carry_the_server_filled_fields():
    """**服务端填的字段一个都不在请求模型上**（结构上不可能伪造）。

    ⚠️ 这一条是「先算后写」之外的另一半防线：Task 4 的
    ``test_the_override_request_model_cannot_carry_the_two_server_filled_fields``
    钉的是同一件事的处方侧。钉「字段不在模型上」而不是「多传会 422」，
    因为 Pydantic 缺省 ``extra="ignore"``——多传的那些键会被**静默丢掉**，
    于是「模型上没有这个字段」才是「服务端那一份不可能被覆盖」的真正保证。
    """
    banned = {
        RpeSubmitCreate: ("student_id", "submitted_at"),
        TrainingLogCreate: ("student_id", "submitted_at", "late", "source", "batch_id"),
        MiniTestEntryCreate: ("entered_by", "normalized_score"),
    }
    for model, names in banned.items():
        for name in names:
            assert name not in model.model_fields, (model.__name__, name)
    # ⚠️ 反过来也要钉：该由客户端传的字段一个都不能少（少一个前端就没法用）
    assert list(RpeSubmitCreate.model_fields) == [
        "class_session_id", "rpe", "elapsed_seconds", "rpe_token"]
    assert list(TrainingLogCreate.model_fields) == [
        "log_date", "completed", "duration_min", "feeling", "is_rest_day"]
    assert list(MiniTestEntryCreate.model_fields) == [
        "student_id", "semester_id", "week", "item_combo",
        "squat_30s_count", "shuttle_20m_s", "tested_on"]
