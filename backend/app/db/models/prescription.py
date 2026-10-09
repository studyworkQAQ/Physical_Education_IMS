"""spec §4.4 处方数据模型（Plan 02 逐 Task 往这里加表，**四个 Task 四张表**）。

**本小节到 Plan 02 Task 6 为止已经建满，Plan 03 一张都没往这里加**：全库 **25 张表** =
Plan 01 的 14 张 + 本小节的 4 张 + **Plan 03 Task 2 的 7 张**（后者全部住在
:mod:`.feedback`，包括 spec §4.6 的 ``alert`` / ``notification``——理由见那个模块的
docstring）。计划 ``Document/2026-10-06-实施计划02-智能处方引擎.md`` ``:700``
（行号取 shell 口径、绑定 commit ``fb5bddb``）那份「18 张表」清单是 Plan 02 的口径：

========================  =========  =========================================
表                         归属 Task   备注
========================  =========  =========================================
``exercise``              **Task 2**  **已建**
``prescription_template``  **Task 3**  **已建**：18 套模板的索引行，YAML 在 ``data/prescription/``
``prescription``           **Task 6**  **已建**（计划原文按旧编号写作 Task 9，见计划的
                                       「Task 重编号对照表」：原 Task 9 → 新 Task 6）
``weekly_adjustment``      **Task 6**  **已建**，同上；⚠️ Plan 03 Task 2 给它补了一条
                                       ``UniqueConstraint``（裁定 S2：schema 变更一律归
                                       那个计划唯一的建表 Task），见 ``__table_args__``
========================  =========  =========================================

⚠️ **再加表时，下面这套同步动作要重跑一遍**（Task 6 实测：派单给的清单漏了
最后两项，是跑到红才发现的；Plan 03 Task 2 又实测出**两项**派单预检漏掉的——外键总数与
``_in_domain`` 列数，两者都只以散文形式存在，记在
``tests/db/test_models.py::test_all_twenty_five_tables_created`` 那段注释的第 ⑥ 格）：
``tests/db/test_models.py::test_all_twenty_five_tables_created`` 用 ``==`` 钉住表集合
（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把后续 Task 的表建进来」
——那种提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感）。故加表时
**必须同步改那道守卫的期望集合、``== 25`` 的三处断言与函数名里的英文数词**，
以及本文件上面那张表。⚠️ **按可 grep 的原文找，不要按裸行号找**
（fix round 3 更正：此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的
位置；Task 2 把它们改成 ``== 15`` 时那三处就已推移，而本句没跟上——与 fr2 的 CE-7 是
同一个失效形态。⚠️ **Task 3 又踩了同一个坑**：控制者派单的自查清单里印的仍是 ``966eae0``
上的三个位置，而在代码基线 ``c29bc69`` 上实测已推移——即「复用历史输出里的行号等同手写」，
硬规矩 #61 的扩写。故本段**一个裸行号都不给**，只给两条 grep，且**每次改表数都要重跑**）：

* ``git grep -n "== 25" -- backend/tests/db/test_models.py`` 现命中 **7** 处 = **3** 处真断言
  （两处 ``assert len(tables) == 25, "守卫的覆盖面必须先被确认是这 25 张表"`` 与一处
  ``assert len(Base.metadata.tables) == 25``）+ **4** 处那个文件里的散文（grep 命令自己、
  紧随其后逐字引出的那两条断言原文，以及那段注释**第 ④ 格**提到 ``tests/test_main.py``
  那两处的地方）。
  ⚠️ **散文计数在 Plan 03 Task 2 从 3 涨到 4**，涨的就是第 ④ 格那半句——
  加一处引用就要把计数一起改（硬规矩 #66）。**改完表数请重跑这条 grep、按命中数逐个更新，
  并连带更新本文件这一句里的两个数**；
* 函数名用 ``git grep -n "test_all_twenty_five_tables_created" -- backend`` 找（现命中 **11** 处
  / 7 个文件：``tests/db/test_models.py`` 3（``def`` 行与两处注释引用）、
  ``tests/test_main.py`` 1、``tests/api/conftest.py`` 1、``app/db/models/__init__.py`` 1、
  ``app/db/models/feedback.py`` 1、``app/main.py`` 1、本文件 3——上面那段正文的引用、
  第 ⑥ 格那句、以及本条 grep 命令自己。⚠️ **Plan 03 Task 2 把 6 处抬到 11 处**：
  表数这个事实多印一处，本条计数就要跟着改一处，硬规矩 #66）；
* ``git grep -n "json_text_columns" -- backend/tests/db/test_models.py``：加带 ``JsonText``
  的列时要抬 ``assert len(json_text_columns) == 21``，并连带改
  :mod:`._shared` 的 ``JsonText`` docstring 与 :mod:`app.db.models` 的约定 3（三处同一事实）；
* ``git grep -n "_BATCH_OWNED_TABLES" -- backend``：加带 ``batch_id`` 的列
  时要往那份集合里加表名，否则 ``test_only_batch_owned_tables_expose_batch_id`` 按**集合相等**
  判、当场红（它同时断言每一列真的指向 ``daily_sync_run``）。
  ⚠️ **Plan 03 Task 2 实测更正派单预检 P3-A3**：这条 grep 在 ``app/`` 下的**八处**命中
  （本文件三处、``models/feedback.py`` 两处、``models/__init__.py`` 一处、
  ``pipeline/daily.py`` 两处）**全是散文引用**，
  ``_BATCH_OWNED_TABLES`` 的**定义只有 ``tests/db/test_models.py`` 那一份**，
  不存在「生产代码里的常量 + 测试里的镜像」这个形状。要改的是那一份的九个字面量，
  以及这八处散文里「五张」的说法（Plan 03 Task 2 之后是**九张**）。
  ⚠️ 并且**先读 :mod:`.feedback` 的模块 docstring**：「有 ``batch_id``」不等于
  「该进 ``_replay_cleanup``」，``class_session`` 就是反例。

⚠️ **两处此前印错的说法，本次按硬规矩 #64 与计划逐 Task 交叉核对后更正**（Plan02 账本
P2-A10；这两句熬过了 Task 1 的任务评审 + 5 轮 fix + 收尾评审，因为那六轮的注意力都在
架构守卫与 ``test_models.py`` / ``daily.py`` 的散文上）：

* ``training_package`` **不是表**。它是 ``prescription`` 的一个 ``JsonText`` 列——计划
  ``:568``「断言新处方的 ``training_package`` 等于**无覆盖**的基线」、``:569``「
  ``prescription`` 行数不变、``training_package`` 逐字段相同」都是按**列**在用这个词；
  spec 全文也没有它作为表名的出处（spec §4.4 ``:240`` 那一行写的是「4 周训练包 JSON」）。
  ⚠️ Task 6 落地后这一点已由 :class:`Prescription` 的那一列证实。
* ``prescription_override`` **在计划里没有这张表**。Task 8 的 Files（计划 ``:491``）只建
  ``app/domain/prescription/override.py`` + 它的测试；计划 ``:700`` 的 18 张表清单里没有它。
  教师覆盖记录是 ``prescription`` 的一个 JSON 列（spec §4.4 ``:240``「教师覆盖记录 JSON」），
  因为覆盖是**叠加在训练包上的纯函数**（spec §7.5），不需要自己的表。
  ⚠️ Task 6 落地后它就是 :attr:`Prescription.teacher_overrides`。

``exercise`` 与 ``prescription_template`` 与另外两张表有一处**性质上的不同**，值得写在这里：
它们是本小节仅有的两张**参考数据**表（专家维护的知识资产在 DB 里的**投影**），
``prescription`` 与 ``weekly_adjustment`` 是业务数据（Task 6 已把这个判断落进
``tests/seed/test_generate.py`` 的分区：后两张归 ``DATA_TABLES``，前两张留在
``REFERENCE_TABLES``）。故前两张的灌数据函数**都不在**
``app/seed/``——那是仿真人口生成器的住址，且自 Plan 01 结案后重新冻结
（Global Constraint #10）；两者的同类是 ``app/refdata.py``，故灌数据函数是
:func:`app.refdata_prescription.sync_exercises`（Plan02 账本 P2-A1 的裁定）与
:func:`app.refdata_prescription.sync_templates`（Plan02 账本 P3-A1：**同一条裁定传导到
Task 3** ——它在 Task 2 预检时查出来并裁了，却没传导过来，于是 Task 3 的原文里同一个
缺陷原封不动地躺着；这也正是硬规矩 #75 的由来）。
⚠️ 后两张的写入方是 **Task 7** 的 ``app/pipeline/prescription_stage.py``；Task 6 只建表。
⚠️ **Task 7 已落地**（本段随它更新，硬规矩 #66）：``prescription`` 现在由
:func:`app.pipeline.prescription_stage.generate_prescriptions` 写，两张表都进了
``daily._replay_cleanup`` 的按批删清单（顺序承重，P7-A4）；``weekly_adjustment`` 的生产
写入方**仍为零**（``source = "teacher"`` 归 Plan 03 的教师端、``"auto"`` 归 Plan 03 的
预警侧）。``tests/seed/test_generate.py`` 仍要求 **seed 阶段**两张表都是 0 行——
灌参考数据的 :func:`app.refdata_prescription.sync_exercises` / ``sync_templates`` 只写
前两张表，处方是**业务数据**、只由管道按业务日期产出。
⚠️ Task 2 时这一段印的是「``exercise`` …是本小节**唯一**一张参考数据表」，Task 3 建出
``prescription_template`` 之后那半句已经不成立（硬规矩 #66：一个事实变了要 grep 出全部
同类陈述逐个更新）。
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

from ._shared import JsonText, _in_domain
# 值域的**单一所有者**（本包约定 2）：``label_at_generation`` 存的就是
# ``stratification_result.label`` 那一族值，故 CHECK 直接引它的类常量、不在本模块
# 再声明第二份词表。``derived`` 不 import 本模块，无环（``derived`` 自己也是这么
# 引 ``organisation.Student`` 的）。
from .derived import StratificationResult


# ---------------------------------------------------------------------------
# spec §4.4 处方：动作库（Task 2）
# ---------------------------------------------------------------------------


class Exercise(Base):
    """一个运动动作。spec §4.4 ``:239`` 的六项与下面六列一一对应。

    | spec §4.4 ``:239`` 原文                    | 本表的列          |
    | ========================================== | ================= |
    | id                                         | ``id``            |
    | 动作名                                     | ``name``          |
    | 视频二维码 URL                             | ``video_url``     |
    | **``impact_level``** ∈ {high, medium, low} | ``impact_level``  |
    | 目标素质                                   | ``targets``       |
    | 器械需求                                   | ``equipment``     |

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


# ---------------------------------------------------------------------------
# spec §4.4 处方：一张已生成的训练包（Task 6）
# ---------------------------------------------------------------------------


class Prescription(Base):
    """一名学生在某一天生成的一张运动处方。spec §4.4 ``:240`` + **三处预检更正**
    + **fix round 1 的一处追加**（F1-1：``label_at_generation``，控制者错误 #148）。

    | spec §4.4 ``:240`` 原文           | 本表的列                      |
    | ================================= | ============================= |
    | id                                | ``id``                        |
    | 学生                              | ``student_id``                |
    | 生成日期                          | ``generated_on``              |
    | 模板 id                           | ``template_ref`` ⚠️ 见下      |
    | 4 周训练包 JSON                   | ``training_package``          |
    | 装配快照 JSON                     | ``assembly_snapshot``         |
    | 安全替换记录 JSON                 | ``safety_substitutions``      |
    | 教师覆盖记录 JSON                 | ``teacher_overrides``         |
    | 状态                              | ``status``                    |
    | 生效起 / 生效止                   | ``valid_from`` / ``valid_to`` |
    | 触发原因                          | ``trigger_reasons``           |

    另有**四列** spec §4.4 **没有**，逐列的依据写在各自注释里：``microcycle_weeks``（P6-A3）、
    ``previous_had_overrides``（P6-A2）、``label_at_generation``（**Task 7 fix round 1 的
    F1-1**，控制者错误 #148：Task 6 预检时逐个核了 ``microcycle_weeks`` 有没有住址，
    却没把 :class:`~app.domain.prescription.triggers.LastPrescription` 的**五个字段逐个对到
    列上**——四个有列、只有它没有）、``batch_id``（与 Plan 01 三张派生表同构），
    以及 ``(student_id, generated_on)`` 的唯一约束（Review Focus 第 2 条）。

    ⚠️⚠️ **``template_ref`` 这个列名与 domain 侧的 ``template_id`` 指的是同一个东西**
    （P6-A7，Task 7 的实现者请先读这一段再动手）：

    * **domain 侧叫 ``template_id``**：:attr:`app.domain.prescription.templates.Template.template_id`
      与 :attr:`app.domain.prescription.triggers.LastPrescription.template_id`，那是 spec §7.2
      ``:454`` YAML 骨架里的字面键名，也是 18 份模板 YAML 内容的一部分；
    * **DB 侧叫 ``template_ref``**：与 :attr:`PrescriptionTemplate.template_ref` **同名**，
      于是「这一张处方是按哪一行模板索引生成的」在 schema 上就是一次同名列的连接，
      不必有人记住「这两列其实是一个东西」；
    * 两者是**同一串字符**（``RED-END-ABN-01`` 一类，spec §7.2 的
      ``<层3>-<桶3>-<体成分3>-<序号2>`` 格式，今天最长 14 字符），只在边界上换名字。
      Task 7 落库时写 ``template_ref=template.template_id`` 即可，**不要**去 DB 里找一个
      叫 ``template_id`` 的列、也**不要**给 domain 的值对象加一个 ``template_ref`` 字段。
      漂移守卫：``tests/db/test_models.py`` 的
      ``test_prescription_template_ref_is_the_same_name_as_the_template_table_column``。

    ⚠️ **``valid_to`` 与 Plan 01 的 ``stratification_result.valid_to`` 处置相反，两者都对**
    （简报 Task 6「决定」第 4 条要求在一处写明为什么不同，就写在这里）：

    * ``stratification_result.valid_to`` **恒 NULL**（刻意不关账）：分层结果是**每日快照**，
      它没有自然有效期，「当前生效的那一条」由 ``ORDER BY computed_on DESC LIMIT 1`` 取。
      若给它关账，重放某一天就要跨批改写后续所有行的 ``valid_to``，而
      :func:`app.db.repo.delete_by_batch` 只按 ``batch_id`` 删——跨批的行删不到，于是
      「重放」会留下一堆 ``valid_to`` 与真实区间不符的行。
    * ``prescription.valid_to`` **要真的填**：处方**天然有有效期**（一个微周期），而
      「这名学生当前生效的处方」是 Plan 02 的核心查询（教师端、学生端、Plan 03 的预警
      都要它），靠 ``generated_on`` 加 ``microcycle_weeks`` 现算会让每个读侧都复制一遍
      那个算式（第二个所有者）。填法：
      ``valid_to = generated_on + microcycle_weeks 周 − 1 天``，即**首尾都算在内的闭区间**
      （``microcycle_weeks = 4``、``generated_on = 2026-03-02`` → ``valid_to = 2026-03-29``，
      那正是第 28 天）。⚠️ 它与
      :func:`app.domain.prescription.triggers.evaluate_triggers` 触发 3 的 ``>=`` 边界
      **差一天、而且应该差一天**：``2026-03-30 − 2026-03-02 = 28 天 ≥ 4 × 7`` → 触发 3 在
      ``03-30`` 开火，即新处方在旧处方到期的**次日**生成，两者既不重叠也不留空档
      （若 ``valid_to`` 写成 ``03-30``，``03-30`` 这一天就会同时被两张处方认领）。
      换处方时把上一张置 ``replaced``，**不改写**它的 ``valid_to``。
      ⚠️ **Task 7 落地时把这句的适用范围说清**（此前括注写的是「它本来就到期了」，
      那只在**触发 3（微周期到期）**驱动的换处方上成立）：分层标签变化（触发 2）驱动的
      换处方发生在旧处方**还没到期**的时候，此时也**同样不改写**——理由不是「它到期了」，
      而是①本列必须能从 ``generated_on + microcycle_weeks`` **离线复算**（spec §4.3），
      改写它就废掉这条可追溯性；②改写上一批的行会破坏「同一业务日期重跑只动本批」这条
      幂等边界，与 Plan 01 的 ``stratification_result.valid_to`` 恒 NULL 是同一条纪律
      （``app/pipeline/daily.py`` 的 ``_stratify_and_persist`` 注释逐字给了这个理由）。
      于是两张处方的有效期**可以重叠**，而「哪一张现在生效」由 ``status`` 唯一确定、
      不靠日期区间（守卫 ``tests/pipeline/test_prescription_stage.py`` 的
      ``test_a_layer_change_regenerates_and_replaces``）。
    * 两者不矛盾：差别来自「有没有自然有效期」，不是其中一个写错了。

    **``status`` 刻意没有默认值**（与 :attr:`.ops.DailySyncRun.status` 的 ``default="failed"``
    相反）：那一列的默认值是**保守侧**，因为运行记录常在跑完之前就入库；而本列在
    INSERT 那一刻就已经知道答案了（生成成功 → ``active``，安全规则命中却找不到等价动作 →
    ``needs_review``，见 spec §7.4 与 Review Focus 第 5 条）。给一个 ``default="active"``
    会让「忘了显式写 status」静默变成「这张处方是好的」，而那正是 spec 唯一一处显式要求
    「宁可不自动，也不要自动错」的地方。故本列 NOT NULL 且无缺省，漏传当场炸
    （守卫 ``tests/db/test_models.py::test_prescription_status_is_required_and_has_no_default``）。

    **列宽**（硬规矩 #18）：``status`` 的取值域里最长者是 ``"needs_review"``（**12**），
    声明 ``String(16)``，余量 4；``template_ref`` 与
    :attr:`PrescriptionTemplate.template_ref` 同宽（``String(32)``，今天最长 14、余量 18）；
    ``label_at_generation`` 与 ``stratification_result.label`` 同宽（``String(20)``，
    最长者 ``"insufficient_data"`` 是 **17**、余量 3，Ruling 144 的同一个值）。
    ``status`` 与 ``label_at_generation`` 带 ``_in_domain`` CHECK，故被
    ``tests/db/test_models.py::test_string_column_widths_fit_their_value_domains`` 自动覆盖；
    ``template_ref`` **没有封闭取值域、没有 CHECK → 不被它覆盖**（与 Task 2 的 P2-A5、
    Task 3 的 P3-A5 同型），它的列宽断言另住在
    ``tests/db/test_models.py::test_prescription_template_ref_column_is_as_wide_as_the_template_table_one``
    （两列各自对**字面量 32** 断言，不是互相比，故两侧不同源——硬规矩 #35）。
    """

    __tablename__ = "prescription"

    #: ``status`` 的取值域，spec §4.4 ``:240``。四个值：``active``（当前生效）、
    #: ``replaced``（被更新的一张取代）、``archived``（学期结束/学生离校后归档）、
    #: ``needs_review``（spec §7.4：安全规则命中却找不到等价动作，**不得静默跳过**）。
    #: ⚠️ 最长者 ``"needs_review"`` 是 12 字符，``String(16)`` 余量 4（P6-A9）。
    STATUSES: set[str] = {"active", "replaced", "archived", "needs_review"}

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    #: 生成日期。与 ``student_id`` 组成唯一约束（Review Focus 第 2 条：同一天被两次触发
    #: 只生成一张处方）——那是**机制**，不是纪律：管道重跑或「教师手动请求撞上自动触发」
    #: 时，第二次的 INSERT 会被数据库自己拒收，而不是靠 Task 7 记得先查一遍。
    generated_on: Mapped[dt.date] = mapped_column(Date)
    #: 指向 ``daily_sync_run``：``_replay_cleanup`` 按它整批删（Ruling 31 的口径，与
    #: Plan 01 三张派生表同构）。⚠️ 这一列让本表进
    #: ``tests/db/test_models.py::_BATCH_OWNED_TABLES`` 那份「谁可以有 batch_id」的清单。
    batch_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"), index=True)
    #: 模板的逻辑 id。⚠️ **domain 侧叫 ``template_id``**，对照关系见本类 docstring。
    template_ref: Mapped[str] = mapped_column(String(32))
    #: 微周期周数，**生成当时从 :attr:`app.domain.prescription.templates.Template.microcycle_weeks`
    #: 快照下来**（P6-A3）。⚠️ ``prescription_template`` 表**没有**这一列（实测 10 列），
    #: 而触发 3 的判据与 ``valid_to`` 的算式都要它；模板将来会改版（``version`` 会变），
    #: 故把周期钉在处方行上才符合 spec §4.3 的可追溯性：一张 2026-03 生成的处方必须能
    #: 在 2027 年离线复算出它当时的 ``valid_to``，而不必去猜「那时模板是几周的」。
    #: **刻意不给 ``prescription_template`` 加这一列**——教师端要展示模板周期是 Plan 03
    #: 的 CRUD 层的活，今天加会让本 Task 回头改 Task 3 已结案的表 + ``sync_templates``。
    microcycle_weeks: Mapped[int] = mapped_column(Integer)
    #: **生成当时的分层标签**（Task 7 fix round 1 的 F1-1 新增）。触发 2 的判据逐字是
    #: ``current_label != last_prescription.label_at_generation``，故本列是那条判据的
    #: **唯一输入**。理由与 :attr:`microcycle_weeks`（P6-A3）**完全同构**：处方要能
    #: **离线复算**触发判定（spec §4.3「任一条结果都能离线复算」），就把判定输入
    #: 快照在处方行上。
    #:
    #: ⚠️ **在此之前它没有住址**，``app.pipeline.prescription_stage`` 只能按
    #: ``(student_id, computed_on == generated_on)`` 去 ``outerjoin`` 回读同一天
    #: ``stratification_result.label``。那有三个具体失效形态：①
    #: :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删 ``stratification_result``
    #: 的行——**重放之后那一天的分层行可能已经不在了**，join 返回 ``NULL`` → 触发 2
    #: **静默不成立**（该换处方的时候不换）；② join 的条件是一个**跨表的隐式契约**，
    #: 没有任何守卫钉住它；③ 它让「处方的触发判定」依赖另一张表的行还在不在。
    #: 守卫：``tests/pipeline/test_prescription_stage.py`` 的
    #: ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``
    #: （删掉那一天的分层行 → 触发 2 仍然成立）与 ``tests/db/test_models.py`` 的
    #: ``test_prescription_label_at_generation_shares_its_domain_with_the_label_column``。
    #:
    #: **列宽与 CHECK 都与 ``stratification_result.label`` 同口径**（硬规矩 #18）：值域直接引
    #: :attr:`StratificationResult.LABELS`，**不在本类再声明第二份词表**（本包约定 2 的
    #: 「类常量是唯一真相」在这里的读法是「那个类常量只有一个」）。最长者
    #: ``"insufficient_data"`` 是 **17** 字符（Ruling 144 的同一个值），``String(20)``
    #: 余量 3，与那一列逐字相同——两处长度不同就是一个没人看得见的漂移。
    #: ⚠️ 值域**含** ``insufficient_data`` 而生产上写不进那一档（Z0 闸门在 upsert 之前就
    #: ``continue``）；**刻意不收窄成三个**——收窄就要在本类另立一份词表，即第二个所有者。
    #: 对照 :attr:`PrescriptionTemplate.LAYERS`：那里收窄成三个是因为模板的 ``layer`` 真的
    #: 可能被人写成 ``insufficient_data``、需要 DB 拒收，两处的取舍不同而理由相同。
    label_at_generation: Mapped[str] = mapped_column(String(20), nullable=False)
    #: 4 周训练包 JSON（:class:`app.domain.prescription.assembler.TrainingPackage` 的落库形态）。
    training_package: Mapped[dict] = mapped_column(JsonText)
    #: 装配快照 JSON，**恰好 12 个键**（Task 5 钉死的契约，
    #: ``tests/domain/test_prescription_assembler.py::test_assembly_snapshot_keys_are_exactly_the_pinned_set``），
    #: :func:`app.domain.prescription.safety.apply_safety` 至多再追加 3 个 → **上界 15**。
    #: 它的契约是「离线复算**本张**处方」，故 ⚠️ **不要往里加「关于上一张处方」的键**
    #: （P6-A2 否掉的正是那个方案，见下面 :attr:`previous_had_overrides`）。
    assembly_snapshot: Mapped[dict] = mapped_column(JsonText)
    #: 安全替换记录 JSON（:class:`app.domain.prescription.safety.Substitution` 的列表）。
    safety_substitutions: Mapped[list] = mapped_column(JsonText)
    #: 教师覆盖记录 JSON（:class:`app.domain.prescription.override.OverrideRecord` 的列表）。
    #: 覆盖是**叠加在训练包上的纯函数**（spec §7.5），故它不需要自己的表——本列就是
    #: ``prescription_override`` 这张**不存在的表**的替代品（本模块 docstring 的第二条更正）。
    teacher_overrides: Mapped[list] = mapped_column(JsonText)
    #: **上一张处方当时有没有教师覆盖**（P6-A2 新增，取代「往 ``assembly_snapshot`` 加第 16
    #: 个键」的原方案）。理由：它是**关于上一张处方的事实**，不属于「这一张处方的装配
    #: 输入输出」，放进 ``assembly_snapshot`` 是**范畴错误**（那一列的契约是「离线复算本张
    #: 处方」），而且会让 Task 5 刚钉死的两条键集守卫（12 键 / 至多 +3 键）一起变红。
    #: 用途：Task 7 重生成时据此在日志与教师端留一句「上一张的 N 条覆盖**不会**被继承」
    #: （Review Focus 第 2 条与 Step 6 那条 ``test_regeneration_does_not_inherit_teacher_overrides``）。
    #: ``default=False``：首次生成没有「上一张」，此时它是 ``False`` 而不是 NULL——
    #: 「没有上一张」与「上一张有覆盖」是两件事，但「上一张没有覆盖」与「没有上一张」
    #: 对**本张处方**的处置完全相同（都无覆盖可继承），故合并成一档、不另设三态。
    previous_had_overrides: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    #: 取值域见 :attr:`STATUSES`。⚠️ **NOT NULL 且无默认值**，理由见本类 docstring。
    status: Mapped[str] = mapped_column(String(16))
    #: 生效起。今天恒等于 ``generated_on``；分成两列是因为它们**语义不同**（一个是
    #: 「什么时候算出来的」，一个是「从哪天起按它练」），而 spec §8.4 的「本周训练单」
    #: 读模型允许教师在周一之前先生成、下周一才生效。
    #:
    #: ⚠️ **「今天恒等于」这条是被守卫的**（待清扫第 6 条，Task 9 结案）：
    #: ``tests/pipeline/test_prescription_stage.py`` 里 ``assert {row.valid_from for row in
    #: rows} == {AS_OF}`` 与紧邻的 ``{row.generated_on for row in rows} == {AS_OF}`` 并列，
    #: 故把 ``valid_from`` 写成别的日期会当场红。
    #: ⚠️ **而「两者不相等」那一档今天在生产上不可达，故不存在一条能*区分*它俩的测试**
    #: （硬规矩 #39：写下能力就写明谁在用它、以及它守不住什么）：全仓唯一的写入点是
    #: :func:`app.pipeline.prescription_stage.generate_prescriptions` 的那个字典，
    #: ``"generated_on": as_of`` 与 ``"valid_from": as_of`` 用的是**同一个** ``as_of``。
    #: 要写一条区分测试，就得先造一个让两者不等的调用方——那是 Plan 03 教师端的事
    #: （spec §8.4「周一之前先生成、下周一才生效」，也就是上面那句话的出处）。
    #: 故本 Task 的处置是**把这件事写进本注释、不加一条恒绿的假守卫**（同 Ruling 154 的
    #: 形状：结构上不可能变红的断言只是噪音）。
    valid_from: Mapped[dt.date] = mapped_column(Date)
    #: 生效止（**闭区间**，算式与「为什么与 Plan 01 相反」见本类 docstring）。
    #: nullable：``needs_review`` 的处方还没有确定的有效期，``archived`` 的可以被显式置空。
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    #: 本次生成命中的**全部**触发原因（:class:`app.domain.prescription.triggers.TriggerReason`
    #: 的 ``.value`` 列表，按 spec §5.2 的编号序）。⚠️ 是**列表**不是单值：
    #: :func:`app.domain.prescription.triggers.evaluate_triggers` 返回的是全部命中者，
    #: 教师端要能回答「为什么今天换了处方」，只留第一条会让「教师手动请求 + 微周期到期」
    #: 看起来只是「教师手动请求」。
    trigger_reasons: Mapped[list] = mapped_column(JsonText)

    __table_args__ = (
        _in_domain("status", STATUSES, "ck_prescription_status"),
        # 值域引 StratificationResult.LABELS（单一所有者），约束名照本表既有风格
        # ck_<表名>_<列名>。
        _in_domain(
            "label_at_generation",
            StratificationResult.LABELS,
            "ck_prescription_label_at_generation",
        ),
        UniqueConstraint(
            "student_id", "generated_on", name="uq_prescription_student_day"
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.4 + §8.4 处方：某一周的量微调（Task 6）
# ---------------------------------------------------------------------------


class WeeklyAdjustment(Base):
    """对一张处方的**某一周**乘一个系数（spec §8.4 的「骨架 + 周微调」两层拆分的第二层）。

    | spec §4.4 ``:241`` 原文 | 本表的列            |
    | ======================= | =================== |
    | id                      | ``id``              |
    | 处方                    | ``prescription_id`` |
    | 周次                    | ``week``            |
    | 系数                    | ``factor``          |
    | 原因                    | ``reason``          |
    | 来源                    | ``source``          |
    | 时间                    | ``created_at``      |

    另有一列 spec §4.4 没有的 ``batch_id``（P6-A8，依据见那一列的注释）。

    **为什么微调不直接改 ``prescription.training_package``**：训练包是**骨架**（spec §8.4
    的第一层），微调是叠在它上面的第二层。就地改写会让「这一周的量是算出来的还是被人
    改过的」无从分辨，也让 ``assembly_snapshot`` 的离线复算失去意义（复算出来的是骨架，
    与库里那一行对不上）。故 Plan 03 的「本周训练单」读模型是
    ``骨架第 N 周 × 该周的全部 factor``（:mod:`app.domain.prescription.weekly`，Task 8）。

    ⚠️ **本 Task 只建表 + 教师路径**：``source = "teacher"`` 由 Plan 03 的教师端写；
    ``source = "auto"``（spec §8.4 的「预警触发减量 20%」）**留给 Plan 03**，今天没有任何
    生产写入方。它进 :attr:`SOURCES` 是因为 CHECK 的值域要与 Plan 03 的写入方一次对齐——
    届时再往一个已结案的 CHECK 里加值等于重建库（本仓不做迁移，见 :mod:`app.db.models`）。

    **``factor`` 的语义是「乘上去」而不是「增减多少」**：``1.0`` = 不调整，``0.8`` = 减量
    20%（spec §8.4 的字面），``1.2`` = 加量 20%。选乘法而不是「±20%」是因为同一周上可以
    叠多条微调（教师先减 20%、再因天气减 10%），乘法可交换、可累乘，而「±百分比」相加
    会得到「−30%」这个与两次连乘（``0.8 × 0.9 = 0.72``，即 −28%）**不同**的数——那正是
    口径漂移的形状。**本表不约束 ``factor`` 的取值范围**（不加 CHECK）：合理区间要由体育
    专家给（spec §14 待登记项），今天写一个 ``0.5..1.5`` 一类的范围就是凭空造口径。
    ⚠️ 于是 ``factor = 0`` 或负数在库层面是**放行的**，这一档今天不被任何守卫拦
    （硬规矩 #39），Plan 03 的教师端表单必须自己拦。

    **``reason`` 用 :class:`Text` 而不是 ``String(n)``**：它是给人看的自由文本（教师写
    「本周月考，减量」），照 ``cleaning_log.reason`` 的既有口径。⚠️ 于是它**没有列宽问题**
    （``tests/db/test_models.py::test_string_column_widths_fit_their_value_domains`` 对
    无长度的列直接 ``continue``），也就**不被那道遍历测试覆盖**——它本来也没有封闭取值域。

    **``created_at`` NOT NULL 且无默认值**：时钟一律由调用方注入（Global Constraint #1），
    本包的表**不声明** ``default=dt.datetime.now`` 一类的 Python 侧缺省，也不用
    ``server_default``——后者会把「这一行是什么时候写的」这件事的所有权交给 DB 进程的时钟，
    而回放与重放要求它与 ``daily_sync_run.business_date`` 对得上。
    """

    __tablename__ = "weekly_adjustment"

    #: ``source`` 的取值域（P6-A9：最长者 ``"teacher"`` 是 7 字符，``String(8)`` 余量 1）。
    #: ⚠️ ``"auto"`` 今天**没有生产写入方**，见本类 docstring。
    SOURCES: set[str] = {"auto", "teacher"}

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 被微调的那一张处方。**不声明 ``relationship``**（本包六个表模块的统一约定，见
    #: :mod:`app.db.models`）：管道按 ``batch_id`` 批量读写，显式 ``select`` 比懒加载可预测。
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescription.id"))
    #: 指向 ``daily_sync_run``（**P6-A8 新增**）。计划 Task 7 逐字写着「``_replay_cleanup``
    #: 的清单要加上 ``prescription`` 与 ``weekly_adjustment``（**按 ``batch_id`` 删**）」，
    #: 而 :func:`app.db.repo.delete_by_batch` 是 ``delete(model).where(model.batch_id == …)``
    #: ——模型没有这一列就当场 ``AttributeError``。不加它，Task 7 就得为这一张表另写一段
    #: 级联删（按 ``prescription_id IN (本批的处方)`` 删）并新配一套测试；而「按批删」是本仓
    #: 一致的幂等手段，一列的成本远低于一段新逻辑。⚠️ **必须在 Task 6 就加**：Task 7 才发现
    #: 就要回头改一张已结案的表（硬规矩 #11）。
    #:
    #: ⚠️ **取值口径**（Task 6 结案时按硬规矩 #86 传导给 Task 7 的第 3 件事；同一段话也写在
    #: :mod:`app.pipeline.prescription_stage` 的模块 docstring 里，两处同一口径）：
    #: **管道生成的调整行带本批的 ``batch_id``**；**教师手工加的调整行没有批次**，取
    #: **该行所属处方当前的 ``batch_id``**（处方尚未落库时取本次运行的批次）。
    #: ⚠️ **这条口径的代价**（硬规矩 #39，Task 7 如实记录）：教师手工加的调整行因此继承
    #: 处方的批次，而 :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 整批删
    #: ——于是**重放那一天会连带删掉教师当天的手工微调**。这与「重放同一天的处方会丢掉
    #: ``prescription.teacher_overrides``」是同一条代价的两个面。本仓不做迁移、也没有
    #: 「人工数据豁免于重放」的机制；已登记为 Task 7 报告的关切。
    #: ⚠️ **Task 7 落地后的现状**：``_replay_cleanup`` 的清单里本表**排在 ``prescription``
    #: 前面**（顺序承重：本表的 ``prescription_id`` 是外键，而 ``PRAGMA foreign_keys=ON``
    #: 真的在强制它，先删父表当场 FK 违例，P7-A4）。生产写入方今天仍为**零**
    #: （``source = "teacher"`` 归 Plan 03 的教师端、``"auto"`` 归 Plan 03 的预警侧），
    #: 故本列今天只被「删」不被「写」；守卫是
    #: ``tests/pipeline/test_prescription_stage.py`` 的
    #: ``test_replay_cleanup_covers_prescription_and_weekly_adjustment`` 与它的反证
    #: ``test_deleting_prescription_before_weekly_adjustment_really_violates_the_fk``。
    batch_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"), index=True)
    #: 第几周，**1-based**（spec §8.4：「骨架第 N 周」的 N 从 1 数）。⚠️ 上界是那张处方的
    #: :attr:`Prescription.microcycle_weeks`，而**不是**一个全库常量——模板可以是 2 周、
    #: 6 周，故这里不加 CHECK（加了就是把「4 周」硬编码进 DDL，正是 P6-A3 要避开的事）。
    #: 越界的 ``week`` 今天由 :mod:`app.domain.prescription.weekly`（Task 8）在读侧拒绝。
    week: Mapped[int] = mapped_column(Integer)
    #: 乘上去的系数（``1.0`` = 不调整）。语义与「为什么不存 ±百分比」见本类 docstring。
    factor: Mapped[float] = mapped_column(Float)
    #: 给人看的原因。自由文本，故 ``Text``（照 ``cleaning_log.reason`` 的既有口径）。
    reason: Mapped[str] = mapped_column(Text)
    #: 取值域见 :attr:`SOURCES`。
    source: Mapped[str] = mapped_column(String(8))
    #: 写入时刻。NOT NULL、无缺省，时钟由调用方注入，理由见本类 docstring。
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (
        _in_domain("source", SOURCES, "ck_weekly_adjustment_source"),
        # **Plan 03 Task 2 新增**（计划的裁定 S2：schema 变更一律归本计划唯一的建表
        # Task，不推给写这张表的 Task 7）。P3-A4 实测：在此之前本表**没有任何
        # UniqueConstraint**（约束只有上面那条 CHECK + 2 个外键 + 一个非唯一索引）。
        #
        # 它挡的是 Review Focus 第 3 条的**DB 那一半**：同一条预警被求值两遍
        # （``alert_stage`` 在同一天跑两次、或重放那天 ``_replay_cleanup`` 漏了本表）
        # 就会写出两条一模一样的「减量 20%」，而「本周训练单」是
        # ``骨架第 N 周 × 该周全部 factor`` 的**累乘**（:mod:`app.domain.prescription.weekly`）
        # ——于是那一周的量被连乘成 ``0.8³ = 0.512``，且**全程不报错**。
        # :func:`app.pipeline.daily._replay_cleanup` 的 docstring 逐字描述过这个失效形态。
        # 应用层那一半是 ``alert.window_key`` 的去重键（见 :mod:`.feedback`）。
        #
        # ⚠️ **``reason`` 在键里，是刻意的**：同一周上叠多条微调本身就是本表的设计语义
        # （教师先减 20%、再因天气减 10%，``0.8 × 0.9 = 0.72``，见本类 docstring），
        # 故约束不能只按 ``(prescription_id, week)``——那样第二次**合法**的微调就插不进去。
        # 键里四列的口径是「同一处方 + 同一周 + 同一原因 + 同一来源 = 同一次调整」。
        # ⚠️ 代价（硬规矩 #39）：``reason`` 是自由文本，改一个标点就绕过了本约束；
        # 真正防重复触发要靠 Task 7 按这四个列做 ``repo.upsert``，本约束只是最后一道兜底。
        #
        # ⚠️ ``reason`` 是 ``Text`` 列，而 SQLite 允许在 TEXT 列上建 UNIQUE 索引
        # （比较按 BINARY collation，逐字节）；换 MySQL 需要给这一列指定前缀长度，
        # 已登记为关切。守卫与行为测试：
        # ``tests/db/test_models.py::test_weekly_adjustment_rejects_a_duplicate_week_reason_source``。
        UniqueConstraint(
            "prescription_id",
            "week",
            "reason",
            "source",
            name="uq_weekly_adjustment_prescription_week_reason_source",
        ),
    )
