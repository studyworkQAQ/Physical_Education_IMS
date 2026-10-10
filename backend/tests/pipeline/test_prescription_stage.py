# backend/tests/pipeline/test_prescription_stage.py
"""处方生成阶段（:mod:`app.pipeline.prescription_stage`）与它所依赖的输入扩容的守卫（Plan 02 Task 7）。

本文件分两大节，各自钉一件不同的事（硬规矩 #56：一条测试一个主语）：

* **A 节（P7-A1 / P7-A2 / P7-A3）**：``run_stratify.PersonInputs`` 的三个新字段、
  ``input_snapshot_of`` 的两个新键、``resolve_muscle_lines`` 的 P10 回填，以及
  **P10 绝不进分层判定**这条红线的行为守卫。这一节改的是 **Plan 01 已结案的代码**，
  故它的价值主要是「不回归」——14 例黄金用例与 500 人分布测试全绿只证明标签没变，
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
import json
import logging

import pytest
from sqlalchemy import CheckConstraint, create_engine, delete, event, func, select
from sqlalchemy.exc import IntegrityError

from app.adapters.mock_lepao import MockLePaoAdapter
from app.db import models as M
from app.db import repo
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.db.session import Session, init_db
from app.domain.indicators import AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex
from app.domain.percentile import (
    MIN_SAMPLE, MUSCLE_MASS, PercentileRow, SnapshotMetric,
)
from app.domain.prescription.assembler import assemble
from app.domain.prescription.exercises import EquivalenceTable
from app.domain.prescription.weekly import WeeklyFactor, weekly_training_sheet
from app.domain.stratify import stratify
from app.pipeline import daily, prescription_stage, run_stratify
from app.pipeline.daily import run_daily
from app.pipeline.prescription_stage import (
    ASSEMBLY_ERROR, INSUFFICIENT_DATA, NO_TRIGGER, active_or_needs_review,
    generate_prescriptions, profile_of, training_package_payload, valid_to_of,
    weekly_factors_of,
)
from app.pipeline.run_stratify import (
    PersonInputs, input_snapshot_of, percentile_source_of, resolve_muscle_lines,
)
from app.refdata_prescription import equivalence, exercises, templates
from app.seed.config import SeedConfig
from app.seed.generate import build_dataset, seed_database, write_csv

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
    让 14 例黄金用例一起红。

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


def test_golden_case_path_reads_height_and_weight_from_curr_and_leaves_p10_none():
    """**P9-A1**：黄金用例路径的身高体重**从 ``curr`` 子映射读**；``snapshot_muscle_p10`` 仍缺省 ``None``。

    ⚠️ **本条的契约在 Plan 02 Task 9 变过一次，不是「被删掉的守卫」**。Task 7 落地时那三个
    新字段一律 ``case.get(...)``（P7-A2），因为 13 例夹具的**顶层没有**它们、而那份夹具当时
    不许改；于是 Task 7 之后黄金用例路径的 ``input_snapshot["bmi"]`` **恒为 ``None``**，
    spec §7.4 的三档安全触发在 13 例里**一档都走不到**，Task 9 要断言的 ``needs_review`` 与
    ``safety_substitutions`` 因此恒为假绿。处置变了，契约跟着变。

    **修法是改 ``_from_golden_cases``、不是给夹具加顶层副本**：身高体重的**唯一住址**是
    ``input[i]["curr"]``（与 ``["prev"]``），夹具 ``_meta.bmi`` 逐字写着「**BMI 不在 input
    里**：它由身高体重合成」。在顶层再放一份就是第二个住址（Global Constraint #3），
    而且会与 :func:`app.pipeline.run_stratify.score_raw` 对不上——那一行本来就从同一份
    ``raw`` 读（``bmi_of(raw.get("height_cm"), raw.get("weight_kg"))``，``raw`` 就是 ``curr``），
    两个住址一旦漂移，快照里的**原始值** BMI 与 ``curr_scores["bmi"]`` 的**得分**就来自两次
    不同的读数，同一例的输入自相矛盾且不报错。

    ``snapshot_muscle_p10`` **仍然**是 ``None``：14 人 < ``MIN_SAMPLE = 30``，肌肉量组按
    Ruling 121 第 4 步不产出行，而黄金用例路径**刻意不调** :func:`resolve_muscle_lines`
    （P20 用夹具手工给定的值，理由见 :func:`_from_golden_cases` 的 docstring）。故
    ``muscle_low_p10`` 那一档在 14 例里**结构上不可达**、``safety_skipped`` 恒含
    ``"muscle_p10_missing"`` —— 这是**如实留痕**（``apply_safety`` 的纪律：没测不得讲成
    测了没问题），不是缺陷。钉住它是为了防下一个人以为「忘了回填 P10」而顺手给黄金用例
    路径接上 ``resolve_muscle_lines``：那会让 14 例的 P20 也一起被 ``None`` 覆盖掉
    （查表查不到），GC13 要测的「有这条线时 ``C`` 成立」当场失效。
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
    # 顶层刻意**不给**这三键：身高体重的住址是 curr（P9-A1）。谁把顶层副本加回夹具，
    # 本条的前置断言当场红，逼他来说清「第二个住址」的理由。
    for absent in ("height_cm", "weight_kg", "snapshot_muscle_p10"):
        assert absent not in case, "夹具顶层刻意不给这三键：住址是 curr（P9-A1）"

    persons, snapshot = run_stratify._from_golden_cases([case])
    assert len(persons) == 1
    person = persons[0]
    # 身高体重来自 curr 子映射，与 score_raw 合成 BMI **得分**读的是同一份 raw
    assert person.height_cm == 175.0
    assert person.weight_kg == 78.0
    # P10 仍是 None：14 人 < MIN_SAMPLE，且本路径不调 resolve_muscle_lines
    assert person.snapshot_muscle_p10 is None
    # 既有的那一档没被顺手改掉：P20 仍取夹具手工给定的值
    assert person.snapshot_muscle_p20 == 33.2

    evaluated = run_stratify.evaluate(persons, snapshot)[0]
    got = input_snapshot_of(evaluated, stratify(evaluated.derived), snapshot)
    # 手算的字面值（硬规矩 #35：不从 bmi_of 读回来跟自己比）：
    #   78.0 / (175.0 / 100) ** 2 = 78.0 / 3.0625 = 25.469387755… → round(…, 1) = 25.5
    assert got["bmi"] == 25.5
    assert got["snapshot_muscle_p10"] is None


# ---------------------------------------------------------------------------
# B 节：处方阶段本体
# ---------------------------------------------------------------------------
#
# 两套夹具，各测一件事：
#
# * ``bare`` —— **空**内存库 + 手工建的分层结果行。用来精确构造「一个数据不足的学生」
#   「一个红层转黄层的学生」「一个 BMI > 30 的学生」这类在 60 人种子数据里**造不出来**
#   的形状（实测缺省注入下 60 人 0 个 Z0、0 个 needs_review）。
# * ``session`` + ``seed_dir`` —— 与 ``tests/pipeline/test_daily.py`` 同一条 60 人种子
#   夹具，跑**整条管道**（``run_daily``）。用来钉端到端的计数、幂等、重放与
#   ``daily_sync_run.prescription_count``。
#
# ⚠️ 手工建的分层结果行**不手抄那 28 个键**：一律走生产的
# :func:`app.pipeline.run_stratify.input_snapshot_of` 产出（:func:`_strat_row`）。
# 手抄一份等于在测试里立第二个所有者，而它恰好是本 Task 刚扩过的契约。

#: 60 人 / ``seed=20250828`` / 缺省注入。与 ``tests/pipeline/test_daily.py`` 的 ``CFG``
#: 逐字相同（两份刻意各自持有：那是 Plan 01 的夹具，本文件不 import 它）。
CFG = SeedConfig(students=60, weeks=16, seed=20250828)
SEMESTER_NAME = "2025-2026-1"

#: 计划钉住的业务日期（``tests/pipeline/test_daily.py`` 的 ``D``）。
D = "2025-09-15"
AS_OF = dt.date(2025, 9, 15)
#: 次日：分层照跑，而五个触发一条都不成立（标签没变、离到期还差 27 天、没有新采集）。
D_NEXT = "2025-09-16"
#: 第 **28** 天：触发 3（微周期到期，``>=``）开火。``2025-09-15 + 28 天``，字面写死。
D_PLUS_28 = "2025-10-13"

#: ``microcycle_weeks = 4`` 的 18 套模板下，``2025-09-15`` 生成的处方到期日
#: = ``09-15 + 4 周 − 1 天`` = **2025-10-12**（第 28 天，闭区间）。
VALID_TO_FROM_D = dt.date(2025, 10, 12)

#: 四种分层形状对应的六项短板得分。**P25 一律 50**（见 :func:`_snapshot`），故
#: ``30`` = 短板、``60`` = 达标。标签由生产 ``stratify`` 算出、不在这里写死；
#: 写死的是**得分**（输入侧），断言的是**标签**（输出侧），两侧不同源。
_SCORES_BY_LABEL = {
    # W = 6 → R2「短板 ≥3 项，无条件升红」
    "red": {item: 30 for item in WEAKNESS_ITEMS},
    # W = 2（耐力桶两项）且 C = False → Y3「短板 ≥2 项且体成分未判为异常」
    "yellow": {
        **{item: 60 for item in WEAKNESS_ITEMS},
        ScoredItem.VITAL_CAPACITY: 30,
        ScoredItem.DISTANCE_RUN: 30,
    },
    # W = 0 且 C = False → G1
    "green": {item: 60 for item in WEAKNESS_ITEMS},
    # 六项全缺测 → valid_count = 0 → Z0 闸门
    "insufficient": {item: None for item in WEAKNESS_ITEMS},
}


@pytest.fixture
def bare():
    """只有学期的**空**内存库。``PRAGMA foreign_keys=ON`` 对它同样生效
    （``app/db/session.py`` 的钩子挂在 ``Engine`` **类**上）。"""
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        sem = M.Semester(name=SEMESTER_NAME, start_date=dt.date(2025, 9, 1),
                         end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
        s.add(sem)
        s.flush()
        s.commit()
        yield s, sem.id


@pytest.fixture
def seed_dir(tmp_path):
    d = tmp_path / "lepao"
    write_csv(build_dataset(CFG), d)      # 体测/体成分/问卷经适配器流入
    return d


@pytest.fixture
def session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, CFG)             # 只写组织结构
        yield s


def _semester_id(session) -> int:
    """按**名字**取本学年的 id（Ruling 173，口径照 ``tests/pipeline/test_daily.py``）。"""
    return session.scalar(select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME))


def _batch(session, semester_id: int, day: dt.date) -> int:
    """一行 ``daily_sync_run``，返回它的 ``id``（= ``batch_id``）。"""
    run = repo.upsert(
        session, M.DailySyncRun, ("semester_id", "business_date"),
        {"semester_id": semester_id, "business_date": day, "status": "success"},
    )
    session.flush()
    return run.id


def _student(session, student_no: str, sex: str = "male",
             birth: dt.date = dt.date(2006, 3, 4)) -> M.Student:
    """``birth = 2006-03-04`` → ``age_from(birth, 2025-09-15) = 19`` → ``大一、大二``，
    与 :func:`_snapshot` 那些行的年级组对得上（否则判定线一行也匹配不到、全员 Z0）。"""
    student = M.Student(student_no=student_no, name="学生" + student_no[-3:],
                        sex=sex, birth=birth, grade=1)
    session.add(student)
    session.flush()
    return student


def _strat_row(session, student, day, batch_id, kind, **person_overrides) -> str:
    """写一行**生产口径**的 ``stratification_result``，返回它的 ``label``。

    ``input_snapshot`` 由 :func:`app.pipeline.run_stratify.input_snapshot_of` 产出
    （28 个键，含 Task 7 新加的 ``bmi`` 与 ``snapshot_muscle_p10``），
    ``snapshot_muscle_p10`` / ``p20`` 由 :func:`resolve_muscle_lines` 从
    :func:`_snapshot` 回填——故这一行与 ``daily._stratify_and_persist`` 写出来的
    形状逐格同构。
    """
    person = _person(
        student_id=student.id,
        sex=Sex(student.sex),
        curr_scores={ScoredItem.BMI: None, **_SCORES_BY_LABEL[kind]},
        **person_overrides,
    )
    rows = _snapshot()
    resolved = resolve_muscle_lines([person], rows)[0]
    evaluated = run_stratify.evaluate([resolved], rows)[0]
    result = stratify(evaluated.derived)
    session.add(
        M.StratificationResult(
            student_id=student.id, computed_on=day, batch_id=batch_id,
            label=result.label.value,
            hit_rules=",".join(rule.value for rule in result.hit_rules),
            input_snapshot=input_snapshot_of(evaluated, result, rows),
            percentile_source=percentile_source_of(resolved, rows),
            valid_from=day, valid_to=None,
        )
    )
    session.flush()
    return result.label.value


def _generate(session, semester_id, batch_id, day, equiv=None):
    """:func:`generate_prescriptions` 的缺省注入版（三份参考数据走生产单例）。"""
    return generate_prescriptions(
        session, semester_id, batch_id, day,
        templates=templates(), exercises=exercises(),
        equivalence=equivalence() if equiv is None else equiv,
    )


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


# --- B1 纯函数三件 ---------------------------------------------------------


def test_valid_to_is_generated_on_plus_microcycle_minus_one_day():
    """``valid_to = generated_on + microcycle_weeks 周 − 1 天``，**首尾都算在内的闭区间**。

    四档日期一律**字面写死**（不用 ``timedelta`` 现算，免得期望侧与被测侧共用同一个算式）：
    ``2026-03-02`` + 4 周 − 1 天 = ``2026-03-29``，那正是第 **28** 天
    （:class:`app.db.models.prescription.Prescription` 的 ``valid_to`` 列注释逐字给了这一例）。

    ⚠️ **``− 1 天`` 是承重的**（简报 Step 2–6 的变异 ④）：删掉它，``valid_to`` 变成
    ``2026-03-30``，而触发 3 的判据 ``(as_of − generated_on).days >= 4 × 7`` 也在
    ``03-30`` 开火 —— 那一天于是同时被两张处方认领。第二档（``microcycle_weeks = 2``）
    钉住「周数从处方行取、不硬编码 4」（Task 6 的 P6-A3）。
    """
    assert valid_to_of(dt.date(2026, 3, 2), 4) == dt.date(2026, 3, 29)
    assert valid_to_of(dt.date(2026, 3, 2), 2) == dt.date(2026, 3, 15)
    assert valid_to_of(dt.date(2025, 9, 15), 4) == VALID_TO_FROM_D
    # 闭区间：generated_on 自己算第 1 天，故 valid_to − generated_on == 27 天而不是 28
    assert (valid_to_of(dt.date(2026, 3, 2), 4) - dt.date(2026, 3, 2)).days == 27


def test_needs_review_wins_over_active_in_the_status_mapping():
    """**``needs_review`` 优先于 ``active``**（Ruling 10；spec §7.4 末段「宁可不自动，
    也不要自动错」）。一张待人工复核的处方不能被学生端当成生效处方执行。

    两个返回值都字面写死，且都必须在 DB 的取值域里（``Prescription.STATUSES``）——
    后者钉住「映射产出的字符串真的落得进那一列」，而不是一个 CHECK 会拒收的第四态。
    """
    assert active_or_needs_review(True) == "needs_review"
    assert active_or_needs_review(False) == "active"
    assert active_or_needs_review(True) != "active", "needs_review 必须压过 active"
    assert {active_or_needs_review(True), active_or_needs_review(False)} <= Prescription.STATUSES


def test_training_package_payload_survives_a_json_round_trip():
    """``training_package`` 那一列真的能被 :class:`~app.db.models._shared.JsonText` 吃下去。

    ⚠️ ``JsonText.process_bind_param`` 是裸 ``json.dumps(value, ensure_ascii=False)``,
    **没有 ``default=`` 兜底**，而 ``AssembledBlock.structure`` 是
    ``types.MappingProxyType``（``isinstance(proxy, dict)`` 为 ``False``）——
    最后那一段 ``pytest.raises`` 就是这件事的**反证**：原始包直接 dumps 会炸，
    摊平之后不会。没有那一段，本条会被一个「反正 SQLAlchemy 会处理」的错觉骗过。
    """
    from app.domain.prescription.assembler import StudentProfile, assemble

    profile = StudentProfile(
        student_id=1, sex=Sex.MALE, birth=dt.date(2006, 3, 4), age=19,
        endurance_score=70.0, bmi=None, body_fat_pct=None,
        muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None,
    )
    pkg = assemble(profile, templates()["RED-END-ABN-01"], AS_OF, exercises=exercises())

    payload = training_package_payload(pkg)
    back = json.loads(json.dumps(payload, ensure_ascii=False))
    assert back == payload
    assert sorted(payload) == ["paused", "template_id", "template_version", "weeks"]
    assert payload["template_id"] == "RED-END-ABN-01"
    assert payload["paused"] is False
    assert len(payload["weeks"]) == 4                      # microcycle_weeks = 4
    assert [week["week"] for week in payload["weeks"]] == [1, 2, 3, 4]
    block = payload["weeks"][0]["sessions"][0]["blocks"][0]
    assert type(block["structure"]) is dict                # 不是 mappingproxy
    assert block["impact_level"] == "high"                 # 枚举写成 .value
    assert block["exercise_ref"] == "interval_run"
    # assembly_snapshot **不在**这一列（它有自己的列，复制一份就是第二个所有者）
    assert "assembly_snapshot" not in payload
    # 反证：原始包里的 structure 直接 dumps 会炸
    with pytest.raises(TypeError):
        json.dumps(pkg.weeks[0].sessions[0].blocks[0].structure)


# --- B2 Z0 闸门：insufficient_data 必须留痕（Task 6 传导的第 4 件事）--------


def test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped(bare, caplog):
    """Review Focus 第 3 条：Z0 拦下的学生**不得生成处方**，且**必须留下可交代的痕迹**。

    痕迹落在两处，两处都断言：① ``skipped_reasons`` 里必须有
    ``"insufficient_data"`` 这个**字面键**（Task 6 实现者报的最高优先级关切：
    ``evaluate_triggers`` 是纯函数、没有渠道把「为什么返回空 tuple」传出来，
    而这一档会让教师端的「重新生成」按钮**无声失败**）；② 一条 ``warning`` 日志。

    ⚠️ **键名字面写死**（``"insufficient_data"``），不从
    ``prescription_stage.INSUFFICIENT_DATA`` 读回来跟自己比（硬规矩 #35）；
    那个常量与 ``Layer.INSUFFICIENT.value`` 的同源性由
    ``tests/domain/test_prescription_triggers.py`` 的漂移测试守。

    ⚠️ **``skipped_reasons`` 是稀疏的**：另一个人（红层）拿到了处方，故字典里
    **只有** ``insufficient_data`` 一个键。这一条同时钉住「不把六个 ``MatchStatus``
    以 0 填进去」——填了的话下面那条 ``== {"insufficient_data": 1}`` 当场红。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    ok = _student(session, "2025001001")
    bad = _student(session, "2025001002")
    assert _strat_row(session, ok, AS_OF, batch, "red") == "red"
    assert _strat_row(session, bad, AS_OF, batch, "insufficient") == "insufficient_data"

    caplog.set_level(logging.DEBUG, logger="app.pipeline.prescription_stage")
    report = _generate(session, sem, batch, AS_OF)

    assert report.generated == 1
    assert report.skipped == 1
    assert report.skipped_reasons == {"insufficient_data": 1}
    assert report.skipped_reasons[INSUFFICIENT_DATA] == 1
    # 那个学生**没有**处方行——不是「有一张 status 特别的处方」
    assert [row.student_id for row in session.scalars(select(Prescription))] == [ok.id]
    # 逐人的痕迹在 debug 档，整批的汇总在 warning 档（噪声取舍见模块 docstring）
    per_student = [rec for rec in caplog.records
                   if rec.levelno == logging.DEBUG and "数据不足" in rec.getMessage()]
    assert len(per_student) == 1, "逐人那一条只该有 Z0 那一个人"
    assert bad.student_no in per_student[0].getMessage()
    assert any(
        rec.levelno == logging.WARNING and "Z0 闸门" in rec.getMessage()
        for rec in caplog.records
    ), "整批汇总那一条 warning 必须点名 Z0 闸门与人数"


def test_the_z0_gate_is_checked_before_the_matcher_is_consulted(bare, monkeypatch):
    """Z0 那一档必须在**匹配之前**就被分出来，不是「匹配返回 NO_LAYER 之后再改个键名」。

    两者今天产出的处方**一样**（都没有），但 ``skipped_reasons`` 的键不同，而那个键是
    教师端唯一能读到的原因：``"insufficient_data"`` 说的是「补齐体测数据就有处方」，
    ``"no_layer"`` 说的是「矩阵里缺这一格」——两条完全不同的处置。
    把 Z0 的早退挪到匹配之后（或干脆删掉），本条当场红。

    ⚠️ 这一条与 :func:`test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped`
    是**同一档的两个观测面**（一个看键名、一个看「匹配器有没有被惊动」），
    故删掉早退会让两条一起红——简报 Step 2–6 的变异 ① 预期的正是这个形状。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    ok, bad = _student(session, "2025001001"), _student(session, "2025001002")
    _strat_row(session, ok, AS_OF, batch, "red")
    _strat_row(session, bad, AS_OF, batch, "insufficient")

    consulted: list[str] = []
    real = prescription_stage.match_template

    def recorder(inp, tmpls):
        consulted.append(inp.layer.value)
        return real(inp, tmpls)

    monkeypatch.setattr(prescription_stage, "match_template", recorder)
    report = _generate(session, sem, batch, AS_OF)

    assert consulted == ["red"], (
        "匹配器看到了 insufficient_data：Z0 的早退没有排在匹配之前，"
        f"实际被咨询的层是 {consulted}"
    )
    assert report.generated == 1
    assert report.skipped_reasons == {"insufficient_data": 1}


def test_no_bucket_and_no_layer_never_appear_even_with_a_z0_student(bare):
    """**Ruling 11 在「真的有 Z0 学生」那一档上仍然成立。**

    :func:`test_no_student_is_skipped_for_a_missing_bucket` 跑的是 60 人种子夹具，而它
    在 ``D = 2025-09-15`` 上**一个 Z0 学生都没有**（实测标签分布
    ``{yellow: 29, green: 24, red: 7}``）——于是那条守不住「Z0 早退把 NO_LAYER 一起吃掉」
    这一格。本条用 ``bare`` 夹具把四档标签各造一个人，把那一格补上。

    四个人 → 3 张处方（红/黄/绿）+ 1 个 ``insufficient_data``；``no_bucket`` 与
    ``no_layer`` 两个键**都不出现**。依据（简报 Step 1 的 Ruling 11）：
    ``dominant_bucket is None`` 只在 6 个短板判定项**全部** ``None`` 时发生，而那必然使
    ``valid_count == 0`` → Z0 → 被本阶段的早退先拦下，故生产路径上
    ``NO_BUCKET ⊆ NO_LAYER ⊆ insufficient_data``。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    for index, kind in enumerate(("red", "yellow", "green", "insufficient"), start=1):
        student = _student(session, f"202500100{index}")
        _strat_row(session, student, AS_OF, batch, kind)

    report = _generate(session, sem, batch, AS_OF)
    assert report.generated == 3
    assert report.skipped == 1
    assert report.skipped_reasons == {"insufficient_data": 1}
    assert "no_bucket" not in report.skipped_reasons
    assert "no_layer" not in report.skipped_reasons
    # 三张处方各自落到自己那一格的模板（层 × 主导短板 × 体成分）
    assert {row.template_ref for row in session.scalars(select(Prescription))} == {
        "RED-END-NOR-02", "YEL-END-NOR-08", "GRN-END-NOR-14",
    }


def test_no_student_is_skipped_for_a_missing_bucket(session, seed_dir):
    """**Ruling 11 的唯一守卫**：``skipped_reasons`` 里**没有** ``"no_bucket"`` 键。

    依据：``dominant_bucket is None`` 只在 6 个短板判定项**全部** ``None`` 时发生
    （Plan01 Ruling 175 补的 ``derive.py`` 那一支），而那必然使 ``valid_count == 0`` →
    Z0 → ``insufficient_data``，故**生产路径上 ``NO_BUCKET ⊆ NO_LAYER``**。

    没有这一条，``find_weaknesses`` 的口径一变（例如「有短板才算有效项」），处方数会
    静默少一批而没有任何断言提示。⚠️ 它只在 ``skipped_reasons`` 稀疏时才咬得住：
    若六个 ``MatchStatus`` 一律以 0 入字典，``not in`` 就恒假、本条变成永真式。
    """
    sem = _semester_id(session)
    report = None
    real = prescription_stage.generate_prescriptions

    def spy(*args, **kwargs):
        nonlocal report
        report = real(*args, **kwargs)
        return report

    # 直接调 run_daily 拿不到 report 对象，故 monkeypatch 一层把它捞出来
    import app.pipeline.daily as daily_module
    daily_module.generate_prescriptions = spy
    try:
        run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    finally:
        daily_module.generate_prescriptions = real

    assert run.status == "success"
    assert "no_bucket" not in report.skipped_reasons
    assert "no_layer" not in report.skipped_reasons, (
        "NO_LAYER 那一档在生产上被 insufficient_data 的早退先拦下，故它也不该出现"
    )
    assert report.skipped_reasons == {}


# --- B3 端到端：60 人种子数据 ---------------------------------------------


def test_prescriptions_are_generated_for_every_stratified_student(session, seed_dir):
    """60 人 / ``seed=20250828`` / 缺省注入、``D = 2025-09-15``：**60 张处方**。

    这三个数字都是本轮亲跑实测（硬规矩 #44）：分层标签分布
    ``{yellow: 29, green: 24, red: 7}``（合计 60，**0 个 ``insufficient_data``**），
    18 套模板里用到了 **12** 套，``status`` 一律 ``active``（0 个 ``needs_review``），
    触发原因一律 ``["first_stratification"]``（首日、库里一张处方都没有）。

    ⚠️ **首日 ``insufficient_data`` 是 0 人**，故 Z0 那一档由
    :func:`test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped`
    的 ``bare`` 夹具守（60 人种子数据里造不出来）。
    ⚠️ 计划 Step 1 点名的「500 人零注入 → 500 张 / 缺省注入 → 498 张」两个数**不进测试网**：
    跑一次 500 人的整条管道约 20 s，而 ``tests/pipeline/test_backfill.py`` 已经有一条
    ``elapsed < 60`` 的 500 人测试；再加两条会让套件翻倍。那两个数由本轮探针复量、
    记进 Task 7 报告（**历史实测，不被守卫**）。
    """
    sem = _semester_id(session)
    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    assert run.status == "success"

    rows = list(session.scalars(select(Prescription)))
    assert len(rows) == 60
    assert run.prescription_count == 60
    # 每一个已分层的学生**恰好**一张，且分层结果行数与处方行数相等
    stratified = {row.student_id for row in session.scalars(select(M.StratificationResult))}
    assert len(stratified) == 60
    assert {row.student_id for row in rows} == stratified
    assert len({row.student_id for row in rows}) == 60, "一人一天一张（唯一约束 + upsert）"

    assert {row.status for row in rows} == {"active"}
    assert {tuple(row.trigger_reasons) for row in rows} == {("first_stratification",)}
    assert {row.generated_on for row in rows} == {AS_OF}
    assert {row.valid_from for row in rows} == {AS_OF}
    assert {row.valid_to for row in rows} == {VALID_TO_FROM_D}
    # Task 6 传导的第 1 件事：microcycle_weeks 从模板快照下来（18 套今天一律 4）
    assert {row.microcycle_weeks for row in rows} == {4}
    # Task 6 传导的第 2 件事：首日没有「上一张」，故一律 False（不是 NULL）
    assert {row.previous_had_overrides for row in rows} == {False}
    # ⚠️ teacher_overrides 是 list（不可哈希），故逐行比而不是取集合
    assert all(row.teacher_overrides == [] for row in rows)
    assert {row.batch_id for row in rows} == {run.id}
    # DB 列叫 template_ref，取值是 domain 的 template_id（P6-A7）
    assert len({row.template_ref for row in rows}) == 12
    assert all(row.template_ref in templates() for row in rows)
    # assembly_snapshot = assemble 的 12 键 + apply_safety 的 3 键
    assert {len(row.assembly_snapshot) for row in rows} == {15}


def test_report_counts_add_up_to_every_stratified_student(session, seed_dir):
    """``generated + skipped == 本日分层结果的行数``，且 ``skipped`` == 各原因之和。

    这条恒等式是「没有人被静默丢掉」的唯一守卫：``generate_prescriptions`` 的循环里
    每一条 ``continue`` 都必须经过 ``_skip``，漏一条，本条当场对不上账。
    """
    sem = _semester_id(session)
    captured = {}
    real = prescription_stage.generate_prescriptions

    def spy(*args, **kwargs):
        captured["report"] = real(*args, **kwargs)
        return captured["report"]

    import app.pipeline.daily as daily_module
    daily_module.generate_prescriptions = spy
    try:
        run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    finally:
        daily_module.generate_prescriptions = real

    report = captured["report"]
    total = _count(session, M.StratificationResult)
    assert report.generated + report.skipped == total == 60
    assert sum(report.skipped_reasons.values()) == report.skipped
    assert report.generated == _count(session, Prescription)


def test_daily_sync_run_prescription_count_matches_the_report(session, seed_dir):
    """``daily_sync_run.prescription_count`` = ``PrescriptionReport.generated``
    = ``prescription`` 表里 ``batch_id`` 属于本批的行数。**三个数两两相等**，
    而不是「计数列与表行数相等」这一条——后者会被「报表算错、但表和计数列一起错」骗过。
    """
    sem = _semester_id(session)
    captured = {}
    real = prescription_stage.generate_prescriptions

    def spy(*args, **kwargs):
        captured["report"] = real(*args, **kwargs)
        return captured["report"]

    import app.pipeline.daily as daily_module
    daily_module.generate_prescriptions = spy
    try:
        run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    finally:
        daily_module.generate_prescriptions = real

    rows = session.scalar(
        select(func.count()).select_from(Prescription).where(Prescription.batch_id == run.id)
    )
    assert run.prescription_count == captured["report"].generated == rows == 60
    # 反空转：真的写进去了，不是「0 == 0 == 0」
    assert rows > 0


def test_no_trigger_means_no_new_prescription(session, seed_dir):
    """次日跑：标签没变、没到期、没有新采集 → ``generated == 0``，处方行数不变。

    **处方不每天重发**（spec §5.2）。``D_NEXT = 2025-09-16`` 距首日 1 天
    （触发 3 要 ``>= 28`` 天），分层输入一个都没变（评估锚点仍是 2025-09-01 那个
    ``week1`` 批次，故触发 2 与触发 4 都不成立），教师也没点（触发 5 在管道侧恒 ``False``）。

    ⚠️ 这一条同时钉住「跳过是**留痕的**而不是静默的」：60 人全落进
    ``skipped_reasons["no_trigger"]``。
    """
    sem, adapter = _semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, adapter)
    assert _count(session, Prescription) == 60

    captured = {}
    real = prescription_stage.generate_prescriptions

    def spy(*args, **kwargs):
        captured["report"] = real(*args, **kwargs)
        return captured["report"]

    import app.pipeline.daily as daily_module
    daily_module.generate_prescriptions = spy
    try:
        run2 = run_daily(session, sem, D_NEXT, adapter)
    finally:
        daily_module.generate_prescriptions = real

    report = captured["report"]
    assert report.generated == 0
    assert run2.prescription_count == 0
    assert report.skipped == 60
    assert report.skipped_reasons == {"no_trigger": 60}
    # 行数不变，且**没有**一张是次日生成的
    assert _count(session, Prescription) == 60
    assert {row.generated_on for row in session.scalars(select(Prescription))} == {AS_OF}
    assert {row.status for row in session.scalars(select(Prescription))} == {"active"}


# --- B4 幂等与重放清理 ----------------------------------------------------


def test_rerun_same_day_does_not_duplicate_prescriptions(session, seed_dir):
    """同一业务日期重跑：``prescription`` 行数不变（照 Plan 01
    ``test_rerun_same_day_does_not_wipe_percentile_snapshot`` 的形状）。

    机制是两层的：① ``_replay_cleanup`` 按 ``batch_id`` 先删掉本批的处方行；
    ② ``UniqueConstraint("student_id", "generated_on")`` + ``repo.upsert`` 兜住
    「同一天被两次触发」（Review Focus 第 2 条）——**机制是那条唯一约束，
    不是「记得先查一遍」**。
    """
    sem, adapter = _semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, adapter)
    first = _count(session, Prescription)
    run_daily(session, sem, D, adapter)
    second = _count(session, Prescription)
    assert first == 60 and second == 60
    # 一个学生一天只有一张（唯一约束真的在生效，不是「删了又插了两张」）
    ids = [(row.student_id, row.generated_on) for row in session.scalars(select(Prescription))]
    assert len(set(ids)) == len(ids) == 60


def test_replay_cleanup_covers_prescription_and_weekly_adjustment(bare):
    """**P7-A4**：``_replay_cleanup`` 的清单含两张新表，且**子表先删**、不抛 FK 错。

    漏掉 ``weekly_adjustment`` 的失效形态最阴：那张表**没有任何唯一约束**，不删就会
    每跑一次多一批调整行，而「本周训练单」是 ``骨架第 N 周 × 该周全部 factor`` 的
    **累乘**（spec §8.4），多一批 ``0.8`` 就把那一周的量再打八折，且全程不报错。

    ⚠️ 触私有名 ``daily._replay_cleanup``：本条要钉的正是**那份清单**，
    经 ``run_daily`` 绕过去的话就同时动了七个阶段，红了看不出是哪一份清单的问题。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, batch, "red")
    assert _generate(session, sem, batch, AS_OF).generated == 1

    prescription = session.scalar(select(Prescription))
    session.add(
        WeeklyAdjustment(
            prescription_id=prescription.id, batch_id=batch, week=1, factor=0.8,
            reason="本周月考，减量", source="teacher",
            created_at=dt.datetime(2025, 9, 16, 9, 0),
        )
    )
    session.flush()
    assert _count(session, WeeklyAdjustment) == 1

    daily._replay_cleanup(session, batch)
    session.flush()
    assert _count(session, Prescription) == 0
    assert _count(session, WeeklyAdjustment) == 0
    # 清单里 Plan 01 那三张也照旧被清（本条改动没有把它们挤掉）
    assert _count(session, M.StratificationResult) == 0
    assert _count(session, M.DerivedMetrics) == 0


def test_deleting_prescription_before_weekly_adjustment_really_violates_the_fk(bare):
    """**P7-A4 的反证**：把顺序倒过来（先删父表）真的会 ``FOREIGN KEY constraint failed``。

    没有这一条，:func:`test_replay_cleanup_covers_prescription_and_weekly_adjustment`
    会被一个「反正两张表都空了」的实现骗过——例如先 ``DELETE FROM weekly_adjustment``
    再删处方（顺序对但绕过了清单），或者干脆关掉外键强制。本条把「顺序承重」这句话
    变成可执行的证据：``PRAGMA foreign_keys=ON`` 真的在强制那条 FK。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, batch, "red")
    assert _generate(session, sem, batch, AS_OF).generated == 1
    prescription = session.scalar(select(Prescription))
    session.add(
        WeeklyAdjustment(
            prescription_id=prescription.id, batch_id=batch, week=1, factor=0.8,
            reason="本周月考，减量", source="teacher",
            created_at=dt.datetime(2025, 9, 16, 9, 0),
        )
    )
    session.flush()

    with pytest.raises(IntegrityError) as exc:
        repo.delete_by_batch(session, Prescription, batch)
    assert "FOREIGN KEY constraint failed" in str(exc.value)


# --- B5 换处方：触发 2 与 replaced ---------------------------------------


def test_a_layer_change_regenerates_and_replaces(bare):
    """红(D1) → 黄(D2)：新处方 ``active``、旧处方 ``replaced``，触发原因是 ``layer_changed``。

    ⚠️ **旧处方的 ``valid_to`` 不改写**（这是对计划 Step 1 那句「``valid_to`` 关账」的一处
    有意偏离，理由记在 Task 7 报告的「顶回控制者」一节）：
    ① :class:`app.db.models.prescription.Prescription` 的 ``valid_to`` 列注释逐字写着
    「换处方时把上一张置 ``replaced``，**不改写**它的 ``valid_to``」，而它是 Task 6
    已结案的代码；② ``valid_to`` 必须能从 ``generated_on + microcycle_weeks`` **离线复算**
    （spec §4.3），改写它就废掉了这条可追溯性；③ Plan 01 的
    ``stratification_result.valid_to`` 恒 NULL 正是同一条纪律（``daily._stratify_and_persist``
    的注释：「把旧行的 valid_to 写成本日会让重放必须同时改写上一批的行——那会破坏
    『同一业务日期重跑只动本批』这条幂等边界」）。
    「哪一张现在生效」由 ``status`` 唯一确定，不靠日期区间。
    """
    session, sem = bare
    d2 = dt.date(2025, 9, 22)
    b1 = _batch(session, sem, AS_OF)
    b2 = _batch(session, sem, d2)
    student = _student(session, "2025001001")

    assert _strat_row(session, student, AS_OF, b1, "red") == "red"
    first = _generate(session, sem, b1, AS_OF)
    assert first.generated == 1 and first.skipped_reasons == {}

    assert _strat_row(session, student, d2, b2, "yellow") == "yellow"
    second = _generate(session, sem, b2, d2)
    assert second.generated == 1

    rows = {row.generated_on: row for row in session.scalars(select(Prescription))}
    assert sorted(rows) == [AS_OF, d2]
    assert rows[AS_OF].status == "replaced"
    assert rows[AS_OF].template_ref == "RED-END-NOR-02"
    assert rows[AS_OF].trigger_reasons == ["first_stratification"]
    # **不改写** valid_to：它仍是生成当时算出的那一个，且仍可离线复算
    assert rows[AS_OF].valid_to == VALID_TO_FROM_D
    assert rows[d2].status == "active"
    assert rows[d2].template_ref == "YEL-END-NOR-08"
    assert rows[d2].trigger_reasons == ["layer_changed"]
    assert rows[d2].valid_to == dt.date(2025, 10, 19)


def test_trigger_2_survives_the_deletion_of_that_days_stratification_row(bare):
    """**fix round 1（F1-1）的唯一可执行判据**：删掉「生成那一天」的分层结果行之后，
    触发 2 仍然成立。

    ``prescription.label_at_generation`` 这一列存在的全部理由就是本条测试。在此之前
    「上一张处方生成当时的标签」只能 ``outerjoin`` 回读**同一天**的
    ``stratification_result``，而那一行是**会被删的**——
    :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删它（Plan 01 的既有口径），
    于是重放那一天之后 join 返回 ``NULL``：

    * 当时的实际行为：``_last_prescription_of`` 响亮抛 ``ValueError``、整批回滚（那条守卫
      叫 ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``，
      **已由本条取代**——它钉的那个失效形态在加了本列之后结构上不可达）；
    * 更糟的可能行为：若当初写成 ``join`` 而不是 ``outerjoin``，这个人会**静默**变成
      「没有上一张处方」→ 触发 1 → 天天重发处方、教师覆盖天天被冲掉。

    而 spec §4.3 要的是「任一条结果都能离线复算」：把判定输入快照在处方行上（与 P6-A3
    给 ``microcycle_weeks`` 快照**同构**），触发判定就不再依赖另一张表的行还在不在。

    ⚠️ 红/绿取证（硬规矩 #65）：加列**之前**本条以
    ``ValueError: 学生 … 没有分层结果 …`` 当场报错（红），加列 +
    ``_last_prescription_of`` 改读本列之后绿；两次实测输出记在 Task 7 报告 fix round 1。
    """
    session, sem = bare
    d2 = dt.date(2025, 9, 22)
    b1, b2 = _batch(session, sem, AS_OF), _batch(session, sem, d2)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, b1, "red")
    assert _generate(session, sem, b1, AS_OF).generated == 1
    assert _count(session, Prescription) == 1

    # 重放 AS_OF 那天会做的事：按批删掉本批的分层结果行（这里按日期删，形状等价）
    session.execute(
        delete(M.StratificationResult).where(M.StratificationResult.computed_on == AS_OF)
    )
    session.flush()
    assert _count(session, M.StratificationResult) == 0, "那一天的分层行已经不在了"

    _strat_row(session, student, d2, b2, "yellow")
    second = _generate(session, sem, b2, d2)
    assert second.generated == 1

    rows = {row.generated_on: row for row in session.scalars(select(Prescription))}
    assert sorted(rows) == [AS_OF, d2]
    # 触发 2 仍然成立：比较对象是处方行上快照的那一个，不是（已删的）分层行
    assert rows[d2].trigger_reasons == ["layer_changed"]
    assert rows[d2].label_at_generation == "yellow"
    assert rows[AS_OF].label_at_generation == "red"
    assert rows[AS_OF].status == "replaced"
    assert rows[d2].status == "active"


def test_regeneration_does_not_inherit_teacher_overrides(session, seed_dir):
    """**Step 0（Task 6 的 P6-A1 移过来的第 1 条）**，spec §7.5 原文：
    「下次自动生成时回到算法基线、不继承覆盖，但界面提示『该生上次存在人工覆盖』」。

    三件事逐个钉住：① 新处方的 ``teacher_overrides`` 是空列表（**不继承**）；
    ② ``prescription.previous_had_overrides is True``（**界面提示的唯一载体**）；
    ③ 新处方的 ``training_package`` 与覆盖之前那份**逐字段相同**（回到算法基线）。

    ⚠️ **②不是 ``assembly_snapshot`` 里的键**（P6-A2 否掉的正是那个方案）：那一列的
    契约是「离线复算**本张**处方」，而「上一张有没有覆盖」是关于**另一张**处方的事实；
    往快照加键会让 Task 5 钉死的「12 键 / 至多 +3 键」两条守卫一起变红。
    本条因此**同时**断言快照仍是 15 个键、且里面没有任何与覆盖有关的键。

    重生成由**触发 3（微周期到期）**驱动：``D_PLUS_28 = 2025-10-13`` 距首日整 28 天，
    ``(as_of − generated_on).days >= 4 × 7`` 开火。
    """
    sem, adapter = _semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, adapter)

    target = session.scalar(select(Prescription).order_by(Prescription.id)).student_id
    old = session.scalar(select(Prescription).where(Prescription.student_id == target))
    baseline_package = old.training_package
    # 教师手工加一条覆盖（Plan 03 的教师端写入方；本条只模拟它留下的那一列内容）
    old.teacher_overrides = [{
        "kind": "volume_scale", "target": None, "old_value": "1.0", "new_value": "0.8",
        "reason": "本周月考，减量", "teacher_staff_no": "T001",
        "applied_at": "2025-09-16T09:00:00",
    }]
    session.flush()
    assert old.teacher_overrides and old.previous_had_overrides is False

    run_daily(session, sem, D_PLUS_28, adapter)

    rows = {row.generated_on: row
            for row in session.scalars(
                select(Prescription).where(Prescription.student_id == target))}
    assert sorted(rows) == [AS_OF, dt.date(2025, 10, 13)]
    new = rows[dt.date(2025, 10, 13)]
    # ① 不继承覆盖
    assert new.teacher_overrides == []
    # ② 界面提示的唯一载体
    assert new.previous_had_overrides is True
    # ③ 回到算法基线：训练包与覆盖之前那份逐字段相同
    assert new.training_package == baseline_package
    # 旧处方让位（status 是唯一判据，valid_to 不改写）
    assert rows[AS_OF].status == "replaced"
    assert rows[AS_OF].valid_to == VALID_TO_FROM_D
    assert new.status == "active"
    assert new.trigger_reasons == ["microcycle_expired"]
    # ⚠️ ②不是快照里的键：仍是 15 个，且没有任何覆盖相关的键
    assert len(new.assembly_snapshot) == 15
    assert not [key for key in new.assembly_snapshot if "override" in key.lower()]


def test_same_day_regeneration_is_idempotent(session, seed_dir):
    """**Step 0（Task 6 的 P6-A1 移过来的第 2 条）**，Review Focus 第 2 条：
    同一天跑两次管道 → ``prescription`` 行数不变、``training_package`` 逐字段相同。

    这是 ``tests/pipeline/test_daily.py`` 那条全表 canonical sha256 的**处方侧对读**：
    那条比的是 11 张表的全部行，本条单独把「训练包的内容」拎出来逐字段比——
    一个「行数对但训练包每次都不同」的回归（例如装配器读到了遍历序不稳定的字典）
    两条都会红，但本条的失败消息能直接指出是哪一个学生、哪一周。
    """
    sem, adapter = _semester_id(session), MockLePaoAdapter(seed_dir)
    run_daily(session, sem, D, adapter)
    first = {row.student_id: row.training_package
             for row in session.scalars(select(Prescription))}
    run_daily(session, sem, D, adapter)
    second = {row.student_id: row.training_package
              for row in session.scalars(select(Prescription))}

    assert len(first) == len(second) == 60
    assert _count(session, Prescription) == 60
    differing = [sid for sid in first if first[sid] != second[sid]]
    assert differing == [], f"{len(differing)} 名学生的训练包在重放后变了，例如 {differing[:3]}"
    # 反空转：训练包真的有内容（不是两次都比了个空字典）
    assert all(pkg["weeks"] for pkg in second.values())
    assert all(len(pkg["weeks"]) == 4 for pkg in second.values())


# --- B6 安全后置的端到端：needs_review ------------------------------------


def test_needs_review_when_no_equivalent_exercise(bare, caplog):
    """**Review Focus 第 5 条的端到端版本**：安全规则命中却在等价表里找不到替身 →
    处方 ``status = "needs_review"``、写 ``warning`` 日志、**不静默跳过**。

    构造：一个 ``red`` + 耐力桶 + 体成分异常的学生（体脂率 25.0% > 男生 20% 阈值）
    → 匹配 ``RED-END-ABN-01``（4 课全部含 ``interval_run``，``impact_level: high``）；
    BMI = ``round(102.0 / 1.70², 1)`` = **35.3** > 30 → 触发 ``bmi_over_30``；
    注入一份**空映射**的等价表 → ``lookup`` 一律返回 ``None`` → ``needs_review``。

    ⚠️ 真表（``exercise_equivalence.yaml`` v1.0）有 **10** 条映射，故这一档在生产数据上
    **不可达**——必须注入空表才造得出来。这也是本条用 ``bare`` 夹具而不是 60 人种子数据的原因。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    student = _student(session, "2025001001")
    label = _strat_row(session, student, AS_OF, batch, "red",
                       body_fat_pct=25.0, height_cm=170.0, weight_kg=102.0)
    assert label == "red"

    empty = EquivalenceTable(
        version="TEST-EMPTY", mappings=(),
        volume_reduction={"bmi_over_30": 0.8, "muscle_low_p10": 0.9},
    )
    caplog.set_level(logging.WARNING, logger="app.pipeline.prescription_stage")
    report = _generate(session, sem, batch, AS_OF, equiv=empty)

    assert report.generated == 1
    assert report.needs_review == 1
    assert report.skipped == 0

    row = session.scalar(select(Prescription))
    assert row.template_ref == "RED-END-ABN-01"
    # needs_review 优先于 active：装配**成功**了，但状态不得是 active
    assert row.status == "needs_review"
    assert row.status != "active"
    # 找不到替身 → 一条替换都没有，而那个高冲击 block **原样保留**（不删除）
    assert row.safety_substitutions == []
    refs = [block["exercise_ref"]
            for week in row.training_package["weeks"]
            for session_payload in week["sessions"]
            for block in session_payload["blocks"]]
    # 4 周 × 4 课 × 1 个 interval_run = **16** 次出现（RED-END-ABN-01 的 weekly_frequency
    # 是 4、每课一个 interval_run）。原样保留 ⇒ 16 次一个都没被换掉。
    assert refs.count("interval_run") == 16, "原样保留：删掉动作会让训练量静默缩水"
    assert "bmi_over_30" in row.assembly_snapshot["safety_triggers"]
    # 不静默跳过：warning 日志真的写了，且点名了那个动作
    messages = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("找不到冲击" in text and "interval_run" in text for text in messages), messages


def test_a_matching_equivalence_table_yields_an_active_prescription(bare):
    """上一档的**反证**：同一份输入配上**真**等价表 → ``active``、且真的有替换记录。

    没有这一条，:func:`test_needs_review_when_no_equivalent_exercise` 会被一个
    「凡是安全触发就一律 needs_review」的实现骗过（那会让 500 人里一大批处方
    白白挂进人工复核队列）。
    """
    session, sem = bare
    batch = _batch(session, sem, AS_OF)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, batch, "red",
               body_fat_pct=25.0, height_cm=170.0, weight_kg=102.0)
    report = _generate(session, sem, batch, AS_OF)

    assert report.generated == 1
    assert report.needs_review == 0
    row = session.scalar(select(Prescription))
    assert row.status == "active"
    assert row.template_ref == "RED-END-ABN-01"
    # 4 周 × 4 课 = **16** 条替换记录（逐 block 实例，spec §7.4 :512 的审计要求；
    # Substitution 的 docstring 逐字点了 RED-END-ABN-01 的 interval_run 这一例）
    assert len(row.safety_substitutions) == 16
    assert {item["original_ref"] for item in row.safety_substitutions} == {"interval_run"}
    assert {item["trigger"] for item in row.safety_substitutions} == {"bmi_over_30"}
    # 映射表版本号落进了每一条记录（spec §7.4 :512）
    assert {item["equivalence_version"] for item in row.safety_substitutions} == {"1.0"}
    # 高冲击动作真的被换掉了
    refs = [block["exercise_ref"]
            for week in row.training_package["weeks"]
            for session_payload in week["sessions"]
            for block in session_payload["blocks"]]
    assert "interval_run" not in refs


# --- B7 异常分层：按学生捕获 ----------------------------------------------


def test_per_student_assembly_failure_does_not_roll_back_the_batch(session, seed_dir, caplog):
    """**简报 Task 7「决定」第 2 条**：一个学生的装配失败**不得**让整批回滚。

    处方阶段跑在 ``run_daily`` 的 SAVEPOINT 里，故 ``assemble`` / ``apply_safety`` 抛的
    异常必须**按学生捕获**；只有基础设施异常（DB 写失败）才让它冒泡。
    本条 monkeypatch ``prescription_stage.assemble``，让它只对 ``student_id`` 最小的
    那个人抛 ``ValueError``，然后断言：

    * ``run.status == "success"``（整批**没有**回滚）；
    * 分层结果与百分位快照**都还在**（60 / >0 行）——这是「没回滚」的直接证据，
      只看处方行数会被「整批回滚 → 处方也是 0 行」骗过；
    * 其余 **59** 人照常拿到处方，那一个人没有；
    * 报表里那一个人计进了 ``needs_review`` 与 ``skipped_reasons["assembly_error"]``；
    * 写了一条 ``warning`` 日志，点名学号与异常类型。
    """
    sem = _semester_id(session)
    target = session.scalar(select(M.Student.id).order_by(M.Student.id).limit(1))
    target_no = session.scalar(
        select(M.Student.student_no).where(M.Student.id == target)
    )
    real = prescription_stage.assemble

    def flaky(profile, template, as_of, *, exercises):
        if profile.student_id == target:
            raise ValueError("装配炸了（测试注入）")
        return real(profile, template, as_of, exercises=exercises)

    captured = {}
    real_generate = prescription_stage.generate_prescriptions

    def spy(*args, **kwargs):
        captured["report"] = real_generate(*args, **kwargs)
        return captured["report"]

    import app.pipeline.daily as daily_module
    caplog.set_level(logging.WARNING, logger="app.pipeline.prescription_stage")
    daily_module.generate_prescriptions = spy
    prescription_stage.assemble = flaky
    try:
        run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    finally:
        prescription_stage.assemble = real
        daily_module.generate_prescriptions = real_generate

    assert run.status == "success"
    # 整批没回滚：分层结果与快照都还在
    assert _count(session, M.StratificationResult) == 60
    assert _count(session, M.PercentileSnapshot) > 0
    assert _count(session, M.DerivedMetrics) == 60

    report = captured["report"]
    assert report.generated == 59
    assert run.prescription_count == 59
    assert _count(session, Prescription) == 59
    assert report.needs_review == 1
    assert report.skipped == 1
    assert report.skipped_reasons == {ASSEMBLY_ERROR: 1}
    assert report.skipped_reasons["assembly_error"] == 1
    assert target not in {row.student_id for row in session.scalars(select(Prescription))}

    messages = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any(target_no in text and "装配失败" in text and "ValueError" in text
               for text in messages), messages


# --- B8 profile_of 的单一所有者 ------------------------------------------


def test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result(session, seed_dir):
    """**守的是「不产生第二个所有者」**：把 ``fitness_test_result`` 的行改坏，
    ``profile_of`` 的结果**一个字都不变**。

    变异本条要抓的实现：让 ``profile_of`` 回去查 ``fitness_test_result`` 重算七项得分
    或 BMI —— 那样本条当场红。理由有两条（简报 Task 7「``profile_of`` 的输入来源」）：
    ① 同一份身高体重在两处被算成 BMI，任一处改口径就漂移；② 更要紧的是
    ``fitness_test_result`` 是**会被后续批次 upsert 覆盖的**存量表，读它就等于用今天的
    数据解释昨天的处方，而 spec §4.3 要求的是「判定当时」的输入。
    """
    sem = _semester_id(session)
    run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
    target = session.scalar(
        select(Prescription.student_id).order_by(Prescription.id).limit(1)
    )
    before = profile_of(session, target, AS_OF)
    assert before.endurance_score is not None, "反空转：这个人的耐力两项确实有得分"

    # 把这个人**所有**体测行改坏：身高体重与七项得分全换成别的值
    rows = list(session.scalars(
        select(M.FitnessTestResult).where(M.FitnessTestResult.student_id == target)
    ))
    assert rows, "反空转：这个人确实有体测行可改"
    for row in rows:
        row.height_cm = 999.0
        row.weight_kg = 999.0
        row.total_score = 0
        for item in ScoredItem:
            setattr(row, f"score_{item.value}", 0)
    session.flush()

    after = profile_of(session, target, AS_OF)
    assert after == before, (
        "profile_of 读到了 fitness_test_result：那是第二个所有者，且会让"
        "「判定当时的输入」变成「今天库里的值」（spec §4.3）"
    )
    assert after.bmi == before.bmi and after.endurance_score == before.endurance_score


# ⚠️ 这里原有一条 ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``
# （Task 7 首轮交付）：它钉的是「触发 2 的比较对象查不到时响亮抛 ``ValueError``」，
# 而那个失效形态的前提是「标签只能 ``outerjoin`` 回读同一天的 ``stratification_result``」。
# **fix round 1 的 F1-1 给 ``prescription`` 加了 ``label_at_generation`` 列**（判定输入快照
# 在处方行上，与 P6-A3 给 ``microcycle_weeks`` 快照同构），该前提消失 → 那个 ``ValueError``
# 分支**结构上不可达**，守卫随之删掉。取代它的是 B5 节的
# ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``：同一个数据形状
# （删掉那一天的分层行），断言的是**相反**的结论——触发 2 仍然成立、整批不回滚。


def test_profile_of_fails_loudly_without_a_stratification_row(bare):
    """当天没有分层结果 → ``ValueError``，**不是**一个全 ``None`` 的画像。

    静默返回的话，装配器会拿到 ``endurance_score = None`` → 个体修正系数 ``1.0`` →
    一张**看起来完全正常**的处方，而它其实建立在「这个人今天没被分层」之上。
    """
    session, sem = bare
    student = _student(session, "2025001001")
    with pytest.raises(ValueError) as exc:
        profile_of(session, student.id, AS_OF)
    assert "没有分层结果" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        profile_of(session, 999999, AS_OF)
    assert "查无 id=999999" in str(exc.value)


def test_a_batch_from_another_semester_is_rejected_loudly(bare):
    """``semester_id`` 这个形参**没有被丢弃**（Ruling 86）：批次与学期对不上就响亮失败。

    ``prescription`` 表没有 ``semester_id`` 列，故这个形参唯一的实质用途就是这道前置校验
    ——``_replay_cleanup`` 按 ``batch_id`` 删，接错批次会让重放删不到本批的处方行、
    于是翻倍（Plan 01 Ruling 32 的同源缺陷）。两档各断言一次：查无这一行、学期对不上。
    """
    session, sem = bare
    other = M.Semester(name="2024-2025-1", start_date=dt.date(2024, 9, 1),
                       end_date=dt.date(2025, 1, 20), weeks=16, is_current=False)
    session.add(other)
    session.flush()
    batch = _batch(session, sem, AS_OF)

    with pytest.raises(ValueError) as exc:
        _generate(session, other.id, batch, AS_OF)
    assert "semester_id" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        _generate(session, sem, 999999, AS_OF)
    assert "daily_sync_run 里查无 id=999999" in str(exc.value)
    # 两次都**没有**写进任何处方行（校验在循环之前）
    assert _count(session, Prescription) == 0


# --- B9 Task 8：weekly_factors_of（ORM 行 → WeeklyFactor 值对象）-----------
#
# ⚠️ **本节的调整行一律直接插**（P8-A4，照 Task 2 的 ``sync_exercises`` / ``sync_templates``
# 先例）：``weekly_adjustment`` 表**今天 0 行**——``source = "auto"`` 是 Plan 03 的预警落地、
# ``"teacher"`` 要等 Plan 03 的教师端 CRUD API，故 ``weekly_factors_of`` 在生产路径上今天
# **没有调用方**。不靠管道产出，就不会把「读模型的守卫」与「生成阶段的守卫」缠在一起。


def _prescription_with(session, sem, day, *student_nos):
    """给 ``*student_nos`` 各生成一张红层处方，返回 ``([Prescription 行], batch_id)``。"""
    batch = _batch(session, sem, day)
    for student_no in student_nos:
        student = _student(session, student_no)
        _strat_row(session, student, day, batch, "red")
    assert _generate(session, sem, batch, day).generated == len(student_nos)
    rows = session.scalars(
        select(Prescription).order_by(Prescription.student_id)
    ).all()
    return list(rows), batch


def _adjust(session, prescription, batch, *, week, factor, reason, source, created_at):
    """直接插一行 ``weekly_adjustment``，返回它（``created_at`` 一律显式给：那一列无缺省）。"""
    row = WeeklyAdjustment(
        prescription_id=prescription.id, batch_id=batch, week=week, factor=factor,
        reason=reason, source=source, created_at=created_at,
    )
    session.add(row)
    session.flush()
    return row


def _emitted(session, call):
    """跑 ``call()``，同时抓下真正发给 DBAPI 的 SQL 串，返回 ``(结果, [sql, …])``。

    ⚠️ 用 ``before_cursor_execute`` 而不是自己拼一个 ``select`` 去比对：后者是**同源**
    （硬规矩 #35），只有前者量到的是 ``weekly_factors_of`` **真的**发出去的那一句。
    """
    engine = session.get_bind()
    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        result = call()
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return result, seen


def test_weekly_factors_of_returns_an_empty_list_for_an_unadjusted_prescription(bare):
    """零条调整 → 空列表；**查无此处方**也是空列表（两档同形，本函数刻意不区分）。

    两者的正确渲染都是「本周没有微调、照骨架执行」。区分它们需要多查一次 ``prescription``，
    而 Plan 03 的 API 层本来就持有那一行（它得先知道 ``generated_on`` 与
    ``microcycle_weeks`` 才能调 :func:`~app.domain.prescription.weekly.current_week`）。
    """
    session, sem = bare
    (prescription,), _batch_id = _prescription_with(session, sem, AS_OF, "2025001001")
    assert weekly_factors_of(session, prescription.id) == []
    assert weekly_factors_of(session, 999999) == []
    assert _count(session, WeeklyAdjustment) == 0


def test_weekly_factors_of_converts_every_row_and_sorts_by_created_at(bare):
    """三个字段逐个映射，顺序按 ``created_at``，且**不按 ``week`` 过滤**。

    ⚠️ 插入顺序刻意与 ``created_at`` 顺序**相反**（先插最晚的那一条），于是「按 ``id``
    排」与「按 ``created_at`` 排」给出不同的答案——没有这一手，本条在 SQLite 上是恒真式
    （``id`` 自增，而全表扫描恒按 rowid 升序）。

    期望值**字面写死**（硬规矩 #35）：``(week, factor, reason, source)`` 四元组的顺序就是
    ``created_at`` 的升序，其中第 2 周那一条**也在**结果里（过滤是
    :func:`~app.domain.prescription.weekly.weekly_training_sheet` 的活，不是本函数的）。
    """
    session, sem = bare
    (prescription,), batch = _prescription_with(session, sem, AS_OF, "2025001001")
    # 插入顺序：最晚 → 最早 → 更晚（id 顺序因此是 1,2,3 而 created_at 顺序是 2,1,3）
    _adjust(session, prescription, batch, week=2, factor=1.1, reason="第二次",
            source="auto", created_at=dt.datetime(2025, 9, 16, 9, 0))
    _adjust(session, prescription, batch, week=1, factor=0.8, reason="第一次",
            source="teacher", created_at=dt.datetime(2025, 9, 15, 18, 0))
    _adjust(session, prescription, batch, week=1, factor=0.9, reason="第三次",
            source="teacher", created_at=dt.datetime(2025, 9, 17, 8, 0))

    got = weekly_factors_of(session, prescription.id)
    assert all(isinstance(item, WeeklyFactor) for item in got)
    assert [(f.week, f.factor, f.reason, f.source) for f in got] == [
        (1, 0.8, "第一次", "teacher"),
        (2, 1.1, "第二次", "auto"),
        (1, 0.9, "第三次", "teacher"),
    ]


def test_weekly_factors_of_breaks_a_created_at_tie_by_id(bare):
    """**P8-A4 的 tie-breaker**：``created_at`` 相同 → 按 ``id`` 升序。

    ``created_at`` 是 ``DateTime NOT NULL`` **无缺省**（时钟由调用方注入），故同一秒批量
    插入的多条调整 ``created_at`` **相等**；没有 tie-breaker 时顺序就交给查询计划，
    换引擎/换计划就可能变。而那个顺序是**承重**的：``WeeklySheet.reasons`` / ``sources``
    的顺序就是这个列表的顺序（``WeeklyFactor`` 没有时间戳字段，读模型结构上不可能自己排序）。

    ⚠️ **两半各钉一件事**（硬规矩 #39）：数据面那一半在 **SQLite 上删掉 ``, id`` 也不会红**
    ——``INTEGER PRIMARY KEY`` 是 rowid 别名、表是 B-tree，全表扫描恒按 rowid 升序，
    于是「碰巧对」。真正会红的是 SQL 形状那一半：它量的是**真的发出去的** ``ORDER BY``
    子句里 ``created_at`` 排在 ``id`` 之前。
    """
    session, sem = bare
    (prescription,), batch = _prescription_with(session, sem, AS_OF, "2025001001")
    same_second = dt.datetime(2025, 9, 16, 9, 0, 0)
    first = _adjust(session, prescription, batch, week=1, factor=0.8, reason="同一秒第一条",
                    source="teacher", created_at=same_second)
    second = _adjust(session, prescription, batch, week=1, factor=0.9, reason="同一秒第二条",
                    source="auto", created_at=same_second)
    assert first.id < second.id, (first.id, second.id)

    got, seen = _emitted(session, lambda: weekly_factors_of(session, prescription.id))
    # ① 数据面：created_at 相等时按 id 升序
    assert [f.reason for f in got] == ["同一秒第一条", "同一秒第二条"]
    assert [f.source for f in got] == ["teacher", "auto"]
    # ② SQL 面：真的发出去的那一句里两个排序键都在，且 created_at 在前
    select_sql = next(s for s in seen if "FROM weekly_adjustment" in s)
    assert "ORDER BY" in select_sql, select_sql
    tail = select_sql.split("ORDER BY", 1)[1]
    assert ".created_at" in tail, tail
    assert ".id" in tail, tail
    assert tail.index(".created_at") < tail.index(".id"), tail


def test_weekly_factors_of_only_reads_the_prescription_it_was_asked_about(bare):
    """按 ``prescription_id`` 过滤：另一张处方的调整行**一条都不许漏进来**。

    漏进来的失效形态很阴：两张处方同属一个学生（换过一次），而「本周训练单」是
    ``骨架第 N 周 × 该周全部 factor`` 的**累乘**，多一条 ``0.8`` 就把那一周再打八折、
    全程不报错（与 ``_replay_cleanup`` 漏删 ``weekly_adjustment`` 是同一条代价的形状）。
    """
    session, sem = bare
    (older, newer), batch = _prescription_with(
        session, sem, AS_OF, "2025001001", "2025001002"
    )
    assert older.id != newer.id
    _adjust(session, older, batch, week=1, factor=0.5, reason="别人的调整",
            source="auto", created_at=dt.datetime(2025, 9, 15, 8, 0))
    _adjust(session, newer, batch, week=1, factor=0.8, reason="自己的调整",
            source="teacher", created_at=dt.datetime(2025, 9, 15, 9, 0))

    assert [f.reason for f in weekly_factors_of(session, newer.id)] == ["自己的调整"]
    assert [f.factor for f in weekly_factors_of(session, older.id)] == [0.5]


def test_weekly_adjustment_sources_are_pinned_verbatim():
    """**P8-A5 的漂移测试**：``source`` 值域的唯一所有者字面就是 ``{"auto", "teacher"}``。

    ``WeeklyFactor.source`` 在 domain 侧是**裸 ``str``**（P8-A5：domain 不另立词表），故
    那条值域只住在这里 —— DB 的类常量 :attr:`WeeklyAdjustment.SOURCES` 与它生成的
    ``ck_weekly_adjustment_source``。⚠️ **这条测试必须住在 pipeline 层**：domain 不能
    import ORM（:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 不含
    ``sqlalchemy``），故 ``tests/domain/test_prescription_weekly.py`` 那一条钉的是**反面**
    （domain 侧确实没有第二份词表）。与 Task 5 的 P5-A9（``ADDON_TRIGGERS`` /
    ``EQUIVALENCE_TRIGGERS`` 两套词表）是同一条纪律。

    ⚠️ 顺带钉住 **P8-A6 的 DB 那一半**：这张表**只有**一条 CHECK，而它管的是 ``source``；
    ``factor`` 那一列**刻意没有** CHECK —— ``(0, 2]`` 是**读模型的语义**、不是数据的形状，
    Plan 03 可能要放宽上界（届时改的是 ``weekly.py`` 的两个私有常量，而不是一次重建库）。
    谁「好心」给它补一条 CHECK，本条当场红。
    """
    assert WeeklyAdjustment.SOURCES == {"auto", "teacher"}

    checks = [
        c for c in WeeklyAdjustment.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    assert [c.name for c in checks] == ["ck_weekly_adjustment_source"], checks
    sqltext = str(checks[0].sqltext)
    assert "'auto'" in sqltext and "'teacher'" in sqltext, sqltext
    # P8-A6：factor 那一列刻意没有 CHECK（唯一那条 CHECK 管的是 source）
    assert not [c for c in checks if "factor" in str(c.sqltext)]


def test_db_rows_reach_the_read_model_with_their_order_intact(bare):
    """端到端：**直接插的** ``weekly_adjustment`` 行 → ``weekly_factors_of`` →
    :func:`~app.domain.prescription.weekly.weekly_training_sheet`。

    两个半截（pipeline 的读取口与 domain 的读模型）能不能对上是本 Task 的交付物本身：
    ``WeeklySheet.reasons`` / ``sources`` 的顺序**就是** DB 的顺序，而 ``0.8 × 1.25 = 1.0``
    让 ``sessions`` 与骨架**逐字段相同**——于是「先减量再加量回到基线」这件事在库 → 值
    对象 → 训练单这一整条链上都可验证（spec §8.4 的「可追溯、可回滚」）。

    ⚠️ 骨架在**内存里重新装配**（走生产的 ``profile_of`` + ``assemble``），不从
    ``prescription.training_package`` 那个 JSON 列反序列化：JSON → ``TrainingPackage``
    的反向映射今天**不存在**（那是 Plan 03 的 API 层的活），而本 Task 不该顺手造一个。
    ⚠️ 模板 id 从处方行的 ``template_ref`` 读、**不写死**：``bare`` 夹具那个红层学生的
    ``C = False``，匹配到的是 ``RED-END-NOR-*`` 而不是 ``RED-END-ABN-01``。
    """
    session, sem = bare
    (prescription,), batch = _prescription_with(session, sem, AS_OF, "2025001001")
    _adjust(session, prescription, batch, week=1, factor=0.8, reason="本周月考，减量",
            source="teacher", created_at=dt.datetime(2025, 9, 15, 18, 0))
    _adjust(session, prescription, batch, week=1, factor=1.25, reason="RED_RPE_SUSTAINED",
            source="auto", created_at=dt.datetime(2025, 9, 16, 9, 0))

    student_id = prescription.student_id
    profile = profile_of(session, student_id, AS_OF)
    pkg = assemble(profile, templates()[prescription.template_ref], AS_OF,
                   exercises=exercises())

    sheet = weekly_training_sheet(pkg, 1, weekly_factors_of(session, prescription.id))
    assert sheet.week == 1
    assert sheet.factor == pytest.approx(1.0)
    assert sheet.reasons == ("本周月考，减量", "RED_RPE_SUSTAINED")
    assert sheet.sources == ("teacher", "auto")
    assert sheet.paused is False
    assert sheet.sessions == pkg.weeks[0].sessions
    # 第 2 周一条调整都没有 → factor 1.0、reasons/sources 空（过滤是读模型的活）
    week2 = weekly_training_sheet(pkg, 2, weekly_factors_of(session, prescription.id))
    assert week2.factor == 1.0
    assert week2.reasons == () and week2.sources == ()


