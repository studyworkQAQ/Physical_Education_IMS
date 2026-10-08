"""校内百分位快照：同校区 × 同性别 × 同年级组的五档得分分布，以及样本不足时的国标常模兜底。

spec §4.0 规定「百分位一律在国标单项得分上算，而不是在原始值上算」——原始值方向不一致
（50 米跑、耐力跑越小越好），直接对原始值切 P25 会得出相反结论。本模块因此只吃**已经
正查成 0–100 的得分**，方向问题在 :mod:`app.domain.indicators` 那一层就已经被抹平。

**唯一的例外是 ``muscle_mass_kg``**（Ruling 102 / 121）：spec §6.3② 的体成分异常 ``C``
要用「肌肉量 < 同龄同性别 P20」这条判定线，而肌肉量**不是国标计分项**、没有得分可正查。
它本身是「越大越好」的单一方向量，直接在 kg 上切分位不存在方向问题，故按原始值入样。
这类指标由 :class:`SnapshotMetric` 显式声明（7 个计分项 + ``muscle_mass_kg``），
不在 :class:`~app.domain.indicators.ScoredItem` 里——把肌肉量塞进 ``ScoredItem`` 会同时
污染 ``ITEM_WEIGHTS`` / ``WEAKNESS_ITEMS`` / ``ITEM_BUCKET`` 三处不变式。

本模块是纯计算叶子，与 :mod:`app.domain.indicators` 同一条纪律（Ruling 15 / Ruling 87）：
不碰数据库、不读盘、不碰时钟，评分表由调用方（Task 10 用 ``app.refdata.standard()``）
显式注入。**刻意不 import ``app.refdata``**：domain 层若经两跳间接依赖唯一会读盘的模块，
Task 1 的 AST 纯净性守卫就被架空（守卫拦的是字面模式，拦不住「import 一个会读盘的模块」），
而且每条单元测试都会被迫读真实 CSV，再也造不出「表里只有 3 个档」这种边界形状。

物化由 Task 10 的管道负责（spec §4.0：百分位**必须物化为快照表，禁止实时计算**，否则
分层结果无法复现任意一天的状态）。本模块只产出值对象。
"""
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from app.domain.indicators import (
    AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex, score_item, segment_thresholds,
)
from app.domain.tables import StandardTable

# 百分位不可靠的样本量下限。低于它整组降级为国标常模（Review Focus #4）：
# 30 是统计上「大样本」的通行门槛，n < 30 时 P25 的抽样误差足以把一整个班的
# 短板判定线推过一个档位——而 P25 是 spec §6.3① 里 W 的唯一判定线。
MIN_SAMPLE = 30

# 五档**只在这里声明一次**：PercentileRow 的五个字段名与所有推导逻辑都由它生成
# （见 _PERCENTILE_FIELDS 与 _percentile_fields），改档位只需改这一行加对应字段。
# 25 是短板判定线（spec §6.3①：单项得分 < P25 记为显性短板），
# 20 是体成分维度 C 的肌肉量判定线（spec §6.3②），10/50/75 供画像与大屏展开。
PERCENTILES: tuple[int, ...] = (10, 20, 25, 50, 75)

_PERCENTILE_FIELDS: tuple[str, ...] = tuple(f"p{p}" for p in PERCENTILES)

# 肌肉量：spec §6.3② 的 ``C`` 要用「同龄同性别 P20」这条判定线，而它**不是国标计分项**
# （InBody 读数，没有得分可正查），故只存在于快照这一层。
MUSCLE_MASS = "muscle_mass_kg"

# 快照里可能出现的**非计分项**指标清单。
EXTRA_METRICS: tuple[str, ...] = (MUSCLE_MASS,)

_SNAPSHOT_METRIC_DOC = """快照行的指标域 = 7 个国标计分项的值 **+** :data:`EXTRA_METRICS`。

用函数式 API 从 :class:`~app.domain.indicators.ScoredItem` **派生**，而不是手抄第二份
7 行清单：计分项一旦增减（国标口径调整），本枚举自动跟着走，而手抄的那份不会报错、
只会让新计分项在入口校验里被拒。``type=str`` 让成员仍是 ``str``，故与 ``ScoredItem``
的成员**跨枚举相等**（``SnapshotMetric.SPRINT_50M == ScoredItem.SPRINT_50M`` 为真），
:func:`lookup_p25` 的 ``==`` 比较因此不必改，调用方传哪一种枚举都能命中同一行。

取值域同时是 ORM ``PercentileSnapshot.ITEMS`` 的内容（那一侧刻意不 import domain，
与 ``Student.SEXES`` 同一处置，由 ``tests/db/test_models.py`` 的漂移测试钉住两处一致）。
"""

SnapshotMetric = Enum(
    "SnapshotMetric",
    {item.name: item.value for item in ScoredItem}
    | {name.upper(): name for name in EXTRA_METRICS},
    type=str,
)
SnapshotMetric.__doc__ = _SNAPSHOT_METRIC_DOC

# 7 个国标计分项的值。**从 ``ScoredItem`` 派生**，不手抄：它是 :func:`national_norm`
# 判「这个指标**有没有**国标常模这回事」的第一道依据（第二道是 :func:`norm_is_derivable`
# 的单调性判据——BMI 在词表里、却没有可推导的常模，Ruling 214），与 ``SnapshotMetric``
# 的差集恰好是 :data:`EXTRA_METRICS`。
_SCORED_VALUES: frozenset[str] = frozenset(item.value for item in ScoredItem)


@dataclass(frozen=True)
class PercentileRow:
    """一个 (指标, 性别, 年级组) 分组的百分位快照行。

    业务列与 ORM 的 ``app.db.models.PercentileSnapshot`` 一一对应，故
    :func:`compute_snapshot` 的输出可直接落库；``semester_id`` / ``computed_on`` /
    ``batch_id`` **不在本值对象里**——它们属于「哪一次运行」而不是「这一组的分布」，
    由 Task 10 在写库时补（它本来就握着业务日期，那是幂等键 ``(semester_id,
    business_date)`` 的一半）。Ruling 86 因此把 ``computed_on`` 从
    :func:`compute_snapshot` 的签名里删掉了：**一个被接收然后被丢弃的参数是撒谎**，
    调用方会以为它被记录了。

    ``p10`` … ``p75`` 五个字段与 :data:`PERCENTILES` 逐项对应，且由
    :func:`_percentile_fields` 机械绑定：往 ``PERCENTILES`` 里加一档而忘了加字段
    （或反过来）会在构造时直接 ``TypeError``，不会静默少算一档。

    ``sample_size`` 的两种含义见 :func:`national_norm` 与 :func:`compute_snapshot`：
    常模行是 ``0``（无样本、纯推导），降级行是**真实观测人数**（Review Focus #4 的留痕）。

    ``item`` 的类型是 :class:`SnapshotMetric` 而不是 ``ScoredItem``（Ruling 121）：
    肌肉量行必须能表达，否则 spec §6.3② 的 ``C`` 只能退化成「看体脂率」且不报错。
    """

    item: SnapshotMetric
    sex: Sex
    age_group: str
    p10: float
    p20: float
    p25: float
    p50: float
    p75: float
    sample_size: int
    source: str  # "school" | "national"，与 PercentileSnapshot.SOURCES 同域


def _percentile_fields(values: tuple[float, ...]) -> dict[str, float]:
    """按 :data:`PERCENTILES` 的顺序把五个数值摊成 ``{"p10": …, …}`` 关键字。

    档位数字因此只存在于 ``PERCENTILES`` 一处：推导逻辑与字段名之间没有第二份手抄的
    ``(10, 20, 25, 50, 75)``，两者不一致时构造 :class:`PercentileRow` 会当场 ``TypeError``。
    """
    return dict(zip(_PERCENTILE_FIELDS, values))


def norm_is_derivable(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> bool:
    """该 (项, 性别, 年级组) 上**有没有**可推导的国标常模行（Ruling 214）。

    判据是「沿 ``raw_value`` 升序的得分序列**单调**（不减或不增）」，与
    :func:`~app.domain.indicators.raw_from_score` 拒绝 BMI 的判据**同一条**（Ruling 19：
    「非单调的项直接抛 ``ValueError``」）——两处要问的是同一个问题：「这张档位序列能不能
    当成一个方向一致的阶梯来用」。

    **为什么单调性是承重的**：:func:`national_norm` 的显式假设是「全国参考人群在该项原始值上
    **均匀分布于评分表的量程** ``[lo, hi]``」，而 ``lo`` / ``hi`` 取首末阈值。对非单调的
    区间映射，这个假设**结构性不成立**——BMI 那 4 组的首末阈值是 CSV 用来封口开区间的
    **哨兵** ``0.0`` 与 ``999.0``（``data/README_national_standard.md``：「哨兵 ``0`` 和
    ``999`` 不是国标数值，纯粹是为了把开区间表示成有限档位序列」），于是 ``[lo, hi] =
    [0, 999]``、量程 999，五个分位点全部落到 ``raw >= 249.75`` 的区间 → **五档一律 60 分**，
    且四个 (性别 × 年级组) 完全相同。本轮亲跑复现（``national_norm(standard(), BMI, …)``）::

        male   大一、大二  lo=0.0 hi=999.0 span=999.0  五档=[60.0, 60.0, 60.0, 60.0, 60.0]
        male   大三、大四  lo=0.0 hi=999.0 span=999.0  五档=[60.0, 60.0, 60.0, 60.0, 60.0]
        female 大一、大二  lo=0.0 hi=999.0 span=999.0  五档=[60.0, 60.0, 60.0, 60.0, 60.0]
        female 大三、大四  lo=0.0 hi=999.0 span=999.0  五档=[60.0, 60.0, 60.0, 60.0, 60.0]
        （对照 sprint_50m/male/大一、大二 = [20.0, 40.0, 50.0, 66.0, 74.0]）

    **它确实在生产路径上被产出**：``run_stratify.cohort_snapshot`` 的
    ``for item in ScoredItem`` **含 BMI**，黄金用例那 13 人 < ``MIN_SAMPLE`` 故整组降级，
    实测 28 行快照里 BMI 占 4 行、五档全 60.0（``sample_size`` 分别是 8/1/3/1）。

    **今天不影响分层**：:func:`app.domain.derive.find_weaknesses` 与 :func:`lines_used`
    都只遍历 :data:`~app.domain.indicators.WEAKNESS_ITEMS`（6 项，天然排除 BMI），
    故 ``lookup_p25(BMI, …)`` 在生产上**从无调用者**。但它会被
    :mod:`app.pipeline.percentile_stage` 物化进 ``percentile_snapshot``，而 spec §9.2
    要求「**7 项**国标计分项雷达图（含 P25/P50 参照线）」——Plan 02 一接上，学生看到的
    BMI 参照线就是一条 ``P10 = … = P75 = 60`` 的水平线，四个组还完全相同。
    **它「看起来像一条真判定线」，正是本项目最怕的缺陷形态。**

    **已否决的替代处置：把 ``[lo, hi]`` 收窄到哨兵之内的官方端点**（男 ``[17.8, 28.0]``、
    女 ``[17.1, 28.0]``）。本轮亲跑：那样五档变成 ``[80.0, 80.0, 80.0, 100.0, 100.0]``
    ——不退化了，但它是**另一套编造的常模**，而且更糟：① 它声称「BMI 分位越高得分越高」，
    对一个健康指标方向是反的；② 它把低体重（``< 17.8``）与肥胖（``>= 28.0``）两段
    **整个人群从参考分布里删掉了**，而那两段恰恰是官方给 80 分与 60 分的区间。
    故不采用。

    纯函数，只用公开 API（:func:`~app.domain.indicators.segment_thresholds` +
    :func:`~app.domain.indicators.score_item`），不 import 私有名
    ``_lower_is_better``（本模块的既有纪律，见 :func:`national_norm`）。
    """
    thresholds = segment_thresholds(table, item, sex, age_group)
    scores = [score_item(table, item, raw, sex, age_group) for raw in thresholds]
    return all(b >= a for a, b in zip(scores, scores[1:])) or all(
        b <= a for a, b in zip(scores, scores[1:])
    )


def national_norm(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> PercentileRow:
    """国标常模行：样本不足时的兜底判定线，**是评分表的纯函数，不是第二份数据文件**。

    **只对 7 个国标计分项有效**（Ruling 121 第 4 步）：``muscle_mass_kg`` 这类
    :data:`EXTRA_METRICS` **没有国标常模可降级**——InBody 的肌肉量 P20 是设备与人群
    特异的，国标 2014 里没有它的任何阈值，编一个出来就是凭空捏造判定线（而它直接决定
    谁被标为 ``muscle_low``）。故传入非计分项一律 ``ValueError``；:func:`compute_snapshot`
    对样本不足的肌肉量组**不产出行**，``flag_body_comp`` 于是收到
    ``snapshot_muscle_p20 = None``——与 :func:`lookup_p25` 的 ``None`` 语义同构、
    符合 Ruling 21（缺测不当最坏值）。

    **第二道拒收：非单调的区间型映射（Ruling 214）**。BMI 是 7 个计分项之一、在上面那道
    词表校验里**通过**，但它的官方表是「区间 → 得分」（两头 80、中间 100），CSV 用哨兵
    ``0`` 与 ``999`` 把两个开口区间封成有限档位序列，于是本函数的量程假设
    ``[lo, hi] = [0, 999]`` 是**哨兵之间的区间**而不是生理量程。硬推的后果是实测的：
    四个 (性别 × 年级组) 一律产出 ``p10 = p20 = p25 = p50 = p75 = 60.0`` 的退化行
    ——一条「看起来像真判定线」的水平线。故本函数对
    ``not norm_is_derivable(...)`` 的组抛 ``ValueError``，:func:`compute_snapshot`
    则**不产出该行**（与肌肉量同构，调用方查 P25 得 ``None``）。判据与被否决的
    「收窄到哨兵之内」替代方案见 :func:`norm_is_derivable`。

    **为什么是推导而不是查表（Ruling 84）**：《国家学生体质健康标准（2014 年修订）》
    公布的是**评分阈值**（原始值 → 得分），**不公布人群百分位常模**。所以「数值取自
    国标 2014 常模」这种要求无法照做——只能靠编数字填满一张 CSV，而编出来的常模无法与
    任何真实来源对账，偏偏它正是「样本 < 30 人时」的短板判定线，直接决定谁被标为短板。
    本实现改为从仓内已有的 ``national_standard_2014.csv`` 按一个**显式假设**推导。

    **假设**：全国参考人群在该项原始值上**均匀分布于评分表的量程** ``[lo, hi]``，
    其中 ``lo`` / ``hi`` 取 :func:`~app.domain.indicators.segment_thresholds` 的首末阈值。

    **推导**：得分分布的第 ``p`` 百分位 =
    ``score_item(table, item, lo + q/100 · (hi − lo), sex, age_group)``，其中
    ``q = p``（越大越好）或 ``q = 100 − p``（越小越好）。

    **方向感知是承重的，不是修饰**。50 米跑与耐力跑越小越好，原始值的**低**分位对应
    **高**得分；不做反向映射，这两项会得到 ``P10=80 > P25=74 > P50=66 > P75=50`` 这种
    **递减**序列，而 :class:`PercentileRow` 的语义要求 ``p10 ≤ … ≤ p75``，spec §6.3① 的
    短板判定线 ``score < p25`` 于是彻底失效（P25 变成了偏高的那一段）。方向**从表推断**：
    比较 ``score_item(lo)`` 与 ``score_item(hi)``，前者更大即「越小越好」。
    **不得按项硬编码**——这里用公开 API（``score_item`` 比首末两点）自己推一次，
    不去 import 私有名 :func:`app.domain.indicators._lower_is_better`。

    ⚠️ **但两处推断并不等价，本处此前印的「``_lower_is_better`` 已有同一套推断」是可证伪的**
    （Ruling 215，硬规矩 #39/#43 的第三类盲区：凡声称「两处相同 / 同一套 / 等价 / 一致」的
    散文，必须有一处可执行的比较，否则降级为「设计上应当一致，未被守卫」）。实测两者的判据
    根本不同：``_lower_is_better`` 判「沿 raw 升序得分**全程单调不增**」（``indicators.py`` 的
    ``all(nxt <= cur for cur, nxt in zip(scores, scores[1:]))``，扫完整个档位序列），
    本函数判「``score_item(lo) > score_item(hi)``」即**只看首末两点**。28 组逐组对账
    （本轮亲跑）::

        结论                       组数  明细
        -------------------------- ----  ------------------------------------
        两处一致                    24   16 组两侧都 False（越大越好）
                                         + 8 组两侧都 True（50 米跑、耐力跑）
        两处**相反**                 4   bmi 的 4 个 (性别 × 年级组)：
                                         _lower_is_better=False（它不单调不增）
                                         端点比较=True（80 分 > 60 分）

    BMI 那一侧由 :func:`norm_is_derivable` 的单调性闸**单独兜住**（Ruling 214）：它在本函数
    取 ``lo`` / ``hi`` 之前就抛 ``ValueError``，故端点比较在 BMI 上**根本不会被执行**——
    两处不一致今天没有后果，但那是被另一道闸挡住的，不是「同一套推断」。
    **守卫**：``tests/domain/test_percentile.py`` 的
    ``test_norm_is_derivable_separates_the_24_monotone_groups_from_the_4_bmi_groups``
    钉住 24/4 这个分组（逐组断言、不抽样），
    ``test_national_norm_direction_is_read_from_the_table_not_hardcoded`` 钉住端点比较真的
    在起作用（把方向写反，50 米跑与耐力跑的 P25 会从 50 / 30 跳到 74 / 72）。

    已否决的替代推导：「每个官方档等占比」会让 P25 退化成得分阶梯自己的百分位、几乎丢掉
    全部项别信息，故不采用。**但本处此前印的「对所有项都退化成同一个 ``57.5``」按字面为假**
    ——fix round 3 逐组复算（对 7 个计分项 × 2 性别 × 2 年级组 = **28 组**，各取该组
    ``national_standard_2014.csv`` 里 distinct 官方得分的 25 分位、``method="linear"``）：
    **22 组 = 57.5**、**4 组 = 70.0**（``bmi``，它只有 {60, 80, 100} 三档）、
    **2 组 = 45.0**（男生 ``pull_up_or_sit_up``，15 档）。即 28 组里有 6 组不是 57.5，
    「同一个 57.5」只在 22/28 上成立。结论不变（丢掉项别信息、故不采用），但**这个数
    必须带组名**——与 Ruling 200 那四类缺陷同形：散文比它所在代码更自信。
    **不被守卫**：没有测试断言这三组数，被守的是本函数实际采用的那套推导
    （``tests/domain/test_percentile.py`` 钉住 ``national_norm`` 的五个百分位与方向）。

    **这个假设是占位，不是结论**：真实的全国常模需要教育部公布的人群分布数据，本原型没有。
    已列入 spec §14 待确认 **#24**。换成真实常模时**只需要替换本函数**——推导逻辑一律
    不得散落到调用方，否则换数据源时要改的地方就不止一处，而漏掉的那一处会静默给出
    与别处不一致的判定线。

    **``sample_size`` 在这里写 ``0``**，含义是「无样本、纯推导」，**不是**「样本量为 0」。
    :func:`compute_snapshot` 降级时会把它覆盖为**真实观测人数**（Review Focus #4 的留痕
    要求：研究上要能看出这一组是降级的、且知道实际只有多少人），所以同一组的两处
    ``sample_size`` 不相等是**预期行为**，不是其中一处写错了。

    表里没有这个 (项, 性别, 年级组) 组合时由 ``segment_thresholds`` 抛 ``KeyError``：
    那是调用方传错了组合，属于程序缺陷，不该被静默吞成一个空行。
    """
    # getattr(item, "value", item)：调用方可能传 ScoredItem / SnapshotMetric 成员，也可能
    # 传裸字符串，三种形状都要能判。不查就会退化成 segment_thresholds 的 KeyError，
    # 消息是 "('muscle_mass_kg', 'male', '大一、大二')" ——看不出「肌肉量根本没有常模」这个真因。
    if getattr(item, "value", item) not in _SCORED_VALUES:
        raise ValueError(
            f"national_norm 只对 7 个国标计分项有效，收到 item={item!r}；"
            f"{sorted(EXTRA_METRICS)} 没有国标常模可降级（国标 2014 不含其阈值），"
            f"编一个出来就是凭空捏造判定线。样本不足时该组不产出快照行，"
            f"调用方会收到 None（缺测不当最坏值，Ruling 21）"
        )
    thresholds = segment_thresholds(table, item, sex, age_group)
    if not norm_is_derivable(table, item, sex, age_group):
        raise ValueError(
            f"{getattr(item, 'value', item)}/{sex}/{age_group} 是非单调的**区间型映射**"
            f"（首末阈值 {thresholds[0]!r} 与 {thresholds[-1]!r} 是 CSV 用来封口开区间的哨兵，"
            f"不是国标数值），没有 uniform-in-raw 的常模可推导：把 [{thresholds[0]}, "
            f"{thresholds[-1]}] 当成「全国参考人群均匀分布的量程」会让五个分位点全部落到"
            f"同一个档、产出一行五档全等的假判定线（实测 BMI 四组一律 60.0）。"
            f"样本不足时该组**不产出快照行**，调用方会收到 None（缺测不当最坏值，Ruling 21），"
            f"与 muscle_mass_kg 的处置同构（Ruling 121 第 4 步 / Ruling 214）"
        )
    lo, hi = thresholds[0], thresholds[-1]
    span = hi - lo
    # 方向从表推断（见 docstring）：原始值低端得分更高 ⇒ 越小越好 ⇒ 分位取补
    lower_is_better = score_item(table, item, lo, sex, age_group) > score_item(
        table, item, hi, sex, age_group
    )
    values = tuple(
        float(
            score_item(
                table,
                item,
                lo + span * ((100 - p) if lower_is_better else p) / 100.0,
                sex,
                age_group,
            )
        )
        for p in PERCENTILES
    )
    return PercentileRow(
        item=item,
        sex=sex,
        age_group=age_group,
        **_percentile_fields(values),
        sample_size=0,
        source="national",
    )


def _validated_member(enum_type, value, field: str, index: int):
    """把 ``scores[index][field]`` 构造成 ``enum_type`` 的成员，失败时报出**可定位**的消息。

    ``Sex(...)`` / ``SnapshotMetric(...)`` 本来就会在 :func:`compute_snapshot` 的分组那一行抛
    ``ValueError``，但消息只有 ``'MALE' is not a valid Sex``——不说第几行、也不说合法取值
    有哪些。500 人 × 7 项的批次里这条消息等于没给线索，故在入口显式校验（Ruling 118-M3）。

    ``item`` 按 :class:`SnapshotMetric` 校验而**不是** ``ScoredItem``（Ruling 121 第 2 步）：
    肌肉量行必须能在入口通过，否则它连分组都进不去，spec §6.3② 的 P20 判定线永远算不出来
    ——而那是**静默**的（``C`` 退化成只看体脂率，全程不报错）。
    """
    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(
            f"scores[{index}] 的 {field}={value!r} 不是合法的 {enum_type.__name__}，"
            f"合法取值是 {[member.value for member in enum_type]}"
        ) from None


def compute_snapshot(
    scores: list[dict], table: StandardTable
) -> list[PercentileRow]:
    """一批样本 → 每个 (指标, 性别, 年级组) 分组最多一行百分位快照。

    ``scores`` 每项形如
    ``{"sex": str, "age_group": str, "item": SnapshotMetric, "score": int | float}``。
    对 7 个国标计分项，``score`` **必须已经是
    :func:`~app.domain.indicators.score_item` 正查出来的国标单项得分**（spec §4.0：
    统一为越大越好后再算百分位）；对 :data:`EXTRA_METRICS`（肌肉量）则是**清洗后的原始
    kg 读数**——它没有国标得分，而「越大越好」是它的天然方向，故直接在 kg 上切分位
    （Ruling 121）。分组键是 ``(sex, age_group, item)``，与 ORM ``PercentileSnapshot``
    的五列业务唯一键去掉「哪个学期、哪一天」后完全一致——同一组最多产出**一行**，
    计分项样本不足时整组降级为 ``source = "national"``，不是「校内行 + 常模行」并存两行。

    **肌肉量组样本 < ``MIN_SAMPLE`` 时不产出该行**（Ruling 121 第 4 步）：它没有国标
    常模可降级（理由见 :func:`national_norm`）。缺行的后果是调用方查 P20 得 ``None``、
    ``flag_body_comp`` 的肌肉量那一支无从成立——**合法状态，不是异常**，与
    :func:`lookup_p25` 的 ``None`` 语义同构。留痕靠 Task 10 在 ``DailySyncRun`` 的摘要里
    计「缺线组数」，**不新增第三个 ``reasons`` token**（Ruling 97① 冻结了 vocabulary）。

    **两条口径由调用方保证，本函数不查**（Ruling 121）：① 肌肉量的**样本单位是学生**，
    每人只入一行（取该生 ``<= business_date`` 的最新一条体成分）——按测量行入样会把同一个人
    的三次测量当三个样本，两种口径给出的 P20 **不同**、足以翻掉几个人的 ``C``；
    ② 入样的必须是**清洗后**的值——缺省注入下存在 ``muscle_mass_kg = 135.0`` 这类越界值，
    未清洗会把 P20 拉高。

    ①的量级（fix round 3 实测，500 人 / ``seed=20250828``，学生级走生产的
    :func:`app.pipeline.run_stratify.cohort_snapshot`、行级把每条体成分记录都当一个样本；
    **差值按 (性别, 年级组) 分组给，不是一个数**）::

        组                    缺省注入 学生级/行级/差     零注入 学生级/行级/差
        female 大一、大二      23.70 / 23.30 / +0.40      23.70 / 23.30 / +0.40
        female 大三、大四      23.60 / 23.30 / +0.30      23.60 / 23.30 / +0.30
        male   大一、大二      33.14 / 33.00 / +0.14      33.20 / 33.10 / +0.10
        male   大三、大四      33.44 / 33.50 / −0.06      33.56 / 33.50 / +0.06

        C 标记翻动的人数（学生级线 vs 行级线）：男 2 + 女 5 = **7 人**（两种注入下相同）

    本处与 :func:`app.pipeline.run_stratify.cohort_snapshot` 此前都印着「差 0.2 kg，足以
    翻**十几个**人的 ``C``」：0.2 kg 只是上表四个组里最小的那个量级（实际跨度 −0.06 到
    +0.40 kg、**符号都会翻**），「十几个人」在本口径下复现不出来——fix round 3 量到的是
    7 人。把行级样本改成「只取本学年的 3 条」会让差值再变一组（female +0.20/+0.10、
    male −0.06/−0.32，翻动 6 人），故**这个量级本身高度依赖行级样本怎么取**，只能当
    「足以翻人」的定性证据用，不能当可复现的定量基线。**不被守卫**：没有测试同时跑两种
    口径；被守的是「每人最多一行」这个约定本身——``cohort_snapshot`` 的构造逐人只 append
    一次肌肉量行，改成逐测量行会让上面的 P20 漂移、进而让
    ``tests/integration/test_golden_cases.py`` 的分层分布断言红。

    **调用方职责：每个 (学生, 项目) 组合只能出现一行。** 本函数逐行收样本，同一学生在
    同一项目上出现两行就会被当成**两个独立样本**计入分位数，把 P25 拉向重复值那一侧——
    而 P25 正是 spec §6.3① 里短板判定 ``W`` 的唯一判定线，「谁被标为短板」于是随重复行
    一起漂移，且全程不报错。生产路径上这道去重由 **Task 5 的清洗层**负责：体测按
    ``(student_no, batch_key)``、体成分按 ``(student_no, measured_on)`` 去重，各自保留
    输入顺序中靠后的一行（见 :mod:`app.pipeline.clean`）。

    :func:`compute_snapshot` **刻意不做第二道去重**，两个理由：① 它是 domain 层的内部
    边界而不是系统入口，重复校验属于上游职责，在这里再查一遍只会让「去重的所有者是谁」
    变得含糊；② 更要紧的是**静默去重会掩盖上游去重失效**——那正是本项目反复吃亏的缺陷
    形态：一处代码把另一处的错误悄悄吸收掉，测试全绿、日志无异常，直到结论错了才暴露。
    宁可让重复样本如实体现在分位数上，也不要让它消失在第二次去重里。

    契约里**没有** ``student_id``。调用方传入多余的键（例如它手里的 ORM 行本来就带着
    ``student_id``）**不会被拒绝**，只是不被消费：分组只读 ``sex`` / ``age_group`` /
    ``item``，百分位只读 ``score``。Ruling 88 把它从契约里删掉，与 Ruling 86 删掉
    ``computed_on`` 参数同理——**一个被接收然后被丢弃的字段是撒谎**，列在契约里会让人
    以为它参与了去重或留痕。

    五档用 ``np.percentile(..., method="linear")``，档位一律取自 :data:`PERCENTILES`。
    返回值按 ``(item, sex, age_group)`` 排序，故同一批输入的行序是**规范序**而不依赖
    调用方拼装 ``scores`` 的顺序（Task 10 的幂等重放可以直接逐行对比）。

    **计分项样本 < ``MIN_SAMPLE`` 时整组改用 :func:`national_norm` 兜底，但 ``sample_size``
    覆盖为真实观测人数**（Review Focus #4）。降级行除 ``sample_size`` 外**逐字段等于**
    ``national_norm`` 的产出（用 :func:`dataclasses.replace` 保证，不是手抄五个字段），
    否则「降级到国标常模」这句话就没有可核对的含义。常模行自己的 ``sample_size`` 是
    ``0``（含义见 :func:`national_norm`），两者不相等是**预期行为**。**两类组没有这条
    兜底路径、样本不足时整组不产出行**（见上）：肌肉量（:data:`EXTRA_METRICS`），以及
    非单调的区间型映射（BMI，判据 :func:`norm_is_derivable`，Ruling 214）——后者硬推会得到
    一行五档全 ``60.0`` 的假判定线。

    **并列（ties）的后果——刻意口径，不是缺陷**：就低取档（Ruling 18）使每项得分只有
    ≤20 个离散取值（男引体向上仅 15 个），``method="linear"`` 在大量并列处会给出
    ``57.5`` 这类**半分**；而 spec §14 **#21** 定了短板判定用**严格小于**（``score < p25``）。
    两者叠加的效果是：若某组有 30% 的人同为 60 分且 P25 恰为 60，这 30% **全都不算**短板
    （改用 ``<=`` 则全算，会实质改变 ``W``、改变红黄绿比例、甚至改变 ``valid_count >= 4``
    闸门的通过情况）。下游因此必须知道 ``p25`` **可能是半分**，不得假定它是官方档位分。

    **入口校验三个分组字段**（Ruling 118-M3）：``age_group`` 必须取
    :data:`~app.domain.indicators.AGE_GROUPS` 里的年级组名，``sex`` / ``item`` 必须能构造成
    :class:`~app.domain.indicators.Sex` / :class:`SnapshotMetric`，
    否则 ``ValueError``，消息报出**第几行、哪个字段、收到什么值**（``scores[i] 的 …``）。
    此前 ``age_group`` **完全不校验**：非法组名在 ``n >= MIN_SAMPLE`` 时静默产出一行
    ``lookup_p25`` 永远匹配不上的快照（该组全员零短板、``valid_count = 0``），
    ``n < MIN_SAMPLE`` 时才因走 :func:`national_norm` 而 ``KeyError``——**同一种输入错误
    响不响亮取决于样本量**，比一律静默更难查（实测 ``age_group="18-19"``：``n=40`` 无错、
    产出一行 ``p25=23.25`` 且合法组名查它得 ``None``；``n=5`` 才 ``KeyError``）。
    ``sex`` / ``item`` 本来也会抛 ``ValueError``，但消息不含行号，故一并改成显式校验。
    这与 Ruling 107 给 :func:`app.domain.derive.derive` 加的校验是**同一条口径**
    （``AGE_GROUPS`` 是全仓唯一清单，不另立第二份）：那边堵**消费者**传错组名，
    这边堵**生产者**写错组名。

    纯函数：不碰数据库、不读盘、不碰时钟（``table`` 由调用方注入，Ruling 87），
    也不接受 ``computed_on``（Ruling 86）。Task 1 的三个 AST 守卫会扫本模块。
    """
    groups: dict[tuple[Sex, str, SnapshotMetric], list[float]] = {}
    for index, row in enumerate(scores):
        sex = _validated_member(Sex, row["sex"], "sex", index)
        item = _validated_member(SnapshotMetric, row["item"], "item", index)
        age_group = row["age_group"]
        if age_group not in AGE_GROUPS:
            raise ValueError(
                f"scores[{index}] 的 age_group={age_group!r} 不是合法的年级组名，"
                f"合法清单是 {list(AGE_GROUPS)}（app.domain.indicators.AGE_GROUPS，"
                f"全仓唯一口径）；非法组名在 n >= MIN_SAMPLE 时静默产出一行 "
                f"lookup_p25 永远匹配不上的快照（该组全员零短板、valid_count=0），"
                f"n < MIN_SAMPLE 时才在 national_norm 里 KeyError"
            )
        groups.setdefault((sex, age_group, item), []).append(float(row["score"]))

    snapshot: list[PercentileRow] = []
    for (sex, age_group, item), group in groups.items():
        if len(group) < MIN_SAMPLE:
            if item.value in EXTRA_METRICS or not norm_is_derivable(
                table, item, sex, age_group
            ):
                # 两类「没有国标常模可降级」：① 肌肉量等非计分项（Ruling 121 第 4 步）；
                # ② 非单调的区间型映射（BMI，Ruling 214）——它的「量程」端点是 CSV 哨兵
                # 0/999，硬推会得到一行五档全 60.0 的假判定线。整组不产出行，
                # 调用方查 P25/P20 得 None，与 lookup_p25 的 None 语义同构。
                continue
            snapshot.append(
                replace(
                    national_norm(table, item, sex, age_group),
                    sample_size=len(group),
                )
            )
            continue
        percentiles = np.percentile(
            np.asarray(group, dtype=float), list(PERCENTILES), method="linear"
        )
        snapshot.append(
            PercentileRow(
                item=item,
                sex=sex,
                age_group=age_group,
                **_percentile_fields(tuple(float(v) for v in percentiles)),
                sample_size=len(group),
                source="school",
            )
        )
    snapshot.sort(key=lambda r: (r.item.value, r.sex.value, r.age_group))
    return snapshot


def _lookup_row(
    snapshot: list[PercentileRow],
    item: SnapshotMetric,
    sex: Sex,
    age_group: str,
) -> PercentileRow | None:
    """取某 (指标, 性别, 年级组) 的快照行；该组不存在时返回 ``None``。

    比较一律用 ``==``，而 ``Sex`` / ``ScoredItem`` / :class:`SnapshotMetric` 都是 ``str``
    枚举，故传枚举成员或裸字符串（``"male"`` / ``"sprint_50m"``）都能命中同一行；
    ``SnapshotMetric.SPRINT_50M == ScoredItem.SPRINT_50M`` 也为真（两者都是值为
    ``"sprint_50m"`` 的 ``str``），跨枚举传参不会静默失配。
    """
    for row in snapshot:
        if row.item == item and row.sex == sex and row.age_group == age_group:
            return row
    return None


def lookup_p25(
    snapshot: list[PercentileRow],
    item: ScoredItem,
    sex: Sex,
    age_group: str,
) -> float | None:
    """从快照里取某 (项, 性别, 年级组) 的短板判定线 P25；该组不存在时返回 ``None``。

    Task 8 的 ``find_weaknesses`` 用它实现 spec §6.3①：``单项得分 < P25`` 记为显性短板。
    **返回 ``None`` 表示「这一组没有判定线」**，与「判定线是 0 分」是两件不同的事：
    调用方必须把 ``None`` 当作该项**不计入 ``W``**（等同缺测，绝不当 0 分、也绝不当
    「不短板」而静默跳过统计），否则没有快照的组会被系统性地判成零短板。

    比较一律用 ``==``，而 ``Sex`` / ``ScoredItem`` 都是 ``str`` 枚举，故传枚举成员或
    传裸字符串（``"male"`` / ``"sprint_50m"``）都能命中同一行。

    返回的 ``p25`` **可能是半分**（如 ``57.5``），且判定用**严格小于**（spec §14 #21）——
    并列的后果见 :func:`compute_snapshot` 的 docstring。
    """
    row = _lookup_row(snapshot, item, sex, age_group)
    return None if row is None else row.p25


def lookup_p20(
    snapshot: list[PercentileRow],
    sex: Sex,
    age_group: str,
) -> float | None:
    """从快照里取某 (性别, 年级组) 的**肌肉量** P20 判定线；该组不存在时返回 ``None``。

    spec §6.3② 的 ``C = (体脂率 > 阈值) OR (肌肉量 < 同龄同性别 P20)``，本函数是那条
    P20 的唯一读取口（Ruling 121）。指标固定为 :data:`MUSCLE_MASS`，故签名里没有
    ``item`` 参数——**一个只有一个合法取值的参数是撒谎**，它会让调用方以为可以传别的项。

    ``None`` 的语义与 :func:`lookup_p25` 同构：该组肌肉量样本 < ``MIN_SAMPLE`` 时
    :func:`compute_snapshot` 不产出行（没有国标常模可降级），于是 ``flag_body_comp`` 的
    肌肉量那一支无从成立。**这是合法状态而不是异常**（Ruling 21：缺测不当最坏值），
    代价是缺 InBody 数据的人 ``C`` 更容易为 ``False``、干预不足，已在
    :func:`app.domain.derive.flag_body_comp` 的 docstring 里如实记录。

    注意肌肉量行的 ``p20`` 是**kg 读数**而不是 0–100 的得分（它没有国标得分），
    与 ``muscle_mass_kg`` 同量纲，可直接比较。
    """
    row = _lookup_row(snapshot, SnapshotMetric(MUSCLE_MASS), sex, age_group)
    return None if row is None else row.p20


def lookup_p10(
    snapshot: list[PercentileRow],
    sex: Sex,
    age_group: str,
) -> float | None:
    """从快照里取某 (性别, 年级组) 的**肌肉量** P10 判定线；该组不存在时返回 ``None``。

    Plan 02 Task 7 新增（P7-A3）。**与 :func:`lookup_p20` 逐字同构**：同一个
    :func:`_lookup_row`、同一套「该组无行 → ``None``」语义、同样的签名（指标固定为
    :data:`MUSCLE_MASS`，故没有 ``item`` 形参——**一个只有一个合法取值的参数是撒谎**）。
    差别只有两处，都是**必须**不同的：取的列（``row.p10`` 而不是 ``row.p20``）与下面这段
    「谁消费它」。

    **消费者是 spec §7.4 的处方安全后置，不是分层**：
    :func:`app.domain.prescription.safety.apply_safety` 的
    :class:`~app.domain.prescription.safety.SafetyInput.muscle_p10` 用它，判据是
    「肌肉量 < 同龄同性别 **P10**」。⚠️ **本函数绝不进分层判定**（红线，P7-A3）：
    spec §6.3② 的体成分异常 ``C`` 用的是 **P20**，由 :func:`lookup_p20` 供，
    :func:`app.domain.derive.flag_body_comp` 的签名里只有 ``snapshot_muscle_p20`` 一个
    分位形参（守卫 ``tests/domain/test_derive.py`` 的
    ``test_smi_is_not_an_input_at_all`` 把那个签名逐字钉住）。两条线**服务两件不同的事**：
    P20 判「这个人今天的体成分算不算异常」（→ 分层标签），P10 判「给这个人的训练包
    要不要做安全降级」（→ ``needs_review``）。P10 < P20，把 P10 喂进 ``flag_body_comp``
    会**收窄** ``C`` 的触发面、改掉 Plan 01 已结案的分层标签，13 例黄金用例当场红。
    行为侧的守卫是 ``tests/pipeline/test_prescription_stage.py`` 的
    ``test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict``。

    ``None`` 的语义与 :func:`lookup_p20` / :func:`lookup_p25` 同构：该组肌肉量样本
    < ``MIN_SAMPLE`` 时 :func:`compute_snapshot` 不产出行（没有国标常模可降级），
    于是安全后置的肌肉量那一支无从成立。**这是合法状态而不是异常**（Ruling 21：缺测
    不当最坏值）；:func:`app.domain.prescription.safety.apply_safety` 对 ``None`` 的处置
    是**不触发 + 在 ``safety_skipped`` 里留痕**（token ``"muscle_p10_missing"``），
    与 :func:`app.domain.derive.flag_body_comp` 收到 ``snapshot_muscle_p20 = None`` 时的
    处置同向。

    注意肌肉量行的 ``p10`` 是**kg 读数**而不是 0–100 的得分（它没有国标得分），
    与 ``muscle_mass_kg`` 同量纲，可直接比较。
    """
    row = _lookup_row(snapshot, SnapshotMetric(MUSCLE_MASS), sex, age_group)
    return None if row is None else row.p10


def lines_used(
    curr: dict[ScoredItem, int | None],
    snapshot: list[PercentileRow],
    sex: Sex,
    age_group: str,
) -> list[PercentileRow]:
    """本生的短板判定里**实际用上**的判定线行（Ruling 137 的输入）。

    判据与 :func:`app.domain.derive.find_weaknesses` 逐字同构：只遍历
    :data:`~app.domain.indicators.WEAKNESS_ITEMS`（6 项，天然排除 BMI），且要求
    「该项有得分」**且**「该 (项, 性别, 年级组) 组有快照行」——两种「不算」都会同时压低
    ``W`` 与 ``valid_count``，故本函数返回的行数**恒等于** ``WeaknessResult.valid_count``
    （由 ``tests/domain/test_percentile.py`` 的
    ``test_lines_used_count_equals_valid_count`` 钉住，两处判据漂移当场红）。

    **为什么需要它**：``stratification_result.percentile_source`` 要交代「这个人的判定线
    是校内百分位还是国标兜底」，而 ``DerivedResult`` 不携带所用行（Ruling 126 的同一处置：
    不为一个未定义的字段扩容值对象）。有了本函数，来源汇总就是一个纯函数，
    不必让 ``find_weaknesses`` 多返回一份没人消费的行清单。
    """
    used: list[PercentileRow] = []
    for item in WEAKNESS_ITEMS:
        if curr.get(item) is None:
            continue
        row = _lookup_row(snapshot, item, sex, age_group)
        if row is not None:
            used.append(row)
    return used


def summarize_source(rows: Iterable[PercentileRow]) -> str:
    """把 :func:`lines_used` 的行汇总成 ``stratification_result.percentile_source`` 的取值。

    三条口径（Ruling 137），全部由「用过哪些行」这一个输入决定：

    * **一行都没用过** → ``"none"``。它对应 ``valid_count = 0``（Z0 闸门直接拦下）：
      填 ``"school"`` 会声称「这个人的判定线来自校内百分位」，而他根本没有判定线，
      那是一条凭空造出的可追溯性。
    * **用过 1–3 行**（Z0 命中，但确实用过判定线）→ 按实际用过的那些行汇总，规则同下条。
    * **用过 6 行且 school / national 混用** → **任一项降级即 ``"national"``**。取保守侧：
      告诉教师「这个人的判定线里有人是兜底来的」比反过来安全——反过来说会让一个部分
      依赖推导常模的判定被当成校内实测分布，而它正是「谁被标为短板」的唯一依据。

    取值域与 ORM ``StratificationResult.PERCENTILE_SOURCES`` 逐字相同
    （``{"school", "national", "none"}``），最长 ``"national"`` = 8 字符，列宽 ``String(8)`` 够。
    """
    sources = {row.source for row in rows}
    if not sources:
        return "none"
    return "national" if "national" in sources else "school"
