"""复核两处不符：用正确的工具（硬规矩 #107：探针的谓词要先对已知反例验证）。"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"

print("### 1. routers/__init__.py 的 include_router 顺序（不是 import 顺序！）")
ri = (BACKEND / "app" / "api" / "routers" / "__init__.py").read_text(encoding="utf-8")
print(f"  文件 {len(ri.encode('utf-8'))} B / {ri.count(chr(10))} 行")
print("\n  --- 全部 include_router 调用（按出现序）---")
for i, l in enumerate(ri.split("\n")):
    if "include_router" in l:
        print(f"  :{i+1} {l.strip()[:120]}")
print("\n  --- 我上一版探针错在哪：ri.find() 找的是**子串首次出现**，"
      "而 import 行 `from … import catalog, feedback` 里 catalog 按字母序在前 ---")
for i, l in enumerate(ri.split("\n")):
    if re.search(r"^\s*(from|import)\b.*\b(catalog|feedback|prescription)\b", l):
        print(f"  :{i+1} {l.strip()[:120]}")
print("\n  --- 「顺序今天不承重」那句的上下文（看它是不是已被改写/是否在讲别的事）---")
for m in re.finditer("顺序", ri):
    s = max(0, m.start() - 260)
    print(f"  @{m.start()}: …{ri[s:m.start()+300]}…")
    print("  " + "-" * 70)

print("\n### 2. test_backfill.py 里 under_60_seconds 与 under_90_seconds 各出现在哪")
tb = (BACKEND / "tests" / "pipeline" / "test_backfill.py").read_text(encoding="utf-8")
for pat in ("under_60_seconds", "under_90_seconds", "elapsed < 60", "elapsed < 90"):
    hits = [i + 1 for i, l in enumerate(tb.split("\n")) if pat in l]
    print(f"  {pat!r:22s} 命中行 = {hits or '无'}")
print("\n  --- 含 under_60_seconds 的那些行原文 ---")
for i, l in enumerate(tb.split("\n")):
    if "under_60_seconds" in l:
        print(f"  :{i+1} {l.strip()[:150]}")
print("\n  --- def 行（函数名到底叫什么）---")
for i, l in enumerate(tb.split("\n")):
    if l.startswith("def ") or l.lstrip().startswith("def test_backfill"):
        print(f"  :{i+1} {l.strip()[:120]}")

print("\n### 3. 全仓 AST 复核旧函数名（实现者说它跑过、命中 0）")
import ast  # noqa: E402
hits = []
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts or "t5_probes" in p.parts or "t4_probes" in p.parts \
            or "t3_probes" in p.parts or "t2_probes" in p.parts or "t1_probes" in p.parts:
        continue
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError as e:
        print(f"  ⚠️ 语法错误 {p.relative_to(BACKEND)}: {e}")
        continue
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and "under_60" in n.name:
            hits.append((p.relative_to(BACKEND).as_posix(), n.lineno, n.name))
        if isinstance(n, ast.Attribute) and "under_60" in n.attr:
            hits.append((p.relative_to(BACKEND).as_posix(), n.lineno, n.attr))
        if isinstance(n, ast.Name) and "under_60" in n.id:
            hits.append((p.relative_to(BACKEND).as_posix(), n.lineno, n.id))
print(f"  AST 里 under_60 的定义/引用命中 = {hits or '无 ✅'}")
