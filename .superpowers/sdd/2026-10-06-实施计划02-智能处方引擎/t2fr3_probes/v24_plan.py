# -*- coding: utf-8 -*-
"""Verify the reviewer's I-6/I-7 claims about the plan document at fb5bddb vs HEAD."""
import pathlib
import subprocess

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
PLAN = "Document/2026-10-06-实施计划02-智能处方引擎.md"


def show(rev):
    r = subprocess.run(["git", "show", f"{rev}:{PLAN}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8").replace("\r\n", "\n").split("\n")


for rev in ("fb5bddb", "2df6825"):
    lines = show(rev)
    print("=" * 78)
    print(f"{rev}: plan has {len(lines)-1} lines")
    for i in (681, 682, 684, 685, 688, 707):
        s = lines[i-1] if i <= len(lines) else "<OUT OF RANGE>"
        print(f"  :{i}| {s[:170]}")
    print("  --- grep '#29' / '动作库的视频源' ---")
    for i, s in enumerate(lines, 1):
        if "动作库的视频源" in s or "#29" in s:
            print(f"  :{i}| {s[:170]}")

print()
print("=" * 78)
print("git diff --numstat fb5bddb..2df6825 for plan and spec")
for rel in (PLAN, "Document/2026-09-28-体育闭环原型-设计spec.md"):
    r = subprocess.run(["git", "diff", "--numstat", f"fb5bddb..2df6825", "--", rel],
                       cwd=ROOT, capture_output=True)
    print(f"  {rel}: {r.stdout.decode('utf-8','replace').strip()!r}")
print()
print("commits touching the plan in fb5bddb..2df6825:")
r = subprocess.run(["git", "log", "--oneline", "fb5bddb..2df6825", "--", PLAN],
                   cwd=ROOT, capture_output=True)
print(r.stdout.decode("utf-8", "replace"))
print("commits touching Document/*spec.md in fb5bddb..2df6825:")
r = subprocess.run(["git", "log", "--oneline", "fb5bddb..2df6825", "--",
                    "Document/2026-09-28-体育闭环原型-设计spec.md"],
                   cwd=ROOT, capture_output=True)
print(r.stdout.decode("utf-8", "replace"))
