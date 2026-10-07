# -*- coding: utf-8 -*-
"""P15 — 硬规矩 #56 自查：本轮新增文字里，凡出现判定/颜色/后果词，逐句检查有没有主语。"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
d = subprocess.run(["git", "-c", "core.quotepath=false", "diff", "-U0", "HEAD"],
                   cwd=ROOT, capture_output=True)
text = d.stdout.decode("utf-8", "replace")
cur = None
added = []
for line in text.splitlines():
    if line.startswith("+++ b/"):
        cur = line[6:]
    elif line.startswith("+") and not line.startswith("+++"):
        added.append((cur, line[1:]))

WORDS = ("GREEN", "RED", "假绿", "放行", "变红", "变绿", "全绿", "全红", "offender", "真绿")
SUBJ = ("本文件", "本守卫", "purity", "layering", "test_domain_purity", "test_layering",
        "那一份", "两份", "第一条守卫", "第二条守卫", "第三条守卫", "第二三条守卫",
        "第一", "第二", "第三", "它", "那一格", "这一格", "同一格", "新格", "那一档",
        "这一档", "探针", "本测试", "对照", "尺子", "G1", "G2", "G3")

print("新增行总数 =", len(added))
print()
hits = 0
nosub = []
for f, l in added:
    if any(w in l for w in WORDS):
        hits += 1
        has = any(s in l for s in SUBJ)
        print("  %s %-24s | %s" % ("有主语" if has else "**无主语**", pathlib.Path(f).name, l.strip()[:150]))
        if not has:
            nosub.append((f, l))
print()
print("含判定/颜色/后果词的新增行 = %d ; 其中本轮内**行内**没有主语词的 = %d" % (hits, len(nosub)))
print()
print("=== 无主语词的逐条上下文（主语可能在前一行，需人工判）===")
for f, l in nosub:
    idx = [i for i, (ff, ll) in enumerate(added) if ff == f and ll == l][0]
    lo = max(0, idx - 3)
    hi = min(len(added), idx + 2)
    print("  --- %s" % pathlib.Path(f).name)
    for j in range(lo, hi):
        mark = ">>" if j == idx else "  "
        print("   %s %s" % (mark, added[j][1].strip()[:150]))
