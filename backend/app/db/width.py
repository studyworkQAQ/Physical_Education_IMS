"""**客户端可控的串怎么落进一个「声明了有限宽度」的列**（Plan 06 Task 12 / C1）。

--------------------------------------------------------------------------
⚠️⚠️ 本模块存在的全部理由：SQLite **不强制** ``VARCHAR(n)`` 的长度
--------------------------------------------------------------------------

实测（Plan 06 Task 11 与 Task 12 各量过一遍）：往一个声明 ``String(32)`` 的列里写
500 个字符，SQLite **不报错、读回来也不截断**。于是「声明宽度 ≥ 实写长度」这件事在
本仓今天**没有任何一处会响**——而它在换后端的那天会以两种不同的方式响：

* **PostgreSQL** → ``value too long for type character varying(32)``（**响亮**）；
* **MySQL**（非严格模式）→ **静默截断**（比响亮更坏：数据被改了而没人知道）。

⚠️⚠️ 而在本仓，「响亮」那一档的后果**也不只是报错**：Task 5/6 的裁定是
「**审计写失败不许让业务写看起来失败**」（:mod:`app.api.audit` 模块 docstring 最后一节），
故审计行的写入失败是**被吞掉**的 —— 一条超长的请求路径能让**那一行的审计彻底消失**。
那是**攻击者可控的审计缺失**：他只要把 URL 写到 300 字符，就能让「他对什么做了什么」
这一格在库里查不到，而业务响应码看起来完全正常。

--------------------------------------------------------------------------
⚠️⚠️ 处置分三档，而**选哪一档是每一列的语义决定**（住在调用方）
--------------------------------------------------------------------------

================================  ==========================================
列的语义                            处置
================================  ==========================================
**证据/原文**（``audit_log.path``   :func:`truncate` —— 按声明宽度截断，
/ ``audit_log.target`` /              并**留下可辨识的标记**
``login_attempt.login``）             （:data:`OVERLONG_SUFFIX`）
**有格式的身份/地址**               :func:`overlong_sentinel` —— 落一个
（``audit_log.staff_no`` /            **不可能被误认成真值**的哨兵
``login_attempt.ip``）                （截一个 IP 会得到一个**假 IP**，
                                      截一个工号会得到一个**假工号**）
**取值域有限**                      **不截、不落哨兵**：判据本来就在
（``audit_log.method`` /              写入路径上（:func:`app.api.audit.should_record`
``audit_log.subject_kind`` /          那道方法闸门、``ck_*`` 那些 CHECK 约束），
各表的枚举列）                        守卫量的是「域内最长值 ≤ 声明宽度」
**请求体的业务字段**                :func:`ensure_fits` —— **拒绝**（422）。
（``student.name`` 一族）             ⚠️ 截断一个学生的姓名是**数据损坏**、
                                      不是有界；这一档必须让调用方知道自己送宽了
================================  ==========================================

⚠️ 于是本模块**只持有「宽度」这一件事的知识**（标记长什么样、哨兵长什么样、
怎么从模型上读出声明宽度），**不持有「哪一列该用哪一档」**——后者是每一列的语义，
逐格的理由写在**调用方**（:func:`app.api.audit.record` / :func:`app.auth.policy._key` /
:func:`app.api.crud.build_crud_router` 里那两个写端点）。

--------------------------------------------------------------------------
⚠️ 标记的形状：**尾缀**，且**总长恒等于声明宽度**
--------------------------------------------------------------------------

:data:`OVERLONG_SUFFIX` = ``"…[cut]"``（**6 个字符**：一个 ``…`` + ``[cut]``）。
:func:`truncate` 保留前 ``width - 6`` 个字符再接上它，故：

* **总长恰好等于 ``width``**，一个字符都不多（⚠️ 派单逐字要求「不许把总长推过声明宽度」）；
* ⚠️ **选尾缀而不是前缀**：审计的 ``path`` 要答的是「对**哪一个**做了什么」，
  路径的**前**半段（``/api/students/12``）才是信息，后半段是填充；
  限流键同理（``bind:2023120001…`` 的前缀是「用途」那一维，:func:`app.auth.policy._key`）。
  把标记放前面会把唯一有信息量的那几个字符挤掉。
* ⚠️ **``…`` 而不是 ``...``**：一个字符顶三个，而 ``width - 6`` 与 ``width - 8``
  的差别在窄列上（``String(16)``）是 12.5% 的可用信息。
* ⚠️ **``[cut]`` 而不是只留一个 ``…``**：一个孤零零的 ``…`` 会出现在**真实数据**里
  （一个省号式的名字、一段被复制粘贴的引文），于是「这一格被截过」与「这一格本来就
  有个省略号」不可分辨。``…[cut]`` 是一个不会自然出现的串。
* ⚠️ **而「被截过」这件事必须看得出来**（派单逐字要求「不许静默截断」）：
  读审计的人要能判断「这一行的 path 是完整的、还是被切掉的」。

--------------------------------------------------------------------------
⚠️ 它**刻意不是**一个 SQLAlchemy 事件钩子（``before_flush`` 一类）
--------------------------------------------------------------------------

一个全局钩子看起来更「扫得全」（任何写入路径都跑不掉），实现者**顶回**，三条理由：

1. **失效方向错**：钩子在 ``flush`` 时才跑，那一刻抛出来的是 ``IntegrityError``
   一族 → 经 :mod:`app.api.errors` 折成 **409**（``integrity_conflict``）。
   而「客户端送了一个超宽的字段」是请求校验错误，正确的码是 **422**
   （与 :func:`app.api.schemas._base.one_of` 把枚举越界从 409 挪到 422 是同一条口径）。
2. **它会把三档处置压成一档**：审计要的是「截断 + 标记，**绝不失败**」，
   请求体要的是「拒绝」，钩子只有一个动作可选。
3. **它会连带管住管道与 seed**（那些写入的值全部来自仓库内的 YAML / 生成器，
   不是客户端），把一条关于**信任边界**的纪律铺到不需要它的地方 ——
   而 seed 一旦撞上一次拒绝，症状是「演示库灌不进去」，离真因隔一整层。

故本模块是**三个显式的收口点**各自调它（收口点清单见
``tests/api/test_column_widths.py`` 的模块 docstring），而不是一道全局闸。

--------------------------------------------------------------------------
本模块的位置（``tests/architecture/test_layering.py`` 看着）
--------------------------------------------------------------------------

``app.db`` 是依赖图的下层，它**只 import 标准库与 sqlalchemy**、不 import 任何 ``app.*``。
两个消费者（:mod:`app.auth.policy` 与 :mod:`app.api`）都是**向下**依赖它，故无环。
⚠️ 它**住在 ``app/db/`` 而不是 ``app/db/models/``**：后者是表定义包、且有一个
``_MODELS_PUBLIC_BASELINE``（33）的导入面守卫（Ruling 97），往里加一个与表无关的
工具模块会把那个基线抬到 34 —— 而那正是 Ruling 97 逐字禁止的动作。
⚠️ ``app/db/__init__.py`` 今天是**空文件**，故加本子模块不改 ``app.db`` 的任何导入面。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import String

__all__ = [
    "OVERLONG_SUFFIX",
    "declared_width",
    "ensure_fits",
    "overlong_sentinel",
    "truncate",
]

#: 「这一格被截过」的**可辨识标记**。⚠️ 它的**长度是承重的**：
#: :func:`truncate` 用 ``width - len(本串)`` 决定保留多少个原文字符，
#: 故把它改长会让窄列上可用的信息变少（逐字理由见模块 docstring 的「标记的形状」）。
#: ⚠️ 6 个字符 = 1 个 ``…`` + 5 个 ``[cut]``。
OVERLONG_SUFFIX = "…[cut]"


def declared_width(column: Any) -> int | None:
    """一个列**声明**的宽度；不是「有限宽度的 ``String``」就回 ``None``。

    ⚠️ 它是「声明宽度是多少」这件事在本仓的**唯一读点**：三个收口点与守卫都经它，
    故「把某一列改宽/改窄」会自动跟着改这里的判定 —— 而**没有任何一处硬编码宽度数字**
    （派单逐字要求「期望侧必须从模型声明推出来」）。

    ⚠️ ``Text`` / ``JsonText`` 那一类**无界**列回 ``None``（``type.length`` 是 ``None``），
    于是「本模块管不管这一列」与「这一列有没有声明宽度」是同一个判据，
    不需要第二份清单。⚠️ 那些列因此**天然不是宽度炸弹**（它们没有宽度可炸），
    而「一个无界列会无限长」是另一件事（本仓的 ``audit_log`` 刻意**没有**那样的列，
    逐字理由见 :mod:`app.db.models.audit` 的模块 docstring 第三节）。
    """
    length = getattr(column.type, "length", None)
    if isinstance(column.type, String) and isinstance(length, int) and length > 0:
        return length
    return None


def truncate(value: str | None, width: int | None) -> str | None:
    """**证据/原文**那一档：超宽就按 ``width`` 截断，并留下 :data:`OVERLONG_SUFFIX`。

    ⚠️ ``width is None``（= 那一列**没有**声明宽度，:func:`declared_width` 的判据）
    时**原样返回**：一个 ``Text`` 列没有宽度可判，而「无界」是它的声明、不是一次遗漏。
    ⚠️ 于是调用方可以直接把 :func:`declared_width` 的结果接进来，
    不需要在外面再写一个 ``if width is not None``（那会是本判据的第二个住址）。

    ⚠️ **不超宽时逐字原样返回**（``value`` 本身，不是它的拷贝）：绝大多数写入落在这一支，
    故本函数在热路径上的成本是一次 ``len()`` 比较。
    ⚠️ ``None`` 原样返回（可空列的 ``NULL`` 不是一个「长度为 0 的串」，
    把它折成 ``""`` 会让「这一格没有值」与「这一格是空串」在库里不可分辨）。

    ⚠️ **极窄列那一支**（``width <= len(OVERLONG_SUFFIX)``）：标记本身装不下，
    于是只留标记的前 ``width`` 个字符。⚠️ 它今天**不可达**（全库最窄的
    ``String(n)`` 是 ``String(8)``，而标记是 6 个字符），故它是许可而不是断言
    （硬规矩 #39）；留着它的理由是失效方向 —— 有人建一个 ``String(4)`` 的列时，
    本函数**仍然返回一个不超过声明宽度的串**，而不是一个把炸弹原样传下去的串。
    """
    if width is None or value is None or len(value) <= width:
        return value
    keep = width - len(OVERLONG_SUFFIX)
    if keep <= 0:
        return OVERLONG_SUFFIX[:width]
    return value[:keep] + OVERLONG_SUFFIX


def overlong_sentinel(value: str | None, width: int | None) -> str | None:
    """**有格式的身份/地址**那一档：超宽就落一个哨兵，**不截断**。

    ⚠️⚠️ 它与 :func:`truncate` 的差别是**语义**的、不是修辞的（派单点名要这一格）：
    截断一个 IP 会得到一个**语法上仍然像 IP 的假 IP**（``"2001:db8::1234…[cut]"``
    的读法可以是任何东西），截断一个工号会得到一个**看着像真工号的假工号** ——
    而审计那一格的全部用途就是「**指认一个人**」。一个指认到不存在的人的值
    比一个明确写着「这里装不下」的值坏得多（前者是一句假话，后者是一句实话）。

    ⚠️ 哨兵的形状是 ``<over:原文长度>``（例如 ``<over:400>``）：

    * ``<`` / ``>`` 不在 IP 的文本形式里、也不在本仓的工号/学号形状里
      （``T0001`` / ``2023120001``），故它**不可能被误认成一个真值**；
    * ⚠️ 而它**保住了原文长度**这一格：「有人送了一个 400 字符的工号」与
      「有人送了一个 4 000 字符的工号」是不同的探测强度，
      截断/固定哨兵都会把这一格抹平。
    * ⚠️ 装不下时（``width`` 比 ``<over:N>`` 还窄）退化成 ``<over>``，
      再装不下就按宽度切 —— 与 :func:`truncate` 同一条失效方向：**恒不超过声明宽度**。
    """
    if value is None or width is None or len(value) <= width:
        return value
    text = f"<over:{len(value)}>"
    if len(text) <= width:
        return text
    fallback = "<over>"
    return fallback if len(fallback) <= width else fallback[:width]


def ensure_fits(table: Any, values: dict[str, Any]) -> None:
    """**请求体**那一档：任何一个字符串值超过它那一列的声明宽度就抛 :class:`ValueError`。

    ⚠️ 抛 ``ValueError`` 而不是 ``HTTPException``：本模块不 import ``fastapi``
    （它是 ``app.db`` 层的），而 :mod:`app.api.errors` 已经把 ``ValueError`` 折成
    **422 ``unprocessable_value``** 并**带上消息原文**（与
    :func:`app.api.schemas._base.one_of` / :func:`app.auth.passwords.ensure_acceptable`
    逐字同一条链）。

    ⚠️⚠️ **这一档刻意是「拒绝」而不是「截断」**（派单给了截断/校验/拒绝三选一，
    实现者对**请求体的业务字段**选拒绝，理由逐字如下）：
    截断一个 ``student.name`` 会得到一个**看起来正常的假姓名**（``"张…[cut]"``）
    写进名册，而下一次打印学籍卡时它就是一个错的名字 —— 那是**数据损坏**，
    比拒绝一次请求坏得多。⚠️ 对照 :func:`truncate` 服务的那三格
    （``path`` / ``target`` / 限流键）：它们的原文是**攻击者送的垃圾**，
    截断它没有损坏任何人的数据，只是把一条证据裁短、并且**标明裁过**。
    同一个动作在两档上的价值相反，故两档用两个函数、而不是一个开关。

    ⚠️ **它只判「声明了有限宽度的 ``String`` 列」**（经 :func:`declared_width`）：
    数值列、日期列、``Text`` / ``JsonText`` 列一律放过（后者没有宽度可判）。
    ⚠️ 键不在表上的（``values`` 里混进了一个不是列名的键）也放过：
    那一档由 SQLAlchemy 自己在 ``model(**values)`` 上抛 ``TypeError``，
    本函数不去替它答（两个所有者答同一个问题会漂）。

    ⚠️ 报错文本里点名了**列名、声明宽度与实送长度**三格：422 的 ``message``
    是给**人**看的（:mod:`app.api.errors` 的模块 docstring），而「哪个字段送宽了」
    正是前端表单要标红的那一格。
    """
    for name, value in values.items():
        if not isinstance(value, str) or name not in table.c:
            continue
        width = declared_width(table.c[name])
        if width is not None and len(value) > width:
            raise ValueError(
                f"{table.name}.{name} 最多 {width} 个字符（收到 {len(value)} 个）："
                f"这一列声明的是 VARCHAR({width})，超宽的值在 PostgreSQL 上会被拒绝、"
                f"在 MySQL 上会被静默截断，故本系统在写入之前就拒掉它"
            )
