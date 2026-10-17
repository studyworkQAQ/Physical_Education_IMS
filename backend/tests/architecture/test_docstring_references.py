"""**全仓 docstring 里的 ``:func:`` / ``:class:`` / ``:mod:`` 引用都指得到真名**
（Plan 06 Task 12 / C4）。

--------------------------------------------------------------------------
⚠️ 它收的是哪一条（实测清单）
--------------------------------------------------------------------------

派单点名了两处（``tests/api/test_crud.py`` 与 ``app/api/routers/catalog.py`` 都把
``test_the_student_keyed_resources_admit_four_read_tiers`` 写成了少一个 ``four`` 的形状），
并要求「先 ``Grep`` 全仓所有 ``:func:``/``:class:``/``:mod:`` 引用，
**把坏的一个不留地列出来**再修」。实测（本机亲跑，扫描面 = ``backend/`` 下全部
``.py``，引用总数 **5 055** 条）：

* **本波之前就已经坏的 9 处**（逐个都改成了真名）：
  派单点名的那 2 处（少一个 ``four``）、``tests/api/test_audit_api.py``（少一个 ``an_``）、
  ``tests/conftest.py``（指着一个模块里根本不存在的常量名）、
  ``app/api/routers/dashboard.py`` / ``app/db/models/organisation.py`` /
  ``scripts/dump_openapi.py`` / ``tests/db/test_models.py`` / ``tests/test_serve.py``
  各 1 处（都是「守卫是某某某」那一族，而那一条守卫在后面的波里改了名）；
* **本波自己写坏的 3 处**（同样改掉）：``tests/api/test_column_widths.py`` 两处、
  ``app/auth/passwords.py`` 一处 —— ⚠️ 如实记：它们是本波新写的散文，
  而本条守卫**当场**把它们抓出来了（那是它第一次证明自己有牙）；
* **刻意提到的历史名 8 处 / 6 个名字**：它们**不是**坏引用，逐格理由见
  :data:`_HISTORICAL`。

⚠️ 派单只点了 2 处，实测是 **12** 处（含本波自己的 3 处）—— 于是「散文里的名字」
这一族的失效形态是**静默**的：一个读的人按那个名字 ``git grep``，得到 0 个命中，
而他会以为是自己的搜索写错了。⚠️ 而派单点名的第 2 处（``catalog.py``）用的是
**裸双反引号**、不是 ``:func:`` 角色，故一条只扫 Sphinx 角色的守卫**抓不到它**
—— 本条两种形状都扫（后者按 ``test_`` 前缀收窄，逐字理由见
:data:`BARE_TEST_NAME`）。

--------------------------------------------------------------------------
⚠️⚠️ 判据的形状：**低假阳性**优先（这是本条能不能留下的关键，派单点名要核）
--------------------------------------------------------------------------

第一版解析器（「把 ``A.B.C`` 折成 ``import_module("A.B")`` + ``getattr("C")``、
裸名折成「本模块有没有这个名字」）实测在 5 055 条引用上报出 **401** 处「解析不到」，
而其中**绝大多数是假阳性**：``:attr:`AuditLog.SUBJECT_KINDS```（类属性，
``import_module("AuditLog")`` 当然失败）、``:mod:`pathlib```（标准库，
而引用它的那个模块没有 ``import pathlib``）、``:class:`ValueError```（内置）、
「mod 角色 + 一个前导点」的**相对**模块语法、以及一个带 ``~`` 前缀的
（Sphinx 的 ``~`` 缩短显示语法）、``:func:`starlette.routing.Router.not_found```
（**真的存在**，本机实测 ``hasattr(Router, "not_found") is True``，
而它要**逐段**试 import 才折得开）。

⚠️ 401 条里真坏的只有 6 条 ⇒ 那一版守卫的信噪比是 **1.5%**，
它会被下一个人立刻调松或删掉（那比没有守卫更坏：一条恒红的守卫会训练人忽略红）。
故本条的判据换成**五级放行**（下面 :func:`_resolves` 逐档写了理由），
其中第 ② 档是「**末段名字在全仓任何一个 ``.py`` 里被定义过**」——
它用一个 AST 索引（函数/类/赋值/属性/形参/import 别名，实测约 1.7 万个名字）
换来了「散文里提到另一个文件的测试函数名」这一族（本仓**大量**这么写，
例如 ``app/api/schemas/organisation.py`` 指 ``tests/api/test_crud.py`` 的
``test_every_read_schema_covers_exactly_the_model_columns``）不再假红。

⚠️ **代价（硬规矩 #39，如实记）**：第 ② 档是**宽松**的，故本条的**召回率不是 100%**
—— 一个打错的名字若恰好与全仓某一处属性名/形参名同形，它会溜过去。
本条守的是「**凭空不存在**的名字」（那 6 处全是这一类，包括少了 ``four`` 的那两处：
``…admit_the_read_tiers`` 在全仓任何位置都不存在）。
⚠️ 而「名字存在、但指的是另一个东西」这一族本条**不守**
（那要理解语义，而不只是解析符号）。

--------------------------------------------------------------------------
⚠️ 反空转（硬规矩 #50）
--------------------------------------------------------------------------

三拍，缺一拍本条就可能恒绿：① 引用总数 ≥ 4 000（扫描面没写错）；
② 那 6 处**已经修好**的名字确实解析得到（否则「0 处坏」可能只是解析器全放行）；
③ 解析器对**已知反例**确实会报（:func:`test_the_resolver_reports_a_name_that_exists_nowhere`
拿那 6 处改前的原文喂它，断言它一律判「解析不到」）。
"""
from __future__ import annotations

import ast
import builtins
import importlib
import pathlib
import re

#: 仓库根（本文件在 ``backend/tests/architecture/`` 下）。
BACKEND = pathlib.Path(__file__).resolve().parents[2]

#: Sphinx 的角色。⚠️ 本仓实际用到的实测是这 9 个（``func`` 2 861 条最多）。
ROLES = ("func", "class", "mod", "data", "attr", "meth", "obj", "exc", "const")

#: 一条 ``:role:`target``` 引用。⚠️ ``[^`<]+`` 而不是 ``[^`]+``：Sphinx 的
#: ``:func:`显示名 <真名>`` 形状里带一个 ``<``，本仓实测 **0** 处用到它，
#: 而排除 ``<`` 能让「万一有人用了」时本条**跳过**而不是判红在一个假名字上。
REF = re.compile(r":(?:%s):`([^`<]+)`" % "|".join(ROLES))

#: ⚠️ **裸双反引号里的「看起来像一个 Python 名字」的串也要扫**（派单点名的第 2 处
#: 就是这个形状：``catalog.py`` 用 `` ``test_the_…`` `` 而不是 ``:func:`` 角色）。
#: ⚠️ 而它必须**窄**：只认 ``test_`` 开头的（本仓全部测试函数名都以它开头），
#: 否则每一处 `` ``student_no`` `` / `` ``POST`` `` 一类散文都会被拖进来，
#: 假阳性会把本条淹掉（逐字理由见模块 docstring 的「判据的形状」那一节）。
BARE_TEST_NAME = re.compile(r"``(test_[A-Za-z0-9_]+)``")

#: 扫描面：``backend/`` 下全部 ``.py``（含 ``app/`` / ``tests/`` / ``scripts/`` /
#: ``migrations/``）。⚠️ 一个都不排：散文里的引用在这四个子树里都有。
EXCLUDED_PARTS = frozenset({"__pycache__", ".git", "node_modules"})


def _py_files() -> list[pathlib.Path]:
    return [
        path
        for path in sorted(BACKEND.rglob("*.py"))
        if not (EXCLUDED_PARTS & set(path.parts))
    ]


def _name_index() -> set[str]:
    """全仓每一个 ``.py`` 里**被定义过**的名字（第 ② 档判据的数据）。

    ⚠️ 它收六种形状：函数/类定义名、赋值目标（含元组解包与属性赋值的属性名）、
    带标注的赋值、任何一处属性访问的**属性名**、形参名、以及 import 的绑定名。
    ⚠️ 「属性名」与「形参名」两族是**刻意**收的：本仓的散文大量写
    「attr 角色 + 类名点常量名」与「func 角色 + 一个私有助手名」这两种形状，
    而前者在 AST 上既可能是类体内的赋值、也可能只是别处的一次属性访问。
    ⚠️ 代价（如实记，模块 docstring 末节）：判据因此是宽松的，
    它守「凭空不存在的名字」，不守「名字存在但指错了东西」。
    """
    index: set[str] = set()
    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - 全仓今天 0 处（另有一条守卫钉它）
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                index.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for piece in ast.walk(target):
                        if isinstance(piece, ast.Name):
                            index.add(piece.id)
                        elif isinstance(piece, ast.Attribute):
                            index.add(piece.attr)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                index.add(node.target.id)
            elif isinstance(node, ast.Attribute):
                index.add(node.attr)
            elif isinstance(node, ast.arg):
                index.add(node.arg)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    index.add(alias.asname or alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    index.add(alias.asname or alias.name)
    return index


#: 模块名的相对解析要用的「文件 → 模块名」。⚠️ ``__init__.py`` 折成**它那个包**
#: （``app/db/models/__init__.py`` → ``app.db.models``），于是那个文件里的
#: 「前导点 + ops」补全成 ``app.db.models.ops``。⚠️ 本仓实测 21 处相对引用里
#: **绝大多数**住在两个 ``__init__.py`` 里，故这一格是承重的。
def _module_of(path: pathlib.Path) -> str | None:
    relative = path.relative_to(BACKEND).as_posix()
    if not relative.startswith(("app/", "tests/", "scripts/")):
        return None
    module = relative[: -len(".py")].replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module


#: ``backend/`` 下每一个 ``.py`` 的**文件名主干**。⚠️ 它是第 ⑥ 档放行口的数据：
#: 本仓的散文里大量出现 `` ``test_generate`` `` / `` ``test_prescription_exercises`` ``
#: 这种**指一个测试文件**（不是指一个函数）的写法，而不认它的话那一批会假红。
_FILE_STEMS = {path.stem for path in _py_files()}


def _importable(dotted: str) -> bool:
    """``dotted`` 那一条**点号路径**能不能被逐段折开（import 一段、getattr 其余）。

    ⚠️ **逐段**是承重的：``starlette.routing.Router.not_found`` 要先
    ``import_module("starlette.routing")`` 再 ``getattr`` 两下；
    而 ``import_module("starlette.routing.Router")`` 恒失败（那是个类）。
    ⚠️ 从**最长**的前缀开始试（于是 ``app.api.crud.build_crud_router`` 先试
    import ``app.api.crud``），失败就退一段 —— 退到只剩一段时
    就是「它本身是一个模块」那一档（``:mod:`app.config```）。
    """
    parts = dotted.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        head = ".".join(parts[:cut])
        try:
            obj = importlib.import_module(head)
        except Exception:  # noqa: BLE001  ⚠️ 刻意宽：import 不到就是「这一刀不对」
            continue
        for piece in parts[cut:]:
            obj = getattr(obj, piece, None)
            if obj is None:
                break
        if obj is not None:
            return True
    try:
        importlib.import_module(dotted)
        return True
    except Exception:  # noqa: BLE001
        return False


def _resolves(target: str, module: str | None, index: set[str]) -> bool:
    """一条引用的目标**指得到真名**吗。五级放行，逐档的理由：

    ① ``…`` 省略号 —— 本仓有一处**刻意**的缩写
       （``tests/api/test_auth_api.py`` 的
       ``test_bind_student_gives_the_same_code_and_message_…``，
       真名长到一行装不下）。判据是「省略号**前面**那一段是全仓某个名字的前缀」，
       于是「缩写」放行、「打错」照样红。
    ② Sphinx 的 ``~`` 前缀（缩短显示）→ 去掉它再判。
    ③ Sphinx 的**相对**模块名（前导点那一个形状）→ 按引用它的那个文件的包补全再判。
       ⚠️ 本仓实测 **21** 处是这个形状（``app/db/models/__init__.py`` /
       ``app/api/schemas/__init__.py`` 一族），不补全就是 21 条假红。
    ④ 点号路径 → :func:`_importable`（逐段试）。
    ⑤ 末段名字 → 全仓索引 / 内置名。⚠️ 这一档是「散文里提到另一个文件的
       测试函数名」那一大族的放行口（模块 docstring 的「判据的形状」那一节）。
    """
    name = target.strip()
    if name.endswith("()"):
        name = name[:-2]
    if "…" in name:
        head = name.split("…", 1)[0].rpartition(".")[2]
        return len(head) >= 8 and any(
            real.startswith(head) for real in index
        )
    if name.startswith("~"):
        name = name[1:]
    if name.startswith("."):
        if module is None:
            return False
        package = module.rpartition(".")[0]
        name = f"{package}{name}" if package else name.lstrip(".")
    # ⚠️ ④ **无条件**试一次点号路径的逐段 import：``:mod:`zoneinfo``` 一类
    #    **不带点**的标准库模块也要经这一档（只判「有点才 import」的话，
    #    ``zoneinfo`` 会落到第 ⑤ 档、而全仓没有一个文件 ``import zoneinfo``
    #    ⇒ 假红。本机实测就是那一格）。
    if _importable(name):
        return True
    last = name.rpartition(".")[2]
    # ⑤ 末段名字在全仓索引里 / 是一个内置名
    if name in index or last in index:
        return True
    if hasattr(builtins, last):
        return True
    # ⑥ 它是一个**测试文件名**（散文里「``test_generate`` 那一份」这种指文件的写法）
    return last in _FILE_STEMS


#: --------------------------------------------------------------------------
#: **历史名**：散文里刻意提到的一个「今天已经不存在」的名字
#: --------------------------------------------------------------------------
#:
#: ⚠️ 它们**不是坏引用**，而是本仓一条既有纪律的产物（硬规矩 #66：绑时点的历史陈述
#: 在它绑定的时点上是真的，**不要改成今天的样子**）。实测全仓 **8** 处、**6** 个名字，
#: 逐格的理由：
#:
#: * 「**改前它叫 X**」/「**本条替代了 X**」/「**这里原有一条 X**」/「**原文叫 X**」
#:   —— 那一句说的是**过去**，而把 X 换成今天的名字会让那一句话变成假话
#:   （「本条替代了〈本条自己〉」）。共 5 个名字、7 处；
#: * 「**这个名字是留给下一个想加形参的人看的**」
#:   （``test_override_does_not_mutate_the_template``）—— 一个**预留名**，
#:   它今天不存在是**要的**。
#:
#: ⚠️ 于是本条守卫的判据是「**解析得到 ∪ 历史名清单 == 全部引用**」，
#: 而不是「解析得到 == 全部引用」。⚠️ 而清单本身也被守住（反腐烂）：
#: :func:`test_the_historical_name_list_does_not_rot` 断言清单里每一个名字
#: **确实还被散文引用着**（于是「那条历史陈述被删掉了、而清单没跟着删」会红），
#: 且每一个名字**确实不在**全仓索引里（于是「有人又把那个测试建回来了」也会红 ——
#: 那时它就该从清单里出去、按普通引用被解析）。
_HISTORICAL: dict[str, str] = {
    "test_a_prescription_whose_stratification_row_is_gone_fails_loudly":
        "Task 7 首轮交付的那一条，钉的失效形态在加了 label_at_generation 之后"
        "结构上不可达、已删；三处散文（prescription_stage.py 1、"
        "test_prescription_stage.py 2）逐字写着「已一并删掉 / 已由本条取代 / 原有一条」",
    "test_exactly_two_resources_declare_read_requires_staff":
        "Plan 05A Task 5 的那一条；那个布尔开关在安全收紧波被 read_scope 替代，"
        "散文逐字写着「本条**替代**了」",
    "test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin":
        "改前那一条的名字；散文逐字写着「改前它叫 …」，而它钉的那一格"
        "（Task 8 顶回 1）后来被修成了「对相关的那一位教师可见」",
    "test_the_normalized_route_is_anonymous_and_a_student_can_read_it":
        "Plan 06 Task 8 之前那一条的名字；散文逐字写着「本条**替掉**了改前那一条」"
        "（那个端点自 Task 8 起不再匿名）",
    "test_every_impact_level_has_at_least_one_low_substitute":
        "P2-C2 改名之前的原文名；散文逐字写着「原文叫 …，名字说『每个 impact level』"
        "而描述只要求 high」——那一句的全部信息量就在那个旧名字上",
    "test_override_does_not_mutate_the_template":
        "**预留名**（不是历史名）：散文逐字写着「这个名字是留给下一个想加形参的人看的」",
    "test_all_twenty_eight_tables_created":
        "**Plan 08 Task 1 改名之前**的原文名（表数 28 → 29，函数名里的英文数词跟着改，"
        "那是 ``tests/db/test_models.py`` 那份同步清单的第 ① 格）。⚠️ 它**仍然被散文引用着**："
        "同一份清单里那一段逐字写着「改前是 ``test_all_twenty_eight_tables_created`` 的 "
        "11 处 / 7 个文件；改后逐字是 …``twenty_nine``… 的 11 处 / 7 个文件」——"
        "那一句的全部信息量就在**旧名字**上（它证明的是「改名是 1:1 的、没有漏一处」），"
        "故按本清单既有的口径留在 ``_HISTORICAL`` 里，⚠️ 而**不是**把散文改成新名字"
        "（那样两侧就同源了，「1:1」那句话会当场变成一句无从核对的话）。",
}


def test_every_docstring_reference_points_at_a_name_that_exists():
    """**主判据**：全仓每一条引用都指得到一个真名，或在 :data:`_HISTORICAL` 清单上。

    ⚠️ 红的形状是**逐条点名**（文件:行号 + 那个名字），而不是只报一个数：
    一条引用坏掉时，读的人要能直接跳到那一行。
    ⚠️ 而「一个刻意提到的历史名」不算坏（逐字理由见 :data:`_HISTORICAL`）。
    """
    index = _name_index()
    bad: list[str] = []
    total = 0
    for path in _py_files():
        relative = path.relative_to(BACKEND).as_posix()
        module = _module_of(path)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            targets = list(REF.findall(line)) + list(BARE_TEST_NAME.findall(line))
            for target in targets:
                total += 1
                name = target.strip()
                if name.rpartition(".")[2] in _HISTORICAL:
                    continue
                if not _resolves(target, module, index):
                    bad.append(f"{relative}:{lineno} → {name!r}")
    assert total >= 4000, f"只扫到 {total} 条引用（本机实测 5 055）：扫描面写错了？"
    assert not bad, (
        f"{len(bad)} 处 docstring 引用指不到真名（一个读的人按它 git grep 会得到 0 个命中，"
        f"而他会以为是自己的搜索写错了）。⚠️ 若它是一条**刻意**提到的历史名/预留名，"
        f"把它连同理由加进 _HISTORICAL；否则改成真名：\n  " + "\n  ".join(bad)
    )


def test_the_historical_name_list_does_not_rot():
    """:data:`_HISTORICAL` 那份清单**自己不腐烂**（反空转的两拍）。

    ① 清单里每一个名字**确实还被散文引用着**：那一句历史陈述被删掉之后，
       清单里留着它就是死配置（而下一个人会以为「这个名字是可以随便提的」）；
    ② 每一个名字**确实不在**全仓索引里：若有人把那个测试又建回来了，
       它就变成一个普通引用、该从清单里出去 —— 留在清单上会让本条守卫
       对那一格**永久失明**（清单是跳过解析的，跳过就是不检查）。

    ⚠️ 少了②的话，「往清单里塞一个真名字来让本条守卫绿」是可行的
    —— 那是本条唯一的作弊面，故两拍都在。
    """
    index = _name_index()
    referenced: dict[str, list[str]] = {name: [] for name in _HISTORICAL}
    for path in _py_files():
        relative = path.relative_to(BACKEND).as_posix()
        # ⚠️ **本文件自己不算**：``_HISTORICAL`` 的键与注释里都写着那些名字，
        #    把它算进来的话「散文里的历史陈述被删干净了」这一档**恒绿**
        #    （清单自己引用自己），①那一拍就空转了。
        if relative == pathlib.Path(__file__).relative_to(BACKEND).as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        for name in _HISTORICAL:
            if name in text:
                referenced[name].append(relative)
    unused = sorted(name for name, sites in referenced.items() if not sites)
    assert not unused, f"_HISTORICAL 里这几个名字已经没人提了，删掉它们：{unused}"
    resurrected = sorted(name for name in _HISTORICAL if name in index)
    assert not resurrected, (
        f"_HISTORICAL 里这几个名字**又存在了**（有人把那个测试建回来了）："
        f"{resurrected}。把它们从清单里删掉，让它们按普通引用被解析"
    )
    # ⚠️ 反空转：清单不是一份空表（空表会让主判据退化成「全部都要解析得到」，
    #    而那在本仓是**假**的 —— 9 处历史陈述会当场红）。
    # ⚠️ **Plan 08 Task 1 把它从 6 抬到 7**（+ ``test_all_twenty_eight_tables_created``：
    #    表数 28 → 29 时函数名里的英文数词跟着改，而那份同步清单里「改名是 1:1 的」
    #    那一句的全部信息量就在**旧名字**上，故按本清单既有的口径留在这里）。
    assert len(_HISTORICAL) == 7, len(_HISTORICAL)


def test_the_resolver_reports_a_name_that_exists_nowhere():
    """**反空转**：解析器对**已知反例**确实会报（否则「0 处坏」可能只是它全放行）。

    ⚠️ 反例取的就是本波实测到的那 6 处**改前**的原文（模块 docstring 那张表），
    故本条同时钉住「那 6 处是真的坏、不是解析器的口味」。
    ⚠️ 绿档也在场：每一处的**真名**必须解析得到（否则「解析器判红」与
    「解析器什么都判红」在颜色上不可分辨）。
    """
    index = _name_index()
    known_bad = [
        "test_the_student_keyed_resources_admit_the_read_tiers",   # 少了 four（两处）
        "test_anonymous_read_writes_no_audit_row",                 # 少了 an_
        "app.auth.passwords.PBKDF2_ITERATIONS",                    # 那个模块里没有它
        "_BODY_REJECTED",                                          # 本波新文件自带的
        "_every_declared_width",                                   # 同上（助手改了名）
    ]
    for target in known_bad:
        assert not _resolves(target, "app.api.crud", index), (
            f"{target!r} 本该解析不到（它是本波实测到的坏引用之一）"
        )
    for target in (
        "test_the_student_keyed_resources_admit_four_read_tiers",
        "test_an_anonymous_read_writes_no_audit_row",
        "app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR",
        "app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS",
        # ⚠️ 三格「形状麻烦而名字是真的」：类属性 / 标准库 / 三段点号路径
        "AuditLog.SUBJECT_KINDS",
        "pathlib",
        "starlette.routing.Router.not_found",
        # ⚠️ Sphinx 的两个语法：``~`` 缩短显示 与 相对模块名
        "~app.domain.prescription.assembler",
        "test_bind_student_gives_the_same_code_and_message_…",
    ):
        assert _resolves(target, "app.db.models.audit", index), (
            f"{target!r} 是真的名字却被判成解析不到 = 解析器太严（会淹在假阳性里）"
        )
    # ⚠️ 相对模块名那一档：「前导点 + ops」在 ``app/db/models/audit.py`` 里指的是
    #    ``app.db.models.ops``（实测本仓 21 处是这个形状）。
    assert _resolves(".ops", "app.db.models.audit", index)
    assert not _resolves(".not_a_module_at_all", "app.db.models.audit", index)
