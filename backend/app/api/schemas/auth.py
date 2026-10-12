"""``app/api/routers/auth.py`` 那**五个**端点的请求体与响应契约（Plan 05A Task 1）。

⚠️ **本模块是 ``schemas/`` 的第 10 个模块，而它一个资源都不服务**：
``user_session`` 不在 :data:`app.api.routers.catalog.RESOURCES` 的 23 行里
（它没有匿名可读的列表，它的读端点是 ``GET /api/auth/me``、写端点是
``POST /api/auth/{login,logout}``，五个都是手写的特例端点）。
与 :mod:`.dashboard` / :mod:`.pipeline` 同一档。

--------------------------------------------------------------------------
⚠️⚠️ 五个模型里最重要的性质：**没有一个含 ``password_hash``**
--------------------------------------------------------------------------

口令哈希只住在 DB 列与 :mod:`app.auth.passwords` 里。它**既不是请求体的字段**
（客户端提交的是明文，哈希由服务端算——能被客户端写进去的哈希等于
「任何人可以给任何人设一个自己知道的口令」，那就绕过了绑定流程的验身材料本身），
**也不是响应体的字段**（``SessionIdentityRead`` 只有 6 格，没有它）。
守卫是 ``tests/api/test_auth_api.py`` 的
``test_no_auth_schema_mentions_a_credential_column``。

--------------------------------------------------------------------------
⚠️ ``password`` 用 :class:`~pydantic.SecretStr`，且**那一格不是为了好看**
--------------------------------------------------------------------------

Pydantic v2 的 ``ValidationError.errors()`` 每一格都带一个 ``input``，
而 :mod:`app.api.errors` 的 ``_request_validation`` 会把整份 ``errors()``
经 ``jsonable_encoder`` 塞进 422 的 ``detail`` 里。于是**任何一个字段校验失败**，
响应体里就可能出现客户端刚提交的那份请求体——含明文口令。
``SecretStr`` 让「口令本身校验失败」那一格被掩掉（它的 ``__repr__`` 与
``jsonable_encoder`` 都给 ``'**********'``）。

⚠️ **但 ``SecretStr`` 挡不住「别的字段缺失」那一档**：``missing`` 错误的 ``input``
是**整个请求体**（一个原始 ``dict``，里面那一格还是明文串，因为 Pydantic 还没来得及
把它转成 ``SecretStr``）。故 :mod:`app.api.errors` 另外做了一层**按键名脱敏**
（``_SENSITIVE_INPUT_KEYS``），两道合起来才封住这一档。
守卫是 ``tests/api/test_auth_api.py`` 的
``test_a_validation_error_never_echoes_the_submitted_password``。
"""
import datetime as dt

from pydantic import BaseModel, SecretStr, field_validator

from app.api.schemas._base import one_of
from app.db.models.auth import UserSession

__all__ = [
    "LoginCreate",
    "SessionIdentityRead",
    "StudentBindCreate",
    "TeacherBindCreate",
]


class _PasswordMixin(BaseModel):
    """三个请求体共用的那一格 ``password``。

    ⚠️ **刻意不带 Pydantic 侧的长度约束**（没有 ``min_length=``）：计划 §3.2 要的那一档
    是 **422 ``unprocessable_value``**，而 Pydantic 的字段约束会给
    **422 ``request_validation_failed``**——两个 code 不同，而前者才是
    :func:`app.auth.passwords.ensure_acceptable` 抛 ``ValueError`` 折出来的那一个。
    ⚠️ 于是「口令太短」与「请求体缺了一个字段」在前端是**两档**：
    前者要提示「口令至少 8 个字符」，后者是前端自己的 bug。
    把它们混成一个 code 会让前端只能显示一句「参数不对」。
    """

    password: SecretStr


class StudentBindCreate(_PasswordMixin):
    """``POST /api/auth/students/bind`` 的请求体：**学号 + 出生日期 + 新口令**。

    ⚠️ **字段名是 ``birth`` 而不是计划 §3.2 写的 ``birth_date``**（实现者顶回）：
    ``student`` 表那一列实测就叫 ``birth``（Plan 01 建的），而本仓的既定约定是
    「Pydantic 字段名一律与 DB 列名逐字相同」（:mod:`app.api.crud` 的模块 docstring
    那张 23 行对照表就是这份约定，``StudentCreate.birth`` 已经在前）。
    用 ``birth_date`` 会让同一个概念在两个请求体里叫两个名字，而前端
    （``GET /api/students`` 拿到的就是 ``birth``）要在两处各记一个。

    ⚠️⚠️ **验身材料本身是匿名可读的**（计划 §3.2 自己点出的权衡）：
    ``GET /api/students`` 今天匿名返回全部 60 人的 ``birth``。故本端点挡的是
    「不知道学号与出生日期的人」，而**不挡**「读过那个列表的人」。
    原型可接受、已写进 spec 的已知局限，而收紧那 48 个匿名 GET 是 **Task 5** 的活。
    """

    student_no: str
    birth: dt.date


class TeacherBindCreate(_PasswordMixin):
    """``POST /api/auth/teachers/bind`` 的请求体：**工号 + 姓名 + 新口令**。

    ⚠️ **验身材料是「工号 + 姓名」，而 ``teacher`` 表实测**有** ``name`` 列**
    （``['id', 'staff_no', 'name']``，Plan 05A 实现者亲跑取证），故计划 §3.2 那一格
    的假设成立、**不需要顶回**。
    ⚠️ 理由与学生那一侧同构：教师行由管理员创建（``POST /api/teachers``，
    Plan 05A Task 2 之后**仅管理员**），管理员可以把工号与姓名告给他。
    ⚠️ 而它比学生那一侧**弱**：``name`` 也是匿名可读的
    （``TeacherRead`` 含它，泛型 ``GET`` 一律匿名），故「工号 + 姓名」这一对
    同样是「读过列表的人就知道」的材料。如实记录（硬规矩 #39），
    与学生那一档合并登记为同一条已知局限。
    """

    staff_no: str
    name: str


class LoginCreate(_PasswordMixin):
    """``POST /api/auth/login`` 的请求体：``kind`` + 登录名 + 口令。

    ⚠️ **一个 ``login`` 字段装两种登录名**（学号或工号），而不是两个可选字段：
    两个可选字段要一条「恰好一个非空」的互斥校验，而 Pydantic 表达它要靠
    ``model_validator``，出错时那一格的 ``loc`` 是 ``("body",)``（指不到具体字段），
    前端于是不知道该把红框画在哪一个输入框上。一个字段 + 一个 ``kind`` 下拉框
    与计划 §4.1 的登录页形状（「选身份：学生 / 教师」）逐字对应。

    ⚠️ **``kind`` 只有两个值，管理员不在里面**（用户 2026-10-12 的裁定「管理员这个角色
    接管管理台」落地成一个 ``teacher`` 行上的 ``role`` 标签，不是第三种身份）：
    管理员用 ``kind="teacher"`` 登录，前端再按响应体里的 ``role`` 决定跳
    ``/admin`` 还是 ``/t/dashboard``（计划 §4.1 逐字写了这个形状）。
    取值域的唯一所有者是 :attr:`UserSession.KINDS`（本包约定：类常量是唯一真相），
    故这里**不写字面词表**、走 :func:`one_of`。
    """

    kind: str
    login: str

    @field_validator("kind")
    @classmethod
    def _kind_in_the_model_domain(cls, value: str) -> str:
        return one_of("kind", value, UserSession.KINDS)


class SessionIdentityRead(BaseModel):
    """``POST /api/auth/login`` 与 ``GET /api/auth/me`` 共用的响应体（**逐字同形**）。

    六格。⚠️ **``login`` 与 ``me`` 共用一个模型是有意的**：前端登录后要立刻知道
    「我是谁、我该跳哪个首页」，而 ``me`` 要答的是同一个问题；两个模型会在
    下一次加字段时漂开（一个加了、另一个忘了），而它们的消费者是同一段代码。
    ⚠️ 先例是 ``dashboard._student_home_response``（学生侧与教师侧的首页
    **逐字同形**，守卫是 ``test_the_teacher_and_the_student_variants_of_the_home_page_return_the_same_body``）。

    六格各自从哪来（硬规矩 #110）：

    * ``kind`` / ``id`` / ``role`` —— :class:`app.auth.sessions.Identity` 的同名三格
      （即 ``user_session`` 那一行）；
    * ``name`` —— **subject 行**（``student.name`` / ``teacher.name``），
      故改名之后立刻生效（``role`` 不是：它冗余存在会话行上，
      降权要等重新登录——两条守卫各钉一半，见 ``tests/auth/test_sessions.py``）；
    * ``student_no`` / ``staff_no`` —— **subject 行**，且**互斥**：
      学生那一档只填前者、教师那一档只填后者，另一个是 ``None``。
      ⚠️ 两格而不是一个 ``login``：前端要按 ``kind`` 显示「学号」或「工号」两个
      不同的中文标签，而一个字段名给不出标签；⚠️ 而它们**同时**在
      ``Identity.login`` 里以一格的形式存在（那一格是给服务端闸门用的，
      ``require_staff`` 一族以工号为主语）。
    """

    kind: str
    id: int
    name: str
    role: str
    student_no: str | None = None
    staff_no: str | None = None
