"""Task 8 亲验：全部运行时口径（硬规矩 #89）。"""
import dataclasses
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. weekly.py 的四个公开对象（运行时口径）")
from app.domain.prescription.weekly import (  # noqa: E402
    WeeklyFactor, WeeklySheet, current_week, weekly_training_sheet,
)
for cls in (WeeklyFactor, WeeklySheet):
    F = dataclasses.fields(cls)
    print(f"  {cls.__name__} ({len(F)} 个字段)")
    for f in F:
        has_d = f.default is not dataclasses.MISSING
        print(f"      .{f.name}: {f.type}  {'= ' + repr(f.default) if has_d else '（无缺省）'}")

print()
print("### 2. current_week 的 6 个边界（控制者独立实算，不照抄报告）")
import datetime as dt  # noqa: E402
g = dt.date(2026, 3, 2)
cases = [(g, 1), (g + dt.timedelta(days=6), 1), (g + dt.timedelta(days=7), 2),
         (g + dt.timedelta(days=27), 4), (g + dt.timedelta(days=28), None),
         (g - dt.timedelta(days=1), None)]
for as_of, want in cases:
    got = current_week(g, as_of, 4)
    print(f"  generated_on={g} as_of={as_of} (Δ={(as_of-g).days:+3d}d) -> {got!r}  期望 {want!r}  "
          f"{'OK' if got == want else '⚠️ 不符'}")

print()
print("### 3. 跨模块一致性：current_week is None ⟺ MICROCYCLE_EXPIRED 在到期日同真")
from app.domain.prescription.triggers import (  # noqa: E402
    TriggerInput, LastPrescription, TriggerReason, evaluate_triggers, _DAYS_PER_WEEK,
)
print(f"  triggers._DAYS_PER_WEEK = {_DAYS_PER_WEEK}")
import app.domain.prescription.weekly as WK  # noqa: E402
src = (BACKEND / "app" / "domain" / "prescription" / "weekly.py").read_text(encoding="utf-8")
n_days = src.count("_DAYS_PER_WEEK")
print(f"  weekly.py 里 '_DAYS_PER_WEEK' 命中 = {n_days}")
print(f"  weekly.py 里是否自己写了字面 '// 7' ? {'// 7' in src}")
lp = LastPrescription(generated_on=g, template_id="RED-END-ABN-01",
                      label_at_generation="red", microcycle_weeks=4, status="active")
for delta in (27, 28):
    as_of = g + dt.timedelta(days=delta)
    cw = current_week(g, as_of, 4)
    tr = evaluate_triggers(TriggerInput(
        as_of=as_of, current_label="red", current_template_id="RED-END-ABN-01",
        last_prescription=lp, latest_assessment_date=None, teacher_requested=False))
    expired = TriggerReason.MICROCYCLE_EXPIRED in tr
    print(f"  Δ={delta}d: current_week={cw!r}  MICROCYCLE_EXPIRED={expired}  "
          f"-> (cw is None) == expired ? {(cw is None) == expired}")

print()
print("### 4. 公开面 / 扫描面 / 表数")
import app.domain.prescription as PKG  # noqa: E402
print(f"  __all__ = {len(PKG.__all__)}   (基线 47，应 51)")
new = sorted(set(PKG.__all__) - {"WeeklyFactor", "WeeklySheet", "current_week", "weekly_training_sheet"})
print(f"  去掉四个新名后剩 {len(new)} 个 -> 与 47 相符? {len(new) == 47}")
for s in ("domain", "pipeline", "db"):
    print(f"  app/{s:9s} = {len(list((BACKEND/'app'/s).rglob('*.py')))}")
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("domain", "pipeline", "db"))
print(f"  合计 = {tot}  (基线 34，应 35)")
from app.db import models as M  # noqa: E402
print(f"  表数 = {len(M.Base.metadata.tables)}   (应 18)")
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
print(f"  models 公有面 = {len(obs - subs)} 个   (应 33，Ruling 97)")

print()
print("### 5. 两个基线清单的实测值")
import re  # noqa: E402
rf = (BACKEND / "tests" / "test_refdata_prescription.py").read_text(encoding="utf-8")
for m in re.finditer(r"assert len\(([^)]*)\) == (\d+)", rf):
    print(f"  test_refdata_prescription.py: assert len({m.group(1)}) == {m.group(2)}")
m = re.search(r"_OWNED_MODULES\s*=\s*frozenset\(\{([^}]*)\}\)", rf, re.S)
if m:
    print(f"  _OWNED_MODULES = {sorted(re.findall(chr(34) + '([^' + chr(34) + ']*)' + chr(34), m.group(1)))}")

print()
print("### 6. domain 纯净性：weekly.py 的 import 面")
import ast  # noqa: E402
imps = set()
for n in ast.walk(ast.parse(src)):
    if isinstance(n, ast.Import):
        imps |= {a.name for a in n.names}
    elif isinstance(n, ast.ImportFrom):
        imps.add(("" if n.level == 0 else f"<L{n.level}>") + (n.module or ""))
print(f"  weekly.py {len(src.encode('utf-8'))} B / {src.count(chr(10))} 行")
print(f"  imports = {sorted(imps)}")
BAD = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random",
       "math", "types", "json", "os", "sys", "pathlib", "datetime"}
print(f"  违规 = {sorted(imps & BAD) or '无'}")

print()
print("### 7. 禁区指纹 + golden_cases.json")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "3DE598AF38631209"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:40s} {len(b):7d} B {got} {'OK' if got == want else 'MISMATCH!'}")
gc = BACKEND / "tests" / "fixtures" / "golden_cases.json"
print(f"  golden_cases.json {gc.stat().st_size} B sha16={hashlib.sha256(gc.read_bytes()).hexdigest()[:16].upper()}")
print(f"  pe.db 存在? {(BACKEND/'pe.db').exists()}")
