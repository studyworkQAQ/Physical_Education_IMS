"""P3 — Minor 4：EXPLAIN QUERY PLAN 的 detail 全串到底长什么样（A / B 两个场景）。
P4 — Minor 5：daily.py:226/:228 两个「均值」是不是截断值。"""
import datetime as dt
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import Index, create_engine, text  # noqa: E402
from app.db import models as M  # noqa: E402
from app.db.session import init_db  # noqa: E402

Q = ("select id from stratification_result where student_id = :sid "
     "order by computed_on desc limit 1")

print("=== P3: EXPLAIN QUERY PLAN 的整行（4 列全打，不只 detail）===")
tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr5_plan_"))
for tag, extra in (("A 仅 UniqueConstraint 的自动索引", False),
                   ("B A + 显式 Index(student_id, computed_on)", True)):
    dbfile = tmp / (tag[0] + ".db")
    eng = create_engine("sqlite:///" + dbfile.as_posix())
    init_db(eng)
    if extra:
        Index("ix_stratification_result_student_computed",
              M.StratificationResult.student_id,
              M.StratificationResult.computed_on).create(eng)
    with eng.connect() as c:
        rows = c.execute(text("explain query plan " + Q.replace(":sid", "1"))).all()
    print(" 场景 %s" % tag)
    for r in rows:
        print("   整行 = %r" % (tuple(r),))
        print("   detail(r[3]) = %r" % (r[3],))
        print("   detail 是否以 'SEARCH stratification_result ' 开头 = %s"
              % str(r[3]).startswith("SEARCH stratification_result "))
        print("   detail 里是否含 'USING COVERING INDEX' = %s"
              % ("USING COVERING INDEX" in str(r[3])))
    eng.dispose()

print()
print("=== P4: daily.py:226/:228 两个「均值」===")
base = (20.48, 20.85)
after = (20.89, 21.18)
for label, xs, printed in (("基线", base, 20.66), ("本 Task 之后", after, 21.03)):
    mean = (xs[0] + xs[1]) / 2
    print(" %s 样本 %s" % (label, xs))
    print("   真均值            = %r" % mean)
    print("   round(mean, 2)    = %r" % round(mean, 2))
    print("   源码印的值        = %r" % printed)
    print("   int(mean*100)/100 = %r   （截断到百分位）" % (int(mean * 100) / 100))
    print("   '%.2f' 格式化     = %r" % ("%.2f" % mean, "%.2f" % mean))
    print("   源码值 == round()? %s ; 源码值 == 截断? %s"
          % (printed == round(mean, 2), printed == int(mean * 100) / 100))
    print("   组内极差 = %.2f - %.2f = %r" % (max(xs), min(xs), max(xs) - min(xs)))

d = ((after[0] + after[1]) / 2) - ((base[0] + base[1]) / 2)
print()
print(" 差 = %r  -> 源码印 +0.37 s ; 一致? %s" % (d, round(d, 2) == 0.37))
print(" 百分比 = %r%% -> 源码印 +1.8%% ; 一致? %s"
      % (d / ((base[0] + base[1]) / 2) * 100,
         round(d / ((base[0] + base[1]) / 2) * 100, 1) == 1.8))
print(" 60 / 21.18 = %r -> 源码印 2.83x ; 一致? %s"
      % (60 / 21.18, round(60 / 21.18, 2) == 2.83))
print(" round(21.035, 2) = %r  （派单说 round() 是 21.04）" % round(21.035, 2))
print(" round(20.665, 2) = %r" % round(20.665, 2))
import shutil
shutil.rmtree(tmp, ignore_errors=True)
print(" temp dir removed:", not tmp.exists())
