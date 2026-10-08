"""Task 7 预检 probe 3：最高风险点 —— bmi 原始值与 P10 能不能在 input_snapshot_of 里算出来。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

rs = (BACKEND / "app" / "pipeline" / "run_stratify.py").read_text(encoding="utf-8")
tree = ast.parse(rs)

print("### A. run_stratify.py 的 dataclass 字段（Person / Evaluated / …）")
for n in tree.body:
    if isinstance(n, ast.ClassDef):
        decs = [ast.unparse(d) for d in n.decorator_list]
        print(f"  class {n.name}  dec={decs}")
        for s in n.body:
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                v = f" = {ast.unparse(s.value)}" if s.value is not None else ""
                print(f"      .{s.target.id}: {ast.unparse(s.annotation)}{v}"[:140])

print()
print("### B. input_snapshot_of 的全部调用方（改签名会波及谁）")
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    s = p.read_text(encoding="utf-8")
    for i, l in enumerate(s.split("\n")):
        if "input_snapshot_of" in l:
            print(f"  {p.relative_to(BACKEND).as_posix()}:{i+1} {l.strip()[:130]}")

print()
print("### C. percentile.py 有没有 lookup_p10（P10 的既有取法）")
pc = (BACKEND / "app" / "domain" / "percentile.py").read_text(encoding="utf-8")
for m in re.finditer(r"^def (\w+)\(([^)]*)\)", pc, re.M):
    print(f"  def {m.group(1)}({m.group(2).strip()[:90]})")
for i, l in enumerate(pc.split("\n")):
    if re.search(r"p10|p20|PercentileRow", l) and ("def " in l or "p10" in l):
        print(f"  :{i+1} {l.strip()[:130]}")

print()
print("### D. PercentileRow 的字段（p10 在不在值对象上）")
for n in ast.parse(pc).body:
    if isinstance(n, ast.ClassDef):
        print(f"  class {n.name}")
        for s in n.body:
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                print(f"      .{s.target.id}: {ast.unparse(s.annotation)}")

print()
print("### E. PIPELINE_TABLES 的清单（canonical sha256 的覆盖面）")
td = (BACKEND / "tests" / "pipeline" / "test_daily.py").read_text(encoding="utf-8")
m = re.search(r"PIPELINE_TABLES\s*=\s*[\(\[]([^)\]]*)[\)\]]", td, re.S)
if m:
    items = re.findall(r'"([^"]+)"', m.group(1))
    print(f"  PIPELINE_TABLES = {len(items)} 张 {items}")
for i, l in enumerate(td.split("\n")):
    if "PIPELINE_TABLES" in l:
        print(f"  :{i+1} {l.strip()[:140]}")

print()
print("### F. bmi_of 的签名与住址")
ind = (BACKEND / "app" / "domain" / "indicators.py").read_text(encoding="utf-8")
i = ind.index("def bmi_of")
print("  " + ind[i:i + 700].replace("\n", "\n  ")[:700])

print()
print("### G. fitness_test_result 的列（身高体重在不在）")
from app.db import models as M  # noqa: E402
print(f"  {[c.name for c in M.Base.metadata.tables['fitness_test_result'].columns]}")

print()
print("### H. daily.py 里 stratify 阶段怎么拿到 height/weight（若 Person 上没有）")
d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
for i, l in enumerate(d.split("\n")):
    if re.search(r"height|weight|bmi_of", l):
        print(f"  :{i+1} {l.strip()[:130]}")
