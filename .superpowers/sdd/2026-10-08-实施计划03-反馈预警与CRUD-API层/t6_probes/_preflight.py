"""Plan 03 Task 6 预检（一份探针）：domain/alerts.py + alert_rules.yaml 要照的既有形状。
⚠️ 硬规矩 #108：探针写完先 py_compile 一次（架构守卫会 AST 解析工作树里的全部 .py）。
"""
import ast
import dataclasses
import inspect
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))

print("### A. app/domain/ 的布局（alerts.py 要放哪、扫描面会怎么变）")
dom = BACKEND / "app" / "domain"
for p in sorted(dom.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    print(f"  {p.relative_to(BACKEND).as_posix():44s} {p.stat().st_size:7d} B")
print(f"  app/domain 下 .py 数 = {len([p for p in dom.rglob('*.py') if '__pycache__' not in p.parts])}")
print(f"  ⚠️ 计划说 alerts.py 放 app/domain/ 顶层（不进 prescription/ 子包）——核实顶层今天有哪些模块")

print()
print("### B. 两份架构守卫的下界断言（S6 说 Task 1 已抬到位、后面不再动）")
for name in ("test_domain_purity.py", "test_layering.py"):
    p = BACKEND / "tests" / "architecture" / name
    s = p.read_text(encoding="utf-8")
    print(f"  --- {name} ({len(s.encode('utf-8'))} B / {s.count(chr(10))} 行)")
    for i, l in enumerate(s.split("\n")):
        if re.search(r">=\s*\d+|len\(.*\)\s*>=|ALLOWED_MODULES|SCANNED_DIRS|_API_ALLOWED", l):
            print(f"    :{i+1} {l.strip()[:125]}")

print()
print("### C. ALLOWED_MODULES 里有没有 alerts.py 要用的东西")
from tests.architecture.test_domain_purity import ALLOWED_MODULES  # noqa: E402
print(f"  ALLOWED_MODULES = {sorted(ALLOWED_MODULES)}")
for want in ("dataclasses", "enum", "collections.abc", "typing", "collections"):
    print(f"    {want:18s} 在? {want in ALLOWED_MODULES}")

print()
print("### D. refdata_prescription.py 的公开面（refdata_alerts.py 要照它的形状）")
import app.refdata_prescription as RP  # noqa: E402
print(f"  __all__ = {getattr(RP, '__all__', '（无）')}")
for n in sorted(dir(RP)):
    if n.startswith("__"):
        continue
    o = getattr(RP, n)
    if callable(o) and getattr(o, "__module__", "") == RP.__name__:
        try:
            print(f"  def {n}{inspect.signature(o)}")
        except (TypeError, ValueError):
            print(f"  {n}（签名取不到）")
src = (BACKEND / "app" / "refdata_prescription.py").read_text(encoding="utf-8")
print(f"  refdata_prescription.py {len(src.encode('utf-8'))} B / {src.count(chr(10))} 行")
for helper in ("_line_index", "_fail", "_exact_keys", "_load_yaml", "DATA_DIR"):
    print(f"    {helper:16s} 命中 {src.count(helper)}")

print()
print("### E. 公有面基线守卫的形状（Task 6 要给 app.domain.alerts 建一份同样的）")
tr = (BACKEND / "tests" / "test_refdata_prescription.py").read_text(encoding="utf-8")
print(f"  test_refdata_prescription.py {len(tr.encode('utf-8'))} B / {tr.count(chr(10))} 行")
i = tr.index("_PRESCRIPTION_PUBLIC_BASELINE")
print("  " + tr[i - 300:i + 1600].replace("\n", "\n  ")[:2000])

print()
print("### F. 指纹测试的形状（alert_rules.yaml 要加一条同样的）")
for m in re.finditer(r"^(FINGERPRINT|EXERCISES_FINGERPRINT|EQUIVALENCE_FINGERPRINT|[A-Z_]*FINGERPRINT)\s*=\s*(.+)$", tr, re.M):
    print(f"  {m.group(1)} = {m.group(2)[:60]}")
i = tr.index("def _fingerprint") if "def _fingerprint" in tr else tr.index("sha256")
print("  " + tr[max(0, i - 200):i + 700].replace("\n", "\n  ")[:900])

print()
print("### G. RPE 值域的今天住址（单一所有者：alerts.py 的阈值不能与它冲突）")
from app.db.models.feedback import RpeRecord  # noqa: E402
print(f"  RpeRecord.RPE_MIN / RPE_MAX = {RpeRecord.RPE_MIN} / {RpeRecord.RPE_MAX}")
ck = [c for c in RpeRecord.__table__.constraints if type(c).__name__ == "CheckConstraint"]
for c in ck:
    print(f"  CHECK {c.name} = {c.sqltext}")
print(f"  ⚠️ spec §8.2 的 RED_RPE_SUSTAINED 是「连续 >= 9」、YELLOW_CLASS_RPE_HIGH 是「均值 > 7」——都落在 [0,10] 内 ✅")

print()
print("### H. domain/prescription/__init__.py 的重导出形状（alerts.py 若建 __init__ 要照它）")
pi = (BACKEND / "app" / "domain" / "prescription" / "__init__.py").read_text(encoding="utf-8")
print(f"  {len(pi.encode('utf-8'))} B / {pi.count(chr(10))} 行")
i = pi.index("__all__")
print("  " + pi[i - 100:i + 1500].replace("\n", "\n  ")[:1700])

print()
print("### I. MiniTest / TrainingLog 的列（预警规则的输入从哪来）")
from app.db.models.feedback import MiniTest, TrainingLog, Alert  # noqa: E402
for cls in (MiniTest, TrainingLog, Alert):
    print(f"  {cls.__tablename__}: {[c.name for c in cls.__table__.columns]}")
print(f"  Alert.LEVELS = {getattr(Alert, 'LEVELS', None)}")
print(f"  Alert.STATUSES = {getattr(Alert, 'STATUSES', None)}")
print(f"  Alert 的其它类常量 = {[n for n in dir(Alert) if n.isupper()]}")

print()
print("### J. 现有 domain 模块的「值类型住 domain、加载器住 domain 外」先例（Ruling 96）")
for m in ("app.domain.indicators", "app.domain.prescription.exercises", "app.domain.stratify"):
    mod = __import__(m, fromlist=["x"])
    names = [n for n in getattr(mod, "__all__", [])]
    print(f"  {m:38s} __all__ = {len(names)} 个")
