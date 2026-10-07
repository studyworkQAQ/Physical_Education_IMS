"""``app.domain.prescription`` 的公开面：从这里重导出，消费者不必记住内部模块划分。

计划的 File Structure 把本文件列为「公开面重导出」（Plan02 账本 P2-B1 指出原文没有任何
Task 的 Files 段认领它，而没有它这个包不成立，故归 Task 2）。

**逐 Task 递增**：Task 2 重导出 :mod:`~app.domain.prescription.exercises` 的 **7** 个名字
（Ruling 96 把动作库的值对象搬进 domain 之后，``ImpactLevel`` 也改成从 ``exercises`` 取——
唯一所有者在那边）。Task 3 加 :mod:`~app.domain.prescription.templates` 的 **12** 个
（3 张词表 + 3 个维度枚举 + 5 个值对象 + 1 个纯函数）与 :mod:`app.domain.stratify` 的
**1** 个（``Layer``），共 **20** 个。Task 4 建 ``match.py``、Task 5-9 各自建自己的模块时，
请同步往这里与 ``__all__`` 追加——**两处必须一起改**，否则 ``__all__`` 会谎报公开面。
⚠️ 还有**第三处**：``tests/test_refdata_prescription.py`` 的
``_PRESCRIPTION_PUBLIC_BASELINE``（字面基线，Task 3 起每项是 ``(名字, 所有者模块)`` 二元组）
与它的 ``assert len(...) == 20``。三处不同步那条守卫就会红——那是**期望**的红
（硬规矩 #35 的正确产物：基线是字面清单，不从本文件反推）。

**每个名字都从它的所有者模块 import、不从二级 re-export 再 re-export**：``ImpactLevel`` 取自
``.exercises`` 而不是 ``.templates``（后者也 re-export 了它），``Layer`` 取自
``app.domain.stratify`` 而不是 ``.templates``。那会让「谁是所有者」在导入图上看不出来。
``.templates`` 里那两句 re-export 是给**既有导入面**用的（``from app.domain.prescription.
templates import ImpactLevel`` 这个写法在 Task 2 就存在，不能一夜之间变成 ImportError），
不是给本文件用的。

⚠️ **重导出不等于所有**（硬规矩 #39）：从这里 import 得到一个名字，不代表它的**取值**由
本包决定。``TARGET_DOMAIN`` 的值来自 :data:`app.domain.indicators.ITEM_BUCKET`，
``WeaknessBucket`` 的三个取值同样以 ``ITEM_BUCKET`` 为所有者（漂移守卫是
``test_weakness_bucket_values_are_the_three_item_bucket_names``），``Layer`` 由
:mod:`app.domain.stratify` 声明、本包只借它，``EQUIVALENCE_TRIGGERS`` 的取值域抄自
spec §7.4 ``:508-509``，``IMPACT_RANK`` 的秩序是「冲击由高到低」的显式声明（``ImpactLevel``
继承 ``str``、自己不带这个序），``TEMPLATE_LAYERS`` 是「``Layer`` 的四个成员里排除
``INSUFFICIENT``」这个**排除**声明的住址。本文件只搬运名字，不搬运所有权。
"""
from app.domain.stratify import Layer

from .exercises import (
    EQUIVALENCE_TRIGGERS,
    IMPACT_RANK,
    TARGET_DOMAIN,
    EquivalenceMapping,
    EquivalenceTable,
    ExerciseSpec,
    ImpactLevel,
)
from .templates import (
    ADDON_TRIGGERS,
    INTENSITY_TYPES,
    TEMPLATE_LAYERS,
    Addon,
    Block,
    BodyCompState,
    Intensity,
    ReviewStatus,
    Session,
    Template,
    WeaknessBucket,
    is_reachable,
)

__all__ = [
    # --- Task 2：动作库与等价表（所有者 app.domain.prescription.exercises）---
    "EQUIVALENCE_TRIGGERS",
    "IMPACT_RANK",
    "TARGET_DOMAIN",
    "EquivalenceMapping",
    "EquivalenceTable",
    "ExerciseSpec",
    "ImpactLevel",
    # --- Task 3：分层标签（所有者 app.domain.stratify，本包只借它一个名字）---
    "Layer",
    # --- Task 3：模板（所有者 app.domain.prescription.templates）---
    "ADDON_TRIGGERS",
    "INTENSITY_TYPES",
    "TEMPLATE_LAYERS",
    "WeaknessBucket",
    "BodyCompState",
    "ReviewStatus",
    "Intensity",
    "Block",
    "Session",
    "Addon",
    "Template",
    "is_reachable",
]
