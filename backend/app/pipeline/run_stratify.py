"""分层链路的**纯内存**版本：``score_item → compute_snapshot → derive → stratify``。

本模块是算法的**唯一编排路径**：``stratify_dataset`` 供 Task 9 的两条集成测试（黄金用例
与 500 人分布）直接调用，``daily.py`` 的落库阶段则复用这里的 :func:`cohort_snapshot`、
:func:`evaluate`、:func:`result_dict` 与 :func:`input_snapshot_of`——**不另写第二套**。
两套算法路径的后果是「离线复算的结果与库里的不一样」，而那正是 spec §1.3 逐人可追溯
要防的事。

**唯一一处不共用的是 ``stratify`` 这个调用点**：``daily.py`` 在自己的命名空间里
``from app.domain.stratify import stratify`` 后逐人调用，而本模块的
:func:`stratify_dataset` 也调它。这不是两条算法路径（调的是同一个 domain 纯函数），
而是为了让 ``tests/pipeline/test_daily.py`` 的 ``test_failure_rolls_back_whole_batch``
能 monkeypatch ``app.pipeline.daily.stratify`` 把整批打崩——若 ``daily.py`` 只调
``stratify_dataset``，那次 monkeypatch 会静默无效、整批照常成功、断言当场失败。

本模块**不触碰数据库**（``stratify_dataset`` 是 spec §12 黄金用例与分布测试的入口，
它们必须能在没有库的情况下跑）。它会读盘两次，都是只读参考数据：
``app.refdata.standard()`` 的国标评分表与 ``data/indicator_ranges.yaml`` 的清洗区间表
——后者是 Task 5 清洗层的输入，而喂给 ``score_item`` 的值**必须是清洗后的**（Ruling 21）。

``payload`` 的两种形状（计划 Task 10 的 Interfaces）：

* ``list`` → 黄金用例输入结构（``tests/fixtures/golden_cases.json`` 的 ``input``）：
  每人给 8 项原始测量 + 体成分 + 上学年原始值，``snapshot_muscle_p20`` **手工给定**；
* ``dict`` → :func:`app.seed.generate.build_dataset` 的输出结构：三类原始记录 +
  ``population``，肌肉量 P20 由本模块算出的快照经 :func:`lookup_p20` 查得。
"""
import datetime as dt
import pathlib
from dataclasses import dataclass, fields, replace

from app.adapters.base import (
    BODY_COMP_COLUMNS, FITNESS_COLUMNS, RawBodyCompRecord, RawFitnessRecord,
    parse_batch_key,
)
from app.domain.derive import DerivedResult, derive, national_total
from app.domain.indicators import (
    COLUMN_BY_ITEM, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, bmi_of,
    score_item,
)
from app.domain.percentile import (
    MUSCLE_MASS, PercentileRow, compute_snapshot, lines_used, lookup_p10,
    lookup_p20, summarize_source,
)
from app.domain.stratify import Layer, StratResult, explain, stratify
from app.domain.tables import StandardTable
from app.pipeline.clean import clean_body_comp, clean_fitness, load_ranges
from app.refdata import DATA_DIR, RANGES_FILENAME, standard

# ⚠️ ``bmi_of`` 与 ``COLUMN_BY_ITEM`` 在本模块是**重导出**，唯一所有者是
# :mod:`app.domain.indicators`（Plan 02 Task 1 迁走：前者是身高体重的纯函数，住在管道层
# 意味着 domain 里的安全后置规则拿不到它；后者是一张词表，住在 ``app/seed`` 意味着生产层
# 为了拿它必须 import 仿真数据生成器，违反 spec §3.3 的单向依赖）。
# 重导出是为了**保持既有导入面**：``bmi_of`` 在下面 ``__all__`` 里、
# ``run_stratify.bmi_of`` 与 ``run_stratify.COLUMN_BY_ITEM`` 都照旧可用。
# 新代码请直接从 domain 导入；``tests/architecture/test_layering.py`` 的依赖方向守卫
# 会在有人把这两句改回 ``from app.seed...`` 时变红。

__all__ = [
    "Evaluated",
    "PersonInputs",
    "StratifyReport",
    # 跨模块消费的常量，唯一消费者是 ``app/pipeline/percentile_stage.py`` 的那条显式导入：
    # ``WEEK1_TIMEPOINT`` 是 week1 评估锚点的唯一所有者（Ruling 152 合流）、``YEAR_STEP`` 是
    # ``years`` 口径的唯一所有者（Ruling 140）。``from x import name`` 不看 ``__all__``，故
    # 漏掉它们不影响功能，但会让下一个人以为它们私有、可放心改名——而改值会同时改动 DB 与
    # 内存两条路径的口径。实测（**Task 10 的** fix round 3 做的变异：``WEEK1_TIMEPOINT`` →
    # ``"week8"``；本处此前只写「fix round 3」，与 Task 11 的 fix round 3 撞名，故补上任务名）：
    # **当时那 419 条**测试里 **3 条变红**（419 是那时的套件规模，Task 11 fix round 3 是 428 条；
    # 这个数字不被守卫，只是一次变异取证的记录。⚠️ 它与
    # ``app/pipeline/percentile_stage.py`` 里「418 条测试里只有内存路径那条趋势测试红」
    # **不矛盾**：那一次是 Task 10 的 fix round 1、套件是 418 条，而
    # ``test_memory_path_and_db_path_agree_at_the_pinned_business_date`` 还没写出来，
    # 所以只红 1 条）——``test_daily.py`` 的
    # ``test_trend_matches_the_generator_oracle_on_week1_anchors`` 与
    # ``test_memory_path_and_db_path_agree_at_the_pinned_business_date``、
    # ``test_golden_cases.py`` 的
    # ``test_trend_agrees_with_the_generator_oracle_on_the_decidable_subset``。
    # 列表按 ASCII 字典序，两个大写常量因此排在类名之后、小写函数之前。
    "WEEK1_TIMEPOINT",
    "YEAR_STEP",
    "bmi_of",
    "cohort_snapshot",
    "distribution_of",
    "empty_scores",
    "evaluate",
    "input_snapshot_of",
    "muscle_line_gaps",
    "percentile_source_of",
    "ranges",
    "record_dict",
    "resolve_muscle_lines",
    "result_dict",
    "score_raw",
    "stratify_dataset",
]

# 趋势对比恒取「每学年的 week1」、years 恒为 1.0（Ruling 140）。
# **被否决的读法**：若取「<= business_date 的两条最新记录」，在 D = 2025-09-15 下会比到
# 本学年 week1(2025-09-01) vs 上学年 week16(2024-12-16)，years 变成 ≈0.71 的分数，
# 而 Ruling 114 的年均口径 Delta / years 会把趋势**放大 1.4 倍**、Y4 触发面随之虚高；
# 且它与 Task 6 的 trend_label 永不可比（Ruling 75② 明写「趋势判据只在 week1 上由构造
# 保证」），端到端交叉验证就没了。week8 / week16 是学期内的过程测量，归 spec §8.2 与 Plan 03。
WEEK1_TIMEPOINT = "week1"
YEAR_STEP = 1.0

_ranges_cache = None


def ranges():
    """:func:`app.pipeline.clean.load_ranges` 的进程内单例（与 ``app.seed.generate._ranges`` 同法）。

    区间表只有 ``data/indicator_ranges.yaml`` 一个真相，文件名从 :mod:`app.refdata`
    导入而不是在这里重抄一遍——两处字面量漂移的后果是清洗层静默用不上越界保护，
    而 ``load_ranges`` 的键集合校验只在**它读到的那个文件**上生效。
    （Plan 02 Task 1 之前它住在 ``app.seed.generate``，于是本模块为了拿一个文件名字符串
    就得 import 仿真数据生成器；:mod:`app.refdata` 是 ``DATA_DIR`` 与
    ``STANDARD_FILENAME`` 的既有所有者，搬过去之后「哪个文件在哪个目录」在同一个模块里。）

    **导出而不私有**：``daily.py`` 的 Clean 阶段要用同一份区间表，两处各读一次盘、
    或其中一处自己拼一个路径，都会让「清洗口径只有一个所有者」这句话不成立。
    """
    global _ranges_cache
    if _ranges_cache is None:
        _ranges_cache = load_ranges(pathlib.Path(DATA_DIR) / RANGES_FILENAME)
    return _ranges_cache


@dataclass(frozen=True)
class PersonInputs:
    """一个人在某一次判定里的**全部**输入。

    **前 12 个字段**与 :func:`app.domain.derive.derive` 的 11 个参数一一对应
    （``age_group`` 在第 9 位——少写一个不会立刻 ``TypeError``，而是 ``snapshot`` 被当成
    ``age_group``、``40.0`` 被当成 ``snapshot``，然后在 ``find_weaknesses`` 里以一个看不出
    所以然的错误炸开）。:func:`evaluate` 因此按关键字展开，不按位置传参。

    **后 3 个字段是 Plan 02 Task 7 加的（P7-A1 / P7-A3），``derive`` 一个都不读**：它们只
    服务 :func:`input_snapshot_of`，即处方侧判定输入的**可追溯性**（spec §4.3）。
    ⚠️ 挂在 ``PersonInputs`` 上**不等于**进了分层判定——守卫是
    ``tests/pipeline/test_prescription_stage.py`` 的
    ``test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict``（改
    ``snapshot_muscle_p10`` 的值，分层结论一个字都不变；同一条测试的后半段是对照：
    改 ``snapshot_muscle_p20`` **必须**改结论，否则「把所有分位输入都拔掉」这种改动能骗过它）。

    * ``height_cm`` / ``weight_kg`` —— 评估锚点那一批 ``fitness_test_result`` 的两列原值。
      它们**只**被 :func:`input_snapshot_of` 拿去喂 :func:`app.domain.indicators.bmi_of`，
      算出 ``input_snapshot`` 的 ``"bmi"`` 键（**原始值**，不是国标得分）。
      spec §7.4 的安全后置要的是「BMI > 30」这个原始值，而 ``curr_scores["bmi"]`` 存的是
      **得分**，两者不可互换（P7-A9：``bmi_of`` 的 docstring 在 Task 1 就预写了这个用途）。
      ⚠️ **绝不让 ``profile_of`` 回查 ``fitness_test_result`` 重算**——那是第二个所有者
      （同一份身高体重在两处被算成 BMI，任一处改口径就漂移）。
    * ``snapshot_muscle_p10`` —— 肌肉量 **P10**，由 :func:`resolve_muscle_lines` 与 P20
      **同时**回填。⚠️ **P10 不进分层判定**（红线，P7-A3）：spec §6.3② 的 ``C`` 用 P20，
      spec §7.4 的处方安全触发用 P10，两条线服务两件不同的事（P10 < P20，混用会**收窄**
      ``C`` 的触发面、改掉 Plan 01 已结案的标签）。

    ``curr_total`` / ``prev_total`` 由**调用方**给出而不是在这里现算：DB 路径传的是
    ``fitness_test_result.total_score`` 那一列的存量值，于是 ``derive`` 的 Ruling 118-M1
    值校验真的在核对「落库的总分」与「落库的七项得分」是否自洽；内存路径没有存量列，
    由 :func:`national_total`（唯一所有者，Ruling 63）算出。**任何路径都不得手写加权求和**。

    ``years`` 在**无历史时也必须是 1.0**，不得传 0（Ruling 123：``years <= 0`` 会
    ``ValueError``，而 ``prev_scores is None`` 已经是「无历史」的唯一编码，不得用
    ``years = 0`` 做第二重编码）。

    ``prev_age_group`` 只用于**上学年记录的正查得分**（Ruling 56）：查表用的龄组必须是
    该记录所属学年的那一组，否则趋势差值带系统性偏差，而趋势是规则 Y4 的唯一输入。
    ``age_group`` 则是**本学年**的组，用于短板判定与快照查询。

    ⚠️ **15 个字段一个都没有缺省值**（含新加的三个，与 ``snapshot_muscle_p20`` 同口径）：
    构造点必须显式说出每一个值。给缺省的后果是「漏改一个构造点」静默退化成 ``None``
    ——实测构造点只有 **3** 处（``percentile_stage.cohort_from_db``、本模块的
    :func:`_from_golden_cases` 与 :func:`_from_dataset`），漏掉任何一处，那一整条路径的
    ``"bmi"`` 或 ``"snapshot_muscle_p10"`` 就恒为 ``None``、安全触发永不成立且不报错。
    """

    student_id: object
    sex: Sex
    age_group: str
    prev_age_group: str
    curr_scores: dict
    prev_scores: dict | None
    curr_total: int | None
    prev_total: int | None
    years: float
    body_fat_pct: float | None
    muscle_mass_kg: float | None
    snapshot_muscle_p20: float | None
    # --- 以下三个是 Plan 02 Task 7 加的，derive 一个都不读（见 docstring）---
    height_cm: float | None
    weight_kg: float | None
    snapshot_muscle_p10: float | None


@dataclass(frozen=True)
class Evaluated:
    """一个人 ``derive`` 之后的结果，即 ``stratify`` 的输入与它当时的输入。"""

    person: PersonInputs
    derived: DerivedResult


@dataclass(frozen=True)
class StratifyReport:
    """一次纯内存分层的产出。

    ``results`` 每项的键固定为 ``student_id`` / ``label`` / ``hit_rules`` / ``W`` / ``C`` /
    ``valid_count`` / ``dominant_bucket`` / ``trend`` / ``percentile_source`` / ``explain``
    （计划 Task 10 的 Interfaces 块逐字）。``distribution`` 的键是四个标签、值是**占比
    float**（不是计数），四个键**恒在**（无人的档为 ``0.0``）——少一个键会让
    ``dist["green"]`` 在「本日没有绿层」这种完全合法的情况下 ``KeyError``。
    """

    results: list[dict]
    distribution: dict[str, float]


def score_raw(
    raw: dict, sex: Sex, age_group: str, table: StandardTable
) -> dict[ScoredItem, int | None]:
    """8 项原始测量 → 7 项国标得分（含由身高体重合成的 BMI）。

    **前置条件：``raw`` 里的值必须已经是清洗过的**（Ruling 21）。``score_item`` 对越界
    只做夹取，而低侧夹取对「越小越好」的项意味着**低值得高分**（实测 50 米跑与耐力跑的
    0.0 秒都返回 100 分）——一个零填充的缺测会给体能最差的学生送上 20% 权重的满分，
    还同时抹掉两个桶的短板，全程不报错。故 :func:`_from_dataset` 先过 Task 5 的清洗层。

    返回的 dict **恒含 7 个键**（缺测的值为 ``None``）：``derive`` 的
    ``_require_seven_keys``（Ruling 101）要求键齐全，缺键会 ``KeyError``。

    项 → 原始值列名的映射从 :data:`app.domain.indicators.COLUMN_BY_ITEM` 导入，
    **不在这里重抄**：它无法从名字推导（``pull_up_or_sit_up`` 对应的是
    ``strength_count``），抄错的后果是某一项恒为 ``None``、该桶短板静默消失。
    BMI 那一项走 :func:`app.domain.indicators.bmi_of` 合成，同样不在这里重写算式。
    """
    scores = {
        ScoredItem.BMI: score_item(
            table, ScoredItem.BMI,
            bmi_of(raw.get("height_cm"), raw.get("weight_kg")), sex, age_group,
        )
    }
    for item in WEAKNESS_ITEMS:
        scores[item] = score_item(table, item, raw.get(COLUMN_BY_ITEM[item]), sex, age_group)
    return scores


def empty_scores() -> dict[ScoredItem, int | None]:
    """七项全缺测的得分表（该生在本批里根本没有体测记录时用）。

    七项全 ``None`` ⇒ ``national_total`` 返回 ``None`` ⇒ ``valid_count = 0`` ⇒ Z0 闸门
    拦下、标签 ``insufficient_data``。**这是合法状态**（Ruling 106），不是异常，
    不要为它做前置特判或跳过——跳过的后果是这个人在 ``derived_metrics`` 与
    ``stratification_result`` 里凭空消失，而 spec §4.6 要求运维记录能数出「本日没分层的人」。
    """
    return {item: None for item in ScoredItem}


def cohort_snapshot(
    persons: list[PersonInputs], table: StandardTable
) -> list[PercentileRow]:
    """整批人 → 校内百分位快照（:func:`compute_snapshot` 在本项目里的**唯一**调用点）。

    样本构成严格遵守 Ruling 88 的调用方职责与 Ruling 121 的两条口径：

    * **7 个计分项**：每人每项最多一行，取 ``curr_scores``（即锚点 week1 的得分）；
      ``score is None`` 的行**不传进去**（Task 8 前向约束）。快照不需要预筛，
      ``derive`` 经 ``lookup_p25`` 按 ``(item, sex, age_group)`` 三元自行挑判定线。
    * **肌肉量**：**每人最多一行**（样本单位是学生，不是测量行）——按测量行入样会把
      同一个人的三次测量当三个样本，两种口径的 P20 **不同**（按 (性别, 年级组) 分组，
      fix round 3 实测跨度 −0.06 到 +0.40 kg、符号都会翻，逐组的表在
      :func:`app.domain.percentile.compute_snapshot` 的 docstring 里），足以翻掉几个人的
      ``C``（本口径实测 **7 人**：男 2 + 女 5）。喂的必须是**清洗后**的值
      （缺省注入下存在 ``muscle_mass_kg = 135.0`` 这种越界值，未清洗会把 P20 拉高）。

      ⚠️ 本处此前还印着「green 的容差余量只剩 **0.4 个百分点**（Ruling 128）」——那是
      **零注入**那一组的余量，而本函数的调用方 ``stratify_dataset(build_dataset(cfg))``
      走的是**缺省注入**，同一 seed 下 green = 34.0%、对下界 30% 的余量是 **4.0 个百分点**
      （fix round 3 复跑；两组的完整对照表见
      ``tests/integration/test_golden_cases.py::test_target_layer_distribution_within_tolerance``
      的 docstring）。这与 Ruling 199 是**同一个缺陷的第二个住址**：0.4 pp 那个数只在
      零注入下成立，而零注入这条路径**没有任何测试守 green**（``tests/pipeline/test_daily.py``
      的 ``CLEAN_CFG`` 是 60 人、只钉趋势不钉分层），故它是历史实测、不被守卫。
    """
    rows: list[dict] = []
    for person in persons:
        for item in ScoredItem:
            score = person.curr_scores.get(item)
            if score is None:
                continue
            rows.append(
                {
                    "sex": person.sex.value,
                    "age_group": person.age_group,
                    "item": item.value,
                    "score": score,
                }
            )
        if person.muscle_mass_kg is not None:
            rows.append(
                {
                    "sex": person.sex.value,
                    "age_group": person.age_group,
                    "item": MUSCLE_MASS,
                    "score": person.muscle_mass_kg,
                }
            )
    return compute_snapshot(rows, table)


def resolve_muscle_lines(
    persons: list[PersonInputs], snapshot: list[PercentileRow]
) -> list[PersonInputs]:
    """按 ``(sex, age_group)`` 从快照**同时**回填每人的 ``snapshot_muscle_p20`` 与 ``snapshot_muscle_p10``。

    **两条路径共用这一个回填函数**（内存的 :func:`_from_dataset` 与 DB 的
    ``daily.py``），故不可能一处查表、另一处凭空给值——那正是 Ruling 102 的缺陷形态：
    没有生产者时只能传 ``None``，``muscle_low`` 永不可达、``C`` 退化成只看体脂率，
    **且不报错**。

    ⚠️ **两档必须一次回填完**（P7-A3 / Plan 02 Task 7）：P20 服务 spec §6.3② 的 ``C``
    判定（→ 分层标签），P10 服务 spec §7.4 的处方安全触发（→ ``needs_review``）。
    只回填 P20 的话，``snapshot_muscle_p10`` 在 DB 路径上恒为 ``None``、安全触发
    **永不成立**，而全链路不报错（``apply_safety`` 对 ``None`` 的处置是「不触发 +
    在 ``safety_skipped`` 里留痕」，看起来完全合法）。守卫是
    ``tests/pipeline/test_prescription_stage.py`` 的
    ``test_resolve_muscle_lines_backfills_p20_and_p10_together``。

    ⚠️ **P10 绝不进分层判定**（红线）：``evaluate`` 按关键字展开 ``PersonInputs`` 时
    **不传**它，``derive`` / ``flag_body_comp`` 的形参里也没有它（守卫
    ``tests/domain/test_derive.py::test_smi_is_not_an_input_at_all`` 逐字钉住那个签名）。

    查不到（该组肌肉量样本 < ``MIN_SAMPLE``，按 Ruling 121 第 4 步不产出行）时两档都保持
    ``None``：``flag_body_comp`` 的肌肉量那一支于是无从成立，与 ``lookup_p25`` 的
    ``None`` 语义同构（Ruling 21：缺测不当最坏值）。
    """
    return [
        replace(
            person,
            snapshot_muscle_p20=lookup_p20(snapshot, person.sex, person.age_group),
            snapshot_muscle_p10=lookup_p10(snapshot, person.sex, person.age_group),
        )
        for person in persons
    ]


def muscle_line_gaps(
    persons: list[PersonInputs], snapshot: list[PercentileRow]
) -> int:
    """**缺肌肉量判定线的组数**（Ruling 121 第 4 步要求的留痕）。

    口径：``persons`` 里出现过的 ``(sex, age_group)`` 组数，减去快照里已有肌肉量行的组数。
    该组一个人也没测 InBody 时同样算一条缺线——那个组确实没有判定线，而「没有线」与
    「有线但没人低于它」在 ``C`` 上是两件不同的事。

    **不新增第三个 ``reasons`` token**（Ruling 97① 冻结了 vocabulary，改它要先改
    spec §6.3②）：留痕走 ``DailySyncRun`` 的摘要，由 ``daily.py`` 写。
    """
    needed = {(person.sex.value, person.age_group) for person in persons}
    have = {
        (row.sex.value, row.age_group)
        for row in snapshot
        if row.item.value == MUSCLE_MASS
    }
    return len(needed - have)


def evaluate(persons: list[PersonInputs], snapshot: list[PercentileRow]) -> list[Evaluated]:
    """逐人调用 :func:`app.domain.derive.derive`。**按关键字传参**（11 个参数，见 PersonInputs）。"""
    evaluated = []
    for person in persons:
        derived = derive(
            curr_scores=person.curr_scores,
            prev_scores=person.prev_scores,
            curr_total=person.curr_total,
            prev_total=person.prev_total,
            years=person.years,
            body_fat_pct=person.body_fat_pct,
            muscle_mass_kg=person.muscle_mass_kg,
            sex=person.sex,
            age_group=person.age_group,
            snapshot=snapshot,
            snapshot_muscle_p20=person.snapshot_muscle_p20,
        )
        evaluated.append(Evaluated(person=person, derived=derived))
    return evaluated


def percentile_source_of(person: PersonInputs, snapshot: list[PercentileRow]) -> str:
    """``stratification_result.percentile_source`` 的值（Ruling 137 的生产者接线处）。"""
    return summarize_source(
        lines_used(person.curr_scores, snapshot, person.sex, person.age_group)
    )


def result_dict(
    evaluated: Evaluated, result: StratResult, snapshot: list[PercentileRow]
) -> dict:
    """一个人 → 计划 Interfaces 钉住的那 10 个键。

    ``hit_rules`` 是 ``list[str]``（``RuleId`` 的 ``.value``），**任何路径都至少一项**：
    Z0 命中时是 ``["Z0"]`` 而不是空列表（Ruling 125）——``explain()`` 按 ``hit_rules[-1]``
    取文案，空列表会当场 ``IndexError``，而 Z0 恰恰是最需要向学生解释「为什么没有分层
    结果」的那条路径。
    """
    person, derived = evaluated.person, evaluated.derived
    return {
        "student_id": person.student_id,
        "label": result.label.value,
        "hit_rules": [rule.value for rule in result.hit_rules],
        "W": derived.weakness.count,
        "C": derived.body_comp.abnormal,
        "valid_count": derived.weakness.valid_count,
        "dominant_bucket": derived.weakness.dominant_bucket,
        "trend": derived.trend.value,
        "percentile_source": percentile_source_of(person, snapshot),
        "explain": explain(result, derived),
    }


def input_snapshot_of(
    evaluated: Evaluated, result: StratResult, snapshot: list[PercentileRow]
) -> dict:
    """``stratification_result.input_snapshot``：判定当时的全部输入，使任一条结果都能离线复算。

    spec §4.3 要求的可追溯性落在这一列上——不必回到当天的原始数据就能重算出同一个标签。
    故它同时存**输入**（七项得分、体成分两列、所用判定线、years、龄组）与**中间量**
    （W、C、valid_count、趋势、主导桶、国标总分）。

    ⚠️ **Plan 02 Task 7 起它还额外承载「处方侧的判定输入」两个键**（``"bmi"`` 原始值与
    ``"snapshot_muscle_p10"``），于是顶层是 **28** 个键（Plan 01 是 26 个）。理由：spec §7.4
    的安全后置要用「BMI > 30」这个**原始值**与「肌肉量 < P10」这条线，而
    :func:`app.pipeline.prescription_stage.profile_of` 只从本快照读、**不回查
    ``fitness_test_result`` 重算**（那会产生第二个所有者：同一份身高体重在两处被算成 BMI，
    任一处改口径就漂移）。**BMI 与 P10 是处方的判定输入，不落进快照就等于处方的可追溯性
    断在这一环**——一张 2026 年生成的处方必须能在 2027 年离线复算出它当时为什么被判
    ``needs_review``。守卫是 ``tests/pipeline/test_prescription_stage.py`` 的
    ``test_input_snapshot_gains_the_raw_bmi_and_the_p10_line``（28 个键逐字钉死）与
    ``test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result``
    （把 ``fitness_test_result`` 改坏，``profile_of`` 的结果不变）。

    ⚠️ **这两个键对分层判定是惰性的**：``derive`` 不读它们，``evaluate`` 也不传它们。
    加键因此不会改任何标签——``tests/pipeline/test_daily.py`` 的两条
    ``assert first == second``（幂等 + 全表 canonical sha256）比的是**两次运行相等**，
    不是与一个字面哈希相等，故加键后它们仍然绿（P7-A6）。

    键一律用 ``.value`` 而不是枚举成员：``json.dumps`` 对 ``str`` 子类的**字典键**会走
    ``str(key)``，实测得到 ``"ScoredItem.BMI"`` 而不是 ``"bmi"``——落库的键于是变成
    一个没人认得的字面量，离线复算时 ``KeyError``。
    """
    person, derived = evaluated.person, evaluated.derived
    lines = lines_used(person.curr_scores, snapshot, person.sex, person.age_group)
    return {
        "sex": person.sex.value,
        "age_group": person.age_group,
        "prev_age_group": person.prev_age_group,
        "years": person.years,
        "curr_scores": {item.value: person.curr_scores.get(item) for item in ScoredItem},
        "prev_scores": (
            None if person.prev_scores is None
            else {item.value: person.prev_scores.get(item) for item in ScoredItem}
        ),
        "curr_total": person.curr_total,
        "prev_total": person.prev_total,
        # BMI 的**原始值**（kg/m²），由 domain 的 bmi_of 从评估锚点那一批的身高体重算。
        # ⚠️ 与 curr_scores["bmi"]（国标**得分**）是两个键、两件事：spec §7.4 的安全触发
        # 判的是「BMI > 30」这个原始值，得分那一档的口径是「两头 80、中间 100」的区间映射，
        # 反查不回唯一的原始值（indicators.raw_from_score 因此拒收 BMI）。
        # 身高或体重缺测时为 None（Ruling 21：缺测不当最坏值，绝不当 0——
        # 一个 bmi=0 的快照会让「0 > 30」为假，学生静默躲过复核）。
        "bmi": bmi_of(person.height_cm, person.weight_kg),
        "body_fat_pct": person.body_fat_pct,
        "body_fat_limit": derived.body_comp.limit,
        "muscle_mass_kg": person.muscle_mass_kg,
        # None = 该组肌肉量样本 < MIN_SAMPLE、没有 P20 判定线（Ruling 121 第 4 步）。
        # 这是**留痕**：读这一列就能分清「肌肉量够用」与「压根没有这条线」。
        "snapshot_muscle_p20": person.snapshot_muscle_p20,
        # 同上，但这一档服务 spec §7.4 的处方安全触发（肌肉量 < P10），**不进分层判定**。
        "snapshot_muscle_p10": person.snapshot_muscle_p10,
        "p25_lines": {row.item.value: row.p25 for row in lines},
        "W": derived.weakness.count,
        "C": derived.body_comp.abnormal,
        "body_comp_reasons": list(derived.body_comp.reasons),
        "valid_count": derived.weakness.valid_count,
        "dominant_bucket": derived.weakness.dominant_bucket,
        "weakness_items": [item.value for item in derived.weakness.items],
        "trend": derived.trend.value,
        "annual_change": dict(derived.annual_change),
        "national_total": derived.national_total,
        "label": result.label.value,
        "hit_rules": [rule.value for rule in result.hit_rules],
        "reason": result.reason,
        "percentile_source": percentile_source_of(person, snapshot),
    }


def distribution_of(labels) -> dict[str, float]:
    """标签序列 → 四档**占比**（float）。四个键恒在，无人的档为 ``0.0``。"""
    counts = {layer.value: 0 for layer in Layer}
    total = 0
    for label in labels:
        counts[label] += 1
        total += 1
    return {key: (count / total if total else 0.0) for key, count in counts.items()}


# ---------------------------------------------------------------------------
# 两种 payload 形状 → PersonInputs
# ---------------------------------------------------------------------------

def _fitness_record(row: dict) -> RawFitnessRecord:
    """``build_dataset`` 的一条体测 dict → 契约记录（只挑 11 个契约列）。

    ``row[column]`` 逐列取而不是 ``**row``：生成器的记录还带着 ``student_id`` /
    ``academic_year`` / ``timepoint`` / ``score_*`` / ``trend_label`` 这些**不写盘**的诊断列，
    直接展开会 ``TypeError``（多余的关键字参数）。漏一列则当场 ``KeyError``。
    """
    return RawFitnessRecord(**{column: row[column] for column in FITNESS_COLUMNS})


def _body_comp_record(row: dict) -> RawBodyCompRecord:
    return RawBodyCompRecord(**{column: row[column] for column in BODY_COMP_COLUMNS})


def record_dict(record: RawFitnessRecord) -> dict:
    """契约记录 → ``score_raw`` 吃的 dict（键名与 ``COLUMN_BY_ITEM`` 的值对齐）。"""
    return {field.name: getattr(record, field.name) for field in fields(RawFitnessRecord)}


def _week1_dates(fitness: list[RawFitnessRecord]) -> list[dt.date]:
    """全部 ``week1`` 采集日，**降序**。``batch_key`` 一律经 ``parse_batch_key`` 解析。"""
    dates = {
        dt.date.fromisoformat(record.tested_on)
        for record in fitness
        if parse_batch_key(record.batch_key)[1] == WEEK1_TIMEPOINT
    }
    return sorted(dates, reverse=True)


def _from_golden_cases(cases: list[dict]) -> tuple[list[PersonInputs], list[PercentileRow]]:
    """黄金用例（``golden_cases.json`` 的 ``input``）→ ``(persons, snapshot)``。

    链路与该夹具 ``_meta.expected_from`` 写明的逐字一致：``score_item`` →
    ``compute_snapshot``（**这批人自己的 curr 得分**）→ ``national_total`` → ``derive`` →
    ``stratify``。``snapshot_muscle_p20`` 用夹具**手工给定**的值而不是查快照：13 人
    < ``MIN_SAMPLE = 30``，肌肉量组按 Ruling 121 第 4 步不产出行，查表只会得到 ``None``，
    而 GC13 要测的正是「有这条线时 ``C`` 成立」。

    人数 < 30 也意味着 **6 个短板判定项**全部走 ``national_norm`` 兜底（``source =
    "national"``），故这 13 例守卫的是**国标常模判定线**那一路；校内百分位那一路由
    500 人的分布测试守卫。

    **BMI 不在其中**（Ruling 214）：它的官方表是非单调的区间映射，CSV 用哨兵 ``0`` / ``999``
    封口开区间，``national_norm`` 对它抛 ``ValueError``、``compute_snapshot`` **不产出该行**
    （改前会产出一行五档全 ``60.0`` 的退化行——一条「看起来像真判定线」的水平线）。
    故本函数产出的快照是 **24 行**（6 项 × 2 性别 × 2 年级组）而不是 28 行。
    对分层**零影响**：``find_weaknesses`` 与 ``lines_used`` 只遍历 ``WEAKNESS_ITEMS``，
    ``lookup_p25(BMI, …)`` 在生产上从无调用者；受影响的是 Plan 02 的雷达图参照线
    （spec §9.2 要「7 项」），它现在会**查不到 BMI 那一行**而不是拿到一条假线。
    """
    table = standard()
    persons: list[PersonInputs] = []
    for case in cases:
        sex = Sex(case["sex"])
        age = int(case["age"])
        age_group, prev_age_group = age_group_of(age), age_group_of(age - 1)
        curr = case["curr"]
        curr_scores = score_raw(curr, sex, age_group, table)
        prev = case.get("prev")
        prev_scores = None if prev is None else score_raw(prev, sex, prev_age_group, table)
        body_comp = case["body_comp"]
        persons.append(
            PersonInputs(
                student_id=case["student_id"],
                sex=sex,
                age_group=age_group,
                prev_age_group=prev_age_group,
                curr_scores=curr_scores,
                prev_scores=prev_scores,
                curr_total=national_total(curr_scores),
                prev_total=(None if prev_scores is None else national_total(prev_scores)),
                years=float(case["years"]),
                body_fat_pct=body_comp["body_fat_pct"],
                muscle_mass_kg=body_comp["muscle_mass_kg"],
                snapshot_muscle_p20=case["snapshot_muscle_p20"],
                # ⚠️⚠️ **P9-A1（Plan 02 Task 9 更正了 P7-A2 的处置）**：身高体重从
                # ``curr`` 子映射读，**不在夹具顶层再放一份副本**。它们的唯一住址是
                # ``input[i]["curr"]``（与 ``["prev"]``），夹具 ``_meta.bmi`` 逐字写着
                # 「**BMI 不在 input 里**：它由身高体重合成」；而 :func:`score_raw` 合成
                # BMI **得分**读的也正是上面那一份 ``curr``（``bmi_of(raw.get("height_cm"),
                # raw.get("weight_kg"))``），故快照里的**原始值** BMI 与
                # ``curr_scores["bmi"]`` 的**得分**不可能来自两次不同的测量。加顶层副本
                # 就是第二个住址（Global Constraint #3），漂移时两处静默对不上。
                # Task 7 当时用 ``case.get(...)`` 缺省 ``None`` 是因为那份夹具不许改，
                # 代价是 13 例的 ``"bmi"`` 全 ``None`` → spec §7.4 的三档安全触发在黄金用例
                # 里一档都走不到、``needs_review`` 与 ``safety_substitutions`` 恒为假绿。
                # ``.get()`` 而不是硬下标：``curr`` 的 8 列都可能是 ``null``（GC10 有 3 项
                # 缺测），缺测时 ``bmi`` 为 ``None``——**绝不当 0**（Ruling 21：一个
                # ``bmi = 0`` 的快照会让「0 > 30」为假，学生静默躲过复核）。
                # ``snapshot_muscle_p10`` **仍**缺省 ``None``：13 人 < ``MIN_SAMPLE = 30``，
                # 肌肉量组不产出行，而本路径**刻意不调** :func:`resolve_muscle_lines`
                # （P20 用夹具手工给定的值）。故 ``muscle_low_p10`` 那一档在 13 例里
                # 结构上不可达、``safety_skipped`` 恒含 ``"muscle_p10_missing"``——
                # 如实留痕，不是缺陷。
                # 守卫：tests/pipeline/test_prescription_stage.py 的
                # test_golden_case_path_reads_height_and_weight_from_curr_and_leaves_p10_none
                # （单例、手算的 bmi 字面值）与 tests/integration/test_golden_cases.py 的
                # test_golden_cases_reach_the_training_package（13 例逐例钉 ``bmi``）。
                height_cm=curr.get("height_cm"),
                weight_kg=curr.get("weight_kg"),
                snapshot_muscle_p10=case.get("snapshot_muscle_p10"),
            )
        )
    return persons, cohort_snapshot(persons, table)


def _from_dataset(ds: dict) -> tuple[list[PersonInputs], list[PercentileRow]]:
    """:func:`app.seed.generate.build_dataset` 的输出 → ``(persons, snapshot)``。

    **没有 ``business_date`` 可依据**（``stratify_dataset`` 的签名里就没有它），故锚点取
    数据集里**最新的那个 ``week1``**：这与 ``daily.py`` 在 ``D = 2025-09-15`` 上选出的锚点
    逐字相同（``2025-09-01``），两条路径因此在计划钉住的那个业务日期上给出同一批结果。
    ``D`` 更晚时两者会分道——DB 路径按真实的 ``business_date`` 取最新体成分，内存路径
    恒停在 week1——那是「没有业务日期」这个签名限制的必然结果，不是算法分叉。

    三类记录一律**先过 Task 5 的清洗层**再评分（Ruling 21）：``build_dataset`` 缺省会注入
    4% 缺测、0.5% 越界、0.3% 量纲错误与 1% 重复行，不清洗就把 ``muscle_mass_kg = 135.0``
    这类值直接喂进 P20 样本，判定线会被拉高且不报错。

    趋势对比取「每学年的 ``week1``」、``years = 1.0``（Ruling 140），这正是 Task 6
    ``trend_label`` 的口径（Ruling 75②）。**但 500 人跑完后的趋势分布并不等于生成器的配额**
    ``{持续下滑:100, 波动大:75, 稳定:200, 稳步提升:125}``（Ruling 146 更正了此前印在这里的
    那个假等式）：实测 ``seed=20250828`` 得到的是 ``{insufficient_data: 209, 稳定: 120,
    稳步提升: 71, 持续下滑: 60, 波动大: 40}``。

    它**不是全假、是漏了测量条件**：``dirty`` 四项全 0 的**零注入**配置下该等式确实成立
    （同一 seed 实测 ``{持续下滑:100, 波动大:75, 稳定:200, 稳步提升:125}``、
    ``insufficient_data`` 0 人），而 Task 10 的落库取证与
    ``tests/pipeline/test_daily.py::test_trend_matches_the_generator_oracle_on_week1_anchors``
    量的都是零注入；本函数的调用方 ``stratify_dataset(build_dataset(cfg))`` 走的是
    **缺省注入**（4% 逐项缺测），两者不是同一个条件。

    成因是**构造性的、不是实现走偏**：:func:`classify_trend` 在 ``prev_total`` /
    ``curr_total`` 任一为 ``None`` 时归 ``INSUFFICIENT``（Ruling 99），而
    :func:`national_total` 对 7 个计分项**得分**全有或全无——这 7 个得分由 **8 个原始
    单元格**算出（身高与体重共同决定 BMI 得分），任一单元格缺测即让整条记录的总分变
    ``None``；``build_dataset`` 缺省按测量单元格注入 4% 缺测，而可判要求两条锚点记录都
    完整。

    **只印实测、不印概率模型**（硬规矩 #25）：此处此前印着一个把「7 个计分项**得分**」
    当成「7 个独立同率缺测**单元格**」的概率推算，Ruling 159 实测推翻了它的全部前提
    （单元格是 8 个不是 7 个，逐列缺测率也并不相同），故整段删除、**不换新模型**。
    ``seed=20250828``、缺省注入、500 人、内存路径（``stratify_dataset``）实测：**291 人
    可判 / 209 人不可判**。注入形态（清洗前的 week1 行；8 个测量单元格取
    ``MEASURE_COLUMNS_BY_SOURCE["fitness"]``）：共 **1011** 条（两学年 ×500 + 11 条重复
    副本），其中 **252 条（24.9%）**含 ≥1 个缺测单元格；合计缺测 **283 / 8088 = 3.5%**、
    逐列 **2.6%–4.5%**。逐列不等是**抽样波动**、不是配额分摊：``inject_dirty`` 对每个
    测量单元格各消耗一次 ``rng.random()``，``missing`` 的概率恒为
    ``cfg.dirty["missing"] = 0.04``（``app/seed/config.py`` 明写这四类注入不走
    ``allocate_quota``）；六个 seed 的总缺测率实测 **3.5%–4.3%、均值 4.0%**，即注入率
    就是 4%，本 seed 的 3.5% 是抽样偏低的那一端。

    **可判比例随 seed 变动**：四个 seed 实测可判 **227–291 人（45.4%–58.2%）**，故
    ``tests/integration/test_golden_cases.py`` 钉的精确计数只对 ``seed=20250828`` 成立
    ——那是 ``SeedConfig`` 的缺省值，也是该测试 fixture 显式传入的值。

    **真正的不变量是「可判子集上的高一致率」，不是「分布逐类相等」**：那 291 人里有 280 人
    （96.2%）与生成器的 ``trend_label`` 一致。**11 处分歧的真因是 ``outlier`` 注入，11/11**
    （Ruling 210 更正了此前印在这里的一句**编造的机制**——「某个单项缺测被清成 ``None`` →
    该项 delta 退出计数、加权和下降」；它与 Ruling 164 同型，都是借一处真实现象编一个听起来
    毫无破绽的因果故事，故它一路活过了 Ruling 200 的全仓散文清扫）。

    机制（逐人取证，走 ``build_dataset`` 自己的 ``dirty_marks`` 痕迹而不是重新推导，
    硬规矩 #6；11 人全列，非抽样）：``inject_dirty`` 把值抬到 ``indicator_ranges.yaml``
    **上限的 1.5 倍**（``generate.py`` 的 ``inject_dirty`` docstring：「``outlier``：把值抬到
    合理区间上限的 1.5 倍」），清洗层再把它**夹回上限**，而**夹回后的值重新正查会得到一个与
    生成器设计分完全不同的得分**——越大越好项跳到 100、越小越好项跳到底档 10。实测（``ag`` 是
    **该锚点记录所属学年**的年级组，即 ``age_group_of(age)`` / ``age_group_of(age - 1)``，
    Ruling 56；「oracle → got」是生成器的 ``trend_label`` 与管道的判定）::

        sid  性别  ag          锚点侧  列                    干净值→注入值→夹取值    得分      oracle → got
        ---- ----- ----------- ------- --------------------- -------------------- --------- ------------------
         20  男    大一、大二   prev    sit_and_reach_cm       1.1 →  60.0 →  40.0   30 → 100  稳步提升 → 稳定
         26  女    大一、大二   prev    sprint_50m_s          10.0 →  22.5 →  15.0   62 →  10  波动大   → 稳定
         57  男    大一、大二   prev    sprint_50m_s           9.0 →  22.5 →  15.0   60 →  10  稳定     → 稳步提升
        118  男    大一、大二   curr    strength_count        13.0 →  90.0 →  60.0   72 → 100  稳定     → 稳步提升
        167  男    大三、大四   curr    sit_and_reach_cm       0.7 →  60.0 →  40.0   20 → 100  稳定     → 稳步提升
        209  男    大一、大二   curr    sit_and_reach_cm       1.5 →  60.0 →  40.0   30 → 100  稳定     → 稳步提升
        385  男    大三、大四   prev    sit_and_reach_cm       9.5 →  60.0 →  40.0   66 → 100  稳步提升 → 稳定
        395  男    大一、大二   curr    distance_run_s       272.2 → 1350.0 → 900.0  50 →  10  稳定     → 持续下滑
        451  女    大一、大二   prev    sit_and_reach_cm       4.5 →  60.0 →  40.0   40 → 100  稳步提升 → 稳定
        488  女    大三、大四   curr    distance_run_s       251.4 → 1350.0 → 900.0  68 →  10  波动大   → 持续下滑
        495  女    大一、大二   prev    weight_kg（合成 BMI） 54.6 → 225.0 → 150.0  100 →  60  稳定     → 稳步提升

    （sid 495 那一行是 ``weight_kg`` 被注入、身高未被注入，故 BMI 由
    :func:`bmi_of` 用同一行的身高合成后再正查——``bmi`` 是七项里唯一不走
    ``COLUMN_BY_ITEM`` 直读的项。）

    得分跳变直接改掉该生的 ``delta_i`` 与 ``Delta``，趋势因此与生成器的 ``trend_label``
    分道——这是**注入的预期效果**（``outlier`` 就是要造出「被清洗层修正过、因而与设计分不同」
    的记录），不是实现走偏，故 96.2% 就是这组条件下的正确一致率。

    **原来那句机制在代码里结构性不可能发生**（这条论证是构造性的，不依赖抽样）：
    ``national_total`` 对七项得分**全有或全无**——``derive.py:199`` 的
    ``if any(value is None for value in values): return None``；故「可判」⟺ 七项得分齐全
    ⟺ 6 个 delta 全部参与计数，而 ``derive.py:265`` 的
    ``deltas = [curr[item] - prev[item] for item in WEAKNESS_ITEMS]`` 是**无条件**列表推导、
    没有「某项退出计数」的分支。**「某个单项缺测被清成 None → 该项 delta 退出计数」这条路径
    不存在。** 实测佐证：可判的 291 人里，本学年 week1 行含 ≥1 个 ``None`` 单元格的人数是
    **0**（8 个测量单元格取 ``height_cm / weight_kg / vital_capacity_ml / sprint_50m_s /
    sit_and_reach_cm / standing_jump_cm / strength_count / distance_run_s``）。

    三个反例（同样 500 人 / ``seed=20250828``，只改 ``cfg.dirty``，本轮亲跑；
    「同样有缺测这个因、却没有分歧这个果」，硬规矩 #23 加强版）::

        配置                                     decidable  discrepant
        ---------------------------------------- ---------  ----------
        缺省注入（4% 缺测 + 0.5% 越界 + …）          291          11
        B1：同样 4% 缺测，outlier/unit_error/dup = 0  286           0
        B2：只有 outlier 0.5%，缺测 = 0               500          17
        B5：缺测拉到 20%，其余 = 0                     17           0

    B1 直接否证「缺测是成因」（缺测率不变、只关 ``outlier`` → 分歧归零）；B2 反向加强
    （只留 ``outlier`` → 分歧**更多**）；B5 说明缺测只影响**可判人数**、不影响一致率。

    **守卫**：``11`` 这个数字由 ``test_golden_cases.py`` 的
    ``test_trend_agrees_with_the_generator_oracle_on_the_decidable_subset`` 钉住（它同时钉
    291 与 280）；**成因**由同文件的
    ``test_trend_discrepancies_vanish_without_outlier_injection`` 钉住——它就是上面的 B1，
    在零 ``outlier`` 配置下断言分歧为 **0**。把 ``inject_dirty`` 的 ``outlier`` 分支或清洗层
    的夹取改掉，两条一起红（硬规矩 #17：裁定必须同时写出「哪一条测试会因违反它而变红」）。
    """
    table = standard()
    field_ranges = ranges()
    fitness = clean_fitness(
        [_fitness_record(row) for row in ds["fitness"]], field_ranges
    ).fitness
    body_comp = clean_body_comp(
        [_body_comp_record(row) for row in ds["body_comp"]], field_ranges
    ).body_comp

    week1 = _week1_dates(fitness)
    if not week1:
        raise ValueError(
            "数据集里没有任何 week1 体测记录：趋势对比与短板判定都以「每学年的 week1」"
            "为锚点（Ruling 140），无锚点则整批人只能走 Z0，分布断言会静默退化成"
            "「全员 insufficient_data」"
        )
    curr_date = week1[0]
    prev_date = week1[1] if len(week1) > 1 else None

    curr_by_student = {
        record.student_no: record for record in fitness
        if dt.date.fromisoformat(record.tested_on) == curr_date
    }
    prev_by_student = (
        {} if prev_date is None else {
            record.student_no: record for record in fitness
            if dt.date.fromisoformat(record.tested_on) == prev_date
        }
    )
    # 体成分：每人取 <= 锚点日的最新一条（样本单位是学生，Ruling 121）
    body_by_student: dict[str, RawBodyCompRecord] = {}
    for record in body_comp:
        measured_on = dt.date.fromisoformat(record.measured_on)
        if measured_on > curr_date:
            continue
        current = body_by_student.get(record.student_no)
        if current is None or measured_on >= dt.date.fromisoformat(current.measured_on):
            body_by_student[record.student_no] = record

    persons: list[PersonInputs] = []
    for person in ds["population"]:
        student_no = person["student_no"]
        sex = Sex(person["sex"])
        age = int(person["age"])
        age_group, prev_age_group = age_group_of(age), age_group_of(age - 1)
        curr = curr_by_student.get(student_no)
        prev = prev_by_student.get(student_no)
        body = body_by_student.get(student_no)
        curr_scores = (
            empty_scores() if curr is None else score_raw(record_dict(curr), sex, age_group, table)
        )
        prev_scores = (
            None if prev is None
            else score_raw(record_dict(prev), sex, prev_age_group, table)
        )
        persons.append(
            PersonInputs(
                student_id=person["student_id"],
                sex=sex,
                age_group=age_group,
                prev_age_group=prev_age_group,
                curr_scores=curr_scores,
                prev_scores=prev_scores,
                curr_total=national_total(curr_scores),
                prev_total=(None if prev_scores is None else national_total(prev_scores)),
                years=YEAR_STEP,
                body_fat_pct=None if body is None else body.body_fat_pct,
                muscle_mass_kg=None if body is None else body.muscle_mass_kg,
                snapshot_muscle_p20=None,   # 占位：快照要整批人算完才存在
                # 身高体重取**评估锚点那一批**（curr）的清洗后读数——与 score_raw 合成
                # BMI 得分用的是同一行，故 input_snapshot 里 "bmi"（原始值）与
                # curr_scores["bmi"]（得分）不可能来自两次不同的测量。本批没有记录时
                # 两列都是 None（→ "bmi" 为 None，绝不当 0，Ruling 21）。
                height_cm=None if curr is None else curr.height_cm,
                weight_kg=None if curr is None else curr.weight_kg,
                snapshot_muscle_p10=None,   # 占位：同上，由 resolve_muscle_lines 回填
            )
        )
    snapshot = cohort_snapshot(persons, table)
    return resolve_muscle_lines(persons, snapshot), snapshot


def stratify_dataset(payload: dict | list) -> StratifyReport:
    """纯内存版分层：**不落库**，供 Task 9 的两条集成测试直接调用（Ruling 5）。

    ``payload`` 是 ``list`` 时按黄金用例输入结构解析，是 ``dict`` 时按
    :func:`app.seed.generate.build_dataset` 的输出结构解析。``results`` 的顺序与
    ``payload`` 的人数顺序一一对应（黄金用例的断言靠 ``zip`` 对齐）。

    其他类型一律 ``TypeError``：静默把未知形状当成空数据集会让分布断言退化成
    「全员 0.0」，那比崩溃更难发现。
    """
    if isinstance(payload, list):
        persons, snapshot = _from_golden_cases(payload)
    elif isinstance(payload, dict):
        persons, snapshot = _from_dataset(payload)
    else:
        raise TypeError(
            f"payload 必须是 list（黄金用例输入）或 dict（build_dataset 输出），"
            f"收到 {type(payload).__name__}"
        )
    results = [
        result_dict(evaluated, stratify(evaluated.derived), snapshot)
        for evaluated in evaluate(persons, snapshot)
    ]
    return StratifyReport(
        results=results,
        distribution=distribution_of(result["label"] for result in results),
    )
