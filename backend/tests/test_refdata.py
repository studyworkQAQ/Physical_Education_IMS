"""参考表加载与进程内缓存的约束：CSV 只允许 app/refdata.py 读。"""
import collections
import csv
import dataclasses

import pytest

from app import refdata
from app.domain.tables import StandardTable
from app.domain.indicators import AGE_GROUPS, Sex, ScoredItem

CSV_HEADER = "item,sex,age_group,score,raw_value\n"
# 两行合法数据 + 第三行待参数化注入的非法值，非法行落在 CSV 第 4 行
GOOD_ROWS = ("bmi,male,大一、大二,80,0\n"
             "bmi,male,大一、大二,100,20\n")


def _csv_group_counts(path):
    """独立于 load_standard 再数一遍 CSV，用于交叉核对每组的档位数。"""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows), collections.Counter(
        (r["item"], r["sex"], r["age_group"]) for r in rows)


def test_data_dir_points_at_backend_data():
    assert refdata.DATA_DIR.name == "data"
    assert (refdata.DATA_DIR / "national_standard_2014.csv").is_file()

def test_load_standard_returns_frozen_table():
    t = refdata.load_standard()
    assert isinstance(t, StandardTable)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.segments = {}

def test_segments_mapping_is_read_only():
    # frozen=True 只是浅冻结：挡得住「换掉整个字段」，挡不住 segments[key] = ... 就地改写。
    # 而 standard() 是进程内共享单例，一次误写会让之后所有查表静默变质，
    # spec §1.3 的逐人可追溯性也就没了，所以映射本身必须是只读视图。
    t = refdata.load_standard()
    key = next(iter(t.segments))
    with pytest.raises(TypeError):
        t.segments[key] = ((0.0, 0),)
    with pytest.raises(TypeError):
        del t.segments[key]

def test_standard_is_cached_singleton():
    assert refdata.standard() is refdata.standard()

def test_table_covers_every_item_sex_agegroup():
    # 键集必须**恰好等于** 项 × 性别 × 年级组 的全笛卡尔积：0 缺失、0 孤儿。
    # 只断言「每组 >= 2 档」是抓不住的——CSV 里一个拼错的 item 会把某一行从正确的组
    # 悄悄摘走、另立一个孤儿键，该组从 20 档变 19 档，缺掉的那一档会让整个区间的
    # 查表结果偏移，而任何地方都不报错，短板判定还会静默漏项。
    t = refdata.load_standard()
    expected_keys = {(i.value, s.value, ag)
                     for i in ScoredItem for s in Sex for ag in AGE_GROUPS}
    assert set(t.segments) == expected_keys
    # 每组档位数必须等于 CSV 里该组的行数（再独立数一遍，不复用 load_standard 的解析）
    total, per_group = _csv_group_counts(refdata.DATA_DIR / refdata.STANDARD_FILENAME)
    assert total == sum(per_group.values()) == sum(len(v) for v in t.segments.values())
    mismatched = {k: (len(t.segments[k]), per_group[k])
                  for k in expected_keys if len(t.segments[k]) != per_group[k]}
    assert mismatched == {}

@pytest.mark.parametrize("column,bad_value", [
    ("item", "vital_capacty"),          # 拼错：少一个 i
    ("sex", "Male"),                     # 大小写不符枚举值
    ("age_group", "大一-大二"),           # 分隔符不符官方年级组名
])
def test_malformed_csv_raises_with_line_number(tmp_path, column, bad_value):
    # 三个分组列必须逐行按枚举校验，且报错要能直接定位到 CSV 行号与非法值本身，
    # 否则录错一个字的人得靠肉眼在 502 行里找。
    values = {"item": "bmi", "sex": "male", "age_group": "大一、大二",
              "score": "60", "raw_value": "28"}
    values[column] = bad_value
    bad = tmp_path / "bad.csv"
    bad.write_text(
        CSV_HEADER + GOOD_ROWS + ",".join(values.values()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(bad)
    message = str(excinfo.value)
    assert "第 4 行" in message        # 表头 1 行 + 合法 2 行，非法行是第 4 行
    assert bad_value in message
    assert f"{column} 值非法" in message

def test_missing_csv_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        refdata.load_standard(tmp_path / "nope.csv")
