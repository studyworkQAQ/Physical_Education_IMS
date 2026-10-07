# -*- coding: utf-8 -*-
"""Hard rule #32: ast.dump equivalence of backend/app/** vs baseline 966eae0,
after stripping docstrings. Plus two control groups.

usage: python v14_astdiff.py [baseline]
"""
import ast
import copy
import subprocess
import sys

import pathlib

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BASE = sys.argv[1] if len(sys.argv) > 1 else "966eae0"
APP = ROOT / "backend/app"

DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, DOC_OWNERS) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                node.body = node.body[1:]
                if not node.body:
                    node.body = [ast.Pass()]
    return tree


def dump(src: str) -> str:
    return ast.dump(strip_docstrings(ast.parse(src)), annotate_fields=True,
                    include_attributes=False)


def dump_raw(src: str) -> str:
    return ast.dump(ast.parse(src), annotate_fields=True, include_attributes=False)


def git_show(path_rel: str) -> str:
    r = subprocess.run(["git", "show", f"{BASE}:{path_rel}"], cwd=ROOT,
                       capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"git show failed for {path_rel}: {r.stderr.decode('utf-8', 'replace')}")
    return r.stdout.decode("utf-8")


files = sorted(p.relative_to(ROOT).as_posix() for p in APP.rglob("*.py"))
print(f"backend/app/** python files: {len(files)}  (baseline {BASE})")

same_stripped = 0
diff_stripped = []
same_raw = 0
diff_raw = []
for rel in files:
    cur = (ROOT / rel).read_bytes().decode("utf-8")
    old = git_show(rel)
    if dump(cur) == dump(old):
        same_stripped += 1
    else:
        diff_stripped.append(rel)
    if dump_raw(cur) == dump_raw(old):
        same_raw += 1
    else:
        diff_raw.append(rel)

print()
print(f"[MAIN]  ast.dump(strip docstrings) SAME = {same_stripped}/{len(files)} ; "
      f"DIFF = {diff_stripped}")
print(f"[CTRL-1] ast.dump(WITH docstrings)  SAME = {same_raw}/{len(files)} ; "
      f"DIFF count = {len(diff_raw)}")
print("         (control 1 proves the docstring-stripping is doing real work: "
      "these files' docstrings DID change)")
for rel in diff_raw:
    print(f"           docstring-changed: {rel}")

# ---- CONTROL 2: inject real semantic mutations, the gate MUST catch all of them
print()
print("[CTRL-2] injecting real semantic mutations into the current tree; "
      "the stripped-AST gate must catch every one")
MUTATIONS = [
    ("exercises.py: IMPACT_RANK HIGH 0 -> 2",
     "backend/app/domain/prescription/exercises.py",
     "ImpactLevel.HIGH: 0,", "ImpactLevel.HIGH: 2,"),
    ("exercises.py: lookup >= -> >",
     "backend/app/domain/prescription/exercises.py",
     "if IMPACT_RANK[mapping.max_impact] >= ceiling_rank:",
     "if IMPACT_RANK[mapping.max_impact] > ceiling_rank:"),
    ("refdata_prescription.py: drop .value",
     "backend/app/refdata_prescription.py",
     '"impact_level": spec.impact_level.value,', '"impact_level": spec.impact_level,'),
    ("refdata_prescription.py: remove session.flush()",
     "backend/app/refdata_prescription.py",
     "    session.flush()\n    return len(library)", "    return len(library)"),
]
cache = {}
for label, rel, old, new in MUTATIONS:
    if rel not in cache:
        cache[rel] = (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")
    src = cache[rel]
    n = src.count(old)
    if n != 1:
        print(f"  SKIP [{label}] pattern hits = {n} (expected 1)")
        continue
    mutated = src.replace(old, new)
    # confirm on the AST that the mutation really changed code (hard rule #53)
    changed_ast = dump(mutated) != dump(src)
    caught = dump(mutated) != dump(git_show(rel))
    print(f"  {label:52s} ast-changed-by-mutation={changed_ast} "
          f"gate-caught-vs-baseline={caught}")

print()
print("[CTRL-3] the gate is not vacuously SAME: baseline-vs-baseline on a file "
      "that was NOT touched this round")
untouched = "backend/app/domain/indicators.py"
cur = (ROOT / untouched).read_bytes().decode("utf-8")
old = git_show(untouched)
print(f"  {untouched}: bytes-identical-to-baseline(LF-normalised)="
      f"{cur.replace(chr(13)+chr(10), chr(10)) == old} ; stripped-AST SAME={dump(cur)==dump(old)}")

sys.exit(0 if not diff_stripped else 1)
