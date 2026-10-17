"""请求审计留痕：**「记与不记」的唯一判据** + 中间件 + 那一行的写入方（Plan 06 Task 5）。

行本身是 :class:`app.db.models.audit.AuditLog`；本模块是**唯一**写它的地方
（:func:`record` 一行 ``INSERT``，全仓没有任何一处 ``UPDATE`` / ``DELETE`` 这张表），
故「一次请求在审计里长什么样」这件事只有一个住址——与 :mod:`app.auth.sessions`
之于 ``user_session`` 是同一个形状。

--------------------------------------------------------------------------
⚠️⚠️ 判据只有一条：**HTTP 方法**（派单 §1 第 2 条：「记与不记的判据只住在一个函数里」）
--------------------------------------------------------------------------

:func:`should_record` 是那条判据的**唯一**住址，它的全部内容就是
``method.upper() in AUDITED_METHODS``（``POST`` / ``PATCH`` / ``DELETE``）。

派单还要求「**外加** ``POST /api/auth/login`` / ``logout`` / 两个 ``bind``」，并当场注明
「它们本就是 POST，故自然覆盖 —— **核实**，不要写第二份判据」。**核实结果（实读
``app/api/routers/auth.py`` 的五个装饰器）**：

==================================  ======  ==========================
路径                                  方法    被本判据覆盖？
==================================  ======  ==========================
``POST /api/auth/students/bind``     POST    ✓（装饰器 ``@router.post``）
``POST /api/auth/teachers/bind``     POST    ✓（同上）
``POST /api/auth/login``             POST    ✓（同上）
``POST /api/auth/logout``            POST    ✓（同上）
``GET  /api/auth/me``                GET     ✗ **刻意不记**（它是读）
==================================  ======  ==========================

于是四个鉴权事件**全部**落在同一条方法判据里，本模块**没有**第二份「路径白名单」。
⚠️ 这正是派单要的形状：若写成「方法 ∈ {POST,PATCH,DELETE} **或** 路径 ∈ {login,
logout, bind…}」，那么下一个人加一个 ``POST /api/auth/refresh`` 时要记得改**两处**，
而漏掉的那一处是**静默**的（新端点照样工作，只是审计里少一行）。

--------------------------------------------------------------------------
⚠️⚠️ **读（GET）一律不记**（派单 §1 第 2 条，实现者复核后维持）
--------------------------------------------------------------------------

派单 §4 把「『GET 一律不记』是否该给管理台的读也记」列为本波最可能的顶回之一。
实现者**核过、不顶回**，三条理由：

1. **体量**：本仓 103 个操作里 **64** 个是 GET（``/openapi.json`` 实测；
   ⚠️ 这两个数是**时点快照**，会随端点增删而漂 —— 确切的五格由
   ``frontend/scripts/smoke.mjs`` 现场数 ``/openapi.json``，本处只是给「GET 占多数」
   这个论断一个可对账的基准）。前端一屏
   学生详情就打出 5–8 个 GET，教师大屏更多；把读也记上，``audit_log`` 的增长率会从
   「每天几百行」变成「每天几万行」，而它是**单调增长**的（清理任务自 Plan 08 Task 2
   起有了：``scripts/retention.py``，⚠️ 而它**不会自己跑**；
   :class:`app.db.models.audit.AuditLog` 的模块 docstring 第一节）。
2. **噪声淹没信号**：运维问的那一句是「谁**改**了什么」。把那 64 个 GET
   （其中 **15** 个还是**匿名**的参考数据读）也记进来，答案里 95% 的行与那个问题无关。
   ⚠️ 改前这一句写的是「44 个匿名参考数据 GET」—— 那是 Plan 05A **安全收紧波之前**
   的数（当时 48 个匿名 GET 被裁定成 44 匿名 + 4 仅教职），收紧之后匿名 GET 只剩 15 个，
   而这个数没人跟着改（终审 S4-6 的同族）。
3. ⚠️ **而「谁读了谁的档案」这一问确实答不了**——那是本条口径的**真实代价**，
   如实记录（硬规矩 #39）：安全收紧波之后学生键资源一律要身份，故「一个教师翻了
   哪些学生的健康档案」今天**不在审计里**。要补的话正确的做法是**另开一张表**
   （读审计的留存期与写审计不同，且它要的是聚合而不是逐行），不是把 GET 塞进本表。
   已登记为待清扫，并写进 spec §13 的已知局限。

--------------------------------------------------------------------------
⚠️⚠️ **不记请求体**（隐私纪律；派单 §1 第 3 条）
--------------------------------------------------------------------------

逐字理由与「为什么它是**结构性质**而不是『中间件里克制住不写』」住在
:mod:`app.db.models.audit` 的模块 docstring 第三节（那张表**没有**能装请求体的列）。
本模块因此**从来不读** ``request.body()`` / ``await request.json()``：
⚠️ 那不只是隐私问题——``BaseHTTPMiddleware`` 下读掉请求体会让下游端点拿不到它
（除非用 Starlette 的 ``_CachedRequest`` 重放），故「不读体」同时是一条正确性纪律。
守卫是 ``tests/api/test_audit_api.py`` 的
``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
（真发一次带口令的 login，然后把那一行的**全部 9 列**逐列扫一遍）。

--------------------------------------------------------------------------
⚠️ 「谁做的」从 ``request.state`` 取，**不在中间件里再解析一次会话**
--------------------------------------------------------------------------

:func:`note_subject` 是唯一往 ``request.state`` 上写那一格的口子，**四个**调用方：

* :func:`app.api.deps._resolve_cookie_identity` —— cookie 那一档的**唯一**收口
  （四个身份依赖都经它），故「带 cookie 的写」只在这里记一次；
  ⚠️ 它也顺带解决了 ``logout``：``current_session`` 在**吊销之前**就把身份存下来了，
  否则登出那一行会变成 ``anonymous``（会话已经 ``revoked_at``，事后再解析必然是 ``None``）。
* :func:`app.api.deps.current_student` 与 :func:`app.api.deps.current_teacher` 的
  **请求头**那两支（过渡通道 ``PE_ALLOW_HEADER_IDENTITY=1``）。
  ⚠️ **生产档下这一支不可达**（请求头被完全忽略），而它**必须**存在：否则开发档与
  全部 1426 条测试里的写操作会被记成 ``anonymous``，那是一句关于「谁做的」的假话。
  ⚠️ :func:`app.api.deps.current_reader` **刻意不在里面**：它的三个消费者
  （泛型 list / 泛型 read-one / ``GET /api/mini-tests/normalized``）**全是 GET**，
  而 GET 一律不记（模块 docstring 第二节）——给它也加一句就是死代码。
* :func:`app.api.routers.auth.login` 的**成功**那一档（登录时还没有 cookie 可解析，
  而口令与学号都在请求体里、本模块不读体，故只有端点自己知道是谁）。

⚠️ **为什么不在中间件里自己 ``resolve`` 一次**：那会给每个带 cookie 的写请求**多一次**
:func:`app.auth.sessions.resolve`——而那个函数末尾**自己 commit**（滑动过期），
于是同一个请求会写两遍 ``user_session``。走 ``request.state`` 的代价是**零次**额外查询
（身份本来就要解析一次才能过闸门）。

⚠️ **失效方向**：一个既没有 cookie、也没有请求头、也没有登录成功的写请求
→ ``request.state`` 上那一格不存在 → :func:`subject_of_request` 回
:data:`ANONYMOUS_SUBJECT`（``subject_kind='anonymous'``）。**鉴权失败因此照样有一行**
（派单 §1 第 4 条）：那正是「谁在撞门」的唯一可见性——:mod:`app.auth.policy` 的锁定档
故意不回显「还剩几次 / 是不是被锁了」，故没有本表的话，一次撞门在系统里**没有任何痕迹**。

--------------------------------------------------------------------------
⚠️ 审计写不下去时**不让业务请求失败**（如实记）
--------------------------------------------------------------------------

:func:`record` 抛出去的话（库被写锁占住、磁盘满），``dispatch`` 会把它按
``ERROR`` 记进日志、然后**照常把响应发出去**。理由：那一刻业务写入**已经 commit 了**
（端点自己 commit，:func:`app.api.deps.get_db` 刻意不 commit），把它折成一个 500
会让客户端以为「没写进去」并重试——那是比「审计少一行」严重得多的一次谎报。
⚠️ 代价：审计是**尽力而为**的，不是「写不进去就拒绝服务」的强一致审计。
要后者的话得把审计写进**业务事务**里（同一个 Session、同一次 commit），
那会让每个端点都多一次耦合，超出本 Task 的范围。已登记为待清扫。
"""
from __future__ import annotations

import dataclasses
import logging

from fastapi import FastAPI, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.auth import sessions as auth_sessions
from app.db import width as db_width
from app.db.models.audit import ANONYMOUS_SUBJECT_KIND, AuditLog

__all__ = [
    "ANONYMOUS_SUBJECT",
    "AUDITED_METHODS",
    "SUBJECT_STATE_KEY",
    "AuditMiddleware",
    "AuditSubject",
    "install_audit",
    "note_subject",
    "record",
    "should_record",
    "subject_of_request",
    "target_of",
]

_LOGGER = logging.getLogger(__name__)

#: **被审计的方法**。⚠️ 它是「哪些请求会留痕」这件事在全仓的唯一字面量住址，
#: 而判据本身在 :func:`should_record`（派单 §1 第 2 条：判据只住在一个函数里）。
#: ⚠️ ``GET`` / ``HEAD`` / ``OPTIONS`` / ``PUT`` 都**不在**里面：前三个是读与预检
#: （理由见模块 docstring 第二节），``PUT`` 本仓一个端点都没有（改一律走 ``PATCH``，
#: :func:`app.api.crud.build_crud_router` 只注册 POST / PATCH / DELETE）。
AUDITED_METHODS = frozenset({"POST", "PATCH", "DELETE"})

#: ``request.state`` 上那一格的名字。⚠️ 字面量只有这一处：写入方
#: （:func:`note_subject`）与读取方（:func:`subject_of_request`）都从本常量取。
SUBJECT_STATE_KEY = "audit_subject"


@dataclasses.dataclass(frozen=True)
class AuditSubject:
    """「这一次请求是谁做的」的三格。**frozen**：它挂在 ``request.state`` 上被
    多个依赖与端点先后读到，可变化会让「端点改了自己的身份」成为一件在类型上可能的事
    （与 :class:`app.auth.sessions.Identity` 同一条口径）。

    ⚠️ **它刻意不是** :class:`app.auth.sessions.Identity`（五格）：``Identity`` 带
    ``name`` 与 ``role``，而审计**一行都不需要它们**——``name`` 是随时会改的人话
    （:class:`app.auth.sessions.Identity` 的 docstring 逐字写了「会话行上刻意不存它」），
    ``role`` 已经在 ``user_session`` 上、且审计要的是「当时是谁」而不是「当时是什么角色」。
    少两格 = 少两处「顺手也存下来」的诱惑，而 :class:`app.db.models.audit.AuditLog`
    的 9 列里本来就没有能装它们的位置。
    """

    #: ``student`` / ``teacher`` / ``anonymous``（取值域 =
    #: :attr:`app.db.models.audit.AuditLog.SUBJECT_KINDS`）。
    kind: str
    #: ``student.id`` / ``teacher.id``；匿名档为 ``None``。
    subject_id: int | None = None
    #: 工号；**只教职那一档填**（理由见 ``AuditLog.staff_no`` 那一列的注释）。
    staff_no: str | None = None


#: 「没有身份」那一档。**同一个对象**被复用（``frozen`` 故安全），于是
#: 「匿名」在审计里是一个可辨识的常量而不是每次新造的等价实例。
ANONYMOUS_SUBJECT = AuditSubject(kind=ANONYMOUS_SUBJECT_KIND)


def should_record(method: str) -> bool:
    """**这一次请求要不要留一行审计**——全仓唯一的判据（派单 §1 第 2 条）。

    ⚠️ 它**只看方法**，不看路径、不看身份、不看响应码。四条后果逐条都是要的：

    * ``POST /api/auth/login`` 的**失败**档也记（401 / 403 / 423 一律照记）：
      「谁在撞门」全在 4xx 里；
    * ``GET /api/audit-logs`` 自己**不记**（它是 GET）：否则管理员每翻一页审计
      就往审计里加一行，那张表会自己喂自己；
    * 一个**不存在的路径**上的 POST 也记（404）：探测行为正是审计要的东西；
    * ``OPTIONS`` 预检不记（浏览器发的、与任何人的意图无关）。

    ⚠️ ``method.upper()``：ASGI 的 ``scope["method"]`` 恒为大写
    （Starlette 不做归一化，而 HTTP 的方法令牌本身区分大小写），故那一格今天
    是**许可**而不是断言（硬规矩 #39）。留着它的理由是「直接调本函数的测试可以写
    ``should_record("post")``」，而失效方向是安全的（一个真发出来的小写方法
    在 ASGI 层就不存在）。
    """
    return method.upper() in AUDITED_METHODS


def note_subject(request: Request, subject: AuditSubject) -> None:
    """把「这一次请求是谁做的」记在 ``request.state`` 上，给中间件事后取。

    ⚠️ **它是那一格的唯一写入口**（六个调用方逐个见模块 docstring 第五节）。
    ⚠️ 走 ``request.state`` 而不是模块级全局：后者在并发下会被另一个请求覆盖，
    而 ``request.state`` 的后端是 ``scope["state"]``（每个请求一份），
    故同一个 scope 上的中间件与端点看到的是同一格、而不同请求互不干扰。
    """
    setattr(request.state, SUBJECT_STATE_KEY, subject)


def subject_of_request(request: Request) -> AuditSubject:
    """取 :func:`note_subject` 存下的那一格；**没存过就是匿名**。

    ⚠️ 「没存过」的三档：① 真的没有身份（鉴权失败 → 正是派单 §1 第 4 条要的那一行）；
    ② 这个端点根本不要身份（例如匿名可打的 ``POST /api/auth/students/bind``）；
    ③ 有人建了一个新的写入端点而没经过那六个调用点里的任何一个。
    ⚠️ 第 ③ 档是**静默**的（审计里会多出一批 ``anonymous`` 行，而它们本该有名有姓）。
    已如实记录（硬规矩 #39）：要堵住它得让「身份」与「审计主体」在类型上不可分
    （例如让身份依赖**返回** :class:`AuditSubject`），那是一次全仓签名改动，
    不在本 Task 的范围里。
    """
    return getattr(request.state, SUBJECT_STATE_KEY, None) or ANONYMOUS_SUBJECT


def target_of(request: Request) -> str | None:
    """``target`` 那一格：**路径里恰好一个参数**时取它的原文，否则 ``None``。

    ⚠️⚠️ **派单 §4 顶回 ③ 当场裁定了来源**：「**不要解析响应体**（要缓冲响应，代价大），
    从路径模板取即可，取不到就空」。实现者复核后**同意**，并补两条实测理由：

    1. **缓冲响应体在 ``BaseHTTPMiddleware`` 下是有代价的**：``call_next`` 回的是一个
       ``_StreamingResponse``，要读体就得把它整个消费掉再重新包一个 ``Response``——
       于是每个写请求的响应都在内存里多一份拷贝，而 ``POST /api/pipeline/run-daily``
       的响应体是**整份批处理报告**（实测几十 KB）。
    2. **体里的 id 也不是唯一真相**：``POST /api/students`` 回的是整个新建的行
       （21 列），要从里面挑出「哪个是 target」就得给每个资源写一份映射——
       那是 23 份口径，而路径参数只有**一份**（``scope["path_params"]``）。

    ⚠️ 于是**「恰好一个」而不是「取最后一个」**：今天全部特例端点与泛型端点的路径
    里最多只有一个占位符（实测 ``/openapi.json`` 的 **75** 个路径模板；⚠️ 改前这里写的是
    71 = Plan 06 Task 9 时点的数，此后加了 ``/api/mini-tests/normalized/me`` 与
    ``/api/teacher/students/{id}/normalized`` 等，没人跟着改 ⇒ 终审 S4-6），故两档在今天
    等价；写「恰好一个」的理由是失效方向——将来真出现一个两段占位的路径
    （``/api/students/{sid}/prescriptions/{pid}``）时，「取最后一个」会**静默**地把
    ``pid`` 记成 target（而读的人以为是学生 id），本函数则记 ``None``（少一格，
    但不说谎）。⚠️ 那一档今天不可达，故它是许可而不是断言（硬规矩 #39）。

    ⚠️ **存的是字符串原文**：``scope["path_params"]`` 的值是 Starlette 的
    ``str`` convertor 产出的**未转换**串（``"12"`` 而不是 ``12``），而列是
    ``String(64)``。故本函数**不做 ``int()``**：一个格式错的 id（``PATCH
    /api/students/abc``）在端点里是 422，而它在审计里仍然要被记成「有人对 ``abc``
    试了一次写」——转成 ``int`` 会当场抛、于是那一行**没了**。
    """
    params = request.scope.get("path_params") or {}
    if len(params) != 1:
        return None
    value = next(iter(params.values()))
    return None if value is None else str(value)


def record(
    engine: Engine,
    *,
    method: str,
    path: str,
    status: int,
    subject: AuditSubject,
    target: str | None,
) -> None:
    """写**一行**审计并 commit。⚠️ 它是全仓唯一写 ``audit_log`` 的函数。

    ⚠️ **自己开一个 ``Session``、自己 commit**：调用方是中间件，它手里没有请求那个
    ``Session``（那一个在响应发出之前就已经被 :func:`app.api.deps.get_db` 关掉了，
    FastAPI 0.106 起「带 yield 的依赖」的退出码在响应发出**之前**跑）。
    与 :func:`app.auth.sessions.issue` / ``revoke`` 同一条口径：**审计行必须在响应
    发出之前落库**，否则一个崩溃在响应途中的进程会留下「做了但没记」的空档。

    ⚠️ ``at`` 取 :func:`app.auth.sessions.now`（naive **本地**时刻）——本表刻意不用
    UTC，逐字理由见 :class:`app.db.models.audit.AuditLog` 的 ``at`` 那一列。

    ------------------------------------------------------------------
    ⚠️⚠️ **三个客户端可控的串在这里被收成有界**（Plan 06 Task 12 / C1）
    ------------------------------------------------------------------

    本函数是全仓唯一写 ``audit_log`` 的地方，故它同时是「这张表的三个客户端可控列
    不许超宽」这**唯一**一个可以设防的位置。逐格（宽度一律从模型上读，
    经 :func:`app.db.width.declared_width`，本处一个数字都不写）：

    * ``path`` ← ``request.url.path``（**匿名可控**：一条 400 字符的 URL 就够）
      → :func:`app.db.width.truncate`（**截断 + 可辨识标记**）。
      ⚠️ 截断**不毁掉这一格的用途**（派单点名要核这一件）：一条超长路径的信息全在
      **前**半段（``/api/students/12`` 那一截），而标记是**尾缀**，故读的人既看得见
      打的是哪个端点、也看得见「这里被切过」。⚠️ 而不设防的后果不是「PG 上报错」
      这么轻：本模块的失效方向是「审计写不下去**不让业务请求失败**」（下面那一段），
      故一次超宽写入在 PG 上表现为**这一行审计静默消失** = 攻击者可控的审计缺失。
    * ``target`` ← ``scope["path_params"]`` 的原文（同样匿名可控）→ 同上截断。
    * ``staff_no`` ← 开发档的 ``X-Teacher-Staff-No`` **请求头原文**
      （:func:`app.api.deps.current_teacher` 在 ``require_staff`` **之前**就调了
      :func:`note_subject`，故一个不在册的超长工号也会走到这里）
      → :func:`app.db.width.overlong_sentinel`（**哨兵、不截断**）。
      ⚠️ 这一格刻意与上面两格**不同档**：``staff_no`` 是「**指认一个人**」的列，
      截断它会得到一个**看着像真工号的假工号**（那是一句假话），
      而哨兵 ``<over:400>`` 是一句实话、并且保住了「原文有多长」这一格。
      逐字理由见 :func:`app.db.width.overlong_sentinel`。
      ⚠️ 生产档下这一支**不可达**（请求头通道被 :func:`app.api.deps.allow_header_identity`
      强制关，cookie 那一档的 ``staff_no`` 恒来自名册行 ⇒ 已经受
      ``teacher.staff_no`` 的声明宽度约束）；⚠️ 而它**必须**设防，因为开发档与
      全部测试跑的就是请求头那一档，且「不可达」是一个**环境变量的距离**。

    ⚠️ 另两格**不在这里设防**，因为它们**已经**有判据（派单要求先实测有没有校验）：

    * ``method`` —— :func:`should_record` 那道方法闸门是它的校验：``dispatch`` 只在
      ``method.upper() in AUDITED_METHODS`` 时才走到本函数，故写进来的恒是
      ``POST`` / ``PATCH`` / ``DELETE`` 三者之一（最长 6，声明 8）。
      ⚠️ 实测取证：一个 400 字符的方法令牌打过来得到 **405**、审计行**一行都不多**
      （``tests/api/test_column_widths.py``）。⚠️ 故本列**刻意不截断**：
      截一个方法名只会造出一个不存在的方法，而「哪些方法被记」的唯一所有者是
      :func:`should_record`（:class:`app.db.models.audit.AuditLog.method` 那一列的
      注释逐字写了为什么本列连 CHECK 都没有）。
    * ``subject_kind`` —— 取值域是 :attr:`AuditLog.SUBJECT_KINDS`（三档，最长
      ``anonymous`` = 9，声明 16），且有 DB 层的 ``ck_audit_log_subject_kind`` 兜底。

    ⚠️ 于是「每一格客户端可控的列都有界」这件事在本表上是**三档处置**、
    而不是一个统一动作，而这三档的**判据**（域内最长值 ≤ 声明宽度）由
    ``tests/api/test_column_widths.py`` 逐列量（期望侧从模型读，不硬编码）。

    ⚠️ **本函数不吞异常**：吞不吞是调用方（:class:`AuditMiddleware`）的决定，
    理由逐字写在模块 docstring 最后一节。
    """
    columns = AuditLog.__table__.c
    with Session(engine) as session:
        session.add(
            AuditLog(
                at=auth_sessions.now(),
                subject_kind=subject.kind,
                subject_id=subject.subject_id,
                staff_no=db_width.overlong_sentinel(
                    subject.staff_no, db_width.declared_width(columns.staff_no)
                ),
                method=method.upper(),
                path=db_width.truncate(path, db_width.declared_width(columns.path)),
                status=status,
                target=db_width.truncate(
                    target, db_width.declared_width(columns.target)
                ),
            )
        )
        session.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    """把 :func:`should_record` 认下的那些请求，在**响应出来之后**记一行。

    ⚠️ **为什么是 ``BaseHTTPMiddleware`` 而不是裸 ASGI**：本中间件要的是
    「响应码」这一格，而 ``BaseHTTPMiddleware`` 的 ``call_next`` 直接给一个带
    ``status_code`` 的 ``Response``；裸 ASGI 要自己截 ``http.response.start`` 消息。
    ⚠️ 代价是它会把下游跑在一个单独的 anyio 任务里（Starlette 的实现），
    而本仓的响应全是 JSON、没有流式端点，故那份代价今天为零。

    ⚠️⚠️ **「响应之后」是承重的**，两格理由：① ``status`` 只有事后才知道；
    ② :func:`target_of` 读的 ``scope["path_params"]`` 是**路由匹配之后**才有的
    （匹配发生在下游），故事前取到的恒为空字典、``target`` 会**恒为 ``None``**。

    ⚠️ **判据在 ``call_next`` 之前就跑**（第一行那个 ``if``）：不该记的请求
    （全部 GET）**一次 ``request.state`` 都不碰、一个 ``Session`` 都不开**，
    于是 63 个 GET 端点的开销是**零**（⚠️ 改前写的是 60，同上面那两格的漂移）。

    ⚠️ **``except`` 那一支记 500**：一个没被任何处理器接住的异常会**穿过**本中间件
    （Starlette 的 ``ServerErrorMiddleware`` 在 user middleware **之外**，
    而 :mod:`app.api.errors` 那个兜底 500 处理器正是挂在它上面的），
    故不 ``try`` 的话「写操作炸了」这一档在审计里**一行都没有**——
    而那恰恰是最该留痕的一档。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """一次请求：判据 → 放行 → 记一行。

        ⚠️ 两个类型标注都来自 Starlette 的**公有**名字
        （``starlette.middleware.base.RequestResponseEndpoint`` / ``starlette.responses.Response``，
        实测 starlette 1.7.0 两个都在），故本模块不碰任何 ``_`` 前缀的私有形状
        ——⚠️ 这一点与 :mod:`app.api.routers` 的模块 docstring 里那条
        「``_IncludedRouter`` 是私有类型，换版本可能就不在了」是同一份警惕。
        """
        if not should_record(request.method):
            return await call_next(request)
        try:
            response = await call_next(request)
        except Exception:
            self._write(request, 500)
            raise
        self._write(request, response.status_code)
        return response

    @staticmethod
    def _write(request: Request, status: int) -> None:
        """调 :func:`record`；**写不下去就按 ``ERROR`` 记日志、不让请求失败**。

        ⚠️ 逐字理由见模块 docstring 最后一节。⚠️ 那条日志**带上路径与响应码**，
        故「审计少了一行」这件事在日志里是**可查的**（不是静默的）——
        失效方向从「静默丢审计」变成「响亮的 ERROR + 丢审计」。
        """
        try:
            record(
                request.app.state.engine,
                method=request.method,
                path=request.url.path,
                status=status,
                subject=subject_of_request(request),
                target=target_of(request),
            )
        except Exception:  # noqa: BLE001  ⚠️ 刻意宽：见上面那段
            _LOGGER.exception(
                "审计行写不下去（%s %s → %s）：业务响应照常发出，而这一行**丢了**。"
                "常见成因是库被写锁占住或磁盘满；请查 app.api.audit 的这一段日志。",
                request.method,
                request.url.path,
                status,
            )


def install_audit(application: FastAPI) -> None:
    """把 :class:`AuditMiddleware` 挂上。⚠️ **它是唯一的挂载点**（:func:`app.main.create_app`）。

    ⚠️ **它必须在 :func:`app.main._install_cors` 之前被调**：``add_middleware`` 是
    **插到 ``user_middleware`` 的最前面**，而 Starlette 建栈时
    ``user_middleware[0]`` 是**最外层**。故先挂审计、后挂 CORS 的结果是
    **CORS 在外、审计在内**——那正是想要的两格：

    1. 跨源预检（``OPTIONS``）在 CORS 那一层就被回答，根本不进来
       （⚠️ 就算进来也不记：``OPTIONS`` 不在 :data:`AUDITED_METHODS` 里）；
    2. 审计看到的响应**已经带上了 CORS 头**，而它记的 ``status`` 与浏览器收到的
       那个是同一个（反过来挂的话，一个被 CORS 拦下的响应在审计里会是 200，
       而浏览器那边是失败——两格对不上，运维会去查一个不存在的问题）。

    ⚠️ 它**刻意不影响** :func:`app.main._selfcheck_prod`：那一道自检只数
    ``CORSMiddleware`` 的项（``entry.cls is not CORSMiddleware: continue``），
    故多一层审计中间件在生产档上既不触发它、也不被它挡住。
    ⚠️ 而「审计在**两档**下都工作」（派单 §0 那条 ⚠️）因此是构造上的：
    本模块**一个环境变量都不读**，故 ``PE_ENV`` 是 ``dev`` 还是 ``prod``
    对「记不记、记什么」没有任何影响。守卫是 ``tests/api/test_audit_api.py`` 的
    ``test_the_audit_trail_is_written_in_both_deployment_tiers``。
    """
    application.add_middleware(AuditMiddleware)
