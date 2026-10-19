"""**一次性绑定令牌**的签发 / 解析 / 校验 / 作废（Plan 08 Task 4）。

行本身是 :class:`app.db.models.auth.BindToken`；本模块是**唯一**写它的地方
（:func:`issue` 建行、:func:`consume` 写 ``used_at``，全仓没有任何一处 ``DELETE``
这张表），故「一张令牌在库里长什么样」这件事只有一个住址 —— 与
:mod:`app.auth.sessions` 之于 ``user_session``、:mod:`app.api.audit` 之于 ``audit_log``
是同一个形状。

--------------------------------------------------------------------------
⚠️⚠️ 明文的形状：``<token_id>.<secret>``（两段）
--------------------------------------------------------------------------

``token_id`` 是**选择子**（selector）、``secret`` 是**凭据**。⚠️ 两格的角色相反，
而「为什么必须有一个明文的选择子」那一段逐字理由住在
:class:`app.db.models.auth.BindToken` 的 docstring 第二节（一句话：PBKDF2 的盐每行随机，
故哈希**不能**当等值键用；不用选择子的唯一替代是「扫全表逐行 ``verify_password``」，
那是一格 ``O(行数) × 0.3 s`` 的廉价 CPU DoS）。本处不复述第二份。

⚠️ 于是本模块的四格常量（:data:`TOKEN_ID_BYTES` / :data:`SECRET_BYTES` /
:data:`SEPARATOR` / :data:`BIND_TOKEN_TTL`）是「一张令牌长什么样」在全仓的唯一住址：
:func:`mint` 造它、:func:`split` 拆它、两个列宽守卫量它，三处都读这四个对象。

--------------------------------------------------------------------------
⚠️⚠️ 哈希**复用** :mod:`app.auth.passwords`，不写第二个 PBKDF2
--------------------------------------------------------------------------

派单 §2 第 1 条逐字要求这一格。落地是两行：签发用
:func:`app.auth.passwords.hash_password`、校验用
:func:`app.auth.passwords.verify_password`。⚠️ 于是「一次 PBKDF2 该跑多少圈」
（:data:`app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS` = **600 000**，
可被 ``PBKDF2_ITERATIONS`` 覆盖）、盐宽（16 B）、自描述串的四段形状、
迭代次数的**上下界**（100 000 / 2 000 000）与恒定时间比较
（:func:`hmac.compare_digest`）全部由那个模块持有，本模块**一个参数都不写死**。

⚠️⚠️ **这一格是承重的、不是省事**：:func:`verify_password` **从串里读迭代次数**，
故「校验不依赖当前配置」这条性质对本表同样成立 —— 运维把 ``PBKDF2_ITERATIONS``
从 600 000 抬到 1 000 000 之后，**未使用的旧令牌照旧验得过**（只是新签发的用更多工作量）。
一个自己写的确定性哈希会把这条性质弄丢，失效形状是「全部未使用的令牌当场失效」，
逐字论证住在 :class:`app.db.models.auth.BindToken` 的 docstring 第二节末段。

--------------------------------------------------------------------------
⚠️ 本模块的位置（``tests/architecture/test_layering.py`` 看着）
--------------------------------------------------------------------------

``app.auth`` 可以 import ``app.db`` 与 ``app.config``，**不得** import ``app.api``
（:mod:`app.auth` 的包 docstring）。故本模块**不 import ``fastapi``**、不抛
``HTTPException``：判定失败一律**返回 ``None`` / ``False``**，
「折成哪个 HTTP 码」由 :mod:`app.api.routers.auth` 决定 ——
与 :mod:`app.auth.policy` 的「本模块只答『锁没锁』，住在那里的只有码」逐字同一条口径。
"""

import dataclasses
import datetime as dt
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.sessions import now as _session_now
from app.db import width as db_width
from app.db.models.auth import BindToken

__all__ = [
    "BIND_TOKEN_TTL",
    "BindTokenRow",
    "SECRET_BYTES",
    "SEPARATOR",
    "TOKEN_ID_BYTES",
    "consume",
    "find",
    "is_expired",
    "issue",
    "matches",
    "mint",
    "outstanding",
    "split",
]

#: 选择子那一段的随机字节数。12 字节 → URL-safe base64 恰好 **16** 个字符
#: （``ceil(12/3)*4``，且 12 是 3 的倍数故没有 ``=`` 填充），落在
#: ``bind_token.token_id`` 的 ``String(32)`` 之内一倍。
#: ⚠️ **96 bit**：它不是秘密，而唯一约束（``unique=True``）要的是「碰撞不可能发生」，
#: 96 bit 在「一学期几百张」的量级上是一次生日碰撞概率约 ``10^-24`` 的事件。
TOKEN_ID_BYTES = 12

#: 秘密那一段的随机字节数。24 字节 → URL-safe base64 恰好 **32** 个字符。
#: ⚠️ **192 bit**：它是**凭据**，而本端点**没有限流到「猜不出来」的程度**
#: （:mod:`app.auth.policy` 的绑定那一组是 3 次 / 15 分钟窗口 / 锁 60 分钟），
#: 故熵必须自己够 —— 192 bit 意味着离线与在线两条路都是不可行的。
#: ⚠️ 取 24 而不是 :data:`app.auth.sessions.TOKEN_BYTES`（48）的理由：
#: 会话令牌要当 cookie 值（64 个字符已经贴着浏览器与日志的舒适度），
#: 而绑定令牌要**被人念出来或抄下来**（教务干事在迎新现场把它交给学生），
#: 49 个字符是一次可以接受的抄写、81 个不是。⚠️ 熵的账因此是 192 bit 而不是 384 bit，
#: 而 192 bit 对「一次性、7 天有效、限流 3 次」的凭据是富余的。
SECRET_BYTES = 24

#: 两段的分隔符。⚠️ 它**不在** URL-safe base64 的字母表里
#: （``A–Z a–z 0–9 - _``），故 :func:`split` 无歧义；也**不是** ``$``
#: （那是 :data:`app.auth.passwords.SEPARATOR`，两个分隔符同词会让
#: 「一个令牌串里出现 ``$``」变成一件读代码时要想一下的事）。
SEPARATOR = "."

#: 一张令牌的缺省存活时长。⚠️ **7 天**，三条理由：
#:
#: 1. **它要盖住一次真实的迎新流程**：教务干事在开学第一周集中签发，
#:    而学生不一定当天就绑定（要拿到手机/电脑、要找一个不被别人看见的地方设口令）。
#:    一天的窗口会把「周五签发、周一绑定」这一档打成失败。
#: 2. **它要短到「泄漏了也会自己死」**：一张被抄在纸上、贴在公告栏上、
#:    或误发进一个群里的令牌，最多活 7 天。⚠️ 而「一次性」那一格是更强的保证
#:    （用掉就废），本 TTL 挡的是「**从来没被用掉**、于是一直活着」的那一档。
#: 3. ⚠️ 它与 :data:`app.auth.sessions.SESSION_TTL`（2 小时）**刻意不是一个量级**：
#:    会话是「一次已认证的连续使用」，令牌是「一次尚未认证的一次性交接」。
#:    把两者对齐（都给 2 小时）会让迎新流程失败；把会话抬到 7 天会让
#:    「一台公用机器上忘记登出」的窗口从 2 小时变成 7 天。
#:
#: ⚠️ **刻意不做成环境变量**（与本仓 ``PE_*`` 那七个的取舍相反，如实记）：
#: 加一个变量就多一档「运维写错一个值」的失效（而一个巨大的值等于取消过期），
#: 且今天没有任何一个部署需要它不是 7 天。要改的话改这一个字面量、
#: 并同步 spec §13.26 的那一句。
BIND_TOKEN_TTL = dt.timedelta(days=7)


@dataclasses.dataclass(frozen=True)
class BindTokenRow:
    """:func:`find` 的返回值：那一行 + **拆出来的秘密那一段**。**frozen**：
    它会在端点里被传给 :func:`consume`，可变化会让「端点改了自己刚读到的行」
    成为一件在类型上可能的事（与 :class:`app.auth.policy.LoginThrottle` 同一条口径）。

    ⚠️ **为什么不是一个裸的 ORM 行**：端点要用的是三格
    （``row`` 本身给 :func:`consume`、``secret`` 给 :func:`verify_password`、
    ``kind``/``login`` 给回查与限流键），而「明文怎么拆成两半」这件事
    只能有一个住址（:func:`split`）。返回一个已经拆好的对，端点就**不可能**
    自己再拆一次（那会是第二个所有者）。
    """

    #: ``bind_token`` 那一行。
    row: BindToken
    #: 明文令牌的第二段（秘密）。⚠️ 它是**调用方交进来的那一份**，
    #: 不是从库里读出来的（库里只有哈希，读不出来 —— 那正是本模块存在的理由）。
    secret: str


def mint() -> "tuple[str, str, str]":
    """造一张新令牌的三格：``(明文, token_id, secret)``。

    ⚠️ **它是「一张令牌长什么样」在全仓的唯一产出点**：
    :func:`issue` 经它，守卫也经它（故「明文由两段组成、以 :data:`SEPARATOR` 分隔」
    这件事不可能有两份实现）。

    ⚠️ 两段都用 :func:`secrets.token_urlsafe` 而**不是** :mod:`random`：
    后者是梅森旋转，状态可以从输出反推 —— 与
    :func:`app.auth.passwords.hash_password` 的盐、
    :func:`app.auth.sessions.new_token` 的会话 id 逐字同一条口径。

    ⚠️ **明文只在返回值里存在这一次**：调用方（:func:`issue`）把它交出去、
    由端点回给签发它的那一位管理员，此后**库里与日志里都读不出它**
    （库里只有 :func:`hash_password` 的产出；而 :mod:`app.api.audit` 从不读请求体、
    也不读响应体）。守卫是 ``tests/api/test_bind_token.py`` 的
    ``test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table``。
    """
    token_id = secrets.token_urlsafe(TOKEN_ID_BYTES)
    secret = secrets.token_urlsafe(SECRET_BYTES)
    return SEPARATOR.join((token_id, secret)), token_id, secret


def split(plain: str) -> "tuple[str, str] | None":
    """明文令牌 → ``(token_id, secret)``；**形状不对就 ``None``**（绝不抛）。

    ⚠️ 「绝不抛」与 :func:`app.auth.passwords.verify_password` 同一条理由：
    ``plain`` 是**匿名的**客户端可控串（``POST /api/auth/bind-with-token`` 的请求体），
    一个 ``ValueError`` 会被 :mod:`app.api.errors` 折成 422 ``unprocessable_value``
    并**带上消息原文**——那等于告诉一个探测者「你交的串形状不对，差在哪」，
    而正确的答复是与「令牌不存在」**逐字相同**的那一档 403。

    ⚠️ 三档 ``None``：空串/全空白、分隔符出现**不等于一次**（0 次或 ≥2 次）、
    任一段为空。⚠️ 第三档是承重的：``"abc."`` 会让 ``secret`` 是空串，
    而 :func:`app.auth.passwords.verify_password` 对空摘要的处理是「当坏串」
    （它的 ``if not salt or not want`` 那一支）—— 两档都给 ``False``，
    但在本函数里先挡掉，是为了让「一个空秘密」根本不走到那一次 PBKDF2 上。
    """
    if not plain or not plain.strip():
        return None
    parts = plain.split(SEPARATOR)
    if len(parts) != 2:
        return None
    token_id, secret = parts
    if not token_id or not secret:
        return None
    return token_id, secret


def _clock(now: "dt.datetime | None") -> dt.datetime:
    """``now`` 可注入（同 :func:`app.auth.policy._clock` / :func:`app.pipeline.daily.run_daily`
    的先例）；缺省走 :func:`app.auth.sessions.now`（**naive 本地时刻**）。

    ⚠️ 缺省那半句是承重的：``bind_token.issued_at`` / ``expires_at`` / ``used_at``
    与库里其余全部 ``DateTime`` 列同口径，而差 8 小时会让「过期了吗」这个判断
    在 UTC 与本地之间给出相反的答案（一个刚签发的令牌会被判成 8 小时前就过期了）——
    与 :class:`app.db.models.auth.LoginAttempt` 的 ``at`` 列注释逐字同一条失效形态。
    """
    return _session_now() if now is None else now


def issue(
    db: Session,
    *,
    kind: str,
    login: str,
    issued_by: "str | None",
    now: "dt.datetime | None" = None,
    ttl: dt.timedelta = BIND_TOKEN_TTL,
) -> "tuple[BindToken, str]":
    """签发一张：建一行、**commit**、返回 ``(行, 明文)``。

    ⚠️ **明文只在这一个返回值里出现一次**（:func:`mint` 的 docstring）。
    调用方（``POST /api/auth/bind-tokens``）把它放进响应体，此后**没有任何一处**
    能把它读回来 —— 库里那一格是 :func:`app.auth.passwords.hash_password` 的产出。

    ⚠️ **本函数自己 commit**，理由与 :func:`app.auth.sessions.issue` /
    :func:`app.auth.policy.record_failure` 逐字相同：这一次写入必须在下一次请求之前
    落库，否则「令牌已经交给学生了、而学生那一发兑换查不到那一行」——
    症状是「教务干事明明发了、学生说令牌不正确」，离真因（一次没提交的写入）隔一整层。
    ⚠️ 而 :func:`app.api.deps.get_db` 刻意**不** commit，故这一次必须由本函数做。

    ⚠️ **它不判「目标在不在册 / 绑没绑过」**：那两档是**签发端点**的职责
    （它们各自要一个不同的 HTTP 码与一句不同的人话，而本模块不 import ``fastapi``）。
    于是本函数是一个纯写入动作，可被端点与测试直接调。

    ⚠️ ``issued_by`` 过一遍 :func:`app.db.width.overlong_sentinel`：
    它在生产档下来自会话行（已受 ``teacher.staff_no`` 的声明宽度约束），
    而**开发档下来自请求头原文**（``PE_ALLOW_HEADER_IDENTITY=1``）。
    ⚠️ 那一档今天**不可达**（:func:`app.api.deps.require_admin` 先经
    :func:`app.api.deps.require_staff`，一个不在册的工号当场 403，
    而在册就意味着它与 ``teacher.staff_no`` 的某个值逐字相同、故 ≤ 32）——
    而它**仍然设防**，逐字理由与 :func:`app.auth.policy._ip` 那一条相同：
    「不可达是一个环境变量的距离」，而成本是一次 ``len()`` 比较。
    ⚠️ 用**哨兵**而不是截断：本列是「指认一个人」的列，截断它会得到一个
    **看着像真工号的假工号**（那是一句假话），而哨兵 ``<over:400>`` 是一句实话。

    ⚠️ ``login`` **刻意不设防**：它的宽度收口点是签发端点那一次
    「按原文回查 subject 行」——查不到就是 404，故一个超宽的 ``login``
    **根本走不到本函数**（端点在调它之前就返回了）。⚠️ 而这一格由守卫钉住
    （``tests/api/test_bind_token.py`` 的
    ``test_an_overlong_login_never_reaches_the_bind_token_row``：交一个 400 字符的
    学号，断言 **404** 且 ``bind_token`` **0 行**）。
    """
    plain, token_id, secret = mint()
    current = _clock(now)
    row = BindToken(
        token_id=token_id,
        token_hash=hash_password(secret),
        kind=kind,
        login=login,
        issued_at=current,
        expires_at=current + ttl,
        used_at=None,
        issued_by=db_width.overlong_sentinel(
            issued_by, db_width.declared_width(BindToken.__table__.c.issued_by)
        ),
    )
    db.add(row)
    db.commit()
    return row, plain


def find(db: Session, plain: str) -> "BindTokenRow | None":
    """明文令牌 → :class:`BindTokenRow`；**选择子查无此行 / 形状不对 → ``None``**。

    ⚠️⚠️ **本函数刻意不校验秘密、也不判过期与作废**：它只答「这个选择子在不在库里」。
    三档判定各自住在调用方（``POST /api/auth/bind-with-token``），
    而**顺序是承重的**（逐字理由见那个端点的 docstring，本处只给一句）：
    先 :func:`app.auth.passwords.verify_password`，**再**判 ``used_at`` 与 ``expires_at``
    —— 反过来的话，一个只拿到 ``token_id``（例如从一条被截断的日志里）的人
    就能用「过期 / 已用」与「不存在」两档的差别，判出这个选择子在不在库里。

    ⚠️ **成本**：一次唯一索引上的点查（``token_id`` 的 ``unique=True``）。
    ⚠️⚠️ 而「选择子不存在」那一档**一次 PBKDF2 都不跑**（本函数返回 ``None``，
    端点当场 403）—— 那是本设计对「拿一串编造的令牌灌这个端点」这一格 DoS 的处置，
    与 :func:`app.auth.policy.is_locked` 排在 :func:`verify_password` 之前
    是同一条形状（锁定档不跑哈希）。

    ⚠️ 用 :func:`sqlalchemy.select` 而不是 ``db.get``：主键是 ``id``（一个自增整数），
    而查询的形状是按 ``token_id`` 等值 —— 本仓对「非主键的点查」一律走显式 ``select``
    （:func:`app.auth.sessions.student_by_login` / :func:`app.api.deps.require_staff` 同形）。
    """
    parts = split(plain)
    if parts is None:
        return None
    token_id, secret = parts
    row = db.scalar(select(BindToken).where(BindToken.token_id == token_id))
    if row is None:
        return None
    return BindTokenRow(row=row, secret=secret)


def matches(found: BindTokenRow) -> bool:
    """那一份秘密对不对得上。⚠️ 它就是
    :func:`app.auth.passwords.verify_password`（**复用**，不写第二个 PBKDF2）。

    ⚠️ **它在本模块里是一层薄薄的转发**，而那一层是**要的**：它让
    「一张令牌怎么校验」这件事在本模块有一个可 grep 的名字，
    于是「谁在做校验」不需要读端点才知道。⚠️ 它也**绝不抛**
    （``verify_password`` 的 docstring 第一节逐字写了为什么这一格是承重的）。
    """
    return verify_password(found.secret, found.row.token_hash)


def is_expired(row: BindToken, now: "dt.datetime | None" = None) -> bool:
    """这张令牌过期了吗。⚠️ 判据是 ``expires_at <= now``（**恰好等于那一刻也算过期**），
    与 :func:`app.auth.sessions.resolve` 的第 4 档逐字同一条口径。

    ⚠️ 反过来的判据（``<``）会让「一个 TTL 为 0 的令牌」在签发的同一瞬间可用 ——
    而那正是会话那一侧写下这条口径时要防的形状。

    ⚠️⚠️ **那一个 ``=`` 号是有守卫的**（本函数唯一一处「判据写在 docstring 里、
    而行为面看不出来」的形状）：守卫的唯一所有者是 ``tests/api/test_bind_token.py`` 的
    ``test_the_expiry_boundary_is_inclusive_at_the_exact_moment_itself``（三拍：
    恰好那一刻 ``True`` / 差一微秒 ``False`` / 端点真的读到它 ⇒ 403）。
    ⚠️ 补它之前，把下面那一行的 ``<=`` 改成 ``<``，**全部 379 条**令牌相关测试
    与 ``-k "expir or ttl or spent"`` 的 **22** 条一律全绿（终审 R7-02 / 变异 M7-3）。
    """
    return row.expires_at <= _clock(now)


def consume(
    db: Session, row: BindToken, *, now: "dt.datetime | None" = None
) -> bool:
    """把 ``used_at`` 写上（**仅当它还是 NULL**）→ 是否真的作废了一张。

    ⚠️⚠️ **判据是 ``rowcount``，不是「先读出来看是不是 NULL」**：
    与 :func:`app.api.routers.auth._bind_credential` 逐字同一条口径
    （那一处的模块 docstring 用一整节写了为什么 check-then-act 会让两个并发请求都过）。
    于是「一张令牌只能用一次」是一个**数据库保证的不变量**。
    守卫是 ``tests/api/test_bind_token.py`` 的
    ``test_the_second_redemption_of_one_token_is_refused_and_the_first_one_wins``
    （它按「第二次的影响行数是 0」那一拍实测，不靠真的开两个线程）。

    ⚠️ **它不 commit**（与 :func:`app.auth.policy.clear_failures` 同一条口径）：
    调用方（兑换端点）要把「令牌作废」与「口令哈希落库」放在**同一个**工作单元里 ——
    分两次 commit 会留下一个「口令已经绑上、而令牌还没作废」的窗口，
    而那个窗口里第二发兑换会**再绑一次**（⚠️ 它绑不上：``password_hash`` 已经不是
    NULL，故它得到 409 —— 但它会**用掉**同一张令牌第二次，而那一格是审计上的假象）。
    ⚠️ 那一次 commit 由 :func:`app.auth.policy.record_success` 做
    （与自助绑定那一侧逐字相同：``bind_student`` 也**不再自己 commit**）。

    ⚠️ ``synchronize_session=False``：本函数用的是 Core 的 :func:`sqlalchemy.update`，
    而 ``row`` 那个 ORM 实例还在 identity map 里；两个调用方在 ``rowcount == 1``
    之后都不再读 ``row``，故不需要同步（逐字理由见
    :func:`app.api.routers.auth._bind_credential`）。⚠️ 而**失败那一档**（``rowcount == 0``）
    调用方要读 ``row.used_at`` 来区分「已用过」与「并发被抢」，故它 ``rollback``
    之后重读 —— 那一格住在端点里。
    """
    result = db.execute(
        update(BindToken)
        .where(BindToken.id == row.id, BindToken.used_at.is_(None))
        .values(used_at=_clock(now))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def outstanding(db: Session, kind: str, login: str) -> int:
    """**这一个账号**此刻还有几张**没过期、没用过**的令牌。

    ⚠️ 它是签发端点那一句提示的数据来源（「这个学号已经有 N 张未使用的令牌」），
    ⚠️ 而它**刻意不是一个闸门**：本 Task 的裁定是**允许**一个账号同时有多张未使用的
    令牌（逐字理由见 ``POST /api/auth/bind-tokens`` 的 docstring 第三节 ——
    一句话：拒发的话，「学生把令牌弄丢了」这一档会让教务干事被卡住 7 天，
    而本波**没有**撤销端点）。
    """
    rows = db.scalars(
        select(BindToken.id).where(
            BindToken.kind == kind,
            BindToken.login == login,
            BindToken.used_at.is_(None),
            BindToken.expires_at > _session_now(),
        )
    )
    return len(list(rows))
