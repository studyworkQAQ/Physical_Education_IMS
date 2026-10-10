"""spec §8.2 的五条预警规则（Plan 03 Task 6）。

三级预警是「学生练得太苦 → 系统推减量 20%」这条闭环的**闸门**：教师处理一条 ``red``
预警时，Task 7 的 ``alert_stage`` 会往 ``weekly_adjustment`` 写一条 ``source="auto"``、
``factor=0.8`` 的行（spec §8.4）。故本模块的每一个比较符都直接决定**谁被减量**——
而这类错误在端到端测试里看不出来（少触发一条预警，500 人的分布测试只动几个百分点），
账本 Ruling 1 因此把本 Task 定为全计划**唯一**要求做变异测试的地方。

**它是纯函数、不做 I/O**（Global Constraint #1）：阈值由 ``alert_rules.yaml`` 经
:mod:`app.refdata_alerts` 加载成 :class:`AlertRules` 后**作为参数传入**，id / 周次 /
日期串全部由调用方注入。本模块不读盘、不读时钟、不掷随机数，也不 import
``sqlalchemy`` / ``yaml`` / ``datetime``。于是「同一份输入 → 同一个结果」成立，且
:mod:`tests.architecture.test_domain_purity` 的三条守卫能机器可查地钉住这件事。

--------------------------------------------------------------------------

**五条规则与它们的作用域**（spec §8.2 的表；``RuleId`` 的声明序 == 表格行序）：

=========================  ======  ========  =========================================
规则                        级别    作用域    判据
=========================  ======  ========  =========================================
``RED_MINITEST_DROP``       red     student   连续 ``consecutive`` 次二次小测下降，每次
                                              严格 ``< 上一次 × (1 - drop_pct)``，
                                              需 ``points_needed`` 个数据点
``RED_RPE_SUSTAINED``       red     student   ``rpe_streak >= streak``
``YELLOW_CHECKIN_GAP``      yellow  student   ``checkin_gap_days >= gap_days``
``YELLOW_CLASS_RPE_HIGH``   yellow  class     ``mean_rpe > mean_rpe_max``（**严格**）
``GREEN_MASTERY``           green   student   ``completion_rate >= completion_rate_min``
                                              **且** ``mini_test_improved``
=========================  ======  ========  =========================================

阈值一个都不写在本模块里（Global Constraint #3：唯一所有者是
``backend/data/alert_rules.yaml``）。:func:`tests.domain.test_alerts.test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module`
换一套参数再跑一遍，于是「把 9 / 3 / 2 / 7.0 / 0.95 / 1.0 硬编码进来」每一条都红。

⚠️ **两个阈值在 domain 里不被读**（硬规矩 #39：写下能力就写明守不住什么）：

* ``rpe_min``（``9``）——``rpe_streak`` 的定义是「最近连续若干次 ``rpe >= rpe_min``」，
  而**算那个 streak 的是 Task 7 的 ``alert_stage``**（它才读得到 ``rpe_record`` 表）。
  domain 拿到的是**已经算好的** streak，故它无从校验这个阈值被用对了。
* ``improve_pct``（``0.03``）——spec §8.2 口径表 #4 逐字「任一指标改善 ≥ **3%**」，
  而判定发生在 Task 7 算 ``mini_test_improved`` 的时候（它才读得到两次 ``mini_test``）。
  ⚠️ 与下降阈值 5% **刻意不对称**（口径表原文：「正向激励应更宽松」）。

两个都仍然原样进 :attr:`StudentHit.snapshot`，于是「这条预警当时按哪一版阈值判的」
可以离线复核，而不必重放整个管道。**它们不是死配置**，但它们的消费者在 domain 之外。

--------------------------------------------------------------------------

**``window_key`` 与 ``subject_key`` 是 ``alert`` 表去重键的两半**，两者的算式都住在
本模块（``app/db/models/feedback.py`` 的 :class:`~app.db.models.feedback.Alert` 逐字
写明「算式的唯一所有者是 Task 6 的 :mod:`app.domain.alerts`」，
``app/api/schemas/alerts.py`` 与 ``tests/db/test_models.py`` 各复述了一次）。
DB 侧的约束是 ``UniqueConstraint("rule_id", "subject_key", "semester_id", "window_key")``，
四列全 NOT NULL。

⚠️ **``window_key`` 的取值算式承载着 Review Focus 第 3 条**：同一条
``RED_RPE_SUSTAINED`` 在连续第 3、4、5 次快评都满足条件时，若键取的是**最后一次**的
``class_session_id``，三次触发就会得到三个不同的键、插进三行 ``alert``、推三次
「减量 20%」，训练量被连乘成 ``0.8³ = 0.512``——而全链路没有一处报错。故算式取的是
**凑满 ``streak`` 那一次**的 id（``rpe_session_ids[streak - 1]``），streak 再长键也不变。

⚠️ **``RED_MINITEST_DROP`` 刻意用另一套口径**（``mini_test_ids[-1]``，随最后一次小测
前进）：小测不是每堂课都有的，一次新小测是一次**新的观测窗口**；而快评每堂课都有，
锚在最后一次会让键天天变。

**为什么把 id 放进 domain、而不是让 Task 7 在 I/O 层拼这两个键**（P6-A1 的裁定）：
放在 domain 里它们是纯函数、能被单元测试穷举；放在 ``alert_stage`` 里它们只能靠集成
测试撞。这与 Plan 02 的 Ruling 96（「值类型住 domain、加载器住 domain 外」）是同一条纪律。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**：:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES`
实测 = ``{collections, collections.abc, dataclasses, enum, numpy, typing}``，
``datetime`` 不在其中。故 ``YELLOW_CHECKIN_GAP`` 的 ``window_key`` 要的那个 ISO 日期串
由**调用方注入**（:attr:`StudentSignals.checkin_gap_end`），domain 既不调
``date.isoformat()`` 也不写 ``dt.date`` 这样的标注（P6-A4 的裁定）。
本模块连一个日期字段都没有，故 :mod:`app.domain.prescription.intensity` 那套
「标注写成前向引用字符串」的做法在这里也用不上。

⚠️ **计划正文的字段清单带不出这两个键**，实现者顶回后补了 4 个字段（P6-A1 只补了其中
两个 id 元组）：

* ``StudentSignals.semester_id`` / ``week`` —— ``GREEN_MASTERY`` 是 **student** 作用域
  （``alert_rules.yaml`` 逐字 ``scope: student``），而它的 ``window_key`` 是
  ``semester_id:week``；P6-A1 只给 ``ClassSignals`` 补了这两个字段。
* ``StudentSignals.checkin_gap_end`` —— ``YELLOW_CHECKIN_GAP`` 的 ``window_key`` 是
  ``gap<中断结束日的 ISO 串>``，而原清单里**一个日期字段都没有**。
* ``StudentSignals.student_id`` / ``ClassSignals.course_section_id`` ——
  ``subject_key`` 要它们，而原清单里也没有（见上面那一段：三处已落地的代码都把
  ``subject_key`` 的所有者钉在本模块）。

判据是硬规矩 #110：**定义一个纯函数的输出结构时，逐字段回问「这个值从哪个入参来」**。
逐个键回问一遍，缺的四个字段就自己浮出来了。

--------------------------------------------------------------------------

**「判不了」与「没问题」是两件事**（Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）。
三条规则的输入可以是 ``None``／点数不足：

* ``RED_MINITEST_DROP``：数据点少于 ``points_needed``；
* ``YELLOW_CLASS_RPE_HIGH``：``mean_rpe is None``（本周一次快评都没有）；
* ``GREEN_MASTERY``：``completion_rate is None``。

三档一律**不触发**，但必须在 :func:`student_skip_traces` / :func:`class_skip_traces`
的返回值里留痕。⚠️ **留痕不能只写在散文里**：``points_needed`` 是 YAML 的一个参数，
「够不够点」这个判断因此必须在 domain——否则 Task 7 得再读一次那个阈值，那就是第二个
所有者。实现上，每个求值器返回 ``(命中, 留痕)`` 两个可空值，于是「什么时候判不了」
这件事在**一处**决定，:func:`evaluate_student` 取前半、:func:`student_skip_traces`
取后半，两者不可能漂。

⚠️ **留痕的消费者是 Task 7**（硬规矩 #39）：本模块只负责**算出**它。落库时把它记进
``daily_sync_run`` 的计数或一条 ``warning`` 日志是 ``alert_stage`` 的职责；没人消费的话
「这个学生这周为什么没有预警」仍然无从回答。
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "AlertLevel",
    "RuleId",
    "AlertScope",
    "SUBJECT_PREFIX_STUDENT",
    "SUBJECT_PREFIX_SECTION",
    "AlertRule",
    "AlertRules",
    "StudentSignals",
    "ClassSignals",
    "StudentHit",
    "ClassHit",
    "evaluate_student",
    "evaluate_class",
    "student_skip_traces",
    "class_skip_traces",
    "declared_scope",
]


class AlertLevel(str, Enum):
    """三级预警（spec §4.6 / §8.2 的「级别」列）。**本枚举是那三个字符串的唯一所有者。**

    ``app.db.models.feedback.Alert.LEVELS`` 是它的 **DB 镜像**（``_in_domain`` 用它生成
    ``ck_alert_level``）。⚠️ 本 Task **刻意不去改** ``Alert.LEVELS`` 让它反过来引用本枚举：
    domain 层按 Global Constraint #1 不得 import ``app.db``，而 DB 侧引 domain 会让
    ``models`` 从此依赖一个纯函数叶子（``Exercise.IMPACT_LEVELS`` 的注释里写着同一条理由）。
    故两份**并存**，由
    :func:`tests.domain.test_alerts.test_alert_level_is_the_owner_and_the_db_check_domain_is_its_mirror`
    钉成逐字相等。

    **继承 ``str``** 的理由与 :class:`app.domain.prescription.triggers.TriggerReason`
    相同：``alert.level`` 是普通字符串列，而 ``trigger_snapshot`` 是 ``JsonText`` 列，
    继承 ``str`` 之后 ``json.dumps`` 直接接受它，不必在 ORM 边界上处处翻译。
    """

    #: 红：需要教师介入（处理它会推「减量 20%」，spec §8.4）。
    RED = "red"
    #: 黄：需要教师关注。
    YELLOW = "yellow"
    #: 绿：正向激励（**不**改训练量）。
    GREEN = "green"


class RuleId(str, Enum):
    """spec §8.2 表格的 5 行。**声明序 == 表格行序**，且它是承重的。

    :func:`evaluate_student` / :func:`evaluate_class` 按声明序排返回的 tuple，
    Task 7 按同一个序落库、教师端按同一个序渲染。⚠️ 成员名与 ``.value`` **逐字相同**：
    ``alert.rule_id`` 那一列（``String(32)``）存的就是那个大写串，最长者
    ``YELLOW_CLASS_RPE_HIGH`` 是 21 字符、余量 11。

    ⚠️ **取值域的另一半所有者是 ``alert_rules.yaml`` 的 ``rules:`` 键集**：
    :func:`app.refdata_alerts.load_alert_rules` 要求两者**恰好相等**——多一个键
    （专家加了新规则忘了改代码）与少一个键都响亮失败。静默忽略多出来的那一个，
    会让那条新规则**永远不生效**，而 YAML 看起来完全正常、评审也过了。
    """

    #: ① 连续两次二次小测下降 ≥ 5%（需 3 个数据点）。
    RED_MINITEST_DROP = "RED_MINITEST_DROP"
    #: ② RPE 连续 ≥ 9 分（连续 3 次课堂快评）。
    RED_RPE_SUSTAINED = "RED_RPE_SUSTAINED"
    #: ③ 打卡中断 2 天（连续 2 个**应打卡训练日**，休息日不计入）。
    YELLOW_CHECKIN_GAP = "YELLOW_CHECKIN_GAP"
    #: ④ 课堂 RPE 均值 > 7 分（**班级**作用域）。
    YELLOW_CLASS_RPE_HIGH = "YELLOW_CLASS_RPE_HIGH"
    #: ⑤ 本周完成度 100% **AND** 二次小测提升（任一指标改善 ≥ 3%）。
    GREEN_MASTERY = "GREEN_MASTERY"


class AlertScope(str, Enum):
    """spec §8.2 的「作用域」列：一条规则的主语是**一个学生**还是**一个教学班**。

    ⚠️ 它决定的是「哪一套求值器处理这条规则」——班级级规则拿不到
    :class:`StudentSignals`（它没有 ``mean_rpe``），学生级规则拿不到
    :class:`ClassSignals`。故**代码侧的分区**（:func:`declared_scope`）与
    **YAML 侧的 ``scope``** 必须一致，由
    :func:`app.refdata_alerts.load_alert_rules` 在加载期对账；
    没有那道对账，专家把 YAML 里的 ``scope`` 一翻就是一件**什么也不发生**的事。
    """

    #: 主语是一个学生（``alert.student_id`` 非空）。
    STUDENT = "student"
    #: 主语是一个教学班（``alert.course_section_id`` 非空）。
    CLASS = "class"


#: ``alert.subject_key`` 的**学生级**前缀（``student:<student.id>``）。
#:
#: **为什么需要这一列**（``app/db/models/feedback.py`` 模块 docstring 的那一段）：
#: SQLite 的 ``UNIQUE`` 对 NULL 是「NULL ≠ NULL」，而 ``student_id`` 与
#: ``course_section_id`` 是**两个可空外键**（spec §4.6 逐字「student_id（班级级预警为
#: course_section_id）」），进不了去重键——否则那条 ``UniqueConstraint`` 对班级级预警
#: **静默失效**。故加一个 NOT NULL 的归一化主语位。
#:
#: ⚠️ **本常量与 :data:`SUBJECT_PREFIX_SECTION` 是那两个前缀串的唯一所有者**：
#: ``app/api/schemas/alerts.py`` 逐字写着「前端不要自己拼它，也不要解析它」，
#: ``tests/db/test_models.py`` 的 ``_alert_fields`` 刻意按字面形状现拼
#: （``f"student:{stu.id}"``）而不 import 本常量——两侧同源的话前缀写错也全绿
#: （硬规矩 #35）。
SUBJECT_PREFIX_STUDENT = "student"

#: ``alert.subject_key`` 的**班级级**前缀（``section:<course_section.id>``）。
#: ⚠️ 是 ``section`` 而不是 ``course_section``：``subject_key`` 是 ``String(24)``，
#: 最长形状 ``course_section:2147483647`` 是 **25** 字符、**超宽 1**；
#: ``section:2147483647`` 是 18 字符、余量 6（``tests/db/test_models.py`` 钉的正是这一个数）。
#: ⚠️ **本处此前印的是「27 字符、超宽 3」，两个数都错**（Plan 03 Task 9 实测更正：
#: ``len("course_section:") == 15`` + ``len("2147483647") == 10`` = **25**，
#: 而列宽 24，故超宽 **1**）。⚠️ **结论不变、前缀仍必须是 ``section``**——超宽 1 与超宽 3
#: 在 SQLite 上都不报错（它不强制 ``VARCHAR`` 长度），而换到 MySQL 会**静默截断**，
#: 截断后的 ``subject_key`` 会让去重键指向另一个主语。错的只是报告里的那两个数。
SUBJECT_PREFIX_SECTION = "section"


@dataclass(frozen=True)
class AlertRule:
    """一条规则：它的身份（``rule_id``）、两个 spec §8.2 的列、与它的阈值。

    ``params`` 的键集**逐规则不同**（``RED_RPE_SUSTAINED`` 是 ``rpe_min`` / ``streak``，
    ``GREEN_MASTERY`` 是 ``completion_rate_min`` / ``improve_pct``），故它是一个自由映射
    而不是固定字段的 dataclass：加一个阈值不该改本模块。键集的**唯一所有者**是
    :data:`app.refdata_alerts._PARAM_TYPES`（加载器按它校验「恰好这几个键」）。

    ⚠️ ``params`` 的值是 ``int`` 与 ``float`` 的混合，这是**承重的**：计数类
    （``streak`` / ``consecutive`` / ``points_needed`` / ``gap_days``）必须是 ``int``，
    因为 ``streak`` 要被当成**下标**用（``window_key`` 取
    ``rpe_session_ids[streak - 1]``），一个 ``2.0`` 会在那一步抛
    ``TypeError: list indices must be integers``；测量值与比率类一律归一成 ``float``
    （口径同 :func:`app.refdata_yaml.as_float` 的 docstring）。
    """

    rule_id: RuleId
    level: AlertLevel
    scope: AlertScope
    params: Mapping[str, float | int]


@dataclass(frozen=True)
class AlertRules:
    """一份 ``alert_rules.yaml``：版本号 + 「``RuleId`` → :class:`AlertRule`」的只读映射。

    ``version`` 是 spec §4.4 要求的「静态 YAML + **版本号**」的那一半：Task 7 把它写进
    **``alert.trigger_snapshot["alert_rules_version"]``**，于是一条已经触发过的预警
    能回答「当时是按哪一版阈值判的」。
    ⚠️⚠️ **本处此前印的是「写进 ``weekly_adjustment`` 的 ``auto`` 来源留痕」，那句是错的**
    （Plan 03 Task 7 的顶回 4）：``weekly_adjustment.reason`` 那一列**刻意不带版本号**，
    因为它是 ``UniqueConstraint("prescription_id", "week", "reason", "source")``
    的一列——把版本号拼进去等于「**升一次版本号 = 同一周可以再减一次量**」→
    ``0.8 × 0.8 = 0.64``，而教师只以为自己减了一次（Review Focus 第 3 条要挡的正是它）。
    ``trigger_snapshot`` 是一个 ``JsonText`` 列、**不进去重键**，故版本号落在那里
    既可离线复核、又不影响去重。写入点是
    :func:`app.pipeline.alert_stage.evaluate_alerts` 里 ``_persist`` 的那一行
    ``snapshot = {**hit.snapshot, "alert_rules_version": rules.version, **extra}``。⚠️ **它必须是 ``str``**——YAML 里不加引号的 ``1.0`` 会被
    PyYAML 解析成 ``float``，而 ``1.10`` 会变成 ``1.1``（Plan 02 Task 3 踩过，
    18 份模板因此一律加引号），加载器两侧都校。
    """

    version: str
    rules: Mapping[RuleId, AlertRule]

    def params_of(self, rule_id: RuleId) -> Mapping[str, float | int]:
        """那一条规则的阈值映射（调用方读阈值时的便捷入口）。

        ⚠️ **本模块内部的 5 个求值器不走它**：它们收的是整个 :class:`AlertRule`
        （判据要 ``params``，命中要 ``level``，两者必须来自同一行配置，分开取就有了
        「读到两条不同规则的阈值与级别」的可能）。本方法是给 Task 7 的
        （它落库时要把阈值写进 ``trigger_snapshot`` 之外的地方，例如周报的口径说明）。
        """
        return self.rules[rule_id].params


@dataclass(frozen=True)
class StudentSignals:
    """**一个学生在某一周**的全部输入。字段名与顺序见下表（11 个，运行时口径由
    :func:`tests.domain.test_alerts.test_the_signal_dataclasses_have_exactly_the_fields_the_rules_need`
    钉住）。

    ==========================  ==========================================================
    字段                        谁读它
    ==========================  ==========================================================
    ``student_id``              ``subject_key``
    ``semester_id`` / ``week``  ``GREEN_MASTERY`` 的 ``window_key``
    ``rpe_streak``              ``RED_RPE_SUSTAINED`` 的判据
    ``rpe_session_ids``         ``RED_RPE_SUSTAINED`` 的 ``window_key``
    ``mini_test_scores``        ``RED_MINITEST_DROP`` 的判据
    ``mini_test_ids``           ``RED_MINITEST_DROP`` 的 ``window_key``
    ``checkin_gap_days``        ``YELLOW_CHECKIN_GAP`` 的判据
    ``checkin_gap_end``         ``YELLOW_CHECKIN_GAP`` 的 ``window_key``
    ``completion_rate``         ``GREEN_MASTERY`` 的判据
    ``mini_test_improved``      ``GREEN_MASTERY`` 的判据
    ==========================  ==========================================================

    ⚠️ **一个字段都不多**（硬规矩 #110 的反向：一个没有消费者的入参就是一个会被下一个人
    误当成判据的东西）。三个 ``id`` 类字段与一个日期串是 P6-A1 + 实现者顶回补进来的，
    理由见模块 docstring 那一段。

    * ``rpe_streak`` —— **当前**连续 ``rpe >= rpe_min`` 的次数（``rpe_min`` 由 Task 7 消费，
      见模块 docstring）。
    * ``rpe_session_ids`` —— 与 ``rpe_streak`` **平行**：那 ``rpe_streak`` 次快评各自的
      ``class_session_id``，**按时间升序**（最早在前）。``window_key`` 取
      ``[streak - 1]``，即**凑满阈值那一次**，理由见模块 docstring。
    * ``mini_test_scores`` —— 按周次**升序**的最近若干个二次小测分。
    * ``mini_test_ids`` —— 与 ``mini_test_scores`` **同序等长**。
    * ``checkin_gap_days`` —— 连续未打卡的**应打卡训练日**数（休息日不计入中断，
      spec §8.2 口径表 #3）。⚠️ **「什么是训练日」由 Task 7 按处方算好再传进来**，
      domain 不知道——这是 spec §8.1 折中方案（打卡完成率按处方训练日计）的直接后果。
    * ``checkin_gap_end`` —— 那段中断的**结束日**的 ISO 8601 串（``YYYY-MM-DD``），
      由调用方算好注入（domain import 不到 ``datetime``，见模块 docstring）。
    * ``completion_rate`` —— 本周完成率，``[0, 1]`` 的比率；``None`` = **判不了**
      （本周没有应打卡训练日，或采集缺失），不是 0。
    * ``mini_test_improved`` —— 「任一指标改善 ≥ ``improve_pct``」，由 Task 7 算好。
    """

    student_id: int
    semester_id: int
    week: int
    rpe_streak: int
    rpe_session_ids: tuple[int, ...]
    mini_test_scores: tuple[float, ...]
    mini_test_ids: tuple[int, ...]
    checkin_gap_days: int
    checkin_gap_end: str
    completion_rate: float | None
    mini_test_improved: bool


@dataclass(frozen=True)
class ClassSignals:
    """**一个教学班在某一周**的全部输入（5 个字段）。

    * ``course_section_id`` —— ``subject_key`` 要它。
    * ``semester_id`` / ``week`` —— ``window_key`` 就是 ``f"{semester_id}:{week}"``
      （一个班一周最多一条班级级预警）。
    * ``mean_rpe`` —— 本周课堂快评的均值；``None`` = **本周一次快评都没有**，
      那一档**不触发 + 留痕**（「没测」不得讲成「测了且没问题」）。
    * ``student_count`` —— ⚠️ **它不是判据**，只进 snapshot：spec §8.2 没有「班上人数
      太少就不报」这一条，编一个下限就是编一条没人评审过的规则。它在快照里的用处是让
      教师能看出「这个 7.8 的均值是 31 个人的还是 2 个人的」。
    """

    course_section_id: int
    semester_id: int
    week: int
    mean_rpe: float | None
    student_count: int


@dataclass(frozen=True)
class StudentHit:
    """一条**学生级**命中。

    ``subject_key`` 与 ``window_key`` 一起构成 ``alert`` 表去重键的两半
    （另两半是 ``rule_id`` 与 ``semester_id``，前者就是 :attr:`rule_id`、后者由 Task 7
    从管道上下文取）。``snapshot`` 落进 ``alert.trigger_snapshot``（``JsonText`` 列）：
    它装的是**本规则读到的每一个信号值 + 它比过的每一个阈值**，于是「这条预警为什么触发」
    可以离线复核，而不必重放整个管道、也不必回去查当时那一版 YAML。

    ⚠️ ``snapshot`` 是一个**普通 ``dict``**、不是只读视图：domain 的 allow-list 不放行
    ``types``，故这里做不出 ``MappingProxyType``（加载器那一侧可以，它对
    ``AlertRules.rules`` 与 ``params`` 都做了）。它每次求值**新建一个**，故两条命中
    不会共享同一个 dict（:func:`tests.domain.test_alerts.test_evaluate_is_deterministic_and_does_not_mutate_its_input`
    钉的就是这件事）；Task 7 往一条的 snapshot 里补键不会连带改掉另一条。
    """

    rule_id: RuleId
    level: AlertLevel
    subject_key: str
    window_key: str
    snapshot: dict


@dataclass(frozen=True)
class ClassHit:
    """一条**班级级**命中。字段与 :class:`StudentHit` 逐字相同，只是主语是教学班。

    ⚠️ **两个类型刻意不合并成一个**：它们的 ``subject_key`` 来自不同的入参
    （``student_id`` vs ``course_section_id``），合并之后「一条命中到底是学生级还是
    班级级」就只能靠读 ``subject_key`` 的前缀来判断——而那正是
    ``app/api/schemas/alerts.py`` 明写「前端不要解析它」的那个串。
    """

    rule_id: RuleId
    level: AlertLevel
    subject_key: str
    window_key: str
    snapshot: dict


#: 一条规则的求值器：收「一个信号 + 那一条规则」，返回 ``(命中, 留痕)`` 两个可空值。
#: ⚠️ **返回一对而不是一个可空值**是「判不了 ≠ 没问题」这条纪律的落地方式：
#: 「什么时候判不了」在每个求值器里只写一次，:func:`evaluate_student` 取前半、
#: :func:`student_skip_traces` 取后半，两者不可能漂（若拆成两套函数各判一次，
#: 阈值 ``points_needed`` 就会被读两遍，而两份判断迟早不一致）。
_Evaluator = Callable[[object, AlertRule], "tuple[object | None, dict | None]"]


def _require_parallel(sig: StudentSignals) -> None:
    """校验 :class:`StudentSignals` 的两个「平行/同序」契约（P6-A1 的裁定）。

    ``window_key`` 要按**下标**取那两个 id 元组，故长度不对时朴素实现会抛 ``IndexError``
    ——它点不出是哪个字段不对、也说不出这是**调用方**的契约违例，而报错点在 domain 深处、
    离真因（Task 7 少查了一列）隔三层。故改成响亮的 ``ValueError``。

    ⚠️ 它**守不住顺序**（硬规矩 #39）：``rpe_session_ids`` 必须按时间**升序**，
    否则 ``[streak - 1]`` 会锚到错误的那一次快评上——而那件事在 domain 里无从判断
    （domain 拿不到 ``class_session.session_date``）。契约写在
    :class:`StudentSignals` 的 docstring 里，守卫归 Task 7 的 ``alert_stage``。
    """
    if len(sig.rpe_session_ids) != sig.rpe_streak:
        raise ValueError(
            f"StudentSignals 的契约被破坏了：rpe_session_ids 有 "
            f"{len(sig.rpe_session_ids)} 项，而 rpe_streak 是 {sig.rpe_streak}——"
            f"两者必须平行（那 rpe_streak 次快评各自的 class_session_id，按时间升序）。"
            f"RED_RPE_SUSTAINED 的 window_key 要取 rpe_session_ids[streak - 1]，"
            f"长度不对就会锚到错误的那一次触发上，于是「同一次触发只有一条 alert」失效"
        )
    if len(sig.mini_test_ids) != len(sig.mini_test_scores):
        raise ValueError(
            f"StudentSignals 的契约被破坏了：mini_test_ids 有 {len(sig.mini_test_ids)} 项，"
            f"而 mini_test_scores 有 {len(sig.mini_test_scores)} 项——两者必须**同序等长**。"
            f"RED_MINITEST_DROP 的 window_key 要取 mini_test_ids[-1]，"
            f"错位会让去重键指向一个不存在的小测"
        )


def _minitest_drop(
    sig: StudentSignals, rule: AlertRule
) -> "tuple[StudentHit | None, dict | None]":
    """``RED_MINITEST_DROP``：连续 ``consecutive`` 次二次小测下降，每次严格低于上一次的
    ``1 - drop_pct`` 倍；需 ``points_needed`` 个数据点。

    spec §8.2 原文「连续两次二次小测下降 ≥ 5%」，口径表 #2 把它精确成
    「需 **3 个数据点**：``score(t) < score(t-1) × 0.95`` **且**
    ``score(t-1) < score(t-2) × 0.95``。首次可能触发于第 6 周」。

    ⚠️ **严格 ``<``**（与 Plan 01 的 P25、Plan 02 的 ``BODY_FAT_LIMIT`` / ``bmi > 30`` /
    ``muscle < P10`` 同口径）：恰好下降 5.00% **不**算下降。本函数里它写成
    ``newer >= older * factor`` 的**否定式**（提前返回），故变异测试打的是
    ``>=`` → ``>``，那与把 spec 的 ``<`` 改成 ``<=`` 是同一个变异。

    ⚠️ **只看最后 ``consecutive + 1`` 个点**：更早的下降不算数（那已经不是「连续」了），
    而最近一次回升能把它取消。``points_needed == consecutive + 1`` 这个跨参数不变量由
    :func:`app.refdata_alerts.load_alert_rules` 在加载期校验，故本函数**不再校一次**
    ——校两遍就是两个所有者，而它们迟早不一致。
    """
    scores = sig.mini_test_scores
    needed = int(rule.params["points_needed"])
    if len(scores) < needed:
        return None, {"insufficient_points": len(scores), "points_needed": needed}
    consecutive = int(rule.params["consecutive"])
    factor = 1.0 - float(rule.params["drop_pct"])
    tail = scores[-(consecutive + 1):]
    for older, newer in zip(tail, tail[1:]):
        if newer >= older * factor:
            return None, None
    return StudentHit(
        rule_id=rule.rule_id,
        level=rule.level,
        subject_key=f"{SUBJECT_PREFIX_STUDENT}:{sig.student_id}",
        window_key=f"mt{sig.mini_test_ids[-1]}",
        snapshot={"mini_test_scores": list(scores), **rule.params},
    ), None


def _rpe_sustained(
    sig: StudentSignals, rule: AlertRule
) -> "tuple[StudentHit | None, dict | None]":
    """``RED_RPE_SUSTAINED``：``rpe_streak >= streak``（spec §8.2 逐字「RPE 连续 ≥ 9 分」，
    口径表 #1「连续 **3 次**课堂快评」）。

    ⚠️ ``rpe_min``（那个 9）**不在这里被读**：算 streak 的是 Task 7（它才读得到
    ``rpe_record`` 表），domain 拿到的是已经算好的次数。它仍然进 snapshot，理由见
    模块 docstring。

    ⚠️ **``window_key`` 取 ``rpe_session_ids[streak - 1]``，不是 ``[-1]``**——
    那是 Review Focus 第 3 条的全部落点，理由逐字见模块 docstring 那一段。
    """
    needed = int(rule.params["streak"])
    if sig.rpe_streak >= needed:
        return StudentHit(
            rule_id=rule.rule_id,
            level=rule.level,
            subject_key=f"{SUBJECT_PREFIX_STUDENT}:{sig.student_id}",
            window_key=f"rpe{sig.rpe_session_ids[needed - 1]}",
            snapshot={"rpe_streak": sig.rpe_streak, **rule.params},
        ), None
    return None, None


def _checkin_gap(
    sig: StudentSignals, rule: AlertRule
) -> "tuple[StudentHit | None, dict | None]":
    """``YELLOW_CHECKIN_GAP``：``checkin_gap_days >= gap_days``（spec §8.2「打卡中断 2 天」，
    口径表 #3「连续 **2 个应打卡训练日**未打卡，**休息日不计入中断**」）。

    ⚠️ **「什么是应打卡训练日」domain 不知道**：``checkin_gap_days`` 由 Task 7 的
    ``alert_stage`` 按处方训练日算好传进来。这是 spec §8.1 折中方案（打卡完成率按处方
    训练日计）的直接后果，也是本模块唯一一处「判据的语义有一半住在调用方」的地方。
    """
    if sig.checkin_gap_days >= int(rule.params["gap_days"]):
        return StudentHit(
            rule_id=rule.rule_id,
            level=rule.level,
            subject_key=f"{SUBJECT_PREFIX_STUDENT}:{sig.student_id}",
            window_key=f"gap{sig.checkin_gap_end}",
            snapshot={"checkin_gap_days": sig.checkin_gap_days, **rule.params},
        ), None
    return None, None


def _mastery(
    sig: StudentSignals, rule: AlertRule
) -> "tuple[StudentHit | None, dict | None]":
    """``GREEN_MASTERY``：本周完成度 100% **AND** 二次小测提升。

    ⚠️ **判据写 ``>=`` 而不是计划正文的 ``==``**（实现者顶回，三条理由）：

    1. YAML 的参数名逐字是 ``completion_rate_min``——一个叫 ``_min`` 的阈值被 ``==``
       消费是自相矛盾的（它就不是一个 min 了），而下一个人改 YAML 时会以为改它就能改行为；
    2. ``completion_rate`` 是「打卡数 ÷ 应打卡训练日数」，值域 ``[0, 1]``，故
       ``>= 1.0`` 与 ``== 1.0`` 对**任何合法输入**逐格等价——spec 的「100%」没有被放宽；
    3. 写成 ``==`` 会让本 Task 唯一要求的**变异测试没有靶子**：``==`` → ``>=`` 在值域
       ``[0, 1]`` 上不可分辨，任何测试都不会红，而那正是 Ruling 1 要防的形状
       （「一个比较符写错了而 956 条测试全绿」）。

    ⚠️ **它守不住什么**（硬规矩 #39）：第 2 条的等价性依赖「调用方传进来的比率不超过 1」。
    若 Task 7 因为一个 off-by-one 传出 ``1.2``，``>=`` 会触发而 ``==`` 不会。本模块
    **刻意不夹取**（夹取就是把「比率该是多少」这条口径抄进 domain，那是第二个所有者）；
    方向上它也是安全的那一侧——绿牌是正向激励、不改训练量，多给一张绿牌的代价远小于
    多推一次「减量 20%」。

    ``improve_pct``（那个 3%）不在这里被读，理由同 :func:`_rpe_sustained` 的 ``rpe_min``。
    """
    if sig.completion_rate is None:
        return None, {
            "missing": "completion_rate",
            "completion_rate_min": rule.params["completion_rate_min"],
        }
    if (
        sig.completion_rate >= float(rule.params["completion_rate_min"])
        and sig.mini_test_improved
    ):
        return StudentHit(
            rule_id=rule.rule_id,
            level=rule.level,
            subject_key=f"{SUBJECT_PREFIX_STUDENT}:{sig.student_id}",
            window_key=f"{sig.semester_id}:{sig.week}",
            snapshot={
                "completion_rate": sig.completion_rate,
                "mini_test_improved": sig.mini_test_improved,
                **rule.params,
            },
        ), None
    return None, None


def _class_rpe_high(
    sig: ClassSignals, rule: AlertRule
) -> "tuple[ClassHit | None, dict | None]":
    """``YELLOW_CLASS_RPE_HIGH``：课堂 RPE 均值 **> ``mean_rpe_max``**（spec §8.2 逐字
    「> 7 分」，作用域**班级**）。

    ⚠️ **严格 ``>``**：恰好 7.0 **不**触发。这与 ``RED_RPE_SUSTAINED`` 的 ``>=``
    刻意不同，而两处都是照 spec 原文抄的（那一条写「≥ 9」，这一条写「> 7」）——
    不是笔误，也别「统一」它们。

    ``mean_rpe is None`` = 本周一次快评都没有 → **不触发 + 留痕**
    （``insufficient_points: 0``，与 :func:`_minitest_drop` 用同一个键名，于是 Task 7
    汇总留痕时不必按规则分支）。``student_count`` 只进留痕与 snapshot、不是判据。
    """
    if sig.mean_rpe is None:
        return None, {
            "insufficient_points": 0,
            "student_count": sig.student_count,
            "mean_rpe_max": rule.params["mean_rpe_max"],
        }
    if sig.mean_rpe > float(rule.params["mean_rpe_max"]):
        return ClassHit(
            rule_id=rule.rule_id,
            level=rule.level,
            subject_key=f"{SUBJECT_PREFIX_SECTION}:{sig.course_section_id}",
            window_key=f"{sig.semester_id}:{sig.week}",
            snapshot={
                "mean_rpe": sig.mean_rpe,
                "student_count": sig.student_count,
                **rule.params,
            },
        ), None
    return None, None


#: 学生级规则的求值器。**键集就是「哪些规则是 student 作用域」的代码侧所有者**，
#: 由 :func:`declared_scope` 对外声明、由 :func:`app.refdata_alerts.load_alert_rules`
#: 与 YAML 的 ``scope`` 对账。⚠️ 遍历序不靠这两个 dict，而是靠 ``RuleId`` 的声明序
#: （:func:`evaluate_student` 按 ``for rule_id in RuleId`` 走），故 dict 的书写序
#: 不承重。
_STUDENT_EVALUATORS: Mapping[RuleId, _Evaluator] = {
    RuleId.RED_MINITEST_DROP: _minitest_drop,
    RuleId.RED_RPE_SUSTAINED: _rpe_sustained,
    RuleId.YELLOW_CHECKIN_GAP: _checkin_gap,
    RuleId.GREEN_MASTERY: _mastery,
}

#: 班级级规则的求值器，口径同 :data:`_STUDENT_EVALUATORS`。
_CLASS_EVALUATORS: Mapping[RuleId, _Evaluator] = {
    RuleId.YELLOW_CLASS_RPE_HIGH: _class_rpe_high,
}


def evaluate_student(
    sig: StudentSignals, rules: AlertRules
) -> "tuple[StudentHit, ...]":
    """求**全部**学生级规则，返回全部命中者（按 ``RuleId`` 声明序 == spec §8.2 行序）。

    **返回全部命中者、不是第一个**（口径同
    :func:`app.domain.prescription.triggers.evaluate_triggers`）：一个学生可以同时
    「连续三次 RPE 9 分」与「打卡中断 3 天」，而那是**两件事**——教师处理其中一件不会
    让另一件消失，只报第一条会让第二件永远查不到。

    返回**空 tuple** 而不是 ``None``：调用方因此只需一条读法
    （``if evaluate_student(sig, rules):``）。⚠️ 空 tuple 有两种成因——「判过了、都不成立」
    与「判不了」，两者**必须分开**，后者由 :func:`student_skip_traces` 回答。
    """
    _require_parallel(sig)
    hits: list[StudentHit] = []
    for rule_id in RuleId:
        evaluate_one = _STUDENT_EVALUATORS.get(rule_id)
        if evaluate_one is None:
            continue
        hit, _trace = evaluate_one(sig, rules.rules[rule_id])
        if hit is not None:
            hits.append(hit)
    return tuple(hits)


def evaluate_class(sig: ClassSignals, rules: AlertRules) -> "tuple[ClassHit, ...]":
    """求**全部**班级级规则，返回全部命中者（按 ``RuleId`` 声明序）。口径逐字同
    :func:`evaluate_student`。

    ⚠️ **本函数不校验那两个平行元组**（:func:`_require_parallel` 只在学生侧跑）：
    :class:`ClassSignals` 里没有 id 元组，``window_key`` 直接由 ``semester_id`` 与
    ``week`` 拼出来，没有下标可越界。
    """
    hits: list[ClassHit] = []
    for rule_id in RuleId:
        evaluate_one = _CLASS_EVALUATORS.get(rule_id)
        if evaluate_one is None:
            continue
        hit, _trace = evaluate_one(sig, rules.rules[rule_id])
        if hit is not None:
            hits.append(hit)
    return tuple(hits)


def student_skip_traces(
    sig: StudentSignals, rules: AlertRules
) -> "dict[RuleId, dict]":
    """「求值过、但**判不了**」的学生级规则 → 留痕快照。

    「判不了」与「没问题」是两件事（Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）：
    一个从没做过二次小测的学生与一个做了三次、一次都没下降的学生，在教师端不该看起来一样。
    两档都返回空 tuple 的话，「这个学生这周为什么没有预警」就无从回答。

    ⚠️ **本函数不重新判一次**：它跑的是同一批求值器、只取返回值的**后半**，故
    「什么时候判不了」在代码里只有一处（见 :data:`_Evaluator` 的注释）。

    ⚠️ **本函数不调 :func:`_require_parallel`**：它不按下标取任何 id（留痕里只有计数与
    阈值），故一个不满足契约的信号在这里不会炸、而在 :func:`evaluate_student` 里会炸。
    Task 7 应当**先**调 :func:`evaluate_student`（它会炸），再调本函数收留痕。

    返回一个**普通 ``dict``**（新建、不外泄内部状态），键是 :class:`RuleId`。
    """
    traces: dict[RuleId, dict] = {}
    for rule_id in RuleId:
        evaluate_one = _STUDENT_EVALUATORS.get(rule_id)
        if evaluate_one is None:
            continue
        hit, trace = evaluate_one(sig, rules.rules[rule_id])
        if hit is None and trace is not None:
            traces[rule_id] = trace
    return traces


def class_skip_traces(sig: ClassSignals, rules: AlertRules) -> "dict[RuleId, dict]":
    """「求值过、但**判不了**」的班级级规则 → 留痕快照。口径逐字同
    :func:`student_skip_traces`。
    """
    traces: dict[RuleId, dict] = {}
    for rule_id in RuleId:
        evaluate_one = _CLASS_EVALUATORS.get(rule_id)
        if evaluate_one is None:
            continue
        hit, trace = evaluate_one(sig, rules.rules[rule_id])
        if hit is None and trace is not None:
            traces[rule_id] = trace
    return traces


def declared_scope(rule_id: RuleId) -> AlertScope:
    """**代码侧**声明的作用域：哪一套求值器处理这一条规则。

    :func:`app.refdata_alerts.load_alert_rules` 拿它与 YAML 里那一条的 ``scope`` 对账，
    不一致就在加载期响亮失败（口径同 ``refdata_prescription._template`` 对
    ``reachable`` 的处置）。**没有那道对账，YAML 的 ``scope`` 就是装饰**：专家把它一翻
    而代码不跟着翻，就是一件什么也不发生的事，而他会以为发生了。

    ⚠️ **它守不住什么**（硬规矩 #39）：谁往 :class:`RuleId` 加了第 6 个成员却忘了接进
    :data:`_STUDENT_EVALUATORS` / :data:`_CLASS_EVALUATORS`，本函数会**静默地**把它
    报成 ``CLASS``（``in`` 判假就落到第二个 ``return``）。那一档由
    :func:`tests.domain.test_alerts.test_declared_scope_partitions_the_five_rules_as_the_spec_table_says`
    的字面对账抓住（期望侧是 5 个键的字面 dict，多一个成员就多一个键、当场不相等），
    以及加载器「YAML 的键集必须恰好等于 ``RuleId``」那一条。
    """
    if rule_id in _STUDENT_EVALUATORS:
        return AlertScope.STUDENT
    return AlertScope.CLASS
