r"""把 ``/openapi.json`` 的内容 dump 成一份 JSON 文件，**不起服务、不占端口、不建库**。

--------------------------------------------------------------------------
为什么要有这个脚本（Plan 06 Task 11 / A3）
--------------------------------------------------------------------------

``npm run gen:api`` 此前的输入是一个 **URL**::

    openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/schema.d.ts

⚠️⚠️ 于是「产物新不新」取决于**8000 上此刻跑的是哪一份代码**。Plan 06 Task 10 踩过
一次：改完后端、没有重启那个 uvicorn，``gen:api`` 读到的是**旧进程**里的旧 spec，
产出了一份陈旧的 ``schema.d.ts`` —— 而它是**入库产物**（前端读契约的唯一入口）。
失效形态是「静默产出一份陈旧的交付物」：TypeScript 只用它的**类型**，
注释漂了编译器一句话都不说。

本脚本把输入从「在跑的服务」换成「**进程内**的 :func:`app.main.create_app`」::

    create_app(db_url="sqlite://")  →  app.openapi()  →  json.dump

于是 ``gen:api`` 读到的**一定是当前工作树里的那一份代码**，与「有没有起服务、
起的是哪一份」彻底无关。

--------------------------------------------------------------------------
⚠️⚠️ 它**刻意不建库**（``backend/pe.db`` 是本仓的禁区）
--------------------------------------------------------------------------

:func:`app.main.create_app` 的 ``db_url`` 缺省会解析到
:data:`app.config.DEFAULT_DB_URL`，而那个常量**逐字指向禁区** ``backend/pe.db``。
两格挡住了它：

1. **显式传 ``db_url="sqlite://"``**（内存库）——于是 :func:`app.main._resolve_db_url`
   根本不去读 ``PE_DB_URL``、也不回落到 ``DEFAULT_DB_URL``。⚠️ 它**刻意不尊重**
   ``PE_DB_URL``：OpenAPI 文档与「连的是哪个库」**无关**（29 张表的 schema 由
   ``Base.metadata`` 给出），尊重它只会让「在一个 shell 里设过 ``PE_DB_URL``」
   变成一件影响产物的事。
2. **不进 lifespan**——``init_db`` 住在 :func:`app.main.create_app` 返回的那个应用的
   ``_lifespan`` 里，而本脚本**只调** ``app.openapi()``、从不 ``async with`` 它、
   也从不起 uvicorn。故「建表」这一步一次都不跑（``create_engine`` 本身是惰性的：
   不连接、不建文件）。

⚠️ 而这两格都**有断言**，不是「我看代码里没写」（硬规矩 #109）：
:func:`_assert_forbidden_zone_is_untouched` 在 dump 的**前后各查一次**
``backend/pe.db`` 存在不存在，前一次存在就 refuse to run（禁区已经被别人破了，
本脚本不该在那上面继续干活），后一次存在就**非 0 退出**并点名是本脚本建的。
守卫是 ``tests/api/test_prescription_api.py`` 的
``test_running_the_dump_script_as_a_subprocess_never_creates_the_forbidden_database``。

--------------------------------------------------------------------------
⚠️ 序列化的口径与 ``GET /openapi.json`` **逐字相同**
--------------------------------------------------------------------------

:func:`_render` 用的是 ``starlette.responses.JSONResponse.render`` 的那一套参数
（``ensure_ascii=False`` / ``allow_nan=False`` / ``indent=None`` / ``separators=(",", ":")``），
故本脚本 dump 出来的**文件字节**与那个端点的**响应体字节**逐字相等。
⚠️ 那一格不是洁癖：它让「离线路径」与「HTTP 路径」两条取法可以被**按字节**对账
（``tests/api/test_prescription_api.py`` 的
``test_the_offline_dump_is_byte_identical_to_the_http_endpoint``），
于是「换了取法之后产物会不会漂」这件事有一条守卫钉着，而不是靠一次人工比对。

--------------------------------------------------------------------------
怎么跑
--------------------------------------------------------------------------

::

    cd frontend
    npm run gen:api

或直接::

    python backend/scripts/dump_openapi.py --out somewhere/openapi.json
    python backend/scripts/dump_openapi.py            # 不给 --out 就写 stdout

⚠️ 不给 ``--out`` 时**stdout 上只有那份 JSON**（一切人类可读的话都走 stderr），
故 ``python backend/scripts/dump_openapi.py > openapi.json`` 也是对的。

--------------------------------------------------------------------------
⚠️ 它会被架构守卫 AST 解析
--------------------------------------------------------------------------

``tests/architecture/test_layering.py`` 与 ``test_domain_purity.py`` 都对
``BACKEND.rglob("*.py")`` 逐个 ``ast.parse``，``backend/scripts/**`` 在扫描面内；
``tests/architecture/test_source_hygiene.py`` 还会编译它并数 invalid escape。
故本文件必须 **UTF-8 无 BOM**、可解析、且不含任何裸的 invalid escape。

⚠️ 而本 docstring **自己就是 raw 的**（``r`` 前缀），理由与 ``app/main.py`` 那一个
逐字相同（Plan 06 Task 11 / A2）：它里面写着 Windows 路径 ``backend\pe.db``，
而 ``\p`` 在一个**非** raw 的字符串里就是一个 invalid escape sequence
——``tests/architecture/test_source_hygiene.py`` 会当场抓到它。
⚠️ 于是本文件是那条守卫落地之后的**第一个受益者**：它证明「全仓扫描」那一格
不是只为 ``main.py`` 那一处写的。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

#: ``backend/``。⚠️ 与同目录的 ``serve_app.py`` / ``demo_bootstrap.py`` 逐字同一条口径：
#: ``python backend/scripts/dump_openapi.py`` 放进 ``sys.path`` 的是**脚本所在目录**
#: （``backend/scripts/``），而 ``app`` 包在 ``backend/`` 下，故要显式补一条。
BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import DEFAULT_DB_URL  # noqa: E402
from app.main import create_app  # noqa: E402

__all__ = ["dump_openapi", "main", "render_spec"]

#: 禁区。⚠️ 路径**不在本文件里敲第二遍**：它由 :data:`app.config.DEFAULT_DB_URL`
#: （那个常量的字面值逐字就是 ``sqlite:///<backend>/pe.db``）反解出来，
#: 于是「禁区叫什么」仍然只有一个所有者。
FORBIDDEN_DB_FILE = pathlib.Path(DEFAULT_DB_URL.removeprefix("sqlite:///"))


def _assert_forbidden_zone_is_untouched(stage: str) -> None:
    """``backend/pe.db`` 不得存在。⚠️ dump 的**前后各调一次**（``stage`` 进报错文本）。

    ⚠️ 前一次的意义与本脚本无关：禁区已经被别人破了的话，本脚本**不该继续干活**
    ——它跑的是一次装配，而那一次装配会不会碰到那个文件，正是本条要证明的事，
    在一个已经存在那个文件的仓上证明不了任何事。
    """
    if FORBIDDEN_DB_FILE.exists():
        raise SystemExit(
            f"禁区：{FORBIDDEN_DB_FILE} 存在（在 {stage} 之前就已存在）。"
            "它不得存在（Global Constraints）。本脚本一次库都不建，故它不是本脚本建的；"
            "请手工删掉它再重跑。"
        )


def dump_openapi() -> dict:
    """**进程内**取那份 OpenAPI 文档。⚠️ 不连库、不起服务、不占端口。

    ⚠️ ``db_url="sqlite://"`` 是**显式**的（理由逐字见模块 docstring 第二节）：
    缺省会让 :func:`app.main._resolve_db_url` 去读 ``PE_DB_URL``、
    再回落到指向禁区的 :data:`app.config.DEFAULT_DB_URL`。
    ⚠️ 而 ``static_dist`` 刻意**不传**：SPA 那条 catch-all 是
    :class:`starlette.routing.Route` 而不是 ``APIRoute``，故它在不在都不改
    ``/openapi.json`` 一个字节（``tests/test_serve.py`` 的
    ``test_the_openapi_document_is_identical_with_and_without_the_spa`` 钉着那一格）。
    不传还有第二个好处：传了就要一个真实存在的 ``dist``，而本脚本与前端构建无关。
    """
    application = create_app(db_url="sqlite://")
    # ⚠️ 只调 openapi()，**从不** ``async with application.router.lifespan_context``、
    #    也从不起 uvicorn ⇒ lifespan 里的 init_db 一次都不跑（模块 docstring 第二节）。
    return application.openapi()


def render_spec(spec: dict) -> bytes:
    """一份 spec → 与 ``GET /openapi.json`` 的**响应体逐字相同**的那份字节。

    ⚠️ 四个参数逐字抄自 ``starlette.responses.JSONResponse.render``
    （FastAPI 的 ``/openapi.json`` 端点就是拿它渲染的）。改任何一个都会让
    「离线路径」与「HTTP 路径」两份字节不再相等，而那一格有守卫
    （``tests/api/test_prescription_api.py`` 的
    ``test_the_offline_dump_is_byte_identical_to_the_http_endpoint``）。
    """
    return json.dumps(
        spec, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    ).encode("utf-8")


def main(argv: "list[str] | None" = None) -> int:
    """``--out`` 给了就写那个文件（父目录不存在会建），没给就写 stdout。恒回 ``0``。"""
    parser = argparse.ArgumentParser(
        description="把 /openapi.json 的内容 dump 出来（进程内取，不起服务、不建库）。"
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="写到这个文件（缺省写 stdout；一切人类可读的话一律走 stderr）",
    )
    args = parser.parse_args(argv)

    _assert_forbidden_zone_is_untouched("dump")
    spec = dump_openapi()
    payload = render_spec(spec)
    _assert_forbidden_zone_is_untouched("dump 完")

    if args.out is None:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(payload)

    paths = spec.get("paths", {})
    operations = sum(
        1
        for methods in paths.values()
        for method in methods
        if method.lower() in ("get", "put", "post", "delete", "options", "head", "patch", "trace")
    )
    # ⚠️ stderr：stdout 上只许有那份 JSON（模块 docstring「怎么跑」那一节）。
    print(
        f"[dump_openapi] {len(payload)} 字节 / {len(paths)} 路径 / {operations} 操作 → "
        f"{'stdout' if args.out is None else args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
