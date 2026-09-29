"""潜变量模型与体测记录生成（spec §10.2）。

**为什么是潜变量驱动而不是逐项独立随机**
六个短板判定项若各自独立抽分，耐力与力量得分的相关系数会落在 0 附近，而真实人群里
它们由同一个「体能水平」牵引、显著正相关（本模块在缺省配置下实测约 0.51）。差别不是
美观问题：分层引擎按能力桶聚合短板、处方引擎按主导桶给运动处方，独立随机的数据会让
「短板集中在某个桶」这件事几乎不发生，于是整个系统的核心路径在演示数据上根本走不到。
所以先抽一个共同因子 ``latent_fitness``，再让它按不同载荷派生出耐力 / 力量 / 速度柔韧
三个桶的潜变量，得分由桶潜变量生成（简报 Step 3 的公式逐字实现）。

**得分 → 原始值一律走国标表的正反查，不做任何舍入或插值**
``raw_from_score`` 是就低取档的方向感知反查（Ruling 22），拿到什么就存什么；
``score_item`` 再把存下来的原始值正查回得分（Ruling 18）。两者对每一个官方档精确往返，
所以记录里带的 ``score_*`` 与原始值天然自洽，``tests/seed`` 里有一条测试专门钉这一点。
次数项（引体向上 / 仰卧起坐）的档边界本身就是整数，反查结果一定是可测量的读数——
**任何一处 ``round()`` 都可能把 13.5 顶成 14 从而跨过档位**，故本模块不做舍入。

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
    """
    table = standard()
    labels = _trend_labels(population, cfg, rng)
    offsets = _trend_offsets(population, labels, rng)
    targets = _base_targets(population, latents, rng)
    drifts = _within_year_drifts(population, labels, cfg, rng)

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
                age_group = age_group_of(person["age"])
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
                    target = targets[student_id][item] + drift
                    if not plan.is_current:
                        target -= offsets[student_id][item]
                    raw, realised = _raw_and_score(
                        table, item, float(np.clip(target, 0.0, 100.0)), sex, age_group, memo
                    )
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
