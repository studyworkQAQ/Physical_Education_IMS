"""spec §8.3 的消息通知：``NotificationChannel`` 契约 + ``InAppChannel`` + 两个未来通道的骨架。

**原型只做站内消息**（计划 File Structure「本计划刻意不做」第 2 条，spec §8.3 原文逐字：
「原型不做真实推送（需微信订阅消息资质 / 短信通道）」）。故本模块一个真的实现、两个
``raise NotImplementedError`` 的骨架，形状照 :mod:`app.adapters.http_lepao`
（那里同样是「一个 Mock 能跑通全链路、一个 HTTP 骨架四个方法全抛」）。

----------------------------------------------------------------------------
本模块在依赖图里的位置
----------------------------------------------------------------------------

``app/notify.py`` 住在 ``app/`` **根下**，不属于任何一层子目录，故
:data:`tests.architecture.test_layering.SCANNED_DIRS`（``pipeline`` / ``db`` / ``domain`` /
``api``）**扫不到它**——与 ``app/main.py`` / ``app/config.py`` / ``app/refdata*.py`` 同档。
这是有意的：

* ``api`` 要 import 它（:data:`~tests.architecture.test_layering.API_ALLOWED_PREFIXES`
  里 ``"app.notify"`` 那一项是 Plan 03 Task 1 **预留**的，它的注释逐字写了「Task 1 给
  ``api`` 定依赖方向时就把 ``notify`` 列进去了」）；
* ``pipeline`` 也要 import 它（``alert_stage`` 触发一条 ``YELLOW_CHECKIN_GAP`` 时
  **自动**发补练提醒，spec §8.2 逐字「自动发『补练提醒』，无需教师介入」）；
* 而 ``pipeline`` 与 ``api`` 之间是**单向**的（``api → pipeline``，反向被守卫禁止）。

于是「两层都要用的一个工具」只能住在两层**之外**。放进 ``app/api/`` 会让
``alert_stage`` 反向依赖 ``api``（当场撞
:func:`~tests.architecture.test_layering.test_api_layer_dependency_direction_is_one_way`
的反向那一圈）；放进 ``app/pipeline/`` 在守卫上可行（``api → pipeline`` 是许可方向），
但语义上不对：发消息不是批处理的一个阶段。

⚠️ **本模块只 import ``app.db`` 与 ``app.config``**（两个都在任何层的许可方向上），
故它不可能是环里的一环。

----------------------------------------------------------------------------
``notification`` 这张表的三条性质决定了本模块能做什么
----------------------------------------------------------------------------

1. **它不带 ``batch_id``**（:mod:`app.db.models.feedback` 的模块 docstring：消息是
   **已经推给某个人**的东西，重放那天按批删掉它，学生端消息中心的红点会凭空消失）。
   于是它**不在** :func:`app.pipeline.daily._replay_cleanup` 的清单里——
   **「从任何入口都删不掉一行通知」是有意的**。本模块因此也不提供任何删除/撤回能力。
2. **它的两个外键都带 ``ON DELETE SET NULL``**（``alert_id`` / ``prescription_id``）。
   这正是第 1 条能成立的前提：``alert`` **在**重放清单里（Task 7 接进去的），
   普通外键会让重放当场 ``FOREIGN KEY constraint failed``、整批回滚。
   代价是断开关联的通知再也点不回原预警，前端应把 ``alert_id IS NULL`` 渲染成纯文本。
3. **``created_at`` NOT NULL 且无缺省**：时钟一律由调用方注入（本仓全部表的统一约定），
   故本模块的时钟住址是 :func:`now_local`，而 ``InAppChannel`` 收一个 ``now`` 可调用对象。

----------------------------------------------------------------------------
值域只有一个所有者
----------------------------------------------------------------------------

``channel`` 与 ``recipient_kind`` 两列各有 CHECK 约束
（``ck_notification_channel`` / ``ck_notification_recipient_kind``），值域的唯一所有者是
:class:`~app.db.models.feedback.Notification` 的两个类常量。本模块**不抄第二份字符串**：
下面那三个常量都经 :func:`_vocabulary` 与模型常量**对账**，对不上就在 **import 期**响亮
失败——而不是等到某一次 ``send`` 落库时被 CHECK 拒收（那时报错点离真因隔两层，
而 SQLite 的消息只有 ``CHECK constraint failed``）。

⚠️ 它**守不住**「词表被扩了而本模块没跟上」（硬规矩 #39）：往
``Notification.CHANNELS`` 加第四个值不会让本模块炸。那一档由
``tests/test_notify.py::test_the_three_channels_cover_exactly_the_model_vocabulary``
按**集合相等**钉住。
"""
import datetime as dt
from collections.abc import Callable, Iterable
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import TIMEZONE
from app.db.models.feedback import Notification

__all__ = [
    "IN_APP",
    "RECIPIENT_STUDENT",
    "RECIPIENT_TEACHER",
    "InAppChannel",
    "NotificationChannel",
    "SmsChannel",
    "WechatSubscribeChannel",
    "now_local",
]


def now_local() -> dt.datetime:
    """**现在几点**，naive 本地时刻（时区 = :data:`app.config.TIMEZONE`）。

    ⚠️ ``.replace(tzinfo=None)`` **是承重的**：本仓的 ``DateTime`` 列存 naive
    （SQLite 没有时区类型），而 aware 与 naive 相比会当场
    ``TypeError: can't compare offset-naive and offset-aware datetimes``——
    炸的地方（某一次 ``ORDER BY`` 或某一条判据）离真因（这一行）很远。
    口径逐字同 :func:`app.api.routers.feedback._now_local`（那是 ``api`` 层自己的
    时钟住址，两处刻意不合并：本模块在 ``app/`` 根下，而那一处在 router 里，
    合并意味着让 ``api`` 的一个私有函数成为跨层的所有者）。

    ⚠️ **测试一律注入固定的 ``now``**（``InAppChannel(now=lambda: MOMENT)``），
    不要 monkeypatch 本函数：注入点是构造参数，patch 一个模块级函数会连带改掉
    同一进程里其它测试看到的时钟。
    """
    return dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


def _vocabulary(value: str, allowed: Iterable[str], column: str) -> str:
    """把一个**字面**取值与模型类常量对账，对不上就在 import 期响亮失败。

    存在的理由见模块 docstring 的「值域只有一个所有者」那一节：不对账的话，
    一个拼错的通道名要等到 ``send`` 落库时才被 CHECK 拒收，而那时 SQLite 只说
    ``CHECK constraint failed: notification.channel``——不说期望值是什么、
    也不说这个串是从哪个模块来的。
    """
    allowed_set = set(allowed)
    if value not in allowed_set:
        raise ValueError(
            f"{value!r} 不在 {column} 的取值域 {sorted(allowed_set)} 内"
            f"（唯一所有者是 app.db.models.feedback.Notification 的类常量）"
        )
    return value


#: ``notification.channel`` 的**站内消息**档（spec §8.3 的 ``InAppChannel``）。
IN_APP = _vocabulary("in_app", Notification.CHANNELS, "notification.channel")

#: ``notification.recipient_kind`` 的两档。⚠️ ``recipient_id`` **不是外键**
#: （它是多态的：``student`` 时指 ``student.id``、``teacher`` 时指 ``teacher.id``，
#: 而 SQLite 没有跨两张父表的外键写法），故这两列**必须一起**才能定位接收者。
RECIPIENT_STUDENT = _vocabulary(
    "student", Notification.RECIPIENT_KINDS, "notification.recipient_kind"
)
RECIPIENT_TEACHER = _vocabulary(
    "teacher", Notification.RECIPIENT_KINDS, "notification.recipient_kind"
)


@runtime_checkable
class NotificationChannel(Protocol):
    """spec §8.3 的 ``NotificationChannel``：**发一条消息给一个人**。

    ⚠️ 用 :class:`~typing.Protocol` 而不是 ABC（结构性子类型）：加一个通道不该要求
    它 import 本模块并显式继承——那会让「未来实现」多一个依赖。
    ``@runtime_checkable`` 让 ``isinstance(obj, NotificationChannel)`` 可用，
    ⚠️ 但它**只检查方法名在不在、不检查签名**（Python 自己的限制），故
    ``tests/test_notify.py`` 另有一条按 :func:`inspect.signature` 钉住 7 个形参的测试。

    七个形参逐个说（简报 Interfaces / Produces 逐字钉住的签名）：

    ``session``
        写库用的会话。**通道不 commit、不 flush**（事务边界由调用方掌握，
        与 :func:`app.db.repo.upsert` 同一条口径）：``alert_stage`` 跑在
        ``run_daily`` 的 SAVEPOINT 里，而 ``POST /api/alerts/{id}/handle`` 要
        「写调整 + 发消息 + 改状态」三步一起成功或一起失败。
    ``recipient_kind`` / ``recipient_id``
        接收者。两列合起来才是 spec §4.6 那一格「接收者」，理由见
        :data:`RECIPIENT_STUDENT` 的注释。
    ``title`` / ``body``
        给人看的自由文本（两列都是 ``Text``，没有列宽口径）。
    ``alert_id`` / ``prescription_id``
        可选的关联。⚠️ 两列都带 ``ON DELETE SET NULL``，故调用方**可以**传一个
        将来会被重放删掉的 id；断开关联之后前端应渲染成不可点的纯文本。
    """

    def send(
        self,
        session: Session,
        *,
        recipient_kind: str,
        recipient_id: int,
        title: str,
        body: str,
        alert_id: int | None = None,
        prescription_id: int | None = None,
    ) -> Notification:
        """写一条消息并返回那一行（**未 flush**，``id`` 在调用方 flush 前是 ``None``）。"""
        ...


class InAppChannel:
    """站内消息（spec §8.3 唯一在原型里落地的一档）。

    ``channel`` 一律是 :data:`IN_APP`，``is_read`` 一律是 ``False``
    （红点与消息中心都读它，而「刚发出去」与「已读」必须是两档）。
    ``created_at`` 取自构造时注入的 ``now``——⚠️ **不读模块级时钟**：
    那会让「这条消息是什么时候推的」在测试里不可复现（跨过午夜跑同一个测试会得到
    不同的日期，而 ``alert_stage`` 的测试要按天对账）。

    ⚠️ **本类不做「同一个人同一条预警只发一次」的去重**（硬规矩 #39）：
    ``notification`` 表**没有任何唯一约束**（Task 3 的 P3-B2 实测：全库三张这样的表之一），
    故重复调用就是重复插行。去重在**调用方**：``alert_stage`` 只对
    「本批**新**落库的预警」发消息（撞上 ``uq_alert_rule_subject_semester_window``
    的那一条走 ``deduped`` 分支、直接 ``continue``），于是同一次触发只发一次。
    守卫是 ``tests/pipeline/test_alert_stage.py`` 的
    ``test_the_same_trigger_raises_one_alert_not_three``。
    """

    #: 本通道写进 ``notification.channel`` 的值。
    CHANNEL = IN_APP

    def __init__(self, *, now: Callable[[], dt.datetime] = now_local) -> None:
        self._now = now

    def __repr__(self) -> str:
        return f"{type(self).__name__}(channel={self.CHANNEL!r})"

    def send(
        self,
        session: Session,
        *,
        recipient_kind: str,
        recipient_id: int,
        title: str,
        body: str,
        alert_id: int | None = None,
        prescription_id: int | None = None,
    ) -> Notification:
        """写一行 ``notification``（``channel="in_app"``）并返回它。**不 flush、不 commit。**"""
        row = Notification(
            recipient_kind=recipient_kind,
            recipient_id=recipient_id,
            channel=self.CHANNEL,
            title=title,
            body=body,
            alert_id=alert_id,
            prescription_id=prescription_id,
            is_read=False,
            created_at=self._now(),
        )
        session.add(row)
        return row


class WechatSubscribeChannel:
    """微信订阅消息（**骨架**，spec §8.3：「原型不做真实推送（需微信订阅消息资质）」）。

    形状照 :class:`app.adapters.http_lepao.HttpLePaoAdapter`：类现在就建，方法一律
    ``raise NotImplementedError``。提前建类的理由与那一个逐字相同——把「未来要动的地方」
    圈定：资质与模板 ID 一旦到位，改动只落在本文件，``app/pipeline`` 与 ``app/api``
    完全不动（它们只认 :class:`NotificationChannel` 这个契约）。

    **未来实现时必须满足的契约**：

    * ``send`` 的签名与 :class:`InAppChannel` 逐字相同（7 个形参、6 个 keyword-only），
      且不 commit、不 flush——事务边界由调用方掌握；
    * **投递失败必须抛，不得静默返回 ``None``**：调用方靠返回值决定
      「教师点了『推送减量 20%』」要不要把 ``alert.status`` 置 ``handled``，
      一个静默失败会让界面显示成功而学生什么都没收到；
    * ⚠️ **不得沿用「三个实现跑同一组契约测试」这种说法**（``http_lepao.py`` 的
      docstring 逐字警告过同一件事）：本文件今天只有
      ``test_the_two_future_channels_raise_for_every_method`` 这一条骨架测试，
      真实实现落地时**必须补齐它自己的行为契约测试**（模板 ID 校验、openid 缺失、
      微信 API 的错误码映射、重试与幂等）；
    * 微信订阅消息是**一次性授权**（用户点一次只能发一条），故实现要自己维护
      「还有几次可发」的余额——那张表本仓今天没有，届时是一次 schema 变更
      （本仓不做迁移 = 重建库，见 :mod:`app.db.models` 的模块 docstring）；
    * ``token`` / ``appsecret`` 一类的机密**不得**进 ``__repr__``、日志或异常消息
      （照 ``HttpLePaoAdapter`` 把 token 存成 ``self._token`` 私有属性的处置）。
    """

    #: 本通道将来写进 ``notification.channel`` 的值。
    #: ⚠️ 它是 ``Notification.CHANNELS`` 里**最长**的一个（16 字符），
    #: 而那一列是 ``String(16)``、**余量 0**（模型注释里逐字写了这件事）：
    #: 换更长的通道名之前必须先抬列宽，而 SQLite 不强制长度、
    #: 故溢出在本仓的测试里永远不报错。
    CHANNEL = _vocabulary(
        "wechat_subscribe", Notification.CHANNELS, "notification.channel"
    )

    def send(
        self,
        session: Session,
        *,
        recipient_kind: str,
        recipient_id: int,
        title: str,
        body: str,
        alert_id: int | None = None,
        prescription_id: int | None = None,
    ) -> Notification:
        """微信订阅消息。⚠️ 需要资质与模板 ID，原型不实现（见类 docstring 的契约）。"""
        raise NotImplementedError("微信订阅消息需要资质与模板 ID，见本模块 docstring")


class SmsChannel:
    """短信（**骨架**，spec §8.3：「原型不做真实推送（需……短信通道）」）。

    契约与「不得沿用同一组契约测试」那条警告逐字见 :class:`WechatSubscribeChannel`。
    另有一条本通道特有的：**短信按条计费且不可撤回**，故真实实现必须自己做
    「同一个人 + 同一条预警 24 小时内只发一次」的限流——⚠️ 而
    :class:`InAppChannel` 的 docstring 逐字写了它**不做**去重（去重在调用方），
    于是这一档不能照抄站内消息的处置。
    """

    #: 本通道将来写进 ``notification.channel`` 的值。
    CHANNEL = _vocabulary("sms", Notification.CHANNELS, "notification.channel")

    def send(
        self,
        session: Session,
        *,
        recipient_kind: str,
        recipient_id: int,
        title: str,
        body: str,
        alert_id: int | None = None,
        prescription_id: int | None = None,
    ) -> Notification:
        """短信。⚠️ 需要短信通道，原型不实现（见类 docstring 的契约）。"""
        raise NotImplementedError("短信通道未接入，见本模块 docstring")
