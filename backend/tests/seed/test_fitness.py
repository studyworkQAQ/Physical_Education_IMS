"""``app.seed.fitness`` 的专项测试：Ruling 56（上学年按上学年龄组查表）与
Ruling 54（档内抖动 + 表下溢出，含修正 Ruling 57/58）。

**为什么单独一个文件**：``test_generate.py`` 钉的是「整个数据集的形状与契约」
（编班、CSV、注入、入库、可复现），这里钉的是「单条体测记录的原始值是怎么算出来的」
——两者的被测单元不同，混在一个文件里会让 500 人全量配置的断言与逐项遍历评分表的
断言互相拖慢。

**为什么用零注入配置（:data:`CLEAN`）**：脏数据注入会改掉原始值而不回算 ``score_*``
列（生成期的量，有意为之），于是「原始值 ↔ 得分 ↔ 评分表」这三者的自洽只对未被注入
的单元格成立。本文件要量的是生成器本身的口径，把注入关掉后每一条记录都必须自洽，
断言因此可以是全称的而不必先过滤一遍 ``dirty_marks``。
"""
import re
from collections import Counter
from dataclasses import fields

import numpy as np
import pytest

from app.domain.indicators import (
    AGE_GROUPS,
    WEAKNESS_ITEMS,
    ScoredItem,
    Sex,
    age_group_of,
    raw_from_score,
    score_item,
    segment_thresholds,
)
from app.refdata import standard
from app.seed import fitness
from app.seed.config import SEMESTERS, SeedConfig, current_semester
from app.seed.fitness import (
    COLUMN_BY_ITEM,
    MEASURE_DECIMALS,
    jitter_raw,
    latent_profiles,
    make_fitness_tests,
    sub_floor_marks,
)
from app.seed.generate import build_dataset
from app.seed.population import make_population
from app.seed.sections import make_sections

NO_DIRTY = {"missing": 0.0, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0}
CLEAN = SeedConfig(students=120, weeks=16, seed=20250828, dirty=NO_DIRTY)
FULL = SeedConfig(students=500, weeks=16, seed=20250828)

PREVIOUS_YEAR = next(p.academic_year for p in SEMESTERS if not p.is_current)
CURRENT_YEAR = current_semester().academic_year
PULL_UP = ScoredItem.PULL_UP_OR_SIT_UP
MALE = Sex.MALE.value

# 档距明显大于测量分辨率的五处（Ruling 57 点名要修的症状）：抖动在这里必须真的生效。
WIDER_THAN_RESOLUTION: tuple[tuple[ScoredItem, str], ...] = (
    (ScoredItem.VITAL_CAPACITY, MALE),
    (ScoredItem.VITAL_CAPACITY, Sex.FEMALE.value),
    (ScoredItem.SIT_AND_REACH, MALE),
    (ScoredItem.SIT_AND_REACH, Sex.FEMALE.value),
    (ScoredItem.STANDING_JUMP, MALE),
    (ScoredItem.STANDING_JUMP, Sex.FEMALE.value),
    (ScoredItem.DISTANCE_RUN, MALE),
    (ScoredItem.DISTANCE_RUN, Sex.FEMALE.value),
    (PULL_UP, Sex.FEMALE.value),
)
DRAWS_PER_BAND = 50


def _bands(table, item, sex, age_group) -> list[int]:
    """该 (项, 性别, 龄组) 的全部官方档分，升序。

    从评分表本身推（阈值 → ``score_item``），不硬编码 10/20/…/100 这串魔数：表一改，
    遍历范围自动跟着走，而硬编码的那份会静默漏掉新增的档。
    """
    return sorted(
        {
            score_item(table, item, threshold, sex, age_group)
            for threshold in segment_thresholds(table, item, sex, age_group)
        }
    )


def _room_in_units(table, item, sex, age_group, endpoint, scale) -> int:
    """该档在「更好」一侧有多少个**分辨率格点**（含端点自身）。

    独立于实现推导：先找出相邻阈值里得分**更高**的那一个（它就是「更好」的方向，
    不需要知道该项是越大越好还是越小越好），再用两者的差换算成格点数。返回 1 意味着
    格点只有端点自己 → 无抖动空间；返回 0 意味着已是最好档。

    之所以不复用 ``jitter_raw`` 的内部算式，是因为一条自证的测试等于没测：本函数
    只依赖 ``segment_thresholds`` 与 ``score_item`` 两个公开纯函数。
    """
    thresholds = segment_thresholds(table, item, sex, age_group)
    index = thresholds.index(endpoint)
    band_score = score_item(table, item, endpoint, sex, age_group)
    better = [
        thresholds[i]
        for i in (index - 1, index + 1)
        if 0 <= i < len(thresholds)
        and score_item(table, item, thresholds[i], sex, age_group) > band_score
    ]
    if not better:
        return 0
    return abs(int(round((better[0] - endpoint) * scale)))


def _floor_raw(table, item, sex, age_group) -> int:
    return int(min(segment_thresholds(table, item, sex, age_group)))


def _age_group_of(record, pop) -> str:
    """某条记录**所属学年**的龄组（Ruling 56）：上学年小一岁。"""
    person = pop[record["student_id"]]
    return age_group_of(
        person["age"]
        if record["academic_year"] == CURRENT_YEAR
        else person["age"] - 1
    )


def _fitness_with_latents(cfg: SeedConfig) -> tuple[list[dict], list[dict], dict]:
    """按 :func:`app.seed.generate.build_dataset` 的顺序跑生成器，但**保留 latents**。

    ``build_dataset`` 不返回潜变量，而 Ruling 58 的选取规则与断言都要用它。随机数消耗
    顺序必须与 ``_organisation`` 一致（population → latents → sections），否则这里看到的
    记录与 ``build_dataset`` 产出的不是同一批，断言就变成了对另一份数据的空谈。
    """
    rng = np.random.default_rng(cfg.seed)
    population = make_population(cfg, rng)
    latents = latent_profiles(population, cfg, rng)
    make_sections(population, cfg, rng, latents)
    return make_fitness_tests(population, latents, cfg, rng), population, latents


def test_previous_year_records_use_the_previous_year_age_group():
    """Ruling 56：上学年的记录必须用**上学年**的年龄组查表。

    ``person["age"]`` 以当前学期开学日（``config.BIRTH_REFERENCE_DATE``）为参考日，
    故上学年该生小一岁。``age_group_of`` 的分界是 19/20，于是**只有 ``age == 20`` 的
    学生**真的跨线（上学年 19 岁 → 大一、大二组；本学年 20 岁 → 大三、大四组）；
    ``age == 18`` 的学生上学年 17 岁仍落在低龄组，不跨线。

    断言分两半，缺一不可：

    1. **正确性**：每个跨线学生的每条上学年记录、每个计分项，其 ``score_*`` 都等于
       用 ``age_group_of(age - 1)`` 那张表正查原始值的结果；
    2. **可分辨性**：这些记录里至少有一条，用 ``age_group_of(age)``（本学年的表）去查
       会得出**不同**的得分。没有这半条，上面那半条可能是在两张恰好相同的表之间空转
       ——那就证明不了任何东西。实测该比例见断言下的计数。
    """
    ds = build_dataset(CLEAN)
    pop = {p["student_id"]: p for p in ds["population"]}
    table = standard()
    previous_year_records = [
        r for r in ds["fitness"] if r["academic_year"] == PREVIOUS_YEAR
    ]
    crossers = [r for r in previous_year_records if pop[r["student_id"]]["age"] == 20]
    assert crossers, "120 人配置下 age==20 的学生不可能一个都没有，否则本测试空转"

    discriminative = 0
    for record in crossers:
        person = pop[record["student_id"]]
        sex = Sex(person["sex"])
        previous_group = age_group_of(person["age"] - 1)
        current_group = age_group_of(person["age"])
        assert previous_group != current_group
        for item in WEAKNESS_ITEMS:
            raw = record[COLUMN_BY_ITEM[item]]
            expected = score_item(table, item, raw, sex, previous_group)
            assert record[f"score_{item.value}"] == expected, (
                f"学号 {record['student_no']} 上学年 {item.value} 原始值 {raw}："
                f"记录里是 {record[f'score_{item.value}']} 分，"
                f"按上学年龄组 {previous_group} 查表应是 {expected} 分"
            )
            if score_item(table, item, raw, sex, current_group) != expected:
                discriminative += 1
    assert discriminative > 0, (
        "跨线学生的上学年记录在本学年龄组的表上得分全同——本测试无法分辨两张表，"
        "等于没测；请换一个跨线年龄或改用能分辨的项"
    )


# ---------------------------------------------------------------------------
# Ruling 54(a)：档内抖动（适用范围由 Ruling 57 收窄）
# ---------------------------------------------------------------------------


def test_jitter_never_crosses_a_score_band():
    """Ruling 54 的「逐档回验」：6 项 × 2 性别 × 2 龄组 × **全部官方档**，每档 50 次。

    回验放在测试里而不是运行时（简报 §4.2）：抖动在**整数单位**上取闭区间，从构造上
    就不可能跨档，于是运行时的「抽完再回验、失败重试」只会掩盖真缺陷——万一哪天
    ``MEASURE_DECIMALS`` 或评分表变了，重试会把不一致悄悄抹平，而这条测试会当场炸开。
    """
    table = standard()
    rng = np.random.default_rng(20250828)
    checked = 0
    for item in WEAKNESS_ITEMS:
        for sex in Sex:
            for age_group in AGE_GROUPS:
                for band in _bands(table, item, sex, age_group):
                    endpoint = raw_from_score(table, item, band, sex, age_group)
                    # 前提：端点本身就落在该档（Ruling 22 的精确往返），否则下面那条
                    # 断言会把「抖动跨档」与「端点本来就错档」两种失败混为一谈
                    assert score_item(table, item, endpoint, sex, age_group) == band
                    for _ in range(DRAWS_PER_BAND):
                        jittered = jitter_raw(table, item, endpoint, sex, age_group, rng)
                        assert score_item(table, item, jittered, sex, age_group) == band, (
                            f"{item.value}/{sex.value}/{age_group} 档 {band}：端点 "
                            f"{endpoint} 抖成 {jittered} 后跨档了"
                        )
                        checked += 1
    assert checked > 5000


def test_jittered_values_respect_measure_resolution():
    """抖动值必须落在该列的测量分辨率上（Ruling 57 明令禁止亚分辨率值）。

    用**整数单位**判定而不是浮点取模：``6.7 % 0.1`` 在浮点下是 ``0.09999…``，
    会把合法值判成非法、把非法值判成合法，这条测试自己就成了噪声源。
    """
    table = standard()
    rng = np.random.default_rng(7)
    for item in WEAKNESS_ITEMS:
        scale = 10 ** MEASURE_DECIMALS[item]
        for sex in Sex:
            for age_group in AGE_GROUPS:
                for band in _bands(table, item, sex, age_group):
                    endpoint = raw_from_score(table, item, band, sex, age_group)
                    for _ in range(DRAWS_PER_BAND):
                        value = jitter_raw(table, item, endpoint, sex, age_group, rng)
                        units = value * scale
                        assert abs(units - round(units)) <= 1e-6 * max(1.0, abs(units)), (
                            f"{item.value}/{sex.value}/{age_group}：{value} 不是 "
                            f"1/{scale} 的整数倍（该列分辨率是 {MEASURE_DECIMALS[item]} 位小数）"
                        )


def test_jitter_is_effective_where_the_band_is_wider_than_resolution():
    """逐档判定：**有格点空间就必须抖开，没有就必须原样返回端点**。

    遍历 6 项 × 2 性别 × 2 龄组 × 全部官方档，每档的空间由 :func:`_room_in_units`
    从评分表独立算出（格点数 = 与「更好」一侧相邻阈值的差 ÷ 分辨率）：

    * 空间 ≤ 1（只有端点自己）→ 抖动必须恒等于端点，且**不消耗随机数**；
    * 空间 ≥ 2 → 50 次抖动至少产生 2 个不同取值，否则「抖动」是个装饰品。

    实测（``segment_thresholds`` 全表扫描；fix round 3 复跑，逐组数字见下，**不被守卫**
    ——本条测试断言的是「窄档不抖、宽档会抖」，不是档距本身）：男生引体向上两个年级组
    各 15 档 / 14 个档距，**处处等于**分辨率 1 次，故它一处都不该抖；50 米跑**男生**只有
    最高 4 档（100/95/90/85）的档距是 0.1 s、其余 15 档是 0.2 s（两个年级组同为
    ``{0.1: 4, 0.2: 15}``）；**女生**是 ``{0.1: 2, 0.2: 15, 0.3: 2}``——即 0.1 s 的档距
    只有 **2** 个而不是 4 个，另有两档 0.3 s（本处此前只写了「女生另有两档 0.3 s」，
    漏了 0.1 s 那一半也随性别变）。女生引体（1 分钟仰卧起坐）是 ``{2.0: 17, 3.0: 2}``。
    0.2 / 0.3 s 都**是分辨率的两倍**，故那些档里
    7.2 s 这类读数是合法的真实测量、也确实该抖出来。这修正了 Ruling 57 那句
    「50 米跑的档距恰为 0.1 s（全部 4 组）」——它量的是**最小**档距，不是逐档档距。
    Ruling 57 的规范内容（**不得伪造亚分辨率精度**）由
    :func:`test_jittered_values_respect_measure_resolution` 与
    :func:`test_measure_decimals_match_the_official_reporting_resolution` 钉住。
    """
    table = standard()
    rng = np.random.default_rng(99)
    wide: Counter = Counter()
    narrow: Counter = Counter()
    for item in WEAKNESS_ITEMS:
        scale = 10 ** MEASURE_DECIMALS[item]
        for sex in Sex:
            for age_group in AGE_GROUPS:
                for band in _bands(table, item, sex, age_group):
                    endpoint = raw_from_score(table, item, band, sex, age_group)
                    room = _room_in_units(table, item, sex, age_group, endpoint, scale)
                    drawn = {
                        jitter_raw(table, item, endpoint, sex, age_group, rng)
                        for _ in range(DRAWS_PER_BAND)
                    }
                    if room <= 1:
                        assert drawn == {endpoint}, (
                            f"{item.value}/{sex.value}/{age_group} 档 {band}（端点 {endpoint}）"
                            f"只有 {room} 个格点，按设计不得抖动，实际得到 {sorted(drawn)}"
                        )
                        narrow[(item, sex.value)] += 1
                    else:
                        assert len(drawn) >= 2, (
                            f"{item.value}/{sex.value}/{age_group} 档 {band}（端点 {endpoint}）"
                            f"有 {room} 个格点，50 次抖动却只得到 {sorted(drawn)}"
                        )
                        assert all(
                            score_item(table, item, value, sex, age_group) == band
                            for value in drawn
                        )
                        wide[(item, sex.value)] += 1
    # Ruling 57 点名要修的五处（肺活量、坐位体前屈、立定跳远、耐力跑、女生次数）
    # 必须真的抖开了，否则本条测试是空转
    for item, sex_value in WIDER_THAN_RESOLUTION:
        assert wide[(item, sex_value)] > 0, f"{item.value}/{sex_value} 一处都没抖开"
    # 男生引体向上：档距处处 == 分辨率 1 次，故一处都不该抖（15 档 × 2 龄组全是窄档）
    assert wide[(PULL_UP, MALE)] == 0
    assert narrow[(PULL_UP, MALE)] == 15 * len(AGE_GROUPS)
    assert sum(wide.values()) > 100 and sum(narrow.values()) > 20


def test_measure_decimals_match_the_official_reporting_resolution():
    """``MEASURE_DECIMALS`` 是**上报口径**的事实，不是可调旋钮——逐字钉住。

    上面那条分辨率测试是从 ``MEASURE_DECIMALS`` 读 ``scale`` 的，所以有人把 50 米改成
    2 位小数（生成 6.73 s 这种国标评分表根本没有的精度）时它会**跟着一起通过**。本条
    是那个漏洞的唯一堵点：常量本身被字面钉死，改动必须是有意识的、且要在此处留下理由。
    """
    assert MEASURE_DECIMALS == {
        ScoredItem.VITAL_CAPACITY: 0,
        ScoredItem.SPRINT_50M: 1,
        ScoredItem.SIT_AND_REACH: 1,
        ScoredItem.STANDING_JUMP: 0,
        ScoredItem.PULL_UP_OR_SIT_UP: 0,
        ScoredItem.DISTANCE_RUN: 1,
    }
    assert set(MEASURE_DECIMALS) == set(WEAKNESS_ITEMS)



def test_full_dataset_raw_values_are_not_all_band_endpoints():
    """端到端回归：500 人数据集里肺活量的不同取值个数 **> 官方档位数**。

    这就是「一眼看出是造的」那个症状（所有肺活量都是 120 ml 的整数倍）。用零注入配置，
    因为 ``outlier`` 注入本身会造出非阈值读数（``max × 1.5``），留着它这条断言就可能被
    注入值蒙过去、而不是被抖动满足。
    """
    ds = build_dataset(SeedConfig(students=500, weeks=16, seed=20250828, dirty=NO_DIRTY))
    table = standard()
    endpoints = {
        threshold
        for sex in Sex
        for age_group in AGE_GROUPS
        for threshold in segment_thresholds(table, ScoredItem.VITAL_CAPACITY, sex, age_group)
    }
    values = {
        r["vital_capacity_ml"] for r in ds["fitness"] if r["vital_capacity_ml"] is not None
    }
    assert len(values) > len(endpoints), (
        f"肺活量只有 {len(values)} 个不同取值，而官方档位阈值有 {len(endpoints)} 个："
        f"数据里的每个读数都是档位端点"
    )
    assert len(values - endpoints) > 100


def test_jitter_can_be_disabled_by_config():
    """``jitter_within_band=False`` 必须是个真开关：所有原始值退回档位端点。

    关掉抖动同时也关掉表下溢出（``sub_floor_rate={}``），否则被标记男生的引体向上
    天然低于表内最低档，这条「全是端点」的断言就无法成立——两者是彼此独立的旋钮，
    本条只量前者。
    """
    cfg = SeedConfig(
        students=120,
        weeks=16,
        seed=20250828,
        dirty=NO_DIRTY,
        jitter_within_band=False,
        sub_floor_rate={},
    )
    records, population, _latents = _fitness_with_latents(cfg)
    pop = {p["student_id"]: p for p in population}
    table = standard()
    checked = 0
    for record in records:
        sex = Sex(pop[record["student_id"]]["sex"])
        age_group = _age_group_of(record, pop)
        for item in WEAKNESS_ITEMS:
            raw = record[COLUMN_BY_ITEM[item]]
            assert raw == raw_from_score(
                table, item, record[f"score_{item.value}"], sex, age_group
            ), f"{item.value} 的 {raw} 不是档位端点，但 jitter_within_band=False"
            checked += 1
    assert checked == len(records) * len(WEAKNESS_ITEMS)


# ---------------------------------------------------------------------------
# Ruling 54(b)：表下溢出（选取方式由 Ruling 58 修正）
# ---------------------------------------------------------------------------


def test_sub_floor_targets_the_weakest_students_by_latent():
    """Ruling 58 的核心性质：被标记者是**该桶潜变量最低的那一批**，不是随机挑的。

    单调性用最强的形式断言：被标记者里最大的 ``latent_strength`` 也不得超过未标记者里
    最小的那一个。按记录独立掷骰子（Ruling 54 原文的字面读法）会立刻违反它——那会造出
    ``latent_strength = +2`` 的壮汉一个引体向上都做不起，与本模块赖以存在的潜变量相关性
    直接冲突。
    """
    cfg = CLEAN
    _records, population, latents = _fitness_with_latents(cfg)
    marks = sub_floor_marks(population, latents, cfg)
    marked = marks[(MALE, PULL_UP)]
    males = [p["student_id"] for p in population if p["sex"] == MALE]
    expected = int(round(len(males) * cfg.sub_floor_rate[f"{MALE}:{PULL_UP.value}"]))
    assert len(males) == 66 and expected == 7
    assert len(marked) == expected
    assert marked <= set(males)
    unmarked = set(males) - marked
    assert max(latents[s]["strength"] for s in marked) <= min(
        latents[s]["strength"] for s in unmarked
    )
    # 默认配置只针对男生引体向上，不得顺手标记别的项或别的性别
    assert set(marks) == {(MALE, PULL_UP)}


def test_sub_floor_values_are_below_the_table_floor():
    """被标记者的每条记录都落在 ``[0, 表内最低档)``，且得分由 ``score_item`` 夹取得出。

    **地板效应（Task 8/9 前向约束）**：被标记者该项两学年六个时点的得分都等于底档分，
    故该项的学年间趋势恒为 0。这不是缺陷，是「一个人做不起 5 个引体向上」这件事本身的
    持久性——但它意味着趋势判定与黄金用例必须容忍这一项恒为零。
    """
    cfg = CLEAN
    records, population, latents = _fitness_with_latents(cfg)
    pop = {p["student_id"]: p for p in population}
    table = standard()
    marks = sub_floor_marks(population, latents, cfg)
    marked = marks[(MALE, PULL_UP)]
    column = COLUMN_BY_ITEM[PULL_UP]

    per_student: dict[int, list[bool]] = {}
    for record in records:
        person = pop[record["student_id"]]
        sex = Sex(person["sex"])
        age_group = _age_group_of(record, pop)
        floor_raw = _floor_raw(table, PULL_UP, sex, age_group)
        value = record[column]
        if record["student_id"] in marked:
            assert sex is Sex.MALE
            assert value < floor_raw and value >= 0, (
                f"学号 {record['student_no']} 被标记为表下溢出，"
                f"但 {column}={value}（该龄组表内最低档是 {floor_raw}）"
            )
            assert float(value).is_integer(), f"{column}={value} 不是整数次"
            bottom = score_item(table, PULL_UP, float(floor_raw), sex, age_group)
            assert record[f"score_{PULL_UP.value}"] == bottom == score_item(
                table, PULL_UP, value, sex, age_group
            )
        else:
            assert value >= floor_raw, (
                f"学号 {record['student_no']} 未被标记，{column}={value} 却低于"
                f"表内最低档 {floor_raw}"
            )
        per_student.setdefault(record["student_id"], []).append(value < floor_raw)

    # 标记是**持久的**：被标记者六个时点全在表下，未标记者六条全在表上。
    # 若逐条掷骰子，同一个人会出现 week1 做 12 个、week8 做 0 个。
    assert {sid for sid, flags in per_student.items() if all(flags)} == marked
    assert {sid for sid, flags in per_student.items() if any(flags)} == marked
    assert all(len(flags) == len(SEMESTERS) * 3 for flags in per_student.values())
    # 逐条重抽体现测量波动：7 人 × 6 条不可能全抽到同一个次数
    marked_values = [
        record[column]
        for record in records
        if record["student_id"] in marked
    ]
    assert len(set(marked_values)) >= 3, f"表下取值毫无波动：{Counter(marked_values)}"


def test_sub_floor_rate_rejects_unknown_keys():
    """未知键必须响亮报错，并附上完整合法键清单。

    静默忽略等于「配了但没生效」，而这条配置的全部意义就是影响 Task 9 的分层分布：
    一个拼错的键会让红色层的低尾悄无声息地回到被截断的状态，谁也看不出配置没生效。

    合法键取 ``Sex`` × **六个短板判定项**（不含 BMI）：BMI 的档位序列非单调、根本不走
    反查，``male:bmi`` 会是一个永远不生效的键，接受它就等于留下第二个静默失效的入口。
    """
    legal = [f"{sex.value}:{item.value}" for sex in Sex for item in WEAKNESS_ITEMS]
    for bad in ({"male:no_such_item": 0.1}, {"female:bmi": 0.1}, {"bmi:male": 0.1}):
        cfg = SeedConfig(students=40, weeks=16, seed=3, dirty=NO_DIRTY, sub_floor_rate=bad)
        with pytest.raises(ValueError) as excinfo:
            sub_floor_marks([], {}, cfg)
        message = str(excinfo.value)
        assert next(iter(bad)) in message
        for key in legal:
            assert key in message, f"异常消息里没有合法键 {key}：{message}"


def test_sub_floor_can_be_disabled():
    """``sub_floor_rate={}`` 时没有任何记录低于表内最低档（六项 × 两性别全查）。"""
    cfg = SeedConfig(students=120, weeks=16, seed=20250828, dirty=NO_DIRTY, sub_floor_rate={})
    records, population, _latents = _fitness_with_latents(cfg)
    pop = {p["student_id"]: p for p in population}
    table = standard()
    assert sub_floor_marks(population, _latents, cfg) == {}
    for record in records:
        sex = Sex(pop[record["student_id"]]["sex"])
        age_group = _age_group_of(record, pop)
        for item in WEAKNESS_ITEMS:
            floor_raw = min(segment_thresholds(table, item, sex, age_group))
            assert record[COLUMN_BY_ITEM[item]] >= floor_raw, (
                f"{item.value}/{sex.value}/{age_group} 的 {record[COLUMN_BY_ITEM[item]]} "
                f"低于表内最低档 {floor_raw}，但 sub_floor_rate 是空的"
            )


# ---------------------------------------------------------------------------
# 计划 Step 4 第 4 步：「落档 → 重算 → 校正」循环必须在轮数上限内收敛
# ---------------------------------------------------------------------------


def test_trend_correction_loop_settles_every_student_within_the_round_cap(monkeypatch):
    """校正循环的三条性质：**每人都收敛**、**轮数不破上限**、**循环不是死代码**。

    国标 60 分以下档距是 10 分，就低取档单项最多吃掉 9 分、六项加权后最多约 7.65 分——
    与「稳定」类的 ±5 窄带同量级，靠留余量躲不过去，必须落档后精确重算并校正
    （计划 Step 4 第 4 步）。超限 ``RuntimeError`` 响亮失败：真发生的话本测试会因为
    ``build_dataset`` 抛异常而直接炸开，故「RuntimeError 次数为 0」由「测试通过」隐含。

    ``triggered > 0`` 是**反空转守卫**：它证明量化损失确实会把一部分学生推出判据、
    循环真的在工作。若哪天它变成 0，说明这个循环已是死代码，应当删掉而不是留着装饰。
    """
    captured: dict[str, int] = {}
    original = fitness._trend_prev_targets

    def wrapper(*args, **kwargs):
        prev_targets, stats = original(*args, **kwargs)
        captured.update(stats)
        return prev_targets, stats

    monkeypatch.setattr(fitness, "_trend_prev_targets", wrapper)
    _fitness_with_latents(FULL)
    assert captured["students"] == FULL.students == 500
    assert captured["max_rounds"] <= fitness.CORRECTION_MAX_ROUNDS
    assert captured["triggered"] > 0, "校正循环一轮都没触发：它已经是死代码，应删除"
    assert captured["triggered"] <= captured["students"]


# ---------------------------------------------------------------------------
# 零宽窗口的退化行为：``max(0.0, …)`` 钳位把窗口塌成单点，而**不是**判不可行
# ---------------------------------------------------------------------------


def test_zero_room_collapses_the_stable_window_to_a_single_point():
    """``room`` 不够时窗口**塌成单点 ``(b, b)``**，而不是 ``None``（判不可行）。

    这条钉住的是**一个刻意的设计决定**，不是一个凑巧的行为：
    ``_delta_target_windows`` 里那句 ``magnitude = w_free * max(0.0, room − jitter −
    CORRECTION_RESERVE) / 100`` 的 ``max(0.0, …)`` 钳位，在 ``room ≤ jitter +
    CORRECTION_RESERVE``（稳定类即 ``room ≤ 12``）时把 ``magnitude`` 压成 0，于是
    ``lo = hi = b``——该生的 ``Delta_target`` 不再是一个抽样区间而是一个确定值，且**一分
    校正预留都没拿到**。它的安全性因此**全部押在 :func:`_settle_prev_targets` 的校正循环
    推得动上**（方案 a：接受现状）。缺省 500 人配置下这批人有 **133** 个（占稳定类可行的
    489 人的 27%），其中 **88** 个真的被标为「稳定」；账目与风险方向见
    ``app/seed/fitness.py`` 里 ``magnitude`` 上方那段注释。

    **它保护的是「方案 a」这个裁定**。复审建议的方案 b（把钳位改成「余量为负即判不可行」，
    让 :data:`CORRECTION_RESERVE` 名实相符）已被否决，代价是明确的：稳定类可行池立刻少
    133 人 → :func:`_trend_labels` 的洗牌与 ``shuffled.sort`` 的让位顺序全变 → 抽到的
    ``Delta_target`` 与零和抖动全部平移 → **三个 CSV 的字节全部作废**（取证哈希
    ``498AA3256678B01A`` / ``1234025C05843B27`` / ``835A98FCC0779B51`` 一并失效），而
    收益只是让一个常量名实相符。真要改，须与 Task 9（调 ``jitter`` /
    ``CORRECTION_STEP`` / 评分表）一起排期、一起重做可复现性取证。

    **没有这条测试，那次改动会静默通过全部既有断言**：可行池缩水只会让「稳定」的配额从
    别处补上，四类比例仍是精确配额、CSV 仍自洽，只有字节变了。

    输入取 ``curr`` 六项全 100、``bmi_delta = 0``：``head_up = min(100 − curr) = 0`` ⟹
    ``room = 0``（钳位到最狠的那一格），且 ``b = 0`` ⟹ 单点必为 ``(0.0, 0.0)``。同时钉住
    另三类的对照形状——「波动大」要 ``max(curr) ≤ 84`` 故 ``None``、「持续下滑」钳位后
    ``lo > hi`` 故 ``None``、「稳步提升」的 ``room = head_down = 100`` 仍宽故可行：**方案 b
    之下这名学生的「稳定」窗口会变成 ``None``，而余下三类里只有「稳步提升」装得下他**，
    于是他会把稳定池的配额顶掉或直接触发 ``_trend_labels`` 的响亮 ``ValueError``。
    """
    curr = {item: 100 for item in WEAKNESS_ITEMS}
    windows = fitness._delta_target_windows(curr, 0, WEAKNESS_ITEMS)

    assert windows["稳定"] is not None, (
        "「稳定」窗口被判成不可行了：max(0.0, …) 钳位被改成了「余量为负即判不可行」（方案 b）。"
        "后果是稳定类可行池少 133 人、洗牌与配额全变、三个 CSV 的字节与已取证哈希全部作废——"
        "这不是一次等价重构，须与 Task 9 一起排期。"
    )
    assert windows["稳定"] == (0.0, 0.0), windows["稳定"]
    # 单点就是 b（这里 b = 0）：钳位吃掉的是 magnitude，不是窗口的位置
    assert windows["波动大"] is None and windows["持续下滑"] is None
    assert windows["稳步提升"] is not None


# ---------------------------------------------------------------------------
# 四条「响亮失败」守卫的自证测试（评审 Minor-4，fix round 3 必修）
#
# 上一条测试的 docstring 说「RuntimeError 次数为 0 由测试通过隐含」——那只证明**当次
# 数据**没有触发守卫，不证明守卫还在。若有人把 ``raise`` 改成 ``return prev_targets, rounds``
# （静默放行），或把 ``if len(pool) < need`` 改成 ``pool[:need]`` + 余下改标签，280 条测试
# 仍会全绿：兜底的 oracle 测试只在当次数据上比对，而静默放行恰好会让当次数据自洽地错。
# Ruling 65/70 的全部意义就是「响亮失败而不是静默改标签」，故这四条必须各自被测试打到。
# ---------------------------------------------------------------------------


def _synthetic_info(student_id: int, curr_value: int, bmi_score: int = 80) -> dict:
    """``_settle_prev_targets`` 的**合成** ``info``：六项同分、BMI 两学年同档（故 ``b = 0``）。

    手工构造而不是靠调 ``SeedConfig`` 去撞：撞出来的失败既不可复现，也说不清是哪一个判据
    放的行，而守卫测试要钉的恰恰是「在这一行、因为这一个条件、抛这一个异常、消息里有这些
    数字」。形状与 :func:`app.seed.fitness._trend_inputs` 产出的 bundle 逐项对齐。
    """
    return {
        "student_id": student_id,
        "sex": Sex.MALE,
        "prev_group": AGE_GROUPS[0],
        "curr": {item: curr_value for item in WEAKNESS_ITEMS},
        "free": WEAKNESS_ITEMS,
        "fixed_prev": {},
        "curr_bmi": bmi_score,
        "prev_bmi": bmi_score,
        "windows": {},
    }


@pytest.mark.parametrize(
    "label,curr_value,misjudged",
    [("稳步提升", 10, "稳定"), ("持续下滑", 100, "稳定")],
    ids=["表底-稳步提升", "表顶-持续下滑"],
)
def test_correction_loop_raises_when_no_item_can_be_moved_any_further(label, curr_value, misjudged):
    """``_settle_prev_targets`` 的「趋势校正推不动了」守卫：``_correction_move`` 返回 ``None``
    时必须 ``RuntimeError``。

    （不写 ``fitness.py`` 的行号：加一段注释就会让它过期。钉住它的是消息开头那句
    「趋势校正推不动了」——它把这条与「N 轮仍未达判据」那条区分开。）

    两个方向各钉一半，都落在评分表的端点档上：

    * **表底**（``curr`` 六项全 10）：``prev`` 已是表内最低档，``direction = -1`` 一步也
      走不了，而「稳步提升」恰恰要求把 ``prev`` 再压低；
    * **表顶**（``curr`` 六项全 100）：对称的另一半，「持续下滑」要求把 ``prev`` 抬到 100
      以上。

    两者都是可行域筛选本该挡住的输入（表底装不下提升、表顶装不下下滑），守卫的存在就是
    为了让「筛选放行了一个装不下该标签的学生」当场炸开，而不是产出一个 ``trend_label``
    与数据不符的学生——那是 Task 8 的对账基准、也是规则 Y4 的唯一输入。

    消息必须含**学生标识**与**迭代轮数**（Ruling 65）：没有它们，看到这条异常的人无法
    知道是哪个学生、第几轮、被判成了什么。
    """
    info = _synthetic_info(9001, curr_value)
    deltas = {item: 0 for item in WEAKNESS_ITEMS}
    with pytest.raises(RuntimeError) as excinfo:
        fitness._settle_prev_targets(label, info, deltas, standard(), {}, {})
    message = str(excinfo.value)
    # 「推不动了」把这条与「N 轮仍未达判据」那条区分开：两条都是 RuntimeError，
    # 只断言类型的话，守卫被换成另一条也照样绿。
    assert "趋势校正推不动了" in message
    assert "student_id=9001" in message
    assert f"标签「{label}」" in message
    assert "第 0 轮后" in message
    assert "Delta'=0" in message
    assert f"被判成「{misjudged}」" in message
    assert "端点档" in message


def test_correction_loop_raises_when_the_round_cap_is_exhausted():
    """``_settle_prev_targets`` 的「N 轮仍未达判据」守卫：跑满 ``CORRECTION_MAX_ROUNDS``
    仍不达标时必须 ``RuntimeError``。

    合成输入：``curr`` 六项全 100、标签「波动大」、``delta_i`` 三正三负各 ±12。负号三项的
    ``prev_target = 112`` 被 clip 回 100 → ``prev = 100`` → ``delta_i' = 0``，而 ``delta_i = 0``
    两边都不计入（spec §14 #23）→ 永远只有 3 正 0 负，凑不出「恰好 3 正 3 负」。同时
    ``_correction_move`` 的波动大分支推的是**幅值最大**那一项（一个正号项）、方向 ``-1``，
    每轮把它的 ``prev`` 再压低一档 → ``|delta'|`` 越来越大、``Delta'`` 越来越正，判据被推得
    更远，8 轮后必然撞上限。

    这条与上一条一起证明上限**不是装饰**：真有推不动的学生时，它给出的是异常而不是一个
    静默的错误标签。
    """
    items = WEAKNESS_ITEMS
    deltas = {items[0]: 12, items[1]: 12, items[2]: 12,
              items[3]: -12, items[4]: -12, items[5]: -12}
    with pytest.raises(RuntimeError) as excinfo:
        fitness._settle_prev_targets("波动大", _synthetic_info(9004, 100), deltas, standard(), {}, {})
    message = str(excinfo.value)
    assert "轮仍未达判据" in message
    assert f"{fitness.CORRECTION_MAX_ROUNDS} 轮" in message  # 迭代轮数（Ruling 65）
    assert "student_id=9004" in message                      # 学生标识（Ruling 65）
    assert "标签「波动大」" in message
    assert "Delta'=" in message and "被判成「" in message
    assert "不静默放行" in message


# 三种可行域形状，只为喂 ``_trend_labels``：它只读 ``bundle[sid]["windows"]``。
DECLINING_OK = {"波动大": None, "持续下滑": (0.0, 0.0), "稳步提升": None, "稳定": (0.0, 0.0)}
STABLE_ONLY = {"波动大": None, "持续下滑": None, "稳步提升": None, "稳定": (0.0, 0.0)}
ALL_INFEASIBLE = {"波动大": None, "持续下滑": None, "稳步提升": None, "稳定": None}


def _bundle(*windows_per_sid: dict) -> dict[int, dict]:
    """把若干「窗口形状」按 ``student_id = 1..n`` 包成 ``_trend_labels`` 要的 bundle。"""
    return {
        sid: {"windows": windows}
        for sid, windows in enumerate(windows_per_sid, start=1)
    }


def test_trend_labels_raises_when_a_feasible_pool_is_short():
    """``_trend_labels`` 的「可行池不足」守卫：池装不下配额时必须 ``ValueError``，并报出
    **需要数与实有数**。

    Ruling 65 明写「池不足响亮报错，不得静默改标签」：``trend_label`` 是交给 Task 8 交叉
    验证、并驱动分层规则 Y4 的**真值**，静默改标签等于把真值造假。消息里的两个数字是定位
    手段——没有它们，看到这条异常的人得自己重跑一遍可行域筛选才知道差多少人。

    合成 ``bundle``：4 人里只有 1 人的「持续下滑」窗口非 ``None``，而配额要 2 人。
    """
    cfg = SeedConfig(
        students=4, weeks=16, seed=7,
        trend_mix={"持续下滑": 0.5, "波动大": 0.0, "稳步提升": 0.0, "稳定": 0.5},
    )
    population = [{"student_id": sid} for sid in (1, 2, 3, 4)]
    bundle = _bundle(DECLINING_OK, STABLE_ONLY, STABLE_ONLY, STABLE_ONLY)
    with pytest.raises(ValueError) as excinfo:
        fitness._trend_labels(population, cfg, np.random.default_rng(cfg.seed), bundle)
    message = str(excinfo.value)
    assert "可行池不足" in message and "「持续下滑」" in message
    assert "需要 2 人" in message and "实有 1 人" in message  # Ruling 65 要求的两个数字
    assert "全体 4 人" in message
    assert "不得静默改标签" in message


def test_trend_labels_raises_when_the_residual_holds_a_stable_infeasible_student():
    """``_trend_labels`` 的「余下有稳定不可行者」守卫：让完了仍然不够时必须 ``ValueError``。

    「稳定」拿余下全部（计划 Step 4），所以前三类挑人时**优先挑稳定不可行的**
    （``_trend_labels`` 里那句 ``shuffled.sort(key=…windows["稳定"] is None…)``）。这条守卫
    拦的是「让完了仍然不够」：此时唯一的出路是改标签，而改标签就是造假，故响亮失败。
    合成 ``bundle``：sid 4 四类全不可行，前三类配额只有 1 个（给了 sid 1），于是余下 3 人里
    带着一个构造不出来的稳定标签。

    消息同时报出**需要数**（稳定配额）、**实有数**（余下人数与其中不可行人数）与**是哪几个
    ``student_id``**——最后一项是这条消息独有的，上一条「可行池不足」报的是池大小。
    """
    cfg = SeedConfig(
        students=4, weeks=16, seed=7,
        trend_mix={"持续下滑": 0.25, "波动大": 0.0, "稳步提升": 0.0, "稳定": 0.75},
    )
    population = [{"student_id": sid} for sid in (1, 2, 3, 4)]
    bundle = _bundle(DECLINING_OK, STABLE_ONLY, STABLE_ONLY, ALL_INFEASIBLE)
    with pytest.raises(ValueError) as excinfo:
        fitness._trend_labels(population, cfg, np.random.default_rng(cfg.seed), bundle)
    message = str(excinfo.value)
    assert "余下 3 人" in message and "配额 3" in message
    assert "1 人在该类可行域之外" in message
    assert "[4]" in message
    assert "不得静默改标签" in message


def test_build_dataset_raises_instead_of_silently_generating_fewer_students():
    """同一条池不足守卫走**真实路径**：``build_dataset`` 整体炸开，而不是静默少生成几个人。

    上面两条用合成 ``bundle``，钉的是「守卫在这一行、因这个条件抛」；这一条钉的是「真实
    失效路径上它确实会被走到」——否则守卫可能只存在于一个谁也到不了的分支里（这正是评审
    Minor-4 的指控）。``持续下滑`` 0.9 在 120 人上要 108 人，而可行池实测只有 54 人
    （Ruling 79：``持续下滑`` 是四类里余量最紧的一类，1.52×）。

    **静默少生成**的后果不是「数据少一点」：配额之和必须等于 ``students``，少一个人就会在
    编班时凭空消失且不报错——``allocate_quota`` 的 docstring 正是为此才拒绝比例之和 ≠ 1。
    """
    cfg = SeedConfig(
        students=120, weeks=16, seed=20250828,
        trend_mix={"持续下滑": 0.9, "波动大": 0.0, "稳步提升": 0.0, "稳定": 0.1},
    )
    with pytest.raises(ValueError) as excinfo:
        build_dataset(cfg)
    message = str(excinfo.value)
    assert "可行池不足" in message and "「持续下滑」" in message
    assert "需要 108 人" in message  # 由 trend_mix × students 精确推出，不随筛选判据变
    matched = re.search(r"实有 (\d+) 人", message)
    assert matched, f"消息没有报出实有数：{message}"
    assert 0 < int(matched.group(1)) < 108, message


# ---------------------------------------------------------------------------
# Ruling 66：latent_sd 必须是真旋钮
# ---------------------------------------------------------------------------


def _latent_spread(latent_sd: float, students: int = 500) -> float:
    """给定 ``latent_sd`` 时 ``latent_fitness`` 的**经验**标准差（ddof=1）。"""
    cfg = SeedConfig(students=students, weeks=16, seed=20250828, latent_sd=latent_sd)
    rng = np.random.default_rng(cfg.seed)
    population = make_population(cfg, rng)
    latents = latent_profiles(population, cfg, rng)
    return float(np.std([profile["fitness"] for profile in latents.values()], ddof=1))


def test_latent_sd_is_a_config_field_defaulting_to_one():
    """``SeedConfig`` 必须真的有 ``latent_sd`` 这个字段，且缺省 1.0（Ruling 66）。

    上一轮 ``progress.md:619`` 写「只开 ``latent_mean``/``latent_sd`` 参数位……正确」，
    而 ``latent_sd`` 从来没被开出来（``fitness.py`` 里 σ 硬编码成字面量 ``1.0``）——
    评审 M2 用 ``dataclasses.fields`` 与 ``git grep`` 双重取证。本条把「字段存在」钉死，
    免得同一句错话第三次被写进账本。
    """
    assert {field.name for field in fields(SeedConfig)} >= {"latent_mean", "latent_sd"}
    assert SeedConfig().latent_sd == 1.0


def test_latent_sd_scales_the_empirical_spread_of_latent_fitness():
    """``latent_sd`` 改变时，潜变量的**经验标准差**随之改变。

    量的是从生成结果算回来的经验 sd，不是配置值本身（读配置跟配置比是自证）。
    500 人下正态样本 sd 的标准误约 ``sd / sqrt(2n) ≈ 0.032``，故 ``±0.2`` 的带宽约容纳
    6 个标准误：既不会因换种子翻车，也宽不到能吸收「σ 根本没接上线」——那种情况下
    ``latent_sd=2.0`` 的经验 sd 仍会是 1.0，落在 ``[1.8, 2.2]`` 之外。

    **本轮不做二分法调参**（那是 Task 9）：这里只证明旋钮接上了、方向对。
    """
    baseline = _latent_spread(1.0)
    assert 0.9 <= baseline <= 1.1, f"缺省 σ=1.0 时经验 sd 是 {baseline}"
    doubled = _latent_spread(2.0)
    assert 1.8 <= doubled <= 2.2, f"σ=2.0 时经验 sd 是 {doubled}，旋钮没接上或被别处钳住"
    halved = _latent_spread(0.5)
    assert 0.4 <= halved <= 0.6, f"σ=0.5 时经验 sd 是 {halved}"
    # 三个点连起来必须是单调的：只测一个点可能被某个恰好等值的巧合蒙过去
    assert halved < baseline < doubled


def test_latent_sd_propagates_through_the_bucket_loadings():
    """σ 必须传到三个**桶潜变量**上，而不只是 ``latent_fitness`` 自己。

    ``endurance = 0.8·fitness + ε(sd 0.6)``，故 ``sd(endurance) = sqrt(0.8²·σ² + 0.6²)``：
    σ=1 时是 1.0（实测约 1.00），σ=2 时是 ``sqrt(2.56 + 0.36) = 1.71``。断言用这个
    **手算的理论值** ±0.15（500 人下抽样波动约 0.05，留三倍余量），而不是拿 σ=2 的经验值
    去跟 σ=1 的经验值比大小——后者只能证明「变大了」，证明不了「按载荷公式变的」。
    这条同时挡住一种真实的失效模式：有人把 σ 只接到 ``fitness`` 上，桶潜变量仍用旧的
    硬编码 1.0 生成，于是六项得分的分布纹丝不动、Task 9 调 σ 调了个空。
    """
    def spreads(latent_sd: float) -> dict[str, float]:
        cfg = SeedConfig(students=500, weeks=16, seed=20250828, latent_sd=latent_sd)
        rng = np.random.default_rng(cfg.seed)
        population = make_population(cfg, rng)
        latents = latent_profiles(population, cfg, rng)
        return {
            name: float(np.std([profile[name] for profile in latents.values()], ddof=1))
            for name in ("endurance", "strength", "speedflex")
        }

    at_one = spreads(1.0)
    at_two = spreads(2.0)
    # 理论 sd：sqrt(载荷² · σ² + 残差 sd²)，载荷与残差 sd 见 fitness.LATENT_LOADINGS
    theory_two = {"endurance": 1.7088, "strength": 1.5524, "speedflex": 1.4422}
    for name, expected in theory_two.items():
        assert abs(at_two[name] - expected) < 0.15, (
            f"σ=2.0 时 {name} 的经验 sd 是 {at_two[name]:.4f}，"
            f"按载荷公式应为 {expected:.4f}（σ=1.0 时实测 {at_one[name]:.4f}）"
        )
    # sqrt(0.8²·1 + 0.6²) = 1.0、sqrt(0.7² + 0.7²) = 0.9899、sqrt(0.6² + 0.8²) = 1.0
    assert abs(at_one["endurance"] - 1.0) < 0.15
    assert abs(at_one["strength"] - 0.9899) < 0.15
    assert abs(at_one["speedflex"] - 1.0) < 0.15

