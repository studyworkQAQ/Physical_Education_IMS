# -*- coding: utf-8 -*-
"""Probe P7: daily.py:206-212 那个 anchor 实验 + config.py:43 的 TypeError 断言。"""
import datetime as dt, sys, pathlib
sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
from sqlalchemy import create_engine
from app.db import models as M
from app.db.session import Session, init_db
from app.pipeline.percentile_stage import assessment_anchor
from app.config import BACKEND_DIR, DEFAULT_CSV_DIR, DEFAULT_DB_URL

DAYS = [dt.date(2025, 9, d) for d in range(1, 6)]


def run(test_date):
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                         end_date=dt.date(2026, 1, 31), weeks=16, is_current=True)
        s.add(sem); s.flush()
        b = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
                               test_date=test_date, academic_year="2025-2026")
        s.add(b); s.flush()
        for i, d in enumerate(DAYS, start=1):
            st = M.Student(student_no="2025%06d" % i, name="x", sex="male",
                           birth=dt.date(2006, 1, 1), grade=1)
            s.add(st); s.flush()
            s.add(M.FitnessTestResult(test_batch_id=b.id, student_id=st.id, tested_on=d))
        s.commit()
        flags, first = [], None
        for as_of in DAYS:
            got = assessment_anchor(s, as_of).curr_batch_id == b.id
            flags.append("Y" if got else "n")
            if got and first is None:
                first = as_of
    eng.dispose()
    return flags, first


print("=== daily.py:206-212 的两行逐日输出（docstring 印的值 vs 本轮实测）===")
for td, claimed in ((dt.date(2025, 9, 1), "YYYYY / 首次 09-01"),
                    (dt.date(2025, 9, 5), "nnnnY / 首次 09-05")):
    flags, first = run(td)
    print("  test_date=%s  %s  -> 首次被选中 as_of=%s   | docstring: %s" % (
        td.isoformat(), " ".join("%s=%s" % (d.strftime("%m-%d"), f) for d, f in zip(DAYS, flags)),
        first.isoformat() if first else None, claimed))

print("\n=== config.py:43 —— MockLePaoAdapter() 无参调用 ===")
from app.adapters.mock_lepao import MockLePaoAdapter
try:
    MockLePaoAdapter()
    print("  竟然成功（与 docstring 相反！）")
except TypeError as e:
    print("  TypeError:", e)

print("\n=== test_config.py 的两条断言（字面量口径）===")
print("  DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() = %r  == 'data/seed' -> %s" % (
    DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix(),
    DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() == "data/seed"))
print("  DEFAULT_DB_URL = %r  endswith('/backend/pe.db') -> %s" % (
    DEFAULT_DB_URL, DEFAULT_DB_URL.endswith("/backend/pe.db")))

print("\n=== config.py:31-32 —— generate.py 里的 parents[2] 是否等价 ===")
g = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\app\seed\generate.py")
print("  generate.py 存在:", g.exists())
if g.exists():
    print("  generate.py.resolve().parents[2] = %s" % g.resolve().parents[2])
print("  BACKEND_DIR                      = %s" % BACKEND_DIR)
print("  等价 ->", g.exists() and g.resolve().parents[2] == BACKEND_DIR)

print("\n=== 禁区快照 ===")
print("  backend/pe.db 存在:", (BACKEND_DIR / "pe.db").exists())
print("  backend/data/seed 文件数:", len(list((BACKEND_DIR / "data" / "seed").glob("*")))
      if (BACKEND_DIR / "data" / "seed").exists() else "目录不存在")
