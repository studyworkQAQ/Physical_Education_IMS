"""F1-2：量 test_backfill_500_students_under_60_seconds 断言的那个 `elapsed`（n 次，无 trace 钩子）。

夹具形状逐字复刻 tests/pipeline/test_backfill.py 的 `seed_dir` + `replay`
（CFG=500 人 / seed=20250828 / START..END = 2025-09-01..2025-12-21 / 独立 sqlite 文件）。
`elapsed` 就是被 `assert elapsed < 60` 断言的那一个量（time.perf_counter 之差）。
用法：python _t7f1_backfill.py [n]   （缺省 n=3）
"""
import pathlib
import shutil
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

assert sys.gettrace() is None, "本探针必须在没有 trace 钩子（coverage / debugger）下跑"

from sqlalchemy import create_engine, select               # noqa: E402
from app.adapters.mock_lepao import MockLePaoAdapter       # noqa: E402
from app.db import models as M                             # noqa: E402
from app.db.session import Session, init_db                # noqa: E402
from app.pipeline.backfill import run_backfill             # noqa: E402
from app.seed.config import SeedConfig                     # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402

CFG = SeedConfig(students=500, weeks=16, seed=20250828)
SEMESTER_NAME = "2025-2026-1"          # Ruling 173：按名字取，不取「第一条」
START, END = "2025-09-01", "2025-12-21"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3

dataset = build_dataset(CFG)
values = []
for i in range(N):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"t7f1bf{i}_"))
    try:
        d = tmp / "lepao"
        write_csv(dataset, d)
        eng = create_engine(f"sqlite:///{tmp / 'replay.db'}")
        init_db(eng)
        with Session(eng) as s:
            seed_database(s, CFG)
            sem = s.scalar(select(M.Semester.id).where(M.Semester.name == SEMESTER_NAME))
            t0 = time.perf_counter()
            runs = run_backfill(s, sem, START, END, MockLePaoAdapter(d))
            elapsed = time.perf_counter() - t0
            assert len(runs) == 112, len(runs)
            values.append(elapsed)
            print(f"  run {i + 1}: elapsed = {elapsed:.2f} s   "
                  f"余量 60 / {elapsed:.2f} = {60 / elapsed:.2f}x", flush=True)
        eng.dispose()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print()
print(f"n={len(values)}  min={min(values):.2f}  max={max(values):.2f}")
print(f"最小余量 = 60 / {max(values):.2f} = {60 / max(values):.2f}x")
