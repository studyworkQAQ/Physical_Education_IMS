"""spec §8.1 **三源采集**的七个特例端点（Plan 03 Task 5）。

三源 = 课堂端（RPE 快评）/ 课外端（每日打卡）/ 阶段端（双周二次小测）。它们**不走**
:func:`app.api.crud.build_crud_router`，因为每一个都有「客户端算不出来、或不该让它算」
的一半——:data:`app.api.routers.catalog.RESOURCES` 里那三个资源因此是
``writable=False``，**本模块是那三张表唯一的写入方**（``class_session`` 例外：它是
``writable=True``，本模块只加它的一个**操作**端点，不重复它的 CRUD）。

----------------------------------------------------------------------------
七个端点
----------------------------------------------------------------------------

===============================================================  ======  =====================
路径                                                              码      响应模型
===============================================================  ======  =====================
``POST /api/class-sessions/{id}/open-rpe``                        200     :class:`RpeOpenResult`
``POST /api/rpe-records``                                         **201** :class:`RpeRecordRead`
``GET  /api/class-sessions/{id}/rpe-status``                      200     :class:`RpeStatusRead`
``POST /api/training-logs``                                       **201** :class:`TrainingLogRead`
``GET  /api/students/{id}/training-logs/completion-rate``         200     :class:`CompletionRateRead`
``POST /api/mini-tests/batch``                                    200     :class:`MiniTestBatchResult`
``GET  /api/mini-tests/normalized``                               200     :class:`NormalizedScoreRead`
===============================================================  ======  =====================

⚠️ **两个 ``POST`` 回 201 + ``Location``、另两个回 200**，这个区分与 Task 3/4 逐字一致：
``rpe-records`` 与 ``training-logs`` 是「**创建了一个新资源**」（有它自己的 URI 可指），
而 ``open-rpe`` 是「对一个已存在的课次做了一次**操作**」、``mini-tests/batch`` 是
「一次提交了若干行、要回报每一行的下落」（它的响应体是**报告**、不是一个新资源）。

----------------------------------------------------------------------------
⚠️⚠️ include 顺序在本 Task 起**承重**（:mod:`app.api.routers` 的模块 docstring 已同步）
----------------------------------------------------------------------------

``mini-tests`` 是只读资源，故泛型工厂**注册**了 ``GET /api/mini-tests/{mini_test_id}``，
而本模块的 ``GET /api/mini-tests/normalized`` 与它**同形**（都是两段、末段一个占位）。
FastAPI 按注册先后取先匹配的，故本 router 必须 include 在
:data:`app.api.routers.catalog` **之前**——否则 ``normalized`` 会被当成
``mini_test_id`` 去转 ``int``，得到 **422** 且消息是「``mini_test_id`` 不是一个整数」，
把下一个人支去修前端传的参。守卫是
``tests/api/test_feedback.py::test_the_normalized_route_is_not_swallowed_by_the_generic_read_route``。
⚠️ Task 4 的四个路径与泛型的五个端点「没有一个同形」，故那时顺序不承重；本 Task 是
第一个让它承重的。

----------------------------------------------------------------------------
时钟：``_now_local`` 是「现在几点」在本模块的唯一住址
----------------------------------------------------------------------------

**API 层可以碰时钟**（计划 Architecture 一节逐字写着），而 domain 与 pipeline 的纯函数
一律要时间由调用方注入。:func:`_now_local` 就是那个注入点，三件事都由它一处持有：

1. **时区** = :data:`app.config.TIMEZONE`（IANA 名字，本模块不写第二份 ``"Asia/Shanghai"``）；
2. **naive 化**：``.replace(tzinfo=None)`` 是**承重的**——本仓的 ``DateTime`` 列存 naive
   （SQLite 没有时区类型），而 aware 与 naive 相比会当场
   ``TypeError: can't compare offset-naive and offset-aware datetimes``；
3. **可测性**：测试 ``monkeypatch`` 这一个函数就换掉了全部端点看到的时钟。
   ⚠️ 没有它，:data:`CHECKIN_DEADLINE` 的三条边界测试只能在每天 21:59–22:01
   那两分钟里跑——那不是测试，是彩票。

⚠️ **原型口径：不处理跨时区学生**（:data:`app.config.TIMEZONE` 的注释里逐字写了理由）。

----------------------------------------------------------------------------
身份与作用域（计划 Review Focus 第 1 条：越权访问）
----------------------------------------------------------------------------

* **学生侧三个**（``POST /api/rpe-records``、``POST /api/training-logs``、
  ``GET …/completion-rate``）：``X-Student-Id`` 必需，且经
  :func:`app.api.deps.require_scope` 校验。⚠️ 两个 ``POST`` 的请求体里**没有**
  ``student_id``（服务端从头取），故「替别人交」在结构上不可能；闸门挡的是
  「头里那个 id 根本不在册」这一档。
* **教师侧四个**（``open-rpe``、``rpe-status``、``mini-tests/batch``、
  ``mini-tests/normalized``）：``X-Teacher-Staff-No`` 必需 + :func:`require_teacher`。
  ⚠️ 原型**没有**「教师 ↔ 班级 ↔ 学生」的授权模型，故任何在册教师可以读任何班的
  名单、录任何班的小测（:func:`app.api.deps.require_teacher` 的 docstring 里如实记了
  这条代价）。
* 四个端点都挂 ``dependencies=[Security(...)]``（P4-A5），故那两个请求头在
  ``/openapi.json`` 的 ``components.securitySchemes`` 里各有一格、Swagger 的
  「Authorize」弹窗里填得进去。⚠️ **判定不在 ``Security`` 上**（它 ``auto_error=False``、
  只负责声明），仍在 :func:`current_student` / :func:`current_teacher`，
  故「缺头」的码仍是本仓既有的 **401**。

----------------------------------------------------------------------------
⚠️ 本模块**刻意不做**的三件事
----------------------------------------------------------------------------

1. **不做扫码签到**（spec §8.1 原文：「H5 调摄像头权限复杂，且原型阶段学生已登录并
   绑定教学班」）。
2. **不做 ``rpe_token`` 的过期**。原型阶段它只是一个 16 字符随机串，用来挡
   「学生猜 ``class_session_id`` 乱交」；不做时效是因为一节课的长度不固定
   （连堂、拖堂、补课），而一个过期的口令在课堂上表现为「学生明明填对了却报错」。
3. **不把 ``normalized_score`` 写回 ``mini_test`` 那一列**。它由
   ``GET /api/mini-tests/normalized`` **现算**：「班内百分位反查」要读整个教学班的行，
   而教师是**一次提交一批**的——录到第 3 行时第 4..40 行还没进来，那一刻算出来的
   百分位**必然是错的**。让那一列留在 ``NULL`` 比写一个错的值诚实（包约定 1）。
   ⚠️ 代价（硬规矩 #39）：``mini_test.normalized_score`` 因此**只有**
   :func:`app.demo_data.build_demo_feedback` 一个写入方（它写的是演示口径的近似值），
   而 ``GET /api/mini-tests`` 读到的那一列与 ``/normalized`` 现算的**不是同一个数**。
   已登记为关切；要消除它就得让 ``normalized`` 端点回写，而那会让一个 ``GET``
   有副作用（本仓不接受）。
"""
import datetime as dt
import secrets
import statistics
from collections import defaultdict
from collections.abc import Sequence
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response, Security
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# ⚠️ 复用 Task 3 那个私有的 404 助手（与 Task 4 同一条处置）：「主键查无此行」这件事
#    在全仓只应该有一种说法。
from app.api.crud import _get_or_404
from app.api.deps import (
    STUDENT_ID_SCHEME,
    TEACHER_STAFF_NO_SCHEME,
    current_student,
    current_teacher,
    get_db,
    require_scope,
    require_teacher,
)
from app.api.errors import error_response

# ⚠️ 复用 Task 4 那个私有的「哪一张处方在那一天生效」（它把四个条件与 ORDER BY 的
#    理由逐条写清了）。**不抄第二份**：完成率端点与学生端「本周训练单」必须对
#    「哪一张处方现在生效」给出同一个答案，否则同一屏上的两个数会互相矛盾。
from app.api.routers.prescription import _current_prescription
from app.api.schemas.feedback import (
    CompletionRateRead,
    MiniTestBatchFailure,
    MiniTestBatchResult,
    MiniTestEntryCreate,
    NormalizedEntryRead,
    NormalizedScoreRead,
    NormalizedSectionRead,
    RpeOpenResult,
    RpeRecordRead,
    RpeStatusRead,
    RpeSubmitCreate,
    RpeSubmissionRead,
    TrainingLogCreate,
    TrainingLogRead,
    UnassignedEntryRead,
)
from app.config import TIMEZONE

# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：这几个类**都不在** app.db.models 的
#    公有导入面上，写 models.ClassSession 会当场 AttributeError。
from app.db.models.feedback import ClassSession, MiniTest, RpeRecord, TrainingLog
from app.db.models.organisation import CourseSection, Enrollment, Semester
from app.db.models.prescription import Prescription
from app.domain.prescription.weekly import current_week, weekly_training_sheet
from app.pipeline.prescription_stage import effective_package, weekly_factors_of
from app.refdata_prescription import exercises

__all__ = [
    "CHECKIN_DEADLINE",
    "CHECKIN_SOURCE",
    "CODE_INVALID_RPE_TOKEN",
    "CODE_RPE_NOT_OPENED",
    "DAYS_PER_WEEK",
    "PROXY_FILL_SECONDS",
    "RATE_PRECISION",
    "SCORE_PRECISION",
    "router",
]

#: **打卡窗口的上界**（spec §8.1 逐字：「打卡窗口 = 当日 00:00–22:00。22:00 后提交
#: 仍入库但标记 ``late = true``，**不计入当日完成**」）。
#:
#: ⚠️⚠️ **窗口是闭区间 ``[00:00, 22:00]``，故判定式是 ``> CHECKIN_DEADLINE``、
#: 不是 ``>=``**（Review Focus 第 2 条要求「响亮地定一个口径并测边界」）：
#: spec 写的是「22:00 **后**」，而 ``22:00:00`` 整点不是「后」。于是
#: ``21:59:59`` 不迟、``22:00:00`` **不迟**、``22:00:01`` 迟。
#: ⚠️ 三条守卫只差一秒（``LATE_BOUNDARIES``），故把 ``>`` 改成 ``>=`` 只有中间那条会红
#: ——那正是「边界测试」要的形状：一个字符的改动就有测试respond。
#: ⚠️ 下界 ``00:00`` **不需要判**：``datetime.time`` 的最小值就是它，任何时刻都 ``>=``。
CHECKIN_DEADLINE: dt.time = dt.time(22, 0)

#: 学生打卡写进 ``training_log.source`` 的值。
#:
#: ⚠️ **值域的所有者是** :attr:`TrainingLog.SOURCES`（+ DB 的 ``ck_training_log_source``），
#: 本常量只回答「三个值里采集端点写哪一个」。守卫是
#: ``test_the_checkin_source_constant_is_inside_the_model_value_domain``
#: （两侧不同源：一侧是本常量、一侧是类常量 + CHECK）。
CHECKIN_SOURCE = "checkin"

#: ``rpe-status`` 里「疑似代填」的耗时门槛（秒）。
#:
#: ⚠️ **它不是准入门槛**：``POST /api/rpe-records`` 对 ``elapsed_seconds > 60``
#: **照样收**（spec §8.1 明写「**已知局限：无法防代填**」，而一个真花了 90 秒填的
#: 学生不该被拒）。本常量只决定「哪些行被单独计数报给教师」，由**人**去判断。
#: ⚠️ 出处：spec §8.1 说「指导文件要求 **10 秒**内完成」，而 10 秒太紧
#: （网络慢、字体大、读题慢都会超），故取它的 **6 倍**作为一个「明显不是在课堂上
#: 顺手填完」的粗筛线。这是本 Task 的工程决定，登记 spec §14。
PROXY_FILL_SECONDS: float = 60.0

#: 完成率 ``round`` 的小数位。⚠️ 裸的 ``numerator`` / ``denominator`` 与它并排给，
#: 故这次 round 不丢信息（Plan 02 P5-A6 批评的是「round 之后没有裸值可对账」那一种）。
RATE_PRECISION = 4

#: 小测标准化得分 ``round`` 的小数位。⚠️ **中间步骤不 round**：``composite`` 用
#: **未 round 的**百分位算完再 round，否则 ``(30 + 83.33) / 2 = 56.665`` 会撞上
#: 浮点的银行家舍入（``round(56.665, 2)`` 在 CPython 上给 ``56.66``），
#: 而正确的 ``(30 + 83.3333…) / 2 = 56.6666…`` → ``56.67``。
SCORE_PRECISION = 2

#: 一周的天数。⚠️ 与 :data:`app.domain.prescription.weekly._DAYS_PER_WEEK` 是**同一个数**，
#: 但那个是 domain 的私有常量、且 domain 不得被 api 之外的层反向依赖，故本层自己持有一份。
#: ⚠️ 「7」不是业务参数（它是历法），故两处各写一份不构成「阈值有两个所有者」。
DAYS_PER_WEEK = 7

#: 「快评还没被发起」的 ``code``（409）。
#:
#: ⚠️ 用 **409** 不用 422：请求体本身没有错（``class_session_id`` 存在、``rpe`` 合法），
#: 错的是**资源的状态**。给两个码是为了让前端能区分「你填错了」与「老师还没发起」。
CODE_RPE_NOT_OPENED = "rpe_not_opened"

#: 「课堂快评口令不匹配」的 ``code``（403）。
#:
#: ⚠️ 用 **403** 不用 422：口令是一个**凭证**，不匹配是授权失败。
#: ⚠️ 与 :func:`app.api.deps.require_scope` 同一条口径——**不**用 404 区分
#: 「课次不存在」与「口令不对」：那等于把「哪些课次已经发起了快评」告诉调用方。
CODE_INVALID_RPE_TOKEN = "invalid_rpe_token"


def _now_local() -> dt.datetime:
    """服务端**当前时刻**，naive 本地时间（时区 = :data:`app.config.TIMEZONE`）。

    ⚠️ 本模块唯一的时钟住址（模块 docstring 那一节）。``.replace(tzinfo=None)``
    **是承重的**：库里的 ``DateTime`` 列存 naive，aware 与 naive 相比会当场
    ``TypeError``。
    """
    return dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


def _new_rpe_token() -> str:
    """一个新的课堂快评口令（长度 = :attr:`ClassSession.RPE_TOKEN_LEN`）。

    ⚠️ **用 :mod:`secrets` 而不是 :mod:`random`**：``random`` 是梅森旋转伪随机，
    看过几个输出就能推出内部状态、从而**预测下一个口令**，而口令的作用是挡
    「学生猜 ``class_session_id`` 乱交」。``secrets`` 走操作系统的 CSPRNG。
    ⚠️ ``random`` 也**不在** domain 的 allow-list 里，但本模块是 ``api`` 层、不是 domain
    （架构守卫的 ``_is_api_allowed`` 是只针对 ``app.*`` 前缀的 allow-list，
    标准库不受它约束），故这里不存在守卫问题。

    ⚠️ 字节数由列宽**派生**（``RPE_TOKEN_LEN * 3 // 4``）：base64url 每 3 字节编成
    4 字符，故 16 字符 ← 12 字节，**恰好**填满、无 padding。两个数因此只有一个所有者
    （P5-A6）；末尾那个切片是**兜底**——它保证「万一算式被改错，也不会写出一个
    塞不进列的口令」（SQLite 不强制 ``VARCHAR`` 长度，故溢出在本仓永远不报错，
    换到 MySQL 会静默截断、而截断后的口令**永远校验不过**）。
    """
    nbytes = ClassSession.RPE_TOKEN_LEN * 3 // 4
    return secrets.token_urlsafe(nbytes)[: ClassSession.RPE_TOKEN_LEN]


def _shuttle_percentile(seconds: float, sample: Sequence[float]) -> float:
    """**班内百分位反查**（spec §8.1：「折返得分 = 该教学班内折返秒数的百分位反查」）。

    折返跑是**秒数越少越好**，故「反查」= 把方向倒过来：数「比自己**慢**的人数」。
    用的是标准的 percentile rank 公式（并列取中点）::

        PR = (比自己慢的人数 + 0.5 × 与自己并列的人数) / 样本数 × 100

    ⚠️ **并列取中点**（``0.5 ×``）而不是「严格小于」：三个人跑出一样的秒数时，
    严格口径会给他们三个**不同**的分（取决于谁排在前面），而中点口径给他们
    **同一个** 50.0 —— 后者才是「并列」该有的样子。
    ⚠️ ``n = 1`` 时本式给 **50.0**（自己的并列数 = 1，``0.5 / 1 × 100``）。
    但这一档**在生产里到不了**：``sample`` 至少含调用者自己，而一个学生若不在任何
    教学班，他会走 ``unassigned`` 那一支、根本不进百分位；若他在班里，班里的样本
    就是「这个班全部有折返成绩的行」，其中至少他一个。故 ``n = 1`` 只在
    「全班只有一个人测了折返」时出现，那时 50.0 是标准公式的自洽结果。
    ⚠️ 返回**未 round** 的值：``composite`` 要用裸值算完再 round（见
    :data:`SCORE_PRECISION` 的注释，那里逐字写了 ``56.665`` 那个坑）。
    ⚠️ ``sample`` 为空时本函数会 ``ZeroDivisionError``——**刻意不兜底**：
    调用方只在 ``shuttle_20m_s is not None`` 时调它，那时 ``sample`` 必非空。
    兜一个 ``return 0.0`` 会把「算错了」静默变成「这个学生最差」。
    """
    slower = sum(1 for value in sample if value > seconds)
    tied = sum(1 for value in sample if value == seconds)
    return (slower + 0.5 * tied) / len(sample) * 100.0


def _week_days(start_date: dt.date, week: int) -> list[dt.date]:
    """学期第 ``week`` 周（1-based）的那 7 天，按日期升序。

    ⚠️ ``week`` 是**学期周次**，与 ``mini_test.week`` / ``weekly_class_report.week``
    同口径（**不是**处方微周期内的周次——那个由 :func:`current_week` 算，
    两者在 ``generated_on`` 不等于 ``semester.start_date`` 时会错开，
    而那个错开由 ``completion-rate`` 端点的「逐天判定」处理）。
    ⚠️ 不校验 ``week`` 的上界：一个超出学期长度的周次自然得到一段落在
    ``end_date`` 之外的日期，于是那几天没有处方、也没有打卡 → 完成率 ``null``
    且 ``reason`` 说明。**不**回 422：「第 20 周」在一个 16 周的学期里是
    「那一周什么都没发生」，不是一次非法请求。
    """
    first = start_date + dt.timedelta(days=(week - 1) * DAYS_PER_WEEK)
    return [first + dt.timedelta(days=offset) for offset in range(DAYS_PER_WEEK)]


def _training_days_of(session: Session, row: Prescription, week: int) -> tuple[set, bool]:
    """一张处方在它的第 ``week`` 周里的**训练日集合**（日期），以及那一周是否 ``paused``。

    ⚠️ **``AssembledSession.day`` 是「周内第几天」（1-based、在一套模板内连续）**，
    不是星期几、也不是日历日——:class:`~app.domain.prescription.templates.Session` 的
    docstring 逐字写了这个口径，并且逐字点名了本函数要做的事：「Task 11 的
    『本周训练单』按周次取课、**打卡完成率按处方训练日计**（spec §14 第 9 项），
    ``day`` 跳号会让『第 3 天该打卡吗』没有答案」。
    故映射是 ``处方周起点 + (day − 1) 天``，而处方周起点 =
    ``generated_on + (week − 1) × 7``——与 :func:`current_week` 的
    ``elapsed_days // 7 + 1`` **互为反函数**，两侧因此不会漂。
    """
    sheet = weekly_training_sheet(
        effective_package(row, exercises=exercises()),
        week,
        weekly_factors_of(session, row.id),
    )
    week_start = row.generated_on + dt.timedelta(days=(week - 1) * DAYS_PER_WEEK)
    return {
        week_start + dt.timedelta(days=item.day - 1) for item in sheet.sessions
    }, sheet.paused


router = APIRouter()


@router.post(
    "/api/class-sessions/{class_session_id}/open-rpe",
    tags=["class-sessions"],
    response_model=RpeOpenResult,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def open_rpe(
    class_session_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict:
    """（教师）**发起课堂快评**：置 ``rpe_opened=True`` + 生成口令，把口令回给前端投屏。

    ⚠️ **幂等，且第二次不换口令**（``already_open=True``）：教师手抖点两次时，
    若换掉口令，第一个学生已经抄在纸上的那串会当场失效，而他看到的是「口令错误」
    ——那看起来像他抄错了。与 Task 4 的 ``regenerate``「幂等 → 200 而不是 409」
    同一条口径，但这里的幂等更强一档：**连生成的值都不变**。

    ⚠️ **回 200 不回 201、不带 ``Location``**：这是对已存在的课次做了一次**操作**，
    没有新资源可以指（与 Task 4 的两个 POST 同一条约定）。

    ⚠️ 顺带把 :class:`ClassSession` 那条「``rpe_opened`` 与 ``rpe_token`` 的一致性
    在 DB 侧没有约束、交给写入方」的关切**兑现**了：本函数是「两者一起写」的唯一
    住址，故 ``rpe_opened=True`` 而 ``rpe_token IS NULL`` 这个状态从这里出不去。
    ⚠️ 但泛型的 ``PATCH /api/class-sessions/{id}`` **仍然**能把两列改成不一致
    （Task 3 刻意不加跨列校验），故那条关切只算兑了一半，如实记录。
    """
    require_teacher(session, staff_no)
    row = _get_or_404(session, ClassSession, class_session_id)
    already_open = row.rpe_opened and row.rpe_token is not None
    if not already_open:
        row.rpe_opened = True
        row.rpe_token = _new_rpe_token()
        session.commit()
        session.refresh(row)
    return {
        "class_session_id": row.id,
        "rpe_opened": row.rpe_opened,
        "rpe_token": row.rpe_token,
        "already_open": already_open,
    }


@router.post(
    "/api/rpe-records",
    tags=["rpe-records"],
    status_code=201,
    response_model=RpeRecordRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def submit_rpe(
    payload: RpeSubmitCreate,
    response: Response,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
) -> object:
    """（学生）提交课堂快评。**``student_id`` 与 ``submitted_at`` 由服务端填**。

    四道闸门按**从便宜到贵**排（前两道不查库）：

    1. 身份在册（:func:`require_scope`，一次 ``SELECT``）；
    2. 课次存在（:func:`_get_or_404`）；
    3. **快评已发起**（``rpe_opened`` 且 ``rpe_token`` 非空）→ 否则 **409**
       :data:`CODE_RPE_NOT_OPENED`。⚠️ 这一道必须在验口令**之前**：一节课还没发起时
       ``rpe_token IS NULL``，而 ``payload.rpe_token == None`` 恒为假，
       于是先验口令会把「老师还没发起」报成「你口令错了」——两种提示教师要做的事
       完全不同（前者是去点那个按钮，后者是去核对投屏）；
    4. **口令匹配** → 否则 **403** :data:`CODE_INVALID_RPE_TOKEN`。它挡的是
       「学生猜 ``class_session_id`` 乱交」（spec §4.5 的「快评口令」那一格的用途）。
       ⚠️ **不做过期**（模块 docstring 的「刻意不做」第 2 条）。

    ⚠️ 撞 ``uq_rpe_record_session_student`` → **409**（一节课一个学生只能交一次），
    由 :mod:`app.api.errors` 的全局 ``IntegrityError`` 处理器折出来，本函数不自己接：
    接了就要在这里重写一遍那句 409 的消息，而「撞自然键」这件事全仓只该有一种说法。
    ⚠️ 那条唯一约束**是承重的**：少了它，学生连点两次「提交」会让
    ``YELLOW_CLASS_RPE_HIGH`` 的「课堂 RPE 均值」被同一个人算两遍，而教师端的
    「已提交名单」会显示 101%。
    """
    require_scope(session, requester, requester)
    row = _get_or_404(session, ClassSession, payload.class_session_id)
    if not row.rpe_opened or row.rpe_token is None:
        return error_response(
            409,
            CODE_RPE_NOT_OPENED,
            f"课次 {row.id}（{row.session_date.isoformat()} 第 {row.period} 节）还没有发起"
            f"课堂快评：rpe_opened={row.rpe_opened}、rpe_token "
            f"{'为空' if row.rpe_token is None else '非空'}。教师端要先点「发起课堂快评」"
            f"（POST /api/class-sessions/{row.id}/open-rpe）",
        )
    if payload.rpe_token != row.rpe_token:
        return error_response(
            403,
            CODE_INVALID_RPE_TOKEN,
            f"课堂快评口令不匹配（课次 {row.id}）。口令由教师在课堂上投屏，"
            f"长度是 {ClassSession.RPE_TOKEN_LEN} 个字符",
        )
    record = RpeRecord(
        class_session_id=row.id,
        student_id=requester,
        rpe=payload.rpe,
        submitted_at=_now_local(),
        elapsed_seconds=payload.elapsed_seconds,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    response.headers["Location"] = f"/api/rpe-records/{record.id}"
    return record


@router.get(
    "/api/class-sessions/{class_session_id}/rpe-status",
    tags=["class-sessions"],
    response_model=RpeStatusRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def rpe_status(
    class_session_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict:
    """（教师）**已交/未交名单 + 人均 RPE + 提交耗时中位数**（spec §8.1：
    「教师端实时显示已提交/未提交名单，可现场催交」）。

    ⚠️ **名单的分母是选课人数、分子是实际提交数，两者可以不一致且两个方向都可能**：
    选了课没交的人进 ``not_submitted``；没选课却交上来的人（旁听、或选课后被退选）
    进 ``submitted`` 但不进 ``not_submitted``。故两个数**都单独给**、不让前端去减。

    ⚠️ 选课名单按 ``(course_section_id, semester_id)`` 取，而 ``semester_id`` 从
    **教学班**上读（:class:`CourseSection` 有那一列）——⚠️ **不**从 ``session_date``
    反查学期：一个日期落在哪个学期是 ``semester.[start_date, end_date)`` 的活，
    而教学班自己已经知道属于哪个学期，绕一圈去按日期反查会在「两个学期的区间重叠」
    或「课次排在学期区间外（调课）」时给出错的答案。

    ⚠️ ``mean_rpe`` / ``median_elapsed_seconds`` 在没人交时是 ``None`` 而不是 ``0``
    （「不知道」不得讲成「0」）。``mean_rpe`` **不 round**：它是给
    ``YELLOW_CLASS_RPE_HIGH``（均值 > 7）与前端同时读的，round 会让「7.00004」
    变成「7.0」从而在阈值上翻边。
    """
    require_teacher(session, staff_no)
    row = _get_or_404(session, ClassSession, class_session_id)
    section = _get_or_404(session, CourseSection, row.course_section_id)
    enrolled = set(session.scalars(
        select(Enrollment.student_id).where(
            Enrollment.course_section_id == section.id,
            Enrollment.semester_id == section.semester_id,
        )
    ).all())
    records = session.scalars(
        select(RpeRecord)
        .where(RpeRecord.class_session_id == row.id)
        .order_by(RpeRecord.student_id)
    ).all()
    submitted_ids = {record.student_id for record in records}
    elapsed_values = [
        record.elapsed_seconds for record in records
        if record.elapsed_seconds is not None
    ]
    return {
        "class_session_id": row.id,
        "course_section_id": row.course_section_id,
        "session_date": row.session_date,
        "period": row.period,
        "rpe_opened": row.rpe_opened,
        "enrolled_count": len(enrolled),
        "submitted": [
            {
                "student_id": record.student_id,
                "rpe": record.rpe,
                "elapsed_seconds": record.elapsed_seconds,
                "submitted_at": record.submitted_at,
            }
            for record in records
        ],
        "not_submitted": sorted(enrolled - submitted_ids),
        "mean_rpe": (
            sum(record.rpe for record in records) / len(records) if records else None
        ),
        # ⚠️ 只在**量到耗时**的那些行上取中位数：None 进 statistics.median 会 TypeError，
        #    而把 None 当 0 会把中位数往下拽（「没量到」不是「量到 0 秒」，包约定 1）。
        "median_elapsed_seconds": (
            statistics.median(elapsed_values) if elapsed_values else None
        ),
        "suspected_proxy_count": sum(
            1 for value in elapsed_values if value > PROXY_FILL_SECONDS
        ),
    }


@router.post(
    "/api/training-logs",
    tags=["training-logs"],
    status_code=201,
    response_model=TrainingLogRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def create_training_log(
    payload: TrainingLogCreate,
    response: Response,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
) -> object:
    """（学生）**每日打卡**。``late`` / ``submitted_at`` / ``source`` / ``batch_id``
    四个一律由服务端填（:class:`TrainingLogCreate` 的 docstring 逐条给了理由）。

    ⚠️ **``late`` 的判定式是 ``submitted_at.time() > CHECKIN_DEADLINE``**
    （闭区间，见那个常量的注释）。``log_date`` **不参与**判定：spec 说的是
    「22:00 **后提交**」，主语是提交时刻，不是「在补哪一天」。

    ⚠️ **补卡照收**（``log_date`` 与 ``submitted_at`` 的日期不一致），只是
    **不计入完成率**（那是读侧的事，见 :func:`completion_rate`）。理由：
    补卡是学生主动补交的作业，拒收它等于把数据丢掉；而完成率要严，
    故排除落在读侧——**两个决定各在自己那一层做**。

    ⚠️ ``batch_id`` 恒为 ``NULL``（P5-A1）：这一行不属于任何批次，而 ``NULL`` 让它
    天然躲过 :func:`app.db.repo.delete_by_batch`——重放那天不该删掉学生的作业。

    ⚠️ 同一天重复 → **409**（``uq_training_log_student_day``），由全局
    ``IntegrityError`` 处理器折出来。⚠️ **不做「补卡覆盖旧行」**：一天一行是这张表的
    口径，改成 upsert 会让「学生先打了『没练』、后来又改成『练了』」这件事在库里
    不留痕迹，而 ``YELLOW_CHECKIN_GAP`` 与事后审计都要能回答「他当时交的是什么」。
    """
    require_scope(session, requester, requester)
    submitted_at = _now_local()
    row = TrainingLog(
        student_id=requester,
        log_date=payload.log_date,
        submitted_at=submitted_at,
        completed=payload.completed,
        duration_min=payload.duration_min,
        feeling=payload.feeling,
        is_rest_day=payload.is_rest_day,
        late=submitted_at.time() > CHECKIN_DEADLINE,
        source=CHECKIN_SOURCE,
        batch_id=None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    response.headers["Location"] = f"/api/training-logs/{row.id}"
    return row


@router.get(
    "/api/students/{student_id}/training-logs/completion-rate",
    tags=["training-logs"],
    response_model=CompletionRateRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def completion_rate(
    student_id: int,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
    semester_id: int = Query(description="学期 id（定位学期的第一天，从而定位这一周的 7 天）"),
    week: int = Query(ge=1, description="**学期**周次（1-based，与 mini_test.week 同口径）"),
) -> dict:
    """某学生某一周的**打卡完成率**，只按处方训练日计（spec §8.1 的折中方案：
    「每日都可打卡，非训练日一键『今日休息』；但**完成率只按处方训练日计算**」）。

    ----------------------------------------------------------------------------
    分母：**处方训练日 ∩ 所查那一周的 7 天**（P5-A2 的落地）
    ----------------------------------------------------------------------------

    ⚠️ **分母不是无条件的 ``len(sheet.sessions)``**，而是那些训练日里**落在所查
    学期周内**的那些。裁定的原话是「分母改成 ``len(sheet.sessions)``」，
    而它要兑现的**理由**是「教师用 ``WEEKLY_FREQUENCY`` 覆盖之后，``sessions``
    已经反映了覆盖后的天数」——取交集**同样兑现那个理由**（交集的大小随
    ``sessions`` 变），并且多做对一件事：处方周与学期周**错位**时
    （``generated_on`` 不是学期第一天，这在真实数据里是常态），无条件的
    ``len(sessions)`` 会把不属于这一周的日子算进分母，于是「这一周一天都没训」
    被讲成「分母 2、分子 0 = 0%」。**两者在对齐时逐字相同**
    （守卫 ``test_the_completion_rate_denominator_is_the_prescription_training_days``），
    错位时交集那一个才对（守卫 ``test_training_days_outside_the_queried_week_do_not_count``）。

    ⚠️ 于是本端点**逐天**判定这 7 天：对每一天取「那天生效的处方」
    （:func:`_current_prescription`，与 Task 4 共用同一个所有者）→ ``current_week``
    → ``weekly_training_sheet`` → 那一天在不在训练日集合里。
    ⚠️ 这一周内可能跨处方、甚至跨处方周次（周中换处方），逐天判定天然处理它；
    代价是最多 7 次装配，故按 ``(prescription_id, week)`` **缓存** sheet 的结果
    （装配要反解一个大 JSON 列，7 次重复做在同一张处方上是纯浪费）。

    ----------------------------------------------------------------------------
    分子：``completed`` 且 ``not late`` 且 ``not is_rest_day`` 且**不是补卡**
    ----------------------------------------------------------------------------

    四个条件各有一条出处：前三个是 spec §8.1 逐字（「22:00 后提交…**不计入当日完成**」、
    「非训练日一键『今日休息』」），第四个（``submitted_at.date() == log_date``）
    是派单决定 ② 的「补卡入库但不计入完成率」——⚠️ 而它**需要**
    ``submitted_at`` 那一列，那一列正是本 Task 给 ``training_log`` 补的
    （:class:`TrainingLog` 的类 docstring 里逐字写了为什么不能用 ``late`` 代替它）。

    ----------------------------------------------------------------------------
    ``completion_rate`` 为 ``null`` 的三档（P5-A2：「不知道」不得讲成「0%」）
    ----------------------------------------------------------------------------

    ① 这一周里没有任何一天有生效处方（``prescription_id`` 也是 ``null``）；
    ② 有处方、但 ``current_week`` 对它返回 ``None``（已到期，该换处方了 = spec §5.2
      触发 3）——与 Task 4 的 ``outside_microcycle`` 是同一个形状；
    ③ 有处方、周次也算得出来，但训练日与这一周**一天都不重叠**。
    三档的 ``reason`` 各不相同，故前端能给三种提示，而不是都说「没有数据」。
    """
    require_scope(session, student_id, requester)
    semester = _get_or_404(session, Semester, semester_id)
    days = _week_days(semester.start_date, week)

    expected: list[dt.date] = []
    seen_prescription_id: int | None = None
    saw_week_none = False
    paused = False
    prescription_week: int | None = None
    sheets: dict[tuple[int, int], tuple[set, bool]] = {}

    for day in days:
        row = _current_prescription(session, student_id, day)
        if row is None:
            continue
        seen_prescription_id = row.id
        rx_week = current_week(row.generated_on, day, row.microcycle_weeks)
        if rx_week is None:
            saw_week_none = True
            continue
        cache_key = (row.id, rx_week)
        if cache_key not in sheets:
            sheets[cache_key] = _training_days_of(session, row, rx_week)
        training_days, sheet_paused = sheets[cache_key]
        paused = paused or sheet_paused
        if day in training_days:
            expected.append(day)
            if prescription_week is None:
                prescription_week = rx_week

    completed_days: list[dt.date] = []
    if expected:
        rows = session.scalars(
            select(TrainingLog).where(
                TrainingLog.student_id == student_id,
                TrainingLog.log_date.in_(expected),
            )
        ).all()
        completed_days = sorted(
            row.log_date for row in rows
            if row.completed
            and not row.late
            and not row.is_rest_day
            # 补卡不计入：那一天已经过去了，事后补交不能改写过程指标
            and row.submitted_at.date() == row.log_date
        )

    denominator = len(expected)
    numerator = len(completed_days)
    if denominator:
        rate: float | None = round(numerator / denominator, RATE_PRECISION)
        reason: str | None = None
    else:
        rate = None
        if seen_prescription_id is None:
            reason = (
                f"学生 {student_id} 在学期 {semester_id} 第 {week} 周"
                f"（{days[0].isoformat()} 至 {days[-1].isoformat()}）里"
                f"**没有任何一天**有生效的处方，故完成率没有定义。"
                f"处方不每天重发：它只在 spec §5.2 的五条触发之一成立时才生成，"
                f"故「没有」是常态、不是故障"
            )
        elif saw_week_none:
            reason = (
                f"学生 {student_id} 有生效的处方（id={seen_prescription_id}），"
                f"但第 {week} 周不在它的微周期内：current_week 返回 None"
                f"（那一天早于生成日、或已经过了最后一周）。"
                f"⚠️ 这一档通常意味着**该换处方了**（spec §5.2 触发 3），"
                f"而不是「这个学生这一周没练」"
            )
        else:
            reason = (
                f"学生 {student_id} 的处方（id={seen_prescription_id}）在第 {week} 周"
                f"有生效的周次，但那些周次的训练日与这一周的 7 天**一天都不重叠**"
                f"（处方周与学期周错位，例如处方是在这一周之后才生成的）"
            )
    return {
        "student_id": student_id,
        "semester_id": semester_id,
        "week": week,
        "completion_rate": rate,
        "numerator": numerator,
        "denominator": denominator,
        "expected_days": expected,
        "completed_days": completed_days,
        "prescription_id": seen_prescription_id,
        "prescription_week": prescription_week,
        "paused": paused,
        "reason": reason,
    }


@router.post(
    "/api/mini-tests/batch",
    tags=["mini-tests"],
    response_model=MiniTestBatchResult,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def batch_mini_tests(
    payload: list[MiniTestEntryCreate],
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict:
    """（教师）按教学班**批量录入**二次小测（spec §8.1：「教师确认并批量录入
    （按教学班列出学生逐个填）」）。

    ⚠️ **逐条独立**（``SAVEPOINT`` / ``session.begin_nested()``）：一行撞唯一键
    只让**那一行**回滚，其余照常入库，而失败清单点名 ``index`` 与 ``student_id``。
    教师一次提交三四十行，其中一行「这个学生这周已经录过了」不该让整批作废
    ——那会逼他自己找出是哪一行、删掉、再提交一次，而 ``failed`` 本来就能告诉他。
    ⚠️ ``begin_nested()`` 是必需的、不是装饰：SQLite 在一条 INSERT 失败后，
    **同一个事务**里的后续写入会一直撞 ``PendingRollbackError``，
    而 SAVEPOINT 把回滚范围限制在这一行。

    ⚠️ **HTTP 状态恒为 200**（含全部失败）：派单逐字要求的是「``207``-风格 ……
    HTTP 状态仍是 ``200``」。不用真的 ``207 Multi-Status``（WebDAV 的码，
    前端的 fetch 封装普遍把非 2xx 当错误分支，而「39 行成功 1 行重复」不是一次失败的
    请求）。⚠️ 代价：**全部失败也是 200**，故前端必须读 ``failed`` 的长度、
    不能只看状态码。已登记为关切。

    ⚠️ ``entered_by`` 取 ``X-Teacher-Staff-No``；``normalized_score`` 留 ``NULL``
    （两者都不在请求模型上，理由见 :class:`MiniTestEntryCreate` 与本模块 docstring
    的「刻意不做」第 3 条）。
    """
    require_teacher(session, staff_no)
    created = 0
    failed: list[dict] = []
    for index, entry in enumerate(payload):
        try:
            with session.begin_nested():
                session.add(MiniTest(
                    student_id=entry.student_id,
                    semester_id=entry.semester_id,
                    week=entry.week,
                    item_combo=list(entry.item_combo),
                    squat_30s_count=entry.squat_30s_count,
                    shuttle_20m_s=entry.shuttle_20m_s,
                    # ⚠️ 留 NULL：读侧现算（本模块 docstring 的「刻意不做」第 3 条）
                    normalized_score=None,
                    tested_on=entry.tested_on,
                    entered_by=staff_no,
                ))
            created += 1
        except IntegrityError as exc:
            # ⚠️ 用 exc.orig（DBAPI 的原始消息）而不是 str(exc)：后者带完整 SQL 与
            #    绑定参数，回给前端等于把 schema 与数据一起送出去
            #    （与 app.api.errors 的 IntegrityError 处理器同一条纪律）。
            origin = getattr(exc, "orig", None)
            failed.append({
                "index": index,
                "student_id": entry.student_id,
                "message": str(origin) if origin is not None else "写入被数据库拒绝",
            })
    session.commit()
    return {"created": created, "failed": failed}


@router.get(
    "/api/mini-tests/normalized",
    tags=["mini-tests"],
    response_model=NormalizedScoreRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def normalized_scores(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    semester_id: int = Query(description="学期 id（「班内」按这个学期的选课关系定）"),
    week: int = Query(ge=1, description="**学期**周次，与 mini_test.week 同口径"),
) -> dict:
    """**标准化得分**（spec §8.1 的算式）：``深蹲得分 = 次数``、
    ``折返得分 = 班内百分位反查``、``小测综合分 = 两项等权平均``。

    ⚠️ **按教学班分组**：spec 逐字是「**该教学班内**折返秒数的百分位反查」，
    而一个学生同一学期**可能在两个班**（阶段一的行政班与阶段二的分层班并存），
    那时他在两个班里各有一行、百分位各不相同。平铺成一张学生表就会丢掉
    「这个分是相对谁算的」。

    ⚠️ **不在任何教学班的学生进 ``unassigned``、不给分数**：「班内百分位」对他
    **无定义**，而三种候选处置（当成一个人的班 → 他会拿到 50.0；给 0 → 把「不知道」
    讲成「最差」；点名报出来）里只有第三种不撒谎，且它顺带把「选课记录漏了一条」
    这个**要修的数据问题**摆到教师面前。

    ⚠️ **``shuttle_20m_s IS NULL`` 的行不进百分位样本**：一个「没测」的人若被当成
    「最慢的那个」，会把全班的百分位一起往下拽（所有人都变好）。它自己的
    ``shuttle_score`` 与 ``composite`` 都是 ``null``，而 ``squat_score`` 照常给。

    ⚠️ ``composite`` 用**未 round 的**百分位算完再 round（:data:`SCORE_PRECISION`
    的注释逐字写了 ``56.665`` 那个浮点坑）。⚠️ **量纲是混的**（次数 vs 百分位），
    如实记录在 :class:`NormalizedEntryRead` 的 docstring 里。
    """
    require_teacher(session, staff_no)
    rows = session.scalars(
        select(MiniTest).where(
            MiniTest.semester_id == semester_id, MiniTest.week == week
        )
    ).all()
    sections_of: dict[int, set[int]] = defaultdict(set)
    for row in session.execute(
        select(Enrollment.student_id, Enrollment.course_section_id).where(
            Enrollment.semester_id == semester_id
        )
    ).all():
        sections_of[row.student_id].add(row.course_section_id)

    by_section: dict[int, list] = defaultdict(list)
    unassigned: list[dict] = []
    for row in rows:
        sections = sections_of.get(row.student_id)
        if not sections:
            unassigned.append({"student_id": row.student_id, "mini_test_id": row.id})
            continue
        for section_id in sections:
            by_section[section_id].append(row)

    scored: list[dict] = []
    for section_id in sorted(by_section):
        group = by_section[section_id]
        sample = [row.shuttle_20m_s for row in group if row.shuttle_20m_s is not None]
        entries = []
        for row in sorted(group, key=lambda item: item.student_id):
            squat = (
                None if row.squat_30s_count is None else float(row.squat_30s_count)
            )
            raw_shuttle = (
                None if row.shuttle_20m_s is None
                else _shuttle_percentile(row.shuttle_20m_s, sample)
            )
            entries.append({
                "student_id": row.student_id,
                "mini_test_id": row.id,
                "squat_score": squat,
                "shuttle_score": (
                    None if raw_shuttle is None else round(raw_shuttle, SCORE_PRECISION)
                ),
                # ⚠️ 任一项缺失 → 综合分也是 null（把 null 当 0 会让这个学生的综合分
                #    变成「另一项的一半」，那是一句关于他的假话）
                "composite": (
                    None if squat is None or raw_shuttle is None
                    else round((squat + raw_shuttle) / 2, SCORE_PRECISION)
                ),
            })
        scored.append({
            "course_section_id": section_id,
            "scored_count": len(sample),
            "entries": entries,
        })
    return {
        "semester_id": semester_id,
        "week": week,
        "sections": scored,
        "unassigned": unassigned,
    }
