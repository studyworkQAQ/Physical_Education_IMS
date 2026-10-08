# backend/tests/domain/test_prescription_override.py
"""spec §7.5 的五种教师覆盖 :func:`app.domain.prescription.override.apply_overrides` 的守卫
（Plan 02 Task 5 的 5.4）。

**期望值一律字面写死、独立重算**（硬规矩 #35 / #44）。基准包是 ``RED-END-ABN-01`` 用一个
**系数恰为 1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）装配出来的，故第 1 周
第 1 课的字面量是：``interval_run`` **48.0 min**（``hr_zone`` = ``(116, 136)``）、
``compound_circuit`` **120.0 reps**（``hr_zone`` 是 ``None``），快照里 ``hrmax`` = **194.0**。
覆盖后的字面值本机 Python 3.11.1 亲跑::

    WEEKLY_FREQUENCY 4 → 3   round(48.0 × 3/4, 1) = 36.0    round(120.0 × 3/4, 1) = 90.0
    WEEKLY_FREQUENCY 4 → 2   round(48.0 × 2/4, 1) = 24.0    round(120.0 × 2/4, 1) = 60.0
    VOLUME_SCALE "0.8"       round(48.0 × 0.8, 1) = 38.4
    VOLUME_SCALE "1.2"       round(48.0 × 1.2, 1) = 57.6    round(120.0 × 1.2, 1) = 144.0
    INTENSITY_STEP "-5"      delta = int(-5 × 194.0 / 100.0) = int(-9.7) = **-9**
                             (116, 136) → **(107, 127)**

⚠️ **``apply_overrides`` 也比简报的签名多一个 keyword-only 形参 ``exercises``**（与 5.3 的
:func:`app.domain.prescription.safety.apply_safety` 同一条顶回）：``SUBSTITUTE_EXERCISE`` 要换掉
一个动作，而 :class:`AssembledBlock` 的 ``exercise_name`` / ``video_url`` / ``impact_level``
三个字段**只能从动作库取**（P5-A8：读**源**）。简报给的
``apply_overrides(pkg, records)`` 拿不到它们，于是要么留着旧动作的名字与 URL（一个
**看起来正常**的谎），要么把 ``AssembledBlock`` 的三个字段留空。两者都不可接受，故加形参。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「下次自动生成回到算法基线、不继承覆盖」**（spec §7.5 原文）：那不是本模块的职责，
  而是 Task 6 的触发逻辑——生成时**不读**上一张处方的 override 记录。集成测试归 Task 6。
* **不守 ``teacher_staff_no`` 非空**：简报只要求 ``reason`` 非空，故一个空工号的覆盖记录
  能构造出来、没有任何一条测试会红。
* **不守 ``INTENSITY_STEP`` 对 ``onerm_pct`` / ``rpe`` / ``none`` 三档的作用**：
  ``AssembledBlock`` **不保存** :class:`Intensity`（只保存渲染好的 ``intensity_text`` 与
  ``hr_zone``），故一个「强度档位」的覆盖今天**只能**作用在目标心率区间上。那三档的 block
  原样不动，且**没有 warning 通道**能把这件事说出来（``apply_overrides`` 只返回一个
  ``TrainingPackage``）。已作为关切报出。
"""
import dataclasses
import datetime as dt

import pytest

from app import refdata_prescription as rp
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, TrainingPackage, assemble
from app.domain.prescription.exercises import ImpactLevel
from app.domain.prescription.override import (
    OverrideKind,
    OverrideRecord,
    apply_overrides,
    summarize_overrides,
)

_AS_OF = dt.date(2026, 10, 6)
_BIRTH = dt.date(2006, 3, 15)
_AT = dt.datetime(2026, 10, 6, 9, 0)


def _profile(**overrides) -> StudentProfile:
    """系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。"""
    fields = {
        "student_id": 1, "sex": Sex.MALE, "birth": _BIRTH, "age": 20,
        "endurance_score": 70.0, "bmi": None, "body_fat_pct": None,
        "muscle_mass_kg": None, "muscle_p10": None, "measured_hrmax": None,
    }
    fields.update(overrides)
    return StudentProfile(**fields)


def _pkg() -> TrainingPackage:
    return assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                    exercises=rp.exercises())


def _record(kind: OverrideKind, new_value: str, *, target: str | None = None,
            old_value: str = "", reason: str = "教师面诊后调整",
            applied_at: dt.datetime = _AT) -> OverrideRecord:
    return OverrideRecord(
        kind=kind, target=target, old_value=old_value, new_value=new_value,
        reason=reason, teacher_staff_no="T001", applied_at=applied_at,
    )


def _apply(records) -> TrainingPackage:
    return apply_overrides(_pkg(), records, exercises=rp.exercises())


def _blocks(pkg: TrainingPackage, week: int = 1, day: int = 1):
    return pkg.weeks[week - 1].sessions[day - 1].blocks


# ---------------------------------------------------------------------------
# 词表与字段名（跨 Task 的契约）
# ---------------------------------------------------------------------------


def test_override_kind_has_exactly_the_five_pinned_members():
    """五种 ``kind``、**声明序**照 spec §7.5 的书写序逐字钉死。

    ⚠️ 声明序不是字母序，故 ``sorted(...)`` 这类改法会红。五个成员一个都不能少：
    ``prescription.teacher_overrides`` 那个 JSON 列（Task 6）存的就是 ``kind.value``，
    少一个成员等于少一种教师能做的覆盖。
    """
    assert [member.value for member in OverrideKind] == [
        "weekly_frequency", "substitute_exercise", "intensity_step",
        "volume_scale", "pause"]
    # 继承 str，故 == 字符串直接成立（口径照 ImpactLevel / ReviewStatus / MatchStatus）
    assert OverrideKind.PAUSE == "pause"


def test_override_record_field_names_are_pinned():
    """``OverrideRecord`` 的七个字段名与顺序逐字钉死（Task 6 要按它落 JSON 列）。"""
    assert [f.name for f in dataclasses.fields(OverrideRecord)] == [
        "kind", "target", "old_value", "new_value", "reason",
        "teacher_staff_no", "applied_at"]


def test_empty_reason_is_rejected():
    """``reason`` 不得为空（``OverrideRecord.__post_init__`` 校验 ``reason.strip()``）。

    理由：spec §7.5 末段说这些记录是**研究数据**（「学期末回答教师在哪些环节最不信任
    算法」），一条没有理由的覆盖对研究毫无价值。这与 Plan 01 给 ``WeaknessResult`` 加
    ``count == len(items)`` 不变量是同一个手法。
    ⚠️ 全空格也算空（``strip()``）——那是最常见的「先提交再补理由」的形状。
    """
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(ValueError):
            _record(OverrideKind.PAUSE, "true", reason=bad)
    assert _record(OverrideKind.PAUSE, "true", reason=" 面诊 ").reason == " 面诊 "


def test_no_records_is_a_noop():
    """空列表 → 原样返回（逐字段相等），且**不是同一个对象**（纯函数一律产出新包）。"""
    pkg = _pkg()
    out = apply_overrides(pkg, (), exercises=rp.exercises())
    assert out == pkg
    assert out is not pkg


# ---------------------------------------------------------------------------
# 五种 kind 各一条（命中即可，不做穷举边界）
# ---------------------------------------------------------------------------


def test_weekly_frequency_override_drops_the_extra_days_and_rescales_the_volume():
    """``WEEKLY_FREQUENCY``：保留前 N 课，且**按 N/原课次 重算量**。

    ⚠️ **重算是承重的**：``weekly_volume`` 是**周量**（``base × sessions_per_week × 系数 ×
    delta``），砍掉一课而不改它，那个数就在**撒谎**——教师端会显示「48 分钟/周」而学生
    实际只做 3 课共 36 分钟。故 ``sessions_per_week`` 与 ``weekly_volume`` 一起改。
    ``4 → 3``：``round(48.0 × 3/4, 1) = `` **36.0**、``round(120.0 × 3/4, 1) = `` **90.0**。
    追加的 addon block（``weekly_volume`` 为 ``0.0``）同理不变。
    """
    out = _apply([_record(OverrideKind.WEEKLY_FREQUENCY, "3", old_value="4")])
    assert [len(week.sessions) for week in out.weeks] == [3, 3, 3, 3]
    assert [session.day for session in out.weeks[0].sessions] == [1, 2, 3]
    interval, compound = _blocks(out)
    assert interval.weekly_volume == 36.0
    assert interval.sessions_per_week == 3
    assert compound.weekly_volume == 90.0
    assert compound.sessions_per_week == 3
    # 4 周都被砍（不是只砍第 1 周）：第 4 周 40.8 × 3/4 = 30.6
    assert _blocks(out, week=4)[0].weekly_volume == 30.6
    # 快照一个字没改（覆盖不进快照：那 12 + 3 个键是装配层与安全层的契约）
    assert out.assembly_snapshot == _pkg().assembly_snapshot


def test_weekly_frequency_outside_the_available_range_is_rejected():
    """``n > 该周的课数`` 与 ``n < 1`` 都拒绝，**不静默夹取**。

    模板只有 4 课，算法**造不出**第 5 课（那等于代码替专家写模板）；``0`` 课与
    ``PAUSE`` 是两件事（``PAUSE`` 保留 ``weeks``、可撤销；``0`` 课是一份空训练包）。
    ``int("abc")`` 那一档由 Python 自己抛 ``ValueError``，故也不需要额外一条守卫。
    """
    for bad in ("5", "0", "-1"):
        with pytest.raises(ValueError):
            _apply([_record(OverrideKind.WEEKLY_FREQUENCY, bad, old_value="4")])
    with pytest.raises(ValueError):
        _apply([_record(OverrideKind.WEEKLY_FREQUENCY, "abc", old_value="4")])


def test_substitute_exercise_swaps_ref_name_url_and_impact_from_the_library():
    """``SUBSTITUTE_EXERCISE``：四个字段一起换，且**替身的值取自动作库**。

    ⚠️ 只换 ``exercise_ref`` 而留着旧动作的名字与视频 URL 是一个**看起来正常的谎**
    （学生端点进去看到的是间歇跑的视频、而处方上写着固定自行车），故四个字段
    （``exercise_ref`` / ``exercise_name`` / ``video_url`` / ``impact_level``）必须一起换。
    剂量（强度文案 / 心率区间 / ``structure`` / ``weekly_volume`` / 单位 / 周课次）**原样继承**
    ——与 5.3 的等价替换同一语义：换掉的是动作，不是训练刺激。
    """
    library = rp.exercises()
    out = _apply([_record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking",
                          target="interval_run", old_value="interval_run")])
    substituted, kept = _blocks(out)
    spec = library["brisk_walking"]
    assert substituted.exercise_ref == "brisk_walking"
    assert substituted.exercise_name == spec.name
    assert substituted.video_url == spec.video_url
    assert substituted.impact_level is ImpactLevel.LOW
    assert substituted.intensity_text == _blocks(_pkg())[0].intensity_text
    assert substituted.hr_zone == (116, 136)
    assert substituted.weekly_volume == 48.0
    assert substituted.volume_unit == "min"
    assert substituted.sessions_per_week == 4
    assert kept.exercise_ref == "compound_circuit"
    # 4 周 × 4 课 = 16 个 block 全被换（不只有第 1 课）
    assert len({b.exercise_ref for w in out.weeks for s in w.sessions
                for b in s.blocks}) == 2


def test_substitute_exercise_rejects_an_unknown_ref_on_either_side():
    """**两个方向都要响**：``new_value`` 不在动作库里、``target`` 不在训练包里。

    后一半尤其承重：一个打错的 ``target``（``"interval_runn"``）会让覆盖**静默无事发生**，
    而教师以为自己已经改过了——那正是「静默跳过」在覆盖侧的形状。
    """
    with pytest.raises(ValueError) as new_ref:
        _apply([_record(OverrideKind.SUBSTITUTE_EXERCISE, "no_such_exercise",
                        target="interval_run")])
    assert "no_such_exercise" in str(new_ref.value)
    with pytest.raises(ValueError) as target:
        _apply([_record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking",
                        target="interval_runn")])
    assert "interval_runn" in str(target.value)


def test_intensity_step_shifts_the_hr_zone_and_leaves_the_others_alone():
    """``INTENSITY_STEP``：``new_value`` 是**目标心率区间的百分比点数增量**（可为负）。

    位移量 ``delta = int(step × hrmax / 100)``，``hrmax`` 从 ``assembly_snapshot["hrmax"]`` 读
    （**不重新算**：快照里那个数才是这张处方当初用的值，重算一次就是第二个所有者）。
    ``step = -5``、``hrmax = 194.0`` → ``int(-9.7) = `` **−9** → ``(116, 136)`` 变
    **(107, 127)**（区间**宽度不变**，故不是「重新取整」而是「整体平移」）。

    ⚠️ ``hr_zone is None`` 的 block（``onerm_pct`` / ``rpe`` / ``none`` 三档，真仓 130 个
    block 里 **106** 个）**原样不动**：``AssembledBlock`` 不保存 ``Intensity``，
    「1RM 的 70%」这个数在装配之后已经只剩文案里的字面量，改它就是改一句中文。
    ``intensity_text`` 后面追加一句留痕，于是学生端看到的原文案（模板的意图）与
    覆盖后的 bpm 都在。
    """
    out = _apply([_record(OverrideKind.INTENSITY_STEP, "-5", old_value="0")])
    interval, compound = _blocks(out)
    assert interval.hr_zone == (107, 127)
    assert "教师覆盖" in interval.intensity_text
    assert "107" in interval.intensity_text and "127" in interval.intensity_text
    assert interval.intensity_text.startswith(_blocks(_pkg())[0].intensity_text)
    assert compound.hr_zone is None
    assert compound.intensity_text == _blocks(_pkg())[1].intensity_text
    # 量一个字不变（强度档位与训练量是两个维度）
    assert interval.weekly_volume == 48.0
    # 加号也认（int("+5") == 5）：(116, 136) → int(9.7) = 9 → (125, 145)
    up = _apply([_record(OverrideKind.INTENSITY_STEP, "+5", old_value="0")])
    assert _blocks(up)[0].hr_zone == (125, 145)


def test_intensity_step_rejects_a_zone_that_would_go_non_positive():
    """平移之后低界 ``<= 0`` → 拒绝，**不夹取**。

    ``step = -60``、``hrmax = 194.0`` → ``delta = int(-116.4) = -116`` → 低界 ``116 - 116 = 0``。
    一个 0 bpm 的目标心率区间是荒谬值，而它**看起来完全正常**（两个整数、低界小于高界）；
    口径照 :func:`app.domain.prescription.intensity.hr_zone` 对 ``hrmax_bpm <= 0`` 的拒绝
    （Review Focus 第 4 条：静默产出荒谬值比崩溃危险）。
    """
    with pytest.raises(ValueError):
        _apply([_record(OverrideKind.INTENSITY_STEP, "-60", old_value="0")])
    # -59 仍合法：delta = int(-114.46) = -114 → 低界 2
    assert _blocks(_apply([_record(OverrideKind.INTENSITY_STEP, "-59", old_value="0")]))[0] \
        .hr_zone == (2, 22)


def test_volume_scale_multiplies_the_weekly_volume_of_the_target_only():
    """``VOLUME_SCALE``：``new_value`` 是一个乘数字符串（``"0.8"``）。

    **``target`` 非空时只作用于那一个动作**：``round(48.0 × 0.8, 1) = `` **38.4**，
    而同课的 ``compound_circuit`` 一个字不变（**120.0**）。
    乘的是 ``weekly_volume``，``volume_unit`` / ``sessions_per_week`` / ``structure`` 都不动
    ——「整体降量」降的是量，不是频次。
    """
    out = _apply([_record(OverrideKind.VOLUME_SCALE, "0.8", target="interval_run",
                          old_value="1.0")])
    interval, compound = _blocks(out)
    assert interval.weekly_volume == 38.4
    assert compound.weekly_volume == 120.0
    assert interval.volume_unit == "min"
    assert interval.sessions_per_week == 4
    # 4 周都缩放：第 4 周 40.8 × 0.8 = 32.64 → 32.6
    assert _blocks(out, week=4)[0].weekly_volume == 32.6


def test_volume_scale_without_a_target_scales_every_block():
    """``target is None`` → **整体**降量/加量（spec §7.5 的原文是「整体降量/加量」）。

    ``"1.2"``：``round(48.0 × 1.2, 1) = `` **57.6**、``round(120.0 × 1.2, 1) = `` **144.0**。
    ⚠️ **加量是合法的**（``> 1`` 不拒绝）：``volume_reduction`` 那两个系数被加载器限制在
    ``(0.0, 1.0)`` 内（``> 1`` 是「安全触发反而加量」），而**教师覆盖**不是安全触发——
    一个恢复得快的学生可以被教师加量。故本模块只拒绝 ``<= 0``。
    """
    out = _apply([_record(OverrideKind.VOLUME_SCALE, "1.2", old_value="1.0")])
    interval, compound = _blocks(out)
    assert interval.weekly_volume == 57.6
    assert compound.weekly_volume == 144.0


def test_volume_scale_rejects_a_non_positive_factor_and_an_unknown_target():
    """``<= 0`` 的乘数拒绝（``0`` 是把训练量清零、处方名存实亡；负数没有物理意义），
    打错的 ``target`` 也拒绝（**不静默无事发生**）。"""
    for bad in ("0", "-0.5", "0.0"):
        with pytest.raises(ValueError):
            _apply([_record(OverrideKind.VOLUME_SCALE, bad)])
    with pytest.raises(ValueError) as excinfo:
        _apply([_record(OverrideKind.VOLUME_SCALE, "0.8", target="interval_runn")])
    assert "interval_runn" in str(excinfo.value)


def test_pause_keeps_the_weeks_and_sets_the_flag():
    """``PAUSE``：**原样保留 ``weeks``**、把 ``paused`` 置 ``True``。

    「暂停」是**可撤销**的，删掉 ``weeks`` 就不可逆了（简报 5.4 的决定原文）。
    撤销 = Task 6 再跑一次生成（下次自动生成回到算法基线、不继承覆盖，spec §7.5）。
    """
    pkg = _pkg()
    out = _apply([_record(OverrideKind.PAUSE, "true", old_value="false")])
    assert out.paused is True
    assert out.weeks == pkg.weeks
    assert out.template_id == pkg.template_id
    assert out.assembly_snapshot == pkg.assembly_snapshot
    assert pkg.paused is False       # 入参没被就地改


# ---------------------------------------------------------------------------
# 顺序、纯函数性、汇总
# ---------------------------------------------------------------------------


def test_override_records_are_applied_in_list_order_not_by_applied_at():
    """**多条覆盖同一目标 → 由列表顺序决定，后者胜**（不用 ``applied_at``）。

    理由（简报 5.4 的决定原文）：同一秒批量操作时 ``applied_at`` 相等，而调用方持有真实顺序。
    本条把两种顺序的**结果差异**做出来：列表是 ``["3"（applied_at 09:00）, "2"（08:00）]``，
    按列表序得到 **2 课 / 24.0 min**；按 ``applied_at`` 序则先砍到 2 课、再想砍到 3 课
    ——那一档 ``3 > 2`` 会 ``ValueError``。两种顺序**一个成功一个报错**，故本条对
    「改成按 ``applied_at`` 排序」这个改法是真的有牙。
    """
    late = _record(OverrideKind.WEEKLY_FREQUENCY, "3", old_value="4",
                   applied_at=dt.datetime(2026, 10, 6, 9, 0))
    early = _record(OverrideKind.WEEKLY_FREQUENCY, "2", old_value="3",
                    applied_at=dt.datetime(2026, 10, 6, 8, 0))
    out = _apply([late, early])
    assert [len(week.sessions) for week in out.weeks] == [2, 2, 2, 2]
    assert _blocks(out)[0].weekly_volume == 24.0
    assert _blocks(out)[0].sessions_per_week == 2
    with pytest.raises(ValueError):
        _apply([early, late])


def test_a_substitution_chain_is_applied_in_order():
    """``A → B`` 再 ``B → C`` 得到 ``C``：链式覆盖只有在列表序下才走得通。

    这是「顺序承重」的第二个证据（第一个是
    :func:`test_override_records_are_applied_in_list_order_not_by_applied_at`）：
    反过来写 ``[B → C, A → B]`` 会在第一条就 ``ValueError``，因为 ``B`` 那时还不在包里。
    """
    out = _apply([
        _record(OverrideKind.SUBSTITUTE_EXERCISE, "stationary_cycling",
                target="interval_run"),
        _record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking",
                target="stationary_cycling"),
    ])
    assert _blocks(out)[0].exercise_ref == "brisk_walking"
    with pytest.raises(ValueError):
        _apply([
            _record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking",
                    target="stationary_cycling"),
            _record(OverrideKind.SUBSTITUTE_EXERCISE, "stationary_cycling",
                    target="interval_run"),
        ])


def test_an_unknown_override_kind_is_rejected():
    """``kind`` 落在五个成员之外 → ``ValueError``，**不静默忽略**。

    ``OverrideRecord`` 是 frozen dataclass、构造期只校验 ``reason``，故一个
    ``kind="teleport"`` 的记录**能构造出来**（``OverrideKind`` 继承 ``str``，
    而字段标注不是运行时约束）。静默忽略它 = 教师以为改过了、而处方一个字没变。
    """
    with pytest.raises(ValueError) as excinfo:
        _apply([_record("teleport", "1")])
    assert "teleport" in str(excinfo.value)


def test_apply_overrides_does_not_mutate_the_template_or_the_package():
    """**覆盖不修改模板**（spec §7.5 原文），也不修改传入的训练包：两者都是纯函数入参。

    ⚠️ 模板那半句在真仓上是**双重保证**的：``apply_overrides`` 的签名里根本没有
    ``Template``，且 :func:`app.refdata_prescription.templates` 返回的是
    ``MappingProxyType`` + frozen dataclass。本条仍然断言一次，因为「签名里没有」是
    **今天**的事实，而 ``test_override_does_not_mutate_the_template`` 这个名字是留给
    下一个想加形参的人看的。
    """
    pkg = _pkg()
    template_before = rp.templates()["RED-END-ABN-01"]
    library_before = {ref: dataclasses.replace(spec)
                      for ref, spec in rp.exercises().items()}
    snapshot_before = dict(pkg.assembly_snapshot)

    out = _apply([
        _record(OverrideKind.WEEKLY_FREQUENCY, "3", old_value="4"),
        _record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking", target="interval_run"),
        _record(OverrideKind.VOLUME_SCALE, "0.8"),
        _record(OverrideKind.PAUSE, "true"),
    ])

    assert out is not pkg
    assert pkg.weeks == _pkg().weeks
    assert pkg.paused is False
    assert pkg.assembly_snapshot == snapshot_before
    assert len(pkg.weeks[0].sessions) == 4
    assert rp.templates()["RED-END-ABN-01"] == template_before
    assert rp.templates()["RED-END-ABN-01"].weekly_frequency == 4
    for ref, spec in library_before.items():
        assert rp.exercises()[ref] == spec
    # 四条覆盖都生效了（顺序：砍课 → 换动作 → 整体缩到 0.8 → 暂停）
    assert out.paused is True
    assert [len(week.sessions) for week in out.weeks] == [3, 3, 3, 3]
    assert _blocks(out)[0].exercise_ref == "brisk_walking"
    # 36.0（砍到 3 课）× 0.8 = 28.8
    assert _blocks(out)[0].weekly_volume == 28.8


def test_summarize_overrides_counts_by_kind():
    """按 ``kind`` 计数，**期望 dict 字面写死**。

    它是 spec §7.5 末段「学期末回答教师在哪些环节最不信任算法」的输入：五档计数一比，
    哪一档被覆盖得最多就是算法在那一环最不被信任。
    键是 ``kind.value``（``str``）而不是枚举成员本身：这个 dict 要落进 JSON。
    **只出现过的档才有键**（不补 0），于是「一档都没被覆盖过」与「覆盖过但计数为 0」
    在数据上分得开——后者不可能发生，前者是一个真实且有意义的观测。
    """
    records = [
        _record(OverrideKind.VOLUME_SCALE, "0.8"),
        _record(OverrideKind.VOLUME_SCALE, "0.9"),
        _record(OverrideKind.PAUSE, "true"),
        _record(OverrideKind.SUBSTITUTE_EXERCISE, "brisk_walking", target="interval_run"),
    ]
    assert summarize_overrides(records) == {
        "pause": 1, "substitute_exercise": 1, "volume_scale": 2}
    assert summarize_overrides([]) == {}
    assert list(summarize_overrides(records)) == [
        "pause", "substitute_exercise", "volume_scale"]
