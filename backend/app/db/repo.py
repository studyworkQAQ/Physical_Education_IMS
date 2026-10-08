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

    **更新分支是 PATCH 语义，不是 PUT**：只有出现在 ``values`` 里的键会被写回，
    没给的列一律保持库中原值。后果必须说清楚——重放同一业务日期时，若本次抽取
    少了上一轮填过的某一列（源系统那列整列缺失、或某个分支没走到），旧值会**静默
    存活**，读起来像是「这一轮也算出了这个值」。所以 **Task 10 每次调用都必须传该
    表的完整列集合**，让「本轮没算出来」表现为显式写入 ``None``，而不是表现为
    「沿用上一轮」。本函数刻意不做「补全缺失键」的猜测：猜不出调用方到底是漏传
    还是有意不改。

    **插入分支返回的实例，``id`` 在 flush 之前是 ``None``**。Task 10 要用这个 ``id``
    当 ``batch_id``，而 ``derived_metrics.batch_id`` / ``stratification_result.batch_id``
    都是 NOT NULL，故忘了 flush 会在写入派生行时炸出来，不会静默落一个 NULL——
    但这条契约写在这里，免得靠炸来发现。

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

    ``batch_id`` 在本项目里**专指「指向 ``daily_sync_run`` 的外键」**，也就是本函数
    可据以删除的归属键；全库只有五张表有这一列（Ruling 31，由
    ``test_only_derived_tables_expose_batch_id`` 钉住）：Plan 01 的三张派生表
    （``DerivedMetrics`` / ``StratificationResult`` / ``PercentileSnapshot``）与
    Plan 02 Task 6 的两张处方表（``Prescription`` / ``WeeklyAdjustment``，P6-A8：
    Task 7 的 ``_replay_cleanup`` 要按 ``batch_id`` 删它们，故列在本 Task 就加）。
    指向别的父表的键一律用可区分
    的名字：``fitness_test_result.test_batch_id`` 指体测批次、``cleaning_log.sync_run_id``
    指同步运行。

    幂等重放靠它：重跑同一业务日期时，先按批清掉旧行再重写。**今天**
    ``app/pipeline/daily.py`` 的 ``_replay_cleanup`` 只清 Plan 01 那三张派生表；
    Task 7 会把两张处方表接进那份清单（删的顺序是承重的：``weekly_adjustment``
    的 ``prescription_id`` 指向 ``prescription``，而 ``PRAGMA foreign_keys=ON``
    真的在强制它，故必须**先删子表**）。五张表都带
    ``batch_id`` 外键指向 ``daily_sync_run``（``percentile_snapshot`` 是 Ruling 29
    补上的），正是为了让这一步不必靠「学生 + 日期」去猜行的归属。

    **进来先 flush**：下面那条批量 DELETE 只作用于**已经在库里**的行。若调用方在同一
    个会话里先 ``upsert`` 了一批尚未落库的新行、再调本函数（重放路径的自然写法就是
    「算完就写、写完再清旧的」，顺序颠倒很容易发生），新行会躲过这次删除、随后又被
    autoflush 插进去——调用方以为自己清干净了，实际留下的是「旧行没了、新行双份」。
    先 flush 就把「待删的行」定义成「本会话到此为止写过的全部行」。

    传入没有 ``batch_id`` 列的模型会抛 ``AttributeError``（点名模型与字段），不是静默
    返回 0：``cleaning_log`` 那一列叫 ``sync_run_id``、``fitness_test_result`` 那一列叫
    ``test_batch_id``，把表名记错就正好踩这里。

    对 ``FitnessTestResult`` 而言这个报错是**刻意设计**的（Ruling 31）：改名之前它也
    叫 ``batch_id``，误拿一个 ``sync_run_id`` 来删它时，因 ``fitness_test_batch.id``
    只有 1/2/3（week1/week8/week16）而 ``daily_sync_run.id`` 按业务日递增，凡
    ``sync_run_id ∈ {1, 2, 3}`` 都会匹配上并**静默删掉真实源体测数据**（实测 3 → 2 行、
    返回 1、无任何异常）；两列都是 int，外键拦不住（每个值各自合法），属性存在所以
    ``AttributeError`` 也拦不住。删源数据比删派生行严重：派生行重算就回来了，源体测
    数据删了就是删了。故本函数可安全传入的只有上面那五张带 ``batch_id`` 的表。
    """
    session.flush()
    result = session.execute(delete(model).where(model.batch_id == batch_id))
    return result.rowcount
