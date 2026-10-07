import os, re, ast, subprocess, pathlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(ROOT)
def rd(p): return open(p,'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace").split("\n")
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("L1 _MODELS_PUBLIC_BASELINE full literal (33 names) and the four names cited in prose")
tm = open(os.path.join(B,"tests","db","test_models.py"),'rb').read().replace(b"\r\n",b"\n").decode("utf-8")
t = ast.parse(tm)
for node in t.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0],'id','')=="_MODELS_PUBLIC_BASELINE":
        names = [e.value for e in node.value.elts]
        print("  n =", len(names)); print("  ", names)
        for q in ("dt","json","Boolean","mapped_column"):
            print("  contains %-14s -> %s" % (q, q in names))

H("L2 Plan01 Ruling 144 body (does it say '7 个任务'?)")
p1 = rd(os.path.join(ROOT, r".superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md"))
for n in range(1585, 1605):
    print("  p1:%5d| %s" % (n, p1[n-1][:250]))

H("L3 git diff fb5bddb..966eae0 -- tests/architecture/test_domain_purity.py")
r = subprocess.run(["git","diff","-U6","fb5bddb..966eae0","--","backend/tests/architecture/test_domain_purity.py"],capture_output=True)
print(r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace"))

H("L4 git diff fb5bddb..966eae0 -- tests/architecture/test_layering.py")
r = subprocess.run(["git","diff","-U6","fb5bddb..966eae0","--","backend/tests/architecture/test_layering.py"],capture_output=True)
print(r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace"))
