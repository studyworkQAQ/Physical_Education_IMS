"""``app.main`` 的应用工厂、``/api/health`` 与 ``app.api.errors`` 的异常映射。

**为什么错误映射的测试住在这里、而不是 ``tests/api/test_errors.py``**：被测的对象是
``create_app`` 的**接线**（``register_error_handlers(app)`` 有没有被调、调完是不是真生效），
不是 ``errors.py`` 里某个函数的返回值。而接线只能在「一个真的 ASGI 应用 + 一次真的请求」
上验——那正是本文件的夹具已经在做的事。计划 File Structure 的测试清单里也没有
``test_errors.py``。

**每条映射的探针都是现场加的路由**（``@app.get("/probe/…")``）：``create_app`` 今天只有
``/api/health`` 一个端点，而它一个异常都不抛。要让 ``ValueError`` / ``IntegrityError`` /
``NoResultFound`` / ``RuntimeError`` 真的从端点里飞出来，就得有会抛它们的端点。
在测试里往 ``app`` 上加路由是安全的：Starlette 的路由表是**每次请求现查**的，
故 ``TestClient`` 已经 ``__enter__`` 过（lifespan 已跑完）之后再加也照样生效。

⚠️ **本文件不断言 ``backend/pe.db`` 存在与否**。``tests/test_config.py`` 的模块 docstring
已经把这条口径定死了：「它是运行期状态，且把它写进测试会让『跑过 CLI 的机器上测试变红』
这种与配置无关的失败混进来」。本文件断言的是它的**两个可测的替身**：注入的 ``db_url``
确实被用上了（那个文件真的出现在 ``tmp_path`` 里）、以及工厂期**一条连接都没开**
（``engine.pool.checkedout() == 0``）。
"""
import datetime as dt
import importlib

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import DEFAULT_DB_URL
from app.db.models.organisation import Student
from app.db.session import init_db
from app.main import DB_URL_ENV_VAR, DEMO_DB_URL, create_app


@pytest.fixture()
def app():
    """内存库上的应用（与 ``tests/api/conftest.py`` 同形状；两份刻意不合并，理由见那份）。"""
    return create_app(db_url="sqlite://")


@pytest.fixture()
def client(app) -> TestClient:
    init_db(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client


def _student(student_no: str) -> Student:
    return Student(
        student_no=student_no,
        name=student_no,
        sex="male",
        birth=dt.date(2005, 1, 1),
        department=None,
        grade=1,
    )


# ---------------------------------------------------------------------------
# 计划 Step 1 点名的三条
# ---------------------------------------------------------------------------


def test_health_reports_the_table_count(client):
    """``GET /api/health`` → ``{"status": "ok", "tables": 25, "students": 0}``。

    ``tables == 25`` **字面写死**（硬规矩 #35）：它是 Plan 03 Task 2 结案时的表数
    （Plan 02 结案是 18，Task 2 一次加了反馈三源 4 张 + 预警/通知 2 张 + 班级周报 1 张）。
    从 ``len(Base.metadata.tables)`` 读回来跟自己比是同源断言，它证明不了
    「25 张表都注册进来了」，只证明「metadata 与自己一致」。
    ⚠️ 再加表时的同步清单归 ``tests/db/test_models.py::test_all_twenty_five_tables_created``
    的那段注释（它的第 ④ 格点了本文件这两处）。

    ``students == 0`` 也是字面量：内存库刚建完表、一行都没有。它顺带证明
    ``health`` 真的执行了一次查询——``tables`` 是 schema 层面的、不碰库，
    单看它证明不了「连上了正确的库」。
    """
    got = client.get("/api/health")
    assert got.status_code == 200
    assert got.json() == {"status": "ok", "tables": 25, "students": 0}


def test_create_app_accepts_an_injected_db_url(tmp_path):
    """``db_url`` 是被**真用**的，不是存下来给人看的。

    三段递进，缺一不可：

    ① 引擎的 URL 就是注入的那一个，且不等于 ``DEFAULT_DB_URL``（后者指向禁区的
      ``backend/pe.db``）；
    ② 工厂期**一条连接都没开**——``create_engine`` 是惰性的，这是「``import app.main``
      不会建出 ``pe.db``」的全部依据；
    ③ 真的跑一次请求之后，``tmp_path`` 下**出现了那个文件**。没有这一段，
      ①② 只能证明「URL 字符串被存下来了」。

    ⚠️ **比 URL 要用 :func:`sqlalchemy.engine.make_url`、不能比 ``str(engine.url)``**
    （本 Task 的 fix round 1 撞上的）：Windows 上 ``str()`` 会把盘符里的 ``:`` 百分号编码，
    ``str(make_url("sqlite:///C:/x.db"))`` 给出的是 ``sqlite:///C%3A/x.db``。
    于是「注入的 URL == 期望值」与「注入的 URL != DEFAULT_DB_URL」这两条**在字符串口径下
    都会因为编码差异而给出错误的答案**——第二条更阴：它恒真，故它证明的不是
    「没有落到缺省库」，而只是「盘符被编码了」。``URL.__eq__`` 比的是解析后的各段，
    不受渲染方式影响。
    """
    target = tmp_path / "injected.db"
    url = "sqlite:///" + target.as_posix()
    application = create_app(db_url=url)

    assert application.state.engine.url == make_url(url)
    assert application.state.engine.url != make_url(DEFAULT_DB_URL)
    assert application.state.engine.pool.checkedout() == 0

    init_db(application.state.engine)
    with TestClient(application) as test_client:
        assert test_client.get("/api/health").json()["tables"] == 25

    assert target.is_file(), "注入的 db_url 没有被真正使用"


def test_openapi_schema_is_generable(client):
    """``/openapi.json`` 生成得出来，且 ``paths`` 里有 ``/api/health``。

    计划把这一条称为「**系统能跑起来的最小可执行判据**」：OpenAPI schema 要把全部路由的
    签名、依赖与响应模型**求值一遍**才能生成，故任何一个依赖写错（``Depends`` 里塞了
    不可调用的东西、``Header`` 的标注 FastAPI 解析不了、Pydantic 模型当依赖用不成立）
    都会在这里炸，而不是等到浏览器打开 ``/docs`` 的时候。
    """
    got = client.get("/openapi.json")
    assert got.status_code == 200
    body = got.json()
    assert "/api/health" in body["paths"]
    assert "get" in body["paths"]["/api/health"]


# ---------------------------------------------------------------------------
# 缺省 URL 的解析：``db_url`` > ``PE_DB_URL`` > ``DEFAULT_DB_URL``
# ---------------------------------------------------------------------------


def test_module_level_app_uses_the_default_url_without_opening_it(monkeypatch):
    """``import app.main`` 建出的那个模块级 ``app`` 绑在 ``DEFAULT_DB_URL`` 上、且没打开它。

    这一条守的是本 Task **最容易破的那个禁区**：``app = create_app()`` 是
    ``uvicorn app.main:app`` 的入口，而 ``DEFAULT_DB_URL`` 逐字是
    ``sqlite:///<backend>/pe.db``（``tests/test_config.py`` 用字面后缀钉住了这一点）。
    如果 ``create_app`` 在工厂期就连接（例如把 ``init_db`` 从 lifespan 提到工厂体里），
    那么**光是收集本文件**就会在仓库里建出 ``backend/pe.db``。
    ``pool.checkedout() == 0`` 是这件事的可测替身（见模块 docstring 末尾那条 ⚠️）。

    ⚠️ ``monkeypatch.delenv`` + ``importlib.reload``：``app.main`` 在本文件顶部就已经被
    import 过了（要拿 ``DB_URL_ENV_VAR`` / ``DEMO_DB_URL`` / ``create_app``），
    故模块级的 ``app = create_app()`` **早在夹具生效之前**就执行完了——单写
    ``import app.main`` 只会从 ``sys.modules`` 拿回那个旧对象，环境变量删不删都一样，
    测试会变成「碰巧环境里没有 ``PE_DB_URL``」才绿。``reload`` 把模块体**重新执行一遍**，
    于是它验的正是「在受控环境下执行那句模块级语句」这件事本身。
    """
    monkeypatch.delenv(DB_URL_ENV_VAR, raising=False)
    import app.main

    reloaded = importlib.reload(app.main)

    assert reloaded.app.state.engine.url == make_url(DEFAULT_DB_URL)
    assert reloaded.app.state.engine.pool.checkedout() == 0


def test_pe_db_url_env_var_overrides_the_default(monkeypatch, tmp_path):
    """``PE_DB_URL`` 在环境里时优先于 ``DEFAULT_DB_URL``。

    **为什么需要这个覆盖口子**（本 Task 顶回派单的一处，报告里也记了）：计划 Step 4 的命令
    是 ``python -m uvicorn app.main:app --port 8000``，而它加载的是**模块级**的 ``app``——
    那个对象由 ``create_app()`` 无参建出，命令行上没有任何位置能塞 ``db_url``。
    于是要么让它落到 ``DEFAULT_DB_URL``（= 建出禁区的 ``backend/pe.db``），
    要么给工厂一个不经过函数参数的入口。环境变量是这两者之间唯一的解。
    有了它，Step 4 的命令**逐字不变**、库落在 ``pe_demo.db``。

    ``DEMO_DB_URL`` 也在这里一并钉住：它是「手工演示用哪个库」的唯一所有者，
    文件名必须是 ``pe_demo.db`` 而**不是** ``pe.db``——两个名字差四个字符，
    而错的那一个是禁区。
    """
    target = tmp_path / "override.db"
    monkeypatch.setenv(DB_URL_ENV_VAR, "sqlite:///" + target.as_posix())
    application = create_app()

    assert application.state.engine.url == make_url("sqlite:///" + target.as_posix())
    assert application.state.engine.url != make_url(DEFAULT_DB_URL)

    init_db(application.state.engine)
    with TestClient(application) as test_client:
        assert test_client.get("/api/health").status_code == 200
    assert target.is_file()

    assert DEMO_DB_URL.endswith("/backend/pe_demo.db")
    assert not DEMO_DB_URL.endswith("/backend/pe.db")


# ---------------------------------------------------------------------------
# 异常映射（app.api.errors）
# ---------------------------------------------------------------------------


def test_domain_value_error_maps_to_422(app, client):
    """domain 与加载器抛的 ``ValueError`` → 422，**且带上消息原文**。

    带原文是计划的显式决定：那些消息逐字写明了「哪个键、哪个文件、期望什么」
    （Plan 02 的模板 YAML 校验、Plan 03 Task 6 的 ``alert_rules.yaml`` 校验都是这个形状），
    抹掉它等于让前端只看到「参数不对」。故本条断言的是**整份响应体**、不是状态码。
    """

    @app.get("/probe/value-error")
    def _boom():
        raise ValueError("alert_rules.yaml 缺少键 version")

    got = client.get("/probe/value-error")
    assert got.status_code == 422
    assert got.json() == {
        "error": {
            "code": "unprocessable_value",
            "message": "alert_rules.yaml 缺少键 version",
            "detail": None,
        }
    }


def test_integrity_error_maps_to_409(app, client):
    """``IntegrityError`` → 409，消息取 ``exc.orig``（DBAPI 原文）而**不是** ``str(exc)``。

    探针造的是一次**真的**唯一约束冲突（两个学生同一个 ``student_no``），
    不是手工拼一个 ``IntegrityError`` 出来：手工拼的话，测的只是「处理器会不会读
    ``exc.orig``」，而真的冲突才顺带证明「端点里 ``commit()`` 抛出来的异常
    确实能飞到处理器」（中间隔着 ``get_db`` 那个生成器依赖的 ``finally``）。

    ⚠️ ``str(exc)`` 里带**完整 SQL 与绑定参数**，回给前端等于把 schema 和数据一起送出去。
    故断言里同时要求：DBAPI 的那句原文在（对前端有用），而 ``INSERT INTO`` 不在。
    """

    @app.post("/probe/duplicate")
    def _boom(session: Session = Depends(get_db)):
        session.add(_student("DUP2025001"))
        session.add(_student("DUP2025001"))
        session.commit()
        return "unreachable"

    got = client.post("/probe/duplicate")
    assert got.status_code == 409
    body = got.json()
    assert body["error"]["code"] == "integrity_conflict"
    assert "UNIQUE constraint failed" in body["error"]["message"]
    assert body["error"]["detail"] is None
    assert "INSERT INTO" not in got.text
    assert "Traceback" not in got.text


def test_no_result_found_maps_to_404(app, client):
    """``NoResultFound`` → 404。

    ``scalar_one()`` 查不到行时抛的就是它。Task 3 的 ``build_crud_router`` 读单个资源
    用的正是 ``scalar_one()``，故这条映射是它 404 的唯一来源。
    """

    @app.get("/probe/missing")
    def _boom(session: Session = Depends(get_db)):
        return session.execute(select(Student).where(Student.id == 424243)).scalar_one()

    got = client.get("/probe/missing")
    assert got.status_code == 404
    body = got.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["detail"] is None
    assert body["error"]["message"]


def test_unhandled_exception_maps_to_500_without_leaking_the_stack(app):
    """其余异常 → 500，且响应体里**既没有堆栈也没有异常消息**。

    ⚠️ 本条自建一个 ``raise_server_exceptions=False`` 的 ``TestClient``：缺省的 ``True``
    会把异常**再抛给调用方**（Starlette 的 ``ServerErrorMiddleware`` 发完响应总要
    ``raise exc``），于是测试撞上去的是那个 ``RuntimeError`` 而不是 500 响应体。
    ``client`` 夹具保持 ``True`` 是有意的——端点里真出了 bug 时，测试要看到堆栈。

    探针的消息里刻意塞了一个像连接串的片段：``"pe.db" not in got.text`` 因此不只是
    「没有堆栈」，还是「没有把内部配置回给前端」。
    """

    @app.get("/probe/boom")
    def _boom():
        raise RuntimeError("内部细节：连接串 sqlite:///C:/secret/pe.db")

    init_db(app.state.engine)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        got = test_client.get("/probe/boom")

    assert got.status_code == 500
    assert got.json() == {
        "error": {"code": "internal_error", "message": "服务器内部错误", "detail": None}
    }
    for leaked in ("RuntimeError", "Traceback", "pe.db", "secret"):
        assert leaked not in got.text


def test_the_catch_all_handler_does_not_swallow_http_exceptions(client):
    """兜底的 ``Exception`` 处理器不得把 ``HTTPException`` 也吞成 500。

    这一条是**红绿对照里的那半边**：``register_error_handlers`` 一共注册 6 个处理器，
    其中最宽的 ``Exception`` 排在最后。Starlette 的两层中间件（``ExceptionMiddleware``
    管具体类、``ServerErrorMiddleware`` 管 ``Exception``）本该保证窄的先命中，
    但那是框架的性质、不是本仓的性质——路由不存在时的 404 是最容易验的一格：
    Starlette 的 ``Router.not_found`` 抛的正是 ``HTTPException(404)``，
    它必须走 ``errors.py`` 为 ``HTTPException`` 注册的那个处理器、拿到统一形状，
    而不是被兜底处理器变成 500。
    """
    got = client.get("/api/definitely-not-a-route")
    assert got.status_code == 404
    assert got.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "detail": None,
        }
    }
