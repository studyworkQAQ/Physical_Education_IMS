"""``app/domain/report.py`` 的行为约束（Plan 03 Task 8，**支 I 是 Plan 03 Task 9 加的**）。

**分九支**，每支钉一件不同的事：

* **支 A（词表与阈值的单一所有者）**：分层词表与预警级别词表**不重述**，
  而是从 :class:`app.domain.stratify.Layer` 与 :class:`app.domain.alerts.AlertLevel`
  派生；大屏那两个阈值与预警那两个阈值**刻意不同**（spec §14 #11「两套并存」）；
  「算法建议」的 10% 与 spec §8.4 的「减量 20%」**刻意不同**（简报 Task 8「决定」第 1 条）。
* **支 B（分层分布与周环比流动）**：**上一周没有快照 → ``flow`` 全 0 且
  ``has_previous`` 为假**（简报逐字：「『不知道』不得讲成『变化了』」）；
  「本周才出现的人」与「本周消失的人」**不与「换层」混成一档**。
* **支 C（人均 RPE）**：``None`` = 判不了、不是 0；周级均值是**按提交数加权**的，
  与 :func:`app.pipeline.alert_stage.evaluate_alerts` 里那一份班级均值**逐字相等**
  （两处并存、由一条测试钉住，先例是 ``AlertLevel`` ↔ ``Alert.LEVELS``）。
* **支 D（按层分组的打卡完成率）**：一层里一个可测的人都没有 → ``rate`` 是
  ``None`` 而不是 ``0.0``。
* **支 E（进步榜）**：Top10 截断、退步名单不截断、变化恰为 0 的**两个榜都不进**
  但**被计数**、上一次得分为 0 / 缺测的一律 ``unmeasured``（除零与「无穷大改善」都不接受）。
* **支 F（预警汇总）**：级别 × 状态**双稠密**（计数为 0 的格子也在），
  于是「本周没有红牌」与「本周没跑」不同形。
* **支 G（算法建议）**：一条查表规则的三档 + 优先级 + ``< 5`` 的**严格**边界。
* **支 H（大屏异常名单）**：用的是**大屏自己的**两个阈值，与预警那两个不同。
* **支 I（二次小测的标准化得分，Plan 03 Task 9 从 api 层搬进来）**：spec §8.1 的三格算式
  （深蹲得分 = 次数 / 折返得分 = **班内百分位反查** / 综合分 = 两项等权平均）、
  并列取中点、``n = 1`` 给 50.0、空样本**响亮地**除零、缺测一律 ``None`` 而不是 0、
  ``composite`` 用**未 round 的**百分位算完再 round（那个 ``56.665`` 浮点坑），
  以及**全仓只有一份定义**（AST 数定义份数）。

⚠️ 断言两侧不同源（硬规矩 #35）：期望值一律**字面**写在测试里
（``"red"`` / ``3`` / ``8`` / ``10`` / ``5.0`` / ``"本周建议整体降量 10%"`` / 那些学生 id），
**不从被测模块读回来**。支 A 里那几条「与另一个所有者对账」的测试，另一侧一律是
**别的模块**（``alert_rules.yaml`` / ``alert_stage`` / ``api.routers.feedback``），
不是 ``report`` 自己。
"""
import ast
import pathlib

import pytest

from app.domain.report import (
    CLASS_RPE_LOW_MAX,
    LAYERS,
    LEVELS,
    PCT_PRECISION,
    PROGRESS_BOARD_TOP_N,
    RATE_PRECISION,
    REASON_CHECKIN_GAP,
    REASON_RPE_HIGH,
    RPE_PRECISION,
    RpeWeek,
    SCREEN_GAP_DAYS,
    SCREEN_RPE_MAX,
    SCORE_PRECISION,
    SUGGESTION_HOLD,
    SUGGESTION_INCREASE,
    SUGGESTION_REDUCE,
    SUGGESTION_STEP_PCT,
    abnormal_roster,
    alert_summary,
    checkin_rate_by_layer,
    daily_mean_rpe,
    layer_distribution,
    layer_flow,
    mini_test_scores,
    progress_board,
    rpe_summary,
    shuttle_percentile,
    suggestion,
    week_mean_rpe,
)

BACKEND = pathlib.Path(__file__).resolve().parents[2]

#: 三个处置状态的字面量。⚠️ **期望侧刻意写字面量**（硬规矩 #35）：
#: 它是 :func:`alert_summary` 的 ``statuses`` 入参，本文件不从 ``alert_stage`` 读回来。
STATUSES = ("pending", "handled", "ignored")

#: 一周七天的 ISO 串（2025-09-08 是周一、2025-09-14 是周日；学期第 2 周）。
WEEK2 = tuple(f"2025-09-{day:02d}" for day in range(8, 15))
#: 上一周（学期第 1 周，2025-09-01 是周一）。
WEEK1 = tuple(f"2025-09-{day:02d}" for day in range(1, 8))


# ===========================================================================
# 支 A：词表与阈值的单一所有者
# ===========================================================================


def test_the_layer_vocabulary_is_derived_from_the_stratify_owner():
    """``LAYERS`` **逐字等于** :class:`app.domain.stratify.Layer` 的声明序。

    ⚠️ 期望侧是**字面量**，不是 ``Layer``（否则两侧同源、恒绿）。
    它钉的是两件事：① 四个值一个不多一个不少（``insufficient_data`` 也在——
    一个数据不足的学生**不是**绿层，把他从饼图里抹掉会让分母对不上）；
    ② 顺序是 ``Layer`` 的声明序（饼图与图例的行序因此稳定）。
    """
    assert LAYERS == ("red", "yellow", "green", "insufficient_data")


def test_the_alert_level_vocabulary_is_derived_from_the_alerts_owner():
    """``LEVELS`` **逐字等于** :class:`app.domain.alerts.AlertLevel` 的声明序。

    ⚠️ 它是**三个**、不含 ``insufficient_data``：预警级别与分层标签是两套词表，
    共用一份会让「本周 0 条绿牌」与「本周 0 个绿层学生」在同一个键下打架。
    """
    assert LEVELS == ("red", "yellow", "green")


def test_the_screen_thresholds_are_not_the_alert_thresholds():
    """**spec §14 #11「两套并存」**：大屏的筛选阈值与预警的判据阈值**刻意不同**。

    spec §9.1 逐字记录了指导文件的内部矛盾：大屏「连续 **3** 天未打卡 | RPE > **8**」，
    预警「中断 **2** 天、RPE 连续 ≥ **9**」。裁定是「预警 = 正式工单（阈值严），
    大屏 = 宽松展示筛选器（阈值松，只展示不派单）」。

    ⚠️ 本条的两侧来自**两个不同的所有者**：大屏那两个是本模块的常量，
    预警那两个是 ``data/alert_rules.yaml`` 经 :mod:`app.refdata_alerts` 加载的。
    把它们改成相等 → 本条当场红，而那正是「两套并存」被悄悄合并的形状。
    """
    from app.refdata_alerts import alert_rules

    rules = alert_rules()
    assert SCREEN_GAP_DAYS == 3
    assert SCREEN_RPE_MAX == 8
    assert rules.params_of("YELLOW_CHECKIN_GAP")["gap_days"] == 2
    assert rules.params_of("RED_RPE_SUSTAINED")["rpe_min"] == 9
    assert SCREEN_GAP_DAYS != rules.params_of("YELLOW_CHECKIN_GAP")["gap_days"]
    assert SCREEN_RPE_MAX != rules.params_of("RED_RPE_SUSTAINED")["rpe_min"]


def test_the_suggestion_step_is_ten_percent_and_the_auto_reduction_is_twenty():
    """**10% 与 20% 的不对称是有意的**（简报 Task 8「决定」第 1 条逐字要求写清）。

    20% 是**红色预警对单个学生**的处置（spec §8.4，系统**自动执行**）；
    10% 是**班级级建议**（给教师看的，**不自动执行**），故更温和。
    ⚠️ 本条把「它们不相等」钉住：把 :data:`SUGGESTION_STEP_PCT` 改成 20 会让
    教师端与自动减量给出同一个数，而那时「建议」与「已经执行」在界面上无从区分。
    """
    from app.pipeline.alert_stage import AUTO_REDUCTION_FACTOR

    assert SUGGESTION_STEP_PCT == 10
    assert AUTO_REDUCTION_FACTOR == 0.8
    assert SUGGESTION_STEP_PCT != int(round((1.0 - AUTO_REDUCTION_FACTOR) * 100))


def test_the_three_suggestion_strings_are_the_lookup_table():
    """三个字符串**逐字**（它们会落进 ``weekly_class_report.suggestion`` 那一列，
    是给人看的一句话，故字面量就是契约）。

    ⚠️ 那两个百分比由 :data:`SUGGESTION_STEP_PCT` 生成、不手写第二遍：
    改一个数而忘了改文案，教师看到的建议就与系统据以判的数不符。
    """
    assert SUGGESTION_REDUCE == "本周建议整体降量 10%"
    assert SUGGESTION_INCREASE == "本周建议整体加量 10%"
    assert SUGGESTION_HOLD == "维持当前强度"
    assert CLASS_RPE_LOW_MAX == 5.0


def test_the_two_precisions_match_their_counterparts_in_the_api_layer():
    """两个 round 精度各自与**已有的那一处**对齐（两处并存、由本条钉成相等）。

    * ``RATE_PRECISION`` ↔ :data:`app.api.routers.feedback.RATE_PRECISION`：
      同一个量（打卡完成率）在学生端端点与班级周报里必须给到同一个精度，
      否则教师大屏上的「红层 83%」与学生首页上的「83.33%」会被当成两个数。
    * ``RPE_PRECISION`` / ``PCT_PRECISION`` 是**本模块自己的**显示精度
      （RPE 曲线与进步榜的百分比），api 层今天没有对应物，故只钉字面量。

    ⚠️ domain **不能** import ``app.api``（:mod:`tests.architecture.test_layering`
    的反向那一圈），故这里是「两份并存 + 一条测试钉住」，与
    ``AlertLevel`` ↔ ``Alert.LEVELS`` 是同一种处置。
    """
    from app.api.routers.feedback import RATE_PRECISION as ENDPOINT_RATE_PRECISION

    assert RATE_PRECISION == 4
    assert RATE_PRECISION == ENDPOINT_RATE_PRECISION
    assert RPE_PRECISION == 2
    assert PCT_PRECISION == 2


def test_the_progress_board_cap_is_ten():
    """``PROGRESS_BOARD_TOP_N == 10``（spec §8.5 逐字「进步榜 Top10」）。"""
    assert PROGRESS_BOARD_TOP_N == 10


# ===========================================================================
# 支 B：分层分布与周环比流动
# ===========================================================================


def test_layer_distribution_is_dense_over_the_four_labels():
    """**四个标签一律出现**，计数为 0 的也在。

    ⚠️ 与 :attr:`app.pipeline.alert_stage.AlertReport.by_level` 的**稀疏**口径刻意相反，
    理由也相反：那一处「以 0 入字典会让『今天没有红牌』与『今天没跑』同形」，
    而**一份周报的存在本身就是「跑过了」的证据**，且饼图要的是四条固定的扇区
    （少一条，前端就得自己补 0，那才是第二个所有者）。
    """
    got = layer_distribution(
        {1: "red", 2: "red", 3: "green", 4: "insufficient_data"}, None
    )
    assert got["by_layer"] == {
        "red": 2, "yellow": 0, "green": 1, "insufficient_data": 1,
    }


def test_layer_distribution_of_a_class_nobody_was_stratified_in_is_all_zeros():
    """空班 → 四个 0，而**不是**一个空字典（前端不必防 ``KeyError``）。"""
    got = layer_distribution({}, None)
    assert got["by_layer"] == {
        "red": 0, "yellow": 0, "green": 0, "insufficient_data": 0,
    }


def test_the_first_week_has_no_previous_snapshot_and_the_flow_is_all_zero():
    """**简报 Task 8「决定」第 2 条逐字**：上一周没有快照（学期第一周）→
    ``flow`` 全 0 且 ``layer_distribution_prev`` 为 ``null``。

    ⚠️ 失效形态是「不知道」被讲成「变化了」：把 ``previous=None`` 当成
    「上周一个人都没有」，全班就会显示成「本周升入 40 人」，
    而教师看到的是一句**凭空捏造的进步**。
    """
    empty = {layer: [] for layer in LAYERS}
    got = layer_distribution({1: "red", 2: "green"}, None)
    assert got["previous"] is None
    assert got["flow"] == {
        "has_previous": False,
        "entered": empty,
        "left": empty,
        "appeared": empty,
        "disappeared": empty,
    }


def test_a_student_who_changed_layer_is_counted_as_entered_and_left():
    """换层的人**同时**进新层的 ``entered`` 与旧层的 ``left``（一次流动的两半）。"""
    got = layer_flow({1: "green", 2: "red"}, {1: "red", 2: "red"})
    assert got["has_previous"] is True
    assert got["entered"] == {
        "red": [], "yellow": [], "green": [1], "insufficient_data": [],
    }
    assert got["left"] == {
        "red": [1], "yellow": [], "green": [], "insufficient_data": [],
    }
    assert got["appeared"] == {
        "red": [], "yellow": [], "green": [], "insufficient_data": [],
    }
    assert got["disappeared"] == {
        "red": [], "yellow": [], "green": [], "insufficient_data": [],
    }


def test_a_student_who_stayed_in_the_same_layer_is_in_neither_roster():
    """没换层的人**两个名单都不进**：把他算进 ``entered`` 会让「本周流动 40 人」
    在一个一个人都没动的班里成立。

    ⚠️ **标签刻意用 ``"".join(...)`` 现拼、不用字面量**：两个字面量 ``"yellow"``
    在 CPython 里是**同一个驻留对象**，于是「按值比」与「按身份比」给出同一个答案，
    而生产路径上的标签是从 SQLite 读回来的**两个不同的 str 对象**。
    用现拼的串才让本条真的钉住 :func:`layer_flow` 用的是 ``!=`` 而不是 ``is not``
    （后者会让**全班每个人都算成换过层**，而全链路不报错）。
    变异取证 M23 亲跑：``!=`` → ``is not`` 在本条上 killed。
    """
    got = layer_flow({7: "".join(["yel", "low"])}, {7: "".join(["yell", "ow"])})
    assert got["entered"]["yellow"] == []
    assert got["left"]["yellow"] == []
    assert got["has_previous"] is True


def test_a_student_who_only_shows_up_this_week_is_appeared_not_entered():
    """**本周才出现**（上周没有分层行）与**本周消失**各占一档，不与「换层」混。

    ⚠️ 混了的失效形态：一个转学进来的学生会被算成「升入绿层 1 人」，
    而教师读到的是「有一个人从别的层进步到了绿层」——那不是发生的事。
    代价（硬规矩 #39）：``entered`` / ``left`` 因此**不能**用来核对
    「本周人数 = 上周人数 − left + entered」，那个恒等式要连
    ``appeared`` / ``disappeared`` 一起算，本模块**不替前端做这一步**。

    三个学生各占一档：1 只在本周、3 只在上周、2 两周都在但换了层。
    """
    got = layer_flow({1: "green", 2: "red"}, {2: "yellow", 3: "green"})
    assert got["appeared"] == {
        "red": [], "yellow": [], "green": [1], "insufficient_data": [],
    }
    assert got["disappeared"] == {
        "red": [], "yellow": [], "green": [3], "insufficient_data": [],
    }
    # 学生 2 上周在 yellow、本周在 red → 一次真实的换层，两个名单都进
    assert got["entered"]["red"] == [2]
    assert got["left"]["yellow"] == [2]
    # ⚠️ 而学生 1 与 3 **既不在** entered **也不在** left
    assert got["entered"]["green"] == []
    assert got["left"]["green"] == []


def test_the_flow_rosters_are_sorted_by_student_id():
    """名单**按学生 id 升序**：``dict`` 的迭代序是插入序，而插入序取决于调用方
    拼装 ``labels`` 的顺序（那是一次 SQL 的结果序）。不排序的话，同一份数据
    两次生成的周报会给出两个不同顺序的名单，而
    ``tests/pipeline/test_daily.py`` 那种「跑两遍逐字相等」的幂等断言就会红。

    ⚠️ **学生 id 取 ``1 / 2 / 16`` 是实测挑出来的反例**（硬规矩 #107：用谓词挑对象
    之前先对一个已知反例验证谓词）。``layer_flow`` 遍历的是
    ``set(labels_now) | set(labels_prev)``，而 CPython 的 set 迭代序是**槽位序**
    （``hash(int) == int``，故落槽 = ``值 % 表长``），它与升序**通常**不同、
    但**不总是**不同：实测 ``{9, 3, 6}`` 的并集迭代序恰好是 ``[3, 6, 9]``
    = 升序，用它写本条会让「去掉 ``sorted``」这个变异**存活**。
    ``{1, 2, 16}`` 的并集迭代序实测是 ``[16, 1, 2]`` ≠ ``[1, 2, 16]``，故它有牙
    （变异取证 M13 亲跑：换成 1/2/16 之后 killed）。
    """
    got = layer_flow({1: "green", 2: "green", 16: "green"},
                     {1: "red", 2: "red", 16: "red"})
    assert got["entered"]["green"] == [1, 2, 16]
    assert got["left"]["red"] == [1, 2, 16]


# ===========================================================================
# 支 C：人均 RPE
# ===========================================================================


def test_daily_mean_rpe_puts_none_on_a_day_without_submissions():
    """**没交快评的那一天是 ``None``、不是一个 0 值的点**。

    ⚠️ 失效形态：把空日画成 0，折线会在周三掉到 0 再弹回 7，
    而教师读到的是「周三全班疲劳度骤降」——那天只是没上课。
    """
    got = daily_mean_rpe(
        WEEK2, {"2025-09-08": [6, 8], "2025-09-10": [7]},
    )
    assert got == [
        {"day": "2025-09-08", "mean": 7.0, "submissions": 2},
        None,
        {"day": "2025-09-10", "mean": 7.0, "submissions": 1},
        None, None, None, None,
    ]


def test_daily_mean_rpe_of_an_empty_day_list_is_an_empty_curve():
    """一天都不给 → 空曲线（不是 ``None``：曲线的**长度**由 ``days`` 决定，
    而 ``days`` 恒是那 7 天，故这一档只在调用方传空序列时出现）。"""
    assert daily_mean_rpe((), {"2025-09-08": [6]}) == []


def test_week_mean_rpe_is_submission_weighted_not_the_mean_of_daily_means():
    """**周级「人均 RPE」= 全部提交的算术均值**（按提交数加权），不是日均值再平均。

    ⚠️ 两个口径在「每天交的人数不同」时**不相等**，本条正是用这样一份数据钉住它：
    周一 1 个人交 10、周二 3 个人各交 6 → 加权 ``(10+6+6+6)/4 = 7.0``，
    而「日均值再平均」是 ``(10.0 + 6.0)/2 = 8.0``。
    选加权的理由：spec §8.5 写的是「**人均** RPE」，人均的分母是**人次**；
    而 :func:`app.pipeline.alert_stage.evaluate_alerts` 给
    ``YELLOW_CLASS_RPE_HIGH`` 喂的就是全部提交的算术均值，两处必须同一个数
    （守卫见 :func:`test_week_mean_rpe_agrees_with_the_class_level_alert_formula`）。
    """
    week = RpeWeek(
        days=WEEK2,
        values={"2025-09-08": [10], "2025-09-09": [6, 6, 6]},
    )
    assert week_mean_rpe(week) == 7.0


def test_week_mean_rpe_of_a_week_without_submissions_is_none():
    """本周一次快评都没有 → ``None``（**不是 0.0**：0 是「测了、一点都不累」，
    与「没测」是两件事，而后者正是 :func:`suggestion` 要放行的那一档）。"""
    assert week_mean_rpe(RpeWeek(days=WEEK2, values={})) is None
    assert week_mean_rpe(RpeWeek(days=WEEK2, values={"2025-09-08": []})) is None


def test_week_mean_rpe_agrees_with_the_class_level_alert_formula():
    """**两个所有者钉成相等**：本模块的周级均值与预警阶段喂给
    ``YELLOW_CLASS_RPE_HIGH`` 的那一份班级均值是同一个数。

    ⚠️ 期望侧**在测试里重算一遍**（``sum(...) / len(...)``），不 import
    ``alert_stage`` 的那一行（它是 ``evaluate_alerts`` 体内的一个内联表达式，
    抽不出来）。两侧同源的话本条恒绿、什么都不钉。
    ⚠️ 不一致的失效形态：大屏上写「本周人均 RPE 6.9」，而同一周的班级黄牌
    却按 7.1 触发了 —— 教师会认为系统算错了。
    """
    raw = [9, 9, 10, 8, 7]
    week = RpeWeek(
        days=WEEK2,
        values={"2025-09-08": raw[:3], "2025-09-11": raw[3:]},
    )
    expected = sum(raw) / len(raw)
    assert week_mean_rpe(week) == pytest.approx(expected)
    # 而它确实越过了 alert_rules.yaml 里那一条 7.0 的线
    from app.refdata_alerts import alert_rules

    assert expected > alert_rules().params_of("YELLOW_CLASS_RPE_HIGH")["mean_rpe_max"]


def test_rpe_summary_without_a_previous_week_leaves_the_three_comparisons_null():
    """学期第一周：``previous_curve`` / ``previous_mean`` / ``delta`` 一律 ``None``。"""
    got = rpe_summary(RpeWeek(days=WEEK2, values={"2025-09-08": [6, 8]}), None)
    assert got["previous_curve"] is None
    assert got["previous_mean"] is None
    assert got["delta"] is None
    assert got["mean"] == 7.0
    assert got["curve"][0] == {"day": "2025-09-08", "mean": 7.0, "submissions": 2}


def test_rpe_summary_delta_is_this_week_minus_last_week():
    """``delta`` = 本周 − 上周（**符号承重**：正数是「更累了」）。"""
    current = RpeWeek(days=WEEK2, values={"2025-09-08": [8, 8]})
    previous = RpeWeek(days=WEEK1, values={"2025-09-01": [6, 7]})
    got = rpe_summary(current, previous)
    assert got["mean"] == 8.0
    assert got["previous_mean"] == 6.5
    assert got["delta"] == 1.5
    assert got["previous_curve"][0] == {"day": "2025-09-01", "mean": 6.5, "submissions": 2}


def test_rpe_summary_delta_is_null_when_either_side_is_unmeasurable():
    """两侧任一侧 ``None`` → ``delta`` 是 ``None``，**不是 0.0**
    （0.0 会被读成「与上周持平」）。"""
    assert rpe_summary(RpeWeek(days=WEEK2, values={}), None)["delta"] is None
    empty = RpeWeek(days=WEEK2, values={})
    full = RpeWeek(days=WEEK1, values={"2025-09-01": [6]})
    assert rpe_summary(empty, full)["delta"] is None
    assert rpe_summary(empty, full)["previous_mean"] == 6.0
    assert rpe_summary(full, empty)["delta"] is None
    assert rpe_summary(full, empty)["mean"] == 6.0


# ===========================================================================
# 支 D：按层分组的打卡完成率
# ===========================================================================


def test_the_layer_rate_is_the_mean_of_the_measured_students_rates():
    """一层里可测的那些人的**完成率均值**（每人等权）。

    ⚠️ 口径决定与代价（硬规矩 #39）：**每人等权**，不是「全班完成天数 /
    全班应打卡天数」。后者要给每个学生先算出分母（= 装配他的处方训练包），
    而等权均值只要一个已经算好的比率。代价是一个每周练 2 天的绿层学生与
    一个每周练 5 天的红层学生在均值里**同样重**；``measured`` 与 ``students``
    两格因此都在载荷里，读的人能看出这一层的样本有多大。
    """
    got = checkin_rate_by_layer(
        {1: 1.0, 2: 0.5, 3: 0.0}, {1: "red", 2: "red", 3: "green"},
    )
    assert got["red"] == {"students": 2, "measured": 2, "rate": 0.75}
    assert got["green"] == {"students": 1, "measured": 1, "rate": 0.0}
    assert got["yellow"] == {"students": 0, "measured": 0, "rate": None}
    assert got["insufficient_data"] == {"students": 0, "measured": 0, "rate": None}


def test_a_layer_nobody_could_be_measured_in_reports_none_not_zero():
    """一层里**一个可测的人都没有** → ``rate`` 是 ``None``、不是 ``0.0``。

    ⚠️ 这是「判不了」与「0% 完成率」的分界：后者是 spec 逐字点名的
    「RCT 关键过程指标」，写成 0.0 等于在报表上断言「这一层一个人也没练」。
    """
    got = checkin_rate_by_layer({1: None, 2: None}, {1: "yellow", 2: "yellow"})
    assert got["yellow"] == {"students": 2, "measured": 0, "rate": None}


def test_a_student_without_a_rate_still_counts_towards_the_layer_size():
    """``rates`` 里查无此人 → 计入 ``students``、不计入 ``measured``。

    ⚠️ 与「显式给了 ``None``」同档：两者都是「判不了」，
    而 ``students`` 要的是**这一层有多少人**（分母），不是「有多少人测到了」。
    """
    got = checkin_rate_by_layer({1: 0.8}, {1: "green", 2: "green"})
    assert got["green"] == {"students": 2, "measured": 1, "rate": 0.8}


def test_a_student_without_a_label_is_ignored():
    """``rates`` 里有、``labels`` 里没有 → **整条忽略**（没有层可归）。

    ⚠️ 那一档在真实数据里是「本周有打卡、但当日的分层行是
    ``insufficient_data`` 之外的缺失」，静默忽略好过凭空造一个
    ``"(unlabelled)"`` 键——那会是 :data:`LAYERS` 之外的第五个键，
    而 DB 的 ``ck_stratification_result_label`` 正好就是为了挡住它。
    """
    got = checkin_rate_by_layer({1: 1.0, 2: 0.5}, {1: "red"})
    assert got["red"] == {"students": 1, "measured": 1, "rate": 1.0}
    assert sum(bucket["students"] for bucket in got.values()) == 1


def test_the_layer_rate_is_rounded_to_the_endpoint_precision():
    """``rate`` round 到 :data:`RATE_PRECISION` 位（1/3 → ``0.3333``）。

    ⚠️ 这一格要落进 ``weekly_class_report.checkin_rate_by_layer`` 那一列并被读回来，
    一个 ``0.3333333333333333`` 会让同一份数据在两次生成后**逐字不等**
    （浮点尾数随求和顺序漂），而幂等断言比的是逐字相等。
    """
    got = checkin_rate_by_layer({1: 1.0, 2: 0.0, 3: 0.0}, {1: "red", 2: "red", 3: "red"})
    assert got["red"]["rate"] == 0.3333


# ===========================================================================
# 支 E：进步榜
# ===========================================================================


def _scores(count: int, older: float, step: float) -> dict:
    """``count`` 个学生的 ``(上次, 本次)`` 得分，第 i 个的相对变化是 ``step × i``。"""
    return {
        student_id: (older, older * (1.0 + step * student_id))
        for student_id in range(1, count + 1)
    }


def test_the_board_caps_the_improvers_at_ten_and_reports_the_cap():
    """**Top10 截断**（spec §8.5 逐字），且 ``top_n`` 一并落进载荷。

    ⚠️ ``top_n`` 不是常量的回声：周报是**存下来再读回来**的，
    若明年把 10 改成 20，一份旧的 ``top`` 只有 10 项就无从分辨
    「当时只截了 10 个」与「当时只有 10 个人进步」。口径与
    ``alert.trigger_snapshot["alert_rules_version"]`` 逐字同一条。
    """
    got = progress_board(_scores(25, 60.0, 0.01))
    assert got["top_n"] == 10
    assert len(got["top"]) == 10
    assert got["top"][0] == {"student_id": 25, "change_pct": 25.0}
    assert got["top"][-1] == {"student_id": 16, "change_pct": 16.0}


def test_the_regressed_roster_is_sorted_worst_first_and_is_not_capped():
    """退步名单**不截断**、按「退得最多」在前（spec §8.5 只给进步榜点了 Top10）。"""
    got = progress_board(_scores(15, 60.0, -0.01))
    assert len(got["regressed"]) == 15
    assert got["regressed"][0] == {"student_id": 15, "change_pct": -15.0}
    assert got["regressed"][-1] == {"student_id": 1, "change_pct": -1.0}
    assert got["top"] == []


def test_a_student_who_did_not_move_is_in_neither_roster_but_is_counted():
    """变化恰为 0 的**两个榜都不进**（进步榜里一个 0% 会挤掉一个真的进步的人），
    但计入 ``unchanged``——**不静默丢掉**（他确实被测了、也确实没变）。

    ⚠️ ``unchanged`` 由减法得出而不是第三个循环：``len(changed) − len(top 截断前)
    − len(regressed)``，故它与两个榜**不可能对不上**。
    """
    got = progress_board({1: (60.0, 60.0), 2: (60.0, 66.0), 3: (60.0, 54.0)})
    assert [entry["student_id"] for entry in got["top"]] == [2]
    assert [entry["student_id"] for entry in got["regressed"]] == [3]
    assert got["unchanged"] == 1
    assert got["unmeasured"] == 0


def test_a_tiny_change_that_rounds_to_zero_counts_as_unchanged():
    """**代价如实记录**（硬规矩 #39）：变化率 round 到 :data:`PCT_PRECISION` 位后
    成 0.0 的（``0.004%``）落进 ``unchanged``，不进任何一个榜。
    那一档在真实数据里是「两次小测几乎一样」，把他从进步榜里剔掉是对的；
    而一个刚好越过 ``0.005%`` 的会进榜——**边界由 round 决定，不由一个额外阈值决定**。
    """
    got = progress_board({1: (100.0, 100.00004), 2: (100.0, 100.01)})
    assert got["unchanged"] == 1
    assert [entry["student_id"] for entry in got["top"]] == [2]


@pytest.mark.parametrize(
    "pair",
    [(None, 60.0), (60.0, None), (None, None), (0.0, 60.0)],
    ids=["上次缺测", "本次缺测", "两次都缺测", "上次是零分"],
)
def test_an_unmeasurable_pair_never_reaches_a_roster(pair):
    """四档「判不了」一律进 ``unmeasured``，**不进榜**。

    ⚠️ 「上次是零分」那一档是承重的：相对变化的分母是 ``abs(old)``，
    ``old = 0`` 会让它无定义；把它当成「无穷大改善」会让一个从 0 分做到
    1 分的学生永远霸榜。口径与
    :func:`app.pipeline.alert_stage._mini_test_improved` 逐字相同
    （那一处的 docstring 也点名了同一个失效形态）。
    """
    got = progress_board({1: pair, 2: (60.0, 66.0)})
    assert got["unmeasured"] == 1
    assert [entry["student_id"] for entry in got["top"]] == [2]
    assert got["unchanged"] == 0


def test_the_relative_change_is_signed_by_direction_not_by_magnitude():
    """变化率带符号：涨是正、跌是负。分母取 ``abs(old)``，故一个**负的**上次得分
    （``normalized_score`` 今天不做值域校验）也不会把方向翻过来。

    ⚠️ 分母若写成裸的 ``old``，``old = -50`` 会让「从 −50 涨到 −40」算成
    ``10 / -50 = -20%``（一个进步被报成退步），而全链路不报错。
    """
    got = progress_board({1: (-50.0, -40.0), 2: (-50.0, -60.0)})
    assert got["top"] == [{"student_id": 1, "change_pct": 20.0}]
    assert got["regressed"] == [{"student_id": 2, "change_pct": -20.0}]
    assert got["unmeasured"] == 0


def test_ties_are_broken_by_student_id():
    """并列的变化率**按学生 id 升序**：``sorted`` 是稳定排序，而输入序来自
    ``dict`` 的插入序（= 一次 SQL 的结果序），不打 tie-breaker 的话同一份数据
    两次生成的榜会不同序，幂等断言就会红。"""
    got = progress_board({5: (60.0, 66.0), 2: (60.0, 66.0), 9: (60.0, 66.0)})
    assert [entry["student_id"] for entry in got["top"]] == [2, 5, 9]


def test_an_empty_class_produces_an_empty_board():
    """一个人都没测 → 两个空榜 + 两个 0（而 ``top_n`` 仍然是 10）。"""
    got = progress_board({})
    assert got == {
        "top_n": 10, "top": [], "regressed": [], "unchanged": 0, "unmeasured": 0,
    }


# ===========================================================================
# 支 F：预警汇总
# ===========================================================================


def test_alert_summary_is_dense_over_levels_and_statuses():
    """**级别 × 状态双稠密**：9 个格子一个不缺。

    ⚠️ 与 :func:`layer_distribution` 同一条理由，而这里更承重：spec §8.5 逐字要
    「红/黄/绿各若干，**已处理/待处理**」，少一个格子，教师端就没法回答
    「本周有没有还没处理的红牌」——而那个答案是**要不要加班**的判据。
    """
    got = alert_summary(
        [("red", "pending"), ("red", "handled"), ("yellow", "pending"),
         ("green", "ignored"), ("green", "pending")],
        statuses=STATUSES,
    )
    assert got == {
        "red": {"pending": 1, "handled": 1, "ignored": 0},
        "yellow": {"pending": 1, "handled": 0, "ignored": 0},
        "green": {"pending": 1, "handled": 0, "ignored": 1},
    }


def test_alert_summary_of_a_week_without_alerts_is_all_zeros():
    """本周一条预警都没有 → 9 个 0（**不是**一个空字典，也不是 ``None``）。"""
    assert alert_summary([], statuses=STATUSES) == {
        "red": {"pending": 0, "handled": 0, "ignored": 0},
        "yellow": {"pending": 0, "handled": 0, "ignored": 0},
        "green": {"pending": 0, "handled": 0, "ignored": 0},
    }


def test_alert_summary_rejects_a_level_or_a_status_outside_the_vocabulary():
    """词表外的一格 → ``KeyError``（**响亮失败**，不是静默丢掉）。

    ⚠️ 静默丢掉的失效形态：``level`` 拼成 ``"Red"`` 的那一条预警会从汇总里消失，
    而 9 个格子的和**看起来**仍然正常（教师端不会去核对它与 ``alert`` 表的行数）。
    """
    with pytest.raises(KeyError):
        alert_summary([("crimson", "pending")], statuses=STATUSES)
    with pytest.raises(KeyError):
        alert_summary([("red", "archived")], statuses=STATUSES)


def test_the_status_vocabulary_is_passed_in_not_declared_here():
    """**``statuses`` 由调用方注入**，本模块不声明第三个住址。

    值域的所有者是 :attr:`app.db.models.feedback.Alert.STATUSES`（+ DB 的
    ``ck_alert_status``），生产写入方是 :mod:`app.pipeline.alert_stage` 的那三个常量。
    ⚠️ domain **import 不到**它们两个（:mod:`tests.architecture.test_domain_purity`
    的白名单只放行 ``app.domain.*`` 与六个标准库模块），故有两条路：
    ① 在 domain 里再写一份 ``("pending", "handled", "ignored")`` 并加一条对账测试
    （``AlertLevel`` ↔ ``Alert.LEVELS`` 的先例）；② 由调用方传进来。
    本模块选 ②：它**只有一个所有者**、也不需要一条对账测试来防漂移。
    本条钉的是「传进来的顺序就是载荷里键的顺序」（前端按它排列三档）。
    """
    got = alert_summary([("red", "handled")], statuses=("handled", "pending", "ignored"))
    assert list(got["red"]) == ["handled", "pending", "ignored"]


# ===========================================================================
# 支 G：算法建议（一条查表规则）
# ===========================================================================


def test_the_class_rpe_signal_alone_suggests_a_reduction():
    """``YELLOW_CLASS_RPE_HIGH`` 命中 → 降量（spec §8.5 逐字点名的那一条信号）。"""
    assert suggestion(True, 7.4) == "本周建议整体降量 10%"


def test_a_low_mean_rpe_without_the_class_signal_suggests_an_increase():
    """未命中班级信号 **且** 人均 RPE ``< 5`` → 加量。"""
    assert suggestion(False, 4.2) == "本周建议整体加量 10%"


def test_a_mid_range_mean_rpe_suggests_holding():
    """其余一律维持（``5 <= mean``）。"""
    assert suggestion(False, 6.0) == "维持当前强度"


def test_the_low_rpe_boundary_is_strict():
    """``< 5`` 是**严格**的：恰好 5.0 → 维持。

    ⚠️ 与 :func:`app.domain.alerts` 那五条规则的比较符同一条纪律
    （``YELLOW_CLASS_RPE_HIGH`` 也是严格的 ``>``）：一个闭区间边界会让
    「刚好卡在阈值上」的那一周给出一个方向相反的建议，而那种周恰恰是最需要
    「维持」的一周。
    """
    assert suggestion(False, CLASS_RPE_LOW_MAX) == "维持当前强度"
    assert suggestion(False, 4.999) == "本周建议整体加量 10%"


def test_an_unmeasurable_mean_rpe_suggests_holding_not_increasing():
    """**本周一次快评都没有 → 维持**，不是加量。

    ⚠️ 失效形态：``None < 5`` 在 Python 里当场 ``TypeError``（好），
    而把 ``None`` 折成 ``0.0`` 会让「没测」变成「一点都不累 → 加量 10%」——
    一句**建立在缺失数据上的建议**，而教师无从看出它没有依据。
    """
    assert suggestion(False, None) == "维持当前强度"


def test_the_class_signal_beats_the_low_rpe_signal():
    """**优先级承重**：班级黄牌命中时即使人均 RPE 很低也建议降量。

    ⚠️ 这一档在真实数据里是可达的（``YELLOW_CLASS_RPE_HIGH`` 的均值按**本周课堂快评**
    算，而一个班可以同时有「课上课很累」与「整周人均不高」），
    而两档给出的是**方向相反**的建议，故顺序不能反。
    反过来写（先判低 RPE）的话本条当场红。
    """
    assert suggestion(True, 3.0) == "本周建议整体降量 10%"
    assert suggestion(True, None) == "本周建议整体降量 10%"


# ===========================================================================
# 支 H：大屏异常名单（spec §9.1 的第 ④ 块）
# ===========================================================================


def test_the_roster_uses_the_screen_thresholds_not_the_alert_ones():
    """**spec §14 #11 的可执行落点**：连续 2 天未打卡的学生**上预警工单**、
    但**不上大屏异常名单**（大屏的门槛是 3 天）。

    ⚠️ 这一格是本支的全部理由：把 :data:`SCREEN_GAP_DAYS` 改成 2，
    本条当场红，而那时「两套并存」已经被悄悄合并成一套了 ——
    大屏于是变成第二个工单队列，教师在上面看到的一切都已经在他的待办里。
    """
    roster = abnormal_roster({1: 2, 2: 3}, {})
    assert [entry["student_id"] for entry in roster] == [2]
    assert roster[0]["reasons"] == ["checkin_gap"]
    assert roster[0]["gap_days"] == 3


def test_the_rpe_screen_is_strictly_above_eight():
    """``RPE > 8`` 是**严格**的：8 不上名单、9 上（spec §9.1 逐字「RPE > 8」，
    而预警那一条是「连续 ≥ 9」——两个判据的形状也不同，那边要**连续**）。"""
    roster = abnormal_roster({}, {1: [8, 8], 2: [7, 9], 3: [8]})
    assert [entry["student_id"] for entry in roster] == [2]
    assert roster[0]["reasons"] == ["rpe_high"]
    assert roster[0]["peak_rpe"] == 9


def test_a_student_flagged_for_both_reasons_carries_both_in_a_fixed_order():
    """两条都中 → 两个 reason 都在，且**顺序固定**（先打卡后 RPE）。

    ⚠️ 顺序固定是为了前端渲染稳定，也是为了幂等断言逐字相等。
    """
    roster = abnormal_roster({4: 5}, {4: [10]})
    assert roster == [{
        "student_id": 4,
        "reasons": [REASON_CHECKIN_GAP, REASON_RPE_HIGH],
        "gap_days": 5,
        "peak_rpe": 10,
    }]
    assert [REASON_CHECKIN_GAP, REASON_RPE_HIGH] == ["checkin_gap", "rpe_high"]


def test_a_student_meeting_neither_screen_is_not_on_the_roster():
    """两条都不中 → **不上名单**（一个 40 人的班里 38 个人不该出现在异常名单上）。"""
    assert abnormal_roster({1: 0, 2: 1}, {1: [5], 2: [6, 7]}) == []


def test_a_student_absent_from_one_of_the_two_maps_is_still_screened():
    """两个入参各覆盖一半人（一个学生可能只打过卡、只交过快评）。

    ⚠️ 缺失的那一侧按**保守**方向补：``gap_days`` 补 0（不知道就当没中断）、
    ``peak_rpe`` 是 ``None``（不知道就**不**当 0——0 会被读成「一点都不累」）。
    """
    roster = abnormal_roster({1: 4}, {2: [9]})
    assert roster == [
        {"student_id": 1, "reasons": ["checkin_gap"], "gap_days": 4, "peak_rpe": None},
        {"student_id": 2, "reasons": ["rpe_high"], "gap_days": 0, "peak_rpe": 9},
    ]


def test_the_roster_is_sorted_by_student_id():
    """名单按学生 id 升序（大屏是**滚动**展示的，顺序不稳会让教师每次都看到不同的人）。"""
    roster = abnormal_roster({9: 4, 3: 4, 6: 4}, {})
    assert [entry["student_id"] for entry in roster] == [3, 6, 9]


def test_an_empty_class_has_an_empty_roster():
    """两个入参都空 → 空名单（不是 ``None``：前端要的是一个可以直接 map 的数组）。"""
    assert abnormal_roster({}, {}) == []


# ===========================================================================
# 支 I：二次小测的**标准化得分**（spec §8.1；Plan 03 Task 9 从 api 层搬进 domain）
# ===========================================================================
#
# ⚠️ 本支的两个函数原先住在 ``app/api/routers/feedback.py``（``_shuttle_percentile``
# 与那三格内联的算式）。搬家的触发条件是**第二个消费者出现了**：
# :func:`app.pipeline.report_stage.class_snapshot` 生成班级周报时要算同一个数填进
# 进步榜，而 ``pipeline`` 反向 import ``api`` 被架构守卫禁止。
# 故本支既是「算式对不对」的守卫，也是「算式只有一份」的守卫（末尾那条 AST 断言）。


def test_the_shuttle_percentile_counts_slower_people_and_splits_ties():
    """**班内百分位反查**：``PR = (比自己慢的人数 + 0.5 × 并列人数) / 样本数 × 100``。

    ⚠️ 折返跑是**秒数越少越好**，故「反查」= 数比自己**慢**的人。三格期望值都是手算的
    （样本 ``[10.0, 11.0, 12.0]``，``n = 3``）：

    * 最快（10.0）：慢的 2 人 + 并列 1 人 → ``(2 + 0.5) / 3 × 100 = 83.333…``
    * 中间（11.0）：慢的 1 人 + 并列 1 人 → ``(1 + 0.5) / 3 × 100 = 50.0``
    * 最慢（12.0）：慢的 0 人 + 并列 1 人 → ``(0 + 0.5) / 3 × 100 = 16.666…``

    ⚠️ **返回未 round 的裸值**（:data:`SCORE_PRECISION` 的注释逐字写了那个
    ``56.665`` 浮点坑）：round 由 :func:`mini_test_scores` 一处做完，
    故本条用 ``pytest.approx`` 比到小数点后 10 位，**不**比 round 过的值。
    """
    sample = [10.0, 11.0, 12.0]
    assert shuttle_percentile(10.0, sample) == pytest.approx(250.0 / 3.0, abs=1e-10)
    assert shuttle_percentile(11.0, sample) == pytest.approx(50.0, abs=1e-10)
    assert shuttle_percentile(12.0, sample) == pytest.approx(50.0 / 3.0, abs=1e-10)


def test_tied_runtimes_get_the_same_percentile_not_three_different_ones():
    """**并列取中点**：三个人跑出一样的秒数 → 三个人**同一个** 50.0。

    ⚠️ 这一格是本函数与「严格小于」口径的分水岭：严格口径会按书写序给他们三个
    **不同**的分（0 / 33.33 / 66.67），而「并列」该有的样子是同一个数。
    把 ``0.5 *`` 改成 ``0`` 或把 ``>`` 改成 ``>=``，本条当场红。
    """
    assert shuttle_percentile(11.0, [11.0, 11.0, 11.0]) == pytest.approx(50.0, abs=1e-10)


def test_a_single_person_sample_is_fifty_not_zero_and_not_a_hundred():
    """``n = 1`` → **50.0**（自己的并列数 = 1，``0.5 / 1 × 100``）。

    ⚠️ 这是标准公式的自洽结果，**不是**「排过名」：全班只有一个人测了折返时他既不是
    最好也不是最差。⚠️ 而它在真实数据下**看起来像**真排过名，故 Plan 04 应当在
    ``scored_count == 1`` 时显示「无排名」——那是展示层的口径
    （``scored_count`` 已经由 ``GET /api/mini-tests/normalized`` 给出去了），
    本函数**刻意不改**（已登记为移交项）。
    """
    assert shuttle_percentile(30.0, [30.0]) == pytest.approx(50.0, abs=1e-10)


def test_an_empty_sample_raises_instead_of_reporting_the_worst_score():
    """空样本 → ``ZeroDivisionError``（**刻意不兜底**）。

    ⚠️ 兜一个 ``return 0.0`` 会把「算错了」静默变成「这个学生最差」，
    而 0.0 是一个**合法的**百分位值，下游没有任何东西会拦。
    两个调用方都只在 ``shuttle_20m_s is not None`` 时调它，那时样本必非空
    （至少含调用者自己），故这一档在生产路径上不可达——本条钉的是
    「不可达的那一档是响的」。
    """
    with pytest.raises(ZeroDivisionError):
        shuttle_percentile(30.0, [])


def test_mini_test_scores_follows_spec_8_1_verbatim():
    """spec §8.1 的三格：**深蹲得分 = 次数**、**折返得分 = 班内百分位反查**、
    **综合分 = 两项等权平均**。

    ⚠️ 样本 ``[10.0, 10.0, 12.0, 13.0, 14.0, 15.0]``、本人 ``10.0``：
    慢的 4 人 + 并列 2 人 → ``(4 + 0.5 × 2) / 6 × 100 = 83.3333…`` →
    round 2 位 = **83.33**；深蹲 30 次 → **30.0**；
    综合分 = ``(30 + 83.3333…) / 2 = 56.6666…`` → round 2 位 = **56.67**。

    ⚠️⚠️ **56.67 而不是 56.66 是本条的全部价值**（:data:`SCORE_PRECISION` 的注释
    逐字写了这个坑）：若先把百分位 round 成 83.33 再平均，得到的是
    ``(30 + 83.33) / 2 = 56.665``，而 ``round(56.665, 2)`` 在 CPython 上给 **56.66**
    （56.665 的二进制表示略小于十进制的 56.665）。故本条同时钉住
    「中间步骤不 round」这条口径——把 :func:`mini_test_scores` 改成
    ``round((squat + round(raw, 2)) / 2, 2)``，本条当场红。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    assert mini_test_scores(30, 10.0, sample) == {
        "squat_score": 30.0,
        "shuttle_score": 83.33,
        "composite": 56.67,
    }
    # 反面对照：先 round 百分位再平均会得到 56.66（本行把那个坑写成一个可执行的事实）
    assert round((30 + round(250.0 / 3.0, 2)) / 2, 2) == 56.66


def test_the_composite_rounds_the_unrounded_percentile_not_the_displayed_one():
    """:data:`SCORE_PRECISION` 的注释里点名的那一条守卫（**与上一条互为正反面**）。

    上一条钉的是「三格的字面值」，本条钉的是「``shuttle_score`` 显示 83.33、
    而 ``composite`` 用的是 83.3333…」这件事本身：两格**必须**来自同一个裸值，
    一个 round 过、一个没 round 过，否则同一份响应里的两个数互相矛盾
    （教师拿 83.33 与 30 一平均得 56.665，而系统写的是 56.67，他会认为系统算错了）。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    got = mini_test_scores(30, 10.0, sample)
    assert got["shuttle_score"] == 83.33
    assert got["composite"] == 56.67
    assert got["composite"] != round((30 + got["shuttle_score"]) / 2, SCORE_PRECISION)


def test_a_missing_squat_leaves_the_composite_unknown_not_halved():
    """深蹲缺测 → ``squat_score`` 与 ``composite`` 都是 ``None``，
    而 ``shuttle_score`` **照常给**。

    ⚠️ 把 ``None`` 当 0 会让这个学生的综合分变成「另一项的一半」
    （``(0 + 83.33) / 2 = 41.67``），那是一句关于他的假话；而它会直接掉进
    :func:`progress_board` 的**退步名单**（相对上一次的分是负的），
    教师于是去找一个其实没退步的学生谈话。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    assert mini_test_scores(None, 10.0, sample) == {
        "squat_score": None,
        "shuttle_score": 83.33,
        "composite": None,
    }


def test_a_missing_shuttle_leaves_the_composite_unknown_and_skips_the_sample():
    """折返缺测 → ``shuttle_score`` 与 ``composite`` 都是 ``None``，
    而 ``squat_score`` **照常给**；⚠️ 且**样本可以是空的**（本函数不去查百分位）。

    ⚠️ 这一格同时钉住「``shuttle_20m_s is None`` 时不调
    :func:`shuttle_percentile`」：若调了，空样本会当场 ``ZeroDivisionError``
    （见上面那条）。而生产路径上这一档**是可达的**——教师只录了深蹲、
    折返那一格空着，:func:`app.pipeline.report_stage._composite_of` 就会以空样本调进来。
    """
    assert mini_test_scores(30, None, []) == {
        "squat_score": 30.0,
        "shuttle_score": None,
        "composite": None,
    }


def test_both_measurements_missing_is_all_none():
    """两项都缺测 → 三格全 ``None``（``or`` 的第二支：``squat`` 为 ``None`` 时
    短路，``raw`` 那一支也要单独走到，故本条与上两条**互不覆盖**）。"""
    assert mini_test_scores(None, None, []) == {
        "squat_score": None,
        "shuttle_score": None,
        "composite": None,
    }


def test_the_squat_score_is_a_float_even_though_the_column_is_an_integer():
    """``squat_score`` 一律 ``float``：那一列是 ``Integer``，而 ``composite`` 是两项的
    平均（可能是 ``x.5``），两格类型不一致会让前端拿到 ``70`` 与 ``70.0`` 两种形状。"""
    got = mini_test_scores(70, 30.0, [30.0])
    assert isinstance(got["squat_score"], float)
    assert got["squat_score"] == 70.0
    # 全班并列 → 百分位 50.0 → 综合分 (70 + 50) / 2 = 60.0
    assert got == {"squat_score": 70.0, "shuttle_score": 50.0, "composite": 60.0}


def test_the_mini_test_normalization_has_exactly_one_definition():
    """**AST 口径**（硬规矩 #89 再扩写：数「一个名字有几份定义」用 AST）：
    「班内百分位反查」与「综合分」在全仓只有**一份定义**。

    照 ``tests/pipeline/test_alert_stage.py`` 的
    ``test_training_days_of_has_exactly_one_definition`` 的形状办（同为「一个私有函数
    因为第二个消费者出现而搬家」，而搬家之后**旧的那一份必须真的消失**）。

    ⚠️ **失效形态很具体**：留一个平行的副本就是第二个所有者，两份「班内百分位」
    漂了之后，教师录完成绩当场看到的分与周日周报上的进步榜就不是同一个口径了，
    而**两边各自的测试都还是绿的**（一边测端点、一边测周报）。

    ⚠️ **本条守不住什么**（硬规矩 #39）：它数的是**函数名**，故谁把算式
    **内联**进 ``report_stage`` 或某个 router（不再是一个有名字的函数）本条不红。
    那一档由 ``app/domain/`` 的 **100% 分支覆盖**兜一半
    （内联进 pipeline/api 的那一份不在覆盖率口径里，于是它没有测试），
    以及 :func:`test_the_api_layer_and_the_report_stage_give_the_same_composite` 兜另一半。
    """
    names = ("shuttle_percentile", "_shuttle_percentile", "mini_test_scores",
             "_mini_test_scores")
    definitions = []
    for py in sorted((BACKEND / "app").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in names
            ):
                definitions.append(
                    (py.relative_to(BACKEND).as_posix(), node.name, node.lineno)
                )
    assert len(definitions) == 2, (
        f"「班内百分位反查 + 综合分」应当只有 2 份定义"
        f"（shuttle_percentile 与 mini_test_scores，都在 app/domain/report.py），"
        f"实到 {len(definitions)}: {definitions}"
    )
    assert [(where, name) for where, name, _line in definitions] == [
        ("app/domain/report.py", "shuttle_percentile"),
        ("app/domain/report.py", "mini_test_scores"),
    ], f"住址不对（应当都在 app/domain/report.py）: {definitions}"


def test_the_api_layer_and_the_report_stage_give_the_same_composite():
    """**两个消费者给出同一个综合分**（本支存在的理由本身）。

    一侧是 ``GET /api/mini-tests/normalized`` 的响应，另一侧是
    :func:`app.pipeline.report_stage._composite_of`。⚠️ 两侧**都**调
    :func:`mini_test_scores`，故本条看似恒真——它挡的是「某一侧在调用前后又自己做了一次
    round / 又自己挑了一次样本」：那正是上面那条 AST 断言守不住的内联档。
    """
    from app.pipeline.report_stage import _composite_of

    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    via_domain = mini_test_scores(30, 10.0, sample)["composite"]

    class _Row:
        squat_30s_count = 30
        shuttle_20m_s = 10.0

    class _Other:
        def __init__(self, shuttle):
            self.squat_30s_count = 0
            self.shuttle_20m_s = shuttle

    week_rows = [_Row()] + [_Other(value) for value in (10.0, 12.0, 13.0, 14.0, 15.0)]
    assert _composite_of(_Row(), week_rows) == via_domain == 56.67
