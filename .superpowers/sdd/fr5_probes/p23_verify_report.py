# -*- coding: utf-8 -*-
"""P23 — 修正报告里那段自述（判据口径写错了）并复跑落盘闸门。

第一次跑 p21 的闸门报了一条 FAIL：「'## fix round 5' 恰 1 次」实际数到 2。
核磁盘后确认：**是尺子的口径错、不是文件错**——第 2 次命中就在报告自己描述这条判据的那句话里
（自指）。故：① 把判据换成「整行等于 '## fix round 5' 的行恰 1 行」；② 把报告里那段自述改成
它真正核了的东西，并把「最终 sha/行数」指到本脚本的输出，不写死一个会被自己改过时的数。
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

OLD = (
    "**报告文件本身的口径**：追加前 `task-1-report.md` 是 **3298 LF 行 / 243343 B / CRLF 0**，\n"
    "sha256[:16] `adad2d0ab59eb81d`；本节以 `\\n` 追加、整个文件按字节写回，落盘后复核\n"
    "「`## fix round 5` 恰出现 1 次」+「原有 15 个 `## ` 标题一个不少」+「前 3298 行逐字未变」。\n"
)
NEW = (
    "**报告文件本身的口径**：追加前 `task-1-report.md` 是 **3298 LF 行 / 243343 B / CRLF 0**、\n"
    "sha256[:16] `adad2d0ab59eb81d`；本节以 `\\n` 追加、整个文件按字节写回。落盘后复核 5 项：\n"
    "① **整行等于本节标题的行恰 1 行**（⚠️ 判据不能写成「那个子串出现 1 次」——描述这条判据的\n"
    "这句话自己就含该子串，`p21` 第一次跑就因此报了一条 FAIL；核磁盘后确认是**尺子的口径错、\n"
    "不是文件错**，与 fix round 4 那次「断言 rc 1 不等于操作失败」同族，故就地改判据而不是改文件）；\n"
    "② 原有 15 个 `## ` 标题一个不少；③ 新文件以「原文（去掉尾部空行）+ 一个换行」开头，\n"
    "即旧内容逐字未变、没有被覆盖；④ CRLF 仍为 0；⑤ 本节没有追加两遍。\n"
    "**最终行数 / 字节 / sha256 以 `fr5_probes/p23_verify_report.py` 的输出为准**——本段自己就被\n"
    "那个脚本改过一次，故不在这里写死一个会被自己改过时的数（账本 Ruling 29 / 评审 Minor 2\n"
    "要消灭的正是这种形态）。`git status --short` = `''`、HEAD = `7b84599`（该报告 gitignored，\n"
    "不在 commit 里）。\n"
)

raw = R.read_bytes()
t = raw.decode("utf-8")
SHA0 = hashlib.sha256(raw).hexdigest()
assert t.count(OLD) == 1, t.count(OLD)
t2 = t.replace(OLD, NEW, 1)
assert t2.count(NEW) == 1 and t2.count(OLD) == 0
R.write_bytes(t2.encode("utf-8"))
back = R.read_bytes()
t3 = back.decode("utf-8")
SHA1 = hashlib.sha256(back).hexdigest()

print("=== 落盘闸门（双向）===")
checks = [
    ("新串在：修正后的自述", t3.count(NEW) == 1),
    ("旧串不在：被判为口径错的那句", t3.count(OLD) == 0),
    ("① 整行等于 '## fix round 5' 的行恰 1 行",
     sum(1 for l in t3.splitlines() if l == "## fix round 5") == 1),
    ("② 原有 15 个 '## ' 标题一个不少",
     all(l in t3 for l in [x for x in t.splitlines() if x.startswith("## ")])
     and len([x for x in t.splitlines() if x.startswith("## ")]) == 15),
    ("③ 追加前的原文逐字未变（与 $env:TEMP 的备份逐行比前 3298 行）",
     (pathlib.Path(subprocess.run(["powershell", "-NoProfile", "-Command", "echo $env:TEMP"],
                                  capture_output=True).stdout.decode().strip())
      / "pe_fr5_report_backup.md").read_bytes().decode("utf-8").splitlines()
     == t3.splitlines()[:3298]),
    ("④ CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("⑤ 本节没有追加两遍", t3.count("### 9. 本轮探针清单") == 1),
    ("⑥ 上一节 '## fix round 4' 仍在", t3.count("\n## fix round 4\n") == 1),
    ("⑦ 全部 16 个 '## ' 顶级标题",
     len([x for x in t3.splitlines() if x.startswith("## ")]) == 16),
]
ok = True
for name, res in checks:
    print("  %s %s" % ("OK  " if res else "FAIL", name))
    ok = ok and res
print()
print("  sha256[:16] %s -> %s" % (SHA0[:16], SHA1[:16]))
print("  bytes %d -> %d ; LF lines %d -> %d ; CRLF %d"
      % (len(raw), len(back), len(t.splitlines()), len(t3.splitlines()), back.count(b"\r\n")))
print()
print("=== 顶级标题清单（应含 fix round 1..5）===")
for i, l in enumerate(t3.splitlines(), 1):
    if l.startswith("## "):
        print("  %5d| %s" % (i, l[:80]))
print()
print("  git status --short =", repr(subprocess.run(["git", "status", "--short"], cwd=str(ROOT),
      capture_output=True).stdout.decode("utf-8", "replace")))
print("  HEAD =", subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
      capture_output=True).stdout.decode().strip())
sys.exit(0 if ok else 1)
