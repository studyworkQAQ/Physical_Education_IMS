import os, hashlib, shutil, tempfile
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review.md")
b0 = open(P,'rb').read()
bkp = os.path.join(tempfile.gettempdir(), "rv2_task-2-review_backup3.md")
shutil.copyfile(P, bkp)
print("backup ->", bkp, os.path.getsize(bkp), hashlib.sha256(b0).hexdigest()[:16].upper())

old = "### 5.1 三个指纹 + 禁区（全部逐字相符）\n".encode("utf-8")
new = ("### 5.1 三个指纹 + 禁区（全部逐字相符）\n\n"
       "> **哈希口径**（两种，别混）：`backend/data/*`（`.gitattributes` 钉 `text eol=lf`，工作树本来就是纯 LF）用"
       "**CRLF 归一化后**的 sha256[:16]，与测试里 `_fingerprint()` 的口径一致；"
       "`backend/**/*.py`（工作树是纯 CRLF）用**裸字节**的 sha256[:16]，与账本 Ruling 108 记的"
       "`exercises.py = 1FC9AA42A6B93BF5` 同口径。下表逐个标注。\n").encode("utf-8")
assert b0.count(old) == 1, b0.count(old)
b1 = b0.replace(old, new, 1)

old2 = "| `backend/app/domain/prescription/exercises.py` | `1FC9AA42A6B93BF5`（账本 `:1281`） | **12384 B / `1FC9AA42A6B93BF5`** | ✅ |".encode("utf-8")
new2 = "| `backend/app/domain/prescription/exercises.py`（**裸字节**口径） | `1FC9AA42A6B93BF5`（账本 `:1281`） | **12384 B / CRLF 200 / `1FC9AA42A6B93BF5`** | ✅ |".encode("utf-8")
assert b1.count(old2) == 1, b1.count(old2)
b2 = b1.replace(old2, new2, 1)

old3 = "| `backend/tests/domain/test_prescription_templates.py` | **10697 B / `B71E435CF3FC577C`** ✓（MB4 用的是 `$env:TEMP` 副本，跑前跑后一致） |".encode("utf-8")
new3 = "| `backend/tests/domain/test_prescription_templates.py`（**裸字节**口径） | **10697 B / CRLF 147 / `B71E435CF3FC577C`** ✓（MB4 用的是 `$env:TEMP` 副本，跑前跑后一致） |".encode("utf-8")
assert b2.count(old3) == 1, b2.count(old3)
b3 = b2.replace(old3, new3, 1)

open(P,'wb').write(b3)
b4 = open(P,'rb').read()
print("after : bytes=%d sha16=%s lf=%d crlf=%d" % (len(b4), hashlib.sha256(b4).hexdigest()[:16].upper(), b4.count(b"\n"), b4.count(b"\r\n")))
t = b4.replace(b"\r\n",b"\n").decode("utf-8")
print("OLD tokens residual =", {k: t.count(k) for k in ["TODO","PLACEHOLDER","XXXX","待补","待填","lorem","TBD"]})
for s in ["哈希口径","裸字节","Approved with findings","findings 计数：Critical 0 / Important 7 / Minor 10",
          "不可复核项（12 条）","1FC9AA42A6B93BF5","B71E435CF3FC577C","4D97FDB473AFBD71" ]:
    print("  NEW hit=%d  %s" % (t.count(s), s[:50]))
import re
print("sections:", [s[:40] for s in t.split("\n") if s.startswith("## ")])
print("I-headings:", len(re.findall(r"^#### I-\d", t, re.M)), " M-rows:", len(re.findall(r"^\| \*\*M-\d+\*\*", t, re.M)), " CE-rows:", len(re.findall(r"^\| \*\*CE-\d+\*\*", t, re.M)))
