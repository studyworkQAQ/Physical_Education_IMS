# -*- coding: utf-8 -*-
"""Print a byte-accurate numbered slice; usage: v04.py <path> [start] [end]"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
b = p.read_bytes()
lines = b.decode("utf-8").split("\n")
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end = int(sys.argv[3]) if len(sys.argv) > 3 else len(lines)
for i in range(start, min(end, len(lines)) + 1):
    print(f"{i:4d}| {lines[i-1].rstrip(chr(13))}")
