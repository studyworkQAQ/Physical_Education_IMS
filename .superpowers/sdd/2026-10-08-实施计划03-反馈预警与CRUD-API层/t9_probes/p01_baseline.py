"""Task 9 基线探针：在当前 HEAD 上实测派单里引用的每一个「既有常量的当前值」（硬规矩 #111）。

口径一律运行时（#89）：表数走 metadata，扫描面走 AST 文件计数，端点数走 app.openapi()["paths"]。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "backend"))

from app.db import models as _models_pkg  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.main import create_app  # noqa: E402
import app.db.models.assessment  # noqa: E402,F401
import app.db.models.derived  # noqa: E402,F401
import app.db.models.feedback  # noqa: E402,F401
import app.db.models.ops  # noqa: E402,F401
import app.db.models.organisation  # noqa: E402,F401
import app.db.models.prescription  # noqa: E402,F401

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"

print("== tables ==")
print("table count:", len(Base.metadata.tables))
print("len(models.__all__):", len(_models_pkg.__all__))
# _MODELS_PUBLIC_BASELINE 住在测试里（它是「拆包前的公有导入面」那份**字面清单**，
# 刻意不从 app.db.models 读回来跟自己比，硬规矩 #35），故用 AST 数它的元素个数。
import ast  # noqa: E402

_tree = ast.parse((BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8"))
for _node in _tree.body:
    if isinstance(_node, ast.Assign) and any(
        getattr(t, "id", None) == "_MODELS_PUBLIC_BASELINE" for t in _node.targets
    ):
        print("_MODELS_PUBLIC_BASELINE 的元素个数（AST 口径）:", len(_node.value.elts))

print("== scan surface (mirrors tests/architecture/test_layering.py) ==")
for name in ("pipeline", "db", "domain", "api"):
    d = BACKEND / "app" / name
    n = len(list(d.rglob("*.py")))
    print(f"  app/{name}: {n}")

print("== endpoints ==")
app = create_app()
spec = app.openapi()
paths = spec["paths"]
api_paths = [p for p in paths if p.startswith("/api/")]
ops = 0
sec = 0
for p, item in paths.items():
    for method, op in item.items():
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        ops += 1
        if "security" in op:
            sec += 1
print("path templates total:", len(paths))
print("path templates under /api/:", len(api_paths))
print("operations:", ops)
print("operations with security:", sec)
print("app.routes len (惰性 include_router, 不可用):", len(app.routes))
