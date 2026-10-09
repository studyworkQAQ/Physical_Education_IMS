"""探针 P3-A3：``_BATCH_OWNED_TABLES`` 到底定义在哪个文件。

派单预检说「它是生产代码里的常量，测试那一份是镜像」，并点名
``app/db/models/__init__.py`` / ``app/db/models/prescription.py``（两处）/
``app/pipeline/daily.py`` / ``tests/db/test_models.py``（六处）。
本探针用 **AST** 而不是 grep 判「哪一处是赋值」：只有 ``ast.Assign`` /
``ast.AnnAssign`` 的目标名叫 ``_BATCH_OWNED_TABLES`` 才算定义，
出现在字符串/注释里的一律算散文引用。
"""
import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
NAME = "_BATCH_OWNED_TABLES"

definitions, prose = [], []
for path in sorted(BACKEND.rglob("*.py")):
    if "t2_probes" in path.parts:
        continue
    source = path.read_text(encoding="utf-8")
    if NAME not in source:
        continue
    rel = path.relative_to(BACKEND).as_posix()
    tree = ast.parse(source)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == NAME:
                assigned.append(node.lineno)
    hits = sum(1 for line in source.splitlines() if NAME in line)
    if assigned:
        definitions.append((rel, assigned, hits))
    else:
        prose.append((rel, hits))

print("=== 赋值（真定义）===")
for rel, linenos, hits in definitions:
    print(f"  {rel}: 定义在第 {linenos} 行；该文件共 {hits} 行提到它")
print(f"  合计定义处 = {sum(len(l) for _r, l, _h in definitions)}")

print("=== 只有散文引用（注释 / docstring / 字符串）===")
for rel, hits in prose:
    print(f"  {rel}: {hits} 行提到它，0 处赋值")

app_prose = sum(h for r, h in prose if r.startswith("app/"))
print(f"\napp/ 下的散文引用行数 = {app_prose}（派单预检说的是「四处命中」）")
print("结论：", "只有一份定义" if len(definitions) == 1 else f"{len(definitions)} 份定义！")
