"""抽 Plan 03 的 task-N-brief.md（参数化，9 个 Task 复用同一份脚本）。

用法：python _mk_brief.py N [派单头文件]
按标题锚点抽（硬规矩 #78：不用裸行号），逐字复制计划正文、不改写一个字。
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"

N = int(sys.argv[1])
HEADER_FILE = sys.argv[2] if len(sys.argv) > 2 else None
OUT = HERE / f"task-{N}-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_t1 = find("## Task 1: ")
i_tn = find(f"## Task {N}: ")
# 本节终点 = 下一个 "## " 标题（Task N+1 或「计划完成后的状态」）
i_end = len(L)
for i in range(i_tn + 1, len(L)):
    if L[i].startswith("## "):
        i_end = i
        break
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}  t1={i_t1+1} t{N}={i_tn+1} end={i_end}")
assert i_t1 <= i_tn < i_end

head = pathlib.Path(HEADER_FILE).read_bytes().decode("utf-8") if HEADER_FILE else ""
if head and nl != "\n":
    head = head.replace("\r\n", "\n").replace("\n", nl)

parts = [head, nl.join(L[0:i_t1]).rstrip(), "", "---", "", nl.join(L[i_tn:i_end]).rstrip(), ""]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
print(f"  含 '## Task {N}: ' = {chk.count(f'## Task {N}: ')}")
print(f"  含 '## Global Constraints' = {chk.count('## Global Constraints')}")
print(f"  含 '## Review Focus' = {chk.count('## Review Focus')}")
others = [m for m in range(1, 10) if m != N and f"## Task {m}: " in chk]
print(f"  不含其它 Task 节 = {not others}  (漏进来的: {others})")
