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

**Plan 03 Task 1 给 ``SCANNED_DIRS`` 加了第四项 ``"api"``**——这是本项目第一次有 HTTP 层
（``app/api/`` 与 ``app/main.py`` 在此之前都不存在）。加它有两个后果，都在本文件里落地：

1. :func:`test_production_layers_never_import_app_seed` 的扫描面从 **35** 个 ``.py``
   变成 **38** 个（pipeline 8 + db 11 + domain 16 + **api 3**），于是那条
   ``len(scanned)`` 的空转下界一次性抬到位（``>= 8`` → ``>= 18``，取法见该断言上方的
   推导；账本 S6 的裁定是「下界由 Task 1 一次抬完，后面 8 个 Task 不再动它」）。
2. ``api`` 的**依赖方向**由新增的
   :func:`test_api_layer_dependency_direction_is_one_way` 定死：``api`` 可以向下
   import ``db`` / ``domain`` / ``pipeline`` / ``adapters`` / ``refdata*`` / ``config`` /
   ``notify``，**反向一律禁止**（``pipeline`` / ``db`` / ``domain`` 里出现 ``app.api``
   就是 offender）。

⚠️ **``app/main.py`` 不在 ``SCANNED_DIRS`` 的任何一项里**：它是 ``app/`` 根下的模块、
不属于任何一层子目录，而 ``_py_files`` 只按目录扫。这是有意的——``main.py`` 是应用装配点，
它**必须**能 import ``app.api``（``uvicorn app.main:app`` 的入口就在那里），
把它归进「不得依赖 api」的那一圈会当场自相矛盾。它在依赖图里的位置是 ``api`` **之上**。

⚠️ **``app/domain/`` 的纯净性守卫不会因为有 ``api`` 这一层而误判**（Plan 03 Task 1 实测）：
:mod:`tests.architecture.test_domain_purity` 的 ``DOMAIN`` 是一条**硬编码路径**
（``parents[2] / "app" / "domain"``）、``_domain_files()`` 只 ``rglob`` 它自己那一个目录，
既不扫 ``app/`` 下的兄弟目录、也不从 ``SCANNED_DIRS`` 这类清单里读。故 ``app/api/``
里 import ``fastapi`` / ``pydantic`` 与那份白名单（``ALLOWED_MODULES`` 六项）完全无关。
两份守卫**各自**发现目录的机制是不同的：本文件用一份目录名清单，purity 用一条路径常量；
本 Task 只改了前者，因为要加的层只属于前者。
"""
import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[2]
APP = BACKEND / "app"

#: 被扫的生产层目录。``app/domain`` 一并扫：它由 allow-list 守卫更紧地管着，
#: 列在这里只是让「谁能依赖 app.seed」这个问题有一个统一的取景框。
#: ``api`` 自 Plan 03 Task 1 起在列（本项目第一次有 HTTP 层）；它的依赖方向由
#: :func:`test_api_layer_dependency_direction_is_one_way` 另外定死。
#: ⚠️ **``"seed"`` 不得加进来**：``app/seed/**`` 自己就 import ``app.seed``，
#: 加进去会让 :func:`test_production_layers_never_import_app_seed` 抓到一堆自我依赖。
#: ⚠️ **``"adapters"`` 今天也不在列**，理由见模块 docstring 的最后一条。
SCANNED_DIRS = ("pipeline", "db", "domain", "api")

#: 生产层不得依赖的模块前缀
FORBIDDEN_PREFIX = "app.seed"

#: ``api`` 层自己的前缀。反向依赖判定的主语。
API_PREFIX = "app.api"

#: ``api`` 层允许 import 的 ``app.*`` 前缀（``.`` 边界匹配，见 :func:`_is_api_allowed`）。
#:
#: 计划 Task 1 的 Interfaces 一节逐字给的是「``api`` 可以 import ``db`` / ``domain`` /
#: ``pipeline`` / ``refdata*`` / ``config`` / ``notify``；反向一律禁止」。本清单是它的
#: 落地，另加两项、各有一条理由：
#:
#: * ``app.api`` —— 层内互相依赖（``routers`` → ``deps`` / ``errors`` / ``schemas``）。
#:   不加它的话 ``app/api/routers/catalog.py`` 里一句 ``from app.api.crud import …``
#:   就会红，而那显然是合法的。
#: * ``app.adapters`` —— spec §3.3 里它在 ``pipeline`` **下面**（``pipeline → adapters``），
#:   故 ``api → adapters`` 不是反向。它今天用不上，但 Task 9 的
#:   ``POST /api/pipeline/run-daily`` 会撞上：``app.pipeline.daily.run_daily`` 的第四个
#:   参数是**适配器实例**（``daily.py`` 的 CLI 那一行是
#:   ``run_daily(session, semester.id, args.date, build_adapter())``），
#:   而 ``build_adapter`` 住在 ``app.adapters.factory``。不把它列进来的话，
#:   Task 9 要么改本清单、要么在端点里绕过工厂手搓适配器（那才是真的坏味道）。
#:
#: ⚠️ ``refdata*`` 按 ``.`` 边界**展开成三个具体串**，不用裸前缀：``app.refdata_prescription``
#: 既不等于 ``app.refdata``、也不以 ``app.refdata.`` 开头（中间是下划线），
#: 故裸 ``startswith("app.refdata")`` 与「按 ``.`` 边界匹配」在这里给出**不同**的答案。
#: 展开成三个串之后，「加一个 ``app/refdata_xxx.py``」必须是一次显式的清单修改——
#: 与 :data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 里
#: 「``numpy`` 只列裸名、不列 ``numpy.*``」同一个立意。
#: ``app.refdata_alerts`` 由 Task 6 建、**今天还不存在**：allow-list 里列一个尚不存在的
#: 模块是安全的（它是许可、不是断言），而列在这里正是为了兑现「后面 8 个 Task 不再动本文件」。
#:
#: ⚠️ **刻意不在清单里的两个**：``app.seed``（已由
#: :func:`test_production_layers_never_import_app_seed` 挡着，本清单是第二道）与
#: ``app.main``——后者在 ``api`` **之上**（它是装配 ``api`` 的那个人），
#: ``api`` 反过来 import 它就是导入环。:func:`test_api_allow_list_matches_on_dot_boundaries`
#: 把这两格都列成 RED。
API_ALLOWED_PREFIXES = (
    "app.api",
    "app.db",
    "app.domain",
    "app.pipeline",
    "app.adapters",
    "app.config",
    "app.notify",
    "app.refdata",
    "app.refdata_prescription",
    "app.refdata_alerts",
)


def _is_api_allowed(module: str) -> bool:
    """一个**绝对** ``app.*`` 模块串是否落在 :data:`API_ALLOWED_PREFIXES` 内。

    与 :func:`_is_forbidden` 同一个 ``.`` 边界口径（等于，或以 ``前缀 + "."`` 开头）：
    裸 ``startswith`` 会把 ``app.dbx`` / ``app.refdatax`` 这类（今天不存在、将来可能有的）
    模块误判成合法。
    """
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in API_ALLOWED_PREFIXES
    )


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

    合成树实测（把 ``BACKEND`` / ``APP`` **两个都**指到 ``$env:TEMP`` 下一棵形状与
    ``backend/app`` 相同的树：:func:`_package_of` 里是 ``py.relative_to(BACKEND)``，只改
    ``APP`` 会抛 ``ValueError: … is not in the subpath of …``；且 ``pipeline`` / ``db`` /
    ``domain`` 三个目录合计要有 **≥ 8 个 ``.py``**（含探针文件自己），否则本文件那条
    ``len(scanned) >= 8`` 的空转守卫先响（``AssertionError: 只扫到 1 个 .py …``）、探针的
    颜色不可解释，故**必须先跑一行已知 GREEN 的干净对照**（探针只写 ``x = 1``；上面四条
    都是 fix round 5 亲跑）。同款配方在 :mod:`tests.architecture.test_domain_purity` 那一份
    里下界是 ``>= 5``、重定向的是 ``DOMAIN`` **和** ``BACKEND``，两处 fix round 5 已互相
    对齐（Plan02 Ruling 68／硬规矩 #51/#53）。逐条写进探针文件后直接调用本测试函数）：
    上述两种写法**改前全绿**、改后全红。

    而 ``app/db/models/`` 包内**真实存在**的那批相对导入，折算后是 ``app.db.models._shared``
    / ``app.db.models.organisation`` 一类，不以 ``app.seed`` 开头，**仍然绿**。它们的全貌用
    这条命令数。**条数必须绑时点**（Plan02 账本 Ruling 106 的 CE-6）：**Task 1** 的
    fix round 1（``6a2938f``）亲跑、fix round 5（``7b84599``）复跑都是同一个结果——
    **12 条**、全部 ``level == 1``、全部落在 ``app.db.models`` 包内；这两个 rev 上用
    ``git show`` 重算今天仍是 12，故这句历史陈述**在它绑定的时点上是真的、不要改成 15**。
    ⚠️ **而全仓的当前值已经不是 12**：Plan 02 Task 2 建出 ``app/domain/prescription/``
    之后，在 ``c21767d`` 上同一条命令数出 **15** 条 = ``app/db/models`` **13** +
    ``app/domain/prescription`` **2**、level 分布 ``{1: 15}``（主体 ``3ea27cc`` 是 14，
    fix round 1 给 ``templates.py`` 补上那句 re-export 后是 15），即「全部落在
    ``app.db.models`` 包内」这半句**只对那 13 条成立、对全仓已不成立**::

        cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"

    ⚠️ **Task 4 落地后的当前值是 18 条**（同一条命令，在本 Task 的工作树上亲跑）=
    ``app/db/models`` **13** + ``app/domain/prescription`` **5**，level 分布仍是
    ``{1: 18}``。那 5 条是：``__init__.py`` 的 ``from .exercises import (…)`` /
    ``from .match import (…)`` / ``from .templates import (…)`` 三句（``.templates`` 那一句是
    Task 3 加的、``.match`` 那一句是 Task 4 加的，故 Task 3 结案时全仓是 **16**）、
    ``templates.py`` 的
    ``from .exercises import ImpactLevel``、``match.py`` 的 ``from .templates import (…)``
    （Task 4 加的那一条）。⚠️ **Task 4 一次加了 2 条、不是 1 条**：简报 P4-A6 给出的那个
    「``match.py`` 若写相对导入之后全仓会变成几条」的预测**少算了一条**（按硬规矩 #74
    不在这里复述那个数）——同一个 P4-A6 的第 1 项要求 ``prescription/__init__.py``
    重导出 4 个新名字，而那一句 ``from .match import (…)`` 自己就是一条 ``level == 1``
    的相对导入。**三轮都刻意选绝对导入**
    （Task 2 的 ``from app.domain.indicators import ITEM_BUCKET``、Task 4 的
    ``from app.domain.stratify import …``），故 ``level == 2`` 到今天仍不存在
    （Plan02 账本 Ruling 104）。
    那 15 条里 ``module`` 为空的形状仍是 **1 条**（分母从 12 变 15、**分子不变**：
    ``6a2938f`` / ``7b84599`` / ``3ea27cc`` / ``c21767d`` 四个 rev 上都实扫过，
    ``app/domain/prescription`` 那 2 条的 ``module`` 都是 ``'exercises'``、非空）：
    ``app/db/models/__init__.py`` 里那句 ``from . import feedback, prescription``
    （⚠️ **不写裸行号**：Task 2 按 Ruling 90 改该文件 docstring 时把它从 ``:74`` 推到
    ``:82``，引用它的两处没跟着改，账本 Ruling 106 的 CE-7；可 grep 的原文是
    ``from . import feedback, prescription  # noqa: F401``，``git grep -n "import feedback"
    -- backend/app`` 只命中这一处）。上面那条命令在 ``c21767d`` 上打出来的**第 7 行**是
    ``app/db/models/__init__.py 82 1 None``——**序数 7 在那四个 rev 上都没变**（该文件恒有
    7 条相对导入、``module=None`` 那条恒排最后，且它在 ``sorted()`` 下排全仓第一），变的
    只是行号；Windows 上 ``pathlib`` 打出的分隔符是反斜杠
    （``app\\db\\models\\__init__.py 82 1 None``），分隔符随平台、序数与数字不随。
    它是**一个节点、两个名字、两个模块**，故
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
    :mod:`tests.architecture.test_domain_purity` 各一条 ``test_absolute_folding_matches_resolve_name``。

    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
      ``("seed", 5, ("app", "db", "models"), "generate")`` 折成 ``app.db.seed`` 而不是
      ``None`` → 本测试红。
    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
      ``app.seed`` → 本测试红。
    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
      模块，Plan02 Ruling 36）→ 末尾那一段红。

    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。fix round 3 实测
    三种变异各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条
    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。
    断言里印出来的折算值也是实跑的：越界档报
    ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =
    'app.db.seed'``（而 ``resolve_name('.....seed', 'app.db.models')`` 抛 ``ImportError``）、
    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。

    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内
    真实存在的那批 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被
    :func:`_is_forbidden` 放过。**这批的条数绑时点**（Plan02 账本 Ruling 106 的 CE-6）：
    **Task 1** 的 fix round 1（``6a2938f``）亲跑数出 **12** 条、fix round 5（``7b84599``）
    复跑仍是 **12** 条，全部 ``level == 1``、全部落在 ``app.db.models`` 包内（两个 rev 上
    重算今天仍是 12，故这两句历史陈述**是真的、不要改成 15**）。⚠️ **而全仓的当前值不是
    12**：Plan 02 Task 2 建出 ``app/domain/prescription/`` 之后，在 ``c21767d`` 上是
    **15** 条 = ``app/db/models`` **13** + ``app/domain/prescription`` **2**、level 分布
    ``{1: 15}``，故「全部落在 ``app.db.models`` 包内」这半句**只对那 13 条成立**、对全仓
    已不成立。⚠️ **Task 4 落地后全仓是 18 条**（``app/db/models`` 13 +
    ``app/domain/prescription`` 5，level 分布 ``{1: 18}``；逐条清单与命令见
    :func:`_imported_modules` 的 docstring）。

    **本绿档的主语是「``app/db/models`` 包内那批」**（硬规矩 #56）：12 条与 13 条两个时点
    它都在场、颜色都是 GREEN（亲跑 ``_is_forbidden('app.db.models._shared') is False``）。
    domain 侧那批（Task 4 之后是 **5** 条）折算成 ``app.domain.prescription.exercises`` /
    ``….match`` / ``….templates`` **三个**串，在**本文件**的判据下同样
    GREEN（不以 ``app.seed`` 开头，亲跑 ``_is_forbidden(...) is False``）；在
    :mod:`tests.architecture.test_domain_purity` 那一份的判据下也 GREEN（命中白名单前缀
    ``app.domain.``）。两份颜色相同、判据不同，这不是抄错。

    **矩阵第 9 行是 fix round 5 新加的绿档**（Plan02 Ruling 67）：
    ``app/domain/prescription/match.py`` 里**假如**写 ``from ..indicators import X``——
    包深 3 → **两个点**才上溯到 ``app.domain``，故 ``level == 2``（**不是** ``level == 1``）。
    ⚠️ **Task 4 落地后这一格仍是「前瞻」**：``match.py`` 实际写的是
    ``from app.domain.stratify import …`` / ``from app.domain.indicators import …``
    两条绝对串加 ``from .templates import …`` 一条 ``level == 1``，故真仓到今天为止
    **没有任何 ``level == 2`` 的相对导入**（Plan02 账本 Ruling 104）。fix round 5 亲跑::

        _package_of(BACKEND / 'app/domain/prescription/match.py')
            = ('app', 'domain', 'prescription')
        _absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')
            = 'app.domain.indicators'
        resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'
        _is_forbidden('app.domain.indicators') = False  -> 本文件（layering 侧）判 GREEN

    **放行理由与 purity 那一份不同**：本文件放行它是因为它**不以 ``app.seed`` 开头**；
    :mod:`tests.architecture.test_domain_purity` 那一份放行它是因为它**命中白名单前缀
    ``app.domain.``**。两份这一格颜色相同、判据不同，这不是抄错（硬规矩 #56）。

    ⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")``
    折成 ``app.db.seed``——**在 ``app.seed`` 前缀下是 GREEN**（它上溯一层只到 ``app.db``），
    而在 purity 的白名单下是 RED：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份
    回归测试的期望颜色列**不相同**，这不是抄错。

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
    * 它扫真仓，但扫的是「折算与 ``resolve_name`` 是否一致」、**不是**「折算结果是否以
      ``app.seed`` 开头」：真仓今天一条 offender 都没有（(c)），故「``FORBIDDEN_PREFIX``
      取值本身对不对」仍只由 :func:`test_production_layers_never_import_app_seed` 看着，
      判颜色这件事只有手写矩阵的 RED 格与那条守卫在做，两条判据互不覆盖。
    * 矩阵是有限的 12 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
    """
    # 就地 import：模块级 import 会改动本文件的 <module-level>，故这条测试自 fix round 3
    # 起就把 import 留在函数体内、改动面也一直钉死在「这一条测试函数 + docstring」
    # 之内（Plan02 Ruling 46/57）。
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
        # **Task 1 fix round 5 为 Task 4 的形状埋的一格**（fix round 5 新加，Plan02 Ruling 67；
        # ⚠️ 本行此前把这一格的归属记错了**两处**——它既不是那个 Task 加的、也不是那个 Task
        # 的形状；Plan02 账本 P4-A6 的第 ③ 项。被撤销的写法按硬规矩 #74 不再逐字复述）：
        # app/domain/prescription/match.py 里**假如**写 `from ..indicators import X`——
        # 包深 3 → 两个点才上溯到 app.domain，故 level == 2。
        # 折成 app.domain.indicators；本文件（layering 侧）判的是 app.seed 前缀，
        # _is_forbidden('app.domain.indicators') = False → 不以 app.seed 开头 → GREEN。
        # ⚠️ 与 test_domain_purity.py 同一格的 GREEN **理由不同**（那一份是命中白名单前缀
        # app.domain.）：颜色相同、判据不同，这不是抄错（硬规矩 #56）。
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
    # ⚠️ 本段刻意**不复用** :func:`_imported_modules`：那个生成器已经把折算做完了，
    # 拿不到 (module, level, name) 三个原始入参，也就无法与 resolve_name 对拍。
    #
    # ⚠️ **它是那 12 格矩阵的补充、不是替代**（Task 4 实测的理由，两份守卫同一段）：真仓今天
    #   (a) 没有任何 level >= 2 的相对导入（Task 2 / 3 / 4 三轮都刻意选了绝对导入，
    #       Plan02 账本 Ruling 104），
    #   (b) 没有任何越界档（resolve_name 抛 ImportError、_absolute 必须返回 None 那一档），
    #   (c) 没有任何 offender（真仓里没有一句 import app.seed，本文件判 RED 的格子一个也不存在）。
    # 这三类**只有手写的矩阵能提供**。Ruling 56 当初把「换成全仓扫描」的时机定在
    # 「level == 2 的**合法**相对导入开始真实出现」之后，而那个前提到今天仍未成立；
    # 删掉矩阵会让 _absolute 的越界分支与 _is_forbidden 的 RED 判定同时失去守卫
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
        for node in ast.walk(real_tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue  # 绝对串不经 _package_of / _absolute 的折算，本段只对拍相对导入
            # 一个节点可以带多个名字（`from . import feedback, prescription`），
            # 逐个展开成多次折算（Plan02 Ruling 36）
            for name in ([a.name for a in node.names] if not node.module else [""]):
                relative_seen += 1
                module = node.module or ""
                rel = "." * node.level + (module or name)
                pkg_str = ".".join(got_pkg)
                try:
                    want = importlib.util.resolve_name(rel, pkg_str)
                except ImportError:
                    want = None
                got = _absolute(module, node.level, got_pkg, name)
                folded.add("<越界>" if got is None else got)
                if got != want:
                    real_offenders.append(
                        f"{where} 里的 from {rel} import …：_absolute({module!r}, "
                        f"{node.level}, {got_pkg!r}, {name!r}) = {got!r}，而 "
                        f"resolve_name({rel!r}, {pkg_str!r}) = {want!r}"
                    )
    # 空转守卫（BACKEND 指错 / 真仓被搬空时上面那个循环一条都不跑、offenders 恒为 []）。
    # 三个下界与五个折算串都是**字面量**（硬规矩 #35，不从被测函数反推）：
    #   40 = backend/ 下 .py 的个数下界（**Plan 02 Task 4 落地时实测 69**——那个数绑的是
    #        那一个时点，⚠️ **不要把它改成今天的值**：本行是「下界的取法说明」，
    #        改成当前值会让下界与实测贴死、一次合法重构就红）；
    #        ⚠️ **Plan 03 Task 9 结案时的当前值是 130**（app 82 + tests 47 + scripts 1，
    #        命令：`cd backend; python -c "import pathlib; print(len(pathlib.Path('.').rglob('*.py')))"`）；
    #   16 = 全仓相对导入的条数下界（**Plan 02 Task 4 落地时实测 18**，命令见
    #        _imported_modules 的 docstring；⚠️ 同上，那个 18 绑的是 Task 4 的时点。
    #        ⚠️ **Plan 03 Task 9 结案时的当前值是 38**）；
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
    # ⚠️ 这两格是**合成的** level == 2 / level == 3 导入，真仓里不存在（见上面 (a)），
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
        "它返回**模块路径**，于是 app/db/models/x.py 里的 from ...seed import … 折成 "
        "app.db.seed、不再以 app.seed 开头 → 本守卫假绿（test_domain_purity.py 那一份同理："
        "app/domain/x.py 里的 from ..seed import … 折成 app.domain.seed、命中白名单前缀 "
        "app.domain.），而在本段断言加上之前，这么改一次全量测试都照样通过：\n"
        + "\n".join(pkg_offenders)
    )


def test_production_layers_never_import_app_seed():
    """``app/pipeline`` / ``app/db`` / ``app/domain`` / ``app/api`` 不得 import ``app.seed``。

    offender 一次性报全（``assert offenders == []``）：逐处 assert 的话第一个红会盖住
    后面的，而迁移这四处是一次性的活，一次看全才不必跑四遍。

    ⚠️ ``api`` 自 Plan 03 Task 1 起被本条一起扫（``SCANNED_DIRS`` 的第四项），
    而它**从来没有**依赖 ``app.seed`` 的理由：HTTP 层要的是「库里的数据」与
    「domain 的纯函数」，仿真数据生成器是开发期工具。故本条对 ``api`` 是
    **先天的回归守卫**（落地当天就绿），它的价值在于挡住将来某个人为了造演示数据
    而在端点里写一句 ``from app.seed.generate import …``——那个形状在本仓有前科，
    正是本文件 docstring 开头列的那 4 处 offender。
    （演示数据的所有者是计划 Task 2 的 ``app/demo_data.py``，而它**不在**
    :data:`API_ALLOWED_PREFIXES` 里，故那道口子由
    :func:`test_api_layer_dependency_direction_is_one_way` 另外挡着。）
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
    # 文件数实测（在**仓库根**跑，一条命令数完全部目录；fix round 1 亲跑）::
    #
    #     python -c "import pathlib,collections; c=collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain')); print(sorted(c.items()), sum(c.values()))"
    #
    #   基线 e26347f          → [('db', 4), ('domain', 6), ('pipeline', 7)] 17
    #   Task 1 拆包后 ad1d190 → [('db', 11), ('domain', 6), ('pipeline', 7)] 24
    #   Plan02 Task 3 结案 3473dc6 → [('db', 11), ('domain', 9), ('pipeline', 7)] 27
    #   Plan02 Task 4 建 match.py 后 → [('db', 11), ('domain', 10), ('pipeline', 7)] 28
    #     （domain 那 10 个 = __init__ / derive / indicators / percentile / stratify / tables
    #      + prescription/{__init__,exercises,match,templates}；本行是本 Task 亲跑的）
    #   Plan02 结案 / Plan03 基线 69b4218 → [('db', 11), ('domain', 16), ('pipeline', 8)] 35
    #     （domain 涨到 16 = 那 6 个 + prescription/{__init__, assembler, exercises,
    #      intensity, match, override, safety, templates, triggers, weekly} 10 个；
    #      pipeline 涨到 8 = 那 7 个 + prescription_stage.py）
    #   **Plan03 Task 1 建 app/api/ 后（本 Task 亲跑，同一条命令加上 'api'）** →
    #     [('api', 3), ('db', 11), ('domain', 16), ('pipeline', 8)] **38**
    #
    # 交叉核对（同样在仓库根跑，逐文件名可比）::
    #
    #     git ls-tree -r --name-only <commit> -- backend/app/pipeline backend/app/db backend/app/domain backend/app/api
    #
    # 下界取 **18** 而不是实测的 17 / 24 / 27 / 28 / 35 / 38：拆包与合并模块都会正常地改变
    # 文件数，写死实测值会让一次合法重构变红。**18 的取法是「四个目录各自的地板之和」**
    # = pipeline 5 + db 5 + domain 5 + api 3（Plan 03 Task 1 起 SCANNED_DIRS 是四项）：
    #
    #   * 5 沿用 :mod:`tests.architecture.test_domain_purity` 的 ``_assert_not_empty``
    #     已经为 domain 定下的那个数（那里实测 6 取 5，给「两个模块合并」这类合法重构留一格），
    #     **不另发明一个**；pipeline（实测 8）与 db（实测 11）用同一个数，
    #     因为它们的失效形状相同（「整层被搬空」）。
    #   * api 取 **3** = 本 Task 落地时 ``app/api/`` 的实测文件数
    #     （``__init__.py`` / ``deps.py`` / ``errors.py``）。⚠️ 它是**下界、不是预测**：
    #     计划 File Structure 要在 ``app/api/`` 下建 **18** 个 ``.py``（根 4 =
    #     ``__init__`` / ``deps`` / ``crud`` / ``errors``，``schemas/`` 7，``routers/`` 7），
    #     写成 18 会让本 Task 当场红，而账本 S6 要的是「一次抬到位、后面 8 个 Task 不再动」
    #     ——**下界只能在它已经成立的前提下抬**，故只能抬到今天的实测值。
    #
    # 于是这个聚合下界的含义从「四个目录被**一起**搬空才响」收紧成
    # 「四个目录的地板之和被击穿才响」：8 → 18 抬了 10 格，而 18 ≤ 38 仍然成立。
    #
    # **代价（硬规矩 #39）**：它仍挡不住「某一个目录被搬到只剩它自己的地板」。
    # 最坏的一格是 api：计划建满时聚合值是 pipeline 10 + db 11 + domain 17 + api 18 = **56**
    # （Task 7 给 domain 加 ``alerts.py``、Task 7/8 给 pipeline 加 ``alert_stage.py`` 与
    # ``report_stage.py``，逐条见计划 File Structure），那时把 api 搬回只剩 3 个是
    # 56 − 15 = 41 ≥ 18，**仍然绿**。那一档的兜底与本文件原来的口径相同：``domain`` 由
    # ``tests/architecture/test_domain_purity.py`` 自己那条 ``>= 5`` 空转守卫看着；
    # ``pipeline`` / ``db`` / ``api`` 被搬空时 ``tests/pipeline/`` / ``tests/db/`` /
    # ``tests/api/`` 会在**收集期**就 ImportError（它们直接 ``from app.pipeline import …`` /
    # ``from app.db import …`` / ``from app.api.deps import …``）。
    # 目录被**整个删掉**则由 :func:`_py_files` 里的 ``root.is_dir()`` 当场拦下。
    assert len(scanned) >= 18, f"只扫到 {len(scanned)} 个 .py，目录可能被搬空: {SCANNED_DIRS}"

    assert offenders == [], (
        f"生产层依赖了仿真数据生成器 app.seed（spec §3.3 依赖方向单向不可逆）：\n"
        + "\n".join(offenders)
    )


def test_api_allow_list_matches_on_dot_boundaries():
    """:func:`_is_api_allowed` 的判定矩阵（红绿两档同时在场，硬规矩 #50）。

    **这一条是 :func:`test_api_layer_dependency_direction_is_one_way` 的红档半边**：
    真仓今天一条 offender 都没有（``app/api/`` 里只有 ``deps.py`` 的一句
    ``from app.db.models.organisation import Student``），故那条守卫落地当天就绿——
    而一条恒绿的守卫与一条空转的守卫在颜色上无法区分。判颜色这件事只有本矩阵在做。
    与 :func:`test_absolute_folding_matches_resolve_name` 的分工也是这个：
    那一条守的是「相对导入折算得对不对」，本条守的是「折算出来的串**判成什么颜色**」。

    期望颜色一律**字面写死**（硬规矩 #35：不从 ``_is_api_allowed`` 反推）。

    ⚠️ ``app.refdatax`` 那一格是本矩阵存在的理由之一：``app.refdata_prescription`` 与
    ``app.refdata`` 之间是**下划线**而不是点，故「裸 ``startswith("app.refdata")``」与
    「按 ``.`` 边界匹配」对 ``app.refdatax`` 给出**不同**的答案（前者 True、后者 False）。
    :data:`API_ALLOWED_PREFIXES` 因此把 ``refdata*`` 展开成三个具体串，
    而不是写一个裸前缀——展开之后 ``app.refdatax`` 才是 RED。
    """
    cases = [
        # --- GREEN：计划 Interfaces 一节逐字点名的六个方向 -------------------
        ("app.db.session", "GREEN"),
        ("app.db.models.organisation", "GREEN"),
        ("app.domain.prescription.assembler", "GREEN"),
        ("app.pipeline.daily", "GREEN"),
        ("app.config", "GREEN"),
        ("app.notify", "GREEN"),
        ("app.refdata", "GREEN"),
        ("app.refdata_prescription", "GREEN"),
        # Task 6 才建、今天还不存在：allow-list 里列一个尚不存在的模块是**许可**、
        # 不是断言，故它今天就是 GREEN（这一格兑现「后面 8 个 Task 不再动本文件」）。
        ("app.refdata_alerts", "GREEN"),
        # --- GREEN：本 Task 在计划之外加的两项（理由见 API_ALLOWED_PREFIXES）---
        ("app.api", "GREEN"),
        ("app.api.deps", "GREEN"),
        ("app.api.routers.catalog", "GREEN"),
        ("app.adapters.factory", "GREEN"),
        # --- RED：反向与导入环 ---------------------------------------------
        # app/main.py 在 api **之上**（它装配 api），api 反过来 import 它就是环。
        ("app.main", "RED"),
        # 仿真数据生成器：另一条守卫也抓它，本清单是第二道（两道判据不同，见其 docstring）。
        ("app.seed.generate", "RED"),
        ("app.seed", "RED"),
        # --- RED：`.` 边界（裸 startswith 会放过这四格）---------------------
        ("app.dbx", "RED"),
        ("app.api_", "RED"),
        ("app.refdatax", "RED"),
        ("app.configx", "RED"),
        # --- RED：不在清单里的 app.* 模块 ----------------------------------
        # Task 2 的演示数据生成器。刻意不放行：端点要造演示数据的话，
        # 那是一次需要显式改清单的决定，不是顺手一句 import。
        ("app.demo_data", "RED"),
        # --- RED（**已知的假阳性**，硬规矩 #39）---------------------------
        # `from app import config` 的 AST 是 ImportFrom(module="app", level=0)，
        # _imported_modules 对 level==0 只 yield node.module、**不带 names**，
        # 故它折出来的是裸串 "app" 而不是 "app.config" → 判 RED。
        # 这是一次**误报**而不是漏报（红的方向是安全的），且本仓的既定风格是
        # 「跨包一律写完整点号绝对串」（Plan02 账本 Ruling 104：真仓的相对导入全是
        # level==1 的包内导入，跨包的那几处 Task 2/3/4 三轮都刻意选了
        # `from app.domain.indicators import …` 这种完整串），故这一格今天不可达。
        # ⚠️ 要消除它得给 _imported_modules 在 level==0 时也按 names 展开——
        # 那个函数是**两份守卫共用**的、且被 Plan02 Ruling 35/36/41 的三段规格说明钉着，
        # 为一个今天不存在的写法去动它不划算。谁真撞上这条红，正确处置是把
        # `from app import config` 改写成 `from app.config import …`。
        ("app", "RED"),
    ]
    offenders: list[str] = []
    for module, color in cases:
        got = "GREEN" if _is_api_allowed(module) else "RED"
        if got != color:
            offenders.append(f"_is_api_allowed({module!r}) 判成 {got}、期望 {color}")
    # 空转守卫：矩阵本身被写空时上面那个循环一条都不跑、offenders 恒为 []。
    # 22 = 本矩阵的格数下界（写它的时候是 22 格：13 GREEN + 9 RED）。
    assert len(cases) >= 22, f"矩阵只剩 {len(cases)} 格，可能被写空了"
    assert offenders == [], (
        "api 层的 allow-list 判定不对（`.` 边界被写成裸 startswith 时，"
        "app.dbx / app.refdatax 那几格会变绿）：\n" + "\n".join(offenders)
    )


def test_api_layer_dependency_direction_is_one_way():
    """``api`` 只能**向下**依赖；``pipeline`` / ``db`` / ``domain`` 一律不得反向依赖 ``api``。

    spec §3.3 的依赖方向图是 ``api → services → domain`` / ``pipeline → adapters``，
    即 ``api`` 是最上层。计划 Task 1 的 Interfaces 一节把它落成一句可执行的话：
    「``api`` 可以 import ``db`` / ``domain`` / ``pipeline`` / ``refdata*`` / ``config`` /
    ``notify``；**反向一律禁止**（``domain`` 与 ``db`` 都不许 import ``api``）」。

    **扫的机制与本文件既有那一条完全相同**（照既有机制加、不另发明一套）：
    同一份 :func:`_py_files`（含它的 ``root.is_dir()`` 守卫）、同一份
    :func:`_package_of`、同一份 :func:`_imported_modules`（故**函数内导入也被覆盖**，
    ``ast.walk`` 的性质）。差别只在判定函数：那一条用 :func:`_is_forbidden`
    的黑名单，本条用 :func:`_is_api_allowed` 的白名单 + :data:`API_PREFIX` 的反向匹配。

    **反向那一圈为什么是 ``SCANNED_DIRS`` 减掉 ``api``**、而不是硬写三个目录名：
    这样「将来再往 ``SCANNED_DIRS`` 加一层」会自动把它纳入「不得依赖 api」的约束，
    不必有人记得同步第二处清单（单一所有者）。⚠️ 而 ``app/adapters/`` 与 ``app/seed/``
    **不在这一圈里**，因为它们不在 ``SCANNED_DIRS`` 里（理由见模块 docstring 与
    :data:`SCANNED_DIRS` 上方那两条 ⚠️）；``app/main.py`` 同理不在——它在 ``api`` 之上，
    本来就必须 import ``app.api``。

    **本守卫不覆盖什么**（硬规矩 #39）：

    * 三方库与标准库：``api`` 里 import ``fastapi`` / ``pydantic`` / ``sqlalchemy``
      一律放过（``not module.startswith("app.")`` 那一支）。给 ``api`` 也上一份
      allow-list 是另一件事，本仓只对 ``domain`` 做那件事（它有「无 I/O」这个更强的理由）。
    * ``importlib`` 动态导入、字符串拼出来的模块名（与既有条目同一个缺口）。
    * ``from app import config`` 这种**不带完整点号**的写法会折成裸串 ``"app"`` 而判红
      ——是误报不是漏报，详见
      :func:`test_api_allow_list_matches_on_dot_boundaries` 矩阵最后一格的注释。
    """
    offenders: list[str] = []

    # --- 正向：api 只能向下 -------------------------------------------------
    api_py = _py_files("api")
    api_folded: set[str] = set()
    for py in api_py:
        tree = ast.parse(py.read_text(encoding="utf-8"))
        where = py.relative_to(BACKEND).as_posix()
        for lineno, module in _imported_modules(tree, _package_of(py)):
            if module is None:
                offenders.append(f"{where}:{lineno}: 相对导入上溯到顶层包 app 之外")
                continue
            if module != "app" and not module.startswith("app."):
                continue  # 三方库与标准库不归本守卫管
            api_folded.add(module)
            if not _is_api_allowed(module):
                offenders.append(
                    f"{where}:{lineno}: api 层依赖了 {module}"
                    f"（不在 API_ALLOWED_PREFIXES = {API_ALLOWED_PREFIXES} 内）"
                )

    # --- 反向：其余被扫的层不得依赖 api --------------------------------------
    reverse_py: list[pathlib.Path] = []
    for relative_dir in SCANNED_DIRS:
        if relative_dir == "api":
            continue
        for py in _py_files(relative_dir):
            reverse_py.append(py)
            tree = ast.parse(py.read_text(encoding="utf-8"))
            where = py.relative_to(BACKEND).as_posix()
            for lineno, module in _imported_modules(tree, _package_of(py)):
                if module is None:
                    continue  # 越界档由既有那一条判 offender，本条不重复报
                if module == API_PREFIX or module.startswith(API_PREFIX + "."):
                    offenders.append(f"{where}:{lineno}: {relative_dir} 层反向依赖了 {module}")

    # 空转守卫。三个下界与一个折算串都是**字面量**（硬规矩 #35）：
    #   3  = app/api/ 的 .py 个数下界（Plan 03 Task 1 落地时实测 3：__init__ / deps / errors；
    #        计划建满后是 18，故 3 是下界不是预测）；
    #   15 = 反向那一圈（pipeline + db + domain）的 .py 个数下界，取法与
    #        test_production_layers_never_import_app_seed 里那个 18 同源：
    #        三个目录各留 5 格地板（5 沿用 test_domain_purity._assert_not_empty 的数），
    #        5 × 3 = 15；实测 35（pipeline 8 + db 11 + domain 16）。
    #   "app.db.models.organisation" = app/api/ 下今天**唯一**一条 app.* 导入
    #        （deps.py 的 from app.db.models.organisation import Student）。
    #        它是本守卫的**绿档**：少了它，「api_folded 是空集」与「api 一条 app.* 都没
    #        import」在颜色上无法区分，而前者意味着上面那个循环空转了。
    assert len(api_py) >= 3, f"只扫到 {len(api_py)} 个 .py，app/api 可能被搬空: {api_py}"
    assert len(reverse_py) >= 15, (
        f"只扫到 {len(reverse_py)} 个 .py，反向那一圈可能被搬空: {SCANNED_DIRS}"
    )
    assert "app.db.models.organisation" in api_folded, (
        "app/api/ 里没有折出 app.db.models.organisation，正向那一圈可能已经空转："
        f"{sorted(api_folded)}"
    )

    assert offenders == [], (
        "api 层的依赖方向被破坏（spec §3.3：api 是最上层，只能向下）：\n"
        + "\n".join(offenders)
    )
