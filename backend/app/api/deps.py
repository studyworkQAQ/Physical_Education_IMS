"""HTTP 层的依赖注入：数据库会话、身份、作用域闸门、分页。

--------------------------------------------------------------------------
⚠️⚠️ **Plan 05A 之后本模块有两条身份通道**（计划 §2.1 的「双通道过渡」）
--------------------------------------------------------------------------

1. **cookie 会话**（``pe_session``）——真实鉴权：首次绑定口令 → 登录 → 服务端
   ``user_session`` 行 → 每次请求解析（含滑动过期与「subject 已删当场吊销」）→ 登出真的失效。
   它是 :func:`current_student` / :func:`current_teacher` / :func:`current_session`
   **先看**的那一条。
2. **请求头**（``X-Student-Id`` / ``X-Teacher-Staff-No``）——⚠️ **过渡态**，
   由 :data:`ALLOW_HEADER_IDENTITY_ENV_VAR` 控制，**生产缺省是关的**：
   没有签名、没有过期、没有吊销，它挡的是「前端把 id 写错就读到别人的数据」这一类
   **事故**，而**不挡**「有人故意伪造请求头」这一类**攻击**（请求头本来就是客户端
   可以随便写的）。

⚠️ **为什么不能直接删掉第 2 条**：既有 **1270 条**测试与前端 ``smoke.mjs`` 的 16 步
全部假设请求头身份，而它们验的是**业务规则**、不是鉴权。删掉它 = 全部重写。
故 ``tests/conftest.py`` 把 ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``"1"``，
1270 条**一条都不用改**；生产缺省 ``"0"`` 由
``tests/api/test_auth_api.py`` 的 ``test_the_header_identity_channel_is_closed_by_default``
钉住（少了那条守卫，「生产忘了设这个变量、于是谁都能伪造请求头」是**静默**的）。
⚠️ **待清扫**：Plan 05A 全部完成（Task 3 的前端登录页落地）之后要把
``backend/scripts/demo.ps1`` 里那个 ``PE_ALLOW_HEADER_IDENTITY=1`` 撤掉，
并在 Task 5 重新裁定那 48 个匿名 GET。

**本模块在依赖图里的位置**（spec §3.3：``api → services → domain``）：``api`` 是最上层，
它可以 import ``app.db`` / ``app.domain`` / ``app.pipeline`` / ``app.refdata*`` /
``app.config`` / ``app.notify``，**反向一律禁止**。守卫是
``tests/architecture/test_layering.py``（Plan 03 Task 1 给它加的 ``api`` 那一层）。
本模块只向下拿两样东西：``app.db.session`` 的 ``Session`` 与
``app.db.models.organisation`` 的四个类（``Student`` / ``Teacher`` /
``CourseSection`` / ``Enrollment``，后两个自 **Plan 03 Task 8** 起被
:func:`require_teaches_section` / :func:`require_teaches_student` 用）——它**不碰 domain**，
因为闸门要判的是「这个 id 在不在册」「这个班是不是他教的」，那是数据库里的事实、
不是领域规则。

**``get_db`` 为什么不提交**：与 ``app.db.repo.upsert`` 的「flush 但不 commit」同口径
（计划 Interfaces 一节逐字要求）。「什么时候算一个工作单元结束了」这件事只有端点知道，
依赖不知道；由依赖提交的话，一个端点里两次写入就没法作为一个整体成功或失败。
"""
import dataclasses
import os
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import APIKeyCookie, APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import Select, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# ⚠️ ``api → auth`` 是许可方向（Plan 05A Task 1 给
# ``tests/architecture/test_layering.py`` 的 ``API_ALLOWED_PREFIXES`` 加了第十一项）。
from app.auth import sessions as auth_sessions
from app.db.models.organisation import CourseSection, Enrollment, Student, Teacher

# ⚠️ **Plan 06 Task 5**：``app.api.audit`` 是同层模块（``app.api`` 那一项许可层内互相依赖），
# 故这一句不需要给 :data:`tests.architecture.test_layering.API_ALLOWED_PREFIXES` 加第十三项。
# ⚠️ **导入方向是 ``deps → audit``、不是反过来**：``app.api.audit`` 只 import
# ``app.auth.sessions`` 与 ``app.db.models.audit``，它**不 import 本模块**
# （它要的是 ``request.state`` 上那一格，而不是身份判定），故无环。
from app.api.audit import AuditSubject, note_subject

# ⚠️ ``api → deploy`` 是 **Plan 06 Task 4** 给那份 allow-list 加的第十二项。
# ⚠️ **这一句刻意写成 ``from app.deploy import is_prod`` 而不是 ``from app import deploy``**：
# 后者在 AST 上是 ``ImportFrom(module="app", level=0)``，
# ``tests/architecture/test_layering.py`` 的 ``_imported_modules`` 对 ``level == 0``
# 只 yield ``node.module``、**不带 names**，故它折出来的是裸串 ``"app"``——
# 而 ``"app"`` 在那份 allow-list 的判定矩阵里是 **RED**（一个已知的假阳性，
# 逐字理由写在 ``test_api_allow_list_matches_on_dot_boundaries`` 最后一格的注释里）。
# 写完整点号串折出来的是 ``"app.deploy"``，命中新增的那一项 → GREEN。
from app.deploy import is_prod

__all__ = [
    "ADMIN_ROLE",
    "ALLOW_HEADER_IDENTITY_DEFAULT",
    "ALLOW_HEADER_IDENTITY_ENV_VAR",
    "NOT_STUDENT_OWNED",
    "SESSION_COOKIE_SCHEME",
    "STAFF_ROLES",
    "STUDENT_ID_SCHEME",
    "TEACHER_STAFF_NO_SCHEME",
    "Page",
    "ReaderIdentity",
    "allow_header_identity",
    "current_reader",
    "current_session",
    "current_student",
    "current_teacher",
    "get_db",
    "require_admin",
    "require_scope",
    "require_staff",
    "require_teaches_section",
    "require_teaches_student",
    "taught_section_ids",
    "taught_student_ids",
    "teacher_id_of",
]

#: ---------------------------------------------------------------------------
#: **Plan 05A Task 2：``role`` 的三个字面值与「谁算教职」**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ 取值域的**唯一所有者是模型类常量**（本包约定 2）：
#: :attr:`app.db.models.organisation.Teacher.ROLES` = ``{"teacher", "admin"}``，
#: 而学生会话的 ``"student"`` 住在 :attr:`app.db.models.auth.UserSession.ROLES`。
#: 本处只给「管理员那一个字面量」与「教职 = 这两个」一个模块内的短名字，
#: 一致性由 ``tests/auth/test_sessions.py`` 的
#: ``test_the_role_vocabulary_of_a_session_is_the_teacher_one_plus_student`` 钉住。
ADMIN_ROLE = "admin"

#: 「在册教职」的取值域。⚠️ 它是 :func:`require_staff` 那道闸门的**第二支**判据：
#: 第一支是「这个工号在不在 ``teacher`` 表里」，第二支是「那一行的 ``role`` 在不在这个
#: 集合里」。⚠️ 第二支今天**恒真**（DB 的 ``ck_teacher_role`` 已经挡住了别的值），
#: 故它是**许可而不是断言**（硬规矩 #39）；把它写出来的理由是「教职是谁」这件事
#: 在 HTTP 层要有一个可读的住址，而不是散在四个端点里各写一遍 ``!= "admin"``。
STAFF_ROLES = frozenset(Teacher.ROLES)

#: ---------------------------------------------------------------------------
#: **P4-A5（前后端对接缺口 1）：两个身份请求头的 OpenAPI ``apiKey`` securityScheme**
#: ---------------------------------------------------------------------------
#:
#: 实测在本 Task 之前：``openapi()["components"]`` 里**没有** ``securitySchemes``、
#: spec 顶层**没有** ``security``、47 个路径里**声明过的 header 参数为空**——
#: 而 ``X-Student-Id`` / ``X-Teacher-Staff-No`` 是全部学生侧端点的必需头。
#: 后果逐字照计划：``/docs`` 的 Swagger UI 上**没有任何地方能填它们**，
#: 而 ``openapi-typescript`` / ``orval`` 一类生成的客户端**也不知道要发**，
#: 于是前端一接就撞 401、且从 spec 上看不出为什么。
#: ⚠️ 用户 2026-10-08 的原话是「要确保后端和前端能够对接的上」，这两个常量就是它的落点。
#:
#: ⚠️⚠️ **``auto_error=False`` 是承重的**：缺省时 ``APIKeyHeader`` 自己会在缺头时抛
#: ``HTTPException(403)``，而本仓「缺身份」的口径是 :func:`current_student` /
#: :func:`current_teacher` 抛的 **401**（``tests/api/test_scope.py`` 的
#: ``test_missing_identity_header_is_401`` 钉住了码与统一错误形状）。留着 ``auto_error``
#: 的话同一个失效会按「谁先跑」给出两个不同的码。故这两个 scheme 只负责**声明**
#: （进 OpenAPI），判定仍由那两个依赖做。
#:
#: ⚠️ ``scheme_name`` 显式写成请求头的字面名：它就是 Swagger「Authorize」弹窗里显示的那个
#: 名字，也是生成的 TS 客户端里那个认证参数的名字。写成头名（而不是 ``studentId`` 一类）
#: 是为了让「要发哪个头」这件事在 UI 上不用猜。两个 scheme 的 ``scheme_name`` **必须不同**，
#: 否则第二个会在 ``components.securitySchemes`` 里覆盖第一个（同名键）。
#:
#: 用法是 ``dependencies=[Security(STUDENT_ID_SCHEME)]``（只声明、不取值）或
#: ``ident: int = Security(STUDENT_ID_SCHEME)``（取值）。⚠️ 本仓的两个端点组
#: （:mod:`app.api.routers.prescription` 的四个）一律走**前者** +
#: :func:`current_student` / :func:`current_teacher`：值要从依赖里出来才能被
#: ``require_scope`` 用上，而 401 的口径也要由那两个函数持有（见上面那条 ⚠️）。
STUDENT_ID_SCHEME = APIKeyHeader(
    name="X-Student-Id",
    auto_error=False,
    scheme_name="X-Student-Id",
    description=(
        "学生身份（学号代理键 student.id 的整数字面量）。⚠️ 原型口径：没有签名、"
        "没有过期、没有吊销，上线前必须换成真实会话。缺头 → 401 unauthenticated；"
        "头存在但不是整数 → 422 request_validation_failed；"
        "与目标数据的所有者不符 → 403 forbidden。"
    ),
)

#: 教师身份。与 :data:`STUDENT_ID_SCHEME` 同一条口径，差别是它是**字符串工号**
#: （``teacher.staff_no``），故「空白」也算缺（见 :func:`current_teacher`）。
TEACHER_STAFF_NO_SCHEME = APIKeyHeader(
    name="X-Teacher-Staff-No",
    auto_error=False,
    scheme_name="X-Teacher-Staff-No",
    description=(
        "教师身份（工号 teacher.staff_no 的字面量）。⚠️ 原型口径同上。"
        "缺头或全空白 → 401 unauthenticated；工号不在 teacher 表里 → 403 forbidden"
        "（require_staff：一条覆盖记录的 teacher_staff_no 是研究数据，"
        "写进一个不存在的工号等于让它作废）。"
    ),
)


#: ---------------------------------------------------------------------------
#: **Plan 05A §2.1：请求头那条通道的开关**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **它住在本模块、不住在 ``app.config``**，理由与 :data:`app.main.DB_URL_ENV_VAR` /
#: :data:`app.api.routers.pipeline.CSV_DIR_ENV_VAR` /
#: :data:`app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR` 逐字相同：
#: ``config.py`` 是全仓依赖图的叶子（只 import :mod:`pathlib`），给它加一个 ``import os``
#: 会改掉那个性质，而它持有的应当是**缺省值**、不是「本层如何在运行时覆盖缺省值」。
#: ⚠️ **计划 §2.1 写的是「``app/config.py`` 加 ``PE_ALLOW_HEADER_IDENTITY``」，
#: 实现者顶回**：那与本仓既有的三处先例、以及 ``config.py`` 自己 docstring 里那句
#: 「本模块不 import :mod:`zoneinfo`…只 import :mod:`pathlib`」直接冲突。
#: 缺省值本身（``"0"``）仍然是字面量、仍然有唯一住址（下面那个常量），
#: 只是「怎么在运行时覆盖它」这件事住在消费者这一侧。
ALLOW_HEADER_IDENTITY_ENV_VAR = "PE_ALLOW_HEADER_IDENTITY"

#: 缺省值 ``"0"`` = **只认 cookie 会话**（生产档）。
#: ⚠️ 它是字面量、且被守卫按字面量钉住
#: （``tests/api/test_auth_api.py::test_the_header_identity_channel_is_closed_by_default``
#: 除了断言本常量，还**实发一次请求**：``monkeypatch.delenv`` 之后重建 app，
#: 匿名带 ``X-Student-Id: 1`` 读 ``/api/students/1/home`` 必须是 **401**）。
#: ⚠️ 只钉常量的话，「常量是 0、但 :func:`allow_header_identity` 写反了」是绿的；
#: 只发请求的话，「函数对、但常量被改成 1」是绿的。两拍合起来才封住。
ALLOW_HEADER_IDENTITY_DEFAULT = "0"


def allow_header_identity() -> bool:
    """请求头那条通道**本次**开不开：``PE_ALLOW_HEADER_IDENTITY == "1"``，**且不是生产档**。

    ⚠️⚠️ **Plan 06 Task 4 加了第二个条件：``prod`` 下强制 ``False``**（计划 §4 逐字要求
    「``PE_ALLOW_HEADER_IDENTITY`` 在 prod 下**强制 0**（读到 1 也忽略 + 一条 warning 日志）」）。
    本函数负责「忽略」，那条 warning 由 :func:`app.main.create_app` 在装配时打**一次**
    （逐请求打会把日志淹掉，而「这个开关在生产上被设成了 1」是一个**部署事实**、
    不是一个请求事实）。

    ⚠️ **为什么是「强制关」而不是「生产上警告一下」**：这条通道**没有签名、没有过期、
    没有吊销**（本模块 docstring 第二节），它挡的是「前端把 id 写错就读到别人的数据」
    这一类**事故**，而**不挡**「有人故意伪造请求头」这一类**攻击**。在开发档上留着它
    是为了让既有 **1370 条**测试与 ``smoke.mjs`` 的 16 步不必重写（它们验的是业务规则、
    不是鉴权）；而生产档上它等于「任何人都可以自称任何学号」。
    ⚠️ 于是「生产上有人把它设成了 1」的失效方向本来是**静默不安全**——
    改前它就是一个纯环境变量判定，设了就开。改成强制关之后，那个失效**不可能发生**，
    而 warning 只是告诉运维「你设的那一格没有生效」。
    ⚠️ 守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_the_header_identity_channel_is_forced_off_in_the_production_tier``
    （它把 ``PE_ALLOW_HEADER_IDENTITY=1`` 与 ``PE_ENV=prod`` **同时**设上，
    然后实发一次带伪造请求头的匿名请求、断言 **401**）。

    ⚠️ **在请求时读环境变量、不在 import 时读**（口径与
    :func:`app.api.routers.pipeline._csv_dir` / :func:`app.auth.passwords.iterations`
    逐字相同）：``app.main`` 的模块级 ``app = create_app()`` 让「import 期读」等价于
    「必须在 import 之前设好」，而 ``monkeypatch.setenv`` 发生在 import **之后**。

    ⚠️ **只有字面 ``"1"`` 算开**（``"true"`` / ``"yes"`` / ``"2"`` 都算关）：
    一个安全开关的取值域越窄越好，而「哪些串算真」是一张迟早没人记得的对照表。
    失效方向是安全的——写错一个值会**关掉**过渡通道（表现为测试全 401，响亮），
    而不是**打开**它（表现为生产上谁都能伪造请求头，静默）。
    ⚠️ **而 :func:`app.deploy.tier` 的失效方向是 ``raise``**（一个认不出的 ``PE_ENV``
    会当场抛，不会静默落到某一档），故本函数的第一格判定不可能「静默地问错档位」。

    ⚠️ 空字符串按「没设」处理（``or``）：``$env:PE_ALLOW_HEADER_IDENTITY = ""`` 在
    PowerShell 里是「设了一个空值」而不是「删掉这个变量」。
    """
    if is_prod():
        return False
    raw = os.environ.get(ALLOW_HEADER_IDENTITY_ENV_VAR, "")
    return (raw or ALLOW_HEADER_IDENTITY_DEFAULT) == "1"


#: ---------------------------------------------------------------------------
#: **Plan 05A §3.4：cookie 会话的 OpenAPI ``apiKey`` securityScheme**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ 它与上面那两个请求头 scheme 是**同一条口径**（P4-A5：判定与声明必须成对挂，
#: 只挂判定的话前端从 spec 上看不出来要带 cookie、生成的 TS 客户端也不会加
#: ``credentials``），故它也是 ``auto_error=False``：**只负责声明**，
#: 判定仍由 :func:`current_session` / :func:`current_student` / :func:`current_teacher` 做，
#: 于是「缺会话」在本仓恒为 **401 ``unauthenticated``** 而不是 ``APIKeyCookie`` 自己那个 403。
#:
#: ⚠️ ``scheme_name`` 显式写成 cookie 的字面名 ``pe_session``：它就是 Swagger
#: 「Authorize」弹窗里显示的那个名字。⚠️ 而 Swagger UI **设不了 cookie**
#: （浏览器的同源策略不给页面脚本写 HttpOnly cookie，而那正是 ``httponly=True`` 的目的），
#: 故在 ``/docs`` 上试登录端点的正确姿势是**先打 ``POST /api/auth/login``**
#: ——浏览器会自己存下 ``Set-Cookie``，之后同源的请求自动带上。
#: 这一段写进 spec §13（Task 5）。
#:
#: ⚠️ **它是本仓第三个 securityScheme**，故 ``tests/api/test_prescription_api.py`` 那条
#: 全仓级断言（``sorted(schemes) == [...]``）与「挂 ``security`` 的操作数 = 46」
#: 两格都由 Plan 05A 改写（口径变化的理由逐字写在那条守卫的 docstring 里）。
SESSION_COOKIE_SCHEME = APIKeyCookie(
    name=auth_sessions.SESSION_COOKIE_NAME,
    auto_error=False,
    scheme_name=auth_sessions.SESSION_COOKIE_NAME,
    description=(
        "会话 cookie（HttpOnly，故 JS 读不到）。由 POST /api/auth/login 的 Set-Cookie "
        "种下、POST /api/auth/logout 过期掉；服务端那一行是 user_session，"
        "故登出是真的失效（不是客户端把一串丢掉）。缺会话或会话已过期/已吊销 → "
        "401 unauthenticated。⚠️ 前端 fetch 必须带 credentials: 'same-origin'"
        "（同源部署下这是默认值，但显式写出来，否则跨源部署时不会有任何提示）。"
    ),
)


def get_db(request: Request) -> Iterator[Session]:
    """每请求一个 :class:`~sqlalchemy.orm.Session`，退出时 ``close()``，**不 commit**。

    ⚠️ **签名与计划 Interfaces 写下的 ``get_db() -> Iterator[Session]`` 差一个参数**
    （本 Task 顶回派单的一处，报告里也记了）。差的那个参数是必需的：会话要一个引擎，
    而引擎是 :func:`app.main.create_app` 按注入的 ``db_url`` 造的、存在
    ``app.state.engine`` 上。一个无参的 ``get_db()`` 只能从**模块级全局**取引擎，
    于是同一进程里的两个应用（``create_app(db_url=A)`` 与 ``create_app(db_url=B)``）
    会共用**后建的那一个**引擎——而 ``tests/api/conftest.py`` 的 ``app`` 夹具是
    function 级的，每个测试都建一个新应用。那种共享会让「A 的测试读到了 B 的库」，
    且表现为间歇性的空结果，离真因极远。

    ``Request`` 是 FastAPI 里唯一能从依赖内部拿到「当前这个 app」的入口，
    故用它。对调用方没有区别：端点里仍然写 ``session: Session = Depends(get_db)``
    （``tests/test_main.py`` 的三个探针就是这么写的），FastAPI 自己会把 ``request``
    注进来。

    ``close()`` 放在 ``finally`` 里，故端点抛异常时会话也一定被关掉：
    SQLAlchemy 的 ``Session.close()`` 会回滚未完成的事务并归还连接。
    ``tests/test_main.py::test_integrity_error_maps_to_409`` 走的正是这一支
    （``commit()`` 抛 ``IntegrityError``、异常要穿过这个 ``finally`` 才能飞到错误处理器）。
    """
    engine: Engine = request.app.state.engine
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def _resolve_cookie_identity(request: Request, session: Session):
    """cookie 里那个串 → :class:`app.auth.sessions.Identity` 或 ``None``。

    ⚠️ 它是「哪个 cookie 是会话」这件事在本模块的**唯一**读点：三个身份依赖
    （:func:`current_session` / :func:`current_student` / :func:`current_teacher`）
    都经它，故 cookie 名只有一个住址（:data:`app.auth.sessions.SESSION_COOKIE_NAME`）。

    ⚠️ **不带 cookie 时本函数的成本是零次数据库访问**：
    :func:`app.auth.sessions.resolve` 的第一档就是「token 为空 → 返回 ``None``」，
    在 ``db.get`` 之前。这正是 1270 条既有测试（全部走请求头那一档）不受影响的原因。

    ⚠️⚠️ **Plan 06 Task 5 起它还多一件事**：解析成功时把「这一次请求是谁做的」
    记在 ``request.state`` 上（:func:`app.api.audit.note_subject`），供审计中间件
    **事后**取用。⚠️ 放在本函数里而不是四个身份依赖里各写一遍，理由正是上面那一句
    ——它是 cookie 那一档的**唯一**收口，故「带 cookie 的写请求」只会记一次、
    且不需要任何一处知道审计的存在。

    ⚠️ **它也顺带解决了 ``logout``**：:func:`app.api.routers.auth.logout` 会把那一行
    ``revoked_at`` 写上，于是**事后**再解析必然是 ``None``（登出那一行审计会变成
    ``anonymous``，而它恰恰是最该有名有姓的一行——「谁把自己的会话登出了」）。
    本函数在吊销**之前**跑，故那一格存得下来。

    ⚠️ **``staff_no`` 只教职那一档填**（学生那一档是 ``None``）：
    逐字理由见 :attr:`app.db.models.audit.AuditLog.staff_no` 那一列的注释。
    ⚠️ 而 :class:`app.auth.sessions.Identity` 的 ``login`` 一格在**两档**都有值
    （学生是学号、教师是工号），故本处要按 ``kind`` 分派一次——那正是
    :func:`app.api.routers.auth._identity_body` 把 ``login`` 拆成两格时做的同一件事。
    """
    identity = auth_sessions.resolve(session, request.cookies.get(auth_sessions.SESSION_COOKIE_NAME))
    if identity is not None:
        note_subject(
            request,
            AuditSubject(
                kind=identity.kind,
                subject_id=identity.subject_id,
                staff_no=(
                    identity.login
                    if identity.kind == auth_sessions.TEACHER_KIND
                    else None
                ),
            ),
        )
    return identity


def current_session(
    request: Request, session: Session = Depends(get_db)
) -> auth_sessions.Identity:
    """**只认 cookie 会话**的身份依赖；没有 → ``401``。

    ⚠️⚠️ **它刻意不回落请求头**（与 :func:`current_student` / :func:`current_teacher`
    的差别就在这一格）：它的两个消费者是 ``GET /api/auth/me`` 与
    ``POST /api/auth/logout``，而这两个端点说的**就是会话本身**——
    一个由请求头伪造出来的「我是谁」既没有 ``Set-Cookie`` 可种、也没有
    ``user_session`` 行可吊销，于是 ``logout`` 会变成一件什么也不做的事、
    ``me`` 会变成一句谎话（它回不出 ``role``，因为请求头那一档没有 role）。

    ⚠️ 返回的是整个 :class:`~app.auth.sessions.Identity`（五格），
    不是 ``int`` 或 ``str``：``me`` 要 ``name`` / ``role`` / ``login`` 三格，
    而 ``logout`` 要那个 token（从 ``request.cookies`` 再取一次）。
    """
    identity = _resolve_cookie_identity(request, session)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail=(
                f"缺少有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie："
                f"未登录、会话已过期（{auth_sessions.SESSION_TTL}）或已被吊销"
                f"（登出、或 subject 已从名册上删掉）"
            ),
        )
    return identity


def current_student(
    request: Request,
    session: Session = Depends(get_db),
    x_student_id: int | None = Header(None),
) -> int:
    """学生身份：**先看 cookie 会话，没有就（在过渡通道开着时）回落到 ``X-Student-Id``**。

    三档，顺序是承重的：

    1. **cookie 会话是学生的** → 返回 ``subject_id``（即 ``student.id``）。
       ⚠️ 这一档是**可信**的：它经过了口令校验，且 :func:`auth_sessions.resolve`
       已经回查过「这个学生还在不在册」（不在就当场吊销）。
    2. **cookie 会话是教师的** → ``403``。⚠️ 不是 401：请求者**已经登录了**，
       只是不是这个端点要的那一类人（``unauthenticated`` 说的是「我不知道你是谁」，
       而这里我们知道）。与 :func:`require_scope` 的「身份与目标不符 → 403」同一条口径。
    3. **没有 cookie 会话** →
       a. 过渡通道开着（``PE_ALLOW_HEADER_IDENTITY=1``）：有头用头、缺头 ``401``；
       b. 关着（**生产缺省**）：一律 ``401``，**请求头被完全忽略**——
          ⚠️ 那一格是本函数存在的全部理由：一个「先读头、再看开关」的实现
          会在生产上照样接受伪造的请求头。

    ⚠️ **签名多了两个参数**（``request`` 与 ``session``），故调用方仍然是
    ``requester: int = Depends(current_student)``（FastAPI 自己注入），
    但**直接调用**它的代码（``tests/api/test_scope.py`` 里没有，
    它一律走 ``Depends``）要跟着改。⚠️ ``request`` 必须排在最前：
    它没有缺省值，而 Python 的语法规则要求「带缺省的形参不得排在不带缺省的前面」。

    ⚠️ 标注成 ``int | None`` 的一个后果（**没变**）：过渡通道开着时，
    **头存在但不是整数**（``X-Student-Id: abc``）抛的是 FastAPI 的
    ``RequestValidationError`` → ``422``，不是本函数的 ``401``。
    不构成漏洞（两个码都拒绝访问），但前端要知道「没有头」与「头格式错」是两个码。
    口径由 ``tests/api/test_scope.py::test_a_non_integer_identity_header_is_422`` 钉住。
    ⚠️⚠️ **但那一格在带 cookie 时仍然会触发**（实现者实测，此前这里印的是
    「带 cookie 时那一格不再触发」——那句是错的，已按实际改写）：
    FastAPI 在**依赖体运行之前**就把 ``Header`` 参数解析并校验完了，
    故 ``X-Student-Id: abc`` + 一个有效的 cookie 得到的是 **422**、不是 200。
    ⚠️ 于是「生产档下请求头被忽略」这句话要精确到：请求头**不参与身份判定**，
    但它**仍然被解析**，一个格式错的头仍然会让请求失败。
    如实记录（硬规矩 #39）：它不构成漏洞（两个码都拒绝访问），
    但一个「顺手带着历史请求头」的前端在生产档下会看到 422 而不是 200。
    要彻底摘掉它，得把标注从 ``int | None`` 改成 ``str | None`` 并在本函数里自己转
    ``int``——而那会让「非整数的头」折成 **422 ``unprocessable_value``** 而不是
    既有的 **422 ``request_validation_failed``**（``tests/api/test_scope.py`` 的
    ``test_a_non_integer_identity_header_is_422`` 钉住了后者），
    为一个不影响安全的形状去改一个既有 code 不划算。
    守卫 ``tests/api/test_auth_api.py`` 的
    ``test_a_malformed_identity_header_is_422_even_next_to_a_valid_cookie`` 钉住实测行为。
    """
    identity = _resolve_cookie_identity(request, session)
    if identity is not None:
        if identity.kind != auth_sessions.STUDENT_KIND:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"当前会话是 {identity.kind}（{identity.login}），"
                    f"而本端点要的是学生身份：一个教师/管理员的 cookie 不能当学生用"
                ),
            )
        return identity.subject_id
    if allow_header_identity():
        if x_student_id is None:
            raise HTTPException(
                status_code=401,
                detail=(
                    f"缺少身份：既没有有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie，"
                    f"也没有请求头 X-Student-Id（过渡通道 "
                    f"{ALLOW_HEADER_IDENTITY_ENV_VAR}=1 是开着的）"
                ),
            )
        # ⚠️ **Plan 06 Task 5**：请求头那一档也要把「谁做的」交给审计
        #    （:func:`app.api.audit.note_subject`）。⚠️ 生产档下这一支**不可达**
        #    （:func:`allow_header_identity` 在 ``prod`` 下恒回 ``False``），
        #    而没有它的话开发档与全部测试里的写请求会被记成 ``anonymous``
        #    ——那是一句关于「谁做的」的假话。逐字理由见 :mod:`app.api.audit`
        #    的模块 docstring 第五节。
        note_subject(
            request,
            AuditSubject(kind=auth_sessions.STUDENT_KIND, subject_id=x_student_id),
        )
        return x_student_id
    raise HTTPException(
        status_code=401,
        detail=(
            f"缺少身份：需要一个有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie"
            f"（请先 POST /api/auth/login）。⚠️ 请求头 X-Student-Id 被忽略："
            f"{ALLOW_HEADER_IDENTITY_ENV_VAR} 不是 1"
        ),
    )


def current_teacher(
    request: Request,
    session: Session = Depends(get_db),
    x_teacher_staff_no: str | None = Header(None),
) -> str:
    """教师身份：**先看 cookie 会话，没有就（在过渡通道开着时）回落到 ``X-Teacher-Staff-No``**。

    三档与 :func:`current_student` 逐字同构（那一段是本仓对这条口径的唯一散文，
    刻意不抄第二份），差别只有两格：

    * **返回的是工号字符串**，不是代理键。⚠️ 这是承重的：教师侧全部闸门
      （:func:`require_staff` 一族、以及写进 ``prescription.teacher_overrides`` 的
      ``teacher_staff_no`` 一格）都以**工号**为主语，而 cookie 会话行上存的是
      ``teacher.id``。故 :func:`auth_sessions.resolve` 回查 subject 行时顺手把
      ``staff_no`` 装进 ``Identity.login``，本函数交出那一格——
      于是**两条通道对下游是同形的**，教师侧的端点一行都不用改。
    * 「空白也算缺」：``X-Teacher-Staff-No:`` 与 ``X-Teacher-Staff-No: %20``
      这类请求头会被 ASGI 原样送进来，而一个空工号既查不到教师、也不该被当成
      「有身份」。学号那一侧不需要这一支，因为 ``int`` 标注已经让非数字变成 ``422``。

    ⚠️ **管理员也走这一档**（``role='admin'`` 的行就在 ``teacher`` 表里，
    故 ``kind`` 仍然是 ``teacher``）：本函数**不看 role**，
    「这个端点要不要管理员」是 :func:`require_admin` 的事（Plan 05A Task 2）。
    """
    identity = _resolve_cookie_identity(request, session)
    if identity is not None:
        if identity.kind != auth_sessions.TEACHER_KIND:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"当前会话是 {identity.kind}（{identity.login}），"
                    f"而本端点要的是教师身份：一个学生的 cookie 不能当教师用"
                ),
            )
        return identity.login
    if allow_header_identity():
        if x_teacher_staff_no is None or not x_teacher_staff_no.strip():
            raise HTTPException(
                status_code=401,
                detail=(
                    f"缺少身份：既没有有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie，"
                    f"也没有请求头 X-Teacher-Staff-No（过渡通道 "
                    f"{ALLOW_HEADER_IDENTITY_ENV_VAR}=1 是开着的）"
                ),
            )
        # ⚠️ **Plan 06 Task 5**：与 :func:`current_student` 那一支同一条口径
        #    （逐字理由见那一处的注释，本处不抄第二份）。
        #    ⚠️ 本档填 ``staff_no``、**不填** ``subject_id``：请求头给的是工号，
        #    而 ``teacher.id`` 要再查一次库才拿得到——那一次查询对审计没有任何用处
        #    （``staff_no`` 已经能唯一定位那个人），故不查。
        #    ⚠️ 于是「审计行的 ``subject_id`` 为 NULL 而 ``staff_no`` 非空」是
        #    **请求头那一档的正常形状**，不是数据缺失；生产档下不可达。
        note_subject(
            request,
            AuditSubject(
                kind=auth_sessions.TEACHER_KIND, staff_no=x_teacher_staff_no
            ),
        )
        return x_teacher_staff_no
    raise HTTPException(
        status_code=401,
        detail=(
            f"缺少身份：需要一个有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie"
            f"（请先 POST /api/auth/login）。⚠️ 请求头 X-Teacher-Staff-No 被忽略："
            f"{ALLOW_HEADER_IDENTITY_ENV_VAR} 不是 1"
        ),
    )


@dataclasses.dataclass(frozen=True)
class ReaderIdentity:
    """**泛型读的身份**（:func:`current_reader` 的返回值）。**frozen**：它是一次请求的
    既成事实，可变化会让「端点体里改一下身份」在结构上成为可能。

    ------------------------------------------------------------------------
    ⚠️⚠️ 三格是**互斥**的，而互斥由 :func:`current_reader` 保证、不在本类里再判一次
    ------------------------------------------------------------------------

    ==============================  ==========================================
    会话                             三格的取值
    ==============================  ==========================================
    学生（``kind='student'``）       ``student_id`` 有值，另两格 ``None``
    教师（``role='teacher'``）       ``staff_no`` + ``role`` 有值，``student_id`` 是 ``None``
    管理员（``role='admin'``）        同上，而 :attr:`is_admin` 为 ``True``
    ==============================  ==========================================

    「匿名」那一档**根本到不了这里**（:func:`current_reader` 当场 ``401``），
    故本类**没有**「没有身份」的取值——那正是它此前被写成 ``int | None`` 时
    最容易被读错的一格（``None`` 是「教职，故不过滤」，不是「没身份」）。

    ------------------------------------------------------------------------
    ⚠️ 为什么本波从 ``int | None`` 换成一个 dataclass（Plan 06 Task 8）
    ------------------------------------------------------------------------
    :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT` 那一档要**三**个不同的动作
    （学生 → 只读自己的行 / 教师 → 只读自己任教班级的学生行 / 管理员 → 全读），
    而 ``int | None`` 只表达得开两个。把「教职」再拆成「教师 / 管理员」有两条路：
    ① 让端点体自己去查 ``teacher.role``（= 第二个所有者，且 13 个资源各查一次）；
    ② 让身份依赖一次解析、把 ``role`` 一起交出来。本类走的是 ②，
    与 :func:`current_reader` 那段「一次解析、就地分档」的既有口径同一条。

    ⚠️ ``role`` 存的是**字面量**（``"teacher"`` / ``"admin"``），取值域的唯一所有者
    仍然是 :attr:`app.db.models.organisation.Teacher.ROLES`（:data:`STAFF_ROLES`），
    本类不另立一份词表。
    """

    #: 学生会话：``student.id``。教职会话恒为 ``None``。
    student_id: int | None = None
    #: 教职会话：``teacher.staff_no``。学生会话恒为 ``None``。
    staff_no: str | None = None
    #: 教职会话：``teacher.role``（``"teacher"`` / ``"admin"``）。学生会话恒为 ``None``。
    role: str | None = None

    @property
    def is_admin(self) -> bool:
        """这一位教职是不是管理员（= **越过任教范围**，全读）。

        ⚠️ 它是「``role == 'admin'`` 意味着什么」在本类的唯一住址：两道任教闸门
        （:func:`require_teaches_section` / :func:`require_teaches_student`）
        各自也有一支 ``== ADMIN_ROLE`` 的越过，而那两支的理由逐字住在那两个函数里，
        本处不抄第二份。
        """
        return self.role == ADMIN_ROLE

    @property
    def is_student(self) -> bool:
        """这一位是不是学生会话。⚠️ 判据是 ``student_id is not None``，
        而不是「``staff_no is None``」——后者对「匿名」也成立，而匿名到不了这里，
        于是两个判据今天等价；写成前者是为了让「哪一格承载身份」这件事只有一处。"""
        return self.student_id is not None


def current_reader(
    request: Request,
    session: Session = Depends(get_db),
    x_student_id: int | None = Header(None),
    x_teacher_staff_no: str | None = Header(None),
) -> ReaderIdentity:
    """**泛型读的四档身份**（安全收紧波立三档；Plan 06 Task 8 把「教职」拆成两档）：
    匿名 ``401`` / 学生 → ``student_id`` / 教师 → ``staff_no`` + ``role='teacher'`` /
    管理员 → ``staff_no`` + ``role='admin'``。

    ------------------------------------------------------------------------
    ⚠️ 返回值是 :class:`ReaderIdentity`（三格互斥），**不再是** ``int | None``
    ------------------------------------------------------------------------
    「没有身份」那一档**根本到不了调用方**（本函数当场 ``401``）。故调用方
    （:func:`app.api.crud.build_crud_router` 里那两个身份感知的端点分支、
    以及 :func:`app.api.routers.feedback.normalized_scores`）读到的一定是
    **一个有身份的 :class:`ReaderIdentity`**，而「按哪一格过滤」由它自己的
    ``read_scope`` 档决定：

    * ``student_self`` 只读 :attr:`~ReaderIdentity.student_id`（教职一律全读）；
    * ``staff_taught`` 三格都读（学生 → 自己的行；教师 → 任教班级的学生行；
      管理员 → 全读）。

    ⚠️⚠️ **本波之前它返回 ``int | None``，而 ``None`` 的语义是「教职，故不过滤」**。
    那个形状在「教职一律全读」的口径下是对的，而 Plan 06 Task 8 把教师那一档
    收成「只读自己任教班级的学生」之后，``None`` 就同时意味着「管理员全读」与
    「教师按任教范围过滤」两件事——调用方于是必须自己再判一次 ``role``，
    那就是第二个所有者。换成三格的 dataclass 之后，「谁读到什么」在
    ``read_scope`` 那一格上仍然只有一个住址。

    ------------------------------------------------------------------------
    为什么不是复用 :func:`current_student` + :func:`current_teacher`
    ------------------------------------------------------------------------
    那两个函数各自**只认一种 kind**，而另一 kind 的 cookie 会被它们判成 ``403``
    （:func:`current_student` 逐字：「一个教师/管理员的 cookie 不能当学生用」）。
    而本波收紧的这一圈端点要的是**四档**：学生读自己的、教师读自己班的、
    管理员读全部、匿名一律拒。
    若在端点里「先试 ``current_student``、403 了再试 ``current_teacher``」，
    就会得到两个问题：① 两次 ``HTTPException`` 要靠 ``try/except`` 区分「跨 kind」
    与「真的没身份」，而那两档的码不同（403 / 401）；② 依赖被调用两次 =
    ``_resolve_cookie_identity`` 跑两次（两次 ``db.get``）。
    故这里**一次**解析、就地分档。⚠️ 而四档里「cookie 优先、请求头只在过渡通道开着时
    回落」这个**顺序**与那两个函数逐字相同（那一段散文的住址是
    :func:`current_student` 的 docstring，本处刻意不抄第二份）。

    ------------------------------------------------------------------------
    三个在册校验（各一档，失效方向都是「拒绝」）
    ------------------------------------------------------------------------
    * **学生那一档不在本函数里查库**：:func:`require_scope` 的第二支就是
      「``requester_id`` 在 ``student`` 表里查无此人 → ``403``」，而
      ``read_scope="student_self"`` 的 read-one **一定**会调它、list 的
      ``WHERE student_id = :me`` 天然查不出任何行（一个不在册的 id 没有数据）。
      故这里再查一次是白跑一次 ``SELECT``。
    * **教职那一档一律查**（⚠️ 本波把 cookie 那一档也加进来了，理由见下）：
      ``X-Teacher-Staff-No: WHATEVER`` 若不校验，过渡通道开着时任何调用方都能拿一个
      编造的工号换到「全读」——那比收紧之前更糟。故两条通道都调 :func:`require_staff`
      （不在册 ``403``）。
      ⚠️⚠️ **cookie 那一档此前刻意不查**（「``resolve`` 已经回查过 subject 行」），
      本波改成查，因为 ``role`` **必须是新鲜的**：``staff_taught`` 拿它决定
      「越过任教范围」还是「按任教范围过滤」，而 ``user_session.role`` 是登录时
      **冗余存下来**的那一份（:class:`app.auth.sessions.Identity` 的注释逐字记着这件事）。
      读它的话，一个被降级的管理员在会话过期之前仍然全读全校，
      而**写入侧**（:func:`require_admin`）已经当场拒绝他了——两侧给出两个口径。
      代价是教职会话的每一次泛型读多一次 ``teacher`` 表上的索引点查（``staff_no`` 唯一），
      与 :func:`require_staff` 既有的那一次同形。
    * ⚠️ 而「管理员越过任教范围」这一档**不在本函数里判**：本函数只交出 ``role``，
      判的是调用方（:attr:`ReaderIdentity.is_admin`）。理由与两道任教闸门里
      那两支 ``== ADMIN_ROLE`` 同一条：越过是**闸门**的语义，不是身份的语义。

    ⚠️ **两个请求头都带时学生头优先**。这不是随便挑的：两档里「学生自过滤」
    是**更窄**的那一个，故「挑错了」的失效方向是少给数据（响、可见），
    而不是多给（静默）。⚠️ 生产档下这一支不可达（请求头被完全忽略）。
    """
    identity = _resolve_cookie_identity(request, session)
    if identity is not None:
        if identity.kind == auth_sessions.STUDENT_KIND:
            return ReaderIdentity(student_id=identity.subject_id)
        # ⚠️ 到这里 kind 只可能是 teacher（管理员也是一行 teacher，role='admin'）。
        #    ⚠️ 而 ``role`` 刻意从**库里**取（``require_staff`` 返回它），
        #    不用 ``identity.role``（会话行上那份冗余）——逐字理由见上面第三段。
        return ReaderIdentity(
            staff_no=identity.login,
            role=require_staff(session, identity.login),
        )
    if allow_header_identity():
        if x_student_id is not None:
            return ReaderIdentity(student_id=x_student_id)
        if x_teacher_staff_no is not None and x_teacher_staff_no.strip():
            return ReaderIdentity(
                staff_no=x_teacher_staff_no,
                role=require_staff(session, x_teacher_staff_no),
            )
        raise HTTPException(
            status_code=401,
            detail=(
                f"缺少身份：既没有有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie，"
                f"也没有请求头 X-Student-Id / X-Teacher-Staff-No（过渡通道 "
                f"{ALLOW_HEADER_IDENTITY_ENV_VAR}=1 是开着的）"
            ),
        )
    raise HTTPException(
        status_code=401,
        detail=(
            f"缺少身份：需要一个有效的 {auth_sessions.SESSION_COOKIE_NAME} cookie"
            f"（请先 POST /api/auth/login）。⚠️ 请求头 X-Student-Id / "
            f"X-Teacher-Staff-No 被忽略：{ALLOW_HEADER_IDENTITY_ENV_VAR} 不是 1"
        ),
    )


#: 「这一行**不属于任何学生**」的哨兵。
#:
#: 它存在的全部理由是 :data:`app.api.crud.READ_SCOPE_STUDENT_SELF` 那一档里
#: **多态键**的资源（今天恰好 1 个：``notification``，它的学生键是
#: ``recipient_id`` + ``recipient_kind == 'student'``，而 ``recipient_kind``
#: 的取值域还包括 ``teacher``）。一行发给教师的通知**没有**学生所有者，
#: 而 :func:`require_scope` 的两个入参都是 ``int``——于是「无主」必须折成一个
#: 不可能撞上任何在册学生的整数，才能把判定**整个交给** ``require_scope``
#: （而不是在 ``crud.py`` 里再写一份 ``if owner is None: raise 403``，
#: 那就是派单点名不要的「第二份过滤逻辑」）。
#:
#: ⚠️ ``-1`` 是安全的：``student.id`` 是 SQLite 的 ``INTEGER PRIMARY KEY``
#: （rowid 别名），**恒 >= 1**，故 ``-1 != requester_id`` 对任何在册学生都成立，
#: :func:`require_scope` 的第一支当场 ``403``。
#: ⚠️ 代价（硬规矩 #39，如实记）：那一档的 message 是「学生 4 无权访问学生 -1 的数据」，
#: 读起来像是有一个 id 为 -1 的学生。今天演示库上 ``notification.recipient_kind``
#: 实测 **19 行全是 ``'student'``**，故这一支不可达；它挡的是「将来给教师也发站内信」。
#: 守卫是 ``tests/api/test_crud.py`` 的
#: ``test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student``。
NOT_STUDENT_OWNED = -1


def require_scope(session: Session, student_id: int, requester_id: int) -> None:
    """**作用域闸门**（计划 Review Focus 第 1 条：越权访问）。

    两个入参是**两个不同的东西**，混淆它们是这道闸门唯一的失效方式：

    * ``student_id`` —— **目标数据的所有者**，由调用方从行上读出来
      （``row.student_id``），不是从请求头来的；
    * ``requester_id`` —— **请求者的身份**，由调用方从一个身份依赖里拿到。
      ⚠️ **本函数自己不取身份**（它的两个入参都是 ``int``），故「优先读会话还是
      优先读请求头」这件事**不在这里**、也不该在这里：
      今天有两个调用方，各自用不同的依赖，而两者都是**同一个双通道口径**
      （先看 ``pe_session`` cookie，没有才在 ``PE_ALLOW_HEADER_IDENTITY=1`` 时
      回落请求头；生产缺省 ``"0"`` 下请求头被完全忽略）：

      * 特例端点（``weekly-sheet`` / ``prescriptions/current`` / ``home`` 一类）
        用 :func:`current_student`（**只认学生**，教师 cookie 是 403）；
      * 泛型工厂 ``read_scope="student_self"`` 那一档的 read-one
        用 :func:`current_reader`（**三档**：匿名 401 / 学生给 id / 教职给 ``None``，
        而教职那一档根本不会调到本函数）。

      ⚠️⚠️ 本处此前逐字写的是「来自 :func:`current_student`（即 ``X-Student-Id``）」，
      括号里那半句自 Plan 05A 起就已经过期（``current_student`` 优先读 cookie），
      而安全收紧波又加了第二个调用方 —— 故改成上面这份「本函数不取身份」的口径，
      它不会再因为多一个调用方而过期。

    两件事任一不成立就 ``403``：

    1. ``student_id != requester_id``。学生 A 拿 ``X-Student-Id: B`` 去读 B 的打卡 /
       RPE / 训练单 / 处方，正是 Review Focus 第 1 条逐字点名的形状。
    2. ``requester_id`` 在 ``student`` 表里查无此人。**这一支是 ``session`` 参数存在的
       全部理由**：不查库的闸门只能比对两个整数，于是 ``X-Student-Id: 999999`` 会被
       放行到端点里、只靠下游的 ``404`` 兜底——而下游的 ``404`` 是「没有这行数据」的
       意思，不是「你不是这个人」的意思，两者混在一起之后，前端无法区分
       「我确实没有打卡记录」与「我根本没登录成任何人」。

    两支都报 ``403``、不报 ``404``：区分「行不存在」与「你不是它的主人」等于把
    「哪些 id 在册」这件事告诉调用方。

    顺序是**先比对、后查库**：不匹配时不必白跑一次 ``SELECT``，而且比对是纯整数运算、
    不可能因为库的状态而改变结论。

    ⚠️ 「pure gate」的准确含义是**只判定、不改状态**（不 commit、不写库、不缓存、
    不回一个「通过了」的对象——返回值是 ``None``），**不是**「不碰数据库」。
    第 2 支要读一次 ``student``。测试名沿用计划原文的
    ``test_require_scope_is_a_pure_gate``，它的 docstring 里重述了这条口径。

    ⚠️ **教师不走这道闸门**：``requester_id`` 是 ``int``，而教师身份是工号字符串。
    教师端的边界是「这个教师在不在册」（:func:`require_staff`）；⚠️ 而自
    **Plan 03 Task 8** 起，教师端**读一个具体的班或学生**还要过
    :func:`require_teaches_section` / :func:`require_teaches_student`
    （任教关系），故「教师端一律跨学生」这句话已经不成立了——它今天只对
    那三个**写入**端点（教师覆盖 / 手动重生成 / 预警处置）还成立。
    """
    if student_id != requester_id:
        raise HTTPException(
            status_code=403,
            detail=f"学生 {requester_id} 无权访问学生 {student_id} 的数据",
        )
    if session.get(Student, requester_id) is None:
        raise HTTPException(
            status_code=403,
            detail=f"身份 {requester_id} 不是一个在册学生",
        )


def require_staff(session: Session, staff_no: str) -> str:
    """**在册教职闸门**：``staff_no`` 不在 ``teacher`` 表里就 ``403``；在册则**返回它的 role**。

    ⚠️⚠️ **Plan 05A Task 2 把它从 ``require_teacher`` 改名成 ``require_staff``、
    并让它返回 ``role``**（此前返回 ``None``）。改名不是修辞，而是一次事实的更正：
    **管理员也是一行 ``teacher``**（``role='admin'``，用户 2026-10-12 裁定
    「管理员这个角色接管管理台」落地成一个标签、不是第三张表），故本闸门今天
    放行的是「教师**或**管理员」，而旧名字读起来像是只放行教师。
    ⚠️ **计划 §3.6 第 3 条要求的是「新增一个 ``require_staff`` 依赖 =
    ``role in {"teacher","admin"}``」，实现者实测后发现那一格在行为上是 no-op**：
    旧 ``require_teacher`` 只查「工号在不在 ``teacher`` 表里」、**从不看 role**，
    故它本来就放行管理员。真正需要的动作是 ① 改名（让「教师或管理员」这件事
    在名字上成立）② 显式返回 role（:func:`require_admin` 与两道任教闸门要用它）
    ③ 显式校验 role 的取值域（把 ``role in {"teacher","admin"}`` 那句变成可执行的）。
    这一条已作为顶回记进报告。

    与 :func:`require_scope` 的第二支同一条理由（那一段逐字写着「这一支是 ``session``
    参数存在的**全部理由**」）：不查库的闸门只能判「有没有带头」，于是
    ``X-Teacher-Staff-No: WHATEVER`` 会被放行到端点里，而那个串随后被写进
    :attr:`app.db.models.prescription.Prescription.teacher_overrides` 的
    ``teacher_staff_no`` 一格——spec §7.5 末段把那些记录当**研究数据**
    （「学期末回答教师在哪些环节最不信任算法」），一条挂在不存在的人身上的覆盖
    在事后**无从归属**，等于让它作废。

    ⚠️ **报 403 不报 404**：区分「这个工号不存在」与「你不是这个人」等于把在册名单
    告诉调用方，与 :func:`require_scope` 同一条口径。

    ⚠️ **它只查一次库**（``select(Teacher.role).where(...)``）：``role`` 为 ``None``
    就是「查无此工号」，故不需要「先查 id、再查 role」两次往返。
    ⚠️ 而 :func:`teacher_id_of` 仍然单独存在（两道任教闸门要 ``teacher.id``
    去比 ``course_section.teacher_id``），故**在册的那一档会查两次**——
    两次都是主键/唯一索引上的点查，且 ``Session`` 的 identity map 让第二次的
    ``SELECT`` 只在 ``teacher`` 表上发生（不拉行对象）。要收敛成一次的话，
    把 :func:`teacher_id_of` 改成「返回 ``(id, role)``」并让本函数复用它即可，
    那是一次签名改动、不是一次语义改动；本 Task 没做（超出范围），已登记为待清扫。

    ⚠️ **本函数不判「这个教师能不能改这个学生的处方」**：它只判「在不在册」。
    ``course_section.teacher_id`` 与 ``enrollment`` 能推出一个「教师 ↔ 班级 ↔ 学生」的
    授权模型，**Plan 03 Task 8 已经把它建出来了**（:func:`require_teaches_section` /
    :func:`require_teaches_student`，两者都先调本函数），但**只挂在读的一侧**
    （教师大屏、班级周报、教师端读单个学生的本周训练单）。
    ⚠️ 三个**写入**端点（``POST …/overrides`` / ``POST …/regenerate`` /
    ``POST …/alerts/{id}/handle``）今天**仍然**只过本闸门，故任何在册教师可以覆盖任何
    学生的处方——如实记录（硬规矩 #39），并已登记为关切。收窄它们是一次一行的改动
    （把 ``require_staff`` 换成 ``require_teaches_student``），但那会改掉 Plan 04
    教师端的可点范围，故不在 Task 8 里顺手做。

    ⚠️ 它**刻意不复用** :func:`require_scope`：那个函数的两个入参都是 ``int``
    （学生 id），而教师身份是工号字符串；它的 docstring 里也逐字写了「教师不走这道闸门」。

    **返回**：那一行的 ``role``（``"teacher"`` 或 ``"admin"``）。
    ⚠️ 调用方**可以忽略返回值**（既有的四个特例端点就是这么写的：
    ``require_staff(session, staff_no)`` 单独一行），而 :func:`require_admin` 与
    两道任教闸门要用它。
    """
    role = session.scalar(select(Teacher.role).where(Teacher.staff_no == staff_no))
    if role is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"身份 {staff_no!r} 不是一个在册教师（teacher.staff_no 查无此工号）"
            ),
        )
    if role not in STAFF_ROLES:
        # ⚠️ 今天不可达（DB 的 ck_teacher_role 挡住了别的值），故它是许可而不是断言。
        # 它挡的是「有人绕过 ORM 直接写库」与「将来给 ROLES 加了第三个值、
        # 而 HTTP 层的口径没跟着定」两档——后者会让那个新角色**静默地**
        # 拿到全部课堂功能的权限。
        raise HTTPException(
            status_code=403,
            detail=(
                f"身份 {staff_no!r} 的 role 是 {role!r}，不在教职的取值域 "
                f"{sorted(STAFF_ROLES)} 里（teacher.role 的 CHECK 约束本应挡住它，"
                f"故这一档意味着有人绕过 ORM 直接写了库）"
            ),
        )
    return role


def require_admin(session: Session, staff_no: str) -> str:
    """**管理台闸门**：在册教职**且** ``role == 'admin'``；否则 ``403``。返回那个 role。

    用户 2026-10-12 逐字裁定「管理员这个角色接管管理台（23 个资源的增删改查）」，
    本函数就是那一句的可执行形式。它挂在
    :func:`app.api.crud._require_admin_identity` 上，于是 9 个可写资源的
    POST / PATCH / DELETE 一共 **26** 个操作从「任何在册教师可写」变成
    「**仅管理员**可写」（Plan 05A Task 2）。

    ⚠️ **两档都报 403、但 message 不同**，而这是有意的：

    * 「工号不在册」→ 由 :func:`require_staff` 报，message 说「不是一个在册教师」。
      那一档在**双通道过渡期**几乎只可能是「前端把工号写错了」或「登录态坏了」；
    * 「在册但不是管理员」→ 本函数报，message 明写 ``role`` 的当前值。
      那一档是**真的越权**，而前端要能把它翻译成一句人话
      （「管理台的写操作只有教务干事能做」）——只回一个 403 而不说为什么，
      用户会以为自己的登录坏了、去反复重登。

    ⚠️ **它不报 401**：请求者**已经**被认出来了（请求头或 cookie 都给出了一个工号，
    而那个工号在册）。「缺身份」是 401（由 :func:`current_teacher` 报），
    「身份不够」是 403——两档混在一起的话，前端无法区分「去登录」与「你没这个权限」。

    ⚠️ **请求头/cookie 的载体一个字都没变**（仍然是 ``X-Teacher-Staff-No`` 或
    ``pe_session``）：管理员就是一行 ``teacher``，故 OpenAPI 那一格
    （``Security(TEACHER_STAFF_NO_SCHEME)``）与前端发的那个头都不用改，
    改的只是**判定**。⚠️ 于是「挂 ``security`` 的操作数」在 Task 2 里**不变**
    （48）；变的是「谁能过」。
    """
    role = require_staff(session, staff_no)
    if role != ADMIN_ROLE:
        raise HTTPException(
            status_code=403,
            detail=(
                f"身份 {staff_no!r} 不是管理员（teacher.role == {role!r}）："
                f"管理台（23 个资源的增删改查）自 Plan 05A 起仅 role='admin' 可用。"
                f"课堂功能（大屏 / 周报 / 三源采集 / 预警处置 / 教师覆盖）不受影响，"
                f"它们过的是 require_staff（教师或管理员都可以）"
            ),
        )
    return role


def teacher_id_of(session: Session, staff_no: str) -> "int | None":
    """工号 → ``teacher.id``；查无此人则 ``None``。

    ⚠️ 它是「工号怎么变成一个可以比对的代理键」在本仓的唯一住址：
    ``course_section.teacher_id`` 存的是 ``teacher.id``（不是工号），
    而请求头传的是工号，故下面两道闸门都要先走这一步。

    ⚠️⚠️ **Plan 06 Task 8 把它从私有的 ``_teacher_id_of`` 改成公开面**（并加进
    :data:`__all__`）：第四档 :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT` 要在
    **SQL 层**拼「我任教的学生」那个子查询（:func:`taught_student_ids` 的入参是
    ``teacher.id``，不是工号），而 ``app.api.crud`` 若自己再写一句
    ``select(Teacher.id).where(...)`` 就是这一格的第二个所有者——两处漂移的失效形态是
    「泛型 list 的任教范围与特例端点的任教范围不是同一个集合」，而两侧各自的测试都还是绿的。
    """
    return session.scalar(select(Teacher.id).where(Teacher.staff_no == staff_no))


def require_teaches_section(
    session: Session, staff_no: str, course_section_id: int
) -> None:
    """**任教关系闸门（班级那一侧）**：这个教学班不是他教的 → ``403``。

    链路是 ``teacher.staff_no`` → ``teacher.id`` → ``course_section.teacher_id``
    （一跳，``course_section`` 上没有别的归属列）。

    ⚠️ **先过 :func:`require_staff`**（在册），再判任教关系：两道闸门各报一句
    不同的人话，而「工号根本不存在」与「工号存在但这个班不是他的」对前端是两种提示
    （前者是登录态坏了，后者是真的越权）。

    ⚠️ **「班不存在」与「班不是他教的」都报 403、不报 404**：与 :func:`require_scope`
    同一条口径——区分两者等于把「哪些 ``course_section_id`` 在册」告诉调用方。
    ⚠️ 代价（硬规矩 #39）：一个把 id 打错的前端会看到 403 而不是 404，
    于是它以为自己没有权限、去查登录态。这一档由 ``detail`` 里的原话兜住
    （它明写「不是他任教的班，或这个班不存在」）。

    ⚠️ **它不判学期**：``course_section.id`` 是全局代理键，而一个教师可以在不同学期
    教同名的班（两行、两个 id）。故「他教过这个班」与「他这学期教这个班」在本闸门上
    是同一件事——那一行本身就带着 ``semester_id``。

    ⚠️⚠️ **Plan 05A Task 2：``role == 'admin'`` 时越过本闸门**（计划 §3.6 第 2 条，
    ⚠️ **用户未裁定**，实现者复核后**同意**，复核证据逐字见下面那段）。
    理由：管理员（教务干事）**通常不带任何班**，于是不放行的话 ``role='admin'``
    就只是一个标签、这个角色没有任何意义——他会登录进 ``/admin``，
    却在教师大屏与班级周报上**一律 403**。
    ⚠️ **实现者实测复核**（派单 §4 第 2 条要求的）：一个不带任何班的**普通教师**
    今天访问 ``GET /api/dashboard/class/{id}`` 得到的是 **403**
    （``course_section.teacher_id`` 不等于他的 ``teacher.id``），
    而 ``GET /api/teacher/students/{id}/weekly-sheet`` 同样是 **403**
    （没有选课行）。故那条推论在代码里**成立**：闸门确实按任教关系判，
    而管理员确实没有任教关系。守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_an_admin_passes_the_teaching_gates_that_stop_a_classless_teacher``。
    ⚠️ **代价（硬规矩 #39）**：管理员因此能读**全校任何班、任何学生**的数据，
    而本仓没有「哪个教务干事管哪个院系」这一格。原型可接受（一个学校通常只有一两个
    干事），而它是一次真实的权限放大，已写进 spec §13 的已知局限。
    """
    if require_staff(session, staff_no) == ADMIN_ROLE:
        return  # 管理员越过任教范围闸门（理由与代价见上面那段 ⚠️⚠️）
    teacher_id = teacher_id_of(session, staff_no)
    taught = session.scalar(
        select(CourseSection.id).where(
            CourseSection.id == course_section_id,
            CourseSection.teacher_id == teacher_id,
        )
    )
    if taught is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"教学班 {course_section_id} 不是教师 {staff_no!r} 任教的班"
                f"（或这个班不存在）：判据是 course_section.teacher_id，"
                f"两者都报 403 而不是 404，因为区分它们等于把在册的班 id 告诉调用方"
            ),
        )


def taught_section_ids(teacher_id: "int | None", semester_id: int) -> Select:
    """**「这位教师在这个学期任教哪些教学班」的那一条 ``SELECT``**（返回 ``course_section.id``）。

    ⚠️ 它是「我本学期任教的班」这个集合在 **SQL 层**的唯一住址，
    **四个**消费者（⚠️ Plan 06 Task 8b 又加了两个）：

    * :func:`taught_student_ids`（它把本语句整个当成 ``IN (…)`` 的子查询，
      于是「我任教的学生」= 「在我任教的班里选过课的学生」，与派单 §1 逐字给出的
      那条 SQL 同形）；
    * :func:`app.api.routers.feedback.normalized_scores`（Plan 06 Task 8 给它加的
      **行级**收窄：教师只读得到自己任教的班的班内百分位）；
    * :func:`app.api.crud._orphan_condition`（Plan 06 Task 8b 的**第二根轴**：
      一行**没有**学生所有者的数据——班级级预警 ``alert.student_id IS NULL`` +
      ``course_section_id``——按「那个班是不是我本学期任教的」判，
      于是它对**相关的那一位教师**可见，而不是对任何教师都不可见）；
    * :func:`app.api.crud._section_filter`（Plan 06 Task 8b 的**第五档**
      :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT_SECTION`：
      ``weekly-class-reports`` 的教师档从「任何在册教职全读」收成
      ``WHERE course_section_id IN (本语句)``）。

    ⚠️⚠️ 于是后两个消费者与它们的 **read-one** 那一侧也**同源**：
    :func:`app.api.crud._require_row_matches` 拿的是**同一个函数**产出的
    同一个表达式对象，故「list 里看得见、点进去 403」与反过来都不可能发生。

    ⚠️⚠️ **它与 :func:`require_teaches_section` 那道闸门刻意不是同一条判据**：
    那道闸门**不判学期**（它的 docstring 逐字写了理由：``course_section.id`` 是
    全局代理键，一个教师在不同学期教同名的班是两行、两个 id，故「他教过这个班」
    与「他这学期教这个班」在那道闸门上是同一件事）。而本函数**要**一个学期：
    它的两个消费者问的都是「**这个学期**他能看见什么」，
    而不带学期的话，一位上学期教过某个班的教师这学期仍然能读到那个班的数据。
    ⚠️ 于是「同一个人、两个问题、两条判据」是**有意的**，而不是两份重复：
    ``require_teaches_section`` 回答「这一个班是不是他的」（点查，不拉集合），
    本函数回答「他的班有哪些」（集合，供 ``IN`` 子查询用）。

    ⚠️ ``teacher_id`` 可空时得到**空集**（``= NULL`` 恒不成立），逐字理由见
    :func:`taught_student_ids`。
    """
    return select(CourseSection.id).where(
        CourseSection.teacher_id == teacher_id,
        CourseSection.semester_id == semester_id,
    )


def taught_student_ids(teacher_id: "int | None", semester_id: int) -> Select:
    """**「这位教师在这个学期能通过任教关系看到哪些学生」的那一条 ``SELECT``**。

    返回的是**语句**而不是结果集——它是本仓「任教范围」这个判据在 **SQL 层**的
    唯一住址，两个消费者各用它一半：

    * :func:`require_teaches_student`（Plan 03 Task 8 的闸门）在它上面再挂一个
      ``WHERE enrollment.student_id = :那一个`` + ``LIMIT 1``，于是「这个学生在不在
      他的任教范围里」与「他能看到哪些学生」是**同一条语句的两个用法**；
    * :func:`app.api.crud._taught_filter`（Plan 06 Task 8 的第四档 ``staff_taught``）
      把它整个当成 ``IN (…)`` 的子查询，于是 13 个学生键资源的泛型 list 在
      **数据库里**就只剩他任教的学生的行（``LIMIT`` / ``OFFSET`` 与 ``total``
      都作用在已过滤的行上）。

    ⚠️⚠️ **判据逐字是 ``enrollment.course_section_id ∈ 我本学期任教的班``，
    且那一个学期同时钉住 ``enrollment`` 与 ``course_section`` 两行**
    （简报 P8-A5 点名的那条链：``enrollment`` 表 + ``course_section.teacher_id``；
    后半句由 :func:`taught_section_ids` 承担）。
    两个 ``semester_id`` 条件是**承重**的：少了它们，判据退化成「他**曾经**教过这个学生」，
    于是一位上学期教过某人的教师，这学期仍然能读那个人**本学期**的健康档案
    ——而那正是本判据要挡的形状。逐字理由住在 :func:`require_teaches_student` 里，
    本处不抄第二份。

    ⚠️ **``teacher_id`` 可空**（:func:`teacher_id_of` 查无此人时给 ``None``）：
    ``course_section.teacher_id = NULL`` 在 SQL 的三值逻辑下**恒不成立**，
    故一个不存在的教师得到的是**空集**，不是一次异常。失效方向是「少给数据」。

    ⚠️ **它不解析「哪一个是本学期」**：``semester_id`` 由调用方给，
    而「哪一个是本学年」的唯一所有者是
    :func:`app.pipeline.percentile_stage.current_semester_of`（本模块**不 import**
    ``app.pipeline``：那是 ``api`` 层内部的事，而本模块今天只向下拿 ``app.db`` 与
    ``app.auth``，见模块 docstring 的「本模块在依赖图里的位置」那一段）。

    ⚠️ ``SELECT`` 的列是 ``enrollment.student_id``（不是 ``enrollment.id``），
    故它可以直接作为 ``<学生键列> IN (本语句)`` 的子查询；
    一个学生在两个班里会有两行，``IN`` 对重复值不敏感（不必 ``DISTINCT``）。

    ⚠️ 形状是**两层 ``IN``**（``student_id IN (SELECT … FROM enrollment WHERE
    course_section_id IN (SELECT id FROM course_section WHERE …))``）而不是一次
    ``JOIN``，理由逐字是派单 §1 给的那条 SQL 的形状——两者语义相同，
    而 ``IN`` 那一形能直接被 :func:`app.api.crud._taught_filter` 接到
    **三种学生键形状**上（直接列 / 多态列 / 经外键，后者因此是三层 ``IN``），
    ``JOIN`` 那一形接不上第三种（中间表要再 ``JOIN`` 一次，而
    :class:`app.api.crud.StudentOwner` 的 ``via`` 只声明了表名与列名）。
    """
    return select(Enrollment.student_id).where(
        Enrollment.course_section_id.in_(taught_section_ids(teacher_id, semester_id)),
        # ⚠️ 承重：少了这一格，「上学期选过他的班」就等于「这学期也能读他」。
        #    ⚠️⚠️ 而它与 :func:`taught_section_ids` 里那一格 ``CourseSection.semester_id``
        #    在**既有的夹具上互相冗余**（Plan 06 Task 8 的定点变异实测：单独去掉任一个
        #    都不红 —— ``test_teaching_last_semester_does_not_grant_access_this_semester``
        #    造的是「上学期的班 + 上学期的选课行」，两个条件各挡住一半；
        #    **两个一起去掉**才红 2 条）。⚠️ 它单独承重的那一档是
        #    「一条 ``semester_id`` 是本学期的选课行、指向一个**上学期**的班」的反面
        #    （即选课行是上学期的、而班是本学期的），那种行在库层面可写
        #    （两列各自都是合法外键），而本仓今天没有那样的夹具 —— 如实记为已知边界。
        Enrollment.semester_id == semester_id,
    )


def require_teaches_student(
    session: Session, staff_no: str, student_id: int, semester_id: int
) -> None:
    """**任教关系闸门（学生那一侧）**：这个学生不在他**本学期**任教的任何班里 → ``403``。

    链路是 ``teacher.staff_no`` → ``teacher.id`` → ``course_section.teacher_id``
    → ``enrollment.course_section_id`` → ``enrollment.student_id``（简报 P8-A5 点名的
    那条链：``enrollment`` 表 + ``course_section.teacher_id``）。

    ⚠️⚠️ **``semester_id`` 是必填的，而它是承重的**（本 Task 的第一版没有它、
    当场被自己的测试抓到）：不带学期的话，判据退化成「他**曾经**教过这个学生」，
    于是一位上学期教过某人的教师，这学期仍然能读那个人**本学期**的训练单
    ——而那正是本闸门要挡的形状（那个学生已经不在他的班上了）。
    带上它之后，``enrollment`` 与 ``course_section`` 两行都必须落在同一个学期里，
    故「上学期教过」不再等于「这学期能读」。
    ⚠️ 调用方负责解析出那个学期（:func:`app.pipeline.percentile_stage.current_semester_of`
    是「哪一个是本学年」的唯一所有者）；本函数**不自己猜**。
    ⚠️ 顺带：两行的 ``semester_id`` 都必须等于入参那一个，故
    「一个学期的选课行挂到另一个学期的班上」这一档也被挡住（那种行在库层面可写，
    两列各自都是合法外键）。

    ⚠️ 它是 :func:`app.api.routers.prescription.weekly_sheet`（学生身份、
    ``X-Student-Id`` + :func:`require_scope`）的**教师侧对偶**：同一条数据
    （某个学生某一周的训练单），两个身份、两道不同的闸门。
    ⚠️ 而那个学生侧端点**刻意不接受** ``X-Teacher-Staff-No``
    （:mod:`app.api.routers.prescription` 的模块 docstring 逐字写了理由：
    「一个『学生或教师任一即可』的闸门要判两条规则」），故教师端必须有自己的一条路径。

    ⚠️ **代价（硬规矩 #39）**：``enrollment`` 今天在**生产路径上没有任何写入方**
    （:mod:`app.pipeline.alert_stage` 的模块 docstring 也记了同一件事），它只由
    ``seed_database`` 与 ``POST /api/enrollments`` 铺。故一个真实上线的系统里，
    「教师能不能看这个学生」取决于有没有人把选课行录进来——漏录的表现是教师端 403，
    而不是一条看得见的提示。
    ⚠️⚠️ **而 Plan 05A Task 2 之后管理员不受这一档影响**：``role == 'admin'`` 越过本闸门
    （理由、实测复核与代价逐字见 :func:`require_teaches_section` 里那段同款注释，
    刻意不抄第二份）。⚠️ 于是上面那条「漏录选课行」的代价**只对普通教师成立**。
    """
    if require_staff(session, staff_no) == ADMIN_ROLE:
        return  # 管理员越过任教范围闸门（理由逐字见 require_teaches_section）
    # ⚠️⚠️ **Plan 06 Task 8 起本闸门的那一条 ``SELECT`` 住在
    #    :func:`taught_student_ids` 里**（此前它逐字写在本函数体里）。
    #    抽出来的理由不是省字，而是**判据只能有一个所有者**：第四档
    #    :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT` 要在 SQL 层拼
    #    「我任教的学生」那个 ``IN (…)`` 子查询，而它必须与「这个学生在不在我的
    #    任教范围里」是**同一条语句**——两份写法漂移之后，失效形态是
    #    「泛型 list 里看得见某个学生的行、而点进详情是 403」（或反过来），
    #    两侧各自的测试都还是绿的。
    teacher_id = teacher_id_of(session, staff_no)
    taught = session.scalar(
        taught_student_ids(teacher_id, semester_id)
        .where(Enrollment.student_id == student_id)
        .limit(1)
    )
    if taught is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"学生 {student_id} 不在教师 {staff_no!r} 于学期 {semester_id} 任教的"
                f"任何教学班里（或这个学生不存在）：判据是 enrollment ⋈ "
                f"course_section.teacher_id，且两行的 semester_id 都必须等于那一个学期"
                f"——上学期教过他不等于这学期能读他。两者都报 403 而不是 404，"
                f"理由与 require_teaches_section 逐字相同"
            ),
        )


class Page(BaseModel):
    """分页参数。用法是 ``page: Page = Depends()``（Task 3 的 ``build_crud_router`` 会
    给 23 个资源各挂一个）。

    ``limit`` 上界 **200**：原型阶段前端一屏最多几十行，200 已远超需要；设上界是为了让
    ``?limit=100000`` 不会变成一次全表扫描——SQLite 不会替你拒绝它。
    下界 **1**：``limit=0`` 在语义上是「什么都不要」，而它会与「参数没传」在返回的
    空列表上无法区分，故直接拒掉。
    ``offset`` 下界 **0**：负偏移在 SQLite 上等价于 0，但那是一次静默的语义改写。

    ⚠️ 这三条边界**不是文档、是被强制执行的**：Pydantic 在构造时校验，
    而当它作为 FastAPI 依赖时同一套校验发生在解析查询串的阶段（失败 → ``422``，
    经 :mod:`app.api.errors` 折成统一形状）。
    ``tests/api/test_scope.py::test_page_caps_limit_at_two_hundred`` 两侧都测了。
    """

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
