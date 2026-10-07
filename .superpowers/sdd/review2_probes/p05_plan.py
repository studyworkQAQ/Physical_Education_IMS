import os, re, subprocess
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
os.chdir(ROOT)
plan = r"Document/2026-10-06-实施计划02-智能处方引擎.md"
cur = open(plan,'rb').read().replace(b"\r\n",b"\n").decode("utf-8").split("\n")
print("=== CURRENT plan: lines matching #2x/#3x numbering near Task 12 ===")
for i,s in enumerate(cur,1):
    if re.search(r"#2[6-9]|#3[0-5]|§14", s):
        print(f"{i:>5}|{s[:400]}")
print()
old = subprocess.run(["git","show",f"fb5bddb:{plan}"],capture_output=True).stdout.replace(b"\r\n",b"\n").decode("utf-8").split("\n")
print("=== fb5bddb plan: total lines", len(old), " current:", len(cur))
for n in (491,500,502,524,568,569,678,681,683,685,700,703,177,181,182,185,209):
    print(f"fb5bddb :{n:>4}| {old[n-1][:300] if n-1 < len(old) else 'OOB'}")
