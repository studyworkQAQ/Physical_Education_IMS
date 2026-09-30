"""校内百分位快照的行为约束：分组键、五档口径、样本不足降级国标常模（Review Focus #4）。"""
import pytest

from app.domain.percentile import (
    MIN_SAMPLE, MUSCLE_MASS, PERCENTILES, SnapshotMetric, compute_snapshot,
    lines_used, lookup_p20, lookup_p25, national_norm, summarize_source,
)
from app.domain.derive import find_weaknesses
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


def _item_rows(item, score_of, n=MIN_SAMPLE, sex="male", age_group=LOWER_GRADE):
    """同 :func:`rows`，但得分由 ``score_of(i)`` 给出。

    Ruling 117-C3 的测试需要**两个 item 有不同的得分分布**：``rows()`` 把
    ``(i * 7) % 100`` 写死在助手里，只换 ``item`` 不换分布的话，两组的五档会完全相同，
    「按 item 分组」与「塌成一组」在 p25 上就区分不出来（只能靠行数与 sample_size 区分）。
    """
    return [{"sex": sex, "age_group": age_group, "item": item, "score": score_of(i)}
            for i in range(n)]


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


def test_snapshot_groups_by_sex_and_age_group():
    # 原名 test_snapshot_groups_by_sex_age_item，但本条**从未喂过两个不同的 item**
    # （rows() 的 item 默认恒为 SPRINT_50M），名字声称的第三维根本没测——名字与实测不符
    # 本身就是缺陷（Ruling 117-C3；本项目出过 test_smi_does_not_affect_flag 那种撒谎的名字）。
    # item 那一维由下面 test_snapshot_also_groups_by_item 覆盖，本条只声称它真测的两维。
    snap = compute_snapshot(rows(40) + rows(40, sex="female"), T)
    assert {(r.sex, r.age_group) for r in snap} == {(Sex.MALE, LOWER_GRADE), (Sex.FEMALE, LOWER_GRADE)}
    assert all(r.sample_size == 40 for r in snap)

def test_snapshot_also_groups_by_item():
    # Ruling 117-C3：生产代码的分组键**含 item**（(Sex, age_group, ScoredItem)），但改前
    # 10 条测试没有一条喂过两个不同的 item，复审把键里的 item 去掉 → 369 passed，
    # 2 项 × 30 行塌成 1 行 sprint_50m、sample_size=60、p25=24.5（我用本条的构造复现）。
    # 两项的得分分布刻意不同（一个是 (i*7)%100、一个是它的补），故 p25 必然不等；
    # sample_size 各自 30 而不是 60 是「塌成一组」最直接的露馅点。
    sprint = _item_rows(ScoredItem.SPRINT_50M, lambda i: (i * 7) % 100)
    distance = _item_rows(ScoredItem.DISTANCE_RUN, lambda i: 100 - (i * 7) % 100)
    snap = compute_snapshot(sprint + distance, T)
    assert len(snap) == 2
    by_item = {r.item: r for r in snap}
    assert set(by_item) == {ScoredItem.SPRINT_50M, ScoredItem.DISTANCE_RUN}
    assert all(r.sample_size == MIN_SAMPLE for r in snap)
    assert all(r.source == "school" for r in snap)
    assert all((r.sex, r.age_group) == (Sex.MALE, LOWER_GRADE) for r in snap)
    assert by_item[ScoredItem.SPRINT_50M].p25 != by_item[ScoredItem.DISTANCE_RUN].p25
    # 两个具体值取自生产实现在还原态下的输出（22.25 / 26.25），不是独立推导；
    # 承重的是上面的 != 与 sample_size，这两行只是把「分布确实不同」钉成可复现的数。
    assert by_item[ScoredItem.SPRINT_50M].p25 == 22.25
    assert by_item[ScoredItem.DISTANCE_RUN].p25 == 26.25

def test_compute_snapshot_rejects_an_unknown_age_group():
    # Ruling 118-M3：改前 age_group **完全不校验**，且响不响亮取决于样本量——
    # n=40 静默产出一行 lookup_p25 永远匹配不上的快照（实测 p25=23.25，用合法组名查它得
    # None → 该组全员零短板、valid_count=0），n=5 才在 national_norm 里 KeyError。
    # 两侧现在一律 ValueError，且消息报出**第几行**与**合法清单**（与 derive 的 Ruling 107
    # 同一条口径：那边堵消费者传错，这边堵生产者写错）。
    for n in (MIN_SAMPLE, MIN_SAMPLE - 1):
        with pytest.raises(ValueError) as exc:
            compute_snapshot(rows(n, age_group="18-19"), T)
        message = str(exc.value)
        assert "scores[0]" in message
        assert "18-19" in message
        assert all(group in message for group in AGE_GROUPS)

def test_compute_snapshot_rejects_an_unknown_sex_or_item_with_the_row_index():
    # 改前这两者也会在分组那一行抛 ValueError，但消息只有 "'MALE' is not a valid Sex"
    # ——500 人 × 7 项的批次里不含行号、不含合法取值，等于没给线索。
    bad_sex = rows(MIN_SAMPLE)
    bad_sex[3]["sex"] = "MALE"                        # Sex 的值域是小写
    with pytest.raises(ValueError) as exc:
        compute_snapshot(bad_sex, T)
    assert "scores[3]" in str(exc.value) and "sex" in str(exc.value)
    assert "male" in str(exc.value)                   # 消息给出合法取值清单

    bad_item = rows(MIN_SAMPLE)
    # Ruling 121 之前这里用的是 "muscle_mass_kg"（当时的口号是「库里存得下、算不出来」）。
    # Task 10 落地 0.2 后肌肉量**成了合法指标**（它是 spec §6.3② 那条 P20 判定线的样本），
    # 故换成一个仍然非法的指标名：体脂率走的是固定阈值（男 20% / 女 28%），不进快照。
    bad_item[7]["item"] = "body_fat_pct"
    with pytest.raises(ValueError) as exc:
        compute_snapshot(bad_item, T)
    assert "scores[7]" in str(exc.value) and "item" in str(exc.value)
    assert "body_fat_pct" in str(exc.value)

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


# ---------------------------------------------------------------------------
# Ruling 121（Task 10 Step 0.2）：肌肉量 P20 的生产者
# ---------------------------------------------------------------------------

def _muscle_rows(kg_of, n, sex="male", age_group=LOWER_GRADE):
    """n 行肌肉量样本。``score`` 位放的是**清洗后的 kg 读数**——它没有国标得分可正查。"""
    return [{"sex": sex, "age_group": age_group, "item": MUSCLE_MASS,
             "score": kg_of(i)} for i in range(n)]


def test_muscle_mass_group_yields_a_kg_p20_when_sample_reaches_min():
    """肌肉量组样本达标时产出一行校内行，五档是 **kg 读数**而不是 0–100 的得分。"""
    snap = compute_snapshot(_muscle_rows(lambda i: 30.0 + i * 0.2, MIN_SAMPLE), T)
    assert len(snap) == 1
    row = snap[0]
    assert row.item is SnapshotMetric.MUSCLE_MASS_KG
    assert row.source == "school" and row.sample_size == MIN_SAMPLE
    assert row.p10 < row.p20 < row.p25 < row.p50 < row.p75
    # 30.0 … 35.8 的 30 个等距样本：P20 落在 31 附近，绝不是 0–100 的得分量纲
    assert 30.0 < row.p20 < 32.0
    assert lookup_p20(snap, Sex.MALE, LOWER_GRADE) == row.p20


def test_muscle_mass_group_below_min_sample_produces_no_row():
    """肌肉量**没有国标常模可降级**：样本 < 30 时整组不产出行（Ruling 121 第 4 步）。

    断言的是「不产出行」而不是「产出一行 national」：InBody 的 P20 是设备与人群特异的，
    国标 2014 里没有它的任何阈值，编一个出来就是凭空捏造判定线，而它直接决定谁被标为
    ``muscle_low``。缺行让 ``flag_body_comp`` 收到 ``snapshot_muscle_p20 = None``——与
    ``lookup_p25`` 的 ``None`` 语义同构（Ruling 21：缺测不当最坏值）。
    """
    snap = compute_snapshot(_muscle_rows(lambda i: 30.0 + i * 0.2, MIN_SAMPLE - 1), T)
    assert snap == []
    assert lookup_p20(snap, Sex.MALE, LOWER_GRADE) is None
    # national_norm 自己也拒收：不得给后来人留下「那就编一个常模」这条路。
    # 不查的话它会退化成 segment_thresholds 的 KeyError，消息只有那个三元组，
    # 看不出「肌肉量根本没有常模」这个真因。
    with pytest.raises(ValueError) as exc:
        national_norm(T, MUSCLE_MASS, Sex.MALE, LOWER_GRADE)
    assert "muscle_mass_kg" in str(exc.value)


def test_muscle_and_scored_items_coexist_in_one_snapshot():
    """两类指标可以在同一次调用里入样，且规范序按 ``item.value`` 排。"""
    snap = compute_snapshot(
        rows(MIN_SAMPLE) + _muscle_rows(lambda i: 30.0 + i * 0.2, MIN_SAMPLE), T
    )
    assert [r.item.value for r in snap] == ["muscle_mass_kg", "sprint_50m"]
    assert all(r.source == "school" for r in snap)
    # 计分项那一行的 P25 仍是 0–100 的得分：两类指标的量纲不互相污染
    assert lookup_p25(snap, ScoredItem.SPRINT_50M, Sex.MALE, LOWER_GRADE) > 1.0


# ---------------------------------------------------------------------------
# Ruling 137（Task 10 Step 0.3）：percentile_source 的生产者
# ---------------------------------------------------------------------------

def _six_item_snapshot(n=MIN_SAMPLE):
    """6 个短板判定项各一组的快照；``n < MIN_SAMPLE`` 时六组全部降级为国标常模。"""
    return compute_snapshot(
        [row for item in WEAKNESS_ITEMS
         for row in _item_rows(item, lambda i: (i * 7) % 100, n=n)],
        T,
    )


def test_lines_used_count_equals_valid_count():
    """``lines_used`` 与 ``find_weaknesses`` 的判据必须**同构**。

    这条是 Ruling 137 的唯一防伪保证：``percentile_source`` 要交代「用过哪些判定线」，
    而 ``valid_count`` 是「有几项进了 W 的分母」——两者若各算一套，教师大屏会在
    「判定线来自校内百分位」与「只有 3 个有效项」之间说出自相矛盾的话，且全程不报错。
    """
    snapshot = _six_item_snapshot()
    curr = {item: 60 for item in WEAKNESS_ITEMS}
    curr[ScoredItem.SPRINT_50M] = None      # 缺测：既不算短板、也不进 valid_count
    assert len(lines_used(curr, snapshot, Sex.MALE, LOWER_GRADE)) == \
        find_weaknesses(curr, snapshot, Sex.MALE, LOWER_GRADE).valid_count == \
        len(WEAKNESS_ITEMS) - 1

    # 再抽掉一组的判定线：该行不在快照里 → 同样两边一起少一项
    partial = [r for r in snapshot if r.item != ScoredItem.DISTANCE_RUN]
    assert len(lines_used(curr, partial, Sex.MALE, LOWER_GRADE)) == \
        find_weaknesses(curr, partial, Sex.MALE, LOWER_GRADE).valid_count == \
        len(WEAKNESS_ITEMS) - 2


def test_summarize_source_covers_the_three_rulings():
    """Ruling 137 的三条口径：无来源 → ``none``、全校内 → ``school``、任一降级 → ``national``。"""
    school = _six_item_snapshot()                     # n = 30 → source = "school"
    national = _six_item_snapshot(MIN_SAMPLE - 1)     # n = 29 → 整组降级 "national"
    assert {r.source for r in school} == {"school"}
    assert {r.source for r in national} == {"national"}

    # ① valid_count = 0：一行都没用过
    assert summarize_source([]) == "none"
    # ② valid_count ∈ {1,2,3}：按实际用过的那 1–3 行汇总
    assert summarize_source(school[:3]) == "school"
    assert summarize_source(national[:1]) == "national"
    # ③ 6 项混用：任一项降级即 national（保守侧）
    assert summarize_source(school[:5] + national[:1]) == "national"
    assert summarize_source(school) == "school"
    assert summarize_source(national) == "national"
