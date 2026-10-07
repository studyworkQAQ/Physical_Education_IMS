# -*- coding: utf-8 -*-
"""pe_fr2_edit_arch.py — Plan02 Task1 fix round 2：两个架构守卫文件的改动。

所有替换都 assert 命中次数 == 1；CRLF 原样保留（读字节 → 归一化成 LF 编辑 → 写回 CRLF）。
"""
import pathlib
import sys

BACKEND = pathlib.Path(sys.argv[1]).resolve()

BODY_OLD = '''    if level == 0:
        return module
    anchor = package[: len(package) - (level - 1)]
    if not anchor:
        return None
    return ".".join(anchor + ((module,) if module else ()))
'''

BODY_NEW = '''    if level == 0:
        return module
    if level - 1 > len(package):
        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串
        return None
    anchor = package[: len(package) - (level - 1)]
    if not anchor:
        return None
    tail = module or name
    return ".".join(anchor + ((tail,) if tail else ()))
'''

SIG_OLD = 'def _absolute(module: str, level: int, package: tuple[str, ...]) -> str | None:'
SIG_NEW = 'def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:'

EDITS = []

# ================================================================ purity
P = "tests/architecture/test_domain_purity.py"

EDITS.append((P, SIG_OLD, SIG_NEW))
EDITS.append((P, BODY_OLD, BODY_NEW))

EDITS.append((P, '''    ``level == 2`` 上溯一层，依此类推——与 :func:`importlib.util.resolve_name` 同口径
    （``resolve_name("..seed.generate", "app.domain.ind")`` == ``"app.seed.generate"``）。
''', '''    ``level == 2`` 上溯一层，依此类推——与 :func:`importlib.util.resolve_name` 同口径。
    ⚠️ 它的第二个参数是 ``__package__``、即**包名**，不是模块名。两行都是本机 Python
    3.11.1 的实跑值（Plan02 Ruling 37）::

        resolve_name("..seed.generate", "app.domain")     -> "app.seed.generate"      # 包名，对
        resolve_name("..seed.generate", "app.domain.ind") -> "app.domain.seed.generate"  # 模块名，错

    第二行是 fix round 1 的 docstring 原来举的例子。这一段是 :func:`_package_of` 的**规格
    说明**，所以一个假举例不是笔误：谁按它去「对齐」代码（让 ``_package_of`` 返回
    ``("app", "domain", "ind")``），``app/domain/x.py`` 里的 ``from ..seed import generate``
    就会折成 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` → **守卫当场假绿**
    （硬规矩 #52：形如 ``f(x) == y`` 的举例必须是真跑过的输出）。

    ``name`` 是 ``node.names`` 里的**一个**被导入名，只在 ``module`` 为空时用得上：
    ``from .. import seed`` 的 AST 是 ``ImportFrom(module=None, level=2,
    names=[alias("seed")])``，被导入的模块名住在 ``names`` 里。只看 ``module`` 会把它折成
    ``app``、丢掉 ``.seed``，而 ``resolve_name("..seed", "app.pipeline")`` -> ``"app.seed"``
    → 不在白名单 → 本该 offender。**一个节点可以带多个名字**（``from .. import seed,
    pipeline`` 导入的是两个模块），故由 :func:`_imported_modules` 逐个展开成多次调用，
    本函数一次只折一个（Plan02 Ruling 36）。
'''))

EDITS.append((P, '''    返回 ``None`` 的那一档（``app/domain/x.py`` 里写 ``from ...seed import …``）同样
    判 offender、**不是「不管」**：Python 运行时会抛
    ``ValueError: attempted relative import beyond top-level package``，但那是运行期的事，
    静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。
''', '''    返回 ``None`` 的那一档（``app/domain/x.py`` 里写 ``from ...seed import …``）同样
    判 offender、**不是「不管」**：Python 3.11.1 运行时会抛
    ``ImportError: attempted relative import beyond top-level package``（合成树里真跑一遍
    ``import app.domain.x`` 的实测；:func:`importlib.util.resolve_name` 对同一输入抛同一个
    异常），但那是运行期的事，静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试
    全绿。**而这一档必须真的返回 ``None``**：``level - 1 > len(package)`` 时切片末端是
    **负数**，Python 会从尾部切出一个非空 anchor（``("app", "domain")[: 2 - 3]`` ==
    ``("app",)``），于是越界的 import 被折成一个**更浅的错误绝对串**——
    ``app/domain/x.py`` 里的 ``from ....domain import tables``（``level == 4``、包深 2）
    会折成 ``app.domain``、**命中白名单前缀 ``app.domain.`` 变成真绿**，而 ``resolve_name``
    对同一输入抛 ``ImportError``（Plan02 Ruling 35）。
'''))

EDITS.append((P, '''def _imported_modules(tree: ast.AST):
    """yield ``(lineno, 完整模块串, 相对层级)``；``ast.walk`` 覆盖函数内导入。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, 0
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, (node.module or ""), node.level
''', '''def _imported_modules(tree: ast.AST):
    """yield ``(lineno, 完整模块串, 相对层级, 被导入名)``；``ast.walk`` 覆盖函数内导入。

    第 4 项只在 ``level > 0`` **且** ``module`` 为空时非空——那一档被导入的模块名住在
    ``node.names`` 里（``from .. import seed``）。**一个节点可以带多个名字**，而
    ``from .. import seed, pipeline`` 导入的是**两个**模块，故这一档逐个 ``names`` yield
    两条、由 :func:`_absolute` 各自折算；只 yield 一条就会把 ``app.seed`` 折成 ``app``
    （Plan02 Ruling 36）。真仓里就有这一形状：``app/db/models/__init__.py:74`` 的
    ``from . import feedback, prescription``。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, 0, ""
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                for alias in node.names:
                    yield node.lineno, "", node.level, alias.name
            else:
                yield node.lineno, (node.module or ""), node.level, ""
'''))

EDITS.append((P, '''        for lineno, module, level in _imported_modules(tree):
            absolute = _absolute(module, level, package)
''', '''        for lineno, module, level, name in _imported_modules(tree):
            absolute = _absolute(module, level, package, name)
'''))

# ---- Minor 3：主语与结论必须落在同一个深度上
EDITS.append((P, '''      实测 12 条、全部 ``level == 1``），故 domain 侧**没有 offender**；但 Plan 02 Task 2
      起会建 ``app/domain/prescription/`` 这一层子包，届时 ``level == 2`` 的相对导入
      开始正常出现，「一律放行」的写法会跟着变成真漏洞。折算之后
      ``app/domain/sub/x.py`` 里的 ``from ..tables import X`` 仍然合法（解析到
      ``app.domain.tables``），而 ``from ..seed import generate`` 解析到 ``app.seed.generate``
      → offender。
''', '''      实测 12 条、全部 ``level == 1``），故 domain 侧**没有 offender**；但 Plan 02 Task 2
      起会建 ``app/domain/prescription/`` 这一层子包，届时 ``level == 2`` 的相对导入
      开始正常出现，「一律放行」的写法会跟着变成真漏洞。折算之后（⚠️ **同一句写法在不同
      文件深度解析到不同的地方**，故下面每条都带主语；合成树里逐条写入探针文件后直接
      调用本测试函数，颜色是实跑的，Plan02 Ruling 39-3）：

      * **扁平的** ``app/domain/x.py``（包深 2）：``from ..seed import generate`` 解析到
        ``app.seed.generate`` → **offender**；``from ...seed import generate`` 已经越界，
        :func:`_absolute` 返回 ``None`` → **同样 offender**。
      * ``app/domain/sub/x.py``（包深 3）：``from ..tables import X`` 解析到
        ``app.domain.tables`` → **合法**；而**同一句** ``from ..seed import generate`` 在
        这个深度解析到的是 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` →
        **不是 offender**（这一档要到 ``app.seed`` 得写 ``from ...seed import generate``，
        即 ``level == 3``，它才是 offender）。
'''))

# ---- Ruling 38 之一：_dotted 的「唯一途径是 import」是假的
EDITS.append((P, '''    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``）返回 ``None``，
    本守卫因此**放过**它们。对 ``datetime`` / ``time`` / ``builtins`` 那不是漏洞：拿到这些
    对象的唯一途径是 import，而 import 已经被 allow-list 挡在门外。**但 ``open`` 是内置名、
    不需要 import**，故这一档对 ``open`` 是真漏——与
    :func:`test_domain_has_no_clock_or_file_access` docstring 里那条「别名间接不被守卫」
    是同一个缺口，两处一起看才是本守卫的完整能力边界。
''', '''    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``、
    ``__import__("datetime").datetime.now()``——它们的 ``node.func`` 分别是 ``ast.Call`` /
    ``ast.Subscript`` / ``ast.Call`` / ``ast.Attribute(value=ast.Call)``，本函数只沿
    ``ast.Attribute`` 下溯到 ``ast.Name``，故一律返回 ``None``），本守卫因此**放过**它们。

    ⚠️ 这一段此前写着「对 ``datetime`` / ``time`` / ``builtins`` 那不是漏洞：拿到这些对象的
    **唯一途径是 import**，而 import 已经被 allow-list 挡在门外」——**那句是假的**，
    是个全称断言而它有反例：``__import__`` 自己就是**内置名**、不需要 import，而 G1 只匹配
    ``ast.Import`` / ``ast.ImportFrom`` 两种节点，于是 ``__import__("datetime").datetime.now()``
    **三条守卫全绿**（本机 Python 3.11.1 实跑；行与颜色见
    :func:`test_domain_has_no_clock_or_file_access` docstring 里那张 G1/G2/G3 表的第 8–14 行）。
    ``open`` 同理，也是内置名。**正确口径是：凡 :func:`_dotted` 还原不出点号串的调用形态，
    一律不被本守卫覆盖**，与那个对象是怎么拿到的无关。与
    :func:`test_domain_has_no_clock_or_file_access` docstring 里那条「别名间接不被守卫」
    是同一个缺口，两处一起看才是本守卫的完整能力边界（硬规矩 #39）。
'''))

# ---- Ruling 38 之二：把这一族写进 G1/G2/G3 实测表
EDITS.append((P, '''        import datetime as dt; dt.datetime.now()           RED            RED               GREEN
''', '''        import datetime as dt; dt.datetime.now()           RED            RED               GREEN
        __import__("datetime").datetime.now()             GREEN          GREEN             GREEN
        __import__("os").listdir(".")                     GREEN          GREEN             GREEN
        __import__("builtins").open("x")                  GREEN          GREEN             GREEN
        getattr(__import__("datetime"), "datetime").now()  GREEN          GREEN             GREEN
        eval("__import__('datetime').datetime.now()")     GREEN          GREEN             GREEN
        def _f(x): return getattr(x, "now")()             GREEN          GREEN             GREEN
        def _f(table): return table[0]()                  GREEN          GREEN             GREEN

    第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 **fix round 2 新增**（Plan02
    Ruling 38）；本轮把 14 行**全部重跑了一遍**，前 7 行的颜色逐字复现。
'''))

EDITS.append((P, '''    ``now = datetime.now`` 再 ``now()`` 同理（那种写法 G1 会先因 ``import datetime`` 变红，
    但**红的原因不是这次调用**）。堵这一类需要数据流/别名分析，本仓不做。
''', '''    ``now = datetime.now`` 再 ``now()`` 同理（那种写法 G1 会先因 ``import datetime`` 变红，
    但**红的原因不是这次调用**）。堵这一类需要数据流/别名分析，本仓不做。

    ⚠️ **「拿到工具必经 import」也不成立**（上表第 8–14 行，Plan02 Ruling 38）：
    ``__import__`` / ``eval`` / ``getattr`` 三个**内置名**都能在不写一条 ``ast.Import`` 的
    前提下拿到 ``datetime`` / ``os`` / ``builtins``，而 G2 的 :func:`_dotted` 对这些形态
    一律返回 ``None``、G3 的子串表里也没有 ``__import__`` / ``eval``，于是三条守卫**全绿**。
    ``__import__("os").listdir(".")`` 这一行尤其值得记住：它同时绕过了「不许取时钟」与
    「不许读盘」两条**立意**，而三条守卫一条都不响。这七行不是待修的漏洞清单，而是本条
    守卫的**能力边界**：它守的是「直白地写出 ``datetime.now()`` / ``open()``」，不守任何
    需要还原、求值或别名追踪才能看清的形态。要堵这一族就得把 ``__import__`` / ``eval`` /
    ``getattr`` 这些内置名本身列进封禁，代价是 domain 里连一个正常的
    ``getattr(obj, "name", default)`` 都写不了——本仓不做，但必须写清楚（硬规矩 #39）。
'''))

# ================================================================ layering
L = "tests/architecture/test_layering.py"

EDITS.append((L, SIG_OLD, SIG_NEW))
EDITS.append((L, BODY_OLD, BODY_NEW))

EDITS.append((L, '''    与 :func:`importlib.util.resolve_name` 同口径（``resolve_name("...seed.generate",
    "app.db.models.organisation")`` == ``"app.seed.generate"``）。``None`` 的那一档
    （如 ``app/pipeline/x.py`` 里写 ``from ...seed import …``）由调用方直接判 offender：
    Python 运行时会抛 ``ValueError: attempted relative import beyond top-level package``，
    但静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。
''', '''    与 :func:`importlib.util.resolve_name` 同口径。⚠️ 它的第二个参数是 ``__package__``、
    即**包名**，不是模块名。两行都是本机 Python 3.11.1 的实跑值（Plan02 Ruling 37）::

        resolve_name("...seed.generate", "app.db.models")              -> "app.seed.generate"     # 包名，对
        resolve_name("...seed.generate", "app.db.models.organisation") -> "app.db.seed.generate"  # 模块名，错

    第二行是 fix round 1 的 docstring 原来举的例子。这一段是 :func:`_package_of` 的**规格
    说明**，所以一个假举例不是笔误：谁按它去「对齐」代码（让 ``_package_of`` 把模块名那段
    也返回），``app/db/models/x.py`` 里的 ``from ...seed import …`` 就会折成 ``app.db.seed``、
    **不再以 ``app.seed`` 开头** → 本守卫当场假绿（硬规矩 #52）。

    ``name`` 是 ``node.names`` 里的**一个**被导入名，只在 ``module`` 为空时用得上：
    ``from .. import seed`` 的 AST 是 ``ImportFrom(module=None, level=2,
    names=[alias("seed")])``，被导入的模块名住在 ``names`` 里。只看 ``module`` 会把它折成
    ``app``、丢掉 ``.seed``，而 ``resolve_name("..seed", "app.pipeline")`` -> ``"app.seed"``
    → :func:`_is_forbidden` 命中 → **本该 offender、却是绿的**。多个名字由
    :func:`_imported_modules` 逐个展开，本函数一次只折一个（Plan02 Ruling 36）。
    ⚠️ **折算串错了不等于判定错了**：``app/db/models/x.py``（包深 3）的 ``from .. import
    seed`` 上溯一层到 ``app.db``，正确答案是 ``app.db.seed``，它**本来就不以 ``app.seed``
    开头**，故这一例的判定一直是绿、修完仍是绿，变的只是折算出来的那个串（此前是
    ``app.db``）。同一句写在 ``app/pipeline/x.py`` 或 ``app/db/x.py``（包深 2）里才指向
    ``app.seed``、才必须变红（Plan02 Ruling 41）。

    ``None`` 的那一档（如 ``app/pipeline/x.py`` 里写 ``from ...seed import …``）由调用方
    直接判 offender：Python 3.11.1 运行时会抛
    ``ImportError: attempted relative import beyond top-level package``（合成树里真跑一遍
    ``import app.domain.x`` 的实测；:func:`importlib.util.resolve_name` 抛同一个异常），
    但静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。**而这一档必须真的
    返回 ``None``**：``level - 1 > len(package)`` 时切片末端是**负数**，Python 会从尾部切出
    一个非空 anchor（``("app", "db", "models")[: 3 - 4]`` == ``("app", "db")``），于是
    ``app/db/models/x.py`` 里的 ``from .....seed import generate``（``level == 5``、包深 3）
    被折成 ``app.db.seed``、**不以 ``app.seed`` 开头 → 假绿**，而 ``resolve_name`` 对同一
    输入抛 ``ImportError``（Plan02 Ruling 35）。
'''))

EDITS.append((L, '''        cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, _absolute(node.module or "", node.level, package)
''', '''        cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"

    那 12 条里有 **1 条**是 ``module`` 为空的形状：``app/db/models/__init__.py:74`` 的
    ``from . import feedback, prescription``（上面那条命令打出来的第 7 行是
    ``app/db/models/__init__.py 74 1 None``）。它是**一个节点、两个名字、两个模块**，故
    下面按 ``names`` 逐个 yield、折算成 ``app.db.models.feedback`` 与
    ``app.db.models.prescription`` 两条；此前只 yield 一条 ``app.db.models``（Plan02
    Ruling 36）。两条都不以 ``app.seed`` 开头，**判定不变、仍然绿**。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                # `from .. import seed, pipeline` 是一个节点导入两个模块，必须逐个折算
                for alias in node.names:
                    yield node.lineno, _absolute("", node.level, package, alias.name)
            else:
                yield node.lineno, _absolute(node.module or "", node.level, package)
'''))

# ---- Minor 1：搬空单个目录后的上界是 18，不是 17
EDITS.append((L, '''    # 一次合法重构变红。**代价（硬规矩 #39）**：8 只挡得住「三个目录被一起搬空」——单个
    # 目录被搬空时仍剩 13…17 个 .py，本断言拦不住。那一档的兜底是：``domain`` 由
''', '''    # 一次合法重构变红。**代价（硬规矩 #39）**：8 只挡得住「三个目录被一起搬空」——单个
    # 目录被搬空时仍剩 **13…18** 个 .py（24 − 11(db) = 13、24 − 7(pipeline) = 17、
    # 24 − 6(domain) = 18，由上面那条 Counter 命令本轮亲跑得出），本断言拦不住。
    # 那一档的兜底是：``domain`` 由
'''))


def main():
    per_file = {}
    for rel, old, new in EDITS:
        per_file.setdefault(rel, []).append((old, new))
    for rel, pairs in per_file.items():
        path = BACKEND / rel
        raw = path.read_bytes()
        crlf = raw.count(b"\r\n")
        text = raw.decode("utf-8")
        assert crlf == text.count("\n"), (rel, "不是纯 CRLF", crlf, text.count("\n"))
        norm = text.replace("\r\n", "\n")
        for i, (old, new) in enumerate(pairs):
            n = norm.count(old)
            assert n == 1, "%s 第 %d 处替换命中 %d 次（应为 1）:\n%s" % (rel, i, n, old[:160])
            norm = norm.replace(old, new)
        out = norm.replace("\n", "\r\n").encode("utf-8")
        path.write_bytes(out)
        print("已写 %-48s %d 处替换  %d -> %d 字节  CRLF %d" %
              (rel, len(pairs), len(raw), len(out), out.count(b"\r\n")))


main()
