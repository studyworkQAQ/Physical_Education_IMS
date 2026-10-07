"""动作库与低冲击等价映射表的**值对象**（Plan 02 Task 2；Ruling 96 自加载器迁入 domain）。

**为什么住 domain、而不是与唯一的加载器同住**（Plan02 账本 Ruling 96）：照抄本仓既有的
同构先例——``StandardTable`` 这个值类型住 :mod:`app.domain.tables`，解析 CSV 的加载器
``load_standard()`` / ``standard()`` 住 :mod:`app.refdata`，而 ``app/refdata.py:29`` 写的是
``from app.domain.tables import StandardTable``。即「**值类型住 domain、加载器住 domain
外、加载器 import 值类型**」。本模块就是那一层值类型：``exercises.yaml`` 与
``exercise_equivalence.yaml`` 的解析与校验住在 :mod:`app.refdata_prescription`，解析出来
的东西就是这里的四个不可变对象与三张词表。

**搬迁的直接动因不是审美**：:mod:`tests.architecture.test_domain_purity` 的 allow-list
**不放行 ``app.domain`` → 非 ``app.domain`` 的 import**。值对象若留在加载器模块里，Task 7
的 ``app/domain/prescription/safety.py`` 就**拿不到这三个类型做标注**，而 spec §7.4 的等价
替换恰恰要调 :meth:`EquivalenceTable.lookup`——它只能按 duck typing 接，于是「传进来的到底
是不是一张等价表」在类型层面看不出来。

**不读盘**（Global Constraint #1）：本模块的 import 只有 ``enum`` / ``dataclasses`` /
``collections.abc`` 与 ``app.domain.indicators``，四者都在上面那道 allow-list 内（亲跑
``_is_allowed``：三个标准库串命中 :data:`ALLOWED_MODULES`，第四个命中前缀
``app.domain.``）。于是 domain 不会隐式依赖磁盘上某个 YAML 是否存在，同一份输入在手，
结果就可复现、可追溯（spec §1.3）。

**``ImpactLevel`` 为什么也住在这里、而不是留在 ``templates.py``**（Ruling 96 ③）：它是
``ExerciseSpec.impact_level`` 的类型、也是 :data:`IMPACT_RANK` 的键类型，留在
``templates.py`` 会让本模块反向依赖模板模块；而**依赖方向恰恰相反**——Task 3 的模板
dataclass 会带 ``exercise_ref`` 与 ``impact_level`` 两个字段，即模板引用动作库、动作库不
引用模板。故 ``templates.py`` 改成从本模块 import 并 re-export 它（保持既有导入面，口径照
``app/pipeline/run_stratify.py:50-57`` 那次同类搬迁）。

⚠️ **本模块守不住什么**（硬规矩 #39）：它只**承载**值、不校验值。「``exercises.yaml`` 里
每个 ``impact_level`` 都在词表内」「每条映射声明的 ``max_impact`` 与 ``to_ref`` 的真实冲击
一致」「每个 ``targets`` 都落在 :data:`TARGET_DOMAIN` 里」——这些校验全部住在加载器
:mod:`app.refdata_prescription` 与 ``tests/test_refdata_prescription.py`` 里。**直接构造**
:class:`ExerciseSpec`（绕过加载器）可以得到一个 ``targets`` 为空、``impact_level`` 拼错的
对象，本模块不拦，也没有任何一条测试会红。
"""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from app.domain.indicators import ITEM_BUCKET


class ImpactLevel(str, Enum):
    """spec §4.4 ``:239`` 的 ``exercise.impact_level`` 取值域：``high`` / ``medium`` / ``low``。

    **继承 ``str``**：``exercise.impact_level`` 那一列是 ``String(8)``，继承 ``str`` 之后
    ``ImpactLevel.HIGH == "high"`` 直接成立，落库与读回都是同一个字符串，不必在 ORM 边界
    上处处写 ``.value``。漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()``
    存成 ``"ImpactLevel.HIGH"``（19 字符，还撑破 ``String(8)``——SQLite 不强制长度，故
    写侧不报错，换严格长度的后端才截断，硬规矩 #18 的那个失效形态）。

    ⚠️ **它不携带序**：继承 ``str`` 意味着 ``<`` 是**字典序**，即
    ``ImpactLevel.HIGH < ImpactLevel.LOW < ImpactLevel.MEDIUM``，与「冲击由高到低」完全
    无关。冲击序由消费方显式声明，今天有两份、刻意不同源（硬规矩 #35）：生产侧是
    **本模块**的 :data:`IMPACT_RANK`（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
    :mod:`app.refdata_prescription`），测试侧
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


#: ``targets`` 的取值域：``ITEM_BUCKET`` 的三个桶名。
#: ⚠️ **不是 ``set(ITEM_BUCKET.values())``**（Plan02 账本 P2-A4）：那个集合有 **4** 个元素、
#: 含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶，
#: Plan01 Ruling 19 的口径），照字面写会把 ``None`` 放进取值域、并让一个空 ``targets``
#: 悄悄合法。由 ``tests/test_refdata_prescription.py`` 的
#: ``test_target_domain_is_the_three_bucket_names_not_the_raw_values`` 钉住这个构造方式。
TARGET_DOMAIN: frozenset[str] = frozenset(
    bucket for bucket in ITEM_BUCKET.values() if bucket is not None
)


#: spec §7.4 ``:508-509`` 里**走等价表**的两个触发条件（``when`` 的取值域）。
#: ``:510`` 的第三个触发（体脂率异常）走的是「追加模板 ``addons`` 中的能量消耗模块」、
#: **不查等价表**，故它不在这里（Plan02 账本 P2-C3 亲验）。
EQUIVALENCE_TRIGGERS: frozenset[str] = frozenset({"bmi_over_30", "muscle_low_p10"})


#: 冲击等级的**降序**排名（0 = 冲击最高）。
#: ⚠️ 不能靠 ``ImpactLevel`` 的比较得出序：它继承 ``str``，``<`` 是字典序
#: （``"high" < "low" < "medium"``），与冲击序无关。测试侧另有一份**字面写死**的
#: ``IMPACT_DESCENDING``（``tests/test_refdata_prescription.py``），两份刻意不同源
#: （硬规矩 #35）：改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level``
#: 与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
#: 之一会红。
#:
#: **改名（Ruling 96）**：搬进 domain 之前它叫 ``_IMPACT_RANK``、住在
#: :mod:`app.refdata_prescription`。前导下划线在那里表示「本模块私有」；搬进来之后它是
#: domain 公开面的一部分（``app/domain/prescription/__init__.py`` 重导出它），而跨模块
#: import 一个带前导下划线的名字自相矛盾，故去掉下划线。**秩值一个未改**（0=high、
#: 2=low），改的是名字与住址。
IMPACT_RANK: dict[ImpactLevel, int] = {
    ImpactLevel.HIGH: 0,
    ImpactLevel.MEDIUM: 1,
    ImpactLevel.LOW: 2,
}


@dataclass(frozen=True)
class ExerciseSpec:
    """``exercises.yaml`` 的一个条目。

    ``ref`` 是 ``exercise_ref`` 的**唯一所有者**（Global Constraint #3）：模板 YAML 与
    ``exercise_equivalence.yaml`` 都按它引用动作，而它的键集就住在那份 YAML 的顶层键上。
    Task 3 的模板加载器必须校验「每个 ``exercise_ref`` 都在动作库里」，违例在加载时响亮
    失败（Review Focus 第 1 条）。

    ``impact_level`` 同样是单一所有者（Plan02 账本 P2-B2）：**本字段是「这个动作是哪一档
    冲击」的唯一真相**。spec §7.2 ``:470-471`` 的模板 YAML 字面形状里每个 block 也自带一份
    ``impact_level``，那是**副本**；**负责校验一致的是 Task 3 的模板加载器**（不一致就在
    加载时响亮失败，与 ``exercise_ref`` 的处置同构）——加载器
    :mod:`app.refdata_prescription` 只加载动作库、看不到模板，故校验不住这件事，
    这一点必须写明（硬规矩 #39）。

    ``targets`` 是 ``frozenset``：一个动作可以同时瞄准多个素质桶（如折返跑既是耐力也是
    速度），而桶的**顺序不承重**（Task 4 的匹配按主导短板桶查，不按序）。用 ``frozenset``
    而不是 ``tuple`` 正是为了在类型上排除「顺序有意义」这个误读。
    """

    ref: str
    name: str
    video_url: str
    impact_level: ImpactLevel
    targets: frozenset[str]
    equipment: str


@dataclass(frozen=True)
class EquivalenceMapping:
    """``exercise_equivalence.yaml`` 的 ``mappings`` 里的一条。

    ``from_ref`` 是被替换的动作（今天全是 ``high`` 冲击），``to_ref`` 是替身，
    ``max_impact`` 是这条映射**自己声明**的替身冲击上限，``when`` 是触发条件。

    ``max_impact`` 与 ``to_ref`` 的真实冲击必须一致——:meth:`EquivalenceTable.lookup`
    是按 ``max_impact`` 过滤的、**不看动作库**，故一张撒谎的表会让 lookup 返回一个冲击
    高于上限的动作。这条一致性由
    ``tests/test_refdata_prescription.py::test_equivalence_never_maps_to_a_higher_impact_level``
    钉住（它同时验「不升冲击」与「声明与真实一致」两件事）。
    """

    from_ref: str
    to_ref: str
    max_impact: ImpactLevel
    when: str


@dataclass(frozen=True)
class EquivalenceTable:
    """一张完整的低冲击等价映射表（spec §4.4 ``:243``：静态 YAML + **版本号**，不入库）。

    ``version`` 会被 Task 7 写进 ``prescription.safety_substitutions``（spec §7.4 ``:512``
    要求记录「原动作、新动作、触发条件、**映射表版本号**」），于是一张已生成的处方能回答
    「当时是按哪一版映射表替换的」。

    ``volume_reduction`` 的两个系数是「跑量按映射表下调」（spec §7.4 ``:508-509``）的
    具体数值。⚠️ **它们在 spec 里没有出处**（Plan02 账本 P2-A3）：``:508`` 只写「按映射表
    下调」、没给任何数，``:509`` 写「同上」。spec 里唯一出现的「系数 0.8」在 ``:604``，
    那是**预警触发的减量 20%**（``weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)``，
    属 Plan 03），与本表的跑量下调是**两个不同机制**；``0.9`` 在 spec 里根本没有对应物。
    故这两个数是**本设计的默认规定**，已登记进 ``exercise_equivalence.yaml`` 的注释与
    spec §14 第 28 项；**Task 7 消费时不得把它们当成 spec 条文引用**。
    """

    version: str
    mappings: tuple[EquivalenceMapping, ...]
    volume_reduction: Mapping[str, float]

    def lookup(self, ref: str, impact_ceiling: ImpactLevel) -> str | None:
        """``ref`` 在冲击不超过 ``impact_ceiling`` 的前提下的替身；查不到返回 ``None``。

        返回 ``None`` **不是**「静默跳过」：spec §7.4 ``:514`` 明写「安全规则命中但映射表
        找不到等价动作时，不静默跳过」——生成 ``warning`` 级日志、处方状态置
        ``needs_review``、教师端标记「需人工复核」。故 Task 7 拿到 ``None`` 必须走那条路径
        （Review Focus 第 5 条），而不是把原动作留在训练包里。

        命中条件是 ``IMPACT_RANK[max_impact] >= IMPACT_RANK[impact_ceiling]``，即映射
        声明的上限**不高于**调用方给的上限。取**第一条**命中者：``mappings`` 的顺序就是
        YAML 里的书写顺序（:func:`~app.refdata_prescription.load_equivalence` 不重排），
        故专家可以通过调整书写顺序来
        表达偏好，而不必引入一个额外的优先级字段。
        """
        ceiling_rank = IMPACT_RANK[impact_ceiling]
        for mapping in self.mappings:
            if mapping.from_ref != ref:
                continue
            if IMPACT_RANK[mapping.max_impact] >= ceiling_rank:
                return mapping.to_ref
        return None
