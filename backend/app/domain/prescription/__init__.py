"""``app.domain.prescription`` 的公开面：从这里重导出，消费者不必记住内部模块划分。

计划的 File Structure 把本文件列为「公开面重导出」（Plan02 账本 P2-B1 指出原文没有任何
Task 的 Files 段认领它，而没有它这个包不成立，故归 Task 2）。

**逐 Task 递增**：Task 2 重导出 :mod:`~app.domain.prescription.exercises` 的 **7** 个名字
（Ruling 96 把动作库的值对象搬进 domain 之后，``ImpactLevel`` 也改成从 ``exercises`` 取——
唯一所有者在那边）。Task 3 加 :mod:`~app.domain.prescription.templates` 的 **12** 个
（3 张词表 + 3 个维度枚举 + 5 个值对象 + 1 个纯函数）与 :mod:`app.domain.stratify` 的
**1** 个（``Layer``），共 **20** 个。Task 4 加 :mod:`~app.domain.prescription.match` 的
**4** 个（1 个 status 枚举 + 2 个值对象 + 1 个纯函数），共 **24** 个。**Task 5 一次加
四个模块的 19 个**（原 Task 5/6/7/8 合并，Ruling 145）：:mod:`~app.domain.prescription.intensity`
**3**（3 个纯函数）、:mod:`~app.domain.prescription.assembler` **8**（2 张词表 + 5 个值对象 +
1 个纯函数）、:mod:`~app.domain.prescription.safety` **4**（3 个值对象 + 1 个纯函数）、
:mod:`~app.domain.prescription.override` **4**（1 个 kind 枚举 + 1 个值对象 + 2 个纯函数），
共 **43** 个。Task 6-9 各自建自己的模块时，请同步往这里与 ``__all__`` 追加——**两处必须一起改**，
否则 ``__all__`` 会谎报公开面。
⚠️ 还有**第三处**：``tests/test_refdata_prescription.py`` 的
``_PRESCRIPTION_PUBLIC_BASELINE``（字面基线，Task 3 起每项是 ``(名字, 所有者模块)`` 二元组）
与它的 ``assert len(...) == 43``、``_OWNED_MODULES``（Task 5 起是**七**个模块）。
三处不同步那条守卫就会红——那是**期望**的红
（硬规矩 #35 的正确产物：基线是字面清单，不从本文件反推）。
⚠️ **Task 5 的四个模块刻意在 5.1-5.4 四个 commit 里都*不*重导出**（测试直接从所有者模块
import），到 5.5 才一次性扩容本文件与那份基线：否则每建一个模块就要改一次字面基线
（24 → 27 → 35 → 39 → 43，四次），而每一次改动都是一次「抄漏一个名字」的机会。

**每个名字都从它的所有者模块 import、不从二级 re-export 再 re-export**：``ImpactLevel`` 取自
``.exercises`` 而不是 ``.templates``（后者也 re-export 了它），``Layer`` 取自
``app.domain.stratify`` 而不是 ``.templates``，``Template`` / ``ReviewStatus`` /
``BodyCompState`` 取自 ``.templates`` 而不是 ``.match``（后者为了写
:func:`~app.domain.prescription.match.match_template` 的签名与判据也 import 了这三个，
于是 ``app.domain.prescription.match.Template`` 同样取得到）。那会让「谁是所有者」
在导入图上看不出来。
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
⚠️ **反过来也要说清**：Task 4 那 4 个名字（``MatchStatus`` / ``MatchInput`` /
``MatchOutcome`` / ``match_template``）的所有者**就是** ``.match`` 自己，不在上面这份
「借来的」清单里；它们唯一「取值不由本包决定」的地方是 ``MatchInput.layer`` 的类型
（``Layer``）与 ``NO_LAYER`` 的 ``reason`` 文案（:mod:`app.domain.stratify` 的 Z0 那一句，
``match.py`` 里是副本、漂移守卫在
``tests/domain/test_prescription_match.py``）。
⚠️ **Task 5 那 19 个名字同理**：所有者就是 ``.intensity`` / ``.assembler`` / ``.safety`` /
``.override`` 四个模块自己。它们「取值不由本包决定」的地方有**五处**，逐处点名
（硬规矩 #39：重导出不等于所有）：
① ``StudentProfile.sex`` 的类型 :class:`app.domain.indicators.Sex`（P5-A11：绝对导入，
与 ``match.py`` 引 ``Layer`` 同口径）；
② ``AssembledBlock.impact_level`` 的**每个动作是哪一档**由 ``backend/data/exercises.yaml``
决定（P5-A8：装配器从 :class:`ExerciseSpec` 取、不从 ``Block`` 的冗余副本取）；
③ ``apply_safety`` 乘上去的两个跑量下调系数住在 ``backend/data/exercise_equivalence.yaml``
的 ``volume_reduction``（词表的键集是 ``EQUIVALENCE_TRIGGERS``）；
④ ``safety.py`` 的 ``_TRIGGER_MAP`` 是 ``ADDON_TRIGGERS`` 与 ``EQUIVALENCE_TRIGGERS`` 的
**消费者**（P5-A9，两条漂移测试字面钉住上游）；
⑤ ``assembler.py`` 的三档个体修正系数（``< 60 → 0.8``、``[60, 80) → 1.0``、``>= 80 → 1.2``、
男 ``1.0`` / 女 ``0.9``）**指导文件没给**，是工程约定（spec §14 #32，归 Task 9 登记），
它们**私有**（``_ENDURANCE_LOW_CUTOFF`` 等带前导下划线）故不在本公开面里——把一套待专家
确认的阈值做成公开契约，会让「专家调阈值」看起来像一次破坏公开面的改动。
"""
from app.domain.stratify import Layer

from .assembler import (
    VOLUME_FACTOR_BANDS,
    VOLUME_UNITS,
    AssembledBlock,
    AssembledSession,
    AssembledWeek,
    StudentProfile,
    TrainingPackage,
    assemble,
)
from .exercises import (
    EQUIVALENCE_TRIGGERS,
    IMPACT_RANK,
    TARGET_DOMAIN,
    EquivalenceMapping,
    EquivalenceTable,
    ExerciseSpec,
    ImpactLevel,
)
from .intensity import age_from, hr_zone, hrmax
from .match import (
    MatchInput,
    MatchOutcome,
    MatchStatus,
    match_template,
)
from .override import (
    OverrideKind,
    OverrideRecord,
    apply_overrides,
    summarize_overrides,
)
from .safety import (
    SafetyInput,
    SafetyOutcome,
    Substitution,
    apply_safety,
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
    # --- Task 4：模板匹配器（所有者 app.domain.prescription.match）---
    # 声明序照 match.py 里的书写序（枚举 → 两个值对象 → 纯函数），与上面三组同口径。
    "MatchStatus",
    "MatchInput",
    "MatchOutcome",
    "match_template",
    # --- Task 5 的 5.1：强度换算（所有者 app.domain.prescription.intensity）---
    # 声明序照 intensity.py 里的书写序（三个纯函数）。
    "hrmax",
    "hr_zone",
    "age_from",
    # --- Task 5 的 5.2：装配器（所有者 app.domain.prescription.assembler）---
    # 声明序照 assembler.py 里的书写序（2 张词表 → 5 个值对象自底向上 → 纯函数）。
    "VOLUME_UNITS",
    "VOLUME_FACTOR_BANDS",
    "StudentProfile",
    "AssembledBlock",
    "AssembledSession",
    "AssembledWeek",
    "TrainingPackage",
    "assemble",
    # --- Task 5 的 5.3：安全后置（所有者 app.domain.prescription.safety）---
    "SafetyInput",
    "Substitution",
    "SafetyOutcome",
    "apply_safety",
    # --- Task 5 的 5.4：教师覆盖（所有者 app.domain.prescription.override）---
    "OverrideKind",
    "OverrideRecord",
    "apply_overrides",
    "summarize_overrides",
]
