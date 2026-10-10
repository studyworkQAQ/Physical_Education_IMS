"""预警处置端点（Plan 03 Task 7）：``POST /api/alerts/{alert_id}/handle``。

它**不走** :func:`app.api.crud.build_crud_router`，因为它不是 CRUD：它是对一个已存在的
资源做**一次操作**，而那次操作有两件副作用（写一条 ``weekly_adjustment``、发一条站内
消息）与一道状态机（``pending → handled / ignored``）。⚠️ 这也正是 ``alerts`` 在
:data:`app.api.routers.catalog.RESOURCES` 里 ``writable=False`` 的理由：那个注释逐字写着
「开放 CRUD 写它会绕过 ``window_key`` 去重（Review Focus 第 3 条）」，
故本模块是 ``alert`` 表**唯一**的写入方（管道那一侧是
:func:`app.pipeline.alert_stage.evaluate_alerts`，它只 INSERT 新行、从不 UPDATE）。

----------------------------------------------------------------------------
三档动作（简报 Task 7「决定」最后一条逐字）
----------------------------------------------------------------------------

=================  ==================  ===========================================
``action``          处置后的 ``status``   做的事
=================  ==================  ===========================================
``reduce_20pct``    ``handled``         写 ``weekly_adjustment(source="auto",
                                        factor=0.8)`` + 推送「减量 20%」给学生
``ignore``          ``ignored``         只改状态
``note``            **仍是 ``pending``** 只记 ``handled_action``（教师写一句话，
                                        但这一条还没处置完）
=================  ==================  ===========================================

⚠️ **``handled_action`` 与 ``handled_at`` 一律由服务端填**：请求体里没有这两个字段
（:class:`~app.api.schemas.alerts.AlertHandleCreate` 只有两个键），故客户端
**结构上不可能**伪造「昨天由别的动作处置过」。而 ``alert`` 是 RCT 的过程数据
（``on_delete="forbid"`` 就是为它定的），一条能被客户端改写的处置痕迹等于没有痕迹。

----------------------------------------------------------------------------
⚠️⚠️ ``reduce_20pct`` 的 ``source`` 是 ``"auto"``、不是 ``"teacher"``
----------------------------------------------------------------------------

这是本端点最容易被改错的一格，理由是一条具体的失效：管道在**触发那天**就已经自动写过
一条 ``source="auto"`` / ``reason=<rule_id>`` 的调整了（spec §8.4「预警触发减量 20%」，
:func:`app.pipeline.alert_stage._write_auto_adjustment`）。教师后来点「减量 20%」
是**同一次调整**的第二个触发点，不是第二次调整。

若这里写 ``source="teacher"``，那条四列唯一约束
（``uq_weekly_adjustment_prescription_week_reason_source``）就**拦不住它**——
``source`` 是键的一列，两个不同的值等于两个不同的键，于是同一周上会有
``0.8 × 0.8``，而「本周训练单」是该周全部 factor 的**累乘**
（:func:`~app.domain.prescription.weekly.weekly_training_sheet`）：学生端看到量被减了 36%，
而教师只点了一次「减量 20%」。**Review Focus 第 3 条要防的连乘会从教师端回来。**

写成 ``"auto"`` 之后，撞键 → :func:`_write_auto_adjustment` 的 SAVEPOINT 收到
``IntegrityError`` → 返回 ``False`` → 响应里 ``adjustment is None``，
前端应渲染成「本周已经减过量了，本次未再减」。⚠️ 于是 ``None`` 是**有信息的一档**，
不是失败（HTTP 仍是 200、``status`` 仍是 ``handled``）：教师那一次点击**有效的部分**是
「这条预警我看过了、并且推了消息给学生」。

⚠️ 代价（硬规矩 #39）：``weekly_adjustment.source`` 于是**回答不了**「这一条是管道自动
写的还是教师点的」。要区分请读 ``alert.handled_action`` 与 ``alert.handled_at``
（两行是同一次触发的两半，``reason`` 就是同一条 ``rule_id``）。
本 Task 认为这个代价小于连乘：值域 ``{auto, teacher}`` 里的 ``"teacher"`` 仍然有写入方
（:mod:`app.api.routers.prescription` 那一侧的教师覆盖走的是 ``teacher_overrides`` 列，
而 ``weekly-adjustments`` 资源在 CRUD 目录里是 ``writable=False``，故今天 ``"teacher"``
这个值**仍然没有生产写入方**——如实记录，它进 ``SOURCES`` 的理由与 ``"auto"`` 当初一样：
届时往一个已结案的 CHECK 里加值等于重建库）。

----------------------------------------------------------------------------
重复处置 → 409
----------------------------------------------------------------------------

⚠️ **一条规则、三档通用**：``status != "pending"`` 就 **409**
:data:`ALERT_NOT_PENDING`。已经 ``handled`` 的不能再 ``reduce_20pct``（否则又乘一次
0.8，理由同上），已经 ``ignored`` 的也不能——教师改主意了应当去开一条新的预警
（下一轮求值会按 ``window_key`` 落新行），而不是把一条已经处置过的痕迹翻回去。
⚠️ ``note`` 那一档**处置后仍是 ``pending``**，故可以连着记多条备注
（后一条覆盖 ``handled_action``）。那是有意的：备注不是处置。
"""
import datetime as dt

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy import select
from sqlalchemy.orm import Session

# ⚠️ 复用 Task 3 那个私有的 404 助手（与 Task 4 / Task 5 同一条处置）：
#    「主键查无此行」这件事在全仓只应该有一种说法。
from app.api.crud import _get_or_404
from app.api.deps import (
    TEACHER_STAFF_NO_SCHEME,
    current_teacher,
    get_db,
    require_teacher,
)
from app.api.errors import error_response

# ⚠️ 复用 Task 4 那两个私有的 api 层助手，**不写第二份**：
#    ``_current_prescription`` 是「哪一张处方在那一天生效」的唯一所有者
#    （完成率端点与学生端「本周训练单」也读它），``_business_day`` 是「今天是什么日子」
#    在 api 层的唯一所有者。抄第二份的后果是同一屏上两个数互相矛盾。
from app.api.routers.prescription import _business_day, _current_prescription
from app.api.schemas.alerts import AlertHandleCreate, AlertHandleResult
from app.db.models.feedback import Alert
from app.db.models.prescription import WeeklyAdjustment
from app.domain.alerts import RuleId
from app.domain.prescription.weekly import current_week
from app.notify import RECIPIENT_STUDENT, InAppChannel

# ⚠️ 三样东西一律从 pipeline 层 import（``api → pipeline`` 是许可方向），不抄第二份：
#    * 三个状态串的所有者是 :mod:`app.pipeline.alert_stage`（它由一条测试与
#      ``Alert.STATUSES`` 对账）；
#    * ``AUTO_REDUCTION_FACTOR`` / ``AUTO_SOURCE`` 同理，而 ``_write_auto_adjustment``
#      是「一条 auto 调整怎么写」的唯一所有者（含 WeeklyFactor 那道写入侧校验与
#      撞键时的 SAVEPOINT 处置）——在 router 里重写一遍就等于把那道校验漏掉一次。
#    * ``_now_local`` 是「现在几点」在 **api 层**的唯一住址（:mod:`app.api.routers.feedback`
#      的模块 docstring 有一节专门讲它），本模块 import 它、不写第三份时钟。
from app.api.routers.feedback import _now_local
from app.pipeline.alert_stage import (
    ALERT_HANDLED,
    ALERT_IGNORED,
    ALERT_PENDING,
    AUTO_REDUCTION_FACTOR,
    AUTO_SOURCE,
    _write_auto_adjustment,
)

__all__ = [
    "ACTION_IGNORE",
    "ACTION_NOTE",
    "ACTION_REDUCE",
    "ALERT_NOT_PENDING",
    "router",
]

#: 三档动作的名字。⚠️ **值域的所有者是**
#: :data:`app.api.schemas.alerts.HANDLE_ACTIONS`（请求侧的唯一闸门，
#: 由 ``AlertHandleCreate`` 的 ``field_validator`` 强制）；本三个常量只回答
#: 「端点里哪一支做哪一件事」，故它们各自必须是那一份的成员——守卫是
#: ``tests/api/test_alerts_api.py::test_the_three_action_constants_are_the_schema_vocabulary``
#: （按**集合相等**断言，于是加第四档而忘了接进端点会当场红）。
ACTION_REDUCE = "reduce_20pct"
ACTION_IGNORE = "ignore"
ACTION_NOTE = "note"

#: 「这条预警已经被处置过了」的 ``code``（409）。
#:
#: ⚠️ 用 **409** 不用 422：请求体本身没有错（``action`` 在词表里、``note`` 也合法），
#: 错的是**资源的状态**——与 :data:`app.api.routers.feedback.CODE_RPE_NOT_OPENED`
#: 同一条口径（那里的注释逐字写了「给两个码是为了让前端能区分『你填错了』与
#: 『老师还没发起』」）。这里同理：前端要能说「这条已经被处理过了」，
#: 而不是「你的请求有问题」。
ALERT_NOT_PENDING = "alert_not_pending"

router = APIRouter()


@router.post(
    "/api/alerts/{alert_id}/handle",
    tags=["alerts"],
    response_model=AlertHandleResult,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def handle_alert(
    alert_id: int,
    payload: AlertHandleCreate,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    as_of: dt.date | None = Query(
        default=None,
        description="减量落在哪一天所属的处方周（YYYY-MM-DD）。缺省 = 服务端当天。",
    ),
) -> object:
    """教师处置一条预警（spec §8.2 的「教师端弹『降量建议』→ 教师点击 → 推送『减量 20%』」）。

    ⚠️ **回 200 不回 201、不带 ``Location``**：这是对已存在的资源做了一次**操作**，
    没有新资源可以指（与 Task 4 的两个 POST、Task 5 的 ``open-rpe`` 同一条约定）。
    ⚠️ 编一个 ``…/handle/0`` 出来会更糟：前端会以为「处置记录」是一张可以单独
    GET/PATCH 的资源，而它**不是**——它就是 ``alert`` 那一行上的三列
    （``status`` / ``handled_action`` / ``handled_at``）。

    **``as_of`` 只影响 ``reduce_20pct`` 那一档**（它决定减量落在哪一个处方周）；
    ``ignore`` 与 ``note`` 不读它。⚠️ 缺省取服务端当天由 :func:`_business_day` 单点持有，
    代价与对策逐字见 :mod:`app.api.routers.prescription` 的模块 docstring
    （「测试一律显式传 ``as_of``」）。

    四档失败，各有一个不同的码：

    * **404** —— 查无这条预警（:func:`_get_or_404`）；
    * **409** :data:`ALERT_NOT_PENDING` —— 已经处置过了（见模块 docstring）；
    * **422** —— ``action`` 不在词表里（schema 的 ``field_validator``）、
      ``action == "note"`` 而备注为空、班级级预警点了 ``reduce_20pct``、
      或那个学生当天没有可减量的处方（三档各是一条 ``ValueError``，
      经 :mod:`app.api.errors` 折成统一形状）；
    * **403** —— 工号不在册（:func:`app.api.deps.require_teacher`）。
    """
    require_teacher(session, staff_no)
    row = _get_or_404(session, Alert, alert_id)
    if row.status != ALERT_PENDING:
        return error_response(
            409,
            ALERT_NOT_PENDING,
            f"预警 {alert_id} 的 status 已经是 {row.status!r} 而不是 {ALERT_PENDING!r}，"
            f"故不能再处置一次。⚠️ 这一档挡的是「减量 20%」被点两次："
            f"本周训练单是该周全部 factor 的**累乘**，再点一次就是 0.8 × 0.8 = 0.64，"
            f"而教师只以为自己减了一次（Review Focus 第 3 条）。"
            f"教师改了主意的正确处置是等下一轮求值按 window_key 落一条新预警，"
            f"而不是把一条已经处置过的痕迹翻回去",
        )

    action = payload.action
    note = (payload.note or "").strip()
    if action == ACTION_NOTE and not note:
        raise ValueError(
            f"action = {ACTION_NOTE!r} 时 note 必填且不得为空白："
            f"这一档**只**记 handled_action 一列（status 保持 pending），"
            f"一句空备注等于什么都没记，而 alert 是 RCT 的过程数据"
        )

    day = _business_day(as_of)
    adjustment = None
    notification = None

    if action == ACTION_REDUCE:
        if row.student_id is None:
            # 班级级预警的主语是一个教学班（spec §4.6 逐字「student_id（班级级预警为
            # course_section_id）」），而 weekly_adjustment 挂在**一张处方**上——
            # 一个班没有一张共用的处方，故「给这个班减量 20%」在数据模型里无从落地。
            raise ValueError(
                f"预警 {alert_id} 是**班级级**的（course_section_id="
                f"{row.course_section_id}、student_id 为 NULL），故无法对它执行 "
                f"{ACTION_REDUCE!r}：weekly_adjustment 挂在**一张处方**上，"
                f"而一个教学班没有一张共用的处方（spec §8.4 的减量是逐人的）。"
                f"班级级的 YELLOW_CLASS_RPE_HIGH 的正确处置是教师自己调整下一节课的强度，"
                f"或者对班上具体某个学生的那一条预警点减量"
            )
        prescription = _current_prescription(session, row.student_id, day)
        if prescription is None:
            raise ValueError(
                f"学生 {row.student_id} 在 {day.isoformat()} 没有生效的处方，"
                f"故无处可减：weekly_adjustment.prescription_id 是 NOT NULL 外键。"
                f"这一档通常意味着该换处方了（spec §5.2 触发 3），"
                f"而不是「这个学生不该减量」——请先重生成处方，再回来处置这条预警"
            )
        week = current_week(
            prescription.generated_on, day, prescription.microcycle_weeks
        )
        if week is None:
            # ⚠️ **可达路径只有一条**（硬规矩 #39，与 :data:`app.api.routers.prescription.OUTSIDE_MICROCYCLE`
            #    那一格的实测结论逐字相同）：``valid_to`` 是 nullable 的，而
            #    :func:`_current_prescription` 把 NULL 当「不设终点」放行，于是一张
            #    ``valid_to IS NULL`` 且 ``generated_on`` 在很久以前的行会被选中，
            #    而 ``current_week`` 对它返回 ``None``。
            #    ⚠️ 反过来，一张 ``valid_to`` **有值**且已过期的处方**到不了这里**——
            #    它在上面那一步就被 ``_current_prescription`` 滤掉了，报的是
            #    「没有生效的处方」那一档。两档的消息因此不同，而它们指的是同一件事的
            #    两个入口，故都点名 spec §5.2 触发 3。
            raise ValueError(
                f"学生 {row.student_id} 的处方（{prescription.generated_on.isoformat()} "
                f"生成、{prescription.microcycle_weeks} 周微周期）在 "
                f"{day.isoformat()} 不在有效期内：current_week 返回 None。"
                f"给一张已到期的处方写「本周减量」没有意义（口径与管道那一侧逐字相同，"
                f"见 app.pipeline.alert_stage._write_auto_adjustment）"
            )
        # ⚠️ 走 pipeline 那**一个**所有者：它内部先构造 WeeklyFactor 值对象
        #    （factor ∈ (0, 2] 的写入侧唯一闸门，那一列刻意没有 DB CHECK），
        #    再用裸 INSERT + 自己的 SAVEPOINT 让 DB 当去重的裁判。
        # ⚠️ batch_id 取**处方自己的**那一个：教师手工发起的写入没有自己的批次，
        #    口径逐字见 WeeklyAdjustment.batch_id 的列注释（与 Task 4 的 regenerate 同一条）。
        written = _write_auto_adjustment(
            session,
            prescription=prescription,
            week=week,
            rule_id=RuleId(row.rule_id),
            batch_id=prescription.batch_id,
            created_at=_now_local(),
        )
        if written:
            adjustment = session.scalar(
                select(WeeklyAdjustment).where(
                    WeeklyAdjustment.prescription_id == prescription.id,
                    WeeklyAdjustment.week == week,
                    WeeklyAdjustment.reason == row.rule_id,
                    WeeklyAdjustment.source == AUTO_SOURCE,
                )
            )
        row.status = ALERT_HANDLED
        row.handled_action = f"{action}: {note}" if note else action
        row.handled_at = _now_local()
        # ⚠️ **推送发生在教师点击之后**（spec §8.2 逐字「教师端弹『降量建议』→ 教师点击 →
        #    推送『减量 20%』」）：管道触发那天**刻意不推**（理由见
        #    app.pipeline.alert_stage._notify 的 docstring），故这一条消息是本端点独有的。
        # ⚠️ 它**不管调整有没有新写**都发：教师点了「减量 20%」，学生就该被告知
        #    「本周的量减了 20%」——哪怕那一条调整是管道几天前就写好的。
        notification = InAppChannel(now=_now_local).send(
            session,
            recipient_kind=RECIPIENT_STUDENT,
            recipient_id=row.student_id,
            title="本周训练量已减 20%",
            body=(
                f"老师看过你的预警（{row.rule_id}）之后，把本周的训练量减了 "
                f"{int(round((1.0 - AUTO_REDUCTION_FACTOR) * 100))}%。"
                f"打开「本周训练单」看到的就是调整之后的量。"
                + (f"老师留言：{note}" if note else "")
            ),
            alert_id=row.id,
            prescription_id=prescription.id,
        )
    elif action == ACTION_IGNORE:
        row.status = ALERT_IGNORED
        row.handled_action = f"{action}: {note}" if note else action
        row.handled_at = _now_local()
    else:
        # ⚠️ **status 保持 pending**（简报 Task 7「决定」最后一条逐字）：
        #    备注不是处置。于是 handled_at 也**不写**——那一列的名字是「处理时间」，
        #    给一条仍然 pending 的预警填上它，前端就会显示「已处理于 …」而状态是待处理。
        row.handled_action = note

    session.commit()
    session.refresh(row)
    return {
        "alert": row,
        "action": action,
        "adjustment": adjustment,
        "notification": notification,
    }
