"""**30** 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.7，Plan 05A 的 ``user_session``、
Plan 06 Task 3 的 ``login_attempt``、Task 5 的 ``audit_log``、Plan 08 Task 1 的
``read_audit_log`` 与 **Task 4 的 ``bind_token``** 都按 §13）。

⚠️ 张数由 Plan 02 与 Plan 03 **逐 Task 递增**（Plan 02 Task 2 加 ``exercise`` → 15；
Task 3 加 ``prescription_template`` → 16；Task 6 加 ``prescription`` + ``weekly_adjustment``
→ 18，计划原文按旧编号写作 Task 9，见计划的「Task 重编号对照表」；
**Plan 03 Task 2 一次加 7 张 → 25**：反馈三源 4 张（spec §4.5）+ 预警/通知 2 张（§4.6）
+ 班级周报 1 张（§4.7），全部住在 :mod:`.feedback`；
**Plan 05A Task 1 加 1 张 → 26**：``user_session``，住在 :mod:`.auth`；
**Plan 06 Task 3 再加 1 张 → 27**：``login_attempt``，也住在 :mod:`.auth`；
**Plan 06 Task 5 再加 1 张 → 28**：``audit_log``，住在**新建的** :mod:`.audit`
——⚠️ 它**不能**放进 :mod:`.ops`（spec §4.6 的标题逐字是「预警与运维」，看着像它的家），
本包对 ``ops`` 是星号导入，逐字理由见 :mod:`.audit` 的 docstring 末节；
**Plan 08 Task 1 再加 1 张 → 29**：``read_audit_log``，也住在 :mod:`.audit`；
**Plan 08 Task 4 再加 1 张 → 30**：``bind_token``，住在 :mod:`.auth`
——⚠️ 它与那两张鉴权表是**同一个族的第三张**（都只由 HTTP 请求写、都不带 ``batch_id``、
都不进公有导入面），逐字理由见 :mod:`.auth` 的模块 docstring 第一节），
每加一张都要同步改 ``tests/db/test_models.py`` 的三处 ``==``、``expected`` 集合与函数名里
的英文数词，归属表与**完整同步清单**（Task 6 实测比派单给的多两项：``json_text_columns``
的条数与 ``_BATCH_OWNED_TABLES``；Plan 03 Task 2 又实测多两项：外键总数与
``_in_domain`` 列数；**Plan 05A Task 1 再实测多两项**：``tests/seed/test_generate.py``
的**表分区穷尽性**与 ``tests/api/test_crud.py`` 里那两处 ``len(Base.metadata.tables)``）
见 :mod:`.prescription` 的模块 docstring。

三条贯穿全表的约定，改动前请先读完：

1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
   声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
   当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
   ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
   ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。

2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
   断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
   约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。
   ⚠️ **``_in_domain`` 只吃字符串词表**，故整数区间要手写 CHECK：全库第一处是
   ``rpe_record.rpe`` 的 ``BETWEEN 0 AND 10``（Plan 03 Task 2，P3-A5），
   它的文本同样**由类常量生成**（``RPE_MIN`` / ``RPE_MAX``），守的是同一条纪律。

3. **JSON 形态的列一律用 :class:`JsonText`**（21 个列，无一例外）。SQLite 没有原生
   JSON，该类型以 ``TEXT`` 为底层、由它自己负责 dumps/loads，调用方拿到手的直接是
   原样的 ``dict`` / ``list`` / 标量，与 domain 层的值对象（如
   ``DerivedResult.annual_change: dict[str, float]``）同构，不必各自再约定一套序列化
   格式——那正是口径漂移的温床。为什么不用 SQLAlchemy 自带的 ``JSON`` 类型，见
   :class:`JsonText` 的 docstring（SQLite 的 NUMERIC 亲和性会改写标量）。

本包的八个表模块都不声明任何 ``relationship``：管道按 ``batch_id`` 批量读写，显式 ``select`` 比
懒加载更可预测，也不会在 Session 关闭后触发意外的延迟查询。

**本包是 2026-10 的一次拆包（Plan 02 Task 1）**，此前 14 张表同住一个 676 行的
``models.py``。小节划分严格按 spec §4（⚠️ 最后一行 :mod:`.auth` 是 Plan 05A 加的，
它按的是 **§13**「运行方式」那一节里新增的「登录」小节——鉴权不是 spec §4 的任何一个小节，
而把它硬塞进 §4.1「组织与身份」会让 ``organisation.py`` 同时是「学籍」与「凭据」两个主题的住址）：

=========================  ==========================================
模块                        spec 小节与内容
=========================  ==========================================
:mod:`.organisation`        §4.1 组织与身份（5 张）
:mod:`.assessment`          §4.2 学期节点数据（4 张）
:mod:`.derived`             §4.3 派生与分层（3 张）
:mod:`.prescription`        §4.4 处方（**4 张**：Task 2 的 ``exercise``、Task 3 的
                            ``prescription_template``、Task 6 的 ``prescription`` 与
                            ``weekly_adjustment``；逐 Task 归属见该模块的 docstring）
:mod:`.feedback`            §4.5 反馈三源 + §4.6 的 ``alert`` / ``notification``
                            + §4.7 班级周报（**7 张**，Plan 03 Task 2 填）
:mod:`.ops`                 §4.6 的**运维**两张（``daily_sync_run`` / ``cleaning_log``）
:mod:`.auth`                §13 的「登录」**三**张（``user_session``，Plan 05A Task 1 填；
                            ``login_attempt``，Plan 06 Task 3 填；
                            ``bind_token``，**Plan 08 Task 4** 填）
:mod:`.audit`               §13 的「审计留痕」**一**张（``audit_log``，Plan 06 Task 5 填。
                            ⚠️ 它按 §4.6「运维」也讲得通，而**刻意不住** :mod:`.ops`：
                            本文件对 ``ops`` 是**星号**导入，放进去会让 ``AuditLog``
                            自动进入包的公有命名空间、当场撞红下面那条基线守卫
                            ——与 ``alert`` / ``notification`` 那三张同一个理由，
                            逐字见 :mod:`.audit` 的模块 docstring 末节）
:mod:`._shared`             跨小节共享的 ``JsonText`` 与 ``_in_domain``
=========================  ==========================================

⚠️ **``alert`` / ``notification`` / ``weekly_class_report`` 住在 :mod:`.feedback` 而不在
:mod:`.ops`，尽管 spec §4.6 的标题逐字是「预警与运维」**（Plan 03 账本 P3-A1，Critical）。
理由是**导入机制**：本文件对 ``ops`` 是 ``from .ops import *``（星号），对 ``feedback``
是 ``from . import feedback``（非星号），故放进 ``ops.py`` 的类名会**自动**进入本包的
公有命名空间、当场撞红下面那条基线守卫，而唯一的「修法」（把基线从 33 抬到 36）
正是 Ruling 97 禁止的。**别按 spec 的章节标题搬**，完整理由写在 :mod:`.feedback`
的模块 docstring 里。
⚠️ **Plan 05A 的 ``user_session`` 撞的是同一条**：``UserSession`` 也**不进**公有导入面，
故 :mod:`.auth` 与 :mod:`.feedback` / :mod:`.prescription` 一样走**非星号**导入，
基线仍是 **33**（⚠️ 计划 §3.1 写的是「``_MODELS_PUBLIC_BASELINE`` 33 → ?」，
实现者实测的答复是**不变**，理由逐字见下面 ``__all__`` 上方那段注释）。

**``from app.db import models`` 的导入面逐字未变**：``models.Student``、``models.Base``、
``models.JsonText``、``models._in_domain`` 全部照旧可用。这一点由
``tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split``
钉住——它把拆包**之前**实测的 33 个公有名（``sorted(n for n in dir(models) if not
n.startswith("_"))``，Plan02 Ruling 1 的可执行判据）字面写进测试，拆包后逐字比对。
唯一的新增名是八个子模块本身（``models.organisation`` 等），那是包的结构性属性、
不是导入面，测试里显式排除并断言排除集与基线不相交。
⚠️ **Plan 02 的 4 个表类、Plan 03 的 7 个与 Plan 05A 的 1 个都不在那 33 个里**，
守卫是 ``…::test_new_tables_stay_out_of_the_models_public_namespace``。

⚠️ **子模块刻意不定义 ``__all__``**：本文件用 ``from .x import *`` 重导出，于是包的公有
名恰好等于「各子模块自己需要的那些 import 的并集」——这正是拆包前单模块的语义。哪个子
模块一旦定义了 ``__all__``，``import *`` 就会被它截断、并集缩小，上面那条测试当场变红。
所以**不要给子模块加 ``__all__``**；要收窄导入面，先改那条测试的判据并说明理由。

⚠️ **Plan 06 Task 1 起本仓有迁移链了，「schema 改动 = 重建库」那句话作废**（此前本处
逐字写着「本仓不做迁移……没有 Alembic，也不打算有」，那是 Plan 01 的裁定，
Plan 06 由用户于 2026-10-13 推翻：这是要交付给甲方的产品，现场升级版本**不能丢数据**）。
现在的口径是：改本包下的模型 → ``alembic revision --autogenerate`` → 人审那条迁移 →
守卫转绿。逐字流程见 **spec §13.7**，两条守卫是
``tests/db/test_migration_baseline.py``（迁移建出来的库 == ``create_all`` 建出来的库）
与 ``tests/db/test_migration_chain.py``（改了模型没写迁移就红）。
⚠️ ``init_db`` 的**内存库那一档仍然走 ``create_all``**（快；全部测试都走它），
磁盘库走 ``alembic upgrade head``。这个不对称由上面第一条守卫兜住。
⚠️ 下面这两条**禁区口径一字未改**，只是「重建库」不再是升级的必要步骤：
``backend/pe.db`` **不得存在**、``backend/data/seed/`` **恒为 0 文件**。
⚠️⚠️ **本处此前教的是「删掉 ``pe.db`` 重跑 ``python -m app.seed.generate``」**，
而那一句教人破**两个**禁区（``pe.db`` 不得存在、那个 CLI 的缺省 CSV 目录是
``backend/data/seed/``、恒为 0 文件）。重建演示库请走 ``backend/scripts/demo.ps1``
（它第一步就是删旧演示库）；确实要用那三个 CLI 就**必须**显式传 ``--db-url``
与 ``--csv-dir``。完整口径见 spec §13.3 与 :func:`app.db.session.init_db` 的 docstring。
⚠️ Plan 03 Task 2 之后**手工演示用的是 ``backend/pe_demo.db``**（``app.main.DEMO_DB_URL``），
而 ``pe.db`` 是禁区；重建演示库请删 ``pe_demo.db`` 后按 :mod:`app.main` 模块 docstring
里那三行跑（第二行把 ``DEMO_DB_URL`` 读进 ``PE_DB_URL``）。
"""

# _in_domain 带前导下划线，`import *` 不会带它过来；显式重导出以保持
# `app.db.models._in_domain` 这个既有写法可用（tests/db/test_models.py 的注释引用它）。
from ._shared import _in_domain  # noqa: F401

# 八个子模块刻意不定义 __all__，故 `import *` 带过来的是它们各自命名空间里的全部公有名，
# 其并集 == 拆包前单模块 models.py 的公有名集合（见上方 docstring 与那条基线测试）。
# ⚠️ 下面那五行是**星号**导入的五个，另两个（`feedback` / `prescription`）与 Plan 05A
# 新加的 `auth` 是**非星号**的，理由逐字见再下面那两段注释。
from ._shared import *  # noqa: F401,F403
from .organisation import *  # noqa: F401,F403
from .assessment import *  # noqa: F401,F403
from .derived import *  # noqa: F401,F403
from .ops import *  # noqa: F401,F403

# `audit` / `auth` / `feedback` / `prescription` 四者的导入都是**承重的**：只有在本模块被
# import 之后，这四个子模块里的表类才注册进 `Base.metadata`。`prescription` 自 Plan 02
# Task 2 起承重（`Exercise`、Task 3 的 `PrescriptionTemplate`、Task 6 的 `Prescription` /
# `WeeklyAdjustment`）；`feedback` 自 **Plan 03 Task 2** 起承重（7 张表）——在此之前它
# 是一个 475 B 的空壳，导入它只是为了让「这里为什么没有表」那段 docstring 随包一起被加载；
# `auth` 自 **Plan 05A Task 1** 起承重（`user_session` 一张；**Plan 06 Task 3 又加一张**
# `login_attempt`，故今天那个子模块是两张表）；`audit` 自 **Plan 06 Task 5** 起承重
# （`audit_log` 一张）。
# 漏掉任何一个，`tests/db/test_models.py::test_all_twenty_nine_tables_created` 当场红。
# `app.db.models.audit` / `.auth` / `.feedback` / `.prescription` 这四个属性名也让写入方
# 直接可用。
from . import audit, auth, feedback, prescription  # noqa: F401

# ⚠️ Plan 02 新加的表类（`Exercise` / `PrescriptionTemplate` / `Prescription` /
# `WeeklyAdjustment` 四个）、**Plan 03 Task 2 新加的七个**（`ClassSession` / `RpeRecord` /
# `TrainingLog` / `MiniTest` / `Alert` / `Notification` / `WeeklyClassReport`）、
# **Plan 05A Task 1 / Plan 06 Task 3 各新加的一个**（`UserSession` / `LoginAttempt`）
# 与 **Plan 06 Task 5 新加的一个**（`AuditLog`）
# **刻意不进** `__all__`、
# 也没有 `from .prescription import *` / `from .feedback import *` / `from .auth import *`
# / `from .audit import *`：
# `test_models_public_namespace_is_unchanged_by_the_split`
# 钉的是**拆包之前**（基线 `e26347f`）实测的 33 个公有名，往那份基线里加新名字
# 等于把「拆包没改导入面」偷换成「拆包后的现状」，两侧就同源了（硬规矩 #35）。
# 故这三个计划的表按子模块引用：`from app.db.models.prescription import Exercise`、
# `from app.db.models.feedback import Alert`、`from app.db.models.auth import UserSession`。
# 这条纪律对 Task 3 的 `PrescriptionTemplate` 同样成立（账本 Ruling 97 /「带进 Task 3 的
# 清单」⑨），守卫是 `tests/test_refdata_prescription.py` 的
# `test_prescription_template_is_not_in_the_models_public_namespace`。
# ⚠️ **Task 6 顶回过一次派单**：派单的 Step 0 第 6 格要求把 `_MODELS_PUBLIC_BASELINE`
# 从 33 抬到 35（加 `Prescription` 与 `WeeklyAdjustment`）并在本文件重导出这两个类。
# 那与 Ruling 97 **直接冲突**——那条守卫的 docstring 逐字把「基线被更新成含新名字」列为
# 它要防的失效形态，而抬基线会让 `…is_unchanged_by_the_split` 这个函数名当场变成谎话。
# 故 Task 6 **没有**重导出、**没有**动那份基线（仍是 33），改为新增一条守卫
# `tests/db/test_models.py::test_new_tables_stay_out_of_the_models_public_namespace`
# 把 Ruling 97 钉到这些表上。Plan 03 Task 2 把那条守卫从 2 个表类扩到 **11** 个并改了名，
# **Plan 05A Task 1 再扩到 12 个并把它改成计划无关的名字**（原名 `…plan02_and_plan03…`
# 会让下一个计划的实现者以为新表由别处守，而那句话逐字写在它自己的 docstring 里）；
# 基线仍是 33、子模块由六个变成**七个**（**Plan 06 Task 5 再变成八个**：+ ``audit``）。
# Task 5–9 的写入方请写
# `from app.db.models.feedback import ClassSession, RpeRecord, TrainingLog, MiniTest`
# 与 `from app.db.models.prescription import Prescription, WeeklyAdjustment`；
# Plan 05A 与 Plan 06 的写入方请写 `from app.db.models.auth import UserSession`
# 与 `from app.db.models.auth import LoginAttempt`；
# **Plan 06 Task 5 的写入方请写 `from app.db.models.audit import AuditLog`**
# （今天只有一个写入方：`app/api/audit.py` 的 `record`；一个读取方：
# `app/api/routers/audit.py` 的 `list_audit_logs`）。
# ⚠️⚠️ **它为什么不住 `ops.py`**（spec §4.6 的标题逐字是「预警与运维」，看着像它的家）：
# 本文件对 `ops` 是 `from .ops import *`（**星号**），搬过去 `AuditLog` 会自动进入包的
# 公有命名空间、当场撞红 `_MODELS_PUBLIC_BASELINE`（33）那条守卫，而唯一的「修法」
# （把基线抬到 34）正是 Ruling 97 禁止的——与 `alert` / `notification` /
# `weekly_class_report` 那三张**同一条**（P3-A1）。逐字理由见 `.audit` 的模块 docstring 末节。
# ⚠️⚠️ **计划 §3.1 写的是「`_MODELS_PUBLIC_BASELINE` 33 → ?（新增 `UserSession` 等公开名）」，
# 实现者顶回**：`UserSession` **不进**公有面（上面那条 Ruling 97 直接适用于它，
# 而计划的同一节也逐字要求「`models/__init__.py` 的 `__all__` 要加」——
# 那一句与 Ruling 97 冲突，故按 Ruling 97 办：`__all__` **一个字都没动**）。
# 实测：`len({n for n in dir(models) if not n.startswith('_')} - 八个子模块名) == 33` 不变。
# 代价是 `UserSession` 只能按 `app.db.models.auth.UserSession` 引用，
# 与 Plan 02/03 那 11 张表同一个形状。
__all__ = [
    "Semester",
    "Teacher",
    "Student",
    "CourseSection",
    "Enrollment",
    "FitnessTestBatch",
    "FitnessTestResult",
    "BodyComposition",
    "InterestSurvey",
    "PercentileSnapshot",
    "DerivedMetrics",
    "StratificationResult",
    "DailySyncRun",
    "CleaningLog",
]
