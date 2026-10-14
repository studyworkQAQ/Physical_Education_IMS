"""``/api/auth/*``：**五个**端点（Plan 05A Task 1）。

==============================  ======  ==============  ==========================
路径                             码      身份             语义
==============================  ======  ==============  ==========================
``POST /api/auth/students/bind``  204   **匿名**         学号 + 出生日期 + 新口令 → 首次绑定
``POST /api/auth/teachers/bind``  204   **匿名**         工号 + 姓名 + 新口令 → 首次绑定
``POST /api/auth/login``          200   **匿名**         口令 → ``Set-Cookie`` + 我是谁
``POST /api/auth/logout``         204   **cookie 会话**  吊销那一行 + ``Set-Cookie`` 过期
``GET  /api/auth/me``             200   **cookie 会话**  我是谁（六格）
==============================  ======  ==============  ==========================

⚠️ **是 5 个不是 6 个**（计划自审第 4 条自己抓出来的数错）：另一个会话里的
《实施计划 05》数出 6 个是因为它有 **refresh** 令牌；本计划**不做 refresh**，
改用**滑动过期**（:func:`app.auth.sessions.resolve` 每次把 ``expires_at`` 往后推），
故「两种令牌」那一套整个不存在。

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

from fastapi import APIRouter, Depends, Request, Response, Security
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.audit import AuditSubject, note_subject
from app.api.deps import SESSION_COOKIE_SCHEME, current_session, get_db
from app.api.errors import error_response
from app.api.schemas.auth import (
    LoginCreate,
    SessionIdentityRead,
    StudentBindCreate,
    TeacherBindCreate,
)
from app.auth import policy as auth_policy
from app.auth import sessions as auth_sessions
from app.auth.passwords import ensure_acceptable, hash_password, verify_password
from app.auth.sessions import Identity
from app.db.models.organisation import Student, Teacher

__all__ = ["PASSWORD_ALREADY_BOUND", "PASSWORD_NOT_BOUND", "INVALID_CREDENTIALS", "router"]

router = APIRouter()

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
