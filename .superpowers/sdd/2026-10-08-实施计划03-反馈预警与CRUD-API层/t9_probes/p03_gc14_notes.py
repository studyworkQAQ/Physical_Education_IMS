"""Task 9 探针 03：读既有 13 例的 note / dominant_bucket / 6 项得分，为 GC14 选输入。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.domain.indicators import (  # noqa: E402
    COLUMN_BY_ITEM,
    ITEM_BUCKET,
    WEAKNESS_ITEMS,
    Sex,
    age_group_of,
    score_item,
)
from app.refdata import standard  # noqa: E402

GOLDEN = BACKEND / "tests" / "fixtures" / "golden_cases.json"
cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
table = standard()

print("COLUMN_BY_ITEM:", {k.value: v for k, v in COLUMN_BY_ITEM.items()})
print("ITEM_BUCKET:", {k.value: v for k, v in ITEM_BUCKET.items()})
print()
print("== 既有 13 例 ==")
for case, exp in zip(cases["input"], cases["expected"]):
    sex = Sex(case["sex"])
    ag = age_group_of(case["age"])
    scores = {}
    for item in WEAKNESS_ITEMS:
        col = COLUMN_BY_ITEM[item]
        raw = case["curr"].get(col)
        scores[item.value] = None if raw is None else score_item(table, item, raw, sex, ag)
    bmi_raw = case["curr"]["weight_kg"] / (case["curr"]["height_cm"] / 100) ** 2
    print(f"  {exp['student_id']} sex={case['sex']:6s} age={case['age']} ag={ag} "
          f"W={exp['W']} C={exp['C']} valid={exp['valid_count']} "
          f"dom={exp['dominant_bucket']:18s} tpl={exp['template_id']} "
          f"trend={exp['trend']} hit={exp['hit_rules']}")
    print(f"      bmi={exp['bmi']} (raw {bmi_raw:.4f})  bf={case['body_comp']['body_fat_pct']} "
          f"mm={case['body_comp']['muscle_mass_kg']} p20={case['snapshot_muscle_p20']}")
    print(f"      scores={scores}")
    print(f"      note: {exp['note']}")
    print(f"      reason: {exp['reason']}")
    print(f"      explain: {exp['explain']}")
    print()
