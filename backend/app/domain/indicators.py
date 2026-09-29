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


def score_item(
    table: StandardTable,
    item: ScoredItem,
    value: float | None,
    sex: Sex,
    age_group: str,
) -> int | None:
    """正查：原始成绩 → 国标单项得分。

    在档位序列内定位 ``value`` 所在区间后线性插值，并四舍五入到整数分——
    恰好等于档位阈值时不会因为浮点表示误差掉到下一档。

    **越界一律夹到所落那一端的档位分，绝不返回 ``None``**（Ruling 17）。
    ``segments`` 按原始值升序，所以「优于表内最好档」与「差于表内最差档」
    都由同一句夹取自动落到正确端点：哪一端是高分由表自身的单调性决定，
    实现无需判断该项是「越大越好」还是「越小越好」。国标本来就是这么给分的：
    低于最低档的成绩拿最低档的分，而不算「没有成绩」。

    ``None`` 只保留给两种**真缺测**情形：``value`` 缺失，或表里没有这个
    (项, 性别, 年级组) 组合。任何路径都不抛异常、也不返回 0。

    把差到表外的真实成绩判成 ``None`` 是会静默反转研究结论的缺陷：``None`` 在下游
    一律等于「没测」，既拉低 ``valid_count``（有效项不足 4 个直接不分层），又让该项
    不计入短板数 ``W``——体能最差的学生因此被系统性地筛出红色干预层，全程不报错。
    物理上不可能的读数（如 50 米跑 999 秒）由 Task 5 的清洗管道按
    ``indicator_ranges.yaml`` 先行修正，不归本函数兜。
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
    for (raw0, score0), (raw1, score1) in zip(segments, segments[1:]):
        if value <= raw1:
            if raw1 == raw0:
                return score1
            return round(score0 + (value - raw0) / (raw1 - raw0) * (score1 - score0))
    # 上面两次夹取已保证 low_raw <= value <= high_raw，循环必然命中；
    # 这一行只兜「档位序列只有一个元素」的退化表，取该唯一档位的分。
    return high_score


def raw_from_score(
    table: StandardTable, item: ScoredItem, score: int, sex: Sex, age_group: str
) -> float:
    """反查：目标单项得分 → 原始成绩，供仿真数据生成按目标分数造出可信的实测值。

    用的是与 :func:`score_item` 同一张表、同一套档位的反向线性插值，因此
    ``score_item(table, item, raw_from_score(...), ...)`` 在档位精度内能还原目标分。
    目标分高于或低于表内得分范围时，夹到对应端点档位的原始值。

    表里没有这个 (项, 性别, 年级组) 组合时抛 ``KeyError``：那是调用方传错了组合，
    属于程序缺陷，与「学生某项缺测」不是一回事，不该被静默吞掉。
    """
    segments = table.segments[(item.value, sex.value, age_group)]
    scores = [segment[1] for segment in segments]
    top, bottom = max(scores), min(scores)
    if score >= top:
        return float(segments[scores.index(top)][0])
    if score <= bottom:
        return float(segments[scores.index(bottom)][0])
    for (raw0, score0), (raw1, score1) in zip(segments, segments[1:]):
        if min(score0, score1) <= score <= max(score0, score1):
            if score1 == score0:
                return float(raw0)
            return float(raw0 + (score - score0) / (score1 - score0) * (raw1 - raw0))
    # 相邻档位的得分区间在 [bottom, top] 上首尾相接，正常评分表走不到这里；
    # 兜底取得分最接近的档位原始值，保证返回类型始终是 float 而不是 None
    return float(min(segments, key=lambda segment: abs(segment[1] - score))[0])


def segment_thresholds(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> list[float]:
    """该 (项, 性别, 年级组) 下全部档位的原始值阈值，升序。

    边界测试用它从评分表本身取真实档位，而不是硬编码魔数与 CSV 脱钩。
    表里没有这个组合时返回空列表。
    """
    segments = _segments_of(table, item, sex, age_group) or ()
    return [float(raw) for raw, _ in segments]
