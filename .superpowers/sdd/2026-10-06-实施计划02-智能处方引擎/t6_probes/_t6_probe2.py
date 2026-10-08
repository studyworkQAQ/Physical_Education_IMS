"""Task 6 预检 probe 2：分区守卫的行数断言口径（P6-A6 是本 Task 最容易踩的坑）。"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

sg = (BACKEND / "tests" / "seed" / "test_generate.py").read_text(encoding="utf-8")
L = sg.split("\n")
print(f"### test_generate.py  {len(sg.encode('utf-8'))} B / {len(L)} 行")

print("\n### A. 分区穷尽守卫那一段（:520-:560）")
for i in range(519, min(560, len(L))):
    print(f"  :{i+1} {L[i].rstrip()[:150]}")

print("\n### B. 所有用到 DATA_TABLES / REFERENCE_TABLES / ORGANISATION_TABLES 的地方")
for i, l in enumerate(L):
    if re.search(r"DATA_TABLES|REFERENCE_TABLES|ORGANISATION_TABLES", l):
        print(f"  :{i+1} {l.strip()[:150]}")

print("\n### C. :580-:625（那两个 func.count 断言的口径）")
for i in range(579, min(625, len(L))):
    print(f"  :{i+1} {L[i].rstrip()[:150]}")

print("\n### D. _MODELS_PUBLIC_BASELINE 的内容与 _MODELS_SUBMODULES")
tm = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
i = tm.index("_MODELS_PUBLIC_BASELINE")
seg = tm[i:tm.index("]", tm.index("= (", i)) + 1] if "= (" in tm[i:i + 60] else tm[i:i + 2000]
print("  " + seg.replace("\n", "\n  ")[:1800])
j = tm.index("_MODELS_SUBMODULES")
print("\n  " + tm[j:tm.index("}", j) + 1].replace("\n", "\n  ")[:500])

print("\n### E. models/__init__.py 的 __all__（加两张表要同步）")
mi = (BACKEND / "app" / "db" / "models" / "__init__.py").read_text(encoding="utf-8")
k = mi.index("__all__")
print("  " + mi[k:mi.index("]", k) + 1].replace("\n", "\n  ")[:1500])

print("\n### F. models/feedback.py 的全文（只有 475 B，看它是空壳还是已有内容）")
print((BACKEND / "app" / "db" / "models" / "feedback.py").read_text(encoding="utf-8"))
