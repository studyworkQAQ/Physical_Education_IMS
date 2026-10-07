# -*- coding: utf-8 -*-
"""Probe P18: purity:524 的配方只说「把 DOMAIN 指到合成树」，没提 BACKEND。
照字面做会怎样？（这正是硬规矩 #53 / 控制者错误 #71 的形态。）"""
import importlib.util, pathlib, shutil, tempfile
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
spec = importlib.util.spec_from_file_location("hp", ROOT / "backend/tests/architecture/test_domain_purity.py")
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_p18_"))
DOM = TMP / "app" / "domain"
DOM.mkdir(parents=True)
for i in range(5):
    (DOM / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
(DOM / "probe.py").write_text('import os\nos.listdir(".")\n', encoding="utf-8")

P.DOMAIN = DOM                      # 只重定向 DOMAIN，BACKEND 留在真仓（照 purity:524 字面做）
print("BACKEND =", P.BACKEND)
print("DOMAIN  =", P.DOMAIN)
for name, fn in (("G1", P.test_domain_imports_stay_within_the_allow_list),
                 ("G2", P.test_domain_has_no_clock_or_file_access),
                 ("G3", P.test_domain_has_no_filesystem_access)):
    try:
        fn(); print("  %s GREEN" % name)
    except AssertionError as e:
        print("  %s RED(AssertionError) <- %s" % (name, str(e).splitlines()[-1][:70]))
    except Exception as e:
        print("  %s 抛 %s: %s" % (name, type(e).__name__, str(e)[:110]))

P.BACKEND = TMP                     # 补上 BACKEND 重定向之后
print("\n补上 P.BACKEND = 合成树根 之后：")
for name, fn in (("G1", P.test_domain_imports_stay_within_the_allow_list),
                 ("G2", P.test_domain_has_no_clock_or_file_access),
                 ("G3", P.test_domain_has_no_filesystem_access)):
    try:
        fn(); print("  %s GREEN" % name)
    except AssertionError as e:
        print("  %s RED(AssertionError) <- %s" % (name, str(e).splitlines()[-1][:70]))
    except Exception as e:
        print("  %s 抛 %s: %s" % (name, type(e).__name__, str(e)[:110]))
shutil.rmtree(TMP, ignore_errors=True)
