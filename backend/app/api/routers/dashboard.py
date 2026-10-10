"""教师大屏（spec §9.1）、学生端首页（§9.2）与教师端读单个学生训练单的**四个读端点**
（Plan 03 Task 8）。

==============================================================  ======  ==========================
路径                                                             身份     响应模型
==============================================================  ======  ==========================
``GET /api/dashboard/class/{course_section_id}``                 教师     :class:`ClassDashboardRead`
``GET /api/dashboard/weekly-class-report/{course_section_id}``   教师     :class:`WeeklyClassReportRead`
``GET /api/students/{student_id}/home``                          学生     :class:`StudentHomeRead`
``GET /api/teacher/students/{student_id}/weekly-sheet``          教师     :class:`WeeklySheetRead`
==============================================================  ======  ==========================

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
``test_the_dashboard_and_the_stored_report_agree_on_the_same_sunday``
（同一个周日、同一个班，两个端点的六个共有键**逐字相等**）。

⚠️ 而本模块**自己**只写四段查询，各有一个理由（都不是聚合）：

1. ``weekly_class_report`` 那一行的查找（它读的是**存下来的**周报，不是现算的）；
2. 学生首页的「当前分层 + 可解释性」（:func:`_stratification_payload`，逐人不是逐班）；
3. 学生首页的「待办卡片」（已发起快评而这个学生还没交的课）；
4. 学生首页的「未读通知数」与「勋章数」（两个 COUNT）。

----------------------------------------------------------------------------
⚠️ include 顺序：本 router **必须**排在 :mod:`.catalog` 之前
----------------------------------------------------------------------------

:mod:`app.api.routers` 的模块 docstring 逐字写了这条纪律（「特例一律在泛型之前」）。
⚠️ 本 Task 实测：``/api/dashboard/…`` 与 ``/api/teacher/students/…`` 与 23 个资源的
五个端点**没有一个同形**（``dashboard`` / ``teacher`` 都不是资源路径的第一段），
而 ``/api/students/{student_id}/home`` 是三段、泛型的 ``/api/students/{student_id}``
是两段，故也不同形。⚠️ 于是顺序对本 router **今天不承重**——但它仍然排在
``catalog`` 之前，因为「一条不需要逐个 router 去论证『它同形吗』的规则才是能执行的规则」
（那句话逐字写在 :data:`app.api.routers.api_router` 的注释里）。

----------------------------------------------------------------------------
身份与作用域（计划 Review Focus 第 1 条：越权访问）
----------------------------------------------------------------------------

* **三个教师侧**：``X-Teacher-Staff-No`` + :func:`app.api.deps.require_teaches_section`
  （班级那两个）/ :func:`app.api.deps.require_teaches_student`（读单个学生那一个）。
  ⚠️ **任教关系是 Plan 03 Task 8 建的**（简报 P8-A5 点名的那条链：
  ``enrollment`` + ``course_section.teacher_id``），它**只挂在读的一侧**；
  三个写入端点（教师覆盖 / 手动重生成 / 预警处置）今天仍只过
  :func:`app.api.deps.require_teacher`（在册）——如实记录，已登记为关切。
* **一个学生侧**：``X-Student-Id`` + :func:`app.api.deps.require_scope`。
* 四个都挂 ``dependencies=[Security(...)]``（P4-A5），故那两个请求头在
  ``/openapi.json`` 的 ``components.securitySchemes`` 里各有一格、Swagger 的
  「Authorize」弹窗里填得进去。⚠️ **判定不在 ``Security`` 上**（它 ``auto_error=False``、
  只负责声明），仍在 :func:`current_student` / :func:`current_teacher`，
  故「缺头」的码仍是本仓既有的 **401**。
  ⚠️ 连带：``tests/api/test_prescription_api.py`` 那份 ``expected`` 清单
  由 **12 项扩到 16 项**（那条守卫的 docstring 逐字写着「Task 8/9 每加一个带身份的
  特例端点都要回来加一行——这是**有意的**」）。

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
    STUDENT_ID_SCHEME,
    TEACHER_STAFF_NO_SCHEME,
    current_student,
    current_teacher,
    get_db,
    require_scope,
    require_teaches_section,
    require_teaches_student,
)
from app.api.errors import error_response

# ⚠️ 复用 Task 4 那两个私有的 api 层助手，**不写第二份**：``_business_day`` 是
#    「今天是什么日子」在 api 层的唯一所有者，``_weekly_sheet_response`` 是
#    「某个学生在某一天的本周训练单」的唯一所有者（Task 8 从 weekly_sheet 的函数体
#    抽出来的，理由逐字见它的 docstring）。
from app.api.routers.prescription import _business_day, _weekly_sheet_response
from app.api.schemas.alerts import WeeklyClassReportRead
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
    未读通知数、电子勋章。

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
    day = _business_day(as_of)
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

    unread = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_kind == "student",
            Notification.recipient_id == student_id,
            Notification.is_read.is_(False),
        )
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
