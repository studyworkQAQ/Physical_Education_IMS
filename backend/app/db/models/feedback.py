"""spec §4.5 反馈三源 + §4.6 预警与通知 + §4.7 班级周报：**七张表全住在本模块**。

Plan 02 Task 1 建这个模块时它是一个 475 B 的空壳，模块 docstring 逐字写着「本模块今天
刻意是空的」；Plan 03 Task 2 把它填满。七张表与 spec 小节的对应关系：

=========================  ===========  =====================================
表                          spec 小节    谁写它
=========================  ===========  =====================================
``class_session``           §4.5         管道 **+ 教师实时**（建课次 / 发起快评）
``rpe_record``              §4.5         **学生实时**（课堂快评 H5）
``training_log``            §4.5         管道 **+ 学生实时**（H5 每日打卡）
``mini_test``               §4.5         **教师实时**（批量录入）
``alert``                   §4.6         管道（Task 7 的 ``alert_stage``）
``notification``            §4.6         Task 8 的 ``InAppChannel``
``weekly_class_report``     §4.7         管道（Task 9 的 ``report_stage``）
=========================  ===========  =====================================

⚠️⚠️ **``alert`` / ``notification`` / ``weekly_class_report`` 刻意不住在
:mod:`.ops`，尽管 spec §4.6 的标题逐字是「预警与运维」**（Plan 03 账本 P3-A1，Critical）。
理由是**导入机制**、不是文档结构：``app/db/models/__init__.py`` 对 ``ops`` 是
``from .ops import *``（**星号**导入），而对 ``feedback`` 与 ``prescription`` 是
``from . import feedback, prescription``（**非星号**）。把这三个类放进 ``ops.py``，
``Alert`` / ``Notification`` / ``WeeklyClassReport`` 三个名字就会**自动**出现在
``app.db.models`` 的公有命名空间里，于是
``tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split``
的 ``assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)`` 当场红——
而唯一的「修法」是把那份基线从 **33** 抬到 **36**，那正是 Ruling 97 逐字禁止的
（「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了」，
硬规矩 #35）。走本模块则**零新增守卫**：非星号导入让七个类名天然留在公有面之外，
与 Plan 02 的 ``prescription.py`` 完全同一个机制。

⚠️ 于是「留空而不是放占位类」那段旧 docstring（它指向 :mod:`app.db.models.prescription`
的 docstring）已经不适用，整段换成本段。**别按 spec 的章节标题把这七张表里的任何一张
搬去 ``ops.py``**——搬过去就会撞上面那条守卫，而撞红之后唯一看起来可行的修法是错的。
spec 的 §4.5/§4.6/§4.7 分节是**文档结构**，不是 Python 模块布局的约束。

三条贯穿全表的约定写在包的 docstring 里（:mod:`app.db.models`）：缺测就是 ``NULL``
绝不是 0；枚举取值域「类常量 + :func:`._shared._in_domain`」两处设防；JSON 形态的列
一律用 :class:`._shared.JsonText`（本模块贡献 **7** 个：``mini_test.item_combo``、
``alert.trigger_snapshot`` 与 ``weekly_class_report`` 的 5 个）。
本模块同样**不声明任何 ``relationship``**。

----------------------------------------------------------------------------
``batch_id``：**七张表里只有四张有**，这个区分是承重的
----------------------------------------------------------------------------

* **有的四张**（``class_session`` / ``training_log`` / ``alert`` /
  ``weekly_class_report``）是**批处理产物**：由管道按业务日期整批写出，因此也必须能
  被 :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 整批删——重放的定义是
  「同一批输入得到同一批输出」，删不干净就是翻倍。它们因此进
  ``tests/db/test_models.py::_BATCH_OWNED_TABLES`` 那份清单（5 → **9** 张）。
  ⚠️ **其中两张的这一列是可空的**（``class_session`` / ``training_log``，Plan 03
  Task 5 的 P5-A1）：它们各有**两个**写入来源——管道整批写的那一种带 ``batch_id``，
  **用户实时写的那一种留 ``NULL``**（教师在前端建课次、学生在 H5 上打卡）。
  ``NOT NULL`` 只容得下一个来源，于是实时的那种行改可空之前**根本写不进去**。
  ⚠️ **可空恰好把重放语义也一并解决了**：``delete_by_batch`` 是 ``WHERE batch_id = :b``，
  而 SQL 的三值逻辑里 ``NULL = 任何值`` **都不成立**，故实时行天然躲过重放——
  这正是下面那三张表想要的性质，只是它们用「不带这一列」实现、这两张用「带但可空」实现。
  ⚠️ 判据仍是「**有** ``batch_id`` 列」（可空性不改变列的存在），故
  ``_BATCH_OWNED_TABLES`` 那条守卫与 ``test_only_batch_owned_tables_expose_batch_id``
  都**不受影响**；受影响的是读模型（``batch_id: int`` 要改成 ``int | None``，
  否则 ``NULL`` 会让 ``response_model`` 校验失败 → **500**，而 500 会把
  「这一行是用户实时写的」这件事伪装成服务器故障）。
* **没有的三张**（``rpe_record`` / ``mini_test`` / ``notification``）是**用户实时写入**的：
  学生在课堂上交的快评、教师刚批量录入的小测、已经推给某个人的站内消息。
  给它们加 ``batch_id`` 就等于宣布「重放那天可以按批删掉它们」，而
  **删源数据比删派生行严重得多**——派生行重算就回来了，学生交过的作业删了就是删了
  （与 ``fitness_test_result`` 那一列刻意叫 ``test_batch_id`` 而不叫 ``batch_id``
  是同一条判断，Ruling 31）。
  守卫是 ``tests/db/test_models.py::test_the_three_user_written_tables_have_no_batch_id``。

⚠️ **「有 ``batch_id``」不等于「在 ``_replay_cleanup`` 的清单里」**，而 ``class_session``
正是这个区别的要害（按硬规矩 #86 传导给 Task 8）：``rpe_record.class_session_id`` 是
**NOT NULL 的外键**指向它，而 ``rpe_record`` 是用户实时写入、重放不该删。于是
``ClassSession`` **不得**进 ``_replay_cleanup``——按批删课次会当场
``FOREIGN KEY constraint failed``（``PRAGMA foreign_keys=ON``，Ruling 27），
而改成 ``ON DELETE CASCADE`` 更糟：它会连带删掉学生刚交的快评。
``class_session`` 的幂等手段因此是 ``repo.upsert`` 按
``(course_section_id, session_date, period)`` 更新，与三张源表同一档；
它那一列 ``batch_id`` 只用来回答「这一行是哪一次同步写进来的」，不用来删。
``alert`` 与 ``weekly_class_report`` 没有这个问题（没有子表指着它们，
``notification.alert_id`` 带 ``ON DELETE SET NULL``），Task 8 可以照常接进清单。

----------------------------------------------------------------------------
``alert`` 的去重键：为什么多一列 spec 没有的 ``subject_key``
----------------------------------------------------------------------------

Review Focus 第 3 条要求「同一次触发只有一条 ``alert``」，而预警有两种作用域
（spec §4.6 逐字：「student_id（班级级预警为 course_section_id）」）。
计划正文的方案是把两个作用域列都改成 ``nullable=False`` + 用 ``0`` 作哨兵，
理由是 SQLite 的 UNIQUE 对 NULL 是「NULL ≠ NULL」、两列可空会让约束对班级级预警
**静默失效**。**那个诊断是对的，方子却撞在另一堵墙上**：这两列都是外键，
父表里没有 ``id = 0`` 的行（SQLite 的 rowid 从 1 起），于是每一条哨兵行都会当场
``IntegrityError: FOREIGN KEY constraint failed``。

本模块的落地：两个外键列**保持可空**（完整性不丢，Review Focus 第 4 条要的正是
「FK 违例当场炸而不是静默留下孤儿行」），另加一个 NOT NULL 的 ``subject_key``
承担去重键里的主语位，并配一条 CHECK 保证「两个作用域列恰好一个非空」
（否则 ``subject_key`` 无从定义）。这与 :class:`.ops.CleaningLog` 的
``student_no``（非空、逐字照抄）+ ``student_id``（可空外键）双列承载（Ruling 25）
是同一个形状。守卫与那段反证（哨兵 0 真的会炸）住在
``tests/db/test_models.py::test_alert_dedup_binds_for_both_student_and_class_scope``
与 ``…::test_alert_subject_sentinel_zero_would_violate_the_fk``。
⚠️ ``window_key`` 同样是 spec §4.6 没有的列（本计划的工程决定，登记 spec §14）。

----------------------------------------------------------------------------
加表 / 加列时要同步改哪些地方（硬规矩 #66/#88：跑一次全量，别只 grep 一个数）
----------------------------------------------------------------------------

完整清单住在 :mod:`.prescription` 的模块 docstring 与
``tests/db/test_models.py::test_all_twenty_five_tables_created`` 的那段注释里，
本模块不抄第二份（单一所有者）。只提醒两处**本模块特有**的：

* 加带 ``JsonText`` 的列 → 抬 ``assert len(json_text_columns) == 21``，
  并连带改 :mod:`._shared` 的 ``JsonText`` docstring 与 :mod:`app.db.models` 的约定 3
  （**三处同一事实**）；
* 加带 ``batch_id`` 的列 → 往 ``_BATCH_OWNED_TABLES`` 那**一份**清单里加表名
  （Plan 03 Task 2 实测：它在 ``app/`` 下的四处命中**全是散文引用**，没有第二份定义），
  并先读上面那段「有 ``batch_id`` 不等于进 ``_replay_cleanup``」。
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

# `notification.prescription_id` 与 `rpe_record.class_session_id` 都是**字符串形式**的
# 外键，SQLAlchemy 要到 ``create_all`` / mapper 配置那一刻才去 ``Base.metadata`` 里找
# 目标表。`prescription` 与本模块平级、且 `__init__.py` 的
# `from . import feedback, prescription` 已经把两者都导入，故走包路径时不需要本行；
# 但「只 import 本子模块」的写法（`from app.db.models.feedback import Alert` 然后
# 自己 `create_all`）会当场 `NoReferencedTableError: prescription`。显式导入把这个
# 脚枪拆掉，与 `prescription.py` 为拿 `StratificationResult.LABELS` 而
# `from .derived import StratificationResult` 是同一种「承重导入」。无环：
# prescription → derived → organisation，没有任何一条边指回 feedback。
from . import prescription as _prescription_module  # noqa: F401


# ---------------------------------------------------------------------------
# spec §4.5 反馈三源之一：课堂端 RPE（课次 + 快评记录）
# ---------------------------------------------------------------------------


class ClassSession(Base):
    """一节课。课堂快评（RPE）挂在它上面，故它是 §4.5「课堂端」那一源的锚点。

    | spec §4.5 原文            | 本表的列              |
    | ========================= | ===================== |
    | id                        | ``id``                |
    | course_section_id         | ``course_section_id`` |
    | 日期                      | ``session_date``      |
    | 节次                      | ``period``            |
    | 是否已发起课堂快评        | ``rpe_opened``        |
    | 快评口令                  | ``rpe_token``         |

    另有一列 spec §4.5 没有的 ``batch_id``（理由见模块 docstring 的那一段）。

    **``rpe_opened`` 是「教师点没点『发起课堂快评』」**（spec §8.1 的第一步），
    而不是「有没有人提交」。把它做成缺省 ``False`` 的 NOT NULL：一个没被发起的快评与
    一个发起了但没人交的快评，在学生端首页是两种不同的状态（前者根本没有待办卡片），
    而 ``NULL`` 会把两者混成一档。

    **``rpe_token`` 可空**：没发起就没有口令，这与 ``rpe_opened = False`` 是同一件事的
    两面，但两列都留：口令是给学生端校验用的**字符串**，开关是给教师端列表用的
    **布尔**，读侧不必互相反推。⚠️ 两者今天没有任何约束把它们绑在一起
    （``rpe_opened = False`` 而 ``rpe_token`` 非空在库层面放行），
    Task 5 的写入方要自己保证一致；已登记为关切（硬规矩 #39）。

    **``period`` 是节次（第几节），不是时长**，故没有 CHECK：一节课的节次编号是校历
    口径（1–N），写死一个 ``1..12`` 就是凭空造口径（照 ``WeeklyAdjustment.factor``
    不加 CHECK 的既有处置）。

    ⚠️ **``batch_id`` 可空（Plan 03 Task 5，P5-A1）**：本表有**两个写入来源**——
    ① 管道/演示生成器按业务日期整批写（带 ``batch_id``，回答「这一行是哪一次同步
    写进来的」）；② **教师在前端实时建课次**（spec §8.1 的第一步「教师发起课堂快评」
    的前提是那节课得先存在），**这种行没有批次可指**。改可空之前它写不进去
    （当场 ``NOT NULL constraint failed``）。完整理由与「可空为什么恰好是对的」
    见模块 docstring 的那一段与 :func:`app.db.repo.delete_by_batch` 的 docstring。
    """

    __tablename__ = "class_session"

    #: ``rpe_token`` 的**长度**（= 列宽 = 生成时的截断长度）。
    #:
    #: ⚠️ **本常量是「16」这个数在本仓的唯一所有者**（P5-A6）：本 Task 之前它是两个
    #: 没有出处的魔数——一个在 ``String(16)`` 里、一个在 Task 5 的
    #: ``secrets.token_urlsafe(12)[:16]`` 里，两处各写一遍迟早漂移，而漂移是静默的
    #: （SQLite **不强制** ``VARCHAR`` 长度，故一个 20 字符的口令会照样存进去、
    #: 只是换到 MySQL 会被截断成 16 而**校验从此永远失败**——炸在读侧，离真因很远）。
    #: 生成侧引它、列类型也引它，故「口令塞不进列」在结构上不可能发生。
    #: ⚠️ ``12`` 那个字节数由本常量派生（``RPE_TOKEN_LEN * 3 // 4``）：base64url 每
    #: 3 字节编成 4 字符，故 12 字节 → 恰好 16 字符、无 padding。
    RPE_TOKEN_LEN: int = 16

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 哪个教学班的课。**不声明 ``relationship``**（本包的统一约定，见
    #: :mod:`app.db.models`）：显式 ``select`` 比懒加载可预测。
    course_section_id: Mapped[int] = mapped_column(ForeignKey("course_section.id"))
    session_date: Mapped[dt.date] = mapped_column(Date)
    period: Mapped[int] = mapped_column(Integer)
    #: 是否已发起课堂快评。NOT NULL + 缺省 ``False``，理由见本类 docstring。
    rpe_opened: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 快评口令，宽度 = :attr:`RPE_TOKEN_LEN`。⚠️ Task 3 结案时这一列的注释写的是
    #: 「演示与 Task 5 都用 8 位大写字母数字，余量 8」——**Task 5 实际用的是
    #: ``secrets.token_urlsafe``（base64url 字母表，大小写混排 + ``-`` / ``_``），
    #: 长度恰好等于列宽**，故那句「余量 8」已经不成立，按实际口径改写。
    #: 列宽断言仍住在
    #: ``tests/db/test_models.py::test_the_unconstrained_string_columns_of_the_plan03_tables_are_wide_enough``。
    rpe_token: Mapped[str | None] = mapped_column(String(RPE_TOKEN_LEN))
    #: 指向 ``daily_sync_run``，**可空**（P5-A1，理由见本类 docstring 末段）：
    #: 管道写的那一批带它，教师实时建的那一行留 ``NULL``。
    #: ⚠️ **本表有 ``batch_id`` 却不得进 ``_replay_cleanup``**：
    #: ``rpe_record.class_session_id`` 是 NOT NULL 的外键指向本表，而 ``rpe_record`` 是
    #: 学生实时写入的、重放不该删。幂等手段是 ``repo.upsert`` 按下面那条唯一约束更新。
    #: 完整理由见模块 docstring（按硬规矩 #86 传导给 Task 8）。
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True, nullable=True
    )

    __table_args__ = (
        # ⚠️ 这一条 spec §4.5 没有点名，是本 Task 补的（顶回 #1）：7 张表里计划正文给
        # 另外 5 张都点了唯一约束，唯独漏了本表，而它正是最需要的一条——
        # `repo.upsert` 是「先 select 再 update/insert」，没有 DB 层兜底时两个写入方
        # 会各插一行，而下一次 upsert 的 select 撞上 `MultipleResultsFound`，
        # **炸在离真因很远的读侧**。理由与守卫见
        # ``tests/db/test_models.py::test_class_session_rejects_a_second_session_for_the_same_section_date_and_period``。
        UniqueConstraint(
            "course_section_id",
            "session_date",
            "period",
            name="uq_class_session_section_date_period",
        ),
    )


class RpeRecord(Base):
    """一次课堂快评（RPE 0–10 主观疲劳），spec §4.5「课堂端」。

    | spec §4.5 原文     | 本表的列             |
    | ================== | ==================== |
    | （id）             | ``id``               |
    | class_session_id   | ``class_session_id`` |
    | student_id         | ``student_id``       |
    | RPE 0–10           | ``rpe`` + CHECK      |
    | 提交时间           | ``submitted_at``     |
    | **提交耗时秒**     | ``elapsed_seconds``  |

    **刻意不带 ``batch_id``**：它是学生在课堂上实时交的，重放那天不该被按批删掉
    （模块 docstring 的那一段）。

    ``elapsed_seconds`` 的可空是**承重的**：spec §8.1 逐字「指导文件要求 10 秒内完成」，
    没有这一列，那句话在系统里就没有落点。而它可空、无缺省——「没量到耗时」与
    「量到 0 秒」不是一回事（包约定 1：缺测就是 ``NULL``）。

    ``(class_session_id, student_id)`` 唯一：一节课上同一个学生只能交一次。
    少了它，学生连点两次「提交」会让 ``YELLOW_CLASS_RPE_HIGH`` 的「课堂 RPE 均值」
    被同一个人算两遍，而教师端「已提交/未提交名单」会显示 101%。
    """

    __tablename__ = "rpe_record"

    #: RPE 值域的两个端点。**它是全库「RPE 是 0–10 的整数」这件事的唯一所有者**
    #: （spec §8.2；Plan 02 已把它写进 ``assembler.py`` 的 docstring 与 ``INTENSITY_TYPES``
    #: 的 ``rpe`` 档，那两处是散文、不是常量，故不要再写第三份）。
    #: ⚠️ 下面那条 CHECK 的文本由这两个常量生成而不是手写第二遍，理由与
    #: :func:`._shared._in_domain` 逐字同一条：手写两遍迟早漂移，而漂移是静默的。
    #: ⚠️ spec §8.2 的两条阈值都建立在这个值域上（``RED_RPE_SUSTAINED`` 连续 ≥ **9**、
    #: ``YELLOW_CLASS_RPE_HIGH`` 均值 > **7**），故 Task 6 校验 ``alert_rules.yaml``
    #: 时应当拿它们当上界——把 RPE 改成百分制而不同步阈值，那两条规则会**静默失效**。
    RPE_MIN: int = 0
    RPE_MAX: int = 10

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 哪一节课。NOT NULL 的外键——⚠️ 这正是 ``ClassSession`` **不得**进
    #: ``_replay_cleanup`` 的原因（见那一列的注释）。
    class_session_id: Mapped[int] = mapped_column(ForeignKey("class_session.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    #: 0–10 的整数，值域见 :attr:`RPE_MIN` / :attr:`RPE_MAX`。
    rpe: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: 提交耗时（秒）。可空、无缺省，理由见本类 docstring。
    elapsed_seconds: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "class_session_id", "student_id", name="uq_rpe_record_session_student"
        ),
        # ⚠️ **全库第一处手写的 CHECK**（P3-A5）：:func:`._shared._in_domain` 的签名是
        # ``(column: str, allowed: Iterable[str], name: str)``，它只吃**字符串词表**，
        # 而 RPE 是整数区间。文本按 f-string 从上面两个类常量生成，不手写第二遍。
        CheckConstraint(
            f"rpe BETWEEN {RPE_MIN} AND {RPE_MAX}", name="ck_rpe_record_rpe"
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.5 反馈三源之二：课外端每日打卡
# ---------------------------------------------------------------------------


class TrainingLog(Base):
    """一天的课外训练打卡，spec §4.5「课外端」。

    | spec §4.5 原文     | 本表的列          |
    | ================== | ================= |
    | （id）             | ``id``            |
    | student_id         | ``student_id``    |
    | 日期               | ``log_date``      |
    | （提交时刻）       | ``submitted_at``  |
    | 是否完成           | ``completed``     |
    | 完成时长分钟       | ``duration_min``  |
    | 自评感受           | ``feeling`` + CHECK |
    | 是否休息日打卡     | ``is_rest_day``   |
    | ``late`` 标记      | ``late``          |
    | 来源               | ``source`` + CHECK |
    | sync_run_id        | ``batch_id``      |

    ⚠️ spec §4.5 那一格写的是 **``sync_run_id``**，本表叫 **``batch_id``**：两者指的是
    同一个父表（``daily_sync_run``），而 ``batch_id`` 一词在本项目里**专指**它
    （Ruling 31：``delete_by_batch`` 的合法目标）。用 ``sync_run_id`` 这个名字会让本表
    落进 ``cleaning_log`` 那一档（刻意**不**按批删的表），而打卡**有一半是**管道产物、
    重放那天必须能删干净。故按 Ruling 31 的口径命名，spec 的那一格是文档用词。

    ⚠️⚠️ **``batch_id`` 可空（Plan 03 Task 5，P5-A1）：本表有两个写入来源，而
    ``NOT NULL`` 只容得下一个。** ① 管道/演示生成器按业务日期整批同步（带
    ``batch_id``，``_replay_cleanup`` 按批删它们）；② **学生每天在 H5 上打卡**
    （spec §8.1 的「课外端每日打卡」）——**这种行没有批次可指**，改可空之前
    写进去当场 ``NOT NULL constraint failed``。
    **可空恰好是对的方案**，理由是一条 SQL 语义：:func:`app.db.repo.delete_by_batch`
    是 ``WHERE batch_id = :b``，而 **``NULL = 任何值`` 在 SQL 里都不成立**
    （三值逻辑），故**学生实时打的那些行天然躲过重放**——这正是我们要的：
    打卡是学生的作业，重放那天不该把它删掉（与 ``rpe_record`` / ``mini_test``
    干脆不带 ``batch_id`` 是**同一个判断的两种落法**：那两张表只有一种来源，
    本表有两种，故用「可空」把两种来源分开）。

    ⚠️ **``submitted_at`` 是 spec §4.5 的字段清单里**没有**的一列**（Plan 03 Task 5 补，
    登记 spec §14）。补它的理由不是「多一列信息」，而是**没有它就实现不了 spec §8.1
    自己要求的两件事**：

    1. **``late`` 的判定需要提交时刻**：spec §8.1 逐字「打卡窗口 = 当日 00:00–22:00。
       22:00 后提交仍入库但标记 ``late = true``」。判定发生在写入那一刻
       （:mod:`app.api.routers.feedback` 拿 ``datetime.now(ZoneInfo(TIMEZONE))`` 比），
       **不存下来就无从复核**——而完成率是 spec 逐字点名的「RCT 关键过程指标，必须严格」。
    2. **「补卡不计入完成率」需要它与 ``log_date`` 相比**：学生 23:50 补打前天的卡时，
       ``late`` 只看时刻（23:50 > 22:00 → ``True``），**但一个 21:00 补打前天卡的
       学生 ``late`` 是 ``False``**——没有 ``submitted_at`` 就读侧**分不清**
       「当天打的」与「事后补的」，于是「补卡不计入完成率」这条口径无处落地。

    ⚠️ **不加它的替代方案是把「补卡」编码进 ``late``**（补卡也置 ``True``），
    本 Task 明确**不选**它：那会把「22:05 交的当天卡」与「三天后补的卡」
    **不可逆地混成一档**，而 Task 6/7 的 ``YELLOW_CHECKIN_GAP`` 与事后审计都可能要
    区分两者。信息销毁比多一列贵（本仓不做迁移，但**现在**加一列比**以后**加便宜：
    以后加 = 重建库 + 历史行的 ``submitted_at`` 永远只能是 ``NULL``）。
    ⚠️ 与 :attr:`RpeRecord.submitted_at` 也因此对称了：两张表都是「学生实时提交」的，
    此前只有一张有提交时刻，那个不对称本身就是这一列缺失的征兆。

    **``late`` 与 ``completed`` 是两件事**，不要合并：spec §8.1 逐字「22:00 后提交
    仍入库但标记 ``late = true``，**不计入当日完成**」。于是 ``completed = True`` 且
    ``late = True`` 是**合法且有含义**的一档——学生说他自己练了，但交得太晚，
    完成率（RCT 的关键过程指标）不算它。把两列合成一个三态枚举会让「练了但迟交」
    与「没练」在库里长得一样，而那是过程指标里最不该混的一类。
    ⚠️ 打卡窗口「当日 00:00–22:00」的**判定**归 :mod:`app.api.routers.feedback`
    （Review Focus 第 2 条：22:00:00 整点算闭区间内、不算迟），本表只承载判定结果。

    **``is_rest_day``**：spec §8.1 的折中方案是「每日都可打卡，非训练日一键『今日休息』；
    但完成率只按处方训练日计算」。没有这一列，休息日的打卡会被算进分母，
    绿层学生（处方每周只练 2 天）的完成率于是天然低到不可能达标。

    ``(student_id, log_date)`` 唯一：一天一行。⚠️ 注意这条唯一键里**没有**
    ``submitted_at``，故「补卡」不可能造出同一天的第二行——补卡是**更新**那一行
    还是被 409 拒掉，由写入方决定（:mod:`app.api.routers.feedback` 选**拒掉**：
    一天一行是这张表的口径，改它会连带 ``YELLOW_CHECKIN_GAP`` 的「连续 N 天」判据）。
    """

    __tablename__ = "training_log"

    #: ``feeling`` 的取值域 = spec §8.1 的「轻松 / 适中 / 吃力」三选一。
    #: 存英文 token（与全库其余枚举同一口径），中文标签由前端映射。
    #: 最长者 ``"moderate"`` 是 8 字符，``String(16)`` 余量 8。
    FEELINGS: set[str] = {"easy", "moderate", "hard"}

    #: ``source`` 的取值域（P5-A3：本 Task 之前这一列**没有唯一所有者**，
    #: 故刻意没有 CHECK；Task 5 落地采集端点时按那一列注释里写下的
    #: 「Task 5 落地时必须回来定这个值域并补 CHECK」兑现）。三个值各有写入方：
    #:
    #: * ``"checkin"`` —— **学生实时打卡**（:mod:`app.api.routers.feedback` 的
    #:   ``POST /api/training-logs``，本 Task 新增的写入方）；
    #: * ``"demo"`` —— :func:`app.demo_data.build_demo_feedback`（Task 2 就有）。
    #:   ⚠️ 它同时兼着一个用处：一眼能认出哪些行是演示数据、哪些是真人打的
    #:   （``app/demo_data.py`` 的 :data:`~app.demo_data.DEMO_SOURCE` 是它的住址）；
    #: * ``"lepao"`` —— 乐跑 App 同步（spec §4.5 那一源）。⚠️ **今天生产里还没有
    #:   这个写入方**（``app/pipeline/daily.py`` 不写 ``training_log``；它只在
    #:   ``tests/api/test_crud.py`` 的夹具里出现），**仍然放进词表**：照
    #:   :attr:`Notification.CHANNELS` 的既有处置——「届时往一个已结案的 CHECK 里
    #:   加值等于重建库（本仓不做迁移）」，故宁可现在多列一个还没有写入方的值。
    #:
    #: ⚠️ 最长者 ``"checkin"`` 是 7 字符，``String(16)`` 余量 9。
    SOURCES: set[str] = {"checkin", "lepao", "demo"}

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    log_date: Mapped[dt.date] = mapped_column(Date)
    #: **提交时刻**（spec §4.5 没有这一列，理由与取舍见本类 docstring 那一段）。
    #: NOT NULL 且**无缺省**：时钟由调用方注入（本包的统一约定，守卫是
    #: ``tests/db/test_models.py::test_the_plan03_tables_inject_the_clock_and_never_default_it``）。
    #: ⚠️ 存的是 **naive 本地时间**（``app.config.TIMEZONE`` 那个时区）：SQLite 的
    #: ``DateTime`` 存 naive，而混用 aware 与 naive 做比较会当场 ``TypeError``。
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: 学生自报「今天练了没有」。NOT NULL、**无缺省**：缺省会让「忘了写」看起来像
    #: 「写了没练」或「写了练了」，而完成率是 RCT 关键过程指标（spec §8.1）。
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: 完成时长（分钟）。可空：没练就没有时长（包约定 1）。
    duration_min: Mapped[float | None] = mapped_column(Float)
    #: 自评感受，取值域见 :attr:`FEELINGS`。可空：没练就没有感受。
    feeling: Mapped[str | None] = mapped_column(String(16))
    is_rest_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 22:00 之后提交。语义见本类 docstring（与 ``completed`` 是两件事）。
    late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 来源，取值域见 :attr:`SOURCES`（P5-A3 起有了 CHECK，此前刻意没有）。
    #: ⚠️ 加了 CHECK 之后，这一列的列宽由
    #: ``test_string_column_widths_fit_their_value_domains`` 那条**遍历**测试自动覆盖
    #: （它从 ``_in_domain`` 的约束文本反解取值域），不再只靠
    #: ``test_the_unconstrained_string_columns_of_the_plan03_tables_are_wide_enough``
    #: 的字面量钉；后者仍保留「恰好 16」那一格，防有人把列改窄。
    source: Mapped[str] = mapped_column(String(16))
    #: 指向 ``daily_sync_run``（spec §4.5 那一格写的是 ``sync_run_id``，
    #: 命名口径见本类 docstring）。**可空**：管道同步的行带它、学生实时打卡的行留
    #: ``NULL``，而 ``NULL`` 让后者天然躲过 ``delete_by_batch``（P5-A1，
    #: 完整理由见本类 docstring 那一段）。
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_sync_run.id"), index=True, nullable=True
    )

    __table_args__ = (
        UniqueConstraint("student_id", "log_date", name="uq_training_log_student_day"),
        _in_domain("feeling", FEELINGS, "ck_training_log_feeling"),
        _in_domain("source", SOURCES, "ck_training_log_source"),
    )


# ---------------------------------------------------------------------------
# spec §4.5 反馈三源之三：阶段端二次小测（每两周）
# ---------------------------------------------------------------------------


class MiniTest(Base):
    """一次二次小测，spec §4.5「阶段端」。

    | spec §4.5 原文       | 本表的列             |
    | ==================== | ==================== |
    | （id）               | ``id``               |
    | student_id           | ``student_id``       |
    | semester_id          | ``semester_id``      |
    | 周次                 | ``week``             |
    | 测试项组合           | ``item_combo``       |
    | 30 秒深蹲次数        | ``squat_30s_count``  |
    | 20m 折返秒数         | ``shuttle_20m_s``    |
    | 标准化得分           | ``normalized_score`` |
    | 测试日期             | ``tested_on``        |
    | 录入教师             | ``entered_by``       |

    **刻意不带 ``batch_id``**：它是教师**批量录入**的（spec §8.1：「按教学班列出学生
    逐个填」），重放那天不该被按批删掉。

    **``item_combo`` 是「教师从测试项库中选的组合」**（spec §8.1：指导文件给了
    「30 秒深蹲 + 20m 折返跑」，但写了「或其他」）。故两个测量列都**可空**：
    选了别的组合时这两列就是 ``NULL``，而组合本身记在 ``item_combo`` 里。
    把两列做成 NOT NULL 等于把「深蹲 + 折返」硬编码进 schema，
    而 spec 明确留了口子。

    ⚠️ **``normalized_score`` 的算法今天没有实现**：spec §8.1 给的是
    「深蹲得分 = 次数（直接用）；折返得分 = 该教学班内折返秒数的百分位反查；
    综合分 = 两项等权平均」，而「班内百分位反查」要读整个教学班的行，
    是 spec §5 第 7 阶段（Aggregate）的活。故本 Task 只建列，
    :func:`app.demo_data.build_demo_feedback` 写的是**演示口径**的近似值
    （它自己的 docstring 里逐字声明了这件事）。

    ``(student_id, semester_id, week)`` 唯一：每两周一次，一周至多一份。
    ``RED_MINITEST_DROP`` 要 3 个数据点才能判「连续两次下降 ≥ 5%」（spec §8.2 的
    补齐口径 #2），同一周多一行会让那三个点错位成「同一周自己跟自己比」。
    """

    __tablename__ = "mini_test"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    #: 学期周次（1-based，与 ``weekly_adjustment.week`` 同口径）。
    #: ⚠️ 不加「必须是偶数周」的 CHECK：spec §8.1 说的是「系统按学期周历**自动算出**
    #: 应测周次（偶数周），**教师确认**并批量录入」——教师可以改，写死进 DDL 就是
    #: 把一个可调整的排期口径变成数据库约束。
    week: Mapped[int] = mapped_column(Integer)
    #: 测试项组合，例如 ``["squat_30s", "shuttle_20m"]``。走 :class:`JsonText`：
    #: 读回来是原样的 ``list``，调用方不必自己 ``json.loads``（包约定 3）。
    item_combo: Mapped[list] = mapped_column(JsonText)
    squat_30s_count: Mapped[int | None] = mapped_column(Integer)
    shuttle_20m_s: Mapped[float | None] = mapped_column(Float)
    normalized_score: Mapped[float | None] = mapped_column(Float)
    tested_on: Mapped[dt.date] = mapped_column(Date)
    #: 录入教师的**工号**（``String(32)``，与 ``teacher.staff_no`` 同宽）。
    #: ⚠️ 刻意不是外键：原型用请求头传身份（``X-Teacher-Staff-No``，见
    #: :mod:`app.api.deps`），录入方在写这一行时手上只有工号；做成 ``teacher_id``
    #: 外键会要求写入方先查一次 ``teacher`` 表。代价是「删教师不会带走他录的小测」，
    #: 已登记为关切（Task 3 的删除策略要显式声明这一档）。
    entered_by: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        UniqueConstraint(
            "student_id", "semester_id", "week", name="uq_mini_test_student_semester_week"
        ),
    )


# ---------------------------------------------------------------------------
# spec §4.6 预警与通知（⚠️ 住在本模块而不是 ops.py，理由见模块 docstring）
# ---------------------------------------------------------------------------


class Alert(Base):
    """一条预警。spec §4.6 的字段清单 + 两列本计划的工程决定。

    | spec §4.6 原文                              | 本表的列              |
    | =========================================== | ===================== |
    | id                                          | ``id``                |
    | student_id（班级级预警为 course_section_id）| ``student_id`` / ``course_section_id`` |
    | 级别 ∈ {red, yellow, green}                 | ``level`` + CHECK     |
    | 规则 ID                                     | ``rule_id``           |
    | **触发数据快照 JSON**                       | ``trigger_snapshot``  |
    | 触发时间                                    | ``triggered_at``      |
    | 状态 ∈ {pending, handled, ignored}          | ``status`` + CHECK    |
    | 教师处理动作                                | ``handled_action``    |
    | 处理时间                                    | ``handled_at``        |

    spec 没有、本计划补的三列：``semester_id``（去重键的一部分：没有它，
    「上学期处理过、这学期又触发」会插不进去）、``window_key``（触发窗口标识）、
    ``subject_key``（去重键的主语位）。**三列的完整理由见模块 docstring 的那一段**；
    ``window_key`` 与 ``subject_key`` 要登记 spec §14。

    **``status`` NOT NULL 且无缺省**（照 :class:`.prescription.Prescription` 的
    ``status``，与 :class:`.ops.DailySyncRun` 的 ``default="failed"`` 相反）：
    预警在 INSERT 那一刻就已经知道自己是 ``pending``，给一个缺省只会让「忘了写状态」
    静默变成「这条还没人处理」。

    ``handled_action`` 用 :class:`Text` 而不是 ``String(n)``：它是给人看的自由文本
    （教师写「已与家长沟通，本周减量」），照 ``cleaning_log.reason`` 的既有口径。
    """

    __tablename__ = "alert"

    #: 三级预警（spec §4.6）。最长者 ``"yellow"`` 是 6 字符，``String(8)`` 余量 2。
    LEVELS: set[str] = {"red", "yellow", "green"}
    #: 处置状态。``handled`` / ``ignored`` 让教师处置过的预警**留在库里当痕迹**，
    #: 而不是被删掉——删掉之后「这一条为什么没有再触发」就无从回答
    #: （Review Focus 第 3 条）。最长者 ``"pending"`` / ``"ignored"`` 是 7 字符，
    #: ``String(8)`` 余量 1。
    STATUSES: set[str] = {"pending", "handled", "ignored"}

    id: Mapped[int] = mapped_column(primary_key=True)
    #: **学生级预警**填它，班级级预警为 ``NULL``。可空的外键——⚠️ 计划正文原本要把
    #: 本列改成 ``nullable=False`` + 用 ``0`` 作哨兵，那会当场撞外键
    #: （父表里没有 ``id = 0`` 的行），反证是
    #: ``tests/db/test_models.py::test_alert_subject_sentinel_zero_would_violate_the_fk``。
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))
    #: **班级级预警**填它（spec §4.6 逐字「student_id（班级级预警为 course_section_id）」），
    #: 学生级预警为 ``NULL``。可空的理由同上。
    course_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_section.id")
    )
    #: 去重键的一部分：同一条规则在**不同学期**再触发是一条新预警。
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    #: 去重键的**主语位**：学生级 ``student:<id>``、班级级 ``section:<id>``。
    #: ⚠️ 算式的唯一所有者是 Task 6 的 :mod:`app.domain.alerts`，本模块**不声明**
    #: 前缀常量（那会是第二个所有者，而 domain 层按 Global Constraints 不得 import
    #: ``app.db``，故它拿不到这里的常量）。
    #: 存在的理由：SQLite 的 UNIQUE 对 NULL 是「NULL ≠ NULL」，上面那两个可空外键
    #: 进不了去重键，否则约束对班级级预警**静默失效**（模块 docstring 的那一段）。
    subject_key: Mapped[str] = mapped_column(String(24))
    level: Mapped[str] = mapped_column(String(8))
    #: 规则 ID，取值域的唯一所有者是 ``backend/data/alert_rules.yaml``（Task 6 落地）。
    #: spec §8.2 今天最长的是 ``YELLOW_CLASS_RPE_HIGH``（21 字符），``String(32)`` 余量 11。
    rule_id: Mapped[str] = mapped_column(String(32))
    #: **触发数据快照**：规则求值当时读到的那几个数（例如
    #: ``{"streak": 3, "rpe": [9, 9, 10]}``）。走 :class:`JsonText`。
    #: 有它，「这条预警为什么触发」才能离线复核，而不必重放整个管道。
    trigger_snapshot: Mapped[dict] = mapped_column(JsonText)
    triggered_at: Mapped[dt.datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(8))
    handled_action: Mapped[str | None] = mapped_column(Text)
    handled_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    #: 指向 ``daily_sync_run``：Task 8 会把 ``Alert`` 接进 ``_replay_cleanup``。
    #: ⚠️ ``notification.alert_id`` 带 ``ON DELETE SET NULL``，正是为了让那一步
    #: 不会连带删掉已经推出去的通知、也不会当场 FK 违例（见 :class:`Notification`）。
    batch_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"), index=True)
    #: **触发窗口标识**（spec §4.6 没有这一列，本计划的工程决定 → 登记 spec §14）。
    #: 五种取值算式归 Task 6 的 :mod:`app.domain.alerts`：``RED_RPE_SUSTAINED`` 用
    #: 「第 3 次快评的 ``class_session_id``」、``RED_MINITEST_DROP`` 用「第 3 个小测的
    #: ``mini_test.id``」、``YELLOW_CHECKIN_GAP`` 用「中断结束日的 ISO 串」、
    #: ``YELLOW_CLASS_RPE_HIGH`` 与 ``GREEN_MASTERY`` 用 ``semester_id:week``。
    #: 于是「同一次触发只有一条 alert」由 DB 保证，而「下一轮再触发」是一条新行。
    window_key: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        # 四列全 NOT NULL，故 UNIQUE 对学生级与班级级**都真的生效**（模块 docstring）。
        UniqueConstraint(
            "rule_id",
            "subject_key",
            "semester_id",
            "window_key",
            name="uq_alert_rule_subject_semester_window",
        ),
        _in_domain("level", LEVELS, "ck_alert_level"),
        _in_domain("status", STATUSES, "ck_alert_status"),
        # 两个作用域列**恰好一个**非空。这是 ``subject_key`` 那套设计的前提：
        # 两个都填 = 一条有两个主语的预警（去重键于是含歧义），
        # 两个都不填 = 一条**谁都不属于**的预警（大屏上永远查不到它）。
        # 两种都是静默的，故交给 DB。`<>` 在 SQLite / PostgreSQL / MySQL 上对
        # 布尔表达式都成立（IS NULL 求值成 0/1）。
        # ⚠️ 它**守不住**「``subject_key`` 与非空的那一列一致」：那需要把前缀词表
        # 在 SQL 里再拼一次，而前缀的唯一所有者是 :mod:`app.domain.alerts`。
        CheckConstraint(
            "(student_id IS NULL) <> (course_section_id IS NULL)",
            name="ck_alert_subject_is_exactly_one",
        ),
    )


class Notification(Base):
    """一条消息（spec §4.6 / §8.3）。原型只做 ``in_app`` 这一档。

    | spec §4.6 原文          | 本表的列                              |
    | ======================= | ===================================== |
    | id                      | ``id``                                |
    | 接收者                  | ``recipient_kind`` + ``recipient_id`` |
    | 通道                    | ``channel`` + CHECK                   |
    | 标题                    | ``title``                             |
    | 正文                    | ``body``                              |
    | 关联 alert/prescription | ``alert_id`` / ``prescription_id``    |
    | 已读标记                | ``is_read``                           |
    | 创建时间                | ``created_at``                        |

    **刻意不带 ``batch_id``**：消息是**已经推给某个人**的东西，重放那天按批删掉它，
    学生端消息中心的红点会凭空消失，而他不知道自己收到过什么。
    于是它与 ``alert`` 的关系只能是「父行被删、子行留下并断开关联」，
    这就是下面两个外键都带 ``ON DELETE SET NULL`` 的由来。

    **``recipient_id`` 不是外键**：它是多态的（``recipient_kind = "student"`` 时指
    ``student.id``、``"teacher"`` 时指 ``teacher.id``），而 SQLite 没有跨两张父表的
    外键写法。代价是「删学生不会带走他的通知」，已登记为关切。
    ``recipient_kind`` + ``recipient_id`` 两列合起来才是 spec 那一格「接收者」。

    ``title`` / ``body`` 都用 :class:`Text`：它们是给人看的自由文本，
    没有封闭取值域，给一个 ``String(n)`` 就是凭空造一个列宽口径
    （照 ``cleaning_log.reason`` / ``weekly_adjustment.reason`` 的既有处置）。
    """

    __tablename__ = "notification"

    #: 接收者的两类。最长者 ``"teacher"`` 是 7 字符，``String(8)`` 余量 1。
    RECIPIENT_KINDS: set[str] = {"student", "teacher"}
    #: spec §8.3 的 ``NotificationChannel`` 三实现。**本计划只做 ``in_app``**，
    #: 另两个值今天没有写入方——与 ``WeeklyAdjustment.SOURCES`` 的 ``"auto"``
    #: 同一条理由：届时往一个已结案的 CHECK 里加值等于重建库（本仓不做迁移）。
    #: ⚠️ 最长者 ``"wechat_subscribe"`` 是 **16** 字符，``String(16)`` **余量 0**：
    #: 换更长的通道名（例如 ``"wechat_work_app"`` 之外的任何东西）之前必须先抬列宽，
    #: 而 SQLite 不强制长度、故溢出在本仓的测试里永远不报错（Ruling 144 的形状）。
    CHANNELS: set[str] = {"in_app", "wechat_subscribe", "sms"}

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_kind: Mapped[str] = mapped_column(String(8))
    recipient_id: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    #: ⚠️ ``ON DELETE SET NULL`` 是承重的（计划正文的显式决定）：Task 8 会把 ``Alert``
    #: 加进 ``_replay_cleanup``，而本表**不带** ``batch_id``、不进那份清单。
    #: 普通外键会让重放当场 ``FOREIGN KEY constraint failed``、整批回滚；
    #: ``CASCADE`` 则会连带删掉已经推出去的消息。``SET NULL`` 是唯一同时满足
    #: 「重放不炸」与「消息不丢」的那一档。
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert.id", ondelete="SET NULL")
    )
    #: ⚠️ 同样带 ``ON DELETE SET NULL``，而**计划正文只点了 ``alert_id``**（顶回 #3）：
    #: ``prescription`` **今天就已经在** ``_replay_cleanup`` 的清单里（Plan 02 Task 7，
    #: P7-A4），故「重放那天删掉处方」不是 Task 8 才会发生的事、是现在每天都在发生的事。
    #: 少了 ``SET NULL``，第一条指向处方的通知一落库，下一次重放同一天就会炸在
    #: ``delete_by_batch(session, Prescription, …)`` 上——而 Plan 02 的既有测试全绿，
    #: 因为它们一条 ``notification`` 都不写。
    #: 代价：断开关联的通知再也点不回原处方，前端应把 ``prescription_id IS NULL``
    #: 渲染成不可点的纯文本。
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescription.id", ondelete="SET NULL")
    )
    #: 已读标记。NOT NULL + 缺省 ``False``：红点与消息中心都读它，而「没写」与「未读」
    #: 对前端是同一件事（与 :class:`.ops.DailySyncRun` 计数列 ``default=0`` 同一条理由）。
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)

    __table_args__ = (
        _in_domain("recipient_kind", RECIPIENT_KINDS, "ck_notification_recipient_kind"),
        _in_domain("channel", CHANNELS, "ck_notification_channel"),
    )


# ---------------------------------------------------------------------------
# spec §4.7 班级周报（⚠️ 住在本模块而不是 ops.py，理由见模块 docstring）
# ---------------------------------------------------------------------------


class WeeklyClassReport(Base):
    """一个教学班一周的周报，spec §4.7 / §8.5。

    | spec §4.7 原文           | 本表的列                |
    | ======================== | ======================= |
    | id                       | ``id``                  |
    | course_section_id        | ``course_section_id``   |
    | semester_id              | ``semester_id``         |
    | 周次                     | ``week``                |
    | 分层分布及环比流动       | ``layer_distribution``  |
    | 人均 RPE 与上周对比      | ``rpe_summary``         |
    | 按层分组打卡完成率       | ``checkin_rate_by_layer`` |
    | 进步榜/退步名单 JSON     | ``progress_board``      |
    | 预警汇总                 | ``alert_summary``       |
    | 算法建议                 | ``suggestion``          |
    | 生成时间                 | ``generated_at``        |

    另有一列 spec §4.7 没有的 ``batch_id``（模块 docstring 的那一段）。

    **5 个聚合列全部是 :class:`JsonText`**（本模块 7 个 ``JsonText`` 列里的 5 个）：
    它们的形状由 Task 9 的 ``report_stage`` 定，而现在定不下——「环比流动」要几个键、
    「进步榜」取前几名，都要等生成器写出来才知道。做成 5 个标量列会把一个还没定的
    形状提前钉进 DDL，而本仓不做迁移（改一次就是重建库）。第 6 列 ``suggestion``
    是**自由文本**（给人看的一句话），故用 :class:`Text`、不是 JSON。

    ``(course_section_id, semester_id, week)`` 唯一：一个班一周只有一份。
    同一周两份会让「环比流动」与「人均 RPE 与上周对比」有两个互相矛盾的基准，
    而教师大屏读的是「最新那一份」——哪一份生效于是取决于 ``id`` 的先后。
    """

    __tablename__ = "weekly_class_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_section_id: Mapped[int] = mapped_column(ForeignKey("course_section.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
    #: 学期周次（1-based，与 ``mini_test.week`` / ``weekly_adjustment.week`` 同口径）。
    week: Mapped[int] = mapped_column(Integer)
    layer_distribution: Mapped[dict] = mapped_column(JsonText)
    rpe_summary: Mapped[dict] = mapped_column(JsonText)
    checkin_rate_by_layer: Mapped[dict] = mapped_column(JsonText)
    progress_board: Mapped[dict] = mapped_column(JsonText)
    alert_summary: Mapped[dict] = mapped_column(JsonText)
    suggestion: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime)
    #: 指向 ``daily_sync_run``：周报是管道产物（spec §5 第 9 阶段），重放那天要能按批删。
    #: 没有子表指着本表，故 Task 8/9 把它接进 ``_replay_cleanup`` 没有
    #: ``class_session`` 那个问题。
    batch_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"), index=True)

    __table_args__ = (
        UniqueConstraint(
            "course_section_id",
            "semester_id",
            "week",
            name="uq_weekly_class_report_section_semester_week",
        ),
    )
