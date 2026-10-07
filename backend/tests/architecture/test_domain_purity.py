"""domain 层纯净性架构约束的可执行检查（spec §3.3、Plan 02 Global Constraints）。

spec §3.3 规定 ``app/domain/`` 禁止任何 I/O：不得 import 数据库 / HTTP 框架，不得调用
时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，参考表一律由
:mod:`app.refdata` 加载后**作为参数传入**（Plan01 Ruling 15）。这是分层引擎与处方引擎
可单测、可复现的前提，也是 spec §12「domain 分支覆盖 100%」能成立的前提。

本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**
（``test_absolute_folding_matches_resolve_name``，测的是 ``_absolute`` / ``_package_of``
这两个辅助函数，**不是第四条守卫**；Plan02 Ruling 46/54）。三条守卫 Plan 02 Task 1 全部
改写过一次，改动理由各写在对应测试的 docstring 里：

1. import 守卫从 **deny-list 改成 allow-list**（终审 A 的 M7）；
2. 时钟与 ``open`` 从**子串匹配改成 AST 节点匹配**（解析 ``ast.Call`` 的 ``func``）；
3. 三条都加 ``len(scanned) >= 5`` 的空转守卫——此前只有 ``DOMAIN.is_dir()``，而
   一个**存在但被搬空**的目录同样会让 ``rglob`` 返回空、offenders 恒为 ``[]``、测试假绿。

第 1 条在 fix round 1 又补了一刀：相对导入不再无条件放行，先用 :func:`_absolute` 折算成
绝对模块串再走白名单（``level >= 2`` 的相对导入会跨包，见该函数的 docstring）。
"""
import ast
import pathlib

DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "app" / "domain"
#: ``backend/``。相对导入要折算成绝对串，就得知道源文件在包树里的位置，见 :func:`_package_of`。
BACKEND = DOMAIN.parent.parent

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
    ⚠️ **那个 6 绑它自己的时点**：Plan 02 逐 Task 建 ``prescription/`` 子包之后，
    本 Task（Task 4，建 ``match.py``）落地时同一条命令数出 **10** 个
    （6 + ``prescription/{__init__, exercises, templates, match}``），故余量已经从
    「1 格」变成「5 格」——下界本身**不需要**跟着改（它挡的是「整层被搬空」，
    不是「文件数变了」），但读这段的人不该以为 5 与 6 只差一格还是今天的状态。
    """
    assert len(scanned) >= 5, (
        f"只扫到 {len(scanned)} 个 .py，app/domain 可能被搬空，三条守卫会一起假绿"
    )


def _imported_modules(tree: ast.AST):
    """yield ``(lineno, 完整模块串, 相对层级, 被导入名)``；``ast.walk`` 覆盖函数内导入。

    第 4 项只在 ``level > 0`` **且** ``module`` 为空时非空——那一档被导入的模块名住在
    ``node.names`` 里（``from .. import seed``）。**一个节点可以带多个名字**，而
    ``from .. import seed, pipeline`` 导入的是**两个**模块，故这一档逐个 ``names`` yield
    两条、由 :func:`_absolute` 各自折算；只 yield 一条就会把 ``app.seed`` 折成 ``app``
    （Plan02 Ruling 36）。真仓里就有这一形状：``app/db/models/__init__.py`` 里那句
    ``from . import feedback, prescription  # noqa: F401``（⚠️ **用可 grep 的原文定位、
    不写裸行号**：``git grep -n "import feedback" -- backend/app`` 只命中这一处，而裸行号
    已被编辑推走过一次——Task 2 按 Ruling 90 改该文件 docstring 时它从 ``:74`` 落到 ``:82``，
    引用它的两处都没跟着改（Plan02 账本 Ruling 106 的 CE-7）。在 ``c21767d`` 上它是第
    **82** 行；``:74`` 今天是 ``from .derived import *  # noqa: F401,F403``）。
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


def _package_of(py: pathlib.Path) -> tuple[str, ...]:
    """``py`` 所在的**包**，以 ``backend/`` 为根的段。

    ``app/domain/x.py`` → ``("app", "domain")``，``app/domain/sub/x.py`` →
    ``("app", "domain", "sub")``。``__init__.py`` 与同目录的普通模块给出**同一个**包：
    去掉扩展名后最后一段在两种情况下都是「模块名」（``__init__`` / ``x``），故一律取
    ``parts[:-1]``——这正是 Python 自己的 ``__package__``。
    """
    return py.relative_to(BACKEND).with_suffix("").parts[:-1]


def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。

    ``level == 0`` 本来就是绝对串。``level == 1`` 落在 ``package`` 自己这一层，
    ``level == 2`` 上溯一层，依此类推——与 :func:`importlib.util.resolve_name` 同口径。
    ⚠️ 它的第二个参数是 ``__package__``、即**包名**，不是模块名。两行都是本机 Python
    3.11.1 的实跑值（Plan02 Ruling 37）::

        resolve_name("..seed.generate", "app.domain")     -> "app.seed.generate"      # 包名，对
        resolve_name("..seed.generate", "app.domain.ind") -> "app.domain.seed.generate"  # 模块名，错

    第二行是 fix round 1 的 docstring 原来举的例子。这一段是 :func:`_package_of` 的**规格
    说明**，所以一个假举例不是笔误：谁按它去「对齐」代码（让 ``_package_of`` 返回
    ``("app", "domain", "ind")``），``app/domain/x.py`` 里的 ``from ..seed import generate``
    就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``：``generate`` 住在
    ``node.names`` 里、不进折算串，Plan02 Ruling 36；本机 Python 3.11.1 实跑
    ``_absolute("seed", 2, ("app", "domain", "ind"))`` -> ``'app.domain.seed'``、
    ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →
    **本守卫当场假绿**。主语必须标出来（硬规矩 #56）：这个「假绿」只属于本文件
    （:mod:`tests.architecture.test_domain_purity` 这一份）——它本该把 ``app.seed`` 判成
    offender，却被折出来的 ``app.domain.seed`` 骗过。:mod:`tests.architecture.test_layering`
    那一份对**同一个串**判的是 ``app.seed`` 前缀，``_is_forbidden('app.domain.seed')`` 为
    ``False``（fix round 5 亲跑）→ 那一份是**正确的 GREEN**、不是假绿。
    （硬规矩 #52：形如 ``f(x) == y`` 的举例必须是真跑过的输出）。

    ``name`` 是 ``node.names`` 里的**一个**被导入名，只在 ``module`` 为空时用得上：
    ``from .. import seed`` 的 AST 是 ``ImportFrom(module=None, level=2,
    names=[alias("seed")])``，被导入的模块名住在 ``names`` 里。只看 ``module`` 会把它折成
    ``app``、丢掉 ``.seed``，而 ``resolve_name("..seed", "app.pipeline")`` -> ``"app.seed"``
    → 不在白名单 → 本该 offender。**一个节点可以带多个名字**（``from .. import seed,
    pipeline`` 导入的是两个模块），故由 :func:`_imported_modules` 逐个展开成多次调用，
    本函数一次只折一个（Plan02 Ruling 36）。

    **相对导入必须先折算再走白名单，不能一律放行**。这段判定此前住在 :func:`_is_allowed`
    里、形如 ``if level: return True``，注释是「相对导入只可能落在 ``app.domain`` 包内」——
    那句只对 ``level == 1`` 成立。合成树实测（``app/domain/probe.py`` 里逐条写入下列
    写法后直接调用本测试函数）：``from .. import pipeline`` 解析到 ``app.pipeline``、
    ``from ..seed import generate`` 解析到 ``app.seed.generate``，**改前两条全绿**。
    这与 :data:`ALLOWED_MODULES` 的立意相反：allow-list 的意义是「没被显式允许的一律
    不行」，而 ``if level: return True`` 恰好是「有一类写法一律允许」。

    返回 ``None`` 的那一档（``app/domain/x.py`` 里写 ``from ...seed import …``）同样
    判 offender、**不是「不管」**：Python 3.11.1 运行时会抛
    ``ImportError: attempted relative import beyond top-level package``（合成树里真跑一遍
    ``import app.domain.x`` 的实测；:func:`importlib.util.resolve_name` 对同一输入抛同一个
    异常），但那是运行期的事，静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试
    全绿。**而这一档必须真的返回 ``None``**：``level - 1 > len(package)`` 时切片末端是
    **负数**，Python 会从尾部切出一个非空 anchor（``("app", "domain")[: 2 - 3]`` ==
    ``("app",)``），于是越界的 import 被折成一个**更浅的错误绝对串**——
    ``app/domain/x.py`` 里的 ``from ....domain import tables``（``level == 4``、包深 2）
    会折成 ``app.domain``，而 ``_is_allowed`` 的第一支正是 ``module == ALLOWED_PACKAGE``——
    **命中的是「相等」这一支，不是 ``startswith(ALLOWED_PACKAGE + ".")`` 那一支**（本机
    Python 3.11.1 实跑：``"app.domain" == ALLOWED_PACKAGE`` -> ``True``、
    ``"app.domain".startswith(ALLOWED_PACKAGE + ".")`` -> ``False``；Plan02 Ruling 42），
    于是变成真绿；而 ``resolve_name``
    对同一输入抛 ``ImportError``（Plan02 Ruling 35）。
    """
    if level == 0:
        return module
    if level - 1 > len(package):
        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串
        return None
    anchor = package[: len(package) - (level - 1)]
    if not anchor:
        return None
    tail = module or name
    return ".".join(anchor + ((tail,) if tail else ()))


def _is_allowed(module: str) -> bool:
    """一个**绝对**模块串是否在白名单内（相对导入先经 :func:`_absolute` 折算）。"""
    if module == ALLOWED_PACKAGE or module.startswith(ALLOWED_PACKAGE + "."):
        return True
    return module in ALLOWED_MODULES


def test_absolute_folding_matches_resolve_name():
    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。

    **判据为什么锚在 ``resolve_name`` 上、而不是锚在一张期望值表上**：表是某个人某一次跑
    出来的结果，抄进测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；
    ``resolve_name`` 是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格
    现场调一次 ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``
    （越界档，Plan02 Ruling 35）。

    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug；下面列的是三条
    变异**（``2 ≠ 3`` 不是笔误：Ruling 36 有**两半**——``_absolute`` 接 ``name``、
    ``_imported_modules`` 一名一条展开，两半都在 fix round 2 那一个 commit ``1fa9941`` 里
    落地；加上 Ruling 35 的越界档，就是「两个 bug / 三条变异」，与下面「三条的复现命令」
    「三种变异」是同一个计数）。Plan02 Ruling 46：谁把**两份**的
    ``if level - 1 > len(package): return None`` 都删掉，在基线 ``be0f1af^``（= ``1fa9941``，
    本测试还不存在的那一次）上全量 **479 passed、退出码 0**。fix round 5 在 ``$env:TEMP``
    的 ``git worktree`` 上亲跑复现：原样 ``479 passed in 57.41s``、删掉那 3 行后
    ``479 passed in 59.20s``，两次退出码都是 0。⚠️ 别在 HEAD 上照做：HEAD 有 481 条，
    同一个变异会得到 ``2 failed, 479 passed``，红的正是本文件与
    :mod:`tests.architecture.test_layering` 各一条 ``test_absolute_folding_matches_resolve_name``。

    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
      ``("domain", 4, ("app", "domain"), "tables")`` 折成 ``app.domain`` 而不是 ``None``
      → 本测试红。
    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
      ``app.seed`` → 本测试红。
    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
      模块，Plan02 Ruling 36）→ 末尾那一段红。

    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。fix round 3 实测
    三种变异各让**本文件这一条**红、而 :mod:`tests.architecture.test_layering` 那一条
    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。
    断言里印出来的折算值
    也是实跑的：越界档报 ``_absolute('domain', 4, ('app', 'domain'), 'tables') =
    'app.domain'``（而 ``resolve_name('....domain', 'app.domain')`` 抛 ``ImportError``）、
    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。

    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫），而且是**两档**：

    * ``level == 1`` 的包内导入折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed`
      放行（矩阵第 2、3 行）。
    * ``level == 2`` 的**跨子包**导入也必须仍被 :func:`_is_allowed` 放行（矩阵第 9 行，
      fix round 5 新加，Plan02 Ruling 67）：``app/domain/prescription/match.py`` 里**假如**写
      ``from ..indicators import X`` 就是这一档。⚠️ **它是 ``level == 2`` 而**不是
      ``level == 1``——那个文件的 ``__package__`` 是 ``app.domain.prescription``（包深 3），
      要**两个点**才上溯到 ``app.domain``。⚠️ **Task 4 落地后这一格仍是「前瞻」**：
      ``match.py`` 实际写的是 ``from app.domain.stratify import …``（跨包指向所有者，绝对串）
      与 ``from .templates import …``（同包兄弟，``level == 1``），故真仓到今天为止
      **没有任何 ``level == 2`` 的相对导入**（Plan02 账本 Ruling 104）。fix round 5 亲跑
      （本机 Python 3.11.1）::

          ast.parse('from ..indicators import X') -> level=2 module='indicators' names=['X']
          _package_of(BACKEND / 'app/domain/prescription/match.py')
              = ('app', 'domain', 'prescription')
          _absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')
              = 'app.domain.indicators'
          resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'
          _is_allowed('app.domain.indicators') = True   -> 本文件（purity 侧）判 GREEN

      改前这一格**不在矩阵里**：那 11 格里 ``(包深 3, level 2, GREEN)`` 是 **0 格**、GREEN
      只有 2 格且都在包深 2 / ``level == 1``，于是「Task 2 那个形状在 purity 侧是绿的」这件
      事仓库里没有任何断言看着。:mod:`tests.architecture.test_layering` 那一份的同一格也是
      GREEN，但**理由不同**：它判的是 ``app.seed`` 前缀，
      ``_is_forbidden('app.domain.indicators')`` 为 ``False`` → 不以 ``app.seed`` 开头就放行。
    ⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")`` 折成 ``app.db.seed``，在
    **本文件**的白名单下是 RED、在 :mod:`tests.architecture.test_layering` 的 ``app.seed``
    前缀下却是 GREEN：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份回归测试的
    期望颜色列**不相同**，这不是抄错。

    **本测试守不住什么**（硬规矩 #39）：

    * :func:`_package_of` 由本测试**末尾两段**看着（Plan02 Ruling 54；Task 4 起第一段从
      「手写 4 格」换成扫真仓）：**扫真仓那一段**把 ``backend/`` 下每个 ``.py`` 的
      ``_package_of(py)`` 与 ``py.relative_to(BACKEND).parent.parts`` 对拍，故包深自动跟进、
      不必有人记得加行（Ruling 66 / C-fr4-1 要的正是这个；``__init__.py`` 与同目录的普通
      模块必须给出**同一个**包，那正是 ``parts[:-1]`` 这个写法的全部理由，扫描天然覆盖到
      ``app/db/models/`` 那一对）；**合成那一段**再把 ``_package_of`` 的输出喂给
      :func:`_absolute`，用的是真仓里**不存在**的 ``level == 2`` / ``level == 3`` 导入，
      故它覆盖「包深 2 与包深 3 上越级折算」这一档。两段互不替代。
      ⚠️ 上面那 12 格矩阵的 ``package`` 入参仍是**手写的**，故矩阵与这两段也互不覆盖。
    * 它扫真仓，但扫的是「折算与 ``resolve_name`` 是否一致」、**不是**「折算结果是否落在
      白名单内」：真仓今天一条 offender 都没有（(c)），故「白名单取值本身对不对」仍只由
      :func:`test_domain_imports_stay_within_the_allow_list` 看着，判颜色这件事只有手写矩阵
      的 RED 格与那条 allow-list 守卫在做，两条判据互不覆盖。
    * 矩阵是有限的 12 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
    """
    # 就地 import：模块级 import 会改动本文件的 <module-level>，故这条测试自 fix round 3
    # 起就把 import 留在函数体内、改动面也一直钉死在「这一条测试函数 + docstring」
    # 之内（Plan02 Ruling 46/57）。
    import importlib.util

    #: ``(module, level, package, name, 期望颜色)``。以 **AST 形状**为参数，不用「``from …``
    #: 的字面写法」当唯一标识——同一句写法在不同包深下折算到不同的地方（Plan02
    #: Ruling 41/45）。期望颜色是**判据**（本文件的白名单语义），不是折算结果。
    cases = [
        # level == 0：本来就是绝对串，原样返回
        ("app.seed.generate", 0, ("app", "domain"), "", "RED"),
        # level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）
        ("tables", 1, ("app", "domain"), "", "GREEN"),
        ("", 1, ("app", "domain"), "tables", "GREEN"),
        # level == 2：跨包指向 app.seed，真 offender
        ("seed.generate", 2, ("app", "pipeline"), "", "RED"),
        # module 为空：被导入的模块名住在 node.names 里（Ruling 36）
        ("", 2, ("app", "pipeline"), "seed", "RED"),
        ("", 2, ("app", "db"), "seed", "RED"),
        ("", 2, ("app", "db", "models"), "seed", "RED"),
        ("", 2, ("app", "domain"), "seed", "RED"),
        # **Task 1 fix round 5 为 Task 4 的形状埋的一格**（fix round 5 新加，Plan02 Ruling 67；
        # ⚠️ 本行此前把这一格的归属记错了**两处**——它既不是那个 Task 加的、也不是那个 Task
        # 的形状；Plan02 账本 P4-A6 的第 ③ 项。被撤销的写法按硬规矩 #74 不再逐字复述）：
        # app/domain/prescription/match.py
        # 里**假如**写 `from ..indicators import X`——包深 3 → 两个点才上溯到 app.domain，
        # 故 level == 2。折成 app.domain.indicators；本文件（purity 侧）命中白名单前缀
        # app.domain. → GREEN。test_layering.py 同一格也是 GREEN，但理由是「不以 app.seed
        # 开头」、不是白名单。
        # ⚠️ **Task 4 落地后这一格仍是「前瞻」、不是真仓形状**：match.py 实际选的是
        # 「跨包指向所有者用绝对串（from app.domain.stratify import …）+ 同包兄弟用
        # level == 1 相对串（from .templates import …）」，与 templates.py / __init__.py
        # 既有写法一致，故全仓到今天为止**没有任何 level == 2 的相对导入**
        # （Plan02 账本 Ruling 104 记的同一件事，Task 2 与 Task 3 也都选了绝对导入）。
        ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN"),
        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）
        ("seed", 5, ("app", "db", "models"), "generate", "RED"),
        ("domain", 4, ("app", "domain"), "tables", "RED"),
        # level - 1 == len(package)：由 `not anchor` 那一行兜住，同样必须 None
        ("seed", 3, ("app", "domain"), "generate", "RED"),
    ]
    offenders: list[str] = []
    for module, level, package, name, color in cases:
        rel = "." * level + (module or name)
        pkg = ".".join(package)
        try:
            want = importlib.util.resolve_name(rel, pkg)
        except ImportError:
            want = None
        got = _absolute(module, level, package, name)
        if got != want:
            offenders.append(
                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r}，"
                f"而 resolve_name({rel!r}, {pkg!r}) = {want!r}"
            )
        verdict = "RED" if got is None or not _is_allowed(got) else "GREEN"
        if verdict != color:
            offenders.append(
                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r} "
                f"判成 {verdict}、期望 {color}"
            )
    assert offenders == [], (
        "_absolute 与 importlib.util.resolve_name 不一致、或某一档颜色不对"
        "（Plan02 Ruling 35/36/41）：\n" + "\n".join(offenders)
    )

    # Ruling 36 的另一半：一个 ImportFrom 节点带两个名字，必须展开成两条、各自折算。
    tree = ast.parse("from .. import seed, pipeline\n")
    package = ("app", "pipeline")
    got = [_absolute(module, level, package, name)
           for _lineno, module, level, name in _imported_modules(tree)]
    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
            for alias in ("seed", "pipeline")]
    assert got == want, f"一名一条的展开失效: {got} != {want}"

    # ------------------------------------------------- Ruling 54 / 56 / 66（C-fr4-1）
    # 上面 12 格的 package / level / module 入参全是**手写的**，故真仓长出新形状时没人会被
    # 提醒加行（Plan02 Ruling 54 说的是 _package_of、Ruling 56 说的是整个矩阵、Ruling 66 /
    # C-fr4-1 把 _package_of 的处置具体化成「扫真仓与 parent.parts 对拍」）。Task 4 起补一段
    # **扫真仓**的对拍，backend/ 下每个 .py 都过两遍：
    #   ① _package_of(py) 与 py.relative_to(BACKEND).parent.parts 对拍（C-fr4-1）；
    #   ② 它的每个相对导入现场折一次、与 resolve_name 对拍（Ruling 56）。
    # 两侧都不同源：① 的期望侧是 pathlib 自己的 parent.parts（与被测的
    # with_suffix("").parts[:-1] 是两个独立写法，且 __init__.py 与普通模块必须给出同一个包
    # ——那正是 parts[:-1] 这个写法的全部理由）；② 的期望侧是 Python 自己对相对导入的定义。
    #
    # ⚠️ **它是那 12 格矩阵的补充、不是替代**（Task 4 实测的理由，两份守卫同一段）：真仓今天
    #   (a) 没有任何 level >= 2 的相对导入（Task 2 / 3 / 4 三轮都刻意选了绝对导入，
    #       Plan02 账本 Ruling 104），
    #   (b) 没有任何越界档（resolve_name 抛 ImportError、_absolute 必须返回 None 那一档），
    #   (c) 没有任何 offender（本文件判定为 RED 的格子）。
    # 这三类**只有手写的矩阵能提供**。Ruling 56 当初把「换成全仓扫描」的时机定在
    # 「level == 2 的**合法**相对导入开始真实出现」之后，而那个前提到今天仍未成立；
    # 删掉矩阵会让 _absolute 的越界分支与 _is_allowed 的 RED 判定同时失去守卫
    # ——正是 Ruling 35/46 修掉过的那个「479 passed、退出码 0」的假绿。
    real_offenders: list[str] = []
    real_py = sorted(BACKEND.rglob("*.py"))
    folded: set[str] = set()
    relative_seen = 0
    for py in real_py:
        where = py.relative_to(BACKEND).as_posix()
        got_pkg = _package_of(py)
        want_pkg = py.relative_to(BACKEND).parent.parts
        if got_pkg != want_pkg:
            real_offenders.append(
                f"_package_of({where}) = {got_pkg!r}，而 parent.parts = {want_pkg!r}"
                "（parts[:-1] 被写成了 parts 时就是这一格红）"
            )
        real_tree = ast.parse(py.read_text(encoding="utf-8"))
        for _lineno, module, level, name in _imported_modules(real_tree):
            if not level:
                continue  # 绝对串不经 _package_of / _absolute 的折算，本段只对拍相对导入
            relative_seen += 1
            rel = "." * level + (module or name)
            pkg_str = ".".join(got_pkg)
            try:
                want = importlib.util.resolve_name(rel, pkg_str)
            except ImportError:
                want = None
            got = _absolute(module, level, got_pkg, name)
            folded.add("<越界>" if got is None else got)
            if got != want:
                real_offenders.append(
                    f"{where} 里的 from {rel} import …：_absolute({module!r}, {level}, "
                    f"{got_pkg!r}, {name!r}) = {got!r}，而 resolve_name({rel!r}, "
                    f"{pkg_str!r}) = {want!r}"
                )
    # 空转守卫（BACKEND 指错 / 真仓被搬空时上面那个循环一条都不跑、offenders 恒为 []）。
    # 三个下界与五个折算串都是**字面量**（硬规矩 #35，不从被测函数反推）：
    #   40 = backend/ 下 .py 的个数下界（Task 4 落地时实测 69）；
    #   16 = 全仓相对导入的条数下界（Task 4 落地时实测 18，命令见
    #        test_domain_imports_stay_within_the_allow_list 的 docstring）；
    #   五个折算串各代表一类真实形状：app/db/models 包内的 level == 1、
    #   `from . import feedback, prescription` 那种「一个节点两个名字」的展开（Ruling 36）、
    #   以及 app/domain/prescription 包内的三句（.exercises 自 Task 2、.templates 自 Task 3、
    #   .match 自 Task 4）。少了任何一个，本段的「绿」就可能是空转。
    assert len(real_py) >= 40, f"只扫到 {len(real_py)} 个 .py，BACKEND 可能指错了: {BACKEND}"
    assert relative_seen >= 16, f"只扫到 {relative_seen} 条相对导入，本段可能空转了"
    for expect in ("app.db.models._shared", "app.db.models.feedback",
                   "app.domain.prescription.exercises", "app.domain.prescription.match",
                   "app.domain.prescription.templates"):
        assert expect in folded, (
            f"真仓里没有折出 {expect}，本段的绿档可能已经空转：{sorted(folded)}"
        )
    assert real_offenders == [], (
        "扫真仓的对拍不通过（Plan02 Ruling 54/56/66）：\n" + "\n".join(real_offenders)
    )

    # _package_of 被改坏的**后果**也要能跑、不能只写在断言消息里：把它的输出直接喂给
    # _absolute，结果仍须与 resolve_name 逐字相同（判据同上，锚在 Python 自己的语义上）。
    # ⚠️ 这两格是**合成的** level >= 2 / level == 3 导入，真仓里不存在（见上面 (a)），
    # 故扫真仓那一段替代不了它；反过来它也替代不了扫描（它只覆盖 2 个包深）。
    pkg_offenders: list[str] = []
    for rel, level, module, want_pkg in (
            ("app/domain/indicators.py", 2, "seed", ("app", "domain")),
            ("app/db/models/organisation.py", 3, "seed", ("app", "db", "models"))):
        rel_import = "." * level + module
        pkg_str = ".".join(want_pkg)
        got = _absolute(module, level, _package_of(BACKEND / rel))
        want = importlib.util.resolve_name(rel_import, pkg_str)
        if got != want:
            pkg_offenders.append(
                f"{rel} 里的 from {rel_import} import …：用 _package_of 的结果折算得到 "
                f"{got!r}，而 resolve_name({rel_import!r}, {pkg_str!r}) = {want!r}"
            )
    assert pkg_offenders == [], (
        "_package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让"
        "它返回**模块路径**，于是 app/domain/x.py 里的 from ..seed import … 折成 "
        "app.domain.seed、命中白名单前缀 app.domain. → 本文件的守卫假绿（test_layering.py "
        "那一份同理：app/db/models/x.py 里的 from ...seed import … 折成 app.db.seed、不再"
        "以 app.seed 开头），而在本段断言加上之前，这么改一次全量测试都照样通过：\n"
        + "\n".join(pkg_offenders)
    )


def test_domain_imports_stay_within_the_allow_list():
    """domain 的 import 一律落在白名单内（allow-list，不是 deny-list）。

    **为什么从 deny-list 改成 allow-list**：deny-list 只能挡住**已经被想到**的库。基线
    ``e26347f`` 上那个集合是**六项**，里面**没有 ``os``**（``git show
    e26347f:backend/tests/architecture/test_domain_purity.py`` 第 13 行）::

        FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx",
                     "pydantic_settings", "random"}

    它比的是 AST 取出的**顶层名**（同文件 ``:38`` ``mods = [a.name.split(".")[0] …]``、
    ``:40`` ``mods = [node.module.split(".")[0]]``、``:41`` ``… if m in FORBIDDEN``）。
    把基线守卫落盘、``DOMAIN`` 重定向到一棵合成树后亲跑，**下面三种写法在基线上三条守卫
    全绿**：

    * ``from os import listdir`` —— 第一条取出顶层名 ``os``，不在 ``FORBIDDEN``；第三条
      子串守卫也撞不上：源码里写的是 ``os import``，**没有**子串 ``import os``，
      也没有 ``os.listdir``。
    * ``import numpy.random`` —— 顶层名 ``numpy`` 不在 ``FORBIDDEN``（Global Constraints
      点名要挡的无种子随机数由此进来）。
    * ``import app.refdata`` —— 顶层名 ``app`` 不在 ``FORBIDDEN``。

    控制组（证明基线守卫**不是恒绿**，同一次跑）：``import sqlalchemy`` → 第一条 **红**；
    ``import os`` → 第三条 **红**（源码里有子串 ``import os``）；``os.listdir('x')`` →
    第三条 **红**。故基线守卫是有牙的，只是牙口不含 ``from os import …`` 这一种写法。

    allow-list 把举证责任反过来：**没被显式允许的一律不行**，于是不需要有人先想到 ``os``
    才会被挡。终审 A 说的「14 种写法可绕过」是它自己的枚举，fix round 1 没有逐条复跑；
    上面三条是**亲跑基线**的结果，两者方向一致。

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
    * **相对导入一律先折算成绝对串**再走白名单（:func:`_absolute`）。全仓的相对导入
      **全部是 ``level == 1``**，但自 Plan 02 Task 2 起已**不再只住在** ``app/db/models/``
      包内（命令::

          cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"

      在 ``c21767d`` 上实测 **15** 条 = ``app/db/models`` **13** 条 +
      ``app/domain/prescription`` **2** 条（``__init__.py`` 的 ``from .exercises import (…)``
      与 ``templates.py`` 的 ``from .exercises import ImpactLevel``），level 分布
      ``{1: 15}``。**Task 1 期间那个「12 条」是绑定轮次的历史值、不要顺手改成 15**：
      ``6a2938f``（fix round 1 亲跑）与 ``7b84599``（fix round 5 复跑）两个 rev 上用
      ``git show`` 重算都仍是 **12** 条、且全部落在 ``app/db/models`` 包内；Task 2 主体
      ``3ea27cc`` 建出本子包后是 **14**，fix round 1 给 ``templates.py`` 补上那句 re-export
      后是 **15**（Plan02 账本 Ruling 106 的 CE-6）。
       ⚠️ **Task 4 落地后的当前值是 18 条**（同一条命令，在本 Task 的工作树上亲跑）=
       ``app/db/models`` **13** + ``app/domain/prescription`` **5**——``__init__.py`` 的
       ``from .exercises import (…)`` / ``from .match import (…)`` /
       ``from .templates import (…)`` 三句、``templates.py`` 的
       ``from .exercises import ImpactLevel``、``match.py`` 的 ``from .templates import (…)``，
       level 分布仍是 ``{1: 18}``（Task 3 结案时是 **16** = 13 + 3）。
       ⚠️ **Task 4 一次加了 2 条、不是 1 条**：简报 P4-A6 给出的那个「``match.py`` 若写相对
       导入之后全仓会变成几条」的预测**少算了一条**（按硬规矩 #74 不在这里复述那个数）——
       同一个 P4-A6 的第 1 项要求 ``prescription/__init__.py`` 重导出 4 个新名字，
       而那一句 ``from .match import (…)`` 自己就是一条 ``level == 1`` 的相对导入。
       故 domain 侧**没有 offender** 这个
       结论不变、而**理由变了**：不再是「domain 侧没有相对导入」，而是那 5 条折算成
       ``app.domain.prescription.exercises`` / ``….match`` / ``….templates``
       **三个**串、都命中白名单前缀 ``app.domain.``（亲跑：
       ``_absolute('exercises', 1, ('app', 'domain', 'prescription'))`` =
       ``'app.domain.prescription.exercises'``；``match.py`` 那一句同理折成
       ``'app.domain.prescription.templates'``）。``level == 2`` 在真仓里**今天仍不存在**
       （账本 Ruling 104 亲扫：Task 2 刻意选了绝对导入
       ``from app.domain.indicators import ITEM_BUCKET``，与既有 4 个 domain 模块同风格；
       Task 3 与 **Task 4** 沿用了同一个选择——``match.py`` 写的是
       ``from app.domain.stratify import MIN_VALID_COUNT, Layer`` 与
       ``from app.domain.indicators import WEAKNESS_ITEMS`` 两条绝对串，加
       ``from .templates import …`` 一条 ``level == 1``），
       但 ``app/domain/prescription/`` 这一层子包已经建出、Task 4 的 ``match.py`` 也已落地，
       **将来**谁在这个包深 3 的子包里写
       ``from ..indicators import X`` 它就开始正常出现，「一律放行」的写法会跟着变成真漏洞。
      折算之后（⚠️ **同一句写法在不同
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
        package = _package_of(py)
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for lineno, module, level, name in _imported_modules(tree):
            absolute = _absolute(module, level, package, name)
            if absolute is not None and _is_allowed(absolute):
                continue
            written = module or "<空模块名>"
            if level:
                target = "<上溯到顶层包 app 之外>" if absolute is None else absolute
                written = f"{'.' * level}{module} → {target}"
            offenders.append(f"{py.name}:{lineno}: {written}")

    _assert_not_empty(scanned)
    assert offenders == [], (
        "app/domain 是叶子层，import 必须落在白名单内"
        f"（{sorted(ALLOWED_MODULES)} + {ALLOWED_PACKAGE}.*）：\n" + "\n".join(offenders)
    )


def _dotted(node: ast.AST) -> str | None:
    """把一个表达式还原成点号串（``dt.datetime.now`` → ``"dt.datetime.now"``）。

    还原不出点号串的形态一律返回 ``None``，本守卫因此**放过**它们。四种形态的
    ``node.func`` 是什么，本机 Python 3.11.1 实跑（``ast.parse(s).body[0].value.func``）::

        f()()                                   ast.Call
        table[0]()                              ast.Subscript
        getattr(x, "now")()                     ast.Call
        __import__("datetime").datetime.now()   ast.Attribute(value=ast.Attribute(value=ast.Call))

    本函数只沿 ``ast.Attribute`` 下溯、走到 ``ast.Name`` 才收工，故上面四种都还原不出来。
    ``eval("…")`` 是**另一种**放过法：它的 ``node.func`` 是 ``ast.Name(id="eval")``、点号串
    还原得出 ``"eval"``，只是 ``eval`` 不在 :data:`FORBIDDEN_CALLS` 里。

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

    **为什么从子串改成 AST 节点匹配**（终审 A 的 M7）。**收益是「不再误报」，不是「多抓
    漏报」**——本节此前把方向写反了（它说 AST 侧「顺着 ``_dotted`` 追赋值」，而
    :func:`_dotted` 只还原调用表达式自身、代码里没有任何赋值追踪）。下面是合成树上的实测
    口径（**配方 fix round 5 补正**，Plan02 Ruling 68——改前这一段照字面做会得到**全红**）：
    把 ``DOMAIN`` **和** ``BACKEND`` 一起指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的
    合成树。``BACKEND`` 也必须改：:func:`_package_of` 里是 ``py.relative_to(BACKEND)``，
    只改 ``DOMAIN`` 会让第一条守卫抛 ``ValueError: … is not in the subpath of …``（fix
    round 5 亲跑）。树里要放 **≥ 5 个 ``.py``**（含探针文件自己），否则
    :func:`_assert_not_empty` 的空转守卫先响（``AssertionError: 只扫到 1 个 .py …``）、
    第二三条守卫一起变红。⚠️ **先跑一行已知三列全 GREEN 的干净对照**（探针内容只写
    ``x = 1`` 就够；fix round 5 亲跑它确实是 ``GREEN / GREEN / GREEN``）——没有这一行，
    「全红」既可能是本文件那三条守卫坏了、也可能是配方少了一项，两者不可区分（硬规矩
    #53）。逐条写进探针文件后分别调用三条守卫（fix round 1 首跑；fix round 5 用补正后的
    配方复跑，14 行 × 3 列 = 42 格逐格相符、0 处不符）::

        probe.py 的内容                                   G1 allow-list  G2 AST 时钟/open  G3 子串 IO
        _f = open; _f('x')                                GREEN          GREEN             GREEN
        def reopen(): …  然后 reopen()                     GREEN          GREEN             GREEN
        def open_ended(): …  然后 open_ended()             GREEN          GREEN             GREEN
        只有 docstring:「不要用 datetime.now()，也不要 open(」 GREEN          GREEN             GREEN
        open('x')                                         GREEN          RED               GREEN
        import builtins; builtins.open('x')               RED            RED               GREEN
        import datetime as dt; dt.datetime.now()           RED            RED               GREEN
        __import__("datetime").datetime.now()             GREEN          GREEN             GREEN
        __import__("os").listdir(".")                     GREEN          GREEN             GREEN
        __import__("builtins").open("x")                  GREEN          GREEN             GREEN
        getattr(__import__("datetime"), "datetime").now()  GREEN          GREEN             GREEN
        eval("__import__('datetime').datetime.now()")     GREEN          GREEN             GREEN
        def _f(x): return getattr(x, "now")()             GREEN          GREEN             GREEN
        def _f(table): return table[0]()                  GREEN          GREEN             GREEN

    第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 **fix round 2 新增**（Plan02
    Ruling 38）；fix round 2 把 14 行**全部重跑了一遍**，前 7 行的颜色逐字复现。fix round 5
    又用补正后的配方重跑一遍：**14 行 × 3 列 = 42 格逐格相符、0 处不符**，另加一行干净对照
    （探针只写 ``x = 1``）三列全 GREEN。同一次跑也复现了 :data:`FORBIDDEN_IO` 那句
    「0 vs 2」：第 9 行 ``__import__("os").listdir(".")`` 命中 **0** 个子串，对照组
    ``import os`` 换行 ``os.listdir('.')`` 命中 **2** 个（``import os`` / ``os.listdir``）。
    ⚠️ 反过来，照**补正前**的字面配方（只重定向 ``DOMAIN``、树里 1 个 ``.py``）跑，
    fix round 5 实测**15 行（14 行 + 干净对照行）× 3 列全 RED**：第一条守卫报 ``ValueError``、
    第二三条报 ``AssertionError: 只扫到 1 个 .py …``。所以那张表没错，坏的是配方
    （Plan02 Ruling 68）。

    * **误报没了**（真收益）：第 4 行。旧守卫是逐项 ``if c in src``（基线 ``e26347f`` 的
      ``test_domain_purity.py:50``），Plan 01 因此**不敢在 domain 的散文里写这些词**——
      那是让守卫反过来审查文档，而本仓的 docstring 恰恰要求把口径写全（硬规矩 #19）。
      AST 只看 ``ast.Call`` 节点，散文里怎么提都不响。
    * **``.`` 边界替代 ``\\b`` 正则**：第 2、3 行不被误抓，而第 6 行 ``builtins.open()``
      仍然被抓（:func:`_hit_forbidden_call`）。
    * **点号形态天然覆盖**：第 7 行由 :func:`_dotted` 还原成 ``"dt.datetime.now"``、命中
      ``datetime.now`` 那一项。但旧子串守卫这一种**也能撞上**（源码里就有子串
      ``datetime.now``），故**不是新增拦截力**。

    ⚠️ **本条守不住什么**（硬规矩 #39）：第 1 行 ``_f = open`` 再 ``_f('x')`` **三条守卫
    全绿**。``open`` 是内置名、不需要 import，故 G1 的白名单帮不上；:data:`FORBIDDEN_IO`
    里没有裸 ``open``，故 G3 的子串也帮不上；G2 拿到的 ``node.func`` 是
    ``ast.Name(id="_f")`` → 点号串 ``"_f"`` → 不命中 :data:`FORBIDDEN_CALLS`。
    ``now = datetime.now`` 再 ``now()`` 同理（那种写法 G1 会先因 ``import datetime`` 变红，
    但**红的原因不是这次调用**）。堵这一类需要数据流/别名分析，本仓不做。

    ⚠️ **「拿到工具必经 import」也不成立**（上表第 8–14 行，Plan02 Ruling 38）：
    ``__import__`` / ``eval`` / ``getattr`` 三个**内置名**都能在不写一条 ``ast.Import`` 的
    前提下拿到 ``datetime`` / ``os`` / ``builtins``，于是 G1 一声不响；G2 对
    ``__import__(…).datetime.now()`` / ``getattr(x, "now")()`` / ``table[0]()`` 还原不出
    点号串（见 :func:`_dotted`），对 ``eval(…)`` 还原得出 ``"eval"``、只是它不在
    :data:`FORBIDDEN_CALLS` 里；G3 的子串表里既没有 ``__import__`` 也没有 ``eval``——
    三条守卫**全绿**。

    ``__import__("os").listdir(".")`` 这一行尤其值得记住：``os.listdir`` 与 ``import os``
    **两个子串都在** :data:`FORBIDDEN_IO` 里，而写成这个形状后源码里**一个都不出现**
    （本机实跑：该探针命中的 ``FORBIDDEN_IO`` 子串数 = 0；对照组 ``import os`` 换行
    ``os.listdir(".")`` 命中 2 个），于是第三条子串守卫也一声不响——「不许读盘」这条立意
    被完整绕过。这七行不是待修的漏洞清单，而是本条守卫的**能力边界**：它守的是「直白地
    写出 ``datetime.now()`` / ``open()`` / ``os.listdir()``」，不守任何需要还原、求值或
    别名追踪才能看清的形态。要堵这一族就得把 ``__import__`` / ``eval`` / ``getattr`` 这些
    内置名本身列进封禁，代价是 domain 里连一个正常的 ``getattr(obj, "name", default)``
    都写不了——本仓不做，但必须写清楚（硬规矩 #39）。

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
