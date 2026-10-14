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
    "NormalizedSelfRead",
    "NormalizedSelfSectionRead",
    "RpeOpenResult",
    "RpeRecordRead",
    "RpeStatusRead",
    "RpeSubmitCreate",
    "RpeSubmissionRead",
    "RpeTokenRead",
    "TrainingLogCreate",
    "TrainingLogRead",
    "UnassignedEntryRead",
]


# ---------------------------------------------------------------------------
# class_session（DB 7 列；读模型 **6** 列；唯一可写的一个，也是唯一 cascade 的一个）
# ---------------------------------------------------------------------------


class ClassSessionRead(ReadModel):
    """``class_session`` 的 **6** 列（DB 那 7 列**减去 ``rpe_token``）。

    ⚠️⚠️ **``rpe_token`` 自 Plan 03 收尾小修波起不在本模型上**（此前它在，于是本模型
    是「7 列、与 DB 逐字对齐」）。理由是**泛型 ``GET`` 缺省匿名**（Task 3 的偏离 ⑦：
    大屏与列表要能不登录就读，用户 2026-10-08 裁定「加强制」时也逐字保留了这一半；
    ⚠️ 「一律」二字自 Plan 05A Task 5 起有了 2 个例外，而 ``class-sessions`` **不在**
    其中——待清扫波真 HTTP 实测匿名 ``GET /api/class-sessions`` 仍是 **200**，
    故下面那一句论证一字不变。账面只有一个住址：
    :mod:`app.api.routers.catalog` 的模块 docstring，本处不复述第二份），
    故那一格留在 read 模型上等于把「学生提交课堂快评的**唯一闸门**」摊在一个匿名 GET 上：
    任何人 ``GET /api/class-sessions`` 就能读到全部口令，而它存在的理由恰恰是挡
    「学生猜 ``class_session_id`` 乱交」（:func:`app.api.routers.feedback._new_rpe_token`
    的 docstring 逐字写了这个用途）。**匿名可读 = 闸门形同虚设。**

    ⚠️ 于是它是**本仓第一个「与 DB 列不逐字对齐」的 ``*Read``**，
    ``tests/api/test_crud.py::test_every_read_schema_covers_exactly_the_model_columns``
    的第一拍为此多了一份清单
    :data:`~tests.api.test_crud._SERVER_GENERATED_HIDDEN_COLUMNS`——它与
    :data:`~tests.api.test_crud._SERVER_FILLED_COLUMNS` 是**两档**（前者「服务端生成、
    且**不在** read 模型里暴露」，后者「服务端填、但**要**暴露」），两个常量的注释
    各自写明自己那一档。

    ⚠️⚠️ **摘掉本模型上那一格只堵住了洞的一半**：泛型 **list 端点不走
    ``response_model``**（它显式只 SELECT ``kept`` 那些列、手工拼 dict，理由逐字见
    :func:`app.api.crud.build_crud_router` 里那个端点的 docstring），故
    ``GET /api/class-sessions``——**正是终审点名的那个 URL**——照旧会原样返回口令。
    另一半的住址是 :data:`app.api.routers.catalog.RESOURCES` 里 ``/api/class-sessions``
    那一行的 ``"list_exclude": ("rpe_token",)``（23 行里唯一一行显式传它）。
    ⚠️ **加第二个秘密列时两处都要改**：只改一处会得到一个「看起来修好了」的洞，
    而两侧各有守卫（``test_every_read_schema_covers_exactly_the_model_columns`` 与
    ``test_every_resource_list_omits_json_text_columns_and_read_one_includes_them``）。

    ⚠️ 教师仍然看得到口令，只是换了门：
    ``GET /api/class-sessions/{class_session_id}/rpe-token``（教师头，
    :func:`app.api.routers.feedback.read_rpe_token`），它返回**既有的**那一个、
    **不重新生成**。⚠️ 这一档是控制者的裁定（方案 b）。⚠️ 而它给的理由
    （「方案 a 要重新 ``open-rpe``，会生成**新**口令，学生手上那个就废了」）
    **与本仓的实现不符**，实现者据实更正：:func:`~app.api.routers.feedback.open_rpe`
    是幂等的且**第二次不换口令**（``already_open=True``，守卫
    ``test_open_rpe_twice_keeps_the_first_token``），故方案 a 拿到的其实是同一个串。
    选 b 的真正理由是**语义**：a 要让教师端拿一个 ``POST``（「发起课堂快评」这个动作）
    去当读操作使，前端还得靠 ``already_open`` 那一格反推「其实什么都没发生」；
    而 b 是一个 ``GET``，它说的就是它做的。两个方案都堵得住洞，b 不把话说反。

    ⚠️ ``rpe_opened`` **留在**本模型上：它是「教师点没点『发起课堂快评』」
    （spec §8.1 的第一步），**不是**「有没有人提交」；它不是秘密，
    而教师端列表要靠它显示「这节课发起了没有」。
    ⚠️ 代价（硬规矩 #39）：于是学生端**无法**从 API 拿到口令，只能读教师投屏。
    这正是 spec §8.1 的原意（口令在课堂上投屏、学生手输），故本处如实记录而不补救。
    """

    id: int
    course_section_id: int
    session_date: dt.date
    period: int
    rpe_opened: bool
    #: ⚠️ **可空**（Plan 03 Task 5 的 P5-A1）：教师在前端实时建的课次没有批次可指，
    #: 那一行落 ``NULL``。改可空之前本字段是 ``int``，于是一条 ``NULL`` 会让
    #: ``response_model`` 校验失败 → **500**，而 500 会把「这一行是教师实时建的」
    #: 这件事伪装成服务器故障（前端只会显示「服务出错」）。
    batch_id: int | None


class ClassSessionCreate(BaseModel):
    """``class_session`` 的 **5** 个客户端可写列（7 列减去 ``id`` 与 ``rpe_token``）。

    ⚠️⚠️ **``rpe_token`` 自 Plan 03 全分支终审的 I4 之后不在本模型上**（此前它在，
    于是本模型是「6 个可写列」）。理由是那一列**由服务端填**：教师「发起课堂快评」的
    正主是 ``POST /api/class-sessions/{class_session_id}/open-rpe``
    （:func:`app.api.routers.feedback.open_rpe`），它是**全仓唯一**调
    :func:`app.api.routers.feedback._new_rpe_token` 的地方，而那个函数强制了两件
    本模型给不了的事：① 走 :mod:`secrets` 的 CSPRNG（不是 ``random`` 的梅森旋转，
    看过几个输出就能预测下一个口令）；② 长度逐字等于
    :attr:`app.db.models.feedback.ClassSession.RPE_TOKEN_LEN`。
    ⚠️ 而 **SQLite 不强制 ``VARCHAR`` 长度**，故客户端从泛型 POST 塞一个 200 字符的
    口令**永远不报错**——那正是 ``_new_rpe_token`` 的 docstring 自己点名的失效形态
    （「换到 MySQL 会静默截断、而截断后的口令永远校验不过」）。
    与 Task 4 的 :class:`app.api.schemas.prescription.OverrideCreate` 少两格、
    Task 5 的 :class:`RpeSubmitCreate` 少两格是同一条纪律（服务端填的字段不上请求模型）。
    守卫是 ``tests/api/test_crud.py`` 的
    :data:`~tests.api.test_crud._SERVER_FILLED_COLUMNS` 那一格。

    ⚠️ ``rpe_opened`` **仍然在**本模型上（教师可以先建课次、稍后再发起快评）。
    ⚠️ 代价如实记录（硬规矩 #39）：于是「``rpe_opened=True`` 而 ``rpe_token IS NULL``」
    这个不一致状态**仍然**能从泛型 POST/PATCH 出去（DB 侧没有跨列约束，本模块也刻意
    不加）。它不是一句谎而是一个**安全的失败**：:func:`app.api.routers.feedback.submit_rpe`
    的第三道闸门（:func:`app.api.routers.feedback._rpe_is_open`，判 ``rpe_opened`` **且**
    ``rpe_token`` 非空）→ **409**
    ``rpe_not_opened``，学生交不上来，教师端会看到「这节课还没发起」。

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
    batch_id: int | None = None


class ClassSessionUpdate(BaseModel):
    """``class_session`` 的部分更新（**5** 个客户端可写列，与 :class:`ClassSessionCreate` 同一份）。

    ⚠️⚠️ **教师「发起课堂快评」不是本端点**（Plan 03 全分支终审的 I4：本处此前逐字写着
    「教师『发起课堂快评』就是 ``PATCH {"rpe_opened": true, "rpe_token": "…"}``」，
    把 Plan 04 指向了错误的门，而同一个 docstring 的末尾又写着「Task 5 的采集端点是
    它的正主」，前后两句互相矛盾）。**正主是**
    ``POST /api/class-sessions/{class_session_id}/open-rpe``
    （:func:`app.api.routers.feedback.open_rpe`）：它是全仓唯一调
    :func:`~app.api.routers.feedback._new_rpe_token` 的地方，故也是「``rpe_opened=True``
    与 ``rpe_token`` 非空**一起写**」的唯一住址，而且**幂等**（第二次点不换口令，
    否则第一个学生抄在纸上的那串会当场失效）。它回 200、把口令回给前端投屏。

    ⚠️ 于是 **``rpe_token`` 不在本模型上**（理由与代价逐字见
    :class:`ClassSessionCreate` 的 docstring 第一节；一句话版本：SQLite 不强制
    ``VARCHAR`` 长度，从 PATCH 写一个超长口令永远不报错，而那个口令换到严格长度的
    后端会被静默截断、从此永远校验不过）。
    ⚠️ 本模型因此**只能**改 ``rpe_opened``，改不出一个口令；把 ``rpe_opened`` 单独
    置 ``True`` 得到的是「发起了但没有口令」，而 :func:`~app.api.routers.feedback.submit_rpe`
    对那一档报 **409** ``rpe_not_opened``——一个安全的失败，不是一句谎。

    两列的一致性（``rpe_opened=False`` 时 ``rpe_token`` 应为 ``NULL``）
    **在 DB 侧没有约束**（那一列的注释明写了这件事并把它交给写入方），
    本模块也刻意不加：加一条跨列校验就等于在 API 层替
    :class:`app.db.models.feedback.ClassSession` 声明一个它自己没声明的不变量。
    ⚠️ 那条 Task 3 的关切自 Task 5 建出 ``open-rpe`` 起**兑了一大半**
    （「一起写」有了唯一住址），剩下的半格是「泛型 PATCH 仍能把 ``rpe_opened``
    单独翻上去」，如实记录在 :func:`~app.api.routers.feedback.open_rpe` 的 docstring 里。
    """

    course_section_id: int | None = None
    session_date: dt.date | None = None
    period: int | None = None
    rpe_opened: bool | None = None
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
# 本段这 **14** 个是**八个**特例端点用的（Task 5 的七个 + 收尾小修波加的
# ``GET …/rpe-token`` 那一个，见 :class:`RpeTokenRead`）。⚠️ **两段刻意不合并**：
# 泛型那一份的形状由
# ``tests/api/test_crud.py::test_every_read_schema_covers_exactly_the_model_columns``
# 按「与 DB 列逐字对齐」钉住（⚠️ 自收尾小修波起有**一个**例外：``ClassSessionRead``
# 少 ``rpe_token`` 那一格，由那份测试的
# ``_SERVER_GENERATED_HIDDEN_COLUMNS`` 清单点名），而特例这一份的形状由**业务语义**定
# （例如 ``RpeStatusRead`` 里的 ``not_submitted`` 在任何一张表里都没有对应的列）。
# 把它们混在一起会让那条「与列对齐」的守卫不得不为特例模型开例外。
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


class RpeTokenRead(BaseModel):
    """``GET /api/class-sessions/{id}/rpe-token`` 的响应（**教师身份**，返回既有的口令）。

    Plan 03 收尾小修波加的第二个「口令出口」。第一个是 :class:`RpeOpenResult`
    （``POST …/open-rpe``，教师**发起**时把口令回给前端投屏），本模型是它的**只读**版：
    教师翻页回来要再看一次那个口令，而**不重新生成**。
    ⚠️ 它存在的唯一理由是 :class:`ClassSessionRead` **不含** ``rpe_token``
    （理由逐字见那个模型的 docstring 首段，本处刻意不复述第二份：口令是
    「学生提交课堂快评的唯一闸门」，而那个资源今天仍在匿名可读的缺省那一档里）。

    ⚠️ **只有两格，且 ``rpe_opened`` 刻意不在里面**：本端点在「快评没发起」时回
    **409** :data:`app.api.routers.feedback.CODE_RPE_NOT_OPENED`，故一个 200 响应
    **必然**意味着已发起。再带一格恒为 ``True`` 的布尔，是给前端一个可以自相矛盾的地方
    （``{"rpe_opened": false, "rpe_token": "…"}`` 这个组合在结构上就写不出来）。

    ⚠️ 于是 ``rpe_token`` 是 ``str`` 而**不是** ``str | None``：「没有口令」不是一档
    ``null``，是一个 409（本项目最响的那条纪律：不要用 ``null`` 顶替「不知道」——
    一个 ``null`` 会让前端把「老师还没发起」渲染成「口令是空的」）。
    ⚠️ 与 :class:`RpeOpenResult` 刻意**不合并**（后者多两格 ``rpe_opened`` /
    ``already_open``，而 ``already_open`` 是「幂等」的载体，只有 ``POST`` 那一侧有意义）。
    """

    class_session_id: int
    rpe_token: str


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
    """**一个学生的一次小测在班内的折返百分位**（spec §8.1 三格里的**第二格**）。

    ------------------------------------------------------------------
    ⚠️⚠️ Plan 06 Task 9 起它**只有三格**（此前是五格）
    ------------------------------------------------------------------

    摘掉的是 ``squat_score`` 与 ``composite``。理由是**契约面**的、不是取舍：

    * 那两格承载的是**原始值**：``squat_score`` 逐行等于 ``mini_test.squat_30s_count``
      （spec §8.1 逐字「深蹲得分 = 次数（直接用）」），而 ``composite`` 是两项的
      等权平均、故 ``squat = 2 × composite − shuttle_score`` 可**反推**。
      两格都摘掉才真的把「别人的原始体测值」挡住，只摘一格等于没摘。
    * 此前的处置是**列级**收窄（学生档把别人的那两格置 ``None``），于是同一个操作的
      响应体**随身份而变**，而 OpenAPI 只有一张 schema —— 生成出来的 ``schema.d.ts``
      因此宣称「这两格永远有值」，那是一份**假契约**。
    * 本波把列级收窄抬成 **schema 级摘列**：本模型从此**不含任何随身份而变的列**，
      三格对四种身份逐字相同。⚠️ 而「本人要看到自己的那两格」这一档改由
      :class:`NormalizedSelfRead`（``GET /api/mini-tests/normalized/me``）承担 ——
      那一个端点的形状**恒定**，故它是真契约。

    ⚠️ ``shuttle_score`` **刻意留着**：它是**换算结果**（0–100 的班内百分位，
    不含原始健康量），而学生端要靠**全班**的它算「比自己慢的人数」与名次
    （``MiniTest.vue`` 的 ``mySections``）—— 把它也收到 ``student_self`` 那一档
    会让名次恒为 1。
    ⚠️ ``None`` 是它的既有合法值：``shuttle_20m_s IS NULL`` 的行**不进**百分位样本
    （否则一个「没测」的人会被当成「最慢的那个」，把全班的百分位一起往下拽），
    它自己的 ``shuttle_score`` 就是 ``None``。
    """

    student_id: int
    mini_test_id: int
    shuttle_score: float | None


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

    ⚠️⚠️ **``sections`` 里有哪些班随身份而变**（Plan 06 Task 8 的响应级裁班：
    学生只留自己 ``enrollment`` 的班、教师只留本学期任教的班、管理员全留），
    而**每一行的列**恒为 :class:`NormalizedEntryRead` 那三格（Plan 06 Task 9 的
    schema 级摘列）。⚠️ 两者是两件不同的事：前者收的是「哪些行」——OpenAPI 表达不了
    行数，但那是分页/过滤的常规形状；后者收的是「哪些列」，而它今天**不随身份而变**，
    故 ``schema.d.ts`` 上那三格是真契约。逐字交代住在
    :func:`app.api.routers.feedback.normalized_scores` 的 docstring 里。
    """

    semester_id: int
    week: int
    sections: list[NormalizedSectionRead]
    unassigned: list[UnassignedEntryRead]


class NormalizedSelfSectionRead(BaseModel):
    """**本人**在**一个教学班**里的标准化得分（spec §8.1 的三格，**全列**）。

    ⚠️ 三格一律由 :func:`app.domain.report.mini_test_scores` 那**一份**算式给出，
    本模型不重算任何一格（守卫是 ``tests/domain/test_report.py`` 的
    ``test_the_mini_test_normalization_has_exactly_one_definition``：AST 数定义份数）。
    ⚠️ 而它与 :class:`NormalizedEntryRead` 的 ``shuttle_score`` **必须逐字相等**
    （同一次小测、同一个班、同一个样本）—— 那一格由
    ``tests/api/test_feedback.py`` 的
    ``test_the_self_endpoint_agrees_with_the_class_level_percentile`` 双向钉住。

    ⚠️ **量纲是混的**（``squat_score`` 是**次数**、``shuttle_score`` 是 **0–100 的
    百分位**），如实记录：spec §8.1 逐字要求「深蹲得分 = 次数（直接用）」，故照它算、
    **不**擅自把深蹲也转成百分位（那是改 spec 的算法、是专家的活）。
    ⚠️ 于是 ``composite`` 不是一个可以跨班比较的绝对量，而把它当成一个「体能总分」
    来读是错的（:func:`app.domain.report.mini_test_scores` 的 docstring 逐字写了这一条）。
    ⚠️ 它今天的两个消费者（``RED_MINITEST_DROP``「连续两次下降 ≥ 5%」与本模型）
    都只用它做**同一个班内**的相对比较，故量纲混用不影响结论。

    ⚠️ **任一项为 ``None`` 则 ``composite`` 也是 ``None``**（不是把 ``None`` 当 0——
    那会让这个学生的综合分变成「另一项的一半」，是一句关于他的假话）。
    """

    course_section_id: int
    mini_test_id: int
    squat_score: float | None
    shuttle_score: float | None
    composite: float | None


class NormalizedSelfRead(BaseModel):
    """``GET /api/mini-tests/normalized/me?semester_id=&week=`` 的响应。

    ⚠️⚠️ **形状恒定**（本模型存在的全部理由）：它恒为「**调用者自己**的那几行、
    **全列**」。⚠️ 于是它**不随身份而变** —— 教职与匿名根本读不到它
    （``403`` / ``401``，逐字见
    :func:`app.api.routers.feedback.normalized_scores_self`），而任何一种能读到它的
    身份读到的都是同一个形状。OpenAPI 因此是**真契约**：``schema.d.ts`` 上说有值的格，
    响应里就有值。⚠️ 那正是 :class:`NormalizedEntryRead` 摘掉两格之后**欠下**的那一格
    （本人要看到自己的深蹲得分与综合分），本模型把它还上。

    ⚠️ **``sections`` 可以有 0 / 1 / 2 项**：

    * ``0`` —— 本人那一周没有小测行，**或**他本学期没编班（两档在本响应上不可分辨，
      而在 :class:`NormalizedScoreRead` 那一侧可分辨：``unassigned``）；
    * ``2`` —— 一个学生同一学期**可能在两个班**（行政班与分层班并存），
      那时他在两个班里各有一行、百分位各不相同（演示库上每个人都恰好 2 个）。
    """

    semester_id: int
    week: int
    sections: list[NormalizedSelfSectionRead]
