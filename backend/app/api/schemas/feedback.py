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

from pydantic import BaseModel, Field, field_validator

from app.api.schemas._base import ReadModel, one_of

# ⚠️ 引模型类常量而**不在本模块抄第二份词表/值域**（单一所有者）：``rpe`` 的 0–10 归
# ``RpeRecord.RPE_MIN`` / ``RPE_MAX``，``feeling`` 的三个值归 ``TrainingLog.FEELINGS``。
# 两处各写一遍迟早漂移，而漂移是静默的（Pydantic 放行的值 DB 的 CHECK 拒收 → 409，
# 或反过来）。走子模块路径（Ruling 97：这两个类**不在** app.db.models 的公有导入面上）。
from app.db.models.feedback import RpeRecord, TrainingLog

__all__ = [
    "ClassSessionCreate",
    "ClassSessionRead",
    "ClassSessionUpdate",
    "CompletionRateRead",
    "MiniTestBatchFailure",
    "MiniTestBatchResult",
    "MiniTestEntryCreate",
    "MiniTestRead",
    "NormalizedEntryRead",
    "NormalizedScoreRead",
    "NormalizedSectionRead",
    "RpeOpenResult",
    "RpeRecordRead",
    "RpeStatusRead",
    "RpeSubmitCreate",
    "RpeSubmissionRead",
    "TrainingLogCreate",
    "TrainingLogRead",
    "UnassignedEntryRead",
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
    #: ⚠️ **可空**（Plan 03 Task 5 的 P5-A1）：教师在前端实时建的课次没有批次可指，
    #: 那一行落 ``NULL``。改可空之前本字段是 ``int``，于是一条 ``NULL`` 会让
    #: ``response_model`` 校验失败 → **500**，而 500 会把「这一行是教师实时建的」
    #: 这件事伪装成服务器故障（前端只会显示「服务出错」）。
    batch_id: int | None


class ClassSessionCreate(BaseModel):
    """``class_session`` 的 6 个可写列。

    ⚠️ **``batch_id`` 自 Plan 03 Task 5 起是可选的**（P5-A1）。本模型在 Task 3 结案时
    那一段写的是「``batch_id`` 是必填的，而这一格是本资源最别扭的一处」，并给了一个
    原型口径：「教师建课次之前库里得先有一次 daily 运行
    （``POST /api/pipeline/run-daily``，Task 9），前端从 ``GET /api/class-sessions``
    的既有行里读一个 ``batch_id`` 复用」。**那个别扭现在没有了**，整段按实际改写：

    那一列在 DB 侧改成了**可空**的外键（:class:`app.db.models.feedback.ClassSession`
    的那一列注释交代了理由：本表有**两个**写入来源，管道整批写的那种带 ``batch_id``，
    教师实时建的那种没有批次可指，而 ``NOT NULL`` 只容得一个）。于是：

    * **教师在前端建课次 → 不传 ``batch_id``**（落 ``NULL``）。这是本资源的正常用法，
      不再要求库里先有一次 daily 运行；
    * **要标出「这一行是哪一次同步写进来的」时才传**（管道/演示生成器那一种）。

    ⚠️ ``NULL`` 还有一个**承重的**副作用：:func:`app.db.repo.delete_by_batch` 是
    ``WHERE batch_id = :b``，而 SQL 里 ``NULL = 任何值`` 都不成立，故教师实时建的课次
    **天然躲过重放**——那正是我们要的（重放不该删掉教师手工排的课）。
    ⚠️ 本模型**仍然没有**替它发明缺省值：``batch_id: int = 0`` 会当场
    ``FOREIGN KEY constraint failed``（父表里没有 ``id = 0`` 的行，硬规矩 #101：
    用哨兵值代替 NULL 之前必须先确认那一列不是外键）。缺省是 ``None``，即真 ``NULL``。
    """

    course_section_id: int
    session_date: dt.date
    period: int
    rpe_opened: bool = False
    rpe_token: str | None = None
    batch_id: int | None = None


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
# training_log（11 列；只读，写入走 Task 5 的 POST /api/training-logs）
# ---------------------------------------------------------------------------


class TrainingLogRead(ReadModel):
    """``training_log`` 的 **11** 列（Plan 03 Task 5 加了 ``submitted_at``，此前是 10）。

    ⚠️ **``late`` 与 ``completed`` 是两件事，不要合并成一个三态**：
    spec §8.1 逐字「22:00 后提交仍入库但标记 ``late = true``，**不计入当日完成**」。
    于是 ``completed=true`` 且 ``late=true`` 是**合法且有含义**的一档——
    学生说他自己练了，但交得太晚，完成率不算它。
    前端要显示「练了但迟交」，请把两列一起读。

    ⚠️ **``submitted_at`` 与 ``log_date`` 一起读才知道这一行是不是「补卡」**：
    ``log_date`` 是学生**在补哪一天**，``submitted_at`` 是他**什么时候交的**
    （服务端时钟，naive 本地时间，时区 = :data:`app.config.TIMEZONE`）。
    两者的日期不一致 = 事后补打，而**补卡不计入完成率**
    （:mod:`app.api.routers.feedback` 的完成率端点按这条口径过滤）。
    ⚠️ 注意 ``late`` **只**看 ``submitted_at`` 的**时刻**（> 22:00），不看日期是否错位：
    一个 21:00 补打前天卡的学生 ``late=false``，但他那一行仍然不计入完成率——
    两件事各由一列承载，前端不要拿 ``late`` 当「补卡」用。

    ``duration_min`` 与 ``feeling`` 可空（没练就没有时长与感受）；
    ``feeling`` 的取值域由 ``ck_training_log_feeling`` 强制、``source`` 的由
    ``ck_training_log_source`` 强制（P5-A3 新增），本模块都不抄第二份。
    """

    id: int
    student_id: int
    log_date: dt.date
    submitted_at: dt.datetime
    completed: bool
    duration_min: float | None
    feeling: str | None
    is_rest_day: bool
    late: bool
    source: str
    #: ⚠️ **可空**（P5-A1）：学生在 H5 上实时打的那一行没有批次可指，落 ``NULL``；
    #: 管道同步来的那一批带着 ``daily_sync_run.id``。改可空之前本字段是 ``int``，
    #: 于是学生打的**每一条**卡都会让 ``response_model`` 校验失败 → **500**。
    batch_id: int | None


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


# ===========================================================================
# Plan 03 Task 5：spec §8.1 三源采集的**特例**模型
#
# ⚠️ 上面那 6 个是 Task 3 的泛型 CRUD 用的（``*Read`` / ``*Create`` / ``*Update``），
# 本段这 13 个是七个特例端点用的。⚠️ **两段刻意不合并**：泛型那一份的形状由
# ``tests/api/test_crud.py::test_read_models_match_the_db_columns`` 按「与 DB 列逐字
# 对齐」钉住，而特例这一份的形状由**业务语义**定（例如 ``RpeStatusRead`` 里的
# ``not_submitted`` 在任何一张表里都没有对应的列）。把它们混在一起会让那条
# 「与列对齐」的守卫不得不为特例模型开例外。
# ===========================================================================


class RpeOpenResult(BaseModel):
    """``POST /api/class-sessions/{id}/open-rpe`` 的响应（教师发起课堂快评）。

    ⚠️ ``already_open`` 那一格是**幂等**的载体：教师手抖点两次时第二次不换口令
    （换掉的话第一个学生已经抄在纸上的那串会当场失效，而他看到的是「口令错误」），
    前端靠这一格决定要不要重新投屏。
    """

    class_session_id: int
    rpe_opened: bool
    rpe_token: str
    already_open: bool


class RpeSubmitCreate(BaseModel):
    """学生提交课堂快评的请求体（**4** 个字段）。

    ⚠️ **``student_id`` 与 ``submitted_at`` 刻意不在本模型上**（服务端分别取
    ``X-Student-Id`` 与自己的时钟）：学生端的时钟不可信（它可以被改），而 RPE 的
    时间戳是 ``RED_RPE_SUSTAINED``「连续三次」那个判据的输入；``student_id`` 若可传
    就等于让学生 A 替学生 B 交一份。与 Task 4 的 :class:`OverrideCreate`
    少两个字段是同一条纪律。
    ⚠️ 于是**多传这两个键不报错、但会被忽略**（Pydantic 缺省 ``extra="ignore"``）。
    守卫是 ``test_the_request_models_cannot_carry_the_server_filled_fields``
    ——它钉的是「字段不在模型上」，因为那才是「服务端那一份不可能被覆盖」的保证。

    ⚠️ ``rpe`` 的上下界**引** :attr:`RpeRecord.RPE_MIN` / ``RPE_MAX``（不写第二份 0 与 10），
    故域外值由 Pydantic 折成 **422**，而不是等 DB 的 ``ck_rpe_record_rpe`` 给 **409**。

    ⚠️ ``elapsed_seconds`` **可为 ``null``** 且 ``> 60`` **不拒绝**：spec §8.1 明写
    「**已知局限：无法防代填**」，故后端不能拿耗时当准入门槛——一个真花了 90 秒填的
    学生不该被拒。那一档由 ``rpe-status`` 的 ``suspected_proxy_count`` 报给教师，
    由**人**去判断。``ge=0`` 仍要：一个负的耗时是前端算错了（打开页面的时刻晚于提交时刻）。
    """

    class_session_id: int
    rpe: int = Field(ge=RpeRecord.RPE_MIN, le=RpeRecord.RPE_MAX)
    elapsed_seconds: float | None = Field(default=None, ge=0)
    rpe_token: str


class RpeSubmissionRead(BaseModel):
    """``rpe-status`` 的「已交名单」里的一行（**不是** ``rpe_record`` 的整行）。

    ⚠️ 刻意不带 ``id`` / ``class_session_id``：教师端要的是「谁交了、交了什么、
    花了多久」，而课次 id 在响应的上一层已经有了（重复它会让前端有机会把两个
    不同层级的值搞混）。要整行走 ``GET /api/rpe-records/{id}``（Task 3 的泛型 read）。
    """

    student_id: int
    rpe: int
    elapsed_seconds: float | None
    submitted_at: dt.datetime


class RpeStatusRead(BaseModel):
    """``GET /api/class-sessions/{id}/rpe-status`` 的响应（spec §8.1：
    「教师端实时显示已提交/未提交名单，可现场催交」）。

    ⚠️ **``enrolled_count`` 与 ``len(submitted)`` 可以不一致、且两个方向都可能**：
    名单的分母是**选课人数**（``enrollment`` 表），分子是**实际提交数**。
    一个选了课没交的人进 ``not_submitted``；一个没选课却交上来的人（旁听、
    或选课后被退选）进 ``submitted`` 但**不**进 ``not_submitted``。
    教师端要看到的正是这个差，故两个数都单独给、不让前端去减。

    ⚠️ ``mean_rpe`` / ``median_elapsed_seconds`` 在**没人交**时是 ``null`` 而不是 ``0``
    （「不知道」不得讲成「0」，P5-A2 的同一条纪律）：一个 ``0`` 会被读成
    「这节课全班 RPE 0」，而那是一句关于这节课的假话。
    ``median_elapsed_seconds`` 只在**量到耗时**的那些行上取中位数
    （``null`` 的行不参与，否则排序当场 ``TypeError``）；全都为 ``null`` 时它也是 ``null``。

    ⚠️ ``suspected_proxy_count`` 是 ``elapsed_seconds > 60`` 的行数——「疑似代填」的信号，
    **不是**判定（spec §8.1 明写无法防代填）。门槛的住址是
    :data:`app.api.routers.feedback.PROXY_FILL_SECONDS`。
    """

    class_session_id: int
    course_section_id: int
    session_date: dt.date
    period: int
    rpe_opened: bool
    enrolled_count: int
    submitted: list[RpeSubmissionRead]
    not_submitted: list[int]
    mean_rpe: float | None
    median_elapsed_seconds: float | None
    suspected_proxy_count: int


class TrainingLogCreate(BaseModel):
    """学生每日打卡的请求体（**5** 个字段）。

    ⚠️ **``student_id`` / ``submitted_at`` / ``late`` / ``source`` / ``batch_id``
    五个一律由服务端填**，故都不在本模型上：

    * ``late`` —— spec §8.1 的打卡窗口判定（``[00:00, 22:00]`` 闭区间）。
      完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」，故这一半**不能**
      交给客户端：让客户端传 ``late`` 等于让每个学生自己决定他今天算不算完成；
    * ``submitted_at`` —— 服务端的时钟（时区 = :data:`app.config.TIMEZONE`）。
      它同时是「补卡」的判据（与 ``log_date`` 的日期不一致 ⇒ 补卡 ⇒ 不计入完成率）；
    * ``source`` —— 恒为 :data:`app.api.routers.feedback.CHECKIN_SOURCE`；
    * ``batch_id`` —— 恒为 ``NULL``（P5-A1：学生实时打的卡不属于任何批次，
      而 ``NULL`` 让它天然躲过 ``delete_by_batch``）。

    ⚠️ ``feeling`` 的值域**引** :attr:`TrainingLog.FEELINGS` 并经
    :func:`app.api.schemas._base.one_of` 校验 → 域外值是 **422** 而不是 DB CHECK 的
    **409**（那个助手的 docstring 逐字给了理由：前端填错一个下拉框不该被报成
    「与别人撞了」）。``None`` 放行（没练就没有感受，包约定 1）。

    ⚠️ ``is_rest_day`` 缺省 ``False``：spec §8.1 的折中方案是「非训练日一键『今日休息』」，
    即**默认不是**休息日，那一个键是显式动作。
    """

    log_date: dt.date
    completed: bool
    duration_min: float | None = Field(default=None, ge=0)
    feeling: str | None = None
    is_rest_day: bool = False

    @field_validator("feeling")
    @classmethod
    def _feeling_in_domain(cls, value: str | None) -> str | None:
        return one_of("feeling", value, TrainingLog.FEELINGS)


class CompletionRateRead(BaseModel):
    """``GET /api/students/{id}/training-logs/completion-rate`` 的响应。

    ⚠️ **分子与分母都单独给**，而不是只给一个百分比：完成率是 RCT 的关键过程指标，
    而一个裸的 ``0.5`` 无法回答「是 1/2 还是 15/30」——前者是一个刚被教师减到
    2 天的学生、后者是一个整周都在练的学生，两者的解读完全不同。
    ``expected_days`` / ``completed_days`` 因此也给全（前端要能在日历上点亮它们）。

    ⚠️ **``completion_rate`` 为 ``null`` 的三档**（P5-A2 的裁定：「不知道」不得讲成「0%」）：
    ① 这一周里没有任何一天有生效处方；② 有处方但 ``current_week`` 对它返回 ``None``
    （已到期，该换处方了）；③ 有处方、周次也算得出来，但**训练日与所查那一周
    一天都不重叠**。三档的 ``reason`` 各不相同，前端据此给三种提示。
    ⚠️ ``round`` 到 **4** 位（:data:`app.api.routers.feedback.RATE_PRECISION`）：
    ``1/3`` 在 JSON 里会是 ``0.3333333333333333``，而前端要显示的是「33.3%」。
    **裸值不丢**——``numerator`` / ``denominator`` 就在旁边，故这次 round 不是
    Plan 02 P5-A6 批评的那一种（那一种是「round 之后没有裸值可对账」）。

    ⚠️ ``paused`` 透出来而**不**影响 ``completion_rate``（P8-A3：「暂停」与
    「本周量为 0」是两件不同的事，:func:`weekly_training_sheet` 对 ``paused`` 只抄不判）。
    在前端把 ``paused=true`` 渲染成「本周暂停」是它自己的决定。
    """

    student_id: int
    semester_id: int
    week: int
    completion_rate: float | None
    numerator: int
    denominator: int
    expected_days: list[dt.date]
    completed_days: list[dt.date]
    prescription_id: int | None
    prescription_week: int | None
    paused: bool
    reason: str | None


class MiniTestEntryCreate(BaseModel):
    """教师批量录入二次小测时**一行**的请求体（请求体是它的一个列表）。

    ⚠️ **``entered_by`` 与 ``normalized_score`` 刻意不在本模型上**：
    前者取 ``X-Teacher-Staff-No``（让客户端传等于让它能冒充别的教师，而这一列是
    「谁录的这一行」的唯一痕迹）；后者由**读侧**现算
    （``GET /api/mini-tests/normalized``），录入时留 ``NULL``——⚠️ 因为「班内百分位反查」
    要读整个教学班的行，而教师是**一次提交一批**的：录到第 3 行时第 4..40 行还没进来，
    那一刻算出来的百分位**必然是错的**。让它留在 ``NULL`` 比写一个错的值诚实
    （包约定 1：缺测就是 ``NULL``）。

    ⚠️ ``squat_30s_count`` / ``shuttle_20m_s`` **都可空**：spec §8.1 给的是
    「30 秒深蹲 + 20m 折返跑」但写了「**或其他**」，选了别的组合时这两列就是 ``NULL``，
    而组合本身记在 ``item_combo`` 里（:class:`MiniTestRead` 的 docstring 逐字交代了
    「前端不能假定这两列有值」）。
    """

    student_id: int
    semester_id: int
    week: int = Field(ge=1)
    item_combo: list
    squat_30s_count: int | None = Field(default=None, ge=0)
    shuttle_20m_s: float | None = Field(default=None, gt=0)
    tested_on: dt.date


class MiniTestBatchFailure(BaseModel):
    """批量录入里**失败的那一条**：位置 + 是谁 + 为什么。

    ⚠️ ``index`` 是它在**请求体列表里的位置**（0-based），不是 ``mini_test.id``
    ——失败的那一行根本没有 id。教师端拿 ``index`` 回去高亮表格里的那一行，
    这正是 spec §8.1「按教学班列出学生逐个填」那个界面需要的。
    """

    index: int
    student_id: int
    message: str


class MiniTestBatchResult(BaseModel):
    """``POST /api/mini-tests/batch`` 的响应。**HTTP 状态恒为 200**（含部分失败）。

    ⚠️ 派单逐字要求的是「``207``-风格的 ``{"created": n, "failed": [...]}``，
    HTTP 状态仍是 ``200``」。不用真的 ``207 Multi-Status``：那是 WebDAV 的码，
    前端的 fetch 封装普遍把非 2xx 当错误分支，而「39 行成功 1 行重复」
    **不是**一次失败的请求。
    ⚠️ 也不用「全有或全无」：一行重复就让整批回滚的话，教师得自己找出是哪一行、
    删掉、再提交一次——而 ``failed`` 列表本来就能告诉他。
    逐条独立靠 ``SAVEPOINT``（``session.begin_nested()``）实现。
    """

    created: int
    failed: list[MiniTestBatchFailure]


class NormalizedEntryRead(BaseModel):
    """一个学生的一次小测在**班内**的标准化得分（spec §8.1 的算式）。

    三格的关系：``composite`` = ``squat_score`` 与 ``shuttle_score`` 的**等权平均**，
    ⚠️ **任一项为 ``null`` 则 ``composite`` 也是 ``null``**（不是把 ``null`` 当 0——
    那会让这个学生的综合分变成「另一项的一半」，是一句关于他的假话）。

    ⚠️ **量纲是混的**（``squat_score`` 是**次数**、``shuttle_score`` 是 **0–100 的百分位**），
    如实记录：spec §8.1 逐字要求「深蹲得分 = 次数（直接用）」，故本端点照它算、
    **不**擅自把深蹲也转成百分位（那是改 spec 的算法、是专家的活）。
    ⚠️ 它唯一的消费者 ``RED_MINITEST_DROP``（「连续两次下降 ≥ 5%」）对量纲**不敏感**：
    两次小测用同一个算式，比值就有意义。故混合量纲损害的是「综合分的**绝对值**
    可解释性」，不是预警规则的正确性。已登记为关切。
    """

    student_id: int
    mini_test_id: int
    squat_score: float | None
    shuttle_score: float | None
    composite: float | None


class NormalizedSectionRead(BaseModel):
    """一个教学班的标准化得分（``entries`` 按 ``student_id`` 升序）。

    ⚠️ ``scored_count`` = **进了百分位样本的人数**（= 班内有折返成绩的小测行数），
    不是 ``len(entries)``：选了别的测试项组合（``shuttle_20m_s IS NULL``）的学生
    在 ``entries`` 里、但**不进**样本（否则一个「没测」的人会被当成「最慢的那个」，
    把全班的百分位一起往下拽）。前端要显示「本班 N 人参与排名」用的就是这一格。
    """

    course_section_id: int
    scored_count: int
    entries: list[NormalizedEntryRead]


class UnassignedEntryRead(BaseModel):
    """有小测、但那个学期**不在任何教学班**的学生 → 「班内百分位」对他**无定义**。

    ⚠️ 三种候选处置里选「点名报出来」：① 当成一个只有他一个人的班 → 他会拿到
    ``50.0``（标准 percentile rank 公式在 ``n = 1`` 时的自洽结果），而那个 50
    看起来像真的算过；② 给 ``0`` → 把「不知道」讲成「最差」；
    ③ **列进 ``unassigned``** → 教师看得见「这个学生没编班」，而那本来就是要修的
    数据问题（``enrollment`` 漏了一条）。
    """

    student_id: int
    mini_test_id: int


class NormalizedScoreRead(BaseModel):
    """``GET /api/mini-tests/normalized?semester_id=&week=`` 的响应。

    ⚠️ **按教学班分组**（``sections``）而不是平铺一张学生表：spec §8.1 的算式逐字是
    「**该教学班内**折返秒数的百分位反查」，而一个学生同一学期**可能在两个班**
    （:class:`CourseSection.GROUPING_MODES` 的注释：阶段一的行政班与阶段二的分层班
    **并存**）。那时他在两个班里各有一行、百分位各不相同——平铺就会丢掉
    「这个分是相对谁算的」这个信息。
    """

    semester_id: int
    week: int
    sections: list[NormalizedSectionRead]
    unassigned: list[UnassignedEntryRead]
