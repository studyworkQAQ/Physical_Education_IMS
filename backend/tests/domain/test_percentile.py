"""校内百分位快照的行为约束：分组键、五档口径、样本不足降级国标常模（Review Focus #4）。"""
import numpy as np
from app.domain.percentile import (
    MIN_SAMPLE, PERCENTILES, compute_snapshot, lookup_p25, national_norm,
)
from app.domain.indicators import (
    AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex, score_item, segment_thresholds,
)
from app.refdata import load_standard, standard

T = standard()
LOWER_GRADE, UPPER_GRADE = AGE_GROUPS      # "大一、大二" / "大三、大四"

MINI_HEADER = "item,sex,age_group,score,raw_value\n"


def rows(n, sex="male", age_group=LOWER_GRADE, item=ScoredItem.SPRINT_50M, start=0):
    return [{"student_id": start + i, "sex": sex, "age_group": age_group,
             "item": item, "score": (i * 7) % 100} for i in range(n)]


def _mini_table(tmp_path, bands):
    """一张只有 3 个档的迷你评分表（50 米跑 / 男 / 大一、大二，越小越好）。

    造法照 tests/test_refdata.py：把 CSV 写进 ``tmp_path`` 再用 ``refdata.load_standard``
    读回来——真表每组 20 档，「只有 3 个档」这种边界形状在真表上造不出来（Ruling 87）。
    """
    body = "".join(f"sprint_50m,male,{LOWER_GRADE},{score},{raw}\n"
                   for score, raw in bands)
    path = tmp_path / f"mini_{bands[0][0]}.csv"
    path.write_text(MINI_HEADER + body, encoding="utf-8")
    return load_standard(path)


def test_snapshot_groups_by_sex_age_item():
    snap = compute_snapshot(rows(40) + rows(40, sex="female"), T)
    assert {(r.sex, r.age_group) for r in snap} == {(Sex.MALE, LOWER_GRADE), (Sex.FEMALE, LOWER_GRADE)}
    assert all(r.sample_size == 40 for r in snap)

def test_percentile_values_are_ordered():
    r = compute_snapshot(rows(100), T)[0]
    assert r.p10 <= r.p20 <= r.p25 <= r.p50 <= r.p75

def test_snapshot_falls_back_to_national_when_sample_below_30():
    # Review Focus #4
    snap = compute_snapshot(rows(MIN_SAMPLE - 1), T)
    assert len(snap) == 1
    assert snap[0].source == "national"
    assert snap[0].sample_size == MIN_SAMPLE - 1     # 真实样本量仍须留痕

def test_fallback_row_equals_national_norm_exactly():
    # 降级行必须**逐字段等于** national_norm 的产出（除了 sample_size 留真值），
    # 否则「降级到国标常模」这句话就没有可核对的含义。
    snap = compute_snapshot(rows(MIN_SAMPLE - 1), T)[0]
    ref = national_norm(T, ScoredItem.SPRINT_50M, Sex.MALE, LOWER_GRADE)
    assert (snap.p10, snap.p20, snap.p25, snap.p50, snap.p75) == \
           (ref.p10, ref.p20, ref.p25, ref.p50, ref.p75)
    assert snap.sample_size == MIN_SAMPLE - 1 and ref.sample_size == 0

def test_snapshot_uses_school_when_sample_reaches_30():
    assert compute_snapshot(rows(MIN_SAMPLE), T)[0].source == "school"

def test_lookup_p25_returns_none_when_group_absent():
    assert lookup_p25([], ScoredItem.SPRINT_50M, Sex.MALE, LOWER_GRADE) is None

def test_national_norm_covers_every_weakness_item_sex_and_grade_group():
    for item in WEAKNESS_ITEMS:
        for sex in (Sex.MALE, Sex.FEMALE):
            for age_group in AGE_GROUPS:
                r = national_norm(T, item, sex, age_group)
                assert r.source == "national" and r.item is item and r.sex is sex

def test_national_norm_percentiles_are_monotone_for_every_group():
    # Ruling 84 的方向守卫：国标 2014 里 50 米跑与耐力跑是**越小越好**，
    # 「原始值的第 p 百分位」映射到得分时是**反的**（原始值越低得分越高）。
    # 不做方向感知，这两项会得到 P10=80 > P25=74 > P75=50 这种递减序列，
    # 而 PercentileRow 的语义要求 p10 <= ... <= p75 —— 短板判定线于是彻底失效。
    # 24 组（6 项 × 2 性别 × 2 年级组）逐一断言，不许抽样。
    for item in WEAKNESS_ITEMS:
        for sex in (Sex.MALE, Sex.FEMALE):
            for age_group in AGE_GROUPS:
                vals = [getattr(national_norm(T, item, sex, age_group), f"p{p}")
                        for p in PERCENTILES]
                assert all(a <= b for a, b in zip(vals, vals[1:])), (item, sex, age_group, vals)

def test_national_norm_direction_is_read_from_the_table_not_hardcoded():
    # 越小越好的两项必须真的走了反向映射：把方向判断写反，这两项的 P25 会从
    # 50 / 30 跳到 74 / 72（即原始值低分位对应的高得分），差异极大、一眼可辨。
    lo = segment_thresholds(T, ScoredItem.DISTANCE_RUN, Sex.MALE, LOWER_GRADE)
    assert national_norm(T, ScoredItem.DISTANCE_RUN, Sex.MALE, LOWER_GRADE).p25 == \
        score_item(T, ScoredItem.DISTANCE_RUN, lo[0] + 0.75 * (lo[-1] - lo[0]),
                   Sex.MALE, LOWER_GRADE)

def test_national_norm_needs_no_file_beyond_the_standard_table(tmp_path):
    # Ruling 84 的另一半：常模不是第二份数据文件，而是评分表的纯函数。
    # 用一张只有 3 个档的迷你表也能算出结果，证明它不依赖真表的形状。
    mini = _mini_table(tmp_path, ((100, 6.5), (70, 7.5), (40, 9.0)))
    r = national_norm(mini, ScoredItem.SPRINT_50M, Sex.MALE, LOWER_GRADE)
    vals = [getattr(r, f"p{p}") for p in PERCENTILES]
    # 五档全部落在这 3 个档的得分集合里（真表该组有 20 档，取值集合完全不同）
    assert set(vals) <= {100, 70, 40}
    assert all(a <= b for a, b in zip(vals, vals[1:])), vals
    assert r.source == "national" and r.sample_size == 0
    # 换一套档位分，五档随之整体改变：常模确实只是**注入表**的纯函数，
    # 既没有回落到真表、也没有读第二份文件。33 分在国标里根本不存在。
    other = _mini_table(tmp_path, ((99, 6.5), (66, 7.5), (33, 9.0)))
    vals2 = [getattr(national_norm(other, ScoredItem.SPRINT_50M, Sex.MALE, LOWER_GRADE),
                     f"p{p}") for p in PERCENTILES]
    assert set(vals2) <= {99, 66, 33}
    assert vals2 != vals
    assert 33 in vals2
