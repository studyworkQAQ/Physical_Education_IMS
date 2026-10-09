"""把报告从 t5_probes/_report.md 落到 .superpowers/ 下（python 写、规范化行尾、立刻复核）。

⚠️ 纪律：报告一律用 python 写（不用编辑器工具反复改 .superpowers/ 下的文件）；
落盘后立刻用 read_bytes() 复核字节数与行数（硬规矩 #89 扩写），
因为这个 IDE 曾把陈旧且截断的缓存写回磁盘（Plan 02 永久丢了约 107 KB）。
"""
import hashlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
SRC = BACKEND / "t5_probes" / "_report.md"
DEST = (REPO / ".superpowers" / "sdd"
        / "2026-10-08-实施计划03-反馈预警与CRUD-API层" / "task-5-report.md")

CODE_HEAD = "3be0bc1"

text = SRC.read_text(encoding="utf-8")
# 行尾规范化为 LF（markdown 的通用口径；.superpowers/ 不在 .gitattributes 的
# backend/data/*.yaml text eol=lf 规则里，故这里显式定一次）
text = text.replace("\r\n", "\n").replace("\r", "\n")

# __HEAD__ 有两个含义要分开：代码的最后一个 commit（已知），与报告自身所在的
# 收尾 commit（写报告时还不存在）。**不编一个 sha**，如实写成两句。
text = text.replace(
    "**结案** `__HEAD__`",
    f"**代码结案** `{CODE_HEAD}`（报告自身在其后的收尾 commit，sha 见交回控制者那一段）",
)
text = text.replace(
    "| **`__HEAD__`** | 收尾：结案报告（本文件） |",
    "| **（收尾 commit）** | 结案报告（本文件）。⚠️ 它的 sha 在写本文件时还不存在"
    "（报告在自己的 commit 里），故不在此处编一个——见交回控制者那一段 |",
)
assert "__HEAD__" not in text, "还有没填的占位符"

DEST.parent.mkdir(parents=True, exist_ok=True)
raw = text.encode("utf-8")
DEST.write_bytes(raw)

# --- 落盘后立刻复核（不信 write_bytes 的返回值，重新读一遍磁盘）---
back = DEST.read_bytes()
print("dest:", DEST)
print("write_bytes == read_bytes 逐字节相同:", back == raw)
print("bytes:", len(back))
print("lines:", back.count(b"\n") + (0 if back.endswith(b"\n") else 1))
print("crlf:", back.count(b"\r\n"), " lf:", back.count(b"\n"))
print("sha256[:16]:", hashlib.sha256(back).hexdigest()[:16].upper())
print("starts_with_BOM:", back.startswith(b"\xef\xbb\xbf"))
first, *_, last = back.decode("utf-8").splitlines()
print("first_line:", first)
print("last_line :", last)

# 八节标题逐个点名（简报 0.6 节要求的八节）
body = back.decode("utf-8")
sections = [f"## {mark}" for mark in
            ("① 环境与基线复现", "② schema 变更", "③ 七个端点",
             "④ `late` 的三条边界测试", "⑤ `test_models.py`",
             "⑥ 待清扫", "⑦ 最终验收", "⑧ commit")]
missing = [s for s in sections if s not in body]
print("八节齐全:", not missing, "缺:", missing)
sys.exit(0 if not missing and back == raw else 1)
