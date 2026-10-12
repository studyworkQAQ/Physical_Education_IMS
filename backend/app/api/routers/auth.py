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

from app.api.deps import SESSION_COOKIE_SCHEME, current_session, get_db
from app.api.errors import error_response
from app.api.schemas.auth import (
    LoginCreate,
    SessionIdentityRead,
    StudentBindCreate,
    TeacherBindCreate,
)
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
    session: Session = Depends(get_db),
) -> Response:
    """（匿名）学生**首次**绑定口令：学号 + 出生日期 + 新口令 → 204。

    ⚠️ **这是「名册已存在 + 首次绑定密码」，不是自助注册**（用户 2026-10-12 逐字裁定）：
    本端点**不建学生行**，学生行由管理员经 ``POST /api/students`` 建
    （Plan 05A Task 2 之后**仅管理员**）。故一个不在册的学号在这里是 403、不是 201。

    四档失败，**顺序是承重的**：

    * **422 ``unprocessable_value``** —— 口令太短（< 8 个字符）。⚠️ 排在最前：
      它是纯本地判定、不碰库，故一次弱口令尝试**不会**变成一次数据库查询
      （一个不需要账号就能打出来的 DoS 面）。
    * **403 ``forbidden``** —— 学号不在册 **或** 出生日期不符。
      ⚠️ **两档共用一个 code + 一句 message**（:data:`_BIND_FORBIDDEN_MESSAGE`）：
      区分它们等于把「哪些学号在册」逐个字告诉一个匿名调用方。
      ⚠️ 而**这一档的防护强度是有限的**，因为验身材料本身匿名可读
      （``GET /api/students`` 今天就返回全部 60 人的 ``birth``）——
      计划 §3.2 自己点出了这个权衡，收紧它是 Task 5 的活。
    * **409 ``password_already_bound``** —— 已经绑定过了。
      ⚠️ **它排在 403 之后**：反过来就会让一个不知道出生日期的攻击者
      读出「这个学号绑定过了没有」。
    * **422 ``request_validation_failed``** —— 请求体缺字段或 ``birth`` 不是合法日期。

    ⚠️ **成功后不自动登录**（不回 ``Set-Cookie``）：绑定与登录是两件事，
    前端在 204 之后自己打一次 ``POST /api/auth/login``。理由是「绑定成功即已认证」
    会让「验身材料泄漏」直接等于「账号被接管」，而分开之后攻击者还需要口令。
    """
    ensure_acceptable(payload.password.get_secret_value())
    student = auth_sessions.student_by_login(session, payload.student_no)
    if student is None or student.birth != payload.birth:
        # ⚠️ 两档合成一个 ``or``：这不是「顺便少写一行」，而是**刻意的**——
        # 分成两个 ``if`` 之后，下一个人「顺手给第二档换一句更具体的 message」
        # 就会把「哪些学号在册」泄漏出去。
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
    session.commit()
    return Response(status_code=204)


@router.post(
    "/api/auth/teachers/bind",
    tags=["auth"],
    status_code=204,
)
def bind_teacher(
    payload: TeacherBindCreate,
    session: Session = Depends(get_db),
) -> Response:
    """（匿名）教师**首次**绑定口令：工号 + 姓名 + 新口令 → 204。

    与 :func:`bind_student` **逐档同构**（四档、顺序、以及「两档 403 合成一个 ``or``」
    的理由都相同，故那一整段散文刻意不抄第二份），差别只有三格：

    * 验身材料是 **工号 + 姓名**（``teacher`` 表实测**有** ``name`` 列，
      故计划 §3.2 那一格的假设成立）。⚠️ 它比学生那一侧**弱**：``name`` 也匿名可读
      （``TeacherRead`` 含它），故「读过 ``GET /api/teachers`` 的人」就能绑定任何工号
      ——如实记录，与学生那一档合并登记为同一条已知局限（spec §13，Task 5 收紧）。
    * ``role`` **不由本端点决定**：绑定一个教师不会把他变成管理员，
      ``role`` 只能由 ``POST/PATCH /api/teachers``（**仅管理员**）改。
      ⚠️ 那一格是承重的——若绑定请求体能带 ``role``，任何人就能把自己绑成管理员。
    * message 里点的是「工号」不是「学号」。
    """
    ensure_acceptable(payload.password.get_secret_value())
    teacher = auth_sessions.teacher_by_login(session, payload.staff_no)
    if teacher is None or teacher.name != payload.name:
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
    session.commit()
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
    response: Response,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """（匿名）口令登录 → ``Set-Cookie`` + 响应体回「我是谁」。

    ⚠️ **登录失败的两档必须区分**（计划 §3.3 逐字要求）：

    * **403 ``password_not_bound``** —— 这个学号/工号**在不在册**、或**在册但没绑口令**。
      用户该去 ``/bind``。
    * **401 ``invalid_credentials``** —— 绑过、而口令不对。用户该重输。

    ⚠️ **这确实泄漏了「这个学号在不在册」**——控制者裁定**接受**，三条理由：
    ① 原型不做防枚举；② 绑定流程本身就需要这个信号（不然用户不知道自己是
    「没注册」还是「口令错」，而两者要的下一步动作相反）；
    ③ ``GET /api/students`` 今天就匿名返回全部 60 人，故这个信号本来就是公开的。
    已写进 spec 的已知局限（Task 5 会连同那 48 个匿名 GET 一起重新裁定）。

    ⚠️ **两档的 ``message`` 也因此刻意不同**（与 :func:`bind_student` 的
    「两档 403 合成一句」相反）：那里的两档要**不可区分**（防枚举在册名单），
    这里的两档要**可区分**（引导用户走对下一步）。同一种「403」在两个端点上
    给出相反的口径，故两处各写一段散文说明，刻意不合并。

    ⚠️ **不做登录失败计数 / 账号锁定**（计划 §1 的非目标逐字列了它）。
    代价如实记：一个知道学号的人可以无限次试口令，而 PBKDF2 的 600 000 次迭代
    意味着**服务端**每次尝试要花 ~0.3 s——于是「试口令」同时是一个
    **廉价的 CPU DoS**（一个请求换服务端 0.3 秒）。生产要加速度限制，
    已登记为待清扫。

    ⚠️ **不设 ``Secure``（除非 ``PE_ENV=production``）**、``SameSite=Lax``、
    ``Path=/``、``HttpOnly``、**不设 ``Domain``**：六个参数只有一个住址
    （:func:`app.auth.sessions.cookie_kwargs`），逐格理由见那个函数的 docstring。
    """
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
        return error_response(401, INVALID_CREDENTIALS, "口令不正确")

    role = (
        auth_sessions.STUDENT_ROLE
        if payload.kind == auth_sessions.STUDENT_KIND
        else subject.role
    )
    token = auth_sessions.issue(
        session, kind=payload.kind, subject_id=subject.id, role=role
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
