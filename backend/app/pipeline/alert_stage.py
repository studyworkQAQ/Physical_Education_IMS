"""预警阶段：spec §8.2 的 5 条规则接上电（Plan 03 Task 7）。

它是 :mod:`app.pipeline.daily` 的第七个阶段
（``Extract → Clean → Percentile → Derive → Stratify → Prescribe → **Alert** → Commit``），
跑在处方阶段**之后**、同一个 SAVEPOINT 之内——因为它要读「当天刚生成的处方」才能算出
``GREEN_MASTERY`` 的完成率与 ``YELLOW_CHECKIN_GAP`` 的应打卡训练日。

本模块**一条判据都不写**：5 条规则的阈值与比较符全在 :mod:`app.domain.alerts`
（纯函数、100% 分支覆盖、Task 6 做过 5 条变异取证），阈值全在 ``data/alert_rules.yaml``。
本模块只负责四件事：

1. **把库里的三源数据组装成 :class:`~app.domain.alerts.StudentSignals` /
   :class:`~app.domain.alerts.ClassSignals`**（``rpe_streak`` / ``mini_test_improved`` /
   ``checkin_gap_days`` / ``completion_rate`` 四个派生信号都算在这里，domain 拿不到库）；
2. **把命中落成 ``alert`` 行**（去重靠 ``uq_alert_rule_subject_semester_window``）；
3. **发消息**（:class:`~app.notify.InAppChannel`，spec §8.3 只做站内消息）；
4. **给红色预警写 ``weekly_adjustment`` 的 ``auto`` 来源**（spec §8.4「减量 20%」）
   ——⚠️ 这是 Plan 02 结案时**逐字留给 Plan 03** 的活：``WeeklyAdjustment.SOURCES``
   的值域 ``{auto, teacher}`` 里，``"auto"`` 到今天为止**没有任何生产写入方**。

--------------------------------------------------------------------------
Review Focus 第 3 条：同一次触发只落一条 alert、只减一次量
--------------------------------------------------------------------------

失效形态是**静默的连乘**：同一条 ``RED_RPE_SUSTAINED`` 在连续第 3、4、5 次快评都满足
条件时，若每次都插一行 ``alert``、每次都写一条 ``weekly_adjustment(factor=0.8)``，
那么「本周训练单」= ``骨架第 N 周 × 该周全部 factor`` 的**累乘**
（:func:`~app.domain.prescription.weekly.weekly_training_sheet`）会把那一周的量乘成
``0.8³ = 0.512``，而全链路**没有一处报错**。

三道闸门，各挡一段：

1. **``window_key`` 锚在「凑满阈值那一次」**（:mod:`app.domain.alerts` 的算式：
   ``rpe_session_ids[streak - 1]``，不是 ``[-1]``）→ streak 再长键也不变；
2. **``uq_alert_rule_subject_semester_window``** 四列唯一 → 同一次触发只有一行 ``alert``，
   本模块**先 SELECT 后 INSERT**，撞上已有行就计入 :attr:`AlertReport.deduped`
   并 ``continue``（⚠️ **不走 :func:`app.db.repo.upsert`**：upsert 的更新分支会把一条
   已经 ``handled`` 的预警静默改回 ``pending``，教师处置过的痕迹就没了）；
3. **``uq_weekly_adjustment_prescription_week_reason_source``** 四列唯一 → 同一处方
   同一周同一原因同一来源只有一条 ``auto`` 调整。⚠️ 这一道**故意让 DB 当裁判**：
   本模块直接 ``session.add`` 一个裸 INSERT 并把它包在自己的 SAVEPOINT 里，撞上
   ``IntegrityError`` 就只回滚那一个 SAVEPOINT、计入日志、继续下一个人。
   **不用 ``repo.upsert``** 的理由逐字见 :func:`_write_auto_adjustment` 的 docstring。

⚠️ 第 1 道闸门有一个**本模块负责的前提**（P7-A3 第 2 条）：``rpe_session_ids`` 必须
按时间升序，而 domain **校不了顺序**（它拿不到 ``class_session.session_date``）。
乱序会让 ``[streak - 1]`` 锚到错误的那一次快评上 → 键随一次迟到提交而移动 →
第 2 道闸门失效 → 连乘回来。故本模块的 ``ORDER BY`` 是承重的，逐字见
:func:`_rpe_rows` 的 docstring。

--------------------------------------------------------------------------
异常分层：按学生捕获，只有基础设施异常才冒泡
--------------------------------------------------------------------------

照 :mod:`app.pipeline.prescription_stage` 的既有分层（简报 Task 7「决定」第 2 条）：
一个学生的信号组装/求值失败（``ValueError`` / ``KeyError`` / ``TypeError`` 一类
「这一个人的输入有问题」）**按学生捕获**、计入 :attr:`AlertReport.errors` + 一条
``warning`` 日志，然后 ``continue``；DB 读写一律在 ``try`` **之外**，故
``IntegrityError`` / ``OperationalError`` 直接抛给 :func:`app.pipeline.daily.run_daily`，
由它回滚整批并写一条 ``status = "failed"`` 的运行记录。

理由与处方阶段逐字相同：本阶段跑在 SAVEPOINT 里，一个学生的数据坏掉不该掀掉一整天的
批处理；而库写不进去时继续跑只会产出一份与库不符的报表。

--------------------------------------------------------------------------
求值人群：**在三源里留过痕的学生**，不是 ``student`` 表的每一个人
--------------------------------------------------------------------------

⚠️ 这是一条**本 Task 的口径决定**，理由是两条（硬规矩 #39：写下能力就写明守不住什么）：

* **正确性**：一个本学期在 ``rpe_record`` / ``training_log`` / ``mini_test`` 三张表里
  一行都没有的学生，11 个信号里 9 个只能是 0 / ``None``——他产出的不是「预警」而是
  一整片 ``insufficient_points`` 留痕。把 500 个人全部求值一遍，得到的是 500 条
  内容完全相同的「判不了」，而那正好淹掉真正有数据的那些人（与
  :mod:`app.pipeline.prescription_stage` 拒绝「逐人一条 ``insufficient_data`` warning」
  是同一条判断）。
* **性能**：``GREEN_MASTERY`` 与 ``YELLOW_CHECKIN_GAP`` 都要
  :func:`~app.pipeline.prescription_stage.training_days_of`，而它要装配训练包
  （:attr:`~app.db.models.prescription.Prescription.training_package` 是 4 周 ×4 课 ×3 block
  的嵌套 JSON）。``_previous_prescriptions`` 为了整学期回放的性能刻意用 ``load_only``
  **延迟加载**那一列，故每次装配都是一次额外的 SELECT。⚠️ 于是「全员求值」会让
  ``tests/pipeline/test_backfill.py``（500 人 ×112 业务日）多跑约 56 000 次装配。
  按「留过痕的人」求值，那条路径上今天的三张表在回放里**恒为空**
  （:mod:`app.pipeline.daily` 一个字节都不往它们写），故 Alert 阶段的成本是
  **常数次查询**（6 次：三源各一次 + 人群一次 + 处方预取一次 + 教学班一次），
  与人数无关。⚠️ 这里刻意不写死「N 次」以外的那个 N：加一次预取就过期，
  而它要说的只是「不随人数增长」。

⚠️ **代价**：一个本学期在三源里**一行都没留过**的学生不会被求值——系统分不清
「他不用这个系统」与「他这周没练」。原型阶段这是可接受的那一侧（给 500 个从没登录过的
人推补练提醒是纯噪声），但要知道它在。真实上线时应当把人群换成
「本学期有选课 ∧ 有生效处方」，那需要 ``enrollment`` 参与，而 ``enrollment`` 今天在
演示数据里是全量铺的、在生产路径上没有任何写入方。

⚠️⚠️ **打卡那一源的窗口与喂信号的窗口刻意不同**（这是上面那条代价的边界，
逐字理由写在 :func:`evaluate_alerts` 体内 ``onboarded`` 那一处的注释里）：
**人群**按「学期起点以来有没有打过卡」取，**信号**按 :data:`_CHECKIN_LOOKBACK`
（三周）取。用同一个窗口的话，一个连续失联四周的学生在回看窗口里一行都没有 →
不在人群里 → ``YELLOW_CHECKIN_GAP`` 对他**永远不触发**，而那正是这条规则存在的理由。
于是「留过痕」的准确含义是**本学期曾经用过这个系统**，不是「最近三周用过」。

**班级级那一侧不按数据筛**：一个教学班本周一次快评都没有时 ``mean_rpe is None``，
domain 会把它记成留痕（``insufficient_points: 0``）而**不是**「测了且没问题」——
那正是 :func:`~app.domain.alerts.class_skip_traces` 存在的理由。教学班的数量是十几个
（不是几百个），故全量遍历不贵。
"""
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：这七张表**都不在** app.db.models 的
#    公有导入面上，写 models.Alert 会当场 AttributeError。
from app.db.models.feedback import Alert, ClassSession, MiniTest, RpeRecord, TrainingLog
from app.db.models.organisation import CourseSection, Semester
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.domain.alerts import (
    AlertLevel,
    AlertRules,
    ClassSignals,
    RuleId,
    StudentSignals,
    evaluate_class,
    evaluate_student,
    class_skip_traces,
    student_skip_traces,
)
from app.domain.prescription.exercises import ExerciseSpec
from app.domain.prescription.weekly import WeeklyFactor, current_week
from app.notify import (
    RECIPIENT_STUDENT,
    RECIPIENT_TEACHER,
    InAppChannel,
    NotificationChannel,
)

# ⚠️ 复用处方阶段那个私有的批次前置校验（口径照 app/api/routers/feedback.py 复用
#    _get_or_404、app/api/routers/prescription.py 复用 _current_prescription 的既有处置）：
#    「批次与学期必须是同一次运行」这件事在全仓只应该有一种说法，而那一段话
#    （含它点名的失效形态：接错批次会让重放删不到本批的行、于是翻倍）已经写在那里了。
from app.pipeline.prescription_stage import (
    _previous_prescriptions,
    _require_batch_in_semester,
    training_days_of,
)

__all__ = [
    "ALERT_HANDLED",
    "ALERT_IGNORED",
    "ALERT_PENDING",
    "AUTO_REDUCTION_FACTOR",
    "AUTO_SOURCE",
    "AlertReport",
    "evaluate_alerts",
    "semester_week_of",
    "semester_week_range",
]

logger = logging.getLogger(__name__)

#: ``alert.status`` 的三档。⚠️ **值域的所有者是** :attr:`Alert.STATUSES`
#: （+ DB 的 ``ck_alert_status``），本三个常量只回答「预警阶段与处置端点各写哪一个」。
#: 守卫是 ``tests/pipeline/test_alert_stage.py`` 的
#: ``test_the_status_and_source_constants_are_inside_the_model_value_domains``
#: （两侧不同源：一侧是本常量、一侧是类常量，硬规矩 #35）。
#: ⚠️ :mod:`app.api.routers.alerts` **import 这三个**、不抄第二份字面串。
ALERT_PENDING = "pending"
ALERT_HANDLED = "handled"
ALERT_IGNORED = "ignored"

#: ``weekly_adjustment.source`` 的 ``auto`` 档（spec §8.4「预警触发减量 20%」）。
#:
#: ⚠️ **本常量是 ``"auto"`` 这个串在生产代码里的唯一住址**：值域的所有者是
#: :attr:`WeeklyAdjustment.SOURCES`，而 Plan 02 Task 6 建表时逐字写下了
#: 「``"auto"`` 今天**没有生产写入方**，它进 SOURCES 是因为 CHECK 的值域要与 Plan 03
#: 的写入方一次对齐」。本 Task 就是那个写入方。
#: ⚠️ :mod:`app.api.routers.alerts` 的 ``reduce_20pct`` 那一档**也用本常量**——
#: 教师点「减量 20%」与管道自动减量是**同一次调整**的两个触发点，不是两次调整，
#: 理由逐字见那个端点的 docstring（少了它会得到 ``0.8 × 0.8 = 0.64``）。
AUTO_SOURCE = "auto"

#: 「减量 20%」的系数（spec §8.4 的字面：``0.8``）。
#:
#: ⚠️ **它不在 ``alert_rules.yaml`` 里，而那是有意的**：那份 YAML 的所有者是
#: 「5 条规则的**判据阈值**」（``_PARAM_TYPES`` 逐规则钉住了键集，多一个键就在加载期
#: 响亮失败），而 ``0.8`` 不是判据、是**处置动作的量**。把它塞进 YAML 要同时改
#: ``_PARAM_TYPES``（Task 6 已结案、且它的键集守卫是「恰好这几个键」）与
#: ``data/alert_rules.yaml``（被 ``ALERT_RULES_FINGERPRINT`` 按字节钉住，
#: 改一个数就红，而 spec §4.4 逐字要求改阈值走版本控制与评审）。
#: 故它住在这里，与它的两个消费者（本模块的自动写入 +
#: :mod:`app.api.routers.alerts` 的教师写入）**同一个住址**。
#:
#: ⚠️ **写入前一律先构造一个 :class:`~app.domain.prescription.weekly.WeeklyFactor`
#: 值对象再落库**（Plan 02 留给 Plan 03 的第 4 条）：``weekly_adjustment.factor`` 那一列
#: **刻意没有 CHECK**（P8-A6：``(0, 2]`` 是读模型的语义、不是数据的形状），故值对象是
#: 写入侧**唯一**的闸门。少了它，一个 ``factor = 0`` 会静默落库，然后让学生端打开
#: 训练单时在 :func:`~app.pipeline.prescription_stage.weekly_factors_of` 里抛
#: ``ValueError`` → **500**（Plan 02 Task 8 的关切 1 逐字就是这个形状）。
AUTO_REDUCTION_FACTOR = 0.8

#: 一周。⚠️ **不写 ``days=7``**：「一周 7 天」这条历法事实的所有者是
#: :data:`app.domain.prescription.triggers._DAYS_PER_WEEK`（在管道层再写一个 ``7``
#: 就是第二个住址，:func:`app.pipeline.prescription_stage.valid_to_of` 的 docstring
#: 逐字写了这条纪律）。``dt.timedelta(weeks=1)`` 是同一个数的**派生**形式。
_ONE_WEEK = dt.timedelta(weeks=1)

#: 算 ``checkin_gap_days`` 时向回看多久。
#:
#: ⚠️ **两个处方周**（不是「N 天」）：中断的定义是「连续 N 个**应打卡训练日**未打卡」，
#: 而训练日来自处方的周训练单。只看本周的话，一个在周中才开始的中断永远凑不满
#: ``gap_days = 2``（绿层处方每周只练 2 天）；多看一周就能跨周接上。
#: ⚠️ **它是一个上限**（硬规矩 #39）：一段比两周更长的中断会被截断成两周的长度，
#: 于是 ``checkin_gap_days`` 报的是「至少这么多」。判据是 ``>= gap_days``，
#: 截断**不会**漏报（只会少报天数），故方向是安全的。
_GAP_LOOKBACK_WEEKS = 2

#: 预取 ``training_log`` 的窗口。比 :data:`_GAP_LOOKBACK_WEEKS` 多一周：
#: 处方周与学期周可以错开（``generated_on`` 不是学期第一天是真实数据里的常态），
#: 而完成率要的是**本处方周**的训练日，那些日子最早可以落在三周前。
_CHECKIN_LOOKBACK = _ONE_WEEK * (_GAP_LOOKBACK_WEEKS + 1)


@dataclass(frozen=True)
class AlertReport:
    """一次预警阶段的产出计数。前四格照简报 Interfaces / Produces 逐字，后两格是
    本 Task 加的、各有一条出处。

    ``raised``
        **本批新落库**的 ``alert`` 行数 = :attr:`app.db.models.ops.DailySyncRun.alert_count`
        要落的值（Plan 01 就建好的列、至今从未被写过；Plan 02 留给 Plan 03 的第 7 条）。
        ⚠️ 它是「新写的」而不是「今天成立的」：撞上已有行而 dedup 的那些**不计入**，
        故同一天重跑得到 ``raised = 0``——那正是重放该有的样子。
    ``deduped``
        求值成立、但 ``uq_alert_rule_subject_semester_window`` 上已经有一行的次数
        （Review Focus 第 3 条的可观测量）。
    ``by_level``
        ``{level: 新落库的行数}``，**稀疏**（计数为 0 的级别不出现，口径照
        :attr:`app.pipeline.prescription_stage.PrescriptionReport.skipped_reasons`：
        一律以 0 入字典的话「今天没有红牌」与「今天没跑」就同形了）。
    ``adjustments_written``
        本批**新写**的 ``weekly_adjustment(source="auto")`` 行数。
        ⚠️ 它**可以小于**红色预警的条数：处方已到期时不写（见
        :func:`_write_auto_adjustment`），撞唯一约束时也不写。
    ``skipped``
        ``{rule_id: 「求值过、但判不了」的次数}``——**P7-A3 第 1 条的落点**。
        ⚠️⚠️ **它与 :attr:`app.pipeline.report_stage.ReportSummary.skipped` 同名不同义**
        （Plan 03 Task 9 写明）：那一格数的是「**名册为空**的教学班数」
        （``enrollment`` 里一个学生都没有 → 不写周报行），与本格「哪条规则对哪几个人
        判不了」是两个完全不相干的量，且**类型也不同**（那一格是 ``int``、本格是 ``dict``）。
        两格都叫 ``skipped`` 是因为它们各自回答「这一次跑**跳过**了什么」，
        而两个阶段跳过的是不同种类的东西。⚠️ 合并成一个名字会让下一个人以为
        「预警跳过的次数」与「周报跳过的班数」可以相加。
        :func:`~app.domain.alerts.student_skip_traces` / ``class_skip_traces`` 回答的是
        「什么时候判不了」（``insufficient_points`` / ``missing: completion_rate``），
        而 Task 6 逐字交代了「留痕的消费者是 Task 7，本模块只负责算出它」。
        ⚠️ **不读它就是死配置**（与 Plan 02 的 ``Intensity.rpe`` 同型），故它进报表、
        进日志，并由 ``test_the_skip_traces_are_consumed_not_just_computed`` 钉住。
    ``errors``
        按学生/按班捕获的求值失败数（异常分层第 1 档）。⚠️ **它不是 0 就该看日志**：
        每一次都带学生 id、异常类型与消息写了一条 ``warning``。
    """

    raised: int
    deduped: int
    by_level: dict
    adjustments_written: int
    skipped: dict
    errors: int


def semester_week_of(start_date: dt.date, day: dt.date) -> "int | None":
    """``day`` 是学期（开学日 ``start_date``）的**第几周**（1-based），早于开学日则 ``None``。

    ⚠️ **这是「学期周次」，不是处方微周期内的周次**（后者由
    :func:`~app.domain.prescription.weekly.current_week` 算）。两者在 ``generated_on``
    不等于 ``semester.start_date`` 时会错开，而那个错开是真实数据里的常态。
    ``mini_test.week`` / ``weekly_class_report.week`` /
    :attr:`StudentSignals.week` 用的都是**本函数**这一个口径。

    ⚠️ **它不校验上界**：一个超出 ``semester.weeks`` 的日期会得到一个大于学期长度的周次。
    与 :func:`app.api.routers.feedback._week_days` 同一条处置（那里的 docstring 逐字写了
    理由：「第 20 周」在一个 16 周的学期里是「那一周什么都没发生」，不是一次非法请求）。

    ⚠️ **与 ``_week_days`` 是同一个口径的两个方向**（日期 → 周次 / 周次 → 7 天），
    两处并存、由 ``tests/pipeline/test_alert_stage.py`` 的
    ``test_the_semester_week_helpers_agree_with_the_api_layer_one`` 钉成逐字相等
    （先例是 :class:`app.domain.alerts.AlertLevel` 与 :attr:`Alert.LEVELS`：
    两份并存、由一条测试钉成相等）。不合并的理由是分层：``_week_days`` 住在
    ``app/api/``，而本模块住在 ``app/pipeline/``，反向 import 被架构守卫禁止。
    """
    if day < start_date:
        return None
    return (day - start_date) // _ONE_WEEK + 1


def semester_week_range(start_date: dt.date, week: int) -> "tuple[dt.date, dt.date]":
    """学期第 ``week`` 周的首日与末日（**闭区间**）。口径逐字见 :func:`semester_week_of`。"""
    first = start_date + _ONE_WEEK * (week - 1)
    return first, first + _ONE_WEEK - dt.timedelta(days=1)


def _rpe_rows(session: Session, semester_id: int):
    """本学期的**全部**课堂快评，按「学生 → 课次时间」升序，只取 8 个小列。

    ⚠️⚠️ **``ORDER BY`` 是承重的**（P7-A3 第 2 条）。:class:`StudentSignals` 的契约要求
    ``rpe_session_ids`` **按时间升序**，而 domain 的
    :func:`~app.domain.alerts._require_parallel` **只校长度、校不了顺序**（它拿不到
    ``class_session.session_date``）。顺序错了的失效形态是**静默的**：
    ``window_key`` 取 ``rpe_session_ids[streak - 1]``，一个错位的元组会让它锚到
    另一次快评上，于是「同一次触发只有一条 alert」失效 → 连乘 ``0.512`` 回来。

    ⚠️ **排序键是「课次时间」而不是「提交时刻」**（本 Task 顶回派单的一处，理由是一条
    具体的失效序列）：派单写的是「按 ``submitted_at`` 排序」，而 ``submitted_at`` 是
    **学生按下提交键**的时刻，不是那节课的时刻。两者在正常流程里同序（快评是课堂上
    投屏口令、当场交的），但 :func:`app.api.routers.feedback.submit_rpe` **刻意不做过期**
    （它 docstring 的「刻意不做」第 2 条），故一节早先的课完全可以在一节晚近的课
    **之后**才被提交。那时按 ``submitted_at`` 排会把 ``S0`` 插进 ``[S1, S2, S3]`` 的
    **前面**，锚点从 ``S3`` 移到 ``S2`` → 键变 → 同一次「连续 ≥ 9」触发第二次落库。
    故排序键取 ``(session_date, period)``（那才是「连续 3 次**课堂**快评」的时间轴），
    ``submitted_at`` 与 ``id`` 只作同节课内的 tie-breaker。
    ⚠️ 守卫是 ``test_a_late_submission_does_not_move_the_window_key_anchor``。

    **只取 8 个小列、不取 ORM 实体**：整学期 500 人 ×32 节课是 16 000 行，
    而本模块只要 ``rpe`` / ``class_session_id`` / 课次时间三件事。口径照
    :func:`app.pipeline.prescription_stage._previous_prescriptions` 的 ``load_only``
    （那里的 docstring 逐字给了实测：整行加载会让整学期回放多花约 30 s）。
    """
    return session.execute(
        select(
            RpeRecord.student_id,
            RpeRecord.class_session_id,
            RpeRecord.rpe,
            RpeRecord.submitted_at,
            RpeRecord.id,
            ClassSession.session_date,
            ClassSession.period,
            ClassSession.course_section_id,
        )
        .join(ClassSession, ClassSession.id == RpeRecord.class_session_id)
        .join(CourseSection, CourseSection.id == ClassSession.course_section_id)
        .where(CourseSection.semester_id == semester_id)
        .order_by(
            RpeRecord.student_id,
            ClassSession.session_date,
            ClassSession.period,
            RpeRecord.submitted_at,
            RpeRecord.id,
        )
    ).all()


def _rpe_streak(rows: Sequence, rpe_min: float) -> "tuple[int, tuple]":
    """末尾那段连续 ``rpe >= rpe_min`` 的长度，与那几次的 ``class_session_id``（**升序**）。

    ⚠️ **``rpe_min`` 在这里被消费**（P7-A3 第 3 条）：它是 ``alert_rules.yaml`` 的
    ``RED_RPE_SUSTAINED.params.rpe_min``（那个 9），而 domain **读不到它**——
    domain 拿到的 ``rpe_streak`` 是**已经算好的次数**（:func:`app.domain.alerts._rpe_streak`
    的 docstring 逐字交代了这件事，并把消费者点名给本模块）。不读它就是死配置。

    ⚠️ 入参 ``rows`` 必须**已经按课次时间升序**（:func:`_rpe_rows` 的 ``ORDER BY``），
    故本函数反向扫描、再把结果翻回来，返回的元组因此也是升序。
    """
    ids: list = []
    for row in reversed(rows):
        if row.rpe >= rpe_min:
            ids.append(row.class_session_id)
        else:
            break
    ids.reverse()
    return len(ids), tuple(ids)


def _mini_test_improved(minis: Sequence, improve_pct: float) -> bool:
    """最近两次二次小测里，**任一指标**改善 ≥ ``improve_pct``（spec §8.2 口径表 #4）。

    ⚠️ **``improve_pct`` 在这里被消费**（P7-A3 第 3 条）：那个 3% 住在
    ``GREEN_MASTERY.params``，而 domain 拿到的是**已经算好的** ``mini_test_improved``
    布尔值（:func:`app.domain.alerts._mastery` 的 docstring 逐字把消费者点名给本模块）。
    ⚠️ 它与下降阈值 5% **刻意不对称**（口径表原文「正向激励应更宽松」），
    故**不要**去 ``RED_MINITEST_DROP.params.drop_pct`` 里取这个数。

    三个指标各有一个方向（``shuttle_20m_s`` 是**秒数越少越好**，另两个越多越好）：

    ====================  ========  =======================================
    列                     方向      改善的算式
    ====================  ========  =======================================
    ``normalized_score``   越高越好  ``(new - old) / old >= improve_pct``
    ``squat_30s_count``    越高越好  ``(new - old) / old >= improve_pct``
    ``shuttle_20m_s``      越低越好  ``(old - new) / old >= improve_pct``
    ====================  ========  =======================================

    ⚠️ **分母一律是 ``abs(old)``**，且 ``old`` 为 0 / ``None`` 时那一项**跳过**：
    ``old = 0`` 会让改善率无定义（除零），而把它当成「无穷大改善」会让一个
    从 0 次深蹲做到 1 次的学生每周拿一张绿牌。
    ⚠️ **两次里任一对可比指标达标就算改善**（spec 逐字「任一指标」），
    故不是「综合分涨了」这一个判据——``normalized_score`` 今天在演示数据里是
    近似值（:class:`MiniTest` 的 docstring 逐字交代了「班内百分位反查」还没实现），
    只靠它会让绿牌取决于一个未定稿的算法。

    **少于两次小测 → ``False``**（不是 ``None``）：``GREEN_MASTERY`` 是
    ``completion_rate >= 1.0`` **AND** ``mini_test_improved``，一个从没测过的学生
    不该拿绿牌；而「判不了」的留痕由 ``RED_MINITEST_DROP`` 的
    ``insufficient_points`` 那一档负责（它才是需要 3 个数据点的那一条）。
    """
    if len(minis) < 2:
        return False
    older, newer = minis[-2], minis[-1]
    for old, new, lower_is_better in (
        (older.normalized_score, newer.normalized_score, False),
        (older.squat_30s_count, newer.squat_30s_count, False),
        (older.shuttle_20m_s, newer.shuttle_20m_s, True),
    ):
        if old is None or new is None or not old:
            continue
        delta = (old - new) if lower_is_better else (new - old)
        if delta / abs(old) >= improve_pct:
            return True
    return False


def _counted_checkin_days(logs: Sequence) -> set:
    """**计入完成率**的那些打卡日（spec §8.1 的四个条件，与完成率端点逐字同口径）。

    ==========================  ==================================================
    条件                         出处
    ==========================  ==================================================
    ``completed``                spec §8.1「学生自报今天练了没有」
    ``not late``                 spec §8.1 逐字「22:00 后提交仍入库但标记 late = true，
                                 **不计入当日完成**」
    ``not is_rest_day``          spec §8.1 折中方案「非训练日一键『今日休息』；
                                 但完成率只按处方训练日计算」
    ``submitted_at.date() ==     派单决定 ②「补卡入库但不计入完成率」
    log_date``                   （⚠️ 它**需要** ``submitted_at`` 那一列，
                                 那一列正是 Task 5 给 ``training_log`` 补的）
    ==========================  ==================================================

    ⚠️⚠️ **这四个条件有第二个所有者**：:func:`app.api.routers.feedback.completion_rate`
    的分子。两处并存而**不合并**，理由与处置照
    :class:`app.domain.alerts.AlertLevel` 与 :attr:`Alert.LEVELS` 的先例——
    那一处住在 ``app/api/``（本模块反向 import 不到），而它是端点响应体的算法本体、
    抽出来会让端点读不懂。故由
    ``tests/pipeline/test_alert_stage.py`` 的
    ``test_the_completion_rate_numerator_uses_the_same_four_conditions_as_the_endpoint``
    把两侧钉成逐字相等：四个条件各造一行违例，断言 ``completion_rate`` 仍是 ``0.0``
    （于是 ``GREEN_MASTERY`` 不触发）。⚠️ **改其中一处而不改另一处，那条测试会红**。

    ⚠️ 与 :func:`_reported_checkin_days` **刻意是两套口径**，理由逐字见那一个的 docstring。
    """
    return {
        log.log_date
        for log in logs
        if log.completed
        and not log.late
        and not log.is_rest_day
        and log.submitted_at.date() == log.log_date
    }


def _reported_checkin_days(logs: Sequence) -> set:
    """**学生自己报过练了**的那些日（``completed`` 且不是休息日打卡）。

    ⚠️ **它与 :func:`_counted_checkin_days` 刻意不同**，而这不是随手写的第二套口径：

    * **完成率**（``GREEN_MASTERY`` 的判据）是 spec 逐字点名的「RCT 关键过程指标，
      必须严格」，故迟交与补卡都不算；
    * **打卡中断**（``YELLOW_CHECKIN_GAP`` 的判据）问的是另一件事——
      「这个学生是不是**失联**了」。一个 22:40 才交卡的学生并没有失联，
      给他推一条「你已经连续 2 天没打卡了」是一句**当面撒谎**的提醒
      （他知道自己交了），而那条提醒会自动发给学生本人（spec §8.2 逐字
      「**自动**发『补练提醒』，无需教师介入」），没有教师能拦下它。

    故中断这一档只看「有没有报过」，不看「报得及不及时」。
    ⚠️ 代价（硬规矩 #39）：一个天天迟交的学生完成率永远不达标（拿不到绿牌）、
    也永远不会被提醒补练——两套口径对他给出两个方向相反的结论。已登记为关切。
    """
    return {
        log.log_date for log in logs if log.completed and not log.is_rest_day
    }


def _student_signals(
    *,
    student_id: int,
    semester_id: int,
    week: int,
    rpe: Sequence,
    minis: Sequence,
    logs: Sequence,
    prescription: "Prescription | None",
    as_of: dt.date,
    rules: AlertRules,
    exercises: Mapping,
    session: Session,
) -> "tuple[StudentSignals, bool]":
    """一个学生的 11 个信号 + 「处方是否已到期」那一格。

    ⚠️ **返回一对**：``prescription_expired`` 不进 :class:`StudentSignals`
    （那 11 个字段是 Task 6 按硬规矩 #110 逐字段回问「这个值从哪个入参来」定下来的，
    **一个都不多**，加一个没有消费者的字段就是给下一个人一个会被误当成判据的东西）。
    它的消费者是 :func:`_write_auto_adjustment` 与 ``alert.trigger_snapshot`` 里的
    ``"prescription_expired": true`` 留痕。

    11 个字段逐个说来源：

    ==========================  ==================================================
    字段                          来源
    ==========================  ==================================================
    ``student_id`` / ``semester_id``  调用方的管道上下文
    ``week``                      :func:`semester_week_of`（**学期**周次）
    ``rpe_streak`` / ``rpe_session_ids``  :func:`_rpe_streak`（消费 ``rpe_min``）
    ``mini_test_scores`` / ``mini_test_ids``  本学期的 ``mini_test``，按 ``week`` 升序，
                                          **同序等长**（domain 的 ``_require_parallel`` 要它）
    ``checkin_gap_days`` / ``checkin_gap_end``  处方训练日 ∖ :func:`_reported_checkin_days`
    ``completion_rate``           处方训练日 ∩ :func:`_counted_checkin_days`
    ``mini_test_improved``        :func:`_mini_test_improved`（消费 ``improve_pct``）
    ==========================  ==================================================

    ------------------------------------------------------------------
    ``completion_rate`` 的三档 ``None``（「判不了」不得讲成「0%」）
    ------------------------------------------------------------------

    与 :func:`app.api.routers.feedback.completion_rate` 同一条纪律：

    ① 没有生效处方；② 有处方但 :func:`current_week` 返回 ``None``（已到期 = spec §5.2
    触发 3 该开火的那一天）；③ 那一周 ``paused``、或没有训练日、或**第一个训练日还没到**。
    三档一律 ``None``，于是 domain 会把它记成留痕（``missing: completion_rate``）
    而不是「完成度 0%」。

    ⚠️ **③ 的「还没到」是承重的**：不判它的话，周一早上跑批时本周三天训练一天都没发生，
    ``completion_rate`` 会是 ``0.0``——那是「判不了」被讲成了「一天都没练」。

    ------------------------------------------------------------------
    ``completion_rate`` 夹在 ``[0, 1]``（P7-A3 第 4 条）
    ------------------------------------------------------------------

    ⚠️ Task 6 顶回 6 那条等价性论证（``>= 1.0`` ≡ ``== 1.0``）**建立在比率不超过 1 之上**，
    越界会让它不再等价（一个 ``1.2`` 会触发而 ``==`` 不会）。故这里显式 ``min(1.0, …)``。
    ⚠️ **它今天不可达**（如实记录，硬规矩 #39）：分子是
    ``_counted_checkin_days(...) ∩ 本周训练日``，而分母就是「本周训练日」，
    故分子**结构上**不可能超过分母。仍写下这一格的理由是**它是那个交集的护栏**：
    谁哪天把交集去掉（例如改成「按学期周算分子、按处方周算分母」），
    比率就会越过 1，而 domain 的 ``>=`` 会静默开始与 spec 的「100%」不等价。
    守卫是 ``test_the_completion_rate_never_exceeds_one``（它造一个「在非训练日也打了卡」
    的学生，让交集**真的**做功）。
    """
    rpe_min = float(rules.params_of(RuleId.RED_RPE_SUSTAINED)["rpe_min"])
    improve_pct = float(rules.params_of(RuleId.GREEN_MASTERY)["improve_pct"])
    gap_days_needed = int(rules.params_of(RuleId.YELLOW_CHECKIN_GAP)["gap_days"])

    streak, streak_ids = _rpe_streak(rpe, rpe_min)
    scored = [row for row in minis if row.normalized_score is not None]

    expired = True
    completion_rate = None
    gap_days = 0
    gap_end = as_of.isoformat()

    rx_week = None
    if prescription is not None:
        rx_week = current_week(
            prescription.generated_on, as_of, prescription.microcycle_weeks
        )
        expired = rx_week is None

    if rx_week is not None:
        days, paused = training_days_of(
            session, prescription, rx_week, exercises=exercises
        )
        reported = _reported_checkin_days(logs)
        counted = _counted_checkin_days(logs)

        # --- 完成率：本处方周的训练日（含还没到的那些）当分母 -------------------
        if days and not paused and min(days) <= as_of:
            done = counted & days
            completion_rate = min(1.0, len(done) / len(days))

        # --- 中断：本处方周 + 上一周的训练日里，<= as_of 的那些，反向数连续未报 ---
        candidate = set(days)
        if rx_week > 1:
            previous_days, previous_paused = training_days_of(
                session, prescription, rx_week - 1, exercises=exercises
            )
            if not previous_paused:
                candidate |= previous_days
        expected = sorted(day for day in candidate if day <= as_of)
        missed: list = []
        for day in reversed(expected):
            if day in reported:
                break
            missed.append(day)
        missed.reverse()
        gap_days = len(missed)
        if gap_days >= gap_days_needed:
            # ⚠️ **锚在「凑满阈值那一天」**，不是中断的最后一天（本 Task 的口径决定，
            #    与 domain 给 RED_RPE_SUSTAINED 选 rpe_session_ids[streak-1] 是同一条判断）：
            #    中断每多一天就多一个 window_key 的话，一个 5 天的中断会落 4 条 alert
            #    ——那正是 Review Focus 第 3 条要防的形状，只是从 RPE 那一侧搬到了打卡这一侧。
            #    ⚠️ 于是它与 domain docstring 里「那段中断的**结束日**」的字面读法不同：
            #    字面读法（中断的最后一天）会让键天天变。理由与守卫逐字见报告。
            gap_end = missed[gap_days_needed - 1].isoformat()
        elif missed:
            gap_end = missed[-1].isoformat()

    return (
        StudentSignals(
            student_id=student_id,
            semester_id=semester_id,
            week=week,
            rpe_streak=streak,
            rpe_session_ids=streak_ids,
            mini_test_scores=tuple(row.normalized_score for row in scored),
            mini_test_ids=tuple(row.id for row in scored),
            checkin_gap_days=gap_days,
            checkin_gap_end=gap_end,
            completion_rate=completion_rate,
            mini_test_improved=_mini_test_improved(minis, improve_pct),
        ),
        expired,
    )


def _write_auto_adjustment(
    session: Session,
    *,
    prescription: Prescription,
    week: int,
    rule_id: RuleId,
    batch_id: int,
    created_at: dt.datetime,
) -> bool:
    """给一张处方的某一周写一条 ``source="auto"`` / ``factor=0.8`` 的调整，返回**是否新写**。

    spec §8.4「预警触发减量 20%」的落地点，也是 Plan 02 结案时逐字留给 Plan 03 的那件事
    （:attr:`WeeklyAdjustment.SOURCES` 的 ``"auto"`` 到今天为止没有生产写入方）。

    ------------------------------------------------------------------
    三个决定，各挡一个静默失效
    ------------------------------------------------------------------

    1. **先构造 :class:`~app.domain.prescription.weekly.WeeklyFactor` 值对象，再落库**
       （Plan 02 留给 Plan 03 的第 4 条）。``weekly_adjustment.factor`` 那一列**刻意没有
       CHECK**（P8-A6），故值对象的 ``__post_init__``（``(0, 2]``）是写入侧唯一的闸门。
       ⚠️ 少了它，一个 ``factor = 0.0`` 会静默落库，然后让学生端打开训练单时在
       :func:`~app.pipeline.prescription_stage.weekly_factors_of` 里抛 ``ValueError`` → 500
       （Plan 02 Task 8 的关切 1 逐字就是这个形状，而当时的裁定是「不能靠 docstring 传话」）。
       守卫是 ``test_the_auto_factor_passes_through_weekly_factor_validation``
       （把 :data:`AUTO_REDUCTION_FACTOR` 变异成 ``0.0`` → 那条红）。

    2. **裸 ``INSERT`` + 自己的 SAVEPOINT，让 DB 当去重的裁判**——⚠️ **刻意不用
       :func:`app.db.repo.upsert`**（派单逐字点名的坑）：``upsert`` 是「先 SELECT 再
       update/insert」，撞上 ``uq_weekly_adjustment_prescription_week_reason_source``
       时它**不抛异常**，而是走更新分支、把 ``factor`` / ``batch_id`` / ``created_at``
       三个非键列 ``setattr`` 到**已有的那一行**上并返回它。于是「一次本该被拒绝的重复
       写入」变成「静默改掉一条已经生效的调整」——而那条调整的 ``created_at`` 正是
       :func:`app.pipeline.prescription_stage.weekly_factors_of` 的排序键，改它会让
       同一周上多条调整的**相乘顺序**跟着变（浮点尾数因此漂，教师端显示的系数也漂）。
       裸 INSERT 结构上不可能更新任何行：撞键就是 ``IntegrityError``。

    3. **``IntegrityError`` 只回滚它自己的 SAVEPOINT**，然后返回 ``False`` 继续下一个人。
       ⚠️ **不能裸 ``session.rollback()``**：本阶段跑在 :func:`app.pipeline.daily.run_daily`
       的 ``session.begin_nested()`` 里，裸 rollback 会把**整批**（分层 + 快照 + 派生 +
       处方 + 本批已写的预警）一起撤销，而调用方以为只是这一条调整没写进去。
       SAVEPOINT 嵌套是 SQLAlchemy 支持的（``begin_nested()`` 可以套在 ``begin_nested()`` 里）。

    ------------------------------------------------------------------
    ``reason`` 写的是**裸的 rule_id**，不带版本号
    ------------------------------------------------------------------

    ⚠️ 这是对 :mod:`app.domain.alerts` 模块 docstring 那一句
    （「``version`` ……Task 7 把它写进 ``weekly_adjustment`` 的 ``auto`` 来源留痕」）的
    **一处有意偏离**，理由是一条具体的失效：``reason`` 是那条四列唯一约束的**一列**，
    把版本号拼进去（``"RED_RPE_SUSTAINED@v1.0"``）会让「专家升一次 YAML 版本号」
    等价于「同一周可以再减一次量」——于是 ``0.8 × 0.8 = 0.64``，
    而 Review Focus 第 3 条要防的连乘**从版本号那一侧回来了**。
    约束自己的注释也逐字警告过「``reason`` 是自由文本，改一个标点就绕过了本约束」。

    版本号因此落在 :attr:`Alert.trigger_snapshot` 的 ``alert_rules_version`` 键里
    （见 :func:`evaluate_alerts`）：预警行与调整行是**同一次触发**的两半
    （同一条规则、同一周、同一个学生），故「当时按哪一版阈值判的」仍然可以离线复核，
    而不必把版本塞进去重键。

    ------------------------------------------------------------------
    ``batch_id`` 的口径
    ------------------------------------------------------------------

    **管道生成的调整行带本批的 ``batch_id``**（:attr:`WeeklyAdjustment.batch_id` 的列注释
    与 :mod:`app.pipeline.prescription_stage` 的模块 docstring 各写了一遍，两处同一口径）。
    ⚠️ 代价一并继承：:func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 整批删，
    故重放那一天会连带删掉本批写的调整行——而那正是重放该有的样子
    （同一批输入 → 同一批输出）。
    """
    factor = WeeklyFactor(
        week=week,
        factor=AUTO_REDUCTION_FACTOR,
        reason=rule_id.value,
        source=AUTO_SOURCE,
    )
    try:
        # ⚠️ 进 SAVEPOINT 之前先 flush：begin_nested() 会把此前所有未落库的写入
        #    （本批刚 add 的 alert 与 notification）一并带进这个 SAVEPOINT，
        #    于是它们中间任何一条坏了都会被算到「调整撞键」这一档上。
        session.flush()
        with session.begin_nested():
            session.add(
                WeeklyAdjustment(
                    prescription_id=prescription.id,
                    batch_id=batch_id,
                    week=factor.week,
                    factor=factor.factor,
                    reason=factor.reason,
                    source=factor.source,
                    created_at=created_at,
                )
            )
            session.flush()
    except IntegrityError as exc:
        logger.info(
            "处方 %s 第 %s 周已经有一条 %s 的 %s 调整（%s），本次不重复写："
            "同一周同一原因同一来源只允许一条，否则本周训练单会把量连乘"
            "（uq_weekly_adjustment_prescription_week_reason_source 是这条的裁判）。"
            "底层错误：%s",
            prescription.id, week, AUTO_SOURCE, rule_id.value, factor.factor, exc.orig,
        )
        return False
    return True


def _notify(
    channel: NotificationChannel,
    session: Session,
    *,
    hit,
    alert_id: int,
    snapshot: Mapping,
    recipient_kind: str,
    recipient_id: int,
) -> None:
    """按级别决定「发不发、发给谁」，然后发一条站内消息（spec §8.2 / §8.3）。

    =========================  ==========  =====================================
    规则                        收件人      出处
    =========================  ==========  =====================================
    ``YELLOW_CHECKIN_GAP``      学生本人    spec §8.2 逐字「**自动**发『补练提醒』，
                                            无需教师介入」
    ``GREEN_MASTERY``           学生本人    spec §8.2「生成电子勋章记录」+ §8.3
                                            「在原型中落地为站内消息」
    ``YELLOW_CLASS_RPE_HIGH``   该班的教师  spec §8.2「教师端提示」
    两条 ``RED_*``              **不发**    spec §8.2 逐字「教师端弹『降量建议』→
                                            **教师点击** → 推送『减量 20%』」
    =========================  ==========  =====================================

    ⚠️ **两条红色规则刻意不自动推送**，而 ``weekly_adjustment`` 的 ``auto`` 行**是**
    自动写的（简报 Task 7「决定」第 3 条）：两者不是同一件事。减量是系统对
    「这个学生练得太苦」的**保护性动作**（spec §8.4），而推送是**告诉学生**这件事——
    后者要教师先看过一眼，因为教师可能知道一个系统不知道的理由（学生受伤了、
    这周月考），那时正确的处置是 ``ignore`` 而不是让学生收到一条「你的量减了 20%」。
    推送由 :mod:`app.api.routers.alerts` 的 ``reduce_20pct`` 那一档补上。
    """
    if hit.level is AlertLevel.RED:
        return
    if hit.rule_id is RuleId.YELLOW_CHECKIN_GAP:
        title = "补练提醒"
        body = (
            f"你已经连续 {snapshot['checkin_gap_days']} 个应打卡训练日没有打卡了。"
            f"训练计划里的休息日不算中断，所以这几天本来是该练的。"
            f"打开 H5 补一次训练，或者今天一键『今日休息』。"
        )
    elif hit.rule_id is RuleId.GREEN_MASTERY:
        title = "本周电子勋章"
        body = (
            f"本周训练完成度 100%，而且二次小测有指标在进步。"
            f"这一条已经记进你的电子勋章记录。"
        )
    else:
        title = "课堂 RPE 均值偏高"
        body = (
            f"教学班 {snapshot['student_count']} 名学生本周的课堂 RPE 均值是 "
            f"{snapshot['mean_rpe']:.2f}，高于阈值。"
            f"下一节课可以考虑降一档强度或延长组间休息。"
        )
    channel.send(
        session,
        recipient_kind=recipient_kind,
        recipient_id=recipient_id,
        title=title,
        body=body,
        alert_id=alert_id,
    )


def evaluate_alerts(
    session: Session,
    semester_id: int,
    batch_id: int,
    as_of: dt.date,
    *,
    rules: AlertRules,
    exercises: Mapping[str, ExerciseSpec],
    now: dt.datetime,
    channel: "NotificationChannel | None" = None,
) -> AlertReport:
    """为 ``as_of`` 那一天求 5 条预警规则，落库 + 发消息 + 写自动减量，返回计数报表。

    ------------------------------------------------------------------
    签名：比简报 Interfaces 多三个 keyword-only 形参
    ------------------------------------------------------------------

    简报写的是 ``(session, semester_id, batch_id, as_of, *, rules)``，而那个签名**跑不起来**，
    缺的三样各是一条 NOT NULL 列或一个既有纪律（本 Task 顶回的一处，逐条报告）：

    * ``now`` —— ``alert.triggered_at`` 与 ``notification.created_at`` 都是
      ``DateTime NOT NULL`` **且无缺省**（本仓全部表的统一约定：时钟由调用方注入，
      守卫是 ``tests/db/test_models.py`` 的
      ``test_the_plan03_tables_inject_the_clock_and_never_default_it``）。
      ``api`` 与 ``pipeline`` 都可以碰时钟，但**注入**才让测试可复现。
    * ``exercises`` —— :func:`~app.pipeline.prescription_stage.training_days_of` 要它，
      而 :mod:`app.pipeline.prescription_stage` 的既有纪律是「三份参考数据一律由
      调用方注入」（:func:`~app.pipeline.prescription_stage.generate_prescriptions` 就是），
      故本模块不自己调 ``refdata_prescription.exercises()`` 单例。
    * ``channel`` —— 可注入的通知通道，缺省 :class:`~app.notify.InAppChannel`。
      有它，测试可以断言「红色预警一条消息都不发」而不必去查 ``notification`` 表。

    ⚠️ **不 commit、不 rollback**：事务边界由 :mod:`app.pipeline.daily` 掌握
    （与 :func:`app.db.repo.upsert` / ``generate_prescriptions`` 同一条口径）。

    ------------------------------------------------------------------
    ``as_of`` 早于开学日 → 空报表 + 一条 warning
    ------------------------------------------------------------------

    :func:`app.pipeline.daily.run_daily` **不要求** ``business_date`` 落在
    ``semester_id`` 那个学期的区间内（它的 docstring 逐字写了这件事：``semester_id``
    是**运行记录**的归属、不是数据的归属）。而预警的 ``week`` 是学期周次，
    没有周次就没有 ``window_key``（``GREEN_MASTERY`` 与 ``YELLOW_CLASS_RPE_HIGH``
    的键就是 ``semester_id:week``）。故这一档**不抛**：它是一次合法的重放历史日期，
    只是那一天没有「本周」可言。留痕走一条 ``warning``。
    """
    _require_batch_in_semester(session, semester_id, batch_id)
    semester = session.get(Semester, semester_id)
    if semester is None:
        raise ValueError(
            f"semester 表里查无 id={semester_id}：alert.semester_id 是 NOT NULL 外键，"
            f"而且它是去重键 uq_alert_rule_subject_semester_window 的一列，"
            f"没有归属就写不进去"
        )
    week = semester_week_of(semester.start_date, as_of)
    if week is None:
        logger.warning(
            "业务日期 %s 早于学期 %s 的开学日 %s，故没有「本学期第几周」可言："
            "GREEN_MASTERY 与 YELLOW_CLASS_RPE_HIGH 的 window_key 就是 semester_id:week，"
            "没有周次就无从去重。本批不求值任何预警（alert_count = 0），"
            "而 0 在这一档的意思是「没跑」，不是「今天没有预警」",
            as_of.isoformat(), semester_id, semester.start_date.isoformat(),
        )
        return AlertReport(
            raised=0, deduped=0, by_level={}, adjustments_written=0, skipped={}, errors=0
        )

    sender = channel if channel is not None else InAppChannel(now=lambda: now)

    # --- 批级预取（4 次查询，不逐人查；理由见 _rpe_rows 的 docstring）----------
    rpe_by_student: dict = defaultdict(list)
    rpe_by_section: dict = defaultdict(list)
    week_start, week_end = semester_week_range(semester.start_date, week)
    for row in _rpe_rows(session, semester_id):
        rpe_by_student[row.student_id].append(row)
        if week_start <= row.session_date <= week_end:
            rpe_by_section[row.course_section_id].append(row)

    mini_by_student: dict = defaultdict(list)
    for row in session.scalars(
        select(MiniTest)
        .where(MiniTest.semester_id == semester_id)
        .order_by(MiniTest.student_id, MiniTest.week, MiniTest.id)
    ):
        mini_by_student[row.student_id].append(row)

    logs_by_student: dict = defaultdict(list)
    for row in session.scalars(
        select(TrainingLog).where(
            TrainingLog.log_date >= as_of - _CHECKIN_LOOKBACK,
            TrainingLog.log_date <= as_of,
        )
    ):
        logs_by_student[row.student_id].append(row)

    # ⚠️⚠️ **人群用的那一份打卡查询与上面那一份刻意不同窗口**（本 Task 的一个要点）：
    # 上面那一份按 :data:`_CHECKIN_LOOKBACK` 收窄，因为它喂的是**信号**（本周完成率、
    # 近两周的中断）；本份**只按学期起点**收窄，因为它喂的是**人群**。
    # 用同一个窗口的话会漏掉最该被提醒的那一类人：一个连续失联 4 周的学生，
    # 在 3 周的回看窗口里**一行 ``training_log`` 都没有**，于是他不在人群里、
    # 于是 ``YELLOW_CHECKIN_GAP`` 对他**永远不触发**——而那条规则存在的理由
    # 逐字就是「打卡中断」（spec §8.2 判据表第 3 行）。
    # ⚠️ 反过来，人群**不能**不加窗口：``training_log`` 是逐日增长的表，
    # 全表 distinct 会随学期线性变贵。按 ``semester.start_date`` 收窄是那个平衡点。
    onboarded = set(
        session.scalars(
            select(TrainingLog.student_id)
            .where(TrainingLog.log_date >= semester.start_date)
            .distinct()
        )
    )

    prescriptions = _previous_prescriptions(session, as_of)

    raised = deduped = adjustments = errors = 0
    by_level: dict = {}
    skipped: dict = {}

    def _count_skipped(traces: Mapping) -> None:
        for rule_id in traces:
            skipped[rule_id.value] = skipped.get(rule_id.value, 0) + 1

    def _persist(hit, *, student_id, course_section_id, extra) -> "Alert | None":
        """落一行 ``alert``；撞上已有的那一行就返回 ``None``（= deduped）。

        ⚠️ **先 SELECT 后 INSERT，不走 :func:`app.db.repo.upsert`**：upsert 的更新分支
        会把一条已经 ``handled`` / ``ignored`` 的预警**静默改回** ``pending``、
        并把 ``triggered_at`` 与 ``trigger_snapshot`` 一起换掉——教师处置过的痕迹
        就此消失，而 Review Focus 第 3 条要的恰恰是「处置过的预警留在库里当痕迹」。
        """
        nonlocal raised, deduped
        existing = session.scalar(
            select(Alert).where(
                Alert.rule_id == hit.rule_id.value,
                Alert.subject_key == hit.subject_key,
                Alert.semester_id == semester_id,
                Alert.window_key == hit.window_key,
            )
        )
        if existing is not None:
            deduped += 1
            logger.debug(
                "规则 %s 的主语 %s 在窗口 %s 上已经有一条预警（id=%s, status=%s），"
                "本次不重复落库、不重复推送、不重复减量",
                hit.rule_id.value, hit.subject_key, hit.window_key,
                existing.id, existing.status,
            )
            return None
        snapshot = {**hit.snapshot, "alert_rules_version": rules.version, **extra}
        alert = Alert(
            student_id=student_id,
            course_section_id=course_section_id,
            semester_id=semester_id,
            subject_key=hit.subject_key,
            level=hit.level.value,
            rule_id=hit.rule_id.value,
            trigger_snapshot=snapshot,
            triggered_at=now,
            status=ALERT_PENDING,
            batch_id=batch_id,
            window_key=hit.window_key,
        )
        session.add(alert)
        session.flush()
        raised += 1
        by_level[hit.level.value] = by_level.get(hit.level.value, 0) + 1
        return alert

    # --- 学生级：人群 = 在三源里留过痕的学生（理由见模块 docstring）-------------
    population = sorted(
        set(rpe_by_student) | set(mini_by_student) | onboarded
    )
    for student_id in population:
        minis = mini_by_student.get(student_id, [])
        try:
            signals, expired = _student_signals(
                student_id=student_id,
                semester_id=semester_id,
                week=week,
                rpe=rpe_by_student.get(student_id, []),
                minis=minis,
                logs=logs_by_student.get(student_id, []),
                prescription=prescriptions.get(student_id),
                as_of=as_of,
                rules=rules,
                exercises=exercises,
                session=session,
            )
            # ⚠️ 先 evaluate 后 skip_traces：前者会跑 _require_parallel（契约违例当场
            #    ValueError），后者刻意不跑（它的 docstring 逐字交代了这个顺序要求）。
            hits = evaluate_student(signals, rules)
            traces = student_skip_traces(signals, rules)
        except Exception as exc:  # noqa: BLE001 - 按学生捕获，见模块 docstring
            errors += 1
            logger.warning(
                "学生 %s 在 %s 的预警求值失败：%s: %s —— 跳过这一个人，整批不回滚。"
                "这一档要人工过目（它通常是三源数据里有脏行，或处方训练包装配不出来）",
                student_id, as_of.isoformat(), type(exc).__name__, exc,
            )
            continue

        _count_skipped(traces)
        prescription = prescriptions.get(student_id)
        for hit in hits:
            alert = _persist(
                hit,
                student_id=student_id,
                course_section_id=None,
                extra={
                    # ⚠️ 两格留痕都是「处方到期」那一档的：到期时**不写**减量调整
                    #    （给一张已到期的处方写「本周减量」没有意义，而 spec §5.2 的
                    #    触发 3 会在同一天生成新处方），只把这件事记在快照里。
                    "prescription_expired": expired,
                    "prescription_id": None if prescription is None else prescription.id,
                    "semester_week": week,
                },
            )
            if alert is None:
                continue
            if hit.level is AlertLevel.RED:
                rx_week = None
                if prescription is not None:
                    rx_week = current_week(
                        prescription.generated_on, as_of, prescription.microcycle_weeks
                    )
                if rx_week is None:
                    logger.warning(
                        "学生 %s 触发了 %s（红色）但没有可减量的处方周"
                        "（处方不存在，或 current_week 返回 None = 已到期）："
                        "不写 weekly_adjustment，只在 alert.trigger_snapshot 里留痕 "
                        "prescription_expired=true。这一档通常意味着该换处方了"
                        "（spec §5.2 触发 3），而不是「这个学生不该减量」",
                        student_id, hit.rule_id.value,
                    )
                elif _write_auto_adjustment(
                    session,
                    prescription=prescription,
                    week=rx_week,
                    rule_id=hit.rule_id,
                    batch_id=batch_id,
                    created_at=now,
                ):
                    adjustments += 1
            _notify(
                sender,
                session,
                hit=hit,
                alert_id=alert.id,
                snapshot=alert.trigger_snapshot,
                recipient_kind=RECIPIENT_STUDENT,
                recipient_id=student_id,
            )

    # --- 班级级：全量遍历本学期的教学班（理由见模块 docstring 末段）-------------
    for section_id, teacher_id in session.execute(
        select(CourseSection.id, CourseSection.teacher_id)
        .where(CourseSection.semester_id == semester_id)
        .order_by(CourseSection.id)
    ).all():
        rows = rpe_by_section.get(section_id, [])
        signals = ClassSignals(
            course_section_id=section_id,
            semester_id=semester_id,
            week=week,
            mean_rpe=(sum(row.rpe for row in rows) / len(rows)) if rows else None,
            student_count=len({row.student_id for row in rows}),
        )
        try:
            hits = evaluate_class(signals, rules)
            traces = class_skip_traces(signals, rules)
        except Exception as exc:  # noqa: BLE001 - 按班捕获，口径同上
            errors += 1
            logger.warning(
                "教学班 %s 在 %s 的预警求值失败：%s: %s —— 跳过这一个班，整批不回滚",
                section_id, as_of.isoformat(), type(exc).__name__, exc,
            )
            continue

        _count_skipped(traces)
        for hit in hits:
            alert = _persist(
                hit,
                student_id=None,
                course_section_id=section_id,
                extra={"semester_week": week},
            )
            if alert is None:
                continue
            _notify(
                sender,
                session,
                hit=hit,
                alert_id=alert.id,
                snapshot=alert.trigger_snapshot,
                recipient_kind=RECIPIENT_TEACHER,
                recipient_id=teacher_id,
            )

    session.flush()
    report = AlertReport(
        raised=raised,
        deduped=deduped,
        by_level=by_level,
        adjustments_written=adjustments,
        skipped=skipped,
        errors=errors,
    )
    # 每批一条日志（噪声取舍照 prescription_stage 的「日志的分档」那一节）。
    # ⚠️ skipped 那一格是 P7-A3 第 1 条要求的消费者：不留这一行，
    #    「这个学生这周为什么没有预警」就仍然无从回答。
    logger.info(
        "学期 %s 批次 %s（%s，第 %s 周）预警阶段：新落库 %d 条、去重 %d 条、"
        "级别分布 %s、自动减量 %d 条、求值失败 %d 人/班；「判不了」的留痕 %s"
        "（阈值版本 %s）",
        semester_id, batch_id, as_of.isoformat(), week,
        report.raised, report.deduped, dict(sorted(report.by_level.items())),
        report.adjustments_written, report.errors,
        dict(sorted(report.skipped.items())), rules.version,
    )
    return report
