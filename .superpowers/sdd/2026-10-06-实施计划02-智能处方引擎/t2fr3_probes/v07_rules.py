# -*- coding: utf-8 -*-
"""Extract hard-rule definition lines from both ledgers."""
import pathlib
import re

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
P1 = ROOT / ".superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md"
P2 = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md"

WANT1 = {18, 19, 26, 29, 30, 32, 35, 39}
WANT2 = {50, 51, 52, 53, 56, 57, 61, 62, 65, 66, 67, 68, 70, 71, 72, 73}

pat_def = re.compile(r"(补硬规矩|硬规矩\s*#\d+\s*修订|新增硬规矩|##\s*硬规矩)")

for label, p, want in (("PLAN01", P1, WANT1), ("PLAN02", P2, WANT2)):
    lines = p.read_bytes().decode("utf-8").split("\n")
    print("#" * 78)
    print(f"# {label} ledger — hard rule definition lines")
    print("#" * 78)
    for i, ln in enumerate(lines, 1):
        s = ln.rstrip("\r")
        if not pat_def.search(s):
            continue
        nums = {int(n) for n in re.findall(r"#(\d+)", s)}
        if nums & want:
            print(f"[{i}] {s[:400]}")
