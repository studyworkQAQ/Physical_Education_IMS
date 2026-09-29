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

**本模块是 ``app.seed`` 里唯一会碰磁盘的地方**，而且只经 :func:`app.refdata.standard`
这个受管加载器读国标评分表（进程内单例、只读、由 ``MappingProxyType`` 封住就地改写）。
生成器自己不 open 任何文件。
"""
import math
from dataclasses import dataclass

import numpy as np

from app.adapters import base
from app.domain.indicators import (
    ITEM_BUCKET,
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

# latent_fitness 的载荷与残差标准差：
#   endurance = 0.8·fitness + N(0, 0.6)；strength = 0.7·fitness + N(0, 0.7)
#   speedflex = 0.6·fitness + N(0, 0.8)
# 简报把残差写作 N(0, 0.6) 这种形状，这里按**标准差**读（不是方差）：按方差读会让
# 耐力/力量的理论相关系数从 0.57 掉到 0.46，叠上逐项噪声与国标档位离散化之后已经贴近
# 「相关系数 > 0.4」那条断言的边界，而按标准差读留出的是 0.51 左右的实测余量。
LATENT_LOADINGS: dict[str, tuple[float, float]] = {
    "endurance": (0.8, 0.6),
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
# 两学年趋势与学年内漂移（简报 Step 4）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrendProfile:
    """一类趋势标签的量化定义。

    ``prev_offset`` 是「上学年得分 = 本学年得分 + U(*prev_offset)」的区间：偏移为正
    表示上学年更好，也就是**下滑**。``drift_scale`` 放大学年内三个时点之间的随机漂移，
    「波动大」因此不只是学年间跳，学期内也跳。
    """

    prev_offset: tuple[float, float]
    drift_scale: float


TREND_PROFILES: dict[str, TrendProfile] = {
    "持续下滑": TrendProfile(prev_offset=(4.0, 12.0), drift_scale=1.0),
    "波动大": TrendProfile(prev_offset=(-10.0, 10.0), drift_scale=2.5),
    "稳步提升": TrendProfile(prev_offset=(-12.0, -4.0), drift_scale=1.0),
    "稳定": TrendProfile(prev_offset=(-2.0, 2.0), drift_scale=0.6),
}

# 一个采集间隔（week1→week8、week8→week16）的平均得分增益与其标准差。均值取小正数：
# 一学期体育课下来体能略有进步，但幅度必须远小于学年间的趋势项，否则趋势会被学期内
# 的自然增长冲淡，Task 8 的趋势判定就分不出四类人。
INTERVAL_GAIN_MEAN = 0.8
INTERVAL_GAIN_SD = 1.5
# 趋势项在六个项目上的逐项抖动：一个人整体下滑，但柔韧性可能反而变好，
# 全部项目严格同步下滑在真实数据里是不存在的。
ITEM_TREND_JITTER_SD = 1.5

# 每条体测记录相对该生基准值的测量噪声（同一台仪器、同一个人在不同批次上的读数差）
HEIGHT_NOISE_SD = 0.3
WEIGHT_NOISE_SD = 0.9
# 上学年相对本学年的体重基线差：一年前的读数整体略低一点，量级远小于噪声
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
    fitness = rng.normal(cfg.latent_mean, 1.0, total)
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


def _trend_labels(
    population: list[dict], cfg: SeedConfig, rng: np.random.Generator
) -> dict[int, str]:
    """按 ``cfg.trend_mix`` 给每名学生分配一个趋势标签。

    用 :func:`allocate_quota` 精确配额 + 洗牌，而不是逐个 ``rng.random()`` 抽样：
    抽样在 500 人上带 ±2% 的波动，简报要求的 20/15/25/40 就永远只能「大致」对上，
    测试也只能写容差；精确配额让「比例配错了」与「比例抽歪了」这两件事不再互相掩盖。
    """
    quota = allocate_quota(cfg.trend_mix, len(population))
    pool = np.array(
        [label for label, count in quota.items() for _ in range(count)], dtype=object
    )
    rng.shuffle(pool)
    return {person["student_id"]: str(pool[index]) for index, person in enumerate(population)}


def _trend_offsets(
    population: list[dict],
    labels: dict[int, str],
    rng: np.random.Generator,
) -> dict[int, dict[ScoredItem, float]]:
    """每名学生「上学年相对本学年」的得分偏移，逐项一个。

    偏移 = 一个**跨六项共享**的标签级偏移 + 每项一个小抖动。共享项保证一个人的六个
    项目朝同一方向变（Task 8 判趋势靠的正是这种一致性），抖动保证他不会六项严格同步
    （真实数据里不存在这种学生）。

    随机数消耗顺序：外层按 ``population`` 的列表序，内层按 ``WEAKNESS_ITEMS`` 的声明序。
    """
    offsets: dict[int, dict[ScoredItem, float]] = {}
    for person in population:
        profile = TREND_PROFILES[labels[person["student_id"]]]
        shared = float(rng.uniform(*profile.prev_offset))
        offsets[person["student_id"]] = {
            item: shared + float(rng.normal(0.0, ITEM_TREND_JITTER_SD))
            for item in WEAKNESS_ITEMS
        }
    return offsets


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
    labels = _trend_labels(population, cfg, rng)
    offsets = _trend_offsets(population, labels, rng)
    targets = _base_targets(population, latents, rng)
    drifts = _within_year_drifts(population, labels, cfg, rng)
    # 未知键在此响亮报错（附带完整合法键清单），而不是等到某个学生恰好命中才炸
    sub_floor_pairs = {
        (student_id, item)
        for (_sex_value, item), student_ids in sub_floor_marks(population, latents, cfg).items()
        for student_id in student_ids
    }

    records: list[dict] = []
    memo: dict = {}
    for plan in SEMESTERS:
        year_shift = 0.0 if plan.is_current else PREVIOUS_YEAR_WEIGHT_SHIFT
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
                # 叠上测量噪声后再夹回 population 的那条安全带：噪声很小（sd 0.3 / 0.9），
                # 但一次越界就会让清洗层记一条 outlier_corrected，与 inject_dirty 注入的
                # 那批混在一起，Task 5 的交叉验证就再也分不清哪一条是谁造成的。
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
                raws: dict[ScoredItem, float] = {}
                scores: dict[ScoredItem, int] = {
                    ScoredItem.BMI: int(
                        score_item(table, ScoredItem.BMI, bmi, sex, age_group)
                    )
                }
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
                        # 必须容忍。
                        floor_raw = int(min(segment_thresholds(table, item, sex, age_group)))
                        raw = float(int(rng.integers(0, floor_raw)))
                        realised = int(score_item(table, item, raw, sex, age_group))
                    else:
                        target = targets[student_id][item] + drift
                        if not plan.is_current:
                            target -= offsets[student_id][item]
                        raw, realised = _raw_and_score(
                            table, item, float(np.clip(target, 0.0, 100.0)), sex, age_group, memo
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
