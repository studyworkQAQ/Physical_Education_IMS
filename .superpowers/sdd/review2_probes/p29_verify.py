import os, hashlib, re
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
P = os.path.join(ROOT, r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review.md")
b = open(P,'rb').read()
crlf = b.count(b"\r\n"); lf = b.count(b"\n")
print("bytes      =", len(b))
print("LF lines   =", lf, " CRLF =", crlf, " bare LF =", lf-crlf)
print("sha256[:16]=", hashlib.sha256(b).hexdigest()[:16].upper())
t = b.replace(b"\r\n", b"\n").decode("utf-8")
print("decoded chars =", len(t))

NEW = [
 "Approved with findings",
 "findings 计数：Critical 0 / Important 7 / Minor 10",
 "_cache_key_cy.cp311-win_amd64.pyd",
 "Policy ID:{0283ac0f-fff1-49ae-ada1-8a933130cad6}",
 "I-7 spec §14 第 28 项",
 "M-10",
 "CE-7",
 "8 个 low 动作里的 **5** 个被用到",
 "app\\domain\\prescription\\templates.py       2      2      0      0     0%   37-39",
 "pc_covered = 99.6434",
 "4 416 480 B",
 "1FC9AA42A6B93BF5",
 "序数恒为 7、变的只是行号",
 "不可复核项（12 条）",
]
OLD = ["TODO", "PLACEHOLDER", "XXXX", "待补", "待填", "lorem", "TBD"]
print("\n--- 双向串查 ---")
bad = 0
for s in NEW:
    n = t.count(s)
    print("  NEW %-62r -> %d" % (s[:60], n))
    if n < 1: bad += 1
for s in OLD:
    n = t.count(s)
    print("  OLD %-62r -> %d" % (s[:60], n))
    if n != 0: bad += 1
print("\n双向串查 失败项 =", bad)

print("\n--- finding 计数自校 ---")
print("  '#### I-' headings =", len(re.findall(r"^#### I-\d", t, re.M)))
print("  'I-N' 表格行 (M-) =", len(re.findall(r"^\| \*\*M-\d+\*\*", t, re.M)))
print("  CE- 表格行        =", len(re.findall(r"^\| \*\*CE-\d+\*\*", t, re.M)))
print("  不可复核表行      =", len(re.findall(r"^\| \d+ \| ", t, re.M)))
print("  section headings:")
for i,s in enumerate(t.split("\n"),1):
    if s.startswith("## "): print("    :%4d| %s" % (i, s[:110]))
