"""登录限流与锁定的**阈值**（配置，不是代码）与三个动作（Plan 06 Task 3）。

--------------------------------------------------------------------------
规则（缺省 5 次失败 / 15 分钟窗口 / 锁 15 分钟，三格都可被环境变量覆盖）
--------------------------------------------------------------------------

一次登录尝试的处置只有四档，**顺序是承重的**：

1. **已锁** → :func:`is_locked` 回 ``True``，端点**当场**回一个与「口令错」
   **逐字相同**的 ``401 invalid_credentials``（见下面那一整节）。
2. **口令验不过** → :func:`record_failure` 写一行 ``ok=False``，回 ``401``。
3. **口令对了** → :func:`record_success` **删掉这个标识的全部行**并写一行
   ``ok=True``（= 清零），照常签发会话。
4. **不在册 / 未绑定** → ``403 password_not_bound``，**一行都不写**（见下面第三节）。

判「锁」的算式（:func:`is_locked`，三行、无隐藏状态）::

    recent = 这个 (kind, login) 上 at >= now - lookback 的 ok=False 行
    if len(recent) < max_fails: 不锁
    else: 锁 iff now - max(recent.at) < lock

⚠️ ``lookback`` 是 :func:`_lookback`，= **``max(window, lock)``**（不是裸 ``window``）。
理由是一条**静默失效**：若只回看 ``window``，则当运维把 ``PE_LOGIN_LOCK_MIN`` 抬到
比窗口大（例如「窗口 15 分钟、锁 60 分钟」）时，那 5 行失败会在**锁到期之前**就滑出
回看范围，于是 ``len(recent)`` 归 0、锁**被静默截断成 ``window``** ——配置了 60、
实际生效 15，而没有一处报错。抬到 ``max`` 之后那一档不再可能。
⚠️ **代价（硬规矩 #39，如实记）**：``lock > window`` 时「N 次失败」的判定窗口也
跟着变宽（那一档下是 ``lock``），即**多锁、不少锁**——失效方向是安全的。
⚠️ **缺省档 ``window == lock == 15 分钟``，故两者逐字等价**，本仓今天跑的就是那一个。

⚠️ 于是「锁到什么时候」锚在**最近一次被记录的失败**上，而**锁定期间的尝试不写行**
（第 1 档直接返回，不调 :func:`record_failure`）——那正是「锁满自动解锁」成立的机制：
第 5 次失败之后过 ``lock``，无论期间被打过多少次，锁都到点自动消失。
反过来，若锁定期间也写行，则一个持续探测的攻击者会让这个账号**永远**锁着
（滑动锁），而一个反复重试的**合法用户**也会把自己一直锁在里面——
后者的失效方向是「真实用户被永久拒之门外」，比前者严重。

--------------------------------------------------------------------------
⚠️⚠️ 锁内那一档回的是 ``401 invalid_credentials``，**不是** 423 / 429
--------------------------------------------------------------------------

计划 §3 原文写的是「锁内再试回 423（或 429）」，**控制者于 2026-10-13 改判为 401**，
实现者复核后**同意**，理由逐字如下（这一格是本模块最容易被下一个人「顺手改回去」的地方，
故散文写在模块级、并由 ``tests/api/test_auth_api.py`` 的
``test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password`` 钉住）：

* ``401 invalid_credentials`` 已经是「不在册」与「验身不符」之外的**第三个**含义吗？
  **不是**——它是同一个 code 的第三个来源。既有裁定（Plan 05A §3.3）是
  「401 对『验身不符』用一个 code、不给枚举信号」，而 ``423`` / ``429`` 会**额外**
  告诉探测者两件事：① 这个标识**存在且绑过口令**（不然它不可能被锁），
  ② 它**正在被锁**。第一件正是 ``403 password_not_bound`` 那一档已经泄漏、
  并被控制者显式接受的那一个比特；第二件是**新**的，而它让攻击者可以
  「用 423 当探针判断自己有没有把某个账号锁住」，进而对一个学校的教务干事账号
  做定向拒绝服务。
* 于是改判之后的口径是：**锁是服务端真实的 enforcement**（第 5 次之后一次口令都不再验，
  PBKDF2 的 600 000 次迭代一次都不跑，故它同时是那个「廉价 CPU DoS」的解药），
  而**它在响应上完全不可见**。
* ⚠️ **代价（如实记，硬规矩 #39）**：被锁的**合法用户**在锁定期内得不到任何提示
  ——他看到的就是「口令不正确」，于是他会继续重输（而那些重输**不写行**、
  故不会把锁推后，15 分钟后自然解开）。这一格写进 spec 的已知局限：
  「锁定期内不区分提示，避免枚举」。⚠️ 而「谁被锁过」这件事今天**在库里也查不到**
  （:class:`app.db.models.auth.LoginAttempt` 不是审计日志），可见性留给
  Plan 06 Task 5 的 ``audit_log``。

⚠️ **残留的一个旁路信号：响应耗时**（硬规矩 #39）。锁内那一档不跑 PBKDF2，
故它比「真的验一次口令」快约 0.3 秒，一个能测时序的调用方因此仍能判出「被锁了」。
**它不构成新的泄漏**：判「被锁了」需要先判「这个标识绑过口令」，而后者由
``403 password_not_bound`` 那一档**明文**给出（既有裁定接受）。要抹平它得在锁内
那一档也跑一次假哈希，而那恰好把本档要省的 CPU 又花回去了——与本档存在的理由相反。

--------------------------------------------------------------------------
⚠️ 只有「口令验不过」那一档计数；``403 password_not_bound`` 一行都不写
--------------------------------------------------------------------------

派单没点名这一格，故把判定与理由写在这里：

* **要挡的攻击面只有它**。暴力破解要的是「拿一个口令去撞一个已绑定的账号」，
  而那一次撞的结果**只**由 :func:`app.auth.passwords.verify_password` 给出。
  ``403`` 那一档根本没有口令参与（``password_hash`` 是 ``NULL``、或标识不在册），
  计数它不会挡住任何一次口令猜测。
* **计数它反而会让提示变坏**。计划 §3.3 刻意让 ``403``（该去绑定）与 ``401``（该重输）
  **可区分**——两档要的下一步动作相反。若 ``403`` 也计数，则一个把学号打错五次的
  新生会从「请先绑定」变成「口令不正确」，而他**根本没有口令**：那是一句把他支去
  反复重输的谎话，失效方向是**用户被卡住**。
* ⚠️ **它因此不挡枚举**。一个匿名调用方可以无限次地问「这个学号绑过口令吗」
  （403 vs 401）。**这不是本 Task 引入的**：那一格是 Plan 05A §3.3 的既有裁定
  （「控制者裁定接受」，理由与收敛过程逐字写在
  :func:`app.api.routers.auth.login` 的 docstring 里），本模块不重开它。
  而限流仍然挡得住枚举**之后**的那一步（拿到一个已绑定标识之后的口令猜测）。

--------------------------------------------------------------------------
⚠️ 阈值是**配置**、不是代码（计划 §3 逐字要求）
--------------------------------------------------------------------------

三格各有自己的环境变量，缺省值是本模块的**字面量**（:data:`DEFAULT_MAX_FAILS` /
:data:`DEFAULT_WINDOW_MINUTES` / :data:`DEFAULT_LOCK_MINUTES`），
运行时由 :func:`throttle` 解析成 :class:`LoginThrottle`。
⚠️ **在请求时读环境变量、不在 import 时读**（口径与
:func:`app.auth.passwords.iterations` / :func:`app.api.deps.allow_header_identity`
逐字相同）：``app.main`` 有一条模块级的 ``app = create_app()``，
「import 期读」等价于「必须在 import 之前设好」，而 ``monkeypatch.setenv``
发生在 import **之后**。
⚠️ **坏值抛 ``ValueError`` 而不是静默回落缺省**：``app.api.errors`` 把它折成
422 ``unprocessable_value`` 并带上消息原文，于是「环境变量写错了一个字母」
在第一次登录请求上就响。口径与 :func:`app.auth.passwords.iterations` 相同。
⚠️ 而**三格各自的下界**是本模块自己判的（``max_fails >= 1`` /
两个分钟数 ``>= 0``）：``max_fails = 0`` 会让**每一次**登录都算「已达阈值」
（于是谁都登录不了），而两个分钟数的 ``0`` 是**合法**的
（``window = 0`` = 只看「此刻」的失败 = 事实上关掉计数；``lock = 0`` = 不锁），
故它们的下界是 0 而不是 1。⚠️ 关掉限流的正确姿势是把 ``PE_LOGIN_LOCK_MIN``
设成 ``0``，**不是**把 ``PE_LOGIN_MAX_FAILS`` 设成一个巨大的数
（后者仍然每次失败都写一行库，于是表照样长）。

--------------------------------------------------------------------------
本模块的位置（``tests/architecture/test_layering.py`` 看着）
--------------------------------------------------------------------------

``app.auth`` 可以 import ``app.db`` 与 ``app.config``，**不得** import ``app.api``
（:mod:`app.auth` 的包 docstring）。故本模块**不 import ``fastapi``**、
不抛 ``HTTPException``：判定失败一律**返回 ``bool``**，
「折成哪个 HTTP 码」由 :mod:`app.api.routers.auth` 决定。
⚠️ 于是「锁内回 401 而不是 423」这一格**不住在本模块**——本模块只答「锁没锁」，
住在那里的只有码。这正是上面那条改判能被一条 HTTP 级守卫钉住、而不必动本模块的原因。
"""

import dataclasses
import datetime as dt
import os

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.sessions import now as _session_now
from app.db.models.auth import LoginAttempt

__all__ = [
    "DEFAULT_LOCK_MINUTES",
    "DEFAULT_MAX_FAILS",
    "DEFAULT_WINDOW_MINUTES",
    "LOCK_MIN_ENV_VAR",
    "LoginThrottle",
    "MAX_FAILS_ENV_VAR",
    "WINDOW_MIN_ENV_VAR",
    "clear_failures",
    "failure_count",
    "is_locked",
    "record_failure",
    "record_success",
    "throttle",
]

#: 缺省阈值三格。⚠️ **它们是字面量、被守卫按字面量钉住**
#: （``tests/auth/test_policy.py``）：从 :func:`throttle` 的返回值读回来跟自己比是
#: 同源断言，它证明不了「环境变量没设时用的就是 5/15/15」。
DEFAULT_MAX_FAILS = 5
DEFAULT_WINDOW_MINUTES = 15
DEFAULT_LOCK_MINUTES = 15

#: 三个环境变量的名字。⚠️ 住在本模块而不住在 ``app.config``，理由与
#: :data:`app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR` /
#: :data:`app.api.deps.ALLOW_HEADER_IDENTITY_ENV_VAR` 逐字相同：
#: ``config.py`` 是全仓依赖图的叶子（只 import :mod:`pathlib`），给它加一个
#: ``import os`` 会改掉那个性质，而它持有的应当是**缺省值**、
#: 不是「本层如何在运行时覆盖缺省值」。
MAX_FAILS_ENV_VAR = "PE_LOGIN_MAX_FAILS"
WINDOW_MIN_ENV_VAR = "PE_LOGIN_WINDOW_MIN"
LOCK_MIN_ENV_VAR = "PE_LOGIN_LOCK_MIN"


@dataclasses.dataclass(frozen=True)
class LoginThrottle:
    """一次进程内的限流阈值三格。**frozen**：它会被传进三个动作里，
    可变化会让「端点改了自己刚读到的阈值」成为一件在类型上可能的事。

    ⚠️ 两个时长是 :class:`datetime.timedelta` 而**不是分钟数**：分钟数在
    :func:`is_locked` 里要变成 ``now - window``，而那一处乘法就是
    「这个数是分钟还是秒」这个问题的第二个所有者。存 ``timedelta`` 之后，
    「单位」这件事只在 :func:`_minutes` 一处存在。
    """

    max_fails: int
    window: dt.timedelta
    lock: dt.timedelta


def _minutes(env_var: str, default: int) -> int:
    """读一个「分钟数」的环境变量；空 = 用缺省，坏值 = ``ValueError``（响亮）。

    ⚠️ 空字符串按「没设」处理（``strip()`` 之后判空）：``$env:PE_LOGIN_LOCK_MIN = ""``
    在 PowerShell 里是「设了一个空值」而不是「删掉这个变量」，而 ``int("")`` 是
    ``ValueError``——在一个与真因无关的地方。口径与
    :func:`app.auth.passwords.iterations` 逐字相同。
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{env_var} 必须是一个整数，收到 {raw!r}") from None
    if value < 0:
        raise ValueError(
            f"{env_var} 必须 ≥ 0（负数会让窗口起点跑到未来去，于是限流恒不生效），"
            f"收到 {value}"
        )
    return value


def throttle() -> LoginThrottle:
    """本次进程要用的三格阈值：环境变量 > 三个 :data:`DEFAULT_*` 字面量。"""
    max_fails = _minutes(MAX_FAILS_ENV_VAR, DEFAULT_MAX_FAILS)
    if max_fails < 1:
        # ⚠️ 单独判、不复用 _minutes 的那个 >= 0：``max_fails = 0`` 的意思是
        #    「0 次失败就算达到阈值」，于是**每一次**登录（含成功的）都在锁里，
        #    表现为「谁都登录不了」，而报错会指向一个与真因无关的地方。
        raise ValueError(
            f"{MAX_FAILS_ENV_VAR} 必须 ≥ 1（0 会让每一次登录都落进锁定档，"
            f"于是谁都登录不了；要关掉限流请把 {LOCK_MIN_ENV_VAR} 设成 0），"
            f"收到 {max_fails}"
        )
    return LoginThrottle(
        max_fails=max_fails,
        window=dt.timedelta(minutes=_minutes(WINDOW_MIN_ENV_VAR, DEFAULT_WINDOW_MINUTES)),
        lock=dt.timedelta(minutes=_minutes(LOCK_MIN_ENV_VAR, DEFAULT_LOCK_MINUTES)),
    )


def _clock(now: dt.datetime | None) -> dt.datetime:
    """``now`` 可注入（同 :func:`app.pipeline.daily.run_daily` 的先例）；缺省取真时钟。

    ⚠️ 缺省走 :func:`app.auth.sessions.now`（**naive 本地时间**）而**不是**
    ``dt.datetime.utcnow()``：``login_attempt.at`` 与库里其余全部 ``DateTime`` 列
    同口径（:class:`app.db.models.auth.LoginAttempt` 的 ``at`` 列注释），
    差 8 小时会让「窗口起点」永远在未来 → 限流**恒不生效**、而没有任何一处报错。
    """
    return _session_now() if now is None else now


def _lookback(policy: LoginThrottle) -> dt.timedelta:
    """计数回看 = ``max(window, lock)``。逐字理由见模块 docstring 第一节那段 ⚠️。

    ⚠️ 它是「回看多久」这件事在全仓的**唯一住址**：:func:`failure_count` 与
    :func:`is_locked` 都经它，故「窗口怎么算」不可能有两份。
    """
    return max(policy.window, policy.lock)


def failure_count(
    db: Session, kind: str, login: str, *, now: dt.datetime | None = None
) -> int:
    """这个 ``(kind, login)`` 在**当前回看窗口内**被记下的失败次数。

    ⚠️ 它是「计数」这件事在全仓的唯一住址：:func:`is_locked` 与守卫测试都经它，
    故「窗口怎么算」不可能有两份。
    ⚠️ 一次 ``SELECT count(*)``、**不拉行**：本表是单调增长的，
    而判定只需要一个数。
    """
    current = _clock(now)
    return int(
        db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.kind == kind,
                LoginAttempt.login == login,
                LoginAttempt.ok.is_(False),
                LoginAttempt.at >= current - _lookback(throttle()),
            )
        )
        or 0
    )


def is_locked(
    db: Session, kind: str, login: str, *, now: dt.datetime | None = None
) -> bool:
    """这个 ``(kind, login)`` **此刻**是不是在锁定期内（算式见模块 docstring 第一节）。

    ⚠️ 边界用 ``<`` 而不是 ``<=``：恰好过满 ``lock`` 的那一刻**已经解锁**
    （与 :func:`app.auth.sessions.resolve` 的 ``expires_at <= current`` 同一条口径：
    边界那一瞬间算「已过」）。守卫是
    :func:`tests.auth.test_policy.test_the_lock_lifts_itself_exactly_when_the_lock_period_has_elapsed`
    ——它靠注入 ``now`` 走完整条时间线，**不睡 15 分钟**。

    ⚠️ **计数那一半不在这里重算**：走 :func:`failure_count`（它是「窗口怎么算」的
    唯一住址）。本函数自己只多问一件事——**最近一次**被记录的失败是什么时候，
    因为「锁到什么时候」锚在那一刻上（模块 docstring 第一节）。
    ⚠️ 两次查询而不是一次：``max(at)`` 与 ``count(*)`` 在 SQLite 上都是一次
    ``ix_login_attempt_kind_login_at`` 上的索引扫描（等值两列 + 范围一列），
    而把它们合成一次要拉回行来在 Python 侧算——本表单调增长，那是更贵的那一个。

    ⚠️ **本函数不写库、不 commit**（与 :func:`app.api.deps.require_scope` 的
    「pure gate」同一条口径）：它只答一个问题。写行是 :func:`record_failure` /
    :func:`record_success` 的事，而「什么时候算一个工作单元结束」由端点决定。
    """
    policy = throttle()
    if failure_count(db, kind, login, now=now) < policy.max_fails:
        return False
    current = _clock(now)
    latest = db.scalar(
        select(func.max(LoginAttempt.at)).where(
            LoginAttempt.kind == kind,
            LoginAttempt.login == login,
            LoginAttempt.ok.is_(False),
            LoginAttempt.at >= current - _lookback(policy),
        )
    )
    # ⚠️ latest 为 None 而 count >= max_fails 在逻辑上不可达（count 数的就是那批行），
    #    故这一支是许可而不是断言（硬规矩 #39）：两档之间隔着一个并发写入的窗口，
    #    而那一个窗口的正确答案是「不锁」（宁可少锁一次，也不要按一个不存在的时刻算锁）。
    if latest is None:
        return False
    return (current - latest) < policy.lock


def record_failure(
    db: Session,
    kind: str,
    login: str,
    *,
    ip: str | None = None,
    now: dt.datetime | None = None,
) -> None:
    """写一行 ``ok=False``（**并 commit**）。

    ⚠️ **本函数自己 commit**，理由与 :func:`app.auth.sessions.issue` 逐字相同：
    这一次写入必须在下一次请求之前落库，否则「连打五次」的前四次会因为
    :func:`app.api.deps.get_db` 在请求结束时 ``close()``（回滚未完成的事务）而**全部丢掉**
    ——于是限流恒不生效，而症状是「怎么试都不锁」。
    ⚠️ 而 :func:`app.api.routers.auth.login` 那一档回的是 ``error_response(401, …)``
    （一个已经构造好的 ``Response``），端点里没有别的写入、也就没有第二个 commit。
    """
    db.add(LoginAttempt(kind=kind, login=login, ok=False, at=_clock(now), ip=ip))
    db.commit()


def clear_failures(db: Session, kind: str, login: str) -> int:
    """删掉这个 ``(kind, login)`` 的**全部**行（成功与失败都删），返回影响行数。

    ⚠️ **删的是全部行、不只是 ``ok=False`` 的行**：留着上一次成功的 ``ok=True``
    行没有任何判定用途（:func:`is_locked` 只看失败行），而本表是单调增长的，
    一次成功登录是**唯一**一个可以安全收缩它的时机。
    ⚠️ 它**不 commit**：生产路径上唯一的调用方是 :func:`record_success`，
    那一次 DELETE 与紧随的
    那一次 INSERT 必须是**同一个**工作单元（否则「删了旧行、还没写新行」的窗口里
    另一个请求会看到「这个标识从来没试过」——那正是限流要防的形状）。
    """
    return db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.kind == kind, LoginAttempt.login == login
        )
    ).rowcount


def record_success(
    db: Session,
    kind: str,
    login: str,
    *,
    ip: str | None = None,
    now: dt.datetime | None = None,
) -> None:
    """成功登录：**清零**这个 ``(kind, login)`` 的失败计数，并写一行 ``ok=True``。

    ⚠️ 「清零」的实现是 :func:`clear_failures` 那一次 DELETE + 本函数那一次 INSERT，
    两者在同一个事务里（``commit`` 只有一次，在末尾）。
    ⚠️ **仍然写一行 ``ok=True``**（而不是「删完就完」）：删完之后的库里没有任何痕迹
    说明这个标识刚刚成功登录过，而下一个人来查「为什么这个标识一条失败记录都没有」
    时得到的是一个无法区分的答案（从来没失败过 / 失败了但被清了）。
    ⚠️ 而它**不是**审计留痕（那是 Task 5 的 ``audit_log``）：本行会被下一次成功登录
    删掉，故它答的只是「此刻这个标识的计数器是干净的、且干净是因为一次成功」。
    """
    clear_failures(db, kind, login)
    db.add(LoginAttempt(kind=kind, login=login, ok=True, at=_clock(now), ip=ip))
    db.commit()
