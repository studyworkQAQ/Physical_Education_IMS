"""国标 2014 指标定义与评分正查/反查的行为约束。"""
import pytest

from app.domain.indicators import (
    Sex, ScoredItem, WEAKNESS_ITEMS, ITEM_BUCKET,
    age_group_of, score_item, raw_from_score, segment_thresholds,
)
from app.refdata import standard

T = standard()          # 表由 refdata 加载后注入，domain 自身不读盘（Ruling 15）
G = age_group_of(19)

# 全部测试一律从评分表自身推导档位与档位分，不硬编码 CSV 数值——
# 将来一次合法的数据更正不应该弄红测试。唯一例外见
# test_bmi_unrounded_value_scores_correctly 里的说明。
EPS = 1e-6


def test_weakness_items_exclude_bmi():
    assert len(WEAKNESS_ITEMS) == 6
    assert ScoredItem.BMI not in WEAKNESS_ITEMS

def test_scored_items_count_is_seven():
    assert len(list(ScoredItem)) == 7

def test_buckets_cover_all_weakness_items():
    assert {ITEM_BUCKET[i] for i in WEAKNESS_ITEMS} == {
        "endurance", "strength", "speed_flexibility"}
    assert ITEM_BUCKET[ScoredItem.BMI] is None

def test_direction_is_normalized_to_higher_is_better():
    # 50 米跑越快得分越高
    assert score_item(T, ScoredItem.SPRINT_50M, 6.5, Sex.MALE, G) > \
           score_item(T, ScoredItem.SPRINT_50M, 9.0, Sex.MALE, G)

def test_score_at_exact_threshold_returns_that_thresholds_score():
    # Ruling 18：就低取档下，恰好等于某档阈值时必须拿到该档在表里列出的分，
    # 既不掉档也不插值。阈值与期望分都从表里取，不硬编码魔数。
    for item in (ScoredItem.SPRINT_50M, ScoredItem.STANDING_JUMP):
        segments = T.segments[(item.value, Sex.MALE.value, G)]
        for raw, listed in segments:
            assert score_item(T, item, raw, Sex.MALE, G) == listed

def test_score_just_past_threshold_drops_one_band():
    # 就低取档的直接后果：刚越过阈值一档就掉到相邻的低档，这是国标本来的口径，
    # 不再是「浮点误差掉档」的缺陷。方向由表推断，两类项各验一次。
    lower_is_better = ScoredItem.SPRINT_50M          # 沿 raw 升序得分递减
    higher_is_better = ScoredItem.STANDING_JUMP       # 沿 raw 升序得分递增

    seg = T.segments[(lower_is_better.value, Sex.MALE.value, G)]
    (raw, listed), (raw_next, listed_next) = seg[3], seg[4]
    assert raw_next - raw > EPS and listed_next < listed
    assert score_item(T, lower_is_better, raw, Sex.MALE, G) == listed
    assert score_item(T, lower_is_better, raw + EPS, Sex.MALE, G) == listed_next

    seg = T.segments[(higher_is_better.value, Sex.MALE.value, G)]
    (raw_prev, listed_prev), (raw, listed) = seg[9], seg[10]
    assert raw - raw_prev > EPS and listed_prev < listed
    assert score_item(T, higher_is_better, raw, Sex.MALE, G) == listed
    assert score_item(T, higher_is_better, raw - EPS, Sex.MALE, G) == listed_prev

def test_score_item_only_returns_official_discrete_scores():
    # 这条是「插值」缺陷的照妖镜：旧实现在同一批扫描点上产出过 1666 个
    # 国标里根本不存在的分（如立定跳远 210 cm → 61 分、1000 米 280 秒 → 56 分），
    # 使系统单项分无法与学校官方体测报表逐格对账（spec §12 黄金用例、§1.3 可追溯性）。
    for item in ScoredItem:
        for sex in Sex:
            segments = T.segments[(item.value, sex.value, G)]
            official = {listed for _, listed in segments}
            lo, hi = segments[0][0], segments[-1][0]
            probes = [lo + (hi - lo) * k / 200 for k in range(201)]
            probes += [lo - 1.0, hi + 1.0]      # 越界夹取也只能夹到表内的档位分
            for value in probes:
                got = score_item(T, item, value, sex, G)
                assert got in official, (
                    f"{item.value}/{sex.value}/{G} raw={value} 得到非官方分 {got}")

def test_bmi_unrounded_value_scores_correctly():
    # 【本文件唯一允许硬编码 CSV 数值的测试】钉的是国标公布的 BMI 区间端点本身
    # （男：低体重 ≤17.8、正常 17.9~23.9、超重 24.0~27.9、肥胖 ≥28.0），
    # 这些端点就是被测口径，无法从 segment_thresholds 推导出来。
    # Ruling 18 关掉的正是三个 0.1 宽的舍入缝：未取整的 17.85 / 23.94 / 27.95
    # 此前被插值成 90 / 92 / 70 这些国标里不存在的分；就低取档下 23.94 落回
    # 23.9 → 100 分，该生按国标确实是「正常」。
    expected = {15.0: 80, 17.85: 80, 23.94: 100, 24.0: 80, 28.0: 60, 38.0: 60}
    for bmi, want in expected.items():
        assert score_item(T, ScoredItem.BMI, bmi, Sex.MALE, G) == want

def test_sex_specific_items_differ():
    m = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.MALE, G)
    f = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.FEMALE, G)
    assert m != f  # 男引体向上 10 次与女仰卧起坐 10 次得分不同

def test_missing_value_returns_none():
    assert score_item(T, ScoredItem.VITAL_CAPACITY, None, Sex.MALE, G) is None

def test_value_worse_than_worst_segment_clamps_to_floor_not_none():
    # Ruling 17：差于表内最差档必须夹到该档分数，绝不可返回 None。
    # 返回 None 会把「极差成绩」当成「缺测」，既拉低 valid_count，又让该项
    # 不计入短板 W —— 最需要干预的学生反而被筛出红色层，且全程不报错。
    worst = segment_thresholds(T, ScoredItem.DISTANCE_RUN, Sex.MALE, G)[-1]
    at_worst = score_item(T, ScoredItem.DISTANCE_RUN, worst, Sex.MALE, G)
    beyond   = score_item(T, ScoredItem.DISTANCE_RUN, worst + 120.0, Sex.MALE, G)
    assert at_worst is not None
    assert beyond == at_worst

def test_value_better_than_best_segment_clamps_to_ceiling():
    best = segment_thresholds(T, ScoredItem.SPRINT_50M, Sex.MALE, G)[0]
    at_best = score_item(T, ScoredItem.SPRINT_50M, best, Sex.MALE, G)
    beyond  = score_item(T, ScoredItem.SPRINT_50M, max(best - 2.0, 0.1), Sex.MALE, G)
    assert at_best is not None
    assert beyond == at_best

def test_unknown_item_sex_agegroup_key_returns_none():
    # 契约的另一半：None 只留给「真缺测」——value 缺失或表里没有这个组合。
    # 传错 (项, 性别, 年级组) 组合与「成绩差到表外」必须是两回事。
    assert score_item(T, ScoredItem.VITAL_CAPACITY, 4000.0, Sex.MALE, "不存在的年级组") is None

def test_raw_from_score_roundtrips():
    # 就低取档下反查落在档位区间中点，回代必须**精确**等于该官方档的分（不再容忍 ±1）
    for item in WEAKNESS_ITEMS:
        for sex in Sex:
            for _, listed in T.segments[(item.value, sex.value, G)]:
                raw = raw_from_score(T, item, listed, sex, G)
                assert score_item(T, item, raw, sex, G) == listed

def test_raw_from_score_maps_unofficial_target_down_to_official_band():
    # 就低：请求分不是官方档时，落到「不超过它的最大官方档」，回代得到的是那个档的分
    # 而不是请求分本身（Task 6 会算出 73 这类连续目标分）。
    # 注：73 在本项落 72 档而非 70 档，因为 72 本身就是官方档；71 才落 70 档。
    segments = T.segments[(ScoredItem.STANDING_JUMP.value, Sex.MALE.value, G)]
    official = sorted({listed for _, listed in segments})
    for requested, want in ((73, 72), (71, 70)):
        assert want in official
        assert want == max(s for s in official if s <= requested)
        raw = raw_from_score(T, ScoredItem.STANDING_JUMP, requested, Sex.MALE, G)
        assert score_item(T, ScoredItem.STANDING_JUMP, raw, Sex.MALE, G) == want

def test_raw_from_score_rejects_non_monotonic_item():
    # Ruling 19：BMI 两头 80、中间 100，非单调，「按目标分反查唯一原始值」不成立。
    # 旧实现对 80 分返回哨兵 0.0（80 恰是 BMI 最常见的目标分：低体重与超重都是 80），
    # Task 6 会因此造出 BMI = 0 kg/m² 的学生，而 score_item(..., 0.0) == 80
    # 使往返测试全绿——缺陷被完美掩盖。正确做法是生成身高体重后正查。
    for sex in Sex:
        with pytest.raises(ValueError):
            raw_from_score(T, ScoredItem.BMI, 80, sex, G)

def test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key():
    # 三个函数对「键不存在」的契约必须一致：反查与取阈值都抛 KeyError。
    # segment_thresholds 返回空列表会让调用方的 [0]/[-1] 退化成看不出所以然的 IndexError。
    with pytest.raises(KeyError):
        raw_from_score(T, ScoredItem.VITAL_CAPACITY, 80, Sex.MALE, "不存在的年级组")
    with pytest.raises(KeyError):
        segment_thresholds(T, ScoredItem.VITAL_CAPACITY, Sex.MALE, "不存在的年级组")

def test_domain_functions_are_pure_and_take_table_explicitly():
    # Ruling 15：同一个表对象传入两次结果必须一致，且 domain 不依赖任何全局加载状态
    a = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    b = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    assert a == b and a is not None
