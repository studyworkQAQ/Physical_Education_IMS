"""Plan 03 Task 1 亲验：全量 / 覆盖率 / 扫描面 / 签名 / 禁区 / 守卫有牙。"""
import hashlib
import inspect
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. 签名（运行时口径）")
from app.main import create_app, DEMO_DB_URL, DB_URL_ENV_VAR  # noqa: E402
from app.api import deps  # noqa: E402
for f in (create_app, deps.get_db, deps.current_student, deps.current_teacher, deps.require_scope):
    print(f"  {f.__module__}.{f.__name__}{inspect.signature(f)}")
print(f"  DB_URL_ENV_VAR = {DB_URL_ENV_VAR!r}")
print(f"  DEMO_DB_URL = {DEMO_DB_URL!r}")
from app.config import DEFAULT_DB_URL  # noqa: E402
print(f"  DEFAULT_DB_URL = {DEFAULT_DB_URL!r}   <- 控制者核实它是不是 pe.db")
print(f"  pe.db 存在? {(BACKEND / 'pe.db').exists()}   pe_demo.db 存在? {(BACKEND / 'pe_demo.db').exists()}")

print()
print("### 2. Page 的字段与约束")
from pydantic import BaseModel  # noqa: E402
P = deps.Page
for name, fi in P.model_fields.items():
    print(f"  .{name}: {fi.annotation}  default={fi.default}  约束={fi.metadata}")

print()
print("### 3. 扫描面（运行时口径，不用正则数源码）")
tot = 0
for s in ("pipeline", "db", "domain", "api"):
    n = len(list((BACKEND / "app" / s).rglob("*.py")))
    tot += n
    print(f"  app/{s:9s} = {n}")
print(f"  合计 = {tot}   (基线 35)")
print(f"  backend 全树 .py = {len(list(BACKEND.rglob('*.py')))}")

print()
print("### 4. app/api 的文件清单")
for p in sorted((BACKEND / "app" / "api").rglob("*.py")):
    print(f"  {p.relative_to(BACKEND).as_posix():40s} {p.stat().st_size:6d} B")

print()
print("### 5. 反向依赖守卫：domain / db / pipeline 里有没有 app.api")
bad = []
for s in ("domain", "db", "pipeline", "seed"):
    for p in (BACKEND / "app" / s).rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        if "app.api" in txt or "from app import api" in txt:
            bad.append(p.relative_to(BACKEND).as_posix())
print(f"  违规文件 = {bad or '无'}")

print()
print("### 6. 三个禁区指纹 + data 未改")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:40s} {len(b):7d} B CRLF={b.count(bytes([13,10]))} {got} {'OK' if got == want else '⚠️ MISMATCH'}")
for args in (["git", "diff", "--stat", "69b4218", "HEAD", "--", "backend/data"],
             ["git", "status", "--short"], ["git", "log", "--oneline", "-4"]):
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    print(f"  $ {' '.join(args[1:4])}… -> {out[:300] if out else '（空）'}")
print(f"  data/seed 文件数 = {len(list((BACKEND/'data'/'seed').rglob('*'))) if (BACKEND/'data'/'seed').exists() else 'DIR-ABSENT'}")

print()
print("### 7. .gitignore 是否挡住了 pe_demo.db")
gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
print(f"  含 'pe_demo.db'? {'pe_demo.db' in gi}")
r = subprocess.run(["git", "check-ignore", "-v", "backend/pe_demo.db"], cwd=str(ROOT),
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git check-ignore -> {(r.stdout or r.stderr).strip()[:160] or '（未被忽略！）'}")

print()
print("### 8. errors.py 注册了哪些异常处理器（顶回 4 的复核）")
err = (BACKEND / "app" / "api" / "errors.py").read_text(encoding="utf-8")
import re  # noqa: E402
for m in re.finditer(r"add_exception_handler\(\s*([\w.]+)", err):
    print(f"  handler: {m.group(1)}")
for m in re.finditer(r"^def (\w+)\(", err, re.M):
    print(f"  def {m.group(1)}")

print()
print("### 9. tests/api 有没有 __init__.py（偏离 ① 的复核）")
print(f"  tests 下 __init__.py 数 = {len(list((BACKEND/'tests').rglob('__init__.py')))}")
print(f"  tests 下 .py 总数 = {len(list((BACKEND/'tests').rglob('*.py')))}")
print(f"  tests/api 的内容 = {[p.name for p in sorted((BACKEND/'tests'/'api').iterdir())]}")
