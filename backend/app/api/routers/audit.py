"""``GET /api/audit-logs``（**写**审计）与 ``GET /api/read-audit-logs``（**敏感读**审计）：
两个**管理员只读**的查询端点（Plan 06 Task 5 建第一个；**Plan 08 Task 1** 加第二个）。

⚠️⚠️ **两个端点、一个模块**，而这是派单 §2 第 7 条那条裁定的落点：管理台**不新开页面**
（在既有 ``/admin/audit-logs`` 上加一个「写 / 读」切换），故后端也**不新开 router 模块**
——否则「审计的读端点」这件事在本仓会有两个住址，而 :mod:`app.api.routers` 的
模块 docstring 里那句「本目录今天是 ``__init__`` + 8 个 router = 9 个 ``.py`」
也要跟着改（⚠️ 那一格现在仍然成立，本波一个字都没动它）。

⚠️ **两个端点的身份口径逐字相同**（派单 §2 第 8 条的裁定：「与既有 ``/api/audit-logs``
同一条口径」）：同一个 ``Security(TEACHER_STAFF_NO_SCHEME)`` 声明 +
同一个 :func:`app.api.deps.current_teacher` + 同一个 :func:`app.api.deps.require_admin`。
⚠️ 于是「能读写审计的人」与「能读读审计的人」是**同一批人**，
而那一格是**要的**：读审计里能读到「谁翻过谁的档案」，那是比「谁改了名册」
**更**敏感的一格信息，故它的权限面不许比写审计更宽。

⚠️ 两者**都不走** :func:`app.api.crud.build_crud_router`：

* ``audit_log`` **不是** :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源
  （派单 §1 第 5 条逐字要求；它是特例端点，同 ``/api/health`` 那一族）；
* ⚠️ **走泛型工厂会得到四个错**：① 它会注册 ``POST`` / ``PATCH`` / ``DELETE``
  （而审计行**不许被任何端点改**——不可改写是审计的第一条性质，
  :class:`app.db.models.audit.AuditLog` 的模块 docstring 第一节）；
  ② 它的 ``read_scope`` 三档里**没有**「仅管理员」这一档
  （:data:`app.api.crud.READ_SCOPE_STAFF` 放行的是「教师**或**管理员」）；
  ③ 泛型 list **一律匿名**或按学生键收窄，而本端点两档都不是；
  ④ 它会进 ``RESOURCES`` 那张 23 行的读写矩阵，于是
  ``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned``
  的三格数字（23 / 9 / 14）全部要改——而那张矩阵说的是**业务资源**。

--------------------------------------------------------------------------
⚠️⚠️ 身份档：**仅 ``role='admin'``**（派单 §1 第 5 条的四格矩阵）
--------------------------------------------------------------------------

===========  ==============================  ==================================
调用方        实测码                            由谁给出
===========  ==============================  ==================================
匿名          **401** ``unauthenticated``     :func:`app.api.deps.current_teacher`
学生（cookie）**403** ``forbidden``           同上（「一个学生的 cookie 不能当教师用」）
教师（在册）   **403** ``forbidden``           :func:`app.api.deps.require_admin`
管理员        **200**                         ——
===========  ==============================  ==================================

⚠️ **判定复用的是既有那两道闸门**（``current_teacher`` + ``require_admin``），
与 :func:`app.api.crud._require_admin_identity` 组合的是**同两个函数**
——故「管理台的写操作仅管理员」与「审计仅管理员可读」是**同一条口径**，
不是两份判据。⚠️ 那一格是本端点最重要的性质：审计页里能读到「谁改了名册」，
而改名册本身就要管理员，故两件事的权限面**必须**重合，否则会出现
「能读审计的人比能写的人多」或反过来。

⚠️ **学生那一档是 403 不是 401**（与 :func:`app.api.deps.current_student` 的
「教师 cookie 打学生端点」同一条口径）：请求者**已经被认出来了**，
只是不是这个端点要的那一类人。``unauthenticated`` 说的是「我不知道你是谁」，
而这里我们知道。

⚠️⚠️ **过渡通道那一档如实记**（硬规矩 #39）：``PE_ALLOW_HEADER_IDENTITY=1``
（**仅开发档**，生产档被 :func:`app.api.deps.allow_header_identity` 强制关）时，
一个 ``X-Student-Id`` 头**不会**让学生通过——:func:`app.api.deps.current_teacher`
只认 ``X-Teacher-Staff-No``，故带学生头得到的是 **401** 而不是上表那个 403。
⚠️ 两档都拒绝访问，故不构成漏洞；差别只在码。守卫按**上表**钉（它用真 cookie 登录，
与生产档同一条路径），另有一条把请求头那一档的实测码也钉住
（``tests/api/test_audit_api.py``）。

--------------------------------------------------------------------------
⚠️ 本端点**自己不产生审计行**（它是 GET）
--------------------------------------------------------------------------

:func:`app.api.audit.should_record` 只认 ``POST`` / ``PATCH`` / ``DELETE``，
故管理员翻审计页**不会**往审计里加行。⚠️ 那一格是**要的**：否则审计页会自己喂自己
（每翻一页多一行「有人翻了审计」），而那张表是**单调增长**的（清理任务自 Plan 08
Task 2 起有了：``scripts/retention.py``，⚠️ 而它**不会自己跑**）。
⚠️ 代价：「谁看过审计」今天**查不到**。如实记录，已登记为待清扫
（要补的话正确的做法是另开一张读审计表，理由逐字见 :mod:`app.api.audit`
的模块 docstring 第二节第 3 条）。
"""
from fastapi import APIRouter, Depends, Security
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    TEACHER_STAFF_NO_SCHEME,
    Page,
    current_teacher,
    get_db,
    require_admin,
)
from app.api.schemas.audit import (
    AuditLogFilter,
    AuditLogPageRead,
    ReadAuditLogFilter,
    ReadAuditLogPageRead,
)
from app.db.models.audit import AuditLog, ReadAuditLog

__all__ = ["router"]

router = APIRouter()


@router.get(
    "/api/audit-logs",
    tags=["audit"],
    response_model=AuditLogPageRead,
    # ⚠️ **只声明教师头那一个 scheme**，与本仓既有口径逐字相同
    #    （``tests/api/test_prescription_api.py`` 里 :data:`student_self_reads`
    #    上方那段注释：「泛型端点一律声明请求头 scheme，cookie 那一格只由
    #    ``/api/auth/me`` 与 ``/api/auth/logout`` 声明」）。
    #    ⚠️ 于是 ``securitySchemes`` **仍是 3 格**、而「值恰好是 ``pe_session`` 的
    #    特例端点」**仍是那两个**——那一格由同一条守卫的末尾两拍钉住。
    #    ⚠️ **声明与判定是两件事**：本端点用浏览器里的 cookie 也照样能过，
    #    因为 :func:`app.api.deps.current_teacher` **先看 cookie**、
    #    再在过渡通道开着时回落请求头。``TEACHER_STAFF_NO_SCHEME`` 是
    #    ``auto_error=False`` 的，故它只负责**声明**（进 ``/openapi.json``、
    #    于是 Swagger 的 Authorize 弹窗能填、生成的 TS 客户端知道要发这个头），
    #    不负责判定（理由逐字见 :data:`app.api.deps.TEACHER_STAFF_NO_SCHEME` 的注释）。
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def list_audit_logs(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    page: Page = Depends(),
    filters: AuditLogFilter = Depends(),
) -> dict[str, object]:
    """（**仅管理员**）审计行的一页：四个信封键，``items`` 按 ``id DESC``（**最新在前**）。

    ⚠️ **闸门在函数体的第一行**（:func:`app.api.deps.require_admin`），排在任何一次
    查询之前：一个非管理员连「这张表有多少行」都读不到（``total`` 也是一格信息）。
    ⚠️ 它**不复用** :func:`app.api.crud._require_admin_identity`：那一个是一个
    ``Depends`` 形状的组合（``staff_no`` 与 ``session`` 由它自己注入），
    而本端点已经显式注入了那两格（``filters`` 与 ``page`` 也要 ``Depends``，
    混用两种形状会让「哪个依赖注入了 session」这件事有两份答案）。
    两个函数**调的是同一个** :func:`app.api.deps.require_admin`，故判据仍然只有一份。

    ⚠️ **``ORDER BY id DESC`` 而不是 ``at DESC``**：``id`` 是 ``INTEGER PRIMARY KEY``
    = rowid 别名，故逆序扫主键本身就是一次索引扫描，**不需要**额外建一个 ``(at)``
    索引；而 ``id`` 的递增序与 ``at`` 的递增序在本表上**是同一个顺序**
    （写入方只有一个、时钟只有一个、且本表**没有任何 UPDATE**，
    逐字见 :class:`app.db.models.audit.AuditLog` 的 ``__table_args__`` 注释）。

    ⚠️ **``total`` 与 ``items`` 走同一个 ``WHERE``**：那一格的失效形态
    （「学生会话的 ``items`` 只有自己的行、而 ``total`` 是全表 840」）逐字写在
    :func:`app.api.crud._list_page` 的 docstring 里，本处不抄第二份。
    ⚠️ 本端点因此**不调** ``_list_page``：那个函数的 ``order_column`` 是**升序**的
    （泛型 list 一律 ``ORDER BY id``，审计要的是**倒序**），
    而给它加一个「倒序」开关会让 23 个资源的 list 端点都多一个用不上的参数。
    ⚠️ 于是四个信封键在本仓有**两处**拼装（``_list_page`` 与本函数），
    如实记录（硬规矩 #39）：键名的一致性由
    :class:`app.api.schemas.audit.AuditLogPageRead` 与
    ``tests/api/test_audit_api.py`` 的
    ``test_the_envelope_has_exactly_the_four_keys_of_a_generic_list`` 双向钉住。

    ⚠️ **过滤在 SQL 层**（两个 ``WHERE``，不是「拉全量再筛」）：本表是**单调增长**的，
    而 ``LIMIT`` / ``OFFSET`` 作用在**已过滤**的行上，故「某一类人的第 1 页」永远是满的。
    """
    require_admin(session, staff_no)

    conditions = []
    if filters.subject_kind is not None:
        conditions.append(AuditLog.subject_kind == filters.subject_kind)
    if filters.method is not None:
        conditions.append(AuditLog.method == filters.method)

    count_statement = select(func.count()).select_from(AuditLog)
    statement = select(AuditLog).order_by(AuditLog.id.desc())
    for condition in conditions:
        count_statement = count_statement.where(condition)
        statement = statement.where(condition)

    return {
        "items": session.scalars(
            statement.limit(page.limit).offset(page.offset)
        ).all(),
        "total": session.scalar(count_statement),
        "limit": page.limit,
        "offset": page.offset,
    }


@router.get(
    "/api/read-audit-logs",
    tags=["audit"],
    response_model=ReadAuditLogPageRead,
    # ⚠️ **与上面 ``/api/audit-logs`` 那一格逐字相同**（同一个
    #    ``TEACHER_STAFF_NO_SCHEME``，故 ``securitySchemes`` **仍是 3 格**、
    #    而「值恰好是 ``pe_session`` 的特例端点」**仍是那两个**）。
    #    ⚠️ 逐字理由住在上面那个端点的同一处注释里，本处不抄第二份。
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def list_read_audit_logs(
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    page: Page = Depends(),
    filters: ReadAuditLogFilter = Depends(),
) -> dict[str, object]:
    """（**仅管理员**）读审计行的一页：四个信封键，``items`` 按 ``id DESC``（**最新在前**）。

    ⚠️ **它与 :func:`list_audit_logs` 逐格同形**（闸门在函数体第一行、``ORDER BY id DESC``、
    ``total`` 与 ``items`` 走同一个 ``WHERE``、过滤在 SQL 层），
    故那四段的逐字理由**一律住在上面那个函数里**，本处不抄第二份（硬规矩 #66）。
    ⚠️ 而「同形」这件事**不靠人眼**：``tests/api/test_read_audit_api.py`` 的
    ``test_the_read_audit_endpoint_is_shaped_like_the_write_one`` 把两者的
    四个信封键、排序方向与三档身份的码逐个对拍。

    ⚠️⚠️ **两处刻意的差别**（各有一条守卫）：

    1. **过滤的那两格不同**：写审计是 ``subject_kind`` + ``method``，
       本端点是 ``subject_kind`` + ``student_id``。⚠️ 后者正是这张表存在的理由
       （「**这一个学生**的档案被谁翻过」），而它**走索引**
       （``ix_read_audit_log_student_id_at``，列序 ``(student_id, at)`` 的逐字理由见
       :class:`app.db.models.audit.ReadAuditLog` 的 ``__table_args__`` 注释）。
       ⚠️ ``subject_kind`` 的取值域**也不同**（两档，``anonymous`` 不在里面），
       故 ``?subject_kind=anonymous`` 在本端点是 **422**、在写审计端点是 200 + 0 行
       —— 逐字理由见 :class:`app.api.schemas.audit.ReadAuditLogFilter`。
    2. ⚠️ **本端点自己会产生一行读审计**（它是敏感读，
       :data:`app.api.read_audit.READ_ROUTES` 把它归在 ``AUDIT_TRAIL`` 那一类）。
       这与 :func:`list_audit_logs` **相反**（那一个不产生任何行，因为写审计只认三个
       写方法），故上面那个函数的末节那句「本端点自己不产生审计行」在本函数上**不成立**。
       ⚠️ **裁定：要记**，三条理由逐字见
       :data:`app.api.read_audit.READ_CLASSES` 的 ``AUDIT_TRAIL`` 那一条
       （一句话：「谁看过审计」正是这一类存在的理由，而它有界——一次翻页一行、
       只有 ``role='admin'`` 打得到，处置是 Task 2 的 90 天留存窗口）。
       ⚠️ 守卫是 ``tests/api/test_read_audit_api.py`` 的
       ``test_reading_the_read_audit_page_adds_exactly_one_row_about_itself``
       （**恰好一行**，不是「至少一行」：它同时钉住了「一次请求只落一行」那个上界）。
    """
    require_admin(session, staff_no)

    conditions = []
    if filters.subject_kind is not None:
        conditions.append(ReadAuditLog.subject_kind == filters.subject_kind)
    if filters.student_id is not None:
        conditions.append(ReadAuditLog.student_id == filters.student_id)

    count_statement = select(func.count()).select_from(ReadAuditLog)
    statement = select(ReadAuditLog).order_by(ReadAuditLog.id.desc())
    for condition in conditions:
        count_statement = count_statement.where(condition)
        statement = statement.where(condition)

    return {
        "items": session.scalars(
            statement.limit(page.limit).offset(page.offset)
        ).all(),
        "total": session.scalar(count_statement),
        "limit": page.limit,
        "offset": page.offset,
    }
