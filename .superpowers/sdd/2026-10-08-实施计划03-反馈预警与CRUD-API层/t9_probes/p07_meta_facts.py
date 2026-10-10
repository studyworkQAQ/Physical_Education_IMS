"""Task 9 探针 07：为 GC14 的 _meta 改写取两个事实（运行时口径）。

① 既有 13 例的 week1_block0_hr_zone 与 safety_* 四格（改写 expected_schema 要引它们）；
② 男「大一、大二」那一组的 sample_size 在 13 人 vs 14 人下各是多少
   （percentile_note 要说「行数不变、只把该组的 sample_size 抬一格」，两个数都得实测）。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.pipeline import run_stratify  # noqa: E402

GOLDEN = BACKEND / "tests" / "fixtures" / "golden_cases.json"
cases = json.loads(GOLDEN.read_text(encoding="utf-8"))

print("== ① 既有 13 例的 hr_zone / needs_review / substitution_count / triggers / skipped ==")
for exp in cases["expected"]:
    print(f"  {exp['student_id']} hr_zone={exp['week1_block0_hr_zone']} "
          f"ref={exp['week1_block0_exercise_ref']} vol={exp['week1_block0_weekly_volume']}"
          f"({exp['week1_block0_volume_unit']}) nr={exp['needs_review']} "
          f"subs={exp['safety_substitution_count']} trig={exp['safety_triggers']} "
          f"skip={exp['safety_skipped']}")


def _groups(inputs):
    _persons, snapshot = run_stratify._from_golden_cases(inputs)
    out = {}
    for row in snapshot:
        key = (row.item.value, row.sex.value, row.age_group)
        out.setdefault(key, []).append((row.sample_size, row.source))
    return snapshot, out


gc14_curr = {
    "height_cm": 175.0, "weight_kg": 95.0, "vital_capacity_ml": 3700.0,
    "sprint_50m_s": 9.5, "sit_and_reach_cm": 3.7, "standing_jump_cm": 228.0,
    "strength_count": 10.0, "distance_run_s": 292.0,
}
gc14 = {
    "student_id": "GC14", "sex": "male", "age": 19, "years": 1.0,
    "snapshot_muscle_p20": 33.2,
    "body_comp": {"body_fat_pct": 28.0, "muscle_mass_kg": 45.0, "smi": None},
    "curr": gc14_curr, "prev": dict(gc14_curr),
}

print("\n== ② 快照分组与 sample_size：13 人 vs 14 人 ==")
for label, inputs in (("13 人", cases["input"]), ("14 人", cases["input"] + [gc14])):
    snapshot, groups = _groups(inputs)
    sizes = sorted({v[0][0] for v in groups.values()})
    print(f"  {label}: rows={len(snapshot)} groups={len(groups)} "
          f"sources={sorted({v[0][1] for v in groups.values()})} sizes={sizes}")
    male_lower = [(k, v[0]) for k, v in sorted(groups.items())
                  if v and k[1] == "male" and k[2] == "大一、大二"]
    print(f"      male/大一、大二 的 6 项 (sample_size, source): "
          f"{[(k[0], s) for k, s in male_lower]}")
    print(f"      p25 lines（male 大一、大二）: "
          f"{ {k[0]: v for k, v in []} }")

# 两次的 p25 判定线是否逐格相同（percentile_note 要说「24 行不变、判定线不变」）
s13, g13 = _groups(cases["input"])
s14, g14 = _groups(cases["input"] + [gc14])
rows13 = {(r.item.value, r.sex.value, r.age_group): (r.p10, r.p20, r.p25, r.p50, r.p75, r.source)
          for r in s13}
rows14 = {(r.item.value, r.sex.value, r.age_group): (r.p10, r.p20, r.p25, r.p50, r.p75, r.source)
          for r in s14}
print("\n== ③ 键集与五档判定线是否逐格相同 ==")
print("  keys equal:", set(rows13) == set(rows14))
diff = {k: (rows13[k], rows14[k]) for k in rows13 if rows13[k] != rows14.get(k)}
print("  differing rows:", diff if diff else "NONE（判定线逐格相同，只有 sample_size 变）")
size13 = {(r.item.value, r.sex.value, r.age_group): r.sample_size for r in s13}
size14 = {(r.item.value, r.sex.value, r.age_group): r.sample_size for r in s14}
changed = {k: (size13[k], size14[k]) for k in size13 if size13[k] != size14[k]}
print("  sample_size changed groups:", changed)
