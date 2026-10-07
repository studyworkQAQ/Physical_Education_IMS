"""P1 — Ruling 67 亲跑：Task 2 的形状到底是 level 几，两侧各是什么颜色。"""
import ast, importlib.util, pathlib, sys

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
sys.path.insert(0, str(BACKEND))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, BACKEND / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pur = load("tests/architecture/test_domain_purity.py", "pur_mod")
lay = load("tests/architecture/test_layering.py", "lay_mod")

src = "from ..indicators import X\n"
node = ast.parse(src).body[0]
print("== AST of %r" % src.strip())
print("   type=%s level=%r module=%r names=%r"
      % (type(node).__name__, node.level, node.module,
         [a.name for a in node.names]))
print("   点数 = %d 个 '.'" % node.level)

relpath = "app/domain/prescription/match.py"
print("\n== _package_of(%s)" % relpath)
print("   purity  _package_of ->", pur._package_of(pur.BACKEND / relpath))
print("   layering _package_of ->", lay._package_of(lay.BACKEND / relpath))
print("   BACKEND(purity) =", pur.BACKEND)
print("   BACKEND(layering) =", lay.BACKEND)
print("   DOMAIN(purity) =", pur.DOMAIN)

pkg = pur._package_of(pur.BACKEND / relpath)
module, level, name = node.module, node.level, node.names[0].name
abs_pur = pur._absolute(module, level, pkg, name)
abs_lay = lay._absolute(module, level, lay._package_of(lay.BACKEND / relpath), name)
print("\n== _absolute('indicators', %d, %r, 'X')" % (level, pkg))
print("   purity  _absolute ->", repr(abs_pur))
print("   layering _absolute ->", repr(abs_lay))
print("   importlib.util.resolve_name('..indicators', %r) -> %r"
      % (".".join(pkg), importlib.util.resolve_name("..indicators", ".".join(pkg))))

print("\n== 两侧各自的判定（主语标清）")
print("   purity   _is_allowed(%r)    = %s  -> 该文件判 %s"
      % (abs_pur, pur._is_allowed(abs_pur),
         "GREEN" if pur._is_allowed(abs_pur) else "RED"))
print("   layering _is_forbidden(%r) = %s  -> 该文件判 %s"
      % (abs_lay, lay._is_forbidden(abs_lay),
         "RED" if lay._is_forbidden(abs_lay) else "GREEN"))
print("   purity   ALLOWED_PACKAGE = %r" % pur.ALLOWED_PACKAGE)
print("   layering FORBIDDEN_PREFIX = %r" % lay.FORBIDDEN_PREFIX)
print("   %r.startswith(%r + '.') = %s"
      % (abs_pur, pur.ALLOWED_PACKAGE,
         abs_pur.startswith(pur.ALLOWED_PACKAGE + ".")))
print("   %r == %r or startswith(%r + '.') = %s"
      % (abs_lay, lay.FORBIDDEN_PREFIX, lay.FORBIDDEN_PREFIX,
         abs_lay == lay.FORBIDDEN_PREFIX
         or abs_lay.startswith(lay.FORBIDDEN_PREFIX + ".")))

# ---- 现有矩阵逐格数颜色 / 包深 / level ----
print("\n== 现有 cases 矩阵（AST 抽，不是手数）")
for rel, name_ in (("tests/architecture/test_domain_purity.py", "purity"),
                   ("tests/architecture/test_layering.py", "layering")):
    tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef)
              and n.name == "test_absolute_folding_matches_resolve_name")
    cases = None
    for st in ast.walk(fn):
        if isinstance(st, ast.Assign) and any(
                getattr(t, "id", "") == "cases" for t in st.targets):
            cases = ast.literal_eval(st.value)
    print("  %s: %d 格" % (name_, len(cases)))
    from collections import Counter
    c = Counter((len(r[2]), r[1], r[4]) for r in cases)
    for k in sorted(c):
        print("     (包深 %d, level %d, %s) -> %d 格" % (k[0], k[1], k[2], c[k]))
    green3_2 = [r for r in cases if len(r[2]) == 3 and r[1] == 2 and r[4] == "GREEN"]
    print("     (包深3, level2, GREEN) = %d 格  %s" % (len(green3_2), green3_2))
