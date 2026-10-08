"""Task 6 亲验：重点是 Step 0 第 6 格那条 Critical 顶回是否成立（Ruling 97）。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. models/__init__.py 的 __all__：Plan 02 的表类在不在里面？")
mi = (BACKEND / "app" / "db" / "models" / "__init__.py").read_text(encoding="utf-8")
k = mi.index("__all__")
all_seg = mi[k:mi.index("]", k) + 1]
names = re.findall(r'"([^"]+)"', all_seg)
print(f"  __all__ 共 {len(names)} 个：{names}")
for plan02 in ("Exercise", "PrescriptionTemplate", "Prescription", "WeeklyAdjustment"):
    print(f"  {plan02:22s} 在 __all__ 里? {plan02 in names}")

print()
print("### B. Ruling 97 那条守卫的原文（_MODELS_PUBLIC_BASELINE 的 docstring）")
tm = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
L = tm.split("\n")
for i, l in enumerate(L):
    if "_MODELS_PUBLIC_BASELINE" in l or "unchanged_by_the_split" in l or "stay_out_of_the_models" in l:
        print(f"  :{i+1} {l.rstrip()[:150]}")

print()
print("### C. 那条守卫的 docstring 全文（看它把什么列为「要防的失效」）")
for m in re.finditer(r"def (test_\w*public\w*|test_\w*namespace\w*)\(.*?\):\n(.*?)(?=\ndef |\Z)", tm, re.S):
    print(f"  --- def {m.group(1)} ---")
    print("  " + m.group(2)[:2600].replace("\n", "\n  "))
    print()

print()
print("### D. 表数与两张新表的列")
from app.db import models as M  # noqa: E402
tabs = M.Base.metadata.tables
print(f"  表数 = {len(tabs)}   (基线 16，应为 18)")
for name in ("prescription", "weekly_adjustment", "prescription_template"):
    t = tabs.get(name)
    if t is None:
        print(f"  {name}: 不存在！")
        continue
    cols = [(c.name, type(c.type).__name__, c.nullable, c.default is not None) for c in t.columns]
    print(f"  {name} ({len(cols)} 列)")
    for c in cols:
        print(f"     {c[0]:24s} {c[1]:10s} nullable={c[2]!s:5s} has_default={c[3]}")
    cks = [c for c in t.constraints if type(c).__name__ == "CheckConstraint"]
    uqs = [c for c in t.constraints if type(c).__name__ == "UniqueConstraint"]
    fks = [c for c in t.constraints if type(c).__name__ == "ForeignKeyConstraint"]
    print(f"     CHECK={[c.name for c in cks]}  UNIQUE={[u.name for u in uqs]}  "
          f"FK={[f.name for f in fks]}")

print()
print("### E. triggers.py 的公开面与 import 面")
p = BACKEND / "app" / "domain" / "prescription" / "triggers.py"
src = p.read_text(encoding="utf-8")
tree = ast.parse(src)
imps = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        imps |= {a.name for a in n.names}
    elif isinstance(n, ast.ImportFrom):
        imps.add(("" if n.level == 0 else f"<L{n.level}>") + (n.module or ""))
print(f"  bytes={len(src.encode('utf-8'))} lines={src.count(chr(10))}")
print(f"  imports = {sorted(imps)}")
print(f"  含 'timedelta'? {'timedelta' in src}   含 'import datetime'? {'import datetime' in src}")
for m in re.finditer(r"timedelta|\.days|_DAYS_PER_WEEK", src):
    line = src[:m.start()].count("\n") + 1
    print(f"     :{line} {src.splitlines()[line-1].strip()[:120]}")
    if line > 200:
        break

print()
print("### F. __all__ 与两个基线的实际值")
import app.domain.prescription as PKG  # noqa: E402
OLD43 = """ADDON_TRIGGERS Addon AssembledBlock AssembledSession
AssembledWeek Block BodyCompState EQUIVALENCE_TRIGGERS EquivalenceMapping EquivalenceTable
ExerciseSpec IMPACT_RANK INTENSITY_TYPES ImpactLevel Intensity Layer MatchInput MatchOutcome
MatchStatus OverrideKind OverrideRecord ReviewStatus SafetyInput SafetyOutcome Session
StudentProfile Substitution TARGET_DOMAIN TEMPLATE_LAYERS Template TrainingPackage VOLUME_FACTOR_BANDS
VOLUME_UNITS WeaknessBucket age_from apply_overrides apply_safety assemble hr_zone hrmax
is_reachable match_template summarize_overrides""".split()
print(f"  app.domain.prescription.__all__ = {len(PKG.__all__)}   (基线 43，旧清单 {len(OLD43)} 个)")
print(f"  新增 = {sorted(set(PKG.__all__) - set(OLD43))}")
print(f"  少了 = {sorted(set(OLD43) - set(PKG.__all__))}")
for f, pat in ((BACKEND / "tests" / "test_refdata_prescription.py",
                r"assert len\(_PRESCRIPTION_PUBLIC_BASELINE\) == (\d+)"),
               (BACKEND / "tests" / "db" / "test_models.py",
                r"assert len\(_MODELS_PUBLIC_BASELINE\) == (\d+)"),
               (BACKEND / "tests" / "db" / "test_models.py", r"== 18"),
               (BACKEND / "tests" / "db" / "test_models.py", r"== 16"),
               (BACKEND / "tests" / "db" / "test_models.py", r"sixteen"),
               (BACKEND / "tests" / "db" / "test_models.py", r"eighteen")):
    s = f.read_text(encoding="utf-8")
    print(f"  {f.name}: {pat!r} 命中 {len(re.findall(pat, s))}")

print()
print("### G. 分区守卫")
sg = (BACKEND / "tests" / "seed" / "test_generate.py").read_text(encoding="utf-8")
for name in ("ORGANISATION_TABLES", "DATA_TABLES", "REFERENCE_TABLES"):
    m = re.search(rf"^{name}\s*=\s*\(([^)]*)\)", sg, re.M | re.S)
    if m:
        items = re.findall(r'"([^"]+)"', m.group(1))
        print(f"  {name} = {len(items)} 个 {items}")
m = re.search(r"assert REFERENCE_TABLES == \(([^)]*)\)", sg)
print(f"  字面断言: assert REFERENCE_TABLES == ({m.group(1) if m else '未找到'})")

print()
print("### H. 扫描面")
for sub in ("domain", "pipeline", "db"):
    print(f"  app/{sub:9s} = {len(list((BACKEND/'app'/sub).rglob('*.py')))}")
