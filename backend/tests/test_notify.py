"""``app/notify.py`` 的守卫（Plan 03 Task 7）。

三件事各有一支：

1. **``InAppChannel`` 真的写出一行合法的 ``notification``**——列宽、CHECK、两个可空外键、
   ``is_read`` 缺省、``created_at`` 由注入的时钟给出（本仓的表**一律不带** Python 侧
   ``default=``，故「忘了传时钟」在别处是静默的 ``NULL``，在这里是 ``NOT NULL`` 违例）。
2. **值域读的是模型类常量、不是第二份字面串**（Global Constraint #3 单一所有者）：
   ``channel="in_app"`` 与 ``recipient_kind`` 都从
   :attr:`~app.db.models.feedback.Notification` 的类常量取，故改词表只改一处。
3. **两个未来通道是骨架**：照 :mod:`app.adapters.http_lepao` 的形状，四个方法一律
   ``NotImplementedError``，且**消息里点明契约住在本模块 docstring**——
   spec §8.3 逐字「原型不做真实推送（需微信订阅消息资质 / 短信通道）」。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律字面写在测试里
（``"in_app"`` / ``"student"`` / 那些标题正文），**不从被测模块读回来**。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError

from app.db import models as M
# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：Plan 03 的 7 张反馈/预警表**刻意不在**
#    app.db.models 的公有导入面上，写 M.Alert 会当场 AttributeError。
from app.db.models.feedback import Alert, Notification
from app.db.session import Session, init_db
from app.notify import (
    IN_APP,
    RECIPIENT_STUDENT,
    RECIPIENT_TEACHER,
    InAppChannel,
    NotificationChannel,
    SmsChannel,
    WechatSubscribeChannel,
    now_local,
)

MOMENT = dt.datetime(2025, 9, 17, 8, 30, 0)


@pytest.fixture
def session():
    """建好 25 张表的**空**内存库（``PRAGMA foreign_keys=ON`` 对它同样生效）。"""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as s:
        yield s


def _student(session, student_no: str = "2025001") -> M.Student:
    row = M.Student(
        student_no=student_no, name="学生" + student_no[-3:],
        sex="male", birth=dt.date(2006, 3, 4), grade=1,
    )
    session.add(row)
    session.flush()
    return row


def _count(session) -> int:
    return session.scalar(select(func.count()).select_from(Notification))


def _channel() -> InAppChannel:
    return InAppChannel(now=lambda: MOMENT)


# --- 支 1：InAppChannel 写出一行合法的通知 ---------------------------------


def test_send_writes_one_in_app_row_with_the_injected_clock(session):
    student = _student(session)
    row = _channel().send(
        session,
        recipient_kind=RECIPIENT_STUDENT,
        recipient_id=student.id,
        title="补练提醒",
        body="你已经连续 2 个训练日没有打卡了。",
    )
    session.flush()

    assert row.id is not None
    assert row.recipient_kind == "student"
    assert row.recipient_id == student.id
    assert row.channel == "in_app"
    assert row.title == "补练提醒"
    assert row.body == "你已经连续 2 个训练日没有打卡了。"
    # 两个关联外键缺省都是 NULL（一条不关联任何预警的普通消息）
    assert row.alert_id is None
    assert row.prescription_id is None
    # 新消息一律未读：红点与消息中心都读这一列
    assert row.is_read is False
    # ⚠️ 时钟是**注入**的：本仓的表不带 Python 侧 default，故这一格只能来自 now
    assert row.created_at == MOMENT
    assert _count(session) == 1


def test_send_persists_the_optional_alert_and_prescription_links(session):
    semester = M.Semester(
        name="2025-2026-1", start_date=dt.date(2025, 9, 1),
        end_date=dt.date(2026, 1, 20), weeks=16, is_current=True,
    )
    teacher = M.Teacher(staff_no="T001", name="教师一")
    session.add_all([semester, teacher])
    session.flush()
    batch = M.DailySyncRun(
        semester_id=semester.id, business_date=dt.date(2025, 9, 15), status="success"
    )
    session.add(batch)
    session.flush()
    section = M.CourseSection(
        semester_id=semester.id, teacher_id=teacher.id, name="一班",
        grouping_mode="administrative",
    )
    session.add(section)
    session.flush()
    student = _student(session)
    alert = Alert(
        semester_id=semester.id, student_id=student.id,
        subject_key=f"student:{student.id}", level="yellow",
        rule_id="YELLOW_CHECKIN_GAP", trigger_snapshot={"checkin_gap_days": 2},
        triggered_at=MOMENT, status="pending", batch_id=batch.id,
        window_key="gap2025-09-15",
    )
    session.add(alert)
    session.flush()

    row = _channel().send(
        session,
        recipient_kind=RECIPIENT_STUDENT,
        recipient_id=student.id,
        title="补练提醒",
        body="正文",
        alert_id=alert.id,
    )
    session.flush()
    assert row.alert_id == alert.id
    assert row.prescription_id is None


def test_a_notification_survives_the_deletion_of_its_alert(session):
    """``alert_id`` 带 ``ON DELETE SET NULL``：重放删掉预警不得连带删掉已推出去的消息。

    这一条是 Task 2 顶回 3 的行为面：``Alert`` 进了 ``_replay_cleanup`` 的清单之后，
    每次重放都会按批删预警，而消息**刻意不带** ``batch_id``、不在那份清单里。
    """
    semester = M.Semester(
        name="2025-2026-1", start_date=dt.date(2025, 9, 1),
        end_date=dt.date(2026, 1, 20), weeks=16, is_current=True,
    )
    session.add(semester)
    session.flush()
    batch = M.DailySyncRun(
        semester_id=semester.id, business_date=dt.date(2025, 9, 15), status="success"
    )
    session.add(batch)
    session.flush()
    student = _student(session)
    alert = Alert(
        semester_id=semester.id, student_id=student.id,
        subject_key=f"student:{student.id}", level="green", rule_id="GREEN_MASTERY",
        trigger_snapshot={}, triggered_at=MOMENT, status="pending",
        batch_id=batch.id, window_key=f"{semester.id}:1",
    )
    session.add(alert)
    session.flush()
    row = _channel().send(
        session,
        recipient_kind=RECIPIENT_STUDENT,
        recipient_id=student.id,
        title="电子勋章",
        body="本周完成度 100%",
        alert_id=alert.id,
    )
    session.flush()
    session.delete(alert)
    session.commit()

    kept = session.get(Notification, row.id)
    assert kept is not None, "消息被连带删掉了（ON DELETE SET NULL 失效）"
    assert kept.alert_id is None
    assert kept.title == "电子勋章"
    assert session.scalar(select(func.count()).select_from(Alert)) == 0


def test_send_does_not_commit(session):
    """通道**不提交**：事务边界由调用方掌握（与 :func:`app.db.repo.upsert` 同一条口径）。

    ⚠️ 这条口径是承重的：``alert_stage`` 跑在 ``run_daily`` 的 SAVEPOINT 里，
    而 ``POST /api/alerts/{id}/handle`` 要「写调整 + 发消息 + 改状态」三步一起成功或
    一起失败。通道自己 commit 的话，一次失败的处置会留下一条已经推出去的消息。
    """
    student = _student(session)
    session.commit()  # 把学生那一行落定，于是下面这条是唯一未提交的写入
    _channel().send(
        session,
        recipient_kind=RECIPIENT_STUDENT,
        recipient_id=student.id,
        title="t",
        body="b",
    )
    session.rollback()
    assert _count(session) == 0


# --- 支 2：值域只有一个所有者 ---------------------------------------------


def test_the_channel_and_recipient_vocabulary_comes_from_the_model_not_a_second_copy():
    """三个常量必须是 :class:`Notification` 那两个类常量的**成员**，不是抄来的字面串。

    ⚠️ 两侧不同源（硬规矩 #35）：期望侧写的是模型类常量（``Notification.CHANNELS``），
    被测侧是 ``app.notify`` 的三个常量。抄第二份字符串的话，改词表只改一处、
    另一处静默写不进库（``ck_notification_channel`` 当场拒收）。
    """
    assert IN_APP in Notification.CHANNELS
    assert IN_APP == "in_app"
    assert RECIPIENT_STUDENT in Notification.RECIPIENT_KINDS
    assert RECIPIENT_TEACHER in Notification.RECIPIENT_KINDS
    assert RECIPIENT_STUDENT == "student"
    assert RECIPIENT_TEACHER == "teacher"


def test_an_unknown_channel_is_rejected_by_the_check_constraint(session):
    """反证：值域**真的**被 DB 强制，故「抄一份字面串」是会炸的、不是静默的。"""
    student = _student(session)
    row = Notification(
        recipient_kind="student", recipient_id=student.id, channel="carrier_pigeon",
        title="t", body="b", created_at=MOMENT,
    )
    session.add(row)
    with pytest.raises(IntegrityError):
        session.flush()


def test_the_three_channels_cover_exactly_the_model_vocabulary():
    """三个通道类的 ``CHANNEL`` 合起来**恰好**是 ``Notification.CHANNELS``。

    ⚠️ 它是「骨架也进值域对账」的守卫：往词表里加第四个通道而忘了建类（或反过来
    建了类而词表里没有它）都当场红。期望侧是模型常量，被测侧是三个类属性。
    """
    assert {InAppChannel.CHANNEL, WechatSubscribeChannel.CHANNEL, SmsChannel.CHANNEL} == (
        Notification.CHANNELS
    )
    assert len(Notification.CHANNELS) == 3


# --- 支 3：两个未来通道是骨架 ---------------------------------------------


@pytest.mark.parametrize(
    "cls", [WechatSubscribeChannel, SmsChannel], ids=["wechat", "sms"]
)
def test_the_two_future_channels_raise_for_every_method(cls):
    """照 :mod:`app.adapters.http_lepao` 的形状：一律 ``NotImplementedError``。

    ⚠️ **``send`` 也抛**：一个「静默返回 ``None``」的骨架会让调用方以为消息推出去了，
    而那正是 spec §8.3「原型不做真实推送」最坏的落地方式（教师点了「推送减量 20%」、
    界面显示成功、学生什么都没收到）。
    """
    channel = cls()
    with pytest.raises(NotImplementedError):
        channel.send(
            None,
            recipient_kind=RECIPIENT_STUDENT,
            recipient_id=1,
            title="t",
            body="b",
        )


@pytest.mark.parametrize(
    "cls", [WechatSubscribeChannel, SmsChannel], ids=["wechat", "sms"]
)
def test_the_two_future_channels_declare_the_channel_they_would_use(cls):
    assert cls.CHANNEL in Notification.CHANNELS
    assert cls.CHANNEL != IN_APP


# --- 支 4：契约与协议 ------------------------------------------------------


def test_every_channel_satisfies_the_protocol():
    """三个类都是 :class:`NotificationChannel`（``runtime_checkable`` 的 Protocol）。

    ⚠️ 它只检查**方法名在不在**，不检查签名——故 :func:`test_the_protocol_names_the_seven_keyword_arguments`
    另外钉住签名。两条合起来才是「换通道不改调用方」。
    """
    for cls in (InAppChannel, WechatSubscribeChannel, SmsChannel):
        assert isinstance(cls(), NotificationChannel), cls.__name__


def test_the_protocol_names_the_seven_keyword_arguments():
    """``send`` 的签名逐字是简报 Interfaces 钉住的那一个（7 个形参、5 个 keyword-only）。

    ⚠️ 用 :func:`inspect.signature` 而不是数源码里的逗号（硬规矩 #89：运行时口径）。
    期望侧是**字面**写出的 7 个名字与 5 个 kinds，不从被测模块反推。
    """
    import inspect

    params = inspect.signature(NotificationChannel.send).parameters
    assert list(params) == [
        "self", "session", "recipient_kind", "recipient_id",
        "title", "body", "alert_id", "prescription_id",
    ]
    assert len(params) == 8  # self + 7
    keyword_only = [
        name for name, p in params.items()
        if p.kind is inspect.Parameter.KEYWORD_ONLY
    ]
    assert keyword_only == [
        "recipient_kind", "recipient_id", "title", "body", "alert_id", "prescription_id",
    ]
    assert params["alert_id"].default is None
    assert params["prescription_id"].default is None
    # InAppChannel 的实现与协议同形（换通道不改调用方的前提）
    assert list(inspect.signature(InAppChannel.send).parameters) == list(params)


def test_now_local_is_naive_and_follows_the_configured_timezone():
    """``now_local()`` 返回 **naive** 本地时刻（本仓的 ``DateTime`` 列存 naive）。

    ⚠️ ``replace(tzinfo=None)`` 是承重的：aware 与 naive 相比会当场 ``TypeError``，
    而它炸的地方离真因（一次 ``datetime.now(ZoneInfo(...))``）很远。
    ⚠️ 上下界用**现场取的** UTC 与本地时刻夹（不写死一个日期），故这条测试任何时候跑都成立。
    """
    from zoneinfo import ZoneInfo

    from app.config import TIMEZONE

    got = now_local()
    assert got.tzinfo is None
    lower = dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None) - dt.timedelta(minutes=5)
    upper = dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None) + dt.timedelta(minutes=5)
    assert lower <= got <= upper
