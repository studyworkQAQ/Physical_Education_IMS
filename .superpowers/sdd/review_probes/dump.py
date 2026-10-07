"""Shell-口径 line-number dumper (Read tool line numbers unreliable in this repo)."""
import sys, pathlib
p = pathlib.Path(sys.argv[1])
a = int(sys.argv[2]) if len(sys.argv) > 2 else 1
b = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
L = p.read_text(encoding='utf-8').splitlines()
b = min(b, len(L))
for i in range(a - 1, b):
    print('%5d| %s' % (i + 1, L[i]))
