"""新 Task 5 预检：把 5.1-5.4 会用到的既有接口逐个实测出来（不猜）。"""
import ast
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
assert BACKEND.is_dir(), BACKEND


def dump(path, only=()):
    src = (BACKEND / path).read_text(encoding="utf-8")
    print("=" * 74)
    print(f"{path}   {len(src.encode('utf-8'))} bytes   {src.count(chr(10))} lf")
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            if only and n.name not in only:
                continue
            decs = [ast.unparse(d) for d in n.decorator_list]
            bases = [ast.unparse(b) for b in n.bases]
            print(f"  class {n.name}  dec={decs}  bases={bases}")
            for s in n.body:
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    val = f" = {ast.unparse(s.value)}" if s.value is not None else ""
                    print(f"      .{s.target.id}: {ast.unparse(s.annotation)}{val}")
                elif isinstance(s, ast.Assign):
                    for tg in s.targets:
                        if isinstance(tg, ast.Name):
                            print(f"      {tg.id} = {ast.unparse(s.value)[:120]}")
                elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    a = s.args
                    names = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
                    kw = [x.arg for x in a.kwonlyargs]
                    ret = f" -> {ast.unparse(s.returns)}" if s.returns else ""
                    print(f"      def {s.name}({', '.join(names)}{', *, ' + ', '.join(kw) if kw else ''}){ret}")
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name) and tg.id.isupper():
                    print(f"  CONST {tg.id} = {ast.unparse(n.value)[:200]}")
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if only and n.name not in only:
                continue
            a = n.args
            names = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
            kw = [x.arg for x in a.kwonlyargs]
            ret = f" -> {ast.unparse(n.returns)}" if n.returns else ""
            print(f"  def {n.name}({', '.join(names)}{', *, ' + ', '.join(kw) if kw else ''}){ret}")


dump("app/domain/prescription/templates.py")
dump("app/domain/prescription/exercises.py")
dump("app/domain/prescription/__init__.py")
print("### sys.argv 之外的探针见 _t5_probe2.py")
sys.stdout.flush()
