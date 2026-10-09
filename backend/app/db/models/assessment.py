"""spec §4.2 学期节点数据（低频，来自乐跑）：体测批次、体测成绩、体成分、兴趣问卷。

Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。
"""

import datetime as dt

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import JsonText, _in_domain


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
    :func:`app.db.repo.delete_by_batch` 可据以删除的归属键，全库只有九张表允许拥有
    它（Plan 01 的三张派生表 + Plan 02 Task 6 的 ``prescription`` / ``weekly_adjustment``
    + Plan 03 Task 2 的 ``class_session`` / ``training_log`` / ``alert`` /
    ``weekly_class_report``）。
    若本表也叫 ``batch_id``，误调 ``delete_by_batch(session, FitnessTestResult,
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
    # **这一列是「本条成绩是哪一天测的」的唯一所有者**（Plan 02 Task 1，终审 B 的 M1）。
    # 源记录本来就带它（``RawFitnessRecord.tested_on``，同时是适配器的增量水位线字段），
    # 但 Plan 01 只把它写进了 ``fitness_test_batch.test_date`` —— 那是**一个批次一个值**，
    # 而一个 week1 批次的记录横跨好几个采集日。后果是 ``cohort_from_db`` 无法按日期截断：
    # 重跑一个**更早**的业务日期时，``_results_of`` 会把整个批次的记录全读回来，包括
    # 那些测量日**晚于** as_of 的行——用未来的数据算过去的分层。终审实测 60 人里
    # **12 人 label 不同**。加上本列后 ``percentile_stage._results_of`` 多一句
    # ``.where(FitnessTestResult.tested_on <= as_of)``，守卫是
    # ``tests/pipeline/test_percentile_stage.py::test_cohort_truncates_results_by_tested_on``。
    #
    # ``fitness_test_batch.test_date`` **不删**：加了本列之后它的唯一职责变成
    # ``assessment_anchor`` 的**排序键**（挑「<= as_of 的最新一个 week1 批次」），
    # 而一个随执行顺序漂移的排序键是不可接受的——故 Step 5 同时把 ``daily._fitness_batch``
    # 的 upsert 改成 ``min(现有值, 本条值)`` 折叠，使它不再随抽取窗口漂移。
    #
    # NOT NULL 且无缺省：每条源记录都带 ``tested_on``（Ruling 41 让适配器**无条件**校验并
    # 归一化它，空单元格在抽取阶段就抛 ``ValueError``），故生产路径上不存在「不知道哪天测的」
    # 的成绩行。做成可空的代价是 ``tested_on <= as_of`` 对 NULL 恒为假、那一行被静默丢掉，
    # 而「静默少一个人」正是本列要消灭的缺陷形态。
    #
    # ⚠️ **破坏性 schema 改动**：已有的 ``pe.db`` 里那 3000 行（500 人 × 6 个采集日）没有
    # 这一列，而 ``create_all`` 不给已存在的表补列，故**必须重建库**（见包 docstring）。
    tested_on: Mapped[dt.date] = mapped_column(Date)

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
