"""仿真数据集的装配、脏数据注入、CSV 落盘、组织结构入库与 CLI。

本模块是 ``app.seed`` 的**唯一编排者**：五个生成器（人口学、编班、体测、体成分、问卷）
各自只管一件事、各自接收调用方传入的 ``rng``，而**全项目只有一个随机数入口**——
:func:`_organisation` 里那一句 ``np.random.default_rng(cfg.seed)``。它的状态被依次交给
每一个生成器，所以「同一个 seed 产出字节级一致的数据集」不是靠纪律维持的，而是结构上
就没有第二个随机源可用（``tests/seed`` 里有一条源码级守卫钉住这一点）。

**职责边界（承重）**
:func:`seed_database` **只**写组织结构五张表（semester / teacher / student /
course_section / enrollment）。体测、体成分、问卷必须经 ``MockLePaoAdapter`` 与
Task 5 的清洗管道流入数据库——直接入库会绕过清洗与幂等，Task 10 的管道测试于是再也
测不到真实路径，而「原始数据 → 清洗留痕 → 评分 → 分层」这条链恰恰是本项目的研究主体。

**CSV 契约只有一个所有者**
文件名与列序一律从 :mod:`app.adapters.base` 导入（Ruling 36），``batch_key`` 一律用
:func:`app.adapters.base.make_batch_key` 构造（Ruling 35），日期一律零填充
``YYYY-MM-DD`` 且不带时间部分（Ruling 38），JSON 列一律
``json.dumps(..., ensure_ascii=False, allow_nan=False)``（Ruling 39）。
**``students.csv`` 有意不产出**（Ruling 37）：``fetch_students`` 在本批只属于契约、
不被任何管道阶段消费，组织结构由 :func:`seed_database` 建立；``MockLePaoAdapter``
对缺失文件 yield 空，故不写它不会崩。
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib

import numpy as np
from sqlalchemy.orm import Session

from app.adapters import base
from app.db import models, repo
from app.db.session import engine, init_db
from app.pipeline.clean import (
    BODY_COMP_MEASURE_FIELDS,
    FITNESS_MEASURE_FIELDS,
    WHOLE_RECORD,
    FieldRange,
    load_ranges,
)
from app.refdata import DATA_DIR
from app.seed.body_comp import make_body_comp
from app.seed.config import (
    SEMESTERS,
    SeedConfig,
    current_semester,
    semester_end_date,
)
from app.seed.fitness import latent_profiles, make_fitness_tests
from app.seed.population import make_population
from app.seed.sections import make_sections, make_teachers
from app.seed.survey import make_survey

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CSV_DIR = BACKEND_DIR / "data" / "seed"
DEFAULT_DB_URL = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"
RANGES_FILENAME = "indicator_ranges.yaml"

# 注入痕迹挂在记录上的私有键。build_dataset 会把它**摘下来**汇总成顶层的 dirty_marks，
# 故最终数据集里的记录不含此键——这一点是承重的：duplicate 注入要求两行逐字相同
# （Ruling 52），若其中一行多带一个痕迹键，两行就不再相同，清洗层「保留输入顺序中靠后
# 的一条」也就会留下一条与它的前身不一致的记录。
DIRTY_MARKS_KEY = "_dirty_marks"

# 三类源各自的「记录身份列」。同时用它来**从记录的形状推断源**，于是 inject_dirty
# 不必多收一个 source 参数、简报里的三参数签名可以逐字保留。
# 用元组而不是字典：匹配顺序是契约的一部分，元组让这一点在类型上就是显然的。
ROW_KEY_BY_SOURCE: tuple[tuple[str, str], ...] = (
    ("fitness", "batch_key"),
    ("body_comp", "measured_on"),
    ("survey", "filled_on"),
)
# missing / outlier / unit_error 只允许作用于**测量列**（Ruling 44）。清单从清洗层
# 推导（它自己又是从两个原始记录数据类的字段声明序推导的），故这里既没有手抄第二份，
# 也不可能把日期列或标识列写进来。
MEASURE_COLUMNS_BY_SOURCE: dict[str, tuple[str, ...]] = {
    "fitness": FITNESS_MEASURE_FIELDS,
    "body_comp": BODY_COMP_MEASURE_FIELDS,
}
# 清洗层唯一认得的量纲错误：身高按「米」录入（normalize_height 识别 0 < cm < 3 后 ×100）。
# 别的列没有量纲启发式，注入了也不会被认出来，只会变成一条越界异常值——那是在伪造
# 「清洗层修好了一类它根本不会修的错误」，故 unit_error 只落在 height_cm 上。
UNIT_ERROR_COLUMN = "height_cm"
UNIT_ERROR_DIVISOR = 100.0
OUTLIER_FACTOR = 1.5

_ranges_cache: dict[str, FieldRange] | None = None


def _ranges() -> dict[str, FieldRange]:
    """:func:`app.pipeline.clean.load_ranges` 的进程内单例（与 ``refdata.standard()`` 同法）。

    注入异常值需要知道每个字段的合理上限，而那份上限只有 ``indicator_ranges.yaml``
    一个真相；自己写死一份魔数意味着 yaml 一改、注入值就可能落回合理区间内，
    ``outlier`` 于是静默退化成「什么都没发生」，而 ``dirty_marks`` 仍然声称注入过了。
    """
    global _ranges_cache
    if _ranges_cache is None:
        _ranges_cache = load_ranges(DATA_DIR / RANGES_FILENAME)
    return _ranges_cache


def _organisation(
    cfg: SeedConfig,
) -> tuple[list[dict], dict[int, dict[str, float]], dict[str, list[dict]], np.random.Generator]:
    """生成组织结构，返回 ``(population, latents, sections, rng)``。

    :func:`build_dataset` 与 :func:`seed_database` 共用这一段，两侧看到的
    ``student_id`` / ``section_id`` 因此必然对得上——若各自跑一遍生成流程，任何一处
    顺序调整都会让入库的学生与 CSV 里的学号静默错位。

    返回 ``rng`` 不是泄漏内部状态，而是**契约**：它此刻的状态就是「组织结构已生成完」
    之后的状态，``build_dataset`` 接着用它生成三类学期数据，随机序列因此与
    ``seed_database`` 走的是同一条前缀。
    """
    rng = np.random.default_rng(cfg.seed)
    population = make_population(cfg, rng)
    latents = latent_profiles(population, cfg, rng)
    sections = make_sections(population, cfg, rng, latents)
    return population, latents, sections, rng


def inject_dirty(
    records: list[dict], cfg: SeedConfig, rng: np.random.Generator
) -> list[dict]:
    """按 ``cfg.dirty`` 的比例注入四类脏数据，返回**新列表**（输入行不被改动）。

    四类注入的落点各不相同，这不是随意的：

    * ``missing``：把该测量单元格置成 ``None``（写盘即空字符串）。**不用 ``0`` 或负数**
      ——``0`` 在 ``non_positive_is_missing`` 为真的字段上确实也会被清洗层判成缺测，
      但在 ``strength_count``（0 次是合法真实值）与 ``sit_and_reach_cm``（国标本就有
      负值档）上，``0`` 与负数是**真实数据**，注入它们等于伪造一个清洗层本该放行的值。
    * ``outlier``：把值抬到合理区间上限的 1.5 倍。**只往上抬、不往下压**：往下压对
      ``strength_count``（下界 0、``zero_allowed``）会落进清洗层的「负数只能来自未测
      哨兵」分支，产出一条 ``missing_dropped`` 而不是 ``outlier_corrected``——注入的
      种类于是取决于字段配置，``dirty_marks`` 与 ``cleaning_log`` 的交叉验证就对不上了。
      一条规则、零例外，比「按字段分别判断该往哪边压」可靠得多。
    * ``unit_error``：只作用于 :data:`UNIT_ERROR_COLUMN`，把厘米改成米。
    * ``duplicate``：把**整行逐字复制**一份追加到列表末尾（Ruling 52）。不改任何字段，
      尤其不改日期：体测去重键是 ``(student_no, batch_key)``，「保留后者」按**输入顺序**
      判定而不是按日期，两行日期不同就会让胜出的可能是较早的那次测量，而
      ``cleaning_log`` 的 ``reason`` 只能如实印出两个日期、无法声称「取最新」。

    ``missing`` / ``outlier`` / ``unit_error`` 的比例按**测量单元格**计，``duplicate``
    按**记录**计。每个单元格恰好消耗一次 ``rng.random()``、每条记录恰好消耗一次，
    与是否真的注入无关——随机数消耗量因此不随 ``cfg.dirty`` 变化，换一组注入比例不会
    把后面所有数据的取值一起推走。

    每处注入在**被改动的那一行**上挂一条痕迹（键 :data:`DIRTY_MARKS_KEY`），
    由 :func:`build_dataset` 摘下来汇总成顶层的 ``dirty_marks``。痕迹字段名与
    ``CleaningEntry`` 对齐（``student_no`` / ``field`` / ``original_value`` /
    ``processed_value`` / ``kind`` / ``reason``），另加 ``source`` 与 ``row_key``
    两个定位列；``kind`` 用的是**注入侧**的名字（missing / outlier / unit_error /
    duplicate），不是清洗侧的 ``missing_dropped`` 那一套——两者是「我做了什么」与
    「清洗层判定成什么」，交叉验证要的正是它们的对应关系。
    """
    ranges = _ranges()
    outlier_rate = cfg.dirty["outlier"]
    missing_rate = cfg.dirty["missing"]
    duplicate_rate = cfg.dirty["duplicate"]
    output: list[dict] = []
    copies: list[dict] = []
    for record in records:
        row = dict(record)
        source, row_key_column = _locate(row)
        marks: list[dict] = []
        for column in MEASURE_COLUMNS_BY_SOURCE.get(source, ()):
            unit_rate = cfg.dirty["unit_error"] if column == UNIT_ERROR_COLUMN else 0.0
            draw = rng.random()
            if draw < unit_rate:
                kind = "unit_error"
            elif draw < unit_rate + outlier_rate:
                kind = "outlier"
            elif draw < unit_rate + outlier_rate + missing_rate:
                kind = "missing"
            else:
                continue
            original = row[column]
            injected = _damage(kind, original, ranges[column])
            row[column] = injected
            marks.append(_mark(row, row_key_column, source, column, kind, original, injected))
        if rng.random() < duplicate_rate:
            # 逐字复制**已经注入过其它脏数据的那一行**：两行必须完全相同，
            # 否则清洗层的去重就会留下一条与它前身不一致的记录。
            copies.append(dict(row))
            marks.append(
                _mark(
                    row,
                    row_key_column,
                    source,
                    WHOLE_RECORD,
                    "duplicate",
                    row[row_key_column],
                    row[row_key_column],
                )
            )
        if marks:
            row[DIRTY_MARKS_KEY] = marks
        output.append(row)
    output.extend(copies)
    return output


def _locate(row: dict) -> tuple[str, str]:
    """从记录的形状推断它属于哪一类源，返回 ``(source, 该源的身份列名)``。"""
    for source, row_key_column in ROW_KEY_BY_SOURCE:
        if row_key_column in row:
            return source, row_key_column
    raise ValueError(
        f"无法判定记录属于哪一类源：{sorted(row)} 里没有 "
        f"{[key for _, key in ROW_KEY_BY_SOURCE]} 中的任何一列"
    )


def _damage(kind: str, original: float, field_range: FieldRange) -> float | None:
    """按注入种类算出被污染后的值（``outlier`` 走 :data:`OUTLIER_FACTOR`）。"""
    if kind == "missing":
        return None
    if kind == "unit_error":
        # 保留 3 位小数：厘米 ÷ 100 会留下浮点残渣（175.4 / 100 = 1.7540000000000002），
        # 而 normalize_height 本来就只舍入到 0.1 cm，多出来的位数没有任何含义。
        return round(original / UNIT_ERROR_DIVISOR, 3)
    return round(field_range.max * OUTLIER_FACTOR, 1)


def _mark(
    row: dict,
    row_key_column: str,
    source: str,
    column: str,
    kind: str,
    original: object,
    processed: object,
) -> dict:
    """一条注入痕迹。``reason`` 必须说清「注入了什么、期望清洗层怎么处置它」。"""
    identity = f"学号 {row['student_no']}（{row_key_column}={row[row_key_column]}）"
    if kind == "duplicate":
        reason = (
            f"{identity} 的整行被逐字复制一份追加到文件末尾，模拟增量水位线未推进或"
            f"源系统重传；两行**完全相同**（含 {row_key_column}），故清洗层「保留输入顺序中"
            f"靠后的一条」不存在歧义，期望产出一条 duplicate_removed"
        )
    elif kind == "missing":
        reason = (
            f"{identity} 的 {column} 由 {original} 置空，模拟未测 / 仪器无读数 / 导入丢失，"
            f"期望清洗层判为缺测并产出一条 missing_dropped（绝不填 0）"
        )
    elif kind == "unit_error":
        reason = (
            f"{identity} 的 {column} 由 {original} 厘米改成 {processed} 米，"
            f"模拟按「米」录入的量纲错误，期望 normalize_height 识别后 ×100 归一"
            f"并产出一条 unit_normalized"
        )
    else:
        reason = (
            f"{identity} 的 {column} 由 {original} 改成 {processed}，"
            f"超出该指标合理区间上限，期望清洗层夹取到边界并产出一条 outlier_corrected"
        )
    return {
        "source": source,
        "student_no": row["student_no"],
        "row_key": row[row_key_column],
        "field": column,
        "kind": kind,
        "original_value": original,
        "processed_value": processed,
        "reason": reason,
    }


def build_dataset(cfg: SeedConfig) -> dict[str, list[dict]]:
    """按 ``cfg`` 生成整个数据集。

    返回的键：``population`` / ``course_sections`` / ``enrollments`` / ``fitness`` /
    ``body_comp`` / ``survey`` / ``dirty_marks``。

    调用顺序就是随机数消耗顺序，**不得调整**：三类学期数据先生成完，再依次注入脏数据。
    同一个 ``cfg`` 调用两次得到 ``==`` 相等的结果，这是研究项目的硬要求；换一个 ``seed``
    则必须得到不同的结果。
    """
    population, latents, sections, rng = _organisation(cfg)
    generated = {
        "fitness": make_fitness_tests(population, latents, cfg, rng),
        "body_comp": make_body_comp(population, latents, cfg, rng),
        "survey": make_survey(population, latents, cfg, rng),
    }
    dirty_marks: list[dict] = []
    injected: dict[str, list[dict]] = {}
    for source, records in generated.items():
        rows = inject_dirty(records, cfg, rng)
        injected[source] = rows
        for row in rows:
            dirty_marks.extend(row.pop(DIRTY_MARKS_KEY, ()))
    return {
        "population": population,
        "course_sections": sections["course_sections"],
        "enrollments": sections["enrollments"],
        "fitness": injected["fitness"],
        "body_comp": injected["body_comp"],
        "survey": injected["survey"],
        "dirty_marks": dirty_marks,
    }


def write_csv(ds: dict[str, list[dict]], out_dir: pathlib.Path) -> None:
    """把 ``fitness`` / ``body_comp`` / ``survey`` 三类写成适配器约定的 CSV。

    只写三类，**不写 ``students.csv``**（Ruling 37，理由见模块 docstring）。列序取自
    :mod:`app.adapters.base` 的契约常量，逐列用 ``row[column]`` 取值：生成器漏写一列会
    当场 ``KeyError``，而不是静默产出一个少列的文件让读取侧去猜。

    行结束符固定 ``"\\n"``：``csv.writer`` 的缺省是 ``"\\r\\n"``，那会让同一份数据在
    Windows 与 POSIX 上写出不同的字节，「同种子字节级一致」就只在同一台机器上成立。
    """
    target = pathlib.Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, columns, key in (
        (base.FITNESS_FILENAME, base.FITNESS_COLUMNS, "fitness"),
        (base.BODY_COMP_FILENAME, base.BODY_COMP_COLUMNS, "body_comp"),
        (base.SURVEY_FILENAME, base.SURVEY_COLUMNS, "survey"),
    ):
        with (target / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)
            for row in ds[key]:
                writer.writerow([_cell(row[column]) for column in columns])


def _cell(value: object) -> object:
    """一个 Python 值 → CSV 单元格。

    ``None`` 写成空字符串（契约里唯一合法的缺失表达，**绝不是 ``0`` 或 ``nan``**：
    ``0`` 会经 ``score_item`` 的低侧夹取拿到满分，``nan`` 与任何阈值比较都为假）。
    ``dict`` 走 ``json.dumps(..., ensure_ascii=False, allow_nan=False)``——
    ``allow_nan=False`` 是承重的：缺省的 ``True`` 会写出非标准字面量 ``NaN``，而
    ``json.loads`` 缺省又接受它，于是一个 NaN 能原样写盘、原样读回、全程零报错，
    最后在与任何阈值比较时恒为假（Ruling 39 的生产方一侧）。

    浮点标量另做一次有限性检查：适配器读到 ``nan`` / ``inf`` 会抛带行号的
    ``ValueError``，而在写侧就拦下来，错误现场才是**造出这个值的那一行**，
    而不是几千行之外某个读文件的地方。

    **numpy 标量一律显式转成 Python 标量**（``np.float64`` 是 ``float`` 的子类，故它会进
    上面那个 ``repr`` 分支，而 numpy 2.x 的 ``repr(np.float64(1.5))`` 是
    ``'np.float64(1.5)'``）：那种字符串会原样落进 CSV，适配器 ``float()`` 解析时抛
    ``ValueError`` 并中断整批抽取。生成器目前每一处都包了 ``float(...)``，所以这条缺陷
    尚未触发；在这里转一次，就把「将来漏包一次」从运行时事故变成结构性不可达。
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                f"CSV 契约不接受非有限浮点值 {value!r}：缺测请写 None（落盘为空字符串）"
            )
        return repr(float(value))
    if isinstance(value, np.integer):
        return int(value)
    return value


def seed_database(session: Session, cfg: SeedConfig) -> None:
    """把**组织结构**写进数据库：semester / teacher / student / course_section / enrollment。

    体测、体成分、问卷一律**不写**——它们必须经适配器与清洗管道流入，否则就绕过了
    清洗与幂等（理由见模块 docstring）。

    假设表已经建好（调用方先跑 :func:`app.db.session.init_db`），且**不 commit**：
    事务边界由调用方掌握，「整批失败回滚」才成立——这与 :func:`app.db.repo.upsert`
    的口径一致。

    写入一律走 ``repo.upsert`` 按自然键幂等更新，故重复调用不会翻倍。每写完一类就
    ``flush`` 一次，为的是拿到自增主键给下一类的外键用；顺序是父表在前、子表在后。
    用 ORM 的 ``add`` + ``flush``（而不是 Core ``insert()`` 或裸 SQL）还有一个好处：
    SQLAlchemy 的工作单元会对外键做拓扑排序，父行一定先落——本项目在 SQLite 上打开了
    ``PRAGMA foreign_keys=ON``，顺序写错是会真报错的。
    """
    population, _latents, sections, _rng = _organisation(cfg)

    semesters: dict[str, models.Semester] = {}
    for plan in SEMESTERS:
        semesters[plan.name] = repo.upsert(
            session,
            models.Semester,
            ("name",),
            {
                "name": plan.name,
                "start_date": plan.start_date,
                "end_date": semester_end_date(plan, cfg.weeks),
                "weeks": cfg.weeks,
                "is_current": plan.is_current,
            },
        )
    teachers = {}
    for teacher in make_teachers(cfg):
        teachers[teacher["staff_no"]] = repo.upsert(
            session, models.Teacher, ("staff_no",), dict(teacher)
        )
    session.flush()

    students: dict[int, models.Student] = {}
    for person in population:
        students[person["student_id"]] = repo.upsert(
            session,
            models.Student,
            ("student_no",),
            {
                "student_no": person["student_no"],
                "name": person["name"],
                "sex": person["sex"],
                "birth": dt.date.fromisoformat(person["birth"]),
                "department": person["department"],
                "grade": person["grade"],
            },
        )
    session.flush()

    current_id = semesters[current_semester().name].id
    course_sections: dict[str, models.CourseSection] = {}
    for section in sections["course_sections"]:
        course_sections[section["section_id"]] = repo.upsert(
            session,
            models.CourseSection,
            ("semester_id", "name"),
            {
                "semester_id": current_id,
                "teacher_id": teachers[section["teacher_staff_no"]].id,
                "name": section["name"],
                "schedule_text": section["schedule_text"],
                "grouping_mode": section["grouping_mode"],
            },
        )
    session.flush()

    for enrollment in sections["enrollments"]:
        repo.upsert(
            session,
            models.Enrollment,
            ("semester_id", "student_id", "course_section_id"),
            {
                "semester_id": current_id,
                "student_id": students[enrollment["student_id"]].id,
                "course_section_id": course_sections[enrollment["section_id"]].id,
            },
        )
    session.flush()


def summarize(ds: dict[str, list[dict]]) -> str:
    """CLI 用的控制台摘要：人数、男女比、两学年体测条数、脏数据注入计数。"""
    population = ds["population"]
    males = sum(1 for person in population if person["sex"] == "male")
    total = len(population)
    by_year: dict[str, int] = {}
    for record in ds["fitness"]:
        by_year[record["academic_year"]] = by_year.get(record["academic_year"], 0) + 1
    kinds: dict[str, int] = {}
    for mark in ds["dirty_marks"]:
        kinds[mark["kind"]] = kinds.get(mark["kind"], 0) + 1
    years = "、".join(f"{year} {count} 条" for year, count in sorted(by_year.items()))
    dirty = "、".join(f"{kind} {count}" for kind, count in sorted(kinds.items()))
    return (
        f"人数 {total}（男 {males} / 女 {total - males}，男生占比 {males / total:.3f}）\n"
        f"体测记录 {len(ds['fitness'])} 条：{years}\n"
        f"体成分记录 {len(ds['body_comp'])} 条，问卷 {len(ds['survey'])} 份\n"
        f"教学班 {len(ds['course_sections'])} 个，选课关系 {len(ds['enrollments'])} 条\n"
        f"脏数据注入 {len(ds['dirty_marks'])} 处：{dirty}"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：``python -m app.seed.generate --students 500 --weeks 16 --seed 20250828``。

    缺省行为是「既写盘也入库」：三类 CSV 落到 ``backend/data/seed/``，组织结构写进
    ``backend/pe.db``。``--out-csv DIR`` 只改 CSV 的输出路径，不改入库行为。
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.seed.generate", description="生成高保真仿真数据集并建立组织结构"
    )
    parser.add_argument("--students", type=int, default=500, help="学生人数（缺省 500）")
    parser.add_argument("--weeks", type=int, default=16, help="教学周数（缺省 16）")
    parser.add_argument("--seed", type=int, default=20250828, help="随机种子（缺省 20250828）")
    parser.add_argument(
        "--out-csv",
        type=pathlib.Path,
        default=None,
        help=f"三类 CSV 的输出目录（缺省 {DEFAULT_CSV_DIR}）",
    )
    args = parser.parse_args(argv)
    cfg = SeedConfig(students=args.students, weeks=args.weeks, seed=args.seed)

    ds = build_dataset(cfg)
    out_dir = args.out_csv if args.out_csv is not None else DEFAULT_CSV_DIR
    write_csv(ds, out_dir)

    eng = engine(DEFAULT_DB_URL)
    init_db(eng)
    with Session(eng) as session:
        seed_database(session, cfg)
        session.commit()

    print(f"CSV 已写入 {out_dir}（fitness.csv / body_comp.csv / survey.csv，不含 students.csv）")
    print(f"组织结构已写入 {DEFAULT_DB_URL}")
    print(summarize(ds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
