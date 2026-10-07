"""Shell-口径 grep with line numbers."""
import sys, re, pathlib
pat = re.compile(sys.argv[1])
paths = [pathlib.Path(x) for x in sys.argv[2:]]
for p in paths:
    if p.is_dir():
        continue
    L = p.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(L):
        if pat.search(line):
            print('%s:%d| %s' % (p.name, i + 1, line))
