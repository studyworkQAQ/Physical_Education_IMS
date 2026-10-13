"""**产品档**的静态文件服务与 SPA fallback（Plan 06 Task 7）。

--------------------------------------------------------------------------
为什么要有这个模块
--------------------------------------------------------------------------

交付给甲方的是**一个进程**：uvicorn 同时服务 ``/api/*`` 与 ``frontend/dist`` 里
构建好的前端。甲方运维不该跑 ``vite dev server``（那是开发期的东西：它不压缩、
不做指纹、要靠 ``server.proxy`` 才有同源，且它的进程模型不是给生产用的）。

于是「一个 URL 该发什么」这件事需要一份判据，而它有三个互相冲突的要求：

1. ``/api/*`` / ``/openapi.json`` / ``/docs`` / ``/redoc`` 一律**不许**被前端接走
   ——它们要么是真端点，要么是 ``app/api/errors.py`` 那个统一错误形状的 404；
2. ``dist`` 里**真实存在**的文件（``/assets/*.js|*.css``、woff2、svg）要按原字节发，
   且 ``content-type`` 要**对**（一个 ``text/plain`` 的 ``.js`` 会被浏览器按 ES module
   的严格 MIME 检查直接拒掉，症状是「白屏 + 一行控制台报错」）；
3. 其余一切路径（``/login``、``/s/home``、``/t/dashboard``、``/admin/students/1``，
   以及**打错的**任意 URL）都要回 ``index.html`` ——前端用的是
   ``createWebHistory()``（``frontend/src/router/index.ts``），深链接没有服务端
   fallback 就是一个 404，而 ``router`` 自己那条 ``/:pathMatch(.*)*`` 只在
   **浏览器已经拿到 index.html 之后**才有机会生效。

--------------------------------------------------------------------------
⚠️ 判据只有**一个所有者**：:func:`resolve_static_path`
--------------------------------------------------------------------------

「不是保留前缀、且磁盘上没有这个文件 → index.html」这一句在全仓只写一遍。
:func:`is_reserved` 是它的第一格、:func:`_candidate_under` 是它的第二格，
两者都是**纯函数**（不碰 HTTP、不碰全局状态），故 ``tests/test_serve.py``
可以不经起服务就把红绿两档都摆出来（硬规矩 #50：一条恒绿的守卫与一条空转的
守卫在颜色上无法区分）。

--------------------------------------------------------------------------
⚠️⚠️ 它**不改** ``/api/*`` 的任何一个可观察行为
--------------------------------------------------------------------------

这条路由是**追加在 ``application.router.routes`` 的末尾**的，而 Starlette 的
``Router`` 是「按顺序找第一个 ``Match.FULL``，找不到就退到第一个 ``Match.PARTIAL``，
再找不到才 404」。于是：

* ``GET /api/health`` 一类**真端点**在更前面就 ``FULL`` 命中，永远到不了这里；
* ``GET /api/nope``（路径不匹配任何 api 路由）会落到这里 → :func:`is_reserved`
  说「保留」→ 抛 ``HTTPException(404)`` → 被 ``app/api/errors.py`` 折成
  ``{"error": {"code": "not_found", …}}``，**与今天没有本模块时逐字相同**；
* ``POST /api/students``（路径匹配、方法不匹配）在 api 路由那一层就已经是
  ``PARTIAL``，而 Starlette 取的是**第一个** ``PARTIAL``，故仍然是 405 而不是
  被本模块接走。

⚠️⚠️ **而这一格不能靠「给 catch-all 传什么 ``methods``」解决**，两个现成选项各坏一半：

* ``methods=None``（任何方法都 ``FULL``）：``POST /api/health`` 与
  ``DELETE /api/semesters`` 会被 catch-all 的 ``FULL`` **抢在** api 路由的
  ``PARTIAL`` 前面（Starlette 一遇到 ``FULL`` 就返回），于是它们从 **405 变成 404**
  ——而 ``frontend/scripts/smoke.mjs`` 第 10 步逐字断言
  「``DELETE /api/semesters`` 是 **405** 不是 204」，那会当场红；
* ``methods=["GET", "HEAD"]``：api 路由的 ``PARTIAL`` 保住了（405 正确），
  而 catch-all 自己对 ``POST /api/nope`` 也给出一个 ``PARTIAL``
  （路径命中、方法不命中），且它是**唯一**的 ``PARTIAL`` → 于是 ``POST /api/nope``
  从 **404 变成 405 ``Allow: GET, HEAD``**。⚠️ 那一格比看起来坏：它在 ``/api`` 下面
  回一句「这个路径存在、只是方法不对」，而它**不存在**——正是本模块开头说的
  「把 404 变成一个误导性的响应」那一类。

故本模块用 :class:`_SpaRoute`：一个**对非 ``GET``/``HEAD`` 连 ``PARTIAL`` 都不给**
（直接 ``Match.NONE``）的 catch-all。四档于是同时正确——
``GET /login`` → index.html、``DELETE /api/semesters`` → 405（api 路由的 ``PARTIAL``
胜出）、``POST /api/nope`` → 404、``POST /login`` → 404。
``tests/test_serve.py`` 把这四格逐个钉住。

--------------------------------------------------------------------------
⚠️ 它**不进** OpenAPI
--------------------------------------------------------------------------

用的是 :class:`starlette.routing.Route` 而**不是** ``@application.get(...)``：
``fastapi.openapi.utils.get_openapi`` 只收 ``APIRoute`` 实例，故
``/openapi.json`` 的路径数与操作数**一格都不变**（本仓的基线是 72 路径 /
100 操作，前端 ``src/api/generated/schema.d.ts`` 由它生成）。
``tests/test_serve.py`` 用「给了 ``static_dist`` 与不给，两份 ``app.openapi()``
逐字相等」把这件事钉住——那是一份**双侧同源**的断言，但两侧走的是
``create_app`` 的两个不同分支，故它抓得住「有人把 SPA 路由写成了 APIRoute」。

--------------------------------------------------------------------------
⚠️ 目录穿越
--------------------------------------------------------------------------

``scope["path"]`` 是 uvicorn **percent-decode 之后**的串，故 ``/%2e%2e%2f%2e%2e%2fpe.db``
到这里已经是 ``/../../pe.db``。:func:`_candidate_under` 因此一律
``resolve()`` 之后再用 :meth:`pathlib.PurePath.is_relative_to` 复核它**仍在 dist 内**；
不在就返回 ``None``，而 :func:`resolve_static_path` 把 ``None`` 原样交出去
（→ 调用方抛 404），**绝不**发那个文件、也**不**退化成 index.html
（退化成 index.html 的话一个 200 会让探测者以为那是一个合法的前端路由）。
⚠️ 这一格同时挡住了 Windows 的**盘号绝对路径**：``Path("C:/dist") / "C:/Windows/win.ini"``
在 pathlib 里等于右边那个绝对路径（左边的被丢掉），故必须靠
``is_relative_to`` 兜，而不能靠「拼出来的串里没有 ``..``」这类字符串判据。
"""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Match, Route
from starlette.types import Scope

__all__ = [
    "INDEX_HTML",
    "RESERVED_PREFIXES",
    "SPA_METHODS",
    "SPA_ROUTE_PATH",
    "is_reserved",
    "media_type_of",
    "mount_spa",
    "resolve_static_path",
]

#: SPA 的入口文件名。⚠️ 它同时是「``dist`` 是不是一个构建产物」的判据：
#: ``npm run build`` 一定会写出它，而一个空目录 / 指错的目录一定没有它。
INDEX_HTML = "index.html"

#: SPA 那条 catch-all 路由的路径模板。⚠️ ``{path:path}`` 的正则是 ``(?P<path>.*)``，
#: 故它**也**匹配 ``/``（此时 ``path`` 是空串）——不需要另外再注册一条根路由。
SPA_ROUTE_PATH = "/{path:path}"

#: SPA 只接这两个方法。⚠️ 它是 :class:`_SpaRoute` 的判据、也是全仓「哪些方法可以
#: 拿到一份 HTML」的唯一住址：一个静态产物目录对 ``POST`` / ``DELETE`` 无话可说，
#: 而**装作**有话可说（回一个 405 ``Allow: GET, HEAD``）会在 ``/api`` 下面撒谎。
#: 逐字理由见模块 docstring 的第二节。
SPA_METHODS: frozenset[str] = frozenset({"GET", "HEAD"})

#: **永不 fallback** 的前缀。判据是「等于它、或以 ``它 + "/"`` 开头」
#: （:func:`is_reserved`），故 ``/apixyz`` 与 ``/documentary`` 都**不在**这一档里
#: ——裸 ``startswith("/api")`` 会把它们误判成保留前缀，而它们的正确去处是
#: index.html（前端 ``router`` 的 ``/:pathMatch(.*)*`` 会把它们弹回 ``/s/home``）。
#:
#: ⚠️ 四项逐个：``/api`` 是全部业务端点；``/openapi.json`` 是契约（前端
#: ``src/api/contract.ts`` 在开发期直接读它，管理台的表单由它驱动）；
#: ``/docs`` 与 ``/redoc`` 是 FastAPI 自带的两张交互文档页
#: （``/docs/oauth2-redirect`` 由 ``/docs`` 那一项一并盖住）。
#: ⚠️ 这四项**都是 FastAPI 已经注册好的真路由**，故本清单挡的不是「它们被遮住」
#: （顺序已经保证了那一格），而是「它们下面**不存在**的子路径被 fallback 成
#: 一个 200 的 index.html」——那一档会把一个 404 变成 200，而 200 的响应体是
#: 一份 HTML，调用方的 ``JSON.parse`` 会在离真因很远的地方炸。
RESERVED_PREFIXES: tuple[str, ...] = ("/api", "/openapi.json", "/docs", "/redoc")

#: 扩展名 → ``content-type``。⚠️ **本表是实测出来的、不是洁癖**：
#: ``FileResponse`` 缺省用 :func:`mimetypes.guess_type`，而 ``mimetypes`` 在 Windows 上
#: 会**读注册表**（``HKEY_CLASSES_ROOT\\<扩展名>\\Content Type``）。本机亲跑::
#:
#:     python -c "import mimetypes;print(mimetypes.guess_type('a.woff2'),mimetypes.guess_type('a.js'))"
#:     → (None, None) ('application/javascript', None)
#:
#: ``None`` 会让 Starlette 退化成 ``text/plain``：本机的 4 个自托管 woff2 因此会带着
#: ``content-type: text/plain`` 发出去。⚠️ 而 ``.js`` 那一格**本机是对的、别的机器不一定**
#: ——注册表里把 ``.js`` 映成 ``text/plain`` 的 Windows 机器是真实存在的一档
#: （装过某些老工具就会留下），而 ES module 的**严格 MIME 检查**会让浏览器
#: 直接拒绝执行它：症状是「产品档白屏、控制台一行
#: ``Failed to load module script: Expected a JavaScript module…``」，
#: 而 dev 档（vite 自己发 ``content-type``）完全正常 —— 离真因有两层。
#: 故这里把 ``dist`` 里**实际会出现**的扩展名逐字钉住，不赌注册表。
#: ⚠️ 与 ``npm run check:dist`` 的 ``SCANNED_EXTENSIONS`` 是两件事（那一份数的是
#: 「要扫哪些文本产物」，本表数的是「要发什么 content-type」），故刻意不共享常量。
_MEDIA_TYPES: dict[str, str] = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".mjs": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def is_reserved(url_path: str) -> bool:
    """``url_path`` 是否落在 :data:`RESERVED_PREFIXES` 里（= **永不** fallback）。

    ⚠️ 边界口径与 ``tests/architecture/test_layering.py`` 的 :func:`_is_api_allowed`
    逐字相同（「等于，或以 ``前缀 + "/"`` 开头」）：裸 ``startswith`` 会把
    ``/apixyz`` 误判成 ``/api`` 的子路径。
    """
    return any(
        url_path == prefix or url_path.startswith(prefix + "/")
        for prefix in RESERVED_PREFIXES
    )


def _candidate_under(root: pathlib.Path, url_path: str) -> pathlib.Path | None:
    """``url_path`` 在 ``root`` 里对应的那个文件；**逃出 ``root``** 时返回 ``None``。

    ⚠️ 它只做「解析 + 越界复核」，**不做存在性判定**（那是
    :func:`resolve_static_path` 的事）：两件事分开，于是「越界」与「不存在」
    可以被分别测出来，而它们在本模块里的去处是**不同的**
    （越界 → ``None`` → 404；不存在 → index.html）。
    """
    relative = url_path.lstrip("/")
    if not relative:
        return root / INDEX_HTML
    try:
        candidate = (root / relative).resolve()
    except (OSError, ValueError):
        # Windows 上 `resolve()` 对一个带非法字符（NUL 一类）的路径会抛，
        # 而那一档的正确去处就是「本层不接」。
        return None
    if not candidate.is_relative_to(root):
        return None
    return candidate


def resolve_static_path(dist: pathlib.Path, url_path: str) -> pathlib.Path | None:
    """**SPA fallback 判据的唯一所有者。**

    返回值三档，逐档对应模块 docstring 里那三个要求：

    ==========================  ====================================================
    返回                         含义
    ==========================  ====================================================
    ``dist`` 内的一个文件         磁盘上真有它 → 按原字节发
    ``dist/index.html``          保留前缀之外、磁盘上没有 → SPA fallback
    ``None``                     **本层不接这个路径** → 交给框架 404
    ==========================  ====================================================

    ``None`` 的两档（:func:`is_reserved` 为真、或 :func:`_candidate_under` 判出越界）
    都由调用方抛 ``HTTPException(404)``，于是响应体是 ``app/api/errors.py`` 那个
    统一形状，而不是 StaticFiles 的纯文本 404。

    ⚠️ ``url_path`` 必须是**已经 percent-decode** 的那一份
    （``request.scope["path"]``，也就是 ASGI 规范里的 ``path``），
    不要用 ``request.url.path``：后者是把已解码的串再拼回一个 URL 然后重新解析，
    于是一个**字面**含 ``%2f`` 的路径会被二次解码。
    ⚠️ ``dist/index.html`` 不存在时也返回 ``None``（而不是返回一个发不出去的路径）：
    那一档意味着 ``dist`` 根本不是一个构建产物，:func:`mount_spa` 在**装配时**
    就已经把它拦下来了，故这里只是第二道。
    """
    if is_reserved(url_path):
        return None
    root = dist.resolve()
    candidate = _candidate_under(root, url_path)
    if candidate is None:
        # ⚠️ **越界与「不存在」是两档、去处也不同**：越界（``..`` 上溯、Windows 的
        #    盘号绝对路径、resolve() 抛的非法字符）一律 ``None`` → 404，
        #    而**不是**回 index.html。⚠️ 两档都发不出那个文件，故安全性质相同；
        #    分开是为了**诚实**：一个 200 的 index.html 会让探测者以为
        #    ``/%2e%2e%2f…`` 是一个合法的前端路由，而 404 说的是真话。
        return None
    if candidate.is_file():
        return candidate
    index = root / INDEX_HTML
    return index if index.is_file() else None


def media_type_of(path: pathlib.Path) -> str | None:
    """一个产物文件的 ``content-type``；认不出的扩展名返回 ``None``（交给框架去猜）。

    ⚠️ 逐字理由见 :data:`_MEDIA_TYPES`：``mimetypes`` 在 Windows 上读注册表，
    故本机实测 ``.woff2`` → ``None``（会退化成 ``text/plain``）。
    """
    return _MEDIA_TYPES.get(path.suffix.lower())


class _SpaRoute(Route):
    """一条对**非** :data:`SPA_METHODS` 的请求连 ``Match.PARTIAL`` 都不给的 catch-all。

    ⚠️ 这五行的全部理由在模块 docstring 的第二节，一句话概括：
    ``methods=None`` 会把 ``DELETE /api/semesters`` 从 405 改成 404
    （catch-all 的 ``FULL`` 抢在 api 路由的 ``PARTIAL`` 前面），
    而 ``methods=["GET", "HEAD"]`` 会把 ``POST /api/nope`` 从 404 改成 405
    （catch-all 自己是那个唯一的 ``PARTIAL``）。
    返回 :attr:`Match.NONE` 让 Starlette 的 ``Router`` **当作这条路不存在**，
    于是两档都退回框架缺省：有 ``PARTIAL`` 就 405、一个都没有就
    :func:`starlette.routing.Router.not_found` 的 404
    （再被 ``app/api/errors.py`` 折成 ``{"error": {"code": "not_found", …}}``）。

    ⚠️ ``scope.get("method")`` 而不是 ``scope["method"]``：``websocket`` 那一档的
    scope 里没有 ``method`` 键，而 :meth:`Route.matches` 对它的回答本来就是 ``NONE``，
    故这里给 ``NONE`` 与父类逐字相同（不是新增的一档）。
    """

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope.get("method") not in SPA_METHODS:
            return Match.NONE, {}
        return super().matches(scope)


def mount_spa(application: FastAPI, dist: pathlib.Path) -> None:
    """把 ``dist`` 挂成 ``application`` 的**最后一条**路由。由 :func:`app.main.create_app`
    在全部 API 路由注册完之后调用一次（``static_dist`` 非 ``None`` 时）。

    ⚠️ **顺序是承重的**：Starlette 按 ``routes`` 的顺序找第一个 ``Match.FULL``，
    故本函数必须在 ``include_router(api_router)`` 与 ``/api/health`` **之后**跑。
    早一步的话 ``/api/health`` 会被 SPA 接走（``resolve_static_path`` 会因为
    ``is_reserved`` 返回 ``None`` → 404），症状是「产品档上每个端点都 404」。
    ``tests/test_serve.py`` 用 ``GET /api/health`` 在**给了 ``static_dist``** 的
    应用上仍然 200 把这一格钉住。

    ⚠️ ``dist/index.html`` 不存在 → **当场 :class:`FileNotFoundError`**。
    失效方向必须是「起不来」而不是「起来了但每一页都是 404」
    （与 ``app/deploy.py`` 的 :func:`app.main._selfcheck_prod`、
    ``backend/scripts/demo.ps1`` 那两道禁区守卫同一条姿势）。
    ⚠️ 而它是**装配期**抛的，``backend/scripts/serve_app.py`` 有一条模块级的
    ``app = create_app(...)``，故 ``uvicorn serve_app:app`` 在一个坏
    ``PE_STATIC_DIST`` 下**根本起不来**，那句报错就是运维要看的东西。

    ⚠️ 用的是 :class:`_SpaRoute` 而不是裸 :class:`~starlette.routing.Route`，
    逐字理由见那个类与模块 docstring 的第二节（一句话：两个现成的 ``methods``
    取值各会把 ``/api`` 下面的一档状态码改掉，而 :class:`_SpaRoute` 对非
    ``GET``/``HEAD`` 直接 ``Match.NONE``，于是两档都退回框架缺省）。
    """
    if not (dist / INDEX_HTML).is_file():
        raise FileNotFoundError(
            f"{dist / INDEX_HTML} 不存在：PE_STATIC_DIST 指的不是一个前端构建产物。"
            f"请先在 frontend/ 下跑 `npm run build`（或让 scripts/serve.ps1 自己跑，"
            f"它会先判 dist 是不是比 src 旧），或者**不设** PE_STATIC_DIST"
            f"（不设 = 只服务 /api，与 dev 档逐字相同）"
        )

    async def _spa(request: Request) -> Response:
        target = resolve_static_path(dist, request.scope["path"])
        if target is None:
            raise StarletteHTTPException(status_code=404)
        return FileResponse(target, media_type=media_type_of(target))

    application.router.routes.append(
        _SpaRoute(SPA_ROUTE_PATH, _spa, methods=sorted(SPA_METHODS))
    )
