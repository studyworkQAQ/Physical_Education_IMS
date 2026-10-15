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
import json
import logging

import pytest
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.main as main_module
from app.api.deps import allow_header_identity, get_db
from app.auth.sessions import cookie_kwargs, cookie_secure
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
    """``GET /api/health`` → ``{"status": "ok", "tables": 28, "students": 0, "trial": false}``。

    ``tables == 28`` **字面写死**（硬规矩 #35）：它是 **Plan 06 Task 5** 结案时的表数
    （Plan 05A Task 1 结案时是 26，Task 3 加了 ``login_attempt`` 一张；
    Plan 03 Task 2 结案时是 25，Plan 05A 加了 ``user_session`` 一张）
    （Plan 02 结案是 18，Task 2 一次加了反馈三源 4 张 + 预警/通知 2 张 + 班级周报 1 张）。
    从 ``len(Base.metadata.tables)`` 读回来跟自己比是同源断言，它证明不了
    「28 张表都注册进来了」，只证明「metadata 与自己一致」。
    ⚠️ 再加表时的同步清单归 ``tests/db/test_models.py::test_all_twenty_eight_tables_created``
    的那段注释（它的第 ④ 格点了本文件这两处）。

    ⚠️ **本响应体刻意不含「当前部署档位」一类的运行时事实**（Plan 06 Task 4 的派单第 5 条）：
    ``/api/health`` 是**匿名**可读的，把 ``PE_ENV`` 的值回给匿名等于告诉探测者
    「这是一个 dev 档（CORS 全开、请求头身份可用）」——那是他要挑的那一个目标。
    故 ``PE_ENV`` / ``PE_CORS_ORIGINS`` / ``PE_ALLOW_HEADER_IDENTITY`` 一格都不回。
    守卫是 ``tests/test_main.py`` 的
    ``test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller``。

    ⚠️⚠️ **而第四格 ``trial`` 是 Plan 07 Task 1 加的、它不违反上述那一条**：
    ``PE_TRIAL`` 与 ``PE_ENV`` **正交**（试用档今天就是 ``PE_ENV=dev`` + ``PE_TRIAL=1``），
    而它答的那件事**本来就印在每一个页面上**（``frontend/src/App.vue`` 的那条告示，
    16 条路由都看得见），故它不是秘密。⚠️ 它是本响应体里**唯一**一格运行时事实，
    钉它的是 ``test_the_trial_cell_is_the_only_runtime_fact_health_discloses``
    （那一条同时钉住「三格数字在两档 ``PE_TRIAL`` 下逐字节相同」）。

    ``students == 0`` 也是字面量：内存库刚建完表、一行都没有。它顺带证明
    ``health`` 真的执行了一次查询——``tables`` 是 schema 层面的、不碰库，
    单看它证明不了「连上了正确的库」。
    """
    got = client.get("/api/health")
    assert got.status_code == 200
    # ⚠️ ``trial`` 是 Plan 07 Task 1 加的第四格。⚠️ 本条**不**设 ``PE_TRIAL``
    #    （``tests/conftest.py`` 也不设它），故期望侧是字面量 ``False``；
    #    「设了会怎样」那一半住在下面那两条新守卫里（硬规矩 #50：红绿两侧都要在场）。
    assert got.json() == {"status": "ok", "tables": 28, "students": 0, "trial": False}


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
        assert test_client.get("/api/health").json()["tables"] == 28

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
# ---------------------------------------------------------------------------
# Plan 06 Task 4：生产档配置与启动自检
# ---------------------------------------------------------------------------
#
# ⚠️ 分工：**纯值**（``PE_ENV`` 怎么解析、``PE_CORS_ORIGINS`` 怎么切）在
# ``tests/test_deploy.py``；**请求头身份通道在 prod 下被强制关**的 HTTP 那一半在
# ``tests/api/test_auth_api.py``（它要实发一次带伪造请求头的匿名请求）；
# 本段钉的是**装配与自检**——即 ``create_app`` 拿档位做了什么、以及它什么时候
# ``raise``。三份刻意不合并（与 ``tests/auth/`` ↔ ``tests/api/`` 的分工同一条口径）。


@pytest.fixture()
def prod_env(monkeypatch):
    """把进程切到生产档，且 ``PE_CORS_ORIGINS`` **未设**（= 同源部署那一档）。"""
    monkeypatch.setenv("PE_ENV", "prod")
    monkeypatch.delenv("PE_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("PE_ALLOW_HEADER_IDENTITY", raising=False)
    return monkeypatch


def _cors_entries(application):
    """这个应用上挂着的 ``CORSMiddleware`` 条目（可能一个都没有）。

    ⚠️ 判据是 ``entry.cls is CORSMiddleware`` 而**不是** ``str(entry)``：
    Starlette 的 ``Middleware`` 对象带 ``.cls`` / ``.args`` / ``.kwargs`` 三格
    （实测 starlette 1.7.0），故「挂了什么」与「用什么参数挂的」都能直接读出来。
    :func:`app.main._selfcheck_prod` 用的是同一套判据——两侧同源在这里是**要的**
    （自检与守卫看同一个东西，才不会出现「自检绿而守卫红」）。
    """
    return [entry for entry in application.user_middleware
            if entry.cls is CORSMiddleware]


def _lower_headers(response):
    return {key.lower() for key in response.headers}


def test_the_dev_tier_still_mounts_the_wildcard_cors_and_no_secure_cookie(monkeypatch):
    """**派单 §2 第 4 格的后半句**：``dev`` 下行为**一个字都没变**（既有 1370 条的前提）。

    四拍：

    1. 挂着**恰好一个** ``CORSMiddleware``，且 ``allow_origins == ["*"]``
       （改前的硬编码值，逐字保留）；
    2. ``allow_credentials`` 仍是 Starlette 的缺省 ``False``
       （``"*"`` 与 ``allow_credentials=True`` 在 CORS 规范里互斥）；
    3. ``cookie_secure()`` 是 ``False``（原型跑在明文 HTTP 上，带 ``Secure`` 的 cookie
       **根本不会被浏览器存下来**）；
    4. ⚠️ **实发一次带 ``Origin`` 的请求**：``access-control-allow-origin: *`` 真的回来了。
       少了这一拍，「中间件挂上了、而参数写错了」是绿的。
    """
    monkeypatch.delenv("PE_ENV", raising=False)
    monkeypatch.delenv("PE_CORS_ORIGINS", raising=False)
    application = create_app(db_url="sqlite://")

    entries = _cors_entries(application)
    assert len(entries) == 1, application.user_middleware
    assert entries[0].kwargs["allow_origins"] == ["*"]
    assert entries[0].kwargs.get("allow_credentials", False) is False
    assert cookie_secure() is False
    assert cookie_kwargs("T")["secure"] is False

    init_db(application.state.engine)
    with TestClient(application) as test_client:
        got = test_client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert got.status_code == 200
    assert got.headers["access-control-allow-origin"] == "*"


def test_prod_without_a_whitelist_mounts_no_cors_middleware_at_all(prod_env):
    """**派单 §2 第 2 格**：``prod`` + 白名单为空 → **一个 CORSMiddleware 都不挂**。

    ⚠️ 计划 §4 逐字要求的是「**缺省空 = 不挂 CORSMiddleware**（即拒绝跨域）」，
    而不是「挂一个空白名单」。两者在浏览器上行为相同（都不回
    ``Access-Control-Allow-Origin``），但「不挂」在 ``user_middleware`` 上**看得见**，
    于是本条与 :func:`app.main._selfcheck_prod` 都能直接数它。
    ⚠️ 第 3 拍是承重的：**实发一次带 ``Origin`` 的跨源请求**，断言响应里
    ``access-control-allow-origin`` **不出现**（= 浏览器会拦下它）。
    只数中间件的话，「挂了、但白名单是空的」与「没挂」在颜色上无法区分。
    ⚠️ 注意响应仍然是 **200**：CORS 是**浏览器**的机制，服务端照常应答；
    「拒绝跨域」的含义是「不给浏览器那个许可头」，不是「回一个 4xx」。
    """
    application = create_app(db_url="sqlite://")
    assert _cors_entries(application) == [], application.user_middleware

    init_db(application.state.engine)
    with TestClient(application) as test_client:
        got = test_client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert got.status_code == 200
    assert "access-control-allow-origin" not in _lower_headers(got)


def test_prod_with_a_whitelist_echoes_only_the_listed_origins(prod_env):
    """``prod`` + 白名单非空 → 只回显清单里的源，且带 ``allow-credentials``。

    三拍（红绿同时在场，硬规矩 #50）：

    1. **绿档**：清单里的源 → ``access-control-allow-origin`` 逐字回显它，
       且 ``access-control-allow-credentials: true``（不同源部署时浏览器要它，
       否则登录端点种下的 ``Set-Cookie`` 会被丢掉）；
    2. **红档**：清单外的源 → **一个 CORS 头都不给**；
    3. 装配层面：``allow_origins`` 就是那张清单、``allow_credentials`` 是 ``True``。
    """
    prod_env.setenv("PE_CORS_ORIGINS", "https://pe.xmu.edu.cn,https://admin.xmu.edu.cn")
    application = create_app(db_url="sqlite://")
    entries = _cors_entries(application)
    assert len(entries) == 1
    assert entries[0].kwargs["allow_origins"] == [
        "https://pe.xmu.edu.cn", "https://admin.xmu.edu.cn"
    ]
    assert entries[0].kwargs["allow_credentials"] is True

    init_db(application.state.engine)
    with TestClient(application) as test_client:
        listed = test_client.get("/api/health", headers={"Origin": "https://pe.xmu.edu.cn"})
        stranger = test_client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert listed.headers["access-control-allow-origin"] == "https://pe.xmu.edu.cn"
    assert listed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in _lower_headers(stranger)


def test_prod_with_a_wildcard_cors_whitelist_refuses_to_start(prod_env):
    """**自检第 1 格**：``PE_CORS_ORIGINS=*`` → ``create_app`` 当场 ``raise``。

    ⚠️ 这一条是自检**不是恒绿**的主要证据：它是一个**运维真的会犯的错**
    （图省事写一个星号），而它的正确处置是「服务起不来」，
    不是「静默地把生产档变成 CORS 全开」。
    ⚠️ 报错必须点名 ``PE_CORS_ORIGINS``（运维要能一眼看出改哪个变量），
    并且**明写「不设它」是合法的那一档**（同源部署要的正是「不挂 CORS」，
    而一个只说「不许写星号」的报错会把人引向「那我写 localhost:5173 吧」）。
    """
    prod_env.setenv("PE_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError) as excinfo:
        create_app(db_url="sqlite://")
    message = str(excinfo.value)
    assert "PE_CORS_ORIGINS" in message, message
    assert "*" in message, message
    assert "PE_ENV" in message, message

    # 混在清单里的一个星号同样响（不是「只写一个星号才拦」）
    prod_env.setenv("PE_CORS_ORIGINS", "https://pe.xmu.edu.cn,*")
    with pytest.raises(RuntimeError):
        create_app(db_url="sqlite://")


def test_the_selfcheck_raises_when_the_secure_cookie_is_off_in_prod(prod_env):
    """**自检第 2 格（定点变异）**：把 ``cookie_secure`` 改假 → ``create_app`` 当场 ``raise``。

    ⚠️ 这一格在**构造上**不可能为假（``cookie_secure()`` 就是 ``deploy.is_prod()``，
    而自检只在 prod 下跑），故它必须靠**变异**来证明有牙——否则它就是一条恒绿的装饰。
    变异的打点是 ``app.main.cookie_secure``（那一处是
    ``from app.auth.sessions import cookie_secure``，故 :func:`app.main._selfcheck_prod`
    查的是本模块的命名空间）；打在 ``app.auth.sessions`` 上拦不到它。
    ⚠️ 它挡的是「有人把 ``cookie_secure`` 改成读别的变量」与「有人把 ``secure``
    那一格挪出 :func:`app.auth.sessions.cookie_kwargs`」两档——两档都是
    「生产上会话 cookie 不带 ``Secure``」= 可以在明文链路上被读走。
    """
    prod_env.setattr(main_module, "cookie_secure", lambda: False)
    with pytest.raises(RuntimeError) as excinfo:
        create_app(db_url="sqlite://")
    message = str(excinfo.value)
    assert "Secure" in message, message
    assert "cookie_secure" in message, message


def test_the_selfcheck_catches_a_wildcard_cors_mounted_behind_its_back(prod_env):
    """自检数的是**装配好的那个应用**：绕过 :func:`app.main._install_cors` 也抓得到。

    ⚠️ 这一条钉的是自检的**判据来源**：它读 ``application.user_middleware``，
    而不是读「我打算挂什么」。一个只看意图的自检在下面这个变异下会**绿着放行**
    一个全开的 CORS——而那正是它存在的理由（:func:`app.main._selfcheck_prod`
    的 docstring 第二节）。
    ⚠️ 变异形状是真实的：下一个人给某个新端点加一个「临时放开跨域」的中间件时，
    最省事的写法就是在 ``create_app`` 里再 ``add_middleware`` 一次。
    """
    original = main_module._install_cors

    def sneaky(application):
        original(application)
        application.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )

    prod_env.setattr(main_module, "_install_cors", sneaky)
    with pytest.raises(RuntimeError) as excinfo:
        create_app(db_url="sqlite://")
    assert "allow_origins" in str(excinfo.value), str(excinfo.value)


def test_the_selfcheck_reports_every_offender_at_once(prod_env):
    """两格**一次报全**：一次启动失败只报一格的话，运维修完一格重启又撞第二格。"""
    prod_env.setenv("PE_CORS_ORIGINS", "*")
    prod_env.setattr(main_module, "cookie_secure", lambda: False)
    with pytest.raises(RuntimeError) as excinfo:
        create_app(db_url="sqlite://")
    message = str(excinfo.value)
    assert "PE_CORS_ORIGINS" in message and "Secure" in message, message
    assert message.count("\n  - ") == 2, message


def test_the_selfcheck_is_a_no_op_in_the_dev_tier(monkeypatch):
    """``dev`` 下自检**什么也不做**（它连 ``user_middleware`` 都不数）。

    ⚠️ 这一条是「dev 下 1370 条一条都不许红」的**局部**证据：dev 档挂着
    ``allow_origins=["*"]``，而自检若不分档就会让**每一条**建应用的测试当场 raise。
    """
    monkeypatch.delenv("PE_ENV", raising=False)
    application = create_app(db_url="sqlite://")
    assert _cors_entries(application)[0].kwargs["allow_origins"] == ["*"]
    main_module._selfcheck_prod(application)      # 不抛


def test_an_unrecognised_tier_refuses_to_build_an_app(monkeypatch):
    """坏的 ``PE_ENV`` 让 ``create_app`` 抛 ``ValueError``——故 ``import app.main`` 也抛。

    ⚠️ **这一条是「服务起不来」那个失效方向的落点**：``app.main`` 有一条模块级的
    ``app = create_app()``，故 ``uvicorn app.main:app`` 在一个坏 ``PE_ENV`` 下
    根本起不来，报错是 ``ValueError: PE_ENV 只能是 …``（而不是一个
    看起来在跑的 dev 档服务）。
    """
    monkeypatch.setenv("PE_ENV", "productionn")
    with pytest.raises(ValueError) as excinfo:
        create_app(db_url="sqlite://")
    assert "PE_ENV" in str(excinfo.value)


def test_the_production_tier_holds_all_three_documented_properties_at_once(prod_env):
    """**派单 §2 第 4 格点名的那一条**：``prod`` 下三格 + 自检，一次断完。

    三格逐个（计划 §4 的原文）：① CORS 从 ``*`` 改成读 ``PE_CORS_ORIGINS``、
    缺省空 = 不挂；② cookie 的 ``Secure`` 仅 prod 开；③ ``PE_ALLOW_HEADER_IDENTITY``
    在 prod 下**强制 0**（读到 1 也忽略）。第四格是自检本身。
    ⚠️ 本条**刻意把 ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``1``**：三格里第三格的全部
    意义就在「设了也忽略」，而不设它的话本条对那一格是空转的。
    ⚠️ 第 ⑤ 拍是自检的**牙**（把 ② 改假 → 当场 raise），故本条不是恒绿的。
    """
    prod_env.setenv("PE_ALLOW_HEADER_IDENTITY", "1")

    application = create_app(db_url="sqlite://")

    # ① CORS：白名单未设 → 一个 CORSMiddleware 都不挂（绝不是 *）
    assert _cors_entries(application) == []
    # ② cookie 的 Secure 开着（05A 既有；Task 4 核实它真的是「仅 prod」）
    assert cookie_secure() is True
    assert cookie_kwargs("T")["secure"] is True
    # ③ 请求头身份通道**强制关**（环境变量明明是 1）
    assert allow_header_identity() is False
    # ④ 自检在这一份配置上**不响**（绿档同时在场，硬规矩 #50）
    main_module._selfcheck_prod(application)
    # ⑤ 而它确实有牙
    prod_env.setattr(main_module, "cookie_secure", lambda: False)
    with pytest.raises(RuntimeError):
        main_module._selfcheck_prod(application)


def test_prod_logs_exactly_one_warning_when_the_header_identity_switch_is_set(
        prod_env, caplog):
    """**派单 §2 第 2 格第三项的后半句**：读到 ``1`` 也忽略，**并打一条 warning**。

    ⚠️ 「一次装配一条」是刻意的口径（:func:`app.main._warn_if_header_identity_was_requested_in_prod`
    的 docstring）：``「这个开关在生产上被设成了 1」``是一个**部署事实**、
    不是一个请求事实，逐请求打会把日志淹掉——而淹掉日志的后果正是那条 warning
    再也看不见。故本条建**两个**应用、断言**两条**记录（不是 1 条、也不是 0 条）。
    ⚠️ ``caplog`` 要显式 ``at_level``：``alembic.ini`` 的 ``[logger_root]`` 是
    ``WARNING``，而 pytest 的 ``caplog`` 缺省抓 ``WARNING`` 及以上，
    故这一行是**许可**而不是必需（写出来是为了让「本条要抓哪一级」这件事可读）。
    """
    prod_env.setenv("PE_ALLOW_HEADER_IDENTITY", "1")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        create_app(db_url="sqlite://")
        create_app(db_url="sqlite://")
    hits = [record for record in caplog.records
            if "PE_ALLOW_HEADER_IDENTITY" in record.getMessage()]
    assert len(hits) == 2, [record.getMessage() for record in caplog.records]
    assert all(record.levelno == logging.WARNING for record in hits)
    # ⚠️ 那条 warning 必须说清「它没有生效」，否则运维会以为通道是开的
    assert "忽略" in hits[0].getMessage()


def test_dev_logs_no_warning_about_the_header_identity_switch(monkeypatch, caplog):
    """``dev`` 下把那个开关设成 ``1`` **不打 warning**（它是那一档的正常使用方式）。

    ⚠️ 少了本条，「warning 无条件打」是绿的——而 ``tests/conftest.py`` 恰恰把
    ``PE_ALLOW_HEADER_IDENTITY`` 设成 ``"1"``（1370 条测试的前提），
    于是「无条件打」会让每一次建应用都往日志里塞一条与它无关的告警。
    """
    monkeypatch.delenv("PE_ENV", raising=False)
    monkeypatch.setenv("PE_ALLOW_HEADER_IDENTITY", "1")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        create_app(db_url="sqlite://")
    assert [record for record in caplog.records
            if "PE_ALLOW_HEADER_IDENTITY" in record.getMessage()] == []
    assert allow_header_identity() is True


def test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller(monkeypatch):
    """**派单 §2 第 5 格**：``/api/health`` 与 ``/openapi.json`` 对匿名**与档位无关**。

    ⚠️ 判据是「两档下**逐字节相同**」，而不是「响应体里搜不到某个词」。理由是实测的：
    FastAPI 会把**端点的 docstring** 渲染成 OpenAPI 的 operation ``description``，
    而 :func:`app.api.routers.auth.login` 的 docstring 里逐字写着
    ``PE_ENV=production`` / ``PE_LOGIN_MAX_FAILS`` 一类**机制名**——
    那些是产品文档、不是本实例的档位，搜词会把它们误判成泄漏，
    而下一个人「修」它的办法是删注释（硬规矩 #109 的形状）。
    ⚠️ **逐字节相同则一举封死**：若响应体在两档下一模一样，则它**按定义**
    不可能携带任何关于「本实例跑在哪一档」的信息。

    ⚠️ 另外两拍：① ``/api/health`` 的键集合是字面量四格（``status`` / ``tables`` /
    ``students`` / ``trial``），**没有**「当前部署档位」那一格；② 那份**实例相关**的
    配置值（``PE_CORS_ORIGINS`` 里写的域名）不出现在任何一份响应体里。

    ⚠️⚠️ **Plan 07 Task 1 把它加强了一格**：两档 ``PE_ENV`` 要在**同一个**
    ``PE_TRIAL`` 下比（本条一律 ``PE_TRIAL=1``）。⚠️ 而这一格是**承重**的：
    ``trial`` 那一格本身就随 ``PE_TRIAL`` 变，故若两侧 ``PE_TRIAL`` 不同，
    「逐字节相同」会**因为一个与档位无关的格子**而红 —— 而修它的人很可能
    顺手把 ``trial`` 从响应里删掉（于是页面告示静默失效）。设成同一个值之后，
    本条钉住的仍然**只有**「部署档位不泄漏」这一件事。
    ⚠️ 取 ``PE_TRIAL=1`` 而不是缺省：那一档下响应体里**真的有一格** ``"trial":true``，
    于是「两档 ``PE_ENV`` 逐字节相同」这句话是在**一个非平凡的响应体**上成立的
    （缺省档下它是 ``false``，而 ``false`` 与 ``false`` 相同这件事信息量更少）。
    """
    monkeypatch.delenv("PE_ENV", raising=False)
    monkeypatch.delenv("PE_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("PE_TRIAL", "1")
    dev = create_app(db_url="sqlite://")
    init_db(dev.state.engine)
    with TestClient(dev) as test_client:
        dev_health = test_client.get("/api/health").content
        dev_openapi = test_client.get("/openapi.json").content

    monkeypatch.setenv("PE_ENV", "prod")
    monkeypatch.setenv("PE_CORS_ORIGINS", "https://pe.xmu.edu.cn")
    prod = create_app(db_url="sqlite://")
    init_db(prod.state.engine)
    with TestClient(prod) as test_client:
        prod_health = test_client.get("/api/health").content
        prod_openapi = test_client.get("/openapi.json").content

    assert dev_health == prod_health, (dev_health, prod_health)
    assert dev_openapi == prod_openapi

    assert set(json.loads(dev_health)) == {"status", "tables", "students", "trial"}
    # ⚠️ 反空转：``PE_TRIAL=1`` 那一格**真的**是 ``true``（否则上面那句
    #    「逐字节相同」是在两个 ``false`` 上成立的，信息量少一半）。
    assert json.loads(dev_health)["trial"] is True, dev_health
    for body in (dev_health, dev_openapi):
        assert b"pe.xmu.edu.cn" not in body, body[:400]
    # ⚠️ 部署档位的**两个字面值**都不许出现在 ``/api/health`` 的响应体里
    #    （``trial`` 是布尔，不是档位名）。⚠️ 本拍**只打在 health 上、不打在 openapi 上**：
    #    端点的 docstring 会被 FastAPI 渲染成 ``description``，而那些 docstring 里
    #    **逐字提及**了 ``PE_ENV=prod`` 一类的机制名（本文件上面那条守卫的 docstring
    #    第一节记着这一格），搜词会假红；而 openapi 那一侧已经由「两档逐字节相同」封死。
    assert b'"dev"' not in dev_health and b'"prod"' not in dev_health, dev_health


# ---------------------------------------------------------------------------
# Plan 07 Task 1：``PE_TRIAL``（试用档）在 HTTP 那一层的三条守卫
#
# ⚠️ **纯值那一半住在 ``tests/test_deploy.py``**（``is_trial()`` 的取值域、
# 认不出的值抛、调用时读、与 ``tier()`` 正交）。本文件钉的是**接线**：
# ① 那一格真的出现在 ``/api/health`` 的响应体里、且**只有**它随开关变；
# ② ``/openapi.json`` **一个字节都不随它变**（而五格与「24 个未定型」被字面钉住）；
# ③ 一个认不出的 ``PE_TRIAL`` 让 ``create_app`` 抛 ⇒ 服务**起不来**。
# ---------------------------------------------------------------------------


def test_the_trial_cell_is_the_only_runtime_fact_health_discloses(client, monkeypatch):
    """``/api/health`` 的 ``trial`` 一格**随 ``PE_TRIAL`` 变**，而其余三格一个字节都不变。

    四拍（⚠️ 红绿两侧都在场，硬规矩 #50）：

    ① 缺省 → ``trial is False``（开发档与产品档因此**不挂**页面告示；
       那一半的运行时取证在 ``frontend/scripts/smoke.mjs`` 第 14 步）；
    ② ⚠️ **同一个 ``client``**、``setenv`` 之后立刻 → ``trial is True``：
       这一格钉的是「**请求时读**、不是装配时读一次并缓存」。⚠️ 它与
       ``tests/test_deploy.py`` 的 ``test_the_trial_switch_is_read_at_call_time…``
       各钉一半：那一条钉 :func:`app.deploy.is_trial` 这个**所有者**，
       本拍钉 ``health`` 这个**消费者**（若端点把值在装配期抄进一个闭包变量，
       那一条绿、本拍红）；
    ③ 其余三格（``status`` / ``tables`` / ``students``）在两档下**逐字相同**，
       且 ``trial`` 是**布尔**（不是 ``"1"`` / ``"true"`` 一类字符串——
       前端 ``App.vue`` 判的是 ``health.trial === true``）；
    ④ 认不出的值在**请求期也响亮**：422 ``unprocessable_value`` + 消息原文点名
       ``PE_TRIAL``。⚠️ 这一拍是 ③ 那一格（装配期抛）的**兜底**：
       若有人把装配期那一次调用删掉，坏值仍然不会静默变成 ``false``。
    """
    monkeypatch.delenv("PE_TRIAL", raising=False)
    off = client.get("/api/health")
    assert off.status_code == 200
    off_body = off.json()
    assert off_body["trial"] is False, off_body

    monkeypatch.setenv("PE_TRIAL", "1")
    on = client.get("/api/health")
    assert on.status_code == 200
    on_body = on.json()
    assert on_body["trial"] is True, on_body
    assert isinstance(on_body["trial"], bool), on_body

    def rest(body):
        """去掉 ``trial`` 那一格之后的三格（③ 那一拍要的就是「其余逐字相同」）。"""
        return {key: value for key, value in body.items() if key != "trial"}

    assert rest(on_body) == rest(off_body), (off_body, on_body)
    assert set(on_body) == {"status", "tables", "students", "trial"}, on_body

    monkeypatch.setenv("PE_TRIAL", "yes")
    bad = client.get("/api/health")
    assert bad.status_code == 422, bad.content
    payload = bad.json()["error"]
    assert payload["code"] == "unprocessable_value", payload
    assert "PE_TRIAL" in payload["message"], payload
    assert "yes" in payload["message"], payload


#: ``/openapi.json`` 的**五格**（Plan 07 Task 1 结案时的实测值）。
#: ⚠️ 字面量（硬规矩 #35）。⚠️ 其中「挂 security 的操作数 = 84」另有一个**所有者**
#: （``tests/api/test_prescription_api.py`` 的
#: ``test_the_identity_schemes_are_registered_as_openapi_security_schemes``，
#: 它把 84 拆成 26 特例 + 26 CRUD 写入 + 6 个仅教职读 + 26 个学生键读），
#: 本处刻意**不复述那个算式**（硬规矩 #111），只钉「试用档开关没有改它」。
OPENAPI_CELLS = {
    "paths": 74,
    "operations": 102,
    "with_security": 84,
    "get": 63,
    "get_anonymous": 15,
    "security_schemes": 3,
    #: 「24 个未定型响应」= 23 个泛型 list + ``/api/health``。
    #: ⚠️ 清单的**逐端点**住址是 ``frontend/src/api/types.ts`` 的文件头（本处不复述）。
    "untyped_200": 24,
}

#: ``/api/health`` 的 200 响应 schema 的**字面原文**。
#: ⚠️ 它就是「未定型」那一档：返回注解 ``dict[str, object]`` ⇒ FastAPI 渲染成
#: ``additionalProperties: true``。⚠️ 本处把它按字面钉住的意义是：
#: **给那个 dict 加一格不改 schema 一个字节** —— 故 ``trial`` 那一格是免费的，
#: 而「新开一个端点」不是（路径数与操作数各 +1，五格全要跟着改）。
HEALTH_UNTYPED_SCHEMA = {
    "additionalProperties": True,
    "title": "Response Health Api Health Get",
    "type": "object",
}

_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _openapi_bytes(monkeypatch, trial_value: "str | None") -> bytes:
    """在 ``PE_TRIAL`` = ``trial_value`` 下起一个应用、取 ``/openapi.json`` 的**响应体字节**。

    ⚠️ **每次都新建一个应用**（不复用一个实例调两次 ``app.openapi()``）：
    FastAPI 把结果缓存在 ``app.openapi_schema`` 上，复用会让「三份逐字节相同」
    变成一个**恒真**的断言（硬规矩 #50 的形状）。
    ⚠️ 走 HTTP 而不是 ``app.openapi()``：本条要钉的是**端点发出来的那份字节**
    （渲染口径由 ``starlette.responses.JSONResponse.render`` 决定），
    与 ``backend/scripts/dump_openapi.py`` 的
    ``test_the_offline_dump_is_byte_identical_to_the_http_endpoint`` 同一条口径。
    """
    monkeypatch.delenv("PE_TRIAL", raising=False)
    if trial_value is not None:
        monkeypatch.setenv("PE_TRIAL", trial_value)
    application = create_app(db_url="sqlite://")
    init_db(application.state.engine)
    with TestClient(application) as test_client:
        got = test_client.get("/openapi.json")
    assert got.status_code == 200
    return got.content


def test_the_trial_switch_never_touches_the_openapi_document(monkeypatch):
    """**常驻版的「openapi 不变」取证**：三档 ``PE_TRIAL`` 下逐字节相同 + 五格 + 24 个未定型。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它钉的是**性质**，不是一份 417 KB 的基线快照
    ------------------------------------------------------------------------
    实施计划 07 派单 §1.3 要的是「改前改后各 dump 一次、逐字节对比」。
    那一格的**一次性取证**住在实现者报告里（改前 417 032 B / 改后 420 367 B，
    摊平成 4520 个叶子之后**恰好 1 个**不同：``paths`` 里 ``/api/health`` 那一格的
    ``description``）。⚠️ 而它**不能**做成常驻守卫：FastAPI 把端点的 docstring
    渲染成 operation 的 ``description``，故任何一次对那段 docstring 的修改都会
    让「与快照逐字节相同」红 —— 而修它的人唯一的出路就是删掉说明文字
    （硬规矩 #109 的形状）。

    故本条钉的是三格**性质**（它们对 docstring 的措辞完全不敏感）：

    ① **三档 ``PE_TRIAL``（未设 / ``0`` / ``1``）下 ``/openapi.json`` 逐字节相同**
       ⇒ 「档位有没有落进契约面」这件事有一个会红的判据；⚠️ 姿势与既有的
       ``test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller``
       （dev vs prod 逐字节相同）与 ``tests/test_serve.py`` 的
       ``test_the_openapi_document_is_identical_with_and_without_the_spa`` 同款；
    ② **五格 + 「24 个未定型」按字面钉住**（:data:`OPENAPI_CELLS`）⇒
       「有人顺手加了一个端点」会红，并指路到那五个数；
    ③ **``/api/health`` 的响应 schema 逐字仍是 :data:`HEALTH_UNTYPED_SCHEMA`**
       ⇒ 它**仍然**是 24 个未定型之一，于是「给那个 dict 加一格是免费的」
       这句话有可执行的依据，而不是一句推断。
    """
    unset = _openapi_bytes(monkeypatch, None)
    off = _openapi_bytes(monkeypatch, "0")
    on = _openapi_bytes(monkeypatch, "1")
    assert unset == off == on, (len(unset), len(off), len(on))

    spec = json.loads(on)
    paths = spec["paths"]
    operations = [
        (path, method)
        for path, item in paths.items()
        for method in item
        if method.lower() in _HTTP_METHODS
    ]
    with_security = [pm for pm in operations if paths[pm[0]][pm[1]].get("security")]
    gets = [pm for pm in operations if pm[1] == "get"]
    get_anonymous = [pm for pm in gets if not paths[pm[0]][pm[1]].get("security")]
    schemes = spec.get("components", {}).get("securitySchemes", {})

    measured = {
        "paths": len(paths),
        "operations": len(operations),
        "with_security": len(with_security),
        "get": len(gets),
        "get_anonymous": len(get_anonymous),
        "security_schemes": len(schemes),
    }
    assert measured == {k: v for k, v in OPENAPI_CELLS.items() if k in measured}, measured

    # ③ 「未定型」的判据：200 响应的 schema 里既没有 ``$ref``、也没有
    #    ``items`` / ``properties`` / ``allOf`` / ``anyOf`` / ``oneOf``。
    #    ⚠️ 判据与 ``frontend/src/api/types.ts`` 文件头那一段「数法」逐字同款
    #    （那一段写的是「不含 $ref/oneOf/anyOf/allOf/items」；本处多收一个
    #    ``properties``，它只会让清单**更窄**，而实测两档给的都是 24）。
    shaped = ("$ref", "items", "properties", "allOf", "anyOf", "oneOf")
    untyped = []
    for path, method in operations:
        response = paths[path][method].get("responses", {}).get("200")
        if response is None:
            continue
        schema = response.get("content", {}).get("application/json", {}).get("schema", {})
        if not any(key in schema for key in shaped):
            untyped.append((path, method))
    assert len(untyped) == OPENAPI_CELLS["untyped_200"], untyped
    assert ("/api/health", "get") in untyped, untyped

    health_schema = (
        paths["/api/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    )
    assert health_schema == HEALTH_UNTYPED_SCHEMA, health_schema


def test_an_unrecognised_pe_trial_refuses_to_build_an_app(monkeypatch):
    """坏的 ``PE_TRIAL`` 让 ``create_app`` 抛 ``ValueError``——故 ``import app.main`` 也抛。

    ⚠️ 与 :func:`test_an_unrecognised_tier_refuses_to_build_an_app` **同一条姿势**，
    而同一条理由：``app.main`` 有一条模块级的 ``app = create_app()``，故
    ``uvicorn app.main:app`` 在一个坏 ``PE_TRIAL`` 下**根本起不来**。
    ⚠️ 失效方向因此是「起不来」，而**不是**「静默不挂告示」——后者会让甲方
    把真学生的体测数据敲进一份随时会被删掉重灌的仿真库（实施计划 07 §0 第 2 条）。
    ⚠️ 逐个点名测的三个值：``yes`` 是「以为它是个布尔词」、``2`` 是「以为它是个数字」、
    ``false`` 是**最吃紧的一档**（它**看起来**是「关」，而本仓只认 ``"0"``，
    故它抛而不是安静地当成关）。
    """
    for value in ("yes", "2", "false"):
        monkeypatch.setenv("PE_TRIAL", value)
        with pytest.raises(ValueError) as excinfo:
            create_app(db_url="sqlite://")
        message = str(excinfo.value)
        assert "PE_TRIAL" in message, (value, message)
        assert value in message, (value, message)
