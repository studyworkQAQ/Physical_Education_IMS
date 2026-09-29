"""国标评分表的数据结构。

只放结构，不放逻辑，也不碰任何外部资源：评分表由 app/refdata.py 从 CSV 解析后
构造成这里的不可变对象，再作为首参注入 app/domain/indicators.py 的纯函数
（Ruling 15）。这样领域层始终是叶子，同一份表对象在手，结果就可复现、可追溯。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StandardTable:
    """一份完整的国标单项评分表。

    ``segments`` 的键是 ``(item.value, sex.value, age_group)``，值是按原始值升序
    排列的 ``(raw_value, score)`` 档位序列。「越大越好」的项（肺活量、坐位体前屈、
    立定跳远、引体向上/仰卧起坐）沿 raw_value 升序对应 score 升序；「越小越好」的项
    （50 米跑、耐力跑）沿 raw_value 升序对应 score 降序。方向由表本身承载，
    评分实现因此不需要为任何一项硬编码方向。
    """

    segments: dict[tuple[str, str, str], tuple[tuple[float, int], ...]]
