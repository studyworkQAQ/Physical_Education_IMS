"""``app/api/schemas/`` 包内共享的两件基础设施：读模型基类与取值域校验助手。

与 :mod:`app.db.models._shared` 同一个立意（那个模块的 docstring 逐字给了理由，本模块不
抄第二份）：**七个** schema 模块都要用它们，塞进其中任何一个都会让另外六个为了拿一个基类
而 import 一个与它毫无关系的小节（例如 ``derived.py`` 为了 ``ReadModel`` 去 import
``organisation``）。模块名带前导下划线，故它不在 :mod:`app.api.schemas` 的重导出清单里。

⚠️ **本模块是 Plan 03 Task 3 在计划 File Structure 之外加的一个文件**（那份清单只列了
``__init__`` / ``organisation`` / ``assessment`` / ``derived`` / ``prescription``）。
加它的理由就是上面那条，而先例是 :mod:`app.db.models._shared`。
"""
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = ["ReadModel", "one_of"]


class ReadModel(BaseModel):
    """全部 ``*Read`` 模型的基类：打开「从 ORM 对象的**属性**读字段」。

    ``from_attributes=True``（Pydantic v1 的 ``orm_mode``）是让
    ``response_model=XxxRead`` 能直接吃一个 SQLAlchemy 实例的唯一开关：没有它，
    ``model_validate`` 会要求入参是 ``dict``，于是 23 个资源的每个端点都得自己写一遍
    ``{c.name: getattr(row, c.name) for c in …}``——那正是本工厂要消灭的重复。

    ⚠️ **它只对 ``*Read`` 打开**：``*Create`` / ``*Update`` 直接继承
    :class:`~pydantic.BaseModel`。那两类的输入是**请求体**（JSON），
    给它们开 ``from_attributes`` 等于允许「把一个 ORM 行当请求体传进来」，
    而那种输入在 HTTP 边界上不存在。
    """

    model_config = ConfigDict(from_attributes=True)


def one_of(column: str, value: Any, allowed: Iterable[str]) -> Any:
    """``value`` 是否落在 ``allowed`` 里；不在就抛带**列名与取值域**的 :class:`ValueError`。

    给 :func:`pydantic.field_validator` 用的助手。抛 ``ValueError`` 而不是
    ``HTTPException``：Pydantic 会把它包成 ``ValidationError``，FastAPI 再抛
    ``RequestValidationError``，最后由 :mod:`app.api.errors` 折成 **422** +
    统一形状。这条链是本仓既有的（``tests/test_main.py`` 的
    ``test_domain_value_error_maps_to_422`` 与
    ``tests/api/test_scope.py::test_a_non_integer_identity_header_is_422`` 各钉了一半）。

    **为什么要有它**：三张可写表的枚举列（``student.sex`` /
    ``course_section.grouping_mode`` / ``fitness_test_batch.timepoint``）在 DB 侧都有
    ``CheckConstraint``，但那道约束是**写库时**才响的，响的方式是 ``IntegrityError`` →
    **409**。而「客户端送了一个不在取值域里的值」是请求校验错误，正确的码是 **422**。
    没有本助手，前端表单填错一个下拉框会收到「integrity_conflict」，
    于是它会把一个自己的输入错误当成「与别人撞了」。

    ⚠️ **取值域的单一所有者仍是模型类常量**（``Student.SEXES`` 一类，本包约定 2 的
    「类常量是唯一真相」）：本函数**接**那个集合作参数，不自己再声明一份词表。
    于是「两处设防」变成三处（类常量 / SQL CHECK / Pydantic），而三处只有**一份**词表。

    ``value is None`` 一律放行：``*Update`` 模型里每个字段都是 ``X | None = None``，
    而 PATCH 的语义是「没传就不改」（``model_dump(exclude_unset=True)``），
    故 ``None`` 在这里的意思是「不校验」，不是「把这一列设成 NULL」。
    ⚠️ 代价（硬规矩 #39）：``PATCH {"sex": null}`` 因此会通过 schema 校验、
    落到 DB 的 NOT NULL 上，得到 **409** 而不是 422。这一档今天没有守卫，
    已登记为 Task 3 报告的关切。
    """
    if value is not None and value not in allowed:
        raise ValueError(
            f"{column} 的取值必须是 {sorted(allowed)} 之一，收到 {value!r}"
        )
    return value
