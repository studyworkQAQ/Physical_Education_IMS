"""``trend_label`` 的 oracle 测试（Ruling 69①，spec §6.3 / §10.5）。

**这个文件存在的理由**：上一轮生成器把趋势符号接反了——被标为「持续下滑」的 100 人本学年
总分实际比上学年**高**、被标为「稳步提升」的 125 人实际**低**，两类标签整体互换，而它活过了
两轮共 236 条测试，因为 ``trend_label`` 在全部测试里只被数过一次个数（评审 M5）。数个数
证明不了方向；能证明方向的只有一条**独立于生成器**的判据实现，逐人对账。

因此本文件的 :func:`_oracle` 是从 spec §6.3 的判定表**正文**逐字翻译的，不看
``app.seed.fitness`` 的实现。若有人「照着生成器抄一遍」，它就退化成自证循环、一条缺陷也
抓不住——这正是评审要求「双向守卫」的原因（另一向是 Task 8 的生产侧对账，Ruling 69②）。

**口径**（spec §6.3「口径先钉死」）：``Delta`` 是**国标加权总分**（0–100，七项按
:data:`app.domain.indicators.ITEM_WEIGHTS` 加权）的变化量，不是 6 项之和（0–600）的变化量；
「项」是 6 个短板判定项（BMI 不入计数，只通过 ``Delta`` 影响判定）。
"""
import statistics
from collections import Counter

import pytest

from app.domain.indicators import ITEM_WEIGHTS, WEAKNESS_ITEMS, ScoredItem
from app.seed.config import SeedConfig, allocate_quota
from app.seed.fitness import _weighted_total
from app.seed.generate import build_dataset

BMI = ScoredItem.BMI
ALL_SEVEN = tuple(ScoredItem)
SIX = tuple(WEAKNESS_ITEMS)

# 判定表里出现的四个字面阈值。**写死在这里**、不从生成器或 Task 8 的常量导入：
# oracle 的全部价值就在于它与被测实现没有共享任何一处代码或常量。
VOLATILE_MIN_SPLIT = 3        # min(#{delta>0}, #{delta<0}) >= 3
VOLATILE_ITEM_SWING = 10      # 且 max|delta_i| >= 10
TOTAL_DROP = 5                # Delta <= -5
SINGLE_ITEM_DROP = 5          # delta_i <= -5
DECLINING_ITEMS = 3           # 这样的项 >= 3
TOTAL_RISE = 5                # Delta >= +5
# 稳步提升的第二半个判据「无单项下降 ≥5 分」用的也是 5，与 TOTAL_DROP / SINGLE_ITEM_DROP
# 同一个数（§6.3 勘误 Ruling 64b：三处 5 分口径统一）。单独起个名字是为了让 _oracle 的
# 四行与规格表的四行**一一对应**，读代码的人不必去猜哪个 5 是哪个 5。
IMPROVE_FLOOR = 5


def _oracle(deltas: dict[ScoredItem, int], total_change: float) -> str:
    """spec §6.3「③ 历史趋势」判定表的独立实现：自上而下匹配、**命中即停**。

    | 顺序 | 标签     | 判定 |
    |---|---|---|
    | 1 | ``波动大``   | ``min(#{delta_i > 0}, #{delta_i < 0}) >= 3`` **且** ``max_i abs(delta_i) >= 10`` |
    | 2 | ``持续下滑`` | ``Delta <= -5`` **或** ``#{i: delta_i <= -5} >= 3`` |
    | 3 | ``稳步提升`` | ``Delta >= +5`` **且** ``min_i delta_i > -5`` |
    | 4 | ``稳定``     | 以上皆不满足 |

    规格正文的三条附带口径一并翻译进来：

    * **行序是「波动大」优先**（§6.3 勘误 Ruling 64a）。6 个项上
      ``min(#{正}, #{负}) >= 3`` 等价于恰好 3 正 3 负，而这必然满足「≥3 项下降 ≥5 分」的
      持续下滑第二分支；若把持续下滑印在第一行，波动大这一行**可证明不可达**。
    * **``delta_i = 0`` 既不计入正也不计入负**（§6.3 末段、§14 #23）。副作用是一次
      「六项里有一项恰好持平」的测量会让波动大退化为不可达——规格明写这是刻意的保守
      （宁漏判不误判），故 :func:`test_one_zero_delta_makes_volatile_unreachable` 钉住它。
    * **``delta_i = 本学年 − 上学年``，正 = 进步**（§6.3 勘误 Ruling 62）。
    """
    ups = sum(1 for delta in deltas.values() if delta > 0)
    downs = sum(1 for delta in deltas.values() if delta < 0)
    if (
        min(ups, downs) >= VOLATILE_MIN_SPLIT
        and max(abs(delta) for delta in deltas.values()) >= VOLATILE_ITEM_SWING
    ):
        return "波动大"
    if total_change <= -TOTAL_DROP or sum(
        1 for delta in deltas.values() if delta <= -SINGLE_ITEM_DROP
    ) >= DECLINING_ITEMS:
        return "持续下滑"
    if total_change >= TOTAL_RISE and min(deltas.values()) > -IMPROVE_FLOOR:
        return "稳步提升"
    return "稳定"


def _scores(six: dict[ScoredItem, int], bmi: int = 75) -> dict[ScoredItem, int]:
    """七项得分（六个短板项 + 一个 BMI）。BMI 缺省 75，多数黄金用例让它保持不变。"""
    return {**six, BMI: bmi}


def _deltas(previous: dict[ScoredItem, int], current: dict[ScoredItem, int]):
    """``(六个 delta_i, Delta)``——``Delta`` 一律经 :func:`_weighted_total` 从**得分**算。

    不在测试里手写总分字面量：手写一个 450 这类数会把「6 项之和（0–600）」与「国标总分
    （0–100）」两个口径混在一起，而 ±5 的阈值只在后者上有意义（Ruling 63）。
    """
    deltas = {item: current[item] - previous[item] for item in SIX}
    return deltas, _weighted_total(current) - _weighted_total(previous)


def _flat(value: int) -> dict[ScoredItem, int]:
    return {item: value for item in SIX}


# ---------------------------------------------------------------------------
# _weighted_total 本身必须先被钉住（否则上面所有期望值都建立在它之上）
# ---------------------------------------------------------------------------


def test_weighted_total_is_the_floored_weighted_sum_of_seven_items():
    """期望值全部**手算**写在注释里，不从被测函数读回来。

    权重取自 spec §4.2：BMI 15、肺活量 15、50 米 20、坐位体前屈 10、立定跳远 10、
    引体/仰卧起坐 10、耐力跑 20（和 100）。``ITEM_WEIGHTS`` 的字面值由
    ``tests/domain/test_indicators.py::test_item_weights_match_spec_4_2_verbatim`` 钉住，
    故这里可以直接引用它而不构成自证。
    """
    # 七项全 75 → Σ w·s = 75 × 100 = 7500 → 7500 // 100 = 75
    assert _weighted_total({item: 75 for item in ALL_SEVEN}) == 75
    # 七项全 100 → 10000 // 100 = 100；七项全 0 → 0
    assert _weighted_total({item: 100 for item in ALL_SEVEN}) == 100
    assert _weighted_total({item: 0 for item in ALL_SEVEN}) == 0
    # BMI 100、六项全 60 → 15×100 + 85×60 = 1500 + 5100 = 6600 → 66
    assert _weighted_total(_scores(_flat(60), bmi=100)) == 66
    # BMI 80、肺活量 70、50 米 90、坐位体前屈 60、立定跳远 55、引体 10、耐力跑 75：
    #   15×80 + 15×70 + 20×90 + 10×60 + 10×55 + 10×10 + 20×75
    # = 1200 + 1050 + 1800 +  600 +  550 +  100 + 1500 = 6800 → 68
    mixed = _scores(
        {
            ScoredItem.VITAL_CAPACITY: 70,
            ScoredItem.SPRINT_50M: 90,
            ScoredItem.SIT_AND_REACH: 60,
            ScoredItem.STANDING_JUMP: 55,
            ScoredItem.PULL_UP_OR_SIT_UP: 10,
            ScoredItem.DISTANCE_RUN: 75,
        },
        bmi=80,
    )
    assert _weighted_total(mixed) == 68
    # 向下取整（``//`` 而不是 ``/``）：BMI 77、六项全 76 → 15×77 + 85×76 = 1155 + 6460
    #   = 7615 → 76（不是 76.15、也不是四舍五入的 76 之外的任何东西）
    assert _weighted_total(_scores(_flat(76), bmi=77)) == 76
    # 六项的权重和是 85，BMI 是 15：单独钉一次，趋势模型的 100·Delta_6/85 就靠它
    assert sum(ITEM_WEIGHTS[item] for item in SIX) == 85
    assert ITEM_WEIGHTS[BMI] == 15


# ---------------------------------------------------------------------------
# 手算黄金用例：逐条覆盖判定表的每一行与每一个分支
# ---------------------------------------------------------------------------


def test_volatile_outranks_declining():
    """**行序守卫**（Ruling 64a）：3 项各降 12 + 3 项各升 10 → 必须判波动大。

    算式：Σ w·d = 20×(−12) + 20×(−12) + 10×(−12) + 15×(+10) + 10×(+10) + 10×(+10)
                = −240 − 240 − 120 + 150 + 100 + 100 = **−250**
    七项全 75 时 Σ w·s = 7500 → 上学年总分 7500 // 100 = 75；
    本学年 7250 // 100 = 72 → ``Delta`` = 72 − 75 = **−3**。
    ``Delta`` = −3 > −5，故第一分支不触发；但下降 ≥5 的项恰有 3 个（−12 ×3），
    **第二分支触发** → 若行序写反成「持续下滑 → 波动大」，本条会返回持续下滑。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.SPRINT_50M: 63,          # −12（w 20）
            ScoredItem.DISTANCE_RUN: 63,        # −12（w 20）
            ScoredItem.PULL_UP_OR_SIT_UP: 63,   # −12（w 10）
            ScoredItem.VITAL_CAPACITY: 85,      # +10（w 15）
            ScoredItem.SIT_AND_REACH: 85,       # +10（w 10）
            ScoredItem.STANDING_JUMP: 85,       # +10（w 10）
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == -3
    assert sorted(deltas.values()) == [-12, -12, -12, 10, 10, 10]
    assert _oracle(deltas, total_change) == "波动大"


def test_volatile_by_three_up_three_down_with_big_swing():
    """波动大的正面用例：恰好 3 正 3 负、``max|delta|`` = 13 ≥ 10。

    算式：Σ w·d = 15×13 + 10×12 + 10×11 + 20×(−13) + 10×(−12) + 20×(−11)
                = 195 + 120 + 110 − 260 − 120 − 220 = **−175**
    上学年 7500 // 100 = 75，本学年 7325 // 100 = 73 → ``Delta`` = **−2**。
    下降 ≥5 的项有 3 个，故持续下滑的第二分支也满足——**行序救了它**。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.VITAL_CAPACITY: 88,      # +13
            ScoredItem.SIT_AND_REACH: 87,       # +12
            ScoredItem.STANDING_JUMP: 86,       # +11
            ScoredItem.SPRINT_50M: 62,          # −13
            ScoredItem.PULL_UP_OR_SIT_UP: 63,   # −12
            ScoredItem.DISTANCE_RUN: 64,        # −11
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == -2
    assert _oracle(deltas, total_change) == "波动大"


def test_declining_by_total_drop_only():
    """**只由总分分支**触发的持续下滑：下降 ≥5 的项只有 2 个。

    算式：Σ w·d = 15×(−4) + 20×(−10) + 10×(−4) + 10×(−4) + 10×(−4) + 20×(−6)
                = −60 − 200 − 40 − 40 − 40 − 120 = **−500**
    上学年 7500 // 100 = 75，本学年 7000 // 100 = 70 → ``Delta`` = **−5** ≤ −5 ✓
    ``#{delta ≤ −5}`` = 2（−10 与 −6）< 3，故第二分支不触发；六项全负 → 非波动大。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.VITAL_CAPACITY: 71,      # −4
            ScoredItem.SPRINT_50M: 65,          # −10
            ScoredItem.SIT_AND_REACH: 71,       # −4
            ScoredItem.STANDING_JUMP: 71,       # −4
            ScoredItem.PULL_UP_OR_SIT_UP: 71,   # −4
            ScoredItem.DISTANCE_RUN: 69,        # −6
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == -5
    assert sum(1 for d in deltas.values() if d <= -SINGLE_ITEM_DROP) == 2
    assert _oracle(deltas, total_change) == "持续下滑"


def test_declining_by_three_items_dropping_five_only():
    """**只由「≥3 项下降 ≥5」分支**触发的持续下滑：``Delta`` 恰好没到 −5。

    算式：Σ w·d = 10×(−5) + 10×(−5) + 10×(−5) + 15×(+1) + 20×(+1) + 20×(+1)
                = −150 + 55 = **−95**
    上学年 7500 // 100 = 75，本学年 7405 // 100 = 74 → ``Delta`` = **−1** > −5，
    故第一分支不触发；下降 ≥5 的项 = 3 ✓ → 第二分支触发。
    注意本例恰好 3 正 3 负，但 ``max|delta|`` = 5 < 10，故波动大不成立——
    这一条同时钉住「波动大需要**两个**条件同时满足」。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.SIT_AND_REACH: 70,       # −5
            ScoredItem.STANDING_JUMP: 70,       # −5
            ScoredItem.PULL_UP_OR_SIT_UP: 70,   # −5
            ScoredItem.VITAL_CAPACITY: 76,      # +1
            ScoredItem.SPRINT_50M: 76,          # +1
            ScoredItem.DISTANCE_RUN: 76,        # +1
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == -1
    assert min(
        sum(1 for d in deltas.values() if d > 0),
        sum(1 for d in deltas.values() if d < 0),
    ) == 3
    assert max(abs(d) for d in deltas.values()) == 5
    assert _oracle(deltas, total_change) == "持续下滑"


def test_declining_by_item_branch_even_when_the_total_rises():
    """``Delta`` = 0 也能判持续下滑：第二分支与总分**无关**（Ruling 64b 的语义）。

    算式：Σ w·d = 10×(−9)×3 + 15×(+5) + 20×(+5) + 20×(+5) = −270 + 275 = **+5**
    上学年 7500 // 100 = 75，本学年 7505 // 100 = 75 → ``Delta`` = **0**。
    ``max|delta|`` = 9 < 10 → 非波动大（尽管仍是 3 正 3 负）；下降 ≥5 的项 = 3 ✓。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.SIT_AND_REACH: 66,       # −9
            ScoredItem.STANDING_JUMP: 66,       # −9
            ScoredItem.PULL_UP_OR_SIT_UP: 66,   # −9
            ScoredItem.VITAL_CAPACITY: 80,      # +5
            ScoredItem.SPRINT_50M: 80,          # +5
            ScoredItem.DISTANCE_RUN: 80,        # +5
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == 0
    assert _oracle(deltas, total_change) == "持续下滑"


def test_improving_needs_both_total_rise_and_no_single_item_drop():
    """稳步提升：``Delta`` ≥ +5 **且** ``min delta_i`` > −5，两个条件缺一不可。

    算式：Σ w·d = 15×(+7) + 20×(+7) + 10×(+7) + 10×(+7) + 10×(+7) + 20×(+7) = 85×7 = **595**
    上学年 7500 // 100 = 75，本学年 8095 // 100 = 80 → ``Delta`` = **+5** ≥ +5 ✓
    ``min delta_i`` = +7 > −5 ✓；六项全正 → 非波动大。
    """
    previous = _scores(_flat(75))
    current = _scores(_flat(82))
    deltas, total_change = _deltas(previous, current)
    assert total_change == 5
    assert _oracle(deltas, total_change) == "稳步提升"


def test_single_item_drop_of_six_blocks_improving():
    """一项降 6 分就把稳步提升挡掉，落到稳定——钉住 ``min_i delta_i > −5`` 这半句。

    算式：Σ w·d = 10×(−6) + 15×(+10) + 20×(+10) + 10×(+10) + 10×(+10) + 20×(+10)
                = −60 + 750 = **+690**
    上学年 7500 // 100 = 75，本学年 8190 // 100 = 81 → ``Delta`` = **+6** ≥ +5，
    但 ``min delta_i`` = −6 ≤ −5 → 稳步提升不成立。
    非波动大（5 正 1 负，min = 1 < 3）；``Delta`` = +6 > −5 且下降 ≥5 的项只有 1 个
    → 也非持续下滑 → **稳定**。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.SIT_AND_REACH: 69,       # −6 ← 唯一的下降项
            ScoredItem.VITAL_CAPACITY: 85,      # +10
            ScoredItem.SPRINT_50M: 85,          # +10
            ScoredItem.STANDING_JUMP: 85,       # +10
            ScoredItem.PULL_UP_OR_SIT_UP: 85,   # +10
            ScoredItem.DISTANCE_RUN: 85,        # +10
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == 6
    assert min(deltas.values()) == -6
    assert _oracle(deltas, total_change) == "稳定"


def test_stable_when_nothing_crosses_any_threshold():
    """稳定 = 以上皆不满足（残差类）。

    算式：Σ w·d = 15×(+2) + 20×(−2) = 30 − 40 = **−10**
    上学年 7500 // 100 = 75，本学年 7490 // 100 = 74 → ``Delta`` = **−1**。
    1 正 1 负 → 非波动大；−1 > −5 且无一项 ≤ −5 → 非持续下滑；−1 < +5 → 非稳步提升。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.VITAL_CAPACITY: 77,      # +2
            ScoredItem.SPRINT_50M: 73,          # −2
            ScoredItem.SIT_AND_REACH: 75,
            ScoredItem.STANDING_JUMP: 75,
            ScoredItem.PULL_UP_OR_SIT_UP: 75,
            ScoredItem.DISTANCE_RUN: 75,
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == -1
    assert _oracle(deltas, total_change) == "稳定"


def test_total_rise_of_four_is_stable_not_improving():
    """``Delta`` = +4 差一分不够：从下方钉住 ``Delta >= +5`` 这个边界。

    算式：Σ w·d = 85 × (+5) = **+425**
    上学年 7500 // 100 = 75，本学年 7925 // 100 = 79 → ``Delta`` = **+4** < +5 → 稳定。
    （六项各升 5 分却判「稳定」，因为 BMI 没动、加权后总分只涨 4 分——这正是
    Ruling 63「总分必须是 0–100 加权口径」的直接后果：在 600 分制上它会涨 30 分。）
    """
    previous = _scores(_flat(75))
    current = _scores(_flat(80))
    deltas, total_change = _deltas(previous, current)
    assert total_change == 4
    assert _oracle(deltas, total_change) == "稳定"


def test_one_zero_delta_makes_volatile_unreachable():
    """一项 ``delta_i = 0`` → 5 个非零项里 ``min(#{正}, #{负})`` ≤ 2 → 波动大不可达。

    算式：Σ w·d = 15×(+13) + 10×(+12) + 10×(+11) + 20×(−13) + 10×(−12) + 20×0
                = 195 + 120 + 110 − 260 − 120 + 0 = **+45**
    上学年 7500 // 100 = 75，本学年 7545 // 100 = 75 → ``Delta`` = **0**。
    与 :func:`test_volatile_by_three_up_three_down_with_big_swing` 只差「耐力跑保持 75」
    这一处：那边 3 正 3 负判波动大，这边 3 正 2 负 1 零 → 落到稳定。
    spec §14 #23 明写这是刻意的保守，故必须由测试钉住而不是留给读者猜。
    """
    previous = _scores(_flat(75))
    current = _scores(
        {
            ScoredItem.VITAL_CAPACITY: 88,      # +13
            ScoredItem.SIT_AND_REACH: 87,       # +12
            ScoredItem.STANDING_JUMP: 86,       # +11
            ScoredItem.SPRINT_50M: 62,          # −13
            ScoredItem.PULL_UP_OR_SIT_UP: 63,   # −12
            ScoredItem.DISTANCE_RUN: 75,        # 0 ← 持平
        }
    )
    deltas, total_change = _deltas(previous, current)
    assert total_change == 0
    assert deltas[ScoredItem.DISTANCE_RUN] == 0
    assert max(abs(d) for d in deltas.values()) == 13 >= VOLATILE_ITEM_SWING
    assert _oracle(deltas, total_change) != "波动大"
    assert _oracle(deltas, total_change) == "稳定"


# ---------------------------------------------------------------------------
# 500 人全覆盖 + 方向回归（M5 的直接守卫）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def week1_pairs():
    """``build_dataset(SeedConfig())`` 的两学年 ``week1`` 记录，按 ``student_id`` 配对。

    返回 ``{student_id: (上学年记录, 本学年记录)}``。

    用记录里的 **``score_*`` 得分列**算 ``delta_i`` 与 ``Delta``，不用生成器的中间变量
    （那是自证）。得分列是生成期的诊断量、不写盘也不入库，``inject_dirty`` 只改测量列，
    故缺省配置下的脏数据注入不会污染这里的对账；它们与原始值的自洽由
    ``test_generated_raw_values_roundtrip_through_the_official_table`` 单独钉住。
    ``duplicate`` 注入是整行逐字复制（Ruling 52），``setdefault`` 因此取到哪一份都一样。
    """
    ds = build_dataset(SeedConfig())
    years = sorted({record["academic_year"] for record in ds["fitness"]})
    assert len(years) == 2, f"趋势判定需要恰好两个学年，实际是 {years}"
    previous_year, current_year = years
    seen: dict[int, dict[str, dict]] = {}
    for record in ds["fitness"]:
        if record["timepoint"] != "week1":
            continue
        slot = seen.setdefault(record["student_id"], {})
        slot[record["academic_year"]] = record
    pairs = {}
    for student_id, slot in seen.items():
        assert set(slot) == {previous_year, current_year}, f"学生 {student_id} 的 week1 记录不全"
        pairs[student_id] = (slot[previous_year], slot[current_year])
    return pairs


def _seven_scores(record: dict) -> dict[ScoredItem, int]:
    """一条体测记录 → 七项国标得分（BMI + 六个短板项），**全部取自记录里的得分列**。"""
    scores = {BMI: int(record["score_bmi"])}
    for item in SIX:
        scores[item] = int(record[f"score_{item.value}"])
    return scores


def _deltas_of(pair) -> tuple[dict[ScoredItem, int], int, str]:
    """一对 week1 记录 → ``(六个 delta_i, Delta, trend_label)``，全部取自记录本身。"""
    previous, current = pair
    previous_scores = _seven_scores(previous)
    current_scores = _seven_scores(current)
    deltas = {item: current_scores[item] - previous_scores[item] for item in SIX}
    total_change = _weighted_total(current_scores) - _weighted_total(previous_scores)
    assert previous["trend_label"] == current["trend_label"], "同一名学生两学年的标签必须一致"
    return deltas, total_change, current["trend_label"]


def test_oracle_agrees_with_trend_label_for_all_500_students(week1_pairs):
    """**Ruling 69① 的承重断言**：500 人逐人 ``_oracle(实际 delta) == trend_label``。

    ``trend_label`` 是交给 Task 8 交叉验证、并驱动分层规则 Y4 的真值（spec §10.5）。
    上一轮它与数据 88.2% 不一致却全绿，因为没有任何一条测试钉住方向。本条要求
    **不一致数为 0**：一处不一致就是一个学生的真值是假的。
    """
    assert len(week1_pairs) == 500
    mismatches: list[tuple[int, str, str]] = []
    per_label = Counter()
    for student_id in sorted(week1_pairs):
        deltas, total_change, label = _deltas_of(week1_pairs[student_id])
        expected = _oracle(deltas, total_change)
        per_label[label] += 1
        if expected != label:
            mismatches.append((student_id, label, expected))
    assert per_label == Counter(allocate_quota(SeedConfig().trend_mix, 500)), (
        f"四类标签的配额不是精确分配：{dict(per_label)}"
    )
    assert mismatches == [], (
        f"{len(mismatches)} 名学生的 trend_label 与 spec §6.3 判定表不符"
        f"（前 10 条：{mismatches[:10]}）"
    )


def test_declining_group_really_declines_and_improving_group_really_improves(week1_pairs):
    """**方向回归测试**（评审 M5 的直接守卫，本条在修复前必须红）。

    按 ``trend_label`` 分组，量的是**国标加权总分**（0–100）的学年间变化：

    * 「持续下滑」组：``Delta`` 中位数 < 0，且负数占比 ≥ 95%；
    * 「稳步提升」组：``Delta`` 中位数 > 0，且正数占比 ≥ 95%。

    95% 而不是 100%：符号约定（Ruling 62）保证**方向**，但 spec §6.3 的持续下滑允许
    「总分没降够 5 分、只是 ≥3 项各降 ≥5 分」这种学生存在，故留 5% 的余量给判据的
    第二分支。上一轮的实测是 100/100 全为正与 125/125 全为负——**方向整体互换**，
    任何非零的容差都拦不住它，所以本条的中位数符号是承重的。
    """
    groups: dict[str, list[int]] = {}
    for pair in week1_pairs.values():
        _deltas, total_change, label = _deltas_of(pair)
        groups.setdefault(label, []).append(total_change)

    declining = groups["持续下滑"]
    improving = groups["稳步提升"]
    assert len(declining) == 100 and len(improving) == 125

    declining_median = statistics.median(declining)
    improving_median = statistics.median(improving)
    declining_negative = sum(1 for value in declining if value < 0) / len(declining)
    improving_positive = sum(1 for value in improving if value > 0) / len(improving)

    assert declining_median < 0, (
        f"「持续下滑」组的加权总分变化中位数是 {declining_median:+.1f}（应为负）："
        f"标签与数据方向相反"
    )
    assert declining_negative >= 0.95, (
        f"「持续下滑」组只有 {declining_negative:.2%} 的学生总分真的下降（要求 ≥ 95%）"
    )
    assert improving_median > 0, (
        f"「稳步提升」组的加权总分变化中位数是 {improving_median:+.1f}（应为正）："
        f"标签与数据方向相反"
    )
    assert improving_positive >= 0.95, (
        f"「稳步提升」组只有 {improving_positive:.2%} 的学生总分真的上升（要求 ≥ 95%）"
    )


def test_all_four_labels_are_populated_and_volatile_has_the_required_shape(week1_pairs):
    """四类都非空，且「波动大」组**每个人**都满足构造要求（评审 C2 的直接守卫）。

    上一轮 75 名「波动大」学生里只有 **1** 人真的满足 spec §6.3 的判据（35 人被判持续
    下滑、34 人被判稳步提升），因为偏移模型是「跨六项共享一个偏移 + 每项 sd 1.5 的小
    抖动」，六项几乎总是同号。本条把构造要求钉成断言：

    * 人数 == ``allocate_quota`` 给出的精确配额 75；
    * 每人**恰好 3 正 3 负**（``delta_i = 0`` 一个都没有）；
    * 每人 ``max|delta_i| >= 10``。
    """
    quota = allocate_quota(SeedConfig().trend_mix, 500)
    assert quota == {"持续下滑": 100, "波动大": 75, "稳步提升": 125, "稳定": 200}
    counts = Counter()
    volatile_shapes = []
    for pair in week1_pairs.values():
        deltas, _total_change, label = _deltas_of(pair)
        counts[label] += 1
        if label == "波动大":
            ups = sum(1 for d in deltas.values() if d > 0)
            downs = sum(1 for d in deltas.values() if d < 0)
            zeros = sum(1 for d in deltas.values() if d == 0)
            volatile_shapes.append((ups, downs, zeros, max(abs(d) for d in deltas.values())))
    assert counts == Counter(quota), f"四类标签的实到人数 {dict(counts)} 不等于配额 {quota}"
    assert len(volatile_shapes) == 75
    for ups, downs, zeros, swing in volatile_shapes:
        assert (ups, downs, zeros) == (3, 3, 0), f"波动大要求恰好 3 正 3 负，实际 {(ups, downs, zeros)}"
        assert swing >= VOLATILE_ITEM_SWING, f"波动大要求 max|delta| ≥ 10，实际 {swing}"
