"""Task 9 预检 probe 1（修正版）：golden_cases.json 的真实形状 + spec §14 现状 + 测试结构。"""
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. golden_cases.json 的顶层结构")
gc = BACKEND / "tests" / "fixtures" / "golden_cases.json"
raw = gc.read_bytes()
data = json.loads(raw.decode("utf-8"))
print(f"  {len(raw)} B / sha16={hashlib.sha256(raw).hexdigest()[:16].upper()}")
print(f"  顶层键 = {sorted(data)}   各值类型 = "
      f"{ {k: type(v).__name__ for k, v in data.items()} }")
inp, exp = data["input"], data["expected"]
print(f"  input 类型={type(inp).__name__} 长度={len(inp)}")
print(f"  expected 类型={type(exp).__name__} 长度={len(exp)}")

print()
print("### B. _meta 全文")
print(json.dumps(data["_meta"], ensure_ascii=False, indent=2)[:2500])

print()
print("### C. 第 1 例的 input 与 expected（Task 9 要往这两处加字段）")
k0 = list(inp)[0] if isinstance(inp, dict) else 0
one_in = inp[k0] if isinstance(inp, dict) else inp[0]
one_ex = exp[k0] if isinstance(exp, dict) else exp[0]
print(f"  键/下标 = {k0!r}")
print(f"  input 的字段（{len(one_in)} 个）= {sorted(one_in)}")
print(f"  input 全文：")
print(json.dumps(one_in, ensure_ascii=False, indent=2)[:1800])
print(f"  expected 的字段（{len(one_ex)} 个）= {sorted(one_ex)}")
print(f"  expected 全文：")
print(json.dumps(one_ex, ensure_ascii=False, indent=2)[:1200])

print()
print("### D. 13 例的 id / label / 有没有 height_cm & weight_kg（P7-A2 的连带）")
ids = list(inp) if isinstance(inp, dict) else list(range(len(inp)))
for k in ids:
    i = inp[k] if isinstance(inp, dict) else inp[k]
    e = exp[k] if isinstance(exp, dict) else exp[k]
    print(f"  {str(k):8s} label={e.get('label', '?'):18s} "
          f"height_cm={'有' if 'height_cm' in json.dumps(i) else '无'} "
          f"weight_kg={'有' if 'weight_kg' in json.dumps(i) else '无'} "
          f"input字段数={len(i)} expected字段数={len(e)}")

print()
print("### E. 黄金用例测试的结构")
tg = (BACKEND / "tests" / "integration" / "test_golden_cases.py").read_text(encoding="utf-8")
TL = tg.split("\n")
print(f"  {len(tg.encode('utf-8'))} B / {len(TL)} 行")
for i, l in enumerate(TL):
    if re.match(r"^(def |@pytest|class )", l) or "golden_cases" in l or "parametrize" in l:
        print(f"  :{i+1} {l.strip()[:130]}")

print()
print("### F. spec §14 的现状（Task 9 要补 #30/#32/#33/#34/#35/#36/#37）")
spec = ROOT / "Document" / "2026-09-28-体育闭环原型-设计spec.md"
sb = spec.read_bytes()
st = sb.decode("utf-8")
print(f"  spec {len(sb)} B / CRLF={st.count(chr(13)+chr(10))} / LF={st.count(chr(10))} / "
      f"bom={sb[:3] == bytes([0xEF, 0xBB, 0xBF])}")
m = re.search(r"^## .*14.*$", st, re.M)
print(f"  §14 的标题 = {m.group(0) if m else '（没找到）'}")
if m:
    seg = st[m.start():]
    rows = re.findall(r"^\|\s*(\d+)\s*\|", seg, re.M)
    print(f"  §14 表格里的编号 = {rows}")
    print(f"  最大编号 = {max(int(x) for x in rows) if rows else '（无）'}  共 {len(rows)} 行")
    nxt = re.search(r"^## ", seg[10:], re.M)
    print(f"  §14 之后还有章节? {bool(nxt)}")

print()
print("### G. spec 里 §1.3 的勘误段（要回填两个 canonical sha256）")
for pat in ("fe0a44e052c7946b", "行数合计", "882"):
    hits = [st[:x.start()].count("\n") + 1 for x in re.finditer(re.escape(pat), st)]
    print(f"  {pat!r} 命中行 = {hits}")
    for ln in hits[:3]:
        print(f"     :{ln} {st.splitlines()[ln-1].strip()[:160]}")

print()
print("### H. 计划正文里那 9 条待清扫涉及的原文（Task 9 要改）")
plan = (ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md").read_text(encoding="utf-8")
for pat in ("怎么摊", "八个模块", "九个实质模块", "8 个模块"):
    print(f"  计划正文里 {pat!r} 命中 {plan.count(pat)}")
asm = (BACKEND / "app" / "domain" / "prescription" / "assembler.py").read_text(encoding="utf-8")
for i, l in enumerate(asm.split("\n")):
    if "怎么摊" in l or "Task 8" in l:
        print(f"  assembler.py:{i+1} {l.strip()[:140]}")
