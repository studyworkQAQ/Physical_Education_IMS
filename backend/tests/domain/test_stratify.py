"""红黄绿分层引擎（spec §6.2 的八行决策表）与 ``explain()`` 可解释性文案的行为约束。

20 条测试分五组：

* 八条规则各至少一条（R1 / R2 / Y1×2 / Y2 / Y3×2 / Y4 / G1 / Z0），外加规则**优先级**
  两条（R1 先于 R2、Z0 先于全部）与「趋势只升级永不降级」一条（spec §6.1 空洞二）；
* ``valid_count`` 闸门的两条边界（``= 3`` 不分层、``= 4`` 照常分层，Review Focus #2 / #5）；
* ``explain()`` 的三条：具体数值与该性别阈值（spec §9.2）、女生阈值、Z0 路径的文案；
* ``ITEM_DISPLAY_NAMES`` 与 spec §4.2 计分项表逐行一致（Ruling 127）；
* **两条响亮失败**（Ruling 175，为把 ``app/domain/`` 的分支覆盖补到 100%）：
  ``WeaknessResult`` 的 ``count == len(items)`` 构造不变量，以及决策表残差行 ``G1``
  被摘掉时 :func:`stratify` 抛 ``RuntimeError`` 而不是静默给 ``None``。

期望值一律**字面写在这里**，不从被测常量读回来跟自己比——自证的常量测试等于没有测试
（``test_indicators.py`` 的 ``test_item_weights_match_spec_4_2_verbatim`` 是同一条纪律）。
"""
import pytest

from app.domain.stratify import (
    stratify, Layer, RuleId, RULE_ORDER, MIN_VALID_COUNT, explain,
)
from app.domain.derive import DerivedResult, WeaknessResult, BodyCompFlag, Trend
from app.domain.indicators import ITEM_DISPLAY_NAMES, WEAKNESS_ITEMS, ScoredItem, Sex


def mk(w, c=False, trend=Trend.STABLE, valid=6, dominant="endurance",
       sex=Sex.MALE, bf=22.4):
    # **与 Task 8 的实际产出对齐（Ruling 116，修正两处照抄源失效）**：
    # ① `WeaknessResult` **没有** `patterns` 参数（Ruling 98 已删），传它会
    #    `TypeError: __init__() got an unexpected keyword argument 'patterns'`；
    # ② `reasons` 的 token 是 **`"body_fat_high"`**，不是 `"body_fat_over"`
    #    （Ruling 97① 冻结的 vocabulary 只有 `body_fat_high` / `muscle_low` 两个）。
    # 两者都不会被 Task 9 自己的断言抓到——`mk()` 是测试助手，构造失败会在
    # **第一条**测试就 TypeError，看起来像 Task 9 写错了而不是助手过期了。
    # ③ `items` 必须是**真的 w 项**（Ruling 175）：此前恒传 `items=()`，于是
    #    `count=4` 配 `items=()` ——生产永不产生的状态（`find_weaknesses` 恒设
    #    `count=len(weak)` / `items=tuple(weak)`）。它当时唯一的后果是让 `_weakness_text`
    #    那条退化分支天天可达；分支已删，`__post_init__` 现在会当场 ValueError。
    #    取**前** w 项而不是随便 w 项：`WEAKNESS_ITEMS` 的声明序就是 `items` 的规范序。
    limit = 20.0 if sex == Sex.MALE else 28.0
    return DerivedResult(
        sex=sex,
        trend=trend,
        weakness=WeaknessResult(items=tuple(WEAKNESS_ITEMS[:w]), count=w,
                                valid_count=valid, dominant_bucket=dominant),
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


def test_weakness_result_rejects_count_that_disagrees_with_items():
    """Ruling 175：``count == len(items)`` 是构造不变量，违反就**当场** ``ValueError``。

    它守的是 ``_weakness_text`` 那条**已删除**的退化分支（``items`` 为空而 ``count > 0``
    → 只报项数）。删分支而不钉不变量，等于允许下一个调用方（Plan 02 的 API 层、重算脚本、
    另一个测试助手）再造出同一个生产永不产生的状态——那时它不再报错，只是决策表按
    ``count`` 判成红/黄层，而学生看到的文案说「0 项短板」。

    本条同时是 ``mk()`` 那处修正（③）的守卫：把 ``items=()`` 改回去，上面 18 条测试会
    在**第一条**就 ValueError，看起来像 Task 9 全坏了而不是助手造了假对象。
    """
    with pytest.raises(ValueError, match=r"必须等于 len\(items\)"):
        WeaknessResult(items=(), count=2, valid_count=6, dominant_bucket="endurance")
    # 合法的那一侧（生产构造点 ``find_weaknesses`` 的形状）不得被误伤
    assert WeaknessResult(items=tuple(WEAKNESS_ITEMS[:2]), count=2,
                          valid_count=6, dominant_bucket="endurance").count == 2


def test_stratify_fails_loudly_when_the_residual_rule_is_gone(monkeypatch):
    """Ruling 175：末尾那句 ``RuntimeError`` **不用 ``pragma: no cover``**，用 monkeypatch 覆盖。

    按构造它是残差行（决策表完备，见 ``_HOLDS`` 的注释），正常输入下永不可达——但它的
    **全部价值**就是「残差行若被人删掉，要大声失败而不是静默给出错答案」，而 Ruling
    64a/115 那两次事故正是「残差行不残差」。给一个「守不可达代码」的分支挂 pragma 等于
    承认它守不住任何东西。这里把 ``G1`` 从 ``RULE_ORDER`` 里摘掉，制造出
    「``W=0 ∧ ¬C`` 无人接手」的局面。

    ``RULE_ORDER`` **可以干净地 monkeypatch**：``stratify()`` 在调用时读模块全局
    （``for rule in RULE_ORDER:``），而 ``app/`` 里没有任何一处 ``from ... import
    RULE_ORDER`` 把它拷进别的命名空间（全仓只有 ``tests/db/test_models.py:14`` 那样导入，
    与本测试无关），故不需要退到 pragma。
    """
    monkeypatch.setattr(
        "app.domain.stratify.RULE_ORDER",
        tuple(rule for rule in RULE_ORDER if rule is not RuleId.G1),
    )
    with pytest.raises(RuntimeError) as exc:
        stratify(mk(0, c=False))          # W=0、¬C、valid=6、趋势稳定 → 只有 G1 会接手
    msg = str(exc.value)
    # 消息必须自带定位信息：残差行缺失时，运维看到的只有这一行
    for token in ("W=0", "C=False", "valid_count=6", "trend=稳定", "残差行 G1 是否还在？"):
        assert token in msg, msg
