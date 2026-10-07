# -*- coding: utf-8 -*-
"""Probe P6: 静态引文类陈述逐条核（文件:行 + 引文，硬规矩 #29）。"""
import subprocess, pathlib, sys
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BK = ROOT / "backend"


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8",
                          cwd=str(ROOT)).stdout


def lines(rel, rev=None):
    if rev:
        return sh("git", "-C", str(ROOT), "show", "%s:%s" % (rev, rel)).splitlines()
    return (ROOT / rel).read_text(encoding="utf-8").splitlines()


def show(rel, nums, rev=None, label=""):
    L = lines(rel, rev)
    print("  %s%s" % (rel, ("  @" + rev) if rev else ""))
    for n in nums:
        print("    %4d| %s" % (n, L[n - 1] if n - 1 < len(L) else "<越界>"))


print("=== 1. layering:18-25 —— 基线 e26347f 的 4 处 offender ===")
print(sh("git", "-C", str(ROOT), "grep", "-n", "from app.seed", "e26347f", "--",
         "backend/app/pipeline", "backend/app/db", "backend/app/domain").rstrip() or "  <0 命中>")
print("  HEAD 上同一条 grep:")
print(sh("git", "-C", str(ROOT), "grep", "-n", "from app.seed", "HEAD", "--",
         "backend/app/pipeline", "backend/app/db", "backend/app/domain").rstrip() or "    <0 命中>")

print("\n=== 2. config.py 的引文（fix round 1 新写）===")
show("backend/app/config.py", range(30, 52))
print("  --- 被引的两处 ---")
show("backend/app/adapters/factory.py", range(44, 55))
show("backend/app/adapters/mock_lepao.py", range(425, 432))

print("\n=== 3. daily.py 引的 percentile_stage 两处 ===")
show("backend/app/pipeline/percentile_stage.py", [130, 131, 132, 133, 134, 174, 175, 176, 177, 178])

print("\n=== 4. test_config.py 引的四处 ===")
show("backend/tests/adapters/test_factory.py", [30, 31, 32, 33, 34])
show("backend/app/refdata.py", [21, 22, 23, 24])
show("backend/tests/test_refdata.py", [80, 81, 82, 83, 84, 185, 186, 187, 188])
print("  --- git grep -n DEFAULT_DB_URL -- backend/tests  @ad1d190 ---")
print(sh("git", "-C", str(ROOT), "grep", "-n", "DEFAULT_DB_URL", "ad1d190", "--", "backend/tests").rstrip() or "    <0 命中>")

print("\n=== 5. layering:22-23 引的基线 offender 原文 ===")
show("backend/tests/architecture/test_layering.py", [18, 19, 20, 21, 22, 23, 24, 25, 26])
