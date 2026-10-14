"""鉴权的两张运行时表：``user_session``（Plan 05A）与 ``login_attempt``（Plan 06 Task 3）。

两张表都是 spec §13「登录」那一节的落点，且**都只由 HTTP 请求写**（不由管道、不由 seed）。
它们回答的是两个不同的问题：``user_session`` 答「**这个 cookie 是谁**」，
``login_attempt`` 答「**这个标识最近被试错了多少次**」。故它们刻意是两张表而不是一张
——一次登录成功后会话行要活两小时，而限流计数在成功那一刻就该清零；把两件事塞进一张表
会让「清零」变成一次 ``UPDATE``（要留行）或一次 ``DELETE``（要丢会话），两个都不对。

--------------------------------------------------------------------------
Plan 05A：服务端会话表 ``user_session``
--------------------------------------------------------------------------

**为什么是一张表而不是一个签名 cookie**（计划 §3.4 的裁定 (a)，三条理由逐字抄在这里，
因为它们是这整个模块的存在理由）：

1. **登出是真的失效**。HMAC 签名的自包含 cookie 的「登出」只是客户端把那串丢掉，
   被偷走的 cookie 在 ``exp`` 之前**照样能用**；而用户 2026-10-12 说现状「有点太粗糙了」，
   「登出登不掉」正是那一类粗糙。服务端行 + ``revoked_at`` 一列，登出就是一次 UPDATE。
2. 只多一张表，代价可控。
3. 与本仓「一切承重的事实都落在库里、可追溯」的既有纪律一致
   （``daily_sync_run`` / ``cleaning_log`` 都是这个形状）。

**代价（如实记，硬规矩 #39）**：**过期行不会自己消失**。原型不做清理任务
（那要一个定时进程，而本项目只有一个 ``uvicorn``），故 ``user_session`` 会单调增长。
生产需要一个清理任务（``DELETE FROM user_session WHERE expires_at < now − 7 天``），
已登记为待清扫。⚠️ 而「过期或被吊销的会话不能用」这一条**有守卫**
（``tests/auth/test_sessions.py``），故增长是空间问题、不是安全问题。

--------------------------------------------------------------------------
⚠️⚠️ ``subject_id`` **刻意不建外键**（计划 §3.1 标注「本计划最容易漏的一格」）
--------------------------------------------------------------------------

它要同时指向 ``student.id`` 与 ``teacher.id``，而**多态外键在 SQL 里不存在**
（一个 ``REFERENCES`` 只能指一张表；两张表各建一个可空外键则还要求
「恰好一个非空」这条互斥约束，而 SQLite 的 CHECK 能表达互斥、却表达不了
「非空的那一个必须真的存在」——两个外键各自都合法，于是 ``kind='student'`` 的行
可以把 ``subject_id`` 写成某个**教师**的 id 而两个外键都不响）。

连带的三件事，每一件都在别处有落点：

* :func:`app.api.crud._child_tables` **探测不到它**（那个函数扫的是 ``foreign_keys``），
  故 ``DELETE /api/students/{id}`` 的 ``restrict`` 那一档**看不见**指向该学生的会话行
  ——删学生会留下孤儿会话行；
* 于是**吊销必须在解析会话时做**：:func:`app.auth.sessions.resolve` 每次都回查一次
  subject 行，查无此人就**当场写 ``revoked_at``** 并按「没有身份」处理（→ 401）。
  守卫是 ``tests/api/test_auth_api.py`` 的
  ``test_a_session_whose_subject_has_been_deleted_is_revoked_on_the_next_request``
  （删掉一个学生 → 他的旧 cookie **立刻 401**，不是 500、也不是照常放行）；
* ``role`` 那一列因此是**冗余**存的（见下一节）。

--------------------------------------------------------------------------
⚠️ ``role`` 冗余存一份：理由与代价（计划 §3.1 的裁定，实现者复核后维持）
--------------------------------------------------------------------------

不冗余的话，「这个人是不是管理员」这个问题只能问 ``teacher`` 表。冗余了则
**「管理员被降权成教师」不会立刻生效**——要等他重新登录。控制者裁定冗余，
原型可接受（降权是极罕见操作），代价写进 spec §13。

⚠️ **实现者复核后补两条事实**（它们不推翻裁定，但改掉裁定的两条理由）：

1. 冗余**并没有**省掉那次 JOIN——:func:`app.auth.sessions.resolve` 无论如何都要回查
   subject 行（上面那条「subject 已删当场吊销」要求它）。故冗余真正买到的是
   「降权不需要重新登录」这件事**可以不做**，而不是「少一次查询」。
2. ⚠️⚠️ **而「降权不会立刻生效」这一句在安全档上是不成立的**（Plan 05A Task 2 实测）：
   后端的两道 role 闸门（:func:`app.api.deps.require_admin` 与
   ``require_teaches_section`` / ``require_teaches_student`` 的管理员越过那一支）
   都经 :func:`app.api.deps.require_staff`，而它查的是 **``teacher`` 表**、
   **不是本表这一列**。故降权对**权限**是立刻生效的（下一次请求就 403）；
   滞后的只有 ``GET /api/auth/me`` 与登录响应体里那个 ``role``
   ——而那一格是**前端路由**的判据，不是后端闸门的判据。
   ⚠️ 于是这一列的真实代价是 **UI 一致性**（被降权的人在重新登录之前，
   前端仍会把他送到 ``/admin``，然后每一次写都吃一个 403），失效方向是安全的。
   守卫是 ``tests/api/test_auth_api.py`` 的
   ``test_demoting_an_admin_takes_the_console_away_immediately_but_not_the_me_projection``
   与 ``tests/auth/test_sessions.py`` 的
   ``test_a_demoted_admin_keeps_the_role_recorded_on_his_live_session``（各钉一半）。

要收紧的话，把 ``resolve`` 里教师的 role 改成以 ``teacher`` 表为准、
会话行上那一份只当留痕即可，那是一次一行的改动（⚠️ 而按第 2 条，
它换来的只是「前端不再多显示一个入口」，不是「权限不再滞留」）。

--------------------------------------------------------------------------
本模块刻意不做的事
--------------------------------------------------------------------------

* **不声明 ``relationship``**（本包六个既有表模块同一条约定）：会话按 ``id`` 点查，
  显式 ``select`` 比懒加载可预测，也不会在 ``Session`` 关闭后触发延迟查询。
* **不进 ``app.db.models`` 的公有导入面**（Ruling 97 / 硬规矩 #102）：
  ``models/__init__.py`` 对本模块是 ``from . import auth``（**非星号**），故
  ``UserSession`` 只能按 ``from app.db.models.auth import UserSession`` 引用。
  理由是那条基线守卫钉的是**拆包之前**实测的 33 个公有名，往里加名字等于把
  「拆包没改导入面」偷换成「拆包后的现状」（两侧同源，硬规矩 #35）。守卫是
  ``tests/db/test_models.py::test_new_tables_stay_out_of_the_models_public_namespace``。
* **不带 ``batch_id``**：它不是管道产物，``repo.delete_by_batch`` 不该碰它
  （守卫 ``tests/db/test_models.py::test_only_batch_owned_tables_expose_batch_id``
  按**集合相等**判，故这张新表必须不在那九张里）。
* **不是 :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源**：会话行没有
  「匿名可读的列表」这一档，它的读端点是 ``GET /api/auth/me``、写端点是
  ``POST /api/auth/{login,logout}``，四个都是手写的特例端点。
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import _in_domain


class UserSession(Base):
    """一次登录产生的一行服务端会话。cookie 里只放它的主键（一个不透明串）。

    8 列。⚠️ **主键是 ``String(64)`` 而不是自增整数**：它是
    :func:`secrets.token_urlsafe` 产出的 48 字节随机串的 URL-safe base64
    （48 字节 → 恰好 64 个字符，故列宽与它逐字对齐）。用随机串而不是自增整数
    有两个理由：

    1. 自增 id 是**可枚举**的，而它就是要放进 cookie 的那个值——拿到一个 cookie 的人
       能推出「大约有多少人登录过」，也能挨个试别人的 id；
    2. 随机串让「id 本身不含任何信息」这件事成立（它不是第几个会话、也不隐含时间）。

    列宽由 :data:`app.auth.sessions.TOKEN_BYTES` 决定，守卫是
    ``tests/auth/test_sessions.py`` 的
    ``test_the_token_fits_the_column_and_the_column_is_exactly_as_wide``
    （⚠️ 那条守卫**两侧不同源**：期望侧是列宽的字面量 64 与 ``token_urlsafe`` 的
    长度算式，被测侧是 200 次真实签发的最大长度）。
    """

    __tablename__ = "user_session"

    #: ``kind`` 的取值域。⚠️ 它是「``subject_id`` 该去哪张表回查」的唯一判据，
    #: 故 :data:`app.auth.sessions.KINDS` **就是本集合**（那一处 ``from`` 的是这里，
    #: 不是第二份词表）——本包约定 2：类常量是唯一真相，CHECK 文本由它生成。
    KINDS: set[str] = {"student", "teacher"}

    #: ``role`` 的取值域。**三个**值而不是两个：学生会话的 role 是 ``"student"``
    #: （不是 ``None``）——那一列 ``NOT NULL``，而「学生的角色叫什么」这件事需要一个
    #: 字面值。⚠️ 于是本集合是 :attr:`app.db.models.organisation.Teacher.ROLES` 的
    #: **超集**，两者刻意不合并：教师的 role 只有 ``teacher`` / ``admin``，
    #: 而会话行的 role 还要能装 ``student``。
    #: ⚠️ 两份词表的一致性由 ``tests/auth/test_sessions.py`` 的
    #: ``test_the_role_vocabulary_of_a_session_is_the_teacher_one_plus_student`` 钉住。
    ROLES: set[str] = {"student", "teacher", "admin"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    # ⚠️ 刻意不是外键（模块 docstring 第二节）：它要同时指向 student.id 与 teacher.id。
    subject_id: Mapped[int] = mapped_column(Integer)
    # ⚠️ 冗余存一份（模块 docstring 第三节）。
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    # 滑动过期的落点：每个带有效 cookie 的请求都把它与 expires_at 一起往后推
    # （app.auth.sessions.resolve）。⚠️ 于是 ``last_seen_at - created_at`` 是
    # 「这个会话被用了多久」，而 ``expires_at - last_seen_at`` 恒等于那个 TTL。
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime)
    # 登出 = 写这一列（**不是删行**）：留痕，且让「被偷的 cookie 在登出后失效」可追溯。
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        _in_domain("kind", KINDS, "ck_user_session_kind"),
        _in_domain("role", ROLES, "ck_user_session_role"),
    )


class LoginAttempt(Base):
    """一次**登录尝试**的限流记录（Plan 06 Task 3）。

    ------------------------------------------------------------------
    ⚠️⚠️ 它是**限流键的存储**，不是审计日志
    ------------------------------------------------------------------

    这两件事看着像同一件（都叫「记一行登录」），而它们要的东西相反：审计要**永久留痕**
    （谁在什么时候从哪来试过什么），限流要**能被清零**（一次成功登录就把这个标识的失败
    计数抹掉，:func:`app.auth.policy.clear_failures`）。塞进一张表的话，「清零」要么是
    一次 ``DELETE``（审计留痕当场没了）、要么是一次 ``UPDATE``（于是「失败次数」变成
    一个可以被改写的数，而审计的第一条性质就是不可改写）。故本表**只管限流**，
    审计留痕是 Plan 06 Task 5 的 ``audit_log``（本波不实现）。
    ⚠️ 于是「一个账号被锁过几次」这件事今天**在库里查不到**——被锁的合法用户也
    得不到任何提示（理由见 :mod:`app.auth.policy` 的模块 docstring），
    那一格的可见性留给 Task 5。已写进 spec 的已知局限。

    ------------------------------------------------------------------
    ⚠️ ``login`` 存的是**原文**（学号 / 工号），不是哈希
    ------------------------------------------------------------------

    它是**限流键**，不是凭据：查询形状是
    ``WHERE kind = ? AND login = ? AND at >= ?``（一次等值 + 一次范围），
    而哈希之后仍然要按同一个键等值查（故它不减少任何一次查询），
    换来的只是「拿到这个库的人读不出被试过的是哪些学号」。
    ⚠️ **而那一句今天已经不成立**：同一个库里 ``student.student_no`` 与
    ``teacher.staff_no`` 就是原文，且 ``login_attempt.login`` 的取值域**恰好是**
    那两列的子集——把这一列哈希掉，只是让「哪一个人被试过错口令」这一个事实变得
    难读，而「有哪些学号」仍然摆在 ``student`` 表里。
    ⚠️ 学号/工号在本系统里**不是秘密**（它们被印在校园卡上、被念在课堂上、
    是 ``GET /api/students`` 的响应体字段），与口令不是一类东西。故存原文。
    ⚠️⚠️ 而**列宽不再与那两列逐字相同**（Plan 06 Task 11 起本列是 ``String(64)``，
    名册那两列仍然是 ``String(32)``）：Plan 06 Task 10 把「用途」那一维编进了
    本列的前缀，于是写进来的串是 ``前缀 + 原文``、比名册原文长。
    那个 64 的来历与「不许改回 32」的理由逐字见 :attr:`LoginAttempt.login` 的列注释。

    ------------------------------------------------------------------
    ⚠️ 没有外键（与 ``user_session.subject_id`` 同一条理由，但更彻底）
    ------------------------------------------------------------------

    ``login`` 是**原文的学号/工号**、不是 ``student.id`` / ``teacher.id``，
    而多态外键在 SQL 里不存在（:class:`UserSession` 的模块 docstring 第二节）。
    ⚠️ 于是本表**必然**会留下「指向一个不在册的标识」的行——而那正是限流最要挡的形状：
    一个匿名调用方可以拿**任意编造的**学号试口令，若限流键必须先在册才生效，
    他只要每次换一个不在册的串就能无限试下去（同时把 ``student`` 表的枚举面打满）。
    故「标识不在册」也**照样计数**：:func:`app.api.routers.auth.login` 在
    「口令验不过」那一档写 ``ok=False``，与在册与否无关。
    ⚠️ 连带：``app.api.crud._child_tables`` 探测不到本表（它扫 ``foreign_keys``），
    故删一个学生不会级联删他的登录尝试行。这一档**是可接受的**：那些行不含任何
    指向该学生的代理键，删掉学生之后它们只是一串学号文本，不构成孤儿引用。

    ------------------------------------------------------------------
    本模块刻意不做的事（与 :class:`UserSession` 同一份约定）
    ------------------------------------------------------------------

    * **不声明 ``relationship``**；
    * **不进 ``app.db.models`` 的公有导入面**（Ruling 97）：``models/__init__.py`` 对本
      模块是 ``from . import auth``（非星号），故只能写
      ``from app.db.models.auth import LoginAttempt``。守卫是
      ``tests/db/test_models.py::test_new_tables_stay_out_of_the_models_public_namespace``；
    * **不带 ``batch_id``**（它不是管道产物；守卫按集合相等判，故本表必须不在那九张里）；
    * **不是 :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源**：它没有任何
      读端点（连管理员也没有——见上面「不是审计日志」那一段）。
    """

    __tablename__ = "login_attempt"

    #: ``kind`` 的取值域。⚠️ **它就是 :attr:`UserSession.KINDS` 那一个对象**
    #: （本包约定 2：类常量是唯一真相，CHECK 文本由它生成）——「一次登录尝试属于
    #: 哪一类人」与「一个会话属于哪一类人」是**同一个**取值域，写两份的话
    #: 加第三类身份（例如「家长」）时只改到其中一份，而漏掉的那一份是静默的。
    KINDS = UserSession.KINDS

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: ``student`` / ``teacher``：限流键的前半段。⚠️ 它**必须**进键里——
    #: 学号与工号的取值域今天不相交（``2023120001`` vs ``T0001``），但那是**数据事实**、
    #: 不是 schema 事实；少了 ``kind`` 的话「一个叫 ``1`` 的学号」与「一个叫 ``1`` 的工号」
    #: 会共用一个计数器。
    kind: Mapped[str] = mapped_column(String(16))
    #: 限流键的**后半段**（存的是学号/工号**原文**，理由见上面那一整段；
    #: ⚠️ Plan 06 Task 10 起「用途」那一维编在本列的**前缀**上，逐字理由见
    #: :mod:`app.auth.policy` 的模块 docstring「限流键多了一维」那一节）。
    #:
    #: ⚠️⚠️ **列宽刻意比 ``student.student_no`` / ``teacher.staff_no``（都是
    #: ``String(32)``）宽一格**（Plan 06 Task 11 / A1）：写进本列的已经不是名册原文、
    #: 而是 ``前缀 + 原文``，故它的上界是「**最长前缀 + 名册列宽**」，
    #: 那一个数今天实测是 ``len("bind:") + 32`` = **37**。
    #: 取 **64** 的理由：① 它是 37 的下一个整齐上界（2 的幂），
    #: ② 与同表的 ``ip`` 列、以及 :attr:`UserSession.id` 逐字同宽（本仓的「宽字符串」
    #: 只有 32 / 64 两档，不引第三个数），③ 给「将来再加一个用途前缀」留出余量
    #: ——再加一个 ``unbind:``（7 个字符）也只有 39，仍然远在 64 之内。
    #:
    #: ⚠️⚠️ **不许把这一格改回 32**：SQLite **不强制** ``VARCHAR(n)`` 的长度
    #: （实测：37 个字符写进一个声明 32 的列不报错、读回来也不截断），
    #: 故改回去在今天这个只跑 SQLite 的仓里**一切照旧**——那正是它危险的地方：
    #: 换 PostgreSQL 会**报错**、换 MySQL 会**静默截断**，而截断会让两个不同的
    #: 绑定键撞成同一个（⇒ 限流误伤登录）。⚠️ 本仓的**其余列**今天没有这一格：
    #: 那些「声明宽度 ≥ 实际最长值」的断言量的都是**不由前缀拼出来的**值。
    #:
    #: ⚠️ 守卫是 ``tests/auth/test_policy.py`` 的
    #: ``test_the_login_column_is_at_least_as_wide_as_the_longest_key_the_policy_writes``。
    #: ⚠️⚠️ 它的期望侧**刻意不是字面量 37**：它真的走一遍
    #: :func:`app.auth.policy.record_failure` 把**最长的那一个键**写进去、再量回来，
    #: 故「加宽名册列」与「换一个更长的前缀」两件事都会让它跟着变红——
    #: 写死 37 的话，下一次改前缀时它会**静默失效**。
    #: ⚠️ 迁移链的**第 4 条**（``login_attempt`` 的列宽）是这一格的 DDL 落点：
    #: SQLite 没有 ``ALTER COLUMN``，故它走 ``batch_alter_table``。
    login: Mapped[str] = mapped_column(String(64))
    #: 这一次尝试**成功了吗**。⚠️ ``ok=True`` 的行只在「登录成功」那一刻写一行，
    #: 而它的全部作用是让 :func:`app.auth.policy.clear_failures` 有一个可以留下的痕迹；
    #: 计数只看 ``ok == False`` 的行。⚠️ 写 ``ok=True`` 而不是「删掉全部失败行」：
    #: 删行的话「这个人刚刚成功登录过」这件事就不在库里了，而下一个人来查
    #: 「为什么这个标识没有失败记录」时得到的是一个无法区分的答案
    #: （从来没失败过 / 失败了但被清了）。
    ok: Mapped[bool] = mapped_column(Boolean)
    #: 这一次尝试的时刻。⚠️ **naive 本地时间**，口径与 :func:`app.auth.sessions.now`
    #: 逐字相同（先转到 :data:`app.config.TIMEZONE`、再摘掉 tzinfo）——
    #: SQLite 没有时区类型，而库里其余全部 ``DateTime`` 列都是 naive 本地时刻，
    #: 混进一个 UTC 会让「窗口起点」的比较差 8 小时（于是限流**恒不生效**，
    #: 因为窗口起点永远在未来）。⚠️ 这一格是本表最容易错的地方，
    #: 故 :func:`app.auth.policy.record` 只接受调用方交进来的 ``now``、
    #: 自己不取时钟（``now`` 可注入的另一半理由见那个函数的 docstring）。
    at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: 来源 IP（``request.client.host``）。**可空**：ASGI 服务器在 Unix socket 或
    #: 某些反代配置下给不出它，而限流键**不含 IP**（含的话攻击者换一个出口 IP 就绕过），
    #: 故它只是「事后看一眼这个标识是被谁试的」的一格线索，缺了不影响判定。
    #: ⚠️ 列宽 64：IPv6 的文本形式最长 45 个字符（``IPv4-mapped`` 那一档），
    #: 64 给「反代塞进来的 ``X-Forwarded-For`` 一类」留出余量。
    #: ⚠️ **它刻意不参与限流判定**（理由见上面那半句），故本表**没有**含它的索引。
    ip: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        _in_domain("kind", KINDS, "ck_login_attempt_kind"),
        # ⚠️ **全库第一个复合索引**（此前 9 个 ``ix_*_batch_id`` 都是单列的
        # ``index=True``）。它是限流那一次查询的形状：``kind`` 与 ``login`` 等值、
        # ``at`` 范围，故列序是 ``(kind, login, at)``——把范围列放最后，
        # 前两列的等值才能把扫描收窄到一个标识的行上。
        # ⚠️ 反过来的列序（``(at, kind, login)``）在 SQLite 上**只用得到第一列**，
        # 于是「这个标识最近 15 分钟失败了几次」退化成一次全表扫描，
        # 而本表是**单调增长**的（原型没有清理任务，与 ``user_session`` 同一条待清扫）。
        Index("ix_login_attempt_kind_login_at", "kind", "login", "at"),
    )
