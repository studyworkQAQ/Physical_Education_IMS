"""T8 探针 1：把派单里每一条「既有常量的当前值」在**当前 HEAD** 上实测一次（硬规矩 #111）。

运行：cd backend; python ..\\.superpowers\\sdd\\...\\t8_probes\\p1_baseline.py
口径：一律运行时（AST / len() / import），绝不用正则数源码（硬规矩 #89）。
"""
import ast
import hashlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve()
# t8_probes -> <plan dir> -> sdd -> .superpowers -> repo root -> backend
ROOT = BACKEND.parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("=" * 72)
print("[1] 仓库根 =", ROOT)
print("    backend =", BACKEND, "exists:", BACKEND.is_dir())

# --- 2. _replay_cleanup 的清单（AST 口径，P8-A1）--------------------------
daily_py = BACKEND / "app" / "pipeline" / "daily.py"
tree = ast.parse(daily_py.read_text(encoding="utf-8"))
found = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_replay_cleanup":
        found = node
assert found is not None, "_replay_cleanup 没找到"
names = []
for sub in ast.walk(found):
    if isinstance(sub, ast.For):
        # for model in ( ... ):
        if isinstance(sub.iter, ast.Tuple):
            for elt in sub.iter.elts:
                if isinstance(elt, ast.Attribute):
                    names.append(ast.unparse(elt))
                elif isinstance(elt, ast.Name):
                    names.append(elt.id)
print("\n[2] _replay_cleanup 清单（AST 口径）=", names)
print("    长度 =", len(names))
print("    带 models. 前缀的 =", [n for n in names if n.startswith("models.")])
print("    裸名 =", [n for n in names if not n.startswith("models.")])

# --- 3. 两种写法在函数体里都能解析吗（P8-A1 的后半）------------------------
print("\n[3] _replay_cleanup 的函数体里，模型名怎么解析？")
print("    函数体源码（去掉 docstring 之后的语句）:")
body = found.body
for stmt in body:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        continue
    print("      ", ast.unparse(stmt)[:160])
imports_at_top = {}
for node in tree.body:
    if isinstance(node, ast.ImportFrom):
        for a in node.names:
            imports_at_top[a.asname or a.name] = node.module
    elif isinstance(node, ast.Import):
        for a in node.names:
            imports_at_top[a.asname or a.name] = a.name
for n in names:
    head = n.split(".")[0]
    print(f"      {n:38s} <- 顶层绑定 {head!r} = {imports_at_top.get(head)!r}")

# --- 4. 表数 / _MODELS_PUBLIC_BASELINE / 扫描面 / 端点数 ------------------
from app.db.session import Base  # noqa: E402
import app.db.models  # noqa: E402,F401  触发全部子模块导入

print("\n[4] 表数（Base.metadata）=", len(Base.metadata.tables))

tst = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
ttree = ast.parse(tst)
baseline = None
for node in ttree.body:
    if isinstance(node, ast.Assign):
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "_MODELS_PUBLIC_BASELINE":
                baseline = [e.value for e in node.value.elts]
print("    _MODELS_PUBLIC_BASELINE 长度 =", len(baseline))
import app.db.models as M  # noqa: E402
public = [n for n in dir(M) if not n.startswith("_")]
print("    app.db.models 实际公有名（去子模块）=",
      len([n for n in public if n not in ("feedback", "prescription", "derived",
                                          "organisation", "ops", "_shared")]))

# 扫描面：test_layering 的 SCANNED_DIRS 实扫
SCANNED = ("pipeline", "db", "domain", "api")
total = 0
per = {}
for d in SCANNED:
    files = sorted((BACKEND / "app" / d).rglob("*.py"))
    per[d] = len(files)
    total += len(files)
print("\n[5] 扫描面（SCANNED_DIRS 实扫）=", per, "合计 =", total)

# 端点数：app.openapi()["paths"]（⚠️ 不是 len(app.routes)，include_router 是惰性的）
from app.main import create_app  # noqa: E402
app_obj = create_app(db_url="sqlite://")
paths = app_obj.openapi()["paths"]
ops = sum(1 for p in paths for m in paths[p])
print("\n[6] openapi paths =", len(paths), " operations =", ops)

# --- 7. 四个指纹 -----------------------------------------------------------
print("\n[7] backend/data 指纹（sha256 前 16 位大写）")


def fp(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16].upper()


data = BACKEND / "data"
CRLF = bytes([13, 10])
for f in sorted(data.rglob("*.yaml")):
    raw = f.read_bytes()
    print(f"    {str(f.relative_to(BACKEND)):48s} {fp(f)}  CRLF={raw.count(CRLF)}")
csvs = sorted(data.rglob("*.csv"))
print("    csv 文件数 =", len(csvs))
for f in csvs:
    print(f"    {str(f.relative_to(BACKEND)):48s} {fp(f)}")
print("    data/seed 文件数 =", len(list((data / 'seed').rglob('*'))) if (data / 'seed').is_dir() else "目录不存在")

# --- 8. pe.db 不得存在 -----------------------------------------------------
print("\n[8] backend/pe.db 存在? ", (BACKEND / "pe.db").exists())
print("    backend/pe_demo.db 存在? ", (BACKEND / "pe_demo.db").exists())

# --- 9. WeeklyClassReport 的列数与 JsonText 列 ----------------------------
from app.db.models.feedback import WeeklyClassReport  # noqa: E402
from app.db.models._shared import JsonText  # noqa: E402

cols = list(WeeklyClassReport.__table__.columns)
print("\n[9] WeeklyClassReport 列数 =", len(cols), [c.name for c in cols])
print("    JsonText 列 =", [c.name for c in cols if isinstance(c.type, JsonText)])

# --- 10. 周日判据：weekday() == 6 是不是周日（用真实日期字面验）------------
import datetime as dt  # noqa: E402
print("\n[10] 周日判据核对（真实日期字面）")
for iso in ("2025-09-13", "2025-09-14", "2025-09-15"):
    d = dt.date.fromisoformat(iso)
    print(f"     {iso} {d.strftime('%A'):10s} weekday()={d.weekday()} isoweekday()={d.isoweekday()}")

# --- 11. alert_stage 的公开面 ---------------------------------------------
import app.pipeline.alert_stage as AS  # noqa: E402
print("\n[11] alert_stage.__all__ =", AS.__all__)
print("     semester_week_of(2025-09-01, 2025-09-14) =",
      AS.semester_week_of(dt.date(2025, 9, 1), dt.date(2025, 9, 14)))
print("     semester_week_range(2025-09-01, 2) =",
      AS.semester_week_range(dt.date(2025, 9, 1), 2))

# --- 12. domain/alerts 的 AlertLevel / RuleId ------------------------------
from app.domain.alerts import AlertLevel, RuleId  # noqa: E402
print("\n[12] AlertLevel =", [e.value for e in AlertLevel])
print("     RuleId =", [e.value for e in RuleId])
from app.domain.stratify import Layer  # noqa: E402
print("     Layer =", [e.value for e in Layer])
from app.db.models.feedback import Alert  # noqa: E402
print("     Alert.LEVELS =", sorted(Alert.LEVELS), " Alert.STATUSES =", sorted(Alert.STATUSES))

# --- 13. routers 的 __all__ / RESOURCES 数 --------------------------------
from app.api.routers.catalog import RESOURCES  # noqa: E402
print("\n[13] RESOURCES 数 =", len(RESOURCES))
print("      writable=False 的 =", sorted(r["path"] for r in RESOURCES if not r["writable"]))

# --- 14. notify 的公开面 ---------------------------------------------------
import app.notify as N  # noqa: E402
print("\n[14] notify.__all__ =", N.__all__)

# --- 15. demo_data 的公开面 ------------------------------------------------
import app.demo_data as DD  # noqa: E402
print("\n[15] demo_data.__all__ =", getattr(DD, "__all__", "(无)"))
