# -*- coding: utf-8 -*-
"""pe_fr5_astdiff.py — 硬规矩 #32 的 fix round 5 形态：改动面自证（代码基线 6784d57，带对照组）。

⚠️ HEAD 是 d00533c，但 d00533c / ef48d33 / 73313f7 三个都只是 Document/ 下的文档 commit，
两个守卫文件与 daily.py / test_models.py 自 6784d57 起未变，故代码基线取 6784d57。
"""
import ast
import difflib
import io
import pathlib
import subprocess
import sys
import tokenize

REPO = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
COMMIT = "6784d57"
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py",
         "backend/tests/db/test_models.py",
         "backend/app/pipeline/daily.py"]
EXPECT = {
    FILES[0]: ["test_absolute_folding_matches_resolve_name"],
    FILES[1]: ["test_absolute_folding_matches_resolve_name"],
    FILES[2]: [],
    FILES[3]: [],
}
CHANGED_UNIT = "test_absolute_folding_matches_resolve_name"
GIT = ["git", "-c", "core.quotepath=false"]


def norm(src):
    return src.replace("\r\n", "\n")


def strip_docs(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = [ast.Pass()] + b[1:]
    return tree


def units(src):
    tree = strip_docs(ast.parse(norm(src)))
    out, mod = {}, []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node, include_attributes=False)
        else:
            mod.append(ast.dump(node, include_attributes=False))
    out["<module-level>"] = "\n".join(mod)
    return out


def base(rel):
    r = subprocess.run(GIT + ["show", "%s:%s" % (COMMIT, rel)], cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, rel
    return r.stdout.decode("utf-8")          # blob 是 LF 版，norm() 会再归一化


def work(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def docs(src):
    tree = ast.parse(norm(src))
    out = {"<module>": ast.get_docstring(tree) or ""}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.get_docstring(node) or ""
    return out


def comments(src):
    return [t.string for t in tokenize.generate_tokens(io.StringIO(norm(src)).readline)
            if t.type == tokenize.COMMENT]


def asserts_of(src, fnname):
    tree = ast.parse(norm(src))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return [ast.dump(a, include_attributes=False) for a in ast.walk(node)
                    if isinstance(a, ast.Assert)]
    return []


print("=== ⓪ 改动面 ===")
head = subprocess.run(GIT + ["rev-parse", "--short", "HEAD"], cwd=str(REPO),
                      capture_output=True).stdout.decode().strip()
r = subprocess.run(GIT + ["diff", "--name-only", "HEAD"], cwd=str(REPO), capture_output=True)
names = r.stdout.decode("utf-8").split()
print("   HEAD = %s ; git diff --name-only HEAD = %s" % (head, names))
assert set(names) == set(FILES), names
r = subprocess.run(GIT + ["diff", "--numstat", "HEAD"], cwd=str(REPO), capture_output=True)
for l in r.stdout.decode("utf-8").splitlines():
    print("     ", l)
r = subprocess.run(GIT + ["diff", "--name-only", COMMIT, "--", "backend/"],
                   cwd=str(REPO), capture_output=True)
bnames = r.stdout.decode("utf-8").split()
print("   git diff --name-only %s -- backend/ = %s" % (COMMIT, bnames))
assert set(bnames) == set(FILES), bnames
r = subprocess.run(GIT + ["diff", "--name-only", COMMIT, "--", "backend/app/"],
                   cwd=str(REPO), capture_output=True)
app = r.stdout.decode("utf-8").split()
print("   git diff --name-only %s -- backend/app/ = %s（禁区里只允许 daily.py 一个）" % (COMMIT, app))
assert app == ["backend/app/pipeline/daily.py"], app
r = subprocess.run(GIT + ["diff", "--name-only", "HEAD", "--", "backend/data/", "Document/"],
                   cwd=str(REPO), capture_output=True)
print("   git diff --name-only HEAD -- backend/data/ Document/ = %r（本轮工作树改动，必须空）"
      % (r.stdout.decode("utf-8").split()))
assert r.stdout.decode("utf-8").split() == []
r = subprocess.run(GIT + ["diff", "--name-only", COMMIT, "HEAD", "--", "Document/"],
                   cwd=str(REPO), capture_output=True)
print("   git diff --name-only %s HEAD -- Document/ = %s（这是控制者自己的 ef48d33/d00533c 两个"
      "文档 commit，不是本轮改动）" % (COMMIT, r.stdout.decode("utf-8").split()))

print()
print("=== ① 剥 docstring 后逐顶层单元比（代码基线 %s）===" % COMMIT)
summary = {}
for rel in FILES:
    b, w = units(base(rel)), units(work(rel))
    names_u = list(dict.fromkeys(list(b) + list(w)))
    changed = []
    print("--- %s ---" % rel)
    for n in names_u:
        if n not in b:
            tag = "NEW      "
            changed.append(n)
        elif n not in w:
            tag = "DELETED  "
            changed.append(n)
        elif b[n] != w[n]:
            tag = "AST 变了 "
            changed.append(n)
        else:
            tag = "未动     "
        print("   %s %s" % (tag, n))
    print("   → 有差异的顶层单元 = %s" % changed)
    assert changed == EXPECT[rel], (rel, changed, EXPECT[rel])
    summary[rel] = changed

print()
print("=== ② docstring 变了哪些（只列名字与增删行数，正文太长）===")
for rel in FILES:
    d0, d1 = docs(base(rel)), docs(work(rel))
    print("--- %s ---" % rel)
    assert set(d0) == set(d1), rel
    for n in d0:
        if d0[n] != d1.get(n):
            a = len(d0[n].splitlines())
            b_ = len(d1[n].splitlines())
            print("   %-46s docstring 变了：%d 行 -> %d 行" % (n, a, b_))
        else:
            print("   %-46s 未动" % n)

print()
print("=== ③ 注释全量清点（AST 看不见注释，这是 ① 的盲区，单独交代）===")
for rel in FILES:
    c0, c1 = comments(base(rel)), comments(work(rel))
    diff = list(difflib.unified_diff(c0, c1, "基线", "工作树", lineterm="", n=0))
    print("--- %s ---  注释条数 %d -> %d" % (rel, len(c0), len(c1)))
    for l in diff:
        print("   " + l[:170])

print()
print("=== ④ 既有 5 条守卫 assert 逐字未动 ===")
PAIRS = [(FILES[0], "test_domain_imports_stay_within_the_allow_list"),
         (FILES[0], "test_domain_has_no_clock_or_file_access"),
         (FILES[0], "test_domain_has_no_filesystem_access"),
         (FILES[1], "test_production_layers_never_import_app_seed")]
total = 0
for rel, fn in PAIRS:
    a0, a1 = asserts_of(base(rel), fn), asserts_of(work(rel), fn)
    total += len(a1)
    print("   %-24s %-46s assert %d→%d 逐字相同=%s"
          % (pathlib.Path(rel).name, fn, len(a0), len(a1), a0 == a1))
    assert a0 == a1, (rel, fn)
print("   既有守卫 assert 合计 %d 条，全部逐字未动" % total)
assert total == 5, total
print("   新测试里的 assert 条数：%s"
      % {pathlib.Path(rel).name: len(asserts_of(work(rel), CHANGED_UNIT))
         for rel in FILES[:2]})
print("   新测试里的 assert 与基线逐字相同？%s"
      % {pathlib.Path(rel).name:
         asserts_of(base(rel), CHANGED_UNIT) == asserts_of(work(rel), CHANGED_UNIT)
         for rel in FILES[:2]})

print()
print("=== ⑤ 硬规矩 #51：两份 _package_of / _absolute 仍逐字相同（剥 docstring）===")


def fn_dump(src, fnname):
    tree = strip_docs(ast.parse(norm(src)))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return ast.dump(node, include_attributes=False)
    return None


for fnname in ("_package_of", "_absolute", "_imported_modules"):
    a = fn_dump(work(FILES[0]), fnname)
    b = fn_dump(work(FILES[1]), fnname)
    if fnname == "_imported_modules":
        print("   %-18s 两份**故意不同**（purity 版 yield 4 元、layering 版 yield 2 元）= %s"
              % (fnname, a != b))
        assert a != b
    else:
        print("   %-18s 两份 identical(excl docstring) = %s" % (fnname, a == b))
        assert a == b, fnname
    for rel in FILES[:2]:
        same = fn_dump(base(rel), fnname) == fn_dump(work(rel), fnname)
        print("   %-18s %-24s 与基线逐字相同 = %s" % ("", pathlib.Path(rel).name, same))
        assert same, (rel, fnname)

print()
print("=== ⑥ 对照组（硬规矩 #53）：尺子必须能报 DIFF、能报 SAME、真的剥 docstring、对注释是盲的 ===")
MUT_OLD = "    anchor = package[: len(package) - (level - 1)]\n"
MUT_NEW = "    anchor = package[: len(package) - level]\n"
CELL_OLD = '        ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN"),\n'
CELL_NEW = '        ("indicators", 2, ("app", "domain", "prescription"), "X", "RED"),\n'
for rel in FILES[:2]:
    w_src = work(rel)
    w_u = units(w_src)
    assert w_src.count(MUT_OLD) == 1 and w_src.count(CELL_OLD) == 1, rel
    sem = units(w_src.replace(MUT_OLD, MUT_NEW))
    cell = units(w_src.replace(CELL_OLD, CELL_NEW))
    self_c = units(w_src)
    print("   %-24s ① 注入 _absolute 语义变异 → 报 DIFF 的单元 = %s"
          % (pathlib.Path(rel).name, [n for n in w_u if w_u[n] != sem.get(n)]))
    print("   %-24s ② 只把新格期望颜色 GREEN→RED → 报 DIFF 的单元 = %s"
          % ("", [n for n in w_u if w_u[n] != cell.get(n)]))
    print("   %-24s ③ 工作树自比 → 报 DIFF 的单元 = %s" % ("", [n for n in w_u if w_u[n] != self_c[n]]))
    assert [n for n in w_u if w_u[n] != sem.get(n)] == ["_absolute"]
    assert [n for n in w_u if w_u[n] != cell.get(n)] == [CHANGED_UNIT]
    assert [n for n in w_u if w_u[n] != self_c[n]] == []
    # 只改 docstring：不剥时报 DIFF、剥掉后不报
    d0 = docs(w_src)
    key = [k for k in d0 if k == CHANGED_UNIT][0]
    doc_mut = w_src.replace("（硬规矩 #50：只放红档会得到一条过紧的守卫）",
                            "（硬规矩 #50：只放红档会得到一条过紧的守卫。 ）")
    assert doc_mut != w_src, rel
    raw = ast.dump(ast.parse(norm(w_src))) != ast.dump(ast.parse(norm(doc_mut)))
    stripped = [n for n in w_u if w_u[n] != units(doc_mut).get(n)]
    print("   %-24s ④ 只改 docstring 一个字符：不剥时 DIFF=%s（须 True）、剥掉后=%s（须 []）"
          % ("", raw, stripped))
    assert raw is True and stripped == []
    # 只改注释：AST 全盲
    com_mut = w_src.replace("        # 越界档：resolve_name 抛 ImportError",
                            "        # 越界档（fr5）：resolve_name 抛 ImportError")
    assert com_mut != w_src, rel
    raw_c = ast.dump(ast.parse(norm(w_src))) != ast.dump(ast.parse(norm(com_mut)))
    stripped_c = [n for n in w_u if w_u[n] != units(com_mut).get(n)]
    print("   %-24s ⑤ 只改一行**注释**：AST 报 DIFF=%s、逐单元报 DIFF=%s → 尺子对注释是**盲的**"
          % ("", raw_c, stripped_c))
    assert raw_c is False and stripped_c == []

print()
print("硬规矩 #32 闸门（fix round 5 形态）: PASS")
print("有差异的顶层单元清单 = %s" % {pathlib.Path(k).name: v for k, v in summary.items()})
