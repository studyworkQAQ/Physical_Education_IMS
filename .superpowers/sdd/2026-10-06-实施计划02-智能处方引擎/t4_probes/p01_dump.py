import pathlib, sys

p = pathlib.Path(sys.argv[1])
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
text = p.read_bytes().decode("utf-8")
lines = text.split("\n")
for i, ln in enumerate(lines, 1):
    if start <= i <= end:
        print("%4d| %s" % (i, ln))
