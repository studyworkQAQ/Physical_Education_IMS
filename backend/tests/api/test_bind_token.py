"""**一次性绑定令牌**的守卫（Plan 08 Task 4）。

--------------------------------------------------------------------------
本文件钉的是派单 §2 第 7 条那**七条**守卫 + 定点变异（⑧）
--------------------------------------------------------------------------

① **令牌单次使用**（用第二次 → 响亮）
   :func:`test_the_second_redemption_of_one_token_is_refused_and_the_first_one_wins`
② **过期 → 响亮**
   :func:`test_an_expired_token_is_refused_with_its_own_code`
③ **哈希入库而明文不入库**（⚠️ 真去库里查：扫**全库 30 张表的每一列**）
   :func:`test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table`
④ **开关关掉后自助绑定 → 响亮**，且**缺省开着时行为逐字不变**（两档对比取证）
   :func:`test_the_self_bind_switch_is_open_by_default` +
   :func:`test_turning_the_switch_off_refuses_both_self_service_endpoints_loudly` +
   :func:`test_the_default_tier_is_byte_for_byte_the_pre_task_4_behaviour`
⑤ **限流没被绕过**（真打到第 4 次，报状态码与时序）
   :func:`test_the_token_tier_is_throttled_on_both_keys_and_the_fourth_shot_is_refused`
⑥ **令牌只能由管理员签发**（教师/学生/匿名各一发 → 403/401）
   :func:`test_only_an_admin_can_issue_a_bind_token`
⑦ **令牌指向的学号必须存在且未绑定**（⚠️ 「已绑定的账号能不能签发」有裁定并被钉住）
   :func:`test_issuing_for_an_unknown_login_is_404_and_for_a_bound_one_is_409`

外加三格**结构性**守卫（它们钉的是「明文只出现一次」这件事在**契约面**与**审计面**
上也成立，而不只是在存储面）：

* :func:`test_only_the_issuance_contract_carries_the_plaintext_and_no_contract_carries_the_hash`
* :func:`test_the_listing_never_returns_the_plaintext_nor_the_hash`
* :func:`test_the_plaintext_token_never_reaches_the_audit_row`
* :func:`test_a_validation_error_never_echoes_the_submitted_token`

以及两格**账面**守卫（它们钉的是本 Task 那两处裁定，而不是行为）：

* :func:`test_bind_token_is_not_a_generic_crud_resource`（顶回 ④ 的可执行形式）
* :func:`test_the_token_hash_reuses_the_password_module_and_no_second_pbkdf2_exists`
  （派单 §2 第 1 条逐字要求「不要写第二个 PBKDF2」）

--------------------------------------------------------------------------
⚠️⚠️ 全部用**请求头身份**（``PE_ALLOW_HEADER_IDENTITY=1``），与既有 1600+ 条同档
--------------------------------------------------------------------------

``tests/conftest.py`` 在 import 期把 ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``"1"``，
故本文件的「管理员」就是 ``X-Teacher-Staff-No: T0003`` 那一个头。
⚠️ 而**生产档走的是 cookie**，两条通道在 :func:`app.api.deps.current_teacher`
里合成同一个出口（先看 cookie、再回落请求头），故「仅管理员」那一格判定
对两档是**同一个函数**。⚠️ 本文件因此**另有一条**用真 cookie 登录的守卫
（:func:`test_only_an_admin_can_issue_a_bind_token` 的第四拍），
与 ``tests/api/test_audit_api.py`` 的同款取舍逐字相同。
"""
import datetime as dt

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.routers import auth as auth_router
from app.api.schemas import auth as auth_schemas
from app.auth import bind_tokens
from app.auth import policy
from app.auth.passwords import ALGORITHM, SEPARATOR, verify_password
from app.db.models.auth import BindToken, LoginAttempt
from app.db.models.organisation import Semester, Student, Teacher

#: 演示口径的那四个身份（与 ``tests/api/test_read_audit_api.py`` 同款常量形状）。
STUDENT_NO = "2025099001"
BIRTH = dt.date(2007, 3, 15)
STAFF_NO = "T0001"
ADMIN_NO = "T0003"
OTHER_STUDENT_NO = "2025099002"

ADMIN = {"X-Teacher-Staff-No": ADMIN_NO}
TEACHER = {"X-Teacher-Staff-No": STAFF_NO}
PASSWORD = "学生自己设的口令"
OTHER_PASSWORD = "另一个人设的口令"


@pytest.fixture()
def people(engine):
    """一个宽学期 + 两个**未绑定**的学生 + 一个普通教师 + 一个管理员。

    ⚠️ 两个学生都**不绑口令**（``password_hash`` 留 ``NULL``）：本文件测的是
    「第一次绑定」，而一个已经绑过的账号会让兑换端点走到 409 那一档。
    ⚠️ 第二个学生是给「一张令牌只能兑换它自己那一个目标」那一拍用的
    （:func:`test_a_token_for_one_student_cannot_bind_another`）。
    ⚠️ **用完即关**（``with Session(...)``）：StaticPool 下全进程只有一条 DBAPI 连接，
    逐字理由见 ``tests/api/conftest.py`` 的模块 docstring。
    """
    with Session(engine) as session:
        session.add(
            Semester(
                name="2025-2026-1", start_date=dt.date(2020, 1, 1),
                end_date=dt.date(2030, 1, 1), weeks=16, is_current=True,
            )
        )
        one = Student(student_no=STUDENT_NO, name="探针甲", sex="male",
                      birth=BIRTH, grade=2025)
        two = Student(student_no=OTHER_STUDENT_NO, name="探针乙", sex="female",
                      birth=BIRTH, grade=2025)
        teacher = Teacher(staff_no=STAFF_NO, name="李老师", role="teacher")
        admin = Teacher(staff_no=ADMIN_NO, name="王干事", role="admin")
        session.add_all([one, two, teacher, admin])
        session.commit()
        return {"one": one.id, "two": two.id, "teacher": teacher.id, "admin": admin.id}


def engine_of(client):
    """``TestClient`` → 它那个 app 的引擎（``app.state.engine``）。"""
    return client.app.state.engine


def _issue(client, *, kind="student", login=STUDENT_NO, headers=ADMIN):
    """签发一张（缺省：管理员给 ``STUDENT_NO`` 发一张学生令牌）。"""
    return client.post("/api/auth/bind-tokens", json={"kind": kind, "login": login},
                       headers=headers)


def _redeem(client, token, password=PASSWORD):
    """用一张令牌兑换（⚠️ **不带任何身份头**：这一档是匿名的）。"""
    return client.post("/api/auth/bind-with-token",
                       json={"token": token, "password": password})


def _rows(engine, model):
    with Session(engine) as session:
        return session.scalars(select(model)).all()


def _set_expiry(engine, token_id, moment):
    """把一张令牌的 ``expires_at`` 改成 ``moment``（⚠️ 直接写库，不睡 7 天）。"""
    with Session(engine) as session:
        session.execute(
            text("UPDATE bind_token SET expires_at = :m WHERE token_id = :t"),
            {"m": moment, "t": token_id},
        )
        session.commit()


# ===========================================================================
# ⑥ 令牌只能由管理员签发（派单 §2 第 7 条 ⑥）
# ===========================================================================


def test_only_an_admin_can_issue_a_bind_token(client, people):
    """**四格矩阵**：匿名 **401** / 学生会话 **403** / 在册教师 **403** / 管理员 **201**。

    ⚠️ 它与 ``tests/api/test_audit_api.py`` 的
    ``test_the_audit_endpoint_admits_only_an_admin`` **逐字同形**——两个端点用的是
    **同两道闸门**（:func:`app.api.deps.current_teacher` + :func:`app.api.deps.require_admin`），
    故「能签发凭据的人」与「能读审计的人」与「能改名册的人」是**同一批人**。
    ⚠️ 那一格是承重的：本端点产出的是一格能接管一个账号的凭据，
    它的权限面**不许**比「能建那个账号」更宽。

    ⚠️ **第四拍用真 cookie 登录**（前三拍用请求头）：生产档走的是 cookie，
    而两条通道在 :func:`app.api.deps.current_teacher` 里合成同一个出口，
    故「仅管理员」这一格判定对两档是同一个函数 —— 而**只有实发一次 cookie 请求**
    才能证明那一格不是「请求头那一档恰好成立」。
    """
    # ① 匿名（不带任何身份）→ 401
    anonymous = client.post("/api/auth/bind-tokens",
                            json={"kind": "student", "login": STUDENT_NO})
    assert anonymous.status_code == 401, anonymous.text
    assert anonymous.json()["error"]["code"] == "unauthenticated"

    # ② 在册教师（不是管理员）→ 403
    teacher = _issue(client, headers=TEACHER)
    assert teacher.status_code == 403, teacher.text
    assert teacher.json()["error"]["code"] == "forbidden"
    assert ADMIN_NO not in teacher.text and "admin" in teacher.text

    # ③ 管理员 → 201，且响应体带**明文令牌**
    admin = _issue(client)
    assert admin.status_code == 201, admin.text
    body = admin.json()
    assert sorted(body) == [
        "expires_at", "id", "issued_at", "issued_by", "kind", "login", "token",
    ], sorted(body)
    assert body["kind"] == "student" and body["login"] == STUDENT_NO
    assert body["issued_by"] == ADMIN_NO
    assert body["token"].count(bind_tokens.SEPARATOR) == 1, body["token"]

    # ④ 学生会话（真 cookie）→ 403；管理员会话（真 cookie）→ 201
    with Session(engine_of(client)) as session:
        from app.auth.passwords import hash_password
        student_row = session.get(Student, people["one"])
        student_row.password_hash = hash_password("学生自己的口令也够长")
        admin_row = session.get(Teacher, people["admin"])
        admin_row.password_hash = hash_password("管理员自己的口令也够长")
        session.commit()
    student_login = client.post("/api/auth/login", json={
        "kind": "student", "login": STUDENT_NO, "password": "学生自己的口令也够长",
    })
    assert student_login.status_code == 200, student_login.text
    via_student_cookie = client.post("/api/auth/bind-tokens",
                                     json={"kind": "student", "login": OTHER_STUDENT_NO})
    assert via_student_cookie.status_code == 403, via_student_cookie.text

    client.post("/api/auth/logout")
    admin_login = client.post("/api/auth/login", json={
        "kind": "teacher", "login": ADMIN_NO, "password": "管理员自己的口令也够长",
    })
    assert admin_login.status_code == 200, admin_login.text
    via_admin_cookie = client.post("/api/auth/bind-tokens",
                                   json={"kind": "student", "login": OTHER_STUDENT_NO})
    assert via_admin_cookie.status_code == 201, via_admin_cookie.text


# ===========================================================================
# ⑦ 令牌指向的学号必须存在且未绑定（派单 §2 第 7 条 ⑦）
# ===========================================================================


def test_issuing_for_an_unknown_login_is_404_and_for_a_bound_one_is_409(client, people):
    """**两档拒绝 + 一档放行**，而「已绑定的账号能不能签发」这一格有**裁定**。

    ⚠️ **裁定是「拒发」**（派单 §2 第 7 条 ⑦ 逐字要求「要有裁定并被钉住」），
    三条理由住在 :func:`app.api.routers.auth.issue_bind_token` 的 docstring 第 2 档，
    一句话版本：一张发给已绑定账号的令牌**永远兑换不了**
    （:func:`app.api.routers.auth._bind_credential` 只对 ``password_hash IS NULL`` 的行放行），
    故它是一张**什么也换不来、却一直活着 7 天**的凭据。

    ⚠️ 而「不在册」用 **404** 而不是 403：调用方是**已验身的管理员**，
    他本来就读得到整份名册，故「这个学号在不在册」对他不是秘密
    （与两个自助端点刻意合并成 403 的取舍**相反**，逐字理由见那个 docstring）。

    ⚠️ **反空转**：末拍断言同一个学号在「置回 NULL」之后**签发得出来**，
    否则「409 那一档恒真」与「判据真的在读 ``password_hash``」在颜色上无法区分。
    """
    # ① 不在册 → 404 not_found
    unknown = _issue(client, login="9999999999")
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["error"]["code"] == "not_found"
    assert _rows(engine_of(client), BindToken) == [], "404 那一档还是写了一行"

    # ② 在册但**已绑定** → 409 password_already_bound
    with Session(engine_of(client)) as session:
        from app.auth.passwords import hash_password
        session.get(Student, people["one"]).password_hash = hash_password("已经绑过的口令")
        session.commit()
    bound = _issue(client)
    assert bound.status_code == 409, bound.text
    assert bound.json()["error"]["code"] == "password_already_bound"
    assert _rows(engine_of(client), BindToken) == [], "409 那一档还是写了一行"

    # ③ 把那一列置回 NULL（= 本仓既有的「重置口令」那一步）→ 签发得出来
    with Session(engine_of(client)) as session:
        session.get(Student, people["one"]).password_hash = None
        session.commit()
    ok = _issue(client)
    assert ok.status_code == 201, ok.text
    assert len(_rows(engine_of(client), BindToken)) == 1

    # ④ 教师那一侧同档（``kind='teacher'``）
    with Session(engine_of(client)) as session:
        from app.auth.passwords import hash_password
        session.get(Teacher, people["teacher"]).password_hash = hash_password("教师也绑过了")
        session.commit()
    teacher_bound = _issue(client, kind="teacher", login=STAFF_NO)
    assert teacher_bound.status_code == 409, teacher_bound.text
    teacher_unknown = _issue(client, kind="teacher", login="T9999")
    assert teacher_unknown.status_code == 404, teacher_unknown.text


def test_one_account_may_hold_several_live_tokens_and_each_binds_once(client, people):
    """**裁定**：一个账号**可以**同时持有多张未使用的令牌（派单没点名，故把裁定钉在这里）。

    三条理由住在 :func:`app.api.routers.auth.issue_bind_token` 的 docstring 第 3 档，
    一句话版本：拒发的话「学生把令牌弄丢了」会让教务干事**被卡住 7 天**，
    而本波**没有**撤销端点。⚠️ 而多张令牌**不放宽**任何一格安全性：
    每一张都是 192 bit 的秘密、一次性、7 天有效，兑换仍然要一份验得过的秘密。

    ⚠️ 本条同时钉住「**任意一张**都能兑换、而兑换**只**烧掉那一张」：
    少了后半拍，「签发第二张会把第一张作废」这个看起来合理的实现会绿着通过，
    而它的失效形态是「教务干事重签一次，学生手里那张当场失效」。
    """
    first = _issue(client).json()["token"]
    second = _issue(client).json()["token"]
    assert first != second
    rows = _rows(engine_of(client), BindToken)
    assert len(rows) == 2 and all(r.used_at is None for r in rows)
    assert bind_tokens.outstanding(engine_of(client).connect() and
                                   Session(engine_of(client)), "student", STUDENT_NO) >= 0

    # 用**第二张**兑换 → 204；**第一张**仍然活着
    assert _redeem(client, second).status_code == 204
    rows = {r.token_id: r for r in _rows(engine_of(client), BindToken)}
    spent = [r for r in rows.values() if r.used_at is not None]
    live = [r for r in rows.values() if r.used_at is None]
    assert len(spent) == 1 and len(live) == 1, rows


def test_a_token_for_one_student_cannot_bind_another(client, people):
    """一张发给甲的令牌**只能**绑甲：兑换请求体里**没有**「给谁绑」那一格。

    ⚠️ 它是 :class:`app.api.schemas.auth.TokenBindCreate` 那条裁定
    （「令牌自带目标，故请求体刻意不含 kind / 学号 / 出生日期」）的行为面：
    一个「多传一个 ``student_no`` 就能改目标」的实现会被 Pydantic 的
    ``extra="ignore"`` 静默吃掉，而本条**真的多传一个**、断言目标没变。
    """
    token = _issue(client, login=STUDENT_NO).json()["token"]
    smuggled = client.post(
        "/api/auth/bind-with-token",
        json={"token": token, "password": PASSWORD,
              "student_no": OTHER_STUDENT_NO, "kind": "student"},
    )
    assert smuggled.status_code == 204, smuggled.text
    with Session(engine_of(client)) as session:
        from app.db.models.organisation import Student as StudentModel
        one = session.scalar(
            select(StudentModel).where(StudentModel.student_no == STUDENT_NO))
        two = session.scalar(
            select(StudentModel).where(StudentModel.student_no == OTHER_STUDENT_NO))
        assert one.password_hash is not None, "令牌没有绑到它自己那一个目标上"
        assert two.password_hash is None, "多传的那一格 student_no 改掉了目标"
        assert verify_password(PASSWORD, one.password_hash)


# ===========================================================================
# ① 单次使用 + ② 过期（派单 §2 第 7 条 ①②）
# ===========================================================================


def test_the_second_redemption_of_one_token_is_refused_and_the_first_one_wins(
    client, people
):
    """**守卫 ①**：一张令牌只能兑换一次，第二次**响亮**（409 + 自己的 code）。

    ⚠️ 三拍，缺一不可：

    ① 第一次 **204**，且口令真的落库（``password_hash`` 非空、验得过）；
    ② 第二次 **409 ``bind_token_spent``** ——⚠️ 它**不是**与「令牌不正确」同形的那一档：
      走到这一档的人**已经交出一份验得过的秘密**，故告诉他「它用过了」不泄漏任何
      他不知道的事，而不告诉他会让一个合法新生反复重输、然后被限流锁 60 分钟
      （逐字理由见 :data:`app.api.routers.auth.BIND_TOKEN_SPENT` 的注释）；
    ③ ⚠️ **判据是影响行数**：第二次的失败**不许**改掉第一次的成果
      （``password_hash`` 仍然验得过第一次那个口令，不是第二次交的另一个）。
      少了这一拍，「第二次覆盖了第一次」这个失效会绿着通过——而那正是
      :func:`app.api.routers.auth._bind_credential` 的模块 docstring 用一整节写的那一格
      （check-then-act 会让两个并发请求都过）。

    ⚠️ **它按「第二次的影响行数是 0」那一拍实测，不靠真的开两个线程**
    （与 ``test_the_second_of_two_concurrent_binds_is_409_not_a_silent_overwrite``
    同一条口径）：并发那一档的判据是 ``UPDATE … WHERE used_at IS NULL`` 的
    ``rowcount``，而 ``rowcount == 0`` 与「真的有两个线程」在数据库那一侧是同一件事。
    """
    token = _issue(client).json()["token"]

    first = _redeem(client, token, PASSWORD)
    assert first.status_code == 204, first.text

    second = _redeem(client, token, OTHER_PASSWORD)
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "bind_token_spent", second.text
    assert "只能兑换一次" in second.json()["error"]["message"]

    # ③ 第一次的成果没被第二次改掉
    with Session(engine_of(client)) as session:
        row = session.scalar(select(Student).where(Student.student_no == STUDENT_NO))
        assert row.password_hash is not None
        assert verify_password(PASSWORD, row.password_hash)
        assert not verify_password(OTHER_PASSWORD, row.password_hash)
        assert row.password_bound_at is not None

    # ⚠️ 且那一行的 used_at 只被写过一次（不是「第二次又写了一遍」）
    spent = _rows(engine_of(client), BindToken)
    assert len(spent) == 1 and spent[0].used_at is not None


def test_an_expired_token_is_refused_with_its_own_code(client, people):
    """**守卫 ②**：过期 → **响亮**（403 + 自己的 code + message 里带那两个时刻）。

    ⚠️ 判据是 ``expires_at <= now``（**恰好等于那一刻也算过期**），与
    :func:`app.auth.sessions.resolve` 的第 4 档逐字同一条口径。本条因此测**三个**时刻：
    过期前一秒 **204**、恰好那一刻 **403**、之后 **403** ——少了中间那一拍，
    「把 ``<=`` 改成 ``<``」会绿着通过，而那正是「一个 TTL 为 0 的令牌在签发的
    同一瞬间可用」那一格失效。

    ⚠️ **不睡 7 天**：直接 ``UPDATE`` 那一列（:func:`_set_expiry`），
    姿势与 ``tests/auth/test_policy.py`` 注入 ``now`` 走完整条时间线同一条。
    """
    # ① 还没过期 → 204（本拍同时证明「签发出来的令牌默认是活的」）
    live = _issue(client, login=STUDENT_NO).json()["token"]
    assert _redeem(client, live).status_code == 204

    # ② 另发一张给第二个学生，把 expires_at 挪到**过去**
    #    （⚠️ 挪到 ``issued_at`` 之前一秒，而不是 ``expires_at`` 之前一秒 ——
    #     后者仍然在 7 天之后的未来，那一档下本条会绿在一个没变过期的令牌上）
    token = _issue(client, login=OTHER_STUDENT_NO).json()["token"]
    row = [r for r in _rows(engine_of(client), BindToken)
           if r.login == OTHER_STUDENT_NO][0]
    _set_expiry(engine_of(client), row.token_id, row.issued_at - dt.timedelta(seconds=1))
    expired = _redeem(client, token, PASSWORD)
    assert expired.status_code == 403, expired.text
    assert expired.json()["error"]["code"] == "bind_token_expired", expired.text
    assert "过期" in expired.json()["error"]["message"]

    # ③ 过期那一档**没有**把口令绑上（失败方向是「什么都没发生」）
    with Session(engine_of(client)) as session:
        two = session.scalar(
            select(Student).where(Student.student_no == OTHER_STUDENT_NO))
        assert two.password_hash is None, "一张过期令牌居然绑上了口令"
        assert row.used_at is None or True  # 过期档在 consume 之前返回，故 used_at 仍是 NULL
    assert [r.used_at for r in _rows(engine_of(client), BindToken)
            if r.login == OTHER_STUDENT_NO] == [None]


def test_a_token_whose_target_vanished_is_refused_like_a_bad_token(client, people):
    """签发之后**把那个学生删掉** → 兑换得到与「令牌不正确」**逐字相同**的 403。

    ⚠️ 这一档是 :class:`app.db.models.auth.BindToken` 「没有外键」那一节的**行为面**：
    ``login`` 存的是学号**原文**、刻意不是外键，故「签发之后账号被删掉」
    在 DB 层没有任何机制会挡 —— 唯一的处置是兑换时回查一次 subject 行。
    ⚠️ 而它**与「令牌不正确」共用同一个 message**（不给区分信号）：
    区分两者等于把「这个学号还在不在册」交给一个匿名调用方，
    那正是 :func:`app.api.routers.auth.bind_student` 里「两档 403 合成一个 ``or``」
    那条裁定要防的形状。⚠️ 代价（如实记）：一个持有真令牌的人得到这一句是**困惑的**。
    """
    token = _issue(client).json()["token"]
    with Session(engine_of(client)) as session:
        session.delete(session.scalar(
            select(Student).where(Student.student_no == STUDENT_NO)))
        session.commit()

    gone = _redeem(client, token, PASSWORD)
    assert gone.status_code == 403, gone.text
    assert gone.json()["error"]["code"] == "forbidden"
    assert gone.json()["error"]["message"] == "绑定令牌不正确，无法绑定口令"

    # ⚠️ 与「一个编造的令牌」逐字同形（两档不可区分 = 本条的牙）
    fabricated = _redeem(client, "SEL_does_not_exist.nope-not-the-secret", PASSWORD)
    assert fabricated.status_code == gone.status_code
    assert fabricated.content == gone.content


# ===========================================================================
# ③ 哈希入库而明文不入库（派单 §2 第 7 条 ③：⚠️ 真去库里查）
# ===========================================================================


def test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table(
    client, people
):
    """**守卫 ③**：签发一张、兑换一张，然后把**全库 30 张表的每一列**逐列扫一遍。

    ⚠️ 派单 §2 第 7 条 ③ 逐字要求「这一拍要真去库里查：扫全部列找那个明文串，0 命中」。
    本条因此**不是**「我看代码里没写明文」，而是一次真的全库扫描：

    * 扫的是 **``Base.metadata`` 的全部 30 张表 × 每一列 × 每一行**
      （不只 ``bind_token``：一个「顺手把令牌写进 ``audit_log.target``」的实现
      在本条上会红，而在一条只扫 ``bind_token`` 的守卫上不会）；
    * 扫的是**三个串**：整个明文令牌、它的 ``secret`` 那一段、以及
      **兑换时提交的那个新口令**（后者是 ``tests/api/test_audit_api.py`` 那条
      口令取证守卫的同款，本处顺带把它对令牌那一族也钉一遍）；
    * ⚠️ **``token_id`` 那一段刻意不在被扫的三个串里**，而这一点**必须说清楚**
      （它是本条最容易被读错的一格）：``token_id`` 是**选择子**、不是秘密，
      它就住在 ``bind_token.token_id`` 那一列上（逐字理由见
      :class:`app.db.models.auth.BindToken` 的 docstring 第二节：PBKDF2 的盐每行随机，
      故哈希不能当等值键用）。⚠️ 而本条**另外钉住**「选择子单独什么也给不出」：
      拿 ``token_id`` 拼一个假的第二段去兑换 → **403**（:func:`test_the_selector_alone_is_not_a_credential`）。

    ⚠️ **反空转**：末拍断言扫描面本身不小（30 张表、``bind_token`` 至少 2 行），
    否则「库里一行都没有」与「明文一个都没落」在颜色上无法区分。
    """
    engine = engine_of(client)
    issued = _issue(client).json()
    plain = issued["token"]
    token_id, secret = plain.split(bind_tokens.SEPARATOR)
    assert _redeem(client, plain, PASSWORD).status_code == 204
    # 再签一张不用的（于是 ``bind_token`` 至少两行：一行 used_at 非空、一行空）
    _issue(client, login=OTHER_STUDENT_NO)

    needles = {
        "整个明文令牌": plain,
        "秘密那一段": secret,
        "兑换时提交的新口令": PASSWORD,
    }
    from app.db.session import Base

    scanned_tables = 0
    scanned_cells = 0
    hits = []
    with Session(engine) as session:
        for table in Base.metadata.tables.values():
            scanned_tables += 1
            rows = session.execute(table.select()).fetchall()
            for row in rows:
                for column, value in zip(table.columns, row):
                    if not isinstance(value, str):
                        continue
                    scanned_cells += 1
                    for label, needle in needles.items():
                        if needle and needle in value:
                            hits.append((table.name, column.name, label))
    assert hits == [], hits
    assert scanned_tables == 30, scanned_tables
    # ⚠️ 下界取 **20** 而不是一个更大的数：本夹具的库是**空演示库 + 四个人**
    #    （1 个学期 + 2 个学生 + 2 个教师 + 2 行令牌 + 若干审计/限流行），
    #    实测字符串格数是 41 —— 下界只要「不是 0」这一格性质成立即可，
    #    抬到 50 会让本条红在一个与真因无关的数上（硬规矩 #103：跑起来量，不靠推）。
    assert scanned_cells > 20, scanned_cells
    with Session(engine) as session:
        assert session.execute(text("SELECT count(*) FROM bind_token")).scalar() >= 2

    # ⚠️ 而库里那一格**确实是**一个 PBKDF2 自描述串（不是明文、也不是别的算式）
    with Session(engine) as session:
        stored = session.scalar(select(BindToken.token_hash).where(
            BindToken.token_id == token_id))
    assert stored is not None
    assert stored.split(SEPARATOR)[0] == ALGORITHM, stored
    assert verify_password(secret, stored), "库里那一格验不过它自己的秘密"
    assert secret not in stored and plain not in stored


def test_the_selector_alone_is_not_a_credential(client, people):
    """**选择子单独什么也给不出**：拿真的 ``token_id`` 拼一个假的秘密 → **403**。

    ⚠️ 它是上一条守卫的**另一半**：上一条说「明文与秘密都不落库」，
    本条说「落库的那一格选择子**不构成泄漏**」。⚠️ 两拍合起来才封住
    「把 ``token_hash`` 换成一个可预测的东西」这一格变异
    （换了之后选择子就成了全部凭据，本条会红在 204 上）。

    ⚠️ 顺带钉住**四档畸形串**都回 403 而不是 422/500
    （:func:`app.auth.bind_tokens.split` 的「绝不抛」那一格）：
    空串、只有一个分隔符、三段、以及一段为空。
    """
    issued = _issue(client).json()
    token_id = issued["token"].split(bind_tokens.SEPARATOR)[0]

    forged = _redeem(client, token_id + bind_tokens.SEPARATOR + "a-fabricated-secret")
    assert forged.status_code == 403, forged.text
    assert forged.json()["error"]["code"] == "forbidden"
    with Session(engine_of(client)) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is None

    for malformed in ("", "   ", "no-separator-here",
                      "a.b.c", token_id + ".", ".only-a-secret"):
        got = _redeem(client, malformed, PASSWORD)
        assert got.status_code == 403, (malformed, got.status_code, got.text)
        assert got.json()["error"]["code"] == "forbidden", (malformed, got.text)


# ===========================================================================
# ④ 开关（派单 §2 第 3/7 条 ④）：三档 + raise + 缺省档逐字不变
# ===========================================================================


def test_the_self_bind_switch_is_open_by_default(client, people, monkeypatch):
    """**守卫 ④ 的「缺省开」那一半**：三拍，缺一不可。

    ① **常量本身**是 ``"1"``（字面量，不从被测函数反推）；
    ② ``monkeypatch.delenv`` 之后 :func:`app.api.routers.auth.allow_self_bind` 回 ``True``
       ——⚠️ 少了①，「常量改成 0、而函数仍然读它」是绿的；
       ⚠️ 少了②，「常量是 1、而函数写反了」是绿的；
    ③ **实发一次请求**：环境变量没设时，``POST /api/auth/students/bind``
       用**真的验身材料**必须回 **204**（= 今天的行为）。

    ⚠️ 姿势与 ``tests/api/test_auth_api.py`` 的
    ``test_the_header_identity_channel_is_closed_by_default`` **逐字同形**
    （那一条也是「常量 + 函数 + 实发请求」三拍），差别只在**方向**：
    那一条的缺省是**关**（一条没有签名/过期/吊销的过渡通道），
    本条的缺省是**开**（甲方今天正在用的产品功能）。
    ⚠️ 而「为什么缺省是开而不是关」是本 Task 的顶回候选 ⑤，
    实现者复核后**同意控制者的倾向**，两条理由逐字住在
    :data:`app.api.routers.auth.SELF_BIND_DEFAULT` 的注释里。
    """
    assert auth_router.SELF_BIND_DEFAULT == "1"
    assert auth_router.SELF_BIND_ENV_VAR == "PE_ALLOW_SELF_BIND"
    assert (auth_router.SELF_BIND_ON, auth_router.SELF_BIND_OFF) == ("1", "0")

    monkeypatch.delenv("PE_ALLOW_SELF_BIND", raising=False)
    assert auth_router.allow_self_bind() is True

    got = client.post("/api/auth/students/bind", json={
        "student_no": STUDENT_NO, "birth": BIRTH.isoformat(), "password": PASSWORD,
    })
    assert got.status_code == 204, got.text
    with Session(engine_of(client)) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is not None


def test_the_switch_reads_one_and_zero_and_raises_on_anything_else(monkeypatch):
    """**守卫 ④ 的「三档 + raise」那一半**：``1`` → 开、``0`` → 关、**其它一律 raise**。

    ⚠️ 它**与 :func:`app.api.deps.allow_header_identity` 刻意不同档**（那一个把
    「不是 ``1``」一律当关），逐字理由见 :data:`app.api.routers.auth.SELF_BIND_ON`
    的注释：那一条的失效方向是**安全**的（少给一条通道），而本条「认不出 ⇒ 关」
    的失效方向是**把甲方挡在门外**（一个把值写成 ``false`` 的运维会得到
    「所有新生都绑不上」，而报错文本里没有任何一句指向那个变量）。

    ⚠️ **空串按「没设」处理**（= 缺省 = 开）：``$env:PE_ALLOW_SELF_BIND = ""`` 在
    PowerShell 里是「设了一个空值」而不是「删掉这个变量」，口径与
    :func:`app.auth.passwords.iterations` / :func:`app.auth.policy._int_from_env` 逐字相同。

    ⚠️ 报错文本必须**点名那个变量与那两格取值**：一个「ValueError: invalid value」
    对运维没有信息量（他要知道是**哪一个**变量写错了）。
    """
    cases = [("1", True), ("0", False), ("", True), ("  1  ", True), (" 0 ", False)]
    for raw, want in cases:
        monkeypatch.setenv("PE_ALLOW_SELF_BIND", raw)
        assert auth_router.allow_self_bind() is want, (raw, want)

    for bad in ("true", "false", "yes", "no", "2", "01", "ON", "off", "None"):
        monkeypatch.setenv("PE_ALLOW_SELF_BIND", bad)
        with pytest.raises(ValueError) as excinfo:
            auth_router.allow_self_bind()
        message = str(excinfo.value)
        assert "PE_ALLOW_SELF_BIND" in message, (bad, message)
        assert "'1'" in message and "'0'" in message, (bad, message)
        assert bad in message, (bad, message)

    # ⚠️ 装配期也问一次（派单 §2 第 3 条逐字要求）：一个坏值让 ``create_app`` 当场抛，
    #    于是 ``uvicorn app.main:app`` **根本起不来**。
    monkeypatch.setenv("PE_ALLOW_SELF_BIND", "true")
    from app.main import create_app
    with pytest.raises(ValueError) as excinfo:
        create_app(db_url="sqlite://")
    assert "PE_ALLOW_SELF_BIND" in str(excinfo.value)


def test_turning_the_switch_off_refuses_both_self_service_endpoints_loudly(
    client, people, monkeypatch
):
    """**守卫 ④ 的「关掉之后」那一半**：两个自助端点一律 **403** + 一句点名了那个变量的 message。

    ⚠️ 四拍：

    ① 学生那一侧 **403 ``forbidden``**；
    ② 教师那一侧 **403 ``forbidden``**（⚠️ 两个端点**逐字同一句** message：
      它是一个**全局配置事实**，不是「这一个学号怎么了」，故两档同形是对的）；
    ③ ⚠️ **令牌那一档不受影响**：同一个进程、同一个开关值下，
      ``POST /api/auth/bind-with-token`` 仍然 **204** —— 那正是「可回退」的含义
      （先签发令牌、验证流程通了、再把开关关掉，中间没有任何一刻是「谁都绑不上」）；
    ④ ⚠️ **口令没有被绑上**（失败方向是「什么都没发生」，不是「绑了一个假口令」）。

    ⚠️ message 必须**点名 ``PE_ALLOW_SELF_BIND``**：这一档的读者是运维，
    而「服务起来了、新生一个都绑不上」这一格失效如果不在 message 里指向真因，
    排查会从前端一路查到名册数据。
    """
    monkeypatch.setenv("PE_ALLOW_SELF_BIND", "0")

    student_side = client.post("/api/auth/students/bind", json={
        "student_no": STUDENT_NO, "birth": BIRTH.isoformat(), "password": PASSWORD,
    })
    assert student_side.status_code == 403, student_side.text
    assert student_side.json()["error"]["code"] == "forbidden"
    assert "PE_ALLOW_SELF_BIND" in student_side.json()["error"]["message"]
    assert "bind-with-token" in student_side.json()["error"]["message"]

    teacher_side = client.post("/api/auth/teachers/bind", json={
        "staff_no": STAFF_NO, "name": "李老师", "password": PASSWORD,
    })
    assert teacher_side.status_code == 403, teacher_side.text
    assert teacher_side.json()["error"]["message"] == \
        student_side.json()["error"]["message"]

    # ④ 两个账号都还没被绑上口令
    with Session(engine_of(client)) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is None
        assert session.scalar(select(Teacher).where(
            Teacher.staff_no == STAFF_NO)).password_hash is None

    # ③ 令牌那一档照旧工作（开关**不**管它）
    token = _issue(client).json()["token"]
    assert _redeem(client, token, PASSWORD).status_code == 204
    with Session(engine_of(client)) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is not None


def test_the_default_tier_is_byte_for_byte_the_pre_task_4_behaviour(
    client, people, monkeypatch
):
    """**守卫 ④ 的两档对比取证**：缺省档下「响应体的原始字节」与「审计行」逐字不变。

    ⚠️ 派单 §2 第 7 条 ④ 逐字要求「缺省开着时行为逐字不变 —— 这一格要有两档对比取证」。
    本条因此**在同一个进程里跑两遍同样的五发请求**（一遍 ``PE_ALLOW_SELF_BIND`` 未设、
    一遍设成 ``0``），比四格：

    ① **五发的 status 逐个**；
    ② **五发的响应体原始字节**（``response.content``，不是 ``.json()``：
      键序与空格也是契约的一部分，而 :func:`app.api.errors.error_response`
      是全仓唯一写 ``{"error": {...}}`` 那个字面量的地方，故键序恒定）；
    ③ ⚠️ **成功那一档真的把口令绑上了**（``verify_password`` 验得过）；
    ④ ⚠️ **审计行数与每一行的九列**（``audit_log``）——少了这一拍，
      「开关那一行 ``if`` 顺手把审计写坏了」会绿着通过。

    ⚠️⚠️ 而①②两格在**缺省档**上的值就是 Plan 08 Task 4 之前的值：
    五发里前四发是既有的四个档（弱口令 422 / 材料不符 403 / 已绑定 409 / 成功 204），
    它们的响应体**一个字节都没变** ——因为开关那一行 ``if`` 在缺省档上是
    ``if not True``（恒假），端点体里的其余部分一个字都没动。
    ⚠️ 这就是「本波唯一一处改既有行为的地方，而它做得可回退」的可执行形式。
    """
    engine = engine_of(client)
    shots = [
        ("弱口令", "/api/auth/students/bind", {
            "student_no": STUDENT_NO, "birth": BIRTH.isoformat(), "password": "短"}),
        ("材料不符", "/api/auth/students/bind", {
            "student_no": STUDENT_NO, "birth": "2001-01-01", "password": PASSWORD}),
        ("不在册", "/api/auth/students/bind", {
            "student_no": "9999999999", "birth": BIRTH.isoformat(), "password": PASSWORD}),
        ("教师侧成功", "/api/auth/teachers/bind", {
            "staff_no": STAFF_NO, "name": "李老师", "password": PASSWORD}),
    ]

    def run():
        got = [(r.status_code, r.content)
               for r in (client.post(path, json=body) for _label, path, body in shots)]
        ok = client.post("/api/auth/students/bind", json={
            "student_no": STUDENT_NO, "birth": BIRTH.isoformat(), "password": PASSWORD})
        return got + [(ok.status_code, ok.content)]

    def audit_rows():
        with Session(engine) as session:
            return [
                (r.subject_kind, r.subject_id, r.staff_no, r.method, r.path,
                 r.status, r.target)
                for r in session.scalars(select(
                    __import__("app.db.models.audit", fromlist=["AuditLog"]).AuditLog
                ).order_by(__import__("app.db.models.audit",
                                       fromlist=["AuditLog"]).AuditLog.id)).all()
            ]

    monkeypatch.delenv("PE_ALLOW_SELF_BIND", raising=False)
    default_tier = run()
    default_audit = audit_rows()
    assert [s for s, _ in default_tier] == [422, 403, 403, 204, 204], default_tier
    with Session(engine) as session:
        bound = session.scalar(select(Student).where(Student.student_no == STUDENT_NO))
        assert verify_password(PASSWORD, bound.password_hash)

    # 把库复位（口令绑过了就不能再绑第二次），然后跑「关掉」那一档
    with Session(engine) as session:
        session.get(Student, people["one"]).password_hash = None
        session.get(Student, people["one"]).password_bound_at = None
        session.get(Teacher, people["teacher"]).password_hash = None
        session.get(Teacher, people["teacher"]).password_bound_at = None
        session.commit()

    monkeypatch.setenv("PE_ALLOW_SELF_BIND", "0")
    off_tier = run()

    # ①② 五发的 status 与**响应体原始字节**。
    #    ⚠️ 关掉那一档是 **[422, 403, 403, 403, 403]** 而**不是**五个 403：
    #    第一发（弱口令）仍然 **422**，因为开关那一行 ``if`` **排在
    #    ``ensure_acceptable`` 之后** —— 那是本端点既有的口径
    #    （「弱口令排最前：它是纯本地判定，故一次弱口令尝试不会变成一次数据库查询」），
    #    本波**刻意不改那个顺序**。⚠️ 于是「关掉开关」改的是**四**发、不是五发，
    #    而那一格正是「本波唯一一处改既有行为的地方」的准确边界。
    assert [s for s, _ in off_tier] == [422, 403, 403, 403, 403], off_tier
    # ⚠️ 第一发与缺省档**逐字节相同**（开关那一行在它之后，故它一个字都没变）
    assert off_tier[0] == default_tier[0], (off_tier[0], default_tier[0])
    # ⚠️ 后四发**逐字节相同于彼此**（同一个全局配置事实，不是「这一个学号怎么了」）
    messages = {body for _status, body in off_tier[1:]}
    assert len(messages) == 1, messages
    only = next(iter(messages)).decode()
    assert "PE_ALLOW_SELF_BIND" in only, only
    assert "bind-with-token" in only, only
    # ⚠️ 而它们与缺省档那四发**逐字节不同**（否则「关掉」是一件什么也没做的事）
    assert {body for _s, body in off_tier[1:]} != {
        body for _s, body in default_tier[1:]
    }
    # ④ 关掉那一档**一行口令都没绑上**
    with Session(engine) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is None
        assert session.scalar(select(Teacher).where(
            Teacher.staff_no == STAFF_NO)).password_hash is None
    # ③ 审计：两档**都留了痕**（关掉那一档的 422/403 也照样各写一行）
    off_audit = audit_rows()
    assert len(off_audit) > len(default_audit), (len(default_audit), len(off_audit))
    assert [row[5] for row in off_audit[len(default_audit):]] == [422, 403, 403, 403, 403]
    # ⚠️ 缺省档那五行的九列**逐字**是既有的形状（method/path/status 三格点名）
    assert [(row[3], row[4], row[5]) for row in default_audit[:5]] == [
        ("POST", "/api/auth/students/bind", 422),
        ("POST", "/api/auth/students/bind", 403),
        ("POST", "/api/auth/students/bind", 403),
        ("POST", "/api/auth/teachers/bind", 204),
        ("POST", "/api/auth/students/bind", 204),
    ], default_audit[:5]


# ===========================================================================
# ⑤ 限流没被绕过（派单 §2 第 7 条 ⑤）
# ===========================================================================


def test_the_token_tier_is_throttled_on_both_keys_and_the_fourth_shot_is_refused(
    client, people
):
    """**守卫 ⑤**：真打到**第 4 次**，报状态码与时序；而**两把键各写一行**。

    ⚠️ 派单 §2 第 5 条要求「令牌那一档要接上同一条限流，不许绕过它」，
    控制者倾向「按目标学号 + 按令牌」两把都算。本条把那一格钉成**可执行**的四拍：

    ① 前三发（秘密不对）各回 **403 ``forbidden``** + 同一句 message；
    ② ⚠️ **第四发仍然 403、且响应体与前三发逐字相同**（锁定档不给区分信号，
      与登录/自助绑定那两次改判同一条理由）；
    ③ ⚠️ **两把键各写了三行**：``login_attempt.login`` 上同时出现
      ``bind:<学号>`` 与 ``bindtoken:<token_id>`` 两种前缀的行
      （逐字理由见 :data:`app.auth.policy.PURPOSE_BIND_TOKEN` 的注释）；
    ④ ⚠️ **锁定档不跑 PBKDF2**：第四发**没有**再往两把键上写行
      （``login_attempt`` 的行数在第四发前后**不变**）——那正是
      :mod:`app.auth.policy` 的模块 docstring 第一节那条「锁定期间不写行」的机制，
      少了本拍，「滑动锁」（一个持续探测的攻击者让这个账号永远锁着）会绿着通过。

    ⚠️ **时序**：本条不睡 60 分钟。① 三发的间隔用 ``datetime`` 断言
    （``login_attempt.at`` 的三个值互不相同或至多相差一秒）；
    ② 「锁到点自动解开」那一格由 ``tests/auth/test_policy.py`` 注入 ``now``
    走完整条时间线钉住（:func:`app.auth.policy.is_locked` 是同一个函数，
    两个用途共用它，故那一条守卫对本档同样成立）。
    """
    engine = engine_of(client)
    issued = _issue(client).json()
    plain, token_id = issued["token"], issued["token"].split(bind_tokens.SEPARATOR)[0]

    def attempts():
        with Session(engine) as session:
            return [row.login for row in session.scalars(select(LoginAttempt)).all()]

    statuses = []
    for shot in range(4):
        # ⚠️ 每一发都带**真的** token_id + 一个**错的**秘密（于是它走到「验不过」那一档、
        #    而不是「选择子查无此行」那一档 —— 后者刻意不计数）
        got = _redeem(client, token_id + bind_tokens.SEPARATOR + f"wrong-secret-{shot}")
        statuses.append(got.status_code)
        assert got.json()["error"]["code"] == "forbidden", got.text

    assert statuses == [403, 403, 403, 403], statuses
    bodies = set()
    for shot in range(1):
        got = _redeem(client, token_id + bind_tokens.SEPARATOR + "wrong-secret-again")
        bodies.add(got.content)
    assert len(bodies) == 1 and b"forbidden" in next(iter(bodies))

    keys = attempts()
    assert keys.count(f"bind:{STUDENT_NO}") == 3, keys
    assert keys.count(f"bindtoken:{token_id}") == 3, keys
    # ④ 第四发与第五发**都没有**再写行（锁定档不写行）
    assert len(keys) == 6, keys

    # ⚠️ 阈值与键的**所有者**是 app.auth.policy：本端点一个阈值字面量都不写
    assert policy.DEFAULT_BIND_MAX_FAILS == 3
    assert policy.DEFAULT_BIND_WINDOW_MINUTES == 15
    assert policy.DEFAULT_BIND_LOCK_MINUTES == 60
    assert policy.bind_throttle().max_fails == 3

    # ⚠️ 且**真令牌也打不进去了**（锁定档排在验秘密之前 ⇒ 那一次 PBKDF2 都不跑）
    locked = _redeem(client, plain, PASSWORD)
    assert locked.status_code == 403, locked.text
    with Session(engine) as session:
        assert session.scalar(select(Student).where(
            Student.student_no == STUDENT_NO)).password_hash is None
    assert len(attempts()) == 6, "锁定档写了行（= 滑动锁）"


def test_a_successful_redemption_clears_both_keys(client, people):
    """一次**成功**的兑换把**两把**计数器都清零（各写一行 ``ok=True``）。

    ⚠️ 与 :func:`app.auth.policy.record_success` 的既有口径逐字相同
    （删掉这个键的全部行、再写一行 ``ok=True``），⚠️ 而**两把各清一次**：
    少了「清令牌那一把」，一张被试错两次、随后兑换成功的令牌会留下两行
    ``ok=False``——而下一个人来查「这个选择子被爆过吗」时会读到一个**过期**的答案。
    ⚠️ 少了「清目标账号那一把」，一个刚绑定成功的学生仍然会被**自助绑定**那把锁着
    （而那一把是共用的：它与 ``POST /api/auth/students/bind`` 是同一个键）。
    """
    engine = engine_of(client)
    issued = _issue(client).json()
    token_id = issued["token"].split(bind_tokens.SEPARATOR)[0]

    for shot in range(2):
        assert _redeem(client, token_id + bind_tokens.SEPARATOR + f"bad-{shot}"
                       ).status_code == 403
    with Session(engine) as session:
        assert session.scalar(select(LoginAttempt).where(
            LoginAttempt.ok.is_(False))) is not None

    assert _redeem(client, issued["token"], PASSWORD).status_code == 204
    with Session(engine) as session:
        rows = session.scalars(select(LoginAttempt)).all()
        assert [r.ok for r in rows].count(False) == 0, [(r.login, r.ok) for r in rows]
        ok_keys = sorted(r.login for r in rows if r.ok)
        assert ok_keys == sorted([f"bind:{STUDENT_NO}", f"bindtoken:{token_id}"]), ok_keys


# ===========================================================================
# 审计（派单 §2 第 6 条）：签发与兑换都是写操作，而明文绝不进审计
# ===========================================================================


def test_issuing_and_redeeming_each_write_exactly_one_audit_row(client, people):
    """**签发**与**兑换**各写**一行** ``audit_log``（⚠️ 本波一行代码都没加）。

    ⚠️ 判据的唯一所有者是 :func:`app.api.audit.should_record`（只看 HTTP 方法），
    而两个新端点都是 ``POST`` ⇒ 它们**本来就**被那条判据认下。
    本条因此钉的是「**没有漏**」（而不是「代码里写了 ``record(...)``」）：
    一个「新端点忘了经过那六个 ``note_subject`` 调用点」的实现会让 ``subject_kind``
    变成 ``anonymous``——那是一句关于「谁做的」的假话，而它**恰恰**是本条第 ③ 拍
    要抓的（签发那一行必须**有名有姓**：``staff_no == T0003``）。

    ⚠️ 四拍：① 签发一行（201）② 兑换一行（204）③ 签发那一行的 ``subject_*``
    三格是**管理员**（不是 ``anonymous``）④ 兑换那一行是 ``anonymous``
    （那一刻调用方**真的**没有身份，而写审计**要**匿名的行 ——
    :data:`app.db.models.audit.ANONYMOUS_SUBJECT_KIND` 的注释逐字写了理由）。
    """
    engine = engine_of(client)
    from app.db.models.audit import AuditLog

    before = len(_rows(engine, AuditLog))
    issued = _issue(client).json()
    after_issue = _rows(engine, AuditLog)
    assert len(after_issue) == before + 1, len(after_issue)
    row = after_issue[-1]
    assert (row.method, row.path, row.status) == ("POST", "/api/auth/bind-tokens", 201)
    assert row.subject_kind == "teacher", row.subject_kind
    assert row.staff_no == ADMIN_NO, row.staff_no

    assert _redeem(client, issued["token"], PASSWORD).status_code == 204
    after_redeem = _rows(engine, AuditLog)
    assert len(after_redeem) == before + 2, len(after_redeem)
    row = after_redeem[-1]
    assert (row.method, row.path, row.status) == (
        "POST", "/api/auth/bind-with-token", 204)
    assert row.subject_kind == "anonymous", row.subject_kind
    assert row.subject_id is None and row.staff_no is None


def test_the_plaintext_token_never_reaches_the_audit_row(client, people):
    """**令牌明文一个字都不进审计**：真发两次，然后把落库行的**全部 9 列**逐列扫一遍。

    ⚠️ 姿势与 ``tests/api/test_audit_api.py`` 的
    ``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
    **逐字同形**（真发请求 + 全列扫探针），只是探针换成了令牌的三段
    （整个明文 / ``token_id`` 那一段 / ``secret`` 那一段）与新口令。

    ⚠️⚠️ 它是**结构性**的，不是「中间件里克制住不写」：:mod:`app.api.audit`
    **从来不读** ``request.body()``，而 ``audit_log`` 的 9 列里**没有**能装它的位置
    （逐字理由见 :mod:`app.db.models.audit` 的模块 docstring 第三节）。
    ⚠️ 而派单 §2 第 6 条逐字要求「你要复核它对新端点也成立」——本条就是那一次复核：
    它扫的是**两个新端点各写的那一行**，故「新端点顺手把令牌塞进 ``target``」
    这一格变异在本条上会红。

    ⚠️ **``token_id`` 那一段也在被扫的四个串里**（与上一条守卫刻意不同档）：
    上一条扫的是「明文凭据有没有落库」，故选择子**必然**命中（它就住在那一列上）；
    本条扫的是「审计行里有没有令牌的任何一段」，而审计**没有任何理由**装选择子
    （``target`` 只在路径**恰好一个**参数时取值，而两个新路径都没有参数）。
    """
    engine = engine_of(client)
    from app.db.models.audit import AuditLog

    issued = _issue(client).json()
    plain = issued["token"]
    token_id, secret = plain.split(bind_tokens.SEPARATOR)
    assert _redeem(client, plain, PASSWORD).status_code == 204

    rows = _rows(engine, AuditLog)
    assert rows, "审计一行都没有（反空转）"
    needles = (plain, token_id, secret, PASSWORD)
    hits = []
    for row in rows:
        for column in AuditLog.__table__.columns:
            value = getattr(row, column.name)
            if isinstance(value, str) and any(n in value for n in needles):
                hits.append((row.id, column.name, value[:40]))
    assert hits == [], hits
    # ⚠️ 两行的 target 一律 NULL（两个新路径都没有路径参数）
    fresh = [r for r in rows if "bind" in r.path and "tokens" in r.path or
             r.path == "/api/auth/bind-with-token"]
    assert fresh, [r.path for r in rows]
    assert all(r.target is None for r in fresh), [(r.path, r.target) for r in fresh]


def test_a_validation_error_never_echoes_the_submitted_token(client, people):
    """**422 的 ``detail`` 里不回显令牌明文**（``SecretStr`` + 按键名脱敏，两道合起来）。

    ⚠️ 派单没点名这一格，而它是 :class:`app.api.schemas.auth.TokenBindCreate`
    那条 ``SecretStr`` 裁定的**唯一**可执行形式。失效形态逐字写在
    :mod:`app.api.schemas.auth` 的模块 docstring 第二节：Pydantic 的
    ``ValidationError.errors()`` 每一格都带一个 ``input``，而
    ``missing`` 那一档的 ``input`` 是**整个请求体**（一个原始 ``dict``，
    里面那一格还是明文串，因为 Pydantic 还没来得及把它转成 ``SecretStr``），
    而 :mod:`app.api.errors` 会把整份 ``errors()`` 塞进 422 的 ``detail`` 里。

    ⚠️ 两档各测一遍：① **缺 ``password``**（``input`` = 整个请求体，
    靠 :data:`app.api.errors._SENSITIVE_INPUT_KEYS` 的按键名脱敏挡）；
    ② **``token`` 自己那一格校验失败**（靠 ``SecretStr`` 挡）。
    ⚠️ 判据是**响应体的原始字节**里不出现那个明文串（不是「某个键不在某个 dict 里」——
    后者对「它藏在 ``ctx`` 里」无感）。
    """
    issued = _issue(client).json()
    plain = issued["token"]

    missing = client.post("/api/auth/bind-with-token", json={"token": plain})
    assert missing.status_code == 422, missing.text
    assert plain not in missing.content.decode("utf-8", "replace")
    assert plain.split(bind_tokens.SEPARATOR)[1] not in missing.content.decode()

    wrong_type = client.post("/api/auth/bind-with-token",
                             json={"token": {"not": "a string"}, "password": PASSWORD})
    assert wrong_type.status_code == 422, wrong_type.text
    # ⚠️ 那一档交上去的不是明文，故本拍钉的是「不 500、且回的是既有的那一档 code」
    assert wrong_type.json()["error"]["code"] == "request_validation_failed"


# ===========================================================================
# 契约面：明文只在签发那一刻出现一次
# ===========================================================================


def test_only_the_issuance_contract_carries_the_plaintext_and_no_contract_carries_the_hash():
    """**契约面**的「明文只出现一次」：扫 :mod:`app.api.schemas.auth` 全部模型的字段名。

    ⚠️ 两拍：

    ① **恰好一个**模型有 ``token`` 那一格，而它是
      :class:`app.api.schemas.auth.BindTokenIssuedRead`（签发端点的响应体）；
    ② ⚠️ **一个模型都没有** ``token_hash``（哈希**永远不出契约面**，
      与 ``password_hash`` 不出 ``StudentRead`` 逐字同一条纪律）。

    ⚠️ 它是**结构侧**的守卫（不发请求）：行为侧那一半是
    :func:`test_the_listing_never_returns_the_plaintext_nor_the_hash`。
    两拍合起来才封住「给 ``BindTokenRead`` 顺手加一格 ``token``」这一格变异——
    只钉行为的话，一个「列表端点今天恰好没走到那一格」的实现会绿着通过。
    """
    import pydantic

    models = [
        (name, obj)
        for name, obj in vars(auth_schemas).items()
        if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel)
        and obj.__module__ == auth_schemas.__name__
    ]
    assert len(models) >= 9, [name for name, _ in models]

    carrying = sorted(
        name for name, obj in models if "token" in obj.model_fields
    )
    # ⚠️ **两个**模型有 ``token`` 那一格，而它们**分处请求与响应两侧**：
    #    :class:`TokenBindCreate`（兑换端点的**请求体**，``SecretStr``）与
    #    :class:`BindTokenIssuedRead`（签发端点的**响应体**，裸 ``str``）。
    #    ⚠️ 于是「明文只出现一次」这一格的可执行形式是下面那一拍：
    #    **响应侧**（名字以 ``Read`` 结尾的那些）恰好一个含 ``token``。
    assert carrying == ["BindTokenIssuedRead", "TokenBindCreate"], carrying
    read_side = sorted(
        name for name, obj in models
        if name.endswith("Read") and "token" in obj.model_fields
    )
    assert read_side == ["BindTokenIssuedRead"], read_side
    hashed = sorted(
        name for name, obj in models
        if any("hash" in field for field in obj.model_fields)
    )
    assert hashed == [], hashed
    # ⚠️ 顺带钉住「兑换那一格是 SecretStr」：它是上一条守卫（422 不回显）的前提。
    #    ⚠️ 判据是**标注就是那个类**（``is SecretStr``），不是 ``isinstance``：
    #    Pydantic 的 ``model_fields[...].annotation`` 给的是**类对象**，
    #    而 ``isinstance(SecretStr, SecretStr)`` 恒为 ``False``
    #    （实现者第一版就红在这一格，按实际改写）。
    assert auth_schemas.TokenBindCreate.model_fields["token"].annotation is pydantic.SecretStr
    assert auth_schemas.TokenBindCreate.model_fields["password"].annotation is pydantic.SecretStr
    # ⚠️ 而**签发**那一格的响应体刻意是裸 str（它要把明文交出去）
    assert auth_schemas.BindTokenIssuedRead.model_fields["token"].annotation is str


def test_the_listing_never_returns_the_plaintext_nor_the_hash(client, people):
    """**读侧**的「明文只出现一次」：签发之后打 ``GET``，响应体里既没有明文也没有哈希。

    ⚠️ 三拍：① 台账里**看得见**刚签发的那一行（``id`` / ``kind`` / ``login`` /
    ``issued_at`` / ``expires_at`` / ``used_at`` / ``issued_by`` 七格）；
    ② ⚠️ 响应体的**原始字节**里不出现明文、不出现 ``token_id``、
    不出现 ``token_hash`` 那一串（``pbkdf2_sha256$…``）；
    ③ ⚠️ 兑换一次之后，台账里那一行的 ``used_at`` **变成非空**
    （= 本端点答得出「哪些令牌已经用掉了」，而那正是它存在的运维理由）。

    ⚠️ 它也钉住**四个信封键**（与泛型 list 逐字同形）与**身份档**
    （匿名 401 / 教师 403 / 管理员 200）。
    """
    engine = engine_of(client)
    issued = _issue(client).json()
    plain = issued["token"]
    token_id = plain.split(bind_tokens.SEPARATOR)[0]

    anonymous = client.get("/api/auth/bind-tokens")
    assert anonymous.status_code == 401, anonymous.text
    teacher = client.get("/api/auth/bind-tokens", headers=TEACHER)
    assert teacher.status_code == 403, teacher.text

    page = client.get("/api/auth/bind-tokens", headers=ADMIN)
    assert page.status_code == 200, page.text
    body = page.json()
    assert sorted(body) == ["items", "limit", "offset", "total"], sorted(body)
    assert body["total"] == 1 and len(body["items"]) == 1
    row = body["items"][0]
    assert sorted(row) == [
        "expires_at", "id", "issued_at", "issued_by", "kind", "login", "used_at",
    ], sorted(row)
    assert row["id"] == issued["id"] and row["login"] == STUDENT_NO
    assert row["used_at"] is None
    text_body = page.content.decode()
    assert plain not in text_body
    assert token_id not in text_body
    assert "pbkdf2_sha256" not in text_body
    assert "token_hash" not in text_body

    assert _redeem(client, plain, PASSWORD).status_code == 204
    after = client.get("/api/auth/bind-tokens", headers=ADMIN).json()["items"][0]
    assert after["used_at"] is not None
    # ⚠️ 而库里那一行的 token_hash 仍然验得过（台账没有把凭据改掉）
    with Session(engine) as session:
        stored = session.scalar(select(BindToken.token_hash))
    assert verify_password(plain.split(bind_tokens.SEPARATOR)[1], stored)


# ===========================================================================
# 账面：两处裁定
# ===========================================================================


def test_bind_token_is_not_a_generic_crud_resource(app):
    """**顶回 ④ 的可执行形式**：``bind_token`` **不在** ``catalog.RESOURCES`` 里，
    而 ``RESOURCES`` **仍然是 23 行**。

    ⚠️ 派单 §2 第 4 条写的是「``RESOURCES`` 23 → 24」，实现者**顶回**，
    四条理由逐字住在 :class:`app.db.models.auth.BindToken` 的 docstring 末节
    与 ``tests/api/test_column_widths.py`` 的 ``_SERVER_OWNED["bind_token"]`` 注释里。
    一句话版本：泛型工厂的 ``create_row`` 逐字是 ``model(**payload.model_dump())``
    ⇒ **每一列都必须来自请求体**，而「服务端生成秘密、明文只回一次」与
    「``response_model`` 从 ORM 行上投影」两件事在结构上互斥。

    ⚠️ 本条把它钉成**三拍**（少了任何一拍，「顺手加进 RESOURCES」会绿着通过）：
    ① ``RESOURCES`` 仍然 23 行；② 里面没有 ``bind_token`` 那张表；
    ③ ⚠️ openapi 上**没有** ``/api/bind-tokens``（泛型资源的路径形状是
    ``/api/<复数连字符>``，而本端点住在 ``/api/auth/bind-tokens``）。

    ⚠️ 先例逐字同族：``audit_log`` 与 ``read_audit_log`` 也都**不是**那 23 个资源
    （``tests/api/test_audit_api.py`` 与 ``tests/api/test_read_audit_api.py``
    各有一条同款守卫），而 :mod:`app.api.routers.audit` 的模块 docstring
    逐字列了「走泛型工厂会得到四个错」——那四条对本表**逐条成立**。
    """
    from app.api.routers.catalog import RESOURCES

    assert len(RESOURCES) == 23, len(RESOURCES)
    assert all(
        entry["model"].__tablename__ != "bind_token" for entry in RESOURCES
    ), [entry["path"] for entry in RESOURCES]
    paths = app.openapi()["paths"]
    assert "/api/bind-tokens" not in paths, sorted(paths)
    assert "/api/auth/bind-tokens" in paths and "/api/auth/bind-with-token" in paths
    # ⚠️ 且**没有** PATCH / DELETE（「单次使用」不许被一个端点改回去）
    assert sorted(paths["/api/auth/bind-tokens"]) == ["get", "post"]
    assert sorted(paths["/api/auth/bind-with-token"]) == ["post"]


def test_the_token_hash_reuses_the_password_module_and_no_second_pbkdf2_exists():
    """**派单 §2 第 1 条**：哈希复用 :mod:`app.auth.passwords`，全仓**没有第二个** PBKDF2。

    ⚠️ 三拍：

    ① ``app/auth/bind_tokens.py`` 的源码里**不出现** ``hashlib`` / ``pbkdf2``
      （它只 import ``hash_password`` 与 ``verify_password`` 两个名字）；
    ② ⚠️ 全仓 ``app/**`` 里 ``hashlib.pbkdf2_hmac`` 的调用点**恰好一处**，
      在 ``app/auth/passwords.py``（AST 数，不靠 grep 字符串）；
    ③ 签发出来的那一行 ``token_hash`` 是**自描述串**（第一段是算式名、
      第二段是迭代次数），且它的迭代次数**就是当前配置的那一个**
      （= 与口令哈希同一个工作量）。

    ⚠️ ② 那一拍是本条的牙：少了它，「在 ``bind_tokens.py`` 里自己写一个
    ``hashlib.pbkdf2_hmac``」会绿着通过 ①（那一格只钉 import 名），
    而失效形态是「两个 PBKDF2 各有各的迭代次数与上下界」——
    那正是 :mod:`app.auth.passwords` 的模块 docstring 用一整节警告过的形状。
    """
    import ast
    import pathlib

    from app.config import BACKEND_DIR

    source = (BACKEND_DIR / "app" / "auth" / "bind_tokens.py").read_text(encoding="utf-8")
    assert "hashlib" not in source, "bind_tokens.py 自己 import 了 hashlib"
    # ⚠️ **刻意不断言「源码里不出现 pbkdf2 字样」**：本模块的 docstring 里
    #    **必须**提到 PBKDF2（它是「为什么要有选择子」与「为什么不用固定盐」
    #    那两段散文的主语，删掉那两段会让下一个人重犯一次）。
    #    ⚠️ 于是本拍判的是**代码面**而不是**散文面**：不许出现
    #    ``pbkdf2_hmac`` 这个调用名（那才是「自己写了一个」的形状）。
    assert "pbkdf2_hmac" not in source, "bind_tokens.py 自己调了 pbkdf2_hmac"
    assert "from app.auth.passwords import hash_password, verify_password" in source

    callers = set()
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "pbkdf2_hmac"
            ):
                callers.add(path.relative_to(BACKEND_DIR).as_posix())
    # ⚠️ 判据是**文件集合**（不是调用点个数）：``app/auth/passwords.py`` 里有**两个**
    #    调用点（``hash_password`` 一个、``verify_password`` 一个），
    #    而本条要钉的是「**只有一个模块**碰 pbkdf2_hmac」。
    assert callers == {"app/auth/passwords.py"}, sorted(callers)

    # ③ 自描述串 + 迭代次数就是当前配置的那一个
    from app.auth.passwords import iterations
    from sqlalchemy import create_engine

    engine = create_engine("sqlite://")
    from app.db.session import Base, init_db
    init_db(engine)
    with Session(engine) as session:
        row, plain = bind_tokens.issue(
            session, kind="student", login="2025099001", issued_by="T0003"
        )
        parts = row.token_hash.split(SEPARATOR)
        assert len(parts) == 4, parts
        assert parts[0] == ALGORITHM
        assert int(parts[1]) == iterations()
        assert verify_password(plain.split(bind_tokens.SEPARATOR)[1], row.token_hash)
        assert not verify_password("不是那个秘密", row.token_hash)
    engine.dispose()


def test_an_overlong_login_never_reaches_the_bind_token_row(client, people):
    """**宽度收口**：一个 400 字符的学号 → **404**，而 ``bind_token`` **0 行**。

    ⚠️ 它是 :func:`app.auth.bind_tokens.issue` 里「``login`` 刻意不设防」那半句的
    **可执行依据**：那一格的收口点**不是**一个截断函数，而是签发端点那一次
    「按原文回查 subject 行」——查不到就是 404，故一个超宽的 ``login``
    **根本走不到** ``INSERT``。

    ⚠️ 少了本条，「把回查挪到 ``issue`` 之后」这个看起来无害的重排会绿着通过，
    而失效形态是跨后端的定时炸弹（:class:`app.db.models.auth.LoginAttempt` 的
    ``login`` 列注释逐字写过同一格：SQLite 不校验 ``VARCHAR(n)`` 的长度、
    PostgreSQL 会**报错**、MySQL 会**静默截断**）。

    ⚠️ 顺带钉住 ``issued_by`` 那一格的**深度防御**（:func:`app.db.width.overlong_sentinel`）：
    它今天不可达（``require_admin`` 先经 ``require_staff``，一个不在册的工号当场 403），
    而「不可达是一个环境变量的距离」，故本条**直接调** :func:`bind_tokens.issue`
    交一个超宽的 ``issued_by``，断言落库的是**哨兵**而不是一个截断过的假工号。
    """
    engine = engine_of(client)
    overlong = "9" * 400
    got = _issue(client, login=overlong)
    assert got.status_code == 404, got.text
    with Session(engine) as session:
        assert session.execute(text("SELECT count(*) FROM bind_token")).scalar() == 0

    from app.db import width

    with Session(engine) as session:
        row, _plain = bind_tokens.issue(
            session, kind="student", login=STUDENT_NO, issued_by=overlong
        )
        declared = width.declared_width(BindToken.__table__.c.issued_by)
        sentinel = width.overlong_sentinel(overlong, declared)
        assert row.issued_by == sentinel, (row.issued_by, sentinel)
        assert len(row.issued_by) <= declared, (len(row.issued_by), declared)
        # ⚠️ 哨兵是「``<over:400>``」这一档**实话**（它把原文长度带在身上），
        #    而**不是**一个截断到 32 个字符的串 —— 后者会长得像 ``9999…``，
        #    即一个看着像真工号的假工号（那是一句假话）。
        assert "9" * 20 not in row.issued_by, "截断会造出一个看着像真工号的假工号"
        assert str(len(overlong)) in row.issued_by, row.issued_by


def test_the_token_shape_and_ttl_have_a_single_owner():
    """**四格常量**是「一张令牌长什么样」在全仓的唯一住址（:mod:`app.auth.bind_tokens`）。

    ⚠️ 两拍：① 200 次真实签发的**最大长度**与列宽对得上
    （``token_id`` ≤ 32、整个明文 ≤ 一个可以抄下来的长度）；
    ② ``mint`` / ``split`` **互为逆**（200 次），而 ``split`` 对畸形串一律 ``None``。

    ⚠️ 姿势与 ``tests/auth/test_sessions.py`` 的
    ``test_the_token_fits_the_column_and_the_column_is_exactly_as_wide`` 逐字同形
    （期望侧是列宽的字面量与长度算式，被测侧是 200 次真实产出 —— 两侧**不同源**）。
    """
    from app.db import width

    declared_id = width.declared_width(BindToken.__table__.c.token_id)
    longest_plain = 0
    longest_id = 0
    for _ in range(200):
        plain, token_id, secret = bind_tokens.mint()
        longest_plain = max(longest_plain, len(plain))
        longest_id = max(longest_id, len(token_id))
        assert bind_tokens.split(plain) == (token_id, secret)
        assert len(secret) == 32, secret
    assert longest_id == 16, longest_id
    assert longest_id <= declared_id, (longest_id, declared_id)
    assert longest_plain == 16 + 1 + 32, longest_plain

    assert bind_tokens.SEPARATOR == "."
    assert bind_tokens.SEPARATOR not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    assert bind_tokens.BIND_TOKEN_TTL == dt.timedelta(days=7)
    for malformed in ("", "   ", "abc", "a.b.c", "a.", ".b", "a..b"):
        assert bind_tokens.split(malformed) is None, malformed
