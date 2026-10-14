"""**登录**与**绑定**两件事的限流与锁定：**阈值**（配置，不是代码）+ 五个动作
+ 「用途」那一维怎么进键（Plan 06 Task 3 建、Plan 06 Task 10 加第二组）。

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
⚠️⚠️ Plan 06 Task 10 起：限流键多了一维「**用途**」，而阈值多了一组
--------------------------------------------------------------------------

本模块此前只管**登录**一件事。而 ``POST /api/auth/{students,teachers}/bind`` 用的验身材料
是**弱材料**（学生 = 学号 + 出生日期，教师 = 工号 + 姓名，spec §1.2 第 4 条），
而它**今天完全没有限流** —— 于是一个匿名调用方可以对一个**还没绑定**的账号反复猜
出生日期/姓名，猜中就**抢到**那个账号的口令。本波给它加上同一套机器。

⚠️⚠️ **而键必须与登录分开**，这一格是本件最容易做错的地方：若两个用途共用
``(kind, login)`` 一个键，则「猜出生日期猜错 3 次」会把那个账号的**登录**也锁掉
——那是把限流变成了**拒绝服务**（一个匿名调用方只要拿别人的学号乱猜绑定材料，
就能把那个人锁在自己的账号外面）；反过来也成立（一个把自己的口令输错三次的用户
会被锁得绑不上）。故键是 **``(kind, purpose, login)``** 三维。

``purpose`` 那一维**落在键的字符串里**，而**不是** ``login_attempt`` 的一个新列。
逐字理由（派单 §2.1 给了两条路，实现者选 ①「编进键里」、并**顶回**了派单举的那个
例子——它把用途编进 ``kind`` 里，而那在本仓**做不到**）：

* ⚠️ **``kind`` 那一列有一条 SQL 层的 CHECK**（``ck_login_attempt_kind``，文本由
  :attr:`app.db.models.auth.LoginAttempt.KINDS` 生成，而它**就是**
  :attr:`~app.db.models.auth.UserSession.KINDS` 那一个对象，三张表同一族语义）。
  故 ``kind="student_bind"`` 会被**数据库自己拒收**（``IntegrityError``）；
  要让它过得先放宽那个取值域 ⇒ 改 DDL ⇒ **配一条迁移**（迁移链 3 → 4），
  还要同步「CHECK 条数」「``LoginAttempt.KINDS is UserSession.KINDS``」两条既有守卫
  （``tests/auth/test_policy.py::test_the_kind_check_constraint_has_teeth`` 与
  ``tests/db/test_models.py``）—— 而那会把 ``user_session.kind`` /
  ``audit_log.subject_kind`` 的取值域一起污染（三张表共用那一个集合）。
* ⚠️ 于是本波把用途编进**键的另一半**（``login``）：``login`` 那一列**没有** CHECK、
  也**没有**取值域守卫，它今天存的只是「限流键的后半段」。编进去之后
  **不加列、不动表形状**（表数仍然 **28**、``login_attempt`` 仍然 **6** 列），
  这正是派单 §2.1 倾向 ① 的那一条理由。
  ⚠️⚠️ 而本处原先还写着「**不动 schema、不动迁移**（迁移链仍然 3）」——那半句
  在 Plan 06 Task 11 被证明**说过头了**：加前缀把这一列的**上界**从 32 抬到了 37，
  而它声明的还是 ``String(32)``，于是要一条改列宽的迁移（链 3 → **4**）。
  ⚠️ 那一格在 SQLite 上是**静默**的（它不校验 ``VARCHAR(n)`` 的长度），
  逐字后果、那个 64 的来历与守卫都住在下面「两条如实记的残余」的第 1 条。
* ⚠️ 编法：:data:`_KEY_PREFIX_BY_PURPOSE` = ``{"login": "", "bind": "bind:"}``，
  即**登录那一档的键逐字不变**（``("student", "2023120001")``），只有绑定那一档
  多一个前缀（``("student", "bind:2023120001")``）。⚠️ 「登录的键不变」是承重的：
  一个已经在库里的限流行不会因为本波而**换键**（换了的话那些行会变成孤儿、
  而正在被锁的账号会当场解开）。
* ⚠️ **前缀只有这一个住址**（:func:`_key`），而五个动作一律经它 ⇒
  「用途怎么进键」不可能有两份。⚠️ 而**调用方交的是 ``purpose``、不是前缀串**：
  端点上写的是 ``purpose=auth_policy.PURPOSE_BIND``（一个人话词），
  前缀那一格是存储细节、住在这一层。

⚠️ **两条如实记的残余**（硬规矩 #39）：

1. ~~**列宽**~~ → **已收**（Plan 06 Task 11 / A1）：``login_attempt.login`` 从
   ``String(32)`` 加宽到 **``String(64)``**，并配了迁移链的**第 4 条**迁移
   （SQLite 没有 ``ALTER COLUMN``，故走 ``batch_alter_table``；``downgrade`` 改回 32）。
   ⚠️ **原文如实抄在这里**，因为它是这一格为什么值得单开一条迁移的证据：
   「``login_attempt.login`` 是 ``String(32)``，而加前缀之后那个键最长是
   ``5 + len(学号)``。本仓的学号/工号实测最长 **10** 个字符（``2023120001`` /
   ``T0001``），故实际最长 **15**；⚠️ 而 schema 上 ``student.student_no`` 也是
   ``String(32)``，故**理论上**一个 32 字符的学号会让键变成 37 字符 ——
   SQLite **不校验** ``VARCHAR(n)`` 的长度（实测：写进去不报错、读出来不截断），
   而本仓今天只跑 SQLite。换到别的后端之前要先给这一列加宽。」
   ⚠️⚠️ 「换到别的后端」那一格是**跨后端的定时炸弹**，而两颗弹的引信不同：
   PostgreSQL 会**报错**（响亮）、MySQL 会**静默截断**——而截断会让两个不同的
   绑定键撞成同一个（``bind:AAAA…`` 与 ``bind:AAAB…`` 截到 32 之后同串），
   于是限流**误伤登录**。故本仓第一条「声明与实际写入不符」的列宽不留到换后端那天。
   ⚠️ 守卫（``tests/auth/test_policy.py`` 的
   ``test_the_login_column_is_at_least_as_wide_as_the_longest_key_the_policy_writes``）
   **刻意不硬编码 37**：它真的走一遍 :func:`record_failure` 把最长的那一个键写进去、
   再量回来，故改前缀或加宽名册列都会让它跟着变。
2. **键碰撞**：一个 ``student_no`` 字面等于 ``"bind:X"`` 的学生，会让他的**登录**计数
   与 ``X`` 的**绑定**计数共用一个键。⚠️ 而要走通它需要一个 ``student_no`` 里带
   ``:`` 的**在册学生行**，而建学生行**仅管理员**可做（``POST /api/students``，
   Plan 05A Task 2 起）；且登录那一档只在「在册**且**已绑口令**且**口令错」时才写行，
   故一个匿名调用方**无从**构造它。判定：不构成新的攻击面，如实记录、不加校验。

⚠️⚠️ **绑定那一组阈值比登录更严**（缺省 **3** 次 / **15** 分钟窗口 / 锁 **60** 分钟）
--------------------------------------------------------------------------

派单 §2.2 逐字要求「缺省应当比登录更严」，并要取值与理由。理由是一条算术：

=========================  =========================  ==============================
                            登录（既有）                绑定（本波）
=========================  =========================  ==============================
猜的是什么                  口令（PBKDF2 600 000 次）   出生日期 / 姓名
可信取值的个数               实际上**无界**              出生日期 ≈ 8 个出生年 × 366
                                                       ≈ **2 900**；⚠️ 姓名对读过名册的
                                                       教职是**已知串**
每次猜测的服务端代价          ~0.3 s（PBKDF2）           ~0（一次等值查询）
``max_fails``               5                          **3**
``lock``                    15 分钟                     **60** 分钟
一天能试多少次               ``24/0.25 × 5 = 480``      ``24/1 × 3 = 72``
⇒ 对一个账号一天内被猜中      ≈ 480/2900 = **16.5%**     ≈ 72/2900 = **2.5%**
=========================  =========================  ==============================

（「一天能试多少次」的算式是 ``24 h / lock × max_fails``：锁定档**不写行**，
故锁一到点就自动解开、攻击者可以再试 ``max_fails`` 次 —— 逐字机制见第一节。）

* ⚠️ **``window`` 保持 15**：它决定「多少次失败算一批」，而本模块的回看是
  :func:`_lookback` = ``max(window, lock)`` = **60** 分钟，故计数窗口实际被抬到 60 ——
  那是**多锁、不少锁**，失效方向安全（:func:`_lookback` 的 docstring 逐字写了这一档）。
* ⚠️ **代价（如实记）**：一个把出生日期打错 3 次的新生要等 **60 分钟**才能再试绑定，
  而本原型**没有口令找回** ⇒ 那 60 分钟里他既登不进也绑不上。裁定接受：
  绑定是**一次性**的入网动作、通常在开学集中办理（有教务干事在场），
  而「60 分钟的不便」与「账号被抢绑」相比是便宜的那一头。
* ⚠️ 三格**各有自己的环境变量**（``PE_BIND_MAX_FAILS`` / ``PE_BIND_WINDOW_MIN`` /
  ``PE_BIND_LOCK_MIN``），口径与登录那三个逐字相同（请求时读、坏值抛 ``ValueError``、
  两个分钟数的下界是 0）。⚠️ 要更严就把 ``PE_BIND_LOCK_MIN`` 抬到 ``360``
  （⇒ 12 次/天 ⇒ ≈0.4%/天/账号），要关掉绑定限流就把它设成 ``0``
  （⚠️ **不是**把 ``PE_BIND_MAX_FAILS`` 设成一个巨大的数，理由与登录那一格逐字相同）。
* ⚠️ **两组阈值一共只有这一份解析**（:func:`_throttle`）：:func:`throttle` 与
  :func:`bind_throttle` 各自只交出「自己的三个变量名 + 自己的三个缺省 + 自己那个人话名词」，
  故「下界怎么判、坏值怎么报、分钟怎么变成 ``timedelta``」三件事各只有一份。
* ⚠️ **而「哪个用途用哪一组」也只有这一个住址**（:func:`_policy_of`）：
  五个动作一律经它取阈值，故不存在「绑定那一档读了登录的阈值」这种串线。

--------------------------------------------------------------------------
本模块的位置（``tests/architecture/test_layering.py`` 看着）
--------------------------------------------------------------------------

``app.auth`` 可以 import ``app.db`` 与 ``app.config``，**不得** import ``app.api``
（:mod:`app.auth` 的包 docstring）。故本模块**不 import ``fastapi``**、
不抛 ``HTTPException``：判定失败一律**返回 ``bool``**，
「折成哪个 HTTP 码」由 :mod:`app.api.routers.auth` 决定。
⚠️ 于是「锁内回 401 而不是 423」这一格**不住在本模块**——本模块只答「锁没锁」，
住在那里的只有码。这正是上面那条改判能被一条 HTTP 级守卫钉住、而不必动本模块的原因。
⚠️⚠️ **绑定那一档同理**：它回的是与「验身材料不符」**逐字相同**的
``403 forbidden``（控制者裁定，与登录那一次改判同一条理由：另给一个码就是枚举信号
「这个标识存在且已被锁」），而那一个码住在 :mod:`app.api.routers.auth`、不在这里。
"""

import dataclasses
import datetime as dt
import os

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.sessions import now as _session_now
from app.db import width as db_width
from app.db.models.auth import LoginAttempt

__all__ = [
    "BIND_LOCK_MIN_ENV_VAR",
    "BIND_MAX_FAILS_ENV_VAR",
    "BIND_WINDOW_MIN_ENV_VAR",
    "DEFAULT_BIND_LOCK_MINUTES",
    "DEFAULT_BIND_MAX_FAILS",
    "DEFAULT_BIND_WINDOW_MINUTES",
    "DEFAULT_LOCK_MINUTES",
    "DEFAULT_MAX_FAILS",
    "DEFAULT_WINDOW_MINUTES",
    "LOCK_MIN_ENV_VAR",
    "LoginThrottle",
    "MAX_FAILS_ENV_VAR",
    "PURPOSES",
    "PURPOSE_BIND",
    "PURPOSE_LOGIN",
    "WINDOW_MIN_ENV_VAR",
    "bind_throttle",
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

#: **绑定**那一组三格的缺省与环境变量（Plan 06 Task 10）。
#: ⚠️ 三格**一律比登录那一组更严**（``3 < 5``、``60 > 15``），逐字算术见模块
#: docstring 的「绑定那一组阈值比登录更严」那一节；⚠️ 六个字面量同样**被守卫按字面量
#: 钉住**（``tests/auth/test_policy.py``），不从 :func:`bind_throttle` 的返回值读回来
#: 跟自己比（那是同源断言，证明不了「环境变量没设时用的就是 3/15/60」）。
DEFAULT_BIND_MAX_FAILS = 3
DEFAULT_BIND_WINDOW_MINUTES = 15
DEFAULT_BIND_LOCK_MINUTES = 60

BIND_MAX_FAILS_ENV_VAR = "PE_BIND_MAX_FAILS"
BIND_WINDOW_MIN_ENV_VAR = "PE_BIND_WINDOW_MIN"
BIND_LOCK_MIN_ENV_VAR = "PE_BIND_LOCK_MIN"

#: 「**用途**」那一维的两个取值（Plan 06 Task 10）。⚠️ 它是限流键的中间一段，
#: 逐字理由见模块 docstring 的「限流键多了一维」那一节（⚠️ 那一节也交代了
#: **为什么不是** ``login_attempt`` 的一个新列、也**不是** ``kind`` 的一个新取值）。
PURPOSE_LOGIN = "login"
PURPOSE_BIND = "bind"

#: 取值域。⚠️ 它**刻意不是**从 :data:`_KEY_PREFIX_BY_PURPOSE` 反推出来的第二个对象
#: （:func:`_check_purpose` 与守卫都读它），故「加第三个用途」时漏掉前缀会当场
#: ``KeyError``、而不是静默地与登录共用一个计数器。
PURPOSES = frozenset({PURPOSE_LOGIN, PURPOSE_BIND})

#: 用途 → **键的前缀**。⚠️ 登录那一档的前缀是**空串**：那让它的键与 Plan 06 Task 3
#: 起库里已有的那些行**逐字相同**（``("student", "2023120001")``），于是本波
#: 不会让一个正在被锁的账号当场解开、也不会留下一批换过键的孤儿行。
#: ⚠️ 它是「前缀长什么样」在全仓的唯一住址（:func:`_key` 是唯一的读者）。
_KEY_PREFIX_BY_PURPOSE = {PURPOSE_LOGIN: "", PURPOSE_BIND: "bind:"}


@dataclasses.dataclass(frozen=True)
class LoginThrottle:
    """一次进程内的限流阈值三格。**frozen**：它会被传进五个动作里，
    可变化会让「端点改了自己刚读到的阈值」成为一件在类型上可能的事。

    ⚠️ **Plan 06 Task 10 起它装两组阈值**（:func:`throttle` 的登录那一组、
    :func:`bind_throttle` 的绑定那一组），而**类名刻意不改**：它答的是
    「一组三格阈值」这一件事，而改名要动十几处既有守卫、换来的只是对称
    （逐字理由见 :func:`throttle` 的 docstring 末段）。

    ⚠️ 两个时长是 :class:`datetime.timedelta` 而**不是分钟数**：分钟数在
    :func:`is_locked` 里要变成 ``now - window``，而那一处乘法就是
    「这个数是分钟还是秒」这个问题的第二个所有者。存 ``timedelta`` 之后，
    「单位」这件事只在 :func:`throttle` 那两行 ``dt.timedelta(minutes=…)`` 里存在。
    """

    max_fails: int
    window: dt.timedelta
    lock: dt.timedelta


def _int_from_env(env_var: str, default: int, noun: str) -> int:
    """读一个**非负整数**环境变量；空 = 用缺省，坏值 = ``ValueError``（响亮）。

    ⚠️ 空字符串按「没设」处理（``strip()`` 之后判空）：``$env:PE_LOGIN_LOCK_MIN = ""``
    在 PowerShell 里是「设了一个空值」而不是「删掉这个变量」，而 ``int("")`` 是
    ``ValueError``——在一个与真因无关的地方。口径与
    :func:`app.auth.passwords.iterations` 逐字相同。

    ⚠️ ``noun`` 会进报错文本：三个变量都是整数，而「必须是一个整数」这一句
    对运维没有信息量（他要知道是**哪一个**写错了）。
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{env_var}（{noun}）必须是一个整数，收到 {raw!r}") from None
    if value < 0:
        raise ValueError(f"{env_var}（{noun}）必须 ≥ 0，收到 {value}")
    return value


def _check_purpose(purpose: str) -> str:
    """``purpose`` 在 :data:`PURPOSES` 里吗；不在就**响亮地**抛 ``ValueError``。

    ⚠️ 报错文本里点名了它决定的**两件事**（键的前缀 + 用哪一组阈值），因为写错一个
    字母的失效形态是**静默**的：一个不认识的前缀会让两个用途各用一个没人共享的键
    （于是限流恒不生效），而一个恰好撞上另一个用途的前缀会让两者**共用**一个计数器
    （于是「猜出生日期猜错三次」把那个账号的登录也锁掉 = 一次自我造成的拒绝服务）。
    """
    if purpose not in PURPOSES:
        raise ValueError(
            f"限流键的「用途」必须是 {sorted(PURPOSES)} 里的一个，收到 {purpose!r}"
            "（它决定两件事：键的前缀 + 用哪一组阈值。写错一个字母要么让限流恒不生效、"
            "要么让两个用途共用一个计数器 = 把限流变成拒绝服务）"
        )
    return purpose


def _key(purpose: str, login: str) -> str:
    """限流键的**后半段**：``purpose`` 怎么进键，**只有这一个住址**。

    ⚠️ 五个动作（:func:`failure_count` / :func:`is_locked` / :func:`record_failure` /
    :func:`clear_failures` / :func:`record_success`）一律经它，故「登录与绑定共用一个
    计数器」这件事在结构上不可能发生 —— 而它正是本件最容易做错的一格
    （逐字理由见模块 docstring 的「限流键多了一维」那一节）。
    ⚠️ 它返回的是**要写进 ``login_attempt.login`` 那一列的串**，而不是一个三元组：
    本波**不加列**（同一节），故「三维键」是靠这一列的字符串承载的。

    ------------------------------------------------------------------
    ⚠️⚠️ **它同时是那一列的宽度收口点**（Plan 06 Task 12 / C1）
    ------------------------------------------------------------------

    ``login`` 那一格的原文**是客户端可控的**：``POST /api/auth/{students,teachers}/bind``
    在「标识不在册」那一档**照样计数**（:class:`app.db.models.auth.LoginAttempt` 的
    模块 docstring 第三节逐字要求：否则一个匿名调用方每次换一个编造的串就能无限试下去），
    于是 ``payload.student_no`` 的**原文**会一路走到本函数。⚠️ 实测取证：一个匿名的
    ``POST /api/auth/students/bind`` 带一个 **500 字符**的学号，改前落库的
    ``login_attempt.login`` 是 **505** 个字符（``len("bind:") + 500``），
    而那一列声明的是 ``String(64)``。

    ⚠️ 于是 Plan 06 Task 11 那条守卫（``声明宽度 ≥ 名册列宽 + 最长前缀`` = 64 ≥ 37）
    **量的不是这一格**：它灌的是「一个**在册形状**的最长原文」，而本档灌的是
    「一个**不在册**的任意长原文」。两者都要有界，故收口点在这里 —— 而**不是**在
    ``bind`` 端点上：五个动作都经本函数，端点上设防只堵住两个 ``bind``，
    而「一个 400 字符的键」在 :func:`failure_count` 与 :func:`record_failure` 上
    就会**算出两个不同的键**（那比超宽更坏：限流恒不生效）。

    ⚠️⚠️ **截断在这里是安全的**（派单点名要核「截断会不会毁掉用途」）：
    :class:`app.db.models.auth.LoginAttempt` 的列注释逐字警告过「MySQL 的静默截断会让
    两个不同的绑定键撞成同一个 ⇒ 限流误伤登录」。⚠️ 那一格说的是**数据库自己**在
    一个比声明宽度更宽的值上截断（截到哪一位由后端决定、且**不留标记**）；
    本函数是**在写入之前**按同一个声明宽度截、并且留下
    :data:`app.db.width.OVERLONG_SUFFIX`。⚠️ 于是「误伤登录」不可能发生：
    一个**合法**的键最长是「最长前缀 + 名册列宽」（今天实测 37），
    而一个被截过的键**恒等于**声明宽度（64）—— 两者长度不同，故永不相撞。
    撞只可能发生在**两个超宽的垃圾键**之间，而那些键指向的标识本来就不在册。

    ⚠️ 失效方向：截断只影响「一个不在册的超长标识」的计数器分组，
    不影响任何一次**合法**登录或绑定的判定（它们的键逐字不变）。
    """
    column = LoginAttempt.__table__.c.login
    return db_width.truncate(
        _KEY_PREFIX_BY_PURPOSE[_check_purpose(purpose)] + login,
        db_width.declared_width(column),
    )


def _ip(ip: str | None) -> str | None:
    """``login_attempt.ip`` 那一格的宽度收口（Plan 06 Task 12 / C1）。

    ⚠️ **它今天不是客户端可控的**（实测取证见 ``tests/api/test_column_widths.py``）：
    三个调用方一律交 ``request.client.host``（:mod:`app.api.routers.auth`），
    那是 ASGI 服务器从**套接字对端**读出来的地址，本仓**没有任何一处**解析
    ``X-Forwarded-For``（一个客户端可以随便写的请求头）。故实测最长写入是
    IPv6 文本形式的上界（45 个字符，IPv4-mapped 那一档），远在 ``String(64)`` 之内。

    ⚠️⚠️ **而它仍然设防**，两条理由：① :func:`record_failure` / :func:`record_success`
    是**公有面**，「谁都可以交一个串进来」在类型上成立 —— 而「把反代塞进来的
    ``X-Forwarded-For`` 也存上」正是 :class:`app.db.models.auth.LoginAttempt.ip`
    那一列的注释**点名预留**的将来（``64 给「反代塞进来的 X-Forwarded-For 一类」留出余量``），
    而那一步一旦做了，这一格当场从「不可控」变成「完全可控」（一个调用方可以在那个头里
    塞任意长的串）；② 它的成本是一次 ``len()`` 比较。

    ⚠️ **用哨兵而不是截断**（:func:`app.db.width.overlong_sentinel`）：IP 是**有格式**的列，
    截断它会得到一个**语法上仍然像 IP 的假 IP**，而这一格的全部用途是事后线索
    （「这个标识是被谁试的」）—— 一条指向不存在的主机的线索比一句「装不下」更坏。
    """
    column = LoginAttempt.__table__.c.ip
    return db_width.overlong_sentinel(ip, db_width.declared_width(column))


def _throttle(
    max_var: str,
    window_var: str,
    lock_var: str,
    defaults: "tuple[int, int, int]",
    noun: str,
) -> LoginThrottle:
    """**一组**三格阈值的解析：环境变量 > 字面量缺省。

    ⚠️⚠️ 它是「三格怎么解析」在全仓的**唯一住址**（Plan 06 Task 10 从
    :func:`throttle` 的函数体里提上来的）：:func:`throttle`（登录）与
    :func:`bind_throttle`（绑定）各自只交出**自己的三个变量名 + 自己的三个缺省 +
    自己那个人话名词**。⚠️ 于是「下界怎么判、坏值怎么报、分钟怎么变成
    ``timedelta``」三件事各只有一份 —— 两份的话，失效形态是「绑定那一组的坏值
    没人校验」（一个静默的 ``window = 0`` 就等于关掉限流）。

    ⚠️ 三格的**下界不同**，逐格的理由：

    * ``max_fails`` **≥ 1**：``0`` 的意思是「0 次失败就算达到阈值」，于是**每一次**
      {noun}（含成功的）都落进锁定档 = 谁都{noun}不了，而报错会指向一个与真因无关的地方。
      ⚠️ 报错里**指路**「要关掉限流请把 ``{lock_var}`` 设成 0」——
      否则运维的下一个动作是把 ``max_fails`` 设成一个巨大的数，而那**仍然每次失败都写一行库**
      （表照样长，只是永远数不到阈值）。
    * 两个分钟数 **≥ 0**（``0`` 是**合法**的 = 关掉那一格：``window = 0`` 让窗口退化成
      「只看此刻」= 事实上不计数，``lock = 0`` 让 ``(now - latest) < 0`` 恒假 = 不锁）。
      ⚠️ **负值一律拒收**，理由是一条静默失效：负的时长会让「窗口起点」
      ``now − window`` 跑到**未来**去，于是 ``at >= 起点`` 恒为假、
      限流**恒不生效**、而没有任何一处报错。

    ⚠️ ``noun`` 会进报错文本（与 :func:`_int_from_env` 的同名入参同一条理由）：
    两组共六个变量都是整数，而「必须是一个整数」这一句对运维没有信息量
    （他要知道是**哪一个**写错了、以及那是**哪一件事**的阈值）。
    """
    default_max, default_window, default_lock = defaults
    max_fails = _int_from_env(max_var, default_max, "失败次数阈值")
    if max_fails < 1:
        raise ValueError(
            f"{max_var}（失败次数阈值）必须 ≥ 1（0 会让每一次{noun}都落进锁定档，"
            f"于是谁都{noun}不了；要关掉限流请把 {lock_var} 设成 0），"
            f"收到 {max_fails}"
        )
    return LoginThrottle(
        max_fails=max_fails,
        window=dt.timedelta(
            minutes=_int_from_env(window_var, default_window, "计数窗口分钟数")
        ),
        lock=dt.timedelta(
            minutes=_int_from_env(lock_var, default_lock, "锁定时长分钟数")
        ),
    )


def throttle() -> LoginThrottle:
    """**登录**那一组三格阈值（``PE_LOGIN_*``，缺省 5 / 15 / 15）。

    ⚠️ 解析本身住在 :func:`_throttle`（与 :func:`bind_throttle` 共用一份）。
    ⚠️ 本函数**刻意保留原名**（不叫 ``login_throttle``）：它是 Plan 06 Task 3 起的
    公有面，而 ``tests/auth/test_policy.py`` 与
    ``tests/api/test_auth_api.py`` 都按这个名字钉它；改一次名要动十几处，
    而它换来的只是对称 —— 不值得（硬规矩 #39 的反面：不为修辞付改动面）。
    """
    return _throttle(
        MAX_FAILS_ENV_VAR,
        WINDOW_MIN_ENV_VAR,
        LOCK_MIN_ENV_VAR,
        (DEFAULT_MAX_FAILS, DEFAULT_WINDOW_MINUTES, DEFAULT_LOCK_MINUTES),
        "登录",
    )


def bind_throttle() -> LoginThrottle:
    """**绑定**那一组三格阈值（``PE_BIND_*``，缺省 **3 / 15 / 60**）。

    ⚠️ 三格**一律比登录那一组更严**，逐字算术（2 900 个可信出生日期 ⇒ 480 次/天
    是 16.5%/天/账号、72 次/天是 2.5%/天/账号）住在模块 docstring 的
    「绑定那一组阈值比登录更严」那一节，本处不复述第二份。
    ⚠️ 返回的类型与登录那一组**是同一个** :class:`LoginThrottle`：它答的是
    「一组三格阈值」，而名字里的 ``Login`` 是 Plan 06 Task 3 的历史名
    （⚠️ 刻意不改名，理由逐字见 :func:`throttle` 的 docstring 末段）。
    """
    return _throttle(
        BIND_MAX_FAILS_ENV_VAR,
        BIND_WINDOW_MIN_ENV_VAR,
        BIND_LOCK_MIN_ENV_VAR,
        (
            DEFAULT_BIND_MAX_FAILS,
            DEFAULT_BIND_WINDOW_MINUTES,
            DEFAULT_BIND_LOCK_MINUTES,
        ),
        "绑定",
    )


def _policy_of(purpose: str) -> LoginThrottle:
    """「**哪个用途用哪一组阈值**」的唯一判据。

    ⚠️ 五个动作一律经它取阈值，故「绑定那一档读了登录的阈值」这种串线
    在结构上不可能发生。⚠️ 它与 :func:`_key` 是**两个**住址、各答一件事
    （一个答「键长什么样」、一个答「阈值是多少」），而两者都先经
    :func:`_check_purpose`，故一个不认识的 ``purpose`` 在两处都会**响亮地**抛。
    """
    return throttle() if _check_purpose(purpose) == PURPOSE_LOGIN else bind_throttle()


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
    db: Session,
    kind: str,
    login: str,
    *,
    purpose: str = PURPOSE_LOGIN,
    now: dt.datetime | None = None,
) -> int:
    """这个 ``(kind, purpose, login)`` 在**当前回看窗口内**被记下的失败次数。

    ⚠️ 它是「计数」这件事在全仓的唯一住址：:func:`is_locked` 与守卫测试都经它，
    故「窗口怎么算」不可能有两份。
    ⚠️ 一次 ``SELECT count(*)``、**不拉行**：本表是单调增长的，
    而判定只需要一个数。

    ⚠️ **``purpose`` 有缺省值 ``PURPOSE_LOGIN``**（Plan 06 Task 10）：那是为了让
    Plan 06 Task 3 起的全部既有调用方（:func:`app.api.routers.auth.login` 与
    ``tests/auth/test_policy.py`` 的十几处）**一行都不用改**，而缺省值指的正是
    它们本来就在做的那一件事。⚠️ 绑定那一侧的调用方一律**显式**交
    ``purpose=PURPOSE_BIND``（:mod:`app.api.routers.auth` 的两个 ``bind`` 端点），
    故「忘了交 purpose」这个失效只会退化成「绑定用了登录那一组阈值 + 登录那一个键」
    —— 而那一档由 ``tests/auth/test_policy.py`` 的**交叉不污染**守卫当场抓到。
    ⚠️ 键与阈值各自只有一个住址（:func:`_key` / :func:`_policy_of`），本函数只经它们。
    """
    current = _clock(now)
    return int(
        db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.kind == kind,
                LoginAttempt.login == _key(purpose, login),
                LoginAttempt.ok.is_(False),
                LoginAttempt.at >= current - _lookback(_policy_of(purpose)),
            )
        )
        or 0
    )


def is_locked(
    db: Session,
    kind: str,
    login: str,
    *,
    purpose: str = PURPOSE_LOGIN,
    now: dt.datetime | None = None,
) -> bool:
    """这个 ``(kind, purpose, login)`` **此刻**是不是在锁定期内（算式见模块 docstring 第一节）。

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
    ⚠️ 于是「锁定档不做任何昂贵步骤」这件事**由调用方的位置**保证：两个 ``bind``
    端点把本函数排在**查 subject 行之前**，故锁定档既不查 ``student`` / ``teacher``、
    也不跑 :func:`app.auth.passwords.hash_password`（绑定路径上唯一那一次 PBKDF2）。
    守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_the_locked_bind_tier_never_reads_the_roster_nor_hashes_a_password``。

    ⚠️ ``purpose`` 的缺省与「忘了交会怎样」逐字见 :func:`failure_count` 的 docstring。
    """
    policy = _policy_of(purpose)
    if failure_count(db, kind, login, purpose=purpose, now=now) < policy.max_fails:
        return False
    current = _clock(now)
    latest = db.scalar(
        select(func.max(LoginAttempt.at)).where(
            LoginAttempt.kind == kind,
            LoginAttempt.login == _key(purpose, login),
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
    purpose: str = PURPOSE_LOGIN,
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
    ⚠️⚠️ **绑定那一档不是这样**（Plan 06 Task 10，如实记）：``bind`` 端点在
    403 那一档**只有过一次 ``SELECT``**（查 subject 行），故这一次 commit 提交的
    就是本行、没有别的写入被顺带提交；⚠️ 而**成功**那一档是相反的
    （:func:`record_success` 的那一次 commit 会**顺带**把 ``password_hash`` 那一次
    UPDATE 一起提交 —— 那是有意的，逐字理由见那个函数的 docstring）。

    ⚠️ ``purpose`` 的缺省与「忘了交会怎样」逐字见 :func:`failure_count` 的 docstring。
    """
    db.add(LoginAttempt(
        kind=kind, login=_key(purpose, login), ok=False, at=_clock(now), ip=_ip(ip)
    ))
    db.commit()


def clear_failures(
    db: Session, kind: str, login: str, *, purpose: str = PURPOSE_LOGIN
) -> int:
    """删掉这个 ``(kind, purpose, login)`` 的**全部**行（成功与失败都删），返回影响行数。

    ⚠️ **删的是全部行、不只是 ``ok=False`` 的行**：留着上一次成功的 ``ok=True``
    行没有任何判定用途（:func:`is_locked` 只看失败行），而本表是单调增长的，
    一次成功登录是**唯一**一个可以安全收缩它的时机。
    ⚠️ 它**不 commit**：生产路径上唯一的调用方是 :func:`record_success`，
    那一次 DELETE 与紧随的
    那一次 INSERT 必须是**同一个**工作单元（否则「删了旧行、还没写新行」的窗口里
    另一个请求会看到「这个标识从来没试过」——那正是限流要防的形状）。
    ⚠️⚠️ **它按 ``purpose`` 删**（Plan 06 Task 10）：一次成功的**绑定**只清掉
    绑定那一个键的行，**不动**同一个人登录那一个键的行（反之亦然）。
    ⚠️ 少了那一格的失效形态是具体的：按 ``(kind, login)`` 删的话，一次成功的绑定
    会把那个人**登录**的失败行一起删掉 —— 于是「一个匿名调用方先猜错四次口令、
    随后那个人自己绑定成功」会把攻击者那四次失败**抹掉**，他于是又能再猜五次
    （而不是只剩一次）。⚠️ 反过来（一次成功登录清掉**绑定**的失败行）同样是给
    攻击者续命：一个已经登录进去的人每登录一次就把别人对他账号的绑定猜测清零。
    ⚠️ 守卫是 ``tests/auth/test_policy.py`` 的
    ``test_clearing_one_purpose_leaves_the_other_purposes_rows_alone``。
    """
    return db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.kind == kind, LoginAttempt.login == _key(purpose, login)
        )
    ).rowcount


def record_success(
    db: Session,
    kind: str,
    login: str,
    *,
    purpose: str = PURPOSE_LOGIN,
    ip: str | None = None,
    now: dt.datetime | None = None,
) -> None:
    """一次成功（登录**或**绑定）：**清零**这个 ``(kind, purpose, login)`` 的失败计数，
    并写一行 ``ok=True``。

    ⚠️ 「清零」的实现是 :func:`clear_failures` 那一次 DELETE + 本函数那一次 INSERT，
    两者在同一个事务里（``commit`` 只有一次，在末尾）。
    ⚠️ **仍然写一行 ``ok=True``**（而不是「删完就完」）：删完之后的库里没有任何痕迹
    说明这个标识刚刚成功过，而下一个人来查「为什么这个标识一条失败记录都没有」
    时得到的是一个无法区分的答案（从来没失败过 / 失败了但被清了）。
    ⚠️ 而它**不是**审计留痕（那是 Task 5 的 ``audit_log``）：本行会被下一次成功
    删掉，故它答的只是「此刻这个键的计数器是干净的、且干净是因为一次成功」。

    ⚠️⚠️ **绑定那一档的一次 commit 顺带提交了 ``password_hash`` 那一次 UPDATE**
    （Plan 06 Task 10，如实记）：``bind`` 端点在 ``rowcount == 1`` 之后调本函数、
    **不再自己 commit**，于是「口令哈希落库」与「计数器清零」落在**同一个**事务里。
    ⚠️ 那是**有意**的、且与 :func:`app.api.routers.auth.login` 的顺序逐字同一条口径
    （那里是「清零排在 ``issue`` 之前」）：反过来（先 commit 业务写入、再清零）会留下
    一个「口令已经绑上、而计数器还没清」的窗口，而那个窗口里另一个请求会看到旧的失败数
    —— 于是一个刚刚绑定成功的人可能仍然被锁在门外。
    ⚠️ 代价（硬规矩 #39）：本函数因此**不只是**一个限流动作，它在绑定那一档上
    同时是那一次业务写入的提交点。要拆开就得让端点自己 commit 两次，
    而那正是上面那个窗口。已如实记录、不拆。

    ⚠️ ``purpose`` 的缺省与「忘了交会怎样」逐字见 :func:`failure_count` 的 docstring。
    """
    clear_failures(db, kind, login, purpose=purpose)
    db.add(LoginAttempt(
        kind=kind, login=_key(purpose, login), ok=True, at=_clock(now), ip=_ip(ip)
    ))
    db.commit()
