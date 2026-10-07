# -*- coding: utf-8 -*-
"""给评审文件打两处补丁（python 按字节写 + 落盘闸门：新串在、旧串不在）。"""
import pathlib, hashlib
P = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd"
                 r"\2026-10-06-实施计划02-智能处方引擎\task-1-fixchain-review.md")
t = P.read_text(encoding="utf-8")

PATCH = [
    # (旧串, 新串)
    ("今天照字面做同一变异会得到 `479 passed, 2 failed`（红的正是本轮新加的那两条），「全绿」不成立。",
     "今天照字面做同一变异会得到 **`2 failed, 479 passed in 55.48s`、exit 1**（我实跑过：`review_probes/p21.py`，"
     "在 `$env:TEMP` 的 backend 副本上两份都删掉那 3 行；红的正是本轮新加的那两条 "
     "`test_absolute_folding_matches_resolve_name`），「全绿」不成立。"),
    ("`purity:210`/`layering:198` 印的「479 条全绿」，改前口子是真的）；同一变异在 HEAD 上 **2 failed**",
     "`purity:210`/`layering:198` 印的「479 条全绿」，改前口子是真的）；同一变异在 HEAD 上 **`2 failed, 479 passed`**"),
    ("`purity:360`/`layering:346` 印的「全量测试都照样通过」，改前口子是真的）；同一变异在 HEAD 上 **2 failed**",
     "`purity:360`/`layering:346` 印的「全量测试都照样通过」，改前口子是真的）；同一变异在 HEAD 上 **`2 failed`**"),
    ("派单原文：「`progress.md` — 执行账本……grep `硬规矩 #` 把 **#19 / #29 / #30 / #32 / #35 / #39 / #42 / #43 /\n#44 / #46 / #47** / #50 / #51 / #52 / #53 / #54 / #55 / #56 / #57 的定义行都读一遍（散在全文……）」。",
     "派单原文（为避免 markdown 把行首的 `#44` 当标题，下面这行加了缩进）：\n\n"
     "    `progress.md` — 执行账本……grep `硬规矩 #` 把 #19 / #29 / #30 / #32 / #35 / #39 / #42 / #43 /\n"
     "    #44 / #46 / #47 / #50 / #51 / #52 / #53 / #54 / #55 / #56 / #57 的定义行都读一遍（散在全文……）"),
]
for old, new in PATCH:
    n = t.count(old)
    assert n == 1, "旧串命中 %d 次（应为 1）: %r" % (n, old[:60])
    t = t.replace(old, new)

P.write_text(t, encoding="utf-8", newline="\n")
b = P.read_bytes()
t2 = P.read_text(encoding="utf-8")
print("bytes=%d LF=%d CRLF=%d sha256[:16]=%s U+FFFD=%d"
      % (len(b), b.count(b"\n"), b.count(b"\r\n"), hashlib.sha256(b).hexdigest()[:16], t2.count("\ufffd")))
print("\n落盘闸门：")
for old, new in PATCH:
    print("  新串命中 %d ；旧串残留 %d   %s" % (t2.count(new), t2.count(old), new[:48].replace("\n", "\\n")))
print("\n行首是 '#' 但不是标题的行（应为 0）：")
bad = [(i, l) for i, l in enumerate(t2.splitlines(), 1)
       if l.startswith("#") and not l.startswith("# ") and not l.startswith("##")]
print(" ", bad or "无")
print("\nCE-8 那一段现状：")
L = t2.splitlines()
k = next(i for i, l in enumerate(L) if l.startswith("### CE-8"))
for i in range(k, k + 10):
    print("  %4d| %s" % (i + 1, L[i][:110]))
