r"""**留存清理**：四张表的过期行（Plan 08 Task 2）。

``login_attempt`` / ``user_session`` / ``audit_log`` / ``read_audit_log`` —— spec §13.15
交付须知第 **6** 条与 §15 的 **B2 / B3** 逐字登记着「三张表单调增长、没有清理任务」
（第四张 ``read_audit_log`` 是 Plan 08 Task 1 刚加的，它一出生就带着同一条待清扫，
见 §13.9.1 末段「处置是 Task 2 的 90 天留存窗口」）。本模块是那一条的**唯一**收口点。

--------------------------------------------------------------------------
⚠️⚠️ 它是**破坏性**的：失效方向因此是本模块的全部设计
--------------------------------------------------------------------------

删掉的是**含个人健康数据的审计痕迹**（``read_audit_log`` 逐行记着「谁翻过哪个学生的
档案」，``audit_log`` 逐行记着「谁改了什么」），而删除**不可撤销**。故四条纪律，
每一条都有一个守卫钉着（``tests/test_retention.py``）：

1. **先预告、再删、删完复核**。四张表各自的 ``COUNT(*)`` 在删之前**逐表打印**，
   删完再打印 ``rowcount``，两者**逐字不符就整批回滚**并响亮失败
   （:func:`clean` 的对账那一段）。⚠️ 不许静默删：「静默」的定义是
   「输出里看不出删了哪张表多少行」，故每一张表都占一行、两个数都在。
2. **``--dry-run`` 一行都不删**。它不是「打印完再删」的一个开关，而是一条**走不到
   ``DELETE`` 语句**的路径（:func:`clean` 里 ``dry_run`` 那一档连写事务都不开），
   并且它自己**复核**一遍「四张表的行数与进来时逐字相同」。
3. **窗口有下界**。``0`` 天意味着「把这张表全部删掉」，那是「误删一切」的形状；
   四张表一律 ≥ :data:`MIN_DAYS` 天，而 ``audit_log`` 另有一道
   :data:`AUDIT_MIN_DAYS` = **365** 天的下界 —— 那不是本模块发明的数，
   是 spec §13.9.1 逐字的「写审计**不少于 1 年**」。
4. **整批一个事务**，且那个事务是 ``BEGIN IMMEDIATE``（:func:`_engine`）：
   写锁在**预告之前**就拿到，故「预告的行数」与「实删的行数」之间不可能插进
   另一个写者（真实的一档是 :func:`app.auth.policy.clear_failures` —— 一次成功登录
   会当场删掉那个标识的 ``login_attempt`` 行）。⚠️ ``--dry-run`` 那一档**不**取写锁
   （只读的探查不该挡住正在跑的甲方服务）。

--------------------------------------------------------------------------
⚠️⚠️ 时间口径：四张表的时间列**全是 naive 本地时刻**（实测取证）
--------------------------------------------------------------------------

清理判据是「某个时间列 < 截止时刻」，而**截止时刻必须与那一列同口径**：错一档
（拿 ``datetime.utcnow()`` 当「现在」）就会把整整 8 小时的行判错方向。

本仓的口径是**唯一**的：:func:`app.auth.sessions.now`（先转到
:data:`app.config.TIMEZONE` = ``Asia/Shanghai``、再摘掉 ``tzinfo``）。⚠️ 本模块
**只调它、不自己取时钟**（``moment`` 可注入，同 :func:`app.pipeline.daily.run_daily`
的 ``now`` 先例），故四张表的判据与写进四张表的值是同一个所有者。

实测（2026-10-17，本 Task 亲跑：在 8041 上起一个自己的实例、真发一次错口令登录 +
一次对口令登录 + 一次敏感读 ``GET /api/students/4``，然后把库里读回来的值与三个时钟
逐个对账；取证逐字见 ``task-2-report.md`` §3）::

    列                              库里的值                     与 datetime.now() 差   与 utcnow() 差
    login_attempt.at                2026-10-17 20:40:36.380451              −0.2 s        +28 799.8 s
    user_session.created_at         2026-10-17 20:40:36.388884              −0.2 s        +28 799.8 s
    user_session.expires_at         2026-10-17 22:40:36.453603            +7 199.9 s      +35 999.9 s
    user_session.last_seen_at       2026-10-17 20:40:36.453603              −0.1 s        +28 799.9 s
    audit_log.at                    2026-10-17 20:40:36.538541              −0.0 s        +28 800.0 s
    read_audit_log.at               2026-10-17 20:40:36.467011              −0.1 s        +28 799.9 s

⇒ 六个列**全部**是 naive **本地**时刻（与 ``utcnow()`` 恒差 28 800 s = 8 h），
且四张表**同源**（都是 :func:`app.auth.sessions.now`）。``expires_at`` 那 +7 200 s
正是 :data:`app.auth.sessions.SESSION_TTL` = 2 小时 —— 它就是「未过期」的判据来源。

⚠️ 守卫有两条：① 把 :func:`app.auth.sessions.now` monkeypatch 成一个**未来**的时刻，
断言「按真实时钟还不该删的行**被删了**」（换成 ``utcnow()`` 的实现会当场红）；
② 按**源码字面**断言本模块里没有 ``utcnow``、也没有第二处取时钟的调用。

--------------------------------------------------------------------------
⚠️⚠️ 四个缺省窗口：三个照 spec 已写下的数、一个照 spec 已写下的数
--------------------------------------------------------------------------

==================  ==========  ==============================================
表                  缺省窗口      数的住址（⚠️ 本模块**不造**第二个数）
==================  ==========  ==============================================
``user_session``     **7** 天    ``app/db/models/auth.py`` 模块 docstring 逐字
                                ``DELETE FROM user_session WHERE expires_at < now − 7 天``
``login_attempt``   **30** 天    spec §15 **B3** 逐字 ``WHERE <时间列> < now − 30 天``
``audit_log``      **365** 天    spec §13.9.1 逐字「写审计**不少于 1 年**」
                                （365 是满足「不少于」的最小整数）
``read_audit_log``  **90** 天    spec §13.9.1 逐字「处置是 Task 2 的 **90** 天留存窗口」
==================  ==========  ==============================================

⚠️ 派单建议的是「会话 7 · 登录尝试 **90** · 写审计不少于 1 年 · 读审计 90」，
其中**三格与 spec 已写下的数逐字相同**，而「登录尝试 90 天」与 §15 B3 的 30 天不同
⇒ 本模块**照 spec 的 30**（派单自己写的是「有就照它、不要造第二个数字」），
并把这一处顶回记在 ``task-2-report.md`` §7。要 90 天请传
``--login-attempt-days 90``（或设 ``PE_RETENTION_LOGIN_ATTEMPT_DAYS``）。

⚠️ **四个数只有这一个住址**：``.ps1`` 包装、注册计划任务的脚本、README 与 spec
一律**复述而不重定义**（改窗口只改本文件这四个常量）。

--------------------------------------------------------------------------
⚠️⚠️ 它**不**自动备份（派单 §2 第 4 条那个开放问题的裁定）
--------------------------------------------------------------------------

派单把「删之前要不要先自动落一份备份」交给实现者判断。裁定是**不自动备份**，
但**每次真删之前打印一段响亮的告示**并指向 ``backend/scripts/backup.ps1``。三条理由：

1. **今天的备份是明文的**（spec §13.15 第 7 条实测：文件头 ``SQLite format 3\0``、
   不用任何密钥就读得出 60 人姓名与出生日期），而加密是 **Plan 08 Task 3** 的事。
   于是「每清一次就自动备一份」= 每天在磁盘上多留一份**含全校学生健康数据的明文
   整库副本**。
2. **``backup.ps1`` 从不删旧备份**（同一条须知：「也不做保留策略」；``-Keep`` 是
   Task 3 要加的）。于是一个每天跑的计划任务一年会留下 **365 份**明文全库副本 ——
   把一个**有界**的隐私暴露面换成一个**无界**的，而它防的还是「删错了 30 天前的行」。
3. **正确的形状是两个显式步骤**：``backup.ps1`` 然后 ``retention.ps1``。
   ``backend/scripts/register_retention_task.ps1`` 打印的那一对计划任务命令就是这个顺序
   （备份那一条排在清理那一条**前面 30 分钟**），而运维日志里两格都看得见。

⚠️ 代价如实记（硬规矩 #39）：不自动备份意味着「删错了」的后路**取决于运维有没有
先跑备份**。本模块因此把可发现性做在别处 —— 预告/实删逐字对账（不符就整批回滚）、
``--dry-run``、窗口下界、以及**只删过期行**这一条结构性性质
（:class:`TableSpec` 的 ``session`` 那一格锚在 ``expires_at`` 上，故任何窗口都删不到
一个还在有效期里的会话）。

--------------------------------------------------------------------------
本模块刻意不做的事
--------------------------------------------------------------------------

* **不建「清理跑过几次、每次删了多少」的记录表**：那是一张新表 = 迁移 6，
  而本 CLI 的输出与运维日志（计划任务的历史）已经答得出同一问。派单倾向不做，
  实现者复核后同意（顶回 0 处）。
* **不归档成 CSV 再删**（§15 B2 提过 ``audit_log`` 的这一形状）：导出的 CSV 是
  又一份**明文**的个人健康数据副本，与上面「不自动备份」是同一条理由。
  要归档请先 ``backup.ps1``（整库、可用任何 SQLite 客户端打开、可用
  ``scripts/restore.py`` 恢复），再从备份里导。
* **不动 schema**：不加表、不加列、不加索引。⚠️ 四张表上今天**没有**一个
  「只含时间列」的索引（``ix_audit_log_subject_kind_at`` 与
  ``ix_read_audit_log_student_id_at`` 都是复合的、且时间列在**后**），故那四次
  ``COUNT(*)`` 与四次 ``DELETE`` 是**全表扫描**。今天量级下（演示库 3 / 1 / 3 / 1 行、
  甲方试用库 4 / 11 / 20 / 0 行）这是毫秒级；跑一学期之后 ``audit_log`` 会到几万行，
  一次全表扫描仍然是**亚秒**级、且发生在夜里的计划任务里。已登记为 §15 的新条目
  （要加索引就是迁移 6，与本 Task「不动 schema」的约束冲突）。
* **不碰 ``backend/data/**`` 与 ``backend/pe.db``**：库路径的解析与禁区守卫一律
  **复用** ``scripts/backup.py`` 的 :func:`resolve_db_path`（它是「``--db-url`` >
  ``PE_DB_URL`` > ``DEMO_DB_URL``」与那两个禁区的唯一所有者），本模块不写第二份。
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import os
import pathlib
import sys
from typing import Any, Callable

from sqlalchemy import delete, event, func, select
from sqlalchemy.engine import Connection, Engine

from app.auth import sessions
from app.db.models.audit import AuditLog, ReadAuditLog
from app.db.models.auth import LoginAttempt, UserSession
from app.db.session import engine as build_engine

#: ⚠️ ``scripts/`` 不是包（没有 ``__init__.py``），故 ``import backup`` 要靠本文件所在
#:    目录在 ``sys.path`` 上。⚠️ **它是无条件的**，逐字理由与
#:    ``scripts/restore.py`` 那一段相同：``python scripts/retention.py`` 时 Python 会把
#:    脚本所在目录放进 ``sys.path[0]``（于是本段冗余），而
#:    ``tests/test_retention.py`` 用 ``importlib`` 按路径加载本模块时**不会**
#:    （于是本段承重）。
_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from backup import (  # noqa: E402
    BackupError,
    db_path_from_url,
    resolve_db_path,
)

__all__ = [
    "AUDIT_MIN_DAYS",
    "DEFAULT_AUDIT_DAYS",
    "DEFAULT_LOGIN_ATTEMPT_DAYS",
    "DEFAULT_READ_AUDIT_DAYS",
    "DEFAULT_SESSION_DAYS",
    "MIN_DAYS",
    "SPECS",
    "RetentionError",
    "TableResult",
    "TableSpec",
    "clean",
    "main",
    "resolve_days",
]

#: 四张表共用的窗口**下界**（天）。⚠️ ``0`` 被拒：它的语义是「把这张表全部删掉」，
#: 那是「误删一切」的形状（派单 §2 第 7 条 ⑥ 点名的那一格定点变异就是它）。
#: 要清空一张表请显式跑 SQL 并对后果负责，或先从备份恢复 —— 本 CLI 不替你做那个决定。
MIN_DAYS = 1

#: ``audit_log`` 的**额外**下界（天）。⚠️ 它不是本模块发明的数：spec §13.9.1 逐字
#: 「写审计**不少于 1 年**」，而 365 是满足「不少于」的最小整数。故 ``--audit-days 30``
#: 会被拒 —— 一个把写审计窗口调到 30 天的运维，删掉的是 spec 明确要求留着的那一批痕迹。
AUDIT_MIN_DAYS = 365

#: ``user_session`` 的缺省窗口（天）。⚠️ 数的住址是 ``app/db/models/auth.py`` 的模块
#: docstring：``DELETE FROM user_session WHERE expires_at < now − 7 天``
#: （连列名与那个**严格小于**都与本模块的判据逐字相同）。
DEFAULT_SESSION_DAYS = 7

#: ``login_attempt`` 的缺省窗口（天）。⚠️ 数的住址是 spec §15 **B3**。
#: ⚠️ 它对限流本身**没有任何影响**：判「锁」只看 ``max(window, lock)`` 之内
#: （登录 15 分钟、绑定 60 分钟，spec §13.4.6），故 30 天纯粹是事后线索的留存
#: （``ip`` 那一列只有本表有）。
DEFAULT_LOGIN_ATTEMPT_DAYS = 30

#: ``audit_log`` 的缺省窗口（天）= spec §13.9.1 的「不少于 1 年」。
DEFAULT_AUDIT_DAYS = 365

#: ``read_audit_log`` 的缺省窗口（天）= spec §13.9.1 逐字点名的「Task 2 的 90 天」。
#: ⚠️ 它**刻意短于**写审计：读审计的量级比写审计高一个数量级
#: （``GET`` 里被归为**敏感**的那些都记，一次翻学生详情就是 5–8 行；⚠️ 本处
#: **刻意不写件数** —— 那张清单的唯一所有者是 ``app/api/read_audit.py`` 的
#: ``READ_ROUTES``，而它会随端点增删再漂，硬规矩 #111；⚠️ 改前本行逐字写着
#: 「64 个 GET 里 46 个记」，Plan 08 Task 4 之后是 65 / 47，终审 **R7-14**
#: 点名了它，因为本文件是**随可分发包发出去的源码**、甲方读得到），
#: 而那一句「谁翻过谁的档案」
#: 的取证价值随时间衰减得比「谁改了什么」快 —— 这正是 §13.9.1「不复用 ``audit_log``」
#: 的第 3 条理由（两张表的留存策略不同）。
DEFAULT_READ_AUDIT_DAYS = 90


class RetentionError(RuntimeError):
    """一次清理**该拒绝**的动作，或一次「实删与预告不符」的对账失败。

    ⚠️ 它是一个具名异常而不是裸 :class:`RuntimeError`，与 ``scripts/backup.py`` 的
    ``BackupError`` 同一条口径：``main()`` 只捕这两个，于是「预期内的拒绝」打印一句
    人话 + 退出码 **2**，而「预期外的 bug」照常抛栈（失效方向是响亮的）。
    ⚠️ 抛出点在事务**内部**，故它同时是「整批回滚」的触发器（:func:`clean`）。
    """


@dataclasses.dataclass(frozen=True)
class TableSpec:
    """一张表的清理规格。**frozen**：它会被传进计数与删除两步，
    可变化会让「预告用的判据」与「实删用的判据」在类型上可能不是同一个。

    ⚠️⚠️ **判据的单一所有者就是这里**：:attr:`column` 是**模型的列对象**
    （不是列名字符串），而「预告的 ``COUNT``」与「实删的 ``DELETE``」用的是
    **同一个** ``column < cutoff`` 表达式（:func:`_predicate`）。于是
    「数出来要删的那些行」与「真删掉的那些行」在结构上是同一个集合 ——
    而不是两处各写一遍、靠人眼保证一致。

    ⚠️ ``session`` 那一格锚在 ``expires_at`` 上而**不是** ``created_at`` /
    ``last_seen_at``，于是「删掉一个未过期的会话、把人踢下线」这一档对**任何**窗口
    都不可达（一个活着的会话 ``expires_at`` 恒在未来，故恒不小于任何
    ``now − N 天``，N ≥ 0）。⚠️ 连带一格裁定：**已吊销但还没到期**的行
    （``revoked_at`` 非空、``expires_at`` 仍在未来）**不删** ——
    :func:`app.auth.sessions.revoke` 的整个立意就是「登出 = 写一列、**不删行**，
    好让『被偷的 cookie 在登出后失效』可追溯」，而清理任务立刻把它删掉等于抹掉
    最新的那一条登出痕迹。它有界（最多再活一个 :data:`app.auth.sessions.SESSION_TTL`
    = 2 小时就落到判据里），故这一档不需要第二个判据。
    """

    #: CLI 旗标与环境变量共用的名字主干（``--<key>-days`` / ``PE_RETENTION_<KEY>_DAYS``）。
    key: str
    #: 时间列（**模型属性**，不是字符串）。
    column: Any
    #: 缺省窗口（天）。⚠️ 四个数的住址逐字见模块 docstring 那张表。
    default_days: int
    #: 环境变量名。
    env_var: str
    #: 下界（天）；``audit`` 那一格是 :data:`AUDIT_MIN_DAYS`，其余是 :data:`MIN_DAYS`。
    min_days: int
    #: 判据的一句人话（打印在控制台上，让运维当场看清「删的是哪一批」）。
    criterion: str

    @property
    def table(self) -> str:
        """表名 —— 取自模型的 ``__tablename__``（不写第二份字面量）。"""
        return str(self.model.__tablename__)

    @property
    def model(self) -> Any:
        """这一格由 :data:`SPECS` 的构造点填（见那里为什么用 ``column.class_``）。"""
        return self.column.class_

    @property
    def column_name(self) -> str:
        """时间列的名字 —— 取自列对象本身（不写第二份字面量）。"""
        return str(self.column.key)


#: 四张表的清单。⚠️ **它是「清哪四张表、按哪一列、缺省留几天」的唯一所有者**：
#: 控制台输出、守卫、``.ps1`` 包装、注册脚本与文档一律从它读或复述它。
#: ⚠️ 顺序就是打印顺序，也是删除顺序 —— ⚠️ 而**顺序不承重**：四张表之间
#: 一个外键都没有（``user_session`` / ``login_attempt`` 的 ``subject_id`` 刻意不是外键，
#: 两张审计表同理），故 ``PRAGMA foreign_keys=ON`` 在这里没有话说。
SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        key="session",
        column=UserSession.expires_at,
        default_days=DEFAULT_SESSION_DAYS,
        env_var="PE_RETENTION_SESSION_DAYS",
        min_days=MIN_DAYS,
        criterion="**已过期**的会话（expires_at < 截止时刻）；未过期的一律不动",
    ),
    TableSpec(
        key="login_attempt",
        column=LoginAttempt.at,
        default_days=DEFAULT_LOGIN_ATTEMPT_DAYS,
        env_var="PE_RETENTION_LOGIN_ATTEMPT_DAYS",
        min_days=MIN_DAYS,
        criterion="这一次尝试发生在截止时刻之前（⚠️ 对限流无影响：判锁只看 15/60 分钟之内）",
    ),
    TableSpec(
        key="audit",
        column=AuditLog.at,
        default_days=DEFAULT_AUDIT_DAYS,
        env_var="PE_RETENTION_AUDIT_DAYS",
        min_days=AUDIT_MIN_DAYS,
        criterion="这一条**写**审计发生在截止时刻之前（spec §13.9.1：写审计「不少于 1 年」）",
    ),
    TableSpec(
        key="read_audit",
        column=ReadAuditLog.at,
        default_days=DEFAULT_READ_AUDIT_DAYS,
        env_var="PE_RETENTION_READ_AUDIT_DAYS",
        min_days=MIN_DAYS,
        criterion="这一条**敏感读**审计发生在截止时刻之前（⚠️ 窗口刻意短于写审计，spec §13.9.1）",
    ),
)


@dataclasses.dataclass(frozen=True)
class TableResult:
    """一张表这一次清理的**六个数**。⚠️ 它同时是控制台那几行的数据源与守卫的断言对象
    （守卫不必去解析 stdout，于是「打印的」与「真发生的」不可能只对一个）。"""

    spec: TableSpec
    days: int
    cutoff: dt.datetime
    #: 清理前这张表的**总**行数（让「删掉的占多少」看得见）。
    before: int
    #: 预告将删的行数（``COUNT(*) WHERE 判据``，删之前取的）。
    predicted: int
    #: 实删的行数（``DELETE`` 的 ``rowcount``）。⚠️ ``--dry-run`` 下恒 **0**。
    deleted: int
    #: 复核：删完之后**仍满足判据**的行数（恒 **0**；不为 0 就整批回滚）。
    remaining: int


def _predicate(spec: TableSpec, cutoff: dt.datetime):
    """``<时间列> < cutoff``。⚠️ **严格小于**：恰好等于截止时刻的那一行**不删**。

    ⚠️ 这一格是**裁定**（派单 §2 第 7 条 ④），两条理由：

    * spec 两处已写下的算式都是 ``<``（``app/db/models/auth.py`` 的
      ``expires_at < now − 7 天``、§15 B3 的 ``<时间列> < now − 30 天``）；
    * 它是**保守**的那一侧：边界那一行留下来，最坏是多留一行、下一次跑就删掉；
      反过来（``<=``）最坏是删掉一行本该留满窗口的痕迹，而删除不可撤销。

    ⚠️ 与 :func:`app.auth.sessions.resolve` 判过期用的 ``<=`` **刻意不同档**：
    那一句答的是「这个会话**现在**还能不能用」（一个 TTL 为 0 的会话不得在签发的
    同一瞬间可用），本句答的是「这一行是不是**已经老过**保留窗口」。
    两者都不是笔误，故两处都写清楚了。
    """
    return spec.column < cutoff


def _count_all(conn: Connection, spec: TableSpec) -> int:
    """一张表的**总**行数。"""
    return int(conn.scalar(select(func.count()).select_from(spec.column.class_)) or 0)


def _count_matching(conn: Connection, spec: TableSpec, cutoff: dt.datetime) -> int:
    """一张表上**满足判据**的行数（= 预告将删的那个数）。"""
    return int(
        conn.scalar(
            select(func.count())
            .select_from(spec.column.class_)
            .where(_predicate(spec, cutoff))
        )
        or 0
    )


def _days_from_env(env_var: str, default: int) -> int:
    """读一个整数环境变量；空 = 用缺省，坏值 = :class:`RetentionError`（响亮）。

    ⚠️ 口径逐字同 ``app/auth/policy.py`` 的 ``_int_from_env``（空字符串按「没设」处理：
    ``$env:PE_RETENTION_AUDIT_DAYS = ""`` 在 PowerShell 里是「设了一个空值」而不是
    「删掉这个变量」）。⚠️ **而不复用它**：那一个是 ``app.auth`` 层的私有助手，
    而本模块要的是**带下界**的一档（``0`` 必须拒），把它加进 ``policy`` 会给限流那一层
    塞一个它用不上的参数。故本函数只借它的口径、不借它的住址。
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RetentionError(
            f"{env_var}（保留窗口的天数）必须是一个整数，收到 {raw!r}"
        ) from None


def resolve_days(spec: TableSpec, explicit: int | None = None) -> int:
    """一张表的窗口天数：**CLI 实参 > 环境变量 > 缺省值**，并校验下界。

    ⚠️ 缺省值的**单一所有者**是 :data:`SPECS` 里那一格 ``default_days``
    （它的值又来自模块顶层那四个常量）。``.ps1`` 包装、注册脚本与文档
    一律**不写第二份数字**。
    """
    value = _days_from_env(spec.env_var, spec.default_days) if explicit is None else explicit
    if value < spec.min_days:
        raise RetentionError(
            f"{spec.table} 的保留窗口给的是 {value} 天，而下界是 {spec.min_days} 天"
            f"（--{spec.key.replace('_', '-')}-days / {spec.env_var}）。"
            + (
                "⚠️ 0 天的语义是「把这张表**全部**删掉」——包括今天刚写的行，"
                "那是「误删一切」的形状，本 CLI 拒绝它。要清空一张表请显式跑 SQL "
                "并对后果负责，或先从备份恢复（scripts/backup.ps1）。"
                if value <= 0
                else ""
            )
            + (
                "⚠️ 而这一格的下界不是本模块发明的：spec §13.9.1 逐字要求"
                "「写审计**不少于 1 年**」，删掉它等于删掉 spec 要求留着的痕迹。"
                if spec.min_days == AUDIT_MIN_DAYS
                else ""
            )
        )
    return value


def _engine(db_url: str, *, immediate: bool) -> Engine:
    """按 URL 造引擎；``immediate`` 时把事务改成 ``BEGIN IMMEDIATE``。

    ⚠️ 那两行 ``event.listens_for`` 是 SQLAlchemy 文档里「pysqlite 上的可串行化
    隔离」那一条**配方**（先把 DBAPI 连接的 ``isolation_level`` 设成 ``None``
    以关掉 pysqlite 自己那个隐式 ``BEGIN``，再在 ``begin`` 事件里发我们自己的
    ``BEGIN IMMEDIATE``）。⚠️ **它是承重的**，不是洁癖：

    * 没有它，``COUNT(*)``（预告）与 ``DELETE``（实删）之间另一个连接可以提交一次写。
      真实存在的那一档是 :func:`app.auth.policy.clear_failures` —— 一次成功登录会
      当场删掉那个标识的 ``login_attempt`` 行，于是实删 < 预告 ⇒ 对账失败 ⇒
      整批回滚 + 一句「行数不符」的报错，而**真因只是有人在那一毫秒里登录成功了**。
      那是「假红」，而假红会让运维不再相信这个报错（于是真红也被忽略）。
    * 有了它，写锁在**预告之前**就拿到，整个「预告 → 删 → 复核」是一个不可分割的
      临界区 ⇒ 对账**恒**相符，那一格报错因此只可能是真问题。

    ⚠️ 代价（如实记，硬规矩 #39）：写锁被握住的时间是这四次 ``COUNT`` + 四次
    ``DELETE`` 的墙钟（今天量级下是毫秒级；``audit_log`` 长到几万行时是一次全表
    扫描，仍然亚秒）。同期若有一个写请求进来，它最多等到 ``sqlite3`` 的
    ``timeout``（本仓缺省 5 s）—— 而清理是**夜里**的计划任务，撞上的概率很低。
    ⚠️ ``--dry-run`` 那一档**不**装这两个钩子：一次只读的探查不该去挡正在给甲方
    服务的那个进程的写。
    """
    eng = build_engine(db_url)
    if immediate:

        @event.listens_for(eng, "connect")
        def _no_implicit_begin(dbapi_connection, _record):
            dbapi_connection.isolation_level = None

        @event.listens_for(eng, "begin")
        def _begin_immediate(conn):
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    return eng


def clean(
    db_url: str,
    *,
    days: dict[str, int] | None = None,
    dry_run: bool = False,
    moment: dt.datetime | None = None,
    emit: Callable[[str], None] = print,
) -> tuple[TableResult, ...]:
    """跑一次清理；返回四张表各自的 :class:`TableResult`。

    ``days`` 是 ``{key: 天数}``（缺省 ``None`` = 四张表都走「环境变量 > 缺省值」）。
    ``moment`` 可注入（同 :func:`app.pipeline.daily.run_daily` 的 ``now`` 先例）：
    缺省取 :func:`app.auth.sessions.now`，⚠️ 而**只**取它 —— 本模块没有第二处时钟
    （理由与守卫逐字见模块 docstring「时间口径」那一节）。

    ⚠️⚠️ ``dry_run=True`` 时**一条 ``DELETE`` 都不会被构造**：那一档走的是
    ``eng.connect()``（只读、不取写锁），函数体里唯一那处 ``delete(...)`` 在
    ``if dry_run: return ...`` **之后**。派单 §2 第 7 条 ⑥ 的定点变异
    （把那个短路去掉）因此会当场红在
    ``test_a_dry_run_deletes_not_a_single_row`` 上。
    """
    now = sessions.now() if moment is None else moment
    if now.tzinfo is not None:
        # ⚠️ 结构性不可能（sessions.now() 的最后一格就是 replace(tzinfo=None)），
        #    而一个 aware 的注入值会让下面每一次「列 < cutoff」的比较在 SQLite 上
        #    静默地按字符串比出错误答案。故这里响亮拒绝，不猜。
        raise RetentionError(
            f"moment 必须是 naive 本地时刻（收到 tzinfo={now.tzinfo!r}）："
            f"四张表的时间列存的都是 naive 本地时刻，口径的唯一所有者是 "
            f"app.auth.sessions.now（TIMEZONE={sessions.TIMEZONE!r}）"
        )
    windows = {
        spec.key: resolve_days(spec, None if days is None else days.get(spec.key))
        for spec in SPECS
    }
    cutoffs = {
        spec.key: now - dt.timedelta(days=windows[spec.key]) for spec in SPECS
    }

    path = db_path_from_url(db_url)
    emit("== 厦大体育数智系统 · 留存清理 ==")
    emit("   库     %s" % path)
    emit(
        "   时刻   %s（naive **本地**时刻 %s；所有者 app.auth.sessions.now）"
        % (now.strftime("%Y-%m-%d %H:%M:%S"), sessions.TIMEZONE)
    )
    emit(
        "   模式   %s"
        % ("**DRY-RUN**（一行都不删、也不取写锁）" if dry_run else "真删（不可撤销）")
    )
    emit("")
    emit("   %-16s %-12s %7s   %-19s %8s %10s" % (
        "表", "时间列", "窗口", "截止时刻（严格早于它才删）", "现存", "预告删除"))

    eng = _engine(db_url, immediate=not dry_run)
    try:
        with (eng.connect() if dry_run else eng.begin()) as conn:
            before = {spec.key: _count_all(conn, spec) for spec in SPECS}
            predicted = {
                spec.key: _count_matching(conn, spec, cutoffs[spec.key]) for spec in SPECS
            }
            for spec in SPECS:
                emit("   %-16s %-12s %5d 天   %-19s %8d %10d" % (
                    spec.table, spec.column_name, windows[spec.key],
                    cutoffs[spec.key].strftime("%Y-%m-%d %H:%M:%S"),
                    before[spec.key], predicted[spec.key],
                ))
            emit("   %-16s %-12s %7s   %-19s %8d %10d" % (
                "合计", "", "", "",
                sum(before.values()), sum(predicted.values())))
            emit("")
            emit("   判据（逐表，⚠️ 恰好等于截止时刻的那一行**不删**）：")
            for spec in SPECS:
                emit("      · %-16s %s" % (spec.table, spec.criterion))

            if dry_run:
                after = {spec.key: _count_all(conn, spec) for spec in SPECS}
                if after != before:
                    # ⚠️ 结构上不可达（这一档一条写语句都没发），而它是
                    #    「--dry-run 一行都不删」这句话的**自我复核**：
                    #    下一个人若把 DELETE 挪到短路之前，这一格当场红。
                    raise RetentionError(
                        f"--dry-run 之下四张表的行数变了：{before} → {after}"
                    )
                emit("")
                emit(
                    "   DRY-RUN：**一行都没删**（复核：四张表的总行数与进来时逐字相同，"
                    "%d → %d）。要真删就去掉 --dry-run。"
                    % (sum(before.values()), sum(after.values()))
                )
                return tuple(
                    TableResult(
                        spec=spec, days=windows[spec.key], cutoff=cutoffs[spec.key],
                        before=before[spec.key], predicted=predicted[spec.key],
                        deleted=0, remaining=predicted[spec.key],
                    )
                    for spec in SPECS
                )

            emit("")
            emit("   ⚠️⚠️ 下面这一步**不可撤销**，而本 CLI **不会**自动备份（裁定与三条理由")
            emit("      逐字见本模块 docstring「它**不**自动备份」那一节，口径正文在 spec §13.24）：")
            emit("      今天的备份是**明文**整库副本、而 backup.ps1 **缺省**不删旧的（-Keep 要显式给）")
            emit("      ⇒ 自动备份等于每天多留一份含全校学生健康数据的明文副本。要留后路请**先**跑一次：")
            emit("        powershell -ExecutionPolicy Bypass -File backend\\scripts\\backup.ps1")
            emit("")
            emit("   合计：将删 %d 行 → 开始删…" % sum(predicted.values()))

            deleted: dict[str, int] = {}
            for spec in SPECS:
                result = conn.execute(
                    delete(spec.column.class_).where(_predicate(spec, cutoffs[spec.key]))
                )
                deleted[spec.key] = int(result.rowcount or 0)
            remaining = {
                spec.key: _count_matching(conn, spec, cutoffs[spec.key]) for spec in SPECS
            }

            # ⚠️⚠️ 对账：任一张表「实删 != 预告」或「删完还剩满足判据的行」→ 抛。
            #    抛出点在 ``with eng.begin()`` 里面 ⇒ **四张表全部回滚**（一行都没删）。
            for spec in SPECS:
                if deleted[spec.key] != predicted[spec.key]:
                    raise RetentionError(
                        f"{spec.table} 的实删行数（{deleted[spec.key]}）与预告"
                        f"（{predicted[spec.key]}）不符 ⇒ 四张表**全部回滚**，一行都没删。"
                        f"⚠️ 本事务是 BEGIN IMMEDIATE（写锁在预告之前就拿到），故这一格"
                        f"不该发生；它发生了说明判据在两处不一致，请查 _predicate 与 "
                        f"delete() 是不是用了同一个表达式"
                    )
                if remaining[spec.key] != 0:
                    raise RetentionError(
                        f"{spec.table} 删完之后仍有 {remaining[spec.key]} 行满足判据"
                        f"（截止时刻 {cutoffs[spec.key]}）⇒ 四张表**全部回滚**。"
                        f"⚠️ 这一格说明 DELETE 的 WHERE 与 COUNT 的 WHERE 不是同一个"
                    )

            emit("")
            emit("   实删（逐表）：")
            for spec in SPECS:
                emit("      · %-16s 预告 %5d / 实删 %5d / 删完仍满足判据 %d" % (
                    spec.table, predicted[spec.key], deleted[spec.key], remaining[spec.key]))
            emit(
                "   合计：预告 %d == 实删 %d ✓（逐字相符；不符就整批回滚、一行都不删）"
                % (sum(predicted.values()), sum(deleted.values()))
            )
            emit("   复核：四张表上「仍满足判据的行」合计 %d（恒为 0）" % sum(remaining.values()))
            return tuple(
                TableResult(
                    spec=spec, days=windows[spec.key], cutoff=cutoffs[spec.key],
                    before=before[spec.key], predicted=predicted[spec.key],
                    deleted=deleted[spec.key], remaining=remaining[spec.key],
                )
                for spec in SPECS
            )
    finally:
        eng.dispose()


def main(argv: "list[str] | None" = None) -> int:
    """``python scripts/retention.py [--db-url URL] [--dry-run] [--<表>-days N]``。

    **退出码**：``0`` = 跑完（含「一行都没删」的那一档，那是常态不是故障）；
    ``2`` = 被拒（:class:`RetentionError` / ``BackupError``：禁区、库不存在、
    窗口低于下界、实删与预告不符）。⚠️ 预期外的 bug **照常抛栈**（不被捕），
    与 ``scripts/backup.py`` 的 ``main()`` 同一条口径。

    ⚠️ ``--db-url`` 的缺省**不是** :data:`app.config.DEFAULT_DB_URL`（那是禁区
    ``backend/pe.db``），而是 ``PE_DB_URL`` > ``app.main.DEMO_DB_URL`` ——
    解析与禁区守卫都**复用** ``scripts/backup.py`` 的 :func:`resolve_db_path`，
    本模块不写第二个解析器、也不写第二道禁区守卫。
    """
    parser = argparse.ArgumentParser(
        prog="python scripts/retention.py",
        description=(
            "留存清理：按保留窗口删 login_attempt / user_session（**只删已过期的**）/ "
            "audit_log / read_audit_log 四张表的过期行。⚠️ 破坏性、不可撤销；"
            "先 --dry-run 看一遍预告。"
        ),
    )
    parser.add_argument(
        "--db-url", default=None,
        help=(
            "要清理的库 URL（sqlite:///…）。缺省读 $PE_DB_URL，再缺省是 "
            "app.main.DEMO_DB_URL（= backend/pe_demo.db，与 backup.ps1 一致）。"
            "⚠️ 刻意不回落到 app.config.DEFAULT_DB_URL：那是禁区 backend/pe.db"
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "**一行都不删**：只打印四张表各自「将删多少行」，并复核总行数没变。"
            "⚠️ 这一档连写事务都不开（不取写锁），故可以在服务跑着的时候安全地看"
        ),
    )
    for spec in SPECS:
        parser.add_argument(
            "--%s-days" % spec.key.replace("_", "-"),
            type=int, default=None, dest="%s_days" % spec.key,
            help=(
                "%s 的保留窗口（天）。缺省 %d（⚠️ 缺省值的唯一所有者是 "
                "scripts/retention.py 的 DEFAULT_* 常量，spec 那三个数的住址见它的"
                "模块 docstring）；也可用环境变量 %s 覆盖。下界 %d 天"
                % (spec.table, spec.default_days, spec.env_var, spec.min_days)
            ),
        )
    args = parser.parse_args(argv)

    db_path = resolve_db_path(args.db_url)
    if not db_path.is_file():
        raise RetentionError(
            f"{db_path} 不存在：没有库可清理。⚠️ 本脚本刻意不让 SQLite「打开即建」"
            f"（那会把「路径写错了」变成一次「四张表都是 0 行」的静默成功）；"
            f"演示库请用 backend/scripts/demo.ps1 建一份，试用库请用 scripts/trial.ps1"
        )
    db_url = "sqlite:///" + db_path.resolve().as_posix()
    explicit = {
        spec.key: getattr(args, "%s_days" % spec.key) for spec in SPECS
    }
    clean(
        db_url,
        days={key: value for key, value in explicit.items() if value is not None},
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    BACKEND = pathlib.Path(__file__).resolve().parents[1]
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    try:
        sys.exit(main())
    except (RetentionError, BackupError) as exc:
        print("清理**没有**执行（拒绝或回滚）：%s" % exc, file=sys.stderr)
        sys.exit(2)
