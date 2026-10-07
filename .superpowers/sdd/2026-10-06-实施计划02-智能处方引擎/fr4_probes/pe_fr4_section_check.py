# -*- coding: utf-8 -*-
"""pe_fr4_section_check.py — 核 SECTION_fix_round_4.md 的每一次编辑是否真的落盘。

用法: python pe_fr4_section_check.py <仓库根>
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
P = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr4_probes/SECTION_fix_round_4.md"
t = P.read_bytes().decode("utf-8")

CHECKS = [
    ("A 脚本计数", "11 个 + 3 份输出", "9 个 + 3 份输出"),
    ("B 段区间", ":313-362", ":312-362"),
    ("C 三条计数", "另有 17 处", "其余 12 处"),
    ("D #51 闸门", "各 50 行、只有 4 行不同", "（同结构、同 4 个形状"),
    ("E fr4.7 标题", "4 条成立 + 1 条账本错误 + 2 条不计入", "1 条不成立/已限定"),
    ("F ④ Read", "对自己都不自洽", "没有一处是 −1"),
    ("G #54 行号", "#54 `:588`", "#54 `:587`"),
    ("H ② 行数", "各 14 行，purity", "各 15 行"),
]
bad = []
for name, new, old in CHECKS:
    cn, co = t.count(new), t.count(old)
    ok = cn == 1 and co == 0
    print("  %-14s 新串命中=%d 旧串命中=%d  %s" % (name, cn, co, "OK" if ok else "!! 未落盘"))
    if not ok:
        bad.append(name)
print("未落盘项 = %d / %d  %s" % (len(bad), len(CHECKS), bad))
print("文件 bytes=%d 行数=%d CRLF=%d" % (len(t.encode("utf-8")), len(t.split("\n")),
                                      P.read_bytes().count(b"\r\n")))
