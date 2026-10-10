"""Task 9 探针 05：GC14 的 week1_block0_weekly_volume 与 hr_zone 的**手算复核**。

``_meta.expected_schema`` 给的算式：
  weekly_volume = base × sessions_per_week × 个体修正系数 × week_deltas[0]，round(…, 1)
  hr_zone = [floor(HRmax × 低界%), ceil(HRmax × 高界%)]，HRmax = 208 − 0.7 × age
安全后置再乘 ``safety_volume_factor`` 并 round(…, 1)。

⚠️ 输入是**手写的** StudentProfile（不 import 探针 04，避免它的打印与「跑一次生产」
混在一起）：字面值取自探针 04 打印出来的 ``profile:`` 那一行，两侧不同源
（硬规矩 #35 在探针里的对应做法：期望侧手写、实际侧现算）。
"""
import datetime as dt
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.domain.indicators import Sex  # noqa: E402
from app.domain.prescription.assembler import StudentProfile, assemble  # noqa: E402
from app.domain.prescription.safety import SafetyInput, apply_safety  # noqa: E402
from app.refdata_prescription import equivalence, exercises, templates  # noqa: E402

AS_OF = dt.date(2025, 9, 15)
AGE = 19
TEMPLATE_ID = "RED-SPD-ABN-05"

profile = StudentProfile(
    student_id=14, sex=Sex.MALE, birth=dt.date(2006, 9, 15), age=AGE,
    endurance_score=60.0, bmi=31.0, body_fat_pct=28.0, muscle_mass_kg=45.0,
    muscle_p10=None, measured_hrmax=None,
)
template = templates()[TEMPLATE_ID]
pkg = assemble(profile, template, AS_OF, exercises=exercises())
snap = pkg.assembly_snapshot
print("assembly_snapshot（assemble 的 12 个键）:")
for key in sorted(snap):
    print(f"   {key} = {snap[key]!r}")
b0 = pkg.weeks[0].sessions[0].blocks[0]
print("\n安全后置**之前**的 block0:", b0.exercise_ref, b0.impact_level.value,
      b0.weekly_volume, b0.volume_unit, b0.hr_zone, b0.intensity_text, b0.structure)

safety = apply_safety(
    pkg,
    SafetyInput(bmi=31.0, muscle_mass_kg=45.0, muscle_p10=None, body_fat_abnormal=True),
    equivalence(), template=template, exercises=exercises(),
)
after = safety.package.weeks[0].sessions[0].blocks[0]
print("安全后置**之后**的 block0:", after.exercise_ref, after.impact_level.value,
      after.weekly_volume, after.volume_unit, after.hr_zone)

print("\n== 手算复核 ==")
# ⚠️ ``weekly_volume_base`` 是**按单位汇总**的一份 MappingProxy（{'min': 144.0}），
# 不是 block 级的 base；block 级的 base 由 structure 算出（§14 #36：时长类 = work_min × sets）。
structure = dict(b0.structure)
block_base = structure["work_min"] * structure["sets"]
base = dict(snap["weekly_volume_base"])
freq = template.weekly_frequency
indiv = snap["volume_factor"]
delta0 = snap["week_deltas"][0]
pre = block_base * freq * indiv * delta0
print(f"  weekly_volume_base（按单位汇总，只作对照）= {base}")
print(f"  block base = work_min {structure['work_min']} × sets {structure['sets']} = {block_base}"
      f"（rest_min {structure['rest_min']} 不计入量，spec §14 #36）")
print(f"  {block_base} × sessions_per_week={freq} × 个体修正={indiv}"
      f"（band={snap['volume_factor_band']}）× week_deltas[0]={delta0}"
      f" = {pre} → round(…,1) = {round(pre, 1)}")
factor = safety.package.assembly_snapshot["safety_volume_factor"]
print(f"  × safety_volume_factor={factor} = {round(pre, 1) * factor}"
      f" → round(…,1) = {round(round(pre, 1) * factor, 1)}")
print(f"  实际 block0.weekly_volume = {after.weekly_volume}")
hrmax = 208 - 0.7 * AGE
print(f"  HRmax = 208 − 0.7 × {AGE} = {hrmax}")
print(f"  hr_zone 实际 = {list(after.hr_zone)}；"
      f"60% → {hrmax * 0.60} floor {math.floor(hrmax * 0.60)}；"
      f"70% → {hrmax * 0.70} ceil {math.ceil(hrmax * 0.70)}")
print(f"  模板 block0 的 intensity = {template.sessions[0].blocks[0].intensity}")
print(f"\n  substitutions = {len(safety.substitutions)}；"
      f"HIGH block 数 = {sum(1 for w in pkg.weeks for s in w.sessions for b in s.blocks if b.impact_level.value == 'high')}")
print(f"  needs_review = {safety.needs_review}")
print(f"  warnings = {list(safety.warnings)}")
