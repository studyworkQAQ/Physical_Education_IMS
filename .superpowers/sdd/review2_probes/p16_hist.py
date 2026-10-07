import os, subprocess, re, ast, hashlib, pathlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)
def blob(rev, path):
    r = subprocess.run(["git","show",f"{rev}:{path}"],capture_output=True)
    if r.returncode != 0: return None
    return r.stdout.replace(b"\r\n", b"\n").decode("utf-8","replace")
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("H1  test_models.py at HEAD: what is at :163 / :228 / :472 (the numbers printed in prose)")
cur = blob("HEAD","backend/tests/db/test_models.py").split("\n")
for n in (163,169,228,236,472,494):
    print("  HEAD :%4d| %s" % (n, cur[n-1][:180]))
old = blob("fb5bddb","backend/tests/db/test_models.py").split("\n")
print("  --- at fb5bddb (pre-Task2) ---")
for n in (163,228,472):
    print("  fb5b :%4d| %s" % (n, old[n-1][:180]))

H("H2  models.py line count at e26347f (docstring claims '676 行')")
m = blob("e26347f","backend/app/db/models.py")
print("  exists ->", m is not None, " lines(LF) ->", (m.count("\n") if m else None))

H("H3  refdata.py load_standard/standard line numbers at fb5bddb vs HEAD")
for rev in ("fb5bddb","HEAD"):
    t = blob(rev,"backend/app/refdata.py").split("\n")
    hits = [(i,s.strip()) for i,s in enumerate(t,1) if s.startswith("def load_standard") or s.startswith("def standard")]
    print("  %-9s -> %s" % (rev, hits))

H("H4  _IMPACT_RANK / IMPACT_RANK residence at 3ea27cc and c21767d")
for rev in ("3ea27cc","c21767d","HEAD"):
    a = blob(rev,"backend/app/refdata_prescription.py") or ""
    b = blob(rev,"backend/app/domain/prescription/exercises.py")
    print("  %-8s refdata_prescription: _IMPACT_RANK=%d IMPACT_RANK=%d | exercises.py exists=%s IMPACT_RANK=%d _IMPACT_RANK=%d"
          % (rev, len(re.findall(r"_IMPACT_RANK", a)), len(re.findall(r"(?<!_)\bIMPACT_RANK\b", a)),
             b is not None, (len(re.findall(r"(?<!_)\bIMPACT_RANK\b", b)) if b else -1),
             (len(re.findall(r"_IMPACT_RANK", b)) if b else -1)))
    if rev == "3ea27cc" and a:
        for i,s in enumerate(a.split("\n"),1):
            if "_IMPACT_RANK" in s: print("      3ea27cc refdata_prescription.py:%d| %s" % (i, s.strip()[:150]))

H("H5  the 7 objects at 3ea27cc (refdata_prescription) vs HEAD (exercises.py)")
a = blob("3ea27cc","backend/app/refdata_prescription.py")
names = ["ImpactLevel","ExerciseSpec","EquivalenceMapping","EquivalenceTable","TARGET_DOMAIN","EQUIVALENCE_TRIGGERS","_IMPACT_RANK","IMPACT_RANK"]
def toplevel_defs(src):
    t = ast.parse(src)
    out = []
    for n in t.body:
        if isinstance(n,(ast.ClassDef,ast.FunctionDef)): out.append((n.lineno, n.name))
        elif isinstance(n,(ast.Assign,ast.AnnAssign)):
            for tg in (n.targets if isinstance(n,ast.Assign) else [n.target]):
                if isinstance(tg,ast.Name): out.append((n.lineno, tg.id))
    return out
print("  3ea27cc refdata_prescription.py top-level:", toplevel_defs(a))
b = blob("HEAD","backend/app/domain/prescription/exercises.py")
print("  HEAD    exercises.py top-level:", toplevel_defs(b))
print("  HEAD    refdata_prescription.py top-level:", toplevel_defs(blob("HEAD","backend/app/refdata_prescription.py")))
print("  HEAD    templates.py top-level:", toplevel_defs(blob("HEAD","backend/app/domain/prescription/templates.py")))

H("H6  domain/prescription/__init__.py line count at 3ea27cc (dispatch says '12 行')")
for rev in ("3ea27cc","c21767d","HEAD"):
    t = blob(rev,"backend/app/domain/prescription/__init__.py")
    print("  %-8s lines=%d  bytes=%d" % (rev, t.count("\n"), len(t.encode('utf-8'))))
    if rev == "3ea27cc":
        for i,s in enumerate(t.split("\n"),1): print("      %2d| %s" % (i, s[:120]))

H("H7  repo-wide relative imports in backend/app at 4 revs (ledger: 12 / 12 / 14 / 15)")
def rel_imports(rev):
    out = []
    r = subprocess.run(["git","ls-tree","-r","--name-only",rev,"backend/app"],capture_output=True)
    for p in r.stdout.decode().splitlines():
        if not p.endswith(".py"): continue
        src = blob(rev,p)
        if src is None: continue
        try: t = ast.parse(src)
        except SyntaxError: continue
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom) and n.level and n.level > 0:
                out.append((p, n.lineno, n.level, n.module, [a.name for a in n.names]))
    return out
for rev in ("6a2938f","7b84599","3ea27cc","c21767d","HEAD"):
    ri = rel_imports(rev)
    bypkg = {}
    for p,ln,lv,mod,nm in ri:
        bypkg.setdefault("/".join(p.split("/")[:-1]), 0)
        bypkg["/".join(p.split("/")[:-1])] += 1
    print("  %-8s total=%2d  by-dir=%s" % (rev, len(ri), bypkg))
    if rev in ("3ea27cc","c21767d","HEAD"):
        for p,ln,lv,mod,nm in ri:
            if "prescription" in p: print("        %s:%d level=%d module=%s names=%s" % (p,ln,lv,mod,nm))

H("H8  ALLOWED_MODULES / ALLOWED_PACKAGE across revs (was the allow-list widened?)")
for rev in ("fb5bddb","3ea27cc","c21767d","HEAD"):
    t = blob(rev,"backend/tests/architecture/test_domain_purity.py")
    for i,s in enumerate(t.split("\n"),1):
        if s.startswith("ALLOWED_MODULES") or s.startswith("ALLOWED_PACKAGE"):
            print("  %-8s :%4d| %s" % (rev, i, s[:200]))
    # find the assignment block end
    m = re.search(r"ALLOWED_MODULES[^=]*=\s*frozenset\(\{(.*?)\}\)", t, re.S)
    if m:
        items = re.findall(r'"([^"]+)"', m.group(1))
        print("           -> %d module strings: %s" % (len(items), items))
