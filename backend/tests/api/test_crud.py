"""泛型 CRUD 工厂（:mod:`app.api.crud`）与 :mod:`app.api.routers.catalog` 的 23 个资源。

**本文件分三批**（与本 Task 的三个 commit 对应）：

* **批次 A**——计划 Step 1 点名的那些，用 ``semester``（最简单的可写资源）、``teacher``
  （可写 + ``restrict`` + 无子行，故 DELETE 真的能 204）与 ``stratification_result``
  （只读 + 带一个 ``JsonText`` 列）把五个端点跑通；
* **批次 B**——遍历型守卫：23 行 ``RESOURCES`` 的计数、import 路径（P3-B1）、自然键
  （P3-B2）、``list_exclude`` 的自动探测（P3-B3）、``_child_tables`` 对
  ``SET NULL``/``CASCADE`` 的排除（P3-B4）、409 消息不含字面 ``"None"``（P3-B5）；
* **批次 C**——两个「有能力、无生产调用方」的工厂参数（``readable`` 与
  ``list_exclude`` 的显式覆盖）各一条，使它们不是死代码（硬规矩 #39）。
  ⚠️ ``list_exclude`` 那一半自 Plan 03 收尾小修波起**有了生产调用方**
  （``/api/class-sessions`` 用它排掉秘密列 ``rpe_token``），故批次 C 那条现在钉的是
  「显式覆盖 + 不影响 read-one」这个分支本身，理由逐字见它的 docstring。

⚠️ **``semester`` 的 ``on_delete`` 是 ``forbid``**（读写矩阵第 1 行），故计划 Step 1 那条
``test_delete_returns_204_and_the_row_is_gone`` **不能用它**——本文件改用 ``teachers``。
同理 ``test_a_forbidden_delete_is_405_even_on_a_writable_resource`` 才由 ``semesters`` 承担。

⚠️ **计划 Step 1 还列了三条错误映射测试**（``ValueError`` → 422 / ``IntegrityError`` → 409 /
未处理异常 → 500）。**本文件刻意不重复它们**：那三条已经由 Plan 03 Task 1 交付在
``tests/test_main.py``（``test_domain_value_error_maps_to_422`` /
``test_integrity_error_maps_to_409`` / ``test_unhandled_exception_maps_to_500_without_leaking_the_stack``），
被测对象是 :func:`app.api.errors.register_error_handlers` 的**接线**，与本文件被测的
「工厂生成的端点」是两个所有者。本文件只测**CRUD 自己会抛的那几个码**
（404 / 409 / 405 / 422），它们同样穿过那份统一形状。

**``_seed_one_row_per_table`` 是本文件的承重夹具**：批次 B 的
``test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`` 要在
**23 个资源上逐个**比对 list 与 read-one 的键集合，而空库上的 ``items == []`` 会让
「list 里一个 ``JsonText`` 列都不出现」**恒真**（硬规矩 #50 的反面：一条空转的守卫与一条
真的守卫在颜色上无法区分）。故它按外键拓扑序往 24 张表各插一行，且每个 ``JsonText`` 列
都填**非空**的值。
"""
import ast
import datetime as dt
import inspect
import json
import pathlib

import pytest
from fastapi import HTTPException
from sqlalchemy import CheckConstraint, UniqueConstraint, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.crud import (
    ON_DELETE_CASCADE,
    ON_DELETE_FORBID,
    ON_DELETE_RESTRICT,
    ORPHAN_BY_TAUGHT_SECTION,
    ORPHAN_BY_TEACHER_SELF,
    READ_SCOPE_STAFF,
    READ_SCOPE_STAFF_TAUGHT,
    READ_SCOPE_STAFF_TAUGHT_SECTION,
    READ_SCOPE_STUDENT_SELF,
    READ_SCOPE_VALUES,
    STUDENT_SCOPED_READ_VALUES,
    CrudSchemas,
    OrphanOwner,
    StudentOwner,
    _child_tables,
    _conflict_message,
    _json_text_columns,
    _pk_alias_of,
    _require_orphan_row_readable,
    build_crud_router,
)
from app.api.deps import NOT_STUDENT_OWNED, ReaderIdentity, require_scope
from app.api.routers import catalog
from app.api.routers.catalog import RESOURCES
from app.api.schemas.organisation import (
    SemesterCreate,
    SemesterRead,
    SemesterUpdate,
)
from app.db import models
from app.db.models import (
    BodyComposition,
    CourseSection,
    DerivedMetrics,
    Enrollment,
    FitnessTestBatch,
    FitnessTestResult,
    InterestSurvey,
    PercentileSnapshot,
    Semester,
    Student,
    StratificationResult,
    Teacher,
)
from app.db.models._shared import JsonText
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.ops import DailySyncRun
from app.db.models.prescription import (
    Exercise,
    Prescription,
    PrescriptionTemplate,
    WeeklyAdjustment,
)
from app.db.session import Base

D = dt.date
T = dt.datetime

SEMESTER_PAYLOAD = {
    "name": "2025-2026-1",
    "start_date": "2025-09-01",
    "end_date": "2025-12-22",
    "weeks": 16,
    "is_current": True,
}

STUDENT_PAYLOAD = {
    "student_no": "S2025001",
    "name": "小明",
    "sex": "male",
    "birth": "2005-03-04",
    "department": "体育学院",
    "grade": 1,
}

#: ``_seed_one_row_per_table`` 里那位教师的工号。
#:
#: ⚠️⚠️ **Plan 06 Task 8 起它是一个承重的名字**：那一位是**唯一**教
#: ``seeded["course_section"]`` 的人，而 ``seeded["student"]`` 就选在那个班里，
#: 故它是四档矩阵里「**教师自己班**」那一档的身份（:func:`teaching_teacher_headers`）。
#: 改前它只在一个地方被字面写出来（``_seed_one_row_per_table`` 里那一行），
#: 而第四档一加进来就有第二个消费者了 —— 两处各写一遍字面量的失效形态是
#: 「改了夹具里的工号、于是『教师自己班』那一档静默地变成『教师别人班』」，
#: 而那两档的期望值恰好是反的（200/1 vs 403/0），红是必然的、但报错会指到身份那一格。
SEEDED_TEACHER_STAFF_NO = "T2025001"


def _seed_one_row_per_table(engine) -> dict[str, int]:
    """按**外键拓扑序**往 24 张表各插一行，返回 ``{表名: 该行主键}``。

    24 = 23 个资源对应的表 + ``daily_sync_run``（它不是资源，但九张表的 ``batch_id``
    指向它，而 ``PRAGMA foreign_keys=ON`` 真的在强制，故必须先有它）。

    ⚠️ **每一列的值都是手写的**，不从 :data:`app.db.session.Base` 的元数据推：
    推出来的值会在 5 处 ``CheckConstraint`` 上炸（``student.sex`` / ``alert`` 的
    「两个作用域列恰好一个非空」/ ``rpe_record.rpe BETWEEN 0 AND 10`` /
    ``stratification_result.label`` / ``notification.channel``），而「按元数据自动填」
    要反解 CHECK 文本才能填对——那正是硬规矩 #89 禁止的形状（用正则读源码/DDL）。
    手写 24 行是一次性的成本，且它同时是「一行合法数据长什么样」的可执行文档。

    ⚠️ **``JsonText`` 列一律填非空值**：见模块 docstring 里
    ``_seed_one_row_per_table`` 那一段的理由。
    """
    ids: dict[str, int] = {}
    with Session(engine) as session:

        def _add(model, **values):
            row = model(**values)
            session.add(row)
            session.flush()
            ids[model.__tablename__] = row.id
            return row

        # --- 无外键的三张 + 全库的批次锚点 -----------------------------------
        _add(
            Semester,
            name="2025-2026-1",
            start_date=D(2025, 9, 1),
            end_date=D(2025, 12, 22),
            weeks=16,
            is_current=True,
        )
        _add(Teacher, staff_no=SEEDED_TEACHER_STAFF_NO, name="张老师")
        _add(
            Student,
            student_no="S2025001",
            name="小明",
            sex="male",
            birth=D(2005, 3, 4),
            department="体育学院",
            grade=1,
        )
        _add(
            DailySyncRun,
            semester_id=ids["semester"],
            business_date=D(2025, 9, 10),
            started_at=T(2025, 9, 10, 2, 0),
            finished_at=T(2025, 9, 10, 2, 5),
            status="success",
        )

        # --- spec §4.1 的另两张 ---------------------------------------------
        _add(
            CourseSection,
            semester_id=ids["semester"],
            teacher_id=ids["teacher"],
            name="体育(1)班",
            schedule_text="周三 3-4 节",
            grouping_mode="administrative",
        )
        _add(
            Enrollment,
            semester_id=ids["semester"],
            student_id=ids["student"],
            course_section_id=ids["course_section"],
        )

        # --- spec §4.2 学期节点数据 ------------------------------------------
        _add(
            FitnessTestBatch,
            semester_id=ids["semester"],
            timepoint="week1",
            test_date=D(2025, 9, 8),
            source="lepao",
            academic_year="2025-2026",
        )
        _add(
            FitnessTestResult,
            test_batch_id=ids["fitness_test_batch"],
            student_id=ids["student"],
            tested_on=D(2025, 9, 8),
            height_cm=175.0,
            weight_kg=68.0,
            vital_capacity_ml=4200.0,
            sprint_50m_s=7.2,
            sit_and_reach_cm=12.5,
            standing_jump_cm=230.0,
            strength_count=10.0,
            distance_run_s=240.0,
            score_bmi=80,
            score_vital_capacity=75,
            score_sprint_50m=70,
            score_sit_and_reach=72,
            score_standing_jump=68,
            score_pull_up_or_sit_up=66,
            score_distance_run=60,
            total_score=70,
            national_grade="及格",
        )
        _add(
            BodyComposition,
            student_id=ids["student"],
            measured_on=D(2025, 9, 9),
            muscle_mass_kg=30.0,
            body_fat_pct=18.0,
            smi=7.1,
            weight_kg=68.0,
            device="InBody770",
        )
        _add(
            InterestSurvey,
            student_id=ids["student"],
            semester_id=ids["semester"],
            filled_on=D(2025, 9, 5),
            total_score=3.8,
            dimensions={"运动乐趣": 4.0, "运动能力": 3.5},
            raw_answers={"q1": 4, "q2": 3},
        )

        # --- spec §4.3 派生与分层 --------------------------------------------
        _add(
            PercentileSnapshot,
            semester_id=ids["semester"],
            computed_on=D(2025, 9, 10),
            batch_id=ids["daily_sync_run"],
            item="bmi",
            sex="male",
            age_group="19-22岁",
            p10=17.0,
            p20=18.0,
            p25=18.5,
            p50=21.0,
            p75=23.0,
            sample_size=120,
            source="school",
        )
        _add(
            DerivedMetrics,
            student_id=ids["student"],
            computed_on=D(2025, 9, 10),
            batch_id=ids["daily_sync_run"],
            annual_change={"sprint_50m": -0.02, "distance_run": 0.01},
            trend="improving",
            weaknesses=["distance_run"],
            weakness_count=1,
            valid_count=6,
            body_comp_abnormal=False,
            body_comp_reasons=[],
        )
        _add(
            StratificationResult,
            student_id=ids["student"],
            computed_on=D(2025, 9, 10),
            batch_id=ids["daily_sync_run"],
            label="yellow",
            hit_rules="R1,Y1",
            input_snapshot={"W": 1, "C": 0, "valid_count": 6},
            percentile_source="school",
            valid_from=D(2025, 9, 10),
            valid_to=None,
        )

        # --- spec §4.4 处方四张 ----------------------------------------------
        _add(
            Exercise,
            ref="interval_run",
            name="间歇跑",
            video_url="https://example.invalid/exercise/interval_run",
            impact_level="high",
            targets=["endurance"],
            equipment="none",
        )
        _add(
            PrescriptionTemplate,
            layer="yellow",
            weakness="endurance",
            body_comp="normal",
            template_ref="YEL-END-NOR-01",
            version="1.0",
            review_status="approved",
            reviewer="原型自审（占位）",
            reviewed_at=D(2025, 8, 20),
            reachable=True,
        )
        _add(
            Prescription,
            student_id=ids["student"],
            generated_on=D(2025, 9, 10),
            batch_id=ids["daily_sync_run"],
            template_ref="YEL-END-NOR-01",
            microcycle_weeks=4,
            label_at_generation="yellow",
            training_package={"weeks": [{"week": 1, "sessions": 3}]},
            assembly_snapshot={"layer": "yellow", "weakness": "endurance"},
            safety_substitutions=[{"from": "jump_rope", "to": "cycle"}],
            teacher_overrides=[{"week": 2, "factor": 0.9}],
            previous_had_overrides=False,
            status="active",
            valid_from=D(2025, 9, 10),
            valid_to=D(2025, 10, 7),
            trigger_reasons=["first_prescription"],
        )
        _add(
            WeeklyAdjustment,
            prescription_id=ids["prescription"],
            batch_id=ids["daily_sync_run"],
            week=1,
            factor=0.8,
            reason="本周月考，减量",
            source="teacher",
            created_at=T(2025, 9, 11, 9, 0),
        )

        # --- spec §4.5 反馈三源四张 ------------------------------------------
        _add(
            ClassSession,
            course_section_id=ids["course_section"],
            session_date=D(2025, 9, 10),
            period=3,
            rpe_opened=True,
            rpe_token="ABC12345",
            batch_id=ids["daily_sync_run"],
        )
        _add(
            RpeRecord,
            class_session_id=ids["class_session"],
            student_id=ids["student"],
            rpe=5,
            submitted_at=T(2025, 9, 10, 10, 35),
            elapsed_seconds=8.5,
        )
        _add(
            TrainingLog,
            student_id=ids["student"],
            log_date=D(2025, 9, 11),
            # ⚠️ submitted_at 是 Plan 03 Task 5 加的 NOT NULL 列（无缺省，时钟由调用方
            #    注入）。取 log_date 那天的 20:00：与下面 late=False 自洽（20:00 < 22:00），
            #    且日期一致 = 「当天打的卡」而不是补卡。
            submitted_at=T(2025, 9, 11, 20, 0),
            completed=True,
            duration_min=35.0,
            feeling="moderate",
            is_rest_day=False,
            late=False,
            source="demo",
            batch_id=ids["daily_sync_run"],
        )
        _add(
            MiniTest,
            student_id=ids["student"],
            semester_id=ids["semester"],
            week=2,
            item_combo=["squat_30s", "shuttle_20m"],
            squat_30s_count=42,
            shuttle_20m_s=5.6,
            normalized_score=78.0,
            tested_on=D(2025, 9, 12),
            entered_by="T2025001",
        )

        # --- spec §4.6 预警与通知 + §4.7 班级周报 -----------------------------
        # ⚠️ alert 有一条 CHECK：(student_id IS NULL) <> (course_section_id IS NULL)，
        # 故两列**恰好一个**非空（硬规矩 #101：这两列都是外键，用 0 当哨兵会当场 FK 违例）。
        _add(
            Alert,
            student_id=ids["student"],
            course_section_id=None,
            semester_id=ids["semester"],
            subject_key="student:" + str(ids["student"]),
            level="yellow",
            rule_id="YELLOW_CHECKIN_GAP",
            trigger_snapshot={"gap_days": 4},
            triggered_at=T(2025, 9, 12, 3, 0),
            status="pending",
            handled_action=None,
            handled_at=None,
            batch_id=ids["daily_sync_run"],
            window_key="2025-09-12",
        )
        _add(
            Notification,
            recipient_kind="student",
            recipient_id=ids["student"],
            channel="in_app",
            title="本周预警",
            body="你已经 4 天没有打卡了。",
            alert_id=ids["alert"],
            prescription_id=ids["prescription"],
            is_read=False,
            created_at=T(2025, 9, 12, 3, 0),
        )
        _add(
            WeeklyClassReport,
            course_section_id=ids["course_section"],
            semester_id=ids["semester"],
            week=2,
            layer_distribution={"red": 1, "yellow": 2, "green": 3},
            rpe_summary={"mean": 6.1, "delta": 0.2},
            checkin_rate_by_layer={"green": 0.9, "yellow": 0.7},
            progress_board={"top": ["S2025001"], "bottom": []},
            alert_summary={"yellow": 1, "red": 0},
            suggestion="本周整体负荷适中，黄层学生的打卡率需要盯一下。",
            generated_at=T(2025, 9, 14, 4, 0),
            batch_id=ids["daily_sync_run"],
        )
        session.commit()
    return ids


@pytest.fixture()
def seeded(engine) -> dict[str, int]:
    """每表一行的库。**用完即关**（``conftest.py`` 的 StaticPool 纪律）。"""
    return _seed_one_row_per_table(engine)


#: 写入侧那个身份头的工号。
#:
#: ⚠️ **刻意与 :func:`_seed_one_row_per_table` 里那个 ``T2025001`` 不同**：
#: ``admin_headers`` 与 ``seeded`` 谁先跑由**测试签名的形参顺序**决定，
#: 用同一个工号的话「本夹具先跑」会让 ``seeded`` 当场撞 ``teacher.staff_no`` 的唯一约束
#: （409 → ``IntegrityError``），而那一条错误会指到离真因很远的地方。
ADMIN_STAFF_NO = "T2025900"

#: **普通教师**（``role='teacher'``）的工号。⚠️ 与上面那个不同号，
#: 因为 :func:`plain_teacher_headers` 与 :func:`admin_headers` 可能在同一个测试里都用，
#: 而 ``teacher.staff_no`` 有唯一约束。
PLAIN_TEACHER_STAFF_NO = "T2025901"


def _staff_headers(engine, staff_no: str, name: str, role: str) -> dict:
    """插一行 ``teacher`` 并给出它的身份头。**两个夹具共用**（幂等）。"""
    with Session(engine) as session:
        exists = session.scalar(select(Teacher.id).where(Teacher.staff_no == staff_no))
        if exists is None:
            session.add(Teacher(staff_no=staff_no, name=name, role=role))
            session.commit()
        else:
            # ⚠️ 幂等那一支也要保证 role 对：``seeded`` 可能先插了同一个工号
            # （今天不会——两个工号刻意与它的 ``T2025001`` 不同，见上面的注释），
            # 而静默地沿用别人的 role 会让本夹具给出一个假的「管理员」。
            row = session.get(Teacher, exists)
            if row.role != role:
                row.role = role
                session.commit()
    return {"X-Teacher-Staff-No": staff_no}


@pytest.fixture()
def admin_headers(engine) -> dict:
    """一个**在册管理员**的身份头：``{"X-Teacher-Staff-No": …}``（那一行 ``role='admin'``）。

    ⚠️⚠️ **本文件里每一次对可写资源的 POST / PATCH / DELETE 都要带它**：
    9 个可写资源的写入端点一律挂 ``Security(TEACHER_STAFF_NO_SCHEME)`` +
    :func:`app.api.crud._require_admin_identity`，缺头 **401**、
    在册但 ``role != 'admin'`` **403**。故本夹具**真的插一行 ``role='admin'`` 的教师**
    （不只是给一个串），否则拿到的是 403 而不是 201。

    ⚠️⚠️ **本夹具自 Plan 05A Task 2 起插的是管理员、此前插的是普通教师**
    （名字也相应地从 ``teacher_headers`` 改成 ``admin_headers``，全文件 39 处）。
    理由是口径变了：用户 2026-10-12 逐字裁定「管理员这个角色接管管理台
    （23 个资源的增删改查）」，于是那 26 个写入操作从「任何在册教师可写」
    变成「**仅管理员**可写」。
    ⚠️ **载体一个字都没变**（仍然是 ``X-Teacher-Staff-No``，因为管理员就是一行
    ``teacher``），故本文件里三十来处 ``headers=admin_headers`` 的**用法**逐字不变，
    变的只是那一行的 ``role``。
    ⚠️ 而「普通教师被挡在管理台之外」那一拍由 :func:`plain_teacher_headers` 提供，
    两个夹具**必须在场**（硬规矩 #50）：只有管理员夹具的话，
    「管理台对任何在册教师开放」（= Task 2 之前的口径）也能全绿。

    ⚠️ 它**只影响写的一侧**：``GET`` 一律匿名（大屏与列表要能不登录就读），
    故带上它去读也不会改变任何读端点的行为。
    ⚠️ 幂等：同一个测试同时用 ``seeded`` 与本夹具时只插一行。
    """
    return _staff_headers(engine, ADMIN_STAFF_NO, "写入侧守卫用管理员", "admin")


@pytest.fixture()
def plain_teacher_headers(engine) -> dict:
    """一个**在册但不是管理员**的教师身份头（``role='teacher'``）。

    ⚠️ 它是 :func:`admin_headers` 的**红档半边**：管理台的写操作在 Plan 05A Task 2
    之后要 ``403`` 掉它。少了本夹具，「把 ``require_admin`` 改回 ``require_staff``」
    是**静默**的（全部写入测试照旧全绿，因为管理员也是一种教职）——
    而那正是本 Task 要防的那一次退化。
    ⚠️ 而它**仍然**能过课堂功能的那些闸门（:func:`app.api.deps.require_staff`：
    ``open-rpe`` / ``rpe-token`` / ``mini-tests/batch`` / ``alerts/{id}/handle`` /
    ``teacher/students/*``）——管理员接管的是**管理台**，不是把教师赶出课堂。
    那一格由 ``tests/api/test_auth_api.py`` 的
    ``test_a_plain_teacher_keeps_the_classroom_endpoints_and_loses_the_console`` 钉住。
    """
    return _staff_headers(
        engine, PLAIN_TEACHER_STAFF_NO, "写入侧守卫用普通教师", "teacher"
    )


@pytest.fixture()
def teaching_teacher_headers(seeded) -> dict:
    """一位**真的教 ``seeded`` 那个班**的普通教师身份头（Plan 06 Task 8）。

    ⚠️ 它是四档矩阵里「**教师自己班**」那一档，而 :func:`plain_teacher_headers`
    是「**教师别人班**」那一档。⚠️⚠️ **两档必须在场**（硬规矩 #50）：
    只有前者的话，「第四档整个没生效（教职照旧全读）」是绿的；
    只有后者的话，「第四档收成了『教师一律看不到』」是绿的——
    而那会让 Plan 04 的教师端整个不可用。

    ⚠️ 它**不插行**：那一位教师、那个班、那条选课行都由
    :func:`_seed_one_row_per_table` 铺好了（``course_section.teacher_id`` 指着他、
    ``enrollment`` 把 ``seeded["student"]`` 编进那个班、而 ``semester.is_current``
    是 ``True``，故 :func:`app.pipeline.percentile_stage.current_semester_of`
    解析出来的正是那一个学期）。⚠️ 于是本夹具的唯一职责是**给出那个工号**，
    而工号的字面量住在 :data:`SEEDED_TEACHER_STAFF_NO`（单一所有者）。

    ⚠️ 它的 ``role`` 是 ``Teacher.DEFAULT_ROLE``（``"teacher"``，**不是** ``admin``）：
    「管理员越过任教范围」那一档由 :func:`admin_headers` 提供，
    若本夹具也是管理员，那两档就分不开了。
    """
    return {"X-Teacher-Staff-No": SEEDED_TEACHER_STAFF_NO}


#: **第二位真的带班的教师**的工号（Plan 06 Task 8b）。
#:
#: ⚠️ 它与 :data:`SEEDED_TEACHER_STAFF_NO` / :data:`ADMIN_STAFF_NO` /
#: :data:`PLAIN_TEACHER_STAFF_NO` 三个都不同号（``teacher.staff_no`` 有唯一约束），
#: 而它的 ``role`` 是缺省的 ``"teacher"``（**不是** admin，否则「管理员越过任教范围」
#: 与「教师按任教范围收窄」两档就分不开了）。
OTHER_TEACHING_TEACHER_STAFF_NO = "T2025002"


@pytest.fixture()
def other_section(engine, seeded) -> dict:
    """**另一个教学班 + 另一位真的带它的普通教师**（Plan 06 Task 8b）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它是本波三条守卫能取证的全部理由
    ------------------------------------------------------------------------
    :func:`_seed_one_row_per_table` 只铺了**一个**班与**一位**带它的教师，
    而 Task 8 那两条守卫之所以看不见「无主行对任何教师都不可见」这格 Critical，
    正是因为「只有一个班」时，「对相关教师可见」与「对任何教师都不可见」两个口径
    在**教师那一维**只差一个人——而 :func:`plain_teacher_headers` 那一位
    **不带任何班**，于是两档对他给出**同一个**答案（403 / 空列表）。
    加了第二个班与第二位带班教师之后，两档才**分得开**（一个 200、一个 403）。

    ⚠️ 它**刻意不改** :func:`_seed_one_row_per_table`：那一份是「每表一行」的
    拓扑序夹具，给它加第二个班/第二位教师会让本文件若干条 ``total == 1`` 的守卫
    全变（与 :func:`test_the_student_keyed_resources_admit_four_read_tiers` 里
    「第二个学生」那段注释逐字同一条理由）。故本夹具就地补两行。

    ⚠️ 而它**刻意不给那个班编任何学生**（不插 ``enrollment``）：
    于是那个班对第四档的**学生主轴**是空的（``taught_student_ids`` 给出空集），
    **只有第二根轴（班级）能命中它** —— 那正是本波要分开钉的两根轴。
    ⚠️ 第五档（``weekly-class-reports``）要的也正是这一格：一个班、一份周报、
    而班里的学生对另一个教师不可见。

    返回 ``{teacher_id, staff_no, course_section_id}`` 三格。
    """
    with Session(engine) as session:
        teacher = Teacher(staff_no=OTHER_TEACHING_TEACHER_STAFF_NO, name="李老师")
        session.add(teacher)
        session.flush()
        section = CourseSection(
            # ⚠️ 挂在**同一个** ``is_current`` 的学期上：第二根轴与第五档都吃
            #    :func:`app.api.crud._current_semester_id`，而它解析出来的正是
            #    ``seeded["semester"]``（``is_current=True``）。挂到别的学期上，
            #    两档都会给出「不可见」，于是守卫**空转**（硬规矩 #50）。
            semester_id=seeded["semester"],
            teacher_id=teacher.id,
            name="体育(2)班",
            schedule_text="周五 3-4 节",
            grouping_mode="administrative",
        )
        session.add(section)
        session.commit()
        result = {
            "teacher_id": teacher.id,
            "staff_no": teacher.staff_no,
            "course_section_id": section.id,
        }
    assert result["course_section_id"] != seeded["course_section"], (
        "第二个班必须与 seeded 那一个不同行，否则两档教师在任教范围上分不开"
    )
    return result


@pytest.fixture()
def other_teaching_teacher_headers(other_section) -> dict:
    """:func:`other_section` 里那一位教师的身份头（**四档身份矩阵的第五档**）。

    ⚠️ 它与 :func:`teaching_teacher_headers` 的关系正是「教师自己班 / 教师别人班」
    那两档的**镜像**：本波三条守卫各造**两行**（一行挂 seeded 那个班、一行挂本夹具
    那个班），于是两位教师各看得到一行、看不到另一行 —— 少了任何一位，
    「第二根轴写成了恒真（任何教师都看得到）」与「写成了恒假（= Task 8 的那格
    Critical 没修）」两个反方向都会静默。
    """
    return {"X-Teacher-Staff-No": other_section["staff_no"]}


# ---------------------------------------------------------------------------
# 批次 A：五个端点（semester / teacher / stratification_result）
# ---------------------------------------------------------------------------


def test_list_returns_items_total_limit_offset(client, seeded, admin_headers):
    """``GET {path}`` 的响应形状逐字是 ``{"items", "total", "limit", "offset"}``。

    ``total`` 是**全表计数**、不受 ``limit``/``offset`` 影响——前端要靠它算总页数，
    一个「本页条数」会让分页控件永远只有一页。三个学期 + ``limit=2`` 把这个差别钉住：
    ``len(items) == 2`` 而 ``total == 3``，两侧不同源。
    """
    for name in ("2025-2026-2", "2026-2027-1"):
        got = client.post(
            "/api/semesters", json={**SEMESTER_PAYLOAD, "name": name},
            headers=admin_headers,
        )
        assert got.status_code == 201, got.text

    page = client.get("/api/semesters", params={"limit": 2, "offset": 0})
    assert page.status_code == 200, page.text
    body = page.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    # 缺省分页：limit 50 / offset 0（app.api.deps.Page 的字面缺省）
    default = client.get("/api/semesters").json()
    assert (default["limit"], default["offset"], default["total"]) == (50, 0, 3)
    assert len(default["items"]) == 3


def test_limit_over_200_is_422(client):
    """分页上界 **200**：``limit=201`` → 422，且走统一错误形状。

    上界的唯一所有者是 :class:`app.api.deps.Page`（``le=200``），故本条断言的是
    **真的 CRUD 端点**上那道边界生效——``tests/api/test_scope.py`` 的同名断言用的是一条
    探针路由，两者守的是「声明」与「接线」两件事。
    """
    got = client.get("/api/semesters", params={"limit": 201})
    assert got.status_code == 422
    body = got.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "request_validation_failed"
    # 绿档：200 本身必须放行（否则「一律 422」也能让上面那三行全绿）
    assert client.get("/api/semesters", params={"limit": 200}).status_code == 200


def test_offset_beyond_total_returns_empty_items(client, seeded):
    """``offset`` 超过总行数 → ``items == []`` 而 ``total`` 仍是真值。

    这一档必须**不是 404**：分页翻过尾是前端的正常状态（刚删掉最后一页的唯一一行），
    报 404 会让前端把它当成「资源不存在」而跳回列表页。
    """
    got = client.get("/api/semesters", params={"offset": 5})
    assert got.status_code == 200
    body = got.json()
    assert body["items"] == []
    assert body["total"] == 1
    assert body["offset"] == 5


def test_create_returns_201_with_a_location_header(client, admin_headers):
    """``POST {path}`` → **201** + ``Location`` 头 + 整行的读模型。

    ``Location`` 是 RFC 9110 对「创建出了一个新资源」的要求，也是前端「建完就跳到详情页」
    最省事的实现路径（不必从响应体里挑主键）。断言它逐字等于 ``{path}/{新主键}``，
    而那个主键从**响应体**读回来——两侧一个是头、一个是体，不同源。
    """
    got = client.post("/api/semesters", json=SEMESTER_PAYLOAD, headers=admin_headers)
    assert got.status_code == 201, got.text
    body = got.json()
    new_id = body["id"]
    assert isinstance(new_id, int) and new_id > 0
    assert got.headers["Location"] == "/api/semesters/" + str(new_id)
    assert body["name"] == "2025-2026-1"
    assert body["weeks"] == 16
    assert body["is_current"] is True
    # 建出来的行真的在库里（不是只在响应体里）
    assert client.get("/api/semesters/" + str(new_id)).status_code == 200


def test_create_with_a_duplicate_natural_key_is_409(client, admin_headers):
    """撞自然键 → **409**，消息点名**列名**、且不含字面 ``"None"``（P3-B5）。

    ⚠️ ``semester.name`` 的唯一约束是**无名的**（实测 ``UniqueConstraint.name is None``，
    同族的还有 ``teacher.staff_no`` / ``student.student_no`` / ``exercise.ref`` /
    ``prescription_template.template_ref``）。把约束名插进消息就会渲染出字面 ``"None"``，
    而那句话是要给教师看的。故断言里同时要求 ``"name" in message`` 与
    ``"None" not in message``。

    **红绿两档**：第二次 POST 之前先断言第一次是 201，否则「一律 409」也能让本条绿。
    """
    first = client.post("/api/semesters", json=SEMESTER_PAYLOAD, headers=admin_headers)
    assert first.status_code == 201, first.text

    second = client.post("/api/semesters", json=SEMESTER_PAYLOAD, headers=admin_headers)
    assert second.status_code == 409, second.text
    body = second.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "integrity_conflict"
    message = body["error"]["message"]
    assert "name" in message
    assert "None" not in message
    # 撞键的那一次**没有**多出一行
    rows = client.get("/api/semesters").json()
    assert rows["total"] == 1

    # ⚠️ 而且那一行**没有被改**——这一拍守的是 ``session.rollback()``。
    # :func:`app.db.repo.upsert` 的语义是「有则更新、无则插入」，故它的更新分支在
    # 返回之前**已经 ``setattr`` 过那一行了**；409 之前不回滚的话，一次被拒绝的 POST
    # 就改掉了库里的数据，而响应体看不出来（它是 409，前端会当成「什么都没发生」）。
    # 用一个「同 name、不同 weeks」的请求撞一次，再把原行读回来比。
    tampered = client.post(
        "/api/semesters", json={**SEMESTER_PAYLOAD, "weeks": 99}, headers=admin_headers
    )
    assert tampered.status_code == 409, tampered.text
    after = client.get("/api/semesters/" + str(first.json()["id"])).json()
    assert after["weeks"] == 16, "被拒绝的 POST 改掉了已有行（rollback 没做）"
    assert client.get("/api/semesters").json()["total"] == 1


def test_read_one_returns_the_row(client, seeded, admin_headers):
    """``GET {path}/{pk}`` → 整行，**含** ``JsonText`` 列（list 端点不含，见下面那条）。

    ⚠️ **安全收紧波起它带身份**：``stratification-results`` 是学生键资源
    （``read_scope="student_self"``），匿名打过去是 401。
    ⚠️ 本条钉的是「read-one 含 ``JsonText`` 列」，与身份无关，故带一个**教职**头
    （教职那一档是全读）；「匿名 401 / 学生只读自己的 / 学生读别人的 403」
    三档由 :func:`test_the_student_keyed_resources_admit_four_read_tiers` 钉。
    """
    got = client.get(
        "/api/stratification-results/" + str(seeded["stratification_result"]),
        headers=admin_headers,
    )
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["label"] == "yellow"
    assert body["hit_rules"] == "R1,Y1"
    assert body["input_snapshot"] == {"W": 1, "C": 0, "valid_count": 6}
    assert body["valid_to"] is None


def test_read_a_missing_pk_is_404(client, admin_headers):
    """主键查无此行 → 404 + 统一形状。

    ⚠️ 实现走的是 ``session.get(model, pk)`` + 显式 ``raise HTTPException(404)``
    （P3-B7：``repo.py`` 只有 ``upsert`` 与 ``delete_by_batch`` 两个公开函数，
    没有 ``get_or_404``，也**不该**为这件事给它加一个）。

    ⚠️ **安全收紧波起它带身份**：``stratification-results`` 是学生键资源，
    匿名打过去是 **401**（身份闸门在路由匹配之后、端点体之前跑，
    故它**先于** ``_get_or_404`` 的那一次 ``session.get``）。
    ⚠️ 于是「404 与 401 谁先」这件事在本仓有了明确答案：**缺身份先 401**。
    那是对的——把「这个 id 在不在」告诉一个匿名调用方本身就是泄漏。
    """
    got = client.get("/api/stratification-results/424243", headers=admin_headers)
    assert got.status_code == 404
    body = got.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["detail"] is None
    assert "424243" in body["error"]["message"]


def test_patch_changes_only_the_keys_present(client, admin_headers):
    """**部分更新**：``null`` 与「没传」必须可区分（计划 Review Focus 的同一条）。

    三拍，缺一不可：

    ① ``PATCH {"name": …}`` 只改 ``name``，``department`` 保持原值——
      若实现用了 ``model_dump()`` 而不是 ``model_dump(exclude_unset=True)``，
      没传的键会以 ``None`` 落进去，这一拍当场红；
    ② ``PATCH {"department": null}`` **显式**清空 ``department``——
      若实现把 ``None`` 一律当「没传」，这一拍红；
    ③ ②之后 ``name`` 仍是①改过的那个值（两拍互不干扰）。
    """
    created = client.post("/api/students", json=STUDENT_PAYLOAD, headers=admin_headers)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    renamed = client.patch(
        "/api/students/" + str(sid), json={"name": "小红"}, headers=admin_headers
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "小红"
    assert renamed.json()["department"] == "体育学院", "没传的键被清掉了"

    cleared = client.patch(
        "/api/students/" + str(sid), json={"department": None}, headers=admin_headers
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["department"] is None, "显式的 null 被当成了「没传」"
    assert cleared.json()["name"] == "小红"

    # 空请求体 = 什么都不改（exclude_unset 的边界档）
    noop = client.patch(
        "/api/students/" + str(sid), json={}, headers=admin_headers
    )
    assert noop.status_code == 200, noop.text
    assert noop.json()["name"] == "小红"
    assert noop.json()["department"] is None


def test_delete_returns_204_and_the_row_is_gone(client, admin_headers):
    """``DELETE {path}/{pk}`` → **204** 且行真的没了。

    ⚠️ 用 ``teachers`` 而不是计划 Step 1 说的 ``semester``：``semesters`` 的
    ``on_delete`` 是 ``forbid``（读写矩阵第 1 行），它的 DELETE 端点**根本没注册**，
    打过去是 405 而不是 204。``teachers`` 是可写 + ``restrict`` + 今天没有子行，
    是「真的能删成功」那一档里最简单的一个。
    """
    created = client.post(
        "/api/teachers", json={"staff_no": "T2025009", "name": "李老师"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]

    deleted = client.delete("/api/teachers/" + str(tid), headers=admin_headers)
    assert deleted.status_code == 204
    assert deleted.content == b""

    assert client.get(
        "/api/teachers/" + str(tid), headers=admin_headers
    ).status_code == 404
    # 再删一次也是 404、不是 204（幂等的语义是「这行不在了」，不是「删成功了」）
    assert client.delete(
        "/api/teachers/" + str(tid), headers=admin_headers
    ).status_code == 404


def test_a_readonly_resource_rejects_post_patch_delete_with_405(
    client, seeded, admin_headers
):
    """``writable=False`` 的资源：POST / PATCH / DELETE 一律 **405**，GET 照常 200。

    ⚠️ **实现是「不注册那个路由」而不是「注册了再 raise 405」**，两个后果都是承重的：

    * OpenAPI 里**不出现**那些方法，故 Plan 04 的前端不会照着 ``/docs`` 写一个必然 405
      的提交按钮；
    * 405 由 Starlette 的路由匹配给出（``Allow`` 头因此是对的），再经
      :mod:`app.api.errors` 折成统一形状，``code`` 是 ``http_405``——
      那个 ``http_<码>`` 的兜底正是 ``errors.py`` 的 ``_CODE_BY_STATUS`` 注释里
      举的例子，本条把它在真端点上钉住。

    **绿档同时在场**（硬规矩 #50）：同一资源的两个 GET 必须 200，
    否则「这个资源整个没挂上去」也会让上面三行全绿。

    ⚠️ **安全收紧波起那两个 GET 带身份**（``stratification-results`` 是学生键资源，
    匿名是 401，于是「绿档同时在场」会假红成 401）。
    ⚠️ 而三个**写入**请求**刻意不带**身份：本条钉的是「路由根本不注册」，
    而 405 由 Starlette 的路由匹配给出、**在身份依赖之前**——
    给它带上了头就等于把「405 是因为没注册」偷换成「405 是因为别的原因」，
    那一拍就不再看它本该看的东西。
    """
    pk = seeded["stratification_result"]
    assert client.get("/api/stratification-results", headers=admin_headers).status_code == 200
    assert client.get(
        "/api/stratification-results/" + str(pk), headers=admin_headers
    ).status_code == 200

    for method, url, payload in (
        ("post", "/api/stratification-results", {"student_id": 1}),
        ("patch", "/api/stratification-results/" + str(pk), {"label": "red"}),
        ("delete", "/api/stratification-results/" + str(pk), None),
    ):
        got = client.request(method, url, json=payload)
        assert got.status_code == 405, (method, url, got.status_code, got.text)
        assert got.json()["error"]["code"] == "http_405"
        assert "GET" in got.headers["allow"]
    # 行还在（405 不是「删了但报了个错」）
    assert client.get(
        "/api/stratification-results/" + str(pk), headers=admin_headers
    ).status_code == 200


def test_a_forbidden_delete_is_405_even_on_a_writable_resource(
    client, seeded, admin_headers
):
    """``writable=True`` 且 ``on_delete="forbid"``：增改读照常，**只有 DELETE 是 405**。

    这一条与上一条守的是**两个不同的开关**：上一条是 ``writable=False``（三个写方法一起
    关掉），本条是 ``on_delete="forbid"``（只关 DELETE）。把两者合成一个开关的实现
    （例如「forbid 就顺手把 PATCH 也关了」）在这里当场红。
    """
    sid = seeded["semester"]
    assert client.get("/api/semesters").status_code == 200
    assert client.get("/api/semesters/" + str(sid)).status_code == 200
    assert client.patch(
        "/api/semesters/" + str(sid), json={"weeks": 18}, headers=admin_headers
    ).status_code == 200
    assert client.post(
        "/api/semesters", json={**SEMESTER_PAYLOAD, "name": "2026-2027-1"},
        headers=admin_headers,
    ).status_code == 201

    got = client.delete("/api/semesters/" + str(sid))
    assert got.status_code == 405
    assert got.json()["error"]["code"] == "http_405"
    assert client.get("/api/semesters/" + str(sid)).json()["weeks"] == 18


def test_list_omits_the_big_json_columns_but_read_one_includes_them(
    client, seeded, admin_headers
):
    """``list_exclude`` 的自动探测（P3-B3）：list 不返回 ``JsonText`` 列，read-one 返回。

    ⚠️ **本条只在 ``stratification_result`` 一个资源上跑**（批次 A 的范围）；
    遍历 23 个资源的那一条是批次 B 的
    :func:`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`。
    两条刻意不合并：本条是「行为对不对」的最小可跑单元，先红先绿；那一条是覆盖面。

    **``total`` 也要一并看**：list 端点必须仍然数得到那一行，
    否则「少 select 几列」可能是靠「少返回几行」实现的。

    ⚠️ **安全收紧波起它带教职身份**（``stratification-results`` 是学生键资源，
    匿名是 401，于是 ``.json()`` 拿到的是错误信封、``KeyError: 'total'``）。
    ⚠️ 带**教职**头而不是学生头是有意的：本条钉的是「``JsonText`` 列的排除」，
    而教职那一档是**全读**，故 ``total == 1`` 仍然成立；
    若带学生头，``total`` 会变成「**我的**行数」，那是另一条守卫要钉的事
    （:func:`test_the_student_keyed_resources_admit_four_read_tiers` 的第五拍）。
    """
    listing = client.get("/api/stratification-results", headers=admin_headers).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert "input_snapshot" not in item
    assert item["label"] == "yellow"

    one = client.get(
        "/api/stratification-results/" + str(seeded["stratification_result"]),
        headers=admin_headers,
    ).json()
    assert one["input_snapshot"] == {"W": 1, "C": 0, "valid_count": 6}
    # 非空转守卫：read-one 的键**严格多于** list 的键，差集恰好是那些 JsonText 列
    assert set(one) - set(item) == {"input_snapshot"}


# ---------------------------------------------------------------------------
# 批次 B：遍历 23 行 RESOURCES 的守卫
# ---------------------------------------------------------------------------

#: 23 个资源的**字面**路径清单，与计划读写矩阵那 23 行同序。
#: ⚠️ Plan 04 的前端逐字照着它写，故它是被钉死的契约、不是「碰巧长成这样」。
_EXPECTED_PATHS = (
    "/api/semesters",
    "/api/teachers",
    "/api/students",
    "/api/course-sections",
    "/api/enrollments",
    "/api/fitness-test-batches",
    "/api/fitness-test-results",
    "/api/body-compositions",
    "/api/interest-surveys",
    "/api/percentile-snapshots",
    "/api/derived-metrics",
    "/api/stratification-results",
    "/api/exercises",
    "/api/prescription-templates",
    "/api/prescriptions",
    "/api/weekly-adjustments",
    "/api/class-sessions",
    "/api/rpe-records",
    "/api/training-logs",
    "/api/mini-tests",
    "/api/alerts",
    "/api/notifications",
    "/api/weekly-class-reports",
)

#: 23 个资源上的 ``JsonText`` 列，**字面**写死（P3-B3 的独立一侧）。
#: 合计 **19** 个、分布在 **8** 张表；另 2 个（``cleaning_log.original_value`` /
#: ``processed_value``）不在这 23 个资源上，故全库是 21 个 / 9 张表。
_JSON_TEXT_COLUMNS = {
    "interest_survey": ["dimensions", "raw_answers"],
    "derived_metrics": ["annual_change", "weaknesses", "body_comp_reasons"],
    "stratification_result": ["input_snapshot"],
    "exercise": ["targets"],
    "prescription": [
        "training_package",
        "assembly_snapshot",
        "safety_substitutions",
        "teacher_overrides",
        "trigger_reasons",
    ],
    "mini_test": ["item_combo"],
    "alert": ["trigger_snapshot"],
    "weekly_class_report": [
        "layer_distribution",
        "rpe_summary",
        "checkin_rate_by_layer",
        "progress_board",
        "alert_summary",
    ],
}

#: P3-B1 的那 11 个：模型类名 → 它们**必须**走的子模块路径。
_NON_PUBLIC_MODULES = {
    "app.db.models.prescription": {
        "Exercise",
        "PrescriptionTemplate",
        "Prescription",
        "WeeklyAdjustment",
    },
    "app.db.models.feedback": {
        "ClassSession",
        "RpeRecord",
        "TrainingLog",
        "MiniTest",
        "Alert",
        "Notification",
        "WeeklyClassReport",
    },
}


def _unique_columns(table) -> tuple[str, ...] | None:
    """从 :data:`Base.metadata` 读一张表的自然键（唯一约束的那些列），没有则 ``None``。

    **这是 ``RESOURCES["natural_key"]`` 的独立一侧**：期望值来自 SQLAlchemy 的约束对象，
    而不是从 ``catalog.py`` 读回来跟自己比（硬规矩 #35）。

    ⚠️ 列级 ``unique=True`` 也会被 SQLAlchemy 物化成一条**无名**的
    :class:`~sqlalchemy.UniqueConstraint`（实测 ``semester`` / ``teacher`` / ``student`` /
    ``exercise`` / ``prescription_template`` 五张就是这一档），故只看表级约束就够了、
    不必另扫 ``column.unique``。
    """
    found = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert len(found) <= 1, f"{table.name} 有 {len(found)} 条表级唯一约束，本 helper 只认一条"
    return tuple(c.name for c in found[0].columns) if found else None


def _factory_spec(**overrides):
    """:func:`build_crud_router` 的一组**合法**参数，供配置校验那几条测试逐个改坏。"""
    spec = {
        "model": Semester,
        "schemas": CrudSchemas(SemesterRead),
        "path": "/api/semesters",
        "tags": ["semesters"],
        "writable": False,
        "natural_key": ("name",),
    }
    spec.update(overrides)
    return spec


def test_all_twenty_three_resources_are_listable(client, seeded, admin_headers):
    """23 个路由**真的挂上了**，且每个都数得到 ``seeded`` 插进去的那一行。

    这一条是「目录 → 工厂 → 汇总路由 → ``create_app``」这条装配链的端到端冒烟：
    中间任何一环漏了（``catalog`` 少一行、``routers/__init__`` 少一次
    ``include_router``、``main.py`` 少一句），这里就以 **404** 而不是「某个资源悄悄
    不存在」的形式响。

    ``total == 1`` 对匿名那 **7** 个资源都成立，是因为 :func:`_seed_one_row_per_table`
    每表恰好插一行——于是这一条同时是 ``total`` 的口径守卫
    （它数的是**本页口径下**的行数、不是本页）。

    ⚠️⚠️ **安全收紧波起判据从 ``read_requires_staff`` 换成 ``read_scope is not None``**：
    Plan 05A Task 5 之后只有 ``students`` / ``teachers`` 两行要身份（故 ``anonymous == 21``），
    本波把 13 个学生键资源与 ``weekly-class-reports`` 也收进来，于是**匿名只剩 7 个**。
    ⚠️ **一律带教职头**（而不是「学生键资源带学生头」）是有意的：本条钉的是
    「路由挂上了、数得到那一行」，而教职那一档是**全读**，故 23 行可以用同一个身份跑完；
    带学生头的话每一行都要先算出「这一行的所有者是不是我」（``weekly-adjustments``
    还是间接键），那会让本条从一次装配冒烟变成一次作用域测试——
    而作用域由 :func:`test_the_student_keyed_resources_admit_four_read_tiers` 钉。
    ⚠️ 而**只有那 7 个匿名的不带**：给所有 23 行一律带头的话，
    「把闸门挂到全部资源上」这一档就静默了（末行那个 ``anonymous == 7``
    与下面那句「反假绿：真的没带头」两拍合起来才封住它）。
    """
    assert len(RESOURCES) == 23
    assert tuple(spec["path"] for spec in RESOURCES) == _EXPECTED_PATHS
    anonymous = 0
    for spec in RESOURCES:
        needs_identity = spec["read_scope"] is not None
        anonymous += not needs_identity
        got = client.get(
            spec["path"], headers=admin_headers if needs_identity else None
        )
        assert got.status_code == 200, (spec["path"], got.text)
        body = got.json()
        assert set(body) == {"items", "total", "limit", "offset"}, spec["path"]
        ids = [row["id"] for row in body["items"]]
        assert seeded[spec["model"].__tablename__] in ids, spec["path"]
        if needs_identity:
            # ⚠️ 要身份那 16 行只能是 ``>= 1``：本夹具（``admin_headers``）**自己也插一行
            #    ``teacher``**（``T2025900``，``role='admin'``），故 ``/api/teachers``
            #    实测是 2 行。⚠️ 判据因此从「行数」换成「``seeded`` 那一行在不在里面」
            #    —— 后者才是本条要钉的事（路由挂上了、数得到那一行）。
            assert body["total"] >= 1, spec["path"]
        else:
            # ⚠️ 匿名那 **7** 行**仍然严格 == 1**：本夹具不给它们多插行，
            #    而一律放宽成 ``>= 1`` 会让「某个资源悄悄多了一行」静默。
            assert body["total"] == 1, spec["path"]
            assert len(body["items"]) == 1, spec["path"]
            # ⚠️ 反假绿：不带身份那一档**必须**真的没带头（而不是带了一个空的）。
            assert got.request.headers.get("X-Teacher-Staff-No") is None, spec["path"]
    #: ⚠️ **7 而不是 21**（安全收紧波）。7 个仍匿名的资源逐字是：``semesters`` /
    #: ``course-sections`` / ``fitness-test-batches`` / ``percentile-snapshots`` /
    #: ``exercises`` / ``prescription-templates`` / ``class-sessions``——
    #: 全是**不含任何学生键**的参考数据与班级/批次级数据（裁定 4）。
    #: ⚠️ 本清单**不在这里写第二遍**（它的住址是 :mod:`app.api.routers.catalog`
    #: 的模块 docstring 那张三档表），本行只钉**个数**：
    #: 「有人把第八个资源也放成匿名」与「有人把这 7 个也收进去」都会红。
    assert anonymous == 7, anonymous


def test_the_read_write_matrix_counts_are_pinned():
    """读写矩阵的三个计数逐行钉住。

    ⚠️⚠️ **本条的期望值与派单/简报给的不同**（本 Task 的顶回 2，报告第 ⑥ 节）。
    简报 §4 的 P3-B8 与 §9 的第 5 格逐字写的是「**可写 8 / 只读 15**；
    ``restrict`` **11** / ``forbid`` **11** / ``cascade`` **1**」，
    而**按读写矩阵那 23 行逐行数**得到的是「**可写 9 / 只读 14**；
    ``restrict`` **12** / ``forbid`` **10** / ``cascade`` **1**」：

    * ✅ 的 9 行是 ``semesters`` / ``teachers`` / ``students`` / ``course-sections`` /
      ``enrollments`` / ``fitness-test-batches`` / ``body-compositions`` /
      ``interest-surveys`` / ``class-sessions``；
    * ``restrict`` 的 12 行是 ``teachers`` / ``students`` / ``course-sections`` /
      ``enrollments`` / ``fitness-test-batches`` / ``body-compositions`` /
      ``interest-surveys`` / ``prescriptions`` / ``weekly-adjustments`` /
      ``rpe-records`` / ``training-logs`` / ``mini-tests``；
    * ``forbid`` 的 10 行是 ``semesters`` / ``fitness-test-results`` /
      ``percentile-snapshots`` / ``derived-metrics`` / ``stratification-results`` /
      ``exercises`` / ``prescription-templates`` / ``alerts`` / ``notifications`` /
      ``weekly-class-reports``。

    三组各自加总都是 23，且**矩阵已经应用过 P3-B8**（``alerts`` 与 ``notifications``
    两行的 ``on_delete`` 格里逐字印着「**``forbid``（P3-B8 更正，原为 ``restrict``）**」）。
    故 P3-B8 那句「原为 12/10/1」与「更正后 11/11/1」两个数**都对不上矩阵本身**：
    更正前应是 14/8/1、更正后是 12/10/1。计划正文自己也逐字要求
    「**数字自己数、不要照抄本行**（硬规矩 #44/#89）」，本条就是照那句话办的。

    ⚠️ 只读那 14 个也与计划正文「只读资源：**15 个**」那半句不符——
    而那一段自己列出来的是 4 + 1 + 2 + 7 = **14** 个。
    """
    assert len(RESOURCES) == 23
    assert len({spec["path"] for spec in RESOURCES}) == 23, "路径有重复"
    assert len({spec["model"] for spec in RESOURCES}) == 23, "模型有重复"

    assert sorted(s["path"] for s in RESOURCES if s["writable"] is True) == [
        "/api/body-compositions",
        "/api/class-sessions",
        "/api/course-sections",
        "/api/enrollments",
        "/api/fitness-test-batches",
        "/api/interest-surveys",
        "/api/semesters",
        "/api/students",
        "/api/teachers",
    ]
    assert sum(1 for s in RESOURCES if s["writable"] is False) == 14

    counts: dict[str, int] = {}
    for spec in RESOURCES:
        counts[spec["on_delete"]] = counts.get(spec["on_delete"], 0) + 1
    assert counts == {
        ON_DELETE_RESTRICT: 12,
        ON_DELETE_FORBID: 10,
        ON_DELETE_CASCADE: 1,
    }

    # cascade 全库只有一个用户（计划 Task 3 的显式决定）
    assert [s["path"] for s in RESOURCES if s["on_delete"] == ON_DELETE_CASCADE] == [
        "/api/class-sessions"
    ]
    # P3-B8 的落点：alerts 与 notifications 在 forbid 这一档里
    assert sorted(s["path"] for s in RESOURCES if s["on_delete"] == ON_DELETE_FORBID) == [
        "/api/alerts",
        "/api/derived-metrics",
        "/api/exercises",
        "/api/fitness-test-results",
        "/api/notifications",
        "/api/percentile-snapshots",
        "/api/prescription-templates",
        "/api/semesters",
        "/api/stratification-results",
        "/api/weekly-class-reports",
    ]


def test_every_resource_declares_on_delete_explicitly():
    """每一行都**字面写了** ``on_delete``（缺省值不算显式）。

    为什么值得一条守卫：``build_crud_router`` 的 ``on_delete`` **有**缺省值
    ``"restrict"``，于是加第 24 个资源时忘了写它会**静默**落到那一档——
    而 ``restrict`` 对一张批处理产物表（该 ``forbid`` 的）意味着
    「没有子行时可以从 API 删掉」，那正是 P3-B8 要消灭的失效形态。

    断言的是**键在不在**（``"on_delete" in spec``），不是值等不等于什么——
    后者对「忘了写」完全无感。

    顺带把 ``natural_key`` 那一档也钉住：它**没有**缺省值，故漏写是 ``TypeError``
    （响亮），而不是静默落到「无自然键 → POST 走裸 ``session.add`` → 重复行」。
    """
    assert len(RESOURCES) == 23, "本条会在 RESOURCES 被写空时空转全绿"
    assert [spec["path"] for spec in RESOURCES if "on_delete" not in spec] == []
    assert [spec["path"] for spec in RESOURCES if "natural_key" not in spec] == []
    assert [spec["path"] for spec in RESOURCES if "writable" not in spec] == []

    signature = inspect.signature(build_crud_router)
    assert signature.parameters["on_delete"].default == ON_DELETE_RESTRICT == "restrict"
    assert signature.parameters["natural_key"].default is inspect.Parameter.empty


def test_every_writable_resource_declares_require_admin_explicitly():
    """可写的那 9 行都**字面写了** ``"require_admin": True``（缺省值不算显式）。

    与 :func:`test_every_resource_declares_on_delete_explicitly` 同一条理由、同一个形状：
    ``build_crud_router`` 的 ``require_admin`` **有**缺省值 ``False``，于是加第 24 个
    可写资源时忘了写它会**静默**退回「匿名可写」——那正是 Plan 03 全分支终审实测到的
    失效形态（35 个 mutating 操作里 26 个不带 ``security``，零请求头连着四个 POST
    全部 201，而最后一行的 ``rpe_token`` 是客户端自己挑的串）。

    ⚠️ 断言的是**键在不在**（``"require_admin" in spec``），不是值等不等于什么
    ——后者对「忘了写」完全无感。
    ⚠️ 只读那 14 行**不该**出现这个键：工厂体里的第 7 道校验会在导入期响
    （只读资源根本不注册 POST/PATCH/DELETE，挂上去是一件什么也不发生的事）。
    ⚠️ 9 个可写资源的清单是**字面写死**的（硬规矩 #35），不从 ``RESOURCES`` 反推：
    两侧同源的话，「把一行的 ``writable`` 翻成 ``False`` 来绕过本条」会一起改两边、
    断言恒成立。
    """
    assert len(RESOURCES) == 23, "本条会在 RESOURCES 被写空时空转全绿"
    writable = [spec for spec in RESOURCES if spec["writable"]]
    assert len(writable) == 9, (
        f"可写资源实测是 {len(writable)} 个而不是 9 个："
        f"{sorted(spec['path'] for spec in writable)}。"
        f"读写矩阵变了的话，本条下面那份字面清单要跟着改（不要反过来改断言）"
    )
    assert [spec["path"] for spec in writable if "require_admin" not in spec] == [], (
        "上面这些可写资源没有字面写 require_admin，会静默落到缺省的 False（匿名可写）"
    )
    assert sorted(spec["path"] for spec in writable if spec["require_admin"]) == [
        "/api/body-compositions",
        "/api/class-sessions",
        "/api/course-sections",
        "/api/enrollments",
        "/api/fitness-test-batches",
        "/api/interest-surveys",
        "/api/semesters",
        "/api/students",
        "/api/teachers",
    ]
    assert [
        spec["path"] for spec in RESOURCES
        if not spec["writable"] and spec.get("require_admin")
    ] == [], "只读资源不该挂 require_admin（工厂体里第 7 道校验会在导入期响）"

    signature = inspect.signature(build_crud_router)
    assert signature.parameters["require_admin"].default is False


#: 只读的 14 个资源里，POST **不是** 405 的那两个：它们的 POST 不是泛型工厂注册的，
#: 而是 :mod:`app.api.routers.feedback` 的两个**学生侧特例**端点
#: （``POST /api/rpe-records`` 交课堂快评、``POST /api/training-logs`` 交每日打卡，
#: 两者都挂 ``Security(STUDENT_ID_SCHEME)``，缺 ``X-Student-Id`` → 401）。
#: ⚠️ 于是「只读 ⇒ POST 405」这句话对这两个路径**不成立**，本清单就是那条例外，
#: 字面写死（硬规矩 #35）：谁再给一个只读资源加一个特例 POST，本条会红在那一行上，
#: 而那正是需要过目一眼的改动。
_STUDENT_OWNED_POSTS = frozenset({"/api/rpe-records", "/api/training-logs"})


def test_every_writable_resource_admits_only_an_admin_mutation(
    app, client, seeded, admin_headers, plain_teacher_headers
):
    """遍历 ``RESOURCES``：**可写 ⇒ 匿名 401 / 普通教师 403 / 管理员放行**；
    **只读 ⇒ 匿名写 405**。

    这是 Plan 03 全分支终审那条 Important（「26 个匿名 mutating 操作」）的守卫，
    用户 2026-10-08 裁定「加强制」；**Plan 05A Task 2 把它从两拍扩成三拍**
    （用户 2026-10-12 裁定「管理员这个角色接管管理台」）。
    函数名因此从 ``…rejects_an_anonymous_mutation`` 改成
    ``…admits_only_an_admin_mutation``：旧名只说了第一拍，而本条今天守的是
    「**恰好**管理员能写」——一个只守「匿名被挡」的名字会让下一个人以为
    「教师也能写」是本条认可的现状。⚠️ 连带改名的散文引用共 **6 处**
    （``app/api/crud.py`` 2、``app/api/routers/catalog.py`` 2、
    ``app/api/routers/__init__.py`` 1、``tests/api/test_prescription_api.py`` 1）。

    **两侧都在场**（硬规矩 #50）：只断可写那一半的话，
    一个「23 个资源一律挂教师头」的实现也能全绿，而那会当场毁掉教师大屏与学生首页
    （Task 3 的偏离 ⑦「身份头条件注册」定的就是「``GET`` 一律匿名」）。
    ⚠️ **三拍也必须都在场**，两两各挡一个失效：

    * 少了「匿名 401」→ 把闸门整个摘掉是绿的；
    * 少了「普通教师 403」→ 把 ``require_admin`` 改回 ``require_staff``
      （= Task 2 之前的口径）是绿的，而那是本 Task 要防的**那一次退化**；
    * 少了「管理员放行」→ 把闸门写成 ``raise HTTPException(403)``（谁都写不了）是绿的。

    ------------------------------------------------------------------
    ⚠️⚠️ 被测面一律走 ``app.openapi()["paths"]`` 与**实发请求**，绝不走 ``app.routes``
    ------------------------------------------------------------------

    FastAPI 0.141.1 的 ``include_router`` 是**惰性的**：23 个资源的路由被折叠成一个
    ``_IncludedRouter``，故 ``len(app.routes)`` 实测只有 **6**。终审专门验证过：
    按 ``app.routes`` 写的路由/安全扫描是**假绿**的——它在今天正确的接线上报 0 个问题，
    在一个把顺序排反的最小 app 上**也**报 0 个问题。
    （那条警告的住址是 :mod:`app.api.routers` 的模块级注释，本条是它的第二个落点。）

    ------------------------------------------------------------------
    四格各自挡什么
    ------------------------------------------------------------------

    ① **OpenAPI 面**：可写资源的 ``post`` / ``patch`` / ``delete`` 三个操作的
      ``security`` 逐字等于 ``[{"X-Teacher-Staff-No": []}]``——它挡的是
      「判定挂了、声明没挂」（前端从 spec 上看不出来要带头，一接就 401，
      那正是 P4-A5 当初要修的缺口）。
      ⚠️ **Plan 05A Task 2 之后这一格逐字不变**：管理员就是一行 ``teacher``，
      故载体仍然是那个请求头，改的只是**判定**（``require_staff`` → ``require_admin``）。
      于是「挂 ``security`` 的操作数」在 Task 2 里**不动**（48）。
    ② **行为面（匿名）**：不带头实发一次写请求 → **401**——它挡的是
      「声明挂了、判定没挂」（``TEACHER_STAFF_NO_SCHEME`` 是 ``auto_error=False`` 的，
      只挂 ``Security(...)`` 而漏掉 :func:`app.api.crud._require_admin_identity`
      的话，spec 上写了、实际谁都放行）；
    ③ **行为面（普通教师）**：带一个在册**非管理员**的工号 → **403 ``forbidden``**，
      且 message 里点名 ``role``（前端要能翻译成「管理台只有教务干事能改」，
      而一个光秃秃的 403 会让用户以为登录坏了、去反复重登）；
    ④ **只读那一半**：POST/PATCH/DELETE 一律 405，且 ``paths`` 里根本没有那些方法
      （两个学生侧特例 POST 是 :data:`_STUDENT_OWNED_POSTS` 那条字面例外）。

    ⚠️ 主键一律用**不存在**的 ``424243``（②③ 两拍）：401/403 必须排在 404 之前，
    而用一个存在的行会让「先 404 再 401」这个错序看不出来。
    ⚠️ 请求体一律是 ``{}``：实测**依赖跑在请求体校验之前**，故不带头时得到的是 401
    而不是 422（那一格由 :func:`test_a_value_outside_the_model_domain_is_422_not_409`
    的注释点名）。于是本条不必为 9 个资源各造一份合法请求体。
    ⚠️⚠️ **而「管理员放行」那一拍因此不能用 POST**：``{}`` 会让它落到 422
    （请求体校验），而 422 与 200 都只证明「闸门放行了」，看不出区别——
    但 422 也**证明不了**写入真的能成。故那一拍用 **PATCH ``{}``**：
    ``exclude_unset=True`` 让它「一个键都不改」，于是响应是 **200**（不是 422、
    不是 403），且 9 个资源共用同一份请求体。
    ⚠️ 而「管理员真的能建一行、真的能删一行」由
    :func:`test_an_admin_can_create_and_delete_while_a_teacher_cannot` 单独钉住
    （POST → **201** + ``Location`` 头、DELETE → **204**），
    两条守卫**并列、不合并**：本条管「9 个资源逐个都放行管理员」，
    那一条管「放行之后写入真的走得通」。
    """
    paths = app.openapi()["paths"]
    missing_pk = 424243

    detail_of: dict[str, str] = {}
    for spec in RESOURCES:
        path = spec["path"]
        segments = len(path.split("/"))
        found = [
            key for key in paths
            if key.startswith(path + "/{") and len(key.split("/")) == segments + 1
        ]
        assert len(found) == 1, (path, found)
        detail_of[path] = found[0]

    checked = {"post": 0, "patch": 0, "delete": 0}
    admitted = 0
    for spec in RESOURCES:
        path, detail = spec["path"], detail_of[spec["path"]]
        forbidden_delete = spec["on_delete"] == ON_DELETE_FORBID
        if spec["writable"]:
            # ①②③：三个写方法各来两发（匿名 + 普通教师）。⚠️ 实发请求打的是**具体 URL**
            #    （``{path}/{不存在的主键}``），而查 OpenAPI 用的是**路径模板** ``detail``。
            concrete = path + "/" + str(missing_pk)
            for method in ("post", "patch", "delete"):
                template = path if method == "post" else detail
                url = path if method == "post" else concrete
                if method == "delete" and forbidden_delete:
                    # on_delete="forbid" → DELETE 端点根本不注册 → 405（不是 401/403）
                    assert "delete" not in paths[detail], (path, "forbid 却注册了 DELETE")
                    assert client.delete(concrete).status_code == 405, path
                    # ⚠️ 普通教师那一拍也是 405：路由根本不注册，故 405 由 Starlette 的
                    #    路由匹配给出、**先于**任何身份判定（带上头也仍是 405）。
                    assert client.delete(
                        concrete, headers=plain_teacher_headers
                    ).status_code == 405, path
                    continue
                anonymous = client.request(method, url, json={})
                assert anonymous.status_code == 401, (
                    f"{method.upper()} {template} 不带教师头应当是 401，"
                    f"实际 {anonymous.status_code}：{anonymous.text}"
                )
                assert anonymous.json()["error"]["code"] == "unauthenticated", (path, method)
                # ③ 在册**非管理员** → 403（Plan 05A Task 2 加的那一拍）
                teacher = client.request(method, url, json={}, headers=plain_teacher_headers)
                assert teacher.status_code == 403, (
                    f"{method.upper()} {template} 带一个普通教师的工号应当是 403，"
                    f"实际 {teacher.status_code}：{teacher.text}"
                )
                body = teacher.json()["error"]
                assert body["code"] == "forbidden", (path, method, body)
                assert "role" in body["message"], (path, method, body["message"])
                operation = paths[template][method]
                assert operation["security"] == [{"X-Teacher-Staff-No": []}], (
                    path, method, operation.get("security")
                )
                checked[method] += 1
            # ③′ 管理员放行：用 PATCH {}（唯一一个不需要合法请求体就能 2xx 的写方法，
            #     理由逐字见上面 docstring 末段）。打的是 seeded 那一行**存在**的主键。
            patched = client.patch(
                path + "/" + str(seeded[spec["model"].__tablename__]),
                json={},
                headers=admin_headers,
            )
            assert patched.status_code == 200, (
                path, patched.status_code, patched.text,
                "管理员应当被放行（200 = 一个键都不改的 PATCH），"
                "403 意味着 require_admin 把管理员也挡了、"
                "401 意味着身份根本没被认出来",
            )
            admitted += 1
            # 而 GET 的口径按本行声明的 read_scope 分**四档**
            # ⚠️⚠️ **Plan 05A Task 5 之前这里逐字是「GET 仍然匿名」三行断言**
            #    （``client.get(path) == 200`` + 两个 ``"security" not in …``）；
            #    Task 5 把它分成两档（``read_requires_staff`` 的有/无）；
            #    **安全收紧波分成三档**（``read_scope`` 的 ``None`` / ``"staff"`` /
            #    ``"student_self"``）；**Plan 06 Task 8 分成四档**（+ ``"staff_taught"``）。
            #    ⚠️ 分档是**必须**的：一律按「匿名」断的话
            #    16 行会红，一律按「要身份」断的话「把闸门挂到全部 23 个资源上」
            #    这一档会静默（硬规矩 #50：两侧都得在场）。
            #    ⚠️ 而**7 行仍然走 else 那一支**，故「参考数据要能不登录就读」
            #    这条口径**照旧被验证**。
            #    ⚠️⚠️ **本条对第四档只断「两个 GET 都 200 + security 那一格的形状」**：
            #    「教师读到多少行」不在这里断（本夹具的 ``plain_teacher_headers``
            #    是一位**不教任何班**的教师，故他读到的是 ``total == 0``），
            #    那是 :func:`test_the_student_keyed_resources_admit_four_read_tiers` 的活。
            # ⚠️ 本拍**只断教职那一档放行**（教师 + 管理员都 200），
            #    不断「学生只读自己的」——那是
            #    :func:`test_the_student_keyed_resources_admit_four_read_tiers` 的活
            #    （本条的夹具里没有学生行，而造一个要连 ``seeded`` 的拓扑序一起改）。
            if spec["read_scope"] is None:
                assert client.get(path).status_code == 200, path
                assert "security" not in paths[path]["get"], path
                assert "security" not in paths[detail]["get"], path
            else:
                assert client.get(path).status_code == 401, (path, "本行的 list 应当要身份")
                assert client.get(path, headers=admin_headers).status_code == 200, path
                assert client.get(path, headers=plain_teacher_headers).status_code == 200, path
                want = [{"X-Teacher-Staff-No": []}]
                if spec["read_scope"] in STUDENT_SCOPED_READ_VALUES:
                    # ⚠️ 按学生键收窄的那**两档**都声明**两个** scheme（OR 语义）：
                    #    四档身份里学生与教职都能过，而
                    #    :func:`app.api.deps.current_reader` 一次解析、就地分档。
                    #    ⚠️⚠️ 于是 **Plan 06 Task 8 加第四档时 openapi 的 ``security``
                    #    一格一个字节都没变**（改的是「教师读到多少行」，不是「谁能打」）。
                    want = [{"X-Student-Id": []}, {"X-Teacher-Staff-No": []}]
                for template in (path, detail):
                    assert paths[template]["get"]["security"] == want, (path, template)
        else:
            # ③：只读资源一律没有写端点
            got = client.post(path, json={})
            expected = 401 if path in _STUDENT_OWNED_POSTS else 405
            assert got.status_code == expected, (path, got.status_code, got.text)
            if path in _STUDENT_OWNED_POSTS:
                assert paths[path]["post"]["security"] == [{"X-Student-Id": []}], path
            else:
                assert "post" not in paths[path], path
            assert "patch" not in paths[detail], path
            assert "delete" not in paths[detail], path
            concrete = path + "/" + str(missing_pk)
            assert client.patch(concrete, json={}).status_code == 405, path
            assert client.delete(concrete).status_code == 405, path

    # ⚠️ 本条会在 RESOURCES 被写空时空转全绿，故钉一下**真的**遍历到了东西：
    # 9 POST + 9 PATCH + 8 DELETE = 26（semesters 是 forbid、没有 DELETE）。
    # ⚠️ 那两个计数各自挡一个空转：``checked`` 数的是「匿名 + 普通教师」两拍跑了几发，
    # ``admitted`` 数的是「管理员放行」那一拍跑了几个资源。少了后者，
    # 「9 个资源里只有第一个被放行、其余 8 个都 403」是绿的。
    assert checked == {"post": 9, "patch": 9, "delete": 8}, checked
    assert admitted == 9, admitted


def test_an_admin_can_create_and_delete_while_a_teacher_cannot(
    client, seeded, admin_headers, plain_teacher_headers
):
    """**三拍守卫的第四拍**：管理员放行之后，写入**真的走得通**（201 + ``Location`` + 204）。

    ⚠️ 与 :func:`test_every_writable_resource_admits_only_an_admin_mutation` 的分工：
    那一条管「9 个资源逐个都放行管理员」（用 PATCH ``{}`` → 200，因为它是唯一一个
    不需要合法请求体就能 2xx 的写方法），本条管「放行之后一次完整的写-改-删」。
    两条**并列、不合并**：只有前者的话，「闸门放行了、但 ``require_admin`` 之后
    的某一步炸了」是绿的；只有后者的话，另外 8 个资源没有被覆盖。

    ⚠️ 顺带钉住 :class:`app.api.schemas.organisation.TeacherCreate` 的三格：

    * ``role`` 的**缺省是 ``teacher``**——建一个管理员必须是一次显式的
      ``{"role": "admin"}``，故「漏写 role」的失效方向是安全的（少给权限，不是多给）；
    * ``role`` **可以由管理员改**（提权 / 降权），而 ``POST /api/teachers`` 本身
      仅管理员可调，故「谁能造出一个管理员」的答案是「已经是管理员的人」；
    * ``role`` 的取值域由 **Pydantic** 判 → **422 ``request_validation_failed``**，
      不是 DB 的 CHECK 撞出来的 **409 ``integrity_conflict``**
      （本包约定：枚举列两处设防，而 HTTP 边界上正确的那个码是 422，
      理由逐字见 :func:`app.api.schemas._base.one_of` 的 docstring）。
    """
    payload = {"staff_no": "T2025902", "name": "新建的教师"}

    # ① 普通教师：三发全 403，且 message 点名 role（前端要能翻译成人话）
    for method, url, kwargs in (
        ("post", "/api/teachers", {"json": payload}),
        ("patch", "/api/teachers/1", {"json": {"name": "改过名字"}}),
        ("delete", "/api/teachers/1", {}),
    ):
        got = client.request(method, url, headers=plain_teacher_headers, **kwargs)
        assert got.status_code == 403, (method, url, got.status_code, got.text)
        assert got.json()["error"]["code"] == "forbidden", (method, url)
        assert "role" in got.json()["error"]["message"], (method, url, got.text)

    # ② 管理员：201 + Location，且缺省 role 是 teacher
    created = client.post("/api/teachers", json=payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    new_id = created.json()["id"]
    assert created.headers["Location"] == f"/api/teachers/{new_id}"
    assert created.json()["role"] == "teacher", (
        "新建教师的缺省 role 必须是 teacher：漏写 role 的失效方向应当是「少给权限」"
    )
    assert created.json()["staff_no"] == payload["staff_no"]

    # ③ 管理员：PATCH 200 / DELETE 204（而普通教师那两发上面已经断过 403）
    patched = client.patch(
        f"/api/teachers/{new_id}", json={"name": "改过名字"}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "改过名字"
    assert client.delete(f"/api/teachers/{new_id}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/teachers/{new_id}", headers=admin_headers).status_code == 404

    # ④ role 可以由管理员显式给出（提权），且取值域由 Pydantic 判 → 422 不是 409
    promoted = client.post(
        "/api/teachers",
        json={"staff_no": "T2025903", "name": "新干事", "role": "admin"},
        headers=admin_headers,
    )
    assert promoted.status_code == 201, promoted.text
    assert promoted.json()["role"] == "admin"
    bad_role = client.post(
        "/api/teachers",
        json={"staff_no": "T2025904", "name": "x", "role": "校长"},
        headers=admin_headers,
    )
    assert bad_role.status_code == 422, bad_role.text
    assert bad_role.json()["error"]["code"] == "request_validation_failed"
    # ⚠️ 取值域那一句在 ``detail`` 里、不在 ``message`` 里（``message`` 是
    # ``request_validation_failed`` 那一档固定的「请求参数校验未通过」，
    # 逐字理由见 app/api/errors.py 的 _request_validation）
    assert "role" in str(bad_role.json()["error"]["detail"])
    assert "admin" in str(bad_role.json()["error"]["detail"]), (
        "422 的 detail 里没有取值域，前端无从提示用户「只能填 teacher 或 admin」"
    )


def test_the_factory_rejects_a_bad_configuration():
    """工厂体里那**七道**配置校验**真的有牙**（每一条都能被改坏到红）。

    ⚠️ 第六道（``pk_alias`` 必须是标识符）是 Plan 03 Task 4 的 P4-A6 加的，
    第七道（``require_admin=True`` 与 ``writable=False`` 互斥）是 Plan 03 全分支
    终审之后加的，前五道是 Task 3 的。

    它们全部在**导入期**响（``catalog.py`` 在模块体里调 23 次工厂），故失败的形状是
    「``uvicorn`` 起不来 / pytest 收集期 ImportError」，而不是「某个端点在运行时炸」。
    """
    with pytest.raises(ValueError, match="on_delete"):
        build_crud_router(**_factory_spec(on_delete="nope"))
    with pytest.raises(ValueError, match="writable=True"):
        build_crud_router(**_factory_spec(writable=True))
    with pytest.raises(ValueError, match="cascade"):
        build_crud_router(**_factory_spec(on_delete=ON_DELETE_CASCADE))
    with pytest.raises(ValueError, match="不存在的列"):
        build_crud_router(**_factory_spec(natural_key=("nope",)))
    with pytest.raises(ValueError, match="必须挂在"):
        build_crud_router(**_factory_spec(path="/semesters"))
    # P4-A6：pk_alias 会逐字进 URL 模板与 /openapi.json，故一个不是标识符的别名要响。
    # ⚠️ 用连字符那一档（而不是空串）：连字符正是本仓 URL 的惯例，
    #    于是「照着 path 的写法填 pk_alias」是最可能犯的那个错。
    with pytest.raises(ValueError, match="pk_alias"):
        build_crud_router(**_factory_spec(pk_alias="semester-id"))
    # 第 7 道：只读资源根本不注册 POST/PATCH/DELETE，故 require_admin=True 是
    # **一件什么也不发生的事**——失效形态是静默的（端点没变、OpenAPI 没变），
    # 而它会让下一个人以为「这个资源被保护了」。
    with pytest.raises(ValueError, match="require_admin"):
        build_crud_router(**_factory_spec(require_admin=True))

    without_natural_key = _factory_spec()
    del without_natural_key["natural_key"]
    with pytest.raises(TypeError):
        build_crud_router(**without_natural_key)

    # 绿档：合法配置不抛（否则「一律抛」也能让上面全绿）
    assert build_crud_router(**_factory_spec()) is not None


def test_the_eleven_non_public_models_are_reached_through_their_submodules():
    """**P3-B1（本 Task 唯一的 Critical）**：11 个模型走子模块路径，另 12 个走公有面。

    三个侧面，缺一不可：

    ① **运行时**：23 个 ``model`` 的 ``__module__`` 逐个对到字面期望——
      4 个在 ``app.db.models.prescription``、7 个在 ``app.db.models.feedback``、
      其余 12 个在 ``organisation`` / ``assessment`` / ``derived``；
    ② **公有面**：那 11 个 ``hasattr(models, 名字) is False`` 且不在 ``models.__all__``
      ——于是 ``catalog.py`` 若写 ``models.Prescription`` 会是 ``AttributeError``，
      而「有人把它们重导出进公有面了」（Ruling 97 禁止的那件事）也会让本条红；
    ③ **源码面**（AST，不用正则数命中数——硬规矩 #89 的再扩写）：
      ``catalog.py`` 里确有两条 ``ImportFrom`` 分别从那两个子模块导入那 11 个名字，
      且 ``models.X`` 这种属性访问**恰好 12 处**、一处都不是那 11 个。

    ③ 是 ①② 补不上的那一格：①② 只证明「跑起来是对的」，
    而「用哪条 import 写出来的」只有源码面能钉。
    """
    observed: dict[str, set[str]] = {}
    for spec in RESOURCES:
        model = spec["model"]
        observed.setdefault(model.__module__, set()).add(model.__name__)
    assert observed == {
        "app.db.models.organisation": {
            "Semester",
            "Teacher",
            "Student",
            "CourseSection",
            "Enrollment",
        },
        "app.db.models.assessment": {
            "FitnessTestBatch",
            "FitnessTestResult",
            "BodyComposition",
            "InterestSurvey",
        },
        "app.db.models.derived": {
            "PercentileSnapshot",
            "DerivedMetrics",
            "StratificationResult",
        },
        "app.db.models.prescription": {
            "Exercise",
            "PrescriptionTemplate",
            "Prescription",
            "WeeklyAdjustment",
        },
        "app.db.models.feedback": {
            "ClassSession",
            "RpeRecord",
            "TrainingLog",
            "MiniTest",
            "Alert",
            "Notification",
            "WeeklyClassReport",
        },
    }

    eleven = set().union(*_NON_PUBLIC_MODULES.values())
    assert len(eleven) == 11
    for module, names in _NON_PUBLIC_MODULES.items():
        assert observed[module] == names
    for name in eleven:
        assert not hasattr(models, name), f"{name} 出现在 models 的公有面上了（Ruling 97）"
        assert name not in models.__all__

    public = [s["model"].__name__ for s in RESOURCES if s["model"].__name__ not in eleven]
    assert len(public) == 12
    for name in public:
        assert hasattr(models, name), name

    tree = ast.parse(pathlib.Path(catalog.__file__).read_text(encoding="utf-8"))
    imported: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module in _NON_PUBLIC_MODULES
        ):
            imported.setdefault(node.module, set()).update(a.name for a in node.names)
    assert imported == _NON_PUBLIC_MODULES

    attribute_access = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "models"
    }
    assert len(attribute_access) == 12, sorted(attribute_access)
    assert attribute_access.isdisjoint(eleven)


def test_every_resource_path_is_a_hyphenated_plural_under_api():
    """路径的形状：``/api/`` + 复数 + **连字符**（不是下划线），且与 ``tags`` 同串。

    连字符是 URL 惯例，而下划线是 DB 列名与 Pydantic 字段名的惯例——
    两套写法在同一个系统里并存，故 :mod:`app.api.crud` 的模块 docstring 里有一张
    23 行的对照表。本条钉住 URL 那一半：``tail`` 里一个下划线都不许有。
    """
    assert tuple(spec["path"] for spec in RESOURCES) == _EXPECTED_PATHS
    for spec in RESOURCES:
        assert spec["path"].startswith("/api/")
        tail = spec["path"][len("/api/") :]
        assert "_" not in tail, spec["path"]
        assert tail.endswith("s"), f"{spec['path']} 不是复数"
        assert spec["tags"] == [tail]


#: 23 个 detail 路径的**路径参数名**，逐个字面写死（硬规矩 #35：不从
#: :func:`app.api.crud._pk_alias_of` 读回来跟自己比，否则那条推导被改坏时本守卫恒绿）。
#: ⚠️ **与 :data:`_EXPECTED_PATHS` 同序**，故两行可以逐行对拍。
#:
#: ⚠️ **本清单是 Plan 03 Task 4 的 P4-A6 要求的「那条遍历型守卫要跟着改」的落点**：
#: 改名之前 23 个 detail 路径的参数名 distinct 实测是 ``['pk_value']``
#: （``/api/semesters/{pk_value}``），于是生成的 TS 客户端里到处是 ``pkValue``。
_EXPECTED_PK_ALIASES = (
    "semester_id",
    "teacher_id",
    "student_id",
    "course_section_id",
    "enrollment_id",
    "fitness_test_batch_id",
    "fitness_test_result_id",
    "body_composition_id",
    "interest_survey_id",
    "percentile_snapshot_id",
    "derived_metric_id",
    "stratification_result_id",
    "exercise_id",
    "prescription_template_id",
    "prescription_id",
    "weekly_adjustment_id",
    "class_session_id",
    "rpe_record_id",
    "training_log_id",
    "mini_test_id",
    "alert_id",
    "notification_id",
    "weekly_class_report_id",
)


def test_every_detail_path_names_its_pk_after_the_resource(client):
    """**P4-A6 的遍历型守卫**：23 个 detail 路径的参数名逐个等于资源名的单数 + ``_id``。

    三个侧面，缺一不可：

    ① **URL 模板真的变了**——``paths`` 里那把键是 ``/api/semesters/{semester_id}``
       而不是 ``/api/semesters/{pk_value}``。这一格是本条存在的理由：
       ``pk_alias`` 是一个**纯 OpenAPI 层**的改名，除了这里的键与那个 parameter 的
       ``name``，运行时没有任何别的地方能看出它生效了。
    ② **``GET`` 那个操作的 path 参数名就是它**（且 ``in == "path"``）。
       ⚠️ 与①不是同一件事：模板里的占位符名与 parameter 的 ``name`` 由 FastAPI
       分别从路由与函数签名取，而本仓的函数形参**仍叫 ``pk_value``**、靠
       ``Path(alias=…)`` 绑过去——绑错了的话①对而②错。
    ③ **distinct 恰好是那 23 个名字**，即一个都不重、一个都没漏。
       ⚠️ 这一格顺带钉住了「改名前的那个值已经彻底消失」：
       ``"pk_value" not in distinct``。

    ⚠️ **两侧不同源**（硬规矩 #35）：期望侧是上面那份字面清单，被测侧是
    ``/openapi.json``（HTTP 实读，不是 ``app.openapi()`` 的内存对象——两者今天等价，
    但前者连「``/openapi.json`` 这个端点还挂着」一起验了）。
    """
    assert len(_EXPECTED_PATHS) == len(_EXPECTED_PK_ALIASES) == 23
    paths = client.get("/openapi.json").json()["paths"]

    distinct: set[str] = set()
    for path, alias in zip(_EXPECTED_PATHS, _EXPECTED_PK_ALIASES):
        key = path + "/{" + alias + "}"
        assert key in paths, f"{key} 不在 openapi 的 paths 里：{sorted(paths)}"
        params = paths[key]["get"]["parameters"]
        in_path = [p for p in params if p["in"] == "path"]
        assert [p["name"] for p in in_path] == [alias], (key, params)
        assert in_path[0]["required"] is True, key
        assert in_path[0]["schema"]["type"] == "integer", key
        distinct.add(alias)

    assert len(distinct) == 23, sorted(distinct)
    assert distinct == set(_EXPECTED_PK_ALIASES)
    assert "pk_value" not in distinct, "P4-A6 的改名没有生效"
    # 旧模板一把都不许留下（改名是**替换**，不是新增一个别名）
    assert not [key for key in paths if key.endswith("/{pk_value}")]


def test_the_automatic_pk_alias_is_the_singular_resource_name_plus_id():
    """:func:`app.api.crud._pk_alias_of` 的推导规则，**含两档 23 个资源里没有的形状**。

    前六格是计划 P4-A6 逐字点名的例子（``semesters`` / ``course-sections`` /
    ``fitness-test-results``）与它们的同族。

    ⚠️ **中间两格是「末尾不是 s」那一档**：23 个资源里一个都没有它，故它是
    **许可而不是断言**（硬规矩 #39），但没有它的话「一个单数路径推出 ``_id``」
    这个失效形态就没有任何守卫看着。

    ⚠️⚠️ **最后一格是把推导的「笨」钉住（不是把它钉对）**：``-es`` 结尾的复数会多留
    一个 ``e``，而 23 个资源里恰好有一个是这一档（``fitness-test-batches``），
    它因此**显式**传了 ``pk_alias``（下面第二段钉住「恰好那一行、也只有那一行」）。
    本格的价值是：谁把推导改成「认得 -es」，这里会红——而那是一次**需要被看见**的
    改动，因为英语复数还原有例外（``exercises`` 只去 ``s``），改它就要引入一份后缀词表。
    """
    cases = {
        "/api/semesters": "semester_id",
        "/api/course-sections": "course_section_id",
        "/api/fitness-test-results": "fitness_test_result_id",
        "/api/weekly-class-reports": "weekly_class_report_id",
        "/api/mini-tests": "mini_test_id",
        "/api/derived-metrics": "derived_metric_id",
        # 末尾不是 s：原样保留 + _id（不是 "_id"）
        "/api/probe": "probe_id",
        "/api/probe-training-log": "probe_training_log_id",
        # -es 结尾的复数：多留一个 e（推导刻意保持笨，见 docstring）
        "/api/fitness-test-batches": "fitness_test_batche_id",
        "/api/exercises": "exercise_id",
    }
    for path, want in cases.items():
        assert _pk_alias_of(path) == want, path
    # 23 个资源路径逐个跑一遍：自动推导与上面那份字面清单（= openapi 里实读到的名字）
    # **恰好只差一格**，就是 -es 那一档；差的那一格由 RESOURCES 显式覆盖补上。
    # ⚠️ 两侧不同源：这一侧是 _pk_alias_of 的输出，那一侧是 openapi 实读的名字。
    differences = [
        (path, _pk_alias_of(path), pinned)
        for path, pinned in zip(_EXPECTED_PATHS, _EXPECTED_PK_ALIASES)
        if _pk_alias_of(path) != pinned
    ]
    assert differences == [
        (
            "/api/fitness-test-batches",
            "fitness_test_batche_id",
            "fitness_test_batch_id",
        )
    ], differences
    # 「显式覆盖」恰好一行、且就是那一行（两侧不同源：这一侧读 RESOURCES 的字面键，
    # 那一侧是 openapi 实读出来的 23 个名字）。
    explicit = [spec["path"] for spec in RESOURCES if spec.get("pk_alias") is not None]
    assert explicit == ["/api/fitness-test-batches"]
    assert [spec["pk_alias"] for spec in RESOURCES if "pk_alias" in spec] == [
        "fitness_test_batch_id"
    ]


def test_an_explicit_pk_alias_overrides_the_automatic_one(app, engine, client):
    """``pk_alias`` 显式传时**覆盖**自动推导，且覆盖之后端点**真的还能用**。

    ⚠️ **23 行 ``RESOURCES`` 一个都没显式传它**，故这一档是「有能力、无生产调用方」
    （硬规矩 #39），本条用一个合成资源把它跑通，于是它不是死代码。
    第二拍（真的打一次 GET 并拿到 200）是承重的：只断言 OpenAPI 里那个名字的话，
    「模板改了而 ``Path(alias=…)`` 忘了绑」会给出一个**看起来对**的 spec
    和一个必然 404 的端点。
    """
    app.include_router(
        build_crud_router(
            model=Semester,
            schemas=CrudSchemas(SemesterRead),
            path="/api/probe-semesters",
            tags=["probe"],
            writable=False,
            on_delete=ON_DELETE_FORBID,
            natural_key=("name",),
            pk_alias="which_semester",
        )
    )
    with Session(engine) as session:
        # ⚠️ 不用 SEMESTER_PAYLOAD：那一份的两个日期是 **ISO 字符串**（它是给 POST 的
        #    JSON 请求体用的，Pydantic 会解析），而直接构造 ORM 行时 SQLite 的 Date
        #    绑定处理器要的是真的 date 对象。
        row = Semester(
            name=SEMESTER_PAYLOAD["name"],
            start_date=D(2025, 9, 1),
            end_date=D(2025, 12, 22),
            weeks=16,
            is_current=True,
        )
        session.add(row)
        session.commit()
        pk = row.id

    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/probe-semesters/{which_semester}" in paths, sorted(paths)
    # 自动推导出来的那个名字**不得**同时存在（覆盖，不是并存）
    assert "/api/probe-semesters/{probe_semester_id}" not in paths

    got = client.get(f"/api/probe-semesters/{pk}")
    assert got.status_code == 200, got.text
    assert got.json()["name"] == SEMESTER_PAYLOAD["name"]
    assert client.get("/api/probe-semesters/999999").status_code == 404


#: -----------------------------------------------------------------------
#: 档 1：**服务端填、但要暴露**（``*Create`` / ``*Update`` 刻意不含，``*Read`` **含**）
#: -----------------------------------------------------------------------
#:
#: 客户端传了也没用（Pydantic 缺省 ``extra="ignore"``，多传的键被静默丢掉），
#: 但读侧仍然要看得见它——例如服务端算出来的 ``late`` / ``normalized_score`` 一类。
#:
#: 与 Task 4 的 ``OverrideCreate`` 少两格、Task 5 的 ``RpeSubmitCreate`` 少两格是
#: **同一条纪律**，只是那两处是特例端点的请求模型、不在 ``RESOURCES`` 里，
#: 故由 ``tests/api/test_prescription_api.py`` / ``tests/api/test_feedback.py`` 各自钉。
#:
#: ⚠️ ``class_session.rpe_token`` 自 Plan 03 全分支终审的 I4 之后进本清单：
#: 教师「发起课堂快评」的正主是 ``POST /api/class-sessions/{id}/open-rpe``
#: （全仓唯一调 :func:`app.api.routers.feedback._new_rpe_token` 的地方，
#: 强制 CSPRNG 与 ``RPE_TOKEN_LEN`` 长度不变量），而 **SQLite 不强制 ``VARCHAR`` 长度**，
#: 故走泛型 POST/PATCH 写一个超长口令**永远不报错**——那正是 ``_new_rpe_token`` 的
#: docstring 自己点名的失效形态（换到严格长度的后端会被静默截断、从此永远校验不过）。
#: ⚠️ 而它**同时**在档 2 里（:data:`_SERVER_GENERATED_HIDDEN_COLUMNS`）：
#: 收尾小修波把它从 ``ClassSessionRead`` 上也摘掉了，故「写不进去」与「读不出来」
#: 两半各自有一份清单点名。**两档语义不同、刻意不合并成一个**：
#: 档 1 只影响 ``*Create`` / ``*Update``，档 2 只影响 ``*Read``，
#: 一份合并的清单会说不清「哪一半被摘掉了」。
_SERVER_FILLED_COLUMNS: dict[str, tuple[str, ...]] = {
    "/api/class-sessions": ("rpe_token",),
    # ⚠️ **Plan 05A Task 1 加的两行**（凭据的两列）：``password_hash`` 与
    # ``password_bound_at`` 都由 ``POST /api/auth/{students,teachers}/bind`` 填
    # （服务端算哈希、服务端盖时刻），故 ``*Create`` / ``*Update`` 刻意不含它们。
    # ⚠️ **那一格是承重的、不只是「传了也没用」**：能被 POST 写进去的口令哈希等于
    # 「任何在册教师（Plan 05A Task 2 之后是任何管理员）可以给任何学生/教师
    # 设一个自己知道的口令」，而那就是绕过绑定流程的验身材料本身。
    # ⚠️ 而 ``password_bound_at`` **在 ``*Read`` 里是暴露的**（档 1 的语义正是
    # 「服务端填、但要暴露」）：管理台要看「谁还没注册」。
    "/api/students": ("password_hash", "password_bound_at"),
    "/api/teachers": ("password_hash", "password_bound_at"),
}

#: -----------------------------------------------------------------------
#: 档 2：**服务端生成、且不在 read 模型里暴露**（``*Read`` 刻意不含；它是秘密）
#: -----------------------------------------------------------------------
#:
#: ⚠️ 本清单是 Plan 03 收尾小修波加的（终审 fix 波把这一格登记为关切并移交，本波兑现）。
#: 它钉的是「``*Read`` 与 DB 列逐字对齐」那条口径的**唯一例外**：
#:
#: ``rpe_token`` 是**学生提交课堂快评的唯一闸门**（``POST /api/rpe-records`` 校验它，
#: 口令不对是 403 ``invalid_rpe_token``），而它存在的理由是挡「学生猜 ``class_session_id``
#: 乱交」（:func:`app.api.routers.feedback._new_rpe_token` 的 docstring）。
#: ⚠️ 而**泛型 ``GET`` 一律匿名**（Task 3 的偏离 ⑦，用户 2026-10-08「加强制」裁定
#: 逐字保留了读的一侧），故那一格留在 ``ClassSessionRead`` 上等于
#: **任何人 ``GET /api/class-sessions`` 就能读到全部口令**——闸门形同虚设。
#:
#: ⚠️ 于是「服务端生成」在本仓分成两档，两份清单各管一档：
#:
#: * 档 1（:data:`_SERVER_FILLED_COLUMNS`）——服务端填、**要**暴露（``*Read`` 含它）；
#: * 档 2（本清单）——服务端生成、**且是秘密**（``*Read`` **不含**它）。
#:
#: ⚠️ **摘掉一列不等于关掉那扇门**（控制者的裁定，方案 b）：教师仍然看得到口令，
#: 只是换了一个**要教师头**的窄端点
#: ``GET /api/class-sessions/{class_session_id}/rpe-token``
#: （:func:`app.api.routers.feedback.read_rpe_token`，返回**既有的**那一个、
#: **不重新生成**；快评没发起时是 **409** ``rpe_not_opened``，不是 ``null``）。
#: 守卫是 ``tests/api/test_feedback.py`` 的四条
#: ``test_the_rpe_token_*``。⚠️ 那个端点因此让「挂 ``security`` 的操作数」
#: 从 44 变成 **45**（``tests/api/test_prescription_api.py`` 末尾钉住）。
#:
#: ⚠️⚠️ **本清单只管 read 模型那一半，而洞有另一半**：泛型 **list 端点不走
#: ``response_model``**（它显式只 SELECT ``kept`` 那些列、手工拼 dict），故光是把
#: ``rpe_token`` 从 ``ClassSessionRead`` 上摘掉，``GET /api/class-sessions``
#: ——**正是终审点名的那个 URL**——照旧原样返回全部口令。另一半的住址是
#: :data:`app.api.routers.catalog.RESOURCES` 里 ``/api/class-sessions`` 那一行的
#: ``"list_exclude": ("rpe_token",)``（23 行里唯一一行），守卫是本文件的
#: :func:`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
#: （它也读本清单，故两侧**共用一份**期望）。
#: ⚠️ 于是「一个秘密列不再匿名可读」在本仓有**两个**住址、两条守卫：
#: 读模型（本清单 + 第一拍的对齐断言）与 list（``list_exclude`` + 遍历守卫）。
#: **加第二个秘密列时两处都要改**，只改一处会得到一个「看起来修好了」的洞。
_SERVER_GENERATED_HIDDEN_COLUMNS: dict[str, tuple[str, ...]] = {
    "/api/class-sessions": ("rpe_token",),
    # ⚠️ **Plan 05A Task 1 加的两行**（口令哈希）。它与 ``rpe_token`` 是同一档
    # 而**严重性更高**：``rpe_token`` 泄漏的后果是「有人能替学生交课堂快评」，
    # 而口令哈希泄漏的后果是**离线爆破**（一个 PBKDF2-SHA256 串在 GPU 上是几小时的事），
    # 且爆破出来的口令**在别的系统上也可能能用**（用户复用口令是常态），
    # 而原型没有找回流程，故泄漏是**不可撤销**的。
    # ⚠️ 改前这一行还写着「也没有登录失败锁定」—— 那一句在 Plan 06 Task 3 之后就是
    #    **假的**（锁定真的在：同一个 ``(kind, login)`` 在窗口内失败到阈值就锁，
    #    逐字口径见 ``app/auth/policy.py`` 与 spec §13.4.6），终审 S1-2 的同族自查挖到它。
    #    ⚠️ 而**本条的结论一个字都不变**：锁定挡的是「在线一个账号一个账号地试」，
    #    而口令哈希泄漏之后是**离线**爆破（GPU 上几小时），锁定在那一档一次都不参与。
    # ⚠️ 于是这两行的另一半（list 端点）在 ``catalog.RESOURCES`` 的
    # ``students`` / ``teachers`` 两行上各写了一个 ``"list_exclude": ("password_hash",)``
    # ——本清单只管 ``*Read``，而泛型 list **不走 ``response_model``**，
    # 两半缺一不可（本常量上面那段注释逐字写了这个形状）。
    # ⚠️⚠️ **安全收紧波给这两行各加了第二列 ``password_bound_at``**
    # （控制者裁定 3）。此前本处逐字写的是「``password_bound_at`` **不在本清单里**
    # （它不是秘密），故它在 ``*Read`` 里」——那句话的**前提**（「不是秘密 ⇒ 可以暴露」）
    # 被终审的附带发现推翻了：它告诉一个教职**哪些账号还没绑口令**，
    # 也就是**哪些还能被抢占绑定**（``POST /api/auth/{students,teachers}/bind``
    # 只对 ``password_hash IS NULL`` 的行放行，故它挡不住抢占）。
    # ⚠️ 教职专用故低危（要读到它先得有一个在册教职会话），但本波在收读侧，顺手一并摘掉。
    # ⚠️ **四处缺一不可**（与 ``rpe_token`` 同一个形状）：本清单（档 2）+
    # ``StudentRead`` / ``TeacherRead`` 摘列 + ``catalog.RESOURCES`` 两行的
    # ``list_exclude`` 各加一格 + 下面那条三拍守卫
    # （:func:`test_password_bound_at_is_absent_from_both_the_read_model_and_the_list`）。
    "/api/students": ("password_hash", "password_bound_at"),
    "/api/teachers": ("password_hash", "password_bound_at"),
}


def test_every_read_schema_covers_exactly_the_model_columns():
    """41 个模型的字段集与 DB 列集**逐字对齐（含声明顺序）**。

    两侧不同源：期望侧是 ``model.__table__.columns``（SQLAlchemy 的元数据），
    被测侧是 ``BaseModel.model_fields``（Pydantic 的元数据）。
    于是「schema 少写了一列」「多写了一列」「把列名拼错了」三种失效都会红——
    而它们是 41 个类 × 平均 9 个字段这套手写代码最可能犯的错。

    ⚠️ **``*Read`` 的对齐自 Plan 03 收尾小修波起有一份例外清单**
    :data:`_SERVER_GENERATED_HIDDEN_COLUMNS`（**Plan 05A Task 1 起 3 格**：
    ``class_session.rpe_token`` 与 ``student`` / ``teacher`` 各自的 ``password_hash``，
    三格都是秘密而泛型 ``GET`` 一律匿名，理由逐字见那个常量的注释）。
    ⚠️ 例外**不削弱**本条：它按 ``path`` 精确点名到列，且本条**反向**也钉
    （清单里点名的列必须①真的是该表的一列、②真的**不在**读模型上），
    于是「把一列写进清单来绕过对齐断言」会让②红——除非它真的从 ``*Read`` 上摘掉了，
    而那正是本条要它做的事。⚠️ 另外 ``len(_SERVER_GENERATED_HIDDEN_COLUMNS) == 3``
    与它**逐格点名的那份字面清单**也被钉住：例外清单**长出来**（有人嫌对齐断言碍事、
    往里加第四行）会当场红，而一次「加一行」的改动在只有①②两拍时是**静默**的。

    ⚠️ 顺带钉住两条形状规则：``*Create`` / ``*Update`` 的字段集 = 全部列**减去 ``id``**
    （代理键由 SQLite 给）**再减去** :data:`_SERVER_FILLED_COLUMNS` 里那几列
    （服务端填的，客户端传了也没用），且 ``*Update`` 的每个字段都**有缺省值**
    （PATCH 的 ``exclude_unset`` 语义要求「没传」是可表达的）。
    ⚠️ 那份清单是**字面写死**的（硬规矩 #35），且本条**反向**也钉：清单里点名的列
    必须①真的是该表的一列、②真的**不在**那两个模型上。少了②，
    「把一列写进清单来绕过对齐断言」就成了一件事什么也不做的改动。
    """
    counted = 0
    for spec in RESOURCES:
        columns = [c.name for c in spec["model"].__table__.columns]
        hidden = _SERVER_GENERATED_HIDDEN_COLUMNS.get(spec["path"], ())
        assert list(spec["schemas"].read.model_fields) == [
            c for c in columns if c not in hidden
        ], spec["path"]
        for name in hidden:
            assert name in columns, (spec["path"], name, "清单里点名的不是该表的列")
            assert name not in spec["schemas"].read.model_fields, (spec["path"], name)
        counted += 1
        if spec["writable"]:
            server_filled = _SERVER_FILLED_COLUMNS.get(spec["path"], ())
            without_id = [
                c for c in columns if c != "id" and c not in server_filled
            ]
            assert list(spec["schemas"].create.model_fields) == without_id, spec["path"]
            assert list(spec["schemas"].update.model_fields) == without_id, spec["path"]
            for name in server_filled:
                assert name in columns, (spec["path"], name, "清单里点名的不是该表的列")
                assert name not in spec["schemas"].create.model_fields, (spec["path"], name)
                assert name not in spec["schemas"].update.model_fields, (spec["path"], name)
            required = [
                name
                for name, field in spec["schemas"].update.model_fields.items()
                if field.is_required()
            ]
            assert required == [], (spec["path"], required)
            counted += 2
        else:
            assert spec["schemas"].create is None, spec["path"]
            assert spec["schemas"].update is None, spec["path"]
    assert counted == 41
    # ⚠️ 例外清单的**大小**也钉住。**Plan 05A Task 1 把它从 1 抬到 3**
    # （+ ``student.password_hash`` 与 ``teacher.password_hash``）；
    # **安全收紧波把它从 3 抬到 5**（+ ``student.password_bound_at`` 与
    # ``teacher.password_bound_at``，控制者裁定 3：它告诉一个教职「哪些账号还没绑口令」
    # = 哪些还能被抢占绑定；理由与代价逐字见 ``app/api/schemas/organisation.py`` 的
    # ``TeacherRead``）。⚠️ 抬它是一次「让某个 ``*Read`` 少一列」的显式登记，而本行的存在
    # 正是为了让这次登记**必须发生在这里**（少了本行，加第四行是静默的）。
    # 判据是「**每一个**例外都得是一个凭据/秘密」，而不是「例外只有一个」——
    # 后者在第二个秘密列出现的那天就已经过期了。
    # ⚠️ **两个数分开钉**：``len(...)`` 是**几个资源**有例外（仍 3），
    # ``sum(len(v))`` 是**几列**被摘（3 → 5）。少了后者，「给一个资源摘第二列」是静默的。
    assert len(_SERVER_GENERATED_HIDDEN_COLUMNS) == 3, _SERVER_GENERATED_HIDDEN_COLUMNS
    assert sum(len(v) for v in _SERVER_GENERATED_HIDDEN_COLUMNS.values()) == 5
    assert sorted(
        f"{path.split('/')[-1]}.{column}"
        for path, columns in _SERVER_GENERATED_HIDDEN_COLUMNS.items()
        for column in columns
    ) == [
        "class-sessions.rpe_token",
        "students.password_bound_at",
        "students.password_hash",
        "teachers.password_bound_at",
        "teachers.password_hash",
    ]


def test_natural_key_is_a_real_unique_constraint_of_that_table():
    """``RESOURCES`` 的 20 个 ``natural_key`` 逐个等于该表**真实存在**的唯一约束。

    两侧不同源：被测侧是 ``catalog.py`` 的字面元组，期望侧是
    :func:`_unique_columns`（从 :data:`Base.metadata` 的 ``UniqueConstraint`` 读）。

    ⚠️ 这条守的是「自然键不是**发明**出来的」：``repo.upsert`` 拿它当幂等键，
    而一个不对应任何 DB 约束的键意味着「撞键时 DB 不会兜底」——
    两个并发 POST 会各插一行，而下一次 ``upsert`` 的 ``select`` 撞上
    ``MultipleResultsFound``，**炸在离真因很远的读侧**
    （:class:`app.db.models.feedback.ClassSession` 的 ``__table_args__`` 注释
    逐字描述过这个失效形态）。

    ⚠️ 反向也钉住：**恰好 3 张**资源表没有唯一约束（P3-B2），
    它们的 ``natural_key`` 必须是 ``None``。
    """
    with_key = 0
    for spec in RESOURCES:
        table = spec["model"].__table__
        expected = _unique_columns(table)
        assert spec["natural_key"] == expected, (
            spec["path"],
            spec["natural_key"],
            expected,
        )
        with_key += expected is not None
    assert with_key == 20
    assert len(RESOURCES) - with_key == 3

    resource_tables = [spec["model"].__table__ for spec in RESOURCES]
    assert sorted(t.name for t in resource_tables if _unique_columns(t) is None) == [
        "course_section",
        "fitness_test_batch",
        "notification",
    ]


def test_every_resource_list_omits_json_text_columns_and_read_one_includes_them(
    client, seeded, admin_headers
):
    """**P3-B3 的遍历守卫**：23 个资源逐个比对 list 与 read-one 的键集合。

    **三方对拍**，任一方抄漏都会红：

    ① 字面清单 :data:`_JSON_TEXT_COLUMNS`（19 个 / 8 张表，写死在本文件里）；
    ② 从 :data:`Base.metadata` 现场探测（``isinstance(c.type, JsonText)``，
      与 :func:`app.api.crud._json_text_columns` 是**两份**写法）；
    ③ **真的 HTTP 响应**：list 的 ``items[0]`` 与 read-one 的 body。

    ⚠️ **``seeded`` 是这条守卫不空转的全部理由**：空库上 ``items == []``，
    于是「list 里一个 ``JsonText`` 列都不出现」对 23 个资源**恒真**——
    一条恒真的守卫与一条真的守卫在颜色上无法区分（硬规矩 #50）。
    故每表都有一行、且每个 ``JsonText`` 列都填了非空值。

    ⚠️ 末尾 ``total == 19`` 是**跨资源**的合计，它把「某一张表的探测结果是空集」
    这种失效也一并抓住（否则 8 张表里漏一张，①②③ 会一起错得自洽）。

    ⚠️⚠️ **收尾小修波给本条加了第四方**：:data:`_SERVER_GENERATED_HIDDEN_COLUMNS`
    （Plan 03 收尾小修波时 1 格：``class_session.rpe_token``；Plan 05A Task 1 起 3 格，
    另两格是 ``student`` / ``teacher`` 的 ``password_hash``；
    **安全收紧波起 5 格**，再加 ``student`` / ``teacher`` 的 ``password_bound_at``）。
    加它的原因是**本条量到了派单没料到的
    一半**：泛型 list 端点**不走 ``response_model``**（它显式只 SELECT ``kept`` 那些列、
    手工拼 dict，理由逐字见 :func:`app.api.crud.build_crud_router` 里那个端点的
    docstring），故「把 ``rpe_token`` 从 ``ClassSessionRead`` 上摘掉」
    **只堵住了 read-one / POST / PATCH**，而 ``GET /api/class-sessions``
    ——**正是终审点名的那个 URL**——照旧原样返回全部口令。
    于是那一格在 :data:`app.api.routers.catalog.RESOURCES` 里**也**显式排掉了
    （``"list_exclude": ("rpe_token",)``，23 行里唯一一行），本条钉住它真的生效。
    ⚠️ 期望侧**不读** ``spec["list_exclude"]``（两侧同源的话，「忘了写那一行」
    会同时改掉两边、断言恒成立），而是「全部列 − ``JsonText`` 列 − 秘密列」。
    """
    running_total = 0
    tables_with_json = 0
    declares_list_exclude = 0
    for spec in RESOURCES:
        table = spec["model"].__table__
        detected = [c.name for c in table.columns if isinstance(c.type, JsonText)]
        assert detected == _JSON_TEXT_COLUMNS.get(table.name, []), table.name
        running_total += len(detected)
        tables_with_json += bool(detected)
        declares_list_exclude += "list_exclude" in spec

        # ⚠️ 安全收紧波：判据从 ``read_requires_staff`` 换成 ``read_scope is not None``
        #    （16 行要身份、7 行仍匿名），故只有那 16 行带头。
        #    ⚠️ **刻意不给 23 行一律带头**：
        #    本条量的是「list 与 read-one 的键集合」，与身份无关，而一律带头会让
        #    「闸门被挂到了全部 23 个资源上」这一档在本条里静默
        #    （它由 :func:`test_all_twenty_three_resources_are_listable` 的
        #    ``anonymous == 7`` 那一拍与本文件末尾那条三档守卫各钉一半）。
        #    ⚠️ 带**教职**头（而不是学生头）：教职那一档是全读，故 ``items[0]``
        #    一定在；带学生头的话 ``seeded`` 那一行的所有者未必是它，
        #    ``items`` 可能是空的（那会让本条空转全绿）。
        staff_headers = admin_headers if spec["read_scope"] is not None else None
        listing = client.get(spec["path"], headers=staff_headers).json()
        item = listing["items"][0]
        one = client.get(
            spec["path"] + "/" + str(seeded[table.name]), headers=staff_headers
        ).json()

        for column in detected:
            assert column not in item, (spec["path"], column)
            assert column in one, (spec["path"], column)
        # ⚠️ 秘密列**两个端点都不许出现**（``seeded`` 给 class_session 那一行填的是
        #    非空的 "ABC12345"，故这两拍不是空转）。
        #    ⚠️ 措辞自安全收紧波起不再说「匿名」：那 3 个资源的两个 GET 今天都要身份，
        #    而本拍钉的是**纵深防御的第二层**——「闸门哪天为别的理由放开时，
        #    凭据仍然不在响应体里」（那句话的住址是
        #    ``app/api/schemas/organisation.py`` 的 ``TeacherRead``）。
        for column in _SERVER_GENERATED_HIDDEN_COLUMNS.get(spec["path"], ()):
            assert column not in item, (spec["path"], column, "秘密列出现在 list 里")
            assert column not in one, (spec["path"], column, "秘密列出现在 read-one 里")
        hidden = set(_SERVER_GENERATED_HIDDEN_COLUMNS.get(spec["path"], ()))
        assert set(one) - set(item) == set(detected) - hidden, spec["path"]
        assert set(item) == {c.name for c in table.columns} - set(detected) - hidden, (
            spec["path"]
        )

    assert running_total == 19
    assert tables_with_json == 8
    # ⚠️ 「显式传 list_exclude 的行数」也钉住。**Plan 05A Task 1 把它从 1 抬到 3**
    #    （+ students 与 teachers，排的都是 ``password_hash``，理由逐字见
    #    :data:`_SERVER_GENERATED_HIDDEN_COLUMNS` 那两行的注释）。
    #    少了本行，「有人给第四个资源也排掉一列」是静默的——
    #    而上面那两拍只钉「秘密列不出现」，钉不住「非秘密列被误排掉」。
    assert declares_list_exclude == 3, declares_list_exclude


def test_child_tables_skips_the_foreign_keys_that_clear_themselves():
    """**P3-B4**：``_child_tables`` 找**入向**外键，且跳过 ``SET NULL`` / ``CASCADE``。

    两侧不同源：期望侧是就地扫 :data:`Base.metadata` 数**原始**入向外键
    （连 ``ondelete`` 一起打出来），被测侧是 :func:`app.api.crud._child_tables`。

    ⚠️ **不跳过会怎样**（这一条守的失效形态）：``notification.alert_id`` 与
    ``notification.prescription_id`` 都带 ``ON DELETE SET NULL``
    （Plan 03 Task 2 的顶回 3 加的），删父行时 **SQLite 自己置 NULL、不报 FK 违例**。
    于是不跳过的话 ``_child_tables(Alert)`` 会返回 ``[("notification", "alert_id")]``，
    ``DELETE /api/alerts/{id}`` 报「1 行 notification 仍指向它」——
    一句**假话**，而且它挡住的是一次本来能成功的删除。

    ⚠️ 而 ``alert`` / ``notification`` 的 ``on_delete`` 是 ``forbid``（P3-B8），
    故那个假 409 今天**打不出来**——本条因此是纯结构面的守卫。
    ``prescription`` 那一格才是**打得出来**的：它的 ``on_delete`` 是 ``restrict``，
    不跳过 ``notification`` 就会在有通知指向处方时报一个假 409。
    """
    assert len(Base.metadata.tables) == 30, "本条会在 metadata 没装满时空转全绿"

    def raw_inbound(table_name: str):
        target = Base.metadata.tables[table_name]
        return sorted(
            (other.name, fk.parent.name, fk.ondelete)
            for other in Base.metadata.tables.values()
            for fk in other.foreign_keys
            if fk.column.table is target
        )

    # --- 原始事实：这两个外键确实带 SET NULL --------------------------------
    assert raw_inbound("alert") == [("notification", "alert_id", "SET NULL")]
    assert raw_inbound("prescription") == [
        ("notification", "prescription_id", "SET NULL"),
        ("weekly_adjustment", "prescription_id", None),
    ]
    assert raw_inbound("class_session") == [("rpe_record", "class_session_id", None)]
    assert raw_inbound("notification") == []

    # --- 被测：带 SET NULL 的被跳过，ondelete 为 None 的一个都不许漏 ----------
    assert _child_tables(Alert) == []
    assert _child_tables(Notification) == []
    assert _child_tables(Prescription) == [("weekly_adjustment", "prescription_id")]
    assert _child_tables(ClassSession) == [("rpe_record", "class_session_id")]
    # Student 的 12 个入向外键 ondelete 全是 None，故一个都不能被跳过
    assert raw_inbound("student") == [
        (name, column, None) for name, column in _child_tables(Student)
    ]
    assert len(_child_tables(Student)) == 12

    # --- 全库今天没有一个外键带 DB 级 CASCADE --------------------------------
    # 故 _SELF_CLEARING_ONDELETE 里的 "CASCADE" 那一档是**许可而不是断言**
    # （硬规矩 #39：写清楚它今天守不住什么）。
    assert all(
        fk.ondelete != "CASCADE"
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
    )
    # ⚠️ 用集合相等而不是 sorted()：ondelete 的取值里含 None，
    # 而 None 与 str 之间没有 < 关系（sorted 会当场 TypeError）。
    assert {
        fk.ondelete for t in Base.metadata.tables.values() for fk in t.foreign_keys
    } == {None, "SET NULL"}


def test_a_conflict_message_names_the_key_columns_and_never_the_literal_none():
    """**P3-B5**：20 个有自然键的资源，409 的消息**含列名**、**不含字面 ``"None"``**。

    ⚠️ 23 个资源里有 **5 张表的唯一约束是无名的**（实测 ``UniqueConstraint.name is None``：
    ``semester.name`` / ``teacher.staff_no`` / ``student.student_no`` / ``exercise.ref`` /
    ``prescription_template.template_ref``）。把 ``uq.name`` 插进 f-string 会渲染成
    字面 ``"None"``，而那句话是要**显示给教师看**的。

    本条遍历全部 20 个（不只是那 5 个）：消息由同一个 :func:`_conflict_message` 生成，
    而它是**唯一**拼这句话的地方（单一所有者），故 20 个一起断言的成本与 5 个相同。
    ⚠️ 消息里也**不引提交上来的值**——值可能是 ``None``（``str(None) == "None"``）、
    也可能是自由文本（``weekly_adjustment.reason``）。

    HTTP 面那一半由批次 A 的 ``test_create_with_a_duplicate_natural_key_is_409`` 承担
    （它走的是真的 ``POST /api/semesters``，而 ``semester`` 正是那 5 张无名表之一）。
    """
    checked = 0
    unnamed: set[str] = set()
    for spec in RESOURCES:
        table = spec["model"].__table__
        key = _unique_columns(table)
        if key is None:
            continue
        checked += 1
        constraint = next(
            c for c in table.constraints if isinstance(c, UniqueConstraint)
        )
        if constraint.name is None:
            unnamed.add(table.name)
        message = _conflict_message(table.name, key)
        for column in key:
            assert column in message, (table.name, column, message)
        assert "None" not in message, (table.name, message)
        assert table.name in message
    assert checked == 20
    assert unnamed == {
        "semester",
        "teacher",
        "student",
        "exercise",
        "prescription_template",
    }


def test_a_resource_without_a_natural_key_never_returns_409(
    client, seeded, admin_headers
):
    """**P3-B2 的反向守卫**：没有自然键的资源，POST **结构上不可能**撞键。

    为什么要有这一条：``test_create_with_a_duplicate_natural_key_is_409`` 只覆盖了
    20 个有自然键的资源，而下一个人很容易把「409」当成 POST 的普适行为——
    于是他会给 ``course_section`` 写一条永远红的撞键测试，或者更糟：
    给那张表**加一条唯一约束**来让测试变绿（那是改 schema，本仓不做迁移）。

    ⚠️ **三个无自然键的资源里只有两个能走 HTTP 面**：
    ``notifications`` 是只读的（``writable=False``），POST 根本不注册 → **405**，
    故「无自然键 → 无 409」在它身上只能从 ``RESOURCES`` 的结构面断言。
    这个不对称是刻意的、写在这里，免得下一个人以为漏测了一个。
    """
    assert sorted(s["path"] for s in RESOURCES if s["natural_key"] is None) == [
        "/api/course-sections",
        "/api/fitness-test-batches",
        "/api/notifications",
    ]

    for path, payload in (
        (
            "/api/course-sections",
            {
                "semester_id": seeded["semester"],
                "teacher_id": seeded["teacher"],
                "name": "体育(1)班",
                "schedule_text": "周三 3-4 节",
                "grouping_mode": "administrative",
            },
        ),
        (
            "/api/fitness-test-batches",
            {
                "semester_id": seeded["semester"],
                "timepoint": "week1",
                "test_date": "2025-09-08",
                "source": "lepao",
                "academic_year": "2025-2026",
            },
        ),
    ):
        first = client.post(path, json=payload, headers=admin_headers)
        second = client.post(path, json=payload, headers=admin_headers)
        assert (first.status_code, second.status_code) == (201, 201), (
            path,
            first.text,
            second.text,
        )
        assert first.json()["id"] != second.json()["id"], path
        assert client.get(path).json()["total"] == 3, path  # seeded 1 行 + 这两行

    # ⚠️ 这一发**刻意不带** ``admin_headers``：``notifications`` 是 ``writable=False``，
    #    泛型工厂根本不注册它的 POST，故 405 由 Starlette 的路由匹配给出、
    #    **先于**任何身份判定（带上头也仍是 405）。
    assert client.post("/api/notifications", json={}).status_code == 405


def test_on_delete_restrict_names_the_blocking_child_table(
    client, seeded, admin_headers
):
    """``restrict`` 有子行 → **409**，消息点名**子表、那一列、几行**。

    「点名是哪张子表挡住的」是计划 Review Focus 第 4 条的落点：一句
    「删不掉」让教师无从下手，而「1 行 course_section 仍指向它」告诉他先去处理那个班。

    **红绿两档**：``seeded`` 的那个教师有一个 ``course_section`` 子行 → 409；
    现场新建、没有子行的教师 → 204。少了后一半，一个「一律 409」的实现也能全绿。
    """
    blocked = client.delete(
        "/api/teachers/" + str(seeded["teacher"]), headers=admin_headers
    )
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["error"]["code"] == "integrity_conflict"
    message = body["error"]["message"]
    assert "course_section" in message
    assert "teacher_id" in message
    assert "1 行" in message
    # 被挡住的那一行还在（409 不是「删了但报了个错」）
    assert client.get(
        "/api/teachers/" + str(seeded["teacher"]), headers=admin_headers
    ).status_code == 200

    fresh = client.post(
        "/api/teachers", json={"staff_no": "T2025077", "name": "王老师"},
        headers=admin_headers,
    )
    assert fresh.status_code == 201, fresh.text
    allowed = client.delete(
        "/api/teachers/" + str(fresh.json()["id"]), headers=admin_headers
    )
    assert allowed.status_code == 204, allowed.text


def test_on_delete_cascade_deletes_children_first(client, engine, seeded, admin_headers):
    """``cascade`` 的**子表先删**（P7-A4 的同一条纪律），且真的删干净了。

    **红绿对照**分两半：

    ① 工厂的 DELETE 端点对「有一个 ``rpe_record`` 子行」的课次返回 **204**、
      两张表都归零。若实现是「先删父表」，``PRAGMA foreign_keys=ON``
      会当场 ``FOREIGN KEY constraint failed``，经 :mod:`app.api.errors` 折成
      **409**（``IntegrityError``）而不是 204。
    ② **反证**：同一形状下用裸 SQL **不先删子表**去删父表，确实抛
      ``IntegrityError``。少了②，「那两张表本来就空」也能让①绿。
    """

    def _counts() -> tuple[int, int]:
        with Session(engine) as session:
            return (
                session.scalar(select(func.count()).select_from(ClassSession)),
                session.scalar(select(func.count()).select_from(RpeRecord)),
            )

    assert _counts() == (1, 1)
    got = client.delete(
        "/api/class-sessions/" + str(seeded["class_session"]), headers=admin_headers
    )
    assert got.status_code == 204, got.text
    assert _counts() == (0, 0)

    # --- ② 反证：另建一节带快评的课，用裸 SQL 删父表 -------------------------
    created = client.post(
        "/api/class-sessions",
        json={
            "course_section_id": seeded["course_section"],
            "session_date": "2025-09-17",
            "period": 3,
            "rpe_opened": True,
            # ⚠️ 此处此前还有 ``"rpe_token": "ZZZ99999"``，自 I4 之后那一格
            #    **不在** ``ClassSessionCreate`` 上了（服务端填，见
            #    :data:`_SERVER_FILLED_COLUMNS`），留着会被 Pydantic 静默丢掉、
            #    于是本行看起来像是在写它而其实没有。口令要写请走
            #    ``POST /api/class-sessions/{id}/open-rpe``。
            "batch_id": seeded["daily_sync_run"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    other = created.json()["id"]
    with Session(engine) as session:
        session.add(
            RpeRecord(
                class_session_id=other,
                student_id=seeded["student"],
                rpe=6,
                submitted_at=T(2025, 9, 17, 10, 35),
                elapsed_seconds=None,
            )
        )
        session.commit()
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            session.execute(
                delete(ClassSession.__table__).where(ClassSession.__table__.c.id == other)
            )
            session.commit()
    # 而工厂的 cascade 对同一行是 204
    assert client.delete(
        "/api/class-sessions/" + str(other), headers=admin_headers
    ).status_code == 204
    assert _counts() == (0, 0)


def test_the_scope_hook_rejects_a_mismatched_identity_with_403(app, engine, client, seeded):
    """``scope`` 钩子：身份与行的所有者不匹配 → **403**；且它是**可选**的。

    ⚠️ ``scope`` 在今天 23 行 ``RESOURCES`` 里**恒为 ``None``**（本波收紧的
    ``read_scope="student_self"`` 那一档**刻意不复用**这个钩子：``ScopeFn`` 的签名是
    「拿到一个 ORM 行 + 两个 ``| None`` 的身份」，而 list 要的是**过滤**、
    且本波要的是「匿名 401」而不是「缺头也算过」，两者不是一件事），
    故它是「有能力、无生产调用方」的一档。
    本条用一个**合成的** ``ScopeFn`` 把它跑通，于是它不是死代码——
    同时钉住三件下一个人会踩的事：

    ① 挂了钩子的路由会拒（403，含「没带头」那一档）；
    ② **没挂**钩子、且 ``read_scope is None`` 的路由不要求身份
      （同一个 ``training_log`` 行、同一个模型、同一个工厂，
      差别**只有**那个钩子）——否则「一律 403」也能让①绿；
      ⚠️⚠️ **本拍此前拿目录里的 ``/api/training-logs/{id}`` 当「不要求身份」的例子，
      而那个前提自安全收紧波起已经假了**（那一行今天是
      ``read_scope="student_self"``，匿名实测 **401**）。故本拍改成再建一个
      **合成的**匿名路由：这样「同一个模型、同一个行、只差一个钩子」这个对比
      仍然是干净的，而不必去目录里找一个恰好匿名、又恰好用同一张表的资源
      （23 行里没有这样的资源）。
    ③ 那两个身份请求头**只出现在要身份的路由上**（OpenAPI 面）。
      这一格是「无条件注册依赖」那个偷懒写法的直接后果：
      23 × 3 个端点会凭空多出两个头，而 Plan 04 的前端会以为每个 CRUD 都要传身份。
      ⚠️⚠️ **安全收紧波把「要身份的路由」从 1 个（本条那个合成探针）抬到 27 个**
      （+ 13 个 ``student_self`` 资源 × 2 个 GET）——那些端点上出现这两个头是
      **对的**（:func:`app.api.deps.current_reader` 就是靠它们回落的），
      故本拍的判据从「只有探针有」改成「**7 个匿名参考数据资源一个都没有**」。
      ⚠️ 而 :func:`app.api.crud.build_crud_router` 里那两个 ``list_rows`` /
      ``read_one`` 分支存在的全部理由就是这一格：``Depends(current_reader)``
      必须作为端点形参（端点要它的值），而形参会进 OpenAPI，
      无条件挂上去的话那 7 个匿名资源会凭空多出两个请求头。

    ⚠️ 探针路径也必须挂在 ``/api/`` 下：工厂体里有一道
    ``path.startswith("/api/")`` 的校验（``test_the_factory_rejects_a_bad_configuration``
    钉住它有牙），故本条用 ``/api/probe-training-logs`` 而不是 ``/probe/…``。
    它不会与目录里的 ``/api/training-logs`` 撞车——两个串不同。
    """
    from app.api.schemas.feedback import TrainingLogRead

    def _owner_only(session: Session, row, student_id, staff_no) -> None:
        require_scope(session, row.student_id, student_id)

    app.include_router(
        build_crud_router(
            model=TrainingLog,
            schemas=CrudSchemas(TrainingLogRead),
            path="/api/probe-training-logs",
            tags=["probe"],
            writable=False,
            on_delete=ON_DELETE_RESTRICT,
            natural_key=("student_id", "log_date"),
            scope=_owner_only,
        )
    )
    # ② 那一半：**同一个模型、同一行**，差别只有「没挂钩子」+ ``read_scope=None``。
    app.include_router(
        build_crud_router(
            model=TrainingLog,
            schemas=CrudSchemas(TrainingLogRead),
            path="/api/probe-anon-training-logs",
            tags=["probe"],
            writable=False,
            on_delete=ON_DELETE_RESTRICT,
            natural_key=("student_id", "log_date"),
            read_scope=None,
        )
    )
    pk = str(seeded["training_log"])
    owner = str(seeded["student"])

    own = client.get("/api/probe-training-logs/" + pk, headers={"X-Student-Id": owner})
    assert own.status_code == 200, own.text

    stranger = client.get(
        "/api/probe-training-logs/" + pk, headers={"X-Student-Id": "999999"}
    )
    assert stranger.status_code == 403, stranger.text
    assert stranger.json()["error"]["code"] == "forbidden"

    assert client.get("/api/probe-training-logs/" + pk).status_code == 403

    # ② 没挂钩子的那一个：匿名 200（同一行、同一个模型）
    assert client.get("/api/probe-anon-training-logs/" + pk).status_code == 200
    # ⚠️ 而目录里那个 ``/api/training-logs`` 今天**要身份**（安全收紧波），
    #    三档由 :func:`test_the_student_keyed_resources_admit_four_read_tiers` 钉，
    #    本处只钉「匿名确实是 401」，于是「②那个合成路由的 200 不是因为全仓都匿名」
    #    这件事在本条内部就自证了。
    assert client.get("/api/training-logs/" + pk).status_code == 401

    paths = client.get("/openapi.json").json()["paths"]

    def _parameter_names(key: str) -> set[str]:
        return {
            p["name"].replace("-", "_").lower() for p in paths[key]["get"]["parameters"]
        }

    assert {"x_student_id", "x_teacher_staff_no"} <= _parameter_names(
        "/api/probe-training-logs/{probe_training_log_id}"
    )
    # ③ 反假绿：**没挂钩子、也不要身份**的那个合成路由上，两个头一个都不出现。
    assert _parameter_names(
        "/api/probe-anon-training-logs/{probe_anon_training_log_id}"
    ) == {"probe_anon_training_log_id"}
    # ③ 而 7 个**匿名参考数据资源**的成员 GET 上也一个都不出现（``read_scope is None``
    #    ⇒ 走的是工厂里那个不带 ``reader`` 形参的分支）。
    anonymous_detail_gets = 0
    for spec in RESOURCES:
        if spec["read_scope"] is not None:
            continue
        segments = len(spec["path"].split("/"))
        found = [
            key for key in paths
            if key.startswith(spec["path"] + "/{")
            and len(key.split("/")) == segments + 1
        ]
        assert len(found) == 1, (spec["path"], found)
        names = _parameter_names(found[0])
        assert "x_student_id" not in names, (spec["path"], names)
        assert "x_teacher_staff_no" not in names, (spec["path"], names)
        anonymous_detail_gets += 1
    assert anonymous_detail_gets == 7, anonymous_detail_gets


def test_a_value_outside_the_model_domain_is_422_not_409(client, seeded, admin_headers):
    """三处枚举列送一个域外值 → **422**（请求校验），而不是 DB 的 CHECK → **409**。

    为什么值得一条：``student.sex`` / ``course_section.grouping_mode`` /
    ``fitness_test_batch.timepoint`` 在 DB 侧都有 ``CheckConstraint``，
    但那是**写库时**才响的，响的方式是 ``IntegrityError`` → 409 ``integrity_conflict``。
    前端表单填错一个下拉框会收到「与别人撞了」，于是它会去查「谁跟我重复」——
    而真正的问题是它自己送了一个不存在的值。

    ⚠️ **取值域的唯一所有者仍是模型类常量**（``Student.SEXES`` 一类）：
    schema 侧的校验器把那个集合**传**给 :func:`app.api.schemas._base.one_of`，
    不自己声明第二份词表。故末尾三行断言的是「那个集合还是原来那个」，
    而不是「schema 里的词表对不对」——后者不存在。
    """
    assert sorted(Student.SEXES) == ["female", "male"]
    assert sorted(CourseSection.GROUPING_MODES) == ["administrative", "stratified"]
    assert sorted(FitnessTestBatch.TIMEPOINTS) == ["week1", "week16", "week8"]

    # ⚠️⚠️ 三发都**必须带** ``admin_headers``：``_require_admin_identity`` 是一个
    #    依赖，而依赖跑在请求体校验**之前**（实测：不带头时 ``POST /api/students`` 送
    #    一个空 body 得到的是 **401** 而不是 422）。少了这个头，本条会红在
    #    「422 != 401」上，而那与「枚举列的取值域校验」毫无关系。
    bad = client.post(
        "/api/students",
        json={**STUDENT_PAYLOAD, "student_no": "S2025002", "sex": "unknown"},
        headers=admin_headers,
    )
    assert bad.status_code == 422, bad.text
    body = bad.json()
    assert body["error"]["code"] == "request_validation_failed"
    detail = str(body["error"]["detail"])
    assert "sex" in detail
    assert "female" in detail, "消息里没有取值域，前端无从提示用户"
    assert "None" not in body["error"]["message"]

    good = client.post(
        "/api/students",
        json={**STUDENT_PAYLOAD, "student_no": "S2025003", "sex": "female"},
        headers=admin_headers,
    )
    assert good.status_code == 201, good.text

    patched = client.patch(
        "/api/course-sections/" + str(seeded["course_section"]),
        json={"grouping_mode": "nope"},
        headers=admin_headers,
    )
    assert patched.status_code == 422, patched.text
    # 那一行没被改坏
    assert (
        client.get("/api/course-sections/" + str(seeded["course_section"]))
        .json()["grouping_mode"]
        == "administrative"
    )


def test_every_table_has_a_single_column_primary_key():
    """:func:`app.api.crud._purge_where` 的**前提**：29 张表的主键都是单列 ``id``。

    那个函数用 ``next(iter(table.primary_key.columns))`` 取主键列，
    复合主键会让它**静默只按第一列删**（删多了，而且不报错）——
    正是「一个假设没人看着」的形状。故把假设写成守卫。

    ⚠️ 它也顺带是 :func:`app.api.crud.build_crud_router` 的 ``pk: str = "id"``
    那个缺省值的前提：路径参数标注成 ``int``，而 29 张表里**除 ``user_session`` 外**
    的主键都是 INTEGER。
    ⚠️ **Plan 05A Task 1 之后本条有一个例外**（实现者实测，此前 25 张表没有例外）：
    ``user_session.id`` 是 ``String(64)``（一个 ``secrets.token_urlsafe`` 出来的不透明串，
    理由逐字见 ``app/db/models/auth.py`` 的 ``UserSession`` docstring）。
    ⚠️ **它不动摇 :func:`app.api.crud._purge_where`**：那个函数只在 ``on_delete="cascade"``
    那一档被调用，而 ``user_session`` 不是 23 个 CRUD 资源之一（它没有 list/create 端点），
    故它的主键类型**永远不会**被 ``_purge_where`` 读到。本条断言的是「单列 + 名叫 ``id``」，
    两格对 ``user_session`` 都成立；「主键是整数」这半句因此由下面那格显式例外化，
    而不是让本条静默变成一句假话（硬规矩 #39）。
    """
    assert len(Base.metadata.tables) == 30
    offenders = [
        (table.name, [c.name for c in table.primary_key.columns])
        for table in Base.metadata.tables.values()
        if len(table.primary_key.columns) != 1
    ]
    assert offenders == []
    assert {
        next(iter(table.primary_key.columns)).name
        for table in Base.metadata.tables.values()
    } == {"id"}
    # 整数主键那一格：29 张里恰好 1 张不是（user_session.id 是 String(64)；
    # ⚠️ Plan 06 Task 3 的 login_attempt.id 是 Integer，故那个例外**没有**变成两个）。
    from sqlalchemy import Integer as _Integer

    non_integer = sorted(
        table.name
        for table in Base.metadata.tables.values()
        if not isinstance(next(iter(table.primary_key.columns)).type, _Integer)
    )
    assert non_integer == ["user_session"], non_integer


# ---------------------------------------------------------------------------
# 批次 C：两个「有能力、无生产调用方」的工厂参数（硬规矩 #39）
# ---------------------------------------------------------------------------


def test_readable_false_turns_off_both_get_endpoints(app, client):
    """``readable=False`` 关掉**两个** GET；写的那几个照注册。

    ⚠️ 这是「**有能力、无生产调用方**」的一档（硬规矩 #39）：23 行 ``RESOURCES``
    没有一个写 ``readable=False``——23 个资源全都可读，而「只写不读」的资源在
    一个管理型原型里没有意义。参数留着是因为计划的 Interfaces 逐字列了它，
    而本条让它**不是死代码**：它钉住的是「关掉的是 list 与 read-one 两个端点、
    不是只关一个」，以及「关掉读**不会**顺手关掉写」。

    **绿档**是末尾那一行：目录里的 ``/api/semesters``（``readable=True``）两个 GET
    都是 200，故「一律 405」的实现过不了本条。

    ⚠️ 探针挂在 ``/api/probe-write-only-semesters``：工厂有一道
    ``path.startswith("/api/")`` 校验，且它写的是**同一张** ``semester`` 表
    （``client`` 夹具是空库，故与目录路由互不干扰）。
    """
    app.include_router(
        build_crud_router(
            model=Semester,
            schemas=CrudSchemas(SemesterRead, SemesterCreate, SemesterUpdate),
            path="/api/probe-write-only-semesters",
            tags=["probe"],
            writable=True,
            on_delete=ON_DELETE_FORBID,
            natural_key=("name",),
            readable=False,
        )
    )
    assert client.get("/api/probe-write-only-semesters").status_code == 405
    assert client.get("/api/probe-write-only-semesters/1").status_code == 405

    created = client.post(
        "/api/probe-write-only-semesters",
        json={**SEMESTER_PAYLOAD, "name": "只写不读的学期"},
    )
    assert created.status_code == 201, created.text
    new_id = str(created.json()["id"])
    patched = client.patch(
        "/api/probe-write-only-semesters/" + new_id, json={"weeks": 20}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["weeks"] == 20, "PATCH 的响应体是 read 模型，readable 管不到它"
    # on_delete="forbid" 与 readable=False 是两个独立开关：DELETE 仍是 405
    assert client.delete("/api/probe-write-only-semesters/" + new_id).status_code == 405

    assert client.get("/api/semesters").status_code == 200


def test_an_explicit_list_exclude_overrides_the_auto_detection(app, client):
    """``list_exclude`` 显式传元组时**覆盖**自动探测（P3-B3 保留的那个例外口子）。

    ⚠️ **本处此前印的是「23 行 ``RESOURCES`` 没有一行用它（实测 ``'list_exclude' in spec``
    的行数是 0），故它是『许可而不是断言』的一档」**，那句自 Plan 03 收尾小修波起
    已经过期（按实际改写）：``/api/class-sessions`` 那一行现在显式传
    ``("rpe_token",)``，而理由是**秘密列**（``rpe_token`` 是「学生提交课堂快评的
    唯一闸门」，而 list 端点不走 ``response_model``，故只在读模型上摘掉它堵不住 list），
    **不是** P3-B3 原本设想的「list 确实要返回某个小 JSON 列」。
    ⚠️ 那一行由
    :func:`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
    钉（含「恰好 1 行显式声明」那一拍）。**本条钉的是另一件事**：显式元组
    **覆盖**自动探测、且**不影响 read-one**——今天没有生产调用方走这一档，
    故本条用合成资源跑通它，使那个覆盖分支不是死代码。

    **选 ``semester`` 是刻意的**：那张表**一个 ``JsonText`` 列都没有**，
    故自动探测的结果是**空元组**——于是「``weeks`` 从 list 里消失了」这件事
    **只能**来自显式覆盖，不可能是探测的功劳。挑一张有 JSON 列的表来测就分不清了。
    """
    app.include_router(
        build_crud_router(
            model=Semester,
            schemas=CrudSchemas(SemesterRead, SemesterCreate, SemesterUpdate),
            path="/api/probe-excluded-semesters",
            tags=["probe"],
            writable=True,
            on_delete=ON_DELETE_FORBID,
            natural_key=("name",),
            list_exclude=("weeks",),
        )
    )
    # 自动探测在 semester 上确实是空集（本条的前提，不是被测对象）
    assert _json_text_columns(Semester) == ()

    created = client.post("/api/probe-excluded-semesters", json=SEMESTER_PAYLOAD)
    assert created.status_code == 201, created.text
    item = client.get("/api/probe-excluded-semesters").json()["items"][0]
    assert "weeks" not in item
    assert "name" in item, "覆盖把不该排除的列也排掉了"

    one = client.get("/api/probe-excluded-semesters/" + str(created.json()["id"])).json()
    assert one["weeks"] == 16, "read-one 不该受 list_exclude 影响"
    assert set(one) - set(item) == {"weeks"}



# ===========================================================================
# Plan 05A Task 5：那 4 个名册读（``students`` / ``teachers`` × 集合/成员）
# ===========================================================================
#: **字面清单**（硬规矩 #35）：哪两个资源的读要教职身份。
#: ⚠️ 刻意**不从** :data:`app.api.routers.catalog.RESOURCES` 反推：两侧同源的话，
#: 「把某一行的 ``read_requires_staff`` 删掉」会同时改掉两边、断言恒成立。
_ROSTER_PATHS = ("/api/students", "/api/teachers")


def test_every_resource_declares_read_scope_explicitly():
    """``RESOURCES`` 的 **23 行一律字面写出** ``"read_scope"`` 这个键（写 ``None`` 也要写）。

    ⚠️ **判据是「键在不在」而不是「值是什么」**（与 ``on_delete`` / ``require_admin`` /
    Plan 05A 那个 ``read_requires_staff`` 三条同一条口径）：
    :func:`app.api.crud.build_crud_router` 的 ``read_scope`` **有缺省值 ``None``**，
    故「忘了写」与「写了 ``None``」在行为上无法区分——而失效方向是
    **静默地退回匿名可读**（= 把一整套以 ``student_id`` 为键的健康档案摊给任何调用方），
    那正是安全收紧波要消灭的失效形态。

    ⚠️ 本条**替代**了 Plan 05A Task 5 的
    ``test_exactly_two_resources_declare_read_requires_staff``（那个布尔开关
    在本波被 ``read_scope`` 替代，两条并存就是两个所有者）。
    ⚠️ 而「恰好几行是哪一档」由
    :func:`test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two` 钉：
    本条只管**键在不在**，那一条管**值的分布**。两条各钉一半——
    只有本条的话「把 23 行全改成 ``None``」是绿的；
    只有那一条的话「删掉某一行的键、让它落回缺省值 ``None``」
    在那一行恰好属于匿名那 7 个时也是绿的。
    """
    missing = [spec["path"] for spec in RESOURCES if "read_scope" not in spec]
    assert missing == [], missing
    assert len(RESOURCES) == 23
    for spec in RESOURCES:
        assert spec["read_scope"] is None or spec["read_scope"] in READ_SCOPE_VALUES, (
            spec["path"], spec["read_scope"]
        )
        # ⚠️ 反向也钉：``student_owner`` **只在**按学生键收窄的那**两档**出现
        #    （``student_self`` / ``staff_taught``；⚠️ Plan 06 Task 8 之前这里逐字是
        #    ``== READ_SCOPE_STUDENT_SELF``，第四档一加进去它就会对 13 行视而不见）。
        #    少了本行，「给一个匿名资源写了 ``student_owner``」要等到工厂第 10 道校验
        #    在导入期响才知道，而那条校验本身也得有人钉住它真的被触发过
        #    （:func:`test_the_factory_rejects_a_bad_configuration`）。
        assert ("student_owner" in spec) == (
            spec["read_scope"] in STUDENT_SCOPED_READ_VALUES
        ), spec["path"]


def test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two():
    """五档的**行数与名单**逐字钉住：
    **7 匿名 / 0 学生自读 / 13 任教范围（学生键）/ 1 任教范围（班级键）/ 2 仅教职**。

    ⚠️ 期望侧**字面写死**（硬规矩 #35），不从 :data:`RESOURCES` 反推：
    两侧同源的话，「把某一行的 ``read_scope`` 改成 ``None``」会同时改掉两边、
    断言恒成立。⚠️ 而这份名单的**散文版**住在
    :mod:`app.api.routers.catalog` 的模块 docstring（那张五档表）——
    两处刻意不合并：一处是人读的口径、一处是机器钉的契约，
    而「加第 24 个资源」必须**同时**改两处，那正是本条存在的理由。

    ⚠️⚠️ **函数名自 Plan 06 Task 8b 起是五个数字**
    （``seven_zero_thirteen_one_and_two``；Task 8 那一次是四个
    ``seven_zero_thirteen_and_three``）：本波把 ``weekly-class-reports`` 从
    ``"staff"`` 那一档挪进了新的**第五档**
    :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT_SECTION`（Task 8 顶回 2 的落点），
    于是 ``3 仅教职`` 变成 ``1 班级键 + 2 仅教职``。⚠️ **改名要同步全部引用**
    （硬规矩 #66）：本仓活文档里的引用共 4 处，已一并更新，逐字清单见实现者报告。
    ⚠️⚠️ 而 ``student_self`` 那一档今天**0 行**（安全收紧波立的：13 行全部改成了
    ``staff_taught``，用户裁定「教师账号之间要有数据隔离」），**刻意不删**
    （保留它的理由逐字见 :data:`app.api.crud.READ_SCOPE_STUDENT_SELF` 的注释），
    故本条把「0 行」也钉住：它挡的是「有人悄悄把某一行改回 ``student_self``」——
    那一改会让那个资源对**任何**在册教职重新变成全校全读，
    而失效方向是**静默地多给数据**。
    ⚠️ 而「0 行的那一档不是死代码」由
    :func:`test_the_student_self_tier_still_behaves_as_staff_full_read` 用合成资源钉住。

    ⚠️ 五档各自挡一个失效方向：

    * **7 匿名**：挡「收得太宽」。这 7 个是参考数据与班级/批次级数据，
      大屏与登录前的页面要用；把它们也收进去会让 ``/login`` 之前的页面全 401。
    * **0 学生键（教职全读）**：见上面那段——挡「悄悄退回去」。
    * **13 任教范围（学生键）**：挡「收得太窄」。终审 I6 点名的那一批
      （体成分 / 体测 / 派生 / 分层 / 处方 / 打卡 / RPE / 小测 / 预警 / 问卷 /
      选课），**外加**安全收紧波实测查出来的 2 个非直接键：
      ``notifications``（多态键 ``recipient_id`` + ``recipient_kind``）与
      ``weekly-adjustments``（间接键 ``prescription_id`` → ``prescription.student_id``）。
      ⚠️ 而「13」这个数字挡住的是「收得太宽」：把其中一行挪到 ``staff`` 那一档
      就等于「任何在册教师全校全读」。
    * **1 任教范围（班级键）**：``weekly-class-reports``。⚠️ 本波新钉的一档，
      而「1」这个数字挡的是**两个反方向**：把它挪回 ``staff`` = 任何在册教师
      读得到别的班那份 ``progress_board``（= Task 8 顶回 2 的那一格跨教师泄漏复活）；
      把它挪进第四档 = 工厂第 12 道校验当场抛（第四档要 ``student_owner``、
      第五档要 ``section_column``，两格互斥）。逐字取证住在
      :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches`。
    * **2 仅教职**：``students`` / ``teachers``（Plan 05A Task 5 的两份名册，
      各含绑定口令的全部验身材料）。⚠️ 本波之前这一档是 3 行——
      第三行 ``weekly-class-reports`` 挪走了，理由见上一格。
    """
    by_tier: dict[object, list[str]] = {
        None: [],
        READ_SCOPE_STUDENT_SELF: [],
        READ_SCOPE_STAFF_TAUGHT: [],
        READ_SCOPE_STAFF_TAUGHT_SECTION: [],
        READ_SCOPE_STAFF: [],
    }
    for spec in RESOURCES:
        by_tier[spec["read_scope"]].append(spec["path"])
    assert sorted(by_tier[None]) == [
        "/api/class-sessions",
        "/api/course-sections",
        "/api/exercises",
        "/api/fitness-test-batches",
        "/api/percentile-snapshots",
        "/api/prescription-templates",
        "/api/semesters",
    ], by_tier[None]
    assert by_tier[READ_SCOPE_STUDENT_SELF] == [], by_tier[READ_SCOPE_STUDENT_SELF]
    assert sorted(by_tier[READ_SCOPE_STAFF_TAUGHT]) == [
        "/api/alerts",
        "/api/body-compositions",
        "/api/derived-metrics",
        "/api/enrollments",
        "/api/fitness-test-results",
        "/api/interest-surveys",
        "/api/mini-tests",
        "/api/notifications",
        "/api/prescriptions",
        "/api/rpe-records",
        "/api/stratification-results",
        "/api/training-logs",
        "/api/weekly-adjustments",
    ], by_tier[READ_SCOPE_STAFF_TAUGHT]
    assert sorted(by_tier[READ_SCOPE_STAFF_TAUGHT_SECTION]) == [
        "/api/weekly-class-reports",
    ], by_tier[READ_SCOPE_STAFF_TAUGHT_SECTION]
    assert sorted(by_tier[READ_SCOPE_STAFF]) == [
        "/api/students",
        "/api/teachers",
    ], by_tier[READ_SCOPE_STAFF]
    assert (
        len(by_tier[None]),
        len(by_tier[READ_SCOPE_STUDENT_SELF]),
        len(by_tier[READ_SCOPE_STAFF_TAUGHT]),
        len(by_tier[READ_SCOPE_STAFF_TAUGHT_SECTION]),
        len(by_tier[READ_SCOPE_STAFF]),
    ) == (7, 0, 13, 1, 2)


def test_every_student_keyed_resource_declares_a_student_scoped_read_scope():
    """**遍历型守卫**（派单 §2 逐字要求的那一条；Plan 06 Task 8 同步到第四档）：
    凡是**含 ``student_id`` 列**的资源，都声明了
    :data:`app.api.crud.STUDENT_SCOPED_READ_VALUES` 里的一档
    （``student_self`` / ``staff_taught``）。

    ⚠️ 它挡的是「下一个人加第 24 个资源、那张表带 ``student_id``、而他忘了声明」——
    那次遗漏在 :func:`test_every_resource_declares_read_scope_explicitly` 里也会红
    （键不在），但**报错指向的是「键不在」而不是「这张表有学生键」**，
    而下一个人看到前者会以为「补一个 ``None`` 就行」。本条把「为什么不能是 ``None``」
    写进报错里。

    ⚠️⚠️ **本波把判据从「非 ``None``」收紧成「是那两档之一」**（派单 §0 逐字点名的
    「该遍历守卫要同步」）：改前它写的是 ``spec["read_scope"] is not None``，
    于是「把一张学生键表声明成 ``staff``」是**绿的**——而那一档是
    「任何在册教职全校全读」，正是本波要消灭的失效形态（一个教师读全校 60 人的
    健康档案）。⚠️ 而它对 ``weekly-class-reports`` 那一行**不适用**：
    那张表身上没有 ``student_id`` 列（``student_id`` 埋在 ``progress_board``
    那个 JSON 列**里面**），故它不在本谓词里——那一行的跨教师泄漏是
    **另一格**已知局限，逐字取证与顶回住在 :data:`RESOURCES` 那一行的注释里。

    ⚠️ **两侧不同源**：期望侧就地扫 ``spec["model"].__table__.columns``
    （SQLAlchemy 的元数据），被测侧是 :data:`RESOURCES` 的字面声明。

    ⚠️⚠️ **它只覆盖 11 行**（含 ``student_id`` 列的那 11 个资源）。
    另 2 个学生键资源**故意**不在这个谓词里，而这是本条的已知边界：

    * ``notification`` 的学生键是 ``recipient_id``（多态，靠 ``recipient_kind`` 分档），
      它身上**没有** ``student_id`` 列——派单 §2 逐字警告过「不要靠
      『字段里有 ``student_id`` 就自动收紧』的推断」，而这一行就是那个警告的实证；
    * ``weekly_adjustment`` 的学生键要经 ``prescription_id`` 一跳才到。

    两者由 :func:`test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two`
    的字面名单钉住（13 行里点名了它们）。⚠️ 于是「一个**新的**多态/间接学生键资源
    被加成匿名」这件事**仍然只能靠人**——如实记为已知局限（硬规矩 #39），
    并已登记为待清扫：要机器化就得给 ``StudentOwner`` 加一条
    「反向遍历全部外键、看能不能一跳到达 ``student``」的探测，
    而那正是派单点名不要的「推断」。
    """
    keyed = 0
    for spec in RESOURCES:
        table = spec["model"].__table__
        if "student_id" not in {c.name for c in table.columns}:
            continue
        keyed += 1
        assert spec["read_scope"] in STUDENT_SCOPED_READ_VALUES, (
            f"{spec['path']}（表 {table.name}）含 student_id 列，"
            f"却把 read_scope 声明成 {spec['read_scope']!r}：那等于把这一整张以 "
            f"student.id 为键的表摊给任何匿名调用方（终审 I6），"
            f"或者摊给任何在册教职（Plan 06 Task 8 收的那一半）。"
            f"要它真的匿名/全校，请改成不含学生键的形状，"
            f"而不是把这一格写成 None 或 'staff'。"
        )
    #: ⚠️ **11 而不是 13**：那 2 个非直接键的资源不在这个谓词里，
    #: 理由逐字见上面 docstring 末段。
    assert keyed == 11, keyed
    #: ⚠️ 反向也钉一遍：``staff_taught`` 那一档的 13 行里，
    #: **恰好 11 行**的 ``StudentOwner.column`` 是 ``student_id``，
    #: 另 2 行是 ``prescription_id`` / ``recipient_id``。
    #: 少了本行，「有人把 ``notifications`` 的 owner 改回缺省的 ``student_id``」
    #: 会响在**导入期**（工厂第 11 道校验：那一列不在 ``notification`` 上），
    #: 报错离「谁改的、为什么改」有一层；本行把它变成一句指名道姓的契约。
    #: ⚠️ 判据写 ``in STUDENT_SCOPED_READ_VALUES`` 而不是 ``== STAFF_TAUGHT``：
    #: 它要钉的是「**任何**按学生键收窄的行都显式声明了键在哪一列」，
    #: 而 ``student_self`` 那一档今天 0 行、明天可能不是。
    direct = [
        spec["path"] for spec in RESOURCES
        if spec["read_scope"] in STUDENT_SCOPED_READ_VALUES
        and spec["student_owner"].column == "student_id"
    ]
    indirect = sorted(
        spec["student_owner"].column for spec in RESOURCES
        if spec["read_scope"] in STUDENT_SCOPED_READ_VALUES
        and spec["student_owner"].column != "student_id"
    )
    assert len(direct) == 11, direct
    assert indirect == ["prescription_id", "recipient_id"], indirect
    #: ⚠️ 两个非直接键的**声明形状**也逐字钉住（多态那一档的 ``kind`` 是承重的：
    #: 少了它，学生 4 会读到发给**教师 4** 的站内信，而两个 id 空间必然重叠）。
    owners = {
        spec["path"]: spec["student_owner"] for spec in RESOURCES
        if spec["read_scope"] in STUDENT_SCOPED_READ_VALUES
    }
    assert len(owners) == 13, sorted(owners)
    assert owners["/api/notifications"] == StudentOwner(
        column="recipient_id",
        kind=("recipient_kind", "student"),
        orphan=OrphanOwner(
            column="recipient_id",
            by=ORPHAN_BY_TEACHER_SELF,
            kind=("recipient_kind", "teacher"),
        ),
    )
    assert owners["/api/weekly-adjustments"] == StudentOwner(
        column="prescription_id", via=("prescription", "student_id")
    )
    assert all(o.kind is None for p, o in owners.items() if p != "/api/notifications")
    assert all(
        o.via is None for p, o in owners.items() if p != "/api/weekly-adjustments"
    )
    #: ⚠️⚠️ **第二根轴（Plan 06 Task 8b）的声明面也在这里逐字钉住**：13 行里
    #: **恰好 2 行**声明了 :attr:`StudentOwner.orphan`，而它们是**两个不同的档**
    #: （``alerts`` → :data:`ORPHAN_BY_TAUGHT_SECTION`、
    #: ``notifications`` → :data:`ORPHAN_BY_TEACHER_SELF`）。
    #: ⚠️ 少了本段，两格改动都是**静默的**：① 把第二根轴加到第三行
    #: （= 一张本来「无主行对任何教师都不可见」的表突然对某一位教师可见）；
    #: ② 把两档判据**互换**（= ``alerts`` 改按「收件人是我」判、``notifications``
    #: 改按「挂在我任教的班上」判，两档都恒假 → 悄悄退回 Task 8 顶回 1 那一格
    #: Critical，而失效方向是 200 + 少一行）。
    #: ⚠️ 而 ② 在**行为**上也由
    #: :func:`test_a_class_level_alert_is_visible_to_the_teacher_of_that_section_only`
    #: 与 :func:`test_a_notification_addressed_to_a_teacher_is_readable_by_him_only`
    #: 各钉一半（两条都带「本班/本人那一行 200」的绿档）——本段钉**声明面**、
    #: 那两条钉**运行期**，两侧各一半，与工厂第 15 道校验（导入期）合起来是三处。
    assert owners["/api/alerts"] == StudentOwner(
        column="student_id",
        orphan=OrphanOwner(
            column="course_section_id", by=ORPHAN_BY_TAUGHT_SECTION
        ),
    )
    with_orphan = sorted(p for p, o in owners.items() if o.orphan is not None)
    assert with_orphan == ["/api/alerts", "/api/notifications"], with_orphan
    assert sorted(
        o.orphan.by for o in owners.values() if o.orphan is not None
    ) == sorted([ORPHAN_BY_TAUGHT_SECTION, ORPHAN_BY_TEACHER_SELF])
    #: ⚠️ :data:`ORPHAN_BY_TAUGHT_SECTION` 那一档**必须**同时给出「主轴那一列 IS NULL」
    #:    的语义，而它由 :attr:`StudentOwner.column` 回答（本处钉住两行各自的组合）；
    #:    :data:`ORPHAN_BY_TEACHER_SELF` 那一档**必须**给出 ``kind``
    #:    （``notification.recipient_id`` 是 NOT NULL，「这一行不属于任何学生」
    #:    只能由种类列回答）。两格在导入期由工厂第 15 道校验挡，本处钉声明面。
    assert owners["/api/alerts"].orphan.kind is None
    assert owners["/api/notifications"].orphan.kind == ("recipient_kind", "teacher")


def test_the_two_roster_resources_admit_only_staff_reads(
    app, client, seeded, admin_headers, plain_teacher_headers
):
    """**Plan 05A Task 5 的三拍守卫**：名册的 4 个 GET 只对在册教职开放。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它挡的是本波查出来的那个洞（派单 §2.5 第 2 条 + 实现者新查出的教师那一侧）
    ------------------------------------------------------------------------
    ``POST /api/auth/students/bind`` 的验身材料是 ``student_no`` + ``birth``，
    而 ``POST /api/auth/teachers/bind`` 的是 ``staff_no`` + ``name``。
    Plan 05A Task 5 之前，``GET /api/students`` 匿名返回全部 60 人的 ``birth``、
    ``GET /api/teachers`` 匿名返回全部工号**与**姓名 —— 于是**任何匿名调用方**
    都能给任何账号绑一个自己知道的口令、再登录成他；教师那一侧还能挑一个
    ``role='admin'`` 的工号（``bind`` 不看 role、也不改 role，但登录之后他就是那个管理员）。

    ⚠️ 学生那一格是 Task 1+2 的实现者查出来的、控制者的计划完全漏掉的；
    **教师那一格是本波实现者实测新查出来的**（派单与计划都只点了学生那一侧）。

    ------------------------------------------------------------------------
    五拍，每一拍各挡一个失效形态
    ------------------------------------------------------------------------
    ① **匿名 → 401 ``unauthenticated``**：挡「把闸门整个摘掉」。
    ② **不在册的工号 → 403 ``forbidden``**：挡「只判有没有带头、不查库」
       （:func:`app.api.deps.require_staff` 那一次 ``select`` 存在的全部理由）。
    ③ **普通教师 → 200**：挡「收得太窄」。教师端的大屏/周报/预警队列都要读名册
       （按工号与姓名显示学生与同事），把它们也收成管理员会让 Plan 04 的教师端整个不可用。
    ④ **管理员 → 200**：与 ③ 一起挡「把 ``require_staff`` 写成 ``role == 'teacher'``」
       （管理员的 role 是 ``admin``，那一档会把他挡在名册之外，
       而管理台的 3 个页面读的就是名册）。
    ⑤ **反假绿**：那两份响应体里**确实**有 ``birth`` / ``name``（= 验身材料本身）。
       少了这一拍，「资源整个没挂上去 → 404」也能让 ① 那三行绿
       （404 也不是 200）；而 ``security`` 那一格的断言只证明**声明**在。

    ⚠️ 而「另外 21 个资源的 list 仍然匿名可读」由
    :func:`test_all_twenty_three_resources_are_listable` 的 ``anonymous == 21``
    那一拍钉住（本条刻意不重复：两条各钉一半，合并成一条会让
    「全仓一律要身份」与「全仓一律匿名」两个反方向都只红在一处）。
    """
    paths = app.openapi()["paths"]
    detail_of = {
        "/api/students": "/api/students/{student_id}",
        "/api/teachers": "/api/teachers/{teacher_id}",
    }
    # ⑤ 反假绿先跑：验身材料**真的**在这两个响应体里（用管理员身份读）
    student_row = client.get(
        "/api/students/" + str(seeded["student"]), headers=admin_headers
    ).json()
    teacher_row = client.get(
        "/api/teachers/" + str(seeded["teacher"]), headers=admin_headers
    ).json()
    assert "birth" in student_row, student_row
    assert {"staff_no", "name"} <= set(teacher_row), teacher_row

    for path in _ROSTER_PATHS:
        for template in (path, detail_of[path]):
            # ① OpenAPI 的声明面（少了它，前端与生成的 TS 客户端不知道要带身份）
            assert paths[template]["get"]["security"] == [{"X-Teacher-Staff-No": []}], template

        for url in (path, path + "/" + str(
            seeded["student"] if path == "/api/students" else seeded["teacher"]
        )):
            anonymous = client.get(url)
            assert anonymous.status_code == 401, (url, anonymous.text)
            assert anonymous.json()["error"]["code"] == "unauthenticated", url

            nobody = client.get(url, headers={"X-Teacher-Staff-No": "T2099999"})
            assert nobody.status_code == 403, (url, nobody.text)
            assert nobody.json()["error"]["code"] == "forbidden", url

            teacher = client.get(url, headers=plain_teacher_headers)
            assert teacher.status_code == 200, (url, teacher.text)

            admin = client.get(url, headers=admin_headers)
            assert admin.status_code == 200, (url, admin.text)


def test_the_student_keyed_resources_admit_four_read_tiers(
    client,
    engine,
    seeded,
    admin_headers,
    plain_teacher_headers,
    teaching_teacher_headers,
):
    """**四档矩阵**（Plan 06 Task 8 / 派单 §4 第 1 条）：16 个非匿名资源 × 两个 GET
    × **六档身份**，逐个实发请求（共 **172** 发，⚠️ 那个总数由本条末尾的
    ``assert fired == 172`` **机器钉住**，不再手抄——改前 docstring 里写的是 168、
    与实测的 172 差 4 发，而没有任何东西会红，Plan 06 Task 8b 顺手收了这一格）。

    ⚠️⚠️ **函数名里的 ``four`` 自 Plan 06 Task 8b 起刻意不改**（本波核过一次的取舍）：
    第五档 :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT_SECTION` **在结构上不可能**
    落在一个学生键资源上——工厂第 10 道校验禁止 ``student_owner`` 出现在那两档之外、
    第 13 道禁止 ``section_column`` 出现在第五档之外，故两格**互斥**。
    于是「**学生键**资源承认四档」这句话在加了第五档之后仍然逐字为真
    （对照 :func:`test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two`：
    那一条钉的是**全部** 23 行的五档分布，故它必须改名，本条不必）。
    ⚠️ 而第五档那唯一一个资源（``weekly-class-reports``，班级键）的六档身份矩阵住在
    :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches`。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它挡的是两个洞，不是一个
    ------------------------------------------------------------------------
    ① **终审 I6**（安全收紧波关的那一半）：那 44 个匿名 GET 里没有一个返回验身材料
       或人名，**但放行了整套以 ``student_id``（1–60 的小整数）为键的健康档案**：
       体成分、体测原始值 + 6 项得分、分层 ``label`` + ``hit_rules``、
       ``body_comp_abnormal``、处方、840 条训练日志（``feeling`` / ``duration_min``）、
       240 条 RPE、32 条预警、19 条站内消息（标题 + 正文）、兴趣问卷，以及
       ``enrollments``（谁在哪个班）。
       **任何已登录的学生只要把 cookie 丢掉，就能匿名读全校 60 人的健康档案。**
    ② **Plan 06 Task 8 关的那一半**（用户裁定「教师账号之间要有数据隔离」）：
       收紧之后那 13 个资源对**任何在册教师**仍然是全校全读——一位只带两个班的教师
       登录进去就能读到全校 60 人的健康档案。实测演示库：T0001 的任教范围是
       **41 / 60** 人，而他读 ``GET /api/training-logs`` 的 ``total`` 改前是全表
       **840**、改后是 **574**（``read_scope`` 的第四档 ``staff_taught``）。

    ------------------------------------------------------------------------
    六档，每一档各挡一个失效形态（前三档是安全收紧波立的，后三档是本波）
    ------------------------------------------------------------------------
    ① **匿名 → 401 ``unauthenticated``**（16 × 2 = **32** 发）：挡「把闸门整个摘掉」。
       这是安全收紧波的核心那一拍——少它，「丢 cookie 就能读全校」照旧成立。
    ② **学生读自己 → 200 且只看到自己的行**：挡「收得太宽」
       （学生会话仍然全读 = 收紧没生效）。
       ⚠️ 断的是 ``total == 1`` **与** ``items`` 的 id 清单**两格**：
       只断 ``items`` 的话，「在 Python 里过滤了 items、却把全表计数留给 total」
       是绿的，而那个失效会让前端分页器显示一个翻不到的页数（派单 §2 第 2 条）。
    ③ **另一个在册学生 → list 空（``total == 0``）+ read-one 403 ``forbidden``**：
       挡「过滤条件写错成恒真」与「read-one 忘了判」。
       ⚠️ **``total == 0`` 那一格是「过滤在 SQL 层」的直接证据**：
       若实现是「拉全量再在 Python 里筛」，``total`` 会是全表计数（1）。
       ⚠️ 而 read-one 用**另一个在册学生**而不是一个编造的 id：
       :func:`app.api.deps.require_scope` 有两支（不是本人 / 不在册），
       一个编造的 id 只会走到第二支，于是「第一支被写反」是绿的。
    ④ **教他的教师 → 200 且看得到那一行**（``total == 1``、read-one 200）：
       挡「收得太窄」。教师端三个页面（``Dashboard.vue`` / ``AlertQueue.vue`` /
       ``StudentDetail.vue``）都要按班、按人读**自己学生**的数据，
       把第四档写成「教师一律看不到」会让 Plan 04 的教师端整个不可用。
    ⑤ **不教他的教师 → list 空（``total == 0``）+ read-one 403 ``forbidden``**：
       挡「第四档整个没生效」（= 教职照旧全读，那正是本波要消灭的形状）。
       ⚠️ ``total == 0`` 那一格与 ③ 同一条理由：它是「过滤在 **SQL 层**」的证据。
       ⚠️ 而 read-one 走的是**既有那道闸门**
       :func:`app.api.deps.require_teaches_student`（判据是
       ``enrollment.course_section_id ∈ 我本学期任教的班``），
       故 403 的 message 里逐字带着「不在教师 … 于学期 … 任教的任何教学班里」——
       本条顺手把那一格也断住，于是「泛型读换了一份自己的判据」会红在这里。
    ⑥ **管理员 → 200 全读**：与 ④ 一起挡「把教职那一档写成 ``role == 'teacher'``」
       （管理台的 ``ResourceList`` / ``ResourceDetail`` 走的正是这一圈泛型读，
       而管理员**通常不带任何班**，故他不越过任教范围的话管理台就是空的）。

    ⚠️ **派单 §4 第 1 条要求「至少抽 4 个做全矩阵」**（``training-logs`` / ``alerts`` /
    ``body-compositions`` / ``notifications``），本条对 **13 个全做**
    （夹具是「每表一行」，故全做的成本与抽 4 个同阶，而判别力更强）。
    那 4 个「确实在被测名单里」由下面那一拍点名钉住。

    ⚠️ **``staff`` 那一档自 Plan 06 Task 8b 起是 2 个资源**（``students`` / ``teachers``；
    第三行 ``weekly-class-reports`` 挪进了第五档），与第五档那 1 个一起，
    在本条里只断三格：匿名 401（①）、**学生身份被拒**（②′）与**教职 list 200**。
    ⚠️ ②′ 的码实测是 **401** 而**不是**派单裁定 2 那张表写的
    403 —— 因为本夹具走请求头通道，而 ``X-Student-Id`` 对
    :func:`app.api.deps.current_teacher` 而言等于「没有教师身份」；
    cookie 通道下才是 403（跨 kind）。逐字理由写在 ②′ 那一段的行内注释里。
    名册那两个教职档的三拍由
    :func:`test_the_two_roster_resources_admit_only_staff_reads` 钉住，
    而 ``weekly-class-reports`` 的教职档（**按班收窄**）由
    :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches` 钉住。
    """
    # ⚠️ **第二个在册学生**是 ③ 那一档能跑起来的全部理由（理由逐字见 docstring）。
    #    它刻意不用 :func:`_seed_one_row_per_table`（那一份是「每表一行」的拓扑序夹具，
    #    给它加第二个学生会让 23 个资源的 ``total == 1`` 全部变成 2，
    #    而本文件有 4 条守卫钉那个 1）。
    #    ⚠️ 而它**刻意不编班**：于是它对 ④⑤ 两档都是「不在任何教师的任教范围里」，
    #    两档的期望值因此与 ③ 逐字相同（``total == 0`` / read-one 403）。
    with Session(engine) as session:
        other = Student(
            student_no="S2025777",
            name="另一个在册学生",
            sex="female",
            birth=D(2006, 1, 2),
            department="体育学院",
            grade=1,
        )
        session.add(other)
        session.commit()
        other_id = other.id
    assert other_id != seeded["student"], "第二个学生必须与 seeded 那一个不同行"

    mine = {"X-Student-Id": str(seeded["student"])}
    theirs = {"X-Student-Id": str(other_id)}

    staff_taught = [
        spec for spec in RESOURCES if spec["read_scope"] == READ_SCOPE_STAFF_TAUGHT
    ]
    #: ⚠️ **第五档（Plan 06 Task 8b）**：``weekly-class-reports`` 从 ``staff`` 挪进来。
    #:    本条对它只断「与另外两档逐字相同」的那两格（匿名 401 / 学生身份被拒 /
    #:    教职 list 200），而它那**按班收窄**的六档身份矩阵住在
    #:    :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches`
    #:    （两处刻意不合并：本条的夹具是「每表一行」，那一条要**两个班**才分得开
    #:    「教这个班的教师」与「教别的班的教师」）。
    staff_taught_section = [
        spec for spec in RESOURCES
        if spec["read_scope"] == READ_SCOPE_STAFF_TAUGHT_SECTION
    ]
    staff = [spec for spec in RESOURCES if spec["read_scope"] == READ_SCOPE_STAFF]
    assert (len(staff_taught), len(staff_taught_section), len(staff)) == (13, 1, 2)
    assert [spec["path"] for spec in staff_taught_section] == ["/api/weekly-class-reports"]
    #: ⚠️ 派单 §4 第 1 条点名的那 4 个资源确实在被测名单里（本条是全量、不是抽样）。
    #:    ⚠️ 而 ``notifications``（多态键）与另外 3 个（直接键）各代表一种学生键形状，
    #:    故这 4 个不是随便挑的：它们把 :class:`app.api.crud.StudentOwner` 的
    #:    ``kind`` 那一格与缺省那一格都覆盖到了（间接键 ``weekly-adjustments``
    #:    也在全量里）。
    assert {
        "/api/training-logs",
        "/api/alerts",
        "/api/body-compositions",
        "/api/notifications",
    } <= {spec["path"] for spec in staff_taught}

    # ① 匿名一律 401（16 × 2 = 32 发）
    # ⚠️ **16 这个数字自 Plan 06 Task 8b 起没变**（13 + 1 + 2），变的只是
    #    ``weekly-class-reports`` 从 ``staff`` 那一份挪到了第五档那一份。
    fired = 0
    for spec in staff_taught + staff_taught_section + staff:
        table = spec["model"].__tablename__
        for url in (spec["path"], spec["path"] + "/" + str(seeded[table])):
            got = client.get(url)
            assert got.status_code == 401, (url, got.text)
            assert got.json()["error"]["code"] == "unauthenticated", url
            fired += 1
    assert fired == 32, fired

    # ②③④⑤⑥ 五档身份 × 13 个资源 × 两个 GET
    # ⚠️ 表驱动：每一档给一个「期望的 list 状态 / total / read-one 状态」，
    #    而六档里 ②③ 与 ④⑤ 的期望值**逐字相同**（都是 200/1/200 与 200/0/403）——
    #    那不是巧合：两档判的是同一件事（「这一行属不属于你」），
    #    只是「你」在学生那一侧是本人、在教师那一侧是「他本学期任教的学生」。
    tiers = (
        ("② 学生自己", mine, 200, 1, 200),
        ("③ 学生别人", theirs, 200, 0, 403),
        ("④ 教师自己班", teaching_teacher_headers, 200, 1, 200),
        ("⑤ 教师别人班", plain_teacher_headers, 200, 0, 403),
        ("⑥ 管理员", admin_headers, 200, 1, 200),
    )
    for label, headers, list_status, want_total, one_status in tiers:
        for spec in staff_taught:
            table = spec["model"].__tablename__
            url = spec["path"] + "/" + str(seeded[table])

            listing = client.get(spec["path"], headers=headers)
            fired += 1
            assert listing.status_code == list_status, (label, spec["path"], listing.text)
            body = listing.json()
            # ⚠️⚠️ ``total`` 与 ``items`` **两格都断**（派单 §4 第 3 条）：
            #    只断 ``items`` 的话，「拉全量再在 Python 里筛」是绿的，
            #    而它的失效形态是前端分页器给出一个翻不到的页数。
            assert body["total"] == want_total, (
                label, spec["path"], body["total"],
                "total 没有跟着过滤：那一格必须与 items 走同一个 WHERE",
            )
            want_items = [seeded[table]] if want_total == 1 else []
            assert [row["id"] for row in body["items"]] == want_items, (
                label, spec["path"], body["items"]
            )

            one = client.get(url, headers=headers)
            fired += 1
            assert one.status_code == one_status, (label, url, one.text)
            if one_status == 403:
                assert one.json()["error"]["code"] == "forbidden", (label, url)

    # ⚠️ ⑤ 那一档的 403 **确实是任教闸门给的**（不是别的什么 403）：
    #    message 里逐字带着「不在教师 … 任教的任何教学班里」。少了本拍，
    #    「泛型读自己写了一份判据、而它与 require_teaches_student 漂了」是绿的。
    stray = client.get(
        "/api/training-logs/" + str(seeded["training_log"]),
        headers=plain_teacher_headers,
    )
    assert stray.status_code == 403, stray.text
    message = stray.json()["error"]["message"]
    assert "不在教师" in message and "任教的" in message, message
    assert PLAIN_TEACHER_STAFF_NO in message, message
    fired += 1

    # ②′ staff 那一档（⚠️ Plan 06 Task 8b 起**连第五档一起**）：学生身份被拒。
    # ⚠️⚠️ **码是 401 而不是 403，而这一格是安全收紧波实现者实测出来的**
    # （派单裁定 2 的表里写的是「学生会话 → 403」）：本夹具走的是**请求头通道**
    # （``tests/conftest.py`` 把 ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``"1"``），
    # 而 :func:`app.api.deps.current_teacher` **只认** cookie 与
    # ``X-Teacher-Staff-No``——一个 ``X-Student-Id`` 头对它而言就是「没有教师身份」，
    # 故落到「缺身份」那一档 = **401 ``unauthenticated``**。
    # ⚠️ 而**cookie 通道**下（生产档）同一个学生会话打过去是 **403 ``forbidden``**
    # （``current_teacher`` 看见 ``identity.kind != teacher`` → 跨 kind），
    # 那一档由 ``tests/api/test_auth_api.py`` 的 cookie 侧守卫覆盖。
    # ⚠️ 两档都**拒绝**，差别只是「我不知道你是谁」与「我知道你是谁、但你不是教职」；
    # 这个「同一个失效在两个通道下给出两个码」的形状与
    # :func:`app.api.deps.current_student` docstring 末段记的那一格同族，
    # 如实记录（硬规矩 #39）。
    # ⚠️⚠️ **第五档刻意与 ``staff`` 档跑同一次遍历**（派单 §1 裁定 B 第 3 条逐字要求
    # 「学生那一档的码逐字不变」）：两档都沿用 :func:`app.api.crud._require_staff_identity`
    # 那**一道**闸门，故「学生会话 → 401（请求头通道）/ 403（cookie 通道）」与
    # 「教职 list → 200」两格在两档上**逐字相同**。⚠️ 而这一格正是
    # 「第五档没有顺手换成 :func:`app.api.deps.current_reader`」的行为侧证据：
    # 换了的话 ``X-Student-Id`` 就会被那一道认下来、这里的 401 会变成 200
    # （声明面的同一格证据住在那条第五档守卫末尾的 ``security`` / ``parameters`` 两拍）。
    # ⚠️ 而 ``weekly-class-reports`` 是**只读**资源，故
    # test_every_writable_resource_admits_only_an_admin_mutation 的「教职放行」那一支
    # 覆盖不到它（那条只遍历 writable 的 9 行）——本拍顺手补上。
    # ⚠️⚠️ **而「教职 list 200」不等于「教职读到全部行」**：第五档对**不带任何班**的
    # 那一位给的是 ``total == 0``（Task 8 那一格跨教师泄漏已修），
    # 逐字取证住在 :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches`。
    for spec in staff_taught_section + staff:
        got = client.get(spec["path"], headers=mine)
        assert got.status_code == 401, (spec["path"], got.text)
        assert got.json()["error"]["code"] == "unauthenticated", spec["path"]
        fired += 1
        for headers in (plain_teacher_headers, teaching_teacher_headers):
            assert client.get(spec["path"], headers=headers).status_code == 200, spec[
                "path"
            ]
            fired += 1

    #: ⚠️ **发数由机器钉住，不再手抄**（Plan 06 Task 8b）：改前 docstring 里逐字写着
    #: 「共 **168** 发」，而实测是 **172**（32 + 130 + 1 + 9）——一个手抄的总数漂了
    #: 一整波都没有任何东西会红。故本条把计数收进 ``fired``，末尾断一次。
    #: ⚠️ 本波那一次挪档**没有改这个总数**（``weekly-class-reports`` 只是从
    #: ``staff`` 那一份挪到第五档那一份，16 个非匿名资源与 3 个「学生身份被拒」
    #: 的资源两个数都没动）。
    assert fired == 172, fired


def test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student(
    client, engine, seeded, admin_headers, teaching_teacher_headers
):
    """**多态键那一档的红档**：一行发给**教师**的站内信，学生读不到（403）。

    ⚠️ 它挡的是 :class:`app.api.crud.StudentOwner` 的 ``kind`` 那一格被删掉：
    ``notification`` 的学生键是 ``recipient_id``，而那一格装的是 ``student.id``
    **还是** ``teacher.id`` 由并排的 ``recipient_kind`` 决定
    （:attr:`app.db.models.feedback.Notification.RECIPIENT_KINDS` 实测是
    ``{'student', 'teacher'}``）。少了 ``kind`` 那一格，过滤条件就只剩
    ``recipient_id = :me``——而两个 id 空间是**独立的自增序列**，必然重叠，
    于是学生 1 会读到发给教师 1 的站内信。

    ⚠️ **本条必须自己插一行 ``recipient_kind='teacher'`` 的通知**：
    :func:`_seed_one_row_per_table` 插的那一行是 ``'student'``
    （与演示库实测一致：19 行全是 ``'student'``），故空转不得。
    ⚠️ 造法是「让 ``recipient_id`` 撞上 ``seeded['student']``」——
    即一行**发给教师、但 recipient_id 恰好等于那个学生 id** 的通知。
    那是最刁钻的反例：若 ``kind`` 那一格不在，它会**正好**落进学生的自过滤里。

    ⚠️ 四拍：① 学生 read-one 那一行 → **403**（:data:`NOT_STUDENT_OWNED`
    那一档：这行不属于任何学生）；② 学生的 list 里**不含**它；
    ③ **管理员** read-one 它 → **200**（绿档同时在场，硬规矩 #50：
    否则「这一行根本没插进去」也会让①②绿）；
    ④ **收件人本人**（= 库里第一位教师）read-one 它 → **200**、list 里**含**它
    （⚠️ 本拍是 Plan 06 Task 8b 的**翻转**，逐字见下）。

    ⚠️⚠️ **③ 那一拍自 Plan 06 Task 8 起用管理员、改前用「库里第一个教师」**：
    第四档 ``staff_taught`` 的判据是**学生键**，而这一行**没有**学生所有者
    （``recipient_kind='teacher'`` → :data:`NOT_STUDENT_OWNED`）。
    ⚠️⚠️ **而 ④ 那一拍在 Plan 06 Task 8b 被翻转了**（Task 8 顶回 1 的落点）：
    改前它逐字断的是「**教那个学生的教师** read-one 它 → **403**」，并把这个 403
    当成一格「已顶回的功能收窄」钉住（一位教师从此读不到发给**他自己**的站内信）。
    今天 ``notifications`` 声明了**第二根轴**
    ``OrphanOwner(column="recipient_id", by=ORPHAN_BY_TEACHER_SELF,
    kind=("recipient_kind", "teacher"))``，故**收件人本人**读得到它、
    别的教师读不到（⚠️ **翻转它本身就是取证**，派单 §1 守卫 ④）。
    ⚠️ **①②③ 三拍判据一个字没改**：学生那一支走 :func:`app.api.crud._owner_filter`
    （``recipient_kind='student'`` **且** ``recipient_id = 我``），一个字节都没动，
    于是「学生 4 读到发给教师 4 的站内信」这个方向**仍然挡着**——
    那正是本条从头到尾要钉的那一格（``kind`` 那一格被删掉时它响）。
    ⚠️ 而「对**哪一位**教师可见」那一维的完整六档矩阵由
    :func:`test_a_notification_addressed_to_a_teacher_is_readable_by_him_only` 钉
    （本夹具只有一个班、一位带班教师，故那一维在本条里**分不开**）。
    """
    with Session(engine) as session:
        row = Notification(
            recipient_kind="teacher",
            # ⚠️ 刻意撞上 seeded 那个学生的 id（理由逐字见上面）
            recipient_id=seeded["student"],
            channel="in_app",
            title="发给教师的站内信",
            body="这一行的 recipient_id 恰好等于那个学生的 id。",
            is_read=False,
            created_at=T(2025, 9, 13, 3, 0),
        )
        session.add(row)
        session.commit()
        teacher_notification_id = row.id

    mine = {"X-Student-Id": str(seeded["student"])}
    url = "/api/notifications/" + str(teacher_notification_id)

    # ① 学生 read-one → 403
    got = client.get(url, headers=mine)
    assert got.status_code == 403, (url, got.text)
    assert got.json()["error"]["code"] == "forbidden", url

    # ② 学生的 list 里不含它（而 seeded 那一行『发给学生的』照旧在）
    listing = client.get("/api/notifications?limit=200", headers=mine).json()
    ids = [row["id"] for row in listing["items"]]
    assert teacher_notification_id not in ids, ids
    assert seeded["notification"] in ids, ids
    assert listing["total"] == 1, listing["total"]

    # ③ 绿档：**管理员**读得到它（越过任教范围）
    staff = client.get(url, headers=admin_headers)
    assert staff.status_code == 200, (url, staff.text)
    assert staff.json()["recipient_kind"] == "teacher"

    # ④ **翻转（Plan 06 Task 8b）**：这一行的 ``recipient_id`` 刻意撞上
    #    ``seeded["student"]``，而本夹具里 ``student.id`` 与 ``teacher.id``
    #    **恰好都是 1**（两张表各自的第一行）——故它同时是「发给教师 1 的站内信」，
    #    而 :func:`teaching_teacher_headers` 那一位**正是** ``seeded["teacher"]``。
    #    ⚠️ 下面那一行把「恰好相等」这件事**断言出来**（不再靠巧合读代码猜）：
    #    它一旦不成立，本拍的 200 就会退化成 403，而报错会指到身份那一格。
    #    ⚠️ 反空转：同一位教师读 seeded 那一行『发给学生的』照旧 200，
    #    于是本拍的 200 不可能只是因为「notifications 整个不筛了」。
    assert seeded["student"] == seeded["teacher"], (
        seeded["student"], seeded["teacher"],
        "本拍要求那一行发给的教师恰好是 teaching_teacher_headers 那一位",
    )
    as_teacher = client.get(url, headers=teaching_teacher_headers)
    assert as_teacher.status_code == 200, (url, as_teacher.text)
    assert as_teacher.json()["recipient_kind"] == "teacher", url
    assert client.get(
        "/api/notifications/" + str(seeded["notification"]),
        headers=teaching_teacher_headers,
    ).status_code == 200
    teacher_listing = client.get(
        "/api/notifications?limit=200", headers=teaching_teacher_headers
    ).json()
    assert [row["id"] for row in teacher_listing["items"]] == [
        seeded["notification"], teacher_notification_id
    ], teacher_listing
    assert teacher_listing["total"] == 2, teacher_listing["total"]


def test_a_class_level_alert_is_visible_to_the_teacher_of_that_section_only(
    client,
    engine,
    seeded,
    other_section,
    admin_headers,
    teaching_teacher_headers,
    other_teaching_teacher_headers,
    plain_teacher_headers,
):
    """**第二根轴的红档 + 绿档**（Plan 06 Task 8b；⚠️ 本条是 Task 8 那条守卫的**翻转**）：
    一条**班级级**预警（``student_id IS NULL`` + ``course_section_id`` 非空）对
    **它自己那个班的任课教师**可见、对**别的班的教师**与**不带任何班的教师**不可见、
    对**管理员**可见、对**学生**不可见。

    ------------------------------------------------------------------------
    ⚠️⚠️ 本条改前钉的是**回归现状**，今天钉的是修复（翻转它本身就是取证）
    ------------------------------------------------------------------------
    改前它叫
    ``test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin``，
    逐字断的是「教那个班的教师 read-one → **403**、list 里**不含**它」——
    它把 Task 8 顶回 1 的那一格 **Critical** 钉住，好让将来修它的人先看到它红。
    今天修了，故它**必须**改（派单 §1 守卫 ④ 逐字要求「Task 8 那条守卫要翻转成
    『对相关教师可见』」）。翻转的是 ③ 那一拍：改前 ``403 / total == 1 /
    items == [学生级那一条]``，今天 ``200 / total == 2 /
    items == [学生级那一条, 我班的班级级那一条]``。
    ⚠️ 而 ②（管理员）与 ③④ 里那两格**反空转**的判据**一个字没改**，
    ①⑤⑥ 三拍是本波新加的（改前没有第二位带班教师，故「对**哪一位**教师可见」
    这一维**分不开**）。

    ------------------------------------------------------------------------
    改前为什么是 403（那一格 Critical 的机制，逐字）
    ------------------------------------------------------------------------
    :data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT` 的判据是**学生键**
    （``<学生键列> IN (我本学期任教的学生)``），而一行班级级预警**没有**学生所有者：
    ``alert.student_id`` 是 ``NULL``，SQL 的三值逻辑让 ``NULL IN (…)`` 恒不成立，
    于是它被 list 过滤掉；read-one 那一侧 :func:`app.api.crud._owner_of_row` 给出
    :data:`app.api.deps.NOT_STUDENT_OWNED`（``-1``），
    :func:`app.api.deps.require_teaches_student` 于是 ``403``。
    ⚠️ 失效方向是**静默的**（响应 200、只是少一行），而它**是生产路径会产出的形状**：
    :func:`app.pipeline.alert_stage.evaluate_alerts` 末段有一个
    「班级级：全量遍历本学期的教学班」的循环，命中
    :func:`app.domain.alerts.evaluate_class` 的规则时逐字写
    ``student_id=None, course_section_id=section_id``。
    ⚠️ 演示库上**0 行**（唯一的班级级规则 ``YELLOW_CLASS_RPE_HIGH`` 的阈值是
    班级 RPE 均值 > 7，实测最高 6.93，差 0.07 没越线）——**这正是 Task 8 的
    既有测试与 ``frontend/scripts/smoke.mjs`` 都看不见这格回归的原因**。
    故本条**自己造两行**（两个班各一行），而 :func:`other_section` 那第二个班
    是「对**哪一位**教师可见」这一格能分开的全部理由。

    ------------------------------------------------------------------------
    六拍（⚠️ 红档与绿档都在场，硬规矩 #50）
    ------------------------------------------------------------------------
    ① **匿名** → 两个 read-one 都 ``401 unauthenticated``（挡「把闸门整个摘掉」）；
    ② **管理员** → 两个 read-one 都 200、list ``total == 3``（两根轴都放开 = 全读）；
    ③ **教 seeded 那个班的教师** → 自己那行 **200**、别人那行 **403**、
       list 恰好 **2** 行（学生级那一条 + 自己班的班级级那一条）；
    ④ **教另一个班的教师** → 反过来：别人那行 403、自己那行 200、
       list 恰好 **1** 行（⚠️ 那个班**没有编任何学生**，故学生级那一条对他不可见——
       这一格顺带钉住「第二根轴没有把主轴一起放宽」）；
    ⑤ **不带任何班的教师** → 两个 read-one 都 403、list ``total == 0``
       （挡「第二根轴写成了恒真」）；
    ⑥ **学生** → 两个 read-one 都 403、list ``total == 1``（只有他自己那一条学生级）
       （挡「第二根轴也放开了学生档」：学生那一支走 :func:`app.api.crud._owner_filter`，
       它**一个字节都没改**，而 ``student_id = :me`` 对 ``NULL`` 天然不匹配）。
    ⚠️ ③④⑤ 各带一格**反空转**：同一位教师读 seeded 那条**学生级**预警
    （③ 200 / ④ 403 / ⑤ 403），于是 ③ 的 200 不可能只是因为「alerts 整个不筛了」、
    ④⑤ 的 403 也不可能只是因为「教师一律读不到 alerts」。
    """
    def _class_level_alert(session, section_id: int) -> int:
        """插一条**班级级**预警（形状逐字照 ``alert_stage`` 那个班级级循环）。"""
        row = Alert(
            # ⚠️ 两列**恰好一个**非空（``ck_alert_subject_is_exactly_one``）
            student_id=None,
            course_section_id=section_id,
            semester_id=seeded["semester"],
            # ⚠️ 前缀的字面量所有者是 :data:`app.domain.alerts.SUBJECT_PREFIX_SECTION`
            subject_key="section:" + str(section_id),
            level="yellow",
            rule_id="YELLOW_CLASS_RPE_HIGH",
            trigger_snapshot={"mean_rpe": 7.4, "student_count": 30},
            triggered_at=T(2025, 9, 12, 3, 0),
            status="pending",
            handled_action=None,
            handled_at=None,
            batch_id=seeded["daily_sync_run"],
            # ⚠️ 两条各挂**自己的班**，故 ``subject_key`` 不同、
            #    ``uq_alert_rule_subject_semester_window`` 不撞。
            window_key="2025-09-12",
        )
        session.add(row)
        session.flush()
        return row.id

    with Session(engine) as session:
        mine = _class_level_alert(session, seeded["course_section"])
        theirs = _class_level_alert(session, other_section["course_section_id"])
        session.commit()
    assert mine != theirs
    url_of = {mine: "/api/alerts/" + str(mine), theirs: "/api/alerts/" + str(theirs)}
    student_url = "/api/alerts/" + str(seeded["alert"])

    # ① 匿名：两个 read-one 都 401（挡「把闸门整个摘掉」）
    for url in url_of.values():
        got = client.get(url)
        assert got.status_code == 401, (url, got.text)
        assert got.json()["error"]["code"] == "unauthenticated", url
    assert client.get("/api/alerts").status_code == 401

    # ② 管理员：两个 read-one 都 200、list 含两行（两根轴都放开）
    for url in url_of.values():
        got = client.get(url, headers=admin_headers)
        assert got.status_code == 200, (url, got.text)
        assert got.json()["student_id"] is None, url
        assert got.json()["course_section_id"] is not None, url
    admin_listing = client.get("/api/alerts?limit=200", headers=admin_headers).json()
    assert admin_listing["total"] == 3, admin_listing["total"]
    assert {row["id"] for row in admin_listing["items"]} == {
        seeded["alert"], mine, theirs
    }

    # ③ 教 seeded 那个班的教师：自己那行 200、别人那行 403、list 恰好 2 行
    got = client.get(url_of[mine], headers=teaching_teacher_headers)
    assert got.status_code == 200, (url_of[mine], got.text)
    assert got.json()["course_section_id"] == seeded["course_section"]
    denied = client.get(url_of[theirs], headers=teaching_teacher_headers)
    assert denied.status_code == 403, (url_of[theirs], denied.text)
    assert denied.json()["error"]["code"] == "forbidden", url_of[theirs]
    listing = client.get("/api/alerts?limit=200", headers=teaching_teacher_headers).json()
    assert listing["total"] == 2, listing["total"]
    assert [row["id"] for row in listing["items"]] == [seeded["alert"], mine], listing

    # ④ 教另一个班的教师：反过来，且 list 恰好 1 行（他那个班没有编任何学生，
    #    故学生级那一条对他不可见 —— 这一格钉住「第二根轴没有把主轴一起放宽」）
    assert client.get(url_of[theirs], headers=other_teaching_teacher_headers
                      ).status_code == 200, url_of[theirs]
    assert client.get(url_of[mine], headers=other_teaching_teacher_headers
                      ).status_code == 403, url_of[mine]
    other_listing = client.get(
        "/api/alerts?limit=200", headers=other_teaching_teacher_headers
    ).json()
    assert other_listing["total"] == 1, other_listing["total"]
    assert [row["id"] for row in other_listing["items"]] == [theirs], other_listing

    # ⑤ 不带任何班的教师：两个 read-one 都 403、list total == 0
    for url in url_of.values():
        got = client.get(url, headers=plain_teacher_headers)
        assert got.status_code == 403, (url, got.text)
        assert got.json()["error"]["code"] == "forbidden", url
    plain_listing = client.get("/api/alerts?limit=200", headers=plain_teacher_headers).json()
    assert plain_listing["total"] == 0, plain_listing
    assert plain_listing["items"] == [], plain_listing

    # ⑥ 学生：两个 read-one 都 403、list 只有他自己那一条学生级
    student_headers = {"X-Student-Id": str(seeded["student"])}
    for url in url_of.values():
        got = client.get(url, headers=student_headers)
        assert got.status_code == 403, (url, got.text)
        assert got.json()["error"]["code"] == "forbidden", url
    student_listing = client.get("/api/alerts?limit=200", headers=student_headers).json()
    assert student_listing["total"] == 1, student_listing["total"]
    assert [row["id"] for row in student_listing["items"]] == [seeded["alert"]]

    # ③④⑤ 三格反空转：同一条**学生级**预警在三位教师手上的三个答案
    assert client.get(student_url, headers=teaching_teacher_headers).status_code == 200
    assert client.get(student_url, headers=other_teaching_teacher_headers).status_code == 403
    assert client.get(student_url, headers=plain_teacher_headers).status_code == 403

    # ⚠️ **③ 那一拍的 403 确实是第二根轴给的**（不是别的什么 403）：
    #    message 里逐字带着那一列的名字与「没有学生所有者」。少了本拍，
    #    「read-one 换了一份自己的判据、而它与 list 那一个 OR 支漂了」是绿的。
    message = denied.json()["error"]["message"]
    assert "没有学生所有者" in message and "course_section_id" in message, message
    assert SEEDED_TEACHER_STAFF_NO in message, message


def test_a_notification_addressed_to_a_teacher_is_readable_by_him_only(
    client,
    engine,
    seeded,
    other_section,
    admin_headers,
    teaching_teacher_headers,
    other_teaching_teacher_headers,
    plain_teacher_headers,
):
    """**第二根轴（``teacher_self`` 那一档）的六档身份矩阵**（Plan 06 Task 8b）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它与 :func:`test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student`
    各钉一半，两半合起来才封住这一格
    ------------------------------------------------------------------------
    那一条钉的是「**学生**读不到发给教师的站内信」（``kind`` 那一格被删掉时它响），
    本条钉的是「**哪一位教师**读得到它」——而那一维需要
    :func:`other_section` 那**第二位带班教师**才分得开（改前只有一位时，
    「对收件人可见」与「对任何教师都可见」两个口径给出同一个答案）。
    ⚠️ 改前（Plan 06 Task 8）这一行的答案是「对**任何**教师都 403、只有管理员读得到」，
    即一格**真实的功能收窄**：一位教师读不到发给**他自己**的站内信，
    而它是 ``alert_stage`` 班级级那一段的 ``_notify`` 会产出的形状。

    ------------------------------------------------------------------------
    ⚠️⚠️ 本条**刻意把两个 id 空间的重叠做成反例**（派单 §1 的口径）
    ------------------------------------------------------------------------
    ``student.id`` 与 ``teacher.id`` 是**两个独立的自增序列**，必然重叠。
    故本条先插**第二个学生**（它的 id 于是恰好等于 :func:`other_section`
    那一位教师的 id），再断言那个学生**读不到**这行发给教师的站内信。
    ⚠️ 少了这一拍，「``OrphanOwner.kind`` 那一格被删掉」是**绿的**：
    判据会退化成 ``recipient_id = 我的 teacher.id``，而那个学生正好同号——
    而那正是 :class:`app.api.crud.OrphanOwner` 的注释逐字点名要挡的形状
    （工厂的第 15 道校验在导入期也挡它，两侧各钉一半）。

    ------------------------------------------------------------------------
    六拍（⚠️ 红档与绿档都在场，硬规矩 #50）
    ------------------------------------------------------------------------
    ① **匿名** → list 与 read-one 都 ``401``；
    ② **收件人本人**（:func:`other_teaching_teacher_headers`）→ read-one **200**、
       list 恰好 1 行（⚠️ 它那个班**没有编任何学生**，故 seeded 那条
       「发给学生」的站内信对他不可见 —— 这一格顺带钉住
       「第二根轴没有把主轴一起放宽」）；
    ③ **别的教师**（:func:`teaching_teacher_headers`）→ read-one **403**、
       list 恰好 1 行（= seeded 那条发给学生的）；
    ④ **不带任何班的教师** → read-one **403**、list ``total == 0``；
    ⑤ **管理员** → read-one **200**、list ``total == 2``（两根轴都放开）；
    ⑥ **两个学生**（seeded 那一个 + 与收件人**同号**的那一个）→ read-one 都 **403**、
       list 里都不含它。
    """
    with Session(engine) as session:
        # ⚠️ **第二个学生**：它的 id 于是恰好等于收件人那一位教师的 id
        #    （两张表各自的第二行），即上面那一段点名的重叠反例。
        twin = Student(
            student_no="S2025888",
            name="与收件人教师同号的学生",
            sex="female",
            birth=D(2006, 2, 3),
            department="体育学院",
            grade=1,
        )
        session.add(twin)
        session.flush()
        row = Notification(
            recipient_kind="teacher",
            recipient_id=other_section["teacher_id"],
            channel="in_app",
            title="你任教的班本周课堂 RPE 偏高",
            body="这一行是 alert_stage 的班级级那一段发给任课教师的站内信。",
            is_read=False,
            created_at=T(2025, 9, 13, 3, 0),
        )
        session.add(row)
        session.commit()
        twin_id = twin.id
        teacher_notification_id = row.id
    #: ⚠️ 这一行是本条那格反例能成立的**前提**，故断言出来（不再靠巧合）：
    #:    两个 id 空间重叠了，于是「只看 ``recipient_id``」的判据会把这一行
    #:    同时给收件人教师**和**同号的那个学生。
    assert twin_id == other_section["teacher_id"], (twin_id, other_section["teacher_id"])
    url = "/api/notifications/" + str(teacher_notification_id)

    # ① 匿名：401
    assert client.get(url).status_code == 401
    assert client.get("/api/notifications").status_code == 401

    # ② 收件人本人：200，且 list 里恰好只有这一行
    got = client.get(url, headers=other_teaching_teacher_headers)
    assert got.status_code == 200, (url, got.text)
    assert got.json()["recipient_kind"] == "teacher", url
    assert got.json()["recipient_id"] == other_section["teacher_id"], url
    listing = client.get(
        "/api/notifications?limit=200", headers=other_teaching_teacher_headers
    ).json()
    assert listing["total"] == 1, listing["total"]
    assert [row["id"] for row in listing["items"]] == [teacher_notification_id], listing

    # ③ 别的教师：403，而 seeded 那条「发给学生」的照旧在（反空转）
    denied = client.get(url, headers=teaching_teacher_headers)
    assert denied.status_code == 403, (url, denied.text)
    assert denied.json()["error"]["code"] == "forbidden", url
    other_listing = client.get(
        "/api/notifications?limit=200", headers=teaching_teacher_headers
    ).json()
    assert other_listing["total"] == 1, other_listing["total"]
    assert [row["id"] for row in other_listing["items"]] == [seeded["notification"]]
    assert client.get(
        "/api/notifications/" + str(seeded["notification"]),
        headers=teaching_teacher_headers,
    ).status_code == 200

    # ④ 不带任何班的教师：403 + total == 0
    assert client.get(url, headers=plain_teacher_headers).status_code == 403
    plain_listing = client.get(
        "/api/notifications?limit=200", headers=plain_teacher_headers
    ).json()
    assert plain_listing["total"] == 0, plain_listing

    # ⑤ 管理员：200 + total == 2（两根轴都放开）
    assert client.get(url, headers=admin_headers).status_code == 200
    admin_listing = client.get("/api/notifications?limit=200", headers=admin_headers).json()
    assert admin_listing["total"] == 2, admin_listing["total"]
    assert {row["id"] for row in admin_listing["items"]} == {
        seeded["notification"], teacher_notification_id
    }

    # ⑥ 两个学生都读不到它（⚠️ 第二个与收件人**同号**，那是本条最刁钻的一拍）
    for student_id in (seeded["student"], twin_id):
        headers = {"X-Student-Id": str(student_id)}
        got = client.get(url, headers=headers)
        assert got.status_code == 403, (student_id, url, got.text)
        assert got.json()["error"]["code"] == "forbidden", (student_id, url)
        body = client.get("/api/notifications?limit=200", headers=headers).json()
        assert teacher_notification_id not in [row["id"] for row in body["items"]], (
            student_id, body
        )
    # ⚠️ 反空转：seeded 那个学生**读得到**发给他的那一条（于是 ⑥ 的 403
    #    不可能只是因为「学生一律读不到 notifications」）
    mine = {"X-Student-Id": str(seeded["student"])}
    assert client.get(
        "/api/notifications/" + str(seeded["notification"]), headers=mine
    ).status_code == 200

    # ⚠️ **③ 那一拍的 403 确实是第二根轴给的**（不是别的什么 403）：
    #    message 里逐字带着「没有学生所有者」与那一列的名字。少了本拍，
    #    「read-one 换了一份自己的判据、而它与 list 那一个 OR 支漂了」是绿的。
    message = denied.json()["error"]["message"]
    assert "没有学生所有者" in message and "recipient_id" in message, message


def test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches(
    client,
    engine,
    seeded,
    other_section,
    admin_headers,
    teaching_teacher_headers,
    other_teaching_teacher_headers,
    plain_teacher_headers,
):
    """**第五档 ``staff_taught_section`` 的六档身份矩阵**（Plan 06 Task 8b，
    ⚠️ 修的是 Task 8 顶回 2 的那一格跨教师泄漏）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 改前的实况（Task 8 的逐字取证，本条就是它的反面）
    ------------------------------------------------------------------------
    ``weekly-class-reports`` 改前是 ``read_scope="staff"``（**任何在册教职全读**），
    而泛型 **read-one 含全部 5 个 ``JsonText`` 聚合列**，故任何教师能
    ``GET /api/weekly-class-reports/{别的班的 id}`` 读到那个班的 ``progress_board``
    （= 进步榜 top 10 的 ``student_id`` + ``change_pct``）与 ``layer_distribution`` /
    ``rpe_summary`` / ``checkin_rate_by_layer`` / ``alert_summary`` 四个聚合列。
    实测（演示库、T0001 的 cookie，他只任教班 1 与班 3）：5 个班的 read-one **各 200**，
    班 2 的 ``progress_board.top`` 开头逐字是
    ``[{"student_id":48,"change_pct":188.53},{"student_id":47,"change_pct":165},…]``。
    ⚠️ 而**前端页面上看不出这一格**：特例端点
    ``GET /api/dashboard/weekly-class-report/{id}`` 有自己的
    :func:`app.api.deps.require_teaches_section`，故泄漏面是 **API**、不是 UI。

    ------------------------------------------------------------------------
    ⚠️ 学生那一档**维持现状**（派单 §2 逐字要求先实测「学生今天能不能读它」）
    ------------------------------------------------------------------------
    实测（本条 ⑥ 那一拍 + 改前同一份夹具）：学生会话打过去是 **401**
    （请求头通道：``X-Student-Id`` 对 :func:`app.api.deps.current_teacher` 而言
    等于「没有教师身份」）；cookie 通道下是 **403**（跨 kind）。
    两档都**拒绝**，故「学生能读全校周报」这个更大的洞**不存在**、无需顶回。
    ⚠️ 而第五档**沿用** :func:`app.api.crud._require_staff_identity` 那一道闸门，
    故这一档的码与 ``"staff"`` 档**逐字相同**（本拍判据一个字没改）。

    ------------------------------------------------------------------------
    六拍（⚠️ 红档与绿档都在场，硬规矩 #50）
    ------------------------------------------------------------------------
    ① **匿名** → list 与两个 read-one 都 ``401``；
    ② **教 seeded 那个班的教师** → 自己那行 **200**、别人那行 **403**、
       list 恰好 1 行；
    ③ **教另一个班的教师** → 反过来；
    ④ **不带任何班的教师** → 两个 read-one 都 403、list ``total == 0``
       （挡「第五档写成了恒真」）；
    ⑤ **管理员** → 两个 read-one 都 200、list ``total == 2``（越过任教范围，
       管理台的 ``ResourceList.vue`` 照旧是全校视图）；
    ⑥ **学生** → list ``401``（上面那一段）。
    ⚠️ ② 那一拍**顺带把泄漏面本身钉住**：read-one 的响应体里确实有
    ``progress_board``、而它里面确实带 ``student_id`` —— 少了这一拍，
    「403 是因为响应体空了 / 端点根本没挂上」也能让 ②③④ 全绿。
    """
    with Session(engine) as session:
        row = WeeklyClassReport(
            course_section_id=other_section["course_section_id"],
            semester_id=seeded["semester"],
            week=2,
            layer_distribution={"red": 2, "yellow": 1, "green": 0},
            rpe_summary={"mean": 7.4, "delta": 0.9},
            checkin_rate_by_layer={"red": 0.4, "yellow": 0.6},
            # ⚠️ **形状逐字照演示库实测**：``top`` 里逐条带 ``student_id`` +
            #    ``change_pct``，即「本周进步榜 top 10」——它正是本档要收的泄漏面。
            progress_board={
                "top_n": 10,
                "top": [{"student_id": 48, "change_pct": 188.53}],
            },
            alert_summary={"yellow": 2, "red": 1},
            suggestion="这个班的课堂负荷偏高，本周建议整体减量。",
            generated_at=T(2025, 9, 14, 4, 0),
            batch_id=seeded["daily_sync_run"],
        )
        session.add(row)
        session.commit()
        other_report_id = row.id
    mine_report_id = seeded["weekly_class_report"]
    assert other_report_id != mine_report_id
    url_of = {
        mine_report_id: "/api/weekly-class-reports/" + str(mine_report_id),
        other_report_id: "/api/weekly-class-reports/" + str(other_report_id),
    }

    # ① 匿名：list 与两个 read-one 都 401
    assert client.get("/api/weekly-class-reports").status_code == 401
    for url in url_of.values():
        got = client.get(url)
        assert got.status_code == 401, (url, got.text)
        assert got.json()["error"]["code"] == "unauthenticated", url

    # ② 教 seeded 那个班的教师：自己那行 200（⚠️ 且响应体里确实有那个泄漏面）、
    #    别人那行 403、list 恰好 1 行
    got = client.get(url_of[mine_report_id], headers=teaching_teacher_headers)
    assert got.status_code == 200, (url_of[mine_report_id], got.text)
    body = got.json()
    assert "progress_board" in body, sorted(body)
    assert body["course_section_id"] == seeded["course_section"], body
    denied = client.get(url_of[other_report_id], headers=teaching_teacher_headers)
    assert denied.status_code == 403, (url_of[other_report_id], denied.text)
    assert denied.json()["error"]["code"] == "forbidden"
    listing = client.get(
        "/api/weekly-class-reports?limit=200", headers=teaching_teacher_headers
    ).json()
    assert listing["total"] == 1, listing["total"]
    assert [row["id"] for row in listing["items"]] == [mine_report_id], listing

    # ③ 教另一个班的教师：反过来
    assert client.get(
        url_of[other_report_id], headers=other_teaching_teacher_headers
    ).status_code == 200, url_of[other_report_id]
    assert client.get(
        url_of[mine_report_id], headers=other_teaching_teacher_headers
    ).status_code == 403, url_of[mine_report_id]
    other_listing = client.get(
        "/api/weekly-class-reports?limit=200", headers=other_teaching_teacher_headers
    ).json()
    assert other_listing["total"] == 1, other_listing["total"]
    assert [row["id"] for row in other_listing["items"]] == [other_report_id]

    # ④ 不带任何班的教师：两个 read-one 都 403、list total == 0
    for url in url_of.values():
        got = client.get(url, headers=plain_teacher_headers)
        assert got.status_code == 403, (url, got.text)
    plain_listing = client.get(
        "/api/weekly-class-reports?limit=200", headers=plain_teacher_headers
    ).json()
    assert plain_listing["total"] == 0, plain_listing
    assert plain_listing["items"] == [], plain_listing

    # ⑤ 管理员：两个 read-one 都 200、list total == 2
    for url in url_of.values():
        assert client.get(url, headers=admin_headers).status_code == 200, url
    admin_listing = client.get(
        "/api/weekly-class-reports?limit=200", headers=admin_headers
    ).json()
    assert admin_listing["total"] == 2, admin_listing["total"]
    assert {row["id"] for row in admin_listing["items"]} == {
        mine_report_id, other_report_id
    }

    # ⑥ 学生：**401**（请求头通道；cookie 通道是 403，两档都拒绝 —— 见 docstring）
    student_headers = {"X-Student-Id": str(seeded["student"])}
    got = client.get("/api/weekly-class-reports", headers=student_headers)
    assert got.status_code == 401, got.text
    assert got.json()["error"]["code"] == "unauthenticated"
    for url in url_of.values():
        assert client.get(url, headers=student_headers).status_code == 401, url

    # ⚠️ **② 那一拍的 403 确实是第五档给的**（不是别的什么 403）：
    #    message 里逐字带着那一列的名字与「本学期任教」。少了本拍，
    #    「read-one 换了一份自己的判据、而它与 list 那一个 WHERE 漂了」是绿的。
    message = denied.json()["error"]["message"]
    assert "course_section_id" in message and "本学期" in message, message
    assert SEEDED_TEACHER_STAFF_NO in message, message
    # ⚠️ **而 OpenAPI 的声明面一个字节都没变**：第五档沿用 ``"staff"`` 那一道闸门，
    #    故这两个操作挂的仍然**只有**教师头那一个 scheme（没有 ``X-Student-Id``）。
    #    少了本拍，「顺手换成 current_reader、于是这个只认教职的资源在契约里
    #    多出一个它根本不认的学生头」是绿的。
    paths = client.get("/openapi.json").json()["paths"]
    for template in (
        "/api/weekly-class-reports",
        "/api/weekly-class-reports/{weekly_class_report_id}",
    ):
        assert paths[template]["get"]["security"] == [
            {"X-Teacher-Staff-No": []}
        ], template
        assert [
            p["name"] for p in paths[template]["get"].get("parameters", [])
            if p["in"] == "header"
        ] == ["x-teacher-staff-no"], template

    #: ⚠️⚠️ **而上面那两拍还不够**（派单 §1 裁定 B 第 4 条逐字要求「实测复核」）：
    #: 「与 ``staff`` 档**逐字相同**」比「等于一个字面量」强一格——字面量那两拍
    #: 允许第五档与 ``staff`` 档各自漂到同一个错值上，而本拍把两档**互为对照**：
    #: 把 ``security`` 与**请求头** ``parameters`` 两格序列化成 JSON 后逐字节比。
    #: ⚠️ 只比这两格、不比整个操作对象：路径参数的别名（``weekly_class_report_id``
    #: vs ``student_id``）与 ``response_model`` 本来就**该**不同，
    #: 而本拍要钉的是「**身份**那一格没变」。
    #: ⚠️ 实测（本波）：``/api/weekly-class-reports`` 的两个 GET 与
    #: ``/api/students`` / ``/api/teachers`` 的四个 GET，六格 JSON **逐字相同**。
    def _identity_face(template: str) -> str:
        op = paths[template]["get"]
        return json.dumps(
            {
                "security": op.get("security"),
                "header_parameters": [
                    p for p in op.get("parameters", []) if p.get("in") == "header"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    tier5 = [
        _identity_face("/api/weekly-class-reports"),
        _identity_face("/api/weekly-class-reports/{weekly_class_report_id}"),
    ]
    staff_tier = [
        _identity_face(t)
        for t in (
            "/api/students",
            "/api/students/{student_id}",
            "/api/teachers",
            "/api/teachers/{teacher_id}",
        )
    ]
    assert len(set(staff_tier)) == 1, staff_tier  # 反空转：对照组自己得是一致的
    assert set(tier5) == set(staff_tier), (tier5, staff_tier)


#: ⚠️⚠️ **``403`` 的 body 里不许出现的内部标识符**（Plan 06 Task 8b）。
#:
#: 判据是「一个**不该看到这一行**的调用方，能从这次拒绝里额外学到什么」：
#: 模块路径、私有函数名、档位常量名与内部设计词汇一律是**给实现者读的话**，
#: 发给调用方等于顺手把服务端的内部结构摊出去一档（他本来只该知道「403」）。
#: ⚠️ 改前 :func:`app.api.crud._require_orphan_row_readable` 逐字吐的是
#: 「…第二根轴的判据是「recipient_id 落在他本学期的任教范围里」（teacher_self），
#: 逐字见 app/api/crud.py 的 _orphan_condition」——**四格全中**
#: （内部设计词汇 / 档位常量 / 模块路径 / 私有函数名），
#: 而 :func:`app.api.crud._require_section_readable` 吐的是
#: 「判据是 course_section_id ∈ app.api.deps.taught_section_ids」——中两格。
#:
#: ⚠️ **列名刻意不在本清单里**（``course_section_id`` / ``recipient_id`` /
#: ``recipient_kind``）：它同时是这个资源 ``read`` schema 里的一个字段名，
#: 本来就在这次响应的邻域里；且 :mod:`app.api.deps` 里既有的那些 ``403``
#: 逐字同族（:func:`app.api.deps.require_teaches_section` 写着
#: 「判据是 course_section.teacher_id」，而它从不写函数名与模块路径）。
#: ⚠️ 于是本清单钉的是**收窄的口径**，不是一条「403 不许解释自己」的规矩——
#: 一条不许解释的规矩会把「调用方拿不到任何可行动信息」变成契约。
_DENIAL_BODY_FORBIDDEN_TOKENS = (
    "app/api",
    "app.api",
    "crud.py",
    "deps.py",
    "_orphan_condition",
    "_owner_of_row",
    "_reader_filter",
    "_require_orphan_row_readable",
    "_require_row_matches",
    "_require_section_readable",
    "_section_filter",
    "taught_section",
    "teacher_self",
    "StudentOwner",
    "OrphanOwner",
    "READ_SCOPE",
    "NOT_STUDENT_OWNED",
    "第二根轴",
    "第四档",
    "第五档",
)


def test_the_read_denial_messages_do_not_disclose_internal_identifiers(
    client,
    engine,
    seeded,
    other_section,
    teaching_teacher_headers,
):
    """**``403`` 文案的收窄守卫**（Plan 06 Task 8b / 派单 §1 裁定 A 第 2 条）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它挡的是一格**信息泄漏**，不是一格文案口味
    ------------------------------------------------------------------------
    一个 ``403`` 的调用方**已经**被判定为「不该看到这一行」，而改前那三份 message
    把「服务端怎么判的」逐字告诉了他：模块路径（``app/api/crud.py``）、
    私有函数名（``_orphan_condition``）、档位常量（``teacher_self``）与
    内部设计词汇（「第二根轴」）。⚠️ 那不是「解释得清楚」，那是把
    **给实现者读的话发给了调用方**：他于是学到了服务端的模块划分与判据形状，
    而这三格对他**没有任何正当用处**（他要的只是「为什么我被拒」）。
    ⚠️ 本条与 :data:`_DENIAL_BODY_FORBIDDEN_TOKENS` 一起把口径钉住，
    收窄后的文案逐字理由住在 :func:`app.api.crud._require_orphan_row_readable`。

    ------------------------------------------------------------------------
    四拍：三份**运行期可达**的 message + 一份**防御性**的
    ------------------------------------------------------------------------
    ① 班级级预警（``taught_section`` 那一档）：教 seeded 那个班的教师读
       **别的班**那一条 → ``403``；
    ② 发给教师的站内信（``teacher_self`` 那一档）：同一位教师读
       **发给别的教师**的那一条 → ``403``；
    ③ 别的班那份周报（第五档）：同一位教师读它 → ``403``；
    ④ 「这张表**没有**声明第二根轴」那一支：⚠️ 它今天在 HTTP 层**不可达**
       （实测：13 个学生键资源里只有 ``alert.student_id`` 可空、而它已声明了
       第二根轴；``notification`` 那一档由种类列回答、也已声明；
       ``weekly_adjustment`` 的间接键要中间行消失，而外键挡住了它），
       故本拍**直接调**那一个函数取证——它是「许可而不是断言」的一档，
       而它同样会产出一份 message，故同样要收窄。

    ⚠️⚠️ **每一拍都带一格反空转**（硬规矩 #50）：断言 message 里**确实**还带着
    表名与那个工号。少了它，「把 message 删空 / 换成一句 'forbidden'」
    会让本条**更绿**——而那一改会把「调用方拿不到任何可行动信息」变成现状。
    ⚠️ 而 ``①②③`` 三拍各自由
    :func:`test_a_class_level_alert_is_visible_to_the_teacher_of_that_section_only` /
    :func:`test_a_notification_addressed_to_a_teacher_is_readable_by_him_only` /
    :func:`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches`
    钉住**行为**（谁 200、谁 403），本条只钉**文案**，两处刻意不合并：
    合并的话「文案漂了」与「判据漂了」会红在同一处、而报错分不清是哪一格。
    """
    with Session(engine) as session:
        alert_row = Alert(
            student_id=None,
            course_section_id=other_section["course_section_id"],
            semester_id=seeded["semester"],
            subject_key="section:" + str(other_section["course_section_id"]),
            level="yellow",
            rule_id="YELLOW_CLASS_RPE_HIGH",
            trigger_snapshot={"mean_rpe": 7.4},
            triggered_at=T(2025, 9, 12, 3, 0),
            status="pending",
            batch_id=seeded["daily_sync_run"],
            window_key="2025-09-12",
        )
        note_row = Notification(
            recipient_kind="teacher",
            recipient_id=other_section["teacher_id"],
            channel="in_app",
            title="发给别的教师的站内信",
            body="这一行不是发给 teaching_teacher_headers 那一位的。",
            is_read=False,
            created_at=T(2025, 9, 13, 3, 0),
        )
        report_row = WeeklyClassReport(
            course_section_id=other_section["course_section_id"],
            semester_id=seeded["semester"],
            week=3,
            layer_distribution={"red": 1},
            rpe_summary={"mean": 7.1},
            checkin_rate_by_layer={"red": 0.5},
            progress_board={"top_n": 10, "top": [{"student_id": 48, "change_pct": 1.0}]},
            alert_summary={"yellow": 1},
            suggestion="别的班那一份周报。",
            generated_at=T(2025, 9, 21, 4, 0),
            batch_id=seeded["daily_sync_run"],
        )
        session.add_all([alert_row, note_row, report_row])
        session.commit()
        targets = (
            ("① 班级级预警（别的班）", "/api/alerts/" + str(alert_row.id), "alert"),
            ("② 站内信（发给别的教师）",
             "/api/notifications/" + str(note_row.id), "notification"),
            ("③ 周报（别的班）",
             "/api/weekly-class-reports/" + str(report_row.id), "weekly_class_report"),
        )

    # ①②③ 三份运行期可达的 message
    for label, url, table in targets:
        got = client.get(url, headers=teaching_teacher_headers)
        assert got.status_code == 403, (label, url, got.text)
        body = got.json()
        assert body["error"]["code"] == "forbidden", (label, body)
        message = body["error"]["message"]
        leaked = [t for t in _DENIAL_BODY_FORBIDDEN_TOKENS if t in got.text]
        assert leaked == [], (label, leaked, got.text)
        # ⚠️ 反空转：收窄**不是**删空——表名与那个工号都还在，
        #    故调用方仍然知道「哪一张表的哪一行、因为谁」被拒。
        assert table in message, (label, message)
        assert SEEDED_TEACHER_STAFF_NO in message, (label, message)

    # ④ 「这张表没有声明第二根轴」那一支（HTTP 层今天不可达，故直接调）
    reader = ReaderIdentity(staff_no=SEEDED_TEACHER_STAFF_NO, role=Teacher.DEFAULT_ROLE)
    with Session(engine) as session:
        obj = session.get(Alert, seeded["alert"])
        assert obj is not None
        with pytest.raises(HTTPException) as caught:
            _require_orphan_row_readable(
                session,
                Alert,
                "id",
                obj,
                # ⚠️ 刻意给一份**没有**第二根轴的声明（= 那 11 行的形状）
                StudentOwner(column="student_id"),
                reader,
            )
    assert caught.value.status_code == 403
    detail = str(caught.value.detail)
    leaked = [t for t in _DENIAL_BODY_FORBIDDEN_TOKENS if t in detail]
    assert leaked == [], (leaked, detail)
    assert "不属于任何学生" in detail, detail


def test_the_student_self_tier_still_behaves_as_staff_full_read(
    app, client, seeded, admin_headers, plain_teacher_headers
):
    """``read_scope="student_self"`` 那一档**今天在 23 行 ``RESOURCES`` 里有 0 行**，
    而它**仍然可用**——故它不是死代码（硬规矩 #39 的「许可而不是断言」那一档）。

    ⚠️ **本条与 :func:`test_an_explicit_pk_alias_overrides_the_automatic_one` 同一条口径**：
    一个「有能力、无生产调用方」的档位必须被**跑通一次**，否则下一个人删掉它时
    没有任何东西会红，而删掉它的失效形态是「那个形状在代码里没有名字了，
    要它的人去改 ``staff_taught``（= 把 13 行的口径一起改掉）」。
    保留它的两条理由逐字住在 :data:`app.api.crud.READ_SCOPE_STUDENT_SELF` 的注释里。

    ⚠️⚠️ **判据是「两档只在教职那一维上不同」**（不是「两档各自对不对」）：
    同一个模型、同一行、同一个合成路径形状，差别**只有** ``read_scope`` 那一格。
    四拍：

    ① 匿名 → 两个都 **401**（两档都挂身份）；
    ② 学生自己 → 两个都 **200 / ``total == 1``**（学生那一维逐字相同）；
    ③ **不教他的教师** → ``student_self`` 是 **200 / ``total == 1``**（教职全读），
      而 ``staff_taught`` 是 **200 / ``total == 0``** + read-one **403**；
    ④ 管理员 → 两个都 **200 / ``total == 1``**。

    ⚠️ ③ 那一拍是本条的全部判别力：把两档写成同一条分支的话它会红，
    而 ①②④ 三拍挡的是「收得太窄」（把 ``student_self`` 也写成按任教范围过滤）。
    ⚠️ 用的是 :func:`plain_teacher_headers`（一位**不教任何班**的教师）而不是
    :func:`teaching_teacher_headers`：本条要的是「教职全读」与「按任教范围过滤」
    在**同一位**教师身上给出两个答案，而一位教他的教师在两档下都是 200/1
    （= 没有判别力）。
    """
    from app.api.schemas.feedback import TrainingLogRead

    def _probe(scope: str) -> str:
        path = f"/api/probe-{scope.replace('_', '-')}-training-logs"
        app.include_router(
            build_crud_router(
                model=TrainingLog,
                schemas=CrudSchemas(TrainingLogRead),
                path=path,
                tags=["probe"],
                writable=False,
                on_delete=ON_DELETE_RESTRICT,
                natural_key=("student_id", "log_date"),
                read_scope=scope,
                student_owner=StudentOwner(column="student_id"),
            )
        )
        return path

    self_path = _probe(READ_SCOPE_STUDENT_SELF)
    taught_path = _probe(READ_SCOPE_STAFF_TAUGHT)
    pk = str(seeded["training_log"])
    mine = {"X-Student-Id": str(seeded["student"])}

    # ① 匿名：两个都 401
    for path in (self_path, taught_path):
        assert client.get(path).status_code == 401, path
        assert client.get(path + "/" + pk).status_code == 401, path

    # ② 学生自己：两个都 200 / total == 1 / read-one 200
    for path in (self_path, taught_path):
        body = client.get(path, headers=mine).json()
        assert body["total"] == 1, (path, body["total"])
        assert [row["id"] for row in body["items"]] == [seeded["training_log"]], path
        assert client.get(path + "/" + pk, headers=mine).status_code == 200, path

    # ③ 不教他的教师：两档给出**两个**答案（本条的判别力全在这一拍）
    full = client.get(self_path, headers=plain_teacher_headers)
    assert full.status_code == 200, full.text
    assert full.json()["total"] == 1, (
        self_path, full.json()["total"],
        "student_self 那一档的教职是全读，故它应当数得到 seeded 那一行",
    )
    assert client.get(
        self_path + "/" + pk, headers=plain_teacher_headers
    ).status_code == 200

    scoped = client.get(taught_path, headers=plain_teacher_headers)
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["total"] == 0, (
        taught_path, scoped.json()["total"],
        "staff_taught 那一档的教师只读自己任教班级的学生行，而本夹具那一位不教任何班",
    )
    assert scoped.json()["items"] == [], scoped.json()["items"]
    denied = client.get(taught_path + "/" + pk, headers=plain_teacher_headers)
    assert denied.status_code == 403, (taught_path, denied.text)
    assert denied.json()["error"]["code"] == "forbidden", denied.text

    # ④ 管理员：两个都全读
    for path in (self_path, taught_path):
        body = client.get(path, headers=admin_headers).json()
        assert body["total"] == 1, (path, body["total"])
        assert client.get(path + "/" + pk, headers=admin_headers).status_code == 200


def test_the_generic_list_and_read_one_descriptions_are_verbatim_identical(app):
    """23 个泛型 list 的 OpenAPI ``description`` **只有 1 种取值**，read-one 同样。

    ⚠️ **本条是安全收紧波那两个端点分支的直接后果**：
    :func:`app.api.crud.build_crud_router` 今天为
    ``read_scope in STUDENT_SCOPED_READ_VALUES``（``student_self`` / ``staff_taught``）
    与「其余」各写了一份 ``list_rows`` / ``read_one``（差别**只有形参表**：
    前者多一个 ``reader: ReaderIdentity = Depends(current_reader)``，
    因为形参会进 OpenAPI，无条件挂上去会让那 7 个匿名资源凭空多出两个请求头参数）。
    两支的函数体各一行、都调同一个 :func:`app.api.crud._list_page`，
    而两支的 **docstring 必须逐字相同**——否则同一份 API 会因为有没有一个
    ``reader`` 形参而给出两种「list 是什么形状」的说法，
    而那份说法**逐字进** ``/openapi.json`` 与 ``npm run gen:api`` 的产物。

    ⚠️ **期望侧从 ``app.openapi()`` 实读**（硬规矩 #89），不从源码里抠字符串：
    两侧同源的话，「改了一支的 docstring」会同时改掉两边、断言恒成立。

    ⚠️ 改前实测（本波开工时）：``distinct list descriptions == 1``、
    ``distinct read-one descriptions == 1``，各 ×23。故本条钉的是**既有性质的保持**，
    不是新加的性质。
    """
    paths = app.openapi()["paths"]
    list_descriptions = set()
    read_descriptions = set()
    counted = 0
    for spec in RESOURCES:
        path = spec["path"]
        segments = len(path.split("/"))
        found = [
            key for key in paths
            if key.startswith(path + "/{") and len(key.split("/")) == segments + 1
        ]
        assert len(found) == 1, (path, found)
        list_descriptions.add(paths[path]["get"].get("description", ""))
        read_descriptions.add(paths[found[0]]["get"].get("description", ""))
        counted += 1
    assert counted == 23, counted
    assert len(list_descriptions) == 1, [d[:80] for d in sorted(list_descriptions)]
    assert len(read_descriptions) == 1, [d[:80] for d in sorted(read_descriptions)]
    # ⚠️ 反空转：两种 description 都**非空**，且 list 那一份点名了 ``total``
    #    （本波把它的口径从「全表计数」改成「本页口径下的计数」，
    #    而那句散文的住址只能是那一份 docstring）。
    (list_doc,) = list_descriptions
    (read_doc,) = read_descriptions
    assert list_doc and read_doc
    assert "total" in list_doc, list_doc


def test_password_bound_at_is_absent_from_both_the_read_model_and_the_list(
    client, seeded, admin_headers
):
    """**``password_bound_at`` 摘除的三拍守卫**（控制者裁定 3；照 ``rpe_token`` 的形状）。

    ------------------------------------------------------------------------
    ⚠️ 为什么摘它
    ------------------------------------------------------------------------
    它告诉一个教职**哪些账号还没绑口令**，也就是**哪些还能被抢占绑定**
    （``POST /api/auth/{students,teachers}/bind`` 只对 ``password_hash IS NULL``
    的行放行，故它挡不住「给一个还没注册的账号抢先把口令绑上」）。
    教职专用故低危，但本波在收读侧，顺手一并摘掉。

    ------------------------------------------------------------------------
    三拍，各挡一半（``rpe_token`` 那一条的同构）
    ------------------------------------------------------------------------
    ① **read-one 不含**：``StudentRead`` / ``TeacherRead`` 摘列那一半。
       少了它，「只改了 ``list_exclude``」是绿的，而 read-one 照旧给出那一格。
    ② **list 不含**：``catalog.RESOURCES`` 两行的 ``list_exclude`` 那一半。
       ⚠️ 这一拍**必须**独立存在：泛型 list 端点**不走 ``response_model``**
       （它显式只 SELECT ``kept`` 那些列、手工拼 dict），故光是从读模型上摘掉
       **堵不住 list**——那正是 Plan 03 收尾小修波给 ``rpe_token`` 补第二半时
       逐字记下的失效形态。
    ③ **绿档**：两个端点仍然 200，且**其余各列都在**（学生 7 列 / 教师 4 列）。
       少了它，「把整个读模型清空」也能让①②绿。

    ⚠️ 而「这一列**今天还在 DB 上**、只是不暴露」由
    :func:`test_every_read_schema_covers_exactly_the_model_columns` 的档 2 清单钉住
    （它反向也钉：清单里点名的列必须①真的是该表的一列、②真的**不在**读模型上）。
    ⚠️ 「``*Create`` / ``*Update`` 也不含它」由档 1 清单
    （:data:`_SERVER_FILLED_COLUMNS`）钉住，本条不重复。
    """
    for path, table, kept in (
        ("/api/students", "student", 7),
        ("/api/teachers", "teacher", 4),
    ):
        # ① read-one 不含
        one = client.get(
            path + "/" + str(seeded[table]), headers=admin_headers
        )
        assert one.status_code == 200, (path, one.text)
        assert "password_bound_at" not in one.json(), (path, sorted(one.json()))
        assert "password_bound_at" not in one.text, path
        # ③ 绿档：其余各列都在
        assert len(one.json()) == kept, (path, sorted(one.json()))

        # ② list 不含
        listing = client.get(path, headers=admin_headers)
        assert listing.status_code == 200, (path, listing.text)
        assert "password_bound_at" not in listing.text, path
        for item in listing.json()["items"]:
            assert "password_bound_at" not in item, (path, sorted(item))
            assert "password_hash" not in item, (path, sorted(item))
            # ③ list 的键集合 = read-one 的键集合（这两行没有 JsonText 列，
            #    故 list_exclude 排掉的恰好就是那两个凭据列）
            assert set(item) == set(one.json()), (path, sorted(item))
# ===========================================================================
# Plan 06 Task 15 / 终审 S3-④：``ck_alert_subject_is_exactly_one`` 那条 CHECK
# ===========================================================================
#: ⚠️ **字面量**（硬规矩 #35 的刻意例外）：约束的**名字**是一个决定、不是一个算式，
#: 从被测侧读回来跟自己比是同源断言、什么都证明不了（口径与
#: ``tests/auth/test_passwords.py`` 钉 ``PBKDF2_MIN_VERIFY_ITERATIONS == 100_000``、
#: ``tests/api/test_column_widths.py`` 钉 ``OVERLONG_SUFFIX == "…[cut]"`` 逐字相同）。
#: 而约束的**形状**一律从元数据与实库的 DDL 里读，一个字都不抄。
_ALERT_SUBJECT_CHECK = "ck_alert_subject_is_exactly_one"


def _check_constraints(table) -> list:
    """一张表上全部 ``CheckConstraint``（从**模型元数据**读，不抄字面量）。"""
    return [c for c in table.constraints if isinstance(c, CheckConstraint)]


def test_the_alert_subject_check_constraint_exists_by_name_and_shape_in_model_and_ddl(engine):
    """``alert`` 表上「两个作用域列**恰好一个**非空」那条 CHECK 的名字与形状（两面各钉一次）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 为什么要有本条（终审 S3-④）
    ------------------------------------------------------------------------
    :func:`app.api.crud._orphan_condition` 在 ``ORPHAN_BY_TAUGHT_SECTION`` 那一档上
    额外拼了一格 ``<学生键列> IS NULL``，而它的 docstring 逐字说那一格是**承重**的
    （``crud.py:806-813``：「少了它，一行**有**学生所有者、而那个学生不在我的任教范围里
    的预警，会仅因为『它挂在我教的那个班上』就变可见」）。
    ⚠️ 而终审的定点变异 M23 把那一格改成 ``if False:`` 之后，
    ``pytest tests/api/test_crud.py`` 是 **50 passed / exit 0**（不红）—— 因为
    **今天的写入方**（``app/pipeline/alert_stage.py`` 的学生级那一段写的是
    ``student_id=<id>, course_section_id=None``）加上**本条钉的那条 CHECK**，
    使那一格与不加它**语义等价**。⚠️ 于是它的价值只在**将来**
    （「有人给学生级预警也填上班」那一天），而将来它**不会响**。

    ⚠️ 故本波的处置不是「给 ``_orphan_condition`` 造一个绕过 CHECK 的夹具」
    （绕不过去：那条 CHECK 就是为了挡这一档而存在的），而是**把 CHECK 自己钉住**：
    将来有人放宽它（或把它从模型/迁移里拿掉），会先红在本条上，
    从而被迫回答「那一格 ``IS NULL`` 谁来挡」。

    ------------------------------------------------------------------------
    ⚠️ 两面各钉一次（两侧不同源）
    ------------------------------------------------------------------------
    ① **模型元数据**：``Alert.__table__.constraints`` 里恰好有一个叫这个名字的
       ``CheckConstraint``，而它的 SQL 文本是「两列各自 ``IS NULL``、用 ``<>`` 连」；
    ② **实库的 DDL**：``sqlite_master`` 里 ``alert`` 表的 ``CREATE TABLE`` 原文里
       那个名字与那两列都在。⚠️ 而 ``engine`` 那个夹具走的是
       :func:`app.db.session.init_db` → **alembic 迁移链**（不是 ``create_all(models)``），
       故 ② 量到的是**迁移写出来的** DDL，与 ① 的模型元数据**不同源**：
       「模型上有、迁移里漏了」与反过来都会红。
    """
    named = [c for c in _check_constraints(Alert.__table__) if c.name == _ALERT_SUBJECT_CHECK]
    # ① 模型元数据：恰好一个、名字逐字、形状是「两列 IS NULL 的异或」
    assert len(named) == 1, (
        f"{Alert.__tablename__} 上叫 {_ALERT_SUBJECT_CHECK} 的 CHECK 有 {len(named)} 个；"
        f"全部 CHECK 的名字 = {sorted(c.name for c in _check_constraints(Alert.__table__))}"
    )
    shape = str(named[0].sqltext)
    for column in ("student_id", "course_section_id"):
        assert shape.count(f"{column} IS NULL") == 1, (column, shape)
    assert "<>" in shape, (
        f"那条 CHECK 不再是「恰好一个非空」的形状了：{shape!r}。"
        f"⚠️ 它是 :func:`app.api.crud._orphan_condition` 那一格 ``IS NULL`` 与之等价的"
        f"全部前提（放宽它 = 一行可以同时有学生与班两个主语，"
        f"于是「去年我教过的班上挂着别人的预警」会变成我可见）。"
    )
    # ⚠️ 反空转：``alert`` 表上**还有**别的 CHECK（两个取值域），故上面那一拍
    #    不是「一张没有任何 CHECK 的表上恰好有 1 个叫这个名字的」那种空转形状。
    others = sorted(
        c.name for c in _check_constraints(Alert.__table__) if c.name != _ALERT_SUBJECT_CHECK
    )
    assert len(others) >= 2, others

    # ② 实库的 DDL（迁移链写出来的那一份，与 ① 不同源）
    with engine.connect() as connection:
        ddl = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :n"),
            {"n": Alert.__tablename__},
        ).scalar_one()
    assert _ALERT_SUBJECT_CHECK in ddl, ddl
    for column in ("student_id", "course_section_id"):
        assert f"{column} IS NULL" in ddl, (column, ddl)
    assert "<>" in ddl, ddl
