# -*- coding: utf-8 -*-
"""Probe P14: purity:230-232「Task 2 起 app/domain/prescription/ 子包里的
   `from ..indicators import X` 正是这一档（level == 1 的包内导入）」这句的实测复核。
   以及两份矩阵里绿档的 AST 形状清点。"""
import ast, importlib.util, pathlib, sys
sys.path.insert(0, r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture")
import test_domain_purity as P
import test_layering as L
rn = importlib.util.resolve_name

print("=== 1. `from ..indicators import X` 的 AST 形状 ===")
t = ast.parse("from ..indicators import X\n")
n = t.body[0]
print("  ImportFrom(level=%d, module=%r, names=%s)" % (n.level, n.module, [a.name for a in n.names]))
print("  -> level = %d（**不是 1**）；点是 2 个" % n.level)

print("\n=== 2. 它在 Task 2 的形状（app/domain/prescription/x.py，包深 3）下折算成什么 ===")
pkg = P._package_of(P.BACKEND / "app/domain/prescription/x.py")
print("  _package_of(app/domain/prescription/x.py) = %r" % (pkg,))
folded = P._absolute("indicators", 2, pkg)
print("  purity ._absolute('indicators', 2, %r) = %r" % (pkg, folded))
print("  resolve_name('..indicators', 'app.domain.prescription') = %r" % rn("..indicators", "app.domain.prescription"))
print("  purity ._is_allowed(%r) = %s -> %s" % (folded, P._is_allowed(folded),
                                               "GREEN" if P._is_allowed(folded) else "RED"))
print("  layering._is_forbidden(%r) = %s -> %s" % (folded, L._is_forbidden(folded),
                                                 "RED" if L._is_forbidden(folded) else "GREEN"))

print("\n=== 3. 而 docstring 说的那一档（level == 1）是什么形状 ===")
f1 = P._absolute("tables", 1, ("app", "domain"))
print("  purity 矩阵第 2 行 ('tables', 1, ('app','domain')) -> %r  _is_allowed=%s" % (f1, P._is_allowed(f1)))
print("  对应写法是 `from .tables import X`（**一个点**），源文件在 app/domain/ 下（包深 2）")
print("  而 Task 2 的 prescription/match.py 里写 `from .indicators import X` 会折成 %r" %
      P._absolute("indicators", 1, ("app", "domain", "prescription")))

print("\n=== 4. 两份矩阵的绿档清点（AST 形状）===")


def cases_of(mod):
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
              and x.name == "test_absolute_folding_matches_resolve_name")
    for st in ast.walk(fn):
        if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "cases":
            return ast.literal_eval(st.value)


for name, mod, judge in (("purity", P, lambda s: not P._is_allowed(s)),
                         ("layering", L, lambda s: L._is_forbidden(s))):
    cs = cases_of(mod)
    print("  %s: %d 格" % (name, len(cs)))
    red = sum(1 for c in cs if c[4] == "RED")
    print("     RED %d 格 / GREEN %d 格" % (red, len(cs) - red))
    for i, c in enumerate(cs, 1):
        if c[4] == "GREEN":
            print("     绿档第 %d 行: module=%r level=%d package=%r name=%r  (包深 %d)"
                  % (i, c[0], c[1], c[2], c[3], len(c[2])))
    dep3 = [i for i, c in enumerate(cs, 1) if len(c[2]) == 3]
    print("     包深 3 的行: %s，其颜色: %s" % (dep3, [cs[i - 1][4] for i in dep3]))

print("\n=== 5. Task 2 形状（包深 3 + level 2 + 合法目标）在 purity 矩阵里有没有 ===")
cs = cases_of(P)
hit = [c for c in cs if len(c[2]) == 3 and c[1] == 2 and c[4] == "GREEN"]
print("  purity 矩阵里 (包深3, level2, GREEN) 的格数 =", len(hit), hit)
csL = cases_of(L)
hitL = [c for c in csL if len(c[2]) == 3 and c[1] == 2 and c[4] == "GREEN"]
print("  layering 矩阵里 (包深3, level2, GREEN) 的格数 =", len(hitL), hitL)
