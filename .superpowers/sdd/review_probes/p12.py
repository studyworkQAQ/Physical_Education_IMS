# -*- coding: utf-8 -*-
"""Probe P12: ③ 展开档变异（只 yield 第一个名字）+ 断言消息原文；
   以及 purity:560-561 的 `now = datetime.now` 那一档。全部在 $env:TEMP 副本上做。"""
import ast, hashlib, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
REAL = ROOT / "backend"
G1 = "tests/architecture/test_domain_purity.py"
G2 = "tests/architecture/test_layering.py"
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_mut_p12_"))
COPY = TMP / "backend"
shutil.copytree(REAL, COPY, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
orig = {f: (COPY / f).read_text(encoding="utf-8") for f in (G1, G2)}
before = {f: hashlib.sha256((REAL / f).read_bytes()).hexdigest() for f in (G1, G2)}

P_OLD = '\n                for alias in node.names:\n                    yield node.lineno, "", node.level, alias.name\n'
P_NEW = '\n                yield node.lineno, "", node.level, node.names[0].name\n'
L_OLD = '\n                for alias in node.names:\n                    yield node.lineno, _absolute("", node.level, package, alias.name)\n'
L_NEW = '\n                yield node.lineno, _absolute("", node.level, package, node.names[0].name)\n'


def strip_doc_src(src):
    t = ast.parse(src)
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return ast.dump(t)


def restore():
    for f in (G1, G2):
        (COPY / f).write_text(orig[f], encoding="utf-8")


def run(show_msg=False):
    args = [sys.executable, "-m", "pytest", "tests/architecture", "-k", "absolute",
            "-p", "no:cacheprovider", "--tb=line" if show_msg else "--tb=no", "-q"]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=str(COPY))
    lines = r.stdout.splitlines()
    tail = lines[-1] if lines else ""
    failed = sorted({l.split("::")[0].split("/")[-1].split("\\")[-1]
                     for l in lines if l.startswith("FAILED") or ("::" in l and "Error" in l)})
    msg = [l for l in lines if "展开失效" in l]
    return tail, failed, msg


for label, f, old, new in [
    ("③ 只 yield 第一个名字 —— 只改 test_domain_purity.py", G1, P_OLD, P_NEW),
    ("③ 只 yield 第一个名字 —— 只改 test_layering.py", G2, L_OLD, L_NEW),
]:
    restore()
    s = orig[f]
    assert s.count(old) == 1, (label, s.count(old))
    mut = s.replace(old, new)
    assert strip_doc_src(s) != strip_doc_src(mut), "变异在 AST 上无效: " + label
    (COPY / f).write_text(mut, encoding="utf-8")
    tail, failed, msg = run(show_msg=True)
    print("%-52s -> %-24s 红的是 %s" % (label[:52], tail[:24], failed))
    for m in msg:
        print("      断言原文:", m.strip()[:200])
restore()

print("\n=== purity:560-561 —— `now = datetime.now` 再 `now()` ===")
sys.path.insert(0, str(ROOT / ".superpowers" / "sdd" / "review_probes"))
import importlib.util
spec = importlib.util.spec_from_file_location("hp", REAL / G1)
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
DOM = TMP / "b2" / "app" / "domain"
DOM.mkdir(parents=True)
P.DOMAIN = DOM
P.BACKEND = TMP / "b2"
for i in range(5):
    (DOM / ("filler%d.py" % i)).write_text("VALUE = %d\n" % i, encoding="utf-8")
src = "import datetime\nnow = datetime.now\nnow()\n"
(DOM / "probe.py").write_text(src, encoding="utf-8")
for name, fn in [("G1", P.test_domain_imports_stay_within_the_allow_list),
                 ("G2", P.test_domain_has_no_clock_or_file_access),
                 ("G3", P.test_domain_has_no_filesystem_access)]:
    try:
        fn(); print("  %s GREEN" % name)
    except AssertionError as e:
        print("  %s RED   <- %s" % (name, str(e).splitlines()[-1][:100]))

after = {f: hashlib.sha256((REAL / f).read_bytes()).hexdigest() for f in (G1, G2)}
print("\n主工作树 sha256 未变:", all(before[f] == after[f] for f in (G1, G2)),
      {f.split("/")[-1]: after[f][:16] for f in (G1, G2)})
shutil.rmtree(TMP, ignore_errors=True)
print("临时副本已删除:", TMP.exists())
