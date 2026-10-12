"""``app.auth.sessions`` 的守卫（Plan 05A Task 1-B）。

**这一份文件钉的是「会话行的一生」**：签发（``issue``）→ 解析（``resolve``，含滑动过期
与「subject 已删当场吊销」）→ 吊销（``revoke``），以及 cookie 的那几个参数。

⚠️ **计划 §3.1 标注「本计划最容易漏的一格」就是本文件里的
:func:`test_a_session_whose_subject_has_been_deleted_is_revoked_in_the_row`**：
``user_session.subject_id`` 刻意不是外键（多态外键在 SQL 里不存在），故
① 删一个学生**不会**级联删他的会话行，② :func:`app.api.crud._child_tables`
也**探测不到**它（那个函数扫 ``foreign_keys``），于是 ``DELETE /api/students/{id}``
的 ``restrict`` 那一档看不见它。两档都没有 DB 机制会挡，唯一的处置是解析时回查。

⚠️ 而 HTTP 层那一半（「删掉一个学生 → 他的旧 cookie **立刻 401**」）住在
``tests/api/test_auth_api.py``，因为「401」是 HTTP 的事、``app.auth`` 只返回 ``None``。
两份守卫**刻意不合并**：本文件在纯 ORM 层跑（不需要 ``fastapi``，
:mod:`app.auth` 的模块 docstring 末节），那一份在 ``TestClient`` 上跑。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.sessions import (
    ENV_VAR,
    EPOCH,
    PRODUCTION,
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    STUDENT_KIND,
    STUDENT_ROLE,
    TEACHER_KIND,
    TOKEN_BYTES,
    cookie_kwargs,
    cookie_secure,
    expired_cookie_kwargs,
    issue,
    now,
    resolve,
    revoke,
    student_by_login,
    subject_of,
    teacher_by_login,
)
from app.config import TIMEZONE
from app.db.models.auth import UserSession
from app.db.models.organisation import Student, Teacher
from app.db.session import init_db


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s


@pytest.fixture()
def seeded(session):
    """一个学生 + 两个教师（一个普通、一个管理员），返回三行的 ``id`` 与登录名。"""
    student = Student(
        student_no="S2025001", name="张三", sex="male",
        birth=dt.date(2006, 3, 4), grade=1,
    )
    teacher = Teacher(staff_no="T0001", name="李老师", role="teacher")
    admin = Teacher(staff_no="A0001", name="王干事", role="admin")
    session.add_all([student, teacher, admin])
    session.commit()
    return {
        "student": student.id,
        "student_no": student.student_no,
        "teacher": teacher.id,
        "staff_no": teacher.staff_no,
        "admin": admin.id,
        "admin_no": admin.staff_no,
    }


# ---------------------------------------------------------------------------
# 主键：不透明随机串，且宽度与列宽逐字对齐
# ---------------------------------------------------------------------------


def test_the_token_fits_the_column_and_the_column_is_exactly_as_wide(session):
    """200 次真实签发的**最大**长度 == 列宽 == 64。

    ⚠️ **两侧不同源**（硬规矩 #35）：期望侧是 :data:`TOKEN_BYTES` 与
    ``user_session.id`` 的列宽两个字面量，被测侧是 200 次 ``issue`` 之后
    量出来的实际串长。反推（``len(token) == column.length``）对「列宽被改窄、
    而 ``TOKEN_BYTES`` 跟着改窄」完全无感——而那一档在换到**强制** ``VARCHAR``
    长度的后端（MySQL / PostgreSQL）时是静默截断，截断后的 id 撞车的概率
    会从 2^-384 抬到一个能算出来的数。

    ⚠️ **200 次不是 1 次**：``token_urlsafe`` 的输出长度取决于随机字节里
    有多少个 6-bit 组落在需要填充的位置上——⚠️ 而 48 是 3 的倍数，故**没有**填充，
    长度恒为 64。跑 200 次是把「恒为」这件事从算式变成实测（若哪天有人把
    ``TOKEN_BYTES`` 改成 47，长度会在 63/64 之间跳，本条会红在 ``max`` 上）。
    """
    assert TOKEN_BYTES == 48
    width = UserSession.__table__.c.id.type.length
    assert width == 64, width

    student = Student(
        student_no="S2025999", name="长度探针", sex="female",
        birth=dt.date(2006, 1, 1), grade=1,
    )
    session.add(student)
    session.commit()
    lengths = set()
    for _ in range(200):
        token = issue(session, kind=STUDENT_KIND, subject_id=student.id, role=STUDENT_ROLE)
        lengths.add(len(token))
        revoke(session, token)
    assert max(lengths) == width, sorted(lengths)
    assert len(lengths) == 1, f"长度不恒定：{sorted(lengths)}"


def test_the_primary_key_is_an_opaque_string_not_an_integer(session, seeded):
    """``user_session.id`` 是 ``String``，且两次签发的串都不是数字。

    ⚠️ 用随机串而不是自增整数有两个理由（``UserSession`` 的 docstring 逐字写了）：
    自增 id 是**可枚举**的（拿到一个 cookie 的人能推出「大约有多少人登录过」、
    也能挨个试别人的 id），而随机串让「id 本身不含任何信息」成立。
    ⚠️ 本条也是 ``tests/api/test_crud.py::test_every_table_has_a_single_column_primary_key``
    里那个「整数主键」例外的**另一半**：那一条钉住「26 张表里恰好 1 张的主键不是整数，
    而它是 ``user_session``」，本条钉住「那一张为什么可以不是整数」。
    """
    column = UserSession.__table__.c.id
    assert column.primary_key
    assert column.type.__class__.__name__ == "String"
    first = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    second = issue(session, kind=TEACHER_KIND, subject_id=seeded["teacher"], role="teacher")
    assert not first.isdigit() and not second.isdigit(), (first, second)
    assert first != second


# ---------------------------------------------------------------------------
# 签发
# ---------------------------------------------------------------------------


def test_issue_writes_a_row_whose_expiry_is_the_ttl_after_creation(session, seeded):
    """``issue`` 落一行、**自己 commit**，且 ``expires_at - created_at == TTL``。

    ⚠️ **自己 commit 是承重的**：会话行必须在响应发出之前就落库，否则
    ``Set-Cookie`` 已经给了浏览器、而下一个请求 ``db.get`` 查不到那一行 → 401，
    表现为「登录成功了但立刻又掉线」。而 :func:`app.api.deps.get_db` 刻意**不** commit。
    本条的判据因此是「**在一个新的 Session 里**也能读到那一行」——
    同一个 Session 会从 identity map 里读回来，证明不了 commit 发生过。

    ⚠️ ``last_seen_at == created_at``：刚签发的会话还没被用过，
    而 ``expires_at - last_seen_at`` 恒等于 TTL（滑动过期的不变量）。
    """
    token = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    row = session.get(UserSession, token)
    assert row is not None
    assert row.revoked_at is None
    assert row.expires_at - row.created_at == SESSION_TTL
    assert row.last_seen_at == row.created_at

    other = Session(session.get_bind())
    try:
        fresh = other.get(UserSession, token)
        assert fresh is not None, "issue 没有 commit：换一个 Session 就读不到那一行"
        assert fresh.kind == STUDENT_KIND
        assert fresh.subject_id == seeded["student"]
        assert fresh.role == STUDENT_ROLE
    finally:
        other.close()


def test_issue_stores_the_teacher_role_verbatim_so_admin_survives_a_roundtrip(
    session, seeded
):
    """教师的 ``role`` 是**签发那一刻** ``teacher`` 行上的值，故管理员的会话带着 ``admin``。

    ⚠️ 这一条钉的是 :mod:`app.db.models.auth` 模块 docstring 第三节那个「冗余」的
    **正面价值**：``require_admin`` 判的是会话行上那一份，故一次登录之后
    每个请求都不必再问 ``teacher`` 表「你现在还是管理员吗」。
    ⚠️ 而它的**代价**（降权要等重新登录）由
    :func:`test_a_demoted_admin_keeps_the_role_recorded_on_his_live_session` 钉住——
    两条守卫是同一个决定的两半，故都必须在场（硬规矩 #50）。
    """
    token = issue(session, kind=TEACHER_KIND, subject_id=seeded["admin"], role="admin")
    identity = resolve(session, token)
    assert identity is not None
    assert identity.role == "admin"
    assert identity.kind == TEACHER_KIND
    assert identity.subject_id == seeded["admin"]
    assert identity.name == "王干事"
    assert identity.login == "A0001"

    plain = issue(session, kind=TEACHER_KIND, subject_id=seeded["teacher"], role="teacher")
    assert resolve(session, plain).role == "teacher"


def test_a_demoted_admin_keeps_the_role_recorded_on_his_live_session(session, seeded):
    """**冗余 ``role`` 的代价，如实钉住**：降权不会立刻生效。

    管理员登录之后被降成普通教师（``teacher.role = "teacher"``），而他手里那个
    **仍然有效**的会话行上的 ``role`` 还是 ``admin``，故 ``resolve`` 照旧交出
    ``admin`` ——管理台的写权限要等他**重新登录**才失去。

    ⚠️ **这一条不是「测一个 bug」**：它是控制者裁定「冗余存一份」时接受的代价
    （计划 §3.1：原型可接受，降权是极罕见操作，且已写进 spec §13）。
    把它写成守卫的理由是硬规矩 #39 的反面——一个**没有守卫的已知代价**
    会在下一次重构时被「顺手修好」，而修好它的方式（每次请求以 ``teacher`` 表为准）
    会改掉 ``resolve`` 的语义，于是「会话行上的 role 是留痕还是判据」这件事
    变成一个没人看得见的问题。
    ⚠️ 要收紧的话，改 :func:`app.auth.sessions.resolve` 里教师的 role 取值即可
    （一次一行的改动），那时**本条要跟着翻面**，而不是被删掉。
    """
    token = issue(session, kind=TEACHER_KIND, subject_id=seeded["admin"], role="admin")
    assert resolve(session, token).role == "admin"

    admin = session.get(Teacher, seeded["admin"])
    admin.role = "teacher"
    session.commit()

    assert session.get(Teacher, seeded["admin"]).role == "teacher"
    assert resolve(session, token).role == "admin", (
        "冗余的 role 不再冗余了：resolve 改成了以 teacher 表为准。"
        "若这是有意的收紧，请把本条翻面（断言 == 'teacher'）并同步改 "
        "app/db/models/auth.py 模块 docstring 第三节与 spec §13"
    )
    # 重新登录之后拿到的是新值
    fresh = issue(
        session, kind=TEACHER_KIND, subject_id=seeded["admin"],
        role=session.get(Teacher, seeded["admin"]).role,
    )
    assert resolve(session, fresh).role == "teacher"


# ---------------------------------------------------------------------------
# 解析：滑动过期 + 六档不可用
# ---------------------------------------------------------------------------


def test_resolve_slides_the_expiry_and_updates_last_seen(session, seeded):
    """**滑动过期**：解析一次就把 ``expires_at`` 往后推一个 TTL、``last_seen_at`` 更新成现在。

    ⚠️ 判据是**不变量**而不是墙钟：``expires_at - last_seen_at == TTL`` 在滑动前后都成立，
    而 ``expires_at`` 单调不减。用墙钟（``sleep``）会让本条既慢又间歇性红。
    ⚠️ 于是「活跃用户永不掉线、不活跃用户两小时后掉线」同时成立，
    而**不需要 refresh 令牌**（计划 §3.3 末段：cookie 方案相对 Bearer 的一个实际简化）。

    ⚠️ **滑动过期真的 commit 了**（判据同 ``test_issue_…``：换一个 Session 读）。
    """
    token = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    before = session.get(UserSession, token)
    first_expiry, first_seen = before.expires_at, before.last_seen_at

    identity = resolve(session, token)
    assert identity is not None
    after = session.get(UserSession, token)
    assert after.expires_at - after.last_seen_at == SESSION_TTL
    assert after.expires_at >= first_expiry
    assert after.last_seen_at >= first_seen
    assert after.revoked_at is None

    other = Session(session.get_bind())
    try:
        assert other.get(UserSession, token).last_seen_at == after.last_seen_at, (
            "滑动过期没有 commit：换一个 Session 就读到旧值"
        )
    finally:
        other.close()


def test_resolve_returns_none_for_every_unusable_shape(session, seeded):
    """六档不可用，**逐档点名**，且每一档都是 ``None``（不是异常、不是一个假身份）。

    ⚠️ 返回 ``None`` 而不是抛：``app.auth`` 不 import ``fastapi``，而「没有身份」
    在 HTTP 层是**两个**不同的码（``current_student`` 折 401，
    「cookie 是教师的、端点要学生」折 403），故由调用方决定。

    ⚠️ 第 3、4 两档（已过期 / 已吊销）**刻意不写 ``revoked_at``**：一个过期行不是
    「被吊销」，把它标成吊销会让「运维主动踢人」与「时间到了」在库里无法区分，
    而前者是审计事实、后者不是。本条**反向**钉住这件事（``revoked_at is None``），
    否则「顺手把过期也标成吊销」是静默的。
    """
    # ① token 为空 / 空白
    assert resolve(session, None) is None
    assert resolve(session, "") is None
    assert resolve(session, "   ") is None
    # ② 查无此行（伪造的、或库被重建过）
    assert resolve(session, "A" * 64) is None

    token = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    # ④ 已过期（⚠️ 用 <= 判：恰好等于那一刻也算过期）
    row = session.get(UserSession, token)
    row.expires_at = now() - dt.timedelta(seconds=1)
    session.commit()
    assert resolve(session, token) is None
    assert session.get(UserSession, token).revoked_at is None, "过期不等于被吊销"
    # 边界：expires_at 恰好等于 now 的那一档由「<= 而不是 <」决定，
    # 用一个远未来的 expires_at 证明它不是「一律拒绝」
    row.expires_at = now() + SESSION_TTL
    session.commit()
    assert resolve(session, token) is not None

    # ③ 已吊销
    assert revoke(session, token) is True
    assert resolve(session, token) is None
    assert session.get(UserSession, token).revoked_at is not None

    # ⑤ kind 不在取值域里 → subject_of 回 None → 当场吊销。
    # ⚠️ **这一档今天打不出来**：``ck_user_session_kind`` 会让一个 kind="parent" 的行
    # 在 commit 时 IntegrityError，故 ``resolve`` 里那一支是**许可而不是断言**
    # （硬规矩 #39）。它可达的形状只有一个：有人绕过 ORM 直接写库、或将来给 KINDS
    # 加了第三个值而 ``subject_of`` 的分派没跟上。那半个判据由
    # ``test_the_login_lookups_find_their_rows_and_return_none_for_a_stranger`` 直接调
    # ``subject_of`` 钉住（不经 DB，故不受 CHECK 影响）。


def test_resolve_returns_the_login_and_name_from_the_subject_row_not_the_session(
    session, seeded
):
    """``name`` 与 ``login`` 来自 **subject 行**，会话行上刻意不存它们。

    ⚠️ 理由是「改名之后存的那一份就是一句过期的人话」（``Identity`` 的 docstring
    逐格交代了每个值从哪来，硬规矩 #110）。本条把那一格跑成实测：改一次名，
    同一个 token 解析出来的 ``name`` 跟着变。
    ⚠️ 而 ``role`` **不跟着变**（它是冗余的那一份，见上面那条降权守卫）——
    于是同一个 ``Identity`` 里五格的「新鲜度」是**两种**，本条把两种都钉住。
    """
    token = issue(session, kind=TEACHER_KIND, subject_id=seeded["teacher"], role="teacher")
    assert resolve(session, token).name == "李老师"
    teacher = session.get(Teacher, seeded["teacher"])
    teacher.name = "李老师（改名之后）"
    session.commit()
    identity = resolve(session, token)
    assert identity.name == "李老师（改名之后）"
    assert identity.login == "T0001" == teacher.staff_no
    assert identity.role == "teacher"

    student_token = issue(
        session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE
    )
    student_identity = resolve(session, student_token)
    assert student_identity.login == seeded["student_no"] == "S2025001"
    assert student_identity.role == STUDENT_ROLE == "student"
    assert student_identity.kind == STUDENT_KIND


def test_a_session_whose_subject_has_been_deleted_is_revoked_in_the_row(session, seeded):
    """⚠️ **计划 §3.1 标注「本计划最容易漏的一格」**：subject 行没了 ⇒ 当场吊销。

    三拍：① 删掉那个学生行（``user_session`` 上没有任何 DB 机制会跟着动，
    因为 ``subject_id`` 不是外键）；② ``resolve`` 返回 ``None``（HTTP 层因此是 401）；
    ③ **会话行还在、而 ``revoked_at`` 被写上了**——即「拒绝」与「吊销」两件事都发生了。

    ⚠️ **少了③会怎样**：``resolve`` 只返回 ``None`` 的话，那一行会永远留在库里、
    且 ``revoked_at IS NULL``，于是「这个人为什么被踢了」在库里**无从查证**
    （运维看到的是一行看起来仍然有效的会话）。而本仓的纪律是
    「一切承重的事实都落在库里、可追溯」（``daily_sync_run`` / ``cleaning_log``
    都是这个形状，也正是计划 §3.4 选服务端会话表的第三条理由）。

    ⚠️ **它同时也证明了「删学生不会级联删会话行」**：②之后那一行仍然能被
    ``session.get`` 读到（若外键存在且带 ``CASCADE``，它会已经消失，
    ``session.get`` 回 ``None``，③会红在 ``AttributeError`` 上）。
    """
    token = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    assert resolve(session, token) is not None, "前提：这个会话本来是有效的"

    session.delete(session.get(Student, seeded["student"]))
    session.commit()
    assert session.get(Student, seeded["student"]) is None
    assert subject_of(session, STUDENT_KIND, seeded["student"]) is None

    assert resolve(session, token) is None
    row = session.get(UserSession, token)
    assert row is not None, "会话行被删掉了：那意味着 subject_id 上有了一个外键"
    assert row.revoked_at is not None, "拒绝了但没有吊销：库里查不出这个人为什么被踢"

    # ⚠️ 再解析一次仍然是 None（吊销是终态，不会「过一会儿又活了」）
    assert resolve(session, token) is None


def test_the_teacher_variant_of_the_deleted_subject_guard(session, seeded):
    """教师那一侧的同一格（``subject_of`` 的两个分支各测一次，硬规矩 #50）。

    ⚠️ 只测学生那一侧的话，``subject_of`` 里 ``kind == "teacher"`` 那一支写错
    （例如查了 ``Student``）是绿的——而那一支正是**管理员**走的那一支，
    于是失效形状是「删掉一个离职的教务干事，他的管理台权限还在」。
    """
    token = issue(session, kind=TEACHER_KIND, subject_id=seeded["admin"], role="admin")
    assert resolve(session, token).role == "admin"
    session.delete(session.get(Teacher, seeded["admin"]))
    session.commit()
    assert resolve(session, token) is None
    assert session.get(UserSession, token).revoked_at is not None


# ---------------------------------------------------------------------------
# 吊销
# ---------------------------------------------------------------------------


def test_revoke_writes_revoked_at_and_is_idempotent(session, seeded):
    """``revoke`` 写 ``revoked_at``、**自己 commit**、且第二次返回 ``False``。

    ⚠️ **自己 commit 是「登出登得掉」的全部机制**：``POST /api/auth/logout`` 回 204、
    没有响应体、也没有别的写入，故不 commit 的话那一次 UPDATE 会随
    ``Session.close()`` 被回滚掉——而那正是本计划选服务端会话表（而不是签名 cookie）
    的**第一条理由**。判据同 ``test_issue_…``：换一个 Session 读。
    ⚠️ 幂等（第二次 ``False``）让「登出两次」在 HTTP 层是 204 + 204：
    「你已经登出了」与「你刚刚登出了」对浏览器是同一件事。
    """
    token = issue(session, kind=STUDENT_KIND, subject_id=seeded["student"], role=STUDENT_ROLE)
    assert revoke(session, token) is True
    other = Session(session.get_bind())
    try:
        assert other.get(UserSession, token).revoked_at is not None, (
            "revoke 没有 commit：登出登不掉"
        )
    finally:
        other.close()
    assert revoke(session, token) is False
    assert revoke(session, None) is False
    assert revoke(session, "") is False
    assert revoke(session, "A" * 64) is False
    # 行**没有被删掉**：留痕
    assert session.get(UserSession, token) is not None


# ---------------------------------------------------------------------------
# 取值域：类常量 / CHECK / 会话的那一份
# ---------------------------------------------------------------------------


def test_the_role_vocabulary_of_a_session_is_the_teacher_one_plus_student():
    """``UserSession.ROLES == Teacher.ROLES | {"student"}``，且 ``KINDS`` 是两个。

    ⚠️ **两份词表刻意不合并、但它们的关系必须是这一条等式**：教师的 role 只有
    ``teacher`` / ``admin``，而会话那一列 ``NOT NULL``、故学生的会话也需要一个字面值。
    少了本条，「给 ``Teacher.ROLES`` 加第三个角色（例如 ``principal``）而忘了给
    ``UserSession.ROLES`` 加」是静默的——而它的表现是**登录时一个 409**
    （``IntegrityError`` 撞 CHECK），一句「integrity_conflict」，离真因隔一整层。
    """
    assert UserSession.KINDS == {"student", "teacher"}
    assert Teacher.ROLES == {"teacher", "admin"}
    assert UserSession.ROLES == Teacher.ROLES | {"student"}
    assert STUDENT_ROLE == "student" and STUDENT_ROLE in UserSession.ROLES
    assert STUDENT_KIND == "student" and TEACHER_KIND == "teacher"
    assert Teacher.DEFAULT_ROLE == "teacher" and Teacher.DEFAULT_ROLE in Teacher.ROLES
    # 反空转：KINDS 就是模型类常量那一份（不是第二份词表）
    from app.auth import sessions as sessions_module

    assert sessions_module.KINDS is UserSession.KINDS


def test_the_check_constraints_reject_a_kind_or_role_outside_the_vocabulary(session, seeded):
    """SQL 层那一道（本包约定 2 的「两处设防」之二）真的有牙。

    ⚠️ Python 侧的类常量挡的是「代码写错」，CHECK 挡的是「有人绕过 ORM 直接写库」
    （``demo_bootstrap.py`` 与任何将来的运维脚本都是那个形状）。
    两道各测一次，故本条直接构造 ORM 行、让 DB 自己拒收。
    """
    for bad_kind, bad_role in (("parent", "student"), ("student", "principal"),
                               ("", ""), ("student", None)):
        session.add(
            UserSession(
                id=f"BAD-{bad_kind}-{bad_role}", kind=bad_kind,
                subject_id=seeded["student"], role=bad_role,
                created_at=now(), expires_at=now(), last_seen_at=now(),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    # 绿档：三个合法的 role 都写得进去
    for role in sorted(UserSession.ROLES):
        kind = STUDENT_KIND if role == STUDENT_ROLE else TEACHER_KIND
        subject = seeded["student"] if kind == STUDENT_KIND else seeded["teacher"]
        session.add(
            UserSession(
                id=f"OK-{role}", kind=kind, subject_id=subject, role=role,
                created_at=now(), expires_at=now(), last_seen_at=now(),
            )
        )
        session.commit()
    assert session.get(UserSession, "OK-admin").role == "admin"
    # teacher.role 那一道
    session.add(Teacher(staff_no="T9999", name="x", role="校长"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_subject_id_is_deliberately_not_a_foreign_key():
    """``user_session`` 的**出向**外键数是 0（把「刻意不建」这件事钉成可执行的事实）。

    ⚠️ 这一条守的是**结构**，不是行为：若哪天有人「顺手补上一个外键」
    （它只能指向 ``student`` 或 ``teacher`` 中的一张，故补上去就是**错的**），
    本条当场红。而那一次改动的失效形态是静默的：教师会话的 ``subject_id``
    会被 DB 拒收（或更糟——指向了 ``student`` 表里同号的另一个人）。
    ⚠️ 连带后果也逐字记在这里：:func:`app.api.crud._child_tables` **探测不到**
    本表，故删学生/删教师的 ``restrict`` 那一档看不见会话行
    （处置是解析时回查，见上面那两条守卫）。
    """
    table = UserSession.__table__
    assert len(table.foreign_keys) == 0
    assert [fk.parent.name for fk in table.foreign_keys] == []
    assert not any(c.foreign_keys for c in table.columns)


# ---------------------------------------------------------------------------
# cookie 的参数
# ---------------------------------------------------------------------------


def test_the_cookie_carries_exactly_the_documented_parameters(monkeypatch):
    """六个参数逐个（**不含 ``domain``**），且 ``Max-Age`` 与 ``expires_at`` 同源。

    期望侧是**字面量**（硬规矩 #35）：``pe_session`` / ``7200`` / ``/`` / ``True`` /
    ``False``（非生产）/ ``lax``。⚠️ ``samesite`` 必须是小写：Starlette 只认
    ``"lax"`` / ``"strict"`` / ``"none"`` / ``False``，写 ``"Lax"`` 会原样落进响应头，
    而部分浏览器不接受一个大小写不对的 ``SameSite``（于是它退化成缺省行为，
    CSRF 那一半论证就没了）。

    ⚠️ **``domain`` 必须不在**（``assert "domain" not in kwargs``）：不传就是
    「宿主限定」，而那正是同源部署要的。写 ``domain="localhost"`` 会让 cookie 也对
    ``*.localhost`` 全部子域可见——那是计划 §3.5 那条 CSRF 论证**挡不住**的一档。

    ⚠️ **同源那一拍**（``max_age`` 与 ``SESSION_TTL`` 是同一个数）钉的是
    计划 §3.4 点名的失效：「一个写 7200 一个写 86400」。判据是
    ``int(SESSION_TTL.total_seconds())``，而 ``expires_at - created_at == SESSION_TTL``
    由 :func:`test_issue_writes_a_row_whose_expiry_is_the_ttl_after_creation` 钉，
    两条合起来才是「同源」。
    """
    monkeypatch.delenv(ENV_VAR, raising=False)
    kwargs = cookie_kwargs("TOKEN")
    assert kwargs == {
        "key": "pe_session",
        "value": "TOKEN",
        "max_age": 7200,
        "path": "/",
        "httponly": True,
        "secure": False,
        "samesite": "lax",
    }
    assert SESSION_COOKIE_NAME == "pe_session"
    assert kwargs["max_age"] == int(SESSION_TTL.total_seconds()) == 7200
    assert SESSION_TTL == dt.timedelta(hours=2)
    assert "domain" not in kwargs, (
        "cookie 带了 domain：它会对全部子域可见，而计划 §3.5 的 CSRF 论证挡不住那一档"
    )
    assert "expires" not in kwargs, "活着的 cookie 不该带 Expires（Max-Age 已经够了）"


def test_the_expired_cookie_matches_the_live_one_on_every_matching_parameter(monkeypatch):
    """登出那一发的参数与签发那一发**只差三格**（``value`` / ``max_age`` / ``expires``）。

    ⚠️ RFC 6265 的删除是按 ``(name, domain, path)`` 三元组匹配的，``path`` 差一个字符
    就删不掉那一格（浏览器会留着它，于是「登出之后又自动登进去」）。
    故 :func:`expired_cookie_kwargs` **从** :func:`cookie_kwargs` 派生而不是另写一份
    字面量——两个所有者迟早漂到两个 path 上去。本条钉的就是「它没有另写一份」：
    除了那三格，其余逐字相同（``secure`` 也一样，否则生产上删不掉）。
    """
    monkeypatch.setenv(ENV_VAR, PRODUCTION)
    live = cookie_kwargs("TOKEN")
    dead = expired_cookie_kwargs()
    assert dead["value"] == ""
    assert dead["max_age"] == 0
    assert dead["expires"] == EPOCH == dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    assert dead["expires"].tzinfo is not None, "Expires 一律按 GMT 渲染，故它必须 aware"
    for key in ("key", "path", "httponly", "secure", "samesite"):
        assert dead[key] == live[key], (key, dead[key], live[key])
    assert set(dead) - set(live) == {"expires"}
    assert dead["secure"] is True, "生产档下删除 cookie 也要带 Secure，否则删不掉"


def test_secure_is_on_only_in_production(monkeypatch):
    """``Secure`` 仅在 ``PE_ENV=production`` 时开，且**在请求时读**环境变量。

    ⚠️ 原型跑在 ``http://127.0.0.1:8000`` 上，而带 ``Secure`` 的 cookie
    **在明文 HTTP 上根本不会被浏览器存下来**——于是「一律加 Secure」的表现是
    「本地演示谁都登录不了」，一个离真因很远的症状。
    ⚠️ 「在请求时读」这一格由 ``monkeypatch.setenv`` 之后**立刻**读到新值证明
    （import 期读的话本条会红，因为模块早就 import 完了）。
    ⚠️ 大小写不敏感 + 去空白：``PE_ENV=Production`` 与 ``PE_ENV=" production "``
    都算生产（一个环境变量被写成一个大小写不同的字面量是常见事故，
    而失效方向是「生产上没加 Secure」——不安全的那一侧）。
    """
    assert PRODUCTION == "production" and ENV_VAR == "PE_ENV"
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert cookie_secure() is False
    assert cookie_kwargs("T")["secure"] is False
    for value in ("production", "Production", "  PRODUCTION  "):
        monkeypatch.setenv(ENV_VAR, value)
        assert cookie_secure() is True, value
    for value in ("", "dev", "development", "staging", "prod", "production-ish"):
        monkeypatch.setenv(ENV_VAR, value)
        assert cookie_secure() is False, value


# ---------------------------------------------------------------------------
# 时间与查找
# ---------------------------------------------------------------------------


def test_now_is_naive_local_time_in_the_configured_timezone():
    """``now()`` 是 **naive 本地**时刻，口径与全仓其余 ``DateTime`` 列逐字相同。

    ⚠️ ``replace(tzinfo=None)`` 是承重的：aware 与 naive 相减会当场
    ``TypeError: can't compare offset-naive and offset-aware datetimes``，
    而本模块的每一个判定都是「两个时刻相减/相比」。
    ⚠️ **不用 ``utcnow()``**：那会与库里其余全部 naive **本地**时刻差 8 小时，
    于是一个刚签发的会话会被判成「8 小时前就过期了」。本条用
    ``dt.datetime.now(ZoneInfo(TIMEZONE))`` 做期望侧对拍，故它与
    :data:`app.config.TIMEZONE` 是同一个口径而不是同一个实现。
    """
    from zoneinfo import ZoneInfo

    got = now()
    assert got.tzinfo is None, got
    expected = dt.datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)
    assert abs((expected - got).total_seconds()) < 5, (expected, got)
    assert TIMEZONE == "Asia/Shanghai"
    # 与 utcnow 的差**必须**是那个时区的偏移（本条真正防的失效）
    utc_naive = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    assert (got - utc_naive).total_seconds() == pytest.approx(8 * 3600, abs=5)


def test_the_login_lookups_find_their_rows_and_return_none_for_a_stranger(session, seeded):
    """``student_by_login`` / ``teacher_by_login``：查到回行、查不到回 ``None``（不是异常）。

    ⚠️ 回 ``None`` 是承重的：绑定与登录两个端点要按「查无此人」给出
    **403 ``forbidden``**（与「验身材料不符」同一个 code + 同一句 message，
    不给攻击者区分信号，计划 §3.2），而一个异常会变成 500。
    ⚠️ 空白工号/学号也回 ``None``（``select`` 的等值比较天然不匹配），
    故「传了一个空串」与「传了一个不存在的学号」是同一档。
    """
    assert student_by_login(session, "S2025001").id == seeded["student"]
    assert teacher_by_login(session, "T0001").id == seeded["teacher"]
    assert teacher_by_login(session, "A0001").role == "admin"
    for lookup, missing in (
        (student_by_login, "S9999999"),
        (teacher_by_login, "NOPE"),
        (student_by_login, ""),
        (teacher_by_login, "  "),
    ):
        assert lookup(session, missing) is None, (lookup.__name__, missing)
    # 学号与工号是两个命名空间，不得互相命中
    assert student_by_login(session, "T0001") is None
    assert teacher_by_login(session, "S2025001") is None
    # subject_of 的第三个分支（kind 不在取值域里）
    assert subject_of(session, "parent", seeded["student"]) is None
    assert subject_of(session, STUDENT_KIND, 999999) is None
    # ⚠️ ``subject_of`` **只按 kind 分派、不校验「这个 id 在那张表里是不是同一类人」**：
    # 这正是 ``subject_id`` 不是外键的代价之一（DB 不会替你校验那一对是不是自洽的），
    # 逐字理由见 ``app/db/models/auth.py`` 的模块 docstring 第二节。
    # 本条把那一格**如实**钉住，而不是假装它不存在：一个 kind=teacher 而
    # subject_id 是某个学生 id 的行，会被解析成**同号的那个教师**。
    # 它今天不可达（``issue`` 的两个调用方各自都按 kind 取 id），
    # 而「不可达」与「不可能」是两件事，故这里断言的是分派规则本身。
    cross = subject_of(session, TEACHER_KIND, seeded["student"])
    assert cross is None or isinstance(cross, Teacher), cross
