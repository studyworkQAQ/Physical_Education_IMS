"""**产品档**的静态文件服务与 SPA fallback（Plan 06 Task 7）。

--------------------------------------------------------------------------
为什么要有这个模块
--------------------------------------------------------------------------

交付给甲方的是**一个进程**：uvicorn 同时服务 ``/api/*`` 与 ``frontend/dist`` 里
构建好的前端。甲方运维不该跑 ``vite dev server``（那是开发期的东西：它不压缩、
不做指纹、要靠 ``server.proxy`` 才有同源，且它的进程模型不是给生产用的）。

于是「一个 URL 该发什么」这件事需要一份判据，而它有五个互相冲突的要求
（⚠️ 前三个是 Plan 06 Task 7 立的，后两个是 Plan 06 Task 11 / B1+B2 加的）：

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
4. ⚠️ **而第 3 条有一个例外**（Plan 06 Task 11 / B1）：一个**在要静态产物文件**的路径
   而磁盘上没有它 → **404**，不是 index.html。逐字理由见 :func:`is_asset_request`。
5. ⚠️ **两类缓存头**（Plan 06 Task 11 / B2）：带内容哈希的 ``/assets/*`` 可以被
   永久缓存，而入口文档 ``index.html`` **必须**每次回源校验。
   逐字理由见 :func:`cache_control_for`。

--------------------------------------------------------------------------
⚠️ 判据只有**一个所有者**：:func:`resolve_static_path`
--------------------------------------------------------------------------

「不是保留前缀、且磁盘上没有这个文件 → index.html」这一句在全仓只写一遍。
:func:`is_reserved` 是它的第一格、:func:`_candidate_under` 是它的第二格、
:func:`is_asset_request` 是它的第三格（Plan 06 Task 11 / B1 加的：它把第 3 条
「一律 fallback」收窄成「**除了要静态产物文件的那些**」），
三者都是**纯函数**（不碰 HTTP、不碰全局状态），故 ``tests/test_serve.py``
可以不经起服务就把红绿两档都摆出来（硬规矩 #50：一条恒绿的守卫与一条空转的
守卫在颜色上无法区分）。
⚠️ 缓存头同理只有一个住址：:func:`cache_control_for`（Plan 06 Task 11 / B2）。

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
``/openapi.json`` 的路径数与操作数**一格都不变**（2026-10-16 实测的基线是
**74 路径 / 102 操作**，前端 ``src/api/generated/schema.d.ts`` 由它生成。
⚠️ 那两个数是一份**时点快照**、不是本文件的裁定：它们随端点增删而漂，
确切的五格由 ``frontend/scripts/smoke.mjs`` **现场数** ``/openapi.json`` 得到，
本处只是给「一格都不变」那句话一个可对账的基准）。
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
    "ASSETS_PREFIX",
    "ASSETS_URL_DIR",
    "IMMUTABLE_CACHE_CONTROL",
    "INDEX_HTML",
    "NO_CACHE",
    "RESERVED_PREFIXES",
    "RESERVED_PREFIXES_CASE_INSENSITIVE",
    "SPA_METHODS",
    "SPA_ROUTE_PATH",
    "cache_control_for",
    "is_asset_request",
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

#: ``/api`` 那一个字面量在本模块的**唯一住址**（:data:`RESERVED_PREFIXES` 与
#: :data:`RESERVED_PREFIXES_CASE_INSENSITIVE` 都读它，故它只写一遍）。
_API_PREFIX = "/api"

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
RESERVED_PREFIXES: tuple[str, ...] = (
    _API_PREFIX, "/openapi.json", "/docs", "/redoc",
)

#: :data:`RESERVED_PREFIXES` 里**大小写不敏感**地比的那一份子集（Plan 06 Task 15 /
#: 终审 S4-①）。⚠️ 今天它只有一项：``/api``。
#:
#: ⚠️⚠️ 来历（本波裸 socket 实测，路径逐字发出、不被任何一层归一化）：产品档上
#: ``/API/health`` / ``/Api/Health`` / ``/apI/HEALTH`` / ``/API/nope`` 各回
#: **200 + ``text/html`` + 2 729 B**（= ``index.html``）—— Starlette 的路由匹配与
#: :func:`is_reserved` 的判据**都是大小写敏感**的，于是那些路径既不是真端点、
#: 也不是保留前缀，落到了 SPA fallback 上。⚠️ 后果不是泄漏（那份 HTML 里一个数据
#: 字节都没有），而是**误导**：甲方运维一个把 ``/API/health`` 写错的 uptime 探针
#: 会**永远绿**。改后那一族一律 **404 + 统一错误形状**，与 ``/api/nope`` 同款。
#:
#: ⚠️⚠️ 而**只有 ``/api`` 这一项**进本清单，另三项（``/openapi.json`` / ``/docs`` /
#: ``/redoc``）与全部前端路由**逐字不动**：``/DOCS`` 与 ``/LOGIN`` 今天照旧回
#: ``index.html``。理由不是省事，是**消费者不同**：
#:
#: * ``/api/*`` 是**机器面**（监控探针、脚本、前端 ``fetch`` 之后的 ``JSON.parse``），
#:   一个 200 的 HTML 在那一面是一句会**静默**骗人的话（探针永远绿、``JSON.parse``
#:   在离真因很远的地方炸）；
#: * ``/docs`` 与前端路由是**人手敲的**，回 ``index.html`` 之后前端 router 会把人弹到
#:   该去的地方（``/LOGIN`` → ``/:pathMatch(.*)*`` → ``/s/home`` → 守卫 → ``/login``）；
#:   那一档改回 404 JSON 反而是把人拦在一个白屏上。
#:
#: ⚠️ 于是 HTTP 路径**仍然是大小写敏感**的（RFC 3986），本清单改的只是
#: 「一个大小写打错的 API 路径该回什么」这一格答案。
#: ⚠️ 守卫在 ``tests/test_serve.py`` 的
#: ``test_the_api_prefix_is_matched_case_insensitively_but_the_human_routes_are_not``
#: （判据层 + 反空转）与 ``test_an_uppercase_api_path_answers_the_unified_404_and_not_index_html``
#: （HTTP 层 + 反空转），两条各钉一半。
RESERVED_PREFIXES_CASE_INSENSITIVE: tuple[str, ...] = (_API_PREFIX,)

#: vite 的产物目录名（``build.assetsDir`` 的缺省值）。⚠️ **它是实测出来的、不是假设**：
#: ``frontend/dist`` 今天的布局逐字是「根上一个 ``index.html`` + 一个 ``assets/``
#: 目录（28 个文件：14 个 ``.js`` / 8 个 ``.css`` / 4 个 ``.woff2`` / 2 个 ``.svg``）」，
#: **根级没有任何静态文件**（``frontend/index.html`` 里既没有 ``<link rel="icon">``、
#: 也没有字体外链——字体与品牌 svg 都被打包器收进了 ``assets/``）。
#: ⚠️ 于是本常量今天只有一个读者会真的命中（:func:`is_asset_request`），
#: 而它**必须**是常量而不是散在两处的字面串：``vite.config.ts`` 若哪天显式设了
#: ``build.assetsDir``，改的是这一格。
ASSETS_URL_DIR = "assets"

#: ``/assets/``。⚠️ 判据与 :func:`is_reserved` 同一条口径（「以 ``它`` 开头」，
#: 而它自己**带着**结尾那个 ``/``）：于是裸 ``/assets``（= 那个目录本身）
#: **不在**这一档里，它照旧走 fallback（给一个目录列表等于把产物结构告诉任何
#: 匿名调用方，理由逐字见 ``tests/test_serve.py`` 的
#: ``test_resolve_static_path_answers_exactly_the_four_documented_cases`` 末段）。
ASSETS_PREFIX = "/" + ASSETS_URL_DIR + "/"

#: 带**内容哈希**的产物（``/assets/index-DaycGB6S.js`` 那一族）的缓存头。
#:
#: ⚠️ 三格各自承重（Plan 06 Task 11 / B2）：``public`` 让它能被**共享**缓存
#: （反代 / CDN）存下来——它不含任何按身份而变的东西；``max-age=31536000``
#: 是一年（RFC 允许的上界附近，再大有些实现会当成溢出）；``immutable`` 告诉浏览器
#: 「**连条件请求都不要发**」——没有它的话，用户按一次刷新会对 28 个产物文件
#: 各发一个 ``If-None-Match``（28 个 304 往返，而这 28 个文件名里就带着内容哈希，
#: 名字没变 ⇒ 内容不可能变，那些往返一个比特信息都没有）。
#: ⚠️ 而「文件名带哈希」是这一格成立的**全部前提**：一个不带哈希的文件挂上
#: ``immutable`` 就是一次永久的陈旧（改前那一份会被缓存一年）。
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

#: 入口文档（``index.html``）的缓存头。
#:
#: ⚠️⚠️ **必须是 ``no-cache`` 而不是长缓存**（Plan 06 Task 11 / B2，派单逐字点名）：
#: ``index.html`` 是**唯一**一个引用那些带哈希文件名的地方，而它自己的名字**不带**哈希。
#: 若它可以被长缓存，甲方升级之后用户拿到的仍是**旧的** ``index.html``，
#: 而它引用的是**旧哈希**的 ``/assets/index-<旧>.js`` —— 那些文件在新构建里
#: **已经不存在了**，于是每一屏都是白屏 + 一行
#: ``Failed to load module script`` / ``404``。⚠️ 而那一档**不会自愈**：
#: 用户的缓存要到 ``max-age`` 走完才回源，症状是「升级之后一部分用户白屏几天」。
#: ⚠️ ``no-cache`` 的语义**不是**「不要缓存」（那是 ``no-store``），而是
#: 「缓存可以留，但**每次用之前必须回源校验**」——配合 ``FileResponse`` 自带的
#: ``etag`` / ``last-modified``，产物没变时那一次校验是一个**304**（几百字节、
#: 没有响应体），变了才拉一份新的。故它是「永远拿到对的入口」与「不重复下载」
#: 两件事同时成立的那一档。
#: ⚠️ **不选 ``no-store``** 的理由（顶回派单 §5 ③ 的那一格）：``no-store`` 会让
#: 每一次导航都重下 2 729 字节的入口文档，而它换来的一格额外保证
#: （「中间人一个字节都不许留」）在本档没有意义——``index.html`` 不含任何
#: 按身份而变的东西，也不含凭据（会话在 HttpOnly 的 ``pe_session`` cookie 里）。
NO_CACHE = "no-cache"

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

    ⚠️ **两趟比**（Plan 06 Task 15 / 终审 S4-①）：第一趟逐字比全部四项；
    第二趟把 ``url_path`` 折成小写、只比 :data:`RESERVED_PREFIXES_CASE_INSENSITIVE`
    那一份子集（今天只有 ``/api``）。⚠️ 于是边界口径在两趟里**是同一条**
    （``/APIXYZ`` 与 ``/API-HEALTH`` 照旧**不是**保留前缀），
    只有大小写这一维被放宽，逐格理由见那个常量的注释。
    """
    if any(
        url_path == prefix or url_path.startswith(prefix + "/")
        for prefix in RESERVED_PREFIXES
    ):
        return True
    lowered = url_path.lower()
    return any(
        lowered == prefix or lowered.startswith(prefix + "/")
        for prefix in RESERVED_PREFIXES_CASE_INSENSITIVE
    )


def is_asset_request(url_path: str) -> bool:
    """``url_path`` 是不是**在要一个静态产物文件**（= 磁盘上没有它就 **404**、不 fallback）。

    ------------------------------------------------------------------------
    ⚠️ 为什么要这一格（Plan 06 Task 11 / B1，收 Task 7 登记的一条待清扫）
    ------------------------------------------------------------------------
    改前 ``GET /assets/does-not-exist.js`` 回的是 **200 + ``text/html``**（走了 fallback）。
    那一档坏在两处，而两处都是**离真因很远**的：

    * 浏览器按 ES module 的**严格 MIME 检查**当场拒绝执行它
      （``Failed to load module script: Expected a JavaScript module script but the
      server responded with a MIME type of "text/html"``）——症状是**白屏**，
      而真因是「那一个哈希文件名不存在」（多半是 ``dist`` 没构建、或 ``index.html``
      是旧的而 ``assets/`` 是新的）；
    * 运维排查时**看不出**是「文件没构建出来」还是「路由打错了」：两档都回 200，
      而 200 说的是一句假话（它宣称「这是一个合法的前端路由」）。

    改后那一档是 **404 + ``app/api/errors.py`` 那个统一形状**，与 ``/api/nope`` 同款
    ——于是「产物文件不在」与「前端路由」在**状态码**上就能分开。

    ------------------------------------------------------------------------
    ⚠️ 判据是两格，而**第二格刻意只管根级**
    ------------------------------------------------------------------------
    ① 以 :data:`ASSETS_PREFIX` 开头（``/assets/…``）——vite 的产物一律在那里，
       且文件名**一律带内容哈希**，故「不在磁盘上」只可能是「构建产物与入口文档
       不同代」，绝不可能是「一个合法的前端路由」；
    ② **单段**路径（``lstrip("/")`` 之后不含 ``/``）且扩展名在 :data:`_MEDIA_TYPES` 里
       （``/robots.txt``、``/favicon.ico``、``/site.webmanifest`` 这一族）。
       ⚠️ 派单点名的正是这一格（「也考虑 ``/*.svg``、``/*.woff2`` 这类根级静态文件」）。

    ⚠️⚠️ 而第 ② 格**刻意不放宽到多段路径**，理由是一条既有行为：
    ``/%2e%2e/secret.txt`` 解码之后是 ``/../secret.txt``（多段），它今天的正确去处是
    :func:`_candidate_under` 判出的**越界** → ``None`` → 404；
    而一个字面的 ``/%2e%2e/secret.txt``（**没**被解码）今天走 fallback → index.html
    （``tests/test_serve.py`` 的
    ``test_resolve_static_path_refuses_to_leave_the_dist_directory`` 第 ② 拍逐字钉着
    那一格，并解释了为什么「不做第二次解码」才是对的）。把第 ② 格放宽到多段的话，
    那一档会从 200 变成 404 ——两档都**不泄漏任何字节**，但那是本件**范围之外**
    的一次行为变更，故不做（硬规矩：只改派单点名的那一格）。

    ⚠️ 前端路由**一条都不受影响**：本仓 16 条路由（``router/index.ts`` 的 ``routes``）
    一条都不带扩展名（``/s/weekly-sheet``、``/admin/audit-logs`` 那一族），
    故它们的第 ② 格恒为假、第 ① 格也恒为假 → 照旧 fallback。
    ``tests/test_serve.py`` 把 Task 7 那张 **13 格 fallback 矩阵**逐格钉住。
    """
    if url_path.startswith(ASSETS_PREFIX):
        return True
    relative = url_path.lstrip("/")
    if "/" in relative:
        # ⚠️ 多段路径一律**不是**「在要一个静态产物文件」（理由见 docstring 第二节）
        return False
    return pathlib.PurePosixPath(relative).suffix.lower() in _MEDIA_TYPES


def cache_control_for(url_path: str, target: pathlib.Path) -> str | None:
    """**要发的那个文件**该带哪一条 ``Cache-Control``；``None`` = 一个字节都不加。

    ⚠️ 它是「产品档的缓存策略」在全仓的**唯一住址**（Plan 06 Task 11 / B2）。
    判据刻意只有两格、且**按「发的是哪个文件」判**而不是按 URL 判：

    ① ``target.name == INDEX_HTML`` → :data:`NO_CACHE`。
       ⚠️ 用**文件名**判而不是用 ``url_path == "/index.html"`` 判是承重的：
       SPA fallback 那 13 格（``/``、``/login``、``/s/home``、``/admin/…``）发出去的
       **也是** ``index.html``，而它们恰恰是最需要 ``no-cache`` 的那些
       （用户刷新一次 ``/t/dashboard`` 就是一次入口文档的取用）；
       按 URL 判的话那 13 格一个缓存头都拿不到，浏览器会按**启发式**缓存它们
       （``Last-Modified`` 距今的 10%），于是「升级之后一部分用户白屏几天」那一档
       照样发生——只是从 ``/index.html`` 搬到了 ``/t/dashboard``。
    ② ``url_path`` 以 :data:`ASSETS_PREFIX` 开头 → :data:`IMMUTABLE_CACHE_CONTROL`
       （文件名带内容哈希，故「名字没变 ⇒ 内容没变」）。
    ③ 其余（今天**一格都没有**：``dist`` 的根级只有 ``index.html``）→ ``None``。
       ⚠️ 刻意不给一个兜底的长缓存：根级文件**不带**哈希（``/favicon.ico`` 那一族），
       给它们 ``immutable`` 就是一次永久的陈旧。

    ⚠️⚠️ **``/api/*``、``/openapi.json``、``/docs``、``/redoc`` 一个字节都不受影响**
    （派单 §2 B2 第 ③ 条逐字要求；有守卫钉着「产品档不改 ``/api`` 的任何一格可观察
    行为」= spec §13.11.2）：本函数**只被 :func:`mount_spa` 里那个 ``_spa`` 调用**，
    而那四个面在 :func:`is_reserved` 那一格就已经返回 ``None``、根本走不到发文件那一步
    （它们由 FastAPI 自己的路由发）。守卫是 ``tests/test_serve.py`` 的
    ``test_no_cache_control_is_added_to_the_api_the_contract_or_the_two_doc_pages``。
    """
    if target.name == INDEX_HTML:
        return NO_CACHE
    if url_path.startswith(ASSETS_PREFIX):
        return IMMUTABLE_CACHE_CONTROL
    return None


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

    返回值三档，逐档对应模块 docstring 里那五个要求：

    ==========================  ====================================================
    返回                         含义
    ==========================  ====================================================
    ``dist`` 内的一个文件         磁盘上真有它 → 按原字节发
    ``dist/index.html``          保留前缀之外、磁盘上没有 → SPA fallback
    ``None``                     **本层不接这个路径** → 交给框架 404
    ==========================  ====================================================

    ``None`` 的**三**档（:func:`is_reserved` 为真、:func:`_candidate_under` 判出越界、
    或 Plan 06 Task 11 / B1 加的「:func:`is_asset_request` 为真而磁盘上没有它」）
    都由调用方抛 ``HTTPException(404)``，于是响应体是 ``app/api/errors.py`` 那个
    统一形状，而不是 StaticFiles 的纯文本 404。
    ⚠️ 于是「一个打错的 ``/assets/*.js``」与「一个 ``/api/nope``」在响应上**同款**
    （404 + ``{"error": {"code": "not_found", …}}``）——那正是 B1 要的那一格：
    运维看状态码就知道是「产物文件不在」，而不是被一个 200 的 HTML 支去查前端路由。

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
    if is_asset_request(url_path):
        # ⚠️ Plan 06 Task 11 / B1：一个**在要静态产物文件**的路径而磁盘上没有它 →
        #    None（→ 404 统一形状），**绝不**退化成 index.html。逐字理由见
        #    :func:`is_asset_request`（一句话：一个 200 的 text/html 会让浏览器按
        #    ES module 的严格 MIME 检查当场拒掉它，症状是白屏，而真因是
        #    「那一个带哈希的文件名不存在」；且 200 对运维说的是一句假话）。
        return None
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
        url_path = request.scope["path"]
        target = resolve_static_path(dist, url_path)
        if target is None:
            raise StarletteHTTPException(status_code=404)
        # ⚠️ 缓存头由 :func:`cache_control_for` 一个人决定（Plan 06 Task 11 / B2），
        #    而它回 None 时**一个头都不加**（不是加一条空的）：那三个面
        #    （``/api/*`` / ``/openapi.json`` / 两张文档页）根本走不到这里，
        #    而根级非 index.html 的产物今天一格都没有。
        cache_control = cache_control_for(url_path, target)
        return FileResponse(
            target,
            media_type=media_type_of(target),
            headers=None if cache_control is None else {"Cache-Control": cache_control},
        )

    application.router.routes.append(
        _SpaRoute(SPA_ROUTE_PATH, _spa, methods=sorted(SPA_METHODS))
    )
