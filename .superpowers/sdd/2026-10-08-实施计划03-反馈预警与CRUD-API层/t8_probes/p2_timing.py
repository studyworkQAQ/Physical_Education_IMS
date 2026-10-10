"""T8 探针 2：量 ``training_days_of`` 的吞吐，决定周报「按层分组打卡完成率」的取数口径。

背景：整学期回放是 500 人 ×112 业务日，其中**周日 16 天**；seed 的编班是
``administrative_section_count(500, cfg)`` 个行政班 + 4 个分层班，故 enrollment 约 1000 行。
若周报逐 (班, 生) 调 ``training_days_of``，一次回放就是 16 × 1000 = 16 000 次装配
（按 prescription_id 记忆化后 16 × 500 = 8 000 次）。
``test_backfill_500_students_under_90_seconds`` 的既有实测是 47.33 / 47.96 s、阈值 90、
余量 1.88×（已经低于硬规矩 #42 的 2× 线）。故先量清楚再定口径。

⚠️ 写在 TEMP 下、显式设 PE_DB_URL，绝不碰 backend/pe.db 与 backend/data/seed/。
"""
import datetime as dt
import os
import pathlib
import sys
import tempfile
import time

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
TMP = pathlib.Path(tempfile.mkdtemp(prefix="t8_probe2_"))
DB = TMP / "probe.db"
os.environ["PE_DB_URL"] = f"sqlite:///{DB.as_posix()}"
sys.path.insert(0, str(BACKEND))
# 让 app.config 读到上面那个 PE_DB_URL（它必须在 import 之前设好）
os.chdir(BACKEND)

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import models as M  # noqa: E402
from app.db.models.prescription import Prescription  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.pipeline import daily as daily_mod  # noqa: E402
from app.pipeline.prescription_stage import training_days_of  # noqa: E402
from app.refdata_prescription import exercises as exercise_library  # noqa: E402
from app.seed.config import SeedConfig  # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402
from app.adapters.mock_lepao import MockLePaoAdapter  # noqa: E402

CFG = SeedConfig(students=500, weeks=16, seed=20250828)  # 与 test_backfill.py 逐字同
print("TMP =", TMP)
t0 = time.perf_counter()
dataset = build_dataset(CFG)
write_csv(dataset, TMP)
print(f"build_dataset + write_csv: {time.perf_counter() - t0:.2f}s")

eng = create_engine(f"sqlite:///{DB.as_posix()}")
init_db(eng)
with Session(eng) as s:
    t0 = time.perf_counter()
    seed_database(s, CFG)
    s.commit()
    print(f"seed_database: {time.perf_counter() - t0:.2f}s")
    from sqlalchemy import func
    print("  course_section 行数 =", s.scalar(select(func.count()).select_from(M.CourseSection)))
    print("  enrollment 行数   =", s.scalar(select(func.count()).select_from(M.Enrollment)))
    print("  student 行数      =", s.scalar(select(func.count()).select_from(M.Student)))
    sem = s.scalars(select(M.Semester)).all()
    print("  semester =", [(x.id, x.name, x.start_date.isoformat()) for x in sem])
    semester_id = [x.id for x in sem if x.name == "2025-2026-1"][0]

# 跑三个业务日，让处方生成出来（第一天 first_stratification 触发）
adapter = MockLePaoAdapter(TMP)
for day in ("2025-09-01", "2025-09-02", "2025-09-03"):
    with Session(eng) as s:
        t0 = time.perf_counter()
        run = daily_mod.run_daily(s, semester_id, day, adapter)
        print(f"run_daily({day}): {time.perf_counter() - t0:.2f}s status={run.status}")

with Session(eng) as s:
    from sqlalchemy import func
    print("  prescription 行数 =", s.scalar(select(func.count()).select_from(Prescription)))

# --- 计时：逐人调 training_days_of ----------------------------------------
EX = exercise_library()
with Session(eng) as s:
    rows = list(s.scalars(select(Prescription)))
    print("  取到处方 =", len(rows))
    as_of = dt.date(2025, 9, 3)
    # 预热一次（把参考数据单例与 SQLite 页缓存填上）
    from app.domain.prescription.weekly import current_week
    if rows:
        r0 = rows[0]
        w0 = current_week(r0.generated_on, as_of, r0.microcycle_weeks)
        if w0:
            training_days_of(s, r0, w0, exercises=EX)

    for repeat in (1, 2):
        t0 = time.perf_counter()
        done = 0
        for row in rows:
            week = current_week(row.generated_on, as_of, row.microcycle_weeks)
            if week is None:
                continue
            training_days_of(s, row, week, exercises=EX)
            done += 1
        elapsed = time.perf_counter() - t0
        per = elapsed / done * 1000 if done else float("nan")
        print(f"  第 {repeat} 轮：{done} 次 training_days_of 用 {elapsed:.3f}s"
              f" -> {per:.3f} ms/次")
        print(f"    外推 8000 次（16 个周日 × 500 人，按 prescription_id 记忆化）="
              f" {per * 8000 / 1000:.2f}s")
        print(f"    外推 16000 次（不记忆化，逐 (班, 生)）="
              f" {per * 16000 / 1000:.2f}s")
eng.dispose()
print("DB 大小 =", DB.stat().st_size, "字节；backend/pe.db 存在?",
      (BACKEND / "pe.db").exists())
