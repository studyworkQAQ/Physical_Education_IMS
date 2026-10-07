# -*- coding: utf-8 -*-
"""P29 — 把实现者错误 #9 补进报告 §10，并顺手更正 §10 引言里「其中 3 条」这个**又一处计数错**
（表里尺子/判据形态的是 #4/#5/#7/#8 = 4 条，不是 3 条）。"""
import difflib
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

EDITS = [
    ("§10 标题：6 条 -> 7 条",
     "### 10. 我自己的错误（本轮 6 条，全部自纠；请计入实现者错误计数）\n",
     "### 10. 我自己的错误（本轮 7 条，全部自纠；请计入实现者错误计数）\n",
     "本轮 6 条，全部自纠"),
    ("§10 引言：条数/编号/「其中 3 条」的计数错",
     "按账本口径（Plan 01 Ruling 80 那次为 #1、fix round 3 那次为 #2），本轮我犯 6 条，编号\n"
     "**#3–#8**。没有一条造成了错误落盘或错误结论——但**其中 3 条是同一个形态：尺子/判据本身写错，\n"
     "而被测对象是对的**，这与 fix round 4 那次「断言 rc 1 不等于操作失败」同族，值得单列。\n",
     "按账本口径（Plan 01 Ruling 80 那次为 #1、fix round 3 那次为 #2），本轮我犯 **7** 条，编号\n"
     "**#3–#9**。没有一条造成错误落盘；**#9 让报告里留下 3 个过时数字，已就地更正并在原处标注**。\n"
     "其中 **4 条（#4 / #5 / #7 / #8）是同一个形态：尺子/判据本身写错、而被测对象是对的**，这与\n"
     "fix round 4 那次「断言 rc 1 不等于操作失败」同族，值得单列。\n"
     "（⚠️ 这段引言原先写「其中 **3** 条」，而表里那个形态实际是 4 条——**又一处计数错**，\n"
     "由 #9 那次复核顺手抓到；计数错在本项目已经是 Ruling 49/50/53/55/73 反复出现的一族。）\n",
     "本轮我犯 6 条，编号\n**#3–#8**"),
    ("§10 表格：补 #9 那一行",
     "**从 #4/#5/#7/#8 这四条里能提取的教训**",
     "| **#9** | 报告里留了 **3 个过时数字**：§3 ⓪ 的 numstat（原写 `daily 5/2・purity 73/17・"
     "layering 59/14`）、§3 ② 的 purity `test_absolute_folding_matches_resolve_name` docstring "
     "行数（原写 `50->80`）、§1.8 的 `daily.py 5 insertions / 2 deletions`。根因：这些数是在 "
     "`p16`（补两处行内主语）/ `p18`（四处散文重排）**之前**取的，而我先写了报告、后做的重排 "
     "| commit 之后跑 `git show --numstat HEAD` 与 `p27_postcommit_nums.py` 复核，权威值是 "
     "`6/3・74/17・60/15・11/4`（`--shortstat` = 151 insertions / 39 deletions）与 `50->81` "
     "| `p28_fix_stale_nums.py` 就地更正 3 处，并在 §3 ⓪ 与 §1.8 两处明写「原写 …，已过时」。"
     "**这正是账本 Ruling 29 / CE-4 / 评审 Minor 2 要消灭的形态；而我刚在 §7 里正面确认过控制者"
     "这轮把这件事做对了（CE-fr5-8 / CE-fr5-9），转头自己犯了一次** |\n\n"
     "**从 #4/#5/#7/#8 这四条里能提取的教训**",
     "| **#9** | 报告里留了 **3 个过时数字**：§3 ⓪ 的 numstat（原写 `daily 5/2・purity 73/17・"
     "layering 59/14`）、§3 ② 的 purity `test_absolute_folding_matches_resolve_name` docstring "
     "行数（原写 `50->80`）、§1.8 的 `daily.py 5 insertions / 2 deletions`。根因：这些数是在 "
     "`p16`（补两处行内主语）/ `p18`（四处散文重排）**之前**取的，而我先写了报告、后做的重排 "
     "| commit 之后跑 `git show --numstat HEAD` 与 `p27_postcommit_nums.py` 复核，权威值是 "
     "`6/3・74/17・60/15・11/4`（`--shortstat` = 151 insertions / 39 deletions）与 `50->81` "
     "| `p28_fix_stale_nums.py` 就地更正 3 处，并在 §3 ⓪ 与 §1.8 两处明写「原写 …，已过时」。"
     "**这正是账本 Ruling 29 / CE-4 / 评审 Minor 2 要消灭的形态；而我刚在 §7 里正面确认过控制者"
     "这轮把这件事做对了（CE-fr5-8 / CE-fr5-9），转头自己犯了一次** |\n\n"
     "**从 #4/#5/#7/#8 这四条里能提取的教训**"),
    ("§10 收尾：补 #9 的教训",
     "`p24_gate_only.py` 就是把「基准」显式钉在一个**追加速前的字节备份**上的结果。\n",
     "`p24_gate_only.py` 就是把「基准」显式钉在一个**追加速前的字节备份**上的结果。\n"
     "**#9 的教训是另一族、也更基础**：写完报告之后又动了代码或散文，就必须把报告里**每一个数字**\n"
     "重跑一遍；或者反过来，把所有 cosmetic 改动做完再落笔。本轮我做的是「先落笔、后重排」，\n"
     "于是必然产生过时数——不是运气不好，是顺序错了。\n",
     "`p24_gate_only.py` 就是把「基准」显式钉在一个**追加速前的字节备份**上的结果。\n\n"),
]

raw = R.read_bytes()
t = raw.decode("utf-8")
T_ORIG = t
SHA0 = hashlib.sha256(raw).hexdigest()
L0 = len(t.splitlines())
assert raw.count(b"\r\n") == 0

for name, old, new, absent in EDITS:
    assert t.count(old) == 1, (name, t.count(old))
    t = t.replace(old, new, 1)
    assert t.count(new) >= 1, name
    if absent != new:
        assert t.count(absent) == 0, (name, t.count(absent))
    print("  OK  %s" % name)

R.write_bytes(t.encode("utf-8"))
back = R.read_bytes()
t3 = back.decode("utf-8")
print()
print("=== 落盘闸门（双向）===")
checks = [
    ("新串在：#3–#9", "**#3–#9**" in t3),
    ("新串在：本轮 7 条", "本轮 7 条，全部自纠" in t3),
    ("新串在：#9 表格行", "| **#9** | 报告里留了 **3 个过时数字**" in t3),
    ("新串在：4 条同形态", "其中 **4 条（#4 / #5 / #7 / #8）是同一个形态" in t3),
    ("新串在：#9 的教训段", "**#9 的教训是另一族、也更基础**" in t3),
    ("旧串不在：本轮 6 条", "本轮 6 条，全部自纠" not in t3),
    ("旧串不在：#3–#8", "**#3–#8**" not in t3),
    ("旧串不在：「其中 3 条是同一个形态」", "其中 3 条是同一个形态" not in t3),
    ("#3..#9 七条都在", all(("**#%d**" % i) in t3 for i in range(3, 10))),
    ("CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("'## fix round 5' 整行仍恰 1 行",
     sum(1 for l in t3.splitlines() if l == "## fix round 5") == 1),
    ("§1..§9 小节仍在", all(("### %d. " % i) in t3 for i in range(0, 10))),
    ("改动面只有这 4 处（diff 的 +/- 行数在 4..40 之间）",
     4 <= sum(1 for l in difflib.unified_diff(T_ORIG.splitlines(), t3.splitlines(),
                                              lineterm="", n=0)
              if l[:1] in "+-" and l[:3] not in ("+++", "---")) <= 40),
]
ok = True
for name, res in checks:
    print("  %s %s" % ("OK  " if res else "FAIL", name))
    ok = ok and res
print()
print("  bytes %d -> %d ; LF lines %d -> %d ; sha256[:16] %s -> %s"
      % (len(raw), len(back), L0, len(t3.splitlines()), SHA0[:16],
         hashlib.sha256(back).hexdigest()[:16]))
print("  git status --short =", repr(subprocess.run(["git", "status", "--short"], cwd=str(ROOT),
      capture_output=True).stdout.decode("utf-8", "replace")))
print("  HEAD =", subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
      capture_output=True).stdout.decode().strip())
print()
print("闸门结论:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
