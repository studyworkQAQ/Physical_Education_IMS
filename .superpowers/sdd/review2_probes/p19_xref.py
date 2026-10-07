import os, re, pathlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
def rd(p): return open(p,'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace").split("\n")
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("K1 spec 1.3 (p95 < 3 s / traceability)")
S = rd(os.path.join(ROOT, r"Document\2026-09-28-体育闭环原型-设计spec.md"))
for i,s in enumerate(S,1):
    if re.search(r"p95|1\.3|可追溯", s) and i < 80: print("  spec:%4d| %s" % (i, s[:240]))
print("  --- section heading lines ---")
for i,s in enumerate(S,1):
    if s.startswith("### 1.3") or s.startswith("## 1"): print("  spec:%4d| %s" % (i, s[:200]))

H("K2 app/domain/tables.py: StandardTable.segments type")
T = rd(os.path.join(B,"app","domain","tables.py"))
for i,s in enumerate(T,1):
    if "segments" in s or "Mapping" in s: print("  tables.py:%3d| %s" % (i, s[:180]))

H("K3 app/db/repo.py upsert: flush-not-commit / PATCH semantics")
R = rd(os.path.join(B,"app","db","repo.py"))
for i,s in enumerate(R,1):
    if re.search(r"def upsert|flush|commit|PATCH|natural|自然键", s): print("  repo.py:%3d| %s" % (i, s[:200]))

H("K4 refdata.py load_standard docstring region 130-160")
F = rd(os.path.join(B,"app","refdata.py"))
for n in range(128,160): print("  refdata.py:%3d| %s" % (n, F[n-1][:190]))

H("K5 test_models.py 350-380 (the '11 columns' prose + empty-loop guard)")
M = rd(os.path.join(B,"tests","db","test_models.py"))
for n in range(350,382): print("  test_models.py:%3d| %s" % (n, M[n-1][:200]))

H("K6 _shared.py 1-30")
SH = rd(os.path.join(B,"app","db","models","_shared.py"))
for n in range(1,31): print("  _shared.py:%3d| %s" % (n, SH[n-1][:200]))

H("K7 derived.py trend column width (Ruling 144 fix state)")
D = rd(os.path.join(B,"app","db","models","derived.py"))
for i,s in enumerate(D,1):
    if re.search(r"trend", s): print("  derived.py:%3d| %s" % (i, s[:180]))
