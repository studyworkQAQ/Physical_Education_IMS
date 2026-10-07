"""P5 — Ruling 68：合成树配方。

phase A = 照 ``test_domain_purity.py:523-525`` 的**字面**配方（只重定向 ``DOMAIN``、树里只有
          1 个 ``.py``）→ 预期 14 行连同干净对照行**全 RED**。
phase B = 补正后的配方（``DOMAIN`` **和** ``BACKEND`` 都重定向、树里 >= 5 个 ``.py``）
          → 预期 14 行 × 3 列 = 42 格与源码那张表**逐格相同**。
"""
import importlib.util
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

spec = importlib.util.spec_from_file_location(
    "pur_mod", BACKEND / "tests/architecture/test_domain_purity.py")
pur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pur)

# 源码 :527-541 那张表，逐行照抄（列顺序 G1 allow-list / G2 AST 时钟 open / G3 子串 IO）
TABLE_SRC = [
    ('_f = open; _f(\'x\')', "GREEN", "GREEN", "GREEN"),
    ('def reopen(): ...\nreopen()', "GREEN", "GREEN", "GREEN"),
    ('def open_ended(): ...\nopen_ended()', "GREEN", "GREEN", "GREEN"),
    ('docstring only', "GREEN", "GREEN", "GREEN"),
    ("open('x')", "GREEN", "RED", "GREEN"),
    ("import builtins; builtins.open('x')", "RED", "RED", "GREEN"),
    ("import datetime as dt; dt.datetime.now()", "RED", "RED", "GREEN"),
    ('__import__("datetime").datetime.now()', "GREEN", "GREEN", "GREEN"),
    ('__import__("os").listdir(".")', "GREEN", "GREEN", "GREEN"),
    ('__import__("builtins").open("x")', "GREEN", "GREEN", "GREEN"),
    ('getattr(__import__("datetime"), "datetime").now()', "GREEN", "GREEN", "GREEN"),
    ('eval("__import__(\'datetime\').datetime.now()")', "GREEN", "GREEN", "GREEN"),
    ('def _f(x): return getattr(x, "now")()', "GREEN", "GREEN", "GREEN"),
    ('def _f(table): return table[0]()', "GREEN", "GREEN", "GREEN"),
]
# 每一行真正写进 probe.py 的源码（第 4 行是「只有 docstring」那一档）
PROBES = [
    "_f = open\n_f('x')\n",
    "def reopen():\n    return 1\n\n\nreopen()\n",
    "def open_ended():\n    return 1\n\n\nopen_ended()\n",
    '"""不要用 datetime.now()，也不要 open("""\n',
    "open('x')\n",
    "import builtins\n\nbuiltins.open('x')\n",
    "import datetime as dt\n\ndt.datetime.now()\n",
    '__import__("datetime").datetime.now()\n',
    '__import__("os").listdir(".")\n',
    '__import__("builtins").open("x")\n',
    'getattr(__import__("datetime"), "datetime").now()\n',
    'eval("__import__(\'datetime\').datetime.now()")\n',
    'def _f(x):\n    return getattr(x, "now")()\n',
    'def _f(table):\n    return table[0]()\n',
]
assert len(PROBES) == len(TABLE_SRC) == 14

# 硬规矩 #53 的干净对照行：三列都已知 GREEN
CONTROL_SRC = "x = 1\n"

GUARDS = (("G1", pur.test_domain_imports_stay_within_the_allow_list),
          ("G2", pur.test_domain_has_no_clock_or_file_access),
          ("G3", pur.test_domain_has_no_filesystem_access))


def run_three():
    out = []
    for tag, fn in GUARDS:
        try:
            fn()
            out.append("GREEN")
        except BaseException as e:                       # noqa: BLE001
            out.append("RED(%s: %s)" % (type(e).__name__, str(e).splitlines()[0][:60]))
    return out


def color3(res):
    return tuple("GREEN" if r == "GREEN" else "RED" for r in res)


def build_tree(root: pathlib.Path, n_py: int):
    dom = root / "app" / "domain"
    dom.mkdir(parents=True, exist_ok=True)
    (dom / "__init__.py").write_text("", encoding="utf-8")
    for i in range(n_py - 2):                            # __init__ + probe = 2
        (dom / ("filler%d.py" % i)).write_text("", encoding="utf-8")
    return dom


REAL_DOMAIN, REAL_BACKEND = pur.DOMAIN, pur.BACKEND

# ------------------------------------------------------------------ phase A
print("=== phase A：字面配方（只重定向 DOMAIN；树里只有 probe.py 这 1 个 .py）===")
tmpA = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr5_A_"))
domA = tmpA / "app" / "domain"
domA.mkdir(parents=True)
pur.DOMAIN = domA
# BACKEND 故意**不**改（这就是字面配方）
rows_A = []
for i, src in enumerate([CONTROL_SRC] + PROBES):
    (domA / "probe.py").write_text(src, encoding="utf-8")
    rows_A.append((i, color3(run_three())))
print("  树里的 .py 数 =", len(list(domA.rglob("*.py"))), " BACKEND =", pur.BACKEND)
for i, c in rows_A:
    print("   row %2d (%s) -> %s" % (i, "干净对照" if i == 0 else "第 %d 行" % i, c))
print("  全 RED 的行数 = %d / %d" % (sum(1 for _i, c in rows_A if c == ("RED",) * 3),
                                   len(rows_A)))
# 打出 phase A 的具体异常，证明是哪两条守卫机制在响
(domA / "probe.py").write_text(CONTROL_SRC, encoding="utf-8")
for tag, fn in GUARDS:
    try:
        fn()
        print("   %s -> GREEN" % tag)
    except BaseException as e:                           # noqa: BLE001
        print("   %s -> %s: %s" % (tag, type(e).__name__, str(e).splitlines()[0][:150]))
pur.DOMAIN, pur.BACKEND = REAL_DOMAIN, REAL_BACKEND
shutil.rmtree(tmpA, ignore_errors=True)

# ------------------------------------------------------------------ phase B
print()
print("=== phase B：补正配方（DOMAIN 与 BACKEND 都重定向；树里 5 个 .py）===")
tmpB = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr5_B_"))
domB = build_tree(tmpB, 5)
pur.DOMAIN = domB
pur.BACKEND = tmpB
print("  树里的 .py 数 =", len(list(domB.rglob("*.py"))), " BACKEND =", pur.BACKEND)
rows_B = []
(domB / "probe.py").write_text(CONTROL_SRC, encoding="utf-8")
ctl = color3(run_three())
print("   干净对照行 -> %s   （硬规矩 #53；预期三列全 GREEN）" % (ctl,))
for i, src in enumerate(PROBES):
    (domB / "probe.py").write_text(src, encoding="utf-8")
    got = color3(run_three())
    want = TABLE_SRC[i][1:]
    rows_B.append((i + 1, got, want, got == want))
    print("   row %2d  got=%s  want=%s  %s"
          % (i + 1, got, want, "OK" if got == want else "<<< MISMATCH"))
bad = [r for r in rows_B if not r[3]]
print("  42 格里不符的 = %d" % (len(bad) * 3 if bad else 0))
print("  14 行里不符的 = %d" % len(bad))

# FORBIDDEN_IO 命中数（源码 :573-574 那句「0 vs 2」）
print()
print("=== FORBIDDEN_IO 子串命中数（源码 :573-574）===")
row9 = PROBES[8]
ctrl = "import os\n\nos.listdir('.')\n"
for label, s in (('__import__("os").listdir(".")', row9), ("对照组 import os / os.listdir", ctrl)):
    hits = [t for t in pur.FORBIDDEN_IO if t in s]
    print("   %-34s 命中 %d 个: %s" % (label, len(hits), hits))

pur.DOMAIN, pur.BACKEND = REAL_DOMAIN, REAL_BACKEND
shutil.rmtree(tmpB, ignore_errors=True)
print()
print("两个临时树已删:", not tmpA.exists(), not tmpB.exists())
