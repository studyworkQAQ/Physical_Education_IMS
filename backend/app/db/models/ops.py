"""spec §4.6 预警与运维：每日批处理运行记录、清洗审计。

Plan 01 只落这两张表；``alert`` / ``notification`` 属计划 03。
Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。
"""

import datetime as dt

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import JsonText, _in_domain


# ---------------------------------------------------------------------------
# spec §4.6 预警与运维（本计划只落运维两张表，alert / notification 属计划 03）
# ---------------------------------------------------------------------------


class DailySyncRun(Base):
    """一次每日批处理的运行记录，同时是全管道幂等键的载体。

    ``(semester_id, business_date)`` 唯一：同一天重跑必须落到同一行。管道据此先按
    ``batch_id`` 删掉派生行再重写，重放才是幂等的；否则同一学生同一天会累积出多条
    分层结果，红黄绿分布随之失真。

    计数列一律 ``default=0`` 而非可空：运行记录常在跑完之前就已入库（拿 ``id`` 当
    ``batch_id`` 用），此时计数是「还没数」而不是「未知」，0 比 NULL 更诚实，也让
    下游求和时不必处处防 None。
    """

    __tablename__ = "daily_sync_run"

    STATUSES: set[str] = {"success", "partial", "failed"}

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    business_date: Mapped[dt.date] = mapped_column(Date)  # 与 semester_id 组成唯一约束
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    # 各源抽取条数
    extracted_fitness: Mapped[int] = mapped_column(Integer, default=0)
    extracted_body_comp: Mapped[int] = mapped_column(Integer, default=0)
    extracted_survey: Mapped[int] = mapped_column(Integer, default=0)
    # 清洗计数
    dropped_count: Mapped[int] = mapped_column(Integer, default=0)  # 剔除数
    corrected_count: Mapped[int] = mapped_column(Integer, default=0)  # 修正数
    # 分层分布计数。spec §4.6 只写「红黄绿」，这里补 insufficient_count：
    # 标签域是四个值，少一列就会让「本日没分层的人」在运维记录里凭空消失。
    red_count: Mapped[int] = mapped_column(Integer, default=0)
    yellow_count: Mapped[int] = mapped_column(Integer, default=0)
    green_count: Mapped[int] = mapped_column(Integer, default=0)
    insufficient_count: Mapped[int] = mapped_column(Integer, default=0)
    # 缺肌肉量 P20 判定线的 (性别 × 年级组) 组数（Plan 02 Task 1，终审 C 组第 24 项）。
    # 生产者是 ``app.pipeline.run_stratify.muscle_line_gaps``，由
    # ``daily._stratify_and_persist`` 返回、``run_daily`` 写进本列。
    #
    # **它取代了此前写进 ``error_summary`` 的那段自由文本**（「注意（非错误）：N 个组没有
    # 肌肉量 P20 判定线……」）。那段文本有两个毛病：① 列名与内容不符——它明写「非错误」
    # 却住在 ``error_summary`` 里，于是一个只看列名的人会以为今天出了错；② 它是**文本**，
    # 教师大屏要按组数排序或求和就得先把中文句子解析回一个整数。改成计数列之后两个毛病
    # 一起消失，而 ``daily_sync_run`` 的其余计数列（``dropped_count`` / ``red_count`` …）
    # 本来就是这个形状。
    #
    # **直接切、不与 ``error_summary`` 双写**（Plan02 Ruling 13；计划 Step 4 第 4 项留了
    # 「保留一个 Task 周期两处同时写」的选项）。切之前自己复验过零消费者::
    #
    #     git grep -n "error_summary" -- backend/
    #     git grep -n "注意（非错误）" -- backend/
    #
    # 基线 ``e26347f`` 上，「注意（非错误）」这段文本的写入点只有 ``daily.py:652-659``
    # 一处，**读取点为零**：``daily.py:728-730`` 的 CLI 读的是 ``run.error_summary``
    # 这个列（不区分内容），两条测试（``test_backfill.py:336`` 断言 ``"boom on 2025-09-04"``、
    # ``test_daily.py:435`` 断言 ``"唯一约束"``）读的都是**真错误**那段，没有任何一处
    # 断言过缺线提示。双写等于造出第二个所有者，而单一所有者是本计划 Global Constraints
    # 的第一条。
    #
    # **「为什么会有缺线组」这段解释没有丢**，只是不再逐日复制一份进库里：机制写在
    # ``app.domain.percentile.compute_snapshot`` 的 docstring（Ruling 121 第 4 步：该组
    # InBody 样本 < ``MIN_SAMPLE = 30`` 时整组不产出快照行，而肌肉量**没有国标常模可降级**，
    # 故这些组的 ``C`` 只由体脂率决定），逐人的痕迹仍在
    # ``stratification_result.input_snapshot["snapshot_muscle_p20"] = null`` 里。
    muscle_line_gaps: Mapped[int] = mapped_column(Integer, default=0)
    # 下面两列由计划 02（处方）与计划 03（预警）写入；spec §4.6 已把它们列在本表，
    # 故此处只留计数列，不提前建 prescription / alert 表。
    # ⚠️ **Plan 01 就已经建好了这两列**（``models.py:614-615``），Plan 02 计划原文写的
    # 「spec §4.6 明确列了……Plan 01 没建」与基线不符，故 Task 1 没有新增它们，只把
    # ``alert_count`` 的现状写清楚：**本计划只建列不写值**，写入方是 Plan 03 的 Alert 阶段
    # （spec §5 第 8 阶段）；在那之前它恒为 0，读它的人不得把 0 当成「今天没有预警」。
    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数

    # status 同样有默认值（Ruling 30），理由与计数列一致：本列 NOT NULL，而运行记录
    # 常在跑完之前就已入库（要先拿到 id 当 batch_id 用），此时它还没有真实结局。
    # 默认取 "failed" 而不是 "success"，是保守方向：进程崩在中途时，这一行留下的
    # 就是 "failed"——崩溃被记成失败只是难看，被记成成功则是谎报一次并没有发生的
    # 完整运行，而下游看 status 决定是否要重跑，谎报成功会让这一天永远不再重跑。
    status: Mapped[str] = mapped_column(String(8), default="failed")
    # **自 Plan 02 起本列只承载真错误**（``status == "failed"`` 那次运行的
    # ``f"{type(exc).__name__}: {exc}"``）。此前它还兼着写「注意（非错误）：N 个组没有
    # 肌肉量 P20 判定线……」这段自由文本——列名与内容不符，且它是个要被人再解析回整数的
    # 数字。缺线组数改由上面的 :attr:`DailySyncRun.muscle_line_gaps` 计数列承载，
    # 理由、零消费者的复验命令与「为什么不双写」都写在那一列的注释里（Plan02 Ruling 13）。
    error_summary: Mapped[str | None] = mapped_column(Text)  # 错误摘要

    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "business_date",
            name="uq_daily_sync_run_semester_business_date",
        ),
        _in_domain("status", STATUSES, "ck_daily_sync_run_status"),
    )


class CleaningLog(Base):
    """每一条被剔除或被修正的数据的交代（spec §4.6）。

    不是过度设计：一个要发论文、要结题、要向省内高校推广的研究项目，必须能回答
    「这条数据为什么没了」。``kind`` 与 Task 5 的 ``CleaningEntry.kind`` 同域。

    原值与处理后值用 :class:`JsonText` 而不是裸 ``Text``：清洗条目的值是 ``object``
    （数值、字符串或 ``None``），JSON 编码能原样保住类型与 ``None`` 的语义。若直接
    ``str(value)`` 落成文本，``str(None)`` 会把「缺失」写成字符串 ``"None"``——那是
    审计记录里最难被发现的一类谎报。这两列也是 :class:`JsonText` 存在的直接理由：
    SQLAlchemy 自带的 ``JSON`` 类型在 SQLite 上会把 ``0.0`` 这类标量按 NUMERIC 亲和性
    改写成原生数值（实测读回 ``int 0``），审计记录里的「原值」因此不再等于原值。

    学号用双列承载（Ruling 25）：``student_no`` 非空、逐字节照抄收到的原始学号，
    ``student_id`` 可空、只在学号能解析到 ``student`` 表时才填。**学号解析不出来的
    那条记录，本身就是最该留痕的数据质量问题**：若把 ``student_id`` 做成非空外键，
    孤儿学号的审计记录会被约束直接挡在库外，最该被看见的那一类问题反而被静默吞掉，
    而 spec §4.6「必须能交代每一条被剔除或修正的数据」恰恰在这一类上失守。Task 5 的
    ``CleaningEntry.student_no`` 是 ``str``，双列也让清洗结果不必先解析成功才落库。
    """

    __tablename__ = "cleaning_log"

    KINDS: set[str] = {
        "missing_dropped",
        "outlier_corrected",
        "unit_normalized",
        "duplicate_removed",
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"))
    student_no: Mapped[str] = mapped_column(String(32))  # 原始学号，不做 strip / 补零
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))  # 解析得到才填
    field: Mapped[str] = mapped_column(String(32))  # 出问题的字段名
    # 值域是标量或 None；标注取最常见形态，实际由 JsonText 承载，不做运行期检查
    original_value: Mapped[float | str | None] = mapped_column(JsonText)
    processed_value: Mapped[float | str | None] = mapped_column(JsonText)
    kind: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)

    __table_args__ = (_in_domain("kind", KINDS, "ck_cleaning_log_kind"),)
