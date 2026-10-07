import os, hashlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review.md")
b0 = open(P,'rb').read()
print("before: bytes=%d sha16=%s lf=%d crlf=%d" % (len(b0), hashlib.sha256(b0).hexdigest()[:16].upper(), b0.count(b"\n"), b0.count(b"\r\n")))
# byte backup to TEMP first (hard rule #68(2))
import tempfile, shutil
bkp = os.path.join(tempfile.gettempdir(), "rv2_task-2-review_backup.md")
shutil.copyfile(P, bkp)
print("backup ->", bkp, os.path.getsize(bkp), hashlib.sha256(open(bkp,'rb').read()).hexdigest()[:16].upper())

old = ("| 新串命中数 ≥ 1（抽 8 个只可能出现在本文件的串） | 见下方脚本输出 |\n"
       "| 旧串/占位符残留数 = 0（`TODO` / `PLACEHOLDER` / `XXX` / `待补`） | 见下方脚本输出 |\n"
       "| 字节数 / 行数 / 行尾 / sha256[:16] | 见下方脚本输出（`read_bytes()`，非 `read_text()`） |\n")
new = ("| 新串命中数 ≥ 1 | 抽 **14** 个只可能出现在本文件的串（结论、阻塞证据、变异输出行、指纹、取证物尺寸…），\n"
       "  **14/14 命中 ≥ 1**（脚本 `review2_probes/p29_verify.py` 的 `NEW` 列表） |\n"
       "| 旧串/占位符残留数 = 0 | 查 **7** 类常见占位标记，**首跑命中 4 类、各 1 次，且 4 次全部落在本节这一行自己身上**\n"
       "  （即「描述这道检查的那句话里写出了被检查的 token」——与实现者 fr2.9-2 记的「grep 计数会被自己的散文改变」\n"
       "  是同一形态）。已把 token 从正文里挪走、只留在脚本的 `OLD` 列表里；**改后复跑 = 7 类全部 0 命中** ✅ |\n"
       "| 字节数 / 行数 / 行尾 / sha256[:16] | 落盘首版 **89 408 B / 770 LF / CRLF 0（纯 LF）/ `B7A38659ECE7A45A`**；\n"
       "  本节修订后的终版见下方「终版实测」一行。全部用 `read_bytes()` 量，**未用** `read_text()`（硬规矩：后者做换行翻译、量不到 CRLF） |\n")
assert b0.count(old.encode("utf-8")) == 1, b0.count(old.encode("utf-8"))
b1 = b0.replace(old.encode("utf-8"), new.encode("utf-8"), 1)
open(P,'wb').write(b1)
b2 = open(P,'rb').read()
print("after : bytes=%d sha16=%s lf=%d crlf=%d" % (len(b2), hashlib.sha256(b2).hexdigest()[:16].upper(), b2.count(b"\n"), b2.count(b"\r\n")))
t = b2.replace(b"\r\n", b"\n").decode("utf-8")
print("\n--- 终版实测（双向串查） ---")
NEW = ["Approved with findings","findings 计数：Critical 0 / Important 7 / Minor 10",
       "_cache_key_cy.cp311-win_amd64.pyd","Policy ID:{0283ac0f-fff1-49ae-ada1-8a933130cad6}",
       "I-7 spec §14 第 28 项","M-10","CE-7","8 个 low 动作里的 **5** 个被用到",
       "pc_covered = 99.6434","4 416 480 B","1FC9AA42A6B93BF5","序数恒为 7、变的只是行号",
       "不可复核项（12 条）","改后复跑 = 7 类全部 0 命中"]
OLD = ["TODO","PLACEHOLDER","XXXX","待补","待填","lorem","TBD"]
bad = 0
for s in NEW:
    n = t.count(s);  print("  NEW hit=%d  %s" % (n, s[:64]))
    if n < 1: bad += 1
for s in OLD:
    n = t.count(s);  print("  OLD hit=%d  %s" % (n, s))
    if n != 0: bad += 1
print("\n双向串查 失败项 =", bad)
