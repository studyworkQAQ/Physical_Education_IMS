import subprocess, hashlib, os, sys
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)

def sh(*a):
    return subprocess.run(["git"]+list(a), capture_output=True)

def dump(title, r):
    print("="*70)
    print(title, "rc=", r.returncode)
    out = r.stdout.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("STDERR:", err)

dump("log --follow data/exercises.yaml", sh("log","--oneline","--follow","--","backend/data/exercises.yaml"))
dump("ls-files backend/data", sh("ls-files","backend/data"))
dump("show 966eae0 --stat", sh("show","--stat","--oneline","966eae0"))
dump("name-status fb5bddb..966eae0", sh("diff","--name-status","fb5bddb..966eae0"))
dump("diff --stat fb5bddb..966eae0", sh("diff","--stat","fb5bddb..966eae0"))
