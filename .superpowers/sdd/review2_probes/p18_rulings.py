import os, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P1 = os.path.join(ROOT, r".superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md")
P2 = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md")
def rd(p): return open(p,'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace").split("\n")
L1, L2 = rd(P1), rd(P2)
def H(t): print("\n" + "="*74 + "\n## " + t + "\n" + "="*74)

H("J1 Plan01 ledger: every line mentioning 'Ruling 19' or a heading 'Ruling 19'")
for i,s in enumerate(L1,1):
    if re.search(r"Ruling 19\b", s): print("  :%5d| %s" % (i, s[:260]))

H("J2 Plan01 ledger: which ruling establishes 'BMI 不归任何短板桶 / ITEM_BUCKET[BMI] is None'?")
pat = re.compile(r"ITEM_BUCKET|不归任何短板|BMI.*桶|桶.*BMI")
for i,s in enumerate(L1,1):
    if pat.search(s) and re.search(r"Ruling|裁定", s):
        print("  :%5d| %s" % (i, s[:300]))

H("J3 Plan01 ledger: all 'Ruling N' headings, N in 15..25")
for i,s in enumerate(L1,1):
    m = re.match(r"\s*\*?\*?Ruling (\d+)\b", s.strip("* "))
    if m and 15 <= int(m.group(1)) <= 25:
        print("  :%5d| %s" % (i, s[:200]))

H("J4 Plan02 ledger: does it have its own 'Ruling 19'? and Ruling 28?")
for i,s in enumerate(L2,1):
    if re.search(r"\*?\*?Ruling (19|28)\b", s.strip("* ")) and s.strip().startswith(("**Ruling","Ruling")):
        print("  :%5d| %s" % (i, s[:240]))
print("  --- all Plan02 ruling headings (first 40) ---")
cnt=0
for i,s in enumerate(L2,1):
    if s.startswith("**Ruling ") or s.startswith("#### Ruling") or s.startswith("**P2-"):
        print("  :%5d| %s" % (i, s[:130])); cnt+=1
        if cnt>45: break

H("J5 Plan01 ledger: search for the exact phrase used by the source citation")
for needle in ["天然不属于任何短板桶","不属于任何短板","BMI 不归","不归桶","短板桶"]:
    hits = [(i,s) for i,s in enumerate(L1,1) if needle in s]
    print("  %-22s -> %d hit(s)" % (needle, len(hits)))
    for i,s in hits[:4]: print("      :%5d| %s" % (i, s[:250]))

H("J6 where do source files cite 'Ruling 19' / 'Ruling 144' / 'Ruling 213' / 'Ruling 231' / 'Ruling 28'?")
import pathlib
for p in pathlib.Path(os.path.join(ROOT,"backend")).rglob("*.py"):
    if "__pycache__" in str(p): continue
    txt = p.read_bytes().replace(b"\r\n",b"\n").decode("utf-8","replace")
    for i,s in enumerate(txt.split("\n"),1):
        for n in ("Ruling 19","Ruling 144","Ruling 213","Ruling 231","Ruling 28","Ruling 21","Ruling 1 ","Ruling 12","Ruling 35","Ruling 36"):
            if n in s:
                print("  %-52s :%4d| %s" % (p.relative_to(ROOT), i, s.strip()[:170]))
                break
