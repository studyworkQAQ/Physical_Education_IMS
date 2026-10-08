# -*- coding: utf-8 -*-
"""只读：按计划正文的行号打印若干行（1 基），并打印 P5-A10 / P5-A2 / 5.5 / 5.3 的上下文。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"

raw = PLAN.read_bytes()
text = raw.decode("utf-8")
lines = text.split("\r\n")
print(f"bytes={len(raw)} split_lines={len(lines)} splitlines={len(text.splitlines())}")

want = [int(a) for a in sys.argv[1:]]
for n in want:
    print("-" * 90)
    print(f"[{n}] {lines[n - 1]}")
