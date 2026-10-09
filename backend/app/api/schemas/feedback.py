"""spec §4.5 反馈三源的 4 个资源：三件套 × 1 + 只读 × 3。

| 资源路径                    | 表               | ``writable`` | ``on_delete`` |
| =========================== | ================ | ============ | ============= |
| ``/api/class-sessions``      | ``class_session`` | ✅           | **``cascade``** |
| ``/api/rpe-records``         | ``rpe_record``    | ❌           | ``restrict``  |
| ``/api/training-logs``       | ``training_log``  | ❌           | ``restrict``  |
| ``/api/mini-tests``          | ``mini_test``     | ❌           | ``restrict``  |

**``class_session`` 是全库唯一用 ``on_delete="cascade"`` 的资源**（计划的显式决定）：
教师建课次、取消课次，而**课次取消则 ``rpe_record`` 无意义**（那一节课没上，
学生交的快评是无效数据）。级联由 :func:`app.api.crud._purge_where` 实现，
**子表先删**（P7-A4：``PRAGMA foreign_keys=ON`` 下先删父表当场 FK 违例）。
⚠️ 这与「``ClassSession`` **不得**进 ``_replay_cleanup``」并不矛盾——后者是
**按 ``batch_id`` 整批**删课次，会连带删掉学生刚交的快评，故
:mod:`app.db.models.feedback` 的模块 docstring 明写禁止；
而本处是**教师显式点「取消这一节课」**，那一刻连带删快评正是他要的语义。
两者的差别是「谁做的决定」，不是「删不删子行」。

**三个只读资源各有自己的特例写入口**（Task 5），故泛型 CRUD 不注册它们的 POST：

* ``rpe_record`` —— ``POST /api/rpe-records`` 要校验 ``rpe_token``（课堂口令）、
  且 ``submitted_at`` **必须服务端填**（学生端的时钟不可信，而 RPE 的时间戳是
  ``RED_RPE_SUSTAINED``「连续三次」那个判据的输入）；
* ``training_log`` —— ``late`` **必须服务端算**（spec §8.1：打卡窗口 00:00–22:00，
  22:00 后提交仍入库但 ``late = true`` 且**不计入当日完成**；
  完成率是 RCT 的关键过程指标，故这一半不能交给客户端）；
* ``mini_test`` —— ``normalized_score`` 要**班内百分位反查**，客户端算不出来
  （它要读整个教学班的行）。

⚠️ 于是 ``writable=False`` 在这里的含义是「**不走泛型工厂**」，不是「不能写」。
这也正是 :mod:`app.api.routers` 的模块 docstring 里那条「include 顺序」裁定的落点：
Task 5 的特例端点是这三个路径上**唯一**的 POST，泛型工厂根本没注册，
故两者不可能撞车。

**``JsonText`` 列**：``mini_test.item_combo`` 1 个，另三张 0 个。
"""
import datetime as dt

from pydantic import BaseModel

from app.api.schemas._base import ReadModel

__all__ = [
    "ClassSessionCreate",
    "ClassSessionRead",
    "ClassSessionUpdate",
    "MiniTestRead",
    "RpeRecordRead",
    "TrainingLogRead",
]


# ---------------------------------------------------------------------------
# class_session（7 列；唯一可写的一个，也是唯一 cascade 的一个）
# ---------------------------------------------------------------------------


class ClassSessionRead(ReadModel):
    """``class_session`` 的 7 列。

    ⚠️ ``rpe_opened`` 是「教师点没点『发起课堂快评』」（spec §8.1 的第一步），
    **不是**「有没有人提交」；``rpe_token`` 可空（没发起就没有口令）。
    两列都留是因为读侧不必互相反推：口令给学生端校验用（字符串），
    开关给教师端列表用（布尔）。
    """

    id: int
    course_section_id: int
    session_date: dt.date
    period: int
    rpe_opened: bool
    rpe_token: str | None
    batch_id: int


class ClassSessionCreate(BaseModel):
    """``class_session`` 的 6 个可写列。

    ⚠️ **``batch_id`` 是必填的**，而这一格是本资源最别扭的一处（Task 3 报告的关切）：
    那一列在 DB 侧是 NOT NULL 的外键指向 ``daily_sync_run``
    （:class:`app.db.models.feedback.ClassSession` 的那一列注释交代了它为什么存在：
    本表**有** ``batch_id`` 却**不得**进 ``_replay_cleanup``，它只用来回答
    「这一行是哪一次同步写进来的」）。而 ``daily_sync_run`` **不是 23 个资源之一**，
    故前端拿不到一份可选的批次列表。

    本模块**没有**替它发明缺省值：给一个 ``batch_id: int = 0`` 会当场
    ``FOREIGN KEY constraint failed``（父表里没有 ``id = 0`` 的行，
    这正是硬规矩 #101 与 Plan 03 Task 2 顶回 1 的那条：用哨兵值代替 NULL 之前
    必须先确认那一列不是外键），而把那一列改成可空是**改一张已结案的表**。
    于是原型口径是：教师建课次之前库里得先有一次 daily 运行
    （``POST /api/pipeline/run-daily``，Task 9），前端从
    ``GET /api/class-sessions`` 的既有行里读一个 ``batch_id`` 复用。
    """

    course_section_id: int
    session_date: dt.date
    period: int
    rpe_opened: bool = False
    rpe_token: str | None = None
    batch_id: int


class ClassSessionUpdate(BaseModel):
    """``class_session`` 的部分更新。

    ⚠️ 教师「发起课堂快评」就是 ``PATCH {"rpe_opened": true, "rpe_token": "…"}``。
    两列的一致性（``rpe_opened=False`` 时 ``rpe_token`` 应为 ``NULL``）
    **在 DB 侧没有约束**（那一列的注释明写了这件事并把它交给写入方），
    本模块也刻意不加：加一条跨列校验就等于在 API 层替
    :class:`app.db.models.feedback.ClassSession` 声明一个它自己没声明的不变量。
    已登记为 Task 3 报告的关切，Task 5 的采集端点是它的正主。
    """

    course_section_id: int | None = None
    session_date: dt.date | None = None
    period: int | None = None
    rpe_opened: bool | None = None
    rpe_token: str | None = None
    batch_id: int | None = None


# ---------------------------------------------------------------------------
# rpe_record（6 列；只读，写入走 Task 5）
# ---------------------------------------------------------------------------


class RpeRecordRead(ReadModel):
    """``rpe_record`` 的 6 列。

    ⚠️ ``rpe`` 的值域 **0–10** 的唯一所有者是 spec §8.2，落库侧由
    :attr:`app.db.models.feedback.RpeRecord.RPE_MIN` / ``RPE_MAX`` 生成的
    ``ck_rpe_record_rpe`` 强制。**本模块不写第三份**（单一所有者）：
    读模型只是 ``int``，值域校验发生在写侧（Task 5），
    而读侧读出来的一定是合法值——DB 的 CHECK 已经保证了。

    ``elapsed_seconds`` 可空：spec §8.1「指导文件要求 10 秒内完成」，
    没有这一列那句话在系统里就没有落点；而「没量到耗时」与「量到 0 秒」
    不是一回事（包约定 1：缺测就是 ``NULL``）。
    """

    id: int
    class_session_id: int
    student_id: int
    rpe: int
    submitted_at: dt.datetime
    elapsed_seconds: float | None


# ---------------------------------------------------------------------------
# training_log（10 列；只读，写入走 Task 5）
# ---------------------------------------------------------------------------


class TrainingLogRead(ReadModel):
    """``training_log`` 的 10 列。

    ⚠️ **``late`` 与 ``completed`` 是两件事，不要合并成一个三态**：
    spec §8.1 逐字「22:00 后提交仍入库但标记 ``late = true``，**不计入当日完成**」。
    于是 ``completed=true`` 且 ``late=true`` 是**合法且有含义**的一档——
    学生说他自己练了，但交得太晚，完成率不算它。
    前端要显示「练了但迟交」，请把两列一起读。

    ``duration_min`` 与 ``feeling`` 可空（没练就没有时长与感受）；
    ``feeling`` 的取值域由 ``ck_training_log_feeling`` 强制，本模块不抄第二份。
    """

    id: int
    student_id: int
    log_date: dt.date
    completed: bool
    duration_min: float | None
    feeling: str | None
    is_rest_day: bool
    late: bool
    source: str
    batch_id: int


# ---------------------------------------------------------------------------
# mini_test（10 列；只读 + 1 个 JsonText 列，写入走 Task 5 的批量端点）
# ---------------------------------------------------------------------------


class MiniTestRead(ReadModel):
    """``mini_test`` 的 10 列，含 1 个 ``JsonText`` 列（``item_combo``）。

    ⚠️ 两个测量列（``squat_30s_count`` / ``shuttle_20m_s``）**都可空**：
    spec §8.1 给了「30 秒深蹲 + 20m 折返跑」但写了「或其他」，
    选了别的组合时这两列就是 ``NULL``，而组合本身记在 ``item_combo`` 里。
    故前端**不能**假定这两列有值——要看 ``item_combo``。

    ``entered_by`` 存的是**教师工号字符串**、不是 ``teacher_id`` 外键
    （原型用 ``X-Teacher-Staff-No`` 传身份，做成外键会要求录入方先查一次 ``teacher``）。
    ⚠️ 代价是「删教师不会带走他录的小测」，故 ``teachers`` 的
    ``on_delete="restrict"`` 也挡不住那一层——已登记为关切。
    """

    id: int
    student_id: int
    semester_id: int
    week: int
    item_combo: list
    squat_30s_count: int | None
    shuttle_20m_s: float | None
    normalized_score: float | None
    tested_on: dt.date
    entered_by: str
