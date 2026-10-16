"""**可分发试用包**的守卫（Plan 07 Task 4）：``scripts/package.ps1`` + ``dist-pack/`` 那一条纪律。

--------------------------------------------------------------------------
⚠️ 本文件钉的是**实物**，不是散文
--------------------------------------------------------------------------
派单 Task 4 §1.7 要的五格里，①（包内容清单）②（大小与文件数的上界）
③（``dist-pack/`` 与包里的 ``*.db`` 都没入库）④（``.ps1`` 的 BOM/CRLF）
都能按字面钉；而「包里到底有什么」这一格只有**真的打一个包**才知道
——故本文件有一个 module 级的 fixture 真跑一次 ``scripts/package.ps1``
（落到 pytest 的临时目录里，⚠️ 不在仓库里堆产物），后面几条守卫一律读那个
zip 的**实物**。

⚠️ 而「解包 → 只有 Python → 一条命令起服务 → ``/api/health`` 200 且 16 条路由
各 200 → 停干净」那一格（派单 §1.6 的核心可执行判据）是**跨进程**的，
不住在 pytest 里（``tests/`` 一律用 :class:`fastapi.testclient.TestClient`、
一个端口都不占；口径逐字见 ``tests/test_serve.py`` 与 ``tests/test_trial.py``
的模块 docstring）——它的取证住在实现者报告里。

--------------------------------------------------------------------------
⚠️ 一个会让人**假绿**的坑（本波亲验，故本文件自己解析 zip）
--------------------------------------------------------------------------
:mod:`zipfile` 会把条目名里的 ``\\`` **悄悄换成正斜杠**再交给你。
而 PS 5.1 / .NET Framework 下 ``Compress-Archive`` 与
``ZipFile.CreateFromDirectory`` **两档都**把条目名写成反斜杠
（不合 ZIP 的规范 APPNOTE 4.4.17.1；在 Linux 的 ``unzip`` 与一部分解压工具下，
解出来的**不是目录树**，而是一个名字里带着反斜杠的**平文件**）。
用 ``namelist()`` 去看那两个包，报的是「0 个反斜杠条目，一切正常」
——本波第一版就是这么量的、而且量绿了。
故 :func:`_central_directory_names` **自己解析中央目录的原始字节**，
一个解压库都不用；``package.ps1`` 也因此改成逐个 ``CreateEntry``
并把分隔符显式换成正斜杠。
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import shutil
import subprocess
import zipfile

import pytest

from app.config import BACKEND_DIR

#: 仓库根。⚠️ 由 :data:`app.config.BACKEND_DIR` 推出来、不在本文件里敲第二遍路径
#: （与 ``tests/test_serve.py`` 的 ``REPO_ROOT`` 逐字同一条口径）。
REPO_ROOT = BACKEND_DIR.parent

PACKAGE_PS1 = REPO_ROOT / "scripts" / "package.ps1"
SERVE_PS1 = REPO_ROOT / "scripts" / "serve.ps1"
TRIAL_PS1 = REPO_ROOT / "scripts" / "trial.ps1"
GITIGNORE = REPO_ROOT / ".gitignore"

POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")

#: 落地目录名。⚠️ **字面量**（硬规矩 #35）：它的一半就是被测对象
#: （``package.ps1`` 的 ``$DefaultOutDirName`` 与 ``.gitignore`` 的那一行）。
OUT_DIR_NAME = "dist-pack"

#: 包名的前缀与时间戳的形状（实施计划 07 §4 逐字要求的那个形状）。
PACKAGE_NAME = re.compile(r"^pe-ims-trial-\d{8}-\d{6}\.zip$")

#: ⚠️ **必须不含**的五格（派单 Task 4 §1.7 ① 逐字点名）。
#: 前四个按**整段路径**判，第五个按**扩展名**判。
FORBIDDEN_SEGMENTS = (".git", "node_modules", ".superpowers", "tools")
FORBIDDEN_DB_SUFFIXES = (".db", ".db-journal", ".db-wal", ".db-shm")

#: ⚠️ **必须含**的几格。⚠️ 期望侧是**字面量**、不从 ``package.ps1`` 的
#: ``$MustContain`` 读回来跟自己比（那是同源断言）。⚠️ 而它刻意与脚本里那一份
#: **不完全相同**：两侧各自独立地钉一次，漂开时两条守卫一起红，
#: 而不是「脚本改了自己的清单、于是自己证明自己」。
REQUIRED_ENTRIES = (
    "README.md",
    "backend/pyproject.toml",
    "backend/alembic.ini",
    "backend/app/main.py",
    "backend/migrations/env.py",
    "backend/scripts/demo_bootstrap.py",
    "backend/scripts/serve_app.py",
    "backend/data/national_standard_2014.csv",
    "backend/data/alert_rules.yaml",
    "frontend/dist/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/src/App.vue",
    "frontend/src/router/index.ts",
    "Document/2026-09-28-体育闭环原型-设计spec.md",
    "Document/2026-10-15-甲方试用说明书.md",
    "Document/2026-10-15-实施计划07-交付与试用.md",
    "scripts/serve.ps1",
    "scripts/trial.ps1",
    "scripts/package.ps1",
)

#: 包大小与文件数的界。⚠️ **字面量**，与 ``package.ps1`` 里那四个变量
#: **各自独立**地钉一次（同源断言挡不住「两处一起改宽」，而异源的两处
#: 至少要求改的人**想到**还有另一处）。取值来历逐字见 ``package.ps1`` 那一段注释
#: （实测本波交付时是 339 个文件 / 约 9.8 MiB；⚠️ 那个数会跟着仓库长，故两侧都
#: 只钉**界**、不钉那个数本身 —— 硬规矩 #111）。
MAX_FILES = 2000
MAX_ZIP_BYTES = 48 * 1024 * 1024
MIN_FILES = 150
MIN_ZIP_BYTES = 2 * 1024 * 1024

#: ⚠️ 「打包一个字节都没改」那一格的对账样本：四种行尾/BOM 形状各一份。
BYTE_SAMPLES = (
    "scripts/serve.ps1",                                  # UTF-8 + BOM + CRLF
    "scripts/package.ps1",                                # 同上
    "Document/2026-10-15-甲方试用说明书.md",               # CRLF、无 BOM
    "backend/data/national_standard_2014.csv",            # LF（四个数据指纹之一）
    "backend/pyproject.toml",                             # LF
    "frontend/dist/index.html",                           # 构建产物
    "frontend/src/App.vue",                               # 前端源
)


def _package_ps1_code() -> str:
    """``package.ps1`` 的**代码段**（``#>`` 之后那一部分）。

    ⚠️ **只扫代码段**：``<# .DESCRIPTION #>`` 里逐字**提及**了它刻意不做的几件事
    （``npm run build``、``demo_bootstrap.py``、两个被否掉的压缩 API），
    扫整个文件会红在自己的说明文字上（硬规矩 #109）。
    姿势与 ``tests/test_serve.py`` 的 :func:`_serve_ps1_code` 逐字相同。
    """
    raw = PACKAGE_PS1.read_bytes()
    body = raw[3:].decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    assert body.count("#>") == 1, "package.ps1 的注释块形状变了，本函数的切法要跟着改"
    return body.split("#>", 1)[1]


def _statements() -> str:
    """代码段里**去掉注释行**之后的那一部分（提及不是本身，硬规矩 #109）。"""
    return "\n".join(
        line for line in _package_ps1_code().splitlines()
        if not line.lstrip().startswith("#")
    )


def _git(*args: str) -> str:
    """在**仓库根**跑一条 git 命令并要它的 stdout（失败当场 assert）。"""
    run = subprocess.run(
        ("git", "-c", "core.quotepath=false", *args),
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert run.returncode == 0, (args, run.stderr)
    return run.stdout


def _central_directory_names(zip_path: pathlib.Path) -> list[bytes]:
    """**直接读 zip 中央目录的原始字节**取条目名，⚠️ 不经任何解压库。

    ⚠️ 逐字理由见模块 docstring 的末节：:mod:`zipfile` 会把 ``\\`` 归一成正斜杠，
    用它判「分隔符合不合规范」是**假绿**（本波亲验）。
    中央目录的文件头签名是 ``PK\\x01\\x02``，偏移 28 两字节是名字长度、
    偏移 46 起是名字本身（APPNOTE 4.3.12）。
    """
    blob = zip_path.read_bytes()
    names: list[bytes] = []
    index = 0
    while True:
        index = blob.find(b"PK\x01\x02", index)
        if index < 0:
            return names
        length = int.from_bytes(blob[index + 28:index + 30], "little")
        names.append(blob[index + 46:index + 46 + length])
        index += 46 + length


@pytest.fixture(scope="module")
def package(tmp_path_factory) -> pathlib.Path:
    """**真的打一个包**，落到 pytest 的临时目录里（⚠️ 不在仓库里堆产物）。

    ⚠️ module 级：打一次要 2–3 秒（抄三百多个文件 / 约 17 MiB + 压 0.5 秒
    + 一次 PowerShell 启动），而下面七八条守卫读的都是同一个实物。
    """
    assert POWERSHELL, "本机没有 powershell：这一格的可执行判据跑不了"
    out_dir = tmp_path_factory.mktemp("dist-pack")
    run = subprocess.run(
        (POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(PACKAGE_PS1), "-OutDir", str(out_dir)),
        cwd=str(REPO_ROOT), capture_output=True, check=False,
    )
    stdout = run.stdout.decode("utf-8", "replace") + run.stderr.decode("utf-8", "replace")
    assert run.returncode == 0, (run.returncode, stdout[-4000:])
    zips = sorted(out_dir.glob("pe-ims-trial-*.zip"))
    assert len(zips) == 1, zips
    return zips[0]


# ===========================================================================
# ① 文件形状：UTF-8 + BOM + 纯 CRLF（与本仓另外 6 个 .ps1 同款）
# ===========================================================================


def test_package_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo():
    """**UTF-8 + BOM + 纯 CRLF**（派单 Task 4 §1.7 ④）。

    ⚠️ BOM 是承重的、不是洁癖：PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1`` 时按
    系统 ANSI 代码页（本机 GBK）解码，而本文件的注释里全是 UTF-8 中文——
    轻则注释乱码，重则某个字节序列里出现一个引号把语法弄坏
    （本仓为此付过四次代价）。⚠️ 三拍与 ``tests/test_serve.py`` 的同名一条逐字同款。
    """
    raw = PACKAGE_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "package.ps1 没有 BOM（PowerShell 5.1 会按 GBK 读它）"
    body = raw[3:]
    crlf = body.count(b"\r\n")
    bare = body.count(b"\n") - crlf
    assert bare == 0, f"package.ps1 有 {bare} 个裸 LF（本仓的 .ps1 一律 CRLF）"
    assert crlf > 100, f"package.ps1 只有 {crlf} 行，可能不是一个完整的脚本"
    body.decode("utf-8")

    serve = SERVE_PS1.read_bytes()
    assert serve[:3] == b"\xef\xbb\xbf" and serve[3:].count(b"\n") == serve[3:].count(b"\r\n"), (
        "既有那一款 serve.ps1 的形状变了，本条的「同款」判据要跟着改"
    )
    trial = TRIAL_PS1.read_bytes()
    assert trial[:3] == b"\xef\xbb\xbf" and trial[3:].count(b"\n") == trial[3:].count(b"\r\n")


# ===========================================================================
# ② 落地目录：一个所有者，而 .gitignore 与它不许漂开
# ===========================================================================


def test_the_output_directory_has_one_owner_and_gitignore_agrees():
    """``dist-pack`` 这个名字：``package.ps1`` 是所有者，``.gitignore`` 逐字同意它。

    三拍（⚠️ 两侧不同源：一侧是脚本、一侧是 ``.gitignore``、第三侧是 git 自己），
    姿势与 ``tests/test_trial.py`` 的
    :func:`~tests.test_trial.test_the_trial_database_name_has_one_owner_and_gitignore_agrees`
    逐字相同。

    ⚠️ 第 ③ 拍是本条的**牙**：一个包里是一整份仿真名册与体测数据，
    而 git 历史**删不掉**（与 ``backend/backups/`` 那一段逐字同一条理由）。
    """
    statements = _statements()
    assert f'$DefaultOutDirName = "{OUT_DIR_NAME}"' in statements, (
        f"package.ps1 里那个目录名不是 {OUT_DIR_NAME!r}"
    )
    # ① 字面量在**代码段**里恰好出现两次，⚠️ 而两次各有其名：一次是那个所有者
    #    的赋值，一次是排除清单里的 ``"dist-pack"``（⚠️ 那是**防御性**的第二道：
    #    ``dist-pack`` 本来就不在进包的顶层清单里，把它也列进排除清单是防「有人把
    #    ``$IncludeRoots`` 放宽成『仓库根下全要』」——那时上一个包会被打进下一个包）。
    #    第三次出现就意味着这个名字又多了一个住址。
    assert statements.count(f'"{OUT_DIR_NAME}"') == 2, statements[:600]
    assert "Join-Path $RepoRoot $DefaultOutDirName" in statements

    # ② .gitignore 有那一行
    ignored = GITIGNORE.read_bytes().decode("utf-8").splitlines()
    assert f"{OUT_DIR_NAME}/" in ignored, (
        f".gitignore 里少了 {OUT_DIR_NAME + '/'!r}（那是本波唯一被允许加的一行）"
    )

    # ③ git 自己也这么说
    checked = subprocess.run(
        ("git", "check-ignore", "-v", f"{OUT_DIR_NAME}/pe-ims-trial-x.zip"),
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert checked.returncode == 0, (
        f"git 不认为 {OUT_DIR_NAME}/ 被忽略：{checked.stdout!r} {checked.stderr!r}"
    )
    assert _git("ls-files", "--", OUT_DIR_NAME).strip() == "", (
        f"{OUT_DIR_NAME}/ 下有东西**被入库了**：包里是一整份仿真名册与体测数据，"
        "而 git 历史删不掉"
    )


def test_no_database_file_anywhere_in_the_repository_is_committed():
    """⚠️ 派单 Task 4 §1.7 ③ 的后半：**一个 ``.db`` 都没入库**（三个库名各问一次）。

    ``pe_trial.db`` 那一格 ``tests/test_trial.py`` 已经钉过，本条把面拓宽到
    ``git ls-files`` 的**全仓**：包里没有 ``.db``（②那一格），而仓库里也不该有
    ——三个名字（禁区的 ``pe.db``、演示库、试用库）都含一整份名册与体测数据。
    """
    assert _git("ls-files", "--", "*.db").strip() == "", "有 .db 被入库了"
    for name in ("backend/pe.db", "backend/pe_demo.db", "backend/pe_trial.db"):
        assert _git("ls-files", "--", name).strip() == "", name
    # ⚠️ 反空转：那三个文件在工作树里**确实存在**（否则上面三拍是空的）
    assert not (BACKEND_DIR / "pe.db").exists(), "禁区 backend/pe.db 存在"
    assert (BACKEND_DIR / "pe_trial.db").exists() or (BACKEND_DIR / "pe_demo.db").exists(), (
        "两个库一个都不在工作树里：本条的判据可能在指着一棵空树"
    )


# ===========================================================================
# ③ 包的内容清单（⚠️ 判据落在**实物**上）
# ===========================================================================


def test_the_package_name_and_size_are_within_the_four_reasoned_bounds(package):
    """包名的形状 + 大小与文件数的**四个界**（派单 Task 4 §1.7 ②）。

    ⚠️ **上界才是这一格的牙**：``node_modules``（5 万个文件 / 200 MiB 以上）、
    ``.git``（几千个文件）、``tools\\cloudflared.exe``（55 MiB）三个漏进包的话，
    ``$MustContain`` 那种「必须含」的清单守卫**一条都不会红**（它们只管「少了什么」，
    不管「多了什么」）⇒ 只有上界抓得住。
    ⚠️ 下界只挡「包被掏空」，刻意取得很松（逐字理由见 ``package.ps1`` 那一段注释）。
    """
    assert PACKAGE_NAME.match(package.name), package.name
    size = package.stat().st_size
    assert MIN_ZIP_BYTES <= size <= MAX_ZIP_BYTES, (
        f"包 {size} B 不在 [{MIN_ZIP_BYTES}, {MAX_ZIP_BYTES}] 里"
    )
    with zipfile.ZipFile(package) as archive:
        names = [info.filename for info in archive.infolist()]
    assert MIN_FILES <= len(names) <= MAX_FILES, (
        f"包里有 {len(names)} 个条目，不在 [{MIN_FILES}, {MAX_FILES}] 里"
    )


def test_the_package_contains_everything_required_and_none_of_the_forbidden(package):
    """⚠️ 派单 Task 4 §1.7 ① 的两半：**必须含**的逐个在场、**必须不含**的一个都不在。

    「必须不含」那五格（``.git`` / ``node_modules`` / ``.superpowers`` / ``tools`` /
    ``*.db``）逐格按**整段路径**判：``(^|/)名字(/|$)``，
    于是 ``.gitignore`` 不会被 ``.git`` 那一格误伤（而它本来也在排除清单里）。
    """
    names = _central_directory_names(package)
    decoded = [name.decode("utf-8") for name in names]

    # ① 必须含
    missing = [entry for entry in REQUIRED_ENTRIES if entry not in decoded]
    assert not missing, f"包里缺了 {len(missing)} 格：{missing}"

    # ② 必须不含（四个整段路径）
    for segment in FORBIDDEN_SEGMENTS:
        hits = [
            name for name in decoded
            if name == segment or name.startswith(segment + "/")
            or ("/" + segment + "/") in name or name.endswith("/" + segment)
        ]
        assert not hits, f"包里出现了**必须不含**的 {segment}（{len(hits)} 个，头三个 {hits[:3]}）"

    # ③ 必须不含（*.db 与它的三个侧车后缀）
    db_hits = [name for name in decoded if name.endswith(FORBIDDEN_DB_SUFFIXES)]
    assert not db_hits, f"包里出现了 .db（{db_hits[:3]}）：包里一个库都不放，首次启动自己灌"

    # ⚠️ 反空转：包里**确实**有子目录（否则上面四拍可能只是因为它是个平包）
    assert any("/" in name for name in decoded), decoded[:5]
    # ⚠️ 而 ``backend/data/`` 那 24 个指纹文件确实在（少了它们，解包之后
    #    分层那一步会在离真因很远的地方炸）
    data = [name for name in decoded if name.startswith("backend/data/") and not name.endswith("/")]
    assert len(data) >= 24, (len(data), data[:5])


def test_the_zip_entry_names_use_forward_slashes_as_the_zip_format_requires(package):
    """⚠️ 条目名一律用**正斜杠**（ZIP 的规范 APPNOTE 4.4.17.1），一个反斜杠都没有。

    这一格是本波**实测**出来的真缺陷，不是想出来的：PS 5.1 / .NET Framework 下
    ``Compress-Archive`` 与 ``ZipFile.CreateFromDirectory`` **两档都**把条目名写成
    ``a\\b\\deep.txt``（Windows 的分隔符）。Windows 自己的「全部解压缩」恰好认得它，
    故在开发机上**看不出来**；而 Linux 的 ``unzip`` 与一部分解压工具会把它当成
    **一个文件名**，解出来是一个平文件、不是目录树 ⇒ 包在甲方那台机器上是废的。

    ⚠️⚠️ 判据**必须**读原始字节：:mod:`zipfile` 会把 ``\\`` 悄悄归一成正斜杠，
    用它判这一格是**假绿**（本波第一版就是这么量的、而且量绿了；
    逐字取证见模块 docstring 的末节）。
    """
    raw_names = _central_directory_names(package)
    assert raw_names, "中央目录里一个条目都没解析出来：本函数的切法失效了"
    with_backslash = [name for name in raw_names if b"\\" in name]
    assert not with_backslash, (
        f"{len(with_backslash)} 个条目的名字带着反斜杠（头三个 {with_backslash[:3]}）："
        "④ 那一步的 -replace 被改坏了，或有人把 CreateFromDirectory 换回来了"
    )
    with_slash = [name for name in raw_names if b"/" in name]
    # ⚠️ 反空转：包里有几百个带子目录的条目 ⇒ 上面那一格不是因为「压根没有子目录」
    assert len(with_slash) >= 300, len(with_slash)
    # ⚠️ 而 :mod:`zipfile` 读回来的是同一批名字（它归一化过，故这里只断数量）
    with zipfile.ZipFile(package) as archive:
        assert len(archive.namelist()) == len(raw_names)


def test_packaging_changes_not_one_byte_of_what_it_packs(package):
    """⚠️ **打包一个字节都没改**：行尾与 BOM 逐字保住（派单 §4「zip 里的文件行尾」）。

    四种形状各取一份对账（⚠️ 两侧不同源：一侧是仓库工作树里的原文件、
    一侧是 zip 里的那个条目）：

    * ``scripts/*.ps1`` —— UTF-8 **+ BOM** + 纯 CRLF（本仓为此付过四次代价）；
    * ``Document/**/*.md`` —— CRLF、**无** BOM（``.gitattributes`` 钉的 ``text eol=crlf``）；
    * ``backend/data/**`` —— **LF**（四个数据指纹 + 18 个模板指纹的落脚点，
      ``.gitattributes`` 钉的 ``eol=lf``；改一个字节就是一个指纹红）；
    * ``frontend/dist/**`` 与 ``frontend/src/**`` —— 构建产物与源，原样。

    ⚠️ 失效形态是具体的：一个把文件当**文本**读写的打包实现（``Get-Content`` +
    ``Set-Content``、或 ``Compress-Archive`` 的某些路径）会在 Windows 上把 LF 补成 CRLF、
    或把 BOM 剥掉 —— 而两种都**不会**让「文件在不在」那一格红。
    """
    with zipfile.ZipFile(package) as archive:
        for relative in BYTE_SAMPLES:
            source = (REPO_ROOT / relative).read_bytes()
            packed = archive.read(relative)
            assert packed == source, (
                f"{relative}：包里的字节与工作树里的原文件**不同**"
                f"（{len(packed)} B vs {len(source)} B）⇒ 打包改了它"
            )
            # ⚠️ 再把那四种形状逐个点名（否则「逐字节相同」只是把责任推给了工作树）
            if relative.endswith(".ps1"):
                assert packed[:3] == b"\xef\xbb\xbf", relative
                assert packed.count(b"\n") == packed.count(b"\r\n"), relative
            elif relative.startswith("Document/"):
                assert packed[:3] != b"\xef\xbb\xbf", relative
                assert packed.count(b"\n") == packed.count(b"\r\n"), relative
            elif relative.startswith("backend/data/"):
                assert packed.count(b"\r\n") == 0, (relative, "backend/data/** 一律 LF")
    # ⚠️ 反空转：那七个样本**确实**是四种不同的形状（否则上面那几拍是空的）
    shapes = set()
    for relative in BYTE_SAMPLES:
        blob = (REPO_ROOT / relative).read_bytes()
        shapes.add((blob[:3] == b"\xef\xbb\xbf", blob.count(b"\r\n") > 0))
    assert (True, True) in shapes and (False, True) in shapes and (False, False) in shapes, shapes


# ===========================================================================
# ④ 它**不当**第二个所有者：不构建、不灌库、不起服务、不装依赖
# ===========================================================================


def test_the_packager_never_builds_seeds_serves_or_installs_anything():
    """``package.ps1`` 只**打包**：那四件事一件都不做，⚠️ 判据是「调用形状」而不是「词出现过」。

    ⚠️ 四格各挡一档失效：

    ① **不构建**（``npm`` / ``node``）：「怎么构建」的唯一所有者是 ``serve.ps1`` 的 ②。
       一个打包脚本偷偷跑一次 ``npm run build`` 会让「包里那份产物是哪一次构建出来的」
       变成一件没人知道的事；
    ② **不灌库**（``demo_bootstrap.py`` / 那三个禁跑 CLI）：包里一个 ``.db`` 都不放，
       首次启动由 ``trial.ps1`` 灌（⚠️ 而 ``backend/data/**`` 一字节都不许动，
       ``backend/data/seed/`` 恒为 0 文件）；
    ③ **不起服务**（``uvicorn`` / ``Start-Process``）：那是 ``serve.ps1`` 的活；
    ④ **不装依赖**（``pip install``）：静默改甲方那台机器的 Python 环境不是交付物
       该有的形状（姿势同 ``serve.ps1 -Lan`` 的「不自动改防火墙」）。

    ⚠️ 判据落在**语句**上，而含那些词的语句一律必须是 ``Write-Host`` / ``throw``
    （= 打印给人看的），姿势逐字同 ``tests/test_serve.py`` 里
    ``netsh`` 那一拍（``serve.ps1`` 打印一条 netsh 命令，而一次都不跑它）。
    ⚠️⚠️ 而**清单数组里的那几行要跳过**（本波首跑实测红在自己身上）：
    ``$MustContain`` 里逐字写着 ``backend/scripts/demo_bootstrap.py``
    ——那是「这个文件**必须在包里**」（它是解包之后 ``trial.ps1`` 灌库要用的那个入口），
    而不是「本脚本跑它」。两者在颜色上确实一样，故按**行的形状**分开：
    一行若整个就是一个字符串字面量（``^\\s*"…",?$``），它是清单的元素、不是一条调用。
    ⚠️ 于是本条**同时**钉住两半：那个灌库器**在包里**（下面那一拍反空转），
    而打包脚本**一次都不跑它**。
    """
    statements = _statements()
    lines = statements.splitlines()

    #: 一行整个就是一个字符串字面量 ⇒ 它是某个清单数组的元素，不是一条调用。
    array_element = re.compile(r'^\s*"[^"]*",?\s*$')
    executable = [line for line in lines if not array_element.match(line)]
    assert len(executable) < len(lines), "一行清单元素都没跳过：上面那个正则失效了"

    for needle in ("npm", "node ", "node.exe", "demo_bootstrap", "uvicorn",
                   "pip install", "-m app.", "Start-Process"):
        hits = [line for line in executable if needle in line]
        for line in hits:
            stripped = line.strip()
            assert stripped.startswith("Write-Host") or stripped.startswith("throw"), (
                f"{needle!r} 出现在一条**非打印**的语句里（本脚本只打包，那四件事一件都不做）→ "
                f"{stripped[:200]}"
            )
    # ⚠️ 反空转的另一半：那个灌库器**确实**在「必须含」的清单里
    #    （包里少了它，解包之后 trial.ps1 的第 ③ 步就跑不起来）。
    assert any('"backend\\scripts\\demo_bootstrap.py"' in line for line in lines), (
        "demo_bootstrap.py 不在 $MustContain 里：它是解包之后灌库要用的那个入口"
    )
    # ⚠️ 反空转：它**确实**告诉人该去哪儿构建、该跑哪一条命令装依赖
    #    （否则上面四拍可能只是因为脚本一句话都不说）
    assert any("npm run build" in line for line in lines), "它没有把「先构建」那一条命令说清楚"
    assert any("pip install -e backend" in line for line in lines), (
        "它没有把「装依赖」那一条命令说清楚（清单的唯一所有者是包里的 pyproject.toml）"
    )
    # ⚠️ 而它**唯一**真的动文件系统的两件事：File.Copy（原字节抄进 staging）
    #    与 ZipArchive（压），⚠️ 一个都不经文本层
    assert "[System.IO.File]::Copy(" in statements
    assert "CreateEntry(" in statements
    assert "CopyTo(" in statements
    for forbidden_call in ("Get-Content", "Set-Content", "Out-File", "Add-Content"):
        assert forbidden_call not in statements, (
            f"{forbidden_call} 出现在语句里：它经**文本层**读写文件，会动行尾与 BOM"
            "（⚠️ 本脚本抄文件一律用 File.Copy、压一律用 Stream.CopyTo，都是原字节）"
        )


# ===========================================================================
# ⑨ 脚本内那 4 份自检 + staging 的收尾（Plan 07 Task 8 · 终审 S4-9 / S4-16）
# ===========================================================================

#: ⚠️ ``package.ps1`` 里那 **4** 份**脚本内自检**的形状（终审 S4-9）。
#: 期望侧一律是**字面量**：本文件上面那一份 :data:`REQUIRED_ENTRIES` /
#: :data:`MAX_FILES` / ``>= 24`` 钉的是**包实物**，而这一份钉的是
#: 「脚本里那几份副本还在不在」⇒ 两侧不同源，漂开时两条守卫一起红。
#: ⚠️ 而**取值**被放宽（``2000 → 99999``、``24 → 1``、17 项里删掉几项）
#: 今天仍然只有本条的第 ① 拍能抓到形状、抓不到值 ⇒ 那一格登记在 spec §15 的 **F8**。
SELF_CHECK_SHAPES = (
    "$MustContainDataCount = 24",
    "$MaxFiles = 2000",
    "$MustContain = @(",
    "两份清单打架了",
)

#: ``$MustContain`` 的元素数。⚠️ 字面量，理由同上（脚本里那一份是 17 个具体路径）。
MUST_CONTAIN_ITEMS = 17


def test_the_staging_cleanup_has_one_owner_and_there_is_no_exit_after_staging_exists():
    """脚本内那 4 份自检**在场**、两条「清单打架」是 ``throw``、staging 的收尾只有一个所有者。

    ⚠️ 三格各挡一档失效（终审 S4-9 的 ①② 与 S4-16）：

    ① **4 份脚本内自检在场**（按名字/形状断言）。⚠️ 这**不是**假守卫：
       本文件自己那一份 :data:`REQUIRED_ENTRIES` / :data:`MAX_FILES` / ``>= 24``
       钉的是**包实物**，而脚本里那几份是**另一份副本**（文件里逐字写了这条纪律），
       改前「把副本删掉/放宽」没有任何守卫会红（终审的变异 P5/P6/P7/P8 全绿）；
    ② **``throw`` 而不是 ``exit 1``**：文件头那个 ``trap`` 兜的是**错误**，
       而 ``exit`` 不是错误 ⇒ 走 ``exit`` 的话 staging（十几 MiB）留在 ``$env:TEMP`` 里。
       那正是 commit ``8304175`` 修的实况，也是终审 P7 那一格定点变异
       （⚠️ 而它今天**结构上不可达**：``$IncludeRoots ∩ $ExcludeDirNames = ∅``，
       故只有源码面的守卫能钉住它 —— 运行时永远走不到那一条）；
    ③ **staging 的收尾只有一个所有者、且带 bounded retry**（S4-16）：改前是两份
       逐字相同的 ``Remove-Item … -ErrorAction SilentlyContinue``，而 PS 5.1 的
       ``Remove-Item -Recurse`` 会**部分失败**（本机 ``$env:TEMP`` 上实测剩 3 个文件、
       全是 ``scripts`` 下的 ``.ps1``）⇒ 每次打包都可能留一份残渣。

    ⚠️ 判据落在**语句**上（:func:`_statements` 已经把注释行剥掉，提及不是本身）。
    """
    statements = _statements()
    lines = statements.splitlines()
    assert len(lines) > 300, "package.ps1 的代码段短了一大截：本条的切法要跟着改"

    # --- ① 4 份脚本内自检在场 -------------------------------------------------
    for shape in SELF_CHECK_SHAPES:
        assert shape in statements, f"脚本内自检 {shape!r} 不见了（S4-9 的 ①）"
    head = [i for i, line in enumerate(lines) if line.strip().startswith("$MustContain = @(")]
    assert len(head) == 1, head
    items: list[str] = []
    for line in lines[head[0] + 1:]:
        if line.strip() == ")":
            break
        items.append(line)
    assert len(items) == MUST_CONTAIN_ITEMS, (
        f"$MustContain 的元素数是 {len(items)}，不是 {MUST_CONTAIN_ITEMS}："
        "少了 = 「包能起」那一格的判据被掏空（S4-9 的 ①）"
    )
    assert all(re.match(r'^\s*"[^"]+",?\s*$', item) for item in items), items

    # --- ② 两条「清单打架」是 throw；staging 建好之后一条 exit 都不许有 ---------
    fight_throw = [line.strip() for line in lines
                   if line.strip().startswith("throw") and "两份清单打架了" in line]
    assert len(fight_throw) == 2, (
        f"「两份清单打架」的 throw 只剩 {len(fight_throw)} 条（要 2 条：目录一条、文件一条）"
        "⇒ 撤销 8304175 就是这一格"
    )
    create = [i for i, line in enumerate(lines)
              if "New-Item -ItemType Directory -Force -Path $Stage" in line]
    assert len(create) == 1, create
    tail_exits = [lines[i].strip() for i in range(create[0], len(lines))
                  if re.match(r"^\s*exit\s", lines[i])]
    assert tail_exits == ["exit 0"], (
        f"staging 建好之后出现了 {tail_exits!r}：那一条路径会**绕过** trap（exit 不是错误），"
        "于是十几 MiB 的 staging 留在 $env:TEMP 里（S4-9 的 ②）"
    )
    head_exits = [lines[i].strip() for i in range(create[0]) if re.match(r"^\s*exit\s", lines[i])]
    assert head_exits and all(e == "exit 1" for e in head_exits), head_exits

    # --- ③ 收尾一个所有者 + 有界重试 -------------------------------------------
    assert statements.count("function Remove-Staging") == 1, "收尾的那个函数不在（或不止一份）"
    # ⚠️ 「一个所有者」那一拍的判据是**「静默地删 staging」在整个脚本里恰好一次、
    #    且它在 Remove-Staging 的函数体里**。⚠️ 本波首跑用的是「数一个更长的字面量
    #    （带 -LiteralPath）出现 1 次」，而定点变异 M4（往 trap 里**再加回**一份改前那个
    #    不带 -LiteralPath 的 Remove-Item）**假绿**了 —— 那一份的字面量更长/更短都不影响
    #    计数。故判据改成按**语义**数：`Remove-Item` + `$Stage` + `SilentlyContinue`
    #    三个词同一行。⚠️ 而 ② 建 staging 之前那一份清旧树的 `Remove-Item`
    #    **刻意不带** SilentlyContinue（清不掉就该 throw，否则旧树会污染新包），
    #    故它不在这一拍的计数里 —— 那一格是「严格」的，与收尾那一格「尽力 + 重试」不同。
    silent = [(i, lines[i].strip()) for i in range(len(lines))
              if "Remove-Item" in lines[i] and "$Stage" in lines[i]
              and "SilentlyContinue" in lines[i]]
    assert len(silent) == 1, (
        f"「静默地删 staging」出现了 {len(silent)} 次（要恰好 1 次）："
        f"{[text for _, text in silent]}"
        "—— 改前 trap 与 ⑥ 之后各一份逐字相同的，两份都会部分失败（S4-16）"
    )
    owner = [i for i, line in enumerate(lines) if line.strip().startswith("function Remove-Staging")]
    assert len(owner) == 1, owner
    assert silent[0][0] > owner[0], (
        "那一份**不在** Remove-Staging 之后 ⇒ 它不是函数体里的那一份，"
        "于是「收尾只有一个所有者」这句话不成立"
    )
    calls = [line.strip() for line in lines
             if re.search(r"\bRemove-Staging\b", line) and not line.strip().startswith("function")]
    assert len(calls) == 2, (
        f"Remove-Staging 被调用 {len(calls)} 次（要 2 次：trap 里一次、⑥ 之后一次）"
    )
    assert any("-le 3" in line for line in lines), "有界重试不见了（S4-16 的修法就是它）"
    assert any("Start-Sleep" in line for line in lines), "重试之间没有等 ⇒ 那一格是瞬时的句柄竞争，不等等于没重试"
    assert "function Get-StagingLeftovers" in statements, (
        "删不掉时不再把**剩下哪几个文件**报出来（改前只说「删不掉」，人要自己去 TEMP 里翻）"
    )
    # ⚠️ 顺手钉住 S4-3 的同族那一格：⑥ b 那一段**不印**一个写死的人数
    #    （本脚本不灌库、不起服务 ⇒ 它手上既没有库也没有 /api/health 可读，
    #    那一档下最诚实的做法是不印那个数；它的唯一所有者是 demo_bootstrap.py 的
    #    --students，而运行时读它的唯一所有者是 /api/health）。
    assert "60 人仿真库" not in statements, "⑥ b 又写死了一个人数（终审 S4-3 的同族）"
