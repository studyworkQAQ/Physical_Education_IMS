"""泛型 CRUD 工厂：一次生成五个端点，23 个资源共用同一套行为。

**为什么是工厂而不是 23 套手写路由**（计划 Task 3 的第一条决定，用户裁定
「类似管理型的原型系统，需要能够进行增删改查」）：手写 23 套会产生 23 份**互相不一致**的
分页 / 错误 / 校验行为，而 Plan 04 的前端要为每一种不一致写一个特例。
**一致的行为是原型的资产，不是它的负债。** 有业务语义的特例（三源采集、教师覆盖、
预警处理、大屏聚合）**不走本工厂**，各自手写在自己的 router 里。

----------------------------------------------------------------------------
路径用连字符、字段名用下划线（计划 Task 3 的显式要求，本段就是那份对照）
----------------------------------------------------------------------------

URL 一律挂在 ``/api/`` 下、**复数 + 连字符**；Pydantic 模型的字段名一律**下划线**、
与 DB 列名逐字相同。对照表（23 行，与 :data:`app.api.routers.catalog.RESOURCES` 同序）：

============================  ==========================  ============================
资源路径                        表                          字段名的形状
============================  ==========================  ============================
``/api/semesters``             ``semester``                 ``start_date``
``/api/teachers``              ``teacher``                  ``staff_no``
``/api/students``              ``student``                  ``student_no``
``/api/course-sections``       ``course_section``           ``course_section_id``
``/api/enrollments``           ``enrollment``               ``semester_id``
``/api/fitness-test-batches``  ``fitness_test_batch``       ``test_date``
``/api/fitness-test-results``  ``fitness_test_result``      ``score_pull_up_or_sit_up``
``/api/body-compositions``     ``body_composition``         ``muscle_mass_kg``
``/api/interest-surveys``      ``interest_survey``          ``raw_answers``
``/api/percentile-snapshots``  ``percentile_snapshot``      ``age_group``
``/api/derived-metrics``       ``derived_metrics``          ``body_comp_abnormal``
``/api/stratification-results````stratification_result``    ``percentile_source``
``/api/exercises``             ``exercise``                 ``impact_level``
``/api/prescription-templates````prescription_template``    ``template_ref``
``/api/prescriptions``         ``prescription``             ``label_at_generation``
``/api/weekly-adjustments``    ``weekly_adjustment``        ``prescription_id``
``/api/class-sessions``        ``class_session``            ``session_date``
``/api/rpe-records``           ``rpe_record``               ``class_session_id``
``/api/training-logs``         ``training_log``             ``duration_min``
``/api/mini-tests``            ``mini_test``                ``item_combo``
``/api/alerts``                ``alert``                    ``trigger_snapshot``
``/api/notifications``         ``notification``             ``recipient_kind``
``/api/weekly-class-reports``  ``weekly_class_report``      ``checkin_rate_by_layer``
============================  ==========================  ============================

⚠️ **字段名不得改**：POST 与 PATCH 直接把 ``payload.model_dump()`` 的键喂给
``model(**values)`` / ``setattr``，改一个字段名就是一次
``TypeError: 'xxx' is an invalid keyword argument for Semester``。
⚠️ **路径也不得改**：Plan 04 的前端逐字照着它写（读写矩阵那 23 行）。
守卫是 ``tests/api/test_crud.py`` 的
``test_every_resource_path_is_a_hyphenated_plural_under_api``。

----------------------------------------------------------------------------
五个端点
----------------------------------------------------------------------------

======================  ======  ======================================================
端点                     码      形状
======================  ======  ======================================================
``GET {path}``           200    ``{"items": [...], "total": int, "limit": int,
                                 "offset": int}``；``total`` 是**全表**计数
``POST {path}``          201    整行 + ``Location: {path}/{新主键}`` 头
``GET {path}/{pk}``      200    整行（**含** ``JsonText`` 列）
``PATCH {path}/{pk}``    200    整行；**部分更新**（``exclude_unset=True``）
``DELETE {path}/{pk}``   204    空响应体
======================  ======  ======================================================

**错误一律走 :mod:`app.api.errors` 的统一形状** ``{"error": {"code","message","detail"}}``：
404（主键查无此行）/ 409（撞自然键、或 ``restrict`` 被子行挡住）/
405（``writable=False`` 或 ``on_delete="forbid"``）/ 422（请求体或分页参数校验失败）。

⚠️ **405 的实现是「那个路由根本不注册」**，不是「注册了再 raise」。两个后果都承重：
OpenAPI 里不出现那些方法（前端不会照 ``/docs`` 写一个必然 405 的按钮），
且 ``Allow`` 头由 Starlette 的路由匹配给出、天然是对的。
``errors.py`` 的 ``_CODE_BY_STATUS`` 没有 405 这一格，故 ``code`` 是它那条兜底规则
折出来的 ``http_405``——那条例子的出处正是本工厂。

----------------------------------------------------------------------------
``on_delete`` 的三档（计划 Review Focus 第 4 条：CRUD 的删除连带）
----------------------------------------------------------------------------

* ``"restrict"``（**缺省**，12 个资源）：有子行 → **409**，消息点名子表与行数。
  静默级联会带走不可复现的历史（spec §4.3 要求「历史行指向的东西还在」）。
* ``"cascade"``（**只有 1 个资源**：``class-sessions`` → ``rpe_record``）：
  **子表先删**（P7-A4：``PRAGMA foreign_keys=ON`` 下先删父表当场 FK 违例）。
* ``"forbid"``（10 个资源）：DELETE 端点不注册 → **405**。

⚠️ ``prescriptions`` → ``weekly_adjustment`` 是**另一处** cascade，但 ``prescriptions`` 的
``on_delete`` 是 ``restrict``（不许从 API 删处方），故那个 cascade 由 Task 4 的
「处方被替换」路径内部使用，**不经过 DELETE 端点**。

----------------------------------------------------------------------------
本模块刻意不做的事（硬规矩 #39：写清楚，免得下一个人以为它管得比实际宽）
----------------------------------------------------------------------------

* **不做列排序的查询参数**。``order_by`` 是**工厂参数**（缺省 ``"id"``），
  端点上没有 ``?order_by=``。于是「分页 + 排序」的读法是「返回的 items 按
  ``order_by`` 排好序」，而不是「客户端可以选排序键」。理由：可选排序键要一份
  列名白名单 + 一条 422 分支，而 Plan 04 的表格一屏最多 200 行、客户端排序够用。
  Plan 04 若要服务端排序，那是给本工厂加一个参数，不是改这 23 行。
* **不做软删除、审计日志、ETag / ``If-Match``、批量端点**（计划的显式决定；
  ``mini_test`` 的批量录入是 Task 5 的特例端点，不走本工厂）。
* **不做 PATCH 的取值域预检**。PATCH 只在 ``*Create`` 那三列枚举上有校验器，
  改坏一个外键或撞一个唯一约束时响应是 DB 侧的 409。
* **``pk`` 与 ``order_by`` 今天恒为缺省值 ``"id"``**：28 张表的主键都是单列 ``id``
  （守卫 ``tests/api/test_crud.py::test_every_table_has_a_single_column_primary_key``）。
  两个参数留着是因为计划的 Interfaces 逐字列了它们，而不是因为今天有人用非缺省值。
* **``readable`` 今天恒为 ``True``**：23 个资源没有一个「只写不读」。
  它的存在是为了让「关掉 list」这件事有一个开关，而不是让实现里长出一个
  ``if False``。
* **``scope`` 今天在 23 行 ``RESOURCES`` 里恒为 ``None``**：身份与作用域是特例端点的事
  （Task 5 的三源采集要校验 ``rpe_token``、Task 4 的教师覆盖要认 ``X-Teacher-Staff-No``）。
  本工厂留着这个钩子是因为计划的 Interfaces 列了它，并且
  ``tests/api/test_crud.py::test_the_scope_hook_rejects_a_mismatched_identity_with_403``
  用一个合成的 ``ScopeFn`` 把它跑通了——**它不是死代码，但也没有生产调用方**。
  ⚠️ 它只挂在 ``GET/PATCH/DELETE {path}/{pk}`` 三个端点上：``ScopeFn`` 的第二个入参是
  「一个 ORM 行」，而 list 要的是**过滤**、create 时**行还不存在**，两者都不是这个签名
  能表达的。
  ⚠️⚠️ **本条的前半句自 Plan 03 全分支终审之后已经过期了一半**（按实际改写）：
  「身份是特例端点的事」对**读**的一侧曾经大体成立（泛型 ``GET`` **缺省**匿名，
  大屏与列表要能不登录就读），⚠️ 而**安全收紧波之后它只剩 7 个参考数据资源成立**
  （13 个学生键资源改成「学生只读自己的、教职全读」，3 个改成「仅教职」）——
  ⚠️ 「哪些读今天还匿名」的**账面只有一个住址**：:mod:`app.api.routers.catalog`
  的模块 docstring，本处不复述（复述就是第二个所有者）。
  但对**写**的一侧不再成立——用户 2026-10-08 裁定「8 个可写资源都要
  教师头」（实测是 **9** 个，见 :data:`app.api.routers.catalog.RESOURCES`），
  于是 9 × POST/PATCH/DELETE 一共 26 个写入操作一律挂 ``require_admin=True``。
  落点是 :func:`_require_admin_identity`，它**不走** ``scope`` 这个钩子
  （``ScopeFn`` 判的是「这一行是不是你的」，而写入侧要判的是「你是不是一个在册教师」，
  两者是两件不同的事；create 时行还不存在，``ScopeFn`` 的签名根本用不上）。
"""
import dataclasses
import datetime as dt
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, Security
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.schema import Table

from app.api.deps import (
    NOT_STUDENT_OWNED,
    TEACHER_STAFF_NO_SCHEME,
    Page,
    ReaderIdentity,
    STUDENT_ID_SCHEME,
    current_reader,
    current_teacher,
    get_db,
    require_admin,
    require_scope,
    require_staff,
    require_teaches_student,
    taught_section_ids,
    taught_student_ids,
    teacher_id_of,
)
from app.db import repo
from app.db import width as db_width
from app.db.models._shared import JsonText
from app.db.session import Base

# ⚠️ ``api → pipeline`` 是许可方向（:data:`tests.architecture.test_layering.API_ALLOWED_PREFIXES`
#    里 Plan 03 就列进去的那一项），而本模块是它的**第二个**消费者
#    （第一个是 :mod:`app.api.routers.dashboard`，它拿同一个函数去解
#    「教师侧那两个特例端点的学期」）。⚠️ 于是「哪一个是本学年」在全仓仍然只有
#    一个所有者：:func:`app.pipeline.percentile_stage.current_semester_of`
#    （优先 ``is_current``、退化到「包含那一天的学期区间」），本模块**不自己查一遍**。
from app.pipeline.percentile_stage import current_semester_of

__all__ = [
    "ORPHAN_BY_TAUGHT_SECTION",
    "ORPHAN_BY_TEACHER_SELF",
    "ORPHAN_BY_VALUES",
    "READ_SCOPE_STAFF",
    "READ_SCOPE_STAFF_TAUGHT",
    "READ_SCOPE_STAFF_TAUGHT_SECTION",
    "READ_SCOPE_STUDENT_SELF",
    "READ_SCOPE_VALUES",
    "STUDENT_SCOPED_READ_VALUES",
    "CrudSchemas",
    "OrphanOwner",
    "ScopeFn",
    "StudentOwner",
    "build_crud_router",
]


def _require_admin_identity(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> None:
    """**写入侧的身份闸门**：三档 —— 缺身份 ``401`` / 在册但不是管理员 ``403`` /
    在册且 ``role='admin'`` 放行。

    它是 :func:`app.api.deps.current_teacher`（缺身份 401）与
    :func:`app.api.deps.require_admin`（在册 + ``role`` 两档 403）的**组合**，
    两个判定都不重写。

    ⚠️⚠️ **Plan 05A Task 2 之前它组合的是 ``require_staff``（当时叫 ``require_teacher``），
    故口径是「任何在册教师可写」**；用户 2026-10-12 逐字裁定「管理员这个角色接管管理台
    （23 个资源的增删改查）」，于是 9 × POST/PATCH/DELETE 一共 **26** 个写入操作
    变成「**仅管理员**可写」。⚠️ 而**载体与 OpenAPI 那一格一个字都没变**：
    管理员就是一行 ``role='admin'`` 的 ``teacher``，故仍然是
    ``Security(TEACHER_STAFF_NO_SCHEME)`` + 那个请求头（或 cookie 会话），
    改的只是**判定**——于是「挂 ``security`` 的操作数」在 Task 2 里不动（48）。

    ⚠️ **本函数只服务泛型工厂那 26 个写入端点**。特例端点
    （``POST …/overrides`` / ``POST …/regenerate`` / ``POST …/alerts/{id}/handle`` /
    ``open-rpe`` / ``mini-tests/batch`` / ``run-daily`` 一类）在函数体里手写
    :func:`app.api.deps.require_staff`，**刻意不改成本函数**：它们是**课堂功能**，
    管理员接管的是**管理台**，不是把教师赶出课堂（计划 §3.6 末段）。
    守卫是 ``tests/api/test_auth_api.py`` 的
    ``test_a_plain_teacher_keeps_the_classroom_endpoints_and_loses_the_console``。

    ⚠️ **返回 ``None``**：它是一道 pure gate（只判定、不改状态），端点不需要它的值。
    ⚠️ 它**必须与 ``Security(TEACHER_STAFF_NO_SCHEME)`` 成对挂**：本函数负责**判定**，
    那一个负责**声明**（进 ``/openapi.json`` 的 ``components.securitySchemes`` 与那个
    操作的 ``security`` 一格，于是 Swagger 的 Authorize 弹窗能填、生成的 TS 客户端
    知道要发这个头）。⚠️ 只挂前者会得到「前端从 spec 上看不出来要带头、一接就 401」
    ——那正是 P4-A5 当初要修的缺口；只挂后者会得到「spec 上写了、实际谁都放行」
    （``TEACHER_STAFF_NO_SCHEME`` 是 ``auto_error=False`` 的，缺省**不**抛，
    理由逐字见 :data:`app.api.deps.TEACHER_STAFF_NO_SCHEME` 的注释）。
    守卫是 ``tests/api/test_crud.py`` 的
    ``test_every_writable_resource_admits_only_an_admin_mutation``
    （三拍：逐个资源实发**不带头**的写请求断言 401、带一个**普通教师**的工号断言 403、
    带一个**管理员**的工号断言放行；再逐个断言 ``security`` 那一格在）。
    """
    require_admin(session, staff_no)


def _require_staff_identity(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> ReaderIdentity:
    """**读取侧的身份闸门**（Plan 05A Task 5）：缺身份 ``401`` / 工号不在册 ``403`` /
    在册教职（``teacher`` **或** ``admin``）放行。

    ------------------------------------------------------------------------
    ⚠️⚠️ 为什么会有它：泛型 ``GET`` 的「一律匿名」在 Plan 05A 之后**不再对全部 23 个资源成立**
    ------------------------------------------------------------------------

    Plan 04 Task 3 的偏离 ⑦ 定下「**只读 ⇒ 一律匿名**（``GET`` 一个都不挂 security）」，
    当时的论证逐字是「在不加强制的前提下声明 security 是一份反方向的假契约」——
    而那句话的**前提**是「本系统不做真实鉴权」（Plan 04 非目标第 1 条）。
    Plan 05A 做了真实鉴权，于是前提没了，那 48 个匿名 GET 要**逐个重新裁定**
    （计划 §5 Task 5 第 ② 条）。裁定结果是 **44 个仍匿名、4 个改成要教职身份**，
    而改的这 4 个来自本函数的两个消费者（两份名册）：

    * ``GET /api/students`` 与 ``GET /api/students/{id}`` —— 匿名返回 ``birth``，
      而 ``birth`` **正是学生绑定口令时的验身材料**（``POST /api/auth/students/bind``
      判的就是 ``student.birth != payload.birth``）。故「任何匿名调用方都能给任何学号
      绑定一个自己知道的口令、然后登录成他」。⚠️ 这一格是 Task 1+2 的实现者查出来的、
      **控制者的计划完全漏掉的**（计划 §3.2 只说了「验身材料本身是匿名可读的，
      原型可接受、写进已知局限」，而没有把它当成一个要修的洞）。
    * ``GET /api/teachers`` 与 ``GET /api/teachers/{id}`` —— 匿名返回 ``staff_no`` **与**
      ``name``，而那**两格合起来正是教师绑定口令的全部验身材料**
      （``POST /api/auth/teachers/bind`` 判 ``staff_no`` + ``name``）。
      ⚠️⚠️ **这一格比学生那一格更严重、而派单与计划都没点到它**：学生那一侧
      至少还要一个 ``birth``（一个 60 人里可能重复、而攻击者要逐个试的值），
      教师这一侧的两格**就在同一个响应体里并排躺着**，于是「读过一次
      ``GET /api/teachers`` 的人」可以给**任何**工号绑口令 —— 包括把一个
      ``role='admin'`` 的工号绑成自己的（``bind`` 不看 role、也不改 role，
      但登录之后他就是那个管理员）。实现者实测复核过（匿名 200 + 两格都在），
      故本函数把两个资源**一起**收进来。

    ------------------------------------------------------------------------
    ⚠️ 为什么是「教职」而不是「任何已登录的人」
    ------------------------------------------------------------------------
    收得越窄越好，而**没有任何学生侧的功能需要读名册**（实测：前端 13 个页面里
    读 ``/api/students`` 的是 4 个教师页 + 3 个管理台页 + 那个 DEV-only 的切换器；
    学生页一律走 ``/api/students/{id}/home`` 那类按人收窄的窄端点）。
    若只要求「有会话」，一个学生就能读全校 60 人的 ``birth``，
    于是「给一个**还没绑定**的同学抢先把口令绑上」这一档仍然敞着
    （绑定端点只对 ``password_hash IS NULL`` 的行放行，故它挡不住抢占）。
    要求教职把这一档也关掉了。

    ⚠️ **代价（硬规矩 #39，如实记）**：一个匿名调用方今天读不到学生名册了。
    受影响的三个既有消费者都已经在 Plan 05A 里改过了：前端 4 个教师页与 3 个管理台页
    现在都在路由守卫之后（``/t/*`` 要 ``staff``、``/admin/*`` 要 ``admin``），
    ``smoke.mjs`` 一律先登录。

    ⚠️⚠️ **本处此前还有第二句，而它是假的**（终审 I3）：原文是「而『大屏匿名可读』
    那一档没有被推翻：大屏读的是 ``/api/dashboard/*``（仍然匿名），不是名册」。
    实测：匿名 ``GET /api/dashboard/class/1?week=6&as_of=2025-10-12`` → **401** ——
    ``dashboard`` 那 6 个端点自 Plan 03 Task 8（``415db83``）起就各自挂着
    ``Security(TEACHER_STAFF_NO_SCHEME)`` / ``Security(STUDENT_ID_SCHEME)``，
    故那一句**写下来的当天就是假的**，不是后来才过期的。
    ⚠️ 于是「收紧名册的代价可接受」这一格**不再拿它当依据**：真正的依据是上面那三条
    （三个既有消费者都已在路由守卫之后 / ``smoke.mjs`` 一律先登录），它们与大屏无关。

    ⚠️⚠️ **「哪些读今天还匿名」的账面只有一个住址**：:mod:`app.api.routers.catalog`
    模块 docstring 里「只读 ⇒ 缺省匿名 …… 自 Plan 05A Task 5 起有了 2 个例外」那一段。
    本处、``api/schemas/auth.py``、``api/schemas/organisation.py``、``api/routers/auth.py``、
    ``api/routers/dashboard.py``、``api/routers/feedback.py`` 一律**只指过去、不复述**
    —— 复述就是第二个所有者，而终审 I3 数出来的那 8 处假话正是这么长出来的。
    ⚠️ 待清扫波又收进来两个同族的漏网（``api/schemas/feedback.py`` 与
    ``api/schemas/dashboard.py``），并改对了 **3 处前提已假**的复述
    （``api/schemas/organisation.py`` 的 ``TeacherRead`` 两句 +
    ``api/routers/catalog.py`` 的 ``teachers`` 行一句「``GET /api/teachers``
    是匿名的」；三处实测都是 **401**）。

    ⚠️ 它**必须与 ``Security(TEACHER_STAFF_NO_SCHEME)`` 成对挂**（与
    :func:`_require_admin_identity` 同一条口径、同一段理由，刻意不抄第二份）：
    本函数负责**判定**，那一个负责**声明**。守卫是 ``tests/api/test_crud.py`` 的
    ``test_the_two_roster_resources_admit_only_staff_reads``（三拍：匿名 401 /
    **不在册的工号** 403 / 教师与管理员 200，并逐个断言 openapi 里 ``security``
    那一格在）。
    ⚠️⚠️ **本处此前逐字写的是「三拍：匿名 401 / 学生会话 403 / 教师与管理员 200」，
    而中间那一拍与那条守卫实际测的不同**（安全收紧波实测复核）：守卫测的是
    ``X-Teacher-Staff-No: T2099999``（一个**不在册**的工号）→ 403，
    不是「学生会话」。「学生会话」那一档在**请求头通道**下实测是 **401**
    （``X-Student-Id`` 对 :func:`app.api.deps.current_teacher` 而言等于「没有教师身份」），
    只有在 **cookie 通道**下才是 403（跨 kind）。两档都拒绝，
    逐字实测与理由住在 ``tests/api/test_crud.py`` 的
    ``test_the_student_keyed_resources_admit_four_read_tiers`` 的 ②′ 那一段。

    ⚠️⚠️ **安全收紧波给本函数加了第三个消费者**：``weekly-class-reports``。
    理由是它虽然是**班级键**，
    而它的 ``progress_board`` JSON 列里逐条带 ``student_id`` + ``change_pct``
    （实测原文开头是 ``{"top_n": 10, "top": [{"student_id": 10,
    "change_pct": 235.88}, …]}``，即「本周进步榜 top 10」）。
    ⚠️ 它收不成 ``student_self``：``student_id`` 埋在一个 JSON 列**里面**，
    SQL 层的 ``WHERE`` 够不着它。逐字依据写在
    :data:`app.api.routers.catalog.RESOURCES` 那一行的注释里。
    ⚠️ 于是本函数今天的三个消费者是 2 份名册 + 1 份班级周报，
    而上面那两段「为什么是教职而不是任何已登录的人」的论证**对第三个同样成立**
    （学生端一个页面都不读它，实测 ``views/**`` 里只有教师页 ``ClassReport.vue``）。
    ⚠️⚠️ **Plan 06 Task 8b 把那第三个消费者的 ``read_scope`` 从 ``"staff"``
    改成第五档 ``"staff_taught_section"``**（Task 8 顶回 2 的落点：任何教师能读到
    **别的班**那份周报的 ``progress_board``），而**本函数仍然是它的身份闸门**
    ——第五档收的是「哪个教师能读哪一行」，不是「谁能打这个端点」，
    故学生那一档的码（请求头 401 / cookie 403）逐字不变。

    ⚠️⚠️ **它返回 :class:`app.api.deps.ReaderIdentity`，而改前返回 ``None``**
    （Plan 06 Task 8b）。改前它只是一道 pure gate，而第五档要在端点体里知道
    「这一位教职是不是管理员」（管理员越过任教范围）。⚠️ 而 ``role`` **是顺带的**：
    本函数本来就要调 :func:`app.api.deps.require_staff`，而那个函数**返回 role**
    （它的 docstring 逐字：「在册则返回它的 role」），故这一格不多一次查库。
    ⚠️⚠️ **它刻意不是第二个身份解析器**：``staff_no`` 由
    :func:`app.api.deps.current_teacher` 给（与改前逐字同一条链），
    ``role`` 由 :func:`app.api.deps.require_staff` 给（与
    :func:`app.api.deps.current_reader` 的教职那一支**同一个**函数、同一条
    「``role`` 必须新鲜、不读 ``user_session`` 上那份冗余」的口径），
    本函数只是把两格装进那个既有的 dataclass。
    ⚠️ 于是 ``"staff"`` 那一档的用法**逐字不变**（它挂在 ``dependencies=[…]`` 里，
    返回值被 FastAPI 丢弃）；只有第五档把它当**端点形参**用。
    ⚠️ 而它**刻意不复用** :func:`_require_admin_identity`：那一格判的是
    ``role == 'admin'``，而名册的读对普通教师也要开放（教师端的大屏/周报/预警队列
    都要按工号与姓名显示学生与同事）。
    """
    return ReaderIdentity(staff_no=staff_no, role=require_staff(session, staff_no))

#: 作用域钩子的形状：拿到 ORM 行与两个身份（学生 id / 教师工号），不匹配就抛
#: ``HTTPException(403)``。两个身份都是 ``| None``：**缺头不是错误**，
#: 是不是错误由钩子自己决定（``app.api.deps.current_student`` 那种「缺头就 401」
#: 的语义在这里刻意不复用，否则 23 个资源的 list 端点全都要求登录）。
ScopeFn = Callable[[Session, Any, int | None, str | None], None]

#: ``on_delete`` 的三档。三个常量是「哪三档」的唯一所有者：
#: :func:`build_crud_router` 的校验、:data:`app.api.routers.catalog.RESOURCES` 的 23 行、
#: 与 ``tests/api/test_crud.py`` 那条计数守卫都读它们。
ON_DELETE_RESTRICT = "restrict"
ON_DELETE_CASCADE = "cascade"
ON_DELETE_FORBID = "forbid"
ON_DELETE_VALUES = frozenset({ON_DELETE_RESTRICT, ON_DELETE_CASCADE, ON_DELETE_FORBID})

#: ---------------------------------------------------------------------------
#: **``read_scope`` 的五档**（``None`` 是第六种取值，但它是「不声明」）
#: ---------------------------------------------------------------------------
#:
#: 安全收紧波立了前三档，**Plan 06 Task 8 加第四档**（用户裁定「教师账号之间要有
#: 数据隔离」：改前一个教师会话能匿名读完全校 60 人的健康档案，而任教闸门只挂在
#: 大屏 / 周报 / 学生详情那几个**特例**端点上），**Plan 06 Task 8b 加第五档**
#: （Task 8 复核出来的第二处跨范围泄漏：``weekly-class-reports`` 是**班级键**、
#: 却住在「任何在册教职全读」的 ``"staff"`` 档里，而它的 ``progress_board`` JSON 列
#: 逐条带 ``student_id`` + ``change_pct``，故任何教师读得到**别的班**那份进步榜）：
#:
#: ==========================  ==========  ====================================
#: ``read_scope``                匿名         学生 / 教师 / 管理员
#: ==========================  ==========  ====================================
#: ``None``                     **200 全读**  200 全读（参考数据：不含任何学生键）
#: ``"student_self"``           **401**      学生 → 只读自己的行；**教职一律全读**
#: ``"staff_taught"``           **401**      学生 → 只读自己的行；教师 → **只读自己任教
#:                                           班级的学生行**（⚠️ Task 8b 起还读得到
#:                                           「**没有学生所有者、但属于他的班/他本人**」
#:                                           的那一类行，见 :class:`OrphanOwner`）；
#:                                           管理员 → 全读
#: ``"staff_taught_section"``   **401**      学生 → **401/403**（与 ``"staff"`` 同一条
#:                                           闸门）；教师 → **只读自己本学期任教班级的
#:                                           行**（键是**班**、不是学生）；管理员 → 全读
#: ``"staff"``                  **401**      学生 → **401/403**（见下）；教职 → 全读
#: ==========================  ==========  ====================================
#:
#: ⚠️ ``"staff"`` 与 ``"staff_taught_section"`` 两格里学生被拒的**码**在两档通道下不同
#: （请求头 401 / cookie 403），逐字实测与理由住在 ``tests/api/test_crud.py`` 的
#: ``test_the_student_keyed_resources_admit_four_read_tiers`` 的 ②′ 那一段。
#: ⚠️⚠️ 第五档**刻意沿用** :func:`_require_staff_identity` 那一道闸门（而不是
#: :func:`app.api.deps.current_reader`）：后者带一个 ``X-Student-Id`` 请求头形参，
#: 挂上去会让这个**只认教职**的资源在 ``/openapi.json`` 里凭空多出一个它根本不认的
#: 学生头——那是一份反方向的假契约（Plan 04 Task 3 偏离 ⑦ 点名的那个形状）。
#: 于是第五档的身份由 ``_require_staff_identity`` **返回** :class:`ReaderIdentity`
#: 交出来（它本来就要调 :func:`app.api.deps.require_staff`，故 ``role`` 是顺带的），
#: 而 OpenAPI 的 ``security`` / ``parameters`` 两格与 ``"staff"`` 档**逐字相同**。
#:
#: ⚠️⚠️ **``"staff_taught"`` 与 ``"student_self"`` 的差别只在教职那一档**：
#: 学生与匿名两档**逐字相同**。故 ``"staff_taught"`` 读起来是
#: 「``student_self`` **加上**教师按任教范围收窄」，而不是另一套规则——
#: 而 :func:`build_crud_router` 里两档也**共用同一个端点分支**（同一份形参表、
#: 同一份 docstring，差别只有函数体里那一支 ``if``），于是「改了一档忘了另一档」
#: 在结构上不可能发生。
#:
#: ⚠️⚠️ **``"student_self"`` 自本波起在 23 行 ``RESOURCES`` 里有 0 行**（13 行全部改成
#: ``"staff_taught"``）。它**刻意保留**而不是删掉，理由两条（硬规矩 #39 的「许可而不是
#: 断言」那一档，与 :data:`_SELF_CLEARING_ONDELETE` 里的 ``"CASCADE"`` 同形）：
#: ① 它是「学生只读自己的行、**教职全读**」这个形状的唯一住址，删掉它之后
#:    那个形状在代码里就没有名字了，而下一个人要它时会去改 ``staff_taught``
#:    （= 把 13 行的口径一起改掉）；② 工厂里那一支 ``if`` 与 ``staff_taught`` 共用，
#:    故留着它的成本是 0 行代码。
#: ⚠️ 而「它不是死代码」由 ``tests/api/test_crud.py`` 的
#: ``test_the_student_self_tier_still_behaves_as_staff_full_read`` 用一个**合成资源**钉住
#: （与 ``test_an_explicit_pk_alias_overrides_the_automatic_one`` 同一条口径：
#: 一个「有能力、无生产调用方」的档位必须被跑通一次，否则它就是死代码）。
#: ⚠️ 行数分布（7 / 0 / 13 / **1** / **2**，⚠️ Task 8b 把 ``weekly-class-reports``
#: 从 ``"staff"`` 挪进第五档，故最后两格从 0 / 3 变成 1 / 2）由
#: ``test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two``
#: 字面钉住。
#:
#: ⚠️ **它是 ``read_requires_staff`` 的替代品，不是它的补充**（Plan 05A Task 5 加的
#: 那个布尔开关在安全收紧波被删掉了）：``"staff"`` 与 ``read_requires_staff=True`` 的
#: 行为**逐字相同**（同一个 :func:`_require_staff_identity`、同一个
#: ``Security(TEACHER_STAFF_NO_SCHEME)``），留两个开关就是两个所有者，
#: 而下一个人会问「两个都写会怎样」。
#:
#: ⚠️ **``None`` 刻意不是字符串 ``"anonymous"``**：23 行 ``RESOURCES`` 一律**字面写出**
#: ``"read_scope"`` 这个键（守卫 ``test_every_resource_declares_read_scope_explicitly``
#: 断言的是**键在不在**，与 ``on_delete`` / ``require_admin`` 那两条同一条口径），
#: 于是「忘了写」不再是「静默退回匿名可读」——那正是本波要消灭的失效形态。
READ_SCOPE_STUDENT_SELF = "student_self"
READ_SCOPE_STAFF_TAUGHT = "staff_taught"
#: **第五档**（Plan 06 Task 8b）：**班级键**的资源按「我本学期任教的班」收窄。
#:
#: 它与第四档**同构**，只是键从学生换成班：list 加
#: ``WHERE <班级键列> IN (:func:`app.api.deps.taught_section_ids`)``、read-one 用
#: **同一个表达式**做一次点查（:func:`_require_row_matches`），故「list 里看得见、
#: 点进去 403」与反过来都在结构上不可能发生。判据仍然只有一个所有者
#: （:func:`app.api.deps.taught_section_ids`，第四档的
#: :func:`app.api.deps.taught_student_ids` 就是它的 ``IN (…)` 消费者）。
#:
#: ⚠️ **它刻意不复用** :class:`StudentOwner`：那一格声明的是「这张表的**学生**键在哪」，
#: 而第五档的资源身上**没有**学生键（``weekly_class_report`` 的 ``student_id`` 埋在
#: ``progress_board`` 那个 JSON 列**里面**，SQL 的 ``WHERE`` 够不着它）。
#: 硬塞进去会让「学生键」这个词同时指两种东西。故第五档另有一个形参
#: ``section_column``（同样**逐行显式声明**、不靠推断，见工厂的第 12 / 13 / 14 道校验）。
#:
#: ⚠️ **学生那一档与 ``"staff"`` 逐字相同**（请求头通道 401 / cookie 通道 403）：
#: 第五档收的是「**哪个教师**能读哪一行」，不是「谁能打这个端点」，
#: 故 :func:`_require_staff_identity` 那一道闸门原样沿用。
READ_SCOPE_STAFF_TAUGHT_SECTION = "staff_taught_section"
READ_SCOPE_STAFF = "staff"
READ_SCOPE_VALUES = frozenset(
    {
        READ_SCOPE_STUDENT_SELF,
        READ_SCOPE_STAFF_TAUGHT,
        READ_SCOPE_STAFF_TAUGHT_SECTION,
        READ_SCOPE_STAFF,
    }
)

#: **按学生键收窄的那两档**（学生只读自己的行；差别只在教职那一档，见上面那张表）。
#:
#: ⚠️ 它是「哪两档要 ``student_owner``」的唯一住址：:func:`build_crud_router` 的
#: 第 9 / 10 道校验、:data:`app.api.routers.catalog.RESOURCES` 那 13 行的声明、
#: 与 ``tests/api/test_crud.py`` 的两条遍历守卫都读它。写成两档而不是
#: ``== READ_SCOPE_STUDENT_SELF`` 是本波的一次**修正**：改前那两处逐字写的是
#: ``read_scope == READ_SCOPE_STUDENT_SELF``，而第四档一加进去，它们就会对 13 行
#: **视而不见**（派单 §0 逐字点名了这件事：「该遍历守卫要同步」）。
STUDENT_SCOPED_READ_VALUES = frozenset({READ_SCOPE_STUDENT_SELF, READ_SCOPE_STAFF_TAUGHT})

#: :func:`_child_tables` 要**跳过**的两种 ``ondelete``（P3-B4）。
#:
#: 跳过的理由是「DB 自己会处理，故它挡不住删除」：
#:
#: * ``SET NULL`` —— 实测 ``notification.alert_id`` 与 ``notification.prescription_id``
#:   都带它（Plan 03 Task 2 的顶回 3 加的）。删一条 ``alert`` 时 SQLite 自己把那两个列
#:   置 NULL，**不报 FK 违例**。不跳过的话，``_child_tables(Alert)`` 会返回
#:   ``("notification", "alert_id")``，于是 ``DELETE /api/alerts/{id}`` 报
#:   「1 行 notification 仍指向它」——一句**假话**，而且它挡的是一次本来能成功的删除。
#: * ``CASCADE`` —— DB 自己会删子行，同样挡不住父行被删。
#:   ⚠️ **今天全库没有一个外键带 ``CASCADE``**（实测），故这一档在
#:   :func:`_child_tables` 里是**许可而不是断言**；把它列进来的理由是
#:   ``on_delete="cascade"`` 那一档的删除靠 :func:`_purge_where` **自己**删子行，
#:   若将来有人给某个外键加了 DB 级 ``CASCADE``，两边就会各删一次
#:   （第二次是空操作，不炸，但「谁负责删」变成两个所有者）。
#:
#: ``ondelete`` 为 ``None``（今天 28 张表的 20 个外键里的 18 个）才是「真的会挡住」。
#: ⚠️ ``"SET DEFAULT"`` 刻意**不在**这个集合里：SQLite 支持它，但本库没有任何一列有
#: DB 级缺省值可供回填，加了就是把一个不存在的档位当成存在。
#: 守卫是 ``tests/api/test_crud.py`` 的
#: ``test_child_tables_skips_the_foreign_keys_that_clear_themselves``。
_SELF_CLEARING_ONDELETE = frozenset({"SET NULL", "CASCADE"})


@dataclasses.dataclass(frozen=True)
class CrudSchemas:
    """一个资源的三个 Pydantic 模型。**frozen**：它在
    :data:`app.api.routers.catalog.RESOURCES` 的 23 行里被字面写出来，
    可变化会让「哪一行改了什么」变成运行时才能回答的问题。

    ``create`` 与 ``update`` 可空是**只读资源**的形状（23 个里有 **14** 个只读）：
    只读资源不注册 POST / PATCH，于是那两个模型不存在，``None`` 比
    「造两个永远用不上的类」诚实。可写的那 **9** 个一律三件齐全。

    ⚠️ ``writable=True`` 而这两个之一是 ``None`` 是**配置错误**，
    :func:`build_crud_router` 在工厂体里当场抛 ``ValueError``——那发生在
    ``import app.api.routers.catalog`` 的那一刻，故 ``uvicorn`` 根本起不来，
    不会退化成「POST 端点在运行时炸」。
    """

    read: type[BaseModel]
    create: type[BaseModel] | None = None
    update: type[BaseModel] | None = None


#: :attr:`OrphanOwner.by` 的两档判据。两个常量是「哪两档」的唯一所有者：
#: :func:`_orphan_condition` 的分派、:func:`build_crud_router` 的第 15 道校验、
#: 与 :data:`app.api.routers.catalog.RESOURCES` 那 2 行的声明都读它们
#: （与 :data:`ON_DELETE_VALUES` / :data:`READ_SCOPE_VALUES` 同一条口径）。
#:
#: ⚠️⚠️ **本波（Plan 06 Task 8b）加的是「第二根轴」，而它修的是一格 Critical**：
#: 第四档 :data:`READ_SCOPE_STAFF_TAUGHT` 的判据是**学生键**，于是一行**没有**学生
#: 所有者的数据被一并挡掉，**包括它自己那个班的任课教师**——而失效方向是**静默的**
#: （响应 200、只是少一行）。两类行都是生产路径会产出的形状
#: （:func:`app.pipeline.alert_stage.evaluate_alerts` 末段那个「班级级：全量遍历本学期
#: 的教学班」的循环逐字写 ``student_id=None, course_section_id=section_id``，
#: 并顺带 ``_notify(recipient_kind=RECIPIENT_TEACHER, recipient_id=teacher_id)``）。
ORPHAN_BY_TAUGHT_SECTION = "taught_section"
#: 那一列装的是 ``course_section.id``，判据是「**我本学期任教的班**」
#: （:func:`app.api.deps.taught_section_ids`，与第四档的学生集合同一条链的上半段）。
#: ⚠️ 这一档**额外**要求主轴那一列 ``IS NULL``：一行若**有**学生所有者、
#: 而那个学生不在我的班里，它**不得**因为「挂在我的班上」就变可见
#: （那会把「谁在这个班里但不在我的任教范围」这一格摊出来）。
ORPHAN_BY_TEACHER_SELF = "teacher_self"
#: 那一列装的是 ``teacher.id``，判据是「**就是我自己**」。
#: ⚠️ 教师会话下「我作为学生的 id」**不存在**（:class:`ReaderIdentity` 的三格互斥），
#: 故这一档**只**在教职那一支被读到；学生那一支走 :func:`_owner_filter`，
#: 它只认 :attr:`StudentOwner.kind` 声明的那一个种类（``'student'``），
#: 于是「学生读到发给教师的站内信」与「教师读到发给学生 4 的站内信」两个方向都挡着
#: （两个 id 空间是独立的自增序列，必然重叠）。
ORPHAN_BY_VALUES = frozenset({ORPHAN_BY_TAUGHT_SECTION, ORPHAN_BY_TEACHER_SELF})


@dataclasses.dataclass(frozen=True)
class OrphanOwner:
    """**「一行没有学生所有者时，它属于哪位教师」的声明**（Plan 06 Task 8b 的第二根轴）。

    它**不是**一个平行的所有者类，而是 :class:`StudentOwner` 上的**一根轴**：
    「这一行有没有学生所有者」与「没有的话按哪一格判」是**同一行数据**的两个问题，
    拆成两个类的话，``RESOURCES`` 那 2 行就要各挂两格声明，而「两格之间对不对得上」
    （例如主轴是 ``recipient_id``+``kind='student'``、第二根轴却写了一个别的列）
    就变成一个只有人能回答的问题。⚠️ 于是「哪个资源有哪几根轴」仍然只有一个住址。

    今天的 **2** 个消费者（逐行声明在 :data:`app.api.routers.catalog.RESOURCES`）：

    ==================  ============================================  ==============
    资源                  声明                                          行可见 ⟺
    ==================  ============================================  ==============
    ``alerts``          ``column="course_section_id"``                ``student_id`` 在我的学生集
                        ``by=ORPHAN_BY_TAUGHT_SECTION``                **或**（``student_id IS NULL``
                                                                       且 ``course_section_id``
                                                                       在我的任教班集）
    ``notifications``   ``column="recipient_id"``                     ``recipient_kind='student'``
                        ``by=ORPHAN_BY_TEACHER_SELF``                  且 ``recipient_id`` = 我作为
                        ``kind=("recipient_kind", "teacher")``          学生的 id **或**
                                                                       ``recipient_kind='teacher'``
                                                                       且 ``recipient_id`` = 我作为
                                                                       教师的 id
    ==================  ============================================  ==============

    ⚠️ **两个资源的两根轴形状确实不同**（一个是「NULL + 班级集」、一个是「另一种
    ``kind`` + 我自己的 id」），而它们被收成**一根轴的两档**而不是两个类，
    判据是「两档回答的是**同一个问题**：这一行没有学生所有者，那它凭什么对**我**可见」。
    两档各自需要的材料只有一格不同（**拿什么去比**：一个集合 / 一个 id），
    故 :attr:`by` 就是那一格。⚠️ 而比的对象（:attr:`column`）与「怎么认出这是无主行」
    （:attr:`kind`，或主轴那一列 ``IS NULL``）两档**共用**。

    ⚠️ **它只影响教职那一档**：学生那一支（:func:`_owner_filter`）**一个字节都没改**，
    故一个学生仍然读不到班级级预警、也读不到发给教师的站内信
    （守卫是 ``tests/api/test_crud.py`` 的
    ``test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student`` 的 ①②③）。
    ⚠️ 管理员**两根轴都放开**（``_reader_filter`` 里那一支 ``is_admin`` 在
    第二根轴之前，故本类对管理员不参与判定）。⚠️ 匿名仍然 ``401``
    （:func:`app.api.deps.current_reader` 当场拒，根本到不了这里）。
    """

    #: 无主行上承载「它属于哪个教师侧实体」的那一列
    #: （``course_section.id`` 或 ``teacher.id``，由 :attr:`by` 决定是哪一种）。
    column: str
    #: 拿 :attr:`column` 去比什么：:data:`ORPHAN_BY_TAUGHT_SECTION`（我本学期任教的班集）
    #: 或 :data:`ORPHAN_BY_TEACHER_SELF`（我自己那一行的 ``teacher.id``）。
    by: str
    #: 多态键在**无主那一支**要等于的 ``(种类列名, 值)``；``None`` = 不是多态键。
    #: ⚠️ 它与 :attr:`StudentOwner.kind` 是**同一个列的两个不同取值**
    #: （今天恰好 1 行：``notification.recipient_kind`` 的 ``'student'`` / ``'teacher'``），
    #: 故工厂的第 15 道校验断言两者若都在，**列名必须相同**——
    #: 否则「哪一列决定这一行属于谁」就有两个答案了。
    kind: tuple[str, str] | None = None


@dataclasses.dataclass(frozen=True)
class StudentOwner:
    """**「这张表上哪一格是它的学生所有者」的唯一声明**（安全收紧波）。

    它是 :data:`STUDENT_SCOPED_READ_VALUES` 那**两档**
    （``student_self`` / ``staff_taught``）的配套参数，而它存在的理由是
    「学生键」在本库有**三种形状**，一种推断规则覆盖不了（派单逐字警告过：
    「不要靠『字段里有 student_id 就自动收紧』的推断——推断就是第二个所有者，
    且会漏掉 ``enrollments`` 这种双键的」）：

    1. **直接列**（11 个资源）：``StudentOwner()`` 就够了——``column`` 的缺省值
       是 ``"student_id"``。⚠️ ``enrollment`` 也在这一档：它另外还带
       ``course_section_id``，但「这一行属于谁」由 ``student_id`` 回答。
    2. **多态列**（1 个资源：``notification``）：``recipient_id`` 那一格装的是
       ``student.id`` **还是** ``teacher.id``，由并排的 ``recipient_kind`` 决定。
       故声明是 ``StudentOwner(column="recipient_id",
       kind=("recipient_kind", "student"))``——少了 ``kind`` 那一格，
       学生 4 会读到发给教师 4 的站内信。
    3. **经外键**（1 个资源：``weekly_adjustment``）：它身上**没有**学生列，
       而 ``prescription_id`` 指向的 ``prescription`` 行上有。故声明是
       ``StudentOwner(column="prescription_id", via=("prescription", "student_id"))``。

    ⚠️ **四个消费方，一份声明**（派单 §2 第 3 条「read-one 的 403 与 list 的过滤
    要共用一个判据（单一所有者）」；⚠️ 安全收紧波从两个抬到三个，
    **Plan 06 Task 8b 抬到四个**）：
    :func:`_owner_filter` 用它拼 list 的 ``WHERE``（学生那一档）、
    :func:`_taught_filter` 用它拼 list 的 ``WHERE``（教师那一档，Plan 06 Task 8）、
    :func:`_orphan_condition` 用它拼 list 的 ``WHERE`` 的**第二根轴**
    （教师那一档的「无主行」那一支，Plan 06 Task 8b）、
    :func:`_owner_of_row` 用它从一行上取值再交给
    :func:`app.api.deps.require_scope`（学生）或
    :func:`app.api.deps.require_teaches_student`（教师）判 403。四者都**只**读这一个
    dataclass，故「list 放行了而 read-one 挡住」这类分叉在结构上不可能发生。
    ⚠️ 而 read-one 那一侧的**无主行**判定（:func:`_require_row_readable` 的第三支）
    用的正是 :func:`_orphan_condition` 返回的**同一个表达式对象**做一次点查
    （:func:`_require_row_matches`），故第二根轴也**没有**第二份判据。

    ⚠️ ``via`` 那一档假定中间表的主键叫 ``id``：全库 28 张表都是单列 ``id`` 主键，
    守卫是 ``tests/api/test_crud.py::test_every_table_has_a_single_column_primary_key``。
    工厂体里还会当场校验中间表**确实有**那两列（导入期 ``ValueError``，
    于是写错一个列名不会退化成「过滤条件恒假 → 学生看到空列表」）。
    """

    #: 承载所有者值的那一列（``student.id`` 的字面量）。
    column: str = "student_id"
    #: 多态键：``(种类列名, 它必须等于的值)``；``None`` = 不是多态键。
    kind: tuple[str, str] | None = None
    #: 间接键：``(中间表名, 中间表上那个所有者列名)``；``None`` = ``column`` 就是所有者。
    via: tuple[str, str] | None = None
    #: **第二根轴**（Plan 06 Task 8b）：一行**没有**学生所有者时，
    #: 它凭什么对某一位教师可见。``None`` = 这张表没有第二根轴，
    #: 于是无主行对任何教师都是 ``403`` / list 里不出现（= Task 8 的既有口径，
    #: 今天 13 行里有 **11** 行仍然是它）。⚠️ 它**只在教职那一支被读到**：
    #: 学生那一支走 :func:`_owner_filter`，一个字节都没改。
    #: 逐字的形状与两个消费者见 :class:`OrphanOwner`。
    orphan: OrphanOwner | None = None


def _owner_filter(model: type[Any], owner: StudentOwner, me: int) -> ColumnElement[bool]:
    """按学生键收窄的那两档的 list 端点那个 ``WHERE``（**学生那一档**）：
    **只留所有者是 ``me`` 的行**。

    ⚠️ **它在 SQL 层过滤**（派单 §2 第 2 条）：60 人 × 840 条打卡时，
    「拉全量再在 Python 里筛」是分页意义的反面——``LIMIT 200`` 会先截断
    **别人的**行，于是「我的第 1 页」可能是空的。
    ⚠️ ``total`` 也走同一个条件（:func:`build_crud_router` 里那一句），
    否则前端分页器会按全表算页数。

    ⚠️ ``column`` 可空时（实测 ``alert.student_id`` 就是可空的：班级级预警没有主人）
    ``WHERE student_id = :me`` 对 ``NULL`` 行**天然不匹配**（SQL 的三值逻辑），
    故不需要额外写一句 ``IS NOT NULL``。
    """
    conditions: list[ColumnElement[bool]] = []
    if owner.kind is not None:
        kind_column, kind_value = owner.kind
        conditions.append(getattr(model, kind_column) == kind_value)
    if owner.via is None:
        conditions.append(getattr(model, owner.column) == me)
    else:
        middle_name, middle_owner_column = owner.via
        middle = Base.metadata.tables[middle_name]
        conditions.append(
            getattr(model, owner.column).in_(
                select(middle.c["id"]).where(middle.c[middle_owner_column] == me)
            )
        )
    return and_(*conditions)


def _taught_filter(
    model: type[Any], owner: StudentOwner, teacher_id: int | None, semester_id: int
) -> ColumnElement[bool]:
    """``read_scope="staff_taught"`` 的 list 端点那个 ``WHERE``（**教师那一档**）：
    **只留所有者是「他本学期任教的学生」的行**。

    ------------------------------------------------------------------------
    ⚠️⚠️ 判据不在本函数里，而在 :func:`app.api.deps.taught_student_ids`
    ------------------------------------------------------------------------
    本函数只负责「把那个集合接到**这张表的**学生键上」，即
    ``<学生键列> IN (那一条 SELECT)``。「哪些学生算他任教的」这件事
    （``enrollment ⋈ course_section.teacher_id``，且两行的 ``semester_id`` 都必须
    等于本学年那一个）**只有一个住址**，而 :func:`app.api.deps.require_teaches_student`
    （教师侧那两个特例端点的 403 闸门）读的是同一条语句——
    于是「list 里看得见他的行、点进详情却 403」这类分叉在结构上不可能发生
    （派单 §1 第 3 条逐字要求的「复用同一个判据，不要写第二个」）。

    ------------------------------------------------------------------------
    ⚠️ 它在 SQL 层过滤，且 ``total`` 走同一个条件
    ------------------------------------------------------------------------
    与 :func:`_owner_filter` 同一条理由（那一段是它的唯一散文，本处不抄第二份）：
    60 人 × 840 条打卡时，「拉全量再在 Python 里筛」是分页意义的反面——
    ``LIMIT 200`` 会先截断**别人的**行。故这里拼的是一个 ``IN (子查询)``，
    而 :func:`_list_page` 把同一个 ``where`` 同时挂到 ``COUNT`` 与 ``SELECT`` 上，
    于是教师读到的 ``total`` 是「**我任教的学生**的行数」（实测演示库上
    T0001 的 ``training_log`` 是 574 行，不是全表 840）。

    ------------------------------------------------------------------------
    ⚠️⚠️ 三种学生键形状逐档说（与 :class:`StudentOwner` 的三档一一对应）
    ------------------------------------------------------------------------
    1. **直接列**（11 个资源）：``student_id IN (子查询)``。
       ⚠️ ``column`` 可空时（实测 ``alert.student_id`` 就是可空的：班级级预警没有主人）
       ``IN`` 对 ``NULL`` 行**天然不匹配**（SQL 的三值逻辑）——而那一格在
       **Plan 06 Task 8b 之前**是一格 Critical：班级级预警因此对**任何**教师都不可见，
       包括它自己那个班的任课教师，而失效方向是**静默的**（200、只是少一行）。
       今天它由第二根轴接住：``alerts`` 声明了
       ``OrphanOwner(column="course_section_id", by=ORPHAN_BY_TAUGHT_SECTION)``，
       故那个 ``WHERE`` 是 ``student_id IN (…)` **OR** ``(student_id IS NULL AND
       course_section_id IN (我本学期任教的班))``（逐字理由见 :func:`_orphan_condition`）。
    2. **多态列**（1 个资源：``notification``）：``recipient_kind = 'student'``
       **且** ``recipient_id IN (子查询)``。⚠️ 于是**发给教师的站内信**
       （``recipient_kind='teacher'``，同样由 ``alert_stage`` 的班级级那一段产出）
       在 Task 8b 之前对任何教师都不可见——与上一档同一格 Critical。
       今天它由第二根轴接住：``notifications`` 声明了
       ``OrphanOwner(column="recipient_id", by=ORPHAN_BY_TEACHER_SELF,
       kind=("recipient_kind", "teacher"))``，故那位教师读得到**发给他的**那些行。
    3. **经外键**（1 个资源：``weekly_adjustment``）：
       ``prescription_id IN (SELECT id FROM prescription WHERE student_id IN (子查询))``。
       两层 ``IN`` 都在 SQL 里，故仍然是**一次**往返。
       ⚠️ 它**没有**第二根轴（工厂的第 15 道校验当场挡下 ``via`` + ``orphan`` 并存），
       故它的无主行（中间那行处方已不在）对任何教师仍然 ``403``。

    ⚠️ ``semester_id`` 由调用方解析（:func:`app.pipeline.percentile_stage.current_semester_of`
    是「哪一个是本学年」的唯一所有者），本函数**不自己猜**——与
    :func:`app.api.deps.require_teaches_student` 同一条口径。
    ⚠️⚠️ 第二根轴的 ``taught_section`` 那一档**也吃同一个 ``semester_id``**
    （:func:`app.api.deps.taught_section_ids` 的第二个入参），故「我**本学期**任教的班」
    与「我**本学期**任教的学生」两根轴不会一个判学期、一个不判
    （那正是 :func:`app.api.deps.require_teaches_section` 与
    :func:`app.api.deps.taught_section_ids` 之间那一格有意的差别，
    而它在泛型读这一圈**不适用**：list 与 read-one 必须给出同一个答案）。
    """
    taught = taught_student_ids(teacher_id, semester_id)
    conditions: list[ColumnElement[bool]] = []
    if owner.kind is not None:
        kind_column, kind_value = owner.kind
        conditions.append(getattr(model, kind_column) == kind_value)
    if owner.via is None:
        conditions.append(getattr(model, owner.column).in_(taught))
    else:
        middle_name, middle_owner_column = owner.via
        middle = Base.metadata.tables[middle_name]
        conditions.append(
            getattr(model, owner.column).in_(
                select(middle.c["id"]).where(middle.c[middle_owner_column].in_(taught))
            )
        )
    owned = and_(*conditions)
    # ⚠️ **第二根轴**（Plan 06 Task 8b）：主轴是 ``AND`` 出来的一个合取式，
    #    而两根轴之间是 ``OR``。⚠️ 判据本身**不在这里**（在 :func:`_orphan_condition`），
    #    本处只负责「把它 OR 上来」——于是 read-one 那一侧拿到的与 list 这一侧
    #    是**同一个函数**产出的表达式（:func:`_require_row_readable` 的第三支）。
    orphan = _orphan_condition(model, owner, teacher_id, semester_id)
    return owned if orphan is None else or_(owned, orphan)


def _orphan_condition(
    model: type[Any], owner: StudentOwner, teacher_id: int | None, semester_id: int
) -> ColumnElement[bool] | None:
    """**第二根轴**：一行**没有**学生所有者时，它对哪一位教师可见。``None`` = 没有这根轴。

    ------------------------------------------------------------------------
    ⚠️⚠️ 它是「无主行可见性」这个判据在 SQL 层的**唯一住址**，两个消费者
    ------------------------------------------------------------------------
    :func:`_taught_filter`（list 的 ``WHERE``，把它 ``OR`` 到主轴上）与
    :func:`_require_row_readable` 的第三支（read-one：拿**同一个表达式对象**
    对那一行做一次点查，见 :func:`_require_row_matches`）。
    故「list 里看得见、点进去 403」与反过来两个方向都不可能发生——
    那不是靠两处写对，而是靠**只有一处**。

    ------------------------------------------------------------------------
    两档（:attr:`OrphanOwner.by`）
    ------------------------------------------------------------------------
    * :data:`ORPHAN_BY_TAUGHT_SECTION`（今天 1 行：``alerts``）→
      ``<主轴那一列> IS NULL AND <那一列> IN (我本学期任教的班)``。
      ⚠️ **``IS NULL`` 那一格是承重的**（派单 §1 的裁定逐字写了它）：
      少了它，一行**有**学生所有者、而那个学生不在我的任教范围里的预警，
      会仅因为「它挂在我教的那个班上」就变可见——那正是第四档要挡的形状
      （实测 ``alert_stage`` 的学生级那一段写的是
      ``student_id=<id>, course_section_id=None``，故两列**恰好一个**非空
      —— 由 ``ck_alert_subject_is_exactly_one`` 强制，于是本格在**今天的写入方**下
      与不加它等价；而它是「将来有人给学生级预警也填上班」时唯一挡得住的一格，
      定点变异取证见实现者报告）。
    * :data:`ORPHAN_BY_TEACHER_SELF`（今天 1 行：``notifications``）→
      ``recipient_kind = 'teacher' AND recipient_id = 我作为教师的 id``。
      ⚠️ 这一档**不加** ``IS NULL``：``notification.recipient_id`` 是 NOT NULL，
      「这一行不属于任何学生」由**种类列**回答，不是由 NULL 回答
      （故 :attr:`OrphanOwner.kind` 在这一档是必填的，工厂的第 15 道校验挡它）。

    ⚠️ **它只在教职那一支被读到**：学生那一支走 :func:`_owner_filter`，
    一个字节都没改，故一个学生仍然读不到班级级预警、也读不到发给教师的站内信。
    ⚠️ 管理员那一支在 :func:`_reader_filter` 里**先于**本函数返回 ``None``（全读），
    故本函数对管理员根本不参与判定。
    """
    orphan = owner.orphan
    if orphan is None:
        return None
    conditions: list[ColumnElement[bool]] = []
    if orphan.by == ORPHAN_BY_TAUGHT_SECTION:
        conditions.append(getattr(model, owner.column).is_(None))
    if orphan.kind is not None:
        kind_column, kind_value = orphan.kind
        conditions.append(getattr(model, kind_column) == kind_value)
    if orphan.by == ORPHAN_BY_TAUGHT_SECTION:
        conditions.append(
            getattr(model, orphan.column).in_(
                taught_section_ids(teacher_id, semester_id)
            )
        )
    else:
        # ⚠️ ``teacher_id`` 可空时（:func:`app.api.deps.teacher_id_of` 查无此人）
        #    ``= NULL`` 恒不成立 → 空集，与 :func:`app.api.deps.taught_student_ids`
        #    的同名一档逐字同一条口径（失效方向是「少给数据」）。
        conditions.append(getattr(model, orphan.column) == teacher_id)
    return and_(*conditions)


def _owner_of_row(session: Session, row: Any, owner: StudentOwner) -> int:
    """按学生键收窄的那两档（:data:`STUDENT_SCOPED_READ_VALUES`）的 read-one
    那一次取值：**这一行的学生所有者是谁**。

    ⚠️ 返回 :data:`app.api.deps.NOT_STUDENT_OWNED`（``-1``）而不是 ``None``
    的两档：① 多态键的 ``kind`` 不匹配（一行发给**教师**的通知）；
    ② 那一格本身是 ``NULL`` / 中间行已不在。两档都是「这行不属于任何学生」，
    而 :func:`app.api.deps.require_scope` 与
    :func:`app.api.deps.require_teaches_student` 的入参都是 ``int``——折成一个哨兵
    就能把判定**整个交给它们**，不必在这里写第二份 ``raise HTTPException(403)``
    （那正是派单点名不要的「第二份过滤逻辑」）。哨兵的逐字理由住在
    :data:`app.api.deps.NOT_STUDENT_OWNED` 的注释里，本处不抄第二份。
    ⚠️⚠️ **而第四档（``staff_taught``）拿到这个哨兵之后走哪一支，Plan 06 Task 8b 改过**：
    改前它一律 ``403``（于是班级级预警与发给教师的站内信对**任何**教师都不可见，
    只有管理员读得到——那一格 Critical 的逐字取证住在 :func:`_taught_filter` 的
    docstring 第 1 / 2 档）；今天 :func:`_require_row_readable` 在哨兵那一支改问
    **第二根轴**（:func:`_orphan_condition`）：声明了 :attr:`StudentOwner.orphan`
    的 2 行按它判（相关教师 ``200``、其余 ``403``），没声明的 11 行**逐字保持**
    改前的 ``403``。⚠️ 学生那一支**一个字节都没改**：哨兵交给
    :func:`app.api.deps.require_scope`，它的第一支（``-1 != requester_id``）当场 ``403``，
    故一个学生永远读不到无主行。
    """
    if owner.kind is not None:
        kind_column, kind_value = owner.kind
        if getattr(row, kind_column) != kind_value:
            return NOT_STUDENT_OWNED
    value = getattr(row, owner.column)
    if value is None:
        return NOT_STUDENT_OWNED
    if owner.via is None:
        return int(value)
    middle_name, middle_owner_column = owner.via
    middle = Base.metadata.tables[middle_name]
    found = session.scalar(
        select(middle.c[middle_owner_column]).where(middle.c["id"] == value)
    )
    return NOT_STUDENT_OWNED if found is None else int(found)


def _current_semester_id(session: Session) -> int:
    """「本学年」那个学期的 id。**只由第四 / 第五档的教师那一支调用**
    （⚠️ Plan 06 Task 8b 加了第五档 ``staff_taught_section``，它也要这一个学期）。

    ⚠️ 它是「哪一个是本学年」这件事在本模块的唯一读点，而判据**不在这里**：
    :func:`app.pipeline.percentile_stage.current_semester_of`（优先 ``is_current``、
    退化到「包含那一天的学期区间」、都找不到就**响亮失败**）。
    :func:`app.api.deps.require_teaches_student` 的第四个入参要的也是它
    （那两处调用方是 :mod:`app.api.routers.dashboard` 的两个特例端点，
    它们各自把 ``as_of`` 传进去）。

    ⚠️⚠️ **本处传的是 ``dt.date.today()``，而两个特例端点传的是 ``as_of``**
    （一个查询参数，缺省也是今天）。差别只在「库里没有 ``is_current`` 的学期」那一档：
    那时 ``current_semester_of`` 退化到「包含那一天的区间」，而泛型 list **没有**
    ``as_of`` 这个参数。⚠️ 给它加一个 = 26 个 GET 各多一个查询参数进 OpenAPI
    （而前端一个都不传），代价远大于收益，故本波不加，如实记录（硬规矩 #39）。
    ⚠️ 而它在生产路径上**不可达**：``semester.is_current`` 由
    ``app.seed.organisation`` 铺、由管理台的 ``PATCH /api/semesters`` 改，
    演示库实测恰好一行 ``is_current=1``（``id=2``），故第一档就命中、
    ``today()`` 根本不参与判定。

    ⚠️ 它**每次请求都查一次**（刻意不缓存）：缓存会把「管理员改了 ``is_current``
    之后什么时候生效」变成一个进程级的隐式状态，而那正是本仓一路在消灭的形状。
    代价是一次 ``semester`` 表上的点查，且只发生在**教师**会话的第四 / 第五档读上
    （学生那一支与管理员那一支都不调本函数）。
    """
    return current_semester_of(session, dt.date.today()).id


def _reader_filter(
    session: Session,
    model: type[Any],
    owner: StudentOwner,
    reader: ReaderIdentity,
    read_scope: str,
) -> ColumnElement[bool] | None:
    """按学生键收窄的那两档共用的「list 的 ``WHERE``」；``None`` = **不过滤**。

    ⚠️ **它是「哪一档按什么过滤」的唯一分派点**（Plan 06 Task 8 抽出来的）：
    :func:`build_crud_router` 里 ``list_rows`` 的函数体因此仍然只有一行 ``return``，
    而「学生 / 教师 / 管理员」三档的判定不在端点体里——端点体里写 ``if`` 的话，
    两个端点分支（``list_rows`` 与 ``read_one``）就各有一份，
    而它们的失效形态是**不对称**的（list 放行了、read-one 挡住），
    那正是 :class:`StudentOwner` 那段「四个消费方，一份声明」要防的事。

    三档：

    * **学生** → :func:`_owner_filter`（只留自己的行）。⚠️ 两档
      （``student_self`` / ``staff_taught``）**逐字相同**：第四档改的是教职那一档。
    * **管理员** → ``None``（全读）。⚠️ 越过任教范围的判据是
      :attr:`ReaderIdentity.is_admin`，而它的理由逐字住在
      :func:`app.api.deps.require_teaches_section` 里（本处不抄第二份）。
    * **教师** → 第四档：:func:`_taught_filter`（只留自己本学期任教班级的学生行）；
      ``student_self`` 档：``None``（全读）。
    """
    if reader.is_student:
        return _owner_filter(model, owner, int(reader.student_id))
    if reader.is_admin or read_scope != READ_SCOPE_STAFF_TAUGHT:
        return None
    return _taught_filter(
        model,
        owner,
        teacher_id_of(session, str(reader.staff_no)),
        _current_semester_id(session),
    )


def _section_filter(
    session: Session,
    model: type[Any],
    section_column: str,
    reader: ReaderIdentity,
) -> ColumnElement[bool] | None:
    """第五档（:data:`READ_SCOPE_STAFF_TAUGHT_SECTION`）的「list 的 ``WHERE``」；
    ``None`` = **不过滤**（管理员）。

    ⚠️ 它与 :func:`_reader_filter` **平行而刻意不合并**：那一格分派的是
    「学生 / 教师 / 管理员」三档 × **学生键**，本格只有「教师 / 管理员」两档 ×
    **班级键**，且第五档的学生那一支**根本到不了这里**
    （:func:`_require_staff_identity` 已经把学生会话拒在端点之外）。
    合并成一个函数的话，它的入参要同时接受 ``StudentOwner | None`` 与
    ``section_column: str | None``，而「两个都给」与「两个都不给」两档都是配置错误
    ——那正是工厂第 12 / 13 道校验在**导入期**挡的事，不该留到运行时再判一次。

    ⚠️⚠️ **判据仍然只有一个所有者**：:func:`app.api.deps.taught_section_ids`。
    第四档的 :func:`app.api.deps.taught_student_ids` 就是它的 ``IN (…)`` 消费者，
    而 :func:`app.api.deps.require_teaches_section` 那道闸门问的是**另一个**问题
    （「这一个班是不是他的」，**不判学期**；两格差别的逐字理由住在那个函数的
    docstring 里）。⚠️ 于是本档**判学期**，与第四档逐字同一条口径：
    一位上学期教过某个班的教师，这学期读不到那个班那份周报
    （「上学期教过」不等于「这学期能读」）。

    ⚠️ **管理员 → ``None``**（全读），判据是 :attr:`ReaderIdentity.is_admin`，
    与 :func:`_reader_filter` 里那一支**同一个**属性（理由的住址在
    :func:`app.api.deps.require_teaches_section`，两处都不抄第二份）。
    ⚠️ 而它**是承重的**：管理员通常不带任何班，不放行的话管理台的
    ``ResourceList.vue`` 对这一格会是空的（与第四档同一条理由）。
    """
    if reader.is_admin:
        return None
    return getattr(model, section_column).in_(
        taught_section_ids(
            teacher_id_of(session, str(reader.staff_no)), _current_semester_id(session)
        )
    )


def _require_row_matches(
    session: Session,
    model: type[Any],
    pk: str,
    obj: Any,
    where: ColumnElement[bool],
    detail: str,
) -> None:
    """把 list 那一个 ``WHERE`` **就地用在一行上**（read-one 的 ``403``）。

    ⚠️⚠️ 它是「list 与 read-one 同源」这条纪律在**执行侧**的落点（Plan 06 Task 8b）：
    ``where`` 由调用方从**同一个**构造函数拿（:func:`_orphan_condition` /
    :func:`_section_filter`），本函数只把它挂到一条按主键的点查上。
    于是「list 里看得见、点进去 403」与反过来两个方向都不可能发生——
    不是靠两处各写对一遍，而是靠**判据只有一份**。

    ⚠️ 它**不重新解析**「哪一位教师 / 哪一个学期」：两格都已经烧在 ``where`` 里了，
    故本函数不知道也不关心 ``read_scope`` 是哪一档、更不查库去猜。

    ⚠️ **代价（硬规矩 #39，如实记）**：多一次点查。而它是
    ``WHERE <pk> = :pk AND <那个条件>``，走主键，故与 :func:`_get_or_404` 那一次
    ``session.get`` 同阶。⚠️ 而「为什么不改成在 Python 里比那一行的字段」：
    那就要在这里**重算**一遍判据（``taught_section_ids`` 的 SQL 语义、``NULL`` 的
    三值逻辑、``IN`` 对重复值不敏感……），那正是本函数要消灭的第二份判据。

    ⚠️ ``detail`` 由调用方给：两档（无主行 / 别的班）要说的是两句不同的人话，
    而本函数不知道自己在判哪一档。
    """
    column = getattr(model, pk)
    found = session.scalar(select(column).where(column == getattr(obj, pk), where))
    if found is None:
        raise HTTPException(status_code=403, detail=detail)


def _require_orphan_row_readable(
    session: Session,
    model: type[Any],
    pk: str,
    obj: Any,
    owner: StudentOwner,
    reader: ReaderIdentity,
) -> None:
    """一行**没有学生所有者**时，第四档 read-one 的那一支判定（第二根轴）。

    ⚠️⚠️ **本函数就是 Task 8 顶回 1 的落点**：改前那一行会带着
    :data:`app.api.deps.NOT_STUDENT_OWNED`（``-1``）走进
    :func:`app.api.deps.require_teaches_student` 并一律得到 ``403``
    （``enrollment`` 里没有 ``student_id = -1`` 的行），于是**班级级预警**与
    **发给教师的站内信**对任何教师都不可见——包括它自己那个班的任课教师。
    今天它改问 :func:`_orphan_condition`（**与 list 那一个 ``OR`` 支同一个函数**）。

    ⚠️ **没有第二根轴的那 11 行逐字保持改前的 ``403``**：本函数第一支就抛，
    于是「给一张表加 ``orphan`` 声明」是**唯一**能让无主行对教师变可见的动作
    （定点变异取证见实现者报告）。

    ⚠️ 它**不复用** :func:`app.api.deps.require_teaches_section`，理由两条：
    ① 那道闸门**不判学期**（它的 docstring 逐字写了为什么），而 list 那一侧的
    :func:`_orphan_condition` 判（它吃 :func:`_current_semester_id`）——
    两侧不同源就是本仓一路在消灭的那个失效形态；
    ② 第二根轴还有 :data:`ORPHAN_BY_TEACHER_SELF` 那一档
    （「这一行是发给**我**的」），而 ``deps`` 里今天没有那样一道闸门
    （它是 :func:`app.api.deps.require_scope` 的教职对偶，而那一格还没有第二个消费者）。
    于是两档一律走 :func:`_require_row_matches`，**一个**判据、**一个** ``403`` 住址。

    ------------------------------------------------------------------------
    ⚠️⚠️ 而「管理员越过」这一格**必须由本函数自己判**（本波实测出来的一格红）
    ------------------------------------------------------------------------
    有学生所有者的那一支不需要这样一句：它整个委托给
    :func:`app.api.deps.require_teaches_student`，而那道闸门自己第一句就是
    ``require_staff(...) == ADMIN_ROLE → return``。本格**没有**那样一道闸门可委托
    （理由逐字见上面那段），故少了这一句的话管理员读一条班级级预警会 ``403``——
    而 list 那一侧 :func:`_reader_filter` 的 ``is_admin`` 明明放行了它，
    于是「列表里看得见、点进去 403」这个本仓一路在消灭的失效形态**当场复活**。
    ⚠️ 判据与 :func:`_reader_filter` / :func:`_section_filter` 里那一支是
    **同一个** :attr:`ReaderIdentity.is_admin`，故「管理员越过任教范围」仍然只有一个住址。

    ------------------------------------------------------------------------
    ⚠️⚠️ ``403`` 的 message **刻意不复述内部实现**（本波收窄的一次信息泄漏）
    ------------------------------------------------------------------------
    改前它逐字把第二根轴的判据原文吐给了调用方（含模块路径
    ``app/api/crud.py``、函数名 ``_orphan_condition`` 与档位常量
    ``taught_section`` / ``teacher_self``）。⚠️ 那是**给实现者读的话被发给了调用方**：
    一个不该看到这一行的调用方因此额外学到了「服务端有哪几个模块、判据长什么样」。
    今天它只说**调用方自己那一侧的事实**（这一行不属于任何学生、而它挂的班不是他
    本学期任教的 / 收件人不是他本人）+ **那一列的名字**——列名不算内部标识符：
    它同时是这个资源 ``read`` schema 里的一个字段名，本来就在这次响应的邻域里。
    ⚠️ 口径与 :mod:`app.api.deps` 里既有的那些 ``403`` 逐字同族
    （:func:`app.api.deps.require_teaches_section` 的 message 也写着
    「判据是 ``course_section.teacher_id``」，而它从不写函数名与模块路径）。
    守卫是 ``tests/api/test_crud.py`` 的
    ``test_the_read_denial_messages_do_not_disclose_internal_identifiers``。
    """
    if reader.is_admin:
        return  # 管理员两根轴都放开（判据是 ReaderIdentity.is_admin，理由见上）
    where = _orphan_condition(
        model,
        owner,
        teacher_id_of(session, str(reader.staff_no)),
        _current_semester_id(session),
    )
    if where is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f"{model.__tablename__} 的这一行不属于任何学生，"
                f"故它对教师一律不可见（只有管理员读得到）"
            ),
        )
    orphan = owner.orphan
    # ⚠️ **本行不是死代码，而它的注释此前写错了**（Plan 06 Task 12 / C7 实测更正）：
    #    改前它逐字写着「（反空转，**不可达**）」。实测：把本行换成一句必炸的
    #    ``raise`` 再跑 ``tests/api`` + ``tests/integration`` + ``tests/architecture``，
    #    **28 条测试走到它**（``/api/alerts`` 与 ``/api/notifications`` 两个
    #    多态键资源的教师档读，一律经本函数）。故它是**被执行**的。
    #    ⚠️ 而「它**不可能失败**」那半句仍然成立：``where is None`` 那一支上面已经
    #    ``raise`` 掉了，而 :func:`_orphan_condition` 只在 ``owner.orphan is not None``
    #    时才回一个非 ``None`` 的表达式 —— 两句话是不同的性质
    #    （「跑不到」vs「跑到了也不会红」），改前把它们混成了一格。
    #    ⚠️ 于是**保留**它：它是「那两条性质漂开了」时唯一会响的地方，
    #    而删掉它的收益是 0（一行 assert）、代价是把一档静默失效放回来。
    assert orphan is not None  # ``where is not None`` 已经蕴含它（不会失败，但会被执行）
    if orphan.by == ORPHAN_BY_TAUGHT_SECTION:
        reason = (
            f"它挂的教学班不是教师 {reader.staff_no!r} 本学期任教的班"
            f"（判据是 {orphan.column}）"
        )
    else:
        reason = (
            f"它的收件人不是教师 {reader.staff_no!r} 本人"
            f"（判据是 {orphan.kind[0] if orphan.kind else orphan.column} "
            f"与 {orphan.column}）"
        )
    _require_row_matches(
        session,
        model,
        pk,
        obj,
        where,
        f"{model.__tablename__} 的这一行没有学生所有者，而{reason}",
    )


def _require_section_readable(
    session: Session,
    model: type[Any],
    pk: str,
    section_column: str,
    obj: Any,
    reader: ReaderIdentity,
) -> None:
    """第五档（:data:`READ_SCOPE_STAFF_TAUGHT_SECTION`）read-one 的 ``403`` 判定。

    ⚠️ 与 :func:`_section_filter` 成对，而两者读的是**同一个函数**产出的表达式
    （管理员那一档得到 ``None`` = 不过滤 = 不抛）。故「list 里没有它、
    但 ``GET {path}/{id}`` 200」与反过来都不可能发生。

    ⚠️⚠️ **本函数就是 Task 8 顶回 2 的落点**：改前 ``weekly-class-reports`` 是
    ``read_scope="staff"``（任何在册教职全读），而泛型 **read-one 含全部 JSON 列**，
    故任何教师能读到**别的班**那份周报的 ``progress_board``
    （= 那个班进步榜 top 10 的 ``student_id`` + ``change_pct``）。
    ⚠️ 而特例端点 ``GET /api/dashboard/weekly-class-report/{id}`` **早就有**
    :func:`app.api.deps.require_teaches_section`，故前端页面上看不出这一格——
    泄漏面是 **API**，不是 UI。

    ⚠️⚠️ ``403`` 的 message **刻意不复述内部实现**：改前它逐字写着
    「判据是 ``course_section_id ∈ app.api.deps.taught_section_ids``」——
    一个模块路径 + 一个函数名被发给了调用方。口径与理由逐字见
    :func:`_require_orphan_row_readable` 那一段（本处不抄第二份），
    守卫也是同一条
    （``test_the_read_denial_messages_do_not_disclose_internal_identifiers``）。
    """
    where = _section_filter(session, model, section_column, reader)
    if where is None:
        return  # 管理员：越过任教范围（理由的住址在 require_teaches_section）
    _require_row_matches(
        session,
        model,
        pk,
        obj,
        where,
        (
            f"{model.__tablename__} 的这一行挂的教学班不是教师 {reader.staff_no!r} "
            f"本学期任教的班（判据是 {section_column}）"
        ),
    )


def _require_row_readable(
    session: Session,
    model: type[Any],
    pk: str,
    obj: Any,
    owner: StudentOwner,
    reader: ReaderIdentity,
    read_scope: str,
) -> None:
    """按学生键收窄的那两档共用的「read-one 的 ``403``」判定。

    ⚠️ 与 :func:`_reader_filter` 成对（一个是 list 的 ``WHERE``、一个是 read-one 的
    ``403``），而两者读**同一份** :class:`StudentOwner` 声明与**同一个** ``read_scope``，
    故「list 里看得见、点进去 403」这类分叉在结构上不可能发生。
    ⚠️ **Plan 06 Task 8b 给它加了 ``model`` 与 ``pk`` 两个入参**：第三支
    （无主行）要把 list 那一个 ``WHERE`` 就地用在这一行上，而那需要主键列。

    ⚠️⚠️ **三支判定**（前两支整个交给 :mod:`app.api.deps` 里既有的闸门，
    派单 §2 第 3 条「不要写第二份过滤逻辑」）：

    * 学生 → :func:`app.api.deps.require_scope`（不是本人 / 不在册，两档都 ``403``）；
    * 教师（第四档）+ **这一行有学生所有者** →
      :func:`app.api.deps.require_teaches_student`
      （不在他本学期任教的班里 → ``403``）。⚠️ **管理员的越过不由本函数判**：
      那道闸门自己第一句就是 ``require_staff(...) == ADMIN_ROLE → return``，
      于是「管理员越过任教范围」在**读的一侧**只有一个住址
      （写的一侧是 :func:`app.api.deps.require_admin`，那是另一件事）。
      ⚠️ 而 :func:`_reader_filter` 里那一支 ``is_admin`` **是**本模块自己判的——
      因为「不过滤」不是一次闸门调用，没有一个既有的函数可以委托。
      两处读的都是同一个 :attr:`ReaderIdentity.is_admin`，故判据仍然只有一份。
    * 教师（第四档）+ **这一行没有学生所有者** →
      :func:`_require_orphan_row_readable`（第二根轴，Plan 06 Task 8b）。
      ⚠️ 这一支**不走** ``deps`` 的闸门，逐字理由住在那个函数里。
    * ``student_self`` 档的教职 → 直接返回（全读，既有口径）。
    """
    owned_by = _owner_of_row(session, obj, owner)
    if reader.is_student:
        require_scope(session, owned_by, int(reader.student_id))
        return
    if read_scope != READ_SCOPE_STAFF_TAUGHT:
        return
    if owned_by == NOT_STUDENT_OWNED:
        _require_orphan_row_readable(session, model, pk, obj, owner, reader)
        return
    require_teaches_student(
        session, str(reader.staff_no), owned_by, _current_semester_id(session)
    )


def _json_text_columns(model: type[Any]) -> tuple[str, ...]:
    """``model`` 的全部 :class:`~app.db.models._shared.JsonText` 列名（按声明序）。

    **``list_exclude`` 的自动探测就是本函数**（P3-B3）。为什么自动探测而不是让 23 行
    逐个手抄：实测全库 21 个 ``JsonText`` 列，其中 **19 个**落在这 23 个资源上
    （另 2 个是 ``cleaning_log.original_value`` / ``processed_value``，而 ``cleaning_log``
    不是资源），分布在 **8** 张表：``prescription`` 与 ``weekly_class_report`` **各 5 个**、
    ``derived_metrics`` 3 个、``interest_survey`` 2 个，
    ``stratification_result`` / ``exercise`` / ``mini_test`` / ``alert`` 各 1 个。
    手抄 19 个列名，抄漏一个就是**一次全表 JSON 拉取**——而它是静默的：
    响应仍然正确，只是变慢（Plan 02 Task 7 的性能回归正是「大 JSON 列 eager 加载」，
    ``elapsed`` 一度到 115 s）。反过来「多排除一列」的后果轻得多：read-one 里还能拿到。

    ⚠️ 判据是 ``isinstance(c.type, JsonText)``，即**列的 SQLAlchemy 类型**，
    不是列名、也不是 ``Mapped[...]`` 的标注。故加一个 ``JsonText`` 列会自动被排除，
    不必有人记得改 23 行里的某一行。全库那个「21」由
    ``tests/db/test_models.py::test_no_column_uses_builtin_sqlalchemy_json`` 钉住。
    """
    return tuple(
        column.name
        for column in model.__table__.columns
        if isinstance(column.type, JsonText)
    )


def _child_tables_of(table: Table) -> list[tuple[str, str]]:
    """:func:`_child_tables` 的表级实现。签名与理由见那个函数。"""
    found: list[tuple[str, str]] = []
    for other in Base.metadata.tables.values():
        for foreign_key in other.foreign_keys:
            if foreign_key.column.table is not table:
                continue  # 出向的、或指向别的表的
            if (foreign_key.ondelete or "").upper() in _SELF_CLEARING_ONDELETE:
                continue  # DB 自己会处理，故它挡不住删除（P3-B4）
            found.append((other.name, foreign_key.parent.name))
    return sorted(set(found))


def _child_tables(model: type[Any]) -> list[tuple[str, str]]:
    """**入向**外键：谁指着 ``model``，返回 ``[(子表名, 子表的那一列名), …]``（升序去重）。

    ⚠️ **``model.__table__.foreign_keys`` 给的是出向外键**（我指向谁），
    而 ``on_delete="restrict"`` 要回答的是反过来的问题（谁指向我）。
    后者**不在模型上**，只能扫 :data:`Base.metadata` 的全部 28 张表（P3-B4）。

    ⚠️ 于是本函数有一条**导入期依赖**：``Base.metadata`` 必须已经装满 28 张表。
    这在生产路径上恒成立——:mod:`app.api.routers.catalog` 的第一行就 import
    ``app.db.models``（它 ``from . import audit, auth, feedback, prescription``，故 28 张全注册），
    而本函数在**请求期**才被调用。⚠️ 但它也因此在
    ``import app.api.crud`` 的**那一刻**是可能不完整的，故本函数刻意**不在工厂体里
    预算一次并缓存**：预算会把「metadata 装满了没有」变成一个导入顺序问题，
    而按请求算的代价是一次 28 张表 × 各自外键的遍历，只发生在 DELETE 上。

    **必须排除 ``ondelete`` 为 ``SET NULL`` / ``CASCADE`` 的外键**，理由与实测证据见
    :data:`_SELF_CLEARING_ONDELETE`。一句话：``notification.alert_id`` 带
    ``ON DELETE SET NULL``，删一条 ``alert`` 时 SQLite 自己置 NULL、**不报错**，
    故 ``notification`` 不是「挡住删除 ``alert`` 的子表」。
    """
    return _child_tables_of(model.__table__)


def _purge_where(session: Session, table: Table, condition: ColumnElement[bool]) -> None:
    """删掉 ``table`` 中满足 ``condition`` 的行，**先删它们的后代**。

    ``on_delete="cascade"`` 的实现。递归而不是「删一层子表」：
    子表的子表也指着子表，先删子表同样是 FK 违例。
    ⚠️ **今天只有 ``class_session`` → ``rpe_record`` 一层**（``rpe_record`` 没有子表），
    故深度 ≥ 2 的那条递归边**没有测试覆盖**（硬规矩 #39）。它在图上可达的形状是
    ``student`` → ``prescription`` → ``weekly_adjustment``，而 ``students`` 的
    ``on_delete`` 是 ``restrict``、永远走不到这里。

    ⚠️ **顺序是承重的**（P7-A4）：``PRAGMA foreign_keys=ON`` 由
    :func:`app.db.session._sqlite_foreign_keys_on` 在每条连接上打开，
    故先删父表会当场 ``FOREIGN KEY constraint failed``。守卫是
    ``tests/api/test_crud.py::test_on_delete_cascade_deletes_children_first``。

    ⚠️ **主键取 ``table.primary_key`` 的第一列**：28 张表的主键都是单列 ``id``，
    守卫是 ``test_every_table_has_a_single_column_primary_key``。
    复合主键会让本函数**静默只按第一列删**（删多了），故那条守卫是本函数的前提。

    用 Core 的 :func:`~sqlalchemy.delete` 而不是 ORM 的 ``session.delete``：
    级联删的是「一批子行」，逐行 ``session.delete`` 要先 SELECT 出全部对象，
    而一次 ``DELETE … WHERE fk IN (…)`` 就够。
    """
    primary_key = next(iter(table.primary_key.columns))
    identifiers = [row[0] for row in session.execute(select(primary_key).where(condition))]
    if not identifiers:
        return  # 空集：递归的终止条件，也避免发一条 WHERE … IN () 的废语句
    for child_name, child_column in _child_tables_of(table):
        child = Base.metadata.tables[child_name]
        _purge_where(session, child, child.c[child_column].in_(identifiers))
    session.execute(delete(table).where(primary_key.in_(identifiers)))


def _get_or_404(session: Session, model: type[Any], pk_value: int) -> Any:
    """``session.get`` + 显式 404（P3-B7）。

    ⚠️ **不给 :mod:`app.db.repo` 加 ``get_or_404``**：那个模块是 Plan 01 的，
    公开面只有 ``upsert`` 与 ``delete_by_batch`` 两个函数、且被
    ``tests/db/test_repo.py`` 的公开面基线钉着；而 ``session.get`` 是 SQLAlchemy 的
    原生 API，包一层只是多一个住址。

    用 ``session.get`` 而不是 ``select(...).scalar_one()``：前者走 identity map
    （同一请求里第二次取同一行是免费的），后者每次发一条 SELECT。
    代价是 404 由**本函数**抛而不是由 ``NoResultFound`` 经
    :mod:`app.api.errors` 折出来——两者都落到 ``code == "not_found"``，
    但消息是中文的、且带上主键值（前端要能说出「哪一行没了」）。
    """
    obj = session.get(model, pk_value)
    if obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"{model.__tablename__} 里没有主键为 {pk_value} 的行",
        )
    return obj


def _list_page(
    session: Session,
    model: type[Any],
    kept: list[str],
    order_column: Any,
    page: Page,
    where: ColumnElement[bool] | None,
) -> dict[str, Any]:
    """泛型 list 端点的那个响应体。

    ⚠️ **它是「list 的形状」的唯一所有者**（安全收紧波抽出来的）：
    :func:`build_crud_router` 里那两个 ``list_rows`` 分支（``read_scope`` 是不是
    :data:`STUDENT_SCOPED_READ_VALUES` 里的一档）各是一行 ``return``，都调本函数。
    抽出来的理由不是省字，
    而是**分页信封的四个键**与「``total`` 和 ``items`` 必须走同一个 ``WHERE``」
    这两件事只能有一个住址——写在两支里的话，下一个人给一支加了过滤而忘了另一支，
    失效形态是「学生会话的 ``items`` 只有自己的行、而 ``total`` 是全表 840」，
    前端分页器于是给出一个翻不到的页数（派单 §2 第 2 条点名的那一格）。

    ⚠️ ``where is None`` = **不过滤**（管理员、``student_self`` 档的教职、
    与 7 个匿名参考数据资源）。
    ⚠️ 过滤在 **SQL 层**：``where`` 由 :func:`_reader_filter` 分派给
    :func:`_owner_filter`（学生）或 :func:`_taught_filter`（教师），
    ``LIMIT`` / ``OFFSET`` 作用在**已过滤**的行上，故「我的第 1 页」永远是满的。
    """
    count_statement = select(func.count()).select_from(model)
    statement = select(*[getattr(model, name) for name in kept]).order_by(order_column)
    if where is not None:
        count_statement = count_statement.where(where)
        statement = statement.where(where)
    total = session.scalar(count_statement)
    rows = session.execute(
        statement.limit(page.limit).offset(page.offset)
    ).all()
    return {
        "items": jsonable_encoder([dict(zip(kept, row)) for row in rows]),
        "total": total,
        "limit": page.limit,
        "offset": page.offset,
    }


def _conflict_message(table_name: str, natural_key: tuple[str, ...]) -> str:
    """撞自然键时那句 409 的 ``message``。

    ⚠️ **只引列名、绝不引约束名**（P3-B5）：23 个资源里有 **5 张表的唯一约束是无名的**
    （``semester.name`` / ``teacher.staff_no`` / ``student.student_no`` /
    ``exercise.ref`` / ``prescription_template.template_ref``，实测
    ``UniqueConstraint.name is None``），把 ``uq.name`` 插进 f-string 会渲染成字面
    ``"None"``，而这句话是要显示给教师看的。

    ⚠️ **也绝不引提交上来的值**：值可能是 ``None``（``str(None)`` == ``"None"``）、
    也可能很长（``weekly_adjustment.reason`` 是自由文本）。前端本来就知道自己提交了什么，
    它需要的是「哪几列撞了」。

    守卫是 ``tests/api/test_crud.py`` 的
    ``test_a_conflict_message_names_the_key_columns_and_never_the_literal_none``
    （它遍历全部 20 个有自然键的资源、对每一个都断言 ``"None" not in message``）。
    """
    return f"{table_name} 已经存在同一组自然键（{', '.join(natural_key)}）的行"


def _pk_alias_of(path: str) -> str:
    """资源路径 → **OpenAPI 路径参数名**的缺省推导（P4-A6：资源路径的单数 + ``_id``）。

    ``"/api/semesters"`` → ``"semester_id"``、``"/api/course-sections"`` →
    ``"course_section_id"``、``"/api/fitness-test-results"`` → ``"fitness_test_result_id"``
    （三个都是计划 P4-A6 逐字点名的例子）。规则只有两步：去掉末尾那个 ``s``
    （23 个资源路径**全部**是复数，守卫是 ``tests/api/test_crud.py`` 的
    ``test_every_resource_path_is_a_hyphenated_plural_under_api``），
    再把连字符换成下划线（URL 用连字符、字段名用下划线，见模块 docstring 那张对照表），
    最后接 ``_id``。

    ⚠️ **它是纯 OpenAPI 层的改名，不动 DB、不动路由匹配**：DB 的主键列仍叫 ``id``
    （``pk`` 那个形参管的是它），而 Starlette 的路由匹配只看「这一段是不是一个占位符」，
    不看占位符叫什么。故本函数的输出**只影响**三件事：URL 模板的字面
    （``/api/semesters/{semester_id}``）、``/openapi.json`` 里那个 parameter 的 ``name``、
    以及据此生成的 TS 客户端里那个形参的名字。

    ⚠️ **推导出来的 23 个名字里有一大半恰好与别的表引用这张表时的外键列同名**
    （``semester_id`` / ``student_id`` / ``prescription_id`` / ``course_section_id`` …），
    这不是巧合：那 23 个资源名本来就是表名的复数。于是前端在
    ``GET /api/prescriptions/{prescription_id}`` 与
    ``POST /api/weekly-adjustments {"prescription_id": …}`` 两处看到的是同一个名字。

    ⚠️ **末尾不是 ``s`` 时原样保留**（``endswith`` 那一支的 ``else``）：23 个资源里
    一个都没有这一档，故它是**许可而不是断言**（硬规矩 #39）；留着是为了让
    ``pk_alias=None`` 的自动档在一个人手滑写了单数路径时给出一个**能读**的名字
    （``"/api/probe"`` → ``"probe_id"``），而不是 ``"/api/probe"`` → ``"_id"``。
    守卫是 ``tests/api/test_crud.py`` 的
    ``test_the_automatic_pk_alias_is_the_singular_resource_name_plus_id``。

    ⚠️⚠️ **它认不出 ``-es`` 结尾的复数**（同一个守卫钉住了这一格，免得有人以为推导
    比实际聪明）：``"/api/fitness-test-batches"`` 推出来的是 ``"fitness_test_batche_id"``
    ——多一个 ``e``。**这是刻意的**：英语的复数还原是一个有例外的词法问题
    （``batches`` → ``batch`` 去 ``es``，而 ``exercises`` → ``exercise`` 只去 ``s``，
    两者都以 ``ses`` 结尾），在本函数里写一份「sibilant 后缀表」就是给一个 URL 命名
    问题引入第二份词表，而它**必然**是不完备的（``classes`` → ``classe``）。
    故口径是：**推导保持笨而可预测，笨错的那一个资源显式传 ``pk_alias``**。
    23 行里今天只有 ``fitness-test-batches`` 那一行传了
    （:data:`app.api.routers.catalog.RESOURCES` 的注释逐字交代了这件事），
    于是 ``pk_alias`` 的「显式覆盖」档**有生产调用方**、不是死代码。
    """
    tail = path.rsplit("/", 1)[-1]
    singular = tail[:-1] if tail.endswith("s") else tail
    return singular.replace("-", "_") + "_id"


def build_crud_router(
    *,
    model: type[Any],
    schemas: CrudSchemas,
    path: str,
    tags: list[str],
    pk: str = "id",
    pk_alias: str | None = None,
    order_by: str = "id",
    readable: bool = True,
    writable: bool = True,
    require_admin: bool = False,
    read_scope: str | None = None,
    student_owner: StudentOwner | None = None,
    section_column: str | None = None,
    on_delete: str = ON_DELETE_RESTRICT,
    natural_key: tuple[str, ...] | None,
    list_exclude: tuple[str, ...] | None = None,
    scope: ScopeFn | None = None,
) -> APIRouter:
    """给一个资源生成它的 CRUD 路由。23 个资源各调一次，调用参数住在
    :data:`app.api.routers.catalog.RESOURCES`。

    **参数逐个说**（五个端点的形状与三档 ``on_delete`` 见模块 docstring）：

    ``model``
        SQLAlchemy 的表类。⚠️ **23 个里有 11 个不在 :mod:`app.db.models` 的公有导入面上**
        （Ruling 97 / 硬规矩 #102）：``Exercise`` / ``PrescriptionTemplate`` /
        ``Prescription`` / ``WeeklyAdjustment`` 要走
        ``from app.db.models.prescription import …``，``ClassSession`` / ``RpeRecord`` /
        ``TrainingLog`` / ``MiniTest`` / ``Alert`` / ``Notification`` /
        ``WeeklyClassReport`` 要走 ``from app.db.models.feedback import …``。
        写 ``models.Prescription`` 会得到 ``AttributeError``。
        守卫是 ``tests/api/test_crud.py`` 的
        ``test_the_eleven_non_public_models_are_reached_through_their_submodules``。
    ``schemas``
        :class:`CrudSchemas` 三件套。
    ``path``
        **含 ``/api`` 前缀**的完整路径（``"/api/course-sections"``），复数 + 连字符。
        本工厂不再加前缀，故 :data:`app.api.routers.catalog.RESOURCES` 里那 23 个串
        与前端要打的 URL **逐字相同**。
    ``tags``
        OpenAPI 的分组标签。``/docs`` 按它折叠，23 个资源各一组。
    ``pk`` / ``order_by``
        主键列名与排序列名，今天 23 行全用缺省的 ``"id"``（见模块 docstring 的
        「刻意不做的事」）。
    ``pk_alias``
        **OpenAPI 路径参数的名字**（P4-A6，Plan 03 Task 4 加）。``None`` → 自动取
        :func:`_pk_alias_of`（资源路径的单数 + ``_id``，``semesters`` → ``semester_id``）；
        显式传则覆盖。⚠️ **它与 ``pk`` 是两件不同的事**：``pk`` 是 **DB 列名**
        （``table.c[pk]``、``getattr(obj, pk)`` 读它），``pk_alias`` 只出现在 URL 模板与
        ``/openapi.json`` 里，**一个字都不碰数据库、也不碰路由匹配**。
        加它的理由逐字照计划：改名之前 23 个 detail 路径的参数名 distinct 是
        ``['pk_value']``（``/api/semesters/{pk_value}``），于是生成的 TS 客户端里到处是
        ``pkValue`` 而不是 ``semesterId``，前端读起来很难受。
        ⚠️ **23 行 ``RESOURCES`` 里恰好有 1 行显式传了它**（``fitness-test-batches``，
        因为自动推导认不出 ``-es`` 结尾的复数，理由见 :func:`_pk_alias_of` 的末段），
        另 22 行走自动档。守卫是 ``tests/api/test_crud.py`` 的
        ``test_every_detail_path_names_its_pk_after_the_resource``（23 个名字逐个从
        ``/openapi.json`` 实读）与
        ``test_an_explicit_pk_alias_overrides_the_automatic_one``（合成资源跑通覆盖那一档）。
    ``readable`` / ``writable``
        两个开关，**互相独立**：``writable=False`` 关掉 POST/PATCH/DELETE，
        ``on_delete="forbid"`` 只关掉 DELETE。
        ``tests/api/test_crud.py`` 的
        ``test_a_forbidden_delete_is_405_even_on_a_writable_resource`` 钉的就是这个独立性。
    ``require_admin``
        **写入侧要不要管理员身份**（Plan 03 全分支终审之后加的，用户 2026-10-08 裁定
        「加强制」；⚠️ **Plan 05A Task 2 把它从 ``require_teacher`` 改名成
        ``require_admin`` 并换掉判定**，用户 2026-10-12 裁定「管理员接管管理台」）。
        ``True`` → ``POST`` / ``PATCH`` / ``DELETE`` 三个端点各挂
        ``dependencies=[Security(TEACHER_STAFF_NO_SCHEME), Depends(_require_admin_identity)]``：
        前者负责**声明**（进 ``/openapi.json`` 那个操作的 ``security`` 一格），
        后者负责**判定**（缺头 401、工号不在册 403）。
        ⚠️ **``GET`` 一律不挂**：大屏与列表要能匿名读（Task 3 的偏离 ⑦ 定的
        「身份头条件注册」，而 :func:`_require_admin_identity` 的 docstring 逐字
        交代了为什么两个必须成对挂）。
        ⚠️ 它有缺省值 ``False``，故 :data:`app.api.routers.catalog.RESOURCES` 的
        **每一行可写资源都必须字面写出** ``"require_admin": True``——漏写会静默
        退回「匿名可写」。守卫有两条：
        ``test_every_writable_resource_declares_require_admin_explicitly``（键在不在）
        与 ``test_every_writable_resource_admits_only_an_admin_mutation``
        （实发请求断三拍：匿名 401 / 普通教师 403 / 管理员放行）。
        ⚠️ ``writable=False`` 的资源**必须**写 ``False``（或省略）：只读资源根本不注册
        那三个端点，挂上去是一件什么也不发生的事，而它会让人以为「这个资源被保护了」。
        工厂体里有一道校验把它挡在导入期（第 7 道）。
    ``read_scope``
        **读取侧（两个 ``GET``）的五档**（Plan 05A Task 5 立的那个布尔开关
        ``read_requires_staff`` 在**安全收紧波**被本参数替代、Plan 06 Task 8 又加了
        第四档、**Plan 06 Task 8b 加了第五档**；五档的逐字表与
        「为什么不是补充而是替代」住在 :data:`READ_SCOPE_STUDENT_SELF` 的注释里）。

        * ``None`` → 两个 GET **匿名可读**（今天 **7** 行：``semesters`` /
          ``course-sections`` / ``fitness-test-batches`` / ``percentile-snapshots`` /
          ``exercises`` / ``prescription-templates`` / ``class-sessions``，
          全是**不含任何学生键**的参考数据与班级/批次级数据）。
        * ``"staff"`` → 匿名 ``401``、学生会话被拒（请求头通道 ``401``、
          cookie 通道 ``403``）、工号不在册 ``403``、在册教职全读。挂
          ``dependencies=[Security(TEACHER_STAFF_NO_SCHEME), Depends(_require_staff_identity)]``。
          ⚠️ 今天 **2** 行：``students`` 与 ``teachers``（那两份名册各自含着
          **绑定口令的全部验身材料**，逐字理由见 :func:`_require_staff_identity`）。
          ⚠️⚠️ ``weekly-class-reports`` **自 Plan 06 Task 8b 起不在这一档**（它挪去了
          第五档，见下面）。它的 ``progress_board`` JSON 列里**逐条带
          ``student_id`` + ``change_pct``**，实测是「本周进步榜 top 10」，
          故它虽然是班级键、却含学生级数据；而它的唯一前端消费者是教师页
          ``views/teacher/ClassReport.vue``，已在 ``/t/*`` 的路由守卫之后。
          ⚠️⚠️ **Plan 06 Task 8 复核出它有一格跨教师泄漏，Task 8b 收掉了**：
          泛型 read-one ``GET /api/weekly-class-reports/{id}`` **含全部 JSON 列**，
          故任何在册教师能读到**别的班**那份周报的 ``progress_board``
          （= 那个班进步榜 top 10 的 ``student_id`` + ``change_pct``）。
          特例端点 ``GET /api/dashboard/weekly-class-report/{id}`` 有自己的
          :func:`app.api.deps.require_teaches_section`，故前端页面上看不出这一格。
          **今天那一行已经挪到第五档 ``"staff_taught_section"``**（见下面那一条），
          故 ``"staff"`` 那一档今天只剩 **2** 行（两份名册）。
        * ``"student_self"`` → 匿名 ``401``、学生会话**只读自己的行**
          （list 在 SQL 层加 ``WHERE``、read-one 不匹配 ``403 forbidden``）、
          **教职会话全读**。⚠️ 今天 **0** 行（13 行全部改成了下面那一档），
          保留它的理由逐字见 :data:`READ_SCOPE_STUDENT_SELF` 的注释。
        * ``"staff_taught"`` → 匿名 ``401``、学生会话**只读自己的行**（与上一档逐字相同）、
          **教师会话只读自己本学期任教班级的学生行**（list 在 SQL 层加
          ``WHERE <学生键> IN (SELECT …)``、read-one 走
          :func:`app.api.deps.require_teaches_student` → ``403``）、
          **管理员全读**（越过任教范围，与两道既有闸门同一条口径）。
          ⚠️⚠️ **Plan 06 Task 8b 给它加了第二根轴**：一行**没有**学生所有者的数据
          （班级级预警 / 发给教师的站内信）改前对**任何**教师都不可见
          （Task 8 顶回 1 的那一格 Critical），今天按
          :attr:`StudentOwner.orphan` 的声明判（相关教师 ``200``、其余 ``403``），
          而没声明的 11 行**逐字保持**改前的 ``403``。
          逐字见 :class:`OrphanOwner` 与 :func:`_orphan_condition`。
          挂 ``dependencies=[Security(STUDENT_ID_SCHEME),
          Security(TEACHER_STAFF_NO_SCHEME)]``（OpenAPI 的数组是 **OR** 语义，
          与 ``student_self`` 那一档**逐字相同**，故本波 openapi 的
          ``security`` 一格一个字节都没变）
          + 端点形参 ``reader: ReaderIdentity = Depends(current_reader)``。
          ⚠️ 今天 **13** 行，逐行清单与「哪几行是间接键」的实测见
          :data:`app.api.routers.catalog.RESOURCES`。
        * ``"staff_taught_section"``（**第五档，Plan 06 Task 8b**）→ 匿名 ``401``、
          学生会话**被拒**（与 ``"staff"`` 逐字相同：请求头通道 ``401`` /
          cookie 通道 ``403``，因为闸门仍然是 :func:`_require_staff_identity`）、
          **教师会话只读自己本学期任教班级的行**（list 在 SQL 层加
          ``WHERE <班级键列> IN (:func:`app.api.deps.taught_section_ids`)``、
          read-one 用**同一个表达式**做一次点查 → ``403``）、**管理员全读**。
          挂 ``dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]``
          + 端点形参 ``reader: ReaderIdentity = Depends(_require_staff_identity)``
          （⚠️ 刻意**不用** :func:`app.api.deps.current_reader`：它带一个
          ``X-Student-Id`` 形参，会让这个只认教职的资源在 OpenAPI 里凭空多出一个
          它根本不认的学生头。故本档的 ``security`` 与 ``parameters`` 两格与
          ``"staff"`` 档**逐字相同**，openapi 五格一个字节都没变）。
          ⚠️ 它还要一个 ``section_column``（**班级键在哪一列**，见下面那一条）。
          ⚠️ 今天 **1** 行：``weekly-class-reports``。

        ⚠️ **它有缺省值 ``None``（= 匿名可读）**，故 23 行 ``RESOURCES``
        **一律字面写出** ``"read_scope"`` 这个键（写 ``None`` 也要写）——
        「忘了写」与「写了 None」在行为上无法区分，而失效方向是
        **静默地退回匿名可读**，那正是安全收紧波要消灭的失效形态。守卫有三条：
        ``test_every_resource_declares_read_scope_explicitly``（键在不在）、
        ``test_every_student_keyed_resource_declares_a_student_scoped_read_scope``
        （遍历 28 张表：凡含 ``student_id`` 列的资源都声明了
        :data:`STUDENT_SCOPED_READ_VALUES` 里的一档，于是「加第 24 个资源而忘了声明」
        与「把它声明成 ``staff``（= 任何教师全读）」都会红）与
        ``test_the_student_keyed_resources_admit_four_read_tiers``
        （实发请求断四档矩阵）。
        ⚠️ **它刻意不与 ``require_admin`` 合并成一个「读也要管理员」的开关**：
        教师端的大屏/周报/预警队列都要读名册与学生键数据
        （``views/teacher/Dashboard.vue`` 读 ``listEnrollments`` + ``listAlerts``、
        ``StudentDetail.vue`` 读 ``listMiniTests`` + ``listStratificationResults`` +
        ``listAlerts``、``AlertQueue.vue`` 读 ``listAlerts`` + ``listEnrollments``），
        把它们也收成管理员会让 Plan 04 的教师端整个不可用。
        ⚠️⚠️ 而**本波（第四档）与「收成管理员」是两件不同的事**：教师仍然读得到
        这些数据，只是范围从「全校」收成「我本学期任教的班的学生」
        （实测演示库上 T0001 是 41 / 60 人、T0002 是 42 / 60 人）。
        ⚠️ 而 ``readable=False`` 时本格无从生效，故工厂体里也有一道校验（第 8 道）。
    ``student_owner``
        :class:`StudentOwner`：``read_scope`` 是
        :data:`STUDENT_SCOPED_READ_VALUES` 那两档之一时**必填**（第 9 道校验），
        其余三档**必须省略**（第 10 道校验）。它回答「这张表上哪一格是学生键」，
        而本库有**三种形状**（直接列 / 多态列 / 经外键），逐字见那个类的 docstring。
        ⚠️ 列名与中间表都在导入期校验（第 11 道），故写错一个列名是
        ``import app.api.routers.catalog`` 当场 ``ValueError``（``uvicorn`` 起不来），
        而不是「运行时 500」或「过滤条件恒假 → 学生看到空列表」。
        ⚠️⚠️ **Plan 06 Task 8b 给它加了第二根轴** :attr:`StudentOwner.orphan`
        （:class:`OrphanOwner`）：它回答「一行**没有**学生所有者时，它凭什么对某一位
        教师可见」。⚠️ 缺省 ``None`` = 没有这根轴 = 无主行对任何教师 ``403``
        （Task 8 的既有口径，13 行里 11 行仍然是它），故**加它是一次显式的放宽**，
        而不是一次静默的推断。它的三格也在导入期校验（第 15 道）。
    ``section_column``
        **第五档**（:data:`READ_SCOPE_STAFF_TAUGHT_SECTION`）的配套参数：
        班级键在哪一列（今天 1 行，逐字是 ``"course_section_id"``）。
        第五档时**必填**（第 12 道校验）、其余四档**必须省略**（第 13 道校验）、
        列名在导入期校验（第 14 道）。
        ⚠️ **它刻意不复用** :class:`StudentOwner`：那一格声明的是**学生**键，
        而第五档的资源身上没有学生键（``weekly_class_report`` 的 ``student_id``
        埋在 ``progress_board`` 那个 JSON 列里面）。逐字理由见
        :data:`READ_SCOPE_STAFF_TAUGHT_SECTION` 的注释。
        ⚠️ 而它**同样不靠推断**（「表上有 ``course_section_id`` 就自动按班收窄」
        会是第二个所有者，且 ``enrollment`` / ``alert`` / ``class_session`` /
        ``mini_test`` 四张表也有那一列、而它们各自的答案不同）。
    ``on_delete``
        三档之一。⚠️ **它有缺省值**，而缺省值是一个陷阱：加第 24 个资源时忘了写它，
        就静默落到 ``restrict``。故
        ``tests/api/test_crud.py::test_every_resource_declares_on_delete_explicitly``
        遍历 ``RESOURCES``、断言每一行都**字面写了** ``"on_delete"`` 这个键
        （缺省值不算显式）。
    ``natural_key``
        **无缺省值**（刻意）：忘了写它就是 ``TypeError``，而不是静默落到
        「没有自然键 → POST 走裸 ``session.add`` → 重复行」。
        非空 → POST 走 :func:`app.db.repo.upsert`，撞键 **409**；
        ``None`` → POST 走裸 ``session.add``，**结构上不可能撞键，故没有 409 这一档**
        （P3-B2；3 个资源是这一档：``course-sections`` / ``fitness-test-batches`` /
        ``notifications``）。
    ``list_exclude``
        ``None`` = **自动探测**（:func:`_json_text_columns`）；显式传元组则**覆盖**探测结果。
        ⚠️ **本处此前印的是「覆盖那一档今天是许可而不是断言：23 行没有一行用它」**，
        那句自 Plan 03 收尾小修波起已经不成立（按实际改写）：``/api/class-sessions``
        那一行显式传了 ``("rpe_token",)``，理由是**那一列是秘密而 list 端点不走
        ``response_model``**（把它从 ``ClassSessionRead`` 上摘掉堵不住 list）。
        ⚠️ 而 P3-B3 原本设想的那个用途（「list 确实要返回某个小 JSON 列」）
        今天仍然没有生产调用方，那一档由
        ``tests/api/test_crud.py::test_an_explicit_list_exclude_overrides_the_auto_detection``
        用合成资源跑通。
    ``scope``
        见 :data:`ScopeFn`。今天 23 行全为 ``None``。

    **返回**：一个 :class:`~fastapi.APIRouter`。调用方
    （:mod:`app.api.routers.catalog`）把它 ``include_router`` 进汇总路由，
    :func:`app.main.create_app` 再 include 那一个。

    ⚠️ **本工厂不碰 ``DB_URL_ENV_VAR`` / ``DEMO_DB_URL``**（P3-B6：那两个常量住在
    :mod:`app.main`，**不在** :mod:`app.api.deps`）。它只从
    :func:`app.api.deps.get_db` 拿一个 ``Session``，故「用哪个库」这件事与它无关。
    """
    if on_delete not in ON_DELETE_VALUES:
        raise ValueError(
            f"on_delete 必须是 {sorted(ON_DELETE_VALUES)} 之一，收到 {on_delete!r}"
            f"（资源 {path}）"
        )
    if writable and (schemas.create is None or schemas.update is None):
        raise ValueError(
            f"{path} 声明了 writable=True，但 CrudSchemas 的 create/update 有 None："
            f"{schemas}。只读资源请写 writable=False。"
        )
    if not writable and on_delete == ON_DELETE_CASCADE:
        raise ValueError(
            f"{path} 是只读资源（writable=False），DELETE 端点根本不注册，"
            f"故 on_delete='cascade' 无从生效。"
        )
    if require_admin and not writable:
        # ⚠️ 第 7 道校验（Plan 03 全分支终审之后加的）。它与上面那道 ``cascade`` 的
        #    理由逐字同构：只读资源根本不注册 POST/PATCH/DELETE，故这一格挂上去是
        #    **一件什么也不发生的事**，而它会让下一个人以为「这个资源被保护了」。
        #    失效形态是静默的（端点没变、OpenAPI 没变、测试也不会红），故挡在导入期。
        raise ValueError(
            f"{path} 是只读资源（writable=False），POST/PATCH/DELETE 三个端点根本不注册，"
            f"故 require_admin=True 无从生效。要保护一个只读资源请给它挂 scope，"
            f"或者把它改成 writable=True + require_admin=True"
        )
    if read_scope is not None and read_scope not in READ_SCOPE_VALUES:
        raise ValueError(
            f"read_scope 必须是 None 或 {sorted(READ_SCOPE_VALUES)} 之一，"
            f"收到 {read_scope!r}（资源 {path}）"
        )
    if read_scope is not None and not readable:
        # ⚠️ 第 8 道校验（Plan 05A Task 5 立的，本波从 read_requires_staff 改名过来）。
        #    与第 7 道（``require_admin`` × ``writable``）逐字同构：``readable=False``
        #    的资源根本不注册两个 GET，故这一格挂上去是**一件什么也不发生的事**，
        #    而它会让下一个人以为「这个资源的读被保护了」。
        #    失效形态是静默的（端点没变、OpenAPI 没变、测试也不会红），故挡在导入期。
        raise ValueError(
            f"{path} 声明了 readable=False，两个 GET 端点根本不注册，"
            f"故 read_scope={read_scope!r} 无从生效"
        )
    if read_scope in STUDENT_SCOPED_READ_VALUES and student_owner is None:
        # ⚠️ 第 9 道校验（安全收紧波；Plan 06 Task 8 把判据从「== student_self」
        #    改成「in 那两档」，于是第四档也要求显式声明学生键）。
        #    ``StudentOwner.column`` **有**缺省值 ``"student_id"``，
        #    故「忘了声明」在 11 个直接键资源上会**恰好**是对的——
        #    而那正是最危险的形态：它对 11 行看起来工作，却在 ``notifications``
        #    （多态键 ``recipient_id``）与 ``weekly-adjustments``（间接键
        #    ``prescription_id``）上**静默地**去过滤一个不存在的 ``student_id`` 列。
        #    于是本档要求「键在哪一列」也逐行显式写出来。
        raise ValueError(
            f"{path} 声明了 read_scope={read_scope!r}，但没有显式给出 student_owner："
            f"「哪一列是这张表的学生键」不得靠缺省值猜（本库有三种形状，见 StudentOwner）"
        )
    if read_scope not in STUDENT_SCOPED_READ_VALUES and student_owner is not None:
        # ⚠️ 第 10 道校验（安全收紧波；判据同步见上一道）。与第 7 / 8 道同一条理由：
        #    这一格只在按学生键收窄的那两档下被读到，留着它会让下一个人以为
        #    「这个资源的读已经按学生收窄了」——而实际两个 GET 照旧全读。
        raise ValueError(
            f"{path} 声明了 student_owner 却把 read_scope 写成 {read_scope!r}："
            f"那一格只在 read_scope 是 {sorted(STUDENT_SCOPED_READ_VALUES)} 之一时生效，"
            f"留着它会让下一个人以为这个资源的读已经按学生收窄了"
        )
    if read_scope == READ_SCOPE_STAFF_TAUGHT_SECTION and section_column is None:
        # ⚠️ 第 12 道校验（Plan 06 Task 8b）。与第 9 道逐字同构：
        #    「班级键在哪一列」不得靠推断——推断就是第二个所有者，
        #    而全库有 **5** 张表带 ``course_section_id`` 列（``enrollment`` /
        #    ``alert`` / ``class_session`` / ``mini_test`` / ``weekly_class_report``），
        #    其中 4 张的答案各不相同（前两张按**学生**收窄、第三张是参考数据、
        #    第四张按学生收窄），故「有那一列就自动按班收窄」会当场收错 3 张。
        raise ValueError(
            f"{path} 声明了 read_scope={read_scope!r}，但没有显式给出 section_column："
            f"「哪一列是这张表的班级键」不得靠推断（全库 5 张表带 course_section_id，"
            f"而其中 4 张的答案各不相同）"
        )
    if read_scope != READ_SCOPE_STAFF_TAUGHT_SECTION and section_column is not None:
        # ⚠️ 第 13 道校验（Plan 06 Task 8b）。与第 7 / 8 / 10 道同一条理由：
        #    这一格只在第五档下被读到，留着它会让下一个人以为
        #    「这个资源的读已经按班收窄了」——而实际两个 GET 照旧。
        raise ValueError(
            f"{path} 声明了 section_column 却把 read_scope 写成 {read_scope!r}："
            f"那一格只在 read_scope={READ_SCOPE_STAFF_TAUGHT_SECTION!r} 时生效，"
            f"留着它会让下一个人以为这个资源的读已经按任教班收窄了"
        )
    columns = {column.name for column in model.__table__.columns}
    for label, names in (
        ("pk", (pk,)),
        ("order_by", (order_by,)),
        ("natural_key", natural_key or ()),
        ("list_exclude", list_exclude or ()),
        # ⚠️ 第 14 道校验（Plan 06 Task 8b）：``section_column`` 与上面四格同一条口径
        #    （写错一个列名的失效形态是**请求时** ``AttributeError`` → 500，
        #    而不是一句导入期的配置错误）。⚠️ ``None`` 那一档折成空元组，
        #    于是本行对**没有**声明第五档的 22 行是一个空操作。
        ("section_column", (section_column,) if section_column else ()),
    ):
        unknown = sorted(set(names) - columns)
        if unknown:
            raise ValueError(
                f"{path} 的 {label} 里有 {model.__tablename__} 不存在的列：{unknown}"
            )
    if student_owner is not None:
        # ⚠️ 第 11 道校验（安全收紧波）。失效形态是**静默的**：写错一个列名会让
        #    ``getattr(model, 列名)`` 抛 ``AttributeError``——但那发生在**请求时**
        #    （``_owner_filter`` 在端点体里跑），于是「一个学生键资源的自过滤坏了」
        #    表现为 500，而不是导入期的一句配置错误。挡在导入期。
        owner_names = [student_owner.column]
        if student_owner.kind is not None:
            owner_names.append(student_owner.kind[0])
        unknown = sorted(set(owner_names) - columns)
        if unknown:
            raise ValueError(
                f"{path} 的 student_owner 里有 {model.__tablename__} 不存在的列："
                f"{unknown}"
            )
        if student_owner.via is not None:
            middle_name, middle_owner_column = student_owner.via
            middle = Base.metadata.tables.get(middle_name)
            if middle is None:
                raise ValueError(
                    f"{path} 的 student_owner.via 指向一个不存在的表 {middle_name!r}"
                )
            for needed in ("id", middle_owner_column):
                if needed not in middle.c:
                    raise ValueError(
                        f"{path} 的 student_owner.via 要求 {middle_name} 有一列 "
                        f"{needed!r}（``id`` 是中间表的主键，本库 28 张表都是单列 id 主键）"
                    )
        if student_owner.orphan is not None:
            # ⚠️ 第 15 道校验（Plan 06 Task 8b，**第二根轴**）。四支，每一支各挡一个
            #    **静默**的失效形态（「过滤条件恒假 → 教师看到一个空列表」，
            #    响应 200、只是少一行——与它要修的那一格 Critical 同一个方向）：
            orphan = student_owner.orphan
            if orphan.by not in ORPHAN_BY_VALUES:
                raise ValueError(
                    f"{path} 的 student_owner.orphan.by 必须是 "
                    f"{sorted(ORPHAN_BY_VALUES)} 之一，收到 {orphan.by!r}"
                )
            orphan_names = [orphan.column]
            if orphan.kind is not None:
                orphan_names.append(orphan.kind[0])
            unknown = sorted(set(orphan_names) - columns)
            if unknown:
                raise ValueError(
                    f"{path} 的 student_owner.orphan 里有 {model.__tablename__} "
                    f"不存在的列：{unknown}"
                )
            if student_owner.via is not None:
                # ⚠️ 间接键 + 第二根轴**今天 0 行**，而它挡的是一格静默陷阱：
                #    ``via`` 那一档的「无主」是「中间行已不在」，此时主轴那一列
                #    **非空**，故 ``taught_section`` 那一支的 ``IS NULL`` 恒假
                #    → 第二根轴一声不响地什么也不放行。要它的人必须先想清楚
                #    「无主」在间接键上是什么意思，而不是在这里悄悄得到一个空集。
                raise ValueError(
                    f"{path} 的 student_owner 同时声明了 via 与 orphan："
                    f"间接键的「无主」是「中间行已不在」（主轴那一列非空），"
                    f"而第二根轴的 taught_section 那一支判的是主轴那一列 IS NULL，"
                    f"两者并存会让第二根轴恒假（静默地不放行任何一行）"
                )
            if orphan.by == ORPHAN_BY_TAUGHT_SECTION:
                if not model.__table__.columns[student_owner.column].nullable:
                    # ⚠️ ``IS NULL`` 那一格是这一档「怎么认出这是无主行」的**唯一**判据，
                    #    而它在一个 NOT NULL 的列上恒假 → 第二根轴静默不放行任何一行。
                    raise ValueError(
                        f"{path} 的 student_owner.orphan.by 是 "
                        f"{ORPHAN_BY_TAUGHT_SECTION!r}，而主轴那一列 "
                        f"{student_owner.column!r} 是 NOT NULL："
                        f"这一档靠「主轴那一列 IS NULL」认出无主行，"
                        f"它在 NOT NULL 的列上恒假（要它请改用 "
                        f"{ORPHAN_BY_TEACHER_SELF!r} + kind 那一格）"
                    )
            elif orphan.kind is None:
                # ⚠️ ``teacher_self`` 那一档的主轴列**非空**（今天恰好 1 行：
                #    ``notification.recipient_id``），故「这一行不属于任何学生」
                #    只能由**种类列**回答。少了 kind，判据退化成
                #    ``recipient_id = 我的 teacher.id``——而两个 id 空间是独立的
                #    自增序列、必然重叠，于是一位教师会读到发给**学生 N**
                #    （N 恰好等于他的 teacher.id）的站内信。
                raise ValueError(
                    f"{path} 的 student_owner.orphan.by 是 "
                    f"{ORPHAN_BY_TEACHER_SELF!r}，但没有给出 kind："
                    f"这一档靠种类列认出无主行（少了它，一个教师会读到"
                    f"recipient_id 恰好等于他 teacher.id 的那些**学生**行）"
                )
            if orphan.kind is not None and student_owner.kind is not None:
                if orphan.kind[0] != student_owner.kind[0]:
                    # ⚠️ 两根轴若各认一个不同的种类列，「哪一列决定这一行属于谁」
                    #    就有两个答案了（而两个答案可能互相矛盾）。
                    raise ValueError(
                        f"{path} 的 student_owner.kind 与 student_owner.orphan.kind "
                        f"认了两个不同的种类列（{student_owner.kind[0]!r} vs "
                        f"{orphan.kind[0]!r}）：两根轴必须读同一列的两个取值"
                    )
                if orphan.kind == student_owner.kind:
                    raise ValueError(
                        f"{path} 的 student_owner.orphan.kind 与 student_owner.kind "
                        f"逐字相同（{orphan.kind!r}）：两根轴于是判同一批行，"
                        f"第二根轴是一次空操作"
                    )
    if not path.startswith("/api/"):
        raise ValueError(f"资源路径必须挂在 /api/ 下（复数 + 连字符），收到 {path!r}")
    alias = _pk_alias_of(path) if pk_alias is None else pk_alias
    if not alias.isidentifier():
        raise ValueError(
            f"{path} 的 pk_alias {alias!r} 不是一个合法的 Python 标识符："
            f"它会逐字成为 URL 模板里的占位符名与 /openapi.json 里那个 parameter 的 name，"
            f"而 openapi-typescript / orval 一类的生成器会直接把它当形参名用"
        )

    table = model.__table__
    excluded = (
        tuple(list_exclude) if list_exclude is not None else _json_text_columns(model)
    )
    kept = [column.name for column in table.columns if column.name not in excluded]
    order_column = getattr(model, order_by)

    router = APIRouter()
    # ⚠️ URL 模板里那个占位符叫 alias（P4-A6），而端点函数的形参**仍叫 pk_value**：
    #    两者由下面每个端点签名里的 Path(alias=alias) 绑在一起（本机 FastAPI 0.141.1
    #    亲跑验证：/openapi.json 里 parameter 的 name 是 alias、路由匹配与取值都对）。
    #    于是「23 个资源各自的别名」这件事不必去改 23 个函数的形参名——那需要 exec
    #    或动态签名，而两者的代价都远大于一个 alias。
    detail_path = f"{path}/{{{alias}}}"

    # ``scope`` 只挂在「已存在的单行」那三个端点上，且**只在非 None 时**才注册这个依赖：
    # 依赖里那两个 Header 参数会进 OpenAPI，无条件注册的话 23 × 3 个端点会凭空多出两个
    # 请求头，而前端会以为每个 CRUD 都要传身份。
    guarded: list[Any] = []
    if scope is not None:

        def _scope_guard(
            pk_value: int = Path(alias=alias),
            session: Session = Depends(get_db),
            x_student_id: int | None = Header(None),
            x_teacher_staff_no: str | None = Header(None),
        ) -> None:
            scope(session, _get_or_404(session, model, pk_value), x_student_id,
                  x_teacher_staff_no)

        guarded.append(Depends(_scope_guard))

    # ⚠️ 写入侧的身份闸门（``require_admin``）与上面那个 ``scope`` 钩子**分开装**：
    #    前者只挂 POST/PATCH/DELETE、判「你是不是一个在册教师」，后者只挂
    #    GET/PATCH/DELETE 单行、判「这一行是不是你的」。PATCH 与 DELETE 因此可能
    #    同时挂两个（今天 23 行 ``RESOURCES`` 里 ``scope`` 恒为 ``None``，故实际只有前者）。
    # ⚠️ 两个都必须成对：``Security(...)`` 只**声明**（进 /openapi.json 的 security 一格，
    #    它是 ``auto_error=False`` 的、缺头**不**抛），``Depends(_require_admin_identity)``
    #    才**判定**。理由逐字见 :func:`_require_admin_identity` 的 docstring。
    write_guarded: list[Any] = []
    if require_admin:
        write_guarded.append(Security(TEACHER_STAFF_NO_SCHEME))
        write_guarded.append(Depends(_require_admin_identity))

    # ⚠️ **读取侧的身份闸门**（Plan 05A Task 5 立的，安全收紧波从布尔开关改成三档）：
    #    与写入侧那一份**分开装**，因为判定不同（写入要 ``role='admin'``，
    #    读取只要「在册教职」或「本人」），且**7 个参考数据资源的读仍然匿名**
    #    （故这一格缺省是空列表）。
    #    ⚠️ 它同样必须**成对**挂：``Security(...)`` 只声明（进 /openapi.json 那个操作的
    #    ``security`` 一格，于是前端与生成的 TS 客户端知道要带身份），
    #    ``Depends(...)`` 才判定。逐字理由见 :func:`_require_staff_identity` 的 docstring。
    #    ⚠️ 按学生键收窄的那**两档**（``student_self`` / ``staff_taught``）都**声明两个**
    #    scheme（学生头 **或** 教师头，OpenAPI 的 ``security`` 数组是 OR 语义），
    #    因为它们的四档身份里两种载体都能过；判定由
    #    :func:`app.api.deps.current_reader` 一次解析、就地分档。
    #    ⚠️⚠️ 于是 **Plan 06 Task 8 加第四档时这一格一个字节都没改**：
    #    第四档改的是「教师读到多少行」，不是「谁能打这个端点」，
    #    故 ``/openapi.json`` 的 ``security`` 与 ``securitySchemes`` 两格逐字不变。
    #    ⚠️⚠️ **Plan 06 Task 8b 加第五档时同样**：``weekly-class-reports`` 从
    #    ``"staff"`` 挪到 ``"staff_taught_section"``，而两档**声明的是同一个 scheme**、
    #    判定走的是**同一个** :func:`_require_staff_identity`（差别只在它的返回值
    #    第五档要用、``"staff"`` 档丢弃），故五格 openapi 计数逐字不变。
    #    ⚠️ 而它**刻意不声明** ``pe_session``：本仓的既有口径是「泛型端点一律声明
    #    请求头 scheme，cookie 那一格只由 ``/api/auth/me`` 与 ``/api/auth/logout``
    #    声明」（:func:`_require_staff_identity` 那一档今天就是这样，
    #    而它**同样**认 cookie），故这里不另立第二种口径。
    read_guarded: list[Any] = []
    if read_scope == READ_SCOPE_STAFF:
        read_guarded.append(Security(TEACHER_STAFF_NO_SCHEME))
        read_guarded.append(Depends(_require_staff_identity))
    elif read_scope == READ_SCOPE_STAFF_TAUGHT_SECTION:
        # ⚠️ 第五档**只声明 scheme、不在这里挂 Depends**：判定由下面那个端点分支的
        #    形参 ``reader: ReaderIdentity = Depends(_require_staff_identity)`` 承担
        #    ——它要那个**返回值**（判「管理员越过任教范围」），而挂在
        #    ``dependencies=[…]`` 里的依赖返回值会被 FastAPI 丢弃。
        #    ⚠️ 两者仍然是**成对**的（声明 + 判定都在），只是判定挪进了形参表；
        #    而 FastAPI 的依赖缓存保证同一个依赖在一个请求里**只跑一次**，
        #    故这一挪不多一次查库。
        read_guarded.append(Security(TEACHER_STAFF_NO_SCHEME))
    elif read_scope in STUDENT_SCOPED_READ_VALUES:
        read_guarded.append(Security(STUDENT_ID_SCHEME))
        read_guarded.append(Security(TEACHER_STAFF_NO_SCHEME))
    # ⚠️ ``owner`` 只在按学生键收窄的那两档被读到，而第 9 道校验已经保证
    #    那两档的 ``student_owner`` 非 None（「键在哪一列」不得靠缺省值猜）。
    owner = student_owner

    if readable:
        # ⚠️⚠️ **为什么下面有三个 ``list_rows`` / 三个 ``read_one``**
        #    （安全收紧波立两支；**Plan 06 Task 8b 加第三支**）：
        #    ``Depends(current_reader)`` 必须作为**端点形参**（端点要它的值来过滤），
        #    而形参会进 OpenAPI —— :func:`current_reader` 带两个 ``Header`` 参数，
        #    无条件挂上去的话那 **7 个匿名参考数据资源**的 GET 会凭空多出
        #    ``X-Student-Id`` / ``X-Teacher-Staff-No`` 两个请求头参数，
        #    前端会以为读 ``/api/exercises`` 也要带身份
        #    （这正是上面 ``_scope_guard`` 那一段逐字记过的同一个坑）。
        #    ⚠️ 于是三支的差别**只有形参表**，函数体各一行、都调同一个
        #    :func:`_list_page`；三支的 **docstring 逐字相同**，
        #    而那不是靠自觉：守卫
        #    ``tests/api/test_crud.py::test_the_generic_list_and_read_one_descriptions_are_verbatim_identical``
        #    从 ``/openapi.json`` 实读 23 个 list 与 23 个 read-one 的 ``description``，
        #    断言各自**只有 1 种取值**（改一支漏一支会当场红）。
        #    ⚠️⚠️ **Plan 06 Task 8 起身份感知那一支覆盖两档**
        #    （``student_self`` 与 ``staff_taught``，见
        #    :data:`STUDENT_SCOPED_READ_VALUES`），而两档的差别**不在形参表、
        #    也不在 docstring**，只在函数体调的那一个分派函数里
        #    （:func:`_reader_filter` / :func:`_require_row_readable`，
        #    两者都收 ``read_scope`` 作入参）。故「改了一档忘了另一档」
        #    与「两支的 description 漂了」两个失效形态都被挡在结构上。
        #    ⚠️⚠️ **而第三支（第五档）不能并进第一支**：它的身份形参是
        #    ``Depends(_require_staff_identity)``（**只认教职**），而第一支的是
        #    ``Depends(current_reader)``（学生头 **或** 教师头）——并进去的话
        #    ``/api/weekly-class-reports`` 会在 OpenAPI 里多出一个它根本不认的
        #    ``X-Student-Id`` 形参（一份反方向的假契约，逐字理由见
        #    :data:`READ_SCOPE_STAFF_TAUGHT_SECTION` 上面那张五档表的注脚）。
        if read_scope in STUDENT_SCOPED_READ_VALUES:

            @router.get(path, tags=tags, dependencies=read_guarded)
            def list_rows(
                page: Page = Depends(),
                session: Session = Depends(get_db),
                reader: ReaderIdentity = Depends(current_reader),
            ) -> dict[str, Any]:
                """分页列表。**返回的每个对象不含 ``list_exclude`` 的列**（缺省 = 全部
                ``JsonText`` 列）。

                ⚠️ **本端点没有 ``response_model``**，故它在 OpenAPI 里的响应 schema 是空的。
                这是「SQL 层就不 SELECT 那些列」的代价：一个含全部列的 ``response_model``
                会让 FastAPI 在序列化阶段 ``getattr`` 每一个字段，被 ``defer`` 掉的列于是
                触发 N+1 的延迟加载，「排除大 JSON 列」的性能收益当场归零。
                于是这里改成显式只 SELECT ``kept`` 那些列、手工拼 dict、
                交给 :func:`~fastapi.encoders.jsonable_encoder`（它把 ``date`` /
                ``datetime`` 折成 ISO 串，与 ``response_model`` 那条路径的输出逐字相同）。
                前端要字段清单请看同一资源的 ``GET {path}/{pk}``——那是 ``schemas.read``，
                而 list 的键集合恰好是它减去 ``list_exclude``。

                ``total`` 是**本页口径下**的计数、不受分页影响（前端要它算总页数）。
                ⚠️ 安全收紧波：``total`` 与 ``items`` **走同一个 ``WHERE``**，
                故一个学生会话读到的是「**我的**行数」，不是全表行数——
                否则前端分页器会显示一个它翻不到的页数。
                ⚠️ Plan 06 Task 8：那一个 ``WHERE`` 从此**随身份分三档**
                （学生 → 只留自己的行；**教师 → 只留自己本学期任教班级的学生行**；
                管理员 → 不过滤），而 ``total`` 仍然与 ``items`` 同源，
                故一个教师读到的是「**我的学生**的行数」。判据逐字见
                ``app/api/crud.py`` 的 ``_reader_filter`` 与 ``read_scope`` 那张五档表。
                ⚠️ Plan 06 Task 8b 又给它加了**两根**：① 教师那一档多一根轴——
                一行**没有**学生所有者的数据（班级级预警 / 发给教师的站内信）按
                ``StudentOwner.orphan`` 的声明判，故它对**相关的那一位教师**也在列表里
                （逐字见 ``_orphan_condition``）；② **第五档**
                ``"staff_taught_section"`` 那一个 ``WHERE`` 的键是**班**而不是学生
                （``<班级键列> IN (我本学期任教的班)``，逐字见 ``_section_filter``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                那就没有那一个 ``WHERE``（教职一律全读），``total`` 就是全表计数——
                本段说明对 23 个资源是**同一份**（三个端点分支的 docstring 必须逐字相同，
                守卫见 ``tests/api/test_crud.py`` 的
                ``test_the_generic_list_and_read_one_descriptions_are_verbatim_identical``）。
                """
                return _list_page(
                    session, model, kept, order_column, page,
                    _reader_filter(session, model, owner, reader, read_scope),
                )

            @router.get(detail_path, tags=tags, response_model=schemas.read,
                        dependencies=[*read_guarded, *guarded])
            def read_one(
                pk_value: int = Path(alias=alias),
                session: Session = Depends(get_db),
                reader: ReaderIdentity = Depends(current_reader),
            ) -> Any:
                """单行，**含全部 ``JsonText`` 列**（list 端点不含，P3-B3）。

                ⚠️ Plan 06 Task 8：越权的那一档是 ``403 forbidden``，而「越权」从此
                **随身份分三档**（学生 → 不是本人；**教师 → 不是他本学期任教的学生**；
                管理员 → 不越权）。判定与 list 端点那一个 ``WHERE`` **同源**，
                逐字见 ``app/api/crud.py`` 的 ``_require_row_readable``。
                ⚠️ Plan 06 Task 8b：教师那一档多一支——一行**没有**学生所有者的数据
                改问第二根轴（``_require_orphan_row_readable``）；而**本资源若声明的是
                第五档 ``"staff_taught_section"``**，判的是「这个班是不是他**本学期**
                任教的」（``_require_section_readable``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                教职会话读到的是任何一行（不按人收窄）。
                """
                obj = _get_or_404(session, model, pk_value)
                # ⚠️ **判定整个交给 :func:`_require_row_readable`**（派单 §2 第 3 条
                #    「不要写第二份过滤逻辑」）：本处只负责取那一行，
                #    而「学生 → ``require_scope`` / 教师 → ``require_teaches_student`` /
                #    管理员 → 越过」三档都住在那一个函数里，与 list 的
                #    :func:`_reader_filter` 成对。
                # ⚠️⚠️ **本处此前逐字写的是一段「教职跳过这一句」的注释**，
                #    并逐字记着「``require_teaches_student`` 那道闸门**刻意不扩到泛型读**
                #    ——扩到泛型读会让管理台的 23 个资源列表逐行去查任教关系」。
                #    **Plan 06 Task 8 把那一格反过来做了**（用户裁定「教师账号之间要有
                #    数据隔离」），而当年那条性能论证**仍然成立、只是被换了一种做法绕开**：
                #    本波**不是**「逐行去查任教关系」，而是**一次** ``IN (子查询)``
                #    （:func:`_taught_filter`），故 23 个资源列表的查询次数与改前同阶
                #    （教师那一档每个请求 +2 次点查：``teacher.id`` 与「本学年」）。
                #    ⚠️ 而**管理台**（``views/admin/ResourceList.vue``）走的是管理员会话，
                #    那一档**不过滤**，故派单 §3「管理台不受影响」在结构上成立。
                _require_row_readable(
                    session, model, pk, obj, owner, reader, read_scope
                )
                return obj

        elif read_scope == READ_SCOPE_STAFF_TAUGHT_SECTION:

            @router.get(path, tags=tags, dependencies=read_guarded)
            def list_rows(
                page: Page = Depends(),
                session: Session = Depends(get_db),
                reader: ReaderIdentity = Depends(_require_staff_identity),
            ) -> dict[str, Any]:
                """分页列表。**返回的每个对象不含 ``list_exclude`` 的列**（缺省 = 全部
                ``JsonText`` 列）。

                ⚠️ **本端点没有 ``response_model``**，故它在 OpenAPI 里的响应 schema 是空的。
                这是「SQL 层就不 SELECT 那些列」的代价：一个含全部列的 ``response_model``
                会让 FastAPI 在序列化阶段 ``getattr`` 每一个字段，被 ``defer`` 掉的列于是
                触发 N+1 的延迟加载，「排除大 JSON 列」的性能收益当场归零。
                于是这里改成显式只 SELECT ``kept`` 那些列、手工拼 dict、
                交给 :func:`~fastapi.encoders.jsonable_encoder`（它把 ``date`` /
                ``datetime`` 折成 ISO 串，与 ``response_model`` 那条路径的输出逐字相同）。
                前端要字段清单请看同一资源的 ``GET {path}/{pk}``——那是 ``schemas.read``，
                而 list 的键集合恰好是它减去 ``list_exclude``。

                ``total`` 是**本页口径下**的计数、不受分页影响（前端要它算总页数）。
                ⚠️ 安全收紧波：``total`` 与 ``items`` **走同一个 ``WHERE``**，
                故一个学生会话读到的是「**我的**行数」，不是全表行数——
                否则前端分页器会显示一个它翻不到的页数。
                ⚠️ Plan 06 Task 8：那一个 ``WHERE`` 从此**随身份分三档**
                （学生 → 只留自己的行；**教师 → 只留自己本学期任教班级的学生行**；
                管理员 → 不过滤），而 ``total`` 仍然与 ``items`` 同源，
                故一个教师读到的是「**我的学生**的行数」。判据逐字见
                ``app/api/crud.py`` 的 ``_reader_filter`` 与 ``read_scope`` 那张五档表。
                ⚠️ Plan 06 Task 8b 又给它加了**两根**：① 教师那一档多一根轴——
                一行**没有**学生所有者的数据（班级级预警 / 发给教师的站内信）按
                ``StudentOwner.orphan`` 的声明判，故它对**相关的那一位教师**也在列表里
                （逐字见 ``_orphan_condition``）；② **第五档**
                ``"staff_taught_section"`` 那一个 ``WHERE`` 的键是**班**而不是学生
                （``<班级键列> IN (我本学期任教的班)``，逐字见 ``_section_filter``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                那就没有那一个 ``WHERE``（教职一律全读），``total`` 就是全表计数——
                本段说明对 23 个资源是**同一份**（三个端点分支的 docstring 必须逐字相同，
                守卫见 ``tests/api/test_crud.py`` 的
                ``test_the_generic_list_and_read_one_descriptions_are_verbatim_identical``）。
                """
                return _list_page(
                    session, model, kept, order_column, page,
                    _section_filter(session, model, str(section_column), reader),
                )

            @router.get(detail_path, tags=tags, response_model=schemas.read,
                        dependencies=[*read_guarded, *guarded])
            def read_one(
                pk_value: int = Path(alias=alias),
                session: Session = Depends(get_db),
                reader: ReaderIdentity = Depends(_require_staff_identity),
            ) -> Any:
                """单行，**含全部 ``JsonText`` 列**（list 端点不含，P3-B3）。

                ⚠️ Plan 06 Task 8：越权的那一档是 ``403 forbidden``，而「越权」从此
                **随身份分三档**（学生 → 不是本人；**教师 → 不是他本学期任教的学生**；
                管理员 → 不越权）。判定与 list 端点那一个 ``WHERE`` **同源**，
                逐字见 ``app/api/crud.py`` 的 ``_require_row_readable``。
                ⚠️ Plan 06 Task 8b：教师那一档多一支——一行**没有**学生所有者的数据
                改问第二根轴（``_require_orphan_row_readable``）；而**本资源若声明的是
                第五档 ``"staff_taught_section"``**，判的是「这个班是不是他**本学期**
                任教的」（``_require_section_readable``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                教职会话读到的是任何一行（不按人收窄）。
                """
                obj = _get_or_404(session, model, pk_value)
                # ⚠️ 与上面那一支的 :func:`_require_row_readable` 同一条纪律：
                #    本处只负责取那一行，判定整个交给
                #    :func:`_require_section_readable`（它读的是**同一个**
                #    :func:`_section_filter` 产出的表达式，见
                #    :func:`_require_row_matches`）。
                _require_section_readable(
                    session, model, pk, str(section_column), obj, reader
                )
                return obj

        else:

            @router.get(path, tags=tags, dependencies=read_guarded)
            def list_rows(
                page: Page = Depends(), session: Session = Depends(get_db)
            ) -> dict[str, Any]:
                """分页列表。**返回的每个对象不含 ``list_exclude`` 的列**（缺省 = 全部
                ``JsonText`` 列）。

                ⚠️ **本端点没有 ``response_model``**，故它在 OpenAPI 里的响应 schema 是空的。
                这是「SQL 层就不 SELECT 那些列」的代价：一个含全部列的 ``response_model``
                会让 FastAPI 在序列化阶段 ``getattr`` 每一个字段，被 ``defer`` 掉的列于是
                触发 N+1 的延迟加载，「排除大 JSON 列」的性能收益当场归零。
                于是这里改成显式只 SELECT ``kept`` 那些列、手工拼 dict、
                交给 :func:`~fastapi.encoders.jsonable_encoder`（它把 ``date`` /
                ``datetime`` 折成 ISO 串，与 ``response_model`` 那条路径的输出逐字相同）。
                前端要字段清单请看同一资源的 ``GET {path}/{pk}``——那是 ``schemas.read``，
                而 list 的键集合恰好是它减去 ``list_exclude``。

                ``total`` 是**本页口径下**的计数、不受分页影响（前端要它算总页数）。
                ⚠️ 安全收紧波：``total`` 与 ``items`` **走同一个 ``WHERE``**，
                故一个学生会话读到的是「**我的**行数」，不是全表行数——
                否则前端分页器会显示一个它翻不到的页数。
                ⚠️ Plan 06 Task 8：那一个 ``WHERE`` 从此**随身份分三档**
                （学生 → 只留自己的行；**教师 → 只留自己本学期任教班级的学生行**；
                管理员 → 不过滤），而 ``total`` 仍然与 ``items`` 同源，
                故一个教师读到的是「**我的学生**的行数」。判据逐字见
                ``app/api/crud.py`` 的 ``_reader_filter`` 与 ``read_scope`` 那张五档表。
                ⚠️ Plan 06 Task 8b 又给它加了**两根**：① 教师那一档多一根轴——
                一行**没有**学生所有者的数据（班级级预警 / 发给教师的站内信）按
                ``StudentOwner.orphan`` 的声明判，故它对**相关的那一位教师**也在列表里
                （逐字见 ``_orphan_condition``）；② **第五档**
                ``"staff_taught_section"`` 那一个 ``WHERE`` 的键是**班**而不是学生
                （``<班级键列> IN (我本学期任教的班)``，逐字见 ``_section_filter``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                那就没有那一个 ``WHERE``（教职一律全读），``total`` 就是全表计数——
                本段说明对 23 个资源是**同一份**（三个端点分支的 docstring 必须逐字相同，
                守卫见 ``tests/api/test_crud.py`` 的
                ``test_the_generic_list_and_read_one_descriptions_are_verbatim_identical``）。
                """
                return _list_page(session, model, kept, order_column, page, None)

            @router.get(detail_path, tags=tags, response_model=schemas.read,
                        dependencies=[*read_guarded, *guarded])
            def read_one(
                pk_value: int = Path(alias=alias), session: Session = Depends(get_db)
            ) -> Any:
                """单行，**含全部 ``JsonText`` 列**（list 端点不含，P3-B3）。

                ⚠️ Plan 06 Task 8：越权的那一档是 ``403 forbidden``，而「越权」从此
                **随身份分三档**（学生 → 不是本人；**教师 → 不是他本学期任教的学生**；
                管理员 → 不越权）。判定与 list 端点那一个 ``WHERE`` **同源**，
                逐字见 ``app/api/crud.py`` 的 ``_require_row_readable``。
                ⚠️ Plan 06 Task 8b：教师那一档多一支——一行**没有**学生所有者的数据
                改问第二根轴（``_require_orphan_row_readable``）；而**本资源若声明的是
                第五档 ``"staff_taught_section"``**，判的是「这个班是不是他**本学期**
                任教的」（``_require_section_readable``）。
                ⚠️ 而**本资源若声明的是 ``read_scope=None`` 或 ``"staff"``**，
                教职会话读到的是任何一行（不按人收窄）。
                """
                return _get_or_404(session, model, pk_value)

    if writable:

        @router.post(path, tags=tags, status_code=201, response_model=schemas.read,
                     dependencies=write_guarded)
        def create_row(
            payload: schemas.create,  # type: ignore[valid-type]
            response: Response,
            session: Session = Depends(get_db),
        ) -> Any:
            """建一行 → 201 + ``Location`` 头。

            ⚠️ **两档，由 ``natural_key`` 决定**（P3-B2）：

            * **有自然键** → 走 :func:`app.db.repo.upsert`。⚠️ 那个函数的语义是
              「有则更新、无则插入」，**它撞键时不抛异常**，故 409 必须由本端点判：
              ``upsert`` 新建的实例在 flush 前是 *pending*、因而在 ``session.new`` 里，
              已存在的那一行是 *persistent*、不在。**不在就回滚 + 409**——回滚是必需的，
              因为 ``upsert`` 的更新分支已经 ``setattr`` 过那一行了，
              不回滚就等于「一次被拒绝的 POST 改掉了库里的数据」。
            * **无自然键**（3 个资源）→ 裸 ``session.add``。结构上不可能撞键，
              故这一档**没有 409**；反面守卫是
              ``test_a_resource_without_a_natural_key_never_returns_409``。
            """
            values = payload.model_dump()
            # ⚠️ **Plan 06 Task 12 / C1：请求体的字符串值不许超过目标列的声明宽度**。
            #    逐字理由（为什么是「拒绝」而不是「截断」、为什么住在这里而不是一个
            #    ``before_flush`` 钩子）见 :func:`app.db.width.ensure_fits` 与
            #    :mod:`app.db.width` 的模块 docstring。⚠️ 它抛 ``ValueError`` →
            #    经 :mod:`app.api.errors` 折成 **422 ``unprocessable_value``**（带消息原文），
            #    与 :func:`app.api.schemas._base.one_of` 把枚举越界折成 422 是同一条链。
            #    ⚠️ **它是这一格唯一的收口点**：23 个资源的 POST 与 PATCH 一律经这两处，
            #    故「哪个资源的哪个字段可以送多长」这件事不需要 23 份 schema 注解。
            db_width.ensure_fits(table, values)
            if natural_key:
                obj = repo.upsert(session, model, natural_key, values)
                if obj not in session.new:
                    session.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail=_conflict_message(table.name, natural_key),
                    )
            else:
                obj = model(**values)
                session.add(obj)
            session.commit()
            session.refresh(obj)
            response.headers["Location"] = f"{path}/{getattr(obj, pk)}"
            return obj

        @router.patch(detail_path, tags=tags, response_model=schemas.read,
                      dependencies=[*guarded, *write_guarded])
        def update_row(
            payload: schemas.update,  # type: ignore[valid-type]
            # ⚠️ pk_value 排在 payload **之后**（P4-A6）：它现在带缺省值
            # （Path(alias=…)），而 payload 不带，Python 的语法规则要求「带缺省的形参
            # 不得排在不带缺省的前面」。FastAPI 按名字与标注解析入参、不看顺序，
            # 故换序对请求形状**没有任何影响**（create_row 的 payload 本来也排第一）。
            pk_value: int = Path(alias=alias),
            session: Session = Depends(get_db),
        ) -> Any:
            """**部分更新**：只改请求体里出现的键。

            ``exclude_unset=True`` 是这一档的全部机制，它让 ``null`` 与「没传」可区分
            （计划 Review Focus 的同一条）：``PATCH {"department": null}`` 清空那一列，
            ``PATCH {"name": "x"}`` 不碰它。
            ⚠️ 用 ``model_dump()`` 会让「没传」的键以 ``None`` 落进去，
            于是一次改名会把 ``department`` 悄悄清掉——守卫是
            ``test_patch_changes_only_the_keys_present`` 的第一拍。
            """
            obj = _get_or_404(session, model, pk_value)
            changes = payload.model_dump(exclude_unset=True)
            # ⚠️ **Plan 06 Task 12 / C1**：与 :func:`create_row` 里那一处是同一个收口点
            #    （逐字理由见那一处的注释，本处不抄第二份）。
            #    ⚠️ 它排在 ``setattr`` **之前**、而排在 ``_get_or_404`` 之后：
            #    于是「这一行不存在」仍然先答 404（与既有口径逐字相同，
            #    一个打错 id 的调用方得到的是 404 而不是一个关于请求体的 422）。
            db_width.ensure_fits(table, changes)
            for name, value in changes.items():
                setattr(obj, name, value)
            session.commit()
            session.refresh(obj)
            return obj

    if writable and on_delete != ON_DELETE_FORBID:

        @router.delete(detail_path, tags=tags, status_code=204,
                       dependencies=[*guarded, *write_guarded])
        def delete_row(
            pk_value: int = Path(alias=alias), session: Session = Depends(get_db)
        ) -> Response:
            """删一行 → 204。``restrict`` 有子行时 409、``cascade`` 子表先删。

            ⚠️ ``on_delete="forbid"`` 的资源**不注册本路由**（那一档在工厂体里就被
            ``if`` 挡掉了），故打过去是 Starlette 的 405。
            """
            obj = _get_or_404(session, model, pk_value)
            if on_delete == ON_DELETE_CASCADE:
                _purge_where(session, table, table.c[pk] == pk_value)
            else:
                blockers: list[str] = []
                for child_name, child_column in _child_tables(model):
                    child = Base.metadata.tables[child_name]
                    count = session.scalar(
                        select(func.count())
                        .select_from(child)
                        .where(child.c[child_column] == pk_value)
                    )
                    if count:
                        blockers.append(f"{child_name}.{child_column} 有 {count} 行")
                if blockers:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"无法删除 {table.name} {pk_value}："
                            + "；".join(blockers)
                            + " 仍指向它。请先处理那些行，或改用重放。"
                        ),
                    )
                session.delete(obj)
            session.commit()
            return Response(status_code=204)

    return router
