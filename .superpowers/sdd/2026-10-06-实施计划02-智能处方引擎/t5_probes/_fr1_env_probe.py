# -*- coding: utf-8 -*-
"""只读探针：打印一批关键文件的换行/BOM/字节数/行数，供 fix round 1 前后对账。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
TARGETS = [
    "Document/2026-10-06-实施计划02-智能处方引擎.md",
    ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md",
    ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-5-report.md",
    ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-5-brief.md",
    "backend/app/domain/prescription/assembler.py",
    "backend/app/domain/prescription/intensity.py",
    "backend/app/domain/prescription/safety.py",
    "backend/app/domain/prescription/override.py",
    "backend/app/domain/prescription/__init__.py",
    "backend/tests/domain/test_prescription_assembler.py",
    "backend/tests/domain/test_prescription_intensity.py",
    "backend/tests/domain/test_prescription_safety.py",
    "backend/tests/domain/test_prescription_override.py",
    "backend/app/domain/derive.py",
]


def describe(rel):
    p = ROOT / rel
    if not p.exists():
        print(f"{rel}: <缺失>")
        return
    raw = p.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = raw.count(b"\r\n")
    bare_lf = raw.count(b"\n") - crlf
    nl = ("CRLF" if crlf and not bare_lf else
          "LF" if bare_lf and not crlf else
          "MIXED" if crlf or bare_lf else "NONE")
    print(f"{rel}\n    bytes={len(raw)} lines(split)={len(raw.decode('utf-8').splitlines())} "
          f"nl={nl} crlf={crlf} lf={bare_lf} bom={bom}")


for rel in TARGETS:
    describe(rel)
sys.exit(0)
