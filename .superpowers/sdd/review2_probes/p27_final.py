import os, re, subprocess, pathlib, hashlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT,"backend")
os.chdir(ROOT)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

NEEDLES = [
 (r"backend\app\domain\prescription\exercises.py", "19 字符"),
 (r"backend\app\domain\prescription\exercises.py", "改坏任何一份都会让"),
 (r"backend\app\domain\prescription\exercises.py", "今天有两份"),
 (r"backend\app\domain\prescription\exercises.py", "Plan01 Ruling 19"),
 (r"backend\tests\domain\test_prescription_templates.py", "19 字符"),
 (r"backend\tests\test_refdata_prescription.py", "改坏任何一侧都会让"),
 (r"backend\tests\test_refdata_prescription.py", "改坏任何一份本条都红"),
 (r"backend\tests\test_refdata_prescription.py", "Plan01 Ruling 19"),
 (r"backend\tests\test_refdata_prescription.py", "test_impact_level_vocabulary_agrees_with_the_domain_enum"),
 (r"backend\tests\test_refdata_prescription.py", "本 Task 的四个函数"),
 (r"backend\app\refdata_prescription.py", "本 Task 的四个函数"),
 (r"backend\app\refdata_prescription.py", "同一口径"),
 (r"backend\data\exercise_equivalence.yaml", "8 个 low 动作里的"),
 (r"backend\data\exercises.yaml", "预留为 #29"),
 (r"backend\data\exercises.yaml", ":487 点名的"),
 (r"backend\data\exercises.yaml", "2–3 倍体重"),
 (r"backend\tests\db\test_models.py", ":163"),
 (r"backend\app\db\models\prescription.py", ":163"),
 (r"backend\tests\seed\test_generate.py", "只遍历 ``DATA_TABLES``"),
 (r"Document\2026-09-28-体育闭环原型-设计spec.md", "#29–#35"),
 (r"Document\2026-09-28-体育闭环原型-设计spec.md", "编号冲突待 Task 12 处理"),
]
H("Q1 exact shell line numbers of every quoted snippet")
for rel, needle in NEEDLES:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print("  MISSING FILE", rel); continue
    L = open(p,'rb').read().replace(b"\r\n",b"\n").decode("utf-8").split("\n")
    hits = [i for i,s in enumerate(L,1) if needle in s]
    print("  %-62s %-42r -> %s" % (os.path.basename(rel), needle[:40], hits))
    for i in hits[:3]:
        print("        :%4d| %s" % (i, L[i-1].strip()[:200]))

H("Q2 repo-wide search for the dangling test name")
for pat in ("test_impact_level_vocabulary_agrees_with_the_domain_enum",
            "test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum"):
    r = subprocess.run(["git","grep","-n",pat,"--","backend"],capture_output=True)
    out = r.stdout.decode("utf-8","replace").strip()
    print("  %-64s -> %d hit(s)" % (pat, len(out.splitlines()) if out else 0))
    if out: print("     " + out.replace("\n","\n     "))

H("Q3 final self-attestation")
def sh(*a):
    r = subprocess.run(list(a), capture_output=True, cwd=ROOT)
    return r.returncode, r.stdout.decode("utf-8","replace"), r.stderr.decode("utf-8","replace")
rc,out,err = sh("git","status","--short")
print("  git status --short rc=%d lines=%d" % (rc, len([x for x in out.splitlines() if x.strip()])))
print("  " + (out.strip() or "(empty)"))
rc,out,_ = sh("git","rev-parse","HEAD"); print("  HEAD =", out.strip())
rc,out,_ = sh("git","rev-parse","--abbrev-ref","HEAD"); print("  branch =", out.strip())
print("  backend/pe.db exists ->", os.path.exists(os.path.join(B,"pe.db")))
sd = os.path.join(B,"data","seed")
print("  backend/data/seed exists ->", os.path.exists(sd), " entries ->", os.listdir(sd) if os.path.exists(sd) else None)
for rel in ("backend/data/exercises.yaml","backend/data/exercise_equivalence.yaml","backend/data/national_standard_2014.csv"):
    b = open(os.path.join(ROOT,rel),'rb').read()
    print("  %-46s %7d B  crlf=%d  sha256[:16]=%s" % (rel, len(b), b.count(b"\r\n"),
          hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()[:16].upper()))
rc,out,_ = sh("git","diff","--name-only","fb5bddb..HEAD","--","backend/app/seed")
print("  backend/app/seed changed fb5bddb..HEAD ->", repr(out))
rc,out,_ = sh("git","diff","--name-only","966eae0..HEAD","--","backend")
print("  backend changed 966eae0..HEAD ->", repr(out))
