"""18 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.4、§4.6）。

⚠️ 张数由 Plan 02 **逐 Task 递增**（Task 2 加 ``exercise`` → 15；Task 3 加
``prescription_template`` → 16；**Task 6 加 ``prescription`` + ``weekly_adjustment`` → 18**，
计划原文按旧编号写作 Task 9，见计划的「Task 重编号对照表」），
每加一张都要同步改 ``tests/db/test_models.py`` 的三处 ``==``、``expected`` 集合与函数名里
的英文数词，归属表与**完整同步清单**（Task 6 实测比派单给的多两项：``json_text_columns``
的条数与 ``_DERIVED_TABLES``）见 :mod:`.prescription` 的模块 docstring。

三条贯穿全表的约定，改动前请先读完：

1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
   声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
   当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
   ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
   ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。

2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
   断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
   约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。

3. **JSON 形态的列一律用 :class:`JsonText`**（14 个列，无一例外）。SQLite 没有原生
   JSON，该类型以 ``TEXT`` 为底层、由它自己负责 dumps/loads，调用方拿到手的直接是
   原样的 ``dict`` / ``list`` / 标量，与 domain 层的值对象（如
   ``DerivedResult.annual_change: dict[str, float]``）同构，不必各自再约定一套序列化
   格式——那正是口径漂移的温床。为什么不用 SQLAlchemy 自带的 ``JSON`` 类型，见
   :class:`JsonText` 的 docstring（SQLite 的 NUMERIC 亲和性会改写标量）。

本包的六个表模块都不声明任何 ``relationship``：管道按 ``batch_id`` 批量读写，显式 ``select`` 比
懒加载更可预测，也不会在 Session 关闭后触发意外的延迟查询。

**本包是 2026-10 的一次拆包（Plan 02 Task 1）**，此前 14 张表同住一个 676 行的
``models.py``。小节划分严格按 spec §4：

=========================  ==========================================
模块                        spec 小节与内容
=========================  ==========================================
:mod:`.organisation`        §4.1 组织与身份（5 张）
:mod:`.assessment`          §4.2 学期节点数据（4 张）
:mod:`.derived`             §4.3 派生与分层（3 张）
:mod:`.prescription`        §4.4 处方（**4 张**：Task 2 的 ``exercise``、Task 3 的
                            ``prescription_template``、Task 6 的 ``prescription`` 与
                            ``weekly_adjustment``；逐 Task 归属见该模块的 docstring）
:mod:`.feedback`            §4.5 反馈（**今天为空**，Plan 03 填）
:mod:`.ops`                 §4.6 预警与运维（2 张）
:mod:`._shared`             跨小节共享的 ``JsonText`` 与 ``_in_domain``
=========================  ==========================================

**``from app.db import models`` 的导入面逐字未变**：``models.Student``、``models.Base``、
``models.JsonText``、``models._in_domain`` 全部照旧可用。这一点由
``tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split``
钉住——它把拆包**之前**实测的 33 个公有名（``sorted(n for n in dir(models) if not
n.startswith("_"))``，Plan02 Ruling 1 的可执行判据）字面写进测试，拆包后逐字比对。
唯一的新增名是六个子模块本身（``models.organisation`` 等），那是包的结构性属性、
不是导入面，测试里显式排除并断言排除集与基线不相交。

⚠️ **子模块刻意不定义 ``__all__``**：本文件用 ``from .x import *`` 重导出，于是包的公有
名恰好等于「各子模块自己需要的那些 import 的并集」——这正是拆包前单模块的语义。哪个子
模块一旦定义了 ``__all__``，``import *`` 就会被它截断、并集缩小，上面那条测试当场变红。
所以**不要给子模块加 ``__all__``**；要收窄导入面，先改那条测试的判据并说明理由。

⚠️ **本仓不做迁移，schema 改动 = 重建库**：``init_db`` 走 ``Base.metadata.create_all``，
它对**已存在**的表既不补列、也不补索引/约束（详见 :func:`app.db.session.init_db` 的
docstring）。没有 Alembic，也不打算有。``backend/pe.db`` 不入库（``.gitignore``），故这
对版本控制没有影响；但本地已经生成过库的人，改完 schema 必须删掉 ``pe.db`` 重跑
``python -m app.seed.generate``，否则新列在旧库上根本不存在。
"""

# _in_domain 带前导下划线，`import *` 不会带它过来；显式重导出以保持
# `app.db.models._in_domain` 这个既有写法可用（tests/db/test_models.py 的注释引用它）。
from ._shared import _in_domain  # noqa: F401

# 六个子模块刻意不定义 __all__，故 `import *` 带过来的是它们各自命名空间里的全部公有名，
# 其并集 == 拆包前单模块 models.py 的公有名集合（见上方 docstring 与那条基线测试）。
from ._shared import *  # noqa: F401,F403
from .organisation import *  # noqa: F401,F403
from .assessment import *  # noqa: F401,F403
from .derived import *  # noqa: F401,F403
from .ops import *  # noqa: F401,F403

# `feedback` 今天仍为空，导入它是为了让它的模块 docstring（「这里为什么没有表」的唯一交代）
# 随包一起被加载。`prescription` 的导入自 Plan 02 Task 2 起是**承重的**：`Exercise`、
# Task 3 的 `PrescriptionTemplate` 与 Task 6 的 `Prescription` / `WeeklyAdjustment` 只有在
# 本模块被 import 之后才注册进 `Base.metadata`，漏掉它这四张表就不存在，
# `tests/db/test_models.py::test_all_eighteen_tables_created` 当场红。
# `app.db.models.prescription` 这个属性名也让 Task 7 直接可用。
from . import feedback, prescription  # noqa: F401

# ⚠️ Plan 02 新加的表类（今天是 `Exercise` / `PrescriptionTemplate` / `Prescription` /
# `WeeklyAdjustment` 四个）**刻意不进** `__all__`、
# 也没有 `from .prescription import *`：`test_models_public_namespace_is_unchanged_by_the_split`
# 钉的是**拆包之前**（基线 `e26347f`）实测的 33 个公有名，往那份基线里加 Plan 02 的新名字
# 等于把「拆包没改导入面」偷换成「拆包后的现状」，两侧就同源了（硬规矩 #35）。
# 故 Plan 02 的表按子模块引用：`from app.db.models.prescription import Exercise`。
# 这条纪律对 Task 3 的 `PrescriptionTemplate` 同样成立（账本 Ruling 97 /「带进 Task 3 的
# 清单」⑨），守卫是 `tests/test_refdata_prescription.py` 的
# `test_prescription_template_is_not_in_the_models_public_namespace`。
# ⚠️ **Task 6 顶回过一次派单**：派单的 Step 0 第 6 格要求把 `_MODELS_PUBLIC_BASELINE`
# 从 33 抬到 35（加 `Prescription` 与 `WeeklyAdjustment`）并在本文件重导出这两个类。
# 那与 Ruling 97 **直接冲突**——那条守卫的 docstring 逐字把「基线被更新成含新名字」列为
# 它要防的失效形态，而抬基线会让 `…is_unchanged_by_the_split` 这个函数名当场变成谎话。
# 故 Task 6 **没有**重导出、**没有**动那份基线（仍是 33），改为新增一条守卫
# `tests/db/test_models.py::test_plan02_tables_stay_out_of_the_models_public_namespace`
# 把 Ruling 97 钉到这两张表上。Task 7 的写入方请写
# `from app.db.models.prescription import Prescription, WeeklyAdjustment`。
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
