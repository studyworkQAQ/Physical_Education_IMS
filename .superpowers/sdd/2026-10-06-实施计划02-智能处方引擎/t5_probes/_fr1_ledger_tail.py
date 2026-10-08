# -*- coding: utf-8 -*-
"""只读：打印 progress.md 的尾部若干行（**绝不用编辑器工具打开它**，336 KB 会被截断写回）。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "progress.md"
raw = P.read_bytes()
text = raw.decode("utf-8")
lines = text.split("\r\n")
CRLF = chr(13) + chr(10)
BOM = b"\xef\xbb\xbf"
print(f"bytes={len(raw)} crlf={text.count(CRLF)} "
      f"bare_lf={text.count(chr(10)) - text.count(CRLF)} "
      f"bom={raw.startswith(BOM)} split_lines={len(lines)} "
      f"splitlines={len(text.splitlines())}")
n = int(sys.argv[1]) if len(sys.argv) > 1 else 70
for i in range(max(0, len(lines) - n), len(lines)):
    print(f"{i + 1}| {lines[i]}")
