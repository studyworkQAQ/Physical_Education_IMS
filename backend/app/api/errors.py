"""统一的错误响应形状与异常 → HTTP 状态码的映射。

**统一形状**（计划的显式决定）::

    {"error": {"code": str, "message": str, "detail": Any | None}}

为什么要有它：FastAPI 的缺省错误形状是 ``{"detail": …}``，而 SQLAlchemy 与 domain 层
抛出来的异常如果没人接，前端拿到的是 Starlette 的 HTML 错误页或一个裸 500。
一份 CRUD API 有二十几个资源，前端要写一个统一的错误提示组件；两种形状意味着
那个组件要认两套。``code`` 是给**程序**看的稳定标识（前端按它分支），
``message`` 是给**人**看的（会随措辞调整，不要按它分支），
``detail`` 放结构化的补充（例如请求校验那份带 ``loc`` 的清单），故它是 ``Any``。

**映射表**::

    ValueError                        → 422  unprocessable_value   （带消息原文）
    sqlalchemy IntegrityError         → 409  integrity_conflict    （带 exc.orig 原文）
    sqlalchemy NoResultFound          → 404  not_found
    fastapi RequestValidationError    → 422  request_validation_failed（detail 放清单，
                                                                    ⚠️ **按键名脱敏**）
    starlette HTTPException           → 原状态码，code 由状态码折算
    其余 Exception                     → 500  internal_error        （消息固定、不泄漏）

⚠️ **后两行不在计划枚举的四条里**，本 Task 加上了，理由是同一条：
「统一响应形状」这个决定要成立，就必须连 ``HTTPException`` 与 ``RequestValidationError``
一起折进来——而这两个恰恰是 CRUD API 里**最常见**的错误来源
（:func:`app.api.deps.require_scope` 抛的就是 ``HTTPException(403)``，
``current_student`` 缺头抛 ``HTTPException(401)``，请求体校验失败抛
``RequestValidationError``）。只折 ``ValueError`` / ``IntegrityError`` / ``NoResultFound``
的话，前端仍然要认两种形状。报告里记了这一处对派单的偏离。

**``ValueError`` 带消息原文**是计划的显式决定：domain 与加载器抛的那些消息逐字写明了
「哪个键、哪个文件、期望什么」（Plan 02 的模板 YAML 校验、Plan 03 Task 6 的
``alert_rules.yaml`` 校验都是这个形状），抹掉它等于让前端只看到「参数不对」。

**其余异常一律 500 且不泄漏**：消息固定成 ``internal_error`` 那一句，``detail`` 为
``None``，堆栈只进日志、不进响应体。原型也要有这一条，否则一次 ``KeyError``
会把连接串与表结构回给浏览器。
"""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, NoResultFound
from starlette.exceptions import HTTPException as StarletteHTTPException

__all__ = ["error_response", "register_error_handlers"]

_LOGGER = logging.getLogger(__name__)

#: 状态码 → 稳定的 ``code``。前端按 ``code`` 分支、不按 ``message``。
#: 没列进去的状态码折成 ``http_<状态码>``（例如 ``405`` → ``http_405``），
#: 于是「加一个新状态码」不会静默产生一个 ``None``。
_CODE_BY_STATUS: dict[int, str] = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "integrity_conflict",
    422: "unprocessable_value",
    500: "internal_error",
}

#: 500 的固定消息。它是**唯一**允许出现在 500 响应体里的字符串。
_INTERNAL_MESSAGE = "服务器内部错误"

#: ---------------------------------------------------------------------------
#: **Plan 05A Task 1：422 的 ``detail`` 要按键名脱敏**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **这一格是 Plan 05A 实测出来的、计划没提**：Pydantic v2 的
#: ``ValidationError.errors()`` 每一格都带一个 ``input``，而 ``missing`` 那一档的
#: ``input`` 是**整个请求体**（一个原始 ``dict``）。于是
#: ``POST /api/auth/login {"kind": "student", "password": "…"}``（漏了 ``login``）
#: 的 422 响应体里会**逐字回显那个明文口令**——实测取证::
#:
#:     {"error":{"code":"request_validation_failed", …,"detail":[
#:        {"type":"missing","loc":["body","login"],"msg":"Field required",
#:         "input":{"kind":"student","password":"我的超级机密口令"}}]}}
#:
#: 它泄漏给的是**提交它的那个人**（不是第三方），故不是越权；但那份响应体会被
#: 浏览器 devtools、反代访问日志、APM 采样与前端错误上报各存一份，
#: 而口令是**跨系统复用**的（用户拿同一个口令登别的站是常态）。
#: 这是 CWE-209 / CWE-532 那一类（错误消息里带敏感信息）。
#:
#: ⚠️ **``SecretStr`` 挡不住这一档**（:mod:`app.api.schemas.auth` 的模块 docstring
#: 逐字写了理由）：``missing`` 发生在**任何字段被解析之前**，故 ``input`` 里那一格
#: 还是原始 ``str``，不是 ``SecretStr``。``SecretStr`` 只挡「``password`` 字段自己
#: 校验失败」那一档。两道合起来才封住，故两处都在（不要以为改了一处就够了）。
#:
#: ⚠️ **按「键名」而不是按「端点路径」脱敏**：按路径就要维护一份「哪些路径收口令」
#: 的清单，而加第 6 个鉴权端点时忘了加进去是静默的。按键名的失效方向是安全的
#: ——多脱敏一个不敏感的键，只是 422 的 ``detail`` 里少一格调试信息。
#: ⚠️ 于是清单里除了 ``password`` 还有两个**今天就存在的秘密列**：
#: ``password_hash``（``student`` / ``teacher``）与 ``rpe_token``
#: （``class_session``，Plan 03 收尾小修波把它从匿名读模型上摘掉的那一个）
#: ——它们在 ``*Create`` 里都**不是**字段（走 :data:`_SERVER_FILLED_COLUMNS` 那一档），
#: 故今天不可达；列进来是因为「一个客户端多传一个键」在 Pydantic 缺省的
#: ``extra="ignore"`` 下**不会**进 ``errors()``，但换成 ``extra="forbid"`` 就会，
#: 而那一格不该等到换的那天再补。
#: ⚠️⚠️ **Plan 08 Task 4 加了两个**，而这两个里**第一个是今天就可达的**：
#: ``token``（``POST /api/auth/bind-with-token`` 的请求体那一格，
#: :class:`app.api.schemas.auth.TokenBindCreate`）——它是一格**一次性凭据**，
#: 而 ``TokenBindCreate`` 只有两格，故「缺 ``password``」那一档的 ``input``
#: **就是整个请求体**、里面那一格是明文令牌（``SecretStr`` 挡不住，理由见上面那段）。
#: ⚠️ 于是这一格与 ``password`` 是**同一档失效**，处置逐字相同。
#: ``token_hash``（``bind_token``）与 ``password_hash`` 同族：它不是任何 ``*Create``
#: 的字段（哈希由服务端算，逐字理由见
#: :class:`app.api.schemas.auth.TokenIssueCreate` 的 docstring），故今天不可达，
#: 列进来是同一条「不该等到换 ``extra="forbid"`` 那天再补」。
_SENSITIVE_INPUT_KEYS = frozenset(
    {"password", "password_hash", "rpe_token", "token", "token_hash"}
)

#: 脱敏之后填进去的字面量。⚠️ **不用 ``None``**：``None`` 与「客户端传了 ``null``」
#: 无法区分，而后者是一个真实的、要能被 422 说清楚的输入。
_REDACTED = "***"


def _redact(value: Any) -> Any:
    """递归地把 :data:`_SENSITIVE_INPUT_KEYS` 那些键的值换成 :data:`_REDACTED`。

    ⚠️ **只认 ``dict`` 的键名**，不认「值看起来像口令」：后者要一份启发式，
    而启发式必然漏（一个 8 位的随机串与一个 8 位的学号在形状上无法区分），
    漏的那一次是静默的。
    ⚠️ ``list`` / ``tuple`` 都展开成 ``list``：``jsonable_encoder`` 本来也会把 tuple
    折成 JSON 数组，故这一格不改变输出形状。
    ⚠️ 其它类型原样返回（含 ``None``、标量、以及 Pydantic 塞进 ``ctx`` 的异常对象
    ——那一格交给 :func:`~fastapi.encoders.jsonable_encoder`）。
    """
    if isinstance(value, dict):
        return {
            key: (_REDACTED if key in _SENSITIVE_INPUT_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _redacted_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """:meth:`pydantic.ValidationError.errors` → 脱敏之后的那份清单。

    两处脱敏，各挡一档：

    1. **``input`` 里的敏感键**（:func:`_redact` 递归）——挡「别的字段缺失，
       而 ``input`` 是整个请求体」那一档（上面那段取证就是它）；
    2. **``input`` 本身就是敏感字段的值**（``loc`` 的末段是敏感键名）——挡
       「``password`` 自己校验失败」那一档。⚠️ ``SecretStr`` 也挡这一档，
       但**只在字段类型是 ``SecretStr`` 时**；按 ``loc`` 判的那一道与类型无关，
       故将来有人把一个口令字段写成裸 ``str`` 时它仍然挡得住。
    """
    redacted: list[dict[str, Any]] = []
    for error in exc.errors():
        item = dict(error)
        location = item.get("loc") or ()
        leaf = location[-1] if location else None
        if "input" in item:
            item["input"] = (
                _REDACTED if leaf in _SENSITIVE_INPUT_KEYS else _redact(item["input"])
            )
        if "ctx" in item:
            item["ctx"] = _redact(item["ctx"])
        redacted.append(item)
    return redacted


def error_response(
    status_code: int,
    code: str,
    message: str,
    detail: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """造一个统一形状的响应。**这是全仓唯一写 ``{"error": {...}}`` 这个字面量的地方**
    （单一所有者）：六个处理器都经它出去，故改形状只改这一处。

    ``headers`` 是给 ``HTTPException`` 用的：它的 ``headers``（例如 401 的
    ``WWW-Authenticate``、405 的 ``Allow``）是协议的一部分，折形状时不能丢。
    """
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "detail": detail}},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """把上面那张映射表装到 ``app`` 上。由 :func:`app.main.create_app` 调用一次。

    注册**顺序无关**：Starlette 的 ``ExceptionMiddleware`` 按异常类的 MRO 找最窄的那个
    处理器，而 ``Exception`` 那一档被单独交给外层的 ``ServerErrorMiddleware``，
    故它永远最后命中。
    ``tests/test_main.py::test_the_catch_all_handler_does_not_swallow_http_exceptions``
    把「窄的先命中」这件事在本仓验了一遍，而不是只信框架的文档。
    """

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        # 消息原文照发：这些 ValueError 来自 domain 与 YAML 加载器，
        # 它们逐字写明了「哪个键、哪个文件、期望什么」，是给调用方看的。
        return error_response(422, "unprocessable_value", str(exc))

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # ⚠️ 用 exc.orig（DBAPI 的原始消息，如 "UNIQUE constraint failed: student.student_no"）
        # 而不是 str(exc)：后者带**完整的 SQL 语句与绑定参数**，回给前端等于把 schema
        # 与数据一起送出去。orig 缺失时退化成 code 那一句，绝不退回 str(exc)。
        origin = getattr(exc, "orig", None)
        message = str(origin) if origin is not None else _CODE_BY_STATUS[409]
        return error_response(409, _CODE_BY_STATUS[409], message)

    @app.exception_handler(NoResultFound)
    async def _no_result_found(request: Request, exc: NoResultFound) -> JSONResponse:
        # scalar_one() / one() 查不到行时抛的就是它。消息是 SQLAlchemy 的英文原文，
        # 它不含数据、只说明「这个查询要求恰好一行」，故照发。
        return error_response(404, _CODE_BY_STATUS[404], str(exc))

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # jsonable_encoder 是必需的：Pydantic v2 的 errors() 里 ctx 可以带任意对象
        # （例如一个 ValueError 实例），直接塞进 JSONResponse 会 TypeError。
        # FastAPI 自己的缺省处理器也是这么做的。
        # ⚠️ **Plan 05A Task 1：先脱敏、再编码**（顺序是承重的：编码之后 ``input``
        # 已经变成一个纯 JSON 结构，那时再脱敏就要多认一种形状）。
        # 逐字理由与实测取证见 :data:`_SENSITIVE_INPUT_KEYS` 上方那段注释。
        return error_response(
            422,
            "request_validation_failed",
            "请求参数校验未通过",
            jsonable_encoder(_redacted_validation_errors(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # 这一支让 require_scope 的 403、current_student 的 401、以及 Starlette 自己的
        # 404/405 全部拿到统一形状；headers 照转（协议的一部分）。
        return error_response(
            exc.status_code,
            _CODE_BY_STATUS.get(exc.status_code, f"http_{exc.status_code}"),
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 堆栈只进日志。exc_info=exc 是显式的：ServerErrorMiddleware 是在自己的
        # except 块里 await 本处理器的，sys.exc_info() 那时确实还指着 exc，
        # 但显式传一份不依赖这个时序。
        _LOGGER.exception("未处理的异常 %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(500, _CODE_BY_STATUS[500], _INTERNAL_MESSAGE)
