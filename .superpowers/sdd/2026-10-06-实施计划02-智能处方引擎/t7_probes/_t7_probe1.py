"""Task 7 预检 probe 1：pipeline 层的既有形状 + 计划 Task 7 的每条断言逐个实测。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. app/pipeline 的文件与大小")
for p in sorted((BACKEND / "app" / "pipeline").rglob("*.py")):
    print(f"  {p.relative_to(BACKEND).as_posix():38s} {p.stat().st_size:7d} B")

print()
print("### B. daily.py 的阶段序列与 _replay_cleanup 的清单")
d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
L = d.split("\n")
print(f"  daily.py {len(d.encode('utf-8'))} B / {len(L)} 行")
for i, l in enumerate(L):
    if re.search(r"^def |^    def |_replay_cleanup|delete_by_batch|SAVEPOINT|begin_nested|prescription_count|alert_count", l):
        print(f"  :{i+1} {l.rstrip()[:130]}")

print()
print("### C. run_stratify 的 input_snapshot_of —— Task 7 要给它补两个键")
for p in sorted((BACKEND / "app" / "pipeline").rglob("*.py")):
    s = p.read_text(encoding="utf-8")
    if "input_snapshot_of" in s:
        for m in re.finditer(r"^def input_snapshot_of\(([^)]*)\)", s, re.M):
            print(f"  {p.name}: def input_snapshot_of({m.group(1)[:90]})")
        i = s.index("def input_snapshot_of")
        seg = s[i:i + 3200]
        print("  --- 函数体前 3200 字符 ---")
        print("  " + seg.replace("\n", "\n  "))
        break

print()
print("### D. input_snapshot 今天的顶层键（实测跑一次）")
print("    （计划说 26 个键，且没有 'bmi' 原始值、没有 'snapshot_muscle_p10'）")
