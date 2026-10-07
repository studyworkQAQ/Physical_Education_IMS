# -*- coding: utf-8 -*-
"""pe_fr4_edit3.py — 去掉一个没有占位符的 f 前缀（风格，两个文件各一处）。

用法: python pe_fr4_edit3.py <仓库根>
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
FILES = [REPO / "backend/tests/architecture/test_domain_purity.py",
         REPO / "backend/tests/architecture/test_layering.py"]
OLD = '                f"（parts[:-1] 被写成了 parts）"'
NEW = '                "（parts[:-1] 被写成了 parts）"'

for p in FILES:
    raw = p.read_bytes()
    t = raw.decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), p
    lf = t.replace("\r\n", "\n")
    if lf.count(OLD) == 0 and lf.count(NEW) == 1:
        print("  %-22s 已是新文本，跳过（幂等）" % p.name)
        continue
    assert lf.count(OLD) == 1, (p.name, lf.count(OLD))
    p.write_bytes(lf.replace(OLD, NEW).replace("\n", "\r\n").encode("utf-8"))
    back = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
    b = p.read_bytes()
    print("  %-22s bytes=%d CRLF=%d 裸LF=%d 新串=%d 旧串=%d"
          % (p.name, len(b), b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"),
             back.count(NEW), back.count(OLD)))
    assert back.count(NEW) == 1 and back.count(OLD) == 0
print("完成")
