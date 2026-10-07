import os, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P2 = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md")
txt = open(P2,'rb').read().replace(b"\r\n",b"\n").decode("utf-8","replace")
L = txt.split("\n")
print("Ruling 48 occurrences =", len(re.findall(r"Ruling 48\b", txt)))
print("Ruling 47 occurrences =", len(re.findall(r"Ruling 47\b", txt)))
print("Ruling 49 occurrences =", len(re.findall(r"Ruling 49\b", txt)))
for n in (47,48,49):
    hits = [(i,s.strip()[:150]) for i,s in enumerate(L,1) if re.search(r"Ruling %d\b" % n, s)]
    print("  Ruling %d -> %d hit(s)" % (n, len(hits)))
    for i,s in hits[:3]: print("     :%5d| %s" % (i,s))
print()
print("hard rules #60..#71 definition lines:")
for n in range(60,72):
    hits = [(i,s.strip()[:170]) for i,s in enumerate(L,1) if re.search(r"(补硬规矩 #%d|硬规矩 #%d 修订|硬规矩 #%d：)" % (n,n,n), s)]
    print("  #%-3d -> %d" % (n, len(hits)))
    for i,s in hits[:2]: print("       :%5d| %s" % (i,s))
print()
print("Plan02 ledger ruling headings present, max number:")
nums = sorted({int(m) for s in L for m in re.findall(r"^\*\*Ruling (\d+)", s)})
print("  count =", len(nums), " min =", nums[0] if nums else None, " max =", nums[-1] if nums else None)
missing = [n for n in range(nums[0], nums[-1]+1) if n not in nums] if nums else []
print("  gaps in the '**Ruling N' heading series =", missing)
