"""两个通用读写助手：按自然键幂等写入、按批删除。

刻意保持薄——不做缓存、不做批量优化、不做仓储类层次。管道现在只需要这两件事；
等 Task 10 真的跑出性能问题再加，而不是先猜它需要什么。
"""
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

__all__ = ["upsert", "delete_by_batch"]


def upsert(
    session: Session, model: type[Any], key_fields: Sequence[str], values: dict
) -> Any:
    """按 ``key_fields`` 查一行：有则更新非键字段，无则插入，返回该实例。

    对 14 个模型通用，不针对任何一张表特化：``key_fields`` 由调用方按该表的自然键
    给出（如 ``("semester_id", "business_date")``），本函数只负责查、改、插。

    ``values`` 必须包含全部 ``key_fields``，缺一个就 ``KeyError``。那是调用方传错了
    键，属于程序缺陷；若退化成「查不到」而插入一条重复行，脏数据会静默留在库里。

    本函数既不 commit 也不 flush：事务边界由调用方掌握，「整批失败回滚」才成立。
    """
    stmt = select(model)
    for field in key_fields:
        stmt = stmt.where(getattr(model, field) == values[field])
    instance = session.scalar(stmt)
    if instance is None:
        instance = model(**values)
        session.add(instance)
        return instance
    for field, value in values.items():
        if field not in key_fields:
            setattr(instance, field, value)
    return instance


def delete_by_batch(session: Session, model: type[Any], batch_id: int) -> int:
    """删除 ``model`` 中 ``batch_id`` 匹配的全部行，返回删除条数。

    幂等重放靠它：重跑同一业务日期时，先按批清掉 ``derived_metrics`` 与
    ``stratification_result`` 的旧行再重写。这两张表都带 ``batch_id`` 外键指向
    ``daily_sync_run``，正是为了让这一步不必靠「学生 + 日期」去猜行的归属。
    """
    result = session.execute(delete(model).where(model.batch_id == batch_id))
    return result.rowcount
