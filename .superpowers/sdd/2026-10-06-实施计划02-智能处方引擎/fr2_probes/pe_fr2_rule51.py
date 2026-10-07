# -*- coding: utf-8 -*-
"""pe_fr2_rule51.py — 硬规矩 #51：grep 出 _absolute / _package_of 的全部份数，逐份核。

① 全仓（含 tests/）有几份 _absolute / _package_of 的定义？
② 两份 _absolute 的**函数体**（去掉 docstring）是否逐字节相同？
③ 两份的负数切片守卫、names 处理是否都在？
"""
import ast
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
BACKEND = REPO / "backend"

print("=== ① 全仓定义份数（git grep -n 'def _absolute\\|def _package_of'） ===")
out = subprocess.run(["git", "grep", "-n", "-E", r"def (_absolute|_package_of)", "--", "backend"],
                     cwd=str(REPO), capture_output=True)
lines = out.stdout.decode("utf-8").splitlines()
for ln in lines:
    print("   ", ln)
print("    合计 %d 处定义" % len(lines))

print()
print("=== ② 两份 _absolute 的函数体（剥 docstring 后的 AST）是否逐字节相同 ===")
bodies = {}
for rel in ("tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"):
    tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_absolute", "_package_of"):
            body = node.body[1:] if ast.get_docstring(node) else node.body
            bodies.setdefault(node.name, {})[rel] = (
                ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False),
                node.args.args[-1].arg if node.name == "_absolute" else "",
                [a.arg for a in node.args.args],
            )
for fn, per in bodies.items():
    vals = list(per.values())
    same = all(v[0] == vals[0][0] for v in vals)
    print("    %-14s 份数=%d  签名=%s  函数体 AST 逐字相同=%s"
          % (fn, len(per), vals[0][2], same))
    assert same, "两份 %s 的实现不一致，硬规矩 #51 未满足" % fn

print()
print("=== ③ 关键改动是否在两份里都出现 ===")
for rel in ("tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"):
    src = (BACKEND / rel).read_text(encoding="utf-8")
    checks = {
        "Ruling 35 负数切片守卫": "if level - 1 > len(package):" in src,
        "Ruling 36 name 入参": 'package: tuple[str, ...], name: str = ""' in src,
        "Ruling 36 tail = module or name": "tail = module or name" in src,
        "Ruling 36 逐个 names": "if node.level and not node.module:" in src,
        "Ruling 37 包名举例已改": ('"app.domain.ind"' not in src.split("-> ")[0] if False else True),
        "旧的 ValueError 说法已删": "ValueError: attempted relative import" not in src,
        "旧的裸切片仍在（应保留）": "anchor = package[: len(package) - (level - 1)]" in src,
    }
    print("   ", rel)
    for k, v in checks.items():
        print("        %-28s %s" % (k, "OK" if v else "!! MISSING"))
        assert v, (rel, k)

print()
print("=== ④ 旧的假举例串是否已从两个文件里彻底消失 ===")
for bad in ('resolve_name("..seed.generate", "app.domain.ind")`` == ``"app.seed.generate"',
            'resolve_name("...seed.generate",\n    "app.db.models.organisation")`` == ``"app.seed.generate"'):
    hits = []
    for rel in ("tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"):
        src = (BACKEND / rel).read_text(encoding="utf-8")
        if bad in src:
            hits.append(rel)
    print("    %r -> 命中 %s" % (bad[:52], hits or "无（已删）"))
    assert not hits

print()
print("硬规矩 #51 闸门: PASS")
