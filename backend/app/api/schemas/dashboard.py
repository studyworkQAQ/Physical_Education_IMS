"""教师大屏（spec §9.1）、学生端首页（§9.2）与教师端读单个学生训练单的**响应契约**。

⚠️ **本模块的模型不是「一张表的三件套」**，故它不出现在
:data:`app.api.routers.catalog.RESOURCES` 里、也不进 :mod:`app.api.schemas` 那个
「14 + 9 × 3 = 41」的算式（那条算式数的是 23 个 CRUD 资源；守卫
``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned`` 数的是
``RESOURCES``、不是本包的类）。口径逐字同 :mod:`app.api.schemas.alerts` 的
``AlertHandleCreate`` / ``AlertHandleResult``（那两个也不是三件套的成员）。

--------------------------------------------------------------------------
⚠️⚠️ 这些模型的字段集**逐字等于** :mod:`app.domain.report` 的输出
--------------------------------------------------------------------------

**它们不是第二份口径，而是同一份口径的 HTTP 名字**：每一个嵌套模型的字段集都由一条
测试与 domain 的返回值对账
（``tests/api/test_dashboard.py`` 的
``test_the_response_models_match_the_domain_payloads_field_for_field``），
故「domain 少给了一个键」与「schema 多写了一个键」都会当场红。

⚠️ **为什么值得为它们写 13 个类**（用户 2026-09-28 的原话是「要确保后端和前端能够
对接的上」，Plan 03 Task 4 的 P4-A5 为同一件事给两个身份请求头补了 securityScheme）：
Plan 04 的前端要照着 ``/openapi.json`` 画大屏的四块与学生首页的五格，
而 ``response_model`` 缺席的话那五个端点在 OpenAPI 里只有一个裸的 ``{}``——
生成的 TS 客户端于是给不出任何字段名，前端只能靠读 Python 源码猜。

⚠️ **两个刻意不建模的格子**（如实记录，硬规矩 #39）：

* ``StratificationRead.input_snapshot`` 与 ``ClassDashboardRead.blocks`` 里那些
  **字典的值**（``by_layer`` / ``entered`` / ``alert_summary`` 的键是分层标签、
  预警级别与处置状态）一律标成 ``dict[str, …]`` 而不是逐键展开：那三套键集是
  :data:`app.domain.report.LAYERS` / ``LEVELS`` 与调用方注入的 ``statuses``，
  展开成 Pydantic 字段就是**第二个住址**（domain 加一个标签，这里不会跟着加，
  而 Pydantic 会**静默丢掉**多出来的那个键）。
* ``WeeklySheetRead`` **不在本模块**：教师端读单个学生的训练单复用
  :class:`app.api.schemas.prescription.WeeklySheetRead`（同一个契约、同一个所有者），
  故 ``GET /api/teacher/students/{id}/weekly-sheet`` 与
  ``GET /api/students/{id}/weekly-sheet`` 在 OpenAPI 里指向**同一个** schema。
"""
import datetime as dt

from pydantic import BaseModel, Field

# ⚠️ 复用处方侧那个读模型（**不另造一个摘要形状**）：教师端读单个学生的训练单与
#    学生端读自己的训练单是**同一份数据的同一个契约**，两个端点在 /openapi.json 里
#    因此指向同一个 schema。无环：schemas.prescription 不 import 本模块。
from app.api.schemas.prescription import WeeklySheetRead

__all__ = [
    "AbnormalEntryRead",
    "BadgeRead",
    "ClassBlocksRead",
    "ClassDashboardRead",
    "LayerDistributionRead",
    "LayerFlowRead",
    "LayerRateRead",
    "PendingRpeRead",
    "ProgressBoardRead",
    "ProgressEntryRead",
    "RpePointRead",
    "RpeSummaryRead",
    "ScreenThresholdsRead",
    "StratificationRead",
    "StudentHomeRead",
    "ThresholdLinesRead",
]


# ---------------------------------------------------------------------------
# ① 红黄绿分层饼图 + 周环比流动（spec §9.1 的第 ① 块 / §8.5 的第 1 项）
# ---------------------------------------------------------------------------


class LayerFlowRead(BaseModel):
    """**周环比流动**的四个名单 + 一个开关（:func:`app.domain.report.layer_flow`）。

    ⚠️ ``has_previous`` **是承重的**：四个名单全空有两档成因——「学期第一周，
    没有上一周可比」与「一周里一个人都没换层」，两者在形状上完全相同。
    前端要靠这一格把第一周渲染成「暂无环比数据」，而不是「本周无人流动」。

    ⚠️ 四个字典的**键集**是 :data:`app.domain.report.LAYERS`（四个分层标签），
    值是**按学生 id 升序**的名单。⚠️ 键集不在这里逐键展开，理由见模块 docstring。

    ``entered`` / ``left`` 只含**两周都有分层行**且换了层的人；
    ``appeared`` / ``disappeared`` 是「本周才出现」与「本周消失」，
    **刻意不与换层混成一档**（理由逐字见那个函数的 docstring）。
    """

    has_previous: bool
    entered: dict[str, list[int]]
    left: dict[str, list[int]]
    appeared: dict[str, list[int]]
    disappeared: dict[str, list[int]]


class LayerDistributionRead(BaseModel):
    """``weekly_class_report.layer_distribution`` 那一列的形状（spec §4.7 的
    「分层分布及环比流动」是**一格**，故两半在同一个模型里）。"""

    #: 四个标签**稠密**（计数为 0 的也在）：饼图要四条固定的扇区。
    by_layer: dict[str, int]
    #: 上一周的同一份分布；**上一周不存在时是 ``None``**（不是四个 0）。
    previous: "dict[str, int] | None"
    flow: LayerFlowRead


# ---------------------------------------------------------------------------
# ② 本周人均 RPE 曲线（spec §9.1 的第 ② 块 / §8.5 的第 2 项）
# ---------------------------------------------------------------------------


class RpePointRead(BaseModel):
    """曲线上**有数据**的那一个点。

    ⚠️ ``submissions`` **不是**可从 ``mean`` 推出的重复项：一个「3 个人交出来的 9.0」
    与「38 个人交出来的 9.0」对教师的含义完全不同（前者是一个噪声点），
    而前端手上只有均值。
    """

    day: str
    mean: float
    submissions: int


class RpeSummaryRead(BaseModel):
    """``weekly_class_report.rpe_summary`` 那一列的形状。

    ⚠️ ``curve`` 恒 **7 项**（学期周的那 7 天），**没交快评的那天是 ``None``**
    ——不是一个 ``mean = 0`` 的点：把空日画成 0，折线会在周三掉到 0 再弹回 7，
    而教师读到的是「周三全班疲劳度骤降」，那天只是没上课。
    ⚠️ ``previous_curve`` 是 ``None`` 与「七个 ``None``」是**两件事**：
    前者 = 上一周不存在（学期第一周），后者 = 上一周存在但一天都没交。
    前端靠它决定画不画 spec §9.1 要的那条「上周虚线」。
    ⚠️ ``mean`` / ``previous_mean`` **未 round**（它们是判据输入，见
    :func:`app.domain.report.week_mean_rpe` 的 docstring），``delta`` 与曲线上的
    ``mean`` 是 round 过的（纯显示）。前端负责格式化。
    """

    curve: list["RpePointRead | None"]
    previous_curve: "list[RpePointRead | None] | None"
    mean: "float | None"
    previous_mean: "float | None"
    delta: "float | None"


class ThresholdLinesRead(BaseModel):
    """spec §9.1 第 ② 块要画的那**两条阈值线**（7 / 9）。

    ⚠️ **两个值一律现读 ``data/alert_rules.yaml``**（经
    :func:`app.refdata_alerts.alert_rules`），本模块与 router 都**不写第二份字面量**：
    那份 YAML 是预警阈值的唯一所有者（spec §4.4 逐字「改阈值应走版本控制与评审」），
    抄一份进来会让专家改完 YAML 之后大屏上的线**静默留在旧值**。
    """

    #: ``YELLOW_CLASS_RPE_HIGH.params.mean_rpe_max``（今天 7.0）：**班级**人均 RPE 的线。
    class_mean_max: float
    #: ``RED_RPE_SUSTAINED.params.rpe_min``（今天 9）：**个人**连续 RPE 的线。
    sustained_min: float


class ScreenThresholdsRead(BaseModel):
    """spec §9.1 第 ④ 块「异常名单」的**两个大屏阈值**（3 天 / RPE > 8）。

    ⚠️⚠️ **它们与上面那两条预警阈值刻意不同**（spec §14 #11 的裁定：
    「预警 = 正式工单，大屏 = 宽松展示筛选器」），故两个模型分开、
    前端**不得**拿一个去画另一个。守卫是
    ``tests/domain/test_report.py::test_the_screen_thresholds_are_not_the_alert_thresholds``
    （把两组改成相等 → 当场红）。
    ⚠️ 值一律现读 :mod:`app.domain.report` 的常量，本模块不写第二份。
    """

    gap_days: int
    rpe_max: int


# ---------------------------------------------------------------------------
# ③ 二次小测进步榜（spec §9.1 的第 ③ 块 / §8.5 的第 4 项）
# ---------------------------------------------------------------------------


class ProgressEntryRead(BaseModel):
    """榜上的一行。``change_pct`` 带符号（正 = 进步），已 round 到
    :data:`app.domain.report.PCT_PRECISION` 位。"""

    student_id: int
    change_pct: float


class ProgressBoardRead(BaseModel):
    """``weekly_class_report.progress_board`` 那一列的形状。

    ⚠️ ``top`` **截断到 ``top_n``**（spec §8.5 逐字「Top10」），``regressed`` **不截断**
    （它是「要逐个找学生谈话」的工作清单）。
    ⚠️ ``top_n`` 不是常量的回声：周报是存下来再读回来的，若明年把 10 改成 20，
    一份旧的 ``top`` 只有 10 项就无从分辨「当时只截了 10 个」与「当时只有 10 个人进步」。
    ⚠️ ``unchanged``（变化恰为 0）与 ``unmeasured``（分数缺失 / 上次是 0 分）
    是两个不同的档，**都不在任何一个榜上**。
    """

    top_n: int
    top: list[ProgressEntryRead]
    regressed: list[ProgressEntryRead]
    unchanged: int
    unmeasured: int


# ---------------------------------------------------------------------------
# ④ 异常名单（spec §9.1 的第 ④ 块）—— ⚠️ **只有大屏有，周报不落库**
# ---------------------------------------------------------------------------


class AbnormalEntryRead(BaseModel):
    """异常名单上的一行。

    ⚠️ ``reasons`` 的**顺序固定**（先 ``checkin_gap`` 后 ``rpe_high``）：
    大屏是**滚动**展示的，顺序不稳会让同一个人两次滚过时看起来像两条不同的异常。
    ⚠️ ``peak_rpe`` 可空 = 「这个学生本周没交过快评」（**不是** 0——0 会被读成
    「一点都不累」）。而 ``gap_days`` 缺失时按 ``0`` 补（不知道就当没中断），
    两者的保守方向**相反**，理由逐字见 :func:`app.domain.report.abnormal_roster`。
    """

    student_id: int
    reasons: list[str]
    gap_days: int
    peak_rpe: "int | None"


# ---------------------------------------------------------------------------
# 按层分组的打卡完成率（spec §8.5 的第 3 项）与预警汇总（第 5 项）
# ---------------------------------------------------------------------------


class LayerRateRead(BaseModel):
    """一层的打卡完成率。

    ⚠️ ``rate`` 可空 = 「这一层一个可测的人都没有」（**不是** ``0.0``）：
    完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」，
    写成 0.0 等于在报表上断言「这一层一个人也没练」。
    ``students`` 与 ``measured`` 两格都在，故读的人能看出这一层的样本有多大。
    """

    students: int
    measured: int
    rate: "float | None"


# ---------------------------------------------------------------------------
# 教师大屏（spec §9.1 的四块 + 顶栏的元数据）
# ---------------------------------------------------------------------------


class ClassBlocksRead(BaseModel):
    """:func:`app.pipeline.report_stage.aggregates_of` 的**七个键**。

    ⚠️ **它同时服务大屏与周报**：周报落库取其中六个（``abnormal_roster`` 不落库——
    它是 §9.1 的一个实时筛选器，不是 spec §4.7 那 6 项里的一项，
    而 ``weekly_class_report`` 只有 5 个 JSON 列 + 1 个 Text 列、没有它的位置）。
    ⚠️ ``alert_summary`` 的值是 ``{级别: {状态: 条数}}``（3 × 3 = 9 格**双稠密**），
    键集不逐键展开的理由见模块 docstring。
    """

    layer_distribution: LayerDistributionRead
    rpe_summary: RpeSummaryRead
    #: ``{分层标签: LayerRateRead}``，四个键恒在。
    checkin_rate_by_layer: dict[str, LayerRateRead]
    progress_board: ProgressBoardRead
    #: ``{预警级别: {处置状态: 条数}}``。
    alert_summary: dict[str, dict[str, int]]
    #: **算法建议**（spec §8.5 第 6 项）：一句中文，三档之一。
    #: ⚠️ 那 10% 与 spec §8.4「减量 20%」刻意不同，理由逐字见
    #: :mod:`app.domain.report` 模块 docstring 的「三个两套并存」②。
    suggestion: str
    abnormal_roster: list[AbnormalEntryRead]


class ClassDashboardRead(BaseModel):
    """``GET /api/dashboard/class/{course_section_id}`` 的响应（spec §9.1 整屏）。

    顶栏那一行（「学期 / 教学周次 / 教学班切换 · 数据更新时间 · 预警角标」）由
    前四格 + ``blocks.alert_summary`` 里三档 ``pending`` 之和给出——
    ⚠️ **角标刻意不另给一个计数**：那会是「本周待处理预警数」的第二个所有者，
    而它与 ``alert_summary`` 里的三个数不可能一致地漂。
    """

    course_section_id: int
    semester_id: int
    #: 学期名（``semester.name``，如 ``2025-2026-1``）：顶栏要显示它，
    #: 而前端不该为了一个名字再去调一次 ``GET /api/semesters/{id}``。
    semester_name: str
    course_section_name: str
    week: int
    #: 业务日期（= 数据截至哪一天）。
    as_of: dt.date
    #: **水位线** = ``min(as_of, 那一周的周日)``：周报与大屏都读不到它之后的数据。
    watermark: dt.date
    week_start: dt.date
    #: 本班人数（= ``enrollment`` 的行数）。⚠️ **它不是**
    #: ``sum(blocks.layer_distribution.by_layer.values())``：一个从未被分层过的学生
    #: 在分布里缺席，而「本班 40 人」必须包含他。
    roster_size: int
    blocks: ClassBlocksRead
    rpe_threshold_lines: ThresholdLinesRead
    screen_thresholds: ScreenThresholdsRead


# ---------------------------------------------------------------------------
# 学生端首页（spec §9.2 的「今日」+「我的数据」里那几格）
# ---------------------------------------------------------------------------


class StratificationRead(BaseModel):
    """**当前分层 + 可解释性展开**（spec §9.2 逐字「分层标签可点击展开命中规则」，
    spec §14 #17 的裁定是「做」）。

    ⚠️ ``explanation`` 是 :func:`app.domain.stratify.explain` 的**全文**
    （例如「红色层 ← 你的 1000 米跑与引体向上在校内同龄男生中低于 P25，
    且体脂率 22.4% 超过男生 20% 阈值」），由 ``stratification_result.input_snapshot``
    **离线重建**出 :class:`~app.domain.derive.DerivedResult` 后现算——
    那一列存的正是「判定当时的全部输入」（spec §4.3 的可追溯性），故重建不需要
    回到当天的原始数据。守卫是
    ``tests/api/test_dashboard.py::test_the_explanation_is_the_same_prose_the_pipeline_would_render``
    （两侧不同源：一侧走 HTTP、一侧在测试里直接调 ``explain``）。

    ⚠️ ``label`` 与 ``hit_rules`` / ``reason`` 一律取**库里存的那一份**
    （不取重建后重算的那一份）：它们是当天判定的结果，而重算只能证明
    「快照足以复现」，不能取代它。
    """

    label: str
    hit_rules: list[str]
    reason: str
    explanation: str
    percentile_source: str
    computed_on: dt.date
    #: 判定当时的全部输入（28 个键，由
    #: ``tests/pipeline/test_prescription_stage.py`` 的一条测试逐字钉住）。
    #: ⚠️ 键集不建模，理由见模块 docstring。
    input_snapshot: dict


class PendingRpeRead(BaseModel):
    """一张**待办卡片**：一节已经发起了课堂快评、而这个学生还没交的课。

    ⚠️ ``rpe_token`` **刻意不在里面**：口令是给学生端**提交时**用的，
    而提交走 ``POST /api/rpe-records``（请求体里带它）。首页列表里带上口令
    等于把「哪节课的口令是什么」摊在一个 GET 上，而那个 GET 的作用域闸门
    只校验「请求者是不是这个学生」。学生从卡片点进去时再调
    ``GET /api/class-sessions/{id}`` 取。
    """

    class_session_id: int
    session_date: dt.date
    period: int


class BadgeRead(BaseModel):
    """**电子勋章**（spec §8.2：``GREEN_MASTERY`` → 「生成电子勋章记录」）。

    ⚠️ 原型里「勋章记录」就是 ``alert`` 表里那些 ``rule_id = GREEN_MASTERY`` 的行
    （spec §8.3 逐字「在原型中落地为站内消息」，故没有独立的勋章表）。
    ``count`` 是本学期至今的总数，``latest`` 是最近一次的触发时刻。
    """

    count: int
    latest: "dt.datetime | None"


class StudentHomeRead(BaseModel):
    """``GET /api/students/{student_id}/home`` 的响应（spec §9.2 的「今日」页）。

    ⚠️ **本周完成度那一格刻意不在这里**：它的唯一所有者是
    ``GET /api/students/{student_id}/training-logs/completion-rate``
    （那一个端点已经把「四个条件」「三档 ``None``」「处方周与学期周错开时逐天判定」
    全部写清了，并且与 :func:`app.pipeline.alert_stage._counted_checkin_days`
    由一条测试钉成逐字相等）。在首页再算一遍就是**第二个所有者**，
    而两处的分母窗口一旦漂开，环形进度条与被预警的完成率就会给出两个数。
    前端因此在首页上发两个请求——那是一次并行的 GET，不是一个口径风险。

    ⚠️ ``weekly_sheet`` 与 ``GET /api/students/{id}/weekly-sheet`` **同形**
    （复用 :class:`app.api.schemas.prescription.WeeklySheetRead`），故
    spec §9.2 说的「本周训练单**摘要**」是前端对它的渲染，
    本模块**不另造一个摘要形状**（那会是同一份数据的第二个契约）。
    没有生效处方 / ``as_of`` 落在微周期之外时它是 ``None``
    ——⚠️ 而不是一个 404：首页是**一屏**，一格缺数据不该让整屏失败。
    """

    student_id: int
    as_of: dt.date
    semester_id: "int | None"
    #: 学期周次；``as_of`` 早于开学日时为 ``None``（没有「本学期第几周」可言）。
    week: "int | None"
    #: 当前分层 + 可解释性；**从未被分层过**时为 ``None``。
    stratification: "StratificationRead | None"
    weekly_sheet: "WeeklySheetRead | None" = Field(
        default=None,
        description="本周训练单，形状逐字同 GET /api/students/{id}/weekly-sheet "
                    "（同一个 WeeklySheetRead）；无处方或那一天不在微周期里时为 null",
    )
    #: 待办卡片：已发起快评、而这个学生还没交的课，按 ``(日期, 节次)`` 升序。
    pending_rpe: list[PendingRpeRead]
    #: 未读消息红点（``notification.is_read == False`` 的行数）。
    unread_notifications: int
    badges: BadgeRead
