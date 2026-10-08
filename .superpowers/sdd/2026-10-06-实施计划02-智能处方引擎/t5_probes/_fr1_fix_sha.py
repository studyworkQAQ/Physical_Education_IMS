# -*- coding: utf-8 -*-
"""把报告里 commit 2 的 sha 从 `8350d30` 改成 amend 之后的 `f9b6ed5`，并补一句 amend 说明。

原因：`_fr1_report_append.py` 自己在 commit 2 之后又被改过（闸门字典从「恰好 N 次」放宽成
「至少 N 次」），故把它 `git add` 后 `git commit --amend --no-edit`，sha 随之变。
**没 push，故 amend 安全；两个 commit 的数目没变（派单要求的 2 个）。**
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
REPORT = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "task-5-report.md"
OLD, NEW = "8350d30", "f9b6ed5"


def git(*a) -> str:
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


assert git("rev-parse", "--short", "HEAD") == NEW, git("rev-parse", "--short", "HEAD")
assert git("rev-parse", "--short", "HEAD~1") == "fe3a6df"

raw = REPORT.read_bytes()
text = raw.decode("utf-8")
before = len(raw)
n = text.count(OLD)
assert n == 2, f"报告里 {OLD} 命中 {n} 次、期望 2 次"
assert text.count(NEW) == 0, "新 sha 已经在报告里了？"

NOTE = (
    "\n⚠️ **commit 2 被 `--amend` 过一次**（`8350d30` → `f9b6ed5`，"
    "**没 push**，故安全；两个 commit 的数目没变）：`_fr1_report_append.py` 自己在"
    "commit 2 之后又被改过（写盘前闸门从「恰好 N 次」放宽成「至少 N 次」——"
    "真闸门是 `after_text == before_text + payload` 那一句逐字对账，这一组只挡「漏写了一节」），"
    "故把它补进 commit 2 而不是留一个脏工作树。\n"
)
anchor = "`git add` 一律**按文件名逐个加**"
assert text.count(anchor) == 1, text.count(anchor)
text = text.replace(OLD, NEW).replace(anchor, NOTE.lstrip("\n") + "\n" + anchor, 1)

REPORT.write_bytes(text.encode("utf-8"))
after = REPORT.read_bytes()
atext = after.decode("utf-8")
print(f"报告：{before} B / {len(text.splitlines())} 行 → {len(after)} B / "
      f"{len(atext.splitlines())} 行")
assert atext.count(OLD) == 1, "amend 说明里刻意保留了一次旧 sha"
assert atext.count(NEW) == 3, atext.count(NEW)
assert atext.count("commit 2 被 `--amend` 过一次") == 1
assert after.count(b"\r\n") == 0, "报告应保持纯 LF"
assert not after.startswith(b"\xef\xbb\xbf")
print(f"闸门：旧 sha 剩 1 次（在 amend 说明里）、新 sha 3 次、纯 LF、无 BOM ✓")
print(f"commit1 = {git('rev-parse', '--short', 'HEAD~1')}  "
      f"commit2 = {git('rev-parse', '--short', 'HEAD')}")
sys.exit(0)
