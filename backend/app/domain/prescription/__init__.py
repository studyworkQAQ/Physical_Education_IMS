"""``app.domain.prescription`` 的公开面：从这里重导出，消费者不必记住内部模块划分。

计划的 File Structure 把本文件列为「公开面重导出」（Plan02 账本 P2-B1 指出原文没有任何
Task 的 Files 段认领它，而没有它这个包不成立，故归 Task 2）。

**逐 Task 递增**：Task 2 重导出 :mod:`~app.domain.prescription.exercises` 的 **7** 个名字
（Ruling 96 把动作库的值对象搬进 domain 之后，``ImpactLevel`` 也改成从 ``exercises`` 取——
唯一所有者在那边。本文件刻意**不从 ``templates`` 的 re-export 再 re-export**：那会让
「谁是所有者」在导入图上看不出来）。Task 3 往 ``templates.py`` / ``match.py`` 加东西、
Task 5-9 各自建自己的模块时，请同步往这里与 ``__all__`` 追加——两处必须一起改，否则
``__all__`` 会谎报公开面。

⚠️ **重导出不等于所有**（硬规矩 #39）：从这里 import 得到一个名字，不代表它的**取值**由
本包决定。``TARGET_DOMAIN`` 的值来自 :data:`app.domain.indicators.ITEM_BUCKET`，
``EQUIVALENCE_TRIGGERS`` 的取值域抄自 spec §7.4 ``:508-509``，``IMPACT_RANK`` 的秩序是
「冲击由高到低」的显式声明（``ImpactLevel`` 继承 ``str``、自己不带这个序）。本文件只搬运
名字，不搬运所有权。
"""
from .exercises import (
    EQUIVALENCE_TRIGGERS,
    IMPACT_RANK,
    TARGET_DOMAIN,
    EquivalenceMapping,
    EquivalenceTable,
    ExerciseSpec,
    ImpactLevel,
)

__all__ = [
    "EQUIVALENCE_TRIGGERS",
    "IMPACT_RANK",
    "TARGET_DOMAIN",
    "EquivalenceMapping",
    "EquivalenceTable",
    "ExerciseSpec",
    "ImpactLevel",
]
