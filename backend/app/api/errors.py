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
    fastapi RequestValidationError    → 422  request_validation_failed（detail 放清单）
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
        return error_response(
            422,
            "request_validation_failed",
            "请求参数校验未通过",
            jsonable_encoder(exc.errors()),
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
