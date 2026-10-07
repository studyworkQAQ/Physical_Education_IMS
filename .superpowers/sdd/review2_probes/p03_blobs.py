import subprocess, hashlib, os
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)
P = ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/"
files = ["progress.md","task-1-report.md","task-2-report.md","task-2-brief.md","task-2-review-package.md"]
for f in files:
    wt = open(P+f,'rb').read()
    print("WORKTREE %-32s bytes=%8d sha16=%s crlf=%d lf=%d" % (f, len(wt), hashlib.sha256(wt).hexdigest()[:16].upper(), wt.count(b"\r\n"), wt.count(b"\n")))
print()
for rev in ["8e6a38f","23325de","23388c7","7c5aff8","7296793"]:
    for f in files:
        r = subprocess.run(["git","show",f"{rev}:{P}{f}"], capture_output=True)
        if r.returncode!=0:
            print(f"{rev} {f:32} ABSENT")
            continue
        b = r.stdout
        print("%s %-32s bytes=%8d sha16=%s crlf=%d lf=%d" % (rev, f, len(b), hashlib.sha256(b).hexdigest()[:16].upper(), b.count(b"\r\n"), b.count(b"\n")))
    print()
