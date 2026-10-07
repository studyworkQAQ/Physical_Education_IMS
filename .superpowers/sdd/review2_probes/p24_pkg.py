import os, re, subprocess, pathlib, hashlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(ROOT)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)
def blob(rev,path):
    r = subprocess.run(["git","show",rev+":"+path],capture_output=True)
    return None if r.returncode else r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace")

H("O1 app/db/models/prescription.py:11 at fb5bddb (the name reference P2-A6 pointed at)")
L = blob("fb5bddb","backend/app/db/models/prescription.py").split("\n")
for n in range(1,17): print("  fb5bddb :%3d| %s" % (n, L[n-1][:200]))
print("  --- repo-wide residue of the old test name ---")
r = subprocess.run(["git","grep","-n","test_all_fourteen_tables_created","--","."],capture_output=True)
print("  git grep test_all_fourteen_tables_created ->", repr(r.stdout.decode("utf-8","replace")) or "(none)")
r = subprocess.run(["git","grep","-n","fourteen","--","backend"],capture_output=True)
print("  git grep 'fourteen' in backend ->", repr(r.stdout.decode("utf-8","replace"))[:400])
r = subprocess.run(["git","grep","-n","test_all_fifteen_tables_created","--","backend"],capture_output=True)
print("  git grep test_all_fifteen_tables_created ->")
print("   ", r.stdout.decode("utf-8","replace").strip().replace("\n","\n    "))

H("O2 app/seed touched at all in fb5bddb..966eae0 ?")
r = subprocess.run(["git","diff","--name-status","fb5bddb..966eae0","--","backend/app/seed"],capture_output=True)
print("  name-status app/seed ->", repr(r.stdout.decode()))
r = subprocess.run(["git","diff","--name-status","fb5bddb..966eae0","--","backend/data/national_standard_2014.csv","backend/data/indicator_ranges.yaml","backend/data/README_national_standard.md"],capture_output=True)
print("  name-status other backend/data files ->", repr(r.stdout.decode()))
r = subprocess.run(["git","diff","--name-status","fb5bddb..966eae0","--",".gitattributes",".gitignore"],capture_output=True)
print("  name-status .gitattributes/.gitignore ->", repr(r.stdout.decode()))
print("  .gitattributes identical fb5bddb vs HEAD ->",
      blob("fb5bddb",".gitattributes") == blob("HEAD",".gitattributes"))

H("O3 review package fidelity: does its embedded YAML full text equal the real files?")
pkg = open(os.path.join(ROOT,r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review-package.md"),'rb').read().replace(b"\r\n",b"\n").decode("utf-8").split("\n")
def section(start_marker, end_marker):
    s = next(i for i,x in enumerate(pkg) if x.startswith(start_marker))
    e = next(i for i in range(s+1,len(pkg)) if pkg[i].startswith(end_marker))
    return s,e
for marker, path in (("### backend/data/exercises.yaml","backend/data/exercises.yaml"),
                     ("### backend/data/exercise_equivalence.yaml","backend/data/exercise_equivalence.yaml")):
    s = next(i for i,x in enumerate(pkg) if x.startswith(marker))
    # find the fenced block after s
    f1 = next(i for i in range(s,s+20) if pkg[i].strip().startswith("```"))
    f2 = next(i for i in range(f1+1,len(pkg)) if pkg[i].strip().startswith("```"))
    emb = "\n".join(pkg[f1+1:f2])
    real = open(os.path.join(B,"..",path),'rb').read().replace(b"\r\n",b"\n").decode("utf-8").rstrip("\n")
    print("  %-46s pkg lines %d..%d  identical=%s  emb_len=%d real_len=%d" %
          (path, f1+2, f2, emb == real, len(emb), len(real)))
    if emb != real:
        el, rl = emb.split("\n"), real.split("\n")
        print("     emb lines=%d real lines=%d" % (len(el), len(rl)))
        for i in range(min(len(el),len(rl))):
            if el[i]!=rl[i]:
                print("     first diff at %d:\n       emb : %r\n       real: %r" % (i+1, el[i][:120], rl[i][:120])); break

H("O4 review package: are the git sections faithful? (re-run and compare)")
def run(*a):
    return subprocess.run(["git"]+list(a),capture_output=True).stdout.replace(b"\r\n",b"\n").decode("utf-8","replace")
checks = {
 "git log --oneline": run("log","--oneline","fb5bddb..966eae0").strip(),
 "git diff --stat": run("diff","--stat","fb5bddb..966eae0").strip(),
 "git diff --name-status": run("diff","--name-status","fb5bddb..966eae0").strip(),
}
pkgtxt = "\n".join(pkg)
for k,v in checks.items():
    print("  %-26s embedded-in-package=%s" % (k, v in pkgtxt))

H("O5 count of tests Task 2 added")
def testnames(rev, path):
    s = blob(rev,path)
    if s is None: return set()
    return set(re.findall(r"^def (test_\w+)", s, re.M))
for path in ("backend/tests/test_refdata_prescription.py","backend/tests/domain/test_prescription_templates.py"):
    now = testnames("HEAD",path); before = testnames("fb5bddb",path)
    print("  %-58s HEAD=%2d  fb5bddb=%2d  new=%2d" % (path, len(now), len(before), len(now-before)))
import ast
def param_count(path):
    src = open(os.path.join(B,path),'rb').read().replace(b"\r\n",b"\n").decode("utf-8")
    t = ast.parse(src); tot = 0; details=[]
    for n in t.body:
        if isinstance(n,(ast.FunctionDef,)) and n.name.startswith("test_"):
            k = 1
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func,'attr','')=="parametrize":
                    k = len(d.args[1].elts)
            tot += k; details.append((n.name,k))
    return tot, details
for path in ("tests/test_refdata_prescription.py","tests/domain/test_prescription_templates.py"):
    tot, det = param_count(path)
    print("  %-46s collected test cases = %d" % (path, tot))
    for n,k in det:
        if k>1: print("      %-72s x%d" % (n,k))
