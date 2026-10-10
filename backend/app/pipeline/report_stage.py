"""班级周报阶段（spec §8.5 / §5 的第 9 阶段 ``Weekly``）+ 大屏取数（Plan 03 Task 8）。

它是 :mod:`app.pipeline.daily` 的**第八个**阶段
（``Extract → Clean → Percentile → Derive → Stratify → Prescribe → Alert → **Report** → Commit``），
跑在预警阶段**之后**、同一个 SAVEPOINT 之内——因为「算法建议」要读**当天刚生成的**
班级级预警（:func:`app.domain.report.suggestion` 的第一个入参）。

--------------------------------------------------------------------------
本模块**一条判据都不写**：它只有「取数」与「落库」
--------------------------------------------------------------------------

九个聚合量（分层分布、周环比流动、人均 RPE 曲线、按层完成率、进步榜、预警汇总、
算法建议、大屏异常名单、周级人均 RPE）全在 :mod:`app.domain.report`
（纯函数、100% 分支覆盖、24 条变异取证全 killed）。本模块的职责是三件事：

1. :func:`class_snapshot` —— **把一个教学班一周的库里的行读成一个
   :class:`ClassSnapshot`**（它是「怎么读一个班的一周」在全仓的**唯一**编排）；
2. :func:`aggregates_of` —— 把那个快照喂给 domain 的九个纯函数，
   得到**七个键**的聚合载荷（它是「怎么调那九个函数」的唯一编排）；
3. :func:`generate_weekly_reports` —— 把其中六个键落进
   ``weekly_class_report`` 的 5 个 ``JsonText`` 列 + 1 个 ``Text`` 列。

⚠️⚠️ **①②两步分开、且大屏与周报共用**，是本模块最要紧的一个决定（简报 P8-A2 的落地）。
失效形态很具体：教师大屏是**实时**刷新的，而周报是**周日生成后存下来**的；
若两条路径各自读一遍库、各自调一遍 domain，那么「大屏上的人均 RPE」与
「同一周周报里的人均 RPE」就有了两个取数编排，而它们**必然**某天对不上
（一个夹了水位线、另一个没夹；一个按名册过滤、另一个按课次过滤）。
教师看到大屏写 6.9、周报写 7.1，会认为系统算错了——而他无从判断哪一个是真的。
故 :mod:`app.api.routers.dashboard` 也走 :func:`class_snapshot` + :func:`aggregates_of`，
**不自己写一遍 SQL**。

--------------------------------------------------------------------------
⚠️⚠️ 「每周日」这个判据住在**调用点**、不住在生成器里
--------------------------------------------------------------------------

spec §8.5 逐字「**每周日**批处理生成」。本模块把它拆成两半：

* :func:`generate_weekly_reports` **无条件**为 ``(semester_id, week)`` 生成一遍——
  它是纯的「给一个周次、出一份周报」，不判今天星期几；
* :func:`is_report_day` 持有那个判据，由 :mod:`app.pipeline.daily` 在调用点上用。

**为什么不在生成器里判**（简报 Task 8「决定」第 3 条）：把判据放进生成器的话，
「重放一个历史日期」与「那一天是不是周日」就绑死了，而重放的正确定义是
「同一批输入得到同一批输出」；一个手工补生成上周周报的入口
（Plan 04 的教师端很可能要）会被生成器自己挡掉，而调用方看不出为什么。

⚠️ **``dt.date.weekday() == 6`` 是周日**（Python 的 ``Monday == 0``），而
``isoweekday() == 6`` 是**周六**、``weekday() == 7`` **永不成立**
（于是周报永远不生成、而全链路不报错）。这个 off-by-one 是本 Task 最容易错的一格，
故 :data:`REPORT_WEEKDAY` 是一个**有名字的常量**，且
``tests/pipeline/test_report_stage.py`` 用**三个真实的日期字面**钉住它
（2025-09-13 周六不生成 / 2025-09-14 周日生成 / 2025-09-15 周一不生成）。

--------------------------------------------------------------------------
异常分层：按教学班捕获 + 按人捕获，只有基础设施异常才冒泡
--------------------------------------------------------------------------

照 :mod:`app.pipeline.alert_stage` 的既有分层：

* **按班**：一个班的组装/聚合失败（``ValueError`` / ``KeyError`` / ``TypeError`` 一类
  「这一个班的输入有问题」）计入 :attr:`ReportSummary.errors` + 一条 ``warning``，
  然后 ``continue``；
* **按人**：装配一个学生的处方训练包
  （:func:`~app.pipeline.prescription_stage.training_days_of`）可能失败
  （训练包 JSON 坏、覆盖记录里的动作已从 ``exercises.yaml`` 删掉），而那**不该**让
  整份班级周报消失——那个学生只是 ``rate = None``（判不了），其余 39 个人照算。
  这一档计入 :attr:`ClassCache.errors`，**同一个学生只失败一次**（结果被记忆化）。

DB 读写一律在 ``try`` **之外**，故 ``IntegrityError`` / ``OperationalError`` 直接抛给
:func:`app.pipeline.daily.run_daily`，由它回滚整批并写一条 ``status = "failed"`` 的运行记录。

--------------------------------------------------------------------------
⚠️ 三个窗口口径：它们回答的是**三个不同的问题**（硬规矩 #113）
--------------------------------------------------------------------------

======================  ==================================  ==============================
量                       窗口                                 它回答的问题
======================  ==================================  ==============================
分层标签（本周）         ``computed_on <= watermark``          这一周结束时每人在哪一层
分层标签（上周）         ``computed_on <= 上周末``              周环比流动的基准
人均 RPE 曲线            学期第 N 周的**全 7 天**               曲线的横轴（水位线之后是 ``None``）
打卡 / 小测 / 预警       ``[week_start, watermark]``           本周发生了什么
处方的训练日             **处方周** ∩ 学期第 N 周 ∩ ``<= 水位线``  本周该练哪几天
======================  ==================================  ==============================

⚠️ ``watermark = min(as_of, week_end)``：周报**读不到未来**。
:func:`generate_weekly_reports` 与 :func:`class_snapshot` 都是公开的，故可以在周中被调用
（Plan 04 的教师端很可能要一个「立刻重生成上周周报」的按钮）；不夹水位线的话，
周三生成第 N 周的周报会把周四到周日的数据也算进去，而那一天在 ``as_of`` 时还不存在
——那是一次静默的读未来。
⚠️ **而 RPE 曲线的横轴刻意不夹**：它恒是那 7 天，水位线之后的几天是 ``None``
（:func:`app.domain.report.daily_mean_rpe` 的口径）。少给几天的话横轴会自己缩短，
而教师看不出「周四是空的」与「周四不存在」的区别。

⚠️ **完成率的分母与 :func:`app.pipeline.alert_stage._student_signals` 刻意不同**：
那一处的分母是**整个处方周**的训练日（``GREEN_MASTERY`` 问的是「这个学生在他的
处方周里练满了没有」），本模块的分母是**处方训练日 ∩ 学期第 N 周**
（周报问的是「这个班**本周**按层分组的完成率」）。两个问题不同，故两个窗口不同——
共用一个窗口的话，一个处方周跨两个学期周的学生会在两份周报里各被算一次完整的分母，
两周的完成率于是都偏低，而全链路不报错。
⚠️ 而**分子的四个条件**（``completed`` ∧ ``not late`` ∧ ``not is_rest_day`` ∧
``submitted_at.date() == log_date``）是**同一个所有者**：直接 import
:func:`app.pipeline.alert_stage._counted_checkin_days`，不写第二份
（那一处已经有一条测试把它与 ``GET …/completion-rate`` 端点钉成逐字相等）。
⚠️ **「连续未打卡天数」用的是另一个分子**：
:func:`app.pipeline.alert_stage._reported_checkin_days`（「有没有报过」），
不是 ``_counted``。一个 22:40 才交卡的学生并没有失联，把他算进「连续未打卡」
会让大屏上出现一条他自己知道是假的异常。两档的区别与代价逐字见那个函数的 docstring。

--------------------------------------------------------------------------
⚠️ spec §5 的第 7 阶段（``Aggregate``）今天没有自己的模块
--------------------------------------------------------------------------

它的「聚合 RPE / 打卡 / 二次小测」那一半就是本阶段做的事，而「计算标准化得分」
那一半**仍未落库**：``mini_test.normalized_score`` 由
``GET /api/mini-tests/normalized`` **现算**、刻意不回写（理由逐字见
:mod:`app.api.routers.feedback` 模块 docstring 的「刻意不做」第 3 条）。
⚠️ 于是进步榜读的是那一列**库里现有的值**，而它今天的唯一写入方是
:func:`app.demo_data.build_demo_feedback`（演示口径的近似值）。
已登记为关切（:func:`app.domain.report.progress_board` 的 docstring 也逐字记了）。
"""
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import repo

# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：这几张表**都不在** app.db.models 的
#    公有导入面上，写 models.Alert 会当场 AttributeError。
from app.db.models.derived import StratificationResult
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester
from app.db.models.prescription import Prescription
from app.domain.alerts import RuleId
from app.domain.prescription.weekly import current_week
from app.domain.report import (
    RpeWeek,
    abnormal_roster,
    alert_summary,
    checkin_rate_by_layer,
    layer_distribution,
    progress_board,
    rpe_summary,
    suggestion,
)

# ⚠️ 五样东西一律从既有所有者 import，不写第二份：
#    * ``_counted_checkin_days`` / ``_reported_checkin_days`` 是「哪几天算完成」与
#      「哪几天算报过」的**唯一**所有者（前者由 tests/pipeline/test_alert_stage.py
#      的一条测试与 completion-rate 端点对账）；
#    * ``semester_week_of`` / ``semester_week_range`` 是「学期周次 ↔ 那 7 天」的两个方向
#      （:mod:`app.api.routers.feedback._week_days` 是 api 层的第三个方向，两处并存、
#      由一条测试钉成相等——本模块不造第四处）；
#    * ``_previous_prescriptions`` / ``_require_batch_in_semester`` /
#      ``training_days_of`` 分别是「哪一张处方在那一天生效（批级预取版）」、
#      「批次与学期必须是同一次运行」、「处方第 N 周的训练日」的唯一所有者。
#      ⚠️ ``training_days_of`` 全仓只有一份定义（P8-A3；AST 守卫
#      ``test_training_days_of_has_exactly_one_definition`` 数定义份数 == 1）。
from app.pipeline.alert_stage import (
    ALERT_HANDLED,
    ALERT_IGNORED,
    ALERT_PENDING,
    _CHECKIN_LOOKBACK,
    _counted_checkin_days,
    _reported_checkin_days,
    semester_week_range,
)
from app.pipeline.prescription_stage import (
    _previous_prescriptions,
    _require_batch_in_semester,
    training_days_of,
)

__all__ = [
    "ALERT_STATUSES",
    "CLASS_RPE_HIGH_RULE",
    "ClassCache",
    "ClassSnapshot",
    "REPORT_WEEKDAY",
    "ReportSummary",
    "aggregates_of",
    "class_snapshot",
    "generate_weekly_reports",
    "is_report_day",
    "labels_at",
    "new_cache",
]

logger = logging.getLogger(__name__)

#: 「每周日」的那个 ``weekday()`` 值（spec §8.5 逐字）。⚠️ 理由与三个反例
#: 逐字见模块 docstring 的那一节；``6`` = 周日（``Monday == 0``）。
REPORT_WEEKDAY: int = 6

#: ``alert.status`` 的三档，**顺序就是周报载荷里键的顺序**。
#:
#: ⚠️ 值域的所有者是 :attr:`Alert.STATUSES`（+ DB 的 ``ck_alert_status``），
#: 生产写入方是 :mod:`app.pipeline.alert_stage` 的那三个常量，本 tuple 只回答
#: 「按什么顺序摆这三档」。它由 :func:`app.domain.report.alert_summary` 的
#: ``statuses`` 入参消费——⚠️ **domain 里刻意不声明第二份**
#: （它 import 不到 ``app.pipeline``，而「传参」比「两份并存 + 一条对账测试」
#: 少一个可能漂移的住址，理由逐字见那个函数的 docstring）。
ALERT_STATUSES: tuple[str, ...] = (ALERT_PENDING, ALERT_HANDLED, ALERT_IGNORED)

#: 「算法建议」要读的那一条班级级信号（spec §8.5 逐字点名 ``YELLOW_CLASS_RPE_HIGH``）。
#:
#: ⚠️ **它是 :class:`~app.domain.alerts.RuleId` 的一个成员的 ``.value``**，
#: 不是第二份字面串：规则 ID 词表的所有者是 ``data/alert_rules.yaml``
#: （``RuleId`` 与它由 Task 6 的一条测试对账）。
CLASS_RPE_HIGH_RULE: str = RuleId.YELLOW_CLASS_RPE_HIGH.value

#: 一周。⚠️ **不写 ``days=7``**：「一周 7 天」这条历法事实的所有者是
#: :data:`app.domain.prescription.triggers._DAYS_PER_WEEK`
#: （:mod:`app.pipeline.alert_stage` 的 ``_ONE_WEEK`` 逐字写了这条纪律，本模块照它办）。
_ONE_WEEK = dt.timedelta(weeks=1)
_ONE_DAY = dt.timedelta(days=1)


def is_report_day(as_of: dt.date) -> bool:
    """``as_of`` 是不是**该生成周报**的那一天（spec §8.5 逐字「每周日批处理生成」）。

    判据只有 :data:`REPORT_WEEKDAY` 一个常量，故「哪一天生成」在全仓只有一个住址。
    ⚠️ 它**刻意不知道**学期周次：调用方（:func:`app.pipeline.daily.run_daily`）
    自己用 :func:`~app.pipeline.alert_stage.semester_week_of` 算周次，而 ``as_of``
    早于开学日时那里返回 ``None``。两件事因此**不会互相掩盖**：一个开学前的周日，
    本函数仍然说「是周日」，挡掉那一次生成的是 ``week is None``。
    """
    return as_of.weekday() == REPORT_WEEKDAY


@dataclass
class ClassCache:
    """一次「按班取数」的共享上下文。

    ⚠️ **一个 cache 只服务一个 ``(as_of, week)``**：``rates`` 与 ``gaps`` 两格是
    **按学生**记忆化的，而它们的值取决于学期周次与水位线。跨周复用同一个 cache 会让
    第 N 周的完成率被当成第 N+1 周的（静默、且不报错）。
    :func:`generate_weekly_reports` 每次调用建一个新的；
    :mod:`app.api.routers.dashboard` 每个请求建一个新的。

    ``prescriptions``
        :func:`~app.pipeline.prescription_stage._previous_prescriptions` 的输出
        （**一次查询**拿到全部学生的「``generated_on <= as_of`` 里最新的那一张」，
        且四个大 ``JsonText`` 列被 ``load_only`` 延迟加载）。
    ``days``
        ``{(prescription_id, 处方周次): (训练日集合, 是否 paused) | None}``。
        ⚠️ **记忆化是承重的**：一个学生同时在行政班与分层班的名册上
        （seed 的编班是两套，实测 500 人 → 1000 行 ``enrollment``），
        不记忆化的话整学期回放要装配 16 000 次训练包而不是 8 000 次。
        实测（探针 ``t8_probes/p2_timing.py``，500 人 / 17 个班 / 本机）：
        一次 :func:`~app.pipeline.prescription_stage.training_days_of` 约 **0.39 ms**，
        故记忆化省下的那 8 000 次约 **3.1 s**。
        ⚠️ ``None`` 也被记忆化（装配失败的那一档），故同一个学生**只失败一次**、
        只写一条 ``warning``。
    ``rates`` / ``gaps``
        按学生记忆化的两个聚合量（都与教学班无关，故可以跨班共享）。
    ``errors``
        按人捕获的失败数（异常分层的第二档）。
    """

    prescriptions: Mapping[int, Prescription]
    days: dict = field(default_factory=dict)
    rates: dict = field(default_factory=dict)
    gaps: dict = field(default_factory=dict)
    errors: int = 0


@dataclass(frozen=True)
class ClassSnapshot:
    """一个教学班一周的**全部取数结果**——:func:`aggregates_of` 的唯一入参。

    ⚠️ 它**不含任何聚合量**（一个均值、一个计数都没有）：本类是「库里的行」与
    「domain 的纯函数」之间的那一层适配，故它的每个字段都能一一对上
    :mod:`app.domain.report` 某个函数的某个入参（硬规矩 #110：逐字段回问
    「这个值喂给谁」）：

    ==========================  ==================================================
    字段                          喂给谁
    ==========================  ==================================================
    ``labels_now`` / ``previous`` :func:`~app.domain.report.layer_distribution`
    ``rpe_now`` / ``rpe_prev``    :func:`~app.domain.report.rpe_summary`
    ``rates`` + ``labels_now``    :func:`~app.domain.report.checkin_rate_by_layer`
    ``mini_pairs``               :func:`~app.domain.report.progress_board`
    ``alert_rows``               :func:`~app.domain.report.alert_summary`
    ``class_rpe_high`` + RPE 均值 :func:`~app.domain.report.suggestion`
    ``gap_days`` + ``peak_rpes``  :func:`~app.domain.report.abnormal_roster`
    ==========================  ==================================================

    ``week`` / ``week_start`` / ``watermark`` / ``course_section_id`` / ``semester_id``
    五格是**元数据**（前端要显示「2025-2026-1 第 3 周，数据截至 09-21」），
    不进任何 domain 函数。``roster`` 同理——⚠️ **本班人数是 ``len(roster)``、
    不是 ``sum(labels_now.values())``**：一个从未被分层过的学生在 ``labels_now`` 里
    缺席（:func:`labels_at` 的 docstring 逐字交代了为什么不给他补默认标签），
    而「本班 40 人」必须包含他。
    """

    course_section_id: int
    semester_id: int
    week: int
    week_start: dt.date
    watermark: dt.date
    roster: tuple
    labels_now: dict
    labels_prev: "dict | None"
    rpe_now: RpeWeek
    rpe_prev: "RpeWeek | None"
    rates: dict
    mini_pairs: dict
    alert_rows: tuple
    class_rpe_high: bool
    gap_days: dict
    peak_rpes: dict


def new_cache(session: Session, as_of: dt.date) -> ClassCache:
    """建一个 :class:`ClassCache`（内含**一次**处方批级预取）。

    ⚠️ 它是「一个 cache 一个 ``(as_of, week)``」那条纪律的入口：调用方拿到的是一个
    空的记忆化上下文，而不是一个全局单例。
    """
    return ClassCache(prescriptions=_previous_prescriptions(session, as_of))


def labels_at(session: Session, student_ids: Sequence[int], watermark: dt.date) -> dict:
    """每个学生**在 ``watermark`` 那天生效**的分层标签，``{student_id: label}``。

    「那天生效」= ``computed_on <= watermark`` 里 ``computed_on`` **最大**的那一行
    （``stratification_result.valid_to`` 刻意不去关闭上一日的行，故「哪一条现在生效」
    由 ``computed_on`` 最大者唯一确定——口径逐字见
    :func:`app.pipeline.daily._stratify_and_persist` 里那一列的注释）。

    ⚠️ **一次查询拿到全部学生**（``GROUP BY student_id`` + 自连接回原表取 ``label``），
    不逐人查：整学期 500 人 ×112 业务日会让 ``stratification_result`` 长到 56 000 行，
    逐人查一次就是 500 次往返 ×17 个班 ×16 个周日。``(student_id, computed_on)`` 上有
    ``uq_stratification_result_student_day`` 那条唯一索引，故 ``GROUP BY`` 用得上它。

    ⚠️ **返回的 dict 可能比 ``student_ids`` 短**：一个从未被分层过的学生不在结果里。
    调用方**不得**给他补一个默认标签——「没有分层行」与 ``insufficient_data`` 是两件事
    （后者是跑过了、但有效项不足 4 个），补一个默认值就是把前者讲成后者。
    于是他会落进 :func:`app.domain.report.layer_flow` 的 ``appeared`` 那一档，
    那正是它存在的理由。
    """
    latest = (
        select(
            StratificationResult.student_id.label("sid"),
            func.max(StratificationResult.computed_on).label("day"),
        )
        .where(
            StratificationResult.student_id.in_(student_ids),
            StratificationResult.computed_on <= watermark,
        )
        .group_by(StratificationResult.student_id)
        .subquery()
    )
    return dict(
        session.execute(
            select(StratificationResult.student_id, StratificationResult.label).join(
                latest,
                (StratificationResult.student_id == latest.c.sid)
                & (StratificationResult.computed_on == latest.c.day),
            )
        ).all()
    )


def _training_days(
    session: Session,
    cache: ClassCache,
    prescription: Prescription,
    rx_week: int,
    exercises: Mapping,
):
    """``(训练日集合, 是否 paused)``，**记忆化**；装配失败则记忆化 ``None``。

    ⚠️ 失败**也进缓存**（``None``）：一个训练包坏了的学生若被 17 个班各撞一次，
    就会写 17 条一模一样的 ``warning``、装配 17 次同一个坏 JSON。
    记忆化 ``None`` 让「这个人判不了」成为一个**一次性**的事实。
    """
    key = (prescription.id, rx_week)
    if key in cache.days:
        return cache.days[key]
    try:
        value = training_days_of(
            session, prescription, rx_week, exercises=exercises
        )
    except Exception as exc:  # noqa: BLE001 - 按人捕获，见模块 docstring
        cache.errors += 1
        logger.warning(
            "周报/大屏取数：学生 %s 的处方 %s 第 %s 周装配不出训练日：%s: %s —— "
            "这一格记成「判不了」（完成率 None、连续未打卡天数不计），"
            "整份班级周报不消失。这一档要人工过目（它通常是训练包 JSON 坏了，"
            "或覆盖记录里的动作已经从 exercises.yaml 删掉）",
            prescription.student_id, prescription.id, rx_week, type(exc).__name__, exc,
        )
        value = None
    cache.days[key] = value
    return value


def _rate_of(
    session: Session,
    cache: ClassCache,
    student_id: int,
    day_set: set,
    watermark: dt.date,
    logs: Sequence,
    exercises: Mapping,
) -> "float | None":
    """一个学生在**本学期第 N 周**的打卡完成率，``None`` = 判不了。

    分母 = 处方训练日 ∩ ``day_set``（= 学期第 N 周里 ``<= watermark`` 的那些天），
    分子 = :func:`app.pipeline.alert_stage._counted_checkin_days` ∩ 分母。
    ⚠️ 窗口的取舍逐字见模块 docstring 的「三个窗口口径」（硬规矩 #113）。
    ⚠️ ``logs`` 可以比学期周**更宽**（调用方为 :func:`_gap_of` 多取了三周）：
    分子是那一片日志与分母的**交集**，故窗口更宽的那些天不会进来。

    ``None`` 的四档（**判不了，不是 0%**）：① 没有生效处方；② 处方已到期
    （:func:`~app.domain.prescription.weekly.current_week` 返回 ``None``）；
    ③ 那一周 ``paused``；④ 处方训练日与学期周**不相交**（分母为空）。
    ⚠️ 而「有训练日、已经过去、一次卡都没打」的学生是 **``0.0``**——
    他确实 measurable，而且确实没练；把他记成 ``None`` 会让班级完成率**系统性偏高**，
    而完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」。

    ⚠️ **``min(1.0, …)`` 那个夹子在这里看似多余**（分子是分母的子集，故结构上 ≤ 1），
    而它与 :func:`app.pipeline.alert_stage._student_signals` 里那一个是同一条护栏：
    谁哪天把交集去掉（例如改成「按学期周算分子、按处方周算分母」），比率就会越过 1，
    而 :mod:`app.domain.alerts` 的 ``>= 1.0`` 会静默开始与 spec 的「100%」不等价。
    """
    if student_id in cache.rates:
        return cache.rates[student_id]
    rate = None
    prescription = cache.prescriptions.get(student_id)
    if prescription is not None:
        rx_week = current_week(
            prescription.generated_on, watermark, prescription.microcycle_weeks
        )
        if rx_week is not None:
            got = _training_days(session, cache, prescription, rx_week, exercises)
            if got is not None:
                days, paused = got
                expected = {day for day in days if day in day_set}
                if not paused and expected:
                    done = _counted_checkin_days(logs) & expected
                    rate = min(1.0, len(done) / len(expected))
    cache.rates[student_id] = rate
    return rate


def _gap_of(
    session: Session,
    cache: ClassCache,
    student_id: int,
    watermark: dt.date,
    logs: Sequence,
    exercises: Mapping,
) -> "int | None":
    """一个学生「连续未打卡的应打卡训练日天数」；判不了则 ``None``（**不是 0**）。

    ⚠️ **窗口与 :func:`app.pipeline.alert_stage._student_signals` 逐字相同**
    （本处方周 + 上一周的训练日里 ``<= watermark`` 的那些，按日期倒着数**连续**没在
    :func:`~app.pipeline.alert_stage._reported_checkin_days` 里出现的天数）。
    这一格与完成率那一个**刻意相反**：完成率问的是「这个班**本周**练得怎么样」
    （学期周），而本函数问的是「这个学生**失联多久了**」——与
    ``YELLOW_CHECKIN_GAP`` 是**同一个问题**，故必须共用同一个窗口（硬规矩 #113）。
    ⚠️ 收窄到学期周的失效形态很具体：一个上周就开始失联的学生，
    本周只错过 2 天 → 大屏的「连续 3 天」筛不到他 → 而预警那一条（阈值 2 天）
    **已经**给他开了工单。同一个学生在工单里在、在大屏上不在，教师会认为大屏坏了。

    ⚠️ **判不了时返回 ``None`` 而不是 ``0``**（这一格与预警阶段刻意不同，
    而 :func:`app.domain.report.abnormal_roster` 的入参只要 ``int``）：
    一个没有处方的学生「连续 0 天未打卡」是一句**没有依据的话**
    ——系统不知道他该练哪几天。故本函数返回 ``None``，
    由调用方**把 ``None`` 的那些人整个排除**（不出现在大屏异常名单上，
    也不出现「0 天」这个假数）。

    ⚠️ 本周的 ``paused`` **刻意不参与判定**（只判上一周的）：口径逐字照
    :func:`app.pipeline.alert_stage._student_signals`（那里也是
    ``candidate = set(days)`` 不看 ``paused``，只有上一周看 ``previous_paused``）。
    两处必须同一条，否则同一个学生在预警与大屏上的天数会不同。

    ⚠️ 阈值不在这里比：``>= SCREEN_GAP_DAYS`` 那一步归
    :func:`app.domain.report.abnormal_roster`（本模块只算天数）。
    """
    if student_id in cache.gaps:
        return cache.gaps[student_id]
    gap = None
    prescription = cache.prescriptions.get(student_id)
    if prescription is not None:
        rx_week = current_week(
            prescription.generated_on, watermark, prescription.microcycle_weeks
        )
        if rx_week is not None:
            got = _training_days(session, cache, prescription, rx_week, exercises)
            if got is not None:
                candidate = set(got[0])
                if rx_week > 1:
                    previous = _training_days(
                        session, cache, prescription, rx_week - 1, exercises
                    )
                    if previous is not None and not previous[1]:
                        candidate |= previous[0]
                reported = _reported_checkin_days(logs)
                expected = sorted(day for day in candidate if day <= watermark)
                missed = 0
                for day in reversed(expected):
                    if day in reported:
                        break
                    missed += 1
                gap = missed
    cache.gaps[student_id] = gap
    return gap


def class_snapshot(
    session: Session,
    *,
    semester_id: int,
    course_section_id: int,
    week: int,
    as_of: dt.date,
    exercises: Mapping,
    cache: ClassCache,
) -> ClassSnapshot:
    """把一个教学班的第 ``week`` 周读成一个 :class:`ClassSnapshot`（**7 次查询**）。

    ⚠️ **它是「怎么读一个班的一周」在全仓的唯一编排**（模块 docstring 的第一节给了
    理由：大屏与周报必须给出同一个数）。故它刻意**不**做批级预取——
    一次只读一个班，而 :func:`generate_weekly_reports` 逐班调它。
    代价是「17 个班 × 7 次查询」而不是「7 次查询」，实测那一档在本仓的规模下
    （17 个班、16 个周日）是 1 900 次索引查找，与
    :func:`~app.pipeline.prescription_stage.training_days_of` 那 8 000 次装配相比
    可以忽略；换来的是**两条路径不可能分叉**。

    ``week <= 1`` → ``rpe_prev`` 与 ``labels_prev`` 一律 ``None``
    （简报 Task 8「决定」第 2 条：「不知道」不得讲成「变化了」）。
    ⚠️ 而 ``week > 1`` 但上一周**一行分层都没有**（那一周一次批处理都没跑）
    也归到 ``None``：否则全班都会被报成「本周升入 N 人」，
    那正是简报要防的那句凭空捏造的进步。
    """
    semester = session.get(Semester, semester_id)
    if semester is None:
        raise ValueError(
            f"semester 表里查无 id={semester_id}：学期周次要靠 start_date 折算成日历日期"
            f"（semester_week_range），没有它就连「第 {week} 周是哪 7 天」都无从回答"
        )
    week_start, week_end = semester_week_range(semester.start_date, week)
    watermark = min(as_of, week_end)
    full_day_keys = tuple(
        (week_start + _ONE_DAY * offset).isoformat() for offset in range(7)
    )
    # ⚠️ 分母/中断用的那一份「本周的日子」夹到水位线，而 RPE 曲线的横轴
    #    （full_day_keys）**刻意不夹**：理由逐字见模块 docstring 的「三个窗口口径」。
    day_set = {
        week_start + _ONE_DAY * offset
        for offset in range(7)
        if week_start + _ONE_DAY * offset <= watermark
    }
    prev_end = week_start - _ONE_DAY
    prev_start = prev_end - _ONE_WEEK + _ONE_DAY
    prev_days = tuple(
        (prev_start + _ONE_DAY * offset).isoformat() for offset in range(7)
    )

    roster = tuple(
        session.scalars(
            select(Enrollment.student_id)
            .where(
                Enrollment.semester_id == semester_id,
                Enrollment.course_section_id == course_section_id,
            )
            .order_by(Enrollment.student_id)
        )
    )

    labels_now = labels_at(session, roster, watermark)
    labels_prev = None if week <= 1 else (labels_at(session, roster, prev_end) or None)

    now_values: dict = defaultdict(list)
    prev_values: dict = defaultdict(list)
    peak_rpes: dict = defaultdict(list)
    for student_id, session_date, rpe in session.execute(
        select(RpeRecord.student_id, ClassSession.session_date, RpeRecord.rpe)
        .join(ClassSession, ClassSession.id == RpeRecord.class_session_id)
        .where(
            ClassSession.course_section_id == course_section_id,
            ClassSession.session_date >= prev_start,
            ClassSession.session_date <= watermark,
        )
        .order_by(ClassSession.session_date, RpeRecord.id)
    ).all():
        day = session_date.isoformat()
        if session_date >= week_start:
            now_values[day].append(rpe)
            peak_rpes[student_id].append(rpe)
        else:
            prev_values[day].append(rpe)

    # ⚠️ 日志的窗口比学期周**宽三周**（:data:`app.pipeline.alert_stage._CHECKIN_LOOKBACK`，
    #    同一个常量、不写第二份）：完成率那一份取的是它与分母的**交集**，故宽出来的
    #    那些天进不去；而中断那一份**要**它们（它的窗口与预警逐字相同，见 _gap_of）。
    logs_by_student: dict = defaultdict(list)
    for row in session.scalars(
        select(TrainingLog).where(
            TrainingLog.student_id.in_(roster),
            TrainingLog.log_date >= watermark - _CHECKIN_LOOKBACK,
            TrainingLog.log_date <= watermark,
        )
    ):
        logs_by_student[row.student_id].append(row)

    rates = {}
    gap_days = {}
    for student_id in roster:
        logs = logs_by_student.get(student_id, ())
        rates[student_id] = _rate_of(
            session, cache, student_id, day_set, watermark, logs, exercises
        )
        gap = _gap_of(session, cache, student_id, watermark, logs, exercises)
        # ⚠️ None（判不了）的人**不进** gap_days：见 _gap_of 的 docstring。
        if gap is not None:
            gap_days[student_id] = gap

    mini_pairs: dict = {}
    by_student: dict = defaultdict(list)
    for row in session.scalars(
        select(MiniTest)
        .where(
            MiniTest.semester_id == semester_id,
            MiniTest.student_id.in_(roster),
            # ⚠️ 上界承重：mini_test 是教师批量录入的，而录入没有「不得录未来周次」的
            #    约束（MiniTest.week 的列注释逐字写了为什么不加那条 CHECK）。
            #    不夹上界的话，周日生成第 3 周的周报会把第 4 周那份还没发生的小测
            #    当成「本次」——一次静默的读未来。
            MiniTest.week <= week,
        )
        .order_by(MiniTest.student_id, MiniTest.week, MiniTest.id)
    ):
        by_student[row.student_id].append(row)
    for student_id, rows in by_student.items():
        # ⚠️ 少于两次 → 这个学生**不在** mini_pairs 里（连 unmeasured 都不计）：
        #    一次小测没有「变化」可言，而 progress_board 的 unmeasured 说的是
        #    「有两次、但分数缺失」。两档分开，否则「本学期还没测第二次」会与
        #    「测了但分数缺失」同形。
        if len(rows) >= 2:
            mini_pairs[student_id] = (
                rows[-2].normalized_score,
                rows[-1].normalized_score,
            )

    alert_rows: list = []
    class_rpe_high = False
    window_start = dt.datetime.combine(week_start, dt.time.min)
    window_end = dt.datetime.combine(watermark + _ONE_DAY, dt.time.min)
    for level, status, rule_id, section_id in session.execute(
        select(Alert.level, Alert.status, Alert.rule_id, Alert.course_section_id).where(
            Alert.semester_id == semester_id,
            # ⚠️ 用 triggered_at 夹窗口、不重算 window_key：班级级那两条规则的
            #    window_key 是 f"{semester_id}:{week}"，那个算式的所有者是
            #    app.domain.alerts 的 _class_rpe_high（它没有单独暴露成函数），
            #    在管道层再拼一遍就是第二个住址。
            Alert.triggered_at >= window_start,
            Alert.triggered_at < window_end,
            or_(
                Alert.course_section_id == course_section_id,
                Alert.student_id.in_(roster),
            ),
        )
    ).all():
        alert_rows.append((level, status))
        if section_id is not None and rule_id == CLASS_RPE_HIGH_RULE:
            class_rpe_high = True

    return ClassSnapshot(
        course_section_id=course_section_id,
        semester_id=semester_id,
        week=week,
        week_start=week_start,
        watermark=watermark,
        roster=roster,
        labels_now=labels_now,
        labels_prev=labels_prev,
        rpe_now=RpeWeek(
            days=full_day_keys,
            values={day: now_values.get(day, ()) for day in full_day_keys},
        ),
        rpe_prev=(
            None
            if week <= 1
            else RpeWeek(
                days=prev_days,
                values={day: prev_values.get(day, ()) for day in prev_days},
            )
        ),
        rates=rates,
        mini_pairs=mini_pairs,
        alert_rows=tuple(alert_rows),
        class_rpe_high=class_rpe_high,
        gap_days=gap_days,
        peak_rpes={k: tuple(v) for k, v in peak_rpes.items()},
    )


def aggregates_of(snapshot: ClassSnapshot) -> dict:
    """把 :class:`ClassSnapshot` 喂给 :mod:`app.domain.report` 的九个纯函数，
    返回**七个键**的聚合载荷。

    ⚠️ **它是「怎么调那九个函数」在全仓的唯一编排**：周报落库取其中六个键
    （:func:`generate_weekly_reports`），大屏与首页取全部七个
    （:mod:`app.api.routers.dashboard`）。两条路径因此**不可能**给出两个不同的数。

    ==========================  ==================================================
    键                            去处
    ==========================  ==================================================
    ``layer_distribution``      ``weekly_class_report.layer_distribution`` + 大屏 ①
    ``rpe_summary``             ``weekly_class_report.rpe_summary`` + 大屏 ②
    ``checkin_rate_by_layer``   ``weekly_class_report.checkin_rate_by_layer``
    ``progress_board``          ``weekly_class_report.progress_board`` + 大屏 ③
    ``alert_summary``           ``weekly_class_report.alert_summary``
    ``suggestion``              ``weekly_class_report.suggestion``（:class:`Text`）
    ``abnormal_roster``         **只有大屏 ④**——⚠️ 不落库：它是 §9.1 的一个实时
                                筛选器，不是 spec §4.7 那 6 项里的一项，
                                而 ``weekly_class_report`` 只有 5 个 JSON 列 +
                                1 个 Text 列、没有它的位置
    ==========================  ==================================================

    ⚠️ ``suggestion`` 的第二个入参是 ``rpe_summary["mean"]``（**未 round 的**周级均值），
    而不是另算一遍：那是 :func:`app.domain.report.week_mean_rpe` 的唯一输出，
    再算一次就是第二个所有者。
    """
    rpe = rpe_summary(snapshot.rpe_now, snapshot.rpe_prev)
    return {
        "layer_distribution": layer_distribution(
            snapshot.labels_now, snapshot.labels_prev
        ),
        "rpe_summary": rpe,
        "checkin_rate_by_layer": checkin_rate_by_layer(
            snapshot.rates, snapshot.labels_now
        ),
        "progress_board": progress_board(snapshot.mini_pairs),
        "alert_summary": alert_summary(
            snapshot.alert_rows, statuses=ALERT_STATUSES
        ),
        "suggestion": suggestion(snapshot.class_rpe_high, rpe["mean"]),
        "abnormal_roster": abnormal_roster(snapshot.gap_days, snapshot.peak_rpes),
    }


#: ``weekly_class_report`` 的 5 个 ``JsonText`` 列 ↔ :func:`aggregates_of` 的键。
#:
#: ⚠️ **它是这五个列名的唯一住址**：:func:`generate_weekly_reports` 按它逐列取值，
#: 故「加一个聚合量而忘了落库」会在这张表上少一行、而不是静默多出一个没人读的键。
_JSON_COLUMNS: tuple[str, ...] = (
    "layer_distribution",
    "rpe_summary",
    "checkin_rate_by_layer",
    "progress_board",
    "alert_summary",
)


@dataclass(frozen=True)
class ReportSummary:
    """一次周报阶段的产出计数。前两格照简报 Interfaces / Produces 逐字，
    第三格是本 Task 加的（口径照 :attr:`app.pipeline.alert_stage.AlertReport.errors`）。

    ``generated``
        本批**写进** ``weekly_class_report`` 的行数（含被 :func:`app.db.repo.upsert`
        走**更新**分支的那些——重放那一天得到的是同一批行、同样的内容，
        故它与「新插入的行数」在重放时**不相等**，而重放要的是前者）。
    ``skipped``
        **名册为空**的教学班数（``enrollment`` 里一个学生都没有）。
        ⚠️ 那一档**不写行**：一份「四个 0 + 三个 None」的周报对教师没有任何信息，
        而它会在 ``GET /api/dashboard/weekly-class-report/{id}`` 上看起来像
        「这个班本周什么都没发生」——与「这个班还没有人」是两件事。
        ⚠️ 它**不是**「判不了」的垃圾桶：组装失败的班计入 :attr:`errors`，
        两格分开，否则「一个班没学生」与「一个班的数据坏了」在计数上同形。
    ``errors``
        按班捕获的失败数 + 按人捕获的失败数（:attr:`ClassCache.errors`）。
        ⚠️ **它不是 0 就该看日志**：每一次都带教学班 id（或学生 id 与处方 id）、
        异常类型与消息写了一条 ``warning``。
    """

    generated: int
    skipped: int
    errors: int


def generate_weekly_reports(
    session: Session,
    semester_id: int,
    batch_id: int,
    week: int,
    *,
    as_of: dt.date,
    now: dt.datetime,
    exercises: Mapping,
) -> ReportSummary:
    """为本学期**全部教学班**生成第 ``week`` 周的周报，返回计数报表。

    ------------------------------------------------------------------
    签名：比简报 Interfaces 多两个 keyword-only 形参（本 Task 顶回的一处）
    ------------------------------------------------------------------

    简报写的是 ``(session, semester_id, batch_id, week, *, as_of)``，而那个签名
    **跑不起来**，缺的两样各是一条 NOT NULL 列或一个既有纪律
    （与 Task 7 给 :func:`app.pipeline.alert_stage.evaluate_alerts` 补 ``now`` /
    ``exercises`` 是同一件事，理由逐字相同）：

    * ``now`` —— ``weekly_class_report.generated_at`` 是 ``DateTime NOT NULL``
      **且无缺省**（本仓全部表的统一约定：时钟由调用方注入，守卫是
      ``tests/db/test_models.py`` 的
      ``test_the_plan03_tables_inject_the_clock_and_never_default_it``）。
      ⚠️ 它必须与预警阶段用的**同一个** ``now``：同一批里「预警触发」与「周报生成」
      的先后顺序否则会随两次 ``now()`` 的调用点漂。
    * ``exercises`` —— :func:`~app.pipeline.prescription_stage.training_days_of` 要它，
      而 :mod:`app.pipeline.prescription_stage` 的既有纪律是「三份参考数据一律由
      调用方注入」，故本模块不自己调 ``refdata_prescription.exercises()`` 单例。

    ⚠️ **不 commit、不 rollback**：事务边界由 :mod:`app.pipeline.daily` 掌握
    （与 :func:`app.db.repo.upsert` / ``generate_prescriptions`` / ``evaluate_alerts``
    同一条口径）。

    ------------------------------------------------------------------
    幂等：``UniqueConstraint`` + ``repo.upsert`` + ``_replay_cleanup``
    ------------------------------------------------------------------

    ``(course_section_id, semester_id, week)`` 唯一，故同日重跑命中**更新**分支
    （:attr:`ReportSummary.generated` 因此计的是「写了多少行」而不是「插了多少行」）。
    ⚠️ 而**重放那一天**靠 :func:`app.pipeline.daily._replay_cleanup` 先按 ``batch_id``
    把本批的行删掉——本 Task 把 ``WeeklyClassReport`` 加进了那份清单（六张 → 七张）。
    漏掉它的失效形态**不是翻倍**（唯一约束挡着），而是更隐蔽的一格：那一行会静默沿用
    **上一轮**的 ``batch_id``，于是下一次重放按新的 ``batch_id`` 删时**删不到它**
    ——它从此永远停在旧批次上，而 ``daily_sync_run`` 的计数看起来全都正常。

    ------------------------------------------------------------------
    ``week`` 的三种越界，一律**不抛**
    ------------------------------------------------------------------

    * ``week <= 0`` / 超出 ``semester.weeks`` —— 得到一段落在学期之外的窗口，
      那几天没有分层、没有快评、没有预警 → 一份全 0 的周报。与
      :func:`app.pipeline.alert_stage.semester_week_of` 的处置逐字相同
      （「第 20 周」在一个 16 周的学期里是「那一周什么都没发生」，不是一次非法请求）。
    * ``as_of`` 早于 ``week_start`` —— 水位线夹到 ``week_start``，
      分母只剩一天（:func:`class_snapshot` 里那一档有注释），周报照生成。
    * ``week == 1`` —— 没有上一周，:func:`app.domain.report.layer_flow` 的
      ``has_previous`` 为 ``False``、``layer_distribution["previous"]`` 为 ``None``。
    """
    _require_batch_in_semester(session, semester_id, batch_id)
    # ⚠️ **这里刻意不再校验一次 ``semester_id`` 存不存在**（本 Task 顶回自己的一版草稿）：
    # 上面那一道已经保证了它存在——它比对的正是 ``daily_sync_run.semester_id``，
    # 而那一列是 NOT NULL 外键，故「批次与学期是同一次运行」成立时那个学期行必然在。
    # 再写一次 ``if session.get(Semester, semester_id) is None: raise`` 是一段
    # **不可达**的代码（它只会被 :func:`class_snapshot` 里那一道覆盖到，
    # 而那一道是可达的：大屏可以直接用一个打错的 ``semester_id`` 调 ``class_snapshot``）。
    # ⚠️ 于是「学期 id 打错了」这一档报的是**批次不匹配**那句人话
    # （``_require_batch_in_semester`` 的消息里已经点明了两个 id），不是「查无此学期」。

    cache = new_cache(session, as_of)
    section_ids = list(
        session.scalars(
            select(CourseSection.id)
            .where(CourseSection.semester_id == semester_id)
            .order_by(CourseSection.id)
        )
    )
    rosters = dict(
        session.execute(
            select(Enrollment.course_section_id, func.count(Enrollment.student_id))
            .where(Enrollment.semester_id == semester_id)
            .group_by(Enrollment.course_section_id)
        ).all()
    )

    generated = skipped = errors = 0
    for section_id in section_ids:
        if not rosters.get(section_id):
            # 名册为空 → 不写行（理由见 ReportSummary.skipped）
            skipped += 1
            continue
        try:
            snapshot = class_snapshot(
                session,
                semester_id=semester_id,
                course_section_id=section_id,
                week=week,
                as_of=as_of,
                exercises=exercises,
                cache=cache,
            )
            aggregates = aggregates_of(snapshot)
            values = {
                "course_section_id": section_id,
                "semester_id": semester_id,
                "week": week,
                "suggestion": aggregates["suggestion"],
                "generated_at": now,
                "batch_id": batch_id,
            }
            values.update({column: aggregates[column] for column in _JSON_COLUMNS})
            repo.upsert(
                session,
                WeeklyClassReport,
                ("course_section_id", "semester_id", "week"),
                values,
            )
            generated += 1
        except Exception as exc:  # noqa: BLE001 - 按班捕获，见模块 docstring
            errors += 1
            logger.warning(
                "教学班 %s 第 %s 周的周报生成失败：%s: %s —— 跳过这一个班，整批不回滚",
                section_id, week, type(exc).__name__, exc,
            )
            continue

    session.flush()
    report = ReportSummary(
        generated=generated, skipped=skipped, errors=errors + cache.errors
    )
    logger.info(
        "学期 %s 批次 %s（%s，第 %s 周）周报阶段：生成 %d 份、跳过 %d 个空名册的班、"
        "取数失败 %d 次（其中按人 %d 次）",
        semester_id, batch_id, as_of.isoformat(), week,
        report.generated, report.skipped, report.errors, cache.errors,
    )
    return report
