"""T8 探针 7：最终验收的全部计数与四个指纹（一律运行时 / read_bytes() 口径）。"""
import ast
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
import os  # noqa: E402
os.environ.setdefault("PE_DB_URL", "sqlite://")
os.chdir(BACKEND)

CRLF = bytes([13, 10])


def fp(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16].upper()


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8").stdout


print("=" * 76)
print("[1] 四个指纹（backend/data）")
EXPECT = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercises.yaml": "5394B37F01DAC9AC",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
    "data/alert_rules.yaml": "E48E3AC82BB45BB7",
}
ok = True
for rel, want in EXPECT.items():
    p = BACKEND / rel
    got = fp(p)
    crlf = p.read_bytes().count(CRLF)
    flag = "OK" if got == want else "**不符**"
    ok &= got == want
    print(f"  {flag:8s} {rel:40s} {got}  (期望 {want})  CRLF={crlf}")
print("  四个指纹逐字不变?", ok)

print("\n[2] 禁区")
print("  backend/pe.db 存在?", (BACKEND / "pe.db").exists(), "（必须 False）")
seed_dir = BACKEND / "data" / "seed"
print("  backend/data/seed 存在?", seed_dir.is_dir(),
      "文件数 =", len([p for p in seed_dir.rglob("*") if p.is_file()]) if seed_dir.is_dir() else "n/a",
      "（必须 0）")
diff = git("diff", "--stat", "6127fc7", "HEAD", "--", "backend/data")
print("  git diff 6127fc7 HEAD -- backend/data 为空?", diff.strip() == "", repr(diff.strip()))

print("\n[3] 表数 / 扫描面 / 端点数")
from app.db.session import Base  # noqa: E402
import app.db.models  # noqa: E402,F401
print("  表数 =", len(Base.metadata.tables), "（必须 25）")
SCANNED = ("pipeline", "db", "domain", "api")
per = {d: len(sorted((BACKEND / "app" / d).rglob("*.py"))) for d in SCANNED}
print("  扫描面 =", per, "合计 =", sum(per.values()), "（基线 54）")
from app.main import create_app  # noqa: E402
app = create_app(db_url="sqlite://")
paths = app.openapi()["paths"]
print("  openapi paths =", len(paths), "（基线 57）")
print("  operations =", sum(1 for p in paths for m in paths[p]), "（基线 85）")

print("\n[4] _MODELS_PUBLIC_BASELINE（必须 33，本 Task 不动）")
t = ast.parse((BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8"))
for node in t.body:
    if isinstance(node, ast.Assign):
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "_MODELS_PUBLIC_BASELINE":
                print("  长度 =", len(node.value.elts))

print("\n[5] _replay_cleanup 的清单（AST 口径）")
d = ast.parse((BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8"))
for node in ast.walk(d):
    if isinstance(node, ast.FunctionDef) and node.name == "_replay_cleanup":
        for sub in ast.walk(node):
            if isinstance(sub, ast.For) and isinstance(sub.iter, ast.Tuple):
                names = [ast.unparse(e) for e in sub.iter.elts]
                print("  长度 =", len(names))
                for i, n in enumerate(names, 1):
                    print(f"    {i}. {n}")

print("\n[6] app/domain/report.py 的公开面")
import app.domain.report as R  # noqa: E402
print("  __all__ 长度 =", len(R.__all__))
print("  __all__ =", R.__all__)
consts = [n for n in R.__all__ if n.isupper() or n[0].isupper() and not callable(getattr(R, n))]
funcs = [n for n in R.__all__ if callable(getattr(R, n)) and not isinstance(getattr(R, n), type)]
types = [n for n in R.__all__ if isinstance(getattr(R, n), type)]
print("  函数 =", len(funcs), funcs)
print("  值类型 =", len(types), types)
print("  常量 =", len(R.__all__) - len(funcs) - len(types))
import dataclasses  # noqa: E402
for t_ in types:
    cls = getattr(R, t_)
    if dataclasses.is_dataclass(cls):
        print(f"    {t_} 的字段 =", [f.name for f in dataclasses.fields(cls)])

print("\n[7] report_stage / dashboard / schemas 的公开面")
import app.pipeline.report_stage as RS  # noqa: E402
import app.api.routers.dashboard as RD  # noqa: E402
import app.api.schemas.dashboard as SD  # noqa: E402
import app.api.deps as DEP  # noqa: E402
import app.api.routers.alerts as RA  # noqa: E402
print("  report_stage.__all__ =", len(RS.__all__), RS.__all__)
print("  routers.dashboard.__all__ =", RD.__all__)
print("  schemas.dashboard.__all__ =", len(SD.__all__))
print("  deps.__all__ =", len(DEP.__all__))
print("  routers.alerts.__all__ =", RA.__all__)

print("\n[8] training_days_of 的定义份数（AST，必须 1）")
count = 0
for py in (BACKEND / "app").rglob("*.py"):
    tree = ast.parse(py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name == "training_days_of":
            count += 1
            print("    定义在", py.relative_to(BACKEND))
print("  合计 =", count)

print("\n[9] git")
print(git("log", "--oneline", "-5").strip())
print("  branch =", git("branch", "--show-current").strip())
print("  status:")
print(git("status", "--short"))
