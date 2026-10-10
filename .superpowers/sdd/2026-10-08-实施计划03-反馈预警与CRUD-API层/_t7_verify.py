"""Plan 03 Task 7 亲验 + 结案（Ruling 17 + 控制者错误 #30-#32 + 硬规矩 #112）。
⚠️ #109：跑出「不符项」先用第二个独立工具复核才采信。⚠️ #107：谓词先对已知反例验证。
"""
import dataclasses
import hashlib
import inspect
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. 扫描面 / 端点 / 表数 / 公有面")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
per = {s: len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api")}
print(f"  分目录 = {per}")
chk("扫描面", sum(per.values()), 54)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面", len(obs - subs), 33)
from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 57)
chk("操作数", ops, 85)
chk("handle 端点在线", "/api/alerts/{alert_id}/handle" in spec["paths"], True)

print("\n### 2. 三个新模块的公开面（运行时口径，#107：isclass 与 callable 分开判）")
import app.pipeline.alert_stage as AS  # noqa: E402
import app.notify as NT  # noqa: E402
import app.api.routers.alerts as AR  # noqa: E402
for mod, want in ((AS, 9), (NT, 8), (AR, 5)):
    names = sorted(n for n in dir(mod) if not n.startswith("_")
                   and getattr(getattr(mod, n), "__module__", "") == mod.__name__)
    chk(f"{mod.__name__} 公开面", len(names), want)
    print(f"     {names}")
print(f"  AlertReport 字段 = {[f.name for f in dataclasses.fields(AS.AlertReport)]}")
chk("AlertReport 字段数", len(dataclasses.fields(AS.AlertReport)), 6)
print(f"  evaluate_alerts{inspect.signature(AS.evaluate_alerts)}")
chk("AUTO_REDUCTION_FACTOR", AS.AUTO_REDUCTION_FACTOR, 0.8)
chk("AUTO_SOURCE", AS.AUTO_SOURCE, "auto")

print("\n### 3. 顶回 3：RPE 排序键是课次时间而不是 submitted_at")
src = (BACKEND / "app" / "pipeline" / "alert_stage.py").read_text(encoding="utf-8")
import re  # noqa: E402
for i, l in enumerate(src.split("\n")):
    if re.search(r"order_by|session_date|period|submitted_at", l) and "rpe" in src[max(0, src.index(l) - 400):src.index(l)].lower():
        print(f"  :{i+1} {l.strip()[:135]}")
print("  --- 直接搜 _rpe_rows 的定义体 ---")
i = src.index("def _rpe_rows")
print("  " + src[i:i + 900].replace("\n", "\n  ")[:1000])

print("\n### 4. 顶回 4：reason 不带版本号；版本号落 trigger_snapshot")
for pat in ("alert_rules_version", "trigger_snapshot", "AUTO_SOURCE"):
    print(f"  {pat!r} 在 alert_stage.py 命中 {src.count(pat)}")
i = src.find("alert_rules_version")
if i > 0:
    print("  " + src[max(0, i - 420):i + 260].replace("\n", "\n  "))

print("\n### 5. 顶回 1：_replay_cleanup 的清单（AST 口径，不用文本计数——#103/#107）")
import ast  # noqa: E402
dp = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
tree = ast.parse(dp)
found = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == "_replay_cleanup":
        for s in ast.walk(n):
            if isinstance(s, (ast.Tuple, ast.List)) and len(s.elts) >= 3:
                names = [ast.unparse(e) for e in s.elts]
                if all("models" in x or x[0].isupper() for x in names):
                    found = names
print(f"  清单 = {found}")
chk("清单长度", len(found or []), 6)
chk("ClassSession 不在清单里", any("ClassSession" in x for x in (found or [])), False)
if found:
    iw = next((i for i, x in enumerate(found) if "WeeklyAdjustment" in x), -1)
    ip = next((i for i, x in enumerate(found) if "Prescription" in x and "Template" not in x), -1)
    good = 0 <= iw < ip
    ok &= good
    print(f"  {'✅' if good else '⚠️'} WeeklyAdjustment(#{iw}) 在 Prescription(#{ip}) 之前（子表先删）")

print("\n### 6. 四个指纹 + data 未改 + pe.db")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
    print(f"      {len(b)} B  CRLF={b.count(bytes([13,10]))}")
r = subprocess.run(["git", "diff", "--stat", "6d0c8d2", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)

print("\n### 7. training_days_of 只有一份定义（顶回 5 之外的授权搬家，AST 数定义份数）")
hits = []
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts or "_probes" in p.name or "t7_probes" in p.parts:
        continue
    try:
        tr = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(tr):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in (
                "training_days_of", "_training_days_of"):
            hits.append((p.relative_to(BACKEND).as_posix(), n.lineno, n.name))
print(f"  定义点 = {hits}")
chk("定义份数", len(hits), 1)

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项（按 #109 先复核再采信）'} =====")
