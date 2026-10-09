"""Plan 03 Task 5 预检（第二份，补 E–I）：config / deps / Task 4 的 router 形状 / zoneinfo。"""
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))

print("### A. ⚠️ Critical 复核：class_session.batch_id 与 training_log.batch_id 是 NOT NULL，"
      "而 Task 5 要让教师/学生实时写这两张表")
from app.db.models.feedback import ClassSession, TrainingLog  # noqa: E402
for cls in (ClassSession, TrainingLog):
    c = cls.__table__.c.batch_id
    print(f"  {cls.__tablename__}.batch_id  null={c.nullable}  fk={[str(fk.target_fullname) for fk in c.foreign_keys]}")
print(f"  TrainingLog.source  null={TrainingLog.__table__.c.source.nullable}  "
      f"type={TrainingLog.__table__.c.source.type}")
print(f"  TrainingLog 有 SOURCES 类常量? {getattr(TrainingLog, 'SOURCES', '（无）')}")

print()
print("### B. _replay_cleanup 今天删哪些表（batch_id 可空后，NULL 行会不会被误删）")
dp = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
i = dp.index("_replay_cleanup")
print("  " + dp[i - 300:i + 1300].replace("\n", "\n  ")[:1700])

print()
print("### C. repo.delete_by_batch 的实现（NULL 行会不会被 = 匹配到）")
import app.db.repo as R  # noqa: E402
print(inspect.getsource(R.delete_by_batch))

print()
print("### D. app/config.py 今天有什么（计划要新增 TIMEZONE）")
import app.config as CFG  # noqa: E402
for n in sorted(dir(CFG)):
    if n.startswith("_"):
        continue
    v = getattr(CFG, n)
    if not callable(v) and not inspect.isclass(v):
        print(f"  {n} = {v!r}")
print(f"  有 TIMEZONE? {hasattr(CFG, 'TIMEZONE')}")
try:
    from zoneinfo import ZoneInfo
    import datetime as dt
    z = ZoneInfo("Asia/Shanghai")
    print(f"  zoneinfo 可用 ✅  now(Asia/Shanghai) = {dt.datetime.now(z).isoformat()}")
except Exception as e:
    print(f"  ⚠️ zoneinfo 不可用 -> {type(e).__name__}: {e}")

print()
print("### E. deps.py 的公开函数（Task 5 要用 current_student / require_scope）")
from app.api import deps  # noqa: E402
for n in sorted(dir(deps)):
    if n.startswith("_"):
        continue
    o = getattr(deps, n)
    if callable(o) and getattr(o, "__module__", "") == deps.__name__:
        try:
            print(f"  def {n}{inspect.signature(o)}")
        except (TypeError, ValueError):
            print(f"  {n}（签名取不到）")

print()
print("### F. Task 4 的 prescription router 的形状（Task 5 照它办）")
pr = (BACKEND / "app" / "api" / "routers" / "prescription.py").read_text(encoding="utf-8")
print(f"  prescription.py {len(pr.encode('utf-8'))} B / {pr.count(chr(10))} 行")
for i, l in enumerate(pr.split("\n")):
    if any(k in l for k in ("router = ", "@router.", "async def ", "def ", "Security(", "require_")):
        print(f"  :{i+1} {l.rstrip()[:135]}")

print()
print("### G. routers/__init__.py 今天 include 了什么（Task 5 要加 feedback）")
ri = (BACKEND / "app" / "api" / "routers" / "__init__.py").read_text(encoding="utf-8")
print(f"  {len(ri.encode('utf-8'))} B / {ri.count(chr(10))} 行")
for i, l in enumerate(ri.split("\n")):
    if any(k in l for k in ("include_router", "import", "prefix", "tags", "__all__")):
        print(f"  :{i+1} {l.rstrip()[:135]}")

print()
print("### H. ⚠️ Critical 复核：TrainingPackage 没有 weekly_frequency，完成率的分母从哪来")
from app.domain.prescription import TrainingPackage, weekly as WK  # noqa: E402
import dataclasses  # noqa: E402
print(f"  TrainingPackage 字段 = {[f.name for f in dataclasses.fields(TrainingPackage)]}")
W = [f for f in dataclasses.fields(TrainingPackage) if f.name == "weeks"][0]
print(f"  weeks 的类型 = {W.type}")
print(f"  WeeklySheet 字段 = {[f.name for f in dataclasses.fields(WK.WeeklySheet)]}")
S = [f for f in dataclasses.fields(WK.WeeklySheet) if f.name == "sessions"][0]
print(f"  WeeklySheet.sessions 的类型 = {S.type}   <- 分母 = len(sheet.sessions)")
print(f"  weekly.current_week{inspect.signature(WK.current_week)}")
print(f"  weekly.weekly_training_sheet{inspect.signature(WK.weekly_training_sheet)}")
