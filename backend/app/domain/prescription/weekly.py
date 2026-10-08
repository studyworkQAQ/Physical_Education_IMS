"""spec §8.4 的「本周训练单」读模型：**骨架第 N 周 × 本周调整系数**（Plan 02 Task 8）。

spec §8.4 原文两句::

    学生端「本周训练单」= 骨架第 N 周 × 本周调整系数
    预警触发的「减量 20%」落成一条 weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)，
    可追溯、可回滚

第一句是本模块的**全部职责**。第二句的落库侧是
:class:`app.db.models.prescription.WeeklyAdjustment`（Task 6 建表）与
:func:`app.pipeline.prescription_stage.weekly_factors_of`（Task 8 的 ORM → 值对象转换）；
本模块只认那个值对象 :class:`WeeklyFactor`。

**它是一个读模型（read model），不是校验器**：输入是一张已经装配好的
:class:`~app.domain.prescription.assembler.TrainingPackage`（骨架）与一串调整，输出是一份
可以直接渲染的投影。于是它对 ``paused`` 的处置是**带出来**而不是**抛异常**（见下面第 4 节），
而对越界的 ``week`` 才响亮拒绝——后者不是「一种状态」，是**调用方算错了周次**，
静默返回一张空单会让教师端看到「本周没有训练」而学生其实该练。

--------------------------------------------------------------------------

**1. 缩放只作用于 ``weekly_volume``，其余 9 个字段逐字不变**（P8-A1，Critical）

``AssembledBlock`` 今天是 **10** 个字段（``exercise_ref`` / ``exercise_name`` /
``video_url`` / ``impact_level`` / ``intensity_text`` / ``hr_zone`` / ``structure`` /
``weekly_volume`` / ``volume_unit`` / ``sessions_per_week``），而计划 Task 8 的正文只提了
``weekly_volume`` 与 ``hr_zone`` 两个——``volume_unit`` 与 ``sessions_per_week`` 是 Task 5
fix round 1 之后才有的。故口径**收紧**成：:func:`weekly_training_sheet` 只改
``weekly_volume``（``round(x × factor, 1)``），**其余 9 个字段用
:func:`dataclasses.replace` 原样带过去**。

两个具体的坑，各自点名：

* **``sessions_per_week`` 不是量、是结构**：缩它会让「一周做几次」随减量变化
  （减量 20% ≠ 一周少上 0.8 次课）。改周课次是
  :class:`~app.domain.prescription.override.OverrideKind.WEEKLY_FREQUENCY` 的活，
  那一处**同时**改 ``sessions_per_week`` 与 ``weekly_volume``（因为砍掉一课后那个周量
  就在撒谎）；本模块不砍课，故一个都不动。
* **``hr_zone`` 是强度、不是量**：spec §8.4 明写「微调改的是**本周训练量**」。把两者
  一起缩会让「减量」变成「降强度」，而一张强度被悄悄调低的处方在教师端**看起来完全正常**
  （两个整数、低界小于高界）。守卫是
  ``tests/domain/test_prescription_weekly.py`` 的
  :func:`~tests.domain.test_prescription_weekly.test_scaling_touches_only_weekly_volume_on_the_red_layer`
  ——⚠️ **那条测试必须用红层模板**（P8-A8）：亲跑 ``hr_zone`` 非 ``None`` 的 block 数 =
  红层 **16** / 黄层 **0** / 绿层 **0**（Task 5 的 Ruling 133：真仓 130 个 block 里 82 个是
  ``intensity: {type: none}``），用黄层绿层写「不动 ``hr_zone``」是**恒真式（假绿）**。

⚠️ **``WeeklySheet`` 刻意不提供跨单位的周总量汇总字段**（P8-A1 的后半条）。
``volume_unit`` 的实测值域是 ``{min, reps, unspecified}``，而**同一周里它们并存**
（红层第 1 周就是 ``{min, reps}``，体成分异常触发后是三个全在）。把它们相加就是 Task 5 的
F1-1 那个「混合量纲 float」错误——**48 分钟 + 120 次 = 168 什么？** 故 ``WeeklySheet``
里**唯一的 ``float`` 字段是 ``factor``**，前端要显示总量必须**自己按单位分列**
（口径照 ``assembly_snapshot["weekly_volume_base"]`` 那个按单位分列的只读映射）。
守卫是 :func:`~tests.domain.test_prescription_weekly.test_weekly_sheet_has_no_cross_unit_volume_total_field`。

--------------------------------------------------------------------------

**2. ``volume_unit == "unspecified"`` 那一档照原样带出、不特殊处理**（P8-A2，Critical）

第三档 ``"unspecified"`` 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档的
``weekly_volume`` 恒为 ``0.0``（Addon 没有 ``structure``，量无从算起；编造一个数就是把
「不知道」讲成「知道」，Plan01 Ruling 134 的同一条纪律）。而
:func:`~app.domain.prescription.safety.apply_safety` 追加的 addon **已经在
``TrainingPackage.weeks`` 里**，故本模块**一定会吃到它**——计划对这一档只字未提。

处置是**什么都不做**：``0.0 × factor = 0.0``，无副作用。⚠️ 但「结构上支持、逻辑上没测过」
的路径 Plan 03 一定会撞上，故它有一条**吃真仓**的守卫
（:func:`~tests.domain.test_prescription_weekly.test_the_addon_block_keeps_unspecified_unit_and_zero_volume`：
红层 ``RED-END-ABN-01`` + 体成分异常 → 装配出一个含 addon 的包 → 断言那个 block 的
``weekly_volume == 0.0`` 且 ``volume_unit == "unspecified"``）。
⚠️ 那一档还有两个只有它才有的性质，那条守卫一并钉住：它的 ``structure`` 是一个**可变的
空 ``dict``**（模板 block 那一份是 :class:`types.MappingProxyType`，改不动），它的
``intensity_text`` 是那句「附加模块（模板未指定强度，见 spec §14）」。

--------------------------------------------------------------------------

**3. ``factor`` 的合法区间是 ``(0, 2]``，而 DB 那一列刻意没有 CHECK**（P8-A6）

**这是两层守卫、不是重复**，两者的失守方式不同：

* :class:`WeeklyFactor` 的 ``__post_init__`` 挡的是「教师端/预警侧传了 ``0`` 或 ``20``」
  ——即**经过 domain 的调用方**；
* DB 的 ``weekly_adjustment.factor`` 列**刻意不加** CHECK，因为 ``(0, 2]`` 是
  **读模型的语义**、不是**数据的形状**。Plan 03 完全可能要放宽上界（例如一个恢复期
  学生被允许加量到 3 倍），届时改的是本模块的一个常量，而不是一次「重建库」
  （本仓不做迁移，见 :mod:`app.db.models`）。

⚠️ 于是**有人绕过 domain 直接写库**（``INSERT INTO weekly_adjustment … factor = 0``）
今天**不被任何一层拦**（硬规矩 #39）。那一行会被 :func:`weekly_training_sheet` 吃成一张
「本周量全是 0.0」的训练单——**不响**。拦它的地方是 Plan 03 的写入方（教师端表单与
预警落地），而 :class:`app.db.models.prescription.WeeklyAdjustment` 的 docstring 里已经
把这条代价写在那一列上了。

**``0`` 或负数为什么必须拒绝**：那意味着「本周不训练」，而这在本仓有**另一个机制**——
:class:`~app.domain.prescription.override.OverrideKind.PAUSE`（可撤销、保留 ``weeks``）。
两个机制混用的后果是 ``paused=False`` 而量为 0，前端**无从分辨**「教师暂停了」与
「本周恰好被减到 0」。⚠️ 反过来，「暂停」与「本周量为 0」确实是两件不同的事，
故 :attr:`WeeklySheet.paused` 存在（见下一节），而 ``factor = 0.001`` 这种把量压到
``round(48.0 × 0.001, 1) == 0.0`` 的**合法**调整照样允许——守卫
:func:`~tests.domain.test_prescription_weekly.test_a_paused_package_keeps_its_sessions_and_reports_paused`
把两者的 ``paused`` 一个是 ``True`` 一个是 ``False`` 钉住。

--------------------------------------------------------------------------

**4. ``paused`` 是投影出来的、不是校验出来的**（P8-A3）

``TrainingPackage`` 有 ``paused: bool = False``（Task 5 的 5.4 由 ``OverrideKind.PAUSE``
置位），而计划对「读模型吃到 ``paused=True`` 的包该返回什么」**完全没定**。落地口径：

* :class:`WeeklySheet` 带一个 ``paused: bool``，**从 ``pkg.paused`` 直接抄**；
* ``paused=True`` 时 ``sessions`` **原样保留**（照样按 ``factor`` 缩放）——与 Task 5（5.4）
  的决定逐字一致：「暂停是可撤销的，删掉 ``weeks`` 就不可逆了」；
* **不抛 ``ValueError``**：读模型的职责是**投影**、不是校验。抛异常会让「暂停」这件事在
  API 层变成一个**错误分支**而不是一份可渲染的数据，而学生端在暂停期间恰恰**要**看到
  那张单子（上面写着「本周暂停」），否则它看起来像 404。

--------------------------------------------------------------------------

**5. ``source`` 的取值域不在本模块**（P8-A5，Global Constraint #3）

``WeeklyFactor.source`` 是裸 ``str``，本模块**不校验**它。值域的所有者是 DB 侧的
:attr:`app.db.models.prescription.WeeklyAdjustment.SOURCES`（= ``{"auto", "teacher"}``，
由 ``ck_weekly_adjustment_source`` 强制）。domain **不能 import ORM**，故那条漂移测试
住在 pipeline 层（``tests/pipeline/test_prescription_stage.py``）。本模块这一侧的守卫是
:func:`~tests.domain.test_prescription_weekly.test_source_is_a_bare_string_the_domain_does_not_own`
（钉住「确实没有第二份词表」：一个 ``source="principal"`` 的记录能构造出来）。

⚠️ ``"auto"`` 那一档**本计划不产出**（Plan 03 的预警落地），但它必须能被正确处理——
否则 Plan 03 会撞上一个「结构上支持、逻辑上没测过」的路径。本模块对它**没有任何特殊
分支**（``auto`` 与 ``teacher`` 走同一条乘法），故那条路径与 ``teacher`` 是同一份代码；
测试仍按简报要求用直接构造的 ``WeeklyFactor(source="auto")`` 跑过一遍。

--------------------------------------------------------------------------

**6. ``current_week`` 与触发 3 共用同一个口径**（P8-A7）

Task 6 的 :mod:`app.domain.prescription.triggers` 判「微周期到期」用的是::

    (as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK

本模块判「今天是第几周」必须用**同一个** ``7`` 与**同一个** ``>=`` 边界，否则两处会漂::

    week = (as_of - generated_on).days // _DAYS_PER_WEEK + 1
    week > microcycle_weeks -> None

⚠️ **``_DAYS_PER_WEEK`` 是从 :mod:`app.domain.prescription.triggers` import 进来的，
本模块不写第二份 ``7``**（Global Constraint #3）。这个所有权不是本 Task 新立的：
:func:`app.pipeline.prescription_stage.valid_to_of` 的 docstring 里 Task 7 已经写定
「『一周 7 天』这条历法事实的所有者是 ``triggers._DAYS_PER_WEEK``，在管道层再写一个
``* 7`` 就是第二个住址」。跨模块 import 一个私有名有先例
（``app/db/models/organisation.py`` 的 ``from ._shared import _in_domain``），
代价是 ``weekly`` 与 ``triggers`` 之间多一条依赖边——收益是「谁把 7 改成 8」这件事
**只可能同时发生在两处**，不会一处改一处不改。

⚠️ **``.days // 7`` 对负数向下取整**（``-1 // 7 == -1``），故 ``as_of < generated_on``
时 ``week`` 会是 **0 或负**——而 ``pkg.weeks[0 - 1]`` 在 Python 里**不报错**，它静默取到
**最后一周**。于是实现**必须先判 ``.days < 0`` 再算**，返回 ``None``（**不是 0、不是 1**）。
守卫有两条：:func:`~tests.domain.test_prescription_weekly.test_a_day_before_generation_returns_none_not_zero_and_not_one`
（把 0 与 1 逐个排掉）与
:func:`~tests.domain.test_prescription_weekly.test_current_week_agrees_with_microcycle_expired_on_the_expiry_day`
（**跨模块一致性**：「``current_week`` 返回 ``None``」与「``evaluate_triggers`` 报
``MICROCYCLE_EXPIRED``」在到期日那一格同真、在前一天那一格同假）。
**后者是两个模块口径不漂的唯一守卫**：没有它，任一处把 ``7`` 改成别的数、或把 ``>=``
改成 ``>``，学生端就会看到一张**已经过期却仍在渲染**的训练单，而管道那一天恰好也在给他
换新处方——两张同时生效。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**（与 :mod:`app.domain.prescription.intensity` /
``assembler`` / ``override`` / ``templates`` / ``triggers`` 同一条纪律）：
:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 实测 =
``{dataclasses, enum, collections, collections.abc, numpy, typing}``，``datetime`` 不在其中。
既有做法的两半本模块都沿用：① 类型标注写成**前向引用字符串** ``"dt.date"``
（⚠️ **不是** ``from __future__ import annotations`` + ``TYPE_CHECKING``——实测
``app/domain/`` 下两者各 **0** 命中）；② 运行时只**读**注入对象的属性
（``date - date`` 的结果自己就是一个带 ``.days`` 的对象，故**不构造** ``timedelta``）。
⚠️ **代价**：``typing.get_type_hints(current_week)`` 会抛 ``NameError``（``dt`` 在本模块的
命名空间里不存在），理由与处置逐字写在 :mod:`app.domain.prescription.intensity` 的模块
docstring 里。

⚠️ **排序不是本模块的职责**：:class:`WeeklyFactor` **没有时间戳字段**（它是
``weekly_adjustment`` 那一行的**值对象投影**，而 ``created_at`` 是落库/审计载荷，
与 ``OverrideRecord.applied_at`` 同一条口径——「顺序由列表决定，调用方持有真实顺序」）。
故 ``reasons`` / ``sources`` 的顺序**就是入参序列的顺序**，而把那个顺序排对的是
:func:`app.pipeline.prescription_stage.weekly_factors_of` 的 ``ORDER BY created_at, id``
（``id`` 作 tie-breaker，因为同一秒批量插入时 ``created_at`` 相等）。

⚠️ **本模块守不住什么**（硬规矩 #39）：

* **不守 ``adjustments`` 里有没有重复的同一条调整**（例如 ``_replay_cleanup`` 漏删导致
  同一批调整被写了两遍）：两条 ``0.8`` 会被老老实实乘成 ``0.64``，全程不报错。
  拦它的地方是 :func:`app.pipeline.daily._replay_cleanup` 的清单
  （守卫 ``tests/pipeline/test_prescription_stage.py::test_replay_cleanup_covers_prescription_and_weekly_adjustment``）。
* **不守 ``pkg.weeks`` 是 1..N 连续且有序的**：本模块按 ``pkg.weeks[week - 1]`` 取，
  信任 :func:`~app.domain.prescription.assembler.assemble` 的产出契约（它逐周
  ``AssembledWeek(week=i, …)``）。一个被谁重排过的包会让「第 N 周」取错骨架，
  而本模块**看不出**差别。
* **不守 ``factor`` 越界的库行**（见第 3 节）与**不守 ``source`` 的脏值**（见第 5 节）。
"""
from collections.abc import Sequence
from dataclasses import dataclass, replace

from .assembler import AssembledSession, TrainingPackage
# ⚠️ 「一周 7 天」这条历法事实的**唯一住址**在 triggers（Global Constraint #3），
# 本模块 import 它、不写第二份 7。理由与先例逐字见模块 docstring 第 6 节。
from .triggers import _DAYS_PER_WEEK

#: ``WeeklyFactor.factor`` 的合法区间 ``(0, 2]`` 的两端。
#:
#: ⚠️ **DB 的 ``weekly_adjustment.factor`` 列刻意没有对应的 CHECK**（P8-A6）：这是两层
#: 守卫、不是重复。本模块这一层挡「经过 domain 的调用方传了 0 或 20」；DB 那一层不加，
#: 因为 ``(0, 2]`` 是**读模型的语义**、不是**数据的形状**，Plan 03 可能要放宽上界
#: （届时改的是这两个常量，而不是一次重建库）。完整理由见模块 docstring 第 3 节。
#:
#: **私有**（前导下划线）：它们不出现在 :mod:`app.domain.prescription` 的公开面里，故
#: ``__all__`` 与 ``tests/test_refdata_prescription.py`` 的 ``_PRESCRIPTION_PUBLIC_BASELINE``
#: 都不动（那一份的支 5 要求本模块的**公有**顶层定义与基线互为充要）。把一对
#: **待专家确认**的阈值做成公开契约，会让「专家调上界」看起来像一次破坏公开面的改动
#: （与 ``assembler.py`` 那三档个体修正系数同一条理由）。
_FACTOR_EXCLUSIVE_MIN = 0.0
_FACTOR_INCLUSIVE_MAX = 2.0


@dataclass(frozen=True)
class WeeklyFactor:
    """``weekly_adjustment`` 一行的**值对象投影**（spec §8.4 的「本周调整系数」）。

    字段名与顺序照简报 Interfaces / Produces 逐字。⚠️ **命名决定**：domain 侧叫
    ``WeeklyFactor``，Task 6 建的 ORM 表类叫
    :class:`~app.db.models.prescription.WeeklyAdjustment`（表名 ``weekly_adjustment``，
    spec §4.4 的字面）。两者是同一份数据的两种形态，但**不得同名**——否则 docstring 里写
    「``WeeklyAdjustment`` 的 ``source``」时说不清指 ORM 行还是值对象。**domain 不认识 ORM**，
    转换只发生在 pipeline 层（:func:`app.pipeline.prescription_stage.weekly_factors_of`）。

    ⚠️ **它刻意不带 ``created_at``**：顺序由调用方给的列表决定（与
    :class:`~app.domain.prescription.override.OverrideRecord` 的 ``applied_at`` 同一条口径
    ——「同一秒批量操作时它相等，而调用方持有真实顺序」）。于是本模块**结构上不可能**
    自己排序，也就不会出现「两个模块各排一次、排出两个顺序」。

    ``source`` 的取值域**不在本模块**（P8-A5，见模块 docstring 第 5 节）；``reason`` 也
    **刻意不校验非空**（它与 ``OverrideRecord.reason`` 的口径不同，理由见
    ``tests/domain/test_prescription_weekly.py`` 的
    :func:`~tests.domain.test_prescription_weekly.test_an_empty_reason_is_allowed_because_the_domain_does_not_own_that_rule`）。
    """

    week: int
    factor: float
    reason: str
    source: str

    def __post_init__(self) -> None:
        """``factor`` 必须落在 ``(0, 2]``，越界一律 ``ValueError``。

        理由与「DB 那一列为什么刻意不加 CHECK」逐字见模块 docstring 第 3 节（P8-A6）。
        摘要：``0``/负数意味着「本周不训练」，那应该走
        :class:`~app.domain.prescription.override.OverrideKind.PAUSE`（可撤销、保留
        ``weeks``），**两个机制不得混用**；上界 ``2.0`` 是防手误。
        """
        if not (_FACTOR_EXCLUSIVE_MIN < self.factor <= _FACTOR_INCLUSIVE_MAX):
            raise ValueError(
                f"WeeklyFactor.factor = {self.factor} 不在合法区间 (0, 2] 内："
                f"0 或负数意味着「本周不训练」，那应该走 OverrideKind.PAUSE 覆盖"
                f"（可撤销、保留 weeks）而不是调整系数——两个机制不得混用；上界 2.0 是"
                f"防手误（factor=20 会把训练量放大 20 倍）。⚠️ DB 的 "
                f"weekly_adjustment.factor 列刻意没有对应的 CHECK，理由见 weekly.py "
                f"模块 docstring 第 3 节（P8-A6：两层守卫、不是重复）"
            )


@dataclass(frozen=True)
class WeeklySheet:
    """学生端「本周训练单」：**一份可以直接渲染的投影**（spec §8.4）。

    字段名与顺序照简报 Interfaces / Produces + P8-A3 逐字。

    * ``week`` —— 1-based，与 ``AssembledWeek.week`` 同口径。
    * ``factor`` —— 该周全部调整的**裸乘积**，**不 round**。round 一次会让教师端显示的
      系数与 ``weekly_volume`` 的实际倍数对不上账（``0.8 × 0.9`` 亲跑是
      ``0.7200000000000001``，而 ``round(48.0 × 0.7200000000000001, 1) = 34.6``，
      ``34.6 / 48.0 = 0.7208…``）。只有 ``weekly_volume`` 落 ``round(…, 1)``
      （口径照 :func:`app.domain.prescription.override._volume_scale` 与
      :func:`app.domain.prescription.assembler.assemble`，P5-A6）。
      守卫 :func:`~tests.domain.test_prescription_weekly.test_the_product_keeps_its_float_artifact_like_apply_safety_does`。
    * ``reasons`` / ``sources`` —— 该周**全部**调整的原因与来源，按入参序列的顺序。
      **全部保留**而不是只留最后一条：spec §8.4 说「可追溯、可回滚」，而取最后一条会让
      前一条**消失**；相乘能让每一条都留在乘积里且各自可撤销。
    * ``sessions`` —— 骨架第 ``week`` 周的那几课，**已按 ``factor`` 缩放**。
      ⚠️ 精确口径见模块 docstring 第 1 节：只改 ``weekly_volume``，其余 9 个字段逐字不变。
    * ``paused`` —— 从 ``pkg.paused`` **直接抄**（P8-A3，见模块 docstring 第 4 节）。
      ⚠️ **「暂停」与「本周量为 0」是两件不同的事**（前者是可撤销的状态、后者是调整
      结果），这个字段的存在就是为了不让前端把两者静默合并。

    ⚠️ **刻意不提供跨单位的周总量汇总字段**（P8-A1，见模块 docstring 第 1 节）：
    ``volume_unit`` 的值域是 ``{min, reps, unspecified}`` 且**同一周里并存**，把它们相加
    就是 Task 5 的 F1-1 那个「混合量纲 float」错误。前端要显示总量必须**自己按单位分列**。
    """

    week: int
    factor: float
    reasons: tuple[str, ...]
    sources: tuple[str, ...]
    sessions: tuple[AssembledSession, ...]
    paused: bool


def current_week(
    generated_on: "dt.date", as_of: "dt.date", microcycle_weeks: int
) -> "int | None":
    """``as_of`` 是这张处方的**第几周**（1-based），越界一律 ``None``。

    签名照简报 Interfaces / Produces 逐字。两档 ``None``：

    1. ``as_of`` **早于** ``generated_on``（处方还没生效——重放历史日期、或调用方传错了
       业务日期）。⚠️ **必须先判这一档再算**：``.days // 7`` 对负数**向下取整**
       （``-1 // 7 == -1``），不判的话返回的是 ``0``，而 ``pkg.weeks[0 - 1]`` 在 Python 里
       是**最后一周**（见模块 docstring 第 6 节）。
    2. ``week > microcycle_weeks``（已到期，该换处方了）。与
       :func:`~app.domain.prescription.triggers.evaluate_triggers` 的触发 3 **同一口径**
       （``>=`` 那一格：第 ``microcycle_weeks × 7`` 天当天就到期，故 ``+27`` 天仍是第 4 周、
       ``+28`` 天返回 ``None``）。

    ``microcycle_weeks`` 从**处方行**取（Task 6 的 P6-A3 把它从模板快照在
    :attr:`app.db.models.prescription.Prescription.microcycle_weeks` 上），**不硬编码 4**：
    模板会改版，而一张 2026-03 生成的处方必须能在 2027 年离线复算出它当时的周次
    （spec §4.3）。

    ⚠️ **返回 ``None`` 而不是抛异常**：「今天不在这张处方的有效期内」是一档**正常**状态
    （它恰好也是触发 3 该开火的那一天），调用方据此去取新处方即可；抛异常会把它变成一个
    错误分支。⚠️ 反过来，:func:`weekly_training_sheet` 对越界的 ``week`` **抛**
    ``ValueError``——那不是「一种状态」，是调用方**算错了周次**（它本该先调本函数）。

    纯函数：``generated_on`` / ``as_of`` 一律由调用方注入，本模块不读时钟
    （``datetime`` 不在 domain 的 allow-list 里，见模块 docstring 末节）。
    """
    elapsed_days = (as_of - generated_on).days
    if elapsed_days < 0:
        # ⚠️ 必须排在整除之前：(-1) // 7 == -1 → +1 == 0，一个「第 0 周」会被
        #    pkg.weeks[-1] 静默翻译成最后一周（模块 docstring 第 6 节 / P8-A7）。
        return None
    week = elapsed_days // _DAYS_PER_WEEK + 1
    if week > microcycle_weeks:
        return None
    return week


def weekly_training_sheet(
    pkg: TrainingPackage,
    week: int,
    adjustments: Sequence[WeeklyFactor],
) -> WeeklySheet:
    """骨架第 ``week`` 周 × 该周的全部调整 → 一份 :class:`WeeklySheet`。

    签名照简报 Interfaces / Produces 逐字。**纯函数**：不改 ``pkg``、不改 ``adjustments``、
    不读盘、不读时钟（守卫
    :func:`~tests.domain.test_prescription_weekly.test_weekly_training_sheet_does_not_mutate_the_package`，
    ⚠️ 它**用带 addon 的包**跑，因为 addon block 的 ``structure`` 是一个可变的空 ``dict``
    ——用纯模板包跑的话「没改 ``structure``」是恒真式）。

    **同一周有多条调整时相乘、不取最后一条**（简报 Task 8「决定」第 1 条）：spec §8.4 说
    「可追溯、可回滚」，取最后一条会让前一条**消失**，而相乘能让每一条都留在乘积里且
    各自可撤销。⚠️ 这是**工程决定**，登记 spec §14（归 Task 9）。
    ``reasons`` / ``sources`` 因此**全部保留**，顺序就是 ``adjustments`` 的顺序
    （本模块不排序，理由见模块 docstring 第 6 节末段）。

    **别的周的调整被过滤掉**：``adjustments`` 是**这张处方全部周**的调整
    （:func:`app.pipeline.prescription_stage.weekly_factors_of` 按 ``prescription_id``
    取，不按周），故本函数自己挑 ``adjustment.week == week`` 的那些。⚠️ 过滤**不报错**：
    「第 2 周有调整、第 1 周没有」是常态，不是错误。

    ⚠️ **越界的 ``week`` 响亮拒绝**（``ValueError``，不夹取、不静默返回空单）。这条是
    :attr:`app.db.models.prescription.WeeklyAdjustment.week` 那一列注释里 Task 6 **已经
    承诺过**的口径：那张表刻意没有周次的 CHECK（上界是每张处方各自的 ``microcycle_weeks``，
    写进 DDL 就是把「4 周」硬编码），故拒绝落在读侧。``week = 0`` / 负数尤其要响：
    ``pkg.weeks[-1]`` 是**最后一周**，不拒绝就是一张「第 0 周」的训练单、内容是超量恢复周。

    ⚠️ **``paused`` 只被抄、不被判**（P8-A3）：``paused=True`` 时 ``sessions`` 照样按
    ``factor`` 缩放并原样带出，**不抛异常**（理由见模块 docstring 第 4 节）。
    """
    if week < 1 or week > len(pkg.weeks):
        raise ValueError(
            f"week={week} 超出这张训练包的范围 [1, {len(pkg.weeks)}]：骨架只有 "
            f"{len(pkg.weeks)} 周。**不夹取、不静默返回一张空训练单**——week=0 或负数在 "
            f"Python 里会索引到**最后**一周（pkg.weeks[-1]），于是学生会拿到一张"
            f"「第 0 周」的单子、内容是超量恢复周。调用方应先用 current_week 把业务日期"
            f"折算成周次，它对越界返回 None"
        )

    # 只取该周的那些；顺序原样保留（排序是调用方的职责，本值对象没有时间戳字段）。
    this_week: list[WeeklyFactor] = []
    for adjustment in adjustments:
        if adjustment.week == week:
            this_week.append(adjustment)

    # 相乘、不取最后一条（理由见本函数 docstring）。裸乘积、不 round：
    # 0.8 × 0.9 == 0.7200000000000001，round 一次会让教师端显示的系数与
    # weekly_volume 的实际倍数对不上账（P5-A6 的同一条纪律）。
    factor = 1.0
    for item in this_week:
        factor *= item.factor

    skeleton = pkg.weeks[week - 1]
    # ⚠️ 缩放**只**作用于 weekly_volume，其余 9 个字段用 replace 原样带过去（P8-A1）。
    #    sessions_per_week 是结构不是量；hr_zone 是强度不是量（模块 docstring 第 1 节）。
    sessions = tuple(
        replace(
            session,
            blocks=tuple(
                replace(block, weekly_volume=round(block.weekly_volume * factor, 1))
                for block in session.blocks
            ),
        )
        for session in skeleton.sessions
    )
    return WeeklySheet(
        week=week,
        factor=factor,
        reasons=tuple(item.reason for item in this_week),
        sources=tuple(item.source for item in this_week),
        sessions=sessions,
        # P8-A3：直接抄，不校验、不抛异常。paused=True 时 sessions 原样保留。
        paused=pkg.paused,
    )
