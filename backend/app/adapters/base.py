"""数据源适配器契约：三个原始记录数据类、抽象基类、CSV 契约清单，以及 ``batch_key``
的唯一读写处。

本模块只声明「上游数据源必须提供什么形状的数据」，不含任何实现知识：不 open 文件、
不发请求、不碰数据库、不读时钟。依赖方向是 ``pipeline → adapters``（spec §3.3），
所以这里既不 import ``app.db``，也不 import ``app.pipeline``；只有 ``mock_lepao`` 与
``http_lepao`` 两个实现依赖它。

**CSV 契约的语义与清单都在此定义**（Ruling 36）：文件名与列序常量原先住在读取侧实现
``mock_lepao.py``，于是生产方 Task 6 为了拿到列序得 ``from app.adapters.mock_lepao
import FITNESS_COLUMNS``——**依赖一个具体实现只为取得契约**。现在八个常量都住这里，
三个数据类文件的列序仍由 ``dataclasses.fields()`` 推导（不手抄第二份真相）：

1. 列序 = 对应数据类的字段声明顺序，首行为表头，UTF-8 编码。
2. 空值写为空字符串（不是 ``None``、不是 ``nan``），读取时还原为 ``None``。
   **这条是承重的**：Ruling 21 已查明 ``0`` 会经 ``score_item`` 的低侧夹取拿到满分
   ——50 米跑与耐力跑的 0.0 秒都得 100 分。缺测被读成 ``0``，等于给体能最差的学生送上
   20% 权重的满分，还同时抹掉两个桶的短板，而且全程不报错。JSON 列（``dimensions`` /
   ``raw_answers``）序列化必须用 ``json.dumps(..., allow_nan=False)``：缺省的
   ``allow_nan=True`` 会写出非标准字面量 ``NaN``，而 ``json.loads`` 缺省又接受它，
   于是一个 nan 能原样写盘、原样读回、全程零报错（Ruling 39）。读取侧对
   ``dimensions`` 与 ``raw_answers`` **两列都递归遍历**，凡 ``float`` 实例一律查
   ``math.isfinite``，非有限即抛带**键路径**的 ``ValueError``（Ruling 42）：不变式不留
   例外，下游才能整体推理「适配器绝不产出非有限浮点」；``allow_nan=False`` 是生产方
   一侧的纵深防御，不是替代。``int`` / ``str`` / ``bool`` / ``None`` / 嵌套容器都是
   ``raw_answers`` 的合法内容，原样透传。
3. ``since`` 是 ISO 日期串（``YYYY-MM-DD``），**排他**过滤（``> since``）；``None``
   表示全量。日期恰等于 ``since`` 的记录属于「上一次已经同步过」，不再返回。
   **记录侧的日期列必须是零填充的 ``YYYY-MM-DD``，且不带时间部分**（Ruling 38）：
   ``2025-9-5``、``2025-09-04T10:00`` 都不合法。带 ``T`` 后缀尤其致命——它会让「恰等于
   水位线」变成「晚于水位线」，那条记录于是被永久重复抽取，水位线再也推不过它。
   读取侧实现**无条件强制校验并归一化**（Ruling 41）：不论调用方传没传 ``since``，
   ``tested_on`` / ``measured_on`` / ``filled_on`` 都解析成 ``date`` 后以零填充
   ``YYYY-MM-DD`` 放进记录（紧凑写法 ``20250904`` 归一为 ``2025-09-04``），解析失败
   （含空格子）即抛带文件名 + 行号 + 列名的 ``ValueError``。校验不得是调用模式的副作用，
   文档本身也不算兜底。按 Ruling 40 **不加宽容解析层**——非零填充日期一律响亮失败，
   格式归一化属于「知道自己源格式」的那个具体适配器（将来 ``http_lepao.py`` 自己的
   边界），不进两个实现共享的路径。
4. ``batch_key`` 形如 ``"<academic_year>|<timepoint>"``，只由 :func:`parse_batch_key`
   解析、只由 :func:`make_batch_key` 构造——格式只能有一个所有者，读写两侧都成立
   （Ruling 35）。
"""
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class RawFitnessRecord:
    """一次体测的原始记录（清洗前）；字段声明序即 ``fitness.csv`` 的列序。

    ``student_no`` / ``batch_key`` / ``tested_on`` 声明为 ``str``：契约没给它们 ``None``
    的位置，因此空单元格原样透传为 ``""``，由 Task 5 的清洗层判定并留痕——缺学号的记录
    本身就是最该被看见的数据质量问题，不该在抽取阶段被静默丢掉。

    ``tested_on``（Ruling 33）有两个用途：Task 10 据它查找或创建 ``fitness_test_batch``
    行，它同时是 :meth:`DataSourceAdapter.fetch_fitness` 的增量水位线字段。

    八个测量列是 ``float | None``，``None`` 是契约里唯一合法的缺失表达，绝不能用 ``0``
    或 ``nan`` 代替（理由见模块 docstring 第 2 条）。注意 ``strength_count`` 的 ``0``
    是**合法真实值**（引体向上 0 次），与缺测不是一回事。
    """

    student_no: str
    batch_key: str
    tested_on: str
    height_cm: float | None
    weight_kg: float | None
    vital_capacity_ml: float | None
    sprint_50m_s: float | None
    sit_and_reach_cm: float | None
    standing_jump_cm: float | None
    strength_count: float | None
    distance_run_s: float | None


@dataclass(frozen=True)
class RawBodyCompRecord:
    """一次体成分测量的原始记录；字段声明序即 ``body_comp.csv`` 的列序。

    ``measured_on`` 既是 :meth:`DataSourceAdapter.fetch_body_comp` 的增量水位线字段，
    也是 ``body_composition`` 表 ``(student_id, measured_on)`` 唯一约束的一半。
    """

    student_no: str
    measured_on: str
    muscle_mass_kg: float | None
    body_fat_pct: float | None
    smi: float | None


@dataclass(frozen=True)
class RawSurveyRecord:
    """一份兴趣问卷的原始记录；字段声明序即 ``survey.csv`` 的列序。

    后三列**必填**：``dimensions`` 与 ``raw_answers`` 各序列化为一个 JSON 字符串列，
    缺失时写 ``{}`` 而不是空字符串——``dict`` 字段没有 ``None`` 的位置，把空格悄悄读成
    ``{}`` 会让「问卷没有维度」与「问卷没填」在下游变成同一件事，而 spec §10.9 的
    5 维度正是兴趣画像的全部内容。
    """

    student_no: str
    filled_on: str
    total: float
    dimensions: dict[str, float]
    raw_answers: dict


# ---------------------------------------------------------------------------
# CSV 契约清单（Ruling 36）：生产方（Task 6 的 write_csv）与读取方共用同一份常量
# ---------------------------------------------------------------------------

STUDENTS_FILENAME = "students.csv"
FITNESS_FILENAME = "fitness.csv"
BODY_COMP_FILENAME = "body_comp.csv"
SURVEY_FILENAME = "survey.csv"

# 列序 = 数据类字段声明顺序：从数据类推导，格式变更时只改本文件一处
FITNESS_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(RawFitnessRecord))
BODY_COMP_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(RawBodyCompRecord))
SURVEY_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(RawSurveyRecord))
# students.csv 的列与 app/db/models.py 的 Student 业务列一一对应（不含自增 id）；
# 它没有对应数据类（``fetch_students`` 产出 dict），故在此显式声明
STUDENT_COLUMNS: tuple[str, ...] = (
    "student_no",
    "name",
    "sex",
    "birth",
    "department",
    "grade",
)


class DataSourceAdapter(ABC):
    """上游数据源的只读契约：四个 ``fetch_*`` 一律返回**惰性迭代器**。

    惰性是契约的一部分，不只是省内存：Task 10 的 ``extract`` 会把整批记录直接交给
    Task 5 的清洗层，先攒成 list 再返回会让「500 人 × 两学年 × 三时点」在内存里同时
    存在两份。实现方因此必须是生成器（契约测试直接断言 ``types.GeneratorType``）。

    ``since`` 的排他语义见模块 docstring 第 3 条。实现方应在**调用时**就校验水位线格式
    而不是等到第一次取值：水位线来自持久化状态，格式写错若静默退化成「全量」或「空」，
    症状只是「今天没同步到数据」，不报错。
    """

    @abstractmethod
    def fetch_students(self, since: str | None) -> Iterator[dict]:
        """学生名册，产出以 ``students.csv`` 表头为键的 dict（空单元格值为 ``None``）。

        **不支持增量**（Ruling 33）：``since`` 非 ``None`` 时同样返回全量。第一批里这个
        方法只属于契约、不被任何管道阶段消费——原型阶段的组织结构由 Task 6 的
        ``seed_database`` 建立，Task 10 的
        ``test_organization_data_never_flows_through_adapter`` 钉住「管道不得经适配器
        插入学生」。这是 spec §3.4「骨架先行」的有意安排，不是待删的死代码。
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_fitness(self, since: str | None) -> Iterator[RawFitnessRecord]:
        """体测记录，按 :attr:`RawFitnessRecord.tested_on` 做排他增量过滤。"""
        raise NotImplementedError

    @abstractmethod
    def fetch_body_comp(self, since: str | None) -> Iterator[RawBodyCompRecord]:
        """体成分记录，按 :attr:`RawBodyCompRecord.measured_on` 做排他增量过滤。"""
        raise NotImplementedError

    @abstractmethod
    def fetch_survey(self, since: str | None) -> Iterator[RawSurveyRecord]:
        """兴趣问卷，按 :attr:`RawSurveyRecord.filled_on` 做排他增量过滤。"""
        raise NotImplementedError


BATCH_KEY_SEPARATOR = "|"
# 时点取值域与 app/db/models.py 的 ``FitnessTestBatch.TIMEPOINTS`` 是同一组值。这里不
# 反向 import db（依赖方向是 db ← services / pipeline，adapters 不碰 db），故各写一份；
# db 侧另有 CHECK 约束兜底，两处一旦漂移会在入库时响亮报错，不会静默。
TIMEPOINTS: frozenset[str] = frozenset({"week1", "week8", "week16"})
_ACADEMIC_YEAR = re.compile(r"\d{4}-\d{4}")


def parse_batch_key(key: str) -> tuple[str, str]:
    """``"<academic_year>|<timepoint>"`` → ``(academic_year, timepoint)``。

    **``batch_key`` 格式只能有一个所有者**（Ruling 33）：Task 10 要拿学年与时点去查找或
    创建 ``fitness_test_batch`` 行，必须走这里，不得自己 ``split("|")``——第二处解析意味着
    格式变更时要同时改两个地方，而漏改的那一处不会报错，只会把整批记录挂到错误的批次上。

    格式非法一律抛 ``ValueError`` 并带上原值：缺分隔符、分隔符多于一个、学年不是
    「四位-四位」、时点不在 :data:`TIMEPOINTS` 域内，都属于**生产方写错了**。静默返回
    半截键（如 ``("2025-2026week1", "")``）会让下游建出一个 timepoint 为空的批次行，
    随后 ``ck_fitness_test_batch_timepoint`` 才报错，错误现场离真正的原因隔了两层。
    """
    parts = key.split(BATCH_KEY_SEPARATOR)
    if len(parts) != 2:
        raise ValueError(
            f"batch_key 格式非法: {key!r}；应为 "
            f'"<academic_year>{BATCH_KEY_SEPARATOR}<timepoint>"，如 "2025-2026|week1"'
        )
    academic_year, timepoint = parts
    if not _ACADEMIC_YEAR.fullmatch(academic_year):
        raise ValueError(
            f"batch_key 的学年部分非法: {academic_year!r}（来自 {key!r}）；应形如 "
            f'"2025-2026"，即「四位-四位」'
        )
    if timepoint not in TIMEPOINTS:
        raise ValueError(
            f"batch_key 的时点部分非法: {timepoint!r}（来自 {key!r}）；"
            f"合法值: {sorted(TIMEPOINTS)}"
        )
    return academic_year, timepoint


def make_batch_key(academic_year: str, timepoint: str) -> str:
    """``(academic_year, timepoint)`` → ``"<academic_year>|<timepoint>"``。

    :func:`parse_batch_key` 的**严格逆函数**（Ruling 35）：写侧（Task 6 的 ``write_csv``）
    必须用它构造 ``batch_key``，不得手拼 ``f"{academic_year}|{timepoint}"``。在此之前
    「格式只有一个所有者」只对读侧成立——写侧要拿分隔符，还得从读取侧实现
    ``mock_lepao`` 甚至 ``base`` 里 import 常量再自己拼，第二处拼接点同样会漂移。

    与 :func:`parse_batch_key` 一样在**构造时**就校验：学年必须形如「四位-四位」，时点
    必须在 :data:`TIMEPOINTS` 域内，否则抛 ``ValueError`` 并带上原值。早炸的意义在于
    错误现场就是写错的那一行；放它过去，畸形键会一路写进 CSV、被读回、直到 Task 10 调
    ``parse_batch_key`` 或 ``ck_fitness_test_batch_timepoint`` 才报错，隔了两三层。
    """
    if not isinstance(academic_year, str) or not _ACADEMIC_YEAR.fullmatch(academic_year):
        raise ValueError(
            f"academic_year 非法: {academic_year!r}；应形如 "
            f'"2025-2026"，即「四位-四位」，且不含分隔符 {BATCH_KEY_SEPARATOR!r}'
        )
    if not isinstance(timepoint, str) or timepoint not in TIMEPOINTS:
        raise ValueError(
            f"timepoint 非法: {timepoint!r}；合法值: {sorted(TIMEPOINTS)}"
        )
    return f"{academic_year}{BATCH_KEY_SEPARATOR}{timepoint}"

