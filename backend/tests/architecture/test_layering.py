"""层间依赖方向的架构守卫（spec §3.3）。

spec §3.3 把依赖方向钉成**单向、不可逆**::

    api → services → domain
                  ↘ pipeline → adapters
    db ← services / pipeline

    domain 不依赖任何模块（叶子）

``app/seed/`` 不在这张图里：它是**仿真数据生成器**，属于「造出被试数据」的开发期工具，
位置在 ``pipeline`` 之外、之上。生产层（``pipeline`` / ``db``）反向 import 它，就意味着
「跑一次真实的每日批处理」需要「仿真数据生成器」在导入期就是可用的——而生成器带着
``numpy`` 的随机流、500 人的分布定标、以及 ``data/seed/`` 那套 CSV 契约。这不是风格问题：
它让生产路径的依赖图里出现一个本该只属于开发期的节点，将来把生成器换成真实数据源时，
生产代码要跟着改。

**本守卫落地时抓到的 4 处 offender**（基线 ``e26347f``，命令与输出::

    cd backend
    git grep -n "from app.seed" -- app/pipeline app/db app/domain
    # app/pipeline/backfill.py:234:    from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
    # app/pipeline/daily.py:689:       from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
    # app/pipeline/run_stratify.py:48: from app.seed.fitness import COLUMN_BY_ITEM
    # app/pipeline/run_stratify.py:49: from app.seed.generate import RANGES_FILENAME

四处都是「生产层为了拿一个**常量**而依赖生成器」：两个路径/URL 常量与两个词表常量。
Plan 02 Task 1 给它们各自建了唯一所有者（``app.config`` / ``app.refdata`` /
``app.domain.indicators``）之后本守卫转绿，此后它是**回归守卫**——挡住下一次
「顺手从 seed 里 import 一个现成的常量」。

**为什么用 AST 而不是 ``grep``**：``ast.walk`` 天然覆盖**函数内导入**。上面 4 处里有
2 处（``daily.py:689``、``backfill.py:234``）就写在 ``main()`` 的函数体内，按行扫源码
的文本匹配虽然也能撞上，但一旦有人把它改成 ``importlib.import_module("app.seed.generate")``
或加一层间接，文本匹配就静默失效，AST 也仍然抓得到前一种（``ast.Call`` 不在本守卫范围
内，见下方「本守卫不覆盖什么」）。

**本守卫不覆盖什么**（写清楚，免得下一个人以为它管得比实际宽）：

* ``app/domain/`` 的 import 由 :mod:`tests.architecture.test_domain_purity` 的
  allow-list 守卫管——那条是**白名单**，比本条的黑名单紧得多，domain 里出现
  ``app.seed`` 会先被它抓。本文件仍把 ``app/domain`` 一起扫，是为了让「依赖方向」
  这件事在**一个地方**能被一次看完（``SCANNED_DIRS`` 加一项即可）。
* ``importlib`` 动态导入、字符串拼接出来的模块名。
* ``app/adapters/``：spec §3.3 里它是 ``pipeline`` 的被依赖方，今天没有任何理由
  import ``app.seed``；等真出现理由了再把目录加进 ``SCANNED_DIRS``。
"""
import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[2]
APP = BACKEND / "app"

#: 被扫的生产层目录。``app/domain`` 一并扫：它由 allow-list 守卫更紧地管着，
#: 列在这里只是让「谁能依赖 app.seed」这个问题有一个统一的取景框。
SCANNED_DIRS = ("pipeline", "db", "domain")

#: 生产层不得依赖的模块前缀
FORBIDDEN_PREFIX = "app.seed"


def _py_files(relative_dir: str) -> list[pathlib.Path]:
    """一个生产层目录下的全部 ``.py``，按路径升序（报告顺序因此稳定可复现）。"""
    root = APP / relative_dir
    # Path.rglob() 对不存在的目录静默返回空，缺了这行守卫会空转全绿
    assert root.is_dir(), f"目录缺失，架构测试将空转: {root}"
    return sorted(root.rglob("*.py"))


def _package_of(py: pathlib.Path) -> tuple[str, ...]:
    """``py`` 所在的**包**，以 ``backend/`` 为根的段。

    ``app/pipeline/x.py`` → ``("app", "pipeline")``；``app/db/models/x.py`` 与
    ``app/db/models/__init__.py`` **都**是 ``("app", "db", "models")``——去掉扩展名后最后
    一段在两种情况下都是「模块名」（``x`` / ``__init__``），故一律取 ``parts[:-1]``，
    这正是 Python 自己的 ``__package__``。
    """
    return py.relative_to(BACKEND).with_suffix("").parts[:-1]


def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。

    与 :func:`importlib.util.resolve_name` 同口径。⚠️ 它的第二个参数是 ``__package__``、
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


def _imported_modules(tree: ast.AST, package: tuple[str, ...]):
    """yield ``(lineno, 完整模块串)``；``ast.walk`` 因此覆盖函数内导入。

    相对导入（``node.level > 0``）**不再一律跳过**，而是先经 :func:`_absolute` 折算成绝对
    串。此前这里写的是 ``if node.level: continue``，理由写的是「它只可能落在**同一个包
    内**」——那句只对 ``level == 1`` 成立。``level >= 2`` 会**跨包**，而本守卫要抓的
    ``app.seed`` 恰恰在包外：

    * ``app/pipeline/x.py`` 里的 ``from ..seed import generate``（``level == 2``）解析到
      ``app.seed.generate``；
    * ``app/db/models/x.py`` 里的 ``from ...seed import generate``（``level == 3``）同样
      解析到 ``app.seed.generate``。**这一档是 Plan 02 Task 1 的拆包新造出来的**：拆包前
      ``app/db/models.py`` 的 ``level == 2`` 才到 ``app``，拆包后要 ``level == 3``——
      模块深度多了一层，于是「三级相对导入」从不可达变成可达。

    合成树实测（把 ``BACKEND`` / ``APP`` 指到 ``$env:TEMP`` 下一棵形状与 ``backend/app``
    相同的树，逐条写进探针文件后直接调用本测试函数）：上述两种写法**改前全绿**、改后全红。

    而 ``app/db/models/`` 包内**真实存在**的那批相对导入，折算后是 ``app.db.models._shared``
    / ``app.db.models.organisation`` 一类，不以 ``app.seed`` 开头，**仍然绿**。它们的全貌用
    这条命令数（本轮亲跑：12 条、全部 ``level == 1``、全部落在 ``app.db.models`` 包内）::

        cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"

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


def _is_forbidden(module: str) -> bool:
    """按**完整模块串**判前缀，且只在 ``.`` 边界上匹配。

    边界是必需的：裸 ``startswith("app.seed")`` 会把 ``app.seedling`` 这类
    （今天不存在、但将来可能有的）合法模块误判成 offender。
    """
    return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")


def test_absolute_folding_matches_resolve_name():
    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。

    **这一条与 :mod:`tests.architecture.test_domain_purity` 里的同名测试是「两份重复守卫的
    两份回归测试」**（硬规矩 #51）：``_absolute`` 在两个文件里各有一份、逐字相同，故回归
    测试也必须各有一份——只留一份的话，另一份 ``_absolute`` 被改坏时**没有任何测试会红**。
    下面「复现命令」那一段给了实测：只变异本文件的 ``_absolute``，purity 那条**保持绿**。

    **判据锚在 ``resolve_name`` 上、不锚在期望值表上**：表是某个人某一次跑出来的结果，抄进
    测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；``resolve_name``
    是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格现场调一次
    ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``（越界档，
    Plan02 Ruling 35）。

    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：

    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
      ``("seed", 5, ("app", "db", "models"), "generate")`` 折成 ``app.db.seed`` 而不是
      ``None`` → 本测试红。
    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
      ``app.seed`` → 本测试红。
    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
      模块，Plan02 Ruling 36）→ 末尾那一段红。

    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异
    各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条**保持绿**——
    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值
    也是实跑的：越界档报 ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =
    'app.db.seed'``（而 ``resolve_name('.....seed', 'app.db.models')`` 抛 ``ImportError``）、
    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。

    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内
    真实存在的那 12 条 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被
    :func:`_is_forbidden` 放过。⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")``
    折成 ``app.db.seed``——**在 ``app.seed`` 前缀下是 GREEN**（它上溯一层只到 ``app.db``），
    而在 purity 的白名单下是 RED：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份
    回归测试的期望颜色列**不相同**，这不是抄错。

    **本测试守不住什么**（硬规矩 #39）：

    * ``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内：谁把它改成返回
      「模块名」而不是「包名」，本测试**照样全绿**，而守卫会假绿（``app/db/models/x.py``
      里的 ``from ...seed import …`` 会折成 ``app.db.seed``、不再以 ``app.seed`` 开头）。
      那一档今天只有 :func:`_absolute` docstring 里的实跑举例（Plan02 Ruling 37）在交代。
    * 它不扫真仓文件，故「``FORBIDDEN_PREFIX`` 取值本身对不对」仍只由
      :func:`test_production_layers_never_import_app_seed` 看着，两条判据互不覆盖。
    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
    """
    # 就地 import：模块级 import 会改动本文件的 <module-level>，而本轮的改动面被钉死在
    # 「新增这一条测试函数」之内（Plan02 Ruling 46）。
    import importlib.util

    #: ``(module, level, package, name, 期望颜色)``。以 **AST 形状**为参数，不用「``from …``
    #: 的字面写法」当唯一标识——同一句写法在不同包深下折算到不同的地方（Plan02
    #: Ruling 41/45）。期望颜色是**判据**（本文件的 ``app.seed`` 前缀语义），不是折算结果。
    cases = [
        # level == 0：本来就是绝对串，原样返回
        ("app.seed.generate", 0, ("app", "domain"), "", "RED"),
        # level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）；真仓 app/db/models/ 就是这一档
        ("_shared", 1, ("app", "db", "models"), "", "GREEN"),
        ("", 1, ("app", "db", "models"), "_shared", "GREEN"),
        # level == 2：跨包指向 app.seed，真 offender
        ("seed.generate", 2, ("app", "pipeline"), "", "RED"),
        # module 为空：被导入的模块名住在 node.names 里（Ruling 36）
        ("", 2, ("app", "pipeline"), "seed", "RED"),
        ("", 2, ("app", "db"), "seed", "RED"),
        ("", 2, ("app", "db", "models"), "seed", "GREEN"),
        ("", 2, ("app", "domain"), "seed", "RED"),
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
        verdict = "RED" if got is None or _is_forbidden(got) else "GREEN"
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
    got = [module for _lineno, module in _imported_modules(tree, package)]
    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
            for alias in ("seed", "pipeline")]
    assert got == want, f"一名一条的展开失效: {got} != {want}"


def test_production_layers_never_import_app_seed():
    """``app/pipeline`` / ``app/db`` / ``app/domain`` 不得 import ``app.seed``。

    offender 一次性报全（``assert offenders == []``）：逐处 assert 的话第一个红会盖住
    后面的，而迁移这四处是一次性的活，一次看全才不必跑四遍。
    """
    scanned: list[pathlib.Path] = []
    offenders: list[str] = []
    for relative_dir in SCANNED_DIRS:
        for py in _py_files(relative_dir):
            scanned.append(py)
            tree = ast.parse(py.read_text(encoding="utf-8"))
            where = py.relative_to(BACKEND).as_posix()
            for lineno, module in _imported_modules(tree, _package_of(py)):
                if module is None:
                    offenders.append(f"{where}:{lineno}: 相对导入上溯到顶层包 app 之外")
                elif _is_forbidden(module):
                    offenders.append(f"{where}:{lineno}: {module}")

    # 空转守卫：目录被搬空 / 拼错时 offenders 恒为 []，测试会假绿。
    # 文件数实测（在**仓库根**跑，一条命令数完三个目录；本轮亲跑）::
    #
    #     python -c "import pathlib,collections; c=collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain')); print(sorted(c.items()), sum(c.values()))"
    #
    #   基线 e26347f          → [('db', 4), ('domain', 6), ('pipeline', 7)] 17
    #   Task 1 拆包后 ad1d190 → [('db', 11), ('domain', 6), ('pipeline', 7)] 24
    #
    # 交叉核对（同样在仓库根跑，逐文件名可比）::
    #
    #     git ls-tree -r --name-only <commit> -- backend/app/pipeline backend/app/db backend/app/domain
    #
    # 下界取 8 而不是实测的 17 / 24：拆包与合并模块都会正常地改变文件数，写死实测值会让
    # 一次合法重构变红。**代价（硬规矩 #39）**：8 只挡得住「三个目录被一起搬空」——单个
    # 目录被搬空时仍剩 **13…18** 个 .py（24 − 11(db) = 13、24 − 7(pipeline) = 17、
    # 24 − 6(domain) = 18，由上面那条 Counter 命令本轮亲跑得出），本断言拦不住。
    # 那一档的兜底是：``domain`` 由
    # ``tests/architecture/test_domain_purity.py`` 自己那条 ``>= 5`` 空转守卫看着；
    # ``pipeline`` / ``db`` 被搬空时 ``tests/pipeline/`` 与 ``tests/db/`` 会在**收集期**
    # 就 ImportError（它们直接 ``from app.pipeline import …`` / ``from app.db import …``）。
    # 目录被**整个删掉**则由 :func:`_py_files` 里的 ``root.is_dir()`` 当场拦下。
    assert len(scanned) >= 8, f"只扫到 {len(scanned)} 个 .py，目录可能被搬空: {SCANNED_DIRS}"

    assert offenders == [], (
        f"生产层依赖了仿真数据生成器 app.seed（spec §3.3 依赖方向单向不可逆）：\n"
        + "\n".join(offenders)
    )
