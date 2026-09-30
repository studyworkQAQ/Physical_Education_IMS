"""派生指标的行为约束：趋势四分类、短板与主导桶、体成分异常、国标总分口径（spec §6.3 / §6.4）。

**age_group 一律用 AGE_GROUPS 的年级组名，不得写 "18-19" 这种年龄段字面量**
（Ruling 85，与 Task 7 同一个坑）：国标大学评分表按年级组组织，``"18-19"`` 在真表里
是不存在的键，写它会让测试与生产路径脱钩——测试自造一套假分组、真数据一律 KeyError。
"""
import inspect

import pytest

from app.domain.derive import (
    Trend, classify_trend, derive, find_weaknesses, flag_body_comp, national_total,
)
from app.domain.percentile import PercentileRow
from app.domain.indicators import (
    AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, score_item,
)
from app.refdata import standard
from app.seed.config import SEMESTERS, SeedConfig
from app.seed.fitness import COLUMN_BY_ITEM
from app.seed.generate import build_dataset

# 计划 Step 1 用 ``ScoredItem as I`` 导入，但同一段代码里的 ``total()`` 助手写的是
# ``ScoredItem.BMI``——两个名字都要能用，故导入真名再起别名（见报告关切）。
I = ScoredItem

LOWER_GRADE = AGE_GROUPS[0]        # "大一、大二"
UPPER_GRADE = AGE_GROUPS[1]        # "大三、大四"


def snap(item, p25):
    return PercentileRow(item, Sex.MALE, LOWER_GRADE, p25-20, p25-10, p25, p25+15, p25+25, 100, "school")


def snap_group(item, p25, age_group):
    """同 :func:`snap`，但年级组可变。

    Ruling 103 的多组快照测试需要**两个年级组同时躺在一张快照里**，才能证明
    ``age_group`` 参数真的在挑判定线（``snap`` 把年级组写死成 ``LOWER_GRADE``）。
    """
    return PercentileRow(item, Sex.MALE, age_group, p25-20, p25-10, p25, p25+15, p25+25, 100, "school")


ALL6 = list(WEAKNESS_ITEMS)        # 从 domain 常量来，不手抄第二份清单
SNAP = [snap(i, 60) for i in ALL6]

# Ruling 117-C2：**含 BMI 判定线**的快照。SNAP 只有 6 行，于是「BMI 不在 find_weaknesses
# 的循环里」与「BMI 在循环里但 lookup_p25 查不到判定线」两种实现**行为不可区分**——
# 原 test_bmi_never_counted_as_weakness 因此是空转测试（复审把遍历对象改成
# tuple(ScoredItem) 后 369 条全绿）。**刻意不改 SNAP 本身**：其余测试依赖它恰好 6 行
# （valid_count == 6 的断言、以及「无 BMI 判定线」这个前提）。
SNAP_WITH_BMI = SNAP + [snap(I.BMI, 60)]

# --- 趋势四标签（spec §6.3；求值顺序：波动大 → 持续下滑 → 稳步提升 → 稳定，Ruling 64a）---
def base_scores(v=75):
    return {i: v for i in ALL6}


def total(scores6, bmi=75):
    """测试内的便捷包装：补一个 BMI 得分后交给**生产实现** ``national_total``。

    **不得手写总分字面量、也不得在这里重算加权求和**：口径是 7 项按 ITEM_WEIGHTS 加权，
    手写一个 450 这类数会把「6 项之和（0–600）」与「国标总分（0–100）」两个口径混在一起，
    而 spec §6.3 的 ±5 分阈值只在后者上有意义（Ruling 63）。
    """
    return national_total({**scores6, ScoredItem.BMI: bmi})


def test_trend_declining_by_total_drop_only():
    # 只有 2 项下降 ≥5（不满足第二分支的「≥3 项」），加权总分降 5.8 ≥ 5：
    # 必须由第一分支触发。d = (20×−10, 20×−10, 15×−4, 10×−4, 10×−4, 10×−4) → −580/100
    prev = base_scores(75); curr = dict(prev)
    curr[I.SPRINT_50M] = 65; curr[I.DISTANCE_RUN] = 65
    for i in (I.VITAL_CAPACITY, I.SIT_AND_REACH, I.STANDING_JUMP, I.PULL_UP_OR_SIT_UP):
        curr[i] = 71
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.DECLINING


def test_trend_declining_by_three_items_dropping_five():
    # 加权总分只降 0.95（< 5），必须由「≥3 项单项下降 ≥5 分」这一分支触发（Ruling 64b）。
    # 三项 w=10 各降 5、三项 w=15/20/20 各升 1 → (−150 + 55)/100 = −0.95
    prev = base_scores(75); curr = dict(prev)
    for i in (I.SIT_AND_REACH, I.STANDING_JUMP, I.PULL_UP_OR_SIT_UP):
        curr[i] = 70
    for i in (I.VITAL_CAPACITY, I.SPRINT_50M, I.DISTANCE_RUN):
        curr[i] = 76
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.DECLINING


def test_two_items_dropping_five_below_total_threshold_is_stable():
    # 仅 2 项各降 5、总分降 0.35：DECLINING 两个分支都不满足，max|d| = 5 < 10 故也非 VOLATILE
    prev = base_scores(75); curr = dict(prev)
    curr[I.SIT_AND_REACH] = 70; curr[I.STANDING_JUMP] = 70
    for i in (I.VITAL_CAPACITY, I.SPRINT_50M, I.DISTANCE_RUN, I.PULL_UP_OR_SIT_UP):
        curr[i] = 76
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.STABLE


def test_trend_volatile():
    # 恰好 3 正 3 负（min(#{>0}, #{<0}) = 3）且 max|d| = 13 ≥ 10
    prev = base_scores(75); curr = dict(prev)
    curr[I.VITAL_CAPACITY] = 88; curr[I.SIT_AND_REACH] = 87; curr[I.STANDING_JUMP] = 86
    curr[I.SPRINT_50M] = 62; curr[I.PULL_UP_OR_SIT_UP] = 63; curr[I.DISTANCE_RUN] = 64
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.VOLATILE


def test_volatile_outranks_declining():
    # Ruling 64a 的**唯一**守卫：3 项各降 12（满足 DECLINING 第二分支）+ 3 项各升 10，
    # 总分只降 2.5。若行序写反成「持续下滑 → 波动大」，本条会返回 DECLINING。
    prev = base_scores(75); curr = dict(prev)
    curr[I.SPRINT_50M] = 63; curr[I.DISTANCE_RUN] = 63; curr[I.PULL_UP_OR_SIT_UP] = 63
    curr[I.VITAL_CAPACITY] = 85; curr[I.SIT_AND_REACH] = 85; curr[I.STANDING_JUMP] = 85
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.VOLATILE


def test_one_zero_delta_makes_volatile_unreachable():
    # spec §6.3：delta_i = 0 既不计正也不计负，故 5 项非零时 min(#{>0}, #{<0}) ≤ 2。
    # 这是 Ruling 64 明写的刻意保守，须由测试钉住而不是留给读者猜。
    prev = base_scores(75); curr = dict(prev)
    curr[I.VITAL_CAPACITY] = 88; curr[I.SIT_AND_REACH] = 87; curr[I.STANDING_JUMP] = 86
    curr[I.SPRINT_50M] = 62; curr[I.PULL_UP_OR_SIT_UP] = 63   # DISTANCE_RUN 保持 75，d = 0
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) != Trend.VOLATILE


def test_trend_improving():
    # 每项各升 8 → 总分升 85×8/100 = 6.8 ≥ 5，且 min d = +8 > −5
    assert classify_trend(base_scores(70), base_scores(78),
                          total(base_scores(70)), total(base_scores(78)), 1.0) == Trend.IMPROVING


def test_trend_stable():
    # 仅 2 项各 ±2：加权总分变化 (15×2 + 20×−2)/100 = −0.1，四分支皆不满足
    prev = base_scores(75); curr = dict(prev)
    curr[I.VITAL_CAPACITY] = 77; curr[I.SPRINT_50M] = 73
    assert classify_trend(prev, curr, total(prev), total(curr), 1.0) == Trend.STABLE


def test_trend_insufficient_without_history():
    assert classify_trend(None, base_scores(75), None, total(base_scores(75)), 1.0) == Trend.INSUFFICIENT


def _rescore(table, record, sex, age_group):
    """一条体测记录 → 七项得分，**全部从原始测量值经生产正查 ``score_item`` 重算**。

    刻意不读记录里的 ``score_*`` 诊断列：那是生成期的中间量，读它就退化成自证
    （Task 6 的 oracle 读的正是它）。生产路径拿到的是原始值，所以这里也从原始值走。
    BMI 的算式与 ``app.seed.fitness._anthropometrics`` 逐字一致（含 ``round(..., 1)``）。
    """
    bmi = round(record["weight_kg"] / (record["height_cm"] / 100.0) ** 2, 1)
    scores = {ScoredItem.BMI: int(score_item(table, ScoredItem.BMI, bmi, sex, age_group))}
    for item in WEAKNESS_ITEMS:
        raw = float(record[COLUMN_BY_ITEM[item]])
        scores[item] = int(score_item(table, item, raw, sex, age_group))
    return scores


def test_trend_label_of_generated_data_is_truth():
    # Ruling 62 的守卫，也是 Task 6 那条 oracle 测试的**生产侧对账**：
    # 把 Task 6 生成的 500 人两学年 week1 得分喂给生产分类器，必须逐人等于 trend_label。
    # 两处若不一致，说明 Task 6 的 test-only oracle 与这里的生产实现有一处偏离了 spec §6.3。
    #
    # **两条硬约束（Ruling 75，来自 Task 6 fix round 2 的实现者上报）**
    # 1. **必须用零注入配置**：`SeedConfig(dirty={"missing":0,"outlier":0,"unit_error":0,"duplicate":0})`。
    #    Task 6 那侧能 500/500 一致，是因为它的 oracle 直接读记录里的 `score_*` 诊断列，而
    #    `inject_dirty` **不回算**这些列；生产侧却要从清洗后的原始值重新正查，于是
    #    4% missing → `national_total` 返回 `None` → 走 INSUFFICIENT，0.5% outlier 会凭空造出
    #    大 delta，1% duplicate 会让配对出现两行。**红的理由与趋势模型完全无关**，
    #    用缺省注入配置会让这条对账测试变成一个只反映脏数据比例的噪声源。
    #    若要覆盖注入后的路径，另写一条按 `dirty_marks` 跳过被注入 `(学号, 列)` 的测试。
    # 2. **只对 `week1` 断言**：趋势判据只在 week1 上由构造保证。week8/week16 实测各有
    #    5.0% / 4.2% 的人与 `trend_label` 不一致——目标空间的学年差三个时点相同，但两学年
    #    各自再落档一次、`drift` 一变量化损失就变（单项最多 ±9）。这不是缺陷：
    #    `trend_label` 的语义是「两学年之间的趋势」，其权威时点就是学年起点。
    cfg = SeedConfig(dirty={"missing": 0, "outlier": 0, "unit_error": 0, "duplicate": 0})
    ds = build_dataset(cfg)
    # 零注入是本条对账的前提，故先把它自己钉住：有痕迹就说明配置没生效，
    # 后面的不一致会与脏数据混在一起、分不清是谁造成的。
    assert ds["dirty_marks"] == [], f"零注入配置下仍有注入痕迹：{ds['dirty_marks'][:5]}"

    table = standard()
    is_current = {plan.academic_year: plan.is_current for plan in SEMESTERS}
    years = {record["academic_year"] for record in ds["fitness"]}
    assert len(years) == 2, f"趋势判定需要恰好两个学年，实际是 {sorted(years)}"
    age_of = {p["student_id"]: p["age"] for p in ds["population"]}
    sex_of = {p["student_id"]: Sex(p["sex"]) for p in ds["population"]}

    week1 = [record for record in ds["fitness"] if record["timepoint"] == "week1"]
    # 上学年 / 本学年按 SEMESTERS 的 is_current 认，不按 academic_year 的字典序猜
    previous = {r["student_id"]: r for r in week1 if not is_current[r["academic_year"]]}
    current = {r["student_id"]: r for r in week1 if is_current[r["academic_year"]]}
    assert len(previous) == len(current) == 500, (
        f"week1 配对不齐：上学年 {len(previous)} 人 / 本学年 {len(current)} 人"
    )
    assert set(previous) == set(current)

    agree = 0
    mismatches: list[tuple[int, str, str]] = []
    for student_id in sorted(current):
        prev_record, curr_record = previous[student_id], current[student_id]
        assert prev_record["trend_label"] == curr_record["trend_label"], (
            f"学生 {student_id} 两学年的 trend_label 不一致"
        )
        sex = sex_of[student_id]
        age = age_of[student_id]
        # 龄组按**该记录所属学年**取（Ruling 56）：上学年该生小一岁，age == 20 的学生
        # 上学年落在「大一、大二」那张表上（实测 132 人 = 26.4%）。正反查同表，
        # 否则趋势差值会带系统性偏差。
        prev_scores = _rescore(table, prev_record, sex, age_group_of(age - 1))
        curr_scores = _rescore(table, curr_record, sex, age_group_of(age))
        prev_total = national_total(prev_scores)
        curr_total = national_total(curr_scores)
        got = classify_trend(
            {i: prev_scores[i] for i in WEAKNESS_ITEMS},
            {i: curr_scores[i] for i in WEAKNESS_ITEMS},
            prev_total,
            curr_total,
            1.0,
        )
        expected = curr_record["trend_label"]
        if got.value == expected:
            agree += 1
        else:
            mismatches.append((student_id, expected, got.value))
    assert agree == 500, f"500 人逐人对账只一致 {agree} 人（不一致 {len(mismatches)} 人）"
    assert mismatches == [], (
        f"{len(mismatches)} 名学生的生产分类结果与 trend_label 不符"
        f"（前 5 条 (student_id, 期望, 实际)：{mismatches[:5]}）"
    )


# --- 短板判定（spec §4.2 / §6.3） ---
def test_weakness_below_p25_counted():
    curr = {i: 80 for i in ALL6}; curr[I.DISTANCE_RUN] = 50; curr[I.STANDING_JUMP] = 45
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.count == 2 and set(w.items) == {I.DISTANCE_RUN, I.STANDING_JUMP}
    assert w.valid_count == 6


def test_score_exactly_equal_to_p25_is_not_a_weakness():
    # spec §14 #21：比较符是**严格 `<`**。就低取档让每项得分只有 ≤20 个离散取值，
    # P25 处并列质量很高——若用 `<=`，一个 30% 的人同为 60 分的组会把这 30% 全判成短板，
    # 实质改变 W、改变红黄绿比例，甚至改变 valid_count >= 4 闸门的通过情况。
    curr = {i: 80 for i in ALL6}; curr[I.DISTANCE_RUN] = 60      # 恰等于 SNAP 的 p25
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.count == 0 and I.DISTANCE_RUN not in w.items


def test_item_without_a_snapshot_row_is_not_a_weakness_and_not_counted():
    # lookup_p25 返回 None = 该组无判定线。此时该项既不算短板、也不进 valid_count
    # （前向约束：valid_count 减少可能触发 < 4 的不分层闸门，Task 9 依赖这一点）。
    curr = {i: 30 for i in ALL6}                                  # 全部远低于 p25=60
    partial = [snap(i, 60) for i in ALL6 if i is not I.SPRINT_50M]
    w = find_weaknesses(curr, partial, Sex.MALE, LOWER_GRADE)
    assert w.count == 5 and w.valid_count == 5 and I.SPRINT_50M not in w.items


def test_bmi_never_counted_as_weakness():
    # Ruling 117-C2：本条改前是**空转测试**——用的 SNAP 里没有 BMI 判定线，故把
    # find_weaknesses 的遍历对象改成 tuple(ScoredItem) 后 369 条仍全绿（BMI 进了循环也
    # 查不到判定线 → continue，与「BMI 不在循环里」不可区分）。换成 SNAP_WITH_BMI 后
    # 同一变异立刻响亮失败。spec §4.2「短板判定项 = 6、W 的分母是 6」的唯一守卫在这里。
    curr = {i: 80 for i in ALL6}; curr[I.BMI] = 10       # BMI 远低于它的 p25 = 60
    w = find_weaknesses(curr, SNAP_WITH_BMI, Sex.MALE, LOWER_GRADE)
    assert w.count == 0
    assert I.BMI not in w.items
    assert w.valid_count == 6                            # BMI 也不进分母


def test_missing_item_not_counted_as_zero():
    # Review Focus #2
    curr = {i: 80 for i in ALL6}; curr[I.VITAL_CAPACITY] = None
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.valid_count == 5 and w.count == 0 and I.VITAL_CAPACITY not in w.items


def test_all_six_items_missing_yields_no_dominant_bucket():
    """Ruling 175：6 个短板判定项**全缺测**时 ``dominant_bucket is None``。

    这一支此前零覆盖，``app/domain/`` 的分支覆盖因此停在 99%（当时缺的那一行是
    ``derive.py:330`` 的 ``dominant = None``，**commit ``acf4ded`` 口径**——本处此前只印了
    裸行号、没绑 commit，违反硬规矩 #37：同一行在 ``b6ebaa3`` 上已经是
    ``counts: dict[str, int] = {}``，那句 ``dominant = None`` 挪到了 ``derive.py:353``、
    分支头在 ``derive.py:352`` 的 ``if not tied:``）。它是
    **合法可达**的生产路径，两条到它的路都在 ``find_weaknesses`` 的那个 ``continue`` 上：

    * 6 项得分全 ``None``（Task 6 按 4% 逐项注入缺测，一个人 6 项全缺的概率非零）；
    * 6 项全无判定线（``lookup_p25`` 返回 ``None``，例如该 (项, 性别, 年级组) 组的样本
      ``< MIN_SAMPLE``——Ruling 121 第 4 步记的正是「整组不产出快照行」）。

    本条走第一条路（``SNAP`` 六行判定线齐全，故只有得分缺）。此时 ``valid_count = 0``，
    ``valid_count < MIN_VALID_COUNT`` 让 Task 9 直接判 ``insufficient_data``、**不会去读**
    ``dominant_bucket``（见 :func:`find_weaknesses` docstring 的第三条），故 ``None`` 而不是
    「随便挑一个桶」才是对的：挑一个会让下游以为它有依据。
    """
    curr = {i: None for i in ALL6}
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.count == 0 and w.valid_count == 0
    assert w.items == ()
    assert w.dominant_bucket is None


def test_dominant_bucket_by_count_then_lowest_score():
    curr = {i: 80 for i in ALL6}
    curr[I.DISTANCE_RUN] = 40; curr[I.VITAL_CAPACITY] = 50     # 耐力 2 项
    curr[I.STANDING_JUMP] = 45                                  # 力量 1 项
    assert find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE).dominant_bucket == "endurance"


def test_dominant_bucket_tiebreak_by_lowest_score():
    curr = {i: 80 for i in ALL6}
    curr[I.DISTANCE_RUN] = 40; curr[I.STANDING_JUMP] = 30
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.dominant_bucket == "strength"       # 各 1 项，取最低分所在桶


def test_no_weakness_dominant_is_relative_weakest():
    # Ruling 100：W = 0 时取**桶内有效项得分均值最低者**。
    # speed_flexibility 均值 (70+72)/2 = 71，endurance 与 strength 均为 80。
    curr = {i: 80 for i in ALL6}; curr[I.SPRINT_50M] = 70; curr[I.SIT_AND_REACH] = 72
    assert find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE).dominant_bucket == "speed_flexibility"


def test_no_weakness_dominant_tiebreak_then_declaration_order():
    # Ruling 100 的两级决胜：均值相同 → 取桶内最低单项得分更低者；仍相同 → 按
    # ITEM_BUCKET 声明序取先出现者（保证结果不依赖 dict 哈希顺序）。
    # 本例 endurance 与 strength 均值都是 70、桶内最低分都是 70，两级全并列；
    # ITEM_BUCKET 的声明序是 endurance(VITAL_CAPACITY) → strength(PULL_UP_OR_SIT_UP)
    # → speed_flexibility(SPRINT_50M)，故唯一答案是 endurance。
    # **断言必须是等号**：`assert x in (A, B)` 是两可断言，走哪个分支都通过（Ruling 8）。
    curr = {i: 80 for i in ALL6}
    curr[I.DISTANCE_RUN] = 70; curr[I.VITAL_CAPACITY] = 70        # endurance 均值 70、最低 70
    curr[I.STANDING_JUMP] = 70; curr[I.PULL_UP_OR_SIT_UP] = 70    # strength  均值 70、最低 70
    w = find_weaknesses(curr, SNAP, Sex.MALE, LOWER_GRADE)
    assert w.count == 0
    assert w.dominant_bucket == "endurance"


# --- 体成分异常（spec §6.3 阈值） ---
def test_body_fat_male_boundary():
    assert flag_body_comp(20.0, 50.0, Sex.MALE, 40.0).abnormal is False
    assert flag_body_comp(20.1, 50.0, Sex.MALE, 40.0).abnormal is True


def test_body_fat_female_boundary():
    assert flag_body_comp(28.0, 45.0, Sex.FEMALE, 40.0).abnormal is False
    assert flag_body_comp(28.1, 45.0, Sex.FEMALE, 40.0).abnormal is True


def test_muscle_below_p20_is_abnormal():
    r = flag_body_comp(15.0, 39.9, Sex.MALE, 40.0)
    assert r.abnormal and "muscle_low" in r.reasons


def test_muscle_exactly_at_p20_is_not_abnormal():
    # spec §6.3② 是「肌肉量 < P20」，严格小于；恰等于 P20 不算异常。
    assert flag_body_comp(15.0, 40.0, Sex.MALE, 40.0).abnormal is False


def test_smi_is_not_an_input_at_all():
    # spec §14 #16：骨骼肌指数入库但第一批不参与判定。
    # **必须钉住签名本身**：原计划那条 `test_smi_does_not_affect_flag` 传的是
    # (15.0, 50.0, MALE, 40.0) 然后断言不异常——但 `smi` 根本不是参数，那条测试
    # 对 SMI 零覆盖，它测的只是「正常体脂 + 正常肌肉量不算异常」，是个空转测试。
    params = list(inspect.signature(flag_body_comp).parameters)
    assert params == ["body_fat_pct", "muscle_mass_kg", "sex", "snapshot_muscle_p20"]
    assert not any("smi" in p for p in params)


def test_missing_body_comp_is_not_abnormal_but_carries_the_limit():
    # Ruling 97：两个输入都缺 → abnormal False（spec §6.3② 的布尔式对 None 无从成立），
    # 但 limit 仍按性别填，否则 Task 9 的 explain() 渲染不出「数据缺失（男生阈值 20%）」。
    # 后果（必须写进 docstring）：W >= 2 且无 InBody 数据的学生落 Y3（黄）而非 R1（红），
    # 即**缺数据导致干预不足**——与短板一侧「缺项不计入 W」的代价同向。
    r = flag_body_comp(None, None, Sex.MALE, None)
    assert r.abnormal is False and r.reasons == ()
    assert r.body_fat_pct is None and r.limit == 20.0


def test_flag_carries_value_and_limit_for_explain():
    # Ruling 7：explain() 须能渲染 spec §9.2 文案「体脂率 22.4% 超过男生 20% 阈值」
    r = flag_body_comp(22.4, 50.0, Sex.MALE, 40.0)
    assert r.abnormal and r.body_fat_pct == 22.4 and r.limit == 20.0
    assert r.reasons == ("body_fat_high",)
    rf = flag_body_comp(29.0, 45.0, Sex.FEMALE, 40.0)
    assert rf.abnormal and rf.limit == 28.0
    both = flag_body_comp(29.0, 39.9, Sex.FEMALE, 40.0)
    assert both.reasons == ("body_fat_high", "muscle_low")     # token 顺序固定，供 explain 直接渲染
    ok = flag_body_comp(15.0, 50.0, Sex.MALE, 40.0)
    assert ok.body_fat_pct == 15.0 and ok.limit == 20.0


# --- 国标总分（Ruling 63/101：加权口径的唯一所有者） ---
def test_national_total_is_weighted_and_floored():
    s = {i: 80 for i in ALL6}; s[I.BMI] = 80
    assert national_total(s) == 80                      # 七项同为 80 → 加权后仍是 80
    s2 = dict(s); s2[I.SPRINT_50M] = 100                  # w=20 的项 +20 → 总分 +4
    assert national_total(s2) == 84
    s3 = dict(s); s3[I.SIT_AND_REACH] = 100               # w=10 的项 +20 → 总分 +2
    assert national_total(s3) == 82


def test_national_total_floor_makes_order_of_operations_matter():
    # Ruling 71/76 的守卫：**先各自整除、再相减**，与「差值再除」最多差 1 分，
    # 而 spec §6.3 的 ±5 阈值作用在整数总分上。本例是两种口径**在阈值上分岔**的构造：
    #   Σw·prev = 7500 → //100 = 75；Σw·curr = 7020 → //100 = 70
    #   整数口径 Delta = 70 − 75 = **−5** → 触发「总分下降 ≥ 5」
    #   连续口径 (7020 − 7500)/100 = **−4.80** → **不触发**
    # （控制者已实跑验证；第一版写的 sprint60/dist60/vital72 给的是 Σcurr=6855 →
    #   整数 −7 / 连续 −6.45，两者都触发，测不出分岔，已废。）
    # 逐项 d = (0, −15, 0, 0, 0, −9)：只有 2 项降 ≥5，故第二分支不触发；
    # pos=0 / neg=2 → min=0 < 3，波动大也不触发。**DECLINING 只能由第一分支给出。**
    # 60 与 66 都是 distance_run / sprint_50m 的官方档分（控制者已核对得分阶梯）。
    prev = {i: 75 for i in ALL6}; prev[I.BMI] = 75
    curr = dict(prev); curr[I.SPRINT_50M] = 60; curr[I.DISTANCE_RUN] = 66
    assert national_total(prev) == 75 and national_total(curr) == 70
    assert national_total(curr) - national_total(prev) == -5
    assert classify_trend({i: prev[i] for i in ALL6}, {i: curr[i] for i in ALL6},
                          national_total(prev), national_total(curr), 1.0) == Trend.DECLINING


def test_national_total_returns_none_when_any_of_the_seven_is_missing():
    s = {i: 80 for i in ALL6}; s[I.BMI] = None
    assert national_total(s) is None
    s2 = {i: 80 for i in ALL6}                     # 只有 6 项、根本没有 BMI 键
    assert national_total(s2) is None              # 「键不存在」与「值为 None」同等对待


# --- derive 编排（Ruling 99/101/103/104/106/107/108） ---
# **derive 是 11 个参数，``age_group`` 在第 9 位（``sex`` 之后、``snapshot`` 之前）**
# （Ruling 103）。少写 ``LOWER_GRADE`` 不会立刻 TypeError——``SNAP`` 会被当成
# ``age_group``、``40.0`` 被当成 ``snapshot``，然后在 ``find_weaknesses`` 里以一个
# 看不出所以然的错误炸开（Ruling 109）。
def seven(v=70):
    """七项同分的输入。**刻意不给 ``bmi`` 参数**：需要「BMI 值为 ``None``」的测试请直接
    ``d = seven(70); d[I.BMI] = None``——一个二义参数无法区分「``None`` 表示用 ``v``」
    与「``None`` 表示缺测」，而那正是 Ruling 106 要钉住的状态。"""
    d = {i: v for i in ALL6}
    d[I.BMI] = v
    return d


def test_derive_requires_all_seven_score_keys():
    six = {i: 80 for i in ALL6}                    # 缺 BMI 键
    with pytest.raises(KeyError):
        derive(six, None, None, None, 1.0, 18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_derive_rejects_an_age_group_outside_age_groups():
    # Ruling 107：``age_group`` 是 11 个参数里唯一的自由字符串，传错**不报错**——
    # 实测 "18-19" 静默返回 count=0 / valid_count=0 / dominant_bucket=None，
    # 于是 valid_count = 0 < 4 直接走进 Task 9 的不分层闸门。与 Ruling 103 批评
    # 空串哨兵是同一缺陷形态（差别只在责任方，不在后果），故必须响亮失败。
    with pytest.raises(ValueError):
        derive(seven(80), None, national_total(seven(80)), None, 1.0,
               18.0, 50.0, Sex.MALE, "18-19", SNAP, 40.0)


def test_derive_annual_change_is_empty_without_history():
    s = {i: 80 for i in ALL6}; s[I.BMI] = 80
    r = derive(s, None, national_total(s), None, 1.0, 18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert r.trend is Trend.INSUFFICIENT
    assert r.annual_change == {}                  # 不是「7 个键全 0.0」：0.0 是「一年没变化」
    assert r.national_total == 80 and r.sex is Sex.MALE


def test_derive_annual_change_covers_six_items_plus_total():
    prev = {i: 70 for i in ALL6}; prev[I.BMI] = 70
    curr = {i: 80 for i in ALL6}; curr[I.BMI] = 80
    r = derive(curr, prev, national_total(curr), national_total(prev), 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert set(r.annual_change) == {i.value for i in ALL6} | {"national_total"}
    assert all(v == 10.0 for v in r.annual_change.values())
    assert r.trend is Trend.IMPROVING


def test_derive_years_scales_the_annual_change():
    prev = {i: 70 for i in ALL6}; prev[I.BMI] = 70
    curr = {i: 80 for i in ALL6}; curr[I.BMI] = 80
    r = derive(curr, prev, national_total(curr), national_total(prev), 2.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert r.annual_change["national_total"] == 5.0        # (80−70)/2
    assert r.trend is Trend.IMPROVING                       # 年均 5.0 >= 阈值 5


def test_derive_rejects_inconsistent_curr_total_and_scores():
    # Ruling 101：curr_total 非 None 而七项里有 None（或反之）说明调用方算错了口径，
    # 必须响亮失败，不得静默产出一个 national_total=None 的结果。
    # 计划 Step 1 把本条扩成**两个方向各一个** pytest.raises 分支（Ruling 106 之后
    # prev 一侧用的是同一套对称判据，故 curr 一侧的守卫也必须双向）。
    with pytest.raises(ValueError):                      # 七项值全非 None，却 curr_total=None
        derive(seven(80), None, None, None, 1.0, 18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    curr_gap = seven(80); curr_gap[I.BMI] = None         # BMI 值为 None，却 curr_total=80
    with pytest.raises(ValueError):
        derive(curr_gap, None, 80, None, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_history_with_a_missing_value_is_legal_and_goes_insufficient():
    # **Ruling 106 的核心守卫**：prev 七键齐全、但 BMI **值为 None** 是合法的真实状态
    # （Task 6 的缺测注入率 4%，历史缺测是常态）。此时 national_total 正确返回 None，
    # derive 必须放行 → classify_trend 归 INSUFFICIENT、annual_change 归 {}。
    # Ruling 104 的字面判据（prev_scores is None ↔ prev_total is None）会在这里抛
    # ValueError，而 curr 一侧同形态正常返回——那个不对称会让 classify_trend docstring
    # 明写的「七项里有缺测 → INSUFFICIENT」分支永不可达，并让 Task 10 的 500 人回放
    # 在约 4% 的合法状态上整批崩溃。
    prev = seven(70); prev[I.BMI] = None
    assert national_total(prev) is None                     # 前提：总分合法地不可得
    r = derive(seven(80), prev, national_total(seven(80)), national_total(prev), 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert r.trend is Trend.INSUFFICIENT and r.annual_change == {}


def test_derive_picks_the_right_age_group_from_a_multi_group_snapshot():
    # Ruling 103：``snapshot`` 是**整张多组快照**（两个年级组的行都在里面），判定线由
    # find_weaknesses → lookup_p25 按 (item, sex, age_group) 三元过滤挑出来，调用方不预筛。
    #
    # 构造刻意让「取错组」必然改变 W：两组 P25 相差 20 分（60 / 40），学生六项**固定在
    # 两线之间**（全 50）。于是
    #   age_group = 大一、大二 → 50 < 60 → 六项全部是短板（W = 6）
    #   age_group = 大三、大四 → 50 > 40 → 零短板（W = 0）
    # 若 age_group 没被传进 find_weaknesses（例如恒用 AGE_GROUPS[0]），下半段会红。
    multi = (
        [snap_group(i, 60, LOWER_GRADE) for i in ALL6]
        + [snap_group(i, 40, UPPER_GRADE) for i in ALL6]
    )
    s = {i: 50 for i in ALL6}; s[I.BMI] = 50
    lo = derive(s, None, national_total(s), None, 1.0,
                18.0, 50.0, Sex.MALE, LOWER_GRADE, multi, 40.0)
    hi = derive(s, None, national_total(s), None, 1.0,
                18.0, 50.0, Sex.MALE, UPPER_GRADE, multi, 40.0)
    assert lo.weakness.count == 6 and lo.weakness.count > 0     # W > 0
    assert hi.weakness.count == 0                               # W == 0
    # valid_count 两侧都是 6：证明「大三、大四」那半边是**找到了判定线且 50 不低于它**，
    # 而不是「一行都没匹配上 → 不计入 valid_count」的假零短板。
    assert lo.weakness.valid_count == 6 and hi.weakness.valid_count == 6


def test_derive_exposes_weakness_fields():
    # 此前 5 条 derive 测试只断言 r.trend / r.national_total / r.annual_change，对
    # **r.weakness 零覆盖**——derive 是否真把 find_weaknesses 的结果装进 DerivedResult、
    # 装的是不是同一个对象，全都没有守卫。这条把四个字段逐个钉住。
    #
    # 构造：DISTANCE_RUN（endurance，w=20）= 40、STANDING_JUMP（strength，w=10）= 45，
    # 两项都低于 p25 = 60；其余四项 80 达标。故 W = 2、valid_count = 6。
    # items 按 WEAKNESS_ITEMS 声明序（standing_jump 在 distance_run 之前），不是输入顺序。
    # dominant_bucket：endurance 与 strength 各 1 项并列 → 取桶内最低单项得分更低者，
    # endurance 的 40 < strength 的 45 → "endurance"。
    s = {i: 80 for i in ALL6}; s[I.BMI] = 80
    s[I.DISTANCE_RUN] = 40; s[I.STANDING_JUMP] = 45
    r = derive(s, None, national_total(s), None, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert r.weakness.count == 2
    assert r.weakness.valid_count == 6
    assert r.weakness.items == (I.STANDING_JUMP, I.DISTANCE_RUN)
    assert r.weakness.dominant_bucket == "endurance"


def test_derive_exposes_body_comp_fields():
    # Ruling 117-C1：改前 41 条测试**没有一处读 r.body_comp**（Select-String "\.body_comp"
    # 命中 0），把 derive 里的调用改成 flag_body_comp(None, None, sex, None) → 当时 369 passed
    # （369 是那时的套件规模，fix round 3 是 428 条；这个数字不被守卫，只是变异取证的记录），
    # 而体脂 35%（男阈值 20）+ 肌肉量 10kg（P20=40）静默返回 abnormal=False。
    # 后果是 C ≡ False：spec §6.2 的 R1（W>=2 AND C）与 Y2（W=0 AND C）永不触发、
    # 红色层清空，而测试全绿、日志无异常。这条按**三种情形**把透传逐个钉住，
    # 并覆盖复审实跑过的那组「两者都异常」输入。
    s = {i: 80 for i in ALL6}; s[I.BMI] = 80
    t = national_total(s)

    fat = derive(s, None, t, None, 1.0, 35.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert fat.body_comp.abnormal is True
    assert fat.body_comp.reasons == ("body_fat_high",)
    assert fat.body_comp.body_fat_pct == 35.0 and fat.body_comp.limit == 20.0

    thin = derive(s, None, t, None, 1.0, 15.0, 10.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert thin.body_comp.abnormal is True
    assert thin.body_comp.reasons == ("muscle_low",)
    assert thin.body_comp.body_fat_pct == 15.0 and thin.body_comp.limit == 20.0

    ok = derive(s, None, t, None, 1.0, 15.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert ok.body_comp.abnormal is False and ok.body_comp.reasons == ()
    assert ok.body_comp.body_fat_pct == 15.0
    assert ok.body_comp.limit is not None          # Ruling 97②：limit 一律非 None

    both = derive(s, None, t, None, 1.0, 35.0, 10.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert both.body_comp.reasons == ("body_fat_high", "muscle_low")   # token 顺序固定


def test_derive_rejects_prev_scores_without_prev_total():
    # Ruling 104：一致性校验必须**扩到 prev 一侧**。prev_scores 完整而 prev_total=None
    # 会静默伪装成「无历史」——classify_trend 归 INSUFFICIENT、annual_change 归 {}、
    # 全程不报错，而实际上历史是有的、只是调用方忘了算总分。方向不利且无声，故 ValueError。
    prev = {i: 70 for i in ALL6}; prev[I.BMI] = 70
    curr = {i: 80 for i in ALL6}; curr[I.BMI] = 80
    with pytest.raises(ValueError):
        derive(curr, prev, national_total(curr), None, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_derive_requires_all_seven_prev_score_keys():
    # Ruling 104：prev 一侧复用同一套 _require_seven_keys（不写第二份）。缺 BMI 键时
    # national_total(prev_scores) 会静默返回 None，于是「有历史」变成「总分不可比」、
    # annual_change 归 {} —— 与 curr 一侧同一种静默失效，故同样 KeyError 响亮失败。
    #
    # ``prev_total`` 由生产 ``national_total`` 算出而**不是手写字面量**（同 ``total()``
    # 的纪律）。构造的是真实缺陷形态：调用方算好了总分，却把漏了 BMI 键的 dict 传进来。
    # 实测 KeyError 优先于 prev 一致性 ValueError（_require_seven_keys 跑在前面），
    # 故 prev_total 传 None 也是 KeyError——但那样就测不出「非 None」这一半前提。
    prev = {i: 70 for i in ALL6}                   # 缺 BMI 键
    prev_total = national_total({**prev, I.BMI: 70})
    assert prev_total is not None                  # 前提钉住：prev_total 确实非 None
    curr = {i: 80 for i in ALL6}; curr[I.BMI] = 80
    with pytest.raises(KeyError):
        derive(curr, prev, national_total(curr), prev_total, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_derive_rejects_prev_total_without_prev_scores():
    # Ruling 108：一致性校验是**双向**的（「必须同真同假」），而反方向此前零覆盖。
    # 行为在 Ruling 104 时就已正确，本条只补守卫、不改行为——故它在实现未改时就是绿的，
    # 非空转由变异 3b 证明（把校验改成单向 `prev_complete and prev_total is None`，
    # 本条 DID NOT RAISE）。
    # **实测危害如实写清**：若放行，annual_change 仍是 {}（`prev_scores is not None` 那个
    # 合取项挡住了）、trend 仍是 INSUFFICIENT，即**矛盾输入被静默吞掉、产出与合法的
    # 「无历史」一模一样**，调用方的 bug 永不暴露——不是「凭空造出一张差值表」。
    with pytest.raises(ValueError):
        derive(seven(80), None, national_total(seven(80)), 70, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_derive_rejects_prev_total_with_a_missing_prev_value():
    # Ruling 110 / 形态 6：prev **七键齐全但含 None 值** + prev_total 非 None。
    # 行为自 Ruling 106 起就正确（ValueError、消息诚实），但**零测试覆盖**：上一轮实现者
    # 发现了这个缺口却没敢补，因为简报把测试数钉死在 369（硬规矩 #12 由此而立）。
    # 危害（上一轮变异 3b 实测）：单向校验下形态 6 静默放行 → trend=稳步提升 + 满 7 键的
    # annual_change，而它的基准 70 是 national_total(prev_scores) **永远算不出**的值。
    #
    # **为什么还要断言消息**：形态 6 现在被**两道**守卫拦下——Ruling 106 的 None-ness
    # 对称校验，与本轮 Ruling 118-M1 的值校验（prev_total=70 而真值是 None，两者不等）。
    # 只断言 ValueError 的话，砍掉任一道另一道仍会拦住，本条就**不可伪证**（空转）。
    # 断言消息把它钉在 None-ness 那一支上（值校验那一支的消息不含「同真同假」）。
    prev = seven(70); prev[I.BMI] = None
    assert national_total(prev) is None                     # 前提：总分合法地不可得
    with pytest.raises(ValueError) as exc:
        derive(seven(80), prev, national_total(seven(80)), 70, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    assert "同真同假" in str(exc.value)


def test_derive_rejects_a_curr_total_that_disagrees_with_national_total():
    # Ruling 118-M1：一致性校验改前只查 total 的 **None-ness**、不查**值**。复审实测
    # curr_total=99（而 national_total(curr_scores)=80）静默放行，并原样进入
    # DerivedResult.national_total（spec §6.1 空洞一的同层内排序键）与 classify_trend 的
    # Delta（规则 Y4 的唯一输入）。消息必须报出**两个值**，否则调用方无从定位。
    s = seven(80)
    assert national_total(s) == 80                          # 前提钉住：真值是 80
    with pytest.raises(ValueError) as exc:
        derive(s, None, 99, None, 1.0, 18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    message = str(exc.value)
    assert "99" in message and "80" in message


def test_derive_rejects_a_prev_total_that_disagrees_with_national_total():
    # 同一条判据的 prev 侧。算错的基准会同时污染 Delta 与全部 annual_change：
    # 改前实测 prev_total=55（真值 70）静默放行，annual_change["national_total"]
    # 从 +10.0 变成 +25.0，趋势仍是稳步提升（不响、也不易察觉）。
    prev = seven(70); curr = seven(80)
    assert national_total(prev) == 70
    with pytest.raises(ValueError) as exc:
        derive(curr, prev, national_total(curr), 55, 1.0,
               18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
    message = str(exc.value)
    assert "55" in message and "70" in message


def test_derive_rejects_non_positive_years():
    # Ruling 118-M2：years 改前无任何校验，负值**静默反转**趋势与全部 annual_change 的
    # 符号——实测 years=-1.0 让总分 70→80 的进步被判成「持续下滑」、
    # annual_change["national_total"] = -10.0；years=0 在有历史时是 ZeroDivisionError、
    # 无历史时（annual_change={} 不做除法）**完全不报错**。years 由 Task 10 用两个学年
    # 相减得到，方向写反就是 -1，与 Ruling 62 的 C1 是同一缺陷形态的第二个入口。
    s = seven(80); t = national_total(s)
    for years in (-1.0, 0.0):
        with pytest.raises(ValueError):
            derive(s, None, t, None, years, 18.0, 50.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)


def test_classify_trend_rejects_non_positive_years():
    # classify_trend 是**公开 API**（Task 9/10 可能绕过 derive 直接调它），故两处都校验。
    # 校验在 `prev is None` 的早退**之前**：years 合不合法与有没有历史无关，
    # 最后一条断言把这个顺序钉住（无历史也不放行非法 years）。
    prev = base_scores(75); curr = base_scores(80)
    for years in (-1.0, 0.0):
        with pytest.raises(ValueError):
            classify_trend(prev, curr, total(prev), total(curr), years)
    with pytest.raises(ValueError):
        classify_trend(None, curr, None, total(curr), -1.0)
