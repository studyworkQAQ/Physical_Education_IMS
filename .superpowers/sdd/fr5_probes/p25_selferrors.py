# -*- coding: utf-8 -*-
"""P25 — 往 `## fix round 5` 节末尾追加「### 10. 我自己的错误」。读回全文 -> 追加 -> 按字节写回。"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

ANCHOR = ("**编辑工具本轮的使用情况**：对**入库的 4 个文件**一律用 python 按字节写（0 次编辑工具），\n"
          "落盘闸门 26 + 2 + 4 = **32 处全部双向查过**（新串在、旧标记不在）。对自己的探针脚本用了\n"
          "2 次 `SearchReplace`，两次都在随后的运行里得到了预期行为，即都真落盘了——**本轮没有遇到\n"
          "「报成功而磁盘未写」**，但纪律没松。\n")

SEC = """
### 10. 我自己的错误（本轮 6 条，全部自纠；请计入实现者错误计数）

按账本口径（Plan 01 Ruling 80 那次为 #1、fix round 3 那次为 #2），本轮我犯 6 条，编号
**#3–#8**。没有一条造成了错误落盘或错误结论——但**其中 3 条是同一个形态：尺子/判据本身写错，
而被测对象是对的**，这与 fix round 4 那次「断言 rc 1 不等于操作失败」同族，值得单列。

| # | 错在哪 | 怎么发现的 | 处置 |
| --- | --- | --- | --- |
| **#3** | `do_edits.py` v1 把 `test_domain_purity.py:145-147` 与 `:523-525` 的缩进**手抄成 5 个空格**（实际是 4 个）——起因是我用 `'%4d\\| %s'` 打印时把格式串自己那一个空格数进了缩进 | 脚本里的 `assert t.count(old) == 1` 当场报「old 命中 **0** 次」，**在写盘之前** | 改成 `do_edits2.py`：old 段一律**按 key 行从磁盘取**、不再手抄缩进；并先用 `p11/p12` 以 `repr()` 打出所有待改区段的原文。26 处编辑一次通过 |
| **#4** | `p14_astdiff.py` ⓪ 断言「`git diff --name-only 6784d57 -- Document/` 必须为空」，**忘了 `6784d57` 之后还有控制者自己的 `ef48d33` / `d00533c` 两个文档 commit** | 脚本 AssertionError，打出 `['Document/2026-10-06-实施计划02-智能处方引擎.md']` | 判据改成对 **HEAD** 比（本轮工作树改动必须为空），另跑一条 `git diff 6784d57 HEAD -- Document/` 单独交代那两个文档 commit。**尺子错、不是改动面错** |
| **#5** | `p14_astdiff.py` ⑥ 的对照组断言「注入 `_absolute` 语义变异 → 报 DIFF 的单元应为 `test_absolute_folding_matches_resolve_name`」，而变异打在 `_absolute` 里，正确答案是 `['_absolute']` | 脚本 AssertionError | 改判据为 `['_absolute']`；另加一条**真正**落在被测单元上的对照（把新格期望颜色 `GREEN`→`RED` → 报 DIFF 的单元正是 `test_absolute_folding_matches_resolve_name`）。**尺子错** |
| **#6** | `p3_p4_plans_and_means.py` 里写了 `print("… = %r" % ("%.2f" % mean))`——`%r` 拿到的是**字符串**却按 `%r` 之外又多算了一次格式化，`TypeError: must be real number, not str` | 当场崩 | 拆出 `p4_means.py` 重做，并把 `round` / 截断 / `'%.2f'` 三种口径分开打。**副作用**：崩溃发生在 `shutil.rmtree` 之前，`$env:TEMP\\pe_fr5_plan_7pprgs2k` 留了残留，收工时手动删掉并核过 `Get-ChildItem $env:TEMP -Filter "pe_fr5*"` 为空 |
| **#7** | `p21_report.py` 的落盘闸门写了「`'## fix round 5'` 恰出现 **1** 次」，而报告里**描述这条判据的那句话自己就含这个子串** → 恒为 2、判据不可满足（自指） | 闸门报 FAIL；核磁盘确认标题只有 1 行、第 2 次命中在 `:3854` 那句自述里 | 判据改成「**整行等于** `## fix round 5` 的行恰 1 行」（`p23` / `p24`），并把报告里那段自述改成它真正核了的东西、且不写死会被自己改过时的 sha/行数。**尺子错、不是文件错** |
| **#8** | `p23` 的闸门 ② 拿「本次 patch 前的内容」当「追加本节前的原文」来数 `## ` 标题、断言 15 个，而那时 `p21` 已经追加过本节，实数是 16 | 闸门报 FAIL | 改成拿 `$env:TEMP\\pe_fr5_report_backup.md`（**追加速前**的字节备份）当基准：备份 15 个、现在 16 个、多出来的恰是 `## fix round 5`，且备份的 3298 行逐字仍是新文件的前 3298 行（`p24` 全 PASS）。**尺子错** |

**从 #4/#5/#7/#8 这四条里能提取的教训**（不是「下次注意」，是可机械执行的动作）：
写判据时先问一句「**这个判据自己会不会成为它检查的对象的一部分**」（#7 的自指）、
「**基准取的是哪个时点的内容**」（#4 忘了基线之后还有 commit；#8 拿晚了时点的内容当基准）、
「**变异打在哪一个单元上、就该指望哪一个单元报 DIFF**」（#5）。
`p24_gate_only.py` 就是把「基准」显式钉在一个**追加速前的字节备份**上的结果。

"""

raw = R.read_bytes()
t = raw.decode("utf-8")
SHA0 = hashlib.sha256(raw).hexdigest()
LINES0 = len(t.splitlines())
assert t.count(ANCHOR) == 1, t.count(ANCHOR)
assert t.count("### 10. 我自己的错误") == 0, "本节已存在"
assert raw.count(b"\r\n") == 0

t2 = t.rstrip("\n") + "\n" + SEC
R.write_bytes(t2.encode("utf-8"))
back = R.read_bytes()
t3 = back.decode("utf-8")

print("=== 落盘闸门（双向）===")
checks = [
    ("新串在：'### 10. 我自己的错误' 恰 1 次", t3.count("### 10. 我自己的错误") == 1),
    ("新串在：#3..#8 六条都在", all(("**#%d**" % i) in t3 for i in range(3, 9))),
    ("锚段仍在（没被吃掉）", t3.count(ANCHOR) == 1),
    ("旧内容逐字未变（前 %d 行）" % LINES0, t3.splitlines()[:LINES0] == t.splitlines()[:LINES0]),
    ("CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("没有追加两遍", t3.count("从 #4/#5/#7/#8 这四条里能提取的教训") == 1),
    ("'## fix round 5' 整行仍恰 1 行",
     sum(1 for l in t3.splitlines() if l == "## fix round 5") == 1),
]
ok = True
for name, res in checks:
    print("  %s %s" % ("OK  " if res else "FAIL", name))
    ok = ok and res
print()
print("  bytes %d -> %d ; LF lines %d -> %d ; sha256[:16] %s -> %s"
      % (len(raw), len(back), LINES0, len(t3.splitlines()), SHA0[:16],
         hashlib.sha256(back).hexdigest()[:16]))
print("  git status --short =", repr(subprocess.run(["git", "status", "--short"], cwd=str(ROOT),
      capture_output=True).stdout.decode("utf-8", "replace")))
print("  HEAD =", subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
      capture_output=True).stdout.decode().strip())
print()
print("闸门结论:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
