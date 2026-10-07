import os, re, subprocess, pathlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(ROOT)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)
FILES = ["tests/architecture/test_layering.py","tests/architecture/test_domain_purity.py"]
def rd(rel, rev=None):
    p = rel if rev is None else None
    if rev is None:
        return open(os.path.join(B,rel),'rb').read().replace(b"\r\n",b"\n").decode("utf-8").split("\n")
    r = subprocess.run(["git","show",rev+":backend/"+rel],capture_output=True)
    return r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace").split("\n")

H("N1 grep '12 条' in both guards (ledger: purity 1 残留, layering 2 残留, all rev-bound)")
for rel in FILES:
    L = rd(rel)
    hits = [(i,s) for i,s in enumerate(L,1) if "12 条" in s]
    print("  %-46s -> %d hit(s)" % (rel, len(hits)))
    for i,s in hits: print("     :%4d| %s" % (i, s.strip()[:230]))

H("N2 grep ':74' / ' 74 1 None' / '__init__.py:74' residue (ledger: 0 残留 in both)")
for rel in FILES:
    L = rd(rel)
    for pat in [r"__init__\.py:74", r"__init__\.py 74 1 None", r":74\b"]:
        hits = [(i,s) for i,s in enumerate(L,1) if re.search(pat, s)]
        print("  %-46s pattern %-26s -> %d" % (rel, pat, len(hits)))
        for i,s in hits: print("       :%4d| %s" % (i, s.strip()[:200]))

H("N3 where was 'assert len(scanned) >= 8' at e09e5f6 / fb5bddb? (P2-D4 cites :172)")
for rev in ("e09e5f6","fb5bddb","HEAD"):
    L = rd("tests/architecture/test_layering.py", rev)
    hits = [(i,s.strip()) for i,s in enumerate(L,1) if "len(scanned) >= 8" in s]
    print("  %-8s total_lines=%4d  hits=%s" % (rev, len(L)-1, hits))
    if rev == "e09e5f6":
        for n in (170,171,172,173):
            print("      e09e5f6 :%4d| %s" % (n, L[n-1][:200]))

H("N4 git diff --stat for the two guards across the three Task 2 commits")
for a,b in (("fb5bddb","3ea27cc"),("3ea27cc","c21767d"),("c21767d","966eae0")):
    r = subprocess.run(["git","diff","--stat",a+".."+b,"--","backend/tests/architecture/"],capture_output=True)
    print("  %s..%s" % (a,b))
    print("   ", r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace").strip().replace("\n","\n    "))

H("N5 the spec.md diff (fb5bddb..966eae0) - is it exactly one added row, CRLF preserved?")
r = subprocess.run(["git","diff","--numstat","fb5bddb..966eae0","--","Document/"],capture_output=True)
print(r.stdout.decode("utf-8","replace"))
spec_rel = "Document/2026-09-28-体育闭环原型-设计spec.md"
for rev in ("fb5bddb","HEAD"):
    b = subprocess.run(["git","show",rev+":"+spec_rel],capture_output=True).stdout
    wt = open(os.path.join(ROOT,spec_rel),'rb').read()
    print("  %-8s blob bytes=%7d crlf=%5d lf=%5d bare_lf=%d" % (rev, len(b), b.count(b"\r\n"), b.count(b"\n"), b.count(b"\n")-b.count(b"\r\n")))
    if rev=="HEAD":
        print("  HEAD worktree bytes=%7d crlf=%5d lf=%5d bare_lf=%d" % (len(wt), wt.count(b"\r\n"), wt.count(b"\n"), wt.count(b"\n")-wt.count(b"\r\n")))
        print("  HEAD blob == worktree bytes ->", b == wt)
r = subprocess.run(["git","diff","fb5bddb..966eae0","--",spec_rel],capture_output=True)
d = r.stdout.replace(b"\r\n",b"\n").decode("utf-8","replace")
print("  diff line count =", d.count("\n"))
for line in d.split("\n"):
    if line.startswith(("+","-","@@")) and not line.startswith(("+++","---")):
        print("   ", line[:180])
