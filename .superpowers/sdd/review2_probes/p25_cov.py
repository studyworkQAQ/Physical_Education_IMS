import os, re, pathlib, ast, sys
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("P1 coverage's percent formatting rule: does 441 stmts / Miss 2 / 120 br / BrPart 0 print as 99%?")
try:
    from coverage.numbers import Numbers
    import inspect
    print("  Numbers signature:", str(inspect.signature(Numbers.__init__))[:400])
    n = Numbers(n_files=1, n_statements=441, n_excluded=0, n_missing=2,
                n_branches=120, n_partial_branches=0, n_missing_branches=0)
    print("  pc_covered =", n.pc_covered)
    for attr in dir(n):
        if "str" in attr or attr.startswith("pc"):
            try: print("   ", attr, "=", getattr(n, attr))
            except Exception as e: print("   ", attr, "err", e)
except Exception as e:
    print("  Numbers import failed:", type(e).__name__, e)

H("P2 JsonText columns across app/db/models (claim: 9)")
tot = 0
for p in sorted(pathlib.Path(os.path.join(B,"app","db","models")).glob("*.py")):
    src = p.read_text(encoding="utf-8")
    hits = [(i,s.strip()) for i,s in enumerate(src.split("\n"),1) if re.search(r"mapped_column\(JsonText", s)]
    if hits:
        print("  %-16s %d" % (p.name, len(hits)))
        for i,s in hits: print("      :%4d| %s" % (i, s[:120]))
        tot += len(hits)
print("  TOTAL mapped_column(JsonText) =", tot)

H("P3 String(n) columns of Exercise vs YAML maxima (static)")
src = pathlib.Path(os.path.join(B,"app","db","models","prescription.py")).read_text(encoding="utf-8")
t = ast.parse(src)
cls = next(n for n in t.body if isinstance(n, ast.ClassDef) and n.name=="Exercise")
cols = []
for n in cls.body:
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
        call = ast.unparse(n.value)
        cols.append((n.target.id, n.lineno, call))
for c in cols: print("  %-14s :%3d  %s" % (c[0], c[1], c[2]))
print("  String(n) columns =", sum(1 for c in cols if "String(" in c[2]),
      " JsonText columns =", sum(1 for c in cols if "JsonText" in c[2]),
      " total columns =", len(cols))
maxima = {"ref":29, "name":12, "video_url":62, "impact_level":6, "equipment":13}
for name, ln, call in cols:
    m = re.search(r"String\((\d+)\)", call)
    if m and name in maxima:
        print("  %-12s String(%s) >= %-3d -> %s" % (name, m.group(1), maxima[name], int(m.group(1)) >= maxima[name]))

H("P4 _in_domain CHECK text for impact_level (generated statically)")
quoted = ", ".join("'" + v.replace("'","''") + "'" for v in sorted({"high","medium","low"}))
print("  impact_level IN (%s)" % quoted)

H("P5 exercises.yaml: non-comment non-blank lines = 23 entries x 6 lines?")
txt = pathlib.Path(os.path.join(B,"data","exercises.yaml")).read_text(encoding="utf-8")
nb = [l for l in txt.split("\n") if l.strip() and not l.lstrip().startswith("#")]
print("  non-comment non-blank lines =", len(nb), " = 23*6 ->", len(nb)==138)
print("  first entry block:", nb[0:6])
