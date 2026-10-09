"""处方侧的**四个特例端点**（Plan 03 Task 4）：教师覆盖、本周训练单、当前处方、手动重生成。

它们**不走** :func:`app.api.crud.build_crud_router`，因为有业务语义：读的一侧要把库里的
JSON 列**投影成学生端能直接渲染的形状**（spec §8.4），写的一侧要过 domain 的纯函数
（:func:`~app.domain.prescription.override.apply_overrides` /
:func:`~app.domain.prescription.triggers.evaluate_triggers`）而不是直接 ``setattr``。
⚠️ 这也正是 ``prescriptions`` 在 :data:`app.api.routers.catalog.RESOURCES` 里
``writable=False`` 的理由：**本模块是那张表唯一的写入方**，
于是「直接 PATCH 整行会让 ``training_package`` 与 ``assembly_snapshot`` 失去一致性」
这件事在结构上不可能发生。

----------------------------------------------------------------------------
四个端点
----------------------------------------------------------------------------

==============================================================  ======  ==========================
路径                                                             码      响应模型
==============================================================  ======  ==========================
``GET /api/students/{student_id}/prescriptions/current``          200     :class:`PrescriptionRead`
                                                                          （没有 → 404）
``GET /api/students/{student_id}/weekly-sheet?as_of=…``           200     :class:`WeeklySheetRead`
``POST /api/prescriptions/{prescription_id}/overrides``           200     :class:`OverrideResultRead`
``POST /api/prescriptions/{prescription_id}/regenerate?as_of=…``  200     :class:`PrescriptionRead`
==============================================================  ======  ==========================

⚠️ **两个 POST 都回 200、都不带 ``Location`` 头**，与 Task 3 那 23 个资源的
``POST → 201 + Location`` **刻意不同**：那两个约定说的是「**创建了一个新资源**」，
而这里两个 POST 都是「对一个已存在的资源做了一次**操作**」——覆盖是往一个 JSON 列里
append 一项（P4-A4：那一列是 ``TEXT NOT NULL``，故「追加」= 读列表 → append → 写回，
**不是 INSERT**），重生成是 upsert（同一天重复点命中的是更新分支）。
两者都**没有新的 URI 可以指**，编一个出来（``…/overrides/0``）会让前端以为
覆盖记录是一张可以单独 GET/PATCH 的资源，而它**不是**（spec §4.4：
教师覆盖记录是 ``prescription`` 的一个 JSON 列，没有自己的表）。

----------------------------------------------------------------------------
身份与作用域（计划 Review Focus 第 1 条）
----------------------------------------------------------------------------

* **两个 ``GET`` 是学生侧**：``X-Student-Id`` 必需，且经
  :func:`app.api.deps.require_scope` 校验「请求者 == 数据的所有者」。
  学生 A 拿 ``X-Student-Id: B`` 去读 B 的训练单 → **403**
  （守卫 ``test_a_student_cannot_read_another_students_weekly_sheet``）。
  ⚠️ **教师要看某个学生的训练单请走 Task 8 的教师端聚合**，本模块的两个 GET
  刻意不接受 ``X-Teacher-Staff-No``：一个「学生或教师任一即可」的闸门要判两条规则，
  而原型阶段教师端的读接口本来就是跨学生的（大屏、班级周报），形状不同。
* **两个 ``POST`` 是教师侧**：``X-Teacher-Staff-No`` 必需，且经
  :func:`app.api.deps.require_teacher` 校验「这个工号在册」。
  ⚠️ 原型**没有**「教师 ↔ 班级 ↔ 学生」的授权模型，故任何在册教师可以覆盖任何学生的
  处方（:func:`app.api.deps.require_teacher` 的 docstring 里如实记了这条代价）。

⚠️ 四个端点都挂了 ``dependencies=[Security(...)]``（P4-A5）：那两个请求头因此在
``/openapi.json`` 的 ``components.securitySchemes`` 里各有一格、在需要它们的操作上有
``security`` 要求，于是 Swagger UI 的「Authorize」弹窗里填得进去、
生成的 TS 客户端也知道要发。⚠️ **判定不在 ``Security`` 上**（它 ``auto_error=False``、
只负责声明），仍在 :func:`app.api.deps.current_student` / ``current_teacher``，
故「缺头」的码仍是本仓既有的 **401**（不是 ``APIKeyHeader`` 缺省的 403）。

----------------------------------------------------------------------------
``as_of``：由查询参数传，缺省取服务端当天
----------------------------------------------------------------------------

:func:`~app.domain.prescription.weekly.current_week` 与
:func:`~app.domain.prescription.triggers.evaluate_triggers` 都要求 ``as_of`` 由调用方注入
（domain 不碰时钟），而 **``api`` 是可以碰时钟的那一层**。缺省取
:func:`datetime.date.today` 由 :func:`_business_day` 单点持有。

⚠️ **代价（硬规矩 #39）**：缺省那一档让「今天」进了行为，故依赖它的测试不可复现
（跨过午夜跑同一个测试会得到不同的周次）。对策是**测试一律显式传 ``as_of``**，
而缺省那一档只由一条测试看着（``test_as_of_defaults_to_the_server_clock``，
它在同一进程里现场取 ``date.today()`` 作期望值）。
⚠️ 计划那条决定还提了一个环境变量口子（``PE_AS_OF``），**本 Task 刻意没有实现**：
「测试一律显式传」已经让测试可复现，而一个环境变量时钟是「今天是什么日子」的
**第二个所有者**，还多一档「值不是合法 ISO 日期」的分支要守。报告里记了这一处偏离。
"""
import datetime as dt

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

# ⚠️ 复用 Task 3 那个私有的 404 助手，而不在本模块写第二份消息：
#    「主键查无此行」这件事在全仓只应该有一种说法（前端按 code 分支、按 message 显示）。
from app.api.crud import _get_or_404
from app.api.deps import (
    STUDENT_ID_SCHEME,
    TEACHER_STAFF_NO_SCHEME,
    current_student,
    current_teacher,
    get_db,
    require_scope,
    require_teacher,
)
from app.api.errors import error_response
from app.api.schemas.prescription import (
    OverrideCreate,
    OverrideResultRead,
    PrescriptionRead,
    WeeklySheetRead,
)

# ⚠️ 走子模块路径（Ruling 97 / 硬规矩 #102）：Prescription **不在** app.db.models 的
#    公有导入面上，写 models.Prescription 会当场 AttributeError。
from app.db.models.prescription import Prescription
from app.domain.prescription.override import OverrideRecord
from app.domain.prescription.weekly import current_week, weekly_training_sheet
from app.pipeline.prescription_stage import (
    effective_package,
    override_record_payload,
    regenerate_for_student,
    training_package_payload,
    weekly_factors_of,
    weekly_sheet_payload,
)
from app.refdata_prescription import equivalence, exercises, templates

__all__ = [
    "CURRENT_STATUSES",
    "NO_ACTIVE_PRESCRIPTION",
    "OUTSIDE_MICROCYCLE",
    "router",
]

#: ``GET …/prescriptions/current`` 认的两个 ``status``。
#:
#: ⚠️ **值域的所有者是 :attr:`Prescription.STATUSES`（四个值）**，本常量只回答
#: 「四个里哪两个算『当前生效』」——那是**读侧的口径**，不是数据的形状，故它住在这里。
#: 另两个（``replaced`` / ``archived``）都被排除：``replaced`` 是已经被更新的一张取代的
#: （:func:`app.pipeline.prescription_stage._replace_previous` 写的），
#: ``archived`` 今天**没有写入方**（学期结束/学生离校归档是后续计划的活）。
#:
#: ⚠️ **``needs_review`` 算「当前生效」是计划的显式口径**，但它与
#: :func:`app.pipeline.prescription_stage.active_or_needs_review` 的 docstring 里那句
#: 「一张待人工复核的处方不能被学生端当成生效处方执行」有**张力**，如实记录：
#: 本端点把那一行照常返回，**并带上它的 ``status``**，于是「该不该让学生照着练」
#: 这个判断落在前端（Plan 04 的学生端必须在 ``status == "needs_review"`` 时挂一条横幅）。
#: 反过来做（对 ``needs_review`` 回 404）更糟：学生会看到「你没有训练单」，
#: 而他其实有一张待复核的——那看起来像数据丢了。
#: 守卫是 ``test_a_needs_review_prescription_is_still_the_current_one_and_says_so``。
#:
#: ⚠️ 用 ``tuple`` 而不是 ``set``：``status.in_(...)`` 两者都吃，而 tuple 让
#: 「有哪两个」在守卫里可以按**顺序**逐字钉住。
CURRENT_STATUSES: tuple[str, ...] = ("active", "needs_review")

#: 「这个学生这一天没有生效处方」的 ``code``（计划 Interfaces 逐字钉住的名字）。
NO_ACTIVE_PRESCRIPTION = "no_active_prescription"

#: 「有生效处方，但 ``as_of`` 不在它的微周期里」的 ``code``。
#:
#: ⚠️ **它与 :data:`NO_ACTIVE_PRESCRIPTION` 是两个不同的问题**，故给两个码：
#: 前者是「你压根没有处方」（前端该说「等下一次批处理」），
#: 后者是「你有处方，但你问的那一天不在它的 4 周里」（前端该说「那一天不在本周期」）。
#: 合成一个码的话前端无从区分，而两者的正确 UI 完全不同。
#:
#: ⚠️ **可达路径只有一条**（硬规矩 #39）：``valid_to`` 是 nullable 的
#: （:attr:`Prescription.valid_to` 的注释：``needs_review`` 的处方还没有确定的有效期），
#: 而 :func:`_current_prescription` 把 NULL 当「不设终点」放行；于是一张
#: ``valid_to IS NULL`` 且 ``generated_on`` 在 100 天前的行会被选中，
#: 而 :func:`current_week` 对它返回 ``None``。守卫是
#: ``test_a_day_beyond_the_microcycle_is_404_with_its_own_code``。
OUTSIDE_MICROCYCLE = "outside_microcycle"


def _business_day(as_of: dt.date | None) -> dt.date:
    """``as_of`` 缺省时取**服务端当天**。「今天是什么日子」在本模块只有这一个住址。

    ⚠️ **API 层可以碰时钟**（计划 Architecture 一节逐字写着），而 domain 与 pipeline
    的纯函数一律要 ``as_of`` 由调用方注入——本函数就是那个注入点。
    """
    return dt.date.today() if as_of is None else as_of


def _current_prescription(
    session: Session, student_id: int, as_of: dt.date
) -> Prescription | None:
    """``student_id`` 在 ``as_of`` 那天**当前生效**的那一张处方，没有则 ``None``。

    四个条件逐个说（它们是计划 Interfaces 那句「``status ∈ {active, needs_review}``
    且 ``valid_to`` 未过」的落地）：

    * ``status`` 落在 :data:`CURRENT_STATUSES` 里；
    * ``valid_from <= as_of``——⚠️ **这一条计划没写**，但不加它的话一张
      「周一之前先生成、下周一才生效」的处方（:attr:`Prescription.valid_from` 的
      列注释逐字举了这个用途）会在生效日之前就被学生端读到；
    * ``valid_to IS NULL OR valid_to >= as_of``——``valid_to`` 是**闭区间**的末日
      （``generated_on + microcycle_weeks 周 − 1 天``），故 ``>=`` 而不是 ``>``：
      末日那天处方仍然生效，而次日由触发 3 换新的一张
      （:func:`app.pipeline.prescription_stage.valid_to_of` 的 docstring 逐字交代了
      这个「差一天、而且应该差一天」）；
    * ``ORDER BY generated_on DESC LIMIT 1``——⚠️ 两张处方的有效期**可以重叠**
      （:attr:`Prescription.valid_to` 的注释：换处方时刻意**不改写**上一张的
      ``valid_to``，因为它必须能被离线复算），故「哪一张现在生效」由 ``status`` 定，
      而多张都还挂着 ``active`` 时取**最新**的那一张——与
      :func:`app.pipeline.prescription_stage._previous_prescriptions` 的
      「``generated_on <= as_of`` 里最新的那一张」同一条口径。
    """
    return session.scalar(
        select(Prescription)
        .where(
            Prescription.student_id == student_id,
            Prescription.status.in_(CURRENT_STATUSES),
            Prescription.valid_from <= as_of,
            or_(Prescription.valid_to.is_(None), Prescription.valid_to >= as_of),
        )
        .order_by(Prescription.generated_on.desc())
        .limit(1)
    )


router = APIRouter()


@router.get(
    "/api/students/{student_id}/prescriptions/current",
    tags=["prescriptions"],
    response_model=PrescriptionRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def current_prescription(
    student_id: int,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
    as_of: dt.date | None = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天。",
    ),
) -> object:
    """这个学生**当前生效**的那一张处方（16 列全给，含 5 个 ``JsonText`` 列）。

    没有 → **404** 且 ``code == "no_active_prescription"``（计划 Interfaces 逐字钉住）。
    ⚠️ 用 :func:`app.api.errors.error_response` 直接造响应，而不是
    ``raise HTTPException(404)``：后者的 ``code`` 会被
    :data:`app.api.errors._CODE_BY_STATUS` 折成通用的 ``not_found``，
    而前端要按 ``no_active_prescription`` 分支（「等下一次批处理」与「这个 id 打错了」
    是两种提示）。⚠️ 返回一个 ``Response`` 实例时 FastAPI **跳过** ``response_model``
    的校验，故 200 与 404 两档各自的形状都由本函数显式负责。

    ⚠️ ``needs_review`` 的那一行**照常返回**、并带着它的 ``status``——
    理由与代价逐字见 :data:`CURRENT_STATUSES`。
    """
    require_scope(session, student_id, requester)
    row = _current_prescription(session, student_id, _business_day(as_of))
    if row is None:
        return error_response(
            404,
            NO_ACTIVE_PRESCRIPTION,
            f"学生 {student_id} 在 {_business_day(as_of).isoformat()} 没有生效的处方"
            f"（prescription 里没有 status ∈ {list(CURRENT_STATUSES)} 且有效期覆盖那一天"
            f"的行）。处方不每天重发：它只在 spec §5.2 的五条触发之一成立时才生成，"
            f"故「没有」是常态、不是故障",
        )
    return row


@router.get(
    "/api/students/{student_id}/weekly-sheet",
    tags=["prescriptions"],
    response_model=WeeklySheetRead,
    dependencies=[Security(STUDENT_ID_SCHEME)],
)
def weekly_sheet(
    student_id: int,
    requester: int = Depends(current_student),
    session: Session = Depends(get_db),
    as_of: dt.date | None = Query(
        default=None,
        description="业务日期（YYYY-MM-DD）。缺省 = 服务端当天。它决定「本周是第几周」",
    ),
) -> object:
    """**spec §8.4 的「本周训练单」** = 骨架第 N 周 × 该周的全部调整系数。

    三步，每步的所有者都不是本函数：

    1. **周次**——:func:`~app.domain.prescription.weekly.current_week`
       （与触发 3 共用同一个 ``7`` 与同一个 ``>=`` 边界）；
    2. **骨架**——:func:`~app.pipeline.prescription_stage.effective_package`
       （库里的 ``training_package`` 列 × ``teacher_overrides`` 列，
       ⚠️ 是**教师覆盖之后**的那一份，否则 ``paused`` 永远是 ``False``、
       教师的暂停到不了学生端）；
    3. **本周调整**——:func:`~app.pipeline.prescription_stage.weekly_factors_of`
       （**Plan 02 Task 8 已经交付**，P4-A2：直接调用、不重写）+
       :func:`~app.domain.prescription.weekly.weekly_training_sheet`。

    响应形状是 :func:`~app.pipeline.prescription_stage.weekly_sheet_payload` 的输出
    （6 个键），而每个 block 与教师端从 ``GET /api/prescriptions/{id}`` 读到的
    ``training_package`` 里的 block **逐字段同形**（两处共用同一个
    ``_block_payload``，P4-A1）。⚠️ 那条「同形」是本 Task 的 Critical，
    守卫是 ``test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones``。

    两档 404，**码不同**（理由见 :data:`OUTSIDE_MICROCYCLE`）：
    没有生效处方 → ``no_active_prescription``；有、但 ``as_of`` 落在微周期之外 →
    ``outside_microcycle``。
    """
    require_scope(session, student_id, requester)
    day = _business_day(as_of)
    row = _current_prescription(session, student_id, day)
    if row is None:
        return error_response(
            404,
            NO_ACTIVE_PRESCRIPTION,
            f"学生 {student_id} 在 {day.isoformat()} 没有生效的处方，故没有本周训练单"
            f"（status ∈ {list(CURRENT_STATUSES)} 且有效期覆盖那一天的行一条都没有）",
        )
    week = current_week(row.generated_on, day, row.microcycle_weeks)
    if week is None:
        return error_response(
            404,
            OUTSIDE_MICROCYCLE,
            f"学生 {student_id} 的处方（{row.generated_on.isoformat()} 生成、"
            f"{row.microcycle_weeks} 周微周期）在 {day.isoformat()} 不在有效期内："
            f"current_week 返回 None（那一天早于生成日、或已经过了第 "
            f"{row.microcycle_weeks} 周）。⚠️ 这一档通常意味着该换处方了"
            f"（spec §5.2 触发 3），而不是「这个学生没有训练单」",
        )
    sheet = weekly_training_sheet(
        effective_package(row, exercises=exercises()),
        week,
        weekly_factors_of(session, row.id),
    )
    return weekly_sheet_payload(sheet)


@router.post(
    "/api/prescriptions/{prescription_id}/overrides",
    tags=["prescriptions"],
    response_model=OverrideResultRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def add_override(
    prescription_id: int,
    payload: OverrideCreate,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict:
    """追加**一条**教师覆盖（spec §7.5），返回覆盖之后生效的训练包。

    ⚠️ **是「追加」不是「替换」**（计划的显式决定）：``prescription.teacher_overrides``
    是一个 JSON 列表（P4-A4：那一列是 ``TEXT NOT NULL`` 的 ``JsonText``，故「追加」=
    **读列表 → append → 写回**，不是 INSERT；空列表写 ``[]`` 不写 ``NULL``），
    新记录恒 append 到**末尾**。

    ⚠️⚠️ **顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）
    → 本端点**不按 ``applied_at`` 重排序**，:func:`override_records_of` 也不排。
    ``VOLUME_SCALE`` 与 ``INTENSITY_STEP`` 两档是**增量**的（``"0.8"`` 再 ``"0.9"``
    得 ``0.72``），顺序错了结果就错了、且**全程不报错**。
    守卫是 ``test_overrides_append_and_the_list_order_decides``。

    ⚠️ **``teacher_staff_no`` 与 ``applied_at`` 由服务端填**（P4-A3）：前者取
    ``X-Teacher-Staff-No``，后者取 :func:`datetime.datetime.now`。
    请求体里**没有**这两个字段（:class:`OverrideCreate` 只有 5 个），
    故客户端**结构上不可能**冒充别的教师或伪造时间。

    ⚠️⚠️ **先算、后写**（本端点最要紧的一条实现纪律）：覆盖能不能生效由 domain 判
    （打错的 ``target``、``weekly_frequency`` 越界、``volume_scale <= 0``、
    ``intensity_step`` 把心率下界推到 ``<= 0``——五档全是 ``ValueError``）。
    故本函数**先用全部记录算一遍** :func:`effective_package` 的结果，
    **算成功了才写库**。反过来的顺序（先写再算）会让一次被拒绝的覆盖
    **留在库里**：响应是 422、而库里多了一条记录，下一次 GET 训练单照旧生效。

    ⚠️ ``reason`` 为空 → **422**，消息原文是 domain 那一段
    （「一条没有理由的覆盖对研究毫无价值」）；**API 层不再校验一遍**
    （Plan 02 传导第 4 条：那是第二个所有者）。

    ⚠️ **``prescription.training_package`` 那一列一个字都不改**：它永远是算法基线，
    而 spec §7.5「下次自动生成回到算法基线、不继承覆盖」靠的就是这件事。
    响应里那份 ``training_package`` 是**现算的**生效包。
    """
    row = _get_or_404(session, Prescription, prescription_id)
    require_teacher(session, staff_no)

    # ⚠️ 构造 OverrideRecord 就是「reason 非空」那道校验发生的地方（domain 的
    #    __post_init__），它排在任何写入之前，故一条空理由的覆盖**碰不到库**。
    record = OverrideRecord(
        kind=payload.kind,
        target=payload.target,
        old_value=payload.old_value,
        new_value=payload.new_value,
        reason=payload.reason,
        teacher_staff_no=staff_no,
        applied_at=dt.datetime.now(),
    )
    stored = override_record_payload(record)
    previous = list(row.teacher_overrides)

    # 先算一遍：apply_overrides 的五档 ValueError 都在这里响（→ 422），库一个字没动。
    # ⚠️ extra= 就是「还没落库的这一条」，它排在库里那些之后（顺序承重）。
    # ⚠️ exercises= 是**关键字必填**（Plan 02 的顶回 2）：缺了它 SUBSTITUTE_EXERCISE
    #    会留着旧动作的视频 URL —— 一个看起来正常的谎。
    effective = effective_package(row, exercises=exercises(), extra=(record,))

    row.teacher_overrides = previous + [stored]
    session.commit()
    session.refresh(row)
    return {
        "prescription_id": row.id,
        "overrides": row.teacher_overrides,
        "training_package": training_package_payload(effective),
    }


@router.post(
    "/api/prescriptions/{prescription_id}/regenerate",
    tags=["prescriptions"],
    response_model=PrescriptionRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def regenerate(
    prescription_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    as_of: dt.date | None = Query(
        default=None,
        description="新处方的业务日期（YYYY-MM-DD）。缺省 = 服务端当天",
    ),
) -> Prescription:
    """**手动重生成**（spec §5.2 触发 5：``teacher_requested=True``），返回那一张处方行。

    实现体是 :func:`app.pipeline.prescription_stage.regenerate_for_student`
    ——⚠️ **与批处理共用同一套算法**（五触发 / 匹配 / 装配 / 安全后置 / 上一张置
    ``replaced`` / 那 16 个列值），本端点只负责 HTTP 的那一层。

    ⚠️ **``previous_had_overrides`` 必须在响应里**（Plan 02 传导第 6 条 / P6-A2）：
    它是「界面提示『该生上次存在人工覆盖』」的**唯一载体**，
    **不是** ``assembly_snapshot`` 里的键（往快照加键会让 Plan 02 钉死的
    「12 键 / +3 键」两条守卫变红）。本端点的 ``response_model`` 是
    :class:`PrescriptionRead`（16 列全给），故那一列自然在里面——前端要显示
    「上一张有 N 条人工覆盖，本次已按 spec §7.5 丢弃」就靠它。
    守卫是 ``test_regenerate_clears_overrides_and_sets_previous_had_overrides``。

    ⚠️ **覆盖不继承**（spec §7.5 原文）：新行的 ``teacher_overrides`` 恒为 ``[]``。

    ⚠️ **幂等 → 200 而不是 409**（计划的显式决定）：同一天重复点由
    ``UniqueConstraint("student_id", "generated_on")`` + :func:`app.db.repo.upsert`
    兜住，库里仍是一行。**教师点两次「重新生成」不该看到报错。**
    守卫是 ``test_regenerating_twice_on_the_same_day_returns_200_and_one_row``。

    ⚠️ **``batch_id`` 取被点的那一行自己的**：教师手工发起的写入没有自己的批次，
    口径与 :attr:`app.db.models.prescription.WeeklyAdjustment.batch_id` 那一段逐字相同。
    ⚠️ 代价一并继承：重放那一天会连带删掉这次手工重生成的行。

    ⚠️ **``as_of`` 与 ``{prescription_id}`` 的关系**：URL 里那个 id 只用来定位
    **哪个学生**（与借它的 ``batch_id``）；「上一张是哪一张」由
    :func:`app.pipeline.prescription_stage._previous_prescriptions` 按 ``as_of`` 定
    （它是那件事的唯一所有者）。故对一张**旧的**处方点重生成，被置 ``replaced`` 的是
    **当时生效的那一张**，不是 URL 里那一张——如实记录（硬规矩 #39）。

    失败一律 **422**（domain/pipeline 的 ``ValueError`` 经 :mod:`app.api.errors` 折出来），
    其中最重要的一档是 ``label == insufficient_data``：Plan 02 把它报为最高优先级关切
    （「重新生成」按钮对 Z0 学生**无声失败**），而那一档现在会带着原因回来。
    """
    row = _get_or_404(session, Prescription, prescription_id)
    require_teacher(session, staff_no)
    fresh = regenerate_for_student(
        session,
        row.student_id,
        _business_day(as_of),
        batch_id=row.batch_id,
        templates=templates(),
        exercises=exercises(),
        equivalence=equivalence(),
    )
    session.commit()
    session.refresh(fresh)
    return fresh
