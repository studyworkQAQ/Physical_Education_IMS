# -*- coding: utf-8 -*-
"""pe_fr3_matrix.py — Ruling 46 的判据复核：把两份 _absolute 与 importlib.util.resolve_name 对拍。

用法: python pe_fr3_matrix.py <仓库根>
矩阵以 (module, level, package, name) 四元组为参数（Ruling 45：不用「from … 的字面写法」当唯一标识）。
本脚本只读、不落盘、不碰禁区。
"""
import importlib.util
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
BACKEND = REPO / "backend"

FILES = {
    "purity": BACKEND / "tests/architecture/test_domain_purity.py",
    "layering": BACKEND / "tests/architecture/test_layering.py",
}


def load(tag, path):
    spec = importlib.util.spec_from_file_location("fr3_guard_%s" % tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GUARDS = {tag: load(tag, p) for tag, p in FILES.items()}

# (标签, module, level, package, name, 期望折算串或 None)
MATRIX = [
    ("A level==0 绝对导入",            "app.seed.generate", 0, ("app", "domain"),        "",          None),
    ("B1 level==1 包内合法(module)",   "tables",            1, ("app", "domain"),        "",          None),
    ("B2 level==1 包内合法(name)",     "",                  1, ("app", "db", "models"),  "_shared",   None),
    ("C  真 offender",                 "seed.generate",     2, ("app", "pipeline"),      "",          None),
    ("D1 module 为空 @pipeline",       "",                  2, ("app", "pipeline"),      "seed",      None),
    ("D2 module 为空 @db",             "",                  2, ("app", "db"),            "seed",      None),
    ("D3 module 为空 @db.models",      "",                  2, ("app", "db", "models"),  "seed",      None),
    ("D4 module 为空 @domain",         "",                  2, ("app", "domain"),        "seed",      None),
    ("E1 越界 level5 @db.models",      "seed",              5, ("app", "db", "models"),  "generate",  None),
    ("E2 越界 level4 @domain",         "domain",            4, ("app", "domain"),        "tables",    None),
    ("F1 level==1 越界？(边界) ",      "",                  1, ("app",),                 "seed",      None),
    ("F2 level==len+1 (恰好到 app 之上)", "seed",           3, ("app", "domain"),        "generate",  None),
    ("F3 level==len (恰好 anchor 空)", "seed",              3, ("app", "db", "models"),  "generate",  None),
]


def rn(module, level, package, name):
    rel = "." * level + (module or name)
    pkg = ".".join(package)
    try:
        return importlib.util.resolve_name(rel, pkg), None
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


print("=== resolve_name 直连（本机 %s） ===" % sys.version.split()[0])
print("%-34s %-22s %-16s %s" % ("形状", "resolve_name(rel,pkg)", "异常", "_absolute(purity/layering)"))
rows = []
for label, module, level, package, name, _ in MATRIX:
    val, err = rn(module, level, package, name)
    got = {tag: g._absolute(module, level, package, name) for tag, g in GUARDS.items()}
    same_two = got["purity"] == got["layering"]
    if err:
        match = got["purity"] is None
    else:
        match = got["purity"] == val
    rows.append((label, val, err, got, match, same_two))
    print("%-34s %-22s %-16s %-22s match=%s 两份相同=%s"
          % (label, repr(val) if val is not None else "-", err or "-",
             repr(got["purity"]), match, same_two))

print()
print("=== 逐格结论 ===")
bad = [r for r in rows if not (r[4] and r[5])]
for r in rows:
    print("  %-34s %s" % (r[0], "OK" if (r[4] and r[5]) else "!! MISMATCH"))
print("MISMATCH 格数 = %d / %d" % (len(bad), len(rows)))
print()
print("=== 判定颜色（各自的守卫判据） ===")
for label, module, level, package, name, _ in MATRIX:
    p = GUARDS["purity"]
    lay = GUARDS["layering"]
    ab = p._absolute(module, level, package, name)
    if ab is None:
        pcol = lcol = "RED"
    else:
        pcol = "GREEN" if p._is_allowed(ab) else "RED"
        lcol = "RED" if lay._is_forbidden(ab) else "GREEN"
    print("  %-34s 折算=%-24s purity=%-5s layering=%s" % (label, repr(ab), pcol, lcol))
