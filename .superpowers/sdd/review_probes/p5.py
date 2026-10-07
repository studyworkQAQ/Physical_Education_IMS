# -*- coding: utf-8 -*-
"""Probe P5: 合成树端到端。
(a) HEAD 两条守卫对相对导入探针的颜色（purity:417-424 / layering:138-146「改后全红」）
(b) 基线 ad1d190 两条守卫对同一批探针的颜色（「改前全绿」）
(c) 运行期真跑一次 import，核 purity:166-168 / layering:108-110 的 ImportError 陈述
硬规矩 #53：同时重定向 BACKEND 与 DOMAIN/APP，并带一行已知 GREEN 的对照。
"""
import subprocess, pathlib, tempfile, importlib.util, shutil, sys, os

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_synth_p5_"))


def load(src: str, name: str, path: pathlib.Path):
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def gitshow(rev, rel):
    return subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (rev, rel)],
                          capture_output=True).stdout.decode("utf-8")


# ---- 合成树：形状与 backend/app 相同 ----
SB = TMP / "backend"
for d in ("app/domain/sub", "app/pipeline", "app/db/models"):
    (SB / d).mkdir(parents=True)
(SB / "app" / "__init__.py").write_text("", encoding="utf-8")
(SB / "app" / "domain" / "__init__.py").write_text("", encoding="utf-8")
(SB / "app" / "db" / "__init__.py").write_text("", encoding="utf-8")
(SB / "app" / "pipeline" / "__init__.py").write_text("", encoding="utf-8")
(SB / "app" / "db" / "models" / "__init__.py").write_text("", encoding="utf-8")
# 干净填充（>=5，防空转守卫误红）
for i in range(5):
    (SB / "app" / "domain" / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
for i in range(5):
    (SB / "app" / "pipeline" / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
for i in range(5):
    (SB / "app" / "db" / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
for i in range(5):
    (SB / "app" / "db" / "models" / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")

HEAD_P = load(gitshow("6784d57", "backend/tests/architecture/test_domain_purity.py"), "hp", TMP / "hp.py")
HEAD_L = load(gitshow("6784d57", "backend/tests/architecture/test_layering.py"), "hl", TMP / "hl.py")
BASE_P = load(gitshow("ad1d190", "backend/tests/architecture/test_domain_purity.py"), "bp", TMP / "bp.py")
BASE_L = load(gitshow("ad1d190", "backend/tests/architecture/test_layering.py"), "bl", TMP / "bl.py")

for M in (HEAD_P, BASE_P):
    M.BACKEND = SB
    M.DOMAIN = SB / "app" / "domain"
for M in (HEAD_L, BASE_L):
    M.BACKEND = SB
    M.APP = SB / "app"


def run(fn):
    try:
        fn()
        return "GREEN"
    except AssertionError as e:
        return "RED  [" + str(e).splitlines()[-1][:60] + "]"
    except Exception as e:
        return "ERR:" + type(e).__name__ + " " + str(e)[:50]


def probe(relpath, src):
    (SB / relpath).write_text(src, encoding="utf-8")


P_ROWS = [
    ("对照 VALUE=1", "app/domain/probe.py", "VALUE = 1\n"),
    ("from .. import pipeline", "app/domain/probe.py", "from .. import pipeline\n"),
    ("from ..seed import generate  (扁平, 包深2)", "app/domain/probe.py", "from ..seed import generate\n"),
    ("from ...seed import generate (扁平, 越界)", "app/domain/probe.py", "from ...seed import generate\n"),
    ("sub: from ..tables import X (包深3)", "app/domain/sub/probe.py", "from ..tables import X\n"),
    ("sub: from ..seed import generate (包深3)", "app/domain/sub/probe.py", "from ..seed import generate\n"),
    ("sub: from ...seed import generate (包深3)", "app/domain/sub/probe.py", "from ...seed import generate\n"),
]
print("=== (a/b) purity 侧：app/domain 合成树探针 ===")
print("%-44s %-30s %-30s" % ("探针", "HEAD 6784d57", "BASE ad1d190"))
for label, rel, src in P_ROWS:
    probe(rel, src)
    a = run(HEAD_P.test_domain_imports_stay_within_the_allow_list)
    b = run(BASE_P.test_domain_has_no_forbidden_imports) if hasattr(BASE_P, "test_domain_has_no_forbidden_imports") else run([f for n, f in vars(BASE_P).items() if n.startswith("test_") and "import" in n][0])
    print("%-44s %-30s %-30s" % (label[:44], a[:30], b[:30]))
    # 清掉上一行残留
    for stale in ("app/domain/probe.py", "app/domain/sub/probe.py"):
        p = SB / stale
        if p.exists():
            p.unlink()

L_ROWS = [
    ("对照 VALUE=1", "app/pipeline/probe.py", "VALUE = 1\n"),
    ("pipeline: from ..seed import generate (level2)", "app/pipeline/probe.py", "from ..seed import generate\n"),
    ("pipeline: from .. import seed (level2, module空)", "app/pipeline/probe.py", "from .. import seed\n"),
    ("db: from .. import seed (level2, 包深2)", "app/db/probe.py", "from .. import seed\n"),
    ("db/models: from ...seed import generate (level3)", "app/db/models/probe.py", "from ...seed import generate\n"),
    ("db/models: from .. import seed (level2, 包深3)", "app/db/models/probe.py", "from .. import seed\n"),
    ("db/models: from .....seed import generate (level5)", "app/db/models/probe.py", "from .....seed import generate\n"),
    ("db/models: from ._shared import X (level1, 合法)", "app/db/models/probe.py", "from ._shared import X\n"),
    ("函数体内 from app.seed.fitness import Y", "app/pipeline/probe.py", "def f():\n    from app.seed.fitness import Y\n    return Y\n"),
]
print("\n=== (a/b) layering 侧：app/pipeline|db 合成树探针 ===")
print("%-48s %-30s %-30s" % ("探针", "HEAD 6784d57", "BASE ad1d190"))
for label, rel, src in L_ROWS:
    probe(rel, src)
    a = run(HEAD_L.test_production_layers_never_import_app_seed)
    b = run(BASE_L.test_production_layers_never_import_app_seed)
    print("%-48s %-30s %-30s" % (label[:48], a[:30], b[:30]))
    for stale in ("app/pipeline/probe.py", "app/db/probe.py", "app/db/models/probe.py"):
        p = SB / stale
        if p.exists():
            p.unlink()

print("\n=== (c) 运行期真跑：越界相对导入抛什么 ===")
(SB / "app" / "domain" / "x.py").write_text("from ...seed import generate\nVALUE = 1\n", encoding="utf-8")
sys.path.insert(0, str(SB))
for mod in list(sys.modules):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]
try:
    __import__("app.domain.x")
    print("  import app.domain.x -> 竟然成功（与 docstring 相反！）")
except Exception as e:
    print("  import app.domain.x -> %s: %s" % (type(e).__name__, e))
sys.path.remove(str(SB))
shutil.rmtree(TMP, ignore_errors=True)
print("\n临时树已删除:", TMP.exists())
