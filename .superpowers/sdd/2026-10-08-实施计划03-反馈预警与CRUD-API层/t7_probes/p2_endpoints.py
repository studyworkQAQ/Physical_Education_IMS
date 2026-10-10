"""Task 7 探针 2：端点数为什么只有 5？（硬规矩 #109：不符项先用第二个独立工具复核）"""
import pathlib
import sys

sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")

from app.api.routers import api_router  # noqa: E402
from app.main import create_app  # noqa: E402

print("api_router.routes 条数 =", len(api_router.routes))
app = create_app(db_url="sqlite://")
print("app.routes 条数 =", len(app.routes))
kinds = {}
for r in app.routes:
    kinds.setdefault(type(r).__name__, 0)
    kinds[type(r).__name__] += 1
print("route 类型分布 =", kinds)
ops = sorted(
    (m, r.path)
    for r in app.routes
    if hasattr(r, "methods")
    for m in (r.methods - {"HEAD", "OPTIONS"})
)
print("操作数 =", len(ops))
print("distinct 路径数 =", len({p for _m, p in ops}))
for m, p in ops[:12]:
    print("   ", m, p)

# 第二个独立工具：openapi()
spec = app.openapi()
paths = spec["paths"]
n_ops = sum(
    1
    for item in paths.values()
    for method in item
    if method in {"get", "post", "patch", "put", "delete"}
)
print()
print("openapi paths =", len(paths), " operations =", n_ops)
