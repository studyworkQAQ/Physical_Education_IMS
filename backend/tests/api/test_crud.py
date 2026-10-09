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
import pathlib

import pytest
from sqlalchemy import UniqueConstraint, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.crud import (
    ON_DELETE_CASCADE,
    ON_DELETE_FORBID,
    ON_DELETE_RESTRICT,
    CrudSchemas,
    _child_tables,
    _conflict_message,
    _json_text_columns,
    _pk_alias_of,
    build_crud_router,
)
from app.api.deps import require_scope
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
        _add(Teacher, staff_no="T2025001", name="张老师")
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


# ---------------------------------------------------------------------------
# 批次 A：五个端点（semester / teacher / stratification_result）
# ---------------------------------------------------------------------------


def test_list_returns_items_total_limit_offset(client, seeded):
    """``GET {path}`` 的响应形状逐字是 ``{"items", "total", "limit", "offset"}``。

    ``total`` 是**全表计数**、不受 ``limit``/``offset`` 影响——前端要靠它算总页数，
    一个「本页条数」会让分页控件永远只有一页。三个学期 + ``limit=2`` 把这个差别钉住：
    ``len(items) == 2`` 而 ``total == 3``，两侧不同源。
    """
    for name in ("2025-2026-2", "2026-2027-1"):
        got = client.post("/api/semesters", json={**SEMESTER_PAYLOAD, "name": name})
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


def test_create_returns_201_with_a_location_header(client):
    """``POST {path}`` → **201** + ``Location`` 头 + 整行的读模型。

    ``Location`` 是 RFC 9110 对「创建出了一个新资源」的要求，也是前端「建完就跳到详情页」
    最省事的实现路径（不必从响应体里挑主键）。断言它逐字等于 ``{path}/{新主键}``，
    而那个主键从**响应体**读回来——两侧一个是头、一个是体，不同源。
    """
    got = client.post("/api/semesters", json=SEMESTER_PAYLOAD)
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


def test_create_with_a_duplicate_natural_key_is_409(client):
    """撞自然键 → **409**，消息点名**列名**、且不含字面 ``"None"``（P3-B5）。

    ⚠️ ``semester.name`` 的唯一约束是**无名的**（实测 ``UniqueConstraint.name is None``，
    同族的还有 ``teacher.staff_no`` / ``student.student_no`` / ``exercise.ref`` /
    ``prescription_template.template_ref``）。把约束名插进消息就会渲染出字面 ``"None"``，
    而那句话是要给教师看的。故断言里同时要求 ``"name" in message`` 与
    ``"None" not in message``。

    **红绿两档**：第二次 POST 之前先断言第一次是 201，否则「一律 409」也能让本条绿。
    """
    first = client.post("/api/semesters", json=SEMESTER_PAYLOAD)
    assert first.status_code == 201, first.text

    second = client.post("/api/semesters", json=SEMESTER_PAYLOAD)
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
    tampered = client.post("/api/semesters", json={**SEMESTER_PAYLOAD, "weeks": 99})
    assert tampered.status_code == 409, tampered.text
    after = client.get("/api/semesters/" + str(first.json()["id"])).json()
    assert after["weeks"] == 16, "被拒绝的 POST 改掉了已有行（rollback 没做）"
    assert client.get("/api/semesters").json()["total"] == 1


def test_read_one_returns_the_row(client, seeded):
    """``GET {path}/{pk}`` → 整行，**含** ``JsonText`` 列（list 端点不含，见下面那条）。"""
    got = client.get("/api/stratification-results/" + str(seeded["stratification_result"]))
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["label"] == "yellow"
    assert body["hit_rules"] == "R1,Y1"
    assert body["input_snapshot"] == {"W": 1, "C": 0, "valid_count": 6}
    assert body["valid_to"] is None


def test_read_a_missing_pk_is_404(client):
    """主键查无此行 → 404 + 统一形状。

    ⚠️ 实现走的是 ``session.get(model, pk)`` + 显式 ``raise HTTPException(404)``
    （P3-B7：``repo.py`` 只有 ``upsert`` 与 ``delete_by_batch`` 两个公开函数，
    没有 ``get_or_404``，也**不该**为这件事给它加一个）。
    """
    got = client.get("/api/stratification-results/424243")
    assert got.status_code == 404
    body = got.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["detail"] is None
    assert "424243" in body["error"]["message"]


def test_patch_changes_only_the_keys_present(client):
    """**部分更新**：``null`` 与「没传」必须可区分（计划 Review Focus 的同一条）。

    三拍，缺一不可：

    ① ``PATCH {"name": …}`` 只改 ``name``，``department`` 保持原值——
      若实现用了 ``model_dump()`` 而不是 ``model_dump(exclude_unset=True)``，
      没传的键会以 ``None`` 落进去，这一拍当场红；
    ② ``PATCH {"department": null}`` **显式**清空 ``department``——
      若实现把 ``None`` 一律当「没传」，这一拍红；
    ③ ②之后 ``name`` 仍是①改过的那个值（两拍互不干扰）。
    """
    created = client.post("/api/students", json=STUDENT_PAYLOAD)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    renamed = client.patch("/api/students/" + str(sid), json={"name": "小红"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "小红"
    assert renamed.json()["department"] == "体育学院", "没传的键被清掉了"

    cleared = client.patch("/api/students/" + str(sid), json={"department": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["department"] is None, "显式的 null 被当成了「没传」"
    assert cleared.json()["name"] == "小红"

    # 空请求体 = 什么都不改（exclude_unset 的边界档）
    noop = client.patch("/api/students/" + str(sid), json={})
    assert noop.status_code == 200, noop.text
    assert noop.json()["name"] == "小红"
    assert noop.json()["department"] is None


def test_delete_returns_204_and_the_row_is_gone(client):
    """``DELETE {path}/{pk}`` → **204** 且行真的没了。

    ⚠️ 用 ``teachers`` 而不是计划 Step 1 说的 ``semester``：``semesters`` 的
    ``on_delete`` 是 ``forbid``（读写矩阵第 1 行），它的 DELETE 端点**根本没注册**，
    打过去是 405 而不是 204。``teachers`` 是可写 + ``restrict`` + 今天没有子行，
    是「真的能删成功」那一档里最简单的一个。
    """
    created = client.post("/api/teachers", json={"staff_no": "T2025009", "name": "李老师"})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]

    deleted = client.delete("/api/teachers/" + str(tid))
    assert deleted.status_code == 204
    assert deleted.content == b""

    assert client.get("/api/teachers/" + str(tid)).status_code == 404
    # 再删一次也是 404、不是 204（幂等的语义是「这行不在了」，不是「删成功了」）
    assert client.delete("/api/teachers/" + str(tid)).status_code == 404


def test_a_readonly_resource_rejects_post_patch_delete_with_405(client, seeded):
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
    """
    pk = seeded["stratification_result"]
    assert client.get("/api/stratification-results").status_code == 200
    assert client.get("/api/stratification-results/" + str(pk)).status_code == 200

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
    assert client.get("/api/stratification-results/" + str(pk)).status_code == 200


def test_a_forbidden_delete_is_405_even_on_a_writable_resource(client, seeded):
    """``writable=True`` 且 ``on_delete="forbid"``：增改读照常，**只有 DELETE 是 405**。

    这一条与上一条守的是**两个不同的开关**：上一条是 ``writable=False``（三个写方法一起
    关掉），本条是 ``on_delete="forbid"``（只关 DELETE）。把两者合成一个开关的实现
    （例如「forbid 就顺手把 PATCH 也关了」）在这里当场红。
    """
    sid = seeded["semester"]
    assert client.get("/api/semesters").status_code == 200
    assert client.get("/api/semesters/" + str(sid)).status_code == 200
    assert client.patch("/api/semesters/" + str(sid), json={"weeks": 18}).status_code == 200
    assert client.post(
        "/api/semesters", json={**SEMESTER_PAYLOAD, "name": "2026-2027-1"}
    ).status_code == 201

    got = client.delete("/api/semesters/" + str(sid))
    assert got.status_code == 405
    assert got.json()["error"]["code"] == "http_405"
    assert client.get("/api/semesters/" + str(sid)).json()["weeks"] == 18


def test_list_omits_the_big_json_columns_but_read_one_includes_them(client, seeded):
    """``list_exclude`` 的自动探测（P3-B3）：list 不返回 ``JsonText`` 列，read-one 返回。

    ⚠️ **本条只在 ``stratification_result`` 一个资源上跑**（批次 A 的范围）；
    遍历 23 个资源的那一条是批次 B 的
    :func:`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`。
    两条刻意不合并：本条是「行为对不对」的最小可跑单元，先红先绿；那一条是覆盖面。

    **``total`` 也要一并看**：list 端点必须仍然数得到那一行，
    否则「少 select 几列」可能是靠「少返回几行」实现的。
    """
    listing = client.get("/api/stratification-results").json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert "input_snapshot" not in item
    assert item["label"] == "yellow"

    one = client.get("/api/stratification-results/" + str(seeded["stratification_result"])).json()
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


def test_all_twenty_three_resources_are_listable(client, seeded):
    """23 个路由**真的挂上了**，且每个都数得到 ``seeded`` 插进去的那一行。

    这一条是「目录 → 工厂 → 汇总路由 → ``create_app``」这条装配链的端到端冒烟：
    中间任何一环漏了（``catalog`` 少一行、``routers/__init__`` 少一次
    ``include_router``、``main.py`` 少一句），这里就以 **404** 而不是「某个资源悄悄
    不存在」的形式响。

    ``total == 1`` 对 23 个资源都成立，是因为 :func:`_seed_one_row_per_table`
    每表恰好插一行——于是这一条同时是 ``total`` 的口径守卫
    （它数的是**全表**、不是本页）。
    """
    assert len(RESOURCES) == 23
    assert tuple(spec["path"] for spec in RESOURCES) == _EXPECTED_PATHS
    for spec in RESOURCES:
        got = client.get(spec["path"])
        assert got.status_code == 200, (spec["path"], got.text)
        body = got.json()
        assert set(body) == {"items", "total", "limit", "offset"}, spec["path"]
        assert body["total"] == 1, spec["path"]
        assert len(body["items"]) == 1, spec["path"]
        assert body["items"][0]["id"] == seeded[spec["model"].__tablename__]


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


def test_the_factory_rejects_a_bad_configuration():
    """工厂体里那**六道**配置校验**真的有牙**（每一条都能被改坏到红）。

    ⚠️ 第六道（``pk_alias`` 必须是标识符）是 Plan 03 Task 4 的 P4-A6 加的，
    前五道是 Task 3 的。

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


def test_every_read_schema_covers_exactly_the_model_columns():
    """41 个模型的字段集与 DB 列集**逐字对齐（含声明顺序）**。

    两侧不同源：期望侧是 ``model.__table__.columns``（SQLAlchemy 的元数据），
    被测侧是 ``BaseModel.model_fields``（Pydantic 的元数据）。
    于是「schema 少写了一列」「多写了一列」「把列名拼错了」三种失效都会红——
    而它们是 41 个类 × 平均 9 个字段这套手写代码最可能犯的错。

    ⚠️ 顺带钉住两条形状规则：``*Create`` / ``*Update`` 的字段集 = 全部列**减去 ``id``**
    （代理键由 SQLite 给），且 ``*Update`` 的每个字段都**有缺省值**
    （PATCH 的 ``exclude_unset`` 语义要求「没传」是可表达的）。
    """
    counted = 0
    for spec in RESOURCES:
        columns = [c.name for c in spec["model"].__table__.columns]
        assert list(spec["schemas"].read.model_fields) == columns, spec["path"]
        counted += 1
        if spec["writable"]:
            without_id = [c for c in columns if c != "id"]
            assert list(spec["schemas"].create.model_fields) == without_id, spec["path"]
            assert list(spec["schemas"].update.model_fields) == without_id, spec["path"]
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
    client, seeded
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
    """
    running_total = 0
    tables_with_json = 0
    for spec in RESOURCES:
        table = spec["model"].__table__
        detected = [c.name for c in table.columns if isinstance(c.type, JsonText)]
        assert detected == _JSON_TEXT_COLUMNS.get(table.name, []), table.name
        running_total += len(detected)
        tables_with_json += bool(detected)

        listing = client.get(spec["path"]).json()
        item = listing["items"][0]
        one = client.get(spec["path"] + "/" + str(seeded[table.name])).json()

        for column in detected:
            assert column not in item, (spec["path"], column)
            assert column in one, (spec["path"], column)
        assert set(one) - set(item) == set(detected), spec["path"]
        assert set(item) == {c.name for c in table.columns} - set(detected), spec["path"]

    assert running_total == 19
    assert tables_with_json == 8


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
    assert len(Base.metadata.tables) == 25, "本条会在 metadata 没装满时空转全绿"

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


def test_a_resource_without_a_natural_key_never_returns_409(client, seeded):
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
        first = client.post(path, json=payload)
        second = client.post(path, json=payload)
        assert (first.status_code, second.status_code) == (201, 201), (
            path,
            first.text,
            second.text,
        )
        assert first.json()["id"] != second.json()["id"], path
        assert client.get(path).json()["total"] == 3, path  # seeded 1 行 + 这两行

    assert client.post("/api/notifications", json={}).status_code == 405


def test_on_delete_restrict_names_the_blocking_child_table(client, seeded):
    """``restrict`` 有子行 → **409**，消息点名**子表、那一列、几行**。

    「点名是哪张子表挡住的」是计划 Review Focus 第 4 条的落点：一句
    「删不掉」让教师无从下手，而「1 行 course_section 仍指向它」告诉他先去处理那个班。

    **红绿两档**：``seeded`` 的那个教师有一个 ``course_section`` 子行 → 409；
    现场新建、没有子行的教师 → 204。少了后一半，一个「一律 409」的实现也能全绿。
    """
    blocked = client.delete("/api/teachers/" + str(seeded["teacher"]))
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["error"]["code"] == "integrity_conflict"
    message = body["error"]["message"]
    assert "course_section" in message
    assert "teacher_id" in message
    assert "1 行" in message
    # 被挡住的那一行还在（409 不是「删了但报了个错」）
    assert client.get("/api/teachers/" + str(seeded["teacher"])).status_code == 200

    fresh = client.post("/api/teachers", json={"staff_no": "T2025077", "name": "王老师"})
    assert fresh.status_code == 201, fresh.text
    allowed = client.delete("/api/teachers/" + str(fresh.json()["id"]))
    assert allowed.status_code == 204, allowed.text


def test_on_delete_cascade_deletes_children_first(client, engine, seeded):
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
    got = client.delete("/api/class-sessions/" + str(seeded["class_session"]))
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
            "rpe_token": "ZZZ99999",
            "batch_id": seeded["daily_sync_run"],
        },
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
    assert client.delete("/api/class-sessions/" + str(other)).status_code == 204
    assert _counts() == (0, 0)


def test_the_scope_hook_rejects_a_mismatched_identity_with_403(app, engine, client, seeded):
    """``scope`` 钩子：身份与行的所有者不匹配 → **403**；且它是**可选**的。

    ⚠️ ``scope`` 在今天 23 行 ``RESOURCES`` 里**恒为 ``None``**（身份与作用域是特例端点
    的事，Task 4/5/7/8 各自负责），故它是「有能力、无生产调用方」的一档。
    本条用一个**合成的** ``ScopeFn`` 把它跑通，于是它不是死代码——
    同时钉住三件下一个人会踩的事：

    ① 挂了钩子的路由会拒（403，含「没带头」那一档）；
    ② **没挂**钩子的目录路由不要求身份（同一个 ``training_log`` 行，
      ``/api/training-logs/{id}`` 不带任何头也是 200）——否则「一律 403」也能让①绿；
    ③ 那两个身份请求头**只出现在挂了钩子的路由上**（OpenAPI 面）。
      这一格是「无条件注册依赖」那个偷懒写法的直接后果：
      23 × 3 个端点会凭空多出两个头，而 Plan 04 的前端会以为每个 CRUD 都要传身份。

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

    assert client.get("/api/training-logs/" + pk).status_code == 200

    paths = client.get("/openapi.json").json()["paths"]

    def _parameter_names(key: str) -> set[str]:
        return {
            p["name"].replace("-", "_").lower() for p in paths[key]["get"]["parameters"]
        }

    assert {"x_student_id", "x_teacher_staff_no"} <= _parameter_names(
        "/api/probe-training-logs/{probe_training_log_id}"
    )
    assert _parameter_names("/api/training-logs/{training_log_id}") == {"training_log_id"}


def test_a_value_outside_the_model_domain_is_422_not_409(client, seeded):
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

    bad = client.post(
        "/api/students",
        json={**STUDENT_PAYLOAD, "student_no": "S2025002", "sex": "unknown"},
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
    )
    assert good.status_code == 201, good.text

    patched = client.patch(
        "/api/course-sections/" + str(seeded["course_section"]),
        json={"grouping_mode": "nope"},
    )
    assert patched.status_code == 422, patched.text
    # 那一行没被改坏
    assert (
        client.get("/api/course-sections/" + str(seeded["course_section"]))
        .json()["grouping_mode"]
        == "administrative"
    )


def test_every_table_has_a_single_column_primary_key():
    """:func:`app.api.crud._purge_where` 的**前提**：25 张表的主键都是单列 ``id``。

    那个函数用 ``next(iter(table.primary_key.columns))`` 取主键列，
    复合主键会让它**静默只按第一列删**（删多了，而且不报错）——
    正是「一个假设没人看着」的形状。故把假设写成守卫。

    ⚠️ 它也顺带是 :func:`app.api.crud.build_crud_router` 的 ``pk: str = "id"``
    那个缺省值的前提：路径参数标注成 ``int``，而 25 张表的主键都是 INTEGER。
    """
    assert len(Base.metadata.tables) == 25
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

    ⚠️ 23 行 ``RESOURCES`` **没有一行**用它（实测：``'list_exclude' in spec`` 的行数是 0），
    故它是「许可而不是断言」的一档；存在的理由是「list 端点确实要返回某个小 JSON 列」
    这个将来的例外。本条让它不是死代码。

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

