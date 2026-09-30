"""红黄绿分层引擎：spec §6.2 的八行决策表，以及学生端可解释性文案 :func:`explain`。

本模块是计划 01 的算法终点——Task 2 的国标得分、Task 7 的校内百分位、Task 8 的
:class:`~app.domain.derive.DerivedResult` 在这里变成学生看到的那一个标签。它只吃
``DerivedResult``，只吐 :class:`StratResult`，与 :mod:`app.domain.derive` 同一条纪律
（Ruling 15 / Ruling 87）：纯计算叶子，不碰数据库、不读盘、不碰时钟、不用随机数，
也不 import :mod:`app.refdata`（分层不需要评分表——方向问题在得分那一层就抹平了）。

两条承重的口径决定：

* **``Z0`` 是决策表的第一行，不是最后一行**（Ruling 115 / 125）。``valid_count < 4``
  若印在末行，则在「自上而下、命中即停」语义下它对 ``W = 0 ∧ ¬C`` 的学生**不可达**
  （先命中 ``G1`` 变绿）——而 ``valid_count`` 低恰恰由缺测造成、缺测又把 ``W`` 压低到 0，
  于是**最该被拦的人正好是必然被 ``G1`` 提前吃掉的人**。spec §11.1 的原则是「宁可不出
  结果，也不要出一个错的结果给学生看」，数据不足必须在任何分层判定之前拦截。
  ``Z0`` 是闸门而非分层规则，故不占用 R/Y/G 的编号空间。
* **``hit_rules`` 是「本次求值评估过的规则序列」，最后一项即命中者**，不是「所有命中的
  规则」——命中即停意味着最多只可能命中一条。保留已评估但未命中的前缀不是冗余：它正是
  回答「这个学生为什么不是红色层」的证据（spec §4.3 的可追溯性），也是
  :func:`explain` 选择文案的依据。任何路径都**至少有一项**：``Z0`` 命中时是
  ``(RuleId.Z0,)`` 而**不是空元组**（Ruling 125），空元组会让 ``hit_rules[-1]`` 当场
  ``IndexError``，而 ``Z0`` 恰恰是最需要向学生解释「为什么没有分层结果」的那条路径。
  ``Z0`` 之外的学生，其序列从 ``R1`` 起——闸门未触发时它不算「已评估的分层规则」。

:attr:`StratResult.reason` 与 :func:`explain` 是两个东西、不得互为副本（Ruling 129）：
``reason`` 是**由 ``RuleId`` 单射得出的一行规范中文名**、不含任何学生数据（供日志、API
与大屏列表使用），判据是它必须能只从 ``RuleId`` 算出来（:data:`_REASON` 那 8 行映射表）；
:func:`explain` 是**含具体数值的学生端长文案**，并且直接复用 ``result.reason`` 作为开头，
故规则名只有 :data:`_REASON` 一个所有者。
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.domain.derive import DerivedResult, Trend
from app.domain.indicators import ITEM_DISPLAY_NAMES, WEAKNESS_ITEMS, Sex


class Layer(str, Enum):
    """分层标签。值与 ORM ``StratificationResult.LABELS`` 的四个取值逐字相同。

    ``str`` 混入让 ``Layer.RED == "red"`` 直接成立，落库与前端展示都不必再翻译一次
    （与 Task 8 的 :class:`~app.domain.derive.Trend` 同一处置）。
    """

    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    INSUFFICIENT = "insufficient_data"


class RuleId(str, Enum):
    """决策表的八行行号。``Z0`` 是数据不足闸门（Ruling 125），其余七条是分层规则。"""

    Z0 = "Z0"
    R1 = "R1"
    R2 = "R2"
    Y1 = "Y1"
    Y2 = "Y2"
    Y3 = "Y3"
    Y4 = "Y4"
    G1 = "G1"


# 优先级顺序（spec §6.2 的行序，已按 Ruling 115 把 Z0 提到第一行）。
# **这个元组是承重的**：:func:`stratify` 逐行按它求值、命中即停，故换序就换语义
# （``Z0`` 移到末行会让它不可达，``R1``/``R2`` 互换会让 ``hit_rules[0]`` 变 ``R2``）。
RULE_ORDER: tuple[RuleId, ...] = (
    RuleId.Z0,
    RuleId.R1,
    RuleId.R2,
    RuleId.Y1,
    RuleId.Y2,
    RuleId.Y3,
    RuleId.Y4,
    RuleId.G1,
)

# 数据不足闸门（spec §6.3①、§11.1、§14 #13）：6 个短板判定项里有效项 < 4 → 本日不分层。
# 「有效」= 该项有得分**且**该 (项, 性别, 年级组) 组有 P25 判定线；两种「不算」都会同时
# 压低 ``W`` 与 ``valid_count``（见 :func:`app.domain.derive.find_weaknesses`）。
MIN_VALID_COUNT = 4

# R2 的无条件升红线（spec §6.1 空洞三的补齐：``W >= 4`` 时短板过多本身即高风险信号）。
# 分母是 6，故它实为「6 项里 4 项及以上为短板」（spec §14 #4）。
W_RED_UNCONDITIONAL = 4

# R1 / Y3 的 ``W >= 2``：spec §6.2 原文的字面值，两处共用，故只写一次。
_W_AT_LEAST_TWO = 2


def _holds_z0(derived: DerivedResult) -> bool:
    return derived.weakness.valid_count < MIN_VALID_COUNT


def _holds_r1(derived: DerivedResult) -> bool:
    return derived.weakness.count >= _W_AT_LEAST_TWO and derived.body_comp.abnormal


def _holds_r2(derived: DerivedResult) -> bool:
    return derived.weakness.count >= W_RED_UNCONDITIONAL


def _holds_y1(derived: DerivedResult) -> bool:
    return derived.weakness.count == 1


def _holds_y2(derived: DerivedResult) -> bool:
    return derived.weakness.count == 0 and derived.body_comp.abnormal


def _holds_y3(derived: DerivedResult) -> bool:
    return derived.weakness.count >= _W_AT_LEAST_TWO and not derived.body_comp.abnormal


def _holds_y4(derived: DerivedResult) -> bool:
    # 趋势只作升级项、永不降级（spec §6.1 空洞二）：判据是 **``is Trend.DECLINING``**，
    # 不是「非稳步提升就升级」——放宽成后者会把 `波动大` 与 `稳定` 也一并升黄，
    # 而 spec §6.3 的判定表把这两类与 `持续下滑` 明确区分开（形状 vs 净方向）。
    return (
        derived.weakness.count == 0
        and not derived.body_comp.abnormal
        and derived.trend is Trend.DECLINING
    )


def _holds_g1(derived: DerivedResult) -> bool:
    return derived.weakness.count == 0 and not derived.body_comp.abnormal


# 八行的条件。键与 :data:`RULE_ORDER` 一一对应，:func:`stratify` 按序取用。
# 表是**完备的**：``valid_count >= 4`` 时，``W >= 2 ∧ C`` → R1、``W >= 4`` → R2、
# ``W ∈ {2,3} ∧ ¬C`` → Y3、``W = 1`` → Y1、``W = 0 ∧ C`` → Y2、
# ``W = 0 ∧ ¬C`` → Y4 或 G1，无残差。
_HOLDS: dict[RuleId, Callable[[DerivedResult], bool]] = {
    RuleId.Z0: _holds_z0,
    RuleId.R1: _holds_r1,
    RuleId.R2: _holds_r2,
    RuleId.Y1: _holds_y1,
    RuleId.Y2: _holds_y2,
    RuleId.Y3: _holds_y3,
    RuleId.Y4: _holds_y4,
    RuleId.G1: _holds_g1,
}

# 每行的标签与干预强度（spec §6.2 的第 3、4 列）。
_LAYER_OF: dict[RuleId, Layer] = {
    RuleId.Z0: Layer.INSUFFICIENT,
    RuleId.R1: Layer.RED,
    RuleId.R2: Layer.RED,
    RuleId.Y1: Layer.YELLOW,
    RuleId.Y2: Layer.YELLOW,
    RuleId.Y3: Layer.YELLOW,
    RuleId.Y4: Layer.YELLOW,
    RuleId.G1: Layer.GREEN,
}

# ``reason`` 的 8 行映射表：**只依赖 ``RuleId``**，不读 ``derived``（Ruling 129 的判据）。
# 阈值数字用 :data:`MIN_VALID_COUNT` / :data:`W_RED_UNCONDITIONAL` 插值，避免出现第二个
# 所有者——改了常量而忘了改文案，文案就会撒谎。
#
# **Y3 / G1 写「体成分未判为异常」而不是「体成分正常」**（Ruling 134）：spec §6.2 的字面是
# ``NOT C``，而 ``C = False`` 在 Ruling 97③ 下**包含「数据缺失所以无从判定」这一整类**
# （实测 ``flag_body_comp(None, 40.0, MALE, 33.20)`` + ``W=2`` 走的就是 Y3）。同一例的
# ``explain()`` 会正确说「体成分数据缺失，本次不参与判定」，而 ``reason`` 是**短文案**、
# 进日志与教师大屏列表——正是有人会据此行动的地方。短文案比长文案更自信地说「正常」，
# 是危险的：它把「没测」讲成了「测了且没问题」。
_REASON: dict[RuleId, str] = {
    RuleId.Z0: f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层",
    RuleId.R1: "短板 ≥2 项且体成分异常",
    RuleId.R2: f"短板 ≥{W_RED_UNCONDITIONAL} 项，无条件升红",
    RuleId.Y1: "短板 1 项",
    RuleId.Y2: "无短板但体成分异常",
    RuleId.Y3: "短板 ≥2 项且体成分未判为异常",
    RuleId.Y4: "无短板但趋势持续下滑（趋势只升级、永不降级）",
    RuleId.G1: "无短板且体成分未判为异常",
}

_SEX_WORD: dict[Sex, str] = {Sex.MALE: "男", Sex.FEMALE: "女"}

_LAYER_WORD: dict[Layer, str] = {
    Layer.RED: "红色",
    Layer.YELLOW: "黄色",
    Layer.GREEN: "绿色",
    Layer.INSUFFICIENT: "数据不足",
}


@dataclass(frozen=True)
class StratResult:
    """一个学生在某一天的分层结果（ORM ``stratification_result`` 的三列业务值）。

    ``hit_rules`` 的语义见模块 docstring：**已评估序列**，最后一项即命中者。落库时由
    Task 10 逗号连接成字符串（``"R1,R2,Y1"``），``models.py`` 那一列的注释与此逐字对应。

    ``reason`` 是由 ``label`` 之外的那一条命中规则单射得出的一行规范中文名，**不含学生
    数据**（Ruling 129），故可以直接入库、进日志、上大屏列表；含数值的学生端长文案是
    :func:`explain` 的职责。
    """

    label: Layer
    hit_rules: tuple[RuleId, ...]
    reason: str


def stratify(derived: DerivedResult) -> StratResult:
    """spec §6.2 的决策表：按 :data:`RULE_ORDER` 自上而下求值，**命中即停**。

    纯函数，只读 ``derived`` 的四个字段：``weakness.valid_count``（Z0）、
    ``weakness.count`` 即 ``W``、``body_comp.abnormal`` 即 ``C``、``trend``（Y4）。
    它**不重算** ``W`` / ``C`` / 趋势——那三个口径的所有者是 :mod:`app.domain.derive`
    （Ruling 63 / 97 / 100），本函数只消费。

    决策表完备（见 :data:`_HOLDS` 的注释），故循环必然返回；末尾那句 ``RuntimeError``
    只在有人改坏了 ``RULE_ORDER`` 或某个条件（例如删掉残差行 ``G1``）时才会走到——
    那时静默返回 ``None`` 会让下游在 ``result.label`` 上炸出一个看不出所以然的
    ``AttributeError``，而响亮失败指出的正是真因。
    """
    evaluated: list[RuleId] = []
    for rule in RULE_ORDER:
        if _HOLDS[rule](derived):
            return StratResult(
                label=_LAYER_OF[rule],
                hit_rules=(*evaluated, rule),
                reason=_REASON[rule],
            )
        # Z0 是**闸门**而不是分层规则（Ruling 125：不占用 R/Y/G 的编号空间），故未触发时
        # 不进前缀：否则每个学生的 hit_rules 都以 "Z0," 开头，而计划 Step 1 的
        # test_R1_takes_priority_over_R2 钉的是 `hit_rules[0] == RuleId.R1`。
        # 注意求值**顺序**仍由 RULE_ORDER 决定，Z0 排第一位这件事是承重的（见模块
        # docstring）：把它移到末行会让 W=0 ∧ ¬C 的缺测学生先命中 G1 变绿。
        if rule is not RuleId.Z0:
            evaluated.append(rule)
    raise RuntimeError(
        f"spec §6.2 的决策表未能给该学生定层：已评估 {[r.value for r in evaluated]} "
        f"而无一命中（W={derived.weakness.count}, C={derived.body_comp.abnormal}, "
        f"valid_count={derived.weakness.valid_count}, trend={derived.trend.value}）。"
        f"决策表本应完备，走到这里说明 RULE_ORDER 或某个条件被改坏了"
        f"（残差行 G1 是否还在？）"
    )


def _weakness_text(derived: DerivedResult, sex_word: str) -> str:
    """短板那一条证据：项目中文名 + 「低于校内同龄同性别 P25」这个**固定短语**。

    项目名经 :data:`~app.domain.indicators.ITEM_DISPLAY_NAMES` 按性别渲染（Ruling 127：
    男「1000 米跑」/ 女「800 米跑」，男「引体向上」/ 女「1 分钟仰卧起坐」）。

    **P25 只写短语、不写数值**（Ruling 126）：``DerivedResult`` 不携带 P25 的值
    （``WeaknessResult`` 只有 ``items`` / ``count`` / ``valid_count`` / ``dominant_bucket``），
    而 spec §9.2:641 的示例文案本身也只写「低于 P25」。要展示具体百分位数值就得给
    ``WeaknessResult`` 加字段，那是先改 spec §9.2 的变更，不在这里偷偷做。

    ``items`` 为空而 ``count > 0`` 是**合法输入**（调用方可以只给计数），此时退化为
    只报项数——绝不可渲染成「你的 在校内同龄男生中低于 P25」这种缺主语的句子。
    """
    weakness = derived.weakness
    names = "、".join(
        ITEM_DISPLAY_NAMES[item][derived.sex] for item in weakness.items
    )
    if names:
        return (
            f"你的 {names} 在校内同龄{sex_word}生中低于 P25"
            f"（{weakness.valid_count} 个有效项里 {weakness.count} 项短板）"
        )
    if weakness.count:
        return (
            f"有 {weakness.count} 项在校内同龄{sex_word}生中低于 P25"
            f"（共 {weakness.valid_count} 个有效项）"
        )
    return f"{weakness.valid_count} 个有效项均未低于校内同龄{sex_word}生 P25"


def _body_comp_text(derived: DerivedResult, sex_word: str) -> str:
    """体成分那一条证据：体脂率数值与该性别阈值，或**缺测文案**。

    ``body_fat_pct is None`` 时渲染成「体成分数据缺失，本次不参与判定（男生阈值 20%）」
    这类文案，**绝不渲染成 ``None%``**（Ruling 126）；``limit`` 一律非 ``None``
    （Ruling 97②）正是为此，故可以直接格式化。

    ``muscle_low`` 那一支**没有数值可渲染**：``BodyCompFlag`` 不携带肌肉量读数
    （只有 ``abnormal`` / ``reasons`` / ``body_fat_pct`` / ``limit``），故只写
    「肌肉量低于同龄同性别 P20」这个短语——同 Ruling 126 对 P25 的处置。
    """
    flag = derived.body_comp
    over = f"超过{sex_word}生 {flag.limit:g}% 阈值"
    under = f"未超过{sex_word}生 {flag.limit:g}% 阈值"
    fat_high = "body_fat_high" in flag.reasons
    muscle_low = "muscle_low" in flag.reasons
    if fat_high:
        text = f"体脂率 {flag.body_fat_pct:g}% {over}"
        if muscle_low:
            text += "，且肌肉量低于同龄同性别 P20"
        return text
    if muscle_low:
        detail = "体脂率缺测" if flag.body_fat_pct is None else f"体脂率 {flag.body_fat_pct:g}% {under}"
        return f"肌肉量低于同龄同性别 P20（{detail}，{sex_word}生阈值 {flag.limit:g}%）"
    if flag.body_fat_pct is None:
        return f"体成分数据缺失，本次不参与判定（{sex_word}生阈值 {flag.limit:g}%）"
    return f"体脂率 {flag.body_fat_pct:g}% {under}"


def _trend_text(derived: DerivedResult) -> str:
    """趋势那一条证据：``trend`` 与 ``annual_change``。

    ``annual_change == {}`` 表示**无从比较**（无历史体测，或七项里有缺测使国标总分不可比），
    **不是「各项变化 0 分」**（Ruling 99 / Task 8 前向约束 ③），故文案明确写「无从比较」，
    绝不渲染成 ``+0.0 分`` 这种看起来像测量结果的假话。
    """
    label = (
        "无可比历史"
        if derived.trend is Trend.INSUFFICIENT
        else f"「{derived.trend.value}」"
    )
    if not derived.annual_change:
        return (
            f"历史趋势{label}，年均变化无从比较"
            f"（无历史体测，或计分项里有缺测使国标总分不可比）"
        )
    total = derived.annual_change["national_total"]
    return f"历史趋势{label}，国标总分年均变化 {total:+.1f} 分"


def explain(result: StratResult, derived: DerivedResult) -> str:
    """学生端可解释性文案（spec §9.2「分层可解释性展开」）。

    形态是 ``「{颜色}层 ← {规则名}（规则 {行号}）。依据：{短板}；{体成分}；{趋势}。」``，
    与 spec §9.2:641 的示例「红色层 ← 你的 1000 米跑与引体向上在校内同龄男生中低于 P25，
    且体脂率 22.4% 超过男生 20% 阈值」同构。文案按 ``result.hit_rules[-1]``（即命中者）
    选择——这也是 ``hit_rules`` 任何路径都不得为空元组的原因（Ruling 125）。

    **它能引用的证据只有 ``DerivedResult`` 实际携带的字段**（Ruling 126），四条来源逐条
    写死在三个私有渲染函数里：短板项目名（``weakness.items`` + ``ITEM_DISPLAY_NAMES``）、
    「低于校内同龄同性别 P25」固定短语、体脂率与该性别阈值（``body_comp``）、趋势与年均
    变化（``trend`` / ``annual_change``）。``dominant_bucket`` 刻意**不渲染**：仓内没有
    素质桶的中文名口径（``ITEM_BUCKET`` 的值是 ``endurance`` 这类英文 token），把英文
    token 直接给学生看是文案缺陷，而新造一张中文桶名映射属于新增口径、须先改 spec。

    开头那一句规则名直接复用 ``result.reason``（Ruling 129）：``reason`` 是规则名的唯一
    所有者，本函数不重述它、只补学生数据。

    ``Z0`` 路径单独成句：它没有颜色可报，要说的是「为什么没有分层结果」以及下一步
    （进异常名单、补测后重算），这正是 spec §11.1「宁可不出结果，也不要出一个错的结果
    给学生看」在学生端的落点。
    """
    rule = result.hit_rules[-1]
    sex_word = _SEX_WORD[derived.sex]
    if rule is RuleId.Z0:
        return (
            f"数据不足 ← {result.reason}：{len(WEAKNESS_ITEMS)} 个短板判定项里只有 "
            f"{derived.weakness.valid_count} 项有效，本日不给出红黄绿标签，"
            f"已列入异常名单，补测后重算。"
        )
    return (
        f"{_LAYER_WORD[result.label]}层 ← {result.reason}（规则 {rule.value}）。依据："
        f"{_weakness_text(derived, sex_word)}；"
        f"{_body_comp_text(derived, sex_word)}；"
        f"{_trend_text(derived)}。"
    )
