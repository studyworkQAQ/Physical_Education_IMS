import os, sys, pathlib, shutil, tempfile, subprocess, hashlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
BACKEND = os.path.join(ROOT, "backend")
SRC = os.path.join(BACKEND, "tests", "domain", "test_prescription_templates.py")
orig = open(SRC, 'rb').read()
print("original test file sha256[:16] =", hashlib.sha256(orig).hexdigest()[:16].upper(), " bytes", len(orig))

tmp = tempfile.mkdtemp(prefix="rv2_mb4_")
print("temp dir =", tmp)
mut_path = os.path.join(tmp, "test_mb4_phase2.py")
text = orig.replace(b"\r\n", b"\n").decode("utf-8")

# M-B4 phase 2: redirect BOTH imports away from `templates` to the owner `exercises`
a = "from app.domain.prescription import exercises, templates\nfrom app.domain.prescription.templates import ImpactLevel\n"
b = "from app.domain.prescription import exercises\nfrom app.domain.prescription.exercises import ImpactLevel\n"
assert a in text, "anchor A not found"
t2 = text.replace(a, b, 1)
assert t2 != text
# and remove the guard test so it cannot NameError (deselect equivalent)
marker = "def test_templates_module_still_reexports_impact_level():"
assert marker in t2
head, _, _tail = t2.partition(marker)
t2 = head + "def test_mb4_placeholder_keeps_file_collectable():\n    assert True\n"
open(mut_path, 'wb').write(t2.encode("utf-8"))
print("mutated copy written:", mut_path, os.path.getsize(mut_path), "bytes")
print("mutated copy mentions 'templates' as an import -> ", "prescription.templates import" in t2 or "import exercises, templates" in t2)

COV = ["--cov=app/domain/prescription", "--cov-branch", "--cov-report=term-missing"]
def run(args, label):
    print("\n" + "="*74)
    print("### " + label)
    print("$ cd backend; python -m pytest " + " ".join(args))
    print("="*74)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "-c", "pyproject.toml"] + args,
                       capture_output=True, cwd=BACKEND)
    out = r.stdout.decode("utf-8","replace") + r.stderr.decode("utf-8","replace")
    print(out[-3000:])
    print(">>> EXIT CODE =", r.returncode)
    return r.returncode, out

rc1, o1 = run(["tests/domain/test_prescription_templates.py"] + COV,
              "BASELINE (unmodified guard file, known GREEN)")
rc2, o2 = run([mut_path] + COV,
              "M-B4 PHASE 2 (both imports redirected to `exercises`, guard test removed)")
print("\n" + "="*74)
print("SUMMARY")
print("  baseline exit code =", rc1, "  mutated exit code =", rc2)
for label, o in (("baseline", o1), ("mutated", o2)):
    for line in o.splitlines():
        if "templates.py" in line or "exercises.py" in line or "__init__.py" in line or line.startswith("TOTAL"):
            print("  %-9s | %s" % (label, line.strip()))
shutil.rmtree(tmp, ignore_errors=True)
after = open(SRC,'rb').read()
print("\nrepo test file restored/untouched -> sha256[:16] =", hashlib.sha256(after).hexdigest()[:16].upper(),
      " identical to before:", after == orig)
