import pathlib, re, sys

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md")
lines = p.read_bytes().decode("utf-8").split("\n")
pats = sys.argv[1:]
for i, ln in enumerate(lines, 1):
    for pat in pats:
        if re.search(pat, ln):
            print("L%d [%s] %s" % (i, pat, ln[:400]))
            break
