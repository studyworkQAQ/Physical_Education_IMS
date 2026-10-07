"""处方模板与动作库的**维度词表**（Plan 02 Task 2 只放 :class:`ImpactLevel`）。

⚠️ **本模块今天刻意只有一个枚举**（Plan02 账本 P2-B1 的裁定）：计划的 File Structure 说
它是「模板的**数据结构**（``@dataclass(frozen=True)``）与维度词表；**不读盘**」，而这两
半分属两个 Task——``ImpactLevel`` 是**维度词表**、归 Task 2（``exercise.impact_level`` 的
取值域，spec §4.4 ``:239``），模板的数据结构（``PrescriptionTemplate`` / ``Session`` /
``Block`` / ``Progression`` / ``Addon`` 等）归 **Task 3**。原文让 Task 2 与 Task 3 双双
「Create」本文件，故裁定为：**Task 2 建、只放 ``ImpactLevel``；Task 3 对它是 Modify**。

**为什么不读盘**（Global Constraint #1）：``app/domain/`` 是无 I/O 的纯函数叶子层，
YAML 的解析与校验住在 :mod:`app.refdata_prescription`，解析结果作为**参数**注入 domain
的纯函数。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手结果就可
复现、可追溯（spec §1.3）。这条由 :mod:`tests.architecture.test_domain_purity` 的
allow-list 守卫机器可查地钉住：本模块只允许 import ``enum`` / ``dataclasses`` /
``typing`` / ``collections.abc`` / ``numpy`` 与 ``app.domain`` 前缀。
"""
from enum import Enum


class ImpactLevel(str, Enum):
    """spec §4.4 ``:239`` 的 ``exercise.impact_level`` 取值域：``high`` / ``medium`` / ``low``。

    **继承 ``str``**：``exercise.impact_level`` 那一列是 ``String(8)``，继承 ``str`` 之后
    ``ImpactLevel.HIGH == "high"`` 直接成立，落库与读回都是同一个字符串，不必在 ORM 边界
    上处处写 ``.value``。漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()``
    存成 ``"ImpactLevel.HIGH"``（19 字符，还撑破 ``String(8)``——SQLite 不强制长度，故
    写侧不报错，换严格长度的后端才截断，硬规矩 #18 的那个失效形态）。

    ⚠️ **它不携带序**：继承 ``str`` 意味着 ``<`` 是**字典序**，即
    ``ImpactLevel.HIGH < ImpactLevel.LOW < ImpactLevel.MEDIUM``，与「冲击由高到低」完全
    无关。冲击序由消费方显式声明，今天有两份、刻意不同源（硬规矩 #35）：生产侧
    ``app/refdata_prescription.py`` 的 ``_IMPACT_RANK``，测试侧
    ``tests/test_refdata_prescription.py`` 的 ``IMPACT_DESCENDING``。改坏任何一份都会让
    ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红。

    **谁是这个值的所有者**（Plan02 账本 P2-B2，Global Constraint #3）：本枚举是**词表**
    的所有者（有哪三档），而**每个动作具体是哪一档**的唯一所有者是
    ``backend/data/exercises.yaml``。spec §7.2 ``:470-471`` 的模板 YAML 字面形状里每个
    block 也自带一份 ``impact_level``，那是**副本**：Task 3 的模板加载器必须校验
    「block 的 ``impact_level`` == 动作库里的值」，不一致就在加载时响亮失败。
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
