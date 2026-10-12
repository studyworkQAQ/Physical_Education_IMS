"""spec §4.1 组织与身份：学期、教师、学生、教学班、选课关系。

Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
三条贯穿全表的约定（缺测就是 NULL、枚举取值域两处设防、JSON 列一律用 JsonText）
写在包的 docstring 里：:mod:`app.db.models`。
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import _in_domain


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
    """体育教师。工号是与教务系统对接的自然键。

    ⚠️ **``role`` 自 Plan 05A 起住在这里、不住在一张单独的权限表里**（计划 §1 的非目标
    逐字写了「不建权限表」）：``role`` 只影响两件事——① 管理台的写操作要不要 ``admin``
    （:func:`app.api.deps.require_admin`）；② 是否越过任教范围闸门
    （:func:`app.api.deps.require_teaches_section` / ``require_teaches_student``）。
    一个只影响两件事的二元标签不需要一张 RBAC 表，而一张表会带来「谁维护它」这个问题。

    ⚠️ **管理员也是一行 ``teacher``**（不是第三张表）：用户 2026-10-12 裁定
    「管理员这个角色接管管理台（23 个资源的增删改查）」，而教务干事本来就是一名在册教职，
    故 ``role='admin'`` 是**教师行上的一个标签**。两个后果都承重：
    ① 既有那一道「在册教职」闸门（:func:`app.api.deps.require_staff`）对管理员**天然放行**，
    课堂功能不需要为管理员另开一条路径；
    ② ``POST /api/auth/login`` 的 ``kind`` 只有 ``student`` / ``teacher`` 两个值，
    管理员用教师那一档登录，前端再按响应体里的 ``role`` 决定跳 ``/admin`` 还是 ``/t/dashboard``。
    """

    __tablename__ = "teacher"

    #: ``role`` 的取值域。⚠️ 类常量是唯一真相（本包约定 2），CHECK 文本由它生成。
    #: ⚠️ 它是 :attr:`app.db.models.auth.UserSession.ROLES` 的**子集**
    #: （会话那一列还要能装 ``student``），两份词表的一致性由
    #: ``tests/auth/test_sessions.py`` 的
    #: ``test_the_role_vocabulary_of_a_session_is_the_teacher_one_plus_student`` 钉住。
    ROLES: set[str] = {"teacher", "admin"}

    #: ``role`` 那一列的**普通档**字面值。⚠️ 它是「一个新建的教师默认不是管理员」
    #: 这件事的唯一住址：Python 侧的列 ``default`` 与
    #: :class:`app.api.schemas.organisation.TeacherCreate` 的字段缺省都从这里取。
    #: 没有它的话，``POST /api/teachers`` 漏传 ``role`` 会写进一个 ``NULL``
    #: （那一列 NOT NULL → IntegrityError → 409），而 409 说的是「与别人撞了」，
    #: 与「你没填这一格」是两回事。
    DEFAULT_ROLE: str = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_no: Mapped[str] = mapped_column(String(32), unique=True)  # 工号
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default=DEFAULT_ROLE)
    # Plan 05A 的三列之二：口令与它的绑定时刻。⚠️ **NULL = 未绑定**，
    # 而「未绑定」与「密码错」在 ``POST /api/auth/login`` 上是两个不同的 code
    # （403 password_not_bound / 401 invalid_credentials，计划 §3.3），故那一列的可空性
    # 是承重的、不能用一个哨兵串代替（硬规矩 #101 的反面：这一列**不是**外键，
    # 但用哨兵仍然会让「未绑定」与「绑定了一个不可能的口令」在库里无法区分）。
    # ⚠️ 存的是 :func:`app.auth.passwords.hash_password` 那个**自描述串**
    # （``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``；生产缺省的 600 000 次迭代下
    # 实测 **90** 个字符 = 13 + 1 + 6 + 1 + 24 + 1 + 44），255 的宽度留给将来更长的算式名。
    # ⚠️⚠️ **它不得出现在任何响应体里**：``TeacherRead`` 的字段是显式清单
    # （没有它），而泛型 ``GET /api/teachers`` 的 list 端点**不走 response_model**，
    # 故 :data:`app.api.routers.catalog.RESOURCES` 的 ``teachers`` 那一行显式写了
    # ``"list_exclude": ("password_hash",)``。守卫是 ``tests/api/test_crud.py`` 的
    # ``test_the_credential_columns_never_appear_in_any_response_body``。
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_bound_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    __table_args__ = (_in_domain("role", ROLES, "ck_teacher_role"),)


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
    # Plan 05A 的两列：口令与它的绑定时刻。⚠️ 列名与语义、以及「NULL = 未绑定」
    # 与「它不得出现在任何响应体里」两条，逐字见 :class:`Teacher` 上同名两列的注释
    # （刻意不抄第二份：两处措辞漂开之后，下一个人不知道哪一份是真的）。
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_bound_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

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
