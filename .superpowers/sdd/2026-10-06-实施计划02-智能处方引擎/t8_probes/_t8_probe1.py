"""Task 8 预检 probe：weekly.py 要吃的那些值对象的真实字段 + weekly_adjustment 的真实列。"""
import dataclasses
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.domain.prescription import (  # noqa: E402
    AssembledBlock, AssembledSession, AssembledWeek, TrainingPackage,
)
from app.db.models.prescription import WeeklyAdjustment, Prescription  # noqa: E402

print("### A. weekly.py 要消费的四个值对象的真实字段（运行时口径，硬规矩 #89）")
for cls in (TrainingPackage, AssembledWeek, AssembledSession, AssembledBlock):
    F = dataclasses.fields(cls)
    print(f"  {cls.__name__} ({len(F)} 个字段)")
    for f in F:
        d = "（无缺省）" if isinstance(f.default, dataclasses._MISSING_TYPE.__class__) or f.default is dataclasses.MISSING else f"= {f.default!r}"
        print(f"      .{f.name}: {f.type}  {d}")

print()
print("### B. weekly_adjustment 与 prescription 的真实列")
for cls in (WeeklyAdjustment, Prescription):
    cols = [(c.name, str(c.type), c.nullable) for c in cls.__table__.columns]
    print(f"  {cls.__tablename__} ({len(cols)} 列)")
    for c in cols:
        print(f"      {c[0]:24s} {c[1]:14s} nullable={c[2]}")

print()
print("### C. volume_unit 的值域（缩放不得跨单位相加）")
import app.domain.prescription.assembler as ASM  # noqa: E402
print(f"  VOLUME_UNITS = {sorted(ASM.VOLUME_UNITS)}")
print(f"  VOLUME_FACTOR_BANDS = {sorted(ASM.VOLUME_FACTOR_BANDS)}")

print()
print("### D. TrainingPackage.paused 与 weeks 的实际形状（跑一次真仓装配）")
import datetime as dt  # noqa: E402
from app.domain.indicators import Sex  # noqa: E402
from app.domain.prescription import StudentProfile, assemble  # noqa: E402
from app.refdata_prescription import exercises, templates  # noqa: E402

lib = exercises()
tpls = templates()
prof = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20), age=20,
                      endurance_score=70.0, bmi=22.0, body_fat_pct=None,
                      muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
for tid in ("RED-END-ABN-01", "YEL-END-NOR-08", "GRN-END-NOR-14"):
    pkg = assemble(prof, tpls[tid], dt.date(2026, 10, 8), exercises=lib)
    units = sorted({b.volume_unit for w in pkg.weeks for s in w.sessions for b in s.blocks})
    vols = [(b.volume_unit, b.weekly_volume) for w in pkg.weeks[:1] for s in w.sessions for b in s.blocks]
    print(f"  {tid}: weeks={len(pkg.weeks)} paused={pkg.paused} "
          f"sessions/周={[len(w.sessions) for w in pkg.weeks]} 出现的 volume_unit={units}")
    print(f"      第 1 周的 (unit, weekly_volume) = {vols}")
    print(f"      各周 delta = {[w.delta for w in pkg.weeks]}")

print()
print("### E. prescription_stage 里已有的读法（weekly_factors_of 要照它的形状）")
ps = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
for name in ("weekly_factors_of", "_previous_prescriptions", "def profile_of"):
    print(f"  {name!r} 在 prescription_stage.py 里命中 {ps.count(name)}")
import re  # noqa: E402
for m in re.finditer(r"^def (\w+)\(", ps, re.M):
    print(f"     def {m.group(1)}")

print()
print("### F. domain 的公开面（Task 8 会加几个名字）")
import app.domain.prescription as PKG  # noqa: E402
print(f"  __all__ = {len(PKG.__all__)}")
print(f"  已有 weekly 相关? {[n for n in PKG.__all__ if 'week' in n.lower()]}")
