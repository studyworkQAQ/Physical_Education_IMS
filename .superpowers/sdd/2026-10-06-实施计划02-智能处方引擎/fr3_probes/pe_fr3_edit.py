# -*- coding: utf-8 -*-
"""pe_fr3_edit.py — fix round 3 的唯一写盘入口（Ruling 42 的一处 docstring + Ruling 46 的两条回归测试）。

用法: python pe_fr3_edit.py <仓库根>

做法：读字节 → decode utf-8 → 按 CRLF 切行 → 逐处 assert 命中数恰为 1 → 替换/插入 →
按 CRLF join → write_bytes。写完全程只碰两个守卫文件，且不碰生产代码。
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
PURITY = REPO / "backend/tests/architecture/test_domain_purity.py"
LAYER = REPO / "backend/tests/architecture/test_layering.py"

# ---------------------------------------------------------------- Ruling 42
OLD_167 = "    会折成 ``app.domain``、**命中白名单前缀 ``app.domain.`` 变成真绿**，而 ``resolve_name``"
NEW_167_TEXT = """    会折成 ``app.domain``，而 ``_is_allowed`` 的第一支正是 ``module == ALLOWED_PACKAGE``——
    **命中的是「相等」这一支，不是 ``startswith(ALLOWED_PACKAGE + ".")`` 那一支**（本机
    Python 3.11.1 实跑：``"app.domain" == ALLOWED_PACKAGE`` -> ``True``、
    ``"app.domain".startswith(ALLOWED_PACKAGE + ".")`` -> ``False``；Plan02 Ruling 42），
    于是变成真绿；而 ``resolve_name``"""

# ---------------------------------------------------------------- Ruling 46 · purity
FUNC_PURITY_TEXT = '''def test_absolute_folding_matches_resolve_name():
    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。

    **判据为什么锚在 ``resolve_name`` 上、而不是锚在一张期望值表上**：表是某个人某一次跑
    出来的结果，抄进测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；
    ``resolve_name`` 是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格
    现场调一次 ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``
    （越界档，Plan02 Ruling 35）。

    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：

    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
      ``("domain", 4, ("app", "domain"), "tables")`` 折成 ``app.domain`` 而不是 ``None``
      → 本测试红（变异实测，见任务报告 fix round 3）。
    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
      ``app.seed`` → 本测试红（同上，变异实测）。
    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
      模块，Plan02 Ruling 36）→ 末尾那一段红。

    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``level == 1`` 的包内导入
    折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed` 放行——Task 2 起
    ``app/domain/prescription/`` 子包里的 ``from ..indicators import X`` 正是这一档。
    ⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")`` 折成 ``app.db.seed``，在
    **本文件**的白名单下是 RED、在 :mod:`tests.architecture.test_layering` 的 ``app.seed``
    前缀下却是 GREEN：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份回归测试的
    期望颜色列**不相同**，这不是抄错。

    **本测试守不住什么**（硬规矩 #39）：

    * ``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内：谁把它改成返回
      「模块名」而不是「包名」（``("app", "domain", "x")``），本测试**照样全绿**，而两条
      架构守卫会一起假绿。那一档今天只有 :func:`_absolute` docstring 里 ``resolve_name``
      的两行实跑举例（Plan02 Ruling 37）在交代，仓库里同样没有断言看着。
    * 它不扫真仓文件，故「白名单取值本身对不对」仍只由
      :func:`test_domain_imports_stay_within_the_allow_list` 看着，两条判据互不覆盖。
    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
    """
    # 就地 import：模块级 import 会改动本文件的 <module-level>，而本轮的改动面被钉死在
    # 「新增这一条测试函数 + _absolute docstring 的一处机制更正」之内（Plan02 Ruling 46）。
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
        "（Plan02 Ruling 35/36/41）：\\n" + "\\n".join(offenders)
    )

    # Ruling 36 的另一半：一个 ImportFrom 节点带两个名字，必须展开成两条、各自折算。
    tree = ast.parse("from .. import seed, pipeline\\n")
    package = ("app", "pipeline")
    got = [_absolute(module, level, package, name)
           for _lineno, module, level, name in _imported_modules(tree)]
    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
            for alias in ("seed", "pipeline")]
    assert got == want, f"一名一条的展开失效: {got} != {want}"'''

# ---------------------------------------------------------------- Ruling 46 · layering
FUNC_LAYER_TEXT = '''def test_absolute_folding_matches_resolve_name():
    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。

    **这一条与 :mod:`tests.architecture.test_domain_purity` 里的同名测试是「两份重复守卫的
    两份回归测试」**（硬规矩 #51）：``_absolute`` 在两个文件里各有一份、逐字相同，故回归
    测试也必须各有一份——只留一份的话，另一份 ``_absolute`` 被改坏时**没有任何测试会红**。
    下面的变异实测证明了这一点：只变异本文件的 ``_absolute``，purity 那条**保持绿**。

    **判据锚在 ``resolve_name`` 上、不锚在期望值表上**：表是某个人某一次跑出来的结果，抄进
    测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；``resolve_name``
    是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格现场调一次
    ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``（越界档，
    Plan02 Ruling 35）。

    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：

    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
      ``("seed", 5, ("app", "db", "models"), "generate")`` 折成 ``app.db.seed`` 而不是
      ``None`` → 本测试红（变异实测，见任务报告 fix round 3）。
    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
      ``app.seed`` → 本测试红（同上，变异实测）。
    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
      模块，Plan02 Ruling 36）→ 末尾那一段红。

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
        "（Plan02 Ruling 35/36/41）：\\n" + "\\n".join(offenders)
    )

    # Ruling 36 的另一半：一个 ImportFrom 节点带两个名字，必须展开成两条、各自折算。
    tree = ast.parse("from .. import seed, pipeline\\n")
    package = ("app", "pipeline")
    got = [module for _lineno, module in _imported_modules(tree, package)]
    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
            for alias in ("seed", "pipeline")]
    assert got == want, f"一名一条的展开失效: {got} != {want}"'''

NEW_167 = NEW_167_TEXT.split("\n")
FUNC_PURITY = FUNC_PURITY_TEXT.split("\n")
FUNC_LAYER = FUNC_LAYER_TEXT.split("\n")


def load(path):
    raw = path.read_bytes()
    assert raw[:3] != b"\xef\xbb\xbf", path
    text = raw.decode("utf-8")
    assert "\r\n" in text and text.count("\n") == text.count("\r\n"), path
    return text.split("\r\n")


def save(path, lines):
    data = "\r\n".join(lines).encode("utf-8")
    path.write_bytes(data)
    back = path.read_bytes()
    assert back == data, path
    assert back.count(b"\n") == back.count(b"\r\n"), path
    return back


def sub_once(lines, old, new, tag):
    hits = [i for i, l in enumerate(lines) if l == old]
    assert len(hits) == 1, (tag, "命中 %d 次" % len(hits), hits)
    lines[hits[0]:hits[0] + 1] = new
    print("  %s: 行 %d 替换成 %d 行" % (tag, hits[0] + 1, len(new)))
    return lines


def insert_after(lines, anchor, payload, tag):
    hits = [i for i, l in enumerate(lines) if l == anchor]
    assert len(hits) == 1, (tag, "命中 %d 次" % len(hits), hits)
    lines[hits[0] + 1:hits[0] + 1] = ["", ""] + payload
    print("  %s: 在行 %d 之后插入 %d 行（含 2 行空行）" % (tag, hits[0] + 1, len(payload) + 2))
    return lines


print("=== Ruling 42 + Ruling 46 写盘 ===")
pl = load(PURITY)
n0 = len(pl)
sub_once(pl, OLD_167, NEW_167, "purity Ruling 42")
insert_after(pl, "    return module in ALLOWED_MODULES", FUNC_PURITY, "purity Ruling 46")
b = save(PURITY, pl)
print("  purity: %d 行 -> %d 行，%d 字节" % (n0, len(pl), len(b)))

ll = load(LAYER)
n0 = len(ll)
insert_after(ll,
             '    return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")',
             FUNC_LAYER, "layering Ruling 46")
b = save(LAYER, ll)
print("  layering: %d 行 -> %d 行，%d 字节" % (n0, len(ll), len(b)))

print()
print("=== 写盘后复核 ===")
for path in (PURITY, LAYER):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.split("\r\n")
    print("  %-24s bytes=%d CRLF=%d 裸LF=%d BOM=%s 行数=%d 乱码=%s"
          % (path.name, len(raw), raw.count(b"\r\n"),
             raw.count(b"\n") - raw.count(b"\r\n"), raw[:3] == b"\xef\xbb\xbf",
             len(lines), "\ufffd" in text))
    compile(text, str(path), "exec")
    print("      compile() OK；命中白名单前缀 出现次数 = %d"
          % sum(1 for l in lines if "命中白名单前缀" in l))
    for i, l in enumerate(lines):
        if "命中白名单前缀" in l:
            print("        :%d %s" % (i + 1, l.strip()))
print()
print("写盘完成")
