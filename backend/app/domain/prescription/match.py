"""层 × 主导短板 × 体成分 → 一套处方模板（Plan 02 Task 4；spec §7.1–7.2、§11.2）。

**它是纯函数、不做 I/O**（Global Constraint #1）：``templates`` 由调用方注入
（生产路径上是 :func:`app.refdata_prescription.templates` 那个进程内单例），本模块不读盘、
不 import ``yaml`` / ``sqlalchemy`` / ``pathlib``。于是「同一份输入 → 同一个结果」与磁盘上
有哪些 YAML 无关（spec §1.3 的可复现要求），且
:mod:`tests.architecture.test_domain_purity` 的 allow-list 守卫能机器可查地钉住这件事。

**返回的 :class:`MatchOutcome` 六种 status 一律留痕**，没有一种静默返回 ``None``：
教师端要能分清「这个学生今天没有分层结果」（``NO_LAYER``）、「他的短板判定项全无效」
（``NO_BUCKET``）、「模板矩阵少一个文件」（``NO_TEMPLATE``）、「这一格是预留位」
（``UNREACHABLE``）与「这一套还没审校」（``NOT_APPROVED``）——五件事的处置人各不相同
（补测 / 补测 / 补 YAML / 无需处置 / 催审校），合并成「没有模板」就没人知道该找谁。

--------------------------------------------------------------------------

**优先级链（承重的、换序就换语义）**::

    NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED

命中即停，与 :data:`app.domain.stratify.RULE_ORDER` 同一套写法（那边逐行求值、命中即停，
注释逐字写着「**这个元组是承重的**」）。链上三处的顺序理由：

1. **``NO_BUCKET`` 必须先于 ``UNREACHABLE``**（Plan02 账本 P4-A3 点名的最隐蔽处）：
   ``(green, None, abnormal)`` 这一格**同时**满足「主导短板为空」与「绿层 + 体成分异常」
   两个判据。顺序对调之后，32 格穷举的分类从 ``{NO_LAYER: 8, NO_BUCKET: 6,
   UNREACHABLE: 3, MATCHED: 15}`` 变成 ``{NO_LAYER: 8, NO_BUCKET: 4, UNREACHABLE: 5,
   MATCHED: 15}``——**总数仍是 32**。即「计数对得上」证明不了顺序对，只有一格一格看
   期望表才发现。守卫是
   ``tests/domain/test_prescription_match.py`` 的
   :func:`~tests.domain.test_prescription_match.test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable`
   （单格钉住）与 :data:`~tests.domain.test_prescription_match._MATRIX_32`（按链序排列的
   32 格逐格比对）。
2. **``NO_TEMPLATE`` 必须先于 ``UNREACHABLE`` / ``NOT_APPROVED``**：查不到模板就没有
   ``reachable`` / ``review_status`` 可读，反过来的顺序会在缺格时抛 ``KeyError``
   （或在 ``None`` 上取属性），而那正是「专家少放了一个 YAML 文件」最常见的形状。
3. **``UNREACHABLE`` 先于 ``NOT_APPROVED``**（简报原文已给的那一对）：一套既不可达又未
   审校的模板报 ``UNREACHABLE``（**规格事实**：spec §7.1 说这一格按 §6.2 决策表根本
   不会出现）而不是 ``NOT_APPROVED``（**流程状态**：还没人签字）。教师端据此区分
   「不用催审校，这一格本来就不该有学生」与「去催邹红老师」。

``NO_LAYER`` 先于全部三条：Z0 闸门（spec §6.3①、§11.1）在 ``valid_count < 4`` 时**不产出
分层标签**，此时谈「匹配哪一套模板」没有意义。

--------------------------------------------------------------------------

**``reachable`` 读的是字段、不是函数**（Plan02 账本 P4-A2 的裁定）：

* **规则的唯一所有者**是 :func:`app.domain.prescription.templates.is_reachable`
  （``return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)``）；
* **数据的唯一所有者**是 ``backend/data/prescription/*.yaml`` 里每套模板的 ``reachable``
  键，它经加载器变成 :attr:`Template.reachable`；
* 加载器 :func:`app.refdata_prescription.load_templates` **已强制两者一致**（矛盾就在
  加载时响亮失败——Review Focus 第 1 条点名的第 4 种坏形状）。

故本函数**只读字段**：再调一次 :func:`is_reachable` 就是同一条规则的**第三个住址**
（违反 Global Constraint #3），而且会**掩盖「加载器没校验」这个真故障**——两边都算一遍时，
加载器漏校验永远看不出来。

⚠️ **本函数守不住什么**（硬规矩 #39）：谁绕过加载器手工构造一个 ``reachable=True`` 的
``(green, *, abnormal)`` 模板（``dataclasses.replace`` 就够了，``Template`` 是 frozen
dataclass、构造期不校验），本函数会照常 ``MATCHED`` 出去，**没有任何一条测试会红**。
那一档由加载器与 ``tests/domain/test_prescription_templates.py`` 守。这件事被显式钉成
**期望行为**：:func:`~tests.domain.test_prescription_match.test_a_hand_built_reachable_green_abnormal_template_is_matched`，
免得下一个人以为这里漏了一个判据、顺手把 :func:`is_reachable` 加回来。

--------------------------------------------------------------------------

**``Layer`` 从 :mod:`app.domain.stratify` 绝对导入，不从 ``.templates`` 取**：
``Layer`` 的唯一所有者是 ``app.domain.stratify``（``stratification_result.label`` 那一列、
:data:`app.domain.stratify.RULE_ORDER` 与 Z0 闸门都用它），``.templates`` 里那一份是
**re-export**（它自己的 docstring 逐字写着「**新代码请直接从所有者导入**」）。
``prescription/__init__.py`` 与 ``templates.py`` 今天都写
``from app.domain.stratify import Layer``，本模块与它们一致。

**同包的兄弟模块用 ``level == 1`` 的相对导入**（``from .templates import …``），也与
``templates.py``（``from .exercises import ImpactLevel``）和 ``prescription/__init__.py``
一致：即「跨包指向所有者用绝对串、同包兄弟用相对串」，不一半绝对一半相对。
⚠️ 于是本模块**没有** ``level == 2`` 的相对导入，两份架构守卫矩阵里
``("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")`` 那一格
（Task 1 fix round 5 为 Task 4 埋的）**到本 Task 之后仍是「前瞻」、不是真仓形状**
（Plan02 账本 Ruling 104 记的同一件事，Task 2 与 Task 3 都选了绝对导入）。

--------------------------------------------------------------------------

**``reason`` 的措辞口径**：

* ``NO_LAYER`` 那一支与 Plan 01 的 Z0 文案**逐字同源**（:data:`_NO_LAYER_REASON`）。
* ``NOT_APPROVED`` 那一支必须含「待审校」三个字：spec §11.2 的 B 类算法降级表那一行
  逐字是「模板 ``review.status != approved`` | 拒绝生成，返回「模板待审校」，教师端提示」，
  而 ``reason`` 就是要上教师端的那一句。守卫是
  :func:`~tests.domain.test_prescription_match.test_match_rejects_an_unapproved_template`。
* ``NO_TEMPLATE`` 那一支用**英文 token**（``red`` / ``strength`` / ``normal``）报三个维度：
  仓内**没有**素质桶的中文名口径——:func:`app.domain.stratify.explain` 的 docstring 为此
  专门写了「``dominant_bucket`` 刻意**不渲染**：仓内没有素质桶的中文名口径…把英文 token
  直接给学生看是文案缺陷，而新造一张中文桶名映射属于新增口径、须先改 spec」。本模块
  不新造那张映射（那会是第二个所有者，且要先改 spec）；``Layer`` 的中文词表
  ``stratify._LAYER_WORD`` 是**私有名**，生产码不 import 私有名是本仓既有纪律
  （:func:`app.domain.percentile.national_norm` 的 docstring 逐字写着这一条）。
  故这里的读者是**运维/开发**（「矩阵缺一格」是数据故障，不是给家长看的文案），
  英文 token 足够定位到具体是哪一个 YAML 文件该补。
"""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from app.domain.indicators import WEAKNESS_ITEMS
from app.domain.stratify import MIN_VALID_COUNT, Layer

from .templates import BodyCompState, ReviewStatus, Template

#: ``NO_LAYER`` 的 ``reason``。**它是 :data:`app.domain.stratify._REASON` 里
#: ``RuleId.Z0`` 那一行的副本**（Plan02 账本 P4-A7）：
#:
#: * **唯一所有者**是 ``app/domain/stratify.py`` 的 ``_REASON``（``RuleId.Z0`` →
#:   ``f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"``，可 grep 原文 ``有效项不足``）；
#: * **为什么是副本而不是 import**：``_REASON`` 带前导下划线，而「生产码不 import 私有名」
#:   是本仓 domain 层的既有纪律（:func:`app.domain.percentile.national_norm` 与
#:   :func:`app.domain.percentile.norm_is_derivable` 两处 docstring 都逐字写了这条，
#:   且都为此改用公开 API 自己推一遍）。**测试**可以触私有名（先例是
#:   ``tests/domain/test_percentile.py`` 里那句 ``from app.domain.indicators import
#:   _lower_is_better``，行内注释逐字是「触私有名：本条要比较的正是它」）；
#: * **阈值不复制**：插值用的是 ``stratify`` 公开的 :data:`MIN_VALID_COUNT`，故「4」这个数
#:   仍只有一个住址，改了它两侧一起变；
#: * **漂移时谁会发现**：``tests/domain/test_prescription_match.py`` 的
#:   :func:`~tests.domain.test_prescription_match.test_no_layer_reason_is_verbatim_the_stratify_z0_reason`
#:   （它就地 import ``_REASON`` 与 ``RuleId`` 并逐字比对）。改了 ``stratify`` 那一句的
#:   措辞而忘了改这里，那条测试会红。
_NO_LAYER_REASON = f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"


class MatchStatus(str, Enum):
    """一次匹配的结果档位。**六个成员一个都不能少**（简报 Interfaces / Produces 逐字列举）。

    **继承 ``str``** 的理由与 :class:`~app.domain.prescription.templates.ReviewStatus`
    相同：Task 9 的 ``prescription.status`` 那一列是 ``String``，继承 ``str`` 之后
    ``MatchStatus.NO_LAYER == "no_layer"`` 直接成立，不必在 ORM 边界上处处写 ``.value``。

    ⚠️ **声明序不是优先级序**：``MATCHED`` 排第一是照简报 Produces 那一行的列举序，
    与 :mod:`app.domain.prescription.templates` 里三个枚举「照 spec 书写序声明」同一口径。
    优先级链住在 :func:`match_template` 的 docstring 里、由 32 格穷举测试钉住；
    **不要把本枚举重排成链序**——那会让「声明序 == 简报列举序」这条断言红
    （:func:`~tests.domain.test_prescription_match.test_match_status_has_exactly_the_six_pinned_members`），
    而那是一次需要显式承认的改动。
    """

    MATCHED = "matched"
    NO_LAYER = "no_layer"
    NO_BUCKET = "no_bucket"
    UNREACHABLE = "unreachable"
    NOT_APPROVED = "not_approved"
    NO_TEMPLATE = "no_template"


@dataclass(frozen=True)
class MatchInput:
    """匹配所需的三个维度。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``layer`` 是 :class:`app.domain.stratify.Layer`，**含 ``INSUFFICIENT``**：Z0 闸门拦下的
    学生带着它来匹配，本模块必须认得它并判 ``NO_LAYER``（Review Focus 第 3 条：
    「不得生成处方，且必须留下可交代的痕迹」）。⚠️ 这与模板侧不同——
    :data:`app.domain.prescription.templates.TEMPLATE_LAYERS` **排除** ``INSUFFICIENT``，
    因为没有任何一套模板是写给「没有分层结果」的学生的。

    ``dominant_bucket`` 是 ``str | None`` 而**不是** ``WeaknessBucket | None``：它的来源是
    :attr:`app.domain.derive.WeaknessResult.dominant_bucket`，那一侧的标注就是
    ``str | None``（可 grep 原文 ``dominant_bucket: str | None``）。在本模块再收窄成枚举
    会要求 Task 9 在读回 DB 行时多做一次 ``WeaknessBucket(...)`` 转换，而转换失败
    （``ValueError``）与「桶为空」是两件不同的事。

    ``body_comp_abnormal`` 是 ``bool`` 而**不是** :class:`BodyCompState`：它的来源是
    :attr:`app.domain.derive.BodyCompResult.abnormal`（Plan 01 的 ``C`` 判定结论）。
    ⚠️ ``False`` **包含「数据缺失所以无从判定」**这一整类（Plan 01 的 Ruling 97③，
    ``stratify.py`` 里 ``_REASON`` 上方那段注释逐字讲了它）——即「未判为异常」，
    不是「体成分正常」。
    """

    layer: Layer
    dominant_bucket: str | None
    body_comp_abnormal: bool


@dataclass(frozen=True)
class MatchOutcome:
    """一次匹配的结果。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``template`` 只在 ``status is MATCHED`` 时非 ``None``；非 ``None`` 时它**就是**注入映射里
    那一个对象（不抄副本），守卫是
    :func:`~tests.domain.test_prescription_match.test_matched_outcome_carries_the_injected_template_object_itself`。
    抄副本会让 Task 6 的装配器拿到一个与 :func:`app.refdata_prescription.templates`
    单例**不同一**的对象。

    ``reason`` **六种 status 都非空**（32 格穷举逐格断言）：它是给教师端与日志用的那一句，
    「静默返回 ``None``」正是 Review Focus 第 3 条要防的形状。
    """

    template: Template | None
    status: MatchStatus
    reason: str


def match_template(inp: MatchInput, templates: Mapping[str, Template]) -> MatchOutcome:
    """按 ``(层, 主导短板, 体成分)`` 在注入的模板映射里找一套，找不到就说清为什么。

    **匹配键**是 ``(inp.layer.value, inp.dominant_bucket, "abnormal"/"normal")`` 三元组，
    与每套模板的 ``(layer.value, weakness.value, body_comp.value)`` 逐字比对。
    ⚠️ **不按 ``template_id`` 拼字符串查**：``template_id`` 的形状
    （``<层3>-<桶3>-<体成分3>-<序号2>``）的**唯一所有者**是加载器的 ``_ID_SHAPE``
    （可 grep 原文 ``template_id`` 的形状），在这里再拼一次就是第二个住址
    （Global Constraint #3），而且那个 ``<序号2>`` 在键里根本没有对应物。

    **遍历序是 ``sorted(templates)``**：``templates`` 的键是 ``template_id``，故排序是
    字典序、与字典的插入顺序无关。加载器只校验 ``template_id`` **唯一**、
    **不校验「一格至多一套模板」**（它刻意不做「18 套是否恰好覆盖全矩阵」的策略校验，
    理由见 :func:`app.refdata_prescription.load_templates` 的 docstring），故两个同维度的
    模板在理论上可以共存；那时「取第一个命中者」就会随字典顺序漂。排序之后
    「同一份输入 → 同一个结果」与字典顺序无关，守卫是
    :func:`~tests.domain.test_prescription_match.test_match_is_deterministic_under_dict_ordering`
    （把插入顺序整个反过来，32 格的 :class:`MatchOutcome` 必须逐个相等）。
    Plan 01 的 Ruling 100 为同一件事把 :data:`app.domain.derive._BUCKET_ORDER`
    做成了声明序。

    **优先级链与三处承重顺序**见模块 docstring 的第一节；``reachable`` 读字段而不是调
    :func:`app.domain.prescription.templates.is_reachable` 的理由与本函数守不住什么，
    见第二节。

    纯函数：不读盘、不读时钟、不改注入的映射（``templates`` 只被读；生产路径上它是
    :class:`types.MappingProxyType`，就地改写会当场 ``TypeError``）。
    """
    # ① NO_LAYER：Z0 闸门拦下的学生没有分层标签，谈不上匹配（Review Focus 第 3 条）。
    if inp.layer is Layer.INSUFFICIENT:
        return MatchOutcome(None, MatchStatus.NO_LAYER, _NO_LAYER_REASON)

    # ② NO_BUCKET：主导短板为空是**合法状态**、不是错误（简报 Task 4「决定」第 1 条）。
    #    ⚠️ 按 find_weaknesses 的口径，dominant_bucket is None ⟺ valid_count == 0
    #    （可 grep 原文「一个有效项都没有（全缺测或全无判定线）时为 ``None``」），
    #    而 valid_count == 0 < MIN_VALID_COUNT ⟹ Z0 ⟹ Layer.INSUFFICIENT，
    #    故生产路径上这一支**总是被 ① 先拦下**。它存在的理由是**输入不一致**：
    #    Task 9 的 layer 与 dominant_bucket 可能来自不同时点/不同表的两行
    #    （stratification_result 与 derived_result），那时「有分层标签但没有主导短板」
    #    是一个真实可能的组合，必须报出来而不是 KeyError。
    if inp.dominant_bucket is None:
        return MatchOutcome(
            None,
            MatchStatus.NO_BUCKET,
            f"{len(WEAKNESS_ITEMS)} 个短板判定项全部无效（缺测或无判定线），"
            f"无法确定主导短板",
        )

    body_comp = BodyCompState.ABNORMAL if inp.body_comp_abnormal else BodyCompState.NORMAL
    wanted = (inp.layer.value, inp.dominant_bucket, body_comp.value)

    for template_id in sorted(templates):
        template = templates[template_id]
        if (template.layer.value, template.weakness.value, template.body_comp.value) != wanted:
            continue
        # ④ UNREACHABLE：读**字段**，不调 is_reachable（理由见模块 docstring 第二节）。
        if not template.reachable:
            return MatchOutcome(
                None,
                MatchStatus.UNREACHABLE,
                f"模板 {template.template_id} 是预留位（reachable: false），"
                f"当前不参与匹配",
            )
        # ⑤ NOT_APPROVED：spec §7.2「review.status != approved 的模板拒绝用于生成」，
        #    措辞照 §11.2 那一行的「模板待审校」（教师端原文）。
        if template.review_status is not ReviewStatus.APPROVED:
            return MatchOutcome(
                None,
                MatchStatus.NOT_APPROVED,
                f"模板待审校（{template.template_id} 的 review.status = "
                f"{template.review_status.value}），拒绝生成处方",
            )
        # ⑥ MATCHED
        return MatchOutcome(
            template, MatchStatus.MATCHED, f"匹配到模板 {template.template_id}"
        )

    # ③ NO_TEMPLATE：矩阵里缺这一格。**不是**「这个学生不该有处方」——那是数据故障
    #    （专家少放了一个 YAML 文件），故 reason 必须指出缺哪一格。
    return MatchOutcome(
        None,
        MatchStatus.NO_TEMPLATE,
        f"处方模板矩阵里缺 (层 {inp.layer.value}, 主导短板 {inp.dominant_bucket}, "
        f"体成分 {body_comp.value}) 这一格：那是模板数据缺失，"
        f"不是这个学生不该有处方",
    )
