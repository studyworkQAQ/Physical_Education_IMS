"""Plan 03 Task 7 预检（一份探针）：预警落地要吃的东西 + 架构守卫认不认新模块。
⚠️ 硬规矩 #108：写完先 py_compile。⚠️ #107：谓词先对已知反例验证。
"""
import dataclasses
import inspect
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))

print("### A. ⚠️ 最高风险：pipeline 层的 allow-list 认不认 app.domain.alerts / app.refdata_alerts")
lay = (BACKEND / "tests" / "architecture" / "test_layering.py").read_text(encoding="utf-8")
for name in ("_PIPELINE_ALLOWED", "_DB_ALLOWED", "_API_ALLOWED", "SCANNED_DIRS", "FORBIDDEN_PREFIX"):
    for m in re.finditer(rf"^{name}\s*[:=].*?(?:\}}|\))\s*$", lay, re.M | re.S):
        print(f"  {name}:")
        for l in m.group(0).split("\n"):
            if l.strip() and not l.strip().startswith("#"):
                print(f"    {l.strip()[:118]}")
print("  --- 全部 frozenset/tuple 常量名 ---")
for m in re.finditer(r"^(_?[A-Z][A-Z0-9_]+)\s*(?::[^=]+)?=\s*(frozenset|\(|\{)", lay, re.M):
    print(f"    {m.group(1)}")

print()
print("### B. daily.py 的阶段序列与 _replay_cleanup 今天的清单")
dp = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
print(f"  daily.py {len(dp.encode('utf-8'))} B / {dp.count(chr(10))} 行")
for i, l in enumerate(dp.split("\n")):
    if re.search(r"^(def |class |STAGES|_STAGES|@dataclass)|_replay_cleanup|alert_count|prescription_count|delete_by_batch", l):
        print(f"  :{i+1} {l.rstrip()[:130]}")
i = dp.index("_replay_cleanup")
print("  --- _replay_cleanup 全文 ---")
print("  " + dp[i - 200:i + 1600].replace("\n", "\n  ")[:1900])

print()
print("### C. Task 6 交付的 domain 接口（alert_stage 要调它们）")
import app.domain.alerts as AL  # noqa: E402
for n in AL.__all__:
    o = getattr(AL, n)
    if callable(o) and not dataclasses.is_dataclass(o) and not inspect.isclass(o):
        print(f"  def {n}{inspect.signature(o)}")
print(f"  StudentSignals 字段 = {[f.name for f in dataclasses.fields(AL.StudentSignals)]}")
print(f"  ClassSignals  字段 = {[f.name for f in dataclasses.fields(AL.ClassSignals)]}")
print(f"  StudentHit    字段 = {[f.name for f in dataclasses.fields(AL.StudentHit)]}")
print(f"  ClassHit      字段 = {[f.name for f in dataclasses.fields(AL.ClassHit)]}")
print(f"  SUBJECT_PREFIX_STUDENT = {AL.SUBJECT_PREFIX_STUDENT!r}  SUBJECT_PREFIX_SECTION = {AL.SUBJECT_PREFIX_SECTION!r}")
print(f"  RuleId 成员 = {[m.value for m in AL.RuleId]}")
print(f"  AlertLevel 成员 = {[(m.name, m.value) for m in AL.AlertLevel]}")
print(f"  AlertScope 成员 = {[(m.name, m.value) for m in AL.AlertScope]}")
import app.refdata_alerts as RA  # noqa: E402
pub = sorted(n for n in dir(RA) if not n.startswith("_"))
print(f"  refdata_alerts 公开面 = {pub}")
for n in pub:
    o = getattr(RA, n)
    if callable(o):
        print(f"    {n}{inspect.signature(o)}")

print()
print("### D. weekly.py 与 prescription_stage 的接口（auto 来源要写 weekly_adjustment）")
from app.domain.prescription import weekly as WK  # noqa: E402
print(f"  compute_weekly_factor{inspect.signature(WK.compute_weekly_factor)}")
print(f"  current_week{inspect.signature(WK.current_week)}")
print(f"  WeeklyFactor 字段 = {[f.name for f in dataclasses.fields(WK.WeeklyFactor)]}")
print(f"  WeeklyFactor 的 SOURCES / 值域常量 = {[n for n in dir(WK) if n.isupper()]}")
import app.pipeline.prescription_stage as PS  # noqa: E402
print(f"  weekly_factors_of{inspect.signature(PS.weekly_factors_of)}")
print(f"  active_or_needs_review{inspect.signature(PS.active_or_needs_review)}")
print(f"  regenerate_for_student{inspect.signature(PS.regenerate_for_student)}")

print()
print("### E. Alert / Notification 的列（alert_stage 与 InAppChannel 要填）")
from app.db.models.feedback import Alert, Notification  # noqa: E402
for cls in (Alert, Notification):
    t = cls.__table__
    print(f"  {t.name}（{len(t.columns)} 列）")
    for c in t.columns:
        d = c.default.arg if c.default is not None and not callable(getattr(c.default, "arg", None)) else None
        print(f"     {c.name:22s} {str(c.type):16s} null={c.nullable} pk={c.primary_key} default={d!r}")
    print(f"     类常量 = {[n for n in dir(cls) if n.isupper()]}")

print()
print("### F. 三源表的列（alert_stage 要从它们算 Signals）")
from app.db.models.feedback import RpeRecord, TrainingLog, MiniTest, ClassSession  # noqa: E402
for cls in (ClassSession, RpeRecord, TrainingLog, MiniTest):
    print(f"  {cls.__tablename__}: {[c.name for c in cls.__table__.columns]}")

print()
print("### G. weekly_adjustment 的列与约束（auto 来源要写它）")
from app.db.models.prescription import WeeklyAdjustment  # noqa: E402
t = WeeklyAdjustment.__table__
print(f"  {[ (c.name, str(c.type), c.nullable) for c in t.columns ]}")
for c in t.constraints:
    if type(c).__name__ in ("UniqueConstraint", "CheckConstraint"):
        print(f"  [{type(c).__name__}] {c.name} {[getattr(x,'name',None) for x in getattr(c,'columns',[])] or c.sqltext}")
print(f"  类常量 = {[n for n in dir(WeeklyAdjustment) if n.isupper()]}")
print(f"  SOURCES = {getattr(WeeklyAdjustment, 'SOURCES', None)}")

print()
print("### H. repo.upsert 的签名（写 weekly_adjustment 与 alert 都要用它）")
import app.db.repo as R  # noqa: E402
print(f"  upsert{inspect.signature(R.upsert)}")
print(f"  delete_by_batch{inspect.signature(R.delete_by_batch)}")

print()
print("### I. PrescriptionReport / DailyReport 的形状（alert_count 要写进去）")
print(f"  PrescriptionReport 字段 = {[f.name for f in dataclasses.fields(PS.PrescriptionReport)]}")
import app.pipeline.daily as D  # noqa: E402
cands = [n for n in dir(D) if n.endswith("Report") or n.endswith("Stage")]
print(f"  daily.py 里的 Report/Stage 名 = {cands}")
for n in cands:
    o = getattr(D, n)
    if dataclasses.is_dataclass(o):
        print(f"    {n} 字段 = {[f.name for f in dataclasses.fields(o)]}")
print(f"  daily.run_daily{inspect.signature(D.run_daily)}")
