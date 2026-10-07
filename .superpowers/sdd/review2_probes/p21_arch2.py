import os, sys, ast, pathlib, subprocess, importlib.util, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(B); sys.path.insert(0,B)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("M1 the exact command quoted in both guards, run on the working tree (= c21767d for app/)")
rows = []
for p in sorted(pathlib.Path('app').rglob('*.py')):
    for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows.append((str(p), n.lineno, n.level, n.module))
for i,(p,ln,lv,mod) in enumerate(rows,1):
    mark = "   <== line 7" if i == 7 else ""
    print("  %2d| %s %d %d %s%s" % (i,p,ln,lv,mod,mark))
print("  TOTAL =", len(rows))
byd = {}
for p,ln,lv,mod in rows: byd.setdefault("/".join(p.replace("\\","/").split("/")[:-1]),0); byd["/".join(p.replace("\\","/").split("/")[:-1])]+=1
print("  by dir =", byd)
print("  level distribution =", {k: sum(1 for r in rows if r[2]==k) for k in sorted({r[2] for r in rows})})
print("  module-None count =", sum(1 for r in rows if r[3] is None))

H("M2 how many relative imports does app/db/models/__init__.py have? (claim: 7, None-last)")
src = pathlib.Path('app/db/models/__init__.py').read_text(encoding='utf-8')
rel = [(n.lineno, n.level, n.module) for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.level]
print("  count =", len(rel), " ->", rel)

H("M3 _absolute / _is_forbidden / _is_allowed verbatim checks")
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
tl = load("tl", os.path.join(B,"tests","architecture","test_layering.py"))
td = load("td", os.path.join(B,"tests","architecture","test_domain_purity.py"))
print("  layering _absolute('exercises', 1, ('app','domain','prescription')) =",
      repr(tl._absolute('exercises', 1, ('app','domain','prescription'))))
print("  purity   _absolute('exercises', 1, ('app','domain','prescription')) =",
      repr(td._absolute('exercises', 1, ('app','domain','prescription'))))
print("  layering _is_forbidden('app.db.models._shared') =", tl._is_forbidden('app.db.models._shared'))
print("  layering _is_forbidden('app.domain.prescription.exercises') =", tl._is_forbidden('app.domain.prescription.exercises'))
print("  purity   _is_allowed('app.domain.prescription.exercises') =", td._is_allowed('app.domain.prescription.exercises'))
print("  layering _absolute('seed', 5, ('app','db','models'), 'generate') =",
      repr(tl._absolute('seed', 5, ('app','db','models'), 'generate')))
print("  layering _absolute('', 2, ('app','pipeline'), 'seed') =",
      repr(tl._absolute('', 2, ('app','pipeline'), 'seed')))
print("  purity   _package_of(app/domain/prescription/match.py) =",
      td._package_of(pathlib.Path('app/domain/prescription/match.py')))
try:
    import importlib
    rn = importlib.import_module('importlib.util')
    from importlib.util import resolve_name
    print("  resolve_name('..indicators','app.domain.prescription') =", resolve_name('..indicators','app.domain.prescription'))
except Exception as e:
    print("  resolve_name err:", e)

H("M4 which pre-existing app/domain modules import an absolute 'app.*' string? (claim: 4)")
for p in sorted(pathlib.Path('app/domain').rglob('*.py')):
    src = p.read_text(encoding='utf-8')
    absolutes = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and n.module.startswith("app."):
            absolutes.append((n.lineno, n.module))
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("app."): absolutes.append((n.lineno, a.name))
    if absolutes: print("  %-40s %s" % (str(p), absolutes))

H("M5 ordinal-7 stability across the four revs (emulated with git ls-tree + git show)")
os.chdir(ROOT)
def blob(rev, path):
    r = subprocess.run(["git","show",f"{rev}:{path}"],capture_output=True)
    return None if r.returncode else r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace")
for rev in ("6a2938f","7b84599","3ea27cc","c21767d","966eae0"):
    r = subprocess.run(["git","ls-tree","-r","--name-only",rev,"backend/app"],capture_output=True)
    paths = sorted(x for x in r.stdout.decode().splitlines() if x.endswith(".py"))
    rows = []
    for p in paths:
        s = blob(rev,p)
        if s is None: continue
        try: t = ast.parse(s)
        except SyntaxError: continue
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom) and n.level:
                rows.append((p.replace("backend/","").replace("/","\\"), n.lineno, n.level, n.module))
    print("  %-8s total=%2d  line7=%s" % (rev, len(rows), rows[6] if len(rows)>=7 else "N/A"))
