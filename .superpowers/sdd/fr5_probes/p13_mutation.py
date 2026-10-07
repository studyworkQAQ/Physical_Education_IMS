# -*- coding: utf-8 -*-
"""fix round 5 变异验收：证明矩阵新加的那一格是**活的、且是承重的**。

相位：
  M0 不变异（对照）                                  -> 2 passed
  M1 语义等价改写（对照，证明尺子不恒红）            -> 2 passed
  M2 真变异 A：只改 test_domain_purity.py            -> purity 红、layering 绿
  M3 真变异 A：只改 test_layering.py                 -> layering 红、purity 绿
  M4 真变异 A：两份都改                              -> 2 failed
  M5 定向变异（只折错「level 2 + 包深 3 + module 与 name 都非空」这一形状）：两份都改 -> 2 failed
  M6 = M5，但把**新加的那一格删掉**                   -> 2 passed（证明只有新格能抓住 M5）

每次变异都在**剥 docstring 后的 ast.dump** 上确认真的改了代码；结束按字节还原并核 sha256。
"""
import ast
import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BACKEND = ROOT / "backend"
PUR = BACKEND / "tests/architecture/test_domain_purity.py"
LAY = BACKEND / "tests/architecture/test_layering.py"
TARGET = ("tests/architecture/test_domain_purity.py::test_absolute_folding_matches_resolve_name "
          "tests/architecture/test_layering.py::test_absolute_folding_matches_resolve_name")

ORIG = {p: p.read_bytes() for p in (PUR, LAY)}
SHA = {p: hashlib.sha256(b).hexdigest() for p, b in ORIG.items()}
print("起始 sha256[:16]:", {p.name: SHA[p][:16] for p in SHA})

ANCHOR_OLD = "    anchor = package[: len(package) - (level - 1)]\n"
M1_NEW = "    anchor = tuple(list(package)[: len(package) - (level - 1)])\n"
M2_NEW = "    anchor = package[: len(package) - level]\n"
# 定向变异：只折错「level == 2 且包深 3 且 module 与 name 都非空」这一形状（= 新加的那一格）
M5_OLD_TAIL = "    tail = module or name\n"
M5_NEW_TAIL = ("    if level == 2 and len(package) == 3 and module and name:\n"
               "        return \".\".join(package[:1] + (module,))\n"
               "    tail = module or name\n")
CELL_LINE = '        ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN"),\n'


def dump_no_docs(src_bytes):
    tree = ast.parse(src_bytes.decode("utf-8").replace("\r\n", "\n"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = [ast.Pass()] + b[1:]
    return ast.dump(tree)


def write(path, text):
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


def mutate(path, pairs):
    t = ORIG[path].decode("utf-8").replace("\r\n", "\n")
    for old, new in pairs:
        assert t.count(old) == 1, (path.name, old[:50], t.count(old))
        t = t.replace(old, new, 1)
    write(path, t)
    changed = dump_no_docs(ORIG[path]) != dump_no_docs(path.read_bytes())
    return changed


def restore():
    for p, b in ORIG.items():
        p.write_bytes(b)


def run(tag):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"] + TARGET.split(),
                       cwd=str(BACKEND), capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    last = [l for l in out.strip().splitlines() if l.strip()][-1]
    print("  [%s] rc=%d  末行=%s" % (tag, r.returncode, last.strip()[:120]))
    return r.returncode, out, last


results = []
try:
    print("\n=== M0 不变异（对照）===")
    rc, out, last = run("M0")
    results.append(("M0 不变异", last, rc == 0))

    print("\n=== M1 语义等价改写（对照：证明尺子不恒红）===")
    ch = {p: mutate(p, [(ANCHOR_OLD, M1_NEW)]) for p in (PUR, LAY)}
    print("  剥 docstring 后 ast.dump 真的变了吗（预期两份都 True，因为写法变了）:", ch)
    rc, out, last = run("M1")
    results.append(("M1 语义等价改写", last, rc == 0))
    restore()

    print("\n=== M2 真变异 A：只改 test_domain_purity.py（预期 purity 红、layering 绿）===")
    ch = mutate(PUR, [(ANCHOR_OLD, M2_NEW)])
    print("  purity 剥 docstring 后 ast.dump 变了吗:", ch)
    print("  layering 未动，sha256 相同吗:", hashlib.sha256(LAY.read_bytes()).hexdigest() == SHA[LAY])
    rc, out, last = run("M2")
    for l in out.splitlines():
        if "indicators" in l or "PASSED" in l or "FAILED" in l:
            print("      %s" % l.strip()[:200])
    results.append(("M2 只改 purity", last, rc != 0))
    restore()

    print("\n=== M3 真变异 A：只改 test_layering.py（预期 layering 红、purity 绿）===")
    ch = mutate(LAY, [(ANCHOR_OLD, M2_NEW)])
    print("  layering 剥 docstring 后 ast.dump 变了吗:", ch)
    print("  purity 未动，sha256 相同吗:", hashlib.sha256(PUR.read_bytes()).hexdigest() == SHA[PUR])
    rc, out, last = run("M3")
    for l in out.splitlines():
        if "indicators" in l or "FAILED" in l:
            print("      %s" % l.strip()[:200])
    results.append(("M3 只改 layering", last, rc != 0))
    restore()

    print("\n=== M4 真变异 A：两份都改（预期 2 failed）===")
    for p in (PUR, LAY):
        mutate(p, [(ANCHOR_OLD, M2_NEW)])
    rc, out, last = run("M4")
    results.append(("M4 两份都改", last, rc != 0))
    restore()

    print("\n=== M5 定向变异（只折错新格那一形状）：两份都改（预期 2 failed）===")
    ch = {p.name: mutate(p, [(M5_OLD_TAIL, M5_NEW_TAIL)]) for p in (PUR, LAY)}
    print("  剥 docstring 后 ast.dump 变了吗:", ch)
    rc, out, last = run("M5")
    for l in out.splitlines():
        if "indicators" in l:
            print("      %s" % l.strip()[:200])
    results.append(("M5 定向变异（新格在）", last, rc != 0))
    restore()

    print("\n=== M6 = M5，但把新加的那一格删掉（预期 2 passed -> 只有新格能抓住 M5）===")
    for p in (PUR, LAY):
        t = ORIG[p].decode("utf-8").replace("\r\n", "\n")
        assert t.count(CELL_LINE) == 1
        t = t.replace(M5_OLD_TAIL, M5_NEW_TAIL, 1).replace(CELL_LINE, "", 1)
        write(p, t)
        assert dump_no_docs(ORIG[p]) != dump_no_docs(p.read_bytes())
    rc, out, last = run("M6")
    results.append(("M6 定向变异（新格删掉）", last, rc == 0))
    restore()
finally:
    restore()

print("\n=== 还原核对 ===")
for p in (PUR, LAY):
    same = hashlib.sha256(p.read_bytes()).hexdigest() == SHA[p]
    print("  %-24s sha256 还原=%s  %s" % (p.name, same, SHA[p][:16]))
    assert same, p
print("\n=== 汇总 ===")
for name, last, ok in results:
    print("  %-26s %-34s 判读=%s" % (name, last.strip()[:34], "符合预期" if ok else "<<< 不符合"))
print("\nrc(git status):")
print(subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True)
      .stdout.decode("utf-8", "replace") or "  (空)")
