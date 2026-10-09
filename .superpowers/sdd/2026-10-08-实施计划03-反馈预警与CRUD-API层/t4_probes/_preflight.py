"""Plan 03 Task 4 预检（一份探针）：处方侧特例端点要吃的 Plan 02 接口 + 前后端对接的 3 个缺口。"""
import dataclasses
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]   # t4_probes -> <plan> -> sdd -> .superpowers -> 仓库根
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), BACKEND
sys.path.insert(0, str(BACKEND))

print("### A. weekly.py 的公开面（Task 4 的 weekly-sheet 端点要吃它）")
from app.domain.prescription import weekly as WK  # noqa: E402
for n in ("current_week", "weekly_training_sheet", "WeeklySheet", "WeeklyFactor"):
    o = getattr(WK, n, None)
    if o is None:
        print(f"  ⚠️ {n} 不存在！")
        continue
    if dataclasses.is_dataclass(o):
        print(f"  {n} 字段 = {[(f.name, str(f.type)) for f in dataclasses.fields(o)]}")
    else:
        print(f"  {n}{inspect.signature(o)}")

print()
print("### B. prescription_stage 的公开面（weekly_factors_of 在不在）")
import app.pipeline.prescription_stage as PS  # noqa: E402
print(f"  __all__ = {getattr(PS, '__all__', '（无）')}")
for n in sorted(dir(PS)):
    if n.startswith("_"):
        continue
    o = getattr(PS, n)
    if callable(o) and getattr(o, "__module__", "") == PS.__name__:
        try:
            print(f"  def {n}{inspect.signature(o)}")
        except (TypeError, ValueError):
            print(f"  {n}（签名取不到）")

print()
print("### C. override.py 的公开面（教师覆盖端点要吃它）")
from app.domain.prescription import override as OV  # noqa: E402
for n in ("OverrideKind", "OverrideRecord", "apply_overrides", "summarize_overrides"):
    o = getattr(OV, n, None)
    if o is None:
        print(f"  ⚠️ {n} 不存在！")
    elif dataclasses.is_dataclass(o):
        print(f"  {n} 字段 = {[(f.name, str(f.type), f.default is not dataclasses.MISSING) for f in dataclasses.fields(o)]}")
    elif inspect.isclass(o):
        print(f"  {n} 成员 = {[(m.name, m.value) for m in o]}")
    else:
        print(f"  {n}{inspect.signature(o)}")

print()
print("### D. prescription 表的列（覆盖记录要落进 teacher_overrides）")
from app.db.models.prescription import Prescription  # noqa: E402
cols = [(c.name, str(c.type), c.nullable) for c in Prescription.__table__.columns]
print(f"  {len(cols)} 列")
for c in cols:
    print(f"     {c[0]:26s} {c[1]:14s} nullable={c[2]}")

print()
print("### E. WeeklySheet 能不能 JSON 化（端点要返回它）")
import datetime as dt  # noqa: E402
import json  # noqa: E402
from app.domain.indicators import Sex  # noqa: E402
from app.domain.prescription import StudentProfile, assemble  # noqa: E402
from app.refdata_prescription import exercises, templates  # noqa: E402

lib, tpls = exercises(), templates()
prof = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20), age=20,
                      endurance_score=70.0, bmi=22.0, body_fat_pct=None,
                      muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
pkg = assemble(prof, tpls["RED-END-ABN-01"], dt.date(2026, 10, 8), exercises=lib)
sheet = WK.weekly_training_sheet(pkg, 1, [])
print(f"  WeeklySheet 字段 = {[f.name for f in dataclasses.fields(sheet)]}")
print(f"  paused={sheet.paused}  factor={sheet.factor}  reasons={sheet.reasons}  sources={sheet.sources}")
print(f"  sessions={len(sheet.sessions)}  第1课 blocks={len(sheet.sessions[0].blocks)}")
b0 = sheet.sessions[0].blocks[0]
print(f"  block[0] 字段 = {[f.name for f in dataclasses.fields(b0)]}")
try:
    s = json.dumps(dataclasses.asdict(sheet), allow_nan=False, default=str)
    print(f"  ✅ dataclasses.asdict + json.dumps(default=str) 通过（{len(s)} 字符）")
except TypeError as e:
    print(f"  ⚠️ 失败 -> {e}")
try:
    json.dumps(dataclasses.asdict(sheet), allow_nan=False)
    print("  不带 default=str 也通过")
except TypeError as e:
    print(f"  ⚠️ 不带 default=str 失败 -> {type(e).__name__}: {str(e)[:120]}  <- 端点要处理这个")

print()
print("### F. 前后端对接缺口 1：身份头有没有进 OpenAPI 的 securitySchemes")
from app.main import create_app  # noqa: E402
app = create_app(db_url="sqlite://")
spec = app.openapi()
print(f"  components.securitySchemes = {spec.get('components', {}).get('securitySchemes', '（无）')}")
print(f"  spec 顶层 security = {spec.get('security', '（无）')}")
hdr = sorted({p["name"] for ops in spec["paths"].values() for op in ops.values()
              if isinstance(op, dict) for p in op.get("parameters", []) if p.get("in") == "header"})
print(f"  路径参数里声明过的 header = {hdr or '（空）'}")

print()
print("### G. 前后端对接缺口 3：detail 路径的参数名")
pk_paths = sorted(p for p in spec["paths"] if "{" in p)
print(f"  detail 路径数 = {len(pk_paths)}")
names = sorted({prm["name"] for p in pk_paths for prm in spec["paths"][p]["get"].get("parameters", [])
                if prm.get("in") == "path"})
print(f"  path 参数名的 distinct = {names}")

print()
print("### H. build_crud_router 有没有可以传路径参数名的口子")
from app.api.crud import build_crud_router  # noqa: E402
print(f"  {inspect.signature(build_crud_router)}")

print()
print("### I. CORS 中间件今天的配置（缺口 2）")
mp = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
i = mp.index("add_middleware")
print("  " + mp[i - 200:i + 520].replace("\n", "\n  "))
