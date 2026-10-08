"""Task 7 fr1 亲验：新列 / 新测试 / 计划正文 4 处是否真在树上 / canonical sha256 的交叉验证。"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. prescription 的新列（运行时口径，硬规矩 #89）")
from app.db.models.prescription import Prescription  # noqa: E402
from app.db.models.derived import StratificationResult  # noqa: E402
cols = list(Prescription.__table__.columns)
print(f"  len(columns) = {len(cols)}   (基线 15，应 16)")
c = Prescription.__table__.c.label_at_generation
print(f"  label_at_generation: type={c.type}  nullable={c.nullable}")
print(f"  Prescription 上有第二份 LABELS 词表? {hasattr(Prescription, 'LABELS')}   (应 False)")
print(f"  StratificationResult.LABELS = {sorted(StratificationResult.LABELS)}")
cks = [x for x in Prescription.__table__.constraints if type(x).__name__ == "CheckConstraint"]
for k in cks:
    print(f"  CHECK {k.name}: {str(k.sqltext)[:110]}")

print()
print("### 2. 新测试存在且旧的那条已删")
tp = (BACKEND / "tests" / "pipeline" / "test_prescription_stage.py").read_text(encoding="utf-8")
for name in ("test_trigger_2_survives_the_deletion_of_that_days_stratification_row",
             "test_a_prescription_whose_stratification_row_is_gone_fails_loudly"):
    print(f"  {name[:62]:64s} 命中 {tp.count(name)}")

print()
print("### 3. outerjoin 是否真的从 _last_prescription_of 里删掉了")
ps = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
print(f"  prescription_stage.py {len(ps.encode('utf-8'))} B / {ps.count(chr(10))} 行")
print(f"  'outerjoin' 命中 = {ps.count('outerjoin')}   (应 0)")
print(f"  'label_at_generation' 命中 = {ps.count('label_at_generation')}")
i = ps.index("def _last_prescription_of")
print("  --- _last_prescription_of 的代码行 ---")
seg = ps[i:i + 1600].split("\n")
inq = False
for l in seg:
    s = l.strip()
    if s.count('"""') % 2 == 1:
        inq = not inq
        continue
    if inq or not s or s.startswith("#"):
        continue
    print(f"    {l.rstrip()[:120]}")
    if s.startswith("return") or s.startswith("def ") and l is not seg[0]:
        pass

print()
print("### 4. 计划正文的 4 处（顶回 ① 说控制者没落笔，实现者自己改了 —— 现在应该在树上）")
plan = (ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md").read_text(encoding="utf-8")
print(f"  计划 {len(plan.encode('utf-8'))} B / {plan.count(chr(13)+chr(10))} 行")
checks = [
    ("`valid_to` 关账", "顶回① 的旧文本（应已消失或标注撤回）"),
    ("assembly_error", "顶回② 的第四个键"),
    ("label_at_generation", "F1-1 的新列"),
    ("重放翻倍测试红", "控制者错误 #150 的旧判据"),
    ("String(20)", "新列的长度"),
]
for s, why in checks:
    print(f"  {s!r:28s} 命中 {plan.count(s):3d}   <- {why}")

print()
print("### 5. git 状态与最近 4 个 commit")
for args in (["git", "log", "--oneline", "-4"], ["git", "status", "--short"]):
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(f"  $ {' '.join(args)}")
    for l in (r.stdout or "").strip().split("\n"):
        print(f"    {l[:150]}")

print()
print("### 6. backend/data 与 golden_cases.json 未改（相对 d498bac）")
r = subprocess.run(["git", "diff", "--stat", "d498bac", "HEAD", "--", "backend/data",
                    "backend/tests/fixtures/golden_cases.json"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  diff --stat 输出 = {(r.stdout or '').strip() or '（空 = 未改）'}")

print()
print("### 7. gettrace 钩子是否还在（F1-2）")
r = subprocess.run(["git", "grep", "-n", "gettrace", "--", "backend/tests/"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  " + (r.stdout or "(0 命中)").strip().replace("\n", "\n  ")[:400])
