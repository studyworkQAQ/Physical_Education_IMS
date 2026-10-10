"""Plan 03 fix 波亲验 + 合入 main + 推送。⚠️ #109：不符项先用第二个工具复核。"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


def git(*a):
    r = subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or r.stderr).strip()


print(f"### 0. 当前分支 = {git('rev-parse', '--abbrev-ref', 'HEAD')}   HEAD = {git('log', '--oneline', '-1')[:60]}")

print("\n### 1. 写入侧强制：mutating 操作是否全部带 security（走 openapi，不用 app.routes）")
from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
mut = {"post": 0, "patch": 0, "delete": 0}
mut_sec = {"post": 0, "patch": 0, "delete": 0}
for p in api:
    for m, op in spec["paths"][p].items():
        if m in mut and isinstance(op, dict):
            mut[m] += 1
            if op.get("security"):
                mut_sec[m] += 1
print(f"  mutating 总数 = {mut}  合计 {sum(mut.values())}")
print(f"  其中带 security = {mut_sec}  合计 {sum(mut_sec.values())}")
chk("35 个 mutating 全部带 security", sum(mut_sec.values()), sum(mut.values()))
n_sec = sum(1 for p in api for m, op in spec["paths"][p].items()
            if isinstance(op, dict) and op.get("security"))
chk("挂 security 的操作总数", n_sec, 44)
chk("securitySchemes 仍 2 格", len(spec.get("components", {}).get("securitySchemes", {})), 2)
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 63)
chk("操作数", ops, 91)

print("\n### 2. I4：rpe_token 是否已从泛型写侧摘掉")
from app.api.schemas.feedback import ClassSessionCreate, ClassSessionUpdate, ClassSessionRead  # noqa: E402
chk("ClassSessionCreate 有 rpe_token?", "rpe_token" in ClassSessionCreate.model_fields, False)
chk("ClassSessionUpdate 有 rpe_token?", "rpe_token" in ClassSessionUpdate.model_fields, False)
print(f"  ClassSessionRead 仍有 rpe_token? {'rpe_token' in ClassSessionRead.model_fields}"
      f"   <- ⚠️ 实现者点名的遗留：GET 一律匿名，故口令对匿名调用方可读")

print("\n### 3. I1：run_daily 的 now 是否可注入")
import inspect  # noqa: E402
import app.pipeline.daily as D  # noqa: E402
sig = inspect.signature(D.run_daily)
print(f"  run_daily{sig}")
chk("now 是 keyword-only 且有缺省 None",
    sig.parameters.get("now") is not None
    and sig.parameters["now"].kind is inspect.Parameter.KEYWORD_ONLY
    and sig.parameters["now"].default is None, True)
chk("business_now 存在", hasattr(D, "business_now"), True)

print("\n### 4. C1：一处方一周至多一条 auto 调整（读代码取证，不重跑演示库）")
src = (BACKEND / "app" / "pipeline" / "alert_stage.py").read_text(encoding="utf-8")
for pat in ("三道闸门", "四道闸门", "AUTO_SOURCE", "select("):
    print(f"  alert_stage.py 里 {pat!r} 命中 {src.count(pat)}")
i = src.find("def _write_auto_adjustment")
if i > 0:
    print("  " + src[i:i + 1500].replace("\n", "\n  ")[:1600])

print("\n### 5. 五个指纹 + data 未改 + 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
r = subprocess.run(["git", "diff", "--stat", "20797e7", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff 20797e7..HEAD -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)
chk("data/seed 文件数", len(list((BACKEND / "data" / "seed").rglob("*")))
    if (BACKEND / "data" / "seed").exists() else -1, 0)
dp = BACKEND / "scripts" / "demo.ps1"
x = dp.read_bytes()
chk("demo.ps1 的 BOM 还在（实现者报过一次工具事故）", x[:3] == bytes([0xEF, 0xBB, 0xBF]), True)
print(f"  demo.ps1 {len(x)} B  CRLF={x.count(bytes([13,10]))}")

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项'} =====")
if not ok:
    sys.exit(1)

print("\n### 6. 合入 main（fast-forward）+ 推送")
print(f"  fix 分支相对 main 的 commit 数 = {git('rev-list', '--count', 'main..HEAD')}")
print(git("checkout", "main")[:120])
print(git("merge", "--ff-only", "fix/plan-03-review-findings")[:300])
print(f"  main HEAD = {git('log', '--oneline', '-1')[:110]}")
print(f"  20797e7..HEAD 的 commit 数 = {git('rev-list', '--count', '20797e7..HEAD')}")
print(git("push", "origin", "main")[:300])
print(git("push", "origin", "fix/plan-03-review-findings")[:200])
print(f"  origin/main..main 的差 = {git('rev-list', '--count', 'origin/main..main')}（应 0）")
print(f"  git status -> {git('status', '--short') or '（干净）'}")
