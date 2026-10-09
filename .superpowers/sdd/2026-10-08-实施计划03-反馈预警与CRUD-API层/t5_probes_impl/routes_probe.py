"""为什么 app.routes 里看不到那七个端点？"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.main import create_app          # noqa: E402

app = create_app(db_url="sqlite://")
print("total routes:", len(app.routes))
kinds = {}
for route in app.routes:
    kinds[type(route).__name__] = kinds.get(type(route).__name__, 0) + 1
print("route kinds:", kinds)

api_paths = [
    (getattr(route, "path", None), sorted(getattr(route, "methods", ()) or ()))
    for route in app.routes
    if str(getattr(route, "path", "")).startswith("/api/")
]
print("api route count:", len(api_paths))
for path, methods in api_paths[:8]:
    print("  ", path, methods)

targets = [
    "/api/class-sessions/{class_session_id}/open-rpe",
    "/api/rpe-records",
    "/api/class-sessions/{class_session_id}/rpe-status",
    "/api/training-logs",
    "/api/students/{student_id}/training-logs/completion-rate",
    "/api/mini-tests/batch",
    "/api/mini-tests/normalized",
]
found = {p for p, _ in api_paths}
for t in targets:
    print(f"  present={t in found}  {t}")

# openapi 口径对照（另一种口径：以运行时 openapi() 为准）
spec = app.openapi()
print("openapi paths with /api/:", sum(1 for k in spec["paths"] if k.startswith("/api/")))
print("openapi has normalized:", "/api/mini-tests/normalized" in spec["paths"])
