"""``GET /api/audit-logs`` 的请求与响应契约（Plan 06 Task 5 加的**第 11 个** schema 模块）。

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
from app.db.models.audit import AuditLog

__all__ = ["AuditLogFilter", "AuditLogPageRead", "AuditLogRead"]


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
