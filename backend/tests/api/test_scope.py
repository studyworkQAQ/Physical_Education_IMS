"""身份与作用域闸门（计划 Review Focus 第 1 条：**越权访问**）。

Review Focus 第 1 条的原文是「学生 A 用 ``X-Student-Id: B`` 的请求头去读/写学生 B 的
打卡、RPE、训练单、处方」。原型没有真实鉴权，但**必须有一道闸门**，否则前端一上线
就是任意读写全库。本文件钉住那道闸门的三件事：

1. **缺身份 → 401**（不是 200、也不是 500）；
2. **身份与目标行的所有者不匹配 → 403**；
3. :func:`app.api.deps.require_scope` 单独调用时也是同一套判定（它不是只在 HTTP
   路径上才生效的一层糖）。

**为什么用「探针路由」而不是等 Task 3/5 的真实端点**：本 Task 是 HTTP 层的地基，
``app/api/routers/`` 到 Task 3 才建。而闸门能不能用，取决于它与 ``Depends`` 的
**接线方式**对不对——那正是探针要复现的东西。下面 ``_install_probes`` 里那三个路由的
形状（``Depends(current_student)`` 拿身份、``Depends(get_db)`` 拿会话、然后在函数体里
调 ``require_scope``）就是 Task 3 的 ``build_crud_router`` 与 Task 5 的三源采集端点
将要写的形状；接线错了这里先红，而不是等到 8 个 Task 之后。
"""
import datetime as dt

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import Page, current_student, current_teacher, get_db, require_scope
from app.db.models.organisation import Student


def _add_student(engine, student_no: str) -> int:
    """插一个学生、返回它的 ``id``。

    ⚠️ **用完即关**（``with Session(...)``）：``conftest.py`` 的模块 docstring 交代了
    StaticPool 下全进程只有一条 DBAPI 连接，留一个开着事务的 ``Session`` 会与请求里
    ``get_db`` 的 ``Session`` 抢它。
    """
    with Session(engine) as session:
        student = Student(
            student_no=student_no,
            name=student_no,
            sex="male",
            birth=dt.date(2005, 1, 1),
            department=None,
            grade=1,
        )
        session.add(student)
        session.commit()
        return student.id


def _install_probes(application) -> None:
    """在**被测应用**上挂三个探针路由，形状与 Task 3/5 的真实端点一致。"""

    @application.get("/probe/student/{student_id}")
    def _student_probe(
        student_id: int,
        requester: int = Depends(current_student),
        session: Session = Depends(get_db),
    ):
        require_scope(session, student_id, requester)
        return {"student_id": student_id, "requester": requester}

    @application.get("/probe/teacher")
    def _teacher_probe(staff_no: str = Depends(current_teacher)):
        return {"staff_no": staff_no}

    @application.get("/probe/page")
    def _page_probe(page: Page = Depends()):
        return {"limit": page.limit, "offset": page.offset}


@pytest.fixture()
def probe(app, engine) -> TestClient:
    """挂好探针路由的 ``TestClient``（``app`` / ``engine`` 来自 ``conftest.py``）。"""
    _install_probes(app)
    with TestClient(app) as test_client:
        yield test_client


def test_missing_identity_header_is_401(probe):
    """缺 ``X-Student-Id`` / ``X-Teacher-Staff-No`` 一律 401，且响应体是统一形状。

    两个身份依赖各测一次：它们是**两个**函数，只测一个的话另一个漏掉 ``raise``
    也照样全绿。
    统一形状 ``{"error": {"code", "message", "detail"}}`` 在这里一并钉住——
    键集合与 ``code`` 的字面值都写死在断言里（硬规矩 #35：不从 ``errors.py`` 读回来）。
    """
    student = probe.get("/probe/student/1")
    assert student.status_code == 401
    body = student.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail"}
    assert body["error"]["code"] == "unauthenticated"
    assert body["error"]["detail"] is None
    assert "X-Student-Id" in body["error"]["message"]

    teacher = probe.get("/probe/teacher")
    assert teacher.status_code == 401
    assert teacher.json()["error"]["code"] == "unauthenticated"
    assert "X-Teacher-Staff-No" in teacher.json()["error"]["message"]

    # 绿档同时在场（硬规矩 #50）：带头就必须放行，否则「一律 401」也能让上面全绿。
    with_header = probe.get("/probe/teacher", headers={"X-Teacher-Staff-No": "T2025001"})
    assert with_header.status_code == 200
    assert with_header.json() == {"staff_no": "T2025001"}


def test_a_student_cannot_read_another_students_row(engine, probe):
    """Review Focus 第 1 条的字面形状：A 用 ``X-Student-Id`` 读 B 的行 → 403。

    ⚠️ **红绿两档必须同时在场**（硬规矩 #50）：只有 403 那一档的话，一个恒抛 403 的
    闸门（``raise HTTPException(403)`` 写在函数第一行）也能全绿。故同一支探针上用
    A 自己的 id 再请求一次，必须 200 且回显的是 A 的数据。
    """
    alice = _add_student(engine, "A2025001")
    bob = _add_student(engine, "B2025002")
    assert alice != bob, "两个学生的主键必须不同，否则本测试退化成自己读自己"

    cross = probe.get(f"/probe/student/{bob}", headers={"X-Student-Id": str(alice)})
    assert cross.status_code == 403
    assert cross.json()["error"]["code"] == "forbidden"

    own = probe.get(f"/probe/student/{alice}", headers={"X-Student-Id": str(alice)})
    assert own.status_code == 200
    assert own.json() == {"student_id": alice, "requester": alice}


def test_require_scope_is_a_pure_gate(engine):
    """直接调 :func:`require_scope`：匹配时不抛、不匹配时抛 ``HTTPException(403)``。

    **三支**，不是一支：

    * 匹配 → 返回 ``None``（不抛）。断言 ``is None``：闸门不该回一个「通过了」的对象，
      否则调用方会开始依赖它的返回值。
    * 不匹配 → 403。
    * ``requester_id`` 在 ``student`` 表里查无此人 → **同样 403**。这一支是 ``session``
      参数存在的理由，也是本函数与「只比对两个整数」的区别：没有它，
      ``X-Student-Id: 999999`` 会被放行到端点里、只靠下游的 404 兜底。
      ⚠️ 报 403 而不是 404：区分「行不存在」与「你不是它的主人」等于把
      「哪些 id 在册」告诉调用方。

    「pure gate」的准确含义是**只判定、不改状态**（不 commit、不写库、不缓存），
    不是「不碰数据库」——第三支要读一次 ``student``。
    """
    alice = _add_student(engine, "A2025001")
    bob = _add_student(engine, "B2025002")

    with Session(engine) as session:
        assert require_scope(session, alice, alice) is None

        with pytest.raises(HTTPException) as mismatched:
            require_scope(session, bob, alice)
        assert mismatched.value.status_code == 403

        with pytest.raises(HTTPException) as fabricated:
            require_scope(session, 999999, 999999)
        assert fabricated.value.status_code == 403


def test_a_non_integer_identity_header_is_422(probe):
    """``X-Student-Id: abc`` → 422，且用的是**统一错误形状**、不是 FastAPI 的缺省形状。

    这是 :mod:`app.api.deps` 与 :mod:`app.api.errors` 的接缝：``current_student`` 把
    ``x_student_id`` 标注成 ``int | None``，于是非整数值在**进函数之前**就被 FastAPI 的
    请求校验拦下、抛 ``RequestValidationError``。``errors.py`` 为它注册了处理器，
    把它折进 ``{"error": {...}}``；没有那个处理器的话，422 会有两种形状
    （缺省的 ``{"detail": [...]}`` 与统一的 ``{"error": {...}}``），
    而 422 恰恰是 CRUD API 最常见的那一类错误。

    ⚠️ 口径说明：伪造身份报的是 **422 而不是 401**。这是「``int | None`` 标注」的直接
    后果，也是计划 Interfaces 一节写下的签名。它不构成漏洞（两种码都拒绝访问），
    但前端要知道「头格式错」与「没有头」是两个码。
    """
    got = probe.get("/probe/student/1", headers={"X-Student-Id": "not-an-int"})
    assert got.status_code == 422
    body = got.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "request_validation_failed"
    # FastAPI 缺省形状里那份结构化的错误清单不丢，只是搬进了 detail（故它是 Any 而不是 str）
    assert isinstance(body["error"]["detail"], list)
    assert body["error"]["detail"]


def test_page_caps_limit_at_two_hundred(probe):
    """``Page`` 的三条边界，**以及**它作为 FastAPI 依赖时框架确实执行了同一套边界。

    分两段是因为它们守的是两件事：

    ① 模型自身的字段约束（``limit`` 缺省 50 / 上界 200 / 下界 1，``offset`` 缺省 0 /
       下界 0）。字面期望值一律写死在这里（硬规矩 #35：不从 ``Page.model_fields``
       读回来跟自己比）。
    ② **``Page`` 真的能当依赖用**（``page: Page = Depends()``）。这一段是承重的：
       Pydantic 模型作为依赖是 FastAPI 的一个特性，而 Task 3 的 ``build_crud_router``
       要给 23 个资源各挂一个 ``Page``——如果这个用法在本机的 FastAPI 0.141.1 上不成立，
       红在这里比红在 Task 3 便宜得多。探针路由由 ``_install_probes`` 提供。
    """
    assert (Page().limit, Page().offset) == (50, 0)
    assert Page(limit=200, offset=0).limit == 200
    for bad in ({"limit": 201}, {"limit": 0}, {"offset": -1}):
        with pytest.raises(ValidationError):
            Page(**bad)

    ok = probe.get("/probe/page", params={"limit": 10, "offset": 20})
    assert ok.status_code == 200
    assert ok.json() == {"limit": 10, "offset": 20}

    over = probe.get("/probe/page", params={"limit": 201})
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "request_validation_failed"

    default = probe.get("/probe/page")
    assert default.json() == {"limit": 50, "offset": 0}
