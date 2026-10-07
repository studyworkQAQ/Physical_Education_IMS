# -*- coding: utf-8 -*-
"""pe_fr4_ruling42b.py — 核账本 Ruling 42 那句「`:139` 与 `:246` 说的是
`app.domain.seed.generate`（startswith 为 True，**正确**），只有 `:167` 是错的」。

用法: python pe_fr4_ruling42b.py <仓库根>

结论要看**动词**：
  * 老 `:139` 用的动词是「就会**折成**」——那是 :func:`_absolute` 的返回值，
    对 `from ..seed import generate` 实跑是 `app.domain.seed`（`generate` 住在
    ``node.names`` 里、不进折算串，Ruling 36）。故老 `:139` **错**，本轮已就近更正。
  * 老 `:246`（今 `:422`）用的动词是「**解析到**的是」——那是这句 import 语义上取到的
    对象，`resolve_name("..seed.generate", "app.domain.sub")` 实跑就是
    `app.domain.seed.generate`。故 `:246` **对**，本轮未动。
"""
import importlib.util
import pathlib
import sys
import types

REPO = pathlib.Path(sys.argv[1]).resolve()
P = REPO / "backend/tests/architecture/test_domain_purity.py"


def load(path):
    src = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    real = str(path.resolve())
    ns = {"__file__": real, "__name__": "_probe"}
    exec(compile(src, real, "exec"), ns)
    return types.SimpleNamespace(**ns)


pu = load(P)

print("=== ① 「折成」口径：_absolute 对 from ..seed import generate 的返回值 ===")
for pkg in (("app", "domain"), ("app", "domain", "sub"), ("app", "domain", "ind")):
    got = pu._absolute("seed", 2, pkg)
    rn = importlib.util.resolve_name("..seed", ".".join(pkg))
    print("  pkg=%-30s _absolute('seed', 2, pkg)=%-20s resolve_name('..seed', %s)=%-20s "
          "_is_allowed=%s" % (pkg, repr(got), ".".join(pkg), repr(rn), pu._is_allowed(got)))
    assert got == rn, (pkg, got, rn)
print("  → 三个包深下都**不是** 'app.domain.seed.generate'；扁平那档是 'app.seed'，"
      "包深 3 那两档是 'app.domain.seed'")

print()
print("=== ② 「解析到」口径：这句 import 语义上取到的对象 ===")
for pkg in (("app", "domain"), ("app", "domain", "sub")):
    obj = importlib.util.resolve_name("..seed.generate", ".".join(pkg))
    fold = pu._absolute("seed", 2, pkg)
    print("  pkg=%-24s resolve_name('..seed.generate', %s)=%-28s 而守卫实际比的是折算串 %-18s "
          "startswith('app.domain.')=%s"
          % (pkg, ".".join(pkg), repr(obj), repr(fold), str(fold).startswith("app.domain.")))

print()
print("=== ③ 老 :139 那句（折成 app.domain.seed.generate）是否可能成立 ===")
cands = [
    ("from ..seed import generate", "seed", 2, ""),
    ("from ..seed.generate import X", "seed.generate", 2, ""),
]
for label, module, level, name in cands:
    got = pu._absolute(module, level, ("app", "domain", "ind"))
    print("  %-30s pkg=('app','domain','ind')  折成 %-26s == 'app.domain.seed.generate'? %s"
          % (label, repr(got), got == "app.domain.seed.generate"))
print("  → 只有把写法换成 `from ..seed.generate import X`（module 带点）才会折出那个串；"
      "老 :139 写的是前者，故串错")

print()
print("=== ④ 老 :246 / 今 :422 那两句（本轮未动）复核 ===")
flat = pu._absolute("seed", 2, ("app", "domain"))
sub = pu._absolute("seed", 2, ("app", "domain", "sub"))
sub3 = pu._absolute("seed", 3, ("app", "domain", "sub"))
print("  扁平 app/domain/x.py       from ..seed  -> %-18s _is_allowed=%-5s → %s"
      % (repr(flat), pu._is_allowed(flat), "offender" if not pu._is_allowed(flat) else "放行"))
print("  子包 app/domain/sub/x.py   from ..seed  -> %-18s _is_allowed=%-5s → %s"
      % (repr(sub), pu._is_allowed(sub), "offender" if not pu._is_allowed(sub) else "不是 offender"))
print("  子包 app/domain/sub/x.py   from ...seed -> %-18s _is_allowed=%-5s → %s"
      % (repr(sub3), pu._is_allowed(sub3), "offender" if not pu._is_allowed(sub3) else "不是 offender"))
assert not pu._is_allowed(flat) and pu._is_allowed(sub) and not pu._is_allowed(sub3)
print("  → docstring 的三色（offender / 不是 offender / offender）与实跑相符")
print()
print("Ruling 42 复核: 老 :139 错（本轮已改）、老 :246 对（未动）")
