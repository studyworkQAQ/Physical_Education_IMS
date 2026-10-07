# -*- coding: utf-8 -*-
"""pe_fr3_precheck.py — 写盘前的干跑：确认 OLD_167 / 两个插入锚点在目标文件里各命中恰 1 次，
并确认新增函数文本自身能 parse、能 compile、且不与既有顶层名撞名。

用法: python pe_fr3_precheck.py <仓库根>
"""
import ast
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
HERE = pathlib.Path(__file__).resolve().parent
EDIT = HERE / "pe_fr3_edit.py"

tree = ast.parse(EDIT.read_text(encoding="utf-8"))
consts = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        try:
            consts[node.targets[0].id] = ast.literal_eval(node.value)
        except ValueError:
            pass
print("从 pe_fr3_edit.py 取出字面常量:", sorted(consts))
need = {"OLD_167", "NEW_167_TEXT", "FUNC_PURITY_TEXT", "FUNC_LAYER_TEXT"}
assert need <= set(consts), need - set(consts)

OLD_167 = consts["OLD_167"]
NEW_167 = consts["NEW_167_TEXT"].split("\n")
FUNC = {"purity": consts["FUNC_PURITY_TEXT"].split("\n"),
        "layering": consts["FUNC_LAYER_TEXT"].split("\n")}

TARGETS = {
    "purity": (REPO / "backend/tests/architecture/test_domain_purity.py",
               "    return module in ALLOWED_MODULES"),
    "layering": (REPO / "backend/tests/architecture/test_layering.py",
                 '    return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")'),
}

for tag, (path, anchor) in TARGETS.items():
    raw = path.read_bytes()
    lines = raw.decode("utf-8").split("\r\n")
    print()
    print("=== %s (%s, %d 行) ===" % (tag, path.name, len(lines)))
    n_anchor = sum(1 for l in lines if l == anchor)
    print("  锚点 %r 命中 %d 次 -> %s" % (anchor.strip()[:44], n_anchor, "OK" if n_anchor == 1 else "!!"))
    assert n_anchor == 1
    src = "\n".join(lines)
    top = {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    new_top = {n.name for n in ast.parse("\n".join(FUNC[tag])).body
               if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    print("  新函数顶层名 %s；与既有 %d 个顶层名撞名 = %s" % (sorted(new_top), len(top), sorted(new_top & top)))
    assert not (new_top & top)
    compile("\n".join(FUNC[tag]), "<%s>" % tag, "exec")
    print("  新函数文本 compile() OK；%d 行" % len(FUNC[tag]))
    if tag == "purity":
        hits = [i for i, l in enumerate(lines) if l == OLD_167]
        print("  OLD_167 命中 %d 次 -> 行号 %s" % (len(hits), [i + 1 for i in hits]))
        assert hits == [166], hits
        print("  OLD_167（1 行）-> NEW_167（%d 行）:" % len(NEW_167))
        for l in NEW_167:
            print("      | %s" % l)
        keep = [i + 1 for i, l in enumerate(lines) if "命中白名单前缀" in l]
        print("  改前「命中白名单前缀」出现行 = %s（预期 [139, 167, 246]，改后应剩 2 处）" % keep)
        assert keep == [139, 167, 246], keep

print()
print("干跑 PASS：可以写盘")
