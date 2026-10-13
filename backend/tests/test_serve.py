"""**产品档**的守卫（Plan 06 Task 7）：SPA fallback 判据 + ``serve_app`` 入口 + ``serve.ps1``。

--------------------------------------------------------------------------
派单点名的那一条与本文件的关系
--------------------------------------------------------------------------

派单 §1 第 5 条逐字写的是「**本 Task 的核心验收**：``smoke.mjs`` 在产品档下
18 步全绿、退出码 0」。那一格是**跨进程**的（要真起一个 uvicorn、真跑一个
无头浏览器），故它的取证住在实现者报告里，不在本文件——pytest 里起一个
监听端口的进程与本仓既有的测试口径不符（``tests/`` 一律用
:class:`fastapi.testclient.TestClient`，一个端口都不占）。

⚠️ **本文件补的是那一格补不到的东西**：smoke 全绿只证明「18 条被断言的路径
在产品档下是对的」，而 SPA fallback 的判据有**三类**它压根不打的地方——

1. ``/api`` 下面一个**不存在**的路径（``GET`` 与 ``POST`` 各一档：404 vs 405）；
2. **目录穿越**（``/%2e%2e%2f…`` 到 ``dist`` 外面去）；
3. ``content-type``（一个 ``text/plain`` 的 ``.js`` 在浏览器里是白屏，
   而 smoke 的第 14 步用的是 CDP、它**会**因为 MIME 而挂，但挂的样子是
   「DOM 里没有那个 class」，离真因有两层）。

三类各有一条守卫，且**红绿两档同时在场**（硬规矩 #50）。

--------------------------------------------------------------------------
⚠️ 另有一组「**什么都没变**」的守卫
--------------------------------------------------------------------------

派单 §1 第 4 条逐字要求「1464 条测试与 ``demo.ps1`` 的行为一字不变」。
本文件把那一格做成可执行的三条：

* :func:`test_the_dev_tier_is_untouched_when_static_dist_is_not_given`
  ——不给 ``static_dist`` 时**一条 SPA 路由都没有**，``/login`` 仍然是
  统一形状的 404（而不是一个 200 的 HTML）；
* :func:`test_the_openapi_document_is_identical_with_and_without_the_spa`
  ——``/openapi.json`` 逐字相等（前端 ``src/api/generated/schema.d.ts`` 由它生成，
  多一条路径就要重生成一次）；
* :func:`test_method_semantics_on_and_off_the_api_are_unchanged`
  ——四档状态码（``DELETE /api/semesters`` 405、``POST /api/health`` 405、
  ``POST /api/nope`` 404、``POST /login`` 404）与今天逐字相同。
  ⚠️ 最后那一档是**本 Task 实测出来的**，派单没提：一个 ``methods=None`` 的
  catch-all 会把 ``DELETE /api/semesters`` 从 405 改成 404，
  而 smoke 第 10 步逐字断言它是 405。逐字理由见 :class:`app.static._SpaRoute`。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Route

from app import static
from app.config import BACKEND_DIR
from app.main import create_app

#: ``backend/scripts/``。⚠️ 它**不是包**（没有 ``__init__.py``），故按路径加载
#: （与 ``tests/test_backup_restore.py`` 的 :func:`_load` 同一条口径）。
SCRIPTS_DIR = BACKEND_DIR / "scripts"

#: 仓库根。⚠️ 由 ``app.config.BACKEND_DIR`` 推出来、**不在本文件里敲第二遍路径**
#: （``tests/test_dependencies.py`` 的
#: ``test_both_manifests_really_are_the_two_files_the_guard_thinks_they_are``
#: 钉住了那个常量的形状）。
REPO_ROOT = BACKEND_DIR.parent

SERVE_PS1 = REPO_ROOT / "scripts" / "serve.ps1"
SERVE_APP = SCRIPTS_DIR / "serve_app.py"

#: 一个**最小但形状对**的构建产物：``index.html`` + ``assets/`` 下的
#: js / css / svg / woff2（``npm run build`` 实测就是这五种扩展名，
#: 亲跑：``Get-ChildItem frontend\\dist -Recurse -File | Group-Object Extension``）。
INDEX_BODY = b'<!doctype html>\n<html lang="zh-CN"><title>PE-SPA-FIXTURE</title>\n<div id="app"></div>\n'
JS_BODY = b"console.log('PE-SPA-FIXTURE-JS')\n"
CSS_BODY = b".a{color:#122e66}\n"
SVG_BODY = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
#: ⚠️ 刻意是**二进制**（0x00–0xFF 全字节）：它同时是「woff2 不许被当文本处理」
#: 与「``FileResponse`` 原字节发出」两格的正控。
WOFF2_BODY = bytes(range(256))
#: 住在 ``dist`` **外面**的那个文件：目录穿越那一档要断言的东西是
#: 「它的字节一次都没有被发出去」。
SECRET_BODY = b"PE-SECRET-OUTSIDE-DIST"

#: ``frontend/src/router/index.ts`` 里真实存在的前端路由（深链接那一档的正控）。
#: ⚠️ 期望侧取自**路由树**而不是拍脑袋：15 条路由里的 4 棵树的代表各一条，
#: 加上 ``/login``（``meta.public``）与一个**打错的** URL
#: （路由树用 ``/:pathMatch(.*)*`` 接它，故它也必须拿到 index.html）。
FRONTEND_DEEP_LINKS = (
    "/",
    "/login",
    "/bind",
    "/s/home",
    "/s/weekly-sheet",
    "/t/dashboard",
    "/t/students/1",
    "/admin",
    "/admin/students/1",
    "/this-route-does-not-exist",
)


@pytest.fixture()
def dist(tmp_path: pathlib.Path) -> pathlib.Path:
    """一份临时构建产物 + 一个住在它**外面**的秘密文件。"""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(INDEX_BODY)
    (root / "assets" / "app.js").write_bytes(JS_BODY)
    (root / "assets" / "app.css").write_bytes(CSS_BODY)
    (root / "assets" / "logo.svg").write_bytes(SVG_BODY)
    (root / "assets" / "font.woff2").write_bytes(WOFF2_BODY)
    (tmp_path / "secret.txt").write_bytes(SECRET_BODY)
    return root


@pytest.fixture()
def spa_client(dist: pathlib.Path):
    """**产品档**的那个应用（``static_dist`` 非 ``None``）+ 一个 TestClient。

    ⚠️ 用 ``with`` 进去是承重的：它触发 lifespan 的 ``init_db``，
    于是 ``/api/health`` 那一格是一次**真的查询**（否则它会 500，
    而 500 与「SPA 遮住了 /api」在颜色上无法区分）。
    """
    application = create_app(db_url="sqlite://", static_dist=dist)
    with TestClient(application) as client:
        yield client


def _load_serve_app(monkeypatch, dist: pathlib.Path | None = None):
    """按路径加载 ``backend/scripts/serve_app.py``（每次都拿到一个**新**模块）。

    ⚠️ ``PE_DB_URL`` 一律设成 ``sqlite://``：那个模块有一条**模块级**的
    ``app = create_app(...)``，而不设的话它会解析到
    :data:`app.config.DEFAULT_DB_URL` = ``backend/pe.db``——本仓的**禁区**。
    ``create_engine`` 是惰性的（不建文件），但「测试进程里连一个惰性的
    ``pe.db`` 引擎都不造」是更便宜的一格纪律。
    ⚠️ 模块名带上 ``dist`` 的 id：两个测试各加载一次时不共用 ``sys.modules`` 里
    的那一份（否则第二次的 ``PE_STATIC_DIST`` 会被第一次的模块级 ``app`` 悄悄顶掉）。
    """
    monkeypatch.setenv("PE_DB_URL", "sqlite://")
    if dist is None:
        monkeypatch.delenv("PE_STATIC_DIST", raising=False)
    else:
        monkeypatch.setenv("PE_STATIC_DIST", str(dist))
    name = f"_serve_app_probe_{id(dist)}"
    spec = importlib.util.spec_from_file_location(name, SERVE_APP)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _code_string_literals(tree: ast.AST) -> list[str]:
    """一棵 AST 里的全部字符串字面量，**去掉 docstring**。

    ⚠️ 不去掉的话下面那条「``serve_app.py`` 里不许出现 ``dist`` 这个字面串」
    会红在**它自己的说明文字**上——那个模块的 docstring 逐字解释了
    「为什么不在这里敲第二遍 ``frontend/dist``」，于是它必然**提及**那个串。
    提及不是本身（硬规矩 #109），与 ``tests/test_backup_restore.py`` 里
    「只扫 ``#>`` 之后的代码段」是同一条处置。
    """
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# ===========================================================================
# ① 判据本身（纯函数，不经 HTTP）
# ===========================================================================


def test_is_reserved_draws_its_boundary_on_a_slash_and_not_on_a_prefix():
    """:func:`app.static.is_reserved` 的红绿两档矩阵。

    ⚠️ 最后四行是本条存在的理由：裸 ``startswith("/api")`` 会把 ``/apixyz``
    与 ``/documentary`` 判成保留前缀，而它们的正确去处是 ``index.html``
    （前端 ``router`` 的 ``/:pathMatch(.*)*`` 会把它们弹回 ``/s/home``）。
    一个把打错的 URL 判成 404 的 fallback 不算坏，但它与「SPA fallback」
    这个承诺不符，而**这一格在今天不会被任何别的测试抓到**。
    """
    reserved = [
        "/api", "/api/", "/api/health", "/api/nope", "/api/students/1/prescriptions/current",
        "/openapi.json", "/openapi.json/extra",
        "/docs", "/docs/oauth2-redirect", "/redoc", "/redoc/extra",
    ]
    for path in reserved:
        assert static.is_reserved(path), f"{path} 应当是保留前缀"

    not_reserved = [
        "/", "/login", "/bind", "/s/home", "/t/dashboard", "/admin", "/admin/students/1",
        "/assets/app.js", "/index.html",
        # ⚠️ 边界那四格：它们**以**某个保留前缀**开头**，但不是它的子路径
        "/apixyz", "/api-health", "/documentary", "/redocumentary", "/openapi.jsonl",
    ]
    for path in not_reserved:
        assert not static.is_reserved(path), f"{path} 不该是保留前缀"

    # 反空转：那四项**逐字**是本仓今天真实注册的四个非 /api 面
    assert static.RESERVED_PREFIXES == ("/api", "/openapi.json", "/docs", "/redoc")


def test_resolve_static_path_answers_exactly_the_three_documented_cases(dist):
    """:func:`app.static.resolve_static_path` 的三档（模块 docstring 里那张表）。"""
    index = (dist / "index.html").resolve()

    # 档 1：磁盘上真有它 → 那个文件（按原字节发）
    assert static.resolve_static_path(dist, "/index.html") == index
    assert static.resolve_static_path(dist, "/assets/app.js") == (
        dist / "assets" / "app.js"
    ).resolve()
    assert static.resolve_static_path(dist, "/assets/font.woff2") == (
        dist / "assets" / "font.woff2"
    ).resolve()

    # 档 2：保留前缀之外、磁盘上没有 → index.html（**SPA fallback**）
    for path in FRONTEND_DEEP_LINKS:
        assert static.resolve_static_path(dist, path) == index, path

    # 档 3：保留前缀 → None（= 本层不接，交给框架 404）
    for path in ("/api/health", "/api/nope", "/openapi.json", "/docs", "/docs/nope",
                 "/redoc"):
        assert static.resolve_static_path(dist, path) is None, path

    # ⚠️ 目录（不是文件）也走 fallback：``/assets`` 在磁盘上**存在**，
    #    而 ``is_file()`` 为假 → index.html。那一格是有意的：
    #    给一个目录列表等于把产物结构告诉任何匿名调用方。
    assert static.resolve_static_path(dist, "/assets") == index


def test_resolve_static_path_refuses_to_leave_the_dist_directory(dist, tmp_path):
    """**目录穿越**：``dist`` 外面那个文件的字节一次都不许被发出去。

    ⚠️ ``scope["path"]`` 是 uvicorn **percent-decode 之后**的串，故
    ``/%2e%2e%2fsecret.txt`` 到这里已经是 ``/../secret.txt``——本条因此
    直接用**解码后**的形状测（那一格由 ASGI 规范保证，不是本模块的责任）。
    ⚠️ 三档各走一条不同的路：``..`` 上溯、Windows 的盘号绝对路径
    （``pathlib`` 里 ``Path(a) / "C:/x"`` == ``Path("C:/x")``，左边被**丢掉**，
    故字符串判据挡不住它）、以及一个**存在**的越界目标。
    """
    secret = (tmp_path / "secret.txt").resolve()
    assert secret.is_file() and secret.read_bytes() == SECRET_BODY

    # ① 三档**解码后**的上溯：一律 None（→ 404），绝不退化成 index.html
    #    （退化的话一个 200 会让探测者以为那是一个合法的前端路由）。
    for path in (
        "/../secret.txt",
        "/../../secret.txt",
        "/assets/../../secret.txt",
        "/assets/../../../secret.txt",
    ):
        got = static.resolve_static_path(dist, path)
        assert got != secret, f"{path} 逃出了 dist：{got}"
        assert got is None, (path, got)

    # ② ⚠️ 而**字面**的 ``%2e%2e``（没被解码）不是穿越：它就是一个名字里带
    #    百分号的、不存在的路径 → 走 SPA fallback。⚠️ 这一格是刻意的对照：
    #    percent-decode 是 **uvicorn** 的责任（ASGI 规范里的 ``scope["path"]``
    #    已经是解码后的串），本模块不做第二次解码——做两次解码才是漏洞
    #    （``%252e%252e`` 那一类双编码绕过）。
    literal = static.resolve_static_path(dist, "/%2e%2e/secret.txt")
    assert literal == (dist / "index.html").resolve()
    assert literal.read_bytes() == INDEX_BODY

    # ③ 盘号绝对路径那一档：判据必须是「resolve 之后仍在 dist 内」，
    #    而不是「串里没有 ..」。⚠️ pathlib 里 ``Path(a) / "C:/x"`` == ``Path("C:/x")``
    #    （左边的被**丢掉**），故字符串判据挡不住它。
    windows = "/" + pathlib.Path(sys.executable).as_posix()
    assert static.resolve_static_path(dist, windows) is None


def test_resolve_static_path_returns_none_when_there_is_no_index_to_fall_back_to(
    tmp_path,
):
    """``dist`` 里没有 ``index.html`` 时**不**返回一个发不出去的路径。

    ⚠️ 这是第二道：第一道是 :func:`app.static.mount_spa` 在**装配期**就
    ``FileNotFoundError``（:func:`test_mount_spa_refuses_a_directory_that_is_not_a_build`）。
    本条钉的是「有人绕过 ``mount_spa`` 直接调判据」那一档，
    它必须回答 ``None``（→ 404）而不是 ``dist/index.html``（→ 500）。
    """
    empty = tmp_path / "empty-dist"
    empty.mkdir()
    assert static.resolve_static_path(empty, "/login") is None
    assert static.resolve_static_path(empty, "/") is None
    # 而一个**真存在**的文件仍然照发（「没有 index.html」不等于「不发静态文件」）
    (empty / "robots.txt").write_bytes(b"User-agent: *\n")
    assert static.resolve_static_path(empty, "/robots.txt") == (
        empty / "robots.txt"
    ).resolve()


def test_media_type_of_pins_the_five_extensions_a_build_actually_emits():
    """:func:`app.static.media_type_of` —— ``dist`` 里那五种扩展名逐个钉住。

    ⚠️ **本条不是洁癖**：``FileResponse`` 缺省用 :func:`mimetypes.guess_type`，
    而它在 Windows 上**读注册表**。本机亲跑（Python 3.11.1）::

        mimetypes.guess_type('a.woff2') → (None, None)      # 会退化成 text/plain
        mimetypes.guess_type('a.map')   → (None, None)
        mimetypes.guess_type('a.js')    → ('application/javascript', None)

    ``.js`` 那一格**本机是对的**，而注册表里把它映成 ``text/plain`` 的 Windows
    机器真实存在（装过某些老工具就会留下），且 ES module 的**严格 MIME 检查**
    会让浏览器直接拒绝执行 → 产品档白屏、dev 档正常，离真因两层。
    ⚠️ 故本条断言的是**本模块那张表**、不是 ``mimetypes`` 的答案：
    两侧同源的话它就只能证明「表与它自己相等」（硬规矩 #35）。
    """
    expected = {
        "app.js": "text/javascript; charset=utf-8",
        "app.mjs": "text/javascript; charset=utf-8",
        "app.css": "text/css; charset=utf-8",
        "index.html": "text/html; charset=utf-8",
        "logo.svg": "image/svg+xml",
        "font.woff2": "font/woff2",
        "font.woff": "font/woff",
        "data.json": "application/json",
        "data.map": "application/json",
        "favicon.ico": "image/x-icon",
        "site.webmanifest": "application/manifest+json",
        "shot.png": "image/png",
        "robots.txt": "text/plain; charset=utf-8",
    }
    for name, want in expected.items():
        assert static.media_type_of(pathlib.Path(name)) == want, name
    # 大小写不敏感（``APP.JS`` 与 ``app.js`` 同答）
    assert static.media_type_of(pathlib.Path("APP.JS")) == expected["app.js"]
    # 认不出的扩展名 → None（交给框架去猜，本表不做「一律 text/plain」这类兜底）
    assert static.media_type_of(pathlib.Path("thing.xyz")) is None
    assert static.media_type_of(pathlib.Path("no-extension")) is None


# ===========================================================================
# ② 经 HTTP 的实测矩阵（派单 §1 第 3 条那张表的 pytest 版）
# ===========================================================================


def test_every_frontend_deep_link_gets_index_html_with_a_200(spa_client):
    """深链接逐条 200 + ``text/html`` + **就是** ``index.html`` 的字节。"""
    for path in FRONTEND_DEEP_LINKS:
        response = spa_client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.headers["content-type"].startswith("text/html"), path
        assert response.content == INDEX_BODY, path


def test_real_assets_are_served_byte_for_byte_with_the_right_content_type(spa_client):
    """``dist`` 里**真存在**的文件按原字节发，且 ``content-type`` 对。

    ⚠️ woff2 那一格用的是 0x00–0xFF 全字节的**二进制**体：它同时证明
    「没有被当文本处理」与「没有被 gzip / 转码」。
    """
    matrix = (
        ("/assets/app.js", JS_BODY, "text/javascript"),
        ("/assets/app.css", CSS_BODY, "text/css"),
        ("/assets/logo.svg", SVG_BODY, "image/svg+xml"),
        ("/assets/font.woff2", WOFF2_BODY, "font/woff2"),
        ("/index.html", INDEX_BODY, "text/html"),
    )
    for path, body, media in matrix:
        response = spa_client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith(media), (
            path, response.headers["content-type"]
        )
        assert response.content == body, path

    # HEAD 拿得到同一格头、而**没有**响应体（浏览器的预取与 smoke 的探活都用它）
    head = spa_client.head("/assets/app.js")
    assert head.status_code == 200
    assert head.headers["content-type"].startswith("text/javascript")
    assert head.content == b""


def test_the_api_the_contract_and_the_two_doc_pages_are_not_shadowed(spa_client):
    """``/api/health`` / ``/openapi.json`` / ``/docs`` / ``/redoc`` 四格都还活着。

    ⚠️ 本条是「:func:`app.static.mount_spa` 的**调用位置**是承重的」那一格的
    可执行形式：把它挪到 ``include_router(api_router)`` 之前，
    这四格会**全部**变成 404（catch-all 先 ``FULL`` 命中，然后
    :func:`app.static.is_reserved` 说「保留」→ 抛 404），
    而 dev 档（不传 ``static_dist``）完全正常。
    """
    health = spa_client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok" and body["tables"] == 28 and body["students"] == 0

    contract = spa_client.get("/openapi.json")
    assert contract.status_code == 200
    assert contract.headers["content-type"].startswith("application/json")
    assert "/api/health" in contract.json()["paths"]

    docs = spa_client.get("/docs")
    assert docs.status_code == 200
    assert docs.headers["content-type"].startswith("text/html")
    assert "swagger" in docs.text.lower()

    redoc = spa_client.get("/redoc")
    assert redoc.status_code == 200
    assert redoc.headers["content-type"].startswith("text/html")


def test_an_unknown_path_under_a_reserved_prefix_answers_the_unified_404(spa_client):
    """``/api/nope`` 一族：**404 + 统一错误形状**，绝不是一份 200 的 HTML。

    ⚠️ 这一格是派单 §1 第 3 条点名要的（「一个 dist 里不存在也不该 fallback
    的路径」），而它坏掉的样子最难查：一个 200 的 ``index.html`` 会让调用方的
    ``JSON.parse`` 在**前端**炸，而真因在后端的路由顺序上。
    """
    for path in ("/api/nope", "/api/students/999999/nope", "/openapi.json/extra",
                 "/docs/nope", "/redoc/nope"):
        response = spa_client.get(path)
        assert response.status_code == 404, (path, response.status_code)
        assert response.headers["content-type"].startswith("application/json"), path
        assert response.json()["error"]["code"] == "not_found", path
        assert "PE-SPA-FIXTURE" not in response.text, path


def test_a_traversal_over_http_never_reaches_a_file_outside_dist(spa_client, tmp_path):
    """**经 HTTP** 的目录穿越：``dist`` 外面那个文件的字节一次都不出门。

    ⚠️ 本条与 :func:`test_resolve_static_path_refuses_to_leave_the_dist_directory`
    不是重复：那一条喂的是**已经解码**的串（判据层），本条走的是完整的
    「httpx 发原始 URL → ASGI 传输层 ``unquote`` → ``scope["path"]``」这条路，
    故它同时钉住「:func:`app.static.mount_spa` 读的是 ``scope["path"]``
    而不是 ``request.url.path``」那一格——后者会把已解码的串再拼回一个 URL
    重新解析，一个字面含 ``%252e`` 的路径会被**二次解码**（那才是真漏洞）。

    ⚠️⚠️ **下面那张期望表是实测出来的、不是推出来的**（探针：一个包住 ``app`` 的
    ASGI spy，打印 ``scope["path"]`` 与 ``scope["raw_path"]``）：

    ================================  ==========================  ======  ===========
    请求的 URL                          ``scope["path"]``           状态码   响应体
    ================================  ==========================  ======  ===========
    ``/%2e%2e/secret.txt``             ``/../secret.txt``           404     统一 404
    ``/assets/%2e%2e/%2e%2e/secret…``  ``/assets/../../secret.txt`` 404     统一 404
    ``/assets/%2e%2e/secret.txt``      ``/assets/../secret.txt``    200     index.html
    ``/../secret.txt``（**字面**）      ``/secret.txt``              200     index.html
    ================================  ==========================  ======  ===========

    两格要点：① 第 3 行**不是**穿越——它 resolve 到 ``dist/secret.txt``
    （仍在 ``dist`` 内），而那个文件不存在，故走 SPA fallback；
    ② 第 4 行的**字面** ``/../`` 到不了服务端：``httpx`` 在拼 URL 时就把
    点段折掉了（连 ``raw_path`` 都是 ``b'/secret.txt'``），故「字面 ``..``」
    这一档在 HTTP 层**无法表达**，只有判据层那一条测得到它。
    ⚠️ 四行的共同点是**没有一行发出那个秘密文件的字节**——那才是本条的判据。
    """
    secret = tmp_path / "secret.txt"
    assert secret.is_file() and secret.read_bytes() == SECRET_BODY
    # ⚠️ 反空转：dist 里面**没有**一个叫 secret.txt 的东西（否则「404 / index.html」
    #    可能只是「它被当成 dist 内的一个正常文件发出去了」）。
    assert not (tmp_path / "dist" / "secret.txt").exists()
    assert not (tmp_path / "dist" / "assets" / "secret.txt").exists()

    matrix = (
        ("/%2e%2e/secret.txt", 404),
        ("/assets/%2e%2e/%2e%2e/secret.txt", 404),
        ("/assets/%2E%2E/secret.txt", 200),
        ("/assets/%2e%2e/secret.txt", 200),
        ("/../secret.txt", 200),
        ("/assets/../../secret.txt", 200),
    )
    for path, want_status in matrix:
        response = spa_client.get(path)
        assert response.status_code == want_status, (path, response.status_code)
        assert SECRET_BODY.decode() not in response.text, f"{path} 泄了 dist 外面的文件"
        assert response.headers["content-type"].startswith(
            "text/html" if want_status == 200 else "application/json"
        ), (path, response.headers["content-type"])
        if want_status == 200:
            assert response.content == INDEX_BODY, path
        else:
            assert response.json()["error"]["code"] == "not_found", path


def test_method_semantics_on_and_off_the_api_are_unchanged(spa_client):
    """**四档状态码逐个**与今天（没有 SPA 的 dev 档）逐字相同。

    ⚠️⚠️ 前两档是本 Task **实测出来的**、派单没提，而它们各否定一个「看起来对」
    的实现（逐字理由见 :class:`app.static._SpaRoute` 的 docstring）：

    * ``methods=None`` 的 catch-all → ``DELETE /api/semesters`` 变 **404**
      （``FULL`` 抢在 api 路由的 ``PARTIAL`` 前面）。
      ⚠️ 那一格会**当场红在 smoke 上**：``frontend/scripts/smoke.mjs`` 第 10 步
      逐字断言「DELETE 是 405 不是 204」；
    * ``methods=["GET", "HEAD"]`` 的裸 ``Route`` → ``POST /api/nope`` 变
      **405 ``Allow: GET, HEAD``**（catch-all 自己是那个唯一的 ``PARTIAL``）。
      ⚠️ 那一格更坏：它在 ``/api`` 下面回一句「这个路径存在、只是方法不对」，
      而它**不存在**。

    后两档（``POST /api/nope`` 404、``POST /login`` 404）是同一枚硬币的另一面：
    一个静态产物目录对 ``POST`` 无话可说，而**装作**有话可说就是撒谎。
    """
    # ① 真端点 + 错方法 → 405（api 路由的 PARTIAL 胜出，Allow 头是它自己的）
    delete = spa_client.delete("/api/semesters")
    assert delete.status_code == 405, delete.status_code
    assert delete.json()["error"]["code"] == "http_405"
    post_health = spa_client.post("/api/health")
    assert post_health.status_code == 405, post_health.status_code

    # ② /api 下面一个不存在的路径 → 404（不是 405、更不是 200 的 HTML）
    for path in ("/api/nope", "/api/students/999999/nope"):
        posted = spa_client.post(path)
        assert posted.status_code == 404, (path, posted.status_code)
        assert posted.json()["error"]["code"] == "not_found", path
        assert "GET" not in posted.headers.get("allow", ""), (
            f"{path} 回了 Allow: {posted.headers.get('allow')}，"
            "而它压根不存在（405 会说谎）"
        )

    # ③ /api 之外的一个前端路由，用 POST 打 → 404（GET 才是 200，见上面那条）
    for path in ("/login", "/s/home", "/nope"):
        posted = spa_client.post(path)
        assert posted.status_code == 404, (path, posted.status_code)
        assert posted.json()["error"]["code"] == "not_found", path

    # ⚠️ 反空转：同一个 client 上 GET 那两条**确实是 200**
    #    （否则上面那三格可能只是「整个应用都 404 了」）。
    assert spa_client.get("/login").status_code == 200
    assert spa_client.get("/api/health").status_code == 200


def test_the_spa_route_is_appended_exactly_once_and_last(dist):
    """SPA 那条路由**恰好一条**、且在 ``routes`` 的**末尾**。

    ⚠️ 「恰好一条」挡的是「有人把 ``mount_spa`` 调了两次」
    （例如 ``create_app`` 里调一次、``serve_app`` 里再调一次）：
    第二条永远命中不到，于是它是一份**没有守卫的死代码**，
    而下一个人改判据时会改到那一份上。
    """
    application = create_app(db_url="sqlite://", static_dist=dist)
    routes = application.router.routes
    assert routes[-1].path == static.SPA_ROUTE_PATH, [
        getattr(r, "path", None) for r in routes
    ]
    assert sum(getattr(r, "path", None) == static.SPA_ROUTE_PATH for r in routes) == 1
    assert isinstance(routes[-1], Route)
    # ⚠️ 而**不给** ``static_dist`` 时一条都没有（下一条测试的注册面那一半）
    plain = create_app(db_url="sqlite://")
    assert not any(
        getattr(r, "path", None) == static.SPA_ROUTE_PATH
        for r in plain.router.routes
    )


# ===========================================================================
# ③ 「什么都没变」那三条
# ===========================================================================


def test_the_dev_tier_is_untouched_when_static_dist_is_not_given():
    """不给 ``static_dist`` → ``/login`` 仍然是统一形状的 **404**，不是一份 HTML。

    ⚠️ 它是派单 §1 第 4 条「1464 条测试与 ``demo.ps1`` 的行为一字不变」的
    可执行形式：``demo.ps1`` 跑的是 ``uvicorn app.main:app``，
    而那个 ``app`` 是 ``create_app()`` **无参**建的。
    ⚠️ 失效形态很具体：若 ``static_dist`` 的缺省值不是 ``None``
    （例如缺省成 ``BACKEND_DIR.parent / "frontend" / "dist"``），
    那么**每一个**既有测试都会在 ``frontend/dist`` 存在时多出一条 catch-all，
    而 ``tests/api/`` 里那些断言 404 的测试会**静默地**变成断言一份 200 的 HTML。
    """
    application = create_app(db_url="sqlite://")
    with TestClient(application) as client:
        for path in ("/", "/login", "/s/home", "/admin"):
            response = client.get(path)
            assert response.status_code == 404, (path, response.status_code)
            assert response.json()["error"]["code"] == "not_found", path
        # 而 /api 那一侧照常
        assert client.get("/api/health").status_code == 200


def test_the_openapi_document_is_identical_with_and_without_the_spa(dist):
    """``app.openapi()`` **逐字相等**（给了 ``static_dist`` 与不给）。

    ⚠️ 前端 ``src/api/generated/schema.d.ts`` 由 ``npm run gen:api`` 从
    ``/openapi.json`` 生成，故「多一条路径」不是无害的：它会让那份 4 万行的
    类型文件多出一个 ``paths['/{path}']``，而 ``src/api/contract.ts``
    是按 ``components.schemas`` 驱动管理台表单的。
    ⚠️ 实现上之所以成立：SPA 那条是 :class:`starlette.routing.Route`
    而不是 ``fastapi.routing.APIRoute``，而 ``get_openapi`` 只收后者。
    本条因此**也**是「有人把它改成了 ``@application.get("/{path:path}")``」
    那一档的守卫——那一种写法会让本条当场红。
    """
    plain = create_app(db_url="sqlite://").openapi()
    with_spa = create_app(db_url="sqlite://", static_dist=dist).openapi()
    assert plain == with_spa

    # 反空转：那两份 spec 不是空的（否则「相等」是空转的绿）
    paths = with_spa["paths"]
    operations = [(key, method) for key in paths for method in paths[key]]
    assert len(paths) >= 70, f"只有 {len(paths)} 条路径，spec 可能被指错了"
    assert len(operations) >= 95, f"只有 {len(operations)} 个操作"
    assert sorted(with_spa["components"]["securitySchemes"]) == [
        "X-Student-Id", "X-Teacher-Staff-No", "pe_session",
    ]
    assert not any(key.startswith("/{") for key in paths), (
        "SPA 那条 catch-all 漏进 OpenAPI 了"
    )


def test_mount_spa_refuses_a_directory_that_is_not_a_build(tmp_path):
    """``dist/index.html`` 不在 → **装配期** :class:`FileNotFoundError`（起不来）。

    ⚠️ 失效方向必须是「起不来」而不是「起来了但每页都 404」
    （与 :func:`app.main._selfcheck_prod`、``backend/scripts/demo.ps1`` 那两道
    禁区守卫同一条姿势）。⚠️ 而报错里必须**同时**出现那个路径与
    ``npm run build``：运维拿到的一句 ``404`` 会把他支去查前端路由，
    而真因是 ``PE_STATIC_DIST`` 指错了目录。
    """
    empty = tmp_path / "not-a-build"
    empty.mkdir()
    with pytest.raises(FileNotFoundError) as info:
        create_app(db_url="sqlite://", static_dist=empty)
    message = str(info.value)
    assert str(empty / "index.html") in message
    assert "npm run build" in message
    assert "PE_STATIC_DIST" in message

    # ⚠️ 一个**存在但不是目录**的同名文件同样要响（``is_file()`` 为假）
    a_file = tmp_path / "dist-is-a-file"
    a_file.write_bytes(b"not a directory")
    with pytest.raises(FileNotFoundError):
        create_app(db_url="sqlite://", static_dist=a_file)

    # 反空转：给了一个**真的**构建产物就不响（上面那些 fixture 已经证明过，
    # 这里再钉一次「本条不是恒响」）
    good = tmp_path / "good"
    good.mkdir()
    (good / "index.html").write_bytes(INDEX_BODY)
    assert create_app(db_url="sqlite://", static_dist=good) is not None


# ===========================================================================
# ④ ``backend/scripts/serve_app.py``：那个入口模块
# ===========================================================================


def test_parse_static_dist_treats_a_blank_value_as_unset(monkeypatch):
    """空串 / 只有空白 / 没设 → ``None``（= **不挂** SPA）。

    ⚠️ ``$env:PE_STATIC_DIST = ""`` 在 PowerShell 里是「设了一个空值」
    而不是「删掉这个变量」。若把空串折成 ``Path("")``，
    :func:`app.static.mount_spa` 会抛一句「``index.html`` 不存在」——
    那是一句**假**的报错（运维明明什么都没设，他会被支去查前端构建）。
    与 :func:`app.main._resolve_db_url` 的 ``or`` 同一条口径。
    """
    serve_app = _load_serve_app(monkeypatch)
    assert serve_app.parse_static_dist(None) is None
    assert serve_app.parse_static_dist("") is None
    assert serve_app.parse_static_dist("   ") is None
    assert serve_app.parse_static_dist("\t\r\n") is None
    assert serve_app.parse_static_dist("C:/x/dist") == pathlib.Path("C:/x/dist")
    # ⚠️ 两端的空白被剥掉（PowerShell 里 ``$env:X = " path "`` 是真实的一档）
    assert serve_app.parse_static_dist("  C:/x/dist  ") == pathlib.Path("C:/x/dist")

    assert serve_app.STATIC_DIST_ENV_VAR == "PE_STATIC_DIST"
    assert serve_app.resolve_static_dist() is None


def test_resolve_static_dist_reads_the_process_environment(monkeypatch, dist):
    """:func:`serve_app.resolve_static_dist` 真的读那个环境变量。

    ⚠️ 期望侧是**字面**的 ``PE_STATIC_DIST``（不是从被测模块反推），
    故「有人把它改名成 ``PE_DIST``」会红在这里、而不是红在运维的部署脚本上。
    """
    serve_app = _load_serve_app(monkeypatch)
    monkeypatch.setenv("PE_STATIC_DIST", str(dist))
    assert serve_app.resolve_static_dist() == dist
    monkeypatch.setenv("PE_STATIC_DIST", "   ")
    assert serve_app.resolve_static_dist() is None


def test_the_entry_module_really_builds_a_serving_app(monkeypatch, dist):
    """``serve_app.app`` 就是产品档的那个应用（``uvicorn serve_app:app`` 的入口对象）。

    ⚠️ 本条**加载真模块**（不是重造一个 ``create_app``）：它证明
    「环境变量 → ``create_app(static_dist=…)``」这条线是接通的，
    而不只是两个各自正确的函数。
    """
    serve_app = _load_serve_app(monkeypatch, dist)
    assert serve_app.app is not None
    with TestClient(serve_app.app) as client:
        assert client.get("/login").status_code == 200
        assert client.get("/login").content == INDEX_BODY
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/nope").status_code == 404


def test_the_entry_module_does_not_build_a_spa_when_the_variable_is_unset(monkeypatch):
    """``PE_STATIC_DIST`` 没设 → 那个入口对象与 ``app.main:app`` **同档**（不挂 SPA）。

    ⚠️ 这一格是「不设就是 dev 档」承诺的可执行形式：一个忘了设
    ``PE_STATIC_DIST`` 的 uvicorn 必须**照常起得来**（只服务 ``/api``），
    而不是抛 ``FileNotFoundError``。
    """
    serve_app = _load_serve_app(monkeypatch)
    assert not any(
        getattr(r, "path", None) == static.SPA_ROUTE_PATH
        for r in serve_app.app.router.routes
    )
    with TestClient(serve_app.app) as client:
        assert client.get("/login").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_the_entry_module_is_utf8_without_bom_and_never_names_the_dist_directory():
    """``serve_app.py`` 三格：**无 BOM**、可 ``ast.parse``、**不写死** ``dist`` 的路径。

    ① ⚠️ BOM 那一格不是洁癖：``tests/architecture/test_layering.py`` 与
       ``tests/architecture/test_domain_purity.py`` 都对 ``BACKEND.rglob("*.py")``
       逐个 ``ast.parse(..., encoding="utf-8")``，而一个 BOM 会让 ``ast.parse``
       抛 ``SyntaxError``——于是**那两条远端的守卫**炸，报错位置离真因有两层
       （``tests/db/test_migration_chain.py`` 为 ``migrations/**`` 钉的是同一条）。
    ② 「不写死」那一格是**单一所有者**：``frontend/dist`` 的绝对路径由
       ``scripts/serve.ps1`` 算（它是「仓库根在哪」的唯一所有者），
       在这里再敲一遍就是第二个所有者，而两个所有者漂了之后的症状是
       「serve.ps1 明明构建过了、uvicorn 却指着别的目录」。
       ⚠️ 只扫**代码里**的字符串字面量、不扫 docstring（硬规矩 #109：
       那个 docstring 逐字解释了为什么不在这里敲第二遍，故它必然**提及**那个串）。
    """
    raw = SERVE_APP.read_bytes()
    assert raw[:3] != b"\xef\xbb\xbf", "serve_app.py 带 BOM（ast.parse 会抛 SyntaxError）"
    tree = ast.parse(raw.decode("utf-8"))

    literals = _code_string_literals(tree)
    assert literals, "一个字符串字面量都没扫到，本条可能空转了"
    for literal in literals:
        assert "frontend" not in literal.lower(), (
            f"serve_app.py 的代码里写死了 {literal!r}：``frontend/dist`` 的路径"
            "只有 scripts/serve.ps1 一个所有者（本模块只读 PE_STATIC_DIST）"
        )
        assert "/" not in literal and "\\" not in literal, (
            f"serve_app.py 的代码里出现了一个**路径**字面量 {literal!r}："
            "本模块不许知道产物在哪，它只把 PE_STATIC_DIST 交出去"
        )
    # ⚠️ 反空转：那个环境变量名**必须**在代码里出现（它是本模块存在的理由）
    assert "PE_STATIC_DIST" in literals
    assert "app.main" in [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
