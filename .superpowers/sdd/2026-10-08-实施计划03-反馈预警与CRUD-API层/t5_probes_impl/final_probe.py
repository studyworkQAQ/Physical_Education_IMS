"""Plan 03 Task 5 的最终验收探针：扫描面 / 端点数 / 表数 / 三个指纹 / 禁区。

一律运行时口径（硬规矩 #89）；字节数与行尾用 read_bytes()（#89 扩写）；
「一个名字有几份定义」用 AST（#89 再扩写）。
指纹口径逐字照 tests/test_refdata_prescription.py::_fingerprint：
sha256(read_bytes().replace(CRLF, LF)).hexdigest()[:16].upper()
"""
import ast
import hashlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def fingerprint(path: pathlib.Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()[:16].upper()


print("=== ① 扫描面（tests/architecture/test_layering.py 的 SCANNED_DIRS）===")
from tests.architecture.test_layering import SCANNED_DIRS, _py_files  # noqa: E402
total = 0
for rel in SCANNED_DIRS:
    n = len(_py_files(rel))
    print(f"  {rel:10s} {n}")
    total += n
print("  TOTAL:", total)

print()
print("=== ② HTTP 端点（运行时 openapi 口径）===")
from app.main import create_app  # noqa: E402
app = create_app(db_url="sqlite://")
spec = app.openapi()
METHODS = {"get", "post", "patch", "put", "delete", "head", "options"}
api_paths = [p for p in spec["paths"] if p.startswith("/api/")]
ops = [(p, m) for p in api_paths for m in spec["paths"][p] if m in METHODS]
print("  /api/ 路径模板:", len(api_paths))
print("  /api/ 操作数  :", len(ops))
kinds = {}
for r in app.routes:
    kinds[type(r).__name__] = kinds.get(type(r).__name__, 0) + 1
print("  app.routes（不完整口径，Starlette 1.7 折叠成 _IncludedRouter）:",
      len(app.routes), kinds)

print()
print("=== ③ 表数 / 模型公有导入面 ===")
from app.db import models as M  # noqa: E402
from app.db.session import Base  # noqa: E402
print("  tables:", len(Base.metadata.tables))
print("  models 公有面:", len([n for n in dir(M) if not n.startswith('_')]),
      "（基线 33，应不变）")

print()
print("=== ④ 三个指纹（禁区 backend/data/**）===")
expected = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercises.yaml": "5394B37F01DAC9AC",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
}
for rel, want in expected.items():
    got = fingerprint(BACKEND / rel)
    print(f"  {rel:38s} {got}  逐字不变={got == want}")

print()
print("=== ⑤ backend/data/** 的全部文件（字节数 + CRLF 计数）===")
for p in sorted((BACKEND / "data").rglob("*")):
    if p.is_file():
        raw = p.read_bytes()
        crlf = raw.count(bytes([13, 10]))
        lf = raw.count(bytes([10]))
        print(f"  {p.relative_to(BACKEND).as_posix():48s} {len(raw):8d} B  "
              f"crlf={crlf:5d}  lf={lf:5d}")

print()
print("=== ⑥ 禁区文件是否存在 ===")
print("  backend/pe.db 存在:", (BACKEND / "pe.db").exists(), "（必须 False）")
seed_dir = BACKEND / "data" / "seed"
print("  backend/data/seed 存在:", seed_dir.exists(),
      "文件数:", len([p for p in seed_dir.rglob('*') if p.is_file()])
      if seed_dir.exists() else "n/a", "（必须 0）")

print()
print("=== ⑦ AST：新模块的顶层定义有没有重名（单一所有者）===")
for rel in ("app/api/routers/feedback.py", "app/api/schemas/feedback.py"):
    tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
    names = [n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    assigns = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
               for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
               if isinstance(t, ast.Name)]
    allnames = names + assigns
    dupes = sorted({n for n in allnames if allnames.count(n) > 1})
    print(f"  {rel}: 顶层 {len(allnames)} 个（函数/类 {len(names)} + 常量 {len(assigns)}），重复={dupes}")

print()
print("=== ⑧ 七个端点各自的操作数与 security ===")
for path in sorted(api_paths):
    if any(k in path for k in ("open-rpe", "rpe-status", "completion-rate",
                               "mini-tests", "rpe-records", "training-logs")):
        for m in sorted(spec["paths"][path]):
            if m in METHODS:
                sec = spec["paths"][path][m].get("security")
                print(f"  {m.upper():5s} {path:60s} security={sec}")
