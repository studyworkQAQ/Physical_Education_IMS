from coverage.parser import PythonParser
import pathlib, collections, ast

BE = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend')
for rel in ('app/domain/prescription/templates.py',
            'app/domain/prescription/__init__.py',
            'app/domain/prescription/exercises.py'):
    p = BE / rel
    text = p.read_text(encoding='utf-8')
    parser = PythonParser(text=text)
    parser.parse_source()
    stmts = sorted(parser.statements)
    src = text.split('\n')
    kinds = collections.Counter()
    tree = ast.parse(text)
    # 给每个语句行找一个 AST 归类
    line_kind = {}
    def walk(node, scope):
        for child in ast.iter_child_nodes(node):
            if not hasattr(child, 'lineno'):
                continue
            if isinstance(child, (ast.ClassDef,)):
                line_kind.setdefault(child.lineno, 'ClassDef')
                walk(child, child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                line_kind.setdefault(child.lineno, 'FunctionDef')
                walk(child, child.name)
            elif isinstance(child, ast.Import):
                line_kind.setdefault(child.lineno, 'import')
                walk(child, scope)
            elif isinstance(child, ast.ImportFrom):
                line_kind.setdefault(child.lineno, 'import')
                walk(child, scope)
            elif isinstance(child, ast.AnnAssign):
                line_kind.setdefault(child.lineno,
                                     'AnnAssign(有值)' if child.value is not None else 'AnnAssign(无值)')
                walk(child, scope)
            elif isinstance(child, ast.Assign):
                line_kind.setdefault(child.lineno, 'Assign')
                walk(child, scope)
            elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) \
                    and isinstance(child.value.value, str):
                line_kind.setdefault(child.lineno, 'docstring')
                walk(child, scope)
            else:
                line_kind.setdefault(child.lineno, type(child).__name__)
                walk(child, scope)
    walk(tree, '<module>')
    for ln in stmts:
        kinds[line_kind.get(ln, '?? line %d' % ln)] += 1
    print('%s: coverage stmts = %d' % (rel, len(stmts)))
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print('    %-22s %d' % (k, v))
    print()
