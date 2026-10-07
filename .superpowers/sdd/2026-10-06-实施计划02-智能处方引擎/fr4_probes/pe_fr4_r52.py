# -*- coding: utf-8 -*-
"""pe_fr4_r52.py — 硬规矩 #52：本轮写进 docstring / 断言消息的每一个值都真跑一遍。

用法: python pe_fr4_r52.py <仓库根>
"""
import pathlib
import sys
import types

REPO = pathlib.Path(sys.argv[1]).resolve()
FILES = {
    "purity": REPO / "backend/tests/architecture/test_domain_purity.py",
    "layering": REPO / "backend/tests/architecture/test_layering.py",
}


def load(path):
    src = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    real = str(path.resolve())
    ns = {"__file__": real, "__name__": "_probe"}
    exec(compile(src, real, "exec"), ns)
    return types.SimpleNamespace(**ns)


pu = load(FILES["purity"])
la = load(FILES["layering"])

print("=== purity _absolute docstring 里本轮新写的那两个值 ===")
got = pu._absolute("seed", 2, ("app", "domain", "ind"))
allowed = pu._is_allowed("app.domain.seed")
print('  _absolute("seed", 2, ("app", "domain", "ind")) -> %r   （docstring 写的 %r）相符=%s'
      % (got, "app.domain.seed", got == "app.domain.seed"))
print("  _is_allowed('app.domain.seed')                 -> %r   （docstring 写的 True）相符=%s"
      % (allowed, allowed is True))
assert got == "app.domain.seed" and allowed is True

print()
print("=== 两个断言消息里写的 4 个折算串 ===")
ROWS = [
    ("purity", "app/domain/x.py", "seed", 2, "app.domain.seed", "命中白名单前缀 app.domain."),
    ("layering", "app/db/models/x.py", "seed", 3, "app.db.seed", "不再以 app.seed 开头"),
]
for tag, rel, module, level, claim, why in ROWS:
    m = pu if tag == "purity" else la
    pkg = ("app", "domain", "x") if level == 2 else ("app", "db", "models", "x")
    got = m._absolute(module, level, pkg)
    if tag == "purity":
        verdict = "RED" if got is None or not m._is_allowed(got) else "GREEN"
    else:
        verdict = "RED" if got is None or m._is_forbidden(got) else "GREEN"
    print("  %-9s %-22s from %s%s import …  pkg=%-30s folded=%-18s %s  声称=%r 相符=%s"
          % (tag, rel, "." * level, module, pkg, got, verdict, claim, got == claim))
    assert got == claim, (tag, got, claim)
    assert verdict == "GREEN", (tag, verdict)   # 声称的都是「假绿」，故必须是 GREEN
print("  （why 列：%s）" % "；".join(r[5] for r in ROWS))

print()
print("=== layering _absolute docstring 原有的那句（本轮未改，复核仍成立）===")
got = la._absolute("seed", 3, ("app", "db", "models", "x"))
print("  _absolute('seed', 3, ('app','db','models','x')) -> %r  _is_forbidden=%r  相符=%s"
      % (got, la._is_forbidden(got), got == "app.db.seed" and not la._is_forbidden(got)))
assert got == "app.db.seed" and not la._is_forbidden(got)

print()
print("硬规矩 #52 复核: PASS")
