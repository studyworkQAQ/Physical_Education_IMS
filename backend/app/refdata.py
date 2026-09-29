"""参考数据加载：全项目唯一允许读 ``backend/data/*.csv`` 的模块。

依赖方向是 refdata → domain：这里把 CSV 解析成 app/domain/tables.py 的
StandardTable，再交给 domain 的纯函数使用；进程内缓存也放在这里而不是 domain。
domain 因此保持为无 I/O 的叶子（Ruling 15），不会隐式依赖磁盘上某个 CSV 是否存在。
"""
import csv
import pathlib

from app.domain.indicators import ScoredItem, Sex, segment_thresholds
from app.domain.tables import StandardTable

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
STANDARD_FILENAME = "national_standard_2014.csv"

_standard_cache: StandardTable | None = None


def load_standard(path: pathlib.Path | None = None) -> StandardTable:
    """读取国标评分表 CSV 并构造不可变的 StandardTable。

    CSV 列为 ``item, sex, age_group, score, raw_value``；同一 (项, 性别, 年级组)
    的行按 raw_value 升序聚成档位序列，所以 CSV 里的行序不影响结果。
    ``path`` 缺省为 ``DATA_DIR / STANDARD_FILENAME``，文件不存在抛 FileNotFoundError。
    """
    csv_path = DATA_DIR / STANDARD_FILENAME if path is None else pathlib.Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"国标评分表缺失: {csv_path}")
    grouped: dict[tuple[str, str, str], list[tuple[float, int]]] = {}
    # utf-8-sig：兼容带 BOM 的 CSV，避免 BOM 混进第一列列名
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (row["item"], row["sex"], row["age_group"])
            grouped.setdefault(key, []).append((float(row["raw_value"]), int(row["score"])))
    return StandardTable(segments={key: tuple(sorted(rows)) for key, rows in grouped.items()})


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
