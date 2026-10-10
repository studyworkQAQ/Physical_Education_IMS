"""Task 7 探针 1：在 HEAD (6d0c8d2) 上实测派单点名的每一个既有常量的当前值。

全部用运行时口径（硬规矩 #89/#111）。不写任何文件、不碰数据库。
"""
import hashlib
import pathlib
import sys

sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
APP = BACKEND / "app"

print("=== 1. refdata_alerts 的公开面（dir 口径：不以 _ 开头的顶层名）===")
import app.refdata_alerts as ra  # noqa: E402

public = sorted(n for n in dir(ra) if not n.startswith("_") and n not in {
    "pathlib", "types", "yaml", "refdata_yaml", "AlertLevel", "AlertRule",
    "AlertRules", "AlertScope", "RuleId", "declared_scope", "DATA_DIR",
})
print("  本模块自己定义/导出的公开名:", public)
import ast as _ast  # noqa: E402

tree = _ast.parse((APP / "refdata_alerts.py").read_text(encoding="utf-8"))
own = sorted(
    n.name for n in tree.body
    if isinstance(n, (_ast.FunctionDef, _ast.ClassDef)) and not n.name.startswith("_")
)
own_assign = sorted(
    t.id for n in tree.body if isinstance(n, _ast.Assign)
    for t in n.targets if isinstance(t, _ast.Name) and not t.id.startswith("_")
)
print("  AST 口径 顶层公开 def/class:", own)
print("  AST 口径 顶层公开赋值:", own_assign)
print("  有没有 __all__:", hasattr(ra, "__all__"))
print("  alert_rules() 的 version:", ra.alert_rules().version)

print()
print("=== 2. _replay_cleanup 的清单（AST 口径：那个元组有几项）===")
src = (APP / "pipeline" / "daily.py").read_text(encoding="utf-8")
dtree = _ast.parse(src)
fn = next(n for n in _ast.walk(dtree)
          if isinstance(n, _ast.FunctionDef) and n.name == "_replay_cleanup")
loop = next(n for n in _ast.walk(fn) if isinstance(n, _ast.For))
tup = loop.iter
names = []
for elt in tup.elts:
    if isinstance(elt, _ast.Attribute):
        names.append(f"{_ast.unparse(elt.value)}.{elt.attr}")
    else:
        names.append(_ast.unparse(elt))
print("  元组项数 =", len(names), "顺序 =", names)

print()
print("=== 3. 扫描面（SCANNED_DIRS 四个目录各几个 .py）===")
from tests.architecture.test_layering import SCANNED_DIRS  # noqa: E402

total = 0
for rel in SCANNED_DIRS:
    n = len(sorted((APP / rel).rglob("*.py")))
    total += n
    print(f"  {rel}: {n}")
print("  合计 =", total)
print("  app/ 根下的 .py:", sorted(p.name for p in APP.glob("*.py")))

print()
print("=== 4. 表数 / _MODELS_PUBLIC_BASELINE / 端点数 ===")
from app.db import models as M  # noqa: E402
from app.db.session import Base  # noqa: E402

print("  Base.metadata.tables =", len(Base.metadata.tables))
tmod = _ast.parse((BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8"))
for node in tmod.body:
    if isinstance(node, _ast.Assign) and any(
        isinstance(t, _ast.Name) and t.id == "_MODELS_PUBLIC_BASELINE" for t in node.targets
    ):
        print("  _MODELS_PUBLIC_BASELINE 项数 =", len(node.value.elts))

from app.main import create_app  # noqa: E402

application = create_app(db_url="sqlite://")
paths = {r.path for r in application.routes if hasattr(r, "methods")}
ops = sum(len(r.methods - {"HEAD", "OPTIONS"}) for r in application.routes
          if hasattr(r, "methods"))
print("  distinct 路径数 =", len(paths))
print("  操作数（method × path，去掉 HEAD/OPTIONS）=", ops)

print()
print("=== 5. 四个指纹（sha256 前 16 位，行尾归一化为 LF）===")
data_dir = BACKEND / "data"


def fp(path: pathlib.Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:16].upper()


CRLF = b"\r\n"
for p in sorted(data_dir.rglob("*.yaml")):
    raw = p.read_bytes()
    n_crlf = raw.count(CRLF)
    print(f"  {p.relative_to(BACKEND).as_posix()}: {fp(p)} "
          f"bytes={len(raw)} crlf={n_crlf}")
csvs = sorted(data_dir.rglob("*.csv"))
print("  csv 文件数 =", len(csvs))
for p in csvs:
    print(f"    {p.relative_to(BACKEND).as_posix()}: {fp(p)} bytes={len(p.read_bytes())}")
print("  data/seed 下的文件数 =",
      len(list((data_dir / "seed").rglob("*"))) if (data_dir / "seed").exists() else "ABSENT")

print()
print("=== 6. 禁区 ===")
print("  backend/pe.db 存在:", (BACKEND / "pe.db").exists())
print("  backend/pe_demo.db 存在:", (BACKEND / "pe_demo.db").exists())

print()
print("=== 7. notification / alert / weekly_adjustment 的运行时列数与 CHECK ===")
from app.db.models.feedback import Alert, Notification  # noqa: E402
from app.db.models.prescription import WeeklyAdjustment  # noqa: E402

for model in (Alert, Notification, WeeklyAdjustment):
    cols = list(model.__table__.columns)
    print(f"  {model.__tablename__}: {len(cols)} 列 = {[c.name for c in cols]}")
    for c in model.__table__.constraints:
        print("     constraint:", type(c).__name__, getattr(c, "name", None))
print("  Notification.CHANNELS =", sorted(Notification.CHANNELS))
print("  Notification.RECIPIENT_KINDS =", sorted(Notification.RECIPIENT_KINDS))
print("  WeeklyAdjustment.SOURCES =", sorted(WeeklyAdjustment.SOURCES))
print("  Alert.LEVELS =", sorted(Alert.LEVELS), " STATUSES =", sorted(Alert.STATUSES))

print()
print("=== 8. StudentSignals / ClassSignals / StudentHit 的字段（运行时口径）===")
import dataclasses  # noqa: E402

from app.domain.alerts import (  # noqa: E402
    SUBJECT_PREFIX_SECTION,
    SUBJECT_PREFIX_STUDENT,
    ClassHit,
    ClassSignals,
    StudentHit,
    StudentSignals,
)

for cls in (StudentSignals, ClassSignals, StudentHit, ClassHit):
    fs = dataclasses.fields(cls)
    print(f"  {cls.__name__}: {len(fs)} 字段 = {[f.name for f in fs]}")
print("  SUBJECT_PREFIX_STUDENT =", repr(SUBJECT_PREFIX_STUDENT),
      " SUBJECT_PREFIX_SECTION =", repr(SUBJECT_PREFIX_SECTION))

print()
print("=== 9. _training_days_of 的住址与依赖 ===")
fb = (APP / "api" / "routers" / "feedback.py").read_text(encoding="utf-8")
ftree = _ast.parse(fb)
fndef = next(n for n in _ast.walk(ftree)
             if isinstance(n, _ast.FunctionDef) and n.name == "_training_days_of")
print("  在 app/api/routers/feedback.py 的第", fndef.lineno, "行")
print("  它引用的名字:", sorted({n.id for n in _ast.walk(fndef) if isinstance(n, _ast.Name)}))
callers = []
for p in sorted(BACKEND.rglob("*.py")):
    txt = p.read_text(encoding="utf-8")
    if "_training_days_of" in txt:
        callers.append(p.relative_to(BACKEND).as_posix())
print("  提到它的文件:", callers)
print("  DAYS_PER_WEEK 的住址:")
for p in sorted(APP.rglob("*.py")):
    for node in _ast.walk(_ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(node, _ast.Assign) and any(
            isinstance(t, _ast.Name) and t.id == "DAYS_PER_WEEK" for t in node.targets
        ):
            print("   ", p.relative_to(BACKEND).as_posix(), node.lineno, _ast.unparse(node))
        if isinstance(node, _ast.ImportFrom):
            for a in node.names:
                if a.name == "DAYS_PER_WEEK":
                    print("    import from", node.module, "in",
                          p.relative_to(BACKEND).as_posix(), node.lineno)
