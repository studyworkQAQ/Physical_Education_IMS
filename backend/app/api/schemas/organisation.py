"""spec §4.1 组织与身份的 5 个资源：``Read`` / ``Create`` / ``Update`` 三件套。

| 资源路径               | 表                | 模型类          | ``writable`` | ``on_delete`` |
| ====================== | ================= | =============== | ============ | ============= |
| ``/api/semesters``      | ``semester``      | ``Semester``     | ✅           | ``forbid``    |
| ``/api/teachers``       | ``teacher``       | ``Teacher``      | ✅           | ``restrict``  |
| ``/api/students``       | ``student``       | ``Student``      | ✅           | ``restrict``  |
| ``/api/course-sections``| ``course_section``| ``CourseSection``| ✅           | ``restrict``  |
| ``/api/enrollments``    | ``enrollment``    | ``Enrollment``   | ✅           | ``restrict``  |

⚠️ **路径用连字符、字段名用下划线**（计划 Task 3 的显式要求，对照表住在
:mod:`app.api.crud` 的模块 docstring）：``/api/course-sections`` 而
``course_section_id``。前者是 URL 惯例，后者必须与 DB 列名逐字相同——
:func:`app.api.crud.build_crud_router` 的 POST / PATCH 直接拿
``payload.model_dump()`` 的键去 ``setattr`` / ``model(**values)``，
改一个字段名就是一次 ``TypeError: 'xxx' is an invalid keyword argument``。

**本模块 5 个资源全部可写**，故 5 × 3 = 15 个模型一个都不少。三条字段规则：

1. ``*Read`` = 该表的**全部列**（含主键），类型照列的可空性；
2. ``*Create`` = 全部列**减去 ``id``**（代理键由 SQLite 的 AUTOINCREMENT 给），
   其中带 Python 侧 ``default`` 的列（``semester.is_current`` /
   ``course_section`` 无 / ``class_session.rpe_opened``）声明成有缺省的可选字段；
3. ``*Update`` = 与 ``*Create`` **同名字段**、一律 ``X | None = None``
   （PATCH 的部分更新靠 :meth:`pydantic.BaseModel.model_dump` 的
   ``exclude_unset=True`` 区分「没传」与「传了 null」，故字段必须有缺省值）。

⚠️ **三张表的枚举列有 Pydantic 侧校验**（``student.sex`` /
``course_section.grouping_mode`` / ``fitness_test_batch.timepoint``，后者住在
:mod:`app.api.schemas.assessment`），走 :func:`app.api.schemas._base.one_of` +
模型类常量，理由与「为什么是 422 而不是 409」见那个函数的 docstring。
**其余列一律不做取值校验**：DB 的 ``CheckConstraint`` / ``ForeignKey`` /
``NOT NULL`` 已经在管，在 schema 里再抄一份就是第二个所有者。
"""
import datetime as dt

from pydantic import BaseModel, field_validator

from app.api.schemas._base import ReadModel, one_of
from app.db.models import CourseSection, Student

__all__ = [
    "CourseSectionCreate",
    "CourseSectionRead",
    "CourseSectionUpdate",
    "EnrollmentCreate",
    "EnrollmentRead",
    "EnrollmentUpdate",
    "SemesterCreate",
    "SemesterRead",
    "SemesterUpdate",
    "StudentCreate",
    "StudentRead",
    "StudentUpdate",
    "TeacherCreate",
    "TeacherRead",
    "TeacherUpdate",
]


# ---------------------------------------------------------------------------
# semester（6 列；``name`` 唯一，且那条约束**无名** → 409 消息只能引列名，P3-B5）
# ---------------------------------------------------------------------------


class SemesterRead(ReadModel):
    """``semester`` 的 6 列。⚠️ ``end_date`` 是**排他**上界（Ruling 174）。"""

    id: int
    name: str
    start_date: dt.date
    end_date: dt.date
    weeks: int
    is_current: bool


class SemesterCreate(BaseModel):
    """``semester`` 的 5 个可写列。``is_current`` 有 Python 侧缺省 ``False``。"""

    name: str
    start_date: dt.date
    end_date: dt.date
    weeks: int
    is_current: bool = False


class SemesterUpdate(BaseModel):
    """``semester`` 的部分更新。字段集与 :class:`SemesterCreate` 逐字同名。"""

    name: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    weeks: int | None = None
    is_current: bool | None = None


# ---------------------------------------------------------------------------
# teacher（3 列）
# ---------------------------------------------------------------------------


class TeacherRead(ReadModel):
    """``teacher`` 的 3 列。``staff_no`` 是教师身份的载体（``X-Teacher-Staff-No``）。"""

    id: int
    staff_no: str
    name: str


class TeacherCreate(BaseModel):
    """``teacher`` 的 2 个可写列（``staff_no`` 唯一，约束无名）。"""

    staff_no: str
    name: str


class TeacherUpdate(BaseModel):
    """``teacher`` 的部分更新。"""

    staff_no: str | None = None
    name: str | None = None


# ---------------------------------------------------------------------------
# student（7 列）
# ---------------------------------------------------------------------------


class StudentRead(ReadModel):
    """``student`` 的 7 列。``department`` 可空，故 ``str | None``。"""

    id: int
    student_no: str
    name: str
    sex: str
    birth: dt.date
    department: str | None
    grade: int


class StudentCreate(BaseModel):
    """``student`` 的 6 个可写列（``student_no`` 唯一，约束无名）。

    ⚠️ ``sex`` 的取值域**不在这里声明**：:attr:`Student.SEXES` 是唯一所有者，
    下面的校验器把它传给 :func:`one_of`。
    """

    student_no: str
    name: str
    sex: str
    birth: dt.date
    department: str | None = None
    grade: int

    @field_validator("sex")
    @classmethod
    def _sex_in_the_model_domain(cls, value: str) -> str:
        return one_of("sex", value, Student.SEXES)


class StudentUpdate(BaseModel):
    """``student`` 的部分更新。"""

    student_no: str | None = None
    name: str | None = None
    sex: str | None = None
    birth: dt.date | None = None
    department: str | None = None
    grade: int | None = None

    @field_validator("sex")
    @classmethod
    def _sex_in_the_model_domain(cls, value: str | None) -> str | None:
        return one_of("sex", value, Student.SEXES)


# ---------------------------------------------------------------------------
# course_section（6 列；⚠️ **全表没有唯一约束** → natural_key is None，P3-B2）
# ---------------------------------------------------------------------------


class CourseSectionRead(ReadModel):
    """``course_section`` 的 6 列。"""

    id: int
    semester_id: int
    teacher_id: int
    name: str
    schedule_text: str | None
    grouping_mode: str


class CourseSectionCreate(BaseModel):
    """``course_section`` 的 5 个可写列。

    ⚠️ **本表没有任何唯一约束**（实测：0 条 ``UniqueConstraint``、0 个列级 ``unique``），
    故 ``build_crud_router`` 的 ``natural_key`` 传 ``None``，POST 走裸 ``session.add``
    ——**同一个教学班可以被建两次**，结构上不可能撞键，也就没有 409 这一档
    （P3-B2 的反向测试
    ``tests/api/test_crud.py::test_a_resource_without_a_natural_key_never_returns_409``
    钉的就是这件事）。理由：阶段一的行政班与阶段二的分层班**同名并存**是合法状态
    （``grouping_mode`` 区分它们），而「同学期 + 同名 + 同教师」到底算不算重复
    要问教务，原型不替它定。
    """

    semester_id: int
    teacher_id: int
    name: str
    schedule_text: str | None = None
    grouping_mode: str

    @field_validator("grouping_mode")
    @classmethod
    def _grouping_mode_in_the_model_domain(cls, value: str) -> str:
        return one_of("grouping_mode", value, CourseSection.GROUPING_MODES)


class CourseSectionUpdate(BaseModel):
    """``course_section`` 的部分更新。"""

    semester_id: int | None = None
    teacher_id: int | None = None
    name: str | None = None
    schedule_text: str | None = None
    grouping_mode: str | None = None

    @field_validator("grouping_mode")
    @classmethod
    def _grouping_mode_in_the_model_domain(cls, value: str | None) -> str | None:
        return one_of("grouping_mode", value, CourseSection.GROUPING_MODES)


# ---------------------------------------------------------------------------
# enrollment（4 列；自然键是三列的复合唯一约束）
# ---------------------------------------------------------------------------


class EnrollmentRead(ReadModel):
    """``enrollment`` 的 4 列（三个外键 + 代理键）。"""

    id: int
    semester_id: int
    student_id: int
    course_section_id: int


class EnrollmentCreate(BaseModel):
    """``enrollment`` 的 3 个可写列，恰好是那条复合唯一约束的三列。"""

    semester_id: int
    student_id: int
    course_section_id: int


class EnrollmentUpdate(BaseModel):
    """``enrollment`` 的部分更新。

    ⚠️ 改这三列里的任何一个都可能撞上 ``uq_enrollment_semester_student_section``，
    那时的响应是 **409**（``IntegrityError`` 经 :mod:`app.api.errors`）。
    PATCH 侧**不做**应用层的撞键预检（POST 才做，见
    :func:`app.api.crud.build_crud_router`），故两档的 409 消息措辞不同：
    POST 的是工厂自己拼的中文句子，PATCH 的是 DBAPI 的英文原文。
    """

    semester_id: int | None = None
    student_id: int | None = None
    course_section_id: int | None = None
