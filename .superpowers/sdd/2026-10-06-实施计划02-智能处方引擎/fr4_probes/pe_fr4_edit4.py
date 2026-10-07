# -*- coding: utf-8 -*-
"""pe_fr4_edit4.py — 修报告 fr4 节里三处与实际不符的自述（按事实报，不掩饰）。

用法: python pe_fr4_edit4.py <仓库根>

要修的三处：
  ① fr4.11 原写「`pe_fr4_report.py`（rc 0）」——实测 rc **1**：追加正确，但它最后那条断言
     按**子串**数 `## fix round 4`，而 fr4.11 正文里正好引用了这个串 → 命中 2。
     必须写成「断言口径错、追加本身正确」，并记下「rc 1 不等于操作失败、照着重跑会追加两遍」。
  ② fr4.0 的闸门表要如实给出两个脚本与两个 rc。
  ③ 取证脚本个数（写报告的过程中又多了 2 个脚本）。
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
REPORT = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

OLD_ROW = ("| 追加报告（含落盘闸门 + 覆盖事故自检） | `python fr4_probes/pe_fr4_report.py .` "
           "| 见 fr4.11 |")
NEW_ROW = ("| 追加报告 + 复核 | `python fr4_probes/pe_fr4_report.py .`；"
           "`python fr4_probes/pe_fr4_verify_report.py .` | 前者 rc **1**"
           "（追加正确、它自己那条子串计数断言写错）、后者 **PASS** rc 0，见 fr4.11 |")

OLD_CNT = ("可一键重跑）：**13 个 `pe_fr4_*.py` + 3 份 `OUT_*.txt` + 2 份报告草稿**"
           "（那份被工具写坏的\n`SECTION_fix_round_4.md` 留着当证据，不删）。")
NEW_CNT = ("可一键重跑）：**15 个 `pe_fr4_*.py` + 3 份 `OUT_*.txt` + 2 份报告草稿 = 20 个条目**"
           "（那份被工具写坏的\n`SECTION_fix_round_4.md` 留着当证据，不删）。")

OLD_411 = """### fr4.11 报告的追加方式与自检

`pe_fr4_report.py`（rc 0）：先读全文、记下 sha256 与全部 `##`/`###`/`####` 标题清单，
再 `旧文（去尾换行）+ 空行 + 本节` 落盘，然后 shell 读回核四件事——
① 旧标题清单是新标题清单的**前缀**（顺序与措辞一个没变）；
② 旧全文是新全文的**前缀**（`back.startswith(old.rstrip())`，即**没有覆盖事故**）；
③ `## fix round 4` 命中恰 1、`## fix round 3` 仍是 1、`### fr4.0`…`### fr4.10` 各命中 1；
④ fr3.10 的末行（「没动 `fr2_probes/` 里的 11 个脚本…」）仍在。
落盘前还有一道**草稿落盘闸门**（就是它抓到了那次 `Write` 静默失败）：11 个新串必须全命中、
6 个旧串必须 0 残留，否则 `assert` 失败、不追加。"""

NEW_411 = """### fr4.11 报告的追加方式与自检（含一次我自己的断言写错）

追加由 `pe_fr4_report.py` 做：先读全文、记下 sha256 与全部 `##`/`###`/`####` 标题清单，
再 `旧文（去尾换行）+ 空行 + 本节` 落盘。**落盘前**有一道草稿落盘闸门（就是它抓到了那次
`Write` 静默失败）：13 个新串必须全命中、6 个旧串必须 0 残留，否则 `assert` 失败、不追加
——本次实跑 **13/13 命中、6/6 零残留**。**落盘后**的自检里，前缀那两条通过、
第三条断言**我自己写错了**：它按**子串**数 `## fix round 4`，而本节正文里正好引用了这个串，
故子串命中 **2**、脚本 **rc 1**。追加本身是对的（脚本已经打印
`bytes 189916 -> 241269`、`LF 2616 -> 3277`、`标题数 77 -> 90（新增 13）`，
且 `heads_after[:77] == heads_before` 与 `back.startswith(old.rstrip())` 两条都在 rc 1 之前
就通过了）。改用 `pe_fr4_verify_report.py` 以**整行**口径复核，**rc 0**：

```
整行 `## fix round 4` 命中 1 次 [2618]；`## fix round 3` 1 次 [2154]；`## fix round 1` [1076]、`## fix round 2` [1527]
### fr4.0…### fr4.11 各整行命中 1 次：2677 / 2720 / 2780 / 2819 / 2885 / 2951 / 2973 / 2998 / 3153 / 3203 / 3238 / 3268
四节先后顺序（字节偏移）fr1(53230) < fr2(75013) < fr3(105324) < fr4(127643)
fr3.10 的末行（「没动 `fr2_probes/` 里的 11 个脚本…」）仍在、且在 `## fix round 4` 之前 = True → **没有覆盖事故**
最终 3278 行 / 241269 字节 / LF 3277 / CRLF 0 / BOM False / 乱码(U+FFFD) False
git status --short = ''；git ls-files .superpowers 计数 = 0（报告在 gitignore 内，不入库）
```

⚠️ 这一条要记下来：**「断言 rc 1」不等于「操作失败」**。看到 rc 1 之后我第一件事是核磁盘上
的实际状态（前缀关系 + 标题清单 + 字节数），确认追加正确、只是断言口径错，才去改断言；
如果照着 rc 1 直接重跑一次 `pe_fr4_report.py`，就会把本节**追加两遍**（它的
`assert old.count("## fix round 4") == 0` 会先拦下来，但那只是运气——正确的做法是先核状态）。
这与硬规矩 #53 是同一族：**尺子坏了要和被测对象坏了指认得一样清楚**。"""

raw = REPORT.read_bytes()
t = raw.decode("utf-8")
assert t.count("\r\n") == 0, "报告应是纯 LF"
for name, old, new in (("闸门表行", OLD_ROW, NEW_ROW), ("脚本个数", OLD_CNT, NEW_CNT),
                       ("fr4.11", OLD_411, NEW_411)):
    c = t.count(old)
    print("  %-10s 旧串命中=%d" % (name, c))
    assert c == 1, (name, c)
    t = t.replace(old, new)
REPORT.write_bytes(t.encode("utf-8"))

back = REPORT.read_bytes().decode("utf-8")
print("  落盘后：bytes=%d LF=%d CRLF=%d" % (len(back.encode("utf-8")), back.count("\n"),
                                          REPORT.read_bytes().count(b"\r\n")))
for name, old, new in (("闸门表行", OLD_ROW, NEW_ROW), ("脚本个数", OLD_CNT, NEW_CNT),
                       ("fr4.11", OLD_411, NEW_411)):
    print("  %-10s 新串命中=%d 旧串命中=%d %s"
          % (name, back.count(new), back.count(old),
             "OK" if back.count(new) == 1 and back.count(old) == 0 else "!! FAIL"))
    assert back.count(new) == 1 and back.count(old) == 0, name
print("三处修正落盘完成")
