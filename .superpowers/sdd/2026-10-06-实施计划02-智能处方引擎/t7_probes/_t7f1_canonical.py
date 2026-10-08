"""F1-1 连带：重测 canonical sha256（9 张 / 11 张）与行数合计。

``canonical_dump`` **逐字复用** ``tests/pipeline/test_daily.py`` 的那一个（import 它，
不复制），9 张那一档用临时替换模块级 ``PIPELINE_TABLES`` 得到。夹具形状逐字复刻
``test_rerunning_the_same_business_date_reproduces_every_table``（60 人 / seed=20250828 /
缺省注入 / D = 2025-09-15）。跑**两遍** run_daily，断言两遍哈希逐字相同。
"""
import importlib.util
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

spec = importlib.util.spec_from_file_location(
    "td", BACKEND / "tests" / "pipeline" / "test_daily.py"
)
TD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TD)

from sqlalchemy import create_engine, select                     # noqa: E402
from app.adapters.mock_lepao import MockLePaoAdapter             # noqa: E402
from app.db.session import Session, init_db                      # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402

ELEVEN = tuple(TD.PIPELINE_TABLES)
NINE = tuple(t for t in ELEVEN if t not in ("prescription", "weekly_adjustment"))
assert len(ELEVEN) == 11 and len(NINE) == 9, (len(ELEVEN), len(NINE))
assert TD.D == "2025-09-15" and TD.CFG.students == 60 and TD.CFG.seed == 20250828

tmp = pathlib.Path(tempfile.mkdtemp(prefix="t7f1canon_"))
try:
    d = tmp / "lepao"
    write_csv(build_dataset(TD.CFG), d)
    eng = create_engine(f"sqlite:///{tmp / 't.db'}")
    init_db(eng)
    with Session(eng) as s:
        seed_database(s, TD.CFG)
        sem = TD.semester_id(s)
        adapter = MockLePaoAdapter(d)

        s.execute  # noqa: B018 - 只是让 linter 看见 s 被用到
        TD.run_daily(s, sem, TD.D, adapter)
        TD.PIPELINE_TABLES = ELEVEN
        h11_first, r11_first = TD.canonical_dump(s)
        TD.PIPELINE_TABLES = NINE
        h9_first, r9_first = TD.canonical_dump(s)

        TD.run_daily(s, sem, TD.D, adapter)
        TD.PIPELINE_TABLES = ELEVEN
        h11_second, r11_second = TD.canonical_dump(s)
        TD.PIPELINE_TABLES = NINE
        h9_second, r9_second = TD.canonical_dump(s)

        assert (h11_first, r11_first) == (h11_second, r11_second), "11 张两遍不同！"
        assert (h9_first, r9_first) == (h9_second, r9_second), "9 张两遍不同！"

        print("=== 两遍 run_daily 之后（first == second 成立）===")
        print(f"  9 张（Plan 01）  {h9_first}   行数合计 {sum(r9_first.values())}")
        print(f"  11 张（Task 7）  {h11_first}   行数合计 {sum(r11_first.values())}")
        print()
        print("  逐表行数（11 张）:")
        for name in ELEVEN:
            print(f"    {name:24s} {r11_first[name]:5d}")
        print()
        print("  旧值（Task 7 首轮报告，供对照）:")
        print("    9 张  1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952   882")
        print("    11 张 05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816   942")
        print()
        print(f"  9 张是否变了? {h9_first != '1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952'}"
              f"   11 张是否变了? "
              f"{h11_first != '05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816'}")
        # 处方行上 label_at_generation 的实测分布（确认它真的被填了）
        from app.db.models.prescription import Prescription
        from sqlalchemy import func as _func
        dist = dict(s.execute(
            select(Prescription.label_at_generation, _func.count())
            .group_by(Prescription.label_at_generation)
        ).all())
        print(f"  prescription.label_at_generation 分布 = {dist}")
        print(f"  prescription 列数 = {len(list(Prescription.__table__.columns))}")
        print(f"  prescription 列名 = {[c.name for c in Prescription.__table__.columns]}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
