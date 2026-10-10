"""T8 探针 4：dashboard 接进来之后的端点计数、security 清单、schema 可用性。

口径：端点数一律用 ``app.openapi()["paths"]``（⚠️ 不是 ``len(app.routes)``——
FastAPI 0.141.1 的 include_router 是惰性的，折叠成一个 _IncludedRouter，
``app.routes`` 只数得出 5–6 个；Task 3/5/7 三个实现者都独立撞到过这一条）。
"""
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
os.environ.setdefault("PE_DB_URL", "sqlite://")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.main import create_app  # noqa: E402

app = create_app(db_url="sqlite://")
spec = app.openapi()
paths = spec["paths"]
ops = [(p, m) for p in paths for m in paths[p]]
print("paths =", len(paths), " operations =", len(ops))

NEW = [
    ("/api/dashboard/class/{course_section_id}", "get"),
    ("/api/dashboard/weekly-class-report/{course_section_id}", "get"),
    ("/api/students/{student_id}/home", "get"),
    ("/api/teacher/students/{student_id}/weekly-sheet", "get"),
    ("/api/notifications/{notification_id}/read", "post"),
]
print("\n[新端点]")
for key, method in NEW:
    present = key in paths and method in paths[key]
    sec = paths[key][method].get("security") if present else None
    print(f"  {present!s:5s} {method.upper():5s} {key:58s} security={sec}")

print("\n[带 security 的全部端点]（这就是 test_prescription_api 那份 expected 清单）")
secured = sorted(
    (key, method, list(paths[key][method]["security"][0])[0])
    for key, method in ops
    if paths[key][method].get("security")
)
for key, method, name in secured:
    print(f"  ({key!r}, {method!r}): {name!r},")
print("  合计 =", len(secured))

print("\n[不带 security 的 /api/ 操作数]（守卫的第 ③ 拍下界是 >= 70）")
unsecured = [
    (key, method) for key, method in ops
    if key.startswith("/api/") and not paths[key][method].get("security")
]
print("  =", len(unsecured))

print("\n[securitySchemes] =", sorted(spec["components"]["securitySchemes"]))
print("[spec 顶层 security] =", spec.get("security"))

print("\n[新增的 schema 组件]")
for name in sorted(spec["components"]["schemas"]):
    if name.endswith("Read") and name in {
        "AbnormalEntryRead", "BadgeRead", "ClassBlocksRead", "ClassDashboardRead",
        "LayerDistributionRead", "LayerFlowRead", "LayerRateRead", "PendingRpeRead",
        "ProgressBoardRead", "ProgressEntryRead", "RpePointRead", "RpeSummaryRead",
        "ScreenThresholdsRead", "StratificationRead", "StudentHomeRead",
        "ThresholdLinesRead",
    }:
        props = spec["components"]["schemas"][name].get("properties", {})
        print(f"  {name:26s} {len(props)} 个字段: {sorted(props)}")

print("\n[两个 weekly-sheet 端点是不是指向同一个 schema]")
student_ref = paths["/api/students/{student_id}/weekly-sheet"]["get"]["responses"]["200"]
teacher_resp = paths["/api/teacher/students/{student_id}/weekly-sheet"]["get"]["responses"]["200"]
print("  学生侧 200 =", student_ref.get("content", {}).get("application/json", {}).get("schema"))
print("  教师侧 200 =", teacher_resp.get("content", {}).get("application/json", {}).get("schema"))

# --- 扫描面 ------------------------------------------------------------
SCANNED = ("pipeline", "db", "domain", "api")
per = {d: len(sorted((BACKEND / "app" / d).rglob("*.py"))) for d in SCANNED}
print("\n[扫描面] =", per, "合计 =", sum(per.values()))

from app.db.session import Base  # noqa: E402
import app.db.models  # noqa: E402,F401
print("[表数] =", len(Base.metadata.tables))

import app.api.schemas.dashboard as D  # noqa: E402
print("[schemas.dashboard.__all__ 长度] =", len(D.__all__))
import app.api.routers.dashboard as RD  # noqa: E402
print("[routers.dashboard.__all__] =", RD.__all__)
import app.api.deps as DEPS  # noqa: E402
print("[deps.__all__ 长度] =", len(DEPS.__all__), DEPS.__all__)
import app.api.routers.alerts as RA  # noqa: E402
print("[routers.alerts.__all__] =", RA.__all__)
