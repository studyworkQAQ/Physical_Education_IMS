"""spec §4.4 处方数据模型（Plan 02 逐 Task 往这里加表，**四个 Task 四张表**）。

计划完成后的状态是 **18 张表** = Plan 01 的 14 张 + 本小节的 4 张（计划
``Document/2026-10-06-实施计划02-智能处方引擎.md`` ``:700``，行号取 shell 口径、绑定
commit ``fb5bddb``）：

========================  =========  =========================================
表                         归属 Task   备注
========================  =========  =========================================
``exercise``              **Task 2**  **已建**
``prescription_template``  **Task 3**  **已建**：18 套模板的索引行，YAML 在 ``data/prescription/``
``prescription``           Task 9     计划 ``:524`` 的 Files 段明写「Modify 本文件（加两张表）」
``weekly_adjustment``      Task 9     同上
========================  =========  =========================================

**逐 Task 递增、不得一次性把四张都建出来**：
``tests/db/test_models.py::test_all_sixteen_tables_created`` 用 ``==`` 钉住表集合
（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把后续 Task 的表建进来」
——那种提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感）。故 Task 9 加自己那
两张时，**必须同步改那道守卫的期望集合、``== 16`` 的三处断言与函数名里的「sixteen」**，
以及本文件上面那张表。⚠️ **按可 grep 的原文找，不要按裸行号找**
（fix round 3 更正：此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的
位置；Task 2 把它们改成 ``== 15`` 时那三处就已推移，而本句没跟上——与 fr2 的 CE-7 是
同一个失效形态，故本轮按 fr2 对 CE-7 的修法处理：先给可 grep 的原文，再给绑 commit 的
行号。那三个过期裸行号本轮**不再复述**，免得下一次 grep 又把它们当成有效位置。
⚠️ **Task 3 又踩了同一个坑**：控制者派单的自查清单里印的仍是 ``966eae0`` 上的
``:169`` / ``:236`` / ``:494``，而在代码基线 ``c29bc69`` 上实测已推移到
``:176`` / ``:243`` / ``:501``——即「复用历史输出里的行号等同手写」，硬规矩 #61 的扩写。
故下面只给绑 commit 的一组，且**每次改表数都要重跑那两条 grep**）：

* ``git grep -n "== 16" -- backend/tests/db/test_models.py`` 现命中 **6** 处 = **3** 处真断言
  （两处 ``assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"`` 与一处
  ``assert len(Base.metadata.tables) == 16``）+ **3** 处那个文件里的散文（grep 命令自己，
  以及紧随其后逐字引出的那两条断言原文）。**改完表数请重跑这条 grep、按命中数逐个更新，
  并连带更新本文件这一句里的两个数**（硬规矩 #66）；
* 函数名用 ``git grep -n "test_all_sixteen_tables_created" -- backend`` 找（现命中 **5** 处：
  ``tests/db/test_models.py`` 的 ``def`` 行与一处注释引用、``app/db/models/__init__.py`` 一处、
  本文件两处——一处是上面那段正文的引用、一处是本条 grep 命令自己）；
* 若一定要写行号，必须绑 commit：在**代码基线** ``c29bc69`` 上，Task 3 改动之前它们分别是
  ``:176`` / ``:243`` / ``:501``（三处 ``==``）与 ``:24``（``def``）、``:499``（注释引用）。

⚠️ **两处此前印错的说法，本次按硬规矩 #64 与计划逐 Task 交叉核对后更正**（Plan02 账本
P2-A10；这两句熬过了 Task 1 的任务评审 + 5 轮 fix + 收尾评审，因为那六轮的注意力都在
架构守卫与 ``test_models.py`` / ``daily.py`` 的散文上）：

* ``training_package`` **不是表**。它是 ``prescription`` 的一个 ``JsonText`` 列——计划
  ``:568``「断言新处方的 ``training_package`` 等于**无覆盖**的基线」、``:569``「
  ``prescription`` 行数不变、``training_package`` 逐字段相同」都是按**列**在用这个词；
  spec 全文也没有它作为表名的出处（spec §4.4 ``:240`` 那一行写的是「4 周训练包 JSON」）。
* ``prescription_override`` **在计划里没有这张表**。Task 8 的 Files（计划 ``:491``）只建
  ``app/domain/prescription/override.py`` + 它的测试；计划 ``:700`` 的 18 张表清单里没有它。
  教师覆盖记录是 ``prescription`` 的一个 JSON 列（spec §4.4 ``:240``「教师覆盖记录 JSON」），
  因为覆盖是**叠加在训练包上的纯函数**（spec §7.5），不需要自己的表。

``exercise`` 与 ``prescription_template`` 与另外两张表有一处**性质上的不同**，值得写在这里：
它们是本小节仅有的两张**参考数据**表（专家维护的知识资产在 DB 里的**投影**），
``prescription`` 与 ``weekly_adjustment`` 是业务数据。故它们的灌数据函数**都不在**
``app/seed/``——那是仿真人口生成器的住址，且自 Plan 01 结案后重新冻结
（Global Constraint #10）；两者的同类是 ``app/refdata.py``，故灌数据函数是
:func:`app.refdata_prescription.sync_exercises`（Plan02 账本 P2-A1 的裁定）与
:func:`app.refdata_prescription.sync_templates`（Plan02 账本 P3-A1：**同一条裁定传导到
Task 3** ——它在 Task 2 预检时查出来并裁了，却没传导过来，于是 Task 3 的原文里同一个
缺陷原封不动地躺着；这也正是硬规矩 #75 的由来）。
⚠️ Task 2 时这一段印的是「``exercise`` …是本小节**唯一**一张参考数据表」，Task 3 建出
``prescription_template`` 之后那半句已经不成立（硬规矩 #66：一个事实变了要 grep 出全部
同类陈述逐个更新）。
"""

import datetime as dt

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import JsonText, _in_domain


# ---------------------------------------------------------------------------
# spec §4.4 处方：动作库（Task 2）
# ---------------------------------------------------------------------------


class Exercise(Base):
    """一个运动动作。spec §4.4 ``:239`` 的六项与下面六列一一对应。

    | spec §4.4 ``:239`` 原文                | 本表的列          |
    | ====================================== | ================= |
    | id                                     | ``id``            |
    | 动作名                                 | ``name``          |
    | 视频二维码 URL                         | ``video_url``     |
    | **``impact_level``** ∈ {high, medium, low} | ``impact_level`` |
    | 目标素质                               | ``targets``       |
    | 器械需求                               | ``equipment``     |

    另有一列 spec 没点名、但计划 Step 4 要求的 ``ref``：它是 ``exercise_ref`` 的落库形态，
    也是模板 YAML 引用动作时用的键。**``ref`` 而不是 ``id`` 做引用键**，因为 ``id`` 是代理键、
    随建库顺序变；专家在 YAML 里写 ``exercise_ref: interval_run``，那串字符必须在两次
    重建库之间稳定。

    ⚠️ **本表是 ``backend/data/exercises.yaml`` 的投影，不是第二个所有者**：唯一所有者是
    那份 YAML，本表由 :func:`app.refdata_prescription.sync_exercises` 按 ``ref`` 幂等
    upsert 灌进来。故**不要手工往这张表插行**——下一次 sync 不会删掉它（sync 只 upsert
    YAML 里有的 ref），于是它会变成一个没有任何模板能引用、也没有视频源的孤儿行。

    **``impact_level`` 取值域两处设防**（本包的约定 2，见 :mod:`app.db.models`）：
    :attr:`IMPACT_LEVELS` 是唯一真相，SQL CHECK 的文本由 :func:`_in_domain` 从它生成，
    两者不可能各说各话。它与 Python 侧的
    :class:`app.domain.prescription.exercises.ImpactLevel` 是**两份**词表，由
    ``tests/test_refdata_prescription.py::test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum``
    钉住一致；本模块刻意**不 import** domain 来自动生成它——`db` 层反向依赖 `domain`
    的枚举会让「改一个枚举成员」静默改掉 DDL，而 DDL 变更在本仓等于重建库。

    **列宽**（硬规矩 #18）：``String(n)`` 的 ``n`` 必须容得下取值域里最长的值，而 SQLite
    **不强制**长度，故溢出在本仓的测试里永远不报错、换 MySQL / PostgreSQL 才截断，且
    **炸在读侧不在写侧**。逐列的口径（实测值由
    ``tests/test_refdata_prescription.py::test_exercise_string_column_widths_fit_the_yaml_values``
    从 YAML 现读现比，故这里只写「谁是最长者」而不写数字，免得数字与那份 YAML 漂移）：

    * ``ref`` —— 最长者是 ``energy_expenditure_plus_10pct``（spec §7.2 ``:482`` 的 addon
      模块名，本动作库照它命名以免出现第二个所有者）；
    * ``name`` —— 中文动作名，最长者是 ``pnf_stretching`` 的「本体感觉神经肌肉促进拉伸」；
    * ``video_url`` —— ``https://example.invalid/exercise/`` 前缀 + 最长的 ``ref``；
    * ``equipment`` —— 最长者是 ``medicine_ball``。

    ⚠️ **这四列不被 Plan 01 那道列宽遍历测试覆盖**（Plan02 账本 P2-A5）：
    ``tests/db/test_models.py`` 的 ``_in_domain_columns()`` 只反解**带 ``_in_domain``
    CHECK** 的列，而 ``ref`` / ``name`` / ``video_url`` / ``equipment`` 的取值域不是封闭
    集合、没有 CHECK。本表 5 个 ``String(n)`` 列里只有 ``impact_level`` 会被那道测试扫到。

    ``targets`` 用 :class:`JsonText` 存**排序后的桶名列表**（``["endurance", "strength"]``）：
    桶名来自 :data:`app.domain.indicators.ITEM_BUCKET` 的三个值，排序让落库字节与遍历序
    无关（``frozenset`` 不能直接 JSON 序列化，且它的迭代序跨进程不稳定）。
    """

    __tablename__ = "exercise"

    #: spec §4.4 ``:239`` 的取值域。**与 Python 侧 ``ImpactLevel`` 是两份、由测试钉住一致**。
    IMPACT_LEVELS: set[str] = {"high", "medium", "low"}

    id: Mapped[int] = mapped_column(primary_key=True)
    #: ``exercise_ref``。模板 YAML 与 ``exercise_equivalence.yaml`` 都按它引用动作。
    ref: Mapped[str] = mapped_column(String(48), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    #: 视频二维码 URL。本批一律是 RFC 2606 占位符 ``https://example.invalid/exercise/<ref>``
    #: （``.invalid`` 是保留 TLD、DNS 保证不可解析），真实视频源待项目组提供——见
    #: ``backend/data/exercises.yaml`` 的头注释与 spec §14。
    video_url: Mapped[str] = mapped_column(String(256))
    impact_level: Mapped[str] = mapped_column(String(8))
    #: 该动作瞄准的素质桶名列表，取值域 =
    #: ``frozenset(v for v in ITEM_BUCKET.values() if v is not None)``（三个桶名；
    #: ⚠️ 不是 ``set(ITEM_BUCKET.values())``，那个集合含 ``None``，Plan02 账本 P2-A4）。
    targets: Mapped[list] = mapped_column(JsonText)
    equipment: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        _in_domain("impact_level", IMPACT_LEVELS, "ck_exercise_impact_level"),
    )


# ---------------------------------------------------------------------------
# spec §4.4 处方：18 套模板的索引行（Task 3）
# ---------------------------------------------------------------------------


class PrescriptionTemplate(Base):
    """一套处方模板在 DB 里的**索引行**。spec §4.4 ``:238`` 的九项与下面十列一一对应。

    | spec §4.4 ``:238`` 原文                            | 本表的列            |
    | ================================================== | =================== |
    | id                                                 | ``id``              |
    | 层                                                 | ``layer``           |
    | 主导短板                                           | ``weakness``        |
    | 体成分（共 18 行）                                 | ``body_comp``       |
    | **YAML 路径**                                      | ``template_ref``    |
    | 版本                                               | ``version``         |
    | ``review.status`` ∈ {``pending``, ``approved``}    | ``review_status``   |
    | 审校人                                             | ``reviewer``        |
    | 审校时间                                           | ``reviewed_at``     |

    另有一列 spec §4.4 **没有**、依据在 §7.1 的 ``reachable``（见下面那一列的注释）。

    ⚠️ **``template_ref`` 是逻辑 id 而不是文件路径**（计划 Task 3 Step 6 的决定）：spec §4.4
    那一格写的是「YAML 路径」，而路径会随目录结构变（``data/prescription/`` 改名、按层分子
    目录都会让它变），``template_id`` 则是 YAML **内容**的一部分、已被
    ``tests/domain/test_prescription_templates.py`` 的逐个文件指纹钉住。故这里存内容里的
    那个 id，文件名与它同名的约定由
    :func:`tests.domain.test_prescription_templates.test_every_template_id_matches_its_filename`
    守。这一处偏离已在 spec §7.2 的勘误里交代（计划 Task 12 Step 3 还另有一条 §4.4 勘误）。

    ⚠️ **本表是 ``backend/data/prescription/*.yaml`` 那 18 份文件的投影，不是第二个所有者**
    （与 ``exercise`` 同一条纪律）：唯一所有者是那 18 份 YAML，本表由
    :func:`app.refdata_prescription.sync_templates` 按 ``template_ref`` 幂等 upsert 灌进来。
    故**不要手工往这张表插行**——下一次 sync 不会删掉它，于是它会变成一个没有任何 YAML
    与之对应的孤儿行，而 Task 4 的匹配器是从**内存里的 YAML** 取模板的、不查本表，
    孤儿行既不会被匹配到、也不会被清掉。
    ⚠️ **本表今天没有任何生产读侧**（硬规矩 #39）：Task 4 的匹配器读的是
    :func:`app.refdata_prescription.templates`（内存单例），Task 9 的 ``prescription`` 表
    才会按 ``template_ref`` 引它。故本表今天的角色是**可追溯性的落库面**（spec §1.3：
    「这套处方当时是按哪一版、谁审校的哪一套模板生成的」要能在库里查到），不是查询入口。

    **四个取值域两处设防**（本包的约定 2，见 :mod:`app.db.models`）：四个类常量是唯一真相，
    SQL CHECK 的文本由 :func:`_in_domain` 从它们生成，两者不可能各说各话。它们与 Python 侧
    :mod:`app.domain.prescription.templates` 的枚举/词表是**两份**，由
    ``tests/test_refdata_prescription.py::test_prescription_template_vocabulary_agrees_with_the_domain_enums``
    钉住一致；本模块刻意**不 import** domain（理由与 ``Exercise.IMPACT_LEVELS`` 那条注释相同）。

    ⚠️ ``LAYERS`` 对的是 domain 侧的 ``TEMPLATE_LAYERS``（**三个**），不是 ``Layer`` 枚举
    （**四个**）——差集是 ``insufficient_data``，它是 spec §6.1 Z0 闸门的产物（``valid_count
    < 4`` 时不产出分层标签），**不是**合法模板层。少了这道 CHECK，一行
    ``layer = 'insufficient_data'`` 的模板会被 DB 照收，而 Task 4 的匹配器永远不查它。

    **列宽**（硬规矩 #18）：``String(n)`` 的 ``n`` 必须容得下取值域里最长的值，而 SQLite
    **不强制**长度，故溢出在本仓的测试里永远不报错、换 MySQL / PostgreSQL 才截断，且
    **炸在读侧不在写侧**。逐列的口径：

    * ``layer`` —— 最长者 ``"yellow"``（6），声明 ``String(8)``，余量 2；
    * ``weakness`` —— 最长者 ``"speed_flexibility"``（**17**），声明 ``String(20)``，余量 3；
    * ``body_comp`` —— 最长者 ``"abnormal"``（**8**），声明 ``String(8)``，⚠️ **零余量**；
    * ``review_status`` —— 最长者 ``"approved"``（**8**），声明 ``String(8)``，⚠️ **零余量**；
    * ``version`` —— 今天是 ``"1.0"``（3），声明 ``String(8)``，余量 5；
    * ``template_ref`` —— 今天是 ``"RED-END-ABN-01"`` 一类（**14**，spec §7.2 ``:454`` 的
      ``<层3>-<桶3>-<体成分3>-<序号2>`` 格式），声明 ``String(32)``，余量 18；
    * ``reviewer`` —— 今天是 ``"原型自审（占位）"``（8），声明 ``String(64)``，余量 56
      （真实审校后要写人名，甚至「体育教研室 2026 春 复核」一类的短语）。

    ⚠️ **两个零余量的列**：将来往 ``BodyCompState`` 或 ``ReviewStatus`` 里加一个更长的值
    （例如 ``"conditionally_approved"``），本仓的 SQLite 会**静默收下**、换严格后端才截断，
    且截断后的值读回来会让 ``ReviewStatus(...)`` 当场 ``ValueError``——炸在读侧、离真因隔
    一整个批处理周期。**这两列由 ``tests/db/test_models.py`` 的
    ``test_string_column_widths_fit_their_value_domains`` 自动覆盖**（它们带 ``_in_domain``
    CHECK，那道遍历测试反解得出取值域）；而 ``template_ref`` / ``version`` / ``reviewer``
    **没有封闭取值域、没有 CHECK → 完全不被它覆盖**（Plan02 账本 P3-A5，与 Task 2 的
    P2-A5 同型），故那三列的列宽断言另住在
    ``tests/domain/test_prescription_templates.py::test_template_string_column_widths_fit_the_yaml_values``
    （实际侧从 18 份 YAML 现读）。

    ``reviewer`` / ``reviewed_at`` 是 **nullable** 的：spec §7.2 骨架 ``:462-463`` 的字面形状
    就是 ``reviewer: null`` / ``reviewed_at: null``，而 ``review.status: pending`` 的模板
    天然还没有审校人与审校时间。⚠️ 今天 18 行**都非空**（用户已裁定原型阶段全部标
    ``approved`` + 占位审校人），故这两列的 NULL 分支在生产数据上不可达；它的可达路径是
    spec §14 第 **29** 项落地之后（专家把某一套打回 ``pending``）。
    """

    __tablename__ = "prescription_template"

    #: 合法的**模板层**：三个。⚠️ 不是 ``Layer`` 的四个成员——``insufficient_data`` 被排除，
    #: 与 domain 侧 ``app.domain.prescription.templates.TEMPLATE_LAYERS`` 逐字一致（两份、
    #: 由测试钉住）。
    LAYERS: set[str] = {"red", "yellow", "green"}
    #: 三个主导短板桶，与 ``WeaknessBucket`` 逐字一致。⚠️ **``bmi`` 不在里面**（Plan02 账本
    #: P2-A4：``ITEM_BUCKET[ScoredItem.BMI] is None``，BMI 属身体形态、已由体成分维度 ``C``
    #: 覆盖，故不入桶；出处是 spec §4.2 的「短板判定项 = 6 个（**排除 BMI**）」）。
    WEAKNESSES: set[str] = {"endurance", "strength", "speed_flexibility"}
    #: 体成分两档，与 ``BodyCompState`` 逐字一致。⚠️ ``"abnormal"`` 是 8 字符、**恰好塞满**
    #: ``String(8)``，零余量。
    BODY_COMPS: set[str] = {"normal", "abnormal"}
    #: 审校状态两档，spec §4.4 ``:238`` 逐字。⚠️ ``"approved"`` 是 8 字符、**恰好塞满**
    #: ``String(8)``，零余量。
    REVIEW_STATUSES: set[str] = {"pending", "approved"}

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 层。取值域见 :attr:`LAYERS`（**不含** ``insufficient_data``）。
    layer: Mapped[str] = mapped_column(String(8))
    #: 主导短板桶。最长值 ``"speed_flexibility"`` 是 17 字符，故 ``String(20)``。
    weakness: Mapped[str] = mapped_column(String(20))
    #: 体成分档位。⚠️ 零余量，见 :attr:`BODY_COMPS` 的注释。
    body_comp: Mapped[str] = mapped_column(String(8))
    #: YAML 里的 ``template_id``（spec §7.2 ``:454`` 的 ``RED-END-ABN-01`` 格式，14 字符）。
    #: ``sync_templates`` 的幂等键，也是 Task 9 的 ``prescription.template_id`` 要引的那一串，
    #: 故唯一。⚠️ 存**逻辑 id 而不是文件路径**，理由见本类 docstring。
    template_ref: Mapped[str] = mapped_column(String(32), unique=True)
    #: 模板版本号（YAML 里的 ``version``）。``exercise_equivalence.yaml`` 的 ``version`` 是
    #: 同一类东西：一张已生成的处方要能回答「当时是按哪一版模板生成的」（spec §1.3 可追溯性）。
    version: Mapped[str] = mapped_column(String(8))
    #: ``review.status``。⚠️ 零余量，见 :attr:`REVIEW_STATUSES` 的注释。
    review_status: Mapped[str] = mapped_column(String(8))
    #: 审校人。nullable：``pending`` 的模板还没有审校人（spec §7.2 骨架 ``:462``）。
    reviewer: Mapped[str | None] = mapped_column(String(64))
    #: 审校时间。nullable 同上（骨架 ``:463``）。⚠️ domain 侧 ``Template.reviewed_at`` 是
    #: **ISO 字符串**（``app/domain/`` 的 allow-list 不放行 ``datetime``），转换发生在
    #: :func:`app.refdata_prescription.sync_templates`。
    reviewed_at: Mapped[dt.date | None] = mapped_column(Date)
    #: 这一格维度组合当前**是否可达**。
    #: ⚠️ **它不在 spec §4.4 ``:238`` 的字段清单里**（Plan02 账本 P3-A10）：依据是 spec §7.1
    #: ``:447``「生成器对这 3 套标记 ``reachable: false``，不参与匹配」。故这是一列**超出
    #: §4.4 的增补**，已在 spec §7.2 的勘误里一并交代，不让它看起来像 §4.4 的原文。
    #: 值的唯一所有者是 :func:`app.domain.prescription.templates.is_reachable`（domain 侧），
    #: 加载器校验 YAML 里写的那一份与它一致。
    reachable: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        _in_domain("layer", LAYERS, "ck_prescription_template_layer"),
        _in_domain("weakness", WEAKNESSES, "ck_prescription_template_weakness"),
        _in_domain("body_comp", BODY_COMPS, "ck_prescription_template_body_comp"),
        _in_domain(
            "review_status", REVIEW_STATUSES, "ck_prescription_template_review_status"
        ),
    )
