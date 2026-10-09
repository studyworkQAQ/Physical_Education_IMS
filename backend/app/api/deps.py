"""HTTP 层的依赖注入：数据库会话、身份、作用域闸门、分页。

⚠️ **原型口径，上线前必须换成真实会话**（计划 File Structure「本计划刻意不做」的第 3 条）：
本模块用**请求头**传身份（``X-Student-Id`` / ``X-Teacher-Staff-No``），没有签名、没有过期、
没有吊销。它挡的是「前端把 id 写错就读到别人的数据」这一类**事故**——也就是计划
Review Focus 第 1 条点名的那个形状；它**不挡**「有人故意伪造请求头」这一类**攻击**，
因为请求头本来就是客户端可以随便写的。后者需要真实鉴权，本计划不做。

**本模块在依赖图里的位置**（spec §3.3：``api → services → domain``）：``api`` 是最上层，
它可以 import ``app.db`` / ``app.domain`` / ``app.pipeline`` / ``app.refdata*`` /
``app.config`` / ``app.notify``，**反向一律禁止**。守卫是
``tests/architecture/test_layering.py``（Plan 03 Task 1 给它加的 ``api`` 那一层）。
本模块只向下拿两样东西：``app.db.session`` 的 ``Session`` 与
``app.db.models.organisation`` 的 ``Student``——它**不碰 domain**，
因为闸门要判的是「这个 id 在不在册」，那是数据库里的事实、不是领域规则。

**``get_db`` 为什么不提交**：与 ``app.db.repo.upsert`` 的「flush 但不 commit」同口径
（计划 Interfaces 一节逐字要求）。「什么时候算一个工作单元结束了」这件事只有端点知道，
依赖不知道；由依赖提交的话，一个端点里两次写入就没法作为一个整体成功或失败。
"""
from collections.abc import Iterator

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models.organisation import Student

__all__ = ["Page", "current_student", "current_teacher", "get_db", "require_scope"]


def get_db(request: Request) -> Iterator[Session]:
    """每请求一个 :class:`~sqlalchemy.orm.Session`，退出时 ``close()``，**不 commit**。

    ⚠️ **签名与计划 Interfaces 写下的 ``get_db() -> Iterator[Session]`` 差一个参数**
    （本 Task 顶回派单的一处，报告里也记了）。差的那个参数是必需的：会话要一个引擎，
    而引擎是 :func:`app.main.create_app` 按注入的 ``db_url`` 造的、存在
    ``app.state.engine`` 上。一个无参的 ``get_db()`` 只能从**模块级全局**取引擎，
    于是同一进程里的两个应用（``create_app(db_url=A)`` 与 ``create_app(db_url=B)``）
    会共用**后建的那一个**引擎——而 ``tests/api/conftest.py`` 的 ``app`` 夹具是
    function 级的，每个测试都建一个新应用。那种共享会让「A 的测试读到了 B 的库」，
    且表现为间歇性的空结果，离真因极远。

    ``Request`` 是 FastAPI 里唯一能从依赖内部拿到「当前这个 app」的入口，
    故用它。对调用方没有区别：端点里仍然写 ``session: Session = Depends(get_db)``
    （``tests/test_main.py`` 的三个探针就是这么写的），FastAPI 自己会把 ``request``
    注进来。

    ``close()`` 放在 ``finally`` 里，故端点抛异常时会话也一定被关掉：
    SQLAlchemy 的 ``Session.close()`` 会回滚未完成的事务并归还连接。
    ``tests/test_main.py::test_integrity_error_maps_to_409`` 走的正是这一支
    （``commit()`` 抛 ``IntegrityError``、异常要穿过这个 ``finally`` 才能飞到错误处理器）。
    """
    engine: Engine = request.app.state.engine
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def current_student(x_student_id: int | None = Header(None)) -> int:
    """从 ``X-Student-Id`` 取学生身份；缺头 → ``401``。

    FastAPI 自动把参数名 ``x_student_id`` 折成请求头名 ``X-Student-Id``
    （下划线 → 连字符、首字母大写），不需要手写 ``alias``。

    ⚠️ 标注成 ``int | None`` 的一个后果：**头存在但不是整数**（``X-Student-Id: abc``）
    时抛的是 FastAPI 的 ``RequestValidationError`` → ``422``，不是本函数的 ``401``。
    这是计划 Interfaces 写下的签名（``int | None = Header(None)``）的直接结果，
    不构成漏洞（两个码都拒绝访问），但前端要知道「没有头」与「头格式错」是两个码。
    口径由 ``tests/api/test_scope.py::test_a_non_integer_identity_header_is_422`` 钉住。
    """
    if x_student_id is None:
        raise HTTPException(status_code=401, detail="缺少身份请求头 X-Student-Id")
    return x_student_id


def current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str:
    """从 ``X-Teacher-Staff-No`` 取教师身份；缺头或空白 → ``401``。

    与 :func:`current_student` 的差别是「空白也算缺」：工号是字符串，
    ``X-Teacher-Staff-No:`` 与 ``X-Teacher-Staff-No: %20`` 这类请求头会被 ASGI
    原样送进来，而一个空工号既查不到教师、也不该被当成「有身份」。
    学号那一侧不需要这一支，因为 ``int`` 标注已经让非数字变成 ``422``。
    """
    if x_teacher_staff_no is None or not x_teacher_staff_no.strip():
        raise HTTPException(status_code=401, detail="缺少身份请求头 X-Teacher-Staff-No")
    return x_teacher_staff_no


def require_scope(session: Session, student_id: int, requester_id: int) -> None:
    """**作用域闸门**（计划 Review Focus 第 1 条：越权访问）。

    两个入参是**两个不同的东西**，混淆它们是这道闸门唯一的失效方式：

    * ``student_id`` —— **目标数据的所有者**，由调用方从行上读出来
      （``row.student_id``），不是从请求头来的；
    * ``requester_id`` —— **请求者的身份**，来自 :func:`current_student`
      （即 ``X-Student-Id``）。

    两件事任一不成立就 ``403``：

    1. ``student_id != requester_id``。学生 A 拿 ``X-Student-Id: B`` 去读 B 的打卡 /
       RPE / 训练单 / 处方，正是 Review Focus 第 1 条逐字点名的形状。
    2. ``requester_id`` 在 ``student`` 表里查无此人。**这一支是 ``session`` 参数存在的
       全部理由**：不查库的闸门只能比对两个整数，于是 ``X-Student-Id: 999999`` 会被
       放行到端点里、只靠下游的 ``404`` 兜底——而下游的 ``404`` 是「没有这行数据」的
       意思，不是「你不是这个人」的意思，两者混在一起之后，前端无法区分
       「我确实没有打卡记录」与「我根本没登录成任何人」。

    两支都报 ``403``、不报 ``404``：区分「行不存在」与「你不是它的主人」等于把
    「哪些 id 在册」这件事告诉调用方。

    顺序是**先比对、后查库**：不匹配时不必白跑一次 ``SELECT``，而且比对是纯整数运算、
    不可能因为库的状态而改变结论。

    ⚠️ 「pure gate」的准确含义是**只判定、不改状态**（不 commit、不写库、不缓存、
    不回一个「通过了」的对象——返回值是 ``None``），**不是**「不碰数据库」。
    第 2 支要读一次 ``student``。测试名沿用计划原文的
    ``test_require_scope_is_a_pure_gate``，它的 docstring 里重述了这条口径。

    ⚠️ **教师不走这道闸门**：``requester_id`` 是 ``int``，而教师身份是工号字符串。
    教师端的读写按设计是跨学生的（大屏、班级周报），它的边界是「这个教师在不在册」、
    由 :func:`current_teacher` 与 Task 8 的教师路由各自负责。
    """
    if student_id != requester_id:
        raise HTTPException(
            status_code=403,
            detail=f"学生 {requester_id} 无权访问学生 {student_id} 的数据",
        )
    if session.get(Student, requester_id) is None:
        raise HTTPException(
            status_code=403,
            detail=f"身份 {requester_id} 不是一个在册学生",
        )


class Page(BaseModel):
    """分页参数。用法是 ``page: Page = Depends()``（Task 3 的 ``build_crud_router`` 会
    给 23 个资源各挂一个）。

    ``limit`` 上界 **200**：原型阶段前端一屏最多几十行，200 已远超需要；设上界是为了让
    ``?limit=100000`` 不会变成一次全表扫描——SQLite 不会替你拒绝它。
    下界 **1**：``limit=0`` 在语义上是「什么都不要」，而它会与「参数没传」在返回的
    空列表上无法区分，故直接拒掉。
    ``offset`` 下界 **0**：负偏移在 SQLite 上等价于 0，但那是一次静默的语义改写。

    ⚠️ 这三条边界**不是文档、是被强制执行的**：Pydantic 在构造时校验，
    而当它作为 FastAPI 依赖时同一套校验发生在解析查询串的阶段（失败 → ``422``，
    经 :mod:`app.api.errors` 折成统一形状）。
    ``tests/api/test_scope.py::test_page_caps_limit_at_two_hundred`` 两侧都测了。
    """

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
