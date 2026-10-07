# -*- coding: utf-8 -*-
"""pe_fr4_astdiff.py — 硬规矩 #32 的 fix round 4 形态：改动面自证（基线 be0f1af）。

用法: python pe_fr4_astdiff.py <仓库根>

本轮**没有新增顶层单元**（派单钉死 passed 数不变），故自证的形状是：
  ⓪ git diff --name-only / --numstat（禁区：backend/app/** 命中必须 0）
  ① 剥 docstring 后逐顶层单元比 —— 有差异的单元必须恰好是
     ['test_absolute_folding_matches_resolve_name']（两个文件各一）
  ② docstring 全量清点：哪些函数的 docstring 变了、变成什么（unified diff）
  ③ **注释**全量清点（AST 看不见注释，这是 ① 的盲区，必须单独交代）
  ④ 既有 5 条守卫 assert 逐字未动
  ⑤ 硬规矩 #51：两份 _package_of / _absolute 仍逐字相同（剥 docstring）
  ⑥ 对照组（硬规矩 #53）：尺子必须能报 DIFF、能报 SAME、真的剥 docstring、
     并且**明确暴露它对注释是盲的**

基线用 `git show be0f1af:<path>` 取到内存（不落盘、不 checkout）。
⚠️ 账本记的坑：`git show` 给的是 blob 的 LF 版，故比较前一律归一化成 LF。
"""
import ast
import difflib
import io
import pathlib
import subprocess
import sys
import tokenize

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMIT = "be0f1af"
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]
CHANGED_UNIT = "test_absolute_folding_matches_resolve_name"


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
    r = subprocess.run(["git", "show", "%s:%s" % (COMMIT, rel)], cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, rel
    return r.stdout.decode("utf-8")


def work(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def docs(src):
    """{单元名: docstring}；模块本身记作 <module>。"""
    tree = ast.parse(norm(src))
    out = {"<module>": ast.get_docstring(tree) or ""}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.get_docstring(node) or ""
    return out


def comments(src):
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(norm(src)).readline):
        if tok.type == tokenize.COMMENT:
            out.append(tok.string)
    return out


def asserts_of(src, fnname):
    tree = ast.parse(norm(src))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return [ast.dump(a, include_attributes=False) for a in ast.walk(node)
                    if isinstance(a, ast.Assert)]
    return []


print("=== ⓪ 改动面 ===")
# HEAD = 73313f7（只比 be0f1af 多一个 Document/ 的文档 commit，两个守卫文件自 be0f1af 起未变）
# 故「本轮的工作树改动面」对 HEAD 比，「代码基线」对 be0f1af 比。
GIT = ["git", "-c", "core.quotepath=false"]
r = subprocess.run(GIT + ["diff", "--name-only", "HEAD"], cwd=str(REPO), capture_output=True)
names = r.stdout.decode("utf-8").split()
print("   git diff --name-only HEAD(%s):" % subprocess.run(
    GIT + ["rev-parse", "--short", "HEAD"], cwd=str(REPO), capture_output=True
).stdout.decode().strip())
for n in names:
    print("     ", n)
print("   合计 %d 个文件；生产代码（backend/app/**）命中 = %d"
      % (len(names), sum(1 for n in names if n.startswith("backend/app/"))))
assert set(names) <= set(FILES), names
assert not any(n.startswith("backend/app/") for n in names)
print("   git diff --numstat HEAD:")
r = subprocess.run(GIT + ["diff", "--numstat", "HEAD"], cwd=str(REPO), capture_output=True)
for l in r.stdout.decode("utf-8").splitlines():
    print("     ", l)
r = subprocess.run(GIT + ["diff", "--name-only", COMMIT, "--", "backend/"],
                   cwd=str(REPO), capture_output=True)
bnames = r.stdout.decode("utf-8").split()
print("   git diff --name-only %s -- backend/ = %s" % (COMMIT, bnames))
assert set(bnames) <= set(FILES), bnames
r = subprocess.run(GIT + ["diff", "--name-only", COMMIT, "--", "backend/app/"],
                   cwd=str(REPO), capture_output=True)
print("   git diff --name-only %s -- backend/app/ = %r（禁区，必须空）"
      % (COMMIT, r.stdout.decode("utf-8").split()))
assert r.stdout.decode("utf-8").split() == []
print("   git status --short:")
r = subprocess.run(GIT + ["status", "--short"], cwd=str(REPO), capture_output=True)
for l in r.stdout.decode("utf-8").splitlines():
    print("     ", l)

print()
print("=== ① 剥 docstring 后逐顶层单元比（基线 %s）===" % COMMIT)
summary = {}
for rel in FILES:
    b, w = units(base(rel)), units(work(rel))
    names_u = list(dict.fromkeys(list(b) + list(w)))
    changed = []
    print("--- %s ---" % rel)
    for n in names_u:
        if n not in b:
            tag, _ = "NEW      ", changed.append(n)
        elif n not in w:
            tag, _ = "DELETED  ", changed.append(n)
        elif b[n] != w[n]:
            tag, _ = "AST 变了 ", changed.append(n)
        else:
            tag = "未动     "
        print("   %s %s" % (tag, n))
    print("   → 有差异的顶层单元 = %s" % changed)
    assert changed == [CHANGED_UNIT], (rel, changed)
    assert CHANGED_UNIT in b and CHANGED_UNIT in w, rel
    summary[rel] = changed

print()
print("=== ② docstring 全量清点（哪些变了、变成什么）===")
for rel in FILES:
    d0, d1 = docs(base(rel)), docs(work(rel))
    print("--- %s ---" % rel)
    for n in d0:
        same = d0[n] == d1.get(n)
        print("   %-46s %s" % (n, "未动" if same else "变了 ↓"))
        if not same:
            for l in difflib.unified_diff((d0[n] or "").splitlines(), (d1.get(n) or "").splitlines(),
                                          "基线/" + n, "工作树/" + n, lineterm="", n=1):
                print("      " + l)
    assert set(d0) == set(d1), rel

print()
print("=== ③ 注释全量清点（AST 看不见注释，这是 ① 的盲区，单独交代）===")
for rel in FILES:
    c0, c1 = comments(base(rel)), comments(work(rel))
    diff = list(difflib.unified_diff(c0, c1, "基线", "工作树", lineterm="", n=0))
    print("--- %s ---  注释条数 %d -> %d" % (rel, len(c0), len(c1)))
    for l in diff:
        print("   " + l[:160])

print()
print("=== ④ 既有 5 条守卫 assert 逐字对比 ===")
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
      % {pathlib.Path(rel).name: len(asserts_of(work(rel), CHANGED_UNIT)) for rel in FILES})

print()
print("=== ⑤ 硬规矩 #51：两份 _package_of / _absolute 仍逐字相同（剥 docstring）===")


def fn_dump(src, fnname):
    tree = strip_docs(ast.parse(norm(src)))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return ast.dump(node, include_attributes=False)
    return None


for fnname in ("_package_of", "_absolute"):
    a = fn_dump(work(FILES[0]), fnname)
    b = fn_dump(work(FILES[1]), fnname)
    print("   %-14s 两份 identical(excl docstring) = %s" % (fnname, a == b))
    assert a == b, fnname
    for rel in FILES:
        same = fn_dump(base(rel), fnname) == fn_dump(work(rel), fnname)
        print("   %-14s %-24s 与基线逐字相同 = %s" % ("", pathlib.Path(rel).name, same))
        assert same, (rel, fnname)

print()
print("=== ⑥ 对照组（硬规矩 #53）===")
MUT_OLD = 'return py.relative_to(BACKEND).with_suffix("").parts[:-1]'
MUT_NEW = 'return py.relative_to(BACKEND).with_suffix("").parts'
DOC_OLD = "``py`` 所在的**包**，以 ``backend/`` 为根的段。"
DOC_NEW = "``py`` 所在的**包**（以 ``backend/`` 为根的段）。"
COM_OLD = "    # ---------------------------------------------------------------- Ruling 54"
COM_NEW = "    # ---------------------------------------------------------------- Ruling 54 (fr4)"

for rel in FILES:
    b_src = base(rel)
    w_u = units(b_src)
    assert b_src.count(MUT_OLD) == 1 and b_src.count(DOC_OLD) == 1, rel
    sem = units(b_src.replace(MUT_OLD, MUT_NEW))
    self_c = units(b_src)
    doc = units(b_src.replace(DOC_OLD, DOC_NEW))
    w_src = work(rel)
    assert w_src.count(COM_OLD) == 1, rel
    com = units(w_src.replace(COM_OLD, COM_NEW))
    w_u2 = units(w_src)
    raw_doc_diff = (ast.dump(ast.parse(norm(b_src))) != ast.dump(ast.parse(norm(b_src.replace(DOC_OLD, DOC_NEW)))))
    raw_com_diff = (ast.dump(ast.parse(norm(w_src))) != ast.dump(ast.parse(norm(w_src.replace(COM_OLD, COM_NEW)))))
    print("   %-24s ① 注入 _package_of 语义变异 → 报 DIFF 的单元 = %s"
          % (pathlib.Path(rel).name, [n for n in w_u if w_u[n] != sem.get(n)]))
    print("   %-24s ② 基线自比 → 报 DIFF 的单元 = %s"
          % ("", [n for n in w_u if w_u[n] != self_c[n]]))
    print("   %-24s ③ 只改 _package_of 的 docstring：不剥时报 DIFF=%s（须 True）、剥掉后=%s（须 []）"
          % ("", raw_doc_diff, [n for n in w_u if w_u[n] != doc.get(n)]))
    print("   %-24s ④ 只改一行**注释**：AST 报 DIFF=%s、逐单元报 DIFF=%s → 尺子对注释是**盲的**"
          % ("", raw_com_diff, [n for n in w_u2 if w_u2[n] != com.get(n)]))
    assert [n for n in w_u if w_u[n] != sem.get(n)] == ["_package_of"]
    assert [n for n in w_u if w_u[n] != self_c[n]] == []
    assert raw_doc_diff is True
    assert [n for n in w_u if w_u[n] != doc.get(n)] == []
    assert raw_com_diff is False
    assert [n for n in w_u2 if w_u2[n] != com.get(n)] == []

print()
print("硬规矩 #32 闸门（fix round 4 形态）: PASS")
print("有差异的顶层单元清单 = %s" % summary)
