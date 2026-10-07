"""P10 — Edit A / Edit O 里我要写进源码的每一句判定，逐条亲跑。"""
import importlib.util
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, BACKEND / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pur = load("tests/architecture/test_domain_purity.py", "pur_mod")
lay = load("tests/architecture/test_layering.py", "lay_mod")

print("=== Edit A（purity:146 补主语）要用到的判定 ===")
print("  purity   _is_allowed('app.domain.seed')    = %s" % pur._is_allowed("app.domain.seed"))
print("  layering _is_forbidden('app.domain.seed')  = %s" % lay._is_forbidden("app.domain.seed"))
print("  -> purity 侧是「假绿」（本该 offender 却放行）；layering 侧同一个串是**正确的 GREEN**")
print("     （layering 只封 app.seed 前缀，'app.domain.seed' 不以 'app.seed' 开头）")
print("  layering FORBIDDEN_PREFIX = %r" % lay.FORBIDDEN_PREFIX)
print("  'app.domain.seed'.startswith('app.seed' + '.') = %s"
      % "app.domain.seed".startswith("app.seed" + "."))

print()
print("=== Edit O（layering:145 配方对齐）要用到的判定 ===")
REAL_APP, REAL_BACKEND = lay.APP, lay.BACKEND
tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr5_O_"))
for d in ("pipeline", "db", "domain"):
    (tmp / "app" / d).mkdir(parents=True)
# 只重定向 APP、不重定向 BACKEND
lay.APP = tmp / "app"
for d in ("pipeline", "db", "domain"):
    for i in range(3):
        (tmp / "app" / d / ("m%d.py" % i)).write_text("", encoding="utf-8")
(tmp / "app" / "pipeline" / "probe.py").write_text("from ..seed import generate\n", encoding="utf-8")
n_py = len(list((tmp / "app").rglob("*.py")))
print("  合成树里 pipeline/db/domain 合计 .py 数 = %d（>= 8，故空转守卫这一关先放过）" % n_py)
print("  只改 APP、不改 BACKEND -> BACKEND 仍是 %s" % lay.BACKEND)
try:
    lay.test_production_layers_never_import_app_seed()
    print("  结果：GREEN（没抛）")
except BaseException as e:                                    # noqa: BLE001
    print("  结果：%s: %s" % (type(e).__name__, str(e).splitlines()[0][:130]))

# 再把 BACKEND 也改过来，但把树搬空到 < 8 个 .py
lay.BACKEND = tmp
for p in list((tmp / "app").rglob("*.py"))[1:]:
    p.unlink()
print()
print("  两个都重定向、但树里只剩 %d 个 .py：" % len(list((tmp / "app").rglob("*.py"))))
try:
    lay.test_production_layers_never_import_app_seed()
    print("  结果：GREEN（没抛）")
except BaseException as e:                                    # noqa: BLE001
    print("  结果：%s: %s" % (type(e).__name__, str(e).splitlines()[0][:130]))

# 补足到 8 个 .py、探针是 offender -> 必须 RED（证明补正后的配方能正常显色）
for d in ("pipeline", "db", "domain"):
    for i in range(3):
        f = tmp / "app" / d / ("m%d.py" % i)
        if not f.exists():
            f.write_text("", encoding="utf-8")
(tmp / "app" / "pipeline" / "probe.py").write_text("from ..seed import generate\n", encoding="utf-8")
(tmp / "app" / "db" / "probe.py").write_text("from ...seed import generate\n", encoding="utf-8")
print()
print("  两个都重定向、树里 %d 个 .py、探针是 offender：" % len(list((tmp / "app").rglob("*.py"))))
try:
    lay.test_production_layers_never_import_app_seed()
    print("  结果：GREEN（没抛）")
except BaseException as e:                                    # noqa: BLE001
    print("  结果：%s" % type(e).__name__)
    for l in str(e).splitlines()[:6]:
        print("      %s" % l[:130])
# 干净对照（硬规矩 #53）
(tmp / "app" / "pipeline" / "probe.py").write_text("x = 1\n", encoding="utf-8")
(tmp / "app" / "db" / "probe.py").write_text("x = 1\n", encoding="utf-8")
try:
    lay.test_production_layers_never_import_app_seed()
    print("  干净对照行（探针只写 x = 1）：GREEN")
except BaseException as e:                                    # noqa: BLE001
    print("  干净对照行：RED %s: %s" % (type(e).__name__, str(e).splitlines()[0][:100]))

lay.APP, lay.BACKEND = REAL_APP, REAL_BACKEND
shutil.rmtree(tmp, ignore_errors=True)
print()
print("临时树已删:", not tmp.exists())
