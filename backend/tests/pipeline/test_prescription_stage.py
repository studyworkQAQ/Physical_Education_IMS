# backend/tests/pipeline/test_prescription_stage.py
"""处方生成阶段（:mod:`app.pipeline.prescription_stage`）与它所依赖的输入扩容的守卫（Plan 02 Task 7）。

本文件分两大节，各自钉一件不同的事（硬规矩 #56：一条测试一个主语）：

* **A 节（P7-A1 / P7-A2 / P7-A3）**：``run_stratify.PersonInputs`` 的三个新字段、
  ``input_snapshot_of`` 的两个新键、``resolve_muscle_lines`` 的 P10 回填，以及
  **P10 绝不进分层判定**这条红线的行为守卫。这一节改的是 **Plan 01 已结案的代码**，
  故它的价值主要是「不回归」——13 例黄金用例与 500 人分布测试全绿只证明标签没变，
  证明不了「新加的那一档没有被谁顺手读进判定里」。
* **B 节（Task 7 本体）**：``generate_prescriptions`` 的落库、幂等、异常分层、
  ``skipped_reasons`` 的可交代性，以及 ``_replay_cleanup`` 清单里那两张新表的
  **删除顺序**（P7-A4：``weekly_adjustment`` 有 FK 指向 ``prescription``，
  SQLite 跑在 ``PRAGMA foreign_keys=ON`` 下，先删父表当场违例）。

**期望侧一律字面写死**（硬规矩 #35 / Global Constraint #4）：字段名、键名、键数、
BMI 值、日期都写在测试里，不从被测模块反推。
"""
import dataclasses
import datetime as dt

import pytest

from app.domain.indicators import AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex
from app.domain.percentile import (
    MIN_SAMPLE, MUSCLE_MASS, PercentileRow, SnapshotMetric,
)
from app.domain.stratify import stratify
from app.pipeline import run_stratify
from app.pipeline.run_stratify import (
    PersonInputs, input_snapshot_of, resolve_muscle_lines,
)

LOWER_GRADE, UPPER_GRADE = AGE_GROUPS      # "大一、大二" / "大三、大四"

#: ``PersonInputs`` 的 15 个字段名，**逐字写死**。前 12 个与
#: :func:`app.domain.derive.derive` 的参数顺序一一对应（Plan 01 的既有契约），
#: 后 3 个是 Plan 02 Task 7 加的、``derive`` **一个都不读**（P7-A1 / P7-A3）。
#: ⚠️ 数法用运行时口径 ``len(dataclasses.fields(...))``，不用正则数源码（硬规矩 #89）。
_PINNED_PERSON_FIELDS = (
    "student_id", "sex", "age_group", "prev_age_group", "curr_scores", "prev_scores",
    "curr_total", "prev_total", "years", "body_fat_pct", "muscle_mass_kg",
    "snapshot_muscle_p20", "height_cm", "weight_kg", "snapshot_muscle_p10",
)

#: ``input_snapshot_of`` 的 28 个顶层键 = Plan 01 的 26 个 + Task 7 的 ``bmi`` 与
#: ``snapshot_muscle_p10``。**逐字写死**，且**排序后**比较（``input_snapshot_of`` 的
#: 书写序不由任何断言钉住，钉的是键集）。
_PINNED_SNAPSHOT_KEYS = (
    "C", "W", "age_group", "annual_change", "bmi", "body_comp_reasons", "body_fat_limit",
    "body_fat_pct", "curr_scores", "curr_total", "dominant_bucket", "hit_rules", "label",
    "muscle_mass_kg", "national_total", "p25_lines", "percentile_source", "prev_age_group",
    "prev_scores", "prev_total", "reason", "sex", "snapshot_muscle_p10",
    "snapshot_muscle_p20", "trend", "valid_count", "weakness_items", "years",
)

#: 一条男性肌肉量快照行的两档判定线。**两个值刻意差得远**（P10 = 25.5 / P20 = 30.0）：
#: 若 ``resolve_muscle_lines`` 或 ``lookup_p10`` 抄串了列，两档会给出同一个数，
#: 下面那些 ``==`` 断言当场红。
_MUSCLE_P10, _MUSCLE_P20 = 25.5, 30.0


def _person(**overrides) -> PersonInputs:
    """一个「六项短板全有得分、体成分不缺」的男性学生，``**overrides`` 逐字段覆盖。

    ``curr_scores`` 六项一律 **30 分**（< 下面的 P25 = 50），故 ``W = 6``、
    ``valid_count = 6``（远过 Z0 闸门的 4 项）；主导桶按
    :data:`app.domain.derive._BUCKET_ORDER`（endurance → strength → speed_flexibility）
    取 endurance（两项）。**必须是一个非 ``insufficient_data`` 的标签**：全员 Z0 的话
    「P10 不进分层判定」这条守卫会空转（两个都 ``insufficient_data``，恒相等）。
    """
    values = dict(
        student_id=1,
        sex=Sex.MALE,
        age_group=LOWER_GRADE,
        prev_age_group=LOWER_GRADE,
        curr_scores={
            ScoredItem.BMI: None,
            **{item: 30 for item in WEAKNESS_ITEMS},
        },
        prev_scores=None,
        curr_total=None,
        prev_total=None,
        years=1.0,
        body_fat_pct=15.0,
        muscle_mass_kg=50.0,
        snapshot_muscle_p20=None,
        height_cm=172.5,
        weight_kg=65.0,
        snapshot_muscle_p10=None,
    )
    values.update(overrides)
    return PersonInputs(**values)


def _snapshot(muscle_p10: float = _MUSCLE_P10) -> list[PercentileRow]:
    """六个短板项各一行 P25 = 50 的校内行 + 一行男性肌肉量（P10 / P20 见上）。

    **手工构造 ``PercentileRow``、不经 ``compute_snapshot``**：本节的被测对象是
    ``PersonInputs`` → ``input_snapshot_of`` → 分层这条链，不是分位数算法；手工行让
    「P25 = 50、肌肉量 P10 = 25.5」这两个期望值独立于 numpy（硬规矩 #35）。
    """
    rows = [
        PercentileRow(
            item=SnapshotMetric(item.value), sex=Sex.MALE, age_group=LOWER_GRADE,
            p10=40.0, p20=45.0, p25=50.0, p50=60.0, p75=70.0,
            sample_size=MIN_SAMPLE, source="school",
        )
        for item in WEAKNESS_ITEMS
    ]
    rows.append(
        PercentileRow(
            item=SnapshotMetric(MUSCLE_MASS), sex=Sex.MALE, age_group=LOWER_GRADE,
            p10=muscle_p10, p20=_MUSCLE_P20, p25=0.0, p50=0.0, p75=0.0,
            sample_size=MIN_SAMPLE, source="school",
        )
    )
    return rows


def _verdict(person: PersonInputs, snapshot: list[PercentileRow]) -> dict:
    """一个人的分层结论（:func:`app.pipeline.run_stratify.result_dict` 的那 10 个键）。"""
    evaluated = run_stratify.evaluate([person], snapshot)[0]
    return run_stratify.result_dict(evaluated, stratify(evaluated.derived), snapshot)


def _snapshot_of(person: PersonInputs, snapshot: list[PercentileRow]) -> dict:
    """一个人的 ``stratification_result.input_snapshot``（28 个键）。"""
    evaluated = run_stratify.evaluate([person], snapshot)[0]
    return input_snapshot_of(evaluated, stratify(evaluated.derived), snapshot)


# ---------------------------------------------------------------------------
# A 节：P7-A1 / P7-A2 / P7-A3 —— PersonInputs 三字段、input_snapshot 两键、P10 红线
# ---------------------------------------------------------------------------


def test_person_inputs_gains_exactly_the_three_prescription_fields():
    """15 个字段、顺序逐字钉死；后三个是 Task 7 加的，``derive`` 一个都不读。

    ⚠️ **这一条同时是「P10 不进分层」的静态一半**：``evaluate`` 按关键字把
    ``PersonInputs`` 展开成 ``derive`` 的 11 个参数，而 ``derive`` 的形参里没有任何
    分位名除 ``snapshot_muscle_p20`` 之外（守卫
    ``tests/domain/test_derive.py::test_smi_is_not_an_input_at_all``）。新字段挂在
    ``PersonInputs`` 上**不等于**它进了判定——行为侧那一半见
    :func:`test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict`。
    """
    names = tuple(field.name for field in dataclasses.fields(PersonInputs))
    assert len(names) == 15, f"实测 {len(names)} 个字段: {names}"
    assert names == _PINNED_PERSON_FIELDS
    # 前 12 个仍是 derive 的参数序（Plan 01 的既有契约没被打乱）
    assert names[:12] == _PINNED_PERSON_FIELDS[:12]
    # 三个新字段**一律没有缺省**，与既有的 snapshot_muscle_p20 同口径：构造点必须显式
    # 说出这三个值。给缺省的后果是「漏改一个构造点」静默变成 None（P7-A1 实测构造点
    # 只有 3 处，一处漏了就是那一整条路径的 BMI 恒为 None、安全触发永不成立且不报错）。
    # ⚠️ 「缺省 None」是 P7-A2 里 ``case.get(...)`` 的缺省，不是 dataclass 字段的缺省。
    no_default = {
        field.name for field in dataclasses.fields(PersonInputs)
        if field.default is dataclasses.MISSING
    }
    assert {"height_cm", "weight_kg", "snapshot_muscle_p10"} <= no_default


def test_input_snapshot_gains_the_raw_bmi_and_the_p10_line():
    """28 个键 = Plan 01 的 26 个 + ``bmi``（**原始值**）+ ``snapshot_muscle_p10``。

    ``bmi`` 那一格是 spec §7.4 安全触发「BMI > 30」要的**原始值**，不是国标得分
    （P7-A9：``bmi_of`` 的 docstring 早已预写了这个用途）。今天 ``curr_scores["bmi"]``
    存的是**得分**，两个键并存不冲突：一个是判分用的、一个是安全后置用的。
    ``172.5 cm / 65.0 kg`` → ``round(65.0 / 1.725², 1)`` = **21.8**（字面写死）。
    """
    snapshot = _snapshot()
    person = resolve_muscle_lines([_person(snapshot_muscle_p10=None)], snapshot)[0]
    evaluated = run_stratify.evaluate([person], snapshot)[0]
    got = input_snapshot_of(evaluated, stratify(evaluated.derived), snapshot)

    assert len(got) == 28, f"实测 {len(got)} 个键: {sorted(got)}"
    assert tuple(sorted(got)) == _PINNED_SNAPSHOT_KEYS
    assert got["bmi"] == 21.8
    assert got["curr_scores"]["bmi"] is None, "BMI 得分与 BMI 原始值是两个键，别混"
    # P20 与 P10 同时落进快照，且**两档不同**（抄串列的话这两个值会相等）
    assert got["snapshot_muscle_p20"] == _MUSCLE_P20
    assert got["snapshot_muscle_p10"] == _MUSCLE_P10


def test_input_snapshot_bmi_is_none_when_height_or_weight_is_missing():
    """身高或体重缺测 → ``bmi`` 是 ``None``，**绝不当 0**（Ruling 21）。

    ``bmi_of`` 的签名实测是 ``(float | None, float | None) -> float | None``；本条钉住
    ``input_snapshot_of`` 真的把 ``None`` 透传下来了，而不是在半路上被 ``or 0`` 一类
    的写法吃掉——一个 ``bmi = 0`` 的快照会让安全触发判成「0 > 30 为假」，
    于是一个身高体重缺失的学生**静默**躲过 BMI 那一档复核。
    """
    snapshot = _snapshot()
    for overrides in ({"height_cm": None}, {"weight_kg": None},
                      {"height_cm": None, "weight_kg": None}):
        person = _person(**overrides)
        evaluated = run_stratify.evaluate([person], snapshot)[0]
        got = input_snapshot_of(evaluated, stratify(evaluated.derived), snapshot)
        assert got["bmi"] is None, overrides


def test_resolve_muscle_lines_backfills_p20_and_p10_together():
    """**一次** ``resolve_muscle_lines`` 同时回填两档；查不到时两档一起保持 ``None``。

    两条路径（内存的 ``_from_dataset`` 与 DB 的 ``daily.py``）共用这一个回填函数，
    故不可能一处查表、另一处凭空给值（Ruling 102 的缺陷形态）。⚠️ 「同时」是承重的：
    只回填 P20 的话，``snapshot_muscle_p10`` 在 DB 路径上恒为 ``None``、
    spec §7.4 的肌肉量安全触发**永不成立**，而全链路不报错。
    """
    snapshot = _snapshot()
    resolved = resolve_muscle_lines(
        [_person(snapshot_muscle_p20=None, snapshot_muscle_p10=None)], snapshot
    )[0]
    assert resolved.snapshot_muscle_p20 == _MUSCLE_P20
    assert resolved.snapshot_muscle_p10 == _MUSCLE_P10

    # 该组没有肌肉量行（样本 < MIN_SAMPLE）→ 两档都是 None，不是 0、也不是 P25
    empty = resolve_muscle_lines(
        [_person(snapshot_muscle_p20=None, snapshot_muscle_p10=None)], []
    )[0]
    assert empty.snapshot_muscle_p20 is None
    assert empty.snapshot_muscle_p10 is None

    # 回填是 dataclasses.replace（产出新对象），不是就地改写：入参那份一个字没动
    original = _person(snapshot_muscle_p20=None, snapshot_muscle_p10=None)
    resolve_muscle_lines([original], snapshot)
    assert original.snapshot_muscle_p20 is None and original.snapshot_muscle_p10 is None


def test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict():
    """⚠️ **P7-A3 的红线**：改 ``snapshot_muscle_p10`` 的值，分层结论**一个字都不变**。

    这条守卫钉的是「P10 只服务 spec §7.4 的处方安全触发，绝不进分层判定」。
    三档取值刻意拉开（远低于 / 恰好等于 / 远高于本人的肌肉量 ``50.0 kg``）：
    谁把 P10 接进 ``flag_body_comp`` 或 ``derive``，``24.0`` 那一档会让 ``C`` 翻成
    ``True``、标签从红变黄，本条当场红——而那会改掉 Plan 01 已结案的标签、
    让 13 例黄金用例一起红。

    **对照 ``snapshot_muscle_p20``**（最后一段）：它**是**判定输入，改它必须改结论。
    没有这一段，本条会被一次「把所有分位输入都拔掉」的改动骗过（假绿比假红更危险）。
    """
    snapshot = _snapshot()
    # 先走一遍生产回填拿到「解析完」的那个人，再**只**换 snapshot_muscle_p10 这一个字段。
    # ⚠️ 不能在换之前/之后再调 resolve_muscle_lines：它会按快照把 P10 覆盖回 25.5，
    # 三档取值于是塌成同一个数，本条会假绿（这正是它要抓的缺陷形态）。
    resolved = resolve_muscle_lines([_person()], snapshot)[0]
    assert resolved.snapshot_muscle_p10 == _MUSCLE_P10

    p10_values = (24.0, 50.0, 999.0)
    baseline = _verdict(dataclasses.replace(resolved, snapshot_muscle_p10=24.0), snapshot)
    assert baseline["label"] != "insufficient_data", "全员 Z0 的话本条空转"
    assert baseline["C"] is False
    for p10 in p10_values:
        verdict = _verdict(
            dataclasses.replace(resolved, snapshot_muscle_p10=p10), snapshot
        )
        assert verdict == baseline, f"snapshot_muscle_p10={p10} 改了分层结论: {verdict}"

    # 快照里**唯一**变的那一格就是它自己（可追溯性没有连带失真）
    snap_a = _snapshot_of(dataclasses.replace(resolved, snapshot_muscle_p10=24.0), snapshot)
    snap_b = _snapshot_of(dataclasses.replace(resolved, snapshot_muscle_p10=999.0), snapshot)
    assert sorted(snap_a) == sorted(snap_b)
    assert [key for key in snap_a if snap_a[key] != snap_b[key]] == ["snapshot_muscle_p10"]

    # 反面对照：P20 **是**判定输入，把它抬到 60.0（> 本人的 50.0 kg）必须让 C 翻真。
    # 没有这一段，一次「把所有分位输入都拔掉」的改动能让上面三档全部恒等而骗过本条。
    flipped = _verdict(
        dataclasses.replace(resolved, snapshot_muscle_p20=60.0), snapshot
    )
    assert flipped["C"] is True
    # 文案里的「P20」而不是 reason token「muscle_low」：explain 渲染的是给人看的那一句
    assert "肌肉量低于同龄同性别 P20" in flipped["explain"]
    assert flipped != baseline


def test_golden_case_path_defaults_the_three_new_inputs_to_none():
    """**P7-A2**：黄金用例路径对三个新字段一律用 ``case.get(...)``，缺省 ``None``。

    ``golden_cases.json`` 的 13 例今天**没有** ``height_cm`` / ``weight_kg`` /
    ``snapshot_muscle_p10`` 三个顶层键（它们在 ``curr`` / ``prev`` 子映射里、不是顶层），
    而既有那一行写的是硬下标 ``case["snapshot_muscle_p20"]``。照同样写法加新字段会让
    13 例当场 ``KeyError`` —— 而那份夹具是 **Task 9** 才改的文件。

    ⚠️ **不许改夹具**：本条用一份**手工构造、刻意缺这三键**的用例来钉，不碰
    ``tests/fixtures/golden_cases.json``。Task 9 给 13 例补上身高体重之后本条**仍然绿**
    （它断言的是「缺键时不炸、退化成 ``None``」，不是「夹具缺键」）。
    """
    case = {
        "student_id": "NOHW",
        "sex": "male",
        "age": 19,
        "years": 1.0,
        "snapshot_muscle_p20": 33.2,
        "body_comp": {"body_fat_pct": 22.4, "muscle_mass_kg": 45.0, "smi": None},
        "curr": {
            "height_cm": 175.0, "weight_kg": 78.0, "vital_capacity_ml": 3200.0,
            "sprint_50m_s": 9.5, "sit_and_reach_cm": 5.0, "standing_jump_cm": 180.0,
            "strength_count": 5.0, "distance_run_s": 300.0,
        },
    }
    for absent in ("height_cm", "weight_kg", "snapshot_muscle_p10"):
        assert absent not in case, "夹具形状变了的话本条要重写（P7-A2）"

    persons, snapshot = run_stratify._from_golden_cases([case])
    assert len(persons) == 1
    person = persons[0]
    # 顶层缺这三键 → 一律 None；⚠️ 注意 curr 里**有** height_cm/weight_kg，
    # 但那是算 BMI **得分**用的原始测量，不是 PersonInputs 的顶层输入（P7-A2 的口径）
    assert person.height_cm is None
    assert person.weight_kg is None
    assert person.snapshot_muscle_p10 is None
    # 既有的那一档没被顺手改掉：P20 仍取夹具手工给定的值
    assert person.snapshot_muscle_p20 == 33.2

    evaluated = run_stratify.evaluate(persons, snapshot)[0]
    got = input_snapshot_of(evaluated, stratify(evaluated.derived), snapshot)
    assert got["bmi"] is None
    assert got["snapshot_muscle_p10"] is None
