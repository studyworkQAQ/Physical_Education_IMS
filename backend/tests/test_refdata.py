"""参考表加载与进程内缓存的约束：CSV 只允许 app/refdata.py 读。"""
import dataclasses, pytest
from app import refdata
from app.domain.tables import StandardTable
from app.domain.indicators import AGE_GROUPS, Sex, ScoredItem

def test_data_dir_points_at_backend_data():
    assert refdata.DATA_DIR.name == "data"
    assert (refdata.DATA_DIR / "national_standard_2014.csv").is_file()

def test_load_standard_returns_frozen_table():
    t = refdata.load_standard()
    assert isinstance(t, StandardTable)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.segments = {}

def test_standard_is_cached_singleton():
    assert refdata.standard() is refdata.standard()

def test_table_covers_every_item_sex_agegroup():
    # 每一项 × 性别 × 龄组都必须有档位，否则 score_item 会静默返回 None，
    # 进而让短板判定漏项——这是会污染整个分层结果的静默失效
    t = refdata.load_standard()
    missing = [(i, s, ag) for i in ScoredItem for s in Sex for ag in AGE_GROUPS
               if refdata.segment_count(t, i, s, ag) < 2]
    assert missing == []

def test_missing_csv_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        refdata.load_standard(tmp_path / "nope.csv")
