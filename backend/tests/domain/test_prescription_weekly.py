# backend/tests/domain/test_prescription_weekly.py
"""spec §8.4 的「本周训练单」读模型 :mod:`app.domain.prescription.weekly` 的守卫（Plan 02 Task 8）。

spec §8.4 原文：「学生端『本周训练单』 = 骨架第 N 周 × 本周调整系数」；「预警触发的
『减量 20%』落成一条 ``weekly_adjustment``（系数 0.8, 原因 RED_RPE_SUSTAINED），可追溯、
可回滚」。本文件钉的是那个乘法**到底动了什么、没动什么**。

--------------------------------------------------------------------------

**期望值一律字面写死、独立重算**（硬规矩 #35 / #44）。基准包用一个**系数恰为 1.0** 的画像
（男 + ``endurance_score = 70`` → 档 ``mid`` → ``1.0``；性别男 → ``1.0``）装配，于是第 1 周的
``weekly_volume`` 就是 ``base × sessions_per_week`` 的字面值。本机 Python 3.11.1 /
``as_of = 2026-10-08`` 亲跑（取证脚本见 Task 8 报告 §2）::

    RED-END-ABN-01  4 周 / 每周 4 课 / 单位 {min, reps} / delta (1.0, 1.05, 1.1, 0.85)
                    第 1 周 8 个 block = [interval_run 48.0 min, compound_circuit 120.0 reps] × 4
                    第 4 周            = [40.8 min, 102.0 reps] × 4
    YEL-END-NOR-08  4 周 / 每周 3 课 / 单位 {min}      / 第 1 周 6 个 block 全是 36.0 min
    GRN-END-NOR-14  4 周 / 每周 2 课 / 单位 {min}      / 第 1 周 4 个 block 全是 24.0 min

⚠️ **心率相关的断言一律打在红层**（P8-A8）：亲跑 ``hr_zone`` 非 ``None`` 的 block 数 =
红层 **16** / 黄层 **0** / 绿层 **0**（Task 5 的 Ruling 133：真仓 130 个 block 里 82 个是
``intensity: {type: none}``）。故 :func:`test_scaling_touches_only_weekly_volume_on_the_red_layer`
用 ``RED-END-ABN-01``，且**额外断言它确实有非 ``None`` 的 ``hr_zone``**——没有那一句，
「缩放不动 ``hr_zone``」在黄层绿层上是恒真式（假绿）。

--------------------------------------------------------------------------

⚠️ **吃真仓 YAML 一律走三个进程内单例**（P5-A12 的既有口径）：
:func:`app.refdata_prescription.exercises` / :func:`~app.refdata_prescription.templates` /
:func:`~app.refdata_prescription.equivalence`，不用 ``load_*``。**单例是进程内共享的，
本文件一个字都不改它**：要一个 ``paused=True`` 的包一律用 :func:`dataclasses.replace` 造副本。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「一周 7 天」这个历法事实**：:func:`current_week` 与
  :func:`~app.domain.prescription.triggers.evaluate_triggers` 的触发 3 **共用**
  ``triggers._DAYS_PER_WEEK``（同一个住址，Global Constraint #3），故「谁把 7 改成 8」
  两处一起变、本文件看不出差别。守得住的是**两个模块的口径不漂**：
  :func:`test_current_week_agrees_with_microcycle_expired_on_the_expiry_day`。
* **不守 ``source`` 的取值域**：所有者是 DB 侧的
  :attr:`app.db.models.prescription.WeeklyAdjustment.SOURCES`（P8-A5），domain 只消费。
  漂移测试在 **pipeline 层**（``tests/pipeline/test_prescription_stage.py``），因为
  domain 不能 import ORM。:func:`test_source_is_a_bare_string_the_domain_does_not_own`
  钉的是「domain 侧确实没有第二份词表」这件事本身。
* **不守 ``datetime`` 没被 import 进来**：那是
  :mod:`tests.architecture.test_domain_purity` 的 allow-list 守卫的活
  （实测 ``ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy,
  typing}``）。本文件只把**后果**钉住：``generated_on`` / ``as_of`` 一律由调用方注入，
  函数不读时钟（:func:`test_current_week_does_not_hardcode_a_four_week_microcycle`
  末尾那一句「同样的参数两次调用同结果」）。
* **不守第 4 周那个 ``delta = 0.85``（超量恢复）对不对**：那是模板 YAML 的内容，
  所有者是 ``backend/data/prescription/RED-END-ABN-01.yaml``，字面钉住它的测试在
  ``tests/test_refdata_prescription.py``。本文件只钉「读模型取的是**那一周自己的**骨架」。
"""
import dataclasses
import datetime as dt

import pytest

from app import refdata_prescription as rp
from app.domain.indicators import Sex
from app.domain.prescription.assembler import (
    AssembledBlock, StudentProfile, TrainingPackage, assemble,
)
from app.domain.prescription.safety import SafetyInput, apply_safety
from app.domain.prescription.triggers import (
    LastPrescription, TriggerInput, TriggerReason, evaluate_triggers,
)
from app.domain.prescription.weekly import (
    WeeklyFactor, WeeklySheet, current_week, weekly_training_sheet,
)

_AS_OF = dt.date(2026, 10, 8)
_BIRTH = dt.date(2006, 3, 15)

#: ``current_week`` 的基准生成日与 ``microcycle_weeks = 4`` 的六个格子。日期**字面写死**
#: （与 ``tests/domain/test_prescription_triggers.py`` 的 ``_GENERATED_ON`` / ``_DAY_27`` /
#: ``_DAY_28`` 刻意各写一份：两个文件各自独立钉住同一条口径，改一处不改另一处会红——
#: 那正是 P8-A7 那条跨模块一致性守卫的用意，不是重复。硬规矩 #51）。
_GENERATED_ON = dt.date(2026, 3, 2)
_DAY_MINUS_1 = dt.date(2026, 3, 1)
_DAY_0 = dt.date(2026, 3, 2)
_DAY_6 = dt.date(2026, 3, 8)
_DAY_7 = dt.date(2026, 3, 9)
_DAY_27 = dt.date(2026, 3, 29)
_DAY_28 = dt.date(2026, 3, 30)

#: ``AssembledBlock`` 的 **10** 个字段名（P8-A1）。**逐字写死**，顺序照
#: :mod:`app.domain.prescription.assembler` 里的书写序。⚠️ 数法用运行时口径
#: ``len(dataclasses.fields(...))``，不用正则数源码（硬规矩 #89）。
_PINNED_BLOCK_FIELDS = (
    "exercise_ref", "exercise_name", "video_url", "impact_level", "intensity_text",
    "hr_zone", "structure", "weekly_volume", "volume_unit", "sessions_per_week",
)

#: ``RED-END-ABN-01`` 第 1 周 ``interval_run`` 的目标心率区间（亲跑；HRmax = 194.0，
#: Tanaka ``208 − 0.7 × 20 = 194.0``）。红层是唯一有非 ``None`` ``hr_zone`` 的一层（P8-A8）。
_RED_HR_ZONE = (116, 136)


def _profile() -> StudentProfile:
    """系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。"""
    return StudentProfile(
        student_id=1, sex=Sex.MALE, birth=_BIRTH, age=20, endurance_score=70.0,
        bmi=None, body_fat_pct=None, muscle_mass_kg=None, muscle_p10=None,
        measured_hrmax=None,
    )


def _pkg(template_id: str = "RED-END-ABN-01") -> TrainingPackage:
    return assemble(_profile(), rp.templates()[template_id], _AS_OF,
                    exercises=rp.exercises())


def _addon_pkg() -> TrainingPackage:
    """红层 + 体成分异常 → ``apply_safety`` 追加 addon（P8-A2 的那一档）。

    亲跑：``RED-END-ABN-01`` 的 ``addons`` 是
    ``(Addon(when='body_fat_over', module='energy_expenditure_plus_10pct'),
    Addon(when='muscle_low', module='resistance_priority'))``，故
    ``body_fat_abnormal=True`` 追加 **16** 个 addon block（4 周 × 4 课），每个都是
    ``weekly_volume = 0.0`` / ``volume_unit = "unspecified"`` / ``hr_zone = None`` /
    ``structure = {}`` / ``sessions_per_week = 4``。整包因此有 **48** 个 block。
    """
    template = rp.templates()["RED-END-ABN-01"]
    return apply_safety(
        _pkg(),
        SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                    body_fat_abnormal=True),
        rp.equivalence(), template=template, exercises=rp.exercises(),
    ).package


def _adjustments(*triples) -> tuple[WeeklyFactor, ...]:
    """``(week, factor, source)`` 三元组 → ``WeeklyFactor`` 序列，``reason`` 由序号生成。"""
    return tuple(
        WeeklyFactor(week=week, factor=factor, reason=f"理由{index}", source=source)
        for index, (week, factor, source) in enumerate(triples, start=1)
    )


def _blocks(sheet_or_week) -> list:
    """``WeeklySheet`` 或 ``AssembledWeek`` 的全部 block（两者都有 ``.sessions``）。"""
    return [block for session in sheet_or_week.sessions for block in session.blocks]


def _volumes(sheet) -> list[tuple[str, float, str]]:
    """``[(exercise_ref, weekly_volume, volume_unit)]``，按课序 + block 序。"""
    return [(b.exercise_ref, b.weekly_volume, b.volume_unit) for b in _blocks(sheet)]


# ---------------------------------------------------------------------------
# 1. 两个值对象的形状（P8-A1 / P8-A3 的字段清单）
# ---------------------------------------------------------------------------


def test_the_two_value_objects_are_frozen_and_carry_the_pinned_fields():
    """``WeeklyFactor`` **4** 个字段、``WeeklySheet`` **6** 个字段（含 P8-A3 的 ``paused``）。

    字段名与顺序**逐字写死**（简报 Interfaces / Produces + P8-A3）。数法用运行时口径
    ``len(dataclasses.fields(...))``（硬规矩 #89）。
    """
    assert [f.name for f in dataclasses.fields(WeeklyFactor)] == [
        "week", "factor", "reason", "source",
    ]
    assert len(dataclasses.fields(WeeklyFactor)) == 4

    assert [f.name for f in dataclasses.fields(WeeklySheet)] == [
        "week", "factor", "reasons", "sources", "sessions", "paused",
    ]
    assert len(dataclasses.fields(WeeklySheet)) == 6

    # frozen 不是风格问题：weekly_training_sheet 是纯函数，而它能被「投影过程中就地改写
    # 输入」破坏的唯一途径就是字段可变（口径照 triggers / override 那两个值对象）。
    factor = WeeklyFactor(week=1, factor=0.8, reason="r", source="teacher")
    sheet = weekly_training_sheet(_pkg(), 1, (factor,))
    with pytest.raises(dataclasses.FrozenInstanceError):
        factor.factor = 1.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sheet.factor = 1.0  # type: ignore[misc]


def test_weekly_sheet_has_no_cross_unit_volume_total_field():
    """**P8-A1 的后半条**：``WeeklySheet`` 刻意**不提供**跨单位的周总量汇总字段。

    前提是可查的事实：红层第 1 周的 ``volume_unit`` 值域亲跑 = ``{"min", "reps"}``
    （addon 那一档还会加 ``"unspecified"``，见 P8-A2）。把它们相加就是 Task 5 的 F1-1
    那个「混合量纲 float」错误——**48 分钟 + 120 次 = 168 什么？**

    故本条断言两件事：① 那一周真的有**两个**单位（不是恒真式）；② ``WeeklySheet`` 里
    **唯一的 ``float`` 字段是 ``factor``**，于是没有任何一个字段能装得下那个和。
    """
    sheet = weekly_training_sheet(_pkg(), 1, ())
    units = {block.volume_unit for block in _blocks(sheet)}
    assert units == {"min", "reps"}, units

    float_fields = [f.name for f in dataclasses.fields(WeeklySheet) if f.type is float]
    assert float_fields == ["factor"], float_fields


# ---------------------------------------------------------------------------
# 2. current_week 的六个边界（P8-A7）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (_DAY_MINUS_1, None),   # P8-A7：早于生成日 → None（**不是 0、不是 1**）
        (_DAY_0, 1),            # 生成当天就是第 1 周
        (_DAY_6, 1),            # 第 7 天仍属第 1 周（1-based、闭区间）
        (_DAY_7, 2),            # 第 8 天进第 2 周
        (_DAY_27, 4),           # 第 28 天（= microcycle_weeks × 7 − 1）仍是最后一周
        (_DAY_28, None),        # 第 29 天：已到期，该换处方了
    ],
)
def test_current_week_six_boundaries(as_of, expected):
    """六个格子的日期全部**字面写死**（简报的边界要求 + P8-A7 加的那一格）。"""
    assert current_week(_GENERATED_ON, as_of, 4) == expected


def test_a_day_before_generation_returns_none_not_zero_and_not_one():
    """**P8-A7 的承重格**：``as_of == generated_on − 1 day`` → ``None``。

    ⚠️ ``(−1) // 7 == −1`` → ``−1 + 1 == 0``，故**不先判 ``.days < 0``** 的实现会返回
    ``0``（一个「第 0 周」），而 ``pkg.weeks[0 - 1]`` 在 Python 里**不报错**——它会静默
    取到**最后一周**。于是学生会看到一张「第 0 周」的训练单，内容是第 4 周的超量恢复周。
    本条把三个可能的返回值逐个排掉。
    """
    got = current_week(_GENERATED_ON, _DAY_MINUS_1, 4)
    assert got is None
    assert got != 0
    assert got != 1


def test_current_week_does_not_hardcode_a_four_week_microcycle():
    """``microcycle_weeks`` 从**处方行**取，不硬编码 4（Task 6 的 P6-A3 同一条纪律）。

    2 周的模板：``+13`` 天仍是第 2 周，``+14`` 天到期 → ``None``。
    ⚠️ 末句同时是纯函数的证据：同样的三个参数两次调用给出同一个结果（不读时钟、不读盘，
    ``as_of`` 与 ``generated_on`` 一律由调用方注入）。
    """
    assert current_week(_GENERATED_ON, dt.date(2026, 3, 15), 2) == 2
    assert current_week(_GENERATED_ON, dt.date(2026, 3, 16), 2) is None
    assert current_week(_GENERATED_ON, dt.date(2026, 3, 15), 2) == 2


def test_current_week_agrees_with_microcycle_expired_on_the_expiry_day():
    """**P8-A7 的跨模块一致性守卫**：两个模块的口径不漂的**唯一**守卫。

    对同一组 ``(generated_on, as_of, microcycle_weeks)``，断言「``current_week`` 返回
    ``None``」与「``evaluate_triggers`` 报 :attr:`TriggerReason.MICROCYCLE_EXPIRED`」
    在到期日那一格**同真**、在前一天那一格**同假**。

    没有这一条：任一处把 ``7`` 改成别的数、或把 ``>=`` 改成 ``>``，学生端就会看到一张
    **已经过期却仍在渲染**的训练单（而管道那一天恰好也在给他换新处方，两张同时生效）。

    ⚠️ 触发侧的其余四条一律压掉（标签不变、没有新采集、教师没点），于是 ``hits`` 在
    到期日前恒为 ``()``、到期日恒为 ``(MICROCYCLE_EXPIRED,)``——断言因此能钉住**这一条**
    触发，而不是「碰巧还有别的触发」。
    """
    hits = ()
    for as_of, expected_week in ((_DAY_27, 4), (_DAY_28, None)):
        hits = evaluate_triggers(
            TriggerInput(
                as_of=as_of,
                current_label="yellow",
                current_template_id="YEL-END-NOR-01",
                last_prescription=LastPrescription(
                    generated_on=_GENERATED_ON,
                    template_id="YEL-END-NOR-01",
                    label_at_generation="yellow",
                    microcycle_weeks=4,
                    status="active",
                ),
                latest_assessment_date=None,
                teacher_requested=False,
            )
        )
        expired = TriggerReason.MICROCYCLE_EXPIRED in hits
        week = current_week(_GENERATED_ON, as_of, 4)
        assert week == expected_week, (as_of, week)
        assert expired is (expected_week is None), (as_of, hits, week)
    # 到期日那一格：hits 里**只有** MICROCYCLE_EXPIRED（其余四条确实被压掉了）
    assert hits == (TriggerReason.MICROCYCLE_EXPIRED,)


# ---------------------------------------------------------------------------
# 3. WeeklyFactor 的 (0, 2] 校验（P8-A6）与两个「刻意不校验」
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("factor", [0.0, -0.1, 2.1, 20.0])
def test_a_factor_outside_zero_exclusive_to_two_inclusive_is_rejected(factor):
    """``factor`` 的合法区间是 **``(0, 2]``**，越界一律 ``ValueError``。

    * ``0`` 或负数意味着「本周不训练」——那应该走 Task 5（5.4）的 ``OverrideKind.PAUSE``
      而不是调整系数，**两个机制不得混用**；
    * 上界 ``2.0`` 是防手误（``factor = 20`` 会把训练量放大 20 倍）。

    ⚠️ **DB 的 ``weekly_adjustment.factor`` 列刻意没有对应的 CHECK**（P8-A6）：这是两层
    守卫、不是重复。理由逐字写在 :mod:`app.domain.prescription.weekly` 的模块 docstring 里。
    """
    with pytest.raises(ValueError) as exc:
        WeeklyFactor(week=1, factor=factor, reason="本周月考，减量", source="teacher")
    assert "factor" in str(exc.value)


@pytest.mark.parametrize("factor", [2.0, 1.0, 0.8, 0.001])
def test_the_bounds_themselves_are_accepted(factor):
    """``2.0`` 是**闭**上界、``0`` 是**开**下界：``2.0`` 合法，``0.001`` 也合法。"""
    assert WeeklyFactor(week=1, factor=factor, reason="r", source="auto").factor == factor


def test_source_is_a_bare_string_the_domain_does_not_own():
    """**P8-A5**：``source`` 在 domain 侧是裸 ``str``，本模块**不校验**它的取值域。

    所有者是 DB 侧的 :attr:`app.db.models.prescription.WeeklyAdjustment.SOURCES`
    （= ``{"auto", "teacher"}``，由 ``ck_weekly_adjustment_source`` 强制）。domain 不能
    import ORM，故漂移测试住在 pipeline 层；本条钉的是**反面**：domain 侧确实没有第二份
    词表（一个 ``source="principal"`` 的记录能构造出来、没有任何一条 domain 测试会红）。

    ⚠️ 代价（硬规矩 #39）：一个绕过 DB CHECK 写进来的脏 ``source`` 会被读模型**原样带出**
    到学生端。拦它的地方是那条 CHECK 与 Plan 03 的写入方，不是本模块。
    """
    for source in ("auto", "teacher", "principal"):
        assert WeeklyFactor(week=1, factor=1.0, reason="r", source=source).source == source


def test_an_empty_reason_is_allowed_because_the_domain_does_not_own_that_rule():
    """``reason`` **刻意不校验非空**（与 :class:`OverrideRecord` 的口径**不同**）。

    ``OverrideRecord.reason`` 在构造期拒绝空串，理由是 spec §7.5 末段把教师覆盖当研究数据。
    ``weekly_adjustment.reason`` 是 DB 的 ``Text NOT NULL`` 列，而 ``source = "auto"`` 那一档
    的 reason 由 Plan 03 的预警侧生成（形如 ``RED_RPE_SUSTAINED``）——在读模型这一层再校验
    一次就是第二个住址，而它拦不住真正的失守方（写库那一侧）。故本条把「不校验」钉住：
    空 reason 能构造出来，且原样出现在 ``WeeklySheet.reasons`` 里。
    """
    factor = WeeklyFactor(week=1, factor=0.8, reason="", source="auto")
    sheet = weekly_training_sheet(_pkg(), 1, (factor,))
    assert sheet.reasons == ("",)


# ---------------------------------------------------------------------------
# 4. weekly_training_sheet：空调整列表 = 骨架原样；越界的 week 响亮拒绝
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("template_id", "expected"),
    [
        # 红层：每课 2 个 block，4 课 → 8 个；单位 {min, reps}
        ("RED-END-ABN-01", [("interval_run", 48.0, "min"),
                            ("compound_circuit", 120.0, "reps")] * 4),
        # 黄层：每课 2 个 block，3 课 → 6 个；全是 36.0 min
        ("YEL-END-NOR-08", [("steady_run", 36.0, "min"),
                            ("step_training", 36.0, "min")] * 3),
        # 绿层：每课 2 个 block，2 课 → 4 个；全是 24.0 min
        ("GRN-END-NOR-14", [("orienteering", 24.0, "min"),
                            ("interest_ball_games", 24.0, "min")] * 2),
    ],
)
def test_no_adjustments_mean_factor_one_and_the_untouched_skeleton(template_id, expected):
    """空调整列表 → ``factor == 1.0``、``reasons`` / ``sources`` 空、``sessions`` 与骨架逐字段相同。

    期望值是**字面写死**的三套真仓数据（本文件 docstring 顶部那份亲跑清单），不是从骨架读回来
    跟自己比（硬规矩 #35）；同时**也**断言与骨架 ``==``，那是「读模型什么都没改」的直接表达。
    """
    pkg = _pkg(template_id)
    sheet = weekly_training_sheet(pkg, 1, ())

    assert sheet.week == 1
    assert sheet.factor == 1.0
    assert sheet.reasons == ()
    assert sheet.sources == ()
    assert sheet.paused is False
    assert _volumes(sheet) == expected
    assert sheet.sessions == pkg.weeks[0].sessions


def test_the_sheet_picks_that_weeks_own_skeleton_not_the_first_one():
    """``week = 4`` 取的是**第 4 周自己的**骨架（``delta = 0.85``，超量恢复周）。

    亲跑：红层第 4 周 = ``[40.8 min, 102.0 reps] × 4``，再乘 ``0.8`` →
    ``round(40.8 × 0.8, 1) = 32.6``、``round(102.0 × 0.8, 1) = 81.6``。
    ⚠️ 若实现取错了周（``pkg.weeks[0]``），得到的是 ``38.4 / 96.0``，两个数都不同 → 红。
    """
    sheet = weekly_training_sheet(_pkg(), 4, _adjustments((4, 0.8, "teacher")))
    assert sheet.week == 4
    assert sheet.factor == 0.8
    assert _volumes(sheet) == [("interval_run", 32.6, "min"),
                               ("compound_circuit", 81.6, "reps")] * 4


def test_adjustments_for_another_week_are_ignored():
    """只有 ``week`` 相同的那些进乘积；别的周的调整**一个字都不影响**这一周。

    ⚠️ 这一条同时是 ``weekly_training_sheet`` 里那个 ``if adjustment.week == week`` 的
    **假支**覆盖（domain 分支覆盖必须 100%）。
    """
    sheet = weekly_training_sheet(
        _pkg(), 1,
        _adjustments((2, 0.5, "teacher"), (1, 0.8, "auto"), (3, 0.5, "teacher")),
    )
    assert sheet.factor == 0.8
    assert sheet.reasons == ("理由2",)
    assert sheet.sources == ("auto",)
    assert _volumes(sheet) == [("interval_run", 38.4, "min"),
                               ("compound_circuit", 96.0, "reps")] * 4


@pytest.mark.parametrize("week", [0, 5, -1])
def test_a_week_outside_the_package_is_rejected_loudly(week):
    """越界的 ``week`` 一律 ``ValueError``、**不夹取、不静默返回空单**。

    ⚠️ 这条是 :attr:`app.db.models.prescription.WeeklyAdjustment.week` 那一列注释里
    **已经承诺过**的口径（Task 6 写定：「越界的 ``week`` 今天由
    :mod:`app.domain.prescription.weekly`（Task 8）在读侧拒绝」），因为那张表**刻意没有**
    周次的 CHECK（上界是每张处方各自的 ``microcycle_weeks``，写进 DDL 就是把「4 周」
    硬编码）。

    ⚠️ ``week = 0`` 与 ``week = -1`` 尤其要响：``pkg.weeks[0 - 1]`` 在 Python 里是
    **最后一周**，不拒绝的话就是一张「第 0 周」的训练单、内容是超量恢复周。
    """
    with pytest.raises(ValueError) as exc:
        weekly_training_sheet(_pkg(), week, ())
    assert "week" in str(exc.value)


# ---------------------------------------------------------------------------
# 5. 缩放的精确口径（P8-A1 / P8-A8）
# ---------------------------------------------------------------------------


def test_assembled_block_still_has_exactly_the_ten_pinned_fields():
    """**P8-A1 的前提守卫**：``AssembledBlock`` 今天是 **10** 个字段。

    计划 Task 8 的正文只提了 ``weekly_volume`` 与 ``hr_zone`` 两个字段，而
    ``volume_unit`` 与 ``sessions_per_week`` 是 Task 5 fix round 1 之后才有的。本条把
    「一共 10 个、名字与顺序逐字如此」钉住：谁再加第 11 个字段，这条会红，逼他**显式决定**
    那个字段该不该被缩放（而不是被 ``replace(block, weekly_volume=…)`` 静默带过去）。
    """
    names = tuple(f.name for f in dataclasses.fields(AssembledBlock))
    assert names == _PINNED_BLOCK_FIELDS
    assert len(names) == 10


def test_scaling_touches_only_weekly_volume_on_the_red_layer():
    """**P8-A1 + P8-A8（Critical）**：缩放**只**改 ``weekly_volume``，其余 **9** 个字段逐字不变。

    对照法用 :func:`dataclasses.replace`：把缩放后的 block 的 ``weekly_volume`` 换回骨架
    那一个，两者必须**完全相等**。于是「除 ``weekly_volume`` 外全等」是一句可执行的断言，
    而不是逐字段抄九遍（抄九遍的话，加第 11 个字段时这条测试会静默漏掉它）。

    ⚠️ **必须用红层**（P8-A8）：``hr_zone`` 只有红层的 ``hrmax_pct`` block 非 ``None``，
    黄层绿层全是 ``None``，用它们写「不动 ``hr_zone``」是**恒真式（假绿）**。故本条额外
    断言「确有 4 个非 ``None`` 的 ``hr_zone``」，把恒真式的可能性排掉。

    ⚠️ ``sessions_per_week`` 被缩会让「一周做几次」随减量变化（语义错误：减量 20% 不等于
    一周少上 0.8 次课），故它也在「逐字不变」那 9 个里，并且**单独**用字面值再钉一次。
    """
    pkg = _pkg()
    sheet = weekly_training_sheet(pkg, 1, _adjustments((1, 0.8, "teacher")))

    assert sheet.factor == 0.8
    assert _volumes(sheet) == [("interval_run", 38.4, "min"),
                               ("compound_circuit", 96.0, "reps")] * 4

    hr_zones = [b.hr_zone for b in _blocks(sheet)]
    assert hr_zones.count(_RED_HR_ZONE) == 4, hr_zones
    assert hr_zones.count(None) == 4, hr_zones

    assert {b.sessions_per_week for b in _blocks(sheet)} == {4}

    compared = 0
    for scaled, skeleton in zip(sheet.sessions, pkg.weeks[0].sessions):
        # day / focus 两个字段也一个字没动
        assert dataclasses.replace(scaled, blocks=()) == \
            dataclasses.replace(skeleton, blocks=())
        for got, original in zip(scaled.blocks, skeleton.blocks):
            # 把 weekly_volume 换回骨架那一个 → 必须逐字段全等（其余 9 个字段一个字没动）
            assert dataclasses.replace(got, weekly_volume=original.weekly_volume) == original
            # 而 weekly_volume 确实动了（否则上一条是恒真式）
            assert got.weekly_volume == round(original.weekly_volume * 0.8, 1)
            compared += 1
    assert compared == 8


def test_the_scaled_hr_zone_is_literally_the_skeleton_one():
    """``hr_zone`` 的字面值：缩放前后都是 ``(116, 136)``。

    心率区间是**强度**、不是**量**；把两者一起缩会让「减量」变成「降强度」，而 spec §8.4
    明写「微调改的是**本周训练量**」。⚠️ 期望值 ``116`` / ``136`` 是**字面写死**的
    （HRmax 194.0 的 60%–70%），不是从被测的 block 读回来（硬规矩 #35）。
    """
    pkg = _pkg()
    sheet = weekly_training_sheet(pkg, 1, _adjustments((1, 0.8, "teacher")))
    runs = [b for b in _blocks(sheet) if b.exercise_ref == "interval_run"]
    assert len(runs) == 4
    assert [b.hr_zone for b in runs] == [(116, 136)] * 4
    skeleton_zones = [b.hr_zone for b in _blocks(pkg.weeks[0])]
    assert skeleton_zones.count((116, 136)) == 4


def test_multiple_adjustments_multiply_and_keep_every_reason_and_source():
    """同一周多条调整 → **相乘**，``reasons`` / ``sources`` 按输入顺序全部保留。

    取最后一条会让前一条**消失**，而相乘能让每一条都留在乘积里且各自可撤销
    （spec §8.4「可追溯、可回滚」）。``0.8 × 1.25 = 1.0``：先减量再加量回到基线，
    于是 ``weekly_volume`` 与骨架逐字相同——**这正是「可回滚」的可执行表达**。

    ⚠️ 顺序来自**输入序列**（``WeeklyFactor`` 没有时间戳字段），故排序是调用方
    （:func:`app.pipeline.prescription_stage.weekly_factors_of` 的 ``ORDER BY created_at, id``）
    的职责；``auto`` 与 ``teacher`` 混着来也一样。
    """
    sheet = weekly_training_sheet(
        _pkg(), 1, _adjustments((1, 0.8, "auto"), (1, 1.25, "teacher")),
    )
    assert sheet.factor == pytest.approx(1.0)
    assert sheet.reasons == ("理由1", "理由2")
    assert sheet.sources == ("auto", "teacher")
    assert _volumes(sheet) == [("interval_run", 48.0, "min"),
                               ("compound_circuit", 120.0, "reps")] * 4


def test_the_product_keeps_its_float_artifact_like_apply_safety_does():
    """``0.8 × 0.9`` 亲跑就是 ``0.7200000000000001``、**不是** ``0.72``（P5-A6 同一条纪律）。

    ``WeeklySheet.factor`` 是**裸乘积**、不 round：round 一次会让教师端显示的系数与
    ``weekly_volume`` 的实际倍数对不上账（``34.6 / 48.0 = 0.7208…``）。只有
    ``weekly_volume`` 落 ``round(…, 1)``（口径照
    :func:`app.domain.prescription.override._volume_scale`）。

    ⚠️ 本条同时断言它**字面不等于** ``0.72``，把那个看起来像 bug 的尾数钉住，
    免得下一个人「顺手修掉」。
    """
    sheet = weekly_training_sheet(
        _pkg(), 1, _adjustments((1, 0.8, "teacher"), (1, 0.9, "auto")),
    )
    assert sheet.factor == pytest.approx(0.72)
    assert sheet.factor != 0.72
    assert _volumes(sheet) == [("interval_run", 34.6, "min"),
                               ("compound_circuit", 86.4, "reps")] * 4


# ---------------------------------------------------------------------------
# 6. addon 的 "unspecified" 那一档（P8-A2）与 paused（P8-A3）
# ---------------------------------------------------------------------------


def test_the_addon_block_keeps_unspecified_unit_and_zero_volume():
    """**P8-A2（Critical）**：``volume_unit == "unspecified"`` 的 addon block **照原样带出**。

    真仓路径（不是手工构造的 block）：红层 ``RED-END-ABN-01`` + 体成分异常触发 →
    ``apply_safety`` 追加 ``energy_expenditure_plus_10pct``，那一档的 ``weekly_volume``
    恒为 ``0.0``（Addon 没有 ``structure``，量无从算起；编造一个数就是把「不知道」讲成
    「知道」）。追加的 addon **已经在 ``TrainingPackage.weeks`` 里**，故读模型一定会吃到它。

    处置是**不特殊处理**：``0.0 × 0.8 = 0.0``，无副作用。⚠️ 但「结构上支持、逻辑上没测过」
    的路径 Plan 03 一定会撞上（那一档的 ``structure`` 还是个**可变的空 ``dict``**、
    ``intensity_text`` 是那句「附加模块（模板未指定强度，见 spec §14）」），故本条把它的
    六个字段逐个钉住。
    """
    pkg = _addon_pkg()
    sheet = weekly_training_sheet(pkg, 1, _adjustments((1, 0.8, "teacher")))

    addons = [b for b in _blocks(sheet) if b.volume_unit == "unspecified"]
    assert len(addons) == 4, [b.exercise_ref for b in _blocks(sheet)]
    for block in addons:
        assert block.exercise_ref == "energy_expenditure_plus_10pct"
        assert block.weekly_volume == 0.0
        assert block.volume_unit == "unspecified"
        assert block.hr_zone is None
        assert block.sessions_per_week == 4
        assert dict(block.structure) == {}

    # 同一周里三种单位并存 —— 这正是「不提供跨单位周总量」那条决定的数据面根据
    assert {b.volume_unit for b in _blocks(sheet)} == {"min", "reps", "unspecified"}
    # 其余两个 block 照常缩放
    assert _volumes(sheet) == [
        ("interval_run", 38.4, "min"),
        ("compound_circuit", 96.0, "reps"),
        ("energy_expenditure_plus_10pct", 0.0, "unspecified"),
    ] * 4


def test_a_paused_package_keeps_its_sessions_and_reports_paused():
    """**P8-A3**：``paused=True`` → ``sheet.paused is True``，``sessions`` **原样保留**。

    与 Task 5（5.4）``OverrideKind.PAUSE`` 的决定逐字一致：「暂停是可撤销的，删掉 ``weeks``
    就不可逆了」。**不抛 ``ValueError``**——读模型的职责是**投影**、不是校验；抛异常会让
    「暂停」这件事在 API 层变成一个错误分支而不是一份可渲染的数据。

    ⚠️ **「暂停」与「本周量为 0」是两件不同的事**：前者是可撤销的状态、后者是调整结果。
    于是本条**同时**给出后者的对照（``factor = 0.001`` 把量几乎压平），断言两者的
    ``paused`` 一个是 ``True`` 一个是 ``False``——``paused`` 字段的存在就是为了不让前端把
    它们静默合并。
    """
    paused = dataclasses.replace(_pkg(), paused=True)
    sheet = weekly_training_sheet(paused, 1, ())
    assert sheet.paused is True
    assert sheet.sessions == paused.weeks[0].sessions
    assert _volumes(sheet) == [("interval_run", 48.0, "min"),
                               ("compound_circuit", 120.0, "reps")] * 4

    # 对照：暂停 + 减量同时成立时，两件事各自可见、互不掩盖
    both = weekly_training_sheet(paused, 1, _adjustments((1, 0.8, "teacher")))
    assert both.paused is True
    assert both.factor == 0.8

    # 「量为 0」不是「暂停」：亲跑 round(48.0 × 0.001, 1) == 0.0、
    # round(120.0 × 0.001, 1) == 0.1，而 paused 仍是 False。
    # ⚠️ 那个 0.1 顺手把「跨单位的量不可相加」又演了一遍：同一周里 min 那一档被压到 0、
    # reps 那一档还剩 0.1，两个数的单位不同，加起来没有任何意义（P8-A1 后半条）。
    zero = weekly_training_sheet(_pkg(), 1, _adjustments((1, 0.001, "auto")))
    assert zero.paused is False
    assert {b.weekly_volume for b in _blocks(zero)} == {0.0, 0.1}


def test_weekly_training_sheet_does_not_mutate_the_package():
    """纯函数：入参那个 :class:`TrainingPackage` 一个字都不改（口径照 Task 5 的 5.3 / 5.4）。

    ⚠️ 承重的一点是 ``structure``：模板 block 的那一份是 :class:`types.MappingProxyType`
    （改不动），而 **addon block 的那一份是一个普通空 ``dict``**（``types`` 不在 domain 的
    allow-list 里）。故本条**用带 addon 的包**跑，否则「没改 ``structure``」在模板 block 上
    是恒真式。
    """
    pkg = _addon_pkg()

    def dump() -> list:
        return [
            (block.exercise_ref, block.weekly_volume, block.volume_unit,
             block.sessions_per_week, block.hr_zone, dict(block.structure))
            for week in pkg.weeks
            for session in week.sessions
            for block in session.blocks
        ]

    before = dump()
    weekly_training_sheet(pkg, 1, _adjustments((1, 0.8, "auto")))
    assert dump() == before
    assert len(before) == 48          # 4 周 × 4 课 × 3 block（含 addon）
    assert pkg.paused is False
