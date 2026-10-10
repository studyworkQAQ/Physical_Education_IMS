"""看清 golden_cases.json 的结构，然后把 Task 9 亲验剩下的各节跑完。"""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))

p = BACKEND / "tests" / "fixtures" / "golden_cases.json"
b = p.read_bytes()
g = json.loads(b.decode("utf-8"))
print(f"### golden_cases.json 的结构")
print(f"  {len(b)} B  CRLF={b.count(bytes([13,10]))}  bareLF={b.count(bytes([10])) - b.count(bytes([13,10]))}")
print(f"  顶层 type = {type(g).__name__}")
if isinstance(g, dict):
    for k, v in g.items():
        extra = f"len={len(v)}" if hasattr(v, "__len__") else ""
        print(f"    {k}: {type(v).__name__} {extra}")
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"      [0] 的键 = {sorted(v[0])}")
            ids = [c.get("id") or c.get("case_id") or c.get("name") for c in v]
            print(f"      用例 id = {ids}")
            print(f"      >>> 用例数 = {len(v)}")
            c14 = [c for c in v if str(c.get("id") or c.get("case_id") or "").upper().endswith("14")]
            if c14:
                e = c14[0].get("expected", {})
                pr = c14[0].get("profile", {})
                print(f"      GC14: bmi={pr.get('bmi')}  triggers={e.get('safety_triggers')}  "
                      f"skipped={e.get('safety_skipped')}  template={e.get('template_id')}")
print(f"  as-is sha256[:16] = {hashlib.sha256(b).hexdigest()[:16].upper()}")
print(f"  CRLF→LF sha256[:16] = {hashlib.sha256(b.replace(bytes([13,10]), bytes([10]))).hexdigest()[:16].upper()}")

print()
print("### 剩下的各节")
from app.db import models as M  # noqa: E402
print(f"  表数 = {len(M.Base.metadata.tables)}")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    x = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(x.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {'✅' if got == want else '⚠️'} {rel:38s} {got}  ({len(x)} B, CRLF={x.count(bytes([13,10]))})")
r = subprocess.run(["git", "diff", "--stat", "cf9ad7a", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
print(f"  pe.db 存在? {(BACKEND / 'pe.db').exists()}   data/seed 文件数 = "
      f"{len(list((BACKEND / 'data' / 'seed').rglob('*'))) if (BACKEND / 'data' / 'seed').exists() else 'DIR-ABSENT'}")

dp = BACKEND / "scripts" / "demo.ps1"
print(f"  demo.ps1 存在? {dp.exists()}", end="")
if dp.exists():
    x = dp.read_bytes()
    s = x.decode("utf-8-sig", errors="replace")
    print(f"  {len(x)} B  BOM={x[:3] == bytes([0xEF, 0xBB, 0xBF])}  CRLF={x.count(bytes([13,10]))}")
    for pat in ("pe_demo.db", "Remove-Item", "PE_DB_URL", "seed.generate", "pipeline.backfill", "pipeline.daily"):
        print(f"     {pat!r} 命中 {s.count(pat)}")
print(f"  demo_bootstrap.py 存在? {(BACKEND / 'scripts' / 'demo_bootstrap.py').exists()}")

import ast  # noqa: E402
hits = []
for q in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in q.parts or "_probes" in q.parts or "scripts" in q.parts:
        continue
    try:
        tr = ast.parse(q.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(tr):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ("shuttle_percentile", "mini_test_scores"):
            hits.append((n.name, q.relative_to(BACKEND).as_posix(), n.lineno))
print(f"  标准化得分的定义点 = {hits}")

from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [x for x in spec["paths"] if x.startswith("/api/")]
print(f"  POST 端点里挂 security 的：")
for x in api:
    for m, o in spec["paths"][x].items():
        if m == "post" and isinstance(o, dict):
            print(f"     {'🔒' if o.get('security') else '⚠️ 匿名'} POST {x}")
