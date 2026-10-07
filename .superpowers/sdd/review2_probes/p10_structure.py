import os, re, ast, sys
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
TARGETS = [
 r"backend\tests\test_refdata_prescription.py",
 r"backend\tests\domain\test_prescription_templates.py",
 r"backend\tests\architecture\test_domain_purity.py",
 r"backend\tests\architecture\test_layering.py",
 r"backend\tests\db\test_models.py",
 r"backend\tests\seed\test_generate.py",
]
for rel in TARGETS:
    raw = open(os.path.join(ROOT, rel),'rb').read()
    src = raw.replace(b"\r\n", b"\n").decode("utf-8")
    L = src.split("\n")
    tree = ast.parse(src)
    print("="*78)
    print(f"### {rel}   lines={len(L)-1}")
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            deco = ",".join(ast.unparse(d) for d in node.decorator_list)
            print(f"  def {node.name:<78} line={node.lineno}  {('@'+deco) if deco else ''}")
        elif isinstance(node, ast.ClassDef):
            print(f"  class {node.name} line={node.lineno}")
            for sub in node.body:
                if isinstance(sub,(ast.FunctionDef,)):
                    print(f"      def {sub.name} line={sub.lineno}")
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and (t.id.isupper() or t.id.startswith("_")):
                    try:
                        v = ast.unparse(node.value)
                    except Exception:
                        v = "?"
                    print(f"  CONST {t.id} line={node.lineno} = {v[:300]}")
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            try: v = ast.unparse(node.value)
            except Exception: v = "?"
            print(f"  ANNCONST {node.target.id} line={node.lineno} = {v[:200]}")
