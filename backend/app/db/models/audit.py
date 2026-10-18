"""审计留痕的**两张**表：``audit_log``（Plan 06 Task 5，**写**审计）与
``read_audit_log``（**Plan 08 Task 1**，**敏感读**审计）。

两者各答甲方运维的一个问题：``audit_log`` 答「**谁在什么时候对什么做了什么**」，
``read_audit_log`` 答「**谁在什么时候翻过哪个学生的档案**」。

--------------------------------------------------------------------------
⚠️⚠️ 为什么读审计是**第二张表**、不是 ``audit_log`` 上的一个 ``method='GET'``
--------------------------------------------------------------------------

计划 §1 裁定新开一张表（``read_audit_log``），实现者复核后**同意**，三条理由各自
都能单独成立：

1. **量级差一个数量级**。``audit_log`` 只记三个写方法（实测演示库上跑完一整轮
   试用是 47 行），而本仓 65 个 GET 里有 **47** 个被归为敏感读（判据的唯一所有者
   是 :data:`app.api.read_audit.READ_ROUTES`），一屏学生详情就打出 5–8 个。
   混在一张表里，管理台那一页会被读行淹掉——而它今天**只有** ``id DESC`` 一个序，
   没有「只看写」的过滤（``method`` 那一格能过滤，但缺省视图仍然是混的）。
2. ``audit_log`` 的**九列形状已被三处钉住**：``tests/api/test_audit_api.py`` 的
   :data:`EXPECTED_COLUMNS` 字面量、``app/api/schemas/audit.py`` 的
   ``AuditLogRead``（九格）、与前端 ``views/admin/AuditLogList.vue`` 的九列
   （外加 ``types.ts`` 的 ``AuditLogItem`` 与 ``smoke.mjs`` 第 14 步「列头恰好 9 个」
   那一拍）。而读审计要的那一格 ``student_id``（「**哪个学生的**档案」）在写审计里
   **没有意义**（写操作的对象是行 id，不是人），塞进同一张表就是给九列加第十列、
   四处一起改，且那一列对全部写行恒为 ``NULL``。
3. **留存策略不同**（计划 §1 第 3 条，Task 2 的清理 CLI 会兑现）：写审计
   「不少于 1 年」，读审计 90 天。同一张表上没法给两类行两个保留窗口。

⚠️ 而两张表**共用**三格口径，故它们仍然是一个族、不是两套东西：
``at`` 一律取 :func:`app.auth.sessions.now`（naive 本地时刻）、``subject_kind`` /
``subject_id`` / ``staff_no`` 三格语义逐字相同（列宽也相同：16 / ``Integer`` / 32）、
且**两张表都没有能装请求体的列**（隐私纪律的结构形式，见下面第三节）。

--------------------------------------------------------------------------
⚠️⚠️ 它与 :class:`app.db.models.auth.LoginAttempt` 是两张表，不是一张
--------------------------------------------------------------------------

``login_attempt`` 的模块 docstring 第三节逐字写着「它是**限流键的存储**，不是审计日志」，
并把审计留痕指到了本表（当时写的是「Plan 06 Task 5 的 ``audit_log``（本波不实现）」）。
两者看着像同一件（都叫「记一行请求」），而要的东西相反：审计要**永久留痕、不可改写**，
限流要**能被清零**（一次成功登录就把这个标识的失败计数抹掉）。塞进一张表的话，「清零」
要么是一次 ``DELETE``（审计留痕当场没了）、要么是一次 ``UPDATE``（于是「发生过什么」
变成一个可以被改写的数）。故本表**只管留痕**：它没有任何一处**写入方**会 ``UPDATE``
或 ``DELETE`` 它的行（``GET /api/audit-logs`` 是只读的）。⚠️ 而**留存清理**那一档
自 Plan 08 Task 2 起确实会删它的行（``scripts/retention.py``，口径正文在 spec §13.24）
——它与「留痕不可改写」**不冲突**：清理删的是**整行**、按一个公开的时间判据、
且**先预告后删**（实删与预告不符就整批回滚），而「不可改写」说的是
「一行写下来之后不会被改成别的内容」。⚠️ 它有一个**下界**：spec §13.9.1 逐字
「写审计**不少于 1 年**」，故那个窗口调不到一年以下（低于下界是退出码 2 + 一句人话）。

⚠️ **代价（如实记，硬规矩 #39）**：本表在**没注册**清理任务的机器上仍然单调增长
（与 ``user_session`` / ``login_attempt`` 同一条：那个 CLI **不会自己跑**，
Windows 上没有 cron，注册命令由 ``backend/scripts/register_retention_task.ps1`` 打印）。
故 :attr:`AuditLog.__table_args__`
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


#: ``read_audit_log.subject_kind`` 的取值域。**只有两档**（``student`` / ``teacher``），
#: ⚠️ **``anonymous`` 刻意不在里面**——这是 Plan 08 Task 1 的一条**结构性保证**，
#: 与「``audit_log`` 没有能装请求体的列」同一个形状：
#:
#: * :func:`app.api.read_audit.is_sensitive_read` 的判据是「**敏感路径 + 有名字的主体**」，
#:   故匿名读**根本到不了** :func:`app.api.read_audit.record_read`（47 个敏感读今天
#:   **全部**要身份，匿名一律 401）；
#: * 而本常量再在 **DB 层**设一道 ``ck_read_audit_log_subject_kind``：下一个人若把判据
#:   放宽到「匿名也记」，他会先撞上一条 ``IntegrityError``（那一列的 CHECK 拒收
#:   ``'anonymous'``），而不是静默地往表里灌一批无主的行——那些行答不出「**谁**翻过
#:   谁的档案」，而那张表存在的**全部理由**就是答这一句。
#:   ⚠️ 这一道闸**必须**是 ``subject_kind`` 上的 CHECK 而**不能**是
#:   「``subject_id IS NOT NULL``」：后者对**教职走请求头**那一档也成立
#:   （那一格合法地为 ``NULL``，逐字理由见 :attr:`ReadAuditLog.subject_id` 的注释），
#:   于是它会把一档正常形状一起挡掉。
#:
#: ⚠️ 它直接就是 :attr:`app.db.models.auth.UserSession.KINDS` 那**一个对象**的拷贝
#: （``set(...)`` 造一个新集合、不改原集合），故「加第三类身份（例如家长）」时改
#: ``UserSession.KINDS`` 一处，本表自动跟上——与 :attr:`AuditLog.SUBJECT_KINDS`
#: 同一条口径，差别只在**不加** ``anonymous`` 那一格。
READ_SUBJECT_KINDS: set[str] = set(UserSession.KINDS)


class ReadAuditLog(Base):
    """一次**敏感读**的一行。9 列（Plan 08 Task 1）。

    ------------------------------------------------------------------
    ⚠️ 它与 :class:`AuditLog` 那 9 列的异同（一格一格对）
    ------------------------------------------------------------------

    ==================  ==============================  ==============================
    列                   ``audit_log``（写）              ``read_audit_log``（敏感读）
    ==================  ==============================  ==============================
    ``id`` / ``at``      逐字相同                         逐字相同（同一个时钟所有者）
    ``subject_kind``     三档（含 ``anonymous``）         **两档**（``anonymous`` 结构性排除）
    ``subject_id``       **可空**（匿名档为 ``NULL``）    **可空**（⚠️ 同档，但 ``NULL`` 的
                                                          成因不同：这里**只有**教职走请求头
                                                          那一档，逐字见下面那一列的注释）
    ``staff_no``         逐字相同（只教职填、宽 32）      逐字相同
    ``method``           ``POST`` / ``PATCH`` / ``DELETE`` ⚠️ **没有这一列**：本表只装 GET，
                                                          于是「哪些方法被记」不再需要
                                                          第二个住址（写侧是
                                                          :data:`app.api.audit.AUDITED_METHODS`，
                                                          读侧是
                                                          :data:`app.api.read_audit.READ_ROUTES`，
                                                          两者各管一张表、互不复述）
    ``path``             请求路径的**原文**               ⚠️ ``route``：路由的**模板**
                                                          （``/api/students/{student_id}``）。
                                                          理由见下面那一段
    ——                   ——                             ⚠️ ``student_id``：**读的是哪个学生**。
                                                          写审计没有这一格（写的对象是行 id），
                                                          而它正是本表存在的理由
    ``status``           逐字相同（失败也记）             逐字相同（403 也记，见下面）
    ``target``           逐字相同（恰好一个路径参数）     逐字相同
    ==================  ==============================  ==============================

    ------------------------------------------------------------------
    ⚠️⚠️ ``route`` 存**模板**、不存原文（与 ``audit_log.path`` 刻意不同档）
    ------------------------------------------------------------------

    写审计要答的是「对**哪一个**做了什么」，故 ``path`` 存原文
    （``/api/students/12``），而「哪一个」由 ``target`` 兜住。
    读审计要答的是「翻了**什么档案**」，而「哪个学生」有它自己那一列
    （:attr:`student_id`），故路径那一格只需要**模板**：

    1. **可查**：模板是一个**封闭词表**（今天 47 个值），故「谁翻过周训练单」是一次
       ``WHERE route = '/api/students/{student_id}/weekly-sheet'`` 的等值查询；
       存原文的话它变成一次 ``LIKE`` 前缀匹配，而 ``audit_log`` 的
       ``AuditLogFilter`` 恰恰**刻意不提供** ``path`` 过滤（理由逐字写在
       :class:`app.api.schemas.audit.AuditLogFilter` 的 docstring 里：前缀匹配要决定
       「``/api/students`` 匹不匹配 ``/api/students/12``」，那是一个语义决定）。
       本表用模板绕过了那个决定。
    2. **有界**：模板是**服务端**产物（``scope["route"].path``），不是客户端可控的串，
       故它不需要 :func:`app.db.width.truncate` 那一道设防——一条 400 字符的 URL
       在这里落不成一行（它 404，而 404 没有 ``route``）。⚠️ 而列宽仍然声明
       ``String(256)``（与 ``audit_log.path`` 同宽），:func:`app.api.read_audit.record_read`
       也仍然过一遍 :func:`app.db.width.truncate`：**深度防御**，理由与
       ``audit_log.staff_no`` 那一格相同（「不可达是一个环境变量的距离」）。
    3. ⚠️ **代价（如实记，硬规矩 #39）**：模板把「读的是**哪一行**」抹掉了，
       那一格由 :attr:`target` 兜（与写审计同一个 :func:`app.api.audit.target_of` 形状：
       恰好一个路径参数时取原文，否则 ``NULL``）。

    ------------------------------------------------------------------
    ⚠️⚠️ ``status`` 那一格：**403 也记**（Plan 08 Task 1 的裁定）
    ------------------------------------------------------------------

    判据是「敏感路径 **+ 有名字的主体**」，**不看响应码**。于是：

    * ``200`` —— 真的读到了；
    * ``403`` —— 一个**已登录**的人试了一次他范围外的读（教师翻别的班的学生）。
      ⚠️ 这一档**要记**：它是「有人在探边界」的唯一可见性，而 :mod:`app.api.deps`
      的那几道闸门**故意不回显**「你差在哪」（回显就是一个枚举信号），
      故没有本表的话一次越权探测在系统里**没有任何痕迹**——与
      :data:`app.api.audit.ANONYMOUS_SUBJECT_KIND` 那一段的理由同族；
    * ``401``（匿名）—— **不记**，而它不是被 ``status`` 挡掉的，是被**判据的主体那一半**
      挡掉的（匿名没有名字）。⚠️ 两档在今天的 47 个敏感读上给出同一个结果
      （它们全部要身份 ⇒ 匿名一律 401），故它们是**互为冗余**的两道闸，
      而冗余是有意的：判据放宽（有人把「匿名也记」写进去）时 DB 的 CHECK 会响。

    ⚠️ 于是「一次读被记下来」这件事**不等于**「数据被披露了」，读的人要看 ``status``。
    本表的 :class:`app.api.schemas.audit.ReadAuditLogRead` 因此**必须**带 ``status`` 那一格。
    """

    __tablename__ = "read_audit_log"

    #: ``subject_kind`` 的取值域（两档；逐字理由见 :data:`READ_SUBJECT_KINDS`）。
    SUBJECT_KINDS: set[str] = READ_SUBJECT_KINDS

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: 这一刻（naive 本地时刻）。⚠️ 与 :attr:`AuditLog.at` **同一个所有者**
    #: （:func:`app.auth.sessions.now`）：运维要把两张表按时间对齐着看
    #: （「他先翻了档案、然后改了它」），差 8 小时的对齐是一次假调查。
    at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: ``student`` / ``teacher``。⚠️ **不含 ``anonymous``**（:data:`READ_SUBJECT_KINDS`）。
    #: 列宽 16 与 ``audit_log.subject_kind`` / ``user_session.kind`` / ``login_attempt.kind``
    #: 逐字相同（四张表同一族语义）。
    subject_kind: Mapped[str] = mapped_column(String(16))
    #: ``student.id`` 或 ``teacher.id``；**可空**（⚠️ 与 :attr:`AuditLog.subject_id`
    #: **同档**，逐字理由见下面那一段）。
    #: ⚠️ 刻意不是外键，理由与 :attr:`AuditLog.subject_id` 逐字相同
    #: （多态外键在 SQL 里不存在；且留痕必须在主体消失之后仍然可读）。
    #:
    #: ⚠️⚠️ **它什么时候是 ``NULL``**（本 Task 实测出来的那一格，此前实现者以为恒有值）：
    #: **教职走请求头通道**（``X-Teacher-Staff-No``，即 ``PE_ALLOW_HEADER_IDENTITY=1``
    #: 的开发档与全部测试）时。:func:`app.api.deps.current_teacher` 的那一支
    #: **刻意不查** ``teacher.id``，它的注释逐字写着「请求头给的是工号，而 ``teacher.id``
    #: 要再查一次库才拿得到——那一次查询对审计没有任何用处（``staff_no`` 已经能唯一定位
    #: 那个人），故不查」。⚠️ **本表沿用那一条裁定、不推翻它**，三条理由：
    #: ① 推翻它要给**每一个**教职请求头请求多一次点查（1600+ 条测试全走那一档）；
    #: ② 「谁翻的」这一格**并没有因此丢**：``staff_no`` 唯一确定一个教职，
    #:    而 ``subject_kind`` 告诉你去 ``teacher`` 还是 ``student`` 表 JOIN；
    #: ③ 两张审计表在这一格上**同形**，故运维把它们对齐着看时不会遇到
    #:    「同一一个人在一张表里有 id、在另一张里没有」。
    #: ⚠️ 生产档（cookie 通道）下这一格**恒有值**：
    #: :func:`app.api.deps._resolve_cookie_identity` 从会话行上直接拿 ``subject_id``。
    subject_id: Mapped[int | None] = mapped_column(Integer)
    #: 工号（``teacher.staff_no``）。**只教职那一档填**，学生为 ``NULL``。
    #: ⚠️ 逐字同 :attr:`AuditLog.staff_no`（含「教师侧的闸门以工号为主语」那一段理由），
    #: 列宽 32 与 ``teacher.staff_no`` 相同。
    staff_no: Mapped[str | None] = mapped_column(String(32))
    #: 路由**模板**（``/api/students/{student_id}``），不是请求路径原文。
    #: ⚠️ 逐字理由见上面那一段。⚠️ 列宽 256 与 ``audit_log.path`` 同宽；
    #: 今天最长的模板是 ``/api/students/{student_id}/training-logs/completion-rate``
    #: （57 个字符）。
    route: Mapped[str] = mapped_column(String(256))
    #: **读的是哪个学生**（``student.id``）；路径里没有 ``student_id`` 那一段时为 ``NULL``。
    #: ⚠️ 这一格是本表存在的理由：甲方要的那一句是「谁翻过**谁的**档案」。
    #: ⚠️ 来源**只有路径参数**（:func:`app.api.read_audit.student_id_of`），
    #: 与 :func:`app.api.audit.target_of` 同一条裁定：**不解析响应体**（要缓冲整个响应）、
    #: **不读查询串**（查询串是客户端可控的自由文本，而本表的列清单里刻意没有能装它的
    #: 那一列——与 ``audit_log.path`` 「不含查询串」同一条隐私纪律）。
    #: ⚠️ **刻意不是外键**：留痕必须在被读的那个学生从名册上消失之后仍然可读
    #: （否则「删掉一个学生」这个动作会把他被翻过的历史一起抹掉），
    #: 与 :attr:`AuditLog.subject_id` 同一条理由。
    #: ⚠️ **两档 ``NULL`` 如实记**（硬规矩 #39）：① 读的是**名册/班级聚合**
    #: （``/api/students``、``/api/dashboard/class/{id}``、``/api/weekly-class-reports``），
    #: 一次请求里没有「某一个学生」；② 读的是**自己**
    #: （``/api/mini-tests/normalized/me``），那一格由 :attr:`subject_id` 回答。
    #: 两档都答得出「谁翻了什么」，只是「哪个学生」那一格是空的。
    student_id: Mapped[int | None] = mapped_column(Integer)
    #: 响应码。⚠️ **403 也记**（逐字理由见上面那一段）。
    status: Mapped[int] = mapped_column(Integer)
    #: 被读的那一行的 id（**字符串**原文），取不到就 ``NULL``。
    #: ⚠️ 来源与「为什么是字符串」逐字见 :func:`app.api.audit.target_of`
    #: （本表**复用同一个函数**，不写第二份判据）。列宽 64 与 ``audit_log.target`` 同宽。
    target: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        _in_domain("subject_kind", SUBJECT_KINDS, "ck_read_audit_log_subject_kind"),
        # ⚠️ **列序是 ``(student_id, at)``**，与 ``audit_log`` 的 ``(subject_kind, at)``
        # **刻意不同**：两张表最常问的那一句不同。写审计问「**某一类人**在某一段时间里
        # 做了什么」（故等值列是 ``subject_kind``），读审计问「**这一个学生**的档案
        # 在某一段时间里被谁翻过」（故等值列是 ``student_id``）。
        # ⚠️ 同样是「等值列在前、范围列在后」，与 ``ix_login_attempt_kind_login_at`` /
        # ``ix_audit_log_subject_kind_at`` 同一条口径。
        # ⚠️ 而管理台那一页的「最新 50 行」**不走本索引**：它按 ``id DESC`` 排，
        # 而 ``id`` 是 ``INTEGER PRIMARY KEY`` = rowid 别名，逆序扫主键本身就是一次
        # 索引扫描（逐字理由见 :class:`AuditLog` 的 ``__table_args__`` 注释）。
        Index("ix_read_audit_log_student_id_at", "student_id", "at"),
    )
