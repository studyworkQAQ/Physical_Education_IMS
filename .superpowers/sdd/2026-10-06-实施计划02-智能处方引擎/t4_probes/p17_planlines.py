import pathlib, subprocess

ROOT = pathlib.Path(".").resolve()
PLAN = "Document/2026-10-06-实施处方引擎.md"
PLAN = "Document/2026-10-06-实施计划02-智能处方引擎.md"


def lines_at(rev, lo, hi):
    r = subprocess.run(["git", "show", "%s:%s" % (rev, PLAN)], capture_output=True, cwd=ROOT)
    txt = r.stdout.decode("utf-8").replace("\r\n", "\n")
    ls = txt.split("\n")
    print("### %s  (%d B blob / %d 行)" % (rev, len(r.stdout), len(ls)))
    for n in range(lo, hi + 1):
        if 1 <= n <= len(ls):
            print("  %-5d| %s" % (n, ls[n - 1][:140]))
    print()


for rev in ("a5bdebe", "8631744", "HEAD"):
    lines_at(rev, 372, 406)
