# -*- coding: utf-8 -*-
"""pe_fr4_edit5.py — 给 fr4.11 补一句：那段引用块是**修自述之前**那次跑的输出，
最终字节数要另给（否则报告里就留了一个已被自己改过时的数，正是 Ruling 29/Minor 2 的形态）。

用法: python pe_fr4_edit5.py <仓库根>
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
REPORT = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

OLD = """这与硬规矩 #53 是同一族：**尺子坏了要和被测对象坏了指认得一样清楚**。"""
NEW = """这与硬规矩 #53 是同一族：**尺子坏了要和被测对象坏了指认得一样清楚**。

（⚠️ 上面那个引用块是**修本节这三处自述之前**那次跑的输出，故它写的 `3278 行 / 241269 字节`
已经过时——`pe_fr4_edit4.py` 之后复跑 `pe_fr4_verify_report.py` 仍是 **PASS**，最终
**3294 行 / 242876 字节 / LF 3293 / CRLF 0**，`git status --short` = `''`、HEAD = `6784d57`。
把一个已被自己改过时的数留在报告里，正是账本 Ruling 29 / 评审 Minor 2 要消灭的形态，故就地标注。）"""

raw = REPORT.read_bytes()
t = raw.decode("utf-8")
assert t.count("\r\n") == 0
assert t.count(OLD) == 1, t.count(OLD)
t = t.replace(OLD, NEW)

OLD_CNT = "**15 个 `pe_fr4_*.py` + 3 份 `OUT_*.txt` + 2 份报告草稿 = 20 个条目**"
NEW_CNT = "**16 个 `pe_fr4_*.py` + 3 份 `OUT_*.txt` + 2 份报告草稿 = 21 个条目**"
assert t.count(OLD_CNT) == 1, t.count(OLD_CNT)
t = t.replace(OLD_CNT, NEW_CNT)
REPORT.write_bytes(t.encode("utf-8"))

d = REPORT.parent / "fr4_probes"
fs = sorted(x.name for x in d.iterdir())
npy = sum(1 for f in fs if f.endswith(".py"))
print("  fr4_probes 实数：条目 %d = .py %d + OUT %d + SECTION %d"
      % (len(fs), npy, sum(1 for f in fs if f.startswith("OUT_")),
         sum(1 for f in fs if f.startswith("SECTION"))))
assert (len(fs), npy) == (21, 16), (len(fs), npy)

back = REPORT.read_bytes().decode("utf-8")
b = REPORT.read_bytes()
print("  新串命中=%d 旧串命中=%d（旧串是新串的子串，故应为 1）" % (back.count(NEW), back.count(OLD)))
print("  脚本个数新串命中=%d 旧串命中=%d" % (back.count(NEW_CNT), back.count(OLD_CNT)))
print("  bytes=%d LF=%d CRLF=%d 行数=%d" % (len(b), back.count("\n"), b.count(b"\r\n"),
                                          len(back.split("\n"))))
assert back.count(NEW) == 1 and back.count(OLD) == 1
assert back.count(NEW_CNT) == 1 and back.count(OLD_CNT) == 0
print("补充落盘完成")
