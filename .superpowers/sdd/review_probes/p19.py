# -*- coding: utf-8 -*-
"""Probe P19: 五条既有守卫 assert 在 fix 链里是否被改动（派单/账本 :468 的判据）。"""
import ast, pathlib, subprocess
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]
GUARD_TESTS = {
    "test_domain_imports_stay_within_the_allow_list",
    "test_domain_has_no_clock_or_file_access",
    "test_domain_has_no_filesystem_access",
    "test_production_layers_never_import_app_seed",
}


def asserts(src):
    t = ast.parse(src)
    out = []
    for n in t.body:
        if isinstance(n, ast.FunctionDef) and n.name in GUARD_TESTS:
            for x in ast.walk(n):
                if isinstance(x, ast.Assert):
                    out.append((n.name, x.lineno, ast.unparse(x)))
    return out


for rel in FILES:
    wt = (ROOT / rel).read_text(encoding="utf-8")
    bl = subprocess.run(["git", "-C", str(ROOT), "show", "ad1d190:" + rel],
                        capture_output=True).stdout.decode("utf-8")
    a, b = asserts(wt), asserts(bl)
    print("=== %s ===" % rel.split("/")[-1])
    print("  基线 ad1d190: %d 条守卫 assert ; HEAD: %d 条" % (len(b), len(a)))
    sa = [x[2] for x in a]; sb = [x[2] for x in b]
    print("  文本集合相等 = %s" % (sa == sb))
    for name, ln, txt in a:
        mark = "OK(与基线逐字同)" if txt in sb else "!! 与基线不同 !!"
        print("    %s:%d  %-46s %s" % (name[:22], ln, txt[:46].replace("\n", " "), mark))
    for name, ln, txt in b:
        if txt not in sa:
            print("    基线独有(已消失): %s:%d %s" % (name[:22], ln, txt[:70]))

print("\n=== 新测试里的 assert 条数（每份）===")
for rel in FILES:
    t = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    fn = next(n for n in t.body if isinstance(n, ast.FunctionDef)
              and n.name == "test_absolute_folding_matches_resolve_name")
    print("  %-24s %d 条" % (rel.split("/")[-1], sum(1 for x in ast.walk(fn) if isinstance(x, ast.Assert))))
