# -*- coding: utf-8 -*-
"""P28 — 修正报告里 3 个**过时数字**（实现者错误 #9）。

那 3 个数是在 p16（补两处主语）/ p18（四处散文重排）之前取的，两次纯 docstring 改动之后
numstat 与 docstring 行数都变了，而我先写了报告、后做的重排 → 报告里留了会被自己改过时的数。
**这正是账本 Ruling 29 / CE-4 / 评审 Minor 2 要消灭的形态，我自己刚在 §7 的 CE-fr5 清单里
批评过它，转头就犯了一次。** 以 `git show --numstat HEAD` 与 p27 的重跑值为权威值就地更正。
"""
import difflib
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

EDITS = [
    ("numstat 更正（§3 ⓪）",
     "git diff --numstat HEAD         = daily.py 5/2 ; test_domain_purity.py 73/17 ;\n"
     "                                  test_layering.py 59/14 ; test_models.py 11/4\n",
     "git diff --numstat HEAD         = daily.py 6/3 ; test_domain_purity.py 74/17 ;\n"
     "                                  test_layering.py 60/15 ; test_models.py 11/4\n"
     "git diff --shortstat HEAD^ HEAD = 4 files changed, 151 insertions(+), 39 deletions(-)\n"
     "（⚠️ 这三个数**改过一次**：先写报告、后做 p16/p18 两次纯 docstring 重排，故原写的\n"
     " 5/2・73/17・59/14 已过时。权威值是 `git show --numstat HEAD`，见 `p27_postcommit_nums.py`。\n"
     " 这就是账本 Ruling 29 / CE-4 要消灭的「留一个会被自己改过时的数」——实现者错误 #9。）\n",
     "daily.py 5/2 ; test_domain_purity.py 73/17"),
    ("docstring 行数更正（§3 ②）",
     "test_domain_purity.py  _absolute 51->55 ; test_absolute_folding_matches_resolve_name 50->80 ;\n",
     "test_domain_purity.py  _absolute 51->55 ; test_absolute_folding_matches_resolve_name 50->81 ;\n",
     "test_absolute_folding_matches_resolve_name 50->80 ;"),
    ("daily.py 的 numstat 更正（§1.8）",
     "⚠️ 这是生产文件：本轮对 `daily.py` 的改动是 **5 insertions / 2 deletions**，\n",
     "⚠️ 这是生产文件：本轮对 `daily.py` 的改动是 **6 insertions / 3 deletions**（`git show\n"
     "--numstat HEAD`；原写 5/2，同样是 p18 那次重排之前的数——实现者错误 #9），\n",
     "改动是 **5 insertions / 2 deletions**"),
]

raw = R.read_bytes()
t = raw.decode("utf-8")
SHA0 = hashlib.sha256(raw).hexdigest()
L0 = len(t.splitlines())
assert raw.count(b"\r\n") == 0
T_ORIG = t

for name, old, new, absent in EDITS:
    assert t.count(old) == 1, (name, t.count(old))
    t = t.replace(old, new, 1)
    assert t.count(new) >= 1 and t.count(absent) == 0, name
    print("  OK  %s" % name)

R.write_bytes(t.encode("utf-8"))
back = R.read_bytes()
t3 = back.decode("utf-8")
print()
print("=== 落盘闸门（双向）===")
checks = [("新串在 / 旧串不在：%s" % n,
           t3.count(nw) >= 1 and t3.count(ab) == 0) for n, o, nw, ab in EDITS]
checks += [
    ("权威值在：151 insertions(+), 39 deletions(-)", "151 insertions(+), 39 deletions(-)" in t3),
    ("CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("'## fix round 5' 整行仍恰 1 行",
     sum(1 for l in t3.splitlines() if l == "## fix round 5") == 1),
    ("§10 仍在（没被吃掉）", t3.count("### 10. 我自己的错误") == 1),
    ("改动面只有这 3 处（diff 的 +/- 行数在 3..20 之间）",
     3 <= sum(1 for l in difflib.unified_diff(T_ORIG.splitlines(), t3.splitlines(), lineterm="", n=0)
              if l[:1] in "+-" and l[:3] not in ("+++", "---")) <= 20),
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
