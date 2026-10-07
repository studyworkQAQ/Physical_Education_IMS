# -*- coding: utf-8 -*-
"""Probe P15: 零散的计数/行尾/口径核。"""
import pathlib, subprocess, re
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")

rep = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"
b = rep.read_bytes()
print("=== task-1-report.md 的行数口径（计划正文 :24 说「实为 2616 个 LF 行」）===")
print("  bytes = %d ; \\n 计数 = %d ; \\r\\n 计数 = %d ; splitlines() = %d"
      % (len(b), b.count(b"\n"), b.count(b"\r\n"), len(b.decode("utf-8").splitlines())))

plan = ROOT / "Document/2026-10-06-实施计划02-智能处方引擎.md"
pl = plan.read_text(encoding="utf-8").splitlines()
print("\n=== 计划正文 Global Constraints 的 bullet 数（:13 说「十条」）===")
i = next(k for k, l in enumerate(pl) if l.startswith("## Global Constraints"))
j = next(k for k in range(i + 1, len(pl)) if pl[k].startswith("## "))
n = sum(1 for l in pl[i + 1:j] if l.startswith("- "))
print("  区间 :%d-:%d ；顶层 bullet = %d ；:13 原文「%s」" % (
    i + 1, j, n, [x for x in pl[12].split("，") if "条见 Global" in x or "最要命" in x]))
print("  :13 全文尾部:", pl[12][-70:])

print("\n=== 评审包自证 ===")
pkg = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-fixchain-review-package.md"
pb = pkg.read_bytes()
print("  行数 = %d （派单说 1308）; 字节 = %d （派单说 90750）" % (len(pb.decode("utf-8").splitlines()), len(pb)))

print("\n=== 评审包「生产代码命中（必须为空）」那一节的原文 ===")
L = pb.decode("utf-8").splitlines()
k = next(i for i, l in enumerate(L) if "生产代码命中" in l)
for i in range(k, min(k + 8, len(L))):
    print("  %5d| %s" % (i + 1, L[i]))

print("\n=== 评审包的 diff 与 git 实际输出是否一致（逐字节，不经 PowerShell 管道）===")
sec = []
started = False
for l in L:
    if l.startswith("## git diff -U10"):
        started = True
        continue
    if started:
        if l.strip() == "```diff":
            continue
        if l.strip() == "```" and sec:
            break
        if sec or l.startswith("diff --git"):
            sec.append(l)
actual = subprocess.run(["git", "-C", str(ROOT), "diff", "-U10", "ad1d190..6784d57"],
                        capture_output=True).stdout.decode("utf-8").splitlines()
print("  包内 diff 行数 = %d ; git 实跑 = %d ; 逐行相等 = %s"
      % (len(sec), len(actual), sec == actual))
if sec != actual:
    for i, (a, c) in enumerate(zip(sec, actual)):
        if a != c:
            print("   第一处不同在第 %d 行:" % (i + 1))
            print("     包内: %r" % a[:160])
            print("     git : %r" % c[:160])
            break
    print("   长度差:", len(sec) - len(actual))

print("\n=== HEAD/工作树自证 ===")
for cmd in (["git", "rev-parse", "--short", "HEAD"], ["git", "status", "--short"],
            ["git", "branch", "--show-current"]):
    r = subprocess.run(["git", "-C", str(ROOT)] + cmd[1:], capture_output=True,
                       text=True, encoding="utf-8")
    print("  %-28s -> %r" % (" ".join(cmd), r.stdout.strip()))
print("  backend/pe.db 存在 =", (ROOT / "backend/pe.db").exists())
print("  backend/data/seed 文件数 =", len(list((ROOT / "backend/data/seed").glob("*"))))
print("  .superpowers 被忽略 =", bool(subprocess.run(
    ["git", "-C", str(ROOT), "check-ignore", ".superpowers/sdd/review_probes/p15.py"],
    capture_output=True).stdout))
