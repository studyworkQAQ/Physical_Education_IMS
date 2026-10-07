# -*- coding: utf-8 -*-
"""P20 — 派单里我要写进源码/报告的事实性断言，逐条亲验。

(d) 会在主工作树上临时删掉两份的越界守卫跑一次全量，跑完按字节还原并核 sha256。
"""
import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BACKEND = ROOT / "backend"
PUR = BACKEND / "tests/architecture/test_domain_purity.py"
LAY = BACKEND / "tests/architecture/test_layering.py"
P01 = ROOT / ".superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md"
P02 = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md"


def g(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false"] + list(a), cwd=str(ROOT),
                          capture_output=True).stdout.decode("utf-8", "replace")


print("=== (a) 6784d57..d00533c 之间只有 Document/ 吗 ===")
print("   git diff --name-only 6784d57 d00533c =", g("diff", "--name-only", "6784d57", "d00533c").split())
for c in ("73313f7", "ef48d33", "d00533c"):
    print("   %s 一个 commit 的改动面 = %s" % (c, g("diff", "--name-only", c + "^", c).split()))

print()
print("=== (b) Plan 02 账本的 Ruling 编号：47 -> 49，48 号未使用 ===")
t02 = P02.read_text(encoding="utf-8")
nums = sorted({int(m) for m in re.findall(r"Ruling (\d+)", t02)})
print("   出现过的 Ruling 号（去重、升序）:", nums)
print("   47 在里面吗", 47 in nums, "; 48 在里面吗", 48 in nums, "; 49 在里面吗", 49 in nums)
print("   最大号 =", max(nums))
for i, l in enumerate(t02.splitlines(), 1):
    if l.startswith("**Ruling 47") or l.startswith("**Ruling 48") or l.startswith("**Ruling 49"):
        print("   :%d %s" % (i, l[:80]))

print()
print("=== (c) 两份账本的路径与体积 ===")
for p, claim in ((P01, "约 806 KB"), (P02, "约 123 KB")):
    print("   %-22s exists=%s bytes=%d (%.0f KB)  派单说 %s"
          % (p.parent.name[:22], p.exists(), p.stat().st_size,
             p.stat().st_size / 1024, claim))

print()
print("=== (e) review_probes 目录存在吗 ===")
plan = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎"
print("   plan 目录下的子目录:", sorted(x.name for x in plan.iterdir() if x.is_dir()))
print("   (plan/'review_probes').exists() =", (plan / "review_probes").exists())
print("   全仓 glob '**/review_probes' =", [str(x) for x in ROOT.glob("**/review_probes")])
rev = (plan / "task-1-fixchain-review.md").read_text(encoding="utf-8")
print("   评审报告里引用 'review_probes/' 的次数 =", rev.count("review_probes/"))
for m in sorted(set(re.findall(r"review_probes/[A-Za-z0-9_.]+", rev))):
    print("      ", m)

print()
print("=== (f) 硬规矩的定义位置抽查（派单 §1 的说法）===")
t01 = P01.read_text(encoding="utf-8") if P01.exists() else ""
for n in (19, 30, 32, 35, 39, 42, 46, 47, 48, 50, 51, 52, 53, 56, 57, 58, 59, 60):
    pat_def = re.compile(r"^(补)?硬规矩 #%d[:：]" % n, re.M)
    hits01 = len(pat_def.findall(t01))
    hits02 = len(pat_def.findall(t02))
    # 也接受「**硬规矩 #N：**」这类写法
    alt01 = len(re.findall(r"硬规矩 #%d[：:]" % n, t01))
    alt02 = len(re.findall(r"硬规矩 #%d[：:]" % n, t02))
    print("   #%-3d Plan01 定义行=%d(宽口径 %d)   Plan02 定义行=%d(宽口径 %d)"
          % (n, hits01, alt01, hits02, alt02))

print()
print("=== (d) HEAD 上把两份的越界守卫都删掉，全量跑（预期 2 failed, 479 passed）===")
ORIG = {p: p.read_bytes() for p in (PUR, LAY)}
SHA = {p: hashlib.sha256(b).hexdigest() for p, b in ORIG.items()}
GUARD = "    if level - 1 > len(package):\n"
try:
    for p in (PUR, LAY):
        t = ORIG[p].decode("utf-8").replace("\r\n", "\n")
        assert t.count(GUARD) == 1, p
        lines = t.split("\n")
        i = next(k for k, l in enumerate(lines) if l + "\n" == GUARD)
        print("   %s 删掉 3 行: %r" % (p.name, [x.strip()[:56] for x in lines[i:i + 3]]))
        del lines[i:i + 3]
        p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(BACKEND),
                       capture_output=True)
    out = r.stdout.decode("utf-8", "replace").strip().splitlines()
    print("   rc = %d" % r.returncode)
    for l in out:
        if l.startswith("FAILED"):
            print("      %s" % l[:150])
    print("   末行 = %s" % out[-1].strip())
    print("   与派单那句「2 failed, 479 passed」相符 =",
          r.returncode != 0 and out[-1].strip().startswith("2 failed, 479 passed"))
finally:
    for p, b in ORIG.items():
        p.write_bytes(b)
    print()
    print("   还原核对:", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() == SHA[p]
                          for p in (PUR, LAY)})
    print("   sha256[:16]:", {p.name: SHA[p][:16] for p in (PUR, LAY)})
print()
print("   git status --short = %r" % g("status", "--short"))
print("   HEAD = %s" % g("rev-parse", "--short", "HEAD").strip())
