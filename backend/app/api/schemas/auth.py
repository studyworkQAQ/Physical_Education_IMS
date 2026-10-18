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

from app.api.schemas._base import ReadModel, one_of
from app.db.models.auth import UserSession

__all__ = [
    "BindTokenIssuedRead",
    "BindTokenPageRead",
    "BindTokenRead",
    "LoginCreate",
    "SessionIdentityRead",
    "StudentBindCreate",
    "TeacherBindCreate",
    "TokenBindCreate",
    "TokenIssueCreate",
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

    ⚠️⚠️ **验身材料的可读性**（终审 I3 改写：本处此前的那一句今天**反了**）。
    原文是「验身材料本身是**匿名**可读的：``GET /api/students`` 今天匿名返回全部
    60 人的 ``birth``……而收紧那 48 个匿名 GET 是 **Task 5** 的活」——
    **Task 5 已经做了**：``RESOURCES`` 的 ``students`` 行显式声明了「仅教职可读」
    （⚠️ 那一格今天叫 ``"read_scope": READ_SCOPE_STAFF``，Task 5 当时叫
    ``"read_requires_staff": True``，安全收紧波改的名、行为逐字不变），
    故匿名 ``GET /api/students`` 实测是 **401**。
    今天这一格是：本端点挡的是「不知道学号与出生日期的人」，**也**挡「没有教职会话的人」；
    剩下的局限是「一个**已登录的教职**能给任何还没绑定的学生抢先绑一个口令」
    （绑定只对 ``password_hash IS NULL`` 的行放行，故它挡不住抢占）。
    原型可接受、已写进 spec 的已知局限。
    ⚠️⚠️ **安全收紧波把那一档局限的「可批量枚举」半边关掉了**：此前
    ``StudentRead`` / ``TeacherRead`` 都含 ``password_bound_at``，故一个教职
    一次 ``GET /api/students?limit=200`` 就能列出**全部还没绑定**的账号；
    本波把那一列从两个读模型与两行的 ``list_exclude`` 上一起摘掉了（裁定 3），
    于是「谁还没绑」只能逐个 ``POST /api/auth/login`` 去试
    （403 ``password_not_bound`` vs 401 ``invalid_credentials``）。
    ⚠️ 抢占本身**仍然可能**（绑定端点没变），故这一条已知局限**不撤销**，
    只是从「可批量枚举 + 可抢占」窄化成「可逐个探测 + 可抢占」。
    ⚠️ 「哪些读今天还匿名」的账面只有一个住址：:mod:`app.api.routers.catalog`
    的模块 docstring，本处刻意不复述第二份。
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
    ⚠️ 它与学生那一侧**同档**（终审 I3 改写：本处此前写的是「比学生那一侧**弱**：
    ``name`` 也是匿名可读的（``TeacherRead`` 含它，泛型 ``GET`` 一律匿名）」，
    而 Plan 05A Task 5 已把 ``teachers`` 那一行也显式声明成「仅教职可读」
    （⚠️ 那一格今天叫 ``"read_scope": READ_SCOPE_STAFF``，Task 5 当时叫
    ``"read_requires_staff": True``）
    → 匿名 ``GET /api/teachers`` 实测 **401**，故「匿名可读」与「一律」两半都过期了）：
    ``name`` 今天只有**持教职会话**的人读得到，于是「工号 + 姓名」这一对材料是
    「读过名册的教职就知道」的。如实记录（硬规矩 #39），
    与学生那一档合并登记为同一条已知局限。
    ⚠️ 「哪些读今天还匿名」的账面只有一个住址：:mod:`app.api.routers.catalog`
    的模块 docstring，本处刻意不复述第二份。
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


# ===========================================================================
# ⚠️⚠️ Plan 08 Task 4：**一次性绑定令牌**那五个模型
#
# 它们**刻意与自助绑定那两个同住一个模块**，理由与「读审计那三个与写审计那三个
# 同住 :mod:`app.api.schemas.audit`」逐字同一条（那个文件的注释里写着三条，
# 本处只复述承重的那一条）：它们是**同一个端点族**——同一个 router 模块
# （:mod:`app.api.routers.auth`）、同一个 ``tags=["auth"]``、同一个管理台页面
# 与同一个 ``/bind`` 页，故「绑定的 HTTP 契约」这件事在本仓仍然只有**一个**住址。
#
# ⚠️⚠️ **五个模型里只有一个含明文令牌**（:class:`BindTokenIssuedRead`），
# 而那一个**只在签发那一刻被序列化一次**。⚠️ 于是「明文只出现一次」在契约面上
# 是**可数的**：``git grep "token:" app/api/schemas/auth.py`` 恰好一处，
# 而 :class:`BindTokenRead`（列表与详情用的那一个）**没有** ``token`` 也**没有**
# ``token_hash`` 这两格。守卫是 ``tests/api/test_bind_token.py`` 的
# ``test_only_the_issuance_contract_carries_the_plaintext_and_no_contract_carries_the_hash``
# （它扫的是本模块**全部**模型的字段名，故「给 :class:`BindTokenRead` 顺手加一格
# ``token_hash``」会当场红）。
# ===========================================================================


class TokenIssueCreate(BaseModel):
    """``POST /api/auth/bind-tokens`` 的请求体：**发给谁**（两格，⚠️ **仅管理员**）。

    ⚠️⚠️ **它刻意不含任何秘密**：明文令牌由**服务端**生成
    （:func:`app.auth.bind_tokens.mint` → :func:`secrets.token_urlsafe`）。
    一个「客户端交一个串上来、服务端存它的哈希」的形状会把凭据的**产生**搬到浏览器里
    （于是 CSPRNG 的质量、令牌的长度与字母表全部由前端决定），
    而那正是 :class:`StudentBindCreate` 的 docstring 里那句
    「能被客户端写进去的哈希等于『任何人可以给任何人设一个自己知道的口令』」的同族失效。
    ⚠️ 这一格是本 Task 顶回「把 ``bind_token`` 做成
    :data:`app.api.routers.catalog.RESOURCES` 的第 24 个资源」的第一条理由：
    泛型工厂的 ``create_row`` 逐字是 ``model(**payload.model_dump())``
    （``app/api/crud.py``），即**每一列都必须来自请求体** —— 那个形状下
    ``token_hash`` 只能由客户端交上来。

    ⚠️ ``kind`` 的取值域走 :func:`one_of` + :attr:`UserSession.KINDS`（本包约定 2：
    类常量是唯一真相），与 :class:`LoginCreate` 的同名一格逐字同形。
    ⚠️ ``login`` 是**学号或工号的原文**（按 ``kind`` 分派去哪张表回查），
    与 :class:`LoginCreate.login` 同一条口径（一个字段装两种登录名，
    逐字理由在那个模型的 docstring 里，本处不抄第二份）。
    """

    kind: str
    login: str

    @field_validator("kind")
    @classmethod
    def _kind_in_the_model_domain(cls, value: str) -> str:
        return one_of("kind", value, UserSession.KINDS)


class BindTokenIssuedRead(BaseModel):
    """``POST /api/auth/bind-tokens`` 的响应体（**201**）：**七格，含明文令牌**。

    ⚠️⚠️ **它是全仓唯一一个把明文凭据投影出去的契约模型**，而那一格是**要的**：
    派单 §2 第 1 条逐字要求「明文只在签发那一刻返回一次」。⚠️ 于是「只出现一次」
    这件事有两个可执行的一半：

    * **契约面**：本模型是 ``token`` 那一格的唯一住址，而
      :class:`BindTokenRead`（列表用的那一个）**没有**它 —— 故签发之后
      再打 ``GET /api/auth/bind-tokens`` **读不回**明文（守卫见上面那段）；
    * **存储面**：库里那一格是 :func:`app.auth.passwords.hash_password` 的产出，
      明文**从来没有**落过库（守卫是
      ``test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table``，
      它扫全库 30 张表的每一列）。

    ⚠️ 它**刻意继承 :class:`~pydantic.BaseModel` 而不是 :class:`ReadModel`**：
    端点返回的是一个现拼的 ``dict``（明文那一格不在 ORM 行上，行上是哈希），
    故 ``from_attributes`` 对它没有意义 —— 与
    :class:`app.api.schemas.audit.AuditLogPageRead` 的同款取舍逐字相同。
    ⚠️ 而那一格正是「为什么本模型不能由泛型工厂产出」的第二条理由：
    泛型 ``create_row`` 的 ``response_model`` 是**从 ORM 行上投影**的
    （``return obj``），而行上没有明文。

    ⚠️ ``token`` 用裸 ``str`` 而**不是** :class:`~pydantic.SecretStr`：
    ``SecretStr`` 的全部用途是「不让一个**用户提交的**秘密被回显进 422 的 ``detail``」
    （本文件模块 docstring 第二节逐字写了那一格），而本模型是**响应**，
    它要做的恰恰是**把明文交出去**。⚠️ 而它因此**不可能**触发那一格失效：
    一个响应模型不参与请求校验，故它不会出现在任何 ``ValidationError.errors()`` 里。
    """

    id: int
    kind: str
    login: str
    #: ⚠️ **明文令牌，全仓唯一一次出现**。⚠️ 它**不进审计**：
    #: :mod:`app.api.audit` 从不读请求体**也从不读响应体**
    #: （``record`` 的六个入参里没有任何一个来自体，逐字理由在那个模块的
    #: docstring 第三节），而 ``audit_log`` 的 9 列里也**没有**能装它的位置。
    #: 守卫是 ``test_the_plaintext_token_never_reaches_the_audit_row``。
    token: str
    issued_at: dt.datetime
    expires_at: dt.datetime
    issued_by: str | None = None


class BindTokenRead(ReadModel):
    """一行绑定令牌的**只读投影**（``GET /api/auth/bind-tokens`` 的 ``items`` 元素）。

    **七格 = :class:`app.db.models.auth.BindToken` 的 9 列减去两列**：

    * ⚠️ **减去 ``token_hash``**：它是凭据（一个 PBKDF2 自描述串，含盐与摘要），
      把它投影出去等于「把口令哈希摊给读得到本端点的人」—— 与
      ``RESOURCES`` 里 ``students`` / ``teachers`` 两行的
      ``"list_exclude": ("password_hash", …)`` **逐字同一条纪律**
      （那两行的注释写着「它是纵深防御的第二层，闸门哪天为别的理由放开时
      凭据仍然不在响应体里」）。⚠️ 而本端点**只有 ``role='admin'``** 打得到，
      故这一格是**第三层**（闸门、哈希不可逆、契约里没有这一格）。
    * ⚠️ **减去 ``token_id``**：它是选择子（不是秘密，
      :class:`app.db.models.auth.BindToken` 的 docstring 第二节），
      而它**仍然不投影**，一条理由：本端点的读者是**管理台的页面**，
      而页面上给出选择子就等于给出「一个 49 字符的串里前 16 个字符」——
      它把「拿一串编造的选择子灌兑换端点」这一格探测的成本降低了一点点，
      而它对运维**没有任何用处**（运维要认的是「哪个学号、什么时候到期、用没用」，
      那三格都在）。⚠️ 如实记（硬规矩 #39）：于是「按 ``id`` 指认一张令牌」
      是本端点唯一的指认方式，而 ``id`` 是自增整数 —— 本端点**没有**
      「按 ``id`` 撤销某一张」的操作（本波不做撤销），故那一格今天不构成风险。

    ⚠️ ``used_at`` 是 ``None`` = **还没用过**；非空 = 已用过（那一刻）。
    ⚠️ 而「过期」在本模型上是一个**要前端自己算**的格（``expires_at <= now``）：
    服务端**刻意不**投影一个现算的 ``is_expired`` 布尔，理由是它会让
    「过期了吗」这件事有第二个判据（服务端那一格与
    :func:`app.auth.bind_tokens.is_expired`），而两个判据漂开的失效形态是
    「页面上写着还没过期、兑换端点说已经过期」。⚠️ 代价（如实记）：
    前端要按 **naive 本地时刻**解释这两格（与
    :class:`app.api.schemas.audit.AuditLogRead` 的 ``at`` 同一条口径，
    差 8 小时的失效形态在那里逐字写着）。
    """

    id: int
    kind: str
    login: str
    issued_at: dt.datetime
    expires_at: dt.datetime
    used_at: dt.datetime | None = None
    issued_by: str | None = None


class BindTokenPageRead(BaseModel):
    """``GET /api/auth/bind-tokens`` 的响应体：**四个信封键**，与泛型 list 逐字同形。

    ⚠️ 它与 :class:`app.api.schemas.audit.AuditLogPageRead` /
    ``ReadAuditLogPageRead`` **同形而不同类**，故**刻意不共用一个泛型基类**
    （那一条取舍的逐字理由住在 ``ReadAuditLogPageRead`` 的 docstring 里，
    本处不抄第二份：一句话是给这三处抽 ``Page[T]`` 会改掉「未定型响应 24 个」
    那一格的性质，那是一次跨 23 个资源的契约面改动）。
    """

    items: list[BindTokenRead]
    total: int
    limit: int
    offset: int


class TokenBindCreate(_PasswordMixin):
    """``POST /api/auth/bind-with-token`` 的请求体：**令牌 + 新口令**（两格，⚠️ **匿名**）。

    ⚠️⚠️ **它刻意不含 ``kind`` / ``student_no`` / ``staff_no`` / ``birth``**：
    令牌**自带目标**（``bind_token.kind`` + ``bind_token.login`` 两列），
    故请求体里再交一遍就是**第二份**「这次绑定是给谁的」——而两份漂开的失效形态
    是具体的：「令牌是发给学号 A 的、请求体里写的是学号 B」，
    那一档要么静默地绑错人、要么要一条互斥校验。⚠️ 于是本端点的身份**只有一个来源**，
    与 :class:`LoginCreate` 的 ``kind`` + ``login`` 两格是**相反**的取舍
    （那一端点没有凭据能自带身份，故必须交）。

    ⚠️ ``token`` 用 :class:`~pydantic.SecretStr`，逐字理由与本文件模块 docstring
    第二节那条 ``password`` 的相同：Pydantic 的 ``ValidationError.errors()``
    每一格都带一个 ``input``，而 :mod:`app.api.errors` 会把整份 ``errors()``
    塞进 422 的 ``detail`` 里 —— 于是「``password`` 那一格校验失败」会把
    **同一个请求体里的令牌明文**回显出去。⚠️ 而 :mod:`app.api.errors` 的
    ``_SENSITIVE_INPUT_KEYS`` 那一道按键名脱敏是**另一半**
    （它挡的是「别的字段缺失 ⇒ ``input`` 是整个请求体」那一档），
    两道合起来才封住。⚠️ **``token`` 这个键名必须在那一份清单里**，
    守卫是 ``tests/api/test_bind_token.py`` 的
    ``test_a_validation_error_never_echoes_the_submitted_token``
    （它**真的**发一次「缺 ``password``、带一个真令牌」的请求，
    然后断言响应体的**原始字节**里不出现那个明文串）。
    """

    token: SecretStr
