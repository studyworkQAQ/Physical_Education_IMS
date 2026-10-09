"""Plan 03 Task 2 预检（Ruling 1：每个 Task 一份探针）：7 张表要照的既有形状 + 会红掉的断言。"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### A. models/feedback.py 的空壳全文（Task 2 要把它的 docstring 改掉）")
fb = (BACKEND / "app" / "db" / "models" / "feedback.py").read_text(encoding="utf-8")
print(f"  ({len(fb.encode('utf-8'))} B)")
print(fb)

print("### B. models/ops.py 的类与列（3 张新表要照它的形状）")
ops = (BACKEND / "app" / "db" / "models" / "ops.py").read_text(encoding="utf-8")
print(f"  ({len(ops.encode('utf-8'))} B / {ops.count(chr(10))} 行)")
for n in ast.parse(ops).body:
    if isinstance(n, ast.ClassDef):
        print(f"  class {n.name}({', '.join(ast.unparse(b) for b in n.bases)})  "
              f"dec={[ast.unparse(d) for d in n.decorator_list]}")
        for s in n.body:
            if isinstance(s, ast.Assign):
                for tg in s.targets:
                    if isinstance(tg, ast.Name):
                        print(f"      {tg.id:24s} = {ast.unparse(s.value)[:110]}")
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                v = f" = {ast.unparse(s.value)}" if s.value is not None else ""
                print(f"      {s.target.id:24s}: {ast.unparse(s.annotation)}{v}"[:140])

print()
print("### C. _shared.py 的 _in_domain 签名 + JsonText 的住址")
sh = (BACKEND / "app" / "db" / "models" / "_shared.py").read_text(encoding="utf-8")
for m in re.finditer(r"^(def|class) (\w+)\(?([^)]*)\)?", sh, re.M):
    print(f"  {m.group(1)} {m.group(2)}({m.group(3)[:90]})")
from app.db.models._shared import _in_domain, JsonText  # noqa: E402
import inspect  # noqa: E402
print(f"  _in_domain{inspect.signature(_in_domain)}")
print(f"  JsonText 的 MRO = {[c.__name__ for c in JsonText.__mro__[:4]]}")

print()
print("### D. test_models.py 里所有会因「18 → 25 张表」而红的断言（硬规矩 #88：先数清）")
tm = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
TL = tm.split("\n")
print(f"  test_models.py {len(tm.encode('utf-8'))} B / {len(TL)} 行")
for i, l in enumerate(TL):
    if re.search(r"== 18|== 21|== 33|eighteen|len\(tables\)|len\(json_text|_BATCH_OWNED_TABLES|"
                 r"def test_all_|_MODELS_PUBLIC_BASELINE\)|_MODELS_SUBMODULES", l):
        print(f"  :{i+1} {l.strip()[:150]}")

print()
print("### E. test_generate.py 的分区清单实测长度（运行时口径）")
sys.path.insert(0, str(BACKEND / "tests" / "seed"))
import importlib.util  # noqa: E402
spec_ = importlib.util.spec_from_file_location("tsg", BACKEND / "tests" / "seed" / "test_generate.py")
mod = importlib.util.module_from_spec(spec_)
try:
    spec_.loader.exec_module(mod)
    for name in ("ORGANISATION_TABLES", "DATA_TABLES", "REFERENCE_TABLES", "_BATCH_OWNED_TABLES"):
        v = getattr(mod, name, None)
        if v is not None:
            print(f"  {name} = {len(v)} 个 {tuple(v)}")
except Exception as e:
    print(f"  ⚠️ 导入失败（{type(e).__name__}: {e}），改用文本口径")
    sg = (BACKEND / "tests" / "seed" / "test_generate.py").read_text(encoding="utf-8")
    for name in ("ORGANISATION_TABLES", "DATA_TABLES", "REFERENCE_TABLES", "_BATCH_OWNED_TABLES"):
        m = re.search(rf"^{name}\s*[:=].*?[\)\}}]", sg, re.M | re.S)
        if m:
            items = re.findall(r'"([^"]+)"', m.group(0))
            print(f"  {name} = {len(items)} 个 {items}")

print()
print("### F. _BATCH_OWNED_TABLES 的住址（Plan 02 Task 9 把 _DERIVED_TABLES 改成了这个名字）")
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    s = p.read_text(encoding="utf-8")
    if "_BATCH_OWNED_TABLES" in s:
        hits = [i + 1 for i, l in enumerate(s.split("\n")) if "_BATCH_OWNED_TABLES" in l]
        print(f"  {p.relative_to(BACKEND).as_posix()}: 行 {hits}")

print()
print("### G. weekly_adjustment 今天的约束（S2 要加一条唯一约束）")
from app.db.models.prescription import WeeklyAdjustment  # noqa: E402
t = WeeklyAdjustment.__table__
print(f"  列 = {[c.name for c in t.columns]}")
for c in t.constraints:
    print(f"  {type(c).__name__:26s} name={getattr(c, 'name', None)} "
          f"cols={[getattr(x, 'name', str(x)) for x in getattr(c, 'columns', [])]}")
for ix in t.indexes:
    print(f"  Index {ix.name} cols={[c.name for c in ix.columns]} unique={ix.unique}")

print()
print("### H. models/__init__.py 的 _MODELS_SUBMODULES 与「六个子模块」那段 docstring")
mi = (BACKEND / "app" / "db" / "models" / "__init__.py").read_text(encoding="utf-8")
for i, l in enumerate(mi.split("\n")):
    if re.search(r"_MODELS_SUBMODULES|六个子模块|from \.|Ruling 97", l):
        print(f"  :{i+1} {l.rstrip()[:150]}")

print()
print("### I. daily_sync_run 的列（4 张新表的 batch_id 要 FK 到它）")
from app.db import models as M  # noqa: E402
print(f"  {[c.name for c in M.Base.metadata.tables['daily_sync_run'].columns]}")
print(f"  表数 = {len(M.Base.metadata.tables)}")
print(f"  JsonText 列总数（运行时口径）= "
      f"{sum(1 for tb in M.Base.metadata.tables.values() for c in tb.columns if isinstance(c.type, JsonText))}")
