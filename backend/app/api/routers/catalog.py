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
⚠️ 可写的那 **9** 个一律 ``require_admin=True``（用户 2026-10-08 裁定「加强制」；
⚠️ **Plan 05A Task 2 之前那一格叫 ``require_teacher=True``、判定是「任何在册教师可写」**，
用户 2026-10-12 裁定「管理员这个角色接管管理台（23 个资源的增删改查）」之后
改成「**仅管理员**可写」。⚠️ 请求头与 OpenAPI 那一格一个字都没变——
管理员就是一行 ``role='admin'`` 的 ``teacher``）
----------------------------------------------------------------------------

Plan 03 全分支终审实测：35 个 mutating 操作里只有 9 个带 ``security``、**26 个不带**
（9 POST + 9 PATCH + 8 DELETE，全是本目录那 9 个可写资源），于是零请求头连着
``POST /api/semesters → /api/teachers → /api/course-sections → /api/class-sessions``
**全部 201**，最后一行的 ``rpe_token`` 是客户端自己挑的串、随后 ``GET`` 原样返回。
⚠️ 那半句「随后 ``GET`` 原样返回」**自 Plan 03 收尾小修波起也不再可能了**：
``rpe_token`` 已从 :class:`app.api.schemas.feedback.ClassSessionRead` 上摘掉，
**且**下面 ``/api/class-sessions`` 那一行显式传了 ``"list_exclude": ("rpe_token",)``
（两半都要改——泛型 list 端点**不走** ``response_model``，只摘读模型堵不住 list）。
教师读口令走 ``GET /api/class-sessions/{id}/rpe-token``（要教师头）。

故本目录的口径是：**可写 ⇒ 挂管理员身份**（``POST`` / ``PATCH`` / ``DELETE`` 三个端点各挂
``Security(TEACHER_STAFF_NO_SCHEME)`` + :func:`app.api.crud._require_admin_identity`，
缺身份 **401**、工号不在册 **403**、在册但 ``role != 'admin'`` **403**）。
⚠️ ``semesters`` 是 ``on_delete="forbid"``、不注册 DELETE，故 26 而不是 27。

----------------------------------------------------------------------------
⚠️⚠️ **读侧的四档口径（安全收紧波改写；Plan 06 Task 8 加第四档。
本段是全仓「哪些读今天还匿名」的唯一住址）**
----------------------------------------------------------------------------

Plan 04 Task 3 的偏离 ⑦ 定的是「**只读 ⇒ 一律匿名**」，当时的论证逐字是
「在不加强制的前提下声明 security 是一份反方向的假契约」——而那句话的**前提**是
「本系统不做真实鉴权」。Plan 05A 做了真实鉴权，于是前提没了；Plan 05A Task 5
把 48 个匿名 GET 逐个重新裁定成 **44 匿名 + 4 仅教职**；
**安全收紧波再把那 44 个里的一批收掉**，理由是终审 I6：

    那 44 个匿名 GET 里没有一个返回验身材料或人名，**但放行了整套以
    ``student_id``（1–60 的小整数）为键的健康档案** —— 体成分、体测原始值 + 6 项得分、
    分层 ``label`` + ``hit_rules``、``body_comp_abnormal``、处方、840 条训练日志、
    240 条 RPE、32 条预警、19 条站内消息（标题 + 正文）、兴趣问卷，
    以及 ``enrollments``（谁在哪个班）。**任何已登录的学生只要把 cookie 丢掉，
    就能匿名读全校 60 人的健康档案。**

⚠️⚠️ **Plan 06 Task 8 收的是同一个洞的第二半**（用户裁定「教师账号之间要有数据隔离」）：
安全收紧波之后，那 13 个资源对**任何在册教师**仍然是**全校全读**——
一个教师登录进去就能读到全校 60 人的健康档案，而「教师只能读自己任教的班/学生」
那道闸门（:func:`app.api.deps.require_teaches_student`）当时只挂在教师端那几个
**按人收窄**的特例端点上（``/api/teacher/students/{id}/home`` 与 ``weekly-sheet``）。
本波把它扩到泛型读，做法是第四档 ``"staff_taught"``（**不是**逐行去查任教关系，
而是**一次** ``IN (子查询)``，故查询次数与改前同阶）。

于是本目录的读侧口径是**四档**（逐字的判定表住在
:data:`app.api.crud.READ_SCOPE_STUDENT_SELF` 的注释里，本处只记**行数与名单**）：

======================  ====  ====================================================
``read_scope``           行数   哪几行
======================  ====  ====================================================
``None``（**仍匿名**）     **7**  ``semesters`` / ``course-sections`` /
                                ``fitness-test-batches`` / ``percentile-snapshots`` /
                                ``exercises`` / ``prescription-templates`` /
                                ``class-sessions``
``"student_self"``        **0**  （本波 13 行全部改成下面那一档；保留这一档的理由
                                逐字见 :data:`app.api.crud.READ_SCOPE_STUDENT_SELF`）
``"staff_taught"``       **13**  ``enrollments`` / ``fitness-test-results`` /
                                ``body-compositions`` / ``interest-surveys`` /
                                ``derived-metrics`` / ``stratification-results`` /
                                ``prescriptions`` / ``weekly-adjustments`` /
                                ``rpe-records`` / ``training-logs`` / ``mini-tests`` /
                                ``alerts`` / ``notifications``
``"staff"``               **3**  ``students`` / ``teachers`` / ``weekly-class-reports``
======================  ====  ====================================================

⚠️ **7 个仍匿名的都不含任何学生键**，逐行的判断依据写在各自那一行的注释里
（``class-sessions`` 与 ``percentile-snapshots`` 两行是裁定 4 点名要复核的，
故它们的注释最长）。

⚠️ **13 个 ``staff_taught`` 里有 2 个不是「含 ``student_id`` 列」那个谓词能挑出来的**：
``notifications`` 是**多态键**（``recipient_id`` + ``recipient_kind == 'student'``），
``weekly-adjustments`` 是**间接键**（``prescription_id`` → ``prescription.student_id``）。
两者都由 :class:`app.api.crud.StudentOwner` 的三档形状表达，逐行依据写在各自注释里。
⚠️ 于是「含 ``student_id`` 列 ⇒ 必须声明按学生键收窄的那两档之一」这条守卫
（``test_every_student_keyed_resource_declares_a_student_scoped_read_scope``）
**只覆盖 11 行**，另 2 行由「23 行一律字面写出这个键」那条守卫兜住——
两条各钉一半，少了任何一条，「加第 24 个资源而忘了声明」都是静默的。

⚠️ **特例端点不在本目录**（``GET /api/students/{id}/home`` / ``weekly-sheet`` /
``training-logs/completion-rate`` / ``mini-tests/normalized`` / ``teacher/students/*`` /
``dashboard/*``），它们各自已有身份与范围闸门。
⚠️⚠️ 其中 ``GET /api/mini-tests/normalized`` 曾是本目录点名的那扇「还没关的门」
（它当时**匿名**、且回 ``student_id`` + 三个分数），**交付前收尾波 ③ 已经关上**：
今天它挂 ``Security(STUDENT_ID_SCHEME)`` + ``Security(TEACHER_STAFF_NO_SCHEME)``
（OR 语义：学生或教职皆可，匿名 **401**），判定走
:func:`app.api.deps.current_reader`，且对**学生档做了列级收窄** ——
``entries[i].squat_score`` 实测**就是** ``mini_test.squat_30s_count``（逐行相等）、
``composite`` 又能把它反推出来，故那两格对别人的行一律置 ``None``，
而全班的 ``shuttle_score``（百分位）照常给（学生端要它算名次）。
逐字取证与两条路的取舍住在
:func:`app.api.routers.feedback.normalized_scores` 的 docstring。
⚠️⚠️ **Plan 06 Task 8 又给它加了行级收窄**（派单 §2 点名要一起关的那个跨范围洞）：
收尾波之后它对**教师**没有任何任教闸门，故任何教师能读到全校 5 个班的班内百分位；
今天学生只读得到**自己 enrolled 的班**、教师只读得到**自己任教的班**、管理员全读。
⚠️ 而它**没有** ``course_section_id`` 这个查询参数（派单 §2 的「否则 403」在实测下
无对象），故收窄是**响应级**的（``sections`` 数组按身份裁），不是 ``403``。
⚠️ 于是「匿名 GET」那一档今天**再没有任何一格含 ``student_id``**：
上面那 7 个参考数据资源的集合与成员 GET 全是群体/班级/批次级，
``percentile-snapshots`` 那 14 列实测一个学生键都没有。

⚠️⚠️ **两格已知局限（Plan 06 Task 8 如实记录，硬规矩 #39）**：

1. ``"staff_taught"`` 的判据是**学生键**，故一行**没有学生所有者**的数据对任何教师
   都不可见（只有管理员读得到）：**班级级预警**（``alert.student_id IS NULL`` +
   ``course_section_id``，由 ``alert_stage.evaluate_alerts`` 末段那个班级级循环产出）
   与**发给教师的站内信**（``notification.recipient_kind='teacher'``，由同一段的
   ``_notify`` 产出）。⚠️ 演示库上两者实测各 **0 行**（``YELLOW_CLASS_RPE_HIGH``
   差 0.07 没越线），故既有测试与 ``smoke.mjs`` 都看不见这一格；
   而它是**功能回归**（教师看不到本该他处置的班级级预警）。已顶回给控制者。
   守卫是 ``tests/api/test_crud.py`` 的
   ``test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin``
   （把这一档**钉住**，将来修它的人会先看到那条守卫红）。
2. ``"staff"`` 那一档的 ``weekly-class-reports`` **仍然跨教师**：泛型 read-one
   含全部 JSON 列，故任何在册教师能读到**别的班**那份周报的 ``progress_board``
   （= 那个班进步榜 top 10 的 ``student_id`` + ``change_pct``）。派单 §1 末段逐字要求
   「保持 ``staff`` 档不动」，本波照办并**已顶回**（收它要第五档，键换成班）。

守卫（都在 ``tests/api/test_crud.py``）：
``test_every_resource_declares_read_scope_explicitly``（**键在不在**，缺省值不算显式）、
``test_every_student_keyed_resource_declares_a_student_scoped_read_scope``（遍历 28 张表）、
``test_the_student_keyed_resources_admit_four_read_tiers``（**实发请求**断四档矩阵：
匿名 401 / 学生自己 200 / 学生别人 403 / **教师自己班 200** / **教师别人班 403** /
管理员 200）。
⚠️ 写入侧那两条守卫不变：
``test_every_writable_resource_declares_require_admin_explicitly``（**键在不在**）与
``test_every_writable_resource_admits_only_an_admin_mutation``
（遍历 ``RESOURCES`` **实发请求**：可写的断 401、只读的断 405）。
⚠️ 后者**必须**用实发请求或 ``app.openapi()["paths"]``，**不能用 ``app.routes``**：
FastAPI 0.141.1 的 ``include_router`` 是惰性的（折叠成一个 ``_IncludedRouter``），
``len(app.routes)`` 实测只有 **6**，按它写的守卫会假绿
（那条警告的住址是 :mod:`app.api.routers` 的模块级注释）。

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
    READ_SCOPE_STAFF,
    READ_SCOPE_STAFF_TAUGHT,
    CrudSchemas,
    StudentOwner,
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
#:
#: ⚠️ **可写的那 9 行另外字面写出 ``"require_admin": True``**（只读的 14 行省略它）：
#: 它在工厂里有缺省值 ``False``，漏写就静默退回「匿名可写」——那是终审那个
#: 「26 个 mutating 操作不带 ``security``」的失效形态本身。守卫是
#: ``test_every_writable_resource_declares_require_admin_explicitly``（键在不在）
#: 与 ``test_every_writable_resource_admits_only_an_admin_mutation``
#: （实发请求断三拍：匿名 401 / 普通教师 403 / 管理员放行）。
#: ⚠️ **Plan 05A Task 2 之前这个键叫 ``require_teacher``**（判定是「任何在册教师可写」）。
#: 改名之后 9 行的**值**逐字不变（都是 ``True``），变的是工厂里那一道判定
#: （:func:`app.api.crud._require_admin_identity` → :func:`app.api.deps.require_admin`）。
#: ⚠️ 只读那 14 行**不该**写 ``True``：工厂体里的第 7 道校验会在导入期响
#: （只读资源根本不注册 POST/PATCH/DELETE，挂上去是一件什么也不发生的事）。
RESOURCES: tuple[dict[str, Any], ...] = (
    # -----------------------------------------------------------------------
    # spec §4.1 组织与身份（5 个，全部可写）
    # -----------------------------------------------------------------------
    {
        "model": models.Semester,
        "schemas": CrudSchemas(SemesterRead, SemesterCreate, SemesterUpdate),
        "path": "/api/semesters",
        "tags": ["semesters"],
        # ⚠️ **安全收紧波：23 行一律字面写出 ``read_scope``**（``None`` 也写）。
        # 它有缺省值 ``None``，故「忘了写」与「写了 None」在行为上无法区分，
        # 而失效方向是**静默地退回匿名可读**。守卫是
        # ``tests/api/test_crud.py::test_every_resource_declares_read_scope_explicitly``。
        # 本行是 ``None``：学期是全库的时间轴锚点，**不含任何学生键**，
        # 且登录前的页面要用它（裁定 4）。
        "read_scope": None,
        "writable": True,
        "require_admin": True,
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
        "require_admin": True,
        # ⚠️⚠️ **Plan 05A Task 5：本行的两个 GET 从「匿名」改成「要教职身份」**。
        # 理由（逐字版住在 ``app/api/crud.py`` 的 ``_require_staff_identity``）：
        # ``TeacherRead`` 含 ``staff_no`` **与** ``name``，而那两格合起来正是
        # ``POST /api/auth/teachers/bind`` 的**全部**验身材料 —— 匿名可读时，
        # 「读过一次 GET /api/teachers 的人」可以给**任何**工号绑一个自己知道的口令、
        # 然后登录成他；⚠️ 而 ``role`` 也在同一个响应体里，故他能挑一个
        # ``role='admin'`` 的工号（``bind`` 不看 role、也不改 role，
        # 但登录之后他就是那个管理员）。
        # ⚠️ 这一格**比学生那一侧更严重**（学生至少还要一个 ``birth``），
        # 而计划 §3.2 与派单都只点了学生那一侧 —— 实现者实测复核后一并收紧。
        # ⚠️ **安全收紧波把这一格从布尔开关 ``read_requires_staff: True`` 改成
        # ``read_scope: READ_SCOPE_STAFF``**（行为逐字不变：同一个
        # ``_require_staff_identity``、同一个 ``Security(TEACHER_STAFF_NO_SCHEME)``），
        # 理由与四档表住在 ``app/api/crud.py`` 的 ``READ_SCOPE_STUDENT_SELF`` 注释里。
        "read_scope": READ_SCOPE_STAFF,
        # ⚠️ **Plan 05A Task 1 加的第二个显式 list_exclude**（此前 23 行里只有
        # class-sessions 一行）：``password_hash`` 是凭据，而泛型 list **不走
        # response_model**（它显式只 SELECT kept 那些列、手工拼 dict），故光是把它从
        # ``TeacherRead`` 上摘掉**堵不住本端点**——那一列留在这里等于把全校教师的
        # 口令哈希摊给任何读得到本端点的人。
        # ⚠️⚠️ **本处此前逐字写的是「``GET /api/teachers`` 是匿名的」，而那半句
        # 自它上面 4 行的 ``read_requires_staff`` 落地起就已经假了**（待清扫波真 HTTP
        # 实测：匿名打过去是 **401**）——同一屏里两行注释互相打脸，而照上面那半句读的人
        # 会以为本端点没有身份闸门。⚠️ 本行**照旧要**：它是纵深防御的第二层，
        # 闸门哪天为别的理由放开时凭据仍然不在响应体里。
        # 另一半（读模型）住在 ``TeacherRead``，守卫是 tests/api/test_crud.py 的
        # test_every_resource_list_omits_json_text_columns_and_read_one_includes_them。
        # ⚠️⚠️ **``password_bound_at`` 自安全收紧波起也排**（此前本处逐字写的是
        # 「**不排**：它不是凭据，而管理台要看『谁还没注册』」）。理由与代价逐字见
        # ``app/api/schemas/organisation.py`` 的 ``TeacherRead``（刻意不抄第二份）：
        # 一句话是它告诉一个教职「哪些工号还没绑口令」= **哪些还能被抢占绑定**。
        # ⚠️ 读模型那一半（``TeacherRead`` 摘列）与档 2 清单
        # （``tests/api/test_crud.py`` 的 ``_SERVER_GENERATED_HIDDEN_COLUMNS``）
        # 都要跟着改，三处缺一不可——泛型 list **不走** ``response_model``，
        # 只摘读模型堵不住本端点。
        "list_exclude": ("password_hash", "password_bound_at"),
        # 有 course_section.teacher_id 子行。⚠️ mini_test.entered_by 存的是**工号字符串**、
        # 不是外键，故删教师不会带走他录的小测，_child_tables 也看不到那一层关系。
        # ⚠️ **Plan 05A 又加了一层同型的关系**：``user_session.subject_id`` 刻意不是外键
        # （多态外键在 SQL 里不存在），故删一个教师**不会**级联吊销他的会话行，
        # ``_child_tables`` 也探测不到它。处置是登录/解析时回查 subject 行、
        # 查无此人当场吊销（``app.auth.sessions.resolve``），逐字理由见
        # ``app/db/models/auth.py`` 的模块 docstring 第二节。
        "on_delete": ON_DELETE_RESTRICT,
        "natural_key": ("staff_no",),  # 约束无名（P3-B5）
    },
    {
        "model": models.Student,
        "schemas": CrudSchemas(StudentRead, StudentCreate, StudentUpdate),
        "path": "/api/students",
        "tags": ["students"],
        "writable": True,
        "require_admin": True,
        # ⚠️⚠️ **Plan 05A Task 5：本行的两个 GET 从「匿名」改成「要教职身份」**。
        # ``StudentRead`` 含 ``birth``，而 ``birth`` 正是
        # ``POST /api/auth/students/bind`` 的验身材料 —— 匿名可读时，
        # 「读过一次 GET /api/students 的人」可以给任何学号绑一个自己知道的口令、
        # 然后登录成他。⚠️ 这一格是 Plan 05A Task 1+2 的实现者查出来的、
        # 控制者的计划完全漏掉的（计划 §3.2 只把它登记为「已知局限」）。
        # ⚠️ 处置取的是派单给的 **(b)**「整个改成需要登录」而不是 (a)「把 ``birth``
        # 从 ``StudentRead`` 与泛型 list 里摘掉」，三条理由逐字见
        # ``app/api/crud.py`` 的 ``_require_staff_identity`` 与本波实现者报告的 §5。
        # ⚠️ 安全收紧波：与 teachers 那一行同一次改名（``read_requires_staff`` →
        # ``read_scope``），行为逐字不变，刻意不抄第二份散文。
        "read_scope": READ_SCOPE_STAFF,
        # ⚠️ Plan 05A Task 1：与 teachers 那一行同一条理由（凭据不得匿名可读），
        # 刻意不抄第二份散文。
        # ⚠️ 安全收紧波：``password_bound_at`` 也排（与 teachers 那一行同一次改动，
        # 理由与「三处缺一不可」的形状住在那一行的注释里，刻意不抄第二份）。
        "list_exclude": ("password_hash", "password_bound_at"),
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
        # 班级名册（行政班 + 分层班）：键是 ``semester_id`` / ``teacher_id``，
        # **不含任何学生键**（「谁在这个班」住在 ``enrollment``，那一行已收紧），
        # 且登录前的页面与大屏要用它 → 保持匿名（裁定 4）。
        "read_scope": None,
        "writable": True,
        "require_admin": True,
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
        # ⚠️⚠️ **安全收紧波收紧的第一个「双键」资源**（派单 §2 点名它：
        # 「推断就是第二个所有者，且会漏掉 ``enrollments`` 这种双键的」）。
        # 它身上没有一列健康数据，而 ``student_id ↔ course_section_id`` 这一对
        # **就是「谁在哪个班」**：拿到它 + 那 60 人的 ``student.id`` 是 1..60 的
        # 小整数，任何匿名调用方都能把「学生 4 在 1 班」与别的表拼起来。
        # 三档：匿名 **401** / 学生会话只读**自己**的选课行 / 教职全读
        # （教师端 ``Dashboard.vue`` 与 ``AlertQueue.vue`` 都读它按班筛人）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
        "writable": True,
        "require_admin": True,
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
        # 批次是「哪一次采集」：``semester_id`` / ``timepoint`` / ``test_date``，
        # **不含任何学生键**（逐人的成绩在 ``fitness_test_result``，那一行已收紧）
        # → 保持匿名（裁定 4）。
        "read_scope": None,
        # ⚠️ **23 行里唯一显式传 pk_alias 的一行**（Plan 03 Task 4 的 P4-A6）。
        # 自动推导是「去掉末尾一个 s + 连字符换下划线 + _id」，它对 -es 结尾的复数
        # 会多留一个 e（推出 "fitness_test_batche_id"），而那正是本资源名的形状。
        # 处置不是把推导改聪明（英语复数还原有例外，写一份后缀表必然不完备，
        # 且那是给一个 URL 命名问题引入第二份词表），而是**显式覆盖这一个**。
        # 完整理由在 app.api.crud._pk_alias_of 的 docstring 末段；守卫是
        # tests/api/test_crud.py 的 test_every_detail_path_names_its_pk_after_the_resource
        # （23 个名字逐个从 /openapi.json 实读，字面清单里写的是 fitness_test_batch_id）。
        "pk_alias": "fitness_test_batch_id",
        "writable": True,
        "require_admin": True,
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
        # ⚠️ 学生键：体测**原始值 + 6 项得分**（21 列，23 个资源里字段最多的一个）。
        # 三档口径与「为什么 23 行一律字面写 read_scope」住在上面 ``semesters`` 那一行。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️ 学生键：体成分（``muscle_mass_kg`` / ``body_fat_pct`` / ``smi`` /
        # ``weight_kg``）—— 终审 I6 点名的第一类健康档案。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
        "writable": True,
        "require_admin": True,
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
        # ⚠️ 学生键：兴趣问卷（``raw_answers`` 是逐人的自由作答）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
        "writable": True,
        "require_admin": True,
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
        # **不含任何学生键**（实测 14 列：``semester_id`` / ``batch_id`` / ``item`` /
        # ``sex`` / ``age_group`` / 五个分位数 / ``sample_size`` / ``source``）：
        # 它是**群体**统计，一行对应「某学期某项目某性别某年龄组的 P10..P75」，
        # 没有任何一格能落到一个人身上 → 保持匿名（裁定 4；学生端的「班内百分位」
        # 读的是 ``/api/mini-tests/normalized``，那是另一个端点）。
        "read_scope": None,
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
        # ⚠️ 学生键：派生指标（含 ``body_comp_abnormal`` 那一格「体成分异常」判定）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
        "writable": False,
        "on_delete": ON_DELETE_FORBID,  # 同上：批处理产物
        "natural_key": ("student_id", "computed_on"),
    },
    {
        "model": models.StratificationResult,
        "schemas": CrudSchemas(StratificationResultRead),
        "path": "/api/stratification-results",
        "tags": ["stratification-results"],
        # ⚠️ 学生键：分层结果（``label`` + ``hit_rules``）—— 终审 I6 点名的
        # 「谁被分到红/黄/绿层、因为命中了哪几条规则」。
        # ⚠️ 教师端 ``StudentDetail.vue`` 读它渲染某个学生的分层，故教职那一档必须全读。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # **动作库**（参考数据）：``backend/data/exercises.yaml`` 的投影，
        # 一行是一个动作定义，**不含任何学生键** → 保持匿名（裁定 4）。
        "read_scope": None,
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
        # **18 套模板**（参考数据）：模板 YAML 的投影，**不含任何学生键**
        # → 保持匿名（裁定 4）。
        "read_scope": None,
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
        # ⚠️ 学生键：运动处方整行（含 ``training_package`` / ``assembly_snapshot`` /
        # ``label_at_generation``）。⚠️ 学生端**不**读它（它走
        # ``/api/students/{id}/prescriptions/current`` 与 ``weekly-sheet`` 两个窄端点，
        # 各自已有 ``require_scope`` / ``require_teaches_student`` 闸门）；
        # 本行收的是**泛型**那一圈（管理台与任何匿名调用方）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️⚠️ **间接学生键**（裁定 1 点名要逐个判断的那一个；本波实测后**收**）。
        # 它身上**没有**学生列，而 ``prescription_id`` 指向的 ``prescription`` 行上有。
        # 实测依据（演示库，只读）：``prescription`` **60 行** / ``student`` **60 人**
        # → ``prescription.id`` 与 ``student.id`` 一一对应，故 ``prescription_id``
        # **就是一个学生代理键**；而本表的 ``reason`` 实测是
        # ``RED_RPE_SUSTAINED`` / ``RED_MINITEST_DROP`` 这类**分层规则码**——
        # 合起来等于「全校谁被降了量、因为他是红层且 RPE 持续偏高」，
        # 与 ``stratification_result`` 的 ``label`` + ``hit_rules`` 是同一类信息。
        # ⚠️ 代价：**前端没有一个页面读它**（实测 ``views/**`` 里
        # ``listWeeklyAdjustments`` / ``readWeeklyAdjustment`` 零调用，
        # 只有管理台的泛型 ``listResource`` 会走到，而管理员已登录 → 教职全读）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        # ⚠️ ``via`` 那一档：过滤在 SQL 层是
        # ``WHERE prescription_id IN (SELECT id FROM prescription WHERE student_id = :me)``，
        # read-one 则取中间行上的 ``student_id`` 交给 ``require_scope``。
        # 两者读**同一份**声明（``StudentOwner`` 的 docstring 逐字交代了这个形状）。
        "student_owner": StudentOwner(
            column="prescription_id", via=("prescription", "student_id")
        ),
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
        # **保持匿名**（裁定 4 点名要复核的那一行；本波实测后的判断依据如下）。
        # ① 键是 ``course_section_id`` / ``session_date`` / ``period``，
        #    **不含任何学生键**（谁交了快评在 ``rpe_record``，那一行已收紧）。
        # ② 它身上唯一的秘密是 ``rpe_token``，而**两侧都已经摘掉了**：
        #    read-one 走 ``response_model=ClassSessionRead``，那一列自 Plan 03
        #    收尾小修波起不在模型上；list **不走** ``response_model``，
        #    故下面那一行显式的 ``"list_exclude": ("rpe_token",)`` 是另一半。
        #    ⚠️ 两半缺一不可（只摘读模型的话 ``GET /api/class-sessions`` 照旧原样返回）。
        # ③ 剩下 5 列（``session_date`` / ``period`` / ``rpe_opened`` /
        #    ``course_section_id`` / ``batch_id``）是「哪一节课什么时候上、快评开了没」，
        #    而学生端 ``RpeEntry.vue`` 正是要读它才知道该给哪节课交快评。
        "read_scope": None,
        "writable": True,
        "require_admin": True,
        # **全库唯一的 cascade**：教师建课次、取消课次，而课次取消则 rpe_record 无意义
        # （那一节课没上，学生交的快评是无效数据）。_purge_where 子表先删（P7-A4）。
        # ⚠️ 这与「ClassSession 不得进 _replay_cleanup」不矛盾：后者是**按 batch_id
        # 整批**删课次、会连带删掉学生刚交的快评；本处是教师**显式**点「取消这一节课」。
        "on_delete": ON_DELETE_CASCADE,
        "natural_key": ("course_section_id", "session_date", "period"),
        # ⚠️⚠️ **23 行里唯一一行显式传 list_exclude**（Plan 03 收尾小修波）。
        # 它是「rpe_token 不再匿名可读」这件事的**另一半**，缺了它洞根本没堵上：
        # 泛型 list 端点**不走 response_model**（app.api.crud 的那个端点显式只
        # SELECT kept 那些列、手工拼 dict，理由是含全部列的 response_model 会让
        # defer 掉的 JsonText 列触发 N+1），故把 rpe_token 从 ClassSessionRead 上
        # 摘掉**只堵住了 read-one / POST / PATCH 三个端点**，
        # 而 `GET /api/class-sessions`（**正是终审点名的那个 URL**）照旧原样返回它。
        # ⚠️ 于是那一格必须在这里也排掉。两侧各自有一份守卫：
        # read 模型那一侧是 tests/api/test_crud.py 的
        # _SERVER_GENERATED_HIDDEN_COLUMNS，list 那一侧是
        # test_every_resource_list_omits_json_text_columns_and_read_one_includes_them
        # 里新加的那两拍 + tests/api/test_feedback.py 的
        # test_the_rpe_token_is_absent_from_the_anonymous_class_session_read_response。
        # ⚠️ 本表一个 JsonText 列都没有，故显式元组**覆盖**掉自动探测的空元组，
        # 排掉的只有这一列（read-one 仍然不含它——它已经从 read 模型上摘掉了）。
        "list_exclude": ("rpe_token",),
    },
    {
        "model": RpeRecord,
        "schemas": CrudSchemas(RpeRecordRead),
        "path": "/api/rpe-records",
        "tags": ["rpe-records"],
        # ⚠️ 学生键：课堂快评（240 行）。⚠️ 学生端 ``RpeEntry.vue`` 经
        # ``endpoints.ts`` 的 ``listMyRpeRecords``（翻页收集 + 客户端过滤）读它——
        # 收紧之后**服务端已经过滤**，那一次客户端 ``filter`` 变成 no-op（仍然正确），
        # 而 ``truncated`` 那一格从「840 行撞到 cap」变成「我自己的 4 行」，语义更准。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️ 学生键：训练打卡（**840 行**，全库最大的一张表；含 ``feeling`` /
        # ``duration_min``）。⚠️ 这一行是派单 §2 第 2 条「过滤要在 SQL 层做」的
        # 全部理由：60 人 × 14 天，拉全量再在 Python 里筛会让 ``LIMIT 200``
        # 先截断**别人的**行。学生端 ``CheckIn.vue`` 经 ``listMyTrainingLogs`` 读它。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️ 学生键：二次小测（180 行）。⚠️ **两个**消费者，收紧后各自的行为：
        # ① 学生端 ``MiniTest.vue`` 拉 ``listMiniTests({limit:200})`` 再
        #    ``filter(row => row.student_id === id)`` → 服务端已过滤，那一次 filter
        #    变成 no-op（仍然正确）；
        # ② 教师端 ``StudentDetail.vue`` 拉全表按某个学生筛 → 教职全读，不受影响。
        # ⚠️ 而 ``GET /api/mini-tests/normalized``（班内百分位）是**特例端点**、
        # 不在本行范围内。⚠️⚠️ 本处此前印的是「它今天匿名，回的是 ``student_id`` +
        # 三个分数；派单裁定 2 明写特例端点本波不动，已登记为待清扫」——
        # **交付前收尾波 ③ 已经把它关上了**（学生或教职皆可、匿名 401，
        # 且学生档的 ``squat_score`` / ``composite`` 两格对别人的行置 ``None``：
        # 实测 ``squat_score`` 逐行等于本行资源的 ``squat_30s_count``）。
        # 逐字取证住在 :func:`app.api.routers.feedback.normalized_scores` 的 docstring。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️ 学生键：预警（32 行，含 ``level`` / ``rule_id`` / ``trigger_snapshot``）。
        # ⚠️ ``student_id`` 这一列**可空**（实测 ``nullable=True``：班级级预警没有主人），
        # 故 ``WHERE student_id = :me`` 对 NULL 行天然不匹配（SQL 三值逻辑），
        # 而 read-one 那一侧 ``_owner_of_row`` 把 NULL 折成 ``NOT_STUDENT_OWNED``
        # → ``require_scope`` 403。两档都不会把无主的行给学生。
        # ⚠️ 教师端 ``AlertQueue.vue`` / ``Dashboard.vue`` / ``StudentDetail.vue``
        # 都读全表 → 教职全读那一档是承重的。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(column="student_id"),
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
        # ⚠️⚠️ **多态学生键**（本波实测查出来的、派单那份清单里没有的一行）。
        # 它身上**没有** ``student_id`` 列，故「含 ``student_id`` 列」这个谓词
        # **会漏掉它** —— 而那正是派单 §2 逐字警告「不要靠推断」的实证。
        # 实测（演示库，只读）：``notification`` **19 行**，``recipient_kind`` 的分布是
        # ``{('student', 19)}``（**全部**发给学生），``recipient_id`` 就是 ``student.id``；
        # 而 ``NotificationRead`` 含 ``title`` **与** ``body``，实测正文是
        # 「本周训练完成度 100%，而且二次小测有指标在进步…」这类**逐人的健康反馈**。
        # ⚠️ ``recipient_kind`` 的取值域实测是 ``{'student', 'teacher'}``
        # （:attr:`app.db.models.feedback.Notification.RECIPIENT_KINDS`），
        # 故 ``StudentOwner.kind`` 那一格是**承重的**：少了它，学生 4 会读到
        # 发给**教师 4** 的站内信（两个 id 空间是独立的自增序列，必然重叠）。
        # ⚠️ 学生端**不**读泛型这一圈：``Notifications.vue`` 走
        # ``GET /api/students/{id}/notifications``（特例、学生头、服务端已过滤）。
        # 泛型这一圈的消费者只有管理台（管理员已登录 → 教职全读）。
        "read_scope": READ_SCOPE_STAFF_TAUGHT,
        "student_owner": StudentOwner(
            column="recipient_id", kind=("recipient_kind", "student")
        ),
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
        # ⚠️⚠️ **班级键、但内含学生级数据**（裁定 1 点名要逐个判断的第三个；
        # 安全收紧波实测后**收成仅教职**，而不是按学生键收窄的那两档）。
        # 实测（演示库，只读）：``progress_board`` 那个 JSON 列里**逐条带
        # ``student_id`` + ``change_pct``**——原文开头逐字是
        # ``{"top_n": 10, "top": [{"student_id": 10, "change_pct": 235.88}, …]}``，
        # 即「本周进步榜 top 10」。故它虽然是班级键，却把**哪 10 个学生进步最多、
        # 各自涨了多少**摊给任何匿名调用方。
        # ⚠️ **为什么不是 ``student_self`` / ``staff_taught``**：``student_id`` 埋在
        # 一个 JSON 列**里面**，SQL 层的 ``WHERE`` 够不着它（要做到就得把那一列拆成子表，
        # 那是一次 schema 改动、超出范围；安全收紧波已把它登记为待清扫）。
        # 而它的**唯一**前端消费者是教师页
        # ``views/teacher/ClassReport.vue``（``listWeeklyClassReports({limit:200})``，
        # 已在 ``/t/*`` 的路由守卫之后），学生端一个页面都不读它 ——
        # 故收成「仅教职」既关掉了匿名那一档，又不破坏任何既有页面。
        # ⚠️ 代价（如实记）：一个**学生**从此读不到自己班的周报（跨 kind 被拒）。
        # 学生端要看班级数据走 ``/api/dashboard/*``，而那些端点今天已经各自挂身份。
        # ⚠️⚠️ **Plan 06 Task 8 复核出它仍然跨教师**（派单 §1 末段点名要复核的那一条，
        # 已顶回）：``read_scope="staff"`` 是「任何在册教职全读」，而泛型 **read-one**
        # 含全部 JSON 列，故任何教师能 ``GET /api/weekly-class-reports/{别的班的 id}``
        # 读到那个班的 ``progress_board``（top 10 的 ``student_id`` + ``change_pct``）
        # 与 ``layer_distribution`` / ``alert_summary`` 等四个聚合列。
        # ⚠️ 特例端点 ``GET /api/dashboard/weekly-class-report/{id}`` 有自己的
        # :func:`app.api.deps.require_teaches_section`，故**前端页面上看不出这一格**
        # （``ClassReport.vue`` 的选班下拉逐字写着「只列我任教的」）。
        # ⚠️ 派单逐字要求「保持 ``staff`` 档不动」，本波照办；收它要第五档
        # （``WHERE course_section_id IN (我本学期任教的班)``，与第四档同构、键换成班），
        # 而它**不能**复用 :class:`app.api.crud.StudentOwner`（那是学生键的声明）。
        "read_scope": READ_SCOPE_STAFF,
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
