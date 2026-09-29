"""国标 2014 指标定义与评分正查/反查的行为约束。"""
from app.domain.indicators import (
    Sex, ScoredItem, WEAKNESS_ITEMS, ITEM_BUCKET,
    age_group_of, score_item, raw_from_score, segment_thresholds,
)
from app.refdata import standard

T = standard()          # 表由 refdata 加载后注入，domain 自身不读盘（Ruling 15）
G = age_group_of(19)

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

def test_score_at_segment_boundary():
    # Review Focus #1：恰好等于档位阈值时不得因浮点误差掉档。
    # 阈值从评分表本身取，避免硬编码魔数与 CSV 内容脱钩。
    thr = segment_thresholds(T, ScoredItem.SPRINT_50M, Sex.MALE, G)[3]
    at_thr     = score_item(T, ScoredItem.SPRINT_50M, thr, Sex.MALE, G)
    just_worse = score_item(T, ScoredItem.SPRINT_50M, thr + 1e-9, Sex.MALE, G)
    assert at_thr == just_worse
    assert at_thr is not None

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
    for item in WEAKNESS_ITEMS:
        raw = raw_from_score(T, item, 80, Sex.MALE, G)
        assert abs(score_item(T, item, raw, Sex.MALE, G) - 80) <= 1

def test_domain_functions_are_pure_and_take_table_explicitly():
    # Ruling 15：同一个表对象传入两次结果必须一致，且 domain 不依赖任何全局加载状态
    a = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    b = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    assert a == b and a is not None
