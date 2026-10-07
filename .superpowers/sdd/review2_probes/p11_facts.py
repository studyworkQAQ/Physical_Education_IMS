import os, sys, hashlib, json, sqlite3, types, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
import yaml
from app.domain.indicators import ITEM_BUCKET, ScoredItem
from app.domain import prescription as pkg
from app.domain.prescription import exercises as ex
from app.domain.prescription import templates as tp
from app.domain.prescription.exercises import (ImpactLevel, ExerciseSpec, EquivalenceMapping,
                                               EquivalenceTable, IMPACT_RANK, TARGET_DOMAIN,
                                               EQUIVALENCE_TRIGGERS)

def H(t): print("\n" + "="*72 + "\n## " + t + "\n" + "="*72)

H("E1.1 PyYAML duplicate top-level key")
r = yaml.safe_load("a: 1\na: 2")
print("yaml.safe_load('a: 1\\na: 2') =", r, "== {'a': 2} ->", r == {"a": 2})

H("E1.2 MappingProxyType is not a dict instance")
mp = types.MappingProxyType({})
print("isinstance(MappingProxyType({}), dict) =", isinstance(mp, dict))

H("E1.3 str()/len of a str-subclass Enum member")
s = str(ImpactLevel.HIGH)
print("str(ImpactLevel.HIGH) =", repr(s), " len =", len(s))
print("ImpactLevel.HIGH == 'high' ->", ImpactLevel.HIGH == "high")
print("repr =", repr(ImpactLevel.HIGH), " format =", format(ImpactLevel.HIGH))
print("len('ImpactLevel.HIGH') literal count =", len("ImpactLevel.HIGH"))

H("E1.4 raw sqlite3 storage of a str-subclass enum (no sqlalchemy)")
con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, lv VARCHAR(8))")
con.execute("INSERT INTO t (lv) VALUES (?)", (ImpactLevel.HIGH,))
row = con.execute("SELECT lv, typeof(lv), length(lv) FROM t").fetchone()
print("stored value =", repr(row[0]), " typeof =", row[1], " sqlite length() =", row[2])
con.execute("INSERT INTO t (lv) VALUES (?)", (str(ImpactLevel.HIGH),))
print("if explicitly str(): ", repr(con.execute("SELECT lv, length(lv) FROM t WHERE id=2").fetchone()))

H("E1.5 lexicographic order of the str-enum")
print("ImpactLevel.HIGH < ImpactLevel.LOW < ImpactLevel.MEDIUM ->",
      ImpactLevel.HIGH < ImpactLevel.LOW < ImpactLevel.MEDIUM)
print("'high' < 'low' < 'medium' ->", "high" < "low" < "medium")
print("[m.value for m in ImpactLevel] =", [m.value for m in ImpactLevel])
print("len(ImpactLevel) =", len(ImpactLevel))
print("sorted(ImpactLevel) values =", [m.value for m in sorted(ImpactLevel)])

H("E1.6 ITEM_BUCKET distinct values (P2-A4)")
raw = set(ITEM_BUCKET.values())
print("len(set(ITEM_BUCKET.values())) =", len(raw), " ->", sorted(repr(v) for v in raw))
print("None in raw ->", None in raw)
print("ITEM_BUCKET[ScoredItem.BMI] is None ->", ITEM_BUCKET[ScoredItem.BMI] is None)
print("TARGET_DOMAIN ==", set(TARGET_DOMAIN), " len", len(TARGET_DOMAIN), " None in it ->", None in TARGET_DOMAIN)
print("len(ITEM_BUCKET) =", len(ITEM_BUCKET))
print("short-board items (bucket is not None) =", sorted(i.name for i,b in ITEM_BUCKET.items() if b is not None))

H("E1.7 public namespaces")
print("pkg.__all__ =", pkg.__all__, " len", len(pkg.__all__))
print("sorted(dir(pkg)) public =", sorted(n for n in dir(pkg) if not n.startswith('_')))
print("  ^ NOTE: this process already imported both submodules, so both appear.")
import subprocess
code = ("import sys; sys.path.insert(0,r'%s');"
        "from app.domain import prescription as p;"
        "print(sorted(n for n in dir(p) if not n.startswith('_')))" % BACKEND)
fr = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=BACKEND)
print("FRESH interpreter dir(pkg) public =", fr.stdout.decode().strip(), fr.stderr.decode()[:200])
code2 = ("import sys; sys.path.insert(0,r'%s');"
         "from app.domain.prescription import exercises as e;"
         "print(sorted(n for n in dir(e) if not n.startswith('_')))" % BACKEND)
fr2 = subprocess.run([sys.executable, "-c", code2], capture_output=True, cwd=BACKEND)
print("FRESH interpreter dir(exercises) public =", fr2.stdout.decode().strip())
try:
    print("STANDING_JUMP bucket =", ITEM_BUCKET[ScoredItem.STANDING_JUMP],
          " SIT_AND_REACH bucket =", ITEM_BUCKET[ScoredItem.SIT_AND_REACH])
except AttributeError as e:
    print("ScoredItem member missing:", e, "members =", [m.name for m in ScoredItem])
pub_ex = sorted(n for n in dir(ex) if not n.startswith('_'))
print("sorted(dir(exercises)) public =", pub_ex, " len", len(pub_ex))
print("templates.__all__ =", tp.__all__, " templates.ImpactLevel is exercises.ImpactLevel ->", tp.ImpactLevel is ex.ImpactLevel)
print("IMPACT_RANK =", {k.value: v for k, v in IMPACT_RANK.items()})
print("EQUIVALENCE_TRIGGERS =", sorted(EQUIVALENCE_TRIGGERS), type(EQUIVALENCE_TRIGGERS).__name__)

H("E1.8 AST 支5 reproduction on the REAL exercises.py")
import ast, pathlib
tree = ast.parse(pathlib.Path(ex.__file__).read_text(encoding="utf-8"))
defined = {n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and not n.name.startswith("_")} | \
          {t.id for n in tree.body if isinstance(n,(ast.Assign,ast.AnnAssign))
                for t in (n.targets if isinstance(n,ast.Assign) else [n.target])
                if isinstance(t,ast.Name) and not t.id.startswith("_")}
BASELINE = ["EQUIVALENCE_TRIGGERS","IMPACT_RANK","TARGET_DOMAIN","EquivalenceMapping","EquivalenceTable","ExerciseSpec","ImpactLevel"]
print("defined =", sorted(defined), " count", len(defined))
print("defined == set(baseline) ->", defined == set(BASELINE))
print("sorted(baseline) != baseline ->", sorted(BASELINE) != BASELINE)
print("list(pkg.__all__) == BASELINE ->", list(pkg.__all__) == BASELINE)

H("E1.9 exercises.py import surface")
src = pathlib.Path(ex.__file__).read_text(encoding="utf-8")
t2 = ast.parse(src)
for n in t2.body:
    if isinstance(n, ast.Import):
        print("  Import   ", [a.name for a in n.names], "line", n.lineno)
    if isinstance(n, ast.ImportFrom):
        print("  ImportFrom level=%s module=%s names=%s line=%s" % (n.level, n.module, [a.name for a in n.names], n.lineno))
srcT = pathlib.Path(tp.__file__).read_text(encoding="utf-8")
for n in ast.parse(srcT).body:
    if isinstance(n, ast.ImportFrom):
        print("  templates.py ImportFrom level=%s module=%s names=%s line=%s" % (n.level, n.module, [a.name for a in n.names], n.lineno))
srcI = pathlib.Path(pkg.__file__).read_text(encoding="utf-8")
for n in ast.parse(srcI).body:
    if isinstance(n, ast.ImportFrom):
        print("  __init__.py ImportFrom level=%s module=%s names=%d line=%s" % (n.level, n.module, len(n.names), n.lineno))
