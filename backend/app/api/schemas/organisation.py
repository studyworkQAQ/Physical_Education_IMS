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
**Plan 05A Task 1 加了第四个**：``teacher.role``（同样走 ``one_of`` +
:attr:`app.db.models.Teacher.ROLES`，``TeacherCreate`` 与 ``TeacherUpdate`` 各一个校验器）。
**其余列一律不做取值校验**：DB 的 ``CheckConstraint`` / ``ForeignKey`` /
``NOT NULL`` 已经在管，在 schema 里再抄一份就是第二个所有者。

⚠️⚠️ **Plan 05A Task 1 给 ``student`` 与 ``teacher`` 各加了两个凭据列
（``password_hash`` / ``password_bound_at``），而上面那条字段规则 1
（「``*Read`` = 该表的**全部列**」）因此第一次有了例外**：``password_hash``
是**秘密**，两个 ``*Read`` 都刻意不含它；``password_bound_at`` 不是秘密，故含。
例外的两个住址（读模型 + list 端点的 ``list_exclude``）与完整理由逐字写在
:class:`TeacherRead` 的 docstring 里，守卫是 ``tests/api/test_crud.py`` 的
:func:`test_every_read_schema_covers_exactly_the_model_columns`（档 2 清单）与
:func:`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
（list 那一半）。⚠️ 规则 2（``*Create`` = 全部列减 ``id``）也第一次有了例外：
那两列由服务端填（绑定端点），故走档 1 清单。
"""
import datetime as dt

from pydantic import BaseModel, field_validator

from app.api.schemas._base import ReadModel, one_of
from app.db.models import CourseSection, Student, Teacher

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
# teacher（**6 列**，Plan 05A Task 1 起：原 3 列 + ``role`` + 凭据 2 列）
# ---------------------------------------------------------------------------


class TeacherRead(ReadModel):
    """``teacher`` 的 6 列里**暴露 5 列**。``staff_no`` 是教师身份的载体
    （``X-Teacher-Staff-No``）。

    ⚠️ **``password_hash`` 刻意不在这里**（Plan 05A Task 1）：它是凭据，
    而泛型 ``GET`` 一律匿名（Task 3 的偏离 ⑦），故把它留在读模型上等于
    「任何人 ``GET /api/teachers/{id}`` 就能读到全校教师的口令哈希」——
    离线爆破一个 PBKDF2 串是**几小时**的事，而哈希一旦泄漏就无法撤销
    （改口令要用户自己动手，而原型没有找回流程）。
    它因此进 ``tests/api/test_crud.py`` 的
    :data:`_SERVER_GENERATED_HIDDEN_COLUMNS`（档 2：服务端生成、且是秘密），
    与 ``class_session.rpe_token`` 同一档。
    ⚠️ **另一半的洞在 list 端点**：泛型 list **不走 ``response_model``**，
    故光是从本模型上摘掉它堵不住 ``GET /api/teachers``——
    :data:`app.api.routers.catalog.RESOURCES` 的 ``teachers`` 那一行**也**显式写了
    ``"list_exclude": ("password_hash",)``。两处缺一不可（档 2 那份常量的注释
    逐字写了这个「两半」的形状）。

    ⚠️ **``password_bound_at`` 反过来是暴露的**：它不是凭据，而「这个人绑定过口令了吗、
    什么时候绑的」正是教务干事在管理台上要看的（好去提醒没注册的人）。
    ⚠️ 代价（硬规矩 #39）：匿名 ``GET /api/teachers`` 因此泄漏「哪些工号已注册」，
    而计划 §3.3 已经裁定接受同一档泄漏（登录的 403 ``password_not_bound``
    与 401 ``invalid_credentials`` 两档区分本身就给出了这个信号）。
    它进的是档 1（:data:`_SERVER_FILLED_COLUMNS`：服务端填、但要暴露）。
    """

    id: int
    staff_no: str
    name: str
    role: str
    password_bound_at: dt.datetime | None


class TeacherCreate(BaseModel):
    """``teacher`` 的 3 个可写列（``staff_no`` 唯一，约束无名）。

    ⚠️ ``role`` 有缺省值 :attr:`app.db.models.Teacher.DEFAULT_ROLE`（``"teacher"``）：
    它是本仓第三个「带 Python 侧 default 的列」（另两个是 ``semester.is_current`` 与
    ``class_session.rpe_opened``，见模块 docstring 的字段规则 2）。
    于是**建一个管理员是一次显式的 ``{"role": "admin"}``**，而漏写 ``role``
    得到的是一个普通教师——失效方向是安全的（少给权限，不是多给）。
    ⚠️ 而 ``POST /api/teachers`` 自 Plan 05A Task 2 起**只有管理员能调**
    （``require_admin``），故「谁能造出一个管理员」这个问题的答案是「已经是管理员的人」。
    演示库的第一个管理员由 ``backend/scripts/demo_bootstrap.py`` 直接写 ORM 造出来
    （Plan 05A Task 4）。

    ⚠️ ``password_hash`` / ``password_bound_at`` **不在这里**：它们由
    ``POST /api/auth/teachers/bind`` 填（服务端算哈希、服务端盖时刻），
    客户端传了也没用（Pydantic 缺省 ``extra="ignore"``，多传的键被静默丢掉）。
    ⚠️ 那一格是承重的：能被 POST 写进去的口令哈希等于「任何人可以给任何教师
    设一个自己知道的口令」，而那就是绕过绑定流程（工号 + 姓名验身）本身。
    """

    staff_no: str
    name: str
    role: str = Teacher.DEFAULT_ROLE

    @field_validator("role")
    @classmethod
    def _role_in_the_model_domain(cls, value: str) -> str:
        return one_of("role", value, Teacher.ROLES)


class TeacherUpdate(BaseModel):
    """``teacher`` 的部分更新。

    ⚠️ **``role`` 在这里是可以改的**（把一个教师提成管理员、或把一个管理员降权），
    而它是 Plan 05A Task 2 之后**只有管理员能调**的端点，故「提权」这件事
    只能由已经是管理员的人做。
    ⚠️ **降权对权限是立刻生效的**（Plan 05A Task 2 实测）：``require_admin`` 查的是
    ``teacher`` 表、不是 ``user_session.role`` 那一份冗余，故被降权的人**下一次请求**
    就吃 403。⚠️ 滞后的只有 ``GET /api/auth/me`` 与登录响应体里那个 ``role``
    （它们是**前端路由**的判据）：被降权的人在重新登录之前，前端仍会把他送到
    ``/admin``，然后每一次写都吃一个 403——UI 一致性问题，失效方向是安全的。
    逐字理由与两条守卫见 :mod:`app.db.models.auth` 的模块 docstring 第三节。
    """

    staff_no: str | None = None
    name: str | None = None
    role: str | None = None

    @field_validator("role")
    @classmethod
    def _role_in_the_model_domain(cls, value: str | None) -> str | None:
        return one_of("role", value, Teacher.ROLES)


# ---------------------------------------------------------------------------
# student（**9 列**，Plan 05A Task 1 起：原 7 列 + 凭据 2 列）
# ---------------------------------------------------------------------------


class StudentRead(ReadModel):
    """``student`` 的 9 列里**暴露 8 列**。``department`` 可空，故 ``str | None``。

    ⚠️ **``password_hash`` 刻意不在这里**，理由与两个住址逐字见
    :class:`TeacherRead` 的 docstring（刻意不抄第二份）；
    list 那一半的洞由 ``RESOURCES`` 的 ``students`` 行上那个
    ``"list_exclude": ("password_hash",)`` 堵。
    ⚠️ ``password_bound_at`` 暴露，理由同上。
    ⚠️ **``birth`` 仍然匿名可读**——而它正是学生绑定口令时的验身材料
    （计划 §3.2 自己点出了这个权衡）。收紧它是 **Plan 05A Task 5**
    「48 个匿名 GET 的重新裁定」那一格的活，**不在 Task 1/2 里顺手做**
    （它会改掉前端三个页面的取数姿势）。已登记为关切。
    """

    id: int
    student_no: str
    name: str
    sex: str
    birth: dt.date
    department: str | None
    grade: int
    password_bound_at: dt.datetime | None


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
