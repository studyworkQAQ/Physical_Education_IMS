# -*- coding: utf-8 -*-
"""pe_fr4_report.py — 把 SECTION_fix_round_4.md **追加**到 task-1-report.md 末尾。

用法: python pe_fr4_report.py <仓库根>

不许覆盖已有内容：追加前先记下全文的 sha256 与全部 `##`/`###` 标题清单，追加后逐条核
（旧标题一个不少、顺序不变、旧内容整体是新内容的**前缀**）。落盘后 shell 读回确认。
"""
import hashlib
import pathlib
import re
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
D = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎"
REPORT = D / "task-1-report.md"
SECTION = D / "fr4_probes/SECTION_fr4_final.md"

old_b = REPORT.read_bytes()
old = old_b.decode("utf-8")
old_sha = hashlib.sha256(old_b).hexdigest()
assert old.count("## fix round 4") == 0, "已经追加过了？"
assert old.count("## fix round 3") == 1

sec_b = SECTION.read_bytes()
sec = sec_b.decode("utf-8").replace("\r\n", "\n")
assert sec.startswith("## fix round 4"), sec[:40]

print("=== ① 追加前：先核 SECTION 草稿本身落盘了没有（本轮编辑工具静默失败过 8 次）===")
MUST = [
    "5 条成立 + 1 条账本错误 + 2 条不计入",
    ":313-362",
    "另有 17 处",
    "各 50 行、只有 4 行不同",
    "对自己都不自洽",
    "#54 `:588`",
    "各 14 行，purity",
    "根本没有 Ruling 48",
    "命中 **0** 处",
    "亲身撞上「编辑工具报成功而磁盘未写」9 次",
    "### fr4.11 报告的追加方式与自检",
    "13 个 `pe_fr4_*.py`",
    "SECTION_fr4_final.md",
]
MUST_NOT = ["9 个 + 3 份输出", ":312-362", "其余 12 处", "各 15 行", "1 条不成立/已限定",
            "#54 `:587`"]
bad = []
for s in MUST:
    c = sec.count(s)
    print("   新串 %-42s 命中=%d %s" % (s[:40], c, "OK" if c >= 1 else "!! 缺"))
    if c < 1:
        bad.append(("MUST", s))
for s in MUST_NOT:
    c = sec.count(s)
    print("   旧串 %-42s 命中=%d %s" % (s[:40], c, "OK" if c == 0 else "!! 残留"))
    if c != 0:
        bad.append(("MUST_NOT", s))
assert not bad, bad

print()
print("=== ② 追加 ===")
heads_before = re.findall(r"^#{2,4} .*$", old, re.M)
new = old.rstrip("\n") + "\n\n" + sec.rstrip("\n") + "\n"
REPORT.write_bytes(new.encode("utf-8"))

print()
print("=== ③ 落盘后 shell 读回确认 ===")
back_b = REPORT.read_bytes()
back = back_b.decode("utf-8")
heads_after = re.findall(r"^#{2,4} .*$", back, re.M)
print("   bytes %d -> %d   LF %d -> %d   CRLF %d   BOM %s"
      % (len(old_b), len(back_b), old.count("\n"), back.count("\n"),
         back_b.count(b"\r\n"), back_b.startswith(b"\xef\xbb\xbf")))
print("   sha256[:16] 追加前 %s -> 追加后 %s" % (old_sha[:16], hashlib.sha256(back_b).hexdigest()[:16]))
print("   标题数 %d -> %d（新增 %d）" % (len(heads_before), len(heads_after),
                                    len(heads_after) - len(heads_before)))
assert heads_after[:len(heads_before)] == heads_before, "旧标题被改动了！"
assert back.startswith(old.rstrip("\n")), "旧内容不是新内容的前缀 → 覆盖事故"
assert back.count("## fix round 4") == 1
assert back.count("## fix round 3") == 1
new_heads = heads_after[len(heads_before):]
print("   新增的标题：")
for h in new_heads:
    print("     ", h)
assert new_heads[0] == "## fix round 4"
assert len(new_heads) == 13, new_heads   # 1 个 ## + 12 个 ###（fr4.0..fr4.11）
for k in ("### fr4.0", "### fr4.1", "### fr4.2", "### fr4.3", "### fr4.4", "### fr4.5",
          "### fr4.6", "### fr4.7", "### fr4.8", "### fr4.9", "### fr4.10", "### fr4.11"):
    assert back.count(k) == 1, k
# fr3 的最后一行仍在
assert "- 没动 `fr2_probes/` 里的 11 个脚本（只**读**着复跑了 `pe_fr2_rule51.py`）。" in back
print("   fr3.10 的末行仍在 = True")
print("   末尾 2 行 = %r" % back.split("\n")[-3:-1])
print()
print("追加完成：报告 %d 行 / %d 字节" % (len(back.split("\n")), len(back_b)))
