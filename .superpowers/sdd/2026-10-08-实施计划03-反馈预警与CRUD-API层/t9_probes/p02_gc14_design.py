"""Task 9 探针 02：为 GC14 选一套输入。

要回答三件事（全部运行时口径）：
① exercises.yaml 里 5 个 high 动作与 8 个 low 动作分别是谁，addon 模块
   ``energy_expenditure_plus_5min_hiit`` / ``resistance_priority`` 的冲击等级是什么；
② 18 套模板各自 week1/session0/block0 的动作与冲击等级，以及每套模板里 HIGH block 的
   ref 集合（决定 ``safety_substitution_count`` 与 ``needs_review``）；
③ 既有 13 例的 (sex, age) 组合，确认 GC14 落在哪一组都不会改 ``percentile_note`` 的 24 行。
"""
import collections
import datetime as dt
import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import models  # noqa: E402
from app.domain.prescription.assembler import StudentProfile, assemble  # noqa: E402
from app.domain.indicators import Sex, age_group_of  # noqa: E402
from app.domain.prescription.exercises import ImpactLevel  # noqa: E402
from app.refdata_prescription import equivalence, exercises, templates  # noqa: E402

AS_OF = dt.date(2025, 9, 15)
EX = exercises()
EQ = equivalence()

print("== ① 动作库按冲击等级分组 ==")
by_impact = collections.defaultdict(list)
for ref, spec in EX.items():
    by_impact[spec.impact_level.value].append(ref)
for level in ("high", "medium", "low"):
    print(f"  {level}: {sorted(by_impact[level])}")
print("  equivalence mappings (when=bmi_over_30):",
      sorted((m.from_ref, m.to_ref) for m in EQ.mappings if m.when == "bmi_over_30"))
print("  volume_reduction:", dict(EQ.volume_reduction), "version:", EQ.version)

print("== ② 18 套模板的 block0 与 HIGH block 集合 ==")


def _profile(sex=Sex.MALE, age=20) -> StudentProfile:
    return StudentProfile(
        student_id=1, sex=sex, birth=dt.date(AS_OF.year - age, AS_OF.month, AS_OF.day),
        age=age, endurance_score=70.0, bmi=None, body_fat_pct=None,
        muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None,
    )


for tpl in sorted(templates().values(), key=lambda t: t.template_id):
    pkg = assemble(_profile(), tpl, AS_OF, exercises=EX)
    b0 = pkg.weeks[0].sessions[0].blocks[0]
    high = sorted({
        b.exercise_ref
        for w in pkg.weeks for s in w.sessions for b in s.blocks
        if b.impact_level is ImpactLevel.HIGH
    })
    n_blocks = sum(len(s.blocks) for w in pkg.weeks for s in w.sessions)
    n_high = sum(
        1 for w in pkg.weeks for s in w.sessions for b in s.blocks
        if b.impact_level is ImpactLevel.HIGH
    )
    unmapped = [r for r in high if EQ.lookup(r, ImpactLevel.LOW) is None]
    print(f"  {tpl.template_id:18s} freq={tpl.weekly_frequency} weeks={len(pkg.weeks)} "
          f"blocks={n_blocks} high={n_high} block0={b0.exercise_ref}"
          f"({b0.impact_level.value}) addons={[a.when + ':' + a.module for a in tpl.addons]}")
    print(f"      high refs={high} unmapped={unmapped}")

print("== addon 模块的冲击等级 ==")
for name in ("energy_expenditure_plus_5min_hiit", "resistance_priority"):
    spec = EX.get(name)
    print(f"  {name}: {'<不在动作库>' if spec is None else spec.impact_level.value}")

print("== ③ 既有 13 例的 (sex, age) 与年级组 ==")
cases = json.loads((BACKEND / "tests" / "fixtures" / "golden_cases.json").read_text(encoding="utf-8"))
combos = collections.Counter()
for case in cases["input"]:
    group = age_group_of(case["age"])
    combos[(case["sex"], case["age"], group.value if hasattr(group, "value") else group)] += 1
for key, n in sorted(combos.items()):
    print("  ", key, n)
print("  muscle_p20_by_group:", cases["_meta"]["muscle_p20_by_group"])
print("  age_group_of(19) =", age_group_of(19), " age_group_of(21) =", age_group_of(21))
print("  models.Student.__table__ 无关，仅确认导入成功:", models.__name__)
