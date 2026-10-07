# -*- coding: utf-8 -*-
"""Print a byte-accurate line slice of a file: python v03_slice.py <path> <start> <end>"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
start = int(sys.argv[2])
end = int(sys.argv[3])
b = p.read_bytes()
lines = b.decode("utf-8").split("\n")
for i in range(start, min(end, len(lines)) + 1):
    print(f"{i:5d}| {lines[i-1].rstrip(chr(13))}")
