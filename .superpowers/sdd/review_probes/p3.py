# -*- coding: utf-8 -*-
"""Probe P3: 真仓相对导入全貌（purity:407-411 / layering:148-159）+ 目录计数（layering:371-385）。"""
import ast, pathlib, collections, subprocess, sys
BK = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
os_cwd = BK

print("=== A. 全仓 app/ 下的相对导入（docstring 印的那条命令，逐字照跑）===")
rows = []
for p in sorted(pathlib.Path('app').rglob('*.py')):
    for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows.append((p, n.lineno, n.level, n.module))
for i, (p, ln, lv, mod) in enumerate(rows, 1):
    print("  %2d  %s %s %s %s" % (i, p.as_posix(), ln, lv, mod))
print("  合计 %d 条；level 分布 %s；顶层包分布 %s" % (
    len(rows), dict(collections.Counter(r[2] for r in rows)),
    dict(collections.Counter(r[0].parts[1] for r in rows))))
print("  module 为空的形状有 %d 条: %s" % (
    sum(1 for r in rows if r[3] is None), [(r[0].as_posix(), r[1]) for r in rows if r[3] is None]))
print("  第 7 行是: %s" % (" ".join(str(x) for x in rows[6]) if len(rows) >= 7 else "N/A"))

print("\n=== B. app/db/models/__init__.py:74 原文 ===")
init = (BK / "app/db/models/__init__.py").read_text(encoding="utf-8").splitlines()
for i in (72, 73, 74, 75):
    print("  %4d| %s" % (i, init[i - 1]))

print("\n=== C. 目录计数（layering:373 那条 Counter 命令，在仓库根跑）===")
root = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
c = collections.Counter(p.parts[2] for p in (root / 'backend/app').rglob('*.py')
                        if p.parts[2] in ('pipeline', 'db', 'domain'))
print("  HEAD(ef48d33 工作树) ->", sorted(c.items()), sum(c.values()))
print("  单目录被搬空时剩余: 24-11(db)=%d  24-7(pipeline)=%d  24-6(domain)=%d" % (
    sum(c.values()) - c['db'], sum(c.values()) - c['pipeline'], sum(c.values()) - c['domain']))

print("\n=== D. git 口径的计数（基线 e26347f 与 ad1d190）===")
for rev in ("e26347f", "ad1d190", "6784d57"):
    out = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", rev,
                          "--", "backend/app/pipeline", "backend/app/db", "backend/app/domain"],
                         capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    cc = collections.Counter(x.split("/")[2] for x in out if x.endswith(".py"))
    print("  %-9s -> %s  合计 %d" % (rev, sorted(cc.items()), sum(cc.values())))

print("\n=== E. domain 的 .py 数（purity:85-88 说基线 e26347f 上是 6）===")
for rev in ("e26347f", "6784d57"):
    out = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", rev,
                          "--", "backend/app/domain"], capture_output=True, text=True,
                         encoding="utf-8").stdout.splitlines()
    print("  %-9s -> %d 个: %s" % (rev, len(out), [x.split("/")[-1] for x in out]))
