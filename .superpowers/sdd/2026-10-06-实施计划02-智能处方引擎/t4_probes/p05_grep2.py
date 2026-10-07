import pathlib, re, sys

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md")
lines = p.read_bytes().decode("utf-8").split("\n")
pat = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 400
for i, ln in enumerate(lines, 1):
    if re.search(pat, ln):
        print("---- L%d ----" % i)
        print(ln[:width])
