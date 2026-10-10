"""自查：本 Task 碰过的文件里有没有**未使用**的 import（AST 口径）。

判据：一个 import 绑定的名字，若在模块的其余部分（含 docstring 之外的代码）一次都没被
引用，就是死 import。⚠️ 刻意排除两类：
  * ``__all__`` 里出现的名字（那是重导出，本身就是用途）；
  * 带 ``# noqa`` 的（例如 ``import app.db.models  # noqa: F401`` 那种「只为注册表」的）。
"""
import ast
import pathlib

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")

FILES = [
    "app/notify.py",
    "app/pipeline/alert_stage.py",
    "app/pipeline/prescription_stage.py",
    "app/pipeline/daily.py",
    "app/api/routers/alerts.py",
    "app/api/routers/__init__.py",
    "app/api/routers/feedback.py",
    "app/api/schemas/alerts.py",
    "tests/test_notify.py",
    "tests/pipeline/test_alert_stage.py",
    "tests/api/test_alerts_api.py",
]

for rel in FILES:
    path = BACKEND / rel
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    imported: dict[str, int] = {}
    noqa_lines = set()
    for index, line in enumerate(src.splitlines(), start=1):
        if "noqa" in line:
            noqa_lines.add(index)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imported[bound] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                imported[bound] = node.lineno

    exported = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            exported |= {e.value for e in node.value.elts if isinstance(e, ast.Constant)}

    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
    # 属性访问的根名（models.Student / dt.date / stage.X）
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                used.add(root.id)
    # 字符串标注里的名字（"tuple[set[dt.date], bool]" 一类）
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name in imported:
                if name in node.value:
                    used.add(name)

    dead = sorted(
        name for name, lineno in imported.items()
        if name not in used and name not in exported and lineno not in noqa_lines
    )
    print(f"{rel}: import {len(imported)} 个，未使用 {len(dead)} 个"
          + (f" → {dead}" if dead else ""))
