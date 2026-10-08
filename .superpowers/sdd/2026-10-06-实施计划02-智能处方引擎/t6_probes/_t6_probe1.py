"""Task 6 预检 probe 1：DB 层既有形状 + 计划 Task 6 的每一条断言逐个实测。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. app/db 的文件与大小")
for p in sorted((BACKEND / "app" / "db").rglob("*.py")):
    print(f"  {p.relative_to(BACKEND).as_posix():42s} {p.stat().st_size:7d} B")

print()
print("### B. models/prescription.py 的类与列（Task 6 要往这里加两张表）")
src = (BACKEND / "app" / "db" / "models" / "prescription.py").read_text(encoding="utf-8")
print(f"  ({len(src.encode('utf-8'))} B / {src.count(chr(10))} lf)")
tree = ast.parse(src)
for n in tree.body:
    if isinstance(n, ast.ClassDef):
        print(f"  class {n.name}({', '.join(ast.unparse(b) for b in n.bases)})")
        for s in n.body:
            if isinstance(s, ast.Assign):
                for tg in s.targets:
                    if isinstance(tg, ast.Name):
                        print(f"      {tg.id:22s} = {ast.unparse(s.value)[:120]}")
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                v = f" = {ast.unparse(s.value)}" if s.value is not None else ""
                print(f"      {s.target.id:22s}: {ast.unparse(s.annotation)}{v}"[:150])

print()
print("### C. prescription_template 表有没有 microcycle_weeks / weekly_frequency 列")
print("    （触发 3 要「上一张处方的模板的 microcycle_weeks」，若两表都不存，Task 6/7 算不出来）")
from app.db import models as M  # noqa: E402
for cls_name in ("PrescriptionTemplate", "Exercise"):
    cls = getattr(M, cls_name, None)
    if cls is None:
        print(f"  {cls_name}: 不存在")
        continue
    cols = [c.name for c in cls.__table__.columns]
    print(f"  {cls_name} ({cls.__tablename__}) 列 = {cols}")

print()
print("### D. 全部 16 张表 + 每张表的列数（Task 6 后应为 18）")
for name in sorted(M.Base.metadata.tables):
    t = M.Base.metadata.tables[name]
    print(f"  {name:26s} 列数={len(t.columns):2d}  "
          f"约束={[type(c).__name__ for c in t.constraints if type(c).__name__ != 'PrimaryKeyConstraint']}")

print()
print("### E. JsonText 与 _in_domain 的住址与签名")
for p in sorted((BACKEND / "app" / "db").rglob("*.py")):
    s = p.read_text(encoding="utf-8")
    for m in re.finditer(r"^(class JsonText.*|def _in_domain.*)$", s, re.M):
        print(f"  {p.relative_to(BACKEND).as_posix()}: {m.group(0)[:110]}")

print()
print("### F. test_models.py 里所有钉住表数 / 公开面大小的断言")
tm = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
L = tm.split("\n")
for i, l in enumerate(L):
    if re.search(r"== 16|==\s*33|sixteen|len\(tables\)|_MODELS_PUBLIC_BASELINE\)|def test_all_", l):
        print(f"  :{i+1} {l.strip()[:150]}")

print()
print("### G. tests/seed/test_generate.py 的分区穷尽守卫")
sg = (BACKEND / "tests" / "seed" / "test_generate.py").read_text(encoding="utf-8")
for m in re.finditer(r"^(ORGANISATION_TABLES|DATA_TABLES|REFERENCE_TABLES)\s*=\s*\(?[^)]*\)?", sg, re.M | re.S):
    print("  " + m.group(0).replace("\n", "\n  ")[:500])
for i, l in enumerate(sg.split("\n")):
    if "Base.metadata.tables" in l:
        print(f"  :{i+1} {l.strip()[:160]}")

print()
print("### H. Plan 01 的分层标签实际取值（'insufficient_data' 是不是字面串）")
from app.domain.stratify import Layer  # noqa: E402
print(f"  Layer 成员 = {[(m.name, m.value) for m in Layer]}")
st = (BACKEND / "app" / "domain" / "stratify.py").read_text(encoding="utf-8")
for i, l in enumerate(st.split("\n")):
    if "insufficient" in l.lower():
        print(f"  stratify.py:{i+1} {l.strip()[:130]}")

print()
print("### I. repo.upsert 的签名（Task 7 会用，Task 6 的表要能被它 upsert）")
rp = (BACKEND / "app" / "db" / "repo.py").read_text(encoding="utf-8")
for m in re.finditer(r"^def (\w+)\(([^)]*)\)", rp, re.M):
    print(f"  def {m.group(1)}({m.group(2).strip()[:100]})")

print()
print("### J. daily_sync_run 的列（batch_id 外键的目标）+ _replay_cleanup 的清单")
dsr = getattr(M, "DailySyncRun", None)
if dsr is not None:
    print(f"  daily_sync_run 列 = {[c.name for c in dsr.__table__.columns]}")
for p in sorted((BACKEND / "app" / "pipeline").rglob("*.py")):
    s = p.read_text(encoding="utf-8")
    if "_replay_cleanup" in s:
        i = s.index("_replay_cleanup")
        print(f"  {p.relative_to(BACKEND).as_posix()} 里 _replay_cleanup 附近：")
        seg = s[i:i + 900]
        print("    " + seg.replace("\n", "\n    ")[:900])
        break

print()
print("### K. StratificationResult 的列（Task 6 的 LastPrescription.label_at_generation 来源）")
sr = getattr(M, "StratificationResult", None)
if sr is not None:
    print(f"  stratification_result 列 = {[c.name for c in sr.__table__.columns]}")
