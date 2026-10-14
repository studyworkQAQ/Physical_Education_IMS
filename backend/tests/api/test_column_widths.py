"""**「客户端可控的串不许超过它那一列的声明宽度」**（Plan 06 Task 12 / C1）。

--------------------------------------------------------------------------
⚠️⚠️ 本文件守的是全仓 **68** 格 ``String(n)`` 列，而不是某几格
--------------------------------------------------------------------------

派单逐字要求的是「**一条守卫扫全面**」+「期望侧必须从模型声明推出来，不许硬编码数字」。
于是本文件的形状是：

1. **一张全覆盖的分类账**（下面那五个集合）。⚠️ 它的性质是**集合相等**、
   不是「包含」：:func:`test_every_declared_width_column_is_classified_and_the_classes_are_disjoint`
   断言「五个类的并 == 全库每一格声明了有限宽度的 ``String`` 列」且「两两不相交」。
   ⚠️ 于是**加一张表、加一列**都会当场红，而红的方式是「这一格没人分类」——
   那正是想要的：下一个人必须**做一个决定**（这一列的值从哪来、由谁收口），
   而不是让一格新的宽度炸弹静默地混进来。
2. **每一类各有自己的牙**，而牙一律**从模型上读宽度**
   （:func:`app.db.width.declared_width`），本文件里**没有一个宽度数字**。
   ⚠️ 唯一出现的字面量是「灌多长」那一侧（``+ 1`` / ``* 500`` 一类），
   那是**被测侧**，不是期望侧（硬规矩 #35：两侧不同源）。

--------------------------------------------------------------------------
⚠️ 五个类 = 五种「值从哪来」，而**处置跟着来源走**
--------------------------------------------------------------------------

===========================  =============================================
类                            处置与牙
===========================  =============================================
:data:`_REQUEST_METADATA`     请求的**元数据**（路径 / 路径段 / 请求头 /
                              限流键）→ 在三个收口点上**截断 + 标记**或
                              **落哨兵**；牙是**真发一条超宽的请求**再量落库长度
:data:`_DOMAIN_BOUNDED`       取值域有限、且**不经请求体**（审计的方法与主体、
                              会话的两格、限流的 ``kind``、打卡的 ``feeling``）
                              → 牙是「域内最长值 ≤ 声明宽度」，域从**模型类常量**读
:data:`_IDENTITY_DERIVED`     值来自一个**已经过了在册校验**的身份
                              → 牙是「本列 ≥ 它来源那一列」，两侧都从模型读
:func:`_body_columns`         请求体的业务字段（9 个可写资源的 15 格）
                              → **拒绝**（422）；牙是逐格调
                              :func:`app.db.width.ensure_fits`，红绿两档都在场
:data:`_SERVER_OWNED`         值不来自任何一次 HTTP 请求（管道 / seed / 领域算式 /
                              服务端常量 / 仓库内的 YAML 模板）
                              → 没有客户端可驱动的路径，故**逐表给出理由**、
                              不设运行时牙（⚠️ 理由写在下面那张账上，
                              它是「这一格我核过了」的取证，不是凑数）
===========================  =============================================

--------------------------------------------------------------------------
⚠️ 三个收口点（本文件钉住它们**确实**被接上了，而不只是函数本身对）
--------------------------------------------------------------------------

* :func:`app.api.audit.record` —— 全仓唯一写 ``audit_log`` 的函数
  （``path`` / ``target`` 截断，``staff_no`` 哨兵）；
* :func:`app.auth.policy._key` 与 :func:`app.auth.policy._ip` ——
  ``login_attempt`` 那两格的唯一写入口；
* :func:`app.api.crud.build_crud_router` 里的 ``create_row`` / ``update_row``
  —— 9 个可写资源的 15 格请求体字段的唯一写入口。

⚠️ 逐格的**端到端**取证（超长路径 / 超长路径段 / 超长请求头工号 / 匿名超长绑定探测 /
超长请求体字段 / ``GET /api/audit-logs`` 读得回来）各有一条测试，
它们**真发 HTTP 请求**、真读库，不走任何替身（运行时口径，硬规矩 #89）。

--------------------------------------------------------------------------
⚠️ 隐私纪律（派单 §1 第 6 条）：本波**没有新增任何审计列**
--------------------------------------------------------------------------

``audit_log`` 仍然是 **9** 列、``login_attempt`` 仍然是 **6** 列、
``user_session`` 仍然是 **8** 列 —— 逐字实测写在
:func:`test_no_user_agent_is_stored_anywhere_and_no_column_was_added_by_this_wave` 里。
⚠️ 那一格是本波的一个**明确不做**：``User-Agent`` 原文可以任意长（实测灌 2 000 字符），
而全库**没有任何一列**存它（``user_session`` 与 ``login_attempt`` 都没有 ``user_agent``），
故它今天**不是**宽度炸弹。把它纳入审计要先过
``tests/api/test_audit_api.py`` 的
``test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row``
那一档隐私取证的口径重裁，**本波刻意不做**，已登记为待清扫。
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Session

from app.api import audit as audit_module
from app.api.routers.catalog import RESOURCES
from app.auth import policy
from app.db import width
from app.db.models.audit import AuditLog
from app.db.models.auth import LoginAttempt, UserSession
from app.db.models.feedback import TrainingLog
from app.db.models.organisation import Student, Teacher
from app.db.session import Base

#: --------------------------------------------------------------------------
#: 类 1：**请求元数据**（值是一次 HTTP 请求的原文，故匿名可控）
#: --------------------------------------------------------------------------
#:
#: 每一项是 ``(表, 列, 处置)``，处置只有两档，两档的**语义差别**逐字写在
#: :func:`app.db.width.truncate` 与 :func:`app.db.width.overlong_sentinel` 里：
#:
#: * ``truncate`` —— **证据/原文**：截断并留下 :data:`app.db.width.OVERLONG_SUFFIX`。
#:   ``audit_log.path`` 的信息全在前半段（打的是哪个端点），``login_attempt.login``
#:   的前缀是「用途」那一维，故两格都是「保住前面、标明切过」。
#: * ``sentinel`` —— **有格式的身份/地址**：落 ``<over:原文长度>``，
#:   **不截断**（截一个工号会得到一个看着像真工号的假工号，截一个 IP 会得到一个假 IP）。
_REQUEST_METADATA: tuple[tuple[str, str, str], ...] = (
    # ← ``request.url.path`` 的原文。⚠️ 实测改前：一条 400 字符的 URL 落库 **401**
    #    个字符（含前导 ``/``），声明 ``String(256)``。⚠️ 而它在本仓的后果比
    #    「PG 上报错」坏：审计写失败被 :class:`app.api.audit.AuditMiddleware` 吞掉
    #    （Task 5/6 的裁定），故一次超宽写入 = **那一行审计静默消失**。
    ("audit_log", "path", "truncate"),
    # ← ``scope["path_params"]`` 的原文（:func:`app.api.audit.target_of`）。
    #    ⚠️ 实测改前：``PATCH /api/students/<400 字符>`` 落库 **400** 个字符，
    #    声明 ``String(64)``。⚠️ 而那一档的业务响应是 **422**（``pk_value: int``
    #    校验不过），故「422 的请求也照样留痕」与「留痕本身炸了」同时成立。
    ("audit_log", "target", "truncate"),
    # ← 开发档的 ``X-Teacher-Staff-No`` **请求头原文**：
    #    :func:`app.api.deps.current_teacher` 调 :func:`app.api.audit.note_subject`
    #    排在 ``require_staff`` **之前**，故一个不在册的超长工号也走到审计。
    #    ⚠️ 实测改前：落库 **400** 个字符，声明 ``String(32)``。
    #    ⚠️ 生产档下这一支不可达（请求头通道被强制关），而「不可达」是一个
    #    环境变量的距离，故照设防。
    ("audit_log", "staff_no", "sentinel"),
    # ← 限流键的后半段（:func:`app.auth.policy._key`）。⚠️ 实测改前：一个**匿名**的
    #    ``POST /api/auth/students/bind`` 带一个 500 字符的学号，落库 **505** 个字符
    #    （``len("bind:") + 500``），声明 ``String(64)``。
    #    ⚠️ 它是本类里唯一一格**匿名可驱动**且**不经任何闸门**的
    #    （绑定那一档对「不在册」的标识**照样计数**，那是
    #    :class:`app.db.models.auth.LoginAttempt` 模块 docstring 第三节逐字要求的）。
    ("login_attempt", "login", "truncate"),
    # ← ``request.client.host``。⚠️ **今天不是客户端可控的**（本仓没有任何一处解析
    #    ``X-Forwarded-For``；实测最长写入是 ``testclient``，10 个字符），
    #    故它在本类里是**防御性**的一格：``record_failure`` / ``record_success``
    #    是公有面，而「把反代塞进来的 XFF 也存上」正是那一列的注释点名预留的将来。
    ("login_attempt", "ip", "sentinel"),
)

#: --------------------------------------------------------------------------
#: 类 2：**取值域有限**，且**不经请求体**（故 :func:`app.db.width.ensure_fits` 看不见它）
#: --------------------------------------------------------------------------
#:
#: 每一项是 ``(表, 列, 取值域)``，取值域一律**引模型类常量/模块常量那一个对象**
#: （本包约定 2：类常量是唯一真相），故「域里最长的那个值」是**量出来的**。
#: ⚠️ 牙是 ``max(len(v) for v in 域) <= 声明宽度``：域是加一个值就会变的东西，
#: 而声明宽度是改一列就会变的东西，两侧都从模型读 ⇒ 任一侧动了本条都跟着动。
_DOMAIN_BOUNDED: tuple[tuple[str, str, frozenset | set], ...] = (
    # ⚠️ 它的写入路径**已经有校验**（派单要求先实测）：
    #    :func:`app.api.audit.should_record` 那道方法闸门 —— ``dispatch`` 只在
    #    ``method.upper() in AUDITED_METHODS`` 时才调 ``record``。
    #    ⚠️ 实测取证：一个 400 字符的方法令牌得到 **405**、审计**一行都不多**。
    ("audit_log", "method", audit_module.AUDITED_METHODS),
    # ← 三档（``student`` / ``teacher`` / ``anonymous``），另有 DB 层的
    #    ``ck_audit_log_subject_kind`` 兜底；值只由四个内部调用点给，不经请求原文。
    ("audit_log", "subject_kind", AuditLog.SUBJECT_KINDS),
    ("login_attempt", "kind", LoginAttempt.KINDS),
    ("user_session", "kind", UserSession.KINDS),
    ("user_session", "role", UserSession.ROLES),
    # ← ``POST /api/training-logs`` 的请求体字段，**而它已经过
    #    :func:`app.api.schemas._base.one_of` 校验**（域外值 → 422，
    #    在 :func:`app.db.width.ensure_fits` 之前就答完了），故归本类而不归类 4。
    ("training_log", "feeling", TrainingLog.FEELINGS),
)

#: --------------------------------------------------------------------------
#: 类 3：**身份派生**（值是一个**已经过了在册校验**的工号/学号）
#: --------------------------------------------------------------------------
#:
#: 每一项是 ``(表, 列, 来源表, 来源列)``。⚠️ 牙是「本列的声明宽度 ≥ 来源列的声明宽度」：
#: 只要来源那一列有界，本列就有界，而来源那一列的界由类 4 的
#: :func:`app.db.width.ensure_fits` 守着（``teacher.staff_no`` 在可写资源的清单里）。
_IDENTITY_DERIVED: tuple[tuple[str, str, str, str], ...] = (
    # ← :func:`app.api.routers.feedback.batch_mini_tests` 写它，而**第一行**就是
    #    ``require_staff(session, staff_no)``（不在册 → 403），故写进来的一定是
    #    ``teacher.staff_no`` 上**真实存在**的那一个值。
    #    ⚠️ 与 ``audit_log.staff_no`` 的差别正是**顺序**：审计的 ``note_subject``
    #    排在闸门**之前**（它要记的就是「有人拿这个串试了一次」），故那一格是类 1。
    ("mini_test", "entered_by", "teacher", "staff_no"),
)

#: --------------------------------------------------------------------------
#: 类 5：**服务端所有**（值不来自任何一次 HTTP 请求的原文）
#: --------------------------------------------------------------------------
#:
#: ``表 → (理由, 列)``。⚠️ 这一张账是「**这一格我核过了**」的取证，不是凑数：
#: 它的存在让「全覆盖」那条断言成为一条**集合相等**（于是新列会红），
#: 而理由让读的人不必再把 42 条写入路径重走一遍。
_SERVER_OWNED: dict[str, tuple[str, frozenset[str]]] = {
    "alert": (
        "app.pipeline.alert_stage 按仓库内的 alert_rules.yaml 生成；HTTP 侧只有 "
        "status 那一格被 handle 端点改，而它写的是 ALERT_HANDLED / ALERT_IGNORED "
        "两个模块常量（客户端那句自由文本落在 handled_action，那是 Text、无界）",
        frozenset({"level", "rule_id", "status", "subject_key", "window_key"}),
    ),
    "class_session": (
        "rpe_token 由 app.api.routers.feedback._new_rpe_token() 生成"
        "（secrets.token_urlsafe 截到 ClassSession.RPE_TOKEN_LEN）",
        frozenset({"rpe_token"}),
    ),
    "cleaning_log": (
        "app.pipeline.clean 的产物：三格的值都是**仓库内**的字段名与规则名，"
        "不是 CSV 里的原文（CSV 的原文落在 message，那是 Text）",
        frozenset({"field", "kind", "student_no"}),
    ),
    "daily_sync_run": (
        "app.pipeline.daily 的产物，status 是那三个模块常量之一",
        frozenset({"status"}),
    ),
    "derived_metrics": (
        "app.domain.derive 的产物（trend 是 Trend 枚举的字面值）",
        frozenset({"trend"}),
    ),
    "exercise": (
        "app.refdata_prescription 从 backend/data/ 里的 YAML 模板加载（仓库内的"
        "受控文件，禁区之一），不经任何 HTTP 请求",
        frozenset({"equipment", "impact_level", "name", "ref", "video_url"}),
    ),
    "fitness_test_result": (
        "national_grade 由 app.domain.indicators 按国标表算出",
        frozenset({"national_grade"}),
    ),
    "notification": (
        "app.notify / alert_stage 生成，两格都是模块常量",
        frozenset({"channel", "recipient_kind"}),
    ),
    "percentile_snapshot": (
        "app.pipeline.percentile_stage 生成（item / sex / age_group / source "
        "四格都是枚举字面值或国标年级组）",
        frozenset({"age_group", "item", "sex", "source"}),
    ),
    "prescription": (
        "app.domain.prescription.assembler 生成；HTTP 侧的 overrides 端点只往 "
        "teacher_overrides 那一格 JsonText 里追加，不写这三格",
        frozenset({"label_at_generation", "status", "template_ref"}),
    ),
    "prescription_template": (
        "与 exercise 同一份 YAML 模板（backend/data/，禁区），不经 HTTP",
        frozenset({"body_comp", "layer", "review_status", "reviewer",
                   "template_ref", "version", "weakness"}),
    ),
    "stratification_result": (
        "app.domain.stratify 生成（label / percentile_source 是枚举字面值，"
        "hit_rules 是规则 id 的拼接、而规则 id 住在仓库内的 YAML 里）",
        frozenset({"hit_rules", "label", "percentile_source"}),
    ),
    "student": (
        "password_hash 是 app.auth.passwords.hash_password 的**自描述串**"
        "（实测恒 89 个字符，与口令原文多长无关），不是请求体里的口令",
        frozenset({"password_hash"}),
    ),
    "teacher": (
        "与 student.password_hash 同一条（同一个函数、同一个定长形状）",
        frozenset({"password_hash"}),
    ),
    "training_log": (
        "source 恒为 app.api.routers.feedback.CHECKIN_SOURCE 那一个模块常量"
        "（feeling 不归这里，它在类 2）",
        frozenset({"source"}),
    ),
    "user_session": (
        "id 是 secrets.token_urlsafe(TOKEN_BYTES) —— 那一格另有自己的守卫"
        "（tests/auth/test_sessions.py 的 "
        "test_the_token_fits_the_column_and_the_column_is_exactly_as_wide）",
        frozenset({"id"}),
    ),
    "weekly_adjustment": (
        "app.domain.prescription.weekly 生成，source 是那一档的枚举字面值",
        frozenset({"source"}),
    ),
}

#: 类 4（**请求体的业务字段**）刻意**不是一张清单**：它从
#: :data:`app.api.routers.catalog.RESOURCES` 里 ``writable=True`` 的那些资源**推出来**
#: （表 × 该表 Create/Update schema 上真实存在的字符串字段），故「加一个可写资源」
#: 会自动进本类、不需要记得改本文件。⚠️ 于是「全覆盖」那条断言对类 4 也是活的。
#:
#: ⚠️ 处置是**拒绝**（422）而不是截断：截断一个 ``student.name`` 会得到一个
#: **看起来正常的假姓名**写进名册，那是数据损坏；逐字理由见
#: :func:`app.db.width.ensure_fits` 的 docstring。
#: ⚠️ 于是本类**没有**一个模块级常量：那一格「处置是什么」的住址是
#: :func:`app.db.width.ensure_fits` 自己（在这里再存一个字面量 ``"reject"``
#: 就是第二个所有者，而它谁也不驱动 —— 硬规矩 #39）。


def _declared(table_name: str, column_name: str) -> int:
    """一格 ``String(n)`` 的声明宽度（**从模型读**，本文件不写宽度数字）。"""
    got = width.declared_width(Base.metadata.tables[table_name].c[column_name])
    assert got is not None, f"{table_name}.{column_name} 不是一格有限宽度的 String"
    return got


def _every_string_column() -> set[tuple[str, str]]:
    """全库每一格「声明了有限宽度的 ``String``」列。"""
    out: set[tuple[str, str]] = set()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if width.declared_width(column) is not None:
                out.add((table.name, column.name))
    return out


def _body_columns() -> set[tuple[str, str]]:
    """类 4：可写资源 × 它的 Create/Update schema 上真实存在的字符串列。"""
    out: set[tuple[str, str]] = set()
    for entry in RESOURCES:
        if not entry.get("writable"):
            continue
        table = entry["model"].__table__
        fields = set(entry["schemas"].create.model_fields) | set(
            entry["schemas"].update.model_fields
        )
        for column in table.columns:
            if width.declared_width(column) is not None and column.name in fields:
                out.add((table.name, column.name))
    return out


def _server_owned_columns() -> set[tuple[str, str]]:
    return {
        (table, column)
        for table, (_reason, columns) in _SERVER_OWNED.items()
        for column in columns
    }


# ==========================================================================
# ① 全覆盖：五个类两两不相交，且并集 == 全库每一格 String(n)
# ==========================================================================
def test_every_declared_width_column_is_classified_and_the_classes_are_disjoint():
    """**扫全面**的那一条：任何一格 ``String(n)`` 都必须被**恰好一个**类认领。

    ⚠️ 它是本文件最重要的一条，而它的牙是**集合相等**（不是包含）：

    * **多了一格没人认领** → 红，报出那一格的名字。下一个人必须回答
      「这一列的值从哪来、由谁收口」，而**不能**靠「没写进清单所以没人管」混过去；
    * **两个类都认领同一格** → 红。⚠️ 那一格不是理论上的：本波实测过
      ``student.sex`` / ``teacher.role`` / ``course_section.grouping_mode`` 三格
      **同时**是「请求体字段」与「取值域有限」，而两类的处置不同（422 的 code 也不同：
      ``request_validation_failed`` vs ``unprocessable_value``）。裁定是归**类 4**
      （更一般的那一档，而枚举校验器本来就先响），故它们不在类 2 里；
    * **认领了一格不存在的列** → 红（``_SERVER_OWNED`` 里写错一个列名不会静默）。

    ⚠️ **反空转**：末拍断言扫描面本身不小（全库实测 **68** 格，下界取 60），
    否则「``Base.metadata`` 是空的」与「全库都分类好了」在断言上不可分辨。
    """
    every = _every_string_column()
    metadata = {(t, c) for t, c, _ in _REQUEST_METADATA}
    domain = {(t, c) for t, c, _ in _DOMAIN_BOUNDED}
    identity = {(t, c) for t, c, _, _ in _IDENTITY_DERIVED}
    body = _body_columns()
    owned = _server_owned_columns()

    classes = {
        "_REQUEST_METADATA": metadata,
        "_DOMAIN_BOUNDED": domain,
        "_IDENTITY_DERIVED": identity,
        "_BODY_REJECTED": body,
        "_SERVER_OWNED": owned,
    }
    for first, second in [
        (a, b) for i, a in enumerate(sorted(classes)) for b in sorted(classes)[i + 1:]
    ]:
        assert not (classes[first] & classes[second]), (
            f"{first} 与 {second} 都认领了 {sorted(classes[first] & classes[second])}"
            "：一格只能有一个处置（两类的处置不同、422 的 code 也不同）"
        )
    union = metadata | domain | identity | body | owned
    assert union <= every, f"认领了不存在的列：{sorted(union - every)}"
    assert union == every, (
        f"没人认领的列：{sorted(every - union)}"
        "。加一列 String(n) 就必须回答『它的值从哪来、由谁收口』"
    )
    assert len(every) >= 60, f"只扫到 {len(every)} 格 String(n)（本机实测 68）"


# ==========================================================================
# ② 类 2：取值域有限的那几格，域内最长值 ≤ 声明宽度
# ==========================================================================
def test_the_domain_bounded_columns_fit_their_declared_width():
    """**域内最长的那个值**必须装得下它那一列（域与宽度**都从模型读**）。

    ⚠️ 派单要求这一类**不截断**（「``method`` / ``subject_kind`` 那一类取值域有限的：
    不要截断，校验 + 拒绝或落哨兵」），并要求先实测它们今天的写入路径有没有校验。
    实测结果逐格写在 :data:`_DOMAIN_BOUNDED` 的注释里：``method`` 有
    :func:`app.api.audit.should_record` 那道闸门，``subject_kind`` /两个 ``kind`` /
    两个 ``role`` 有 DB 层的 ``ck_*`` CHECK，``feeling`` 有
    :func:`app.api.schemas._base.one_of` 的 422。
    ⚠️ 于是本条守的是**它们共同的前提**：那个域装得下那一列。
    域加一个更长的值、或那一列被改窄，都会让本条红。
    """
    for table_name, column_name, domain in _DOMAIN_BOUNDED:
        assert domain, f"{table_name}.{column_name} 的取值域是空的"
        longest = max(len(value) for value in domain)
        declared = _declared(table_name, column_name)
        assert longest <= declared, (
            f"{table_name}.{column_name} 声明 {declared}，"
            f"而它的取值域里最长的是 {longest} 个字符（{sorted(domain)}）"
        )


# ==========================================================================
# ③ 类 3：身份派生的那一格 ≥ 它来源的那一格
# ==========================================================================
def test_the_identity_derived_column_is_at_least_as_wide_as_its_source():
    """``mini_test.entered_by`` 必须装得下它**唯一**的来源（``teacher.staff_no``）。

    ⚠️ 两侧都从模型读，故「把名册那一列加宽」会让本条当场红 ——
    而那正是 :class:`app.db.models.auth.LoginAttempt.login` 在 Plan 06 Task 11
    踩过的同一格（它当时声明 32、而实际写进去的是 ``前缀 + 名册原文`` = 37）。
    ⚠️ 本列**不加前缀**，故两格今天逐字同宽（32 == 32）。
    """
    for table_name, column_name, source_table, source_column in _IDENTITY_DERIVED:
        assert _declared(table_name, column_name) >= _declared(
            source_table, source_column
        ), (
            f"{table_name}.{column_name} 比它唯一的来源 "
            f"{source_table}.{source_column} 窄：一个在册的工号会装不进去"
        )


# ==========================================================================
# ④ 收口点本身：截断与哨兵**恒不超过声明宽度**，且截断**恒留标记**
# ==========================================================================
def test_the_truncation_owner_never_widens_and_never_cuts_silently():
    """:func:`app.db.width.truncate` 的两条性质，**遍历全部真实列宽**量。

    ① **恒不超宽**：对全库每一个出现过的声明宽度 × 每一个「宽度 ± 1、宽度 × 2、
       500」的原文长度，返回值长度 ≤ 宽度；
    ② **恒留标记**（派单逐字要求「不许静默截断」）：只要真的截了，
       返回值就**以 :data:`app.db.width.OVERLONG_SUFFIX` 结尾**，
       且**前 ``width - len(标记)`` 个字符与原文逐字相同**（保住的是前缀，
       逐字理由见 :func:`app.db.width.truncate`）；
    ③ **不超宽时逐字原样**（反空转：否则「把每个值都换成标记」也会绿）；
    ④ ``None`` 原样返回（``NULL`` 不是「长度为 0 的串」）。

    ⚠️ 期望侧的宽度来自 :func:`app.db.width.declared_width`（**全库真实出现过的
    那些数**），不是一个手写的清单 —— 于是「有人建了一个 ``String(7)`` 的列」
    会自动进本条的扫描面。
    """
    widths = sorted(
        {
            width.declared_width(column)
            for table in Base.metadata.tables.values()
            for column in table.columns
            if width.declared_width(column) is not None
        }
    )
    assert widths, "全库一格 String(n) 都没扫到"
    suffix = width.OVERLONG_SUFFIX
    for declared in widths:
        for length in {declared - 1, declared, declared + 1, declared * 2, 500}:
            if length < 0:
                continue
            original = "x" * length
            got = width.truncate(original, declared)
            assert got is not None and len(got) <= declared, (
                f"宽度 {declared} × 原文 {length} → {len(got or '')} 个字符"
            )
            if length <= declared:
                assert got == original, (
                    f"原文 {length} 装得下宽度 {declared}，却被改成了 {got!r}"
                )
            else:
                assert got.endswith(suffix), (
                    f"宽度 {declared} × 原文 {length} 截完是 {got!r}："
                    f"没有以 {suffix!r} 结尾 = **静默截断**"
                )
                assert got.startswith(original[: declared - len(suffix)]), (
                    f"宽度 {declared} 截完保住的不是原文的前缀：{got!r}"
                )
                assert len(got) == declared, (
                    f"截完应当**恰好**占满声明宽度（{declared}），实得 {len(got)}"
                )
    assert width.truncate(None, 32) is None
    assert width.truncate("x" * 99, None) == "x" * 99, "无界列（Text）不该被动过"


def test_the_sentinel_owner_never_widens_and_never_looks_like_a_real_value():
    """:func:`app.db.width.overlong_sentinel`：超宽 → 哨兵，且**保住原文长度**那一格。

    ⚠️ 派单点名了 ``ip`` 这一格（「截一个 IP 会得到一个假 IP」），实现者把同一档
    推到了 ``audit_log.staff_no``（截一个工号会得到一个**假工号**，而那一格的全部用途
    是**指认一个人**）。⚠️ 于是哨兵的形状是 ``<over:原文长度>``：

    * ``<`` / ``>`` 不在 IP 的文本形式里、也不在本仓的工号/学号形状里
      ⇒ 它不可能被误读成一个真值；
    * ⚠️ 它**保住了长度**：「有人送了 400 字符」与「有人送了 4 000 字符」是不同的
      探测强度，固定哨兵会把这一格抹平；
    * ⚠️ 它**恒不超过声明宽度**（装不下就退化成 ``<over>``，再装不下就按宽度切）。
    """
    widths = sorted(
        {
            width.declared_width(column)
            for table in Base.metadata.tables.values()
            for column in table.columns
            if width.declared_width(column) is not None
        }
    )
    for declared in widths:
        for length in {declared + 1, declared * 3, 500, 4000}:
            got = width.overlong_sentinel("y" * length, declared)
            assert got is not None and len(got) <= declared, (
                f"宽度 {declared} × 原文 {length} → {len(got or '')} 个字符"
            )
            assert got.startswith("<over"), f"哨兵换了形状：{got!r}"
            assert "y" not in got, f"哨兵里混进了原文的字符：{got!r}"
        assert width.overlong_sentinel("y" * declared, declared) == "y" * declared
    # ⚠️ 长度那一格是**读的出来的**（这是它比固定哨兵好的地方）。
    got = width.overlong_sentinel("y" * 400, 32)
    assert "400" in got, got
    assert width.overlong_sentinel(None, 32) is None
    assert width.overlong_sentinel("y" * 99, None) == "y" * 99


# ==========================================================================
# ⑤ 类 4：可写资源的每一格请求体字段，超宽一律被拒（红绿两档都在场）
# ==========================================================================
def test_every_body_field_of_a_writable_resource_is_rejected_when_it_is_too_wide():
    """**逐格**驱动 :func:`app.db.width.ensure_fits`：宽一格就拒、恰好装满就放。

    ⚠️ 类 4 的清单是**推出来的**（:func:`_body_columns`：``RESOURCES`` 里
    ``writable=True`` 的那些表 × 它们 Create/Update schema 上真实存在的字符串列），
    故加一个可写资源会自动进本条。⚠️ 本机实测 **15** 格（9 个可写资源）。

    ⚠️ **红绿两档都在场**（硬规矩 #50）：``声明宽度 + 1`` 必须抛、
    ``声明宽度`` 必须不抛。少了后者的话，「把 :func:`app.db.width.ensure_fits`
    改成无条件抛」也会绿 —— 而那会让 9 个资源的 POST 全灭。

    ⚠️ 报错文本里点名了**列名与声明宽度**（前端表单要标红的那一格），
    故本条也断言它出现在消息里。
    """
    body = _body_columns()
    assert len(body) >= 10, f"只推出 {len(body)} 格请求体字段（本机实测 15）"
    for table_name, column_name in sorted(body):
        table = Base.metadata.tables[table_name]
        declared = _declared(table_name, column_name)
        width.ensure_fits(table, {column_name: "z" * declared})
        with pytest.raises(ValueError) as caught:
            width.ensure_fits(table, {column_name: "z" * (declared + 1)})
        assert column_name in str(caught.value), str(caught.value)
        assert str(declared) in str(caught.value), str(caught.value)
        # ⚠️ 非字符串值与不是列名的键一律放过（JsonText / 数值 / 日期列不归本条）。
        width.ensure_fits(table, {column_name: None, "不是列名": "z" * 9999})


# ==========================================================================
# ⑥ 端到端：真发超宽的请求，再真读库量（运行时口径，硬规矩 #89）
# ==========================================================================
ADMIN = {"X-Teacher-Staff-No": "T0003"}
OVERLONG = 400


def _seed_an_admin(engine) -> None:
    with Session(engine) as session:
        session.add(Teacher(staff_no="T0003", name="教务干事", role="admin"))
        session.add(
            Student(
                student_no="2023120001",
                name="张三",
                sex=sorted(Student.SEXES)[0],
                birth=dt.date(2005, 3, 4),
                grade=2023,
            )
        )
        session.commit()


def _fire_the_overlong_volley(client) -> dict[str, int]:
    """把五格客户端可控的列**逐个**灌一次超宽原文，回每一档的业务响应码。

    ⚠️ 派单 §1 第 4 条要求的第一格取证是「**业务响应码不受影响**」，
    故本函数把每一档的码原样交出来给调用方断言（而不是在这里断言死）。
    """
    codes: dict[str, int] = {}
    codes["path"] = client.post("/" + "a" * OVERLONG).status_code
    codes["target"] = client.patch(
        "/api/students/" + "b" * OVERLONG, json={}, headers=ADMIN
    ).status_code
    codes["staff_no"] = client.patch(
        "/api/students/1", json={}, headers={"X-Teacher-Staff-No": "c" * OVERLONG}
    ).status_code
    codes["login"] = client.post(
        "/api/auth/students/bind",
        json={
            "student_no": "e" * OVERLONG,
            "birth": "2005-03-04",
            "password": "pe-demo-2025",
        },
    ).status_code
    codes["user_agent"] = client.post(
        "/api/auth/login",
        json={"kind": "student", "login": "2023120001", "password": "wrong-pass"},
        headers={"User-Agent": "U" * 2000},
    ).status_code
    return codes


def test_an_overlong_volley_leaves_every_row_bounded_and_every_response_unchanged(
    client, engine
):
    """**四格取证**（派单 §1 第 4 条逐条）：① 码不变 ② 行还在 ③ 有界且带标记 ④ 读得回来。

    ⚠️ 这一条是本文件的**主取证**：它真发五条超宽请求（含一条 2 000 字符的
    ``User-Agent``），然后逐格量落库长度、逐格认标记。

    ------------------------------------------------------------------------
    ① 业务响应码**不受影响**
    ------------------------------------------------------------------------
    五档的码逐字是改前实测的那五个（404 / 422 / 403 / 403 / 403）。
    ⚠️ 它们的**含义**一律与「宽度」无关：404 是「没有这个路径」、422 是
    ``pk_value: int`` 校验不过、三个 403 分别是「不在册的教职」/「绑定材料不符或不在册」
    /「未绑定口令」。⚠️ 于是本波**没有新增任何一个可区分的码**
    （与 Task 3 对 423/429 的改判同一条理由：新码就是枚举信号）。

    ------------------------------------------------------------------------
    ② 审计行**存在**（不是被静默丢弃）
    ------------------------------------------------------------------------
    ⚠️ 这一格是本件最要命的失效方向：:class:`app.api.audit.AuditMiddleware`
    **刻意吞掉** ``record`` 的异常（Task 5/6 的裁定：审计写失败不许让业务写看起来失败），
    故在 PostgreSQL 上一次超宽写入的表现**不是** 500、而是**那一行审计消失**。
    本条断言五条超宽请求产生了**五行**审计（⚠️ 两个 ``bind`` / ``login`` 也是 POST，
    故也记；只有 ``method`` 那一档刻意不产生行，
    见 :func:`test_an_arbitrary_method_token_never_reaches_the_method_column`）。

    ------------------------------------------------------------------------
    ③ 有界 + **带标记**
    ------------------------------------------------------------------------
    ``path`` / ``target`` / ``login`` 三格以 :data:`app.db.width.OVERLONG_SUFFIX`
    结尾且长度**恰好等于**声明宽度；``staff_no`` 落的是哨兵（``<over:400>``，
    保住原文长度那一格）。⚠️ 期望侧的宽度一律从模型读。

    ------------------------------------------------------------------------
    ④ ``GET /api/audit-logs`` **读得回来**
    ------------------------------------------------------------------------
    管理员用同一个身份读那一页，断言被截过的那一行**在响应体里**、
    且它的 ``path`` 逐字等于库里那一格（= 读路径没有第二次加工它）。
    ⚠️ 前端那一侧「超长值不溢出、不重叠」由 ``frontend/tests/smoke.mjs`` 的
    DOM 守卫钉住（16 条路由），本条只管**读得回来**。
    """
    _seed_an_admin(engine)
    codes = _fire_the_overlong_volley(client)
    assert codes == {
        "path": 404,
        "target": 422,
        "staff_no": 403,
        "login": 403,
        "user_agent": 403,
    }, codes

    with Session(engine) as session:
        rows = session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        attempts = session.scalars(select(LoginAttempt).order_by(LoginAttempt.id)).all()

    # ② 五条超宽请求 → 五行审计（⚠️ 两个 ``bind`` / ``login`` 也是 POST，故也记；
    #    只有 ``method`` 那一档刻意不产生行，见下面那一条测试）
    assert len(rows) == 5, [(r.method, r.status, r.path[:40]) for r in rows]
    path_row, target_row, staff_row = rows[0], rows[1], rows[2]

    suffix = width.OVERLONG_SUFFIX
    declared_path = _declared("audit_log", "path")
    declared_target = _declared("audit_log", "target")
    declared_staff = _declared("audit_log", "staff_no")
    declared_login = _declared("login_attempt", "login")

    # ③ path：两行都超宽（第二条请求的路径本身也超宽），一律截断 + 标记
    for row in (path_row, target_row):
        assert len(row.path) == declared_path, len(row.path)
        assert row.path.endswith(suffix), row.path
    assert path_row.path.startswith("/" + "a" * 8), path_row.path

    # ③ target：只有第二条请求有路径参数
    assert path_row.target is None
    assert target_row.target is not None
    assert len(target_row.target) == declared_target, len(target_row.target)
    assert target_row.target.endswith(suffix), target_row.target
    assert target_row.target.startswith("b" * 8), target_row.target

    # ③ staff_no：哨兵，且保住「原文有多长」
    assert path_row.staff_no is None, "匿名档不该有工号"
    assert staff_row.staff_no == f"<over:{OVERLONG}>", staff_row.staff_no
    assert len(staff_row.staff_no) <= declared_staff
    assert "c" not in staff_row.staff_no, "哨兵里不该混进原文"

    # ③ login_attempt.login：截断 + 标记，且**恰好**占满声明宽度
    assert len(attempts) == 1, [a.login for a in attempts]
    assert len(attempts[0].login) == declared_login, len(attempts[0].login)
    assert attempts[0].login.endswith(suffix), attempts[0].login
    assert attempts[0].login.startswith("bind:" + "e" * 8), attempts[0].login
    # ⚠️ ip 那一格：本仓不解析 X-Forwarded-For，故它是套接字对端的地址
    assert attempts[0].ip is not None and len(attempts[0].ip) <= _declared(
        "login_attempt", "ip"
    )

    # ④ 管理员读得回来，且读出来的与库里那一格逐字相同
    page = client.get("/api/audit-logs", headers=ADMIN)
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 5, body["total"]
    by_path = {item["path"]: item for item in body["items"]}
    assert path_row.path in by_path, sorted(by_path)
    assert by_path[path_row.path]["target"] == path_row.target
    assert by_path[target_row.path]["target"] == target_row.target
    assert by_path[staff_row.path]["staff_no"] == staff_row.staff_no


def test_the_whole_schema_holds_no_value_wider_than_its_column_after_the_sweep(
    client, engine
):
    """**汇总那一拍**：一轮超宽齐射之后，全库没有任何一格的实写长度超过它的声明宽度。

    ⚠️ 它与上一条的分工：上一条**逐格**认标记与哨兵（形状对不对），
    本条**逐列扫全库**（有没有漏掉一格）。⚠️ 少了本条，「某个收口点漏接了一格」
    只会在那一格恰好被上面的齐射打到时才红；有了本条，任何一格超宽都红。

    ⚠️ 期望侧从模型读（:func:`width.declared_width`），被测侧是**真的库里的值**。
    """
    _seed_an_admin(engine)
    _fire_the_overlong_volley(client)
    # ⚠️ 再补一发请求体那一档（类 4）：一个 500 字符的学期名。
    body = client.post(
        "/api/semesters",
        json={"name": "s" * 500, "start_date": "2025-09-01", "end_date": "2026-01-31",
              "weeks": 20},
        headers=ADMIN,
    )
    assert body.status_code == 422, body.text
    assert "semester.name" in body.json()["error"]["message"], body.json()

    offenders = []
    with Session(engine) as session:
        for table in Base.metadata.tables.values():
            declared = {
                column.name: width.declared_width(column) for column in table.columns
            }
            for row in session.execute(select(table)).all():
                for index, column in enumerate(table.columns):
                    value = row[index]
                    width_of = declared[column.name]
                    if (
                        isinstance(value, str)
                        and width_of is not None
                        and len(value) > width_of
                    ):
                        offenders.append(
                            (table.name, column.name, width_of, len(value))
                        )
    assert not offenders, offenders


def test_an_overlong_body_field_is_rejected_with_a_422_that_names_the_column(
    client, engine
):
    """类 4 的**端到端**取证：改前 ``POST /api/semesters`` 带一个 500 字符的学期名是
    **201**（实测落库 500 个字符、声明 ``String(32)``），改后是 **422**。

    ⚠️ 它同时钉住三格：① 码是 422 而不是 409（``ValueError`` →
    ``unprocessable_value`` 那一条既有链，与
    :func:`app.api.schemas._base.one_of` 同一条）；② ``message`` 里点名了
    ``semester.name`` 与那一格的声明宽度（前端表单要标红的那一格）；
    ③ **库里一行都没多**（拒绝不是「先写再改」）。

    ⚠️ ``PATCH`` 那一档也钉：它走的是 :func:`app.api.crud.build_crud_router` 里
    **另一个**端点（``update_row``），两处漏接任何一处都会让对应的那一拍红。
    """
    _seed_an_admin(engine)
    declared = _declared("semester", "name")
    created = client.post(
        "/api/semesters",
        json={
            "name": "n" * (declared + 1),
            "start_date": "2025-09-01",
            "end_date": "2026-01-31",
            "weeks": 20,
        },
        headers=ADMIN,
    )
    assert created.status_code == 422, created.text
    payload = created.json()["error"]
    assert payload["code"] == "unprocessable_value", payload
    assert "semester.name" in payload["message"], payload
    assert str(declared) in payload["message"], payload

    ok = client.post(
        "/api/semesters",
        json={"name": "2025-2026 学年第一学期", "start_date": "2025-09-01",
              "end_date": "2026-01-31", "weeks": 20},
        headers=ADMIN,
    )
    assert ok.status_code == 201, ok.text
    row_id = ok.json()["id"]

    patched = client.patch(
        f"/api/semesters/{row_id}",
        json={"name": "n" * (declared + 1)},
        headers=ADMIN,
    )
    assert patched.status_code == 422, patched.text
    assert "semester.name" in patched.json()["error"]["message"]

    with Session(engine) as session:
        stored = session.scalars(select(Base.metadata.tables["semester"].c.name)).all()
    assert stored == ["2025-2026 学年第一学期"], stored


def test_an_arbitrary_method_token_never_reaches_the_method_column(client, engine):
    """``audit_log.method`` 那一格**不设防**是有据的：闸门在它前面。

    ⚠️ 派单要求「``method`` / ``subject_kind`` 那一类取值域有限的：不要截断，
    **校验 + 拒绝**（先实测它们今天的写入路径有没有校验）」。实测：
    一个 **400 字符**的方法令牌打过来得到 **405**，而审计行**一行都不多** ——
    因为 :func:`app.api.audit.should_record` 只在
    ``method.upper() in AUDITED_METHODS`` 时才放行，故 ``record`` 根本不会被调到。

    ⚠️ 于是本列**刻意不截断也不落哨兵**：截一个方法名只会造出一个不存在的方法，
    而「哪些方法被记」的唯一所有者是 :func:`app.api.audit.should_record`
    （:attr:`app.db.models.audit.AuditLog.method` 那一列的注释逐字写了
    为什么本列连 DB 层的 CHECK 都刻意没有）。
    ⚠️ **反空转**：末拍断言 ``POST`` 那一档**确实**产生了一行，
    否则「审计整个坏了」与「闸门挡住了」在断言上不可分辨。
    """
    _seed_an_admin(engine)
    before = client.get("/api/audit-logs", headers=ADMIN).json()["total"]
    response = client.request("Z" * OVERLONG, "/api/students")
    assert response.status_code == 405, response.status_code
    with Session(engine) as session:
        rows = session.scalars(select(AuditLog)).all()
    assert len(rows) == before, [(r.method, r.path) for r in rows]

    client.post("/api/students", json={}, headers=ADMIN)
    with Session(engine) as session:
        methods = [r.method for r in session.scalars(select(AuditLog)).all()]
    assert "POST" in methods, methods
    assert max(len(m) for m in methods) <= _declared("audit_log", "method")


def test_no_user_agent_is_stored_anywhere_and_no_column_was_added_by_this_wave(engine):
    """**隐私纪律**（派单 §1 第 6 条）：本波**没有新增任何一列**，``User-Agent`` 也仍然不存。

    ⚠️ 派单点名要实测的两格：① ``user_agent`` **今天有没有存？声明多宽？**
    实测：**全库 28 张表里没有任何一列的名字含 ``agent``**，而
    ``user_session`` 是 8 列（``id`` / ``kind`` / ``subject_id`` / ``role`` /
    四个时刻）、``login_attempt`` 是 6 列（``id`` / ``kind`` / ``login`` / ``ok`` /
    ``at`` / ``ip``）—— 两张表都**没有** ``ip`` 之外的任何请求元数据列
    （``user_session`` 连 ``ip`` 都没有）。
    ② 于是按控制者的裁定**不加**：把 ``User-Agent`` 纳入审计要先重裁
    「审计不落任何请求体」那一族隐私口径的边界，本波刻意不做，已登记为待清扫。

    ⚠️ **端到端取证**：真发一条带 **2 000 字符** ``User-Agent`` 的登录请求，
    然后把 ``audit_log`` 与 ``login_attempt`` 的**全部列**逐列扫一遍，
    断言那串里的任何一段（探针 ``"U" * 20``）都不出现。
    ⚠️ 它与 ``tests/api/test_audit_api.py`` 那条口令取证守卫是**同一个形状**
    （真发请求 + 全列扫探针），只是探针换成了 UA 的原文。

    ⚠️ 顺带钉住**列数**（本波「不动 schema」的承诺）：三张表仍然是 9 / 6 / 8 列，
    且迁移链因此**仍然是 4**（``tests/db/test_migration_chain.py`` 钉另一侧）。
    """
    assert [
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if "agent" in column.name.lower()
    ] == []
    assert len(AuditLog.__table__.columns) == 9
    assert len(LoginAttempt.__table__.columns) == 6
    assert len(UserSession.__table__.columns) == 8
    assert len(Base.metadata.tables) == 28


def test_a_two_thousand_character_user_agent_leaves_no_trace_in_any_column(
    client, engine
):
    """:func:`test_no_user_agent_is_stored_anywhere_and_no_column_was_added_by_this_wave`
    的**运行时**那一半：真发一条超长 UA 的请求，再扫两张表的**全部列**。
    """
    _seed_an_admin(engine)
    probe = "U" * 20
    response = client.post(
        "/api/auth/login",
        json={"kind": "student", "login": "2023120001", "password": "wrong-pass"},
        headers={"User-Agent": "U" * 2000, "Referer": "R" * 2000},
    )
    assert response.status_code == 403, response.text
    with Session(engine) as session:
        scanned = [
            (model.__tablename__, column.name, value)
            for model in (AuditLog, LoginAttempt)
            for row in session.scalars(select(model)).all()
            for column in model.__table__.columns
            for value in [getattr(row, column.name)]
            if isinstance(value, str)
        ]
    assert scanned, "两张表一行都没有，扫了个空（反空转）"
    hits = [
        (table, column, len(value))
        for table, column, value in scanned
        if probe in value or "R" * 20 in value
    ]
    assert hits == [], hits


def test_a_legitimate_rate_limit_key_is_byte_for_byte_untouched_by_the_bound():
    """**反空转 / 回归**：一个**合法**的限流键逐字不变（截断只碰超宽的那些）。

    ⚠️ 本条是 :func:`app.auth.policy._key` 那一格收口的**另一半**：
    上一条钉「超宽的进不去」，本条钉「合法的没被改动」。⚠️ 少了本条，
    「把 :func:`app.auth.policy._key` 改成无条件截到 8 个字符」也会绿 ——
    而那会让**全部**限流键撞成同一个（``bind:20`` 与 ``bind:2023120001`` 同串），
    于是「猜错三次绑定材料」把那个人的**登录**也锁掉 = 把限流变成拒绝服务，
    正是 Plan 06 Task 10 花一整节散文要防的失效。

    ⚠️ 期望侧的「最长合法原文」从**名册那两列的声明宽度**推出来
    （与 ``tests/auth/test_policy.py`` 的
    ``test_the_login_column_is_at_least_as_wide_as_the_longest_key_the_policy_writes``
    同一条口径），本条不写长度数字。
    """
    roster = max(
        _declared("student", "student_no"), _declared("teacher", "staff_no")
    )
    longest = "X" * roster
    for purpose in sorted(policy.PURPOSES):
        assert policy._key(purpose, longest) == longest or policy._key(
            purpose, longest
        ).endswith(longest), (
            f"{purpose} 那一档的合法键被改动了：{policy._key(purpose, longest)!r}"
        )
        assert not policy._key(purpose, longest).endswith(width.OVERLONG_SUFFIX)
    # ⚠️ 而超宽的那一档**确实**被收了（否则本条与上一条一起绿在一个没接线的收口点上）
    over = policy._key(policy.PURPOSE_BIND, "X" * (roster * 20))
    assert len(over) == _declared("login_attempt", "login"), len(over)
    assert over.endswith(width.OVERLONG_SUFFIX), over
