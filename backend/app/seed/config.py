"""仿真数据生成器的配置与日历骨架。

本模块是 ``app.seed`` 的叶子：不生成任何数据、不碰数据库、**尤其不碰时钟**。
它只提供三样东西：

1. :class:`SeedConfig`——一次生成的全部可调旋钮；
2. 学期日历（:data:`SEMESTERS`、:func:`timepoint_date`）——两学年 × 三时点的全部
   业务日期都由它算出；
3. :func:`allocate_quota`——把配置里的比例折算成**精确**加起来等于总数的整数配额。

**为什么日历写死在这里而不用 ``date.today()``**
可复现是本项目的硬要求（spec §1.3 逐人可追溯、研究数据必须能重跑）。一个随运行日
漂移的参考日会让同一个 ``seed`` 在不同日期产出不同的 ``birth`` / ``tested_on`` 列，
「同种子字节级一致」当场失效，而且失效得无声无息——每次跑都是合法数据，只是每次
都不一样。所以学年、学期名、开学日一律是常量。

**为什么配额要精确分配而不是按概率抽样**
按 ``rng.random() < ratio`` 逐个抽样，500 人下四类趋势标签的实际比例会带 ±2% 的抽样
波动，测试就只能写容差；容差一旦放宽到能吸收波动，也就宽到能吸收「比例配错了」这类
真缺陷。最大余额法给出的是确定整数，测试因此可以断言等号。
"""
import datetime as dt
import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 学期日历
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemesterPlan:
    """一个学期的日历骨架。

    ``name`` 是 CLI 与幂等键的查找键（``semester.name`` 上有 UNIQUE 约束）；
    ``academic_year`` 必须形如「四位-四位」，因为它要经
    :func:`app.adapters.base.make_batch_key` 构造 ``batch_key``，那里会在构造时校验格式。
    """

    name: str
    academic_year: str
    start_date: dt.date
    is_current: bool


# 上学年在前、本学年在后：生成顺序即列表顺序，两条学年因此共用同一条随机数序列。
# 开学日都取当年的第一个星期一（2024-09-02、2025-09-01）。
SEMESTERS: tuple[SemesterPlan, ...] = (
    SemesterPlan(
        name="2024-2025-1",
        academic_year="2024-2025",
        start_date=dt.date(2024, 9, 2),
        is_current=False,
    ),
    SemesterPlan(
        name="2025-2026-1",
        academic_year="2025-2026",
        start_date=dt.date(2025, 9, 1),
        is_current=True,
    ),
)

# 三个采集节点在学期内的周序（0 基）。与 app/adapters/base.py 的 TIMEPOINTS 同域，
# 但这里是**有序**的：生成顺序必须固定，否则随机数序列会随集合迭代顺序漂移。
TIMEPOINT_SEQUENCE: tuple[str, ...] = ("week1", "week8", "week16")
TIMEPOINT_WEEK_INDEX: dict[str, int] = {"week1": 0, "week8": 7, "week16": 15}
_LAST_TIMEPOINT_WEEK = TIMEPOINT_WEEK_INDEX[TIMEPOINT_SEQUENCE[-1]]


def current_semester() -> SemesterPlan:
    """当前学期。组织结构（教学班、选课关系）一律挂在它上面。"""
    return next(plan for plan in SEMESTERS if plan.is_current)


def timepoint_date(plan: SemesterPlan, timepoint: str) -> dt.date:
    """某学期某采集节点的日历日期。

    ``week1`` 就落在开学日当天，``week8`` / ``week16`` 依次推 7 / 15 周。返回的是
    ``date`` 而不是字符串：写盘时由 :func:`app.seed.generate.write_csv` 统一
    ``.isoformat()``，日期形状因此只有一个所有者（Ruling 38）。
    """
    return plan.start_date + dt.timedelta(weeks=TIMEPOINT_WEEK_INDEX[timepoint])


def semester_end_date(plan: SemesterPlan, weeks: int) -> dt.date:
    """学期结束日 = 开学日 + 教学周数。

    取 ``max(weeks, 最后一个采集节点的周序 + 1)``：``week16`` 的测量日必须落在学期
    区间内，而 ``--weeks`` 是可传的，传个 8 就会让 ``week16`` 掉到学期结束之后——
    那是一条谁都不会去查的静默不一致。
    """
    return plan.start_date + dt.timedelta(weeks=max(weeks, _LAST_TIMEPOINT_WEEK + 1))


# 年龄 → 出生日的**固定参考日**：当前学期的开学日。
# 用「今天」会让同一 seed 在不同日期产出不同的 birth 列，故这里必须是常量。
BIRTH_REFERENCE_DATE: dt.date = current_semester().start_date


# ---------------------------------------------------------------------------
# 配额分配
# ---------------------------------------------------------------------------


def allocate_quota(ratios: dict[str, float], total: int) -> dict[str, int]:
    """把比例折算成**精确**加起来等于 ``total`` 的整数配额（最大余额法）。

    先给每个键 ``floor(total * ratio)``，再把剩下的名额按小数余额从大到小补出去。
    余额相同时按 ``ratios`` 的**字面顺序**决胜（用下标而不是键名比较），所以结果既不
    依赖浮点相等、也不依赖字典的哈希顺序——同一个 ``ratios`` 字面量永远给出同一个配额。

    比例之和必须为 1（误差 1e-9 内）：本函数是「把一个整体切成几份」，不是一般化的
    抽样概率。和不为 1 时 ``leftover`` 会是负数，``ranked[:负数]`` 静默截掉尾部名额，
    配额之和于是小于 ``total``——少了的那几个人会在编班时凭空消失且不报错，故在此响亮拒绝。
    """
    keys = tuple(ratios)
    if abs(math.fsum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError(
            f"比例之和必须为 1，实际是 {math.fsum(ratios.values())!r}：{ratios}"
        )
    exact = {key: total * ratios[key] for key in keys}
    quota = {key: math.floor(value) for key, value in exact.items()}
    leftover = total - sum(quota.values())
    ranked = sorted(
        range(len(keys)), key=lambda i: (quota[keys[i]] - exact[keys[i]], i)
    )
    for index in ranked[:leftover]:
        quota[keys[index]] += 1
    return quota


# ---------------------------------------------------------------------------
# 生成配置
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedConfig:
    """一次仿真数据生成的全部旋钮。

    **不得加 ``slots=True``**：简报的 ``test_different_seed_produces_different_dataset``
    用 ``SeedConfig(**{**CFG.__dict__, "seed": 1})`` 复制配置，而带 slots 的数据类没有
    ``__dict__``，那一行会直接 ``AttributeError``。``frozen=True`` 保留：配置在一次生成
    里被多个模块共享，而 ``dirty`` / ``trend_mix`` / ``target_layer_dist`` 是**可变的
    dict**——冻结实例挡住的是「换掉整个字段」，挡不住就地 ``cfg.dirty["missing"] = 0``，
    所以生成器一律只读这些字典，任何一处就地改写都会让「同种子一致」失效。

    ``target_layer_dist`` 与 ``latent_mean`` 的关系见 :data:`latent_mean` 的说明。
    """

    students: int = 500
    weeks: int = 16
    seed: int = 20250828
    male_ratio: float = 0.55
    target_layer_dist: dict[str, float] = field(
        default_factory=lambda: {"red": 0.20, "yellow": 0.45, "green": 0.35}
    )
    teachers: int = 3
    sections_per_teacher: int = 2
    section_size: tuple[int, int] = (30, 38)
    # 四类脏数据的注入比例（spec §10.7：缺失 3–5%、异常值 0.5%、量纲错误 0.3%、重复 1%）。
    # 前三类按**测量单元格**计，duplicate 按**记录**计——见 app/seed/generate.py 的
    # inject_dirty。这四条不是「把一个整体切成几份」，故不走 allocate_quota。
    dirty: dict[str, float] = field(
        default_factory=lambda: {
            "missing": 0.04,
            "outlier": 0.005,
            "unit_error": 0.003,
            "duplicate": 0.01,
        }
    )
    # 四类两学年趋势标签的比例（简报 Step 4），按**人**精确配额分配
    trend_mix: dict[str, float] = field(
        default_factory=lambda: {
            "持续下滑": 0.20,
            "波动大": 0.15,
            "稳步提升": 0.25,
            "稳定": 0.40,
        }
    )
    # Plan 03 的参数位：实验班相对对照班的额外增益（分/采集间隔）。本计划里它只是被
    # 加到每个人的学年内漂移均值上——**没有实验班/对照班的区分**，那要等 Plan 03 的
    # 干预引擎落地。留位而不实现，是为了让 Plan 03 改的是数值而不是函数签名。
    intervention_effect: float = 0.0
    # 潜变量 latent_fitness 的均值 μ。简报 Step 3 要求「用二分法调 μ 使红/黄/绿比例
    # 逼近 target_layer_dist」，而红黄绿的判定要 Task 9 的分层引擎才算得出来，故本计划
    # 只把 μ 开成一个可调旋钮、缺省 0（即标准正态），二分法由 Task 9 落地。
    latent_mean: float = 0.0
    # 档内抖动（Ruling 54(a)，适用范围由 Ruling 57 收窄）：反查得到的原始值是档位端点，
    # 全落在端点上的数据一眼就是造的。开启后在**不改变所得档位**的前提下，于档带内向
    # 「更好」一侧按该列的测量分辨率均匀取值。关掉它就退回端点行为（旧行为），
    # 供 Task 9 的黄金用例对齐时用。
    jitter_within_band: bool = True
    # 表下溢出（Ruling 54(b)，选取方式由 Ruling 58 修正）：键格式 "<sex.value>:<item.value>"，
    # 值是**该性别学生中被标记的比例**（不是每条记录的抽样概率）。被标记者是该项所属桶
    # 潜变量最低的那一批，两学年六个时点的该项原始值一律落在 [0, 表内最低档) 内。
    # 第一批只对男生引体向上开启：国标最低档是 5 次（大三大四 6 次），而真实高校男生
    # 0–4 次占比很高；不生成这一段会让力量维度低尾被截断 → 校内 P25 偏高 → 力量短板
    # 识别偏少 → 红色层被系统性低估 → Task 9 的 20/45/35 分布断言难以达标。10% 是保守值，
    # Task 9 若仍不达标会调高它。未知键由 app.seed.fitness.sub_floor_marks 响亮拒绝。
    sub_floor_rate: dict[str, float] = field(
        default_factory=lambda: {"male:pull_up_or_sit_up": 0.10}
    )
