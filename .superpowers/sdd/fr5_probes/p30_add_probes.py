# -*- coding: utf-8 -*-
"""P30 — 把 p21..p30 补进报告 §9 的探针清单（原表只列到 p20，是写报告时尚未产生的那些）。"""
import difflib
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
R = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

OLD = ("| `p20_dispatch_claims.py` | 派单事实性断言逐条亲验（§7 的证据来源），含 HEAD 上「2 failed, 479 passed」的复现 |\n")
NEW = OLD + """| `p21_report.py` | 把本节追加进 `task-1-report.md`（读回全文 → 追加 → 按字节写回 → 双向闸门） |
| `p22_findpct.py` | 定位 `p21` 那次 `%` 格式化崩溃的真凶（`100%**` 少写一个 `%`） |
| `p23_verify_report.py` | 就地修正报告自述里写错的判据口径（自指），并复跑闸门 |
| `p24_gate_only.py` | **只读**闸门：拿 `$env:TEMP\\pe_fr5_report_backup.md`（追加速前的字节备份）当基准，核 10 项 |
| `p25_selferrors.py` | 追加 §10「我自己的错误」 |
| `p27_postcommit_nums.py` | commit 之后复核 numstat / docstring 行数 / 注释条数（`p14` 的 ⓪ 段在 commit 后因工作树无 diff 必然断言失败，故另写；**没有 p26**，编号跳过） |
| `p28_fix_stale_nums.py` | 就地更正报告里 3 个过时数字（实现者错误 #9） |
| `p29_add_err9.py` | 把 #9 补进 §10，并更正 §10 引言里「其中 3 条」这个计数错 |
| `p30_add_probes.py` | 把 p21–p30 补进本清单（本行由它自己写入；清单在写报告时只到 p20，因为 p21 之后才存在） |
"""

raw = R.read_bytes()
t = raw.decode("utf-8")
T_ORIG = t
SHA0 = hashlib.sha256(raw).hexdigest()
L0 = len(t.splitlines())
assert raw.count(b"\r\n") == 0
assert t.count(OLD) == 1, t.count(OLD)
t = t.replace(OLD, NEW, 1)
R.write_bytes(t.encode("utf-8"))
back = R.read_bytes()
t3 = back.decode("utf-8")

print("=== 落盘闸门（双向）===")
checks = [
    ("新串在：p21..p30 九行都在",
     all(("| `p%d" % i) in t3 for i in (21, 22, 23, 24, 25, 27, 28, 29, 30))),
    ("旧串不在：p20 那行不再是清单最后一行",
     t3.count(OLD + "\n**编辑工具本轮的使用情况**") == 0),
    ("p20 那行仍在", t3.count(OLD) == 1),
    ("没有追加两遍", t3.count("| `p30_add_probes.py` |") == 1),
    ("CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("'## fix round 5' 整行仍恰 1 行",
     sum(1 for l in t3.splitlines() if l == "## fix round 5") == 1),
    ("§10 仍在", t3.count("### 10. 我自己的错误") == 1),
    ("改动面只有这一处（diff +/- 行数在 9..12 之间）",
     9 <= sum(1 for l in difflib.unified_diff(T_ORIG.splitlines(), t3.splitlines(),
                                              lineterm="", n=0)
              if l[:1] in "+-" and l[:3] not in ("+++", "---")) <= 12),
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
