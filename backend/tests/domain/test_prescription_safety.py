# backend/tests/domain/test_prescription_safety.py
"""spec §7.4 的三触发安全后置 :func:`app.domain.prescription.safety.apply_safety` 的守卫
（Plan 02 Task 5 的 5.3）。

**安全关键，一条不许砍**（简报 Task 5「合并没有砍掉什么」的第 ② 项）：严格比较符 +
「没测不得讲成测了没问题」+「找不到等价动作不得静默跳过」（Review Focus 第 5 条）。

--------------------------------------------------------------------------

**⚠️⚠️ 本文件的第一件事是顶回控制者的一处签名矛盾**（详见报告「关切」节）：

简报 5.3 的 Produces 写的是 ``apply_safety(pkg, inp, eq) -> SafetyOutcome``，而**同一节**的
P5-A3 要求「追加**模板自己的** ``when == "body_fat_over"`` 的 addon」、addon 的
``exercise_name`` / ``video_url`` / ``impact_level`` 「从 ``exercises[addon.module]`` 取」、
``sessions_per_week`` = ``template.weekly_frequency``。**``TrainingPackage`` 里这三样一个都没有**
（它只有 ``template_id`` / ``template_version`` 两个字符串），而 5.3 的等价替换同样需要动作库
——替身的名字、URL 与冲击等级只能从 :class:`ExerciseSpec` 取（P5-A8：读**源**，不读模板副本）。

故落地签名是::

    apply_safety(pkg, inp, eq, *, template: Template, exercises: Mapping[str, ExerciseSpec])

三个位置参数与简报逐字一致，**新增的两个是 keyword-only**（口径照
:func:`app.domain.prescription.assembler.assemble` 的 ``*, exercises``）。代价：调用点要多写
两个实参；收益：P5-A3 这条 Critical 级更正**可实现**，且 ``impact_level`` 仍然只有一个源。

--------------------------------------------------------------------------

**期望值一律字面写死、独立重算**（硬规矩 #35 / #44）。基准包是 ``RED-END-ABN-01`` 用一个
**系数恰为 1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）装配出来的，于是第 1 周
第 1 课的两个 block 的字面量就是 ``base × sessions_per_week``：``interval_run`` = ``12 min × 4``
= **48.0 min**（``impact_level`` 是 ``high``）、``compound_circuit`` = ``30 reps × 4`` =
**120.0 reps**（``medium``）。本机 Python 3.11.1 亲跑的下调后字面值::

    × 0.8（BMI > 30）             interval_run 38.400000000000006 → 38.4   compound_circuit 96.0
    × 0.9（肌肉量 < P10）         interval_run 43.2               → 43.2   compound_circuit 108.0
    × 0.8 × 0.9 = 0.7200000000000001（两个都命中）
                                  interval_run 34.56              → 34.6   compound_circuit 86.4

⚠️ **``0.8 * 0.9`` 亲跑就是 ``0.7200000000000001``、不是 ``0.72``**（P5-A6），故
:func:`test_both_triggers_multiply_the_volume_reduction` **同时**断言两件事：系数用
``pytest.approx(0.72)``、并且它**字面不等于** ``0.72``（把 P5-A6 这个事实钉住，免得下一个人
「顺手修掉」那个看起来像 bug 的尾数）；``weekly_volume`` 一律断言 ``round`` 之后的字面值。

⚠️ **吃真仓 YAML 的测试用三个进程内单例**（P5-A12）：:func:`app.refdata_prescription.exercises`
/ :func:`~app.refdata_prescription.templates` / :func:`~app.refdata_prescription.equivalence`，
不用 ``load_*``（后者每次重解析 18 份 YAML、还各跑一遍 ``yaml.compose`` 建行号索引）。
**单例是进程内共享的，本文件一个字都不改它**：要一张坏等价表一律用
:func:`dataclasses.replace` 造副本。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守 ``volume_reduction`` 那两个系数对不对**：``0.8`` / ``0.9`` 在 spec 里**没有出处**
  （:508 只写「按映射表下调」、没给数；spec 里唯一的「系数 0.8」在 :604，那是 Plan 03 的
  预警减量，是另一个机制）。它们是**工程约定**（spec §14 #28），所有者是
  ``backend/data/exercise_equivalence.yaml``，字面钉住它的测试在
  ``tests/test_refdata_prescription.py``。本文件钉的是「``apply_safety`` 真的把它们乘上去了」。
* **不守「``hiit`` 有等价映射、``energy_expenditure_plus_5min_hiit`` 没有」这个已知不对称**
  （Task 3 记录、本 Task 只复述）：BMI > 30 的黄层学生会「主项被换掉、追加模块原样保留」。
  那是**数据面的事实**，不是代码缺陷。
* **不守 addon ``module`` 不在动作库里的那一档**：简报明写「Task 3 的加载器已校验过它存在，
  故这里**不重复校验**——单一所有者」。于是那一档 surfaces 成 ``KeyError`` 而**不是**
  ``ValueError``（响亮，但异常类型与装配器那三道不一致）。
"""
import dataclasses
import datetime as dt

import pytest

from app import refdata_prescription as rp
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, assemble
from app.domain.prescription.exercises import (
    EQUIVALENCE_TRIGGERS,
    EquivalenceMapping,
    EquivalenceTable,
    ImpactLevel,
)
from app.domain.prescription.safety import (
    SafetyInput,
    SafetyOutcome,
    Substitution,
    apply_safety,
)
from app.domain.prescription.templates import ADDON_TRIGGERS

_AS_OF = dt.date(2026, 10, 6)
_BIRTH = dt.date(2006, 3, 15)

#: ``assemble`` 那 **12** 个键（与 ``tests/domain/test_prescription_assembler.py`` 的
#: :data:`_SNAPSHOT_KEYS` 刻意**各写一份**：两个文件各自独立钉住同一份契约，改一处不改
#: 另一处会红——那正是「一份契约两个守卫」的用意，不是重复。硬规矩 #51）。
_ASSEMBLE_KEYS = (
    "formula", "hrmax", "age", "as_of", "endurance_score", "volume_factor",
    "volume_factor_band", "sex_factor", "template_id", "template_version",
    "week_deltas", "weekly_volume_base",
)

#: ``apply_safety`` 追加的键，**至多 3 个**、名字字面钉死（P5-A7）。
_SAFETY_KEYS = ("safety_triggers", "safety_skipped", "safety_volume_factor")


def _profile(**overrides) -> StudentProfile:
    """系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。"""
    fields = {
        "student_id": 1, "sex": Sex.MALE, "birth": _BIRTH, "age": 20,
        "endurance_score": 70.0, "bmi": None, "body_fat_pct": None,
        "muscle_mass_kg": None, "muscle_p10": None, "measured_hrmax": None,
    }
    fields.update(overrides)
    return StudentProfile(**fields)


def _pkg(template_id: str = "RED-END-ABN-01"):
    """装配一个基准训练包（系数 1.0，故第 1 周的量就是 ``base × sessions_per_week``）。"""
    return assemble(_profile(), rp.templates()[template_id], _AS_OF,
                    exercises=rp.exercises())


def _run(inp: SafetyInput, template_id: str = "RED-END-ABN-01", eq=None) -> SafetyOutcome:
    template = rp.templates()[template_id]
    return apply_safety(_pkg(template_id), inp, rp.equivalence() if eq is None else eq,
                        template=template, exercises=rp.exercises())


def _none_input() -> SafetyInput:
    return SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                       body_fat_abnormal=False)


def _blocks(outcome, week: int = 1, day: int = 1):
    """第 ``week`` 周第 ``day`` 课的 block 序列。收 ``SafetyOutcome`` 或 ``TrainingPackage``。"""
    pkg = getattr(outcome, "package", outcome)
    return pkg.weeks[week - 1].sessions[day - 1].blocks


def _all_blocks(outcome):
    pkg = getattr(outcome, "package", outcome)
    return [b for w in pkg.weeks for s in w.sessions for b in s.blocks]


#: 一张**查不到任何替身**的等价表见 :func:`_empty_table`：用 :func:`dataclasses.replace`
#: 从真表单例造副本（``mappings`` 清空、``version`` 换成 ``"0.0-empty"`` 以便 warning 里能
#: 认出来），故单例一个字都不动。


def _empty_table() -> EquivalenceTable:
    return dataclasses.replace(rp.equivalence(), mappings=(), version="0.0-empty")


def _one_mapping_table() -> EquivalenceTable:
    """只留 ``interval_run → stationary_cycling``（``bmi_over_30``）一条的表。

    ⚠️ 它**一条也命中不了** :func:`test_a_partially_solvable_table_substitutes_what_it_can_and_flags_the_rest`
    用的那套模板（``RED-SPD-ABN-05`` 的两个 high 动作是 ``sprint_50m_intervals`` 与
    ``shuttle_run``，都不是 ``interval_run``）。用它正是为了把「查不到」这一档做出来：
    真表里 5 个 high 动作在两个触发下**都有**映射，故那一档在真数据上不可达。
    ``version`` 换成 ``"0.1-partial"``，于是 warning 里能认出用的是哪一张表。
    """
    return dataclasses.replace(
        rp.equivalence(),
        mappings=(EquivalenceMapping(from_ref="interval_run", to_ref="stationary_cycling",
                                     max_impact=ImpactLevel.LOW, when="bmi_over_30"),),
        version="0.1-partial",
    )


# ---------------------------------------------------------------------------
# 词表漂移（P5-A9：两套不同名的词表，本模块只消费、不定义）
# ---------------------------------------------------------------------------


def test_trigger_word_lists_have_not_drifted():
    """**两条字面断言**钉住上游词表（P5-A9）。

    ``safety.py`` 的 :data:`_TRIGGER_MAP` 是一张**手写的跨表翻译**：它把本模块的三个触发名
    翻成 ``volume_reduction`` 的键（所有者 :mod:`app.domain.prescription.exercises` 的
    :data:`EQUIVALENCE_TRIGGERS`）与 ``addons.when`` 的键（所有者
    :mod:`app.domain.prescription.templates` 的 :data:`ADDON_TRIGGERS`）。
    **两套上游名字完全不同**，故上游一改名，翻译表就会静默失配——``KeyError`` 是响的，
    但「查不到 addon 于是只留一条 warning」是**静默的**。这两条断言就是那道提醒。

    ⚠️ 期望侧字面写死（硬规矩 #35），实际侧才是被测词表；两侧不同源。
    """
    assert ADDON_TRIGGERS == frozenset({"body_fat_over", "muscle_low"})
    assert EQUIVALENCE_TRIGGERS == frozenset({"bmi_over_30", "muscle_low_p10"})
    # 消费侧的翻译表也必须落在上游词表内（左侧读 safety 的私有映射、右侧读两个所有者，
    # 故这一条不是同源比对）。触私有名：本条要比较的正是它（先例是
    # tests/domain/test_percentile.py 里的 `from app.domain.indicators import _lower_is_better`）。
    from app.domain.prescription.safety import _TRIGGER_MAP

    assert set(_TRIGGER_MAP) == {"bmi_over_30", "muscle_low_p10", "body_fat_abnormal"}
    for name, (reduction_key, addon_when) in _TRIGGER_MAP.items():
        assert reduction_key is None or reduction_key in EQUIVALENCE_TRIGGERS, name
        assert addon_when is None or addon_when in ADDON_TRIGGERS, name
    # 真仓的 addons.when 取值域与 ADDON_TRIGGERS 逐字相同（18 套亲扫：各 12 个）
    used = {addon.when for t in rp.templates().values() for addon in t.addons}
    assert used == {"body_fat_over", "muscle_low"}


# ---------------------------------------------------------------------------
# 三个触发 × {命中, 不命中, 恰在边界, 输入缺失}
# ---------------------------------------------------------------------------


def test_no_trigger_at_all_is_a_noop_that_still_appends_the_three_keys():
    """三个输入全缺 → 一个触发都不命中，但**仍然追加那 3 个键**并留痕「为什么没做」。

    **这是「没测不得讲成测了没问题」的落点**（Plan01 Ruling 134 的同一条纪律）：
    ``safety_skipped`` 逐条写明哪个输入缺了，于是一张已生成的处方能回答
    「安全规则是真没命中，还是根本没数据可判」。安全规则**静默跳过比不跳过危险**。
    """
    outcome = _run(_none_input())
    snapshot = outcome.package.assembly_snapshot
    assert snapshot["safety_triggers"] == []
    assert snapshot["safety_skipped"] == [
        "bmi_missing", "muscle_mass_missing", "muscle_p10_missing"]
    assert snapshot["safety_volume_factor"] == 1.0
    assert outcome.substitutions == ()
    assert outcome.needs_review is False
    assert outcome.warnings == ()
    # 训练包本体一个字没变（weeks 逐字段相等）
    assert outcome.package.weeks == _pkg().weeks
    assert _blocks(outcome)[0].weekly_volume == 48.0
    assert [b.exercise_ref for b in _blocks(outcome)] == ["interval_run", "compound_circuit"]


def test_bmi_over_30_reduces_volume_and_substitutes_every_high_impact_block():
    """触发 1：``bmi > 30`` → 跑量 × ``volume_reduction["bmi_over_30"]`` + HIGH 换低冲击。

    ``interval_run``（``impact_level`` 在动作库里是 ``high``）→ ``stationary_cycling``；
    ``compound_circuit``（``medium``）**不动**。量：``48.0 × 0.8 = 38.400000000000006`` →
    ``round(…, 1)`` = **38.4**；``120.0 × 0.8`` = **96.0**。

    ⚠️ 替换记录是**逐 block 实例**的（``Substitution`` 带 ``week`` 与 ``day`` 两个字段）：
    ``interval_run`` 在 ``RED-END-ABN-01`` 里出现 4 周 × 4 课 = **16** 次，故 16 条记录。
    """
    outcome = _run(SafetyInput(bmi=30.1, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False))
    snapshot = outcome.package.assembly_snapshot
    assert snapshot["safety_triggers"] == ["bmi_over_30"]
    assert snapshot["safety_skipped"] == ["muscle_mass_missing", "muscle_p10_missing"]
    assert snapshot["safety_volume_factor"] == pytest.approx(0.8)
    assert outcome.needs_review is False

    substituted, kept = _blocks(outcome)
    assert substituted.exercise_ref == "stationary_cycling"
    assert substituted.impact_level is ImpactLevel.LOW
    assert substituted.exercise_name == rp.exercises()["stationary_cycling"].name
    assert substituted.video_url == rp.exercises()["stationary_cycling"].video_url
    assert substituted.weekly_volume == 38.4
    assert substituted.volume_unit == "min"
    assert kept.exercise_ref == "compound_circuit"
    assert kept.impact_level is ImpactLevel.MEDIUM
    assert kept.weekly_volume == 96.0

    assert len(outcome.substitutions) == 16
    assert {(s.week, s.day) for s in outcome.substitutions} == {
        (week, day) for week in (1, 2, 3, 4) for day in (1, 2, 3, 4)}
    for record in outcome.substitutions:
        assert isinstance(record, Substitution)
        assert record.original_ref == "interval_run"
        assert record.substitute_ref == "stationary_cycling"
        assert record.trigger == "bmi_over_30"
        assert record.equivalence_version == "1.0"
    # 第 4 周同样被下调：40.8 × 0.8 = 32.64 → 32.6
    assert _blocks(outcome, week=4)[0].weekly_volume == 32.6


def test_bmi_exactly_30_does_not_trigger():
    """**恰在边界上不触发**：比较符是严格 ``>``。

    与 Plan 01 的 P25（``score < p25``，spec §14 #21）与体脂率阈值同口径——后者的原文可在
    ``app/domain/derive.py`` 里 grep 到：``BODY_FAT_LIMIT = {Sex.MALE: 20.0,
    Sex.FEMALE: 28.0}``，消费点是 ``body_fat_pct > limit``（**严格大于**，同文件那句注释
    逐字写着「男 > 20%、女 > 28%，**严格大于**」）。
    ``30.0`` 与 ``30.1`` 一起断言，才证明比较符不是 ``>=``。
    """
    boundary = _run(SafetyInput(bmi=30.0, muscle_mass_kg=None, muscle_p10=None,
                               body_fat_abnormal=False))
    assert boundary.package.assembly_snapshot["safety_triggers"] == []
    assert boundary.substitutions == ()
    assert _blocks(boundary)[0].exercise_ref == "interval_run"
    assert _blocks(boundary)[0].weekly_volume == 48.0
    assert boundary.package.assembly_snapshot["safety_volume_factor"] == 1.0
    just_over = _run(SafetyInput(bmi=30.1, muscle_mass_kg=None, muscle_p10=None,
                                body_fat_abnormal=False))
    assert just_over.package.assembly_snapshot["safety_triggers"] == ["bmi_over_30"]


def test_bmi_missing_is_recorded_as_skipped_not_as_clean():
    """``bmi is None`` **不触发**，且在快照里留痕 ``"bmi_missing"``。

    ⚠️ 这一条同时是「一个触发命中、另一个因缺输入跳过」的**并存**档：``muscle_mass_kg``
    24.0 < ``muscle_p10`` 25.0 命中触发 2，而 BMI 那一档因为 ``None`` 被跳过。
    两者都命中的档见 :func:`test_both_triggers_multiply_the_volume_reduction`。
    """
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=24.0, muscle_p10=25.0,
                              body_fat_abnormal=False))
    snapshot = outcome.package.assembly_snapshot
    assert snapshot["safety_triggers"] == ["muscle_low_p10"]
    assert snapshot["safety_skipped"] == ["bmi_missing"]
    assert "muscle_mass_missing" not in snapshot["safety_skipped"]


def test_muscle_below_p10_reduces_volume_substitutes_and_appends_the_addon():
    """触发 2：肌肉量 < 同龄同性别 **P10** → 下调 + 换替身 + **追加 ``muscle_low`` 的 addon**。

    **P5-A3 的更正落地**：原计划判成「无法自动化、只加 warning、置 ``needs_review``」，
    那是错的——真仓 18 套里有 **12** 个 ``when: muscle_low`` / ``module: resistance_priority``
    的 addon（红层 6 + 黄层 6），按原决定它们**永远不会被消费**，是模板里的死数据。
    追加一个 ``resistance_priority`` 模块**不重排任何既有结构**，故它既落地了 spec §7.4
    「并提高抗阻模块比重」，又没有越过「后置处理」的语义边界。

    ⚠️ **``needs_review`` 不由这一条置位**（见
    :func:`test_muscle_trigger_alone_does_not_set_needs_review`）。
    量：``48.0 × 0.9`` = **43.2**、``120.0 × 0.9`` = **108.0**。
    """
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=24.0, muscle_p10=25.0,
                              body_fat_abnormal=False))
    snapshot = outcome.package.assembly_snapshot
    assert snapshot["safety_triggers"] == ["muscle_low_p10"]
    assert snapshot["safety_skipped"] == ["bmi_missing"]
    assert snapshot["safety_volume_factor"] == pytest.approx(0.9)
    assert outcome.needs_review is False

    blocks = _blocks(outcome)
    # 既有 block 的**顺序与身份**全部不变，只有量被下调、HIGH 被换掉
    assert [b.exercise_ref for b in blocks[:2]] == ["stationary_cycling", "compound_circuit"]
    assert blocks[0].weekly_volume == 43.2
    assert blocks[1].weekly_volume == 108.0
    # 追加的 addon 在**末尾**
    assert len(blocks) == 3
    assert blocks[-1].exercise_ref == "resistance_priority"
    assert len(outcome.substitutions) == 16
    assert outcome.substitutions[0].trigger == "muscle_low_p10"


def test_muscle_exactly_at_p10_does_not_trigger():
    """**恰在边界上不触发**：比较符是严格 ``<``（口径同 :func:`test_bmi_exactly_30_does_not_trigger`）。

    ⚠️ 这一格是 P10 而不是 Plan 01 体成分 ``C`` 判定用的 **P20**：spec §7.4 用「肌肉量 < P10」、
    §4.2 的 ``C`` 用「肌肉量 < P20」，**两个阈值不同、分属两个机制，不得混用**
    （``backend/data/exercise_equivalence.yaml`` 的注释里也逐字写了这一条）。
    """
    boundary = _run(SafetyInput(bmi=None, muscle_mass_kg=25.0, muscle_p10=25.0,
                               body_fat_abnormal=False))
    assert boundary.package.assembly_snapshot["safety_triggers"] == []
    assert boundary.substitutions == ()
    assert [b.exercise_ref for b in _blocks(boundary)] == ["interval_run", "compound_circuit"]
    assert len(_blocks(boundary)) == 2
    just_under = _run(SafetyInput(bmi=None, muscle_mass_kg=24.9, muscle_p10=25.0,
                                 body_fat_abnormal=False))
    assert just_under.package.assembly_snapshot["safety_triggers"] == ["muscle_low_p10"]


def test_muscle_inputs_missing_are_both_recorded_as_skipped():
    """``muscle_mass_kg`` 与 ``muscle_p10`` **各自**留痕，缺一个就少一条判据。"""
    only_mass = _run(SafetyInput(bmi=25.0, muscle_mass_kg=30.0, muscle_p10=None,
                                body_fat_abnormal=False))
    assert only_mass.package.assembly_snapshot["safety_skipped"] == ["muscle_p10_missing"]
    assert only_mass.package.assembly_snapshot["safety_triggers"] == []
    only_p10 = _run(SafetyInput(bmi=25.0, muscle_mass_kg=None, muscle_p10=30.0,
                               body_fat_abnormal=False))
    assert only_p10.package.assembly_snapshot["safety_skipped"] == ["muscle_mass_missing"]
    assert only_p10.package.assembly_snapshot["safety_triggers"] == []


def test_body_fat_abnormal_appends_the_template_addon_and_does_not_reduce_volume():
    """触发 3：体脂率异常 → 追加**模板自己的** ``when == "body_fat_over"`` 的 addon。

    **不下调跑量**（:data:`_TRIGGER_MAP` 那一格是 ``(None, "body_fat_over")``）：spec §7.4
    ``:510`` 只说「追加模板 ``addons`` 中的能量消耗模块」，**没有**说下调；而
    ``volume_reduction`` 的键集恰好是 :data:`EQUIVALENCE_TRIGGERS` 那两个
    （加载器 :func:`app.refdata_prescription.load_equivalence` 强制
    ``set(volume_reduction) == EQUIVALENCE_TRIGGERS``），根本没有 ``body_fat_abnormal`` 这一格。

    ⚠️ addon 来自**模板**、不是硬编码：``RED-END-ABN-01`` 的那一个是
    ``energy_expenditure_plus_10pct``（红层 +10% 能量消耗，spec §7.2 ``:482`` 逐字），
    而黄层 6 套的那一个是 ``energy_expenditure_plus_5min_hiit``。
    """
    red = _run(SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                          body_fat_abnormal=True))
    assert red.package.assembly_snapshot["safety_triggers"] == ["body_fat_abnormal"]
    assert red.package.assembly_snapshot["safety_volume_factor"] == 1.0
    assert red.substitutions == ()
    assert red.needs_review is False
    blocks = _blocks(red)
    assert [b.exercise_ref for b in blocks] == [
        "interval_run", "compound_circuit", "energy_expenditure_plus_10pct"]
    # 主项的量一个字没变（这一触发不下调）
    assert blocks[0].weekly_volume == 48.0
    assert blocks[1].weekly_volume == 120.0

    yellow = _run(SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                             body_fat_abnormal=True), template_id="YEL-END-ABN-07")
    assert [b.exercise_ref for b in _blocks(yellow)] == [
        "steady_run", "step_training", "energy_expenditure_plus_5min_hiit"]


def test_body_fat_normal_does_not_trigger():
    """``body_fat_abnormal=False`` → 不追加任何模块（block 数不变）。"""
    outcome = _run(_none_input())
    assert len(_blocks(outcome)) == 2
    assert outcome.package.assembly_snapshot["safety_triggers"] == []


def test_a_green_template_without_addons_only_warns_and_invents_nothing():
    """绿层 6 套全部 ``addons: []``（P5-A3 亲扫坐实）→ **不凭空造模块**，只留一条 warning。

    这是 spec §7.4 ``:510`` 与真数据的冲突（Task 3 已登记）：体脂异常或肌肉量偏低、
    但模板里没有对应 addon 时，造一个模块就等于**代码替专家写模板**；留一条 warning
    让教师看见，才是「宁可不自动，也不要自动错」。
    ``GRN-END-NOR-14`` 亲扫：``addons`` 为空、两个 block（``orienteering`` /
    ``interest_ball_games``）都是 ``medium``，故既无替换也无追加。
    """
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=True), template_id="GRN-END-NOR-14")
    assert outcome.package.assembly_snapshot["safety_triggers"] == ["body_fat_abnormal"]
    assert [b.exercise_ref for b in _blocks(outcome)] == ["orienteering", "interest_ball_games"]
    assert outcome.substitutions == ()
    assert outcome.needs_review is False
    assert len(outcome.warnings) == 1
    assert "GRN-END-NOR-14" in outcome.warnings[0]
    assert "body_fat_over" in outcome.warnings[0]


def test_both_triggers_multiply_the_volume_reduction():
    """**P5-A6**：两个触发都命中 → 系数**相乘**，而 ``0.8 × 0.9`` 不是 ``0.72``。

    三条断言各钉一件事：① 系数用 ``pytest.approx``；② 它**字面不等于** ``0.72``
    （把 IEEE754 那个事实钉住，免得下一个人「顺手修掉」这个看起来像 bug 的尾数——
    ``round`` 掉它会掩盖「系数是乘出来的」这件事）；③ ``weekly_volume`` 断言 ``round``
    之后的**字面值**（``34.6`` / ``86.4``），**不写** ``== 48.0 * 0.72``。
    """
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=24.0, muscle_p10=25.0,
                              body_fat_abnormal=False))
    snapshot = outcome.package.assembly_snapshot
    assert snapshot["safety_triggers"] == ["bmi_over_30", "muscle_low_p10"]
    assert snapshot["safety_volume_factor"] == pytest.approx(0.72)
    assert snapshot["safety_volume_factor"] == 0.7200000000000001
    assert snapshot["safety_volume_factor"] != 0.72
    blocks = _blocks(outcome)
    assert blocks[0].weekly_volume == 34.6      # round(48.0 × 0.7200000000000001, 1)
    assert blocks[1].weekly_volume == 86.4      # round(120.0 × 0.7200000000000001, 1)
    # 追加的 resistance_priority 在末尾，且它的 0.0 × 0.72 仍是 0.0（零副作用）
    assert blocks[-1].exercise_ref == "resistance_priority"
    assert blocks[-1].weekly_volume == 0.0


def test_bmi_over_30_appends_no_addon():
    """**P5-A9**：``bmi_over_30`` 那一格的 addon 键是 ``None`` → **不追加任何模块**。

    实测模板里**没有** ``when: bmi_over_30`` 的 addon（``addons.when`` 的取值域是
    :data:`ADDON_TRIGGERS` = ``{body_fat_over, muscle_low}``），故映射表那一格只能是 ``None``。
    ``RED-END-ABN-01`` 明明**声明了**两个 addon，本条证明它们都没有被这一触发拉出来。
    """
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False))
    assert [b.exercise_ref for b in _blocks(outcome)] == [
        "stationary_cycling", "compound_circuit"]
    assert len(_blocks(outcome)) == 2
    for week in outcome.package.weeks:
        for session in week.sessions:
            assert len(session.blocks) == 2


# ---------------------------------------------------------------------------
# 追加的 addon block 的形状（P5-A3 的追加口径，spec 完全没给 → 登记 §14 新 #35）
# ---------------------------------------------------------------------------


def test_appended_addon_has_zero_volume_and_unspecified_unit():
    """``weekly_volume == 0.0`` + ``volume_unit == "unspecified"`` + 一条点名该 module 的 warning。

    **``0.0`` 是决定、不是偷懒**：``Addon`` 只有 ``when`` / ``module`` 两个字段，没有
    ``structure``、没有 ``intensity``、没有 ``day``，故它的量**无从算起**。三个备选都被否掉：
    ① 按 ref 名字硬编码规则（``…_plus_10pct`` → 周时长总量的 10%）要给 3 个 module 各写
    一条硬编码，**专家加第 4 个 module 就静默失效**，且把量化规则从 ``exercises.yaml`` 手里
    抢走；② 取同 session 内既有 block 的均值——单位可能不同（``min`` vs ``reps``），
    跨单位平均是无意义的数；③ **置 ``0.0`` + ``"unspecified"`` + warning**：spec 没给
    附加模块的量，**编造一个数就是把「不知道」讲成「知道」**（Plan01 Ruling 134 的同一条纪律）。

    ``0.0`` 对下游零副作用：``0.0 × 0.8 = 0.0``（减量乘法）、Task 8 的 ``WeeklySheet``
    缩放同理。教师可以用 ``OverrideKind.VOLUME_SCALE`` 给它一个量。
    """
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=True))
    addon = _blocks(outcome)[-1]
    assert addon.weekly_volume == 0.0
    assert addon.volume_unit == "unspecified"
    assert addon.hr_zone is None
    assert dict(addon.structure) == {}
    assert addon.sessions_per_week == 4          # = template.weekly_frequency
    assert addon.impact_level is ImpactLevel.MEDIUM   # 取自动作库（P5-A8）
    assert addon.exercise_name == rp.exercises()["energy_expenditure_plus_10pct"].name
    assert addon.video_url == rp.exercises()["energy_expenditure_plus_10pct"].video_url
    assert addon.intensity_text == "附加模块（模板未指定强度，见 spec §14）"
    assert any("energy_expenditure_plus_10pct" in w and "0.0" in w
               for w in outcome.warnings), outcome.warnings


def test_appended_addons_go_to_the_end_of_every_session_in_trigger_order():
    """追加到**每一个 session 的 ``blocks`` 末尾**，且**不改变既有 block 的顺序与值**。

    为什么是每一课：``sessions_per_week = template.weekly_frequency``（附加模块每天都做），
    只追加到第 1 课会让它的 ``sessions_per_week`` 字段与它实际出现的课数矛盾。
    追加在**末尾**、既有次序原样，故 :func:`test_apply_safety_does_not_mutate_its_input`
    与 Task 8 的读模型都不受影响。

    两个触发同时命中时，追加序 = :data:`_TRIGGER_MAP` 的迭代序（``muscle_low_p10`` 先于
    ``body_fat_abnormal``），故末尾两块是 ``resistance_priority`` 然后
    ``energy_expenditure_plus_10pct``。**这个序是承重的**（它落进 JSON 列、教师端按它显示），
    故字面钉死。
    """
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=24.0, muscle_p10=25.0,
                              body_fat_abnormal=True))
    before = _pkg()
    for week in outcome.package.weeks:
        for session in week.sessions:
            assert [b.exercise_ref for b in session.blocks] == [
                "stationary_cycling", "compound_circuit",
                "resistance_priority", "energy_expenditure_plus_10pct"]
    # 4 周 × 4 课 × 4 块 = 64；其中两块是追加的 addon → 32 个 addon block
    assert len(_all_blocks(outcome)) == 64
    assert len([b for b in _all_blocks(outcome) if b.volume_unit == "unspecified"]) == 32
    # 既有 block 的 day / focus 全部原样
    assert [(s.day, s.focus) for w in before.weeks for s in w.sessions] == \
        [(s.day, s.focus) for w in outcome.package.weeks for s in w.sessions]


def test_muscle_low_addon_carries_its_own_warning_wording():
    """P5-A3 逐字要求的那条 warning 文本必须出现（它把处置权交回给教师覆盖）。"""
    outcome = _run(SafetyInput(bmi=None, muscle_mass_kg=24.0, muscle_p10=25.0,
                              body_fat_abnormal=False))
    assert any("已追加 resistance_priority 模块" in w and "VOLUME_SCALE" in w
               for w in outcome.warnings), outcome.warnings


def test_muscle_trigger_alone_does_not_set_needs_review():
    """**P5-A3**：``needs_review`` 只在「找不到等价动作」时置位。

    理由：既然已经自动追加了模块，就不存在「宁可不自动」的问题了。原计划把这一条判成
    ``needs_review = True``，那会让**每一个**肌肉量偏低的红/黄层学生都进人工复核队列——
    而复核队列一旦被淹没，真正需要人看的那一档（找不到替身）就没人看了。
    """
    muscle_only = _run(SafetyInput(bmi=None, muscle_mass_kg=24.0, muscle_p10=25.0,
                                  body_fat_abnormal=False))
    assert muscle_only.needs_review is False
    body_fat_only = _run(SafetyInput(bmi=None, muscle_mass_kg=None, muscle_p10=None,
                                    body_fat_abnormal=True))
    assert body_fat_only.needs_review is False


# ---------------------------------------------------------------------------
# Review Focus 第 5 条：找不到等价动作 → 不静默跳过
# ---------------------------------------------------------------------------


def test_missing_equivalent_sets_needs_review_and_keeps_the_block():
    """**Review Focus 第 5 条**（spec §7.4 末段原文）：查不到替身 → ``needs_review = True``、
    写 warning、**该 block 原样保留**。

    **「原样保留」是决定**：删掉动作会让训练量**静默缩水**（教师看到的是一份「看起来正常」
    的训练包，只是少了一块），而保留 + ``needs_review`` 让教师看见。
    warning 里必须写明「哪个动作、哪个触发、映射表版本」——三样都是 spec §7.4 ``:512``
    要求记进 ``prescription.safety_substitutions`` 的字段，缺一件就没法追查。

    ⚠️ 用一张 ``mappings`` 为空的表（:func:`dataclasses.replace` 造副本，真表单例不动）：
    真表里 5 个 high 冲击动作在两个触发下**都有**映射，故这一档在真数据上不可达。
    """
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False), eq=_empty_table())
    assert outcome.needs_review is True
    assert outcome.substitutions == ()
    kept = _blocks(outcome)[0]
    assert kept.exercise_ref == "interval_run"        # 原样保留，没被删、没被换
    assert kept.impact_level is ImpactLevel.HIGH
    assert kept.weekly_volume == 38.4                 # 跑量仍然下调了
    assert len(_blocks(outcome)) == 2
    assert outcome.warnings, "查不到替身却没有 warning，就是静默跳过"
    joined = "\n".join(outcome.warnings)
    assert "interval_run" in joined
    assert "bmi_over_30" in joined
    assert "0.0-empty" in joined


def test_a_partially_solvable_table_substitutes_what_it_can_and_flags_the_rest():
    """同一次调用里「查得到」与「查不到」**并存**：换掉的换掉、查不到的留痕。

    ``RED-SPD-ABN-05`` 第 1 课有三个 block：``sprint_50m_intervals``（high）、
    ``shuttle_run``（high）、``dynamic_stretching``（low）。注入的表只有
    ``interval_run → stationary_cycling`` 一条，故两个 high 动作**都查不到**替身
    → ``needs_review = True``、两条 warning（按 ref 去重）、两个 block 原样保留；
    ``dynamic_stretching`` 是 low，压根不进替换路径。
    """
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False),
                  template_id="RED-SPD-ABN-05", eq=_one_mapping_table())
    assert outcome.needs_review is True
    assert outcome.substitutions == ()
    assert [b.exercise_ref for b in _blocks(outcome)] == [
        "sprint_50m_intervals", "shuttle_run", "dynamic_stretching"]
    warned = "\n".join(outcome.warnings)
    assert "sprint_50m_intervals" in warned
    assert "shuttle_run" in warned
    # 每个查不到的 ref 只留**一条** warning（它在 4 周 × 4 课里出现 16 次，
    # 16 条同样的 warning 会把教师端的复核队列刷成噪音）
    assert len([w for w in outcome.warnings if "sprint_50m_intervals" in w]) == 1


def test_substitution_records_carry_the_equivalence_version():
    """spec §7.4 ``:512`` 明写要记「映射表版本号」：一张已生成的处方能回答
    「当时是按哪一版映射表替换的」。

    ⚠️ 用一张 ``version`` 被换成 ``"9.9"`` 的副本证明这个字段**真的来自注入的表**、
    不是一个写死的字符串（真表的版本恰好是 ``"1.0"``，写死 ``"1.0"`` 的测试对
    「忘了传版本号」这类改法完全无感）。
    """
    table = dataclasses.replace(rp.equivalence(), version="9.9")
    template = rp.templates()["RED-END-ABN-01"]
    outcome = apply_safety(_pkg(), SafetyInput(bmi=31.0, muscle_mass_kg=None,
                                              muscle_p10=None, body_fat_abnormal=False),
                          table, template=template, exercises=rp.exercises())
    assert {r.equivalence_version for r in outcome.substitutions} == {"9.9"}


def test_safety_overrides_the_template():
    """**优先级高于模板定义**（spec §7.4 原文）：模板「明确要」的高冲击动作也必须被换掉。

    ``RED-END-ABN-01`` 的 YAML 里 ``interval_run`` 那一行带着行内注释「供安全后置处理识别」，
    即模板**知道**它是 high 且**仍然**要它（spec §7.2 ``:487`` 的红层耐力参数就是间歇跑）。
    安全规则的优先级高于模板：BMI > 30 的学生拿到的是 ``stationary_cycling``
    （低冲击、保留 60–70% HRmax 的间歇刺激，等价表注释逐字给了这个选择理由）。
    """
    template = rp.templates()["RED-END-ABN-01"]
    assert template.sessions[0].blocks[0].exercise_ref == "interval_run"
    assert rp.exercises()["interval_run"].impact_level is ImpactLevel.HIGH
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False))
    assert _blocks(outcome)[0].exercise_ref == "stationary_cycling"
    # 模板对象本身一个字没变（覆盖发生在训练包上，不在模板上）
    assert rp.templates()["RED-END-ABN-01"].sessions[0].blocks[0].exercise_ref == "interval_run"


def test_the_substitute_inherits_the_original_dose():
    """替身**继承原动作的剂量**：强度文案、心率区间、structure、单位、周课次全部原样。

    这是「换低冲击**等价**动作」的语义：换掉的是冲击，不是训练刺激。等价表的注释逐字写着
    「固定自行车把体重从关节上卸掉，同时**保留 60–70% HRmax 的间歇刺激**」。
    只有 ``weekly_volume`` 跟着跑量下调系数变（它是量、不是刺激形式）。
    """
    before = _blocks(_pkg())[0]
    after = _blocks(_run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                                    body_fat_abnormal=False)))[0]
    assert before.exercise_ref == "interval_run"
    assert after.intensity_text == before.intensity_text
    assert after.hr_zone == before.hr_zone == (116, 136)
    assert dict(after.structure) == dict(before.structure)
    assert after.volume_unit == before.volume_unit == "min"
    assert after.sessions_per_week == before.sessions_per_week == 4
    assert after.weekly_volume == 38.4 and before.weekly_volume == 48.0


# ---------------------------------------------------------------------------
# 快照契约（P5-A7）与纯函数性
# ---------------------------------------------------------------------------


def test_safety_appends_at_most_three_snapshot_keys():
    """**P5-A7**：``assemble`` 那 12 个键**一个都不许改**，``apply_safety`` 至多追加 3 个。

    拆成两段契约的理由：简报原文自相矛盾（5.2 第 6 步说键「字面固定 12 个」并列出 12 个，
    同一节的决定段又要求写 ``"volume_factor_fallback"``、5.3 又要求写 ``"safety_skipped"``
    ——那两个都不在 12 个里）。落地口径是：**12 个是 ``assemble`` 的完整契约**，
    **3 个是安全层的显式追加**，两者各自字面钉死。

    三条断言：① 前 12 个键**名与序**不变；② 追加的恰好是那 3 个、也按这个序；
    ③ 前 12 个键的**值**一个字没被改（安全层不许回头改装配层的账）。
    """
    pkg = _pkg()
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=True))
    snapshot = outcome.package.assembly_snapshot
    assert tuple(snapshot)[:12] == _ASSEMBLE_KEYS
    assert tuple(snapshot)[12:] == _SAFETY_KEYS
    assert len(snapshot) == 15
    for key in _ASSEMBLE_KEYS:
        assert snapshot[key] == pkg.assembly_snapshot[key], key
    # endurance_score is None 时也是 15 个键（band = "unknown" 承载，不加第 13 个）
    unknown = apply_safety(
        assemble(_profile(endurance_score=None), rp.templates()["RED-END-ABN-01"], _AS_OF,
                 exercises=rp.exercises()),
        _none_input(), rp.equivalence(),
        template=rp.templates()["RED-END-ABN-01"], exercises=rp.exercises())
    assert unknown.package.assembly_snapshot["volume_factor_band"] == "unknown"
    assert len(unknown.package.assembly_snapshot) == 15


def test_apply_safety_does_not_mutate_its_input():
    """**纯函数**：传入的 ``TrainingPackage`` 一个字都不改（frozen dataclass + ``replace``）。

    ⚠️ ``assembly_snapshot`` 是 ``dict``（可变），故这一条**不是类型系统白送的**：
    一次 ``pkg.assembly_snapshot["x"] = 1`` 就会污染调用方手里那个包，而
    :func:`app.refdata_prescription.templates` 那个单例是进程内共享的。
    本条用「调用前后逐键比对」证明它没被就地改写。
    """
    pkg = _pkg()
    snapshot_before = dict(pkg.assembly_snapshot)
    weeks_before = dataclasses.replace(pkg)
    template = rp.templates()["RED-END-ABN-01"]
    library_before = {ref: dataclasses.replace(spec)
                      for ref, spec in rp.exercises().items()}
    table_before = dataclasses.replace(rp.equivalence())

    outcome = apply_safety(
        pkg,
        SafetyInput(bmi=31.0, muscle_mass_kg=24.0, muscle_p10=25.0, body_fat_abnormal=True),
        rp.equivalence(), template=template, exercises=rp.exercises())

    assert pkg.assembly_snapshot == snapshot_before
    assert len(pkg.assembly_snapshot) == 12
    assert pkg.weeks == weeks_before.weeks
    assert pkg.paused is False
    assert rp.templates()["RED-END-ABN-01"] == template
    assert len(rp.exercises()) == len(library_before)
    for ref, spec in library_before.items():
        assert rp.exercises()[ref] == spec
    assert rp.equivalence() == table_before
    # 产出的确实是一个**新**包
    assert outcome.package is not pkg
    assert len(outcome.package.assembly_snapshot) == 15


def test_the_outcome_type_is_the_pinned_triple():
    """``SafetyOutcome`` 的四个字段与 ``Substitution`` 的六个字段名逐个字面钉死。

    Task 6 会把 ``substitutions`` 落进 ``prescription.safety_substitutions``、把
    ``needs_review`` 落进 ``prescription.status``、把 ``warnings`` 落进日志，故字段名是
    **跨 Task 的契约**（硬规矩 #11：改了 Interfaces 就要改照抄它的 Step）。
    """
    outcome = _run(SafetyInput(bmi=31.0, muscle_mass_kg=None, muscle_p10=None,
                              body_fat_abnormal=False))
    assert isinstance(outcome, SafetyOutcome)
    assert [f.name for f in dataclasses.fields(SafetyOutcome)] == [
        "package", "substitutions", "needs_review", "warnings"]
    assert [f.name for f in dataclasses.fields(Substitution)] == [
        "week", "day", "original_ref", "substitute_ref", "trigger", "equivalence_version"]
    assert [f.name for f in dataclasses.fields(SafetyInput)] == [
        "bmi", "muscle_mass_kg", "muscle_p10", "body_fat_abnormal"]
    assert isinstance(outcome.substitutions, tuple)
    assert isinstance(outcome.warnings, tuple)
