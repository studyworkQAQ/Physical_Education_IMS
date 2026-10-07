# -*- coding: utf-8 -*-
"""Probe P13: 用 AST 从 test_models.py 的 docstring 里把复现脚本原样抽出来跑（不采信实现者的表）。
核 test_models.py:596-598 的 .db 字节与两条 EXPLAIN QUERY PLAN，并给一个独立墙钟样本。"""
import ast, pathlib, subprocess, sys, tempfile, textwrap

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
SRC = ROOT / "backend/tests/db/test_models.py"
tree = ast.parse(SRC.read_text(encoding="utf-8"))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
          and n.name == "test_single_person_queries_are_index_served")
doc = ast.get_docstring(fn, clean=False)
lines = doc.splitlines()
start = next(i for i, l in enumerate(lines) if l.strip().startswith("import datetime as dt"))
block = []
for l in lines[start:]:
    if l.strip() == "":
        block.append("")
        continue
    if not l.startswith("        "):
        break
    block.append(l[8:])
script = "\n".join(block).rstrip() + "\n"
print("抽出脚本 %d 行，前 3 行：" % len(block))
for l in block[:3]:
    print("   |", l)
print("   ...最后 2 行:")
for l in [x for x in block if x.strip()][-2:]:
    print("   |", l)

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_idx_probe_"))
p = TMP / "repro.py"
p.write_text(script, encoding="utf-8")

for k in (1, 2):
    print("\n--- 第 %d 次跑（cwd=仓库根，脚本落在 %s）---" % (k, TMP))
    r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True,
                       encoding="utf-8", cwd=str(ROOT))
    print("  exit =", r.returncode)
    print(textwrap.indent(r.stdout.strip(), "  ") or "  <no stdout>")
    if r.returncode != 0:
        print(textwrap.indent(r.stderr.strip()[-2000:], "  "))
import shutil
shutil.rmtree(TMP, ignore_errors=True)
print("\n临时目录已删除:", TMP.exists())
print("禁区：backend/pe.db 存在 =", (ROOT / "backend/pe.db").exists(),
      "; backend/data/seed 文件数 =", len(list((ROOT / "backend/data/seed").glob("*"))))
