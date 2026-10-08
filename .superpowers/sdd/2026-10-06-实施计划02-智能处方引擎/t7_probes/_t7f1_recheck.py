"""复核两处探针口径问题：① outerjoin 是不是只出现在散文里；② _replay_cleanup 的真实清单顺序。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

src = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
tree = ast.parse(src)
fn = next(n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "_previous_prescriptions")
body_src = ast.get_source_segment(src, fn)
doc = ast.get_docstring(fn) or ""
code_only = body_src.replace(doc, "")
print("### _previous_prescriptions")
print(f"  docstring 里 'outerjoin' 命中 = {doc.count('outerjoin')}")
print(f"  **代码部分**（去掉 docstring）里 'outerjoin' 命中 = {code_only.count('outerjoin')}  (应 0)")
print(f"  **代码部分**里 'StratificationResult' 命中 = {code_only.count('StratificationResult')}  (应 0)")
print(f"  AST 里的方法调用名 = {sorted({n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)})}")

d = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
dtree = ast.parse(d)
rf = next(n for n in dtree.body if isinstance(n, ast.FunctionDef) and n.name == "_replay_cleanup")
names = []
for node in ast.walk(rf):
    if isinstance(node, ast.Tuple):
        got = []
        for e in node.elts:
            if isinstance(e, ast.Attribute):
                got.append(e.attr)
            elif isinstance(e, ast.Name):
                got.append(e.id)
        if got:
            names.append(tuple(got))
print()
print("### _replay_cleanup 里的元组字面量（AST 口径，不含散文）")
for t in names:
    print(f"  {t}")
m = re.search(r"_TABLES\s*=\s*\(([^)]*)\)", ast.get_source_segment(d, rf) or "")
print(f"  模块/函数级清单常量 = {m.group(0)[:200] if m else '（无）'}")
