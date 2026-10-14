"""教师大屏（spec §9.1）、学生端首页（§9.2）与教师端读单个学生的**六个读端点**
（Plan 03 Task 8 建四个；Plan 04 Task 3 的小修波加第五个，见 :func:`student_notifications`；
Plan 04 收尾波加第六个，见 :func:`teacher_student_home`）。

==============================================================  ======  ==========================
路径                                                             身份     响应模型
==============================================================  ======  ==========================
``GET /api/dashboard/class/{course_section_id}``                 教师     :class:`ClassDashboardRead`
``GET /api/dashboard/weekly-class-report/{course_section_id}``   教师     :class:`WeeklyClassReportRead`
``GET /api/students/{student_id}/home``                          学生     :class:`StudentHomeRead`
``GET /api/students/{student_id}/notifications``                 学生     ``list[NotificationRead]``
``GET /api/teacher/students/{student_id}/weekly-sheet``          教师     :class:`WeeklySheetRead`
``GET /api/teacher/students/{student_id}/home``                  教师     :class:`StudentHomeRead`
==============================================================  ======  ==========================

⚠️ 最后两行是**同一份数据的两个身份入口**（与第 3 行成对）：响应体逐字相同，
因为函数体各被抽成了一个共用的私有函数（:func:`_student_home_response` /
:func:`app.api.routers.prescription._weekly_sheet_response`）——**不是复制粘贴第二份**。

----------------------------------------------------------------------------
⚠️⚠️ 本模块**一条聚合都不算、一条 SQL 都不为自己写**
----------------------------------------------------------------------------

大屏的四块与周报的六项是**同一批聚合量**，故：

* 取数走 :func:`app.pipeline.report_stage.class_snapshot`
  （「怎么读一个班的一周」在全仓的唯一编排）；
* 聚合走 :func:`app.pipeline.report_stage.aggregates_of`
  （「怎么调 :mod:`app.domain.report` 那九个纯函数」的唯一编排）。

失效形态很具体：大屏是**实时**刷新的、周报是**周日存下来的**，两条路径若各自读一遍库，
教师就会看到大屏写「人均 RPE 6.9」而同一周的周报写「7.1」，而他无从判断哪一个是真的。
守卫是 ``tests/api/test_dashboard.py`` 的
``test_the_dashboard_agrees_with_the_stored_report_on_the_same_sunday``
（同一个周日、同一个班，两个端点的六个共有键**逐字相等**）。

⚠️ 而本模块**自己**只写五段查询，各有一个理由（都不是聚合）：

1. ``weekly_class_report`` 那一行的查找（它读的是**存下来的**周报，不是现算的）；
2. 学生首页的「当前分层 + 可解释性」（:func:`_stratification_payload`，逐人不是逐班）；
3. 学生首页的「待办卡片」（已发起快评而这个学生还没交的课）；
4. 学生首页的「未读通知数」与「勋章数」（两个 COUNT）；
5. 学生消息中心的「发给他的全部通知」（:func:`_student_notifications`）。
   ⚠️ 第 4 与第 5 段**共用同一个筛选条件**——那一个函数就是它的唯一住址，
   理由逐字见它的 docstring（两个端点各写一遍的失效形态是「首页角标说 1 条未读、
   消息中心列出来 3 条」，而两处各自的测试都还是绿的）。

----------------------------------------------------------------------------
⚠️ include 顺序：本 router **必须**排在 :mod:`.catalog` 之前
----------------------------------------------------------------------------

:mod:`app.api.routers` 的模块 docstring 逐字写了这条纪律（「特例一律在泛型之前」）。
⚠️ 本 Task 实测：``/api/dashboard/…`` 与 ``/api/teacher/students/…`` 与 23 个资源的
五个端点**没有一个同形**（``dashboard`` / ``teacher`` 都不是资源路径的第一段），
而 ``/api/students/{student_id}/home`` 是三段、泛型的 ``/api/students/{student_id}``
是两段，故也不同形。⚠️ 同一条对 Plan 04 加的
``/api/students/{student_id}/notifications`` 也成立（三段；而 ``notifications``
那个资源自己注册的是 ``/api/notifications`` 与 ``/api/notifications/{notification_id}``，
两者前缀都不同）。⚠️ 于是顺序对本 router **今天不承重**——但它仍然排在
``catalog`` 之前，因为「一条不需要逐个 router 去论证『它同形吗』的规则才是能执行的规则」
（那句话逐字写在 :data:`app.api.routers.api_router` 的注释里）。

----------------------------------------------------------------------------
身份与作用域（计划 Review Focus 第 1 条：越权访问）
----------------------------------------------------------------------------

* **四个教师侧**：``X-Teacher-Staff-No`` + :func:`app.api.deps.require_teaches_section`
  （班级那两个）/ :func:`app.api.deps.require_teaches_student`（读单个学生那两个：
  ``weekly-sheet`` 与 ``home``）。
  ⚠️ **任教关系是 Plan 03 Task 8 建的**（简报 P8-A5 点名的那条链：
  ``enrollment`` + ``course_section.teacher_id``），它**只挂在读的一侧**；
  三个写入端点（教师覆盖 / 手动重生成 / 预警处置）今天仍只过
  :func:`app.api.deps.require_staff`（在册）——如实记录，已登记为关切。
* **两个学生侧**：``X-Student-Id`` + :func:`app.api.deps.require_scope`
  （首页与消息中心）。⚠️ 两处都是 **403** ``forbidden``、不是 404：
  「这个学号不在册」与「你在读别人的数据」刻意同形（理由逐字见那一个函数）。
* 六个都挂 ``dependencies=[Security(...)]``（P4-A5），故那两个请求头在
  ``/openapi.json`` 的 ``components.securitySchemes`` 里各有一格、Swagger 的
  「Authorize」弹窗里填得进去。⚠️ **判定不在 ``Security`` 上**（它 ``auto_error=False``、
  只负责声明），仍在 :func:`current_student` / :func:`current_teacher`，
  故「缺头」的码仍是本仓既有的 **401**。
  ⚠️ 连带：``tests/api/test_prescription_api.py`` 那份 ``expected`` 清单要**跟着长**
  （那条守卫的 docstring 逐字写着「每加一个带身份的特例端点都要回来加一行——
  这是**有意的**」）；本模块每个带身份的端点在那份清单里各占一行，而**每一行为什么挂
  哪一个头**的理由逐字写在对应那个端点函数自己的 docstring 首节（不在本处汇总）。
  ⚠️⚠️ **而本处刻意不再复述任何计数**（待清扫波删掉了此前逐波追加的那一串流水账：
  ``expected`` 的项数、「挂 ``security`` 的操作数」、``/api/`` 的路径模板 / 操作 /
  GET / 匿名 GET 的数）。那串账**过期过三次**，而硬规矩 #111 逐字是「凡是能从别处
  读出来的数，一律视为过期」—— **复述就是第二个所有者**。要读那些数请去机器口径
  的住址：端点族一律 ``app.openapi()["paths"]``（⚠️ **不是** ``len(app.routes)``
  ——FastAPI 0.141.1 的 ``include_router`` 是惰性的，按它数会假绿），
  ``expected`` 的项数由那条守卫自己数，前端那一侧的反查住在
  ``frontend/scripts/smoke.mjs`` 第 12 步。

----------------------------------------------------------------------------
``week`` / ``as_of``：由查询参数传，缺省取服务端当天与它所属的学期周
----------------------------------------------------------------------------

``api`` 是可以碰时钟的那一层，而 domain 与 pipeline 的纯函数一律要日期由调用方注入。
缺省那一档由 :func:`app.api.routers.prescription._business_day` 单点持有
（**不写第二份**「今天是什么日子」），学期周次由
:func:`app.pipeline.alert_stage.semester_week_of` 折算（同一个所有者）。

⚠️ **代价（硬规矩 #39）**：缺省那一档让「今天」进了行为，故依赖它的测试不可复现。
对策与 Task 4 逐字相同：**测试一律显式传 ``as_of`` / ``week``**，
缺省那一档只由一条测试看着（``test_as_of_defaults_to_the_server_clock``）。
"""
import datetime as dt

from fastapi import APIRouter, Depends, Query, Response, Security
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ⚠️ 复用 Task 3 那个私有的 404 助手（与 Task 4 / 5 / 7 同一条处置）：
#    「主键查无此行」这件事在全仓只应该有一种说法。
from app.api.crud import _get_or_404
from app.api.deps import (
    ADMIN_ROLE,
    STUDENT_ID_SCHEME,
    TEACHER_STAFF_NO_SCHEME,
    current_student,
    current_teacher,
    get_db,
    require_scope,
    require_staff,
    require_teaches_section,
    require_teaches_student,
    taught_section_ids,
    teacher_id_of,
)
from app.api.errors import error_response

# ⚠️ 复用 Plan 06 Task 10 抽出来的那一份投影（教师端读单个学生的 normalized 三格）。
#    **不抄第二份**：那三格里的 ``composite`` 是 spec §8.1 的算式结果，而算式在全仓
#    只有一个住址（``app/domain/report.py``，后端有 AST 守卫数定义份数）；投影一旦有
#    两份，``/normalized/me`` 与教师侧变体就会**静默**给出两个不同的综合分，
#    而两侧各自的测试都还是绿的。⚠️ 先例逐字是下面那一个 import
#    （``dashboard`` 从 ``prescription`` 取私有的 ``_weekly_sheet_response``）。
from app.api.routers.feedback import _enrolled_sections, _normalized_self_body

# ⚠️ 复用 Task 4 那两个私有的 api 层助手，**不写第二份**：``_business_day`` 是
#    「今天是什么日子」在 api 层的唯一所有者，``_weekly_sheet_response`` 是
#    「某个学生在某一天的本周训练单」的唯一所有者（Task 8 从 weekly_sheet 的函数体
#    抽出来的，理由逐字见它的 docstring）。
from app.api.routers.prescription import _business_day, _weekly_sheet_response
from app.api.schemas.alerts import NotificationRead, WeeklyClassReportRead

# ⚠️ 教师端读单个学生的 normalized 三格**复用**学生侧那一个响应模型（同一份数据的
#    同一个契约，两个端点在 /openapi.json 里因此指向同一个 schema，
#    与下面 ``WeeklySheetRead`` / ``StudentHomeRead`` 两格逐字同一条处置）。
from app.api.schemas.feedback import NormalizedSelfRead
# ⚠️ 教师端读单个学生的训练单**复用**学生侧那一个响应模型（同一份数据的同一个契约，
#    两个端点在 /openapi.json 里因此指向同一个 schema）。
from app.api.schemas.prescription import WeeklySheetRead
from app.api.schemas.dashboard import (
    ClassDashboardRead,
    ScreenThresholdsRead,
    StudentHomeRead,
    ThresholdLinesRead,
)

# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：这几张表**都不在** app.db.models 的
#    公有导入面上，写 models.ClassSession 会当场 AttributeError。
from app.db.models.derived import StratificationResult
from app.db.models.feedback import (
    Alert,
    ClassSession,
    Notification,
    RpeRecord,
    WeeklyClassReport,
)
from app.db.models.organisation import CourseSection, Enrollment, Semester

# ⚠️ ``recipient_kind`` 那一档的字面量**不在本模块写第二遍**：``app.notify`` 是它的
#    所有者（:data:`app.notify.RECIPIENT_STUDENT` 由 :func:`app.notify._vocabulary`
#    对着 ``Notification.RECIPIENT_KINDS`` 校验过），而本模块此前在
#    :func:`student_home` 里裸写了 ``"student"``——:func:`_student_notifications`
#    抽出来之后，那个字面量在本模块只剩这一处 import。
from app.notify import RECIPIENT_STUDENT

# ⚠️⚠️ **本模块同时用到两个都叫 ``RuleId`` 的枚举，它们是两套完全不同的词表**：
#    * ``app.domain.alerts.RuleId`` = **5 条预警规则**（``RED_RPE_SUSTAINED`` …），
#      值域的所有者是 ``data/alert_rules.yaml``；
#    * ``app.domain.stratify.RuleId`` = **spec §6.2 决策表的 9 条分层规则**
#      （``Z0`` / ``R1`` / ``R2`` / ``Y1..Y4`` / ``G1``），值域的所有者是
#      ``app.domain.stratify.RULE_ORDER``。
#    后者以 ``StratRuleId`` 的名字进来，故本模块里裸写的 ``RuleId`` **一律是预警那一套**
#    （``_threshold_lines`` 的两条、勋章那一条 ``GREEN_MASTERY``）。
#    ``stratification_result.hit_rules`` 存的是**分层**那一套（逗号连接），
#    故 :func:`_stratification_payload` 只用 ``StratRuleId`` 重建它。
from app.domain.alerts import RuleId
from app.domain.derive import BodyCompFlag, DerivedResult, Trend, WeaknessResult
from app.domain.indicators import ScoredItem, Sex
from app.domain.report import SCREEN_GAP_DAYS, SCREEN_RPE_MAX
from app.domain.stratify import Layer, StratResult, explain
from app.domain.stratify import RuleId as StratRuleId

# ⚠️ 三样东西一律从 pipeline 层 import（``api → pipeline`` 是许可方向），不抄第二份：
#    * ``class_snapshot`` / ``aggregates_of`` / ``new_cache`` 是「怎么读一个班的一周」
#      与「怎么调 domain 那九个纯函数」的两个唯一编排（模块 docstring 第一节）；
#    * ``semester_week_of`` / ``semester_week_range`` 是学期周次的两个方向；
#    * ``current_semester_of`` 是「哪一个是本学年」的唯一所有者
#      （优先 is_current、退化到「包含 as_of 的那个」）。
from app.pipeline.alert_stage import semester_week_of, semester_week_range
from app.pipeline.percentile_stage import current_semester_of
from app.pipeline.report_stage import aggregates_of, class_snapshot, new_cache
from app.refdata_alerts import alert_rules
from app.refdata_prescription import exercises as exercise_library

__all__ = ["NO_WEEKLY_REPORT", "router"]

#: 「这个班这一周还没有周报」的 ``code``（404）。
#:
#: ⚠️ 它**不是**故障：周报只在**周日**生成（spec §8.5 逐字），故周中去读本周的
#: 周报必然 404。前端应把这一档渲染成「本周的周报周日晚上生成，先看大屏」，
#: 而不是一条错误横幅。⚠️ 用 :func:`app.api.errors.error_response` 直接造响应
#: 而不是 ``raise HTTPException(404)``：后者的 ``code`` 会被折成通用的 ``not_found``，
#: 而前端要按 ``no_weekly_report`` 分支（口径逐字同
#: :data:`app.api.routers.prescription.NO_ACTIVE_PRESCRIPTION`）。
NO_WEEKLY_REPORT = "no_weekly_report"

router = APIRouter()


def _threshold_lines() -> ThresholdLinesRead:
    """spec §9.1 第 ② 块要画的那两条阈值线，**现读** ``data/alert_rules.yaml``。

    ⚠️ 一个字面量都不写在这里：那份 YAML 是预警阈值的唯一所有者（spec §4.4 逐字
    「改阈值应走版本控制与评审」），抄一份进来会让专家改完 YAML 之后
    大屏上的线**静默留在旧值**——而线画错了看不出来（它只是画在了另一个高度）。
    """
    rules = alert_rules()
    return ThresholdLinesRead(
        class_mean_max=float(
            rules.params_of(RuleId.YELLOW_CLASS_RPE_HIGH)["mean_rpe_max"]
        ),
        sustained_min=float(rules.params_of(RuleId.RED_RPE_SUSTAINED)["rpe_min"]),
    )


@router.get(
    "/api/dashboard/class/{course_section_id}",
    tags=["dashboard"],
    response_model=ClassDashboardRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def class_dashboard(
    course_section_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    week: "int | None" = Query(
        default=None,
        description="学期周次（1-based）。缺省 = as_of 所属的那一周。"
                    "⚠️ 不校验上界：一个超出学期长度的周次是「那一周什么都没发生」，"
                    "不是一次非法请求（口径同 semester_week_of）",
    ),
    as_of: "dt.date | None" = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天。它同时是**水位线**："
                    "本端点读不到它之后的数据",
    ),
) -> dict:
    """**教师大屏整屏**（spec §9.1 的四块 + 顶栏那一行）。

    响应体的 ``blocks`` 就是 :func:`app.pipeline.report_stage.aggregates_of` 的
    **七个键**（① 分层饼图 + 周环比流动、② 人均 RPE 曲线、③ 进步榜 / 退步名单、
    ④ 异常名单，外加按层完成率、预警汇总与算法建议）。
    ⚠️ **顶栏的「预警角标」刻意不另给一个计数**：它等于
    ``blocks.alert_summary`` 里三档 ``pending`` 之和，另给一格就是第二个所有者。

    ⚠️ **spec §14 #11 的「两套并存」在响应体里是两个独立的键**：
    ``rpe_threshold_lines``（7 / 9，来自 ``alert_rules.yaml``，是**预警**的判据线）
    与 ``screen_thresholds``（3 天 / RPE > 8，来自 :mod:`app.domain.report`，
    是**大屏异常名单**的筛选阈值）。前端**不得**拿一个去画另一个。

    ``week`` 缺省时由 ``as_of`` 折算；⚠️ 而 ``as_of`` 早于开学日时
    :func:`~app.pipeline.alert_stage.semester_week_of` 返回 ``None``，
    那一档报 **422**（``ValueError`` 经 :mod:`app.api.errors` 折出来）而不是回一份
    全 0 的大屏：一天不属于任何学期周时，「本周」这个词没有指称。
    """
    require_teaches_section(session, staff_no, course_section_id)
    section = _get_or_404(session, CourseSection, course_section_id)
    semester = _get_or_404(session, Semester, section.semester_id)
    day = _business_day(as_of)
    resolved_week = semester_week_of(semester.start_date, day) if week is None else week
    if resolved_week is None:
        raise ValueError(
            f"业务日期 {day.isoformat()} 早于学期 {semester.name} 的开学日 "
            f"{semester.start_date.isoformat()}，故没有「本学期第几周」可言，"
            f"大屏的「本周」没有指称。请显式传 ?week=，或把 as_of 改到开学日之后"
        )
    snapshot = class_snapshot(
        session,
        semester_id=semester.id,
        course_section_id=course_section_id,
        week=resolved_week,
        as_of=day,
        exercises=exercise_library(),
        cache=new_cache(session, day),
    )
    return {
        "course_section_id": course_section_id,
        "semester_id": semester.id,
        "semester_name": semester.name,
        "course_section_name": section.name,
        "week": resolved_week,
        "as_of": day,
        "watermark": snapshot.watermark,
        "week_start": snapshot.week_start,
        "roster_size": len(snapshot.roster),
        "blocks": aggregates_of(snapshot),
        "rpe_threshold_lines": _threshold_lines(),
        "screen_thresholds": ScreenThresholdsRead(
            gap_days=SCREEN_GAP_DAYS, rpe_max=SCREEN_RPE_MAX
        ),
    }


@router.get(
    "/api/dashboard/weekly-class-report/{course_section_id}",
    tags=["dashboard"],
    response_model=WeeklyClassReportRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def weekly_class_report(
    course_section_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    week: "int | None" = Query(
        default=None,
        description="学期周次（1-based）。缺省 = 这个班**已存下来的最新一周**"
                    "（ORDER BY week DESC LIMIT 1）",
    ),
) -> object:
    """**存下来的**那一份 ``weekly_class_report``（spec §4.7 / §8.5）。

    ⚠️ 它与上面那个大屏端点是**两件事**：本端点读的是周日批处理**落库**的那一行
    （5 个 ``JsonText`` 列 + ``suggestion``），大屏读的是**现算**的。
    同一个周日之后两者逐字相等（守卫见模块 docstring），而周中读本周的周报会 404
    ——它还没生成。

    ⚠️ ``week`` 缺省取**最新的那一份**：教师端的默认视图是「上周的周报」，
    而前端不该为了拿一个周次先调一次 ``GET /api/weekly-class-reports``。

    ⚠️ 404 的 ``code`` 是 :data:`NO_WEEKLY_REPORT`，**不是**通用的 ``not_found``：
    「这个班这一周还没有周报」是常态（周报只在周日生成），前端要说的是一句
    「周日晚上生成，先看大屏」，不是一条错误横幅。

    ⚠️ ``response_model`` 复用 CRUD 目录里那个 :class:`WeeklyClassReportRead`
    （12 列全给，含 5 个 ``JsonText`` 列）：同一行数据从
    ``GET /api/weekly-class-reports/{id}`` 读到的与从这里读到的**是同一个契约**。
    ⚠️ 而那个资源在 :data:`app.api.routers.catalog.RESOURCES` 里是 ``writable=False``，
    故本端点是它的**第二个读取入口**（按 ``(班, 周次)`` 而不是按主键），
    不是第二个写入方——写入方只有 :func:`app.pipeline.report_stage.generate_weekly_reports`。
    """
    require_teaches_section(session, staff_no, course_section_id)
    section = _get_or_404(session, CourseSection, course_section_id)
    stmt = select(WeeklyClassReport).where(
        WeeklyClassReport.course_section_id == course_section_id,
        WeeklyClassReport.semester_id == section.semester_id,
    )
    if week is None:
        row = session.scalars(stmt.order_by(WeeklyClassReport.week.desc()).limit(1)).first()
    else:
        row = session.scalar(stmt.where(WeeklyClassReport.week == week))
    if row is None:
        which = (
            f"第 {week} 周没有周报"
            if week is not None
            else "一份周报都还没有"
        )
        return error_response(
            404,
            NO_WEEKLY_REPORT,
            f"教学班 {course_section_id}（学期 {section.semester_id}）{which}："
            f"weekly_class_report 只在**周日**的批处理里生成（spec §8.5 逐字），"
            f"判据是 report_stage.REPORT_WEEKDAY = 6。要看本周的实时数据请调 "
            f"GET /api/dashboard/class/{course_section_id}（它是现算的，"
            f"而本端点读的是存下来的那一行）",
        )
    return row


def _stratification_payload(row: StratificationResult) -> dict:
    """一行 ``stratification_result`` → **当前分层 + 可解释性展开**（spec §9.2 / §14 #17）。

    ------------------------------------------------------------------
    ``explanation`` 是从 ``input_snapshot`` **离线重建**出来的
    ------------------------------------------------------------------

    :func:`app.domain.stratify.explain` 要两个 domain 值对象
    （:class:`~app.domain.stratify.StratResult` 与
    :class:`~app.domain.derive.DerivedResult`），而它们**都不在库里**——
    库里存的是 ``input_snapshot`` 那一列（28 个键，由
    ``tests/pipeline/test_prescription_stage.py`` 的一条测试逐字钉住），
    而它的契约逐字就是「判定当时的**全部**输入，使任一条结果都能离线复算」
    （:func:`app.pipeline.run_stratify.input_snapshot_of` 的 docstring，spec §4.3）。
    故重建不需要回到当天的原始数据，也不需要重跑一遍管道。

    ⚠️ **``label`` / ``hit_rules`` / ``reason`` 一律取库里存的那一份**，
    不取重建后重算的那一份：它们是当天判定的**结果**，而重建只能证明
    「快照足以复现」，不能取代它。⚠️ 于是 ``explain`` 用到的 ``StratResult``
    是**从快照里读回来的**（``snap["label"]`` / ``snap["hit_rules"]`` /
    ``snap["reason"]``），不是 ``stratify(derived)`` 重算的——重算会把
    「快照与落库的标签不一致」这一档静默掩盖掉，而那一档恰恰是最该被看见的
    （它意味着 ``input_snapshot`` 不足以复现）。
    守卫是 ``tests/api/test_dashboard.py`` 的
    ``test_the_explanation_is_the_same_prose_the_pipeline_would_render``。

    ⚠️ **它是 :func:`app.pipeline.run_stratify.input_snapshot_of` 的逆运算**，
    而那一个正向函数住在 ``run_stratify.py``。把逆向放在这里是本 Task 的一个取舍
    （已登记为待清扫）：它今天只有一个消费者（学生首页），而正向那一份的键集
    由一条测试钉死，故漂移会当场红；等出现第二个消费者时应当把它提到
    ``run_stratify.py`` 与正向那一份并排住。
    """
    snap = row.input_snapshot
    derived = DerivedResult(
        sex=Sex(snap["sex"]),
        trend=Trend(snap["trend"]),
        weakness=WeaknessResult(
            items=tuple(ScoredItem(item) for item in snap["weakness_items"]),
            count=snap["W"],
            valid_count=snap["valid_count"],
            dominant_bucket=snap["dominant_bucket"],
        ),
        body_comp=BodyCompFlag(
            abnormal=snap["C"],
            reasons=tuple(snap["body_comp_reasons"]),
            body_fat_pct=snap["body_fat_pct"],
            limit=snap["body_fat_limit"],
        ),
        annual_change=dict(snap["annual_change"]),
        national_total=snap["national_total"],
    )
    result = StratResult(
        label=Layer(snap["label"]),
        hit_rules=tuple(StratRuleId(rule) for rule in snap["hit_rules"]),
        reason=snap["reason"],
    )
    return {
        "label": row.label,
        "hit_rules": row.hit_rules.split(","),
        # ⚠️ reason 取自**快照**而不是行上：stratification_result 没有 reason 这一列
        #    （它落库的是 label + hit_rules 两个，而 reason 是由命中规则单射得出的
        #    一行规范中文名，见 StratResult 的 docstring，故 input_snapshot 存了一份）。
        "reason": snap["reason"],
        "explanation": explain(result, derived),
        "percentile_source": row.percentile_source,
        "computed_on": row.computed_on,
        "input_snapshot": snap,
    }


def _student_notifications(student_id: int, *, unread_only: bool = False):
    """「**发给这个学生**的站内消息」这个筛选条件在全仓的**唯一住址**。

    ------------------------------------------------------------------------
    为什么要有这一个函数（Plan 04 Task 3 的小修波抽出来的）
    ------------------------------------------------------------------------

    ``notification`` 的收件人是**多态**的（``recipient_kind`` + ``recipient_id`` 两列
    合起来才是 spec §4.6 那一格「接收者」，而 ``recipient_id`` 刻意不是外键，理由逐字见
    :class:`~app.db.models.feedback.Notification` 的 docstring）。于是「发给某个学生的
    消息」不是一列、而是**两列的一个合取**——写两遍的失效形态很具体：
    :func:`student_home` 的未读角标说「1 条未读」，而
    :func:`student_notifications` 列出来 3 条，两个数都在页面上、都还是绿的。

    ⚠️ 全仓今天有**三个**消费者，一律走本函数：

    1. :func:`student_home` 的 ``unread_notifications``（``unread_only=True`` + COUNT）；
    2. :func:`student_notifications` 端点（``unread_only=False`` + 取行）；
    3. :func:`app.api.routers.alerts.mark_notification_read` —— ⚠️ **它今天不走本函数**，
       理由逐字见那一格：它要把作用域**融进按主键取行的那一次查询**
       （``WHERE id = ? AND recipient_kind = ? AND recipient_id = ?``），
       而本函数返回的是一个「按收件人取行」的 ``Select``，两者的主键条件不同源。
       它比对的**两列**与本函数逐字相同（``RECIPIENT_STUDENT`` + ``requester``），
       故「判据漂开」这一档由守卫
       ``tests/api/test_dashboard.py::test_the_notification_list_and_the_unread_badge_agree``
       看着（两个端点对同一个学生给出的未读数必须相等）。

    ------------------------------------------------------------------------
    ⚠️ 返回的是 ``Select``、不是行（硬规矩 #39 的代价如实记）
    ------------------------------------------------------------------------

    于是两个消费者可以各取所需：COUNT 的那一个用 ``.subquery()`` 包一层
    （**不把行拉进内存**），取行的那一个自己 ``.order_by(...)``
    （排序是展示口径、不是筛选口径，故不住在这里）。
    代价是调用方要多写一层 ``select(func.count()).select_from(...)``。
    """
    stmt = select(Notification).where(
        Notification.recipient_kind == RECIPIENT_STUDENT,
        Notification.recipient_id == student_id,
    )
    return stmt.where(Notification.is_read.is_(False)) if unread_only else stmt


def _student_home_response(session: Session, student_id: int, day: dt.date) -> dict:
    """**「某个学生在某一天的首页那一屏」这一个问题的唯一所有者**（Plan 04 收尾波抽出）。

    ⚠️ 它原先是 :func:`student_home` 的函数体，本波把它提成一个私有函数，
    因为教师端也要读同一屏（:func:`teacher_student_home`，即
    ``GET /api/teacher/students/{id}/home``）。**先例逐字是 Task 8 的
    :func:`app.api.routers.prescription._weekly_sheet_response`**：那一个也是
    「学生侧端点挂学生头 → 教师调它 401 → 加一条教师侧变体 → 把函数体抽出来两处共用」，
    于是两个端点的响应体**逐字相同**（守卫是
    ``tests/api/test_dashboard.py`` 的
    ``test_the_teacher_and_the_student_variants_of_the_home_page_return_the_same_body``）。

    ⚠️ **不抽出来的话就有两个编排**：五格里的每一格各有一条口径
    （分层取「``computed_on <= day`` 的最新一行」、待办的窗口是
    「本学期周里已经上过、且教师发起过快评、且他还没交」的那些课、
    未读数走 :func:`_student_notifications`、勋章只数**学生级**的 ``GREEN_MASTERY``），
    复制第二份之后它们漂开的形态是**同一个学生**在两个身份下看到两个不同的首页，
    而两处各自的测试都还是绿的。

    ⚠️ **身份与作用域不在这里**（与 ``_weekly_sheet_response`` 同一条纪律）：
    两个调用方各自负责——学生侧 :func:`app.api.deps.require_scope`，教师侧
    :func:`app.api.deps.require_teaches_student`。本函数只回答「那一屏长什么样」。

    ⚠️ **它自己解析「哪一个是本学年」**（:func:`current_semester_of`）：两个调用方
    都不传 ``semester``，于是「首页的学期」不可能与调用方各判一次而分叉。
    代价（硬规矩 #39）：教师侧那条路径上 ``current_semester_of`` 会被查**两次**
    （一次给任教关系闸门、一次在这里）。那是一次按 ``is_current`` 的单行查找，
    与首页本身那五段查询相比可以忽略；换来的是两个调用方的入参**逐字同形**。
    """
    semester = current_semester_of(session, day)
    week = semester_week_of(semester.start_date, day)

    strat_row = session.scalars(
        select(StratificationResult)
        .where(
            StratificationResult.student_id == student_id,
            StratificationResult.computed_on <= day,
        )
        .order_by(StratificationResult.computed_on.desc())
        .limit(1)
    ).first()

    pending: list = []
    if week is not None:
        week_start, _week_end = semester_week_range(semester.start_date, week)
        submitted = set(
            session.scalars(
                select(RpeRecord.class_session_id).where(
                    RpeRecord.student_id == student_id
                )
            )
        )
        # ⚠️ 待办卡片的窗口是**本学期周里已经上过的那些课**（[week_start, day]）：
        #    一个三周前没交的快评今天仍然可以补交（submit_rpe 刻意不做过期，
        #    理由见 app.api.routers.feedback 模块 docstring 的「刻意不做」第 2 条），
        #    但把它挂在「今日」页的待办上是噪声。⚠️ 而 ``rpe_opened`` 是承重的：
        #    一节没被教师发起快评的课**根本没有**待办（那一列的语义逐字见
        #    ClassSession 的 docstring）。
        for cs_id, session_date, period in session.execute(
            select(
                ClassSession.id, ClassSession.session_date, ClassSession.period
            )
            .join(Enrollment, Enrollment.course_section_id == ClassSession.course_section_id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.semester_id == semester.id,
                ClassSession.rpe_opened.is_(True),
                ClassSession.session_date >= week_start,
                ClassSession.session_date <= day,
            )
            .order_by(ClassSession.session_date, ClassSession.period)
        ).all():
            if cs_id not in submitted:
                pending.append(
                    {
                        "class_session_id": cs_id,
                        "session_date": session_date,
                        "period": period,
                    }
                )

    # ⚠️ 筛选条件的唯一住址是 :func:`_student_notifications`（本处此前把「两列的合取」
    #    裸写在这里，而 Plan 04 Task 3 的小修波又要加一个**列**消息的端点 → 抽出来共用，
    #    否则「首页角标的未读数」与「消息中心列出来的未读数」可以各漂一边、两边都绿）。
    #    ⚠️ 仍然是一次 COUNT（``.subquery()`` 包一层），不把行拉进内存。
    unread = session.scalar(
        select(func.count())
        .select_from(_student_notifications(student_id, unread_only=True).subquery())
    )
    # ⚠️ 勋章 = 本学期至今 ``GREEN_MASTERY`` 的**条数**（spec §8.2 逐字
    #    「生成电子勋章记录」，而原型里那条记录就是 alert 表里的那一行 +
    #    一条站内消息，没有独立的勋章表）。⚠️ 只数**学生级**的那一种
    #    （student_id 非空），班级级的预警不是任何一个人的勋章。
    badge_dates = list(
        session.scalars(
            select(Alert.triggered_at)
            .where(
                Alert.student_id == student_id,
                Alert.semester_id == semester.id,
                Alert.rule_id == RuleId.GREEN_MASTERY.value,
            )
            .order_by(Alert.triggered_at.desc())
        )
    )

    return {
        "student_id": student_id,
        "as_of": day,
        "semester_id": semester.id,
        "week": week,
        "stratification": (
            None if strat_row is None else _stratification_payload(strat_row)
        ),
        # ⚠️ 训练单走 Task 4 那**一个**所有者（两档 404 在这里折成 None）：
        #    首页是一屏，一格缺数据不该让整屏失败，故本端点把那个 Response 对象
        #    当成「没有」读。⚠️ 要区分「没有处方」与「那一天不在微周期里」请调
        #    那个端点自己（它的两档 code 不同，理由见 OUTSIDE_MICROCYCLE）。
        "weekly_sheet": _sheet_or_none(session, student_id, day),
        "pending_rpe": pending,
        "unread_notifications": unread,
        "badges": {
            "count": len(badge_dates),
            "latest": badge_dates[0] if badge_dates else None,
        },
    }


@router.get(
    "/api/students/{student_id}/home",
    tags=["dashboard"],
    response_model=StudentHomeRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def student_home(
    student_id: int,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
    as_of: "dt.date | None" = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天",
    ),
) -> dict:
    """**学生端首页**（spec §9.2 的「今日」页 + 「我的数据」里那两格）。

    五格：当前分层 + 可解释性展开、本周训练单、待办卡片（未交的快评）、
    未读通知数、电子勋章。⚠️ 五格的**编排**住在
    :func:`_student_home_response`（教师侧那个变体共用同一份），本函数只有两行：
    作用域闸门 + 解析 ``as_of``。

    ⚠️ **本周完成度那一格刻意不在这里**，理由逐字见
    :class:`app.api.schemas.dashboard.StudentHomeRead` 的 docstring
    （它的唯一所有者是 ``GET …/training-logs/completion-rate``，
    再算一遍就是第二个所有者，而两处的分母窗口一旦漂开，环形进度条与被预警的
    完成率就会给出两个数）。

    ⚠️ **任何一格缺数据都返回 ``None``、不返回 404**：首页是**一屏**，
    一个从没被分层过的学生仍然该看到他的待办卡片与未读红点。
    这与 :func:`app.api.routers.prescription.weekly_sheet` 的 404 刻意不同
    （那一个端点只回答一个问题，答不了就该说答不了）。
    """
    require_scope(session, student_id, requester)
    return _student_home_response(session, student_id, _business_day(as_of))


def _sheet_or_none(session: Session, student_id: int, day: dt.date):
    """:func:`_weekly_sheet_response` 的**首页版**：两档 404 一律折成 ``None``。

    ⚠️ 判据是「返回值是不是一个 ``Response`` 实例」：那一个函数在 404 的两档上
    返回的是 :func:`app.api.errors.error_response` 造出来的 ``JSONResponse``，
    在 200 那一档返回的是 ``weekly_sheet_payload`` 的 dict。
    两者类型不同，故 ``isinstance`` 是可靠的判据（⚠️ 硬规矩 #107：
    用谓词挑对象之前先对一个已知反例验证谓词——守卫是
    ``tests/api/test_dashboard.py`` 的
    ``test_the_home_page_turns_both_404s_of_the_weekly_sheet_into_null``，
    它把两档 404 各造一次）。
    """
    payload = _weekly_sheet_response(session, student_id, day)
    return None if isinstance(payload, Response) else payload


@router.get(
    "/api/students/{student_id}/notifications",
    tags=["dashboard"],
    response_model=list[NotificationRead],
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def student_notifications(
    student_id: int,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
) -> list:
    """**发给这个学生的全部站内消息**（spec §9.2 的「消息中心」）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 为什么会有这一个端点（Plan 04 Task 3 的小修波，Plan 04 Task 2 顶回的第 1 处）
    ------------------------------------------------------------------------

    它**不是**为了堵一个洞。``notification`` 的泛型 list（``GET /api/notifications``）
    今天就是**匿名**的（终审 I3 复核实测 **200**），任何调用方一次就能读到全部行。
    ⚠️⚠️ 本处此前还给它找了一个**同档的邻居**、并引了一条口径，两半都过期了。原文是
    「而那一档与既有口径同档（48 个匿名 GET 里已经包括 ``GET /api/students``，它给的是
    60 个人的出生日期）。本仓的读侧口径逐字是『**读 ⇒ 一律匿名**（大屏与列表要能
    不登录就读）』」——Plan 05A Task 5 已把 ``students`` / ``teachers`` 那 4 个名册读
    收到教职身份（匿名实测 **401**），故 ① 那个括号里的例子今天反了 ② 「一律」二字
    不再成立（顺带一句：本模块自己的 6 个端点**从来不是**匿名的，它们自 Plan 03 Task 8
    起就各挂 ``Security(...)``）。
    ⚠️ 而本端点的论证**不依赖**那两半：``notification`` 那一行没有在那次重裁里被改
    （仍然匿名），且下面「泛型 list 没有筛选参数 → 前端只能拉全表再客户端过滤」
    那一条与身份无关。
    ⚠️ **「哪些读今天还匿名」的账面只有一个住址**：:mod:`app.api.routers.catalog`
    的模块 docstring，本处只指过去、不复述第二份（终审 I3）。
    守卫是 ``tests/api/test_prescription_api.py`` 那一条全仓级断言。

    理由是**前端的代价**：泛型 list **没有筛选参数**（``?recipient_id=4`` 会被 FastAPI
    静默忽略、只返回全量），故「发给我的消息」在前端只能是「把整张表拉下来、
    再客户端过滤」。⚠️ 演示库上那个代价是「读 19 行、留下 1 行」；而它的**同族**
    （``training_log`` 841 行 / ``rpe_record`` 240 行，两者同样没有按学生筛选的端点）
    是「翻 5 页收集 1200 行、留下 20 行」。消息中心那一页是**正确**的
    （Plan 04 Task 2 就是这么交付的），但每一次打开都要拉全表。
    能不必付的代价就不必付——于是这一格搬到服务端，筛选条件的唯一住址是
    :func:`_student_notifications`（首页那个未读角标走的是同一个函数）。

    ------------------------------------------------------------------------
    身份与作用域
    ------------------------------------------------------------------------

    ``X-Student-Id`` + :func:`app.api.deps.require_scope`，与
    :func:`student_home` **同档**（那一个也是「路径里一个 ``student_id``、
    头里一个请求者」的形状）。⚠️ 于是两档都是 **403** ``forbidden``、不是 404：
    「这个学号不在册」与「你在读别人的消息」刻意同形（理由逐字见
    :func:`app.api.deps.require_scope`——区分两者等于把在册名单告诉调用方）。

    ⚠️ 它与 :func:`app.api.routers.alerts.mark_notification_read` 的作用域判据
    **逐字相同**（``recipient_kind = "student"`` ∧ ``recipient_id = 请求者``），
    只是那一个把判据融进了「按主键取行」的查询里（理由逐字见那一格）。
    故「列出来能看见」与「标已读能标动」结构上不可能一个放行一个拒绝。

    ------------------------------------------------------------------------
    ⚠️ 响应体是一个**裸数组**、不是 ``{"items": …}``
    ------------------------------------------------------------------------

    它**刻意不复用** :class:`app.api.deps.Page` 那四个键：本端点没有 ``limit`` /
    ``offset``（一个学生的站内消息实测是**一人一条**，演示库 19 条发给 19 个不同的
    学生），回一个恒等于行数的 ``total`` 与两个恒为 ``200`` / ``0`` 的
    ``limit`` / ``offset`` 是三个**没有信息的键**，而前端会为它们写一段翻页代码。
    ⚠️ 于是它是全仓**第一个**回裸数组的读端点（``POST /api/mini-tests/batch``
    的**请求体**是数组，响应不是）。若将来一个学生的消息多到要翻页，
    正确做法是把 :class:`Page` 挂上来（并同步前端），**不是**在客户端截断。

    ⚠️ **排序在服务端**（``created_at`` 降序，同刻按 ``id`` 降序）：
    「新的在上面」是消息中心的口径，而它此前住在前端的一个 ``.sort()`` 里
    （``Notifications.vue``）。放这里之后，两个消费者（首页角标 / 消息中心）
    看到的是同一个序。⚠️ ``created_at`` 单独排是不够的：批处理在**同一刻**写若干行，
    而 SQLite 的排序在相等键上**不保证稳定**，故补 ``id`` 做 tie-break。

    ------------------------------------------------------------------------
    ⚠️ 路由顺序：与泛型**不同形**，故不承重（但仍排在 catalog 之前）
    ------------------------------------------------------------------------

    本路径是 ``/api/`` 之后的**三段**（``students`` / ``{student_id}`` /
    ``notifications``），而泛型工厂为 ``students`` 注册的是
    ``GET /api/students`` 与 ``GET /api/students/{student_id}``（一段与两段），
    为 ``notifications`` 注册的是 ``GET /api/notifications`` 与
    ``GET /api/notifications/{notification_id}``。故**没有一个与本路径同形**，
    两种 include 顺序给出同一套匹配。⚠️ 这与
    ``tests/api/test_feedback.py::_LITERAL_TAILED_SPECIAL_ROUTES`` 那三条不同：
    那一份清单钉的是「与 ``{path}/{占位}`` **同形**（两段、末段一个占位）」的特例
    （``GET /api/mini-tests/normalized`` 是唯一真的会被吃掉的一个），
    本路径是三段，不在那一族里。
    """
    require_scope(session, student_id, requester)
    return list(
        session.scalars(
            _student_notifications(student_id).order_by(
                Notification.created_at.desc(), Notification.id.desc()
            )
        )
    )


@router.get(
    "/api/teacher/students/{student_id}/weekly-sheet",
    tags=["dashboard"],
    response_model=WeeklySheetRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def teacher_weekly_sheet(
    student_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    as_of: "dt.date | None" = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天。它决定「本周是第几周」",
    ),
) -> object:
    """**教师端**读单个学生的本周训练单（简报 P8-A5：Task 4 留下的能力缺口）。

    spec §9.1（教师大屏）与 §9.3（学生详情）都要「教师点开一个学生看他的本周训练单」，
    而 ``GET /api/students/{id}/weekly-sheet`` 挂的是**学生**身份头
    （``X-Student-Id`` + :func:`app.api.deps.require_scope`）——
    教师用 ``X-Teacher-Staff-No`` 调它会 **401**。⚠️ 那个端点**刻意不**改成
    「学生或教师任一即可」：一个双身份闸门要判两条规则，而两条规则的失败码不同
    （学生侧不符是 403、教师侧不任教也是 403，但「两个头都没带」是 401 还是 422？），
    理由逐字见 :mod:`app.api.routers.prescription` 的模块 docstring。

    ⚠️ **响应体与学生侧那个端点逐字同形**（同一个
    :func:`app.api.routers.prescription._weekly_sheet_response`、同一个
    :class:`~app.api.schemas.prescription.WeeklySheetRead`），
    故两档 404 的 ``code`` 也逐字相同（``no_active_prescription`` /
    ``outside_microcycle``）。守卫是
    ``tests/api/test_dashboard.py`` 的
    ``test_the_teacher_and_the_student_variants_return_the_same_body``。

    ⚠️ ``response_model`` 与学生侧那个端点**是同一个**
    :class:`~app.api.schemas.prescription.WeeklySheetRead`，故两个端点在
    ``/openapi.json`` 里指向同一个 schema（前端生成的 TS 类型因此只有一份）。
    ⚠️ 两档 404 靠的是本仓既有的那条口径：返回一个 ``Response`` 实例时 FastAPI
    **跳过** ``response_model`` 的校验（:func:`app.api.routers.prescription.current_prescription`
    的 docstring 逐字交代了它）。⚠️ 代价（硬规矩 #39）：两档 404 的形状因此在
    OpenAPI 里**看不见**（那一侧也没有），前端要按 :mod:`app.api.errors` 的统一形状
    与两个 ``code``（``no_active_prescription`` / ``outside_microcycle``）分支。
    已登记为待清扫。

    ⚠️ **任教关系是按 ``as_of`` 所属的那个学期判的**：
    :func:`app.api.deps.require_teaches_student` 的第四个入参是承重的
    （不带学期的话「上学期教过他」就等于「这学期也能读他」，理由逐字见那个函数）。
    而「哪一个是本学年」的所有者是
    :func:`app.pipeline.percentile_stage.current_semester_of`（优先 ``is_current``、
    退化到「包含 ``as_of`` 的那个」），本模块不自己查一遍 ``semester`` 表。
    """
    day = _business_day(as_of)
    require_teaches_student(
        session, staff_no, student_id, current_semester_of(session, day).id
    )
    return _weekly_sheet_response(session, student_id, day)


@router.get(
    "/api/teacher/students/{student_id}/home",
    tags=["dashboard"],
    response_model=StudentHomeRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def teacher_student_home(
    student_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    as_of: "dt.date | None" = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天。它同时决定"
                    "「本周是第几周」与「按哪一个学期判任教关系」",
    ),
) -> dict:
    """**教师端**读单个学生的首页那一屏（Plan 04 收尾波：Task 3 顶回的那一条）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 为什么会有这一个端点
    ------------------------------------------------------------------------

    Plan 04 Task 3 交付「学生详情」页时实测：``GET /api/students/{id}/home``
    挂的是**学生**身份头（``X-Student-Id`` + :func:`app.api.deps.require_scope`），
    教师用 ``X-Teacher-Staff-No`` 调它是 **401** ``unauthenticated``——而且学生侧
    那五个端点**全都**这样。而前端 ``client.ts`` 一次只注入一个身份头，故
    「教师身份」与「读 ``/home``」在结构上互斥。那一页因此降级交付：分层改走匿名的
    ``GET /api/stratification-results``（**拿不到**后端现算的 ``explanation``），
    待办 / 未读数 / 勋章计数**三样点名拿不到**，并顶回「正确形状是加教师侧变体」。
    本端点就是那一条顶回的落地。

    ⚠️ 它**刻意不**把学生侧那个端点改成「学生或教师任一即可」：一个双身份闸门要判
    两条规则，而两条规则的失败码不同（学生侧不符是 403、教师侧不任教也是 403，
    但「两个头都没带」是 401 还是 422？），理由逐字见
    :mod:`app.api.routers.prescription` 的模块 docstring。

    ------------------------------------------------------------------------
    ⚠️ 响应体与学生侧那个端点**逐字相同**
    ------------------------------------------------------------------------

    同一个 :func:`_student_home_response`、同一个
    :class:`~app.api.schemas.dashboard.StudentHomeRead`，故两个端点在
    ``/openapi.json`` 里指向同一个 schema（前端生成的 TS 类型只有一份）。
    **先例逐字是上面那个 ``weekly-sheet`` 的教师侧变体**（Task 8：函数体抽成
    ``_weekly_sheet_response`` 两处共用）。守卫是
    ``tests/api/test_dashboard.py`` 的
    ``test_the_teacher_and_the_student_variants_of_the_home_page_return_the_same_body``
    （⚠️ 两侧**不同源**：一侧用学生头调学生端点、一侧用教师头调本端点，比两者相等）。

    ⚠️ 于是「任何一格缺数据都返回 ``None``、不返回 404」这一档在两侧也逐字相同
    （首页是**一屏**，一格缺数据不该让整屏失败）。⚠️ 而训练单那一格在本端点里
    仍然是**折成 ``None``** 的（:func:`_sheet_or_none`）：要区分「没有处方」与
    「那一天不在微周期里」请调 ``GET /api/teacher/students/{id}/weekly-sheet``
    （它的两档 ``code`` 不同）。

    ------------------------------------------------------------------------
    ⚠️ 任教关系是按 ``as_of`` 所属的那个学期判的
    ------------------------------------------------------------------------

    :func:`app.api.deps.require_teaches_student` 的第四个入参是**承重的**：不带学期的话
    判据会退化成「他**曾经**教过这个学生」，于是一位上学期教过某人的教师这学期仍读得到
    他本学期的数据（Plan 03 硬规矩 #114 的出处）。⚠️ 而 ``enrollment`` 与
    ``course_section`` **两行**的 ``semester_id`` 都必须等于它，故
    「一个学期的选课行挂到另一个学期的班上」这一档也被挡住。
    「哪一个是本学年」的所有者是
    :func:`app.pipeline.percentile_stage.current_semester_of`，本模块不自己查一遍。
    守卫是 ``test_the_home_page_teacher_variant_requires_the_teaching_relation``
    与 ``test_teaching_last_semester_does_not_grant_access_to_the_home_page``。
    """
    day = _business_day(as_of)
    require_teaches_student(
        session, staff_no, student_id, current_semester_of(session, day).id
    )
    return _student_home_response(session, student_id, day)


@router.get(
    "/api/teacher/students/{student_id}/normalized",
    tags=["dashboard"],
    response_model=NormalizedSelfRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def teacher_student_normalized(
    student_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    semester_id: int = Query(
        description="学期 id（「班内」按这个学期的选课关系定）。⚠️ 它**同时**是"
                    "任教关系闸门的那一个学期（见下面那一节），故两个用途只有一个入参"
    ),
    week: int = Query(ge=1, description="**学期**周次，与 mini_test.week 同口径"),
) -> dict:
    """**教师端**读单个学生在那一周的标准化得分三格（**全列**，Plan 06 Task 10）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 为什么会有这一个端点
    ------------------------------------------------------------------------

    Plan 06 Task 9 把 ``squat_score`` / ``composite`` 两格从
    :class:`~app.api.schemas.feedback.NormalizedEntryRead` 上**摘掉**了
    （列级收窄 → **schema 级摘列**：改前那两格对学生档置 ``None``，于是同一个操作的
    响应体**随身份而变**，而 OpenAPI 只有一张 schema → 生成出来的 ``schema.d.ts``
    宣称它们永远有值，是一份**假契约**）。⚠️ 摘列欠下的账由
    ``GET /api/mini-tests/normalized/me`` 还给了**本人**，而它**仅学生可读**
    （教职是 403：「『我自己』对教职无意义」），故教师端「学生详情」页
    （``views/teacher/StudentDetail.vue``）的「小测综合分」那一格当场没了
    ——Task 9 因此顶回「正确的形状是另开一条教师侧变体」。**本端点就是那一条顶回的落地。**

    ⚠️ 它**刻意不**把 ``/normalized/me`` 改成「学生或教职任一即可」：一个双身份闸门要判
    两条规则，而两条规则的失败码不同（学生侧不符是 403、教师侧不任教也是 403，
    但「两个头都没带」是 401 还是 422？），理由逐字见
    :mod:`app.api.routers.prescription` 的模块 docstring。⚠️ 而本仓的既有口径逐字是
    「**教师端必须有自己的一条路径**」，住址在
    :func:`app.api.deps.require_teaches_student` 的 docstring；本端点与上面
    :func:`teacher_weekly_sheet` / :func:`teacher_student_home` 两个教师侧变体
    **同址、同姿势**（同一个 ``Security(TEACHER_STAFF_NO_SCHEME)`` +
    :func:`app.api.deps.current_teacher` + :func:`app.api.deps.require_teaches_student`）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 形状恒定（本端点存在的全部理由）
    ------------------------------------------------------------------------

    它恒为「**那一个学生**的那几行、**全列**」（含 ``squat_score`` 与 ``composite``），
    与 ``response_model`` 声明的 :class:`~app.api.schemas.feedback.NormalizedSelfRead`
    **是同一个 schema**——即「一个身份一种形状」的**反面**：不管谁打它，
    schema 都一样，故 OpenAPI 是**真契约**（``schema.d.ts`` 上说有值的格，响应里就有值）。

    实测矩阵（**生产档 = 真 cookie**；演示库上学生 4 = ``2023120001``，他在班 2 与班 4、
    两班都是 T0002 教）：

    ======================  ==================  ======================================
    调用方                    码                 由谁给出
    ======================  ==================  ======================================
    匿名                    **401**             :func:`app.api.deps.current_teacher`
    学生**会话**（cookie）   **403**             同上（「一个学生的 cookie 不能当教师用」；
                                                他有 ``/normalized/me``）
    T0001（不教他）          **403**             :func:`app.api.deps.require_teaches_student`
    T0002（教他）            **200**（他的行）    同上放行
    T0003（管理员）          **200**             同上（``role='admin'`` 越过任教范围）
    ======================  ==================  ======================================

    ⚠️ **管理员那一档与上面两个教师侧变体逐字同一条口径**（实测两者对 T0003 都是 200，
    而 T0003 **不带任何班**）：:func:`app.api.deps.require_teaches_student` 的第一行就是
    ``if require_staff(...) == ADMIN_ROLE: return``，本端点**不写第二份**管理员判据。
    ⚠️ 守卫是 ``tests/api/test_dashboard.py`` 的
    ``test_the_teacher_normalized_variant_admits_only_a_teaching_staff_session``
    （它**当场复验**了 ``/home`` 与 ``/weekly-sheet`` 对同一个管理员也是 200）。

    ⚠️ **请求头那一档（仅 dev）码不同**，如实记：``X-Student-Id`` 调本端点是 **401**
    而不是 403 —— :func:`app.api.deps.current_teacher` 根本**没读到**教师身份，
    故它答的是「缺身份」而不是「你不是这一类人」；与上面
    :func:`teacher_student_home` 那一条逐字同形（守卫是
    ``test_the_home_page_teacher_variant_rejects_anonymous_and_student_callers``）。
    ⚠️ 而生产档下 ``PE_ALLOW_HEADER_IDENTITY`` 被强制关，故那一档在甲方现场**不可达**；
    它由 ``test_the_teacher_normalized_variant_in_the_dev_header_tier`` 另外钉住。

    ------------------------------------------------------------------------
    ⚠️⚠️ ``sections`` 里只留**他本学期任教的班**（这一格是承重的，不是顺手）
    ------------------------------------------------------------------------

    一个学生同一学期**可能在两个班**（行政班与分层班并存），而那两个班**可能不是同一个
    教师教的**（演示库上学生 1 选在班 1〔T0001〕与班 5〔T0003〕）。若本端点把他**全部**
    班里的行都回给调用方，则 T0001 打学生 1 就会读到他在**班 5** 里的班内百分位——
    那正是 Plan 06 Task 8 在 :func:`app.api.routers.feedback.normalized_scores` 上
    花了一整个 Task 关掉的**跨教师读口**（响应级裁班），本端点会把它**重新开一个**。

    故 ``allowed_sections`` 与那一个端点的教师档**同一条判据、同一个所有者**：
    :func:`app.api.deps.taught_section_ids`（教师）/ ``None``（管理员）。
    ⚠️ 于是「形状恒定」仍然成立：变的是**哪几行**、不是**哪些列**，而
    「哪些行随身份而变」是分页/过滤的常规形状、OpenAPI 表达不了行数
    （逐字口径见 :func:`app.api.routers.feedback.normalized_scores` 的 docstring）。
    ⚠️ 代价（硬规矩 #39，如实记）：教师因此**看不到**这个学生在别人班里的综合分。
    那是有意的（教师账号之间要有数据隔离），要看全班的请管理员登录。

    ------------------------------------------------------------------------
    ⚠️ 任教关系按**入参那个 ``semester_id``** 判（不是按 ``as_of`` 折算）
    ------------------------------------------------------------------------

    上面两个教师侧变体收的是 ``as_of``，故它们要用
    :func:`app.pipeline.percentile_stage.current_semester_of` 把「哪一个是本学年」
    折算出来再交给闸门。⚠️ 本端点**不需要那一步**：``semester_id`` 本来就是它的
    **必填**查询参数（与 :func:`app.api.routers.feedback.normalized_scores` /
    ``normalized/me`` 两个端点逐字同形——两者都是 ``semester_id`` + ``week``、
    都无缺省，实测缺一个就是 **422**），而「班内百分位按哪一个学期的选课关系算」
    与「任教关系按哪一个学期判」**必须是同一个学期**，否则会出现
    「闸门按学期 A 放行、而分数按学期 B 算」这种在同一屏上自相矛盾的形状。
    ⚠️ 于是两个用途**共用一个入参**、本端点**不查** ``semester`` 表、也不折算周次。

    ------------------------------------------------------------------------
    ⚠️ 判据与算式一律复用既有的唯一所有者，本处一行都不写第二份
    ------------------------------------------------------------------------

    * **身份**：:func:`app.api.deps.current_teacher`（学生 cookie 403、匿名 401）。
    * **在册教职 + role**：:func:`app.api.deps.require_staff`
      （⚠️ 它查的是**同一张** ``teacher`` 表，而
      :func:`app.api.deps.require_teaches_student` 内部也调它一次——故非管理员那一档
      本端点会查两次 ``teacher``。如实记（硬规矩 #39）：那张表在演示库上是 **3** 行、
      在生产上是几十行，两次等值主键查询的代价可忽略，而换来的是「管理员判据只有
      一个所有者」（本处只**读** ``require_staff`` 的返回值，不自己判 role）。
    * **任教关系**：:func:`app.api.deps.require_teaches_student`（**带学期**，
      第四个入参承重，逐字理由见它自己的 docstring）。
    * **哪些班**：:func:`app.api.deps.taught_section_ids` + :func:`teacher_id_of`。
    * **分组、取样与三格算式**：:func:`app.api.routers.feedback._normalized_self_body`
      → :func:`app.api.routers.feedback._normalized_sections`
      → :func:`app.domain.report.mini_test_scores`（AST 守卫数定义份数 == 1）。
      ⚠️ 故「同一周同一个班的折返百分位」与「同一次小测的综合分」在本端点、
      ``/normalized`` 与 ``/normalized/me`` **三处结构上不可能**漂开；守卫是
      ``tests/api/test_dashboard.py`` 的
      ``test_the_teacher_variant_agrees_with_the_student_side_endpoint_cell_for_cell``。

    ⚠️ **它自己不产生审计行**（它是 GET；:func:`app.api.audit.should_record` 只认
    ``POST`` / ``PATCH`` / ``DELETE``）。

    ⚠️ 路径形状：**五段**（``/api/teacher/students/{student_id}/normalized``），
    与泛型的 ``GET /api/mini-tests/{mini_test_id}``（三段）与
    ``GET /api/students/{student_id}``（三段）都**不同形**，故 include 顺序对它不承重；
    ⚠️ 而第一段 ``teacher`` 是**单数**、那个资源的路径是 ``/api/teachers``（复数），
    故它也不与 :mod:`app.api.routers.catalog` 的任何一条同形
    （与上面两个 ``/api/teacher/students/…`` 变体逐字同一条论证）。
    """
    require_teaches_student(session, staff_no, student_id, semester_id)
    # ⚠️⚠️ **行级裁班的两档判据各自复用既有的唯一所有者**（与
    #    :func:`app.api.routers.feedback.normalized_scores` 的教师/管理员两支逐字同款）：
    #    管理员 → ``None``（不过滤，越过任教范围，既有口径）；
    #    普通教师 → 他本学期任教的那些班。逐字理由见上面「只留他任教的班」那一节。
    allowed_sections: "set[int] | None"
    if require_staff(session, staff_no) == ADMIN_ROLE:
        allowed_sections = None
    else:
        allowed_sections = set(
            session.scalars(
                taught_section_ids(
                    teacher_id_of(session, str(staff_no)), semester_id
                )
            )
        )
    return _normalized_self_body(
        session, student_id, semester_id, week, allowed_sections,
        # ⚠️ Plan 06 Task 12 / C5：``_normalized_sections`` 不再自己查 ``enrollment``
        #    （改前本端点走的是「它自己查一次」那一支，故本端点本来就只查一次；
        #    而 :mod:`app.api.routers.feedback` 那两个端点各自查了**两遍**）。
        #    于是三个消费者一律**由端点交进去**，那一个入参没有缺省值 ⇒
        #    「忘传就自己查」这一支在结构上不存在。
        _enrolled_sections(session, semester_id),
    )
