"""第二轮：清扫已结案 Task 1-4 正文里会误导人的陈旧 Task 编号，
以及对照表里那两个已经失效的裸行号（插表后行号整体下移）。"""
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
raw = PLAN.read_bytes()
text = raw.decode("utf-8-sig")
nl = "\r\n" if "\r\n" in text else "\n"
edits = []


def sub(old, new, count, label):
    global text
    if nl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", nl)
        new = new.replace("\r\n", "\n").replace("\n", nl)
    n = text.count(old)
    assert n == count, f"[{label}] 期望 {count}，实为 {n}: {old[:60]!r}"
    text = text.replace(old, new)
    edits.append((label, n))


sub("**这项登记由 Task 12 Step 3 统一做**，见那里的 **#30**",
    "**这项登记由 Task 9（原 Task 12）Step 2 统一做**，见那里的 **#30**",
    1, "T2 §14 #30 归属")
sub("否则会与 Task 12 的清单撞号", "否则会与 Task 9（原 Task 12）的清单撞号",
    1, "T2 撞号")
sub("（不等 Task 12），因为值在这一刻被写死；③ Task 7 消费时不得把它们当成 spec 条文引用。"
    "Task 7 只**消费**、不改这个文件——否则 T7 会让 T2 的指纹测试变红",
    "（不等 Task 9），因为值在这一刻被写死；③ Task 5 的 5.3（安全后置，原文写作时的 Task 7）"
    "消费时不得把它们当成 spec 条文引用。5.3 只**消费**、不改这个文件——否则它会让 T2 的指纹测试变红",
    1, "T2 volume_reduction 消费方")
sub("Task 3 加 `prescription_template`、Task 9 加 `prescription` 与 `weekly_adjustment`",
    "Task 3 加 `prescription_template`、Task 6（原 Task 9）加 `prescription` 与 `weekly_adjustment`",
    1, "T2 REFERENCE_TABLES")
sub("会让 Task 7 的安全后置无法区分二者",
    "会让 Task 5 的 5.3（安全后置，原文写作时的 Task 7）无法区分二者",
    1, "T3 hiit 连带")
sub("其中计划 `:130`（Task 1 节）与 `:378`（Task 4 节）已就地更正，其余保持原样。",
    "其中「**Task 7 只需写入 `prescription_count`**」（Task 1 节）、"
    "「若你判断某一项该推到 Task 5」（Task 4 节）、以及 Task 2/3 节里指向 `safety.py` 与 §14 清单的"
    "四处已就地更正；**其余保持原样、按上表折算**。",
    1, "对照表脚注去掉裸行号")

out = text.encode("utf-8")
PLAN.write_bytes(out)
print(f"[out] bytes={len(out)} lines={text.count(nl)}")
for lab, n in edits:
    print(f"  {n}x  {lab}")
