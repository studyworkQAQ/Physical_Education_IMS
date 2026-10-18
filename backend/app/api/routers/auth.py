"""``/api/auth/*``：**八个**端点（Plan 05A Task 1 建五个；**Plan 08 Task 4** 加三个）。

==============================  ======  ==============  ==========================
路径                             码      身份             语义
==============================  ======  ==============  ==========================
``POST /api/auth/students/bind``  204   **匿名**         学号 + 出生日期 + 新口令 → 首次绑定
``POST /api/auth/teachers/bind``  204   **匿名**         工号 + 姓名 + 新口令 → 首次绑定
``POST /api/auth/bind-with-token`` 204  **匿名**         **一次性令牌** + 新口令 → 首次绑定
``POST /api/auth/login``          200   **匿名**         口令 → ``Set-Cookie`` + 我是谁
``POST /api/auth/logout``         204   **cookie 会话**  吊销那一行 + ``Set-Cookie`` 过期
``GET  /api/auth/me``             200   **cookie 会话**  我是谁（六格）
``POST /api/auth/bind-tokens``    201   **仅管理员**     签发一张一次性绑定令牌（明文只回一次）
``GET  /api/auth/bind-tokens``    200   **仅管理员**     已签发令牌的一页（**不含**明文与哈希）
==============================  ======  ==============  ==========================

⚠️ **是 5 个不是 6 个**（计划自审第 4 条自己抓出来的数错）：另一个会话里的
《实施计划 05》数出 6 个是因为它有 **refresh** 令牌；本计划**不做 refresh**，
改用**滑动过期**（:func:`app.auth.sessions.resolve` 每次把 ``expires_at`` 往后推），
故「两种令牌」那一套整个不存在。
⚠️⚠️ **Plan 08 Task 4 之后本模块确实有了「第二种令牌」**，而它与 refresh 令牌
**是两件不同的事**（如实记，免得下一个人把上面那一段读成过期）：
refresh 令牌是**已认证**用户用来续会话的，而绑定令牌是**尚未认证**的人用来
**设置第一份口令**的一次性凭据。故「不做 refresh」那一条裁定**一个字都没变**
（滑动过期仍然是会话那一侧的机制），本波加的三个端点全部住在**绑定**那一族里。

--------------------------------------------------------------------------
⚠️⚠️ Plan 08 Task 4：**两条绑定路径**与那一个开关
--------------------------------------------------------------------------

改前只有「自助绑定」一条：验身材料是**学号 + 出生日期**（教师侧是工号 + 姓名），
而 spec §1.2 第 4 条逐字记着它的强度 ——**任何教职**都读得到全校名册（含 ``birth``），
故这两格对教职是已知的，「验身材料等于零」。Plan 07 Task 9 端到端演过抢绑，
本 Task 又演了一遍（逐字取证见报告 §2）。

本波加的是**第二条、更强的路**：教务干事签发一张一次性令牌
（:class:`app.db.models.auth.BindToken`），学生拿令牌走
:func:`bind_with_token`。⚠️ 而**自助绑定那一条不删**，改成由
:data:`SELF_BIND_ENV_VAR` 控制，**缺省仍开**（= 今天的行为一格不变）。

⚠️⚠️ 于是三档事实要一次说清（本模块最容易被读错的一格）：

1. **缺省档下抢绑仍然做得到**：``PE_ALLOW_SELF_BIND`` 未设 ⇒ 两个自助端点照旧放行。
   要关掉它，运维得把那一个变量设成 ``0``（⚠️ 而关掉之后
   ``POST /api/auth/{students,teachers}/bind`` 一律 **403** + 一句点名了那个变量的 message）。
2. **令牌那一档不依赖开关**：:func:`bind_with_token` **一个环境变量都不读**，
   故它在两档下都工作 —— 那正是「可回退」的含义：先签发令牌、验证流程通了，
   再把开关关掉，中间没有任何一刻是「谁都绑不上」。
3. ⚠️ **而「§1.2 第 4 条收掉了」这句话今天仍然不成立**：只加令牌而不收窄 ``birth``
   的可见面，抢绑只是变麻烦了（要先把开关关掉）、没有变不可能。
   那一半是 **Task 5** 的活，本波**刻意不做**（两件事一起做会让取证混在一起）。
   spec §13.15 交付须知第 4 条因此改成「**部分收**」而不是「已收」。

--------------------------------------------------------------------------
⚠️⚠️ 错误档：六个自定义 ``code``，其中四个**不走** ``HTTPException``
--------------------------------------------------------------------------

:mod:`app.api.errors` 的 ``_CODE_BY_STATUS`` 只能按状态码折出六个 code
（``unauthenticated`` / ``forbidden`` / ``not_found`` / ``integrity_conflict`` /
``unprocessable_value`` / ``internal_error``）。而计划 §3.2/§3.3 要的
``password_already_bound`` / ``password_not_bound`` / ``invalid_credentials``
三个 code **不在那张表里**，故它们经 :func:`app.api.errors.error_response` 直接出去
（那是全仓唯一写 ``{"error": {...}}`` 这个字面量的地方，单一所有者没有被绕过）。

⚠️ 于是「哪个 code 从哪来」有两档，逐个点名：

* ``403 forbidden``（绑定时「不在册」与「验身材料不符」**共用**）→ ``HTTPException``；
* ``401 unauthenticated``（缺会话）→ ``HTTPException``（由
  :func:`app.api.deps.current_session` 抛）；
* ``422 unprocessable_value``（弱口令）→ 端点里 ``raise ValueError``
  （:func:`app.auth.passwords.ensure_acceptable`）；
* ``422 request_validation_failed``（请求体缺字段 / ``kind`` 不在取值域里）→ Pydantic；
* ``409 password_already_bound`` / ``403 password_not_bound`` / ``401 invalid_credentials``
  → :func:`error_response`。

⚠️ **Plan 06 Task 3 给 ``401 invalid_credentials`` 加了第二个来源**：锁定期内再试。
两档的 status、code 与 message **逐字相同**（:data:`_INVALID_CREDENTIALS_MESSAGE` 是那句
message 的唯一住址），故本模块的 code 清单**没有变**——变的是「同一个 code 现在有两种成因」。
控制者对计划 §3「锁内回 423/429」的改判与逐字理由见 :mod:`app.auth.policy` 的模块
docstring 第二节；守卫是 ``tests/api/test_auth_api.py`` 的
``test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password``。

⚠️⚠️ **Plan 06 Task 10 给 ``403 forbidden`` 也加了第二个来源**：两个 ``bind`` 端点的
**绑定限流锁定档**。⚠️ 处置与登录那一次改判**逐字同一条理由**（另给一个码 = 枚举信号
「这个标识存在且已被锁」），故锁定档回的是与「验身材料不符」**整个响应体逐字相同**的
那一档（学生侧 :data:`_BIND_FORBIDDEN_MESSAGE`、教师侧
:data:`_TEACHER_BIND_FORBIDDEN_MESSAGE`，两句 message 各自的唯一住址就是那两个常量）。
守卫是 ``tests/api/test_auth_api.py`` 的
``test_a_locked_bind_answers_byte_for_byte_like_an_ordinary_material_mismatch``
（比 status + ``content-type`` + **整个响应体的原始字节**，两个端点各一遍）。
⚠️ 于是本模块的 code 清单**仍然没有变**——变的又是「同一个 code 多了一种成因」。
⚠️ 而限流的**阈值与键**一律住在 :mod:`app.auth.policy`（``PE_BIND_MAX_FAILS`` /
``PE_BIND_WINDOW_MIN`` / ``PE_BIND_LOCK_MIN`` 三格，缺省 **3 / 15 / 60**，
⚠️ 比登录那一组更严，逐字算术见那个模块的 docstring）；本模块**一个阈值字面量都不写**。

⚠️ 从端点里 ``return error_response(…)`` 而不是 ``raise`` 是**可以的**：
FastAPI 见到返回值是一个 :class:`~starlette.responses.Response` 实例就原样发出，
**不经过** ``response_model`` 的校验（故一个 204 的端点也能回一个 409 的 JSON 体）。

--------------------------------------------------------------------------
⚠️⚠️ ``bind`` 的竞态：判据是**影响行数**，不是「读出来是 NULL 就写」
--------------------------------------------------------------------------

两个请求同时绑定同一个学号。若实现是「先 SELECT 出 ``password_hash is None``、
再 UPDATE」（check-then-act），**两个都能过**：两个 SELECT 都在任何一个 UPDATE
之前发生，于是第二个 UPDATE 会**覆盖**第一个的哈希——而两个请求都拿到 200/204，
用户以为自己的口令生效了，实际生效的是另一个人的。

对策是把检查搬进 UPDATE 的 ``WHERE`` 里（``… AND password_hash IS NULL``），
据 **``rowcount``** 判 409：数据库保证「一行只会被一个 UPDATE 改成非 NULL」，
故第二个请求的 ``rowcount`` 必然是 0。守卫是
``tests/api/test_auth_api.py`` 的
``test_the_second_of_two_concurrent_binds_is_409_not_a_silent_overwrite``
（它按「第二个请求的影响行数是 0」那一拍实测，不靠真的开两个线程）。
"""
import datetime as dt
import os

from fastapi import APIRouter, Depends, Request, Response, Security
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.audit import AuditSubject, note_subject
from app.api.deps import (
    SESSION_COOKIE_SCHEME,
    TEACHER_STAFF_NO_SCHEME,
    Page,
    current_session,
    current_teacher,
    get_db,
    require_admin,
)
from app.api.errors import error_response
from app.api.schemas.auth import (
    BindTokenIssuedRead,
    BindTokenPageRead,
    BindTokenRead,
    LoginCreate,
    SessionIdentityRead,
    StudentBindCreate,
    TeacherBindCreate,
    TokenBindCreate,
    TokenIssueCreate,
)
from app.auth import bind_tokens as auth_bind_tokens
from app.auth import policy as auth_policy
from app.auth import sessions as auth_sessions
from app.auth.passwords import ensure_acceptable, hash_password, verify_password
from app.auth.sessions import Identity
from app.db.models.auth import BindToken
from app.db.models.organisation import Student, Teacher

__all__ = [
    "BIND_TOKEN_EXPIRED",
    "BIND_TOKEN_SPENT",
    "INVALID_CREDENTIALS",
    "PASSWORD_ALREADY_BOUND",
    "PASSWORD_NOT_BOUND",
    "SELF_BIND_DEFAULT",
    "SELF_BIND_ENV_VAR",
    "SELF_BIND_OFF",
    "SELF_BIND_ON",
    "allow_self_bind",
    "router",
]

router = APIRouter()

#: ---------------------------------------------------------------------------
#: **Plan 08 Task 4：自助绑定那一条路的开关**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **它住在本模块、不住在 ``app.config``**，理由与
#: :data:`app.api.deps.ALLOW_HEADER_IDENTITY_ENV_VAR` /
#: :data:`app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR` /
#: :data:`app.auth.policy.MAX_FAILS_ENV_VAR` 逐字相同：``config.py`` 是全仓依赖图的
#: 叶子（只 import :mod:`pathlib`），给它加一个 ``import os`` 会改掉那个性质，
#: 而它持有的应当是**缺省值**、不是「本层如何在运行时覆盖缺省值」。
#: ⚠️ 而它住在**消费者这一侧**（本模块）而不是 :mod:`app.auth.bind_tokens`：
#: 它答的是「**哪一个 HTTP 端点放行**」，而 ``app.auth`` 不得 import ``fastapi``、
#: 也不该知道端点的存在（:mod:`app.auth` 的包 docstring 末节）。
SELF_BIND_ENV_VAR = "PE_ALLOW_SELF_BIND"

#: 缺省值 ``"1"`` = **自助绑定仍然放行**（= 今天的行为一格不变）。
#: ⚠️ 它是字面量、且被守卫按字面量钉住
#: （``tests/api/test_bind_token.py::test_the_self_bind_switch_is_open_by_default``：
#: 除了断言本常量，还 ``monkeypatch.delenv`` 之后**实发一次**自助绑定、断言 **204**）。
#: ⚠️ 只钉常量的话「常量是 1、而 :func:`allow_self_bind` 写反了」是绿的；
#: 只发请求的话「函数对、而常量被改成 0」是绿的。两拍合起来才封住
#: （与 :data:`app.api.deps.ALLOW_HEADER_IDENTITY_DEFAULT` 的同款两拍逐字同形）。
#:
#: ⚠️⚠️ **缺省方向是「开」而不是「关」**，这是本 Task 的顶回候选 ⑤，
#: 实现者复核后**同意控制者的倾向、不顶回**，两条理由：
#: ① 甲方**正在**用自助绑定那一档试用（``backend/pe_trial.db``，服务 PID 见报告 §1），
#:    缺省改成关会把他们**当场挡在门外**——而那一档的失效形状是
#:    「一个真实用户被拒之门外」，比「一个已知的局限多活一周」严重；
#: ② 关掉它**并不真的**收掉 spec §1.2 第 4 条（``birth`` 对教职仍然可读，
#:    一个教职仍然可以拿它去 ``POST /api/auth/login`` 逐个探测），
#:    故「缺省关」买到的是一格**假的**安全感。⚠️ 真正收掉那一格要等 Task 5。
SELF_BIND_DEFAULT = "1"

#: 认得的两格取值。⚠️ **只有这两个**：``"true"`` / ``"yes"`` / ``"2"`` 一律
#: **raise**（不是「当成关」）。⚠️ 这一格与
#: :func:`app.api.deps.allow_header_identity` **刻意不同档**
#: （那一个把「不是 ``1``」一律当关），理由是**失效方向相反**：
#:
#: * 请求头身份那一档，「认不出 ⇒ 关」的失效方向是**安全**的（少给一条通道，
#:   表现为测试全 401，响亮）；
#: * 本档「认不出 ⇒ 关」的失效方向是**把甲方挡在门外**（一个把 ``PE_ALLOW_SELF_BIND``
#:   写成 ``false`` 的运维会得到「所有新生都绑不上」，而报错文本里没有任何一句
#:   指向那个变量）。⚠️ 而「认不出 ⇒ 开」同样不行（那是**静默不安全**）。
#:
#: 故本档取**第三条**：认不出就**响亮地失败**。口径与 :func:`app.deploy.tier`
#: 对 ``PE_ENV`` 的处置逐字相同（``raise``，不静默落到某一档）。
SELF_BIND_ON = "1"
SELF_BIND_OFF = "0"


def allow_self_bind() -> bool:
    """自助绑定（学号 + 出生日期 / 工号 + 姓名）那一条路**本次**开不开。

    ⚠️ **在请求时读环境变量、不在 import 时读**（口径与
    :func:`app.auth.passwords.iterations` / :func:`app.api.deps.allow_header_identity` /
    :func:`app.auth.policy.throttle` 逐字相同）：``app.main`` 有一条模块级的
    ``app = create_app()``，「import 期读」等价于「必须在 import 之前设好」，
    而 ``monkeypatch.setenv`` 发生在 import **之后**。

    ⚠️ 空字符串按「没设」处理（``strip()`` 之后判空）：``$env:PE_ALLOW_SELF_BIND = ""``
    在 PowerShell 里是「设了一个空值」而不是「删掉这个变量」——与
    :func:`app.auth.policy._int_from_env` / :func:`app.auth.passwords.iterations`
    逐字同一条口径。

    ⚠️⚠️ **认不出的值一律 ``ValueError``**（:data:`SELF_BIND_ON` / :data:`SELF_BIND_OFF`
    之外的一切），逐字理由见那两个常量的注释。⚠️ 它有**两个**响的地方：

    * **装配期**（:func:`app.main.create_app` 调它一次）：一个坏值让服务**起不来**，
      报错文本点名了那个变量与那两格取值 —— 那是最响的一档，也是运维真正撞见的那一档；
    * **请求期**（两个自助端点的第一行）：若有人绕过 ``create_app`` 直接调本函数
      （例如一个 CLI），``ValueError`` 经 :mod:`app.api.errors` 折成
      **422 ``unprocessable_value``** 并带上消息原文。

    ⚠️ **它不读 ``PE_ENV``**（与 :func:`app.api.deps.allow_header_identity` 不同）：
    那一格在生产档强制关，因为它是一条**没有签名、没有过期、没有吊销**的过渡通道；
    而自助绑定是**产品功能**（甲方今天正在用它），生产档强制关会把这个交付物
    变成「上线即不可用」。⚠️ 于是「生产上要不要关掉自助绑定」是一个**运维决定**，
    而本函数把它交给运维（如实记，硬规矩 #39：这也意味着一台忘了设
    ``PE_ALLOW_SELF_BIND=0`` 的生产机上，抢绑仍然做得到 —— 那一格由 spec §13.15
    交付须知第 4 条与部署清单一起兜住）。
    """
    raw = os.environ.get(SELF_BIND_ENV_VAR, "").strip()
    if not raw:
        raw = SELF_BIND_DEFAULT
    if raw == SELF_BIND_ON:
        return True
    if raw == SELF_BIND_OFF:
        return False
    raise ValueError(
        f"{SELF_BIND_ENV_VAR}（自助绑定开关）只认 {SELF_BIND_ON!r}（开）与 "
        f"{SELF_BIND_OFF!r}（关）两格取值，收到 {raw!r}。"
        f"⚠️ 认不出的值一律**响亮失败**、不静默落到某一档：「当成关」会把正在用"
        f"自助绑定的新生挡在门外（而报错文本不会指向本变量），「当成开」是静默不安全。"
        f"⚠️ 空串按「没设」处理（= 缺省 {SELF_BIND_DEFAULT!r} = 开）。"
    )


#: 三个自定义 code。⚠️ **它们是字面量的唯一住址**：
#: :mod:`app.api.errors` 的 ``_CODE_BY_STATUS`` 按状态码折不出它们
#: （409 折出来的是 ``integrity_conflict``、403 是 ``forbidden``、401 是 ``unauthenticated``），
#: 而前端要按 code 分支（``password_not_bound`` → 跳绑定页，
#: ``invalid_credentials`` → 停在登录页并清空口令框），故三个串各自只有一个所有者。
PASSWORD_ALREADY_BOUND = "password_already_bound"
PASSWORD_NOT_BOUND = "password_not_bound"
INVALID_CREDENTIALS = "invalid_credentials"

#: ⚠️⚠️ **「口令不正确」那一句 message 的唯一住址**（Plan 06 Task 3 提上来的）。
#: 它此前是 :func:`login` 里 ``error_response(401, INVALID_CREDENTIALS, "口令不正确")``
#: 的一个内联字面量；Task 3 之后**同一档有两个来源**（真的口令错、与锁定期内再试），
#: 而控制者的改判逐字要求两者**逐字相同**（:mod:`app.auth.policy` 的模块 docstring
#: 第二节）。写两遍字面量的话，下一个人给其中一处「顺手改得更具体一点」
#: （例如加上「多次失败后账号已被暂时锁定」）就会当场把「这个标识存在且已被锁」
#: 这个枚举信号送出去——而那正是改判要避免的事。
#: ⚠️ 守卫是 ``tests/api/test_auth_api.py`` 的
#: ``test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password``
#: （比 status + **整个响应体**，故派单点名的 ``code`` / ``message`` 两格连同
#: ``detail`` 一并钉住；两档因此连**响应体的字节序**都相同——
#: ``error_response`` 是全仓唯一写 ``{"error": {...}}`` 的地方，键序恒定）。
_INVALID_CREDENTIALS_MESSAGE = "口令不正确"

#: ⚠️ **绑定时「不在册」与「验身材料不符」共用的那一句 message**（计划 §3.2 逐字要求：
#: 同一个 code + 同一句 message，**不给攻击者区分信号**）。
#: 它是本模块唯一一个「刻意不含任何变量」的用户可见串：插入学号会让
#: 「这个学号在不在册」变成一个可以逐个字读出来的信号，而那正是共用 code 要防的事。
_BIND_FORBIDDEN_MESSAGE = "学号或验身材料不正确，无法绑定口令"

_TEACHER_BIND_FORBIDDEN_MESSAGE = "工号或验身材料不正确，无法绑定口令"

#: ⚠️⚠️ **Plan 08 Task 4 的两个新 code**（本模块的 code 清单从三个变成五个）。
#:
#: 两者各答一件**持令牌的人**必须知道的事，而它们**刻意可区分**
#: （与 :data:`_BIND_FORBIDDEN_MESSAGE` 那条「两档合成一个 403」的裁定**相反**）。
#: 逐字理由：那一条裁定防的是**枚举**（「哪些学号在册」不该逐个字告诉一个匿名调用方），
#: 而要走到下面这两档，调用方**必须先交出一份秘密那一段验得过的完整令牌**
#: （:func:`bind_with_token` 把 :func:`app.auth.bind_tokens.matches` 排在两档之前）——
#: 即他**已经持有那张凭据**。对一个已经持有凭据的人说「它用过了」或「它过期了」
#: 不泄漏任何他不知道的事，而**不说**的代价是具体的：他会以为口令设错了、
#: 反复重输，然后被限流锁 60 分钟（:mod:`app.auth.policy` 的绑定那一组），
#: 而那 60 分钟里他既绑不上也登不进去（本原型没有口令找回）。
#:
#: ⚠️ 而**「令牌不存在 / 秘密不对 / 目标已不在册」三档仍然合成一个 403**
#: （:data:`_BIND_TOKEN_FORBIDDEN_MESSAGE`）：那三档**不需要**任何凭据就能打到，
#: 故它们才是枚举面，处置与 :data:`_BIND_FORBIDDEN_MESSAGE` 逐字同一条。
BIND_TOKEN_SPENT = "bind_token_spent"
BIND_TOKEN_EXPIRED = "bind_token_expired"

#: ⚠️ **令牌那一档「验身不符」的 message**（三档共用，逐字理由见上面那段）。
#: ⚠️ 它**刻意不含任何变量**：插入 ``token_id`` 会让「这个选择子在不在库里」
#: 变成一个可以逐个字读出来的信号，而那正是三档共用一个 message 要防的事。
_BIND_TOKEN_FORBIDDEN_MESSAGE = "绑定令牌不正确，无法绑定口令"

#: ⚠️ **自助绑定被关掉时那一句 message 的唯一住址**（两个端点共用）。
#: 它**点名了那个环境变量**：这一档的读者是**运维**（一个用户看到它只会去问教务干事），
#: 而「服务起来了、新生一个都绑不上」这一格失效如果不在 message 里指向真因，
#: 排查会从前端一路查到名册数据。⚠️ 它**不是**枚举信号：它是一个**全局配置事实**，
#: 对任何学号都给出同一句，故与「这个学号在不在册」无关。
_SELF_BIND_DISABLED_MESSAGE = (
    "本部署已经关掉了自助绑定（学号 + 出生日期 / 工号 + 姓名）：请改用教务干事签发的"
    "一次性绑定令牌（POST /api/auth/bind-with-token）。"
    "⚠️ 运维口径：这一档由环境变量 PE_ALLOW_SELF_BIND=0 决定"
    "（缺省是 1 = 开；把它设回 1 即恢复今天的行为）"
)


def _bind_credential(
    session: Session,
    model: type[Student] | type[Teacher],
    row: Student | Teacher,
    plain: str,
    bound_at: dt.datetime,
) -> int:
    """把哈希写进 ``password_hash``，**仅当那一列还是 NULL**；返回影响行数（0 或 1）。

    ⚠️ 这一格是 ``bind`` 竞态的全部机制（模块 docstring 最后一节）：检查在 ``WHERE`` 里，
    判据是 ``rowcount``，**不是**「先读出来看是不是 NULL」。

    ⚠️ ``synchronize_session=False``：本函数用的是 Core 的 :func:`~sqlalchemy.update`，
    而 ``row`` 那个 ORM 实例还在 identity map 里。缺省的 ``"auto"`` 会尝试
    「按 WHERE 条件在内存里挑出要同步的对象」，那需要**求值** SQL 表达式，
    对 ``IS NULL`` 这类条件可以、但对复杂条件会退化成一次额外的 SELECT；
    显式关掉它，因为两个调用方在 ``rowcount == 1`` 之后都**不再读 ``row``**
    （响应体是 204、没有体），故不需要同步。
    """
    result = session.execute(
        update(model)
        .where(model.id == row.id, model.password_hash.is_(None))
        .values(password_hash=hash_password(plain), password_bound_at=bound_at)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount


@router.post(
    "/api/auth/students/bind",
    tags=["auth"],
    status_code=204,
)
def bind_student(
    payload: StudentBindCreate,
    request: Request,
    session: Session = Depends(get_db),
) -> Response:
    """（匿名）学生**首次**绑定口令：学号 + 出生日期 + 新口令 → 204。

    ⚠️ **这是「名册已存在 + 首次绑定密码」，不是自助注册**（用户 2026-10-12 逐字裁定）：
    本端点**不建学生行**，学生行由管理员经 ``POST /api/students`` 建
    （Plan 05A Task 2 之后**仅管理员**）。故一个不在册的学号在这里是 403、不是 201。

    五档失败，**顺序是承重的**（⚠️ 第 2 档是 **Plan 06 Task 10** 加的）：

    * **422 ``unprocessable_value``** —— 口令太短（< 8 个字符）。⚠️ 排在最前：
      它是纯本地判定、不碰库，故一次弱口令尝试**不会**变成一次数据库查询
      （一个不需要账号就能打出来的 DoS 面）。
    * **403 ``forbidden``（锁定档）** —— 这个学号在**绑定**这一个用途上已经被锁。
      ⚠️ 它排在**查 subject 行之前**，故锁定档既不查 ``student`` 表、也不跑
      :func:`app.auth.passwords.hash_password`（绑定路径上唯一那一次 PBKDF2）。
      ⚠️ 而它的响应体与下面那一档**逐字相同**（控制者裁定，理由与登录那一次
      423/429 → 401 的改判逐字同一条：另给一个码就是枚举信号「这个学号存在且已被锁」）。
      ⚠️ 阈值与键一律住在 :mod:`app.auth.policy`，本函数**一个字面量都不写**。
    * **403 ``forbidden``** —— 学号不在册 **或** 出生日期不符。
      ⚠️ **两档共用一个 code + 一句 message**（:data:`_BIND_FORBIDDEN_MESSAGE`）：
      区分它们等于把「哪些学号在册」逐个字告诉一个匿名调用方。
      ⚠️ 而**这一档的防护强度是有限的**：验身材料（``birth``）今天仍然读得到，
      只是**不再匿名**——Plan 05A Task 5 已把 ``GET /api/students`` 收到教职身份
      （匿名实测 **401**；本处此前写的是「验身材料本身匿名可读……收紧它是 Task 5 的活」，
      而那件活已经做完了，故那一句今天反了）。剩下的局限是「一个已登录的教职
      能替任何还没绑定的学生抢先绑一个口令」。
      ⚠️ 「哪些读今天还匿名」的账面只有一个住址：:mod:`app.api.routers.catalog`
      的模块 docstring，本处不复述第二份（终审 I3）。
    * **409 ``password_already_bound``** —— 已经绑定过了。
      ⚠️ **它排在 403 之后**：反过来就会让一个不知道出生日期的攻击者
      读出「这个学号绑定过了没有」。
    * **422 ``request_validation_failed``** —— 请求体缺字段或 ``birth`` 不是合法日期。

    ⚠️ **成功后不自动登录**（不回 ``Set-Cookie``）：绑定与登录是两件事，
    前端在 204 之后自己打一次 ``POST /api/auth/login``。理由是「绑定成功即已认证」
    会让「验身材料泄漏」直接等于「账号被接管」，而分开之后攻击者还需要口令。

    ------------------------------------------------------------------
    ⚠️⚠️ **Plan 06 Task 10 起本端点有绑定限流与锁定**（此前逐字写着「不做」）
    ------------------------------------------------------------------

    改前的形状是一个**真的洞**：绑定用的验身材料是**弱材料**（学号 + 出生日期，
    spec §1.2 第 4 条），而本端点**完全没有限流** —— 一个匿名调用方可以对一个
    **还没绑定**的账号反复猜出生日期，猜中就**抢到**那个账号的口令
    （而本原型**没有口令找回**，被抢的人再也进不去）。安全收紧波摘掉
    ``password_bound_at`` 那一列只关掉了「可批量枚举谁还没绑」，
    而**猜**这一件事它挡不住。

    四格实现口径（逐字理由各自只有一个住址，本处不复述）：

    * **复用登录那一套机器**：所有者是 :mod:`app.auth.policy`、存储是 ``login_attempt``。
      ⚠️ 而**键多了一维「用途」**（``PURPOSE_BIND``）：与登录共用一个键的话，
      「猜出生日期猜错三次」会把那个账号的**登录**也锁掉 —— 那是把限流变成
      **拒绝服务**（一个匿名调用方只要拿别人的学号乱猜绑定材料，就能把那个人
      锁在自己的账号外面）。逐字理由与「为什么用途编进键的字符串里、而不是加一列」
      见 :mod:`app.auth.policy` 的模块 docstring。
    * **阈值是配置**：**3** 次失败 / **15** 分钟窗口 / 锁 **60** 分钟，三格各有环境变量
      （``PE_BIND_MAX_FAILS`` / ``PE_BIND_WINDOW_MIN`` / ``PE_BIND_LOCK_MIN``）。
      ⚠️ 三格**一律比登录那一组更严**，而那是一条算术（出生日期只有约 2 900 个可信取值）：
      逐字表住在 :mod:`app.auth.policy` 的模块 docstring，本处一个数都不写第二遍。
    * **锁定档回与「材料不符」逐字相同的 ``403 forbidden``**（:data:`_BIND_FORBIDDEN_MESSAGE`）
      ——**不是** 423 / 429，理由与登录那一次改判逐字相同。
      ⚠️ 代价（如实记）：被锁的**合法新生**在锁定期内得不到任何提示，他看到的就是
      「学号或验身材料不正确」，于是他会继续重输（而那些重输**不写行**、
      故不会把锁推后，60 分钟后自然解开）。
    * **只有「材料不符 / 不在册」那一档计数**；``409 password_already_bound``
      **一行都不写**（那一档说明材料**猜对了**，计数它没有任何防护价值，
      而它会把一个「忘了自己绑过」的人越锁越深）。
      ⚠️ 而这一档与登录那一侧的取舍**相反**（登录只计「口令验不过」、不计
      ``403 password_not_bound``），理由也相反：登录那一侧的 403 与 401 是
      **可区分**的两档提示（要的下一步动作相反），计数 403 会把提示改坏；
      而绑定这一侧的「不在册」与「材料不符」**本来就合成同一个 403**
      （下面那个 ``or``），故计数它不会改坏任何提示 —— 而它**正是**要挡的那一档。
    * **成功绑定清零**：:func:`app.auth.policy.record_success`（``purpose=PURPOSE_BIND``）。
      ⚠️ 它自己 commit，而那一次 commit **顺带**把上面 ``password_hash`` 那一次 UPDATE
      一起提交（故本函数**不再自己 commit**）——「口令哈希落库」与「计数器清零」
      落在同一个事务里，逐字理由见那个函数的 docstring。

    ⚠️ **``request`` 这个形参是本波加的**，只为拿一格 ``request.client.host`` 写进
    ``login_attempt.ip``（与 :func:`login` 的同名形参逐字同一条口径：它**不进 OpenAPI**，
    故本端点在 ``/openapi.json`` 上的声明面**一个字节都没变**）。
    ⚠️ **IP 不参与限流判定**（参与的话攻击者换一个出口 IP 就绕过），它只是事后线索。

    ⚠️⚠️ **审计连带（派单 §2.8）**：本端点是 ``POST``，故 :func:`app.api.audit.should_record`
    **本来就**认它 —— **锁定档也照样写一行**审计（``method`` / ``path`` / ``status=403`` /
    ``subject_kind='anonymous'`` / ``target=NULL``），本波**一行代码都不用加**、
    审计档数**一个都没变**。⚠️ 而那一行与「材料不符」那一档的审计行**逐格相同**
    （``audit_log`` 的 9 列里没有任何一格能装「这一次是锁定」：``target`` 取自路径参数、
    而本路径没有参数）。⚠️ 于是「谁被锁过」这件事**在库里仍然查不出**——
    要让那两档可分辨得给 ``audit_log`` 加一列（= 改 schema = 配迁移），
    本波**刻意不做**（逐字顶回见 Task 10 报告的 §5）。
    守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_the_locked_bind_tier_writes_the_same_single_audit_row_as_an_ordinary_mismatch``。
    """
    ensure_acceptable(payload.password.get_secret_value())
    ip = request.client.host if request.client is not None else None
    # ⚠️⚠️ **Plan 08 Task 4 的开关档**（:func:`allow_self_bind`）。
    #    ⚠️ **它排在 ``ensure_acceptable`` 之后**：那一档是纯本地判定（一个长度比较）、
    #    而本档要读一次 ``os.environ`` —— 两个都是零成本的本地动作，
    #    而把「口令太短」排在最前是本端点既有的口径（「一个不需要账号就能打出来的
    #    DoS 面」那一段），故本波**不改那个顺序**。
    #    ⚠️ **缺省档（开关开着）下本行是一个恒真的判定 + 一次字典查找**，
    #    故「今天的行为一格不变」在**响应**与**审计**两侧都成立
    #    （守卫是 ``tests/api/test_bind_token.py`` 的
    #    ``test_the_default_tier_is_byte_for_byte_the_pre_task_4_behaviour``：
    #    两档各发一次同样的请求，比 status + 响应体的**原始字节** + 落库的审计行数与九列）。
    if not allow_self_bind():
        return error_response(403, "forbidden", _SELF_BIND_DISABLED_MESSAGE)
    # ⚠️⚠️ **锁定档排在查 subject 行之前、而排在上面那一档 422 之后**（两个顺序各自承重）：
    #    · 排在 422 **之后**：``ensure_acceptable`` 是**纯本地**判定（一个长度比较），
    #      而 :func:`auth_policy.is_locked` 是**一次数据库查询**（``count(*)`` +
    #      ``max(at)``）。反过来的话，一次弱口令探测就变成一次数据库查询 ——
    #      而那正是本端点原有那条「422 排在最前」的注释要防的形状
    #      （「一个不需要账号就能打出来的 DoS 面」）。
    #    · 排在查 subject 行**之前**：于是锁定档既不查 ``student`` 表、也不跑
    #      :func:`app.auth.passwords.hash_password`（绑定路径上唯一那一次 PBKDF2，
    #      它在 :func:`_bind_credential` 里）。⚠️ 守卫是
    #      ``test_the_locked_bind_tier_never_reads_the_roster_nor_hashes_a_password``。
    #    ⚠️ 它刻意**不写行**：写的话一个持续探测的攻击者会让这个学号永远锁着（滑动锁），
    #    而一个反复重试的**合法新生**也会把自己一直锁在里面。逐字理由见
    #    :mod:`app.auth.policy` 的模块 docstring 第一节。
    if auth_policy.is_locked(
        session,
        auth_sessions.STUDENT_KIND,
        payload.student_no,
        purpose=auth_policy.PURPOSE_BIND,
    ):
        return error_response(403, "forbidden", _BIND_FORBIDDEN_MESSAGE)
    student = auth_sessions.student_by_login(session, payload.student_no)
    if student is None or student.birth != payload.birth:
        # ⚠️ 两档合成一个 ``or``：这不是「顺便少写一行」，而是**刻意的**——
        # 分成两个 ``if`` 之后，下一个人「顺手给第二档换一句更具体的 message」
        # 就会把「哪些学号在册」泄漏出去。
        # ⚠️ 本档**计数**（Plan 06 Task 10）：它正是要挡的那一档（猜出生日期），
        #    而它与「不在册」共用同一个 403，故计数它不会改坏任何提示
        #    （与登录侧「403 不计数」的取舍相反，逐字理由见本函数 docstring）。
        auth_policy.record_failure(
            session,
            auth_sessions.STUDENT_KIND,
            payload.student_no,
            purpose=auth_policy.PURPOSE_BIND,
            ip=ip,
        )
        return error_response(403, "forbidden", _BIND_FORBIDDEN_MESSAGE)
    if _bind_credential(session, Student, student,
                        payload.password.get_secret_value(),
                        auth_sessions.now()) == 0:
        session.rollback()
        return error_response(
            409,
            PASSWORD_ALREADY_BOUND,
            "这个学号已经绑定过口令了：一个账号只能绑定一次。"
            "⚠️ 本原型不做口令找回，故忘了口令要找教务干事重灌那一行"
            "（把 student.password_hash 置回 NULL）",
        )
    # ⚠️ **不再自己 commit**（Plan 06 Task 10）：record_success 自己 commit，
    #    而那一次 commit 顺带把上面 ``password_hash`` 那一次 UPDATE 一起提交 ——
    #    「绑定落库」与「计数器清零」因此在**同一个**事务里（逐字理由见那个函数）。
    auth_policy.record_success(
        session,
        auth_sessions.STUDENT_KIND,
        payload.student_no,
        purpose=auth_policy.PURPOSE_BIND,
        ip=ip,
    )
    return Response(status_code=204)


@router.post(
    "/api/auth/teachers/bind",
    tags=["auth"],
    status_code=204,
)
def bind_teacher(
    payload: TeacherBindCreate,
    request: Request,
    session: Session = Depends(get_db),
) -> Response:
    """（匿名）教师**首次**绑定口令：工号 + 姓名 + 新口令 → 204。

    与 :func:`bind_student` **逐档同构**（五档、顺序、「两档 403 合成一个 ``or``」、
    以及 **Plan 06 Task 10 起的那一套绑定限流**的理由都相同，故那两整段散文刻意
    不抄第二份），差别只有四格：

    * 验身材料是 **工号 + 姓名**（``teacher`` 表实测**有** ``name`` 列，
      故计划 §3.2 那一格的假设成立）。⚠️ 它与学生那一侧**同档**（本处此前写的是
      「比学生那一侧**弱**：``name`` 也匿名可读」——Plan 05A Task 5 已把
      ``GET /api/teachers`` 收到教职身份，匿名实测 **401**，故那一句今天反了）：
      「读过名册的**教职**」就能绑定任何工号 ——如实记录，与学生那一档合并登记为
      同一条已知局限（spec §13）。⚠️ 「哪些读今天还匿名」的账面只有一个住址：
      :mod:`app.api.routers.catalog` 的模块 docstring，本处不复述第二份（终审 I3）。
    * ``role`` **不由本端点决定**：绑定一个教师不会把他变成管理员，
      ``role`` 只能由 ``POST/PATCH /api/teachers``（**仅管理员**）改。
      ⚠️ 那一格是承重的——若绑定请求体能带 ``role``，任何人就能把自己绑成管理员。
    * message 里点的是「工号」不是「学号」（:data:`_TEACHER_BIND_FORBIDDEN_MESSAGE`），
      ⚠️ 故锁定档回的也是**这一句**（与「材料不符」逐字相同是控制者的裁定，
      而两个端点各自的「那一句」是两句不同的常量）。
    * ⚠️⚠️ **限流的收益在这一侧更小**（如实记，硬规矩 #39）：验身材料是**姓名**，
      而一个读过名册的**教职**本来就看得见全部教师的姓名（``GET /api/teachers`` 的
      ``staff`` 档）—— 对他而言限流挡不住任何东西（他一次就猜中）。
      它挡的是**匿名**调用方的盲猜（常见汉名的组合空间虽然比出生日期大，
      而一个学校的教师工号是 ``T0001``… 这种可枚举的形状，故「工号 + 姓名」
      两个一起猜仍然是一个有限的空间）。⚠️ 而「教职能替任何还没绑定的人抢绑口令」
      这一格是 spec §1.2 第 3/4 条**已接受**的残余风险，本波**不改它**。

    ⚠️ 阈值与登录/学生绑定那一组**是同一组**（``PE_BIND_*``，缺省 3 / 15 / 60）：
    两个端点共用一个用途（``PURPOSE_BIND``），故「哪一组阈值管绑定」这件事
    在全仓只有一个答案。⚠️ 而**键仍然按 ``kind`` 分开**（``teacher`` vs ``student``），
    故锁掉一个工号不会连带锁掉一个学号。
    """
    ensure_acceptable(payload.password.get_secret_value())
    ip = request.client.host if request.client is not None else None
    # ⚠️ **Plan 08 Task 4 的开关档**：与 :func:`bind_student` 里那一处**逐字同形**
    #    （顺序、理由与守卫都住在那一处的注释里，刻意不抄第二份）。
    if not allow_self_bind():
        return error_response(403, "forbidden", _SELF_BIND_DISABLED_MESSAGE)
    # ⚠️ 两个顺序各自承重，逐字理由见 :func:`bind_student` 的同款注释（刻意不抄第二份）。
    if auth_policy.is_locked(
        session,
        auth_sessions.TEACHER_KIND,
        payload.staff_no,
        purpose=auth_policy.PURPOSE_BIND,
    ):
        return error_response(403, "forbidden", _TEACHER_BIND_FORBIDDEN_MESSAGE)
    teacher = auth_sessions.teacher_by_login(session, payload.staff_no)
    if teacher is None or teacher.name != payload.name:
        # ⚠️ 本档**计数**（Plan 06 Task 10），逐字理由见 :func:`bind_student` 的同款注释。
        auth_policy.record_failure(
            session,
            auth_sessions.TEACHER_KIND,
            payload.staff_no,
            purpose=auth_policy.PURPOSE_BIND,
            ip=ip,
        )
        return error_response(403, "forbidden", _TEACHER_BIND_FORBIDDEN_MESSAGE)
    if _bind_credential(session, Teacher, teacher,
                        payload.password.get_secret_value(),
                        auth_sessions.now()) == 0:
        session.rollback()
        return error_response(
            409,
            PASSWORD_ALREADY_BOUND,
            "这个工号已经绑定过口令了：一个账号只能绑定一次。"
            "⚠️ 本原型不做口令找回，故忘了口令要找教务干事重灌那一行"
            "（把 teacher.password_hash 置回 NULL）",
        )
    # ⚠️ **不再自己 commit**：逐字理由见 :func:`bind_student` 的同款注释。
    auth_policy.record_success(
        session,
        auth_sessions.TEACHER_KIND,
        payload.staff_no,
        purpose=auth_policy.PURPOSE_BIND,
        ip=ip,
    )
    return Response(status_code=204)


@router.post(
    "/api/auth/bind-with-token",
    tags=["auth"],
    status_code=204,
)
def bind_with_token(
    payload: TokenBindCreate,
    request: Request,
    session: Session = Depends(get_db),
) -> Response:
    """（匿名）**一次性令牌**首次绑定口令：令牌 + 新口令 → 204。

    ⚠️⚠️ **这是 Plan 08 Task 4 加的那条「更强的路」**：它的全部验身材料就是那一张
    令牌（192 bit 的秘密那一段），而令牌只能由**管理员**签发
    （:func:`issue_bind_token`）。于是「读过名册的教职能替任何未绑定账号抢绑」
    这一格在本端点上**不成立** —— 一个教职读得到 ``birth``，而 ``birth`` 在这里
    **一个字都不参与判定**。

    ⚠️ 而它**不读** :data:`SELF_BIND_ENV_VAR`：开关只管两个自助端点。
    逐字理由见模块 docstring 的「两条绑定路径」那一节第 2 条
    （「可回退」的含义是：先签发令牌、验证流程通了、再把开关关掉，
    中间没有任何一刻是「谁都绑不上」）。

    ------------------------------------------------------------------
    ⚠️⚠️ 七档失败，**顺序是承重的**
    ------------------------------------------------------------------

    * **422 ``unprocessable_value``** —— 口令太短。**排在最前**（纯本地、不碰库），
      与 :func:`bind_student` 的同款裁定逐字相同。
    * **403 ``forbidden``（令牌形状不对 / 选择子查无此行）** —— ⚠️ **一次 PBKDF2 都不跑**：
      :func:`app.auth.bind_tokens.find` 是一次唯一索引上的点查，查不到就当场返回。
      那一格是本设计对「拿一串编造的令牌灌本端点」这格 DoS 的处置，
      与 :func:`app.auth.policy.is_locked` 排在 :func:`verify_password` 之前同一条形状。
      ⚠️ 它**刻意不计数**（两把限流键都需要 ``kind``，而那一格只能从令牌行上读）；
      代价如实记：一个匿名调用方可以无限次打这一档，每次的成本是一次索引未命中。
    * **403 ``forbidden``（锁定档）** —— **两把键任一把锁住**就返回
      （:data:`app.auth.policy.PURPOSE_BIND` 按目标账号、
      :data:`app.auth.policy.PURPOSE_BIND_TOKEN` 按 ``token_id``；
      「两把都算」的逐字理由与「令牌那一把今天严格更宽」的如实记都住在
      :data:`app.auth.policy.PURPOSE_BIND_TOKEN` 的注释里）。
      ⚠️ 它排在 :func:`app.auth.bind_tokens.matches` **之前**，故锁定档不跑 PBKDF2；
      ⚠️ 而它**刻意不写行**（滑动锁那一条，:mod:`app.auth.policy` 的模块 docstring 第一节）；
      ⚠️ 响应体与下面「秘密不对」那一档**逐字相同**（:data:`_BIND_TOKEN_FORBIDDEN_MESSAGE`，
      与登录/自助绑定那两次改判同一条理由：另给一个码就是枚举信号）。
    * **403 ``forbidden``（秘密那一段验不过）** —— 唯一跑 PBKDF2 的一档。
      ⚠️ **本档计数**（两把各写一行）：它正是要挡的那一档（爆一个令牌的秘密）。
    * **409 ``bind_token_spent``** —— 这张令牌**已经用过了**。
    * **403 ``bind_token_expired``** —— 这张令牌**过期了**。
      ⚠️⚠️ 上面两档**刻意可区分**、且**排在验秘密之后**，逐字理由见
      :data:`BIND_TOKEN_SPENT` 的注释（一句话：走到这两档的人**已经持有那张凭据**，
      故告诉他们「它废了」不泄漏任何东西，而不告诉他们会让一个合法新生
      反复重输、然后被锁 60 分钟）。
    * **409 ``password_already_bound``** —— 目标账号已经绑定过了。
      ⚠️ **这一档会 ``rollback``**，而那一次回滚**顺带撤销了上面那一次
      「令牌作废」**：于是一张对着已绑定账号打过去的令牌**没有被烧掉**。
      逐字理由：签发端点**拒绝**给一个已绑定的账号签发（:func:`issue_bind_token`
      的第 3 档），故本档今天只可能由一个**竞态**到达（签发与兑换之间那个账号被绑上了），
      而烧掉一张本来就无用的令牌只会让教务干事以为「我发的那张被用了」。

    ⚠️ **成功后不自动登录**（不回 ``Set-Cookie``），与两个自助端点逐字同一条口径：
    「绑定成功即已认证」会让「令牌泄漏」直接等于「账号被接管」，分开之后攻击者还需要口令。
    前端在 204 之后自己打一次 ``POST /api/auth/login``（``views/auth/Bind.vue``）。

    ⚠️⚠️ **审计连带**：本端点是 ``POST``，故 :func:`app.api.audit.should_record`
    **本来就**认它 —— **七档一律各写一行**审计，本波**一行代码都不用加**。
    ⚠️ 而**令牌明文一个字都不进审计**：:mod:`app.api.audit` 从不读请求体
    （逐字理由在那个模块的 docstring 第三节），``audit_log`` 的 9 列里也没有能装它的位置。
    守卫是 ``tests/api/test_bind_token.py`` 的
    ``test_the_plaintext_token_never_reaches_the_audit_row``（**真的**发一次带令牌的兑换，
    然后把那一行的**全部 9 列**逐列扫一遍）。
    """
    ensure_acceptable(payload.password.get_secret_value())
    ip = request.client.host if request.client is not None else None
    # ① 选择子点查（一次索引；查不到 ⇒ 不跑 PBKDF2、不计数）
    found = auth_bind_tokens.find(session, payload.token.get_secret_value())
    if found is None:
        return error_response(403, "forbidden", _BIND_TOKEN_FORBIDDEN_MESSAGE)
    row = found.row
    # ② 锁定档（两把键；排在验秘密之前 ⇒ 不跑 PBKDF2；刻意不写行）
    if auth_policy.is_locked(
        session, row.kind, row.login, purpose=auth_policy.PURPOSE_BIND
    ) or auth_policy.is_locked(
        session, row.kind, row.token_id, purpose=auth_policy.PURPOSE_BIND_TOKEN
    ):
        return error_response(403, "forbidden", _BIND_TOKEN_FORBIDDEN_MESSAGE)
    # ③ 验秘密（本端点唯一那一次 PBKDF2；⚠️ 复用 app.auth.passwords，不写第二个）
    if not auth_bind_tokens.matches(found):
        auth_policy.record_failure(
            session, row.kind, row.login,
            purpose=auth_policy.PURPOSE_BIND, ip=ip,
        )
        auth_policy.record_failure(
            session, row.kind, row.token_id,
            purpose=auth_policy.PURPOSE_BIND_TOKEN, ip=ip,
        )
        return error_response(403, "forbidden", _BIND_TOKEN_FORBIDDEN_MESSAGE)
    # ④/⑤ 已用过 / 已过期（两档各自可区分；⚠️ 都排在验秘密之后）
    if row.used_at is not None:
        return error_response(
            409,
            BIND_TOKEN_SPENT,
            "这个绑定令牌已经用过了：一张令牌只能兑换一次。"
            "⚠️ 若你刚刚才绑定成功，请直接登录；真的忘了口令，"
            "要找教务干事把那一行的 password_hash 置回 NULL 再重签一张令牌"
            "（本原型不做口令找回）",
        )
    if auth_bind_tokens.is_expired(row):
        return error_response(
            403,
            BIND_TOKEN_EXPIRED,
            f"这个绑定令牌已经过期了（它的有效期到 {row.expires_at:%Y-%m-%d %H:%M}，"
            f"签发于 {row.issued_at:%Y-%m-%d %H:%M}）。"
            "⚠️ 请找教务干事重签一张：过期令牌不能续期，而本波**没有**撤销端点",
        )
    # ⑥ 回查 subject 行（⚠️ 令牌行上没有外键，故「签发之后账号被删掉」只能在这里发现）
    if row.kind == auth_sessions.STUDENT_KIND:
        subject = auth_sessions.student_by_login(session, row.login)
        model: "type[Student] | type[Teacher]" = Student
    else:
        subject = auth_sessions.teacher_by_login(session, row.login)
        model = Teacher
    if subject is None:
        # ⚠️ 与「令牌不正确」共用同一档：一个持有真令牌的人得到这一句是**困惑的**
        #    （如实记，硬规矩 #39），而给它第三个可区分的码等于把
        #    「这个学号还在不在册」交给一个匿名调用方 —— 那正是
        #    :func:`bind_student` 里「两档 403 合成一个 or」那条裁定要防的形状。
        #    ⚠️ 本档今天**几乎不可达**：签发端点要求目标在册，
        #    而删一个学生是仅管理员的操作。
        return error_response(403, "forbidden", _BIND_TOKEN_FORBIDDEN_MESSAGE)
    # ⑦ 作废这一张（⚠️ 判据是 rowcount，不 commit —— 与下面那一次口令写入同一个工作单元）
    if not auth_bind_tokens.consume(session, row):
        return error_response(
            409,
            BIND_TOKEN_SPENT,
            "这个绑定令牌已经用过了：一张令牌只能兑换一次。"
            "⚠️ 本档是**并发**那一支（另一个请求刚刚把它用掉了），"
            "判据是那一次 UPDATE 的影响行数是 0",
        )
    if _bind_credential(session, model, subject,
                        payload.password.get_secret_value(),
                        auth_sessions.now()) == 0:
        # ⚠️ rollback 顺带撤销上面那一次「作废」（逐字理由见本函数 docstring 最后一档）
        session.rollback()
        return error_response(
            409,
            PASSWORD_ALREADY_BOUND,
            "这个账号已经绑定过口令了：一张令牌换不来第二次绑定。"
            "⚠️ 本原型不做口令找回，故忘了口令要找教务干事重灌那一行"
            "（把 password_hash 置回 NULL）再重签一张令牌",
        )
    # ⚠️ **不再自己 commit**（与 :func:`bind_student` 逐字同一条口径）：
    #    record_success 自己 commit，而那一次 commit 顺带把「口令哈希落库」与
    #    「令牌作废」两次写入一起提交 —— 三件事因此在**同一个**事务里。
    #    ⚠️ 两把键 ⇒ **两次** record_success ⇒ **两次** commit（如实记）：
    #    第一次就把业务写入提交了，第二次只清另一把计数器。⚠️ 顺序是承重的：
    #    先清令牌那一把（它只影响本端点），再清目标账号那一把
    #    （它与自助绑定共用，故它是「这个账号的绑定计数器干净了」那一格）。
    auth_policy.record_success(
        session, row.kind, row.token_id,
        purpose=auth_policy.PURPOSE_BIND_TOKEN, ip=ip,
    )
    auth_policy.record_success(
        session, row.kind, row.login,
        purpose=auth_policy.PURPOSE_BIND, ip=ip,
    )
    return Response(status_code=204)


@router.post(
    "/api/auth/bind-tokens",
    tags=["auth"],
    status_code=201,
    response_model=BindTokenIssuedRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def issue_bind_token(
    payload: TokenIssueCreate,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """（**仅管理员**）签发一张一次性绑定令牌 → **201** + 明文令牌（**只回这一次**）。

    ------------------------------------------------------------------
    ⚠️⚠️ 身份档与 :func:`app.api.routers.audit.list_audit_logs` **逐字相同**
    ------------------------------------------------------------------

    同一个 ``Security(TEACHER_STAFF_NO_SCHEME)`` 声明 + 同一个
    :func:`app.api.deps.current_teacher` + 同一个 :func:`app.api.deps.require_admin`。
    四格矩阵（匿名 **401** / 学生 cookie **403** / 在册教师 **403** / 管理员 **201**）
    逐字照那个模块的 docstring 第二节，本处不抄第二份。
    ⚠️ 而那一格是**承重的**：本端点产出的是一格**凭据**，
    它的权限面**不许**比「能改名册」更宽 —— 而改名册（``POST /api/students``）
    正是 ``require_admin``，故两者重合。⚠️ 派单 §2 第 7 条 ⑥ 要的就是这一格
    （教师/学生/匿名各一发 → 403/401），守卫是
    ``tests/api/test_bind_token.py`` 的 ``test_only_an_admin_can_issue_a_bind_token``。

    ------------------------------------------------------------------
    ⚠️⚠️ 三档拒绝，**顺序是承重的**
    ------------------------------------------------------------------

    * **404 ``not_found``** —— 这个学号/工号**不在册**。
      ⚠️ 它**排在** :func:`app.auth.bind_tokens.issue` 之前，于是「一个超宽的 ``login``」
      **根本走不到那一列**（那一格的宽度收口点因此是这一次回查，而不是一个截断函数；
      守卫是 ``test_an_overlong_login_never_reaches_the_bind_token_row``）。
      ⚠️ 而本端点**可以**用 404（两个自助端点刻意用 403 合并「不在册」与「材料不符」）：
      调用方是**已验身的管理员**，他本来就读得到整份名册，故「这个学号在不在册」
      对他不是一个秘密 —— 与 :func:`app.api.deps.require_scope` 那条
      「不区分 403 与 404」的裁定**相反**，而相反是对的（那一条防的是匿名枚举）。
    * **409 ``password_already_bound``** —— 这个账号**已经绑定过口令了**。
      ⚠️⚠️ **这是派单 §2 第 7 条 ⑦ 点名要裁定的那一格**，裁定是**拒发**，三条理由：
      ① 一张发给已绑定账号的令牌**永远兑换不了**（:func:`_bind_credential` 只对
      ``password_hash IS NULL`` 的行放行），故它是一张**什么也换不来、却一直活着 7 天**
      的凭据 —— 发出去只有坏处；② 它当场抓住一个常见的手误
      （「我上周不是已经给张三发过一张了吗」）；③ 它把「重置口令」这个流程
      钉成本仓既有的那一条：先把 ``password_hash`` 置回 ``NULL``
      （两个自助端点的 409 message 逐字教的就是这一步），**再**签发 ——
      于是「签发成功」这件事恒等于「这个账号此刻确实可以被绑定」。
      ⚠️ 代价（如实记）：重置口令因此是**两步**而不是一步，
      而第一步今天只能由一个能直接写库的运维做（本仓没有「重置口令」端点，
      Plan 05A 起就是如此，已登记为待清扫）。
    * **⚠️ 而「这个账号已经有一张未使用的令牌」刻意 *不* 是一档拒绝**（本 Task 的裁定）。
      派单没点名它，故把判定与理由写在这里：**允许**一个账号同时有多张未使用的令牌。
      三条理由：① 拒发的话，「学生把令牌弄丢了」这一档会让教务干事**被卡住 7 天**
      ——而本波**没有**撤销端点（撤销要第 4 个端点 + 一条「谁能撤销谁签的」的权限判定，
      超出本 Task 范围，已登记为待清扫）；② 多张令牌**不放宽**任何一格安全性：
      兑换那一次仍然要一份验得过的秘密，而每一张都是 192 bit、一次性、7 天有效；
      ③ 它把「重签」变成教务干事在迎新现场**当场能做**的动作，
      而那正是这个功能存在的场景。
      ⚠️ 代价（如实记）：一个手滑的教务干事可以给同一个学号发五张令牌，
      五张都活着、任意一张都能兑换 —— 页面上看得见（:func:`list_bind_tokens`
      会把五行都列出来，``used_at`` 与 ``expires_at`` 两格都在），故它是**可见的**。

    ------------------------------------------------------------------
    ⚠️⚠️ 明文令牌**只在这一个响应体里出现一次**
    ------------------------------------------------------------------

    库里那一格是 :func:`app.auth.passwords.hash_password` 的产出
    （⚠️ **复用口令那一套 PBKDF2 口径**，迭代次数 600 000、盐 16 B、自描述四段串，
    本模块**一个参数都不写**）。⚠️ 于是签发之后：

    * ``GET /api/auth/bind-tokens`` **读不回**它（:class:`BindTokenRead` 没有那一格）；
    * 库里**扫不出**它（守卫扫全库 30 张表的每一列，逐字见
      ``test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table``）；
    * 审计里**没有**它（:mod:`app.api.audit` 从不读请求体**也从不读响应体**）。

    ⚠️ 它**刻意不设 ``Location`` 头**（与泛型工厂的 ``create_row`` 不同）：
    那一格的约定是指向 read-one 端点，而本端点**没有** read-one
    （逐字理由见 :class:`app.api.schemas.auth.BindTokenRead` 的 docstring：
    一行令牌的可读投影只有列表那一份）。⚠️ 于是「建出来的那一行 id 是几」
    在**响应体**里（``id`` 那一格），与 :class:`app.db.models.audit.AuditLog`
    的 ``target`` 那条已知局限同族（审计答不出新建行的 id）。
    """
    require_admin(session, staff_no)
    if payload.kind == auth_sessions.STUDENT_KIND:
        subject = auth_sessions.student_by_login(session, payload.login)
        bound = None if subject is None else subject.password_hash
    else:
        subject = auth_sessions.teacher_by_login(session, payload.login)
        bound = None if subject is None else subject.password_hash
    if subject is None:
        return error_response(
            404,
            "not_found",
            f"{'学号' if payload.kind == auth_sessions.STUDENT_KIND else '工号'} "
            f"{payload.login!r} 不在名册上：绑定令牌只能发给一个**已在册**的账号"
            f"（建行册走 POST /api/{'students' if payload.kind == auth_sessions.STUDENT_KIND else 'teachers'}，"
            f"同样仅管理员）",
        )
    if bound is not None:
        return error_response(
            409,
            PASSWORD_ALREADY_BOUND,
            f"{'学号' if payload.kind == auth_sessions.STUDENT_KIND else '工号'} "
            f"{payload.login!r} 已经绑定过口令了：一张发给它的令牌**永远兑换不了**"
            f"（绑定只对 password_hash IS NULL 的行放行），故本端点拒发。"
            f"⚠️ 要重置这个账号的口令，先把它那一行的 password_hash 置回 NULL、"
            f"再回来签发（本仓今天没有「重置口令」端点，已登记为待清扫）",
        )
    row, plain = auth_bind_tokens.issue(
        session, kind=payload.kind, login=payload.login, issued_by=staff_no
    )
    return {
        "id": row.id,
        "kind": row.kind,
        "login": row.login,
        "token": plain,
        "issued_at": row.issued_at,
        "expires_at": row.expires_at,
        "issued_by": row.issued_by,
    }


@router.get(
    "/api/auth/bind-tokens",
    tags=["auth"],
    response_model=BindTokenPageRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def list_bind_tokens(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    page: Page = Depends(),
) -> dict[str, object]:
    """（**仅管理员**）已签发令牌的一页：四个信封键，``items`` 按 ``id DESC``（**最新在前**）。

    ⚠️ 身份档与 :func:`issue_bind_token` **逐字相同**（同一个 ``Security`` 声明 +
    :func:`app.api.deps.current_teacher` + :func:`app.api.deps.require_admin`），
    而它与 :func:`app.api.routers.audit.list_audit_logs` 也逐字相同 ——
    故「能签发令牌的人」与「能看令牌台账的人」是**同一批人**。
    ⚠️ 那一格是**要的**：本端点回的是「哪些账号此刻有一张活着的凭据」，
    它的敏感度不低于「谁改了名册」（后者也要管理员）。

    ⚠️⚠️ **响应体里没有 ``token``、也没有 ``token_hash``**：
    :class:`app.api.schemas.auth.BindTokenRead` 是 9 列减去那两列，
    逐字理由在那个模型的 docstring 里。⚠️ 于是「明文只出现一次」在**读侧**也成立
    （守卫是 ``test_only_the_issuance_contract_carries_the_plaintext_and_no_contract_carries_the_hash``
    与 ``test_the_listing_never_returns_the_plaintext_nor_the_hash``）。

    ⚠️ **``ORDER BY id DESC``**（不是 ``issued_at DESC``），理由与
    :func:`app.api.routers.audit.list_audit_logs` 逐字相同：``id`` 是
    ``INTEGER PRIMARY KEY`` = rowid 别名，逆序扫主键本身就是一次索引扫描；
    而本表**只有一个写入方**（:func:`app.auth.bind_tokens.issue`）与**一个时钟**
    （:func:`app.auth.sessions.now`），故 rowid 的递增序就是签发时刻的递增序。
    ⚠️ ``ix_bind_token_kind_login_expires_at`` 服务的是签发端点那一句
    「这个账号还有几张没过期」，**不是**本端点。

    ⚠️ **它是一格敏感读**（进 :data:`app.api.read_audit.READ_ROUTES`，
    归类 ``CREDENTIAL_STATE``）：本端点披露的是「**哪些具名账号**此刻有一张活着的
    绑定凭据」，而那正是抢绑调查里要问的那一句。⚠️ 于是它**自己喂自己**
    （管理员翻一次台账，读审计多一行）—— 与 ``GET /api/audit-logs`` 同一条取舍，
    那一格的逐字理由与「它有界」的论证住在
    :data:`app.api.read_audit.READ_CLASSES` 的 ``AUDIT_TRAIL`` 那一条里。

    ⚠️ **``total`` 与 ``items`` 走同一个 ``WHERE``**：本端点今天**没有过滤参数**
    （故 ``WHERE`` 恒为空），⚠️ 而那一句仍然写下来是因为它是那一格的口径
    （:func:`app.api.crud._list_page` 的 docstring）——加第一个过滤参数的人
    必须让两者一起加。⚠️ 刻意**不加**过滤参数（与
    :class:`app.api.schemas.audit.AuditLogFilter` 同一条「别过度设计」的口径）：
    本表的量级是「一学期几十到几百行」，一次 ``LIMIT 200`` 就够翻。
    """
    require_admin(session, staff_no)
    total = int(session.scalar(select(func.count()).select_from(BindToken)) or 0)
    rows = session.scalars(
        select(BindToken)
        .order_by(BindToken.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    return {
        "items": [
            BindTokenRead.model_validate(row).model_dump() for row in rows
        ],
        "total": total,
        "limit": page.limit,
        "offset": page.offset,
    }


def _identity_body(identity: Identity) -> dict[str, object]:
    """:class:`~app.auth.sessions.Identity`（五格）→ ``SessionIdentityRead``（六格）。

    ⚠️ **五格变六格的那一格是 ``login`` 被拆成两个**（``student_no`` / ``staff_no``，
    互斥、另一个为 ``None``）：前端要按 ``kind`` 显示「学号」或「工号」两个不同的
    中文标签，而一个字段名给不出标签。逐字理由见
    :class:`app.api.schemas.auth.SessionIdentityRead` 的 docstring。

    ⚠️ 它是 ``login`` 与 ``me`` 两个端点**共用**的唯一投影（两个端点的响应体因此
    逐字同形），故「加一个字段」只有一个地方要改。
    """
    return {
        "kind": identity.kind,
        "id": identity.subject_id,
        "name": identity.name,
        "role": identity.role,
        "student_no": identity.login if identity.kind == auth_sessions.STUDENT_KIND else None,
        "staff_no": identity.login if identity.kind == auth_sessions.TEACHER_KIND else None,
    }


@router.post(
    "/api/auth/login",
    tags=["auth"],
    response_model=SessionIdentityRead,
)
def login(
    payload: LoginCreate,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """（匿名）口令登录 → ``Set-Cookie`` + 响应体回「我是谁」。

    ⚠️ **登录失败的两档必须区分**（计划 §3.3 逐字要求）：

    * **403 ``password_not_bound``** —— 这个学号/工号**在不在册**、或**在册但没绑口令**。
      用户该去 ``/bind``。
    * **401 ``invalid_credentials``** —— 绑过、而口令不对。用户该重输。

    ⚠️ **这确实泄漏了「这个学号在不在册」**——控制者裁定**接受**（终审 I3 之后
    理由从 3 条变成 **2 条**，而**裁定本身不变**）：
    ① 原型不做防枚举；② 绑定流程本身就需要这个信号（不然用户不知道自己是
    「没注册」还是「口令错」，而两者要的下一步动作相反）；
    ③ ⚠️ **原来的第三条今天已经断了**：它逐字是「``GET /api/students`` 今天就匿名
       返回全部 60 人，故这个信号本来就是公开的」，而 Plan 05A Task 5 已把那 4 个名册读
       收到教职身份（匿名实测 **401**）→ 这个信号**不再**是公开的。
       换成实测过的一条：枚举面从「匿名」缩到了「**已登录的教职**」，而一个能登录成
       教职的人本来就读得到整份名册（含 ``birth``），故本端点对他**没有多给一个比特**；
       对匿名调用方，泄漏的仍然只是「这一串在不在册」这一个比特，而①②已经裁定它可接受。
    已写进 spec 的已知局限。⚠️ 「哪些读今天还匿名」的账面只有一个住址：
    :mod:`app.api.routers.catalog` 的模块 docstring（那一次重裁的**逐格**结果也在那里），
    本处不复述第二份（终审 I3）。

    ⚠️ **两档的 ``message`` 也因此刻意不同**（与 :func:`bind_student` 的
    「两档 403 合成一句」相反）：那里的两档要**不可区分**（防枚举在册名单），
    这里的两档要**可区分**（引导用户走对下一步）。同一种「403」在两个端点上
    给出相反的口径，故两处各写一段散文说明，刻意不合并。

    ------------------------------------------------------------------
    ⚠️⚠️ **Plan 06 Task 3 起本端点有登录限流与锁定**（此前逐字写着「不做」）
    ------------------------------------------------------------------

    本处此前的那段 ⚠️ 逐字是「**不做登录失败计数 / 账号锁定**（计划 §1 的非目标逐字列了它）」，
    并如实记了它的两条代价：① 一个知道学号的人可以**无限次**试口令；
    ② PBKDF2 的 600 000 次迭代意味着服务端每次尝试要花 ~0.3 s，于是「试口令」
    同时是一个**廉价的 CPU DoS**（一个请求换服务端 0.3 秒）。
    Plan 06 §3 把那一条非目标推翻（用户 2026-10-13 裁定：这是要交付给甲方的产品），
    **两条代价同时被解掉**：锁定档在 :func:`app.auth.policy.is_locked` 就返回了，
    一次 ``verify_password`` 都不跑。

    三格实现口径（逐字理由各自只有一个住址，本处不复述）：

    * **阈值是配置**：``5`` 次失败 / ``15`` 分钟窗口 / 锁 ``15`` 分钟，
      三格各有环境变量（``PE_LOGIN_MAX_FAILS`` / ``PE_LOGIN_WINDOW_MIN`` /
      ``PE_LOGIN_LOCK_MIN``）。所有者是 :mod:`app.auth.policy`。
    * **锁内那一档回 ``401 invalid_credentials``、与正常失败逐字相同**
      （:data:`_INVALID_CREDENTIALS_MESSAGE`）——**不是** 423 / 429。
      计划 §3 原文写的是后者，控制者改判，逐字理由见
      :mod:`app.auth.policy` 的模块 docstring 第二节。
      ⚠️ 代价：被锁的**合法用户**在锁定期内得不到任何提示（他看到的还是「口令不正确」），
      已写进 spec 的已知局限；可见性留给 Plan 06 Task 5 的 ``audit_log``。
    * **只有「口令验不过」那一档计数**；``403 password_not_bound`` **一行都不写**
      （:mod:`app.auth.policy` 的模块 docstring 第三节：计数它不会挡住任何一次口令猜测，
      而它会把一个把学号打错五次的新生从「请先绑定」变成「口令不正确」——
      一句把他支去反复重输的谎话）。
    * **成功登录清零**：:func:`app.auth.policy.record_success` 删掉这个标识的全部行、
      再写一行 ``ok=True``（同一个事务）。

    ⚠️ **``request`` 这个形参是 Task 3 加的**，只为拿一格 ``request.client.host``
    写进 ``login_attempt.ip``。⚠️ 它**不进 OpenAPI**（FastAPI 对 ``Request`` 标注特殊处理），
    故「路径 / 操作数 / 挂 security 的操作数」三格数字一个都没变。
    ⚠️ **IP 不参与限流判定**（参与的话攻击者换一个出口 IP 就绕过），它只是事后线索；
    ``request.client`` 在某些 ASGI 部署下是 ``None``，故那一格可空。

    ⚠️ **不设 ``Secure``（除非 ``PE_ENV=production``）**、``SameSite=Lax``、
    ``Path=/``、``HttpOnly``、**不设 ``Domain``**：六个参数只有一个住址
    （:func:`app.auth.sessions.cookie_kwargs`），逐格理由见那个函数的 docstring。
    """
    ip = request.client.host if request.client is not None else None
    # ⚠️ 锁定档排在**最前**：它既不查 subject 行、也不跑 PBKDF2，
    #    故它是那个「廉价 CPU DoS」的解药（一个请求换一次索引扫描，不是一次 0.3 s 的哈希）。
    # ⚠️ 它刻意**不写行**：写的话一个持续探测的攻击者会让这个账号永远锁着（滑动锁），
    #    而一个反复重试的**合法用户**也会把自己一直锁在里面。逐字理由见
    #    :mod:`app.auth.policy` 的模块 docstring 第一节。
    if auth_policy.is_locked(session, payload.kind, payload.login):
        return error_response(401, INVALID_CREDENTIALS, _INVALID_CREDENTIALS_MESSAGE)
    if payload.kind == auth_sessions.STUDENT_KIND:
        subject = auth_sessions.student_by_login(session, payload.login)
    else:
        subject = auth_sessions.teacher_by_login(session, payload.login)
    if subject is None or subject.password_hash is None:
        return error_response(
            403,
            PASSWORD_NOT_BOUND,
            f"这个{'学号' if payload.kind == auth_sessions.STUDENT_KIND else '工号'}"
            f"还没有绑定口令（或不在名册上）：请先走绑定流程"
            f"（POST /api/auth/{'students' if payload.kind == auth_sessions.STUDENT_KIND else 'teachers'}/bind）",
        )
    if not verify_password(payload.password.get_secret_value(), subject.password_hash):
        auth_policy.record_failure(session, payload.kind, payload.login, ip=ip)
        return error_response(401, INVALID_CREDENTIALS, _INVALID_CREDENTIALS_MESSAGE)
    # ⚠️ 清零排在 issue 之前：record_success 与 issue 各自 commit，
    #    故顺序颠倒的话「会话已签发、而计数器还没清」的窗口里另一个请求会看到旧的失败数。
    auth_policy.record_success(session, payload.kind, payload.login, ip=ip)

    role = (
        auth_sessions.STUDENT_ROLE
        if payload.kind == auth_sessions.STUDENT_KIND
        else subject.role
    )
    token = auth_sessions.issue(
        session, kind=payload.kind, subject_id=subject.id, role=role
    )
    # ⚠️⚠️ **Plan 06 Task 5**：把「这一次登录是谁」交给审计（:func:`note_subject`）。
    #    ⚠️ **只有成功那一档写它**：失败的三档（锁定 / ``password_not_bound`` /
    #    ``invalid_credentials``）一律留 ``anonymous`` —— 那**正是**派单 §1 第 4 条要的：
    #    「鉴权失败也要记（subject 未知 → ``anonymous``），否则『谁在撞门』恰恰查不到」。
    #    ⚠️ 而在失败档把 ``payload.login`` 写进 ``staff_no`` / ``subject_id`` 是**错的**：
    #    那一格是**调用方自称**的串，验身没通过，把它记成「某教师做的」等于让审计
    #    替一个撞门的人作证（他只要填别人的工号就能把审计指向别人）。
    #    ⚠️ 本函数**不读请求体之外的任何东西**来填这一格：``subject`` 那一行是上面
    #    按口令校验通过之后查出来的，故它是**已验身**的身份。
    note_subject(
        request,
        AuditSubject(
            kind=payload.kind,
            subject_id=subject.id,
            staff_no=payload.login
            if payload.kind == auth_sessions.TEACHER_KIND
            else None,
        ),
    )
    # ⚠️ issue 自己已经 commit 了（会话行必须在响应发出之前落库），故这里不再 commit。
    response.set_cookie(**auth_sessions.cookie_kwargs(token))
    return _identity_body(
        Identity(
            kind=payload.kind,
            subject_id=subject.id,
            role=role,
            name=subject.name,
            login=payload.login,
        )
    )


@router.post(
    "/api/auth/logout",
    tags=["auth"],
    status_code=204,
    dependencies=[Security(SESSION_COOKIE_SCHEME)],
)
def logout(
    request: Request,
    _identity: Identity = Depends(current_session),
    session: Session = Depends(get_db),
) -> Response:
    """（cookie 会话）**吊销**那一行 + 让 cookie 过期 → 204。

    ⚠️ **登出是真的失效**（本计划选服务端会话表而不是签名 cookie 的**第一条理由**）：
    :func:`app.auth.sessions.revoke` 写 ``revoked_at`` 并 commit，于是被偷走的 cookie
    在登出之后**立刻**不能用（守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_an_old_cookie_stops_working_the_moment_the_user_logs_out``）。
    签名 cookie 的「登出」只是客户端把那串丢掉，被偷的那一份在 ``exp`` 之前照旧有效。

    ⚠️⚠️ **cookie 是设在「本函数返回的那一个 ``Response`` 实例」上的，不是设在注入的
    ``response`` 参数上**（本函数因此没有 ``response: Response`` 这个形参）。
    这是承重的：FastAPI 只在端点**返回非 ``Response`` 对象**时才把注入的那个
    ``Response`` 的 headers 合并进最终响应（``get_request_handler`` 的 else 那一支
    才有 ``response.headers.raw.extend(sub_response.headers.raw)``）。
    于是「注入 ``response`` + ``set_cookie`` + 返回 ``Response(status_code=204)``」
    这个看起来很自然的写法会**静默丢掉那个 ``Set-Cookie``**——表现为
    「登出成功了、服务端那一行也吊销了，而浏览器的 cookie 还在」，
    于是下一次请求带着一个已吊销的 cookie 撞 401，而不是干净地回到登录页。
    ⚠️ ``login`` 那一侧**不受影响**：它返回 ``dict`` + ``response_model``，
    走的正是会合并 headers 的那一支。

    ⚠️ **它只吊销当前这一个会话**，不是「把这个人的全部会话都踢掉」：
    多设备登录是合法状态，而「一键登出全部设备」要一个 ``revoke_all_for(kind, id)``，
    原型不做（如实记为待清扫）。

    ⚠️ **幂等**：``revoke`` 对一个已吊销的 token 返回 ``False`` 而不报错，
    服务端因此不会因为重复登出而改坏数据。⚠️ 但**第二次请求会先撞 401**——
    :func:`app.api.deps.current_session` 在吊销之后已经解析不出身份了。
    故「幂等」的准确含义是前者，而不是「重复登出回同一个码」。如实记录（硬规矩 #39）。
    """
    del _identity  # ⚠️ 只用来当闸门（没有会话 → 401），token 从 cookie 再取一次
    auth_sessions.revoke(
        session, request.cookies.get(auth_sessions.SESSION_COOKIE_NAME)
    )
    cleared = Response(status_code=204)
    cleared.set_cookie(**auth_sessions.expired_cookie_kwargs())
    return cleared


@router.get(
    "/api/auth/me",
    tags=["auth"],
    response_model=SessionIdentityRead,
    dependencies=[Security(SESSION_COOKIE_SCHEME)],
)
def me(identity: Identity = Depends(current_session)) -> dict[str, object]:
    """（cookie 会话）我是谁：六格（``kind`` / ``id`` / ``name`` / ``role`` + 学号或工号）。

    ⚠️ 与 ``POST /api/auth/login`` 的响应体**逐字同形**（同一个
    :class:`app.api.schemas.auth.SessionIdentityRead`、同一个 :func:`_identity_body`），
    故前端「登录后立刻拿到的那份」与「刷新页面时重新问一次拿到的那份」不可能漂开。
    先例是 ``dashboard._student_home_response``（学生侧与教师侧的首页逐字同形）。

    ⚠️ **它刻意不回落请求头**（:func:`app.api.deps.current_session` 的 docstring
    逐字写了理由）：一个由请求头伪造出来的「我是谁」回不出 ``role``
    （请求头那一档没有 role），于是前端的路由守卫
    （``/admin/*`` 要 ``role == 'admin'``）会拿到一个 ``undefined``，
    而 ``undefined == 'admin'`` 是 ``false``——失效方向是安全的（少给权限），
    但形状是「管理员进了 ``/admin`` 看到一句『你不是管理员』」，离真因很远。

    ⚠️ **它是本仓第 12 个挂 ``security`` 的 GET**（此前 11 个），故
    ``tests/api/test_prescription_api.py`` 那条全仓级断言的三格数字
    （路径模板 / 操作数 / 挂 security 的操作数）都由 Plan 05A 改写。
    """
    return _identity_body(identity)
