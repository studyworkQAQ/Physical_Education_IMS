# -*- coding: utf-8 -*-
"""P27 — commit 之后复核报告里 §3 的那几个数（numstat / docstring 行数 / 注释条数）。

⚠️ p14 的 ⓪ 段用 `git diff HEAD`（工作树 vs HEAD），commit 之后它必然是空的、断言会失败。
本脚本改成对 **commit 本身**（`git diff HEAD^ HEAD`）与**代码基线 `6784d57`** 取数。
"""
import ast
import difflib
import io
import pathlib
import subprocess
import tokenize

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
COMMIT = "6784d57"
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py",
         "backend/tests/db/test_models.py",
         "backend/app/pipeline/daily.py"]
GIT = ["git", "-c", "core.quotepath=false"]


def g(*a):
    return subprocess.run(GIT + list(a), cwd=str(ROOT), capture_output=True).stdout.decode("utf-8", "replace")


def norm(s):
    return s.replace("\r\n", "\n")


def base(rel):
    return g("show", "%s:%s" % (COMMIT, rel))


def work(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def docs(src):
    tree = ast.parse(norm(src))
    out = {"<module>": ast.get_docstring(tree) or ""}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = ast.get_docstring(n) or ""
    return out


def comments(src):
    return [t.string for t in tokenize.generate_tokens(io.StringIO(norm(src)).readline)
            if t.type == tokenize.COMMENT]


print("HEAD =", g("rev-parse", "--short", "HEAD").strip(), " HEAD^ =", g("rev-parse", "--short", "HEAD^").strip())
print()
print("=== numstat（对 commit 本身）===")
print(g("diff", "--numstat", "HEAD^", "HEAD").rstrip())
print("  --shortstat:", g("diff", "--shortstat", "HEAD^", "HEAD").strip())
print("  git show --numstat --format='' HEAD:")
print(g("show", "--numstat", "--format=", "HEAD").rstrip())
print()
print("=== name-only（禁区复核）===")
print("  HEAD^..HEAD 全部          =", g("diff", "--name-only", "HEAD^", "HEAD").split())
print("  HEAD^..HEAD -- backend/app/ =", g("diff", "--name-only", "HEAD^", "HEAD", "--", "backend/app/").split())
print("  6784d57..HEAD -- backend/  =", g("diff", "--name-only", COMMIT, "HEAD", "--", "backend/").split())
print("  6784d57..HEAD -- backend/app/ =", g("diff", "--name-only", COMMIT, "HEAD", "--", "backend/app/").split())
print()
print("=== docstring 行数变化（基线 %s -> HEAD）===" % COMMIT)
for rel in FILES:
    d0, d1 = docs(base(rel)), docs(work(rel))
    print("--- %s" % rel)
    for n in d0:
        if d0[n] != d1.get(n):
            print("   %-52s %d -> %d 行" % (n, len(d0[n].splitlines()), len(d1[n].splitlines())))
    print("   （未变的 %d 个 docstring 略）" % sum(1 for n in d0 if d0[n] == d1.get(n)))
print()
print("=== 注释条数（AST 的盲区）===")
for rel in FILES:
    c0, c1 = comments(base(rel)), comments(work(rel))
    d = list(difflib.unified_diff(c0, c1, lineterm="", n=0))
    print("   %-24s %d -> %d 条（diff 行 %d）" % (pathlib.Path(rel).name, len(c0), len(c1), len(d)))
