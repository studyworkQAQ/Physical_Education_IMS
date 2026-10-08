"""Task 7 预检 probe 2：input_snapshot 的真实键集 + _replay_cleanup 清单 + p10 列 + 幂等断言口径。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. input_snapshot_of 的函数体（run_stratify.py）")
rs = (BACKEND / "app" / "pipeline" / "run_stratify.py").read_text(encoding="utf-8")
L = rs.split("\n")
start = next(i for i, l in enumerate(L) if l.startswith("def input_snapshot_of"))
end = next(i for i in range(start + 1, len(L)) if L[i].startswith("def ") or L[i].startswith("class "))
body = L[start:end]
keys = []
for i, l in enumerate(body):
    m = re.match(r'\s*"([a-z_0-9]+)":', l)
    if m:
        keys.append(m.group(1))
    print(f"  :{start+i+1} {l.rstrip()[:120]}")
print(f"\n  >>> 顶层键实测 {len(keys)} 个：{sorted(keys)}")
print(f"  >>> 含 'bmi'? {'bmi' in keys}   含 'snapshot_muscle_p10'? {'snapshot_muscle_p10' in keys}")
print(f"  >>> 含 'body_fat_pct'? {'body_fat_pct' in keys}   含 'muscle_mass_kg'? {'muscle_mass_kg' in keys}")
print(f"  >>> 含 'curr_scores'? {'curr_scores' in keys}")

print()
print("### B. _replay_cleanup 的模型清单（daily.py）")
d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
DL = d.split("\n")
s = next(i for i, l in enumerate(DL) if l.startswith("def _replay_cleanup"))
e = next(i for i in range(s + 1, len(DL)) if DL[i].startswith("def "))
for i in range(s, e):
    if re.search(r"for model in|models\.|delete_by_batch|\(", DL[i]) and not DL[i].strip().startswith(("#", '"', "``")):
        print(f"  :{i+1} {DL[i].rstrip()[:130]}")

print()
print("### C. percentile_snapshot 的列（p10 在不在）")
from app.db import models as M  # noqa: E402
ps = M.Base.metadata.tables["percentile_snapshot"]
print(f"  列 = {[c.name for c in ps.columns]}")

print()
print("### D. 幂等断言的口径（test_daily.py 的 canonical sha256 那一段）")
td = (BACKEND / "tests" / "pipeline" / "test_daily.py").read_text(encoding="utf-8")
TL = td.split("\n")
for i, l in enumerate(TL):
    if re.search(r"canonical|sha256|assert first == second|882|行数合计|fe0a44e0", l):
        print(f"  :{i+1} {l.rstrip()[:150]}")

print()
print("### E. 全仓有没有那个字面哈希 fe0a44e052c7946b（计划说账本与 spec 都印着它）")
hits = 0
for p in ROOT.rglob("*"):
    if not p.is_file() or ".git" in p.parts:
        continue
    if p.suffix not in (".py", ".md", ".json", ".txt", ".yaml", ".csv"):
        continue
    try:
        if "fe0a44e052c7946b" in p.read_text(encoding="utf-8", errors="ignore"):
            print(f"  命中 {p.relative_to(ROOT).as_posix()}")
            hits += 1
    except OSError:
        pass
print(f"  合计命中 {hits} 个文件")

print()
print("### F. muscle_line_gaps 与 error_summary 的断言（计划说 60 人下恒为 4 / 恒为 NULL）")
for i, l in enumerate(TL):
    if re.search(r"muscle_line_gaps|error_summary", l):
        print(f"  :{i+1} {l.rstrip()[:150]}")

print()
print("### G. run_daily 的阶段调用序列（处方阶段要插在哪）")
for i, l in enumerate(DL):
    if re.search(r"^\s{8,}(extract|clean|percentile|derive|stratif|_stratify|_load_sources|prescri)", l):
        print(f"  :{i+1} {l.rstrip()[:130]}")
