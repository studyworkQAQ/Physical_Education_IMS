"""domain 层纯净性架构约束的可执行检查（spec §3.3、Plan 02 Global Constraints）。

spec §3.3 规定 ``app/domain/`` 禁止任何 I/O：不得 import 数据库 / HTTP 框架，不得调用
时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，参考表一律由
:mod:`app.refdata` 加载后**作为参数传入**（Plan01 Ruling 15）。这是分层引擎与处方引擎
可单测、可复现的前提，也是 spec §12「domain 分支覆盖 100%」能成立的前提。

三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：

1. import 守卫从 **deny-list 改成 allow-list**（终审 A 的 M7）；
2. 时钟与 ``open`` 从**子串匹配改成 AST 节点匹配**（解析 ``ast.Call`` 的 ``func``）；
3. 三条都加 ``len(scanned) >= 5`` 的空转守卫——此前只有 ``DOMAIN.is_dir()``，而
   一个**存在但被搬空**的目录同样会让 ``rglob`` 返回空、offenders 恒为 ``[]``、测试假绿。
"""
import ast
import pathlib

DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "app" / "domain"

#: domain 允许 import 的**完整模块串**白名单（Plan02 Ruling 3）。
#:
#: ⚠️ 按**完整串**比对，不按顶层名：计划原文写「允许 ``collections.abc``」，而
#: ``from collections.abc import X`` 的 AST 顶层名是 ``collections``
#: （``node.module.split(".")[0]``）——按顶层名比对的话 ``collections.abc`` 这一项
#: **永不匹配**，同时 ``from collections import OrderedDict`` 与
#: ``from collections.abc import Iterable`` 变得无法区分，白名单退化成过宽的许可。
#: 故 ``collections`` 与 ``collections.abc`` **两个都列**：前者覆盖 ``import collections``，
#: 后者覆盖 ``from collections.abc import …`` 的完整串。
#:
#: ``numpy`` 只列裸名、不列 ``numpy.*``：**这是有意的**。``numpy.linalg`` 一类纯计算
#: 子模块今天用不上，而 ``numpy.random`` 恰恰是 Global Constraints 点名要挡的无种子
#: 随机数来源；只列裸名就让「要加一个 numpy 子模块」必须是一次显式的白名单修改。
ALLOWED_MODULES = frozenset({
    "dataclasses",
    "enum",
    "collections",
    "collections.abc",
    "numpy",
    "typing",
})

#: 唯一允许的**包**前缀：domain 内部互相依赖（``app.domain.tables`` 等）
ALLOWED_PACKAGE = "app.domain"

#: 时钟与文件句柄。按 ``ast.Call`` 的 ``func`` 点号串匹配，见
#: :func:`test_domain_has_no_clock_or_file_access` 的 docstring。
FORBIDDEN_CALLS = frozenset({
    "datetime.now",
    "datetime.today",
    "datetime.utcnow",
    "date.today",
    "time.time",
    "open",
})

#: 文件访问模式的子串黑名单（第三条守卫仍是子串匹配，理由见其 docstring）。
#: pandas 不在封禁之列——它是纯计算库，spec 的意图是「无文件系统/数据库/网络/时钟」，
#: 不是「不许用某个计算库」；封禁它会迫使向量化优化落到更差的设计上。
#: ``os`` / ``__file__`` / ``json.load`` / ``pickle.load`` 在列：少了它们，domain 里写一句
#: 「import 该标准库再列目录」就能同时绕过时钟与 ``open`` 两道守卫而全绿。
FORBIDDEN_IO = ("read_csv", "read_excel", "read_json", "read_parquet",
                "csv.reader", "csv.DictReader", ".read_text", ".read_bytes", "Path(",
                "import os", "os.listdir", "os.walk", "__file__",
                "json.load", "pickle.load")


def _domain_files() -> list[pathlib.Path]:
    """``app/domain/`` 下的全部 ``.py``，按路径升序（offender 报告顺序因此稳定）。"""
    # Path.rglob() 对不存在的目录静默返回空，缺了这行测试会空转全绿
    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
    return sorted(DOMAIN.rglob("*.py"))


def _assert_not_empty(scanned: list[pathlib.Path]) -> None:
    """空转守卫的第二半：目录**存在但被搬空**时 ``is_dir()`` 拦不住。

    下界 5 而不是 6：基线 ``e26347f`` 上实测 domain 有 **6** 个 ``.py``（``__init__`` /
    ``derive`` / ``indicators`` / ``percentile`` / ``stratify`` / ``tables``；命令见
    :func:`test_domain_imports_stay_within_the_allow_list` 的 docstring）。取 5 是给
    「两个模块合并」这类合法重构留一格余量，同时仍能挡住「整层被搬空」。
    """
    assert len(scanned) >= 5, (
        f"只扫到 {len(scanned)} 个 .py，app/domain 可能被搬空，三条守卫会一起假绿"
    )


def _imported_modules(tree: ast.AST):
    """yield ``(lineno, 完整模块串, 相对层级)``；``ast.walk`` 覆盖函数内导入。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, 0
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, (node.module or ""), node.level


def _is_allowed(module: str, level: int) -> bool:
    if level:
        # 相对导入只可能落在 app.domain 包内（本守卫扫的就是这个包），恒合法
        return True
    if module == ALLOWED_PACKAGE or module.startswith(ALLOWED_PACKAGE + "."):
        return True
    return module in ALLOWED_MODULES


def test_domain_imports_stay_within_the_allow_list():
    """domain 的 import 一律落在白名单内（allow-list，不是 deny-list）。

    **为什么从 deny-list 改成 allow-list**：deny-list 只能挡住**已经被想到**的库。终审 A
    实测旧 deny-list 能被 **14 种写法**绕过（如 ``from os import listdir``——旧守卫比的是
    顶层名 ``os`` 在不在 ``FORBIDDEN`` 里，而它确实拦得住这一种；但 ``import importlib``
    再 ``importlib.import_module("sqlalchemy")`` 这类间接写法它一个也拦不住）。allow-list
    把举证责任反过来：**没被显式允许的一律不行**，于是不需要有人先想到 ``os`` 才会被挡。

    ⚠️ **这一条是回归守卫、不是修复**（Plan02 Ruling 4）。落地当天 domain 六个文件的
    全部 import 就已经在白名单内，所以它**一上来就是绿的**——计划原文 Step 2 写的
    「allow-list 守卫报 ``numpy`` 之外的漏网」是猜的，AST 亲扫没有漏网。它的价值不在于
    今天红不红，而在于**新增的拦截力**：

    * ``import app.refdata`` 从此会被抓。终审 A 曾说「domain 经两跳依赖 ``app.refdata``」，
      **AST 实测不成立**——那是 ``percentile.py`` 模块 docstring 里的自陈（说的是「参考表
      由 refdata 加载后注入」这件事），不是 import。旧 deny-list 里没有 ``app.refdata``，
      所以真的加上这一句 import 时它不会响；白名单会。
    * ``from os import listdir`` / ``import json`` / ``import pathlib`` 一律被抓，
      不必再靠第三条守卫的子串去撞。

    **落地当天的 import 全貌**（AST 亲扫，这就是白名单取值的实测依据；命令::

        python -c "import ast,pathlib; [print(p.name, sorted({a.name for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.module})) for p in sorted(pathlib.Path('app/domain').rglob('*.py'))]"

    在 ``backend/`` 下跑，基线 ``e26347f``）::

        __init__.py      []
        derive.py        ['app.domain.indicators', 'app.domain.percentile', 'dataclasses', 'enum']
        indicators.py    ['app.domain.tables', 'enum']
        percentile.py    ['app.domain.indicators', 'app.domain.tables',
                          'collections.abc', 'dataclasses', 'enum', 'numpy']
        stratify.py      ['app.domain.derive', 'app.domain.indicators',
                          'collections.abc', 'dataclasses', 'enum']
        tables.py        ['collections.abc', 'dataclasses']

    六个文件、去重后**五个**不同的顶层来源（``dataclasses`` / ``enum`` /
    ``collections.abc`` / ``numpy`` / ``app.domain.*``），全部在白名单内。
    ``typing`` 在名单里但今天没人用：它是 ``Mapped[str | None]`` 这类标注的天然候选，
    列进来是为了让「加一个类型标注」不必先改架构测试。
    """
    scanned = _domain_files()
    offenders: list[str] = []
    for py in scanned:
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for lineno, module, level in _imported_modules(tree):
            if not _is_allowed(module, level):
                offenders.append(f"{py.name}:{lineno}: {module or '<空模块名>'}")

    _assert_not_empty(scanned)
    assert offenders == [], (
        "app/domain 是叶子层，import 必须落在白名单内"
        f"（{sorted(ALLOWED_MODULES)} + {ALLOWED_PACKAGE}.*）：\n" + "\n".join(offenders)
    )


def _dotted(node: ast.AST) -> str | None:
    """把一个表达式还原成点号串（``dt.datetime.now`` → ``"dt.datetime.now"``）。

    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``）返回 ``None``。
    那不是漏洞：这类写法要先拿到 ``datetime`` / ``time`` / ``builtins`` 这个对象，而
    拿到它的唯一途径是 import，import 已经被 allow-list 挡在门外。
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _hit_forbidden_call(dotted: str) -> str | None:
    """点号串是否命中 :data:`FORBIDDEN_CALLS`，命中则返回被封禁的那个名字。

    匹配口径是「**等于**，或以 ``.`` + 名字**结尾**」，不是裸 ``endswith``：
    后者会让一个名叫 ``reopen`` 的函数撞上 ``open``。带 ``.`` 边界之后
    ``builtins.open`` / ``open`` 命中，而 ``reopen`` / ``open_ended`` 不命中——
    这正是旧守卫用 ``\\bopen\\s*\\(`` 正则想做到的事，现在由 AST 天然做到。
    """
    for name in sorted(FORBIDDEN_CALLS):
        if dotted == name or dotted.endswith("." + name):
            return name
    return None


def test_domain_has_no_clock_or_file_access():
    """domain 不得调用时钟，也不得自己打开文件句柄。

    **为什么从子串改成 AST 节点匹配**（终审 A 的 M7）：子串匹配同时有两种失效。

    * **漏报**：``import datetime as dt`` 之后写 ``dt.datetime.now()``，子串
      ``"datetime.now"`` 恰好在里面，这一种能撞上；但 ``now = datetime.now`` 再
      ``now()`` 就撞不上了，而 AST 侧只要 ``now`` 的赋值来源是一次 ``ast.Call``
      就能顺着 ``_dotted`` 追到。
    * **误报**：docstring 或注释里出现一句「不要用 ``datetime.now()``」就会把守卫
      弄红。Plan 01 因此**不敢在 domain 的散文里写这些词**，那是让守卫反过来审查
      文档——本仓的 docstring 恰恰要求把口径写全（硬规矩 #19）。AST 只看代码节点，
      散文里怎么提都不响。

    ``open`` 从旧的 ``\\bopen\\s*\\(`` 正则并进 :data:`FORBIDDEN_CALLS`：它本来也是
    一次 ``ast.Call``，两套机制守同一件事只会让人分不清哪条是真相。

    ⚠️ **本条今天与 allow-list 高度重叠**：``datetime`` / ``time`` 都不在白名单里，
    所以 domain 根本 import 不到它们；``open`` 是内置名，不需要 import，故它是本条
    **唯一独立生效**的封禁项。保留整条的理由是纵深：白名单是「不许拿到工具」，本条是
    「不许做这个动作」——将来有人为了别的原因把 ``datetime`` 加进白名单（一个完全可能
    的合法请求，比如要一个 ``date`` 类型标注），本条仍然挡着 ``datetime.now()``。
    """
    scanned = _domain_files()
    offenders: list[str] = []
    for py in scanned:
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            if dotted is None:
                continue
            hit = _hit_forbidden_call(dotted)
            if hit is not None:
                offenders.append(f"{py.name}:{node.lineno}: {dotted}() 命中 {hit}")

    _assert_not_empty(scanned)
    assert offenders == [], (
        "时间与文件句柄一律由调用方注入，domain 不得自取：\n" + "\n".join(offenders)
    )


def test_domain_has_no_filesystem_access():
    """domain 不得出现任何读盘/取路径的写法（子串黑名单，第三条守卫）。

    **这一条刻意仍然是子串匹配**：它要抓的东西里有一半**不是调用**——``__file__`` 是
    一个模块级名字、``import os`` 是一条语句、``.read_text`` 可能挂在一个被注入进来的
    对象上。用 AST 逐个建模这些形态的成本远高于收益，而子串匹配在这里**只会误报不会
    漏报**（误报的代价是散文里不能写这些词，可接受）。

    与 allow-list 的分工：``import os`` / ``json.load`` / ``pickle.load`` /
    ``csv.DictReader`` 现在**两条都抓**（白名单先抓 import，本条再抓用法）。冗余是有意
    的——白名单抓的是「拿到工具」，本条抓的是「用工具」，两者独立失效时另一条还在。
    ``__file__`` 与 ``.read_text`` 则是本条**独有**的拦截面：前者不需要任何 import，
    后者可以作用在一个由调用方传进来的对象上。
    """
    scanned = _domain_files()
    offenders: list[str] = []
    for py in scanned:
        src = py.read_text(encoding="utf-8")
        offenders += [f"{py.name}:{tok}" for tok in FORBIDDEN_IO if tok in src]

    _assert_not_empty(scanned)
    assert offenders == [], (
        "domain 不得读盘（参考表由 app/refdata 加载后作为参数注入，Plan01 Ruling 15）：\n"
        + "\n".join(offenders)
    )
