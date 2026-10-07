import os, sys, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
def lines(rel):
    b = open(os.path.join(ROOT, rel), 'rb').read()
    return b.replace(b"\r\n", b"\n").decode("utf-8").split("\n")

targets = {
 "progress": r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md",
 "report":   r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-report.md",
 "brief":    r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-brief.md",
 "pkg":      r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review-package.md",
}
for k, rel in targets.items():
    L = lines(rel)
    print("#"*78)
    print(f"### {k}  ({rel})  total_lines={len(L)}")
    for i, s in enumerate(L, 1):
        if s.startswith("#") and len(s) < 200:
            print(f"  {i:>5}: {s}")
