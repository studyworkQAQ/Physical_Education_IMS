"""Ruling 12 落地取证（Plan 03 Task 5）。运行时口径，不用正则数源码。"""
import ast
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
TARGET = BACKEND / "tests" / "pipeline" / "test_backfill.py"

raw = TARGET.read_bytes()
text = raw.decode("utf-8")
tree = ast.parse(text)

# ① 占位符必须清零
placeholders = [t for t in ("TBD", "TEMP-PROBE") if t in text]
print("placeholders_left:", placeholders)

# ② 旧函数名在**全仓**（app + tests）不得再有引用
old_name = "test_backfill_500_students_under_60_seconds"
new_name = "test_backfill_500_students_under_90_seconds"
hits_old = []
hits_new = []
for path in sorted(BACKEND.rglob("*.py")):
    if "t5_probes" in path.parts:
        continue
    body = path.read_text(encoding="utf-8")
    if old_name in body:
        hits_old.append(str(path.relative_to(BACKEND)))
    if new_name in body:
        hits_new.append((str(path.relative_to(BACKEND)), body.count(new_name)))
print("old_name_hits:", hits_old)
print("new_name_hits:", hits_new)

# ③ AST：那个函数确实存在、且它的 body 里恰好一条比较断言阈值 90
funcs = {
    n.name: n
    for n in tree.body
    if isinstance(n, ast.FunctionDef)
}
print("has_old_def:", old_name in funcs, " has_new_def:", new_name in funcs)
fn = funcs[new_name]
comparators = [
    c.value
    for node in ast.walk(fn)
    if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)
    for c in node.test.comparators
    if isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
]
print("assert_numeric_comparators:", comparators)
print("docstring_bytes:", len(fn.body[0].value.value.encode("utf-8")))

# ④ 中文没坏：抽 docstring 里几个必须逐字存在的中文串
must = [
    "数量级哨兵",
    "本原型不予验收",
    "函数名就成了谎话",
    "在本机没有复现",
    "顶回给控制者的数据点",
]
print("chinese_ok:", {m: (m in text) for m in must})

# ⑤ 行尾：本文件不是 backend/data/ 下被 .gitattributes 钉 eol=lf 的文件，
#    但按硬规矩 #89 的扩写，用 read_bytes() 报一次实际计数
print("crlf_count:", raw.count(b"\r\n"), " lf_count:", raw.count(b"\n"))
print("file_bytes:", len(raw))

# ⑥ 整个 tests/ 下还有没有别处引用 60 秒阈值这条断言
sys.exit(0 if not placeholders and not hits_old else 1)
