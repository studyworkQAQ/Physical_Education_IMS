"""pe_fr2_probe.py — Plan02 Task1 fix round 2 的合成树探针。

用法: python pe_fr2_probe.py <repo_root> <baseline|work>

三节输出：
  §A resolve_name 举例复核（Ruling 37）
  §B _absolute vs resolve_name 对拍矩阵 + _imported_modules 的 yield 条数（Ruling 35/36）
  §C 合成树端到端：两条守卫的 GREEN/RED，以及 purity 的 G1/G2/G3 三列探针表（Ruling 38）
"""
import ast
import importlib.util
import inspect
import pathlib
import shutil
import subprocess
import sys
import tempfile
from importlib.util import resolve_name

REPO = pathlib.Path(sys.argv[1]).resolve()
WHICH = sys.argv[2]
COMMIT = "6a2938f"
FILES = {
    "purity": "backend/tests/architecture/test_domain_purity.py",
    "layering": "backend/tests/architecture/test_layering.py",
}
TESTFN = {
    "purity": "test_domain_imports_stay_within_the_allow_list",
    "layering": "test_production_layers_never_import_app_seed",
}
G_FN = ["test_domain_imports_stay_within_the_allow_list",
        "test_domain_has_no_clock_or_file_access",
        "test_domain_has_no_filesystem_access"]
SLOTS = ["domain/probe.py", "domain/sub/probe.py", "pipeline/probe.py",
         "db/probe.py", "db/models/probe.py"]
BENIGN = "PASS = 1\n"


def guard_source(key):
    if WHICH == "work":
        return (REPO / FILES[key]).read_text(encoding="utf-8")
    out = subprocess.run(["git", "show", "%s:%s" % (COMMIT, FILES[key])],
                         cwd=str(REPO), capture_output=True)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    return out.stdout.decode("utf-8")


def load(key, tmp):
    p = tmp / ("guard_%s_%s.py" % (key, WHICH))
    p.write_text(guard_source(key), encoding="utf-8")
    name = "guard_%s_%s" % (key, WHICH)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def call_absolute(mod, module, level, package, name):
    """基线 _absolute 只有 3 个入参，改后有 4 个；按签名兼容调用。"""
    fn = mod._absolute
    n = len(inspect.signature(fn).parameters)
    return fn(module, level, package) if n == 3 else fn(module, level, package, name)


def build_tree(root):
    app = root / "backend" / "app"
    for rel in ("domain", "domain/sub", "pipeline", "db", "db/models"):
        d = app / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text(BENIGN, encoding="utf-8")
    for i in range(5):
        (app / "domain" / ("benign%d.py" % i)).write_text(BENIGN, encoding="utf-8")
    for i in range(2):
        for rel in ("pipeline", "db", "db/models"):
            (app / rel / ("benign%d.py" % i)).write_text(BENIGN, encoding="utf-8")
    for rel in SLOTS:
        (app / rel).write_text(BENIGN, encoding="utf-8")
    return app


def reset(app):
    for rel in SLOTS:
        (app / rel).write_text(BENIGN, encoding="utf-8")


def point(mod, key, root):
    if key == "purity":
        mod.DOMAIN = root / "backend" / "app" / "domain"
        mod.BACKEND = root / "backend"
    else:
        mod.BACKEND = root / "backend"
        mod.APP = root / "backend" / "app"


def run_guard(mod, key, root):
    point(mod, key, root)
    try:
        getattr(mod, TESTFN[key])()
        return "GREEN", ""
    except AssertionError as exc:
        return "RED", " | ".join(str(exc).splitlines())


def run_three(mod, root):
    """purity 的三条守卫分别跑，返回 G1/G2/G3 的颜色。"""
    point(mod, "purity", root)
    out = []
    for fn in G_FN:
        try:
            getattr(mod, fn)()
            out.append("GREEN")
        except AssertionError:
            out.append("RED")
    return out


def expected(module, level, package, name):
    tail = module if module else name
    try:
        return resolve_name("." * level + tail, package), None
    except Exception as exc:  # noqa: BLE001 —— 探针要的就是它抛什么
        return None, "%s: %s" % (type(exc).__name__, exc)


# ---------------------------------------------------------------- §A
def section_a():
    print("=== §A Ruling 37: docstring 里那两个 resolve_name 举例（亲跑） ===")
    rows = [
        ("..seed.generate", "app.domain.ind", "改前 purity:118 写的"),
        ("...seed.generate", "app.db.models.organisation", "改前 layering:84-85 写的"),
        ("..seed.generate", "app.domain", "改成包名之后"),
        ("...seed.generate", "app.db.models", "改成包名之后"),
        ("..seed", "app.db.models", "Ruling 41 第三行的正确答案"),
        ("....domain.tables", "app.domain", "Ruling 35 第二例"),
        (".....seed.generate", "app.db.models", "Ruling 35 第一例"),
    ]
    for name, pkg, note in rows:
        try:
            val = repr(resolve_name(name, pkg))
        except Exception as exc:
            val = "%s: %s" % (type(exc).__name__, exc)
        print("  resolve_name(%-20r, %-28r) = %-58s  # %s" % (name, pkg, val, note))


# ---------------------------------------------------------------- §B
MATRIX = [
    # (package, level, module, name, 说明)
    ("app.pipeline", 2, "", "seed", "Ruling 41 第 1 行"),
    ("app.db", 2, "", "seed", "Ruling 41 第 2 行"),
    ("app.db.models", 2, "", "seed", "Ruling 41 第 3 行（判定本来对、折算串错）"),
    ("app.domain", 2, "", "pipeline", "purity 侧 from .. import pipeline"),
    ("app.domain", 1, "", "tables", "level1 + 空 module"),
    ("app.db.models", 1, "_shared", "", "真仓 12 条的形状"),
    ("app.domain", 2, "seed", "", "from ..seed import …"),
    ("app.domain", 2, "seed.generate", "", "purity:118 举例的形状"),
    ("app.db.models", 3, "seed.generate", "", "layering:84 举例的形状"),
    ("app.db.models", 5, "seed.generate", "", "Ruling 35 第 1 例（负数切片）"),
    ("app.domain", 4, "domain.tables", "", "Ruling 35 第 2 例（负数切片）"),
    ("app.domain", 3, "seed", "", "深度 2 的越界档"),
    ("app.domain.sub", 2, "seed", "", "Minor 3：折到 app.domain.seed"),
    ("app.domain.sub", 3, "seed", "", "Minor 3：这一档才到 app.seed"),
    ("app.pipeline", 1, "clean", "", "同包 level1"),
]


def section_b(mods):
    print()
    print("=== §B Ruling 35/36: _absolute(%s) vs importlib.util.resolve_name 对拍 ===" % WHICH)
    diff = 0
    for pkg, level, module, name, note in MATRIX:
        pt = tuple(pkg.split("."))
        exp, err = expected(module, level, pkg, name)
        got = call_absolute(mods["layering"], module, level, pt, name)
        gotp = call_absolute(mods["purity"], module, level, pt, name)
        ok = (got == exp) and (gotp == exp)
        if not ok:
            diff += 1
        src = "from %s%s import %s" % ("." * level, module, name or "X")
        print("  %-2s %-46s @ %-14s _absolute=%-16r resolve_name=%-24s %s"
              % ("OK" if ok else "DIFF", src, pkg, got,
                 repr(exp) if err is None else err, note))
        assert got == gotp, "两个守卫的 _absolute 不一致: %r vs %r" % (got, gotp)
    print("  ---- 对拍 DIFF 格数 = %d / %d" % (diff, len(MATRIX)))

    print()
    print("  -- _imported_modules 的 yield 条数（from .. import seed, pipeline @ app/pipeline）--")
    src = "from .. import seed, pipeline\n"
    tree = ast.parse(src)
    lay = list(mods["layering"]._imported_modules(tree, ("app", "pipeline")))
    print("     layering 侧 yield %d 条: %s" % (len(lay), lay))
    pur = list(mods["purity"]._imported_modules(tree))
    folded = []
    for item in pur:
        lineno, module, level = item[0], item[1], item[2]
        name = item[3] if len(item) > 3 else ""
        folded.append((lineno, call_absolute(mods["purity"], module, level,
                                             ("app", "pipeline"), name)))
    print("     purity   侧 yield %d 条(原始) → 折算 %s" % (len(pur), folded))
    print("     resolve_name 正确答案: %r / %r"
          % (resolve_name("..seed", "app.pipeline"), resolve_name("..pipeline", "app.pipeline")))

    print()
    print("  -- Ruling 41 第三行的直接调用断言 --")
    v = call_absolute(mods["layering"], "", 2, ("app", "db", "models"), "seed")
    print("     _absolute('', 2, ('app','db','models'), 'seed') = %r   == 'app.db.seed'? %s"
          % (v, v == "app.db.seed"))


# ---------------------------------------------------------------- §C
CASES = [
    # (guard, slot, content, want_after_fix, 说明)
    ("layering", "db/models/probe.py", "from .....seed import generate\n", "RED",
     "Ruling 35 第 1 例 level5@深度3（改前必须 GREEN）"),
    ("purity", "domain/probe.py", "from ....domain import tables\n", "RED",
     "Ruling 35 第 2 例 level4@深度2（改前 GREEN，且命中白名单前缀=真绿）"),
    ("layering", "pipeline/probe.py", "from .. import seed\n", "RED", "Ruling 36 / Ruling 41 第 1 行"),
    ("layering", "db/probe.py", "from .. import seed\n", "RED", "Ruling 36 / Ruling 41 第 2 行"),
    ("layering", "db/models/probe.py", "from .. import seed\n", "GREEN",
     "Ruling 41 第 3 行：判定本来对，改后必须仍 GREEN"),
    ("layering", "pipeline/probe.py", "from .. import seed, pipeline\n", "RED",
     "Ruling 36：一个节点两个模块，app.seed 那条必须红"),
    ("purity", "domain/probe.py", "from .. import seed\n", "RED", "purity 侧同一形状"),
    ("purity", "domain/probe.py", "from ..seed import generate\n", "RED", "对照：module 非空"),
    ("purity", "domain/sub/probe.py", "from ..seed import generate\n", "GREEN",
     "Minor 3：深度 3 折到 app.domain.seed.generate → 命中白名单前缀"),
    ("purity", "domain/sub/probe.py", "from ...seed import generate\n", "RED",
     "Minor 3：深度 3 要 level 3 才到 app.seed"),
    ("purity", "domain/sub/probe.py", "from ..tables import X\n", "GREEN",
     "Ruling 28 的合法形状（子包 level2）"),
    ("layering", "db/models/probe.py", "from ._shared import JsonText\n", "GREEN",
     "真仓 12 条 level-1 的形状"),
    ("layering", "pipeline/probe.py", "def f():\n    from app.seed.fitness import COLUMN_BY_ITEM\n",
     "RED", "对照：函数体内绝对导入"),
    ("layering", "db/models/probe.py", BENIGN, "GREEN", "对照：良性内容"),
    ("purity", "domain/probe.py", "import numpy\nfrom .tables import X\n", "GREEN",
     "对照：purity 良性"),
]

G_PROBES = [
    # (probe.py 内容, 说明)
    ("_f = open\n_f('x')\n", "既有表第 1 行"),
    ("def reopen():\n    return 1\nreopen()\n", "既有表第 2 行"),
    ("def open_ended():\n    return 1\nopen_ended()\n", "既有表第 3 行"),
    ('"""不要用 datetime.now()，也不要 open("""\n', "既有表第 4 行：只有 docstring"),
    ("open('x')\n", "既有表第 5 行"),
    ("import builtins\nbuiltins.open('x')\n", "既有表第 6 行"),
    ("import datetime as dt\ndt.datetime.now()\n", "既有表第 7 行"),
    ('__import__("datetime").datetime.now()\n', "Ruling 38 新增"),
    ('__import__("os").listdir(".")\n', "Ruling 38 新增"),
    ('__import__("builtins").open("x")\n', "Ruling 38 新增"),
    ('getattr(__import__("datetime"), "datetime").now()\n', "Ruling 38 新增"),
    ('eval("__import__(\'datetime\').datetime.now()")\n', "Ruling 38 新增"),
    ('def _f(x):\n    return getattr(x, "now")()\n', "Ruling 38 新增"),
    ("def _f(table):\n    return table[0]()\n", "Ruling 38 新增"),
]


def section_c(mods, root):
    print()
    print("=== §C 合成树端到端（守卫取自 %s）===" % WHICH)
    app = root / "backend" / "app"
    hit = 0
    for guard, slot, content, want, note in CASES:
        reset(app)
        (app / slot).write_text(content, encoding="utf-8")
        color, detail = run_guard(mods[guard], guard, root)
        mark = "OK" if color == want else "!!"
        if color == want:
            hit += 1
        print("  %s [%-8s] %-24s %-46s want=%-5s got=%-5s  %s"
              % (mark, guard, "app/" + slot, content.replace("\n", " ⏎ ").strip(),
                 want, color, note))
        if color == "RED":
            print("       offender: %s" % detail[:190])
    reset(app)
    print("  ---- 符合『改后期望』%d/%d（改前跑这一段时，Ruling 35/36 那几行应当是 !!）----"
          % (hit, len(CASES)))

    print()
    print("=== §C2 purity 三条守卫的 G1/G2/G3 探针表（守卫取自 %s）===" % WHICH)
    print("  %-52s %-6s %-6s %-6s  %s" % ("probe.py 的内容", "G1", "G2", "G3", "说明"))
    for content, note in G_PROBES:
        reset(app)
        (app / "domain" / "probe.py").write_text(content, encoding="utf-8")
        g = run_three(mods["purity"], root)
        print("  %-52s %-6s %-6s %-6s  %s"
              % (content.replace("\n", " ⏎ ").strip()[:52], g[0], g[1], g[2], note))
    reset(app)


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def main():
    log = open(pathlib.Path(tempfile.gettempdir()) / ("pe_fr2_%s.log" % WHICH),
               "w", encoding="utf-8", newline="\n")
    sys.stdout = _Tee(sys.__stdout__, log)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr2_"))
    try:
        root = tmp / "tree"
        (root / "backend").mkdir(parents=True)
        build_tree(root)
        mods = {k: load(k, tmp) for k in FILES}
        print("守卫来源: %s（%s）" % (WHICH, COMMIT if WHICH == "baseline" else "工作树"))
        section_a()
        section_b(mods)
        section_c(mods, root)
        n = sum(1 for p in (root / "backend" / "app").rglob("*.py"))
        print()
        print("合成树 .py 数 = %d（purity 下界 5 / layering 下界 8 均已满足）" % n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.stdout.flush()
        log.close()


main()
