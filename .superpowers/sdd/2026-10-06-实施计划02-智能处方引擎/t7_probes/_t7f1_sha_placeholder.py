"""把报告里那个 `<SHA2>` 占位符换成一句真话：一个 commit 无法印自己的 sha。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "task-7-report.md"
src = P.read_text(encoding="utf-8")
assert src.count("<SHA2>") == 2, src.count("<SHA2>")

src = src.replace(
    "| `<SHA2>` | **F1-3** 计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告 |",
    "| **（本 commit）** | **F1-3** 计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告。"
    "⚠️ 一个 commit **印不出自己的 sha**（本报告就在这个 commit 里），故它 = "
    "`git log --oneline -2` 的第 1 条 = 本轮交回控制者的第 2 个 sha |",
)
src = src.replace(
    "* **`<SHA2>`** —— `docs:` F1-3 的计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告",
    "* **（本 commit，sha 印不出来）** —— `docs:` F1-3 的计划正文补丁（11 处替换 + 1 处计数连带）"
    "+ 本报告。⚠️ 一个 commit 无法在自己的内容里印出自己的 sha；它 = `git log --oneline -2` "
    "的第 1 条，也已在本轮交回控制者的最终回复里逐字给出",
)
assert src.count("<SHA2>") == 0
P.write_text(src, encoding="utf-8", newline="")
b = P.read_bytes()
print(f"OK {len(b)} B / {b.count(bytes([10]))} 行 / CRLF={b.count(bytes([13, 10]))}")
