"""潜变量模型与体测记录生成（spec §10.2）。

**为什么是潜变量驱动而不是逐项独立随机**
六个短板判定项若各自独立抽分，耐力与力量得分的相关系数会落在 0 附近，而真实人群里
它们由同一个「体能水平」牵引、显著正相关（本模块在缺省配置下实测约 0.51）。差别不是
美观问题：分层引擎按能力桶聚合短板、处方引擎按主导桶给运动处方，独立随机的数据会让
「短板集中在某个桶」这件事几乎不发生，于是整个系统的核心路径在演示数据上根本走不到。
所以先抽一个共同因子 ``latent_fitness``，再让它按不同载荷派生出耐力 / 力量 / 速度柔韧
三个桶的潜变量，得分由桶潜变量生成（简报 Step 3 的公式逐字实现）。

**得分 → 原始值走国标表的正反查，再做两处「不改档位」的后处理**
``raw_from_score`` 是就低取档的方向感知反查（Ruling 22），返回的是**档位端点**；
``score_item`` 再把原始值正查回得分（Ruling 18）。两者对每一个官方档精确往返，所以
记录里带的 ``score_*`` 与原始值天然自洽，``tests/seed`` 里有一条测试专门钉这一点。
端点值直接落盘会让每一个读数都恰好是国标表的阈值（Ruling 54），故反查之后还有两步：
:func:`jitter_raw` 在**同一档内**按该列的测量分辨率抖开，:func:`sub_floor_marks` 标记
出的那批学生则生成**低于表内最低档**的次数。两者都不破坏上面那条自洽性：前者按构造
不跨档，后者由 ``score_item`` 的低侧夹取（Ruling 17）拿底档分。
**得分一侧不做任何舍入或插值**：次数项（引体向上 / 仰卧起坐）的档边界本身就是整数，
反查结果一定是可测量的读数——**任何一处 ``round()`` 都可能把 13.5 顶成 14 从而跨过
档位**。:func:`jitter_raw` 里那个 ``int(round(threshold * scale))`` 舍入的是「阈值换算
到整数单位」（精确换算，不是近似），与得分无关。

**BMI 是唯一不走反查的项**：它的档位序列非单调（两头 80、中间 100），
``raw_from_score`` 对它直接抛 ``ValueError``。做法是按身高与体重的分布生成原始值，
算出 BMI 后用 ``score_item`` **正查**得分。

**本模块自己不 open 任何文件**：需要国标评分表时只经 :func:`app.refdata.standard`
这个受管加载器取（进程内单例、只读、由 ``MappingProxyType`` 封住就地改写）。
``app.seed`` 里真正碰磁盘的是 :func:`app.seed.generate.write_csv`（写三个 CSV）与
:func:`app.seed.generate._ranges`（经 ``load_ranges`` 读 ``indicator_ranges.yaml``）。
"""
import math
from dataclasses import dataclass

import numpy as np

from app.adapters import base
from app.domain.indicators import (
    ITEM_BUCKET,
    ITEM_WEIGHTS,
    WEAKNESS_ITEMS,
    ScoredItem,
    Sex,
    age_group_of,
    raw_from_score,
    score_item,
    segment_thresholds,
)
from app.refdata import standard
from app.seed.config import (
    SEMESTERS,
    TIMEPOINT_SEQUENCE,
    SeedConfig,
    allocate_quota,
    timepoint_date,
)
from app.seed.population import HEIGHT_RANGE, WEIGHT_RANGE

# ---------------------------------------------------------------------------
# 得分模型（简报 Step 3 的公式）
# ---------------------------------------------------------------------------

# 6 个短板判定项的得分 = clip(70 + 15·latent_所属桶 + N(0, 5), 0, 100)
BASE_SCORE_MEAN = 70.0
BASE_SCORE_SLOPE = 15.0
BASE_SCORE_NOISE_SD = 5.0

# latent_fitness 的载荷与残差**标准差**（记作 sd，不写 ``N(0, 0.6)``——统计学惯例里
# 那个位置是方差，含糊记法会让照计划改代码的人把 sd 当成方差，见评审 Minor m4）：
#   endurance = 0.8·fitness + ε，ε ~ 正态(均值 0, sd 0.6)
#   strength  = 0.7·fitness + ε，ε ~ 正态(均值 0, sd 0.7)
#   speedflex = 0.6·fitness + ε，ε ~ 正态(均值 0, sd 0.8)
# 计划 Step 3 把残差写作 ``N(0, 0.6)`` 这种形状，这里按**标准差**读（不是方差）：按方差读
# 会让耐力/力量的理论相关系数从 0.57 掉到 0.46，叠上逐项噪声与国标档位离散化之后已经贴近
# 「相关系数 > 0.4」那条断言的边界，而按标准差读留出的是 0.51 左右的实测余量。
LATENT_LOADINGS: dict[str, tuple[float, float]] = {
    "endurance": (0.8, 0.6),   # (载荷, 残差 sd)
    "strength": (0.7, 0.7),
    "speedflex": (0.6, 0.8),
}

# app.domain.indicators.ITEM_BUCKET 用的桶名是 "speed_flexibility"，而简报把潜变量的
# 键名钉成 "speedflex"。两套名字都不是错的（一个是国标能力桶、一个是潜变量），
# 故在此显式对照一次，而不是把其中一处悄悄改成另一处。
LATENT_BY_BUCKET: dict[str, str] = {
    "endurance": "endurance",
    "strength": "strength",
    "speed_flexibility": "speedflex",
}

def _items_by_latent() -> dict[str, tuple[ScoredItem, ...]]:
    """潜变量名 → 该桶下的计分项。

    从 :data:`app.domain.indicators.ITEM_BUCKET` 反推，不手抄第二份清单：将来国标口径
    调整（比如某项换桶），这里自动跟着走，而手抄的那份不会报错、只会静默算错桶均值。

    桶内的项序取自 ``ITEM_BUCKET`` 的声明序（dict 保序），故桶均值的求和顺序是固定的
    ——浮点加法不满足结合律，顺序一变结果的最后一位就可能变，「同种子字节级一致」
    随之失效。
    """
    grouped: dict[str, list[ScoredItem]] = {}
    for item, bucket in ITEM_BUCKET.items():
        if bucket is None:  # BMI 不归桶，也不进短板判定
            continue
        grouped.setdefault(LATENT_BY_BUCKET[bucket], []).append(item)
    return {name: tuple(items) for name, items in grouped.items()}


ITEMS_BY_LATENT: dict[str, tuple[ScoredItem, ...]] = _items_by_latent()

# 计分项 → 体测 CSV 的原始值列名。这张映射**无法从名字推导**（``pull_up_or_sit_up``
# 对应的是 ``strength_count``），只能显式写出；写错的后果是 write_csv 按契约列序取值时
# KeyError，当场炸开，不会静默产出一个缺列的文件。
COLUMN_BY_ITEM: dict[ScoredItem, str] = {
    ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
    ScoredItem.SPRINT_50M: "sprint_50m_s",
    ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
    ScoredItem.STANDING_JUMP: "standing_jump_cm",
    ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
    ScoredItem.DISTANCE_RUN: "distance_run_s",
}

# 每个计分项的**测量分辨率**（小数位数）。这是仪器口径与上报口径的知识，不是可调旋钮，
# 所以是模块级常量而不是 ``SeedConfig`` 字段：把它开成配置就等于允许「配出一份评分表
# 根本没有的测量精度」，而 spec §12 要求系统能与学校官方报表逐格对账。
#
# 改动它会**整体平移随机流**（抖动区间的整数单位变了，抽数次数随之变），因而改变同一
# seed 的全部输出——这是配置变更的预期后果，不是缺陷，但必须重做可复现性取证。
MEASURE_DECIMALS: dict[ScoredItem, int] = {
    ScoredItem.VITAL_CAPACITY: 0,      # 肺活量计读到 1 ml
    ScoredItem.SPRINT_50M: 1,          # 计时读到 0.1 s
    ScoredItem.SIT_AND_REACH: 1,       # 游标读到 0.1 cm
    ScoredItem.STANDING_JUMP: 0,       # 跳垫/尺读到 1 cm
    ScoredItem.PULL_UP_OR_SIT_UP: 0,   # 次数是整数
    ScoredItem.DISTANCE_RUN: 1,        # 计时读到 0.1 s
}

# ---------------------------------------------------------------------------
# 国标加权总分（Ruling 63）
# ---------------------------------------------------------------------------


def _weighted_total(scores: dict[ScoredItem, int]) -> int:
    """国标加权总分（0–100）= ``Σ ITEM_WEIGHTS[i] × scores[i] // 100``。

    **Task 8 会提供生产版 ``national_total``，届时本函数应删除并改用它**（Ruling 63：
    加权求和只能有一个所有者）。本轮需要它，只是因为趋势必须在**加权总分空间**上定标
    （spec §10.5），而 Task 8 还没落地。它是私有的、不出现在 ``app.seed`` 的公开面上，
    故不构成第二个所有者；权重一律读 :data:`app.domain.indicators.ITEM_WEIGHTS`。

    与 ``national_total`` 的唯一差别是 ``None`` 处理：生成器的得分列永不为 ``None``
    （缺测是 :func:`app.seed.generate.inject_dirty` 在**落盘前**才注入的），故这里不做
    缺项判定。``// 100`` 是**向下取整**，与 Task 8 逐字一致——趋势判据作用在
    ``curr_total − prev_total`` 上，两侧取整口径差一点，±5 分线就会在个别人身上翻面。
    """
    return sum(ITEM_WEIGHTS[item] * score for item, score in scores.items()) // 100


# ---------------------------------------------------------------------------
# 两学年趋势与学年内漂移（spec §6.3 / §10.5，计划 Task 6 Step 4）
# ---------------------------------------------------------------------------

# spec §6.3 判定表用到的阈值。名字与 Task 8 `derive.py` 的常量**逐字同名**（Ruling 63/64），
# 两侧由 Ruling 69 的两条对账测试钉在一起：生成侧的验收判据写错，
# tests/seed/test_trend_oracle.py 里那个从规格正文独立翻译的 oracle 会当场红。
TOTAL_DROP_THRESHOLD = 5            # Delta <= -5 → 持续下滑（第一分支）
DECLINING_ITEMS_THRESHOLD = 3       # ≥3 项 delta_i <= -5 → 持续下滑（第二分支，Ruling 64b）
SINGLE_ITEM_DROP = 5                # 上面那个「≥3 项」里每一项的下降幅度
IMPROVE_TOTAL_THRESHOLD = 5         # Delta >= +5 → 稳步提升
IMPROVE_SINGLE_ITEM_DROP_LIMIT = 5  # 稳步提升额外要求 min delta_i > -5
VOLATILE_MIN_SPLIT = 3              # 正负两方各 ≥3 项（对 6 项即恰好 3 正 3 负）
VOLATILE_ITEM_SWING = 10            # 且 max|delta_i| >= 10

# 「落档 → 重算 → 校正」循环（计划 Step 4 第 4 步，承重）：一轮把 prev_target 推一个官方档。
# 国标 60 分以下的档距是 10 分，故步长取 10；每轮至少让 Delta' 朝目标移动
# w_max × 10 / 100 = 2 分，循环因此单调且有界。上限 8 轮，超限 RuntimeError 响亮失败——
# 静默放行一个「标签与数据不符」的学生，正是上一轮 236 条测试全绿却方向反了的成因。
CORRECTION_STEP = 10
CORRECTION_MAX_ROUNDS = 8
# 可行域筛选给校正预留的余量（分）。筛得太松会让校正循环把 prev_target 推出 [0, 100]
# 之后再也推不动，最终 RuntimeError；简报 §6.1 第 1 条授权「把筛选判据收紧再试」。
CORRECTION_RESERVE = float(CORRECTION_STEP)

# 配额分配顺序（计划 Step 4）：最受限的先挑，「稳定」拿余下全部。
FEASIBILITY_ORDER: tuple[str, ...] = ("波动大", "持续下滑", "稳步提升", "稳定")

# 六项在 WEAKNESS_ITEMS 里的声明序下标：所有排序的决胜键。用它而不用项名比较，
# 是为了让「同种子字节级一致」不依赖字符串比较的任何实现细节。
_ITEM_INDEX: dict[ScoredItem, int] = {item: index for index, item in enumerate(WEAKNESS_ITEMS)}

# 两个学年在 SEMESTERS 里的下标。按 ``is_current`` 推而不是写死 0/1：生成顺序（上学年在前）
# 是 config.py 的约定，趋势模型要拿「上学年 week1 的 BMI 得分」去扣贡献，写死下标会在
# 有人调换 SEMESTERS 顺序时静默算出反号的 delta_bmi。
_PREVIOUS_INDEX = next(index for index, plan in enumerate(SEMESTERS) if not plan.is_current)
_CURRENT_INDEX = next(index for index, plan in enumerate(SEMESTERS) if plan.is_current)


@dataclass(frozen=True)
class TrendProfile:
    """一类趋势标签的量化定义（口径见 spec §6.3，取值见计划 Task 6 Step 4 的表格）。

    **符号约定（Ruling 62，承重）**：``delta_i = 本学年得分_i − 上学年得分_i``，
    **正 = 进步**；上学年目标分 = 本学年目标分 − ``delta_i``。上一轮把字段定义成
    「偏移为正表示上学年更好」（即 ``-delta_i``）却在注入处用减号，两处符号相消之后
    「持续下滑」与「稳步提升」整体互换（评审 C1）。本轮字段直接就叫 ``delta_target``，
    与规格同名同向，不留第二个可以接反的地方。

    * ``delta_target_range``：**国标加权总分变化** ``Delta_target`` 的抽样区间
      （0–100 口径，Ruling 63）。不是 6 项之和（0–600）——在 600 分制上「±5 分」是噪声级
      阈值，会把绝大多数学生判成持续下滑（评审实测 46%）。
    * ``jitter``：叠在均匀分配上的逐项整数抖动的最大幅值。六项之和恒为零，故它不改变
      ``Delta``，只让六项不严格同步（真实数据里不存在六项完全同步变化的学生）。
      上一轮用的是 ``N(0, sd)`` 那种正态抖动，它既不带界也无零和约束，评审 Minor m4
      点名的「方差还是标准差」含糊记法随本轮重写一并消除。
    * ``swing``：只有「波动大」用——逐项**幅值**的抽样区间，符号由构造强制成 3 正 3 负。
    * ``drift_scale``：放大学年内三个时点之间的随机漂移。
    """

    delta_target_range: tuple[float, float]
    jitter: float
    drift_scale: float
    swing: tuple[float, float] | None = None


TREND_PROFILES: dict[str, TrendProfile] = {
    # Delta_target = -U(6, 18)：总分下降 6–18 分，远超 -5 的判据线，留足落档量化的余量
    "持续下滑": TrendProfile(delta_target_range=(-18.0, -6.0), jitter=3.0, drift_scale=1.0),
    # 不设 Delta 目标：判据是**形状**（恰好 3 正 3 负 + max|delta| >= 10），不是净方向
    "波动大": TrendProfile(
        delta_target_range=(0.0, 0.0), jitter=0.0, drift_scale=2.5, swing=(10.0, 16.0)
    ),
    "稳步提升": TrendProfile(delta_target_range=(6.0, 18.0), jitter=3.0, drift_scale=1.0),
    # U(-2, +2)：判据是 (-5, +5) 的**窄带**，比落档量化损失（六项加权最多约 7.65 分）
    # 还窄，故它靠「先扣 BMI 贡献 + 落档后精确重算 + 校正」算准，不靠留余量
    "稳定": TrendProfile(delta_target_range=(-2.0, 2.0), jitter=2.0, drift_scale=0.6),
}

# 一个采集间隔（week1→week8、week8→week16）的平均得分增益与其标准差。均值取小正数：
# 一学期体育课下来体能略有进步，但幅度必须远小于学年间的趋势项，否则趋势会被学期内
# 的自然增长冲淡，Task 8 的趋势判定就分不出四类人。
INTERVAL_GAIN_MEAN = 0.8
INTERVAL_GAIN_SD = 1.5

# 每条体测记录相对该生基准值的测量噪声（同一台仪器、同一个人在不同批次上的读数差）
HEIGHT_NOISE_SD = 0.3
WEIGHT_NOISE_SD = 0.9
# 上学年相对本学年的体重基线差：一年前的读数整体略低一点，量级远小于噪声。
# **它是体重的年度漂移，不是得分偏移**，故 Ruling 62/63 重写趋势模型时保留不动。
PREVIOUS_YEAR_WEIGHT_SHIFT = -1.2


def latent_profiles(
    population: list[dict], cfg: SeedConfig, rng: np.random.Generator
) -> dict[int, dict[str, float]]:
    """生成每名学生的潜变量，返回 ``{student_id: {"fitness", "endurance", "strength", "speedflex"}}``。

    四个键的形状是简报钉住的接口，故不塞入第五个键（比如身高体重）——需要那些值的地方
    从 ``population`` 记录里取，潜变量字典保持「一个学生的能力画像」这一个含义。

    随机数消耗顺序是 fitness → 三个桶的残差，且四组都是**整批**抽取而不是逐人抽取：
    逐人抽会让随机序列与遍历顺序耦合，将来一旦改成按院系分组生成，同一种子就再也复现
    不出同一批人。
    """
    total = len(population)
    fitness = rng.normal(cfg.latent_mean, cfg.latent_sd, total)
    residuals = {
        name: rng.normal(0.0, sd, total) for name, (_, sd) in LATENT_LOADINGS.items()
    }
    profiles: dict[int, dict[str, float]] = {}
    for index, person in enumerate(population):
        profile = {"fitness": float(fitness[index])}
        for name, (loading, _) in LATENT_LOADINGS.items():
            profile[name] = float(
                loading * fitness[index] + residuals[name][index]
            )
        profiles[person["student_id"]] = profile
    return profiles


def _raw_and_score(
    table, item: ScoredItem, target: float, sex: Sex, age_group: str, memo: dict
) -> tuple[float, int]:
    """目标分 → ``(原始值, 正查回读的得分)``，带**调用内**记忆化。

    记忆化键把连续目标分先 ``math.floor``：国标档位分全是整数（``refdata.load_standard``
    用 ``int()`` 解析 CSV 的 ``score`` 列），所以「不超过 target 的最大官方档」与
    「不超过 floor(target) 的最大官方档」必然是同一档，``raw_from_score`` 的就低语义
    分毫未变；顺带也满足了它 ``score: int`` 的参数标注。取整之后键空间从「每条记录一个」
    收缩到「6 项 × 2 性别 × 2 龄组 × 约 90 个整数分」，500 人 × 两学年 × 三时点
    = 18000 次反查因此变成两千余次表扫描。

    ``memo`` 是**每次调用新建的局部字典**，不做模块级缓存：``StandardTable`` 里装的是
    ``MappingProxyType``，不可哈希，没法当键的一部分，而模块级缓存会在有人拿另一张表
    （测试里的迷你 CSV）调用时静默返回上一张表的结果——分数看着都合法，只是来自另一套
    档位。``score_item`` 与 ``raw_from_score`` 都是纯函数（Ruling 15：不碰磁盘、不碰
    时钟），所以缓存它们的返回值与重新计算完全等价。
    """
    key = (item.value, sex.value, age_group, math.floor(target))
    cached = memo.get(key)
    if cached is not None:
        return cached
    raw = raw_from_score(table, item, key[3], sex, age_group)
    realised = score_item(table, item, raw, sex, age_group)
    result = (float(raw), int(realised))
    memo[key] = result
    return result


def _band_is_lower_better(table, item: ScoredItem, sex: Sex, age_group: str) -> bool:
    """该项是否「越小越好」——按**阈值升序 + ``score_item`` 回读**判方向。

    ``app.domain.indicators`` 里有同名判据，但它是私有的（``_lower_is_better``），
    跨模块 import 私有名字等于把它变成事实上的公开 API 而没有任何一处测试守着它。
    这里只用公开 API：阈值升序时，末档得分低于首档得分就意味着沿原始值增大方向得分
    单调不增，即越小越好。六个短板判定项的档位序列都是单调的，故首末两点足以定方向
    （BMI 非单调，但它既不走反查也不参与抖动）。
    """
    thresholds = segment_thresholds(table, item, sex, age_group)
    return score_item(table, item, thresholds[-1], sex, age_group) < score_item(
        table, item, thresholds[0], sex, age_group
    )


def jitter_raw(
    table,
    item: ScoredItem,
    raw: float,
    sex: Sex,
    age_group: str,
    rng: np.random.Generator,
) -> float:
    """把档位端点抖到**同一档内**「更好」一侧的某个可测量读数上（Ruling 54(a)）。

    ``raw_from_score`` 按 Ruling 22 返回「仍能取得该分的最差原始值」，即档位端点。
    直接采用会让数据里每一个读数都恰好是国标表的阈值——「所有肺活量都是 120 的整数倍」
    一眼就是造的。本函数在档带内向更好的一侧均匀取值：

    * 越大越好：``[raw_s, raw_next)``，``raw_next`` 是严格大于 ``raw_s`` 的最小阈值；
    * 越小越好：``(raw_prev, raw_s]``，``raw_prev`` 是严格小于 ``raw_s`` 的最大阈值；
    * 端点档（最好档没有更好的一侧）无抖动空间，原样返回。

    **一律在整数单位上做**（``scale = 10 ** MEASURE_DECIMALS[item]``）：浮点下
    ``2.01 * 100 == 200.99999999999997``，取整会得到 200 而不是 201——正是 Ruling 49
    踩过的那个残渣。整数单位把阈值换算成精确整数，抖动区间因此是闭区间上的均匀整数，
    **从构造上保证不会跨档**，也就不需要「抽完再回验、失败重试」这类会掩盖真缺陷的
    兜底逻辑；逐档回验放在 ``tests/seed/test_fitness.py`` 里做。

    **次数类项目（引体向上/仰卧起坐）自动被这套逻辑覆盖**：``d = 0``、``scale = 1``，
    整数单位就是次数本身，故 Ruling 54 原文那句「次数类向下取整再回验」在此是多余的
    ——不是漏了，是不需要。

    **无抖动空间时不消耗随机数**（``lo >= hi`` 直接返回端点）。这一条是承重的：男生
    引体向上的 14 个档距**处处等于**它的分辨率 1 次，整数单位区间恒为空 → 恒返回端点。
    真实上报数据也必然全是整数次、且表内每个整数次都是阈值，所以「全落在端点上」在这一项
    与真实数据**不可区分**（Ruling 57 的结论在这一处成立）。50 米跑只有最高 4 档
    （100/95/90/85）是这种情形：其余 15 档的档距是 0.2 s（女生另有两档 0.3 s），即
    分辨率的两倍，7.2 s 这类读数是合法的真实测量，故那些档照抖。
    **任何情况下都不会生成亚分辨率值**（6.73 s 这种）：抖动值一律是
    ``10 ** -MEASURE_DECIMALS[item]`` 的整数倍。伪造评分表根本没有的测量精度会与
    spec §12「可与学校官方报表逐格对账」冲突，那才是 Ruling 57 真正禁止的事。

    ``rng`` 由调用方传入，本函数不自建生成器（源码级守卫会拦）。每条记录抽一次，
    **不进 :func:`_raw_and_score` 的 memo**：记忆化的是昂贵的表扫描，若把抖动也记忆化，
    同一 ``(item, sex, age_group, floor(target))`` 的所有记录会拿到同一个抖动值，
    档内又只剩一个取值，等于白做。
    """
    scale = 10 ** MEASURE_DECIMALS[item]
    units = [int(round(threshold * scale)) for threshold in
             segment_thresholds(table, item, sex, age_group)]
    centre = int(round(raw * scale))
    if _band_is_lower_better(table, item, sex, age_group):
        lower = [unit for unit in units if unit < centre]
        if not lower:
            return raw
        lo, hi = max(lower) + 1, centre
    else:
        upper = [unit for unit in units if unit > centre]
        if not upper:
            return raw
        lo, hi = centre, min(upper) - 1
    if lo >= hi:
        # 区间只剩端点自身（含「档距 == 分辨率」那两种情形），不抽数
        return raw
    return (lo + int(rng.integers(0, hi - lo + 1))) / scale


def sub_floor_marks(
    population: list[dict],
    latents: dict[int, dict[str, float]],
    cfg: SeedConfig,
) -> dict[tuple[str, ScoredItem], frozenset[int]]:
    """按「该桶潜变量最低的 ``rate`` 比例学生」挑出表下溢出对象（Ruling 54(b) + 58）。

    返回 ``{(sex.value, item): frozenset(student_id)}``，是**该生的持久标记**：一个人
    一旦「做不起 5 个引体向上」，两学年六个时点都是如此。

    Ruling 54 原文写「按配置概率生成低于表内最低档的值」，字面读是对每条记录独立掷
    骰子。那样做会造出两个不可接受的后果：① ``latent_strength = +2`` 的壮汉一个引体
    向上都做不起，与本模块赖以存在的潜变量相关性直接冲突；② 同一个人 week1 做 12 个、
    week8 做 0 个。故改为按人选取，平手按 ``student_id`` 决胜（排序因此是全序，结果
    不依赖排序算法的稳定性实现）。

    本函数**不消耗随机数**（纯排序 + 计数），所以改 ``sub_floor_rate`` 不会平移
    标记之外的随机流；但它决定了记录循环里要不要抽表下值，故仍会改变同一种子的输出。

    **未知键响亮拒绝**：合法键是 ``Sex`` × **六个短板判定项**。BMI 不在其中——它的
    档位序列非单调、根本不走反查（``raw_from_score`` 对它直接抛 ``ValueError``），
    ``male:bmi`` 会是一个永远不生效的键；而静默忽略等于「配了但没生效」，这条配置的
    全部意义就是影响 Task 9 的分层分布，配错了必须当场炸开。
    """
    legal = [f"{sex.value}:{item.value}" for sex in Sex for item in WEAKNESS_ITEMS]
    unknown = sorted(set(cfg.sub_floor_rate) - set(legal))
    if unknown:
        raise ValueError(
            f"sub_floor_rate 含未知键 {unknown}；合法键格式是 "
            f'"<sex.value>:<item.value>"，共 {len(legal)} 个：{legal}'
            f"（BMI 走正查、不经反查，故不在其中）"
        )
    marks: dict[tuple[str, ScoredItem], frozenset[int]] = {}
    for key, rate in cfg.sub_floor_rate.items():
        sex_value, item_value = key.split(":")
        item = ScoredItem(item_value)
        latent_name = LATENT_BY_BUCKET[ITEM_BUCKET[item]]
        cohort = sorted(
            (person for person in population if person["sex"] == sex_value),
            key=lambda person: (
                latents[person["student_id"]][latent_name],
                person["student_id"],
            ),
        )
        count = int(round(len(cohort) * rate))
        marks[(sex_value, item)] = frozenset(
            person["student_id"] for person in cohort[:count]
        )
    return marks


def _bottom_score(table, item: ScoredItem, sex: Sex, age_group: str) -> int:
    """该 (项, 性别, 龄组) **表内最低档**的得分。

    表下溢出的学生两学年六个时点都拿这个分（``score_item`` 的低侧夹取，Ruling 17），
    故该项的学年间趋势恒为 0——Ruling 58 的地板效应。趋势模型必须把这 0 算进 ``Delta'``，
    否则被标记者的总分变化会被系统性高估约 ``10 × w / 100`` 分。
    """
    return int(
        score_item(
            table, item, min(segment_thresholds(table, item, sex, age_group)), sex, age_group
        )
    )


def _classify(deltas: dict[ScoredItem, int], total_change: float) -> str:
    """spec §6.3 判定表：自上而下匹配、**命中即停**（行序见 Ruling 64a）。

    这是生成侧的**验收判据**——「落档 → 重算 → 校正」循环拿它判断某名学生构造出来的整数
    得分是否真的满足他被分配的那个标签。它与 ``tests/seed/test_trend_oracle.py`` 里那个
    从规格正文独立翻译出来的 ``_oracle`` 是**两份实现**，由 Ruling 69① 的 500 人全覆盖
    测试对齐；Task 8 落地后再加 Ruling 69② 的生产侧对账，届时本函数应改为调用
    ``app.domain.derive.classify_trend``（前向约束）。

    ``deltas`` 只含 **6 个短板判定项**（BMI 不入计数，只通过 ``total_change`` 影响判定）；
    ``total_change`` 是**国标加权总分**（0–100）的变化量，不是 6 项之和（Ruling 63）。
    ``delta_i = 0`` 的项既不计入正也不计入负（§14 #23 的刻意保守）。
    """
    ups = sum(1 for delta in deltas.values() if delta > 0)
    downs = sum(1 for delta in deltas.values() if delta < 0)
    if (
        min(ups, downs) >= VOLATILE_MIN_SPLIT
        and max(abs(delta) for delta in deltas.values()) >= VOLATILE_ITEM_SWING
    ):
        return "波动大"
    if total_change <= -TOTAL_DROP_THRESHOLD or sum(
        1 for delta in deltas.values() if delta <= -SINGLE_ITEM_DROP
    ) >= DECLINING_ITEMS_THRESHOLD:
        return "持续下滑"
    if total_change >= IMPROVE_TOTAL_THRESHOLD and min(deltas.values()) > -IMPROVE_SINGLE_ITEM_DROP_LIMIT:
        return "稳步提升"
    return "稳定"


def _zero_sum_jitter(rng: np.random.Generator, count: int, bound: int) -> list[int]:
    """``count`` 个落在 ``[-bound, bound]`` 内的整数，**和恒为零**。

    抖动的作用是让六项不严格同步（真实数据里不存在六项完全同步变化的学生），而「和为零」
    保证它不改动 ``Delta``——否则逐项抖动会变成第二个未被定标的总分项，「稳定」的窄带就
    再也守不住。上一轮用的 ``N(0, sd)`` 正态抖动两条都不满足：它无界、也不零和。

    做法是先整批抽 ``count`` 个界内整数（**随机数消耗量与 bound / count 无关**，故
    同种子可复现），再把多出来的和按轮转逐项削掉。终止性：设 ``s = Σ values > 0``，
    则不可能所有 ``values[i]`` 都等于 ``-bound``（那样 ``s = -count·bound < 0``），
    故至少有一项还能减 1，轮转必会走到它；``s < 0`` 对称。整个过程不消耗随机数。
    """
    if bound <= 0 or count == 0:
        return [0] * count
    values = [int(value) for value in rng.integers(-bound, bound + 1, size=count)]
    excess = sum(values)
    index = 0
    while excess:
        step = 1 if excess > 0 else -1
        candidate = values[index] - step
        if -bound <= candidate <= bound:
            values[index] = candidate
            excess -= step
        index = (index + 1) % count
    return values


def _delta_target_windows(
    curr: dict[ScoredItem, int], bmi_delta: int, free: tuple[ScoredItem, ...]
) -> dict[str, tuple[float, float] | None]:
    """该生在四类标签下**可行**的 ``Delta_target`` 区间（``None`` = 该类对他不可行）。

    三个约束叠出这个区间（计划 Step 4「标签分配必须按可行域筛选」）：

    1. **名义区间**：``TREND_PROFILES[label].delta_target_range``（计划表格给的字面值）；
    2. **逐项可行域**：均匀分配下每项承担 ``100·Delta_6 / w_free``，而
       ``prev_i = curr_i − delta_i`` 必须落在 ``[0, 100]`` 内，故
       ``|Delta_6| ≤ w_free × (min_i 余量 − 抖动 − 校正预留) / 100``；
    3. **符号纯度**：六项必须整体同号（持续下滑全负、稳步提升全正、稳定无一项 ≤ −5）。
       落档只会把 ``prev`` 往下拉、把 ``delta_i'`` 往上抬（最多 9 分），若初始 ``delta_i``
       本身就在 0 附近，抬过 0 之后就可能凑出「恰好 3 正 3 负」，被判定表的**第一行**
       抢走标签——那时无论怎么调 ``Delta'`` 都命中不了自己的标签。

    **约束 2 用的是 ``min_i``（逐项余量的最小值），不是计划正文那句
    ``Σ_i w_i·(100 − curr_i) ≥ 100·|Delta_target|``**：后者是**加权和**判据，在均匀分配下
    并不蕴含逐项可行——余量集中在某一项时加权和够大、最小那项却装不下，校正循环会把
    ``prev_target`` 推出 100 之后再也推不动，最终 RuntimeError。简报 §6.1 第 1 条授权
    「先怀疑可行域筛选，把判据收紧再试」，这是收紧后的形式；判据的**形状**（可行域 +
    池不足响亮报错）与计划一致。
    """
    swing_max = TREND_PROFILES["波动大"].swing[1]
    windows: dict[str, tuple[float, float] | None] = {
        # 「波动大」要恰好 3 正 3 负，被表下溢出固定住一项的学生永远凑不出来（delta 恒 0
        # 既不计正也不计负），故直接排除；正号给最低的三项 → 需要 curr ≥ 幅值上限，
        # 负号给最高的三项 → 需要 curr ≤ 100 − 幅值上限（计划 Step 4 的 16 / 84）。
        "波动大": (0.0, 0.0)
        if len(free) == len(WEAKNESS_ITEMS)
        and min(curr[item] for item in free) >= swing_max
        and max(curr[item] for item in free) <= 100.0 - swing_max
        else None
    }
    # BMI 对总分变化的贡献：它不受趋势模型控制（来自身高体重自身的噪声与年度漂移），
    # 却占 15% 权重，一次 ±20 分的档位跳变就是 ±3 分——足以把一个「稳定」学生推过 ±5 线。
    # 故六项要承担的是 Delta_6 = Delta_target − b（计划 Step 4 第 3 步，Ruling 63）。
    b = ITEM_WEIGHTS[ScoredItem.BMI] * bmi_delta / 100.0
    w_free = sum(ITEM_WEIGHTS[item] for item in free)
    head_up = min(100 - curr[item] for item in free)
    head_down = min(curr[item] for item in free)
    for label in ("持续下滑", "稳步提升", "稳定"):
        profile = TREND_PROFILES[label]
        low, high = profile.delta_target_range
        room = {
            "持续下滑": head_up,
            "稳步提升": head_down,
            "稳定": min(head_up, head_down),
        }[label]
        # ⚠️ 已知的未爆哑弹（评审 Minor-7；本轮按控制者裁定**只补注释、不改公式**——改窗口
        # 会平移随机流、让全部 CSV 字节与已取证哈希作废）。这个 ``max(0.0, …)`` 钳位在
        # ``room ≤ profile.jitter + CORRECTION_RESERVE``（稳定类即 ``room ≤ 12``）时把
        # ``magnitude`` 压成 0，窗口塌成**单点** ``(b, b)``：该生的 ``Delta_target`` 不再是
        # 抽样区间而是一个确定值，且**一分校正预留都没拿到**。实测（``SeedConfig()`` 缺省
        # 500 人 / seed=20250828，直接读 ``_trend_inputs`` 产出的 bundle）：稳定类可行
        # 493 人里 **145 人**是零宽，实际被标为「稳定」的 200 人里 **91 人**是零宽；另三类
        # 一个都没有（持续下滑/稳步提升的名义区间宽 12 分，钳位后直接 ``lo > hi`` 判不可行，
        # 波动大的窗口本来就是 ``(0.0, 0.0)``，它不设 Delta 目标）。
        #
        # **单点目标本身并不安全，不要把它记成「落在 ±5 开区间中央所以没事」**：
        # 零宽必有 ``|b| ≤ 2``，而 BMI 档位只有 {60, 80, 100} → ``b ∈ {−6,−3,0,3,6}``，故
        # 这 145 人的窗口一律是 ``(0.0, 0.0)``、``bmi_delta`` 一律为 0 → ``Delta_target ≡ 0``、
        # ``base = 0``、``delta_i`` 只剩 ``[−2, +2]`` 的零和抖动。而落档是**单向**的
        # （``prev_i ≤ prev_target_i`` ⟹ ``delta_i' ≥ delta_i``），界 2 的零和抖动最多能有
        # **4 个正号项**（``(+1,+1,+1,+1,−2,−2)``），每个正号项吃掉的是它下面那一档的档距
        # （60 分以下是 10 分），故 ``Σ w_i·delta_i' ≤ (20+20+15+10)×10 = 650`` →
        # ``Delta'`` 最高约 **+6.5**，**已经越过 ``|Delta'| < 5`` 的上边界**。穷举这 91 人 ×
        # 全部 1751 个零和抖动向量（159341 组）实测：round-0 的 ``Delta'`` 落在 ``[−1, +6]``，
        # 其中 **110 组出带**（全在 ``+5`` 一侧，会被判成「稳步提升」）。
        # 下边界则是**结构性**安全的：``delta_i' < 0`` 要求 ``curr_i + |jitter|`` 恰好是官方档
        # （只有 62–78 那段 2 分细档满足），故 ``|delta_i'| ≤ 2``、
        # ``Σ w_i·delta_i' ≥ −(20+20+15+10)×2 = −130`` → ``Delta'`` 约 ≥ ``−1.3``（实测 −1），
        # 离 ``−5`` 很远。**风险因此是单边的：只有上边界会被顶穿。**
        #
        # **真正兜住它的是校正循环，不是这个窗口**：出带只朝一个方向，故
        # :func:`_correction_move` 只需要 ``direction = +1``（把 ``prev`` 往上推），而顶穿上界
        # 的那几项恰恰是低分项、``prev_i < 100`` 恒成立 → 永远推得动；每轮移动 ≥1 分
        # （w=20 且非端点档时 2 分），把 +6.5 拉回带内最多 3 轮，上限是
        # :data:`CORRECTION_MAX_ROUNDS` = 8。实测那 159341 组里 117 组需要校正、**最多 2 轮**、
        # ``RuntimeError`` **0 次**；生产那一轮 91 个零宽学生**一个都没触发校正**
        # （全 500 人 ``triggered = 16``、``max_rounds = 1``）。
        #
        # 与 :data:`CORRECTION_RESERVE` 的关系：预留的全部意义是「筛选时先扣掉一轮校正的
        # 空间」，钳位到 0 等于这批人的安全性**全部押在校正循环推得动上**，窗口一点余量都没
        # 给。所以 :func:`_settle_prev_targets` 末尾那两条 ``RuntimeError``（「趋势校正推不动
        # 了」与「N 轮仍未达判据」）是它唯一的兜底，两者的自证测试见
        # ``tests/seed/test_fitness.py``。
        # **Task 9 若调大 ``jitter``、调小 ``CORRECTION_STEP`` / ``CORRECTION_RESERVE``，或换
        # 一张档距更大的评分表，上面这笔账必须重算**：零宽人群会变大，而校正每轮的步长会
        # 变小，两个方向都在吃这 8 轮的余量。
        # （数字的口径：145/493 是**稳定类可行**的人里零宽的占比，91/200 是**实际被标为稳定**
        # 的人里的占比；复审报告写的是 133/489，本轮三条独立路径重测都是 145/493——含直接从
        # 记录的 ``score_*`` 列复算，且三个 CSV 的 SHA256 与复审时逐字相同，故数据没变。
        # 差异已作为关切上报。）
        magnitude = w_free * max(0.0, room - profile.jitter - CORRECTION_RESERVE) / 100.0
        # round(base) 的半格余量：round(x) ≤ k ⟺ x < k + 0.5，round(x) ≥ k ⟺ x ≥ k − 0.5
        purity = (0.5 + profile.jitter) * w_free / 100.0
        if label == "持续下滑":
            # 六项全 ≤ −1：round(base) + jitter ≤ −1
            high = min(high, b - purity)
        elif label == "稳步提升":
            # 六项全 ≥ +1：round(base) − jitter ≥ +1
            low = max(low, b + purity)
        else:
            # 无一项 ≤ −5：round(base) − jitter ≥ −4
            low = max(low, b + (profile.jitter - 4.5) * w_free / 100.0)
        lo, hi = max(low, b - magnitude), min(high, b + magnitude)
        windows[label] = (lo, hi) if lo <= hi else None
    return windows


def _trend_labels(
    population: list[dict],
    cfg: SeedConfig,
    rng: np.random.Generator,
    bundle: dict[int, dict],
) -> dict[int, str]:
    """按 ``cfg.trend_mix`` 的**精确配额**分配趋势标签，且**从各自的可行池里抽**。

    配额仍用 :func:`allocate_quota` + 洗牌，而不是逐个 ``rng.random()`` 抽样：抽样在 500 人
    上带 ±2% 的波动，20/15/25/40 就永远只能「大致」对上，测试也只能写容差；精确配额让
    「比例配错了」与「比例抽歪了」这两件事不再互相掩盖。

    分配顺序是 ``波动大 → 持续下滑 → 稳步提升 → 余下全部给稳定``（计划 Step 4）：
    「波动大」最受限（要 ±16 的摆幅 + 恰好 3 正 3 负），先挑才不会被前三类把可行的学生
    分光。「稳定」拿余下的人，所以前三类挑人时**优先挑稳定不可行的**——否则余下的人里会
    留下一个构造不出来的稳定标签。``sort`` 是稳定的，组内仍是 ``rng.permutation`` 的随机序。

    **池不足时响亮 ``ValueError``，报出需要数与实有数**，不得静默改标签：``trend_label``
    是交给 Task 8 交叉验证、并驱动分层规则 Y4 的真值，静默改标签等于把真值造假。
    """
    quota = allocate_quota(cfg.trend_mix, len(population))
    all_ids = [person["student_id"] for person in population]
    assigned: dict[int, str] = {}
    for label in FEASIBILITY_ORDER[:-1]:
        need = quota[label]
        pool = [
            sid
            for sid in all_ids
            if sid not in assigned and bundle[sid]["windows"][label] is not None
        ]
        if len(pool) < need:
            raise ValueError(
                f"趋势标签「{label}」的可行池不足：需要 {need} 人，实有 {len(pool)} 人"
                f"（全体 {len(all_ids)} 人）。判据见 _delta_target_windows 的注释；"
                f"不得静默改标签，因为 trend_label 是 Task 8 交叉验证与规则 Y4 的真值。"
            )
        shuffled = [pool[int(index)] for index in rng.permutation(len(pool))]
        shuffled.sort(key=lambda sid: 0 if bundle[sid]["windows"]["稳定"] is None else 1)
        for sid in shuffled[:need]:
            assigned[sid] = label
    residual = [sid for sid in all_ids if sid not in assigned]
    infeasible = [sid for sid in residual if bundle[sid]["windows"]["稳定"] is None]
    if infeasible:
        raise ValueError(
            f"余下 {len(residual)} 人应全部标为「稳定」（配额 {quota['稳定']}），但其中 "
            f"{len(infeasible)} 人在该类可行域之外（例如 student_id {infeasible[:5]}）。"
            f"前三类挑选时已优先让出稳定不可行的人，仍然不够，说明可行域筛选或配额本身"
            f"与该人群的得分分布不相容；不得静默改标签。"
        )
    for sid in residual:
        assigned[sid] = "稳定"
    return assigned


def _initial_deltas(
    label: str,
    curr: dict[ScoredItem, int],
    free: tuple[ScoredItem, ...],
    window: tuple[float, float],
    bmi_delta: int,
    rng: np.random.Generator,
) -> tuple[dict[ScoredItem, int], float]:
    """该生**自由项**上的初始 ``delta_i``（整数）与抽到的 ``Delta_target``。

    ``波动大`` 走形状构造：每项幅值 ``U(*swing)``（整数），**正号给该生得分最低的三项、
    负号给最高的三项**——低分项往上抬、高分项往下压，``prev_i`` 才装得进 ``[0, 100]``
    （计划 Step 4 的表格）。其余三类走**均匀分配**：六项（或五项）各承担约
    ``100·Delta_6 / w_free`` 分，再叠一个和为零的逐项抖动。

    **均匀分配而不是按 ``1/w_i`` 反比**：国标总分是加权**平均**，要让总分动 ``Delta`` 分，
    最自然的形态是六项一起动约 ``Delta`` 分。反比会让低权重项承担最大摆幅
    （``Delta_6 = −20`` 时 w=10 的项要降 33 分、w=20 的只降 17 分），既不可行
    （``prev_i`` 会冲出 100）也不像真实的整体衰退。
    """
    profile = TREND_PROFILES[label]
    if profile.swing is not None:
        if len(free) != len(WEAKNESS_ITEMS):
            raise RuntimeError(
                f"「{label}」要求六项全自由（恰好 3 正 3 负），但只有 {len(free)} 项自由："
                f"可行域筛选与形状构造脱节了"
            )
        ranked = sorted(free, key=lambda item: (curr[item], _ITEM_INDEX[item]))
        magnitudes = [
            int(value)
            for value in rng.integers(
                int(profile.swing[0]), int(profile.swing[1]) + 1, size=len(ranked)
            )
        ]
        half = len(ranked) // 2
        deltas = {
            item: magnitude if index < half else -magnitude
            for index, (item, magnitude) in enumerate(zip(ranked, magnitudes))
        }
        return deltas, 0.0
    delta_target = float(rng.uniform(*window))
    b = ITEM_WEIGHTS[ScoredItem.BMI] * bmi_delta / 100.0
    w_free = sum(ITEM_WEIGHTS[item] for item in free)
    base = 100.0 * (delta_target - b) / w_free
    jitter = _zero_sum_jitter(rng, len(free), int(profile.jitter))
    # math.floor(x + 0.5) 而不是 round()/np.rint：后两者是银行家舍入，对 −7.5 与 −6.5
    # 都给偶数（−8 与 −6），正负两侧的偏倚方向不一致，会让「下滑」与「提升」两类的
    # 实际幅度不对称。半值上取整是一个方向、可写进文档的确定规则。
    rounded = math.floor(base + 0.5)
    return {item: rounded + jitter[index] for index, item in enumerate(free)}, delta_target


def _correction_move(
    label: str,
    deltas: dict[ScoredItem, int],
    total_change: float,
    prev_scores: dict[ScoredItem, int],
    bounds: dict[ScoredItem, tuple[int, int]],
    free: tuple[ScoredItem, ...],
) -> tuple[ScoredItem, int] | None:
    """校正循环的一步：返回 ``(item, direction)``，``direction × CORRECTION_STEP`` 加到 prev_target 上。

    ``direction = +1`` 让该项的 ``prev`` 升一档、``delta_i'`` 变小（更负）；``-1`` 反之。
    选哪一项按两条规则：

    1. **形状优先**：若当前会被判成「波动大」而标签不是它（Ruling 64a 把形状放在第一行），
       先缩小幅值最大那一项的 ``|delta_i'|``。不先把形状修对，无论怎么调 ``Delta'``
       都命中不了自己的标签。
    2. **再调净方向**：按「当前被判成什么」与「应该是什么」的差，把**权重最大**的那一项
       朝需要的方向推一个官方档（计划 Step 4 第 4 步）。w 最大 → 每轮 ``Delta'`` 移动最多
       （``20 × 10 / 100 = 2`` 分），轮数因此最少。唯一例外是「持续下滑的第二分支被误触」
       （``Delta'`` 其实够高、只是 ≥3 项各降 ≥5 分），那时要推的是**降得最狠**的那一项，
       推最高权重的项解决不了它。

    推不动（已到表内端点档）就顺延到次高权重的项；全都推不动返回 ``None``，
    由调用方 ``RuntimeError`` 响亮失败。
    """
    by_weight = sorted(free, key=lambda item: (-ITEM_WEIGHTS[item], _ITEM_INDEX[item]))
    actual = _classify(deltas, total_change)

    def movable(item: ScoredItem, direction: int) -> bool:
        low, high = bounds[item]
        return prev_scores[item] < high if direction > 0 else prev_scores[item] > low

    def pick(direction: int, focus: ScoredItem | None = None):
        candidates = ((focus,) if focus is not None else ()) + tuple(by_weight)
        for item in candidates:
            if movable(item, direction):
                return item, direction
        return None

    biggest = max(free, key=lambda item: (abs(deltas[item]), ITEM_WEIGHTS[item]))
    if actual == "波动大" and label != "波动大":
        return pick(1 if deltas[biggest] > 0 else -1, biggest)
    if label == "波动大":
        # 3 正 3 负由构造保证、落档不改符号（幅值 ≥ 10 > 落档最多吃掉的 9 分），
        # 故只需把幅值推过 10 这一条线。
        return pick(-1 if deltas[biggest] > 0 else 1, biggest)
    if actual == "稳定":
        return pick(1 if label == "持续下滑" else -1)
    if actual == "持续下滑":
        dropping = [item for item in free if deltas[item] <= -SINGLE_ITEM_DROP]
        if total_change > -TOTAL_DROP_THRESHOLD and len(dropping) >= DECLINING_ITEMS_THRESHOLD:
            worst = min(dropping, key=lambda item: (deltas[item], -ITEM_WEIGHTS[item]))
            return pick(-1, worst)
        return pick(-1)
    return pick(1)


def _settle_prev_targets(
    label: str,
    info: dict,
    deltas: dict[ScoredItem, int],
    table,
    memo: dict,
    bounds_memo: dict,
) -> tuple[dict[ScoredItem, float], int]:
    """**落档 → 重算 → 校正**（计划 Step 4 第 4 步，承重），返回上学年 week1 的目标分与轮数。

    为什么不能靠留余量：``prev_i`` 是「目标分经 ``raw_from_score`` 就低取档后 ``score_item``
    回读」的结果，而国标得分序列是 ``100,95,90,85,80,78,…,62,60,50,40,30,20,10``——
    **60 分以下档距为 10 分**，就低取档单项最多吃掉 9 分、六项加权后最多约 7.65 分。
    这个损失与「稳定」类的 ±5 窄带同量级，把目标定远一点是躲不过去的。故把量化**显式化**：

    1. ``prev_target_i = curr_i − delta_i``；
    2. **落档** ``prev_i = score_item(raw_from_score(prev_target_i))``；
    3. **重算** ``delta_i' = curr_i − prev_i`` 与 ``Delta' = 本学年总分 − 上学年总分``；
    4. **校正**：不达判据就把某一项的 ``prev_target`` 再推一个官方档，回到第 2 步。

    ``Delta'`` 用 :func:`_weighted_total` 从**两个落档后的总分相减**算出，不用
    ``Σ w_i·delta_i' / 100``：``//100`` 的向下取整让两者相差最多 1 分，而判据是
    ``±5`` 的整数线，稳定类的可行带只有 ``[-4, +4]`` 九个整数——差 1 分就会有人在
    生成侧被判「达标」、在 oracle 侧被判「不达标」。Task 8 的 ``national_total`` 同样是
    ``//100``，故这里与之逐字同口径。

    循环**单调且有界**：每轮至少让 ``Delta'`` 朝目标移动 ``w_max × 10 / 100 = 2`` 分
    （最坏情况下被端点档削到 1 分），上限 :data:`CORRECTION_MAX_ROUNDS` 轮，超限
    ``RuntimeError`` 响亮失败，不静默放行一个标签与数据不符的学生。
    """
    free: tuple[ScoredItem, ...] = info["free"]
    sex: Sex = info["sex"]
    age_group: str = info["prev_group"]
    curr_six: dict[ScoredItem, int] = info["curr"]
    bounds: dict[ScoredItem, tuple[int, int]] = {}
    for item in free:
        key = (item, sex, age_group)
        if key not in bounds_memo:
            scores = [
                score_item(table, item, threshold, sex, age_group)
                for threshold in segment_thresholds(table, item, sex, age_group)
            ]
            bounds_memo[key] = (min(scores), max(scores))
        bounds[item] = bounds_memo[key]
    prev_targets = {item: float(curr_six[item] - deltas[item]) for item in free}
    curr_total = _weighted_total({**curr_six, ScoredItem.BMI: info["curr_bmi"]})
    for rounds in range(CORRECTION_MAX_ROUNDS + 1):
        prev_six = {
            item: _raw_and_score(
                table,
                item,
                float(np.clip(prev_targets[item], 0.0, 100.0)),
                sex,
                age_group,
                memo,
            )[1]
            for item in free
        }
        prev_six.update(info["fixed_prev"])
        deltas_now = {item: curr_six[item] - prev_six[item] for item in WEAKNESS_ITEMS}
        total_change = curr_total - _weighted_total(
            {**prev_six, ScoredItem.BMI: info["prev_bmi"]}
        )
        if _classify(deltas_now, total_change) == label:
            return prev_targets, rounds
        move = _correction_move(label, deltas_now, total_change, prev_six, bounds, free)
        if move is None:
            raise RuntimeError(
                f"趋势校正推不动了：student_id={info['student_id']} 标签「{label}」，"
                f"第 {rounds} 轮后 Delta'={total_change}、delta_i'={deltas_now}、"
                f"被判成「{_classify(deltas_now, total_change)}」，而六项已全部到达表内端点档。"
                f"说明可行域筛选放进了一个装不下该标签的学生。"
            )
        item, direction = move
        prev_targets[item] += direction * CORRECTION_STEP
    raise RuntimeError(
        f"趋势校正 {CORRECTION_MAX_ROUNDS} 轮仍未达判据：student_id={info['student_id']} "
        f"标签「{label}」，Delta'={total_change}、delta_i'={deltas_now}、"
        f"被判成「{_classify(deltas_now, total_change)}」。不静默放行标签与数据不符的学生。"
    )


def _trend_inputs(
    population: list[dict],
    targets: dict[int, dict[ScoredItem, float]],
    bodies: dict[tuple[int, int, int], tuple[float, float, float, int]],
    sub_floor_pairs: set[tuple[int, ScoredItem]],
    table,
    memo: dict,
) -> dict[int, dict]:
    """趋势模型的全部输入，按学生打包。

    ``curr`` 是该生**本学年 week1** 的六项落档得分（也就是记录里 ``score_*`` 列的值）：
    趋势必须在这个**整数**空间上构造，因为计划 Step 4 第 1 步写的是
    ``prev_target_i = curr_i − delta_i``，其中的 ``curr_i`` 是落档后的得分。用连续目标分会
    让 ``delta_i'`` 里混进本学年自己那一次落档的损失，校正循环于是同时要补两个方向的量化，
    收敛不了。被表下溢出标记的项两学年都拿底档分（Ruling 58 的地板效应），故它的
    ``curr_i`` 就是底档分、``delta_i`` 恒为 0，且**不参与分配**（``free`` 里没有它）。
    """
    bundle: dict[int, dict] = {}
    for person in population:
        sid = person["student_id"]
        sex = Sex(person["sex"])
        prev_group = age_group_of(person["age"] - 1)
        curr_group = age_group_of(person["age"])
        free = tuple(item for item in WEAKNESS_ITEMS if (sid, item) not in sub_floor_pairs)
        curr = {}
        for item in WEAKNESS_ITEMS:
            if (sid, item) in sub_floor_pairs:
                curr[item] = _bottom_score(table, item, sex, curr_group)
            else:
                curr[item] = _raw_and_score(
                    table,
                    item,
                    float(np.clip(targets[sid][item], 0.0, 100.0)),
                    sex,
                    curr_group,
                    memo,
                )[1]
        curr_bmi = bodies[(_CURRENT_INDEX, 0, sid)][3]
        prev_bmi = bodies[(_PREVIOUS_INDEX, 0, sid)][3]
        bundle[sid] = {
            "student_id": sid,
            "sex": sex,
            "prev_group": prev_group,
            "curr": curr,
            "free": free,
            "fixed_prev": {
                item: _bottom_score(table, item, sex, prev_group)
                for item in WEAKNESS_ITEMS
                if (sid, item) in sub_floor_pairs
            },
            "curr_bmi": curr_bmi,
            "prev_bmi": prev_bmi,
            "windows": _delta_target_windows(curr, curr_bmi - prev_bmi, free),
        }
    return bundle


def _trend_prev_targets(
    population: list[dict],
    labels: dict[int, str],
    bundle: dict[int, dict],
    table,
    memo: dict,
    bounds_memo: dict,
    rng: np.random.Generator,
) -> tuple[dict[int, dict[ScoredItem, float]], dict[str, int]]:
    """每名学生的**上学年 week1 目标分**（已落档校正），以及校正循环的统计。

    其余两个时点的上学年目标分是 ``prev_target + drift[slot]``（与本学年同一条漂移），
    故学年间的目标差在三个时点上都是同一个 ``delta_i``——但**落档后的 ``delta_i'`` 只在
    week1 上被判据保证**，week8/week16 会各自再量化一次（前向约束，见报告）。

    随机数消耗顺序：外层按 ``population`` 的列表序，每人先抽 ``Delta_target``（或波动大的
    六个幅值）、再抽零和抖动；校正循环**不消耗随机数**，故轮数多少不影响可复现性。
    """
    prev_targets: dict[int, dict[ScoredItem, float]] = {}
    stats = {"students": 0, "triggered": 0, "total_rounds": 0, "max_rounds": 0}
    for person in population:
        sid = person["student_id"]
        label = labels[sid]
        info = bundle[sid]
        deltas, _delta_target = _initial_deltas(
            label,
            info["curr"],
            info["free"],
            info["windows"][label],
            info["curr_bmi"] - info["prev_bmi"],
            rng,
        )
        settled, rounds = _settle_prev_targets(label, info, deltas, table, memo, bounds_memo)
        prev_targets[sid] = settled
        stats["students"] += 1
        stats["total_rounds"] += rounds
        if rounds:
            stats["triggered"] += 1
        stats["max_rounds"] = max(stats["max_rounds"], rounds)
    return prev_targets, stats


def _base_targets(
    population: list[dict],
    latents: dict[int, dict[str, float]],
    rng: np.random.Generator,
) -> dict[int, dict[ScoredItem, float]]:
    """每名学生**本学年 week1** 的六项设计得分（连续值，尚未落到国标档位）。

    逐项噪声在这里抽**一次**、之后所有学年与时点共用：同一个人的肺活量在 week1 与
    week16 之间应当是「同一条水平线加上漂移」，而不是两次互不相干的抽样——后者会让
    学年内的变化幅度与学年间的一样大，趋势项就白注入了。
    """
    targets: dict[int, dict[ScoredItem, float]] = {}
    for person in population:
        latent = latents[person["student_id"]]
        targets[person["student_id"]] = {
            item: float(
                np.clip(
                    BASE_SCORE_MEAN
                    + BASE_SCORE_SLOPE * latent[LATENT_BY_BUCKET[ITEM_BUCKET[item]]]
                    + rng.normal(0.0, BASE_SCORE_NOISE_SD),
                    0.0,
                    100.0,
                )
            )
            for item in WEAKNESS_ITEMS
        }
    return targets


def _within_year_drifts(
    population: list[dict],
    labels: dict[int, str],
    cfg: SeedConfig,
    rng: np.random.Generator,
) -> dict[int, tuple[float, float, float]]:
    """每名学生学年内三个时点的**累积**漂移 ``(week1, week8, week16)``，``week1`` 恒为 0。

    ``cfg.intervention_effect`` 是留给 Plan 03 的参数位：它现在被加到每个人的间隔增益
    均值上，**不区分实验班与对照班**——那要等 Plan 03 的干预引擎决定谁进实验组。
    留位而不实现半套，是为了让 Plan 03 改的是数值与分支，而不是函数签名。
    """
    drifts: dict[int, tuple[float, float, float]] = {}
    mean = INTERVAL_GAIN_MEAN + cfg.intervention_effect
    for person in population:
        sd = INTERVAL_GAIN_SD * TREND_PROFILES[labels[person["student_id"]]].drift_scale
        first = float(rng.normal(mean, sd))
        second = float(rng.normal(mean, sd))
        drifts[person["student_id"]] = (0.0, first, first + second)
    return drifts


def _anthropometrics(
    population: list[dict], table, rng: np.random.Generator
) -> dict[tuple[int, int, int], tuple[float, float, float, int]]:
    """两学年 × 三时点 × 全体学生的 ``(身高, 体重, BMI, BMI 得分)``，键 ``(学期下标, 时点下标, 学号)``。

    **必须在趋势模型之前整批算完**（计划 Step 4 第 3 点、简报 §6.2 第 2 条）：
    ``Delta_6 = Delta_target − w_bmi × delta_bmi / 100`` 要在抽六项 ``delta_i`` **之前**
    就知道上学年的 BMI 得分，而它来自上学年 week1 的身高体重。原来「一条记录里先抽身高
    体重、再抽六项」的单趟循环做不到这一点，故 :func:`make_fitness_tests` 被拆成两趟；
    身高体重的抽数点因此全部前移，随机流被整体平移——这是本轮改动的预期后果，不是缺陷，
    但要重做可复现性取证。

    表达式与遍历顺序（学期 → 时点 → 学生）与拆分前逐字一致：叠上测量噪声后再夹回
    ``population`` 的那条安全带（噪声很小，sd 0.3 / 0.9，但一次越界就会让清洗层记一条
    ``outlier_corrected``，与 ``inject_dirty`` 注入的那批混在一起，Task 5 的交叉验证就再也
    分不清哪一条是谁造成的）。龄组按**该记录所属学年**取（Ruling 56），正反查同表。
    """
    bodies: dict[tuple[int, int, int], tuple[float, float, float, int]] = {}
    for semester_index, plan in enumerate(SEMESTERS):
        year_shift = 0.0 if plan.is_current else PREVIOUS_YEAR_WEIGHT_SHIFT
        for slot in range(len(TIMEPOINT_SEQUENCE)):
            for person in population:
                sex = Sex(person["sex"])
                age_group = age_group_of(
                    person["age"] if plan.is_current else person["age"] - 1
                )
                height = round(
                    float(
                        np.clip(
                            person["height_cm"] + rng.normal(0.0, HEIGHT_NOISE_SD),
                            *HEIGHT_RANGE,
                        )
                    ),
                    1,
                )
                weight = round(
                    float(
                        np.clip(
                            person["weight_kg"]
                            + rng.normal(0.0, WEIGHT_NOISE_SD)
                            + year_shift,
                            *WEIGHT_RANGE,
                        )
                    ),
                    1,
                )
                bmi = round(weight / (height / 100.0) ** 2, 1)
                bodies[(semester_index, slot, person["student_id"])] = (
                    height,
                    weight,
                    bmi,
                    int(score_item(table, ScoredItem.BMI, bmi, sex, age_group)),
                )
    return bodies


def make_fitness_tests(
    population: list[dict],
    latents: dict[int, dict[str, float]],
    cfg: SeedConfig,
    rng: np.random.Generator,
) -> list[dict]:
    """生成两学年 × 三时点 × 全体学生的体测记录。

    记录里的键分三组：

    * **契约列**——:data:`app.adapters.base.FITNESS_COLUMNS` 的 11 列，
      :func:`app.seed.generate.write_csv` 只挑这些列写盘；
    * **得分列**——``score_<项名>`` 七项与 ``score_<桶名>_mean`` 三项桶均值。它们是
      生成期的诊断量，用来验证反查确实落回了目标档位、并让「耐力与力量得分正相关」
      这条断言有得可算。**既不写盘也不入库**：管道一律从清洗后的原始值重新正查得分，
      生成器算的分数不是第二份真相。脏数据注入会改掉原始值而**不会**回算这些列，
      所以被注入过的行上两者不再自洽——这是有意的，它们本来就是设计期的量；
    * ``trend_label``——该生的四类趋势标签真值，供 Task 8 交叉验证与本报告统计比例。
      **它现在是真值而不是装饰**：由可行域筛选 + 落档重算校正构造，并被
      ``tests/seed/test_trend_oracle.py`` 逐人对账（Ruling 69①）。

    **两趟结构（承重）**：先整批算完身高体重与 BMI 得分（:func:`_anthropometrics`），
    再算六项。原因是趋势定标必须先扣掉 BMI 的加权贡献——``Delta_6 = Delta_target −
    w_bmi × delta_bmi / 100``，而 BMI 占 15% 权重、一次档位跳变就是 ±3 分，足以把一个
    「稳定」学生推过 ±5 线（计划 Step 4 第 3 点、Ruling 63）。单趟循环里上学年的身高体重
    与六项在同一条记录上先后抽出，抽 ``delta_i`` 时 ``delta_bmi`` 还不存在。

    调用顺序就是随机数消耗顺序，**不得调整**：本学年设计得分 → 身高体重（两学年三时点）
    → 标签（三个可行池各一次 ``rng.permutation``）→ 学年内漂移 → 趋势 ``delta_i``
    → 记录循环里的表下值与档内抖动。

    遍历顺序是「学期 → 时点 → 学生」，三层的顺序都固定，随机数序列因此完全由 ``seed``
    决定。上学年排在本学年之前（:data:`app.seed.config.SEMESTERS` 的声明序）。

    **原始值的两处后处理，随机数消耗顺序同样是契约**：在记录循环内按
    :data:`app.domain.indicators.WEAKNESS_ITEMS` 的声明序逐项处理，被
    :func:`sub_floor_marks` 标记的项抽一次表下值（Ruling 54(b)），其余项在
    ``cfg.jitter_within_band`` 为真时调 :func:`jitter_raw`，而它**只在有抖动空间时**
    才抽数（Ruling 54(a)）。所以改 :data:`MEASURE_DECIMALS`、改 ``sub_floor_rate``、
    或改这两者的先后顺序，都会整体平移随机流、改变同一 ``seed`` 的输出——这是配置
    变更的预期后果，不是缺陷，但每次都要重做可复现性取证。
    """
    table = standard()
    memo: dict = {}
    bounds_memo: dict = {}
    targets = _base_targets(population, latents, rng)
    bodies = _anthropometrics(population, table, rng)
    # 未知键在此响亮报错（附带完整合法键清单），而不是等到某个学生恰好命中才炸
    sub_floor_pairs = {
        (student_id, item)
        for (_sex_value, item), student_ids in sub_floor_marks(population, latents, cfg).items()
        for student_id in student_ids
    }
    bundle = _trend_inputs(population, targets, bodies, sub_floor_pairs, table, memo)
    labels = _trend_labels(population, cfg, rng, bundle)
    drifts = _within_year_drifts(population, labels, cfg, rng)
    prev_targets, _trend_stats = _trend_prev_targets(
        population, labels, bundle, table, memo, bounds_memo, rng
    )

    records: list[dict] = []
    for semester_index, plan in enumerate(SEMESTERS):
        for slot, timepoint in enumerate(TIMEPOINT_SEQUENCE):
            tested_on = timepoint_date(plan, timepoint).isoformat()
            batch_key = base.make_batch_key(plan.academic_year, timepoint)
            for person in population:
                student_id = person["student_id"]
                sex = Sex(person["sex"])
                # 龄组按**该记录所属学年**取（Ruling 56）。person["age"] 是以当前学期
                # 开学日为参考日的年龄，上学年该生小一岁；age_group_of 的分界是 19/20，
                # 故 age == 20 的学生上学年落在「大一、大二」那张表上（实测 500 人配置下
                # 132 人 = 26.4%）。这个 age_group 必须贯穿本条记录的全部查表：BMI 正查、
                # 六项反查与回读、以及表下溢出要用的「表内最低档原始值」——正反查同表，
                # 否则趋势差值（本学年得分 − 上学年得分）会带系统性偏差，而趋势是分层
                # 规则 Y4 的唯一输入。_raw_and_score 的 memo 键含 age_group，故两个龄组
                # 的条目互不串味。
                age_group = age_group_of(
                    person["age"] if plan.is_current else person["age"] - 1
                )
                drift = drifts[student_id][slot]
                height, weight, _bmi, bmi_score = bodies[(semester_index, slot, student_id)]
                raws: dict[ScoredItem, float] = {}
                scores: dict[ScoredItem, int] = {ScoredItem.BMI: bmi_score}
                for item in WEAKNESS_ITEMS:
                    if (student_id, item) in sub_floor_pairs:
                        # 表下溢出（Ruling 54(b)，选取方式见 sub_floor_marks）。
                        # **逐条重抽**而不是给每人钉一个固定值：同一个人六次测量的读数
                        # 本来就会波动（0、2、1、3…），钉死一个值反而不像真实数据。
                        # floor_raw 随**本条记录**的龄组走（Ruling 56）：男生引体向上
                        # 大一、大二 = 5 次，大三、大四 = 6 次。
                        # 得分一律由 score_item 的低侧夹取（Ruling 17）得出，**不写死 10**：
                        # 写死会把「表下值拿底档分」这条口径的所有权从评分表挪到生成器。
                        # 下游影响（承重）：被标记者该项得分被钉死在底档，故该项的学年间
                        # 趋势恒为 0（地板效应），Task 8 的趋势判定与 Task 9 的黄金用例
                        # 必须容忍。趋势模型也不在这一项上分配 delta（见 _trend_inputs）。
                        floor_raw = int(min(segment_thresholds(table, item, sex, age_group)))
                        raw = float(int(rng.integers(0, floor_raw)))
                        realised = int(score_item(table, item, raw, sex, age_group))
                    else:
                        # 上学年用的是**已落档校正过的** week1 目标分（Ruling 62 的符号
                        # 约定：prev_target = curr_i − delta_i），再叠上与本学年同一条
                        # 学年内漂移。故 week1 上学年的落档得分与 _settle_prev_targets
                        # 里重算出的 prev_i 逐字相同——oracle 测试量的正是这一对。
                        design = (
                            targets[student_id][item]
                            if plan.is_current
                            else prev_targets[student_id][item]
                        )
                        raw, realised = _raw_and_score(
                            table,
                            item,
                            float(np.clip(design + drift, 0.0, 100.0)),
                            sex,
                            age_group,
                            memo,
                        )
                        if cfg.jitter_within_band:
                            # 抖动只作用于原始值，**不作用于目标分与 realised 得分**：
                            # 它按构造不跨档（见 jitter_raw），故得分仍是那一个。
                            raw = jitter_raw(table, item, raw, sex, age_group, rng)
                    raws[item] = raw
                    scores[item] = realised
                record = {
                    "student_id": student_id,
                    "student_no": person["student_no"],
                    "academic_year": plan.academic_year,
                    "timepoint": timepoint,
                    "batch_key": batch_key,
                    "tested_on": tested_on,
                    "height_cm": height,
                    "weight_kg": weight,
                    "score_bmi": scores[ScoredItem.BMI],
                }
                for item in WEAKNESS_ITEMS:
                    record[COLUMN_BY_ITEM[item]] = raws[item]
                    record[f"score_{item.value}"] = scores[item]
                for latent_name, items in ITEMS_BY_LATENT.items():
                    record[f"score_{latent_name}_mean"] = float(
                        sum(scores[item] for item in items) / len(items)
                    )
                record["trend_label"] = labels[student_id]
                records.append(record)
    return records
