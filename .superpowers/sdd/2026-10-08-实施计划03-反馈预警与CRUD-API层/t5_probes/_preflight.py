"""Plan 03 Task 5 预检（一份探针）：三源采集端点要吃的东西 + 架构守卫会不会拦 secrets/datetime。"""
import dataclasses
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))

print("### A. ⚠️ 最高风险：架构守卫会不会拦 app/api 里的 secrets / datetime / zoneinfo")
lay = (BACKEND / "tests" / "architecture" / "test_layering.py").read_text(encoding="utf-8")
i = lay.index("_is_api_allowed")
print("  " + lay[i - 400:i + 1500].replace("\n", "\n  ")[:2200])

print()
print("### B. Task 2 建的 4 张表的列（三源采集要写它们）")
from app.db import models as M  # noqa: E402
from app.db.models.feedback import ClassSession, RpeRecord, TrainingLog, MiniTest  # noqa: E402
for cls in (ClassSession, RpeRecord, TrainingLog, MiniTest):
    t = cls.__table__
    print(f"  {t.name}（{len(t.columns)} 列）")
    for c in t.columns:
        d = c.default.arg if c.default is not None and not callable(c.default.arg) else None
        print(f"     {c.name:22s} {str(c.type):16s} null={c.nullable} pk={c.primary_key} default={d!r}")
    for k in t.constraints:
        if type(k).__name__ in ("UniqueConstraint", "CheckConstraint"):
            cols = [getattr(x, "name", None) for x in getattr(k, "columns", [])]
            print(f"     [{type(k).__name__}] {k.name}  {cols or getattr(k, 'sqltext', '')}")

print()
print("### C. TrainingLog 的值域常量与 RpeRecord 的 RPE 上下界（P3-A5 要求有类常量）")
print(f"  TrainingLog.FEELINGS = {getattr(TrainingLog, 'FEELINGS', '（无）')}")
print(f"  RpeRecord.RPE_MIN / RPE_MAX = {getattr(RpeRecord, 'RPE_MIN', '（无）')} / {getattr(RpeRecord, 'RPE_MAX', '（无）')}")
print(f"  ClassSession 的类常量 = {[n for n in dir(ClassSession) if n.isupper()]}")

print()
print("### D. 完成率的分母要从哪来（Template.weekly_frequency）")
import app.pipeline.prescription_stage as PS  # noqa: E402
print(f"  active_or_needs_review{inspect.signature(PS.active_or_needs_review)}")
from app.domain.prescription import TrainingPackage  # noqa: E402
print(f"  TrainingPackage 字段 = {[f.name for f in dataclasses.fields(TrainingPackage)]}")
print(f"  TrainingPackage 有 weekly_frequency? {'weekly_frequency' in [f.name for f in dataclasses.fields(TrainingPackage)]}")
import json  # noqa: E402
print(f"  training_package_payload 的产出里有没有 weekly_frequency / template_ref：")
src = inspect.getsource(PS.training_package_payload)
print("    " + src[:1400].replace("\n", "\n    "))

print()
print("### E. app/config.py 今天有什么（计划要新增 TIMEZONE）")
import app.config as CFG  # noqa: E402
for n in sorted(dir(CFG)):
    if n.startswith("_"):
        continue
    v = getattr(CFG, n)
    if not callable(v) and not inspect.isclass(v):
        print(f"  {n} = {v!r}")
print(f"  有 TIMEZONE? {hasattr(CFG, 'TIMEZONE')}")
print(f"  有 ZoneInfo 可用? ", end="")
try:
    from zoneinfo import ZoneInfo
    ZoneInfo("Asia/Shanghai")
    print("是（zoneinfo + tzdata 都在）")
except Exception as e:
    print(f"否 -> {type(e).__name__}: {e}")

print()
print("### F. deps.py 今天的公开面（Task 5 要加 current_student/require_scope 的使用）")
from app.api import deps  # noqa: E402
for n in sorted(dir(deps)):
    if n.startswith("_"):
        continue
    o = getattr(deps, n)
    if callable(o) and getattr(o, "__module__", "") == deps.__name__:
        try:
            print(f"  def {n}{inspect.signature(o)}")
        except (TypeError, ValueError):
            print(f"  {n}")

print()
print("### G. Task 4 建的 prescription router 的形状（Task 5 照它办）")
pr = (BACKEND / "app" / "api" / "routers" / "prescription.py").read_text(encoding="utf-8")
print(f"  prescription.py {len(pr.encode('utf-8'))} B / {pr.count(chr(10))} 行")
for i, l in enumerate(pr.split("\n")):
    if any(k in l for k in ("router = ", "@router.", "def ", "Security", "Depends", "require_")):
        print(f"  :{i+1} {l.rstrip()[:130]}")

print()
print("### H. routers/__init__.py 今天 include 了什么")
ri = (BACKEND / "app" / "api" / "routers" / "__init__.py").read_text(encoding="utf-8")
print(f"  {len(ri.encode('utf-8'))} B / {ri.count(chr(10))} 行")
for i, l in enumerate(ri.split("\n")):
    if any(k in l for k in ("include_router", "import", "prefix", "tags")):
        print(f"  :{i+1} {l.rstrip()[:130]}")
