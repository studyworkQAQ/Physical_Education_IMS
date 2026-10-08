# -*- coding: utf-8 -*-
"""只读：打印计划正文的一个行区间（1 基，含端点），带行号。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
lines = PLAN.read_bytes().decode("utf-8").split("\r\n")
lo, hi = int(sys.argv[1]), int(sys.argv[2])
out = pathlib.Path(sys.argv[3])
buf = [f"{n}| {lines[n - 1]}" for n in range(lo, min(hi, len(lines)) + 1)]
out.write_text("\n".join(buf) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {len(buf)} lines -> {out.name}")
