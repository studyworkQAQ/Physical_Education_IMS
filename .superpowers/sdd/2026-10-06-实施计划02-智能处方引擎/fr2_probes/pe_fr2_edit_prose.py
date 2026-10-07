# -*- coding: utf-8 -*-
"""pe_fr2_edit_prose.py — Minor 2（test_models.py）与 Minor 4（daily.py）。只动散文。"""
import pathlib
import sys

BACKEND = pathlib.Path(sys.argv[1]).resolve()

EDITS = [
    # ---- Minor 2：表头那两个点值的标签就地改，不删数
    ("tests/db/test_models.py",
     "    场景                             单次墙钟中位 (ms)    ``.db`` 字节        EXPLAIN QUERY PLAN\n",
     "    场景                        单次墙钟中位 (ms，单次采样、方向不可复现)   ``.db`` 字节   EXPLAIN QUERY PLAN\n"),
    # ---- Minor 2：撤回在 11–15 行之下，只读到这一行的人会引一个已被本文件撤回的数
    ("tests/db/test_models.py",
     "    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，两个场景各自\n",
     "    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%——⚠️ **这个方向不可复现**，\n"
     "    是机器/负载噪声，四次连跑的值见下方「复跑」那一段；两个场景各自\n"),
    # ---- Minor 4：0.38 从同行给出的两个数算不出来（20.85 − 20.48 = 0.37）
    ("app/pipeline/daily.py",
     "    基线 **20.48 / 20.85 s**（均值 20.66、组内极差 0.38 s），本 Task 之后\n",
     "    基线 **20.48 / 20.85 s**（均值 20.66、组内极差 20.85 − 20.48 = 0.37 s；两个样本\n"
     "    各自只记到百分位，故极差也只能给到这个精度），本 Task 之后\n"),
]


def main():
    per_file = {}
    for rel, old, new in EDITS:
        per_file.setdefault(rel, []).append((old, new))
    for rel, pairs in per_file.items():
        path = BACKEND / rel
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        crlf = raw.count(b"\r\n")
        assert crlf == text.count("\n"), (rel, "不是纯 CRLF", crlf, text.count("\n"))
        norm = text.replace("\r\n", "\n")
        for i, (old, new) in enumerate(pairs):
            n = norm.count(old)
            assert n == 1, "%s 第 %d 处命中 %d 次（应为 1）:\n%r" % (rel, i, n, old[:120])
            norm = norm.replace(old, new)
        out = norm.replace("\n", "\r\n").encode("utf-8")
        path.write_bytes(out)
        print("已写 %-32s %d 处替换  %d -> %d 字节  CRLF %d" %
              (rel, len(pairs), len(raw), len(out), out.count(b"\r\n")))


main()
