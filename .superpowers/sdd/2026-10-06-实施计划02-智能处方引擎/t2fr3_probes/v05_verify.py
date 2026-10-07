# -*- coding: utf-8 -*-
"""fr3 independent verification of I-1 / I-2 / I-3 / M-4 / M-7 / M-9 facts."""
import ast
import pathlib
import sqlite3
import sys

sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")

import yaml  # noqa: E402

from app.domain.prescription.exercises import IMPACT_RANK, ImpactLevel  # noqa: E402

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
DATA = ROOT / "backend/data"

print("=" * 70)
print("I-1  str()/len/sqlite3 bind")
print("=" * 70)
s = str(ImpactLevel.HIGH)
print(f"str(ImpactLevel.HIGH)      = {s!r}   len = {len(s)}")
print(f"len('ImpactLevel.HIGH')    = {len('ImpactLevel.HIGH')}")
print(f"repr(ImpactLevel.HIGH)     = {ImpactLevel.HIGH!r}   len = {len(repr(ImpactLevel.HIGH))}")
print(f"format(ImpactLevel.HIGH)   = {format(ImpactLevel.HIGH)!r}   len = {len(format(ImpactLevel.HIGH))}")
print(f"ImpactLevel.HIGH.value     = {ImpactLevel.HIGH.value!r}   len = {len(ImpactLevel.HIGH.value)}")
print(f"isinstance(x, str)         = {isinstance(ImpactLevel.HIGH, str)}")

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE t (lv VARCHAR(8))")
con.execute("INSERT INTO t (lv) VALUES (?)", (ImpactLevel.HIGH,))
row = con.execute("SELECT lv, typeof(lv), length(lv) FROM t").fetchone()
print(f"raw sqlite3 bind ImpactLevel.HIGH -> value={row[0]!r} typeof={row[1]} length()={row[2]}")
con.execute("DELETE FROM t")
con.execute("INSERT INTO t (lv) VALUES (?)", (str(ImpactLevel.HIGH),))
row2 = con.execute("SELECT lv, typeof(lv), length(lv) FROM t").fetchone()
print(f"raw sqlite3 bind str(...)         -> value={row2[0]!r} typeof={row2[1]} length()={row2[2]}")
con.close()

# what does the SQLAlchemy String bind processor do on sqlite?
from sqlalchemy import String  # noqa: E402
from sqlalchemy.dialects import sqlite as sqlite_dialect  # noqa: E402

dialect = sqlite_dialect.dialect()
bp = String(8).bind_processor(dialect)
print(f"String(8).bind_processor(sqlite dialect) = {bp!r}")
if bp is not None:
    print(f"  processor(ImpactLevel.HIGH) = {bp(ImpactLevel.HIGH)!r}")

print()
print("=" * 70)
print("I-2  AST: which names does each test reference?")
print("=" * 70)
src = (ROOT / "backend/tests/test_refdata_prescription.py").read_bytes().decode("utf-8")
tree = ast.parse(src)
TARGETS = [
    "test_equivalence_never_maps_to_a_higher_impact_level",
    "test_every_high_impact_exercise_has_a_low_substitute",
    "test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable",
    "test_impact_rank_values_are_pinned_verbatim",
]
defs = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in TARGETS:
        defs[node.name] = node
for name in TARGETS:
    node = defs.get(name)
    if node is None:
        print(f"{name:75s} NOT FOUND")
        continue
    ids = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
    print(f"{name:75s} def@:{node.lineno}-{node.end_lineno} "
          f"IMPACT_RANK={'IMPACT_RANK' in ids} IMPACT_DESCENDING={'IMPACT_DESCENDING' in ids}")

print()
print("=" * 70)
print("I-3 / M-9  YAML data facts")
print("=" * 70)
ex = yaml.safe_load((DATA / "exercises.yaml").read_bytes().decode("utf-8"))
eq = yaml.safe_load((DATA / "exercise_equivalence.yaml").read_bytes().decode("utf-8"))
print(f"exercises count = {len(ex)}")
print(f"mappings count  = {len(eq['mappings'])}")
print(f"version         = {eq['version']!r}")
print(f"volume_reduction= {eq['volume_reduction']}")
by_impact = {}
for ref, e in ex.items():
    by_impact.setdefault(e["impact_level"], []).append(ref)
for k in ("high", "medium", "low"):
    print(f"  {k:6s} ({len(by_impact.get(k, []))}): {sorted(by_impact.get(k, []))}")
tos = [m["to"] for m in eq["mappings"]]
from collections import Counter  # noqa: E402
print(f"distinct 'to' ({len(set(tos))}): {sorted(set(tos))}")
print(f"'to' reuse counts: {dict(Counter(tos))}")
low_used = sorted(set(tos) & set(by_impact.get("low", [])))
low_unused = sorted(set(by_impact.get("low", [])) - set(tos))
print(f"low refs used as a target ({len(low_used)}): {low_used}")
print(f"low refs NOT used ({len(low_unused)}): {low_unused}")
print(f"distinct 'from' ({len(set(m['from'] for m in eq['mappings']))}): "
      f"{sorted(set(m['from'] for m in eq['mappings']))}")
print(f"max_impact values: {sorted(set(m['max_impact'] for m in eq['mappings']))}")
print(f"when values: {sorted(set(m['when'] for m in eq['mappings']))}")
print(f"'challenge_task' in any mapping endpoint? "
      f"{'challenge_task' in set(tos) | set(m['from'] for m in eq['mappings'])}")
print(f"equipment distinct ({len(set(e['equipment'] for e in ex.values()))}): "
      f"{sorted(set(e['equipment'] for e in ex.values()))}")
print(f"longest ref = {max(ex, key=len)!r} len={len(max(ex, key=len))}")

print()
print("=" * 70)
print("M-7  how many places literally write the impact order?")
print("=" * 70)
print("IMPACT_RANK literal dict in exercises.py:", IMPACT_RANK)
print("IMPACT_DESCENDING (test side) =", ("high", "medium", "low"))
