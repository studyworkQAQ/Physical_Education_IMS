# -*- coding: utf-8 -*-
"""Probe P20: layering:107-110 的主语（举例文件 app/pipeline/x.py，实跑却是 import app.domain.x）。"""
import pathlib, shutil, sys, tempfile
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_p20_"))
SB = TMP / "backend"
for d in ("app/pipeline", "app/domain", "app/db/models"):
    (SB / d).mkdir(parents=True)
for d in ("app", "app/pipeline", "app/domain", "app/db", "app/db/models"):
    (SB / d / "__init__.py").write_text("", encoding="utf-8")
sys.path.insert(0, str(SB))
for rel, stmt in (("app/pipeline/x.py", "from ...seed import generate\n"),
                  ("app/domain/x.py", "from ...seed import generate\n"),
                  ("app/db/models/x.py", "from .....seed import generate\n")):
    (SB / rel).write_text(stmt + "VALUE = 1\n", encoding="utf-8")
    mod = rel.replace("/", ".")[:-3]
    for m in list(sys.modules):
        if m == "app" or m.startswith("app."):
            del sys.modules[m]
    try:
        __import__(mod)
        print("  %-22s %-34s -> 竟然成功" % (rel, stmt.strip()))
    except Exception as e:
        print("  %-22s %-34s -> %s: %s" % (rel, stmt.strip(), type(e).__name__, e))
sys.path.remove(str(SB))
shutil.rmtree(TMP, ignore_errors=True)
print("临时树已删除:", TMP.exists())
