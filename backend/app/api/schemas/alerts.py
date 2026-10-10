"""spec §4.6 的 ``alert`` / ``notification`` 与 §4.7 的班级周报：**三个资源都只读**。

| 资源路径                        | 表                      | ``writable`` | ``on_delete``        |
| =============================== | ======================= | ============ | ==================== |
| ``/api/alerts``                  | ``alert``                | ❌           | **``forbid``**（P3-B8） |
| ``/api/notifications``           | ``notification``         | ❌           | **``forbid``**（P3-B8） |
| ``/api/weekly-class-reports``    | ``weekly_class_report``  | ❌           | ``forbid``           |

⚠️ **Task 7 给本模块加了两个模型，但三个资源的 ``writable`` 一个都没动**：
``AlertHandleCreate`` / ``AlertHandleResult`` 服务的是
``POST /api/alerts/{alert_id}/handle``（一个**动作**端点，不是 CRUD 的 POST），
而 ``alerts`` 在 :data:`app.api.routers.catalog.RESOURCES` 里仍然 ``writable=False``。
这正是那个开关存在的理由（它的注释逐字写着「开放 CRUD 写它会绕过 ``window_key`` 去重，
Review Focus 第 3 条」）：**本模块的两个新模型不是给泛型工厂用的**，
故它们不出现在 ``CrudSchemas`` 里、也不改读写矩阵的任何一格。
⚠️ 于是本模块的模型数是 **5**（三个 ``*Read`` + 两个处置模型），
而 :mod:`app.api.schemas` 那个「14 + 9 × 3 = 41」的算式**不含**这两个
（它数的是 23 个资源的 CRUD 三件套，守卫
``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned`` 数的是
``RESOURCES``、不是本包的类）。

⚠️⚠️ **``alerts`` 与 ``notifications`` 的 ``on_delete`` 是 ``forbid`` 而不是 ``restrict``**
（预检更正 P3-B8，计划正文原写 ``restrict``）。理由是这两张表存的是**痕迹**：

* ``alert`` 是「哪个学生在哪一天被哪条规则标记过」的**审计记录**，是 RCT 的过程数据
  （spec §1.3 的可追溯性 + Review Focus 第 3 条的「重复触发」判据都要它）；
* ``notification`` 是**学生看到的消息历史**，红点与消息中心都读它。

``restrict`` 的含义是「没有子行时可以从 API 删掉」——而这两张表**今天都没有子行**
（实测：``_child_tables(Alert)`` 与 ``_child_tables(Notification)`` 都是空列表），
故 ``restrict`` 在这里等价于「随便删」，那会静默抹掉研究数据。
删它们的正确方式是重放（:func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删），
与 ``stratification_result`` 同一档。

⚠️ **``notification`` 刻意不带 ``batch_id``**（它是用户实时写入的，
:mod:`app.db.models.feedback` 的模块 docstring 交代了这件事），
故它**也不在**重放的清单里——即「从任何入口都删不掉一行通知」。
这是有意的：消息历史的价值就在于它不会被程序抹掉。
「已读」走 Task 8 的 ``POST /api/notifications/{id}/read``（改 ``is_read``，不删行）。

⚠️ **本模块的三张表住在 :mod:`app.db.models.feedback`，而它们的 schema 住在这里**
（计划 File Structure 的两行清单就是这么分的）。``app/db/models/`` 那侧刻意相反
（三张表住 ``feedback.py`` 而不住 ``ops.py``），理由是导入机制而不是文档结构
（Plan 03 账本 P3-A1）；本包没有那条约束，故照计划走。对照见
:mod:`app.api.schemas` 的模块 docstring。

**``JsonText`` 列**：``weekly_class_report`` **5 个**（``layer_distribution`` /
``rpe_summary`` / ``checkin_rate_by_layer`` / ``progress_board`` / ``alert_summary``）、
``alert`` 1 个（``trigger_snapshot``）、``notification`` 0 个。
**``notification`` 是全库唯一一张既无唯一约束、又无 ``JsonText`` 列、还只读的资源**，
故它的 list 与 read-one 返回同一套 10 个键。
"""
import datetime as dt

from pydantic import BaseModel, field_validator

from app.api.schemas._base import ReadModel, one_of
from app.api.schemas.prescription import WeeklyAdjustmentRead

__all__ = [
    "AlertHandleCreate",
    "AlertHandleResult",
    "AlertRead",
    "HANDLE_ACTIONS",
    "NotificationRead",
    "WeeklyClassReportRead",
]

#: ``POST /api/alerts/{id}/handle`` 的三档动作（简报 Task 7「决定」最后一条逐字）。
#:
#: ⚠️ **它是这三档的唯一所有者**：:mod:`app.api.routers.alerts` import 它、不抄第二份
#: （Global Constraint #3）。⚠️ 而它**刻意不是** DB 的词表——``alert.handled_action``
#: 是 :class:`Text`（给人看的自由文本，照 ``cleaning_log.reason`` 的既有处置），
#: 故那一列**没有** CHECK、也就没有模型类常量可对账。于是本 tuple 是它在请求侧的
#: 唯一闸门：一个词表外的动作若不拦，会静默写进 ``handled_action`` 而**什么也不做**
#: （前端点了按钮、界面显示成功、训练量一个字没变）。
#: ⚠️ 用 ``tuple`` 而不是 ``set``：``one_of`` 的报错消息里它按序打印，
#: 而三档的书写序（减量 / 忽略 / 备注）就是教师端按钮的排列序。
HANDLE_ACTIONS: tuple[str, ...] = ("reduce_20pct", "ignore", "note")


class AlertRead(ReadModel):
    """``alert`` 的 14 列，含 1 个 ``JsonText`` 列（``trigger_snapshot``）。

    ⚠️ **``student_id`` 与 ``course_section_id`` 恰好一个非空**（DB 侧有
    ``ck_alert_subject_is_exactly_one`` 强制）：spec §4.6 逐字
    「student_id（班级级预警为 course_section_id）」，故预警有两种作用域。
    前端**必须**按哪一列非空来分支渲染（学生卡片 vs 班级卡片），
    而 ``subject_key`` 是它们的归一化形态（``student:<id>`` / ``section:<id>``）——
    ⚠️ 那个前缀算式的唯一所有者是 Task 6 的 :mod:`app.domain.alerts`，
    **前端不要自己拼它**，也不要解析它，读那两个可空列即可。

    ``status`` 的三档（``pending`` / ``handled`` / ``ignored``）里，
    ``handled`` 与 ``ignored`` 让教师处置过的预警**留在库里当痕迹**而不是被删掉
    ——删掉之后「这一条为什么没有再触发」就无从回答（Review Focus 第 3 条）。
    处置走 Task 7 的 ``POST /api/alerts/{id}/handle``（它同时做「减量 20%」）。

    ``window_key`` 是去重键的一部分（``uq_alert_rule_subject_semester_window`` 四列），
    它的五种取值算式归 :mod:`app.domain.alerts`，本模块不解释它的内容。
    """

    id: int
    student_id: int | None
    course_section_id: int | None
    semester_id: int
    subject_key: str
    level: str
    rule_id: str
    trigger_snapshot: dict
    triggered_at: dt.datetime
    status: str
    handled_action: str | None
    handled_at: dt.datetime | None
    batch_id: int
    window_key: str


class NotificationRead(ReadModel):
    """``notification`` 的 10 列。

    ⚠️ **``recipient_id`` 不是外键**：它是多态的（``recipient_kind = "student"`` 时指
    ``student.id``、``"teacher"`` 时指 ``teacher.id``），而 SQLite 没有跨两张父表的
    外键写法。故前端要用 ``recipient_kind`` + ``recipient_id`` **两列一起**才能定位接收者。
    ⚠️ 代价是「删学生不会带走他的通知」，于是 ``students`` 的
    ``on_delete="restrict"`` 也看不到这一层关系（``_child_tables`` 只认外键）。

    ⚠️ ``alert_id`` 与 ``prescription_id`` 都可空，且**都带 ``ON DELETE SET NULL``**
    ——这正是 :func:`app.api.crud._child_tables` 必须跳过它们的原因（P3-B4）。
    前端应把 ``prescription_id IS NULL`` 渲染成**不可点的纯文本**：
    关联已被断开，点过去是 404。
    """

    id: int
    recipient_kind: str
    recipient_id: int
    channel: str
    title: str
    body: str
    alert_id: int | None
    prescription_id: int | None
    is_read: bool
    created_at: dt.datetime


class WeeklyClassReportRead(ReadModel):
    """``weekly_class_report`` 的 12 列，含 **5** 个 ``JsonText`` 列（全库最多的一张，
    与 ``prescription`` 并列）。

    ⚠️ **5 个聚合列的形状由 Task 8 的 ``report_stage`` 定，本模块只声明它们是 ``dict``**：
    「环比流动」要几个键、「进步榜」取前几名，都要等生成器写出来才知道
    （:class:`app.db.models.feedback.WeeklyClassReport` 的 docstring 逐字交代了
    为什么做成 5 个 JSON 列而不是标量列：本仓不做迁移，提前钉进 DDL 就等于
    为一个还没定的形状付一次重建库的代价）。
    故 Plan 04 的前端**不要**照本模块推那 5 个键——要照 Task 8 的输出。

    ``suggestion`` 是自由文本（给人看的一句话），故它是 ``str`` 而不是 JSON。
    """

    id: int
    course_section_id: int
    semester_id: int
    week: int
    layer_distribution: dict
    rpe_summary: dict
    checkin_rate_by_layer: dict
    progress_board: dict
    alert_summary: dict
    suggestion: str
    generated_at: dt.datetime
    batch_id: int


# ---------------------------------------------------------------------------
# Task 7：教师处置一条预警（本模块唯一的**写入**模型，故排在三个只读模型之后）
# ---------------------------------------------------------------------------


class AlertHandleCreate(BaseModel):
    """``POST /api/alerts/{id}/handle`` 的请求体（教师处置一条预警）。

    ⚠️ **``handled_action`` 与 ``handled_at`` 刻意不在请求体里**（简报 Task 7「决定」
    最后一条逐字：「由服务端填」）：前者是服务端按 ``action`` 落的那一格，后者是服务端
    时钟。少了这条，客户端就能把一条预警伪造成「昨天由别的动作处置过」，而
    ``alert`` 是 RCT 的**过程数据**（本模块表头那张矩阵给它定的 ``on_delete="forbid"``
    就是为这件事），一条能被客户端改写的处置痕迹等于没有痕迹。

    ⚠️ ``note`` 只在 ``action == "note"`` 时必填，故**不在这里校验**（Pydantic 的
    ``model_validator`` 能做，但那会把「哪一档要备注」这条业务口径搬进 schema，
    而它的另一半——「备注写进哪一列」——住在端点里）。校验在端点，两处相邻。
    """

    action: str
    note: str | None = None

    @field_validator("action")
    @classmethod
    def _action_in_domain(cls, value: str) -> str:
        """``action`` 必须落在 :data:`HANDLE_ACTIONS` 里（→ **422**，不是 409）。

        ⚠️ 走 :func:`one_of` 而不是自己抛：那条助手是「DB 有 CHECK 的枚举列」在请求侧的
        既有闸门（它的 docstring 逐字解释了为什么是 422：「客户端送了一个不在取值域里的
        值」是请求校验错误，回 409 会让前端把自己的输入错误当成「与别人撞了」）。
        ⚠️ 而 ``alert.handled_action`` 那一列**没有** CHECK（它是 :class:`Text`），
        故本校验是这三档唯一的闸门，理由见 :data:`HANDLE_ACTIONS`。
        """
        return one_of("action", value, HANDLE_ACTIONS)


class AlertHandleResult(BaseModel):
    """``handle`` 的响应：**处置之后的预警** + 这一次处置**真的做了**的两件副作用。

    ⚠️ **为什么要把两个副作用回给前端**（而不是只回那一行 ``alert``）：
    ``reduce_20pct`` 那一档要写一条 ``weekly_adjustment`` 并发一条站内消息，
    而**两者都可能没有发生**——调整撞上了
    ``uq_weekly_adjustment_prescription_week_reason_source``（管道在触发那天已经自动
    减过了，见 :func:`app.pipeline.alert_stage._write_auto_adjustment`）。
    只回 ``alert`` 的话，教师看到 ``status = "handled"`` 会以为量刚被减了，
    而学生端本周的训练单一个字都没变。两个 ``None`` 因此是**有信息的一档**，
    前端应把 ``adjustment is None`` 渲染成「本周已经减过量了，本次未再减」。

    ⚠️ 三个字段都复用**既有的**读模型（:class:`AlertRead` /
    :class:`~app.api.schemas.prescription.WeeklyAdjustmentRead` / :class:`NotificationRead`），
    不另造形状：同一条调整从 ``GET /api/weekly-adjustments/{id}`` 读到的与从这里读到的
    是同一个契约。

    ⚠️ **本类必须排在 :class:`NotificationRead` 之后**：Pydantic 在类体求值时就要能解析
    ``NotificationRead | None`` 这个名字，写成前向引用（``"NotificationRead | None"``）
    则要额外一次 ``model_rebuild()``。故本模块的书写序是「三个只读模型 → 处置的两个」，
    而不是「按字母序」。
    """

    alert: AlertRead
    action: str
    adjustment: WeeklyAdjustmentRead | None
    notification: NotificationRead | None
