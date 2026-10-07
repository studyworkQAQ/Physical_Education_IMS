# -*- coding: utf-8 -*-
"""Probe P1: 纯 Python 层的 docstring 举例复核（硬规矩 #52/#57）。"""
import importlib.util, sys, pathlib, ast
sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture")
import test_domain_purity as P
import test_layering as L

rn = importlib.util.resolve_name
out = []
def w(*a):
    print(*a)

w("=== A. resolve_name 举例（purity:136-137 / layering:87-88）===")
for name, pkg in [
    ("..seed.generate", "app.domain"),
    ("..seed.generate", "app.domain.ind"),
    ("...seed.generate", "app.db.models"),
    ("...seed.generate", "app.db.models.organisation"),
    ("..seed", "app.pipeline"),
    ("..seed.generate", "app.domain.sub"),
]:
    try:
        r = repr(rn(name, pkg))
    except ImportError as e:
        r = "ImportError: " + str(e)
    w("  resolve_name(%-18r, %-28r) = %s" % (name, pkg, r))

w("\n=== B. purity:144-145  _absolute('seed',2,('app','domain','ind')) 与 _is_allowed ===")
v = P._absolute("seed", 2, ("app", "domain", "ind"))
w("  purity._absolute('seed', 2, ('app','domain','ind')) = %r" % (v,))
w("  purity._is_allowed(%r) = %s" % (v, P._is_allowed(v)))

w("\n=== C. 负数切片（purity:171 / layering:113）===")
w("  ('app','domain')[: 2-3]        = %r   (docstring 说 ('app',))" % (("app","domain")[:2-3],))
w("  ('app','db','models')[: 3-4]   = %r   (docstring 说 ('app','db'))" % (("app","db","models")[:3-4],))

w("\n=== D. 越界档在【去掉守卫】后的折算 + 判定支 ===")
def _absolute_noguard(module, level, package, name=""):
    if level == 0:
        return module
    anchor = package[: len(package) - (level - 1)]
    if not anchor:
        return None
    tail = module or name
    return ".".join(anchor + ((tail,) if tail else ()))

d = _absolute_noguard("domain", 4, ("app", "domain"), "tables")
w("  purity 形状 from ....domain import tables @app/domain/x.py:")
w("    noguard folded = %r  (docstring 说 'app.domain')" % (d,))
w("    'app.domain' == ALLOWED_PACKAGE            -> %s" % (d == P.ALLOWED_PACKAGE,))
w("    'app.domain'.startswith(ALLOWED_PACKAGE+'.') -> %s" % (d.startswith(P.ALLOWED_PACKAGE + "."),))
w("    _is_allowed -> %s ; 带守卫的 _absolute -> %r" % (P._is_allowed(d), P._absolute("domain",4,("app","domain"),"tables")))
l = _absolute_noguard("seed", 5, ("app", "db", "models"), "generate")
w("  layering 形状 from .....seed import generate @app/db/models/x.py:")
w("    noguard folded = %r  (docstring 说 'app.db.seed')" % (l,))
w("    _is_forbidden -> %s ; 带守卫的 _absolute -> %r" % (L._is_forbidden(l), L._absolute("seed",5,("app","db","models"),"generate")))

w("\n=== E. resolve_name 对同一输入 ===")
for name, pkg in [("....domain", "app.domain"), (".....seed", "app.db.models"), ("...seed", "app.domain")]:
    try:
        r = repr(rn(name, pkg))
    except ImportError as e:
        r = "ImportError: " + str(e)
    w("  resolve_name(%-12r, %-16r) = %s" % (name, pkg, r))

w("\n=== F. layering:101-105  from .. import seed @app/db/models（修前/修后）===")
def _absolute_tailmodule(module, level, package, name=""):
    if level == 0:
        return module
    if level - 1 > len(package):
        return None
    anchor = package[: len(package) - (level - 1)]
    if not anchor:
        return None
    tail = module
    return ".".join(anchor + ((tail,) if tail else ()))
w("  修后  _absolute('',2,('app','db','models'),'seed') = %r" % (L._absolute("",2,("app","db","models"),"seed"),))
w("  修前  tail=module 版                                = %r  (docstring 说 'app.db')" % (_absolute_tailmodule("",2,("app","db","models"),"seed"),))
w("  _is_forbidden('app.db.seed') = %s -> layering GREEN ✓" % (L._is_forbidden("app.db.seed"),))
w("  _is_allowed ('app.db.seed') = %s -> purity  RED ✓" % (P._is_allowed("app.db.seed"),))
w("  修前那串 _is_forbidden('app.db') = %s -> 也是 GREEN（判定未变）" % (L._is_forbidden("app.db"),))
w("  修前那串 purity _is_allowed('app.db') = %s" % (P._is_allowed("app.db"),))

w("\n=== G. layering:204 / purity:216  tail=module 变异在 app/pipeline 上 ===")
w("  修后 _absolute('',2,('app','pipeline'),'seed') = %r" % (L._absolute("",2,("app","pipeline"),"seed"),))
w("  修前 tail=module                                = %r  (docstring 说 'app')" % (_absolute_tailmodule("",2,("app","pipeline"),"seed"),))

w("\n=== H. _package_of 举例 ===")
BK = P.BACKEND
for rel, want in [("app/domain/x.py", ("app","domain")),
                  ("app/domain/sub/x.py", ("app","domain","sub")),
                  ("app/db/models/x.py", ("app","db","models")),
                  ("app/db/models/__init__.py", ("app","db","models")),
                  ("app/pipeline/x.py", ("app","pipeline"))]:
    w("  purity ._package_of(%-28s) = %r  (docstring/期望 %r)  %s" % (rel, P._package_of(BK/rel), want, "OK" if P._package_of(BK/rel)==want else "MISMATCH"))
    w("  layering._package_of(%-26s) = %r  %s" % (rel, L._package_of(BK/rel), "OK" if L._package_of(BK/rel)==want else "MISMATCH"))

w("\n=== I. purity 断言消息里的后果链（:356-360）===")
# parts[:-1] -> parts 变异
def _package_of_parts(py):
    return py.relative_to(BK).with_suffix("").parts
folded = P._absolute("seed", 2, _package_of_parts(BK / "app/domain/x.py"))
w("  purity: _package_of 变异后 app/domain/x.py 里 from ..seed import … 折成 %r" % (folded,))
w("          _is_allowed(%r) = %s  (docstring 说命中白名单前缀 -> 假绿)" % (folded, P._is_allowed(folded)))
w("          startswith('app.domain.') = %s" % (folded.startswith("app.domain."),))
folded2 = L._absolute("seed", 3, _package_of_parts(BK / "app/db/models/x.py"))
w("  layering: 变异后 app/db/models/x.py 里 from ...seed import … 折成 %r" % (folded2,))
w("            _is_forbidden(%r) = %s  (docstring 说不再以 app.seed 开头 -> 假绿)" % (folded2, L._is_forbidden(folded2)))

w("\n=== J. _hit_forbidden_call（purity:507-510）===")
for s in ["builtins.open", "open", "reopen", "open_ended", "dt.datetime.now", "datetime.now", "eval", "_f"]:
    w("  _hit_forbidden_call(%-16r) = %r" % (s, P._hit_forbidden_call(s)))

w("\n=== K. _dotted 的四种形态（purity:472-477）===")
for s in ['f()()', 'table[0]()', 'getattr(x, "now")()', '__import__("datetime").datetime.now()']:
    node = ast.parse(s).body[0].value.func
    w("  %-40s func=%-52s _dotted=%r" % (s, type(node).__name__ + ("(value=%s)" % type(getattr(node,'value',None)).__name__ if isinstance(node, ast.Attribute) else ""), P._dotted(node)))

w("\n=== L. 计数 ===")
for mod, path in [(P, "test_domain_purity.py"), (L, "test_layering.py")]:
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    tests = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    w("  %s: %d 个 test_* -> %s" % (path, len(tests), tests))
