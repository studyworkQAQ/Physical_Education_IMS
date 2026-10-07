# -*- coding: utf-8 -*-
"""Final fact table: BEFORE = worktree bytes at HEAD 2df6825 (reconstructed from the blob
using the file's own eol convention, cross-checked against the controller's §5 numbers);
AFTER = current worktree bytes."""
import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])

CONTROLLER = {
    "backend/app/domain/prescription/exercises.py": (12384, 200, 200, "E06CBE6A96D28051"),
    "backend/app/refdata_prescription.py": (22400, 406, 406, "875F0DC917984CC5"),
    "backend/app/db/models/prescription.py": (8976, 131, 131, "660CC93E44EBD1BA"),
    "backend/data/exercises.yaml": (13358, 267, 0, "A6A000F58815FCBB"),
    "backend/data/exercise_equivalence.yaml": (7841, 126, 0, "0FFB881574AC04F3"),
    "backend/tests/test_refdata_prescription.py": (54774, 921, 921, "B969FFF932185E53"),
    "backend/tests/domain/test_prescription_templates.py": (10697, 147, 147, "97AE1A3DE28615C7"),
    "backend/tests/db/test_models.py": (43904, 750, 750, "0161112C2D9CA6A3"),
    "backend/tests/seed/test_generate.py": (65501, 1179, 1179, "AEAE90C8CFDFB4C2"),
    "Document/2026-09-28-体育闭环原型-设计spec.md": (85847, 974, 974, "D935A6FD94C8C2C2"),
    "backend/data/national_standard_2014.csv": (21412, None, 0, "D2C8E539E2FA0029"),
}


def stat(b):
    nl = b.count(LF)
    lines = nl if b.endswith(LF) else nl + 1
    fp = hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()
    return len(b), lines, b.count(CRLF), fp


print("| file | BEFORE bytes / lines / CRLF / normfp | AFTER bytes / lines / CRLF / normfp |")
print("|---|---|---|")
for rel, ctrl in CONTROLLER.items():
    blob = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                          capture_output=True).stdout
    before = blob.replace(LF, CRLF) if ctrl[2] != 0 else blob
    b = stat(before)
    a = stat((ROOT / rel).read_bytes())
    agree = (b[0] == ctrl[0] and b[2] == ctrl[2] and b[3] == ctrl[3]
             and (ctrl[1] is None or b[1] == ctrl[1]))
    mark = "OK" if agree else "MISMATCH-vs-dispatch"
    short = rel.replace("backend/", "").replace("Document/2026-09-28-体育闭环原型-设计spec.md", "Document/…设计spec.md")
    print(f"| `{short}` [{mark}] | {b[0]} / {b[1]} / {b[2]} / `{b[3]}` | "
          f"{a[0]} / {a[1]} / {a[2]} / `{a[3]}` |")
