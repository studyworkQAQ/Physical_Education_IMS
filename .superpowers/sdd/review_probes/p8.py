# -*- coding: utf-8 -*-
"""Probe P8 (Section D): 零生产语义改动。剥 docstring 后 ast.dump 比基线 ad1d190。
硬规矩 #53：对照组变异必须在 AST 上确认它真的改了代码。"""
import ast, pathlib, subprocess, sys, copy

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")

FILES = [
    "backend/app/config.py",
    "backend/app/pipeline/daily.py",
    "backend/tests/db/test_models.py",
    "backend/tests/pipeline/test_daily.py",
    "backend/tests/architecture/test_domain_purity.py",
    "backend/tests/architecture/test_layering.py",
    "backend/tests/test_config.py",
]


def strip_docstrings(tree):
    tree = copy.deepcopy(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def dump(src):
    return ast.dump(strip_docstrings(ast.parse(src)), annotate_fields=True, include_attributes=False)


def worktree(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def baseline(rel, rev="ad1d190"):
    r = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (rev, rel)],
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8")


print("=== 剥 docstring 后 ast.dump 与基线 ad1d190 比 ===")
for rel in FILES:
    wt = worktree(rel)
    bl = baseline(rel)
    if bl is None:
        print("  %-46s 基线不存在（新文件）" % rel)
        continue
    same = dump(wt) == dump(bl)
    print("  %-46s %s" % (rel, "SAME" if same else "DIFF"))

print("\n=== 尺子有效性：3 个真语义变异，每个都在 AST 上确认真的改了代码（硬规矩 #53）===")
MUTS = [
    # (文件, 用 AST 改一个常量/运算符, 描述)
    ("backend/app/pipeline/daily.py", "num", "把某个 int 常量 +1（AST 层面改 Constant）"),
    ("backend/app/config.py", "str", "把 'seed' 段改成 'wrong'（AST 层面改 Constant）"),
    ("backend/tests/db/test_models.py", "num", "把某个 int 常量 +1"),
]


def mutate_num(src):
    tree = ast.parse(src)
    hit = [0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            node.value = node.value + 1
            hit[0] += 1
            break
    assert hit[0] == 1, "变异没匹配上任何 int 常量"
    return ast.unparse(tree)


def mutate_str(src, target="seed"):
    tree = ast.parse(src)
    hit = [0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == target:
            node.value = "wrong"
            hit[0] += 1
            break
    assert hit[0] == 1, "变异没匹配上目标字符串 %r" % target
    return ast.unparse(tree)


for rel, kind, desc in MUTS:
    src = worktree(rel)
    mut = mutate_num(src) if kind == "num" else mutate_str(src)
    d0, d1 = dump(src), dump(mut)
    caught = d0 != d1
    print("  %-46s %-40s AST 上真的改了 -> %s（尺子%s）" % (
        rel, desc[:40], caught, "有效" if caught else "!! 无效 !!"))
    # 自比对照：不变异时必须判 SAME
    print("      自比对照（同一份源码两次 dump 相等）->", dump(src) == d0)

print("\n=== 附：CRLF / 字节口径 ===")
for rel in FILES:
    b = (ROOT / rel).read_bytes()
    print("  %-46s %7d B  CRLF=%4d  bare LF=%3d  U+FFFD=%d" % (
        rel, len(b), b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"),
        b.decode("utf-8", "replace").count("\ufffd")))
