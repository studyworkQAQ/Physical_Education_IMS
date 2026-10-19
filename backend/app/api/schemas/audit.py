"""``GET /api/audit-logs`` 与 ``GET /api/read-audit-logs`` 的请求与响应契约
（Plan 06 Task 5 加的**第 11 个** schema 模块；**Plan 08 Task 1** 在同一模块里加了
读审计那三个）。

⚠️ **本模块一个资源都不服务**：``audit_log`` **不在**
:data:`app.api.routers.catalog.RESOURCES` 的 23 行里（派单 §1 第 5 条逐字要求），
它是一个**手写的特例端点**，与 ``/api/health`` 同一族。与 :mod:`.dashboard` /
:mod:`.pipeline` / :mod:`.auth` 同一档。

--------------------------------------------------------------------------
⚠️⚠️ 三个模型里**没有一个含口令、出生日期或任何请求体内容**
--------------------------------------------------------------------------

逐字理由住在 :mod:`app.db.models.audit` 的模块 docstring 第三节（那张表的 9 列里
**根本没有**能装请求体的位置，故「不记请求体」是一条**结构性质**、不是「克制住不写」）。
本模块因此**不可能**把口令投影出去：``AuditLogRead`` 的 9 格与那 9 列一一对应，
而 ``AuditLogFilter`` 的两格是**过滤器**（取值域就是模型类常量），
``AuditLogPageRead`` 是四个信封键。
守卫是 ``tests/api/test_audit_api.py`` 的
``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
（它**真的发一次带口令的 login**，然后把落库那一行的**全部 9 列**逐列扫一遍，
断言口令串与出生日期串一个都不出现）与
``test_no_audit_schema_mentions_a_credential_or_a_body``（结构侧：三个模型的字段名里
不出现 ``password`` / ``birth`` / ``body`` 一类）。

--------------------------------------------------------------------------
⚠️ ``total`` 与 ``items`` **走同一个 ``WHERE``**（与泛型 list 同一条口径）
--------------------------------------------------------------------------

:func:`app.api.crud._list_page` 是「泛型 list 的分页信封」的唯一所有者，而本端点
**不走泛型工厂**（它不是资源），故信封在 :func:`app.api.routers.audit.list_audit_logs`
里自己拼。⚠️ 而那条口径是**同一个**：``total`` 是**过滤后**的计数、不受分页影响，
否则前端分页器会给出一个翻不到的页数（那一格的失效形态逐字写在
:func:`app.api.crud._list_page` 的 docstring 里，本处不抄第二份）。
守卫是 ``tests/api/test_audit_api.py`` 的
``test_total_and_items_share_the_same_filter``。
"""
import datetime as dt

from pydantic import BaseModel, field_validator

from app.api.audit import AUDITED_METHODS
from app.api.schemas._base import ReadModel, one_of
from app.db.models.audit import AuditLog, ReadAuditLog

__all__ = [
    "AuditLogFilter",
    "AuditLogPageRead",
    "AuditLogRead",
    "ReadAuditLogFilter",
    "ReadAuditLogPageRead",
    "ReadAuditLogRead",
]


class AuditLogRead(ReadModel):
    """一行审计。**9 格，与 :class:`app.db.models.audit.AuditLog` 的 9 列一一对应**。

    ⚠️ **它不投影任何「现算」出来的格**：``subject_kind`` 是 ``anonymous`` 时
    ``subject_id`` / ``staff_no`` 两格就是 ``None``，本模型**不去**回查名册把它们补上。
    理由与 :class:`app.db.models.audit.AuditLog` 的 ``subject_id`` 那一列逐字相同
    （鉴权失败时**根本不知道**是谁，而一个事后补出来的 id 会把「撞门的人」
    伪装成「在册的人」）。

    ⚠️ ``at`` 是 **naive 本地时刻**（:data:`app.config.TIMEZONE`），故它序列化成
    ``2025-10-12T09:30:00`` 而**不带** ``Z`` 后缀。前端**不得**按 UTC 解释它
    （差 8 小时）。⚠️ 那一格是对派单的一处顶回，逐字理由见 ``AuditLog.at`` 的注释。
    """

    id: int
    at: dt.datetime
    subject_kind: str
    subject_id: int | None = None
    staff_no: str | None = None
    method: str
    path: str
    status: int
    target: str | None = None


class AuditLogPageRead(BaseModel):
    """``GET /api/audit-logs`` 的响应体：**四个信封键**，与泛型 list 逐字同形。

    ⚠️ 它**刻意继承 :class:`~pydantic.BaseModel` 而不是 :class:`ReadModel`**：
    端点返回的是一个现拼的 ``dict``（不是一个 ORM 行），故 ``from_attributes``
    对它没有意义。⚠️ 而 ``items`` 里那些 :class:`AuditLogRead` **需要**它
    （它们直接从 ORM 行投影），故那一格开在 :class:`ReadModel` 上、不开在这里。
    """

    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int


class AuditLogFilter(BaseModel):
    """两个过滤参数。用法是 ``filters: AuditLogFilter = Depends()``。

    ⚠️ **只有两个**（派单 §1 第 5 条逐字要求「过滤参数不要超过 3 个，够用即可，
    别过度设计」）。选这两个的理由是它们各自对应审计最常问的那一句：

    * ``subject_kind`` —— 「**哪一类人**做的」（而 ``anonymous`` 那一档就是
      「谁在撞门」：鉴权失败的行全在这里，:mod:`app.api.audit` 的模块 docstring
      第五节）；
    * ``method`` —— 「**是哪一种写**」（``DELETE`` 那一档尤其要能单独拎出来看：
      删数据是不可逆的，而本仓的 ``on_delete`` 三档里有 12 个 ``restrict``）。

    ⚠️ **刻意没有的三个**（每一个都想过、都不加）：

    * ``staff_no`` / ``subject_id`` —— 「某一个人做过什么」这一问今天用不上：
      本系统一个学校只有一两个教务干事，而审计页是给**他**看的；
      加了它就要一并加「一个教师能不能查另一个教师」这一格权限判定，
      那是另一个 Task 的问题。⚠️ 如实记为待清扫。
    * ``since`` / ``until`` —— 时间窗要一个**日期解析**口径（含时区），
      而本表的 ``at`` 是 naive 本地时刻，一个 ``?since=2025-10-12`` 到底指
      当天 00:00 还是 24 小时之内会有两种答案。加了它就要先把那一格口径定下来，
      超出本 Task 的范围。⚠️ 如实记为待清扫。
    * ``path`` —— 前缀匹配要决定「``/api/students`` 匹不匹配
      ``/api/students/12``」，而那是一个**语义**决定；本表的行数在原型规模下
      一次 ``LIMIT 200`` 就够翻，不值得为它定一条前缀规则。

    ⚠️ 两格的取值域**都不是字面词表**（硬规矩 #35）：``subject_kind`` 取自
    :attr:`app.db.models.audit.AuditLog.SUBJECT_KINDS`（模型类常量是唯一真相，
    本包约定 2），``method`` 取自 :data:`app.api.audit.AUDITED_METHODS`
    （「哪些方法会被记」的唯一所有者）。⚠️ 于是「传一个不可能出现在表里的值」
    是 **422**，而不是「静默返回 0 行」——后者会让运维以为「今天没有删除操作」。
    """

    subject_kind: str | None = None
    method: str | None = None

    @field_validator("subject_kind")
    @classmethod
    def _subject_kind_in_the_model_domain(cls, value: str | None) -> str | None:
        return one_of("subject_kind", value, AuditLog.SUBJECT_KINDS)

    @field_validator("method")
    @classmethod
    def _method_in_the_audited_domain(cls, value: str | None) -> str | None:
        """⚠️ **先归一化成大写、再校验**（本模型唯一一处不是纯 ``one_of`` 的地方）。

        HTTP 的方法令牌本身区分大小写，而 ``scope["method"]`` 恒为大写
        （:func:`app.api.audit.should_record` 也按大写判、落库前再 ``upper()`` 一次），
        故表里**只可能**有大写。⚠️ 一个运维在 Swagger 上敲 ``?method=post``
        要的是「给我看 POST 的行」，不是「422：取值必须是 ['DELETE', 'PATCH',
        'POST'] 之一」——后者是一句正确但没用的话，而它会让人以为审计坏了。
        ⚠️ 归一化**住在这里、不住在端点里**：端点因此拿到的恒为「``None`` 或一个
        已在取值域里的大写串」，不必再判一次（那就是第二个所有者）。
        """
        return one_of("method", None if value is None else value.upper(), AUDITED_METHODS)


# ===========================================================================
# ⚠️⚠️ Plan 08 Task 1：**读审计**那三个（``GET /api/read-audit-logs``）
#
# 它们**刻意与写审计那三个同住一个模块**，理由三条：
# ① 它们是**同一个端点族**（同一个 router 模块 :mod:`app.api.routers.audit`、
#    同一条身份口径 ``current_teacher`` + ``require_admin``、同一个管理台页面
#    ``views/admin/AuditLogList.vue`` 的「写 / 读」两档），故「审计的 HTTP 契约」
#    这件事在本仓仍然只有**一个**住址；
# ② 新开一个 ``schemas/read_audit.py`` 会让 ``tests/architecture/test_layering.py``
#    的扫描面从 73 变成 74，而那一格换来的只是「两个文件各三个模型」；
# ③ 隐私那一条守卫（``test_no_read_audit_schema_mentions_a_credential_or_a_body``）
#    与写审计那一条（``test_no_audit_schema_mentions_a_credential_or_a_body``）
#    **逐字同形**，住在同一个测试文件里，故契约模型也住在一起才好对拍。
#
# ⚠️⚠️ 而三个模型里**没有一个含口令、出生日期、请求体或查询串**
# —— 逐字理由与写审计那三个相同（:mod:`app.db.models.audit` 的模块 docstring 第三节：
# 那两张表的 9 列里**根本没有**能装它们的位置）。⚠️ 读审计比写审计**多一条**：
# ``route`` 那一格是**路由模板**、不是 ``str(request.url)``，故查询串也进不来
# （逐字理由见 :mod:`app.api.read_audit` 的模块 docstring 第 6 节）。
# ===========================================================================


class ReadAuditLogRead(ReadModel):
    """一行**读审计**。**9 格，与 :class:`app.db.models.audit.ReadAuditLog` 的 9 列
    一一对应**。

    ⚠️ 它与 :class:`AuditLogRead` 的九格里**七格同名**
    （``id`` / ``at`` / ``subject_kind`` / ``subject_id`` / ``staff_no`` / ``status`` /
    ``target``），而**各另有两格不同**：

    * 写审计那两格是 ``method`` + ``path``（请求路径**原文**）；
    * 读审计那两格是 ``route``（路由**模板**）+ ``student_id``（「**哪个学生的**档案」）。

    ⚠️ 于是「九格」这个数在两张表上相同而**内容不同**，⚠️ 那不是巧合也不是抄来的：
    写审计用 ``method`` + ``path`` 两格答「做了什么」，读审计用 ``route`` 一格答
    「翻了什么档案」、腾出来的那一格给了 ``student_id`` —— 而那一格正是本表存在的理由，
    它在写审计里**没有意义**（写的对象是行 id，不是人）。
    ⚠️ ``route`` 存模板而不是原文，于是本模型**不可能**把一条客户端可控的 URL
    投影出去，也不可能把查询串投影出去。

    ⚠️ ``subject_id`` 与 :class:`AuditLogRead` 的那一格**同形**（``int | None``），
    而 ``NULL`` 的**成因不同**：写审计那一档是「匿名撞门，根本不知道是谁」，
    本表这一档是「教职走请求头通道，故只填了 ``staff_no``」
    （逐字理由见 :attr:`app.db.models.audit.ReadAuditLog.subject_id` 的列注释）。
    ⚠️ 而**匿名读不进本表**（:class:`ReadAuditMiddleware` 的主体那一半 +
    ``ck_read_audit_log_subject_kind`` 那一道 DB 闸），故「谁翻的」在本表上
    **永远答得出来**：``subject_kind='student'`` → 看 ``subject_id``，
    ``subject_kind='teacher'`` → 看 ``staff_no``（``subject_id`` 在 cookie 那一档也有值）。

    ⚠️ ``at`` 是 **naive 本地时刻**（:data:`app.config.TIMEZONE`），与
    :class:`AuditLogRead` **同一个时钟所有者**（:func:`app.auth.sessions.now`），
    故运维把两张表按时间对齐着看时不会差 8 小时。前端**不得**按 UTC 解释它。
    """

    id: int
    at: dt.datetime
    subject_kind: str
    subject_id: int | None = None
    staff_no: str | None = None
    route: str
    student_id: int | None = None
    status: int
    target: str | None = None


class ReadAuditLogPageRead(BaseModel):
    """``GET /api/read-audit-logs`` 的响应体：**四个信封键**，与泛型 list 逐字同形。

    ⚠️ 它与 :class:`AuditLogPageRead` **同形而不同类**（``items`` 的元素类型不同），
    故**刻意不共用一个泛型基类**：本仓的四个信封键在
    :func:`app.api.crud._list_page`、:func:`app.api.routers.audit.list_audit_logs`
    与本端点三处拼装，⚠️ 而那一格的口径一致性由**三条**「恰好四个键」的守卫各自钉住
    （``test_the_envelope_has_exactly_the_four_keys_of_a_generic_list`` 与读审计那一条），
    不是由一个共同基类钉住。⚠️ 如实记（硬规矩 #39）：给这三处抽一个
    ``Page[T]`` 泛型基类是**能做**的，而它会让「未定型响应 24 个」那一格少一个
    （泛型 list 的那 23 个之所以未定型，正是因为端点返回的是现拼的 ``dict``），
    那是一次跨 23 个资源的契约面改动，超出本 Task 范围。已登记为待清扫。
    """

    items: list[ReadAuditLogRead]
    total: int
    limit: int
    offset: int


class ReadAuditLogFilter(BaseModel):
    """两个过滤参数。用法是 ``filters: ReadAuditLogFilter = Depends()``。

    ⚠️ **只有两个**，与 :class:`AuditLogFilter` 同一条口径（「过滤参数不要超过 3 个，
    够用即可，别过度设计」）。⚠️ 而两格里**一格与写审计相同、一格不同**，
    差别正是两张表各答的那一句：

    * ``subject_kind`` —— 「**哪一类人**翻的」（与写审计逐字同一个键名；
      ⚠️ 而取值域**不同**：本表是**两档**，``anonymous`` 不在里面）。
      ⚠️ 于是「传 ``anonymous`` 过来」在本端点是 **422**、在写审计端点是 200 + 0 行。
      那一格是**要的**：本表结构上不可能有匿名行，回一个空的 200 等于让运维以为
      「今天没有匿名读」，而真话是「本表根本不记匿名读」。
    * ``student_id`` —— ⚠️ **本表独有**，而它正是这张表存在的理由：
      「**这一个学生**的档案被谁翻过」。⚠️ 走 SQL 层的 ``WHERE``、且**有索引**
      （``ix_read_audit_log_student_id_at``）。

    ⚠️ **刻意没有的三个**（每一个都想过、都不加；前两个的理由与
    :class:`AuditLogFilter` 逐字相同，本处不抄第二份）：

    * ``staff_no`` / ``subject_id`` —— 加了就要一并定「一个教师能不能查另一个教师」；
    * ``since`` / ``until`` —— 时间窗要一个日期解析口径（含时区）；
    * ``route`` —— ⚠️ 这一个**看起来最该加**（「谁翻过周训练单」），而本 Task 不加，
      两条理由：① 管理台那一页今天按 ``id DESC`` 一次 ``LIMIT 200`` 就够翻
      （60 个学生的学校，一天的敏感读是几百行量级）；② 它的取值域是**47 个模板串**，
      而一个下拉里塞 47 个 ``/api/students/{student_id}/training-logs/completion-rate``
      这样的串，比不给这个过滤更难用。⚠️ 要加的话正确的形状是**按
      :data:`app.api.read_audit.READ_CLASSES` 的 11 个类**过滤（``?kind=STUDENT_ROSTER``；
      ⚠️ 时点账，Plan 08 Task 8 改对，此前写着 10 —— 唯一所有者是 ``READ_CLASSES`` 本身），
      而那需要把「类」这一格也落进表里（今天它只在判据里、不在行上）。
      如实记为待清扫。
    """

    subject_kind: str | None = None
    student_id: int | None = None

    @field_validator("subject_kind")
    @classmethod
    def _subject_kind_in_the_read_domain(cls, value: str | None) -> str | None:
        """⚠️ 取值域是 :attr:`app.db.models.audit.ReadAuditLog.SUBJECT_KINDS`
        （**两档**），不是 :attr:`app.db.models.audit.AuditLog.SUBJECT_KINDS`（三档）。

        ⚠️ 两个 ``one_of`` 调的是**同一个**校验函数、传的是**两个不同的模型类常量**，
        故「加第三类身份」时改 :attr:`app.db.models.auth.UserSession.KINDS` 一处、
        两个过滤器一起跟上（:data:`app.db.models.audit.READ_SUBJECT_KINDS` 由它生成）。
        """
        return one_of("subject_kind", value, ReadAuditLog.SUBJECT_KINDS)
