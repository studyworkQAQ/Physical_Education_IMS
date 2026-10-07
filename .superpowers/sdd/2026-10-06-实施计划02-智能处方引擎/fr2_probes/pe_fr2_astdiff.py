# -*- coding: utf-8 -*-
"""pe_fr2_astdiff.py — 两个架构守卫里，到底哪些顶层对象的 AST 变了（剥 docstring 后）。

用来证明：本轮只动了 _absolute / _imported_modules（以及 purity 侧那个必须跟着改的调用点），
两个 test_* 函数的**断言**逐字未动。
"""
import ast
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMIT = "6a2938f"
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]


def strip(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = [ast.Pass()] + b[1:]
    return tree


def units(src):
    """顶层单元 → 剥 docstring 后的 ast.dump；模块级赋值单独归到 '<module-level>'。"""
    tree = strip(ast.parse(src.replace("\r\n", "\n")))
    out = {}
    mod = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node, include_attributes=False)
        else:
            mod.append(ast.dump(node, include_attributes=False))
    out["<module-level>"] = "\n".join(mod)
    return out


def base(rel):
    out = subprocess.run(["git", "show", "%s:%s" % (COMMIT, rel)], cwd=str(REPO),
                         capture_output=True)
    assert out.returncode == 0
    return out.stdout.decode("utf-8")


for rel in FILES:
    b = units(base(rel))
    w = units((REPO / rel).read_text(encoding="utf-8"))
    print("=== %s ===" % rel)
    names = list(dict.fromkeys(list(b) + list(w)))
    for n in names:
        if n not in b:
            print("   NEW       %s" % n)
        elif n not in w:
            print("   DELETED   %s" % n)
        elif b[n] != w[n]:
            print("   AST 变了  %s" % n)
        else:
            print("   未动      %s" % n)
    print()

print("=== 两个 test_* 函数体里的 assert 语句逐字对比（剥 docstring 后） ===")


def asserts(src, fnname):
    tree = ast.parse(src.replace("\r\n", "\n"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return [ast.dump(a, include_attributes=False)
                    for a in ast.walk(node) if isinstance(a, ast.Assert)]
    return []


PAIRS = [("backend/tests/architecture/test_domain_purity.py",
          "test_domain_imports_stay_within_the_allow_list"),
         ("backend/tests/architecture/test_domain_purity.py",
          "test_domain_has_no_clock_or_file_access"),
         ("backend/tests/architecture/test_domain_purity.py",
          "test_domain_has_no_filesystem_access"),
         ("backend/tests/architecture/test_layering.py",
          "test_production_layers_never_import_app_seed")]
for rel, fn in PAIRS:
    a1 = asserts(base(rel), fn)
    a2 = asserts((REPO / rel).read_text(encoding="utf-8"), fn)
    print("   %-52s %-46s assert 条数 %d→%d  逐字相同=%s"
          % (pathlib.Path(rel).name, fn, len(a1), len(a2), a1 == a2))
    assert a1 == a2, (rel, fn)
print()
print("断言未变闸门: PASS")
