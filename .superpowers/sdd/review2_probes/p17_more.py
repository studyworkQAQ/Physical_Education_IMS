import os, subprocess, re, sys, ast
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)
BACKEND = os.path.join(ROOT,"backend")
def blob(rev, path):
    r = subprocess.run(["git","show",f"{rev}:{path}"],capture_output=True)
    return None if r.returncode else r.stdout.replace(b"\r\n",b"\n")
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("I1 line counts of the three files the dispatch quotes sizes for")
FILES = ["backend/app/refdata_prescription.py","backend/tests/test_refdata_prescription.py",
         "backend/app/domain/prescription/__init__.py","backend/app/domain/prescription/templates.py",
         "backend/app/domain/prescription/exercises.py","backend/tests/domain/test_prescription_templates.py"]
revs = ["3ea27cc","c21767d","966eae0","HEAD"]
print("  %-58s %s" % ("file", "  ".join("%9s" % r for r in revs)))
for f in FILES:
    row = []
    for rev in revs:
        b = blob(rev,f)
        row.append("%9s" % ("-" if b is None else b.count(b"\n")))
    print("  %-58s %s" % (f, "  ".join(row)))

H("I2 _is_allowed verdicts for exercises.py's four imports (run the REAL guard function)")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND,"tests","architecture"))
import importlib.util
spec = importlib.util.spec_from_file_location("tdp", os.path.join(BACKEND,"tests","architecture","test_domain_purity.py"))
tdp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tdp)
print("  ALLOWED_MODULES =", sorted(tdp.ALLOWED_MODULES), " n =", len(tdp.ALLOWED_MODULES))
print("  ALLOWED_PACKAGE =", repr(tdp.ALLOWED_PACKAGE))
for mod in ("collections.abc","dataclasses","enum","app.domain.indicators"):
    try:
        print("  _is_allowed(%-24r) = %s" % (mod, tdp._is_allowed(mod)))
    except TypeError as e:
        print("  _is_allowed signature:", e)
print("  _is_allowed('sqlalchemy') =", tdp._is_allowed("sqlalchemy"))
print("  _is_allowed('app.seed') =", tdp._is_allowed("app.seed"))
print("  DOMAIN files scanned =", len(tdp._domain_files()))
for p in sorted(tdp._domain_files()): print("     ", p.name if hasattr(p,'name') else p)
spec2 = importlib.util.spec_from_file_location("tl", os.path.join(BACKEND,"tests","architecture","test_layering.py"))
tl = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(tl)
print("  layering SCANNED_DIRS =", tl.SCANNED_DIRS, " FORBIDDEN_PREFIX =", repr(tl.FORBIDDEN_PREFIX))
tot = 0
for d in tl.SCANNED_DIRS:
    n = len(list(tl._py_files(d))); tot += n
    print("  layering _py_files(%r) = %d" % (d, n))
print("  layering total scanned .py =", tot)
print("  layering _is_forbidden('app.db.seed') =", tl._is_forbidden("app.db.seed"))
print("  purity   _is_allowed('app.db.seed')   =", tdp._is_allowed("app.db.seed"))
print("  layering _is_forbidden('app.seed.x') =", tl._is_forbidden("app.seed.x"))

H("I3 app/{pipeline,db,domain} .py counts (ledger Ruling 101: 7 + 11 + 9 = 27)")
for d in ("pipeline","db","domain"):
    n = sum(1 for _ in __import__("pathlib").Path(os.path.join(BACKEND,"app",d)).rglob("*.py"))
    print("  app/%-9s = %d" % (d, n))
n = sum(1 for _ in __import__("pathlib").Path(os.path.join(BACKEND,"app","domain","prescription")).rglob("*.py"))
print("  app/domain/prescription = %d" % n)

H("I4 _MODELS_PUBLIC_BASELINE length + test_models prose about the in_domain column count")
tm = open(os.path.join(BACKEND,"tests","db","test_models.py"),'rb').read().replace(b"\r\n",b"\n").decode("utf-8")
t = ast.parse(tm)
for node in t.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0],'id','')=="_MODELS_PUBLIC_BASELINE":
        print("  _MODELS_PUBLIC_BASELINE literal length =", len(node.value.elts))
for i,s in enumerate(tm.split("\n"),1):
    if re.search(r"恰好|列\b.*\d+|\d+ 列", s) and 340 <= i <= 420:
        print("  :%4d| %s" % (i, s.strip()[:200]))

H("I5 Plan 01 ledger: do Rulings 19 / 28 / 144 / 213 / 231 exist and say what is claimed?")
p1 = open(r".superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md",'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace")
L1 = p1.split("\n")
print("  Plan01 ledger lines =", len(L1), " bytes =", len(open(r'.superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md','rb').read()))
for n in (19,28,144,213,231):
    hits = [(i,s) for i,s in enumerate(L1,1) if re.search(r"Ruling %d\b" % n, s)]
    print("  Ruling %-4d -> %d mention(s); first at line %s" % (n, len(hits), hits[0][0] if hits else None))
    if hits: print("        %s" % hits[0][1][:220])
hr = [(i,s) for i,s in enumerate(L1,1) if re.match(r"^.*硬规矩 #\d+", s)]
nums = sorted({int(m) for s in L1 for m in re.findall(r"硬规矩 #(\d+)", s)})
print("  hard-rule numbers mentioned in Plan01 ledger: min=%s max=%s count=%d" % (nums[0], nums[-1], len(nums)))
print("  does Plan01 define #18 #19 #29 #30 #32 #35 #39 #42 ? ->",
      {n: len(re.findall(r"硬规矩 #%d\b" % n, p1)) for n in (18,19,29,30,32,35,39,42)})

H("I6 Plan 02 ledger: hard rules #48..#71 definitions")
p2 = open(r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md",'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace")
for n in list(range(48,72)):
    d = len(re.findall(r"补硬规矩 #%d" % n, p2)) + len(re.findall(r"硬规矩 #%d 修订" % n, p2)) + len(re.findall(r"硬规矩 #%d：" % n, p2))
    print("  #%d : definition-ish mentions = %d" % (n, d))
print("  'Ruling 48' occurrences =", len(re.findall(r"Ruling 48\b", p2)))
