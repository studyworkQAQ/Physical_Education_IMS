# -*- coding: utf-8 -*-
"""Probe P16: 零散收尾核。"""
import pathlib, re, sys
sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture")
import test_layering as L
import test_domain_purity as P
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")

print("=== 1. layering:175-178 的 `.` 边界理由 ===")
for s in ("app.seed", "app.seed.generate", "app.seedling", "app.seedy"):
    print("  _is_forbidden(%-20r) = %-5s   裸 startswith('app.seed') = %s"
          % (s, L._is_forbidden(s), s.startswith("app.seed")))
print("  仓里是否存在 app/seedling:", list((ROOT / "backend/app").glob("seedling*")))

print("\n=== 2. 「本轮」在两个守卫文件 + daily.py + test_models.py 里的出现（无 commit/轮次绑定）===")
for rel in ("backend/tests/architecture/test_domain_purity.py",
            "backend/tests/architecture/test_layering.py",
            "backend/app/pipeline/daily.py",
            "backend/tests/db/test_models.py",
            "backend/tests/pipeline/test_daily.py",
            "backend/tests/test_config.py"):
    L2 = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    hits = [(i, l.strip()) for i, l in enumerate(L2, 1) if "本轮" in l]
    print("  %-46s %d 处: %s" % (rel.split("/")[-1], len(hits), [h[0] for h in hits]))
    bound = [(i, l) for i, l in hits if re.search(r"fix round \d|Plan 02 Task 1", l)]
    print("      其中带轮次绑定的: %s" % ([b[0] for b in bound] or "无"))

print("\n=== 3. 「两个 bug」vs 三条 bullet ===")
for rel in ("backend/tests/architecture/test_domain_purity.py",
            "backend/tests/architecture/test_layering.py"):
    t = (ROOT / rel).read_text(encoding="utf-8")
    print("  %-24s '两个 bug' 命中 %d 次 ; '三条的复现命令' 命中 %d 次 ; '三种变异' 命中 %d 次"
          % (rel.split("/")[-1], t.count("两个 bug"), t.count("三条的复现命令"), t.count("三种变异")))

print("\n=== 4. FORBIDDEN_IO / FORBIDDEN_CALLS 的成员核（purity:557-558、:568、:584-586）===")
print("  FORBIDDEN_IO 里有裸 'open' 吗 ->", "open" in P.FORBIDDEN_IO)
print("  FORBIDDEN_IO 里有 '__import__' / 'eval' / 'getattr' 吗 ->",
      [t for t in P.FORBIDDEN_IO if t in ("__import__", "eval", "getattr")] or "都没有")
print("  FORBIDDEN_CALLS =", sorted(P.FORBIDDEN_CALLS))
print("  ALLOWED_MODULES 里有 datetime / time 吗 ->",
      sorted(m for m in P.ALLOWED_MODULES if m in ("datetime", "time")) or "都没有")
print("  ALLOWED_MODULES =", sorted(P.ALLOWED_MODULES))
print("  typing 今天有人用吗 ->", "typing" in {
    n for f in (ROOT / "backend/app/domain").rglob("*.py")
    for n in re.findall(r"^\s*(?:import|from)\s+([\w.]+)", f.read_text(encoding="utf-8"), re.M)})

print("\n=== 5. 479 / 481 口径 ===")
print("  HEAD 全量（本轮亲跑，带 --cov）: 480 passed, 1 skipped = 481 collected")
print("  purity:210 / layering:198 印的是 479 条全绿（基线 1fa9941，本轮已在该基线上复跑 -> 479 passed rc 0）")
