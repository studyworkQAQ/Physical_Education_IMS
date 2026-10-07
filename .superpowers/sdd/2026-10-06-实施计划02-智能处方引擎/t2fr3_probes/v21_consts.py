# -*- coding: utf-8 -*-
"""Refined: after stripping docstrings, enumerate the code-level literal constants
that differ between baseline 966eae0 and the worktree, for every changed .py."""
import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BASE = "966eae0"
DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def strip(tree):
    for node in ast.walk(tree):
        if isinstance(node, DOC_OWNERS) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                node.body = node.body[1:]
                if not node.body:
                    node.body = [ast.Pass()]
    return tree


def code_consts(src):
    out = []
    for n in ast.walk(strip(ast.parse(src))):
        if isinstance(n, ast.Constant):
            out.append(n.value)
    return out


def git_show(rel):
    r = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"git show failed {rel}")
    return r.stdout.decode("utf-8")


changed = [c for c in subprocess.run(["git", "diff", "--name-only", "--", "backend"],
                                     cwd=ROOT, capture_output=True).stdout.decode().split()
           if c.endswith(".py")]
total = 0
print(f"changed files under backend/ ({len(changed)}); code-level literal constants "
      f"that differ from {BASE} (docstrings stripped):")
for rel in changed:
    cur = (ROOT / rel).read_bytes().decode("utf-8")
    old = git_show(rel)
    a, b = code_consts(old), code_consts(cur)
    only_old = [x for x in a if a.count(x) > b.count(x)]
    only_new = [x for x in b if b.count(x) > a.count(x)]
    # dedupe preserving order
    so, sn = list(dict.fromkeys(only_old)), list(dict.fromkeys(only_new))
    total += len(so) + len(sn)
    print(f"  {rel}: -{len(so)} / +{len(sn)}")
    for x in so:
        print(f"      - {x!r}")
    for x in sn:
        print(f"      + {x!r}")
print(f"TOTAL differing code-level literals = {total}")
sys.exit(0)
