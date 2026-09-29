"""国标 2014 的指标定义、能力桶映射，以及评分表的正查/反查纯函数。

本模块是纯计算叶子：不碰磁盘、不碰数据库、不碰网络，也不自己取当前时刻——
时间与随机数一律由调用方注入，评分表一律由调用方（app/refdata.py 加载）作为
首参传入（Ruling 15）。只有这样，spec §1.3「逐人可追溯」与 §12「黄金用例」
才站得住：同一张表、同一个输入，永远得到同一个输出。
"""
from enum import Enum

from app.domain.tables import StandardTable


class Sex(str, Enum):
    """国标按性别分列评分表；引体向上（男）与一分钟仰卧起坐（女）也靠它区分。"""

    MALE = "male"
    FEMALE = "female"


class ScoredItem(str, Enum):
    """大学组的 7 个计分项，对应国标「单项指标与权重」表的全部行。"""

    BMI = "bmi"
    VITAL_CAPACITY = "vital_capacity"
    SPRINT_50M = "sprint_50m"
    SIT_AND_REACH = "sit_and_reach"
    STANDING_JUMP = "standing_jump"
    PULL_UP_OR_SIT_UP = "pull_up_or_sit_up"
    DISTANCE_RUN = "distance_run"


# 短板判定只看这 6 项。BMI 被排除：它是身体形态指标而不是可训练的能力短板，
# 且其官方评分是「区间 → 得分」的映射，与能力项不同构，混进桶化短板逻辑会失真。
WEAKNESS_ITEMS: tuple[ScoredItem, ...] = (
    ScoredItem.VITAL_CAPACITY,
    ScoredItem.SPRINT_50M,
    ScoredItem.SIT_AND_REACH,
    ScoredItem.STANDING_JUMP,
    ScoredItem.PULL_UP_OR_SIT_UP,
    ScoredItem.DISTANCE_RUN,
)

# 能力桶：处方引擎按桶聚合短板后给运动处方，BMI 不归桶
ITEM_BUCKET: dict[ScoredItem, str | None] = {
    ScoredItem.BMI: None,
    ScoredItem.VITAL_CAPACITY: "endurance",
    ScoredItem.DISTANCE_RUN: "endurance",
    ScoredItem.PULL_UP_OR_SIT_UP: "strength",
    ScoredItem.STANDING_JUMP: "strength",
    ScoredItem.SPRINT_50M: "speed_flexibility",
    ScoredItem.SIT_AND_REACH: "speed_flexibility",
}

# 国标 2014「说明」第 4 条：小学、初中、高中按每个年级为一组，
# 「大学一、二年级为一组，三、四年级为一组」。大学这里官方是按年级组划分、
# 没有年龄段，所以 AGE_GROUPS 直接用官方的两个年级组名，不另造年龄带。
AGE_GROUPS: tuple[str, ...] = ("大一、大二", "大三、大四")

# 典型在校年龄：大一 18、大二 19、大三 20、大四 21，故以 19/20 岁为两组分界
_LOWER_GRADE_MAX_AGE = 19


def age_group_of(age: int) -> str:
    """把年龄折算成国标 2014 的大学年级组。

    国标按年级而非年龄分组，这里按典型入学年龄折算：不超过 19 岁归
    ``大一、大二``，20 岁及以上归 ``大三、大四``；超出常见在校年龄（18–22 岁）
    的输入会自然落到端点组，不会产出评分表里不存在的键。
    """
    return AGE_GROUPS[0] if age <= _LOWER_GRADE_MAX_AGE else AGE_GROUPS[1]


def _segments_of(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> tuple[tuple[float, int], ...] | None:
    return table.segments.get((item.value, sex.value, age_group))


def _lower_is_better(segments: tuple[tuple[float, int], ...]) -> bool:
    """该项是否「越小越好」——沿 raw_value 升序看得分是否全程单调不增。

    方向从表推断，不按项硬编码。对沿 raw 单调的表（除 BMI 外全部 26 组），
    这与「首档得分 < 末档得分则为越大越好」完全等价；BMI 是非单调的区间映射
    （两头 80、中间 100），不满足单调不增，故落入「越大越好」分支——那正是它的
    CSV 落法所要求的口径：每个官方闭区间端点起（含）到下一端点前取该端点的分。
    """
    scores = [score for _, score in segments]
    return all(nxt <= cur for cur, nxt in zip(scores, scores[1:]))


def score_item(
    table: StandardTable,
    item: ScoredItem,
    value: float | None,
    sex: Sex,
    age_group: str,
) -> int | None:
    """正查：原始成绩 → 国标单项得分。

    **就低取档的阶梯查表，不做插值**（Ruling 18）。国标评分表是离散阈值表，官方
    口径是「落在哪一档就拿哪一档的分」：越大越好取**最大的 ``raw_i <= value``**，
    越小越好取**最小的 ``raw_i >= value``**。插值会产出 56/61/92 这类国标里根本不
    存在的分数（实测立定跳远 210 cm 插值给 61 分、官方是 60 分；1000 米 280 秒
    插值给 56 分、官方是 50 分），使系统单项分与学校官方体测报表无法逐格对账，
    而 spec §12 黄金用例与 §1.3 可追溯性正是要拿真实报表校验的。阶梯查表无插值
    即无舍入，``round()`` 的银行家舍入偏差也随之消失。

    **越界一律夹到所落那一端的档位分，绝不返回 ``None``**（Ruling 17）。
    ``segments`` 按原始值升序，所以「优于表内最好档」与「差于表内最差档」都由同一句
    夹取自动落到正确端点：哪一端是高分由表自身的单调性决定。国标本来就是这么给分的：
    低于最低档的成绩拿最低档的分，而不算「没有成绩」。

    ``None`` 只保留给两种**真缺测**情形：``value`` 缺失，或表里没有这个
    (项, 性别, 年级组) 组合。任何路径都不抛异常、也不返回 0。

    把差到表外的真实成绩判成 ``None`` 是会静默反转研究结论的缺陷：``None`` 在下游
    一律等于「没测」，既拉低 ``valid_count``（有效项不足 4 个直接不分层），又让该项
    不计入短板数 ``W``——体能最差的学生因此被系统性地筛出红色干预层，全程不报错。

    **前置条件：``value`` 必须已经是清洗过的值**（Ruling 21）。本函数对越界只做夹取，
    不判断读数是否物理可能，因此调用方必须先把物理上不可能的读数转成 ``None`` 再传入：
    高侧如 50 米跑 999 秒（夹到底档 10 分，压分），低侧如 50 米跑 0.0 秒——
    ``0`` 是数值列最常见的缺测占位，而低侧夹取对「越小越好」的项意味着**低值得高分**，
    实测 50 米跑与耐力跑的 0.0 秒都返回 **100 分**：一个缺测项会给体能最差的学生送上
    20% 权重的满分，还同时抹掉两个桶的短板。这比高侧更危险，因为它抬分而非压分。
    处置不能放在这里一刀切拒绝 ``<= 0``（引体向上 0 次、坐位体前屈 −1.3 cm 都是合法
    真实值），必须由 Task 5 的清洗层按 ``indicator_ranges.yaml`` 的逐字段
    ``non_positive_is_missing`` 标记完成。
    """
    if value is None:
        return None
    segments = _segments_of(table, item, sex, age_group)
    if not segments:
        return None
    low_raw, low_score = segments[0]
    high_raw, high_score = segments[-1]
    if value < low_raw:
        return low_score
    if value > high_raw:
        return high_score
    # 上面两次夹取已保证 low_raw <= value <= high_raw，故下面两个生成式必然非空
    if _lower_is_better(segments):
        return next(score for raw, score in segments if raw >= value)
    return next(score for raw, score in reversed(segments) if raw <= value)


def raw_from_score(
    table: StandardTable, item: ScoredItem, score: int, sex: Sex, age_group: str
) -> float:
    """反查：目标单项得分 → 原始成绩，供仿真数据生成按目标分数造出可信的实测值。

    用的是与 :func:`score_item` 同一张表、同一套档位，口径同样是**就低取档**：
    请求分不一定是官方档（Task 6 会算出 73 这类连续目标分），此时先把它落到
    **不超过请求分的最大官方档**，再返回**映射到该档的原始值区间的中点**。
    因此 ``score_item(table, item, raw_from_score(...), ...)`` 精确还原的是那个官方档
    的分（如请求 73 → 落 72 档 → 回代得 72），不是请求分本身。请求分高于表内最高档
    时落到最高档、低于最低档时落到最低档，即夹到端点档的区间。

    区间中点对整数次数项（引体向上／仰卧起坐）会是 ``13.5`` 这类半数：调用方若要取整，
    **必须向下取整到带内整数**（13.5 → 13 仍是 72 分）；向上取整会跨到上一档（14 → 76 分）。

    **非单调的项直接抛 ``ValueError``**：只有 BMI 是这样（两头 80、中间 100）。
    它的档位序列里同一个分对应两段互不相邻的原始值区间，「反查唯一原始值」这个问题
    本身不成立；照旧返回会泄漏 CSV 用来封口开区间的哨兵值——实测
    ``raw_from_score(table, BMI, 80, ...)`` 返回 ``0.0``，而 80 分恰是 BMI 最常见的
    目标分（低体重与超重都是 80），下游会因此造出 BMI = 0 kg/m² 的学生，且因为
    ``score_item(table, BMI, 0.0, ...) == 80`` 往返测试全绿，缺陷被完美掩盖。
    正确做法是直接生成身高与体重、算出 BMI 后用 :func:`score_item` 正查得分。

    表里没有这个 (项, 性别, 年级组) 组合时抛 ``KeyError``：那是调用方传错了组合，
    属于程序缺陷，与「学生某项缺测」不是一回事，不该被静默吞掉。
    """
    segments = table.segments[(item.value, sex.value, age_group)]
    scores = [segment[1] for segment in segments]
    non_decreasing = all(b >= a for a, b in zip(scores, scores[1:]))
    non_increasing = all(b <= a for a, b in zip(scores, scores[1:]))
    if not (non_decreasing or non_increasing):
        raise ValueError(
            f"{item.value} 的档位得分沿原始值非单调（区间型映射），同一得分对应多段"
            f"互不相邻的原始值区间，无法按目标分反查唯一原始值；请直接生成身高与体重、"
            f"算出该指标后用 score_item 正查得分"
        )
    # 就低：不超过请求分的最大官方档；请求分低于最低档时夹到最低档
    official = sorted(set(scores))
    target = max((s for s in official if s <= score), default=official[0])
    band = [raw for raw, s in segments if s == target]
    better = [raw for raw, s in segments if s > target]
    if non_increasing and not non_decreasing:
        # 越小越好：区间是 (上一档原始值, 本档原始值]，得分更高者原始值更小
        near, far = max(band), (max(better) if better else None)
    else:
        # 越大越好：区间是 [本档原始值, 下一档原始值)，得分更高者原始值更大
        near, far = min(band), (min(better) if better else None)
    if far is None:
        # 已是最高档，区间在优侧无界：只能返回该档阈值本身
        return float(near)
    return float((near + far) / 2)


def segment_thresholds(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> list[float]:
    """该 (项, 性别, 年级组) 下全部档位的原始值阈值，升序。

    边界测试用它从评分表本身取真实档位，而不是硬编码魔数与 CSV 脱钩。

    表里没有这个组合时抛 ``KeyError``，与 :func:`raw_from_score` 保持一致：
    返回空列表会让调用方的 ``[0]`` / ``[-1]`` 退化成 ``IndexError``，
    把「传错了组合」这个明确原因藏进一个看不出所以然的下标错误里。
    """
    segments = table.segments[(item.value, sex.value, age_group)]
    return [float(raw) for raw, _ in segments]

