"""Plan 05A：服务端会话表 ``user_session``（spec §13 的「登录」那一节）。

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

⚠️ **实现者复核后补一条事实**（它不推翻裁定，但改掉裁定的一半理由）：冗余**并没有**
省掉那次 JOIN——:func:`app.auth.sessions.resolve` 无论如何都要回查 subject 行
（上面那条「subject 已删当场吊销」要求它）。故冗余真正买到的是
「降权不需要重新登录」这件事**可以不做**，而不是「少一次查询」。
要收紧的话，把 ``resolve`` 里教师的 role 改成以 ``teacher`` 表为准、
会话行上那一份只当留痕即可，那是一次一行的改动。

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

from sqlalchemy import DateTime, Integer, String
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
