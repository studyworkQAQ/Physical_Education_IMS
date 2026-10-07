"""处方模板的**数据结构**与维度词表（Plan 02：Task 2 建、Task 3 填）。

⚠️ **本模块今天没有任何自己的定义**（Plan02 账本 Ruling 96）：Task 2 原来放在这里的
:class:`~app.domain.prescription.exercises.ImpactLevel` 已迁往
:mod:`app.domain.prescription.exercises`，本文件只剩一句 re-export 与一个 ``__all__``。
**为什么迁走**：``ImpactLevel`` 是 ``ExerciseSpec.impact_level`` 与 ``IMPACT_RANK`` 的类型，
留在本模块会让 ``exercises.py`` 反向 import 本模块；而依赖方向恰恰相反——Task 3 要往这里
加的模板 dataclass 会带 ``exercise_ref`` 与 ``impact_level`` 两个字段，即**模板引用动作库、
动作库不引用模板**。File Structure 说本模块是「模板的数据结构与维度词表」，Ruling 96 之后
「**动作库**的维度词表」那一半归 ``exercises.py``，本模块留「模板的数据结构」（Task 3）
与模板自己要用的维度词表。

**re-export 的口径**（照 ``app/pipeline/run_stratify.py:50-57`` 那次同类搬迁）：
``ImpactLevel`` 的**唯一所有者**是 :mod:`app.domain.prescription.exercises`，本模块只是
保持既有导入面——``app.domain.prescription.templates.ImpactLevel`` 照旧可用，故 Task 2
写下的 ``from app.domain.prescription.templates import ImpactLevel`` 不会一夜之间变成
ImportError。**新代码请直接从 ``exercises`` 导入**（本轮已把
``tests/test_refdata_prescription.py`` 的 import 改过去了；
``tests/domain/test_prescription_templates.py`` 刻意**保留**从本模块导入——那是本模块
今天唯一的导入方，也是这 2 条语句进 domain 覆盖率统计的唯一途径）。``__all__`` 里列着它，
是为了让这次 re-export 是一次**显式**声明，而不是「碰巧留在命名空间里」：没有 ``__all__``，
下一个人会以为它本模块私有、可放心改名。

**Task 3 注意**：往本文件加模板 dataclass 时，请同步
``app/domain/prescription/__init__.py`` 的公开面——那里的 ``__all__`` 与本模块的
``__all__`` 是两份，必须一起改，否则公开面谎报。

**为什么不读盘**（Global Constraint #1）：``app/domain/`` 是无 I/O 的纯函数叶子层，
YAML 的解析与校验住在 :mod:`app.refdata_prescription`，解析结果作为**参数**注入 domain
的纯函数。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手结果就可
复现、可追溯（spec §1.3）。这条由 :mod:`tests.architecture.test_domain_purity` 的
allow-list 守卫机器可查地钉住：domain 只允许 import 6 个标准库模块串（``dataclasses`` /
``enum`` / ``collections`` / ``collections.abc`` / ``numpy`` / ``typing``）与 ``app.domain``
前缀；本模块今天只 import 了同包的 ``exercises``（相对导入 ``level == 1``，被那道守卫折算
成 ``app.domain.prescription.exercises``、命中前缀那一项）。
"""
from .exercises import ImpactLevel

__all__ = ["ImpactLevel"]
