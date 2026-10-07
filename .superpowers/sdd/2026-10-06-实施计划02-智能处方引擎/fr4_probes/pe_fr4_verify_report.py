# -*- coding: utf-8 -*-
"""pe_fr4_verify_report.py — 核 task-1-report.md 追加后的最终状态（只读，不改）。

用法: python pe_fr4_verify_report.py <仓库根>

追加已经由 pe_fr4_report.py 完成（它的前缀自检全部通过，最后一条断言把
`## fix round 4` 当子串数、而 fr4.11 的正文里也引用了这个串，故计数为 2 —— 那是断言写错、
不是追加写错）。本脚本改用**整行**口径复核。
"""
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
REPORT = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"
OLD = REPORT.read_bytes()
t = OLD.decode("utf-8")
ls = t.split("\n")

print("=== ① 文件形态 ===")
print("   bytes=%d  LF=%d  CRLF=%d  BOM=%s  乱码(U+FFFD)=%s  行数=%d"
      % (len(OLD), t.count("\n"), OLD.count(b"\r\n"), OLD.startswith(b"\xef\xbb\xbf"),
         "\ufffd" in t, len(ls)))
assert OLD.count(b"\r\n") == 0 and not OLD.startswith(b"\xef\xbb\xbf") and "\ufffd" not in t

print()
print("=== ② 整行口径的标题清点 ===")
h4 = [i for i, l in enumerate(ls, 1) if l == "## fix round 4"]
h3 = [i for i, l in enumerate(ls, 1) if l == "## fix round 3"]
print("   整行 `## fix round 4` 命中 %d 次，行号 %s" % (len(h4), h4))
print("   整行 `## fix round 3` 命中 %d 次，行号 %s" % (len(h3), h3))
assert len(h4) == 1 and len(h3) == 1 and h3[0] < h4[0]
print("   子串 `## fix round 4` 命中 %d 次（多出的一次是 fr4.11 正文里的引用）"
      % t.count("## fix round 4"))

subs = ["### fr4.%d" % i for i in range(12)]
for k in subs:
    hits = [i for i, l in enumerate(ls, 1) if l.startswith(k + " ")]
    print("   %-12s 整行命中 %d 次，行号 %s" % (k, len(hits), hits))
    assert len(hits) == 1, k

print()
print("=== ③ 旧内容一个没丢（fr1/fr2/fr3 的全部标题仍在，且顺序不变）===")
heads = re.findall(r"^#{2,4} .*$", t, re.M)
old_heads = [h for h in heads if not h.startswith("### fr4.") and h != "## fix round 4"]
print("   全部标题 %d 个；其中 fr4 新增 13 个、原有 %d 个" % (len(heads), len(old_heads)))
for k in ("## fix round 1", "## fix round 2", "## fix round 3", "## fix round 4"):
    hits = [i for i, l in enumerate(ls, 1) if l == k]
    print("   %-16s 整行命中 %d 次 %s OK" % (k, len(hits), hits))
    assert len(hits) == 1, k
for k in ("### fr3.10 本轮**没做**的事",
          "### fr2.11 本轮**没做**的事", "### fr1.9 本轮**没做**的事",
          "# Plan 02 Task 1 实施报告 — 架构债清偿"):
    assert t.count(k) == 1, k
    print("   %-34s 命中 1 次 OK" % k[:32])
i1, i2, i3, i4 = (t.index("\n## fix round %d\n" % n) for n in (1, 2, 3, 4))
assert i1 < i2 < i3 < i4, (i1, i2, i3, i4)
print("   四节的先后顺序：fr1(%d) < fr2(%d) < fr3(%d) < fr4(%d)  OK" % (i1, i2, i3, i4))

print()
print("=== ④ fr3.10 的末行仍在（追加没有截断旧内容）===")
tail3 = "- 没动 `fr2_probes/` 里的 11 个脚本（只**读**着复跑了 `pe_fr2_rule51.py`）。"
print("   命中 %d 次；它在 `## fix round 4` 之前 = %s"
      % (t.count(tail3), t.index(tail3) < t.index("\n## fix round 4\n")))
assert t.count(tail3) == 1 and t.index(tail3) < t.index("\n## fix round 4\n")

print()
print("=== ⑤ 报告不入库（禁区自证）===")
r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=str(REPO),
                   capture_output=True)
out = r.stdout.decode("utf-8")
print("   git status --short = %r" % out)
assert out == "", out
r = subprocess.run(["git", "ls-files", ".superpowers"], cwd=str(REPO), capture_output=True)
print("   git ls-files .superpowers 计数 = %d（报告在 gitignore 内，不入库）"
      % len(r.stdout.decode().split()))
assert r.stdout.decode().split() == []
print("   git log --oneline -1 = %s"
      % subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(REPO),
                       capture_output=True).stdout.decode().strip())

print()
print("报告追加复核: PASS（%d 行 / %d 字节）" % (len(ls), len(OLD)))
