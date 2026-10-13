"""``scripts/serve.ps1`` 交给 uvicorn 的那个**入口模块**（Plan 06 Task 7）。

--------------------------------------------------------------------------
为什么需要它（``app.main:app`` 不够用）
--------------------------------------------------------------------------

``app.main`` 的模块级 ``app = create_app()`` 是**无参**建的，而
:func:`app.main.create_app` 的 ``static_dist`` 是一个**关键字实参**
——命令行的 import 串（``uvicorn app.main:app``）上没有任何位置能塞它。

于是产品档需要第二个入口对象。本模块就是它，全部内容只有三件事：

1. 读环境变量 :data:`STATIC_DIST_ENV_VAR`（``PE_STATIC_DIST``）；
2. 把它解析成一个 ``Path`` 或 ``None``（:func:`parse_static_dist`）；
3. ``app = create_app(static_dist=…)``。

⚠️ **它刻意不把那个路径写死在这里**（``frontend/dist`` 那个字面串在本模块里
一次都不出现）：``scripts/serve.ps1`` 已经算出了 ``frontend/dist`` 的**绝对**路径
（它是「仓库根在哪」的唯一所有者），在这里再敲一遍就是第二个所有者，
而两个所有者漂了之后的症状是「serve.ps1 明明构建过了、uvicorn 却指着别的目录」。
故本模块只认环境变量，缺省 ``None`` = **不挂 SPA**（= 与 ``app.main:app`` 逐字相同）。

--------------------------------------------------------------------------
⚠️ 它**不碰** ``app.main`` 的既有入口
--------------------------------------------------------------------------

``create_app`` 的 ``static_dist`` 缺省是 ``None``，故：

* ``uvicorn app.main:app``（``backend/scripts/demo.ps1`` 用的就是它）一行都不变；
* 既有 **1464** 条测试一条都不变（它们全部走 ``create_app(db_url="sqlite://")``，
  一个实参都没多给）；
* ``/openapi.json`` 的路径数与操作数一格都不变
  （SPA 那条是 :class:`starlette.routing.Route`，FastAPI 的 ``get_openapi``
  只收 ``APIRoute``；逐字理由见 :mod:`app.static` 的模块 docstring）。

--------------------------------------------------------------------------
怎么跑
--------------------------------------------------------------------------

::

    cd backend
    $env:PE_STATIC_DIST = "<仓库根>/frontend/dist"
    python -m uvicorn serve_app:app --app-dir scripts --host 127.0.0.1 --port 8020

⚠️ ``--app-dir scripts`` 是必需的：``python -m uvicorn`` 把 CWD（``backend/``）
放进 ``sys.path``，而本模块住在 ``backend/scripts/`` 下、``scripts/`` 又**不是**
一个包（没有 ``__init__.py``，与同目录的 ``demo_bootstrap.py`` / ``backup.py`` 一致），
故 import 串 ``serve_app:app`` 要靠 ``--app-dir`` 才找得到。
``scripts/serve.ps1`` 传的是那个目录的**绝对**路径。

⚠️ ``PE_STATIC_DIST`` 指向的目录里没有 ``index.html`` → :func:`app.static.mount_spa`
在**装配期**抛 ``FileNotFoundError``，而 ``app = create_app(…)`` 是本模块的
**模块级**语句，故 ``import serve_app`` 当场抛、uvicorn **起不来**。
那正是本仓要的失效方向（「起不来」而不是「静默地每页 404」）。

--------------------------------------------------------------------------
⚠️ 它会被架构守卫 AST 解析
--------------------------------------------------------------------------

``tests/architecture/test_layering.py`` 与 ``tests/architecture/test_domain_purity.py``
都对 ``BACKEND.rglob("*.py\")`` 逐个 ``ast.parse``，故本文件必须
**UTF-8 无 BOM** 且可解析（一个 BOM 会让那两条守卫炸在很远的地方，
逐字理由见 ``tests/db/test_migration_chain.py`` 的同名一条）。
``tests/test_serve.py`` 把这两格就地钉住，不必等那两条远端的守卫响。
"""
from __future__ import annotations

import os
import pathlib
import sys

# ⚠️ 与同目录的 ``demo_bootstrap.py`` 逐字同一条口径：``python -m uvicorn`` 放进
#    ``sys.path`` 的是 CWD（``backend/``）与 ``--app-dir`` 那个目录，故 ``app`` 包
#    在**没有** editable 安装（``pip install -e backend``）的机器上不一定找得到。
#    显式补一条，与 ``pyproject.toml`` 的 ``pythonpath=["."]``（只对 pytest 生效）无关。
BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402

__all__ = ["STATIC_DIST_ENV_VAR", "app", "parse_static_dist", "resolve_static_dist"]

#: 覆盖「挂不挂 SPA、挂哪个目录」的环境变量名。
#:
#: ⚠️ 它**不住在 ``app.config``**：``config.py`` 是全仓依赖图的叶子、
#: **只 import :mod:`pathlib`**（``tests/architecture/test_layering.py`` 的
#: :data:`~tests.architecture.test_layering.API_ALLOWED_PREFIXES` 那段注释逐字记着
#: 这个性质），而读环境变量要 ``import os``。与 ``PE_DB_URL``
#: （:data:`app.main.DB_URL_ENV_VAR`）、``PE_ENV``（:data:`app.deploy.ENV_VAR`）、
#: ``PE_ALLOW_HEADER_IDENTITY``（:data:`app.api.deps.ALLOW_HEADER_IDENTITY_ENV_VAR`）
#: 同一条口径：**环境变量名住在读它的那一层**。
#: ⚠️ 而它也不住在 :mod:`app.static`：那一层收的是一个已经解析好的 ``Path``，
#: 「从哪个环境变量读」是**入口**的事，不是**装配**的事。
STATIC_DIST_ENV_VAR = "PE_STATIC_DIST"


def parse_static_dist(raw: str | None) -> pathlib.Path | None:
    """一个环境变量的**原始串** → ``Path`` 或 ``None``。

    ⚠️ 空串与「只有空白」都按**没设**处理：``$env:PE_STATIC_DIST = ""`` 在
    PowerShell 里是「设了一个空值」而不是「删掉这个变量」，而
    ``create_app(static_dist=Path(""))`` 会让 :func:`app.static.mount_spa`
    抛一句「``index.html`` 不存在」——那是一句**假**的报错
    （运维明明什么都没设，他会被支去查前端构建）。
    与 :func:`app.main._resolve_db_url` 的 ``or`` 同一条口径。
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    return pathlib.Path(stripped)


def resolve_static_dist() -> pathlib.Path | None:
    """读本进程的 :data:`STATIC_DIST_ENV_VAR`。⚠️ **请求时**不调它：
    ``app = create_app(…)`` 是模块级语句，故它只在**进程启动**时求值一次
    ——改环境变量必须重启 uvicorn，与 ``PE_DB_URL`` 那一侧逐字相同。
    """
    return parse_static_dist(os.environ.get(STATIC_DIST_ENV_VAR))


#: ``uvicorn serve_app:app`` 的入口对象。⚠️ **模块级**语句，故 ``import serve_app``
#: 就会装配一次应用（造引擎、装中间件、注册路由，以及在 ``PE_STATIC_DIST`` 非空时
#: 挂 SPA）。这与 ``app.main`` 末尾那条 ``app = create_app()`` 是同一个形状，
#: 也是「坏配置 → import 就抛 → uvicorn 起不来」那个失效方向的落点。
#: ⚠️ ``db_url`` **刻意不传**：本模块不管库，那一格仍然是
#: ``PE_DB_URL`` > ``app.config.DEFAULT_DB_URL``（:func:`app.main._resolve_db_url`）。
#: ``scripts/serve.ps1`` 会在起进程之前把 ``PE_DB_URL`` 设好
#: （并自带一道 ``backend/pe.db`` 禁区守卫）。
app = create_app(static_dist=resolve_static_dist())
