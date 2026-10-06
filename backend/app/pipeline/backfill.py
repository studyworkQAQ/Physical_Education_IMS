"""整学期回填：把 ``[start, end]`` 里的**每一个业务日期**逐日交给 :func:`~app.pipeline.daily.run_daily`。

本模块只有两个函数加一个 CLI：:func:`business_dates` 展开日期序列，:func:`run_backfill`
逐日回放。它**不含任何算法**——六个阶段全在 :mod:`app.pipeline.daily` 里，本模块的职责
只有「把一天变成一段时间」与「一天炸了不要连累其余天」。

三条承重的决定：

1. **``business_dates`` 是闭区间**（计划 Interfaces 的字面），而 ``Semester.end_date`` 是
   **排他**的（Ruling 174）。两者一凑就是 113 天而不是 16 周 × 7 = 112 天，故减一天的换算
   放在 CLI 层（:func:`main`），**不改** :func:`app.seed.config.semester_end_date`——那是
   Task 6 的冻结代码，它返回的算式（开学日 + 教学周数）本身是对的。

2. **每日独立事务，单日失败不阻断后续**（计划 Step 3）。这不是本模块新发明的原子性：
   ``run_daily`` 自己就是「整批一个 SAVEPOINT + 末尾 ``commit``」，失败时它先撤销本批、
   再在**独立小事务**里写下 ``status = "failed"`` 的运行记录，然后原样重抛
   （:func:`app.pipeline.daily._record_failure`）。本模块吞掉那次重抛、把失败日的运行记录
   取回来补进返回列表、继续跑下一天。**唯一例外**：连那条留痕都没写进去时原样重抛真因
   ——那一天在库里将没有任何痕迹，而继续跑只会让「哪些天跑过」永久无法交代（何况留痕机制
   本身坏了，剩余各天会以同一种方式失败）。

3. **不做任何性能优化重构**（Ruling 172）。500 人 × 112 天完整回放的墙钟（即 Step 6 那条
   CLI）实测 **17.98–18.92 s，n=5 次独立干净跑**（场景 A、sem=2，每次一个独立临时库，
   fix round 3 在 commit ``b6ebaa3`` 上量的）。本处此前印的是单次点值 17.6 s，按 Ruling 201
   一律改成**区间 + 样本数**。按 ``daily_sync_run.started_at / finished_at`` 反推的单日分布，
   五次跑的逐次取值范围是 ``min 0.102–0.108 / p50 0.125–0.134 / p95 0.142–0.159 /
   max 2.033–2.161``（秒），112 天全部 ``success``。只有 **3 天**抽到新数据（正是本学年
   week1 / week8 / week16 三个采集日；括号内是 n=5 的区间，此前印的是单次点值）：
   ``2025-09-01`` **2.03–2.16 s**（原 1.95）、``2025-10-20`` **0.555–0.598 s**（原 0.57）、
   ``2025-12-15`` **0.575–0.604 s**（原 0.55；这一天在仓内三处被印成 0.60 / 0.59 / 0.55 s
   三个点值——**不是矛盾、是跑次样本**，本轮 8 次回放里它落在 0.575–0.618 s），其余
   **109 天 0.102–0.178 s**（原 0.104–0.158，上界本轮被推到 0.178）——Task 10 的
   「快照按需物化 + 无新数据不重算」正是达标的原因（实测 ``percentile_snapshot`` 全学期只有
   **96 行 = 3 次物化 × 32**，32 = sex 2 × age_group 2 × metric 8；本轮 A 6/6、B 3/3 都是 96）。
   spec §1.3 的「500 人批量管道回放 < 60 秒」在两种读法下都达标（整学期 ≈18 s = 3.2–3.3×、
   单个采集日 ≈2.1 s = 28–29×）。**守卫**：``tests/pipeline/test_backfill.py`` 的
   ``test_backfill_500_students_under_60_seconds`` 断言 ``elapsed < 60``，整学期回放超过
   60 s 会红；**上面这些区间、单日点值与 96 行都不被守卫**（跑次间有 ±5% 量级的波动，
   把它们钉成断言只会造出抖动红灯）——96 行那一半由本文件下面那张四场景表的历史取证承担。
   计划原文那条优化阶梯（快照复用 / pandas 向量化 / WAL）是为一个**不存在的**性能问题付出
   复杂度，一条都没落地。

   ⚠️ **96 行还是 128 行，承重条件只有一条：预跑的那一天后来有没有以同一幂等键再跑过**
   （Ruling 192/193）。Ruling 172/178 记的「4 天有新数据 / 128 行 = 4 次物化 / 89.1 MB」是
   下表**场景 D**（预检探针的跑法）的状态，**不是** Step 6 那条干净跑法——干净跑法是场景 A
   （3 天 / 96 行）。四个场景各用一个独立临时库实测，fix round 2 在 commit ``13207b2`` 上
   逐个重跑、fix round 3 在 ``b6ebaa3`` 上又重跑了 A 与 B，四个计数**逐字复现**::

       场景    runs  strat  snapshot  computed_on 跑法（「预跑」= 先单跑 2025-09-15）
       ------------------------------------------ -----------------------------------
       A        112  56000        96            3 不预跑，按序回放 sem=2（= Step 6 的干净跑法）
       B        112  56000        96            3 预跑 sem=1，再把 09-01..12-21 **完整**回放（同 sem=1）
       C        113  56500       128            4 预跑 sem=1，再在 sem=2 下回放
       D        112  56000       128            4 预跑 sem=1，回放时**跳过** 09-15（= 预检探针的跑法）

       computed_on：A/B = {09-01, 10-20, 12-15}；C/D 多一个 09-15。
       96 = 3 次物化 × 32，128 = 4 × 32，32 = sex 2 × age_group 2 × metric 8。

   **这段必须写成表、不能写成散文**：Ruling 192 那次错误正是把「预跑 + 跳过」这个具体条件
   归纳成「乱序」这个更宽的条件，而**场景 B 同样乱序**（先跑 09-15 再跑 09-01）却仍是 96 行
   ——它当场推翻「乱序」。散文容易被归纳成一个更宽的错条件；表格把每一格的条件与结果并排
   钉住，归纳不进来。

   机制（行号是 commit ``13207b2`` 的 shell 口径，硬规矩 #37）：

   * 幂等键 ``(semester_id, business_date)``——``daily.py:519-522`` 的 ``repo.upsert(session,
     models.DailySyncRun, ("semester_id", "business_date"), ...)``。「以同一幂等键再跑一次」
     因此 upsert 到**同一行**（实测预跑与回放后 ``daily_sync_run.id`` 都是 1）。
   * 回放开头按 ``batch_id`` 删三张派生表——``daily.py:552-553`` 的 ``with
     session.begin_nested(): _replay_cleanup(session, batch_id)``，其正文 ``daily.py:249-254``
     对 ``(DerivedMetrics, StratificationResult, PercentileSnapshot)`` 逐个
     ``repo.delete_by_batch(session, model, batch_id)``。**预跑那 32 行快照就是在这里被删的**
     （B 实测：预跑后 snapshot 32 行，完整回放后 96 行且 computed_on 里没有 09-15）。
   * 水位线取**严格更早**、且**不按 ``semester_id`` 过滤**——``extract.py:89`` 的
     ``models.DailySyncRun.business_date < business_date``（``previous_watermark`` 全文
     ``extract.py:75-94``，不过滤学期那条理由写在 ``extract.py:81``）。回放到 09-15 时水位线
     是 09-14，抽 0 条。
   * 按需物化的判据读本批抽取计数——``percentile_stage.py:342`` 的 ``return bool(row[0] or
     row[1])``（``needs_recompute``，判据说明在 ``percentile_stage.py:301-306``），那两列由
     ``daily.py:568-571`` 在百分位阶段之前写上并 flush。

   **B 与 D 的分水岭实测在那两列上**：预跑刚结束时 09-15 那行是 ``extracted_fitness=2016 /
   extracted_body_comp=2026``（首批水位线为 ``None`` → 全量抽取）；完整回放（B）之后**同一行**
   变成 ``0 / 0`` → ``needs_recompute`` 为假、不再物化，而 ``_replay_cleanup`` 已把预跑那 32 行
   删掉 → 96。跳过 09-15（D）之后那行仍是 ``2016 / 2026``，``_replay_cleanup`` 从未以该
   ``batch_id`` 被调用 → 32 行留在库里 → 128。两个场景的 ``previous_watermark(2025-09-15)``
   **都是** ``2025-09-14``，故水位线本身不是分水岭，「有没有以同一幂等键再跑过」才是。
   （旧版这段把 128 行归给「09-15 挂在**上学年** ``semester_id`` 下」，那是**场景 C** 的机制；
   C 连带产出 113 runs / 56500 strat，与预检探针的 112 / 56000 矛盾，故 C 不可能是它的成因。）

   尺寸一律写**字节数 + 两个单位**（硬规矩 #36：MB 是 10⁶ 还是 2²⁰ 必须写明）。测量条件：
   ``session.commit()`` + ``engine.dispose()`` 之后量**单个** ``.db`` 文件，目录内无 ``-wal`` /
   ``-journal`` 兄弟文件（已列目录确认）::

       场景      .db 字节数   MB (=B/10^6)  MiB (=B/1024^2) 复现
       ---------------------------------------------------- ----
       A         88,883,200          88.88            84.77 无预跑的干净跑法 5/5 次全同
       B         88,899,584          88.90            84.78 带预跑的完整回放 3/3 次全同
       C         89,927,680          89.93            85.76 1/1
       D         89,145,344          89.15            85.02 1/1，= Ruling 178 记的「89.1 MB」

   上一轮报的「84.8 MB」其实是 **MiB**（84.77），与 A 的 88.88 MB 只差 **0.02%**，不是 5% 的
   「sqlite 页分配波动」（Ruling 191）。B 比 A 多的 **16,384 B = 4 页 × 4096 B**：实测
   ``PRAGMA page_size=4096``、``page_count`` A=21700 / B=21704、两者 ``freelist_count``
   **都是 0**——多出的 4 页是**在用页**，不是「删掉的行挂在 freelist 上没还给文件系统」
   （fix round 2 的实测把后一种解释推翻了）。至于删了又插为什么让 B-tree 多用 4 页：**推测
   （页内空间重排），未验证**。

   计划 ``0.8`` 此前把 ``88,899,584 B`` 标为「第二次独立干净跑」并据此写「两次干净跑相差
   0.02 MB，即可复现」——那个框定站不住（Ruling 198 = 控制者第 52 次错误），fix round 3 已
   把计划改写成 A/B 的**状态差**。本轮（fix round 3）在 commit ``b6ebaa3`` 上复跑取证：
   **A 6/6 次全是 ``88,883,200 B``**（5 次 sem=2 + 1 次 sem=1 对照，故与 ``semester_id``
   无关）、**B 3/3 次全是 ``88,899,584 B``**，每次量之前都列了目录、只有一个 ``.db`` 文件。
   即**同一场景内跑次差是 0 B（逐字节相同），跨场景那 4 页是状态差**。**不被守卫**：这些
   字节数没有任何测试断言（回放测试只数行数与状态）。

CLI：``python -m app.pipeline.backfill --semester 2025-2026-1 [--start --end --db]``。
"""
import argparse
import datetime as dt
import time
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import DataSourceAdapter
from app.db import models
from app.pipeline.daily import require_dates_in_semester, run_daily, semester_by_name
from app.pipeline.extract import parse_business_date

__all__ = ["business_dates", "run_backfill", "main"]


def business_dates(start: str, end: str) -> list[str]:
    """闭区间 ``[start, end]`` 展开成升序的 ISO 日期序列。

    ``2025-09-01`` 至 ``2025-12-21`` 恰为 **112** 天 = 16 周 × 7 天（Ruling 174）。
    **闭区间是计划 Interfaces 的字面**，故 ``+ 1`` 是承重的：写成半开区间会让整学期少跑
    最后一天（``tests/pipeline/test_backfill.py`` 的 ``== 112`` 当场红）。

    日期解析一律走 :func:`~app.pipeline.extract.parse_business_date`（日期形状的唯一所有者，
    Ruling 38）：``2025-9-5`` 这类非零填充串在这里就响亮失败，而不是在幂等键
    ``(semester_id, business_date)`` 上悄悄生成第二个键。

    ``end < start`` 是调用方把排他的 ``end_date`` 直接当闭区间上界传进来的典型症状之一
    （另一个是多跑一天），故也在此拒绝而不是返回空列表——空列表会让 CLI 打印
    「共 0 天」并以 0 退出，看起来像成功。
    """
    first = parse_business_date(start)
    last = parse_business_date(end)
    if last < first:
        raise ValueError(
            f"结束业务日期 {end} 早于起始 {start}：区间为空。注意 Semester.end_date 是"
            f"**排他**的（Ruling 174），闭区间上界要用 end_date - 1 天"
        )
    return [
        (first + dt.timedelta(days=offset)).isoformat()
        for offset in range((last - first).days + 1)
    ]


def _traced_failure(session: Session, semester_id: int, day: str) -> models.DailySyncRun | None:
    """取回失败日那条 ``status = "failed"`` 的运行记录；查无则返回 ``None``。

    ``run_daily`` 的失败路径已经把它写进库并**提交**了（独立小事务，见
    :func:`app.pipeline.daily._record_failure`），故这里只是回查同一行。按幂等键
    ``(semester_id, business_date)`` 查——与 ``run_daily`` 里 ``repo.upsert`` 用的键
    逐字相同，故不可能查到别的学期的同一天。
    """
    return session.scalar(
        select(models.DailySyncRun).where(
            models.DailySyncRun.semester_id == semester_id,
            models.DailySyncRun.business_date == parse_business_date(day),
        )
    )


def run_backfill(
    session: Session,
    semester_id: int,
    start: str,
    end: str,
    adapter: DataSourceAdapter,
) -> list[models.DailySyncRun]:
    """逐日回放 ``[start, end]``，返回**每个业务日期一条** :class:`~app.db.models.DailySyncRun`。

    ``semester_id`` 的语义与 :func:`~app.pipeline.daily.run_daily` 完全一致：它是**运行记录
    与快照的归属**（幂等键的一半），不是数据的归属。回填历史时两者本来就不相等。

    返回列表按业务日期升序、长度恒等于 ``len(business_dates(start, end))``：失败日也在里面
    （``status == "failed"``），故调用方可以直接 ``Counter(r.status for r in runs)`` 汇总，
    不必再回库里数一遍。**唯一会让长度变短的情形**是「失败日的留痕也没写进去」，那时本函数
    原样重抛真因（见模块 docstring 第 2 条），不会有静默的短列表。

    ⚠️ 返回的实例在会话关闭后 **detached**（``run_daily`` 末尾的 ``commit`` 还会把已加载的
    属性全部 expire），故一切字段读取都必须在传入的那个 ``Session`` 仍然打开时完成。
    """
    runs: list[models.DailySyncRun] = []
    for day in business_dates(start, end):
        try:
            runs.append(run_daily(session, semester_id, day, adapter))
        except Exception:
            traced = _traced_failure(session, semester_id, day)
            if traced is None:
                # 原样重抛真因，不用一个新异常盖掉它（同 _record_failure 的纪律）。
                raise
            runs.append(traced)
    return runs


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：``python -m app.pipeline.backfill --semester 2025-2026-1``。

    ``--start`` / ``--end`` 缺省从 ``Semester`` 记录取起止日，而 **``--end`` 必须减一天**
    （Ruling 174：``end_date`` 排他，``semester_end_date`` = 开学日 + 教学周数）。不减就是
    113 天，而第 113 天（``2025-12-22``）在本数据集里没有任何新采集记录，它只会多写 500 行
    派生结果、多一条运行记录，看起来完全正常。

    ``--db`` 缺省取 :data:`app.config.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
    写的是**同一个所有者**：这是计划字面（``sqlite:///pe.db``）的一处有意偏离，理由是先跑
    生成器、再跑回填是 Step 6 的既定顺序，而相对路径的 ``sqlite:///pe.db`` 取决于 CWD——
    两个所有者会在有人从仓库根而不是 ``backend/`` 运行时静默指向两个不同的文件。
    （Plan 02 Task 1 之前这个常量住在 ``app.seed.generate``，本函数为此必须 import 生成器；
    现在它住在 :mod:`app.config` 这个叶子里，``pipeline → seed`` 那条边因此消失。）

    退出码：**有任一天 ``status == "failed"``（批没跑完）→ 1**，否则 0。per-day 的
    ``"partial"`` 是「跑完了但有记录因学号解析不到而整条跳过」（已在 ``cleaning_log`` 逐条
    留痕），它体现在控制台的整体汇总里、不改退出码——否则一个建档缺失的学号会让每天的
    定时任务都报失败，而重跑修不好它。
    """
    # 函数内导入：适配器工厂与缺省 DB URL 只属于 CLI 这条启动路径，
    # 放进模块顶层会让 ``import app.pipeline.backfill`` 也依赖它们。
    from app.adapters.factory import build_adapter
    from app.config import DEFAULT_DB_URL
    from app.db.session import engine

    parser = argparse.ArgumentParser(
        prog="python -m app.pipeline.backfill",
        description="按业务日期逐日回放整个学期（Extract → Clean → Percentile → Derive → Stratify）",
    )
    parser.add_argument(
        "--semester", required=True,
        help="学期名（semester.name，如 2025-2026-1）；它是幂等键的一半，故按名字查",
    )
    parser.add_argument("--start", default=None, help="起始业务日期 ISO（缺省 = 学期 start_date）")
    parser.add_argument(
        "--end", default=None,
        help="结束业务日期 ISO，**闭区间**（缺省 = 学期 end_date 减一天，end_date 是排他的）",
    )
    parser.add_argument("--db", default=DEFAULT_DB_URL, help=f"数据库 URL（缺省 {DEFAULT_DB_URL}）")
    args = parser.parse_args(argv)

    eng = engine(args.db)
    with Session(eng) as session:
        semester = semester_by_name(session, args.semester)
        start = args.start if args.start is not None else semester.start_date.isoformat()
        # Ruling 174：end_date 排他 → 闭区间上界减一天，否则 16 周会跑出 113 天
        end = (
            args.end if args.end is not None
            else (semester.end_date - dt.timedelta(days=1)).isoformat()
        )
        # Ruling 212 ③：两个端点都必须落在 --semester 的 [start_date, end_date) 内。
        # 缺省值天然满足（start_date 本身、end_date − 1 天），故本闸只挡显式传参的误操作：
        # 跨学期回填会让同一业务日期在两个 semester_id 下各留一套「当前」派生结果，
        # 而 _replay_cleanup 按 batch_id 删不到对方（见 require_dates_in_semester）。
        require_dates_in_semester(semester, "--start", start)
        require_dates_in_semester(semester, "--end", end)
        days = business_dates(start, end)
        adapter = build_adapter()
        started = time.perf_counter()
        runs = run_backfill(session, semester.id, start, end, adapter)
        elapsed = time.perf_counter() - started

        # ⚠️ 以下一切字段读取都必须在这个 with 块内完成（run_daily 的 commit 已 expire 它们）
        statuses = Counter(run.status for run in runs)
        failed = statuses.get("failed", 0)
        overall = (
            "success" if set(statuses) == {"success"}
            else "failed" if set(statuses) == {"failed"}
            else "partial"
        )
        print(
            f"学期 {semester.name}（id={semester.id}）"
            f"区间 {start}..{end} 共 {len(days)} 天（闭区间）"
        )
        print(
            "状态汇总：" + "、".join(f"{key} {value}" for key, value in sorted(statuses.items()))
            + f" → 整体 {overall}"
        )
        counted = [run for run in runs if run.status != "failed"]
        if counted:
            last = counted[-1]
            total = (
                last.red_count + last.yellow_count + last.green_count + last.insufficient_count
            )

            def share(count: int) -> str:
                return "n/a" if not total else f"{count / total * 100:.1f}%"

            print(
                f"末日 {last.business_date.isoformat()} 分层分布（{total} 人）："
                f"红 {last.red_count}（{share(last.red_count)}）、"
                f"黄 {last.yellow_count}（{share(last.yellow_count)}）、"
                f"绿 {last.green_count}（{share(last.green_count)}）、"
                f"数据不足 {last.insufficient_count}（{share(last.insufficient_count)}）"
            )
        print(f"耗时 {elapsed:.1f} s（{len(days)} 天）")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
