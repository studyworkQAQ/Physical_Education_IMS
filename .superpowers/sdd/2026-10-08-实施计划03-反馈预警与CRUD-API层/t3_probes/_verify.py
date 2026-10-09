"""Plan 03 Task 3 亲验 + 结案：先验（验不过就不写账本），再追加 Ruling 9。"""
import hashlib
import inspect
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # t3_probes -> <plan dir> -> sdd -> .superpowers -> 仓库根
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. 端点计数走 /openapi.json（不用 len(app.routes)——FastAPI 0.141.1 的 include_router 是惰性的）")
from app.main import create_app  # noqa: E402
app = create_app(db_url="sqlite://")
schema = app.openapi()
paths = schema["paths"]
print(f"  len(app.routes) = {len(app.routes)}   <- 惰性，不能用来数端点")
print(f"  openapi paths = {len(paths)}")
methods = {"get": 0, "post": 0, "patch": 0, "delete": 0}
for p, ops in paths.items():
    for m in ops:
        if m in methods:
            methods[m] += 1
print(f"  方法计数 = {methods}")
api_paths = sorted(p for p in paths if p.startswith("/api/"))
print(f"  /api/ 下的路径数 = {len(api_paths)}")
chk("POST 端点数（= 可写资源数）", methods["post"], 9)
chk("PATCH 端点数", methods["patch"], 9)
chk("DELETE 端点数", methods["delete"], 8)

print("\n### 2. 23 个资源是否全部挂在 /api/ 下")
EXPECT = ["semesters", "teachers", "students", "course-sections", "enrollments",
          "fitness-test-batches", "fitness-test-results", "body-compositions", "interest-surveys",
          "percentile-snapshots", "derived-metrics", "stratification-results", "exercises",
          "prescription-templates", "prescriptions", "weekly-adjustments", "class-sessions",
          "rpe-records", "training-logs", "mini-tests", "alerts", "notifications",
          "weekly-class-reports"]
missing = [r for r in EXPECT if f"/api/{r}" not in paths]
extra = [p for p in api_paths if p.rstrip("/").split("/")[-1] not in EXPECT
         and "{" not in p and p not in ("/api/health",)]
chk("资源数", len(EXPECT), 23)
print(f"  缺的 = {missing or '无'}")
print(f"  多的（非 detail 路径）= {extra or '无'}")
ok &= not missing

print("\n### 3. build_crud_router 与 CrudSchemas 的签名")
from app.api.crud import build_crud_router, CrudSchemas  # noqa: E402
print(f"  build_crud_router{inspect.signature(build_crud_router)}")
import dataclasses  # noqa: E402
for f in dataclasses.fields(CrudSchemas):
    has_d = f.default is not dataclasses.MISSING
    print(f"  CrudSchemas.{f.name}: {f.type}  {'= ' + repr(f.default) if has_d else '（必填）'}")
sig = inspect.signature(build_crud_router)
nk = sig.parameters["natural_key"]
print(f"  natural_key 的缺省 = {nk.default!r}  <- 应是无缺省（漏写当场 TypeError）")
chk("natural_key 无缺省", nk.default is inspect.Parameter.empty, True)

print("\n### 4. 11 个子模块 import（Ruling 97 / P3-B1）")
from app.db import models as M  # noqa: E402
public = {n for n in dir(M) if not n.startswith("_")}
OFF = {"Exercise", "PrescriptionTemplate", "Prescription", "WeeklyAdjustment",
       "ClassSession", "RpeRecord", "TrainingLog", "MiniTest", "Alert", "Notification",
       "WeeklyClassReport"}
chk("11 个表类都不在 models 公有面上", len(public & OFF), 0)
cat = (BACKEND / "app" / "api" / "routers" / "catalog.py").read_text(encoding="utf-8")
print(f"  catalog.py {len(cat.encode('utf-8'))} B / {cat.count(chr(10))} 行")
for mod in ("app.db.models.prescription", "app.db.models.feedback"):
    print(f"  catalog.py 里 {mod!r} 命中 {cat.count(mod)}")
print(f"  catalog.py 里 'models.Prescription' 这类错误写法命中 = "
      f"{sum(cat.count('models.' + n) for n in OFF)}   <- 应 0")

print("\n### 5. JsonText 列的口径（P3-B3 顶回：21 是全库、19 是 23 个资源上）")
from app.db.models._shared import JsonText  # noqa: E402
RES_TABLES = ["semester", "teacher", "student", "course_section", "enrollment",
              "fitness_test_batch", "fitness_test_result", "body_composition", "interest_survey",
              "percentile_snapshot", "derived_metrics", "stratification_result", "exercise",
              "prescription_template", "prescription", "weekly_adjustment", "class_session",
              "rpe_record", "training_log", "mini_test", "alert", "notification",
              "weekly_class_report"]
all_json = {t: [c.name for c in tb.columns if isinstance(c.type, JsonText)]
            for t, tb in M.Base.metadata.tables.items()}
all_json = {k: v for k, v in all_json.items() if v}
res_json = {k: v for k, v in all_json.items() if k in RES_TABLES}
chk("全库 JsonText 列总数", sum(len(v) for v in all_json.values()), 21)
chk("全库含 JsonText 的表数", len(all_json), 9)
chk("23 个资源上的 JsonText 列总数", sum(len(v) for v in res_json.values()), 19)
chk("23 个资源上含 JsonText 的表数", len(res_json), 8)
print(f"  全库多出的那张表 = {sorted(set(all_json) - set(res_json))}")

print("\n### 6. 读写矩阵的三个计数（顶回 2：应是 9/14 与 12/10/1，不是派单的 8/15 与 11/11/1）")
import re  # noqa: E402
rows = re.findall(r"build_crud_router\((.*?)\n\s*\)", cat, re.S)
print(f"  catalog.py 里 build_crud_router( 命中 {cat.count('build_crud_router(')}")
w = cat.count("writable=True")
print(f"  文本口径：'writable=True' 命中 {w}（缺省是 True，故可写数 = 23 - 'writable=False' 的命中数）")
print(f"  文本口径：'writable=False' 命中 {cat.count('writable=False')}")
for v in ("restrict", "cascade", "forbid"):
    print(f"  文本口径：on_delete=\"{v}\" 命中 {cat.count(chr(34) + v + chr(34))}")

print("\n### 7. 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    chk(rel, got, want)
r = subprocess.run(["git", "diff", "--stat", "40a7a0e", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)
chk("表数", len(M.Base.metadata.tables), 25)
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api"))
chk("扫描面", tot, 49)

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项，先查再结案'} =====")
