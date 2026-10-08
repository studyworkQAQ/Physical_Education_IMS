"""控制者亲验 Task 5：公开面 / 扫描面 / 指纹 / domain 纯净性 / 两处签名扩参。"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. 公开面")
import app.domain.prescription as PKG  # noqa: E402
print(f"  len(__all__) = {len(PKG.__all__)}   (基线 24)")
new = sorted(set(PKG.__all__) - {
    'ADDON_TRIGGERS', 'Addon', 'Block', 'BodyCompState', 'EQUIVALENCE_TRIGGERS',
    'EquivalenceMapping', 'EquivalenceTable', 'ExerciseSpec', 'IMPACT_RANK',
    'INTENSITY_TYPES', 'ImpactLevel', 'Intensity', 'Layer', 'MatchInput',
    'MatchOutcome', 'MatchStatus', 'ReviewStatus', 'Session', 'TARGET_DOMAIN',
    'TEMPLATE_LAYERS', 'Template', 'WeaknessBucket', 'is_reachable', 'match_template'})
print(f"  新增 {len(new)} 个：{new}")
for n in new:
    obj = getattr(PKG, n)
    print(f"     {n:24s} -> {getattr(obj, '__module__', type(obj).__name__)}")

print()
print("### 2. 扫描面（domain / pipeline / db 的 .py 数）")
for sub in ("domain", "pipeline", "db"):
    n = len(list((BACKEND / "app" / sub).rglob("*.py")))
    print(f"  app/{sub:9s} = {n}")
print(f"  合计 = {sum(len(list((BACKEND/'app'/s).rglob('*.py'))) for s in ('domain','pipeline','db'))}   (基线 28)")

print()
print("### 3. 禁区指纹（必须与 Task 2/3 结案时逐字相同）")
EXPECT = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercises.yaml": "3DE598AF38631209",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
}
for rel, want in EXPECT.items():
    p = BACKEND / rel
    b = p.read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    crlf = b.count(b"\r\n")
    print(f"  {rel:42s} {len(b):7d} B  sha16={got}  {'OK' if got == want else 'MISMATCH!'}  CRLF={crlf}")
print(f"  backend/pe.db 存在? {(BACKEND/'pe.db').exists()}   (必须 False)")
print(f"  backend/data/seed/ 文件数 = "
      f"{len(list((BACKEND/'data'/'seed').rglob('*'))) if (BACKEND/'data'/'seed').exists() else 'DIR-ABSENT'}")
tpl = sorted((BACKEND / "data" / "prescription").glob("*.yaml"))
print(f"  模板 YAML 数 = {len(tpl)}  总字节 = {sum(p.stat().st_size for p in tpl)}  "
      f"CRLF 合计 = {sum(p.read_bytes().count(chr(13).encode()+chr(10).encode()) for p in tpl)}")

print()
print("### 4. 四个新模块的纯净性亲扫（不靠守卫，自己再扫一遍）")
import ast  # noqa: E402
BAD_MOD = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random",
           "math", "os", "sys", "json", "pathlib", "datetime"}
BAD_CALL = {"now", "today", "time"}
for name in ("intensity", "assembler", "safety", "override"):
    p = BACKEND / "app" / "domain" / "prescription" / f"{name}.py"
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imports.add(n.module or "")
    bad = imports & BAD_MOD
    attrs = {f"{ast.unparse(v.value)}.{v.attr}" for v in ast.walk(tree)
             if isinstance(v, ast.Attribute)}
    badattr = {a for a in attrs if a.split(".")[-1] in BAD_CALL}
    print(f"  {name:11s} bytes={len(src.encode('utf-8')):6d} lines={src.count(chr(10)):4d} "
          f"imports={sorted(imports)}")
    print(f"              违规模块={sorted(bad) or '无'}  违规调用={sorted(badattr) or '无'}")

print()
print("### 5. 两处签名扩参（实现者顶回控制者的第 5/6 次）")
for name, fn in (("safety", "apply_safety"), ("override", "apply_overrides"),
                 ("assembler", "assemble")):
    p = BACKEND / "app" / "domain" / "prescription" / f"{name}.py"
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == fn:
            a = n.args
            pos = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
            kw = [x.arg for x in a.kwonlyargs]
            ret = ast.unparse(n.returns) if n.returns else "?"
            print(f"  {name}.{fn}({', '.join(pos)}{', *, ' + ', '.join(kw) if kw else ''}) -> {ret}")

print()
print("### 6. weekly_volume_base 的混合量纲（实现者的异议，控制者复核）")
from app.domain.prescription.assembler import StudentProfile, assemble  # noqa: E402
from app.domain.prescription.templates import Template  # noqa: E402
from app.domain.indicators import Sex  # noqa: E402
from app.refdata_prescription import exercises, templates  # noqa: E402
import datetime as dt  # noqa: E402

tpl = templates()["RED-END-ABN-01"]
lib = exercises()
prof = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20),
                      age=20, endurance_score=50.0, bmi=31.0, body_fat_pct=None,
                      muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
pkg = assemble(prof, tpl, dt.date(2026, 10, 8), exercises=lib)
snap = pkg.assembly_snapshot
print(f"  assembly_snapshot 的键（{len(snap)} 个）= {sorted(snap)}")
print(f"  weekly_volume_base = {snap.get('weekly_volume_base')!r}")
print(f"  volume_factor = {snap.get('volume_factor')!r}  band = {snap.get('volume_factor_band')!r}")
print(f"  hrmax = {snap.get('hrmax')!r}  formula = {snap.get('formula')!r}")
w1 = pkg.weeks[0]
print(f"  第 1 周 delta={w1.delta}  session 数={len(w1.sessions)}")
for s in w1.sessions[:1]:
    for b in s.blocks:
        print(f"     day{s.day} {b.exercise_ref:22s} impact={b.impact_level.value:6s} "
              f"unit={b.volume_unit:11s} spw={b.sessions_per_week} vol={b.weekly_volume} "
              f"hr={b.hr_zone} text={b.intensity_text[:34]!r}")
w4 = pkg.weeks[3]
print(f"  第 4 周 delta={w4.delta}")
for s in w4.sessions[:1]:
    for b in s.blocks:
        print(f"     day{s.day} {b.exercise_ref:22s} vol={b.weekly_volume} {b.volume_unit}")
print(f"  paused = {pkg.paused}  weeks = {len(pkg.weeks)}  template = {pkg.template_id} v{pkg.template_version}")
