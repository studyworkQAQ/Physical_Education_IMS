import os, hashlib, shutil, tempfile
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review.md")
b0 = open(P,'rb').read()
bkp = os.path.join(tempfile.gettempdir(), "rv2_task-2-review_backup2.md")
shutil.copyfile(P, bkp)
print("backup ->", bkp, os.path.getsize(bkp), hashlib.sha256(b0).hexdigest()[:16].upper())
old = "本节修订后的终版见下方「终版实测」一行。全部用 `read_bytes()` 量".encode("utf-8")
new = ("⚠️ **本节刻意不印本文件自己的「终版」字节数 / 行数 / sha256**——那是自指："
       "把终版指纹印进去这个动作本身就会改变它（与 `test_prescription_templates.py:107-109` 拒绝把"
       "「会被自己的散文改变的 grep 计数」写进散文是同一条纪律）。两个**已成为历史、因而可复核**的定点是："
       "落盘首版 `89 408 B / 770 LF / CRLF 0 / B7A38659ECE7A45A`、"
       "首版修订版 `90 081 B / 774 LF / CRLF 0 / 0A5F3A651DE15CF4`；"
       "终版实测值由脚本 `review2_probes/p31_fix2.py` 的 stdout 与评审者的返回消息承担。"
       "全部用 `read_bytes()` 量").encode("utf-8")
assert b0.count(old) == 1, b0.count(old)
b1 = b0.replace(old, new, 1)
open(P,'wb').write(b1)
b2 = open(P,'rb').read()
print("after : bytes=%d sha16=%s lf=%d crlf=%d" % (len(b2), hashlib.sha256(b2).hexdigest()[:16].upper(), b2.count(b"\n"), b2.count(b"\r\n")))
t = b2.replace(b"\r\n",b"\n").decode("utf-8")
OLDTOK = ["TODO","PLACEHOLDER","XXXX","待补","待填","lorem","TBD"]
print("OLD tokens residual =", {k: t.count(k) for k in OLDTOK})
for s in ["0A5F3A651DE15CF4","Approved with findings","findings 计数：Critical 0 / Important 7 / Minor 10","不可复核项（12 条）"]:
    print("  NEW hit=%d  %s" % (t.count(s), s[:50]))
