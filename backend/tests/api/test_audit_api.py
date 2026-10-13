"""请求审计留痕的守卫（Plan 06 Task 5）。

派单 §1 第 6 条点名了**六条**，本文件逐条落地、并各加一条「它有牙」的取证：

========  ==========================================================  ==========================
派单        守卫                                                       它挡的失效形态
========  ==========================================================  ==========================
①          :func:`test_one_login_plus_one_write_is_exactly_two_rows`   漏记 / 多记
②          :func:`test_an_anonymous_read_writes_no_audit_row`          把读也记上（体量与噪声）
③          :func:`test_a_failed_authentication_is_one_anonymous_row`   撞门查不到
④          :func:`test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`
                                                                       口令 / 出生日期落进审计
⑤          :func:`test_the_audit_endpoint_admits_only_an_admin`        审计页被教师或学生读到
⑥          :func:`test_the_two_mutations_of_the_record_predicate_are_caught`
                                                                       判据被改宽 / 改窄
========  ==========================================================  ==========================

⚠️ **④ 的取证姿势是派单逐字要求的**：「对已知反例验证：真的发一次带口令的 login，
然后查审计行的**所有列**」。故那条守卫不是「我看代码里没有 ``body`` 这一列」，
而是**真发一次请求、真读回那一行、真把 9 列逐列扫一遍**。

--------------------------------------------------------------------------
⚠️ 本文件另有五条不在派单清单里的守卫，各挡一个具体的洞
--------------------------------------------------------------------------

* :func:`test_the_audit_trail_is_written_in_both_deployment_tiers` —— 派单 §0 那条 ⚠️
  （「审计与备份在两档下都要工作」）。判据是**结构**的：``app/api/audit.py`` 里
  一次 ``os.environ`` 都没有，故 ``PE_ENV`` 不可能影响它；再各档实发一次请求核对。
* :func:`test_the_target_column_comes_from_the_path_and_never_from_the_response_body`
  —— 派单 §4 顶回 ③ 的裁定（「不要解析响应体，从路径模板取即可，取不到就空」）。
* :func:`test_the_audit_endpoint_does_not_feed_itself` —— 管理员翻审计页**不产生**审计行
  （否则那张单调增长的表会自己喂自己）。
* :func:`test_total_and_items_share_the_same_filter` 与
  :func:`test_the_envelope_has_exactly_the_four_keys_of_a_generic_list` —— 分页信封的口径
  与泛型 list 逐字同形（:func:`app.api.crud._list_page` 那一段的失效形态）。
* :func:`test_the_method_column_deliberately_has_no_check_constraint` —— 把「判据只有一个
  住址」这件事钉成结构事实（``subject_kind`` 有 CHECK、``method`` **没有**）。
"""
import ast
import datetime as dt
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import audit as audit_module
from app.api.audit import AUDITED_METHODS, should_record
from app.api.schemas.audit import AuditLogFilter, AuditLogPageRead, AuditLogRead
from app.config import BACKEND_DIR
from app.db.models.audit import ANONYMOUS_SUBJECT_KIND, AuditLog
from app.db.models.organisation import Semester, Student, Teacher
from app.deploy import ENV_VAR, PROD
from app.main import create_app

#: 演示口令（与 ``backend/scripts/demo_bootstrap.py`` 的 ``DEMO_PASSWORD`` 同值）。
#: ⚠️ **刻意在这里抄一份**而不是从那边 import：本文件要拿它当**探针串**去扫审计行，
#: 而从被测代码那侧读回来的话，「口令改了、探针跟着改」会让守卫恒绿
#: （硬规矩 #35：期望侧与被测侧不同源）。
PASSWORD = "pe-demo-2025"
STUDENT_NO = "2023120001"
BIRTH = dt.date(2005, 3, 4)
STAFF_NO = "T0001"
ADMIN_NO = "T0003"

#: ``audit_log`` 的 9 列名。**字面量**（不从 ``AuditLog.__table__`` 读回来）：
#: 两侧同源的话，「有人给这张表加了一列 ``body``」会让遍历自动多扫一列、
#: 于是隐私守卫**仍然绿**——而那正是它要抓的失效。
EXPECTED_COLUMNS = [
    "id", "at", "subject_kind", "subject_id", "staff_no",
    "method", "path", "status", "target",
]


@pytest.fixture()
def people(engine):
    """一个宽学期 + 一个学生 + 一个普通教师 + 一个管理员。

    ⚠️ 与 ``tests/api/test_auth_api.py`` 的 ``people`` 夹具**同形但刻意各写一份**：
    那一份插的是 ``S2025001`` / ``T0001`` / ``A0001``，本份用的是**演示库那三个账号**
    （派单 §0 给的口径：学生 ``2023120001``、教师 ``T0001``、管理员 ``T0003``、
    口令 ``pe-demo-2025``）。⚠️ 用演示口径不是为了让报告好看：隐私那一条守卫要拿
    **真的那一串口令**去扫审计行，而它必须是「客户端真的提交过的那一个值」。
    ⚠️ 学期区间刻意宽到覆盖今天（2020–2030），故本文件不随墙钟漂。
    """
    with Session(engine) as session:
        session.add(
            Semester(
                name="2025-2026-1", start_date=dt.date(2020, 1, 1),
                end_date=dt.date(2030, 1, 1), weeks=16, is_current=True,
            )
        )
        student = Student(
            student_no=STUDENT_NO, name="张三", sex="male", birth=BIRTH, grade=1
        )
        teacher = Teacher(staff_no=STAFF_NO, name="李老师", role="teacher")
        admin = Teacher(staff_no=ADMIN_NO, name="王干事", role="admin")
        session.add_all([student, teacher, admin])
        session.commit()
        return {"student": student.id, "teacher": teacher.id, "admin": admin.id}


def _rows(engine) -> list[AuditLog]:
    """``audit_log`` 的全部行，按 ``id`` 升序（= 按时刻升序，本表没有任何 UPDATE）。"""
    with Session(engine) as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.id)).all())


def _bind_student(client) -> None:
    got = client.post(
        "/api/auth/students/bind",
        json={
            "student_no": STUDENT_NO,
            "birth": BIRTH.isoformat(),
            "password": PASSWORD,
        },
    )
    assert got.status_code == 204, (got.status_code, got.text)


def _bind_teacher(client, staff_no: str, name: str) -> None:
    got = client.post(
        "/api/auth/teachers/bind",
        json={"staff_no": staff_no, "name": name, "password": PASSWORD},
    )
    assert got.status_code == 204, (got.status_code, got.text)


def _login(client, kind: str, login: str, password: str = PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"kind": kind, "login": login, "password": password},
    )


def _checkin(client):
    """一次**真的会成功**的学生写操作（``POST /api/training-logs`` → 201）。

    ⚠️ 刻意挑一个不依赖任何前置数据的端点：三源采集里 RPE 要 ``rpe_token``
    （得先有课次 + 教师开一次快评），而打卡只要一个日期。
    """
    return client.post(
        "/api/training-logs",
        json={"log_date": "2025-10-12", "completed": True, "duration_min": 30.0},
    )


# ===========================================================================
# ① 一次登录 + 一次写 → 恰好 2 行
# ===========================================================================


def test_one_login_plus_one_write_is_exactly_two_rows(client, engine, people):
    """派单 §1 第 6 条 ①：**恰好两行**，不是「至少两行」。

    ⚠️ ``==`` 而不是 ``>=``（Ruling 28 的同一条口径）：``>=`` 抓不到「一个请求被记了两遍」
    ——而那正是本仓这个形状最容易出的错：``_resolve_cookie_identity`` 是四个身份依赖
    共用的收口，若审计写在**依赖**里而不是在**中间件**里，一个既有 ``current_student``
    又有 ``get_db`` 的端点会记两行。

    ⚠️ **绑定那一行不计入本条的窗口**（它是第三个 POST，也会被记）：本条量的是
    「登录 + 写」这两拍，故先绑定、再取一次基线行数。⚠️ 而「绑定也被记」这件事
    由 :func:`test_the_four_auth_events_are_all_covered_by_the_single_method_predicate`
    单独钉住（派单 §1 第 2 条要求**核实**它们「本就是 POST，故自然覆盖」）。

    三拍，逐格点名（硬规矩 #110：每一格都回问「这个值从哪来」）：

    * 登录那一行：``method`` / ``path`` 来自请求本身，``status`` = 200，
      ``subject_*`` 三格来自 :func:`app.api.routers.auth.login` 里那一次
      :func:`app.api.audit.note_subject`（**成功档才有**）；
    * 写那一行：``subject_*`` 来自 :func:`app.api.deps._resolve_cookie_identity`
      （cookie 那一档的唯一收口），``status`` = 201；
    * ⚠️ 两行的 ``target`` 都是 ``None``：两个路径都**没有**占位符
      （:func:`app.api.audit.target_of` 的「恰好一个参数」那一档不成立）。
    """
    _bind_student(client)
    base = len(_rows(engine))

    assert _login(client, "student", STUDENT_NO).status_code == 200
    wrote = _checkin(client)
    assert wrote.status_code == 201, wrote.text

    added = _rows(engine)[base:]
    assert len(added) == 2, [
        (row.method, row.path, row.status) for row in added
    ]
    login_row, write_row = added
    assert (login_row.method, login_row.path, login_row.status) == (
        "POST", "/api/auth/login", 200
    )
    assert login_row.subject_kind == "student"
    assert login_row.subject_id == people["student"]
    assert login_row.staff_no is None, "学生那一档不填工号（那一列只服务教职）"
    assert login_row.target is None
    assert (write_row.method, write_row.path, write_row.status) == (
        "POST", "/api/training-logs", 201
    )
    assert write_row.subject_kind == "student"
    assert write_row.subject_id == people["student"]
    assert write_row.target is None


# ===========================================================================
# ② 一次匿名读 → 0 行
# ===========================================================================


def test_an_anonymous_read_writes_no_audit_row(client, engine, people):
    """派单 §1 第 6 条 ②：**读一律不记**。

    ⚠️ 本条打的是**三个**匿名 GET（存活探针 / 一个参考数据资源 / 一个 404 的读），
    而不是一个：少了后两拍，「只把 ``/api/health`` 排除掉」这种半吊子实现也会绿。

    ⚠️ 而「404 的**读**也不记」是承重的：判据只看方法
    （:func:`app.api.audit.should_record`），故一个打错路径的 GET 不会在审计里留下一行
    ——那不是漏，那是「读一律不记」的直接后果（要挡扫描器的话，正确的做法是
    按 IP 的全局速率限制，已登记为待清扫）。
    """
    assert _rows(engine) == []

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/exercises").status_code == 200
    assert client.get("/api/definitely-not-a-route").status_code == 404

    assert _rows(engine) == [], [
        (row.method, row.path, row.status) for row in _rows(engine)
    ]


def test_a_write_to_an_unknown_path_is_still_recorded(client, engine, people):
    """**读不记、写照记**，连打在一个不存在的路径上也记。

    ⚠️ 这一档是「谁在撞门」的另一半：一个扫描器打 ``POST /api/admin`` 一类
    本仓根本没有的路径，今天得到的是 404 + **一行审计**（``subject_kind='anonymous'``）。
    ⚠️ 少了本条，把 :func:`app.api.audit.AuditMiddleware` 的写入挪到
    「只有匹配到路由才记」那一档不会有任何测试红，而那会把探测行为整个抹掉。
    """
    got = client.post("/api/definitely-not-a-route", json={})
    assert got.status_code == 404

    rows = _rows(engine)
    assert len(rows) == 1
    assert rows[0].method == "POST"
    assert rows[0].path == "/api/definitely-not-a-route"
    assert rows[0].status == 404
    assert rows[0].subject_kind == ANONYMOUS_SUBJECT_KIND
    # ⚠️ 路由没匹配上 → ``scope`` 里没有 ``path_params`` → target 为空（不是抛）
    assert rows[0].target is None


# ===========================================================================
# ③ 鉴权失败也要记，且 subject_kind == 'anonymous'
# ===========================================================================


def test_a_failed_authentication_is_one_anonymous_row(client, engine, people):
    """派单 §1 第 6 条 ③：**鉴权失败 1 行且 ``subject_kind='anonymous'``**。

    ⚠️ 三档失败各打一次，每一档都是**恰好一行**：

    * **口令错**（``401 invalid_credentials``）—— :mod:`app.auth.policy` 的锁定档
      **故意不给调用方任何提示**，故本行是「谁在撞门」的**唯一**可见性
      （:class:`app.db.models.auth.LoginAttempt` 的模块 docstring 第二节逐字把这一格
      指给了本表）；
    * **没有会话就打一个要身份的写端点**（``401 unauthenticated``）；
    * **学号不在册**（``403 password_not_bound``）——⚠️ 它**也**记，
      而 ``login_attempt`` 那一档**刻意不写行**（计数它挡不住任何一次口令猜测）。
      两张表在同一个事件上给出不同的处置，那是有意的：审计要**永久留痕**，
      限流要**能被清零**。

    ⚠️ 三行的 ``subject_id`` / ``staff_no`` **一律为 ``NULL``**：调用方自称的那个串
    在请求体里，而本模块**不读请求体**（隐私纪律）。⚠️ 于是「有人拿 ``T0001`` 试了
    五次口令」这件事在 ``audit_log`` 里表现为**五行 ``path='/api/auth/login'`` 的
    anonymous 行**，而「试的是哪个工号」要去 ``login_attempt`` 查（那一列存原文）。
    两张表合起来才答得全，如实记录（硬规矩 #39）。
    """
    _bind_teacher(client, STAFF_NO, "李老师")
    base = len(_rows(engine))

    anonymous = TestClient(client.app)
    wrong = _login(anonymous, "teacher", STAFF_NO, password="definitely-wrong")
    assert wrong.status_code == 401, wrong.text
    no_session = anonymous.post(
        "/api/training-logs", json={"log_date": "2025-10-12", "completed": True}
    )
    assert no_session.status_code == 401, no_session.text
    not_bound = _login(anonymous, "student", "S-NOT-ON-ROSTER")
    assert not_bound.status_code == 403, not_bound.text

    added = _rows(engine)[base:]
    assert len(added) == 3, [(r.method, r.path, r.status) for r in added]
    assert [row.status for row in added] == [401, 401, 403]
    for row in added:
        assert row.subject_kind == ANONYMOUS_SUBJECT_KIND, (row.path, row.status)
        assert row.subject_id is None, row.path
        assert row.staff_no is None, row.path
        assert row.method == "POST"


def test_a_successful_logout_keeps_the_identity_that_logged_out(client, engine, people):
    """**登出那一行有名有姓**，不是 ``anonymous``。

    ⚠️ 这一格是 :func:`app.api.deps._resolve_cookie_identity` 里那一次
    :func:`app.api.audit.note_subject` 存在的**全部理由**：``logout`` 端点会把
    ``user_session.revoked_at`` 写上，故**事后**再解析那个 cookie 必然是 ``None``
    ——审计里就会留下一行「有人登出了，但不知道是谁」，而那恰恰是最该有名有姓的一行
    （「谁的 cookie 在什么时候被登出」是排查「cookie 被偷之后攻击者有没有登出」的
    唯一线索）。

    ⚠️ 少了本条，把 ``note_subject`` 从 :func:`_resolve_cookie_identity` 挪到
    「响应之后」不会有任何测试红，而失效是**静默**的（登出行照样写、只是主体错了）。
    """
    _bind_teacher(client, ADMIN_NO, "王干事")
    assert _login(client, "teacher", ADMIN_NO).status_code == 200
    base = len(_rows(engine))

    assert client.post("/api/auth/logout").status_code == 204

    added = _rows(engine)[base:]
    assert len(added) == 1
    row = added[0]
    assert (row.method, row.path, row.status) == ("POST", "/api/auth/logout", 204)
    assert row.subject_kind == "teacher", row.subject_kind
    assert row.subject_id == people["admin"]
    assert row.staff_no == ADMIN_NO


# ===========================================================================
# ④ 隐私：真发一次带口令的 login，然后扫审计行的**全部 9 列**
# ===========================================================================


def test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row(
    client, engine, people
):
    """派单 §1 第 3 条 + 第 6 条 ④：**审计行里不出现口令串与出生日期串**。

    ⚠️⚠️ **取证姿势是派单逐字要求的**：「对已知反例验证：真的发一次带口令的 login，
    然后查审计行的**所有列**」。故本条：

    1. **真发**一次学生绑定（体里有 ``birth`` + 明文口令）与一次登录（体里有明文口令）；
    2. 把落库的**每一行**、**每一列**都读回来（列名取自 :data:`EXPECTED_COLUMNS`
       那份**字面量**，不从 ``AuditLog.__table__`` 读回来——两侧同源的话
       「加一列 ``body``」会让遍历自动多扫一列、守卫仍然绿）；
    3. 断言四个探针串一个都不出现：口令原文、出生日期的 ISO 串、它的紧凑串、
       以及 ``"password"`` 这个词本身。

    ⚠️ 于是本条**同时**钉住两件事：① 值没有落库；② **列名**里也没有
    （一个 ``password`` 列名的存在本身就说明有人打算存它）。

    ⚠️ 它**不是**「我看代码里没有 ``await request.body()``」那种静态断言：
    静态断言在「有人从查询串或请求头里把口令捡进来」时会绿，而本条不会
    （它扫的是**落库的值**，与值从哪来无关）。
    ⚠️ 结构侧那一半（三个响应模型里不出现凭据字段名）住在
    :func:`test_no_audit_schema_mentions_a_credential_or_a_body`。
    """
    _bind_student(client)
    assert _login(client, "student", STUDENT_NO).status_code == 200
    assert _checkin(client).status_code == 201

    rows = _rows(engine)
    assert len(rows) == 3, "取证前提：绑定 / 登录 / 打卡 三行都在"
    assert [c.name for c in AuditLog.__table__.columns] == EXPECTED_COLUMNS, (
        "audit_log 的列清单变了：隐私守卫的遍历面必须跟着改，"
        "否则「新加的那一列」根本不在扫描范围内（那正是本守卫要抓的失效）"
    )

    needles = (
        PASSWORD,
        BIRTH.isoformat(),
        BIRTH.strftime("%Y%m%d"),
        "password",
    )
    offenders: list[str] = []
    for row in rows:
        for column in EXPECTED_COLUMNS:
            value = getattr(row, column)
            text = "" if value is None else str(value)
            for needle in needles:
                if needle in text:
                    offenders.append(f"行 {row.id} 的 {column} 列含 {needle!r}：{text!r}")
    assert offenders == [], "审计行里出现了请求体的内容：\n  " + "\n  ".join(offenders)

    # ⚠️ 反空转：那三个请求**确实**带着口令与出生日期发出去了（否则上面那一段
    #    是在扫一批从未接触过秘密的行，恒绿）。判据取自考古证据而不是响应体：
    #    绑定成功后 ``student.password_hash`` 非空，且它**校验得过**那个口令原文。
    from app.auth.passwords import verify_password

    with Session(engine) as session:
        stored = session.scalar(
            select(Student.password_hash).where(Student.student_no == STUDENT_NO)
        )
    assert stored is not None and verify_password(PASSWORD, stored), (
        "取证前提不成立：这一串口令从来没有被提交过，上面那一段扫描是空转的"
    )


def test_no_audit_schema_mentions_a_credential_or_a_body():
    """**结构侧**的另一半：三个响应/请求模型的字段名里不出现凭据或「体」。

    ⚠️ 它与上面那一条**分工**（刻意不合并）：那一条钉「落库的值」，本条钉
    「HTTP 面上能被读出来的字段名」。⚠️ 少了本条，「给 :class:`AuditLogRead` 加一格
    ``body``、而 :class:`AuditLog` 上恰好也有那一列」这个改动在**读侧**没有任何守卫；
    而上面那一条会红（它扫的是列名），故两拍**互为冗余**——冗余是有意的：
    两条守卫的**修法不同**（一条要删列、一条要删字段），报错因此指向真因。

    ⚠️ 判据是**子串**而不是相等：``password_hash`` / ``request_body`` /
    ``birth_date`` 都要被抓到，而 ``subject_id`` / ``staff_no`` 一类不会误伤。
    """
    forbidden = ("password", "birth", "body", "secret", "credential", "token")
    offenders: list[str] = []
    for model in (AuditLogRead, AuditLogPageRead, AuditLogFilter):
        for name in model.model_fields:
            lowered = name.lower()
            for needle in forbidden:
                if needle in lowered:
                    offenders.append(f"{model.__name__}.{name} 含 {needle!r}")
    assert offenders == [], "审计的 HTTP 契约里出现了凭据/请求体字段：\n  " + "\n  ".join(offenders)

    # ⚠️ 反空转：三个模型**确实**有字段（否则上面那个循环空转全绿）。
    assert len(AuditLogRead.model_fields) == 9, sorted(AuditLogRead.model_fields)
    assert sorted(AuditLogRead.model_fields) == sorted(EXPECTED_COLUMNS), (
        "读模型的 9 格必须与表的 9 列一一对应：多一格就是一个「现算/回查」出来的字段，"
        "少一格就是前端拿不到它要显示的东西"
    )
    assert sorted(AuditLogPageRead.model_fields) == ["items", "limit", "offset", "total"]
    assert sorted(AuditLogFilter.model_fields) == ["method", "subject_kind"]


# ===========================================================================
# ⑤ 三档身份对 GET /api/audit-logs 的状态码矩阵
# ===========================================================================


def test_the_audit_endpoint_admits_only_an_admin(client, engine, people):
    """派单 §1 第 5 条：**仅 ``role='admin'``**（教师 403、学生 403、匿名 401）。

    ⚠️ 四档一律用**真 cookie**（各自登录一次），不用请求头：生产档下
    ``PE_ALLOW_HEADER_IDENTITY`` 被强制关（:func:`app.api.deps.allow_header_identity`），
    故请求头那一档在甲方现场**不可达**；用 cookie 走的是与生产**同一条**判定路径。

    ⚠️ **学生那一档是 403 而不是 401**：请求者已经被认出来了，只是不是这个端点要的
    那一类人（:func:`app.api.deps.current_teacher` 的 403 那一支）。
    ⚠️ 而**教师那一档也是 403、但由另一个人给**（:func:`app.api.deps.require_admin`），
    故两档的 ``detail`` 不同——那是有意的：「你不是教职」与「你是教职但不是管理员」
    对前端是两种提示（前者该去重新登录，后者该回课堂页）。

    ⚠️ 请求头那一档**另外钉**（下面那一条）：``tests/conftest.py`` 把
    ``PE_ALLOW_HEADER_IDENTITY`` 设成了 ``1``，故它在测试进程里是**可达**的，
    而它的实测码与 cookie 那一档**不同**（带学生头是 401 而不是 403，
    因为 :func:`current_teacher` 只认 ``X-Teacher-Staff-No``）。如实记录，不掩盖。
    """
    _bind_student(client)
    _bind_teacher(client, STAFF_NO, "李老师")
    _bind_teacher(client, ADMIN_NO, "王干事")

    admin = TestClient(client.app)
    assert _login(admin, "teacher", ADMIN_NO).status_code == 200
    teacher = TestClient(client.app)
    assert _login(teacher, "teacher", STAFF_NO).status_code == 200
    student = TestClient(client.app)
    assert _login(student, "student", STUDENT_NO).status_code == 200
    anonymous = TestClient(client.app)

    matrix = {
        "管理员": admin.get("/api/audit-logs").status_code,
        "普通教师": teacher.get("/api/audit-logs").status_code,
        "学生": student.get("/api/audit-logs").status_code,
        "匿名": anonymous.get("/api/audit-logs").status_code,
    }
    assert matrix == {"管理员": 200, "普通教师": 403, "学生": 403, "匿名": 401}, matrix

    # ⚠️ 反假绿：200 那一档**真的有内容**（否则「端点没挂上去」也会给出一个
    #    看起来像 403/401 的矩阵，而 200 那一格是空的）。
    body = admin.get("/api/audit-logs").json()
    assert body["total"] > 0, body
    assert body["items"][0]["subject_kind"] in AuditLog.SUBJECT_KINDS


def test_the_audit_endpoint_answered_by_headers_in_the_dev_tier(client, engine, people):
    """**过渡通道那一档的实测码**（开发档；生产档下这一档不可达）。

    ⚠️ 本条钉的是 :func:`app.api.deps.current_teacher` 的**既有**口径在审计端点上的
    后果，而不是给它开一个例外：

    * ``X-Teacher-Staff-No: <管理员>`` → **200**（判定与 cookie 那一档同一个函数）；
    * ``X-Teacher-Staff-No: <普通教师>`` → **403**；
    * ``X-Student-Id: 1`` → **401**（⚠️ 不是 403：``current_teacher`` 只认教师头，
      故一个学生头在它眼里等于「没有身份」）。

    ⚠️ 那一格 ``401 vs 403`` 的差别是本仓既有事实（:func:`app.api.deps.current_student`
    的 docstring 逐字写了它的对偶），本条只是把它在审计端点上也**记下来**，
    免得下一个人以为「学生打审计页是 403」在两条通道上都成立。
    """
    admin_headers = {"X-Teacher-Staff-No": ADMIN_NO}
    teacher_headers = {"X-Teacher-Staff-No": STAFF_NO}
    student_headers = {"X-Student-Id": str(people["student"])}

    assert client.get("/api/audit-logs", headers=admin_headers).status_code == 200
    assert client.get("/api/audit-logs", headers=teacher_headers).status_code == 403
    assert client.get("/api/audit-logs", headers=student_headers).status_code == 401
    assert client.get("/api/audit-logs").status_code == 401


# ===========================================================================
# ⑥ 定点变异：把 GET 也记 / 把写不记
# ===========================================================================


def test_the_two_mutations_of_the_record_predicate_are_caught(
    client, engine, people, monkeypatch
):
    """派单 §1 第 6 条 ⑥：**两个定点变异都要让上面的守卫红**。

    ⚠️ 变异打在 :data:`app.api.audit.AUDITED_METHODS` 上（``should_record`` 在**调用时**
    读那个模块级全局，故 ``monkeypatch.setattr`` 生效），而它走的正是与真守卫
    **完全相同**的那条代码路径（同一个中间件、同一个 ``dispatch``、同一张表）。
    于是本条红/绿直接说明 ①② 两条守卫**有没有牙**，而不是「我另写了一个判定」。

    两格各自：

    * **变异 A（把 GET 也记）**：``AUDITED_METHODS |= {"GET"}`` →
      一次匿名读**产生**一行 → :func:`test_an_anonymous_read_writes_no_audit_row`
      的 ``assert _rows(engine) == []`` 当场红。
    * **变异 B（把写不记）**：``AUDITED_METHODS = frozenset()`` →
      登录 + 写**产生零行** → :func:`test_one_login_plus_one_write_is_exactly_two_rows`
      的 ``len(added) == 2`` 当场红。

    ⚠️ **两格都要跑一遍真请求**：只断言 ``should_record("GET") is True`` 是**静态**的，
    它证明不了中间件真的照那个判据写库（例如「有人把 ``dispatch`` 里那个 ``if`` 删了」
    在静态断言下照样绿）。
    """
    _bind_student(client)
    assert _login(client, "student", STUDENT_NO).status_code == 200

    # --- 变异 A：把 GET 也记 -------------------------------------------------
    monkeypatch.setattr(audit_module, "AUDITED_METHODS", AUDITED_METHODS | {"GET"})
    assert should_record("GET") is True, "变异 A 没有生效，下面那一拍是空转的"
    base = len(_rows(engine))
    assert client.get("/api/health").status_code == 200
    after_a = _rows(engine)[base:]
    assert len(after_a) == 1, (
        "变异 A 应当让「匿名读 → 0 行」那条守卫红：实测新增 "
        f"{len(after_a)} 行 {[(r.method, r.path) for r in after_a]}"
    )
    assert after_a[0].method == "GET" and after_a[0].path == "/api/health"

    # --- 变异 B：把写不记 -----------------------------------------------------
    monkeypatch.setattr(audit_module, "AUDITED_METHODS", frozenset())
    assert should_record("POST") is False, "变异 B 没有生效，下面那一拍是空转的"
    base = len(_rows(engine))
    assert _checkin(client).status_code == 201
    after_b = _rows(engine)[base:]
    assert after_b == [], (
        "变异 B 应当让「登录 + 一次写 → 恰好 2 行」那条守卫红：实测仍然新增了 "
        f"{[(r.method, r.path) for r in after_b]}"
    )


def test_the_record_predicate_is_a_single_owner_and_only_looks_at_the_method():
    """**判据只住在一个函数里**（派单 §1 第 2 条：「记与不记的判据只住在一个函数里」）。

    两拍：

    ① **行为**：判据只看方法——``POST`` / ``PATCH`` / ``DELETE`` 三个都记，
       其余五个（``GET`` / ``HEAD`` / ``OPTIONS`` / ``PUT`` / ``TRACE``）一个都不记；
       ⚠️ 且它对路径、身份、响应码**一律无感**（三个不在 :data:`AUDITED_METHODS`
       之外的方法各试一次，含一个**鉴权端点**的路径与一个**不存在**的路径）。
    ② **结构**（AST）：``app/api/audit.py`` 里 ``AUDITED_METHODS`` 只被**赋值一次**，
       而全仓**没有第二个**「哪些方法要记」的字面量集合。
       ⚠️ 这一拍挡的是派单逐字点名的那个失效形态：若写成「方法 ∈ {POST,PATCH,DELETE}
       **或** 路径 ∈ {login, logout, bind…}」，那么加一个 ``POST /api/auth/refresh``
       时要记得改**两处**，而漏掉的那一处是**静默**的。
    """
    for method in ("POST", "PATCH", "DELETE"):
        assert should_record(method) is True, method
    for method in ("GET", "HEAD", "OPTIONS", "PUT", "TRACE"):
        assert should_record(method) is False, method
    # ⚠️ 小写也认（``upper()`` 那一格），故「按小写调本函数」不会静默变成「不记」
    assert should_record("post") is True

    source = (BACKEND_DIR / "app" / "api" / "audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AUDITED_METHODS"
            for target in node.targets
        )
    ]
    assert len(assignments) == 1, f"AUDITED_METHODS 被赋值了 {len(assignments)} 次"
    # ⚠️ 判据函数**体**里只出现那一个名字：一旦有人往里加一个「路径白名单」，
    #    本行会红。⚠️ 只扫 ``predicate.body``、不扫整个 ``FunctionDef``——
    #    后者的 ``args`` / ``returns`` 里那些**标注**（``str`` / ``bool``）也是
    #    ``ast.Name``，扫进来会得到三个名字而不是一个（本 Task 实测撞过一次）。
    predicate = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "should_record"
    )
    names = sorted({
        node.id for statement in predicate.body for node in ast.walk(statement)
        if isinstance(node, ast.Name) and node.id != "method"
    })
    assert names == ["AUDITED_METHODS"], (
        f"should_record 里出现了第二个判据来源 {names}：记与不记只看方法"
        "（派单 §1 第 2 条），路径白名单会让「加一个新鉴权端点」变成两处改动"
    )


def test_the_four_auth_events_are_all_covered_by_the_single_method_predicate(
    client, engine, people
):
    """**核实**派单 §1 第 2 条那半句：四个鉴权事件「本就是 POST，故自然覆盖」。

    ⚠️ 派单逐字要求「**核实**，不要写第二份判据」。核实结果写成本条：
    两个 ``bind`` + ``login`` + ``logout`` 四个端点各打一次，**四行都在**，
    而 ``app/api/audit.py`` 里**没有任何路径字面量**（第二拍）。

    ⚠️ 少了本条，「把 ``should_record`` 改成方法 + 路径白名单」与
    「四个鉴权端点里有一个其实是 GET」两档都没有守卫；
    而后者是**真的会发生**的失效形态：加一个 ``GET /api/auth/logout`` 的人
    会以为登出仍然被记（它不会）。

    ⚠️ 第五个鉴权端点 ``GET /api/auth/me`` **刻意不在**本条里：它是读，
    故不记（:func:`test_anonymous_read_writes_no_audit_row` 那一档）。
    """
    _bind_student(client)
    _bind_teacher(client, STAFF_NO, "李老师")
    assert _login(client, "student", STUDENT_NO).status_code == 200
    assert client.post("/api/auth/logout").status_code == 204

    paths = [row.path for row in _rows(engine)]
    assert paths == [
        "/api/auth/students/bind",
        "/api/auth/teachers/bind",
        "/api/auth/login",
        "/api/auth/logout",
    ], paths
    assert all(row.method == "POST" for row in _rows(engine))

    # 第二拍：判据那一侧**一个路径字面量都没有**（AST：模块里没有以 /api/ 开头的常量）
    source = (BACKEND_DIR / "app" / "api" / "audit.py").read_text(encoding="utf-8")
    literals = [
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("/api/")
    ]
    assert literals == [], (
        f"app/api/audit.py 里出现了路径字面量 {literals}：记与不记只看方法，"
        "一份路径白名单就是第二个所有者（派单 §1 第 2 条）"
    )


# ===========================================================================
# target：从路径取，绝不从响应体取（派单 §4 顶回 ③ 的裁定）
# ===========================================================================


def test_the_target_column_comes_from_the_path_and_never_from_the_response_body(
    client, engine, people
):
    """派单 §4 顶回 ③ 的裁定落地：**从路径模板取，取不到就空**。

    四拍，各钉一档：

    * ``PATCH /api/students/{id}`` → ``target == "<id>"``（**恰好一个**路径参数）；
    * ``POST /api/semesters`` → ``target is None``（没有参数；⚠️ 新建那一行的 id
      **只在响应体里**，而本模块**不缓冲响应体**——如实记为已知局限）；
    * ``GET`` 一律不记，故没有「读的 target」这一档；
    * ⚠️ **``target`` 存的是字符串原文**：``PATCH /api/students/abc`` 在端点里是
      422（``int`` 转不出来），而它在审计里**仍然有一行**、``target == "abc"``。
      若不 ``str()`` 而是 ``int()``，那一行会当场抛、于是「有人拿一个非数字 id 试写」
      这件事**在审计里消失了**——那正是最该留下来的一行。
    """
    _bind_teacher(client, ADMIN_NO, "王干事")
    admin = TestClient(client.app)
    assert _login(admin, "teacher", ADMIN_NO).status_code == 200

    base = len(_rows(engine))
    assert admin.patch("/api/students/1", json={"name": "改名了"}).status_code == 200
    created = admin.post(
        "/api/semesters",
        json={
            "name": "2026-2027-1", "start_date": "2026-09-01",
            "end_date": "2027-01-20", "weeks": 16, "is_current": False,
        },
    )
    assert created.status_code == 201, created.text
    broken = admin.patch("/api/students/abc", json={"name": "不是一个整数"})
    assert broken.status_code == 422, broken.text

    added = _rows(engine)[base:]
    assert [row.path for row in added] == [
        "/api/students/1", "/api/semesters", "/api/students/abc"
    ]
    assert added[0].target == "1", added[0].target
    assert added[0].status == 200
    assert added[1].target is None, "新建的 id 只在响应体里，故 target 必须是空"
    assert added[1].status == 201
    assert added[2].target == "abc", added[2].target
    assert added[2].status == 422

    # ⚠️ 反空转：那一次 POST **确实**建出了一行、而它的 id 确实只在响应体里
    assert created.json()["id"] >= 1


# ===========================================================================
# 端点自己：信封、过滤、不自喂
# ===========================================================================


def test_the_audit_endpoint_does_not_feed_itself(client, engine, people):
    """管理员翻审计页**不产生**审计行（它是 GET）。

    ⚠️ 少了本条，「把 ``GET`` 加进 :data:`AUDITED_METHODS`」这个改动会让审计页
    每翻一页往表里加一行，而那张表是**单调增长、没有清理任务**的
    （:class:`app.db.models.audit.AuditLog` 的模块 docstring 第一节）。
    ⚠️ 本条与 :func:`test_the_two_mutations_of_the_record_predicate_are_caught`
    的变异 A **不重复**：那一条钉的是「任意 GET 会被记」，本条钉的是
    「**审计端点自己**不会被记」——后者的失效后果更具体（自喂），故单独一条。
    """
    _bind_teacher(client, ADMIN_NO, "王干事")
    admin = TestClient(client.app)
    assert _login(admin, "teacher", ADMIN_NO).status_code == 200
    base = len(_rows(engine))

    for _ in range(3):
        assert admin.get("/api/audit-logs").status_code == 200
    assert admin.get("/api/audit-logs", params={"limit": 1}).status_code == 200

    assert len(_rows(engine)) == base, [
        (row.method, row.path) for row in _rows(engine)[base:]
    ]


def test_the_envelope_has_exactly_the_four_keys_of_a_generic_list(
    client, engine, people
):
    """响应体是**分页信封四键**，与泛型 list 逐字同形（前端因此能复用分页组件）。

    ⚠️ 键名**字面写死**（硬规矩 #35）：``items`` / ``total`` / ``limit`` / ``offset``。
    ⚠️ 本端点**不走** :func:`app.api.crud._list_page`（它不是资源），
    故这四个键在本仓有**两处**拼装——本条与
    ``tests/api/test_crud.py`` 里那一条泛型 list 的信封断言**并列、不合并**
    （合并的唯一办法是让审计端点走泛型工厂，而那会带来四个错，
    逐字见 :mod:`app.api.routers.audit` 的模块 docstring 第一节）。

    ⚠️ ``items`` 按 ``id DESC``（**最新在前**）：审计页的第一屏要的是「刚刚发生了什么」，
    而泛型 list 是 ``id ASC``。⚠️ 那一格差别是本端点**刻意**不复用 ``_list_page``
    的第二个理由（第一个是排序方向）。
    """
    _bind_student(client)
    assert _login(client, "student", STUDENT_NO).status_code == 200
    assert _checkin(client).status_code == 201
    _bind_teacher(client, ADMIN_NO, "王干事")
    admin = TestClient(client.app)
    assert _login(admin, "teacher", ADMIN_NO).status_code == 200

    body = admin.get("/api/audit-logs").json()
    assert sorted(body) == ["items", "limit", "offset", "total"]
    assert body["limit"] == 50 and body["offset"] == 0
    assert body["total"] == len(_rows(engine))
    ids = [row["id"] for row in body["items"]]
    assert ids == sorted(ids, reverse=True), "审计页要最新在前（id DESC）"
    assert sorted(body["items"][0]) == sorted(EXPECTED_COLUMNS)


def test_total_and_items_share_the_same_filter(client, engine, people):
    """``total`` 与 ``items`` **走同一个 ``WHERE``**（过滤后计数、不受分页影响）。

    ⚠️ 失效形态逐字来自 :func:`app.api.crud._list_page` 的 docstring：
    「学生会话的 ``items`` 只有自己的行、而 ``total`` 是全表 840」→ 前端分页器
    给出一个**翻不到**的页数。本条因此三拍：

    ① 过滤之后的 ``total`` **等于**过滤之后的行数（不是全表行数）；
    ② ``limit`` **不改变** ``total``（它是过滤后的总数、不是本页的条数）；
    ③ ``offset`` 翻到第二页时 ``items`` 真的换了、而 ``total`` 不变。

    ⚠️ 两个过滤参数各试一次（``subject_kind`` / ``method``），且**取值域不是字面词表**：
    ``subject_kind`` 取自 :attr:`AuditLog.SUBJECT_KINDS`、``method`` 取自
    :data:`AUDITED_METHODS`（域外值是 **422**、不是「静默 0 行」——后者会让运维以为
    「今天没有删除操作」）。
    """
    _bind_student(client)
    assert _login(client, "student", STUDENT_NO).status_code == 200
    assert _checkin(client).status_code == 201
    anonymous = TestClient(client.app)
    assert _login(anonymous, "student", STUDENT_NO, password="wrong").status_code == 401
    _bind_teacher(client, ADMIN_NO, "王干事")
    admin = TestClient(client.app)
    assert _login(admin, "teacher", ADMIN_NO).status_code == 200

    everything = admin.get("/api/audit-logs").json()
    anonymous_only = admin.get(
        "/api/audit-logs", params={"subject_kind": ANONYMOUS_SUBJECT_KIND}
    ).json()
    assert 0 < anonymous_only["total"] < everything["total"], (
        everything["total"], anonymous_only["total"]
    )
    assert anonymous_only["total"] == sum(
        1 for row in _rows(engine) if row.subject_kind == ANONYMOUS_SUBJECT_KIND
    )
    assert {row["subject_kind"] for row in anonymous_only["items"]} == {
        ANONYMOUS_SUBJECT_KIND
    }

    paged = admin.get(
        "/api/audit-logs", params={"subject_kind": ANONYMOUS_SUBJECT_KIND, "limit": 1}
    ).json()
    assert paged["total"] == anonymous_only["total"], "limit 不该改变 total"
    assert len(paged["items"]) == 1
    second = admin.get(
        "/api/audit-logs",
        params={"subject_kind": ANONYMOUS_SUBJECT_KIND, "limit": 1, "offset": 1},
    ).json()
    assert second["total"] == anonymous_only["total"]
    assert second["items"][0]["id"] != paged["items"][0]["id"]

    # method 过滤：小写也认（归一化住在 AuditLogFilter 里，端点不再判一次）
    lowered = admin.get("/api/audit-logs", params={"method": "patch"}).json()
    upper = admin.get("/api/audit-logs", params={"method": "PATCH"}).json()
    assert lowered["total"] == upper["total"]
    assert {row["method"] for row in upper["items"]} <= {"PATCH"}

    # 域外值是 422，不是静默 0 行
    assert admin.get(
        "/api/audit-logs", params={"method": "GET"}
    ).status_code == 422, "GET 不在 AUDITED_METHODS 里，故表里不可能有这样的行"
    assert admin.get(
        "/api/audit-logs", params={"subject_kind": "ghost"}
    ).status_code == 422
    # ⚠️ 两格的取值域**就是**那两个所有者（不是第三份词表）
    assert AuditLog.SUBJECT_KINDS == {"student", "teacher", ANONYMOUS_SUBJECT_KIND}
    assert AUDITED_METHODS == frozenset({"POST", "PATCH", "DELETE"})


# ===========================================================================
# 两档部署都要工作（派单 §0 那条 ⚠️）
# ===========================================================================


def test_the_audit_trail_is_written_in_both_deployment_tiers(monkeypatch, tmp_path):
    """**dev 与 prod 两档下审计都工作**（派单 §0 的 ⚠️）。

    两拍，**结构那一拍是承重的**：

    ① **结构**：``app/api/audit.py`` 里**一次 ``os.environ`` / ``os.getenv`` 都没有**
       （AST 判，不是文本搜索——文本搜索会把 docstring 里的**提及**当成**本身**，
       硬规矩 #109）。⚠️ 于是「``PE_ENV`` 影响审计」这件事在本模块**构造上不可能**：
       它连环境变量都不读。这一拍比②更强，因为它同时挡住了
       「有人将来在这里加一个 ``PE_AUDIT=0`` 的开关」。
    ② **行为**：两档各起一个应用、各打一次匿名写（401），**各得一行**、
       且两行的 ``subject_kind`` 都是 ``anonymous``。

    ⚠️ 两档各用**独立的临时磁盘库**（``tmp_path`` 下），不用内存库：
    ``prod`` 那一档要过 :func:`app.main._selfcheck_prod`，而它数的是
    ``application.user_middleware``——本条顺带证明「多挂一层审计中间件」
    **不会**让生产档的启动自检响（那一道自检只认 ``CORSMiddleware``）。
    ⚠️ ``PE_CORS_ORIGINS`` 刻意**不设**：不设 = 不挂 CORSMiddleware = 拒绝跨域，
    正是同源部署（Plan 06 Task 7 那一档）要的形状，也让自检无 offender。
    """
    source = (BACKEND_DIR / "app" / "api" / "audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    readers = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv")
    ]
    assert readers == [], (
        f"app/api/audit.py 在第 {readers} 行读了环境变量：审计的口径不该随部署档变"
        "（派单 §0：审计与备份在两档下都要工作）"
    )
    imports_os = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        and any(alias.name == "os" for alias in node.names)
    ]
    assert imports_os == [], "app/api/audit.py 连 os 都不该 import（它没有任何环境事实要读）"

    for tier in ("dev", PROD):
        monkeypatch.setenv(ENV_VAR, tier)
        db = tmp_path / f"{tier}.db"
        application = create_app(db_url="sqlite:///" + db.as_posix())
        with TestClient(application) as tier_client:
            got = tier_client.post(
                "/api/training-logs",
                json={"log_date": "2025-10-12", "completed": True},
            )
            assert got.status_code == 401, (tier, got.status_code, got.text)
        from app.db.session import init_db  # noqa: F401  （仅为可读性：下面是同一个引擎）

        with Session(application.state.engine) as session:
            rows = list(session.scalars(select(AuditLog)).all())
        application.state.engine.dispose()
        assert len(rows) == 1, (tier, [(r.method, r.path, r.status) for r in rows])
        assert rows[0].subject_kind == ANONYMOUS_SUBJECT_KIND, tier
        assert rows[0].status == 401 and rows[0].path == "/api/training-logs"


# ===========================================================================
# 结构：判据只有一个住址、method 刻意没有 CHECK
# ===========================================================================


def test_the_method_column_deliberately_has_no_check_constraint():
    """``subject_kind`` 有 CHECK、``method`` **没有**——而这个不对称是**要的**。

    ⚠️ 本条钉的是 :class:`app.db.models.audit.AuditLog` 里那段注释的可执行形式：
    「哪些方法会被记」的唯一所有者是 :func:`app.api.audit.should_record` 那**一个函数**
    （派单 §1 第 2 条），再在 DB 上设一道会让那条判据有**两个**住址。

    ⚠️ 更具体的后果是**定点变异会红在错误的地方**：派单 §1 第 6 条 ⑥ 要的变异是
    「把 GET 也记」，而一个 ``method IN ('POST','PATCH','DELETE')`` 的 CHECK 会让它
    先炸出 ``IntegrityError`` → 500，于是守卫红是红了、而它证明的不是
    「判据被改宽了」（:func:`test_the_two_mutations_of_the_record_predicate_are_caught`
    的变异 A 因此会红在一个与「行数」无关的异常上）。

    ⚠️ 两拍：① ``method`` 上**没有** CHECK；② ``subject_kind`` 上**有**、
    且它的取值域**就是** :attr:`AuditLog.SUBJECT_KINDS`（本包约定 2：
    类常量是唯一真相，CHECK 文本由 :func:`app.db.models._shared._in_domain` 生成）。
    """
    checks = {
        constraint.name: " ".join(str(constraint.sqltext).split()).upper()
        for constraint in AuditLog.__table__.constraints
        if type(constraint).__name__ == "CheckConstraint"
    }
    assert "ck_audit_log_subject_kind" in checks, sorted(checks)
    assert checks["ck_audit_log_subject_kind"] == (
        "SUBJECT_KIND IN ('ANONYMOUS', 'STUDENT', 'TEACHER')"
    )
    assert not any("METHOD" in text for text in checks.values()), (
        f"method 列上出现了 CHECK：{sorted(checks)}。判据的唯一住址是 "
        "app.api.audit.should_record（派单 §1 第 2 条），DB 上再设一道会让"
        "「把 GET 也记」那个定点变异红在 IntegrityError 上而不是红在行数上"
    )
    # ⚠️ 取值域**不是**第三份词表：它就是 UserSession.KINDS 那一个对象 + anonymous
    from app.db.models.auth import UserSession

    assert AuditLog.SUBJECT_KINDS == UserSession.KINDS | {ANONYMOUS_SUBJECT_KIND}
    assert UserSession.KINDS == {"student", "teacher"}, (
        "`|` 造出新集合、不改那一个：ck_user_session_kind 必须仍然只有两档"
    )


def test_the_audit_table_is_not_a_resource_and_has_no_write_endpoint(client, engine):
    """``audit_log`` **不是** 23 个资源之一，且**没有任何端点能改它**。

    ⚠️ 派单 §1 第 5 条逐字要求「它**不进** ``catalog.RESOURCES`` 的 23 行」。
    两拍：

    ① ``RESOURCES`` 仍然是 **23** 行、且里面**没有** ``audit-logs``；
    ② ``/openapi.json`` 的 ``/api/audit-logs`` 下**只有 ``get``**——
       没有 ``post`` / ``patch`` / ``delete``。

    ⚠️ ② 是**不可改写**这条性质的可执行形式：审计行只由
    :class:`app.api.audit.AuditMiddleware` 写，而一个能 ``PATCH`` 审计行的端点
    等于让「谁改了什么」这件事本身可以被改（:class:`AuditLog` 的模块 docstring
    第一节：不可改写是审计的第一条性质）。
    """
    from app.api.routers.catalog import RESOURCES

    assert len(RESOURCES) == 23, len(RESOURCES)
    assert all(row["path"] != "/api/audit-logs" for row in RESOURCES), [
        row["path"] for row in RESOURCES
    ]

    spec = client.get("/openapi.json").json()
    assert sorted(spec["paths"]["/api/audit-logs"]) == ["get"], (
        sorted(spec["paths"]["/api/audit-logs"])
    )
    assert spec["paths"]["/api/audit-logs"]["get"]["security"] == [
        {"X-Teacher-Staff-No": []}
    ]
    # ⚠️ 它进的是**特例端点**那一圈，故它挂在
    #    tests/api/test_prescription_api.py 的 :data:`expected` 清单里（第 24 项）。
    #    本行只钉「它在 OpenAPI 上存在且只有一个 get」。


def test_the_audit_module_never_reads_the_request_body():
    """**结构侧**：``app/api/audit.py`` 里没有任何读请求体的调用。

    ⚠️ 隐私纪律的**两半**：一半是「表里没有能装请求体的列」
    （:class:`AuditLog` 的 9 列，由
    :func:`test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`
    的列名字面量钉住），另一半是本条——**中间件从来不去读它**。

    ⚠️ 这一半**不只是**隐私问题：``BaseHTTPMiddleware`` 下读掉请求体会让下游端点
    拿不到它（除非用 Starlette 的 ``_CachedRequest`` 重放），故「不读体」同时是一条
    **正确性**纪律。⚠️ 而它的失效方向是响亮的（端点会 422「请求体缺失」），
    故本条挡的其实是「有人为了『审计更有用』去读体、然后用 ``_CachedRequest``
    把 422 修掉」这一整条路——那时 422 不响了，只有本条会红。

    ⚠️ 判据是 AST（``node.attr``），不是文本搜索：文本搜索会把 docstring 里
    ``request.body()`` 这个**提及**当成**本身**（硬规矩 #109）——
    而本模块的 docstring 里恰好就有那个提及。
    """
    source = (BACKEND_DIR / "app" / "api" / "audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = [
        f"{node.lineno}: .{node.attr}()"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in ("body", "json", "form", "stream")
    ]
    assert offenders == [], (
        f"app/api/audit.py 读了请求体：{offenders}。审计只记 method/path/status/"
        "subject/target 五格，而 login 的体里有明文口令、bind 的体里有出生日期"
    )
    # ⚠️ 反空转：本文件确实被解析出了东西（指错路径时 ast.parse 会抛，故这一拍
    #    挡的是「有人把中间件搬到别的文件、而本守卫仍然读旧路径」那一档）
    names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert {"should_record", "note_subject", "target_of", "record",
            "AuditMiddleware", "install_audit"} <= names, sorted(names)
    assert pathlib.Path(BACKEND_DIR, "app", "api", "audit.py").is_file()
