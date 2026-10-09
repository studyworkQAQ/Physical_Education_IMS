"""FastAPI 应用工厂，以及 ``uvicorn app.main:app`` 的那个入口对象。

**本模块是整个项目第一次有 HTTP 层**（Plan 03 Task 1）：Plan 01/02 交付的是一个批处理
系统（``python -m app.pipeline.daily``），没有服务进程。本文件只做四件事：

1. 解析「用哪个库」——:func:`_resolve_db_url`；
2. 造引擎——:func:`_build_engine`（内存 SQLite 要换连接池，见该函数）；
3. 建表——在 **lifespan** 里，不在工厂体里（下面那条 ⚠️ 是本模块最要紧的一句）；
4. 装中间件、错误处理器、``/api/health``，返回 :class:`~fastapi.FastAPI`。

路由本体到 Task 3 才建（``app/api/routers/__init__.py``），届时 ``create_app`` 只
``include_router`` 那一个汇总路由。``/api/health`` **刻意留在本文件**：它是应用级的存活
探针、不是某个资源的 CRUD，而把它单独放进一个 router 意味着 Task 1 就要建出
``app/api/routers/`` 这个空包。

⚠️ **建表必须在 lifespan 里、不能在工厂体里**。``app = create_app()`` 是本模块的
模块级语句，故**光是 ``import app.main`` 就会执行它**；而 ``db_url`` 缺省时解析到
:data:`app.config.DEFAULT_DB_URL`，那个常量逐字指向 ``backend/pe.db``——本仓的**禁区**
（Global Constraints）。``create_engine`` 是惰性的（不连接、不建文件），
故工厂体里造引擎是安全的；而 ``init_db`` 会 ``create_all``、当场连接、
**当场建出那个文件**。把它挪进 lifespan 之后，「建库」这件事只在真的被 serve
（或测试显式调用）时发生。
``tests/test_main.py::test_module_level_app_uses_the_default_url_without_opening_it``
用 ``engine.pool.checkedout() == 0`` 把这条性质钉住。

**手工演示怎么跑**（计划 Step 4）::

    cd backend
    $env:PE_DB_URL = python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"
    python -m uvicorn app.main:app --port 8000

第二行把 :data:`DEMO_DB_URL` 读进环境变量，于是 lifespan 建的是 ``backend/pe_demo.db``
（已进 ``.gitignore``）而**不是** ``backend/pe.db``。
⚠️ 不设 ``PE_DB_URL`` 直接跑第三行，会在 ``backend/`` 下建出 ``pe.db``——
那就是破禁区。**这是本 Task 最容易踩的一脚**，故 :data:`DEMO_DB_URL` 与
:data:`DB_URL_ENV_VAR` 都有唯一所有者、且被测试钉住。

**CORS 是 ``allow_origins=["*"]``**：⚠️ **原型口径，上线前必须收紧**（计划的显式决定）。
Plan 04 的前端跑在 ``localhost:5173`` 的 Vite dev server 上，而演示要在同一台机器的
浏览器里点起来；把允许的源收窄成一张白名单是上线前的一步，不是现在的一步。
``allow_headers=["*"]`` 是必需的：``X-Student-Id`` / ``X-Teacher-Staff-No``
这两个自定义头会触发预检。``allow_credentials`` 保持 Starlette 的缺省 ``False``——
``"*"`` 与 ``allow_credentials=True`` 在 CORS 规范里互斥，而原型用请求头传身份、
不用 Cookie。

**刻意不做**（计划的显式决定，原型阶段它们是噪音）：OpenAPI 的 tag 分组美化、
响应模型的 ``exclude_none``、速率限制、请求日志中间件。
"""
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, func, make_url, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.errors import register_error_handlers
from app.config import BACKEND_DIR, DEFAULT_DB_URL
from app.db import models  # noqa: F401  仅为把 25 张表注册进 Base.metadata
from app.db.models.organisation import Student
from app.db.session import Base
from app.db.session import engine as build_engine
from app.db.session import init_db

__all__ = ["DB_URL_ENV_VAR", "DEMO_DB_URL", "create_app"]

#: 覆盖 :data:`app.config.DEFAULT_DB_URL` 的环境变量名。
#:
#: 存在的理由：``uvicorn app.main:app`` 加载的是**模块级**的 ``app``，
#: 它由 ``create_app()`` 无参建出，命令行上没有任何位置能塞 ``db_url``。
#: 没有这个口子，「跑一次 uvicorn」与「不建出禁区的 ``backend/pe.db``」二者不可兼得。
#: 优先级是 ``db_url`` 实参 > ``PE_DB_URL`` > ``DEFAULT_DB_URL``（:func:`_resolve_db_url`）。
#:
#: ⚠️ 这个覆盖**住在本模块、不住在 ``app.config``**：``config.py`` 是「进程级路径与 URL
#: 缺省值的唯一所有者」，它的模块 docstring 明写「只 import :mod:`pathlib`」、
#: 且它是全仓依赖图的叶子（任何一层都能安全 import 它而不可能造出环）。
#: 给它加一个 ``import os`` 会改掉那个性质，而 ``tests/test_config.py`` 用字面后缀钉住了
#: ``DEFAULT_DB_URL`` 的值——**那个值本身没变**，变的只是「本层如何在运行时覆盖它」。
DB_URL_ENV_VAR = "PE_DB_URL"

#: 手工演示用的磁盘库。**它是「演示库叫什么」的唯一所有者**，
#: PowerShell 里请用 ``python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"``
#: 把它读出来，不要在命令行里再敲一遍那个路径（敲第二遍就是第二个所有者）。
#:
#: ⚠️ **不是** ``backend/pe.db``。``pe.db`` 是禁区，它的语义是
#: 「``app.seed.generate`` 写出来的那份不可复现的库」（``tests/test_config.py`` 的
#: 模块 docstring）；``pe_demo.db`` 是本计划的 HTTP 层在 lifespan 里 ``create_all``
#: 出来的空库，两者不是一回事。文件名差四个字符，而错的那一个是禁区。
#: 已进 ``.gitignore``（连同 ``-journal`` / ``-wal`` / ``-shm``），故不会误入库。
DEMO_DB_URL: str = f"sqlite:///{(BACKEND_DIR / 'pe_demo.db').as_posix()}"


def _resolve_db_url(db_url: str | None) -> str:
    """``db_url`` 实参 > ``PE_DB_URL`` 环境变量 > :data:`app.config.DEFAULT_DB_URL`。

    空字符串按「没设」处理（``or``）：``$env:PE_DB_URL = ""`` 在 PowerShell 里是
    「设了一个空值」而不是「删掉这个变量」，而 ``create_engine("")`` 会抛
    ``ArgumentError``——在离真因很远的地方。
    """
    if db_url is not None:
        return db_url
    return os.environ.get(DB_URL_ENV_VAR, "") or DEFAULT_DB_URL


def _is_memory_sqlite(url: str) -> bool:
    """``url`` 是否指向一个**内存** SQLite 库。

    用 :func:`sqlalchemy.engine.make_url` 解析而不是子串匹配：``sqlite://``、
    ``sqlite:///:memory:``、``sqlite+aiosqlite:///:memory:`` 都要认出来，
    而 ``sqlite:///C:/x/memory.db`` 这种**文件名里带 memory** 的磁盘库不能被误认。
    ``make_url(...).database`` 对 ``sqlite://`` 是 ``None``、对 ``:memory:`` 是那个字面量，
    对磁盘库是路径——两种内存形状正好是「没有路径」与「路径就是 ``:memory:``」。
    """
    made = make_url(url)
    return made.get_backend_name() == "sqlite" and made.database in (None, ":memory:")


def _build_engine(url: str) -> Engine:
    """按 URL 造引擎；内存 SQLite 换 :class:`~sqlalchemy.pool.StaticPool`。

    **``StaticPool`` 在内存库上是承重的、不是优化**：SQLite 的 ``sqlite://`` 是
    「**每条连接一个独立的库**」，而 ``create_engine`` 缺省的 ``QueuePool`` 会在
    连接被归还后另开一条新的。于是 ``init_db`` 建表用的那条连接与请求里
    :func:`app.api.deps.get_db` 拿到的那条可能是两条不同的连接 = 两个不同的库，
    症状是 ``sqlite3.OperationalError: no such table: student``。
    ``StaticPool`` 让全进程复用**同一条**连接。

    ``check_same_thread=False`` 同一条连接的两个必要条件之一：StaticPool 下那唯一的
    ``sqlite3.Connection`` 会被 Starlette 的线程池跨线程复用（同步端点跑在
    ``anyio.to_thread`` 里），而 sqlite3 缺省禁止跨线程使用同一个连接对象。

    ⚠️ 代价：``StaticPool`` + 单连接意味着**没有并发**。这是测试与单机演示要的语义
    （可预测、无锁竞争），不是生产要的。磁盘库那一支不受影响，它走
    :func:`app.db.session.engine`——那个函数刻意不带缺省 URL（Plan 02 Task 1 的终审
    C 组），故本模块必须显式把 URL 交给它。
    """
    if _is_memory_sqlite(url):
        return create_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    return build_engine(url)


def create_app(*, db_url: str | None = None) -> FastAPI:
    """建一个**独立**的应用实例。

    ``db_url`` 缺省时按 :func:`_resolve_db_url` 解析（环境变量 > ``DEFAULT_DB_URL``）；
    **测试一律显式注入 ``"sqlite://"`**（``tests/api/conftest.py``）。

    每次调用返回**新的** ``FastAPI`` 与**新的** ``Engine``，引擎挂在
    ``app.state.engine`` 上、由 :func:`app.api.deps.get_db` 按请求取用。
    ⚠️ 不要把引擎放模块级全局：那样同进程里的两个应用会共用后建的那个引擎，
    而 ``tests/api/`` 的 ``app`` 夹具是 function 级的（每个测试一个新应用）。
    这条性质由 :func:`app.api.deps.get_db` 的 docstring 与本函数的实现共同保证。

    建表发生在 **lifespan**（``async with`` 进入 ``TestClient`` 或 uvicorn 启动时），
    不在本函数体里——理由见模块 docstring 里那条 ⚠️（``pe.db`` 禁区）。
    ``init_db`` 走 ``Base.metadata.create_all``，对已存在的表原样跳过，故可重复调用。
    """
    url = _resolve_db_url(db_url)
    eng = _build_engine(url)

    @asynccontextmanager
    async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
        init_db(eng)
        yield

    application = FastAPI(
        title="体育闭环原型系统",
        description=(
            "spec §9 的后端接口层。⚠️ 原型口径：身份由请求头传递（X-Student-Id / "
            "X-Teacher-Staff-No），没有真实鉴权；CORS 允许全部来源。上线前两者都要收紧。"
        ),
        version="0.3.0",
        lifespan=_lifespan,
    )
    application.state.engine = eng

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(application)

    @application.get("/api/health")
    def health(session: Session = Depends(get_db)) -> dict[str, object]:
        """存活探针：``{"status": "ok", "tables": <int>, "students": <int>}``。

        两个数各答一个不同的问题，这是它作为冒烟判据的全部价值：

        * ``tables`` 取自 ``Base.metadata``，是 **schema 层面**的计数，不碰库——
          故它在空库上也能答对，答的是「25 张表的模型都注册进来了吗」。
          ⚠️ 张数由 Plan 03 Task 2 起从 18 递增到 **25**（反馈三源 4 张 +
          预警/通知 2 张 + 班级周报 1 张，全部住在 ``app/db/models/feedback.py``），
          同步清单归 ``tests/test_main.py::test_health_reports_the_table_count``
          与 ``tests/db/test_models.py::test_all_twenty_five_tables_created``。
        * ``students`` 是一次**真的查询**，答的是「连上的是哪个库、建表了没有」。
          ``tables`` 单独证明不了这件事：它读的是 Python 对象，不是数据库。
        """
        students = session.scalar(select(func.count()).select_from(Student))
        return {
            "status": "ok",
            "tables": len(Base.metadata.tables),
            "students": students,
        }

    return application


#: ``uvicorn app.main:app`` 的入口。⚠️ 它是**模块级**语句，故 ``import app.main``
#: 就会执行：造一个引擎（惰性，不连接、不建文件）、绑在
#: :func:`_resolve_db_url` 解析出来的 URL 上。要换库请在 import 之前设
#: ``PE_DB_URL``（见模块 docstring 的「手工演示怎么跑」）。
app = create_app()
