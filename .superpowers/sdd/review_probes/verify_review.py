# -*- coding: utf-8 -*-
"""落盘闸门：读回确认（硬规矩 #48：同时查「新串在」和结构完整）。"""
import pathlib, hashlib
P = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd"
                 r"\2026-10-06-实施计划02-智能处方引擎\task-1-fixchain-review.md")
t = P.read_text(encoding="utf-8")
b = P.read_bytes()
print("bytes=%d  LF=%d  CRLF=%d  sha256[:16]=%s  U+FFFD=%d"
      % (len(b), b.count(b"\n"), b.count(b"\r\n"), hashlib.sha256(b).hexdigest()[:16], t.count("\ufffd")))
print("\n=== 全部 ## / # 标题 ===")
for i, l in enumerate(t.splitlines(), 1):
    if l.startswith("#"):
        print("  %4d| %s" % (i, l[:100]))
print("\n=== 关键串命中次数（每条应 >= 1）===")
for s in ["Approved with findings", "I-1 ", "I-2 ", "M-1 ", "M-2 ", "M-3 ", "M-4 ", "M-5 ", "M-6 ",
          "CE-1", "CE-2", "CE-3", "CE-4", "CE-5", "CE-6", "CE-7", "CE-8",
          "from ..indicators import X", "479 passed", "SEARCH stratification_result",
          "红档 9 / GREEN 2", "RED 9 / GREEN 2", "440f7167610df187", "50d776680defc25e",
          "0c68f1ae1b506717", "不可复核项（7 项）", "ef48d33", "3298"]:
    print("  %-34s %d" % (s[:34], t.count(s)))
print("\n=== findings 计数自证 ===")
import re
print("  Critical 段落里的条目数 =", len(re.findall(r"^#### C-\d", t, re.M)))
print("  Important 段落里的条目数 =", len(re.findall(r"^#### I-\d", t, re.M)))
print("  Minor 段落里的条目数     =", len(re.findall(r"^#### M-\d", t, re.M)))
print("  控制者错误条目数         =", len(re.findall(r"^### CE-\d", t, re.M)))
