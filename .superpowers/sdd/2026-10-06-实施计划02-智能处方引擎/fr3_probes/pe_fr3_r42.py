# -*- coding: utf-8 -*-
"""pe_fr3_r42.py — Ruling 42 的实测取证：_is_allowed('app.domain') 命中的是哪一支。

用法: python pe_fr3_r42.py <仓库根>
"""
import importlib.util
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location(
    "fr3_purity", REPO / "backend/tests/architecture/test_domain_purity.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

print("ALLOWED_PACKAGE = %r" % p.ALLOWED_PACKAGE)
for m in ("app.domain", "app.domain.seed", "app.domain.seed.generate", "app.db.seed", "enum"):
    eq = m == p.ALLOWED_PACKAGE
    sw = m.startswith(p.ALLOWED_PACKAGE + ".")
    inmods = m in p.ALLOWED_MODULES
    print("  _is_allowed(%-26r) = %-5s | == ALLOWED_PACKAGE: %-5s | startswith(%r): %-5s | in ALLOWED_MODULES: %s"
          % (m, p._is_allowed(m), eq, p.ALLOWED_PACKAGE + ".", sw, inmods))

print()
print("=== Ruling 42 要写进 docstring 的两行（本机实跑） ===")
print('  "app.domain" == ALLOWED_PACKAGE                 ->', "app.domain" == p.ALLOWED_PACKAGE)
print('  "app.domain".startswith(ALLOWED_PACKAGE + ".")  ->', "app.domain".startswith(p.ALLOWED_PACKAGE + "."))
print('  "app.domain.seed.generate".startswith(ALLOWED_PACKAGE + ".") ->',
      "app.domain.seed.generate".startswith(p.ALLOWED_PACKAGE + "."), "  # :139 / :246 说的是这一档，正确、不动")
