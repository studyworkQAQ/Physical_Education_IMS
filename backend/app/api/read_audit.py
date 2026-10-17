"""**敏感读**留痕：「这一条 GET 算不算一次要记的读」的**唯一判据** + 中间件 + 写入方
（Plan 08 Task 1）。

行本身是 :class:`app.db.models.audit.ReadAuditLog`；本模块是**唯一**写它的地方
（:func:`record_read` 一行 ``INSERT``，全仓没有任何一处 ``UPDATE`` / ``DELETE`` 这张表）。
它与 :mod:`app.api.audit` 是**同族的两个模块**，各管一张表：

======================  ==================================  ==================================
                        :mod:`app.api.audit`                 本模块
======================  ==================================  ==================================
表                      ``audit_log``（9 列）                ``read_audit_log``（9 列）
记什么                  三个**写**方法 + 登录/绑定            **敏感读**（46 个 GET）
判据的唯一所有者        :func:`app.api.audit.should_record`   :func:`is_sensitive_read`
判据看什么              **只看 HTTP 方法**                    **只看路由模板**（+ 主体有没有名字）
======================  ==================================  ==================================

⚠️ **两个判据刻意不复用、也不互相引用**：它们答的是两个不同的问题，而把它们合成一个
（例如「方法 ∈ {POST,PATCH,DELETE} **或** 路径 ∈ 那 46 个」）会造出
:mod:`app.api.audit` 的模块 docstring 第二节逐字警告过的那个失效形态——
「加一个新端点时要记得改**两处**，而漏掉的那一处是**静默**的」。
⚠️ 于是本模块**不 import** :data:`app.api.audit.AUDITED_METHODS`，
:mod:`app.api.audit` 也**不 import** :data:`READ_ROUTES`。
⚠️ 而两族**共用**的三格（「谁做的」那一格的存取、``target`` 的取法、
「审计写不下去不让业务请求失败」那一条失效方向）一律**从 :mod:`app.api.audit` 复用**，
本模块一份都不抄：

* :func:`app.api.audit.subject_of_request` / :func:`app.api.audit.note_subject`
  / :class:`app.api.audit.AuditSubject` —— 「这一次请求是谁做的」的**唯一**存取口；
* :func:`app.api.audit.target_of` —— 「恰好一个路径参数时取它的原文」那一条裁定；
* ``_write`` 的 ``except`` 那一支与 :class:`app.api.audit.AuditMiddleware._write`
  逐字同形（含那条响亮的 ``ERROR`` 日志）。

--------------------------------------------------------------------------
⚠️⚠️ 判据一：**只记敏感读，不记全部 GET**（计划 §1 第 1 条，控制者裁定）
--------------------------------------------------------------------------

理由逐字是计划给的：全部 GET 会把 ``health`` / ``docs`` / 静态资源 / 前端轮询都记进去，
**量级会淹掉真正要看的那几行**，而甲方要的是「谁翻过谁的档案」。

实测口径（``/openapi.json``，本 Task 亲跑）：全仓 **64** 个 GET 里
**46 记 / 18 不记**。⚠️ 这两个数是**时点快照**，会随端点增删而漂——而
「它不许悄悄落后于路由」由 ``tests/api/test_read_audit_api.py`` 的
:func:`~tests.api.test_read_audit_api.test_every_get_route_is_classified_exactly_once`
钉住（期望侧取自 ``app.openapi()["paths"]``、被测侧是 :data:`READ_ROUTES` 的字面量，
两侧**不同源**，硬规矩 #35）。

--------------------------------------------------------------------------
⚠️⚠️ 判据的形状：**一张「路由模板 → 归类」的表**（派单 §2 第 3 条，实现者的取舍）
--------------------------------------------------------------------------

派单给了三个候选（``Depends(...)`` / 路径表 / 装饰器）并让实现者选一个、说明取舍。
**选的是路径表**，三条理由，前两条是决定性的：

1. ⚠️ **另两个候选的失效方向是静默的**。``Depends(...)`` 与装饰器都要**每个端点自己挂**，
   于是「加了一个读端点而忘了挂」在结构上**完全可能**、且**一声不响**
   （新端点照样工作，只是审计里少一行）。要堵住它就必须再写一条守卫去遍历路由、
   检查每个端点有没有挂那个依赖——而那条守卫遍历的**正是** ``app.openapi()["paths"]``，
   与一张路径表的守卫**逐字同一个形状**。既然守卫躲不掉，那就让**判据本身**也是那张表：
   一处字面量、一条守卫，而不是「N 个装饰器 + 一条遍历守卫」两份口径。
   ⚠️ 这正是派单逐字点名的失效形态：「不许每个 router 各自判（那是 N 个所有者，
   加一个端点就漏一个）」。
2. ⚠️ **它把「63 个 GET 逐个过一遍」这件事变成一个可以一次读完的物件**。
   计划 §1 第 2 条要求的是「实现者要自己从 openapi 的 63 个 GET 里挑并**逐个说明理由**」，
   而一个 ``Depends`` 挂在 46 个端点上时，「哪 46 个」这件事在全仓**没有任何一处**能一次看到
   （要 grep 46 次）。:data:`READ_ROUTES` 是一张 64 行的表，配上 :data:`READ_CLASSES`
   的 10 条归类理由，一屏读完。
3. **代价（如实记，硬规矩 #39）**：表与路由之间是**两份字面量**，故它们会漂。
   漂移有两个方向，都被同一条守卫抓住：① 加了端点没进表 → 守卫报「未归类」；
   ② 表里有一个已经不是路由的模板 → 守卫报「已不存在」。⚠️ 而
   ``Depends`` 那一档**不会**漂（它挂在端点上，端点删了它也没了）——
   这是那一个候选唯一的真优势，而它换来的是第 1 条那个静默失效。取舍记在这里。

⚠️ **归类理由住在 :data:`READ_CLASSES`（10 条），不住在 64 行里**：64 行里写 64 句
散文的话，同族的理由会被抄十几遍，而抄十几遍的东西一定会漂（本仓已踩过四次同族，
见 :mod:`app.api.routers.catalog` 的模块 docstring）。⚠️ 于是「某一条路径为什么记/不记」
这个问题有**两段**答案：它是哪一类（:data:`READ_ROUTES`，一眼可查）+ 那一类为什么
（:data:`READ_CLASSES`，一处住址）。⚠️ 而 64 行**逐条**的完整表格（含每条一句话理由）
住在本 Task 报告的 §2 与 spec §13.9。

--------------------------------------------------------------------------
⚠️⚠️ 判据二：**主体必须有名字**（匿名读一律不记；派单 §2 第 10 条 ③ 要的裁定）
--------------------------------------------------------------------------

:func:`is_sensitive_read` 只管路径那一半；另一半在
:class:`ReadAuditMiddleware._write` 里：``subject.kind == 'anonymous'`` 就**直接返回**。
两半合起来才是完整判据，⚠️ 而它们**刻意不住在同一个函数里**——路径那一半是
「这张表管哪些端点」（一份可以一次读完的数据），主体那一半是「什么样的读值得记」
（一条规则）。

裁定与三条理由：

1. **本表存在的理由是答「谁翻过谁的档案」**，而一行 ``subject_kind='anonymous',
   subject_id=NULL`` 答不出「谁」。它不是一格信息，是一格噪声。
2. ⚠️ **今天这一档在 46 个敏感读上不可达**（实测：46 个全部要身份，匿名一律 **401**），
   故它是**许可而不是断言**（硬规矩 #39）——留着它的理由是失效方向：
   将来某个敏感读被放开成匿名可读时，那一格**必须**不记（否则表里会出现一批
   答不出「谁」的行），而那时它会真的被走到。
3. ⚠️ **它与写审计的那一条口径刻意相反**，而相反是对的：``audit_log`` **要**匿名的行
   （:data:`app.api.audit.ANONYMOUS_SUBJECT_KIND` 的注释逐字写着「鉴权失败的请求也要记，
   否则『谁在撞门』恰恰查不到」）。差别在于**撞门是一个动作**（一次失败的登录尝试
   本身就是一格事实），而**一次被 401 挡掉的读什么也没发生**（没有数据被披露）。
   ⚠️ 而「已登录的人试了一次范围外的读」（**403**）**要记**——那一档有名字，
   逐字理由见 :class:`app.db.models.audit.ReadAuditLog` 的 ``status`` 那一列。

⚠️ **结构性的第二道闸**：``read_audit_log.subject_kind`` 的取值域是
:data:`app.db.models.audit.READ_SUBJECT_KINDS`（**两档**，``anonymous`` 不在里面），
且有 DB 层的 ``ck_read_audit_log_subject_kind`` 兜底。于是「把判据放宽到匿名也记」
这个改动会先撞上一条 ``IntegrityError``（500）——**响**，而不是静默灌一批无主的行。

--------------------------------------------------------------------------
⚠️⚠️ 裁定：**学生读自己的档案也记、教师读自己任教班的学生也记**（派单 §2 第 9 条）
--------------------------------------------------------------------------

控制者裁定「都记」，实现者复核后**同意、不顶回**，三条理由：

1. **判据里没有「是不是自己」这一维，是刻意的**。要加就得在中间件里比对
   ``subject.subject_id`` 与 ``student_id_of(request)``——而那对 46 个敏感读里的
   **21 个**根本不成立（名册、班级聚合、审计页身上没有「某一个学生」），
   于是「自己翻自己」会变成一个只对一部分端点生效的例外。
   ⚠️ 一个只对一半对象生效的例外，就是一个下一个人一定会读错的判据。
2. ⚠️ **「自己翻自己」是一格真事实，而且它恰恰是绑定/抢绑那一族要看的东西**
   （计划 §0 第 4 条：未绑定账号可被抢绑，而验身材料对教职都是已知的）。
   一次「学生 4 读了学生 4 的档案」在正常情况下每次登录都会发生若干次；
   **异常**的是它发生在不该发生的时候（例如一个刚被抢绑的账号第一次登录就会
   把自己那份档案翻一遍）。把它滤掉等于把这条线索也滤掉。
3. **代价（如实记）**：表会更大。学生端一屏 ``StudentHome`` 打出 3–4 个敏感读，
   60 个学生各翻一次就是 200 行左右。⚠️ 处置不是「不记」，而是**留存窗口更短**
   （计划 §2：读审计 90 天、写审计不少于 1 年），那是 Task 2 的清理 CLI 要兑现的一格。

⚠️ 守卫是 ``tests/api/test_read_audit_api.py`` 的
:func:`~tests.api.test_read_audit_api.test_a_student_reading_his_own_file_is_recorded`
（学生读自己 → **恰好一行**、``subject_kind='student'``、``student_id`` = 他自己）与
:func:`~tests.api.test_read_audit_api.test_a_teacher_reading_his_own_section_is_recorded`。

--------------------------------------------------------------------------
⚠️⚠️ **同步写、不做异步**（派单 §2 第 11 条，实现者复核后同意控制者的倾向）
--------------------------------------------------------------------------

:func:`record_read` 与 :func:`app.api.audit.record` 同一条口径：**自己开一个
``Session``、自己 commit、在响应发出之前落库**。派单点名了「异步/批量」这条备选并
注明「异步会引入『审计可能丢』的失效方向」。实现者复核后**同意同步**，并补一条实测理由：

* 本仓是**单进程 uvicorn + SQLite**，一次 ``INSERT`` 的实测代价是**亚毫秒**级
  （本 Task 报告 §4 有学生详情页改前改后的实测数字），而「异步」在这一档上要引入
  一个后台任务/一个队列/一次 atexit 冲刷，三件都是新的失效面（进程被杀时队列里的行
  **静默消失**——那正是审计最不该有的失效方向）。
* ⚠️ 而 :mod:`app.api.audit` 已经有一条**如实记下**的代价：审计写不下去时
  **不让业务请求失败**（按 ``ERROR`` 记日志、照常发响应）。本模块**逐字沿用**那一条，
  故「同步」的准确说法是「在响应发出之前**尝试**落库」，不是「落不下去就拒绝服务」。
  要后者得把审计写进业务事务里，那会让每个端点都多一次耦合，超出本 Task 范围。

--------------------------------------------------------------------------
⚠️⚠️ **永不落请求体、也永不落查询串**（隐私纪律；派单 §2 第 6 条）
--------------------------------------------------------------------------

逐字理由与「为什么它是**结构性质**」住在 :mod:`app.db.models.audit` 的模块 docstring
第三节（那两张表**都没有**能装请求体的列）。本模块因此**从来不读**
``request.body()`` / ``await request.json()``。⚠️ 读审计比写审计**多一条**：

* **查询串也不落**。``route`` 那一列存的是**路由模板**
  （``/api/students/{student_id}``），不是 ``request.url.path``、更不是
  ``str(request.url)``。⚠️ 而这一格在读审计上**尤其**承重：泛型 list 的过滤一律走
  查询串（``GET /api/body-compositions?student_id=4``），而查询串是**客户端可控的
  自由文本**（``?anything=<任意串>``）。存 ``str(request.url)`` 等于给这一族开一个
  无界的、可注入的列。
* ⚠️ **代价（如实记）**：于是「他按什么条件筛的」这一格查不到，只查得到
  「他翻了哪一类档案、哪一个学生（若路径里有）」。要补的话正确的做法是**白名单**
  那几个过滤键（``student_id`` / ``course_section_id``），而不是把整条查询串存下来。
  已登记为待清扫。

守卫（**照 :mod:`app.api.audit` 那两条的姿势，不写第二套判据**）：
``tests/api/test_read_audit_api.py`` 的
``test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either``
（**真发**一次带请求体 + 带探针查询串的敏感读，然后把落库那一行的**全部 9 列**逐列扫一遍）
与 ``test_no_read_audit_schema_mentions_a_credential_or_a_body``（结构侧）与
``test_the_read_audit_module_never_reads_the_request_body``（AST：本文件里没有任何
``.body()`` / ``.json()`` / ``.form()`` / ``.stream()``）。

--------------------------------------------------------------------------
⚠️ 本模块刻意不做的事
--------------------------------------------------------------------------

* **不给任何 router 加东西**：46 个敏感读端点**一个字节都没改**（判据在中间件里，
  不在端点上——那正是上面第 2 节那个取舍要的形状）；
* **不进 ``app.db.models`` 的公有导入面**：写入方要写
  ``from app.db.models.audit import ReadAuditLog``（Ruling 97 / 硬规矩 #102，
  逐字理由见 :mod:`app.db.models` 的 ``__all__`` 上方那段注释）；
* **不带 ``batch_id``**：它不是管道产物（``_BATCH_OWNED_TABLES`` 按集合相等判，
  故本表必须不在那九张里）；
* **不是 :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源**：它的读端点
  ``GET /api/read-audit-logs`` 是一个**手写的特例端点**（仅 ``role='admin'``），
  与 ``GET /api/audit-logs`` **同一条口径**（派单 §2 第 8 条的裁定），
  住在同一个 router 模块 :mod:`app.api.routers.audit` 里。
"""
from __future__ import annotations

import dataclasses
import logging

from fastapi import FastAPI, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.audit import (
    AuditSubject,
    subject_of_request,
    target_of,
)
from app.auth import sessions as auth_sessions
from app.db import width as db_width
from app.db.models.audit import ANONYMOUS_SUBJECT_KIND, ReadAuditLog

__all__ = [
    "READ_CLASSES",
    "READ_ROUTES",
    "STUDENT_ID_PATH_PARAM",
    "ReadAuditMiddleware",
    "ReadClass",
    "install_read_audit",
    "is_sensitive_read",
    "record_read",
    "route_of",
    "student_id_of",
]

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ReadClass:
    """一类 GET 的**归类**：记不记 + 一句话理由。**frozen**：它被 64 行共享，
    可变化会让「某一行偷偷把自己改成敏感/不敏感」在类型上成为可能。"""

    #: 记不记。⚠️ 它是 :func:`is_sensitive_read` 读的**唯一**一格。
    sensitive: bool
    #: 一句话理由。⚠️ 它**只给人读**（守卫按 ``sensitive`` 判、不按理由判），
    #: 而它住在这里而不是住在 64 行的行内注释里，理由逐字见模块 docstring 第 2 节第 2 条。
    reason: str


#: **10 条归类**。⚠️ 前 6 条 ``sensitive=True``（记），后 4 条 ``False``（不记）。
#:
#: ⚠️ **它是「为什么记/不记」这件事在全仓的唯一住址**：:data:`READ_ROUTES` 的 64 行
#: 只说「这一条路径属于哪一类」，理由一律指回本表。⚠️ 加第 11 类之前请先读
#: 模块 docstring 第 2 节——「63 个 GET 逐个过一遍」是本件的验收面，
#: 而新加一类等于承认有一族此前被归错了。
READ_CLASSES: dict[str, ReadClass] = {
    # ---------------------------------------------------------------- 记（46）
    "PER_STUDENT_HEALTH": ReadClass(
        True,
        "逐人的健康/测评/处方/反馈数据：体成分、体测原始值 + 6 项得分、派生指标"
        "（含 body_comp_abnormal）、分层 label + hit_rules、处方整行、周调整、"
        "训练打卡（含 feeling）、课堂快评 RPE、二次小测、预警（level + trigger_snapshot）、"
        "站内信（标题 + 正文）、兴趣问卷（逐人自由作答）。"
        "⚠️ 这一类正是甲方试用说明书 §6 那一句「谁翻过谁的档案」指的东西。",
    ),
    "PER_STUDENT_VIEW": ReadClass(
        True,
        "某一个具体学生的**聚合视图**：学生首页、周训练单、当前处方、打卡完成率、"
        "本人小测综合分、本人站内信、教师端的「某个学生」三格。"
        "⚠️ 路径里恒有 ``{student_id}``（``normalized/me`` 是唯一例外：它恒取会话里的那个人），"
        "故 ``student_id`` 那一列在这一类上**恒有值**。",
    ),
    "STUDENT_ROSTER": ReadClass(
        True,
        "**全校名册**：``/api/students`` 那一行含 ``birth``（⚠️ 而 ``birth`` 正是自助绑定的"
        "验身材料，计划 §0 第 4 条），``/api/enrollments`` 那一行是「谁在哪个班」。"
        "⚠️ 一次请求就摊出 60 个人，故它比逐人读**更**该留痕。",
    ),
    "CLASS_AGGREGATE": ReadClass(
        True,
        "**班级级**聚合而**内含逐人数据**：班级大屏、班级周报（``progress_board`` 那个 JSON 列"
        "逐条带 ``student_id`` + ``change_pct``）、班内百分位（逐人三个分数）。"
        "⚠️ ``student_id`` 那一列在这一类上是 ``NULL``（路径里没有那一段），"
        "故本表答得出「谁翻过**这个班**的档案」、答不出「翻到了班里哪几个人」"
        "——如实记为已知局限（要答后者得把 ``progress_board`` 拆子表，spec §1.2 第 18 条）。",
    ),
    "STAFF_ROSTER": ReadClass(
        True,
        "**教职名册**：``TeacherRead`` 含 ``staff_no`` **与** ``name``，而那两格合起来正是"
        "``POST /api/auth/teachers/bind`` 的**全部**验身材料（逐字理由住在"
        "``app/api/routers/catalog.py`` 的 ``teachers`` 那一行）。"
        "⚠️ 于是「谁把教职名册翻了一遍」与「谁把学生名册翻了一遍」是同一族问题。",
    ),
    "AUDIT_TRAIL": ReadClass(
        True,
        "**审计页本身**：``GET /api/audit-logs`` 与 ``GET /api/read-audit-logs``。"
        "⚠️ 记它兑现的是 :mod:`app.api.audit` 模块 docstring 里那条**如实记下**的代价"
        "（「『谁看过审计』今天查不到」）与 ``app/api/routers/audit.py`` 末节那一条。"
        "⚠️ **代价（如实记）**：读审计页会往读审计表里加一行，即它**自己喂自己**。"
        "那一格是**要的**（「谁看过审计」正是本类存在的理由），而它有界"
        "（一次翻页一行、只有 ``role='admin'`` 打得到），处置是 Task 2 的 90 天留存窗口。",
    ),
    # --------------------------------------------------------------- 不记（18）
    "REFERENCE_DATA": ReadClass(
        False,
        "**群体/参考数据，一行学生键都没有**（7 个资源的集合 GET + 成员 GET = 14 条）："
        "学期、班级、体测批次、百分位快照（群体统计，实测 14 列一个学生键都没有）、"
        "动作库、处方模板、课次。⚠️ 逐行的判断依据住在"
        "``app/api/routers/catalog.py`` 那 7 行的 ``read_scope: None`` 注释里，"
        "本处不抄第二份。⚠️ 它们**全部匿名可读**，故就算记也答不出「谁」。",
    ),
    "OPS_PROBE": ReadClass(
        False,
        "存活探针 ``GET /api/health``：它回三格计数（``status`` / ``tables`` / ``students``），"
        "**不含任何一个人的任何数据**；⚠️ 而它被 ``scripts/tunnel.ps1`` 每 **60 秒**打一次、"
        "被 ``smoke.mjs`` 四档各打若干次、被前端 ``App.vue`` 每次加载打一次 —— "
        "记它等于用**每分钟一行**的速率往一张含个人健康数据的表里灌无主的行。",
    ),
    "SELF_SESSION": ReadClass(
        False,
        "会话自证 ``GET /api/auth/me``：它只回**请求者自己**那五格（``kind`` / ``login`` /"
        "``name`` / ``role`` / ``subject_id``），**结构上不可能**披露别人的任何数据"
        "（``subject_id`` 恒取自会话）。⚠️ 而它是本仓**调用频率最高**的一个 GET"
        "（前端每一次路由守卫都打一次），故记它 = 把「谁打开了页面」记成「谁翻了档案」，"
        "量级会当场淹掉那 46 条。⚠️ **它与「学生读自己也记」那条裁定不冲突**："
        "那一条说的是**档案**（健康/身份数据），本条说的是**会话回显**（登录态自证）。",
    ),
    "CLASS_TOKEN_OPS": ReadClass(
        False,
        "课次级快评口令与其开关：``rpe-status``（那一节课的快评开了没）与 ``rpe-token``"
        "（教师念给学生的一次性口令）。⚠️ 两格的键都是 ``{class_session_id}``、"
        "**不含任何学生键**，故它们答不出「谁的档案」。⚠️ **如实记一格取舍**："
        "``rpe_token`` 是一格**秘密**（拿到它就能替全班交快评），故「谁读过它」"
        "看着像是该记的；本表**不记**它，理由是它是**一次写的前置**而不是**一次读的产物**"
        "——学生随后那一次 ``POST /api/rpe-records`` **在 ``audit_log`` 里有一行**"
        "（三个写方法之一），故那条链在写审计那侧是完整的。⚠️ 要单独记「谁领了口令」"
        "得给它一个自己的类，已登记为待清扫。",
    ),
}

#: 路径参数里代表「哪一个学生」的那一段的**名字**。⚠️ 字面量只有这一处：
#: :func:`student_id_of` 与那条守卫都从本常量取。
#: ⚠️ 它与 :data:`app.api.crud.StudentOwner` 的 ``column="student_id"`` 是**两件事**：
#: 那一格说的是「这张**表**的学生键在哪一列」，本格说的是「这条**路由**的路径参数叫什么」。
#: 两者今天恰好同名（泛型 read-one 的 ``pk_alias`` 与特例端点的路径段都用 ``student_id``），
#: 而它们**可以**不同名（``/api/weekly-adjustments/{weekly_adjustment_id}`` 的学生键
#: 是间接的），故本模块**不从那一格推**。
STUDENT_ID_PATH_PARAM = "student_id"

#: **64 行「路由模板 → 归类」**。⚠️ 它是「这一条 GET 算不算一次要记的读」这件事
#: 在全仓的**唯一**字面量住址，而判据本身在 :func:`is_sensitive_read`。
#:
#: ⚠️⚠️ **它是 :func:`app.api.audit.should_record` 的对偶，而不是它的补充**：
#: 那一个只看方法（三个写方法），本表只看路由模板（46 个敏感读）。
#: 两者**互不引用**，故「加一个端点」只可能是**一处**改动
#: （写端点 → 自动被方法判据覆盖；读端点 → **必须**进本表，否则守卫当场红）。
#:
#: ⚠️ **顺序按路径字典序**（与 ``/openapi.json`` 的 ``paths`` 同序），故
#: 「本表与 openapi 的那 64 个 GET 逐条对拍」是一次可以肉眼做完的事。
#: ⚠️ 而**键必须逐字等于** ``app.openapi()["paths"]`` 的键（= ``APIRoute.path``）：
#: 一个手滑写成 ``/api/students/{id}`` 的键会让守卫报「已不存在」+「未归类」两格。
READ_ROUTES: dict[str, str] = {
    "/api/alerts": "PER_STUDENT_HEALTH",
    "/api/alerts/{alert_id}": "PER_STUDENT_HEALTH",
    "/api/audit-logs": "AUDIT_TRAIL",
    "/api/auth/me": "SELF_SESSION",
    "/api/body-compositions": "PER_STUDENT_HEALTH",
    "/api/body-compositions/{body_composition_id}": "PER_STUDENT_HEALTH",
    "/api/class-sessions": "REFERENCE_DATA",
    "/api/class-sessions/{class_session_id}": "REFERENCE_DATA",
    "/api/class-sessions/{class_session_id}/rpe-status": "CLASS_TOKEN_OPS",
    "/api/class-sessions/{class_session_id}/rpe-token": "CLASS_TOKEN_OPS",
    "/api/course-sections": "REFERENCE_DATA",
    "/api/course-sections/{course_section_id}": "REFERENCE_DATA",
    "/api/dashboard/class/{course_section_id}": "CLASS_AGGREGATE",
    "/api/dashboard/weekly-class-report/{course_section_id}": "CLASS_AGGREGATE",
    "/api/derived-metrics": "PER_STUDENT_HEALTH",
    "/api/derived-metrics/{derived_metric_id}": "PER_STUDENT_HEALTH",
    "/api/enrollments": "STUDENT_ROSTER",
    "/api/enrollments/{enrollment_id}": "STUDENT_ROSTER",
    "/api/exercises": "REFERENCE_DATA",
    "/api/exercises/{exercise_id}": "REFERENCE_DATA",
    "/api/fitness-test-batches": "REFERENCE_DATA",
    "/api/fitness-test-batches/{fitness_test_batch_id}": "REFERENCE_DATA",
    "/api/fitness-test-results": "PER_STUDENT_HEALTH",
    "/api/fitness-test-results/{fitness_test_result_id}": "PER_STUDENT_HEALTH",
    "/api/health": "OPS_PROBE",
    "/api/interest-surveys": "PER_STUDENT_HEALTH",
    "/api/interest-surveys/{interest_survey_id}": "PER_STUDENT_HEALTH",
    "/api/mini-tests": "PER_STUDENT_HEALTH",
    "/api/mini-tests/normalized": "CLASS_AGGREGATE",
    "/api/mini-tests/normalized/me": "PER_STUDENT_VIEW",
    "/api/mini-tests/{mini_test_id}": "PER_STUDENT_HEALTH",
    "/api/notifications": "PER_STUDENT_HEALTH",
    "/api/notifications/{notification_id}": "PER_STUDENT_HEALTH",
    "/api/percentile-snapshots": "REFERENCE_DATA",
    "/api/percentile-snapshots/{percentile_snapshot_id}": "REFERENCE_DATA",
    "/api/prescription-templates": "REFERENCE_DATA",
    "/api/prescription-templates/{prescription_template_id}": "REFERENCE_DATA",
    "/api/prescriptions": "PER_STUDENT_HEALTH",
    "/api/prescriptions/{prescription_id}": "PER_STUDENT_HEALTH",
    "/api/read-audit-logs": "AUDIT_TRAIL",
    "/api/rpe-records": "PER_STUDENT_HEALTH",
    "/api/rpe-records/{rpe_record_id}": "PER_STUDENT_HEALTH",
    "/api/semesters": "REFERENCE_DATA",
    "/api/semesters/{semester_id}": "REFERENCE_DATA",
    "/api/stratification-results": "PER_STUDENT_HEALTH",
    "/api/stratification-results/{stratification_result_id}": "PER_STUDENT_HEALTH",
    "/api/students": "STUDENT_ROSTER",
    "/api/students/{student_id}": "STUDENT_ROSTER",
    "/api/students/{student_id}/home": "PER_STUDENT_VIEW",
    "/api/students/{student_id}/notifications": "PER_STUDENT_VIEW",
    "/api/students/{student_id}/prescriptions/current": "PER_STUDENT_VIEW",
    "/api/students/{student_id}/training-logs/completion-rate": "PER_STUDENT_VIEW",
    "/api/students/{student_id}/weekly-sheet": "PER_STUDENT_VIEW",
    "/api/teacher/students/{student_id}/home": "PER_STUDENT_VIEW",
    "/api/teacher/students/{student_id}/normalized": "PER_STUDENT_VIEW",
    "/api/teacher/students/{student_id}/weekly-sheet": "PER_STUDENT_VIEW",
    "/api/teachers": "STAFF_ROSTER",
    "/api/teachers/{teacher_id}": "STAFF_ROSTER",
    "/api/training-logs": "PER_STUDENT_HEALTH",
    "/api/training-logs/{training_log_id}": "PER_STUDENT_HEALTH",
    "/api/weekly-adjustments": "PER_STUDENT_HEALTH",
    "/api/weekly-adjustments/{weekly_adjustment_id}": "PER_STUDENT_HEALTH",
    "/api/weekly-class-reports": "CLASS_AGGREGATE",
    "/api/weekly-class-reports/{weekly_class_report_id}": "CLASS_AGGREGATE",
}


def is_sensitive_read(route: str) -> bool:
    """**这一条 GET 要不要留一行读审计**——全仓唯一的判据（派单 §2 第 3 条）。

    ⚠️ 它**只看路由模板**，不看方法、不看身份、不看响应码：

    * **方法**由调用方保证（:class:`ReadAuditMiddleware.dispatch` 的第一行只对 ``GET``
      放行）。⚠️ 于是本函数**不**再判一次方法：判两次的失效形态是
      「有人给它传了一个 POST 的模板、而它答 True」——那不会发生（写端点的模板
      与读端点的模板在本仓**从不重叠**：泛型工厂为同一个 ``path`` 注册的
      POST/PATCH 与 GET 共用模板，⚠️ 而 ``dispatch`` 已经先按方法挡掉了）。
      ⚠️ 如实记一格：``/api/students/{student_id}`` 这一个模板**同时**是
      GET（记）与 PATCH/DELETE（走写审计）的路由，故「模板 → 敏感度」这一张表
      只对 **GET** 有意义，而「只对 GET」这一半住在中间件里、不住在本函数里。
    * **身份**由 :class:`ReadAuditMiddleware._write` 判（匿名不记，逐字理由见
      模块 docstring 第 3 节）。⚠️ 两半**刻意分开**：路径那一半是一份可以一次读完的
      数据，主体那一半是一条规则。
    * **响应码**一律无感：``403`` 也记（一个已登录的人试了一次范围外的读，
      逐字理由见 :class:`app.db.models.audit.ReadAuditLog` 的 ``status`` 那一列）。

    ⚠️ **不在表里的模板一律 ``False``**（``.get`` 的缺省档）：那一档今天在
    生产路径上**不可达**（守卫钉住了「表 == openapi 的全部 GET」），故它是
    **许可而不是断言**（硬规矩 #39）。留着它的失效方向是安全的：
    一个刚加进来、还没归类的读端点**不记**（少一行，守卫会红），
    而不是**误记**（多一行，没人发现）。
    """
    key = READ_ROUTES.get(route)
    return key is not None and READ_CLASSES[key].sensitive


def route_of(request: Request) -> str | None:
    """这一次请求落在**哪一个路由模板**上；没匹配上就 ``None``。

    ⚠️ **必须在 ``call_next`` 之后调**：``scope["route"]`` 是 Starlette 的
    ``Router.__call__`` 在**匹配成功时**才写进去的，而匹配发生在下游。
    这与 :func:`app.api.audit.target_of` 读 ``scope["path_params"]`` 是同一条约束
    （那一格的逐字理由住在 :class:`app.api.audit.AuditMiddleware` 的 docstring 里，
    本处不抄第二份）。

    ⚠️ **取 ``.path`` 而不是 ``.path_format``**：本仓没有一个路由用 Starlette 的
    类型转换器（``{student_id:int}`` 一类），故两者今天**逐字相同**；
    取 ``.path`` 的理由是它**逐字等于** ``app.openapi()["paths"]`` 的键，
    于是「表与路由对拍」那条守卫不需要任何归一化。⚠️ 而这一格是**许可而不是断言**：
    将来真有人写了 ``{id:int}``，``.path`` 与 ``.path_format`` 会分岔
    （后者是 ``{id}``），而 :data:`READ_ROUTES` 的键要跟着 ``.path`` 写。

    ⚠️ **``None`` 的两档**：① 404（没有任何路由匹配）；② 一个非 ``APIRoute``
    的东西（``Mount``，本仓只有 SPA 那一个静态挂载）。两档都**不记**——
    而那一格对 ① 是**要的**：一条 400 字符的探测 URL 在写审计里有一行
    （:func:`app.api.audit.should_record` 对路径无感），在读审计里**没有**，
    因为读审计记的是「翻了**哪一类**档案」，而一个不存在的路径不属于任何一类。
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else None


def student_id_of(request: Request) -> int | None:
    """``student_id`` 那一格：**路径参数里恰好有一段叫 ``student_id``** 时取它。

    ⚠️ **来源只有路径参数**，两档**刻意不取**（逐字理由见模块 docstring 第 6 节）：

    * **不解析响应体**——与 :func:`app.api.audit.target_of` 同一条裁定
      （派单 §4 顶回 ③ 当场裁定的：要缓冲整个响应，代价大）。⚠️ 于是
      ``/api/body-compositions/{id}`` 这一类**行键**端点的 ``student_id`` 是 ``NULL``，
      而「哪个学生」要一次 JOIN 才答得出来。如实记为已知局限，
      与 ``audit_log.target`` 对 ``POST /api/students`` 的那一格局限**同族**。
    * **不读查询串**——查询串是客户端可控的自由文本（``?anything=<任意串>``），
      落进一个 ``Integer`` 列要先 ``int()``、于是一个格式错的值会当场抛；
      而「他按什么条件筛的」这一格本来就不在本表的列清单里。

    ⚠️ **``int()`` 失败回 ``None``、不抛**：``GET /api/students/abc`` 在端点里是
    **422**（``int`` 转不出来），而它在读审计里**仍然要有一行**
    （``route`` = 模板、``target`` = ``"abc"`` 原文、``student_id`` = ``NULL``）——
    「有人拿一个非数字 id 试读学生档案」正是该留下来的一行。
    ⚠️ 这与 :func:`app.api.audit.target_of` 的 ``str(value)`` **刻意不 ``int()``**
    是同一条失效方向的两种写法：那一格存字符串故不需要转，本格存整数故必须转、
    而转不出来时**降级**（少一格）而不是**丢行**（少一行）。
    """
    params = request.scope.get("path_params") or {}
    raw = params.get(STUDENT_ID_PATH_PARAM)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def record_read(
    engine: Engine,
    *,
    route: str,
    status: int,
    subject: AuditSubject,
    student_id: int | None,
    target: str | None,
) -> None:
    """写**一行**读审计并 commit。⚠️ 它是全仓唯一写 ``read_audit_log`` 的函数。

    ⚠️ **自己开一个 ``Session``、自己 commit**，逐字同 :func:`app.api.audit.record`
    的那一段（调用方是中间件，它手里没有请求那个 ``Session``；而审计行必须在响应
    发出之前落库）。⚠️ ``at`` 取 :func:`app.auth.sessions.now`（naive **本地**时刻）
    ——两张审计表**同一个时钟所有者**，故运维把它们按时间对齐着看时不会差 8 小时。

    ------------------------------------------------------------------
    ⚠️⚠️ **两个客户端可控的串在这里被收成有界**（照 Plan 06 Task 12 / C1 的姿势）
    ------------------------------------------------------------------

    逐格（宽度一律从模型上读，经 :func:`app.db.width.declared_width`，本处一个数字都不写）：

    * ``target`` ← ``scope["path_params"]`` 的原文（**匿名可控**）
      → :func:`app.db.width.truncate`（与 ``audit_log.target`` **同档**）。
    * ``staff_no`` ← 开发档的 ``X-Teacher-Staff-No`` **请求头原文**
      → :func:`app.db.width.overlong_sentinel`（与 ``audit_log.staff_no`` **同档**：
      截一个工号会得到一个**看着像真工号的假工号**，而哨兵是一句实话）。
    * ``route`` ← ``scope["route"].path``（**服务端**产物，故它今天**不可控**）
      → ⚠️ **仍然过一遍** :func:`app.db.width.truncate`。这是**深度防御**，
      与 ``audit_log.staff_no`` 那一格同一条理由（「不可达是一个环境变量的距离」）：
      本函数是全仓唯一写这张表的地方，故它是「这张表的每一个字符串列都有界」
      这件事**唯一**可以设防的位置。

    ⚠️ 另三格**不在这里设防**，因为它们**已经**有判据：

    * ``subject_kind`` —— 取值域是 :data:`app.db.models.audit.READ_SUBJECT_KINDS`
      （**两档**，最长 ``student`` = 7，声明 16），且有 DB 层的
      ``ck_read_audit_log_subject_kind`` 兜底；
    * ``subject_id`` / ``student_id`` —— ``int``。⚠️ ``subject_id`` **可空**
      （教职走请求头那一档只填 ``staff_no``，逐字理由见
      :attr:`app.db.models.audit.ReadAuditLog.subject_id` 的列注释）；
      ⚠️ 而「匿名不进本表」那一道闸是 ``subject_kind`` 上的
      ``ck_read_audit_log_subject_kind``（**两档**），不是 ``subject_id IS NOT NULL``；
    * ``status`` —— ``int``，来自 ``response.status_code``。

    ⚠️ **本函数不吞异常**：吞不吞是调用方（:class:`ReadAuditMiddleware`）的决定，
    理由逐字写在 :mod:`app.api.audit` 模块 docstring 最后一节（本处**沿用**、不抄第二份）。
    """
    columns = ReadAuditLog.__table__.c
    with Session(engine) as session:
        session.add(
            ReadAuditLog(
                at=auth_sessions.now(),
                subject_kind=subject.kind,
                subject_id=subject.subject_id,
                staff_no=db_width.overlong_sentinel(
                    subject.staff_no, db_width.declared_width(columns.staff_no)
                ),
                route=db_width.truncate(route, db_width.declared_width(columns.route)),
                student_id=student_id,
                status=status,
                target=db_width.truncate(
                    target, db_width.declared_width(columns.target)
                ),
            )
        )
        session.commit()


class ReadAuditMiddleware(BaseHTTPMiddleware):
    """把 :func:`is_sensitive_read` 认下的那些 GET，在**响应出来之后**记一行。

    ⚠️ **它与 :class:`app.api.audit.AuditMiddleware` 是两层、不是一层**，而那是**要的**：
    两个判据各管一张表、互不引用（模块 docstring 开头那张表），把它们塞进同一个
    ``dispatch`` 会让「哪些请求会留痕」这件事**又**变成两处（一个 ``if`` 判方法、
    一个 ``if`` 判路径），而那正是 :mod:`app.api.audit` 的模块 docstring 第二节
    逐字警告过的形状。
    ⚠️ **代价（如实记，硬规矩 #39）**：每个 GET 因此多穿一层 ``BaseHTTPMiddleware``
    （Starlette 的实现会把下游跑在一个单独的 anyio 任务里）。本 Task 实测那一格的
    代价（学生详情页改前改后的响应时间）写在报告 §4，而它**没有**被折成异步，
    逐字理由见模块 docstring 第 5 节。

    ⚠️⚠️ **「响应之后」是承重的**，与 :class:`app.api.audit.AuditMiddleware` 同两条理由：
    ① ``status`` 只有事后才知道；② :func:`route_of` 读的 ``scope["route"]`` 是
    **路由匹配之后**才有的（匹配发生在下游），故事前取到的恒为 ``None``、
    **一行都记不下来**。

    ⚠️ **方法判据在 ``call_next`` 之前就跑**（第一行那个 ``if``）：非 GET 的请求
    **一次 ``scope`` 都不读、一个 ``Session`` 都不开**，故 38 个写操作的开销是**零**。
    ⚠️ 而 GET 那一档的「不记」也是**零成本**的：:func:`route_of` 是一次字典读、
    :func:`is_sensitive_read` 是一次字典读 + 一次属性读，18 条不记的路由
    在 ``record_read`` 之前就返回了。

    ⚠️ **``except`` 那一支记 500**：与 :class:`app.api.audit.AuditMiddleware` 逐字同形
    （一个没被任何处理器接住的异常会**穿过**用户中间件，故不 ``try`` 的话
    「读操作炸了」这一档在读审计里一行都没有）。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """一次请求：方法判据 → 放行 → 路径判据 + 主体判据 → 记一行。

        ⚠️ 两个类型标注都来自 Starlette 的**公有**名字，与
        :meth:`app.api.audit.AuditMiddleware.dispatch` 逐字相同
        （那一格的警惕住在它的 docstring 里，本处不抄第二份）。
        """
        if request.method != "GET":
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
        """两道判据（路径 + 主体）→ 调 :func:`record_read`；**写不下去就按 ``ERROR``
        记日志、不让请求失败**（与 :meth:`app.api.audit.AuditMiddleware._write` 逐字同形）。

        ⚠️ **两道判据的先后是承重的**：路径那一半**先**跑，因为它是一次字典读、
        而主体那一半要读 ``request.state``；⚠️ 更重要的是**失效方向**——
        反过来写（先判主体）的话，一个匿名的 404 探测会先走到
        :func:`app.api.audit.subject_of_request`（一次 ``getattr``），
        而那一格在 18 条不记的路由上是白跑的。

        ⚠️ ``ANONYMOUS_SUBJECT_KIND`` **从 :mod:`app.db.models.audit` import**，
        本模块一个字面量 ``"anonymous"`` 都不写（那个常量的注释逐字写着
        「⚠️ **所有者在本模块**」）。⚠️ 而它是**第二道闸**：就算有人把本行删掉，
        ``subject_kind`` 上有 ``ck_read_audit_log_subject_kind``（**两档**，
        不含 ``anonymous``），故一行匿名读会撞成 ``IntegrityError`` →
        被上面那个 ``except`` 按 ``ERROR`` 记进日志 —— **响**，
        而不是静默落一行无主的。
        ⚠️ 那道闸**刻意不是** ``subject_id IS NOT NULL``：后者对
        「教职走请求头」那一档也成立（那一格合法地为 ``NULL``），
        于是它会把一档正常形状一起挡掉。
        """
        route = route_of(request)
        if route is None or not is_sensitive_read(route):
            return
        subject = subject_of_request(request)
        if subject.kind == ANONYMOUS_SUBJECT_KIND:
            return
        try:
            record_read(
                request.app.state.engine,
                route=route,
                status=status,
                subject=subject,
                student_id=student_id_of(request),
                target=target_of(request),
            )
        except Exception:  # noqa: BLE001  ⚠️ 刻意宽：见 app.api.audit 的模块 docstring 末节
            _LOGGER.exception(
                "读审计行写不下去（GET %s → %s）：业务响应照常发出，而这一行**丢了**。"
                "常见成因是库被写锁占住或磁盘满；请查 app.api.read_audit 的这一段日志。",
                route,
                status,
            )


def install_read_audit(application: FastAPI) -> None:
    """把 :class:`ReadAuditMiddleware` 挂上。⚠️ **它是唯一的挂载点**
    （:func:`app.main.create_app`，紧接在 :func:`app.api.audit.install_audit` 之后）。

    ⚠️ **顺序**：``add_middleware`` 是**插到 ``user_middleware`` 的最前面**，
    而 Starlette 建栈时 ``user_middleware[0]`` 是**最外层**。故
    ``install_audit`` → ``install_read_audit`` → ``_install_cors`` 的结果是
    **CORS 在最外、然后读审计、然后写审计**。⚠️ 三格理由：

    1. 跨源预检（``OPTIONS``）在 CORS 那一层就被回答，两层审计都进不来
       （⚠️ 就算进来也不记：``OPTIONS`` 不是 ``GET``，也不在
       :data:`app.api.audit.AUDITED_METHODS` 里）；
    2. 两层审计看到的响应**都已经带上了 CORS 头**，故它们记的 ``status``
       与浏览器收到的是同一个；
    3. ⚠️ **读审计在写审计之外**是**不承重**的（两层各写各的表、互不读取对方的产物），
       故反过来挂也对。选这一个序的理由只是「与 ``install_audit`` 相邻、
       读在写之前」这件事在 :func:`app.main.create_app` 里一眼可读到。

    ⚠️ 它**刻意不影响** :func:`app.main._selfcheck_prod`：那一道自检只数
    ``CORSMiddleware`` 的项（``entry.cls is not CORSMiddleware: continue``），
    故多一层中间件在生产档上既不触发它、也不被它挡住
    （与 :func:`app.api.audit.install_audit` 的同一句话，逐字理由住在那里）。
    ⚠️ 而「读审计在**两档**下都工作」因此是构造上的：本模块**一个环境变量都不读**，
    故 ``PE_ENV`` 是 ``dev`` 还是 ``prod`` 对「记不记、记什么」没有任何影响。
    守卫是 ``tests/api/test_read_audit_api.py`` 的
    ``test_the_read_audit_trail_is_written_in_both_deployment_tiers``。
    """
    application.add_middleware(ReadAuditMiddleware)
