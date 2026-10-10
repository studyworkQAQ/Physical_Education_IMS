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

    对 **25** 个模型通用（⚠️ 本处此前印的是「14 个」，那是 Plan 01 结案时的表数；Plan 02 加 4 张、Plan 03 Task 2 加 7 张之后是 25，Plan 03 Task 9 实测更正），不针对任何一张表特化：``key_fields`` 由调用方按该表的自然键
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
    可据以删除的归属键；全库只有九张表有这一列（Ruling 31，由
    ``test_only_batch_owned_tables_expose_batch_id`` 钉住）：Plan 01 的三张派生表
    （``DerivedMetrics`` / ``StratificationResult`` / ``PercentileSnapshot``）、
    Plan 02 Task 6 的两张处方表（``Prescription`` / ``WeeklyAdjustment``，P6-A8：
    Task 7 的 ``_replay_cleanup`` 要按 ``batch_id`` 删它们，故列在本 Task 就加），
    以及 Plan 03 Task 2 的四张反馈/预警表（``ClassSession`` / ``TrainingLog`` /
    ``Alert`` / ``WeeklyClassReport``）。
    ⚠️ **九张里有两张的这一列是可空的**（``class_session`` / ``training_log``，Plan 03
    Task 5 的 P5-A1）：那两张表各有**两个**写入来源——管道整批写的那一种带 ``batch_id``，
    **用户实时写的那一种留 ``NULL``**（教师在前端建课次、学生在 H5 上打卡），
    而 ``NOT NULL`` 只容得下一个来源。⚠️ **可空对本函数的语义恰好是对的**：
    下面那条 ``WHERE model.batch_id == :b`` 在 SQL 的三值逻辑里对 ``NULL`` 行**恒不成立**
    （``NULL = 任何值`` 既不是真也不是假），故**用户实时写的行天然躲过按批删除**——
    这正是那三张干脆不带 ``batch_id`` 的表（``rpe_record`` / ``mini_test`` /
    ``notification``）想要的性质：重放是「同一批输入得到同一批输出」，
    而学生交过的作业不是这批输入的输出，删掉它就是删源数据。
    ⚠️ 于是本函数的**契约变窄了一格**、但没有变错：对那两张表它删的是
    「**这一批同步写进来的**那些行」，不是「这张表里属于这一天的所有行」。
    指向别的父表的键一律用可区分
    的名字：``fitness_test_result.test_batch_id`` 指体测批次、``cleaning_log.sync_run_id``
    指同步运行。⚠️ Plan 03 Task 2 的另外三张（``rpe_record`` / ``mini_test`` /
    ``notification``）**刻意不带** ``batch_id``：它们是用户实时写入的，按批删会抹掉
    学生刚交的作业（理由见 :mod:`app.db.models.feedback` 的模块 docstring）。

    幂等重放靠它：重跑同一业务日期时，先按批清掉旧行再重写。
    ⚠️ **「有 ``batch_id``」不等于「在 ``_replay_cleanup`` 的清单里」**：
    ``app/pipeline/daily.py`` 的 ``_replay_cleanup`` **今天清的是上面九张里的七张**
    （Plan 01 的三张派生表 + Plan 02 的 ``prescription`` / ``weekly_adjustment``
    + Plan 03 Task 7 的 ``alert`` + Plan 03 Task 8 的 ``weekly_class_report``；
    删的顺序是承重的：``weekly_adjustment`` 的 ``prescription_id`` 指向 ``prescription``，
    而 ``PRAGMA foreign_keys=ON`` 真的在强制它，故必须**先删子表**，P7-A4）。
    ⚠️ **本处此前印的是「五张」与「``Alert`` 与 ``WeeklyClassReport`` 由 Task 8 接进清单」，
    两个数都已过期**（Plan 03 Task 9 更正）：``Alert`` 是 **Task 7** 接进的、
    ``WeeklyClassReport`` 才是 Task 8，故今天是**七张**。Plan 03 那四张里，
    ⚠️ **``TrainingLog`` Task 5 没有接**（本处此前印的是「由 Task 5 接」，现按**实际
    发生的事**改写——留一个不兑现的预告，正是下面那段 ⚠️ 批评过的同一个形状）：
    ① ``app/pipeline/daily.py`` **今天一个字节都不往 ``training_log`` 写**（Task 5 实测：
    ``app/`` 下唯一构造 ``TrainingLog`` 行的生产代码是 :mod:`app.demo_data`），
    故把它接进清单今天删的是 **0 行**——那是一段死代码，而「一条删 0 行的清理」
    会让下一个人以为打卡已经被重放管住了；② 这一列 Task 5 起**可空**，
    学生实时打的那些行本来就躲过本函数，故「接进去」的收益只在管道**真的**开始
    同步乐跑打卡时才出现；③ 那一步属于 Task 9（``POST /api/pipeline/run-daily``）
    或之后——**谁让管道写 ``training_log``，谁负责把它接进 ``_replay_cleanup``**。
    已登记为关切（硬规矩 #39）。
    而 **``ClassSession`` 不得接**——``rpe_record.class_session_id`` 是 NOT NULL 的
    外键指向它，按批删课次会当场 FK 违例（改成 ``CASCADE`` 更糟：会连带删掉学生
    刚交的快评），它的幂等手段是 ``upsert`` 按
    ``(course_section_id, session_date, period)`` 更新，与三张源表同一档。
    ⚠️ 本处此前印的是「**今天**只清 Plan 01
    那三张派生表；Task 7 会把两张处方表接进那份清单」——Task 7 早已接完，那句话于是变成
    了对一个**已完成动作**的预告，读它的人会以为处方表今天不在清理清单里、进而以为重放
    会让 ``weekly_adjustment`` 翻倍（待清扫第 8 条，Task 9 结案）。九张表都带
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
