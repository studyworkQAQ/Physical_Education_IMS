# -*- coding: utf-8 -*-
"""Probe P2: 重建合成树，重跑 test_domain_purity.py:527-541 的 14 行 G1/G2/G3 探针表。
硬规矩 #53：同时重定向 BACKEND 与 DOMAIN；并带一行已知 GREEN 的干净对照。"""
import sys, pathlib, tempfile, traceback, shutil
sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture")
import test_domain_purity as P

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_synth_p2_"))
BACKEND = TMP / "backend"
DOMAIN = BACKEND / "app" / "domain"
DOMAIN.mkdir(parents=True)
# 5 个干净填充文件，让 len(scanned) >= 5 的空转守卫不误红（否则 14 行会全 RED，
# 而那是 harness 坏、不是探针的结论 —— 正是硬规矩 #53 要防的形态）
for i in range(5):
    (DOMAIN / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
PROBE = DOMAIN / "probe.py"

P.BACKEND = BACKEND
P.DOMAIN = DOMAIN
assert P._domain_files.__module__ == P.__name__

ROWS = [
    ("control: VALUE = 1 (已知 GREEN 对照)", "VALUE = 1\n", "GREEN", "GREEN", "GREEN"),
    ("1  _f = open; _f('x')", "_f = open\n_f('x')\n", "GREEN", "GREEN", "GREEN"),
    ("2  def reopen(): ... 然后 reopen()", "def reopen():\n    return 1\n\n\nreopen()\n", "GREEN", "GREEN", "GREEN"),
    ("3  def open_ended(): ... 然后 open_ended()", "def open_ended():\n    return 1\n\n\nopen_ended()\n", "GREEN", "GREEN", "GREEN"),
    ('4  只有 docstring:「不要用 datetime.now()，也不要 open(」',
     '"""不要用 datetime.now()，也不要 open("""\nVALUE = 1\n', "GREEN", "GREEN", "GREEN"),
    ("5  open('x')", "open('x')\n", "GREEN", "RED", "GREEN"),
    ("6  import builtins; builtins.open('x')", "import builtins\nbuiltins.open('x')\n", "RED", "RED", "GREEN"),
    ("7  import datetime as dt; dt.datetime.now()", "import datetime as dt\ndt.datetime.now()\n", "RED", "RED", "GREEN"),
    ('8  __import__("datetime").datetime.now()', '__import__("datetime").datetime.now()\n', "GREEN", "GREEN", "GREEN"),
    ('9  __import__("os").listdir(".")', '__import__("os").listdir(".")\n', "GREEN", "GREEN", "GREEN"),
    ('10 __import__("builtins").open("x")', '__import__("builtins").open("x")\n', "GREEN", "GREEN", "GREEN"),
    ('11 getattr(__import__("datetime"), "datetime").now()',
     'getattr(__import__("datetime"), "datetime").now()\n', "GREEN", "GREEN", "GREEN"),
    ('12 eval("__import__(\'datetime\').datetime.now()")',
     """eval("__import__('datetime').datetime.now()")\n""", "GREEN", "GREEN", "GREEN"),
    ('13 def _f(x): return getattr(x, "now")()',
     'def _f(x):\n    return getattr(x, "now")()\n', "GREEN", "GREEN", "GREEN"),
    ("14 def _f(table): return table[0]()", "def _f(table):\n    return table[0]()\n", "GREEN", "GREEN", "GREEN"),
]

GUARDS = [("G1", P.test_domain_imports_stay_within_the_allow_list),
          ("G2", P.test_domain_has_no_clock_or_file_access),
          ("G3", P.test_domain_has_no_filesystem_access)]

print("%-52s %-6s %-6s %-6s   %s" % ("probe.py 的内容", "G1", "G2", "G3", "期望(G1,G2,G3) / 判定"))
bad = 0
for label, src, e1, e2, e3 in ROWS:
    PROBE.write_text(src, encoding="utf-8")
    got = []
    msgs = []
    for _name, fn in GUARDS:
        try:
            fn()
            got.append("GREEN")
        except AssertionError as ex:
            got.append("RED")
            msgs.append(str(ex).splitlines()[-1][:110])
        except Exception as ex:                       # harness 坏了要能看出来
            got.append("ERROR:" + type(ex).__name__)
            msgs.append(repr(ex)[:110])
    want = [e1, e2, e3]
    ok = (got == want)
    if not ok:
        bad += 1
    print("%-52s %-6s %-6s %-6s   %s %s%s" % (label[:52], got[0], got[1], got[2],
                                              "OK " if ok else "DIFF", want, ("  | " + " || ".join(msgs)) if msgs else ""))
    # 空转守卫误红检测
    for m in msgs:
        if "只扫到" in m or "领域层目录缺失" in m:
            print("   !! harness 误红（空转守卫）:", m)
            bad += 1

print("\n不符行数 =", bad)
print("\n=== 附：FORBIDDEN_IO 子串命中数（purity:573-574）===")
for label, src in [('__import__("os").listdir(".")', '__import__("os").listdir(".")\n'),
                   ("对照组 import os / os.listdir", 'import os\nos.listdir(".")\n')]:
    hits = [t for t in P.FORBIDDEN_IO if t in src]
    print("  %-34s 命中 %d 个: %s" % (label[:34], len(hits), hits))

shutil.rmtree(TMP, ignore_errors=True)
print("\n临时树已删除:", TMP, TMP.exists())
