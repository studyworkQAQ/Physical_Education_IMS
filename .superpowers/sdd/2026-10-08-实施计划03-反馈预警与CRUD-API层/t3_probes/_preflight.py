"""Plan 03 Task 3 预检（Ruling 1：一份探针）：泛型 CRUD 工厂要的三张表 —— 模型住址 / 自然键 / 大 JSON 列。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import models as M  # noqa: E402
from app.db.models._shared import JsonText  # noqa: E402

RESOURCES = [
    "semester", "teacher", "student", "course_section", "enrollment",
    "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
    "percentile_snapshot", "derived_metrics", "stratification_result",
    "exercise", "prescription_template", "prescription", "weekly_adjustment",
    "class_session", "rpe_record", "training_log", "mini_test",
    "alert", "notification", "weekly_class_report",
]
print(f"### A. 23 个资源的表 -> 模型类 -> 住址（Ruling 97：不在 models 公有面上的必须走子模块）")
print(f"  资源数 = {len(RESOURCES)}")
public = {n for n in dir(M) if not n.startswith("_")}
import importlib  # noqa: E402
rows = []
for tbl in RESOURCES:
    t = M.Base.metadata.tables.get(tbl)
    if t is None:
        print(f"  ⚠️ 表 {tbl} 不存在！")
        continue
    cls_name = t.entity_namespace if hasattr(t, "entity_namespace") else None
    # 从 registry 找类名
    cls = None
    for mapper in M.Base.registry.mappers:
        if mapper.class_.__tablename__ == tbl:
            cls = mapper.class_
            break
    name = cls.__name__ if cls else "?"
    mod = cls.__module__ if cls else "?"
    on_public = name in public
    rows.append((tbl, name, mod, on_public, len(t.columns)))
    flag = "" if on_public else "   ⚠️ 不在 models 公有面上 -> 必须 from " + mod + " import " + name
    print(f"  {tbl:24s} {name:22s} {mod:34s} 公有面={'是' if on_public else '否'} 列={len(t.columns)}{flag}")
n_off = sum(1 for r in rows if not r[3])
print(f"  >>> 不在 models 公有面上的 = {n_off} / {len(rows)}")

print()
print("### B. 每个资源的自然键（唯一约束）—— 泛型 CRUD 的 409 检测靠它")
for tbl, name, mod, onpub, ncol in rows:
    t = M.Base.metadata.tables[tbl]
    uqs = [(c.name, [x.name for x in c.columns]) for c in t.constraints
           if type(c).__name__ == "UniqueConstraint"]
    print(f"  {tbl:24s} {uqs or '（无唯一约束）'}")

print()
print("### C. 每个资源的大 JSON 列（list 端点默认不返回，只在 read-one 返回）")
for tbl, name, mod, onpub, ncol in rows:
    t = M.Base.metadata.tables[tbl]
    js = [c.name for c in t.columns if isinstance(c.type, JsonText)]
    if js:
        print(f"  {tbl:24s} {js}")
print(f"  >>> JsonText 列总数 = {sum(1 for tb in M.Base.metadata.tables.values() for c in tb.columns if isinstance(c.type, JsonText))}")

print()
print("### D. 每个资源的外键（on_delete='restrict' 时要报告是哪张子表挡住的）")
for tbl, name, mod, onpub, ncol in rows:
    t = M.Base.metadata.tables[tbl]
    kids = sorted({fk.parent.table.name for fk in t.foreign_keys} )
    parents = sorted({fk.column.table.name for fk in t.foreign_keys})
    if parents:
        print(f"  {tbl:24s} -> 父表 {parents}")

print()
print("### E. Task 1 交付的 deps.py / errors.py 的公开面（工厂要用）")
import inspect  # noqa: E402
from app.api import deps, errors  # noqa: E402
for m in (deps, errors):
    names = [n for n in dir(m) if not n.startswith("_") and n not in
             {"annotations", "inspect", "os", "sys", "pathlib", "json", "re", "typing",
              "Iterator", "Session", "Header", "HTTPException", "Request", "BaseModel",
              "Field", "jsonable_encoder", "JSONResponse", "IntegrityError", "NoResultFound",
              "RequestValidationError", "StarletteHTTPException", "traceback", "Any", "Path"}]
    print(f"  {m.__name__}: {sorted(set(names))}")
print(f"  deps 的常量：", end=" ")
for n in dir(deps):
    if n.isupper():
        print(f"{n}={getattr(deps, n)!r}", end="  ")
print()
print(f"  errors.register_error_handlers{inspect.signature(errors.register_error_handlers)}")
print(f"  errors.error_response{inspect.signature(errors.error_response)}")

print()
print("### F. repo.py 的公开函数（工厂的写入路径可能要用）")
import app.db.repo as R  # noqa: E402
for n in sorted(dir(R)):
    if n.startswith("_"):
        continue
    o = getattr(R, n)
    if callable(o) and getattr(o, "__module__", "") == R.__name__:
        try:
            print(f"  {n}{inspect.signature(o)}")
        except (TypeError, ValueError):
            print(f"  {n}（签名取不到）")

print()
print("### G. main.py 今天挂了什么（工厂的路由要 include 进去）")
mp = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
for i, l in enumerate(mp.split("\n")):
    if any(k in l for k in ("include_router", "add_middleware", "exception_handler",
                            "register_error_handlers", "create_all", "@app.get", "def create_app",
                            "APIRouter", "app = ")):
        print(f"  :{i+1} {l.rstrip()[:130]}")
