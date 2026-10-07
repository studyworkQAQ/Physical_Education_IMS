# -*- coding: utf-8 -*-
"""P24 — 只跑落盘闸门（不改文件）。修正 p23 里 ② 的口径错。

p23 的 ② 报 FAIL，原因是它拿「本次 patch 前的文件内容」当「追加本节前的原文」来数 `## ` 标题，
而那时 p21 已经把 `## fix round 5` 追加进去了，故实数是 16 不是 15。**又是尺子的口径错、
不是文件错**（与 p21 那次同族）。正确的判据是拿 `$env:TEMP` 里的**追加速前备份**数：15 个。
"""
import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"
BAK = pathlib.Path(os.environ["TEMP"]) / "pe_fr5_report_backup.md"

raw = R.read_bytes()
t = raw.decode("utf-8")
bak = BAK.read_bytes().decode("utf-8")
SHA = hashlib.sha256(raw).hexdigest()

bak_heads = [l for l in bak.splitlines() if l.startswith("## ")]
new_heads = [l for l in t.splitlines() if l.startswith("## ")]

checks = [
    ("① 整行等于 '## fix round 5' 的行恰 1 行",
     sum(1 for l in t.splitlines() if l == "## fix round 5") == 1),
    ("② 备份里的 %d 个 '## ' 标题一个不少" % len(bak_heads),
     all(h in new_heads for h in bak_heads)),
    ("②b 新文件恰好比备份多 1 个 '## ' 标题（就是 fix round 5）",
     len(new_heads) == len(bak_heads) + 1 and new_heads[-1] == "## fix round 5"),
    ("③ 备份的 %d 行逐字仍是新文件的前 %d 行" % (len(bak.splitlines()), len(bak.splitlines())),
     bak.splitlines() == t.splitlines()[:len(bak.splitlines())]),
    ("④ CRLF 仍为 0", raw.count(b"\r\n") == 0),
    ("⑤ 本节没有追加两遍（'### 9. 本轮探针清单' 恰 1 次）",
     t.count("### 9. 本轮探针清单") == 1),
    ("⑥ 修正后的自述在、被判定口径错的那句不在",
     t.count("整行等于本节标题的行恰 1 行") == 1
     and t.count("落盘后复核\n「`## fix round 5` 恰出现 1 次」") == 0),
    ("⑦ 8 条 finding 的小节标题齐全（1.1..1.9，共 9 个：Ruling 67 拆两条）",
     all(("#### 1.%d " % i) in t for i in range(1, 10))),
    ("⑧ 变异验收 7 相位 M0..M6 都在", all(("**M%d**" % i) in t for i in range(0, 7))),
    ("⑨ CE-fr5-1..9 都在", all(("CE-fr5-%d" % i) in t for i in range(1, 10))),
]
ok = True
print("=== task-1-report.md 落盘闸门（只读，不改文件）===")
for name, res in checks:
    print("  %s %s" % ("OK  " if res else "FAIL", name))
    ok = ok and res
print()
print("  备份（追加速前）: %d LF 行 / %d B / sha256[:16] %s / '## ' 标题 %d 个"
      % (len(bak.splitlines()), len(BAK.read_bytes()),
         hashlib.sha256(BAK.read_bytes()).hexdigest()[:16], len(bak_heads)))
print("  现在            : %d LF 行 / %d B / sha256[:16] %s / '## ' 标题 %d 个 / CRLF %d"
      % (len(t.splitlines()), len(raw), SHA[:16], len(new_heads), raw.count(b"\r\n")))
print()
print("  git status --short =", repr(subprocess.run(["git", "status", "--short"], cwd=str(ROOT),
      capture_output=True).stdout.decode("utf-8", "replace")))
print("  HEAD =", subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
      capture_output=True).stdout.decode().strip())
print()
print("闸门结论:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
