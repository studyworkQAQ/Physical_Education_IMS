"""Task 9 探针 04：构造 GC14 候选、跑完整黄金链路、打印它的 23 个 expected 键。

链路逐字复用 tests/integration/test_golden_cases.py 的两条：
  ① stratify_dataset(cases["input"])                        —— 标签那一环
  ② _from_golden_cases → evaluate → stratify → input_snapshot_of
     → match_template → _profile_of → assemble → apply_safety —— 训练包那一环
期望值取法是「跑一次生产、把输出粘进夹具」，然后由实现者逐条人读确认。
"""
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import models  # noqa: E402
from app.domain.indicators import (  # noqa: E402
    COLUMN_BY_ITEM,
    WEAKNESS_ITEMS,
    Sex,
    age_group_of,
    raw_from_score,
    score_item,
)
from app.domain.prescription.assembler import assemble  # noqa: E402
from app.domain.prescription.match import MatchInput, match_template  # noqa: E402
from app.domain.prescription.safety import SafetyInput, apply_safety  # noqa: E402
from app.domain.stratify import Layer, stratify  # noqa: E402
from app.pipeline import run_stratify  # noqa: E402
from app.pipeline.prescription_stage import _profile_of  # noqa: E402
from app.pipeline.run_stratify import input_snapshot_of, stratify_dataset  # noqa: E402
from app.refdata import standard  # noqa: E402
from app.refdata_prescription import equivalence, exercises, templates  # noqa: E402

AS_OF = dt.date(2025, 9, 15)
GOLDEN = BACKEND / "tests" / "fixtures" / "golden_cases.json"
cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
table = standard()

# ---------------------------------------------------------------------------
# GC14 的**目标得分**（6 个短板判定项）。设计意图：
#   * sprint_50m 与 sit_and_reach 两项低于男「大一、大二」的国标 P25（50 / 62）
#     → W = 2、dominant_bucket = speed_flexibility（13 例里**没有一例**是这个桶）；
#   * 其余 4 项取 GC13 的那一组（全部 >= P25）；
#   * body_fat_pct 28.0 > 男生 20% 阈值 → C = True，reasons = ("body_fat_over",)；
#   * muscle_mass_kg 45.0 > 本组 P20 33.2 → muscle_low 那一支不成立；
#   * height 175.0 / weight 95.0 → bmi = round(95 / 1.75^2, 1) = 31.0 > 30
#     → spec §7.4 的触发 1「BMI > 30」在黄金用例里**第一次真的命中**。
#   → R1（W >= 2 且 C）→ red，模板 RED-SPD-ABN-05（block0 = sprint_50m_intervals，HIGH）。
# ---------------------------------------------------------------------------
SEX = "male"
AGE = 19
TARGET = {
    "vital_capacity": 70,
    "sprint_50m": 40,
    "sit_and_reach": 60,
    "standing_jump": 70,
    "pull_up_or_sit_up": 60,
    "distance_run": 50,
}
HEIGHT_CM = 175.0
WEIGHT_KG = 95.0
AGE_GROUP = age_group_of(AGE)

curr = {"height_cm": HEIGHT_CM, "weight_kg": WEIGHT_KG}
for item in WEAKNESS_ITEMS:
    col = COLUMN_BY_ITEM[item]
    raw = raw_from_score(table, item, TARGET[item.value], Sex(SEX), AGE_GROUP)
    back = score_item(table, item, raw, Sex(SEX), AGE_GROUP)
    assert back == TARGET[item.value], (item, raw, back)
    curr[col] = raw
print("curr =", json.dumps(curr, ensure_ascii=False))
print("bmi  =", round(WEIGHT_KG / (HEIGHT_CM / 100) ** 2, 1))
print("P25 lines (male 大一、大二) from GC09:", {k: v for k, v in
      zip(TARGET, (50, 50, 62, 50, 40, 30))})

gc14 = {
    "student_id": "GC14",
    "sex": SEX,
    "age": AGE,
    "years": 1.0,
    "snapshot_muscle_p20": 33.2,
    "body_comp": {"body_fat_pct": 28.0, "muscle_mass_kg": 45.0, "smi": None},
    "curr": curr,
    # prev == curr：6 项 delta 全 0 → trend 稳定、annual_change +0.0（口径同 GC11 / GC13）
    "prev": dict(curr),
}

all_input = cases["input"] + [gc14]

print("\n== ① stratify_dataset(all 14) 的第 14 个结果 ==")
report = stratify_dataset(all_input)
got = report.results[-1]
print(json.dumps(got, ensure_ascii=False, indent=2, default=str))

print("\n== ② 快照行数与 sample_size（复核 percentile_note 的「24 行」是否仍成立）==")
persons, snapshot = run_stratify._from_golden_cases(all_input)
print("snapshot rows:", len(snapshot))
by = {}
for row in snapshot:
    by.setdefault((row.item.value, row.sex.value), set()).add((row.sample_size, row.source))
print("distinct (sample_size, source):", sorted({v for vs in by.values() for v in vs}))
print("items x sex count:", len(by))

print("\n== ③ 训练包那一环（golden_packages 的同一条链路，只算第 14 例）==")
evaluated = run_stratify.evaluate(persons, snapshot)
index = len(all_input) - 1
case = all_input[index]
one = evaluated[index]
result = stratify(one.derived)
snap = input_snapshot_of(one, result, snapshot)
outcome = match_template(
    MatchInput(layer=Layer(snap["label"]), dominant_bucket=snap["dominant_bucket"],
               body_comp_abnormal=snap["C"]),
    templates(),
)
print("snap:", json.dumps(snap, ensure_ascii=False, default=str))
print("match_status:", outcome.status.value)
template = outcome.template
print("template_id:", template.template_id)
age = int(case["age"])
birth = dt.date(AS_OF.year - age, AS_OF.month, AS_OF.day)
student = models.Student(id=index + 1, sex=case["sex"], birth=birth)
profile = _profile_of(student, snap, AS_OF)
print("profile:", profile)
package = assemble(profile, template, AS_OF, exercises=exercises())
safety = apply_safety(
    package,
    SafetyInput(bmi=profile.bmi, muscle_mass_kg=profile.muscle_mass_kg,
                muscle_p10=profile.muscle_p10, body_fat_abnormal=snap["C"]),
    equivalence(), template=template, exercises=exercises(),
)
block = safety.package.weeks[0].sessions[0].blocks[0]
after = safety.package.assembly_snapshot
row = {
    "student_id": case["student_id"],
    "bmi": snap["bmi"],
    "match_status": outcome.status.value,
    "template_id": template.template_id,
    "label_at_generation": snap["label"],
    "week1_block0_exercise_ref": block.exercise_ref,
    "week1_block0_hr_zone": None if block.hr_zone is None else list(block.hr_zone),
    "week1_block0_weekly_volume": block.weekly_volume,
    "week1_block0_volume_unit": block.volume_unit,
    "needs_review": safety.needs_review,
    "safety_substitution_count": len(safety.substitutions),
    "safety_triggers": list(after["safety_triggers"]),
    "safety_skipped": list(after["safety_skipped"]),
}
print(json.dumps(row, ensure_ascii=False, indent=2))
print("\nassembly_snapshot 全部键:", sorted(after))
print("safety_volume_factor:", after["safety_volume_factor"])
print("warnings:", json.dumps(list(safety.warnings), ensure_ascii=False, indent=2))
print("substitution[0]:", safety.substitutions[0] if safety.substitutions else None)
print("blocks in session0:", [(b.exercise_ref, b.impact_level.value, b.weekly_volume,
                               b.volume_unit) for b in safety.package.weeks[0].sessions[0].blocks])
print("\n== ④ 既有 13 例的训练包期望值是否因加了第 14 人而改变 ==")
rows = []
for i, (c, o) in enumerate(zip(all_input, evaluated)):
    r = stratify(o.derived)
    s = input_snapshot_of(o, r, snapshot)
    m = match_template(MatchInput(layer=Layer(s["label"]), dominant_bucket=s["dominant_bucket"],
                                  body_comp_abnormal=s["C"]), templates())
    rows.append((c["student_id"], s["bmi"], m.status.value,
                 None if m.template is None else m.template.template_id))
for (sid, bmi, st, tpl), exp in zip(rows, cases["expected"]):
    same = (bmi == exp["bmi"] and st == exp["match_status"] and tpl == exp["template_id"])
    print(f"  {sid}: {'SAME' if same else 'CHANGED!!'} bmi={bmi} status={st} tpl={tpl}")
