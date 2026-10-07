# -*- coding: utf-8 -*-
"""fr3 fact check: file bytes / lines / CRLF / fingerprint / anchors."""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")

FILES = [
    ("app/domain/prescription/exercises.py", 12384, 200, 200, "E06CBE6A96D28051"),
    ("app/refdata_prescription.py", 22400, 406, 406, "875F0DC917984CC5"),
    ("app/db/models/prescription.py", 8976, 131, 131, "660CC93E44EBD1BA"),
    ("data/exercises.yaml", 13358, 267, 0, "A6A000F58815FCBB"),
    ("data/exercise_equivalence.yaml", 7841, 126, 0, "0FFB881574AC04F3"),
    ("tests/test_refdata_prescription.py", 54774, 921, 921, "B969FFF932185E53"),
    ("tests/domain/test_prescription_templates.py", 10697, 147, 147, "97AE1A3DE28615C7"),
    ("tests/db/test_models.py", 43904, 750, 750, "0161112C2D9CA6A3"),
    ("tests/seed/test_generate.py", 65501, 1179, 1179, "AEAE90C8CFDFB4C2"),
]

SUPER = [
    (".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-review.md", 91077, 776),
    (".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-review-package.md", 210927, 3229),
    (".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md", 233921, 1544),
    (".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-report.md", 127827, 969),
    (".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-brief.md", 28004, None),
]


def fp(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()


def raw_fp(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16].upper()


def lines_of(b: bytes) -> int:
    """count of lines: number of newline terminators if file ends with newline else +1"""
    if b == b"":
        return 0
    n = b.count(b"\n")
    if not b.endswith(b"\n"):
        n += 1
    return n


def check(rel, root, exp_bytes=None, exp_lines=None, exp_crlf=None, exp_fp=None):
    p = root / rel
    if not p.exists():
        print(f"MISSING {rel}")
        return
    b = p.read_bytes()
    nb = len(b)
    nl = lines_of(b)
    crlf = b.count(b"\r\n")
    f = fp(b)
    rf = raw_fp(b)
    flags = []
    if exp_bytes is not None and nb != exp_bytes:
        flags.append(f"BYTES exp={exp_bytes}")
    if exp_lines is not None and nl != exp_lines:
        flags.append(f"LINES exp={exp_lines}")
    if exp_crlf is not None and crlf != exp_crlf:
        flags.append(f"CRLF exp={exp_crlf}")
    if exp_fp is not None and f not in (exp_fp,) and rf != exp_fp:
        flags.append(f"FP exp={exp_fp} norm={f} raw={rf}")
    tag = "OK " if not flags else "DIFF"
    print(f"{tag} {rel}: {nb} B / {nl} lines / CRLF {crlf} / normfp {f} / rawfp {rf}"
          + ("" if not flags else "  <-- " + "; ".join(flags)))


print("=== backend files ===")
for rel, eb, el, ec, ef in FILES:
    check("backend/" + rel, ROOT, eb, el, ec, ef)

print()
print("=== Document spec ===")
spec_rel = None
d = ROOT / "Document"
for p in sorted(d.glob("*设计spec*.md")):
    spec_rel = p.relative_to(ROOT).as_posix()
    check(spec_rel, ROOT, 85847, 974, 974, "D935A6FD94C8C2C2")
print("spec_rel =", spec_rel)

print()
print("=== superpowers artifacts ===")
for rel, eb, el in SUPER:
    check(rel, ROOT, eb, el)

print()
print("=== forbidden zone ===")
csv = ROOT / "backend/data/national_standard_2014.csv"
b = csv.read_bytes()
_crlf = b.count(b"\r\n")
print(f"csv {len(b)} B / CRLF {_crlf} / normfp {fp(b)} / rawfp {raw_fp(b)}")
print("pe.db exists:", (ROOT / "backend/pe.db").exists())
seed = ROOT / "backend/data/seed"
print("data/seed exists:", seed.exists(),
      "files:", len(list(seed.rglob("*"))) if seed.exists() else "n/a")

print()
print("=== anchors (hit counts) ===")


def hits(rel, needle):
    p = ROOT / rel
    b = p.read_bytes().decode("utf-8")
    return b.count(needle)


ANCHORS = [
    ("backend/app/domain/prescription/exercises.py", "ImpactLevel.HIGH"),
    ("backend/app/domain/prescription/exercises.py", "任何一份"),
    ("backend/app/domain/prescription/exercises.py", "Ruling 19"),
    ("backend/tests/test_refdata_prescription.py", "Ruling 19"),
    ("backend/data/exercise_equivalence.yaml", "5 个"),
    ("backend/tests/db/test_models.py", ":163"),
    ("backend/app/db/models/prescription.py", ":163"),
    ("backend/data/exercises.yaml", "#29"),
]
for rel, nd in ANCHORS:
    print(f"  {rel} :: {nd!r} -> {hits(rel, nd)}")

if spec_rel:
    print(f"  {spec_rel} :: '#29' -> {hits(spec_rel, '#29')}")
    print(f"  {spec_rel} :: '#35' -> {hits(spec_rel, '#35')}")

print()
print("=== == 15 positions in test_models.py ===")
tm = (ROOT / "backend/tests/db/test_models.py").read_bytes().decode("utf-8").split("\n")
for i, ln in enumerate(tm, 1):
    if "== 15" in ln or "test_all_fifteen_tables_created" in ln or ":163" in ln:
        print(f"  :{i}: {ln.rstrip()[:160]}")

print()
print("=== git baseline sanity ===")
print("HEAD short:", end=" ")
sys.stdout.flush()
