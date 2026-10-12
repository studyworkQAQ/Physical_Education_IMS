"""``/api/auth/*`` 那**五个**端点 + ``app/api/deps.py`` 双通道的 HTTP 层守卫（Plan 05A Task 1-C）。

与 ``tests/auth/`` 那两份的分工（刻意不合并）：那两份在**纯 ORM / 纯函数**层跑
（``app.auth`` 不 import ``fastapi``，故它们也不需要 ``TestClient``），本文件跑的是
「HTTP 码与响应体」那一层——即计划 §3.2/§3.3 那两张表里的**每一档**。

⚠️ **本文件里那两条「双通道」的守卫是本计划最要紧的两格**（计划 §2.1）：
生产缺省必须是「只认 cookie」，而既有 1270 条测试全部走请求头
（``tests/conftest.py`` 把 ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``1``）。
于是「生产忘了设这个变量」与「测试把它设成了 1」两件事必须各有一条守卫看着，
否则**任何一档都是静默的**：前者意味着谁都能伪造请求头，后者意味着 1270 条全红。
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    ALLOW_HEADER_IDENTITY_DEFAULT,
    ALLOW_HEADER_IDENTITY_ENV_VAR,
    allow_header_identity,
)
from app.api.routers import auth as auth_router
from app.api.routers.auth import (
    INVALID_CREDENTIALS,
    PASSWORD_ALREADY_BOUND,
    PASSWORD_NOT_BOUND,
)
from app.auth import sessions as auth_sessions
from app.auth.passwords import verify_password
from app.db.models.auth import UserSession
from app.db.models.organisation import (
    CourseSection,
    Enrollment,
    Semester,
    Student,
    Teacher,
)
from app.main import create_app

#: 三个够长的口令（⚠️ **≥ 8 个字符**，:data:`app.auth.passwords.MIN_PASSWORD_LENGTH`）。
#: 刻意互不相同：``test_the_second_of_two_concurrent_binds_…`` 要靠
#: 「库里那一份仍然校验得过**第一个**」来证明第二次绑定没有覆盖它。
PASSWORD = "学生的口令至少八个字"
OTHER_PASSWORD = "另一个人的口令也够长"
ADMIN_PASSWORD = "管理员的口令也够长"

STUDENT_NO = "S2025001"
BIRTH = dt.date(2006, 3, 4)
STAFF_NO = "T0001"
ADMIN_NO = "A0001"


@pytest.fixture()
def people(engine):
    """一个宽学期 + 一个学生 + 一个普通教师 + 一个管理员（``role='admin'``）。

    ⚠️ **那个学期是承重的**：``/api/teacher/students/{id}/weekly-sheet`` 要按
    ``as_of`` 所属的学期判任教关系（:func:`app.pipeline.percentile_stage.current_semester_of`），
    而一个**没有任何学期**的库会让它抛 ``ValueError`` → 422，
    于是本文件里那几条「cookie 身份也能走到任教闸门」的守卫会红在一个与鉴权无关的码上。
    区间刻意宽到覆盖今天（2020–2030），故它不随墙钟漂。

    ⚠️ **用完即关**（``with Session(...)``）：``tests/api/conftest.py`` 的模块 docstring
    交代了 StaticPool 下全进程只有一条 DBAPI 连接，留一个开着事务的 ``Session``
    会与请求里 ``get_db`` 的 ``Session`` 抢它。
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


def _bind_student(client, *, student_no=STUDENT_NO, birth=BIRTH, password=PASSWORD):
    return client.post(
        "/api/auth/students/bind",
        json={
            "student_no": student_no,
            "birth": birth.isoformat() if isinstance(birth, dt.date) else birth,
            "password": password,
        },
    )


def _bind_teacher(client, *, staff_no, name, password):
    return client.post(
        "/api/auth/teachers/bind",
        json={"staff_no": staff_no, "name": name, "password": password},
    )


def _login(client, kind, login, password):
    return client.post(
        "/api/auth/login",
        json={"kind": kind, "login": login, "password": password},
    )

#: **不带任何班**的教师工号（:func:`classes` 夹具插的那一行）。
#: ⚠️ 它是「管理员越过任教范围闸门」那条守卫的**对照**：
#: 没有「一个不带班的普通教师被 403 掉」，「管理员被放行」就证明不了闸门真的在判。
CLASSLESS_NO = "T0002"


def engine_of(client):
    """``TestClient`` → 它那个 app 的引擎（``app.state.engine``）。"""
    return client.app.state.engine


# ---------------------------------------------------------------------------
# ① 双通道：生产缺省必须是「只认 cookie」
# ---------------------------------------------------------------------------


def test_the_header_identity_channel_is_closed_by_default(monkeypatch):
    """**计划 §2.1 要的那条守卫**：缺省 ``"0"`` ⇒ 匿名带 ``X-Student-Id`` 也是 **401**。

    三拍，缺一不可：

    ① **常量本身**是 ``"0"``（字面量，不从被测函数反推）；
    ② ``monkeypatch.delenv`` 之后 :func:`allow_header_identity` 回 ``False``
       ——⚠️ 少了①，「常量改成 1、而函数仍然读它」是绿的；
       ⚠️ 少了②，「常量是 0、而函数写反了」是绿的；
    ③ **实发一次请求**：``monkeypatch.delenv`` 之后**重建一个 app**
       （计划逐字要求的形状；⚠️ 而 ``allow_header_identity()`` 是**请求时**读环境变量的，
       故重建其实不是必需的——重建的价值是「即使有人把它改成 import 期读，
       本条仍然测的是那个进程真的没设这个变量」），匿名带 ``X-Student-Id: 1``
       读 ``/api/students/1/home`` 必须是 **401 ``unauthenticated``**。

    ⚠️ **失效形态是静默的**（这正是本条存在的全部理由）：生产环境忘了设
    ``PE_ALLOW_HEADER_IDENTITY=0``——⚠️ 说反了，是**忘了它缺省就是 0 而顺手设成 1**，
    或者更常见的是「有人把缺省值改成 1 好让本地开发省事」。两种情况下
    **任何功能测试都不会红**（请求头身份照旧能用、前端照旧能跑），
    而任何人只要写一个 ``X-Student-Id: 4`` 就能读走学生 4 的全部数据。

    ⚠️ 第 ④ 拍是**对照**：把开关打开，同一个请求**不是** 401
    （它是 403，因为 ``require_scope`` 的第二支查不到那个在册学生）。
    少了这一拍，「把 ``current_student`` 改成一律抛 401」也能让 ③ 绿——
    而那会毁掉全部 1270 条既有测试所依赖的那条通道。
    """
    assert ALLOW_HEADER_IDENTITY_ENV_VAR == "PE_ALLOW_HEADER_IDENTITY"
    assert ALLOW_HEADER_IDENTITY_DEFAULT == "0"
    monkeypatch.delenv(ALLOW_HEADER_IDENTITY_ENV_VAR, raising=False)
    assert allow_header_identity() is False

    # ⚠️ 一个全新的 app + 全新的空库：不复用 client 夹具（那个进程的 conftest 已经把
    # 开关设成 1 了，而 monkeypatch.delenv 只影响本测试进程的环境变量——
    # 环境变量是进程级的，故 delenv 之后新建的 app 与既有 app 看到的是同一个环境）。
    production = create_app(db_url="sqlite://")
    with TestClient(production) as closed:
        got = closed.get("/api/students/1/home", headers={"X-Student-Id": "1"})
    assert got.status_code == 401, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "unauthenticated"
    assert ALLOW_HEADER_IDENTITY_ENV_VAR in got.json()["error"]["message"]

    # 教师那一侧同样关着（两个依赖各测一次：它们是两个函数，
    # 只测一个的话另一个漏掉 raise 也照样全绿——口径同 test_scope.py 的那条）
    with TestClient(production) as closed:
        got = closed.get(
            "/api/teacher/students/1/weekly-sheet",
            headers={"X-Teacher-Staff-No": STAFF_NO},
        )
    assert got.status_code == 401, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "unauthenticated"

    # ④ 对照：开关打开之后，同一个请求**不是** 401
    monkeypatch.setenv(ALLOW_HEADER_IDENTITY_ENV_VAR, "1")
    assert allow_header_identity() is True
    with TestClient(production) as opened:
        got = opened.get("/api/students/1/home", headers={"X-Student-Id": "1"})
    assert got.status_code == 403, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "forbidden", (
        "开关打开之后应当放行到 require_scope 的第二支（查不到在册学生 → 403），"
        "而它仍然是 401 意味着 current_student 根本没有回落请求头那一档"
    )


def test_the_header_channel_still_carries_the_existing_1270_tests(client, people):
    """**绿档半边**（硬规矩 #50）：开关开着时，请求头身份照旧能用。

    ⚠️ 本条与 1270 条既有测试是**同一件事的两个住址**，故它看起来是冗余的——
    而它不冗余：那 1270 条测的是**业务规则**（它们只是顺带用了请求头），
    没有一条的**主语**是「请求头通道开着」。少了本条，
    「把过渡通道整个删掉」会红在 1270 个离真因很远的地方，
    而报错信息里没有一处会提到 ``PE_ALLOW_HEADER_IDENTITY``。
    """
    assert allow_header_identity() is True, "根 conftest 没有把开关设成 1"
    got = client.get(
        f"/api/students/{people['student']}/notifications",
        headers={"X-Student-Id": str(people["student"])},
    )
    assert got.status_code == 200, got.text
    got = client.get(
        f"/api/teacher/students/{people['student']}/weekly-sheet",
        headers={"X-Teacher-Staff-No": STAFF_NO},
    )
    # ⚠️ 这里**不是** 200：没有选课行，故 require_teaches_student 给 403。
    # 本条要钉的是「请求头被**认出来了**」（不是 401），故 403 正是答案。
    assert got.status_code == 403, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "forbidden"


# ---------------------------------------------------------------------------
# ② 绑定：四档错误 + 「不在册」与「验身材料不符」不可区分
# ---------------------------------------------------------------------------


def test_bind_student_success_is_204_and_stores_a_verifiable_hash(client, people, engine):
    """成功档：204、**没有响应体**、库里那一列是一个**能校验**的自描述串。

    ⚠️ **成功后不自动登录**（不回 ``Set-Cookie``）：绑定与登录是两件事。
    理由是「绑定成功即已认证」会让「验身材料泄漏」直接等于「账号被接管」，
    而分开之后攻击者还需要口令。故本条同时断言 ``me`` 仍然是 401。
    """
    got = _bind_student(client)
    assert got.status_code == 204, got.text
    assert got.content == b"", got.content
    assert "set-cookie" not in {k.lower() for k in got.headers}
    assert client.get("/api/auth/me").status_code == 401

    with Session(engine) as session:
        row = session.get(Student, people["student"])
        assert row.password_hash is not None
        assert row.password_hash.startswith("pbkdf2_sha256$")
        assert row.password_bound_at is not None
        assert verify_password(PASSWORD, row.password_hash) is True
        assert verify_password(OTHER_PASSWORD, row.password_hash) is False


def test_bind_student_gives_the_same_code_and_message_for_a_stranger_and_a_wrong_birth(
    client, people
):
    """**两档不可区分**（计划 §3.2 逐字要求）：同一个 403 + 同一个 code + 同一句 message。

    ⚠️ 区分它们等于把「哪些学号在册」逐个字告诉一个**匿名**调用方
    （他只要拿一个固定的出生日期扫一遍学号，看哪些回「不在册」就知道名册了）。
    ⚠️ 而**这一档的防护强度是有限的**：``GET /api/students`` 今天就匿名返回全部
    学生的 ``birth``，故验身材料本身是公开的。计划 §3.2 自己点出了这个权衡，
    收紧它是 **Task 5**「48 个匿名 GET 的重新裁定」的活。
    本条因此钉的是「**在这个前提下**不额外泄漏」，不是「这一档安全」。

    ⚠️ 三拍都在场：不在册 / 生日不符 / **两个响应体逐字相同**（第三拍是承重的——
    只断两档各自是 403 的话，两句不同的 message 也能全绿，而 message 才是泄漏的那一半）。
    """
    stranger = _bind_student(client, student_no="S9999999")
    wrong_birth = _bind_student(client, birth=dt.date(2000, 1, 1))
    assert stranger.status_code == wrong_birth.status_code == 403
    assert stranger.json() == wrong_birth.json(), (stranger.json(), wrong_birth.json())
    body = stranger.json()["error"]
    assert body["code"] == "forbidden"
    assert body["message"] == "学号或验身材料不正确，无法绑定口令"
    # ⚠️ message 里**不得**出现学号：插进去就等于把「在不在册」变成一个可读的信号
    assert STUDENT_NO not in body["message"]
    assert "S9999999" not in body["message"]
    assert "不在册" not in body["message"] and "出生" not in body["message"]
    # 而正确的那一对仍然 204（否则「一律 403」也能让上面全绿）
    assert _bind_student(client).status_code == 204


def test_bind_student_the_error_tiers_are_in_the_documented_order(client, people, engine):
    """四档错误逐个，**含顺序**：弱口令 422 排在 403 之前、403 排在 409 之前。

    ⚠️ **顺序是承重的**，两个理由：

    * **422 排在最前**：它是纯本地判定、不碰库，故一次弱口令尝试不会变成一次
      数据库查询（一个不需要账号就能打出来的 DoS 面）。
    * **403 排在 409 之前**：反过来的话，一个**不知道出生日期**的攻击者
      就能读出「这个学号绑定过了没有」——而那正是上一档「两档 403 合并」要防的信号，
      从一个别的口子漏出去了。

    ⚠️ 本条把那个「反过来」的形状**实测**了一遍：拿一个错的出生日期去打一个
    **已绑定**的学号，得到的是 403 而不是 409。
    """
    # 弱口令 → 422 unprocessable_value（⚠️ 不是 request_validation_failed）
    short = _bind_student(client, password="短")
    assert short.status_code == 422, short.text
    assert short.json()["error"]["code"] == "unprocessable_value"
    assert "8" in short.json()["error"]["message"]
    # 而它**没有**碰库（弱口令那一档不写 password_hash）
    with Session(engine) as session:
        assert session.get(Student, people["student"]).password_hash is None

    # 请求体缺字段 → 422 request_validation_failed（**另一个** code）
    missing = client.post(
        "/api/auth/students/bind", json={"student_no": STUDENT_NO, "password": PASSWORD}
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "request_validation_failed"

    assert _bind_student(client).status_code == 204

    # 已绑定 → 409 password_already_bound
    again = _bind_student(client, password=OTHER_PASSWORD)
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == PASSWORD_ALREADY_BOUND == "password_already_bound"

    # ⚠️ 顺序那一拍：验身材料不符的 403 **压过** 409
    forged = _bind_student(client, birth=dt.date(2000, 1, 1), password=OTHER_PASSWORD)
    assert forged.status_code == 403, (forged.status_code, forged.json())
    assert forged.json()["error"]["code"] == "forbidden"
    # 而第一次那个口令仍然有效（409 那一档没有把哈希改掉）
    with Session(engine) as session:
        assert verify_password(
            PASSWORD, session.get(Student, people["student"]).password_hash
        )


def test_bind_teacher_is_the_same_shape_with_staff_no_and_name(client, people, engine):
    """教师那一侧：工号 + 姓名，四档同构，且**绑定不会把人变成管理员**。

    ⚠️ ``teacher`` 表实测**有** ``name`` 列（``['id','staff_no','name']``），
    故计划 §3.2 那一格的假设成立、不需要顶回。
    ⚠️ **``role`` 不由本端点决定**是承重的：若绑定请求体能带 ``role``，
    任何人就能把自己绑成管理员（``POST /api/teachers`` 仅管理员可调，
    而绑定端点是**匿名**的）。本条用一个多带 ``role`` 的请求体实测那一格被忽略。
    """
    stranger = _bind_teacher(client, staff_no="NOPE", name="李老师", password=ADMIN_PASSWORD)
    wrong_name = _bind_teacher(client, staff_no=STAFF_NO, name="别的名字", password=ADMIN_PASSWORD)
    assert stranger.status_code == wrong_name.status_code == 403
    assert stranger.json() == wrong_name.json()
    assert stranger.json()["error"]["message"] == "工号或验身材料不正确，无法绑定口令"

    short = _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password="短")
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "unprocessable_value"

    # ⚠️ 多带一个 role 键：Pydantic 缺省 extra="ignore"，故它被静默丢掉
    smuggled = client.post(
        "/api/auth/teachers/bind",
        json={
            "staff_no": STAFF_NO, "name": "李老师",
            "password": ADMIN_PASSWORD, "role": "admin",
        },
    )
    assert smuggled.status_code == 204, smuggled.text
    with Session(engine) as session:
        teacher = session.get(Teacher, people["teacher"])
        assert teacher.role == "teacher", (
            "绑定请求体里的 role 生效了：任何人可以把自己绑成管理员"
        )
        assert verify_password(ADMIN_PASSWORD, teacher.password_hash)
        assert teacher.password_bound_at is not None

    again = _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password=OTHER_PASSWORD)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == PASSWORD_ALREADY_BOUND


def test_the_second_of_two_concurrent_binds_is_409_not_a_silent_overwrite(
    client, people, engine, monkeypatch
):
    """**计划 §2.3 第 5 条要的那条守卫**：判据是 UPDATE 的**影响行数**，不是「读出来是 NULL」。

    ⚠️ **失效形态**：若实现是「先 SELECT 出 ``password_hash is None``、再 UPDATE」
    （check-then-act），两个并发请求的 SELECT 都在任何一个 UPDATE 之前发生，
    于是**两个都能过**——第二个 UPDATE 覆盖第一个的哈希，而两个请求都拿到 204。
    用户以为自己的口令生效了，实际生效的是另一个人的（而另一个人可能是攻击者：
    他知道验身材料、抢先绑定，于是受害者的「绑定成功」是一次静默的账号接管）。

    ⚠️ **对策与判据**：检查搬进 UPDATE 的 ``WHERE``（``… AND password_hash IS NULL``），
    据 ``rowcount`` 判 409。本条因此**直接量那个 rowcount**（用一个替身把
    :func:`app.api.routers.auth._bind_credential` 的返回值抄下来），
    而不只是断言「第二个请求是 409」——后者对 check-then-act 也是绿的
    （只要两次请求是**串行**发的，第二次读到的就已经是非 NULL 了）。
    ⚠️ 于是本条钉的是**机制**（rowcount == 0），不是**症状**（409）。

    ⚠️ 第三拍是「没有静默覆盖」的正面证据：409 之后，用**第一个**口令登录仍然成功、
    用第二个口令仍然失败。少了这一拍，「rowcount 对、但 UPDATE 的 values 写错了」
    也是绿的。
    """
    assert _bind_student(client).status_code == 204

    seen: list[int] = []
    real = auth_router._bind_credential

    def spy(*args, **kwargs):
        affected = real(*args, **kwargs)
        seen.append(affected)
        return affected

    monkeypatch.setattr(auth_router, "_bind_credential", spy)
    second = _bind_student(client, password=OTHER_PASSWORD)
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == PASSWORD_ALREADY_BOUND
    assert seen == [0], (
        f"第二次绑定的影响行数是 {seen}，不是 [0]：说明判据不是 UPDATE 的 WHERE，"
        f"而是一个 check-then-act（两个并发请求都能过）"
    )

    # ⚠️ 替身要还原（monkeypatch 会做），但这里显式复跑一次「第一次绑定」的 rowcount 是 1
    monkeypatch.undo()
    seen.clear()
    monkeypatch.setattr(auth_router, "_bind_credential", spy)
    with Session(engine) as session:
        session.get(Student, people["student"]).password_hash = None
        session.commit()
    assert _bind_student(client).status_code == 204
    assert seen == [1], seen

    # 没有静默覆盖：第一个口令仍然有效、第二个仍然无效
    assert _login(client, "student", STUDENT_NO, PASSWORD).status_code == 200
    client.cookies.clear()
    denied = _login(client, "student", STUDENT_NO, OTHER_PASSWORD)
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == INVALID_CREDENTIALS


# ---------------------------------------------------------------------------
# ③ 登录：两档失败必须区分 + cookie 的参数
# ---------------------------------------------------------------------------


def test_login_distinguishes_not_bound_from_a_wrong_password(client, people):
    """**计划 §3.3 逐字要求的两档**：403 ``password_not_bound`` vs 401 ``invalid_credentials``。

    ⚠️ 这**确实**泄漏了「这个学号在不在册」——控制者裁定**接受**，三条理由：
    ① 原型不做防枚举；② 绑定流程本身就需要这个信号（不然用户不知道自己是「没注册」
    还是「口令错」，而两者要的下一步动作**相反**）；③ ``GET /api/students`` 今天就
    匿名返回全部 60 人。已写进 spec 的已知局限。
    ⚠️ 于是它与 :func:`test_bind_student_gives_the_same_code_and_message_…` 的口径
    **相反**（那里两档要不可区分），两处各写一段散文说明，刻意不合并。

    ⚠️ 三档都在场：不在册 / 在册未绑定 / 已绑定但口令错。前两档**共用**一个 code
    （都是「去绑定」），第三档是另一个（「重输」）。
    """
    stranger = _login(client, "student", "S9999999", PASSWORD)
    unbound = _login(client, "teacher", STAFF_NO, ADMIN_PASSWORD)
    assert stranger.status_code == unbound.status_code == 403
    assert stranger.json()["error"]["code"] == PASSWORD_NOT_BOUND == "password_not_bound"
    assert unbound.json()["error"]["code"] == PASSWORD_NOT_BOUND

    assert _bind_student(client).status_code == 204
    wrong = _login(client, "student", STUDENT_NO, OTHER_PASSWORD)
    assert wrong.status_code == 401, wrong.text
    assert wrong.json()["error"]["code"] == INVALID_CREDENTIALS == "invalid_credentials"
    assert wrong.json()["error"]["message"] != stranger.json()["error"]["message"], (
        "两档的 message 必须不同：它们要的下一步动作相反（去绑定 / 重输口令）"
    )

    # kind 不在取值域里 → 422（Pydantic 那一档，不是上面两档）
    bad_kind = _login(client, "校长", STUDENT_NO, PASSWORD)
    assert bad_kind.status_code == 422
    assert bad_kind.json()["error"]["code"] == "request_validation_failed"

    # 绿档
    good = _login(client, "student", STUDENT_NO, PASSWORD)
    assert good.status_code == 200, good.text


def test_login_sets_the_cookie_with_the_documented_parameters(client, people, monkeypatch):
    """``Set-Cookie`` 的六格逐个（**不含 ``Domain``**），且 ``Max-Age`` 与 TTL 同源。

    ⚠️ 期望侧是**字面量**（``pe_session`` / ``7200`` / ``Path=/`` / ``HttpOnly`` /
    ``SameSite=lax``），不从 :func:`app.auth.sessions.cookie_kwargs` 反推
    （反推就是同源：把 ``max_age`` 改成 86400 两边一起改、断言恒成立，
    而那正是计划 §3.4 点名要防的「一个写 7200 一个写 86400」）。
    ⚠️ **``Domain`` 必须不在**：不传就是宿主限定；写 ``Domain=localhost`` 会让 cookie
    对 ``*.localhost`` 全部子域可见，那是计划 §3.5 那条 CSRF 论证**挡不住**的一档。
    ⚠️ **``Secure`` 只在 ``PE_ENV=production`` 时出现**（两拍都测）：
    原型跑在明文 HTTP 上，而带 ``Secure`` 的 cookie **在明文 HTTP 上根本不会被浏览器
    存下来**，故「一律加 Secure」的表现是「本地演示谁都登录不了」。
    """
    monkeypatch.delenv(auth_sessions.ENV_VAR, raising=False)
    _bind_student(client)
    got = _login(client, "student", STUDENT_NO, PASSWORD)
    assert got.status_code == 200, got.text
    raw = got.headers["set-cookie"]
    assert raw.startswith("pe_session="), raw
    assert "HttpOnly" in raw, raw
    assert "Max-Age=7200" in raw, raw
    assert "Path=/" in raw, raw
    assert "SameSite=lax" in raw, raw
    assert "Secure" not in raw, raw
    assert "Domain" not in raw, raw
    assert "Domain=" not in raw, raw
    # 那一串是不透明随机值，且长度与列宽逐字对齐（64）
    value = raw.split("pe_session=", 1)[1].split(";", 1)[0]
    assert len(value) == 64, (len(value), value)
    assert not value.isdigit()

    # 生产档：Secure 出现，其余五格不变
    monkeypatch.setenv(auth_sessions.ENV_VAR, auth_sessions.PRODUCTION)
    client.cookies.clear()
    secure = _login(client, "student", STUDENT_NO, PASSWORD)
    secure_raw = secure.headers["set-cookie"]
    assert "Secure" in secure_raw, secure_raw
    assert "HttpOnly" in secure_raw and "Max-Age=7200" in secure_raw
    assert "SameSite=lax" in secure_raw and "Path=/" in secure_raw
    assert "Domain" not in secure_raw


def test_login_and_me_return_exactly_the_same_body_and_role_decides_the_landing(
    client, people
):
    """``login`` 与 ``me`` 的响应体**逐字相同**（六格），且三种身份各回各的 ``role``。

    ⚠️ 前端登录后要立刻知道「我该跳哪个首页」（学生 → ``/s/home``、教师 →
    ``/t/dashboard``、管理员 → ``/admin``，计划 §4.1），而刷新页面时它只能问 ``me``。
    两个端点回两份不同形状的话，那段跳转逻辑就要写两遍、并且迟早漂开。
    ⚠️ 先例是 ``dashboard._student_home_response``（学生侧与教师侧的首页逐字同形）。

    ⚠️ **学号与工号是互斥的两格**（学生那一档 ``staff_no is None``、反之亦然），
    而两格而不是一个 ``login`` 的理由逐字见
    :class:`app.api.schemas.auth.SessionIdentityRead` 的 docstring。
    """
    _bind_student(client)
    _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password=ADMIN_PASSWORD)
    _bind_teacher(client, staff_no=ADMIN_NO, name="王干事", password=ADMIN_PASSWORD)

    student_login = _login(client, "student", STUDENT_NO, PASSWORD).json()
    assert client.get("/api/auth/me").json() == student_login
    assert student_login == {
        "kind": "student",
        "id": people["student"],
        "name": "张三",
        "role": "student",
        "student_no": STUDENT_NO,
        "staff_no": None,
    }

    client.cookies.clear()
    teacher_login = _login(client, "teacher", STAFF_NO, ADMIN_PASSWORD).json()
    assert client.get("/api/auth/me").json() == teacher_login
    assert teacher_login["role"] == "teacher"
    assert teacher_login == {
        "kind": "teacher", "id": people["teacher"], "name": "李老师",
        "role": "teacher", "student_no": None, "staff_no": STAFF_NO,
    }

    client.cookies.clear()
    admin_login = _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD).json()
    assert client.get("/api/auth/me").json() == admin_login
    assert admin_login["role"] == "admin"
    assert admin_login["kind"] == "teacher", (
        "管理员不是第三种 kind：他就是一行 role='admin' 的 teacher"
        "（用户 2026-10-12 的裁定「管理员接管管理台」落地成一个标签）"
    )


# ---------------------------------------------------------------------------
# ④ 登出：服务端真的失效
# ---------------------------------------------------------------------------


def test_an_old_cookie_stops_working_the_moment_the_user_logs_out(client, people, engine):
    """**登出是真的失效**（本计划选服务端会话表的第一条理由）。

    三拍：① 登出 204 且 ``Set-Cookie`` 让 cookie 过期；② **同一个 cookie** 再打
    ``me`` 是 401；③ 库里那一行的 ``revoked_at`` 被写上了（行**没有被删掉**——留痕）。

    ⚠️ 签名 cookie 的「登出」只是客户端把那串丢掉，被偷走的 cookie 在 ``exp`` 之前
    照旧有效；用户 2026-10-12 说现状「有点太粗糙了」，而「登出登不掉」正是那一类粗糙。
    ⚠️ 第 ② 拍必须**显式带着登出前那一串**（``client.cookies.clear()`` 之后手工塞回去）：
    若只靠 ``TestClient`` 的 cookie jar，第 ① 拍的 ``Set-Cookie`` 已经把 jar 清掉了，
    于是第 ② 拍打出去的是「没有 cookie」——那当然是 401，而它证明不了「被偷的那一份失效了」。
    """
    _bind_student(client)
    login = _login(client, "student", STUDENT_NO, PASSWORD)
    stolen = login.cookies.get(auth_sessions.SESSION_COOKIE_NAME)
    assert stolen and len(stolen) == 64
    assert client.get("/api/auth/me").status_code == 200, "前提：这个 cookie 本来是有效的"

    out = client.post("/api/auth/logout")
    assert out.status_code == 204, out.text
    assert out.content == b""
    cleared = out.headers["set-cookie"]
    assert cleared.startswith('pe_session=""') or cleared.startswith("pe_session=;"), cleared
    assert "Max-Age=0" in cleared, cleared
    assert "1970" in cleared, ("Expires 应当落在纪元，实测：", cleared)
    assert "Path=/" in cleared and "SameSite=lax" in cleared, (
        "删除 cookie 的 path/samesite 必须与签发时逐字相同，否则删不掉（RFC 6265 按 "
        "(name, domain, path) 三元组匹配）"
    )

    # ② 被偷的那一份立刻失效
    client.cookies.clear()
    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, stolen)
    got = client.get("/api/auth/me")
    assert got.status_code == 401, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "unauthenticated"
    # 学生端点也一样（它走的是 current_student 的 cookie 那一档）
    assert client.get(
        f"/api/students/{people['student']}/notifications"
    ).status_code == 401

    # ③ 行还在、revoked_at 被写上了
    with Session(engine) as session:
        row = session.get(UserSession, stolen)
        assert row is not None, "登出把行删了：那就查不出「这个人什么时候登出的」"
        assert row.revoked_at is not None

    # 再登出一次 → 401（身份已经解析不出来了），而服务端不报错、不改坏数据
    again = client.post("/api/auth/logout")
    assert again.status_code == 401
    with Session(engine) as session:
        assert session.get(UserSession, stolen).revoked_at is not None


def test_a_session_whose_subject_has_been_deleted_is_revoked_on_the_next_request(
    client, people, engine
):
    """⚠️ **计划 §3.1 标注「本计划最容易漏的一格」的 HTTP 层那一半**：
    删掉一个学生 ⇒ 他的旧 cookie **立刻 401**（不是 500、也不是照常放行）。

    ``user_session.subject_id`` 刻意不是外键（多态外键在 SQL 里不存在），故：
    ① 删学生**不会**级联删他的会话行；② :func:`app.api.crud._child_tables`
    也**探测不到**它，于是 ``DELETE /api/students/{id}`` 的 ``restrict`` 那一档看不见它。
    两档都没有 DB 机制会挡，唯一的处置是解析时回查、查无此人当场吊销。
    （纯 ORM 层的那一半住在 ``tests/auth/test_sessions.py``。）

    ⚠️ **不是 500** 这一格尤其要紧：一个天真的实现会在 ``Identity.name`` 上撞
    ``AttributeError``（``None.name``），经 :mod:`app.api.errors` 的兜底折成 500 +
    一句固定的「服务器内部错误」——于是运维看到的是一串 500，而真因是
    「有人从名册上删了一个人」。
    """
    _bind_student(client)
    login = _login(client, "student", STUDENT_NO, PASSWORD)
    token = login.cookies.get(auth_sessions.SESSION_COOKIE_NAME)
    assert client.get("/api/auth/me").status_code == 200

    with Session(engine) as session:
        session.delete(session.get(Student, people["student"]))
        session.commit()
        # ⚠️ 前提取证：会话行**没有**被级联删掉（它要是被删了，本条就只是在测 404/401
        # 的一个平凡档，而「当场吊销」那一格根本没被覆盖到）
        assert session.get(UserSession, token) is not None
        assert session.get(UserSession, token).revoked_at is None

    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, token)
    got = client.get("/api/auth/me")
    assert got.status_code == 401, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "unauthenticated"

    with Session(engine) as session:
        row = session.get(UserSession, token)
        assert row is not None
        assert row.revoked_at is not None, "拒绝了但没有吊销：库里查不出这个人为什么被踢"

    # 学生侧的端点同样 401（它走 current_student 的 cookie 那一档）
    assert client.get(
        f"/api/students/{people['student']}/notifications"
    ).status_code == 401


def test_an_expired_session_is_401_but_is_not_marked_as_revoked(client, people, engine):
    """过期 ⇒ 401，而 ``revoked_at`` **保持 NULL**（过期不等于被吊销）。

    ⚠️ 两档在库里必须可区分：``revoked_at`` 是**审计事实**（有人登出了、或运维踢了人、
    或 subject 被删了），而「时间到了」不是。把过期也标成吊销会让
    「谁在什么时候被踢了」这个问题失去答案。
    """
    _bind_student(client)
    login = _login(client, "student", STUDENT_NO, PASSWORD)
    token = login.cookies.get(auth_sessions.SESSION_COOKIE_NAME)
    with Session(engine) as session:
        row = session.get(UserSession, token)
        row.expires_at = auth_sessions.now() - dt.timedelta(seconds=1)
        session.commit()

    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, token)
    got = client.get("/api/auth/me")
    assert got.status_code == 401, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "unauthenticated"
    with Session(engine) as session:
        assert session.get(UserSession, token).revoked_at is None, (
            "过期被标成了吊销：两档在库里不再可区分"
        )


def test_the_sliding_expiry_pushes_expires_at_forward_on_an_authenticated_request(
    client, people, engine
):
    """**滑动过期**：一个带有效 cookie 的请求把 ``expires_at`` 往后推。

    ⚠️ 判据是「把 ``expires_at`` 拨到只剩 1 分钟，发一次请求，它又变回整整一个 TTL」，
    而不是 ``sleep``（后者既慢又间歇性红）。
    ⚠️ 这就是**不做 refresh 令牌**的那个替代机制（计划 §3.3 末段）：
    「活跃用户永不掉线、不活跃用户两小时后掉线」同时成立。
    """
    _bind_student(client)
    token = _login(client, "student", STUDENT_NO, PASSWORD).cookies.get(
        auth_sessions.SESSION_COOKIE_NAME
    )
    with Session(engine) as session:
        row = session.get(UserSession, token)
        row.expires_at = auth_sessions.now() + dt.timedelta(minutes=1)
        row.last_seen_at = auth_sessions.now() - dt.timedelta(minutes=119)
        session.commit()
        before = row.expires_at

    assert client.get("/api/auth/me").status_code == 200

    with Session(engine) as session:
        row = session.get(UserSession, token)
        assert row.expires_at > before, (row.expires_at, before)
        assert row.expires_at - row.last_seen_at == auth_sessions.SESSION_TTL
        assert row.revoked_at is None


def test_a_forged_or_foreign_cookie_is_401(client, people):
    """伪造的、别的库签发的、以及**别人的**真 token 各一档。

    ⚠️ 第三档是本条存在的理由：前两档对「一律 401」的实现也是绿的，
    而「学生 A 拿到学生 B 的 cookie 就能当 B」是一个**真实**的失效形状
    （它要求 ``resolve`` 认 token 而不认 cookie 的其它属性——本仓正是这么做的，
    故这一档其实会 200 并回 B 的身份；⚠️ **那不是 bug**：cookie 就是 bearer 凭据，
    「谁拿着它谁就是那个人」，防线是 ``HttpOnly`` + ``SameSite`` + HTTPS，
    而不是服务端再判一次「这个 cookie 是不是从这台机器发出去的」。
    本条因此断言的是**它回的是 B 的身份、而不是 A 的**——即 token 与身份
    一一对应，没有串号）。
    """
    assert _bind_student(client).status_code == 204
    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, "A" * 64)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, "!!!not-a-base64-string!!!")
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(auth_sessions.SESSION_COOKIE_NAME, "")
    assert client.get("/api/auth/me").status_code == 401

    # 两个学生各自的 token 不得串号
    with Session(client.app.state.engine) as session:
        session.add(
            Student(student_no="S2025002", name="李四", sex="female",
                    birth=dt.date(2006, 5, 6), grade=1)
        )
        session.commit()
        other_id = session.scalar(
            select(Student.id).where(Student.student_no == "S2025002")
        )
    client.cookies.clear()
    assert client.post(
        "/api/auth/students/bind",
        json={"student_no": "S2025002", "birth": "2006-05-06", "password": OTHER_PASSWORD},
    ).status_code == 204
    first = _login(client, "student", STUDENT_NO, PASSWORD).json()
    second = _login(client, "student", "S2025002", OTHER_PASSWORD).json()
    assert first["id"] == people["student"] and second["id"] == other_id
    assert first["student_no"] != second["student_no"]


def test_a_cookie_of_one_kind_cannot_be_used_as_the_other(client, people):
    """教师的 cookie 打学生端点 → **403**（不是 401）；反之亦然。

    ⚠️ 403 而不是 401：请求者**已经登录了**，只是不是这个端点要的那一类人。
    ``unauthenticated`` 说的是「我不知道你是谁」，而这里我们知道。
    与 :func:`app.api.deps.require_scope` 的「身份与目标不符 → 403」同一条口径。
    """
    _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password=ADMIN_PASSWORD)
    assert _login(client, "teacher", STAFF_NO, ADMIN_PASSWORD).status_code == 200
    got = client.get(f"/api/students/{people['student']}/notifications")
    assert got.status_code == 403, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "forbidden"
    assert "teacher" in got.json()["error"]["message"]

    _bind_student(client)
    client.cookies.clear()
    assert _login(client, "student", STUDENT_NO, PASSWORD).status_code == 200
    got = client.get(
        f"/api/teacher/students/{people['student']}/weekly-sheet"
    )
    assert got.status_code == 403, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "forbidden"
    assert "student" in got.json()["error"]["message"]


def test_a_cookie_identity_reaches_the_same_gates_as_the_header_one(client, people):
    """**双通道的同形性**：cookie 解析出来的教师身份与请求头那一档**对下游同形**。

    ⚠️ 这一格是「教师侧端点一行都不用改」的全部理由：
    :func:`app.api.deps.current_teacher` 交出的是**工号字符串**（两档都是），
    故 ``require_teacher`` 一族、以及写进 ``prescription.teacher_overrides`` 的
    ``teacher_staff_no`` 那一格，都不知道也不关心身份是从哪条通道来的。
    ⚠️ 判据用 403 而不是 200：这个教师没有选课行，故 ``require_teaches_student``
    给 403——而 403 恰恰证明「工号被认出来了、并且真的去查了任教关系」
    （没认出来的话是 401）。
    """
    _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password=ADMIN_PASSWORD)
    assert _login(client, "teacher", STAFF_NO, ADMIN_PASSWORD).status_code == 200
    via_cookie = client.get(f"/api/teacher/students/{people['student']}/weekly-sheet")
    client.cookies.clear()
    via_header = client.get(
        f"/api/teacher/students/{people['student']}/weekly-sheet",
        headers={"X-Teacher-Staff-No": STAFF_NO},
    )
    assert via_cookie.status_code == via_header.status_code == 403
    assert via_cookie.json()["error"]["code"] == via_header.json()["error"]["code"]
    assert STAFF_NO in via_cookie.json()["error"]["message"], via_cookie.json()


def test_a_malformed_identity_header_is_422_even_next_to_a_valid_cookie(client, people):
    """⚠️ **实测行为**（此前 ``deps.py`` 里印的是相反的结论，已按实际改写）：
    一个格式错的 ``X-Student-Id`` **仍然**让请求 422，即使 cookie 是有效的。

    FastAPI 在**依赖体运行之前**就把 ``Header`` 参数解析并校验完了，故
    「生产档下请求头被忽略」这句话要精确到：请求头**不参与身份判定**，
    但它**仍然被解析**。如实记录（硬规矩 #39）：它不构成漏洞（两个码都拒绝访问），
    而彻底摘掉它要改一个既有 code（``request_validation_failed`` →
    ``unprocessable_value``），为一个不影响安全的形状去改它不划算。
    """
    _bind_student(client)
    assert _login(client, "student", STUDENT_NO, PASSWORD).status_code == 200
    assert client.get(f"/api/students/{people['student']}/notifications").status_code == 200
    got = client.get(
        f"/api/students/{people['student']}/notifications",
        headers={"X-Student-Id": "abc"},
    )
    assert got.status_code == 422, (got.status_code, got.text)
    assert got.json()["error"]["code"] == "request_validation_failed"
    # ⚠️ 而一个**合法但属于别人**的头在带 cookie 时**完全不起作用**
    # （cookie 那一档先命中，头连读都不读）——这一格才是「忽略请求头」的真意思
    other = client.get(
        f"/api/students/{people['student']}/notifications",
        headers={"X-Student-Id": str(people["student"] + 999)},
    )
    assert other.status_code == 200, (other.status_code, other.text)


# ---------------------------------------------------------------------------
# ⑤ 口令不得出现在任何响应体里
# ---------------------------------------------------------------------------


def test_a_validation_error_never_echoes_the_submitted_password(client, people):
    """**422 的 ``detail`` 里不得出现明文口令**（Plan 05A 实测出来的洞，计划没提）。

    ⚠️ **取证**（改之前实测）::

        POST /api/auth/login {"kind":"student","password":"我的超级机密口令"}   # 漏了 login
        → 422 {"error":{"code":"request_validation_failed", …, "detail":[
             {"type":"missing","loc":["body","login"],"msg":"Field required",
              "input":{"kind":"student","password":"我的超级机密口令"}}]}}

    Pydantic v2 的 ``errors()`` 每一格都带 ``input``，而 ``missing`` 那一档的 ``input``
    是**整个请求体**。它泄漏给的是提交它的那个人（不是第三方），故不是越权；
    但那份响应体会被浏览器 devtools、反代访问日志、APM 采样与前端错误上报各存一份，
    而口令是**跨系统复用**的（CWE-209 / CWE-532）。

    ⚠️ **``SecretStr`` 挡不住这一档**：``missing`` 发生在任何字段被解析之前，
    故 ``input`` 里那一格还是原始 ``str``。故 :mod:`app.api.errors` 另外做了
    一层**按键名脱敏**（``_SENSITIVE_INPUT_KEYS``），两道合起来才封住。
    本条因此把**四个**端点 × 两种失败形状都扫一遍，并断言那个明文串
    **不出现在响应体的任何位置**（不是「不出现在某一格」——逐字扫整个 body
    才不会漏掉下一个新加的字段）。
    """
    secret = "这是一个绝对不会出现在响应体里的口令"
    bodies = [
        # 漏了 login：``missing`` 的 input 是**整个请求体**（取证里那一格）
        client.post("/api/auth/login", json={"kind": "student", "password": secret}),
        # 漏了 password
        client.post("/api/auth/login", json={"kind": "student", "login": STUDENT_NO}),
        # kind 不在取值域里（走 one_of → ValueError → 422）
        client.post("/api/auth/login",
                    json={"kind": "校长", "login": STUDENT_NO, "password": secret}),
        # 绑定那一侧：漏了 birth，input 同样是整个请求体
        client.post("/api/auth/students/bind",
                    json={"student_no": STUDENT_NO, "password": secret}),
        # birth 不是合法日期（这一档的 input 只有那一个值）
        client.post("/api/auth/students/bind",
                    json={"student_no": STUDENT_NO, "birth": "不是日期",
                          "password": secret}),
        # 教师那一侧：漏了 name 与 password，且多带一个会被忽略的键
        client.post("/api/auth/teachers/bind",
                    json={"staff_no": STAFF_NO, "password": secret,
                          "birth": "2006-03-04"}),
        client.post("/api/auth/teachers/bind", json={"staff_no": STAFF_NO}),
    ]
    assert all(got.status_code == 422 for got in bodies), [
        (g.status_code, g.text) for g in bodies
    ]
    for got in bodies:
        assert got.json()["error"]["code"] == "request_validation_failed", got.text
        assert secret not in got.text, got.text
    # ⚠️ 反空转 + 「哪一格错了」仍然可读：脱敏抹掉的是**值**，不是 **loc**。
    # 少了这一拍，「把整个 detail 抹成 None」也能让上面全绿，
    # 而前端就无从说出「你漏了口令」了。
    missing_password = client.post(
        "/api/auth/login", json={"kind": "student", "login": STUDENT_NO}
    )
    locations = [tuple(item["loc"]) for item in missing_password.json()["error"]["detail"]]
    assert ("body", "password") in locations, locations
    assert all(item["msg"] for item in missing_password.json()["error"]["detail"])
    # ⚠️ 反空转：那个串**确实**被提交上去了（否则上面全是空转绿）
    assert _login(client, "student", STUDENT_NO, secret).status_code in (401, 403)


def test_the_redactor_is_recursive_and_only_keyed_on_the_name():
    """``_redact`` 的三格：递归到嵌套 dict、展开 list、且**只按键名**判。

    ⚠️ 「只按键名」是有意的（:data:`app.api.errors._SENSITIVE_INPUT_KEYS` 的注释
    逐字写了理由）：按「值看起来像口令」判要一份启发式，而启发式必然漏
    （一个 8 位的随机串与一个 8 位的学号在形状上无法区分），漏的那一次是静默的。
    ⚠️ 本条因此**也钉住它不做什么**：一个值等于口令、但键名不敏感的格子**不脱敏**
    ——那是已知的、被接受的边界，而不是一个待修的 bug。
    """
    from app.api.errors import _REDACTED, _SENSITIVE_INPUT_KEYS, _redact

    assert _SENSITIVE_INPUT_KEYS == {"password", "password_hash", "rpe_token"}
    assert _REDACTED == "***"
    assert _redact({"password": "S3cret", "kind": "student"}) == {
        "password": "***", "kind": "student",
    }
    assert _redact({"a": [{"password": "S3cret"}, ["rpe_token"]], "b": 1}) == {
        "a": [{"password": "***"}, ["rpe_token"]], "b": 1,
    }
    # 键名不敏感 ⇒ 原样保留（哪怕值就是那个口令）
    assert _redact({"note": "S3cret"}) == {"note": "S3cret"}
    # 标量 / None / tuple 各一档（⚠️ tuple 展开成 list，而**值**不被判：只认键名）
    assert _redact(None) is None
    assert _redact("password") == "password"
    assert _redact(("password", 1)) == ["password", 1]


def test_no_credential_column_appears_in_any_response_body(client, people):
    """``password_hash`` 在**五个鉴权端点**与**四个 CRUD 端点**的响应体里都不出现。

    ⚠️ 两半各有一个住址（``tests/api/test_crud.py`` 的档 1 / 档 2 清单钉的是
    23 个资源那一侧），本条钉的是**鉴权端点这一侧**：绑定与登录都要读那一列，
    故「顺手把它放进响应体」是一次很容易犯的错误。
    ⚠️ 判据是**逐字扫整个响应体文本**，不是「某个键不在某个 dict 里」——
    后者对「它藏在 ``detail`` 里」无感。
    ⚠️ 扫的是两个串：**哈希值的前缀** ``pbkdf2_sha256$``（那一列的真实内容）与
    **带引号的键名** ``"password_hash"``（它作为一个 JSON 键出现）。
    ⚠️ **不扫裸的 ``password_hash``**：409 的 message 里逐字写着
    「把 ``student.password_hash`` 置回 NULL」——那是一句给教务干事看的运维提示，
    它提到那一列的**名字**、而不是那一列的**值**。扫裸名会把那句提示判成泄漏
    （实现者第一次跑就红在这里，故按实际改写）。
    """
    _bind_student(client)
    _bind_teacher(client, staff_no=ADMIN_NO, name="王干事", password=ADMIN_PASSWORD)
    responses = [
        _bind_student(client, password=OTHER_PASSWORD),          # 409
        _login(client, "student", STUDENT_NO, PASSWORD),          # 200
        _login(client, "student", STUDENT_NO, OTHER_PASSWORD),    # 401
        client.get("/api/auth/me"),                               # 200
        client.post("/api/auth/logout"),                          # 204
    ]
    # ⚠️ **Plan 05A Task 5 起那 4 个名册读要教职身份**（``students`` / ``teachers``
    #    各自的集合与成员 GET）：它们匿名可读时，返回体里含着**绑定口令的全部验身材料**
    #    （学生的 ``birth``；教师的 ``staff_no`` + ``name``）。故这里先以管理员登录一次
    #    （``TestClient`` 自带 cookie jar，上面那一发 logout 已经把它清掉了），
    #    再打那 4 个 —— ⚠️ 而**「先登出、再登录」这个顺序是承重的**：
    #    它顺带证明了登出真的把 cookie 清掉了（否则本段的 4 个请求会是
    #    「带着上一个学生的会话」发出去的，而学生身份打名册是 403）。
    _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD)
    assert client.get("/api/auth/me").json()["role"] == "admin"
    responses += [
        client.get("/api/students"),                              # 教职 list
        client.get(f"/api/students/{people['student']}"),         # 教职 read-one
        client.get("/api/teachers"),
        client.get(f"/api/teachers/{people['admin']}"),
    ]
    for got in responses:
        assert '"password_hash"' not in got.text, (got.request.url, got.text[:400])
        assert "pbkdf2_sha256$" not in got.text, (got.request.url, got.text[:400])
    # ⚠️ 反空转：那一列**确实**有值（否则上面全是空转绿）
    with Session(client.app.state.engine) as session:
        assert session.get(Student, people["student"]).password_hash is not None
        assert session.get(Teacher, people["admin"]).password_hash is not None
    # ⚠️⚠️ **安全收紧波把这两拍反了过来**：``password_bound_at`` 此前是**暴露**的
    #    （本处逐字写的是「它不是凭据，管理台要看『谁还没注册』」），本波把它从
    #    ``StudentRead`` / ``TeacherRead`` 与两行的 ``list_exclude`` 上一起摘掉了
    #    （控制者裁定 3）：它告诉一个教职**哪些账号还没绑口令** = **哪些还能被抢占绑定**
    #    （``bind`` 只对 ``password_hash IS NULL`` 的行放行，故它挡不住抢占）。
    #    ⚠️ 逐字理由与「四处缺一不可」的形状住在
    #    ``app/api/schemas/organisation.py`` 的 ``TeacherRead``；三拍守卫是
    #    ``tests/api/test_crud.py`` 的
    #    ``test_password_bound_at_is_absent_from_both_the_read_model_and_the_list``。
    #    ⚠️ 本处**保留这两拍**（而不是删掉）：它是「凭据列不出现在响应体里」这条
    #    全仓级断言的一部分，而它跑的是一份**真的登录过的 cookie 会话**
    #    （上面那 4 个名册读就是用它发的），与 test_crud.py 那条（走请求头通道）
    #    是两条不同的通道 —— 两条都在场才封住「只在一条通道上摘掉了」。
    assert "password_bound_at" not in client.get("/api/teachers").text
    assert "password_bound_at" not in client.get(f"/api/students/{people['student']}").text
    # role 也暴露（前端的路由守卫要靠它决定跳 /admin 还是 /t/dashboard）
    assert client.get(f"/api/teachers/{people['admin']}").json()["role"] == "admin"


def test_no_auth_schema_mentions_a_credential_column():
    """五个模型的字段集里**没有** ``password_hash`` / ``password_bound_at``。

    ⚠️ 它是上一条的**结构面**对偶：上一条量的是响应体（运行时），本条量的是
    ``model_fields``（导入期）。两条都在场，因为「把 ``password_hash`` 加进
    ``SessionIdentityRead``」这一次改动会让上一条红在**四个**端点上、
    而报错信息指向的是那四个端点，不是那个模型。
    """
    from app.api.schemas import auth as auth_schemas

    for model in (
        auth_schemas.StudentBindCreate,
        auth_schemas.TeacherBindCreate,
        auth_schemas.LoginCreate,
        auth_schemas.SessionIdentityRead,
    ):
        fields = set(model.model_fields)
        assert not (fields & {"password_hash", "password_bound_at"}), (model, fields)
    assert sorted(auth_schemas.SessionIdentityRead.model_fields) == [
        "id", "kind", "name", "role", "staff_no", "student_no",
    ]
    # 三个请求体各有一格 password，且它是 SecretStr（不是裸 str）
    from pydantic import SecretStr

    for model in (
        auth_schemas.StudentBindCreate,
        auth_schemas.TeacherBindCreate,
        auth_schemas.LoginCreate,
    ):
        assert model.model_fields["password"].annotation is SecretStr, model
    assert sorted(auth_schemas.StudentBindCreate.model_fields) == [
        "birth", "password", "student_no",
    ]
    assert sorted(auth_schemas.TeacherBindCreate.model_fields) == [
        "name", "password", "staff_no",
    ]
    assert sorted(auth_schemas.LoginCreate.model_fields) == ["kind", "login", "password"]


# ---------------------------------------------------------------------------
# ⑥ OpenAPI 面：五个路径、第三个 securityScheme、哪两个操作挂它
# ---------------------------------------------------------------------------


def test_the_five_auth_operations_are_declared_and_only_two_of_them_carry_security(app):
    """``/api/auth/*`` 恰好**五个**操作，其中**两个**挂 cookie scheme、三个匿名。

    ⚠️ **一律走 ``app.openapi()["paths"]``，不走 ``app.routes``**：FastAPI 0.141.1 的
    ``include_router`` 是惰性的（它把整个子 router 折叠成一个 ``_IncludedRouter``），
    故 ``len(app.routes)`` 实测只有 6，按它写的扫描是**假绿**的
    （终审专门实测过：它在正确的接线上报 0 个问题，在一个排反了顺序的 app 上**也**报 0）。

    ⚠️ **``pe_session`` 是本仓第三个 securityScheme**（另两个是
    ``X-Student-Id`` / ``X-Teacher-Staff-No``），而它是唯一一个 ``in: cookie`` 的。
    声明它的理由与 P4-A5 那两个逐字相同：只挂判定的话，前端从 spec 上看不出来
    要带 cookie、生成的 TS 客户端也不会加 ``credentials``。
    ⚠️ 而 Swagger UI **设不了** HttpOnly cookie，故在 ``/docs`` 上试登录端点的正确姿势
    是先打 ``POST /api/auth/login``（浏览器自己存 ``Set-Cookie``），这一段归 Task 5 写进 spec §13。
    """
    spec = app.openapi()
    schemes = spec["components"]["securitySchemes"]
    assert sorted(schemes) == ["X-Student-Id", "X-Teacher-Staff-No", "pe_session"]
    cookie_scheme = schemes["pe_session"]
    assert cookie_scheme == {
        "type": "apiKey",
        "in": "cookie",
        "name": "pe_session",
        "description": cookie_scheme["description"],
    }
    assert cookie_scheme["description"], "没有 description，Swagger 上那一格是空的"
    for name in ("X-Student-Id", "X-Teacher-Staff-No"):
        assert schemes[name]["in"] == "header", name

    paths = spec["paths"]
    auth_paths = sorted(key for key in paths if key.startswith("/api/auth"))
    assert auth_paths == [
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/students/bind",
        "/api/auth/teachers/bind",
    ]
    operations = [(key, method) for key in auth_paths for method in paths[key]]
    assert len(operations) == 5, operations
    assert sorted(operations) == [
        ("/api/auth/login", "post"),
        ("/api/auth/logout", "post"),
        ("/api/auth/me", "get"),
        ("/api/auth/students/bind", "post"),
        ("/api/auth/teachers/bind", "post"),
    ]
    # 两个挂 cookie scheme、三个匿名（绑定与登录**必须**匿名：它们就是拿来换 cookie 的）
    carrying = sorted(
        (key, method) for key, method in operations
        if paths[key][method].get("security")
    )
    assert carrying == [("/api/auth/logout", "post"), ("/api/auth/me", "get")]
    for key, method in carrying:
        assert paths[key][method]["security"] == [{"pe_session": []}], (key, method)
    for key, method in sorted(set(operations) - set(carrying)):
        assert "security" not in paths[key][method], (key, method)
    # 状态码那一档也在 spec 上（204 / 200）
    assert paths["/api/auth/students/bind"]["post"]["responses"]["204"]
    assert paths["/api/auth/teachers/bind"]["post"]["responses"]["204"]
    assert paths["/api/auth/logout"]["post"]["responses"]["204"]
    assert paths["/api/auth/me"]["get"]["responses"]["200"]
    assert spec.get("security") is None, "本仓的口径是按端点声明，不用全局 security"


# ---------------------------------------------------------------------------
# ⑦ Plan 05A Task 2：``role`` 影响的两件事
# ---------------------------------------------------------------------------


def test_require_staff_admits_both_roles_while_require_admin_admits_only_one(
    engine, people
):
    """**闸门本身**（不经 HTTP）：``require_staff`` 放行两种 role，``require_admin`` 只放行一种。

    ⚠️ 本条是 :func:`app.api.deps.require_staff` **改名**的可执行判据：
    它此前叫 ``require_teacher``，而计划 §3.6 第 3 条要求的「教师或管理员都可以」
    在旧实现上**本来就成立**（那个函数只查「工号在不在 ``teacher`` 表里」、从不看 role，
    而管理员就是一行 ``teacher``）。故 Task 2 在那一侧真正做的三件事是
    ① 改名（让「教师或管理员」在名字上成立）② **返回 role**
    （``require_admin`` 与两道任教闸门要用它）③ 显式校验 role 的取值域。
    三格逐个断言，故「改回去」不会静默。

    ⚠️ 四档失败逐个点名：不在册 / 在册但非管理员 / **两档的 message 必须不同**
    （前者说「不是一个在册教师」，后者点名 ``role`` 的当前值——前端要能把后者翻译成
    「管理台只有教务干事能改」，而一个光秃秃的 403 会让用户以为登录坏了、去反复重登）。
    """
    from fastapi import HTTPException

    from app.api.deps import ADMIN_ROLE, STAFF_ROLES, require_admin, require_staff

    assert ADMIN_ROLE == "admin"
    assert STAFF_ROLES == frozenset({"teacher", "admin"}) == frozenset(Teacher.ROLES)

    with Session(engine) as session:
        # 绿档：两种 role 都过 require_staff，且**返回 role**（此前返回 None）
        assert require_staff(session, STAFF_NO) == "teacher"
        assert require_staff(session, ADMIN_NO) == "admin"
        assert require_admin(session, ADMIN_NO) == "admin"

        # 红档 1：不在册（两个闸门同一句 message，因为 require_admin 先调 require_staff）
        for gate in (require_staff, require_admin):
            with pytest.raises(HTTPException) as excinfo:
                gate(session, "NOBODY")
            assert excinfo.value.status_code == 403
            assert "不是一个在册教师" in str(excinfo.value.detail)

        # 红档 2：在册但不是管理员
        with pytest.raises(HTTPException) as excinfo:
            require_admin(session, STAFF_NO)
        assert excinfo.value.status_code == 403
        detail = str(excinfo.value.detail)
        assert "'teacher'" in detail, detail
        assert "管理台" in detail and "require_staff" in detail, detail

        # 两档 message 必须不同
        with pytest.raises(HTTPException) as stranger:
            require_staff(session, "NOBODY")
        assert str(stranger.value.detail) != detail

        # 空白工号也算不在册（口径与 current_teacher 的「空白也算缺」一致）
        with pytest.raises(HTTPException):
            require_staff(session, "   ")


@pytest.fixture()
def classes(engine, people):
    """一个教学班（归**普通教师** T0001）+ 一个**不带任何班**的教师 T0002 + 那条选课行。

    ⚠️ 它是下面那条「管理员越过任教范围闸门」守卫的**全部前提**：
    没有「一个不带班的教师被 403 掉」这个对照，「管理员被放行」就证明不了
    闸门真的在判任教关系（一个恒放行的闸门也是「管理员能过」）。
    """
    with Session(engine) as session:
        semester = session.scalar(select(Semester.id))
        owner = people["teacher"]
        section = CourseSection(
            semester_id=semester, teacher_id=owner, name="体育(1)班",
            grouping_mode="administrative",
        )
        session.add(section)
        session.add(Teacher(staff_no=CLASSLESS_NO, name="不带班的教师", role="teacher"))
        session.commit()
        session.add(
            Enrollment(
                semester_id=semester, student_id=people["student"],
                course_section_id=section.id,
            )
        )
        session.commit()
        return {"section": section.id, "semester": semester}


def test_an_admin_passes_the_teaching_gates_that_stop_a_classless_teacher(
    client, people, classes
):
    """⚠️ **派单 §4 第 2 条要的实测复核**：管理员越过任教范围闸门，教师保留。

    控制者的推论是「管理员（教务干事）通常不带任何班 → 若不放行，``role='admin'``
    就只是一个标签、这个角色没有意义」。**实现者复核后同意，证据就是本条的三列**
    （亲跑取证，不是照抄计划；一个空库、只有学期 + 三个教师 + 一个班 + 一条选课行）：

    ==============================================  ========  ==========  ================
    端点（都挂 ``X-Teacher-Staff-No``）               带班教师   不带班教师   管理员（不带班）
    ==============================================  ========  ==========  ================
    ``GET /api/dashboard/class/{id}``                 200      **403**       **200**
    ``GET /api/dashboard/weekly-class-report/{id}``   404 (1)  **403**       404 (1)
    ``GET /api/teacher/students/{id}/weekly-sheet``   404 (2)  **403**       404 (2)
    ==============================================  ========  ==========  ================

    (1) 没有周报（``weekly_class_report`` 只在周日的批处理里生成）；
    (2) 没有生效处方（``no_active_prescription``）。
    两格都**已经过了闸门**、只是没有数据——而 403 是闸门给的。

    ⚠️ 于是推论在代码里**成立**：闸门确实按 ``course_section.teacher_id`` /
    ``enrollment ⋈ course_section`` 判，而不带任何班的人（管理员的常态）确实一律 403。
    不放行的话，管理员登录进 ``/admin`` 之后点教师大屏会**全部 403**，
    ``role='admin'`` 就只剩「能改管理台」这一半意义。

    ⚠️ **代价（硬规矩 #39）**：管理员因此能读**全校任何班、任何学生**的数据，
    而本仓没有「哪个教务干事管哪个院系」这一格。原型可接受（一个学校通常只有一两个
    干事），已登记为关切并写进 spec §13。

    ⚠️ **两条通道各测一次**（请求头 + cookie）：⚠️ 而实现者实测发现
    **两条通道判的是同一份 role**——``require_teaches_*`` 与 ``require_admin``
    都经 :func:`app.api.deps.require_staff`，而它查的是 ``teacher`` 表
    （**不是** ``user_session.role`` 那一份冗余）。故 cookie 那一档不是「另一条判据」，
    只是「另一个身份载体」；两条都要放行，否则前端登录之后反而比开发期
    用请求头时权限更小。
    """
    section, student = classes["section"], people["student"]
    owner = {"X-Teacher-Staff-No": STAFF_NO}
    classless = {"X-Teacher-Staff-No": CLASSLESS_NO}
    admin = {"X-Teacher-Staff-No": ADMIN_NO}

    for path in (
        f"/api/dashboard/class/{section}",
        f"/api/dashboard/weekly-class-report/{section}",
        f"/api/teacher/students/{student}/weekly-sheet",
    ):
        got_classless = client.get(path, headers=classless)
        assert got_classless.status_code == 403, (path, got_classless.text)
        assert got_classless.json()["error"]["code"] == "forbidden"

        got_owner = client.get(path, headers=owner)
        got_admin = client.get(path, headers=admin)
        assert got_owner.status_code == got_admin.status_code, (
            path, got_owner.status_code, got_admin.status_code,
            "管理员应当与**带班教师**看到同一档（放行之后落到同一份数据上），"
            "而不是与不带班的教师同一档",
        )
        assert got_admin.status_code != 403, (path, got_admin.text)
        assert got_admin.status_code < 500, (path, got_admin.text)

    # cookie 那一档：管理员登录之后同样越过闸门
    _bind_teacher(client, staff_no=ADMIN_NO, name="王干事", password=ADMIN_PASSWORD)
    client.cookies.clear()
    assert _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD).status_code == 200
    assert client.get(f"/api/auth/me").json()["role"] == "admin"
    for path in (
        f"/api/dashboard/class/{section}",
        f"/api/teacher/students/{student}/weekly-sheet",
    ):
        got = client.get(path)
        assert got.status_code != 403, (path, got.text)
        assert got.status_code < 500, (path, got.text)


def test_a_plain_teacher_keeps_the_classroom_endpoints_and_loses_the_console(
    client, people, classes
):
    """**计划 §3.6 末段（⚠️ 用户未裁定）**：管理员接管的是**管理台**，不是课堂功能。

    两列同时在场（硬规矩 #50）：

    * **课堂功能保留**：一个普通教师仍然能读自己那个班的大屏（200）——
      而这一格在 Task 2 之前也成立，故它是**回归**守卫：把 ``require_staff``
      换成 ``require_admin`` 的话它会红；
    * **管理台失去**：同一个教师 POST 一个学期是 **403**，而管理员是 **201**。

    ⚠️ **实现者对这一条的复核结论是「同意，但它在行为上是 no-op」**：
    旧 ``require_teacher`` 只查「工号在不在 ``teacher`` 表里」、从不看 ``role``，
    而管理员就是一行 ``teacher``，故它**本来就**放行管理员。Task 2 在那一侧做的是
    改名 + 返回 role + 显式校验取值域（三格都由
    :func:`test_require_staff_admits_both_roles_while_require_admin_admits_only_one` 钉住）。
    ⚠️ 而「教师保留课堂功能」这一半**不是** no-op：它是「没把 ``require_staff``
    顺手换成 ``require_admin``」的守卫，而那是一次很容易犯的错
    （``grep -l require_teacher`` 一把梭就会犯）。

    ⚠️ 本条走的是**请求头**通道；cookie 通道那一格由上一条覆盖。
    """
    section = classes["section"]
    teacher = {"X-Teacher-Staff-No": STAFF_NO}
    admin = {"X-Teacher-Staff-No": ADMIN_NO}

    # 课堂功能：普通教师照旧能读自己那个班
    kept = client.get(f"/api/dashboard/class/{section}", headers=teacher)
    assert kept.status_code == 200, kept.text
    assert kept.json()["course_section_id"] == section
    # 而别人的班仍然是 403（闸门没有被一起摘掉）
    with Session(engine_of(client)) as session:
        other = CourseSection(
            semester_id=classes["semester"], teacher_id=people["admin"],
            name="体育(2)班", grouping_mode="administrative",
        )
        session.add(other)
        session.commit()
        other_id = other.id
    assert client.get(f"/api/dashboard/class/{other_id}", headers=teacher).status_code == 403
    assert client.get(f"/api/dashboard/class/{other_id}", headers=admin).status_code == 200

    # 管理台：普通教师 403、管理员 201
    payload = {
        "name": "2026-2027-1", "start_date": "2026-09-01",
        "end_date": "2027-01-20", "weeks": 16,
    }
    denied = client.post("/api/semesters", json=payload, headers=teacher)
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "forbidden"
    admitted = client.post("/api/semesters", json=payload, headers=admin)
    assert admitted.status_code == 201, admitted.text


def test_the_console_admits_an_admin_over_the_cookie_channel_too(client, people):
    """**cookie 通道下的管理台**：管理员 201、普通教师 403、学生 403。

    ⚠️ 本条是「cookie 通道下管理台也归管理员」的判据。⚠️ 而实现者实测发现
    **cookie 通道判的 role 与请求头通道是同一份**：``require_admin`` 经
    :func:`app.api.deps.require_staff` 查 ``teacher`` 表，**不是** ``user_session.role``
    那一份冗余。故「降权」对管理台是**立刻**生效的（下一次请求就 403），
    而**只有** ``GET /api/auth/me`` 与登录响应体里那个 ``role`` 会滞后到重新登录
    ——那一格是**前端路由**的判据，不是后端闸门的判据。
    ⚠️ 于是冗余 ``role`` 的代价比计划 §3.1 写的**更轻**：它不是「降权不生效」
    （安全档），而是「被降权的人在重新登录之前，前端仍会把他送到 ``/admin``，
    然后每一次写都吃一个 403」（UI 一致性档，失效方向是安全的）。
    两条守卫各钉一半：本条钉「后端按 ``teacher`` 表判」，
    ``tests/auth/test_sessions.py`` 的
    ``test_a_demoted_admin_keeps_the_role_recorded_on_his_live_session``
    钉「会话行上那一份不随降权改变」。
    """
    _bind_teacher(client, staff_no=STAFF_NO, name="李老师", password=ADMIN_PASSWORD)
    _bind_teacher(client, staff_no=ADMIN_NO, name="王干事", password=ADMIN_PASSWORD)
    payload = {
        "name": "2027-2028-1", "start_date": "2027-09-01",
        "end_date": "2028-01-20", "weeks": 16,
    }

    client.cookies.clear()
    assert _login(client, "teacher", STAFF_NO, ADMIN_PASSWORD).status_code == 200
    denied = client.post("/api/semesters", json=payload)
    assert denied.status_code == 403, denied.text
    assert "role" in denied.json()["error"]["message"]

    client.cookies.clear()
    assert _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD).status_code == 200
    admitted = client.post("/api/semesters", json=payload)
    assert admitted.status_code == 201, admitted.text

    # 学生的 cookie 打管理台：403（current_teacher 那一档：会话是学生、端点要教师）
    _bind_student(client)
    client.cookies.clear()
    assert _login(client, "student", STUDENT_NO, PASSWORD).status_code == 200
    student_denied = client.post(
        "/api/semesters", json={**payload, "name": "2028-2029-1"}
    )
    assert student_denied.status_code == 403, student_denied.text
    assert student_denied.json()["error"]["code"] == "forbidden"


def test_demoting_an_admin_takes_the_console_away_immediately_but_not_the_me_projection(
    client, people, engine
):
    """**把上一条那个实测发现钉成守卫**：降权对**管理台**立刻生效、对 ``me`` 要等重登。

    三拍：① 管理员 POST → 201；② 把 ``teacher.role`` 改成 ``teacher``（不碰会话行）；
    ③ 同一个 cookie 再 POST → **403**，而 ``GET /api/auth/me`` 仍然回 ``role: "admin"``。

    ⚠️ **③ 的两半方向相反，而两半都是对的**：闸门查 ``teacher`` 表（故立刻生效，
    失效方向是安全的——权限**少**给），``me`` 回的是 ``user_session.role``
    那一份冗余（故滞后，失效方向也是安全的——前端只会多显示一个入口，
    而点进去每一次写都吃 403）。
    ⚠️ 于是计划 §3.1 写的那条代价（「管理员被降权不会立刻生效」）**在安全档上不成立**，
    它只在 **UI 一致性档**上成立。这一格是实测出来的、不是设计出来的，
    故本条把它钉住：将来若有人把 ``require_admin`` 改成读会话行上那一份
    （「省一次查询」），本条会红在 ③ 的前半，而那正是一次真实的权限滞留。
    """
    _bind_teacher(client, staff_no=ADMIN_NO, name="王干事", password=ADMIN_PASSWORD)
    client.cookies.clear()
    assert _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD).status_code == 200
    first = client.post(
        "/api/semesters",
        json={"name": "2029-2030-1", "start_date": "2029-09-01",
              "end_date": "2030-01-20", "weeks": 16},
    )
    assert first.status_code == 201, first.text

    with Session(engine) as session:
        admin = session.get(Teacher, people["admin"])
        admin.role = "teacher"
        session.commit()

    denied = client.post(
        "/api/semesters",
        json={"name": "2030-2031-1", "start_date": "2030-09-01",
              "end_date": "2031-01-20", "weeks": 16},
    )
    assert denied.status_code == 403, (denied.status_code, denied.text)
    assert "'teacher'" in denied.json()["error"]["message"], denied.text
    assert client.get("/api/auth/me").json()["role"] == "admin", (
        "me 的 role 不再滞后了：那意味着 resolve 改成了以 teacher 表为准。"
        "若这是有意的收紧，请连同 app/db/models/auth.py 模块 docstring 第三节、"
        "tests/auth/test_sessions.py 的 test_a_demoted_admin_keeps_the_role_… 一起改"
    )
    # 重新登录之后 me 也回到 teacher
    client.cookies.clear()
    assert _login(client, "teacher", ADMIN_NO, ADMIN_PASSWORD).json()["role"] == "teacher"

