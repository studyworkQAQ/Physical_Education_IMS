# -*- coding: utf-8 -*-
"""Probe P17: 按 purity:524-525 / layering:145-146 印的配方**逐字**搭合成树，
看能不能复现那张 14 行表（配方说「一棵只有 app/domain/ 的合成树 + 一个探针文件」）。"""
import importlib.util, pathlib, shutil, sys, tempfile
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
spec = importlib.util.spec_from_file_location("hp", ROOT / "backend/tests/architecture/test_domain_purity.py")
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
spec2 = importlib.util.spec_from_file_location("hl", ROOT / "backend/tests/architecture/test_layering.py")
L = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(L)

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_recipe_p17_"))

# ---- 配方 A：purity:524-525 的字面读法 —— 树里只有 app/domain/probe.py ----
SB = TMP / "A"
DOM = SB / "app" / "domain"
DOM.mkdir(parents=True)
P.BACKEND = SB
P.DOMAIN = DOM
rows = [("对照 VALUE = 1", "VALUE = 1\n"),
        ("open('x')", "open('x')\n"),
        ('__import__("os").listdir(".")', '__import__("os").listdir(".")\n')]
print("=== 配方 A（DOMAIN 下只有 1 个探针文件，逐字照 purity:524-525 做）===")
for label, src in rows:
    (DOM / "probe.py").write_text(src, encoding="utf-8")
    out = []
    for name, fn in (("G1", P.test_domain_imports_stay_within_the_allow_list),
                     ("G2", P.test_domain_has_no_clock_or_file_access),
                     ("G3", P.test_domain_has_no_filesystem_access)):
        try:
            fn(); out.append(name + " GREEN")
        except AssertionError as e:
            last = str(e).splitlines()[-1]
            out.append(name + " RED(" + ("空转守卫" if "只扫到" in str(e) else last[:40]) + ")")
    print("  %-30s %s" % (label[:30], " | ".join(out)))

# ---- 配方 A'：同一棵树补足 5 个干净填充文件 ----
for i in range(5):
    (DOM / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
print("\n=== 配方 A'（补 5 个干净 filler，让 len(scanned) >= 5 的空转守卫过关）===")
for label, src in rows:
    (DOM / "probe.py").write_text(src, encoding="utf-8")
    out = []
    for name, fn in (("G1", P.test_domain_imports_stay_within_the_allow_list),
                     ("G2", P.test_domain_has_no_clock_or_file_access),
                     ("G3", P.test_domain_has_no_filesystem_access)):
        try:
            fn(); out.append(name + " GREEN")
        except AssertionError as e:
            out.append(name + " RED(" + str(e).splitlines()[-1][:40] + ")")
    print("  %-30s %s" % (label[:30], " | ".join(out)))

# ---- 配方 B：layering:145-146 的字面读法 —— 形状与 backend/app 相同但只有探针 ----
SB2 = TMP / "B"
for d in ("app/pipeline", "app/db/models", "app/domain"):
    (SB2 / d).mkdir(parents=True)
L.BACKEND = SB2
L.APP = SB2 / "app"
print("\n=== 配方 B（layering：形状相同、每目录只放 1 个探针文件）===")
(SB2 / "app" / "pipeline" / "probe.py").write_text("from ..seed import generate\n", encoding="utf-8")
try:
    L.test_production_layers_never_import_app_seed()
    print("  GREEN")
except AssertionError as e:
    print("  RED ->", str(e).splitlines()[-1][:90])
    print("  是不是空转守卫（len(scanned) >= 8）？", "只扫到" in str(e))
for d in ("app/pipeline", "app/db", "app/db/models", "app/domain"):
    for i in range(4):
        (SB2 / d / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
try:
    L.test_production_layers_never_import_app_seed()
    print("  补足 filler 后：GREEN")
except AssertionError as e:
    print("  补足 filler 后：RED ->", str(e).splitlines()[-1][:90])

shutil.rmtree(TMP, ignore_errors=True)
print("\n临时树已删除:", TMP.exists())
