"""挑一个用于完成率测试的处方模板：列出 ref → weekly_frequency → 第 1 周 sessions 数。"""
import datetime as dt
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import refdata_prescription as rp                 # noqa: E402
from app.domain.indicators import Sex                      # noqa: E402
from app.domain.prescription.assembler import StudentProfile, assemble  # noqa: E402

AS_OF = dt.date(2025, 9, 1)
BIRTH = dt.date(2005, 3, 4)


def _profile() -> StudentProfile:
    return StudentProfile(
        student_id=1, sex=Sex.MALE, birth=BIRTH, age=20, endurance_score=70.0,
        bmi=None, body_fat_pct=None, muscle_mass_kg=None, muscle_p10=None,
        measured_hrmax=None,
    )


templates = rp.templates()
print("template count:", len(templates))
for ref in sorted(templates):
    t = templates[ref]
    pkg = assemble(_profile(), t, AS_OF, exercises=rp.exercises())
    per_week = [len(w.sessions) for w in pkg.weeks]
    days_w1 = [s.day for s in pkg.weeks[0].sessions]
    print(f"{ref:20s} weekly_frequency={t.weekly_frequency} microcycle={t.microcycle_weeks} "
          f"sessions_per_week={per_week} week1_days={days_w1} paused={pkg.paused}")
