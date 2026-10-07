# -*- coding: utf-8 -*-
"""pe_fr4_compose.py — 预演「把 _package_of 的输出喂给 _absolute」这一段断言的实跑值。

用法: python pe_fr4_compose.py <仓库根>
"""
import importlib.util
import pathlib
import sys
import types

REPO = pathlib.Path(sys.argv[1]).resolve()
FILES = {
    "purity": REPO / "backend/tests/architecture/test_domain_purity.py",
    "layering": REPO / "backend/tests/architecture/test_layering.py",
}
OLD = 'return py.relative_to(BACKEND).with_suffix("").parts[:-1]'
NEW = 'return py.relative_to(BACKEND).with_suffix("").parts'


def load(path, mutated=False):
    src = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if mutated:
        assert src.count(OLD) == 1, src.count(OLD)
        src = src.replace(OLD, NEW)
    real = str(path.resolve())
    ns = {"__file__": real, "__name__": "_probe"}
    exec(compile(src, real, "exec"), ns)
    return types.SimpleNamespace(**ns)


COMPOSE = [
    ("app/domain/indicators.py", 2, "seed", ("app", "domain")),
    ("app/db/models/organisation.py", 3, "seed", ("app", "db", "models")),
]

for tag, path in FILES.items():
    for mutated in (False, True):
        m = load(path, mutated)
        print("== %-9s _package_of 变异(parts[:-1] -> parts) = %s" % (tag, mutated))
        for rel, level, module, want_pkg in COMPOSE:
            rel_import = "." * level + module
            pkg_str = ".".join(want_pkg)
            pkg = m._package_of(m.BACKEND / rel)
            got = m._absolute(module, level, pkg)
            want = importlib.util.resolve_name(rel_import, pkg_str)
            if tag == "purity":
                verdict = "RED" if got is None or not m._is_allowed(got) else "GREEN"
            else:
                verdict = "RED" if got is None or m._is_forbidden(got) else "GREEN"
            print("   %-32s pkg=%-38s got=%-18s want=%-18s 相等=%-5s 判定=%s"
                  % (rel, pkg, got, want, got == want, verdict))
