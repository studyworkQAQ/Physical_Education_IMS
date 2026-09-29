"""校内百分位快照：同校区 × 同性别 × 同年级组的五档得分分布，以及样本不足时的国标常模兜底。

spec §4.0 规定「百分位一律在国标单项得分上算，而不是在原始值上算」——原始值方向不一致
（50 米跑、耐力跑越小越好），直接对原始值切 P25 会得出相反结论。本模块因此只吃**已经
正查成 0–100 的得分**，方向问题在 :mod:`app.domain.indicators` 那一层就已经被抹平。

本模块是纯计算叶子，与 :mod:`app.domain.indicators` 同一条纪律（Ruling 15 / Ruling 87）：
不碰数据库、不读盘、不碰时钟，评分表由调用方（Task 10 用 ``app.refdata.standard()``）
显式注入。**刻意不 import ``app.refdata``**：domain 层若经两跳间接依赖唯一会读盘的模块，
Task 1 的 AST 纯净性守卫就被架空（守卫拦的是字面模式，拦不住「import 一个会读盘的模块」），
而且每条单元测试都会被迫读真实 CSV，再也造不出「表里只有 3 个档」这种边界形状。

物化由 Task 10 的管道负责（spec §4.0：百分位**必须物化为快照表，禁止实时计算**，否则
分层结果无法复现任意一天的状态）。本模块只产出值对象。
"""
from dataclasses import dataclass, replace

import numpy as np

from app.domain.indicators import ScoredItem, Sex, score_item, segment_thresholds
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


@dataclass(frozen=True)
class PercentileRow:
    """一个 (项目, 性别, 年级组) 分组的百分位快照行。

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
    """

    item: ScoredItem
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


def national_norm(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> PercentileRow:
    """国标常模行：样本不足时的兜底判定线，**是评分表的纯函数，不是第二份数据文件**。

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
    **不得按项硬编码**——:func:`app.domain.indicators._lower_is_better` 已有同一套推断，
    但它是私有的，这里用公开 API 自己推一次，不去 import 私有名。

    已否决的替代推导：「每个官方档等占比」会让 P25 对**所有项**都退化成同一个 ``57.5``
    （它只是得分阶梯的百分位，丢掉了全部项别信息），实测确认，故不采用。

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
    thresholds = segment_thresholds(table, item, sex, age_group)
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


def compute_snapshot(
    scores: list[dict], table: StandardTable
) -> list[PercentileRow]:
    """一批国标单项得分 → 每个 (项目, 性别, 年级组) 分组一行百分位快照。

    ``scores`` 每项形如
    ``{"sex": str, "age_group": str, "item": ScoredItem, "score": int}``，
    其中 ``score`` **必须已经是 :func:`~app.domain.indicators.score_item` 正查出来的
    国标单项得分**（spec §4.0：统一为越大越好后再算百分位）。分组键是
    ``(sex, age_group, item)``，与 ORM ``PercentileSnapshot`` 的五列业务唯一键去掉
    「哪个学期、哪一天」后完全一致——同一组只产出**一行**，样本不足时整组降级为
    ``source = "national"``，不是「校内行 + 常模行」并存两行。

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

    **样本 < ``MIN_SAMPLE`` 时整组改用 :func:`national_norm` 兜底，但 ``sample_size``
    覆盖为真实观测人数**（Review Focus #4）。降级行除 ``sample_size`` 外**逐字段等于**
    ``national_norm`` 的产出（用 :func:`dataclasses.replace` 保证，不是手抄五个字段），
    否则「降级到国标常模」这句话就没有可核对的含义。常模行自己的 ``sample_size`` 是
    ``0``（含义见 :func:`national_norm`），两者不相等是**预期行为**。

    **并列（ties）的后果——刻意口径，不是缺陷**：就低取档（Ruling 18）使每项得分只有
    ≤20 个离散取值（男引体向上仅 15 个），``method="linear"`` 在大量并列处会给出
    ``57.5`` 这类**半分**；而 spec §14 **#21** 定了短板判定用**严格小于**（``score < p25``）。
    两者叠加的效果是：若某组有 30% 的人同为 60 分且 P25 恰为 60，这 30% **全都不算**短板
    （改用 ``<=`` 则全算，会实质改变 ``W``、改变红黄绿比例、甚至改变 ``valid_count >= 4``
    闸门的通过情况）。下游因此必须知道 ``p25`` **可能是半分**，不得假定它是官方档位分。

    纯函数：不碰数据库、不读盘、不碰时钟（``table`` 由调用方注入，Ruling 87），
    也不接受 ``computed_on``（Ruling 86）。Task 1 的三个 AST 守卫会扫本模块。
    """
    groups: dict[tuple[Sex, str, ScoredItem], list[float]] = {}
    for row in scores:
        key = (Sex(row["sex"]), row["age_group"], ScoredItem(row["item"]))
        groups.setdefault(key, []).append(float(row["score"]))

    snapshot: list[PercentileRow] = []
    for (sex, age_group, item), group in groups.items():
        if len(group) < MIN_SAMPLE:
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
    for row in snapshot:
        if row.item == item and row.sex == sex and row.age_group == age_group:
            return row.p25
    return None
