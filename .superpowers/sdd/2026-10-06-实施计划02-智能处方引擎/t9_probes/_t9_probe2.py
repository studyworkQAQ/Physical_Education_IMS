"""Task 9 预检 probe 2：spec §14 的真实项数（P9-A2 是承重的一条，必须钉死）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[4]
spec = ROOT / "Document" / "2026-09-28-体育闭环原型-设计spec.md"
b = spec.read_bytes()
t = b.decode("utf-8")
L = t.split("\n")
print(f"spec {len(b)} B / {len(L)} 行（按 \\n 切）")

print("\n### A. 所有 '## ' 章节标题（看 §14 之后还有什么）")
for i, l in enumerate(L):
    if l.startswith("## "):
        print(f"  :{i+1} {l.strip()[:100]}")

print("\n### B. §14 那一节的全部行（从标题到下一个 ## ）")
s = next(i for i, l in enumerate(L) if l.startswith("## 14"))
e = next((i for i in range(s + 1, len(L)) if L[i].startswith("## ")), len(L))
print(f"  §14 在 :{s+1}-:{e}，共 {e - s} 行")
for i in range(s, e):
    print(f"  :{i+1} {L[i].rstrip()[:190]}")

print("\n### C. 全 spec 里 '§14' / '第 N 项' 这类交叉引用（Task 2/3 声称追加过）")
for m in re.finditer(r"§\s*14|§14|待确认事项", t):
    ln = t[:m.start()].count("\n") + 1
    print(f"  :{ln} {L[ln-1].strip()[:150]}")

print("\n### D. YAML 注释里有没有「见 spec §14 第 N 项」这类指向（可能指向不存在的条目）")
for rel in ("backend/data/exercises.yaml", "backend/data/exercise_equivalence.yaml"):
    p = ROOT / rel
    s2 = p.read_text(encoding="utf-8")
    hits = [(s2[:m.start()].count("\n") + 1, s2.split("\n")[s2[:m.start()].count("\n")].strip()[:150])
            for m in re.finditer(r"§\s*14|§14", s2)]
    print(f"  {rel}: {len(hits)} 处")
    for ln, txt in hits:
        print(f"     :{ln} {txt}")
import glob
n = 0
for p in sorted((ROOT / "backend" / "data" / "prescription").glob("*.yaml")):
    s3 = p.read_text(encoding="utf-8")
    for m in re.finditer(r"§\s*14|§14", s3):
        ln = s3[:m.start()].count("\n") + 1
        print(f"  {p.name}:{ln} {s3.split(chr(10))[ln-1].strip()[:150]}")
        n += 1
print(f"  18 套模板 YAML 里合计 {n} 处")

print("\n### E. 计划正文里所有 §14 编号的引用（Task 9 要按真实项数重排）")
plan = (ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md").read_text(encoding="utf-8")
nums = sorted({int(m.group(1)) for m in re.finditer(r"§14 #(\d+)|#(\d+)", plan)
               for g in m.groups() if g})
print(f"  计划正文里出现过的 §14 编号 = {nums}")
for pat in ("27 项", "34 项", "27 → 34", "#28", "#29", "#30", "#31", "#32", "#33", "#34", "#35", "#36", "#37"):
    print(f"  {pat!r} 命中 {plan.count(pat)}")
