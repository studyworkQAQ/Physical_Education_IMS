# -*- coding: utf-8 -*-
"""pe_fr4_precheck.py — fix round 4 开工预检（Ruling 54 / 55 的事实核）。

用法: python pe_fr4_precheck.py <仓库根>

核四件事：
  ① 派单点名的 4 个路径形状，_package_of 的实跑值（两个文件各一份，必须一致）
  ② 两个 _package_of docstring 里举的例子是否都是真跑过的输出（硬规矩 #52）
  ③ 「_package_of 返回模块路径」这个变异下，两条守卫各自折成什么串、判定是什么颜色
     —— 顺带核 purity 侧 _absolute docstring :139 那句「折成 app.domain.seed.generate」
  ④ 两个文件里 test_* 的个数 与 模块 docstring 的计数陈述（Ruling 55 的落点）
"""
import ast
import importlib.util
import pathlib
import re
import sys
import types

REPO = pathlib.Path(sys.argv[1]).resolve()
BACKEND = REPO / "backend"
FILES = {
    "purity": BACKEND / "tests/architecture/test_domain_purity.py",
    "layering": BACKEND / "tests/architecture/test_layering.py",
}


def load(tag, mutated=False):
    """在内存里 exec 守卫源码，__file__ 仍指向原位置（BACKEND 是从 __file__ 推的，
    故不能把副本落到别处再 import —— 那会让 parents[2] 指到仓库外）。"""
    src = FILES[tag].read_text(encoding="utf-8")
    if mutated:
        old = 'return py.relative_to(BACKEND).with_suffix("").parts[:-1]'
        new = 'return py.relative_to(BACKEND).with_suffix("").parts'
        assert src.count(old) == 1, (tag, src.count(old))
        src = src.replace(old, new)
    real = str(FILES[tag].resolve())
    ns = {"__file__": real, "__name__": "_fr4_%s%s" % (tag, "mut" if mutated else "")}
    exec(compile(src.replace("\r\n", "\n"), real, "exec"), ns)
    return types.SimpleNamespace(**ns)


SHAPES = [
    "app/db/models/organisation.py",
    "app/db/models/__init__.py",
    "app/domain/indicators.py",
    "app/domain/prescription/match.py",   # Task 2 才会出现
]
DOC_EXAMPLES = [
    "app/domain/x.py", "app/domain/sub/x.py",          # purity 侧 docstring 举的
    "app/pipeline/x.py", "app/db/models/x.py",          # layering 侧 docstring 举的
]

print("=== ① 派单点名的 4 个形状（两份 _package_of 必须给出同一个值）===")
mods = {t: load(t) for t in FILES}
for t in mods:
    print("  %-9s BACKEND = %s  is_dir=%s" % (t, mods[t].BACKEND, mods[t].BACKEND.is_dir()))
for rel in SHAPES:
    vals = {t: mods[t]._package_of(mods[t].BACKEND / rel) for t in FILES}
    same = len(set(vals.values())) == 1
    print("  exists=%-5s %-36s purity=%-34s layering=%-34s 两份一致=%s"
          % ((mods["purity"].BACKEND / rel).exists(), rel,
             vals["purity"], vals["layering"], same))
    assert same

print()
print("=== ② 两个 _package_of docstring 里的举例，是否都是真跑过的输出（硬规矩 #52）===")
WANT = {
    "app/domain/x.py": ("app", "domain"),
    "app/domain/sub/x.py": ("app", "domain", "sub"),
    "app/pipeline/x.py": ("app", "pipeline"),
    "app/db/models/x.py": ("app", "db", "models"),
    "app/db/models/__init__.py": ("app", "db", "models"),
}
for rel, want in WANT.items():
    for t in FILES:
        got = mods[t]._package_of(mods[t].BACKEND / rel)
        print("  %-9s %-30s -> %-32s docstring 写的=%-30s 相符=%s"
              % (t, rel, got, want, got == want))

print()
print("=== ③ 「_package_of 返回模块路径」变异下，两条守卫折成什么、判什么颜色 ===")
muts = {t: load(t, mutated=True) for t in FILES}


def fold(mod, tag, rel, module, level, name):
    """模拟守卫：对 rel 这个源文件里的一句 ImportFrom 折算 + 判定。"""
    pkg = mod._package_of(mod.BACKEND / rel)
    got = mod._absolute(module, level, pkg, name)
    if tag == "purity":
        verdict = "RED" if got is None or not mod._is_allowed(got) else "GREEN"
    else:
        verdict = "RED" if got is None or mod._is_forbidden(got) else "GREEN"
    return pkg, got, verdict


CASES = [
    # (源文件, ImportFrom 的 module/level/name, 派单/docstring 声称的折算串)
    ("app/domain/x.py", ("seed", 2, ""), "app.domain.seed.generate（purity _absolute docstring 这么说）"),
    ("app/db/models/x.py", ("seed", 3, ""), "app.db.seed（layering _absolute docstring 这么说）"),
]
for rel, (module, level, name), claim in CASES:
    print("  源文件 %s   from %s%s import %s" % (rel, "." * level, module, name or "…"))
    print("    docstring 的声称: %s" % claim)
    for tag, mod, mut in (("purity", mods["purity"], muts["purity"]),
                          ("layering", mods["layering"], muts["layering"])):
        p0, g0, v0 = fold(mod, tag, rel, module, level, name)
        p1, g1, v1 = fold(mut, tag, rel, module, level, name)
        print("    %-9s 正常: pkg=%-28s folded=%-22s %s" % (tag, p0, g0, v0))
        print("    %-9s 变异: pkg=%-28s folded=%-22s %s" % ("", p1, g1, v1))
    try:
        rn = importlib.util.resolve_name("." * level + module, ".".join(
            mods["purity"]._package_of(mods["purity"].BACKEND / rel)))
    except ImportError as e:
        rn = "ImportError: %s" % e
    print("    resolve_name（正常包）= %r" % rn)

print()
print("=== ④ test_* 个数 与 模块 docstring 里的计数陈述（Ruling 55）===")
for t in FILES:
    src = FILES[t].read_text(encoding="utf-8")
    tree = ast.parse(src.replace("\r\n", "\n"))
    tests = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    moddoc = ast.get_docstring(tree) or ""
    print("  %-9s test_* 个数 = %d  %s" % (t, len(tests), tests))
    for i, l in enumerate(moddoc.splitlines(), 1):
        if re.search(r"[一二三四五六七八九十]+\s*条|[一二三四五六七八九十]+\s*道|本守卫|三条|两条", l):
            print("      模块 docstring 第 %d 行: %s" % (i, l.strip()))
