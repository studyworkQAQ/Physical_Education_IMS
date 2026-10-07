# -*- coding: utf-8 -*-
"""pe_fr2_rule32.py — 硬规矩 #32 闸门（带对照组）。

把两侧所有 docstring 就地换成 ast.Pass()，再比 ast.dump(include_attributes=False)；
注释本来就不进 AST。基线用 `git show 6a2938f:<path>` 取（不落盘、不 checkout，避开硬规矩 #46）。
两侧一律 CRLF→LF 归一化后再解析。
"""
import ast
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMIT = "6a2938f"
FILES = [
    "backend/app/pipeline/daily.py",
    "backend/tests/db/test_models.py",
    "backend/tests/architecture/test_domain_purity.py",
    "backend/tests/architecture/test_layering.py",
]
#: 期望「剥掉 docstring 后 AST 仍相同」的文件（本轮只许动散文的那两个）
MUST_BE_TRUE = {"backend/app/pipeline/daily.py", "backend/tests/db/test_models.py"}


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = [ast.Pass()] + body[1:]
    return tree


def parse(src):
    return ast.parse(src.replace("\r\n", "\n"))


def dump(src, strip=True):
    tree = parse(src)
    return ast.dump(strip_docstrings(tree) if strip else tree, include_attributes=False)


def base(rel):
    out = subprocess.run(["git", "show", "%s:%s" % (COMMIT, rel)], cwd=str(REPO),
                         capture_output=True)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    return out.stdout.decode("utf-8")


def work(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def mutate(src, old, new):
    assert src.count(old) == 1, "变异锚点命中 %d 次: %r" % (src.count(old), old[:60])
    return src.replace(old, new)


print("=== ① 本轮 4 个文件：工作树 vs 基线 %s ===" % COMMIT)
ok = True
for rel in FILES:
    b, w = base(rel), work(rel)
    raw_same = dump(b, strip=False) == dump(w, strip=False)
    stripped_same = dump(b) == dump(w)
    want = rel in MUST_BE_TRUE
    verdict = "OK" if stripped_same == want else "!! FAIL"
    if stripped_same != want:
        ok = False
    print("  %s %-52s 不剥docstring相等=%-5s 剥掉后相等=%-5s（本轮期望 %s）"
          % (verdict, rel, raw_same, stripped_same, want))

print()
print("=== ② 对照组 A：往**基线**注入 3 个真语义变异，尺子必须判『不相等』（抓到） ===")
MUTS = [
    ("backend/app/pipeline/daily.py",
     "min(existing.test_date, test_date)", "max(existing.test_date, test_date)",
     "把 test_date 的 min 折叠改成 max（:251）"),
    ("backend/tests/db/test_models.py",
     'assert "SCAN" not in plan', 'assert "SCAN" in plan',
     "把查询计划断言的 not in 改成 in（:709）"),
    ("backend/tests/architecture/test_domain_purity.py",
     "assert len(scanned) >= 5, (", "assert len(scanned) >= 4, (",
     "把空转守卫的下界 5 改成 4（:87）"),
]
for rel, old, new, note in MUTS:
    b = base(rel)
    caught = dump(b) != dump(mutate(b, old, new))
    print("  %s %-52s %s" % ("抓到" if caught else "!! 漏掉", rel, note))
    ok = ok and caught

print()
print("=== ③ 对照组 B：往**基线**只注入 docstring 改动，尺子必须判『相等』（证明它真的剥了 docstring） ===")
DOC_MUTS = [
    ("backend/app/pipeline/daily.py",
     "组内极差 0.38 s", "组内极差 0.37 s", "散文里的一个数字"),
    ("backend/tests/db/test_models.py",
     "单次墙钟中位 (ms)", "单次墙钟中位 (ms，单次采样)", "表头标签"),
]
for rel, old, new, note in DOC_MUTS:
    b = base(rel)
    same = dump(b) == dump(mutate(b, old, new))
    print("  %s %-52s 只改 docstring（%s）→ 剥掉后相等=%s"
          % ("判相等" if same else "!! 判不等", rel, note, same))
    ok = ok and same

print()
print("=== ④ 对照组 C：基线跟自己比，尺子必须判『相等』（证明它不是恒 False） ===")
for rel in FILES:
    b = base(rel)
    same = dump(b) == dump(b)
    print("  self-equal(%-52s) = %s" % (rel, same))
    ok = ok and same

print()
print("闸门结论:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
