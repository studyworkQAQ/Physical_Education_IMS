# -*- coding: utf-8 -*-
"""fr3 mutation harness: apply / restore a single mutation, byte-exact.

usage: python v08_mut.py <apply|restore|status> <M-PROD|M-TEST>

M-PROD : backend/app/domain/prescription/exercises.py
         IMPACT_RANK 的秩 HIGH:0 <-> LOW:2 对调
M-TEST : backend/tests/test_refdata_prescription.py
         IMPACT_DESCENDING 反序 ("high","medium","low") -> ("low","medium","high")
"""
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BK = pathlib.Path(r"C:\Users\whwenhao\AppData\Local\Temp\sdd_fr3\backup")
BK.mkdir(parents=True, exist_ok=True)
CRLF = bytes([13, 10])

MUT = {
    "M-PROD": {
        "path": ROOT / "backend/app/domain/prescription/exercises.py",
        "old": (b"IMPACT_RANK: dict[ImpactLevel, int] = {" + CRLF
                + b"    ImpactLevel.HIGH: 0," + CRLF
                + b"    ImpactLevel.MEDIUM: 1," + CRLF
                + b"    ImpactLevel.LOW: 2," + CRLF + b"}"),
        "new": (b"IMPACT_RANK: dict[ImpactLevel, int] = {" + CRLF
                + b"    ImpactLevel.HIGH: 2," + CRLF
                + b"    ImpactLevel.MEDIUM: 1," + CRLF
                + b"    ImpactLevel.LOW: 0," + CRLF + b"}"),
    },
    "M-TEST": {
        "path": ROOT / "backend/tests/test_refdata_prescription.py",
        "old": b'IMPACT_DESCENDING = ("high", "medium", "low")',
        "new": b'IMPACT_DESCENDING = ("low", "medium", "high")',
    },
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16].upper()


def main() -> int:
    action, name = sys.argv[1], sys.argv[2]
    m = MUT[name]
    p = m["path"]
    bak = BK / (name + "__" + p.name + ".orig")
    cur = p.read_bytes()

    if action == "status":
        print(f"{name}: {p.name} {len(cur)} B sha={sha(cur)} "
              f"old_present={cur.count(m['old'])} new_present={cur.count(m['new'])} "
              f"backup_exists={bak.exists()}"
              + (f" backup_sha={sha(bak.read_bytes())}" if bak.exists() else ""))
        return 0

    if action == "apply":
        if bak.exists():
            assert sha(bak.read_bytes()) == sha(cur), (
                "backup exists but differs from the current file -- refusing")
            print(f"  (reusing existing verified backup {bak.name})")
        else:
            shutil.copyfile(p, bak)
            assert sha(bak.read_bytes()) == sha(cur), "backup != original"
        n = cur.count(m["old"])
        assert n == 1, f"expected exactly 1 hit of the pristine pattern, got {n}"
        assert cur.count(m["new"]) == 0, "mutated pattern already present"
        mutated = cur.replace(m["old"], m["new"])
        # AST confirmation that the mutation really changed code (hard rule #53)
        import ast
        a1 = ast.dump(ast.parse(cur.decode("utf-8")))
        a2 = ast.dump(ast.parse(mutated.decode("utf-8")))
        p.write_bytes(mutated)
        after = p.read_bytes()
        print(f"{name} APPLIED: {len(cur)} B -> {len(after)} B ; sha {sha(cur)} -> {sha(after)}")
        print(f"  ast.dump changed on disk = {a1 != a2}")
        print(f"  old hits now = {after.count(m['old'])} ; new hits now = {after.count(m['new'])}")
        print(f"  backup = {bak} ({bak.stat().st_size} B, sha {sha(bak.read_bytes())})")
        return 0

    if action == "restore":
        assert bak.exists(), f"no backup at {bak}"
        orig = bak.read_bytes()
        p.write_bytes(orig)
        after = p.read_bytes()
        ok = after == orig
        print(f"{name} RESTORED: {len(cur)} B -> {len(after)} B ; sha {sha(after)} ; "
              f"byte-identical-to-backup={ok} ; "
              f"old_present={after.count(m['old'])} new_present={after.count(m['new'])}")
        return 0

    raise SystemExit(f"unknown action {action}")


if __name__ == "__main__":
    raise SystemExit(main())
