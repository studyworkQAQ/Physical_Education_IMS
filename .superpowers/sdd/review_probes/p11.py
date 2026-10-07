# -*- coding: utf-8 -*-
"""Probe P11: 剩余散文陈述 + fix 链改动面（哪些当前行是 + 行）。"""
import subprocess, pathlib, re, ast, collections
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True).stdout.decode("utf-8")


print("=== 1. fix 链改动面：当前文件里哪些行是 ad1d190..6784d57 的 + 行 ===")
for rel in FILES:
    d = git("diff", "-U0", "ad1d190..6784d57", "--", rel).splitlines()
    added, removed = [], 0
    newln = 0
    for line in d:
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            newln = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append(newln); newln += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    # 压缩成区间
    ranges = []
    for n in added:
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    print("  %-46s +行 %d / -行 %d" % (rel, len(added), removed))
    print("    区间:", ", ".join("%d-%d" % (a, b) if a != b else str(a) for a, b in ranges))

print("\n=== 2. 基线 ad1d190 的 _dotted docstring（purity:483-488 说『此前写着…那句是假的』）===")
base = git("show", "ad1d190:backend/tests/architecture/test_domain_purity.py").splitlines()
for i, l in enumerate(base, 1):
    if "唯一途径" in l or "那不是漏洞" in l or "顺着" in l:
        print("  base:%4d| %s" % (i, l))
print("  --- 基线 purity 里 open 的正则 / FORBIDDEN_CALLS ---")
for i, l in enumerate(base, 1):
    if "bopen" in l or "FORBIDDEN_CALLS" in l or re.search(r"r[\"'].*open", l):
        print("  base:%4d| %s" % (i, l))
print("  --- 基线 e26347f 的 FORBIDDEN_CALLS ---")
b2 = git("show", "e26347f:backend/tests/architecture/test_domain_purity.py").splitlines()
for i, l in enumerate(b2, 1):
    if "FORBIDDEN_CALLS" in l or "bopen" in l or "open" in l and "=" in l:
        print("  e26347f:%4d| %s" % (i, l))

print("\n=== 3. purity:400-403 —— 终审 A 的「domain 经两跳依赖 app.refdata」 ===")
print("  基线 e26347f 的 domain 里是否出现 app.refdata 的 import：")
for f in git("ls-tree", "-r", "--name-only", "e26347f", "--", "backend/app/domain").split():
    src = subprocess.run(["git", "-C", str(ROOT), "show", "e26347f:" + f],
                         capture_output=True).stdout.decode("utf-8")
    for i, l in enumerate(src.splitlines(), 1):
        if "refdata" in l:
            print("    %s:%d| %s" % (f.split("/")[-1], i, l.strip()[:120]))

print("\n=== 4. purity 里「三条|第三条|两道」的命中数（报告 fr4.2 说全文件 19 处）===")
cur = (ROOT / FILES[0]).read_text(encoding="utf-8").splitlines()
hits = [(i, l) for i, l in enumerate(cur, 1) if re.search(r"三条|第三条|两道", l)]
print("  HEAD 命中 %d 处，行号: %s" % (len(hits), [h[0] for h in hits]))

print("\n=== 5. 墙钟算术（daily.py:226-232）===")
b = [20.48, 20.85]; h = [20.89, 21.18]
mb = sum(b) / 2; mh = sum(h) / 2
print("  基线均值   = %.6f  -> 源码写 20.66 ; round(%.3f,2)=%.2f ; 截断=%.2f" % (mb, mb, round(mb, 2), int(mb * 100) / 100))
print("  本Task均值 = %.6f  -> 源码写 21.03 ; round(%.3f,2)=%.2f ; 截断=%.2f" % (mh, mh, round(mh, 2), int(mh * 100) / 100))
print("  基线组内极差 = %.4f (源码 0.37) ；本Task组内极差 = %.4f (源码 0.29)" % (b[1] - b[0], h[1] - h[0]))
print("  差 = %.6f s (源码 +0.37) ；百分比 = %.4f%% (源码 +1.8%%)" % (mh - mb, (mh - mb) / mb * 100))
print("  60 / 21.18 = %.6f  (源码 2.83×)  ；60 / 21.03 = %.4f" % (60 / 21.18, 60 / mh))

print("\n=== 6. test_models.py:596-616 的算术 ===")
A, B = 0.2708, 0.2941
a, b2_ = 5423104, 6791168
print("  B/A = %.6f -> 源码 1.086 ；慢 %.2f%% -> 源码 8.6%%" % (B / A, (B / A - 1) * 100))
print("  体积差 = %d B (源码 +1 368 064) ；= %.4f%% (源码 +25.23%%)" % (b2_ - a, (b2_ - a) / a * 100))
print("  500*112 = %d (源码 56000)" % (500 * 112))
print("  区间 [0.1385,0.9031] 与 [0.1698,1.0212] 重叠 = %s" % (0.1698 <= 0.9031,))
print("  四次 B/A = 1.086 / 0.944 / 1.019 / 0.989 -> 跨过 1.0 = %s ; 区间 %.3f-%.3f" % (
    min(1.086, 0.944, 1.019, 0.989) < 1 < max(1.086, 0.944, 1.019, 0.989),
    min(1.086, 0.944, 1.019, 0.989), max(1.086, 0.944, 1.019, 0.989)))
