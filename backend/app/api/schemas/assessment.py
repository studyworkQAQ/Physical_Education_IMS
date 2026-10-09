"""spec §4.2 学期节点数据的 4 个资源：三件套 × 3 + 只读 × 1。

| 资源路径                        | 表                     | ``writable`` | ``on_delete`` |
| =============================== | ====================== | ============ | ============= |
| ``/api/fitness-test-batches``    | ``fitness_test_batch``  | ✅           | ``restrict``  |
| ``/api/fitness-test-results``    | ``fitness_test_result`` | ❌           | ``forbid``    |
| ``/api/body-compositions``       | ``body_composition``    | ✅           | ``restrict``  |
| ``/api/interest-surveys``        | ``interest_survey``     | ✅           | ``restrict``  |

**``fitness_test_result`` 为什么只读**（计划 Task 3 的显式决定）：它是**乐跑的投影**
（:mod:`app.adapters` 抽回来、:mod:`app.pipeline.clean` 洗过、按
``uq_fitness_result_test_batch_student`` 幂等落库），也是批处理的**输入**。
开放写入等于让人改原始数据，而下游的百分位快照、短板计数与趋势全部由它算出——
改一行会静默改变整批学生的分层，且没有任何一处日志会记下「这一行被人改过」。

**``body_composition`` 与 ``interest_survey`` 为什么可写**：InBody 与问卷都是**人工录入**的，
录错了教师要能改（计划的原文：「InBody 是人工录入的，教师要能改错」）。

⚠️ **``fitness_test_batch`` 全表没有唯一约束**（实测：0 条 ``UniqueConstraint``、
0 个列级 ``unique``），故 ``natural_key`` 传 ``None``、POST 走裸 ``session.add``——
**同一个 ``(semester_id, timepoint)`` 可以被建两次**，结构上不可能撞键，也就没有 409
这一档（P3-B2）。理由与 ``course_section`` 那条同族：一个学期的 ``week1`` 采集
在真实场景里可能跨好几个采集日、分成好几个批次（``fitness_test_result.tested_on``
那一列的注释逐字交代了这件事：「一个 week1 批次的记录横跨好几个采集日」），
故 ``(semester_id, timepoint)`` **不是**唯一键。⚠️ 代价：重复批次会让
``percentile_stage`` 的「挑 <= as_of 的最新一个 week1 批次」这一步有歧义，
已登记为 Task 3 报告的关切。

**``fitness_test_result`` 的 21 列**是全库最宽的一张表，也是「list 端点必须有分页上界」
的那个理由（计划 Task 3：``21 列 × 上万行``）。它没有 ``JsonText`` 列，故
``list_exclude`` 自动探测出的是空元组——list 与 read-one 返回同一套键。
"""
import datetime as dt

from pydantic import BaseModel, field_validator

from app.api.schemas._base import ReadModel, one_of
from app.db.models import FitnessTestBatch

__all__ = [
    "BodyCompositionCreate",
    "BodyCompositionRead",
    "BodyCompositionUpdate",
    "FitnessTestBatchCreate",
    "FitnessTestBatchRead",
    "FitnessTestBatchUpdate",
    "FitnessTestResultRead",
    "InterestSurveyCreate",
    "InterestSurveyRead",
    "InterestSurveyUpdate",
]


# ---------------------------------------------------------------------------
# fitness_test_batch（6 列；⚠️ 无唯一约束 → natural_key is None）
# ---------------------------------------------------------------------------


class FitnessTestBatchRead(ReadModel):
    """``fitness_test_batch`` 的 6 列。"""

    id: int
    semester_id: int
    timepoint: str
    test_date: dt.date
    source: str | None
    academic_year: str | None


class FitnessTestBatchCreate(BaseModel):
    """``fitness_test_batch`` 的 5 个可写列。"""

    semester_id: int
    timepoint: str
    test_date: dt.date
    source: str | None = None
    academic_year: str | None = None

    @field_validator("timepoint")
    @classmethod
    def _timepoint_in_the_model_domain(cls, value: str) -> str:
        return one_of("timepoint", value, FitnessTestBatch.TIMEPOINTS)


class FitnessTestBatchUpdate(BaseModel):
    """``fitness_test_batch`` 的部分更新。"""

    semester_id: int | None = None
    timepoint: str | None = None
    test_date: dt.date | None = None
    source: str | None = None
    academic_year: str | None = None

    @field_validator("timepoint")
    @classmethod
    def _timepoint_in_the_model_domain(cls, value: str | None) -> str | None:
        return one_of("timepoint", value, FitnessTestBatch.TIMEPOINTS)


# ---------------------------------------------------------------------------
# fitness_test_result（21 列，全库最宽；只读）
# ---------------------------------------------------------------------------


class FitnessTestResultRead(ReadModel):
    """``fitness_test_result`` 的 **21** 列：8 项原始测量 + 7 项国标得分 + 总分与等级。

    ⚠️ **8 → 7 不是抄漏了一列**：身高与体重合成 BMI 一项计分（spec §4.2），
    故 ``height_cm`` 与 ``weight_kg`` 两列共用一个 ``score_bmi``。
    ⚠️ 7 个 ``score_*`` 列的列名一律是 ``score_`` + ``ScoredItem`` 的值，
    管道用 ``getattr(row, f"score_{item.value}")`` 逐项取用——**故这些字段名不得改**，
    改一个就是一次静默的 ``AttributeError``（在读侧，离真因一整个批处理周期）。

    可空性照 :class:`app.db.models.FitnessTestResult` 的列声明：
    **缺测就是 ``NULL``，绝不是 0**（Ruling 21；50 米跑与耐力跑各占 20% 权重，
    把缺测当 0 分等于给体能最差的学生送 40% 权重的满分）。
    """

    id: int
    test_batch_id: int
    student_id: int
    tested_on: dt.date
    height_cm: float | None
    weight_kg: float | None
    vital_capacity_ml: float | None
    sprint_50m_s: float | None
    sit_and_reach_cm: float | None
    standing_jump_cm: float | None
    strength_count: float | None
    distance_run_s: float | None
    score_bmi: int | None
    score_vital_capacity: int | None
    score_sprint_50m: int | None
    score_sit_and_reach: int | None
    score_standing_jump: int | None
    score_pull_up_or_sit_up: int | None
    score_distance_run: int | None
    total_score: int | None
    national_grade: str | None


# ---------------------------------------------------------------------------
# body_composition（8 列）
# ---------------------------------------------------------------------------


class BodyCompositionRead(ReadModel):
    """``body_composition`` 的 8 列。``smi``（骨骼肌指数）入库但**不参与**异常判定
    （spec §14 待确认 #16），故它在读模型里是一个纯展示字段。
    """

    id: int
    student_id: int
    measured_on: dt.date
    muscle_mass_kg: float | None
    body_fat_pct: float | None
    smi: float | None
    weight_kg: float | None
    device: str | None


class BodyCompositionCreate(BaseModel):
    """``body_composition`` 的 7 个可写列。

    ``(student_id, measured_on)`` 是自然键（``uq_body_composition_student_measured_on``），
    故撞键 → 409。⚠️ 五个测量列**全部可空且缺省 ``None``**：
    InBody 报告可以整列缺失（包约定 1：缺测就是 ``NULL``），
    而「没测到」与「测到 0」在体成分上是两件完全不同的事。
    """

    student_id: int
    measured_on: dt.date
    muscle_mass_kg: float | None = None
    body_fat_pct: float | None = None
    smi: float | None = None
    weight_kg: float | None = None
    device: str | None = None


class BodyCompositionUpdate(BaseModel):
    """``body_composition`` 的部分更新。字段集与 :class:`BodyCompositionCreate` 同名。"""

    student_id: int | None = None
    measured_on: dt.date | None = None
    muscle_mass_kg: float | None = None
    body_fat_pct: float | None = None
    smi: float | None = None
    weight_kg: float | None = None
    device: str | None = None


# ---------------------------------------------------------------------------
# interest_survey（7 列；2 个 JsonText 列）
# ---------------------------------------------------------------------------


class InterestSurveyRead(ReadModel):
    """``interest_survey`` 的 7 列，含 2 个 ``JsonText`` 列
    （``dimensions`` / ``raw_answers``）——它们在 list 端点里**不出现**。
    """

    id: int
    student_id: int
    semester_id: int
    filled_on: dt.date
    total_score: float
    dimensions: dict
    raw_answers: dict


class InterestSurveyCreate(BaseModel):
    """``interest_survey`` 的 6 个可写列。

    ⚠️ ``dimensions`` 与 ``raw_answers`` 是**必填**的 ``dict``：两列在 DB 侧都是
    NOT NULL 的 :class:`~app.db.models._shared.JsonText`，而「问卷没答」的正确表达是
    **不建这一行**，不是建一行填 ``{}``——一个空字典会让
    ``interest_survey`` 的维度均值被一份没有答案的问卷拉低，且看不出区别。
    """

    student_id: int
    semester_id: int
    filled_on: dt.date
    total_score: float
    dimensions: dict
    raw_answers: dict


class InterestSurveyUpdate(BaseModel):
    """``interest_survey`` 的部分更新。"""

    student_id: int | None = None
    semester_id: int | None = None
    filled_on: dt.date | None = None
    total_score: float | None = None
    dimensions: dict | None = None
    raw_answers: dict | None = None
