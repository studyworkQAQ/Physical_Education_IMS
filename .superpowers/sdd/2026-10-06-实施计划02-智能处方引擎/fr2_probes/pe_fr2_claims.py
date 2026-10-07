# -*- coding: utf-8 -*-
"""pe_fr2_claims.py — 逐条核实我写进两个 docstring 的『f(x) == y』式断言（硬规矩 #52）。"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
from importlib.util import resolve_name

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMIT = "6a2938f"
FILES = {"purity": "backend/tests/architecture/test_domain_purity.py",
         "layering": "backend/tests/architecture/test_layering.py"}


def load(key, src, tmp, tag):
    p = tmp / ("g_%s_%s.py" % (key, tag))
    p.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[p.stem] = mod
    spec.loader.exec_module(mod)
    return mod


tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr2_claims_"))
base = {}
work = {}
for key, rel in FILES.items():
    bsrc = subprocess.run(["git", "show", "%s:%s" % (COMMIT, rel)], cwd=str(REPO),
                          capture_output=True).stdout.decode("utf-8")
    base[key] = load(key, bsrc, tmp, "base")
    work[key] = load(key, (REPO / rel).read_text(encoding="utf-8"), tmp, "work")

print("=== ① 切片断言（写进 purity:164 与 layering 的那两句） ===")
print('   ("app", "domain")[: 2 - 3]            =', ("app", "domain")[: 2 - 3])
print('   ("app", "db", "models")[: 3 - 4]      =', ("app", "db", "models")[: 3 - 4])

print()
print("=== ② Ruling 35 的两例：改前折算 vs 改后折算 vs resolve_name ===")
SHAPES = [
    ("domain", 4, ("app", "domain"), "", 'app/domain/x.py  from ....domain import tables'),
    ("seed.generate", 5, ("app", "db", "models"), "", 'app/db/models/x.py  from .....seed import generate'),
    ("seed", 4, ("app", "pipeline"), "", 'app/pipeline/x.py  from ....seed import generate'),
]
for module, level, pkg, name, label in SHAPES:
    dots = "." * level
    try:
        rn = repr(resolve_name(dots + module, ".".join(pkg)))
    except Exception as exc:
        rn = "%s" % type(exc).__name__
    b = base["purity"]._absolute(module, level, pkg)
    w = work["purity"]._absolute(module, level, pkg, name)
    bl = base["layering"]._absolute(module, level, pkg)
    wl = work["layering"]._absolute(module, level, pkg, name)
    print("   %s" % label)
    print("      resolve_name(%r, %r) = %s" % (dots + module, ".".join(pkg), rn))
    print("      _absolute 改前=%r  改后=%r   （两份守卫一致=%s）" % (b, w, (b, w) == (bl, wl)))

print()
print("=== ③ Ruling 36/37 的 resolve_name 实跑值（docstring 里逐字引用的那几条） ===")
for name, pkg in [("..seed.generate", "app.domain"),
                  ("..seed.generate", "app.domain.ind"),
                  ("...seed.generate", "app.db.models"),
                  ("...seed.generate", "app.db.models.organisation"),
                  ("..seed", "app.pipeline"),
                  ("..seed", "app.db.models")]:
    print("   resolve_name(%-18r, %-28r) -> %r" % (name, pkg, resolve_name(name, pkg)))

print()
print("=== ④ 真仓那 12 条相对导入：改前/改后折算，必须全部不以 app.seed 开头 ===")
import ast
for key in ("purity", "layering"):
    for d in (base, work):
        d[key].BACKEND = REPO / "backend"
        d[key].APP = REPO / "backend" / "app"
bad = 0
n_rows = 0


def scan(mod, only_rel=False):
    """返回 [(file, lineno, folded)]；only_rel=True 时只看 level>0 的相对导入。"""
    out = []
    for py in sorted((REPO / "backend" / "app").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        pkg = mod._package_of(py)
        for lineno, m in mod._imported_modules(tree, pkg):
            if only_rel:
                node = [n for n in ast.walk(tree)
                        if isinstance(n, ast.ImportFrom) and n.lineno == lineno and n.level]
                if not node:
                    continue
            out.append((py.relative_to(REPO / "backend").as_posix(), lineno, m))
    return out


for tag, mod in (("改前", base["layering"]), ("改后", work["layering"])):
    rows = scan(mod, only_rel=True)
    offenders = [r for r in rows if r[2] is None or mod._is_forbidden(r[2])]
    print("   %s：真仓相对导入折算出 %d 条，offender = %d" % (tag, len(rows), len(offenders)))
    if tag == "改后":
        for r in rows:
            print("        %-34s :%-4d -> %r" % r)
        bad = len(offenders)
        n_rows = len(rows)
allrows = scan(work["layering"])
print("   改后 layering 侧对**全部** import 共 yield %d 条，offender = %d"
      % (len(allrows), sum(1 for r in allrows if r[2] is None
                           or work["layering"]._is_forbidden(r[2]))))
rel = [(py.as_posix(), n.lineno, n.level, n.module, [a.name for a in n.names])
       for py in sorted((REPO / "backend" / "app").rglob("*.py"))
       for n in ast.walk(ast.parse(py.read_text(encoding="utf-8")))
       if isinstance(n, ast.ImportFrom) and n.level]
print("   真仓 ImportFrom(level>0) **节点**数 = %d（其中 module 为空的 = %d）"
      % (len(rel), sum(1 for r in rel if r[3] is None)))
for r in rel:
    if r[3] is None:
        print("      module 为空的那条:", r)
