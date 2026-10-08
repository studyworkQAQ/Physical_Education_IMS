"""Task 7 亲验：全部用运行时口径（硬规矩 #89，绝不用正则数源码）。"""
import dataclasses
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. PersonInputs 的字段（运行时口径）")
from app.pipeline.run_stratify import PersonInputs, input_snapshot_of, resolve_muscle_lines  # noqa: E402
F = dataclasses.fields(PersonInputs)
print(f"  len(fields) = {len(F)}   (基线 12，应 15)")
print(f"  字段名 = {[f.name for f in F]}")
for want in ("height_cm", "weight_kg", "snapshot_muscle_p10"):
    hit = [f for f in F if f.name == want]
    print(f"  {want:22s} 在? {bool(hit)}  缺省={hit[0].default if hit else '-'}")

print()
print("### 2. lookup_p10 存在且与 lookup_p20 同口径")
from app.domain import percentile as PC  # noqa: E402
print(f"  hasattr lookup_p10 = {hasattr(PC, 'lookup_p10')}   lookup_p20 = {hasattr(PC, 'lookup_p20')}")
import inspect  # noqa: E402
print(f"  lookup_p10 签名 = {inspect.signature(PC.lookup_p10)}")
print(f"  lookup_p20 签名 = {inspect.signature(PC.lookup_p20)}")
print(f"  lookup_p10 在 percentile.__all__ 里? {'lookup_p10' in getattr(PC, '__all__', [])}")
print(f"  lookup_p20 在 percentile.__all__ 里? {'lookup_p20' in getattr(PC, '__all__', [])}")
print(f"  lookup_p25 在 percentile.__all__ 里? {'lookup_p25' in getattr(PC, '__all__', [])}")
print(f"  percentile.__all__ = {getattr(PC, '__all__', '（无 __all__）')}")

print()
print("### 3. PIPELINE_TABLES 与 _replay_cleanup 的顺序")
import re  # noqa: E402
td = (BACKEND / "tests" / "pipeline" / "test_daily.py").read_text(encoding="utf-8")
m = re.search(r"^PIPELINE_TABLES = \(([^)]*)\)", td, re.M | re.S)
items = re.findall(r'"([^"]+)"', m.group(1))
print(f"  PIPELINE_TABLES = {len(items)} 张 {items}")
d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
DL = d.split("\n")
st = next(i for i, l in enumerate(DL) if l.startswith("def _replay_cleanup"))
en = next(i for i in range(st + 1, len(DL)) if DL[i].startswith("def "))
print(f"  _replay_cleanup 在 :{st+1}-:{en}，其中的代码行（非注释/非 docstring）：")
inq = False
for i in range(st, en):
    s = DL[i].strip()
    if s.count('"""') % 2 == 1:
        inq = not inq
        continue
    if inq or not s or s.startswith("#"):
        continue
    print(f"    :{i+1} {DL[i].rstrip()[:130]}")

print()
print("### 4. prescription 表有没有 label_at_generation（实现者报的最高优先级关切）")
from app.db import models as M  # noqa: E402
from app.db.models.prescription import Prescription, WeeklyAdjustment  # noqa: E402
print(f"  prescription 列 = {[c.name for c in Prescription.__table__.columns]}")
print(f"  >>> 有 label_at_generation? {'label_at_generation' in [c.name for c in Prescription.__table__.columns]}")
print(f"  weekly_adjustment 列 = {[c.name for c in WeeklyAdjustment.__table__.columns]}")
print(f"  表数 = {len(M.Base.metadata.tables)}")
print(f"  models 公有面上有 Prescription? {hasattr(M, 'Prescription')}  (Ruling 97：应为 False)")

print()
print("### 5. models 公有面仍是 33（Ruling 97）")
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
print(f"  observed - submodules = {len(obs - subs)} 个   (基线 33)")
print(f"  含 Exercise/PrescriptionTemplate/Prescription/WeeklyAdjustment? "
      f"{sorted((obs - subs) & {'Exercise','PrescriptionTemplate','Prescription','WeeklyAdjustment'})}")

print()
print("### 6. 公开面与扫描面")
import app.domain.prescription as PKG  # noqa: E402
print(f"  __all__ = {len(PKG.__all__)}   (基线 47)")
for s in ("domain", "pipeline", "db"):
    print(f"  app/{s:9s} = {len(list((BACKEND/'app'/s).rglob('*.py')))}")
print(f"  合计 = {sum(len(list((BACKEND/'app'/s).rglob('*.py'))) for s in ('domain','pipeline','db'))}  (基线 33，应 34)")

print()
print("### 7. 禁区指纹 + golden_cases.json 未改")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "3DE598AF38631209"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:40s} {len(b):7d} B {got} {'OK' if got == want else 'MISMATCH!'}")
gc = BACKEND / "tests" / "fixtures" / "golden_cases.json"
print(f"  golden_cases.json {gc.stat().st_size} B  sha16={hashlib.sha256(gc.read_bytes()).hexdigest()[:16].upper()}")
print(f"  pe.db 存在? {(BACKEND/'pe.db').exists()}")

print()
print("### 8. domain 纯净性：percentile.py 的 import 面（加了 lookup_p10 之后）")
import ast  # noqa: E402
src = (BACKEND / "app" / "domain" / "percentile.py").read_text(encoding="utf-8")
imps = set()
for n in ast.walk(ast.parse(src)):
    if isinstance(n, ast.Import):
        imps |= {a.name for a in n.names}
    elif isinstance(n, ast.ImportFrom):
        imps.add(("" if n.level == 0 else f"<L{n.level}>") + (n.module or ""))
print(f"  imports = {sorted(imps)}")
BAD = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random",
       "math", "types", "json", "os", "sys", "pathlib", "datetime"}
print(f"  违规 = {sorted(imps & BAD) or '无'}")

print()
print("### 9. prescription_stage.py 的公开面")
ps = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
tree = ast.parse(ps)
print(f"  bytes={len(ps.encode('utf-8'))} lines={ps.count(chr(10))}")
for n in tree.body:
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
        print(f"  {type(n).__name__:9s} {n.name}")
