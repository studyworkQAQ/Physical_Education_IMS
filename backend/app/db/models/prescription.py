"""spec §4.4 处方数据模型（Plan 02 逐 Task 往这里加表，**四个 Task 四张表**）。

计划完成后的状态是 **18 张表** = Plan 01 的 14 张 + 本小节的 4 张（计划
``Document/2026-10-06-实施计划02-智能处方引擎.md`` ``:700``，行号取 shell 口径、绑定
commit ``fb5bddb``）：

========================  =========  =========================================
表                         归属 Task   备注
========================  =========  =========================================
``exercise``              **Task 2**  **已建**（本文件今天只有它）
``prescription_template``  Task 3     18 套模板的索引行，YAML 在 ``data/prescription/``
``prescription``           Task 9     计划 ``:524`` 的 Files 段明写「Modify 本文件（加两张表）」
``weekly_adjustment``      Task 9     同上
========================  =========  =========================================

**逐 Task 递增、不得一次性把四张都建出来**：
``tests/db/test_models.py::test_all_fifteen_tables_created`` 用 ``==`` 钉住表集合
（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把后续 Task 的表建进来」
——那种提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感）。故 Task 3 与
Task 9 各自加自己那张时，**必须同步改那道守卫的期望集合、``== 15`` 的三处断言与函数名里的
「fifteen」**（``tests/db/test_models.py`` ``:24`` / ``:163`` / ``:228`` / ``:472``），
以及本文件上面那张表。

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

``exercise`` 与另外三张表有一处**性质上的不同**，值得写在这里：它是本小节唯一一张
**参考数据**表（专家维护的知识资产在 DB 里的投影），另外三张是业务数据。故它的灌数据
函数**不在** ``app/seed/``——那是仿真人口生成器的住址，且自 Plan 01 结案后重新冻结
（Global Constraint #10）；``exercise`` 的同类是 ``app/refdata.py``，故灌数据函数是
:func:`app.refdata_prescription.sync_exercises`（Plan02 账本 P2-A1 的裁定）。
"""

from sqlalchemy import String
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
    :class:`app.domain.prescription.templates.ImpactLevel` 是**两份**词表，由
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
