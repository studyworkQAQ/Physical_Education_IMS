"""spec §4.3 派生与分层（可追溯核心）：百分位快照、派生指标、分层结果。

Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。

``percentile_snapshot.sex`` 的取值域复用 :attr:`.organisation.Student.SEXES`（唯一所有者），
故本模块 import ``Student``；这是包内唯一的跨小节依赖。
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import JsonText, _in_domain
from .organisation import Student


# ---------------------------------------------------------------------------
# spec §4.3 派生与分层（可追溯核心）
# ---------------------------------------------------------------------------


class PercentileSnapshot(Base):
    """校内百分位快照。**物化而非实时计算**（spec §4.0）。

    实时算会随人群变动漂移，而研究项目必须能复现任意一天的分层结果。列与 Task 7 的
    ``PercentileRow`` 值对象一一对应，故 ``compute_snapshot`` 的输出可直接落库，
    样本量不足 30 时降级来的国标常模行（``source = "national"``）亦然。

    ``batch_id`` + 五列业务唯一键是它的幂等防线（Ruling 29）。此前本表是**唯一一张
    会被物化、却在库层没有任何幂等机制**的表：既无 ``batch_id``（``delete_by_batch``
    删不到它），也无唯一约束（重放翻倍不报错），只能靠 Task 10 的跨日复用逻辑加一条
    行数断言兜着——那是纪律，不是机制；纪律会被下一次重构悄悄改掉，约束不会。

    唯一键的五个列正是 Task 7 的分组键 ``(sex, age_group, item)`` 再加「哪个学期、
    哪一天」：``compute_snapshot`` 对每个分组最多产出一行（7 个计分项在样本 < 30 时
    整组降级为 ``source = "national"``，不是并存两行；``muscle_mass_kg`` **没有国标
    常模可降级**，样本 < 30 时整组不产出行），故 ``source`` 不必进键，同一组同一天
    也只可能有一行。
    """

    __tablename__ = "percentile_snapshot"

    SOURCES: set[str] = {"school", "national"}

    # 取值域与 ``app/domain/percentile.py`` 的 ``SnapshotMetric`` 一致：7 个国标计分项
    # 加上 ``muscle_mass_kg``（肌肉量）。肌肉量**不是计分项**，故它不在 ``ScoredItem``
    # 里；而 spec §6.3② 的 ``C`` 要用「同龄同性别肌肉量 P20」这条判定线，所以快照表
    # 必须存得下它。此前本列是该表**唯一没有取值域约束**的业务列，也正是「库里存得下、
    # 算不出来」这个缺陷形态的机制来源（Ruling 102/121）。与 ``Student.SEXES`` 同一条
    # 处置：db 层不为一个取值集合引入跨层依赖，代价是两处需人工同步，由
    # ``tests/db/test_models.py`` 的漂移测试钉住。
    ITEMS: set[str] = {
        "bmi",
        "vital_capacity",
        "sprint_50m",
        "sit_and_reach",
        "standing_jump",
        "pull_up_or_sit_up",
        "distance_run",
        "muscle_mass_kg",
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )
    item: Mapped[str] = mapped_column(String(32))  # 指标，取 SnapshotMetric 的值
    sex: Mapped[str] = mapped_column(String(8))
    age_group: Mapped[str] = mapped_column(String(16))  # 国标年级组
    p10: Mapped[float] = mapped_column(Float)
    p20: Mapped[float] = mapped_column(Float)
    p25: Mapped[float] = mapped_column(Float)  # 短板判定线：低于它即显性短板
    p50: Mapped[float] = mapped_column(Float)
    p75: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(8))

    __table_args__ = (
        _in_domain("source", SOURCES, "ck_percentile_snapshot_source"),
        _in_domain("sex", Student.SEXES, "ck_percentile_snapshot_sex"),
        _in_domain("item", ITEMS, "ck_percentile_snapshot_item"),
        UniqueConstraint(
            "semester_id",
            "computed_on",
            "item",
            "sex",
            "age_group",
            name="uq_percentile_snapshot_group_day",
        ),
    )


class DerivedMetrics(Base):
    """派生指标：分层判定的直接输入，也是「逐人可追溯」链条的中间一环。

    ``batch_id`` 指向 ``daily_sync_run``：幂等重放靠它按批删除本表与
    ``stratification_result`` 的旧行（见 :func:`app.db.repo.delete_by_batch`）。
    没有这一列，重跑同一天就只能靠「学生 + 日期」去猜哪些行属于哪一次运行。

    **``uq_derived_metrics_student_day``（Ruling 212）**：``(student_id, computed_on)``
    唯一。派生表的**自然键**是 ``(student_id, computed_on)``，而重放的**幂等键**是
    ``(semester_id, business_date)`` —— **两个键不同维度**，``_replay_cleanup`` 只按
    ``batch_id`` 删，跨学期删不到对方。于是「同一业务日期在两个 ``semester_id`` 下各跑一次」
    会留下两套「当前」结果，而所有自然读法（``ORDER BY computed_on DESC LIMIT 1``）
    都会**稳定取到陈旧那一套**（``computed_on`` 相同、无二级排序 → SQLite 按 rowid 升序扫
    → 预跑那批 id 更小）。终审实测（60 人，第二次跑的 ``standing_jump_cm`` 减 60）：
    ``stratification_result`` 120 行 / 60 学生 / **60 人各有两行同 ``computed_on``**、
    ``COUNT(DISTINCT input_snapshot) = 2``。教师大屏 ``WHERE computed_on=? GROUP BY label``
    会把 60 人的班报成 120 人。

    终审已亲验：干净回放下 ``(student_id, computed_on)`` 在 **56000 行**上已经唯一
    （``distinct = 56000``），故正常路径不会误伤，只有跨学期重跑才会响亮失败。
    另一道闸是 CLI 的「``--date`` 必须落在 ``--semester`` 区间内」守卫
    （:func:`app.pipeline.daily.require_dates_in_semester`）。

    ⚠️ **``init_db`` 用 ``Base.metadata.create_all``，它对已存在的表不会补约束/索引**：
    本约束只对**新建**的库生效。已有的 ``pe.db`` 必须重建（或手工
    ``CREATE UNIQUE INDEX``），否则跨学期重跑仍然静默双写。
    """

    __tablename__ = "derived_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )

    annual_change: Mapped[dict] = mapped_column(JsonText)  # 各指标年均变化率
    # 列宽 **20** 而不是 16（Ruling 144）：``Trend.INSUFFICIENT.value`` =
    # ``"insufficient_data"`` 是 **17** 字符，16 装不下。SQLite 不强制 ``VARCHAR`` 长度，
    # 故它静默存下——而 500 人首批实测就有 209 行（41.8%）写这个 17 字符的值；换任何严格
    # 长度的后端（MySQL / PostgreSQL）会截断成 ``"insufficient_dat"``，读回来
    # ``Trend(...)`` 当场 ``ValueError``，**炸在读侧不在写侧**，离真因隔一整个批处理周期。
    # 取 20 与 ``stratification_result.label`` 对齐：两列存的是同一族 17 字符的值。
    # 守卫见 ``tests/db/test_models.py`` 的列宽遍历测试（硬规矩 #18）。
    trend: Mapped[str] = mapped_column(String(20))  # 趋势标签（Task 8 的 Trend 值）
    weaknesses: Mapped[list] = mapped_column(JsonText)  # 短板列表，元素为 ScoredItem 的值
    weakness_count: Mapped[int] = mapped_column(Integer, default=0)  # W，分母恒为 6
    valid_count: Mapped[int] = mapped_column(Integer, default=0)  # < 4 则本日不分层
    body_comp_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)  # C
    body_comp_reasons: Mapped[list] = mapped_column(JsonText)  # C 的原因；正常时为 []

    __table_args__ = (
        UniqueConstraint(
            "student_id", "computed_on", name="uq_derived_metrics_student_day"
        ),
    )


class StratificationResult(Base):
    """红黄绿分层结果（含 ``insufficient_data``），逐人逐日一条。

    ``hit_rules`` 的语义必须读清楚：它是**本次求值评估过的规则 ID 序列**，逗号分隔
    （如 ``"R1,R2,Y1"``），**最后一项才是命中的那条**——**Z0 闸门 + 7 条分层规则**
    自上而下求值、命中即停，所以最多只可能命中一条。保留已评估但未命中的前缀不是
    冗余：它正是回答「这个学生为什么不是红色层」的证据（spec §4.3 要求的可追溯性），
    也是 ``explain()`` 生成中文文案的依据。

    **前缀的构成（Ruling 132）**：``Z0`` 命中时本列**恰为 ``"Z0"``**、只有这一项
    （闸门未评估任何分层规则）；``Z0`` 未命中时本列是**已评估的 7 条分层规则序列**、
    最后一项即命中者、**不含 ``Z0``**（``"R1,R2,Y1"`` 而不是 ``"Z0,R1,R2,Y1"``）。
    故最长取值是 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20 字符**（7 个两字符 ID + 6 个逗号；
    实测 500 人整批的最大长度就是 20——fix round 3 复跑：把 ``stratify_dataset`` 的 500 人
    产出按 ``,``.join 后量，``max = 20``、长度集合 ``{2, 5, 8, 11, 14, 17, 20}``，七档
    「已评估前缀」逐档都在，最长的那条正是 ``R1,R2,Y1,Y2,Y3,Y4,G1``。**这个 20 不被
    守卫**：``hit_rules`` 列没有取值域 CHECK，故 ``tests/db/test_models.py`` 的列宽遍历
    测试扫不到它；128 的余量靠的是 20 ≪ 128 这个量级差，不是断言），``String(128)`` 充裕。

    **``insufficient_data`` 时 ``hit_rules`` 恰为 ``"Z0"``，任何路径都至少有一项**
    （Ruling 125，**不是空串**）：``explain()`` 按 ``hit_rules[-1]`` 取文案，空串会让
    学生端点开「为什么我没有分层结果」时当场 ``IndexError``——而 ``Z0`` 恰恰是最需要
    向学生解释的那条路径。Task 9 已用变异实证过这一崩溃。

    ``input_snapshot`` 存判定当时的全部输入（W、C、valid_count、趋势、主导素质桶、
    各项得分与所用百分位等），使任一条结果都能离线复算，不必回到当天的原始数据。

    **``uq_stratification_result_student_day``（Ruling 212）**：``(student_id, computed_on)``
    唯一。理由、机制与实测证据见 :class:`DerivedMetrics` 的 docstring（两张派生表同一条
    缺陷、同一道约束）：本表的自然键与重放的幂等键 ``(semester_id, business_date)``
    **不同维度**，跨学期重跑同一业务日期会留下两套「当前」分层，而
    ``ORDER BY computed_on DESC LIMIT 1`` 稳定取到陈旧那一套。

    ⚠️ **``init_db`` 用 ``create_all``，对已存在的表不会补约束/索引**：本约束只对**新建**
    的库生效，已有的 ``pe.db`` 必须重建或手工 ``CREATE UNIQUE INDEX``。
    """

    __tablename__ = "stratification_result"

    LABELS: set[str] = {"red", "yellow", "green", "insufficient_data"}
    # ``"none"`` = 本条结果**没有用过任何判定线**（``valid_count = 0``，Z0 闸门直接拦下）。
    # 它不是第三种数据来源，而是「无来源」：若拿 ``"school"`` 去填，教师大屏会说「这个
    # 人的判定线来自校内百分位」，而他根本没有判定线——那是一条凭空造出的可追溯性。
    # ``String(8)`` 够宽（最长的 ``"national"`` 恰 8 字符）。
    PERCENTILE_SOURCES: set[str] = {"school", "national", "none"}

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    computed_on: Mapped[dt.date] = mapped_column(Date)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True
    )
    label: Mapped[str] = mapped_column(String(20))
    hit_rules: Mapped[str] = mapped_column(
        String(128),
        comment="逗号分隔的规则 ID 序列；最后一项为命中者，前缀是已评估但未命中的规则",
    )
    input_snapshot: Mapped[dict] = mapped_column(JsonText)
    # 本条结果**实际用过**的那些判定线行的来源汇总（Ruling 137）：一项都没用过 →
    # ``"none"``；用过 1–3 项（Z0 命中但确实用过判定线）与用过 6 项同一条规则——
    # 6 项混用 school / national 时**任一项降级即 ``"national"``**（保守侧：告诉教师
    # 「这个人的判定线里有人是兜底来的」比反过来安全）。生产者见
    # ``app.domain.percentile.summarize_source``。
    percentile_source: Mapped[str] = mapped_column(String(8))
    valid_from: Mapped[dt.date] = mapped_column(Date)  # 生效起
    valid_to: Mapped[dt.date | None] = mapped_column(Date)  # 生效止；仍生效时为 NULL

    __table_args__ = (
        _in_domain("label", LABELS, "ck_stratification_result_label"),
        _in_domain(
            "percentile_source",
            PERCENTILE_SOURCES,
            "ck_stratification_result_percentile_source",
        ),
        UniqueConstraint(
            "student_id", "computed_on", name="uq_stratification_result_student_day"
        ),
    )
