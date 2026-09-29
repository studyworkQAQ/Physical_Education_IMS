"""参考数据加载：全项目唯一允许读 ``backend/data/*.csv`` 的模块。

依赖方向是 refdata → domain：这里把 CSV 解析成 app/domain/tables.py 的
StandardTable，再交给 domain 的纯函数使用；进程内缓存也放在这里而不是 domain。
domain 因此保持为无 I/O 的叶子（Ruling 15），不会隐式依赖磁盘上某个 CSV 是否存在。
"""
import csv
import pathlib
import types

from app.domain.indicators import AGE_GROUPS, ScoredItem, Sex, segment_thresholds
from app.domain.tables import StandardTable

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
STANDARD_FILENAME = "national_standard_2014.csv"

_standard_cache: StandardTable | None = None


def load_standard(path: pathlib.Path | None = None) -> StandardTable:
    """读取国标评分表 CSV 并构造不可变的 StandardTable。

    CSV 列为 ``item, sex, age_group, score, raw_value``；同一 (项, 性别, 年级组)
    的行按 raw_value 升序聚成档位序列，所以 CSV 里的行序不影响结果。
    ``path`` 缺省为 ``DATA_DIR / STANDARD_FILENAME``，文件不存在抛 FileNotFoundError。

    三个分组列逐行按枚举校验，不合法即抛 ``ValueError`` 并带上 **CSV 行号与 offending 值**。
    不校验的后果是静默的：一个拼错的 ``item``（如 ``vital_capacty``）会把那一行的档
    从正确的组里悄悄摘走、另立一个孤儿键——该组从 20 档变 19 档，缺掉的那一档会让
    整个区间的查表结果偏移，而任何地方都不报错。

    ``segments`` 装入 ``MappingProxyType``：``frozen=True`` 只挡住换掉整个字段，挡不住
    ``segments[key] = ...`` 的就地改写，而 ``standard()`` 是进程内共享单例，一次误写
    会让之后所有查表静默变质，spec §1.3 的可追溯性也就没了。底层 dict 是本函数的
    局部变量、不外泄，故这个只读视图是有效的。
    """
    csv_path = DATA_DIR / STANDARD_FILENAME if path is None else pathlib.Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"国标评分表缺失: {csv_path}")
    grouped: dict[tuple[str, str, str], list[tuple[float, int]]] = {}
    # utf-8-sig：兼容带 BOM 的 CSV，避免 BOM 混进第一列列名
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            # line_num 是已从源文件读过的行数，比 enumerate 更准（能处理跨行引号字段）
            line_no = reader.line_num
            try:
                item = ScoredItem(row["item"])
            except ValueError:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 item 值非法: {row['item']!r}；"
                    f"合法值: {[i.value for i in ScoredItem]}"
                ) from None
            try:
                sex = Sex(row["sex"])
            except ValueError:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 sex 值非法: {row['sex']!r}；"
                    f"合法值: {[s.value for s in Sex]}"
                ) from None
            age_group = row["age_group"]
            if age_group not in AGE_GROUPS:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 age_group 值非法: {age_group!r}；"
                    f"合法值: {list(AGE_GROUPS)}"
                )
            key = (item.value, sex.value, age_group)
            grouped.setdefault(key, []).append((float(row["raw_value"]), int(row["score"])))
    return StandardTable(
        segments=types.MappingProxyType(
            {key: tuple(sorted(rows)) for key, rows in grouped.items()}
        )
    )



def standard() -> StandardTable:
    """进程内单例：评分表是只读参考数据，一个进程加载一次即可。"""
    global _standard_cache
    if _standard_cache is None:
        _standard_cache = load_standard()
    return _standard_cache


def segment_count(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> int:
    """该 (项, 性别, 年级组) 的档位数，供评分表完整性校验。"""
    return len(segment_thresholds(table, item, sex, age_group))
