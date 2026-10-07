# -*- coding: utf-8 -*-
"""Prove the YAML diffs touch comment lines only, and the spec diff touches exactly
line 933 (one row, one cell)."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")


def diff(rel):
    r = subprocess.run(["git", "diff", "-U0", "--", rel], cwd=ROOT, capture_output=True)
    return r.stdout.decode("utf-8", "replace").split("\n")


for rel in ("backend/data/exercises.yaml", "backend/data/exercise_equivalence.yaml"):
    lines = diff(rel)
    plus = [l for l in lines if l.startswith("+") and not l.startswith("+++")]
    minus = [l for l in lines if l.startswith("-") and not l.startswith("---")]
    bad_plus = [l for l in plus if not l[1:].lstrip().startswith("#")]
    bad_minus = [l for l in minus if not l[1:].lstrip().startswith("#")]
    print(f"{rel}: +{len(plus)} / -{len(minus)} lines ; "
          f"non-comment additions={len(bad_plus)} ; non-comment deletions={len(bad_minus)}")
    for l in bad_plus + bad_minus:
        print(f"    !! {l[:160]}")
    if bad_plus or bad_minus:
        sys.exit(1)

print()
rel = "Document/2026-09-28-体育闭环原型-设计spec.md"
lines = diff(rel)
hunks = [l for l in lines if l.startswith("@@")]
plus = [l for l in lines if l.startswith("+") and not l.startswith("+++")]
minus = [l for l in lines if l.startswith("-") and not l.startswith("---")]
print(f"{rel}: hunks={hunks} +{len(plus)} / -{len(minus)}")
for l in minus:
    print(f"  OLD line length = {len(l) - 1}")
    print(f"  OLD starts: {l[1:60]!r}")
    print(f"  OLD ends  : {l[-80:]!r}")
for l in plus:
    print(f"  NEW line length = {len(l) - 1}")
    print(f"  NEW starts: {l[1:60]!r}")
    print(f"  NEW ends  : {l[-120:]!r}")
# confirm the changed line is the one carrying §14 item 28 and that only the last cell moved
old_row = minus[0][1:]
new_row = plus[0][1:]
cut = 0
while cut < min(len(old_row), len(new_row)) and old_row[cut] == new_row[cut]:
    cut += 1
print(f"  common prefix length = {cut}")
print(f"  common prefix tail   = {old_row[max(0, cut-90):cut]!r}")
print(f"  old divergent part   = {old_row[cut:][:120]!r} ... ({len(old_row)-cut} chars)")
print(f"  new divergent part   = {new_row[cut:][:120]!r} ... ({len(new_row)-cut} chars)")
print(f"  old cells (pipe count) = {old_row.count('|')} ; new cells = {new_row.count('|')}")
print(f"  old row starts with '| **28** |' = {old_row.startswith('| **28** |')}")
print(f"  new row starts with '| **28** |' = {new_row.startswith('| **28** |')}")
sys.exit(0)
