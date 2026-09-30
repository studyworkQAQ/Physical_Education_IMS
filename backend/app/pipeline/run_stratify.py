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
    WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, score_item,
)
from app.domain.percentile import (
    MUSCLE_MASS, PercentileRow, compute_snapshot, lines_used, lookup_p20,
    summarize_source,
)
from app.domain.stratify import Layer, StratResult, explain, stratify
from app.domain.tables import StandardTable
from app.pipeline.clean import clean_body_comp, clean_fitness, load_ranges
from app.refdata import DATA_DIR, standard
from app.seed.fitness import COLUMN_BY_ITEM
from app.seed.generate import RANGES_FILENAME

__all__ = [
    "Evaluated",
    "PersonInputs",
    "StratifyReport",
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

    区间表只有 ``data/indicator_ranges.yaml`` 一个真相，文件名从 ``app.seed.generate``
    导入而不是在这里重抄一遍——两处字面量漂移的后果是清洗层静默用不上越界保护，
    而 ``load_ranges`` 的键集合校验只在**它读到的那个文件**上生效。

    **导出而不私有**：``daily.py`` 的 Clean 阶段要用同一份区间表，两处各读一次盘、
    或其中一处自己拼一个路径，都会让「清洗口径只有一个所有者」这句话不成立。
    """
    global _ranges_cache
    if _ranges_cache is None:
        _ranges_cache = load_ranges(pathlib.Path(DATA_DIR) / RANGES_FILENAME)
    return _ranges_cache


@dataclass(frozen=True)
class PersonInputs:
    """一个人在某一次判定里的**全部**输入，即 :func:`app.domain.derive.derive` 的 11 个参数。

    字段顺序与 ``derive`` 的参数顺序一一对应（``age_group`` 在第 9 位——少写一个不会立刻
    ``TypeError``，而是 ``snapshot`` 被当成 ``age_group``、``40.0`` 被当成 ``snapshot``，
    然后在 ``find_weaknesses`` 里以一个看不出所以然的错误炸开）。:func:`evaluate` 因此
    按关键字展开，不按位置传参。

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


def bmi_of(height_cm: float | None, weight_kg: float | None) -> float | None:
    """身高体重 → BMI，口径与生成器（``app.seed.fitness._anthropometrics``）逐字一致。

    ``round(..., 1)`` 是承重的：国标 BMI 档位是区间映射，生成器也算到 1 位小数，
    两侧差 0.05 就可能在档位边界上翻档（进而翻 ``score_bmi``、翻 15% 权重的总分贡献）。
    任一为 ``None``（缺测）时返回 ``None``——**绝不当 0**（Ruling 21）。
    """
    if height_cm is None or weight_kg is None:
        return None
    return round(weight_kg / (height_cm / 100.0) ** 2, 1)


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

    项 → 原始值列名的映射从 ``app.seed.fitness.COLUMN_BY_ITEM`` 导入，**不在这里重抄**：
    它无法从名字推导（``pull_up_or_sit_up`` 对应的是 ``strength_count``），抄错的后果是
    某一项恒为 ``None``、该桶短板静默消失。
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
      同一个人的三次测量当三个样本，实测两种口径的 P20 差 0.2 kg，足以翻十几个人的 ``C``，
      而 green 的容差余量只剩 0.4 个百分点（Ruling 128）。喂的必须是**清洗后**的值
      （缺省注入下存在 ``muscle_mass_kg = 135.0`` 这种越界值，未清洗会把 P20 拉高）。
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
    """按 ``(sex, age_group)`` 从快照回填每人的 ``snapshot_muscle_p20``。

    **两条路径共用这一个回填函数**（内存的 :func:`_from_dataset` 与 DB 的
    ``daily.py``），故不可能一处查表、另一处凭空给值——那正是 Ruling 102 的缺陷形态：
    没有生产者时只能传 ``None``，``muscle_low`` 永不可达、``C`` 退化成只看体脂率，
    **且不报错**。

    查不到（该组肌肉量样本 < ``MIN_SAMPLE``，按 Ruling 121 第 4 步不产出行）时保持
    ``None``：``flag_body_comp`` 的肌肉量那一支于是无从成立，与 ``lookup_p25`` 的
    ``None`` 语义同构（Ruling 21：缺测不当最坏值）。
    """
    return [
        replace(person, snapshot_muscle_p20=lookup_p20(snapshot, person.sex, person.age_group))
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
        "body_fat_pct": person.body_fat_pct,
        "body_fat_limit": derived.body_comp.limit,
        "muscle_mass_kg": person.muscle_mass_kg,
        # None = 该组肌肉量样本 < MIN_SAMPLE、没有 P20 判定线（Ruling 121 第 4 步）。
        # 这是**留痕**：读这一列就能分清「肌肉量够用」与「压根没有这条线」。
        "snapshot_muscle_p20": person.snapshot_muscle_p20,
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

    人数 < 30 也意味着 7 个计分项全部走 ``national_norm`` 兜底（``source = "national"``），
    故这 13 例守卫的是**国标常模判定线**那一路；校内百分位那一路由 500 人的分布测试守卫。
    """
    table = standard()
    persons: list[PersonInputs] = []
    for case in cases:
        sex = Sex(case["sex"])
        age = int(case["age"])
        age_group, prev_age_group = age_group_of(age), age_group_of(age - 1)
        curr_scores = score_raw(case["curr"], sex, age_group, table)
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
    :func:`national_total` 对 7 个计分项**全有或全无**；``build_dataset`` 缺省注入 4% 逐项
    缺测，故单条记录完整的概率约 ``0.96^7 = 75.1%``、两条同时完整约 ``56.4%``——实测
    ``291/500 = 58.2%`` 可判、``209/500 = 41.8%`` 不可判，与推算吻合。

    **真正的不变量是「可判子集上的高一致率」，不是「分布逐类相等」**：那 291 人里有 280 人
    （96.2%）与生成器的 ``trend_label`` 一致；11 处分歧全部可由「某个单项缺测被清成
    ``None`` → 该项 delta 退出计数、加权和下降」解释，是正确行为。钉住这三段数字的是
    ``tests/integration/test_golden_cases.py`` 的
    ``test_trend_agrees_with_the_generator_oracle_on_the_decidable_subset``（硬规矩 #17：
    裁定必须同时写出「哪一条测试会因违反它而变红」）。
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
