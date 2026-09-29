"""MockLePaoAdapter：从 ``seed_dir`` 下的四个 CSV 惰性读取原始记录。

这里是 CSV 契约的**读取侧实现**，也是文件名与列序清单的唯一出处（Task 6 的 ``write_csv``
必须与之逐列对齐）：三个数据类文件的列序由 ``dataclasses.fields()`` 直接从
``app/adapters/base.py`` 的数据类推导，不手抄第二份；``students.csv`` 没有对应数据类
（``fetch_students`` 产出 dict），列序在 :data:`STUDENT_COLUMNS` 显式声明。

契约的可执行定义是 ``tests/fixtures/lepao_sample/`` 下的四个迷你夹具与
``tests/adapters/test_contract.py``；语义部分见 ``base.py`` 的模块 docstring。要点：

* 文件名固定：``students.csv``、``fitness.csv``、``body_comp.csv``、``survey.csv``；
  首行为表头，UTF-8（读取用 ``utf-8-sig``，兼容带 BOM 的写法）
* **表头必须与列序完全一致**（逐列比对，含顺序）：``DictReader`` 按名取值会让列序漂移
  静默通过，所以这里不符即抛 ``ValueError`` 并列出期望与实际
* 空单元格：``float | None`` 列还原为 ``None``；数据类里声明为 ``str`` 的列原样透传为
  ``""``（契约没给它们 ``None`` 的位置）；``students.csv`` 的 dict 值还原为 ``None``
* ``sex`` 列的取值域是 Task 2 的 ``Sex`` 枚举（``male`` / ``female``），非法值抛
  ``ValueError``；dict 里放的是枚举的 ``value`` 字符串而不是枚举成员
* 数值列读到 ``nan`` / ``inf`` 字面量抛 ``ValueError``：``float("nan")`` 解析是成功的，
  而 nan 与任何阈值比较都为假，缺测会伪装成一个「既不低也不高」的幽灵值一路带到分层
* 文件不存在（含整个目录不存在）→ yield 空，不抛错。Task 6 的第一版 ``write_csv``
  只写三类 CSV，缺 ``students.csv`` 时管道必须照样能跑
"""
import csv
import dataclasses
import datetime as dt
import json
import math
import pathlib
from collections.abc import Iterator

from app.adapters.base import (
    DataSourceAdapter,
    RawBodyCompRecord,
    RawFitnessRecord,
    RawSurveyRecord,
)
from app.domain.indicators import Sex

STUDENTS_FILENAME = "students.csv"
FITNESS_FILENAME = "fitness.csv"
BODY_COMP_FILENAME = "body_comp.csv"
SURVEY_FILENAME = "survey.csv"

# 列序 = 数据类字段声明顺序：从数据类推导，格式变更时只改 base.py 一处
FITNESS_COLUMNS: tuple[str, ...] = tuple(
    f.name for f in dataclasses.fields(RawFitnessRecord)
)
BODY_COMP_COLUMNS: tuple[str, ...] = tuple(
    f.name for f in dataclasses.fields(RawBodyCompRecord)
)
SURVEY_COLUMNS: tuple[str, ...] = tuple(
    f.name for f in dataclasses.fields(RawSurveyRecord)
)
# students.csv 的列与 app/db/models.py 的 Student 业务列一一对应（不含自增 id）
STUDENT_COLUMNS: tuple[str, ...] = (
    "student_no",
    "name",
    "sex",
    "birth",
    "department",
    "grade",
)


def _validated_since(since: str | None) -> str | None:
    """校验并规范化增量水位线；``None`` 表示全量。

    用 ``date.fromisoformat`` 校验有两重作用：格式写错时**立刻**抛 ``ValueError``（而不是
    静默退化成「全量」或「空」，那种症状只是「今天没同步到数据」），以及把 ``20250910``
    这类合法但非规范的写法归一成 ``YYYY-MM-DD``，好让 :func:`_is_after` 的字典序比较成立。
    """
    if since is None:
        return None
    try:
        return dt.date.fromisoformat(since).isoformat()
    except (TypeError, ValueError):
        raise ValueError(
            f"since 必须是 ISO 日期串（YYYY-MM-DD）或 None，收到: {since!r}"
        ) from None


def _is_after(value: str | None, watermark: str | None) -> bool:
    """记录日期是否**严格晚于**水位线（排他：恰等于水位线的记录上一次已同步过）。

    ISO ``YYYY-MM-DD`` 定宽，字典序即时序，故直接比字符串，不必逐行解析日期——记录侧的
    日期是**原始数据**，格式合法性归 Task 5 的清洗层管，抽取阶段不代它做决定。空日期
    （``""``）排在任何日期之前，因此在增量拉取里会被排除；Task 6 一定会写日期，这里只
    是把行为讲清楚，不为不会发生的情形加特殊分支。
    """
    if watermark is None:
        return True
    return (value or "").strip() > watermark


def _text_cell(raw: str | None) -> str:
    """数据类里声明为 ``str`` 的列：去首尾空白后原样透传，空单元格保留为 ``""``。"""
    return (raw or "").strip()


def _optional_text(raw: str | None) -> str | None:
    """``students.csv`` 的 dict 值：空单元格还原为 ``None``（dict 没有声明类型可依）。"""
    return (raw or "").strip() or None


def _sex_cell(raw: str | None, *, source: str, line_no: int) -> str | None:
    """``sex`` 列按 Task 2 的 :class:`Sex` 枚举校验，产出枚举的**值**（``male``/``female``）。

    校验放在抽取这一侧，是为了让写错的性别值在**它进来的那一行**报错（带文件名与行号），
    而不是等两个 Task 之后 ``Sex("男")`` 在评分调用点抛出一个看不出源头的 ``ValueError``
    ——那时错误现场离写错的文件已经隔了清洗、入库与查表三层。

    产出的是 ``Sex(...).value`` 而不是枚举成员：``fetch_students`` 的返回类型是原始
    ``dict``，而实测（Python 3.11.1）``str(Sex.MALE)`` 与 ``f"{Sex.MALE}"`` 都得到
    ``"Sex.MALE"`` 而不是 ``"male"``——枚举成员一旦混进原始数据，任何一条日志、
    回写或 ``Student.sex = f"{row['sex']}"`` 都会把 ``"Sex.MALE"`` 存进那个
    ``String(8)`` 列（SQLite 不强制长度），错误要等到下一次 ``Sex(...)`` 才炸。

    空单元格仍还原为 ``None``（契约的缺失表达），不代替清洗层决定缺性别该怎么办。
    """
    if raw is None:
        return None
    try:
        return Sex(raw).value
    except ValueError:
        raise ValueError(
            f"{source} 第 {line_no} 行 sex 值非法: {raw!r}；"
            f"合法值: {[s.value for s in Sex]}"
        ) from None


def _float_cell(
    raw: str | None, *, source: str, line_no: int, column: str
) -> float | None:
    """``float | None`` 列：空 → ``None``，非空 → 有限的 ``float``，否则抛 ``ValueError``。

    报错一律带上文件名、行号与列名：夹具与 Task 6 的输出都可能出错，只抛一个裸
    ``ValueError: could not convert string to float`` 会让人从 500 人 × 三时点的 CSV 里
    靠肉眼找那一格。
    """
    text_value = (raw or "").strip()
    if not text_value:
        return None
    try:
        value = float(text_value)
    except ValueError:
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 不是合法数值: {text_value!r}"
        ) from None
    if not math.isfinite(value):
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 是非有限值 {text_value!r}；"
            f"CSV 契约要求缺测写空字符串，不可写 nan/inf"
        )
    return value


def _required_float(
    raw: str | None, *, source: str, line_no: int, column: str
) -> float:
    """不可缺的数值列（``RawSurveyRecord.total``）：空格即契约违规，抛 ``ValueError``。

    这里不能用 0.0 兜底：``total`` 是问卷总分，0 是一个**有意义的最低分**，拿它填缺测
    等于凭空造出一个对体育毫无兴趣的学生。
    """
    value = _float_cell(raw, source=source, line_no=line_no, column=column)
    if value is None:
        raise ValueError(f"{source} 第 {line_no} 行 {column} 为空，但该字段不可缺测")
    return value


def _json_object(
    raw: str | None, *, source: str, line_no: int, column: str
) -> dict:
    """JSON 列（``dimensions`` / ``raw_answers``）：必须是合法 JSON 对象，否则抛错。

    空格子不按「缺失 → None」处理，因为数据类声明的是 ``dict`` 而不是 ``dict | None``：
    契约对缺失的表达是写 ``{}``。把空格悄悄读成 ``{}`` 会让「问卷没有维度」与「问卷没填」
    在下游变成同一件事。
    """
    text_value = (raw or "").strip()
    if not text_value:
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 为空；JSON 列缺失请写 {{}} 而不是空字符串"
        )
    try:
        parsed = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 不是合法 JSON: {exc}"
        ) from None
    if not isinstance(parsed, dict):
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 必须是 JSON 对象，实际是 "
            f"{type(parsed).__name__}"
        )
    return parsed


def _dimension_scores(
    parsed: dict, *, source: str, line_no: int, column: str
) -> dict[str, float]:
    """把 ``dimensions`` 的键值规范成 ``dict[str, float]``（数据类声明的类型）。

    JSON 里的 ``4`` 会解析成 ``int``，不转就会让下游拿到与声明不符的类型——百分位与
    雷达图那类计算混进 int 不会立刻报错，只会在某处 ``isinstance`` 判定上悄悄走岔。
    """
    scores: dict[str, float] = {}
    for key, value in parsed.items():
        try:
            scores[str(key)] = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{source} 第 {line_no} 行 {column} 的维度值不是数值: "
                f"{key!r}={value!r}"
            ) from None
    return scores


def _check_header(
    path: pathlib.Path, fieldnames: list[str] | None, columns: tuple[str, ...]
) -> None:
    """表头逐列（含顺序）比对；不符即抛 ``ValueError`` 并列出期望与实际。

    只比集合不比顺序的话，Task 6 按别的列序写出的文件会在这里静默通过——读出来是对的，
    契约却已经漂移，等到有人用 ``csv.writer`` 按 ``FITNESS_COLUMNS`` 写、用别的工具按
    实际列序读时才会对上不上。表头单元格做 ``strip`` 只为容忍误留的空白，名字与顺序
    仍然要求完全一致。
    """
    actual = tuple((name or "").strip() for name in (fieldnames or ()))
    if actual != columns:
        raise ValueError(
            f"{path.name} 表头与 CSV 契约不符：期望 {list(columns)}，实际 {list(actual)}；"
            f"列序 = 数据类字段声明顺序，write_csv 必须逐列对齐"
        )


class MockLePaoAdapter(DataSourceAdapter):
    """从本地 CSV 夹具读取的适配器实现：Task 6 生成的数据经它进入管道。

    构造时**不做任何 I/O**：目录可能还不存在（Task 6 尚未生成），而契约测试要用同一组
    参数覆盖 Mock 与 HTTP 两个实现，构造阶段抛错会让参数化在收集期就炸。所有读取都在
    第一次取值时发生，目录或文件缺失一律 yield 空。
    """

    def __init__(self, seed_dir: pathlib.Path) -> None:
        self.seed_dir = pathlib.Path(seed_dir)

    # -- 契约方法：一律返回生成器（契约测试断言 types.GeneratorType） ----------

    def fetch_students(self, since: str | None) -> Iterator[dict]:
        """全量名册。``since`` 照旧校验格式，但**不据此过滤**（Ruling 33）。"""
        _validated_since(since)
        return self._students()

    def fetch_fitness(self, since: str | None) -> Iterator[RawFitnessRecord]:
        """按 ``tested_on`` 排他增量拉取体测记录。"""
        return self._fitness(_validated_since(since))

    def fetch_body_comp(self, since: str | None) -> Iterator[RawBodyCompRecord]:
        """按 ``measured_on`` 排他增量拉取体成分记录。"""
        return self._body_comp(_validated_since(since))

    def fetch_survey(self, since: str | None) -> Iterator[RawSurveyRecord]:
        """按 ``filled_on`` 排他增量拉取兴趣问卷。"""
        return self._survey(_validated_since(since))

    # -- 读取实现 ------------------------------------------------------------

    def _read(
        self, filename: str, columns: tuple[str, ...]
    ) -> Iterator[tuple[int, dict[str, str | None]]]:
        """逐行 yield ``(line_num, row)``；文件不存在则一行也不 yield。

        ``line_num`` 取自 ``DictReader``（已从源文件读过的行数），比 ``enumerate`` 准：
        它能正确处理跨行引号字段，报错时指向的才是文件里真实的那一行。
        """
        path = self.seed_dir / filename
        if not path.is_file():
            return
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            _check_header(path, reader.fieldnames, columns)
            for row in reader:
                yield reader.line_num, row

    def _students(self) -> Iterator[dict]:
        for line_no, row in self._read(STUDENTS_FILENAME, STUDENT_COLUMNS):
            values = {key: _optional_text(value) for key, value in row.items()}
            values["sex"] = _sex_cell(
                values["sex"], source=STUDENTS_FILENAME, line_no=line_no
            )
            yield values

    def _fitness(self, watermark: str | None) -> Iterator[RawFitnessRecord]:
        for line_no, row in self._read(FITNESS_FILENAME, FITNESS_COLUMNS):
            if not _is_after(row["tested_on"], watermark):
                continue
            yield self._build(
                RawFitnessRecord, row, source=FITNESS_FILENAME, line_no=line_no
            )

    def _body_comp(self, watermark: str | None) -> Iterator[RawBodyCompRecord]:
        for line_no, row in self._read(BODY_COMP_FILENAME, BODY_COMP_COLUMNS):
            if not _is_after(row["measured_on"], watermark):
                continue
            yield self._build(
                RawBodyCompRecord, row, source=BODY_COMP_FILENAME, line_no=line_no
            )

    def _survey(self, watermark: str | None) -> Iterator[RawSurveyRecord]:
        for line_no, row in self._read(SURVEY_FILENAME, SURVEY_COLUMNS):
            if not _is_after(row["filled_on"], watermark):
                continue
            context = {"source": SURVEY_FILENAME, "line_no": line_no}
            yield RawSurveyRecord(
                student_no=_text_cell(row["student_no"]),
                filled_on=_text_cell(row["filled_on"]),
                total=_required_float(row["total"], column="total", **context),
                dimensions=_dimension_scores(
                    _json_object(row["dimensions"], column="dimensions", **context),
                    column="dimensions",
                    **context,
                ),
                raw_answers=_json_object(
                    row["raw_answers"], column="raw_answers", **context
                ),
            )

    @staticmethod
    def _build(
        cls: type, row: dict[str, str | None], *, source: str, line_no: int
    ):
        """按数据类字段序把一行 CSV 装成记录。

        分派规则也从数据类推导：声明为 ``str`` 的字段原样透传，其余按可缺测数值解析。
        这依赖 base.py **没有** ``from __future__ import annotations``（注解是被求值的
        对象，故 ``field.type is str`` 成立）；若哪天加了那行 import，``field.type`` 会变成
        字符串 ``'str'``，学号一类文本列会走数值解析并**立刻抛 ``ValueError``**，不会静默。

        只服务 ``RawFitnessRecord`` 与 ``RawBodyCompRecord`` 这两个「``str`` + ``float | None``」
        的数据类；``RawSurveyRecord`` 带 JSON 列与不可缺的 ``total``，单独构造。
        """
        values = {}
        for field in dataclasses.fields(cls):
            raw = row[field.name]
            if field.type is str:
                values[field.name] = _text_cell(raw)
            else:
                values[field.name] = _float_cell(
                    raw, source=source, line_no=line_no, column=field.name
                )
        return cls(**values)
