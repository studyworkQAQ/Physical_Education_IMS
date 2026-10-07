import pathlib, re, sys
for rel, pats in [
    ("backend/app/domain/derive.py", ["if score < line:", "top = max(counts.values())", "dominant = None"]),
    ("backend/app/domain/stratify.py", ["MIN_VALID_COUNT = 4", "W_RED_UNCONDITIONAL = 4", "_W_AT_LEAST_TWO = 2"]),
    ("backend/app/domain/indicators.py", ["def score_item", "return None"]),
    ("backend/app/domain/tables.py", ["def ", "return"]),
    ("backend/app/domain/prescription/templates.py", ["return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)"]),
    ("backend/app/domain/prescription/exercises.py", ["if IMPACT_RANK[mapping.max_impact] >= ceiling_rank:", "ceiling_rank = IMPACT_RANK[impact_ceiling]"]),
    ("backend/app/refdata_prescription.py", ["folder = DATA_DIR / PRESCRIPTION_DIRNAME", "paths = sorted(folder.glob(\"*.yaml\"))"]),
]:
    t = pathlib.Path(rel).read_bytes().decode("utf-8")
    for p in pats:
        print("%-52s %-70s hits=%d" % (rel, p[:68], t.count(p)))
