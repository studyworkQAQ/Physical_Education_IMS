import pathlib, re, sys

p = pathlib.Path(sys.argv[1])
lines = p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
for pat in sys.argv[2:]:
    print("=== %s ===" % pat)
    hits = 0
    for i, ln in enumerate(lines, 1):
        if re.search(pat, ln):
            hits += 1
            print("  L%d| %s" % (i, ln[:200]))
    if hits == 0:
        print("  (0 hits)")
