"""**全仓**的源码卫生：一条今天只有一格内容的守卫，而它挡的是一类**静默**的债。

--------------------------------------------------------------------------
为什么要有这个文件（Plan 06 Task 11 / A2）
--------------------------------------------------------------------------

``app/main.py`` 的模块 docstring 里有一行 Windows 的路径::

    powershell -ExecutionPolicy Bypass -File scripts\\serve.ps1

那个 ``\\s`` 在一个**非** raw 的字符串里是一个 *invalid escape sequence*：Python 把
「反斜杠 + 一个不是合法转义首字母的字符」**原样**留着，同时冒一条警告。
⚠️ 它 today 只是「一条警告」，而它的失效方向是**逐级变硬**的：

* **Python 3.11**（本机实测）→ ``DeprecationWarning``；
* **Python 3.12 起** → ``SyntaxWarning``；
* 官方口径是**将来会变成 ``SyntaxError``** —— 那一天它不再是噪声，而是
  ``import app.main`` **当场炸**（而 ``app.main`` 有一条模块级的 ``app = create_app()``，
  故 ``uvicorn app.main:app`` 也起不来）。

⚠️⚠️ **而它今天为什么没被发现**：Python 的缺省警告过滤器把「不是在 ``__main__`` 里
触发的 ``DeprecationWarning``」一律**吞掉**，故 ``python -c "import app.main"``
的 stderr 是**空的**（本机亲跑取证）。它只在两种场合露头：

1. ``pytest`` 把过滤器调成 ``always`` → 出现在 ``warnings summary`` 一节里
   （⚠️ 且**只在 ``__pycache__`` 冷的时候**：一个已经编译好的 ``.pyc`` 被复用时
   根本不再走编译，于是警告也不发。本机实测：清掉 25 个 ``__pycache__`` 之后，
   ``pytest tests/test_main.py -q`` 从「1 warning」变成「3 warnings」，
   多的那两条正是本文件钉的那一格）；
2. ``python -W error::DeprecationWarning -c "import app.main"`` → 当场
   ``SyntaxError: invalid escape sequence '\\s'``。

⚠️ 于是「跑一遍测试没红」证明不了这一格不存在。本文件那两条守卫因此**自己去编译**
（:func:`compile`，不走 ``import``、也不吃 ``__pycache__``），把警告**录下来数**。

--------------------------------------------------------------------------
⚠️ 扫描面是**全仓**，不是 ``backend/``、更不是只扫 ``main.py``
--------------------------------------------------------------------------

派单逐字要求「它必须是全仓扫描，不是只扫 ``main.py``，否则下一次长在别处就抓不到」。
故 :data:`REPO_ROOT` 是仓库根（``backend/tests/architecture/`` 往上三级），
扫描面是它下面**全部** ``.py``。本机实测 **595** 个，逐桶如下::

    393  .superpowers/sdd/**      历次 wave 的探针脚本（**git 追踪**）
     95  backend/app/**
     60  backend/tests/**
     38  .superpowers/_snapshots/ 一份 2026-10-07 的陈旧副本（⚠️ **被 .gitignore 掉**）
      5  backend/migrations/**
      4  backend/scripts/**

⚠️ ``.superpowers/sdd/**`` 的探针脚本**刻意不排除**：它们是**真的会被跑**的 ``.py``
（每一波的实现者都用 ``python <探针>.py`` 取证），而一个 invalid escape 在
Python 3.12+ 上会让它们在 ``SyntaxWarning`` 里泡着、在将来直接 ``SyntaxError``。
⚠️ 排除的只有**不该被当成源码**的那几棵子树（:data:`EXCLUDED_DIRS`）。

⚠️ **如实记一格机器相关性**（硬规矩 #39）：那 38 个 ``_snapshots`` 下的文件在
``.gitignore`` 第 18 行里，故**本机扫描面 595、一份新克隆上是 557**。
:data:`MIN_SCANNED_FILES` 取下界 **150**（``backend/`` 单独就有 162）正是为了让
这一格**不影响红绿**。⚠️ 而它确实留下一档噪声：一个把 invalid escape 写进那份
陈旧副本的人会看到本条红、而在一份新克隆上它是绿的。处置是把那一行修掉、
或删掉那份副本（它不属于交付物）——**不是**把本条守卫调松。

--------------------------------------------------------------------------
本文件的另一条守卫：``main.py`` 的 docstring **仍然是 raw 的**
--------------------------------------------------------------------------

修法有两种，都是语义无损的：把 ``\\s`` 写成双反斜杠，或给整个 docstring 加 ``r``
前缀。本仓选了后者（一个字符的改动，且**对将来往那个 docstring 里再写一条 Windows
路径免疫**）。⚠️ 而它的代价是「那个 docstring 里再也写不出一个真的换行转义」，
故 :func:`test_main_module_docstring_is_raw_so_its_windows_path_stays_verbatim`
把「它是 raw 的」与「那一行路径**逐字**还在」两格一起钉住：
少了本条，下一个人把 ``r`` 前缀删掉（例如为了在里面写一个 ``\\n``）不会有任何测试红，
而那一格会**当场回到** invalid escape。
"""
from __future__ import annotations

import pathlib
import warnings

#: 仓库根。⚠️ ``parents[3]``：本文件在 ``backend/tests/architecture/`` 下，
#: ``[0]`` = ``architecture``、``[1]`` = ``tests``、``[2]`` = ``backend``、``[3]`` = 仓库根。
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: 扫描面**排除**的子树名（按 ``parts`` 判，故任何深度上的同名目录都被排掉）。
#: ⚠️ ``.superpowers`` **不在**这一份里（理由逐字见模块 docstring 第三节）。
EXCLUDED_DIRS = frozenset({
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
})

#: 扫描面的**下界**（反空转）。⚠️ 它是一个下界而不是等号：每一波都会往
#: ``.superpowers/sdd/**`` 里加探针脚本，写死等号的话下一条探针就让本条红，
#: 而「红」与「真有 invalid escape」在颜色上无法区分（硬规矩 #50）。
#: ⚠️ 本机实测 595 个（构成逐桶见模块 docstring 第三节）；``backend/`` 单独就有
#: **164** 个（本文件与迁移 4 落地之后），故 150 这个下界即使 ``.superpowers``
#: 整棵树被搬空也仍然成立。
MIN_SCANNED_FILES = 150

#: **必须在扫描面里**的那一个文件：本文件存在的全部理由。
#: ⚠️ 少了这一拍，「扫描面写错、一个文件都没扫到」与「全仓干净」在断言上不可分辨
#: （前者会让 offenders 恒为 ``[]``）—— 上面的下界挡的是「扫得太少」，
#: 本行挡的是「**恰好漏掉了那个已知反例**」。
KNOWN_OFFENDER_PATH = REPO_ROOT / "backend" / "app" / "main.py"


def _python_files() -> list[pathlib.Path]:
    """``REPO_ROOT`` 下**全部** ``.py``（排掉 :data:`EXCLUDED_DIRS`），按路径升序。"""
    # ⚠️ rglob 对一个不存在的目录静默返回空，缺这一行守卫会空转全绿。
    assert REPO_ROOT.is_dir(), f"仓库根不存在，守卫将空转全绿: {REPO_ROOT}"
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.py")
        if not (set(path.relative_to(REPO_ROOT).parts) & EXCLUDED_DIRS)
    )


def _invalid_escapes(path: pathlib.Path) -> list[str]:
    """编译 ``path`` 一次，把它冒出来的**全部** invalid escape sequence 警告报成字符串。

    ⚠️ 用 :func:`compile` 而**不是** ``import``：
    ① ``import`` 会吃 ``__pycache__``（一个热的 ``.pyc`` 根本不再编译，警告也就不发）；
    ② ``import`` 有副作用（``app.main`` 有一条模块级的 ``app = create_app()``）；
    ③ ``import`` 会受 Python 缺省警告过滤器的影响（非 ``__main__`` 的
    ``DeprecationWarning`` 被吞）。``compile`` 三格都没有。

    ⚠️ 判据是**警告的文本**而**不是**它的类别：本机 Python 3.11 给的是
    ``DeprecationWarning``，3.12+ 给的是 ``SyntaxWarning``。按类别判的话，
    本条守卫会在升级 Python 的那一天**静默失效**（那正是它要防的失效方向）。
    """
    source = path.read_bytes().decode("utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            # ⚠️ 一个真的语法错误**不是**本条要报的东西（它会让别的守卫红在更近的地方：
            #    ``tests/architecture/test_layering.py`` 与 ``test_domain_purity.py``
            #    都对 ``backend/**`` 做 ``ast.parse``），但它会让本条**跳过**这个文件，
            #    故如实报出来、不静默吞掉。
            return [f"{path}: SyntaxError（本条无法编译它）: {exc}"]
    return [
        f"{path}:{warning.lineno}: {warning.message}"
        for warning in caught
        if "invalid escape sequence" in str(warning.message)
    ]


def test_no_python_file_in_the_repository_carries_an_invalid_escape_sequence():
    """**全仓**的 ``.py`` 一个 invalid escape sequence 都不许有。

    ------------------------------------------------------------------------
    ⚠️ 这一条**在 Plan 06 Task 11 之前是红的**（红 1 格）
    ------------------------------------------------------------------------
    本机实测（595 个 ``.py``）：恰好 **1** 条警告、在 **1** 个文件里——
    ``backend/app/main.py:1: invalid escape sequence '\\s'``
    （``1`` 是模块 docstring 的起始行号，真因在第 41 行那条 Windows 路径上）。
    修法是给那个 docstring 加 ``r`` 前缀（语义无损：``__doc__`` 的 sha256 实测逐字不变）。

    ------------------------------------------------------------------------
    ⚠️ 三拍（红绿两档都在场，硬规矩 #50）
    ------------------------------------------------------------------------
    ① **offenders 为空**（本条的牙）；
    ② **反空转 · 数量**：扫描面 ≥ :data:`MIN_SCANNED_FILES`；
    ③ **反空转 · 已知反例**：:data:`KNOWN_OFFENDER_PATH` **在**扫描面里。
       ⚠️ 少了 ③，把 :data:`EXCLUDED_DIRS` 加一项 ``"app"`` 就能让本条恒绿。
    """
    files = _python_files()
    assert len(files) >= MIN_SCANNED_FILES, (
        f"只扫到 {len(files)} 个 .py（下界 {MIN_SCANNED_FILES}）："
        f"REPO_ROOT 大概指错了 = {REPO_ROOT}"
    )
    assert KNOWN_OFFENDER_PATH in files, (
        f"{KNOWN_OFFENDER_PATH} 不在扫描面里 —— EXCLUDED_DIRS 把它排掉了？"
        f"（本机实测扫描面 {len(files)} 个）"
    )

    offenders: list[str] = []
    for path in files:
        offenders.extend(_invalid_escapes(path))
    assert offenders == [], (
        f"全仓有 {len(offenders)} 处 invalid escape sequence（扫描面 {len(files)} 个 .py）。\n"
        "⚠️ Python 3.11 冒 DeprecationWarning、3.12 起冒 SyntaxWarning、将来是 SyntaxError。\n"
        "修法：给那个字符串加 `r` 前缀，或把反斜杠写成双反斜杠 —— 两者都语义无损，\n"
        "选**对该处上下文无损**的那一种（一个 Windows 路径用 `r`，一个正则用 `r`，\n"
        "一句要真换行的散文用双反斜杠）。\n  " + "\n  ".join(offenders[:20])
    )


def test_main_module_docstring_is_raw_so_its_windows_path_stays_verbatim():
    """``app/main.py`` 的模块 docstring **是 raw 的**，且那条 Windows 路径**逐字**还在。

    ⚠️ 它是上一条的**配套**：上一条钉「全仓没有 invalid escape」，本条钉
    「``main.py`` 那一格的**修法本身**没被撤回」。少了本条，下一个人把 ``r`` 前缀
    删掉（例如为了在那个 docstring 里写一个真的换行转义）会让上一条红，
    而报错文本指向的是「全仓有 1 处 invalid escape」——**离真因（那个 ``r``）有一层**。
    本条让它报在真因上。

    ⚠️ 三拍：① 源文件的第一个字符就是 ``r``；② ``__doc__`` 里那一行路径**逐字**在
    （= raw 那一改真的没有改掉值）；③ ``__doc__`` 里**没有**任何一处
    「反斜杠 + 一个合法转义首字母」被解释掉（⚠️ 这一拍是 ② 的补集：
    ② 钉的是「该有的还在」，③ 钉的是「不该被解释的一个都没被解释」）。
    """
    import app.main as main_module

    source = KNOWN_OFFENDER_PATH.read_bytes().decode("utf-8")
    # ① raw 前缀（⚠️ 期望侧是**源文件的第一个字符**，不是从 __doc__ 反推）
    assert source.startswith('r"""'), (
        "app/main.py 的模块 docstring 不再是 raw 的了 —— 它里面有一条 Windows 路径"
        "（scripts\\serve.ps1），去掉 r 前缀会当场回到 invalid escape sequence"
    )

    doc = main_module.__doc__ or ""
    # ② 那一行逐字还在（反斜杠是**一个**，不是两个 —— 双反斜杠说明有人改错了修法）
    assert "powershell -ExecutionPolicy Bypass -File scripts\\serve.ps1" in doc, (
        "docstring 里那条 Windows 路径变了（本条要的是 raw 前缀，不是把反斜杠写两遍）"
    )
    # ③ 没有任何一个转义被解释掉：raw 字符串里反斜杠**个数**就是源文件里反斜杠的个数
    docstring_body = source[4:]
    end = docstring_body.index('"""')
    raw_backslashes = docstring_body[:end].count("\\")
    assert doc.count("\\") == raw_backslashes, (
        f"__doc__ 里有 {doc.count(chr(92))} 个反斜杠，而源文件那段 docstring 里写了 "
        f"{raw_backslashes} 个 —— 说明有转义被解释掉了（raw 前缀没生效？）"
    )
