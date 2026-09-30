"""14 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.3、§4.6）。

三条贯穿全表的约定，改动前请先读完：

1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
   声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
   当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
   ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
   ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。

2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
   断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
   约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。

3. **JSON 形态的列一律用 :class:`JsonText`**（八个列，无一例外）。SQLite 没有原生
   JSON，该类型以 ``TEXT`` 为底层、由它自己负责 dumps/loads，调用方拿到手的直接是
   原样的 ``dict`` / ``list`` / 标量，与 domain 层的值对象（如
   ``DerivedResult.annual_change: dict[str, float]``）同构，不必各自再约定一套序列化
   格式——那正是口径漂移的温床。为什么不用 SQLAlchemy 自带的 ``JSON`` 类型，见
   :class:`JsonText` 的 docstring（SQLite 的 NUMERIC 亲和性会改写标量）。

本模块不声明任何 ``relationship``：管道按 ``batch_id`` 批量读写，显式 ``select`` 比
懒加载更可预测，也不会在 Session 关闭后触发意外的延迟查询。
"""
import datetime as dt
import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.session import Base

__all__ = [
    "Semester",
    "Teacher",
    "Student",
    "CourseSection",
    "Enrollment",
    "FitnessTestBatch",
    "FitnessTestResult",
    "BodyComposition",
    "InterestSurvey",
    "PercentileSnapshot",
    "DerivedMetrics",
    "StratificationResult",
    "DailySyncRun",
    "CleaningLog",
]


def _in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint:
    """由类常量集合生成 SQL 层的取值域约束。

    约束文本从集合生成而不是手写第二遍：手写两遍迟早会漂移，而漂移是静默的——
    Python 侧放行的值数据库拒收，或反过来数据库放进了 Python 侧读不懂的值。
    取值按字典序排序，使 DDL 文本稳定可复现（同 seed 同 DDL）。
    """
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(allowed))
    return CheckConstraint(f"{column} IN ({quoted})", name=name)


class JsonText(TypeDecorator):
    """把 Python 的 ``dict`` / ``list`` / 标量以 JSON 文本存进 ``TEXT`` 列。

    **为什么不直接用 SQLAlchemy 自带的 ``JSON`` 类型**：它在 SQLite 上渲染成
    ``JSON``，而 SQLite 的亲和性规则里 ``JSON`` 落到 **NUMERIC** 亲和性——凡「看起来
    像数字」的值会被就地转成原生数值存进去，不再是 JSON 文本。实测（Python 3.11.1 /
    SQLAlchemy 2.1.1 / SQLite；探针 = 建一张只有一个 ``JSON`` 列的表、写四个标量后读
    ``select id, typeof(v), v``）：``0.0`` 与 ``65.0`` **都**落 ``typeof='integer'``、
    读回来是 Python ``int`` ``0`` / ``65``（浮点被降成整型），``65.5`` 与 ``65.0000001``
    才落 ``typeof='real'``——NUMERIC 亲和性把**能无损表示成整数**的实数降成整型、其余留
    ``real``。本段此前印的是「``65.0`` 存成 ``real`` 而非文本」，那与它自己下一句的结论
    相反：真存成 ``real 65.0`` 的话读回仍是 ``65.0``，「原值 65.0 kg」就不会被记成
    「原值 65」——正是**降成整型**才造成失真。这条探针**不在测试网里、不被守卫**
    （本仓没有任何测试用 SQLAlchemy 自带的 ``JSON`` 类型），属历史实测，fix round 3 复跑。
    对 ``cleaning_log`` 这种存标量的审计列，这是实打实的失真，而审计记录的全部价值就在于
    原值不被改写。

    以 ``TEXT`` 为底层类型即绕开亲和性转换，同时保留透明 dumps/loads：调用方拿到手的
    仍是原样的 Python 对象，全库八个 JSON 形态的列共用这一种落法，不必区分「这一列
    要不要自己 ``json.dumps``」——那种不对称正是会被忘掉、且忘掉后静默出错的地方。
    ``ensure_ascii=False`` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。
    ``None`` 存 SQL ``NULL`` 而不是 ``'null'`` 文本，读回也是 ``None``。

    ``cache_ok = True`` 是必需的：缺了它 SQLAlchemy 会对每条用到该列的语句发
    ``SAWarning``（该类型无法生成缓存键），在 ``-W error`` 下直接变成失败。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return None if value is None else json.loads(value)


# ---------------------------------------------------------------------------
# spec §4.1 组织与身份
# ---------------------------------------------------------------------------


class Semester(Base):
    """学期：整条管道的日历骨架，业务日期的合法区间由它的起止日界定。"""

    __tablename__ = "semester"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 学期名同时是 CLI（--semester 2025-2026-1）与幂等键的查找键，故唯一
    name: Mapped[str] = mapped_column(String(32), unique=True)
    start_date: Mapped[dt.date] = mapped_column(Date)
    # **排他**上界（Ruling 174）：学期区间是 ``[start_date, end_date)``，与 range/slice 的
    # 惯例一致，也与 ``app.seed.config.semester_end_date`` 的算式（开学日 + 教学周数）自洽——
    # 16 周 × 7 = 112 天对应的闭区间是 ``2025-09-01..2025-12-21``，而本列存的是
    # ``2025-12-22``。故 ``app.pipeline.backfill`` 的 CLI 把它当闭区间上界用之前必须减一天
    # （换算放在 CLI 层，不改 ``semester_end_date``：Task 6 冻结代码，它的算式本身是对的）。
    # 注意 ``daily._semester_of`` / ``percentile_stage.current_semester_of`` 的区间查询仍是
    # **闭**的（``end_date >= day``）：那两处要的是「包含某个测量日」，而最晚的测量日是
    # ``week16`` = ``end_date - 7 天``，多含的那一天里没有任何数据。
    end_date: Mapped[dt.date] = mapped_column(Date)
    weeks: Mapped[int] = mapped_column(Integer)  # 教学周数，spec 固定 16
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class Teacher(Base):
    """体育教师。工号是与教务系统对接的自然键。"""

    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_no: Mapped[str] = mapped_column(String(32), unique=True)  # 工号
    name: Mapped[str] = mapped_column(String(64))


class Student(Base):
    """学生。``sex`` / ``birth`` / ``grade`` 共同决定该查哪一张国标评分表。"""

    __tablename__ = "student"

    # 取值域与 app/domain/indicators.py 的 Sex 枚举一致（male / female）。这里不
    # import 它：Task 3 的接口约定是「Consumes: 无」，db 层不为一个二元集合引入
    # 跨层依赖。代价是两处需人工同步，已登记在任务报告的关切里。
    SEXES: set[str] = {"male", "female"}

    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True)  # 学号
    name: Mapped[str] = mapped_column(String(64))
    sex: Mapped[str] = mapped_column(String(8))
    birth: Mapped[dt.date] = mapped_column(Date)  # 出生年月；龄组由它折算
    department: Mapped[str | None] = mapped_column(String(64))  # 院系
    grade: Mapped[int] = mapped_column(Integer)  # 年级 1–4

    __table_args__ = (_in_domain("sex", SEXES, "ck_student_sex"),)


class CourseSection(Base):
    """教学班。阶段一的行政班与阶段二的分层班并存，靠 ``grouping_mode`` 区分。"""

    __tablename__ = "course_section"

    # administrative = 阶段一在行政班内分层；stratified = 阶段二跨班重编出来的
    # 提升班 / 强化班 / 拓展班。同一批学生两套编班同时存在，演示时可切换。
    GROUPING_MODES: set[str] = {"administrative", "stratified"}

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
    name: Mapped[str] = mapped_column(String(64))  # 课程名 / 分层班名
    schedule_text: Mapped[str | None] = mapped_column(String(64))  # 上课时间
    grouping_mode: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        _in_domain("grouping_mode", GROUPING_MODES, "ck_course_section_grouping_mode"),
    )


class Enrollment(Base):
    """选课关系，对应厦大「三自主」选课：学期 × 学生 × 教学班。"""

    __tablename__ = "enrollment"

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    course_section_id: Mapped[int] = mapped_column(ForeignKey("course_section.id"))

    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "student_id",
            "course_section_id",
            name="uq_enrollment_semester_student_section",
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.2 学期节点数据（低频，来自乐跑）
# ---------------------------------------------------------------------------


class FitnessTestBatch(Base):
    """一次体测批次。``timepoint`` 是学期内的三个采集节点。"""

    __tablename__ = "fitness_test_batch"

    TIMEPOINTS: set[str] = {"week1", "week8", "week16"}

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    timepoint: Mapped[str] = mapped_column(String(8))
    test_date: Mapped[dt.date] = mapped_column(Date)
    # 下面两项来自源系统、可能整列缺失，故可空（见模块 docstring 的可空性原则）
    source: Mapped[str | None] = mapped_column(String(32))  # 来源系统
    academic_year: Mapped[str | None] = mapped_column(String(16))  # 学年

    __table_args__ = (
        _in_domain("timepoint", TIMEPOINTS, "ck_fitness_test_batch_timepoint"),
    )


class FitnessTestResult(Base):
    """一名学生在某批次里的 8 项原始测量、7 项国标计分项得分、总分与等级。

    8 → 7 → 6 的口径见 spec §4.2：身高与体重合成 BMI 一项计分，故 8 项原始测量对应
    7 个计分项；短板判定又排除 BMI（避免与体成分 ``C`` 重复计数），故只有 6 项进
    ``derived_metrics`` 的 ``W``。得分列名一律是 ``score_`` + ``ScoredItem`` 的值，
    管道可用 ``getattr(row, f"score_{item.value}")`` 逐项取用，不必再维护一张映射表。

    指向体测批次的外键**刻意不叫** ``batch_id`` 而叫 ``test_batch_id``（Ruling 31）：
    本项目里 ``batch_id`` 一词专指「指向 ``daily_sync_run`` 的外键」，也就是
    :func:`app.db.repo.delete_by_batch` 可据以删除的归属键，只有三张派生表才允许拥有
    它。若本表也叫 ``batch_id``，误调 ``delete_by_batch(session, FitnessTestResult,
    sync_run_id)`` 时——``fitness_test_batch.id`` 只有 1/2/3（week1/week8/week16），
    而 ``daily_sync_run.id`` 按业务日递增（一学期 1…112）——凡 ``sync_run_id ∈ {1, 2,
    3}`` 都会匹配上并**静默删掉真实源体测数据**：两列都是 int，外键拦不住（每个值各自
    合法），``AttributeError`` 也拦不住（属性存在）。删源数据比删派生行严重得多——派生
    行重算就回来了，源体测数据删了就是删了。改名后这一脚踩下去是响亮的
    ``AttributeError``，与 ``CleaningLog`` 用 ``sync_run_id`` 的既有设计同一口径。
    """

    __tablename__ = "fitness_test_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 体测批次（week1/week8/week16 的测试事件），不是 daily_sync_run，故不叫 batch_id
    test_batch_id: Mapped[int] = mapped_column(ForeignKey("fitness_test_batch.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))

    # —— 8 项原始测量（乐跑口径）——
    height_cm: Mapped[float | None] = mapped_column(Float)  # 身高
    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
    vital_capacity_ml: Mapped[float | None] = mapped_column(Float)  # 肺活量
    sprint_50m_s: Mapped[float | None] = mapped_column(Float)  # 50 米跑
    sit_and_reach_cm: Mapped[float | None] = mapped_column(Float)  # 坐位体前屈
    standing_jump_cm: Mapped[float | None] = mapped_column(Float)  # 立定跳远
    # 引体向上（男）/ 一分钟仰卧起坐（女）；0 次是合法真实值，只有 NULL 才是缺测
    strength_count: Mapped[float | None] = mapped_column(Float)
    distance_run_s: Mapped[float | None] = mapped_column(Float)  # 1000 米（男）/ 800 米（女）

    # —— 7 项国标计分项得分（0–100，就低取档，Ruling 18）——
    score_bmi: Mapped[int | None] = mapped_column(Integer)
    score_vital_capacity: Mapped[int | None] = mapped_column(Integer)
    score_sprint_50m: Mapped[int | None] = mapped_column(Integer)
    score_sit_and_reach: Mapped[int | None] = mapped_column(Integer)
    score_standing_jump: Mapped[int | None] = mapped_column(Integer)
    score_pull_up_or_sit_up: Mapped[int | None] = mapped_column(Integer)
    score_distance_run: Mapped[int | None] = mapped_column(Integer)

    total_score: Mapped[int | None] = mapped_column(Integer)  # 国标总分（100 分制）
    national_grade: Mapped[str | None] = mapped_column(String(16))  # 国标等级

    # 一名学生在同一次体测事件里只可能有一条成绩（Ruling 24）。注意本表的
    # test_batch_id 指向 fitness_test_batch（week1/week8/week16 的测试事件），与
    # daily_sync_run 无关，故幂等重放不能靠 delete_by_batch 按批清理，只能靠这条业务
    # 键兜底：**没有它**的话，Task 10 重跑同一业务日期时若对源表走裸 insert 而不是
    # repo.upsert，同一名学生同一批次的成绩会静默翻倍（该约束加上之前实测 1 → 2 行、
    # 无任何异常），百分位快照、短板计数与趋势随之全部失真。**加上之后它是响亮的**：
    # fix round 3 复跑（裸 SQL 对同一 (student_id, test_batch_id) 插第二行）得
    # ``sqlite3.IntegrityError: UNIQUE constraint failed: fitness_test_result.test_batch_id,
    # fitness_test_result.student_id``、行数保持 1。故那句「1 → 2 行」是**改前**实测、
    # 现由本约束守卫（守卫断言在 ``tests/db/test_models.py``：约束名与列序被逐字钉住）。
    # 约束显式命名，是为了让报错与将来的迁移脚本能指名道姓地引用它。
    __table_args__ = (
        UniqueConstraint(
            "test_batch_id", "student_id", name="uq_fitness_result_test_batch_student"
        ),
    )


class BodyComposition(Base):
    """体成分测量。骨骼肌指数入库但不参与异常判定（spec §14 待确认 #16）。"""

    __tablename__ = "body_composition"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    measured_on: Mapped[dt.date] = mapped_column(Date)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)  # 肌肉量
    body_fat_pct: Mapped[float | None] = mapped_column(Float)  # 体脂率 %
    smi: Mapped[float | None] = mapped_column(Float)  # 骨骼肌指数
    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
    device: Mapped[str | None] = mapped_column(String(32))  # 测量设备

    # 同一学生同一天只留一条体成分（Ruling 24）。本表没有 batch_id，重放翻倍同样只能
    # 靠这条业务键挡住；一旦重复，C（体成分异常）的判定与异常率都会被同一份读数抬高，
    # 而它不会报错——「异常率莫名偏高」比「异常率莫名偏低」更难被当成数据问题追查。
    __table_args__ = (
        UniqueConstraint(
            "student_id", "measured_on", name="uq_body_composition_student_measured_on"
        ),
    )


class InterestSurvey(Base):
    """体育学习兴趣量表问卷（占位 5 维度 × 5 点李克特，spec §10.9）。"""

    __tablename__ = "interest_survey"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    filled_on: Mapped[dt.date] = mapped_column(Date)
    total_score: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict] = mapped_column(JsonText)  # 各维度分，如 {"运动乐趣": 4.0}
    raw_answers: Mapped[dict] = mapped_column(JsonText)  # 原始答题

    # 同一学生同一学期同一天只留一份问卷（Ruling 24）。三列缺一不可：问卷可按学期
    # 重复发放，只有「学期 + 填写日」一起才定位得到唯一的那一份。重复的问卷会同时
    # 抬高样本量与同一个人的权重，兴趣维度均值随之漂移且不报错。
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "semester_id",
            "filled_on",
            name="uq_interest_survey_student_semester_filled_on",
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.3 派生与分层（可追溯核心）
# ---------------------------------------------------------------------------


class PercentileSnapshot(Base):
    """校内百分位快照。**物化而非实时计算**（spec §4.0）。

    实时算会随人群变动漂移，而研究项目必须能复现任意一天的分层结果。列与 Task 7 的
    ``PercentileRow`` 值对象一一对应，故 ``compute_snapshot`` 的输出可直接落库，
    样本量不足 30 时降级来的国标常模行（``source = "national"``）亦然。

    ``batch_id`` + 五列业务唯一键是它的幂等防线（Ruling 29）。此前本表是**唯一一张
    会被物化、却在库层没有任何幂等机制**的表：既无 ``batch_id``（``delete_by_batch``
    删不到它），也无唯一约束（重放翻倍不报错），只能靠 Task 10 的跨日复用逻辑加一条
    行数断言兜着——那是纪律，不是机制；纪律会被下一次重构悄悄改掉，约束不会。

    唯一键的五个列正是 Task 7 的分组键 ``(sex, age_group, item)`` 再加「哪个学期、
    哪一天」：``compute_snapshot`` 对每个分组最多产出一行（7 个计分项在样本 < 30 时
    整组降级为 ``source = "national"``，不是并存两行；``muscle_mass_kg`` **没有国标
    常模可降级**，样本 < 30 时整组不产出行），故 ``source`` 不必进键，同一组同一天
    也只可能有一行。
    """

    __tablename__ = "percentile_snapshot"

    SOURCES: set[str] = {"school", "national"}

    # 取值域与 ``app/domain/percentile.py`` 的 ``SnapshotMetric`` 一致：7 个国标计分项
    # 加上 ``muscle_mass_kg``（肌肉量）。肌肉量**不是计分项**，故它不在 ``ScoredItem``
    # 里；而 spec §6.3② 的 ``C`` 要用「同龄同性别肌肉量 P20」这条判定线，所以快照表
    # 必须存得下它。此前本列是该表**唯一没有取值域约束**的业务列，也正是「库里存得下、
    # 算不出来」这个缺陷形态的机制来源（Ruling 102/121）。与 ``Student.SEXES`` 同一条
    # 处置：db 层不为一个取值集合引入跨层依赖，代价是两处需人工同步，由
    # ``tests/db/test_models.py`` 的漂移测试钉住。
    ITEMS: set[str] = {
        "bmi",
        "vital_capacity",
        "sprint_50m",
        "sit_and_reach",
        "standing_jump",
        "pull_up_or_sit_up",
        "distance_run",
        "muscle_mass_kg",
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )
    item: Mapped[str] = mapped_column(String(32))  # 指标，取 SnapshotMetric 的值
    sex: Mapped[str] = mapped_column(String(8))
    age_group: Mapped[str] = mapped_column(String(16))  # 国标年级组
    p10: Mapped[float] = mapped_column(Float)
    p20: Mapped[float] = mapped_column(Float)
    p25: Mapped[float] = mapped_column(Float)  # 短板判定线：低于它即显性短板
    p50: Mapped[float] = mapped_column(Float)
    p75: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(8))

    __table_args__ = (
        _in_domain("source", SOURCES, "ck_percentile_snapshot_source"),
        _in_domain("sex", Student.SEXES, "ck_percentile_snapshot_sex"),
        _in_domain("item", ITEMS, "ck_percentile_snapshot_item"),
        UniqueConstraint(
            "semester_id",
            "computed_on",
            "item",
            "sex",
            "age_group",
            name="uq_percentile_snapshot_group_day",
        ),
    )


class DerivedMetrics(Base):
    """派生指标：分层判定的直接输入，也是「逐人可追溯」链条的中间一环。

    ``batch_id`` 指向 ``daily_sync_run``：幂等重放靠它按批删除本表与
    ``stratification_result`` 的旧行（见 :func:`app.db.repo.delete_by_batch`）。
    没有这一列，重跑同一天就只能靠「学生 + 日期」去猜哪些行属于哪一次运行。
    """

    __tablename__ = "derived_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )

    annual_change: Mapped[dict] = mapped_column(JsonText)  # 各指标年均变化率
    # 列宽 **20** 而不是 16（Ruling 144）：``Trend.INSUFFICIENT.value`` =
    # ``"insufficient_data"`` 是 **17** 字符，16 装不下。SQLite 不强制 ``VARCHAR`` 长度，
    # 故它静默存下——而 500 人首批实测就有 209 行（41.8%）写这个 17 字符的值；换任何严格
    # 长度的后端（MySQL / PostgreSQL）会截断成 ``"insufficient_dat"``，读回来
    # ``Trend(...)`` 当场 ``ValueError``，**炸在读侧不在写侧**，离真因隔一整个批处理周期。
    # 取 20 与 ``stratification_result.label`` 对齐：两列存的是同一族 17 字符的值。
    # 守卫见 ``tests/db/test_models.py`` 的列宽遍历测试（硬规矩 #18）。
    trend: Mapped[str] = mapped_column(String(20))  # 趋势标签（Task 8 的 Trend 值）
    weaknesses: Mapped[list] = mapped_column(JsonText)  # 短板列表，元素为 ScoredItem 的值
    weakness_count: Mapped[int] = mapped_column(Integer, default=0)  # W，分母恒为 6
    valid_count: Mapped[int] = mapped_column(Integer, default=0)  # < 4 则本日不分层
    body_comp_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)  # C
    body_comp_reasons: Mapped[list] = mapped_column(JsonText)  # C 的原因；正常时为 []


class StratificationResult(Base):
    """红黄绿分层结果（含 ``insufficient_data``），逐人逐日一条。

    ``hit_rules`` 的语义必须读清楚：它是**本次求值评估过的规则 ID 序列**，逗号分隔
    （如 ``"R1,R2,Y1"``），**最后一项才是命中的那条**——**Z0 闸门 + 7 条分层规则**
    自上而下求值、命中即停，所以最多只可能命中一条。保留已评估但未命中的前缀不是
    冗余：它正是回答「这个学生为什么不是红色层」的证据（spec §4.3 要求的可追溯性），
    也是 ``explain()`` 生成中文文案的依据。

    **前缀的构成（Ruling 132）**：``Z0`` 命中时本列**恰为 ``"Z0"``**、只有这一项
    （闸门未评估任何分层规则）；``Z0`` 未命中时本列是**已评估的 7 条分层规则序列**、
    最后一项即命中者、**不含 ``Z0``**（``"R1,R2,Y1"`` 而不是 ``"Z0,R1,R2,Y1"``）。
    故最长取值是 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20 字符**（7 个两字符 ID + 6 个逗号；
    实测 500 人整批的最大长度就是 20——fix round 3 复跑：把 ``stratify_dataset`` 的 500 人
    产出按 ``,``.join 后量，``max = 20``、长度集合 ``{2, 5, 8, 11, 14, 17, 20}``，七档
    「已评估前缀」逐档都在，最长的那条正是 ``R1,R2,Y1,Y2,Y3,Y4,G1``。**这个 20 不被
    守卫**：``hit_rules`` 列没有取值域 CHECK，故 ``tests/db/test_models.py`` 的列宽遍历
    测试扫不到它；128 的余量靠的是 20 ≪ 128 这个量级差，不是断言），``String(128)`` 充裕。

    **``insufficient_data`` 时 ``hit_rules`` 恰为 ``"Z0"``，任何路径都至少有一项**
    （Ruling 125，**不是空串**）：``explain()`` 按 ``hit_rules[-1]`` 取文案，空串会让
    学生端点开「为什么我没有分层结果」时当场 ``IndexError``——而 ``Z0`` 恰恰是最需要
    向学生解释的那条路径。Task 9 已用变异实证过这一崩溃。

    ``input_snapshot`` 存判定当时的全部输入（W、C、valid_count、趋势、主导素质桶、
    各项得分与所用百分位等），使任一条结果都能离线复算，不必回到当天的原始数据。
    """

    __tablename__ = "stratification_result"

    LABELS: set[str] = {"red", "yellow", "green", "insufficient_data"}
    # ``"none"`` = 本条结果**没有用过任何判定线**（``valid_count = 0``，Z0 闸门直接拦下）。
    # 它不是第三种数据来源，而是「无来源」：若拿 ``"school"`` 去填，教师大屏会说「这个
    # 人的判定线来自校内百分位」，而他根本没有判定线——那是一条凭空造出的可追溯性。
    # ``String(8)`` 够宽（最长的 ``"national"`` 恰 8 字符）。
    PERCENTILE_SOURCES: set[str] = {"school", "national", "none"}

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )
    label: Mapped[str] = mapped_column(String(20))
    hit_rules: Mapped[str] = mapped_column(
        String(128),
        comment="逗号分隔的规则 ID 序列；最后一项为命中者，前缀是已评估但未命中的规则",
    )
    input_snapshot: Mapped[dict] = mapped_column(JsonText)
    # 本条结果**实际用过**的那些判定线行的来源汇总（Ruling 137）：一项都没用过 →
    # ``"none"``；用过 1–3 项（Z0 命中但确实用过判定线）与用过 6 项同一条规则——
    # 6 项混用 school / national 时**任一项降级即 ``"national"``**（保守侧：告诉教师
    # 「这个人的判定线里有人是兜底来的」比反过来安全）。生产者见
    # ``app.domain.percentile.summarize_source``。
    percentile_source: Mapped[str] = mapped_column(String(8))
    valid_from: Mapped[dt.date] = mapped_column(Date)  # 生效起
    valid_to: Mapped[dt.date | None] = mapped_column(Date)  # 生效止；仍生效时为 NULL

    __table_args__ = (
        _in_domain("label", LABELS, "ck_stratification_result_label"),
        _in_domain(
            "percentile_source",
            PERCENTILE_SOURCES,
            "ck_stratification_result_percentile_source",
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.6 预警与运维（本计划只落运维两张表，alert / notification 属计划 03）
# ---------------------------------------------------------------------------


class DailySyncRun(Base):
    """一次每日批处理的运行记录，同时是全管道幂等键的载体。

    ``(semester_id, business_date)`` 唯一：同一天重跑必须落到同一行。管道据此先按
    ``batch_id`` 删掉派生行再重写，重放才是幂等的；否则同一学生同一天会累积出多条
    分层结果，红黄绿分布随之失真。

    计数列一律 ``default=0`` 而非可空：运行记录常在跑完之前就已入库（拿 ``id`` 当
    ``batch_id`` 用），此时计数是「还没数」而不是「未知」，0 比 NULL 更诚实，也让
    下游求和时不必处处防 None。
    """

    __tablename__ = "daily_sync_run"

    STATUSES: set[str] = {"success", "partial", "failed"}

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    business_date: Mapped[dt.date] = mapped_column(Date)  # 与 semester_id 组成唯一约束
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    # 各源抽取条数
    extracted_fitness: Mapped[int] = mapped_column(Integer, default=0)
    extracted_body_comp: Mapped[int] = mapped_column(Integer, default=0)
    extracted_survey: Mapped[int] = mapped_column(Integer, default=0)
    # 清洗计数
    dropped_count: Mapped[int] = mapped_column(Integer, default=0)  # 剔除数
    corrected_count: Mapped[int] = mapped_column(Integer, default=0)  # 修正数
    # 分层分布计数。spec §4.6 只写「红黄绿」，这里补 insufficient_count：
    # 标签域是四个值，少一列就会让「本日没分层的人」在运维记录里凭空消失。
    red_count: Mapped[int] = mapped_column(Integer, default=0)
    yellow_count: Mapped[int] = mapped_column(Integer, default=0)
    green_count: Mapped[int] = mapped_column(Integer, default=0)
    insufficient_count: Mapped[int] = mapped_column(Integer, default=0)
    # 下面两列由计划 02（处方）与计划 03（预警）写入；spec §4.6 已把它们列在本表，
    # 故此处只留计数列，不提前建 prescription / alert 表。
    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数

    # status 同样有默认值（Ruling 30），理由与计数列一致：本列 NOT NULL，而运行记录
    # 常在跑完之前就已入库（要先拿到 id 当 batch_id 用），此时它还没有真实结局。
    # 默认取 "failed" 而不是 "success"，是保守方向：进程崩在中途时，这一行留下的
    # 就是 "failed"——崩溃被记成失败只是难看，被记成成功则是谎报一次并没有发生的
    # 完整运行，而下游看 status 决定是否要重跑，谎报成功会让这一天永远不再重跑。
    status: Mapped[str] = mapped_column(String(8), default="failed")
    error_summary: Mapped[str | None] = mapped_column(Text)  # 错误摘要

    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "business_date",
            name="uq_daily_sync_run_semester_business_date",
        ),
        _in_domain("status", STATUSES, "ck_daily_sync_run_status"),
    )


class CleaningLog(Base):
    """每一条被剔除或被修正的数据的交代（spec §4.6）。

    不是过度设计：一个要发论文、要结题、要向省内高校推广的研究项目，必须能回答
    「这条数据为什么没了」。``kind`` 与 Task 5 的 ``CleaningEntry.kind`` 同域。

    原值与处理后值用 :class:`JsonText` 而不是裸 ``Text``：清洗条目的值是 ``object``
    （数值、字符串或 ``None``），JSON 编码能原样保住类型与 ``None`` 的语义。若直接
    ``str(value)`` 落成文本，``str(None)`` 会把「缺失」写成字符串 ``"None"``——那是
    审计记录里最难被发现的一类谎报。这两列也是 :class:`JsonText` 存在的直接理由：
    SQLAlchemy 自带的 ``JSON`` 类型在 SQLite 上会把 ``0.0`` 这类标量按 NUMERIC 亲和性
    改写成原生数值（实测读回 ``int 0``），审计记录里的「原值」因此不再等于原值。

    学号用双列承载（Ruling 25）：``student_no`` 非空、逐字节照抄收到的原始学号，
    ``student_id`` 可空、只在学号能解析到 ``student`` 表时才填。**学号解析不出来的
    那条记录，本身就是最该留痕的数据质量问题**：若把 ``student_id`` 做成非空外键，
    孤儿学号的审计记录会被约束直接挡在库外，最该被看见的那一类问题反而被静默吞掉，
    而 spec §4.6「必须能交代每一条被剔除或修正的数据」恰恰在这一类上失守。Task 5 的
    ``CleaningEntry.student_no`` 是 ``str``，双列也让清洗结果不必先解析成功才落库。
    """

    __tablename__ = "cleaning_log"

    KINDS: set[str] = {
        "missing_dropped",
        "outlier_corrected",
        "unit_normalized",
        "duplicate_removed",
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"))
    student_no: Mapped[str] = mapped_column(String(32))  # 原始学号，不做 strip / 补零
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))  # 解析得到才填
    field: Mapped[str] = mapped_column(String(32))  # 出问题的字段名
    # 值域是标量或 None；标注取最常见形态，实际由 JsonText 承载，不做运行期检查
    original_value: Mapped[float | str | None] = mapped_column(JsonText)
    processed_value: Mapped[float | str | None] = mapped_column(JsonText)
    kind: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)

    __table_args__ = (_in_domain("kind", KINDS, "ck_cleaning_log_kind"),)
