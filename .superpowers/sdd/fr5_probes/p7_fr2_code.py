"""P7 — fix round 2（1fa9941）到底改了哪几处**代码**（不是散文）。"""
import subprocess, pathlib, ast

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]


def src_at(sha, path):
    r = subprocess.run(["git", "show", "%s:%s" % (sha, path)], cwd=ROOT,
                       capture_output=True)
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


for path in FILES:
    print("### %s" % path)
    before = ast.parse(src_at("1fa9941^", path))
    after = ast.parse(src_at("1fa9941", path))

    def funcs(tree):
        return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    fb, fa = funcs(before), funcs(after)
    for name in sorted(set(fb) | set(fa)):
        if name not in fb:
            print("   + 新增函数 %s" % name)
            continue
        if name not in fa:
            print("   - 删除函数 %s" % name)
            continue
        db = ast.dump(ast.parse("pass"))  # placeholder
        # 剥掉 docstring 后比
        def strip(fn):
            import copy
            g = copy.deepcopy(fn)
            if (g.body and isinstance(g.body[0], ast.Expr)
                    and isinstance(g.body[0].value, ast.Constant)
                    and isinstance(g.body[0].value.value, str)):
                g.body = g.body[1:]
            return ast.dump(g)
        if strip(fb[name]) != strip(fa[name]):
            print("   * 函数 %s 的**代码**变了" % name)
            sb = src_at("1fa9941^", path).splitlines()[fb[name].lineno - 1:fb[name].end_lineno]
            sa = src_at("1fa9941", path).splitlines()[fa[name].lineno - 1:fa[name].end_lineno]
            import difflib
            for l in difflib.unified_diff(sb, sa, "before", "after", lineterm="", n=1):
                if l.startswith(("+", "-", "@")) and not l.startswith(("+++", "---")):
                    print("       %s" % l[:140])
        else:
            pass
    print()
