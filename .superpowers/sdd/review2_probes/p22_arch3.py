import os, sys, ast, pathlib, subprocess, importlib.util
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(B); sys.path.insert(0,B)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
tl = load("tl", os.path.join(B,"tests","architecture","test_layering.py"))
td = load("td", os.path.join(B,"tests","architecture","test_domain_purity.py"))
BACKEND = pathlib.Path(B)

H("M3b the 'fix round 5 亲跑' block values")
print("  purity   _package_of(BACKEND/'app/domain/prescription/match.py') =",
      td._package_of(BACKEND / 'app/domain/prescription/match.py'))
print("  layering _package_of(BACKEND/'app/domain/prescription/match.py') =",
      tl._package_of(BACKEND / 'app/domain/prescription/match.py'))
print("  purity   _absolute('indicators',2,('app','domain','prescription'),'X') =",
      repr(td._absolute('indicators',2,('app','domain','prescription'),'X')))
print("  layering _absolute('indicators',2,('app','domain','prescription'),'X') =",
      repr(tl._absolute('indicators',2,('app','domain','prescription'),'X')))
print("  purity   _is_allowed('app.domain.indicators') =", td._is_allowed('app.domain.indicators'))
print("  layering _is_forbidden('app.domain.indicators') =", tl._is_forbidden('app.domain.indicators'))
from importlib.util import resolve_name
print("  resolve_name('..indicators','app.domain.prescription') =", resolve_name('..indicators','app.domain.prescription'))

H("M4 which app/domain modules import an absolute 'app.*' string? (claim: '既有 4 个 domain 模块全部用绝对串')")
cnt = 0
for p in sorted(pathlib.Path('app/domain').rglob('*.py')):
    src = p.read_text(encoding='utf-8')
    ab = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and n.module.startswith("app."):
            ab.append((n.lineno, n.module))
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("app."): ab.append((n.lineno, a.name))
    print("  %-44s absolute app.* imports = %s" % (str(p), ab))
    if ab and "prescription" not in str(p): cnt += 1
print("  pre-existing (non-prescription) domain modules that use an absolute app.* string =", cnt)

H("M5 ordinal-7 stability across revs (git ls-tree + git show, no checkout)")
os.chdir(ROOT)
def blob(rev, path):
    r = subprocess.run(["git","show",rev+":"+path],capture_output=True)
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
                rows.append((p[len("backend/"):].replace("/","\\"), n.lineno, n.level, n.module))
    l7 = rows[6] if len(rows) >= 7 else "N/A"
    print("  %-8s total=%2d  line7=%s" % (rev, len(rows), l7))

H("M6 the empty-scan lower bounds (P2-D4: layering >= 8 at :172, purity >= 5)")
ls = pathlib.Path(os.path.join(B,"tests","architecture","test_layering.py")).read_text(encoding="utf-8").split("\n")
ps = pathlib.Path(os.path.join(B,"tests","architecture","test_domain_purity.py")).read_text(encoding="utf-8").split("\n")
for i,s in enumerate(ls,1):
    if ">= 8" in s or "空转" in s: print("  layering:%4d| %s" % (i, s.strip()[:190]))
for i,s in enumerate(ps,1):
    if ">= 5" in s or "空转" in s: print("  purity  :%4d| %s" % (i, s.strip()[:190]))
