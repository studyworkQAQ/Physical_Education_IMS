"""spec §4.6 的 ``alert`` / ``notification`` 与 §4.7 的班级周报：**三个都只读**。

| 资源路径                        | 表                      | ``writable`` | ``on_delete``        |
| =============================== | ======================= | ============ | ==================== |
| ``/api/alerts``                  | ``alert``                | ❌           | **``forbid``**（P3-B8） |
| ``/api/notifications``           | ``notification``         | ❌           | **``forbid``**（P3-B8） |
| ``/api/weekly-class-reports``    | ``weekly_class_report``  | ❌           | ``forbid``           |

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

from app.api.schemas._base import ReadModel

__all__ = ["AlertRead", "NotificationRead", "WeeklyClassReportRead"]


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
