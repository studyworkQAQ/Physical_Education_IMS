# -*- coding: utf-8 -*-
"""pe_fr4_edit2.py — 两处**注释**的精度修正（超出派单，主动披露）。

用法: python pe_fr4_edit2.py <仓库根>

理由：fix round 3 留下的注释写「**本轮**的改动面被钉死在『**新增**这一条测试函数』之内」，
而 fix round 4 之后那条函数既不是「新增」的、也不再是「本轮」钉死的那一条。注释不进 AST，
故逐顶层单元的 AST 自证看不见它；但它会被读到，且现在读起来是错的（Ruling 32 的
「同一缺陷类就近修正」）。改成引 Ruling 46/57 的口径，不再说「本轮」。
"""
import pathlib
import sys
import unicodedata

REPO = pathlib.Path(sys.argv[1]).resolve()
FILES = [REPO / "backend/tests/architecture/test_domain_purity.py",
         REPO / "backend/tests/architecture/test_layering.py"]

OLD_A = "    # 就地 import：模块级 import 会改动本文件的 <module-level>，而本轮的改动面被钉死在"
NEW_A = "    # 就地 import：模块级 import 会改动本文件的 <module-level>，故这条测试自 fix round 3"
OLD_B1 = "    # 「新增这一条测试函数 + _absolute docstring 的一处机制更正」之内（Plan02 Ruling 46）。"
OLD_B2 = "    # 「新增这一条测试函数」之内（Plan02 Ruling 46）。"
NEW_B = ("    # 起就把 import 留在函数体内、改动面也一直钉死在「这一条测试函数 + docstring」\n"
         "    # 之内（Plan02 Ruling 46/57）。")


def width(line):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)


for p in FILES:
    raw = p.read_bytes()
    t = raw.decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), p
    lf = t.replace("\r\n", "\n")
    if lf.count(OLD_A) == 0 and lf.count(NEW_A) == 1:
        print("  %-22s 已经是新文本，跳过（幂等）" % p.name)
        continue
    assert lf.count(OLD_A) == 1, (p.name, "A", lf.count(OLD_A))
    n_b1, n_b2 = lf.count(OLD_B1), lf.count(OLD_B2)
    assert n_b1 + n_b2 == 1, (p.name, n_b1, n_b2)
    for new in [NEW_A] + NEW_B.split("\n"):
        assert width(new) <= 100, (new, width(new))
    lf = lf.replace(OLD_A, NEW_A).replace(OLD_B1, NEW_B).replace(OLD_B2, NEW_B)
    p.write_bytes(lf.replace("\n", "\r\n").encode("utf-8"))
    b = p.read_bytes()
    back = b.decode("utf-8").replace("\r\n", "\n")
    print("  %-22s bytes=%d CRLF=%d 裸LF=%d  新串命中=%d 旧串命中=%d"
          % (p.name, len(b), b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"),
             back.count(NEW_A) + back.count(NEW_B),
             back.count(OLD_A) + back.count(OLD_B1) + back.count(OLD_B2)))
    assert back.count(NEW_A) == 1 and back.count(NEW_B) == 1
    assert back.count(OLD_A) == back.count(OLD_B1) == back.count(OLD_B2) == 0
print("两处注释修正落盘完成；新行显示宽度上限 100（含 CJK 双宽）")
