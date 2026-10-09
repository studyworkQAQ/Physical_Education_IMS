"""泛型 CRUD 工厂（:mod:`app.api.crud`）与 :mod:`app.api.routers.catalog` 的 23 个资源。

**本文件分两批**，与两个 commit 对应：

* **批次 A**——计划 Step 1 点名的那些，用 ``semester``（最简单的可写资源）、``teacher``
  （可写 + ``restrict`` + 无子行，故 DELETE 真的能 204）与 ``stratification_result``
  （只读 + 带一个 ``JsonText`` 列）把五个端点跑通；
* **批次 B**——遍历型守卫：23 行 ``RESOURCES`` 的计数、import 路径（P3-B1）、自然键
  （P3-B2）、``list_exclude`` 的自动探测（P3-B3）、``_child_tables`` 对
  ``SET NULL``/``CASCADE`` 的排除（P3-B4）、409 消息不含字面 ``"None"``（P3-B5）。

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
import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    # 撞键的那一次**没有**改到已有行（upsert 会 setattr，故必须回滚）
    rows = client.get("/api/semesters").json()
    assert rows["total"] == 1


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
