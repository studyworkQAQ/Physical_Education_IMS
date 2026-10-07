import pathlib, re, sys

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md")
lines = p.read_bytes().decode("utf-8").split("\n")
for i, ln in enumerate(lines, 1):
    if ln.startswith("#") and "Ruling" in ln:
        print(i, ln[:150])
