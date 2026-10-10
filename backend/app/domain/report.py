"""spec §8.5 班级周报与 §9.1 教师大屏的**聚合量**（Plan 03 Task 8）。

它是纯函数叶子层，与 :mod:`app.domain.alerts` 同一档纪律：**无 I/O、无时钟、
100% 分支覆盖**（spec §12）。日期一律是**调用方注入的 ISO 字符串**，
参考表（分层词表、预警级别词表、预警阈值）一律**作为参数传入或从 domain 兄弟模块派生**。

--------------------------------------------------------------------------
为什么这些量住在 domain、而不住在 router 或 ``report_stage`` 里
--------------------------------------------------------------------------

三条理由（简报 P8-A2 的裁定，逐条落地）：

1. **可单测**：spec §12 要求 ``app/domain/`` **100% 分支覆盖**，而住在 router 里的逻辑
   只有集成测试够得着。本模块的九个函数因此各有一组「字面期望值」的单元测试
   （``tests/domain/test_report.py`` 的八支），而
   :mod:`app.pipeline.report_stage` 与 :mod:`app.api.routers.dashboard` 只负责
   「把库里的行组装成这些函数的入参、把返回值落库/回给前端」。
2. **单一所有者**：**大屏与班级周报共享同一批聚合量**（分层分布、周环比流动、
   人均 RPE 曲线、进步榜、按层完成率）。放在两处就会有两个「人均 RPE」，
   而它们在**周报是周日生成的、大屏是实时刷新的**这一差别下必然某天对不上——
   教师会看到大屏写 6.9、周报写 7.1，然后认为系统算错了。
3. **先例**：:mod:`app.domain.alerts` 已经是这个形状（Task 6：151 stmts / 48 branch /
   100%），本模块照它办。

--------------------------------------------------------------------------
⚠️ 三个「两套并存」：本模块刻意与已有的口径**不相等**
--------------------------------------------------------------------------

**① 大屏的筛选阈值 ≠ 预警的判据阈值**（spec §14 #11 的裁定）

spec §9.1 逐字记录了指导文件的内部矛盾：大屏「异常名单」是「连续 **3** 天未打卡 |
RPE > **8**」，而 :mod:`app.domain.alerts` 的预警规则是「中断 **2** 天、RPE 连续 ≥ **9**」。
裁定是「**两套并存，职责不同**」：预警是需要教师处理的**正式工单**（阈值严、有状态机），
大屏异常名单是课堂即时扫视用的**宽松筛选器**（阈值松、只展示不派单）。
故本模块持有 :data:`SCREEN_GAP_DAYS` / :data:`SCREEN_RPE_MAX` 两个常量，
**不复用** ``alert_rules.yaml`` 的那两个数；守卫是
``tests/domain/test_report.py::test_the_screen_thresholds_are_not_the_alert_thresholds``
（把它们改成相等 → 当场红）。

⚠️ **两个阈值今天没有任何 spec 出处之外的依据**（它们就是 spec §9.1 那张 ASCII 图里的
两个字面量），故**不进 ``alert_rules.yaml``**：简报 P8-A6 的裁定是「本 Task 不加
``screen:`` 段」，理由是 ① 加它要按 Plan 02 的 P9-A3 六步程序走（重算 sha256 指纹、
复核 CRLF、同步常量，而**另三个指纹必须逐字不变**）；② ``alert_rules.yaml`` 的所有者是
「5 条**判据**的阈值」（:data:`app.refdata_alerts._PARAM_TYPES` 逐规则钉住了键集），
而大屏那两个数**不是判据**、不产生工单。⚠️ 于是它们是**待体育专家确认**的工程约定，
与 Plan 02 处理 ``Intensity.rpe`` 的方式一致（硬规矩 #39：写下能力就写明守不住什么）。

**② 「算法建议」的 10% ≠ spec §8.4 的「减量 20%」**

:data:`SUGGESTION_STEP_PCT` 是 **10**，而
:data:`app.pipeline.alert_stage.AUTO_REDUCTION_FACTOR` 是 **0.8**（= 减 20%）。
这个不对称**是有意的**，而它会被当成 bug，故逐字写在这里：

* **20%** 是**红色预警对单个学生**的处置，而且**系统自动执行**（写一条
  ``weekly_adjustment(source="auto")``，学生端当周的训练单立刻变）；
* **10%** 是**班级级建议**，给教师看的，**不自动执行**（它落进
  ``weekly_class_report.suggestion`` 那一列，是一句中文，没有写入方去改任何处方）。

一个会自动生效的动作可以激进一点（它保护的是「这个学生练得太苦」），
一个只是建议的动作应当温和一点（教师可能知道一个系统不知道的理由）。
守卫是 ``test_the_suggestion_step_is_ten_percent_and_the_auto_reduction_is_twenty``
（把两者改成同一个数 → 当场红）。

**③ 进步榜的排序量 ≠ ``GREEN_MASTERY`` 的判据**

:func:`progress_board` 按 ``mini_test.normalized_score`` 的**相对变化**排序，
而 :func:`app.pipeline.alert_stage._mini_test_improved` 判的是「三个指标里
**任一**改善 ≥ 3%」（``normalized_score`` / ``squat_30s_count`` / ``shuttle_20m_s``，
后者是**秒数越少越好**）。两个口径刻意不同：**榜要一个可排序的单一量**，
而三个指标的三个方向无法折成一个序、除非再引入一套权重口径（那是新增口径、须先改 spec）。
⚠️ 代价（硬规矩 #39）：``normalized_score`` 今天在库里只有
:func:`app.demo_data.build_demo_feedback` 一个写入方，而它写的是**演示口径的近似值**
（「班内百分位反查」由 ``GET /api/mini-tests/normalized`` **现算**、刻意不回写，
理由见 :mod:`app.api.routers.feedback` 模块 docstring 的「刻意不做」第 3 条）。
故本榜在生产路径上**读到的可能是空**（那一列是 ``NULL``）→ 全员 ``unmeasured``。

--------------------------------------------------------------------------
「判不了」与「0」一律分开（Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）
--------------------------------------------------------------------------

本模块有**六处** ``None``，每一处都是「不知道」而不是「测到了 0」：

==============================  ==================================================
载荷里的键                        ``None`` 的含义
==============================  ==================================================
``rpe_summary.curve[i]``         那一天一节快评都没有（**不是**「那天全班不累」）
``rpe_summary.previous_curve``   上一周不存在（学期第一周）
``rpe_summary.mean`` /           本周（/ 上周）一次快评都没有
``previous_mean`` / ``delta``
``checkin_rate_by_layer[L]``     这一层一个可测的人都没有（**不是**「完成率 0%」，
  的 ``rate``                     而完成率是 spec 逐字点名的「RCT 关键过程指标」）
``layer_distribution.previous``  上一周没有分层快照
``abnormal_roster[i].peak_rpe``  这个学生本周没交过快评（**不是** ``0``）
==============================  ==================================================

:func:`week_mean_rpe` 与 :func:`suggestion` 因此都显式处理 ``None``：
把 ``None`` 折成 ``0.0`` 会让「本周没测」变成「一点都不累 → 建议加量 10%」，
一句**建立在缺失数据上的建议**，而教师无从看出它没有依据。

--------------------------------------------------------------------------
⚠️ 本模块不 import ``datetime``
--------------------------------------------------------------------------

:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 实测 =
``{collections, collections.abc, dataclasses, enum, numpy, typing}``，
**``datetime`` 不在白名单**（与 :mod:`app.domain.alerts` 同一条约束）。
故「一周有哪 7 天」由调用方算好、以 ISO 字符串元组注入（:attr:`RpeWeek.days`），
本模块既不调 ``date.isoformat()`` 也不写 ``dt.date`` 这样的标注。
「学期第 N 周 → 那 7 天」的算式住在
:func:`app.pipeline.alert_stage.semester_week_range`（管道层）与
:func:`app.api.routers.feedback._week_days`（api 层），两处并存、由
``tests/pipeline/test_alert_stage.py`` 的一条测试钉成逐字相等——**本模块不造第三处**。

--------------------------------------------------------------------------
⚠️ 载荷里的 round：哪几格 round、哪几格刻意不 round
--------------------------------------------------------------------------

:data:`RPE_PRECISION` / :data:`RATE_PRECISION` / :data:`PCT_PRECISION` 三个精度常量
只用在**纯显示**的格子上。:func:`week_mean_rpe` 的返回值**不 round**，
因为它是 :func:`suggestion` 的判据输入——round 之后「据以判的数」与
「同一份载荷里显示的数」会差半格，而那种不一致在一个屏上是看得见的。
:attr:`RpeWeek` 那一侧的 ``mean`` / ``previous_mean`` 两格因此也是**未 round 的**
（前端负责格式化），而 ``curve`` 的 7 个点与 ``delta`` 是 round 过的。

⚠️ 这不是随手写的：round 的**唯一目的**是让落进
``weekly_class_report`` 那 5 个 ``JsonText`` 列的东西**可复现**
（浮点尾数随求和顺序漂，而 ``tests/pipeline/test_daily.py`` 那种
「跑两遍逐字相等」的幂等断言比的是逐字相等）。判据输入不参与这件事，故不 round。
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.alerts import AlertLevel
from app.domain.stratify import Layer

__all__ = [
    "CLASS_RPE_LOW_MAX",
    "LAYERS",
    "LEVELS",
    "PCT_PRECISION",
    "PROGRESS_BOARD_TOP_N",
    "RATE_PRECISION",
    "REASON_CHECKIN_GAP",
    "REASON_RPE_HIGH",
    "RPE_PRECISION",
    "RpeWeek",
    "SCREEN_GAP_DAYS",
    "SCREEN_RPE_MAX",
    "SUGGESTION_HOLD",
    "SUGGESTION_INCREASE",
    "SUGGESTION_REDUCE",
    "SUGGESTION_STEP_PCT",
    "abnormal_roster",
    "alert_summary",
    "checkin_rate_by_layer",
    "daily_mean_rpe",
    "layer_distribution",
    "layer_flow",
    "progress_board",
    "rpe_summary",
    "suggestion",
    "week_mean_rpe",
]

#: 分层标签的规范序 = :class:`~app.domain.stratify.Layer` 的**声明序**。
#:
#: ⚠️ **它是派生、不是第二份字面量**（Global Constraint #3：单一所有者）：
#: 值域的所有者是 ``Layer``（+ DB 的 ``ck_stratification_result_label``），
#: 本常量只回答「载荷里四个键按什么顺序出现」。故 ``Layer`` 加一个值，
#: 这里自动跟着加，而饼图少一个扇区这类失效**结构上不可能发生**。
#: ⚠️ ``insufficient_data`` **在列**：一个数据不足的学生不是绿层，
#: 把他从分布里抹掉会让「本班 40 人」与「四个扇区之和 38」对不上，
#: 而那个差额正好是最该被看见的那两个人。
LAYERS: tuple[str, ...] = tuple(layer.value for layer in Layer)

#: 预警级别的规范序 = :class:`~app.domain.alerts.AlertLevel` 的声明序。
#:
#: ⚠️ **它是三个、不含 ``insufficient_data``**：预警级别与分层标签是**两套词表**
#: （``AlertLevel`` 三个值 vs ``Layer`` 四个值），共用一份会让「本周 0 条绿牌」与
#: 「本周 0 个绿层学生」在同一个键下打架。两个都从各自的所有者派生，故不可能漂。
LEVELS: tuple[str, ...] = tuple(level.value for level in AlertLevel)

#: ---------------------------------------------------------------------------
#: 大屏「异常名单」的两个阈值（spec §9.1）。⚠️ **与预警的那两个刻意不同**，
#: 完整理由见模块 docstring 的「三个两套并存」①。
#: ⚠️ **待体育专家确认**：它们今天的唯一依据是 spec §9.1 那张 ASCII 图里的两个字面量，
#: 没有任何运动生理学的出处，故**不进 ``alert_rules.yaml``**（简报 P8-A6 的裁定）。
#: ---------------------------------------------------------------------------

#: 大屏口径：连续**未打卡**的天数达到它就上异常名单（预警那一条是 2 天）。
SCREEN_GAP_DAYS: int = 3

#: 大屏口径：本周课堂快评的**峰值** RPE 严格超过它就上异常名单
#: （预警那一条是「连续 ≥ 9」——⚠️ 判据的**形状**也不同：那边要连续，这边只要一次）。
SCREEN_RPE_MAX: int = 8

#: 异常名单的两个 ``reasons`` token。⚠️ 它们是**载荷里的字面量**（前端按它渲染图标与
#: 文案），故住在这里；与 ``alert.rule_id`` 那套词表**没有关系**
#: （那边是五条规则的名字，值域所有者是 ``data/alert_rules.yaml``）。
REASON_CHECKIN_GAP: str = "checkin_gap"
REASON_RPE_HIGH: str = "rpe_high"

#: ---------------------------------------------------------------------------
#: 「算法建议」的一条查表规则（spec §8.5 最后一项）。⚠️ spec **没给口径**，
#: 简报 Task 8「决定」第 1 条把它定成查表，三个字符串与两个阈值都住在这里。
#: ⚠️ **工程约定，不是运动生理学结论，须由体育专家确认**（→ 登记 spec §14）。
#: ---------------------------------------------------------------------------

#: 建议的步长（百分比）。⚠️ **与 spec §8.4 的「减量 20%」刻意不同**，
#: 理由逐字见模块 docstring 的「三个两套并存」②。
SUGGESTION_STEP_PCT: int = 10

#: 「人均 RPE 低于它就建议加量」的那个界。⚠️ **严格小于**（见 :func:`suggestion`）。
#: ⚠️ 它**不在** ``alert_rules.yaml`` 里：那份 YAML 的所有者是「5 条规则的判据阈值」，
#: 而这一条不产生工单、不产生任何写入，它只是周报上的一句中文。
CLASS_RPE_LOW_MAX: float = 5.0

#: 三档建议的文案。⚠️ **由 :data:`SUGGESTION_STEP_PCT` 生成、不手写第二遍**：
#: 改一个数而忘了改文案，教师看到的建议就与系统据以判的数不符，
#: 而那一列是 :class:`Text`（没有 CHECK、没有词表），没有任何东西会拦。
SUGGESTION_REDUCE: str = f"本周建议整体降量 {SUGGESTION_STEP_PCT}%"
SUGGESTION_INCREASE: str = f"本周建议整体加量 {SUGGESTION_STEP_PCT}%"
SUGGESTION_HOLD: str = "维持当前强度"

#: 进步榜的截断（spec §8.5 逐字「进步榜 Top10」）。⚠️ **退步名单不截断**：
#: spec 只给进步榜点了 Top10，而退步名单是「要逐个找学生谈话」的工作清单，
#: 截断它等于把该谈的人藏起来。
PROGRESS_BOARD_TOP_N: int = 10

#: ---------------------------------------------------------------------------
#: 三个显示精度。⚠️ **判据输入不 round**，理由见模块 docstring 末段。
#: ---------------------------------------------------------------------------

#: RPE 曲线那 7 个点与 ``delta`` 的小数位。
RPE_PRECISION: int = 2

#: 完成率的小数位。⚠️ **与 :data:`app.api.routers.feedback.RATE_PRECISION` 是同一个数**
#: （同一个量在学生端端点与班级周报里必须给到同一个精度，否则教师大屏上的
#: 「红层 83%」与学生首页上的「83.33%」会被当成两个数）。
#: ⚠️ domain **import 不到** ``app.api``（:mod:`tests.architecture.test_layering`
#: 的反向那一圈），故这里是「两份并存 + 一条测试钉成相等」，
#: 先例是 :class:`app.domain.alerts.AlertLevel` 与 ``Alert.LEVELS``。
#: 守卫是 ``tests/domain/test_report.py::test_the_two_precisions_match_their_counterparts_in_the_api_layer``。
RATE_PRECISION: int = 4

#: 进步榜那个百分比的小数位。
PCT_PRECISION: int = 2


@dataclass(frozen=True)
class RpeWeek:
    """一周的课堂快评，:func:`rpe_summary` 与 :func:`week_mean_rpe` 的唯一入参形状。

    ``days``
        这一周的 7 个 ISO 日期串，**升序**。⚠️ 由调用方注入（domain 不 import
        ``datetime``，见模块 docstring）；算式的所有者是
        :func:`app.pipeline.alert_stage.semester_week_range`。
        ⚠️ **曲线的长度由它决定、不由 ``values`` 决定**：一节课都没上的那天也要占一个
        点（值是 ``None``），否则折线的横轴会自己缩短，而教师看不出「周三是空的」
        与「周三不存在」的区别。
    ``values``
        ``{ISO 日期串: 那一天全部快评的 RPE}``。**缺席的键与空列表同义**
        （都是「那天没人交」），故调用方不必把 7 天都填上。
        ⚠️ 值序列**不要求有序**：均值与最大值都与顺序无关。
    """

    days: tuple[str, ...]
    values: Mapping[str, Sequence[int]]


def _count_layers(labels: Mapping[int, str]) -> dict:
    """``{学生 id: 分层标签}`` → **稠密**的 ``{标签: 人数}``（四个键一个不缺）。

    ⚠️ 与 :attr:`app.pipeline.alert_stage.AlertReport.by_level` 的**稀疏**口径刻意相反，
    理由也相反：那一处「一律以 0 入字典会让『今天没有红牌』与『今天没跑』同形」，
    而**一份周报的存在本身就是「跑过了」的证据**，且饼图要的是四条固定的扇区
    （少一条，前端就得自己补 0，那才是第二个所有者）。

    ⚠️ 词表外的标签 → ``KeyError``（**响亮失败**）：``labels`` 的值来自
    ``stratification_result.label``，那一列有 ``ck_stratification_result_label`` 兜着，
    故这一档在生产路径上不可达；它挡的是调用方拼装时打错字。
    """
    counts = dict.fromkeys(LAYERS, 0)
    for label in labels.values():
        counts[label] += 1
    return counts


def layer_flow(
    labels_now: Mapping[int, str], labels_prev: "Mapping[int, str] | None"
) -> dict:
    """**周环比流动**（spec §8.5 第 1 项的后半：「升入/降出各层的人数与名单」）。

    ------------------------------------------------------------------
    ``labels_prev is None`` → 全 0（简报 Task 8「决定」第 2 条逐字）
    ------------------------------------------------------------------

    上一周没有分层快照（学期第一周）时，四个名单**一律为空**、
    ``has_previous`` 为 ``False``。⚠️ **不得**把 ``None`` 当成「上周一个人都没有」：
    那样全班 40 人都会显示成「本周升入 40 人」，而教师读到的是一句
    **凭空捏造的进步**。「不知道」不得讲成「变化了」。
    ``has_previous`` 因此是**承重的**：它是前端唯一能用来把
    「第一周」渲染成「暂无环比数据」的开关（四个空名单与「一周里一个人都没动」
    在形状上完全相同，分不出来）。

    ------------------------------------------------------------------
    四档，各回答一个不同的问题
    ------------------------------------------------------------------

    ================  ==========================================================
    名单                谁在里面
    ================  ==========================================================
    ``entered[L]``     上周与本周**都有**分层行、且从别的层换到 ``L`` 的人
    ``left[L]``        上周与本周**都有**分层行、且从 ``L`` 换到别的层的人
    ``appeared[L]``    上周**没有**分层行、本周有（转进来 / 本学期首次被分层）
    ``disappeared[L]`` 上周有分层行、本周**没有**（退课 / 本周整天缺测）
    ================  ==========================================================

    ⚠️ **后两档是本模块加的**（spec 只说「升入/降出」），理由是一条具体的失效：
    把「本周才出现的人」算进 ``entered`` 的话，一个转学进来的学生会被报成
    「升入绿层 1 人」，而教师读到的是「有一个人从别的层进步到了绿层」——
    那不是发生的事。

    ⚠️ **代价（硬规矩 #39）**：于是 ``entered`` / ``left`` **不能**单独用来核对
    「本周人数 = 上周人数 − left + entered」，那个恒等式要连 ``appeared`` /
    ``disappeared`` 一起算。本模块**不替前端做这一步**（它会是一个新的聚合量，
    而它今天没有消费者）。

    ⚠️ **人数不入载荷**：spec 说「人数与名单」，而人数 = ``len(名单)``，
    再存一份就是两个可能互相矛盾的所有者（Global Constraint #3）。

    **名单一律按学生 id 升序**：``dict`` 的迭代序是插入序，而插入序取决于调用方
    拼装 ``labels`` 的顺序（= 一次 SQL 的结果序）。不排序的话同一份数据两次生成的
    周报会给出两个不同顺序的名单，而幂等断言比的是逐字相等。
    """
    entered = {layer: [] for layer in LAYERS}
    left = {layer: [] for layer in LAYERS}
    appeared = {layer: [] for layer in LAYERS}
    disappeared = {layer: [] for layer in LAYERS}
    if labels_prev is None:
        return {
            "has_previous": False,
            "entered": entered,
            "left": left,
            "appeared": appeared,
            "disappeared": disappeared,
        }
    for student_id in sorted(set(labels_now) | set(labels_prev)):
        now = labels_now.get(student_id)
        before = labels_prev.get(student_id)
        if now is None:
            disappeared[before].append(student_id)
        elif before is None:
            appeared[now].append(student_id)
        elif now != before:
            entered[now].append(student_id)
            left[before].append(student_id)
    return {
        "has_previous": True,
        "entered": entered,
        "left": left,
        "appeared": appeared,
        "disappeared": disappeared,
    }


def layer_distribution(
    labels_now: Mapping[int, str], labels_prev: "Mapping[int, str] | None"
) -> dict:
    """``weekly_class_report.layer_distribution`` 那一列的**全部**内容
    （spec §4.7 的「分层分布及环比流动」是**一格**，故两半在同一个载荷里）。

    三个键：

    ``by_layer``
        本周的**稠密**分布（:func:`_count_layers`）。
    ``previous``
        上周的同一份分布，**上一周没有快照时是 ``None``**
        （简报 Task 8「决定」第 2 条逐字：``layer_distribution_prev`` 为 ``null``）。
        ⚠️ 它与 :func:`layer_flow` 的 ``has_previous`` 是**同一件事的两面**，
        故两者不可能矛盾（都由 ``labels_prev is None`` 这一个判据决定）。
    ``flow``
        :func:`layer_flow` 的输出（四个名单 + ``has_previous``）。
    """
    return {
        "by_layer": _count_layers(labels_now),
        "previous": None if labels_prev is None else _count_layers(labels_prev),
        "flow": layer_flow(labels_now, labels_prev),
    }


def daily_mean_rpe(days: Sequence[str], values: Mapping[str, Sequence[int]]) -> list:
    """**按天**的人均 RPE 曲线（spec §8.5 第 2 项 / §9.1 的第 ② 块）。

    返回一个与 ``days`` **等长**的列表，每项是
    ``{"day": ISO 串, "mean": 均值, "submissions": 提交数}`` 或 ``None``。

    ⚠️ **``None`` = 那天一节课都没交快评**，不是一个 0 值的点：把空日画成 0，
    折线会在周三掉到 0 再弹回 7，而教师读到的是「周三全班疲劳度骤降」——
    那天只是没上课。

    ⚠️ ``submissions`` **在载荷里**：一个「3 个人交出来的均值 9.0」与
    「38 个人交出来的均值 9.0」对教师的含义完全不同（前者是一个噪声点），
    而前端**无从**自己算出它（它手上只有均值）。
    它不是可推导的重复项，故不违反 Global Constraint #3。

    ``mean`` round 到 :data:`RPE_PRECISION` 位（纯显示：它是画线的点，不是任何判据的输入）。
    """
    curve: list = []
    for day in days:
        submissions = values.get(day) or ()
        curve.append(
            None
            if not submissions
            else {
                "day": day,
                "mean": round(sum(submissions) / len(submissions), RPE_PRECISION),
                "submissions": len(submissions),
            }
        )
    return curve


def week_mean_rpe(week: RpeWeek) -> "float | None":
    """整周的**人均 RPE**（按提交数加权），一次快评都没有则 ``None``。

    ⚠️ **加权口径是承重的**：「全部提交的算术均值」≠「七个日均值再平均」，
    两者在**每天交的人数不同**时不相等（周一 1 个人交 10、周二 3 个人各交 6 →
    加权 ``7.0``，而日均值再平均是 ``8.0``）。选加权的理由有两条：

    1. spec §8.5 写的是「**人均** RPE」，人均的分母是**人次**；
    2. :func:`app.pipeline.alert_stage.evaluate_alerts` 给 ``YELLOW_CLASS_RPE_HIGH``
       喂的就是这一份（``sum(row.rpe) / len(rows)``，全部本周提交），
       而那条规则的阈值是 ``mean_rpe > 7.0``——两个口径不一致的话，
       大屏上写「本周人均 6.9」而同一周的班级黄牌按 7.1 触发了，
       教师会认为系统算错了。守卫是
       ``tests/domain/test_report.py::test_week_mean_rpe_agrees_with_the_class_level_alert_formula``
       （期望侧在测试里重算一遍，不 import 被测模块）。

    ⚠️ **返回值刻意不 round**（模块 docstring 末段）：它是 :func:`suggestion` 的
    判据输入，round 之后「据以判的数」与「同一份载荷里显示的数」会差半格。
    """
    flat = [rpe for submissions in week.values.values() for rpe in submissions]
    if not flat:
        return None
    return sum(flat) / len(flat)


def _delta(current: "float | None", previous: "float | None") -> "float | None":
    """``本周 − 上周``，任一侧不可测则 ``None``（**不是 0.0**：0.0 会被读成「持平」）。

    ⚠️ **符号承重**：正数 = 本周更累了。前端渲染成箭头时要按它，
    故这里不取绝对值、也不反过来减。
    """
    if current is None or previous is None:
        return None
    return round(current - previous, RPE_PRECISION)


def rpe_summary(current: RpeWeek, previous: "RpeWeek | None") -> dict:
    """``weekly_class_report.rpe_summary`` 那一列的**全部**内容
    （spec §4.7 的「人均 RPE 与上周对比」是**一格**）。

    五个键：``curve``（本周 7 个点）/ ``previous_curve``（上周 7 个点，§9.1 逐字
    要「上周虚线对比」）/ ``mean`` / ``previous_mean`` / ``delta``。

    ⚠️ ``previous is None`` → 后三格与 ``previous_curve`` **一律 ``None``**
    （学期第一周，与 :func:`layer_flow` 的 ``has_previous`` 同一条纪律）。
    ⚠️ 而 ``previous`` **是一个空的 :class:`RpeWeek`** 与 ``None`` 是两件事：
    前者是「上周存在、但一次快评都没有」→ ``previous_curve`` 是七个 ``None``、
    ``previous_mean`` 是 ``None``；后者是「上周不存在」。
    两者在 ``delta`` 上同为 ``None``，但在 ``previous_curve`` 上可区分，
    而前端要靠它决定「画不画那条虚线」。

    ⚠️ **§9.1 那两条阈值线（7 / 9）不在本载荷里**：它们的唯一所有者是
    ``data/alert_rules.yaml``（``YELLOW_CLASS_RPE_HIGH.mean_rpe_max`` = 7、
    ``RED_RPE_SUSTAINED.rpe_min`` = 9），由
    :mod:`app.api.routers.dashboard` 现读现给。抄一份进来就是第二个住址，
    而专家改一次 YAML 之后大屏上的线会**静默留在旧值**。
    """
    mean = week_mean_rpe(current)
    previous_mean = None if previous is None else week_mean_rpe(previous)
    return {
        "curve": daily_mean_rpe(current.days, current.values),
        "previous_curve": (
            None
            if previous is None
            else daily_mean_rpe(previous.days, previous.values)
        ),
        "mean": mean,
        "previous_mean": previous_mean,
        "delta": _delta(mean, previous_mean),
    }


def checkin_rate_by_layer(
    rates: Mapping[int, "float | None"], labels: Mapping[int, str]
) -> dict:
    """**按层分组的打卡完成率**（spec §8.5 第 3 项），返回
    ``{标签: {"students": 本层人数, "measured": 可测人数, "rate": 均值 | None}}``。

    ------------------------------------------------------------------
    口径决定：每人等权，不是「全班完成天数 / 全班应打卡天数」
    ------------------------------------------------------------------

    ⚠️ **代价（硬规矩 #39）**：等权均值让一个每周练 2 天的绿层学生与一个每周练 5 天的
    红层学生**同样重**，而加权口径（分子分母各自求和）不会。选等权的理由是一条：
    加权口径要给每个学生先算出**分母**（= 装配他的处方训练包，
    :func:`app.pipeline.prescription_stage.training_days_of`），
    而等权只要一个**已经算好的**比率。``students`` 与 ``measured`` 两格因此都在载荷里，
    读的人能看出这一层的样本有多大、以及它是不是「40 个人里只有 2 个测到了」。

    ------------------------------------------------------------------
    三个入参约定
    ------------------------------------------------------------------

    * ``rates[s]`` 是该生**本周**的完成率 ∈ ``[0, 1]``，或 ``None``（判不了）。
      ⚠️ 三档 ``None`` 的口径与 :func:`app.pipeline.alert_stage._student_signals`
      逐字相同：① 没有生效处方；② 处方已到期（``current_week`` 返回 ``None``）；
      ③ 那一周 ``paused``、没有训练日、或第一个训练日还没到。
      **「还没到」那一档是承重的**：不判它的话周日晚上生成的周报会把
      「本周三天训练一天都没发生」算成 ``0.0``。
      ⚠️ 而「有处方、训练日已过、一次卡都没打」的学生**是 ``0.0``、不是 ``None``**
      ——他确实 measurable，而且确实没练。
    * ``labels[s]`` 是该生**本周**的分层标签（``stratification_result.label``）。
    * ``rates`` 里查无此人 → 计入 ``students``、不计入 ``measured``
      （``students`` 要的是「这一层有多少人」，不是「有多少人测到了」）。
    * ``labels`` 里查无此人 → **整条忽略**（没有层可归）。⚠️ 不凭空造一个
      ``"(unlabelled)"`` 键：那会是 :data:`LAYERS` 之外的第五个键，
      而 ``ck_stratification_result_label`` 正好就是为了挡住它。

    ``rate`` round 到 :data:`RATE_PRECISION` 位（要落库并被读回来，
    一个 ``0.3333333333333333`` 会让同一份数据两次生成后逐字不等）。
    """
    sizes = dict.fromkeys(LAYERS, 0)
    measured: dict = {layer: [] for layer in LAYERS}
    for student_id, label in labels.items():
        sizes[label] += 1
        rate = rates.get(student_id)
        if rate is not None:
            measured[label].append(rate)
    return {
        layer: {
            "students": sizes[layer],
            "measured": len(values),
            "rate": (
                None
                if not values
                else round(sum(values) / len(values), RATE_PRECISION)
            ),
        }
        for layer, values in measured.items()
    }


def progress_board(scores: Mapping[int, "tuple[float | None, float | None]"]) -> dict:
    """**二次小测进步榜 Top10 与退步名单**（spec §8.5 第 4 项 / §9.1 的第 ③ 块）。

    ``scores[s]`` 是 ``(上一次的 normalized_score, 这一次的 normalized_score)``，
    由调用方按 ``mini_test.week`` 升序取**最近两次**（那一列有
    ``uq_mini_test_student_semester_week`` 兜着，故一周至多一份）。

    ------------------------------------------------------------------
    相对变化：``(new − old) / abs(old) × 100``
    ------------------------------------------------------------------

    ⚠️ **分母取 ``abs(old)``**：``normalized_score`` 那一列今天**不做值域校验**，
    一个负的 ``old`` 会把方向翻过来（从 −50 涨到 −40 会算成 ``−20%``，
    一个进步被报成退步），而全链路不报错。
    ⚠️ 口径与 :func:`app.pipeline.alert_stage._mini_test_improved` 逐字相同
    （那一处的 docstring 也点名了同一个失效形态）。

    ------------------------------------------------------------------
    四档「判不了」一律 ``unmeasured``，**不进榜**
    ------------------------------------------------------------------

    ``old is None`` / ``new is None`` / ``old == 0``（三个，``old`` 与 ``new`` 都为
    ``None`` 算一次）。⚠️ **``old == 0`` 那一档是承重的**：相对变化的分母是它，
    ``0`` 让变化率无定义；把它当成「无穷大改善」会让一个从 0 分做到 1 分的学生
    **永远霸榜**，而榜的读者以为那是「本周进步最大的人」。

    ------------------------------------------------------------------
    变化恰为 0 的人：两个榜都不进，但**被计数**
    ------------------------------------------------------------------

    ``unchanged`` 由减法得出（``len(changed) − len(improved) − len(regressed)``），
    **不是**第三个循环，故它与两个榜不可能对不上。
    ⚠️ 代价：一个变化率 ``round`` 到 :data:`PCT_PRECISION` 位后成 ``0.0`` 的
    （``0.004%``）也落进 ``unchanged``——**边界由 round 决定、不由一个额外阈值决定**，
    于是本模块不必再持有第二个「多小算没变」的数。

    **并列按学生 id 升序**：``sorted`` 是稳定排序，而输入序来自 ``dict`` 的插入序
    （= 一次 SQL 的结果序），不打 tie-breaker 的话同一份数据两次生成的榜会不同序。
    """
    changed: list = []
    unmeasured = 0
    for student_id, (older, newer) in scores.items():
        if older is None or newer is None or not older:
            unmeasured += 1
            continue
        changed.append(
            {
                "student_id": student_id,
                "change_pct": round(
                    (newer - older) / abs(older) * 100.0, PCT_PRECISION
                ),
            }
        )
    improved = sorted(
        (entry for entry in changed if entry["change_pct"] > 0),
        key=lambda entry: (-entry["change_pct"], entry["student_id"]),
    )
    regressed = sorted(
        (entry for entry in changed if entry["change_pct"] < 0),
        key=lambda entry: (entry["change_pct"], entry["student_id"]),
    )
    return {
        # ⚠️ ``top_n`` **不是常量的回声**：周报是存下来再读回来的，若明年把 10 改成 20，
        #    一份旧的 ``top`` 只有 10 项就无从分辨「当时只截了 10 个」与
        #    「当时只有 10 个人进步」。口径与
        #    ``alert.trigger_snapshot["alert_rules_version"]`` 逐字同一条。
        "top_n": PROGRESS_BOARD_TOP_N,
        "top": improved[:PROGRESS_BOARD_TOP_N],
        "regressed": regressed,
        "unchanged": len(changed) - len(improved) - len(regressed),
        "unmeasured": unmeasured,
    }


def alert_summary(rows: Sequence["tuple[str, str]"], *, statuses: Sequence[str]) -> dict:
    """**预警汇总**（spec §8.5 第 5 项：「红/黄/绿各若干，已处理/待处理」），
    返回 ``{级别: {状态: 条数}}``，**级别 × 状态双稠密**（3 × 3 = 9 个格子一个不缺）。

    ``rows`` 是 ``(level, status)`` 二元组的序列（= 本班 ``alert`` 表的两列）。

    ------------------------------------------------------------------
    ⚠️ ``statuses`` **由调用方注入**，本模块不声明第三个住址
    ------------------------------------------------------------------

    值域的所有者是 ``Alert.STATUSES``（+ DB 的 ``ck_alert_status``），
    生产写入方是 :mod:`app.pipeline.alert_stage` 的那三个常量。
    而 domain **import 不到**它们两个
    （:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 只放行六个标准库模块，
    唯一允许的包前缀是 ``app.domain``），故只有两条路：

    ① 在 domain 里再写一份 ``("pending", "handled", "ignored")``，
       并加一条对账测试把它与那两个所有者钉成相等
       （:class:`app.domain.alerts.AlertLevel` ↔ ``Alert.LEVELS`` 的先例）；
    ② 由调用方传进来。

    **本模块选 ②**：它只有一个所有者、也不需要一条对账测试来防漂移。
    ⚠️ 而**级别**那一侧走的是 ①（:data:`LEVELS` 从 :class:`AlertLevel` 派生）——
    因为 ``AlertLevel`` **就在 domain 里**，够得着，于是那里连「两份」都不存在。
    两侧处置不同不是抄错，是可达性不同（硬规矩 #56）。

    ⚠️ ``statuses`` 的**顺序就是载荷里键的顺序**（前端按它排列三档按钮）。

    ------------------------------------------------------------------
    词表外的一格 → ``KeyError``（响亮失败，不是静默丢掉）
    ------------------------------------------------------------------

    静默丢掉的失效形态：``level`` 拼成 ``"Red"`` 的那一条预警会从汇总里消失，
    而 9 个格子的和**看起来**仍然正常（教师端不会去核对它与 ``alert`` 表的行数）。
    两列都有 DB 的 CHECK 兜着（``ck_alert_level`` / ``ck_alert_status``），
    故这一档在生产路径上不可达；它挡的是调用方拼装时打错字。
    """
    summary = {level: dict.fromkeys(statuses, 0) for level in LEVELS}
    for level, status in rows:
        summary[level][status] += 1
    return summary


def suggestion(class_rpe_high: bool, mean_rpe: "float | None") -> str:
    """**算法建议**（spec §8.5 最后一项）：一条查表规则，三档，返回一句中文。

    spec 逐字只给了形状（「基于 ``YELLOW_CLASS_RPE_HIGH`` 等班级级信号，
    给出『本周建议整体降量/加量 X%』」），**没给口径**，故简报 Task 8「决定」第 1 条
    把它定成下面这张表。⚠️ **工程约定，不是运动生理学结论，须由体育专家确认**
    （→ 登记 spec §14）。

    ==========================================  ==============================
    条件（**自上而下，命中即停**）                 返回
    ==========================================  ==============================
    ``class_rpe_high`` 为真                      :data:`SUGGESTION_REDUCE`
    ``mean_rpe`` 可测 **且** ``< CLASS_RPE_LOW_MAX``  :data:`SUGGESTION_INCREASE`
    其余（含 ``mean_rpe is None``）                :data:`SUGGESTION_HOLD`
    ==========================================  ==============================

    ⚠️ **优先级是承重的**：``class_rpe_high`` 排第一，故一个班可以同时
    「课堂 RPE 均值超线」与「整周人均很低」时给出**降量**——两档的方向相反，
    顺序反了结论就反了。这一档在真实数据里可达：
    ``YELLOW_CLASS_RPE_HIGH`` 的均值只按**本周课堂快评**算
    （:func:`app.pipeline.alert_stage.evaluate_alerts` 里
    ``week_start <= row.session_date <= week_end`` 那一个筛选），
    而本函数的 ``mean_rpe`` 也是同一份，故「同时成立」要求
    ``7.0 < mean < 5.0``——⚠️ **在今天的两个阈值下不可达**。
    仍把顺序钉住的理由是**它们是两个独立的所有者**：专家把 ``mean_rpe_max``
    调到 4.5 之后那一档立刻可达，而那时「先判低 RPE」会给出加量建议
    ——对一个刚刚因为「课太累」被开了工单的班。
    守卫是 ``test_the_class_signal_beats_the_low_rpe_signal``。

    ⚠️ ``class_rpe_high`` 是**布尔**，由调用方从「本周这个班有没有一条
    ``rule_id = YELLOW_CLASS_RPE_HIGH`` 的 ``alert`` 行」得出，
    **不在这里重算一遍阈值**：那份阈值的所有者是 ``data/alert_rules.yaml``，
    在这里再比一次 ``mean_rpe > 7`` 就是第二个住址（Global Constraint #3），
    而专家改一次 YAML 之后两处会给出两个结论。

    ⚠️ ``mean_rpe < CLASS_RPE_LOW_MAX`` 是**严格**的（恰好 ``5.0`` → 维持），
    与 :mod:`app.domain.alerts` 那五条规则的比较符同一条纪律：
    一个闭区间边界会让「刚好卡在阈值上」的那一周给出一个方向相反的建议，
    而那种周恰恰是最需要「维持」的一周。
    """
    if class_rpe_high:
        return SUGGESTION_REDUCE
    if mean_rpe is not None and mean_rpe < CLASS_RPE_LOW_MAX:
        return SUGGESTION_INCREASE
    return SUGGESTION_HOLD


def abnormal_roster(
    gap_days: Mapping[int, int], rpes: Mapping[int, Sequence[int]]
) -> list:
    """**大屏异常名单**（spec §9.1 的第 ④ 块：「连续 3 天未打卡 | RPE > 8」）。

    两个入参各覆盖一半人（一个学生可能只打过卡、只交过快评），
    故遍历的是**两者的键并集**：

    ``gap_days``
        ``{学生 id: 连续未打卡的应打卡训练日天数}``。
        ⚠️ 算式的所有者是 :func:`app.pipeline.alert_stage._student_signals`
        （它读处方训练日 ∖ :func:`~app.pipeline.alert_stage._reported_checkin_days`），
        本模块**只比阈值**、不重算天数。
    ``rpes``
        ``{学生 id: 本周全部课堂快评的 RPE}``。⚠️ 判的是**峰值**（``max``）而不是均值：
        spec §9.1 写的是「RPE > 8」，而预警那一条是「**连续** ≥ 9」——
        两个判据的**形状**也不同（这边只要一次）。

    返回一个按学生 id 升序的列表，每项是
    ``{"student_id", "reasons", "gap_days", "peak_rpe"}``；
    **两条都不中的人不在列表里**（一个 40 人的班里 38 个人不该出现在异常名单上）。

    ⚠️ **缺失的那一侧按保守方向补**：``gap_days`` 补 ``0``（不知道就当没中断），
    而 ``peak_rpe`` 是 ``None``（不知道就**不**当 ``0``——``0`` 会被读成
    「一点都不累」，那是模块 docstring 那六处 ``None`` 里的最后一处）。

    ⚠️ ``reasons`` 的**顺序固定**（先打卡后 RPE）：大屏是**滚动**展示的，
    顺序不稳会让同一个人两次滚过时看起来像两条不同的异常。
    """
    roster: list = []
    for student_id in sorted(set(gap_days) | set(rpes)):
        reasons: list = []
        gap = gap_days.get(student_id, 0)
        if gap >= SCREEN_GAP_DAYS:
            reasons.append(REASON_CHECKIN_GAP)
        peak = max(rpes.get(student_id) or (), default=None)
        if peak is not None and peak > SCREEN_RPE_MAX:
            reasons.append(REASON_RPE_HIGH)
        if reasons:
            roster.append(
                {
                    "student_id": student_id,
                    "reasons": reasons,
                    "gap_days": gap,
                    "peak_rpe": peak,
                }
            )
    return roster
