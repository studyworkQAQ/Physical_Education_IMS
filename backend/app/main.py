"""FastAPI 应用工厂，以及 ``uvicorn app.main:app`` 的那个入口对象。

**本模块是整个项目第一次有 HTTP 层**（Plan 03 Task 1）：Plan 01/02 交付的是一个批处理
系统（``python -m app.pipeline.daily``），没有服务进程。本文件只做四件事：

1. 解析「用哪个库」——:func:`_resolve_db_url`；
2. 造引擎——:func:`_build_engine`（内存 SQLite 要换连接池，见该函数）；
3. 建表——在 **lifespan** 里，不在工厂体里（下面那条 ⚠️ 是本模块最要紧的一句）；
4. 装中间件、错误处理器、``/api/health``，返回 :class:`~fastapi.FastAPI`。

路由本体住在 ``app/api/routers/``，``create_app`` 只 ``include_router`` 那**一个**汇总路由
（``api_router``）——于是 Task 5/7/8/9 各自加一个 router 时**不必再改本文件**，
而本文件上面压着 ``pe.db`` 禁区那条纪律，改得越少越好。``/api/health`` **刻意留在本文件**：
它是应用级的存活探针、不是某个资源的 CRUD。

⚠️ **建表必须在 lifespan 里、不能在工厂体里**。``app = create_app()`` 是本模块的
模块级语句，故**光是 ``import app.main`` 就会执行它**；而 ``db_url`` 缺省时解析到
:data:`app.config.DEFAULT_DB_URL`，那个常量逐字指向 ``backend/pe.db``——本仓的**禁区**
（Global Constraints）。``create_engine`` 是惰性的（不连接、不建文件），
故工厂体里造引擎是安全的；而 ``init_db`` 会**当场连接、当场建出那个文件**
（Plan 06 Task 1 之前是 ``create_all``，之后是 ``alembic upgrade head``——
两者都建文件，故本条 ⚠️ 一字不改仍然成立）。把它挪进 lifespan 之后，
「建库」这件事只在真的被 serve（或测试显式调用）时发生。
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

**CORS 与「哪一档部署」自 Plan 06 Task 4 起由 :mod:`app.deploy` 决定**：
``dev``（缺省）仍然是 ``allow_origins=["*"]``——前端跑在 ``localhost:5173`` 的 Vite dev
server 上，而演示要在同一台机器的浏览器里点起来；``prod`` 则读
``PE_CORS_ORIGINS``（逗号分隔白名单），**缺省空 = 不挂 CORSMiddleware**（= 拒绝跨域），
而非空时带 ``allow_credentials=True``（跨源部署要它，cookie 才会被浏览器发出去）。
``allow_headers=["*"]`` 在两档都必需：``X-Student-Id`` / ``X-Teacher-Staff-No``
这两个自定义头会触发预检。
⚠️ **而 ``prod`` 下装配完还有一道 :func:`_selfcheck_prod`**：CORS 被挂成 ``*``、
或 cookie 的 ``Secure`` 没开 → **``raise``**（服务起不来）。
失效方向必须是「起不来」而不是「静默不安全」，与 ``backend/scripts/demo.ps1``
那两道禁区守卫、:func:`app.db.session._stamp_unversioned` 的「先比对后 stamp」同一个姿势。

**刻意不做**（计划的显式决定，原型阶段它们是噪音）：OpenAPI 的 tag 分组美化、
响应模型的 ``exclude_none``、请求日志中间件。
⚠️ 那份清单里此前还有**「速率限制」**一项，它自 **Plan 06 Task 3** 起被做了
（登录限流与锁定，:mod:`app.auth.policy`）；⚠️ 而它是**按 ``(kind, login)``** 的、
不是「按 IP 的全局速率限制」，故「一个匿名调用方把只读端点打满」那一档今天仍然没有闸。
如实记录，已登记为待清扫。
"""
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, func, make_url, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import deploy
from app.api.deps import ALLOW_HEADER_IDENTITY_ENV_VAR, get_db
from app.api.errors import register_error_handlers
from app.api.routers import api_router
from app.auth.sessions import cookie_secure
from app.config import BACKEND_DIR, DEFAULT_DB_URL
from app.db import models  # noqa: F401  仅为把 27 张表注册进 Base.metadata
from app.db.models.organisation import Student
from app.db.session import Base
from app.db.session import engine as build_engine
from app.db.session import init_db

__all__ = ["DB_URL_ENV_VAR", "DEMO_DB_URL", "create_app"]

_LOGGER = logging.getLogger(__name__)

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


def _install_cors(application: FastAPI) -> None:
    """按**档位**装 CORS。⚠️ 它是「哪一档挂什么」在全仓的唯一住址。

    ==========================  ====================================================
    档位                         挂什么
    ==========================  ====================================================
    ``dev``（缺省）              ``CORSMiddleware(allow_origins=["*"], …)``
    ``prod`` + 白名单为空         **什么都不挂**（= 浏览器一律拦下跨源请求）
    ``prod`` + 白名单非空         ``CORSMiddleware(allow_origins=<白名单>, …,
                                 allow_credentials=True)``
    ==========================  ====================================================

    ⚠️ **「不挂」而不是「挂一个空白名单」**（计划 §4 逐字要求）：两者在浏览器上
    行为相同（都不回 ``Access-Control-Allow-Origin``），但「不挂」在
    ``application.user_middleware`` 上**看得见**（少一项），于是
    :func:`_selfcheck_prod` 与 ``tests/test_main.py`` 都能直接数它，
    而不必去猜「一个空白名单的 CORSMiddleware 到底放不放行」。
    ⚠️ 它也顺带省掉一层中间件：同源部署（Plan 06 Task 7 的那个档）根本不需要 CORS，
    而每一个请求都要穿过 ``CORSMiddleware`` 一次。

    ⚠️ ``allow_credentials=True`` **只在白名单非空那一档给**：``"*"`` 与
    ``allow_credentials=True`` 在 CORS 规范里互斥（Starlette 会照发
    ``Access-Control-Allow-Origin: *``，而浏览器**拒收**带凭据的响应），
    故 ``dev`` 那一档保持 Starlette 的缺省 ``False``——那一档用 ``*`` 就是为了
    「同一个浏览器里点得起来」，而 cookie 在同源下本来就带得过去。
    ⚠️ **prod + 白名单**那一档必须给 ``True``：那一档的语义就是「前端与后端不同源」，
    而不同源时浏览器**默认不发 cookie**（``fetch`` 的 ``credentials`` 缺省是
    ``same-origin``），不给 ``True`` 的话登录端点种下的 ``Set-Cookie`` 会被浏览器丢掉
    ——表现为「登录返回 200，而下一个请求 401」，离真因有一层。
    ⚠️ **而它还不够**：跨**站**（不只是跨源）部署还需要 ``SameSite=None``，
    本仓的 ``samesite`` 恒为 ``"lax"``（:func:`app.auth.sessions.cookie_kwargs`）。
    如实记录（硬规矩 #39），已登记为待清扫；逐字理由见那个函数的 docstring。

    ⚠️ ``PE_CORS_ORIGINS=*`` 在**这一层照挂**（解析出来就是 ``["*"]``），
    然后被 :func:`_selfcheck_prod` 抓出来 ``raise``。⚠️ **不在这里悄悄丢掉那个星号**：
    解析侧丢的话自检就永远看不到它，而运维写下的那个 ``*`` 会变成一个**静默的**
    「什么都没允许」（他会去查前端，而真因是后端把它的配置吃掉了）。
    """
    if not deploy.is_prod():
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return
    origins = deploy.cors_origins()
    if not origins:
        return
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )


def _warn_if_header_identity_was_requested_in_prod() -> None:
    """``prod`` 下若 ``PE_ALLOW_HEADER_IDENTITY=1``：打**一条** warning（它不会生效）。

    ⚠️ 计划 §4 逐字要求「读到 1 也忽略 + 一条 warning 日志」。「忽略」由
    :func:`app.api.deps.allow_header_identity` 做（它在 ``prod`` 下恒回 ``False``），
    「warning」住在这里——⚠️ **一次装配打一条**，不是逐请求打：
    「这个开关在生产上被设成了 1」是一个**部署事实**，不是一个请求事实，
    逐请求打会把日志淹掉（而淹掉日志的后果是那条 warning 再也看不见）。
    ⚠️ 它因此**只在 :func:`create_app` 里被调**：一个不经过 ``create_app`` 的进程
    （例如某个 CLI 直接调 :func:`app.api.deps.allow_header_identity`）拿不到这条日志，
    但那一档下判定仍然是「关」——日志缺了，安全性质没缺。
    """
    if not deploy.is_prod():
        return
    if (os.environ.get(ALLOW_HEADER_IDENTITY_ENV_VAR, "") or "").strip() != "1":
        return
    _LOGGER.warning(
        "%s=1 在 %s=%s 下**被忽略**：请求头身份通道（X-Student-Id / X-Teacher-Staff-No）"
        "在生产档一律关闭（它没有签名、没有过期、没有吊销，故它等于「任何人都可以自称"
        "任何学号」）。身份只有 pe_session cookie 一条通道。⚠️ 本条只在装配时打一次。",
        ALLOW_HEADER_IDENTITY_ENV_VAR,
        deploy.ENV_VAR,
        deploy.PROD,
    )


def _selfcheck_prod(application: FastAPI) -> None:
    """**生产档的启动自检**：两格不对就 :class:`RuntimeError`（服务起不来）。

    ⚠️⚠️ 它是计划 §4 逐字要求的那一条：「prod 下若 ``PE_CORS_ORIGINS`` 未设而代码仍要挂
    ``*``、或 ``Secure`` 未开 → **raise**（与 ``demo.ps1`` 那两道禁区守卫同姿势：
    失效方向必须是『起不来』，不是『静默不安全』）」。

    ⚠️ **它数的是「已经装配好的那个应用」**，不是「我打算挂什么」：判据取自
    ``application.user_middleware``（Starlette 的 ``Middleware`` 对象带 ``.cls`` 与
    ``.kwargs``，实测 starlette 1.7.0），故它抓得住「有人绕过 :func:`_install_cors`
    自己又 ``add_middleware(CORSMiddleware, allow_origins=["*"])`` 了一次」这一档。
    ⚠️ 一个只看「意图」的自检在那一档下会**绿着放行**一个全开的 CORS，
    而那正是本函数存在的理由。

    两格判据逐个：

    1. **CORS 不得是 ``*``**：任何一个 ``CORSMiddleware`` 的 ``allow_origins`` 里
       出现 ``"*"`` 就是 offender。⚠️ 它因此**也**抓 ``PE_CORS_ORIGINS=*``
       （运维图省事写一个星号 → 服务起不来，而不是静默全开）。
    2. **cookie 的 ``Secure`` 必须开**：:func:`app.auth.sessions.cookie_secure` 必须回
       ``True``。⚠️ 这一格在**构造上**不可能为假（``cookie_secure()`` 就是
       ``deploy.is_prod()``，而本函数只在 ``is_prod()`` 时被调），故它是
       **回归守卫**而不是「今天可能响的判定」：它挡的是「有人把 ``cookie_secure``
       改成读别的变量」与「有人把 ``samesite``/``secure`` 那一格挪出
       :func:`app.auth.sessions.cookie_kwargs`」两档。⚠️ 硬规矩 #39：一条构造上恒真的
       判定本身没有牙，故 ``tests/test_main.py`` 用 ``monkeypatch`` 把它**改假**、
       再断言 ``create_app`` 当场 ``raise``（那一条守卫因此**不是**恒绿的）。

    ⚠️ **offender 一次报全**（``raise`` 时把两格都列出来）：一次启动失败只报一格的话，
    运维修完一格重启、又撞第二格，而两格都是同一份部署配置里的错。

    ⚠️ **它在 :func:`create_app` 的末尾被调**，而 ``app.main`` 有一条模块级的
    ``app = create_app()``——故 ``PE_ENV=prod`` + 一份不合法的配置会让
    ``import app.main`` 就抛，``uvicorn app.main:app`` **根本起不来**。
    那正是「起不来」这个失效方向的落点。
    """
    if not deploy.is_prod():
        return
    offenders: list[str] = []
    for entry in application.user_middleware:
        if entry.cls is not CORSMiddleware:
            continue
        origins = entry.kwargs.get("allow_origins") or []
        if "*" in origins:
            offenders.append(
                f"CORS 被挂成了 allow_origins={origins!r}：生产档不得允许全部来源。"
                f"请设 {deploy.CORS_ORIGINS_ENV_VAR} 成一张逗号分隔的显式白名单"
                f"（例如 'https://pe.xmu.edu.cn'），或者**不设它**"
                f"（不设 = 不挂 CORSMiddleware = 拒绝跨域，同源部署要的就是这一档）"
            )
    if not cookie_secure():
        offenders.append(
            f"cookie 的 Secure 没有开（app.auth.sessions.cookie_secure() 回了 False），"
            f"而当前是 {deploy.ENV_VAR}={deploy.PROD}：一个不带 Secure 的会话 cookie "
            f"会在明文 HTTP 上被发出去，于是它可以在链路上被读走。"
            f"⚠️ 这一格在构造上不可能为假（cookie_secure() 就是 is_prod()），"
            f"故它响起来意味着有人改掉了 app.auth.sessions 里那个判据"
        )
    if offenders:
        raise RuntimeError(
            f"生产档启动自检不通过（{deploy.ENV_VAR}={deploy.tier()}），"
            f"服务**拒绝启动**（失效方向必须是「起不来」，不是「静默不安全」）：\n  - "
            + "\n  - ".join(offenders)
        )


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
    ⚠️ Plan 06 Task 1 起 :func:`app.db.session.init_db` 走的是 **alembic 迁移链**
    （磁盘库：文件不存在 → ``upgrade head``；旧库无 ``alembic_version`` → 比对结构后
    ``stamp`` 基线再 ``upgrade head``；已有版本表 → 幂等 ``upgrade head``），
    内存库那一档仍走 ``create_all``（测试用的就是它）。四条路径逐条见那个函数的
    docstring，一致性由 ``tests/db/test_migration_baseline.py`` 钉住。

    ⚠️ **Plan 06 Task 4 起本函数还做三件与档位有关的事**（三件都在函数体里、
    不在 lifespan 里，因为它们是**装配**而不是 I/O）：

    1. :func:`_warn_if_header_identity_was_requested_in_prod` —— ``prod`` 下若
       ``PE_ALLOW_HEADER_IDENTITY=1``，打**一条** warning（它不会生效：
       :func:`app.api.deps.allow_header_identity` 在 ``prod`` 下恒回 ``False``）；
    2. :func:`_install_cors` —— ``dev`` 挂 ``allow_origins=["*"]``；``prod`` 读
       ``PE_CORS_ORIGINS``，**空则什么都不挂**（= 拒绝跨域）；
    3. :func:`_selfcheck_prod` —— ``prod`` 下若「CORS 被挂成 ``*``」或「cookie 的
       ``Secure`` 没开」→ **``raise``**，于是本函数**不返回**、服务起不来。

    ⚠️ 于是 ``create_app`` 在 ``prod`` 下**可能抛**，而在 ``dev`` 下永远不会因档位而抛
    （:func:`app.deploy.tier` 对一个认不出的 ``PE_ENV`` 会抛 ``ValueError``，
    那一档与档位无关：坏值在任何档都是响亮的）。既有 **1370** 条测试全部跑在 ``dev``
    （``tests/conftest.py`` 不设 ``PE_ENV``），故它们一条都不受本 Task 影响——
    那一条「dev 下行为不变」的守卫是 ``tests/test_main.py`` 的
    ``test_the_dev_tier_still_mounts_the_wildcard_cors_and_no_secure_cookie``。
    """
    url = _resolve_db_url(db_url)
    eng = _build_engine(url)

    @asynccontextmanager
    async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
        init_db(eng)
        yield

    application = FastAPI(
        title="厦大体育数智系统",
        description=(
            "spec §9 的后端接口层。身份默认只认 ``pe_session`` cookie（学号/工号首次绑定"
            "口令后签发）；``X-Student-Id`` / ``X-Teacher-Staff-No`` 两个请求头通道仅在 "
            "``PE_ALLOW_HEADER_IDENTITY=1`` 时开放（测试与 DEV 深链接用），⚠️ 而在生产档"
            "（``PE_ENV=prod``）下**一律关闭**、设了也忽略。跨域：开发档允许全部来源；"
            "生产档读 ``PE_CORS_ORIGINS`` 那张显式白名单，缺省不挂 CORS（即拒绝跨域，"
            "同源部署要的正是这一档）。⚠️ 本段**刻意不写「当前是哪一档」**："
            "``/openapi.json`` 是匿名可读的，把档位回给匿名等于告诉探测者"
            "「这是一个开发档（CORS 全开、请求头身份可用）」——那正是他要挑的目标。"
            "守卫是 ``tests/test_main.py`` 的 "
            "``test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller``。"
        ),
        version="0.4.0",
        lifespan=_lifespan,
    )
    application.state.engine = eng

    _warn_if_header_identity_was_requested_in_prod()
    _install_cors(application)
    register_error_handlers(application)
    # ⚠️ 只 include 这**一个**汇总路由：Task 5/7/8/9 各加一个 router 时改的是
    # app/api/routers/__init__.py，不是本文件（本文件压着 pe.db 禁区那条纪律）。
    # 它不带 prefix：RESOURCES 里的 23 个路径串已经逐字含 /api。
    application.include_router(api_router)

    @application.get("/api/health")
    def health(session: Session = Depends(get_db)) -> dict[str, object]:
        """存活探针：``{"status": "ok", "tables": <int>, "students": <int>}``。

        两个数各答一个不同的问题，这是它作为冒烟判据的全部价值：

        * ``tables`` 取自 ``Base.metadata``，是 **schema 层面**的计数，不碰库——
          故它在空库上也能答对，答的是「27 张表的模型都注册进来了吗」。
          ⚠️ 张数由 Plan 03 Task 2 起从 18 递增到 25（反馈三源 4 张 +
          预警/通知 2 张 + 班级周报 1 张，全部住在 ``app/db/models/feedback.py``），
          **Plan 05A Task 1 再递增到 26**、**Plan 06 Task 3 再递增到 27**
          （``user_session`` 与 ``login_attempt``，两张都住在 ``app/db/models/auth.py``；
          ⚠️ 后者是本仓**第一张不在基线迁移里**的表，它由第二条迁移
          ``0b7da3d20211`` 建），
          同步清单归 ``tests/test_main.py::test_health_reports_the_table_count``
          与 ``tests/db/test_models.py::test_all_twenty_seven_tables_created``。
        * ``students`` 是一次**真的查询**，答的是「连上的是哪个库、建表了没有」。
          ``tables`` 单独证明不了这件事：它读的是 Python 对象，不是数据库。
        """
        students = session.scalar(select(func.count()).select_from(Student))
        return {
            "status": "ok",
            "tables": len(Base.metadata.tables),
            "students": students,
        }

    # ⚠️ **最后一件事**：生产档的启动自检（:func:`_selfcheck_prod`）。
    #    排在 ``return`` 之前、全部装配之后，故它数的是**这个应用最终的样子**。
    #    不通过就 ``raise``，于是 ``import app.main``（模块级 ``app = create_app()``）
    #    当场抛、``uvicorn app.main:app`` 起不来。
    _selfcheck_prod(application)
    return application


#: ``uvicorn app.main:app`` 的入口。⚠️ 它是**模块级**语句，故 ``import app.main``
#: 就会执行：造一个引擎（惰性，不连接、不建文件）、绑在
#: :func:`_resolve_db_url` 解析出来的 URL 上。要换库请在 import 之前设
#: ``PE_DB_URL``（见模块 docstring 的「手工演示怎么跑」）。
app = create_app()
