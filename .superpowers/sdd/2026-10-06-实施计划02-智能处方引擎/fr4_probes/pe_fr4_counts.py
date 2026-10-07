# -*- coding: utf-8 -*-
"""pe_fr4_counts.py — 报告里要引的几个计数/行号，全部实测（不靠记忆）。

用法: python pe_fr4_counts.py <仓库根>
"""
import ast
import pathlib
import re
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
PU = REPO / "backend/tests/architecture/test_domain_purity.py"
LA = REPO / "backend/tests/architecture/test_layering.py"


def lines(p):
    return p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")


print("=== ① purity 里「三条 / 第三条」的全部命中（shell 口径行号，绑定 6784d57）===")
pl = lines(PU)
hits = [i for i, l in enumerate(pl, 1) if re.search(r"三条|第三条|两道", l)]
print("   命中 %d 处: %s" % (len(hits), hits))
for i in hits:
    print("   %4d | %s" % (i, pl[i - 1].strip()[:110]))

print()
print("=== ② 「白名单前缀」在 purity 的全部命中 ===")
w = [i for i, l in enumerate(pl, 1) if "白名单前缀" in l]
print("   %s" % w)
for i in w:
    print("   %4d | %s" % (i, pl[i - 1].strip()[:110]))

print()
print("=== ③ Ruling 54 那一段的行区间与行数（两个文件）===")
for p in (PU, LA):
    ls = lines(p)
    a = [i for i, l in enumerate(ls, 1) if l.strip().startswith("# ------") and "Ruling 54" in l]
    assert len(a) == 1, a
    start = a[0]
    # 段尾 = start 之后**第一个** `    )`（该 assert 的收尾括号）
    end = next(i for i in range(start, len(ls) + 1) if ls[i - 1] == "    )")
    comp = [i for i, l in enumerate(ls, 1) if "后果也要能跑" in l]
    print("   %-22s 段区间 %d..%d = %d 行；其中「后果对拍」子段 %d..%d = %d 行"
          % (p.name, start, end, end - start + 1, comp[0], end, end - comp[0] + 1))

print()
print("=== ④ 两份新增段是否同结构（剥掉断言消息后）===")


def seg(p):
    ls = lines(p)
    a = [i for i, l in enumerate(ls, 1) if l.strip().startswith("# ------") and "Ruling 54" in l][0]
    end = next(i for i in range(a, len(ls) + 1) if ls[i - 1] == "    )")
    return ls[a - 1:end]


s1, s2 = seg(PU), seg(LA)
print("   行数 purity=%d layering=%d 逐字相同=%s" % (len(s1), len(s2), s1 == s2))
d = [i for i in range(min(len(s1), len(s2))) if s1[i] != s2[i]]
print("   不同的行（段内相对行号）= %s" % d)
for i in d:
    print("     purity  : %s" % s1[i].strip()[:100])
    print("     layering: %s" % s2[i].strip()[:100])

print()
print("=== ⑤ fr4_probes 目录清点 ===")
d = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr4_probes"
fs = sorted(x.name for x in d.iterdir())
print("   合计 %d 个: %s" % (len(fs), fs))
print("   .py 脚本 %d 个、OUT_*.txt %d 个、SECTION_*.md %d 个"
      % (sum(1 for f in fs if f.endswith(".py")),
         sum(1 for f in fs if f.startswith("OUT_")),
         sum(1 for f in fs if f.startswith("SECTION_"))))

print()
print("=== ⑥ task-1-report.md 的现状（追加前）===")
rp = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"
b = rp.read_bytes()
t = b.decode("utf-8")
print("   bytes=%d CRLF=%d LF=%d 行数=%d  '## fix round 4' 命中=%d  '## fix round 3' 命中=%d"
      % (len(b), b.count(b"\r\n"), b.count(b"\n"), len(t.split("\n")),
         t.count("## fix round 4"), t.count("## fix round 3")))
print("   末尾 3 行 = %r" % t.split("\n")[-4:-1])
