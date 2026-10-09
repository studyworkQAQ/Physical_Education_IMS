"""Plan 03 Task 2 亲验 + 结案：先验，验不过就不写账本。"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. 表数 / 公有面 / 扫描面（运行时口径）")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面（Ruling 97）", len(obs - subs), 33)
new7 = {"ClassSession", "RpeRecord", "TrainingLog", "MiniTest", "Alert", "Notification", "WeeklyClassReport"}
chk("7 个新类名进了公有面?", len((obs - subs) & new7), 0)
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api"))
chk("扫描面", tot, 38)

print("\n### 2. 7 张新表的列数与约束（P3-A1：全在 feedback.py）")
for name, want_cols in (("class_session", 7), ("rpe_record", 6), ("training_log", 10),
                        ("mini_test", 10), ("alert", 14), ("notification", 10),
                        ("weekly_class_report", 12)):
    t = M.Base.metadata.tables[name]
    chk(f"{name} 列数", len(t.columns), want_cols)
    cks = sorted(c.name for c in t.constraints if type(c).__name__ == "CheckConstraint")
    uqs = sorted(c.name for c in t.constraints if type(c).__name__ == "UniqueConstraint")
    print(f"      CHECK={cks}")
    print(f"      UNIQUE={uqs}")

print("\n### 3. 顶回 1 的替代设计：alert 的 subject_key（哨兵 0 方案已被否）")
al = M.Base.metadata.tables["alert"]
cols = {c.name: (str(c.type), c.nullable) for c in al.columns}
for c in ("student_id", "course_section_id", "subject_key", "window_key", "semester_id"):
    print(f"  {c:22s} {cols.get(c, '（不存在）')}")
print(f"  student_id 是外键? {bool(al.c.student_id.foreign_keys)}")
print(f"  course_section_id 是外键? {bool(al.c.course_section_id.foreign_keys)}")

print("\n### 4. weekly_adjustment 的新唯一约束（S2 / P3-A4）")
wa = M.Base.metadata.tables["weekly_adjustment"]
uqs = [(c.name, [x.name for x in c.columns]) for c in wa.constraints
       if type(c).__name__ == "UniqueConstraint"]
print(f"  UNIQUE = {uqs}")
chk("weekly_adjustment 列数（应仍是 8，本 Task 不加列）", len(wa.columns), 8)

print("\n### 5. notification 的两个 ondelete（顶回 3）")
nt = M.Base.metadata.tables["notification"]
for fk in [c for c in nt.constraints if type(c).__name__ == "ForeignKeyConstraint"]:
    for el in fk.elements:
        print(f"  {el.parent.name} -> {el.column.table.name}.{el.column.name}  ondelete={fk.ondelete!r}")

print("\n### 6. ops.py 是否一个字节没改（P3-A1）")
r = subprocess.run(["git", "diff", "--stat", "bcf3936", "HEAD", "--", "backend/app/db/models/ops.py"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff --stat ops.py -> {(r.stdout or '').strip() or '（空 = 一个字节没改）✅'}")

print("\n### 7. 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    chk(rel, got, want)
    print(f"      {len(b)} B  CRLF={b.count(bytes([13,10]))}")
r = subprocess.run(["git", "diff", "--stat", "bcf3936", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)
chk("data/seed 文件数", len(list((BACKEND / "data" / "seed").rglob("*")))
    if (BACKEND / "data" / "seed").exists() else -1, 0)

print("\n### 8. feedback.py 的行尾口径（P3-A6）与 docstring 是否重写了")
fb = (BACKEND / "app" / "db" / "models" / "feedback.py").read_bytes()
print(f"  {len(fb)} B  CRLF={fb.count(bytes([13,10]))}  LF={fb.count(bytes([10]))}  "
      f"-> {'纯 CRLF' if fb.count(bytes([10])) == fb.count(bytes([13,10])) else ('纯 LF' if fb.count(bytes([13,10])) == 0 else '混杂')}")
txt = fb.decode("utf-8")
print(f"  仍写「本模块今天刻意是空的」? {'本模块今天刻意是空的' in txt}  <- 应 False")
print(f"  写了星号导入的理由? {'import *' in txt or '星号' in txt}  <- 应 True")

print("\n### 9. pe_demo.db 是陈旧的（待清扫第 2 条）")
pd_ = BACKEND / "pe_demo.db"
if pd_.exists():
    import sqlite3
    con = sqlite3.connect(str(pd_))
    n = con.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]
    con.close()
    print(f"  pe_demo.db {pd_.stat().st_size} B，表数 = {n}  <- 陈旧（应 25），控制者本轮删掉重建")
else:
    print("  pe_demo.db 不存在")

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项'} =====")
