"""Task 7 验收探针：一次跑完派单第 7 节要的全部数（运行时口径，硬规矩 #89/#111）。"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BACKEND = REPO / "backend"
APP = BACKEND / "app"
sys.path.insert(0, str(BACKEND))

import ast  # noqa: E402

print("=== A. 表数 / _MODELS_PUBLIC_BASELINE / 扫描面 ===")
from app.db.session import Base  # noqa: E402
import app.db.models  # noqa: E402,F401  仅为把 25 张表注册进 metadata

print("  Base.metadata.tables =", len(Base.metadata.tables))

from tests.architecture.test_layering import SCANNED_DIRS  # noqa: E402

total = 0
for rel in SCANNED_DIRS:
    n = len(sorted((APP / rel).rglob("*.py")))
    total += n
    print(f"    {rel}: {n}")
print("  扫描面合计 =", total, "（基线 52）")
print("  app/ 根下的 .py:", sorted(p.name for p in APP.glob("*.py")))

tmod = ast.parse((BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8"))
for node in tmod.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "_MODELS_PUBLIC_BASELINE" for t in node.targets
    ):
        print("  _MODELS_PUBLIC_BASELINE 项数 =", len(node.value.elts), "（应仍 33）")

print()
print("=== B. 端点数（openapi 口径）===")
from app.main import create_app  # noqa: E402

application = create_app(db_url="sqlite://")
spec = application.openapi()
paths = spec["paths"]
n_ops = sum(
    1 for item in paths.values() for m in item
    if m in {"get", "post", "patch", "put", "delete"}
)
api_paths = {k for k in paths if k.startswith("/api/")}
print("  openapi paths =", len(paths), "（基线 56）")
print("  operations =", n_ops, "（基线 84）")
print("  /api/ 下的 paths =", len(api_paths))
print("  新增的那一个:", sorted(api_paths - {
    "/api/health"})[-3:])

print()
print("=== C. _replay_cleanup 的清单（AST 数元组项）===")
dtree = ast.parse((APP / "pipeline" / "daily.py").read_text(encoding="utf-8"))
fn = next(n for n in ast.walk(dtree)
          if isinstance(n, ast.FunctionDef) and n.name == "_replay_cleanup")
loop = next(n for n in ast.walk(fn) if isinstance(n, ast.For))
names = [ast.unparse(e) for e in loop.iter.elts]
print("  项数 =", len(names), "（基线 5）")
print("  顺序 =", names)
print("  ClassSession 在里面:", any("ClassSession" in n for n in names))

print()
print("=== D. run_daily 里的阶段调用序（AST，按行号）===")
rd = next(n for n in ast.walk(dtree)
          if isinstance(n, ast.FunctionDef) and n.name == "run_daily")
stage_calls = []
for node in ast.walk(rd):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"_replay_cleanup", "extract", "_load_sources",
                            "_stratify_and_persist", "generate_prescriptions",
                            "evaluate_alerts", "run_percentile"}:
            stage_calls.append((node.lineno, node.func.id))
for lineno, name in sorted(stage_calls):
    print(f"    :{lineno} {name}")
assigns = [ast.unparse(n.targets[0]) for n in ast.walk(rd)
           if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
           and n.targets[0].attr in {"prescription_count", "alert_count"}]
print("  run 上的两个计数列赋值:", assigns)

print()
print("=== E. 四个指纹（sha256 前 16 位，CRLF 归一化为 LF）===")
CRLF = b"\r\n"
EXPECTED = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercises.yaml": "5394B37F01DAC9AC",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
    "data/alert_rules.yaml": "E48E3AC82BB45BB7",
}


def fp(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(CRLF, b"\n")).hexdigest()[:16].upper()


for rel, want in EXPECTED.items():
    p = BACKEND / rel
    raw = p.read_bytes()
    got = fp(p)
    print(f"  {rel}: {got} 期望 {want} {'✓' if got == want else '✗ 变了'}"
          f"  bytes={len(raw)} crlf={raw.count(CRLF)}")

print()
print("=== F. 禁区 ===")
print("  backend/pe.db 存在:", (BACKEND / "pe.db").exists())
seed_dir = BACKEND / "data" / "seed"
print("  backend/data/seed 下的文件数:",
      len(list(seed_dir.rglob("*"))) if seed_dir.exists() else "ABSENT")


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


diff = git("diff", "--stat", "6d0c8d2", "HEAD", "--", "backend/data")
print("  git diff 6d0c8d2 HEAD -- backend/data:", repr(diff.stdout.strip()) or "（空）")
print("  git diff 退出码:", diff.returncode)
untracked = git("status", "--porcelain", "--", "backend/data")
print("  backend/data 下的未入库改动:", repr(untracked.stdout.strip()) or "（无）")

print()
print("=== G. 公开面（dir 口径）===")
import app.notify as notify  # noqa: E402
import app.pipeline.alert_stage as stage  # noqa: E402
import app.api.routers.alerts as router_mod  # noqa: E402

print("  app.notify.__all__ =", len(notify.__all__), notify.__all__)
print("  app.pipeline.alert_stage.__all__ =", len(stage.__all__), stage.__all__)
print("  app.api.routers.alerts.__all__ =", len(router_mod.__all__), router_mod.__all__)
import app.refdata_alerts as ra  # noqa: E402

own = sorted(
    n.name for n in ast.parse((APP / "refdata_alerts.py").read_text(encoding="utf-8")).body
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
) + sorted(
    t.id for n in ast.parse((APP / "refdata_alerts.py").read_text(encoding="utf-8")).body
    if isinstance(n, ast.Assign) for t in n.targets
    if isinstance(t, ast.Name) and not t.id.startswith("_")
)
print("  app.refdata_alerts 的公开面 =", len(own), own)

print()
print("=== H. AlertReport 的字段（dataclasses 口径）===")
import dataclasses  # noqa: E402

print(" ", [f.name for f in dataclasses.fields(stage.AlertReport)])
print("  frozen:", stage.AlertReport.__dataclass_params__.frozen)

print()
print("=== I. git ===")
print(" ", git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip())
for line in git("log", "--oneline", "-5").stdout.strip().splitlines():
    print("   ", line)
print("  工作树:", repr(git("status", "--porcelain", "--", "backend").stdout.strip()) or "（干净）")
