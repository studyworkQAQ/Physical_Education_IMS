import ast, pathlib, collections

BACKEND = pathlib.Path("backend")
rows = []
for p in sorted((BACKEND / "app").rglob("*.py")):
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows.append((p.as_posix(), n.lineno, n.level, n.module, [a.name for a in n.names]))

print("total ImportFrom with level>0 (nodes) =", len(rows))
lvl = collections.Counter(r[2] for r in rows)
print("level distribution =", dict(lvl))
bypkg = collections.Counter(pathlib.Path(r[0]).parent.as_posix() for r in rows)
print("by dir =", dict(bypkg))
for r in rows:
    print("   ", r)

# 也数一下 tests/ 下的相对导入（守卫扫的是 app/，但「全仓」口径要弄清）
rows2 = []
for p in sorted(BACKEND.rglob("*.py")):
    if p.parts[1] == "app":
        continue
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows2.append((p.as_posix(), n.lineno, n.level, n.module))
print("\noutside app/: nodes =", len(rows2))
for r in rows2:
    print("   ", r)

# 扫描面
SCANNED_DIRS = ("pipeline", "db", "domain")
tot = 0
for d in SCANNED_DIRS:
    n = len(list((BACKEND / "app" / d).rglob("*.py")))
    tot += n
    print("app/%s -> %d .py" % (d, n))
print("SCANNED total =", tot)
print("app/domain .py list:", [p.relative_to(BACKEND).as_posix() for p in sorted((BACKEND/'app'/'domain').rglob('*.py'))])
