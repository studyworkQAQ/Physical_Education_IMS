"""spec §4.1 组织与身份：学期、教师、学生、教学班、选课关系。

Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
三条贯穿全表的约定（缺测就是 NULL、枚举取值域两处设防、JSON 列一律用 JsonText）
写在包的 docstring 里：:mod:`app.db.models`。
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
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
