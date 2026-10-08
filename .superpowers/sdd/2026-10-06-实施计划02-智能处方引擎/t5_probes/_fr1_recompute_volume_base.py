# -*- coding: utf-8 -*-
"""F1-1 的期望值独立重算（**先算后看**：本脚本不复用 assembler 的任何代码）。

口径（派单 F1-1）：键 = 实际出现过的 volume_unit；值 = 该单位下所有 block 的
base × sessions_per_week 之和，round(…, 1)。
base：{sets, work_min, rest_min} → work_min × sets（单位 min）；
      {rounds, reps} → rounds × reps（单位 reps）。

本脚本直接从 YAML 读原始 structure 与 sessions，自己数 sessions_per_week、自己做乘法，
**不 import app.domain.prescription.assembler**，故不构成硬规矩 #35 的同源。
"""
import collections
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[4]
TPL_DIR = ROOT / "backend" / "data" / "prescription"

DURATION = {"sets", "work_min", "rest_min"}
REPS = {"rounds", "reps"}


def base_of(structure):
    keys = set(structure)
    if keys == DURATION:
        return float(structure["work_min"] * structure["sets"]), "min"
    if keys == REPS:
        return float(structure["rounds"] * structure["reps"]), "reps"
    raise AssertionError(f"未预期的键集 {sorted(keys)}")


rows = []
for path in sorted(TPL_DIR.glob("*.yaml")):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    sessions = doc["sessions"]
    per_ref = collections.Counter()
    for s in sessions:
        for b in s["blocks"]:
            per_ref[b["exercise_ref"]] += 1
    # 口径 A：逐 (session, block) 累加 base
    acc_a = collections.OrderedDict()
    for s in sessions:
        for b in s["blocks"]:
            base, unit = base_of(b["structure"])
            acc_a[unit] = acc_a.get(unit, 0.0) + base
    # 口径 B：去重 ref 后 base × sessions_per_week
    acc_b = collections.OrderedDict()
    seen = {}
    for s in sessions:
        for b in s["blocks"]:
            seen.setdefault(b["exercise_ref"], b["structure"])
    for ref, structure in seen.items():
        base, unit = base_of(structure)
        acc_b[unit] = acc_b.get(unit, 0.0) + base * per_ref[ref]
    a = {u: round(v, 1) for u, v in acc_a.items()}
    b = {u: round(v, 1) for u, v in acc_b.items()}
    rows.append((doc["template_id"], doc.get("weekly_frequency"), len(sessions),
                 dict(per_ref), a, b, a == b))

print(f"模板数 = {len(rows)}")
for tid, wf, nsess, per_ref, a, b, same in rows:
    print(f"{tid:18s} weekly_frequency={wf} sessions={nsess} per_ref={per_ref}")
    print(f"    口径A(逐次累加 base) = {a}")
    print(f"    口径B(base × spw)    = {b}   两口径相同={same}")

units_seen = collections.Counter()
for _tid, _wf, _n, _pr, a, _b, _s in rows:
    units_seen[tuple(sorted(a))] += 1
print(f"\n键集分布（18 套）= {dict(units_seen)}")
print(f"含 'unspecified' 的模板数 = "
      f"{sum(1 for *_x, a, _b, _s in rows if 'unspecified' in a)}")
sys.exit(0)
