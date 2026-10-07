# -*- coding: utf-8 -*-
"""Probe P9 (Section C): 两份回归测试的独立性 + 变异验收。
全部在 $env:TEMP 的 backend 副本上做，**主工作树一字不动**（前后核 sha256）。"""
import ast, hashlib, os, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
REAL = ROOT / "backend"
G1 = "tests/architecture/test_domain_purity.py"
G2 = "tests/architecture/test_layering.py"

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_mut_p9_"))
COPY = TMP / "backend"
shutil.copytree(REAL, COPY, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


before = {f: sha(REAL / f) for f in (G1, G2)}
orig = {f: (COPY / f).read_text(encoding="utf-8") for f in (G1, G2)}


def strip_doc_src(src):
    t = ast.parse(src)
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return ast.dump(t)


def apply(f, old, new, tag):
    s = orig[f]
    n = s.count(old)
    assert n == 1, "%s: 目标串在 %s 里出现 %d 次（应为 1）" % (tag, f, n)
    mutated = s.replace(old, new)
    # 硬规矩 #53：在剥 docstring 的 AST 上确认真的改了代码
    real_change = strip_doc_src(orig[f]) != strip_doc_src(mutated)
    (COPY / f).write_text(mutated, encoding="utf-8")
    return real_change


def restore():
    for f in (G1, G2):
        (COPY / f).write_text(orig[f], encoding="utf-8")
        assert sha(COPY / f) == before[f], "还原失败: " + f


def run():
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/architecture", "-q", "-k", "absolute",
                        "--tb=no", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(COPY))
    out = r.stdout.strip().splitlines()
    tail = out[-1] if out else ""
    # 哪一份红
    det = subprocess.run([sys.executable, "-m", "pytest", "tests/architecture", "-k", "absolute",
                          "--tb=no", "-q", "-rf", "-p", "no:cacheprovider"],
                         capture_output=True, text=True, encoding="utf-8", cwd=str(COPY))
    failed = [l for l in det.stdout.splitlines() if l.startswith("FAILED")]
    return tail, [f.split("::")[0].split("/")[-1] for f in failed]


PHASES = [
    ("M0 不变异（对照）", None),
    ("M1 语义等价改写 package[: len(package)-(level-1)] -> package[: len(package)-level+1]（对照）",
     [(G1, "\n    anchor = package[: len(package) - (level - 1)]\n",
       "\n    anchor = package[: len(package) - level + 1]\n"),
      (G2, "\n    anchor = package[: len(package) - (level - 1)]\n",
       "\n    anchor = package[: len(package) - level + 1]\n")]),
    ("① 删掉越界守卫 —— 只改 test_layering.py",
     [(G2, "\n    if level - 1 > len(package):\n"
           "        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串\n"
           "        return None\n", "\n")]),
    ("① 删掉越界守卫 —— 只改 test_domain_purity.py",
     [(G1, "\n    if level - 1 > len(package):\n"
           "        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串\n"
           "        return None\n", "\n")]),
    ("② tail = module or name -> tail = module —— 只改 test_layering.py",
     [(G2, "\n    tail = module or name\n", "\n    tail = module\n")]),
    ("② tail = module or name -> tail = module —— 只改 test_domain_purity.py",
     [(G1, "\n    tail = module or name\n", "\n    tail = module\n")]),
    ("③ parts[:-1] -> parts —— 只改 test_layering.py",
     [(G2, '\n    return py.relative_to(BACKEND).with_suffix("").parts[:-1]\n',
       '\n    return py.relative_to(BACKEND).with_suffix("").parts\n')]),
    ("③ parts[:-1] -> parts —— 只改 test_domain_purity.py",
     [(G1, '\n    return py.relative_to(BACKEND).with_suffix("").parts[:-1]\n',
       '\n    return py.relative_to(BACKEND).with_suffix("").parts\n')]),
    ("③ parts[:-1] -> parts —— 两份都改",
     [(G1, '\n    return py.relative_to(BACKEND).with_suffix("").parts[:-1]\n',
       '\n    return py.relative_to(BACKEND).with_suffix("").parts\n'),
      (G2, '\n    return py.relative_to(BACKEND).with_suffix("").parts[:-1]\n',
       '\n    return py.relative_to(BACKEND).with_suffix("").parts\n')]),
]

print("%-64s %-22s %s" % ("相位", "pytest 末行", "红的是哪一份"))
for label, muts in PHASES:
    restore()
    changes = []
    if muts:
        for f, old, new in muts:
            changes.append(apply(f, old, new, label))
    tail, failed = run()
    flag = ""
    if muts and not all(changes):
        flag = "  !! 变异在 AST 上无效 !!"
    print("%-64s %-22s %s%s" % (label[:64], tail[:22], failed or "[]", flag))
restore()

print("\n=== 主工作树 sha256 前后对比（证明一字未动）===")
after = {f: sha(REAL / f) for f in (G1, G2)}
for f in (G1, G2):
    print("  %-46s %s  %s" % (f, after[f][:16], "UNCHANGED" if before[f] == after[f] else "!! CHANGED !!"))

print("\n=== 硬规矩 #51：两份 _absolute / _package_of 剥 docstring 后是否逐字相同 ===")
for fname, mod in (("test_domain_purity.py", G1), ("test_layering.py", G2)):
    pass


def funcs(path, names):
    t = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    out = {}
    for n in t.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            body = n.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            nn = ast.FunctionDef(name=n.name, args=n.args, body=body,
                                 decorator_list=[], returns=n.returns, type_comment=None)
            out[n.name] = (ast.dump(nn), [a.arg for a in n.args.args],
                           len(n.args.defaults), len(body))
    return out


A = funcs(REAL / G1, {"_absolute", "_package_of", "_is_allowed", "_is_forbidden",
                      "_imported_modules", "_dotted", "_hit_forbidden_call"})
B = funcs(REAL / G2, {"_absolute", "_package_of", "_is_allowed", "_is_forbidden",
                      "_imported_modules", "_dotted", "_hit_forbidden_call"})
for name in ("_absolute", "_package_of"):
    same = A[name][0] == B[name][0]
    print("  %-14s purity args=%s defaults=%d stmts=%d | layering args=%s defaults=%d stmts=%d -> identical(excl docstring) = %s"
          % (name, A[name][1], A[name][2], A[name][3], B[name][1], B[name][2], B[name][3], same))
print("  只在一个文件里存在的辅助:", sorted((set(A) ^ set(B))))

shutil.rmtree(TMP, ignore_errors=True)
print("\n临时副本已删除:", TMP.exists())
