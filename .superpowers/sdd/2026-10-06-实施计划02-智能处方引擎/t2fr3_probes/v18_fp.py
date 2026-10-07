# -*- coding: utf-8 -*-
"""Set the two fingerprint constants from the YAMLs' current bytes (regex-based)."""
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])
DRY = "--dry" in sys.argv


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


ex = (ROOT / "backend/data/exercises.yaml").read_bytes()
eq = (ROOT / "backend/data/exercise_equivalence.yaml").read_bytes()
NEW = {"EXERCISES_FINGERPRINT": norm_fp(ex), "EQUIVALENCE_FINGERPRINT": norm_fp(eq)}
print(f"exercises.yaml            {len(ex)} B CRLF {ex.count(CRLF)} -> {NEW['EXERCISES_FINGERPRINT']}")
print(f"exercise_equivalence.yaml {len(eq)} B CRLF {eq.count(CRLF)} -> {NEW['EQUIVALENCE_FINGERPRINT']}")

p = ROOT / "backend/tests/test_refdata_prescription.py"
raw = p.read_bytes()
ncrlf = raw.count(CRLF)
nlf = raw.count(LF)
assert ncrlf == nlf, f"MIXED eol: CRLF {ncrlf} / LF {nlf}"
text = raw.decode("utf-8").replace("\r\n", "\n")

for name, want in NEW.items():
    pat = re.compile(rf'^{name} = "([0-9A-F]{{16}})"$', re.M)
    hits = pat.findall(text)
    if len(hits) != 1:
        raise SystemExit(f"FAIL: {name} literal hits = {len(hits)} {hits}")
    old = hits[0]
    text = pat.sub(f'{name} = "{want}"', text)
    print(f"  {name}: {old} -> {want} (replaced={old != want})")
    if text.count(f'{name} = "{want}"') != 1 or pat.findall(text) != [want]:
        raise SystemExit(f"FAIL post-check for {name}")

out = text.replace("\n", "\r\n").encode("utf-8")
if DRY:
    print(f"DRY: {len(raw)} -> {len(out)} B")
else:
    p.write_bytes(out)
    chk = p.read_bytes()
    assert chk == out, "write verify failed"
    print(f"WROTE {p.name}: {len(raw)} -> {len(chk)} B ; CRLF {chk.count(CRLF)} ; "
          f"normfp {norm_fp(chk)}")
