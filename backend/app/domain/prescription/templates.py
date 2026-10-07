"""处方模板的**数据结构**与维度词表（Plan 02：Task 2 建、**Task 3 填**）。

⚠️ **「本模块没有任何自己的定义」是 Task 2 时点的状态，Task 3 起已经不成立**
（Plan02 账本 Ruling 96 那半段的历史）：Task 2 原来放在这里的
:class:`~app.domain.prescription.exercises.ImpactLevel` 已迁往
:mod:`app.domain.prescription.exercises`，那时本文件只剩一句 re-export 与一个 ``__all__``。
**为什么迁走**：``ImpactLevel`` 是 ``ExerciseSpec.impact_level`` 与 ``IMPACT_RANK`` 的类型，
留在本模块会让 ``exercises.py`` 反向 import 本模块；而依赖方向恰恰相反——本模块的模板
dataclass 带 ``exercise_ref`` 与 ``impact_level`` 两个字段，即**模板引用动作库、
动作库不引用模板**。File Structure 说本模块是「模板的数据结构与维度词表」，Ruling 96 之后
「**动作库**的维度词表」那一半归 ``exercises.py``，本模块留「模板的数据结构」
（Task 3 落地：3 个维度枚举 + 5 个值对象 + 1 个纯函数）与模板自己要用的维度词表
（3 张：``TEMPLATE_LAYERS`` / ``INTENSITY_TYPES`` / ``ADDON_TRIGGERS``）。

**re-export 的口径**（照 ``app/pipeline/run_stratify.py:50-57`` 那次同类搬迁）：
``ImpactLevel`` 的**唯一所有者**是 :mod:`app.domain.prescription.exercises`，``Layer`` 的
**唯一所有者**是 :mod:`app.domain.stratify`，本模块只是保持既有导入面——
``app.domain.prescription.templates.ImpactLevel`` 与 ``….templates.Layer`` 都照旧可用。
**新代码请直接从所有者导入**；两份 re-export 各有一条守卫看着（
``tests/domain/test_prescription_templates.py`` 的
``test_templates_module_still_reexports_impact_level`` 与
``test_templates_module_still_reexports_layer``）。``__all__`` 里列着它们，是为了让这次
re-export 是一次**显式**声明，而不是「碰巧留在命名空间里」：没有 ``__all__``，
下一个人会以为它本模块私有、可放心改名。

**``Layer`` 为什么是 re-export 而不是本模块自己声明一个**：分层标签的唯一所有者是
:mod:`app.domain.stratify`——``stratification_result.label`` 那一列、``RULE_ORDER`` 与 Z0
闸门都用它。模板的 ``layer`` 维度必须与它**逐字同一**，否则 Task 4 的匹配器要在一处把
``"red"`` 翻译成另一个枚举，而那张翻译表就是第二个所有者（Global Constraint #3）。
⚠️ 但**模板维度只有前三个**：``Layer.INSUFFICIENT``（``"insufficient_data"``）不是合法
模板层——spec §6.1 的 Z0 闸门在 ``valid_count < 4`` 时**不产出分层标签**，故没有任何学生
会带着它来匹配模板。这个「排除」由 :data:`TEMPLATE_LAYERS` 显式声明，加载器与 DB 的
CHECK 都照它办（``prescription_template.layer`` 的 CHECK ∈ ``{red, yellow, green}``）。

**两份 ``__all__`` 必须一起改**：本模块一份、``app/domain/prescription/__init__.py`` 一份，
否则公开面谎报（Task 2 写下的这句叮嘱，Task 3 已照办；两边的守卫分别是
``test_templates_module_still_reexports_impact_level`` 的支 1 与
``tests/test_refdata_prescription.py`` 的
``test_prescription_public_namespace_is_pinned_verbatim`` 的支 2/支 5）。

**为什么不读盘**（Global Constraint #1）：``app/domain/`` 是无 I/O 的叶子层，
YAML 的解析与校验住在 :mod:`app.refdata_prescription`，解析结果作为**参数**注入 domain
的纯函数。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手结果就可
复现、可追溯（spec §1.3）。这条由 :mod:`tests.architecture.test_domain_purity` 的
allow-list 守卫机器可查地钉住：domain 只允许 import 6 个标准库模块串（``dataclasses`` /
``enum`` / ``collections`` / ``collections.abc`` / ``numpy`` / ``typing``）与 ``app.domain``
前缀。本模块今天的 3 句 import 全部落在其中：``collections.abc`` 与 ``dataclasses`` /
``enum`` 命中 6 个串，``app.domain.stratify`` 与同包的 ``.exercises`` 命中前缀
（相对导入被那道守卫折算成 ``app.domain.prescription.exercises``）。

⚠️ **``datetime`` 不在 allow-list 里**，故 :attr:`Template.reviewed_at` 的类型是
``str | None``（ISO 8601 的 ``YYYY-MM-DD``）而**不是** ``datetime.date``。这不是偷懒：
为了一个日期字段去放宽那道架构守卫，代价是 domain 从此可以读时钟（Global Constraint #1
点名要挡的就是 ``date.today()``）。转成 ``date`` 的那一步住在
:func:`app.refdata_prescription.sync_templates`（落库边界，``prescription_template.
reviewed_at`` 那一列是 ``Date``）。

⚠️ **本模块只承载值、不校验值**（硬规矩 #39，与 :mod:`app.domain.prescription.exercises`
同一口径）：直接构造 :class:`Template`（绕过加载器）可以得到一个 ``weekly_frequency`` 与
``sessions`` 数不符、``week_deltas`` 长度与 ``microcycle_weeks`` 不符、``exercise_ref``
悬空的对象，本模块不拦，也没有任何一条测试会红。全部校验住在加载器
:mod:`app.refdata_prescription` 与 ``tests/domain/test_prescription_templates.py`` 里。
**唯一的例外**是 ``review_status``：它**刻意不在构造期校验**（``pending`` 是合法值，
spec §7.2 ``:451`` 的「拒绝用于生成」是 Task 4 匹配器的职责，不是构造器的）——
守卫是 ``test_a_pending_template_is_constructible_so_task_4_has_something_to_reject``。
"""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from app.domain.stratify import Layer

from .exercises import ImpactLevel

#: 合法的**模板层**：``Layer`` 的四个成员里排除 ``INSUFFICIENT``。
#: 出处：spec §7.1 ``:443`` 的「层(3)」与 §7.2 ``:456`` 的行内注释「``red | yellow | green``」。
#: 消费方：① 加载器（``layer: insufficient_data`` 在加载时响亮失败）；② DB 的 CHECK
#: （``PrescriptionTemplate.LAYERS`` 与它逐字一致，由
#: ``test_prescription_template_vocabulary_agrees_with_the_domain_enums`` 对账）；
#: ③ Task 4 的匹配器（一个 ``insufficient_data`` 的学生不该匹配到任何模板）。
TEMPLATE_LAYERS: frozenset[Layer] = frozenset({Layer.RED, Layer.YELLOW, Layer.GREEN})


class WeaknessBucket(str, Enum):
    """主导短板桶（模板的第二个维度）。spec §7.2 ``:457`` 的行内注释逐字给出三个取值。

    **取值必须与 :data:`app.domain.indicators.ITEM_BUCKET` 的值逐字相同**（Global
    Constraint #3：``ITEM_BUCKET`` 是桶名的所有者，本枚举是它在模板维度上的**引用**）。
    ⚠️ 对账公式是 ``set(ITEM_BUCKET.values()) - {None}``，**不是** ``set(ITEM_BUCKET.values())``
    ——后者有 4 个元素、含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，BMI 属身体形态、
    已由体成分维度 ``C`` 覆盖，故不入桶；出处是 spec §4.2 那张「8 项原始测量」表的 BMI 行
    与同节说明「**短板判定项 = 6 个**（**排除 BMI**）」，Plan02 账本 P2-A4）。
    漂移守卫是 ``test_weakness_bucket_values_are_the_three_item_bucket_names``。

    **继承 ``str``** 的理由与 :class:`~app.domain.prescription.exercises.ImpactLevel` 相同：
    ``prescription_template.weakness`` 那一列是 ``String(20)``，继承 ``str`` 之后
    ``WeaknessBucket.STRENGTH == "strength"`` 直接成立，不必在 ORM 边界上处处写 ``.value``。
    """

    ENDURANCE = "endurance"
    STRENGTH = "strength"
    SPEED_FLEXIBILITY = "speed_flexibility"


class BodyCompState(str, Enum):
    """体成分状态（模板的第三个维度）。spec §7.2 ``:458`` 的行内注释逐字给出两个取值。

    ⚠️ **声明序照 spec 那一行的书写序**（``normal | abnormal``），与
    :class:`WeaknessBucket` 同口径。它只有两档，而 spec §6.3 的 ``C`` 判定本身更细
    （体脂率 / 肌肉量两个子条件）——本枚举是**分层时点的粗档**，不是体成分测量值；
    细的判定住在 :mod:`app.domain.stratify`，模板只按它的结论分两套。
    """

    NORMAL = "normal"
    ABNORMAL = "abnormal"


class ReviewStatus(str, Enum):
    """模板的审校状态。spec §4.4 ``:238`` 逐字：``review.status`` ∈ {``pending``, ``approved``}。

    **spec §7.2 ``:451`` 的后果**：「``review.status != approved`` 的模板拒绝用于生成」。
    ⚠️ 那条拒绝**不住在本模块**（硬规矩 #39）：``pending`` 是一个**合法的数据值**，
    构造一个 ``review_status=PENDING`` 的 :class:`Template` 必须成功，否则 Task 4 的匹配器
    根本拿不到它、「拒绝」与「不存在」就分不开了（教师要看到的是「这一套还没审校」，
    不是一个查不到的键）。守卫是
    ``test_a_pending_template_is_constructible_so_task_4_has_something_to_reject``。

    ⚠️ **今天 18 套全是 ``approved``，而那不是审校结果**：用户已裁定原型阶段全部标
    ``approved`` + 占位审校人，须由邹红老师实际审校后替换（spec §14 第 **29** 项）。
    """

    PENDING = "pending"
    APPROVED = "approved"


#: ``Intensity.type`` 的取值域（简报 Interfaces / Produces 逐字列举的四个）。
#: ``hrmax_pct`` 与 ``onerm_pct`` 能在 spec §7.2 骨架 ``:472`` / ``:476`` 逐字找到；
#: ``rpe`` 的出处是 spec §8.2 的课堂快评 RPE 0–10（Plan 03 的预警侧用同一套强度语义）；
#: ``none`` 是「指导文件没给这一层的强度参数」时的**显式**取值——留空与写 ``none``
#: 不是一回事，留空分不清「不需要强度区间」与「忘了填」（与 ``exercises.yaml`` 的
#: ``equipment: none`` 同一条理由）。今天绿层 6 套与黄层 6 套的 block 全是 ``none``，
#: 因为 spec §7.2 ``:487`` 只给了红层的两个数（60–70% HRmax 与 70% 1RM）。
INTENSITY_TYPES: frozenset[str] = frozenset({"hrmax_pct", "onerm_pct", "rpe", "none"})

#: ``Addon.when`` 的取值域。spec §7.2 骨架 ``:481`` / ``:483`` 逐字给出两个。
#: ⚠️ **它与 :data:`app.domain.prescription.exercises.EQUIVALENCE_TRIGGERS` 是两张不同的
#: 词表、刻意不合并**：那一张（``bmi_over_30`` / ``muscle_low_p10``）是 spec §7.4
#: ``:508-509`` 里**走等价表**的两个触发，这一张是 ``:510``「追加模板 ``addons`` 中的
#: 能量消耗模块」、**不查等价表**的那一条。字面值也不同（``body_fat_over`` vs
#: ``bmi_over_30``），合并会让「哪条路该走哪张表」在类型上看不出来（Plan02 账本 P2-C3）。
ADDON_TRIGGERS: frozenset[str] = frozenset({"body_fat_over", "muscle_low"})


@dataclass(frozen=True)
class Intensity:
    """一个 block 的强度处方。spec §7.2 骨架 ``:472`` 与 ``:476`` 给了两种字面形状。

    ``type`` 决定哪几个字段有值，四种组合互斥（由加载器校验，本模块不拦）：

    ==============  ==========================  ==================================
    ``type``         有值的字段                 出处
    ==============  ==========================  ==================================
    ``hrmax_pct``    ``low`` + ``high``          spec §7.2 ``:472``（60–70% HRmax）
    ``onerm_pct``    ``value``                   spec §7.2 ``:476``（70% 1RM）
    ``rpe``          ``value``                   spec §8.2 的 RPE 0–10 同一套语义
    ``none``         三个都是 ``None``           指导文件未给这一层的强度参数
    ==============  ==========================  ==================================

    ⚠️ **``low`` / ``high`` / ``value`` 一律是 ``float``**（加载器把 YAML 里的 ``60`` 收敛成
    ``60.0``）：Task 5 要拿它们做算术（``HRmax × low/100``），int 与 float 混用会让
    「区间端点是不是含端点」这类比较在两个类型间行为不同。

    **三个字段都有缺省值 ``None``**，故 ``Intensity(type="none")`` 可以直接构造——那是
    绿层与黄层 12 套模板的实际形状。
    """

    type: str
    low: float | None = None
    high: float | None = None
    value: float | None = None


@dataclass(frozen=True)
class Block:
    """一次课里的一个训练块。spec §7.2 骨架 ``:470-477`` 的字面形状。

    ``exercise_ref`` 的**唯一所有者**是 ``backend/data/exercises.yaml`` 的顶层键集
    （Global Constraint #3），加载器校验它存在（Review Focus 第 1 条）。

    ``impact_level`` 是**副本**（Plan02 账本 P2-B2）：唯一所有者同样是 ``exercises.yaml``，
    而 spec §7.2 骨架 ``:471`` 的字面形状里每个 block 自带一份（行内注释逐字：
    「供安全后置处理识别」）。加载器校验两份一致，不一致就在加载时响亮失败。
    **为什么保留这个副本**：专家审校一套模板时，「这一套对 BMI > 30 的学生安不安全」的
    唯一线索就是冲击等级；把它从模板里拿走（改成从动作库现取）虽然少一个所有者，
    却把它从专家眼前也拿走了。故照骨架写、由加载器对账。

    ``structure`` 是 ``Mapping`` 而**不是**计划里写的 ``dict``：运行时对象是
    ``types.MappingProxyType``，它不是 ``dict`` 的实例，标 ``dict`` 会是一个假标注
    （与 :func:`app.refdata_prescription.load_exercises` 的返回类型标注同一处置）。
    **只读是承重的**：``frozen=True`` 只挡「换掉整个字段」，挡不住
    ``block.structure["sets"] = 99``，而 :func:`app.refdata_prescription.templates` 是
    进程内共享单例，一次误写会让之后所有装配静默变质。
    ⚠️ 键集**不受约束**（``sets`` / ``work_min`` / ``rest_min`` / ``rounds`` / ``reps`` …）：
    spec 只给了两个字面例子（``:473`` 与 ``:477``），没有给键的词表，故本 Task 不编一个。
    Task 6 的装配器消费它时必须自己认得这些键——那是一次需要 spec 补口径的接触面，
    已作为关切报出。
    """

    exercise_ref: str
    impact_level: ImpactLevel
    intensity: Intensity
    structure: Mapping[str, object]


@dataclass(frozen=True)
class Session:
    """一周里的一个训练日。spec §7.2 骨架 ``:467-469`` 的字面形状。

    ``day`` 是 **1 基**且在一套模板内连续（加载器校验 ``[s.day for s in sessions] ==
    1..N``）：Task 11 的「本周训练单」按周次取课、打卡完成率按处方训练日计
    （spec §14 第 9 项），``day`` 跳号会让「第 3 天该打卡吗」没有答案。

    ``focus`` 是这一天的中文主题（骨架 ``:468`` 的字面值是 ``耐力``）。本 Task 的 18 套里
    它恒等于**桶名**（耐力 / 力量 / 速度柔韧）——指导文件按「层 × 短板」给参数、
    **没有**按周内第几天给，故同一套模板的每一天 ``focus`` 相同；要分化到「周一练什么、
    周三练什么」需要专家给出参数，已并入 spec §14 第 29 项的审校范围。
    """

    day: int
    focus: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Addon:
    """一个条件式追加模块。spec §7.2 骨架 ``:480-484`` 的字面形状。

    ``when`` ∈ :data:`ADDON_TRIGGERS`，``module`` 是一个 ``exercise_ref``（加载器校验它在
    动作库里）。spec §7.4 ``:510`` 的第三个触发（体脂率异常）走的就是这一条路：
    「追加模板 ``addons`` 中的能量消耗模块」，**不查等价表**。

    ⚠️ **声明一个 addon 不等于它会触发**：触发是 Task 7 按学生当下的体测值判定的。
    故 ``body_comp: normal`` 的那 9 套模板**也**声明 ``body_fat_over`` 的 addon——
    模板的 ``body_comp`` 维度是**分层时点**的粗档，而一个「分层时体成分正常、期中体脂
    超标」的学生仍然需要那个模块。把两者绑起来会让他拿不到。
    """

    when: str
    module: str


@dataclass(frozen=True)
class Template:
    """一套完整的 4 周运动处方模板（18 套之一）。

    **字段顺序照简报 Interfaces / Produces 的列举**，其中四个是 spec §7.2 骨架里
    **嵌套块**摊平的结果（Plan02 账本 P3-C3）：``review``（骨架 ``:460-463``）→
    ``review_status`` / ``reviewer`` / ``reviewed_at``，``progression``（骨架
    ``:478-479``）→ ``week_deltas``。摊平的理由：这四个字段各自都是一个标量，
    嵌套只会让消费方多写两层 ``.review.status``，而**校验**（缺块要在加载时响亮失败、
    不能变成 ``KeyError``）是加载器的职责，不需要值对象保持同形。

    ``reachable`` 是 spec §4.4 ``:238`` 字段清单**之外**的一列增补，依据是 spec §7.1
    ``:447``「生成器对这 3 套标记 ``reachable: false``，不参与匹配」（Plan02 账本 P3-A10；
    已在 spec §7.2 的勘误里交代，不让它看起来像 §4.4 的原文）。它的值必须与
    :func:`is_reachable` 一致，由加载器校验。

    ``reviewed_at`` 是 ``str | None``（ISO ``YYYY-MM-DD``）而**不是** ``datetime.date``：
    ``app/domain/`` 的 allow-list 不放行 ``datetime``，见模块 docstring 的倒数第三段。

    ⚠️ **本模块不校验它**（硬规矩 #39）：``weekly_frequency`` 与 ``len(sessions)`` 不符、
    ``week_deltas`` 长度与 ``microcycle_weeks`` 不符、``exercise_ref`` 悬空——直接构造都能
    构造出来，且没有一条测试会红。全部校验住在 :func:`app.refdata_prescription.load_templates`。
    """

    template_id: str
    version: str
    layer: Layer
    weakness: WeaknessBucket
    body_comp: BodyCompState
    reachable: bool
    review_status: ReviewStatus
    reviewer: str | None
    reviewed_at: str | None
    microcycle_weeks: int
    weekly_frequency: int
    sessions: tuple[Session, ...]
    week_deltas: tuple[float, ...]
    addons: tuple[Addon, ...]


def is_reachable(layer: Layer, body_comp: BodyCompState) -> bool:
    """这一格「层 × 体成分」当前**是否可达**。它是 ``reachable`` 的唯一所有者。

    出处：spec §7.1 ``:445``「按 §6.2 决策表，绿色层必然 ``NOT C``，因此
    ``(green, *, abnormal)`` 这 3 套**当前不可达**」；``:447``「保留为**预留位**，不删除…
    生成器对这 3 套标记 ``reachable: false``，不参与匹配」。

    **两处消费**：① 加载器用它校验 YAML 里写的 ``reachable`` 与维度组合不矛盾
    （矛盾就在加载时响亮失败——Review Focus 第 1 条点名的第 4 种坏形状）；
    ② Task 4 的匹配器按它排除预留位。

    ⚠️ **将来分层规则若真的调整**（spec §7.1 ``:447`` 的②：「允许『8 项达标但体成分异常』
    者留在绿色层做体成分专项干预」），**改这一个函数**就能让那 3 套上线；只翻 YAML 里的
    ``reachable`` 而不动本函数，加载器会拒绝那 3 个文件。这是刻意的耦合：一条规则两个住址
    必然漂移（Global Constraint #3），而「预留位就绪」的价值恰恰在于**改一处**就能启用。

    ``weakness`` 不参与判定，故签名里没有它——spec 的不可达结论对三个桶同时成立
    （写作 ``(green, *, abnormal)``）。
    """
    return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)


__all__ = [
    # 词表（单一所有者，Global Constraint #3）
    "ADDON_TRIGGERS",
    "INTENSITY_TYPES",
    "TEMPLATE_LAYERS",
    # 维度枚举
    "Layer",
    "WeaknessBucket",
    "BodyCompState",
    "ReviewStatus",
    # 值对象（自底向上）
    "Intensity",
    "Block",
    "Session",
    "Addon",
    "Template",
    # 纯函数
    "is_reachable",
    # re-export（所有者在 app.domain.prescription.exercises）
    "ImpactLevel",
]
