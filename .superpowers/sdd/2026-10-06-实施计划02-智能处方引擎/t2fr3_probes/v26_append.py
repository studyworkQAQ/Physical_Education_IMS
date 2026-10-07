# -*- coding: utf-8 -*-
"""Append the '## fix round 3' section to task-2-report.md.

Hard rule #68 (revised) item 2: byte backup BEFORE appending.
Then: prefix check + double-direction string check + byte/CRLF arithmetic.
"""
import hashlib
import pathlib
import shutil
import sys

SDD = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
                   r"\.superpowers\sdd\2026-10-06-实施计划02-智能处方引擎")
REPORT = SDD / "task-2-report.md"
SECTION = pathlib.Path(r"C:\Users\whwenhao\AppData\Local\Temp\sdd_fr3\SECTION_fix_round_3.md")
BK = pathlib.Path(r"C:\Users\whwenhao\AppData\Local\Temp\sdd_fr3\backup")
BK.mkdir(parents=True, exist_ok=True)
BACKUP = BK / "task-2-report.md.pre-fr3"
CRLF = bytes([13, 10])
LF = bytes([10])
DRY = "--dry" in sys.argv


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def facts(b):
    return {
        "size": len(b),
        "lf": b.count(LF),
        "crlf": b.count(CRLF),
        "bare": b.count(LF) - b.count(CRLF),
        "sha": sha(b),
    }


pre = REPORT.read_bytes()
pf = facts(pre)
print(f"PRE  task-2-report.md: {pf['size']} B / lines {pf['lf']} / CRLF {pf['crlf']} "
      f"/ bare LF {pf['bare']} / sha {pf['sha']}")

# 1. byte backup (hard rule #68 revised, item 2)
if BACKUP.exists():
    raise SystemExit(f"REFUSE: backup already exists at {BACKUP}")
shutil.copyfile(REPORT, BACKUP)
bk = BACKUP.read_bytes()
assert bk == pre, "backup != original"
bf = facts(bk)
print(f"BACKUP -> {BACKUP}")
print(f"       {bf['size']} B / sha {bf['sha']} / identical-to-report={bk == pre}")

# 2. build the section text, fill in the placeholders
sec_lf = SECTION.read_bytes().decode("utf-8").replace("\r\n", "\n")
subs = {
    "__BK_SIZE__": str(bf["size"]),
    "__BK_SHA__": bf["sha"],
    "__PRE_SIZE__": str(pf["size"]),
    "__PRE_LINES__": str(pf["lf"]),
    "__PRE_CRLF__": str(pf["crlf"]),
    "__PRE_BARE__": str(pf["bare"]),
    "__PRE_SHA__": pf["sha"],
}
for k, v in subs.items():
    n = sec_lf.count(k)
    if n != 1:
        raise SystemExit(f"FAIL: placeholder {k} hits = {n}")
    sec_lf = sec_lf.replace(k, v)
for k in subs:
    if k in sec_lf:
        raise SystemExit(f"FAIL: placeholder {k} survived")
if not sec_lf.startswith("\n## fix round 3 "):
    raise SystemExit(f"FAIL: section does not start with the expected heading: {sec_lf[:60]!r}")
if "## fix round 3" in pre.decode("utf-8"):
    raise SystemExit("FAIL: '## fix round 3' already present in the report -- refusing to duplicate")

# the report body from line 25 on is CRLF; append with CRLF
sec = sec_lf.replace("\n", "\r\n").encode("utf-8")
sf = facts(sec)
print(f"SECTION (as it will be appended, CRLF): {sf['size']} B / lines {sf['lf']} "
      f"/ CRLF {sf['crlf']} / bare LF {sf['bare']} / sha {sf['sha']}")

post_expected = pre + sec
ef = facts(post_expected)
print(f"EXPECTED POST: {ef['size']} B / lines {ef['lf']} / CRLF {ef['crlf']} / bare LF {ef['bare']} "
      f"/ sha {ef['sha']}")
assert ef["size"] == pf["size"] + sf["size"]
assert ef["crlf"] == pf["crlf"] + sf["crlf"]
assert ef["bare"] == pf["bare"] + sf["bare"]

if DRY:
    print("DRY RUN -- nothing written")
    sys.exit(0)

# 3. write
REPORT.write_bytes(post_expected)
post = REPORT.read_bytes()

print()
print("=" * 78)
print("POST-WRITE VERIFICATION (read back from disk)")
print("=" * 78)
ok = True
if post != post_expected:
    ok = False
    print("FAIL: bytes on disk != bytes we intended to write")
else:
    print(f"OK  bytes on disk == intended ({len(post)} B)")
# (1) prefix
if post.startswith(pre):
    print(f"OK  (1) PRE is a strict PREFIX of POST ({len(pre)} of {len(post)} bytes)")
else:
    ok = False
    print("FAIL (1) PRE is NOT a prefix of POST")
# (2) double-direction string check
new_needles = [
    "## fix round 3 — 收尾评审的 7 条 Important + 10 条 Minor",
    "### fr3.5 变异验收",
    "63033BBD7F68CC1F",
    "822CB86A5E998301",
    "CE-fr3-1",
    "CE-fr3-2",
    "RE-fr3-1",
    "RE-fr3-2",
    "2 failed, 529 passed",
    "44/44",
    "ALL CAUGHT = True",
    "### fr3.11 关切与未尽事项",
]
post_text = post.decode("utf-8")
for nd in new_needles:
    n = post_text.count(nd)
    flag = "OK " if n >= 1 else "FAIL"
    if n < 1:
        ok = False
    print(f"  {flag} NEW {nd[:56]!r} -> {n}")
tail = pre.decode("utf-8")[-80:]
n = post_text.count(tail)
flag = "OK " if n == 1 else "FAIL"
if n != 1:
    ok = False
print(f"  {flag} OLD-TAIL (last 80 chars of the pre-append file) -> {n} hit(s)  {tail[-50:]!r}")
# also: the old file must NOT already have contained the new heading
if "## fix round 3" in pre.decode("utf-8"):
    ok = False
    print("  FAIL the pre-append file already contained '## fix round 3'")
else:
    print("  OK  the pre-append file did NOT contain '## fix round 3' (0 hits) -- query is meaningful")
# (3) arithmetic
af = facts(post)
print(f"  {'OK ' if af['size'] == pf['size'] + sf['size'] else 'FAIL'} (3) size {af['size']} == "
      f"{pf['size']} + {sf['size']}")
print(f"  {'OK ' if af['crlf'] == pf['crlf'] + sf['crlf'] else 'FAIL'} (3) CRLF {af['crlf']} == "
      f"{pf['crlf']} + {sf['crlf']}")
print(f"  {'OK ' if af['bare'] == pf['bare'] + sf['bare'] else 'FAIL'} (3) bare LF {af['bare']} == "
      f"{pf['bare']} + {sf['bare']}")
if af["size"] != pf["size"] + sf["size"] or af["crlf"] != pf["crlf"] + sf["crlf"] \
        or af["bare"] != pf["bare"] + sf["bare"]:
    ok = False
print()
print(f"POST task-2-report.md: {af['size']} B / lines {af['lf']} / CRLF {af['crlf']} "
      f"/ bare LF {af['bare']} / sha {af['sha']}")
print(f"RESULT: {'ALL GREEN' if ok else 'FAILURES -- RESTORE FROM ' + str(BACKUP)}")
sys.exit(0 if ok else 1)
