"""派生指标：趋势四分类、短板与主导桶、体成分异常，以及编排入口 :func:`derive`。

本模块把「国标得分 + 校内百分位 + 体成分 + 历史成绩」压成分层引擎（Task 9）要吃的三个
变量——趋势 :class:`Trend`、短板 :class:`WeaknessResult`、体成分 :class:`BodyCompFlag`。
spec §6.2 的七条分层决策表全部建立在这三个变量上，而趋势还是规则 Y4 的唯一输入。

与 :mod:`app.domain.indicators` / :mod:`app.domain.percentile` 同一条纪律
（Ruling 15 / Ruling 87）：纯计算叶子，不碰数据库、不读盘、不碰时钟、不用随机数。
本模块**不需要评分表**——它吃的是已经正查成 0–100 的国标单项得分，「越大越好／越小越好」
的方向问题在 :mod:`app.domain.indicators` 那一层就已经被抹平了。

两处口径的所有权集中在本模块，别处不得重算：

* :func:`national_total` 是国标加权总分（``Σ w_i·s_i // 100``，0–100）的**唯一所有者**
  （Ruling 63）。**先各自整除、再相减**，不得写成 ``Σ w_i·delta_i / 100``：后者是连续量，
  与前者相差最多 1 分，而 spec §6.3 的 ±5 分阈值作用在整数总分上——``稳定`` 类的可行带
  只有 ``[−4, +4]`` 九个整数，1 分足以让「生成数据时算的 Delta」与「判定时算的 Delta」
  落在阈值两侧（实测 500 人里 443 人两种口径的差值非零，区间 ``[−0.90, +0.95]``）。
  副作用值得记住：``//`` 对较小的 ``Σw·curr`` 向下取整，故整数口径**系统性地更容易判
  持续下滑、更不容易判稳步提升**（Ruling 95）。
* :func:`classify_trend` 是趋势四分类的唯一所有者，求值顺序为
  **波动大 → 持续下滑 → 稳步提升 → 稳定**（Ruling 64a，见该函数 docstring）。
"""
from dataclasses import dataclass
from enum import Enum

from app.domain.indicators import (
    AGE_GROUPS, ITEM_BUCKET, ITEM_WEIGHTS, WEAKNESS_ITEMS, ScoredItem, Sex,
)
from app.domain.percentile import PercentileRow, lookup_p25

# ---------------------------------------------------------------------------
# 阈值常量（spec §6.3 逐条对应）。名字与计划 Interfaces 块逐字一致。
# ---------------------------------------------------------------------------

# 「持续下滑」第一分支：国标总分（0–100 加权口径）的年均变化量 <= −5。
# **不是** 6 项得分之和（0–600）的变化量：在 600 分制上「下降 ≥5 分」是噪声级阈值，
# 会让绝大多数学生被判为持续下滑（Ruling 63）。
TOTAL_DROP_THRESHOLD = 5

# 「持续下滑」第二分支要求的「单项下降 ≥ SINGLE_ITEM_DROP 分」的项数。
DECLINING_ITEMS_THRESHOLD = 3

# 单项「算一次下降」的幅度。与 TOTAL_DROP_THRESHOLD、「稳步提升」的
# IMPROVE_SINGLE_ITEM_DROP_LIMIT 同为 5，三处口径统一（Ruling 64b）。
SINGLE_ITEM_DROP = 5

# 「波动大」的方向分裂判据：min(#{delta>0}, #{delta<0}) >= 3。对 6 个短板判定项而言
# 这等价于**恰好 3 正 3 负**；delta_i == 0 的项两边都不计入，故任一项恰好持平时
# 「波动大」退化为不可达——spec §14 #23 明写这是刻意的保守（宁漏判不误判）。
VOLATILE_MIN_SPLIT = 3

# 「波动大」的幅度判据：max_i |delta_i| >= 10。必须与 VOLATILE_MIN_SPLIT **同时**成立。
VOLATILE_ITEM_SWING = 10

# 「稳步提升」第一半：国标总分的年均变化量 >= +5。
IMPROVE_TOTAL_THRESHOLD = 5

# 「稳步提升」第二半：min_i delta_i > −5，即**无单项下降 ≥5 分**。一项降 6 分就能把
# 稳步提升挡掉（总分仍可能涨 6 分），这是刻意的：单项塌陷不该被总分的净涨幅掩盖。
IMPROVE_SINGLE_ITEM_DROP_LIMIT = 5

# 体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，**严格大于**。
BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}

# 七个国标计分项（含 BMI）。ScoredItem 的声明序即 spec §4.2 权重表的行序。
_SEVEN_ITEMS: tuple[ScoredItem, ...] = tuple(ScoredItem)

# 素质桶的**声明序**，从 ITEM_BUCKET 派生而不是手抄第二份清单：
# endurance → strength → speed_flexibility。两级决胜全部并列时按它取先出现者，
# 故 dominant_bucket 不依赖 dict 的哈希顺序（Ruling 100）。
_BUCKET_ORDER: tuple[str, ...] = tuple(
    dict.fromkeys(bucket for bucket in ITEM_BUCKET.values() if bucket is not None)
)


class Trend(str, Enum):
    """趋势四分类 + 「无历史」。

    枚举值**必须与 Task 6 生成器写进 ``trend_label`` 的中文字面量逐字相同**：
    ``trend_label`` 是仿真数据的真值，``tests/domain/test_derive.py`` 的
    ``test_trend_label_of_generated_data_is_truth`` 把 500 人的生产分类结果与它逐人对账，
    字面量差一个字就对不上。``str`` 混入让 ``Trend.STABLE == "稳定"`` 直接成立，
    落库（``derived_metrics.trend_label``）与前端展示都不必再翻译一次。
    """

    DECLINING = "持续下滑"
    VOLATILE = "波动大"
    IMPROVING = "稳步提升"
    STABLE = "稳定"
    INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class WeaknessResult:
    """短板判定的结果（spec §6.3① / §6.4）。

    ``items`` 按 :data:`~app.domain.indicators.WEAKNESS_ITEMS` 的声明序排列，故同一批输入
    的行序是规范序、不依赖调用方拼装 ``curr`` 的顺序。``count`` 就是决策表里的 ``W``；
    ``valid_count`` 是分母（≤6），``valid_count < 4`` 时 Task 9 不分层、标签置
    ``insufficient_data``（spec §6.2 末行）。

    **刻意不含 ``patterns`` 字段**（Ruling 98）：原计划列了它却从未定义语义、也没有任何
    已规定的消费者。一个未定义语义的字段会被实现者按自己的猜测填满、下游按另一种猜测消费。

    ``count == len(items)`` 是**不变量**，构造时校验（Ruling 175）：两个字段各有自己的
    消费者——``count`` 是决策表读的 ``W``（``stratify._holds_*`` 八条全读它），``items``
    是 ``stratify.explain()`` 渲染学生端文案的那一份。两者不一致时系统内部说「W = 2」、
    学生看到的却是「0 项短板」，而**没有任何一层会报错**。生产唯一的构造点是本模块的
    :func:`find_weaknesses`（恒设 ``count = len(weak)`` / ``items = tuple(weak)``），故这条
    校验在生产路径上恒真；它挡的是手工构造——测试助手、Plan 02 的 API 层、未来的重算脚本
    ——造出一个生产永不产生的状态。

    **刻意只钉 ``count == len(items)``，不钉 ``count <= valid_count``**（Ruling 175）：
    后者是真实的语义约束，但 ``tests/domain/test_stratify.py`` 的
    ``test_insufficient_data_beats_all_rules`` 故意用 ``valid_count = 2`` 配 ``count = 5``
    来隔离「Z0 优先于一切」这一个行为，加上它会逼那条测试重写、而重写会削弱它。
    已转延后 Minor 交终审。
    """

    items: tuple[ScoredItem, ...]
    count: int
    valid_count: int
    dominant_bucket: str | None

    def __post_init__(self) -> None:
        if self.count != len(self.items):
            raise ValueError(
                f"WeaknessResult.count（{self.count}）必须等于 len(items)"
                f"（{len(self.items)}）：决策表读 count 当 W、explain() 读 items 渲染"
                f"学生端文案，两者不一致时系统内部说 W={self.count}、学生看到的却是 "
                f"{len(self.items)} 项短板，而任何一层都不会报错"
            )


@dataclass(frozen=True)
class BodyCompFlag:
    """体成分异常 ``C`` 与它的可解释性素材（spec §6.3②）。

    ``reasons`` 是**稳定的英文 token**、不是展示文案，vocabulary 只有
    ``"body_fat_high"`` 与 ``"muscle_low"`` 两个（顺序固定：先体脂率后肌肉量），
    中文文案由 Task 9 的 ``explain()`` 按 token 渲染（Ruling 7 / Ruling 97①）。
    多一个 token 都要先改 spec §6.3②。

    ``limit`` **一律按性别填**，即使 ``body_fat_pct is None``（Ruling 97②）：``explain()``
    要能渲染「体成分数据缺失，本次不参与判定（男生阈值 20%）」这类文案，缺了 ``limit``
    就渲染不出来。只有 ``sex`` 无法确定阈值时才允许 ``None``——而 ``Sex`` 是必填枚举，
    故实际不会发生。
    """

    abnormal: bool
    reasons: tuple[str, ...]
    body_fat_pct: float | None
    limit: float | None


@dataclass(frozen=True)
class DerivedResult:
    """一个学生在某一天的全部派生指标，即 Task 9 ``stratify()`` 的唯一输入。

    ``annual_change`` 的键值口径见 Ruling 99：键是 6 个短板判定项的 ``.value`` 加
    ``"national_total"`` 共 7 个，值是**年均**变化量 ``(curr − prev) / years``；
    **无历史时是空 dict ``{}``**，不是「7 个键全 0.0」——0.0 是「一年没变化」，
    与「无从比较」是两件不同的事，混在一起会让可解释性文案说出「各项年均变化 0 分」
    这种假话。``national_total`` 是调用方传入的 ``curr_total``（本模块不重算），
    供 spec §6.1 空洞一所定的**同层内排序**使用；缺项时为 ``None``。
    """

    sex: Sex
    trend: Trend
    weakness: WeaknessResult
    body_comp: BodyCompFlag
    annual_change: dict[str, float]
    national_total: int | None


def national_total(scores: dict[ScoredItem, int | None]) -> int | None:
    """国标加权总分（0–100）= ``Σ ITEM_WEIGHTS[i] × scores[i] // 100``。

    **加权口径的唯一所有者**（Ruling 63）：Task 10 的总分入库、所有测试的期望值、
    以及趋势判定的 ``Delta`` 一律调用本函数，不得各自手写加权求和。权重来自
    :data:`~app.domain.indicators.ITEM_WEIGHTS`（全仓唯一的一张权重表，和恰为 100，
    故七项全满分时正好 100）。

    **7 个计分项任一为 ``None`` 时返回 ``None``**，且「键根本不存在」与「键存在但值为
    ``None``」**同等对待**——不做权重重归一。理由：缺项的总分与全项的总分**不可比**，
    重归一会造出一个看起来合法、实则口径不同的数，而它正是同层内排序的键；
    ``None`` 让「这个学生排不了序」这件事显式可见。

    **``//`` 而不是 ``/``**（Ruling 71 / 76）：见模块 docstring。返回 ``None`` 而非抛异常
    是因为「某项缺测」是真实数据里的常态（Review Focus #2），不是程序缺陷。
    """
    values = [scores.get(item) for item in _SEVEN_ITEMS]
    if any(value is None for value in values):
        return None
    return sum(ITEM_WEIGHTS[item] * value for item, value in zip(_SEVEN_ITEMS, values)) // 100


def classify_trend(
    prev: dict[ScoredItem, int] | None,
    curr: dict[ScoredItem, int],
    prev_total: int | None,
    curr_total: int | None,
    years: float,
) -> Trend:
    """spec §6.3③ 的历史趋势判定表：自上而下匹配、**命中即停**。

    | 顺序 | 标签 | 判定 |
    |---|---|---|
    | 1 | ``波动大``   | ``min(#{d>0}, #{d<0}) >= 3`` **且** ``max|d_i| >= 10`` |
    | 2 | ``持续下滑`` | ``Delta <= -5`` **或** ``#{i: d_i <= -5} >= 3`` |
    | 3 | ``稳步提升`` | ``Delta >= +5`` **且** ``min_i d_i > -5`` |
    | 4 | ``稳定``     | 以上皆不满足 |

    **行序是承重的（Ruling 64a）**。原 spec 把「持续下滑」印在第一行，那样「波动大」
    **可证明不可达**：6 项里 ``min(#{d>0}, #{d<0}) >= 3`` 等价于恰好 3 正 3 负，而这必然
    满足原「持续下滑」的第二分支「≥3 项为负变化」，于是每个波动大的学生都先被持续下滑
    吃掉。语义上也应当如此：``波动大`` 描述**形状**（方向混杂 + 大幅摆动），
    ``持续下滑`` / ``稳步提升`` 描述**净方向**；形状必须先于净方向判定，因为一个大幅摆动的
    学生几乎必然同时满足某个粗糙的净方向判据，而把他标成「持续下滑」恰好掩盖了干预上最
    需要区分的特征（波动型与持续下滑型的处方与预警策略不同）。

    **第二分支是「≥3 项单项下降 >= ``SINGLE_ITEM_DROP`` 分」，不是「≥3 项为负变化」
    （Ruling 64b）**：原措辞下 ``稳定`` 类几乎无法存在——一个总分不变的学生只要六项里
    出现 3 个 −1 分的正常抖动就会被判持续下滑。收紧后 ``稳定`` 才是「以上皆不满足」的
    自然残差类。

    口径（spec §6.3「口径先钉死」）：

    * ``Delta`` = ``(curr_total − prev_total) / years``，即**年均**变化量，阈值作用在这个量上。
      两个总分是 0–100 的国标加权口径、由调用方用 :func:`national_total` 算好传入，
      本函数自己不做加权——它只比较两个总分。
    * 「项」= 6 个短板判定项（:data:`~app.domain.indicators.WEAKNESS_ITEMS`，天然排除 BMI）。
      BMI 的变化只通过 ``Delta`` 影响判定，不参与「≥3 项」的计数（spec §4.2）。
    * ``delta_i = 本学年得分 − 上学年得分``，**正 = 进步**（Ruling 62 的符号约定）。
    * ``prev`` 为 ``None`` = 无历史体测（如新生），直接 ``INSUFFICIENT``，且**不触发 Y4**
      （spec §6.3 表末行）。``prev_total`` / ``curr_total`` 任一为 ``None``（总分不可得，
      例如七项里有缺测）时同样无从比较，一并归 ``INSUFFICIENT``：那是「不知道」，
      不是「稳定」，判成 ``STABLE`` 会让规则 Y4 对该生静默失效。

    纯函数：不碰数据库、不读盘、不碰时钟，``years`` 由调用方注入。

    **``years`` 必须 > 0**（Ruling 118-M2）：负值会**静默反转**趋势与 :func:`derive` 的
    全部 ``annual_change`` 符号——实测总分 70→80 的进步在 ``years=-1.0`` 下被判成
    ``持续下滑``、``annual_change["national_total"] = -10.0``；``years=0`` 是
    ``ZeroDivisionError``（响亮，可接受）。``years`` 由 Task 10 用「两个学年／两个测量
    日期相减」得到，减法方向写反就是 ``-1``——与 Ruling 62 的 C1（生成器把趋势符号接反、
    两类标签整体互换、活过两轮 236 条测试）是同一缺陷形态的**第二个入口**。故本函数与
    :func:`derive` 入口**两处**都 fail-fast：本函数是公开 API，Task 9/10 可能绕过
    ``derive`` 直接调它。校验放在 ``prev is None`` 的早退**之前**——``years`` 合不合法与
    有没有历史无关，非法输入一律先报。
    """
    if not years > 0:
        raise ValueError(
            f"years={years!r} 必须 > 0（两次体测之间的学年差，相邻两学年为 1.0）："
            f"负值会静默反转趋势与 annual_change 的全部符号，0 会 ZeroDivisionError"
        )
    if prev is None or prev_total is None or curr_total is None:
        return Trend.INSUFFICIENT
    deltas = [curr[item] - prev[item] for item in WEAKNESS_ITEMS]
    total_change = (curr_total - prev_total) / years
    ups = sum(1 for delta in deltas if delta > 0)
    downs = sum(1 for delta in deltas if delta < 0)
    # 1 波动大：方向分裂 **且** 幅度够大，两个条件缺一不可
    if (
        min(ups, downs) >= VOLATILE_MIN_SPLIT
        and max(abs(delta) for delta in deltas) >= VOLATILE_ITEM_SWING
    ):
        return Trend.VOLATILE
    # 2 持续下滑：总分净降够多，**或** 塌陷的单项够多（与总分无关，Delta = 0 也能触发）
    if total_change <= -TOTAL_DROP_THRESHOLD or sum(
        1 for delta in deltas if delta <= -SINGLE_ITEM_DROP
    ) >= DECLINING_ITEMS_THRESHOLD:
        return Trend.DECLINING
    # 3 稳步提升：总分净升够多 **且** 没有单项塌陷
    if total_change >= IMPROVE_TOTAL_THRESHOLD and min(deltas) > -IMPROVE_SINGLE_ITEM_DROP_LIMIT:
        return Trend.IMPROVING
    # 4 稳定：残差类
    return Trend.STABLE


def find_weaknesses(
    curr: dict[ScoredItem, int | None],
    snapshot: list[PercentileRow],
    sex: Sex,
    age_group: str,
) -> WeaknessResult:
    """spec §6.3① 的短板判定 ``W`` 与 §6.4 的主导短板桶。

    只遍历 :data:`~app.domain.indicators.WEAKNESS_ITEMS`（6 项，**天然排除 BMI**）：
    BMI 属身体形态、已由体成分维度 ``C`` 覆盖，同时计入 ``W`` 与 ``C`` 会让一个体脂超标
    学生被**重复计数**，导致 R1（``W>=2 AND C``）被系统性过度触发（spec §4.2）。
    故 ``curr`` 可以含 7 项（带 BMI）也可以只含 6 项，多余的键**忽略**（与 Ruling 88 对
    ``compute_snapshot`` 的处置同构）。

    **两种「不算」必须区分开，但后果相同**：

    * 得分为 ``None``（该项缺测）→ 既不算短板、**也不进 ``valid_count``**。
      **绝不当 0 分**（Review Focus #2 / Ruling 21）：0 分低于任何 P25，会把一个没测的
      项目变成一条短板，反过来若当成「不短板」又会让 ``valid_count`` 虚高——两个方向都
      让体能最差的学生被系统性地移出红色干预层。
    * ``lookup_p25`` 返回 ``None``（该 (项, 性别, 年级组) 组没有快照行 = 没有判定线）→
      同样既不算短板、也不进 ``valid_count``。与「判定线是 0 分」是两件不同的事。

    ``valid_count`` 因此可能 < 6，Task 9 依赖这一点触发 ``valid_count < 4`` 的不分层闸门。

    **P25 的比较符钉死为严格小于（``score < p25``）**，依据 spec §6.3 原文「低于 P25 的
    项目视为显性短板」。这一条在 Ruling 18（就低取档）之后**承重**：每项得分只有 ≤20 个
    离散取值（男引体向上仅 15 个），P25 处的并列质量显著上升——若某组有 30% 学生同为
    60 分且 P25 = 60，``<`` 只把低于 60 分者判为短板，``<=`` 会把这 30% 全判为短板，
    实质改变 ``W``、改变红黄绿比例、甚至改变 ``valid_count >= 4`` 闸门的通过情况
    （spec §14 #21；改用 ``<=`` 属需求变更）。注意 ``p25`` **可能是半分**（如 ``57.5``），
    不得假定它是官方档位分。

    ``dominant_bucket``（spec §6.4）：

    * ``W > 0``：短板数最多的桶；并列时取**该桶内最低单项得分**更低者；仍并列按
      :data:`_BUCKET_ORDER` 声明序取先出现者。
    * ``W == 0``：取**相对最弱桶**（即使全达标也有相对强弱），口径为**桶内有效项得分
      均值最低者**（均值只对非 ``None`` 的项算，Ruling 100）；并列时用与 ``W > 0`` 相同的
      决胜规则——桶内最低单项得分更低者；仍并列按声明序取先出现者。两级全并列时唯一答案
      是 ``endurance``，不依赖 dict 哈希顺序。
    * 一个有效项都没有（全缺测或全无判定线）时为 ``None``——此时 ``valid_count = 0``，
      Task 9 会直接判 ``insufficient_data``，不会去读这个字段。

    纯函数：``snapshot`` 由调用方注入（Task 7 的 ``compute_snapshot`` 产物或从库里读回的行）。
    """
    weak: list[ScoredItem] = []
    valid: dict[str, list[int]] = {}
    counts: dict[str, int] = {}
    lowest_weak: dict[str, int] = {}
    for item in WEAKNESS_ITEMS:
        score = curr.get(item)
        line = lookup_p25(snapshot, item, sex, age_group)
        if score is None or line is None:
            continue
        bucket = ITEM_BUCKET[item]
        valid.setdefault(bucket, []).append(score)
        if score < line:
            weak.append(item)
            counts[bucket] = counts.get(bucket, 0) + 1
            if bucket not in lowest_weak or score < lowest_weak[bucket]:
                lowest_weak[bucket] = score

    if weak:
        top = max(counts.values())
        tied = [bucket for bucket in _BUCKET_ORDER if counts.get(bucket, 0) == top]
        floor = min(lowest_weak[bucket] for bucket in tied)
        dominant = next(bucket for bucket in tied if lowest_weak[bucket] == floor)
    else:
        tied = [bucket for bucket in _BUCKET_ORDER if bucket in valid]
        if not tied:
            dominant = None
        else:
            means = {b: sum(valid[b]) / len(valid[b]) for b in tied}
            lowest_mean = min(means.values())
            tied = [b for b in tied if means[b] == lowest_mean]
            lows = {b: min(valid[b]) for b in tied}
            lowest_score = min(lows.values())
            dominant = next(b for b in tied if lows[b] == lowest_score)

    return WeaknessResult(
        items=tuple(weak),
        count=len(weak),
        valid_count=sum(len(scores) for scores in valid.values()),
        dominant_bucket=dominant,
    )


def flag_body_comp(
    body_fat_pct: float | None,
    muscle_mass_kg: float | None,
    sex: Sex,
    snapshot_muscle_p20: float | None,
) -> BodyCompFlag:
    """spec §6.3② 的体成分异常 ``C`` = ``(体脂率 > 男 20% / 女 28%) OR (肌肉量 < 同龄同性别 P20)``。

    两个比较都是**严格**的：体脂率恰等于阈值（男 20.0 / 女 28.0）不算异常，肌肉量恰等于
    P20 不算异常。骨骼肌指数（SMI）**入库但第一批不参与判定**（spec §14 #16），故本函数
    的签名里根本没有它——这一点由 ``test_smi_is_not_an_input_at_all`` 用
    ``inspect.signature`` 钉住签名本身。

    ``snapshot_muscle_p20`` 由**调用方**从百分位快照里查好再传入（P20 那一档，不是短板
    判定用的 P25）：本模块不读快照、也不需要 ``age_group``。传 ``None`` 表示该组没有
    肌肉量的判定线，此时肌肉量那一支无从成立。

    **两个输入都缺时 ``abnormal = False``（Ruling 97③）**，与 spec §6.3② 的布尔式一致
    （``None > 20.0`` 与 ``None < P20`` 都无从成立）。**后果必须写明**：一个 ``W >= 2``
    但没有 InBody 数据的学生会因 ``C = False`` 落到规则 **Y3（黄）** 而不是 **R1（红）**，
    即**缺数据会导致干预不足**。这是「缺测不当最坏值」原则（Ruling 21）在体成分一侧的
    代价，与短板一侧「缺项不计入 ``W``」的代价同向。**不改成三值**
    （``abnormal: bool | None``）：spec §6.2 的决策表是纯布尔的，改成三值会波及 Task 9
    的整张表——代价不成比例，故如实记录而非改设计。

    ``limit`` 一律按性别填（即使 ``body_fat_pct is None``），``reasons`` 是固定顺序的英文
    token，两者都是 Task 9 ``explain()`` 渲染 spec §9.2 文案的素材，见
    :class:`BodyCompFlag`。
    """
    limit = BODY_FAT_LIMIT.get(sex)
    reasons: list[str] = []
    if body_fat_pct is not None and limit is not None and body_fat_pct > limit:
        reasons.append("body_fat_high")
    if (
        muscle_mass_kg is not None
        and snapshot_muscle_p20 is not None
        and muscle_mass_kg < snapshot_muscle_p20
    ):
        reasons.append("muscle_low")
    return BodyCompFlag(
        abnormal=bool(reasons),
        reasons=tuple(reasons),
        body_fat_pct=body_fat_pct,
        limit=limit,
    )


def _require_seven_keys(name: str, scores: dict) -> None:
    """校验 ``scores`` 含全部 7 个计分项的**键**（Ruling 101），缺键 ``KeyError`` 响亮失败。

    不查就会静默出错：:func:`national_total` 把「键不存在」与「值为 ``None``」同等对待，
    一律返回 ``None``。若调用方只传 6 项（漏了 BMI），``DerivedResult.national_total``
    会在**整个数据集**上恒为 ``None``，于是同层内排序（spec §6.1 空洞一）失效且不报错——
    正是本项目最怕的缺陷形态。
    """
    missing = [item.value for item in _SEVEN_ITEMS if item not in scores]
    if missing:
        raise KeyError(
            f"{name} 必须含全部 7 个计分项的键（含 bmi），实际缺少 {missing}；"
            f"缺键会让 national_total 静默返回 None，同层内排序在整个数据集上失效"
        )


def derive(
    curr_scores: dict[ScoredItem, int | None],
    prev_scores: dict[ScoredItem, int] | None,
    curr_total: int | None,
    prev_total: int | None,
    years: float,
    body_fat_pct: float | None,
    muscle_mass_kg: float | None,
    sex: Sex,
    age_group: str,
    snapshot: list[PercentileRow],
    snapshot_muscle_p20: float | None,
) -> DerivedResult:
    """编排入口：依次调用 :func:`classify_trend`、:func:`find_weaknesses`、:func:`flag_body_comp`。

    **``curr_scores`` / ``prev_scores`` 必须含全部 7 个计分项的键（含 BMI）**（Ruling 101，
    缺键 ``KeyError``，理由见 :func:`_require_seven_keys`）。:func:`find_weaknesses` 只读
    其中 6 项，但 ``DerivedResult.national_total`` 要 7 项才有意义。

    **``curr_total`` / ``prev_total`` 由调用方用 :func:`national_total` 算好传入**，本函数
    **两侧都校验**、判据**对称**（Ruling 101 / 104 / 106），且校验分**两层**：先查
    **None-ness**（下面两条），再查**值**（Ruling 118-M1）——``curr_total`` 必须
    ``== national_total(curr_scores)``，``prev_scores`` 非 ``None`` 时 ``prev_total`` 必须
    ``== national_total(prev_scores)``，不等则 ``ValueError`` 且消息里报出两个值。
    值校验调的是**唯一所有者** :func:`national_total`，**不是第二处加权**，故旧措辞
    「本函数不重算，避免同一套加权出现在两处」不成立（复审 M1 指出）：只查 None-ness 时，
    调用方若手写 ``round(Σ/100)``、漏一项权重、或对缺项做重归一，算错的总分会**静默通过**
    并原样进入 ``DerivedResult.national_total``（spec §6.1 空洞一的同层内排序键）与
    ``Delta``（规则 Y4 的唯一输入）。实测（改前）：``curr_total=99``（真值 80）放行、
    ``prev_total=55``（真值 70）让 ``annual_change["national_total"]`` 从 ``+10.0`` 变成
    ``+25.0``。成本是每人 7 次乘法。

    **这两个参数在值校验落地后语义上冗余**（本函数自己就能算出来），本轮**刻意保留**：
    让调用方显式声明它用的是哪一套口径，并让不一致**当场暴露**，而不是被静默重算掩盖。
    删参数属签名变更、会波及 Task 10 的调用方式，已记为延后 Minor 交终审评估。

    None-ness 一层的判据（Ruling 101 / 104 / 106）：

    * ``curr`` 侧：``curr_total is not None`` 与「7 项**值**都非 ``None``」必须**同真同假**，
      不一致说明调用方算错了口径（例如自己手写了一个忽略缺项的加权求和）。
    * ``prev`` 侧：``prev_total is not None`` 与「``prev_scores`` 7 项**值**都非 ``None``」
      必须**同真同假**（Ruling 106；原判据写的是「``prev_scores is None`` ↔
      ``prev_total is None``」，见下）。它真正要堵的是两件事：七项值全非 ``None``
      （总分可得）却 ``prev_total is None`` ——那会**静默伪装成「无历史」**
      （:func:`classify_trend` 归 ``INSUFFICIENT``、``annual_change`` 归 ``{}``、全程不报错）；
      以及反方向 ``prev_scores is None`` 却给了一个总分（Ruling 108）。

      **原判据为什么错**：它把「有历史、但某项缺测」这个**合法**状态也判成了不一致。
      :func:`national_total` 对含 ``None`` 值的七项正确返回 ``None``，于是每个历史缺测的
      学生都在本函数入口炸掉，而 :func:`classify_trend` docstring 明写的「总分任一为
      ``None``（例如七项里有缺测）→ ``INSUFFICIENT``」分支变成**永不可达**；Task 6 的
      缺测注入率是 4%，即整批 500 人回放会在约 4% 的合法状态上崩溃。

      **键缺失与值缺测必须继续分开**：缺键 → :func:`_require_seven_keys` 先抛
      ``KeyError``（它跑在一致性校验之前）；值为 ``None`` → 缺测、合法，放行到
      ``INSUFFICIENT`` + ``annual_change = {}``。

    两侧不一致一律 ``ValueError`` 响亮失败，不静默产出一个 ``national_total=None``
    或「假无历史」的结果。

    ``age_group`` 是**必需参数**（Ruling 103）：``snapshot`` **可以是整张多组快照**
    （生产上 24 行 = 2 性别 × 2 年级组 × 6 项），:func:`find_weaknesses` 经
    :func:`lookup_p25` 按 ``(item, sex, age_group)`` **三元过滤**自行挑出该生的判定线，
    调用方不需要预筛、本函数也不从快照里反推年级组。``age_group`` **必须**取
    :data:`~app.domain.indicators.AGE_GROUPS` 里的年级组名（``"大一、大二"`` /
    ``"大三、大四"``），由 Task 10 用 ``age_group_of(学生年龄)`` 给出；否则 ``ValueError``
    （Ruling 107）。它是 11 个参数里**唯一的自由字符串**，传 ``"18-19"`` 这类年龄段字面量时
    :func:`lookup_p25` 一行都匹配不上 → ``valid_count = 0 < 4`` → 整批学生**静默**走进
    Task 9 的不分层闸门，与 Ruling 103 批评的空串哨兵是同一缺陷形态（差别只在责任方，
    不在后果）。合法清单从 :mod:`app.domain.indicators` 导入，不另立第二份口径。

    ``years`` 是两次体测之间的学年差（相邻两学年为 ``1.0``），趋势阈值与 ``annual_change``
    都作用在**年均**量上。**必须 > 0**（Ruling 118-M2），否则 ``ValueError``：负值会静默
    反转趋势与全部 ``annual_change`` 的符号（实测证据与理由见 :func:`classify_trend`）。
    本入口在 ``age_group`` 之后立刻校验它——两个自由量都是 fail-fast，:func:`classify_trend`
    里还有同一道校验，因为它是公开 API、可能被直接调用。

    ``annual_change`` 为 ``{}`` 的两种情形（Ruling 99）：``prev_scores is None``（无历史），
    或总分不可比（``curr_total`` / ``prev_total`` 任一为 ``None``，通常是七项里有缺测）。
    两种都是「无从比较」而不是「变化为 0」，故一律用空 dict 表示、**不填 0.0**，也**不填
    部分键**——半张表会让 Task 9 的文案在缺项上说不出话或说出假话。可比时恰好 7 个键。

    纯函数：不碰数据库、不读盘、不碰时钟（Task 1 的三个 AST 守卫会扫本模块）。
    """
    if age_group not in AGE_GROUPS:
        raise ValueError(
            f"age_group={age_group!r} 不是合法的年级组名，合法清单是 {list(AGE_GROUPS)}"
            f"（app.domain.indicators.AGE_GROUPS，全仓唯一口径）；非法组名会让 lookup_p25 "
            f"一行都匹配不上 → valid_count=0 < 4，整批学生静默走进 Task 9 的不分层闸门"
        )
    # Ruling 118-M2：years 是本函数另一个自由量，负值静默反转趋势与全部 annual_change 的
    # 符号（classify_trend 的 docstring 有实测证据），故与 age_group 一样在入口 fail-fast。
    if not years > 0:
        raise ValueError(
            f"years={years!r} 必须 > 0（两次体测之间的学年差，相邻两学年为 1.0）："
            f"负值会静默反转趋势与 annual_change 的全部符号"
            f"（实测 years=-1 让总分 70→80 的进步被判成持续下滑、年均变化 −10.0），"
            f"0 会 ZeroDivisionError"
        )
    _require_seven_keys("curr_scores", curr_scores)
    if prev_scores is not None:
        _require_seven_keys("prev_scores", prev_scores)
    # Ruling 106：与下面的 curr 侧**对称**——校验「total 非 None」↔「七项**值**都非 None」，
    # 而不是「prev_scores is None」↔「prev_total is None」。后者会把「有历史但某项缺测」
    # 这个**合法**状态判成不一致（后果见 docstring）。键缺失已由上面两行 _require_seven_keys
    # 先抛 KeyError，故这里能安全地按值判缺测。
    prev_complete = prev_scores is not None and all(
        prev_scores[item] is not None for item in _SEVEN_ITEMS
    )
    if (prev_total is not None) is not prev_complete:
        if prev_scores is None:
            prev_side = "prev_scores 为 None（无历史）"
        else:
            prev_absent = [item.value for item in _SEVEN_ITEMS if prev_scores[item] is None]
            prev_side = (
                "prev_scores 七项值全部非 None（总分可得）"
                if not prev_absent
                else f"prev_scores 七项里有 {len(prev_absent)} 项值为 None"
                     f"（缺测 {prev_absent}，总分不可得）"
            )
        raise ValueError(
            f"prev_total 与 prev_scores 的口径不一致：prev_total={prev_total!r}，而 {prev_side}；"
            f"prev_total 必须由调用方用 national_total(prev_scores) 算出，"
            f"「prev_total 非 None」与「prev_scores 七项值都非 None」必须同真同假。"
            f"有历史却漏算总分会让「有历史」静默伪装成「无历史」"
            f"（classify_trend 归 INSUFFICIENT、annual_change 归 {{}}），全程不报错；"
            f"无历史或有缺测却给出总分，则是凭空造出一个不可比的差值基准"
        )
    # Ruling 118-M1（值校验，prev 侧）：上面的 None-ness 校验只查「有没有」，不查「对不对」。
    # 走到这里 prev_total 非 None ⇒ 七项值全非 None ⇒ national_total(prev_scores) 必非 None，
    # 故两者可直接比较。调的是唯一所有者 national_total，不是第二处加权。
    if prev_scores is not None and prev_total is not None:
        expected_prev = national_total(prev_scores)
        if prev_total != expected_prev:
            raise ValueError(
                f"prev_total={prev_total!r} 与 national_total(prev_scores)={expected_prev!r} "
                f"不相等：prev_total 必须由调用方用 national_total(prev_scores) 算出，"
                f"不得自行手写加权求和（round(Σ/100)、漏一项权重、对缺项重归一都会被这里拦下）；"
                f"算错的基准会同时污染趋势 Delta 与全部 annual_change，且全程不报错"
            )
    curr_complete = all(curr_scores[item] is not None for item in _SEVEN_ITEMS)
    if (curr_total is not None) is not curr_complete:
        curr_absent = [item.value for item in _SEVEN_ITEMS if curr_scores[item] is None]
        curr_side = (
            "curr_scores 七项值全部非 None（总分可得）"
            if not curr_absent
            else f"curr_scores 七项里有 {len(curr_absent)} 项值为 None"
                 f"（缺测 {curr_absent}，总分不可得）"
        )
        raise ValueError(
            f"curr_total 与 curr_scores 的口径不一致：curr_total={curr_total!r}，而 {curr_side}；"
            f"curr_total 必须由调用方用 national_total(curr_scores) 算出，"
            f"「curr_total 非 None」与「curr_scores 七项值都非 None」必须同真同假"
        )
    # Ruling 118-M1（值校验，curr 侧）：与 prev 侧同一条判据。curr_total 非 None ⇒ 七项值
    # 全非 None ⇒ national_total(curr_scores) 必非 None。
    if curr_total is not None:
        expected_curr = national_total(curr_scores)
        if curr_total != expected_curr:
            raise ValueError(
                f"curr_total={curr_total!r} 与 national_total(curr_scores)={expected_curr!r} "
                f"不相等：curr_total 必须由调用方用 national_total(curr_scores) 算出，"
                f"不得自行手写加权求和（round(Σ/100)、漏一项权重、对缺项重归一都会被这里拦下）；"
                f"它原样进入 DerivedResult.national_total（spec §6.1 空洞一的同层内排序键）"
                f"与 classify_trend 的 Delta（规则 Y4 的唯一输入），算错会两处同时错且不报错"
            )

    six_curr = {item: curr_scores[item] for item in WEAKNESS_ITEMS}
    six_prev = (
        None if prev_scores is None
        else {item: prev_scores[item] for item in WEAKNESS_ITEMS}
    )
    trend = classify_trend(six_prev, six_curr, prev_total, curr_total, years)
    weakness = find_weaknesses(curr_scores, snapshot, sex, age_group)
    body_comp = flag_body_comp(body_fat_pct, muscle_mass_kg, sex, snapshot_muscle_p20)

    annual_change: dict[str, float] = {}
    # `prev_total is not None` 这个合取项在 Ruling 106 之后**承重**（在 Ruling 104 的字面
    # 判据下它冗余）：prev_scores 非 None 现在只意味着「有历史」，不再意味着「七项值都非
    # None」——某项值为 None 的缺测是合法状态。删掉它，一个 BMI 值为 None 的历史会在下面
    # 的减法上抛 TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'。
    if prev_scores is not None and curr_total is not None and prev_total is not None:
        # 两侧 total 均非 None ⇒ 两侧七项值全部非 None（上面的对称一致性校验），
        # 故这里的差值都有定义
        annual_change = {
            item.value: (curr_scores[item] - prev_scores[item]) / years
            for item in WEAKNESS_ITEMS
        }
        annual_change["national_total"] = (curr_total - prev_total) / years

    return DerivedResult(
        sex=sex,
        trend=trend,
        weakness=weakness,
        body_comp=body_comp,
        annual_change=annual_change,
        national_total=curr_total,
    )
