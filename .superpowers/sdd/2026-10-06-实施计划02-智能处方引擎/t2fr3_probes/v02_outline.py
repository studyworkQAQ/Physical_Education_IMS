# -*- coding: utf-8 -*-
"""Dump heading outline of a markdown file with real line numbers (bytes-based)."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
b = p.read_bytes()
text = b.decode("utf-8")
lines = text.split("\n")
crlf = b.count(b"\r\n")
lf = b.count(b"\n")
print(f"# {p.name}: {len(b)} bytes / LF {lf} / CRLF {crlf} / splitlines {len(lines)}")
for i, ln in enumerate(lines, 1):
    s = ln.rstrip("\r")
    if s.startswith("#"):
        print(f"{i:5d}| {s[:200]}")
