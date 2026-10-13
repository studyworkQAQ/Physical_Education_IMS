"""服务端会话的签发 / 解析 / 吊销，以及 cookie 的那几个参数（Plan 05A §3.4）。

会话行本身是 :class:`app.db.models.auth.UserSession`；本模块是**唯一**写它的地方
（``issue`` 建行、``resolve`` 滑动过期与当场吊销、``revoke`` 写 ``revoked_at``），
故「一次登录在库里长什么样」这件事只有一个住址。

--------------------------------------------------------------------------
⚠️ 滑动过期，**不做 refresh 令牌**（计划 §3.3 末段）
--------------------------------------------------------------------------

Bearer 方案要两种令牌（短的 access + 长的 refresh）才能在「令牌被偷的窗口小」与
「用户不必每两小时重登」之间取平衡；cookie 会话不需要，因为**服务端持有那一行**：
每个带有效 cookie 的请求把 ``expires_at`` 往后推一个 TTL、把 ``last_seen_at`` 更新成
现在，于是「活跃用户永不掉线、不活跃用户两小时后掉线」同时成立。
这是 cookie 方案相对 Bearer 的一个**实际简化**，spec §13 要写明。

⚠️ **代价（如实记，硬规矩 #39）**：滑动过期意味着**每个带有效 cookie 的请求都写一次库**
（``resolve`` 末尾那个 ``commit``）。原型是单进程 + SQLite，那一写是一次
``UPDATE user_session SET expires_at=?, last_seen_at=? WHERE id=?``，可忽略；
生产要收敛的话有两条现成的路：① 只在剩余 TTL 低于一半时才推（一次请求一次判断，
把写频降到 1/TTL 的一半）；② 把 ``last_seen_at`` 放进内存、只定期落库。
两条都**不在本计划里**。

--------------------------------------------------------------------------
⚠️ ``resolve`` 每次都回查 subject 行（计划 §3.1 那「最容易漏的一格」）
--------------------------------------------------------------------------

``user_session.subject_id`` 刻意不是外键，故删一个学生**不会**级联删他的会话行，
而 :func:`app.api.crud._child_tables` 也**探测不到**它（那个函数扫 ``foreign_keys``）。
于是「删掉一个学生，他手里的 cookie 还能用」这一档没有任何 DB 机制会挡——
唯一的处置是在解析时回查一次：查无此人就**当场写 ``revoked_at``** 并按「没有身份」返回。

⚠️ 回查的**第二个用途**是拿 ``name`` 与 ``student_no`` / ``staff_no``：
``GET /api/auth/me`` 要回这三格，而它们不在会话行上。故那次 ``SELECT`` 不是纯开销。

--------------------------------------------------------------------------
⚠️ cookie 的参数：``Max-Age`` 与 ``expires_at`` **同源**
--------------------------------------------------------------------------

两者都由 :data:`SESSION_TTL` 算出来（:func:`cookie_kwargs` 的 ``max_age`` 与
:func:`issue` 的 ``expires_at``），故不可能出现「cookie 说 7200、库里的行说 86400」
——那正是计划 §3.4 点名要防的一格。⚠️ 而**权威是库里那一行**：cookie 的 ``Max-Age``
只是给浏览器的提示，``resolve`` 判的是 ``expires_at``。两者同源之后，
「cookie 还在但行已过期」与「行还在但 cookie 已被浏览器丢掉」都退化成同一个 401。
"""

import dataclasses
import datetime as dt
import secrets
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import deploy
from app.config import TIMEZONE
from app.db.models.auth import UserSession
from app.db.models.organisation import Student, Teacher

__all__ = [
    "ENV_VAR",
    "EPOCH",
    "Identity",
    "PRODUCTION",
    "SESSION_COOKIE_NAME",
    "SESSION_TTL",
    "STUDENT_KIND",
    "STUDENT_ROLE",
    "TEACHER_KIND",
    "TOKEN_BYTES",
    "cookie_kwargs",
    "cookie_secure",
    "expired_cookie_kwargs",
    "issue",
    "now",
    "resolve",
    "revoke",
    "student_by_login",
    "subject_of",
    "teacher_by_login",
]

#: ``kind`` 的取值域。⚠️ **它不是第二份词表**：唯一所有者是模型类常量
#: :attr:`UserSession.KINDS`（本包约定 2），本处只是给它一个模块内的短名字。
KINDS = UserSession.KINDS

STUDENT_KIND = "student"
TEACHER_KIND = "teacher"

#: 学生会话在 ``user_session.role`` 那一列上的字面值。教师的两个值住在
#: :attr:`app.db.models.organisation.Teacher.ROLES`（``teacher`` / ``admin``）。
STUDENT_ROLE = "student"

#: cookie 名。⚠️ 它是「哪个 cookie 是会话」在全仓的唯一住址：
#: :func:`app.api.deps.current_session` / ``current_student`` / ``current_teacher``
#: 与 :data:`app.api.deps.SESSION_COOKIE_SCHEME`（OpenAPI 的声明）都从这里读。
SESSION_COOKIE_NAME = "pe_session"

#: 会话的存活时长，也是 cookie 的 ``Max-Age``（同源性见模块 docstring 第四节）。
#: ⚠️ **两小时**：一节课 45 分钟 + 课间，故「教师上一节课的时间里有学生掉线」不会发生；
#: 而它短到「一台公用机器上忘记登出」的窗口是可控的。原型不做「记住我」。
SESSION_TTL = dt.timedelta(hours=2)

#: :func:`secrets.token_urlsafe` 的字节数。48 字节 → URL-safe base64 恰好 **64** 个字符
#: （``ceil(48/3)*4``，且 48 是 3 的倍数故没有 ``=`` 填充），与
#: ``user_session.id`` 的 ``String(64)`` 逐字对齐。
#: ⚠️ 守卫 ``tests/auth/test_sessions.py::test_the_token_fits_the_column_and_the_column_is_exactly_as_wide``
#: 两侧不同源：期望侧是本常量与列宽的字面量，被测侧是 200 次真实签发的最大长度。
TOKEN_BYTES = 48

#: 判「是不是生产环境」的环境变量名。⚠️ **Plan 06 Task 4 起它是
#: :data:`app.deploy.ENV_VAR` 的别名**（同一个 ``str`` 对象，不是第二份字面量）：
#: 那一个值现在决定**三**件事（cookie 的 ``Secure``、请求头身份通道、CORS），
#: 而三个消费者住在三个不同的层、其中两个不许 import 第三个，故它搬去了
#: :mod:`app.deploy`（逐字理由见那个模块的 docstring 第一节）。
#: ⚠️ **本处保留这个名字**：``tests/auth/test_sessions.py`` 与
#: ``tests/api/test_auth_api.py`` 都按 ``auth_sessions.ENV_VAR`` 引用它，
#: 而「一个既有名字的住址搬了」不该逼着两个测试文件跟着改。
ENV_VAR = deploy.ENV_VAR

#: Unix 纪元，给 :func:`expired_cookie_kwargs` 的 ``expires`` 用。
#: ⚠️ **带 tzinfo**：RFC 6265 的 ``Expires`` 一律按 GMT 渲染，而一个 naive
#: ``datetime`` 会被 Starlette 当成「已经是 GMT」直接格式化——那在本时区（+08:00）
#: 会给出一个差 8 小时的串。对「1970 年」这个值来说差 8 小时无关紧要
#: （两边都远在过去），但一个不带 tzinfo 的常量会被下一个人抄去当「今天」用。
EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)

#: ``PE_ENV`` 的「生产」那一个字面值。⚠️ **Plan 06 Task 4 起它是
#: :data:`app.deploy.PRODUCTION` 的别名**，而**正字换成了 ``"prod"``**
#: （:data:`app.deploy.PROD`）：派单给的取值域逐字是 ``{dev, prod}``。
#: ⚠️ **``"production"`` 仍然被接受**（:func:`app.deploy.tier` 的
#: ``_PROD_SPELLINGS`` 两个都认）——删掉它会让所有按 Plan 05A 那份 spec §13
#: 部署的机器**静默**落到开发档，而那正是 :mod:`app.deploy` 要防的失效方向。
PRODUCTION = deploy.PRODUCTION


@dataclasses.dataclass(frozen=True)
class Identity:
    """一次成功解析出来的身份。**frozen**：它会被挂在依赖的返回值上传给端点，
    可变化会让「端点改了自己的身份」成为一件在类型上可能的事。

    五格各自回答一个不同的问题（硬规矩 #110：逐字段回问「这个值从哪来」）：

    * ``kind`` —— 来自 ``user_session.kind``：该去哪张表回查、以及
      :func:`app.api.deps.current_student` 与 ``current_teacher`` 谁该收下它；
    * ``subject_id`` —— 来自 ``user_session.subject_id``：``student.id`` 或 ``teacher.id``，
      它是 :func:`app.api.deps.require_scope` 要比对的那个「请求者的身份」；
    * ``role`` —— 来自 ``user_session.role``（**冗余的那一份**，见
      :mod:`app.db.models.auth` 的模块 docstring 第三节）：``require_admin`` 判它；
    * ``name`` —— 来自 **subject 行**（``student.name`` / ``teacher.name``）：
      会话行上刻意不存它，因为改名之后存的那一份就是一句过期的人话；
    * ``login`` —— 来自 **subject 行**（``student.student_no`` / ``teacher.staff_no``）：
      ``GET /api/auth/me`` 要回它，而教师侧的全部闸门
      （:func:`app.api.deps.require_staff` 一族）以工号为主语，故双通道过渡期
      「cookie 解析出来的教师身份」必须以工号的形式交出去，才能与请求头那一档同形。
    """

    kind: str
    subject_id: int
    role: str
    name: str
    login: str


def now() -> dt.datetime:
    """**现在**，按本仓的既定口径：先转到 :data:`app.config.TIMEZONE`、再摘掉 tzinfo。

    ⚠️ ``replace(tzinfo=None)`` 是承重的：本仓的 ``DateTime`` 列存的是 **naive** 本地时间
    （SQLite 没有时区类型），而 aware 与 naive 相减/相比会当场
    ``TypeError: can't compare offset-naive and offset-aware datetimes``。
    口径与 :mod:`app.api.routers.feedback` 判打卡窗口的那一句逐字相同。

    ⚠️ **不用 ``dt.datetime.utcnow()``**：那会与库里其余全部 naive **本地**时刻差 8 小时，
    于是「expires_at 是不是过了」这个判断在 UTC 与本地之间给出相反的答案
    （一个刚签发的会话会被判成 8 小时前就过期了）。
    """
    return dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


def new_token() -> str:
    """一个不透明的会话 id（:data:`TOKEN_BYTES` 字节随机 → URL-safe base64）。"""
    return secrets.token_urlsafe(TOKEN_BYTES)


def subject_of(db: Session, kind: str, subject_id: int) -> Student | Teacher | None:
    """``(kind, subject_id)`` → 那一行 subject；查无此人（或 ``kind`` 不在取值域里）→ ``None``。

    ⚠️ 它是「``subject_id`` 该去哪张表回查」的**唯一**分派点，而那件事之所以需要一个
    分派点，正是因为 :attr:`UserSession.subject_id` 不是外键
    （:mod:`app.db.models.auth` 的模块 docstring 第二节）。
    ``kind`` 落在取值域之外时返回 ``None`` 而不是抛：DB 的 CHECK 已经挡住了写入，
    故这一支今天不可达，而抛出去会变成一个 500（离真因更远）。
    """
    if kind == STUDENT_KIND:
        return db.get(Student, subject_id)
    if kind == TEACHER_KIND:
        return db.get(Teacher, subject_id)
    return None


def _login_of(kind: str, subject: Student | Teacher) -> str:
    """subject 行 → 它的登录名（学号 / 工号）。与 :func:`subject_of` 同一个分派。"""
    if kind == STUDENT_KIND:
        return subject.student_no  # type: ignore[union-attr]
    return subject.staff_no  # type: ignore[union-attr]


def student_by_login(db: Session, student_no: str) -> Student | None:
    """学号 → 学生行。绑定与登录两个端点共用它（故它是「学号怎么变成一行」的唯一住址）。"""
    return db.scalar(select(Student).where(Student.student_no == student_no))


def teacher_by_login(db: Session, staff_no: str) -> Teacher | None:
    """工号 → 教师行。与 :func:`student_by_login` 同一条口径。

    ⚠️ 它与 :func:`app.api.deps._teacher_id_of` **不是**重复：那一个只取 ``teacher.id``
    （任教关系闸门要的是代理键），本函数取**整行**（绑定要 ``name``、登录要 ``role``）。
    两者差的只是一次 ``SELECT`` 拉回一列还是几列，而合并它们会让
    「闸门只需要一个 id」这件事变成「闸门也拉回一整行」。
    """
    return db.scalar(select(Teacher).where(Teacher.staff_no == staff_no))


def issue(db: Session, *, kind: str, subject_id: int, role: str) -> str:
    """建一行会话、**commit**、返回要放进 cookie 的那个不透明 id。

    ⚠️ **本函数自己 commit**：会话行必须在响应发出之前就落库，否则
    ``Set-Cookie`` 已经给了浏览器、而下一个请求 ``db.get`` 查不到那一行 → 401，
    表现为「登录成功了但立刻又掉线」。而 :func:`app.api.deps.get_db` 刻意**不** commit
    （「什么时候算一个工作单元结束了」只有端点知道），故这一次 commit 必须由本函数做。

    ⚠️ 于是端点里 ``issue`` 之后再 ``session.commit()`` 是**多余但无害**的
    （第二次是空事务）。``POST /api/auth/login`` 因此不写第二个 commit。

    ``role`` 由调用方给：学生恒为 :data:`STUDENT_ROLE`，教师是 ``teacher.role``
    （登录那一刻 ``teacher`` 行上的值）。⚠️ 本函数**不回查** subject 行——
    调用方（``login``）刚刚才按学号/工号查出那一行并校验了口令，再查一次是白跑。
    """
    token = new_token()
    current = now()
    db.add(
        UserSession(
            id=token,
            kind=kind,
            subject_id=subject_id,
            role=role,
            created_at=current,
            expires_at=current + SESSION_TTL,
            last_seen_at=current,
            revoked_at=None,
        )
    )
    db.commit()
    return token


def resolve(db: Session, token: str | None) -> Identity | None:
    """cookie 里那个串 → 一个可用的 :class:`Identity`；**任何一档不可用都返回 ``None``**。

    返回 ``None`` 而不是抛：本模块不 import ``fastapi``（:mod:`app.auth` 的模块 docstring
    末节），而「没有身份」在 HTTP 层是**两个**不同的码
    （:func:`app.api.deps.current_student` 折成 401 ``unauthenticated``，
    :func:`app.api.deps.current_session` 同样折 401，而
    「cookie 是教师的、端点要学生」折成 403 ``forbidden``）——由调用方决定用哪个。

    六档 ``None``，**顺序是承重的**：

    1. ``token`` 为空/空白 → 根本没带 cookie；
    2. ``user_session`` 里查无此行 → 伪造的、或库被重建过；
    3. ``revoked_at`` 非空 → 已登出（**或被下面第 5 档当场吊销过**）；
    4. ``expires_at <= now`` → 已过期（⚠️ 用 ``<=`` 不是 ``<``：恰好等于那一刻也算过期，
       否则「一个 TTL 为 0 的会话」会在签发的同一瞬间可用）；
    5. **subject 行已不存在** → 当场写 ``revoked_at`` 再返回 ``None``
       （模块 docstring 第三节：``subject_id`` 不是外键，故没有任何 DB 机制会替我们做这件事）；
    6. ``kind`` 不在取值域里 → 由 :func:`subject_of` 归到第 5 档。

    ⚠️ **第 3 与第 4 档刻意不写 ``revoked_at``**：一个过期行不是「被吊销」，
    把它标成吊销会让「运维主动踢人」与「时间到了」在库里无法区分，
    而前者是审计事实、后者不是。过期行由待清扫里那个清理任务删。

    ⚠️ 走到最后一行才**滑动过期**并 ``commit``（一次 UPDATE）；前五档都是纯读，
    故「一个不带 cookie 的请求」在本函数里的成本是**零次数据库访问**
    （第 1 档在 ``db.get`` 之前就返回了）——这正是 1270 条既有测试
    （全部走请求头那一档）不受本计划影响的原因。
    """
    if not token or not token.strip():
        return None
    row = db.get(UserSession, token)
    if row is None:
        return None
    current = now()
    if row.revoked_at is not None:
        return None
    if row.expires_at <= current:
        return None
    subject = subject_of(db, row.kind, row.subject_id)
    if subject is None:
        row.revoked_at = current
        db.commit()
        return None
    row.expires_at = current + SESSION_TTL
    row.last_seen_at = current
    db.commit()
    return Identity(
        kind=row.kind,
        subject_id=row.subject_id,
        role=row.role,
        name=subject.name,
        login=_login_of(row.kind, subject),
    )


def revoke(db: Session, token: str | None) -> bool:
    """写 ``revoked_at``（**不删行**）→ 是否真的吊销了一行。

    返回 ``False`` 的三档：``token`` 为空、查无此行、**已经吊销过了**
    （幂等：登出两次是一个成功 + 一个 ``False``，而 HTTP 层两档都回 204，
    因为「你已经登出了」与「你刚刚登出了」对浏览器是同一件事）。

    ⚠️ 自己 ``commit``，理由与 :func:`issue` 逐字相同：``POST /api/auth/logout``
    回 204、没有响应体、也没有别的写入，故不 commit 的话那一次 UPDATE 会随
    ``Session.close()`` 被回滚掉——**登出就真的登不掉了**，而那正是本计划
    选服务端会话表（而不是签名 cookie）的第一条理由。
    """
    if not token:
        return False
    row = db.get(UserSession, token)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = now()
    db.commit()
    return True


def cookie_secure() -> bool:
    """cookie 要不要带 ``Secure``：仅当 :func:`app.deploy.is_prod`。

    ⚠️ **Plan 06 Task 4 起判据搬去了 :mod:`app.deploy`**（本处此前逐字是
    ``os.environ.get(ENV_VAR, "").strip().lower() == PRODUCTION``）。行为上有**两处**变化，
    都是那一个模块的口径带来的：

    1. ``PE_ENV=prod`` 现在也算生产（派单给的取值域是 ``{dev, prod}``；
       05A 的旧拼法 ``production`` **仍然**算）；
    2. ⚠️ **认不出的值不再静默当成开发档，而是 :class:`ValueError`**。
       改前 ``PE_ENV=staging`` / ``PE_ENV=productionn``（一个拼写错误）都得到
       ``False`` = 「cookie 不带 ``Secure``」= **静默不安全**；
       改后它们响亮失败（经 :mod:`app.api.errors` 折成 422 ``unprocessable_value``
       并带上消息原文，而在 ``app.main`` 的模块级 ``create_app()`` 那一档上
       它直接让服务**起不来**）。逐字理由见 :func:`app.deploy.tier`。

    ⚠️ **在请求时读环境变量**（口径与 :func:`app.auth.passwords.iterations` 相同）：
    原型跑在 ``http://127.0.0.1:8000`` 上，而带 ``Secure`` 的 cookie **在明文 HTTP 上
    根本不会被浏览器存下来**——于是「一律加 Secure」的表现是「本地演示谁都登录不了」，
    一个离真因很远的症状。

    ⚠️ **spec §13 要写明的生产那一档**（计划 §2.2）：若前端与后端**不同源**部署，
    则还需要 ① ``allow_origins`` 改成显式白名单（不能是 ``*``）② ``allow_credentials=True``
    ③ cookie 加 ``Secure`` **且** ``SameSite=None``。⚠️ **Plan 06 Task 4 兑现了 ①②**
    （:func:`app.main.create_app` 在 prod 下读 ``PE_CORS_ORIGINS``，非空时挂
    ``allow_credentials=True``），而 **③ 的后半句仍然没做**：``samesite`` 恒为
    ``"lax"``（下面 :func:`cookie_kwargs`），故一个真的**跨站**部署仍然登不上。
    按同源部署（``vite build`` 的产物由后端或同一个反代托管，开发期由 Vite 的
    ``/api`` 代理转发）则不触发那一档，``SameSite=Lax`` 就够。已登记为待清扫。
    """
    return deploy.is_prod()


def cookie_kwargs(token: str) -> dict[str, Any]:
    """:meth:`starlette.responses.Response.set_cookie` 的关键字参数（**不含 ``domain``**）。

    六个参数逐个说（⚠️ 它是全仓唯一写这几个字面量的地方）：

    * ``key`` = :data:`SESSION_COOKIE_NAME`（``pe_session``）；
    * ``value`` = 那个不透明 id；
    * ``max_age`` = :data:`SESSION_TTL` 的秒数（**与 ``expires_at`` 同源**，模块 docstring 第四节）；
    * ``path`` = ``"/"``：会话要在 ``/api/`` 与 ``/s`` / ``/t`` / ``/admin`` 两侧都发出去，
      而缺省的 ``path`` 是「当前 URL 的目录」，那会让 ``/api/auth/login`` 设的 cookie
      只在 ``/api/auth/`` 下可见；
    * ``httponly`` = ``True``：**JS 读不到，故 XSS 拿不走**（拿不到就不能写进
      ``fetch`` 的 body 送出去）。⚠️ 代价：前端**无法**自己判「我登录了吗」，
      只能靠 ``GET /api/auth/me`` 的 401——那是有意的，Plan 05A Task 3 的路由守卫
      正是这么写的；
    * ``secure`` = :func:`cookie_secure`（仅生产）；
    * ``samesite`` = ``"lax"``（**小写**：Starlette 只认 ``"lax"`` / ``"strict"`` /
      ``"none"`` / ``False``，写 ``"Lax"`` 会原样落进响应头、而部分浏览器不接受）。
      ⚠️ ``Lax`` 挡的是**跨站的 POST**（Lax 下跨站请求不带 cookie），CSRF 的另一半论证
      逐字见计划 §3.5 与 spec §13。

    ⚠️ **刻意不传 ``domain``**：不传就是「宿主限定」（只对设它的那个主机有效），
    这正是同源部署要的。写 ``domain="localhost"`` 会让 cookie 也对
    ``*.localhost`` 全部子域可见，而那是 §3.5 那条 CSRF 论证**挡不住**的一档。
    """
    return {
        "key": SESSION_COOKIE_NAME,
        "value": token,
        "max_age": int(SESSION_TTL.total_seconds()),
        "path": "/",
        "httponly": True,
        "secure": cookie_secure(),
        "samesite": "lax",
    }


def expired_cookie_kwargs() -> dict[str, Any]:
    """登出时那一发「让这个 cookie 立刻消失」的参数。

    ⚠️ **必须与 :func:`cookie_kwargs` 的 ``path`` / ``samesite`` / ``secure`` 逐字相同**：
    RFC 6265 的删除是按 ``(name, domain, path)`` 三元组匹配的，
    ``path`` 差一个字符就删不掉那一格（浏览器会留着它，于是「登出之后又自动登进去」）。
    故本函数**从 :func:`cookie_kwargs` 派生**而不是另写一份字面量——
    两个所有者迟早漂到两个 path 上去。

    ``max_age=0`` 与 ``expires``（**一个 1970 年的 aware ``datetime``**）
    **两个都给**：前者是 RFC 6265 的正解，后者是给那些只看 ``Expires`` 的旧客户端。
    ⚠️ **``expires`` 刻意不写成整数 ``0``**（实现者实测出来的坑）：
    Starlette 的 ``set_cookie`` 把 ``int`` 的 ``expires`` 当成
    **「从现在起多少秒」**（``datetime.now(utc) + timedelta(seconds=expires)``），
    而不是「Unix 时间戳」。故 ``expires=0`` 渲染出来的是**当前时刻**
    （实测 ``Set-Cookie: pe_session=""; expires=Mon, 12 Oct 2026 02:43:37 GMT``），
    一个「此刻到期」的 cookie 在边界上究竟算不算过期由客户端决定。
    传一个 ``datetime`` 则两种语义下都是同一个值，故用它。
    """
    kwargs = cookie_kwargs("")
    kwargs["max_age"] = 0
    kwargs["expires"] = EPOCH
    return kwargs
