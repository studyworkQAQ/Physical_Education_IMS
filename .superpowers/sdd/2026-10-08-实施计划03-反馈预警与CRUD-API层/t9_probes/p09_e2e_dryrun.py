"""Task 9 探针 09：端到端场景的**可行性预演**（进程内直接调，不走 HTTP）。

目的：在写 tests/api/test_end_to_end.py 之前，先把「60 人演示库 + 一次 run_daily +
三节课 RPE=9 + 再跑一次 run_daily」这条链上的**真实 id 与真实计数**打出来，
于是测试里的每一个期望值都是实测来的、不是猜的。

⚠️ 用 tmp 目录当 CSV 源，**绝不碰** backend/data/seed/（禁区，0 文件）与 backend/pe.db。
"""
import datetime as dt
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.mock_lepao import MockLePaoAdapter  # noqa: E402
from app.db import models as M  # noqa: E402
from app.db.models.feedback import (  # noqa: E402
    Alert,
    ClassSession,
    Notification,
    RpeRecord,
    WeeklyClassReport,
)
from app.db.models.organisation import (  # noqa: E402
    CourseSection,
    Enrollment,
    Semester,
    Student,
    Teacher,
)
from app.db.models.prescription import Prescription, WeeklyAdjustment  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.pipeline.daily import run_daily  # noqa: E402
from app.seed.config import SeedConfig  # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402

CFG = SeedConfig(students=60, weeks=16, seed=20250828)
BUSINESS_DATE = "2025-09-15"

tmp = pathlib.Path(tempfile.mkdtemp(prefix="t9_e2e_"))
csv_dir = tmp / "lepao"
write_csv(build_dataset(CFG), csv_dir)
print("csv_dir:", csv_dir, "files:", sorted(p.name for p in csv_dir.iterdir()))

engine = create_engine("sqlite://")
init_db(engine)
with Session(engine) as s:
    seed_database(s, CFG)
    s.commit()

with Session(engine) as s:
    print("semesters:", s.execute(
        select(Semester.id, Semester.name, Semester.start_date, Semester.end_date,
               Semester.weeks, Semester.is_current)).all())
    print("teachers[:3]:", s.execute(select(Teacher.id, Teacher.staff_no).limit(3)).all())
    print("students[:3]:", s.execute(select(Student.id, Student.student_no).limit(3)).all())
    print("sections[:6]:", s.execute(
        select(CourseSection.id, CourseSection.semester_id, CourseSection.teacher_id,
               CourseSection.name, CourseSection.grouping_mode).limit(6)).all())
    print("enrollment count:", s.scalar(select(func.count()).select_from(Enrollment)))

SEM = 2
with Session(engine) as s:
    run = run_daily(s, SEM, BUSINESS_DATE, MockLePaoAdapter(csv_dir))
    s.commit()
    print("\nrun #1:", run.id, run.status, "extracted",
          run.extracted_fitness, run.extracted_body_comp, run.extracted_survey,
          "layers", run.red_count, run.yellow_count, run.green_count,
          run.insufficient_count, "rx", run.prescription_count,
          "alerts", run.alert_count, "err", run.error_summary)
    print("prescription count:", s.scalar(select(func.count()).select_from(Prescription)))
    print("stratification count:",
          s.scalar(select(func.count()).select_from(M.StratificationResult)))
    print("daily_sync_run rows:", s.scalar(select(func.count()).select_from(M.DailySyncRun)))

candidate = []
with Session(engine) as s:
    candidate = s.execute(
        select(Prescription.student_id, Prescription.id, Prescription.template_ref,
               Prescription.generated_on, Prescription.microcycle_weeks,
               Prescription.status, Enrollment.course_section_id,
               CourseSection.teacher_id, Teacher.staff_no)
        .join(Enrollment, Enrollment.student_id == Prescription.student_id)
        .join(CourseSection, CourseSection.id == Enrollment.course_section_id)
        .join(Teacher, Teacher.id == CourseSection.teacher_id)
        .where(Prescription.status == "active",
               Enrollment.semester_id == SEM, CourseSection.semester_id == SEM)
        .order_by(Prescription.student_id)
        .limit(4)
    ).all()
    print("\ncandidates:")
    for c in candidate:
        print("   ", c)

chosen = candidate[0]
student_id, section_id, staff_no = chosen[0], chosen[6], chosen[8]
print("\n== 造三节课 + 三次 RPE=9 ==")
print("student_id", student_id, "section_id", section_id, "staff_no", staff_no)
with Session(engine) as s:
    ids = []
    for day in (dt.date(2025, 9, 10), dt.date(2025, 9, 12), dt.date(2025, 9, 15)):
        cs = ClassSession(course_section_id=section_id, session_date=day, period=3,
                          rpe_opened=True, rpe_token="TOK", batch_id=None)
        s.add(cs)
        s.flush()
        ids.append(cs.id)
        s.add(RpeRecord(class_session_id=cs.id, student_id=student_id, rpe=9,
                        submitted_at=dt.datetime(2025, 9, 15, 10, 35),
                        elapsed_seconds=20.0))
    s.commit()
    print("class_session ids:", ids)

with Session(engine) as s:
    run2 = run_daily(s, SEM, BUSINESS_DATE, MockLePaoAdapter(csv_dir))
    s.commit()
    print("\nrun #2:", run2.id, run2.status, "rx", run2.prescription_count,
          "alerts", run2.alert_count, "err", run2.error_summary)
    print("alerts:")
    for a in s.execute(select(Alert.id, Alert.rule_id, Alert.level, Alert.student_id,
                              Alert.course_section_id, Alert.status, Alert.window_key,
                              Alert.subject_key)).all():
        print("   ", a)
    print("weekly_adjustments:")
    for w in s.execute(select(WeeklyAdjustment.id, WeeklyAdjustment.prescription_id,
                              WeeklyAdjustment.week, WeeklyAdjustment.factor,
                              WeeklyAdjustment.reason, WeeklyAdjustment.source)).all():
        print("   ", w)
    print("notifications:")
    for n in s.execute(select(Notification.id, Notification.recipient_kind,
                              Notification.recipient_id, Notification.title,
                              Notification.alert_id, Notification.is_read)).all():
        print("   ", n)
    print("our student's prescription:", s.execute(
        select(Prescription.id, Prescription.student_id, Prescription.status,
               Prescription.generated_on, Prescription.valid_from, Prescription.valid_to)
        .where(Prescription.student_id == student_id)).all())
    print("weekly_class_report count:",
          s.scalar(select(func.count()).select_from(WeeklyClassReport)))
    print("rpe_record count:", s.scalar(select(func.count()).select_from(RpeRecord)))
    print("class_session count:", s.scalar(select(func.count()).select_from(ClassSession)))
    print("teacher of section:", s.execute(
        select(Teacher.staff_no).where(Teacher.id == chosen[7])).all())
