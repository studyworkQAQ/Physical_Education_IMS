import os, subprocess
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)
plan = "Document/2026-10-06-实施计划02-智能处方引擎.md"
def blob(rev):
    r = subprocess.run(["git","show",f"{rev}:{plan}"],capture_output=True)
    return r.stdout.replace(b"\r\n",b"\n").decode("utf-8").split("\n")
print("=== log for plan file (last 12) ===")
print(subprocess.run(["git","log","--oneline","-12","--",plan],capture_output=True).stdout.decode("utf-8","replace"))
print("=== is fb5bddb ancestor of e09e5f6? ===")
for a,b in [("fb5bddb","e09e5f6"),("e09e5f6","fb5bddb")]:
    r=subprocess.run(["git","merge-base","--is-ancestor",a,b],capture_output=True)
    print(f"{a} ancestor-of {b}: rc={r.returncode}")
print(subprocess.run(["git","log","--oneline","fb5bddb~1..966eae0"],capture_output=True).stdout.decode("utf-8","replace"))
print("=== e09e5f6 exists? ===")
print(subprocess.run(["git","cat-file","-t","e09e5f6"],capture_output=True).stdout.decode(),subprocess.run(["git","cat-file","-t","e09e5f6"],capture_output=True).stderr.decode())
for rev in ["e09e5f6","fb5bddb"]:
    try:
        L = blob(rev)
    except Exception as e:
        print(rev,"ERR",e); continue
    print(f"--- {rev}: plan total lines {len(L)} ---")
    for n in (177,181,182,183,184,185,186,187,209,678,679,700):
        if n-1 < len(L):
            print(f"  {rev} :{n:>4}| {L[n-1][:260]}")
