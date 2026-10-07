# -*- coding: utf-8 -*-
"""pe_fr3_astdiff.py — 硬规矩 #32 的本轮形态：逐顶层单元比基线，证明改动面只有
「新增的那一条测试函数」+「_absolute docstring 的一处机制更正（Ruling 42）」。

用法: python pe_fr3_astdiff.py <仓库根>

带三组对照（硬规矩 #53）：
  ① 尺子必须能报 DIFF：把 m2（删掉越界守卫）注入**基线文本的内存副本**，逐单元比必须报 _absolute 变了
  ② 尺子必须能报 SAME：基线跟自己比，全部单元必须「未动」
  ③ 尺子真的剥掉了 docstring：只改 docstring 的内存副本，逐单元比必须全「未动」
"""
import ast
import difflib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMIT = "1fa9941"
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]
NEW_FUNC = "test_absolute_folding_matches_resolve_name"


def strip(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = [ast.Pass()] + b[1:]
    return tree


def units(src):
    tree = strip(ast.parse(src.replace("\r\n", "\n")))
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


def doc_of(src, fnname):
    tree = ast.parse(src.replace("\r\n", "\n"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return ast.get_docstring(node) or ""
    return None


def report(rel, b_src, w_src, expect_new):
    b, w = units(b_src), units(w_src)
    names = list(dict.fromkeys(list(b) + list(w)))
    changed = []
    print("=== %s ===" % rel)
    for n in names:
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
    if expect_new:
        assert changed == [NEW_FUNC], (rel, changed)
        assert NEW_FUNC in w and NEW_FUNC not in b
    return changed


print("=== ⓪ 改动面：git diff --name-only %s..工作树 ===" % COMMIT)
r = subprocess.run(["git", "diff", "--name-only", COMMIT], cwd=str(REPO), capture_output=True)
names = r.stdout.decode("utf-8").split()
for n in names:
    print("   ", n)
print("   合计 %d 个文件；生产代码（backend/app/**）命中 = %d"
      % (len(names), sum(1 for n in names if n.startswith("backend/app/"))))
assert set(names) <= set(FILES), names
assert not any(n.startswith("backend/app/") for n in names)
print("   git diff --numstat:")
r = subprocess.run(["git", "diff", "--numstat", COMMIT], cwd=str(REPO), capture_output=True)
for l in r.stdout.decode("utf-8").splitlines():
    print("     ", l)

print()
print("=== ① 两个守卫文件：工作树 vs 基线 %s（剥 docstring 后逐顶层单元比） ===" % COMMIT)
for rel in FILES:
    report(rel, base(rel), work(rel), expect_new=True)
    print()

print("=== ② _absolute 的 docstring 差异（Ruling 42 的唯一落点，purity 侧） ===")
rel = FILES[0]
d0 = doc_of(base(rel), "_absolute").splitlines()
d1 = doc_of(work(rel), "_absolute").splitlines()
diff = [l for l in difflib.unified_diff(d0, d1, "基线", "工作树", lineterm="", n=1)]
for l in diff:
    print("   ", l)
assert diff, "docstring 没有差异？Ruling 42 没落盘"
print("   layering 侧 _absolute docstring 逐字相同 = %s"
      % (doc_of(base(FILES[1]), "_absolute") == doc_of(work(FILES[1]), "_absolute")))
assert doc_of(base(FILES[1]), "_absolute") == doc_of(work(FILES[1]), "_absolute")

print()
print("=== ③ 既有 4 条 test_* 函数体里的 assert 逐字对比（剥 docstring 后） ===")


def asserts(src, fnname):
    tree = ast.parse(src.replace("\r\n", "\n"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fnname:
            return [ast.dump(a, include_attributes=False) for a in ast.walk(node)
                    if isinstance(a, ast.Assert)]
    return []


PAIRS = [(FILES[0], "test_domain_imports_stay_within_the_allow_list"),
         (FILES[0], "test_domain_has_no_clock_or_file_access"),
         (FILES[0], "test_domain_has_no_filesystem_access"),
         (FILES[1], "test_production_layers_never_import_app_seed")]
total = 0
for rel, fn in PAIRS:
    a1, a2 = asserts(base(rel), fn), asserts(work(rel), fn)
    total += len(a2)
    print("   %-24s %-46s assert %d→%d 逐字相同=%s"
          % (pathlib.Path(rel).name, fn, len(a1), len(a2), a1 == a2))
    assert a1 == a2, (rel, fn)
print("   既有 assert 合计 %d 条，全部逐字未动" % total)
assert total == 5, total

print()
print("=== 对照组（硬规矩 #53）：尺子必须既能报 DIFF、也能报 SAME、还真的剥 docstring ===")


def m2_drop_guard(src):
    lines = src.replace("\r\n", "\n").split("\n")
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "    if level - 1 > len(package):":
            hit += 1
            i += 3
            continue
        out.append(lines[i])
        i += 1
    assert hit == 1, hit
    return "\n".join(out)


DOC_OLD = "把 ``ast.ImportFrom`` 折算成**绝对模块串**"
DOC_NEW = "把 ``ast.ImportFrom`` 折算成**绝对的模块串**"


def docstring_only(src):
    """只改 _absolute docstring 里的一句话（两个文件里各命中恰 1 次）。"""
    assert src.count(DOC_OLD) == 1, src.count(DOC_OLD)
    return src.replace(DOC_OLD, DOC_NEW)


for rel in FILES:
    b_src = base(rel)
    mut = units(m2_drop_guard(b_src))
    same_ctrl = units(b_src)
    doc_src = docstring_only(b_src)
    doc_ctrl = units(doc_src)
    w = units(b_src)
    diff_hits = [n for n in w if n in mut and w[n] != mut[n]]
    self_hits = [n for n in w if n in same_ctrl and w[n] != same_ctrl[n]]
    doc_hits = [n for n in w if n in doc_ctrl and w[n] != doc_ctrl[n]]
    raw_diff = (ast.dump(ast.parse(b_src.replace("\r\n", "\n")), include_attributes=False)
                != ast.dump(ast.parse(doc_src.replace("\r\n", "\n")), include_attributes=False))
    print("   %-24s ① 注入语义变异后报 DIFF 的单元=%s  ② 自比报 DIFF=%s"
          % (pathlib.Path(rel).name, diff_hits, self_hits))
    print("   %-24s ③ 只改 docstring：不剥时报 DIFF=%s（必须 True）、剥掉后报 DIFF=%s（必须 []）"
          % ("", raw_diff, doc_hits))
    assert diff_hits == ["_absolute"], diff_hits
    assert self_hits == [], self_hits
    assert raw_diff is True, "不剥 docstring 时本该报 DIFF"
    assert doc_hits == [], doc_hits
    assert m2_drop_guard(b_src) != b_src and doc_src != b_src

print()
print("硬规矩 #32 闸门（本轮形态）: PASS")
