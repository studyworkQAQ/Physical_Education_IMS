"""国标 2014 指标定义与评分正查/反查的行为约束。"""
import pytest

from app.domain.indicators import (
    Sex, ScoredItem, WEAKNESS_ITEMS, ITEM_BUCKET, ITEM_WEIGHTS, AGE_GROUPS,
    CLEANING_FIELDS, COLUMN_BY_ITEM, WHOLE_RECORD,
    age_group_of, bmi_of, score_item, raw_from_score, segment_thresholds,
)
from app.refdata import standard

T = standard()          # 表由 refdata 加载后注入，domain 自身不读盘（Ruling 15）
G = age_group_of(19)

# 全部测试一律从评分表自身推导档位与档位分，不硬编码 CSV 数值——
# 将来一次合法的数据更正不应该弄红测试。唯一例外见
# test_bmi_unrounded_value_scores_correctly 里的说明。
EPS = 1e-6


def test_item_weights_match_spec_4_2_verbatim():
    """Ruling 63：``ITEM_WEIGHTS`` 逐项等于 spec §4.2 权重表的字面值。

    期望值**写死在这里**、不从 ``ITEM_WEIGHTS`` 读回来跟自己比：自证的常量测试等于没有
    测试（上一轮就有一个测试犯了这个毛病）。这七个数字是国标口径，改动必须是有意识的，
    并且要连带改 Task 8 的 ``national_total`` 与 Task 6 生成器的趋势定标。
    """
    assert ITEM_WEIGHTS == {
        ScoredItem.BMI: 15,               # §4.2 第 1 行：BMI 15
        ScoredItem.VITAL_CAPACITY: 15,    # 第 2 行：肺活量 15
        ScoredItem.SPRINT_50M: 20,        # 第 3 行：50 米跑 20
        ScoredItem.SIT_AND_REACH: 10,     # 第 4 行：坐位体前屈 10
        ScoredItem.STANDING_JUMP: 10,     # 第 5 行：立定跳远 10
        ScoredItem.PULL_UP_OR_SIT_UP: 10, # 第 6 行：引体向上/仰卧起坐 10
        ScoredItem.DISTANCE_RUN: 20,      # 第 7 行：1000/800 米跑 20
    }


def test_item_weights_cover_exactly_the_seven_scored_items():
    """键**恰好**是 ``ScoredItem`` 的全部成员：不多（幽灵项）也不少（漏项）。

    漏一项的后果是 ``Σ w_i × score_i`` 的分母不再是 100，国标总分被系统性压低，而
    ``// 100`` 让这件事在数值上看起来仍然「像个分数」——静默错到 Task 9 的分层分布上。
    """
    assert set(ITEM_WEIGHTS) == set(ScoredItem)
    assert len(ITEM_WEIGHTS) == 7
    assert all(isinstance(w, int) and w > 0 for w in ITEM_WEIGHTS.values())


def test_item_weights_sum_to_one_hundred():
    """和为 100，故国标总分 = ``Σ w_i × score_i // 100`` 落在 0–100（spec §4.2 / §6.1）。"""
    assert 15 + 15 + 20 + 10 + 10 + 10 + 20 == 100
    assert sum(ITEM_WEIGHTS.values()) == 100


def test_weakness_item_weights_sum_to_eighty_five():
    """6 个短板判定项的权重和是 85（= 100 − BMI 的 15）。

    这个数被 Task 6 的趋势模型当分母用（均匀分配下每项承担 ``100·Delta_6 / 85``），
    也被 Task 8 的加权总分间接依赖；写死在这里，改权重表时它会当场红。
    """
    assert 15 + 20 + 10 + 10 + 10 + 20 == 85
    assert sum(ITEM_WEIGHTS[item] for item in WEAKNESS_ITEMS) == 85


def test_weakness_items_exclude_bmi():
    assert len(WEAKNESS_ITEMS) == 6
    assert ScoredItem.BMI not in WEAKNESS_ITEMS

def test_scored_items_count_is_seven():
    assert len(list(ScoredItem)) == 7

def test_buckets_cover_all_weakness_items():
    assert {ITEM_BUCKET[i] for i in WEAKNESS_ITEMS} == {
        "endurance", "strength", "speed_flexibility"}
    assert ITEM_BUCKET[ScoredItem.BMI] is None

def test_direction_is_normalized_to_higher_is_better():
    # 50 米跑越快得分越高
    assert score_item(T, ScoredItem.SPRINT_50M, 6.5, Sex.MALE, G) > \
           score_item(T, ScoredItem.SPRINT_50M, 9.0, Sex.MALE, G)

def test_score_at_exact_threshold_returns_that_thresholds_score():
    # Ruling 18：就低取档下，恰好等于某档阈值时必须拿到该档在表里列出的分，
    # 既不掉档也不插值。阈值与期望分都从表里取，不硬编码魔数。
    for item in (ScoredItem.SPRINT_50M, ScoredItem.STANDING_JUMP):
        segments = T.segments[(item.value, Sex.MALE.value, G)]
        for raw, listed in segments:
            assert score_item(T, item, raw, Sex.MALE, G) == listed

def test_score_just_past_threshold_drops_one_band():
    # 就低取档的直接后果：刚越过阈值一档就掉到相邻的低档，这是国标本来的口径，
    # 不再是「浮点误差掉档」的缺陷。方向由表推断，两类项各验一次。
    lower_is_better = ScoredItem.SPRINT_50M          # 沿 raw 升序得分递减
    higher_is_better = ScoredItem.STANDING_JUMP       # 沿 raw 升序得分递增

    seg = T.segments[(lower_is_better.value, Sex.MALE.value, G)]
    (raw, listed), (raw_next, listed_next) = seg[3], seg[4]
    assert raw_next - raw > EPS and listed_next < listed
    assert score_item(T, lower_is_better, raw, Sex.MALE, G) == listed
    assert score_item(T, lower_is_better, raw + EPS, Sex.MALE, G) == listed_next

    seg = T.segments[(higher_is_better.value, Sex.MALE.value, G)]
    (raw_prev, listed_prev), (raw, listed) = seg[9], seg[10]
    assert raw - raw_prev > EPS and listed_prev < listed
    assert score_item(T, higher_is_better, raw, Sex.MALE, G) == listed
    assert score_item(T, higher_is_better, raw - EPS, Sex.MALE, G) == listed_prev

def test_score_item_only_returns_official_discrete_scores():
    # 这条是「插值」缺陷的照妖镜：旧实现在同一批扫描点上产出过 1666 个
    # 国标里根本不存在的分（如立定跳远 210 cm → 61 分、1000 米 280 秒 → 56 分），
    # 使系统单项分无法与学校官方体测报表逐格对账（spec §12 黄金用例、§1.3 可追溯性）。
    for item in ScoredItem:
        for sex in Sex:
            segments = T.segments[(item.value, sex.value, G)]
            official = {listed for _, listed in segments}
            lo, hi = segments[0][0], segments[-1][0]
            probes = [lo + (hi - lo) * k / 200 for k in range(201)]
            probes += [lo - 1.0, hi + 1.0]      # 越界夹取也只能夹到表内的档位分
            for value in probes:
                got = score_item(T, item, value, sex, G)
                assert got in official, (
                    f"{item.value}/{sex.value}/{G} raw={value} 得到非官方分 {got}")

def test_bmi_unrounded_value_scores_correctly():
    # 【本文件唯一允许硬编码 CSV 数值的测试】钉的是国标公布的 BMI 区间端点本身
    # （男：低体重 ≤17.8、正常 17.9~23.9、超重 24.0~27.9、肥胖 ≥28.0），
    # 这些端点就是被测口径，无法从 segment_thresholds 推导出来。
    # Ruling 18 关掉的正是三个 0.1 宽的舍入缝：未取整的 17.85 / 23.94 / 27.95
    # 此前被插值成 90 / 92 / 70 这些国标里不存在的分；就低取档下 23.94 落回
    # 23.9 → 100 分，该生按国标确实是「正常」。
    expected = {15.0: 80, 17.85: 80, 23.94: 100, 24.0: 80, 28.0: 60, 38.0: 60}
    for bmi, want in expected.items():
        assert score_item(T, ScoredItem.BMI, bmi, Sex.MALE, G) == want

def test_sex_specific_items_differ():
    m = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.MALE, G)
    f = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.FEMALE, G)
    assert m != f  # 男引体向上 10 次与女仰卧起坐 10 次得分不同

def test_missing_value_returns_none():
    assert score_item(T, ScoredItem.VITAL_CAPACITY, None, Sex.MALE, G) is None

def test_value_worse_than_worst_segment_clamps_to_floor_not_none():
    # Ruling 17：差于表内最差档必须夹到该档分数，绝不可返回 None。
    # 返回 None 会把「极差成绩」当成「缺测」，既拉低 valid_count，又让该项
    # 不计入短板 W —— 最需要干预的学生反而被筛出红色层，且全程不报错。
    worst = segment_thresholds(T, ScoredItem.DISTANCE_RUN, Sex.MALE, G)[-1]
    at_worst = score_item(T, ScoredItem.DISTANCE_RUN, worst, Sex.MALE, G)
    beyond   = score_item(T, ScoredItem.DISTANCE_RUN, worst + 120.0, Sex.MALE, G)
    assert at_worst is not None
    assert beyond == at_worst

def test_value_better_than_best_segment_clamps_to_ceiling():
    best = segment_thresholds(T, ScoredItem.SPRINT_50M, Sex.MALE, G)[0]
    at_best = score_item(T, ScoredItem.SPRINT_50M, best, Sex.MALE, G)
    beyond  = score_item(T, ScoredItem.SPRINT_50M, max(best - 2.0, 0.1), Sex.MALE, G)
    assert at_best is not None
    assert beyond == at_best

def test_unknown_item_sex_agegroup_key_returns_none():
    # 契约的另一半：None 只留给「真缺测」——value 缺失或表里没有这个组合。
    # 传错 (项, 性别, 年级组) 组合与「成绩差到表外」必须是两回事。
    assert score_item(T, ScoredItem.VITAL_CAPACITY, 4000.0, Sex.MALE, "不存在的年级组") is None

def _monotonic_groups():
    """评分表里「得分沿 raw 升序单调」的 (项, 性别, 年级组) 组，附带方向。

    方向推断与 ``score_item`` 用的 ``_lower_is_better`` 同一口径：只有全程**单调不增**
    才算越小越好（不能用「首档分 < 末档分」那种朴素判据——BMI 首末档是 80/60，会被误判）。
    BMI 两头 80、中间 100，两个方向都不满足，故不在返回列表里，由
    ``test_raw_from_score_rejects_non_monotonic_item`` 单独看守它的 ``ValueError``。
    """
    groups = []
    for item in ScoredItem:
        for sex in Sex:
            for age_group in AGE_GROUPS:
                segments = T.segments[(item.value, sex.value, age_group)]
                scores = [listed for _, listed in segments]
                non_increasing = all(b <= a for a, b in zip(scores, scores[1:]))
                non_decreasing = all(b >= a for a, b in zip(scores, scores[1:]))
                if non_increasing or non_decreasing:
                    groups.append((item, sex, age_group, non_increasing))
    return groups


def _official_scores(item, sex, age_group):
    return sorted({listed for _, listed in T.segments[(item.value, sex.value, age_group)]})


def test_raw_from_score_roundtrips_exactly_across_whole_table():
    # Ruling 22 的核心不变量：反查返回「仍然拿到该分的最差原始值」（方向感知的档位端点），
    # 于是回代 score_item **精确**还原同一个官方档分。全表每一个单调组、每一个官方档都验，
    # 不留单点抽样——旧的中点实现虽然也能通过往返，但会在次数项上造出 13.5 次这种读数。
    checked = 0
    covered = set()
    for item, sex, age_group, _ in _monotonic_groups():
        covered.add((item, sex, age_group))
        for score in _official_scores(item, sex, age_group):
            raw = raw_from_score(T, item, score, sex, age_group)
            got = score_item(T, item, raw, sex, age_group)
            checked += 1
            assert got == score, (
                f"{item.value}/{sex.value}/{age_group} 目标 {score} 分反查得 raw={raw!r}，"
                f"回代却是 {got!r}，往返不精确")
    # 反空转守卫：扫描必须覆盖全部 6 个短板项 × 2 性别 × 2 年级组（只有 BMI 非单调），
    # 且断言数等于全表官方档对数。这些数字都由表与模块常量现场推导，不硬编码 CSV 数值。
    assert covered == {(i, s, a) for i in WEAKNESS_ITEMS for s in Sex for a in AGE_GROUPS}
    expected = sum(len(_official_scores(i, s, a)) for i, s, a in sorted(
        covered, key=lambda k: (k[0].value, k[1].value, k[2])))
    assert checked == expected >= 2 * len(covered)


def test_raw_from_score_returns_integral_value_for_count_items():
    # 次数项（男引体向上／女一分钟仰卧起坐）在 CSV 里的档边界本身就是整数，
    # 端点语义因此天然给出整数次数，Task 6 造仿真数据时**不需要任何取整**。
    # 旧的中点语义会给出 13.5 次这种物理上不可能的读数，而四舍五入到 14 会跨进 76 档。
    item = ScoredItem.PULL_UP_OR_SIT_UP
    for sex in Sex:
        for age_group in AGE_GROUPS:
            for score in _official_scores(item, sex, age_group):
                raw = raw_from_score(T, item, score, sex, age_group)
                assert raw == int(raw), (
                    f"{item.value}/{sex.value}/{age_group} 目标 {score} 分反查得"
                    f"非整数次数 {raw!r}")
                assert raw >= 0, (
                    f"{item.value}/{sex.value}/{age_group} 目标 {score} 分反查得"
                    f"负次数 {raw!r}")


def test_raw_from_score_returns_worst_qualifying_value_not_midpoint():
    # 这条是端点与中点的分水岭：两者都能通过往返断言，只有「往差侧挪一点点必须掉档」
    # 能证明返回的是**最差**合格值而不是带内任意一点。EPS 远小于档距，
    # 并先断言档距确实大于 EPS，避免 EPS 一次跨过两档造成假绿。
    checked = 0
    for item, sex, age_group, lower_is_better in _monotonic_groups():
        segments = T.segments[(item.value, sex.value, age_group)]
        for score in _official_scores(item, sex, age_group):
            raw = raw_from_score(T, item, score, sex, age_group)
            # 差侧：越大越好是更小的 raw，越小越好是更大的 raw
            worse = [r for r, _ in segments if (r > raw if lower_is_better else r < raw)]
            if not worse:
                continue        # 已是表内最差档：越界会被夹回同一档，无从比较
            gap = (min(worse) - raw) if lower_is_better else (raw - max(worse))
            assert gap > EPS, (
                f"{item.value}/{sex.value}/{age_group} 目标 {score} 分的差侧档距 "
                f"{gap} 不大于 EPS={EPS}，本条测试的探针会跨档")
            probe = raw + EPS if lower_is_better else raw - EPS
            got = score_item(T, item, probe, sex, age_group)
            checked += 1
            assert got is not None and got < score, (
                f"{item.value}/{sex.value}/{age_group} 目标 {score} 分反查得 raw={raw!r}，"
                f"但只差 EPS 的 {probe!r} 仍得 {got!r} 分——返回的不是最差合格值")
    assert checked > 0

def test_raw_from_score_maps_unofficial_target_down_to_official_band():
    # 就低：请求分不是官方档时，落到「不超过它的最大官方档」，回代得到的是那个档的分
    # 而不是请求分本身（Task 6 会算出 73 这类连续目标分）。
    # 注：73 在本项落 72 档而非 70 档，因为 72 本身就是官方档；71 才落 70 档。
    segments = T.segments[(ScoredItem.STANDING_JUMP.value, Sex.MALE.value, G)]
    official = sorted({listed for _, listed in segments})
    for requested, want in ((73, 72), (71, 70)):
        assert want in official
        assert want == max(s for s in official if s <= requested)
        raw = raw_from_score(T, ScoredItem.STANDING_JUMP, requested, Sex.MALE, G)
        assert score_item(T, ScoredItem.STANDING_JUMP, raw, Sex.MALE, G) == want

def test_raw_from_score_rejects_non_monotonic_item():
    # Ruling 19：BMI 两头 80、中间 100，非单调，「按目标分反查唯一原始值」不成立。
    # 旧实现对 80 分返回哨兵 0.0（80 恰是 BMI 最常见的目标分：低体重与超重都是 80），
    # Task 6 会因此造出 BMI = 0 kg/m² 的学生，而 score_item(..., 0.0) == 80
    # 使往返测试全绿——缺陷被完美掩盖。正确做法是生成身高体重后正查。
    for sex in Sex:
        with pytest.raises(ValueError):
            raw_from_score(T, ScoredItem.BMI, 80, sex, G)

def test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key():
    # 三个函数对「键不存在」的契约必须一致：反查与取阈值都抛 KeyError。
    # segment_thresholds 返回空列表会让调用方的 [0]/[-1] 退化成看不出所以然的 IndexError。
    with pytest.raises(KeyError):
        raw_from_score(T, ScoredItem.VITAL_CAPACITY, 80, Sex.MALE, "不存在的年级组")
    with pytest.raises(KeyError):
        segment_thresholds(T, ScoredItem.VITAL_CAPACITY, Sex.MALE, "不存在的年级组")

def test_domain_functions_are_pure_and_take_table_explicitly():
    # Ruling 15：同一个表对象传入两次结果必须一致，且 domain 不依赖任何全局加载状态
    a = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    b = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    assert a == b and a is not None


# ---------------------------------------------------------------------------
# Plan 02 Task 1 迁进 domain 的四样东西：bmi_of / COLUMN_BY_ITEM /
# WHOLE_RECORD / CLEANING_FIELDS
# ---------------------------------------------------------------------------

def test_bmi_of_rounds_to_one_decimal():
    """``bmi_of`` 的两个字面期望值（不从被测函数读回来跟自己比，硬规矩 #35）。

    ``65.0 / 1.725² = 21.84399…`` → ``round(…, 1) = 21.8``。
    ``80.0 / 1.60² = 31.25``（二进制下精确可表示）→ ``round(31.25, 1) = 31.2``，
    **不是 31.3**：CPython 的 ``round`` 是银行家舍入（round-half-to-even）。
    第二个值因此不只是「算对了」，它还钉住了「本函数用的是 ``round`` 而不是
    ``math.floor(x*10+0.5)/10`` 这类半进位实现」——两者在 ``.25`` 这个输入上分道。

    ``round(…, 1)`` 是承重的：国标 BMI 档位是区间映射，生成器也算到 1 位小数，
    两侧差 0.05 就可能在档位边界上翻档（进而翻 ``score_bmi``、翻 15% 权重的总分贡献）。
    """
    assert bmi_of(172.5, 65.0) == 21.8
    assert bmi_of(160.0, 80.0) == 31.2


@pytest.mark.parametrize("height,weight", [
    (None, 65.0),      # 身高缺测
    (172.5, None),     # 体重缺测
    (None, None),      # 两项都缺测
])
def test_bmi_of_returns_none_for_missing_input(height, weight):
    """任一为 ``None`` → ``None``，**绝不当 0**（Plan01 Ruling 21）。

    三个参数化用例覆盖 ``if height_cm is None or weight_kg is None`` 的两个操作数：
    第一个走 ``or`` 左侧短路、第二个走右侧、第三个两侧都真。少任何一个，
    ``--cov-branch`` 下这一行的分支就只被覆盖一半（BrPart）。
    """
    assert bmi_of(height, weight) is None


def test_bmi_zero_would_score_eighty_not_none():
    """上一条坚持返回 ``None`` 的代价核算：``score_item(BMI, 0.0)`` = **80**。

    这是「缺测当 0」在 BMI 上的具体后果，四个 (性别 × 年级组) 组全部实测 80——
    BMI 档位的最低哨兵 ``raw_value`` 就是 ``0``（CSV 用它封住「低于某个 BMI」那个
    开口区间），而它对应的官方档是 80。于是一个从未被测过的身高/体重会变成
    「BMI 低到不存在、却仍拿 80 分与 15% 权重」，全程不报错。
    期望值 80 写死在这里，不从评分表读回来（硬规矩 #35）。
    """
    for sex in Sex:
        for group in AGE_GROUPS:
            assert score_item(T, ScoredItem.BMI, 0.0, sex, group) == 80


def test_column_by_item_is_exactly_the_six_weakness_items():
    """``COLUMN_BY_ITEM`` 的键恰为 6 个短板判定项，值为**字面写死**的原始列名。

    这张映射无法从名字推导（``pull_up_or_sit_up`` 对应的是 ``strength_count``），
    抄错的后果是某一项恒为 ``None``、该桶短板静默消失，而 ``score_raw`` 全程不报错。
    **BMI 不在里面**：它是「8 项原始测量 → 7 个国标计分项」里由身高与体重合成的那一项，
    没有自己的原始列（合成算式是 :func:`bmi_of`）。

    值与 ``RawFitnessRecord`` 的字段名对齐由
    ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
    那一侧核对（两侧不同源：这里写字面量，那里从数据类 ``fields()`` 推导）。
    """
    assert set(COLUMN_BY_ITEM) == set(WEAKNESS_ITEMS)
    assert len(COLUMN_BY_ITEM) == 6
    assert ScoredItem.BMI not in COLUMN_BY_ITEM
    assert COLUMN_BY_ITEM == {
        ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
        ScoredItem.SPRINT_50M: "sprint_50m_s",
        ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
        ScoredItem.STANDING_JUMP: "standing_jump_cm",
        ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
        ScoredItem.DISTANCE_RUN: "distance_run_s",
    }


def test_cleaning_fields_is_the_vocabulary_of_cleaning_log_field():
    """``cleaning_log.field`` 的取值域，13 个值**字面写死**（Plan01 Ruling 156 的落点）。

    ⚠️ **计划原文的公式只有 8 个**：它写的是「``COLUMN_BY_ITEM`` 的值 ∪
    ``{"student_no"}`` ∪ ``WHOLE_RECORD``」，漏了 5 个测量列——``height_cm`` 与
    ``weight_kg``（它们**不在** ``COLUMN_BY_ITEM`` 里，因为那一列只覆盖 6 个短板判定项，
    而这两项合成 BMI），以及体成分的 ``muscle_mass_kg`` / ``body_fat_pct`` / ``smi``。
    照那个公式写的话列宽守卫会有 5 个字段名裸奔，而最长的 ``vital_capacity_ml``
    （17 字符）恰好**在**那 8 个里，所以守卫看上去仍然有效——这正是「用样本推断清单」
    的典型失效形态（硬规矩 #27）。

    全量口径来自生产侧的**全部**写入点：``git grep -n "field=" --
    backend/app/pipeline/clean.py backend/app/pipeline/daily.py`` 在基线 ``e26347f``
    上报 9 处，逐处归类见 :data:`app.domain.indicators.CLEANING_FIELDS` 的注释。
    """
    assert WHOLE_RECORD == "*"
    assert CLEANING_FIELDS == frozenset({
        # 6 个短板判定项的原始列
        "vital_capacity_ml", "sprint_50m_s", "sit_and_reach_cm",
        "standing_jump_cm", "strength_count", "distance_run_s",
        # 合成 BMI 的那两项，同样逐字段过清洗（height_cm 还有专属的 unit_normalized）
        "height_cm", "weight_kg",
        # 体成分的三个测量列
        "muscle_mass_kg", "body_fat_pct", "smi",
        # 记录级：学号无法归属（整条剔除）与整条重复（去重）
        "student_no", "*",
    })
    assert len(CLEANING_FIELDS) == 13
    # 最长值 17 字符必须装得进 cleaning_log.field 的 String(32)；那一侧的核对在
    # tests/db/test_models.py 的列宽遍历测试里用 ORM 元数据做（两侧不同源）。
    assert max(len(f) for f in CLEANING_FIELDS) == 17 == len("vital_capacity_ml")
