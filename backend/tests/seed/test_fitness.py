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
from collections import Counter

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

    实测（``segment_thresholds`` 全表扫描）：男生引体向上的 14 个档距**处处等于**
    分辨率 1 次，故它一处都不该抖；50 米跑则只有最高 4 档（100/95/90/85）的档距是
    0.1 s，其余 15 档是 0.2 s（女生另有两档 0.3 s），**是分辨率的两倍**，故那些档里
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

