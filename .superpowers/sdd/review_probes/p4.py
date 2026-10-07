# -*- coding: utf-8 -*-
"""Probe P4: 把基线 e26347f 的 test_domain_purity.py 落盘，核 purity:369-389 的每条陈述。"""
import subprocess, pathlib, tempfile, sys, importlib.util, shutil
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
blob = subprocess.run(["git", "-C", str(ROOT), "show",
                       "e26347f:backend/tests/architecture/test_domain_purity.py"],
                      capture_output=True).stdout
print("blob bytes =", len(blob), " CRLF =", blob.count(b"\r\n"), " bare LF =", blob.count(b"\n") - blob.count(b"\r\n"))
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_base_p4_"))
base = TMP / "baseline_purity.py"
base.write_bytes(blob)
L = blob.decode("utf-8").splitlines()
print("\n=== 基线文件的相关行（purity:370 说 FORBIDDEN 在第 13 行；:375-376 说 :38/:40/:41；:547 说 :50）===")
for i in (13, 14, 38, 40, 41, 50):
    print("  %4d| %s" % (i, L[i - 1]))

spec = importlib.util.spec_from_file_location("baseline_purity", base)
BP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BP)
print("\n基线 FORBIDDEN =", sorted(BP.FORBIDDEN), " 共 %d 项" % len(BP.FORBIDDEN))
print("'os' in FORBIDDEN ->", "os" in BP.FORBIDDEN)
print("基线的守卫函数:", [n for n in dir(BP) if n.startswith("test_")])

# 重定向 DOMAIN 到合成树
DOM = TMP / "backend" / "app" / "domain"
DOM.mkdir(parents=True)
for i in range(5):
    (DOM / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
PROBE = DOM / "probe.py"
BP.DOMAIN = DOM
print("基线 _domain_files 用 DOMAIN 全局? ", "DOMAIN" in BP.__dict__)

ROWS = [
    ("from os import listdir", "from os import listdir\n"),
    ("import numpy.random", "import numpy.random\n"),
    ("import app.refdata", "import app.refdata\n"),
    ("对照: import sqlalchemy", "import sqlalchemy\n"),
    ("对照: import os", "import os\n"),
    ("对照: os.listdir('x')", "import os\nos.listdir('x')\n"),
]
GUARDS = [(n, getattr(BP, n)) for n in sorted(dir(BP)) if n.startswith("test_")]
print("\n%-28s %s" % ("基线守卫下的探针", "  ".join(g[0][:22].ljust(24) for g in GUARDS)))
for label, src in ROWS:
    PROBE.write_text(src, encoding="utf-8")
    res = []
    for _n, fn in GUARDS:
        try:
            fn()
            res.append("GREEN")
        except AssertionError:
            res.append("RED")
        except Exception as e:
            res.append("ERR:" + type(e).__name__)
    print("%-28s %s" % (label[:28], "  ".join(r.ljust(24) for r in res)))

print("\n=== 基线 domain 的 import 全貌（purity:432-439 的表）===")
BASEDOM = TMP / "basedom"
BASEDOM.mkdir()
files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "e26347f",
                        "--", "backend/app/domain"], capture_output=True, text=True,
                       encoding="utf-8").stdout.split()
import ast
for f in files:
    src = subprocess.run(["git", "-C", str(ROOT), "show", "e26347f:" + f],
                         capture_output=True).stdout.decode("utf-8")
    t = ast.parse(src)
    mods = sorted({a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names}
                  | {n.module for n in ast.walk(t) if isinstance(n, ast.ImportFrom) and n.module})
    print("  %-16s %s" % (pathlib.Path(f).name, mods))
shutil.rmtree(TMP, ignore_errors=True)
