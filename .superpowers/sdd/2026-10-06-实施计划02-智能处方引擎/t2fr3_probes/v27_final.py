# -*- coding: utf-8 -*-
"""fr3 收工自证 (final)."""
import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])


def sh(*a):
    return subprocess.run(list(a), cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


print("1) git status --short  (expect 0 lines)")
s = sh("git", "status", "--short")
print(f"   lines = {len([x for x in s.split(chr(10)) if x.strip()])}")
print("   " + (s.strip() if s.strip() else "(empty)"))

print("2) HEAD / commits on top of 2df6825 / not pushed")
print("   HEAD = " + sh("git", "rev-parse", "--short", "HEAD").strip())
print("   branch = " + sh("git", "branch", "--show-current").strip())
log = sh("git", "log", "--oneline", "2df6825..HEAD")
print(f"   commits in 2df6825..HEAD = {len([x for x in log.split(chr(10)) if x.strip()])}")
print("   " + log.strip().replace("\n", "\n   ")[:300])
up = sh("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
print(f"   upstream = {up.strip()!r} (空/报错 = 没有跟踪远端 = 没 push)")
print("   remotes = " + repr(sh("git", "remote").strip()))

print("3) files in this commit")
print(sh("git", "show", "--stat", "--oneline", "HEAD").strip())

print("4) the three fingerprints, worktree vs HEAD blob")
for rel, eol_lf in (("backend/data/exercises.yaml", True),
                    ("backend/data/exercise_equivalence.yaml", True),
                    ("backend/data/national_standard_2014.csv", True)):
    wt = (ROOT / rel).read_bytes()
    blob = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                          capture_output=True).stdout
    print(f"   {rel}")
    print(f"      worktree {len(wt)} B / CRLF {wt.count(CRLF)} / normfp {norm_fp(wt)}")
    print(f"      HEAD-blob {len(blob)} B / CRLF {blob.count(CRLF)} / normfp {norm_fp(blob)}"
          f" / blob==worktree {blob == wt}")

print("5) constants in the committed test file match the committed YAMLs")
tr = (ROOT / "backend/tests/test_refdata_prescription.py").read_bytes().decode("utf-8")
for name, rel in (("EXERCISES_FINGERPRINT", "backend/data/exercises.yaml"),
                  ("EQUIVALENCE_FINGERPRINT", "backend/data/exercise_equivalence.yaml")):
    want = norm_fp((ROOT / rel).read_bytes())
    line = [l for l in tr.split("\n") if l.startswith(name + " =")]
    ok = len(line) == 1 and want in line[0]
    print(f"   {'OK  ' if ok else 'FAIL'} {name}: code={line[0].strip() if line else None} recomputed={want}")

print("6) report file: worktree vs HEAD blob (-text => must be byte-identical)")
rel = ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-report.md"
wt = (ROOT / rel).read_bytes()
blob = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True).stdout
print(f"   worktree {len(wt)} B / CRLF {wt.count(CRLF)} / bare LF {wt.count(LF)-wt.count(CRLF)} / sha {norm_fp(wt)}")
print(f"   HEAD-blob {len(blob)} B / sha {norm_fp(blob)} / blob==worktree {blob == wt}")
print(f"   ls-files --eol: {sh('git','ls-files','--eol','--',rel).strip()}")

print("7) no temp-dir residue inside the repo")
extra = [p for p in (ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎").iterdir()
         if p.is_dir()]
print("   dirs under the Plan-02 SDD folder: " + ", ".join(sorted(p.name for p in extra)))
print("   (fr2_probes / fr3_probes / fr4_probes are Task 1's, committed in 8e6a38f; "
      "no NEW dir was created this round)")
print("   backend/pe.db exists = " + str((ROOT / "backend/pe.db").exists()))
seed = ROOT / "backend/data/seed"
print("   backend/data/seed file count = " +
      str(len([p for p in seed.rglob('*') if p.is_file()]) if seed.exists() else -1))

print("8) .gitattributes / .gitignore untouched in this commit")
print("   " + repr(sh("git", "show", "--name-only", "--format=", "HEAD", "--",
                      ".gitattributes", ".gitignore").strip()))
