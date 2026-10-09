"""Task 6 的不变量取证（运行时口径，硬规矩 #89）。

一次性打印：扫描面、表数、``_MODELS_PUBLIC_BASELINE``、端点数、三个既有指纹、
``app/domain/`` 的 .py 数、``alerts.py`` 的 ``__all__`` 长度与字段数、
``alert_rules.yaml`` 的字节/行/CRLF/指纹。
"""
import hashlib
import importlib
import os
import pathlib
import sys

BACKEND = pathlib.Path(
    r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend"
)
sys.path.insert(0, str(BACKEND))

# ⚠️ **必须在 import app.* 之前设**：``app/config.py`` 的 ``DEFAULT_DB_URL`` 实测指向
# ``backend/pe.db``，那是禁区（不得存在）。本探针要 ``create_app()`` 数端点，
# 万一哪个模块在 import 期就建 engine，就会在禁区里落一个文件。
_PROBE_DB = pathlib.Path(os.environ["TEMP"]) / "t6_probe_invariants.db"
os.environ["PE_DB_URL"] = f"sqlite:///{_PROBE_DB.as_posix()}"
print(f"PE_DB_URL = {os.environ['PE_DB_URL']}")

import dataclasses  # noqa: E402

from app.domain import alerts  # noqa: E402
from app.db import models as models_pkg  # noqa: E402
from app.refdata import DATA_DIR  # noqa: E402
from app import refdata_alerts  # noqa: E402

print("=" * 72)
# --- 1. 架构守卫的扫描面 ---------------------------------------------------
SCANNED = ("pipeline", "db", "domain", "api")
total = 0
for name in SCANNED:
    n = len(list((BACKEND / "app" / name).rglob("*.py")))
    total += n
    print(f"扫描面 {name:9s} = {n}")
print(f"扫描面 合计      = {total}")
domain_py = sorted((BACKEND / "app" / "domain").rglob("*.py"))
print(f"app/domain/ 的 .py = {len(domain_py)}")
print("   顶层:", sorted(p.name for p in domain_py if p.parent.name == "domain"))

print("=" * 72)
# --- 2. 表数 ---------------------------------------------------------------
from sqlalchemy import Table  # noqa: E402
tables = [t for t in models_pkg.Base.metadata.sorted_tables]
print(f"表数 = {len(tables)}")
print("   ", sorted(t.name for t in tables))
print(f"_MODELS_PUBLIC_BASELINE 相关：models.__all__ 长度 = {len(models_pkg.__all__)}")

print("=" * 72)
# --- 3. 端点数 -------------------------------------------------------------
from app.main import create_app  # noqa: E402
app = create_app()
routes = [r for r in app.routes if hasattr(r, "methods") and r.methods]
api_routes = [r for r in routes if str(getattr(r, "path", "")).startswith("/api")]
print(f"路由总数（有 methods 的）= {len(routes)}；其中 /api 前缀 = {len(api_routes)}")

print("=" * 72)
# --- 4. 三个既有指纹 + 新指纹 ----------------------------------------------
def fp(p: pathlib.Path) -> str:
    return hashlib.sha256(
        p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()

EXPECTED = {
    "national_standard_2014.csv": "D2C8E539E2FA0029",
    "exercises.yaml": "5394B37F01DAC9AC",
    "exercise_equivalence.yaml": "822CB86A5E998301",
}
for name, pinned in EXPECTED.items():
    got = fp(DATA_DIR / name)
    print(f"{name:28s} {got}  {'OK 逐字不变' if got == pinned else '*** 变了 ***'}")

ar = DATA_DIR / refdata_alerts.ALERT_RULES_FILENAME
raw = ar.read_bytes()
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
print(f"{ar.name:28s} {fp(ar)}  bytes={len(raw)} LF={lf} CRLF={crlf}")

print("=" * 72)
# --- 5. alerts.py 的公开面与字段（运行时口径）------------------------------
print(f"alerts.__all__ 长度 = {len(alerts.__all__)}")
print("   ", list(alerts.__all__))
for cls in (alerts.AlertRule, alerts.AlertRules, alerts.StudentSignals,
            alerts.ClassSignals, alerts.StudentHit, alerts.ClassHit):
    names = [f.name for f in dataclasses.fields(cls)]
    print(f"{cls.__name__:16s} 字段 {len(names)}: {names}")
for enum in (alerts.AlertLevel, alerts.RuleId, alerts.AlertScope):
    print(f"{enum.__name__:16s} 成员 {len(list(enum))}: "
          f"{[(m.name, m.value) for m in enum]}")
loaded = refdata_alerts.load_alert_rules()
print(f"load_alert_rules(): version={loaded.version!r} 规则数={len(loaded.rules)}")
for rid, rule in loaded.rules.items():
    print(f"   {rid.value:24s} level={rule.level.value:6s} "
          f"scope={rule.scope.value:7s} params={dict(rule.params)}")

print("=" * 72)
# --- 6. refdata_yaml / refdata_alerts 的公开面 -----------------------------
import ast  # noqa: E402
from app import refdata_yaml  # noqa: E402


def public_defs(module) -> list[str]:
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            if not node.name.startswith("_"):
                out.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    out.append(target.id)
    return out


print(f"refdata_yaml.__all__       = {refdata_yaml.__all__}")
print(f"refdata_yaml 公有顶层定义  = {public_defs(refdata_yaml)}")
print(f"refdata_alerts 公有顶层定义 = {public_defs(refdata_alerts)}")
print(f"refdata_alerts.__all__      = {getattr(refdata_alerts, '__all__', None)}")

import app.refdata_prescription as rp  # noqa: E402
print(f"refdata_prescription 公有顶层定义 = {public_defs(rp)}")
print(f"rp._line_index is refdata_yaml.line_index = "
      f"{rp._line_index is refdata_yaml.line_index}")

print("=" * 72)
# --- 7. 禁区 ---------------------------------------------------------------
print(f"backend/pe.db 存在? {(BACKEND / 'pe.db').exists()}")
print(f"探针库 {_PROBE_DB.name} 存在? {_PROBE_DB.exists()}")
seed = BACKEND / "data" / "seed"
print(f"backend/data/seed 存在? {seed.exists()}；"
      f"文件数 = {len(list(seed.rglob('*'))) if seed.exists() else 'n/a'}")
print(f"backend/data 下条目 = {sorted(p.name for p in DATA_DIR.iterdir())}")
for mod in ("app.refdata_alerts", "app.refdata_yaml"):
    m = importlib.import_module(mod)
    print(f"{mod} 在 SCANNED_DIRS 里? "
          f"{any(part in SCANNED for part in pathlib.Path(m.__file__).relative_to(BACKEND / 'app').parts[:-1])}")
