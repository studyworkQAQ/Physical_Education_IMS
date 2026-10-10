"""Task 9 探针 13：最终验收的全部运行时口径（一次跑完，供报告第 ⑧ 节引用）。

⚠️ 端点数一律走 ``app.openapi()["paths"]``，**不走** ``len(app.routes)``
（FastAPI 0.141.1 的 ``include_router`` 是惰性的，折叠成一个 ``_IncludedRouter``，
``app.routes`` 只数得出 6 个；Plan 03 的 Task 3/5/7 三个实现者各自独立撞到过这一条）。
⚠️ 数「一个名字有几份定义」用 AST；数行尾/字节数用 ``read_bytes()``。
"""
import ast
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
CRLF = b"\r\n"
LF = b"\n"


def sh(*args: str) -> str:
    proc = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return (proc.stdout or "") + (proc.stderr or "")


print("== ① 表数 / 公有导入面 ==")
from app.db import models as M  # noqa: E402
from app.db.session import Base  # noqa: E402
import app.db.models.assessment  # noqa: E402,F401
import app.db.models.derived  # noqa: E402,F401
import app.db.models.feedback  # noqa: E402,F401
import app.db.models.ops  # noqa: E402,F401
import app.db.models.organisation  # noqa: E402,F401
import app.db.models.prescription  # noqa: E402,F401

print("  Base.metadata.tables:", len(Base.metadata.tables))
tree = ast.parse((BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8"))
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
        getattr(t, "id", None) == "_MODELS_PUBLIC_BASELINE" for t in node.targets
    ):
        print("  _MODELS_PUBLIC_BASELINE（AST 数元素）:", len(node.value.elts))

print("== ② 架构守卫的扫描面（镜像 test_layering.SCANNED_DIRS）==")
total = 0
for name in ("pipeline", "db", "domain", "api"):
    n = len(sorted((BACKEND / "app" / name).rglob("*.py")))
    total += n
    print(f"  app/{name}: {n}")
print(f"  合计: {total}")
real_py = sorted(BACKEND.rglob("*.py"))
rel = 0
for py in real_py:
    t = ast.parse(py.read_text(encoding="utf-8"))
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.level:
            rel += len(n.names) if not n.module else 1
print(f"  backend/**/*.py 总数（test_layering 那条 >= 40 的实际值）: {len(real_py)}")
print(f"  全仓相对导入条数（那条 >= 16 的实际值）: {rel}")

print("== ③ 端点面 ==")
from app.main import create_app  # noqa: E402

spec = create_app(db_url="sqlite://").openapi()
paths = spec["paths"]
methods = ("get", "post", "put", "patch", "delete")
ops = sum(1 for item in paths.values() for m in item if m in methods)
sec = sum(1 for item in paths.values() for m, op in item.items()
          if m in methods and "security" in op)
api_paths = [p for p in paths if p.startswith("/api/")]
print(f"  路径模板: {len(paths)}（/api/ 下 {len(api_paths)}）  操作: {ops}  挂 security: {sec}")

print("== ④ 黄金用例 ==")
golden = BACKEND / "tests" / "fixtures" / "golden_cases.json"
raw = golden.read_bytes()
import json  # noqa: E402

data = json.loads(raw.replace(CRLF, LF).decode("utf-8"))
crlf = raw.count(CRLF)
print(f"  {len(raw)} B / {crlf + (raw.count(LF) - crlf)} 行 / CRLF={crlf} "
      f"bare LF={raw.count(LF) - crlf}")
print(f"  sha256[:16] as-is     = {hashlib.sha256(raw).hexdigest()[:16].upper()}")
print(f"  sha256[:16] CRLF->LF  = "
      f"{hashlib.sha256(raw.replace(CRLF, LF)).hexdigest()[:16].upper()}")
print(f"  input {len(data['input'])} 例 / expected {len(data['expected'])} 例")
print(f"  学号: {[c['student_id'] for c in data['input']]}")
gc14 = data["expected"][13]
print(f"  GC14: bmi={gc14['bmi']} tpl={gc14['template_id']} "
      f"subs={gc14['safety_substitution_count']} triggers={gc14['safety_triggers']} "
      f"needs_review={gc14['needs_review']} block0={gc14['week1_block0_exercise_ref']} "
      f"hr={gc14['week1_block0_hr_zone']} vol={gc14['week1_block0_weekly_volume']}")

print("== ⑤ 五个指纹（现算自磁盘，与测试里的字面量各一份）==")


def fp(rel: str) -> str:
    b = (BACKEND / rel).read_bytes()
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


for rel in ("data/national_standard_2014.csv", "data/exercises.yaml",
            "data/exercise_equivalence.yaml", "data/alert_rules.yaml"):
    print(f"  {rel}: {fp(rel)}")
tpl_dir = BACKEND / "data" / "prescription"
digests = {p.name: hashlib.sha256(p.read_bytes().replace(CRLF, LF)).hexdigest()[:16].upper()
           for p in sorted(tpl_dir.glob("*.yaml"))}
print(f"  data/prescription/*.yaml: {len(digests)} 份")
sys.path.insert(0, str(BACKEND))
from tests.domain.test_prescription_templates import TEMPLATE_FINGERPRINTS  # noqa: E402
mismatch = {k: (v, TEMPLATE_FINGERPRINTS.get(k)) for k, v in digests.items()
            if TEMPLATE_FINGERPRINTS.get(k) != v}
print(f"  与 TEMPLATE_FINGERPRINTS 对账: {'全部一致' if not mismatch else mismatch}")

print("== ⑥ 禁区 ==")
print(f"  backend/pe.db 存在 = {(BACKEND / 'pe.db').exists()}（必须 False）")
seed_dir = BACKEND / "data" / "seed"
files = sorted(p.name for p in seed_dir.iterdir()) if seed_dir.is_dir() else []
print(f"  backend/data/seed/ 文件 = {files}（必须 []）")
print(f"  backend/pe_demo.db 存在 = {(BACKEND / 'pe_demo.db').exists()}（gitignore 内，可有）")

print("== ⑦ git：backend/data 的改动面 ==")
out = sh("git", "diff", "--stat", "cf9ad7a", "HEAD", "--", "backend/data")
print(f"  git diff --stat cf9ad7a HEAD -- backend/data:\n{out or '    （空 = 一个字节都没动）'}")
out = sh("git", "diff", "--stat", "cf9ad7a", "HEAD", "--", "backend/tests/fixtures")
print(f"  git diff --stat cf9ad7a HEAD -- backend/tests/fixtures:\n{out}")
out = sh("git", "diff", "--name-only", "cf9ad7a", "HEAD")
print(f"  cf9ad7a..HEAD 改动的全部文件（{len([x for x in out.splitlines() if x])} 个）:")
for line in out.splitlines():
    if line:
        print(f"    {line}")
print("== ⑧ 工作树未入库的（应只有 .superpowers/ 与本 Task 的新文件）==")
print(sh("git", "status", "--porcelain"))
sys.exit(0)
