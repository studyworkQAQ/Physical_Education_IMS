# -*- coding: utf-8 -*-
"""print repr of specific lines"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
start, end = int(sys.argv[2]), int(sys.argv[3])
lines = p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
for i in range(start, min(end, len(lines)) + 1):
    print(f"{i:4d}| {lines[i-1]!r}")
