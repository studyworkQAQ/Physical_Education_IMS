# -*- coding: utf-8 -*-
"""Reproduce the architecture guards' own scan surface (hard rule: unchanged surface)."""
import pathlib
import sys

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests" / "architecture"))

import test_layering as TL  # noqa: E402
import test_domain_purity as TP  # noqa: E402

print("SCANNED_DIRS =", TL.SCANNED_DIRS)
total = 0
for d in TL.SCANNED_DIRS:
    files = TL._py_files(d)
    print(f"  {d:10s} -> {len(files)} .py : {[p.name for p in files]}")
    total += len(files)
print(f"  TOTAL scanned = {total}")
print()
dom = TP._domain_files()
print(f"TP._domain_files() = {len(dom)} : {[p.name for p in dom]}")
print(f"TP lower bound assert = 5 ; TL lower bound assert = 8")
