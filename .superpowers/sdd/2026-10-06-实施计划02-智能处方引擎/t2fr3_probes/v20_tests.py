# -*- coding: utf-8 -*-
"""Verify backend/tests/** changes are comment/docstring-only except the two
authorized non-comment edits (assert message + 2 fingerprint constants), and that
the set of test functions is unchanged vs baseline."""
import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BASE = "966eae0"
CRLF = bytes([13, 10])
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


def dump(src):
    return ast.dump(strip_docstrings(ast.parse(src)), include_attributes=False)


def git_show(rel):
    r = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"git show failed {rel}")
    return r.stdout.decode("utf-8")


changed = subprocess.run(["git", "diff", "--name-only", "--", "backend/tests"],
                         cwd=ROOT, capture_output=True).stdout.decode().split()
print(f"changed test files ({len(changed)}):")
for rel in changed:
    cur = (ROOT / rel).read_bytes().decode("utf-8")
    old = git_show(rel)
    d_cur, d_old = dump(cur), dump(old)
    status = "SAME (comment/docstring only)" if d_cur == d_old else "AST DIFFERS"
    print(f"  {rel}: {status}")
    if d_cur != d_old:
        # enumerate exactly which string constants differ
        def consts(src):
            out = []
            for n in ast.walk(ast.parse(src)):
                if isinstance(n, ast.Constant) and isinstance(n.value, (str, int, float)):
                    out.append(n.value)
            return out
        a, b = consts(old), consts(cur)
        only_old = [x for x in a if x not in b]
        only_new = [x for x in b if x not in a]
        print(f"    literal constants only in BASELINE ({len(only_old)}):")
        for x in only_old:
            print(f"      - {x!r}")
        print(f"    literal constants only in CURRENT ({len(only_new)}):")
        for x in only_new:
            print(f"      + {x!r}")

print()
print("test-function inventory (def test_*) baseline vs current, whole backend/tests tree")


def inventory(get):
    out = {}
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE, "backend/tests"],
                       cwd=ROOT, capture_output=True)
    for rel in r.stdout.decode().split():
        if not rel.endswith(".py"):
            continue
        src = get(rel)
        if src is None:
            continue
        names = [n.name for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        out[rel] = names
    return out


base_inv = inventory(git_show)
cur_inv = inventory(lambda rel: (ROOT / rel).read_bytes().decode("utf-8")
                    if (ROOT / rel).exists() else None)
nb = sum(len(v) for v in base_inv.values())
nc = sum(len(v) for v in cur_inv.values())
print(f"  baseline {BASE}: {len(base_inv)} files, {nb} test functions")
print(f"  current       : {len(cur_inv)} files, {nc} test functions")
diffs = {k for k in set(base_inv) | set(cur_inv)
         if sorted(base_inv.get(k, [])) != sorted(cur_inv.get(k, []))}
print(f"  files whose test-function set changed: {sorted(diffs) if diffs else 'NONE'}")
sys.exit(0 if (nb == nc and not diffs) else 1)
