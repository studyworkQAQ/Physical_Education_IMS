# -*- coding: utf-8 -*-
"""I-5: locate the real source of 'BMI 不参与短板判定与桶化'."""
import pathlib
import re

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
P1 = ROOT / ".superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md"
P2 = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md"
SPEC = ROOT / "Document/2026-09-28-体育闭环原型-设计spec.md"

CRLF = bytes([13, 10])

for label, p in (("PLAN01 ledger", P1), ("PLAN02 ledger", P2)):
    b = p.read_bytes()
    lines = b.decode("utf-8").split("\n")
    ncrlf = b.count(CRLF)
    print("=" * 70)
    print(f"{label}: {p.name}  {len(b)} B / {len(lines)} splitlines / CRLF {ncrlf}")
    print("=" * 70)
    for i, ln in enumerate(lines, 1):
        s = ln.rstrip("\r")
        if "Ruling 19" in s or re.search(r"Ruling\s*19\b", s):
            print(f"  [{i}] {s[:220]}")

print()
print("=" * 70)
print("PLAN01 ledger lines 128-140 (context of :133)")
print("=" * 70)
lines = P1.read_bytes().decode("utf-8").split("\n")
for i in range(112, 142):
    print(f"{i:5d}| {lines[i-1].rstrip(chr(13))[:260]}")

print()
print("=" * 70)
print("PLAN01 ledger lines 166-176 (Ruling 19 definition)")
print("=" * 70)
for i in range(166, 177):
    print(f"{i:5d}| {lines[i-1].rstrip(chr(13))[:260]}")

print()
print("=" * 70)
print("PLAN01 ledger lines 1386-1398 (WEAKNESS_ITEMS 天然排除 BMI)")
print("=" * 70)
for i in range(1386, 1399):
    if i <= len(lines):
        print(f"{i:5d}| {lines[i-1].rstrip(chr(13))[:260]}")

print()
print("=" * 70)
print("spec §4.2 mentions of BMI + 短板/桶")
print("=" * 70)
sl = SPEC.read_bytes().decode("utf-8").split("\n")
for i, ln in enumerate(sl, 1):
    s = ln.rstrip("\r")
    if "BMI" in s and ("短板" in s or "桶" in s or "不参与" in s):
        print(f"  [{i}] {s[:300]}")
