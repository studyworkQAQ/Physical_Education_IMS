# -*- coding: utf-8 -*-
"""把 `_fr1_fix_sha.py` / `_fr1_fix_report_list.py` 补进报告 §8 第 7 条那份「至今未入库」的清单。

⚠️ 这一步是**自指的**：改这份清单的脚本自己也因此未入库。入库它就得再 amend 一次、
commit 2 的 sha 又变、报告里那 3 处 sha 又得改——故刻意止步于此，并把这件事写进那一条。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
REPORT = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "task-5-report.md"

OLD = ("7. **`task-5-report.md`（本文件）与 `task-5-brief.md` / `_mk_brief5.py` / "
       "`_t5_verify.py` 至今未入库**")
NEW = ("7. **`task-5-report.md`（本文件）与 `task-5-brief.md` / `_mk_brief5.py` / "
       "`_t5_verify.py` / `t5_probes/_fr1_fix_sha.py` / `t5_probes/_fr1_fix_report_list.py` "
       "至今未入库**（后两个就是改本条与改 commit 2 那三处 sha 的脚本自己——**入库它们就得"
       "再 amend 一次、sha 又变、报告又得改**，故刻意止步于此）")

raw = REPORT.read_bytes()
text = raw.decode("utf-8")
assert text.count(OLD) == 1, text.count(OLD)
assert text.count(NEW) == 0
text = text.replace(OLD, NEW, 1)
REPORT.write_bytes(text.encode("utf-8"))
after = REPORT.read_bytes()
atext = after.decode("utf-8")
assert atext.count(NEW) == 1
assert atext.count(OLD) == 0
assert after.count(b"\r\n") == 0 and not after.startswith(b"\xef\xbb\xbf")
print(f"报告：{len(raw)} B / {len(raw.decode('utf-8').splitlines())} 行 → "
      f"{len(after)} B / {len(atext.splitlines())} 行（纯 LF、无 BOM）")
sys.exit(0)
