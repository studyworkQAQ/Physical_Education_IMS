"""CRUD 资源目录：**23 行数据 + 一个循环**，每行是一次
:func:`app.api.crud.build_crud_router` 的调用参数。

「这个系统有哪些资源、每个的读写口径是什么」因此是**一份可以一次读完的数据**，
而不是一堆散在函数体里的调用。计划 Task 3 的第一条决定（「一致的行为是原型的资产」）
在这里的落点是：23 个资源**没有一个**有自己的特例分支——特例（三源采集、教师覆盖、
预警处理、大屏聚合、手动跑批）各自手写在自己的 router 里，**不走本目录**。

----------------------------------------------------------------------------
读写矩阵（计划 S4 的裁定，逐行抄在每一行的注释里）
----------------------------------------------------------------------------

合计 **23** 个资源：**可写 9 / 只读 14**；``on_delete`` 是
**``restrict`` 12 / ``forbid`` 10 / ``cascade`` 1**。
⚠️ 这三个数由 ``tests/api/test_crud.py`` 的
:func:`~tests.api.test_crud.test_the_read_write_matrix_counts_are_pinned` 钉住，
期望值**字面写死在测试里**、不从本列表反推（硬规矩 #35/#89；计划 Task 3 逐字要求
「数字自己数、不要照抄本行」）。

----------------------------------------------------------------------------
⚠️ P3-B1 / Ruling 97 / 硬规矩 #102：11 个模型**不在** ``app.db.models`` 的公有导入面上
----------------------------------------------------------------------------

Plan 02 的 4 个（``Exercise`` / ``PrescriptionTemplate`` / ``Prescription`` /
``WeeklyAdjustment``）与 Plan 03 Task 2 的 7 个（``ClassSession`` / ``RpeRecord`` /
``TrainingLog`` / ``MiniTest`` / ``Alert`` / ``Notification`` / ``WeeklyClassReport``）
**刻意不进** ``app/db/models/__init__.py`` 的 ``__all__``，也没有星号重导出——
把 ``_MODELS_PUBLIC_BASELINE`` 从 33 抬上去等于把「拆包没改导入面」偷换成
「拆包后的现状」，断言两侧就同源了。

故本文件对那 11 个走**子模块路径**，对其余 12 个走 ``from app.db import models``。
写 ``models.Prescription`` 会在**导入期**得到 ``AttributeError``（``uvicorn`` 起不来）。
守卫是 ``tests/api/test_crud.py`` 的
:func:`~tests.api.test_crud.test_the_eleven_non_public_models_are_reached_through_their_submodules`
——它同时断言那 11 个**确实不在**公有面上（``hasattr(models, 名字) is False``），
于是「有人把它们重导出了」也会红。

⚠️ **这条纪律已经三次没被传导**（Plan 02 的 P6-A8、Plan 03 Task 2 的 P3-A1、本次），
故立了硬规矩 #102：**计划说 ``models.X`` 而 X 不在公有面上时，一律按子模块路径写。**
"""
from typing import Any

from fastapi import APIRouter

from app.api.crud import (
    ON_DELETE_CASCADE,
    ON_DELETE_FORBID,
    ON_DELETE_RESTRICT,
    CrudSchemas,
    build_crud_router,
)
from app.api.schemas.alerts import AlertRead, NotificationRead, WeeklyClassReportRead
from app.api.schemas.assessment import (
    BodyCompositionCreate,
    BodyCompositionRead,
    BodyCompositionUpdate,
    FitnessTestBatchCreate,
    FitnessTestBatchRead,
    FitnessTestBatchUpdate,
    FitnessTestResultRead,
    InterestSurveyCreate,
    InterestSurveyRead,
    InterestSurveyUpdate,
)
from app.api.schemas.derived import (
    DerivedMetricsRead,
    PercentileSnapshotRead,
    StratificationResultRead,
)
from app.api.schemas.feedback import (
    ClassSessionCreate,
    ClassSessionRead,
    ClassSessionUpdate,
    MiniTestRead,
    RpeRecordRead,
    TrainingLogRead,
)
from app.api.schemas.organisation import (
    CourseSectionCreate,
    CourseSectionRead,
    CourseSectionUpdate,
    EnrollmentCreate,
    EnrollmentRead,
    EnrollmentUpdate,
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
from app.api.schemas.prescription import (
    ExerciseRead,
    PrescriptionRead,
    PrescriptionTemplateRead,
    WeeklyAdjustmentRead,
)

# --- 12 个在公有导入面上的（spec §4.1 / §4.2 / §4.3）------------------------
from app.db import models

# --- 7 个不在公有面上的（Plan 03 Task 2，spec §4.5 / §4.6 / §4.7）------------
# ⚠️ 不要改成 `from app.db import models` 然后用 models.Alert：AttributeError。
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)

# --- 4 个不在公有面上的（Plan 02，spec §4.4）--------------------------------
from app.db.models.prescription import (
    Exercise,
    Prescription,
    PrescriptionTemplate,
    WeeklyAdjustment,
)

__all__ = ["RESOURCES", "router"]

#: 23 个资源的声明。**顺序 = 计划读写矩阵那 23 行的顺序**，也与
#: :mod:`app.api.crud` 模块 docstring 里那张「路径 / 表 / 字段名」对照表同序，
#: 故三处可以逐行对拍。
#:
#: ⚠️ **每一行都字面写出 ``writable`` / ``on_delete`` / ``natural_key`` 三个键**，
#: 即使值等于缺省值：``on_delete`` 有缺省值 ``"restrict"``，漏写会静默落到那一档
#: （``test_every_resource_declares_on_delete_explicitly`` 断言的是**键在不在**）；
#: ``natural_key`` 在工厂里**没有**缺省值，漏写是 ``TypeError``；
#: ``writable`` 写成显式的 ``False`` 而不是省略，是为了让那份计数守卫能直接读它。
RESOURCES: tuple[dict[str, Any], ...] = (
    # -----------------------------------------------------------------------
    # spec §4.1 组织与身份（5 个，全部可写）
    # -----------------------------------------------------------------------
    {
        "model": models.Semester,
        "schemas": CrudSchemas(SemesterRead, SemesterCreate, SemesterUpdate),
        "path": "/api/semesters",
        "tags": ["semesters"],
        "writable": True,
        # 全库的时间轴锚点：9 张表按 semester_id 归组，删一个学期没有安全语义。
        # 「这个学期不要了」的正确做法是把 is_current 置 False。
        "on_delete": ON_DELETE_FORBID,
        # ⚠️ semester.name 的唯一约束**无名**（P3-B5），故 409 的消息只能引列名。
        "natural_key": ("name",),
    },
    {
        "model": models.Teacher,
        "schemas": CrudSchemas(TeacherRead, TeacherCreate, TeacherUpdate),
        "path": "/api/teachers",
        "tags": ["teachers"],
        "writable": True,
        # 有 course_section.teacher_id 子行。⚠️ mini_test.entered_by 存的是**工号字符串**、
        # 不是外键，故删教师不会带走他录的小测，_child_tables 也看不到那一层关系。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("staff_no",),  # 约束无名（P3-B5）
    },
    {
        "model": models.Student,
        "schemas": CrudSchemas(StudentRead, StudentCreate, StudentUpdate),
        "path": "/api/students",
        "tags": ["students"],
        "writable": True,
        # 子行最多的一张表（实测 12 个入向外键）。删一个学生要走学籍流程，
        # 不是 API 单点删。⚠️ notification.recipient_id 不是外键（多态），
        # 故「删学生不会带走他的通知」这一层 restrict 也看不到。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("student_no",),  # 约束无名（P3-B5）
    },
    {
        "model": models.CourseSection,
        "schemas": CrudSchemas(
            CourseSectionRead, CourseSectionCreate, CourseSectionUpdate
        ),
        "path": "/api/course-sections",
        "tags": ["course-sections"],
        "writable": True,
        # 有 enrollment / class_session / alert / weekly_class_report 四个子表。
        "on_delete": ON_DELETE_RESTRICT,
        # ⚠️ **全表没有唯一约束**（P3-B2 的三个之一）→ POST 走裸 session.add，
        # 结构上不可能撞键，故没有 409 这一档。理由：阶段一的行政班与阶段二的
        # 分层班**同名并存**是合法状态（grouping_mode 区分），而「同学期 + 同名 +
        # 同教师」算不算重复要问教务，原型不替它定。
        "natural_key": None,
    },
    {
        "model": models.Enrollment,
        "schemas": CrudSchemas(EnrollmentRead, EnrollmentCreate, EnrollmentUpdate),
        "path": "/api/enrollments",
        "tags": ["enrollments"],
        "writable": True,
        # 关联行，无子行，但删它会让名单悄悄少人（教师端的「本班学生」读它）。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("semester_id", "student_id", "course_section_id"),
    },
    # -----------------------------------------------------------------------
    # spec §4.2 学期节点数据（4 个：3 可写 + 1 只读）
    # -----------------------------------------------------------------------
    {
        "model": models.FitnessTestBatch,
        "schemas": CrudSchemas(
            FitnessTestBatchRead, FitnessTestBatchCreate, FitnessTestBatchUpdate
        ),
        "path": "/api/fitness-test-batches",
        "tags": ["fitness-test-batches"],
        "writable": True,
        # 有 fitness_test_result.test_batch_id 子行。
        "on_delete": ON_DELETE_RESTRICT,
        # ⚠️ **全表没有唯一约束**（P3-B2 的三个之一）。(semester_id, timepoint)
        # 不是唯一键：一个 week1 批次的记录横跨好几个采集日，故可以分成好几个批次
        # （fitness_test_result.tested_on 那一列的注释逐字交代了这件事）。
        # ⚠️ 代价：重复批次会让 percentile_stage「挑 <= as_of 的最新一个 week1 批次」
        # 有歧义，已登记为 Task 3 报告的关切。
        "natural_key": None,
    },
    {
        "model": models.FitnessTestResult,
        "schemas": CrudSchemas(FitnessTestResultRead),
        "path": "/api/fitness-test-results",
        "tags": ["fitness-test-results"],
        "writable": False,
        # **乐跑投影 + 批处理输入**：改它等于改原始数据，而下游的百分位快照、
        # 短板计数与趋势全部由它算出——改一行会静默改变整批学生的分层。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("test_batch_id", "student_id"),
    },
    {
        "model": models.BodyComposition,
        "schemas": CrudSchemas(
            BodyCompositionRead, BodyCompositionCreate, BodyCompositionUpdate
        ),
        "path": "/api/body-compositions",
        "tags": ["body-compositions"],
        "writable": True,
        # 无子行；restrict 是缺省档的保守侧（InBody 是人工录入的，改错请走 PATCH）。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("student_id", "measured_on"),
    },
    {
        "model": models.InterestSurvey,
        "schemas": CrudSchemas(
            InterestSurveyRead, InterestSurveyCreate, InterestSurveyUpdate
        ),
        "path": "/api/interest-surveys",
        "tags": ["interest-surveys"],
        "writable": True,
        "on_delete": ON_DELETE_RESTRICT,  # 同上：人工录入，教师要能改错
        "natural_key": ("student_id", "semester_id", "filled_on"),
    },
    # -----------------------------------------------------------------------
    # spec §4.3 派生与分层（3 个，全部只读 + forbid）
    # -----------------------------------------------------------------------
    {
        "model": models.PercentileSnapshot,
        "schemas": CrudSchemas(PercentileSnapshotRead),
        "path": "/api/percentile-snapshots",
        "tags": ["percentile-snapshots"],
        "writable": False,
        # **批处理产物**：删它的正确方式是重放（_replay_cleanup 按 batch_id 删）。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("semester_id", "computed_on", "item", "sex", "age_group"),
    },
    {
        "model": models.DerivedMetrics,
        "schemas": CrudSchemas(DerivedMetricsRead),
        "path": "/api/derived-metrics",
        "tags": ["derived-metrics"],
        "writable": False,
        "on_delete": ON_DELETE_FORBID,  # 同上：批处理产物
        "natural_key": ("student_id", "computed_on"),
    },
    {
        "model": models.StratificationResult,
        "schemas": CrudSchemas(StratificationResultRead),
        "path": "/api/stratification-results",
        "tags": ["stratification-results"],
        "writable": False,
        # 同上；且它是 **spec §4.3 可追溯性的核心**——改一行 label，
        # 那条行就无法再离线复算了。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("student_id", "computed_on"),
    },
    # -----------------------------------------------------------------------
    # spec §4.4 处方（4 个，全部只读；⚠️ 四个模型都走 app.db.models.prescription）
    # -----------------------------------------------------------------------
    {
        "model": Exercise,
        "schemas": CrudSchemas(ExerciseRead),
        "path": "/api/exercises",
        "tags": ["exercises"],
        "writable": False,
        # **参考数据**：backend/data/exercises.yaml 是唯一所有者，本表是
        # sync_exercises 的投影。开放 API 写它会让那句话变成假的——
        # 下一次 sync 会把 API 的改动静默覆盖掉。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("ref",),  # 约束无名（P3-B5）
    },
    {
        "model": PrescriptionTemplate,
        "schemas": CrudSchemas(PrescriptionTemplateRead),
        "path": "/api/prescription-templates",
        "tags": ["prescription-templates"],
        "writable": False,
        # 同上：18 套模板 YAML 是唯一所有者（sync_templates 的投影）。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("template_ref",),  # 约束无名（P3-B5）
    },
    {
        "model": Prescription,
        "schemas": CrudSchemas(PrescriptionRead),
        "path": "/api/prescriptions",
        "tags": ["prescriptions"],
        "writable": False,
        # ⚠️ **restrict 而不是 cascade**：它确实有一个真子表
        # （weekly_adjustment.prescription_id，实测 ondelete 为 None），
        # 故有微调行的处方删不掉、会得到 409 并点名 weekly_adjustment。
        # 计划里那处「处方作废则微调记录随之作废」的 cascade **不经过 DELETE 端点**，
        # 由 Task 4 的「处方被替换」路径内部使用。
        # ⚠️ 而 notification.prescription_id 带 ON DELETE SET NULL，
        # 故 _child_tables 会跳过它（P3-B4）——它确实不挡。
        "on_delete": ON_DELETE_RESTRICT,
        # 教师覆盖与状态变更走 Task 4 的特例端点：直接 PATCH 整行会让
        # training_package 与 assembly_snapshot 失去一致性。
        "natural_key": ("student_id", "generated_on"),
    },
    {
        "model": WeeklyAdjustment,
        "schemas": CrudSchemas(WeeklyAdjustmentRead),
        "path": "/api/weekly-adjustments",
        "tags": ["weekly-adjustments"],
        "writable": False,
        # 无子行。⚠️ source = "auto" 由 Task 7 的 alert_stage 写、
        # "teacher" 由 Task 4 的覆盖端点写；开放 CRUD 写它会绕过
        # WeeklyFactor 的 (0, 2] 校验（Plan 02 留给 Plan 03 的第 4 条）——
        # factor 在 DB 侧**刻意不加 CHECK**，故 API 是它唯一的闸门。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("prescription_id", "week", "reason", "source"),
    },
    # -----------------------------------------------------------------------
    # spec §4.5 反馈三源（4 个：1 可写 + 3 只读；⚠️ 都走 app.db.models.feedback）
    # -----------------------------------------------------------------------
    {
        "model": ClassSession,
        "schemas": CrudSchemas(ClassSessionRead, ClassSessionCreate, ClassSessionUpdate),
        "path": "/api/class-sessions",
        "tags": ["class-sessions"],
        "writable": True,
        # **全库唯一的 cascade**：教师建课次、取消课次，而课次取消则 rpe_record 无意义
        # （那一节课没上，学生交的快评是无效数据）。_purge_where 子表先删（P7-A4）。
        # ⚠️ 这与「ClassSession 不得进 _replay_cleanup」不矛盾：后者是**按 batch_id
        # 整批**删课次、会连带删掉学生刚交的快评；本处是教师**显式**点「取消这一节课」。
        "on_delete": ON_DELETE_CASCADE,
        "natural_key": ("course_section_id", "session_date", "period"),
    },
    {
        "model": RpeRecord,
        "schemas": CrudSchemas(RpeRecordRead),
        "path": "/api/rpe-records",
        "tags": ["rpe-records"],
        "writable": False,
        # 无子行。⚠️ 写入**只走 Task 5 的 POST /api/rpe-records**：
        # 要校验 rpe_token，且 submitted_at 必须服务端填（学生端的时钟不可信，
        # 而它是 RED_RPE_SUSTAINED「连续三次」那个判据的输入）。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("class_session_id", "student_id"),
    },
    {
        "model": TrainingLog,
        "schemas": CrudSchemas(TrainingLogRead),
        "path": "/api/training-logs",
        "tags": ["training-logs"],
        "writable": False,
        # 无子行。⚠️ 写入**只走 Task 5 的 POST /api/training-logs**：late 必须服务端算
        # （spec §8.1 的 00:00–22:00 窗口；完成率是 RCT 关键过程指标，必须严格）。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("student_id", "log_date"),
    },
    {
        "model": MiniTest,
        "schemas": CrudSchemas(MiniTestRead),
        "path": "/api/mini-tests",
        "tags": ["mini-tests"],
        "writable": False,
        # 无子行。⚠️ 写入**只走 Task 5 的 POST /api/mini-tests/batch**：
        # normalized_score 要班内百分位反查，客户端算不出来。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("student_id", "semester_id", "week"),
    },
    # -----------------------------------------------------------------------
    # spec §4.6 预警与通知（2 个，只读 + forbid，P3-B8 更正）
    # -----------------------------------------------------------------------
    {
        "model": Alert,
        "schemas": CrudSchemas(AlertRead),
        "path": "/api/alerts",
        "tags": ["alerts"],
        "writable": False,
        # ⚠️ **forbid 而不是 restrict**（P3-B8）：alert 是「哪个学生在哪一天被哪条规则
        # 标记过」的审计记录（RCT 的过程数据）。而它**今天没有子行**
        # （notification.alert_id 带 ON DELETE SET NULL，被 _child_tables 跳过），
        # 故 restrict 在这里等价于「随便删」，那会静默抹掉研究数据。
        # 由 alert_stage 生成、由 Task 7 的 POST /api/alerts/{id}/handle 处置；
        # 开放 CRUD 写它会绕过 window_key 去重（Review Focus 第 3 条）。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("rule_id", "subject_key", "semester_id", "window_key"),
    },
    {
        "model": Notification,
        "schemas": CrudSchemas(NotificationRead),
        "path": "/api/notifications",
        "tags": ["notifications"],
        "writable": False,
        # ⚠️ **forbid 而不是 restrict**（P3-B8）：它是学生看到的消息历史。
        # 且它**刻意不带 batch_id**（用户实时写入），故也**不在**重放的清单里——
        # 即「从任何入口都删不掉一行通知」，这是有意的。
        # 「已读」走 Task 8 的 POST /api/notifications/{id}/read（改 is_read，不删行）。
        "on_delete": ON_DELETE_FORBID,
        # ⚠️ **全表没有唯一约束**（P3-B2 的三个之一）。而本资源只读，
        # 故这个 None 今天**不会被 POST 用到**——写出来是为了满足工厂的必填形参，
        # 并把「这张表没有自然键」这件事留在目录里（Task 8 若要加写入方会读到它）。
        "natural_key": None,
    },
    # -----------------------------------------------------------------------
    # spec §4.7 班级周报（1 个，只读 + forbid）
    # -----------------------------------------------------------------------
    {
        "model": WeeklyClassReport,
        "schemas": CrudSchemas(WeeklyClassReportRead),
        "path": "/api/weekly-class-reports",
        "tags": ["weekly-class-reports"],
        "writable": False,
        # **批处理产物**（Task 8 的 report_stage）。5 个 JsonText 聚合列的形状由那个
        # 生成器定，从 API 改一行会让「环比流动」的基准与库里其余各行矛盾。
        "on_delete": ON_DELETE_FORBID,
        "natural_key": ("course_section_id", "semester_id", "week"),
    },
)

router = APIRouter()
for _spec in RESOURCES:
    router.include_router(build_crud_router(**_spec))
