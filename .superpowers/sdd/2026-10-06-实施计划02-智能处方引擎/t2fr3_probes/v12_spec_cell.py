# -*- coding: utf-8 -*-
"""Print the exact repr of the '编号冲突' cell portion of spec line 933."""
import pathlib

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
p = ROOT / "Document/2026-09-28-体育闭环原型-设计spec.md"
lines = p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
ln = lines[932]  # 1-based 933
print("full line length =", len(ln))
idx = ln.find("⚠️ **编号冲突")
print("index of the warning =", idx)
print("cells count (pipe splits) =", ln.count("|"))
print()
print("TAIL repr:")
print(repr(ln[idx:]))
print()
print("PREFIX last 120 chars repr:")
print(repr(ln[max(0, idx-120):idx]))
