# -*- coding: utf-8 -*-
"""Where are the bare-LF lines in task-2-report.md?"""
import pathlib

p = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
                 r"\.superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-report.md")
b = p.read_bytes()
CRLF = bytes([13, 10])
LF = bytes([10])
print(f"total {len(b)} B ; LF {b.count(LF)} ; CRLF {b.count(CRLF)} ; bare LF {b.count(LF)-b.count(CRLF)}")
bare = []
i = 0
lineno = 0
while i < len(b):
    if b[i:i+1] == LF:
        lineno += 1
        if b[i-1:i] != bytes([13]):
            bare.append(lineno)
        i += 1
    else:
        i += 1
print(f"bare-LF line numbers ({len(bare)}): {bare}")
print(f"last line number = {lineno}")
print(f"file ends with newline = {b.endswith(LF)} ; ends with CRLF = {b.endswith(CRLF)}")
print(f"tail 200 bytes repr: {b[-200:]!r}")
