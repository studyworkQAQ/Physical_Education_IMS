"""请求审计留痕的一张表：``audit_log``（Plan 06 Task 5）。

它回答的是甲方运维的那一个问题：**谁在什么时候对什么做了什么**。

--------------------------------------------------------------------------
⚠️⚠️ 它与 :class:`app.db.models.auth.LoginAttempt` 是两张表，不是一张
--------------------------------------------------------------------------

``login_attempt`` 的模块 docstring 第三节逐字写着「它是**限流键的存储**，不是审计日志」，
并把审计留痕指到了本表（当时写的是「Plan 06 Task 5 的 ``audit_log``（本波不实现）」）。
两者看着像同一件（都叫「记一行请求」），而要的东西相反：审计要**永久留痕、不可改写**，
限流要**能被清零**（一次成功登录就把这个标识的失败计数抹掉）。塞进一张表的话，「清零」
要么是一次 ``DELETE``（审计留痕当场没了）、要么是一次 ``UPDATE``（于是「发生过什么」
变成一个可以被改写的数）。故本表**只管留痕**：它没有任何一处写入方会 ``UPDATE``
或 ``DELETE`` 它的行（``GET /api/audit-logs`` 是只读的），也没有清理任务。

⚠️ **代价（如实记，硬规矩 #39）**：本表**单调增长**，与 ``user_session`` /
``login_attempt`` 同一条待清扫（原型没有清理任务）。故 :attr:`AuditLog.__table_args__`
里那个索引是**承重的**而不是优化：没有它，「今天有哪些写操作」是一次全表扫描。

--------------------------------------------------------------------------
⚠️⚠️ ``subject_id`` **刻意不建外键**（与 ``user_session.subject_id`` 同一条理由）
--------------------------------------------------------------------------

它要同时指向 ``student.id`` 与 ``teacher.id``，而**多态外键在 SQL 里不存在**
（逐字论证住在 :mod:`app.db.models.auth` 的模块 docstring 第二节，本处不抄第二份）。
⚠️ 连带：:func:`app.api.crud._child_tables` **探测不到它**（那个函数扫 ``foreign_keys``），
故删一个学生不会级联删他的审计行——**而那一档恰恰是对的**：审计行要在被审计的对象
消失之后仍然可读，否则「删掉一个学生」这个动作本身就把自己从审计里抹掉了。
（⚠️ 这与 ``login_attempt`` 那一条的理由不同：那一条是「不构成孤儿引用，故可接受」，
本条是「留痕必须在主体消失后仍然成立，故是**要的**」。）

--------------------------------------------------------------------------
⚠️⚠️ **隐私纪律：本表不存任何请求体内容**（派单 §1 第 3 条，逐字要求）
--------------------------------------------------------------------------

``POST /api/auth/login`` 的请求体里有**明文口令**，``POST /api/auth/students/bind`` 的
请求体里有**出生日期**与**新口令**。审计要的是「谁、什么时候、对什么、做了什么、
结果如何」这五格，而**没有一格需要请求体**：``method`` + ``path`` 答「做了什么」、
``subject_*`` 答「谁」、``at`` 答「什么时候」、``target`` 答「对什么」、``status``
答「结果如何」。

⚠️ 于是「不记请求体」不是一个取舍，而是**这张表的列清单里根本没有能装它的那一列**。
把它做成一条**结构性质**（而不是「中间件里克制住不写」）是有意的：下一个人想加一列
``body`` 时必须先改本文件，而改本文件会撞上下面那段守卫的取证口径。
守卫是 ``tests/api/test_audit_api.py`` 的
``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
——它**真的发一次带口令的 login**，然后把那一行审计的**全部 9 列**逐列扫一遍，
断言口令串与出生日期串一个都不出现（对已知反例验证，不是「我看代码里没写」）。

--------------------------------------------------------------------------
本模块刻意不做的事（与 :class:`app.db.models.auth.UserSession` 同一份约定）
--------------------------------------------------------------------------

* **不声明 ``relationship``**；
* **不进 ``app.db.models`` 的公有导入面**（Ruling 97 / 硬规矩 #102）：
  ``models/__init__.py`` 对本模块是 ``from . import audit``（**非星号**），故只能写
  ``from app.db.models.audit import AuditLog``。⚠️ **不能放进 :mod:`.ops`**：
  ``__init__.py`` 对 ``ops`` 是 ``from .ops import *``（星号），放进去会让 ``AuditLog``
  自动进入包的公有命名空间、当场撞红 ``_MODELS_PUBLIC_BASELINE``（33）那条守卫，
  而唯一的「修法」（把基线抬到 34）正是 Ruling 97 禁止的（P3-A1 的同一条）。
  守卫是 ``tests/db/test_models.py::test_new_tables_stay_out_of_the_models_public_namespace``；
* **不带 ``batch_id``**：它不是管道产物（守卫按**集合相等**判，故本表必须不在那九张里）；
* **不是 :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源**：它的读端点
  ``GET /api/audit-logs`` 是一个**手写的特例端点**（仅 ``role='admin'``），
  与 ``/api/health`` 同一族——泛型工厂的「匿名可读的列表」那一档对它根本不成立。
"""

import datetime as dt

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import _in_domain
from .auth import UserSession

#: ``subject_kind`` 的「**没有身份**」那一档。⚠️ **所有者在本模块**：
#: :attr:`AuditLog.SUBJECT_KINDS` 由它生成，:mod:`app.api.audit` 也从这里 import 它
#: （而不是在自己那边再写一个字面量 ``"anonymous"``）。
#:
#: ⚠️ **它是必需的、不是凑数的**（派单 §1 第 4 条）：鉴权失败的请求**也要记**，
#: 否则「谁在撞门」恰恰查不到——而 :mod:`app.auth.policy` 的锁定档**故意不给调用方
#: 任何提示**（「还剩几次 / 是不是被锁了」都是枚举信号），故审计是它**唯一**的可见性。
#: 那一格的账面逐字写在 :class:`app.db.models.auth.LoginAttempt` 的模块 docstring 里
#: （「『一个账号被锁过几次』这件事今天在库里查不到……那一格的可见性留给 Task 5」）。
ANONYMOUS_SUBJECT_KIND = "anonymous"


class AuditLog(Base):
    """一次**被审计的请求**的一行。9 列。

    ------------------------------------------------------------------
    ⚠️ ``at`` 是 **naive 本地时刻**，不是 UTC（本实现对派单的一处顶回）
    ------------------------------------------------------------------

    派单 §1 第 1 条写的是「``at``（UTC）」。实现者**顶回**，理由是一条实测的口径冲突：

    * 本库**其余全部** ``DateTime`` 列存的都是 naive **本地**时刻
      （:data:`app.config.TIMEZONE` = ``Asia/Shanghai``），唯一所有者是
      :func:`app.auth.sessions.now`（先转到那个时区、再摘掉 tzinfo）。
      SQLite 没有时区类型，故「naive」在库里看不出是哪一个时区的 naive。
    * ⚠️ **而 ``audit_log`` 与 ``login_attempt`` 记的是同一批事件**：一次失败的登录
      会在 ``login_attempt`` 写一行（``at`` = 本地）、在 ``audit_log`` 写一行。
      若后者是 UTC，同一次尝试的两行**差 8 小时**——而 Task 3 的报告与
      :class:`app.db.models.auth.LoginAttempt` 的 docstring 都指着本表说
      「锁定档的可见性在这里」，运维要做的**正是**把两张表按时间对齐着看。
    * ⚠️ ``LoginAttempt.at`` 那一列的注释已经把同一个失效形态写下来了：
      「混进一个 UTC 会让『窗口起点』的比较差 8 小时」。本表虽然不做窗口比较，
      但它要与人读的日志、与 ``user_session.last_seen_at``、与
      ``daily_sync_run.started_at`` 对齐，那是同一种差 8 小时。

    故本列取 :func:`app.auth.sessions.now`（**同一个**所有者），而
    :func:`app.api.audit.record` 是唯一的写入方。⚠️ 要改成 UTC 的话，
    正确的做法是**整库一起改**（含那三张既有表与 ``now()`` 本身），
    而不是给一张新表换一个时区口径。

    ------------------------------------------------------------------
    ``target``：从**路径参数**取，取不到就 ``None``（派单 §4 顶回 ③ 的裁定）
    ------------------------------------------------------------------

    派单点名了三条可能的顶回，第三条是「``target`` 那一格从哪取（路径里的 id 解析 vs
    响应体）」，并**当场裁定**了：**不要解析响应体**（要缓冲整个响应，代价大），
    从路径模板取即可，取不到就空。实现者复核后**同意**，逐字理由见
    :func:`app.api.audit.target_of`。

    ⚠️ 于是 ``POST /api/students``（新建）的 ``target`` 是 ``None``：新行的 id 只在
    响应体里。这一格如实记录为**已知局限**：审计能答「谁在什么时候往哪个集合里写了
    一行、结果码是什么」，答不了「写出来的那一行 id 是几」。要补的话有两条路
    （让端点把它塞进 ``request.state``、或缓冲响应体），都超出本 Task 的范围。
    """

    __tablename__ = "audit_log"

    #: ``subject_kind`` 的取值域 = 会话的那两档 + ``anonymous``。
    #: ⚠️ **它不是第二份词表**（本包约定 2）：前两格直接取自
    #: :attr:`app.db.models.auth.UserSession.KINDS` 那**一个对象**，
    #: 故「加第三类身份（例如家长）」时改 ``UserSession.KINDS`` 一处，本表自动跟上。
    #: ⚠️ ``|`` 造出一个**新集合**、不改 ``UserSession.KINDS`` 本身
    #: （``set.__or__`` 不是就地运算），故 ``ck_user_session_kind`` 仍然是两档。
    SUBJECT_KINDS: set[str] = UserSession.KINDS | {ANONYMOUS_SUBJECT_KIND}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: 这一刻（naive 本地时刻；理由见上面那一整段）。
    at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: ``student`` / ``teacher`` / ``anonymous``。⚠️ 列宽 16 与
    #: ``user_session.kind`` / ``login_attempt.kind`` 逐字相同（三张表同一族语义）；
    #: 域内最长值是 ``"anonymous"``（9 个字符）。
    subject_kind: Mapped[str] = mapped_column(String(16))
    #: ``student.id`` 或 ``teacher.id``；**匿名档为 ``NULL``**。
    #: ⚠️ 刻意不是外键（模块 docstring 第二节）。
    subject_id: Mapped[int | None] = mapped_column(Integer)
    #: 工号（``teacher.staff_no``）。**只教职那一档填**，学生与匿名为 ``NULL``。
    #: ⚠️ 为什么教职要多存一格而学生不用：教师侧的全部闸门
    #: （:func:`app.api.deps.require_staff` 一族）与 ``prescription.teacher_overrides``
    #: 里的 ``teacher_staff_no`` 都以**工号**为主语，而学生侧以 ``student.id`` 为主语
    #: （:func:`app.api.deps.require_scope` 的两个入参都是 ``int``）。
    #: 于是「查某个教务干事这学期改过什么」这一问，用 ``staff_no`` 一次等值就答完；
    #: 学号那一侧要先 JOIN ``student``。⚠️ 列宽 32 与 ``teacher.staff_no`` 逐字相同。
    staff_no: Mapped[str | None] = mapped_column(String(32))
    #: ``POST`` / ``PATCH`` / ``DELETE``。⚠️ **恒为大写**（HTTP 的方法令牌在
    #: ``scope["method"]`` 里就是大写，:func:`app.api.audit.should_record` 也按大写判）。
    #: ⚠️ 列宽 8：域内最长值是 ``"DELETE"``（6 个字符），8 给「将来记 ``PUT`` /
    #: ``OPTIONS``」留一格余量而不至于宽到看不出这是个方法列。
    #: ⚠️ **本列刻意没有 CHECK 约束**（与 ``subject_kind`` 不同）：「哪些方法被记」
    #: 这件事的唯一所有者是 :func:`app.api.audit.should_record` 那个函数
    #: （派单 §1 第 2 条逐字要求「记与不记的判据只住在一个函数里」），
    #: 再在 DB 上设一道会让那个判据有**两个**住址——而派单 §1 第 6 条要的定点变异
    #: 正是「把 GET 也记」，那时 DB 的 CHECK 会先炸出一个 ``IntegrityError``（500），
    #: 于是守卫红在错误的地方（红是红了，而它证明的不是「判据被改宽了」）。
    method: Mapped[str] = mapped_column(String(8))
    #: 请求路径的**原文**（不含查询串）。⚠️ 刻意是原文而不是路由模板
    #: （``/api/students/12`` 而不是 ``/api/students/{student_id}``）：审计要答的是
    #: 「对**哪一个**做了什么」，模板把那个 id 抹掉了、而 ``target`` 只在恰好一个
    #: 路径参数时才有值（:func:`app.api.audit.target_of`）。
    #: ⚠️ **不含查询串**是隐私纪律的一部分：查询串里可以塞任何东西
    #: （``?reason=<自由文本>``），而本表的列清单里**没有**能装它的那一列。
    #: ⚠️ 列宽 256：今天最长的路径模板是
    #: ``/api/students/{student_id}/prescriptions/current``（47 个字符），
    #: 256 给「占位符被一个长自然键填上」留出余量。SQLite 不强制 ``VARCHAR`` 长度，
    #: 故一个更长的路径不会报错、会照原样存下来。
    path: Mapped[str] = mapped_column(String(256))
    #: 响应码。⚠️ **失败也记**（401 / 403 / 409 / 422 / 500 一律照记）：
    #: 「谁在撞门」恰恰全在 4xx 里（模块 docstring 里 :data:`ANONYMOUS_SUBJECT_KIND`
    #: 那一段）。⚠️ 未被任何处理器接住的异常也记 **500**
    #: （:class:`app.api.audit.AuditMiddleware` 的 ``except`` 那一支）。
    status: Mapped[int] = mapped_column(Integer)
    #: 被写的那个资源的 id（**字符串**形式），取不到就 ``NULL``。
    #: ⚠️ 来源与「为什么是字符串」逐字见 :func:`app.api.audit.target_of`。
    #: ⚠️ 列宽 64：它今天装的是代理键（一个小整数）或 ``rpe_token`` 一类的短串。
    target: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        _in_domain("subject_kind", SUBJECT_KINDS, "ck_audit_log_subject_kind"),
        # ⚠️ **列序是 ``(subject_kind, at)``**（派单 §1 第 1 条给的两个选项之一）。
        # 它服务的是审计最常问的那一句：「**某一类人**在**某一段时间**里做了什么」
        # （``WHERE subject_kind = ? AND at >= ? ORDER BY at DESC``）——把范围列放最后，
        # 前一列的等值才能把扫描收窄到一类人的行上。
        # ⚠️ 与 ``ix_login_attempt_kind_login_at`` 是同一条口径（那个是
        # ``(kind, login, at)``，理由逐字写在 :class:`app.db.models.auth.LoginAttempt`
        # 的 ``__table_args__`` 注释里）。
        # ⚠️ **而「最新 50 行」那一问不走本索引**：``GET /api/audit-logs`` 按
        # ``id DESC`` 排（``id`` 是 ``INTEGER PRIMARY KEY`` = rowid 别名，故逆序扫
        # 主键本身就是一次索引扫描，不需要额外建一个 ``(at)``）。⚠️ 而 ``id DESC``
        # 与 ``at DESC`` 在本表上**给出同一个顺序**：写入方只有一个
        # （:func:`app.api.audit.record`）、时钟只有一个（:func:`app.auth.sessions.now`），
        # 且本表**没有任何 UPDATE**，故 rowid 的递增序就是时刻的递增序。
        Index("ix_audit_log_subject_kind_at", "subject_kind", "at"),
    )
