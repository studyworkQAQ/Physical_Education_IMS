"""MockLePaoAdapter：从 ``seed_dir`` 下的四个 CSV 惰性读取原始记录。

这里是 CSV 契约的**读取侧实现**。契约的语义与清单（文件名、列序）都住在
``app/adapters/base.py``（Ruling 36），本模块只 import 那八个常量、不再自己声明一份：
生产方 Task 6 因此不必依赖某个具体实现就能拿到列序。

契约的可执行定义是 ``tests/fixtures/lepao_sample/`` 下的四个迷你夹具与
``tests/adapters/test_contract.py``；语义部分见 ``base.py`` 的模块 docstring。要点：

* 文件名固定：``students.csv``、``fitness.csv``、``body_comp.csv``、``survey.csv``；
  首行为表头，UTF-8（读取用 ``utf-8-sig``，兼容带 BOM 的写法）
* **表头必须与列序完全一致**（逐列比对，含顺序）：``DictReader`` 按名取值会让列序漂移
  静默通过，所以这里不符即抛 ``ValueError``，指出第一处不一致的列号与两边的列名
* **每行的字段数必须等于列数**：``DictReader`` 会把短行用 ``restval=None`` 补齐、把多
  出来的字段塞进 ``row[None]``，两种畸形都不会自己报错，故与表头检查配对显式校验
* 空单元格：``float | None`` 列还原为 ``None``；数据类里声明为 ``str`` 的列原样透传为
  ``""``（契约没给它们 ``None`` 的位置）；``students.csv`` 的 dict 值还原为 ``None``
* 日期列（``tested_on`` / ``measured_on`` / ``filled_on``）在增量过滤时按
  ``date.fromisoformat`` 解析后比较，非零填充或带时间部分一律抛 ``ValueError``
  （Ruling 38，理由见 :func:`_is_after`）
* ``sex`` 列的取值域是 Task 2 的 ``Sex`` 枚举（``male`` / ``female``），非法值抛
  ``ValueError``；dict 里放的是枚举的 ``value`` 字符串而不是枚举成员
* 数值列读到 ``nan`` / ``inf`` 字面量抛 ``ValueError``：``float("nan")`` 解析是成功的，
  而 nan 与任何阈值比较都为假，缺测会伪装成一个「既不低也不高」的幽灵值一路带到分层。
  ``dimensions`` 这个 JSON 列**同样**逐值做有限性检查——``json.loads`` 缺省接受非标准
  字面量 ``NaN``，而 ``json.dumps`` 缺省又写得出来，两头都不报错（Ruling 39）
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
    BODY_COMP_COLUMNS,
    BODY_COMP_FILENAME,
    FITNESS_COLUMNS,
    FITNESS_FILENAME,
    STUDENT_COLUMNS,
    STUDENTS_FILENAME,
    SURVEY_COLUMNS,
    SURVEY_FILENAME,
    DataSourceAdapter,
    RawBodyCompRecord,
    RawFitnessRecord,
    RawSurveyRecord,
)
from app.domain.indicators import Sex

# 数据类里声明为 ``str`` 的列（原样透传，不走数值解析）。**显式点名而不反射
# ``field.type``**：反射依赖注解被求值成对象，一旦 base.py 加上
# ``from __future__ import annotations``，``field.type`` 就变成字符串 ``'str'``，
# ``student_no`` 会掉进 ``_float_cell``——而 ``float("2024010101")`` 是**成功**的
# （实测得 ``2024010101.0``），学号于是静默变成浮点数，没有任何一处会报错。
# 与声明漂移由 test_contract.py 的 ``test_text_column_set_matches_dataclass_declarations``
# 用 ``typing.get_type_hints``（对延迟注解同样成立）钉住。
TEXT_COLUMNS: frozenset[str] = frozenset(
    {
        "student_no",
        "batch_key",
        "tested_on",
        "measured_on",
        "filled_on",
    }
)


def _validated_since(since: str | None) -> dt.date | None:
    """校验增量水位线并解析成 ``date``；``None`` 表示全量。

    用 ``date.fromisoformat`` 校验有两重作用：格式写错时**立刻**抛 ``ValueError``（而不是
    静默退化成「全量」或「空」，那种症状只是「今天没同步到数据」），以及让水位线从一开始
    就是 ``date`` 对象——:func:`_is_after` 两侧因此是同一类型，不必再依赖「记录侧也一定
    是定宽零填充字符串」这个没人保证过的前提。
    """
    if since is None:
        return None
    try:
        return dt.date.fromisoformat(since)
    except (TypeError, ValueError):
        raise ValueError(
            f"since 必须是 ISO 日期串（YYYY-MM-DD）或 None，收到: {since!r}"
        ) from None


def _is_after(
    value: str | None,
    watermark: dt.date | None,
    *,
    source: str,
    line_no: int,
    column: str,
) -> bool:
    """记录日期是否**严格晚于**水位线（排他：恰等于水位线的记录上一次已同步过）。

    两侧都按 ``date`` 比较。原先这里是「规范化后的水位线」比「原始记录日期字符串」的
    字典序，而契约从没要求记录侧零填充，于是三种形状里两种是错的（实测 Python 3.11.1）：

    * ``'2025-9-5' > '2025-10-01'`` 为 ``True``（实际更早）——只会**多抽**，不丢数据；
    * ``'2025-09-04T10:00' > '2025-09-04'`` 为 ``True``（实际同一天）——**破坏排他语义**，
      恰在水位线上的那条记录被永久重复抽取，水位线再也推不过它（Ruling 38）。

    所以记录侧日期解析失败一律抛 ``ValueError``，带文件名、行号与列名。注意
    ``date.fromisoformat`` 接受 ``20250904`` 这类紧凑写法，但**不接受** ``2025-9-5``：
    非零填充在这里是响亮失败，不是「按日历排对」——比静默多抽更容易定位到写错的生产方。

    空日期（``""``）不解析：它排在任何日期之前，在增量拉取里被排除（Task 6 一定会写
    日期，缺日期本身是数据质量问题，归 Task 5 的清洗层与 ``cleaning_log``，抽取阶段不
    代它决定丢弃）。``watermark is None``（全量）时也不解析——全量拉取不需要比较，此时
    日期格式问题原样交给清洗层，避免把 Task 5 该记一条日志的行升级成中断整条管道。
    """
    if watermark is None:
        return True
    text_value = (value or "").strip()
    if not text_value:
        return False
    try:
        record_date = dt.date.fromisoformat(text_value)
    except ValueError:
        raise ValueError(
            f"{source} 第 {line_no} 行 {column} 不是合法的 ISO 日期: {text_value!r}；"
            f"CSV 契约要求零填充的 YYYY-MM-DD 且不带时间部分"
            f"（带 T 后缀会让恰等于水位线的记录被永久重复抽取）"
        ) from None
    return record_date > watermark


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

    本函数只校验「是合法 JSON 对象」，**不校验值的有限性**：``dimensions`` 由
    :func:`_dimension_scores` 逐值转 ``float`` 并检查 ``isfinite``（数据类声明的是
    ``dict[str, float]``），而 ``raw_answers`` 声明为无类型的 ``dict``——它**不在浮点契约
    管辖范围内**，值可以是 int、字符串甚至嵌套结构，故此处有意不做数值检查。后果：写侧
    若在 ``raw_answers`` 里塞一个 ``NaN``，抽取阶段不会拦住，要靠 Task 6 遵守
    ``json.dumps(..., allow_nan=False)``（Ruling 39）与 Task 5 的清洗层兜底。
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

    转完还要查 ``math.isfinite``，理由与数值列一模一样，而且这条路径更隐蔽：
    ``json.loads`` 缺省接受非标准字面量 ``NaN`` / ``Infinity``，``float(nan)`` 也不抛，
    而 ``json.dumps`` 缺省 ``allow_nan=True`` 又写得出来——于是 Task 6 一旦漏了
    ``allow_nan=False``，一个 nan 能原样写盘、原样读回、全程零报错，最后在与任何阈值
    比较时恒为假（Ruling 39 的消费方一侧）。
    """
    scores: dict[str, float] = {}
    for key, value in parsed.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{source} 第 {line_no} 行 {column} 的维度值不是数值: "
                f"{key!r}={value!r}"
            ) from None
        if not math.isfinite(score):
            raise ValueError(
                f"{source} 第 {line_no} 行 {column} 的维度值是非有限值: "
                f"{key!r}={value!r}；JSON 列必须用 allow_nan=False 序列化，"
                f"缺测不得写成 NaN/Infinity"
            )
        scores[str(key)] = score
    return scores


def _check_header(
    path: pathlib.Path, fieldnames: list[str] | None, columns: tuple[str, ...]
) -> None:
    """表头逐列（含顺序）比对；不符即抛 ``ValueError``，指出第一处不一致的列号。

    只比集合不比顺序的话，Task 6 按别的列序写出的文件会在这里静默通过——读出来是对的，
    契约却已经漂移，等到有人用 ``csv.writer`` 按 ``FITNESS_COLUMNS`` 写、用别的工具按
    实际列序读时才会对上不上。表头单元格做 ``strip`` 只为容忍误留的空白，名字与顺序
    仍然要求完全一致。

    除了期望/实际两个完整列表，还要报**第一个不一致的位置与两边的列名**：11 列的
    ``fitness.csv`` 只给两个列表，等于让人用肉眼 diff 两行 11 项的数组找那一处错位。
    """
    actual = tuple((name or "").strip() for name in (fieldnames or ()))
    if actual == columns:
        return
    position = next(
        (i for i, (expected, got) in enumerate(zip(columns, actual)) if expected != got),
        min(len(columns), len(actual)),
    )
    raise ValueError(
        f"{path.name} 表头与 CSV 契约不符：第 {position + 1} 列（下标 {position}）"
        f"期望 {columns[position] if position < len(columns) else '（无此列）'!r}，"
        f"实际 {actual[position] if position < len(actual) else '（缺列）'!r}；"
        f"期望全部 {list(columns)}，实际全部 {list(actual)}；"
        f"列序 = 数据类字段声明顺序，write_csv 必须逐列对齐"
    )


def _check_row_shape(
    path: pathlib.Path,
    line_no: int,
    row: dict[str | None, object],
    columns: tuple[str, ...],
) -> None:
    """每行字段数必须等于列数；不齐即抛 ``ValueError``。

    ``DictReader`` 会**悄悄**吸收两种畸形：短行用 ``restval``（缺省 ``None``）补齐尾部
    列，多出来的字段塞进 ``row[None]``（``restkey``）。方向上是安全的——补出来的是
    ``None``/``""`` 而不是 ``0`` 或 ``nan``，且按名取值不会错位——但一个少写一列的生产方
    会得到「最后一列全为缺测」的数据，症状与真实缺测无法区分。它与表头检查天然成对，
    故一并在此响亮失败。
    """
    missing = [name for name in columns if row.get(name) is None]
    extra = row.get(None)
    if not missing and extra is None:
        return
    actual_count = len(columns) - len(missing) + (len(extra) if extra else 0)
    detail = []
    if missing:
        detail.append(f"缺 {len(missing)} 列 {missing}")
    if extra:
        detail.append(f"多出 {len(extra)} 个字段 {list(extra)}")
    raise ValueError(
        f"{path.name} 第 {line_no} 行字段数与表头不符：期望 {len(columns)} 列，"
        f"实际 {actual_count} 列（{'；'.join(detail)}）"
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
                _check_row_shape(path, reader.line_num, row, columns)
                yield reader.line_num, row

    def _students(self) -> Iterator[dict]:
        for line_no, row in self._read(STUDENTS_FILENAME, STUDENT_COLUMNS):
            values = {key: _optional_text(value) for key, value in row.items()}
            values["sex"] = _sex_cell(
                values["sex"], source=STUDENTS_FILENAME, line_no=line_no
            )
            yield values

    def _fitness(self, watermark: dt.date | None) -> Iterator[RawFitnessRecord]:
        for line_no, row in self._read(FITNESS_FILENAME, FITNESS_COLUMNS):
            if not _is_after(
                row["tested_on"],
                watermark,
                source=FITNESS_FILENAME,
                line_no=line_no,
                column="tested_on",
            ):
                continue
            yield self._build(
                RawFitnessRecord, row, source=FITNESS_FILENAME, line_no=line_no
            )

    def _body_comp(self, watermark: dt.date | None) -> Iterator[RawBodyCompRecord]:
        for line_no, row in self._read(BODY_COMP_FILENAME, BODY_COMP_COLUMNS):
            if not _is_after(
                row["measured_on"],
                watermark,
                source=BODY_COMP_FILENAME,
                line_no=line_no,
                column="measured_on",
            ):
                continue
            yield self._build(
                RawBodyCompRecord, row, source=BODY_COMP_FILENAME, line_no=line_no
            )

    def _survey(self, watermark: dt.date | None) -> Iterator[RawSurveyRecord]:
        for line_no, row in self._read(SURVEY_FILENAME, SURVEY_COLUMNS):
            if not _is_after(
                row["filled_on"],
                watermark,
                source=SURVEY_FILENAME,
                line_no=line_no,
                column="filled_on",
            ):
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
                # raw_answers 声明为无类型 dict，不在浮点契约内（见 _json_object）
                raw_answers=_json_object(
                    row["raw_answers"], column="raw_answers", **context
                ),
            )

    @staticmethod
    def _build(
        cls: type, row: dict[str, str | None], *, source: str, line_no: int
    ):
        """按数据类字段序把一行 CSV 装成记录。

        分派按 :data:`TEXT_COLUMNS` 这份**显式点名**的文本列集合，不反射 ``field.type``：
        反射只在注解被求值成对象时成立，一旦 base.py 加上 ``from __future__ import
        annotations``，``field.type`` 就变成字符串 ``'str'``，``student_no`` 会掉进
        ``_float_cell``——而 ``float("2024010101")`` 是**成功**的（实测得 ``2024010101.0``），
        学号会静默变成浮点数，一处都不报错。显式集合配上一条用 ``typing.get_type_hints``
        的漂移测试即可，无需依赖注解的求值时机。

        只服务 ``RawFitnessRecord`` 与 ``RawBodyCompRecord`` 这两个「``str`` + ``float | None``」
        的数据类；``RawSurveyRecord`` 带 JSON 列与不可缺的 ``total``，单独构造。
        """
        values = {}
        for field in dataclasses.fields(cls):
            raw = row[field.name]
            if field.name in TEXT_COLUMNS:
                values[field.name] = _text_cell(raw)
            else:
                values[field.name] = _float_cell(
                    raw, source=source, line_no=line_no, column=field.name
                )
        return cls(**values)

