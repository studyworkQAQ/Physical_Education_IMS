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
* **``pk`` 与 ``order_by`` 今天恒为缺省值 ``"id"``**：25 张表的主键都是单列 ``id``
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
"""
import dataclasses
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.schema import Table

from app.api.deps import Page, get_db
from app.db import repo
from app.db.models._shared import JsonText
from app.db.session import Base

__all__ = ["CrudSchemas", "ScopeFn", "build_crud_router"]

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
#: ``ondelete`` 为 ``None``（今天 25 张表的 20 个外键里的 18 个）才是「真的会挡住」。
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
    后者**不在模型上**，只能扫 :data:`Base.metadata` 的全部 25 张表（P3-B4）。

    ⚠️ 于是本函数有一条**导入期依赖**：``Base.metadata`` 必须已经装满 25 张表。
    这在生产路径上恒成立——:mod:`app.api.routers.catalog` 的第一行就 import
    ``app.db.models``（它 ``from . import feedback, prescription``，故 25 张全注册），
    而本函数在**请求期**才被调用。⚠️ 但它也因此在
    ``import app.api.crud`` 的**那一刻**是可能不完整的，故本函数刻意**不在工厂体里
    预算一次并缓存**：预算会把「metadata 装满了没有」变成一个导入顺序问题，
    而按请求算的代价是一次 25 张表 × 各自外键的遍历，只发生在 DELETE 上。

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

    ⚠️ **主键取 ``table.primary_key`` 的第一列**：25 张表的主键都是单列 ``id``，
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


def build_crud_router(
    *,
    model: type[Any],
    schemas: CrudSchemas,
    path: str,
    tags: list[str],
    pk: str = "id",
    order_by: str = "id",
    readable: bool = True,
    writable: bool = True,
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
    ``readable`` / ``writable``
        两个开关，**互相独立**：``writable=False`` 关掉 POST/PATCH/DELETE，
        ``on_delete="forbid"`` 只关掉 DELETE。
        ``tests/api/test_crud.py`` 的
        ``test_a_forbidden_delete_is_405_even_on_a_writable_resource`` 钉的就是这个独立性。
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
        覆盖那一档今天是**许可而不是断言**：23 行没有一行用它，存在的理由是
        「list 端点确实要返回某个小 JSON 列」这个例外（P3-B3）。
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
    columns = {column.name for column in model.__table__.columns}
    for label, names in (
        ("pk", (pk,)),
        ("order_by", (order_by,)),
        ("natural_key", natural_key or ()),
        ("list_exclude", list_exclude or ()),
    ):
        unknown = sorted(set(names) - columns)
        if unknown:
            raise ValueError(
                f"{path} 的 {label} 里有 {model.__tablename__} 不存在的列：{unknown}"
            )
    if not path.startswith("/api/"):
        raise ValueError(f"资源路径必须挂在 /api/ 下（复数 + 连字符），收到 {path!r}")

    table = model.__table__
    excluded = (
        tuple(list_exclude) if list_exclude is not None else _json_text_columns(model)
    )
    kept = [column.name for column in table.columns if column.name not in excluded]
    order_column = getattr(model, order_by)

    router = APIRouter()
    detail_path = path + "/{pk_value}"

    # ``scope`` 只挂在「已存在的单行」那三个端点上，且**只在非 None 时**才注册这个依赖：
    # 依赖里那两个 Header 参数会进 OpenAPI，无条件注册的话 23 × 3 个端点会凭空多出两个
    # 请求头，而前端会以为每个 CRUD 都要传身份。
    guarded: list[Any] = []
    if scope is not None:

        def _scope_guard(
            pk_value: int,
            session: Session = Depends(get_db),
            x_student_id: int | None = Header(None),
            x_teacher_staff_no: str | None = Header(None),
        ) -> None:
            scope(session, _get_or_404(session, model, pk_value), x_student_id,
                  x_teacher_staff_no)

        guarded.append(Depends(_scope_guard))

    if readable:

        @router.get(path, tags=tags)
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

            ``total`` 是**全表**计数、不受分页影响（前端要它算总页数）。
            """
            total = session.scalar(select(func.count()).select_from(model))
            rows = session.execute(
                select(*[getattr(model, name) for name in kept])
                .order_by(order_column)
                .limit(page.limit)
                .offset(page.offset)
            ).all()
            return {
                "items": jsonable_encoder([dict(zip(kept, row)) for row in rows]),
                "total": total,
                "limit": page.limit,
                "offset": page.offset,
            }

        @router.get(detail_path, tags=tags, response_model=schemas.read,
                    dependencies=guarded)
        def read_one(pk_value: int, session: Session = Depends(get_db)) -> Any:
            """单行，**含全部 ``JsonText`` 列**（list 端点不含，P3-B3）。"""
            return _get_or_404(session, model, pk_value)

    if writable:

        @router.post(path, tags=tags, status_code=201, response_model=schemas.read)
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
                      dependencies=guarded)
        def update_row(
            pk_value: int,
            payload: schemas.update,  # type: ignore[valid-type]
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
            for name, value in payload.model_dump(exclude_unset=True).items():
                setattr(obj, name, value)
            session.commit()
            session.refresh(obj)
            return obj

    if writable and on_delete != ON_DELETE_FORBID:

        @router.delete(detail_path, tags=tags, status_code=204,
                       dependencies=guarded)
        def delete_row(pk_value: int, session: Session = Depends(get_db)) -> Response:
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
