"""抽取阶段：从适配器拉三类原始记录，并按**本批业务日期**截断（Ruling 140）。

``business_date`` 与适配器的 ``since`` 是**两件事**，混用会静默产出错误结论：

* ``since`` 是**排他**的增量水位线（``> since``，Ruling 33 / base.py 契约第 3 条），
  它回答「上次同步到哪儿了」；
* ``business_date`` 是**本批的业务日期**，它回答「这一批算的是哪一天」。

把 ``business_date`` 直接当 ``since`` 传会得到「比今天更新的数据」——那是时间旅行。
故本模块的口径是：

    ``since = 上一次跑完（success 或 partial）的运行的 business_date``（首批为 ``None`` = 全量），
    取回后在本地按 ``<= business_date`` 过滤，**晚于 ``business_date`` 的记录一律不进本批**。

**为什么必须本地再过滤一次**：仿真数据是一次性生成的，源 CSV 里同时躺着两个学年六个时点
的全部记录；真实乐跑不会有「未来的数据」，但重放必须假定它可能有。放进来的后果是
「按业务日期幂等重放」失去意义——重跑 09-15 却用到了 12-15 的体测，而同一个业务日期两次
运行会得到不同的分层结果，spec §1.3 的可复现性当场作废。

**水位线为什么按「严格早于本批业务日期的上一次**跑完**的运行」取**：重跑同一天时，那一天自己的
运行记录**不算**水位线（``business_date < business_date`` 为假），故重跑拿到的 ``since``
与首跑逐字相同 → 抽到同一批记录 → 幂等。「跑完」= ``status ∈ {"success", "partial"}``
（Ruling 211）：``partial`` 是「整批跑完、但有记录因学号解析不到而被整条跳过并留痕」，
它的数据已全部落库，故同样推进水位线；``status = "failed"`` 的运行**不**推进——
它没有成功写入任何东西（本批已被 SAVEPOINT 撤销），把它当水位线会让那一段数据永久丢失。
两者的完整论证与实测后果见 :func:`previous_watermark` 的 docstring。

采集日期实测（``SEMESTERS`` × ``TIMEPOINT_SEQUENCE``）：上学年 ``2024-09-02 / 2024-10-21 /
2024-12-16``，本学年 ``2025-09-01 / 2025-10-20 / 2025-12-15``。故 ``business_date =
2025-09-15`` 这一批只应含**上学年全部 3 个时点 + 本学年 week1**。
"""
import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import (
    DataSourceAdapter, RawBodyCompRecord, RawFitnessRecord, RawSurveyRecord,
)
from app.db import models

__all__ = ["Extracted", "extract", "previous_watermark", "parse_business_date"]


def parse_business_date(business_date: str) -> dt.date:
    """``business_date`` → ``date``，格式非法立刻 ``ValueError``。

    与适配器 :func:`app.adapters.mock_lepao._validated_since` 同一条纪律：格式写错若静默
    退化成「全量」或「空」，症状只是「今天没同步到数据」，不报错。它是幂等键
    ``(semester_id, business_date)`` 的一半，也是 ``derived_metrics.computed_on`` 的取值，
    形状必须只有一种（零填充 ``YYYY-MM-DD``，Ruling 38）。
    """
    try:
        return dt.date.fromisoformat(business_date)
    except (TypeError, ValueError):
        raise ValueError(
            f"business_date 必须是 ISO 日期串（YYYY-MM-DD），收到: {business_date!r}"
        ) from None


@dataclass(frozen=True)
class Extracted:
    """一次抽取的产物：三类**已按 ``<= business_date`` 截断**的原始记录。

    ``since`` 是本次实际使用的水位线（``None`` = 全量）。把它带在返回值里不是为了好看：
    幂等重放要求「同一个业务日期两次运行抽到同一批记录」，而这只在 ``since`` 相同时成立，
    留痕让这件事可核对，而不是只能靠推理。
    """

    fitness: list[RawFitnessRecord]
    body_comp: list[RawBodyCompRecord]
    survey: list[RawSurveyRecord]
    since: str | None
    business_date: dt.date


def previous_watermark(session: Session, business_date: dt.date) -> str | None:
    """上一次**跑完**（``status`` ∈ ``{"success", "partial"}``）、且业务日期**严格早于**本批的
    那一次的 ``business_date``。

    查不到（首批、或本批之前全是 ``failed``）时返回 ``None``，即全量抽取——保守方向：多抽一次
    由 ``repo.upsert`` 的业务唯一约束吸收（Ruling 24），少抽一次则是**永久丢数据**。

    **``partial`` 也算水位线（Ruling 211）**：``run_daily`` 只在 ``unattributable > 0`` 时写
    ``partial``——``daily.py`` 的 ``run.status = "partial" if unattributable else "success"``；
    而同一文件 ``run_daily`` 的 docstring 把 ``"partial"`` 定义为「**整批跑完**，但有记录因
    **学号解析不到 ``student`` 表**而被整条跳过（已在 ``cleaning_log`` 里逐条留痕）」。即那一天
    该入库的东西**已经全部入库**，只是有一条数据质量问题被跳过并留了痕——它完全有资格当水位线。
    改前本函数的 docstring 只论证了 ``failed`` 为什么不该推进水位线（「它没有成功写入任何东西」），
    **完全没有考虑 ``partial``**，而同一个包里那两段 docstring 直接矛盾，这就是这条缺陷能藏
    5 个 Task 的原因（``tests/pipeline/`` 此前**没有任何一条**走到 ``unattributable`` 分支）。

    排除 ``partial`` 的后果是实测的：一条学号解析不到的合法记录会让**每一天**都停在
    ``partial``、水位线**永久冻结在 ``None``**，于是每天重抽全量。本轮亲跑（60 人 /
    ``seed=20250828`` / 往 ``fitness.csv`` 追加一条 ``student_no="UNKNOWN999"``、
    ``tested_on=2025-09-01`` 的合法记录 / ``2025-09-01..2025-09-06`` 六天，独立临时库；
    「改前」= 把本函数的过滤条件换回 ``status == "success"``）::

        口径                     改前（只认 success）        改后（success + partial）
        ------------------------ -------------------------- ----------------------------
        六天 status              partial ×6                 partial, success ×5
        次批水位线                None ×6（永久冻结）         09-01 … 09-06（逐日推进）
        extracted_fitness        243 ×6（每天重抽全量）      243, 0, 0, 0, 0, 0
        cleaning_log 行数        **804**（孤儿学号 6 条）    **134**（孤儿学号 1 条）

    即同一条数据质量问题在改前留下**六条互相矛盾的交代**，而分层结果一模一样
    （``stratification_result`` 两侧都是 360 行）——全部代价都花在重复劳动与审计噪声上，
    且退出码恒 0（Ruling 188 明确让 ``partial`` 不改退出码），**全程静默**。
    守卫见 ``tests/pipeline/test_daily.py`` 的
    ``test_orphan_student_no_yields_partial_but_still_advances_the_watermark``。
    更大规模（500 人 ×112 天）的量级见账本 Ruling 211，**本轮未复跑**、按硬规矩 #39 记为
    历史实测；被守卫的是上面这组 60 人的数。

    ``failed`` 仍然不算：本批已被 SAVEPOINT 全量撤销（``daily.py`` 的 ``_record_failure``），
    把它当水位线会让那一段数据永久丢失。

    **不按 ``semester_id`` 过滤**：水位线是**数据源**的属性而不是学期的属性，
    ``DataSourceAdapter.fetch_*`` 的 ``since`` 也是全局的（契约里没有学期参数）。
    跨学期回填时按学期各取一条水位线会让同一份 CSV 被两个学期各自「全量」抽一遍。
    """
    found = session.scalar(
        select(models.DailySyncRun.business_date)
        .where(
            # Ruling 211：``partial`` 是「整批跑完、但有记录因学号解析不到而被整条跳过」，
            # 它的数据已全部落库，故同样推进水位线；只有 ``failed``（本批已回滚）不推进。
            models.DailySyncRun.status.in_(("success", "partial")),
            models.DailySyncRun.business_date < business_date,
        )
        .order_by(models.DailySyncRun.business_date.desc())
        .limit(1)
    )
    return None if found is None else found.isoformat()


def _not_later_than(record_date: str, business_date: dt.date) -> bool:
    """记录日期是否 ``<= business_date``。

    两侧都是 ``date``：记录侧的日期列已由适配器**无条件**解析并归一化成零填充
    ``YYYY-MM-DD``（Ruling 41），故 ``date.fromisoformat`` 一定成功。不用字符串字典序
    比较——那正是 :func:`app.adapters.mock_lepao._is_after` 的 docstring 里记着的坑
    （``'2025-9-5' > '2025-10-01'`` 为真）。
    """
    return dt.date.fromisoformat(record_date) <= business_date


def extract(session: Session, adapter: DataSourceAdapter, business_date: str) -> Extracted:
    """按 ``since = previous_watermark(...)`` 增量拉取，再本地截断到 ``<= business_date``。

    三个 ``fetch_*`` 一律**当场耗尽成 list**：适配器返回的是惰性生成器（契约要求），
    而本批记录随后要被清洗层遍历两次（一次去重、一次逐字段处置），且抽取计数要写进
    ``daily_sync_run``——留着一个半消费的生成器只会让「抽到多少条」这件事说不清。
    """
    as_of = parse_business_date(business_date)
    since = previous_watermark(session, as_of)
    fitness = [
        record for record in adapter.fetch_fitness(since)
        if _not_later_than(record.tested_on, as_of)
    ]
    body_comp = [
        record for record in adapter.fetch_body_comp(since)
        if _not_later_than(record.measured_on, as_of)
    ]
    survey = [
        record for record in adapter.fetch_survey(since)
        if _not_later_than(record.filled_on, as_of)
    ]
    return Extracted(
        fitness=fitness,
        body_comp=body_comp,
        survey=survey,
        since=since,
        business_date=as_of,
    )
