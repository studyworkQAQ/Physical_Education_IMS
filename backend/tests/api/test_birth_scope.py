"""名册 ``birth`` 的**可见面收窄**（Plan 08 Task 5）。

--------------------------------------------------------------------------
本文件钉的是哪一件事
--------------------------------------------------------------------------

``student.birth`` 同时是两件东西：① 学生自助绑定口令的**全部**验身材料之一
（``POST /api/auth/students/bind`` 逐字判 ``student.birth != payload.birth``）与
② 对**全校任何在册教职**可读的一列（``GET /api/students`` 的 ``read_scope`` 是
``"staff"`` = 行级不收窄）。两格叠在一起就是 spec §1.2 第 4 条那一句
「验身材料等于零」：一个已登录的普通教师读一次名册，就能替任何**还没绑定**的
账号设一个自己知道的口令，然后登录成他。

Plan 08 Task 4 给了一条**更强的替代路**（一次性绑定令牌，那条路一个字都不读
``birth``），但自助绑定那一档**没删**、开关 ``PE_ALLOW_SELF_BIND`` 缺省仍开
⇒ 本件是另一半：**把 ``birth`` 那一格对普通教师变形**。

--------------------------------------------------------------------------
⚠️⚠️ 两根轴：行级可见性 vs 值级变形（不要把它们混成一根）
--------------------------------------------------------------------------

``read_scope`` 的五档收的是「**哪几行**对谁可见」（spec §13.4.7）；本件收的是
「一**行里的那一格**对谁给完整值」。``students`` 那一行今天**同时**是
``READ_SCOPE_STAFF``（全校的行对任何教职照旧可见）**与** ``redact=(Redaction(
"birth", …),)``（那些行里 ``birth`` 那一格变形）——合并成一个枚举表达不开。

--------------------------------------------------------------------------
⚠️⚠️ 三档身份的口径（**逐格实测**，本文件每条都有对应的拍）
--------------------------------------------------------------------------

======================  ==========================================  ==========
身份                     ``GET /api/students{,/{id}}`` 的 ``birth``    证据
======================  ==========================================  ==========
匿名                     **401**（到不了变形这一步）                  既有守卫
学生会话                 请求头 **401** / cookie **403**（同上）      本文件 ③
普通教师 ``role=teacher``  **掩码**（两档通道都掩）                    本文件 ①⑨
管理员 ``role=admin``      **完整值**（刻意不掩）                      本文件 ②⑥
======================  ==========================================  ==========

⚠️ **「管理员不掩」是一条裁定、不是一次疏忽**，两条理由（逐字口径住
:data:`app.api.crud.REDACT_ADMIN_ONLY` 与 spec §13.27）：
① 管理员本来就是 omnipotent 的那一档（越过任教范围闸门、独占管理台 26 个写入
   操作），收窄他换不到任何安全；
② 管理台的 student 资源是**可写的 CRUD**，而 ``ResourceDetail.vue`` /
   ``ResourceList.vue`` 的编辑表单把响应体那一行**预填**进 ``<input type="date">``
   —— 掩码若被写回库就是一次数据损坏。
⚠️ 而 ② 那一步实测是**响亮**的（:func:`test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`
的两段：掩码 PATCH → **422** 且库里那一行**逐字未变**；而一个**合法**日期形状的
掩码 PATCH → **200** 且**静默**改掉库里那一格）⇒ 掩码的字面形状是承重的。

--------------------------------------------------------------------------
⚠️⚠️ 顶回：派单点名的两条路在本仓**不存在**，而「学生读自己能拿到完整值」不成立
--------------------------------------------------------------------------

派单 §1 把 ``GET /api/teacher/roster`` 与 ``/api/export/...`` 点成「本件的命门」
（「这两条不掩，本件就等于没做」）。⚠️ **实测：这两个端点在本仓一个都不存在**
（:func:`test_there_is_no_export_or_roster_route_and_the_csv_contract_never_crosses_http`
把那一格钉住）。名册只有一条 HTTP 路：``/api/students`` 那个 CRUD 资源的
list + read-one 两个端点。⚠️ 派单说的「导出侧逐资源列白名单」在本仓对应的是
:data:`app.adapters.base.STUDENT_COLUMNS` —— 那是**入站**的模拟数据源
（``students.csv``）列序契约，由 ``app/adapters/mock_lepao.py`` 读、由
``app/seed/generate.py`` 的 ``write_csv`` 离线写，**一个字节都不经 HTTP**、
也不跨任何鉴权边界。

⚠️ 派单的守卫 ②「学生读自己**能**拿到完整值」同样**不成立**：``students`` 那一行
自 Plan 05A Task 5 起是 ``read_scope="staff"``，一个学生会话打
``GET /api/students/{自己的 id}`` 实测 **401**（请求头通道）/ **403**（cookie 通道）
—— 它**根本到不了**值级变形这一步；而学生自己的窄端点
``GET /api/students/{id}/home`` 的响应体里**没有 ``birth`` 这一格**
（:class:`app.api.schemas.dashboard.StudentHomeRead` 逐字不含它）。
⇒ 今天**没有任何一条路**把一个学生自己的出生日期发给他自己（他绑定口令时
手上那一格是**他自己知道的**，不是从服务器上读来的）。
:func:`test_a_student_session_is_rejected_by_the_row_gate_before_any_redaction`
钉的是这个**真**口径，而不是派单那一句。

⚠️ 而派单变异 ⑦「把『学生读自己』那一档也掩上（过度收窄也是缺陷，必须红）」
因此**没有对应的可变异面**（那一档到不了变形）。本文件用**同方向的另一根轴**
替代它：过度收窄 = 把 ``admin`` 从 ``full_for`` 里拿掉，那会让
:func:`test_an_admin_reads_the_full_value_on_both_routes` 与
:func:`test_masked_columns_for_is_the_single_judgement_and_does_not_over_narrow`
两条同时红。

--------------------------------------------------------------------------
⚠️ 反空转与两侧不同源（硬规矩 #50 / #109）
--------------------------------------------------------------------------

* **期望侧一律写字面量**：掩码串、``"admin"`` / ``"teacher"`` / ``"staff"``、
  openapi 里 ``StudentRead.birth`` 那三格，全部写死在本文件里，
  **不从** :data:`app.api.crud.BIRTH_MASK` / :data:`app.api.deps.ADMIN_ROLE` /
  :data:`app.api.crud.READ_SCOPE_STAFF` **读回来跟自己比**。
  ⚠️ 那三个常量仍然被 import，但只用在「构造一个**合成**声明」与
  「证明被测侧读的就是它们」这两件事上（:func:`test_the_mask_literal_has_exactly_one_definition_in_the_production_tree`）。
* **被测侧一律打 HTTP 并解析响应体**（``client.get(...)`` / ``client.patch(...)``），
  或直接查库（``text("SELECT * FROM student …")``）—— 与「响应体里那一格」
  是两个独立的取法。
* **红绿两档同时在场**：教师读到掩码（红档）**与**管理员读到完整值（绿档）
  必须都在，否则「一律掩」与「一律不掩」两个恒常实现各能让半边全绿。
* :func:`test_no_get_route_hands_a_real_birth_to_a_plain_teacher` 那条**全端点扫描**
  带一条显式的反空转断言（至少 8 个端点真的 200，且出现掩码的路恰好是那 2 条），
  否则「一个端点都没打通」与「打通了但一个 birth 都没漏」在颜色上不可分辨。
"""
import ast
import datetime as dt
import json
import pathlib
import re

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.crud import (
    BIRTH_MASK,
    ON_DELETE_RESTRICT,
    READ_SCOPE_STAFF,
    READ_SCOPE_STUDENT_SELF,
    REDACT_ADMIN_ONLY,
    STAFF_READER_STATE_KEY,
    CrudSchemas,
    Redaction,
    StudentOwner,
    build_crud_router,
    masked_columns_for,
    staff_reader_of_request,
)
from app.api.deps import ReaderIdentity
from app.api.routers.catalog import RESOURCES
from app.api.schemas.organisation import StudentCreate, StudentRead, StudentUpdate
from app.db.models.organisation import Semester, Student, Teacher

#: ``backend/``。⚠️ 本文件在 ``backend/tests/api/`` 下，故 ``parents[2]``。
BACKEND = pathlib.Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# ⚠️⚠️ 期望侧字面量（硬规矩 #35 / #109：一个都不从被测模块读回来）
# ---------------------------------------------------------------------------
#: 掩码的字面量。⚠️ 与 :data:`app.api.crud.BIRTH_MASK` **刻意写成两份**：
#: 期望侧抄被测侧的话，「把掩码改成一个合法日期」这类变异就抓不到了。
MASK = "****-**-**"
#: 一个**合法**日期形状的串：它是 :func:`test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`
#: 里的**绿档对照**（证明那一发 422 是「值不是日期」造成的，而不是端点拒绝写入）。
LEGAL_DATE = "2005-01-01"

STUDENT_NO = "2025099001"
OTHER_STUDENT_NO = "2025099002"
#: ⚠️ 两个学生的出生日期**刻意不同**：否则「掩成一个恒定串」那一拍会退化成
#: 「把两个相同的值掩成同一个串」，抓不到「掩码泄漏了值」这一类失效。
BIRTH_ONE = dt.date(2007, 3, 15)
BIRTH_TWO = dt.date(2006, 11, 2)

PLAIN_STAFF_NO = "T2025901"
ADMIN_STAFF_NO = "T2025900"
TEACHER = {"X-Teacher-Staff-No": PLAIN_STAFF_NO}
ADMIN = {"X-Teacher-Staff-No": ADMIN_STAFF_NO}
#: 演示口令那一串**不在本文件里写第二遍**：本文件走请求头/cookie 两档身份，
#: 而 cookie 那一档要口令，故它的唯一所有者是 :data:`_PASSWORD`（一个测试内部
#: 常量，与 ``scripts/demo_bootstrap.py`` 的 ``DEMO_PASSWORD`` 无关）。
_PASSWORD = "本文件自己设的一串"


@pytest.fixture()
def people(engine):
    """一个宽学期 + 两个出生日期**不同**的学生 + 一个普通教师 + 一个管理员。

    ⚠️ **用完即关**（``with Session(...)``）：``tests/api/conftest.py`` 的模块
    docstring 交代了 StaticPool 下全进程只有一条 DBAPI 连接。
    ⚠️ 两个学生都**不绑口令**（``password_hash`` 留 ``NULL``）——那正是抢绑的
    前提，也让本夹具与 ``tests/api/test_bind_token.py`` 的 ``people`` 同形。
    """
    with Session(engine) as session:
        session.add(
            Semester(
                name="2025-2026-1", start_date=dt.date(2020, 1, 1),
                end_date=dt.date(2030, 1, 1), weeks=16, is_current=True,
            )
        )
        one = Student(student_no=STUDENT_NO, name="探针甲", sex="male",
                      birth=BIRTH_ONE, grade=2025)
        two = Student(student_no=OTHER_STUDENT_NO, name="探针乙", sex="female",
                      birth=BIRTH_TWO, grade=2025)
        teacher = Teacher(staff_no=PLAIN_STAFF_NO, name="普通教师", role="teacher")
        admin = Teacher(staff_no=ADMIN_STAFF_NO, name="管理员", role="admin")
        session.add_all([one, two, teacher, admin])
        session.commit()
        return {"one": one.id, "two": two.id}


def _db_row(client, student_id: int) -> dict:
    """**直接查库**取 ``student`` 那一行的每一列（裸 SQL，不经 ORM、不经 HTTP）。

    ⚠️ 它是「掩码没有被写回库」那一拍的**期望侧**：与响应体是两个独立取法，
    于是「PATCH 之后库里那一行逐字未变」这句话不是自指的。
    """
    with Session(client.app.state.engine) as session:
        row = session.execute(
            text("SELECT * FROM student WHERE id = :i"), {"i": student_id}
        ).mappings().one()
        return dict(row)


def _app_py_files() -> "list[pathlib.Path]":
    """``backend/app/`` 下全部 ``.py``（AST 扫描面）。"""
    return sorted(p for p in (BACKEND / "app").rglob("*.py") if "__pycache__" not in p.parts)


def _every_model() -> "set[type[BaseModel]]":
    """进程里注册过的**全部** Pydantic 模型（沿 ``__subclasses__`` 传递闭包）。

    ⚠️ 它比「AST 扫 ``app/api/schemas/``」更强：一个将来住在别处的响应模型
    只要被 import 过就进得来，于是「新加一条带 ``birth`` 的响应面」不会静默。
    """
    seen: "set[type[BaseModel]]" = set()
    queue = list(BaseModel.__subclasses__())
    while queue:
        cls = queue.pop()
        if cls in seen:
            continue
        seen.add(cls)
        queue.extend(cls.__subclasses__())
    return seen


def _request_with_role(role: "str | None") -> Request:
    """造一个 ``request.state`` 上**已经挂好**教职身份的假 ``Request``。

    ⚠️ ``scope["state"]`` 就是 :class:`starlette.datastructures.State` 的后端
    （逐字口径见 :func:`app.api.crud._require_staff_identity` 的 docstring），
    故这里给一个空 dict 就够了。
    """
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [],
                       "state": {}})
    setattr(request.state, STAFF_READER_STATE_KEY,
            ReaderIdentity(staff_no=PLAIN_STAFF_NO, role=role))
    return request


# ===========================================================================
# ① 教师那一档：两条路都读到掩码
# ===========================================================================
def test_a_plain_teacher_reads_the_mask_on_the_roster_and_on_the_detail(client, people):
    """**普通教师**读名册的**两条**路（list 与 read-one）都只拿到掩码。

    ⚠️ 三格判据，缺一格本条就可能假绿：
    ① 那一格的**值**逐字等于掩码字面量；
    ② 库里那**两个真实**出生日期的 ISO 串**一个都不出现**在原始响应体里
      （期望侧取自本文件的字面量、被测侧是 ``response.text``，两侧不同源）；
    ③ 掩码串**确实出现**（否则「那一格被整个摘掉」也能让 ①② 全绿，
      而摘掉它会改 openapi 的契约面 —— 本件明确不改 schema）。
    """
    listing = client.get("/api/students?limit=200", headers=TEACHER)
    assert listing.status_code == 200, listing.text
    page = listing.json()
    assert page["total"] == 2, page
    assert [row["birth"] for row in page["items"]] == [MASK, MASK], page["items"]
    for real in (BIRTH_ONE.isoformat(), BIRTH_TWO.isoformat()):
        assert real not in listing.text, (real, listing.text)
    assert MASK in listing.text

    for key, real in (("one", BIRTH_ONE), ("two", BIRTH_TWO)):
        detail = client.get(f"/api/students/{people[key]}", headers=TEACHER)
        assert detail.status_code == 200, detail.text
        assert detail.json()["birth"] == MASK, detail.text
        assert real.isoformat() not in detail.text, detail.text
        assert MASK in detail.text


def test_the_mask_holds_on_the_cookie_channel_too(client, people):
    """⚠️ **生产缺省只认 cookie**（``PE_ALLOW_HEADER_IDENTITY`` 的缺省是 ``"0"``），
    故掩码在那一档也必须成立 —— 否则「测试进程打开的那一档绿、甲方在用的那一档漏」。

    三拍：① 教师绑定口令 → 204；② 登录拿到 cookie → 200；
    ③ 用**那一份 cookie**（一个身份头都不发）读两条路 → 都是掩码。
    """
    bound = client.post("/api/auth/teachers/bind", json={
        "staff_no": PLAIN_STAFF_NO, "name": "普通教师", "password": _PASSWORD})
    assert bound.status_code == 204, bound.text
    logged = client.post("/api/auth/login", json={
        "kind": "teacher", "login": PLAIN_STAFF_NO, "password": _PASSWORD})
    assert logged.status_code == 200, logged.text
    assert logged.json()["role"] == "teacher", logged.text

    listing = client.get("/api/students?limit=200")
    assert listing.status_code == 200, listing.text
    assert [row["birth"] for row in listing.json()["items"]] == [MASK, MASK]
    for real in (BIRTH_ONE.isoformat(), BIRTH_TWO.isoformat()):
        assert real not in listing.text
    detail = client.get(f"/api/students/{people['one']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["birth"] == MASK
    assert BIRTH_ONE.isoformat() not in detail.text


# ===========================================================================
# ② 管理员那一档：读到完整值（**裁定**，不许悄悄变）
# ===========================================================================
def test_an_admin_reads_the_full_value_on_both_routes(client, people):
    """**管理员**读到的是完整值。⚠️ 本条是 :func:`test_a_plain_teacher_reads_the_mask_on_the_roster_and_on_the_detail`
    的**绿档半边**（硬规矩 #50）：少了它，「一律掩」（= 把管理台的编辑表单弄坏）
    与「一律不掩」（= 本件要修的那一格原样留着）都能让半边全绿。

    ⚠️ 而「管理员不掩」是一条**裁定**（理由见模块 docstring），故本条同时钉住
    它的**声明面**：:data:`app.api.crud.REDACT_ADMIN_ONLY` 就是 ``{"admin"}``。
    """
    listing = client.get("/api/students?limit=200", headers=ADMIN)
    assert listing.status_code == 200, listing.text
    got = {row["id"]: row["birth"] for row in listing.json()["items"]}
    assert got == {people["one"]: BIRTH_ONE.isoformat(),
                   people["two"]: BIRTH_TWO.isoformat()}, got
    assert MASK not in listing.text

    detail = client.get(f"/api/students/{people['two']}", headers=ADMIN)
    assert detail.status_code == 200, detail.text
    assert detail.json()["birth"] == BIRTH_TWO.isoformat(), detail.text
    assert set(REDACT_ADMIN_ONLY) == {"admin"}


# ===========================================================================
# ③ 学生那一档：行级闸门先挡掉，**到不了**值级变形（派单守卫 ② 的顶回）
# ===========================================================================
def test_a_student_session_is_rejected_by_the_row_gate_before_any_redaction(client, people):
    """学生会话在 ``students`` 资源上是 **401**，而它自己的窄端点里**没有 ``birth``**。

    ⚠️ 派单守卫 ② 要的是「学生读自己**能**拿到完整值」。⚠️ **那一格今天不成立、
    也不需要成立**（逐字理由见模块 docstring 的「顶回」那一段）：
    ``students`` 的 ``read_scope`` 是 ``"staff"``，学生被**行级**闸门挡在门外
    （请求头通道 401；cookie 通道 403 那一档由 ``tests/api/test_crud.py`` 的
    ``test_the_student_keyed_resources_admit_four_read_tiers`` 钉住），
    根本走不到变形那一步。

    ⚠️ 本条因此钉**真**口径的三格，每一格各挡一个静默失效：
    ① 学生打两条路 → **401**（不是 200，也不是掩码）——若有人为了「让学生读到
      自己」把 ``read_scope`` 放宽，本拍当场红；
    ② 401 的响应体里既没有真实出生日期、也没有掩码（变形**没被**触发过）；
    ③ 学生自己的窄端点 ``GET /api/students/{id}/home`` 的响应体里
      **没有 ``birth`` 这一格**（:class:`app.api.schemas.dashboard.StudentHomeRead`
      逐字不含它）⇒ 「学生从别处把自己的出生日期读回来」这条路不存在。
    """
    mine = {"X-Student-Id": str(people["one"])}
    for path in ("/api/students", f"/api/students/{people['one']}"):
        got = client.get(path, headers=mine)
        assert got.status_code == 401, (path, got.status_code, got.text)
        assert BIRTH_ONE.isoformat() not in got.text, got.text
        assert MASK not in got.text, got.text

    home = client.get(f"/api/students/{people['one']}/home", headers=mine)
    assert home.status_code == 200, home.text
    assert "birth" not in home.json(), sorted(home.json())
    assert BIRTH_ONE.isoformat() not in home.text, home.text


# ===========================================================================
# ④ 两份响应体**只差一格** / 掩码是恒定形状
# ===========================================================================
def test_the_masked_and_the_full_bodies_differ_in_exactly_one_cell(client, people):
    """教师那份与管理员那份响应体**逐格**比，只有 ``birth`` 一格不同。

    ⚠️ 本条钉的是 :func:`app.api.crud._redacted_detail` 那段 docstring 的承诺
    （「逐字节等于不变形那一档减去掩码那几格」）：那个函数**不自己拼 dict**，
    而是走 ``read_model.model_validate`` + ``jsonable_encoder`` 那**同一对**函数，
    故键序、``date`` → ISO 串的折法、``response_model`` 摘掉的那两列
    （``password_hash`` / ``password_bound_at``）三格全部相同。
    ⚠️ 于是「变形顺手改坏了别的格」这类失效会被抓到，而不是只验 ``birth`` 那一格。

    ⚠️ list 与 read-one **两侧都比**：它们是两个消费者
    （:func:`app.api.crud._redact_rows` 就地改 / :func:`app.api.crud._redacted_detail`
    折成 ``JSONResponse``），只比一侧的话另一侧漂开是静默的。
    """
    masked = client.get(f"/api/students/{people['one']}", headers=TEACHER)
    full = client.get(f"/api/students/{people['one']}", headers=ADMIN)
    assert (masked.status_code, full.status_code) == (200, 200)
    left, right = masked.json(), full.json()
    assert list(left) == list(right), (list(left), list(right))
    assert sorted(k for k in left if left[k] != right[k]) == ["birth"], (left, right)
    assert left["birth"] == MASK and right["birth"] == BIRTH_ONE.isoformat()
    assert "password_hash" not in left and "password_bound_at" not in left

    masked_rows = client.get("/api/students?limit=200", headers=TEACHER).json()["items"]
    full_rows = client.get("/api/students?limit=200", headers=ADMIN).json()["items"]
    assert len(masked_rows) == len(full_rows) == 2
    for one, other in zip(masked_rows, full_rows):
        assert one["id"] == other["id"]
        assert sorted(k for k in one if one[k] != other[k]) == ["birth"], (one, other)


def test_the_mask_is_a_constant_shape_that_leaks_nothing_about_the_value(client, people):
    """掩码对「有值」与「值是多少」给**同一个**串 ⇒ 它一个比特都不泄漏。

    ⚠️ 三格：
    ① 库里那两行的出生日期**确实不同**（否则本条退化，见 :data:`BIRTH_ONE` 的注释）；
    ② 掩码之后那两格**只有一个取值**；
    ③ 掩过与没掩过的那两份 ``items`` **键集合逐字相同**（掩码没有多造一列、
      也没有把某一列摘掉 —— 摘列会改 openapi 的契约面，本件明确不改 schema）。
    ⚠️ 外加一格**结构性**的事实：``student.birth`` 是 ``Date`` **NOT NULL**，
    故「这一格有没有值」这个信号在响应体上本来就不存在，掩码也就无从泄漏它。
    """
    masked = client.get("/api/students?limit=200", headers=TEACHER).json()["items"]
    full = client.get("/api/students?limit=200", headers=ADMIN).json()["items"]
    assert len({row["birth"] for row in full}) == 2, full
    assert {row["birth"] for row in masked} == {MASK}, masked
    assert [sorted(row) for row in masked] == [sorted(row) for row in full]
    assert Student.__table__.c.birth.nullable is False


# ===========================================================================
# ⑤ 掩码不是合法日期 ⇒ 写回是**响亮**的（本件的承重格）
# ===========================================================================
def test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud(client, people):
    """两段，红绿都在场。

    **红档**：掩码 PATCH 回去 → **422** ``request_validation_failed``，且**库里那一行
    逐字未变**（期望侧是 :func:`_db_row` 直接查库、被测侧是 HTTP，两侧不同源）。
    ⚠️ 「库里逐字未变」那一拍是本条的全部判别力：少了它，一个**静默**把掩码
    写进库的实现（= 一次数据损坏）也能让 422 那一拍全绿。

    **绿档对照**：一个**合法**日期形状的串 PATCH 回去 → **200**，且库里那一格
    **真的变了**。⚠️ 它证明上面那一发 422 是「值不是日期」造成的、而不是
    「这个端点拒绝写入」；⚠️ 而它同时就是「只给年份」（``2005-01-01`` 那一类
    日期形状的掩码）为什么**不能选**的实测证据 —— 管理台的编辑表单把响应体
    预填进 ``<input type="date">``，一个日期形状的掩码在用户手改过别的格之后
    就是一次静默的写坏。

    ⚠️ 期望侧另有一格与被测侧不同源：``dt.date.fromisoformat`` 是**Python 自己**的
    解析器，而端点那一发 422 走的是 **Pydantic** 的解析器 —— 两个独立实现给出
    同一个答案，故「掩码不是合法日期」不是自指的。
    """
    with pytest.raises(ValueError):
        dt.date.fromisoformat(MASK)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", MASK) is None

    sid = people["one"]
    before = _db_row(client, sid)
    rejected = client.patch(f"/api/students/{sid}", json={"birth": MASK}, headers=ADMIN)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "request_validation_failed", rejected.text
    after = _db_row(client, sid)
    assert after == before, ("掩码被写回库了", before, after)
    assert MASK not in json.dumps(after, ensure_ascii=False, default=str)

    accepted = client.patch(f"/api/students/{sid}", json={"birth": LEGAL_DATE},
                            headers=ADMIN)
    assert accepted.status_code == 200, accepted.text
    changed = _db_row(client, sid)
    assert changed != before, "绿档失效：一个合法日期竟然也没写进去"
    assert str(changed["birth"]) == LEGAL_DATE, changed["birth"]

    restored = client.patch(f"/api/students/{sid}",
                            json={"birth": BIRTH_ONE.isoformat()}, headers=ADMIN)
    assert restored.status_code == 200, restored.text
    assert _db_row(client, sid) == before


def test_a_plain_teacher_cannot_write_the_roster_at_all(client, people):
    """写入侧本来就是**管理员独占**，故「教师把掩码写回库」这条路根本不存在。

    ⚠️ 它是 :func:`test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`
    的补强：那一拍证的是「**管理员**写不回去」，本拍证的是「**教师**连写都写不了」。
    四拍一律 **403**（``require_admin`` 那道闸门），且库里那一行逐字未变。
    """
    sid = people["one"]
    before = _db_row(client, sid)
    for method, payload in (("PATCH", {"birth": MASK}), ("PATCH", {"grade": 9}),
                            ("DELETE", None)):
        got = client.request(method, f"/api/students/{sid}", json=payload, headers=TEACHER)
        assert got.status_code == 403, (method, got.status_code, got.text)
        assert got.json()["error"]["code"] == "forbidden", got.text
    created = client.post("/api/students", json={
        "student_no": "X99999999", "name": "探针", "sex": "male",
        "birth": LEGAL_DATE, "grade": 1}, headers=TEACHER)
    assert created.status_code == 403, created.text
    assert _db_row(client, sid) == before


# ===========================================================================
# ⑥ 掩码字面量与判据的**单一所有者**
# ===========================================================================
def test_the_mask_literal_has_exactly_one_definition_in_the_production_tree():
    """AST 扫 ``backend/app/**``：掩码串作为**一个字符串常量**只出现 1 次，
    而那 1 次就是 ``BIRTH_MASK`` 的赋值；名字里带 ``MASK`` 的模块级赋值也只有它。

    ⚠️ 派单守卫 ⑤ 逐字要求的形状。⚠️ 判 ``node.value == MASK``（**全等**）而不是
    「包含」：``crud.py`` 的散文里有若干处**提到**这个串（docstring / 注释），
    而那些不是第二份实现 —— 用「包含」会让本条恒红，于是它抓不到任何东西。
    ⚠️ 而注释根本进不了 AST，故 ``catalog.py`` 那 24 行注释不在扫描面里。

    ⚠️ 「带 MASK 的赋值名」那一格**只数模块级、且名字全大写**的那一类
    （= 常量的形状）。⚠️ 收窄的理由是实测出来的两个**合法**同名者：
    ``crud.py`` 端点体里的局部变量 ``masks``（它是 :func:`masked_columns_for`
    的返回值，不是第二份掩码）与 ``app/seed/population.py`` 的 ``male_mask``
    （人口生成器的性别配比，与 ``birth`` 无关）。不收窄的话本条恒红、
    于是它抓不到任何东西（与上面「包含 vs 全等」同一条理由）。

    ⚠️ 反空转：末拍断言扫描面本身不小（``backend/app/`` 下的 ``.py`` 个数下界），
    否则「BACKEND 指错了」与「真的只有一处」在颜色上不可分辨。
    """
    literals: "list[str]" = []
    mask_names: "list[tuple[str, str]]" = []
    files = _app_py_files()
    for path in files:
        where = path.relative_to(BACKEND).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == MASK:
                literals.append(where)
        # ⚠️ 刻意只走 ``tree.body``（模块级），不走 ``ast.walk``：见上面那一段。
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Name) and "MASK" in target.id
                            and target.id.isupper()):
                        mask_names.append((where, target.id))
    assert literals == ["app/api/crud.py"], literals
    assert mask_names == [("app/api/crud.py", "BIRTH_MASK")], mask_names
    assert len(files) >= 60, f"只扫到 {len(files)} 个 .py：BACKEND 指错了？{BACKEND}"
    assert BIRTH_MASK == MASK, "被测侧读到的常量与期望侧的字面量漂开了"


def test_the_declaration_is_unique_and_the_judgement_has_a_single_owner():
    """23 行 ``RESOURCES`` 里**恰好 1 行**声明变形，且那一格的四个取值全被钉住。

    ⚠️ 期望侧一律字面量：``"/api/students"`` / ``("birth",)`` / 掩码串 /
    ``{"admin"}`` / ``"staff"``，**不读** :data:`app.api.crud.READ_SCOPE_STAFF`
    与 :data:`app.api.deps.ADMIN_ROLE`。
    ⚠️ 而「判据只有一个所有者」那一格由末两拍钉：全仓只有 ``catalog.py`` 一个
    模块 import 了 :data:`app.api.crud.BIRTH_MASK`（= 只有一个声明点），
    且 ``app/api/routers/**`` 里没有任何一处自己写 ``role`` 判据。
    """
    assert len(RESOURCES) == 23
    declared = [row for row in RESOURCES if row.get("redact")]
    assert len(declared) == 1, [row["path"] for row in declared]
    row = declared[0]
    assert row["path"] == "/api/students"
    assert tuple(item.column for item in row["redact"]) == ("birth",)
    item = row["redact"][0]
    assert isinstance(item, Redaction)
    assert item.mask == MASK
    assert set(item.full_for) == {"admin"}
    assert row["read_scope"] == "staff"
    assert row["require_admin"] is True

    importers = []
    for path in _app_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.api.crud":
                if any(alias.name == "BIRTH_MASK" for alias in node.names):
                    importers.append(path.relative_to(BACKEND).as_posix())
    assert importers == ["app/api/routers/catalog.py"], importers


def test_masked_columns_for_is_the_single_judgement_and_does_not_over_narrow():
    """:func:`app.api.crud.masked_columns_for` 是「谁该被掩」的**唯一**判据，
    而它的失效方向是**少给**（不在 ``full_for`` 里的一律变形）。

    ⚠️ 四拍：
    ① ``role='admin'`` → ``{}``（= 读到完整值）；
    ② ``role='teacher'`` → ``{"birth": 掩码}``；
    ③ ``role is None`` → **同样变形**（那一档今天在 ``students`` 资源上到不了，
      但判据本身必须是「不在名单里就掩」，否则「名单写错一个串」会静默地多给）；
    ④ ``redactions`` 为空 → **短路**、根本不碰 ``request.state``
      （那 7 个匿名资源没有身份；碰了就是 ``RuntimeError`` → 500）。
    ⚠️ ④ 那一拍传的是一个 ``state`` 里**什么都没挂**的 ``Request``：
    它证明短路是真的短路，而不是「挂了身份才不炸」。
    """
    declared = (Redaction(column="birth", mask=MASK, full_for=frozenset({"admin"})),)
    assert masked_columns_for(declared, _request_with_role("admin")) == {}
    assert masked_columns_for(declared, _request_with_role("teacher")) == {"birth": MASK}
    assert masked_columns_for(declared, _request_with_role(None)) == {"birth": MASK}

    bare = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    assert masked_columns_for((), bare) == {}
    with pytest.raises(RuntimeError) as loud:
        staff_reader_of_request(bare)
    assert "教职身份" in str(loud.value)


# ===========================================================================
# ⑦ 没有第二条路（派单第 1 件的**结构性**守卫）
# ===========================================================================
def test_every_birth_bearing_resource_row_declares_a_redaction_covering_it():
    """**任何一个**读模型里含 ``birth`` 的资源行，都必须声明覆盖它的变形。

    ⚠️ 本条是「只掩一条等于没掩」那一格的**结构性**答案：它不数「今天有几条路」，
    而是把「暴露 ``birth``」与「声明变形」两件事**绑在一起**——
    将来谁给 ``RESOURCES`` 加一行含 ``birth`` 的资源（或给某个读模型加一列
    ``birth``）而忘了声明变形，本条当场红，而不是等到终审去逐条路数。

    ⚠️ 反空转：末拍断言扫描面本身是 23 行、且其中**确实有**一行含 ``birth``，
    否则「``RESOURCES`` 是空的」与「全都声明好了」在颜色上不可分辨。
    """
    assert len(RESOURCES) == 23
    carriers = []
    for row in RESOURCES:
        if "birth" not in row["schemas"].read.model_fields:
            continue
        carriers.append(row["path"])
        covered = {item.column for item in row.get("redact", ())}
        assert "birth" in covered, (row["path"], sorted(covered))
    assert carriers == ["/api/students"], carriers


def test_the_students_roster_is_the_only_response_model_that_carries_a_birth():
    """全进程 **144** 个 Pydantic 模型里，含 ``birth`` 字段的恰好是那 **4** 个，
    而其中**只有 ``StudentRead`` 是响应模型**。

    ⚠️ 这一格比「逐条路数一遍」更强：它把「``birth`` 能从哪些**响应面**离开
    服务器」收窄到一个名字上，于是任何**新**的响应模型只要带 ``birth``，
    本条当场红（而 :func:`test_every_birth_bearing_resource_row_declares_a_redaction_covering_it`
    会接着要求它声明变形）。

    ⚠️ 另外三个是**请求体**（学生自助绑定的验身材料、管理台的新建/修改），
    方向是**客户端 → 服务器**，故不是泄漏面；⚠️ 而它们**一个都不许**被当成
    某个资源的读模型（末拍）。
    """
    models = _every_model()
    assert len(models) >= 100, len(models)
    carrying = sorted(m.__name__ for m in models if "birth" in m.model_fields)
    assert carrying == ["StudentBindCreate", "StudentCreate", "StudentRead",
                        "StudentUpdate"], carrying
    reads = {row["schemas"].read for row in RESOURCES}
    assert StudentRead in reads
    for name in ("StudentBindCreate", "StudentCreate", "StudentUpdate"):
        cls = next(m for m in models if m.__name__ == name)
        assert cls not in reads, name
    assert StudentRead.model_fields["birth"].annotation is dt.date


def test_there_is_no_export_or_roster_route_and_the_csv_contract_never_crosses_http(app):
    """⚠️ **顶回派单第 1 件的第 3、4 条**：那两个端点在本仓**不存在**，本条钉住它。

    派单把 ``GET /api/teacher/roster``（「交付须知第 4 条点名的就是它」）与
    ``/api/export/...``（「逐资源列白名单、``birth`` 在列级被放行」）点成本件的命门。
    实测：openapi 的全部路径里**没有任何一条**匹配 ``export`` / ``roster`` /
    ``csv`` / ``download`` —— 名册只有一条 HTTP 路（``/api/students`` 那个 CRUD
    资源的 list + read-one），而「列白名单」在本仓对应的是
    ``list_exclude``（逐资源，只排 ``password_hash`` / ``password_bound_at`` /
    ``rpe_token`` 三类**凭据**列，与 ``birth`` 无关）。

    ⚠️ 派单说的那份「导出侧列白名单」真正的住址是
    :data:`app.adapters.base.STUDENT_COLUMNS` —— 那是**入站**的模拟数据源
    （``students.csv``）列序契约：``app/adapters/mock_lepao.py`` 读它、
    ``app/seed/generate.py`` 的 ``write_csv`` 离线写它，**一个字节都不经 HTTP**。
    ⚠️ 本条把那一格也钉住：全仓 import ``STUDENT_COLUMNS`` 这个名字的模块
    **恰好是 ``app/adapters/mock_lepao.py`` 一个**，HTTP 层（``app/api/**``）
    一个都没有 ⇒ 「教师导出一份含完整 ``birth`` 的 CSV」这条路今天不存在，
    而它将来若被加进来，会先撞本条与上面那两条结构守卫。
    ⚠️ 判据**刻意不是**「``app/api/**`` 不许 import ``app.adapters``」：
    ``app/api/routers/pipeline.py`` **合法地** import 了 ``app.adapters.factory``
    （``POST /api/pipeline/run-daily`` 要一个数据源适配器），而那条依赖方向由
    ``tests/architecture/test_layering.py`` 的白名单钉着，不是本条的事。
    """
    paths = sorted(app.openapi()["paths"])
    assert len(paths) >= 70, len(paths)
    assert [p for p in paths if re.search(r"export|roster|csv|download", p, re.I)] == []

    importers = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                    alias.name == "STUDENT_COLUMNS" for alias in node.names):
                importers.append(path.relative_to(BACKEND).as_posix())
    assert importers == ["app/adapters/mock_lepao.py"], importers


def test_no_get_route_hands_a_real_birth_to_a_plain_teacher(client, people):
    """**全端点扫描**：以普通教师身份打 openapi 里**每一个** GET，
    任何一个 **200** 的响应体里都不许出现库里那**两个真实**出生日期。

    ⚠️ 这是「只掩一条等于没掩」那一格的**端到端**答案（上面两条是结构面、
    本条是运行面，两面都要）：它不挑端点、不看代码，只按契约面逐条打一遍。
    ⚠️ 期望侧（那两个真实出生日期）是本文件的字面量、被测侧是 ``response.text``
    ⇒ 两侧不同源。

    ⚠️ **反空转三格**（少了任何一格，「一个端点都没打通」与「打通了但一个都没漏」
    在颜色上不可分辨）：
    ① 扫描面本身 ≥ 60 条；② 至少 8 条真的回了 200；
    ③ **出现掩码的路恰好是那 2 条**（= 变形真的发生了、而且只发生在那一个资源上）。
    """
    paths = sorted(p for p, methods in client.app.openapi()["paths"].items() if "get" in methods)
    assert len(paths) >= 60, len(paths)
    sid = str(people["one"])
    reals = (BIRTH_ONE.isoformat(), BIRTH_TWO.isoformat())
    statuses: "dict[str, int]" = {}
    masked: "list[str]" = []
    for template in paths:
        concrete = template.replace("{student_id}", sid)
        concrete = re.sub(r"\{[a-z_]+\}", "1", concrete)
        got = client.get(concrete, headers=TEACHER)
        statuses[template] = got.status_code
        if got.status_code == 200:
            for real in reals:
                assert real not in got.text, (template, real)
        if MASK in got.text:
            masked.append(template)
    assert sum(1 for code in statuses.values() if code == 200) >= 8, statuses
    assert sorted(masked) == ["/api/students", "/api/students/{student_id}"], masked
    assert statuses["/api/students"] == 200, statuses
    assert [t for t, code in statuses.items() if code >= 500] == [], statuses


# ===========================================================================
# ⑧ 两条审计表里都不落 ``birth``
# ===========================================================================
def test_neither_audit_table_records_a_birth_value(client, people):
    """名册被读过之后，``audit_log`` 与 ``read_audit_log`` 的**每一列**里
    都不出现真实出生日期、也不出现掩码。

    ⚠️ 两张审计表都宣称「永不落请求体」（Plan 06 Task 9 的结构性保证 +
    Plan 08 Task 1 在读审计上同款）。⚠️ 本条补的是**响应体**那一半：
    名册读是 :data:`app.api.read_audit.ReadClass` 的 ``STUDENT_ROSTER`` 那一档
    （一次摊出 60 人，故它比逐人读更该留痕），而留痕留的必须是
    「谁、什么时候、读了哪条路、读到了谁」，**不是**读到的内容。

    ⚠️ **反空转**：先断言读审计**真的记下了**名册那一条（``route`` 是
    ``/api/students``），否则「一行都没记」与「记了但没落 birth」同色 ——
    而前者恰好是本件要防的那一次退化（把敏感读整个关掉也能让本条全绿）。
    """
    sid = people["one"]
    assert client.get("/api/students?limit=200", headers=TEACHER).status_code == 200
    assert client.get(f"/api/students/{sid}", headers=TEACHER).status_code == 200
    assert client.get(f"/api/students/{sid}", headers=ADMIN).status_code == 200

    with Session(client.app.state.engine) as session:
        audits = [dict(r) for r in session.execute(text("SELECT * FROM audit_log")).mappings()]
        reads = [dict(r) for r in
                 session.execute(text("SELECT * FROM read_audit_log")).mappings()]
    assert reads, "读审计一行都没记 ⇒ 本条的绿是空转"
    assert any(row["route"] == "/api/students" for row in reads), \
        sorted({row["route"] for row in reads})

    needles = [BIRTH_ONE.isoformat(), BIRTH_TWO.isoformat(), MASK]
    for table, rows in (("audit_log", audits), ("read_audit_log", reads)):
        for row in rows:
            blob = json.dumps(row, ensure_ascii=False, default=str)
            for needle in needles:
                assert needle not in blob, (table, row.get("id"), needle, blob)


# ===========================================================================
# ⑨ 契约面：掩码不进 openapi，``birth`` 那一格的 schema 一格未动
# ===========================================================================
def test_the_mask_never_reaches_the_contract_and_the_birth_schema_is_untouched(app):
    """计划 §5 的裁定是「**不改 schema，只改值**」，本条把那半句钉住。

    ⚠️ 两格：① 掩码字面量在整份 openapi 里出现 **0** 次（它是一次**运行时**的
    值级变形，不是一次契约变更）；② ``StudentRead.birth`` 那一格的 schema
    逐字仍是 ``{"type": "string", "format": "date", "title": "Birth"}``
    —— 即字段还在、类型还是 date。
    ⚠️ 于是「掩码把契约面弄坏」与「掩码悄悄把那一列摘掉」两个方向都被挡住。
    ⚠️ openapi 的**五格**（77 / 106 / 87 / 65-15 / 3）由 ``frontend/scripts/smoke.mjs``
    第 15 步钉住，本处刻意不抄第二份。
    """
    spec = app.openapi()
    blob = json.dumps(spec, ensure_ascii=False)
    assert MASK not in blob
    assert blob.count(BIRTH_MASK) == 0
    assert spec["components"]["schemas"]["StudentRead"]["properties"]["birth"] == {
        "type": "string", "format": "date", "title": "Birth",
    }


# ===========================================================================
# ⑩ 工厂的导入期校验（三道，各挡一个**静默**失效）
# ===========================================================================
def _probe_router(**overrides):
    """造一个**合成**资源的 router（⚠️ 只造、不 ``include_router``）。

    ⚠️ 缺省形状是「与 ``students`` 那一行同档」（``read_scope="staff"`` +
    一格合法的变形），于是每个调用点只改**它要验的那一格**，
    与 ``tests/api/test_crud.py`` 里那一批合成资源同一条口径。
    """
    kwargs = dict(
        model=Student,
        schemas=CrudSchemas(StudentRead, StudentCreate, StudentUpdate),
        path="/api/probe-birth-scope",
        tags=["probe"],
        writable=False,
        on_delete=ON_DELETE_RESTRICT,
        natural_key=("student_no",),
        read_scope=READ_SCOPE_STAFF,
        redact=(Redaction(column="birth", mask=BIRTH_MASK, full_for=REDACT_ADMIN_ONLY),),
    )
    kwargs.update(overrides)
    return build_crud_router(**kwargs)


def test_the_factory_rejects_a_redaction_on_any_other_read_tier():
    """第 16 道校验：变形今天**只**接在 ``read_scope="staff"`` 那一个端点分支上。

    ⚠️ 挂在别的档上是一件**什么也不发生**的事（响应照旧给完整值、端点 200、
    openapi 不变、既有测试也不红）⇒ 失效形态是**静默**的，而它静的恰好是
    本件要关掉的那一格。故它必须响在**导入期**。
    ⚠️ 两个反例各要一档：``None``（匿名参考数据那一档）与 ``"student_self"``
    （学生键那一档）。⚠️ 后者必须**同时**显式给出 ``student_owner``：
    工厂的另一道校验排在第 16 道**之前**（「声明了学生键档就必须说清哪一列是
    学生键」），不给的话本条会红在**另一道**校验上、于是一句判别力都没有。
    ⚠️ 绿档：缺省那一档（``"staff"``）**能**造出来（末拍）。
    """
    with pytest.raises(ValueError) as anonymous:
        _probe_router(path="/api/probe-birth-tier-anon", read_scope=None)
    assert "read_scope" in str(anonymous.value), str(anonymous.value)
    assert "静默" in str(anonymous.value), str(anonymous.value)

    with pytest.raises(ValueError) as student_tier:
        _probe_router(path="/api/probe-birth-tier-self",
                      read_scope=READ_SCOPE_STUDENT_SELF,
                      student_owner=StudentOwner(column="id"))
    assert "read_scope" in str(student_tier.value), str(student_tier.value)
    assert "静默" in str(student_tier.value), str(student_tier.value)

    assert _probe_router(path="/api/probe-birth-ok") is not None


def test_the_factory_rejects_an_empty_mask_or_an_unknown_role_in_full_for():
    """第 17 道校验的两支，各挡一个**静默**失效。

    ① ``mask`` 是空串/全空白 ⇒ 那一格在响应体里变成 ``""``，而 ``""`` 对前端
      （``contract.ts`` 的 ``fromInputValue`` 把空串折成 ``undefined``）与
      「这一格没传」在 PATCH 那一侧**同形**，于是「掩码」退化成一次能被写回库的空值；
    ② ``full_for`` 里写了一个不在 ``teacher.role`` 取值域里的串（例如把
      ``"admin"`` 打成 ``"Admin"``）⇒ 那一档**永远**匹配不上 ``reader.role``，
      于是「管理员读到完整值」这条裁定**静默**变成「管理员也读到掩码」
      —— 而管理台的编辑表单会把掩码预填进 ``<input type="date">``。
    """
    for bad in ("", "   "):
        with pytest.raises(ValueError) as exc:
            _probe_router(
                path="/api/probe-birth-empty-mask",
                redact=(Redaction(column="birth", mask=bad, full_for=REDACT_ADMIN_ONLY),),
            )
        assert "非空" in str(exc.value), str(exc.value)

    with pytest.raises(ValueError) as exc:
        _probe_router(
            path="/api/probe-birth-bad-role",
            redact=(Redaction(column="birth", mask=BIRTH_MASK,
                              full_for=frozenset({"Admin"})),),
        )
    assert "full_for" in str(exc.value), str(exc.value)
    assert "Admin" in str(exc.value), str(exc.value)


def test_the_factory_rejects_a_redaction_column_that_is_not_on_the_model():
    """第 14 道校验：``redact`` 的列名与 ``pk`` / ``order_by`` / ``natural_key`` /
    ``list_exclude`` / ``section_column`` 五格走**同一个**循环。

    ⚠️ 写错一个列名的失效形态是**请求时**一个 ``if column in row`` 恒假
    ⇒ 掩码静默地什么也不换、响应照旧给完整值 —— 与本件要修的那一格**方向相反**，
    故更要挡在导入期。
    """
    with pytest.raises(ValueError) as exc:
        _probe_router(
            path="/api/probe-birth-bad-column",
            redact=(Redaction(column="birth_date", mask=BIRTH_MASK,
                              full_for=REDACT_ADMIN_ONLY),),
        )
    assert "birth_date" in str(exc.value), str(exc.value)
