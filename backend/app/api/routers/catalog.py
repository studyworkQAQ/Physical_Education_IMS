"""CRUD 资源目录：**一个列表驱动**，每行是一次
:func:`app.api.crud.build_crud_router` 的调用参数。

本 commit 落地第一批 4 个资源（``semesters`` / ``teachers`` / ``students`` /
``stratification-results``），用来把五个端点在两个可写资源与一个只读资源上跑通；
余下 19 行随本 Task 的后续 commit 补齐，届时 :data:`RESOURCES` 是 **23** 行。

**为什么是「一个列表 + 一个循环」而不是 23 次 ``router.include_router(...)``**：
列表让「这个系统有哪些资源、每个的读写口径是什么」成为**一份可以一次读完的数据**，
而不是一堆散在函数体里的调用。遍历型的守卫
（``tests/api/test_crud.py`` 的那 8 条）全部读 :data:`RESOURCES`，
于是「加第 24 个资源」会被它们自动纳入——**除了那些数字本身**，
故那几条断言的期望值一律字面写死（硬规矩 #35/#89），不从 ``RESOURCES`` 反推。

⚠️ **每行必须字面写出 ``natural_key`` 与 ``on_delete`` 两个键**：
前者在工厂里**没有缺省值**（漏写是 ``TypeError``），后者有缺省值 ``"restrict"``
（漏写会静默落到 restrict），故
``test_every_resource_declares_on_delete_explicitly`` 断言的是
``"on_delete" in spec``——**键在不在**，而不是值等不等于什么。
"""
from typing import Any

from fastapi import APIRouter

from app.api.crud import (
    ON_DELETE_FORBID,
    ON_DELETE_RESTRICT,
    CrudSchemas,
    build_crud_router,
)
from app.api.schemas.derived import StratificationResultRead
from app.api.schemas.organisation import (
    SemesterCreate,
    SemesterRead,
    SemesterUpdate,
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TeacherCreate,
    TeacherRead,
    TeacherUpdate,
)

# ⚠️ 下面 12 个模型走 `from app.db import models`（它们在 `app.db.models` 的公有导入面上），
# 而另外 11 个**必须**走子模块路径（Ruling 97 / 硬规矩 #102 / 预检更正 P3-B1）：
#   Exercise / PrescriptionTemplate / Prescription / WeeklyAdjustment
#       → from app.db.models.prescription import …
#   ClassSession / RpeRecord / TrainingLog / MiniTest / Alert / Notification /
#   WeeklyClassReport
#       → from app.db.models.feedback import …
# 写 `models.Prescription` 会得到 AttributeError，且是**导入期**就炸。
from app.db import models

__all__ = ["RESOURCES", "router"]

#: 23 个资源的声明（本 commit 是前 4 行）。**顺序 = 计划读写矩阵那 23 行的顺序**，
#: 也与 :mod:`app.api.crud` 模块 docstring 里那张「路径 / 表 / 字段名」对照表同序，
#: 故三处可以逐行对拍。
RESOURCES: tuple[dict[str, Any], ...] = (
    # --- spec §4.1 组织与身份（5 个，全部可写）-----------------------------
    {
        "model": models.Semester,
        "schemas": CrudSchemas(SemesterRead, SemesterCreate, SemesterUpdate),
        "path": "/api/semesters",
        "tags": ["semesters"],
        "writable": True,
        # 全库的时间轴锚点：删一个学期没有安全语义（它下面的 9 张表都按 semester_id 归组），
        # 而「这个学期不要了」的正确做法是把 is_current 置 False。
        "on_delete": ON_DELETE_FORBID,
        # semester.name 的唯一约束**无名**（P3-B5），故 409 的消息只能引列名。
        "natural_key": ("name",),
    },
    {
        "model": models.Teacher,
        "schemas": CrudSchemas(TeacherRead, TeacherCreate, TeacherUpdate),
        "path": "/api/teachers",
        "tags": ["teachers"],
        "writable": True,
        # 有 course_section.teacher_id 子行。⚠️ mini_test.entered_by 存的是**工号字符串**、
        # 不是外键（app.db.models.feedback.MiniTest 的那一列注释交代了理由与代价），
        # 故删教师不会带走他录的小测，_child_tables 也看不到那一层关系。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("staff_no",),
    },
    {
        "model": models.Student,
        "schemas": CrudSchemas(StudentRead, StudentCreate, StudentUpdate),
        "path": "/api/students",
        "tags": ["students"],
        "writable": True,
        # 子行最多的一张表（实测 12 个入向外键）。删一个学生要走学籍流程，不是 API 单点删。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("student_no",),
    },
    # --- spec §4.3 派生与分层（3 个，全部只读 + forbid）---------------------
    {
        "model": models.StratificationResult,
        "schemas": CrudSchemas(StratificationResultRead),
        "path": "/api/stratification-results",
        "tags": ["stratification-results"],
        "writable": False,
        # 批处理产物 + spec §4.3 可追溯性的核心：改一行 label，那条行就无法再离线复算了。
        # 删它的正确方式是重放（_replay_cleanup 按 batch_id 删）。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("student_id", "computed_on"),
    },
)

router = APIRouter()
for _spec in RESOURCES:
    router.include_router(build_crud_router(**_spec))
