"""清洗管道的行为契约：缺测绝不填 0、越界夹取到边界、量纲启发式、重复行去除，全程留痕。

本文件的十条测试逐字来自实施计划 Task 5 Step 1，另加两条钉住计划没定义的东西：
``CleanResult.dropped`` / ``corrected`` 的确切口径，以及 ``load_ranges`` 对 ranges 文件
里字段名写错/漏写的响亮失败。
"""
import pathlib

import pytest

from app.adapters.base import RawFitnessRecord, RawBodyCompRecord
from app.pipeline.clean import clean_fitness, clean_body_comp, normalize_height, load_ranges

RANGES = load_ranges(pathlib.Path(__file__).parents[2] / "data" / "indicator_ranges.yaml")


def rec(**kw):
    # 字段序与 Ruling 33 后的 RawFitnessRecord 一致：tested_on 是必填的第 3 个位置参数，
    # batch_key 必须是 "<academic_year>|<timepoint>" 格式（parse_batch_key 独占解析）
    base = dict(student_no="S1", batch_key="2025-2026|week1", tested_on="2025-09-04",
        height_cm=175.0, weight_kg=65.0,
        vital_capacity_ml=4200.0, sprint_50m_s=7.2, sit_and_reach_cm=12.0,
        standing_jump_cm=230.0, strength_count=10.0, distance_run_s=240.0)
    return RawFitnessRecord(**{**base, **kw})


def test_unit_error_height_in_meters_normalized():
    # Review Focus #3
    v, entry = normalize_height(1.75)
    assert v == 175.0
    assert entry.kind == "unit_normalized"


def test_outlier_corrected_and_logged():
    r = clean_fitness([rec(sprint_50m_s=3.2)], RANGES)
    assert r.corrected == 1
    assert r.entries[0].kind == "outlier_corrected"
    assert r.entries[0].field == "sprint_50m_s"


def test_body_fat_out_of_range_logged():
    r = clean_body_comp([RawBodyCompRecord("S1", "2025-09-01", 55.0, 62.0, 8.0)], RANGES)
    assert any(e.field == "body_fat_pct" and e.kind == "outlier_corrected" for e in r.entries)


def test_duplicate_record_removed_keeping_newer():
    r = clean_fitness([rec(), rec()], RANGES)
    assert len(r.fitness) == 1
    assert any(e.kind == "duplicate_removed" for e in r.entries)


def test_missing_field_produces_missing_dropped_entry_not_zero():
    # Review Focus #2：缺失字段绝不可被填 0
    r = clean_fitness([rec(vital_capacity_ml=None)], RANGES)
    assert r.fitness[0].vital_capacity_ml is None
    assert any(e.kind == "missing_dropped" and e.field == "vital_capacity_ml" for e in r.entries)


def test_zero_filled_time_field_becomes_missing_not_outlier_corrected():
    # Ruling 21：0 是最常见的缺测占位。若按「修正为区间下界」处理，
    # sprint_50m_s=0.0 会变成 5.0 秒，再经 score_item 低侧夹取得到 100 分——
    # 一个缺测项反而给体能最差的学生送上 20% 权重的满分。必须转 None。
    r = clean_fitness([rec(sprint_50m_s=0.0, distance_run_s=0.0)], RANGES)
    assert r.fitness[0].sprint_50m_s is None
    assert r.fitness[0].distance_run_s is None
    assert all(e.kind == "missing_dropped" for e in r.entries
               if e.field in ("sprint_50m_s", "distance_run_s"))


def test_zero_strength_count_is_a_real_value_not_missing():
    # 引体向上做不起一个 = 0 次，合法真实值，绝不可当缺测
    r = clean_fitness([rec(strength_count=0.0)], RANGES)
    assert r.fitness[0].strength_count == 0.0
    assert not any(e.field == "strength_count" for e in r.entries)


def test_negative_strength_count_is_missing():
    r = clean_fitness([rec(strength_count=-1.0)], RANGES)
    assert r.fitness[0].strength_count is None


def test_negative_sit_and_reach_is_a_real_value():
    # 国标坐位体前屈本就有 −1.3 等负值档
    r = clean_fitness([rec(sit_and_reach_cm=-1.3)], RANGES)
    assert r.fitness[0].sit_and_reach_cm == -1.3
    assert r.entries == []


def test_clean_record_passes_through_untouched():
    r = clean_fitness([rec()], RANGES)
    assert r.entries == [] and r.dropped == 0 and r.corrected == 0


# ---------------------------------------------------------------------------
# 以下两条不在 Step 1 的十条之内：计划声明了 CleanResult.dropped / corrected 却没给
# 定义，也没要求 ranges 文件写错时响亮失败——两者都由控制方在本任务的补充要求中裁定。
# ---------------------------------------------------------------------------


def test_dropped_and_corrected_counters_exclude_duplicate_removed():
    # 钉住三条口径：dropped 只数 missing_dropped；corrected 数 outlier_corrected 与
    # unit_normalized 之和；duplicate_removed 两个计数都不进——被去掉的是重复行，
    # 活下来的那一行本身完好无损，既没丢值也没改值。Task 10 要把这两个数写进
    # daily_sync_run.dropped_count / corrected_count，口径含糊就等于报表口径含糊。
    r = clean_fitness(
        [rec(), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)], RANGES
    )
    assert len(r.fitness) == 1
    assert sorted(e.kind for e in r.entries) == [
        "duplicate_removed", "missing_dropped", "outlier_corrected", "unit_normalized"
    ]
    assert r.dropped == 1
    assert r.corrected == 2


def test_load_ranges_rejects_unknown_or_omitted_field(tmp_path):
    # ranges 文件是专家手工维护的知识资产：字段名拼错（vital_capacty_ml）或漏写一个
    # 字段，会让那个字段的保护静默失效——正是本任务要防的失效模式，故必须早炸。
    unknown = tmp_path / "unknown_field.yaml"
    unknown.write_text(
        "height_cm: {min: 140, max: 220, non_positive_is_missing: true, zero_allowed: false}\n"
        "vital_capacty_ml: {min: 800, max: 9000, non_positive_is_missing: true, zero_allowed: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="vital_capacty_ml"):
        load_ranges(unknown)

    omitted = tmp_path / "omitted_field.yaml"
    omitted.write_text(
        "height_cm: {min: 140, max: 220, non_positive_is_missing: true, zero_allowed: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sprint_50m_s"):
        load_ranges(omitted)
