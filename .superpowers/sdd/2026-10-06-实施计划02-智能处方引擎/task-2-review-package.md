# Task 2 评审包 — `fb5bddb..966eae0`（主体 + 2 轮 fix）

> 生成方式：控制者用 python `subprocess` 跑 git，输出原样拼接（不经 PowerShell 管道，避免其自行加 CRLF）。


## git log --oneline

```
966eae0 test: Plan02 Task2 fix round 2（Ruling 106/107）——两份架构守卫的过期散文改正 + 3 条新守卫，528 → 531 passed、domain 覆盖 441/120 仍 100%、backend/app/** 零字节改动
c21767d refactor: Plan02 Task2 fix round 1（Ruling 96）——动作库的 7 个值对象/词表搬进 app/domain/prescription/exercises.py，528 passed 不变、domain 覆盖 406/114 → 441/120 仍 100%
4386ee2 docs: Ruling 96 File Structure 加 app/domain/prescription/exercises.py（值对象住 domain，与 tables.py/refdata.py 同构）
d40f36c docs: Ruling 92/93 重排 spec §14 编号（Task 2 已占 #28，Task 12 的 7 项去重后为 #29-#34 共 6 项，总数仍 34）
3ea27cc feat: Plan02 Task2 动作库——exercise 表 + exercises.yaml（23 个动作）+ exercise_equivalence.yaml（10 条映射），481 → 528 passed
```


## git diff --stat

```
 ...37\345\236\213-\350\256\276\350\256\241spec.md" |   1 +
 ...244\204\346\226\271\345\274\225\346\223\216.md" |  16 +-
 backend/app/db/models/__init__.py                  |  23 +-
 backend/app/db/models/_shared.py                   |  11 +-
 backend/app/db/models/prescription.py              | 137 ++-
 backend/app/db/session.py                          |   6 +-
 backend/app/domain/prescription/__init__.py        |  37 +
 backend/app/domain/prescription/exercises.py       | 200 +++++
 backend/app/domain/prescription/templates.py       |  39 +
 backend/app/refdata.py                             |  14 +-
 backend/app/refdata_prescription.py                | 406 +++++++++
 backend/data/exercise_equivalence.yaml             | 126 +++
 backend/data/exercises.yaml                        | 267 ++++++
 backend/tests/architecture/test_domain_purity.py   |  33 +-
 backend/tests/architecture/test_layering.py        |  46 +-
 backend/tests/db/test_models.py                    |  50 +-
 .../tests/domain/test_prescription_templates.py    | 147 ++++
 backend/tests/seed/test_generate.py                |  54 +-
 backend/tests/test_refdata_prescription.py         | 921 +++++++++++++++++++++
 19 files changed, 2472 insertions(+), 62 deletions(-)
```


## git diff --name-status

```
M	"Document/2026-09-28-\344\275\223\350\202\262\351\227\255\347\216\257\345\216\237\345\236\213-\350\256\276\350\256\241spec.md"
M	"Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
M	backend/app/db/models/__init__.py
M	backend/app/db/models/_shared.py
M	backend/app/db/models/prescription.py
M	backend/app/db/session.py
A	backend/app/domain/prescription/__init__.py
A	backend/app/domain/prescription/exercises.py
A	backend/app/domain/prescription/templates.py
M	backend/app/refdata.py
A	backend/app/refdata_prescription.py
A	backend/data/exercise_equivalence.yaml
A	backend/data/exercises.yaml
M	backend/tests/architecture/test_domain_purity.py
M	backend/tests/architecture/test_layering.py
M	backend/tests/db/test_models.py
A	backend/tests/domain/test_prescription_templates.py
M	backend/tests/seed/test_generate.py
A	backend/tests/test_refdata_prescription.py
```


## 禁区命中（三者都必须为空）

```
-- backend/data:
backend/data/exercise_equivalence.yaml
backend/data/exercises.yaml
-- backend/app/seed:
(none)-- backend/data/national_standard_2014.csv:
(none)```


## 生产代码 diff（backend/app/**）

```diff
diff --git a/backend/app/db/models/__init__.py b/backend/app/db/models/__init__.py
index 75d1919..f658967 100644
--- a/backend/app/db/models/__init__.py
+++ b/backend/app/db/models/__init__.py
@@ -1,44 +1,49 @@
-"""14 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.3、§4.6）。
+"""15 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.4、§4.6）。
+
+⚠️ 张数由 Plan 02 **逐 Task 递增**（Task 2 加 ``exercise`` → 15；Task 3 加
+``prescription_template`` → 16；Task 9 加 ``prescription`` + ``weekly_adjustment`` → 18），
+每加一张都要同步改 ``tests/db/test_models.py`` 的三处 ``==``、``expected`` 集合与函数名里
+的英文数词，归属表见 :mod:`.prescription` 的模块 docstring。
 
 三条贯穿全表的约定，改动前请先读完：
 
 1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
    声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
    当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
    ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
    ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。
 
 2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
    断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
    约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。
 
-3. **JSON 形态的列一律用 :class:`JsonText`**（八个列，无一例外）。SQLite 没有原生
+3. **JSON 形态的列一律用 :class:`JsonText`**（九个列，无一例外）。SQLite 没有原生
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
-:mod:`.prescription`        §4.4 处方（**今天为空**，Plan 02 Task 2/3/9 填）
+:mod:`.prescription`        §4.4 处方（**1 张**：Task 2 的 ``exercise``；Task 3/9 再加 3 张）
 :mod:`.feedback`            §4.5 反馈（**今天为空**，Plan 03 填）
 :mod:`.ops`                 §4.6 预警与运维（2 张）
 :mod:`._shared`             跨小节共享的 ``JsonText`` 与 ``_in_domain``
 =========================  ==========================================
 
 **``from app.db import models`` 的导入面逐字未变**：``models.Student``、``models.Base``、
 ``models.JsonText``、``models._in_domain`` 全部照旧可用。这一点由
 ``tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split``
 钉住——它把拆包**之前**实测的 33 个公有名（``sorted(n for n in dir(models) if not
 n.startswith("_"))``，Plan02 Ruling 1 的可执行判据）字面写进测试，拆包后逐字比对。
@@ -62,24 +67,32 @@ docstring）。没有 Alembic，也不打算有。``backend/pe.db`` 不入库（
 from ._shared import _in_domain  # noqa: F401
 
 # 六个子模块刻意不定义 __all__，故 `import *` 带过来的是它们各自命名空间里的全部公有名，
 # 其并集 == 拆包前单模块 models.py 的公有名集合（见上方 docstring 与那条基线测试）。
 from ._shared import *  # noqa: F401,F403
 from .organisation import *  # noqa: F401,F403
 from .assessment import *  # noqa: F401,F403
 from .derived import *  # noqa: F401,F403
 from .ops import *  # noqa: F401,F403
 
-# 两个今天为空的小节也要被导入：它们的模块 docstring 是「这里为什么没有表」的唯一交代，
-# 而 `app.db.models.prescription` 这个属性名要让 Plan 02 Task 2/3 直接可用。
+# `feedback` 今天仍为空，导入它是为了让它的模块 docstring（「这里为什么没有表」的唯一交代）
+# 随包一起被加载。`prescription` 的导入自 Plan 02 Task 2 起是**承重的**：`Exercise` 只有在
+# 本模块被 import 之后才注册进 `Base.metadata`，漏掉它 `exercise` 表就不存在，
+# `tests/db/test_models.py::test_all_fifteen_tables_created` 当场红。
+# `app.db.models.prescription` 这个属性名也让 Plan 02 Task 3/9 直接可用。
 from . import feedback, prescription  # noqa: F401
 
+# ⚠️ Plan 02 新加的表类（今天是 `Exercise`）**刻意不进** `__all__`、也没有
+# `from .prescription import *`：`test_models_public_namespace_is_unchanged_by_the_split`
+# 钉的是**拆包之前**（基线 `e26347f`）实测的 33 个公有名，往那份基线里加 Plan 02 的新名字
+# 等于把「拆包没改导入面」偷换成「拆包后的现状」，两侧就同源了（硬规矩 #35）。
+# 故 Plan 02 的表按子模块引用：`from app.db.models.prescription import Exercise`。
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
diff --git a/backend/app/db/models/_shared.py b/backend/app/db/models/_shared.py
index 1172848..6f27f04 100644
--- a/backend/app/db/models/_shared.py
+++ b/backend/app/db/models/_shared.py
@@ -1,16 +1,17 @@
 """``app.db.models`` 包内共享的两件基础设施：JSON 列类型与取值域约束生成器。
 
 拆包（Plan 02 Task 1）之前它们与 14 张表同住一个 ``models.py``。放这里而不是塞进六个
-表模块里的某一个，是因为**四个**表模块都要用它们（``organisation`` / ``assessment`` /
-``derived`` / ``ops``）：塞进任何一个都会让另外三个为了拿一个工具而 import 一个与它
-毫无关系的小节（例如 ``derived`` 为了 ``JsonText`` 去 import ``organisation``）。
+表模块里的某一个，是因为**五个**表模块都要用它们（``organisation`` / ``assessment`` /
+``derived`` / ``ops``，以及 Plan 02 Task 2 起也用了它们的 ``prescription``）：塞进任何
+一个都会让另外几个为了拿一个工具而 import 一个与它毫无关系的小节（例如 ``derived`` 为了
+``JsonText`` 去 import ``organisation``）。
 
 模块名带前导下划线，故它不出现在包 ``__init__`` 那份「公有导入面」基线里
 （Plan02 Ruling 1 的判据是 ``sorted(n for n in dir(models) if not n.startswith("_"))``）。
 """
 
 import json
 from collections.abc import Iterable
 from typing import Any
 
 from sqlalchemy import CheckConstraint, Text
@@ -39,21 +40,23 @@ class JsonText(TypeDecorator):
     读回来是 Python ``int`` ``0`` / ``65``（浮点被降成整型），``65.5`` 与 ``65.0000001``
     才落 ``typeof='real'``——NUMERIC 亲和性把**能无损表示成整数**的实数降成整型、其余留
     ``real``。本段此前印的是「``65.0`` 存成 ``real`` 而非文本」，那与它自己下一句的结论
     相反：真存成 ``real 65.0`` 的话读回仍是 ``65.0``，「原值 65.0 kg」就不会被记成
     「原值 65」——正是**降成整型**才造成失真。这条探针**不在测试网里、不被守卫**
     （本仓没有任何测试用 SQLAlchemy 自带的 ``JSON`` 类型），属历史实测，fix round 3 复跑。
     对 ``cleaning_log`` 这种存标量的审计列，这是实打实的失真，而审计记录的全部价值就在于
     原值不被改写。
 
     以 ``TEXT`` 为底层类型即绕开亲和性转换，同时保留透明 dumps/loads：调用方拿到手的
-    仍是原样的 Python 对象，全库八个 JSON 形态的列共用这一种落法，不必区分「这一列
+    仍是原样的 Python 对象，全库九个 JSON 形态的列共用这一种落法（这个「九」由
+    ``tests/db/test_models.py::test_no_column_uses_builtin_sqlalchemy_json`` 的
+    ``len(json_text_columns) == 9`` 钉住，加列时两处一起改），不必区分「这一列
     要不要自己 ``json.dumps``」——那种不对称正是会被忘掉、且忘掉后静默出错的地方。
     ``ensure_ascii=False`` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。
     ``None`` 存 SQL ``NULL`` 而不是 ``'null'`` 文本，读回也是 ``None``。
 
     ``cache_ok = True`` 是必需的：缺了它 SQLAlchemy 会对每条用到该列的语句发
     ``SAWarning``（该类型无法生成缓存键），在 ``-W error`` 下直接变成失败。
     """
 
     impl = Text
     cache_ok = True
diff --git a/backend/app/db/models/prescription.py b/backend/app/db/models/prescription.py
index 7cb15fe..6b7dbf5 100644
--- a/backend/app/db/models/prescription.py
+++ b/backend/app/db/models/prescription.py
@@ -1,16 +1,131 @@
-"""spec §4.4 处方数据模型（**本模块今天刻意是空的**）。
+"""spec §4.4 处方数据模型（Plan 02 逐 Task 往这里加表，**四个 Task 四张表**）。
 
-Plan 02 Task 1 建了这个模块但**没有往里放任何表**，因为处方的四张表分属后续任务：
+计划完成后的状态是 **18 张表** = Plan 01 的 14 张 + 本小节的 4 张（计划
+``Document/2026-10-06-实施计划02-智能处方引擎.md`` ``:700``，行号取 shell 口径、绑定
+commit ``fb5bddb``）：
 
-* ``prescription`` / ``prescription_template`` / ``training_package`` 由 **Task 2/3** 建
-  （模板与动作库先落地，处方表要引用它们）；
-* ``prescription_override``（教师覆盖）与 ``prescription`` 的触发/幂等列由 **Task 9** 建。
+========================  =========  =========================================
+表                         归属 Task   备注
+========================  =========  =========================================
+``exercise``              **Task 2**  **已建**（本文件今天只有它）
+``prescription_template``  Task 3     18 套模板的索引行，YAML 在 ``data/prescription/``
+``prescription``           Task 9     计划 ``:524`` 的 Files 段明写「Modify 本文件（加两张表）」
+``weekly_adjustment``      Task 9     同上
+========================  =========  =========================================
 
-留空而不是先建一个空类占位（Plan02 Ruling 5）：一个没有列的 ORM 类会被
-``Base.metadata.create_all`` 建成一张**零列以外的空表**，而
-``tests/db/test_models.py::test_all_fourteen_tables_created`` 用 ``==`` 钉住了表集合
-（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把计划 02 的表建进来」）。
-先建空类等于自己弄红那道守卫，而它红得毫无信息量。
+**逐 Task 递增、不得一次性把四张都建出来**：
+``tests/db/test_models.py::test_all_fifteen_tables_created`` 用 ``==`` 钉住表集合
+（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把后续 Task 的表建进来」
+——那种提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感）。故 Task 3 与
+Task 9 各自加自己那张时，**必须同步改那道守卫的期望集合、``== 15`` 的三处断言与函数名里的
+「fifteen」**（``tests/db/test_models.py`` ``:24`` / ``:163`` / ``:228`` / ``:472``），
+以及本文件上面那张表。
 
-⚠️ 建表时请同时更新那道守卫的 ``expected`` 集合与它的「14 张」措辞。
+⚠️ **两处此前印错的说法，本次按硬规矩 #64 与计划逐 Task 交叉核对后更正**（Plan02 账本
+P2-A10；这两句熬过了 Task 1 的任务评审 + 5 轮 fix + 收尾评审，因为那六轮的注意力都在
+架构守卫与 ``test_models.py`` / ``daily.py`` 的散文上）：
+
+* ``training_package`` **不是表**。它是 ``prescription`` 的一个 ``JsonText`` 列——计划
+  ``:568``「断言新处方的 ``training_package`` 等于**无覆盖**的基线」、``:569``「
+  ``prescription`` 行数不变、``training_package`` 逐字段相同」都是按**列**在用这个词；
+  spec 全文也没有它作为表名的出处（spec §4.4 ``:240`` 那一行写的是「4 周训练包 JSON」）。
+* ``prescription_override`` **在计划里没有这张表**。Task 8 的 Files（计划 ``:491``）只建
+  ``app/domain/prescription/override.py`` + 它的测试；计划 ``:700`` 的 18 张表清单里没有它。
+  教师覆盖记录是 ``prescription`` 的一个 JSON 列（spec §4.4 ``:240``「教师覆盖记录 JSON」），
+  因为覆盖是**叠加在训练包上的纯函数**（spec §7.5），不需要自己的表。
+
+``exercise`` 与另外三张表有一处**性质上的不同**，值得写在这里：它是本小节唯一一张
+**参考数据**表（专家维护的知识资产在 DB 里的投影），另外三张是业务数据。故它的灌数据
+函数**不在** ``app/seed/``——那是仿真人口生成器的住址，且自 Plan 01 结案后重新冻结
+（Global Constraint #10）；``exercise`` 的同类是 ``app/refdata.py``，故灌数据函数是
+:func:`app.refdata_prescription.sync_exercises`（Plan02 账本 P2-A1 的裁定）。
 """
+
+from sqlalchemy import String
+from sqlalchemy.orm import Mapped, mapped_column
+
+from app.db.session import Base
+
+from ._shared import JsonText, _in_domain
+
+
+# ---------------------------------------------------------------------------
+# spec §4.4 处方：动作库（Task 2）
+# ---------------------------------------------------------------------------
+
+
+class Exercise(Base):
+    """一个运动动作。spec §4.4 ``:239`` 的六项与下面六列一一对应。
+
+    | spec §4.4 ``:239`` 原文                | 本表的列          |
+    | ====================================== | ================= |
+    | id                                     | ``id``            |
+    | 动作名                                 | ``name``          |
+    | 视频二维码 URL                         | ``video_url``     |
+    | **``impact_level``** ∈ {high, medium, low} | ``impact_level`` |
+    | 目标素质                               | ``targets``       |
+    | 器械需求                               | ``equipment``     |
+
+    另有一列 spec 没点名、但计划 Step 4 要求的 ``ref``：它是 ``exercise_ref`` 的落库形态，
+    也是模板 YAML 引用动作时用的键。**``ref`` 而不是 ``id`` 做引用键**，因为 ``id`` 是代理键、
+    随建库顺序变；专家在 YAML 里写 ``exercise_ref: interval_run``，那串字符必须在两次
+    重建库之间稳定。
+
+    ⚠️ **本表是 ``backend/data/exercises.yaml`` 的投影，不是第二个所有者**：唯一所有者是
+    那份 YAML，本表由 :func:`app.refdata_prescription.sync_exercises` 按 ``ref`` 幂等
+    upsert 灌进来。故**不要手工往这张表插行**——下一次 sync 不会删掉它（sync 只 upsert
+    YAML 里有的 ref），于是它会变成一个没有任何模板能引用、也没有视频源的孤儿行。
+
+    **``impact_level`` 取值域两处设防**（本包的约定 2，见 :mod:`app.db.models`）：
+    :attr:`IMPACT_LEVELS` 是唯一真相，SQL CHECK 的文本由 :func:`_in_domain` 从它生成，
+    两者不可能各说各话。它与 Python 侧的
+    :class:`app.domain.prescription.exercises.ImpactLevel` 是**两份**词表，由
+    ``tests/test_refdata_prescription.py::test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum``
+    钉住一致；本模块刻意**不 import** domain 来自动生成它——`db` 层反向依赖 `domain`
+    的枚举会让「改一个枚举成员」静默改掉 DDL，而 DDL 变更在本仓等于重建库。
+
+    **列宽**（硬规矩 #18）：``String(n)`` 的 ``n`` 必须容得下取值域里最长的值，而 SQLite
+    **不强制**长度，故溢出在本仓的测试里永远不报错、换 MySQL / PostgreSQL 才截断，且
+    **炸在读侧不在写侧**。逐列的口径（实测值由
+    ``tests/test_refdata_prescription.py::test_exercise_string_column_widths_fit_the_yaml_values``
+    从 YAML 现读现比，故这里只写「谁是最长者」而不写数字，免得数字与那份 YAML 漂移）：
+
+    * ``ref`` —— 最长者是 ``energy_expenditure_plus_10pct``（spec §7.2 ``:482`` 的 addon
+      模块名，本动作库照它命名以免出现第二个所有者）；
+    * ``name`` —— 中文动作名，最长者是 ``pnf_stretching`` 的「本体感觉神经肌肉促进拉伸」；
+    * ``video_url`` —— ``https://example.invalid/exercise/`` 前缀 + 最长的 ``ref``；
+    * ``equipment`` —— 最长者是 ``medicine_ball``。
+
+    ⚠️ **这四列不被 Plan 01 那道列宽遍历测试覆盖**（Plan02 账本 P2-A5）：
+    ``tests/db/test_models.py`` 的 ``_in_domain_columns()`` 只反解**带 ``_in_domain``
+    CHECK** 的列，而 ``ref`` / ``name`` / ``video_url`` / ``equipment`` 的取值域不是封闭
+    集合、没有 CHECK。本表 5 个 ``String(n)`` 列里只有 ``impact_level`` 会被那道测试扫到。
+
+    ``targets`` 用 :class:`JsonText` 存**排序后的桶名列表**（``["endurance", "strength"]``）：
+    桶名来自 :data:`app.domain.indicators.ITEM_BUCKET` 的三个值，排序让落库字节与遍历序
+    无关（``frozenset`` 不能直接 JSON 序列化，且它的迭代序跨进程不稳定）。
+    """
+
+    __tablename__ = "exercise"
+
+    #: spec §4.4 ``:239`` 的取值域。**与 Python 侧 ``ImpactLevel`` 是两份、由测试钉住一致**。
+    IMPACT_LEVELS: set[str] = {"high", "medium", "low"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    #: ``exercise_ref``。模板 YAML 与 ``exercise_equivalence.yaml`` 都按它引用动作。
+    ref: Mapped[str] = mapped_column(String(48), unique=True)
+    name: Mapped[str] = mapped_column(String(64))
+    #: 视频二维码 URL。本批一律是 RFC 2606 占位符 ``https://example.invalid/exercise/<ref>``
+    #: （``.invalid`` 是保留 TLD、DNS 保证不可解析），真实视频源待项目组提供——见
+    #: ``backend/data/exercises.yaml`` 的头注释与 spec §14。
+    video_url: Mapped[str] = mapped_column(String(256))
+    impact_level: Mapped[str] = mapped_column(String(8))
+    #: 该动作瞄准的素质桶名列表，取值域 =
+    #: ``frozenset(v for v in ITEM_BUCKET.values() if v is not None)``（三个桶名；
+    #: ⚠️ 不是 ``set(ITEM_BUCKET.values())``，那个集合含 ``None``，Plan02 账本 P2-A4）。
+    targets: Mapped[list] = mapped_column(JsonText)
+    equipment: Mapped[str] = mapped_column(String(32))
+
+    __table_args__ = (
+        _in_domain("impact_level", IMPACT_LEVELS, "ck_exercise_impact_level"),
+    )
diff --git a/backend/app/db/session.py b/backend/app/db/session.py
index 441fa1b..a83ede1 100644
--- a/backend/app/db/session.py
+++ b/backend/app/db/session.py
@@ -1,14 +1,14 @@
 """数据库引擎、会话与建表入口。
 
 本模块只提供四样东西：声明基类 :class:`Base`、引擎工厂 :func:`engine`、会话类
-``Session``、建表函数 :func:`init_db`。14 张表的模型在 :mod:`app.db.models`，
+``Session``、建表函数 :func:`init_db`。15 张表的模型在 :mod:`app.db.models`，
 通用读写助手在 :mod:`app.db.repo`。此外在导入时注册一个 ``connect`` 钩子，打开
 SQLite 默认关闭的外键强制（见 :func:`_sqlite_foreign_keys_on`）。
 
 ``Session`` 直接就是 ``sqlalchemy.orm.Session`` 类本身，而不是绑定了某个引擎的
 ``sessionmaker`` 实例。调用方（测试、CLI、管道）自己先造引擎、再 ``Session(eng)``：
 这样同一份代码既能跑内存库也能跑磁盘库，且不会在导入期就把数据库 URL 钉死——
 测试因此不必依赖任何磁盘文件。
 """
 from sqlalchemy import create_engine, event
 from sqlalchemy.engine import Engine
@@ -36,21 +36,21 @@ def _sqlite_foreign_keys_on(dbapi_connection, _record):
     覆盖不到。代价是它对本进程内**每一个**引擎生效——本项目只用 SQLite，故接受；
     将来若真接非 SQLite 后端，分支要加在本监听器内部（按 DBAPI 连接类型判断），
     不能靠缩小注册目标来解决，否则测试路径又会漏掉。
     """
     cursor = dbapi_connection.cursor()
     cursor.execute("PRAGMA foreign_keys=ON")
     cursor.close()
 
 
 class Base(DeclarativeBase):
-    """全部 14 张表的声明基类。
+    """全部 15 张表的声明基类（张数由 Plan 02 逐 Task 递增，归属见 :mod:`app.db.models`）。
 
     ``Base.metadata`` 是建表的唯一真相：表在 :mod:`app.db.models` 里声明一次，
     :func:`init_db` 据此 ``create_all``，不存在第二份需要手工同步的 DDL。
     """
 
 
 def engine(url: str) -> Engine:
     """按 URL 造一个引擎。
 
     ``url`` **没有缺省值**（Plan 02 Task 1，终审 C 组）。此前签名是
@@ -81,13 +81,13 @@ def init_db(eng: Engine) -> None:
 
     ⚠️ **``create_all`` 对已存在的表既不补列、也不补索引/约束**（SQLite 的
     ``CREATE TABLE IF NOT EXISTS`` 语义，SQLAlchemy 不做 diff）。本仓**不做迁移**
     （没有 Alembic，也不打算有），故 **schema 改动 = 重建库**：已有的 ``backend/pe.db``
     必须删掉重新跑 ``python -m app.seed.generate``，否则新增的列/索引/约束在旧库上
     **完全不存在**，而读写旧库的代码会以「列不存在」或「查询变慢」的形式在离真因很远的
     地方炸开。``backend/pe.db`` 不入库（``.gitignore``），故这一条对版本控制没有影响，
     只影响本地已经生成过库的人。两个 CLI 都**没有** ``--recreate`` 开关：删文件比重建
     索引更诚实，而一个「帮你把库删了」的开关本身就是危险动作。
     """
-    from app.db import models  # noqa: F401  仅为把 14 张表注册进 Base.metadata
+    from app.db import models  # noqa: F401  仅为把 15 张表注册进 Base.metadata
 
     Base.metadata.create_all(eng)
diff --git a/backend/app/domain/prescription/__init__.py b/backend/app/domain/prescription/__init__.py
new file mode 100644
index 0000000..9403fd3
--- /dev/null
+++ b/backend/app/domain/prescription/__init__.py
@@ -0,0 +1,37 @@
+"""``app.domain.prescription`` 的公开面：从这里重导出，消费者不必记住内部模块划分。
+
+计划的 File Structure 把本文件列为「公开面重导出」（Plan02 账本 P2-B1 指出原文没有任何
+Task 的 Files 段认领它，而没有它这个包不成立，故归 Task 2）。
+
+**逐 Task 递增**：Task 2 重导出 :mod:`~app.domain.prescription.exercises` 的 **7** 个名字
+（Ruling 96 把动作库的值对象搬进 domain 之后，``ImpactLevel`` 也改成从 ``exercises`` 取——
+唯一所有者在那边。本文件刻意**不从 ``templates`` 的 re-export 再 re-export**：那会让
+「谁是所有者」在导入图上看不出来）。Task 3 往 ``templates.py`` / ``match.py`` 加东西、
+Task 5-9 各自建自己的模块时，请同步往这里与 ``__all__`` 追加——两处必须一起改，否则
+``__all__`` 会谎报公开面。
+
+⚠️ **重导出不等于所有**（硬规矩 #39）：从这里 import 得到一个名字，不代表它的**取值**由
+本包决定。``TARGET_DOMAIN`` 的值来自 :data:`app.domain.indicators.ITEM_BUCKET`，
+``EQUIVALENCE_TRIGGERS`` 的取值域抄自 spec §7.4 ``:508-509``，``IMPACT_RANK`` 的秩序是
+「冲击由高到低」的显式声明（``ImpactLevel`` 继承 ``str``、自己不带这个序）。本文件只搬运
+名字，不搬运所有权。
+"""
+from .exercises import (
+    EQUIVALENCE_TRIGGERS,
+    IMPACT_RANK,
+    TARGET_DOMAIN,
+    EquivalenceMapping,
+    EquivalenceTable,
+    ExerciseSpec,
+    ImpactLevel,
+)
+
+__all__ = [
+    "EQUIVALENCE_TRIGGERS",
+    "IMPACT_RANK",
+    "TARGET_DOMAIN",
+    "EquivalenceMapping",
+    "EquivalenceTable",
+    "ExerciseSpec",
+    "ImpactLevel",
+]
diff --git a/backend/app/domain/prescription/exercises.py b/backend/app/domain/prescription/exercises.py
new file mode 100644
index 0000000..45f483f
--- /dev/null
+++ b/backend/app/domain/prescription/exercises.py
@@ -0,0 +1,200 @@
+"""动作库与低冲击等价映射表的**值对象**（Plan 02 Task 2；Ruling 96 自加载器迁入 domain）。
+
+**为什么住 domain、而不是与唯一的加载器同住**（Plan02 账本 Ruling 96）：照抄本仓既有的
+同构先例——``StandardTable`` 这个值类型住 :mod:`app.domain.tables`，解析 CSV 的加载器
+``load_standard()`` / ``standard()`` 住 :mod:`app.refdata`，而 ``app/refdata.py:29`` 写的是
+``from app.domain.tables import StandardTable``。即「**值类型住 domain、加载器住 domain
+外、加载器 import 值类型**」。本模块就是那一层值类型：``exercises.yaml`` 与
+``exercise_equivalence.yaml`` 的解析与校验住在 :mod:`app.refdata_prescription`，解析出来
+的东西就是这里的四个不可变对象与三张词表。
+
+**搬迁的直接动因不是审美**：:mod:`tests.architecture.test_domain_purity` 的 allow-list
+**不放行 ``app.domain`` → 非 ``app.domain`` 的 import**。值对象若留在加载器模块里，Task 7
+的 ``app/domain/prescription/safety.py`` 就**拿不到这三个类型做标注**，而 spec §7.4 的等价
+替换恰恰要调 :meth:`EquivalenceTable.lookup`——它只能按 duck typing 接，于是「传进来的到底
+是不是一张等价表」在类型层面看不出来。
+
+**不读盘**（Global Constraint #1）：本模块的 import 只有 ``enum`` / ``dataclasses`` /
+``collections.abc`` 与 ``app.domain.indicators``，四者都在上面那道 allow-list 内（亲跑
+``_is_allowed``：三个标准库串命中 :data:`ALLOWED_MODULES`，第四个命中前缀
+``app.domain.``）。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手，
+结果就可复现、可追溯（spec §1.3）。
+
+**``ImpactLevel`` 为什么也住在这里、而不是留在 ``templates.py``**（Ruling 96 ③）：它是
+``ExerciseSpec.impact_level`` 的类型、也是 :data:`IMPACT_RANK` 的键类型，留在
+``templates.py`` 会让本模块反向依赖模板模块；而**依赖方向恰恰相反**——Task 3 的模板
+dataclass 会带 ``exercise_ref`` 与 ``impact_level`` 两个字段，即模板引用动作库、动作库不
+引用模板。故 ``templates.py`` 改成从本模块 import 并 re-export 它（保持既有导入面，口径照
+``app/pipeline/run_stratify.py:50-57`` 那次同类搬迁）。
+
+⚠️ **本模块守不住什么**（硬规矩 #39）：它只**承载**值、不校验值。「``exercises.yaml`` 里
+每个 ``impact_level`` 都在词表内」「每条映射声明的 ``max_impact`` 与 ``to_ref`` 的真实冲击
+一致」「每个 ``targets`` 都落在 :data:`TARGET_DOMAIN` 里」——这些校验全部住在加载器
+:mod:`app.refdata_prescription` 与 ``tests/test_refdata_prescription.py`` 里。**直接构造**
+:class:`ExerciseSpec`（绕过加载器）可以得到一个 ``targets`` 为空、``impact_level`` 拼错的
+对象，本模块不拦，也没有任何一条测试会红。
+"""
+from collections.abc import Mapping
+from dataclasses import dataclass
+from enum import Enum
+
+from app.domain.indicators import ITEM_BUCKET
+
+
+class ImpactLevel(str, Enum):
+    """spec §4.4 ``:239`` 的 ``exercise.impact_level`` 取值域：``high`` / ``medium`` / ``low``。
+
+    **继承 ``str``**：``exercise.impact_level`` 那一列是 ``String(8)``，继承 ``str`` 之后
+    ``ImpactLevel.HIGH == "high"`` 直接成立，落库与读回都是同一个字符串，不必在 ORM 边界
+    上处处写 ``.value``。漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()``
+    存成 ``"ImpactLevel.HIGH"``（19 字符，还撑破 ``String(8)``——SQLite 不强制长度，故
+    写侧不报错，换严格长度的后端才截断，硬规矩 #18 的那个失效形态）。
+
+    ⚠️ **它不携带序**：继承 ``str`` 意味着 ``<`` 是**字典序**，即
+    ``ImpactLevel.HIGH < ImpactLevel.LOW < ImpactLevel.MEDIUM``，与「冲击由高到低」完全
+    无关。冲击序由消费方显式声明，今天有两份、刻意不同源（硬规矩 #35）：生产侧是
+    **本模块**的 :data:`IMPACT_RANK`（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
+    :mod:`app.refdata_prescription`），测试侧
+    ``tests/test_refdata_prescription.py`` 的 ``IMPACT_DESCENDING``。改坏任何一份都会让
+    ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红。
+
+    **谁是这个值的所有者**（Plan02 账本 P2-B2，Global Constraint #3）：本枚举是**词表**
+    的所有者（有哪三档），而**每个动作具体是哪一档**的唯一所有者是
+    ``backend/data/exercises.yaml``。spec §7.2 ``:470-471`` 的模板 YAML 字面形状里每个
+    block 也自带一份 ``impact_level``，那是**副本**：Task 3 的模板加载器必须校验
+    「block 的 ``impact_level`` == 动作库里的值」，不一致就在加载时响亮失败。
+    """
+
+    HIGH = "high"
+    MEDIUM = "medium"
+    LOW = "low"
+
+
+#: ``targets`` 的取值域：``ITEM_BUCKET`` 的三个桶名。
+#: ⚠️ **不是 ``set(ITEM_BUCKET.values())``**（Plan02 账本 P2-A4）：那个集合有 **4** 个元素、
+#: 含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶，
+#: Plan01 Ruling 19 的口径），照字面写会把 ``None`` 放进取值域、并让一个空 ``targets``
+#: 悄悄合法。由 ``tests/test_refdata_prescription.py`` 的
+#: ``test_target_domain_is_the_three_bucket_names_not_the_raw_values`` 钉住这个构造方式。
+TARGET_DOMAIN: frozenset[str] = frozenset(
+    bucket for bucket in ITEM_BUCKET.values() if bucket is not None
+)
+
+
+#: spec §7.4 ``:508-509`` 里**走等价表**的两个触发条件（``when`` 的取值域）。
+#: ``:510`` 的第三个触发（体脂率异常）走的是「追加模板 ``addons`` 中的能量消耗模块」、
+#: **不查等价表**，故它不在这里（Plan02 账本 P2-C3 亲验）。
+EQUIVALENCE_TRIGGERS: frozenset[str] = frozenset({"bmi_over_30", "muscle_low_p10"})
+
+
+#: 冲击等级的**降序**排名（0 = 冲击最高）。
+#: ⚠️ 不能靠 ``ImpactLevel`` 的比较得出序：它继承 ``str``，``<`` 是字典序
+#: （``"high" < "low" < "medium"``），与冲击序无关。测试侧另有一份**字面写死**的
+#: ``IMPACT_DESCENDING``（``tests/test_refdata_prescription.py``），两份刻意不同源
+#: （硬规矩 #35）：改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level``
+#: 与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
+#: 之一会红。
+#:
+#: **改名（Ruling 96）**：搬进 domain 之前它叫 ``_IMPACT_RANK``、住在
+#: :mod:`app.refdata_prescription`。前导下划线在那里表示「本模块私有」；搬进来之后它是
+#: domain 公开面的一部分（``app/domain/prescription/__init__.py`` 重导出它），而跨模块
+#: import 一个带前导下划线的名字自相矛盾，故去掉下划线。**秩值一个未改**（0=high、
+#: 2=low），改的是名字与住址。
+IMPACT_RANK: dict[ImpactLevel, int] = {
+    ImpactLevel.HIGH: 0,
+    ImpactLevel.MEDIUM: 1,
+    ImpactLevel.LOW: 2,
+}
+
+
+@dataclass(frozen=True)
+class ExerciseSpec:
+    """``exercises.yaml`` 的一个条目。
+
+    ``ref`` 是 ``exercise_ref`` 的**唯一所有者**（Global Constraint #3）：模板 YAML 与
+    ``exercise_equivalence.yaml`` 都按它引用动作，而它的键集就住在那份 YAML 的顶层键上。
+    Task 3 的模板加载器必须校验「每个 ``exercise_ref`` 都在动作库里」，违例在加载时响亮
+    失败（Review Focus 第 1 条）。
+
+    ``impact_level`` 同样是单一所有者（Plan02 账本 P2-B2）：**本字段是「这个动作是哪一档
+    冲击」的唯一真相**。spec §7.2 ``:470-471`` 的模板 YAML 字面形状里每个 block 也自带一份
+    ``impact_level``，那是**副本**；**负责校验一致的是 Task 3 的模板加载器**（不一致就在
+    加载时响亮失败，与 ``exercise_ref`` 的处置同构）——加载器
+    :mod:`app.refdata_prescription` 只加载动作库、看不到模板，故校验不住这件事，
+    这一点必须写明（硬规矩 #39）。
+
+    ``targets`` 是 ``frozenset``：一个动作可以同时瞄准多个素质桶（如折返跑既是耐力也是
+    速度），而桶的**顺序不承重**（Task 4 的匹配按主导短板桶查，不按序）。用 ``frozenset``
+    而不是 ``tuple`` 正是为了在类型上排除「顺序有意义」这个误读。
+    """
+
+    ref: str
+    name: str
+    video_url: str
+    impact_level: ImpactLevel
+    targets: frozenset[str]
+    equipment: str
+
+
+@dataclass(frozen=True)
+class EquivalenceMapping:
+    """``exercise_equivalence.yaml`` 的 ``mappings`` 里的一条。
+
+    ``from_ref`` 是被替换的动作（今天全是 ``high`` 冲击），``to_ref`` 是替身，
+    ``max_impact`` 是这条映射**自己声明**的替身冲击上限，``when`` 是触发条件。
+
+    ``max_impact`` 与 ``to_ref`` 的真实冲击必须一致——:meth:`EquivalenceTable.lookup`
+    是按 ``max_impact`` 过滤的、**不看动作库**，故一张撒谎的表会让 lookup 返回一个冲击
+    高于上限的动作。这条一致性由
+    ``tests/test_refdata_prescription.py::test_equivalence_never_maps_to_a_higher_impact_level``
+    钉住（它同时验「不升冲击」与「声明与真实一致」两件事）。
+    """
+
+    from_ref: str
+    to_ref: str
+    max_impact: ImpactLevel
+    when: str
+
+
+@dataclass(frozen=True)
+class EquivalenceTable:
+    """一张完整的低冲击等价映射表（spec §4.4 ``:243``：静态 YAML + **版本号**，不入库）。
+
+    ``version`` 会被 Task 7 写进 ``prescription.safety_substitutions``（spec §7.4 ``:512``
+    要求记录「原动作、新动作、触发条件、**映射表版本号**」），于是一张已生成的处方能回答
+    「当时是按哪一版映射表替换的」。
+
+    ``volume_reduction`` 的两个系数是「跑量按映射表下调」（spec §7.4 ``:508-509``）的
+    具体数值。⚠️ **它们在 spec 里没有出处**（Plan02 账本 P2-A3）：``:508`` 只写「按映射表
+    下调」、没给任何数，``:509`` 写「同上」。spec 里唯一出现的「系数 0.8」在 ``:604``，
+    那是**预警触发的减量 20%**（``weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)``，
+    属 Plan 03），与本表的跑量下调是**两个不同机制**；``0.9`` 在 spec 里根本没有对应物。
+    故这两个数是**本设计的默认规定**，已登记进 ``exercise_equivalence.yaml`` 的注释与
+    spec §14 第 28 项；**Task 7 消费时不得把它们当成 spec 条文引用**。
+    """
+
+    version: str
+    mappings: tuple[EquivalenceMapping, ...]
+    volume_reduction: Mapping[str, float]
+
+    def lookup(self, ref: str, impact_ceiling: ImpactLevel) -> str | None:
+        """``ref`` 在冲击不超过 ``impact_ceiling`` 的前提下的替身；查不到返回 ``None``。
+
+        返回 ``None`` **不是**「静默跳过」：spec §7.4 ``:514`` 明写「安全规则命中但映射表
+        找不到等价动作时，不静默跳过」——生成 ``warning`` 级日志、处方状态置
+        ``needs_review``、教师端标记「需人工复核」。故 Task 7 拿到 ``None`` 必须走那条路径
+        （Review Focus 第 5 条），而不是把原动作留在训练包里。
+
+        命中条件是 ``IMPACT_RANK[max_impact] >= IMPACT_RANK[impact_ceiling]``，即映射
+        声明的上限**不高于**调用方给的上限。取**第一条**命中者：``mappings`` 的顺序就是
+        YAML 里的书写顺序（:func:`~app.refdata_prescription.load_equivalence` 不重排），
+        故专家可以通过调整书写顺序来
+        表达偏好，而不必引入一个额外的优先级字段。
+        """
+        ceiling_rank = IMPACT_RANK[impact_ceiling]
+        for mapping in self.mappings:
+            if mapping.from_ref != ref:
+                continue
+            if IMPACT_RANK[mapping.max_impact] >= ceiling_rank:
+                return mapping.to_ref
+        return None
diff --git a/backend/app/domain/prescription/templates.py b/backend/app/domain/prescription/templates.py
new file mode 100644
index 0000000..4a1be65
--- /dev/null
+++ b/backend/app/domain/prescription/templates.py
@@ -0,0 +1,39 @@
+"""处方模板的**数据结构**与维度词表（Plan 02：Task 2 建、Task 3 填）。
+
+⚠️ **本模块今天没有任何自己的定义**（Plan02 账本 Ruling 96）：Task 2 原来放在这里的
+:class:`~app.domain.prescription.exercises.ImpactLevel` 已迁往
+:mod:`app.domain.prescription.exercises`，本文件只剩一句 re-export 与一个 ``__all__``。
+**为什么迁走**：``ImpactLevel`` 是 ``ExerciseSpec.impact_level`` 与 ``IMPACT_RANK`` 的类型，
+留在本模块会让 ``exercises.py`` 反向 import 本模块；而依赖方向恰恰相反——Task 3 要往这里
+加的模板 dataclass 会带 ``exercise_ref`` 与 ``impact_level`` 两个字段，即**模板引用动作库、
+动作库不引用模板**。File Structure 说本模块是「模板的数据结构与维度词表」，Ruling 96 之后
+「**动作库**的维度词表」那一半归 ``exercises.py``，本模块留「模板的数据结构」（Task 3）
+与模板自己要用的维度词表。
+
+**re-export 的口径**（照 ``app/pipeline/run_stratify.py:50-57`` 那次同类搬迁）：
+``ImpactLevel`` 的**唯一所有者**是 :mod:`app.domain.prescription.exercises`，本模块只是
+保持既有导入面——``app.domain.prescription.templates.ImpactLevel`` 照旧可用，故 Task 2
+写下的 ``from app.domain.prescription.templates import ImpactLevel`` 不会一夜之间变成
+ImportError。**新代码请直接从 ``exercises`` 导入**（本轮已把
+``tests/test_refdata_prescription.py`` 的 import 改过去了；
+``tests/domain/test_prescription_templates.py`` 刻意**保留**从本模块导入——那是本模块
+今天唯一的导入方，也是这 2 条语句进 domain 覆盖率统计的唯一途径）。``__all__`` 里列着它，
+是为了让这次 re-export 是一次**显式**声明，而不是「碰巧留在命名空间里」：没有 ``__all__``，
+下一个人会以为它本模块私有、可放心改名。
+
+**Task 3 注意**：往本文件加模板 dataclass 时，请同步
+``app/domain/prescription/__init__.py`` 的公开面——那里的 ``__all__`` 与本模块的
+``__all__`` 是两份，必须一起改，否则公开面谎报。
+
+**为什么不读盘**（Global Constraint #1）：``app/domain/`` 是无 I/O 的纯函数叶子层，
+YAML 的解析与校验住在 :mod:`app.refdata_prescription`，解析结果作为**参数**注入 domain
+的纯函数。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手结果就可
+复现、可追溯（spec §1.3）。这条由 :mod:`tests.architecture.test_domain_purity` 的
+allow-list 守卫机器可查地钉住：domain 只允许 import 6 个标准库模块串（``dataclasses`` /
+``enum`` / ``collections`` / ``collections.abc`` / ``numpy`` / ``typing``）与 ``app.domain``
+前缀；本模块今天只 import 了同包的 ``exercises``（相对导入 ``level == 1``，被那道守卫折算
+成 ``app.domain.prescription.exercises``、命中前缀那一项）。
+"""
+from .exercises import ImpactLevel
+
+__all__ = ["ImpactLevel"]
diff --git a/backend/app/refdata.py b/backend/app/refdata.py
index 95d3f57..b1415eb 100644
--- a/backend/app/refdata.py
+++ b/backend/app/refdata.py
@@ -1,23 +1,31 @@
 """参考数据加载：全项目唯一允许读 ``backend/data/*.csv`` 的模块。
 
 依赖方向是 refdata → domain：这里把 CSV 解析成 app/domain/tables.py 的
 StandardTable，再交给 domain 的纯函数使用；进程内缓存也放在这里而不是 domain。
 domain 因此保持为无 I/O 的叶子（Ruling 15），不会隐式依赖磁盘上某个 CSV 是否存在。
 
-本模块同时是 ``backend/data/`` 下**文件名与目录**的唯一所有者：``BACKEND_DIR`` 取自
-:mod:`app.config`（叶子，只 import ``pathlib``，故 refdata → config 不可能造出环），
-``DATA_DIR`` / ``STANDARD_FILENAME`` / ``RANGES_FILENAME`` 都住在这里。
+本模块是 ``backend/data/`` 这个**目录常量**与**国标评分表 / 指标区间表两个文件名**的唯一
+所有者：``BACKEND_DIR`` 取自 :mod:`app.config`（叶子，只 import ``pathlib``，故
+refdata → config 不可能造出环），``DATA_DIR`` / ``STANDARD_FILENAME`` /
+``RANGES_FILENAME`` 都住在这里。
+
 ``RANGES_FILENAME`` 原先住在 ``app/seed/generate.py``，于是生产层为了拿一个**文件名字符串**
 必须 import 仿真数据生成器（基线 ``e26347f`` 的 ``app/pipeline/run_stratify.py:49``）；
 搬到这里之后 ``pipeline → seed`` 那条边消失，且它与 ``DATA_DIR`` 住在同一个模块里，
 「哪个文件在哪个目录」这件事不必再跨两个模块拼。
+
+⚠️ **处方侧那两个 YAML 的文件名不住这里**（Plan 02 Task 2）：``EXERCISES_FILENAME`` 与
+``EQUIVALENCE_FILENAME`` 住在 :mod:`app.refdata_prescription`，与它们唯一的加载器同处一个
+模块。理由是 ``DATA_DIR`` 这一份仍然是唯一的（那边从本模块 import 它），而「哪个文件在
+哪个目录」这件事已经由 ``DATA_DIR`` 回答完了；把两个本模块从不加载的文件名也搬进来，只会
+让 ``app/refdata.py`` 承担一份处方侧的知识。
 """
 import csv
 import pathlib
 import types
 
 from app.config import BACKEND_DIR
 from app.domain.indicators import AGE_GROUPS, ScoredItem, Sex, segment_thresholds
 from app.domain.tables import StandardTable
 
 DATA_DIR = BACKEND_DIR / "data"
diff --git a/backend/app/refdata_prescription.py b/backend/app/refdata_prescription.py
new file mode 100644
index 0000000..c4a5600
--- /dev/null
+++ b/backend/app/refdata_prescription.py
@@ -0,0 +1,406 @@
+"""处方侧参考数据（``backend/data/`` 下的 YAML）的加载、校验与 ``exercise`` 表投影。
+
+**本模块分两段**（Plan02 账本 P2-B3：File Structure 只说它「加载 18 套模板 YAML 与
+``exercise_equivalence.yaml``」，漏了 ``exercises.yaml``，故把分段写在这里，免得 Task 3
+重写整个 docstring）：
+
+===========================  =========  ======================================
+段                            归属 Task   内容
+===========================  =========  ======================================
+动作库 + 等价映射表           **Task 2**  ``exercises.yaml`` / ``exercise_equivalence.yaml``
+                                          的加载器与 ``sync_exercises``（值对象自 Ruling 96
+                                          起住 ``app/domain/prescription/exercises.py``）
+18 套处方模板                 Task 3      ``data/prescription/*.yaml`` 的加载器与校验
+===========================  =========  ======================================
+
+依赖方向与 :mod:`app.refdata` 相同：refdata_prescription → domain（把 YAML 解析成值对象
+再交给 domain 的纯函数），domain 因此保持为无 I/O 的叶子（Global Constraint #1），不会
+隐式依赖磁盘上某个 YAML 是否存在。``DATA_DIR`` 取自 :mod:`app.refdata`（它取自
+:mod:`app.config`），本模块只新增**处方侧那两个 YAML 的文件名**。
+
+⚠️ **值对象不住在这里**（Plan02 账本 Ruling 96；Task 2 fix round 1 搬迁）：
+:class:`~app.domain.prescription.exercises.ExerciseSpec` /
+:class:`~app.domain.prescription.exercises.EquivalenceMapping` /
+:class:`~app.domain.prescription.exercises.EquivalenceTable` 三个值对象，连同
+``ImpactLevel`` 与三张词表（``IMPACT_RANK`` / ``TARGET_DOMAIN`` /
+``EQUIVALENCE_TRIGGERS``），都住在 :mod:`app.domain.prescription.exercises`；本模块从
+那里 import 它们，只负责**加载**。**为什么必须搬**：
+:mod:`tests.architecture.test_domain_purity` 的 allow-list 只放行 6 个标准库模块串
+（``dataclasses`` / ``enum`` / ``collections`` / ``collections.abc`` / ``numpy`` /
+``typing``）与 ``app.domain`` 前缀，**不放行 domain → 非 domain 的 import**。值对象若住
+在这里，Task 7 的 ``app/domain/prescription/safety.py`` 就拿不到这三个类型做标注，而
+spec §7.4 的等价替换恰恰要调 ``EquivalenceTable.lookup()``。**分层照抄本仓既有先例**：
+``StandardTable`` 这个值类型住 :mod:`app.domain.tables`，解析 CSV 的 ``load_standard()``
+/ ``standard()`` 住 :mod:`app.refdata`（``app/refdata.py:29`` 写的是
+``from app.domain.tables import StandardTable``）。
+
+**代价要写明**（硬规矩 #39）：搬进 domain 之后，这些值对象从此受 **domain 分支覆盖
+100%** 约束（Global Constraint #2），而 :meth:`~app.domain.prescription.exercises.EquivalenceTable.lookup`
+的分支今天**全部由 ``tests/test_refdata_prescription.py`` 覆盖**——即一条 domain 代码的
+覆盖率住在 domain 测试目录之外。删那条测试里的任何一个 ``lookup`` 断言，红的不是它自己，
+是 ``--cov=app/domain --cov-branch`` 的 BrPart。
+
+**本模块同时是 ``exercise`` 表的灌数据入口**（:func:`sync_exercises`）。它刻意**不在**
+``app/seed/``：Plan02 账本 P2-A1 的裁定，理由有三——① Global Constraint #10 把
+``app/seed/`` 自 Plan 01 结案后重新冻结；② ``seed_database`` 的 docstring 明写它「**只**写
+组织结构五张表」，而 ``tests/seed/test_generate.py`` 的
+``test_seed_database_writes_only_organisation_tables_and_is_idempotent`` 把这句话变成了守卫；
+③ ``exercise`` 是**参考数据**、不是仿真人口数据，与 ``app/seed/`` 的职责本就不同类，它的
+同类是 :mod:`app.refdata`。
+"""
+import pathlib
+import re
+import types
+from collections.abc import Mapping
+
+import yaml
+from sqlalchemy.orm import Session
+
+from app.db.models.prescription import Exercise
+from app.db.repo import upsert
+from app.domain.prescription.exercises import (
+    EQUIVALENCE_TRIGGERS,
+    TARGET_DOMAIN,
+    EquivalenceMapping,
+    EquivalenceTable,
+    ExerciseSpec,
+    ImpactLevel,
+)
+from app.refdata import DATA_DIR
+
+#: 动作库的**源**（``exercise`` 表由它投影）。``exercise_ref`` 与每个动作的
+#: ``impact_level`` 都以这份文件的键集/字段为**唯一所有者**（Global Constraint #3）。
+EXERCISES_FILENAME = "exercises.yaml"
+
+#: 低冲击等价动作映射 + 映射表版本号 + 跑量下调系数。spec §4.4 ``:243`` 明写它与
+#: ``alert_rules`` 一样是「``data/`` 下的**静态 YAML + 版本号**，不入库」。
+EQUIVALENCE_FILENAME = "exercise_equivalence.yaml"
+
+#: 每个动作必需的键，恰好这五个（多一个少一个都在加载时响亮失败）。
+_EXERCISE_KEYS = ("name", "video_url", "impact_level", "targets", "equipment")
+
+#: 每条等价映射必需的键。``from`` / ``to`` / ``max_impact`` / ``when`` 的字面形状取自
+#: 计划 Task 2 Step 3。
+_MAPPING_KEYS = ("from", "to", "max_impact", "when")
+
+#: ``exercise_ref`` 的形状：小写字母开头，后续只允许小写字母 / 数字 / 下划线。
+#: 收紧形状的理由是它是**跨文件的引用键**（模板 YAML 与等价表都按它引用），一个大小写
+#: 混用的 ref 在 YAML 里看不出问题，而 Windows 的文件系统大小写不敏感、Linux 敏感，
+#: 将来若有人按 ref 找文件就会在两个平台上表现不同。
+_REF_SHAPE = re.compile(r"[a-z][a-z0-9_]*")
+
+_exercises_cache: Mapping[str, ExerciseSpec] | None = None
+_equivalence_cache: EquivalenceTable | None = None
+
+
+def _exercise_spec(path: pathlib.Path, ref: object, entry: object) -> ExerciseSpec:
+    """校验并构造一个 :class:`ExerciseSpec`，违例带**文件名 + ref + 字段名**响亮失败。
+
+    ⚠️ **报错点不出 YAML 行号**（硬规矩 #39：写下守卫能力时必须写明它守不住什么）：
+    ``yaml.safe_load`` 不保留位置信息，要行号得改用 ``yaml.compose`` 逐节点读
+    ``start_mark``。本 Task 不做——Review Focus 第 1 条对「哪个文件哪一行」的要求是针对
+    **18 套模板 YAML**（Task 3）的，那边一个文件一套模板、行号是定位的唯一手段；动作库
+    是**单文件多条目**，``ref`` 就足以定位到那 6 行。
+    """
+    if not isinstance(ref, str) or _REF_SHAPE.fullmatch(ref) is None:
+        raise ValueError(
+            f"动作库 {path} 的动作 ref {ref!r} 形状非法：只允许小写字母开头、"
+            f"后续为小写字母/数字/下划线（正则 {_REF_SHAPE.pattern}）"
+        )
+    if not isinstance(entry, dict):
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 应为「属性名 → 值」的映射，"
+            f"实为 {type(entry).__name__}"
+        )
+    missing = [key for key in _EXERCISE_KEYS if key not in entry]
+    if missing:
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 缺键 {missing}；必需的键恰好是 {list(_EXERCISE_KEYS)}"
+        )
+    unexpected = sorted(set(entry) - set(_EXERCISE_KEYS))
+    if unexpected:
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 有多余的键 {unexpected}；必需的键恰好是 "
+            f"{list(_EXERCISE_KEYS)}。多余的键会被静默忽略，而它通常意味着改名后忘了删"
+            f"旧的那一个——例如把 equipment 改写成 equipments，读到的就永远是旧值"
+        )
+
+    name = entry["name"]
+    if not isinstance(name, str) or not name.strip():
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 name 应为非空字符串（学生端要显示它），实为 {name!r}"
+        )
+    video_url = entry["video_url"]
+    if not isinstance(video_url, str) or not video_url.strip():
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 video_url 应为非空字符串"
+            f"（spec §7.3 :499 的装配第 5 步会把它填进训练包的二维码），实为 {video_url!r}"
+        )
+    equipment = entry["equipment"]
+    if not isinstance(equipment, str) or not equipment.strip():
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 equipment 应为非空字符串"
+            f"（无器械请写 none 而不是留空：留空分不清「不需要器械」与「忘了填」），"
+            f"实为 {equipment!r}"
+        )
+    try:
+        impact_level = ImpactLevel(entry["impact_level"])
+    except ValueError:
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 impact_level 值非法: {entry['impact_level']!r}；"
+            f"合法值: {[level.value for level in ImpactLevel]}（spec §4.4 :239）。"
+            f"拼错的档位不会被 spec §7.4 的安全后置识别成 high，"
+            f"BMI > 30 的学生会照旧被安排高冲击动作，而全链路没有一处报错"
+        ) from None
+    targets_raw = entry["targets"]
+    if not isinstance(targets_raw, list) or not targets_raw:
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 targets 应为**非空**列表，实为 {targets_raw!r}："
+            f"一个不瞄准任何素质桶的动作无法被 18 套模板中的任何一套选用"
+        )
+    unknown = [bucket for bucket in targets_raw if bucket not in TARGET_DOMAIN]
+    if unknown:
+        raise ValueError(
+            f"动作库 {path} 的 {ref} 的 targets 含非桶名 {unknown}；"
+            f"合法值: {sorted(TARGET_DOMAIN)}（来自 app.domain.indicators.ITEM_BUCKET 的"
+            f"三个桶名；⚠️ bmi 不是桶名——BMI 不归任何短板桶，ITEM_BUCKET[BMI] is None）"
+        )
+    return ExerciseSpec(
+        ref=ref,
+        name=name,
+        video_url=video_url,
+        impact_level=impact_level,
+        targets=frozenset(targets_raw),
+        equipment=equipment,
+    )
+
+
+def load_exercises(path: pathlib.Path | None = None) -> Mapping[str, ExerciseSpec]:
+    """读取动作库 YAML 并构造「``exercise_ref`` → :class:`ExerciseSpec`」的只读映射。
+
+    顶层结构是**以 ref 为键的映射**（不是一个列表）：这样「``exercise_ref`` 的唯一所有者
+    是 ``exercises.yaml`` 的**键集**」这句话在文件形状上就成立，而不必靠「列表里每项有个
+    ``ref`` 字段、且它们互不重复」这条需要额外校验的约定。
+
+    ⚠️ **PyYAML 对重复的顶层键是后者覆盖前者、不报错**（实测
+    ``yaml.safe_load("a: 1\\na: 2") == {"a": 2}``），故「专家复制一段忘了改 ref」会让一个
+    动作**静默消失**。本函数看不出来（它拿到的已经是覆盖后的 dict），守卫在
+    ``tests/test_refdata_prescription.py::test_exercise_refs_are_snake_case_and_unique_keys``
+    ——那条用**原始文本**数一遍顶层键、与解析结果对账，两侧不同源。
+
+    ``path`` 缺省为 ``DATA_DIR / EXERCISES_FILENAME``；文件不存在抛 ``FileNotFoundError``。
+    返回 :class:`types.MappingProxyType`：``frozen=True`` 只挡住换掉整个字段，挡不住
+    ``library[ref] = ...`` 的就地改写，而 :func:`exercises` 是进程内共享单例，一次误写会
+    让之后所有装配静默变质（与 ``StandardTable.segments`` 同一处置，见
+    :func:`app.refdata.load_standard` 的 docstring）。底层 dict 是本函数的局部变量、
+    不外泄，故这个只读视图是有效的。
+
+    **返回类型标注是 ``Mapping`` 而不是计划里写的 ``dict``**：运行时对象是
+    ``MappingProxyType``，它**不是** ``dict`` 的实例（``isinstance(MappingProxyType({}),
+    dict)`` 为 ``False``），标 ``dict`` 会是一个假标注。这与 ``StandardTable.segments``
+    声明为 ``Mapping[...]``、由加载方装入 ``MappingProxyType`` 的既有口径一致。
+    """
+    yaml_path = DATA_DIR / EXERCISES_FILENAME if path is None else pathlib.Path(path)
+    if not yaml_path.is_file():
+        raise FileNotFoundError(f"动作库缺失: {yaml_path}")
+    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
+    if raw is None:
+        raise ValueError(
+            f"动作库 {yaml_path} 为空：Task 3 的 18 套模板将没有任何 exercise_ref 可引"
+        )
+    if not isinstance(raw, dict):
+        raise ValueError(
+            f"动作库 {yaml_path} 的顶层结构应为「exercise_ref → 属性映射」，"
+            f"实为 {type(raw).__name__}"
+        )
+    library = {ref: _exercise_spec(yaml_path, ref, entry) for ref, entry in raw.items()}
+    return types.MappingProxyType(library)
+
+
+def exercises() -> Mapping[str, ExerciseSpec]:
+    """进程内单例：动作库是只读参考数据，一个进程加载一次即可。
+
+    与 :func:`app.refdata.standard` 同口径（Plan02 账本 P2-A9：``load_standard`` 只负责
+    加载、**不缓存**，单例是另一个函数）。
+    """
+    global _exercises_cache
+    if _exercises_cache is None:
+        _exercises_cache = load_exercises()
+    return _exercises_cache
+
+
+def _equivalence_mapping(
+    path: pathlib.Path, index: int, item: object
+) -> EquivalenceMapping:
+    """校验并构造一条 :class:`EquivalenceMapping`，违例点名文件与是第几条。"""
+    if not isinstance(item, dict):
+        raise ValueError(
+            f"等价映射表 {path} 的 mappings[{index}] 应为映射，实为 {type(item).__name__}"
+        )
+    missing = [key for key in _MAPPING_KEYS if key not in item]
+    if missing:
+        raise ValueError(
+            f"等价映射表 {path} 的 mappings[{index}] 缺键 {missing}；"
+            f"必需的键恰好是 {list(_MAPPING_KEYS)}"
+        )
+    unexpected = sorted(set(item) - set(_MAPPING_KEYS))
+    if unexpected:
+        raise ValueError(
+            f"等价映射表 {path} 的 mappings[{index}] 有多余的键 {unexpected}；"
+            f"必需的键恰好是 {list(_MAPPING_KEYS)}"
+        )
+    for key in ("from", "to"):
+        value = item[key]
+        if not isinstance(value, str) or not value.strip():
+            raise ValueError(
+                f"等价映射表 {path} 的 mappings[{index}] 的 {key} 应为非空的 exercise_ref，"
+                f"实为 {value!r}"
+            )
+    when = item["when"]
+    if when not in EQUIVALENCE_TRIGGERS:
+        raise ValueError(
+            f"等价映射表 {path} 的 mappings[{index}]"
+            f"（{item['from']} → {item['to']}）的 when 值非法: {when!r}；"
+            f"合法值: {sorted(EQUIVALENCE_TRIGGERS)}——spec §7.4 :508-509 只有这两个触发"
+            f"走等价表，:510 的「体脂率异常」走模板 addons 的能量消耗模块、**不查本表**"
+        )
+    try:
+        max_impact = ImpactLevel(item["max_impact"])
+    except ValueError:
+        raise ValueError(
+            f"等价映射表 {path} 的 mappings[{index}] 的 max_impact 值非法: "
+            f"{item['max_impact']!r}；合法值: {[level.value for level in ImpactLevel]}"
+        ) from None
+    return EquivalenceMapping(
+        from_ref=item["from"],
+        to_ref=item["to"],
+        max_impact=max_impact,
+        when=when,
+    )
+
+
+def load_equivalence(path: pathlib.Path | None = None) -> EquivalenceTable:
+    """读取 ``exercise_equivalence.yaml`` 并构造 :class:`EquivalenceTable`。
+
+    校验顺序是 **version → volume_reduction → mappings**：前两个是**表级**属性（缺了整张
+    表就没法用），第三个是**条目级**的，逐条报错时要点名是第几条，故放最后。
+
+    ⚠️ **本函数不做跨文件校验**（硬规矩 #39）：它**不检查** ``from`` / ``to`` 是否真的在
+    动作库里，因为那会让「删掉 ``exercises.yaml`` 里一个没人引用的 ref」连带把等价表也
+    判成坏的，从而掩盖真正该红的那一条。跨文件不变量由
+    ``tests/test_refdata_prescription.py::test_equivalence_table_only_maps_to_existing_exercises``
+    守；若 Task 7 认为它必须在**加载时**而不是**测试时**被挡住，把校验加在这里即可，
+    届时要连带调整那条测试与简报 Step 5 的变异 ②（「只有指纹测试会红」将不再成立）。
+    """
+    yaml_path = DATA_DIR / EQUIVALENCE_FILENAME if path is None else pathlib.Path(path)
+    if not yaml_path.is_file():
+        raise FileNotFoundError(f"等价映射表缺失: {yaml_path}")
+    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
+    if not isinstance(raw, dict):
+        raise ValueError(
+            f"等价映射表 {yaml_path} 的顶层结构应为映射"
+            f"（version / mappings / volume_reduction 三个键），实为 {type(raw).__name__}"
+        )
+
+    version = raw.get("version")
+    if not isinstance(version, str) or not version.strip():
+        raise ValueError(
+            f"等价映射表 {yaml_path} 的 version 缺失或不是非空字符串，实为 {version!r}："
+            f"spec §7.4 :512 要求把**映射表版本号**写进 prescription.safety_substitutions，"
+            f"没有它一张已生成的处方就无法回答「当时是按哪一版映射表替换的」"
+        )
+
+    volume_reduction = raw.get("volume_reduction")
+    if not isinstance(volume_reduction, dict):
+        raise ValueError(
+            f"等价映射表 {yaml_path} 的 volume_reduction 缺失或不是映射，"
+            f"实为 {volume_reduction!r}：spec §7.4 :508-509 的两个触发都要求"
+            f"「跑量按映射表下调」，下调多少就住在这个键里"
+        )
+    if set(volume_reduction) != EQUIVALENCE_TRIGGERS:
+        raise ValueError(
+            f"等价映射表 {yaml_path} 的 volume_reduction 的键应恰好是 "
+            f"{sorted(EQUIVALENCE_TRIGGERS)}，实为 {sorted(volume_reduction)}"
+        )
+    for trigger, factor in sorted(volume_reduction.items()):
+        if not isinstance(factor, float) or not 0.0 < factor < 1.0:
+            raise ValueError(
+                f"等价映射表 {yaml_path} 的 volume_reduction[{trigger!r}] = {factor!r} "
+                f"不在 (0.0, 1.0) 内：> 1 是「安全触发反而加量」，<= 0 是把训练量清零、"
+                f"处方名存实亡"
+            )
+
+    if "mappings" not in raw:
+        raise ValueError(
+            f"等价映射表 {yaml_path} 缺 mappings 键：没有映射，spec §7.4 的"
+            f"「high 冲击动作换低冲击等价动作」就一条也做不了"
+        )
+    mappings_raw = raw["mappings"]
+    if not isinstance(mappings_raw, list):
+        raise ValueError(
+            f"等价映射表 {yaml_path} 的 mappings 应为列表，实为 {type(mappings_raw).__name__}"
+        )
+    return EquivalenceTable(
+        version=version,
+        mappings=tuple(
+            _equivalence_mapping(yaml_path, index, item)
+            for index, item in enumerate(mappings_raw)
+        ),
+        volume_reduction=types.MappingProxyType(dict(volume_reduction)),
+    )
+
+
+def equivalence() -> EquivalenceTable:
+    """进程内单例，与 :func:`exercises` 同口径。
+
+    本 Task 的四个函数里计划只点了 ``load_exercises`` / ``exercises`` / ``load_equivalence``
+    三个；补这一个是为了**对称**：Task 7 的安全后置是逐学生跑的，少了单例就会每人重解析
+    一次 YAML，而 spec §1.3 给单人处方生成的预算是 p95 < 3 秒。
+    """
+    global _equivalence_cache
+    if _equivalence_cache is None:
+        _equivalence_cache = load_equivalence()
+    return _equivalence_cache
+
+
+def sync_exercises(session: Session) -> int:
+    """把动作库投影进 ``exercise`` 表，返回写入的行数（幂等）。
+
+    按 ``ref`` 走 :func:`app.db.repo.upsert`：有则更新非键列、无则插入，故**重跑不翻倍**，
+    且 YAML 改了某个字段时那一行被**就地更新**而不是插出第二行。返回值恒等于动作库条目数
+    ——「写入行数」的口径是**本次 upsert 触及的行数**，不是「新插入的行数」；这样它对
+    首次灌库与重跑给出同一个数，调用方不必区分两种情况。
+
+    **本函数 flush 但不 commit**：事务边界由调用方掌握（与 :func:`app.db.repo.upsert`
+    同一口径）。flush 是必要的——``impact_level`` 的 CHECK 约束与 ``ref`` 的 UNIQUE 约束
+    只在真正执行 INSERT/UPDATE 时才生效，不 flush 的话一次坏投影会推迟到调用方 commit
+    时才炸，离真因更远。
+
+    ⚠️ **它不删除 YAML 里已经不存在的行**（硬规矩 #39）：从一个动作库里删掉一个动作，
+    ``sync_exercises`` 之后那一行仍在表中。这是刻意的——``prescription``（Task 9）会按
+    ``exercise_ref`` 引用历史处方里的动作，删行会让已生成的处方指向一个查不到的动作。
+    若要真的下线一个动作，那是一次需要人工确认的迁移，不该由一个幂等同步函数顺手做掉。
+
+    ⚠️ **谁在生产路径上调用它，本 Task 没有决定**：Plan02 账本 P2-A1 明确禁止把它接进
+    ``seed_database``（那会撞上「只写组织结构五张表」的守卫），故今天它只有测试这一个
+    调用方。接进管道是 Task 9/10 的活。
+    """
+    library = exercises()
+    for spec in library.values():
+        upsert(
+            session,
+            Exercise,
+            ("ref",),
+            {
+                "ref": spec.ref,
+                "name": spec.name,
+                "video_url": spec.video_url,
+                "impact_level": spec.impact_level.value,
+                # frozenset 不能直接 JSON 序列化，且它的迭代序跨进程不稳定；
+                # 排序让落库字节只由内容决定，canonical dump 才可复现。
+                "targets": sorted(spec.targets),
+                "equipment": spec.equipment,
+            },
+        )
+    session.flush()
+    return len(library)
```


## 数据文件（新增，全文）


### backend/data/exercises.yaml

```yaml
# backend/data/exercises.yaml — 动作库（`exercise` 表的**唯一所有者**）
#
# 【这份文件是什么】
# spec §4.4 的 `exercise` 表由本文件**投影**而来（`app.refdata_prescription.sync_exercises`），
# 不是手工插行：YAML 是体育专家维护的知识资产，DB 行是它的投影，两个所有者会漂移。
# · `exercise_ref` 的唯一所有者 = **本文件的顶层键集**；
# · 每个动作 `impact_level` 的唯一所有者 = **本文件**（Plan02 账本 P2-B2）。spec §7.2 的
#   模板 YAML 字面形状里每个 block 也自带一份 `impact_level`，那是**副本**；负责校验两者
#   一致的是 Task 3 的模板加载器（不一致就在加载时响亮失败），本文件自己校验不住。
#
# 【条目形状】顶层键 = exercise_ref（小写字母开头，只含小写字母/数字/下划线），下面
# **恰好五个键**，多一个少一个都在加载时 ValueError（`load_exercises`）：
#   name          中文动作名，学生端显示
#   video_url     视频二维码 URL。⚠️ 本批一律是 **RFC 2606 占位符**
#                 `https://example.invalid/exercise/<ref>`：`.invalid` 是保留 TLD、DNS 保证
#                 不可解析，故它不可能被误当成一个真能打开的视频源。**不编造真实链接。**
#                 真实视频源须由项目组提供，届时整列替换并同步更新
#                 `tests/test_refdata_prescription.py` 的
#                 `test_video_urls_are_rfc2606_placeholders_keyed_by_ref` 与指纹常量。
#                 ⚠️ 这一条**尚未登记进 spec §14**：本轮只被授权追加第 28 项
#                 （volume_reduction 系数），而计划 Task 12 Step 3 已把「动作库的视频源」
#                 预留为 #29 —— 见 task-2-report.md 的「关切与未尽事项」。
#   impact_level  high | medium | low（spec §4.4 :239 的取值域）
#   targets       素质桶名列表，取值域 = `ITEM_BUCKET` 的三个桶名
#                 endurance | strength | speed_flexibility
#                 ⚠️ `bmi` **不是**桶名：BMI 不归任何短板桶（`ITEM_BUCKET[BMI] is None`），
#                 故 `set(ITEM_BUCKET.values())` 有 4 个元素、含 None，不能当取值域用
#                 （Plan02 账本 P2-A4）
#   equipment     器械需求。无器械写 `none` 而不是留空——留空分不清「不需要」与「忘了填」。
#                 本文件用到的 9 个取值：none / band / step / cone / bike / mat / ball /
#                 ladder / medicine_ball
#
# 【条目数 23 的口径】计划 Task 2 Step 1 定的骨架 = spec §7.2 :487 点名的 **12** 项
# （间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、
# 功能性训练、HIIT、能量消耗模块、抗阻优先模块）+ 速度柔韧类 **4** 项（50 米冲刺间歇、
# 动态拉伸、折返跑、坐位体前屈专项）= **16**，再按 18 套模板（3 层 × 3 主导短板 ×
# 2 体成分）的实际需要补 **7** 项 = **23**，落在计划「预估 20–30 个」的区间内。
# 补的 7 项及理由，逐条写在下面各分节的注释里。
# 条目数由 `test_sync_exercises_projects_every_ref_and_is_idempotent` 按**下界**钉住
# （`>= 20`，取自计划 Task 2 的「预估 20–30 个」）——它抓的是「动作库被截断成几条」，
# 不抓「加了一个动作」，因为**精确值已经由文件字节指纹钉住**，而简报 Step 1 明确允许
# Task 3 往本文件追加 `exercise_ref`、只要求它同步更新指纹常量。
# 文件字节由 `test_exercises_yaml_fingerprint_is_pinned` 钉住（CRLF 归一化为 LF 后取
# sha256 前 16 位）。
#
# 【impact_level 的分布，口径同上】high **5** 个（间歇跑、折返跑、50 米冲刺间歇、跳跃增强式、
# HIIT）、medium **10** 个、low **8** 个，合计 23。5 个 high 每一个都在
# `exercise_equivalence.yaml` 里有 low 替身、且两个触发条件各一条（共 10 条映射），由
# `test_every_high_impact_exercise_has_a_low_substitute` 钉住。
#
# ⚠️ **PyYAML 对重复的顶层键是「后者覆盖前者、不报错」**（实测
# `yaml.safe_load("a: 1\na: 2") == {"a": 2}`），故「复制一段忘了改 ref」会让一个动作
# **静默消失**。守卫是 `test_exercise_refs_are_snake_case_and_unique_keys`：它用**原始文本**
# 数一遍顶层键、与解析结果对账，两侧不同源（硬规矩 #35）。

# ---------------------------------------------------------------------------
# 耐力（endurance）—— 红层 60–70% HRmax 间歇跑、黄层持续跑 + 台阶训练（spec §7.2 :487）
# ---------------------------------------------------------------------------

interval_run:
  name: 间歇跑
  video_url: https://example.invalid/exercise/interval_run
  impact_level: high
  targets: [endurance]
  equipment: none

steady_run:
  name: 持续跑
  video_url: https://example.invalid/exercise/steady_run
  impact_level: medium
  targets: [endurance]
  equipment: none

step_training:
  name: 台阶训练
  video_url: https://example.invalid/exercise/step_training
  impact_level: medium
  targets: [endurance, strength]
  equipment: step

orienteering:
  name: 定向越野
  video_url: https://example.invalid/exercise/orienteering
  impact_level: medium
  targets: [endurance]
  equipment: none

# 补项 1–2：两个 low 冲击的有氧动作。它们不是模板的主选项，而是 `exercise_equivalence.yaml`
# 里 high → low 替换的**落点**：spec §7.4 :508-509 的两个触发（BMI > 30 / 肌肉量 < P10）
# 都是关节负荷过高的医学指征，替身必须真的低冲击。快走与固定自行车是运动处方里最标准的
# 两个低冲击有氧选项（自行车把体重从关节上卸掉，快走把冲击峰值从跑的 2–3 倍体重降到
# 约 1.2 倍）。没有它们，5 个 high 动作里的 3 个（间歇跑、折返跑、50 米冲刺间歇）将无解，
# 直接落进 spec §7.4 :514 的 needs_review 路径。
brisk_walking:
  name: 快走
  video_url: https://example.invalid/exercise/brisk_walking
  impact_level: low
  targets: [endurance]
  equipment: none

stationary_cycling:
  name: 固定自行车
  video_url: https://example.invalid/exercise/stationary_cycling
  impact_level: low
  targets: [endurance]
  equipment: bike

# ---------------------------------------------------------------------------
# 力量（strength）—— 红层 70% 1RM 复合循环、黄层自重 + 弹力带抗阻（spec §7.2 :487）
# ---------------------------------------------------------------------------

compound_circuit:
  name: 复合循环
  video_url: https://example.invalid/exercise/compound_circuit
  impact_level: medium
  targets: [strength, endurance]
  equipment: none

bodyweight_resistance:
  name: 自重抗阻
  video_url: https://example.invalid/exercise/bodyweight_resistance
  impact_level: low
  targets: [strength]
  equipment: mat

band_resistance:
  name: 弹力带抗阻
  video_url: https://example.invalid/exercise/band_resistance
  impact_level: low
  targets: [strength]
  equipment: band

# spec §7.2 :484 的 addon 模块名 `resistance_priority`（`when: muscle_low`）。
# 本文件照那个名字命名，避免出现「模块名」与「动作 ref」两个所有者。
resistance_priority:
  name: 抗阻优先模块
  video_url: https://example.invalid/exercise/resistance_priority
  impact_level: medium
  targets: [strength]
  equipment: band

# 补项 3：红层力量短板需要一个 70% 1RM 量级的抗阻主项（spec §7.2 :476 的
# `intensity: {type: onerm_pct, value: 70}`），而复合循环是**多动作串联**、单动作强度上不去。
# 药球核心训练是可加载的单动作抗阻，且它的冲击等级是 medium（不含跳跃落地），
# 因此不需要在等价表里备 low 替身。
medicine_ball_core:
  name: 药球核心训练
  video_url: https://example.invalid/exercise/medicine_ball_core
  impact_level: medium
  targets: [strength]
  equipment: medicine_ball

# 补项 4：high 冲击的力量动作。立定跳远是国标 6 个短板判定项之一
# （`ScoredItem.STANDING_JUMP`，归 strength 桶），红层要提升它就必须有跳跃类刺激；
# 而它同时是 BMI > 30 时**最该被换掉**的动作（反复落地 = 反复 2–3 倍体重冲击）。
# 故它在等价表里的替身是 `bodyweight_resistance`（同样的下肢力量刺激、零落地）。
plyometric_jump:
  name: 跳跃增强式训练
  video_url: https://example.invalid/exercise/plyometric_jump
  impact_level: high
  targets: [strength, speed_flexibility]
  equipment: none

# ---------------------------------------------------------------------------
# 速度柔韧（speed_flexibility）—— 计划 Task 2 Step 1 要求补的 4 项 + 2 个补项
# ---------------------------------------------------------------------------

sprint_50m_intervals:
  name: 50 米冲刺间歇
  video_url: https://example.invalid/exercise/sprint_50m_intervals
  impact_level: high
  targets: [speed_flexibility, endurance]
  equipment: none

shuttle_run:
  name: 折返跑
  video_url: https://example.invalid/exercise/shuttle_run
  impact_level: high
  targets: [endurance, speed_flexibility]
  equipment: cone

dynamic_stretching:
  name: 动态拉伸
  video_url: https://example.invalid/exercise/dynamic_stretching
  impact_level: low
  targets: [speed_flexibility]
  equipment: none

# 坐位体前屈是国标 6 个短板判定项之一（`ScoredItem.SIT_AND_REACH`，归 speed_flexibility 桶）
sit_and_reach_drill:
  name: 坐位体前屈专项
  video_url: https://example.invalid/exercise/sit_and_reach_drill
  impact_level: low
  targets: [speed_flexibility]
  equipment: mat

# 补项 5：绿层速度柔韧短板需要一个 medium 档的敏捷主项。绿层每周只 2 天（spec §7.2 :487），
# 两个 low 档的拉伸类动作撑不起一次课的主体部分。绳梯敏捷是标准选项，且不含跳跃落地，
# 故为 medium、不需要 low 替身。
agility_ladder:
  name: 绳梯敏捷
  video_url: https://example.invalid/exercise/agility_ladder
  impact_level: medium
  targets: [speed_flexibility]
  equipment: ladder

# 补项 6：坐位体前屈这一项在国标里是**柔韧**，而柔韧的提升除了动态拉伸还需要 PNF
# （本体感觉神经肌肉促进）这一档更有效的静态手法，且它需要弹力带或同伴辅助。
# 它是 low 冲击，因此也可以充当 speed_flexibility 类动作在安全后置下的替身。
pnf_stretching:
  name: 本体感觉神经肌肉促进拉伸
  video_url: https://example.invalid/exercise/pnf_stretching
  impact_level: low
  targets: [speed_flexibility]
  equipment: band

# ---------------------------------------------------------------------------
# 绿层兴趣 / 综合，与两个 addon 模块（spec §7.2 :480-487）
# ---------------------------------------------------------------------------

interest_ball_games:
  name: 兴趣球类
  video_url: https://example.invalid/exercise/interest_ball_games
  impact_level: medium
  targets: [endurance, speed_flexibility]
  equipment: ball

functional_training:
  name: 功能性训练
  video_url: https://example.invalid/exercise/functional_training
  impact_level: low
  targets: [strength, speed_flexibility]
  equipment: none

# spec §7.2 :487「体脂偏高附加 5min HIIT」（黄层）。high 冲击，故在等价表里备 low 替身。
hiit:
  name: 高强度间歇训练
  video_url: https://example.invalid/exercise/hiit
  impact_level: high
  targets: [endurance, strength]
  equipment: none

# spec §7.2 :482 的 addon 模块名 `energy_expenditure_plus_10pct`（`when: body_fat_over`，
# 红层 +10% 能量消耗）。⚠️ 它是 spec §7.4 :510 第三个触发（体脂率异常）走的那条路
# ——**追加模板 addons 里的能量消耗模块，不查等价表**（Plan02 账本 P2-C3），故它在
# `exercise_equivalence.yaml` 里既不是 from 也不是 to。
# 这个 29 字符的名字是本文件最长的 ref，决定了 `exercise.ref` 的列宽下界
# （声明 String(48)，由 test_exercise_string_column_widths_fit_the_yaml_values 现读现比）。
energy_expenditure_plus_10pct:
  name: 能量消耗模块
  video_url: https://example.invalid/exercise/energy_expenditure_plus_10pct
  impact_level: medium
  targets: [endurance]
  equipment: none

# 补项 7：spec §7.2 :487 的绿层写「兴趣球类/定向越野/功能性训练 + **可选挑战任务**」，
# 那句里点到的第四个东西此前没有 ref。它是 medium 冲击、同时瞄准三个桶（挑战任务的形式
# 由教师定，可能是接力、可能是闯关），故在等价表里也不是端点。
# ⚠️ 变异验收 ② 用的正是这个 ref：删掉它，全仓**只有**指纹测试会红——因为没有任何一条
# 映射或断言依赖它（Plan02 账本 P2-C1：原文还要求「模板引用存在性」测试变红，而那个
# 测试是 Task 3 才建的）。
challenge_task:
  name: 可选挑战任务
  video_url: https://example.invalid/exercise/challenge_task
  impact_level: medium
  targets: [endurance, strength, speed_flexibility]
  equipment: none
```


### backend/data/exercise_equivalence.yaml

```yaml
# backend/data/exercise_equivalence.yaml — 低冲击等价动作映射表
#
# 【这份文件是什么】
# spec §4.4 :243 明写：`exercise_equivalence`（动作等价映射）与 `alert_rules`（预警阈值）
# 是 `data/` 下的**静态 YAML + 版本号**，**不入库**——「这是体育专家维护的知识资产而非
# 业务数据，改阈值应走版本控制与评审，不应在运行时改数据库」。
#
# 消费者是 spec §7.4 的安全后置处理器（Task 7 的 `app/domain/prescription/safety.py`），
# 加载器是 `app.refdata_prescription.load_equivalence()` / `equivalence()`。
#
# 【三个顶层键，缺一个都在加载时 ValueError】
#   version           映射表版本号。spec §7.4 :512 要求每次替换把「原动作、新动作、
#                     触发条件、**映射表版本号**」写进 `prescription.safety_substitutions`，
#                     于是一张已生成的处方能回答「当时是按哪一版映射表替换的」。
#                     ⚠️ YAML 里必须**加引号**：裸 `1.0` 会被解析成 float，而 spec 要的是一个
#                     可写进 JSON 的版本标识。
#   mappings          映射条目列表，每条**恰好四个键**：
#                       from       被替换动作的 exercise_ref
#                       to         替身的 exercise_ref（必须在 exercises.yaml 里存在）
#                       max_impact 本条声明的替身冲击上限，必须**等于** `to` 在
#                                  exercises.yaml 里的真实 impact_level
#                                  （`EquivalenceTable.lookup` 按 max_impact 过滤、不看动作库，
#                                  故一张撒谎的表会让 lookup 返回一个冲击高于上限的动作）
#                       when       bmi_over_30 | muscle_low_p10
#                                  —— spec §7.4 :508-509 只有这两个触发**走等价表**；
#                                  :510 的「体脂率异常」走的是「追加模板 addons 中的能量
#                                  消耗模块」，**不查本表**（Plan02 账本 P2-C3 亲验）
#   volume_reduction  两个触发各自的**跑量下调系数**，键必须恰好是上面那两个 when 取值
#
# 【mappings 共 10 条的口径】exercises.yaml 里 impact_level = high 的动作有 **5** 个
# （interval_run / shuttle_run / sprint_50m_intervals / plyometric_jump / hiit），每个在两个
# 触发下各需一条 → 5 × 2 = **10**。每条的 `max_impact` 都是 `low`，且 `to` 的真实冲击也都是
# `low`（8 个 low 动作里的 5 个被用到：stationary_cycling / brisk_walking /
# bodyweight_resistance / functional_training，其中 stationary_cycling 被 4 条复用）。
# ⚠️ **medium 动作刻意不备 low 替身**（Plan02 账本 P2-C2）：spec §7.4 :508-509 的两个触发
# 都只替换 `impact_level: high`，给永不发生的场景写映射是过紧的守卫，代价是把一张专家
# 审校表塞满永不被查到的死条目。
#
# 【替身的选择理由，逐条】
#   interval_run          → stationary_cycling  间歇跑的高冲击来自反复落地；固定自行车把
#                                               体重从关节上卸掉，同时保留 60–70% HRmax 的
#                                               间歇刺激（spec §7.2 :487 的红层耐力参数）
#   sprint_50m_intervals  → stationary_cycling  同上；自行车冲刺是速度间歇的标准低冲击替代
#   shuttle_run           → brisk_walking       折返跑的冲击来自反复急停变向；快走保留了
#                                               位移类有氧、去掉了全部变向冲击
#   plyometric_jump       → bodyweight_resistance  跳跃增强式的目标是下肢力量/爆发，自重
#                                               抗阻保留力量刺激、去掉全部落地
#   hiit                  → functional_training 高强度间歇的代谢刺激由功能性训练的循环形式
#                                               承接，冲击等级 low
#
# ⚠️⚠️ 【volume_reduction 的两个系数在 spec 里**没有出处**】（Plan02 账本 P2-A3）
# spec §7.4 :508 只写「跑量**按映射表下调**」、**没给任何数**；:509（肌肉量 < P10）写「同上」。
# spec 里唯一出现的「系数 0.8」在 :604，那是**预警触发的「减量 20%」**
# （`weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，属 **Plan 03**），与本表的安全
# 后置跑量下调是**两个不同机制**；`0.9` 在 spec 里**根本没有对应物**。
# 把 :604 的 0.8 借来当 §7.4 的系数，正是「借自本仓另一处真实机制、因而通过了所有人直觉
# 审查」的那个失效形态（控制者错误 #40 / 硬规矩 #63）。
# 故：**这两个数是本设计的默认规定，不是 spec 条文**。已登记进 spec §14 第 28 项。
# **Task 7 消费时不得把它们当成 spec 条文引用。**
# 字面钉住它们的测试是 `test_volume_reduction_coefficients_are_pinned_verbatim`。
#
# 【口径提示，Task 7 留意】spec §7.4 用**肌肉量 < P10**，而 §4.2 / :384 的体成分异常判定
# `C` 用**肌肉量 < P20**。两个阈值不同、分属两个机制，不得混用（Plan02 账本 P2-A3 附带发现）。
#
# 【改这张表的处置】文件字节由 `test_equivalence_yaml_fingerprint_is_pinned` 钉住
# （CRLF 归一化为 LF 后取 sha256 前 16 位）。**只把某条 `to` 从一个 low 动作换成另一个
# low 动作，不会破坏任何一条形状不变量**（目标仍存在、仍不升冲击、high 仍有 low 替身、
# version 仍非空），六条语义测试会全绿——那正是指纹存在的理由（Ruling 213 的教训）。
# 改了内容还要考虑**是否升 version**：一张已生成的处方的 safety_substitutions 记着旧版本号，
# 若内容变了而版本号没变，那个字段就在撒谎。

version: "1.0"

mappings:
  # --- 触发 1：BMI > 30（spec §7.4 :508）------------------------------------
  - from: interval_run
    to: stationary_cycling
    max_impact: low
    when: bmi_over_30
  - from: sprint_50m_intervals
    to: stationary_cycling
    max_impact: low
    when: bmi_over_30
  - from: shuttle_run
    to: brisk_walking
    max_impact: low
    when: bmi_over_30
  - from: plyometric_jump
    to: bodyweight_resistance
    max_impact: low
    when: bmi_over_30
  - from: hiit
    to: functional_training
    max_impact: low
    when: bmi_over_30

  # --- 触发 2：肌肉量 < 同龄同性别 P10（spec §7.4 :509，「同上」）------------
  # 替身与触发 1 相同：spec 原文就是「同上，并提高抗阻模块比重」，而「提高抗阻比重」是
  # Task 7 在**装配层**做的事（改模块配比），不是换替身能表达的，故本表不为它另立条目。
  - from: interval_run
    to: stationary_cycling
    max_impact: low
    when: muscle_low_p10
  - from: sprint_50m_intervals
    to: stationary_cycling
    max_impact: low
    when: muscle_low_p10
  - from: shuttle_run
    to: brisk_walking
    max_impact: low
    when: muscle_low_p10
  - from: plyometric_jump
    to: bodyweight_resistance
    max_impact: low
    when: muscle_low_p10
  - from: hiit
    to: functional_training
    max_impact: low
    when: muscle_low_p10

# 跑量下调系数（**本设计的默认规定，无 spec 出处**，理由见上方那段 ⚠️⚠️）。
# 语义：命中该触发时，装配出的周训练量乘以这个系数。0.8 = 下调 20%，0.9 = 下调 10%。
# BMI > 30 下调更多，因为它的关节负荷风险更直接、且 spec 把它列在两个触发的第一位。
volume_reduction:
  bmi_over_30: 0.8
  muscle_low_p10: 0.9
```


## 测试与其余 diff（-U10）

```diff
diff --git a/backend/tests/architecture/test_domain_purity.py b/backend/tests/architecture/test_domain_purity.py
index 827968d..4ac17fd 100644
--- a/backend/tests/architecture/test_domain_purity.py
+++ b/backend/tests/architecture/test_domain_purity.py
@@ -92,22 +92,26 @@ def _assert_not_empty(scanned: list[pathlib.Path]) -> None:
     )
 
 
 def _imported_modules(tree: ast.AST):
     """yield ``(lineno, 完整模块串, 相对层级, 被导入名)``；``ast.walk`` 覆盖函数内导入。
 
     第 4 项只在 ``level > 0`` **且** ``module`` 为空时非空——那一档被导入的模块名住在
     ``node.names`` 里（``from .. import seed``）。**一个节点可以带多个名字**，而
     ``from .. import seed, pipeline`` 导入的是**两个**模块，故这一档逐个 ``names`` yield
     两条、由 :func:`_absolute` 各自折算；只 yield 一条就会把 ``app.seed`` 折成 ``app``
-    （Plan02 Ruling 36）。真仓里就有这一形状：``app/db/models/__init__.py:74`` 的
-    ``from . import feedback, prescription``。
+    （Plan02 Ruling 36）。真仓里就有这一形状：``app/db/models/__init__.py`` 里那句
+    ``from . import feedback, prescription  # noqa: F401``（⚠️ **用可 grep 的原文定位、
+    不写裸行号**：``git grep -n "import feedback" -- backend/app`` 只命中这一处，而裸行号
+    已被编辑推走过一次——Task 2 按 Ruling 90 改该文件 docstring 时它从 ``:74`` 落到 ``:82``，
+    引用它的两处都没跟着改（Plan02 账本 Ruling 106 的 CE-7）。在 ``c21767d`` 上它是第
+    **82** 行；``:74`` 今天是 ``from .derived import *  # noqa: F401,F403``）。
     """
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 yield node.lineno, alias.name, 0, ""
         elif isinstance(node, ast.ImportFrom):
             if node.level and not node.module:
                 for alias in node.names:
                     yield node.lineno, "", node.level, alias.name
             else:
@@ -436,28 +440,43 @@ def test_domain_imports_stay_within_the_allow_list():
     全部 import 就已经在白名单内，所以它**一上来就是绿的**——计划原文 Step 2 写的
     「allow-list 守卫报 ``numpy`` 之外的漏网」是猜的，AST 亲扫没有漏网。它的价值不在于
     今天红不红，而在于**新增的拦截力**：
 
     * ``import app.refdata`` 从此会被抓。终审 A 曾说「domain 经两跳依赖 ``app.refdata``」，
       **AST 实测不成立**——那是 ``percentile.py`` 模块 docstring 里的自陈（说的是「参考表
       由 refdata 加载后注入」这件事），不是 import。旧 deny-list 里没有 ``app.refdata``，
       所以真的加上这一句 import 时它不会响；白名单会。
     * ``from os import listdir`` / ``import json`` / ``import pathlib`` 一律被抓，
       不必再靠第三条守卫的子串去撞。
-    * **相对导入一律先折算成绝对串**再走白名单（:func:`_absolute`）。今天全仓的相对导入
-      只有 ``app/db/models/`` 包内的 ``level == 1``（命令::
+    * **相对导入一律先折算成绝对串**再走白名单（:func:`_absolute`）。全仓的相对导入
+      **全部是 ``level == 1``**，但自 Plan 02 Task 2 起已**不再只住在** ``app/db/models/``
+      包内（命令::
 
           cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
 
-      实测 12 条、全部 ``level == 1``），故 domain 侧**没有 offender**；但 Plan 02 Task 2
-      起会建 ``app/domain/prescription/`` 这一层子包，届时 ``level == 2`` 的相对导入
-      开始正常出现，「一律放行」的写法会跟着变成真漏洞。折算之后（⚠️ **同一句写法在不同
+      在 ``c21767d`` 上实测 **15** 条 = ``app/db/models`` **13** 条 +
+      ``app/domain/prescription`` **2** 条（``__init__.py`` 的 ``from .exercises import (…)``
+      与 ``templates.py`` 的 ``from .exercises import ImpactLevel``），level 分布
+      ``{1: 15}``。**Task 1 期间那个「12 条」是绑定轮次的历史值、不要顺手改成 15**：
+      ``6a2938f``（fix round 1 亲跑）与 ``7b84599``（fix round 5 复跑）两个 rev 上用
+      ``git show`` 重算都仍是 **12** 条、且全部落在 ``app/db/models`` 包内；Task 2 主体
+      ``3ea27cc`` 建出本子包后是 **14**，fix round 1 给 ``templates.py`` 补上那句 re-export
+      后是 **15**（Plan02 账本 Ruling 106 的 CE-6）。故 domain 侧**没有 offender** 这个
+      结论不变、而**理由变了**：不再是「domain 侧没有相对导入」，而是那 2 条折算成
+      ``app.domain.prescription.exercises``、命中白名单前缀 ``app.domain.``（亲跑：
+      ``_absolute('exercises', 1, ('app', 'domain', 'prescription'))`` =
+      ``'app.domain.prescription.exercises'``）。``level == 2`` 在真仓里**今天仍不存在**
+      （账本 Ruling 104 亲扫：Task 2 刻意选了绝对导入
+      ``from app.domain.indicators import ITEM_BUCKET``，与既有 4 个 domain 模块同风格），
+      但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写
+      ``from ..indicators import X`` 它就开始正常出现，「一律放行」的写法会跟着变成真漏洞。
+      折算之后（⚠️ **同一句写法在不同
       文件深度解析到不同的地方**，故下面每条都带主语；合成树里逐条写入探针文件后直接
       调用本测试函数，颜色是实跑的，Plan02 Ruling 39-3）：
 
       * **扁平的** ``app/domain/x.py``（包深 2）：``from ..seed import generate`` 解析到
         ``app.seed.generate`` → **offender**；``from ...seed import generate`` 已经越界，
         :func:`_absolute` 返回 ``None`` → **同样 offender**。
       * ``app/domain/sub/x.py``（包深 3）：``from ..tables import X`` 解析到
         ``app.domain.tables`` → **合法**；而**同一句** ``from ..seed import generate`` 在
         这个深度解析到的是 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` →
         **不是 offender**（这一档要到 ``app.seed`` 得写 ``from ...seed import generate``，
diff --git a/backend/tests/architecture/test_layering.py b/backend/tests/architecture/test_layering.py
index 2dcde57..e3bfafe 100644
--- a/backend/tests/architecture/test_layering.py
+++ b/backend/tests/architecture/test_layering.py
@@ -148,28 +148,45 @@ def _imported_modules(tree: ast.AST, package: tuple[str, ...]):
     ``domain`` 三个目录合计要有 **≥ 8 个 ``.py``**（含探针文件自己），否则本文件那条
     ``len(scanned) >= 8`` 的空转守卫先响（``AssertionError: 只扫到 1 个 .py …``）、探针的
     颜色不可解释，故**必须先跑一行已知 GREEN 的干净对照**（探针只写 ``x = 1``；上面四条
     都是 fix round 5 亲跑）。同款配方在 :mod:`tests.architecture.test_domain_purity` 那一份
     里下界是 ``>= 5``、重定向的是 ``DOMAIN`` **和** ``BACKEND``，两处 fix round 5 已互相
     对齐（Plan02 Ruling 68／硬规矩 #51/#53）。逐条写进探针文件后直接调用本测试函数）：
     上述两种写法**改前全绿**、改后全红。
 
     而 ``app/db/models/`` 包内**真实存在**的那批相对导入，折算后是 ``app.db.models._shared``
     / ``app.db.models.organisation`` 一类，不以 ``app.seed`` 开头，**仍然绿**。它们的全貌用
-    这条命令数（fix round 1 亲跑；fix round 5 复跑仍是同一个结果：12 条、全部
-    ``level == 1``、全部落在 ``app.db.models`` 包内）::
+    这条命令数。**条数必须绑时点**（Plan02 账本 Ruling 106 的 CE-6）：**Task 1** 的
+    fix round 1（``6a2938f``）亲跑、fix round 5（``7b84599``）复跑都是同一个结果——
+    **12 条**、全部 ``level == 1``、全部落在 ``app.db.models`` 包内；这两个 rev 上用
+    ``git show`` 重算今天仍是 12，故这句历史陈述**在它绑定的时点上是真的、不要改成 15**。
+    ⚠️ **而全仓的当前值已经不是 12**：Plan 02 Task 2 建出 ``app/domain/prescription/``
+    之后，在 ``c21767d`` 上同一条命令数出 **15** 条 = ``app/db/models`` **13** +
+    ``app/domain/prescription`` **2**、level 分布 ``{1: 15}``（主体 ``3ea27cc`` 是 14，
+    fix round 1 给 ``templates.py`` 补上那句 re-export 后是 15），即「全部落在
+    ``app.db.models`` 包内」这半句**只对那 13 条成立、对全仓已不成立**::
 
         cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
 
-    那 12 条里有 **1 条**是 ``module`` 为空的形状：``app/db/models/__init__.py:74`` 的
-    ``from . import feedback, prescription``（上面那条命令打出来的第 7 行是
-    ``app/db/models/__init__.py 74 1 None``）。它是**一个节点、两个名字、两个模块**，故
+    那 15 条里 ``module`` 为空的形状仍是 **1 条**（分母从 12 变 15、**分子不变**：
+    ``6a2938f`` / ``7b84599`` / ``3ea27cc`` / ``c21767d`` 四个 rev 上都实扫过，
+    ``app/domain/prescription`` 那 2 条的 ``module`` 都是 ``'exercises'``、非空）：
+    ``app/db/models/__init__.py`` 里那句 ``from . import feedback, prescription``
+    （⚠️ **不写裸行号**：Task 2 按 Ruling 90 改该文件 docstring 时把它从 ``:74`` 推到
+    ``:82``，引用它的两处没跟着改，账本 Ruling 106 的 CE-7；可 grep 的原文是
+    ``from . import feedback, prescription  # noqa: F401``，``git grep -n "import feedback"
+    -- backend/app`` 只命中这一处）。上面那条命令在 ``c21767d`` 上打出来的**第 7 行**是
+    ``app/db/models/__init__.py 82 1 None``——**序数 7 在那四个 rev 上都没变**（该文件恒有
+    7 条相对导入、``module=None`` 那条恒排最后，且它在 ``sorted()`` 下排全仓第一），变的
+    只是行号；Windows 上 ``pathlib`` 打出的分隔符是反斜杠
+    （``app\\db\\models\\__init__.py 82 1 None``），分隔符随平台、序数与数字不随。
+    它是**一个节点、两个名字、两个模块**，故
     下面按 ``names`` 逐个 yield、折算成 ``app.db.models.feedback`` 与
     ``app.db.models.prescription`` 两条；此前只 yield 一条 ``app.db.models``（Plan02
     Ruling 36）。两条都不以 ``app.seed`` 开头，**判定不变、仍然绿**。
     """
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 yield node.lineno, alias.name
         elif isinstance(node, ast.ImportFrom):
             if node.level and not node.module:
@@ -228,23 +245,36 @@ def test_absolute_folding_matches_resolve_name():
     ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。fix round 3 实测
     三种变异各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条
     **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。
     断言里印出来的折算值也是实跑的：越界档报
     ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =
     'app.db.seed'``（而 ``resolve_name('.....seed', 'app.db.models')`` 抛 ``ImportError``）、
     ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
     ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。
 
     **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内
-    真实存在的那 12 条 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被
-    :func:`_is_forbidden` 放过（fix round 1 亲跑数出 12 条；fix round 5 复跑仍是 12 条、
-    全部 ``level == 1``、全部落在 ``app.db.models`` 包内）。
+    真实存在的那批 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被
+    :func:`_is_forbidden` 放过。**这批的条数绑时点**（Plan02 账本 Ruling 106 的 CE-6）：
+    **Task 1** 的 fix round 1（``6a2938f``）亲跑数出 **12** 条、fix round 5（``7b84599``）
+    复跑仍是 **12** 条，全部 ``level == 1``、全部落在 ``app.db.models`` 包内（两个 rev 上
+    重算今天仍是 12，故这两句历史陈述**是真的、不要改成 15**）。⚠️ **而全仓的当前值不是
+    12**：Plan 02 Task 2 建出 ``app/domain/prescription/`` 之后，在 ``c21767d`` 上是
+    **15** 条 = ``app/db/models`` **13** + ``app/domain/prescription`` **2**、level 分布
+    ``{1: 15}``，故「全部落在 ``app.db.models`` 包内」这半句**只对那 13 条成立**、对全仓
+    已不成立。
+
+    **本绿档的主语是「``app/db/models`` 包内那批」**（硬规矩 #56）：12 条与 13 条两个时点
+    它都在场、颜色都是 GREEN（亲跑 ``_is_forbidden('app.db.models._shared') is False``）。
+    domain 那 2 条折算成 ``app.domain.prescription.exercises``，在**本文件**的判据下同样
+    GREEN（不以 ``app.seed`` 开头，亲跑 ``_is_forbidden(...) is False``）；在
+    :mod:`tests.architecture.test_domain_purity` 那一份的判据下也 GREEN（命中白名单前缀
+    ``app.domain.``）。两份颜色相同、判据不同，这不是抄错。
 
     **矩阵第 9 行是 fix round 5 新加的绿档**（Plan02 Ruling 67）：Task 2 起
     ``app/domain/prescription/match.py`` 里的 ``from ..indicators import X``——包深 3 →
     **两个点**才上溯到 ``app.domain``，故 ``level == 2``（**不是** ``level == 1``）。
     fix round 5 亲跑::
 
         _package_of(BACKEND / 'app/domain/prescription/match.py')
             = ('app', 'domain', 'prescription')
         _absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')
             = 'app.domain.indicators'
diff --git a/backend/tests/db/test_models.py b/backend/tests/db/test_models.py
index 23e09b8..401cbe3 100644
--- a/backend/tests/db/test_models.py
+++ b/backend/tests/db/test_models.py
@@ -14,28 +14,34 @@ from app.domain.percentile import (
 )
 from app.domain.stratify import RULE_ORDER, RuleId
 
 @pytest.fixture
 def session():
     eng = create_engine("sqlite:///:memory:")
     init_db(eng)
     with Session(eng) as s:
         yield s
 
-def test_all_fourteen_tables_created(session):
+def test_all_fifteen_tables_created(session):
     expected = {"semester","teacher","student","course_section","enrollment",
         "fitness_test_batch","fitness_test_result","body_composition",
         "interest_survey","percentile_snapshot","derived_metrics",
-        "stratification_result","daily_sync_run","cleaning_log"}
-    # Ruling 28：用 == 而不是 >=。「第一批只建这 14 张」是真实的范围边界，>= 抓不到
-    # 有人提前把计划 02（处方 / 运动记录）或计划 03（预警 / 通知）的表建进来——那种
-    # 提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感。
+        "stratification_result","daily_sync_run","cleaning_log","exercise"}
+    # Ruling 28：用 == 而不是 >=。「本批只建这些」是真实的范围边界，>= 抓不到
+    # 有人提前把后续计划的表建进来——那种提前建表会逼出一次本该不存在的迁移，
+    # 而超集断言对它完全无感。
+    # ⚠️ **Plan 02 逐 Task 递增，不得一次性写到 18**：Plan 01 结案是 14 张，Task 2 加
+    # ``exercise`` → 15（本条现值）；Task 3 加 ``prescription_template`` → 16；Task 9 加
+    # ``prescription`` + ``weekly_adjustment`` → 18（计划 ``:700`` 的「18 张」清单）。
+    # 每个 Task 只改自己那一步，并同步改函数名里的英文数词与本文件 ``:163`` / ``:228`` /
+    # ``:472`` 的三处 ``==``，以及 ``app/db/models/prescription.py`` 模块 docstring 里那张
+    # 「表 → 归属 Task」的表。
     assert set(inspect(session.get_bind()).get_table_names()) == expected
 
 def test_daily_sync_run_business_date_is_unique(session):
     sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025,9,1),
                      end_date=dt.date(2026,1,20), weeks=16, is_current=True)
     session.add(sem); session.flush()
     d = dt.date(2025, 9, 15)
     session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
     session.flush()
     session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
@@ -149,43 +155,45 @@ def _is_builtin_json(type_) -> bool:
     impl = getattr(type_, "impl", None)  # TypeDecorator 的真实落库类型
     return isinstance(impl, type) and issubclass(impl, BuiltinJson)
 
 
 def test_no_column_uses_builtin_sqlalchemy_json():
     """``JsonText`` 已是全库约定，任何一列退回自带 ``JSON`` 都要当场炸。
 
     自带 ``JSON`` 在 SQLite 上是 NUMERIC 亲和性：``original_value = 0.0`` 会存成
     ``integer 0``、读回 ``int 0``，审计记录里的「原值 65.0 kg」变成「原值 65」。
     行为侧已有 ``test_json_text_keeps_float_and_none`` 覆盖，这条是结构侧的守卫——
-    它不看某一列的行为，而是遍历 14 张表的每一列，让「新加的模型忘了这条约定」也
+    它不看某一列的行为，而是遍历 15 张表的每一列，让「新加的模型忘了这条约定」也
     逃不掉。
     """
     tables = Base.metadata.tables
-    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"
+    assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
 
     offenders = [
         f"{table.name}.{column.name}"
         for table in tables.values()
         for column in table.columns
         if _is_builtin_json(column.type)
     ]
     assert offenders == [], f"这些列用了自带 JSON，必须换成 JsonText：{offenders}"
 
-    # 守卫自己也得有牙：八个 JSON 形态的列确实被遍历到了，不是空跑
+    # 守卫自己也得有牙：九个 JSON 形态的列确实被遍历到了，不是空跑。
+    # Plan 02 Task 2 把 8 改成 9：新增的是 ``exercise.targets``（动作瞄准的素质桶名列表）。
     json_text_columns = sorted(
         f"{table.name}.{column.name}"
         for table in tables.values()
         for column in table.columns
         if type(column.type).__name__ == "JsonText"
     )
-    assert len(json_text_columns) == 8, json_text_columns
+    assert len(json_text_columns) == 9, json_text_columns
     assert "cleaning_log.original_value" in json_text_columns
+    assert "exercise.targets" in json_text_columns
 
 
 # ---------------------------------------------------------------------------
 # Ruling 31：``batch_id`` 一词专指 daily_sync_run 的外键
 # ---------------------------------------------------------------------------
 
 # 全库唯一允许拥有 ``batch_id`` 列的三张派生表——即 ``delete_by_batch`` 的合法目标。
 _DERIVED_TABLES = {"derived_metrics", "stratification_result", "percentile_snapshot"}
 
 
@@ -218,21 +226,21 @@ def test_only_derived_tables_expose_batch_id():
 
     遍历 ``Base.metadata``，有 ``batch_id`` 列的表**恰好**是三张派生表。``batch_id``
     在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch`` 可据以
     删除的归属键；任何别的父表都得用可区分的名字（``fitness_test_result.test_batch_id``
     指体测批次、``cleaning_log.sync_run_id`` 指同步运行）。
 
     只断言列名还不够——名字对了语义错了才是 Ruling 31 要防的失效，故同时断言这三列
     真的指向 ``daily_sync_run``。
     """
     tables = Base.metadata.tables
-    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"
+    assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
 
     observed = {
         name for name, table in tables.items() if "batch_id" in set(table.c.keys())
     }
     assert observed == _DERIVED_TABLES, (
         f"batch_id 专指 daily_sync_run 的外键，实到 {sorted(observed)}"
     )
 
     for name in sorted(_DERIVED_TABLES):
         column = tables[name].c.batch_id
@@ -338,28 +346,39 @@ def test_string_column_widths_fit_their_value_domains():
     """凡 ``String(n)`` 列存枚举值或固定词表，``n`` 必须 ≥ 该域内最长值的长度。
 
     SQLite **不强制** ``VARCHAR`` 长度，故这类溢出在测试里永远不报错——Ruling 144 的
     ``derived_metrics.trend String(16)`` 就是这样漏了 7 个任务：``Trend.INSUFFICIENT.value``
     = ``"insufficient_data"`` 是 17 字符，500 人首批实测有 **209 行（41.8%）**往这一列写它。
     换 MySQL / PostgreSQL 会截断成 ``"insufficient_dat"``，读回来 ``Trend(...)`` 当场
     ``ValueError``——**炸在读侧不在写侧**，离真因隔一整个批处理周期。
 
     取值域的两个来源，都不是手抄的第二份清单：
 
-    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天恰好 10 列：
+    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天 **11** 列：
        ``student.sex``、``course_section.grouping_mode``、``fitness_test_batch.timepoint``、
        ``percentile_snapshot`` 的 ``source`` / ``sex`` / ``item``、``stratification_result``
-       的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``）。
+       的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``、
+       以及 Plan 02 Task 2 新增的 ``exercise.impact_level``）。
     2. **没有 CHECK 约束、但取值域有唯一所有者的四列**——见下方注释里各自的出处。
+
+    ⚠️ **这道遍历测试只看得见第 1 类**（Plan02 账本 P2-A5）：``Exercise`` 的 5 个
+    ``String(n)`` 列里只有 ``impact_level`` 带 ``_in_domain`` CHECK，``ref`` / ``name`` /
+    ``video_url`` / ``equipment`` 的取值域不是封闭集合、没有 CHECK，故**完全不被本测试
+    覆盖**——它们的列宽断言住在
+    ``tests/test_refdata_prescription.py::test_exercise_string_column_widths_fit_the_yaml_values``
+    （实际侧从 ``exercises.yaml`` 现读）。Plan 03 再加表时同理：没有 CHECK 的列要自己去
+    对应的测试文件里写。
     """
     domains = _in_domain_columns()
     # 空转守卫：正则写错会静默匹配到 0 列而全绿（那时 offenders 恒为空）。
+    # ⚠️ 这是**下界**、刻意不逐 Task 抬高：它的职责只是「正则没有失配到 0 列」，
+    # 抬到 == 11 会让 Plan 02 剩下的三个 Task 每次都来改这一行，而它抓不到任何新失效。
     assert len(domains) >= 10, f"反解出的受约束列数不对，正则可能失配：{sorted(domains)}"
 
     # 无 CHECK 约束的四列，取值域各自指向生产里的唯一所有者：
     # · ``derived_metrics.trend``       ← :class:`app.domain.derive.Trend` 的成员值
     #   （写入处 ``pipeline/daily.py`` 的 ``trend=derived.trend.value``），最长 17。
     # · ``stratification_result.hit_rules`` ← ``",".join(RuleId.value)``。Z0 路径恰为
     #   ``"Z0"``、非 Z0 路径是 7 条分层规则的已评估前缀，**两者互斥**（Ruling 132），
     #   故生产最大值是非 Z0 的完整前缀 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20**，不是把 Z0
     #   也串起来的 23（Ruling 148）。
     # · ``percentile_snapshot.age_group`` ← :data:`app.domain.indicators.AGE_GROUPS`
@@ -461,22 +480,25 @@ def test_models_public_namespace_is_unchanged_by_the_split():
     assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE), (
         f"少了 {sorted(set(_MODELS_PUBLIC_BASELINE) - observed)}，"
         f"多了 {sorted(observed - _MODELS_SUBMODULES - set(_MODELS_PUBLIC_BASELINE))}"
     )
     assert list(M.__all__) == _MODELS_ALL_BASELINE
 
     # 私有名里有一个是**承重的**：约束文本生成器。它带前导下划线故不在上面的比对里，
     # 但 tests/db/test_models.py 自己的注释与将来的迁移脚本都按
     # ``app.db.models._in_domain`` 引用它，故单独钉一条。
     assert callable(M._in_domain)
-    # 14 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）
-    assert len(Base.metadata.tables) == 14
+    # 15 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）。下面点名的
+    # 是**拆包前就有的 14 张**（``_MODELS_ALL_BASELINE``）；Plan 02 新增的
+    # ``exercise`` 不在那份基线里，它由 ``test_all_fifteen_tables_created`` 的
+    # ``expected`` 集合点名。
+    assert len(Base.metadata.tables) == 15
     for name in _MODELS_ALL_BASELINE:
         assert getattr(M, name).__tablename__ in Base.metadata.tables
 
 
 # ---------------------------------------------------------------------------
 # Plan 02 Task 1 Step 4：fitness_test_result.tested_on 与 daily_sync_run 的计数列
 # ---------------------------------------------------------------------------
 
 def _semester_and_student(session):
     sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
diff --git a/backend/tests/domain/test_prescription_templates.py b/backend/tests/domain/test_prescription_templates.py
new file mode 100644
index 0000000..d03f2b5
--- /dev/null
+++ b/backend/tests/domain/test_prescription_templates.py
@@ -0,0 +1,147 @@
+# backend/tests/domain/test_prescription_templates.py
+"""``ImpactLevel`` 维度词表的守卫（Plan 02 Task 2；Ruling 96 起所有者在 ``exercises``）。
+
+⚠️ **枚举的住址在 Task 2 fix round 1 变过一次**（Plan02 账本 Ruling 96）：它原来住在
+``app/domain/prescription/templates.py``（P2-B1 的裁定），现与动作库的三个值对象一起
+住在 :mod:`app.domain.prescription.exercises`——它是 ``ExerciseSpec.impact_level`` 与
+``IMPACT_RANK`` 的类型，而 Task 3 的模板 dataclass 要引用动作库、不是反过来。
+``templates.py`` 只余一句 re-export。
+
+**本文件的 import 刻意仍指向 ``templates``、不改成所有者**：那是 ``templates.py`` 今天
+**唯一**的导入方（``app/domain/prescription/__init__.py`` 改成从 ``exercises`` 取了），
+而 domain 受 100% 覆盖约束——把这句改成从 ``exercises`` 导入，``templates.py`` 就没人
+import、它那 2 条语句立刻变成 ``Miss 2``。顺带它也守着「re-export 与 ``__all__`` 还在」
+——fix round 2 起这件事另有**显式**守卫：
+:func:`test_templates_module_still_reexports_impact_level`（那句 import 只在**收集期**
+响，删掉 ``__all__`` 它是不会红的）。
+**文件名不改**：计划的 File Structure 把本文件列为 ``templates.py`` 的配对测试，Task 3
+会往这里加模板 dataclass 的守卫；改名超出 Ruling 96 的范围，留给 Task 3 一并决定。
+
+前三条断言的**期望侧都是字面量**，不从被测枚举读回来跟自己比（硬规矩 #35）：取值
+``high`` / ``medium`` / ``low`` 与成员数 3 都抄自 spec §4.4 ``:239`` 的 ``exercise`` 行
+（「**``impact_level``** ∈ {``high``, ``medium``, ``low``}」，行号取 shell 口径、绑定
+commit ``fb5bddb``）。
+第 4 条（:func:`test_templates_module_still_reexports_impact_level`，fix round 2 新加）的
+期望侧同样是字面量（``["ImpactLevel"]``），实际侧是模块对象的属性与 ``is`` 同一性。
+
+⚠️ **本文件守不住什么**（硬规矩 #39）：
+
+* 它守 ``ImpactLevel`` 这个**词表本身**（下面三条），以及 ``templates.py`` 对它的那一句
+  re-export 与 ``__all__``（fix round 2 加的第 4 条，账本 Ruling 107-3）。**不守**
+  「``exercises.yaml`` 里每个动作的
+  ``impact_level`` 取值合法」——那一条住在 ``tests/test_refdata_prescription.py``
+  的 :func:`tests.test_refdata_prescription.test_every_exercise_has_a_valid_impact_level_and_targets`，
+  两侧不同源：那边的实际侧来自 YAML 文件，这边的期望侧来自本枚举。
+* 不守冲击等级之间的**序**（``high > medium > low``）：``ImpactLevel`` 继承 ``str``，
+  故它的 ``<`` 是**字典序**（``"high" < "low" < "medium"``），与冲击序无关。序关系由
+  ``test_equivalence_never_maps_to_a_higher_impact_level`` 字面写死。
+* 不守 ``templates.py`` / ``exercises.py`` 的**无 I/O**：那是
+  :mod:`tests.architecture.test_domain_purity` 的 allow-list 守卫（它扫 ``app/domain``
+  全部 ``.py``，建出本子包后扫描面自动扩大，Plan02 账本 P2-D4 亲验不会红）。
+"""
+import pytest
+
+from app.domain.prescription import exercises, templates
+from app.domain.prescription.templates import ImpactLevel
+
+
+def test_impact_level_values_match_spec_4_4_verbatim():
+    """取值与**声明序**逐字等于 spec §4.4 ``:239`` 写的那三个。
+
+    声明序是承重的：``list(ImpactLevel)`` 的顺序被
+    ``app/refdata_prescription.py`` 之外的消费者（如将来把词表印给专家审校的脚本）
+    当作展示序，而 spec 那一行的书写序就是 high → medium → low。
+    """
+    assert [member.value for member in ImpactLevel] == ["high", "medium", "low"]
+    assert len(ImpactLevel) == 3
+
+
+def test_impact_level_is_a_str_enum_so_it_round_trips_through_the_db():
+    """``ImpactLevel`` 是 ``str`` 子类：``exercise.impact_level`` 那一列是 ``String(8)``。
+
+    不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``，而漏写一处的失效形态是**静默的**：
+    SQLite 会把枚举对象按 ``str()`` 存成 ``"ImpactLevel.HIGH"``（19 字符，还会撑破
+    ``String(8)``——SQLite 不强制长度，故写侧不报错，换严格长度的后端才截断，
+    硬规矩 #18 的那个失效形态）。继承 ``str`` 之后 ``ImpactLevel.HIGH == "high"``
+    直接成立，落库与读回都是同一个字符串。
+    """
+    assert issubclass(ImpactLevel, str)
+    assert ImpactLevel.HIGH == "high"
+    assert ImpactLevel.MEDIUM == "medium"
+    assert ImpactLevel.LOW == "low"
+    # 由字符串反查成员：加载 YAML 时把字面量收敛成枚举就走这一支
+    assert ImpactLevel("medium") is ImpactLevel.MEDIUM
+
+
+def test_impact_level_rejects_a_value_outside_spec_4_4():
+    """词表外的值必须**当场炸**，不得静默变成一个第四档。
+
+    第四档（如 ``"very_high"``）的后果不在写入侧而在读取侧：spec §7.4 ``:508`` 的安全
+    后置只替换 ``impact_level: high``，一个拼错的 ``"hig"`` 会让 BMI > 30 的学生照旧
+    被安排高冲击动作，而全链路没有任何一处报错——正是 Review Focus 第 5 条要防的
+    「安全规则命中却被静默跳过」的上游形态。
+    """
+    for bad in ("very_high", "hig", "HIGH", "", "none"):
+        with pytest.raises(ValueError):
+            ImpactLevel(bad)
+
+
+def test_templates_module_still_reexports_impact_level():
+    """钉住 ``templates.py`` 的那一句 re-export 与它的 ``__all__``（账本 Ruling 107-3）。
+
+    **这条守卫存在的理由是一种「退出码 0 的静默退化」**（Ruling 103 / 硬规矩 #67 那个形态）：
+    ``templates.py`` 今天只有 **2** 条语句（``from .exercises import ImpactLevel`` 与
+    ``__all__ = ["ImpactLevel"]``；coverage 表上是 ``2 stmts / 0 branch / 100%``），而它
+    **唯一的导入方**是本文件顶部的**两句** import：``from app.domain.prescription import
+    exercises, templates``（本条守卫用）与 ``from app.domain.prescription.templates import
+    ImpactLevel``（下面三条用）。取证命令（``^`` 锚定行首，故 docstring 里的引文不会自己
+    命中自己）::
+
+        git grep -n "^from app.domain.prescription.templates import" -- backend
+
+    本轮落盘后**只命中 1 处**，就是本文件顶部那一句 ``…templates import ImpactLevel``；
+    另一句 ``from app.domain.prescription import …`` 把模式里的 ``.templates`` 去掉就数得到
+    （命中 **2** 处，另一处是 ``tests/test_refdata_prescription.py`` 的
+    ``exercises as exercises_mod``、**不含 ``templates``**）。⚠️ **不加 ``^`` 的计数不可用**：
+    同一条命令去掉锚，会把 ``templates.py`` 自己 docstring 里的散文与本 docstring 里的
+    这段引文一起算进来；把模式再松成 ``prescription.templates`` 更糟——正则里的 ``.``
+    连 ``prescription_templates`` 这个**文件名**都匹配，于是它的命中数**每改一次本文件
+    的散文就变一次**（本轮写这句话的前后就变过一次），不是一个稳定量，故不写进散文。
+    这里只留锚定后的那**一个**数；要复核请自己跑上面那条命令（硬规矩 #19/#66）。
+
+    **静默退化是怎么发生的**（本轮实测复现，报告的变异 M-B4）：下一个人完全可能把这个
+    「只有 re-export 的文件」当残留处理掉——最自然的做法不是删文件（那会在**收集期**炸、
+    响亮），而是把本文件顶部那两句 ``templates`` 的 import 都改指所有者 ``exercises``
+    （一个看起来很合理的「去中间层」清理）。那样 ``templates.py`` 就没有任何导入方了 →
+    它那 2 条语句永不执行 → ``--cov=app/domain --cov-branch`` 报 ``templates.py 2 stmts /
+    Miss 2 / 0%``（缺的是 ``37-39``）、``TOTAL 441 stmts / Miss 2 / 99%``，**而 ``pytest``
+    的退出码仍是 0**（实测 ``529 passed, 1 skipped``）：覆盖率不是断言，只有人去看那张表
+    才发现。**本条守卫堵这个口子的方式是它自己也成为一个导入方**——它引用 ``templates``
+    这个模块对象，要绕过它就得连它一起删，而删掉它本条会 ``NameError`` 而红（实测
+    ``1 failed, 530 passed``、退出码 1）。这就是 Ruling 107-3 说的「同时把 Ruling 103
+    那个口子堵上」。
+
+    **两支的主语**（硬规矩 #56）：支 1 钉 ``templates.__all__`` 的**字面内容与长度**；
+    支 2 钉 ``templates.ImpactLevel`` 与 ``exercises.ImpactLevel`` 是**同一个对象**
+    （``is``，不是 ``==``：``ImpactLevel`` 继承 ``str``，一个本地重定义的同值枚举会让
+    ``==`` 成立而 ``is`` 不成立，而那正是「re-export 被换成本地定义」的失效形态）。
+
+    **红/绿双输入**（硬规矩 #50；四个真变异本轮都实跑过，逐支真值见报告 §fr2.4）：
+    绿输入 = 今天的真实状态（两支都实跑通过）。红输入：**M-B1**（把 re-export 换成本地
+    同值的 ``class ImpactLevel`` → **只有支 2 红**，``1 failed, 530 passed``；``==`` 会
+    成立而 ``is`` 不成立，故这一支必须用 ``is``）、**M-B2**（``__all__`` 改成 ``[]`` →
+    **只有支 1 红**，``1 failed, 530 passed``。⚠️ 顶部那句 ``from … import ImpactLevel``
+    是**显式**导入、不看 ``__all__``，故它不会红——这正是需要支 1 的理由）、**M-B3**
+    （整份 ``templates.py`` 删掉 → 本文件在**收集期** ImportError、``pytest`` **退出码 2**，
+    根本跑不到覆盖率那一步）、**M-B4**（见上：两处 import 都改指 ``exercises`` → 本条
+    ``NameError`` 而红，``1 failed, 530 passed``、退出码 1）。
+
+    **本条守不住什么**（硬规矩 #39）：不守 ``ImpactLevel`` 的**取值**（那是上面三条的事），
+    也不守 ``prescription/__init__.py`` 的公开面（那 7 个名字由
+    ``tests/test_refdata_prescription.py`` 的
+    :func:`tests.test_refdata_prescription.test_prescription_public_namespace_is_pinned_verbatim`
+    钉住）。⚠️ Task 3 往 ``templates.py`` 加模板 dataclass 时，**两份 ``__all__`` 要一起改**
+    （本模块一份、``prescription/__init__.py`` 一份），届时支 1 的期望值也要跟着加。
+    """
+    assert templates.__all__ == ["ImpactLevel"]
+    assert templates.ImpactLevel is exercises.ImpactLevel
diff --git a/backend/tests/seed/test_generate.py b/backend/tests/seed/test_generate.py
index aa38747..6aa15d4 100644
--- a/backend/tests/seed/test_generate.py
+++ b/backend/tests/seed/test_generate.py
@@ -479,47 +479,99 @@ def test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises(tmp_path):
         if kind in ("outlier_corrected", "unit_normalized")
     )
 
 
 ORGANISATION_TABLES = ("semester", "teacher", "student", "course_section", "enrollment")
 DATA_TABLES = (
     "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
     "percentile_snapshot", "derived_metrics", "stratification_result",
     "daily_sync_run", "cleaning_log",
 )
+#: **参考数据表**（Plan 02 Task 2 新增的第三个分区，Plan02 账本 P2-A1）。
+#: 它既不是 ``seed_database`` 写的组织结构，也不是经适配器与管道流入的仿真业务数据，
+#: 而是「专家维护的知识资产在 DB 里的**投影**」：``exercise`` 由
+#: :func:`app.refdata_prescription.sync_exercises` 从 ``backend/data/exercises.yaml`` 灌，
+#: 唯一所有者是那份 YAML。
+#: **逐 Task 递增**：Task 3 加 ``prescription_template``，Task 9 加 ``prescription`` 与
+#: ``weekly_adjustment``（计划 ``:700`` 的 18 张表清单）。
+REFERENCE_TABLES = ("exercise",)
+
+
+def test_table_partition_is_exhaustive():
+    """三个分区必须**恰好穷尽** ``Base.metadata`` 的全部表（Plan02 账本 P2-A1）。
+
+    **这条守的是一个此前没人写下来的隐性不变量**：Plan 01 结案时
+    ``ORGANISATION_TABLES``（5 个）+ ``DATA_TABLES``（9 个）**恰好**是当时的全部 14 张表，
+    于是下面那条「``seed_database`` 只写组织结构」的守卫看起来是全覆盖的。而它其实是
+    **枚举式**的：加第 15 张表之后，新表会静默落在两个分区之外——``seed_database`` 越界
+    写它也不会红，因为那条守卫只遍历 ``DATA_TABLES``。
+
+    故本条把「穷尽」变成显式断言。它与 :func:`test_seed_database_writes_only_organisation_tables_and_is_idempotent`
+    是**一对**：本条保证「每张表都被某个分区认领」，那条保证「认领进
+    ``DATA_TABLES`` / ``REFERENCE_TABLES`` 的表 ``seed_database`` 一行都不写」。少了本条，
+    那条会对新表完全无感；少了那条，本条只是分类学。
+
+    ⚠️ **本条守不住什么**（硬规矩 #39）：它只保证「每张表都在某个分区里」，**不保证归对了
+    分区**。把 ``exercise`` 从 ``REFERENCE_TABLES`` 挪进 ``ORGANISATION_TABLES``，本条仍然
+    全绿，而下面那条会红（``assert count > 0`` 说它是组织结构、必须被 ``seed_database``
+    写入）——所以那个失效是**响亮的**，只是红在另一条上。
+    """
+    partitioned = set(ORGANISATION_TABLES) | set(DATA_TABLES) | set(REFERENCE_TABLES)
+    actual = set(models.Base.metadata.tables)
+    assert partitioned == actual, (
+        f"表分区不再穷尽。未归类的表 {sorted(actual - partitioned)}"
+        f"（新加的表必须归进三个分区之一，否则「只写组织结构」那条守卫会对它无感）；"
+        f"分区里已不存在的表 {sorted(partitioned - actual)}"
+    )
+    # 三个分区**互不相交**：一张表同时属于两个分区，会让「seed_database 必须写 / 不许写」
+    # 两条断言对同一张表给出相反的要求。用「三张清单的长度之和 == 并集大小」来查，
+    # 这样交集非空时左边会大于右边。
+    assert (
+        len(ORGANISATION_TABLES) + len(DATA_TABLES) + len(REFERENCE_TABLES)
+        == len(partitioned)
+    ), "三个分区相交了，同一张表被归了两类"
+    # 本 Task 只加 ``exercise`` 一张；抬这个数请连同计划 ``:700`` 的归属一起改
+    assert REFERENCE_TABLES == ("exercise",), REFERENCE_TABLES
 
 
 def test_seed_database_writes_only_organisation_tables_and_is_idempotent():
     """seed_database 只建组织结构；体测/体成分/问卷必须经适配器与管道流入。
 
     直接入库会绕过清洗与幂等，Task 10 的管道测试就再也测不到真实路径。
+
+    ⚠️ Plan 02 Task 2 把下面「必须为 0」那一圈的遍历对象从 ``DATA_TABLES`` 扩成
+    ``DATA_TABLES + REFERENCE_TABLES``（Plan02 账本 P2-A1）：``exercise`` 是参考数据，
+    同样不该由 ``seed_database`` 写——它的灌数据入口是
+    :func:`app.refdata_prescription.sync_exercises`。Global Constraint #10 把 ``app/seed/``
+    自 Plan 01 结案后重新冻结，故本 Task **没有**新建 ``app/seed/prescription.py``、
+    也**没有**改 ``seed_database`` 一行。
     """
     eng = create_engine("sqlite://")
     init_db(eng)
     cfg = SMALL
     with Session(eng) as session:
         seed_database(session, cfg)
         session.commit()
     with Session(eng) as session:
         assert session.scalar(select(func.count()).select_from(models.Student)) == cfg.students
         # 120 人 → ceil(120/38) = 4 个行政班（30 人/班），加 3 个分层班
         assert session.scalar(select(func.count()).select_from(models.CourseSection)) == 4 + 3
         assert session.scalar(
             select(func.count()).select_from(models.Enrollment)
         ) == 2 * cfg.students
         # 两学年各一个学期，当前学期被标记出来
         assert session.scalar(select(func.count()).select_from(models.Semester)) == len(SEMESTERS)
         current = session.scalar(
             select(models.Semester).where(models.Semester.is_current.is_(True))
         )
         assert current is not None and current.name == current_semester().name
-        for table in DATA_TABLES:
+        for table in DATA_TABLES + REFERENCE_TABLES:
             count = session.scalar(
                 select(func.count()).select_from(models.Base.metadata.tables[table])
             )
             assert count == 0, f"{table} 不该由 seed_database 写入"
         for table in ORGANISATION_TABLES:
             count = session.scalar(
                 select(func.count()).select_from(models.Base.metadata.tables[table])
             )
             assert count > 0, f"{table} 是组织结构，seed_database 必须写入"
 
diff --git a/backend/tests/test_refdata_prescription.py b/backend/tests/test_refdata_prescription.py
new file mode 100644
index 0000000..2516ad2
--- /dev/null
+++ b/backend/tests/test_refdata_prescription.py
@@ -0,0 +1,921 @@
+# backend/tests/test_refdata_prescription.py
+"""动作库两份 YAML 的加载 / 校验 / ``exercise`` 表投影（Plan 02 Task 2）。
+
+本文件是 ``backend/data/exercises.yaml`` 与 ``backend/data/exercise_equivalence.yaml``
+的**唯一守卫**，角色与 ``tests/test_refdata.py`` 对国标评分表的角色同构（Ruling 213
+的教训照搬）：这两份是体育专家手工维护的知识资产，**改一个值往往不破坏任何形状
+不变量**，只有指纹能挡住它。故本文件同时下四道闸（第 4 道是 Task 2 fix round 2 加的，
+Plan02 账本 Ruling 107；前三道的口径一个字未改）：
+
+1. **指纹**（:func:`test_exercises_yaml_fingerprint_is_pinned` /
+   :func:`test_equivalence_yaml_fingerprint_is_pinned`）——任何字节改动都红；
+2. **跨文件不变量**（等价映射只指向存在的动作、**永不升冲击**、每个 ``high`` 都有
+   ``low`` 替身）——这三条是 spec §7.4 安全后置的成立前提；
+3. **字面钉住的常量**（``volume_reduction`` 的两个系数、RFC 2606 占位符 URL 形状、
+   四个无 CHECK 约束列的列宽）——两侧不同源（硬规矩 #35）。
+4. **domain 公开面**（``IMPACT_RANK`` 的秩值、``app.domain.prescription.__all__`` 的 7 个
+   名字）——同样字面钉住、两侧不同源。⚠️ 这一道**不是**在守 YAML：它守的是 Ruling 96 搬进
+   ``app/domain/prescription/`` 那批对象的公开面，寄住在本文件是因为本文件已经是那批对象的
+   消费者（``IMPACT_DESCENDING`` 与 ``IMPACT_RANK`` 的两侧不同源就在这里对账）。**Task 3
+   建 ``tests/domain/test_prescription_exercises.py`` 时这两条应当搬过去归位**（账本
+   Ruling 107-1 已把「``lookup()`` 的分支测试住在 domain 测试目录之外」转成 Task 3 的预检
+   项，同一次搬迁即可）。
+
+⚠️ **本文件守不住什么**（硬规矩 #39）：
+
+* **不守「模板 YAML 里的 ``exercise_ref`` 都存在」**——那个测试归 Task 3（Plan02 账本
+  P2-C1：原文把它列进本 Task 的变异 ②，而它在本 Task 里根本不存在）。今天删掉一个
+  没人引用的 ``exercise_ref``，本文件**只有指纹会红**。
+* **不守 ``impact_level`` 与模板 block 里那份副本一致**——同上，归 Task 3 的加载器
+  （P2-B2 裁定 ``exercises.yaml`` 是唯一所有者）。
+* **不守 ``sync_exercises`` 被谁调用**：本 Task 刻意**不**接进 ``seed_database``
+  （P2-A1：那会违反 Global Constraint #10 的 ``app/seed/`` 冻结，并撞上
+  ``tests/seed/test_generate.py`` 的「只写组织结构五张表」守卫）。谁在生产路径上灌
+  ``exercise`` 表，是 Task 9/10 接管道时的事。
+"""
+import ast
+import hashlib
+import pathlib
+import re
+import types
+
+import pytest
+from sqlalchemy import create_engine, func, select
+from sqlalchemy.exc import IntegrityError
+from sqlalchemy.orm import Session
+
+from app import refdata_prescription as rp
+from app.db.models.prescription import Exercise
+from app.db.session import init_db
+from app.domain import prescription as prescription_pkg
+from app.domain.indicators import ITEM_BUCKET
+from app.domain.prescription import exercises as exercises_mod
+from app.domain.prescription.exercises import (
+    EquivalenceMapping,
+    EquivalenceTable,
+    IMPACT_RANK,
+    ImpactLevel,
+)
+
+# ---------------------------------------------------------------------------
+# 期望侧的字面量（一律不从被测 YAML 读回，硬规矩 #35）
+# ---------------------------------------------------------------------------
+
+#: ``exercises.yaml`` 的 sha256 前 16 位（大写十六进制），**行尾归一化为 LF 之后**计算。
+#: 归一化的理由与 ``tests/test_refdata.py`` 的 ``STANDARD_FINGERPRINT`` 完全相同
+#: （Ruling 231）：``core.autocrlf`` 在 Git for Windows 上缺省为 ``true``，裸字节哈希会
+#: 随平台配置漂移、新克隆必红。``backend/data/*.yaml`` 已由 ``.gitattributes:14`` 钉成
+#: ``eol=lf``，故这里的归一化是**第二道保险**而不是唯一依赖。
+EXERCISES_FINGERPRINT = "A6A000F58815FCBB"
+
+#: ``exercise_equivalence.yaml`` 的同口径指纹。
+EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"
+
+#: ``targets`` 的取值域 = ``ITEM_BUCKET`` 的三个桶名（P2-A4）。
+#: ⚠️ **不能写成 ``set(ITEM_BUCKET.values())``**：那个集合有 **4** 个元素、含 ``None``
+#: （``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶），照字面写
+#: 会把 ``None`` 放进取值域、并让一个空 ``targets`` 悄悄合法。下面
+#: :func:`test_target_domain_is_the_three_bucket_names_not_the_raw_values` 把这件事钉住。
+TARGET_DOMAIN = frozenset(v for v in ITEM_BUCKET.values() if v is not None)
+
+#: 冲击等级的**降序**（高 → 低）。字面写死，不从 ``ImpactLevel`` 派生：枚举继承 ``str``，
+#: 它的 ``<`` 是字典序（``"high" < "low" < "medium"``），与冲击序无关，故序关系必须由
+#: 消费方显式声明。生产侧那份在 ``app/domain/prescription/exercises.py`` 的
+#: ``IMPACT_RANK``（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
+#: ``app/refdata_prescription.py``），两侧不同源，改坏任何一侧都会让
+#: :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红。
+IMPACT_DESCENDING = ("high", "medium", "low")
+
+#: spec §7.4 ``:508-509`` 的两个走等价表的触发条件（``:510`` 的「体脂率异常」走模板
+#: ``addons``、**不走等价表**，故 ``when`` 只有这两个取值，Plan02 账本 P2-C3 亲验）。
+SPEC_7_4_TRIGGERS = frozenset({"bmi_over_30", "muscle_low_p10"})
+
+#: RFC 2606 保留 TLD ``.invalid`` 保证不可解析，故占位符不会被误当成真链接。
+#: 用户已裁定：**不编造真实链接**，真实视频源待 spec §14 登记后由项目组提供。
+PLACEHOLDER_PREFIX = "https://example.invalid/exercise/"
+
+
+def _fingerprint(path: pathlib.Path) -> str:
+    """行尾归一化为 LF 之后取 sha256 前 16 位（大写）。口径同 ``tests/test_refdata.py``。"""
+    return hashlib.sha256(
+        path.read_bytes().replace(b"\r\n", b"\n")
+    ).hexdigest()[:16].upper()
+
+
+@pytest.fixture
+def session():
+    """内存库会话。**刻意不用磁盘库**：``backend/pe.db`` 是本 Task 的禁区。"""
+    eng = create_engine("sqlite://")
+    init_db(eng)
+    with Session(eng) as s:
+        yield s
+
+
+def _write_yaml(tmp_path: pathlib.Path, text: str, name: str = "exercises.yaml") -> pathlib.Path:
+    """把一段 YAML 字面量按 LF 落到 ``tmp_path``，返回路径。"""
+    path = tmp_path / name
+    path.write_text(text, encoding="utf-8", newline="\n")
+    return path
+
+
+GOOD_EXERCISE_YAML = """\
+interval_run:
+  name: 间歇跑
+  video_url: https://example.invalid/exercise/interval_run
+  impact_level: high
+  targets: [endurance]
+  equipment: none
+bodyweight_resistance:
+  name: 自重抗阻
+  video_url: https://example.invalid/exercise/bodyweight_resistance
+  impact_level: low
+  targets: [strength]
+  equipment: mat
+"""
+
+
+# ---------------------------------------------------------------------------
+# 闸 1：指纹
+# ---------------------------------------------------------------------------
+
+
+def test_exercises_yaml_fingerprint_is_pinned():
+    """**改动作库必须先改这条测试**——「知识资产变更需被显式承认」的闸门。
+
+    期望值 :data:`EXERCISES_FINGERPRINT` 是测试里的字面量，实际值现算自磁盘，两侧
+    不同源（硬规矩 #35）。红了的正确处置**不是**把新哈希抄进来就算了：先确认这次改动
+    是有意的（专家审校 / Task 3 追加 ``exercise_ref``），再更新本常量；若改动同时动了
+    ``impact_level``，还要复核
+    :func:`test_equivalence_never_maps_to_a_higher_impact_level` 与
+    :func:`test_every_high_impact_exercise_has_a_low_substitute` 是否仍然成立。
+
+    ⚠️ Plan 02 Task 3 被**明确允许**往 ``exercises.yaml`` 追加 ``exercise_ref``（简报
+    Step 1），届时它必须同步更新本常量并在自己的报告里列出追加了哪些、为什么。
+    """
+    path = rp.DATA_DIR / rp.EXERCISES_FILENAME
+    digest = _fingerprint(path)
+    assert digest == EXERCISES_FINGERPRINT, (
+        f"动作库被改动了：sha256 前 16 位是 {digest}，钉住的是 {EXERCISES_FINGERPRINT}。"
+        f"这份 YAML 是专家维护的知识资产、且是 exercise_ref 与 impact_level 的唯一所有者，"
+        f"改动必须被显式承认——确认改动有意之后更新本常量"
+    )
+
+
+def test_equivalence_yaml_fingerprint_is_pinned():
+    """等价映射表的同口径指纹。
+
+    **为什么这一份也要指纹**（简报 Step 2 只点了 ``exercises.yaml``，本条是实现者按
+    Ruling 213 的教训补的）：把某条映射的 ``to`` 从一个 ``low`` 动作换成**另一个**
+    ``low`` 动作，不破坏下面任何一条形状不变量——目标仍存在、仍不升冲击、``high`` 仍
+    有 ``low`` 替身、``version`` 仍非空——**六条语义测试会全绿**。这与终审 M4（改评分表
+    一处 ``raw_value``、全仓只有指纹红）是同一个失效形态。
+    """
+    path = rp.DATA_DIR / rp.EQUIVALENCE_FILENAME
+    digest = _fingerprint(path)
+    assert digest == EQUIVALENCE_FINGERPRINT, (
+        f"等价映射表被改动了：sha256 前 16 位是 {digest}，钉住的是 {EQUIVALENCE_FINGERPRINT}。"
+        f"这份表驱动 spec §7.4 的安全替换，且它的 version 会被写进 "
+        f"prescription.safety_substitutions——改动必须被显式承认，并考虑是否要升 version"
+    )
+
+
+# ---------------------------------------------------------------------------
+# 闸 2：取值域与跨文件不变量
+# ---------------------------------------------------------------------------
+
+
+def test_target_domain_is_the_three_bucket_names_not_the_raw_values():
+    """:data:`TARGET_DOMAIN` 的构造方式本身要被钉住（P2-A4）。
+
+    这条守的是**守卫自己的口径**：``set(ITEM_BUCKET.values())`` 与
+    ``frozenset(v for v in ITEM_BUCKET.values() if v is not None)`` 差一个 ``None``，
+    而差这一个 ``None`` 的后果是「空 ``targets`` 悄悄合法」——因为校验写法通常是
+    ``set(targets) <= DOMAIN``，``None`` 在不在 ``DOMAIN`` 里对**非空** ``targets`` 毫无
+    影响，只有「一个动作不瞄准任何素质桶」这种真正该拒绝的输入才暴露差别。
+    """
+    raw_values = set(ITEM_BUCKET.values())
+    assert len(raw_values) == 4, sorted(repr(v) for v in raw_values)
+    assert None in raw_values, "BMI 不归桶（Plan01 Ruling 19），故 None 必在其中"
+    assert TARGET_DOMAIN == {"endurance", "strength", "speed_flexibility"}
+    assert None not in TARGET_DOMAIN
+
+
+def test_every_exercise_has_a_valid_impact_level_and_targets():
+    """每个动作的 ``impact_level`` 与 ``targets`` 都落在**代码侧**的取值域里。
+
+    两侧不同源：期望侧来自 :class:`ImpactLevel`（domain 枚举）与 ``ITEM_BUCKET``
+    （Plan 01 的桶化口径），实际侧来自 ``exercises.yaml``。先断言期望侧等于 spec §4.4
+    与 §6.1 的字面词表，免得「枚举本身被改坏」时两侧一起漂（硬规矩 #35）。
+    """
+    assert {level.value for level in ImpactLevel} == {"high", "medium", "low"}
+    assert TARGET_DOMAIN == {"endurance", "strength", "speed_flexibility"}
+
+    library = rp.load_exercises()
+    assert library, "动作库为空：Task 3 的 18 套模板将无 ref 可引"
+    offenders = []
+    for ref, spec in library.items():
+        if spec.impact_level not in set(ImpactLevel):
+            offenders.append(f"{ref}.impact_level={spec.impact_level!r}")
+        if not spec.targets:
+            offenders.append(f"{ref}.targets 为空：一个不瞄准任何素质桶的动作无法被模板选用")
+        unknown = spec.targets - TARGET_DOMAIN
+        if unknown:
+            offenders.append(f"{ref}.targets 含非桶名 {sorted(unknown)}")
+        if spec.impact_level.value not in IMPACT_DESCENDING:
+            offenders.append(f"{ref}.impact_level={spec.impact_level.value!r} 不在冲击序里")
+    assert offenders == [], "\n".join(offenders)
+
+
+def test_exercise_refs_are_snake_case_and_unique_keys():
+    """``ref`` 的形状与唯一性。
+
+    唯一性由 YAML 的映射语义保证吗？**不保证**：PyYAML 的 ``safe_load`` 对重复键是
+    **后者覆盖前者、不报错**（实测 ``yaml.safe_load("a: 1\\na: 2") == {"a": 2}``）。
+    于是「专家复制一段忘了改 ref」会让一个动作**静默消失**——它从键集里被顶掉，
+    而 Task 3 的模板若引用了它就会在加载时炸（那还是好的），若没引用就无人发现。
+    本条用**原始文本**数一遍顶层键出现次数，与解析后的键集对账，两侧不同源。
+    """
+    path = rp.DATA_DIR / rp.EXERCISES_FILENAME
+    text = path.read_text(encoding="utf-8")
+    library = rp.load_exercises()
+
+    top_level_keys = [
+        line.split(":", 1)[0] for line in text.splitlines()
+        if line and not line[0].isspace() and not line.lstrip().startswith("#")
+        and ":" in line
+    ]
+    assert len(top_level_keys) == len(set(top_level_keys)), (
+        "exercises.yaml 有重复的顶层键，PyYAML 会静默用后者覆盖前者："
+        f"{sorted(k for k in top_level_keys if top_level_keys.count(k) > 1)}"
+    )
+    assert set(top_level_keys) == set(library), (
+        f"解析出的键集与文本里的顶层键不符：文本多 "
+        f"{sorted(set(top_level_keys) - set(library))}、少 "
+        f"{sorted(set(library) - set(top_level_keys))}"
+    )
+    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", ref) for ref in library), sorted(
+        ref for ref in library if not re.fullmatch(r"[a-z][a-z0-9_]*", ref)
+    )
+
+
+def test_video_urls_are_rfc2606_placeholders_keyed_by_ref():
+    """视频 URL 一律是 ``https://example.invalid/exercise/<ref>`` 形状的占位符。
+
+    用户已裁定「**不编造真实链接**」：``.invalid`` 是 RFC 2606 保留 TLD，DNS 保证不可
+    解析，故占位符不可能被误当成一个真能打开的视频源，也不会指向某个恰好注册了的
+    域名。spec §7.3 ``:499`` 的装配第 5 步会把这个 URL 填进训练包的二维码，所以它的
+    「假」必须是**响亮可识别**的假。
+
+    ⚠️ 项目组提供真实视频源时**本条会变红，那是设计意图**：换 URL 是一次需要被显式
+    承认的知识资产变更（同指纹那两条的处置口径），届时要连带更新本条与指纹常量。
+    """
+    library = rp.load_exercises()
+    offenders = [
+        f"{ref}: {spec.video_url!r}"
+        for ref, spec in library.items()
+        if spec.video_url != f"{PLACEHOLDER_PREFIX}{ref}"
+    ]
+    assert offenders == [], "视频 URL 不是约定的占位符形状：\n" + "\n".join(offenders)
+
+
+def test_equivalence_table_only_maps_to_existing_exercises():
+    """等价映射的两端都必须在动作库里。
+
+    失效形态是实打实的：``to`` 指向一个不存在的 ref 时，spec §7.4 的安全替换会产出一个
+    **装配不出来的动作**——Task 7 拿它去查动作库得 ``None``，于是要么当场 ``KeyError``
+    （好在装配到某个学生时才炸，而不是在专家改 YAML 时炸），要么被写成一次静默跳过，
+    而那正是 spec §7.4 ``:514`` 明令禁止的。``from`` 指向不存在的 ref 则更隐蔽：那条
+    映射永远匹配不上，等于**该动作没有低冲击替身**，BMI > 30 的学生照旧被安排它。
+    """
+    library = rp.load_exercises()
+    table = rp.load_equivalence()
+    offenders = [
+        f"{m.from_ref} -> {m.to_ref}（{'from' if m.from_ref not in library else ''}"
+        f"{'/' if m.from_ref not in library and m.to_ref not in library else ''}"
+        f"{'to' if m.to_ref not in library else ''} 不在动作库）"
+        for m in table.mappings
+        if m.from_ref not in library or m.to_ref not in library
+    ]
+    assert offenders == [], "等价映射指向动作库里不存在的 ref：\n" + "\n".join(offenders)
+
+
+def test_equivalence_never_maps_to_a_higher_impact_level():
+    """**安全属性的核心**：等价替换只能持平或降低冲击，绝不上升。
+
+    序关系 ``high > medium > low`` **字面写死**在 :data:`IMPACT_DESCENDING` 里，不从
+    ``ImpactLevel`` 派生（它继承 ``str``，字典序是 ``high < low < medium``，与冲击序
+    完全无关）。生产侧 ``app/domain/prescription/exercises.py`` 的 ``IMPACT_RANK`` 是
+    同一序的第二份、供 :meth:`EquivalenceTable.lookup` 使用；两份刻意不同源，改坏任何
+    一份本条都红（硬规矩 #35）。
+
+    这条为什么是核心：spec §7.4 的两个触发（BMI > 30 / 肌肉量 < P10）本身就是**关节
+    负荷过高**的医学指征，一次「换成更高冲击」的替换会把安全后置处理器变成伤害放大器，
+    而它披着「已按映射表处理过」的外衣，教师端看不出异常。
+    """
+    library = rp.load_exercises()
+    table = rp.load_equivalence()
+    rank = {value: index for index, value in enumerate(IMPACT_DESCENDING)}
+
+    offenders = []
+    for mapping in table.mappings:
+        source = library[mapping.from_ref].impact_level.value
+        target = library[mapping.to_ref].impact_level.value
+        if rank[target] < rank[source]:
+            offenders.append(
+                f"{mapping.from_ref}({source}) -> {mapping.to_ref}({target}) 升了冲击"
+            )
+        # 映射自己声明的 max_impact 必须与 to 的真实冲击一致：不一致意味着这张表在
+        # 撒谎，而 lookup 正是按 max_impact 过滤的（它不看动作库）。
+        if mapping.max_impact.value != target:
+            offenders.append(
+                f"{mapping.from_ref} -> {mapping.to_ref} 声明 max_impact="
+                f"{mapping.max_impact.value}，而 {mapping.to_ref} 的真实冲击是 {target}"
+            )
+    assert offenders == [], "\n".join(offenders)
+
+
+def test_equivalence_table_has_a_version():
+    """``version`` 必须是非空字符串。
+
+    spec §7.4 ``:512`` 要求每次替换把「原动作、新动作、触发条件、**映射表版本号**」写进
+    ``prescription.safety_substitutions``。没有版本号，一张已生成的处方就无法回答
+    「当时是按哪一版映射表替换的」——而这份表由专家维护、会改，可追溯性（spec §1.3）
+    正依赖这个字段。空串也要拒：它能通过 ``is not None``，写进 JSON 后却什么都说明不了。
+    """
+    table = rp.load_equivalence()
+    assert isinstance(table.version, str)
+    assert table.version.strip() != "", "version 为空：safety_substitutions 将记不下映射表版本"
+    # 字面钉住当前版本，升版必须是一次显式改动
+    assert table.version == "1.0"
+
+
+def test_every_high_impact_exercise_has_a_low_substitute():
+    """**每个** ``high`` 动作都必须有一个 ``low`` 等价物，且两个触发条件各有一个。
+
+    ⚠️ 测试名按**描述**改过（Plan02 账本 P2-C2：原文叫
+    ``test_every_impact_level_has_at_least_one_low_substitute``，名字说「每个 impact
+    level」而描述只要求 ``high``）。要求 ``medium`` 也备一个 ``low`` 替身是**过紧的
+    守卫**：spec §7.4 ``:508-509`` 的两个触发都只替换 ``impact_level: high`` 的动作，
+    给永不发生的场景写断言正是硬规矩 #50 的反面，而它的代价是真的——为了喂饱这条断言
+    就得往 ``exercise_equivalence.yaml`` 塞一堆永不被查到的映射，把一张专家审校表变成
+    噪声。
+
+    反过来这条**必须**存在：一个 ``high`` 动作没有 ``low`` 替身时，BMI > 30 的安全规则
+    会命中但无解，直接落进 Review Focus 第 5 条的 ``needs_review`` 路径。那条路径本身是
+    对的（spec §7.4 ``:514``「宁可不自动，也不要自动错」），但**因为动作库缺条目**而
+    天天触发它，等于把可自动处理的学生全推给人工复核。
+    """
+    library = rp.load_exercises()
+    table = rp.load_equivalence()
+
+    substitutes: dict[str, dict[str, str]] = {}
+    for mapping in table.mappings:
+        substitutes.setdefault(mapping.from_ref, {})[mapping.when] = mapping.to_ref
+
+    offenders = []
+    high_refs = sorted(
+        ref for ref, spec in library.items() if spec.impact_level is ImpactLevel.HIGH
+    )
+    assert high_refs, "动作库里没有任何 high 冲击动作：本条将空转全绿"
+    for ref in high_refs:
+        by_trigger = substitutes.get(ref, {})
+        for trigger in sorted(SPEC_7_4_TRIGGERS):
+            target = by_trigger.get(trigger)
+            if target is None:
+                offenders.append(f"{ref}（high）缺 when={trigger} 的等价物")
+            elif library[target].impact_level is not ImpactLevel.LOW:
+                offenders.append(
+                    f"{ref}（high）在 when={trigger} 下映射到 {target}，"
+                    f"而它的冲击是 {library[target].impact_level.value}、不是 low"
+                )
+    assert offenders == [], "\n".join(offenders)
+
+
+def test_equivalence_when_values_are_exactly_the_two_spec_7_4_triggers():
+    """``when`` 的取值域恰好是 spec §7.4 走等价表的那两个触发。
+
+    spec §7.4 ``:510`` 的第三个触发（体脂率异常）走的是「追加模板 ``addons`` 中的能量
+    消耗模块」，**不查等价表**（Plan02 账本 P2-C3 亲验）。故 ``when`` 出现第三个取值
+    就意味着有人在等价表里实现了一个不属于它的机制，而 Task 7 的消费端永远不会传它
+    ——那条映射是死代码，且它占的位置会让人以为第三个触发也被覆盖了。
+    """
+    table = rp.load_equivalence()
+    observed = {mapping.when for mapping in table.mappings}
+    assert observed == SPEC_7_4_TRIGGERS, (
+        f"when 的取值域应为 {sorted(SPEC_7_4_TRIGGERS)}，实到 {sorted(observed)}"
+    )
+    assert set(table.volume_reduction) == SPEC_7_4_TRIGGERS, (
+        f"volume_reduction 的键应恰好是两个触发，实到 {sorted(table.volume_reduction)}"
+    )
+
+
+def test_volume_reduction_coefficients_are_pinned_verbatim():
+    """两个跑量下调系数**字面钉住**（Plan02 Ruling 7）。
+
+    ⚠️ **这两个数在 spec 里没有出处**（Plan02 账本 P2-A3）：spec §7.4 ``:508`` 只写
+    「跑量**按映射表下调**」、没给任何数，``:509``（肌肉量 < P10）写「同上」。spec 里
+    唯一出现的「系数 0.8」在 ``:604``，那是**预警触发的减量 20%**
+    （``weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)``，属 Plan 03），与 §7.4 的
+    安全后置跑量下调是**两个不同机制**；``0.9`` 在 spec 里根本没有对应物。故本条期望侧
+    是「**本设计的默认规定**」，已登记进 spec §14 第 28 项与 YAML 注释；Task 7 消费时
+    **不得把它们当成 spec 条文引用**。
+
+    系数为什么必须 < 1 且 > 0：> 1 是「安全触发反而加量」，<= 0 是把训练量清零、
+    处方名存实亡。这两条也在这里一并钉住，免得有人把 0.8 改成 8。
+    """
+    table = rp.load_equivalence()
+    assert table.volume_reduction["bmi_over_30"] == 0.8
+    assert table.volume_reduction["muscle_low_p10"] == 0.9
+    for trigger, factor in table.volume_reduction.items():
+        assert isinstance(factor, float), f"{trigger} 的系数应是 float，实为 {type(factor)}"
+        assert 0.0 < factor < 1.0, f"{trigger} 的系数 {factor} 不在 (0, 1) 内"
+
+
+def test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable():
+    """:meth:`EquivalenceTable.lookup` 的三条语义，各带一个「应当红」与「应当绿」的输入。
+
+    硬规矩 #50：设计守卫必须同时构造两种输入并都跑。这里
+    ``ImpactLevel.LOW`` 与 ``ImpactLevel.MEDIUM`` 两个上限对**同一张合成表**给出不同
+    答案，才证明 ``impact_ceiling`` 这个参数真的被用上了（否则它可以被删掉而全部测试
+    仍然绿）。合成表是必要的：真实的 ``exercise_equivalence.yaml`` 里每条映射的
+    ``max_impact`` 都是 ``low``，用它无法区分「上限被尊重」与「上限被忽略」。
+    """
+    table = rp.load_equivalence()
+    # 真表：high 动作在三个上限下都能查到替身（low <= 任何上限）
+    assert table.lookup("interval_run", ImpactLevel.LOW) == "stationary_cycling"
+    assert table.lookup("interval_run", ImpactLevel.MEDIUM) == "stationary_cycling"
+    assert table.lookup("interval_run", ImpactLevel.HIGH) == "stationary_cycling"
+    # 真表：没有映射的 ref → None（Task 7 据此走 needs_review，spec §7.4:514）
+    assert table.lookup("challenge_task", ImpactLevel.LOW) is None
+    assert table.lookup("__不存在的 ref__", ImpactLevel.LOW) is None
+
+    # 合成表：max_impact=medium 的映射在 LOW 上限下**必须查不到**
+    synthetic = EquivalenceTable(
+        version="synthetic",
+        mappings=(
+            EquivalenceMapping(
+                from_ref="a", to_ref="b",
+                max_impact=ImpactLevel.MEDIUM, when="bmi_over_30",
+            ),
+        ),
+        volume_reduction={},
+    )
+    assert synthetic.lookup("a", ImpactLevel.MEDIUM) == "b"
+    assert synthetic.lookup("a", ImpactLevel.HIGH) == "b"
+    assert synthetic.lookup("a", ImpactLevel.LOW) is None
+
+
+def test_impact_rank_values_are_pinned_verbatim():
+    """:data:`IMPACT_RANK` 的**秩值本身**被字面钉住（Plan02 账本 Ruling 107-2）。
+
+    ``IMPACT_RANK`` 自 Ruling 96 起是 domain 的**公开面**（``from app.domain.prescription
+    import IMPACT_RANK`` 可用），而 :meth:`EquivalenceTable.lookup` 的全部判据就是
+    ``IMPACT_RANK[mapping.max_impact] >= IMPACT_RANK[impact_ceiling]``。**秩值整体对调会把
+    「安全替换」变成「升冲击替换」**：spec §7.4 的两个触发（BMI > 30 / 肌肉量 < P10）本身
+    就是关节负荷过高的医学指征，而换出来的动作披着「已按映射表处理过」的外衣，教师端看不出
+    异常——与 :func:`test_equivalence_never_maps_to_a_higher_impact_level` 防的是同一件事，
+    只是那一条从**数据**侧查（映射表里有没有升冲击的行）、本条从**序本身**查。
+
+    今天看着它的本来只有两条**间接**守卫：上面那条（用测试侧字面的 :data:`IMPACT_DESCENDING`）
+    与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
+    （用合成表的三个上限）。fix round 1 的变异 M-B（``HIGH: 0 ↔ LOW: 2`` 对调）实测只让
+    **其中 1 条**红（账本 Ruling 108），而且红的不是「秩值被改了」这件事本身。本条把它变成
+    **直接**的红：秩值一改，支 1 就开火。
+
+    **期望侧字面写死**（硬规矩 #35）：``0`` / ``1`` / ``2`` 三个整数是抄进本测试的，
+    **不从 ``ImpactLevel`` 派生**（它继承 ``str``，``sorted(ImpactLevel)`` 给的是字典序
+    ``high < low < medium``，与冲击序无关），也**不从 ``IMPACT_RANK`` 自己读回来跟自己比**
+    （那样两侧同源，秩值整体对调也恒等成立）。
+
+    **红/绿双输入**（硬规矩 #50）：绿输入 = 今天的真值（支 1、支 2、支 3 都实跑通过）；
+    红输入 = Task 7 的安全后置会撞上的**反方向**（支 4：拿 high 的替身去顶 low 的上限，
+    必须判「不可以」）。只有支 3 的话，把三个秩值改成同一个数也能全绿。改生产码的真变异
+    本轮实跑过两个（逐支真值见报告 §fr2.4）：**M-A1** = ``HIGH: 0 ↔ LOW: 2`` 对调 →
+    **四支全部不成立**、``2 failed, 529 passed``（另一条红的是
+    :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`；
+    fix round 1 的同一个变异只有 ``1 failed``，故**本条正是新增的那一条红**）。
+    **M-A2** = 三个秩值全改成 ``0``（序被抹平）→ **支 2 与支 3 仍是绿的**，只有支 1 与
+    支 4 不成立、``2 failed, 529 passed``。这就是支 4 存在的理由：序被抹平时正方向那一支
+    抓不到东西。
+
+    **四支的主语**（硬规矩 #56）：支 1 = 整个字典的字面值；支 2 = 按秩排出来的成员序与
+    测试侧那份**独立**的降序元组 :data:`IMPACT_DESCENDING` 交叉（两侧不同源）；
+    支 3 = 正方向可替换；支 4 = 反方向不可替换。
+
+    **本条守不住什么**（硬规矩 #39）：它钉**秩值**，不钉「``lookup`` 用 ``>=`` 而不是
+    ``>``」——那一支由上面那条 lookup 测试看着（fix round 1 的变异 M-A 打的是它）。故
+    M-A 与本条的变异打的是**不同断言分支**（硬规矩 #65）。它也没有独立的一支钉「键集恰好
+    等于 ``ImpactLevel`` 的成员集」：那件事由支 1 的字面字典顺带钉住（少一个键或多一个键
+    都会让 ``==`` 不成立）。
+    """
+    # 支 1：整个字典的字面值（键是枚举成员、值是字面整数）
+    assert IMPACT_RANK == {
+        ImpactLevel.HIGH: 0,
+        ImpactLevel.MEDIUM: 1,
+        ImpactLevel.LOW: 2,
+    }
+    # 支 2：按秩升序排出来的成员序，必须等于测试侧独立声明的降序元组
+    descending = [level.value for level in sorted(IMPACT_RANK, key=IMPACT_RANK.__getitem__)]
+    assert descending == list(IMPACT_DESCENDING)
+    # 支 3（绿输入）：秩越大冲击越低，故 low 的替身可以顶 high 的上限
+    assert IMPACT_RANK[ImpactLevel.LOW] >= IMPACT_RANK[ImpactLevel.HIGH]
+    # 支 4（红输入）：反过来必须不成立，否则「升冲击替换」会被判成合法
+    assert not IMPACT_RANK[ImpactLevel.HIGH] >= IMPACT_RANK[ImpactLevel.LOW]
+
+
+# ---------------------------------------------------------------------------
+# 闸 3：ORM 侧（列宽 / 约束 / 投影）
+# ---------------------------------------------------------------------------
+
+
+def test_exercise_string_column_widths_fit_the_yaml_values():
+    """四个**没有** ``_in_domain`` CHECK 的列，列宽必须容得下 YAML 里的实际最长值。
+
+    ⚠️ **Plan02 账本 P2-A5**：``tests/db/test_models.py`` 的
+    ``test_string_column_widths_fit_their_value_domains`` 是**自描述**的（从
+    ``_in_domain`` 生成的 ``column IN (...)`` CHECK 文本反解取值域），故它**只看得见
+    带 CHECK 的列**。``Exercise`` 的 5 个 ``String(n)`` 列里只有 ``impact_level`` 有
+    CHECK，``ref`` / ``name`` / ``video_url`` / ``equipment`` 的取值域不是封闭集合、
+    **完全不被那道测试覆盖**，只能在这里另写。
+
+    两侧不同源：期望侧是 ORM 声明的 ``.type.length``，实际侧从 ``exercises.yaml`` 现读。
+    SQLite **不强制** ``VARCHAR`` 长度，故溢出在本仓的测试里永远不报错——Ruling 144 的
+    ``derived_metrics.trend String(16)`` 就是这样漏了 7 个任务（``"insufficient_data"``
+    是 17 字符），换 MySQL / PostgreSQL 会截断，且**炸在读侧不在写侧**。
+    """
+    library = rp.load_exercises()
+    longest = {
+        "ref": max((spec.ref for spec in library.values()), key=len),
+        "name": max((spec.name for spec in library.values()), key=len),
+        "video_url": max((spec.video_url for spec in library.values()), key=len),
+        "equipment": max((spec.equipment for spec in library.values()), key=len),
+    }
+    offenders = []
+    for column_name, value in sorted(longest.items()):
+        width = Exercise.__table__.c[column_name].type.length
+        if width is None or width < len(value):
+            offenders.append(
+                f"exercise.{column_name} 声明 String({width})，"
+                f"YAML 里最长的却是 {value!r}（{len(value)} 字符）"
+            )
+    assert offenders == [], "列宽容不下取值域（严格长度的后端会静默截断）：\n" + "\n".join(offenders)
+    # 守卫自己也得有牙：四个列都真的被量到了，不是一个空循环
+    assert len(longest) == 4, sorted(longest)
+
+
+def test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum():
+    """ORM 的类常量与 domain 枚举是同一个词表（Global Constraint #3 的漂移测试）。
+
+    ``Exercise.IMPACT_LEVELS`` 是 SQL CHECK 约束的**唯一真相**（约束文本由
+    :func:`app.db.models._in_domain` 从它生成，见 ``app/db/models/__init__.py`` 的
+    约定 2），:class:`ImpactLevel` 是 Python 侧的唯一真相。两份必须逐字相同，否则
+    一侧放行、另一侧拒收，而失效发生在离真因一整个批处理周期之外的读侧。
+    """
+    assert Exercise.IMPACT_LEVELS == {level.value for level in ImpactLevel}
+    assert Exercise.IMPACT_LEVELS == {"high", "medium", "low"}
+
+
+def test_exercise_ref_is_unique_at_the_db_level(session):
+    """``exercise.ref`` 唯一：它是 ``sync_exercises`` 的幂等键，也是模板引用的目标。
+
+    没有这条约束，一次「upsert 的查询没命中」就会插出第二行同 ref 的动作，而
+    ``select(Exercise).where(ref == ...)`` 随后返回哪一行取决于行序——训练包里的视频
+    二维码因此可能在两次装配之间换掉，且没有任何一处报错。
+    """
+    session.add(Exercise(ref="interval_run", name="间歇跑",
+                         video_url="https://example.invalid/exercise/interval_run",
+                         impact_level="high", targets=["endurance"], equipment="none"))
+    session.flush()
+    session.add(Exercise(ref="interval_run", name="间歇跑（重复）",
+                         video_url="https://example.invalid/exercise/interval_run",
+                         impact_level="high", targets=["endurance"], equipment="none"))
+    with pytest.raises(IntegrityError):
+        session.flush()
+
+
+def test_exercise_impact_level_check_rejects_unknown_value(session):
+    """SQL 层的 CHECK 真的在拦：``impact_level`` 写 ``"very_high"`` 必须 ``IntegrityError``。
+
+    这条与 :func:`test_impact_level_vocabulary_agrees_with_the_domain_enum` 分工不同：
+    那条比的是**两份词表一致**，这条验的是**约束真的被建进 DDL 并生效**。少一条就会漏：
+    词表一致但 ``__table_args__`` 忘了挂 ``_in_domain``，Python 侧全绿而数据库照收脏值。
+    """
+    session.add(Exercise(ref="probe", name="探针",
+                         video_url="https://example.invalid/exercise/probe",
+                         impact_level="very_high", targets=["endurance"], equipment="none"))
+    with pytest.raises(IntegrityError):
+        session.flush()
+
+
+def test_sync_exercises_projects_every_ref_and_is_idempotent(session):
+    """``sync_exercises`` 把 YAML 投影成 ``exercise`` 行，重跑不翻倍、返回行数恒定。
+
+    **只在内存库会话里验**（Plan02 账本 D3）：``backend/pe.db`` 与 ``backend/data/seed/``
+    是本 Task 的禁区，故这里绝不跑 ``python -m app.seed.generate`` 一类的 CLI。
+    """
+    library = rp.load_exercises()
+    written = rp.sync_exercises(session)
+    session.commit()
+    assert written == len(library)
+    # **下界**而不是 ``== 23``：条目数的精确值已经由
+    # :func:`test_exercises_yaml_fingerprint_is_pinned` 钉住（少一个条目哈希就变），再钉一次
+    # 等于给 Task 3 增加一个必须同步更新的常量——而简报 Step 1 明确允许 Task 3 往
+    # ``exercises.yaml`` **追加** ``exercise_ref``，且只要求它更新指纹常量。20 这个下界取自
+    # 计划 Task 2 的「预估 20–30 个」，它抓的是「动作库被截断成几条」这类事故，
+    # 不抓「加了一个动作」。
+    assert written >= 20, f"动作库只剩 {written} 条，低于计划预估的 20–30 的下界"
+
+    rows = session.execute(select(Exercise)).scalars().all()
+    assert len(rows) == written
+    assert {row.ref for row in rows} == set(library)
+
+    # 逐列对账：DB 行必须与 YAML 的投影逐字段相同（targets 落库为排序后的 list，
+    # 因为 frozenset 不能直接 JSON 序列化，且排序让落库字节与遍历序无关）
+    for row in rows:
+        spec = library[row.ref]
+        assert row.name == spec.name
+        assert row.video_url == spec.video_url
+        assert row.impact_level == spec.impact_level.value
+        assert row.targets == sorted(spec.targets)
+        assert row.equipment == spec.equipment
+
+    # 幂等：重跑一次，行数与返回值都不变
+    assert rp.sync_exercises(session) == written
+    session.commit()
+    assert session.scalar(select(func.count()).select_from(Exercise)) == written
+
+
+def test_sync_exercises_updates_a_changed_field_in_place(session):
+    """YAML 改了值，重跑必须**更新**那一行而不是插第二行（upsert 的 PATCH 语义）。
+
+    这一条与上一条不重复：上一条验的是「同样的输入跑两次」，这条验的是「输入变了」。
+    失效形态是 ``exercise`` 表随每次改 YAML 而膨胀，且旧行还在——模板按 ref 查时
+    命中哪一行取决于行序。
+    """
+    rp.sync_exercises(session)
+    session.commit()
+    before = session.scalar(select(func.count()).select_from(Exercise))
+
+    session.execute(
+        Exercise.__table__.update()
+        .where(Exercise.__table__.c.ref == "interval_run")
+        .values(name="被改坏的名字")
+    )
+    session.commit()
+    assert rp.sync_exercises(session) == before
+    session.commit()
+    assert session.scalar(select(func.count()).select_from(Exercise)) == before
+    row = session.scalar(select(Exercise).where(Exercise.ref == "interval_run"))
+    assert row.name == rp.load_exercises()["interval_run"].name == "间歇跑"
+
+
+# ---------------------------------------------------------------------------
+# 加载器的响亮失败（Review Focus 第 1 条的同构要求，作用于动作库这一侧）
+# ---------------------------------------------------------------------------
+
+
+def test_load_exercises_is_read_only_and_cached():
+    """``load_exercises()`` 返回只读视图；``exercises()`` 是进程内单例。
+
+    形状照 ``app/refdata.py`` 的 ``load_standard()`` + ``standard()`` **这一对**
+    （Plan02 账本 P2-A9：``load_standard`` 只加载不缓存，单例是另一个函数）。
+    只读是承重的：``exercises()`` 被全进程共享，一次 ``library["x"] = ...`` 的就地改写
+    会让之后所有装配静默变质，而 ``frozen=True`` 只挡「换掉整个字段」、挡不住这个。
+    """
+    first = rp.exercises()
+    assert first is rp.exercises(), "exercises() 不是单例：每次调用都重读磁盘"
+    assert isinstance(first, types.MappingProxyType), type(first)
+    assert rp.load_exercises() is not rp.load_exercises(), (
+        "load_exercises() 不该缓存：它与 load_standard() 同口径，缓存是 exercises() 的职责"
+    )
+    with pytest.raises(TypeError):
+        first["interval_run"] = None  # type: ignore[index]
+    assert rp.equivalence() is rp.equivalence()
+
+
+def test_load_exercises_reports_the_file_when_missing(tmp_path):
+    with pytest.raises(FileNotFoundError, match="动作库"):
+        rp.load_exercises(tmp_path / "nope.yaml")
+
+
+def test_load_equivalence_reports_the_file_when_missing(tmp_path):
+    with pytest.raises(FileNotFoundError, match="等价映射表"):
+        rp.load_equivalence(tmp_path / "nope.yaml")
+
+
+@pytest.mark.parametrize(
+    "mutant, needle",
+    [
+        ("", "为空"),
+        ("[]\n", "顶层结构"),
+        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
+         "  impact_level: very_high\n  targets: [endurance]\n  equipment: none\n", "impact_level"),
+        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
+         "  impact_level: high\n  targets: []\n  equipment: none\n", "targets"),
+        # ``bmi`` 是 ScoredItem 而不是桶名（ITEM_BUCKET[BMI] is None），照字面写
+        # set(ITEM_BUCKET.values()) 会把 None 放进取值域、让这一条悄悄合法（P2-A4）
+        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
+         "  impact_level: high\n  targets: [bmi]\n  equipment: none\n", "targets"),
+        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
+         "  impact_level: high\n  targets: [endurance]\n", "equipment"),
+        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
+         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n  coach: 张老师\n", "coach"),
+        ("Interval_Run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/x\n"
+         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n", "ref"),
+        ("interval_run:\n  name: 间歇跑\n  video_url: ''\n"
+         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n", "video_url"),
+    ],
+)
+def test_load_exercises_rejects_a_malformed_library(tmp_path, mutant, needle):
+    """坏 YAML 必须在**加载时**响亮失败，并点名是哪个文件、哪个 ref、哪个字段。
+
+    不校验的后果是静默的：一个拼错的 ``impact_level`` 会让该动作**永远不被** spec §7.4
+    的安全后置识别成 high，BMI > 30 的学生照旧被安排它，而全链路没有一处报错。
+    """
+    path = _write_yaml(tmp_path, mutant)
+    with pytest.raises(ValueError) as excinfo:
+        rp.load_exercises(path)
+    message = str(excinfo.value)
+    assert needle in message, message
+    assert path.name in message, f"报错没点名文件：{message}"
+
+
+@pytest.mark.parametrize(
+    "mutant, needle",
+    [
+        ("mappings: []\nvolume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "version"),
+        ("version: ''\nmappings: []\n"
+         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "version"),
+        ("version: '1.0'\nvolume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "mappings"),
+        ("version: '1.0'\nmappings: []\n", "volume_reduction"),
+        ("version: '1.0'\nmappings: []\nvolume_reduction: {bmi_over_30: 0.8}\n", "volume_reduction"),
+        ("version: '1.0'\nmappings: []\n"
+         "volume_reduction: {bmi_over_30: 1.8, muscle_low_p10: 0.9}\n", "volume_reduction"),
+        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: low, when: body_fat_over}\n"
+         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "when"),
+        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: very_low, when: bmi_over_30}\n"
+         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "max_impact"),
+        ("version: '1.0'\nmappings:\n  - {from: a, to: b, when: bmi_over_30}\n"
+         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "max_impact"),
+        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: low}\n"
+         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "when"),
+        ("[]\n", "顶层结构"),
+    ],
+)
+def test_load_equivalence_rejects_a_malformed_table(tmp_path, mutant, needle):
+    """坏等价表同样必须在加载时响亮失败，并点名文件与出错的那条映射。"""
+    path = _write_yaml(tmp_path, mutant, name="exercise_equivalence.yaml")
+    with pytest.raises(ValueError) as excinfo:
+        rp.load_equivalence(path)
+    message = str(excinfo.value)
+    assert needle in message, message
+    assert path.name in message, f"报错没点名文件：{message}"
+
+
+def test_a_wellformed_minimal_library_round_trips(tmp_path):
+    """**已知 GREEN 的干净对照**（硬规矩 #53）：上面两批拒绝用例全红的前提是加载器本身能
+    吃下一份合法的 YAML。少了这一条，「把校验改成一律 raise」也能让全部拒绝用例变绿。
+    """
+    path = _write_yaml(tmp_path, GOOD_EXERCISE_YAML)
+    library = rp.load_exercises(path)
+    assert set(library) == {"interval_run", "bodyweight_resistance"}
+    assert library["interval_run"].impact_level is ImpactLevel.HIGH
+    assert library["interval_run"].targets == frozenset({"endurance"})
+    assert isinstance(library["interval_run"].targets, frozenset)
+
+    eq_path = _write_yaml(
+        tmp_path,
+        "version: '9.9'\n"
+        "mappings:\n"
+        "  - {from: interval_run, to: bodyweight_resistance, max_impact: low, when: bmi_over_30}\n"
+        "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n",
+        name="exercise_equivalence.yaml",
+    )
+    table = rp.load_equivalence(eq_path)
+    assert table.version == "9.9"
+    assert len(table.mappings) == 1
+    assert table.lookup("interval_run", ImpactLevel.LOW) == "bodyweight_resistance"
+
+
+# ---------------------------------------------------------------------------
+# 闸 4：domain 公开面基线（Plan 02 Task 2 fix round 2，账本 Ruling 107-4）
+# ---------------------------------------------------------------------------
+
+#: ``app.domain.prescription.__all__`` 的字面基线，**声明序**照
+#: ``app/domain/prescription/__init__.py`` 里 ``__all__`` 的书写序逐字抄进来（三个词表常量
+#: 在前、四个类型在后）。取法（在 ``backend/`` 下跑，一次性取证）::
+#:
+#:     python -c "from app.domain import prescription as p; print(p.__all__)"
+#:
+#: ⚠️ **不从 ``dir(prescription_pkg)`` 反推**（硬规矩 #35）：那样两侧同源，漏重导出一个名字
+#: 两边一起少一个、恒等成立。**而且 ``dir()`` 本身还不可复现**：亲跑 ``dir(pkg)`` 的公有名
+#: 是 ``['EQUIVALENCE_TRIGGERS', 'EquivalenceMapping', 'EquivalenceTable', 'ExerciseSpec',
+#: 'IMPACT_RANK', 'ImpactLevel', 'TARGET_DOMAIN', 'exercises']``——最后那个 ``exercises``
+#: 是**子模块属性**，只有在「已经有谁 import 过它」时才出现，故 ``dir()`` 的内容随导入顺序
+#: 漂。这也是 ``tests/db/test_models.py`` 那边要靠 ``_MODELS_SUBMODULES`` 显式排除六个子模块
+#: 名的原因；本基线钉 ``__all__`` 而不是 ``dir()``，一次就把这个问题绕开。
+#:
+#: **与 ``_MODELS_PUBLIC_BASELINE`` 的理由不同**（硬规矩 #56，别把那段注释的理由抄过来）：
+#: 那 33 个名字是「``models.py`` 拆包前后导入面逐字不变」的**历史快照**，里面含一批**偶然
+#: 公有**的名字（``dt`` / ``json`` / ``Boolean`` / ``mapped_column`` …），保留它们是「逐字
+#: 相同」这个判据的应有代价。而这 7 个是 Task 2 **刻意选出**的公开面：每一个都是 Ruling 96
+#: 搬进 domain 的动作库对象或词表，**没有一个是顺带公有的**（``exercises.py`` 模块级 import
+#: 进来的 ``Mapping`` / ``dataclass`` / ``Enum`` / ``ITEM_BUCKET`` 四个名字在
+#: ``dir(exercises)`` 里也是公有的、共 11 个，而它们**一个都没被重导出**、也不在本基线里，
+#: 支 5 的 AST 口径把它们排除在外）。故本基线的性质是**逐 Task 递增**（Task 3 往
+#: ``templates.py`` 加模板对象时同步追加），不是「冻结」。
+_PRESCRIPTION_PUBLIC_BASELINE = [
+    "EQUIVALENCE_TRIGGERS",
+    "IMPACT_RANK",
+    "TARGET_DOMAIN",
+    "EquivalenceMapping",
+    "EquivalenceTable",
+    "ExerciseSpec",
+    "ImpactLevel",
+]
+
+
+def test_prescription_public_namespace_is_pinned_verbatim():
+    """``app.domain.prescription`` 的公开面被字面钉住（Plan02 账本 Ruling 107-4）。
+
+    ``app/db/models`` 那边有 ``_MODELS_PUBLIC_BASELINE``（33 个名字）钉住拆包前后的导入面，
+    domain 这个包**没有**对应的守卫——而它的 ``__all__`` 在 Task 2 从 1 个名字扩到 7 个，
+    Task 3-9 每个 Task 都要往里追加。
+
+    **失效形态**（硬规矩 #39，逐条给主语）：
+
+    * 谁往 ``__all__`` 里**加**了一个名字（Task 3 的 ``Template`` 一类）却没同步本基线
+      → **支 2 红**；
+    * 谁把 ``__all__`` 里一个名字**删掉** → **支 2 红**；谁只删 ``from .exercises import (…)``
+      里的一个名字而留着 ``__all__`` 里那一个 → **支 4 红**（``__all__`` 谎报：
+      ``from app.domain.prescription import *`` 会在运行期 ``AttributeError``，而那条路径
+      今天没有任何测试走）；
+    * 谁往 ``exercises.py`` 加了新的**公有顶层定义**却忘了重导出 → **支 5 红**。⚠️ 这一支
+      是**唯一**抓得住这个方向的：那种情况下 ``__all__`` 根本没变，支 2 与支 4 都不会响；
+    * 谁把 ``exercises.py`` 里某个对象**改名** → 支 4 与支 5 一起红；
+    * 谁把 ``__all__`` **重排**成字母序 → 支 2 红（支 3 是这一支的反面对照：基线自己不是
+      字母序，故支 2 真的在钉顺序）。
+
+    **它守不住什么**：不守这 7 个名字各自的**取值**——``IMPACT_RANK`` 的秩值由
+    :func:`test_impact_rank_values_are_pinned_verbatim` 钉、``TARGET_DOMAIN`` 与
+    ``EQUIVALENCE_TRIGGERS`` 由闸 2 那两条钉、``ImpactLevel`` 的词表由
+    ``tests/domain/test_prescription_templates.py`` 钉；也不守 ``templates.py`` 的
+    ``__all__``（那是**另一份**，由那个文件 fix round 2 新加的第 4 条守卫钉住。两份
+    ``__all__`` 必须一起改，这句话同时写在 ``templates.py`` 与 ``prescription/__init__.py``
+    的 docstring 里）。
+
+    **红/绿双输入**（硬规矩 #50）：绿输入 = 今天的真实状态（支 1-5 实跑通过）；红输入 =
+    支 6 在测试内**合成**的两种失同步状态（多一个 ``Template`` / 少最后一个名字），比对
+    必须判不相等——它证明支 2 那条相等断言对「多一个」与「少一个」都敏感、不是恒真式
+    （**M-C1 实测：支 6b 真的开了火**，见下）。
+    改生产码的真变异本轮实跑过三个（逐支真值见报告 §fr2.4），**各打不同的支**：
+    **M-C1**（``__all__`` 里删掉 ``ImpactLevel``，7 → 6）→ **支 2 红**，且**支 6b 也一起红**
+    （那种状态下 ``list(__all__)`` 恰好等于 ``baseline[:-1]``，故支 6 不是装饰），
+    ``1 failed, 530 passed``；**M-C2**（只删 ``from .exercises import (…)`` 里的
+    ``ImpactLevel``、``__all__`` 里留着）→ **只有支 4 红**，``1 failed, 530 passed``；
+    **M-C3**（往 ``exercises.py`` 加一个公有顶层定义 ``SUBSTITUTE_POLICY`` 而**不**重导出、
+    ``__all__`` 一个字没改）→ **只有支 5 红**，``1 failed, 530 passed``——这一支是那个
+    方向上**唯一**的守卫，没有它这件事就完全静默。
+
+    **六支的主语**（硬规矩 #56）：支 1 = 基线自己；支 2 = ``__all__`` 的内容**与声明序**；
+    支 3 = 声明序不是字母序；支 4 = ``__all__`` 不许谎报；支 5 = 公开面对 ``exercises.py``
+    的公有顶层定义**穷尽**；支 6 = 反面对照。
+    """
+    baseline = set(_PRESCRIPTION_PUBLIC_BASELINE)
+    # 支 1：基线自校（口径照 tests/db/test_models.py 的 len(_MODELS_PUBLIC_BASELINE) == 33）
+    assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 7, "基线是 7 个名字，抄漏了就当场红"
+    # 支 2（绿输入）：内容与**声明序**都逐字相同
+    assert list(prescription_pkg.__all__) == _PRESCRIPTION_PUBLIC_BASELINE
+    # 支 3：基线不是字母序，故支 2 真的在钉顺序（重排成 sorted() 会让支 2 红）
+    assert sorted(_PRESCRIPTION_PUBLIC_BASELINE) != _PRESCRIPTION_PUBLIC_BASELINE
+    # 支 4：__all__ 不许谎报。先断言所有者侧取到的不是 None，否则 `None is None` 会让
+    #       这一支退化成恒真（假绿）。
+    for name in _PRESCRIPTION_PUBLIC_BASELINE:
+        owner = getattr(exercises_mod, name, None)
+        assert owner is not None, (
+            f"所有者模块 exercises 上没有 {name}，同一性比对会退化成 None is None"
+        )
+        assert getattr(prescription_pkg, name, None) is owner, (
+            f"{name} 在包上取不到、或取到的不是 exercises 里的那个对象（公开面谎报）"
+        )
+    # 支 5：穷尽。期望侧仍是**字面基线**，实际侧是 AST 扫源码（不是 dir()，故不构成 #35 的
+    #       同源）。只有顶层**定义**算数：模块级 import 进来的名字（Mapping / dataclass /
+    #       Enum / ITEM_BUCKET）不算，它们本来也不该被重导出。
+    tree = ast.parse(pathlib.Path(exercises_mod.__file__).read_text(encoding="utf-8"))
+    defined = {
+        node.name for node in tree.body
+        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_")
+    } | {
+        target.id
+        for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
+        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
+        if isinstance(target, ast.Name) and not target.id.startswith("_")
+    }
+    assert defined == baseline, (
+        "exercises.py 的公有顶层定义与公开面基线不同步："
+        f"只在源码里（加了却没重导出）= {sorted(defined - baseline)}；"
+        f"只在基线里（已被删掉或改名）= {sorted(baseline - defined)}"
+    )
+    # 支 6（红输入，硬规矩 #50）：合成的两种失同步状态，比对必须判不相等
+    assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE + ["Template"]
+    assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE[:-1]
```


## spec diff（§14 第 28 项）

```diff
diff --git "a/Document/2026-09-28-\344\275\223\350\202\262\351\227\255\347\216\257\345\216\237\345\236\213-\350\256\276\350\256\241spec.md" "b/Document/2026-09-28-\344\275\223\350\202\262\351\227\255\347\216\257\345\216\237\345\236\213-\350\256\276\350\256\241spec.md"
index 5550d43..9e5acd2 100644
--- "a/Document/2026-09-28-\344\275\223\350\202\262\351\227\255\347\216\257\345\216\237\345\236\213-\350\256\276\350\256\241spec.md"
+++ "b/Document/2026-09-28-\344\275\223\350\202\262\351\227\255\347\216\257\345\216\237\345\236\213-\350\256\276\350\256\241spec.md"
@@ -927,12 +927,13 @@ npm install && npm run dev
 | **22** | **趋势判定表的行序与「持续下滑」第二分支的阈值** | **行序改为「波动大 → 持续下滑 → 稳步提升 → 稳定」（原序下「波动大」可证明不可达）；「持续下滑」第二分支由「≥3 项为负变化」收紧为「≥3 项下降 ≥5 分」（原措辞下「稳定」类几乎无法存在）。两条均为规格缺陷修正，非需求变更，但仍请项目负责人确认是否符合指导文件原意** | **§6.3** | **趋势分类、规则 Y4 的触发人群；仿真数据四类标签的可生成性** |
 | **23** | **「≥3 项变化方向不一致」的读法** | **取「六个 `delta_i` 里正负两方各 ≥3 项」（对 6 项即恰好 3 正 3 负），不取「≥3 项与总分方向不一致」——后者在 `Delta = 0` 时无定义。副作用：任一项 `delta_i` 恰好为 0 时该类退化为不可达，属刻意保守** | **§6.3** | **「波动大」类的识别率与仿真数据中该类的可生成性** |
 | **24** | **国标常模（`percentile_source = national` 的兜底值）从哪来** | **国标 2014 只公布评分阈值、不公布人群百分位常模，故本设计不新增常模数据文件，而是从评分表按「全国参考人群在该项原始值上均匀分布于表内量程 `[lo, hi]`」这一显式假设推导：得分的第 `p` 百分位 = `score_item(lo + q/100·(hi−lo))`，`q = p`（越大越好）或 `100−p`（越小越好）。实测 24 组逆序 0 组、国标 P25 落在 **30–64**（去重取值 `{30,40,50,60,62,64}`），与 500 人仿真数据的本校 P25 同量级（**切片必须写明**：`2025-2026 week1` 上为 50–63（零注入）/ 50–62（缺省注入）；按 Ruling 56 正确取龄组时跨切片全距为 **50–66**；`64` 只出现在 week8/week16，`40` 只在违反 Ruling 56 时出现——复审实测更正，此前写的「50–64」与「40–64」都缺切片条件）。该假设是占位，若项目组能提供教育部公布的真实人群分布，只需替换 `national_norm` 一个函数** | **§6.3、§11.1** | **样本 <30 人的（性别 × 年级组 × 项目）分组的短板判定线；500 人规模下四组均 ≥30（实测 0/24 组触发降级），故生产数据实际不走这条兜底，影响面限于小规模部署与降级路径的测试。⚠️ 已知偏差（实测，非推测）：兜底常模并非本校线的无偏替代——逐组差 `−7…+34` 分、均值 `+9.90`，其中 `distance_run` 四组为 `+30/+34/+20/+20`，即**常模系统性更宽松**，降级时耐力跑的短板会被少判，而它权重 20%（全表最高）。根因是「均匀分布于量程」的假设遇上慢端密集的得分阶梯，属假设的固有后果、不是实现缺陷；换真实常模即消除** |
 | **25** | **`fitness_test_result.national_grade`（国标等级）的阈值口径** | **第一批不产出，恒 `NULL`。** §4.2 列了这一列、§4.2 的说明又写它「用于计算国标总分、**等级**」，而**全文没有任何一处给出「总分 → 优秀/良好/及格/不及格」的阈值**，本节原 24 项里也没有它。实现拒绝自造是对的：这一列会出现在学生端与报表上，自造阈值等于凭空造第二个口径，而 §1.3 的可追溯性与 §12 的黄金用例都依赖「与官方报表逐格对账」。**须提供国标 2014 的等级划分原文（含加分表 2-3~2-6 是否计入学年总分 120 分制）** | **§4.2** | **`fitness_test_result.national_grade` 一列；学生端与报表的「国标等级」展示；Plan 02 若要按等级筛选需先定这一列** |
 | **26** | **`body_composition.weight_kg` 与 `.device` 恒 `NULL`** | **第一批不产出，恒 `NULL`；正确的修法是扩适配器契约，不是删列。** §4.2 列了这两列，而 `RawBodyCompRecord`（`backend/app/adapters/base.py`）只有 3 个测量列（`muscle_mass_kg` / `body_fat_pct` / `smi`），故 `daily.py` 显式写 `None`（**显式写而不是省略**：`repo.upsert` 的更新分支是 PATCH 语义，省略等于「沿用上一轮的值」，那会让一个从未被测过的列看起来像是被测过）。实测 **0/3000** 行有值。真实 InBody 导出**确实**带体重与设备型号，故 Plan 03 接真实数据时应给 `RawBodyCompRecord` 加这两列并同步 `body_comp.csv` 的列序契约 | **§4.2** | **`body_composition` 两列；InBody 设备溯源（哪台机器测的，用于跨设备偏差校正）；`weight_kg` 与体测表的 `weight_kg` 是两处独立测量，可用于交叉校验** |
 | **27** | **肌肉量 P20 判定线的样本单位：学生级 还是 测量行级** | **学生级**（每人只入一行，取该生 `<= business_date` 的最新一条体成分）。理由：快照描述的是**人群**而不是**测量事件**——同一个人的三次测量不是三个独立的人，按行入样会让测得勤的人对判定线有更大权重，而 P20 正是 `C` 的判定项之一。§6.3② 与 §4.0 都**没说样本单位**，实现单方面选了这个口径并量化了差异，本节据此补登记 | **§6.3、§4.0** | **`C` 的判定、分层分布、以及零注入那组 green 对 30% 下界仅剩的 0.4 pp 余量。** 实测量级（500 人 / `seed=20250828`，学生级走生产 `cohort_snapshot`、行级把每条体成分记录都当一个样本；差值按 (性别, 年级组) 分组）：female 大一、大二 `23.70 / 23.30 / +0.40`、female 大三、大四 `23.60 / 23.30 / +0.30`、male 大一、大二 `33.14 / 33.00 / +0.14`、male 大三、大四 `33.44 / 33.50 / −0.06`（零注入：`23.70/23.30/+0.40`、`23.60/23.30/+0.30`、`33.20/33.10/+0.10`、`33.56/33.50/+0.06`）——**跨度 −0.06 到 +0.40 kg、符号都会翻**，`C` 标记翻动 **7 人**（男 2 + 女 5，两种注入下相同）。⚠️ 把行级样本改成「只取本学年的 3 条」会让差值再变一组（female +0.20/+0.10、male −0.06/−0.32、翻动 6 人），故**这个量级高度依赖行级样本怎么取**，只能当「足以翻人」的定性证据，不能当可复现的定量基线。**7 人足以让零注入那组的 green 跌破 30% 下界（余量仅 0.4 pp）**——若 green 掉出去，先怀疑本项口径，不要直接放宽容差 |
+| **28** | **`exercise_equivalence.yaml` 的 `volume_reduction` 两个系数（BMI > 30 → `0.8`；肌肉量 < P10 → `0.9`）** | **本设计的默认规定，spec 全文无出处。** §7.4 `:508` 只写「跑量**按映射表下调**」、**没给任何数**；`:509`（肌肉量 < 同龄同性别 P10）写「同上」。spec 里唯一出现的「系数 0.8」在 `:604`，那是**预警触发的「减量 20%」**（`weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，属 Plan 03），与 §7.4 的安全后置跑量下调是**两个不同机制**；`0.9` 在 spec 里**根本没有对应物**。故实现拒绝把 `:604` 的 0.8 借来当 §7.4 的系数，而是显式取两个默认值并登记于此：`0.8`（下调 20%）用于 BMI > 30，因为它的关节负荷风险更直接、且 spec 把它列在两个触发之首；`0.9`（下调 10%）用于肌肉量 < P10，因为它的主要风险是**抗阻不足**而非负荷过量，故少减一些、并按 `:509` 同时提高抗阻模块比重。**须提供指导文件或运动处方规范里的实际下调幅度。** | **§7.4** | `backend/data/exercise_equivalence.yaml` 的 `volume_reduction` 两个值（字节由 `tests/test_refdata_prescription.py` 的 `test_equivalence_yaml_fingerprint_is_pinned` 钉住、数值由 `test_volume_reduction_coefficients_are_pinned_verbatim` 字面钉住）；Task 7 的 `safety.py` 消费它算周训练量，改这两个数会直接改变 BMI > 30 与肌肉量 < P10 学生身上红/黄层处方的训练量。**Task 7 不得把它们当成 spec 条文引用。** ⚠️ **编号冲突待 Task 12 处理**：计划 02 的 Task 12 Step 3（计划 `:681` 与 `:685`）已把 **#28** 预留给「18 套模板的审校状态」、把 **#32** 预留给与本项**同一主题**的「§7.4 的跑量下调系数与『提高抗阻比重』的处置」。本项因「值在这一刻被写死」提前到 Task 2 登记（Plan02 账本 P2-A3 的裁定），故 Task 12 须把它那 7 项整体后移为 **#29–#35**，并**删掉与本项重复的那一条**（原 #32），否则同一件事会在 §14 里出现两次。 |
 
 ---
 
 ## 15. 后续批次规划
 
 第一批（本 spec）交付核心闭环 6 个子系统后，后续两批各自走独立的 spec → plan → 实现周期：
diff --git "a/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md" "b/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
index d786fd1..018fb86 100644
--- "a/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
+++ "b/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
@@ -45,21 +45,22 @@ spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。
 
 | 路径 | 职责 |
 |---|---|
 | `backend/app/config.py` | `DEFAULT_DB_URL` / `DEFAULT_CSV_DIR` 的唯一所有者（从 `app/seed/generate.py` 迁入，Task 1） |
 | `backend/app/adapters/factory.py` | `build_adapter(kind, **kw) -> DataSourceAdapter`，CLI 与将来的 FastAPI 依赖注入共同消费（Task 1） |
 | `backend/app/domain/prescription/__init__.py` | 公开面重导出 |
-| `backend/app/domain/prescription/templates.py` | 模板的**数据结构**（`@dataclass(frozen=True)`）与维度词表；**不读盘** |
+| `backend/app/domain/prescription/exercises.py` | **动作库的值对象**：`ImpactLevel` / `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable`；**不读盘**（Ruling 96：与 `app/domain/tables.py` 的 `StandardTable` 同构——值类型住 domain、加载器住 domain 外、加载器 import 值类型） |
+| `backend/app/domain/prescription/templates.py` | 模板的**数据结构**（`@dataclass(frozen=True)`）与维度词表；**不读盘**（`ImpactLevel` 自 Ruling 96 起住在 `exercises.py`，本模块按 domain 内部依赖方向 import 或 re-export） |
 | `backend/app/domain/prescription/match.py` | 层 × 主导短板 × 体成分 → 模板（含 `reachable` 与 `review.status` 判定） |
 | `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（Tanaka / 220−age 可切换） |
 | `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配 |
 | `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换 |
 | `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加 |
 | `backend/app/domain/prescription/triggers.py` | spec §5.2 的五触发条件求值 |
 | `backend/app/domain/prescription/weekly.py` | spec §8.4 的「本周训练单 = 骨架第 N 周 × 系数」 |
-| `backend/app/refdata_prescription.py` | 加载 18 套模板 YAML 与 `exercise_equivalence.yaml`，**校验后**交给 domain（domain 不读盘） |
+| `backend/app/refdata_prescription.py` | 加载 **`exercises.yaml`（Task 2）**、18 套模板 YAML（Task 3）与 `exercise_equivalence.yaml`，**校验后**交给 domain（domain 不读盘）；并持有 `sync_exercises(session)`（Ruling 89/P2-A1：不接进 `app/seed/`） |
 | `backend/app/pipeline/prescription_stage.py` | 落库、幂等、`prescription_count` 计数 |
 | `backend/data/prescription/*.yaml` | 18 套模板，一套一文件，体育专家可独立审校 |
 | `backend/data/exercise_equivalence.yaml` | 低冲击等价动作映射 + **版本号** |
 | `backend/data/exercises.yaml` | 动作库的**源**（`exercise` 表由它 seed，理由见 Task 2） |
 
 **新建（测试）**：`backend/tests/domain/test_prescription_{templates,match,intensity,assembler,safety,override,triggers,weekly}.py`、`backend/tests/test_refdata_prescription.py`、`backend/tests/pipeline/test_prescription_stage.py`、`backend/tests/architecture/test_layering.py`
@@ -175,13 +176,13 @@ git commit -F <临时文件>   # 中文，说明清偿了终审 C 组哪几项
 - Produces:
   - `app.domain.prescription.templates.ImpactLevel(str, Enum)`：`HIGH = "high"` / `MEDIUM = "medium"` / `LOW = "low"`（spec §4.4 的 `exercise.impact_level` 取值域）
   - `app.refdata_prescription.load_exercises() -> dict[str, ExerciseSpec]`（键是 `exercise_ref`，单例缓存，`MappingProxyType` 只读，形状照 `app/refdata.py` 的 **`load_standard()` + `standard()` 这一对**）（P2-A9：实测 `load_standard(path=None)` 只负责加载、**不缓存**，单例是**另一个函数** `standard()`（`app/refdata.py:194`，`global _standard_cache`）；原文只点了前者）
   - `app.refdata_prescription.load_equivalence() -> EquivalenceTable`，`EquivalenceTable.version: str` 与 `.lookup(ref: str, impact_ceiling: ImpactLevel) -> str | None`
   - `ExerciseSpec`：`ref` / `name` / `video_url` / `impact_level` / `targets`（`frozenset[str]`，取值域 = `frozenset(v for v in ITEM_BUCKET.values() if v is not None)`，即 `{"endurance", "strength", "speed_flexibility"}` 三个桶名。⚠️ **P2-A4：不能写成 `set(ITEM_BUCKET.values())`** —— 实测它有 **4** 个值、含 `None`（`ITEM_BUCKET[ScoredItem.BMI] is None`，因为 BMI 天然不属于任何短板桶），那样会把 `None` 放进取值域、让一个空 `targets` 悄悄合法）/ `equipment`
 
-**决定（用户已裁定）**：动作库按 **18 套模板实际引用的 `exercise_ref`** 建，预估 20–30 个；**视频 URL 用可识别的占位符** `https://example.invalid/exercise/<ref>`（`.invalid` 是 RFC 2606 保留 TLD，**保证不可解析**，因此不会被误当成真链接），并在 spec §14 登记「须提供真实视频源」。**不编造真实链接。**
+**决定（用户已裁定）**：动作库按 **18 套模板实际引用的 `exercise_ref`** 建，预估 20–30 个；**视频 URL 用可识别的占位符** `https://example.invalid/exercise/<ref>`（`.invalid` 是 RFC 2606 保留 TLD，**保证不可解析**，因此不会被误当成真链接），并在 spec §14 登记「须提供真实视频源」（⚠️ **这项登记由 Task 12 Step 3 统一做**，见那里的 **#30**；Task 2 只把它写进 `exercises.yaml` 的头注释，**不单独占一个 §14 编号**——否则会与 Task 12 的清单撞号，Task 2 实现时已经撞过一次）。**不编造真实链接。**
 
 - [ ] **Step 1: 先写模板，再反推动作清单**
 
 ⚠️ **不要从 Task 3 的 YAML 反推动作清单**（Ruling 6 更正原文——原文让 T2 先写 T3 的模板，那是让 T2 做 T3 的活、构成循环）。**本 Task 从 spec §7.2:487 点名的动作 + 18 格矩阵的结构推出动作库**：间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、功能性训练、HIIT、两个 addon 模块，再补速度柔韧类 4 个（50 米冲刺间歇、动态拉伸、折返跑、坐位体前屈专项）。
 **Task 3 写 YAML 时只能引用本 Task 已建的 ref**；若 T3 需要一个 T2 没建的 ref，**T3 可以往 `exercises.yaml` 追加**（同时更新 T2 的指纹常量），并在报告里列出追加了哪些、为什么。这比「T2 猜 T3 要什么」诚实。
 
@@ -675,17 +676,20 @@ ORM 按 spec §4.4：`id` / `layer`（`String(8)` + CHECK ∈ `{red,yellow,green
 
 - 「单人处方生成」= 一次 `profile_of` + `match_template` + `assemble` + `apply_safety`（**不含** DB 写入，因为 spec §1.3 的验收方式写的是「API 性能测试断言」，而 API 侧的写入是另一件事）。
 - **p95 需要样本**：从 500 人的分层结果里取**全部 500 人**各生成一次，排序取第 475 个（`int(0.95 * 500)`）。
 - **断言写成 `< 3.0`，但报告里必须给出 n、min/p50/p95/max 与测量条件**（有无 `--cov`、机器、跑几次）。⚠️ **硬规矩 #42：余量 < 2× 的墙钟断言一律是 flaky 断言**。先跑一次看 p95 是多少：若 p95 < 1.5 s（2× 余量），断言 `< 3.0` 是安全的；若 p95 在 1.5–3.0 s 之间，**不要把断言钉在 3.0**，改成「记录 + 一条更松的数量级断言」，并在报告里说明（Plan 01 的 `test_backfill_500_students_under_60_seconds` 就是因为在 `--cov` 下余量只有 0.95× 而不得不加了 trace-钩子 skip，Ruling 228）。
 - **同时量 500 人全批**：这是 Plan 02 给管道加的增量成本，要与 Plan 01 的 28.4–34.0 s 合并报告，确认整学期回放仍在 60 s 内。⚠️ **处方不每天生成**（只有触发时才生成），所以整学期回放的增量应当**远小于** 112 × 500 次装配——**先算清楚预期再量**，量出来不符就是发现了问题。
 
-- [ ] **Step 3: spec 勘误与 §14 补项（本计划累计 7 项，#28–#34）**
+- [ ] **Step 3: spec 勘误与 §14 补项（本 Task 追加 **6 项，#29–#34**）**
 
-（Ruling 12 更正原文的「6 项」：正文列了 7 项，与「计划完成后的状态」那段的「27 → 34」一致。）
+⚠️ **P2-A3 的后续更正（Task 2 实现后）**：原文这里是「7 项，#28–#34」。**#28 已被 Task 2 用掉**（`volume_reduction` 两个系数无 spec 出处，见 Task 2 的 P2-A3 裁定：「值在哪一刻被写死就在哪一刻登记」），而原文 #32 正是同一主题（§7.4 的跑量下调系数）——**两项重复**。故本 Task 的清单整体前移一位、并删掉重复的那项：原 #28→**#29**、原 #29→**#30**、原 #30→**#31**、原 #31→**#32**、~~原 #32~~（**删除**，已由 Task 2 的 #28 覆盖）、原 #33→**#33**、原 #34→**#34**。**7 项 − 1 项重复 = 6 项**，而 §14 总数仍是 `27 + 1（Task 2）+ 6（本 Task）= **34**`，与「计划完成后的状态」那段的「27 → 34」**恰好一致**（那个数字本来就是对的，只是分配方式变了）。
 
-- §14 补：**#28** 18 套模板的审校状态（占位 approved，须专家实际审校）；**#29** 动作库的视频源（占位 `.invalid` URL）；**#30** 红/黄层 × `speed_flexibility` 共 4 套模板的强度参数（指导文件空洞，借用同层耐力配置）；**#31** §7.3 步骤 3 的个体修正系数三档阈值与性别系数（工程约定）；**#32** §7.4 的跑量下调系数与「提高抗阻比重」的处置（工程约定 + 不自动）；**#33** §5.2 触发 4「学期末数据刷新」的口径（任何新采集即触发，不限 week16）；**#34** §8.4 同周多调整的合成方式（相乘）。
+（Ruling 12 曾把原文的「6 项」更正为「7 项」；Task 2 落地后**又回到 6 项**——但这次是因为**原 #32 与 Task 2 的 #28 重复而被删**，不是数错。「27 → 34」这个总数在两次更正里都成立。）
+
+- §14 补（**#28 已由 Task 2 追加：`volume_reduction` 的两个系数**）：**#29** 18 套模板的审校状态（占位 approved，须专家实际审校）；**#30** 动作库的视频源（占位 `.invalid` URL；⚠️ Task 2 已把它写进 `exercises.yaml` 的头注释，本项是把它正式登记进 §14）；**#31** 红/黄层 × `speed_flexibility` 共 4 套模板的强度参数（指导文件空洞，借用同层耐力配置）；**#32** §7.3 步骤 3 的个体修正系数三档阈值与性别系数（工程约定）；**#33** §5.2 触发 4「学期末数据刷新」的口径（任何新采集即触发，不限 week16）；**#34** §8.4 同周多调整的合成方式（相乘）。
+  - ~~§7.4 的跑量下调系数与「提高抗阻比重」的处置~~ —— **本项删除（已并入 #28）**。但「**提高抗阻比重**」的处置（spec §7.4 `:509` 的「并提高抗阻模块比重」，计划 Task 7 决定「不自动、只提示」）**尚未登记**，故**并进 #28 的「影响面」格里一起交代**，由 Task 7 落地时确认 #28 的正文已覆盖它；若没覆盖，Task 7 追加为 **#35**。
 - §7.2 加勘误：指明 `speed_flexibility` 桶的参数空洞。
 - §7.3 加勘误：「耐力国标得分」的口径（`vital_capacity` 与 `distance_run` 两项得分的均值）。
 - §4.4 加勘误：`prescription_template` 用 `template_ref`（逻辑 id）而不是「YAML 路径」，理由见 Task 3。
 - §4.6 加勘误：`daily_sync_run` 补 `muscle_line_gaps` 列，`error_summary` 不再承载「注意（非错误）」文本。
 - §1.3 加勘误：「单人处方生成 p95 < 3 秒」的口径（不含 DB 写入，n=500，测量条件）。
 
```
