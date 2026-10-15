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
import re
import subprocess
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


def test_the_api_prefix_is_matched_case_insensitively_but_the_human_routes_are_not():
    """``/API/health`` 一族在**判据层**就是保留前缀（Plan 06 Task 15 / 终审 S4-①）。

    ⚠️ 改前实测（裸 socket 打产品档 :8020，路径逐字发出、不被任何一层归一化）：
    ``/API/health`` / ``/Api/Health`` / ``/apI/HEALTH`` / ``/API/nope`` 各回
    **200 + ``text/html`` + 2 729 B**（= ``index.html``）—— Starlette 的路由匹配与
    :func:`app.static.is_reserved` 的判据**都是大小写敏感**的，于是那些路径既不是
    真端点、也不是保留前缀，落到了 SPA fallback 上。
    ⚠️ 后果不是泄漏（那份 HTML 里一个数据字节都没有），而是**误导**：
    甲方运维一个把 ``/API/health`` 写错的 uptime 探针会**永远绿**。

    ⚠️⚠️ 而**只有 ``/api`` 这一项**放宽，另三项与全部前端路由逐字不动
    （逐格理由住在 :data:`app.static.RESERVED_PREFIXES_CASE_INSENSITIVE` 的注释里：
    ``/api/*`` 是机器面、一个 200 的 HTML 会静默骗人；``/docs`` 与前端路由是人手敲的，
    回 ``index.html`` 之后前端 router 会把人弹到该去的地方）。
    本条与 :func:`test_an_uppercase_api_path_answers_the_unified_404_and_not_index_html`
    各钉一半（判据层 / HTTP 层），两条都带反空转。
    """
    # ① 大小写变体一律判成保留前缀（→ 404 统一形状，不是 200 的 index.html）
    for path in ("/API", "/API/", "/API/health", "/Api/Health", "/apI/HEALTH",
                 "/API/nope", "/API/students/1/prescriptions/current", "/aPi/v1/x"):
        assert static.is_reserved(path), f"{path} 应当被判成保留前缀（大小写不敏感那一项）"

    # ② 反空转：另三项与前端路由**照旧**大小写敏感（否则「只有 /api 这一项」是假的）
    for path in ("/DOCS", "/REDOC", "/OPENAPI.JSON", "/Docs/oauth2-redirect",
                 "/LOGIN", "/Admin", "/S/home", "/ASSETS/app.js"):
        assert not static.is_reserved(path), f"{path} 不该被判成保留前缀（本波刻意不动它）"

    # ③ 边界那四格在大小写变体上**照旧**不是保留前缀（判据是「等于，或以 前缀+'/' 开头」，
    #    故 /APIXYZ 与 /API-HEALTH 都归 fallback —— 与改前逐字同形，那一格是本条存在的理由）
    for path in ("/APIXYZ", "/API-HEALTH", "/Apixyz", "/api-health"):
        assert not static.is_reserved(path), path

    # ④ 大小写不敏感那一份清单是 RESERVED_PREFIXES 的**子集**、且一律小写
    #    （往它里面加一个大写串会让第二趟判据变成永假；加一个不在清单里的串会让
    #    「一个前端路由的大小写变体突然 404」——两档都当场红在这一拍上）
    ci = static.RESERVED_PREFIXES_CASE_INSENSITIVE
    assert ci, "大小写不敏感那一份清单空了 ⇒ ① 那八格无从成立"
    assert set(ci) <= set(static.RESERVED_PREFIXES), (ci, static.RESERVED_PREFIXES)
    assert all(p == p.lower() and p.startswith("/") for p in ci), ci


def test_an_uppercase_api_path_answers_the_unified_404_and_not_index_html(spa_client):
    """:func:`test_the_api_prefix_is_matched_case_insensitively_but_the_human_routes_are_not`
    的 **HTTP 层**那一半（Plan 06 Task 15 / 终审 S4-①）。

    ⚠️ 三格反空转，缺一不可：
    ① 小写那一条真端点照旧 **200**（否则「一律 404」也会绿）；
    ② ``/DOCS`` 与 ``/LOGIN`` 照旧回 **index.html**（本波刻意不动的那两档，
       少了这两拍，「把 is_reserved 整个改成大小写不敏感」会是绿的 ——
       而那正是终审点名不要的形状）；
    ③ 那一族 404 的响应体是 ``app/api/errors.py`` 那个统一形状，不是纯文本。
    """
    for path in ("/API/health", "/Api/Health", "/apI/HEALTH", "/API/nope", "/API/"):
        response = spa_client.get(path)
        assert response.status_code == 404, (path, response.status_code)
        assert response.headers["content-type"].startswith("application/json"), path
        assert response.json()["error"]["code"] == "not_found", path
        assert "PE-SPA-FIXTURE" not in response.text, path

    ok = spa_client.get("/api/health")
    assert ok.status_code == 200, ok.status_code
    assert ok.headers["content-type"].startswith("application/json")
    assert ok.json()["status"] == "ok"

    for path in ("/DOCS", "/LOGIN"):
        fallback = spa_client.get(path)
        assert fallback.status_code == 200, (path, fallback.status_code)
        assert "PE-SPA-FIXTURE" in fallback.text, path


def test_resolve_static_path_answers_exactly_the_four_documented_cases(dist):
    """:func:`app.static.resolve_static_path` 的**四**档（模块 docstring 里那张表）。

    ⚠️ 函数名此前是 ``…three_documented_cases``：Plan 06 Task 11 / B1 给它加了第四档
    （**在要静态产物文件**而磁盘上没有它 → ``None``），故按事实改名（硬规矩 #66）。
    ⚠️ 前三档的期望值**一个字都没改**——那一格是本件的验收之一
    （派单 §2 B1 逐字要求「不许影响任何真实存在的静态文件、不许影响前端路由深链接」）。
    """
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
    # ⚠️ 而裸 ``/assets`` **不是** :func:`app.static.is_asset_request`（判据是
    #    「以 ``/assets/`` 开头」，带那个结尾的斜杠），故 B1 那一格不改它。
    assert static.resolve_static_path(dist, "/assets") == index
    assert not static.is_asset_request("/assets")

    # 档 4（Plan 06 Task 11 / B1）：**在要一个静态产物文件**而磁盘上没有它 → None（→ 404）
    for path in (
        "/assets/does-not-exist.js",
        "/assets/index-DEADBEEF.css",
        "/assets/nope.woff2",
        "/robots.txt",          # 根级 + 一个本模块认得的扩展名
        "/favicon.ico",
        "/site.webmanifest",
    ):
        assert static.resolve_static_path(dist, path) is None, path

    # ⚠️ 而**多段**路径不在档 4 里（逐字理由见 :func:`app.static.is_asset_request`
    #    的 docstring 第二节）：一个字面的 ``%2e%2e`` 仍然走 fallback。
    assert static.resolve_static_path(dist, "/%2e%2e/secret.txt") == index
    assert static.resolve_static_path(dist, "/a/b/robots.txt") == index


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
    ``/assets/%2e%2e/secret.txt``      ``/assets/../secret.txt``    404     统一 404
    ``/../secret.txt``（**字面**）      ``/secret.txt``              404     统一 404
    ================================  ==========================  ======  ===========

    ⚠️⚠️ **Plan 06 Task 11 / B1 把第 3、4 行从 200 改成了 404**（此前它们走 SPA
    fallback、回一份 index.html）。逐字理由：那两个 ``scope["path"]``
    （``/assets/../secret.txt`` 与 ``/secret.txt``）都是**在要一个静态产物文件**
    而 ``dist`` 里没有它 —— 一个 200 的 ``text/html`` 对运维说的是一句假话
    （它宣称「这是一个合法的前端路由」），而 404 说的是真话。
    ⚠️ **本条的判据一格都没变**：它要的从来只是「没有一行发出那个秘密文件的字节」，
    而 200 index.html 与 404 统一形状**都**满足它。故那是一次「更诚实」的改动、
    不是一次安全性改动。
    ⚠️ 第 3 行**不是**穿越——它 resolve 到 ``dist/secret.txt``（仍在 ``dist`` 内）；
    第 4 行的**字面** ``/../`` 到不了服务端：``httpx`` 在拼 URL 时就把点段折掉了
    （连 ``raw_path`` 都是 ``b'/secret.txt'``），故「字面 ``..``」这一档在 HTTP 层
    **无法表达**，只有判据层那一条测得到它。
    """
    secret = tmp_path / "secret.txt"
    assert secret.is_file() and secret.read_bytes() == SECRET_BODY
    # ⚠️ 反空转：dist 里面**没有**一个叫 secret.txt 的东西（否则「404 / index.html」
    #    可能只是「它被当成 dist 内的一个正常文件发出去了」）。
    assert not (tmp_path / "dist" / "secret.txt").exists()
    assert not (tmp_path / "dist" / "assets" / "secret.txt").exists()

    #: ⚠️ 六格**一律 404**（Plan 06 Task 11 / B1 之后；此前后四格是 200 index.html，
    #:    逐字理由见上面那张表下面那一段）。
    matrix = (
        ("/%2e%2e/secret.txt", 404),
        ("/assets/%2e%2e/%2e%2e/secret.txt", 404),
        ("/assets/%2E%2E/secret.txt", 404),
        ("/assets/%2e%2e/secret.txt", 404),
        ("/../secret.txt", 404),
        ("/assets/../../secret.txt", 404),
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

    # ⚠️ 反空转（Plan 06 Task 11 / B1 把六格都改成 404 之后**必需**）：
    #    证明这个应用**不是**「什么都 404」——一个前端深链接与一个真产物文件都还是 200。
    assert spa_client.get("/login").content == INDEX_BODY
    assert spa_client.get("/assets/app.js").content == JS_BODY


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


#: Task 7 那张 **13 格 fallback 矩阵**（``.superpowers/sdd/2026-10-13-…/task-7-report.md``
#: 的 §③ 前 13 行，逐格实测于产品档）。⚠️ 它是 :data:`FRONTEND_DEEP_LINKS` 的**超集**
#: （多出 ``/admin/``、``/apixyz``、``/documentary`` 三格：后两格是「以某个保留前缀
#: **开头**、却不是它的子路径」那一档，逐字理由见 :func:`app.static.is_reserved`）。
#: ⚠️ Plan 06 Task 11 / B1 之后本清单**一格都不许变**：它们一条都不带扩展名、
#: 也都不在 ``/assets/`` 下面，故 :func:`app.static.is_asset_request` 对它们恒为假。
THIRTEEN_FALLBACK_CELLS = (
    "/",
    "/login",
    "/bind",
    "/s/home",
    "/s/weekly-sheet",
    "/t/dashboard",
    "/t/students/1",
    "/admin",
    "/admin/",
    "/admin/students/1",
    "/this-route-does-not-exist",
    "/apixyz",
    "/documentary",
)

#: ``dist`` 里**真存在**的四个产物文件（``dist`` 夹具铺的那四个）。
FOUR_REAL_ASSETS = (
    ("/assets/app.js", JS_BODY, "text/javascript"),
    ("/assets/app.css", CSS_BODY, "text/css"),
    ("/assets/logo.svg", SVG_BODY, "image/svg+xml"),
    ("/assets/font.woff2", WOFF2_BODY, "font/woff2"),
)

#: **不存在**的产物文件（Plan 06 Task 11 / B1 的那一格：一律 404，不是 200 index.html）。
#: ⚠️ 头两格是 Task 7 报告 §③ 里那条待清扫的**原句**（``/assets/does-not-exist.js``），
#: 后四格是派单点名的「``/*.svg``、``/*.woff2`` 这类**根级**静态文件」。
MISSING_PRODUCT_FILES = (
    "/assets/does-not-exist.js",
    "/assets/index-DEADBEEF.css",
    "/assets/xmu-emblem-not-hashed.svg",
    "/robots.txt",
    "/favicon.ico",
    "/site.webmanifest",
)

#: ``/api`` 那四个面（派单 §2 B2 第 ③ 条：一个字节都不许受影响）。
FOUR_API_FACES = ("/api/health", "/openapi.json", "/docs", "/redoc")


def test_is_asset_request_draws_its_boundary_on_the_assets_dir_and_a_root_static_suffix():
    """:func:`app.static.is_asset_request` 的红绿两档矩阵（Plan 06 Task 11 / B1）。

    ⚠️ 最后那一组是**本条存在的理由**：一个「凡是带扩展名就算」的判据会把
    ``/%2e%2e/secret.txt``（多段）也收进来，而那一格今天走 fallback 是**有意的**
    （逐字理由见 :func:`app.static.is_asset_request` 的 docstring 第二节）。
    ⚠️ 反空转：``ASSETS_PREFIX`` 逐字是 ``/assets/``（带那个结尾的斜杠），
    故裸 ``/assets`` 为假 —— 那让「一个目录」与「一个目录下的文件」分成两档。
    """
    assert static.ASSETS_PREFIX == "/assets/"
    assert static.ASSETS_URL_DIR == "assets"

    for path in (
        "/assets/app.js",
        "/assets/index-DaycGB6S.js",
        "/assets/hanken-grotesk-var-latin-CaVRRdDk.woff2",
        "/assets/",                       # 目录本身（带斜杠）→ 在要它下面的东西
        "/assets/does-not-exist.js",
        "/robots.txt",                    # 根级 + 认得的扩展名
        "/favicon.ico",
        "/index.html",
        "/APP.JS",                        # ⚠️ 不在 /assets/ 下、且扩展名大写 → 也算
    ):
        assert static.is_asset_request(path), path

    for path in (
        "",
        "/",
        "/assets",                        # ⚠️ 裸目录名（没有结尾那个斜杠）→ **不算**
        "/login",
        "/s/home",
        "/admin/students/1",
        "/this-route-does-not-exist",
        "/apixyz",
        "/%2e%2e/secret.txt",             # 多段 → 不算（docstring 第二节）
        "/a/b/robots.txt",                # 多段 → 不算
        "/assetss/app.js",                # ⚠️ 边界是那个斜杠，不是裸前缀
        "/no-extension",
        "/thing.xyz",                     # 认不出的扩展名 → 不算（交给 fallback）
    ):
        assert not static.is_asset_request(path), path


def test_a_missing_product_file_answers_the_unified_404_and_the_thirteen_cells_still_fall_back(
    spa_client,
):
    """**B1 的正反两面**：不存在的产物文件 → 统一 404；13 格 fallback → 一格都不变。

    ------------------------------------------------------------------------
    ① 反面（改前那一格）
    ------------------------------------------------------------------------
    改前 ``GET /assets/does-not-exist.js`` 回的是 **200 + ``text/html``**
    （Task 7 报告 §③ 的实测表逐字记着它，并把它登记成待清扫）。两处坏：

    * 浏览器按 ES module 的**严格 MIME 检查**当场拒掉它 → **白屏** +
      一行 ``Failed to load module script: … MIME type of "text/html"``，
      而真因是「那一个带哈希的文件名不存在」（``dist`` 没构建、或 ``index.html``
      与 ``assets/`` 不同代）；
    * 运维**看不出**是「文件没构建出来」还是「路由打错了」：两档都回 200，
      而 200 宣称的是「这是一个合法的前端路由」——一句假话。

    ⚠️ 改后它与 ``/api/nope`` **同款**（404 + ``{"error": {"code": "not_found", …}}``
    + ``application/json``），派单 §2 B1 逐字要求的就是那个形状。

    ------------------------------------------------------------------------
    ② 正面（派单 §2 B1 逐字要求「不许影响」的三件事）
    ------------------------------------------------------------------------
    * Task 7 那张 **13 格 fallback 矩阵**逐格复跑，一格都不许变；
    * ``dist`` 里**真存在**的四个产物文件照旧 200 + 原字节 + 对的 ``content-type``；
    * ``/api/*`` 的那四个面一格都不许变（由
      :func:`test_no_cache_control_is_added_to_the_api_the_contract_or_the_two_doc_pages`
      与既有的 :func:`test_the_api_the_contract_and_the_two_doc_pages_are_not_shadowed` 管）。
    """
    # ① 不存在的产物文件 → 统一 404
    for path in MISSING_PRODUCT_FILES:
        response = spa_client.get(path)
        assert response.status_code == 404, (path, response.status_code)
        assert response.headers["content-type"].startswith("application/json"), (
            path, response.headers["content-type"]
        )
        assert response.json()["error"]["code"] == "not_found", path
        assert "PE-SPA-FIXTURE" not in response.text, (
            f"{path} 回了 index.html —— 它该是 404（B1）"
        )
        # ⚠️ HEAD 同答（``_SpaRoute`` 收 GET 与 HEAD 两个方法）
        assert spa_client.head(path).status_code == 404, path

    # ② 13 格 fallback 矩阵逐格复跑（⚠️ 一个字节都不许变）
    assert len(THIRTEEN_FALLBACK_CELLS) == 13, THIRTEEN_FALLBACK_CELLS
    for path in THIRTEEN_FALLBACK_CELLS:
        response = spa_client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.headers["content-type"].startswith("text/html"), path
        assert response.content == INDEX_BODY, path

    # ③ 真存在的产物文件照旧
    for path, body, media in FOUR_REAL_ASSETS:
        response = spa_client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith(media), (
            path, response.headers["content-type"]
        )
        assert response.content == body, path


def test_fingerprinted_assets_are_immutable_while_the_entry_document_is_revalidated(
    spa_client,
):
    """**B2 的两类缓存头**（改前产品档一个缓存头都没有）。

    ================================  ==========================================================
    发的东西                            ``Cache-Control``
    ================================  ==========================================================
    ``/assets/*``（文件名带内容哈希）    ``public, max-age=31536000, immutable``
    ``index.html``（**含 13 格 fallback**） ``no-cache``
    ================================  ==========================================================

    ⚠️⚠️ 第 2 行是派单 §2 B2 第 ② 条逐字点名的一格，而**理由是一条会自愈不了的事故**：
    ``index.html`` 是唯一引用那些带哈希文件名的地方，而它自己的名字**不带**哈希。
    给它长缓存的话，甲方升级之后用户拿到的仍是**旧的** ``index.html``，
    它引用的是**旧哈希**的 ``/assets/index-<旧>.js`` —— 那些文件在新构建里已经不存在了，
    于是每一屏白屏 + 一行 ``Failed to load module script``，
    且**不会自愈**（要等 ``max-age`` 走完）。

    ⚠️ 而 ``no-cache`` **不是** ``no-store``：它的语义是「缓存可以留、但每次用之前
    必须回源校验」，配合 ``FileResponse`` 自带的 ``etag`` / ``last-modified``，
    产物没变时那一次校验是一个 **304**（没有响应体）。逐字理由（含「为什么不选
    ``no-store``」）见 :data:`app.static.NO_CACHE`。

    ⚠️ **13 格 fallback 也必须拿到 ``no-cache``**，而这一格最容易漏：
    判据是「**发的那个文件**是不是 ``index.html``」（:func:`app.static.cache_control_for`），
    不是「URL 是不是 ``/index.html``」——按 URL 判的话 ``/t/dashboard`` 那一格
    一个缓存头都拿不到，浏览器会按**启发式**缓存它（``Last-Modified`` 距今的 10%），
    于是上面那场事故照样发生、只是搬了个 URL。
    """
    immutable = "public, max-age=31536000, immutable"
    assert static.IMMUTABLE_CACHE_CONTROL == immutable
    assert static.NO_CACHE == "no-cache"

    # ① 带哈希的产物 → immutable（⚠️ 逐字比，不比子串：少一个 ``immutable``
    #    就等于「每次刷新都对 28 个文件各发一个条件请求」）
    for path, _body, _media in FOUR_REAL_ASSETS:
        got = spa_client.get(path)
        assert got.status_code == 200, path
        assert got.headers["cache-control"] == immutable, (path, got.headers["cache-control"])
    # HEAD 同答（浏览器的预取走它）
    assert spa_client.head("/assets/app.js").headers["cache-control"] == immutable

    # ② 入口文档 → no-cache：**直接请求它**与**经 13 格 fallback 拿到它**两档同答
    assert spa_client.get("/index.html").headers["cache-control"] == "no-cache"
    for path in THIRTEEN_FALLBACK_CELLS:
        got = spa_client.get(path)
        assert got.headers["cache-control"] == "no-cache", (path, got.headers["cache-control"])

    # ③ 反空转：那些响应**真的**带着可校验的东西（没有 etag 的话 no-cache
    #    就退化成「每次全量重下」，而那不是本档要的形状）
    entry = spa_client.get("/login")
    assert entry.headers.get("etag"), dict(entry.headers)
    assert entry.headers.get("last-modified"), dict(entry.headers)

    # ④ 404 那一档**不带**任何缓存头（一个 not_found 不该被中间缓存存下来：
    #    甲方运维补上一次构建之后，那一个 404 必须**当场**消失）
    for path in MISSING_PRODUCT_FILES:
        got = spa_client.get(path)
        assert got.status_code == 404, path
        assert "cache-control" not in got.headers, (path, dict(got.headers))


def test_no_cache_control_is_added_to_the_api_the_contract_or_the_two_doc_pages(spa_client):
    """**B2 的反向断言**（派单 §2 B2 第 ③ 条）：``/api/*`` / ``/openapi.json`` / ``/docs`` /
    ``/redoc`` 一个字节都不许受影响。

    ⚠️ 它是 spec §13.11.2 那一条（「产品档不改 ``/api`` 的任何一格可观察行为」）
    在**响应头**这一维上的落地。⚠️ 而本条**刻意比的是「给了 ``static_dist`` 与不给，
    两份响应头逐字相同」**而不是「产品档上没有 cache-control」：后者是一份单侧断言，
    它证明不了「产品档没有**加**什么」（若 FastAPI 哪天自己给 ``/docs`` 挂上一条，
    单侧断言会红在一个与本件无关的地方，而下一个人会去改断言）。

    ⚠️ 五格逐个（四个面 + 一个 404）：``/api/nope`` 也在里面，因为它是
    「产品档才存在的那一档」（dev 档下它由框架的 404 处理器给，形状相同、
    但走的是另一条路），而 B1 恰好改的就是「哪些路径落到那个 404 上」。
    """
    probes = FOUR_API_FACES + ("/api/nope",)

    dev = TestClient(create_app(db_url="sqlite://"))
    with dev:
        for path in probes:
            production = spa_client.get(path)
            development = dev.get(path)
            assert production.status_code == development.status_code, (
                path, production.status_code, development.status_code
            )
            # ⚠️ ``date`` 刻意排掉：它是**发出响应那一刻**的时钟，两次请求之间会走
            #    （一秒一跳），比它等于给本条装了一个偶发的红。
            skip = {"date"}
            prod_headers = {k: v for k, v in production.headers.items() if k.lower() not in skip}
            dev_headers = {k: v for k, v in development.headers.items() if k.lower() not in skip}
            assert prod_headers == dev_headers, (
                f"{path} 的响应头在产品档与 dev 档之间不同："
                f"产品档 {prod_headers} / dev 档 {dev_headers}"
            )
            # ⚠️ 而「相同」还不够，还要**真的没有**缓存头（否则两档一起被污染也是绿的）
            assert "cache-control" not in production.headers, (path, dict(production.headers))
            assert production.content == development.content, path


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


# ===========================================================================
# ⑤ ``scripts/serve.ps1``：那一条命令（派单 §1 的第 1 / 2 / 6 / 7 条）
# ===========================================================================


def _serve_ps1_code() -> str:
    """``serve.ps1`` 的**代码段**（``#>`` 之后那一部分）。

    ⚠️ **只扫代码段**：``<# .DESCRIPTION #>`` 里会**提及**若干它刻意不做的事
    （``-Prod``、演示口令的唯一所有者、三个禁区 CLI 的名字），扫整个文件会红在
    自己的说明文字上（硬规矩 #109）。``tests/test_backup_restore.py`` 的
    ``.ps1`` 那一条首跑实测踩过这一格，逐字记在它的注释里，本处沿用同一切法。
    """
    raw = SERVE_PS1.read_bytes()
    body = raw[3:].decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    assert body.count("#>") == 1, "serve.ps1 的注释块形状变了，本函数的切法要跟着改"
    return body.split("#>", 1)[1]


def test_serve_ps1_lives_at_the_repo_root_and_not_under_backend_scripts():
    """它在**仓库根**的 ``scripts/`` 下（派单 §1 第 1 条），且不与 ``backend/scripts/`` 重名。

    ⚠️ 两层理由：① 它同时碰 ``frontend/`` 与 ``backend/``，故它不属于任何一包；
    ② ``backend/scripts/`` 下今天已经有 ``demo.ps1`` / ``backup.ps1`` / ``restore.ps1``
    三个，而那三个的守卫（``tests/test_backup_restore.py``）是按 ``SCRIPTS_DIR``
    枚举的 —— 把 ``serve.ps1`` 放进那一层会让「哪几个 .ps1 归谁守」这件事变糊。
    """
    assert SERVE_PS1.is_file(), SERVE_PS1
    assert SERVE_PS1.parent.name == "scripts"
    # ⚠️ 不用 `SERVE_PS1.parent.parent == REPO_ROOT`：REPO_ROOT 就是从 BACKEND_DIR
    #    推出来的，那样写是**同义反复**。改成「那个 scripts/ 与 backend/ 是兄弟」，
    #    两侧于是各自独立（一侧走文件系统、一侧走 app.config 的常量）。
    assert SERVE_PS1.resolve().parent.parent / "backend" == BACKEND_DIR
    assert not (SCRIPTS_DIR / "serve.ps1").exists(), (
        "backend/scripts/serve.ps1 也出现了：那一条命令应当只有一个住址"
    )
    # ⚠️ 反空转：仓库根的 scripts/ 里今天**只有**它一个文件（多出来的东西要显式登记）
    assert sorted(p.name for p in SERVE_PS1.parent.iterdir()) == ["serve.ps1"]


def test_serve_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo():
    """**UTF-8 + BOM + 纯 CRLF**，与本仓另外三个 ``.ps1`` 同款。

    ⚠️ BOM 是承重的、不是洁癖：PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1`` 时按
    系统 ANSI 代码页（本机 GBK）解码，而本文件的注释里全是 UTF-8 中文——
    轻则注释乱码，重则某个字节序列里出现一个引号/反引号把语法弄坏
    （上一波实现者被工具剥过一次 BOM，原地复现过解析失败）。
    ⚠️ 三拍与 ``tests/test_backup_restore.py`` 的同名一条逐字同款：
    ① BOM + 0 个裸 LF；② 去掉 BOM 之后能按 UTF-8 解码；③ 与 ``demo.ps1`` 同形状。
    """
    raw = SERVE_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "serve.ps1 没有 BOM（PowerShell 5.1 会按 GBK 读它）"
    body = raw[3:]
    crlf = body.count(b"\r\n")
    bare = body.count(b"\n") - crlf
    assert bare == 0, f"serve.ps1 有 {bare} 个裸 LF（本仓的 .ps1 一律 CRLF）"
    assert crlf > 100, f"serve.ps1 只有 {crlf} 行，可能不是一个完整的脚本"
    body.decode("utf-8")

    demo = (SCRIPTS_DIR / "demo.ps1").read_bytes()
    assert demo[:3] == b"\xef\xbb\xbf" and demo[3:].count(b"\n") == demo[3:].count(b"\r\n"), (
        "既有那一款 demo.ps1 的形状变了，本条的「同款」判据要跟着改"
    )


def test_serve_ps1_has_exactly_the_two_documented_switches_and_no_prod_switch():
    """开关恰好两个：``-Port``（缺省 **8020**）与 ``-SkipBuild``；**没有** ``-Prod``。

    ⚠️ 「没有 ``-Prod``」是派单 §1 第 6 条逐字要求的，而它的理由是**语义**的：
    档位（``PE_ENV``）是一个**部署事实**，归运维的环境变量；做成一个命令行旗标
    会让人以为「加了它就安全了」，而它其实还要 ``PE_CORS_ORIGINS``、``Secure`` cookie
    与一层 TLS 反代（:func:`app.main._selfcheck_prod` 会把前两格验一遍，
    而第三格它验不到）。⚠️ 于是本条挡的是「有人图方便加一个 ``-Prod``」，
    而 ``test_serve_ps1_prints_the_prod_tier_reminder_instead_of_offering_a_switch`` 挡的是另一半
    （「不加旗标」不等于「不告诉运维怎么上生产」）。
    """
    code = _serve_ps1_code()
    start = code.index("param(")
    block = code[start:code.index(")", start)]
    assert sorted(re.findall(r"\$(\w+)", block)) == ["Port", "SkipBuild"], block
    assert "[int]$Port = 8020" in block, block
    assert "[switch]$SkipBuild" in block, block
    # ⚠️ `-Prod` / `$Prod` 只在 **param 块**里断「不在」，不在整段代码里断：
    #    ⑤ 那一句 Write-Host 逐字**提及**了「本脚本刻意没有 -Prod 开关」
    #    （那是本条要它说的话），而提及不是本身（硬规矩 #109）。
    #    ⚠️ `[switch]$Prod` 那一格则在整段代码里断——它是一个**声明**的形状，
    #    散文里不会出现，故它抓住的只可能是真的有人加了那个开关。
    assert "-Prod" not in block and "$Prod" not in block, block
    assert "[switch]$Prod" not in code


def test_serve_ps1_runs_the_five_documented_steps_in_order():
    """派单 §1 第 2 条那五步**逐个在场、且顺序对**。

    ⚠️ 顺序是承重的两处：
    ② 必须在 ③ 之前（``PE_STATIC_DIST`` 指过去的那个目录得先存在）；
    ④ 必须在 ③ 之后（健康检查要打的那个进程得先起来）——
    而 ③ 是**前台阻塞**的，故本脚本用 ``Start-Process -PassThru -NoNewWindow``
    起子进程、轮询健康、打印，最后 ``WaitForExit()``：既满足「运维看得见日志、
    Ctrl-C 停」，又让 ④ 有机会跑（:func:`test_serve_ps1_blocks_in_the_foreground_and_cleans_up_its_child`）。
    """
    code = _serve_ps1_code()
    marks = [
        "-- ① 检查工具链 --",
        "-- ② 前端构建产物 --",
        "-- ③ 起产品档 --",
        "-- ④ 健康检查 --",
        "-- ⑤ 产品档起着",
    ]
    positions = []
    for mark in marks:
        assert code.count(mark) == 1, f"{mark!r} 在代码段里出现了 {code.count(mark)} 次（应当恰好 1 次）"
        positions.append(code.index(mark))
    assert positions == sorted(positions), f"五步的顺序不对：{positions}"

    # ① 两个版本都要查，且**下界是字面的**（不从被测脚本反推）
    assert "$PythonExe --version" in code and "$NodeExe --version" in code
    assert "-lt 311" in code, "python 的下界 3.11（pyproject.toml 的 requires-python）不见了"
    assert "$NodeMajor -lt 20" in code, "node 的下界 20（vite 8 的下限）不见了"
    # ② 「不存在**或**比 src 旧」两档都要判，且要真的会跑构建
    assert "Test-Path $DistIndex" in code
    assert "LastWriteTimeUtc" in code, "「比 src 旧」的判据（mtime）不见了"
    assert "run build" in code and "$LASTEXITCODE -ne 0" in code
    # ③ 一个进程、走 serve_app 那个入口、把产物目录交给它
    assert '"serve_app:app"' in code, "入口对象不是 backend/scripts/serve_app.py 的那个 app"
    assert '"--app-dir"' in code, "scripts/ 不是包，缺了 --app-dir 就 import 不到 serve_app"
    assert "$env:PE_STATIC_DIST = $Dist" in code
    # ④ 轮询 /api/health 直到 200
    assert "/api/health" in code and "Invoke-WebRequest" in code
    assert "$HealthTimeoutSeconds" in code
    # ⑤ 打印 URL 与账号
    assert "$Base/" in code and "T0003" in code


def test_serve_ps1_guards_the_pe_db_forbidden_zone():
    """``backend/pe.db`` 那道禁区守卫（与 ``demo.ps1`` 的 ⑤、``backup.py`` 同一条姿势）。

    ⚠️ 两格：① ``PE_DB_URL`` 未设时**回落到 ``app.main.DEMO_DB_URL``**
    （那是「演示库叫什么」的唯一所有者，本脚本不敲第二遍路径），
    而**不是**回落到 ``app.config.DEFAULT_DB_URL``（那一个逐字指向禁区）；
    ② 解析出来的 URL 若以 ``pe.db`` 结尾就当场 ``throw``。
    ⚠️ 少了本条，一次 ``$env:PE_DB_URL = ""`` 或一次手滑就会让产品档在
    ``backend/`` 下建出 ``pe.db``——而那是本仓收工清单上「不得存在」的第一格。
    """
    code = _serve_ps1_code()
    assert "from app.main import DEMO_DB_URL" in code, (
        "演示库的路径必须从 app.main.DEMO_DB_URL 读（单一所有者），不许在这里敲第二遍"
    )
    assert "DEFAULT_DB_URL" not in code, "它回落到了 DEFAULT_DB_URL（= 禁区 pe.db）"
    assert "pe\\.db" in code and "throw" in code, "禁区守卫不见了"
    # ⚠️ 那条禁区路径**至多提及一次**（在 throw 的那一句报错里，运维要看得懂）。
    #    它是 ``app.config.DEFAULT_DB_URL`` 的字面值，抄第二遍就是第二个所有者。
    assert code.count("backend\\pe.db") <= 1, code.count("backend\\pe.db")


def test_serve_ps1_blocks_in_the_foreground_and_cleans_up_its_child():
    """**前台阻塞**（控制者裁定，与 ``demo.ps1`` 同姿势），而 ``finally`` 兜住子进程。

    ⚠️ 两格各挡一档：
    ① ``WaitForExit()`` —— 少了它，脚本会在起完进程后立刻返回，
       运维看到「命令跑完了」而服务在后台无人看着（日志也没有了去处）；
    ② ``finally`` 里的 ``Stop-Process`` —— 少了它，一次 ``Ctrl-C`` 或一次
       ``throw``（例如健康检查超时）会留下一个**占着端口的孤儿 uvicorn**，
       而下一个人撞上去时看到的是一句 ``WinError 10048``，离真因有一层。
    ⚠️ ``-NoNewWindow`` 也是承重的：子进程因此与脚本**共用同一个控制台**，
    于是 uvicorn 的日志照常打在屏幕上（①那一格的全部意义），
    而 ``Ctrl-C`` 也会同时送到两边。
    """
    code = _serve_ps1_code()
    assert "Start-Process" in code and "-PassThru" in code and "-NoNewWindow" in code
    assert "$Proc.WaitForExit()" in code, "它不是前台阻塞的（脚本会在起完进程后立刻返回）"
    assert "finally" in code and "Stop-Process -Id $Proc.Id -Force" in code, (
        "没有 finally 兜底：一次 Ctrl-C 会留下一个占着端口的孤儿 uvicorn"
    )
    assert "exit $Code" in code, "它没有把 uvicorn 的退出码交回来"
    # ⚠️ 端口预检：被占着就报出那个 PID，而不是让 uvicorn 抛 WinError 10048
    assert "Get-NetTCPConnection -LocalPort $Port" in code


def test_serve_ps1_prints_the_prod_tier_reminder_instead_of_offering_a_switch():
    """它**打印**「要上 HTTPS 反代请设 ``PE_ENV=prod`` 与 ``PE_CORS_ORIGINS`」这一行提醒。

    ⚠️ 与 :func:`test_serve_ps1_has_exactly_the_two_documented_switches_and_no_prod_switch`
    是一对：那一条挡「加了 ``-Prod`` 旗标」，本条挡「不加旗标、于是运维根本不知道
    生产档怎么开」。⚠️ 而它同时把「明文 http 上跑 prod 档会被浏览器拒收 cookie」
    那一格说出来（:func:`app.auth.sessions.cookie_secure` 只在 prod 回 ``True``，
    于是 ``http://`` 上的 ``Secure`` cookie 一律被丢掉，症状是「登录 200、下一个请求 401」）
    ——那正是本脚本**缺省留在 dev 档**的理由。
    """
    code = _serve_ps1_code()
    assert "PE_ENV=prod" in code and "PE_CORS_ORIGINS" in code
    assert "Secure" in code and "401" in code, (
        "它没有把「明文 http 上 prod 档的 cookie 会被浏览器拒收」那一格说出来"
    )
    # ⚠️ 反空转：它打印的是**实测**的档位，而不是一句写死的「dev」
    assert "from app import deploy" in code and "cookie_secure" in code
    assert "$Tier" in code and "$CookieSecure" in code


#: ``PE_ALLOW_HEADER_IDENTITY`` 那一段在 ``demo.ps1`` 里的两个锚点。⚠️ 它们是
#: **切片的边界**、不是期望值本身：期望值是切出来的那一段**原文**，
#: 故「两份漂了」这件事由 demo.ps1 那一个文件说了算（单一所有者）。
_HEADER_IDENTITY_START = "$HeaderIdentityInherited = [Environment]::GetEnvironmentVariable"
_HEADER_IDENTITY_END = (
    "$HeaderIdentityNowShown = if ([string]::IsNullOrEmpty($HeaderIdentityNow)) "
    "{ '未设' } else { '=' + $HeaderIdentityNow }"
)


def _demo_ps1_header_identity_block() -> str:
    """从 ``backend/scripts/demo.ps1`` 里**现场切出**强制清那一段（含它上面那一行注释）。

    ⚠️ 它是「这个开关怎么关」在全仓的**单一所有者**：``serve.ps1`` 逐字抄它，
    而本函数**每次现读那个文件**，故 demo.ps1 改了而 serve.ps1 没跟上 → 守卫当场红。
    ⚠️ 两侧因此**不同源**（硬规矩 #35）：期望侧是 demo.ps1 的文件内容，
    被测侧是 serve.ps1 的文件内容，本函数不持有任何一份字面副本。
    """
    demo = (SCRIPTS_DIR / "demo.ps1").read_bytes()
    assert demo[:3] == b"\xef\xbb\xbf", "demo.ps1 没有 BOM，本函数的解码姿势要跟着改"
    text = demo[3:].decode("utf-8")
    assert text.count(_HEADER_IDENTITY_START) == 1, "demo.ps1 里那一段的锚点不唯一了"
    start = text.index(_HEADER_IDENTITY_START)
    end = text.index(_HEADER_IDENTITY_END, start) + len(_HEADER_IDENTITY_END)
    block = text[start:end]
    # ⚠️ 反空转：切出来的必须是**那一段**、不是一个空串（锚点写错时 index() 会给出
    #    一个 start > end 的区间，切片于是安静地回一个空串，而「serve.ps1 里有它」恒真）。
    assert block.count("\n") >= 7, f"切出来只有 {block.count(chr(10)) + 1} 行：{block[:200]!r}"
    assert "Remove-Item Env:\\PE_ALLOW_HEADER_IDENTITY" in block, block[:400]
    assert "throw" in block, block[:400]
    return block


def test_serve_ps1_force_clears_the_header_identity_channel_with_the_same_lines_demo_ps1_uses():
    """**产品档也强制关掉请求头身份通道**，而且用的是 ``demo.ps1`` **逐字相同**的那一段。

    ------------------------------------------------------------------------
    ⚠️ 改前那一格是什么（Plan 06 Task 7 留下、Plan 06 Task 11 / B3 收掉）
    ------------------------------------------------------------------------
    改前 ``serve.ps1`` 只**打印**实测值 + 一句 ⚠️，原文逐字是「生产档（PE_ENV=prod）下
    app.api.deps 一律忽略它；本脚本**不**替你清掉它（与 demo.ps1 不同：那一个是演示、
    必须强制关；本脚本是部署入口，开关归运维）」。

    ⚠️⚠️ 那句话的**前半句是对的、后半句是危险的**：产品档确实缺省留在 **dev** 档
    （Task 7 的裁定：同源 http 上跑 prod 档，浏览器会拒收 ``Secure`` cookie，
    症状是「登录 200、下一个请求 401」），而 ``app.api.deps.allow_header_identity()``
    **只在 ``PE_ENV=prod`` 下恒回 False**。于是「dev 档 + 运维不小心设了那个变量」
    = **请求头身份通道开着** —— ``X-Student-Id`` / ``X-Teacher-Staff-No``
    没有签名、没有过期、没有吊销，任何人都可以自称任何学号（**含管理员那个工号**）。
    那一档不是「多一个调试口子」，它是**绕过整个鉴权**。
    ⚠️ 而它的失效方向是静默的：服务照常起、健康检查照常 200、
    脚本只印一行 ⚠️（在一个几十行的启动输出里）。

    ------------------------------------------------------------------------
    ⚠️ 四拍
    ------------------------------------------------------------------------
    ① **逐字同款**：demo.ps1 里那一段（:func:`_demo_ps1_header_identity_block` 现切）
       在 serve.ps1 的代码段里**逐字**出现。⚠️ 派单 §2 B3 第 ① 条逐字要求
       「照同一姿势，**不要写第二套**」——本拍把那一句做成可执行的：
       两份漂了（例如有人只给 demo.ps1 加了一格）当场红；
    ② **改前那句「不替你清掉它」不在了**（它现在是一句假话）；
    ③ **顺序**：那一次 ``Remove-Item`` 排在 ``Start-Process``（起 uvicorn 子进程）
       **之前** —— 子进程继承的是本进程**当时**的环境块，清晚了等于没清；
    ④ **打印的是实测值**（两个变量都进那一行 Write-Host），不是一句写死的「未设」，
       且它说的是「已关闭」。
    """
    code = _serve_ps1_code()
    block = _demo_ps1_header_identity_block()

    # ① 逐字同款
    assert block in code, (
        "serve.ps1 里没有 demo.ps1 那一段的逐字副本 —— 它要么是**第二套**写法、"
        "要么根本没强制清。demo.ps1 那一段（期望侧，现读）：\n" + block
    )

    # ② 改前那一档（**只打印、不清**）不在了。
    #    ⚠️⚠️ 判据只扫**语句行**、把 `#` 开头的注释行滤掉：本条上面那一大段注释
    #    **逐字引用**了改前那句原文（「本脚本**不**替你清掉它……开关归运维」）来说明
    #    为什么改判，而**提及不是本身**（硬规矩 #109）——不滤的话本拍会红在自己的
    #    说明文字上，而下一个人「修」它的办法是删掉那段说明。
    statements = "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("#")
    )
    assert "本脚本**不**替你清掉它" not in statements, "改前那句「开关归运维」还在语句里"
    assert "开关归运维" not in statements
    # ⚠️ 改前那个**变量名**（裸 `$HeaderIdentity`，没有 `Inherited` / `Now` 两个后缀）
    #    也不在了 —— 它是「只读一次、只打印」那个形状的唯一落点。
    assert re.search(r"\$HeaderIdentity\s*=", statements) is None, (
        "改前那个只打印用的裸 $HeaderIdentity 变量还在（它读一次就只用来印一句 ⚠️）"
    )

    # ③ 顺序：强制清必须排在起子进程之前
    removed_at = code.index("Remove-Item Env:\\PE_ALLOW_HEADER_IDENTITY")
    started_at = code.index("Start-Process -FilePath $PythonExe")
    assert removed_at < started_at, (
        f"强制清（第 {removed_at} 个字符）排在起 uvicorn（第 {started_at} 个字符）之后："
        "子进程继承的是本进程当时的环境块，清晚了等于没清"
    )
    # ⚠️ 而它还必须排在**健康检查**之前（那一格是运维第一次能看见服务的时间点）
    assert removed_at < code.index("-- ④ 健康检查 --")

    # ④ 打印实测值
    printed = [line for line in code.splitlines()
               if "PE_ALLOW_HEADER_IDENTITY 进本脚本时实测" in line]
    assert len(printed) == 1, printed
    assert "$HeaderIdentityShown" in printed[0] and "$HeaderIdentityNowShown" in printed[0], printed
    assert "强制" in printed[0] and "已关闭" in printed[0], printed

    # ⚠️ 反空转：demo.ps1 那一段**真的**在 demo.ps1 里（否则 ① 会拿一个空串去比）
    demo_code = (SCRIPTS_DIR / "demo.ps1").read_bytes()[3:].decode("utf-8")
    assert block in demo_code


def test_serve_ps1_does_not_become_a_second_owner_of_the_demo_credentials():
    """演示口令与学号**一个都不许抄**在这里（单一所有者是 ``demo_bootstrap.py``）。

    ⚠️ 逐字理由与 ``demo.ps1`` 的那一段注释相同：抄第二份的话，改口令的人会漏改一处，
    而漏改的那一处是**演示时要念给甲方听的**那一处。``demo.ps1`` 因此只印
    「去哪一行找它」，本文件沿用同一条纪律。
    ⚠️ 而工号 ``T0001`` / ``T0002`` / ``T0003`` 是**允许**的：``demo.ps1`` 也逐字印它们
    （它们是名册生成规则 ``app/seed/population.py`` 的固定产物，不是秘密）。
    """
    code = _serve_ps1_code()
    whole = SERVE_PS1.read_bytes()[3:].decode("utf-8")
    for needle in ("pe-demo-2025", "DEMO_PASSWORD ="):
        assert needle not in whole, f"serve.ps1 里抄了一份 {needle!r}"
    assert not re.search(r"\b20\d{8}\b", whole), (
        "serve.ps1 里抄了一个学号形状的字面量：名册由 app/seed/population.py 现造，"
        "而 demo.ps1 曾因为抄了一个从来不在册的学号把演示带进 403（终审 I1）"
    )
    # ⚠️ 反空转：它**确实**把「去哪找口令」说清楚了，且指向那个唯一所有者
    assert "DEMO_PASSWORD" in code and "demo_bootstrap.py" in code
    assert "spec §13" in code


def test_serve_ps1_never_runs_one_of_the_three_forbidden_clis():
    """它**不灌数据**：``app.seed.generate`` / ``app.pipeline.backfill`` /
    ``app.pipeline.daily`` 三个 CLI 一个都不许出现。

    ⚠️ 那三个的 ``main()`` 各自把缺省值写死在**两个禁区**上
    （``backend/data/seed/`` 与 ``backend/pe.db``），故 ``demo.ps1`` 里
    「一条 ``python -m …`` 都没有」，本脚本沿用同一条纪律。
    ⚠️⚠️ 判据是「**调用**形状」而不是「模块名出现过」：③ a 那一句 ``throw`` 的报错里
    逐字解释了 ``pe.db`` 的语义（「它是 ``app.seed.generate`` 写出来的那份
    不可复现的库」），⑤ 那一段也**提及**了 ``demo_bootstrap.py`` 是演示口令的
    唯一所有者 —— 两处都是提及、不是调用（硬规矩 #109）。
    按裸模块名断的话本条会红在自己的说明文字上，而下一个人唯一的出路就是删掉
    那两句解释（``tests/test_backup_restore.py`` 的 ``.ps1`` 那一条首跑踩过同一格）。
    """
    whole = SERVE_PS1.read_bytes()[3:].decode("utf-8")
    code = _serve_ps1_code()
    # ① 一条 `python -m app.…` 都没有；唯一那次 `-m` 是起 uvicorn
    assert "-m app." not in whole, "它跑了一个 app 下面的 CLI（灌数据是 demo.ps1 的活）"
    assert code.count('"-m"') == 1, code.count('"-m"')
    assert '"-m", "uvicorn"' in code, "那唯一一次 -m 不是起 uvicorn"
    assert '"serve_app:app"' in code
    # ② python 一共只被**调**四次，逐个点名：① ``--version``（版本下界）
    #    ② ``-c 'from app.main import DEMO_DB_URL…'``（演示库的 URL，单一所有者）
    #    ③ ``-c 'from app import deploy…'``（档位自检）④ ``Start-Process``（uvicorn 本体）。
    #    ⚠️ 数的是**调用点**（``& $PythonExe`` / ``-FilePath $PythonExe``）而不是
    #    ``$PythonExe`` 这个名字：它在赋值、判空与两句报错文案里也出现。
    #    第五次调用就意味着本脚本自己做了一件它不该做的事（最可能的一档是灌数据）。
    assert code.count("& $PythonExe") == 3, code.count("& $PythonExe")
    assert code.count("-FilePath $PythonExe") == 1, code.count("-FilePath $PythonExe")
    assert code.count("-c 'from app.main import DEMO_DB_URL;print(DEMO_DB_URL)'") == 1
    assert "from app import deploy" in code and "cookie_secure" in code


# ===========================================================================
# ⑥ ``.gitattributes``：行尾钉扎（控制者裁定的两条；⚠️ 第二条被顶回并收窄）
# ===========================================================================


def _git(*args: str) -> str:
    """在**仓库根**跑一条 git 命令并要它的 stdout（失败当场 assert）。

    ⚠️ ``-c core.quotepath=false`` 是承重的：``Document/`` 下 10 个 ``.md`` 的名字
    全是中文，缺省下 git 会把它们转义成 ``"Document/2026-09-28-\\344\\275\\223…"``，
    于是下面那个按 ``path: attr: value`` 切三段的解析对不上号。
    """
    run = subprocess.run(
        ("git", "-c", "core.quotepath=false", *args),
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert run.returncode == 0, (args, run.stderr)
    return run.stdout


def _check_attr(*paths: str) -> dict[str, dict[str, str]]:
    """``git check-attr text eol binary -- <paths>`` → ``{路径: {属性: 值}}``。"""
    table: dict[str, dict[str, str]] = {}
    for line in _git("check-attr", "text", "eol", "binary", "--", *paths).splitlines():
        rest, _, value = line.rpartition(": ")
        path, _, name = rest.rpartition(": ")
        table.setdefault(path, {})[name] = value
    assert table, "check-attr 一行都没回，路径可能被指错了"
    return table


def test_gitattributes_pins_the_eol_of_every_ps1_and_nothing_binary():
    """三条钉扎**都生效**，而两条**不该被碰的**一格都没被碰。

    ⚠️ 控制者裁定的两条逐字是 ``backend/scripts/*.ps1`` 与 ``Document/**``。
    本波把第二条**顶回并收窄**成 ``Document/**/*.md``，理由是实测的：
    ``Document/`` 下 26 个入库文件里有 **15 个 ``.png``** 与 **1 个 ``.doc``**，
    而给 ``**`` 钉 ``text`` 会**关掉 git 的二进制启发式**（那 16 个今天报的是
    ``i/-text w/-text``），于是它们会被当文本做行尾转换。亲跑的取证
    （临时仓库 + 一次真 clone，``core.autocrlf=true``）：``shot-01-login.png`` 的
    入库 blob 从 142 509 B 变成 **142 507 B**，重新 clone 出来是 **142 891 B**、
    sha256 不同（+382 = 那 382 个裸 LF 各多一个 CR）。逐字取证写在
    ``.gitattributes`` 那一段注释与 spec §13.11.5 里。
    ⚠️ 故本条的**红档半边**是「二进制那一格必须是 ``unspecified``」：
    谁把 ``**/*.md`` 放宽回 ``**``，这一格当场红。
    """
    ps1 = [
        "scripts/serve.ps1",
        "backend/scripts/demo.ps1",
        "backend/scripts/backup.ps1",
        "backend/scripts/restore.ps1",
    ]
    markdown = [
        "Document/2026-09-28-体育闭环原型-设计spec.md",
        "Document/2026-10-13-实施计划06-产品级硬化.md",
    ]
    binaries = [
        "Document/shot-01-login.png",
        "Document/shot-11-t-alerts.png",
        "Document/数智驱动的高校公共体育教学和反馈系统设计与实现.doc",
    ]
    untouched = [
        # ⚠️ backend/data/** 的 LF 钉扎：四个数据指纹 + 18 个模板指纹的落脚点
        "backend/data/national_standard_2014.csv",
        "backend/data/alert_rules.yaml",
        "backend/data/README_national_standard.md",
        "backend/data/prescription/RED-END-ABN-01.yaml",
        # ⚠️ woff2 的 binary 与品牌 svg 的 -text
        "frontend/src/assets/fonts/hanken-grotesk-var-latin.woff2",
        "frontend/src/assets/brand/xmu-emblem.svg",
        # ⚠️ .superpowers/** 的 -text（那些文件里印着自己的字节数与 sha256）
        ".superpowers/sdd/2026-10-13-实施计划06-产品级硬化/task-5-6-report.md",
    ]
    table = _check_attr(*ps1, *markdown, *binaries, *untouched)

    # ① 4 个 .ps1 → text: set / eol: crlf（⚠️ 且**没有**被顺手钉成 binary）
    for path in ps1:
        assert table[path]["text"] == "set", (path, table[path])
        assert table[path]["eol"] == "crlf", (path, table[path])
        assert table[path]["binary"] == "unspecified", (path, table[path])
    # ② Document/**/*.md → 同一档
    for path in markdown:
        assert table[path]["text"] == "set", (path, table[path])
        assert table[path]["eol"] == "crlf", (path, table[path])
    # ③⚠️ 红档半边：Document/ 下的二进制**必须是 unspecified**（一旦是 set，
    #    那个文件在下一次 checkout 之后就再也打不开了）
    for path in binaries:
        assert table[path]["text"] == "unspecified", (
            f"{path} 被钉成了文本（text: {table[path]['text']}）：它的字节里本来就有 LF，"
            "一次 checkout 就会把它改坏。Document/** 那条规则必须收窄成 **/*.md"
        )
        assert table[path]["eol"] == "unspecified", (path, table[path])
    # ④ 三条不该被碰的：backend/data 仍是 eol=lf、woff2 仍是 binary、
    #    品牌 svg 与 .superpowers 仍是 -text（text: unset）
    for path in untouched[:4]:
        assert table[path]["text"] == "set" and table[path]["eol"] == "lf", (
            path, table[path]
        )
    assert table[untouched[4]]["binary"] == "set", table[untouched[4]]
    assert table[untouched[4]]["text"] == "unset", table[untouched[4]]
    for path in untouched[5:]:
        assert table[path]["text"] == "unset", (path, table[path])

    # ⑤⚠️ **入库侧**也要核一遍（check-attr 只答「规则说什么」，不答「blob 是什么」）：
    #    钉扎的效果是「入库仍归一化成 LF、检出恒为 CRLF」，故 4 个 .ps1 的
    #    ls-files --eol 每一行都应当同时含 i/lf 与 attr/text eol=crlf。
    rows = _git("ls-files", "--eol", "--", "*.ps1").splitlines()
    assert len(rows) == 4, rows
    for row in rows:
        assert "i/lf" in row and "attr/text eol=crlf" in row, row

    # ⑥ 反空转：那三条规则**逐字**在 .gitattributes 里（否则上面全绿可能只是
    #    「git 压根没读到这个文件」，例如有人在别处又放了一份 .gitattributes）。
    #    ⚠️ 只看**非注释行**：那一段注释里逐字**引用**了被顶回的宽规则
    #    （``Document/** text eol=crlf``，作为取证），而提及不是本身（硬规矩 #109）。
    #    ⚠️ 比较前把行内空白折成单空格：``scripts/*.ps1`` 那一条为了与上一行对齐
    #    用了多个空格，按原文比会让「改一次对齐」变成一次守卫修改。
    rules = [
        " ".join(line.split())
        for line in (REPO_ROOT / ".gitattributes").read_bytes().decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for rule in (
        "backend/scripts/*.ps1 text eol=crlf",
        "scripts/*.ps1 text eol=crlf",
        "Document/**/*.md text eol=crlf",
    ):
        assert rule in rules, (rule, rules)
    # ⚠️ 而 `Document/**` 那一条**宽规则不许作为规则出现**（它就是 ③ 要挡的那个事故）
    assert not any(
        rule.startswith("Document/**") and not rule.startswith("Document/**/*.md")
        for rule in rules
    ), rules


