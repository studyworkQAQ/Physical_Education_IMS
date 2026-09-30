"""红黄绿分层引擎（spec §6.2 的八行决策表）与 ``explain()`` 可解释性文案的行为约束。

18 条测试分四组：

* 八条规则各至少一条（R1 / R2 / Y1×2 / Y2 / Y3×2 / Y4 / G1 / Z0），外加规则**优先级**
  两条（R1 先于 R2、Z0 先于全部）与「趋势只升级永不降级」一条（spec §6.1 空洞二）；
* ``valid_count`` 闸门的两条边界（``= 3`` 不分层、``= 4`` 照常分层，Review Focus #2 / #5）；
* ``explain()`` 的三条：具体数值与该性别阈值（spec §9.2）、女生阈值、Z0 路径的文案；
* ``ITEM_DISPLAY_NAMES`` 与 spec §4.2 计分项表逐行一致（Ruling 127）。

期望值一律**字面写在这里**，不从被测常量读回来跟自己比——自证的常量测试等于没有测试
（``test_indicators.py`` 的 ``test_item_weights_match_spec_4_2_verbatim`` 是同一条纪律）。
"""
from app.domain.stratify import stratify, Layer, RuleId, MIN_VALID_COUNT, explain
from app.domain.derive import DerivedResult, WeaknessResult, BodyCompFlag, Trend
from app.domain.indicators import ITEM_DISPLAY_NAMES, ScoredItem, Sex


def mk(w, c=False, trend=Trend.STABLE, valid=6, dominant="endurance",
       sex=Sex.MALE, bf=22.4):
    # **与 Task 8 的实际产出对齐（Ruling 116，修正两处照抄源失效）**：
    # ① `WeaknessResult` **没有** `patterns` 参数（Ruling 98 已删），传它会
    #    `TypeError: __init__() got an unexpected keyword argument 'patterns'`；
    # ② `reasons` 的 token 是 **`"body_fat_high"`**，不是 `"body_fat_over"`
    #    （Ruling 97① 冻结的 vocabulary 只有 `body_fat_high` / `muscle_low` 两个）。
    # 两者都不会被 Task 9 自己的断言抓到——`mk()` 是测试助手，构造失败会在
    # **第一条**测试就 TypeError，看起来像 Task 9 写错了而不是助手过期了。
    limit = 20.0 if sex == Sex.MALE else 28.0
    return DerivedResult(
        sex=sex,
        trend=trend,
        weakness=WeaknessResult(items=(), count=w, valid_count=valid,
                                dominant_bucket=dominant),
        body_comp=BodyCompFlag(abnormal=c,
                               reasons=("body_fat_high",) if c else (),
                               body_fat_pct=bf, limit=limit),
        annual_change={}, national_total=75)


def test_R1_two_weaknesses_and_abnormal_is_red():
    r = stratify(mk(2, c=True));  assert r.label == Layer.RED and RuleId.R1 in r.hit_rules

def test_R2_four_weaknesses_unconditionally_red():
    r = stratify(mk(4, c=False)); assert r.label == Layer.RED and RuleId.R2 in r.hit_rules

def test_R1_takes_priority_over_R2():
    r = stratify(mk(5, c=True));  assert r.hit_rules[0] == RuleId.R1

def test_Y1_single_weakness_is_yellow():
    r = stratify(mk(1));          assert r.label == Layer.YELLOW and RuleId.Y1 in r.hit_rules

def test_Y1_applies_even_when_body_comp_abnormal():
    r = stratify(mk(1, c=True));  assert r.label == Layer.YELLOW and RuleId.Y1 in r.hit_rules

def test_Y2_only_body_comp_abnormal_is_yellow():
    r = stratify(mk(0, c=True));  assert r.label == Layer.YELLOW and RuleId.Y2 in r.hit_rules

def test_Y3_two_weaknesses_normal_body_comp_is_yellow():
    # spec §6.1 空洞三的补齐
    r = stratify(mk(2, c=False)); assert r.label == Layer.YELLOW and RuleId.Y3 in r.hit_rules

def test_Y3_three_weaknesses_normal_body_comp_still_yellow():
    r = stratify(mk(3, c=False)); assert r.label == Layer.YELLOW and RuleId.Y3 in r.hit_rules

def test_Y4_declining_trend_upgrades_green_to_yellow():
    r = stratify(mk(0, c=False, trend=Trend.DECLINING))
    assert r.label == Layer.YELLOW and RuleId.Y4 in r.hit_rules

def test_Y4_does_not_fire_for_volatile_or_improving():
    for t in (Trend.VOLATILE, Trend.IMPROVING, Trend.STABLE):
        assert stratify(mk(0, c=False, trend=t)).label == Layer.GREEN

def test_trend_never_downgrades():
    # spec §6.1 空洞二：趋势只升级，永不降级
    assert stratify(mk(2, c=True, trend=Trend.IMPROVING)).label == Layer.RED

def test_G1_all_clear_is_green():
    r = stratify(mk(0, c=False)); assert r.label == Layer.GREEN and RuleId.G1 in r.hit_rules

def test_insufficient_data_when_valid_count_below_4():
    # Review Focus #2 / #5。**hit_rules 是 (Z0,) 而不是空元组**（Ruling 125）：
    # 空元组会让 explain() 的 hit_rules[-1] 抛 IndexError，而 Z0 路径恰恰是
    # 最需要向学生解释「为什么没有分层结果」的那一条。
    r = stratify(mk(0, c=False, valid=MIN_VALID_COUNT - 1))
    assert r.label == Layer.INSUFFICIENT and r.hit_rules == (RuleId.Z0,)
    assert "数据不足" in explain(r, mk(0, c=False, valid=MIN_VALID_COUNT - 1))

def test_valid_count_exactly_4_is_stratified():
    assert stratify(mk(0, c=False, valid=MIN_VALID_COUNT)).label == Layer.GREEN

def test_insufficient_data_beats_all_rules():
    assert stratify(mk(5, c=True, valid=2)).label == Layer.INSUFFICIENT

def test_explain_mentions_concrete_evidence():
    # spec §9.2 分层可解释性：文案须引用具体数值与该性别阈值
    d = mk(0, c=True, bf=22.4)
    txt = explain(stratify(d), d)
    assert "体脂率" in txt and "22.4" in txt and "20%" in txt

def test_explain_uses_female_threshold():
    d = mk(0, c=True, sex=Sex.FEMALE, bf=29.0)
    txt = explain(stratify(d), d)
    assert "28%" in txt and "女" in txt

def test_item_display_names_match_spec_4_2_verbatim():
    """Ruling 127：``ITEM_DISPLAY_NAMES`` 逐行等于 spec §4.2 计分项表的中文名。

    ``explain()`` 要靠它把 ``ScoredItem`` 渲染成 spec §9.2:641 示例文案里的
    「1000 米跑」「引体向上」——**两项名称随性别变**（男「1000 米跑」/ 女「800 米跑」、
    男「引体向上」/ 女「1 分钟仰卧起坐」），靠 ``item.value`` 拼不出来。
    期望值字面写在这里、不从被测常量读回（自证循环，本项目犯过两次）。
    """
    assert ITEM_DISPLAY_NAMES == {
        ScoredItem.BMI: {              # §4.2 第 1 行：BMI（身高/体重派生）
            Sex.MALE: "BMI", Sex.FEMALE: "BMI"},
        ScoredItem.VITAL_CAPACITY: {   # 第 2 行：肺活量
            Sex.MALE: "肺活量", Sex.FEMALE: "肺活量"},
        ScoredItem.SPRINT_50M: {       # 第 3 行：50 米跑
            Sex.MALE: "50 米跑", Sex.FEMALE: "50 米跑"},
        ScoredItem.SIT_AND_REACH: {    # 第 4 行：坐位体前屈
            Sex.MALE: "坐位体前屈", Sex.FEMALE: "坐位体前屈"},
        ScoredItem.STANDING_JUMP: {    # 第 5 行：立定跳远
            Sex.MALE: "立定跳远", Sex.FEMALE: "立定跳远"},
        ScoredItem.PULL_UP_OR_SIT_UP: {  # 第 6 行：引体向上（男）/ 1 分钟仰卧起坐（女）
            Sex.MALE: "引体向上", Sex.FEMALE: "1 分钟仰卧起坐"},
        ScoredItem.DISTANCE_RUN: {     # 第 7 行：1000 米跑（男）/ 800 米跑（女）
            Sex.MALE: "1000 米跑", Sex.FEMALE: "800 米跑"},
    }
