import pathlib, re, sys, hashlib

root = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎")
brief = root / "task-4-brief.md"
b = brief.read_bytes()
text = b.decode("utf-8")
lines = text.split("\n")

print("=== brief: bare :NNN occurrences ===")
pat = re.compile(r"`?:\d+(?:-\d+)?`?")
n = 0
for i, ln in enumerate(lines, 1):
    for m in re.finditer(r":\d+", ln):
        s = max(0, m.start() - 45)
        e = min(len(ln), m.end() + 45)
        n += 1
        print("L%d #%d ...%s..." % (i, n, ln[s:e]))
print("total bare :NNN in brief =", n)

prog = root / "progress.md"
pb = prog.read_bytes()
print("\n=== progress.md bytes/lines/sha16 ===", len(pb), len(pb.splitlines()), hashlib.sha256(pb).hexdigest()[:16])
ptext = pb.decode("utf-8")
plines = ptext.split("\n")
print("progress.md split('\\n') count =", len(plines))

print("\n=== progress.md: Task 4 pre-flight section location ===")
for i, ln in enumerate(plines, 1):
    if "Task 4" in ln and ln.startswith("#"):
        print(i, repr(ln[:110]))
    if "Task 3 结案" in ln and ln.startswith("#"):
        print(i, repr(ln[:110]))
    if "带进 Task 4 的清单" in ln:
        print(i, repr(ln[:110]))
