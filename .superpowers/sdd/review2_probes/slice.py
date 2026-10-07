import os, sys
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
MAP = {
 "progress": r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md",
 "report":   r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-report.md",
 "brief":    r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-brief.md",
 "pkg":      r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review-package.md",
 "spec":     r"Document\2026-09-28-体育闭环原型-设计spec.md",
 "plan":     r"Document\2026-10-06-实施计划02-智能处方引擎.md",
 "p1":       r".superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md",
}
which = sys.argv[1]
a = int(sys.argv[2]); b = int(sys.argv[3])
p = MAP[which] if which in MAP else (which if os.path.isabs(which) else os.path.join(ROOT, which))
raw = open(p,'rb').read()
L = raw.replace(b"\r\n", b"\n").decode("utf-8-sig").split("\n")
print(f"--- {p}  total={len(L)}  showing {a}..{b} ---")
for i in range(a, min(b, len(L))+1):
    print(f"{i:>5}|{L[i-1]}")
