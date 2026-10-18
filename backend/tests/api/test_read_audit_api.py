"""**敏感读留痕**的守卫（Plan 08 Task 1）。

派单 §2 第 10 条点名了**六条**，本文件逐条落地、并各加一条「它有牙」的取证：

========  ====================================================================  ==========================
派单        守卫                                                                   它挡的失效形态
========  ====================================================================  ==========================
①②④     :func:`test_every_sensitive_read_leaves_exactly_one_row_and_every_routine_read_leaves_none`
                                                                                 漏记 / 多记 / 一次请求落成 N 行
③          :func:`test_an_anonymous_sensitive_read_leaves_no_row`                 匿名读被记成一行无主的
⑤          :func:`test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either`
                                                                                 请求体 / 查询串落进读审计
⑥          :func:`test_the_three_mutations_of_the_read_audit_predicate_are_caught`
                                                                                 判据被改窄 / 清单落后于路由 /
                                                                                 ``downgrade`` 被改坏
========  ====================================================================  ==========================

⚠️ **①②④ 三条合成一条是刻意的**（派单把它们列成三格）：三格的**期望侧是同一份字面量**
（:data:`app.api.read_audit.READ_ROUTES` 的 64 个键），而**被测侧是同一次遍历**
（64 条 GET 各打一次、各查一次库）。分成三条的话，那 64 次请求要打三遍
（本条实测 64 次请求 ≈ 1.4 s，三遍就是 4 s），而三遍给出的信息**逐字相同**。
⚠️ 而「两侧不同源」那一格（派单逐字要求）**仍然成立**：期望侧读的是
:data:`app.api.read_audit.READ_ROUTES` + :data:`app.api.read_audit.READ_CLASSES`
那**两张字面量表**（⚠️ **不调** :func:`app.api.read_audit.is_sensitive_read`
去算期望值——那样就是拿被测函数自己给自己出题），
被测侧是**真发 HTTP + 真查 ``read_audit_log`` 的行数**。

--------------------------------------------------------------------------
⚠️ 本文件另有九条不在派单清单里的守卫，各挡一个具体的洞
--------------------------------------------------------------------------

* :func:`test_every_get_route_is_classified_exactly_once` —— ⚠️ **本件最重要的性质**：
  「清单不许悄悄落后于路由」。期望侧取自 ``app.openapi()["paths"]``（**活的路由**），
  被测侧是 :data:`app.api.read_audit.READ_ROUTES`（**字面量**），两侧**不同源**。
* :func:`test_the_read_predicate_is_a_single_owner_and_only_looks_at_the_route`
  —— 判据只住在一个函数里（AST：函数体里只出现那两张表的名字）。
* :func:`test_a_student_reading_his_own_file_is_recorded` 与
  :func:`test_a_teacher_reading_his_own_section_is_recorded` —— 派单 §2 第 9 条
  那个必须有裁定的问题（「自己翻自己」也记）。
* :func:`test_a_refused_read_by_an_identified_subject_is_still_recorded` ——
  **403 也记**（一个已登录的人试了一次范围外的读）。
* :func:`test_anonymous_is_structurally_impossible_in_the_subject_kind_domain`
  —— 「匿名不记」那道闸的**结构**那一半（DB CHECK 只有两档）。
* :func:`test_the_read_audit_endpoint_admits_only_an_admin` 与
  :func:`test_the_read_audit_endpoint_is_shaped_like_the_write_one` ——
  派单 §2 第 8 条那个裁定（与 ``/api/audit-logs`` 同一条口径）。
* :func:`test_reading_the_read_audit_page_adds_exactly_one_row_about_itself`
  —— 审计页自己喂自己那一格的**如实**钉住。
* :func:`test_no_read_audit_schema_mentions_a_credential_or_a_body` 与
  :func:`test_the_read_audit_module_never_reads_the_request_body` ——
  隐私纪律的**结构侧**两半（照 ``tests/api/test_audit_api.py`` 那两条的姿势，
  ⚠️ **不写第二套判据**）。
* :func:`test_the_read_audit_table_is_not_a_resource_and_has_no_write_endpoint`
  —— 读审计行不可改写（与 ``audit_log`` 同一条性质）。
* :func:`test_the_read_audit_trail_is_written_in_both_deployment_tiers`
  —— 两档部署下都工作（判据是**结构**的：本模块一次 ``os.environ`` 都不读）。
"""
from __future__ import annotations

import ast
import datetime as dt
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import read_audit as read_audit_module
from app.api.read_audit import (
    READ_CLASSES,
    READ_ROUTES,
    is_sensitive_read,
    route_of,
    student_id_of,
)
from app.api.schemas.audit import (
    ReadAuditLogFilter,
    ReadAuditLogPageRead,
    ReadAuditLogRead,
)
from app.config import BACKEND_DIR
from app.db.models.audit import READ_SUBJECT_KINDS, AuditLog, ReadAuditLog
from app.db.models.organisation import (
    CourseSection,
    Enrollment,
    Semester,
    Student,
    Teacher,
)
from app.deploy import ENV_VAR, PROD
from app.main import create_app

#: ``read_audit_log`` 的 9 列名。**字面量**（不从 ``ReadAuditLog.__table__`` 读回来）：
#: 两侧同源的话，「有人给这张表加了一列 ``body``」会让遍历自动多扫一列、
#: 于是隐私守卫**仍然绿**——而那正是它要抓的失效。
#: ⚠️ 与 ``tests/api/test_audit_api.py`` 的 :data:`EXPECTED_COLUMNS` **刻意各写一份**：
#: 两张表的九格**七格同名、各另有两格不同**（写审计 ``method`` + ``path``；
#: 读审计 ``route`` + ``student_id``），共用一份清单等于把那个差别抹掉。
EXPECTED_READ_COLUMNS = [
    "id", "at", "subject_kind", "subject_id", "staff_no",
    "route", "student_id", "status", "target",
]

#: 64 条 GET 的**归类**（记 / 不记）各自的件数。⚠️ **字面量**（不从
#: :data:`READ_CLASSES` 数回来）：两侧同源的话「把一个类从记翻成不记」
#: 会同时改掉两边、断言恒成立。⚠️ 而 46 + 18 == 64 由
#: :func:`test_every_get_route_is_classified_exactly_once` 从**活的 openapi** 那一侧钉住。
EXPECTED_SENSITIVE_COUNT = 47
EXPECTED_ROUTINE_COUNT = 18

#: 路径参数 → 一个**能过校验**的替身值。⚠️ ``{student_id}`` / ``{teacher_id}`` /
#: ``{course_section_id}`` 三格由 :func:`_url` 用夹具里的真 id 填，其余一律填 ``1``
#: （⚠️ 一个不存在的行 id 得到 **404**，而 404 **照样留痕**——判据不看响应码，
#: 逐字理由见 :class:`app.db.models.audit.ReadAuditLog` 的 ``status`` 那一列。
#: ⚠️ 于是本文件**不需要**给 13 个学生键资源各灌一行数据：那是 13 份夹具，
#: 而「留不留痕」这件事与「那一行在不在」无关）。
_PLACEHOLDER = {
    "alert_id": "1",
    "body_composition_id": "1",
    "class_session_id": "1",
    "derived_metric_id": "1",
    "enrollment_id": "1",
    "exercise_id": "1",
    "fitness_test_batch_id": "1",
    "fitness_test_result_id": "1",
    "interest_survey_id": "1",
    "mini_test_id": "1",
    "notification_id": "1",
    "percentile_snapshot_id": "1",
    "prescription_id": "1",
    "prescription_template_id": "1",
    "rpe_record_id": "1",
    "semester_id": "1",
    "stratification_result_id": "1",
    "training_log_id": "1",
    "weekly_adjustment_id": "1",
    "weekly_class_report_id": "1",
}

#: 七条**只认学生身份**的 GET（``current_student`` 那一族）：拿教职头打过去是 **401**，
#: 故遍历 64 条时要给学生头。⚠️ **字面量**，不从 ``app.openapi()`` 的 security 反推
#: （两侧同源的话「把一个学生端点改成也认教职头」会让本清单自动跟着变、
#: 而那一格恰恰是本清单要钉的）。
STUDENT_ONLY_ROUTES = frozenset({
    "/api/mini-tests/normalized/me",
    "/api/students/{student_id}/home",
    "/api/students/{student_id}/notifications",
    "/api/students/{student_id}/prescriptions/current",
    "/api/students/{student_id}/training-logs/completion-rate",
    "/api/students/{student_id}/weekly-sheet",
})

PASSWORD = "pe-demo-2025"
STUDENT_NO = "2023120001"
BIRTH = dt.date(2005, 3, 4)
STAFF_NO = "T0001"
ADMIN_NO = "T0003"


@pytest.fixture()
def people(engine):
    """一个宽学期 + 一个学生 + 一个**任教他**的教师 + 一个管理员 + 一个教学班 + 一条选课。

    ⚠️ 与 ``tests/api/test_audit_api.py`` 的 ``people`` 夹具**同形而多三样**
    （``course_section`` / ``enrollment`` / 教师的任教关系）：本文件有一条守卫要
    「教师读**自己任教班**的学生 → 200 且留一行」，而那需要
    :func:`app.api.deps.require_teaches_student` 能查到一条任教关系。
    ⚠️ 两份**刻意各写一份**（不抽公共夹具）：抽出来的唯一办法是建一个
    ``tests/`` 根 conftest，而那会给全部 31 个既有测试文件多一个导入期依赖
    （逐字理由见 ``tests/api/conftest.py`` 的模块 docstring 第二节）。
    ⚠️ 学期区间刻意宽到覆盖今天（2020–2030），故本文件不随墙钟漂。
    """
    with Session(engine) as session:
        semester = Semester(
            name="2025-2026-1", start_date=dt.date(2020, 1, 1),
            end_date=dt.date(2030, 1, 1), weeks=16, is_current=True,
        )
        session.add(semester)
        session.flush()
        student = Student(
            student_no=STUDENT_NO, name="张三", sex="male", birth=BIRTH, grade=1
        )
        teacher = Teacher(staff_no=STAFF_NO, name="李老师", role="teacher")
        admin = Teacher(staff_no=ADMIN_NO, name="王干事", role="admin")
        session.add_all([student, teacher, admin])
        session.flush()
        section = CourseSection(
            semester_id=semester.id, name="1班", grouping_mode="administrative",
            teacher_id=teacher.id,
        )
        session.add(section)
        session.flush()
        session.add(
            Enrollment(semester_id=semester.id, student_id=student.id,
                       course_section_id=section.id)
        )
        session.commit()
        return {
            "student": student.id,
            "teacher": teacher.id,
            "admin": admin.id,
            "semester": semester.id,
            "section": section.id,
        }


def _rows(engine) -> list[ReadAuditLog]:
    """``read_audit_log`` 的全部行，按 ``id`` 升序。"""
    with Session(engine) as session:
        return list(
            session.scalars(select(ReadAuditLog).order_by(ReadAuditLog.id)).all()
        )


def _count(engine) -> int:
    return len(_rows(engine))


def _url(template: str, people: dict[str, int]) -> str:
    """把一个路由模板填成一条**能过路径校验**的 URL。"""
    url = template
    for name, value in _PLACEHOLDER.items():
        url = url.replace("{" + name + "}", value)
    url = url.replace("{student_id}", str(people["student"]))
    url = url.replace("{teacher_id}", str(people["teacher"]))
    url = url.replace("{course_section_id}", str(people["section"]))
    assert "{" not in url, (template, url)
    return url


def _bind_and_login(client, kind: str, login: str) -> TestClient:
    """绑一个账号、登一次、返回**带 cookie 的那个** ``TestClient``。

    ⚠️ 与 ``tests/api/test_audit_api.py`` 的 ``_bind_student`` / ``_login`` 同一条口径：
    身份矩阵那几档一律用**真 cookie**（生产档下请求头通道被强制关，
    故 cookie 走的是与生产**同一条**判定路径）。
    """
    if kind == "student":
        got = client.post(
            "/api/auth/students/bind",
            json={"student_no": login, "birth": BIRTH.isoformat(),
                  "password": PASSWORD},
        )
    else:
        name = "李老师" if login == STAFF_NO else "王干事"
        got = client.post(
            "/api/auth/teachers/bind",
            json={"staff_no": login, "name": name, "password": PASSWORD},
        )
    assert got.status_code == 204, (got.status_code, got.text)
    session_client = TestClient(client.app)
    assert session_client.post(
        "/api/auth/login", json={"kind": kind, "login": login, "password": PASSWORD}
    ).status_code == 200
    return session_client


# ===========================================================================
# ⓪ 本件最重要的性质：清单不许悄悄落后于路由
# ===========================================================================


def test_every_get_route_is_classified_exactly_once(client):
    """**64 条 GET 逐个都被归类、且只归一次**（派单 §2 第 3 条那句 ⚠️）。

    ⚠️ 派单逐字写着「这一格是本件最重要的性质：**清单不许悄悄落后于路由**」。
    它的失效形态是**静默**的：下一个人加一个 ``GET /api/students/{id}/diagnosis``
    （一个显然敏感的读），端点照样工作、全部既有测试照样绿，
    而读审计里**一行都没有** —— 甲方问「谁翻过这一格」时库里查不到，
    而没有任何一处会响。

    ⚠️ **两侧不同源**（硬规矩 #35）：

    * 期望侧 = ``app.openapi()["paths"]`` 里**活的**那 64 个 GET 模板
      （⚠️ 用 openapi 而不是 ``app.routes``：FastAPI 0.141.1 的 ``include_router``
      是惰性的，``len(app.routes)`` 实测只有 6，按它写的守卫会假绿——
      那条警告的住址是 :mod:`app.api.routers` 的模块级注释）；
    * 被测侧 = :data:`app.api.read_audit.READ_ROUTES` 那**一张字面量表**。

    三拍，两个方向都响：

    ① **集合相等**：表里多一个不是路由的模板 → 红（报「已不存在」）；
       路由里多一个没进表的 GET → 红（报「未归类」）；
    ② **归类键都认得**：表里写了一个 :data:`READ_CLASSES` 里没有的类名 → 红；
    ③ **件数**：46 记 / 18 不记 / 合计 64（⚠️ 三个都是**字面量**，
       不从 :data:`READ_CLASSES` 数回来）。

    ⚠️ **反空转**：末拍断言 openapi 那一侧真的扫到了 ≥ 64 个 GET
    （否则「openapi 塌成一个空壳」与「全都归类好了」在断言上不可分辨）。
    """
    spec = client.get("/openapi.json").json()
    live = {
        path for path, item in spec["paths"].items() if "get" in item
    }
    assert len(live) >= 64, f"只从 openapi 扫到 {len(live)} 个 GET（契约面塌了？）"

    classified = set(READ_ROUTES)
    assert classified - live == set(), (
        f"READ_ROUTES 里有 {sorted(classified - live)} 已经不是路由了："
        "端点被删/改名之后清单没跟着改（一份过期的清单比没有清单更坏，"
        "因为它会让读的人以为那一格还在被记）"
    )
    assert live - classified == set(), (
        f"有 {sorted(live - classified)} 个 GET **没有被归类**："
        "新加了一个读端点而没进 app/api/read_audit.py 的 READ_ROUTES。"
        "⚠️ 必须**显式**回答「它算不算一次敏感读」——不回答的缺省档是「不记」，"
        "而那正是本条要消灭的静默失效"
    )

    unknown = {
        (route, key) for route, key in READ_ROUTES.items() if key not in READ_CLASSES
    }
    assert unknown == set(), f"READ_ROUTES 指向了不存在的归类：{sorted(unknown)}"

    sensitive = [r for r, k in READ_ROUTES.items() if READ_CLASSES[k].sensitive]
    assert len(sensitive) == EXPECTED_SENSITIVE_COUNT, len(sensitive)
    assert len(READ_ROUTES) - len(sensitive) == EXPECTED_ROUTINE_COUNT
    assert len(READ_ROUTES) == EXPECTED_SENSITIVE_COUNT + EXPECTED_ROUTINE_COUNT
    # ⚠️ 反空转：10 个类**每一个都有至少一行**用得上（否则「加了一个没人用的类」
    #    与「把一行的归类写错」在断言上不可分辨）。
    assert set(READ_ROUTES.values()) == set(READ_CLASSES), (
        f"没人用的归类：{sorted(set(READ_CLASSES) - set(READ_ROUTES.values()))}"
    )


def test_the_read_predicate_is_a_single_owner_and_only_looks_at_the_route():
    """**判据只住在一个函数里**（派单 §2 第 3 条：「不许每个 router 各自判」）。

    三拍（照 ``tests/api/test_audit_api.py`` 的
    :func:`~tests.api.test_audit_api.test_the_record_predicate_is_a_single_owner_and_only_looks_at_the_method`
    的姿势，⚠️ **不写第二套判据**）：

    ① **行为**：判据只看路由模板——一个敏感模板 → ``True``、一个不敏感的 → ``False``、
       一个**不在表里**的 → ``False``（缺省档，失效方向安全）；
       ⚠️ 且它对方法、身份、响应码**一律无感**（本函数的签名里根本没有那三格）；
    ② **结构**（AST）：``is_sensitive_read`` 的**函数体**里只出现那两张表的名字
       （``READ_ROUTES`` / ``READ_CLASSES``）——一旦有人往里加一个第二判据来源
       （例如一份「路径前缀白名单」），本拍会红；
    ③ **全仓没有第二处判据**：``app/api/**`` 与 ``app/db/**`` 里除
       ``read_audit.py`` 之外，**没有任何一处** import :data:`READ_ROUTES`
       （⚠️ 那一格挡的是「某个 router 自己拿那张表判一次」——派单点名不要的形状）。
    """
    assert is_sensitive_read("/api/students/{student_id}") is True
    assert is_sensitive_read("/api/students") is True
    assert is_sensitive_read("/api/health") is False
    assert is_sensitive_read("/api/auth/me") is False
    assert is_sensitive_read("/api/does-not-exist") is False

    source = (BACKEND_DIR / "app" / "api" / "read_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "READ_ROUTES"
    ]
    assert len(assignments) == 1, f"READ_ROUTES 被赋值了 {len(assignments)} 次"
    predicate = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "is_sensitive_read"
    )
    # ⚠️ **只数「不是本函数自己赋出来的」那些名字**：``is_sensitive_read`` 的函数体里
    #    有一个局部名（``key = READ_ROUTES.get(route)`` 的那个 ``key``），
    #    它是**形参/局部**、不是第二个判据来源。⚠️ 改前本拍把所有 ``ast.Name`` 都数进来，
    #    于是它红在 ``['READ_CLASSES', 'READ_ROUTES', 'key']`` 上——
    #    而那一格与「判据有没有第二个住址」毫无关系（本 Task 实测踩过一次；
    #    与 ``tests/api/test_audit_api.py`` 那条同名守卫「只扫 ``predicate.body``、
    #    不扫整个 ``FunctionDef``」是**同族**的一次误伤，⚠️ 而那一族的正确修法
    #    是**排除局部名**、不是把期望侧放宽成 ``>=``）。
    assigned = {
        node.id
        for statement in predicate.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    names = sorted({
        node.id for statement in predicate.body for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        and node.id != "route" and node.id not in assigned
    })
    assert names == ["READ_CLASSES", "READ_ROUTES"], (
        f"is_sensitive_read 里出现了第三个判据来源 {names}：记与不记只看路由模板"
        "（派单 §2 第 3 条），一份前缀白名单或一次身份判断都会让它有第二个住址"
    )

    offenders = []
    for root in ("api", "db"):
        for path in sorted((BACKEND_DIR / "app" / root).rglob("*.py")):
            if path.name == "read_audit.py":
                continue
            body = path.read_text(encoding="utf-8")
            parsed = ast.parse(body)
            for node in ast.walk(parsed):
                if isinstance(node, ast.ImportFrom) and node.module == "app.api.read_audit":
                    offenders.append(f"{path.relative_to(BACKEND_DIR)} import 了判据")
    assert offenders == [], (
        f"判据被搬去了第二个住址：{offenders}。「这一条路径算不算敏感读」只能由 "
        "app/api/read_audit.py 回答（派单 §2 第 3 条：不许每个 router 各自判）"
    )


# ===========================================================================
# ①②④ 逐条留痕 / 逐条不留痕 / 一次请求恰好一行
# ===========================================================================


def test_every_sensitive_read_leaves_exactly_one_row_and_every_routine_read_leaves_none(
    client, engine, people
):
    """派单 §2 第 10 条 ①②④：**64 条 GET 逐条打一遍**，46 记 / 18 不记 / 各恰好一行。

    ⚠️ **遍历的是 :data:`app.api.read_audit.READ_ROUTES` 的全部 64 个键**，
    而不是「挑几个代表」：派单逐字要求「每个被你归为敏感的路径都要有一拍」，
    而挑代表的失效形态是「代表都绿、而第 37 条漏了」。

    ⚠️ **两侧不同源**：期望侧是 :data:`READ_ROUTES` + :data:`READ_CLASSES`
    那两张**字面量表**（⚠️ 不调 :func:`is_sensitive_read` 去算期望值），
    被测侧是**真发 HTTP** 再**真查 ``read_audit_log`` 的行数**。

    ⚠️ **一次请求恰好一行**（``== 1``，不是 ``>= 1``；Ruling 28 的同一条口径）：
    ``>=`` 抓不到「一个请求被记了两遍」——而那正是本仓这个形状最容易出的错：
    ``current_reader`` 是 23 个资源的 list/read-one 共用的身份收口，
    若审计写在**依赖**里而不是在**中间件**里，一个既有 ``current_reader``
    又有 ``get_db`` 的端点会记两行。⚠️ 本仓的写入方只有
    :class:`app.api.read_audit.ReadAuditMiddleware` 那**一个**，故 64 条各恰好一行。

    ⚠️ **身份**：七条只认学生的端点用学生头打（:data:`STUDENT_ONLY_ROUTES`），
    其余用管理员头。⚠️ 而 ``X-Teacher-Staff-No`` 那一档的 ``subject_id`` 是 ``NULL``
    （:func:`app.api.deps.current_teacher` 的请求头那一支刻意不查 ``teacher.id``），
    故本条断言的是 ``staff_no`` 而**不是** ``subject_id``；cookie 那一档由
    :func:`test_the_read_audit_endpoint_admits_only_an_admin` 覆盖。

    ⚠️ **404 / 422 也照样一行**（判据不看响应码）：本夹具**刻意不给** 13 个学生键
    资源灌数据，故它们的成员 GET 一律 404 —— 而那一档**正是要钉的**：
    「有人拿一个不存在的 id 试读体成分」在库里有痕迹。
    """
    admin = {"X-Teacher-Staff-No": ADMIN_NO}
    student = {"X-Student-Id": str(people["student"])}

    assert _count(engine) == 0, "起手就应该是 0 行（夹具不经 HTTP）"
    sensitive_seen: list[str] = []
    routine_seen: list[str] = []
    for template in sorted(READ_ROUTES):
        headers = student if template in STUDENT_ONLY_ROUTES else admin
        before = _count(engine)
        got = client.get(_url(template, people), headers=headers)
        after = _rows(engine)
        added = len(after) - before
        if READ_CLASSES[READ_ROUTES[template]].sensitive:
            sensitive_seen.append(template)
            assert added == 1, (
                f"{template} 是敏感读而它落了 {added} 行（要恰好 1 行）；"
                f"响应码 {got.status_code}"
            )
            row = after[-1]
            assert row.route == template, (row.route, template)
            assert row.staff_no == ADMIN_NO or row.subject_id == people["student"], (
                f"{template} 那一行的主体两格都不对：{row.subject_kind} "
                f"{row.subject_id} {row.staff_no}"
            )
            assert row.status == got.status_code, (row.status, got.status_code)
        else:
            routine_seen.append(template)
            assert added == 0, (
                f"{template} 被归为**不记**而它落了 {added} 行；响应码 {got.status_code}"
            )

    # ⚠️ 反空转：两侧都真的遍历到了东西（否则「表是空的」与「全都对」不可分辨）
    assert len(sensitive_seen) == EXPECTED_SENSITIVE_COUNT, len(sensitive_seen)
    assert len(routine_seen) == EXPECTED_ROUTINE_COUNT, len(routine_seen)
    assert _count(engine) == EXPECTED_SENSITIVE_COUNT


def test_a_sensitive_read_that_names_a_student_records_that_student(
    client, engine, people
):
    """``student_id`` 那一格：**路径里有 ``{student_id}`` 时它必须被填上**。

    ⚠️ 那一格是本表存在的理由（甲方要的那一句是「谁翻过**谁的**档案」），
    而它**只在路径参数里取**（:func:`app.api.read_audit.student_id_of`）。三拍：

    ① ``/api/students/{student_id}`` → ``student_id == 那个学生``、``target`` 同值
       （⚠️ 两格同源而**刻意都留**：``target`` 答「读的是哪一行」、
       ``student_id`` 答「是哪个人」，而后者是**可查的**（有索引）、前者是字符串）；
    ② ``/api/students`` （名册，路径里**没有**那一段）→ ``student_id is None``
       —— 如实钉住「一次请求摊出 60 个人」那一档答不出「哪一个人」；
    ③ ``/api/students/abc`` （**非数字**的 id）→ 端点是 422，而读审计**仍然有一行**、
       ``target == "abc"`` 原文、``student_id is None``。
       ⚠️ 那一格是 :func:`app.api.read_audit.student_id_of` 里 ``int()`` 失败
       **降级而不丢行**的取证：转不出来的话那一行会当场抛、
       于是「有人拿一个非数字 id 试读学生档案」这件事**在读审计里消失了**。
    """
    admin = {"X-Teacher-Staff-No": ADMIN_NO}

    client.get(f"/api/students/{people['student']}", headers=admin)
    row = _rows(engine)[-1]
    assert row.route == "/api/students/{student_id}"
    assert row.student_id == people["student"], row.student_id
    assert row.target == str(people["student"]), row.target

    client.get("/api/students", headers=admin)
    row = _rows(engine)[-1]
    assert row.route == "/api/students"
    assert row.student_id is None, row.student_id
    assert row.target is None, row.target

    client.get("/api/students/abc", headers=admin)
    row = _rows(engine)[-1]
    assert row.route == "/api/students/{student_id}"
    assert row.status == 422, row.status
    assert row.target == "abc", row.target
    assert row.student_id is None, row.student_id


# ===========================================================================
# ③ 匿名读一律不记
# ===========================================================================


def test_an_anonymous_sensitive_read_leaves_no_row(client, engine, people):
    """派单 §2 第 10 条 ③：**匿名读不留痕**（而那一格要有裁定并被钉住）。

    ⚠️ **裁定**：匿名读**不记**，三条理由逐字住在 :mod:`app.api.read_audit`
    的模块 docstring 第 3 节（一句话：本表存在的理由是答「**谁**翻过谁的档案」，
    而一行 ``anonymous`` 答不出「谁」；⚠️ 且今天这一档在 46 个敏感读上**不可达**
    ——它们全部要身份，匿名一律 401）。

    ⚠️ 三拍：① 一个**敏感**的匿名读 → **401** 且**0 行**（实测确认派单那半句
    「匿名会 401 ⇒ 那一格应当不留痕」）；② 一个**不敏感**的匿名读 → 200 且 0 行
    （⚠️ 红绿两侧都要在场，硬规矩 #50：少了本拍，「中间件压根没挂上」
    也会让 ① 全绿）；③ ``read_audit_log`` **整表 0 行**（不是「没有新增」）。
    """
    assert _count(engine) == 0

    got = client.get("/api/students")
    assert got.status_code == 401, got.status_code
    assert _count(engine) == 0, [
        (r.route, r.subject_kind, r.status) for r in _rows(engine)
    ]

    # ② 红绿两侧：一个不敏感的匿名读**确实通了**（证明中间件在跑、库可写）
    ok = client.get("/api/health")
    assert ok.status_code == 200, ok.status_code
    assert _count(engine) == 0

    # ③ 整表 0 行
    assert _rows(engine) == []


def test_anonymous_is_structurally_impossible_in_the_subject_kind_domain():
    """「匿名不记」那道闸的**结构**那一半：``subject_kind`` 的取值域**只有两档**。

    ⚠️ 与「``audit_log`` 没有能装请求体的列」同一个形状：把一件事做成**结构性质**
    而不是「中间件里克制住不写」。于是下一个人若把判据放宽到「匿名也记」，
    他会先撞上一条 ``IntegrityError``（DB 的 ``ck_read_audit_log_subject_kind``
    拒收 ``'anonymous'``），而不是静默地灌一批无主的行。

    三拍：① 模型类常量是**两档**、且**不含** ``anonymous``；
    ② DB 的 CHECK 约束文本里**没有** ``anonymous``（⚠️ 从 DDL 读回来，
    不从类常量推——两侧同源的话「改了类常量忘了改约束」抓不到）；
    ③ ⚠️ 与 :attr:`AuditLog.SUBJECT_KINDS`（**三档**）**刻意不同**，
    故本条同时钉住「两张表的取值域不是一份词表的两个名字」。
    """
    assert READ_SUBJECT_KINDS == {"student", "teacher"}, READ_SUBJECT_KINDS
    assert ReadAuditLog.SUBJECT_KINDS == {"student", "teacher"}
    assert "anonymous" not in ReadAuditLog.SUBJECT_KINDS

    checks = [
        constraint
        for constraint in ReadAuditLog.__table__.constraints
        if constraint.name == "ck_read_audit_log_subject_kind"
    ]
    assert len(checks) == 1, [c.name for c in ReadAuditLog.__table__.constraints]
    clause = str(checks[0].sqltext)
    assert "anonymous" not in clause, clause
    assert "'student'" in clause and "'teacher'" in clause, clause

    assert AuditLog.SUBJECT_KINDS == {"student", "teacher", "anonymous"}
    assert AuditLog.SUBJECT_KINDS - ReadAuditLog.SUBJECT_KINDS == {"anonymous"}


def test_a_refused_read_by_an_identified_subject_is_still_recorded(
    client, engine, people
):
    """**403 也记**：一个已登录的人试了一次他范围外的读，那一格要留痕。

    ⚠️ 判据是「敏感路径 **+ 有名字的主体**」，**不看响应码**
    （逐字理由见 :class:`app.db.models.audit.ReadAuditLog` 的 ``status`` 那一列）。
    于是本条钉的是那个裁定的**行为**：

    * 教师 **T0001** 读**自己任教班**的学生 → **200** 且一行（下面那一条守卫）；
    * 学生读**别人**的档案 → **403** 且**一行**（本条），``status == 403``。

    ⚠️ **为什么要记 403**：它是「有人在探边界」的唯一可见性——
    :func:`app.api.deps.require_scope` 那一族**故意不回显**「你差在哪」
    （回显就是一个枚举信号），故没有本表的话一次越权探测在系统里**没有任何痕迹**。
    ⚠️ 而它与「匿名不记」**不矛盾**：那一档没有名字，本档有。

    ⚠️ 本条用**真 cookie**（学生登录一次），不用请求头：生产档下请求头通道被强制关，
    而 ``require_scope`` 的 403 那一支要的是**会话**里那个 ``subject_id``。
    """
    student = _bind_and_login(client, "student", STUDENT_NO)
    other = people["student"] + 1  # ⚠️ 一个不在册的 id：require_scope 的第二支 → 403

    got = student.get(f"/api/students/{other}/home")
    assert got.status_code == 403, (got.status_code, got.text)

    rows = _rows(engine)
    assert len(rows) == 1, [(r.route, r.status) for r in rows]
    row = rows[0]
    assert row.route == "/api/students/{student_id}/home"
    assert row.status == 403, row.status
    assert row.subject_kind == "student", row.subject_kind
    assert row.subject_id == people["student"], row.subject_id
    assert row.student_id == other, row.student_id


# ===========================================================================
# 派单 §2 第 9 条：「自己翻自己」也记
# ===========================================================================


def test_a_student_reading_his_own_file_is_recorded(client, engine, people):
    """**裁定：学生读自己的档案也记**（派单 §2 第 9 条，控制者裁定、实现者复核同意）。

    ⚠️ 三条理由逐字住在 :mod:`app.api.read_audit` 的模块 docstring 第 4 节
    （一句话：判据里**刻意没有**「是不是自己」这一维，而「自己翻自己」是一格真事实，
    且它恰恰是抢绑那一族要看的线索）。⚠️ 裁定要写进**代码注释与 spec**
    ——代码那一半在 :mod:`app.api.read_audit` 的模块 docstring 第 4 节，
    spec 那一半在 §13.9。

    三拍（⚠️ 用**真 cookie**）：① 学生读**自己**的首页 → **200** 且**恰好一行**；
    ② 那一行的 ``subject_kind == 'student'``、``subject_id`` == 他自己、
    ``student_id`` **也**是他自己（⚠️ 两格同值不是冗余：前者答「谁翻的」、
    后者答「翻的谁的档案」，而「两格相同」正是「自己翻自己」的可查询形状）；
    ③ ⚠️ 反空转：那一行**确实**是这次请求产生的（``id`` 递增、``route`` 对得上）。
    """
    student = _bind_and_login(client, "student", STUDENT_NO)
    assert _count(engine) == 0

    got = student.get(f"/api/students/{people['student']}/home")
    assert got.status_code == 200, (got.status_code, got.text)

    rows = _rows(engine)
    assert len(rows) == 1, [(r.route, r.status) for r in rows]
    row = rows[0]
    assert row.route == "/api/students/{student_id}/home"
    assert row.status == 200
    assert row.subject_kind == "student", row.subject_kind
    assert row.subject_id == people["student"], row.subject_id
    assert row.student_id == people["student"], row.student_id
    assert row.staff_no is None, row.staff_no


def test_a_teacher_reading_his_own_section_is_recorded(client, engine, people):
    """**裁定：教师读自己任教班的学生也记**（派单 §2 第 9 条的另一半）。

    ⚠️ 与上一条同一条裁定，而它**另有**一格价值：本仓自 Plan 06 Task 8 起
    教师只能读自己任教班的学生（:data:`app.api.crud.READ_SCOPE_STAFF_TAUGHT`），
    于是「教师翻了**自己班上**学生的档案」今天是一次**完全合法、且不会响**的动作
    ——而它恰恰是甲方最可能问的那一格（「陈老师有没有翻过赵锦程的体成分」）。
    合法不等于不该留痕。

    三拍（⚠️ 用**真 cookie**，故 ``subject_id`` 有值）：
    ① 教师读**自己任教班**那个学生的首页 → **200** 且**恰好一行**；
    ② 那一行 ``subject_kind == 'teacher'``、``subject_id`` == 他的 ``teacher.id``、
    ``staff_no`` == 工号、``student_id`` == 那个学生；
    ③ ⚠️ 红绿两侧：同一位教师读**别人班**的学生 → **403**，而那一档**也有一行**
    （由 :func:`test_a_refused_read_by_an_identified_subject_is_still_recorded`
    那一条钉住学生侧；本拍钉教师侧）。
    """
    teacher = _bind_and_login(client, "teacher", STAFF_NO)
    assert _count(engine) == 0

    got = teacher.get(f"/api/teacher/students/{people['student']}/home")
    assert got.status_code == 200, (got.status_code, got.text)

    rows = _rows(engine)
    assert len(rows) == 1, [(r.route, r.status) for r in rows]
    row = rows[0]
    assert row.route == "/api/teacher/students/{student_id}/home"
    assert row.subject_kind == "teacher", row.subject_kind
    assert row.subject_id == people["teacher"], row.subject_id
    assert row.staff_no == STAFF_NO, row.staff_no
    assert row.student_id == people["student"], row.student_id

    # ③ 教师读一个**不在他班上**的学生 → 403，而那一档也留一行
    outsider = people["student"] + 1
    refused = teacher.get(f"/api/teacher/students/{outsider}/home")
    assert refused.status_code == 403, (refused.status_code, refused.text)
    after = _rows(engine)
    assert len(after) == 2, [(r.route, r.status) for r in after]
    assert after[-1].status == 403 and after[-1].student_id == outsider


# ===========================================================================
# ⑤ 永不落请求体（也永不落查询串）
# ===========================================================================


def test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either(
    client, engine, people
):
    """派单 §2 第 6 条：**对已知反例验证**——真发一次带体 + 带探针查询串的敏感读，
    然后把落库那一行的**全部 9 列**逐列扫一遍。

    ⚠️ 取证姿势与 ``tests/api/test_audit_api.py`` 的
    ``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
    **逐字同款**（派单 §2 第 6 条逐字要求「照既有那条守卫的姿势，不要写第二套判据」）：
    不是「我看代码里没有 ``body`` 这一列」，而是**真发一次请求、真读回那一行、
    真把 9 列逐列扫一遍**。

    ⚠️ **读审计比写审计多扫一格：查询串**。``audit_log.path`` 存的是
    ``request.url.path``（**不含**查询串，故那一格是「不存」），而本表存的是
    **路由模板**，故查询串连「有机会被存」的位置都没有 —— 本条把那一格钉成实测：
    一个 ``?PROBE_QS=<串>`` 打在敏感读上，落库那 9 列里**一个字符都不出现**。
    ⚠️ 而 GET 带请求体虽然不常见，**HTTP 上合法**（``TestClient`` 也支持），
    故一并扫。

    ⚠️ **反空转**：末两拍断言两个探针串**确实被发出去了**
    （``request.url.query`` 里在）—— 少了它，「探针压根没进请求」与
    「探针进了请求而没落库」在断言上不可分辨。
    """
    probe_body = "PROBE-BODY-pe-demo-2025"
    probe_query = "PROBE-QS-2005-03-04"
    admin = {"X-Teacher-Staff-No": ADMIN_NO}

    got = client.request(
        "GET",
        f"/api/students/{people['student']}?note={probe_query}",
        headers=admin,
        content=probe_body.encode("utf-8"),
    )
    assert got.status_code == 200, (got.status_code, got.text)

    rows = _rows(engine)
    assert len(rows) == 1, [(r.route, r.status) for r in rows]
    row = rows[0]

    # ⚠️ 反空转的第一半：查询串**确实**到了服务端（否则本条是空转全绿）
    assert probe_query in str(got.request.url), got.request.url
    assert probe_body in got.request.read().decode("utf-8")

    # 9 列逐列扫（⚠️ 列名取自 :data:`EXPECTED_READ_COLUMNS` 那份**字面量**，
    #    不从模型读回来：两侧同源的话「加一列 body」会让遍历自动多扫一列、守卫仍绿）
    assert sorted(EXPECTED_READ_COLUMNS) == sorted(
        column.name for column in ReadAuditLog.__table__.columns
    ), "表的列变了：隐私守卫的覆盖面必须先跟着改（本条扫的是字面量那 9 列）"
    for column in EXPECTED_READ_COLUMNS:
        value = getattr(row, column)
        rendered = "" if value is None else str(value)
        for needle in (probe_body, probe_query, "PROBE", PASSWORD, "2005-03-04"):
            assert needle not in rendered, (
                f"读审计的 {column} 那一列里出现了 {needle!r}：{rendered!r}"
            )
    assert row.route == "/api/students/{student_id}", row.route


def test_no_read_audit_schema_mentions_a_credential_or_a_body():
    """**结构侧**的另一半：三个契约模型的字段名里不出现凭据、「体」或「查询串」。

    ⚠️ 与 ``tests/api/test_audit_api.py`` 的
    ``test_no_audit_schema_mentions_a_credential_or_a_body`` **逐字同款**
    （派单 §2 第 6 条：照既有那条守卫的姿势）。⚠️ 两条**刻意不合并**：
    它们的**修法不同**（一条要删写审计的字段、一条要删读审计的），
    报错因此指向真因。

    ⚠️ 判据是**子串**而不是相等：``password_hash`` / ``request_body`` /
    ``birth_date`` / ``query_string`` 都要被抓到，而 ``student_id`` / ``staff_no``
    一类不会误伤。
    """
    forbidden = (
        "password", "birth", "body", "secret", "credential", "token", "query",
    )
    offenders: list[str] = []
    for model in (ReadAuditLogRead, ReadAuditLogPageRead, ReadAuditLogFilter):
        for name in model.model_fields:
            lowered = name.lower()
            for needle in forbidden:
                if needle in lowered:
                    offenders.append(f"{model.__name__}.{name} 含 {needle!r}")
    assert offenders == [], (
        "读审计的 HTTP 契约里出现了凭据/请求体/查询串字段：\n  " + "\n  ".join(offenders)
    )

    # ⚠️ 反空转：三个模型**确实**有字段（否则上面那个循环空转全绿）。
    assert len(ReadAuditLogRead.model_fields) == 9, sorted(ReadAuditLogRead.model_fields)
    assert sorted(ReadAuditLogRead.model_fields) == sorted(EXPECTED_READ_COLUMNS), (
        "读模型的 9 格必须与表的 9 列一一对应：多一格就是一个「现算/回查」出来的字段，"
        "少一格就是前端拿不到它要显示的东西"
    )
    assert sorted(ReadAuditLogPageRead.model_fields) == ["items", "limit", "offset", "total"]
    assert sorted(ReadAuditLogFilter.model_fields) == ["student_id", "subject_kind"]


def test_the_read_audit_module_never_reads_the_request_body():
    """**结构侧**：``app/api/read_audit.py`` 里没有任何读请求体的调用。

    ⚠️ 与 ``tests/api/test_audit_api.py`` 的
    ``test_the_audit_module_never_reads_the_request_body`` **逐字同款**
    （AST 判 ``node.attr``，不是文本搜索——文本搜索会把 docstring 里的**提及**
    当成**本身**，硬规矩 #109；⚠️ 而本模块的 docstring 里恰好就有那个提及）。

    ⚠️ 这一半**不只是**隐私问题：``BaseHTTPMiddleware`` 下读掉请求体会让下游端点
    拿不到它（除非用 Starlette 的 ``_CachedRequest`` 重放），故「不读体」同时是一条
    **正确性**纪律。⚠️ 而对 GET 而言它还有第三格意义：一个 ``await request.body()``
    会让**每一个** GET 都多一次流消费，包括那 18 条不记的。
    """
    source = (BACKEND_DIR / "app" / "api" / "read_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = [
        f"{node.lineno}: .{node.attr}()"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in ("body", "json", "form", "stream")
    ]
    assert offenders == [], (
        f"app/api/read_audit.py 读了请求体：{offenders}。读审计只记 "
        "route/student_id/status/subject/target 那几格，而查询串与请求体都是"
        "客户端可控的自由文本"
    )
    # ⚠️ 反空转：本文件确实被解析出了东西（指错路径时 ast.parse 会抛，故这一拍
    #    挡的是「有人把中间件搬到别的文件、而本守卫仍然读旧路径」那一档）
    names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert {"is_sensitive_read", "route_of", "student_id_of", "record_read",
            "ReadAuditMiddleware", "install_read_audit"} <= names, sorted(names)
    assert pathlib.Path(BACKEND_DIR, "app", "api", "read_audit.py").is_file()
    # ⚠️ 第三拍：本模块**一个环境变量都不读**（故 ``PE_ENV`` 影响不了它）
    assert "os.environ" not in source and "getenv" not in source, (
        "app/api/read_audit.py 读了一个环境变量：「记不记、记什么」不该随部署档位变"
    )


# ===========================================================================
# 读端点：与 /api/audit-logs 同一条口径
# ===========================================================================


def test_the_read_audit_endpoint_admits_only_an_admin(client, engine, people):
    """派单 §2 第 8 条的裁定：**与既有 ``/api/audit-logs`` 同一条口径**（仅 ``role='admin'``）。

    ⚠️ 四档一律用**真 cookie**，与 ``tests/api/test_audit_api.py`` 的
    ``test_the_audit_endpoint_admits_only_an_admin`` **逐字同款**
    （生产档下 ``PE_ALLOW_HEADER_IDENTITY`` 被强制关，故 cookie 走的是与生产
    同一条判定路径）。⚠️ 而**两个端点的矩阵必须逐字相同**：本条同时打
    ``/api/audit-logs``，于是「读审计的权限面比写审计宽」这件事**当场红**。

    ============  ======  ======================================
    调用方          码      由谁给出
    ============  ======  ======================================
    匿名          **401**  :func:`app.api.deps.current_teacher`
    学生（cookie）**403**  同上（「一个学生的 cookie 不能当教师用」）
    教师（在册）   **403**  :func:`app.api.deps.require_admin`
    管理员        **200**  ——
    ============  ======  ======================================
    """
    admin = _bind_and_login(client, "teacher", ADMIN_NO)
    teacher = _bind_and_login(client, "teacher", STAFF_NO)
    student = _bind_and_login(client, "student", STUDENT_NO)
    anonymous = TestClient(client.app)

    for endpoint in ("/api/read-audit-logs", "/api/audit-logs"):
        matrix = {
            "管理员": admin.get(endpoint).status_code,
            "普通教师": teacher.get(endpoint).status_code,
            "学生": student.get(endpoint).status_code,
            "匿名": anonymous.get(endpoint).status_code,
        }
        assert matrix == {"管理员": 200, "普通教师": 403, "学生": 403, "匿名": 401}, (
            endpoint, matrix
        )

    # ⚠️ 反假绿：200 那一档**真的有内容**（四个信封键、``items`` 是一串读审计行）
    body = admin.get("/api/read-audit-logs").json()
    assert sorted(body) == ["items", "limit", "offset", "total"], sorted(body)
    assert body["total"] > 0, body
    assert body["items"][0]["subject_kind"] in ReadAuditLog.SUBJECT_KINDS


def test_the_read_audit_endpoint_is_shaped_like_the_write_one(client, engine, people):
    """**两个端点逐格同形**（派单 §2 第 8 条那句「同一条口径」的可执行形式）。

    四拍：① 四个信封键**逐字相同**；② ``items`` 都按 **``id DESC``**（最新在前）；
    ③ ``total`` 与 ``items`` 走**同一个 ``WHERE``**（过滤之后两格一起变）；
    ④ 过滤参数的取值域**不同**（``subject_kind=anonymous`` 在写审计是 200 + 0 行、
    在读审计是 **422**）——⚠️ 那一格是**要的**，逐字理由见
    :class:`app.api.schemas.audit.ReadAuditLogFilter`。

    ⚠️ 用**真 cookie** 的管理员（与上一条同一个理由）。
    """
    admin = _bind_and_login(client, "teacher", ADMIN_NO)
    # 造三行读审计：两行教师读、一行学生读
    teacher_headers = {"X-Teacher-Staff-No": ADMIN_NO}
    client.get(f"/api/students/{people['student']}", headers=teacher_headers)
    client.get("/api/students", headers=teacher_headers)
    student = _bind_and_login(client, "student", STUDENT_NO)
    student.get(f"/api/students/{people['student']}/home")

    write_page = admin.get("/api/audit-logs").json()
    read_page = admin.get("/api/read-audit-logs").json()

    # ① 信封
    assert sorted(read_page) == sorted(write_page) == ["items", "limit", "offset", "total"]

    # ② id DESC（最新在前）
    ids = [item["id"] for item in read_page["items"]]
    assert ids == sorted(ids, reverse=True), ids
    assert len(ids) >= 3, ids

    # ③ total 与 items 走同一个 WHERE
    filtered = admin.get(
        "/api/read-audit-logs", params={"student_id": people["student"]}
    ).json()
    assert filtered["total"] < read_page["total"], (filtered["total"], read_page["total"])
    assert len(filtered["items"]) == filtered["total"] or filtered["total"] > 200
    assert all(
        item["student_id"] == people["student"] for item in filtered["items"]
    ), filtered["items"][:3]

    # ④ 取值域不同：anonymous 在写审计是 200、在读审计是 422
    assert admin.get("/api/audit-logs", params={"subject_kind": "anonymous"}).status_code == 200
    refused = admin.get("/api/read-audit-logs", params={"subject_kind": "anonymous"})
    assert refused.status_code == 422, (refused.status_code, refused.text)
    assert refused.json()["error"]["code"] == "unprocessable_value", refused.json()


def test_reading_the_read_audit_page_adds_exactly_one_row_about_itself(
    client, engine, people
):
    """⚠️ **如实钉住**：读审计页**自己喂自己**（一次翻页 = 一行「有人翻了读审计」）。

    ⚠️ 那一格与 ``audit_log`` **相反**（写审计页不产生任何行，因为
    :func:`app.api.audit.should_record` 只认三个写方法），而它是**要的**：
    「谁看过审计」正是 :data:`app.api.read_audit.READ_CLASSES` 里 ``AUDIT_TRAIL``
    那一类存在的理由（它兑现的是 :mod:`app.api.audit` 与
    :mod:`app.api.routers.audit` 两处**如实记下**的代价）。

    ⚠️ **恰好一行**（不是「至少一行」）：本条同时是派单 §2 第 10 条 ④
    「一次请求只落一行」在**这一个**端点上的取证。

    ⚠️ **有界**（如实记）：只有 ``role='admin'`` 打得到本端点，故增长速率是
    「一个教务干事翻几页」，不是「60 个学生各翻一屏」；处置是 Task 2 的
    90 天留存窗口（计划 §2）。
    """
    admin = _bind_and_login(client, "teacher", ADMIN_NO)
    before = _count(engine)

    got = admin.get("/api/read-audit-logs")
    assert got.status_code == 200, got.text

    after = _rows(engine)
    assert len(after) - before == 1, [(r.route, r.status) for r in after[before:]]
    row = after[-1]
    assert row.route == "/api/read-audit-logs", row.route
    assert row.subject_kind == "teacher" and row.staff_no == ADMIN_NO
    assert row.student_id is None, row.student_id

    # ⚠️ 红绿两侧：翻**第二页**再加一行（不是「只记第一次」）
    admin.get("/api/read-audit-logs", params={"offset": 0, "limit": 1})
    assert _count(engine) - before == 2


def test_the_read_audit_table_is_not_a_resource_and_has_no_write_endpoint(client, engine):
    """读审计行**不可改写**（与 ``audit_log`` 同一条性质），且它**不是**第 24 个资源。

    三拍：① ``POST`` / ``PATCH`` / ``DELETE`` 打 ``/api/read-audit-logs`` 一律 **405**
    （⚠️ 不是 404：路径存在、只是那些方法没注册——404 会把「端点没挂上」
    与「写端点被删了」混成一档）；② 它**不在** :data:`app.api.routers.catalog.RESOURCES`
    的 23 行里（``read_audit_log`` 不是任何一行的 ``model``）；
    ③ 全仓**没有任何一处** ``UPDATE`` / ``DELETE`` 这张表
    （AST 扫 ``app/**``：``ReadAuditLog`` 只出现在 ``select`` / ``insert`` 那一侧）。
    """
    for method in ("post", "patch", "delete"):
        got = getattr(client, method)("/api/read-audit-logs")
        assert got.status_code == 405, (method, got.status_code, got.text)

    from app.api.routers.catalog import RESOURCES

    assert all(
        entry["model"].__tablename__ != "read_audit_log" for entry in RESOURCES
    ), "read_audit_log 被塞进了那 23 行资源目录（派单 §2 第 8 条裁定它是特例端点）"
    assert len(RESOURCES) == 23, len(RESOURCES)

    offenders = []
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("update", "delete")
                and any(
                    isinstance(arg, ast.Name) and arg.id == "ReadAuditLog"
                    for arg in node.args
                )
            ):
                offenders.append(f"{path.relative_to(BACKEND_DIR)}:{node.lineno}")
    assert offenders == [], (
        f"有人改/删读审计行：{offenders}。不可改写是审计的第一条性质"
    )


# ===========================================================================
# 两档部署
# ===========================================================================


def test_the_read_audit_trail_is_written_in_both_deployment_tiers(monkeypatch, tmp_path):
    """**两档部署下都工作**（照 ``tests/api/test_audit_api.py`` 的同名那条的姿势）。

    ⚠️ 判据是**结构**的：``app/api/read_audit.py`` 里一次 ``os.environ`` 都没有
    （由 :func:`test_the_read_audit_module_never_reads_the_request_body` 的末拍钉住），
    故 ``PE_ENV`` **不可能**影响它；本条再各档**实发一次请求**核对。

    ⚠️ 两档各起一个**独立的磁盘库**（``tmp_path``），故本条顺带是
    「迁移 5 在一个真磁盘库上跑得通、且跑完之后读审计真的写得进去」的取证
    （内存库那一档走 ``create_all``，碰不到迁移链）。

    ⚠️⚠️ **两档一律用真 cookie、且 ``base_url`` 一律是 ``https://``**（本 Task 实测出来的
    一格，与写审计那条同名守卫**刻意不同形**）：

    * 写审计那一条打的是**匿名 POST → 401**，而 401 **照样留痕**（``anonymous`` 那一档），
      故它两档都不需要身份；
    * 本表**不记匿名**（:func:`test_an_anonymous_sensitive_read_leaves_no_row`），
      故本条**必须**先登录。而 ``PE_ALLOW_HEADER_IDENTITY=1`` 在 ``prod`` 下被
      :func:`app.api.deps.allow_header_identity` **强制忽略**（实测：请求头那一档
      在 prod 上是 401），于是只剩 cookie 一条通道；
    * ⚠️ 而 prod 下 cookie 带 ``Secure``（:func:`app.auth.sessions.cookie_secure`），
      ``TestClient`` 缺省的 ``http://testserver`` **不会把 Secure cookie 发回去**
      （httpx 的 cookie jar 按 scheme 判）⇒ 两档一律用 ``https://testserver``。
      ⚠️ 那一格对 dev 也成立（``Secure=False`` 的 cookie 在 https 上照样发），
      故两档**同一份代码**，「两档逐字相同」这句话才是真的在比两档。
    * ⚠️ ``PE_CORS_ORIGINS`` 刻意**不设**（与写审计那条同一个理由）：
      不设 = 不挂 CORSMiddleware = 拒绝跨域，正是同源部署要的形状，
      也让 :func:`app.main._selfcheck_prod` 无 offender ——
      于是本条**顺带**证明「多挂一层读审计中间件」不会让生产档的启动自检响。
    """
    results = {}
    for tier in ("dev", PROD):
        monkeypatch.setenv(ENV_VAR, tier)
        db = tmp_path / f"tier-{tier}.db"
        application = create_app(db_url="sqlite:///" + db.as_posix())
        with TestClient(application, base_url="https://testserver") as tier_client:
            with Session(application.state.engine) as session:
                session.add(
                    Semester(
                        name="2025-2026-1", start_date=dt.date(2020, 1, 1),
                        end_date=dt.date(2030, 1, 1), weeks=16, is_current=True,
                    )
                )
                session.add(Teacher(staff_no=ADMIN_NO, name="王干事", role="admin"))
                session.commit()
            bound = tier_client.post(
                "/api/auth/teachers/bind",
                json={"staff_no": ADMIN_NO, "name": "王干事", "password": PASSWORD},
            )
            assert bound.status_code == 204, (tier, bound.status_code, bound.text)
            logged = tier_client.post(
                "/api/auth/login",
                json={"kind": "teacher", "login": ADMIN_NO, "password": PASSWORD},
            )
            assert logged.status_code == 200, (tier, logged.status_code, logged.text)
            got = tier_client.get("/api/students")
            assert got.status_code == 200, (tier, got.status_code, got.text)
            with Session(application.state.engine) as session:
                rows = list(session.scalars(select(ReadAuditLog)).all())
            # ⚠️ 只挑那一条敏感读的行：登录与绑定是 POST，它们**不进本表**
            #    （而那一格本身由下面那句 ``len(...) == 1`` 钉住）。
            results[tier] = [
                (r.route, r.subject_kind, r.status)
                for r in rows
                if r.route == "/api/students"
            ]
            assert len(rows) == 1, (
                tier, [(r.route, r.status) for r in rows],
                "两个 POST（bind / login）不该出现在读审计里：本表只装 GET",
            )
        application.state.engine.dispose()

    assert results["dev"] == results[PROD] == [
        ("/api/students", "teacher", 200)
    ], results


# ===========================================================================
# ⑥ 定点变异
# ===========================================================================


def test_the_three_mutations_of_the_read_audit_predicate_are_caught(
    client, engine, people, monkeypatch, tmp_path
):
    """派单 §2 第 10 条 ⑥：**三个定点变异都要让上面的守卫红**。

    ⚠️ 三个变异都打在**真代码路径**上（不是「我另写了一个判定」）：

    * **变异 A（把敏感清单去掉一条）**：把 ``STUDENT_ROSTER`` 那一类翻成
      ``sensitive=False`` → ``/api/students`` 不再留痕 →
      :func:`test_every_sensitive_read_leaves_exactly_one_row_and_every_routine_read_leaves_none`
      会红在它那个 ``added == 1`` 上。⚠️ 本拍**真的跑一遍**那个断言的核，
      证明它有牙。
    * **变异 B（把「新增读端点未归类就红」那条守卫的判据放宽）**：
      往 :data:`READ_ROUTES` 里塞一个**不是路由**的模板 →
      :func:`test_every_get_route_is_classified_exactly_once` 会红在
      「已不是路由」那一拍上。⚠️ 而反向那一档（**删掉**一个真路由的键）
      也一并跑：它会红在「没有被归类」那一拍上。
    * **变异 C（把 ``downgrade`` 改坏）**：把迁移 5 的 ``downgrade`` 换成
      ``pass`` → ``tests/db/test_migration_chain.py`` 的
      :func:`~tests.db.test_migration_chain.test_the_read_audit_log_migration_round_trips_and_keeps_every_other_row`
      会红在「表还在」那一拍上。⚠️ 本拍在一个**临时迁移目录**上真跑一遍
      （同一份 DDL、同一套 alembic 机械，只改 ``downgrade`` 的函数体），
      故它证明的是那条守卫**真的有牙**，而不是「我看它会红」。
    """
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    admin = {"X-Teacher-Staff-No": ADMIN_NO}

    # ---------------------------------------------------------------- A
    mutated_classes = dict(READ_CLASSES)
    mutated_classes["STUDENT_ROSTER"] = read_audit_module.ReadClass(
        False, READ_CLASSES["STUDENT_ROSTER"].reason
    )
    monkeypatch.setattr(read_audit_module, "READ_CLASSES", mutated_classes)
    assert is_sensitive_read("/api/students") is False, "变异 A 没生效，下面那一拍是空转"
    before = _count(engine)
    got = client.get("/api/students", headers=admin)
    assert got.status_code == 200
    added = _count(engine) - before
    assert added == 0, (
        f"变异 A（把名册那一类翻成不记）之后仍然落了 {added} 行："
        "「逐条留痕」那条守卫因此**没有牙**"
    )
    # ⚠️ 而「逐条不留痕」那一拍也**同时**被它弄红：``/api/students`` 现在落在
    #    「不记」那一侧，而期望侧的字面量仍然说它「记」⇒ 两侧对不上。
    assert READ_CLASSES[READ_ROUTES["/api/students"]].sensitive is True, (
        "期望侧跟着被测侧一起变了（两侧同源）⇒ 那条守卫是恒绿的"
    )
    monkeypatch.undo()

    # ---------------------------------------------------------------- B
    live = {
        path for path, item in client.get("/openapi.json").json()["paths"].items()
        if "get" in item
    }
    too_many = dict(READ_ROUTES, **{"/api/students/{student_id}/diagnosis": "PER_STUDENT_HEALTH"})
    assert set(too_many) - live == {"/api/students/{student_id}/diagnosis"}
    too_few = {k: v for k, v in READ_ROUTES.items() if k != "/api/students"}
    assert live - set(too_few) == {"/api/students"}
    # ⚠️ 两档都**必须**被那条守卫的两个方向抓到（集合相等 = 两个方向都响）
    assert (set(too_many) - live) != set(), "变异 B 的正向那一档没造出差异，本拍空转"
    assert (live - set(too_few)) != set(), "变异 B 的反向那一档没造出差异，本拍空转"

    # ---------------------------------------------------------------- C
    migrations_src = BACKEND_DIR / "migrations"
    mutated = tmp_path / "migrations"
    mutated.parent.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copytree(migrations_src, mutated, ignore=shutil.ignore_patterns("__pycache__"))
    target = mutated / "versions" / "03331a689ee4_read_audit_log.py"
    assert target.is_file(), target
    body = target.read_text(encoding="utf-8")
    marker = "def downgrade() -> None:"
    head, _sep, _tail = body.partition(marker)
    target.write_text(
        head + marker + "\n    pass\n", encoding="utf-8", newline="\r\n"
    )

    db = tmp_path / "mutant.db"
    url = "sqlite:///" + db.as_posix()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(mutated))
    from app.db.session import DB_URL_ATTRIBUTE

    cfg.attributes[DB_URL_ATTRIBUTE] = url
    command.upgrade(cfg, "head")
    engine_c = create_engine(url)
    try:
        with engine_c.connect() as conn:
            assert conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE name='read_audit_log'")
            ).scalar() == 1
        # ⚠️ **Plan 08 Task 4 起 ``downgrade`` 的靶子从 ``"-1"`` 改成显式的
        #    ``"0ac943e0da9b"``**：链长出第六条之后，``-1`` 退的是**迁移 6**
        #    （``bind_token``），而本拍变异的是**迁移 5** 的 ``downgrade``
        #    ——用 ``-1`` 的话被变异的那个函数**根本不会被调到**，于是
        #    ``still_there == 1`` 那一拍会绿在一个「变异没生效」的形状上
        #    （⚠️ 而它下面那句「变异 C 没生效 ⇒ 本拍是空转」的断言**抓不到这一档**：
        #    它判的是「表还在」，而迁移 6 的 ``downgrade`` 本来就不删 ``read_audit_log``）。
        #    显式靶子让「退到迁移 4」这件事与本拍要变异的那条迁移**绑死**。
        command.downgrade(cfg, "0ac943e0da9b")
        with engine_c.connect() as conn:
            still_there = conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE name='read_audit_log'")
            ).scalar()
            revision = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        # ⚠️ 变异 C 的后果：alembic **以为**它退了一步（版本号真的回去了），
        #    而那张表**还在** ⇒ 守卫那一拍 ``"read_audit_log" not in tables()`` 会红。
        assert revision == "0ac943e0da9b", revision
        assert still_there == 1, (
            "变异 C 没生效（downgrade 仍然把表删了）⇒ 本拍是空转，"
            "而那条迁移守卫有没有牙就无从证明"
        )
    finally:
        engine_c.dispose()
