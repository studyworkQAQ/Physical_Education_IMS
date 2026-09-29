"""清洗管道：把适配器的原始记录转成可评分的干净记录，并为每一条被剔除/被修正的数据留痕。

**本模块只有一个职责**——转换 + 留痕。不碰数据库（落库是 Task 10 的事）、不评分、
不分层、不生成处方。清洗结果与审计条目一起返回给调用方，由调用方决定怎么持久化。

**为什么这一层是承重的（Ruling 21）**
``score_item`` 对低侧越界做夹取，而「越小越好」的项（50 米跑、1000 米跑）低值意味着高分：
实测 ``score_item(T, SPRINT_50M, 0.0, MALE, G)`` 与 ``DISTANCE_RUN`` 的 ``0.0`` 都返回
**100 分**。``0`` 是数值列最常见的缺测占位（NOT NULL 默认值、解析失败回退、导入时把空
单元格填 0），而这两项各占国标 20% 权重——一个零填充的 50 米成绩若走到 ``score_item``，
等于**给体能最差的学生送上 40% 权重的满分，并同时抹掉速度耐力与耐力两个桶的短板**，
全程不抛异常、不留痕。它比高侧越界更危险，因为它抬分而不是压分，不会被「这成绩怎么
这么低」的直觉发现。所以 :data:`FieldRange.non_positive_is_missing` 为真的字段上，
``<= 0`` **不是**「夹取到区间下界」，而是转 ``None`` 记 ``missing_dropped``。

**为什么不能一刀切拒绝 ``<= 0``**
``strength_count = 0``（引体向上做不起一个）与 ``sit_and_reach_cm = -1.3``（国标本就有
负值档）都是合法真实值。处置只能按字段配置，这就是 ``data/indicator_ranges.yaml``
存在的理由。

**日期列不在清洗范围内**：Ruling 41 已让适配器无条件校验并归一化 ``tested_on`` /
``measured_on``，本模块收到的一定是合法的零填充 ``YYYY-MM-DD`` 字符串，原样透传，
不做缺失/异常/量纲处理。

**两类记录级处置**（Ruling 47/48）：学号为空或全空白的记录**整条剔除**——无法归属到任何人
的记录既不能入库也不能参与任何计算；两类记录都去重（体测按 ``(student_no, batch_key)``、
体成分按 ``(student_no, measured_on)``）并保留输入顺序中靠后的一行，**绝不取均值**：两条
测量的平均值是一个从未被测量过的数。去重条目的 ``field`` 写 :data:`WHOLE_RECORD`（它不对应
任何单列），空学号条目的 ``field`` 写 ``student_no``（缺的正是这一列），两者的 ``reason``
都明写「整条记录」被丢弃，与「某一列缺测、记录仍在」的字段级条目一眼可分。
"""
import pathlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields, replace
from typing import TypeVar

import yaml

from app.adapters.base import RawBodyCompRecord, RawFitnessRecord
from app.db.models import CleaningLog

# 两类原始记录在「剔除无法归属 → 去重」这一段里完全同构（都有 student_no 与一个日期/批次
# 列），用受约束的 TypeVar 让 :func:`_dedup` 的返回类型跟着入参走，而不是退化成 Any。
_RecordT = TypeVar("_RecordT", RawFitnessRecord, RawBodyCompRecord)

# ``kind`` 的四个取值逐字来自 ORM 的 ``CleaningLog.KINDS``（Task 3 已建 CHECK 约束
# ck_cleaning_log_kind）。在此只写一次、由 :class:`CleaningEntry` 构造时校验，而不是在
# 每个记录点重抄字符串：两处漂移只会在 Task 10 落库时被约束拒绝，错误现场离真正的原因
# 隔了五个任务，而审计条目已经在内存里攒了一整批。
KIND_MISSING = "missing_dropped"
KIND_OUTLIER = "outlier_corrected"
KIND_UNIT = "unit_normalized"
KIND_DUPLICATE = "duplicate_removed"

# dropped / corrected 的口径（计划只声明了这两个计数字段、没给定义，由控制方裁定）：
# dropped 只数 missing_dropped；corrected 数 outlier_corrected 与 unit_normalized 之和；
# duplicate_removed **两个计数都不进**——被去掉的是一整条重复行，活下来的那一行本身
# 完好无损，既没丢值也没改值。Task 10 要把这两个数写进 daily_sync_run 的
# dropped_count / corrected_count，口径含糊就等于报表口径含糊。
_CORRECTED_KINDS = frozenset({KIND_OUTLIER, KIND_UNIT})

# 记录级条目（重复行去除）不对应任何单个字段名，用星号通配占位。CleaningLog.field 是
# String(32) 且无 CHECK 约束，星号能原样落库，并在审计界面里一眼可辨「不是某一列的问题」。
# 导出为模块常量（Ruling 50）：字面量只在本行出现一次，调用点一律引用常量，避免同一个
# 魔法值散落在几处、改一处漏一处。
WHOLE_RECORD = "*"

# 学号 / 批次 / 日期列不是测量值，不进 ranges 表。测量字段清单从两个数据类的字段声明序
# 推导，不手抄第二份真相（与 base.py 的 FITNESS_COLUMNS 同一手法）：将来给记录加一列，
# load_ranges 会立刻因为「ranges 文件漏了一个字段」而响亮报错，而不是让新列裸奔。
_IDENTITY_FIELDS = frozenset({"student_no", "batch_key", "tested_on", "measured_on"})

FITNESS_MEASURE_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(RawFitnessRecord) if f.name not in _IDENTITY_FIELDS
)
BODY_COMP_MEASURE_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(RawBodyCompRecord) if f.name not in _IDENTITY_FIELDS
)
# 两者的并集只被 load_ranges 用来做键集合校验，外部没有消费方，故取私有名——与同为
# 加载期内部细节的 _RANGE_KEYS 保持一致的可见性（导出一个没人 import 的名字只是让
# 模块的公共表面看起来比实际更大，将来改它还要考虑向后兼容）。
# FITNESS_MEASURE_FIELDS / BODY_COMP_MEASURE_FIELDS 保持导出：Task 10 落库与架构测试
# 都可能要「哪些列是测量列」这份清单。
_KNOWN_MEASURE_FIELDS: frozenset[str] = (
    frozenset(FITNESS_MEASURE_FIELDS) | frozenset(BODY_COMP_MEASURE_FIELDS)
)

_RANGE_KEYS = ("min", "max", "non_positive_is_missing", "zero_allowed")


@dataclass(frozen=True)
class FieldRange:
    """一个测量字段的合理区间与「非正值是否算缺测」的处置策略。

    ``non_positive_is_missing`` 为真时 ``<= 0`` 一律视为缺测占位（转 ``None``），此时
    ``zero_allowed`` 必须为假——两者矛盾意味着「0 既是缺测又是真实值」，:func:`load_ranges`
    会拒绝这样的配置。

    ``zero_allowed`` 为真且 ``non_positive_is_missing`` 为假时，``0`` 是合法真实值
    （引体向上 0 次），负值是否合法改由 ``min`` 决定：``min >= 0`` 的计数字段上负数不可能
    出现，只能来自「未测」哨兵，故判为缺测；``min < 0`` 的字段（坐位体前屈下界 −15）负值
    合法，真越界交给夹取逻辑。

    ``zero_allowed`` 为真时 ``min`` **必须 <= 0**（Ruling 51）：声明「0 是真实值」却让 0
    落在区间外，等于让 0 先被放行、再被夹取到 ``min``，:func:`load_ranges` 拒绝这种配置。
    """

    min: float
    max: float
    non_positive_is_missing: bool
    zero_allowed: bool


@dataclass
class CleaningEntry:
    """一条「这个值为什么被动过」的交代（spec §4.6）。

    字段名与 ORM :class:`CleaningLog` 的列名逐字对齐（Ruling 46），Task 10 可以直接按
    名字落库，不需要一层易错的手工映射。``student_id`` 不在这里：它是可空外键，只有学号
    能解析到 ``student`` 表时才填，解析是 Task 10 的职责（Ruling 25 的双列设计正是为了
    让孤儿学号的审计记录也能落库）。

    ``reason`` 必须是**具体到能看懂的中文句子**：这张表存在的意义是项目结题、发论文、
    被审稿人追问「这条数据为什么没了」时能逐条回答，一句笼统的「数据异常」等于没交代。
    """

    student_no: str
    field: str
    original_value: object
    processed_value: object
    kind: str
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in CleaningLog.KINDS:
            raise ValueError(
                f"CleaningEntry.kind 非法: {self.kind!r}；合法值必须与 "
                f"CleaningLog.KINDS 逐字相同: {sorted(CleaningLog.KINDS)}"
            )


@dataclass
class CleanResult:
    """一次清洗的产出：干净记录 + 审计条目 + 两个计数。

    ``clean_fitness`` 只填 ``fitness``、``clean_body_comp`` 只填 ``body_comp``，另一个
    列表为空——两类记录共用一个结果类型，Task 10 的一次同步可以把两个结果直接串起来。
    ``dropped`` / ``corrected`` 的口径见 :data:`_CORRECTED_KINDS` 处的说明。
    """

    fitness: list[RawFitnessRecord]
    body_comp: list[RawBodyCompRecord]
    entries: list[CleaningEntry]
    dropped: int
    corrected: int


def load_ranges(path: pathlib.Path) -> dict[str, FieldRange]:
    """读取 ``indicator_ranges.yaml``，返回「测量字段名 → :class:`FieldRange`」。

    YAML 结构是**每字段一个映射**（``{min, max, non_positive_is_missing, zero_allowed}``），
    不是一个二元列表（Ruling 45：原计划的 ``dict[str, tuple[float, float]]`` 与「每字段
    两个属性」的要求自相矛盾，已更正）。

    键集合必须与两个原始记录数据类的测量字段**完全一致**：多一个键说明字段名拼错或列已
    改名，少一个键说明那个字段的越界/缺测保护被静默摘掉——后者正是本模块要防的失效模式
    （一个拼错的 ``vital_capacty_ml`` 会让肺活量裸奔，而任何地方都不报错）。两种情况都抛
    带文件路径与 offending 键名的 ``ValueError``。

    属性值同样严格校验类型：``bool`` 是 ``int`` 的子类，故先排除布尔再判数值，否则
    ``min: true`` 会被当成 ``1`` 静默通过。两种自相矛盾的组合也在这里拒绝（见
    :func:`_parse_range`）：``non_positive_is_missing`` 与 ``zero_allowed`` 同时为真，
    以及 ``zero_allowed`` 为真而 ``min > 0``（Ruling 51）。
    """
    ranges_path = pathlib.Path(path)
    if not ranges_path.is_file():
        raise FileNotFoundError(f"指标合理区间表缺失: {ranges_path}")
    raw = yaml.safe_load(ranges_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"{ranges_path} 的顶层结构应为「字段名 → 属性映射」，"
            f"实际是 {type(raw).__name__}"
        )
    known = _KNOWN_MEASURE_FIELDS
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(
            f"{ranges_path} 含有不是测量字段的键: {unknown}；"
            f"合法字段名: {sorted(known)}"
        )
    omitted = sorted(known - set(raw))
    if omitted:
        raise ValueError(
            f"{ranges_path} 漏掉了这些测量字段: {omitted}；"
            f"漏写等于让该字段的越界/缺测保护静默失效"
        )
    return {name: _parse_range(ranges_path, name, raw[name]) for name in sorted(raw)}


def _parse_range(path: pathlib.Path, name: str, raw: object) -> FieldRange:
    """把一个字段的 YAML 映射解析成 :class:`FieldRange`，任何形状不对都响亮失败。"""
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path} 的 {name} 应是一个含 {list(_RANGE_KEYS)} 四个键的映射，实际是 {raw!r}"
        )
    absent = [key for key in _RANGE_KEYS if key not in raw]
    if absent:
        raise ValueError(
            f"{path} 的 {name} 缺少键: {absent}；应有 {list(_RANGE_KEYS)} 四个键"
        )
    for key in ("non_positive_is_missing", "zero_allowed"):
        if not isinstance(raw[key], bool):
            raise ValueError(
                f"{path} 的 {name}.{key} 应为布尔值 true/false，实际是 {raw[key]!r}"
            )
    for key in ("min", "max"):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"{path} 的 {name}.{key} 应为数值，实际是 {value!r}"
            )
    if raw["min"] > raw["max"]:
        raise ValueError(
            f"{path} 的 {name} 区间上下界颠倒: min={raw['min']} > max={raw['max']}"
        )
    if raw["non_positive_is_missing"] and raw["zero_allowed"]:
        raise ValueError(
            f"{path} 的 {name} 配置自相矛盾: non_positive_is_missing 为 true"
            f"（<=0 一律视为缺测）时 zero_allowed 必须为 false"
        )
    # Ruling 51：``zero_allowed`` 声明「0 是合法真实值」，那就必须让 0 落在合法区间内。
    # 否则 :func:`_placeholder_reason` 把 0 放行（它相信这个声明），紧接着越界夹取又把它
    # 夹到 ``min`` 并记 ``outlier_corrected``——一次「配置手误」就把缺测占位变成了区间下界，
    # 而对「越小越好」的项（50 米跑 / 耐力跑）下界值经 score_item 的低侧夹取就是 100 分。
    # 实测：把 sprint_50m_s 改成 {min: 5.0, non_positive_is_missing: false, zero_allowed: true}
    # 后，clean_fitness(sprint_50m_s=0.0) 返回 5.0，score_item 返回 100。
    # 这只能在加载期拦：``_clean_measure`` 拿到的已经是 FieldRange，无从判断它自身是否自洽，
    # 而 ranges 文件是专家手工维护的知识资产，load_ranges 是唯一能拦下坏改动的地方。
    if raw["zero_allowed"] and raw["min"] > 0:
        raise ValueError(
            f"{path} 的 {name} 配置自相矛盾: zero_allowed 为 true 时 min 必须 <= 0，"
            f"否则 0 会被夹取到 {raw['min']}——对「越小越好」的项等于把缺测占位送成满分"
        )
    return FieldRange(
        min=float(raw["min"]),
        max=float(raw["max"]),
        non_positive_is_missing=raw["non_positive_is_missing"],
        zero_allowed=raw["zero_allowed"],
    )


def normalize_height(cm: float | None) -> tuple[float | None, CleaningEntry | None]:
    """身高量纲启发式：``0 < cm < 3`` 判定为按米录入，×100 归一为厘米并留痕。

    **单参数**（Ruling 45 更正）：米制启发式是身高专有的，不需要 ranges 表。

    ``cm <= 0`` 在这里**不处理**，原样返回：``<= 0 → None`` 是所有测量字段共用的通用
    规则，由 :func:`clean_fitness` 在归一化之后按 ``FieldRange.non_positive_is_missing``
    统一施加，不在此重复（重复意味着同一处置有两个所有者，改一处漏一处）。因此
    ``normalize_height(0.0)`` 返回 ``(0.0, None)``，由清洗主流程转成 ``None`` 并记
    ``missing_dropped``。

    返回的条目 ``student_no`` 为空串：本函数按 Ruling 45 是单参数的，拿不到记录身份，
    学号由 :func:`clean_fitness` 在收条目时补齐，故空学号的条目不会出现在任何
    :class:`CleanResult` 里。

    **结果舍入到 1 位小数**（Ruling 49）：身高实测精度就是 0.1 cm，而 ``cm * 100`` 会留下
    浮点残渣——实测 ``2.01 * 100 == 200.99999999999997``、``1.417 * 100 ==
    141.70000000000002``（裁定举例的 ``1.68`` 在 CPython 下恰好无残渣，``1.68 * 100 ==
    168.0``，但那只是运气）。身高经 BMI 参与国标计分，Ruling 18 的就低取档在档位边界上
    理论上可能被 1e-14 级误差翻档，舍入把这一整类风险免费消掉。
    """
    if cm is None:
        return None, None
    if 0 < cm < 3:
        normalized = round(cm * 100, 1)
        return normalized, CleaningEntry(
            student_no="",
            field="height_cm",
            original_value=cm,
            processed_value=normalized,
            kind=KIND_UNIT,
            reason=(
                f"身高原始值 {cm} 落在 (0, 3) 内，判定为按「米」录入的量纲错误，"
                f"×100 归一为 {normalized} 厘米"
            ),
        )
    return cm, None


def clean_fitness(
    records: Iterable[RawFitnessRecord], ranges: dict[str, FieldRange]
) -> CleanResult:
    """清洗一批体测记录：剔除无法归属的记录 → 去重 → 身高校正量纲 → 逐字段处置缺测/越界。

    **空学号在去重之前剔除**（Ruling 47）：没有学号的记录无法归属，连去重键都不该参与——
    若让它进去，所有空学号记录会在 ``("", batch_key)`` 上互相碰撞，把两个不同学生的数据
    当成重复合并掉，还记下一条描述不存在事实的 ``duplicate_removed``。

    **先去重再清洗**，顺序是有意的：若先清洗再去重，被丢弃那条重复行产生的修正条目会
    留在审计里，描述的却是一条没进结果的记录——审计于是指向不存在的数据，比没有审计更糟。

    去重键是 ``(student_no, batch_key)``，**保留输入顺序中靠后的那一条**（后到达的覆盖
    先到达的）：同一批次的重复行通常来自水位线未推进或源系统重传，后一条更接近源头最新
    状态。保留行**就地替换**原位置，不打乱批次内的记录顺序。

    越界的值夹取到最近的区间边界并记 ``outlier_corrected``，**整条记录保留**——丢弃整行
    会让该生其余有效项一起消失，队列静默缩水，而 spec 要的是「能交代每一条被动过的数据」
    而不是「把有问题的学生删掉」。唯一的例外是上面的空学号：那种记录根本没有「该生」。
    """
    survivors, entries = _dedup(
        records,
        key_of=lambda r: (r.student_no, r.batch_key),
        entry_of=lambda discarded, kept: CleaningEntry(
            student_no=kept.student_no,
            field=WHOLE_RECORD,
            original_value=discarded.tested_on,
            processed_value=kept.tested_on,
            kind=KIND_DUPLICATE,
            reason=(
                f"学号 {kept.student_no} 在批次 {kept.batch_key} 上出现多条体测记录，"
                f"保留输入顺序中靠后的一条（tested_on={kept.tested_on}），"
                f"丢弃靠前的一条（tested_on={discarded.tested_on}）；"
                f"同批次重复通常来自增量水位线未推进或源系统重传"
            ),
        ),
    )

    cleaned: list[RawFitnessRecord] = []
    for record in survivors:
        values: dict[str, float | None] = {
            name: getattr(record, name) for name in FITNESS_MEASURE_FIELDS
        }
        height, unit_entry = normalize_height(values["height_cm"])
        if unit_entry is not None:
            entries.append(replace(unit_entry, student_no=record.student_no))
        values["height_cm"] = height
        for name in FITNESS_MEASURE_FIELDS:
            values[name], field_entries = _clean_measure(
                record.student_no, name, values[name], ranges[name]
            )
            entries.extend(field_entries)
        cleaned.append(replace(record, **values))
    dropped, corrected = _tally(entries)
    return CleanResult(
        fitness=cleaned, body_comp=[], entries=entries, dropped=dropped, corrected=corrected
    )


def clean_body_comp(
    records: Iterable[RawBodyCompRecord], ranges: dict[str, FieldRange]
) -> CleanResult:
    """清洗一批体成分记录：剔除无法归属的记录 → 去重 → 逐字段处置缺测/越界。

    字段级规则与 :func:`clean_fitness` 完全一致，记录级处置同样一致（Ruling 47/48）。

    **去重键 ``(student_no, measured_on)``、保留输入顺序中靠后的一行**：``body_composition``
    上有 ``UniqueConstraint("student_id", "measured_on")``（Ruling 24），不去重会让 Task 10
    的 ``repo.upsert`` **静默覆盖**先前那一行且不留任何痕迹，与体测路径的留痕行为不一致。

    **绝不取均值**：两条测量的平均值是一个**从未被测量过的数**，属于 Ruling 21/34 一脉相承
    禁止的凭空捏造。「靠后」指的是**输入顺序**而不是日期（Ruling 52）：本函数没有实现
    「取最新一次测量」这个口径，审计文字也不得声称它——同一种行为在体测与体成分两条路径上
    必须用同一套说法，否则研究者按其中一份去理解另一份时必然读错。

    注：去重键的一半就是 ``measured_on``，故本函数记下的 ``duplicate_removed`` 条目里两个
    值列必然是同一个日期——它们只能告诉你「哪一天撞了」，不像体测那样能区分两个不同的
    ``tested_on``。要定位具体是哪两行，得回到源 CSV 按学号 + 日期查。
    """
    survivors, entries = _dedup(
        records,
        key_of=lambda r: (r.student_no, r.measured_on),
        entry_of=lambda discarded, kept: CleaningEntry(
            student_no=kept.student_no,
            field=WHOLE_RECORD,
            original_value=discarded.measured_on,
            processed_value=kept.measured_on,
            kind=KIND_DUPLICATE,
            reason=(
                f"学号 {kept.student_no} 在测量日 {kept.measured_on} 上出现多条体成分记录，"
                f"保留输入顺序中靠后的一条、丢弃靠前的一条；绝不取均值——两条测量的平均值"
                f"是一个从未被测量过的数。"
                f"不去重会让落库变成 (student_id, measured_on) 唯一约束下的静默覆盖，无痕可查"
            ),
        ),
    )

    cleaned: list[RawBodyCompRecord] = []
    for record in survivors:
        values: dict[str, float | None] = {}
        for name in BODY_COMP_MEASURE_FIELDS:
            values[name], field_entries = _clean_measure(
                record.student_no, name, getattr(record, name), ranges[name]
            )
            entries.extend(field_entries)
        cleaned.append(replace(record, **values))
    dropped, corrected = _tally(entries)
    return CleanResult(
        fitness=[], body_comp=cleaned, entries=entries, dropped=dropped, corrected=corrected
    )


def _dedup(
    records: Iterable[_RecordT],
    key_of: Callable[[_RecordT], tuple[str, str]],
    entry_of: Callable[[_RecordT, _RecordT], CleaningEntry],
) -> tuple[list[_RecordT], list[CleaningEntry]]:
    """剔除无法归属的记录 → 按 ``key_of`` 去重，返回 ``(存活行, 记录级审计条目)``。

    两类记录共用这一段（Ruling 47/48），差异只有三处、全部由参数注入：去重键的第二列
    （体测 ``batch_key`` / 体成分 ``measured_on``）、条目里两个值列放哪个日期、以及
    ``reason`` 的文字。``entry_of(discarded, kept)`` 的顺序固定为「被丢弃行在前、保留行在后」。

    **抽出来不是为了少写几行**：复制粘贴两份的直接后果是像 Ruling 52 那样的措辞更正必须
    做两遍，漏掉一处就得到两条行为一致、审计文字却互相矛盾的代码路径，而 ``cleaning_log``
    的读者无从判断哪一份才是真的。

    两条顺序都是承重的：

    - **空学号先于去重**（Ruling 47）：没有学号的记录连去重键都不该参与，否则所有空学号
      记录会在 ``("", key)`` 上互相碰撞，把两个不同学生的数据当成重复合并掉，还记下一条
      描述不存在事实的 ``duplicate_removed``。
    - **去重先于字段级清洗**（由调用方保证：本函数返回后才开始清洗）：若先清洗再去重，
      被丢弃那条重复行产生的修正条目会留在审计里，描述的却是一条没进结果的记录——审计
      于是指向不存在的数据，比没有审计更糟。

    保留**输入顺序中靠后**的一行，就地替换原位置（不打乱批次内顺序），**绝不取均值**：
    两条测量的平均值是一个从未被测量过的数。注意「靠后」是输入顺序而非日期——体测的去重
    键不含 ``tested_on``，故胜出行的日期未必更晚；``reason`` 只能如实印出两个日期，不得
    声称「取最新」（Ruling 52）。
    """
    entries: list[CleaningEntry] = []
    survivors: list[_RecordT] = []
    position_of: dict[tuple[str, str], int] = {}
    for record in records:
        unattributable = _unattributable_entry(record.student_no)
        if unattributable is not None:
            entries.append(unattributable)
            continue
        key = key_of(record)
        if key not in position_of:
            position_of[key] = len(survivors)
            survivors.append(record)
            continue
        position = position_of[key]
        entries.append(entry_of(survivors[position], record))
        survivors[position] = record
    return survivors, entries


def _unattributable_entry(student_no: str) -> CleaningEntry | None:
    """学号为空或全空白时返回「整条记录已剔除」的审计条目，否则返回 ``None``（Ruling 47）。

    没有学号的记录**无法归属到任何人**：``cleaning_log.student_id`` 解析不出来，
    ``fitness_test`` / ``body_composition`` 的外键也无处可指；队列、分层、处方全部以
    「这个学生」为单位，一条无主的记录既不能入库也不能参与任何计算。所以处置是**整条剔除**，
    而不是把学号置空后继续往下走。

    ``kind`` 仍取 ``missing_dropped``，**不新增第五个 kind**：「缺失的标识导致整条记录被
    剔除」在语义上仍是缺测剔除，``field`` 列已足以指明缺的是哪一项；新增取值会牵动 Task 3
    已建的 CHECK 约束 ``ck_cleaning_log_kind``。``original_value`` 存**收到的原始字符串**，
    让 ``""``（空单元格）与 ``"   "``（只含空白的脏值）在审计里可区分——两者的上游成因不同，
    前者多半是漏填，后者多半是解析或对齐错误。

    ``reason`` 必须明写「整条记录」被丢弃：读 ``cleaning_log`` 的研究者要能分清「这项测量
    缺席，记录仍在」与「整条记录被丢掉了」，两者对样本量的影响完全不同。
    """
    if student_no.strip():
        return None
    return CleaningEntry(
        student_no=student_no,
        field="student_no",
        original_value=student_no,
        processed_value=None,
        kind=KIND_MISSING,
        reason=(
            f"student_no 为空或全空白（原始值 {student_no!r}），整条记录无法归属到任何学生，"
            f"已整条剔除：既不入库，也不参与队列、分层与处方的任何计算。"
            f"请与字段级缺测区分——那种情形整条记录仍在结果里、只有该列为空，"
            f"而这里被丢弃的是整条记录本身"
        ),
    )


def _clean_measure(
    student_no: str, field: str, value: float | None, fr: FieldRange
) -> tuple[float | None, list[CleaningEntry]]:
    """处置单个测量值，返回 (干净值, 审计条目)。

    三段判定，顺序即优先级：缺测（``None`` 或占位值）→ 越界夹取 → 原样通过。
    **缺测优先于越界**是本模块的核心：``sprint_50m_s = 0.0`` 既「越界」又是占位，若先判
    越界就会被夹成 5.0 秒，再经 ``score_item`` 低侧夹取拿到 100 分。
    """
    if value is None:
        return None, [
            CleaningEntry(
                student_no=student_no,
                field=field,
                original_value=None,
                processed_value=None,
                kind=KIND_MISSING,
                reason=(
                    f"{field} 在原始记录中为空（未测、仪器无读数或导入时丢失），"
                    f"按缺测处理保留空值；绝不填 0——0 会被 score_item 当成真实成绩夹取计分"
                ),
            )
        ]
    reason = _placeholder_reason(field, value, fr)
    if reason is not None:
        return None, [
            CleaningEntry(
                student_no=student_no,
                field=field,
                original_value=value,
                processed_value=None,
                kind=KIND_MISSING,
                reason=reason,
            )
        ]
    if value < fr.min or value > fr.max:
        bound = fr.min if value < fr.min else fr.max
        return bound, [
            CleaningEntry(
                student_no=student_no,
                field=field,
                original_value=value,
                processed_value=bound,
                kind=KIND_OUTLIER,
                reason=(
                    f"{field}={value} 超出该指标的合理区间 [{fr.min}, {fr.max}]，"
                    f"夹取到最近的区间边界 {bound}；只修正这一列，"
                    f"该生本条记录的其余有效项原样保留"
                ),
            )
        ]
    return value, []


def _placeholder_reason(field: str, value: float, fr: FieldRange) -> str | None:
    """``value`` 是缺测占位而非真实读数时返回中文理由，否则返回 ``None``（Ruling 21）。

    只看 ``value <= 0``：正值的越界由 :func:`_clean_measure` 的夹取逻辑处置，与本函数
    无关。三种「非正值算缺测」的情形分别由 ``non_positive_is_missing``、``zero_allowed``
    与 ``min`` 裁定，判据见 :class:`FieldRange` 的 docstring。
    """
    if value > 0:
        return None
    if fr.non_positive_is_missing:
        return (
            f"{field}={value} 不是该指标可能出现的真实读数（合理区间 [{fr.min}, {fr.max}]，"
            f"且非正值一律视为缺测）：0 与负数是数值列最常见的缺测占位——NOT NULL 默认值、"
            f"解析失败回退、导入时把空单元格填 0。判为缺测转空值，不夹取到区间下界："
            f"对「越小越好」的项（50 米跑、耐力跑），下界值会经 score_item 的低侧夹取拿到"
            f"满分，一个缺测项反而给体能最差的学生送上 20% 权重的满分并抹掉该桶短板"
        )
    if value == 0:
        if fr.zero_allowed:
            return None
        return (
            f"{field} 收到 0，而该指标的配置不接受 0 作为真实读数"
            f"（合理区间 [{fr.min}, {fr.max}]），判为缺测占位转空值"
        )
    if fr.min >= 0:
        return (
            f"{field}={value} 为负数，而该指标下界为 {fr.min}（0 是合法真实值，"
            f"如引体向上做不起一个记 0 次）：负数不可能出现，只能来自「未测」哨兵值，"
            f"判为缺测转空值；夹取到 {fr.min} 会伪造一条该生确实测过且成绩为 {fr.min} 的记录"
        )
    return None


def _tally(entries: Iterable[CleaningEntry]) -> tuple[int, int]:
    """按 :data:`_CORRECTED_KINDS` 处的口径统计 ``(dropped, corrected)``。"""
    dropped = sum(1 for entry in entries if entry.kind == KIND_MISSING)
    corrected = sum(1 for entry in entries if entry.kind in _CORRECTED_KINDS)
    return dropped, corrected
