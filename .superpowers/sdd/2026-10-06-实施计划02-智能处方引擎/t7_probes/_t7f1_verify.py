"""Task 7 fix round 1 的最终验收探针：全部用运行时口径（硬规矩 #89）。"""
import dataclasses
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


print("### 1. prescription 表（F1-1）")
from app.db import models as M                                  # noqa: E402
from app.db.models.prescription import Prescription, WeeklyAdjustment  # noqa: E402
cols = list(Prescription.__table__.columns)
print(f"  列数 = {len(cols)}   (首轮 15，应 16)")
print(f"  列名 = {[c.name for c in cols]}")
c = Prescription.__table__.c.label_at_generation
print(f"  label_at_generation: type={type(c.type).__name__}({c.type.length}) "
      f"nullable={c.nullable} default={c.default}")
sr = M.StratificationResult.__table__.c.label
print(f"  stratification_result.label: type={type(sr.type).__name__}({sr.type.length}) "
      f"nullable={sr.nullable}")
print(f"  值域单一所有者? Prescription 上有 LABELS 常量? {hasattr(Prescription, 'LABELS')}  (应 False)")
print(f"  StratificationResult.LABELS = {sorted(M.StratificationResult.LABELS)}")
ck = {x.name: str(x.sqltext) for x in Prescription.__table__.constraints
      if type(x).__name__ == "CheckConstraint"}
print(f"  prescription 的 CHECK = {sorted(ck)}")
for k, v in sorted(ck.items()):
    print(f"    {k}: {v}")
print(f"  表数 = {len(M.Base.metadata.tables)}   (应 18)")
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
print(f"  models 公有面 = {len(obs - subs)}   (应 33)")
print(f"  含 Plan02 四表? {sorted((obs - subs) & {'Exercise', 'PrescriptionTemplate', 'Prescription', 'WeeklyAdjustment'})}  (应 [])")

print()
print("### 2. prescription_stage 的公开面与尺寸")
import ast                                                      # noqa: E402
import app.pipeline.prescription_stage as PS                    # noqa: E402
ps = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
print(f"  bytes={len(ps.encode('utf-8'))} lines={ps.count(chr(10))}   (首轮 50675 B / 866 行)")
tree = ast.parse(ps)
pub = [n.name for n in tree.body
       if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")]
print(f"  公开面 = {pub}")
import inspect                                                  # noqa: E402
print(f"  _previous_prescriptions 签名 = {inspect.signature(PS._previous_prescriptions)}")
print(f"  _last_prescription_of 签名 = {inspect.signature(PS._last_prescription_of)}")
print(f"  源码里还有 outerjoin? {'outerjoin' in inspect.getsource(PS._previous_prescriptions)}  (应 False)")

print()
print("### 3. PIPELINE_TABLES 与 _replay_cleanup 顺序")
import re                                                       # noqa: E402
td = (BACKEND / "tests" / "pipeline" / "test_daily.py").read_text(encoding="utf-8")
items = re.findall(r'"([^"]+)"', re.search(r"^PIPELINE_TABLES = \(([^)]*)\)", td, re.M | re.S).group(1))
print(f"  PIPELINE_TABLES = {len(items)} 张")
d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
DL = d.split("\n")
st = next(i for i, l in enumerate(DL) if l.startswith("def _replay_cleanup"))
en = next(i for i in range(st + 1, len(DL)) if DL[i].startswith("def "))
names = re.findall(r"\b(DerivedMetrics|StratificationResult|PercentileSnapshot|WeeklyAdjustment|Prescription)\b",
                   "\n".join(l for l in DL[st:en] if not l.strip().startswith("#")))
seen = []
for n in names:
    if n not in seen:
        seen.append(n)
print(f"  _replay_cleanup 清单顺序（首次出现序）= {tuple(seen)}")

print()
print("### 4. domain 面 / PersonInputs / lookup_p10")
import app.domain.prescription as PKG                           # noqa: E402
from app.domain import percentile as PC                        # noqa: E402
from app.pipeline.run_stratify import PersonInputs, input_snapshot_of  # noqa: E402
print(f"  app.domain.prescription.__all__ = {len(PKG.__all__)}   (应 47)")
print(f"  PersonInputs 字段数 = {len(dataclasses.fields(PersonInputs))}   (应 15)")
print(f"  lookup_p10 = {inspect.signature(PC.lookup_p10)}")
print(f"  lookup_p20 = {inspect.signature(PC.lookup_p20)}")
tot = 0
for s in ("domain", "pipeline", "db"):
    n = len(list((BACKEND / "app" / s).rglob("*.py")))
    tot += n
    print(f"  app/{s:9s} = {n}")
print(f"  扫描面合计 = {tot}   (应 34 = 15 + 8 + 11)")

print()
print("### 5. 禁区指纹 / golden_cases.json / pe.db / data")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "3DE598AF38631209"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:38s} {len(b):7d} B {got} {'OK' if got == want else 'MISMATCH!'}")
gc = BACKEND / "tests" / "fixtures" / "golden_cases.json"
gb = gc.read_bytes()
got = hashlib.sha256(gb).hexdigest()[:16].upper()
print(f"  golden_cases.json {len(gb)} B sha16={got} "
      f"{'OK' if (len(gb), got) == (27346, '8C787701EA70EF90') else 'MISMATCH!'}")
print(f"  pe.db 存在? {(BACKEND / 'pe.db').exists()}   (应 False)")
seed = BACKEND / "data" / "seed"
print(f"  data/seed 存在? {seed.exists()}  文件数 = {len(list(seed.rglob('*'))) if seed.exists() else 0}")
print(f"  git diff fd6a427 -- backend/data -> {git('diff', '--stat', 'fd6a427', '--', 'backend/data')!r}")
print(f"  git diff (未提交) -- backend/data -> {git('diff', '--stat', '--', 'backend/data')!r}")

print()
print("### 6. 改动面（相对 fd6a427）")
print(git("diff", "--stat", "fd6a427"))
print("--- 工作区未提交 ---")
print(git("status", "--porcelain"))
