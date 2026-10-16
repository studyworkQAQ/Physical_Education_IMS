"""**试用档**的守卫（Plan 07 Task 1）：``scripts/trial.ps1`` + ``backend/pe_trial.db`` 那一条纪律。

--------------------------------------------------------------------------
⚠️ 本文件钉的是**脚本的形状**，不是「服务真的起来了」
--------------------------------------------------------------------------
「一条命令起试用」那一格的可执行判据是**跨进程**的（灌一个库、起一个 uvicorn、
用无头浏览器量 16 条路由上的告示），故它住在 ``frontend/scripts/smoke.mjs``
的**第三档**（试用档 = 产品档 + ``PE_TRIAL=1`` + 试用库）与本波实现者报告里，
而**不在** pytest 里：``tests/`` 一律用 :class:`fastapi.testclient.TestClient`、
一个端口都不占（逐字口径见 ``tests/test_serve.py`` 的模块 docstring 第一节）。

⚠️ **本文件补的是那一格补不到的东西**：smoke 全绿只证明「试用档下 16 条路由都挂着
告示」，而它**证明不了**下面这五档 —— 五档的失效方向都是**静默**的：

1. ``trial.ps1`` 变成了**第二个服务器启动器**（于是「产品档怎么起」有了两个所有者，
   改一处漏一处，而漏掉的那一处是要交给甲方运维跑的）；
2. ``trial.ps1`` 变成了**第二个灌库器**（同理，而 demo 与 trial 两个库会漂开）；
3. 禁区守卫少了一道（``backend/pe.db`` 不得存在、``backend/data/seed/`` 恒为 0 文件）；
4. ``-Reset`` **硬删**一个正被进程持有的库（得到的是一份半截的库，而下一次起服务时
   alembic 会在离真因很远的地方炸）；
5. ``pe_trial.db`` 的名字在 ``trial.ps1`` 与 ``.gitignore`` 两处漂开
   （于是那份含 60 个人健康档案的库**被提交进 git 历史**，而历史删不掉）。

--------------------------------------------------------------------------
⚠️ 为什么切「代码段」而不是整个文件
--------------------------------------------------------------------------
``<# .DESCRIPTION #>`` 里会**提及**若干它刻意不做的事（三个禁跑 CLI 的名字、
``pe.db`` 的语义、演示口令的唯一所有者在哪一行），扫整个文件会红在自己的说明文字上
（硬规矩 #109）。姿势与 ``tests/test_serve.py`` 的 :func:`_serve_ps1_code` /
``tests/test_backup_restore.py`` 的同名一条逐字相同。
"""
from __future__ import annotations

import pathlib
import re
import subprocess

from app.config import BACKEND_DIR

#: 仓库根。⚠️ 由 :data:`app.config.BACKEND_DIR` 推出来、**不在本文件里敲第二遍路径**
#: （与 ``tests/test_serve.py`` 的 ``REPO_ROOT`` 逐字同一条口径）。
REPO_ROOT = BACKEND_DIR.parent

TRIAL_PS1 = REPO_ROOT / "scripts" / "trial.ps1"
SERVE_PS1 = REPO_ROOT / "scripts" / "serve.ps1"
GITIGNORE = REPO_ROOT / ".gitignore"

#: 试用库的名字。⚠️ **字面量**（硬规矩 #35）：它的一半就是被测对象
#: （``trial.ps1`` 的 ``$TrialDbName`` 与 ``.gitignore`` 的那四行），
#: 从任何一侧读回来跟自己比都是同源断言。
TRIAL_DB_NAME = "pe_trial.db"

#: ``.gitignore`` 里那四行（本体 + SQLite 的三个侧车文件）。
TRIAL_DB_IGNORE_LINES = tuple(
    f"backend/{TRIAL_DB_NAME}{suffix}" for suffix in ("", "-journal", "-wal", "-shm")
)

#: 试用档缺省的端口。⚠️ 字面量，理由同上。
TRIAL_PORT = 8030

#: 本仓**其它**四个有文档的端口：试用档刻意与它们全错开
#: （于是「试用档与产品档同时在跑、两个浏览器窗口对拍」是合法的）。
OTHER_DOCUMENTED_PORTS = (8000, 8010, 8020, 5173)


def _trial_ps1_code() -> str:
    """``trial.ps1`` 的**代码段**（``#>`` 之后那一部分）。理由见模块 docstring 末节。"""
    raw = TRIAL_PS1.read_bytes()
    body = raw[3:].decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    assert body.count("#>") == 1, "trial.ps1 的注释块形状变了，本函数的切法要跟着改"
    return body.split("#>", 1)[1]


def _statements() -> str:
    """代码段里**去掉注释行**之后的那一部分（提及不是本身，硬规矩 #109）。"""
    return "\n".join(
        line for line in _trial_ps1_code().splitlines()
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


# ===========================================================================
# ① 文件形状：UTF-8 + BOM + 纯 CRLF（与本仓另外 4 个 .ps1 同款）
# ===========================================================================


def test_trial_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo():
    """**UTF-8 + BOM + 纯 CRLF**。

    ⚠️ BOM 是承重的、不是洁癖：PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1`` 时按
    系统 ANSI 代码页（本机 GBK）解码，而本文件的注释里全是 UTF-8 中文——
    轻则注释乱码，重则某个字节序列里出现一个引号/反引号把语法弄坏。
    本仓为此付过四次代价（``.gitattributes`` 那一段逐字记着）。
    ⚠️ 三拍与 ``tests/test_serve.py`` 的同名一条逐字同款。
    """
    raw = TRIAL_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "trial.ps1 没有 BOM（PowerShell 5.1 会按 GBK 读它）"
    body = raw[3:]
    crlf = body.count(b"\r\n")
    bare = body.count(b"\n") - crlf
    assert bare == 0, f"trial.ps1 有 {bare} 个裸 LF（本仓的 .ps1 一律 CRLF）"
    assert crlf > 100, f"trial.ps1 只有 {crlf} 行，可能不是一个完整的脚本"
    body.decode("utf-8")

    serve = SERVE_PS1.read_bytes()
    assert serve[:3] == b"\xef\xbb\xbf" and serve[3:].count(b"\n") == serve[3:].count(b"\r\n"), (
        "既有那一款 serve.ps1 的形状变了，本条的「同款」判据要跟着改"
    )


# ===========================================================================
# ② 它**不是**第二个服务器启动器、也**不是**第二个灌库器
# ===========================================================================


def test_trial_ps1_delegates_to_serve_ps1_instead_of_starting_a_second_server():
    """起 uvicorn 那一格**只有 ``serve.ps1`` 一个住址**：本脚本用 ``powershell -File`` 委托它。

    ⚠️ 四拍，每拍各挡一档：

    ① 它**自己一个 uvicorn 都不起**（``uvicorn`` 这个词在代码段里一次都不出现，
       而 ``-m`` 也只可能出现在委托那一行的参数里——实测一次都没有）；
    ② 它**真的**调了 ``serve.ps1``，而且是**另起一个 powershell 进程**
       （``-File $ServePs1``）：⚠️ 用 ``&`` 调用运算符的话，``serve.ps1`` 末尾那句
       ``exit $Code`` 在 5.1 上的语义不如另起一个进程清楚，而 ``$LASTEXITCODE``
       也只在后者上有定义；
    ③ 端口**透传**（``-Port "$Port"``），而 ``-Lan`` **只在给了旗标时才透传**
       （⚠️ 无条件加 ``-Lan`` 等于把试用档默认暴露到局域网上，那是本 Task 不要的一档）；
    ④ 三个环境变量在**委托之前**设（子进程继承的是本进程当时的环境块，设晚了等于没设）。
    """
    code = _trial_ps1_code()
    statements = _statements()

    # ① 它自己不起服务器
    assert "uvicorn" not in statements, "trial.ps1 自己起了一个 uvicorn（那是 serve.ps1 的活）"
    assert "Start-Process" not in statements, (
        "trial.ps1 用 Start-Process 起了子进程：委托 serve.ps1 的姿势是 powershell -File，"
        "而 Start-Process 会把 serve.ps1 的日志与前台阻塞两格一起弄丢"
    )
    assert "-m " not in statements and '"-m"' not in statements, statements[:400]

    # ② 它真的委托了 serve.ps1
    assert "$ServePs1 = Join-Path $PSScriptRoot \"serve.ps1\"" in code, (
        "serve.ps1 的路径不是从 $PSScriptRoot 算出来的（写死一个绝对路径的话，"
        "仓库搬到别处就断了）"
    )
    assert "-File\", $ServePs1" in code or '-File", $ServePs1' in code, code[:800]
    assert "& powershell @ServeArguments" in code, "它没有真的把 serve.ps1 叫起来"
    assert "if (-not (Test-Path $ServePs1))" in code, "委托之前没有先确认那个文件在"

    # ③ 端口透传；-Lan 只在给了旗标时才透传
    assert '"-Port", "$Port"' in code, code[:800]
    assert "if ($Lan) { $ServeArguments += \"-Lan\" }" in code, (
        "-Lan 不是**条件**透传的：无条件加它等于把试用档默认暴露到局域网上"
    )

    # ④ 三个环境变量都设了，且**都在委托之前**
    delegated_at = code.index("& powershell @ServeArguments")
    for assignment in (
        "$env:PE_DB_URL = $TrialDbUrl",
        "$env:PE_CSV_DIR = $CsvDir",
        '$env:PE_TRIAL = "1"',
    ):
        assert assignment in code, f"少了 {assignment!r}"
        assert code.index(assignment) < delegated_at, (
            f"{assignment!r} 排在委托之后：子进程继承的是本进程当时的环境块，设晚了等于没设"
        )


def test_trial_ps1_seeds_through_the_same_entry_point_demo_ps1_uses():
    """灌库走 ``demo.ps1`` 用的**同一个** Python 入口，⚠️ 不写第二个灌库器。

    三拍：

    ① 它调 ``python scripts/demo_bootstrap.py``，且两个必需参数都给
       （``--db-url`` 指到试用库、``--csv-dir`` 指到 ``$env:TEMP`` 下的一个子目录，
       ⚠️ **不是** ``backend/data/seed``）；
    ② ⚠️ 那三个禁跑 CLI 一次都不**被调用**（``app.seed.generate`` /
       ``app.pipeline.backfill`` / ``app.pipeline.daily`` 的 ``main()`` 各自把缺省值
       写死在两个禁区上）；⚠️ 判据是「调用形状」而不是「模块名出现过」，
       逐字理由在下面第 ② 拍的行内注释里；
    ③ ``--students`` 与 ``--seed`` **刻意不传**：缺省值的唯一所有者是
       ``demo_bootstrap.py`` 的 argparse，在这里再敲一遍就是第二个所有者。
    """
    statements = _statements()

    assert "python scripts/demo_bootstrap.py --db-url $TrialDbUrl --csv-dir $CsvDir" in statements, (
        "灌库那一行不是 demo.ps1 用的那个入口（或参数名漂了）"
    )
    assert "-m app." not in statements, "它跑了一个 app 下面的 CLI（那三个的缺省值写死在两个禁区上）"
    # ⚠️ 判据是「**调用**形状」而不是「模块名出现过」：① 那一句 ``throw`` 的报错里
    #    逐字解释了 ``pe.db`` 的语义（「它是 ``app.seed.generate`` 写出来的那份
    #    不可复现的库」），那是**提及**、不是调用（硬规矩 #109）。按裸模块名断的话
    #    本拍会红在自己的说明文字上，而下一个人唯一的出路就是删掉那句解释
    #    （``tests/test_serve.py`` 的同名一条首跑踩过同一格，本处沿用它的切法）。
    assert "python -m " not in statements, statements[:400]
    # ⚠️ 本拍**只打在灌库那一行上**，不打在整段代码上：③ 那一步有一句 Write-Host
    #    逐字**提及**了这两个参数名（「--students / --seed 刻意不传：缺省的唯一所有者是
    #    demo_bootstrap.py 的 argparse」），而提及不是本身（硬规矩 #109）——
    #    按整段断的话本拍会红在自己的说明文字上，而下一个人唯一的出路就是删掉那句说明。
    # ⚠️ 谓词是「这一行**以那个调用开头**」，而不是「这一行含那个文件名」：
    #    实测有 4 行提及 demo_bootstrap.py（两句 Write-Host 的说明 + 一句 throw 的报错
    #    + 调用本身），含文件名那一版会红在自己的说明文字上（同一格理由）。
    seed_lines = [
        line for line in statements.splitlines()
        if line.strip().startswith("python scripts/demo_bootstrap.py")
    ]
    assert len(seed_lines) == 1, seed_lines
    assert "--students" not in seed_lines[0] and "--seed" not in seed_lines[0], (
        "灌库那一行自己敲了一遍 --students / --seed：那两个缺省值的唯一所有者是 "
        "demo_bootstrap.py 的 argparse（60 与 20250828），抄第二份就是第二个所有者"
    )
    assert "$CsvDir = Join-Path $env:TEMP (\"pe_trial_csv_\" + $PID)" in statements, (
        "CSV 目录不在 $env:TEMP 下（backend/data/** 一个字节都不许动，"
        "而 backend/data/seed/ 恒为 0 文件）"
    )
    assert "Set-Location $Backend" in statements, (
        "灌库之前没有切到 backend/：demo_bootstrap.py 要能 import 到 app 包"
    )


# ===========================================================================
# ③ 禁区守卫（姿势逐字抄 demo.ps1 的 ⑤ 与 serve.ps1 的 ③ a）
# ===========================================================================


def test_trial_ps1_guards_the_pe_db_forbidden_zone_twice():
    """两道 ``pe.db`` 守卫 + 一道 ``data/seed/`` 守卫，⚠️ 且灌库**前后各一次**。

    ① 灌库**之前**：``backend/pe.db`` 已经存在就 ``throw``（本脚本不该在一个已经破了
       禁区的仓上继续干活），而试用库的 URL 若以 ``pe.db`` 结尾也 ``throw``
       ——判据与 ``serve.ps1`` 的 ③ a **逐字同一个正则**；
    ② 灌库**之后**：再查一次两个禁区（``demo.ps1`` 的 ⑤ 就是这个形状：
       前置守卫挡的是「输入指错了」，后置复核挡的是「生成器写歪了」）；
    ③ ``data/seed`` 那一次带 ``-Recurse``（Plan 03 全分支终审的 M2：不带的话
       「有人在 ``data/seed/2025/`` 下写了一堆 CSV」这一档会静默通过复核）。
    """
    code = _trial_ps1_code()
    statements = _statements()

    assert r"'(^|/)pe\.db$'" in code, (
        "禁区守卫的那个正则不见了（⚠️ 它必须与 serve.ps1 的 ③ a 逐字同形，"
        "两份各写一套的话改一处漏一处）"
    )
    assert '$ForbiddenDb = Join-Path $Backend "pe.db"' in statements
    assert statements.count("if (Test-Path $ForbiddenDb)") == 2, (
        "禁区那一道只查了一次：灌库**之前**与**之后**各要一次"
        "（前置挡「输入指错了」，后置复核挡「生成器写歪了」）"
    )
    assert "-File -Recurse" in statements, (
        "data/seed 那一次复核没带 -Recurse：不带的话子目录里的文件看不见，"
        "于是「有人在 data/seed/2025/ 下写了一堆 CSV」会静默通过（Plan 03 终审 M2）"
    )
    assert 'Join-Path $Backend "data\\seed"' in statements
    # ⚠️ 前置那一道必须排在灌库之前
    assert code.index("if (Test-Path $ForbiddenDb)") < code.index("demo_bootstrap.py")


# ===========================================================================
# ④ ``-Reset``：先取证、再查占用，⚠️ 然后才删
# ===========================================================================


def test_trial_ps1_reset_prints_what_it_deletes_and_refuses_a_file_someone_holds():
    """``-Reset`` 的三格：**删前取证** → **占用检测** → 才删；占用时退出非 0、⚠️ 不硬删。

    四拍：

    ① 删之前逐个打印**路径 + 字节数 + sha256[:16] + 改动时刻**
       （⚠️ 一份被删掉的试用库是**找不回来**的，故删的那一瞬间之前必须留下
       「删的到底是哪一份」的取证；这也是各波报告里能引用到那些数的原因）；
    ② 占用检测是一次**独占打开**（``FileShare.None``）：SQLite 打开库时给的是
       ``FILE_SHARE_READ|WRITE``，故一个活着的 uvicorn 会让它抛 ``IOException``。
       ⚠️ 而「端口上有没有 listener」**不是**唯一判据（持有这个文件的也可能是
       另一个还没起完的 ``demo_bootstrap.py``、或一个开着库的 DB 浏览器），
       故它只用来把**人话**说得更具体；
       ⚠️⚠️ 而它**必须排在 ① 的 ``Get-FileHash`` 之前**（本波实测踩到的）：
       那一个 cmdlet 要**读**文件，而一个被持有的 SQLite 库读不出来
       （``FileReadError``），而脚本第一行是 ``$ErrorActionPreference = "Stop"``
       ⇒ 它会停在一段 PowerShell 原文报错上，③ 那一句人话永远打不出来；
    ③ 占用 → ``exit 1``，⚠️ 而 ``Remove-Item`` **排在占用检测之后**（顺序是承重的：
       反过来的话「不硬删」那一格就是一句空话）；
    ④ 四个后缀（本体 + ``-journal`` / ``-wal`` / ``-shm``）都在清单里
       ——只删本体的话，一个陈旧的 ``-wal`` 会让下一次打开库时 SQLite 重放一段
       属于上一份库的日志。
    """
    code = _trial_ps1_code()
    statements = _statements()

    # ① 删前取证
    assert "Get-FileHash -Path $File -Algorithm SHA256" in statements, "删之前没有取 sha256"
    assert ".Substring(0, 16)" in statements, "取证不是 sha256[:16] 那一格（与本仓各波报告同口径）"
    assert "$Item.Length" in statements and "$Item.LastWriteTime" in statements

    # ② 占用检测是一次独占打开
    assert "[System.IO.FileShare]::None" in statements, (
        "占用检测不是一次独占打开（FileShare.None）：靠 Test-Path 判不出「有进程持有它」"
    )
    assert "[System.IO.FileMode]::Open" in statements
    # ⚠️ 「谁持有它」按**进程**找（python ∩ 正在监听的 PID），⚠️ 不按 `-Port` 找：
    #    持有者通常是**另一个** trial.ps1 / serve.ps1 起的 uvicorn，它的端口与本次
    #    `-Port` 无关（本波实测：`-Port 8031 -Reset` 撞上了起在缺省 8030 上的那一个，
    #    改前打印的「端口 8031 上没有 listener」是一句真话、而对要处置它的人没用）。
    assert "Get-Process -Name python" in statements
    assert "Get-NetTCPConnection -State Listen" in statements
    # ⚠️ 而它**排在 Get-FileHash 之前**（本波实测：反过来的话脚本会停在一段
    #    PowerShell 原文报错上，「报一句人话」那一格是空的；逐字理由见上面 ② 那一段）
    assert statements.index("[System.IO.FileShare]::None") < statements.index("Get-FileHash -Path $File"), (
        "占用检测排在 Get-FileHash 之后：一个被持有的库读不出来（FileReadError），"
        "而 $ErrorActionPreference='Stop' 会让脚本停在 PowerShell 的原文报错上，"
        "于是那一句人话永远打不出来"
    )

    # ③ 占用 → 退出非 0，且 Remove-Item 排在它之后
    held_at = statements.index("if ($Held.Count -gt 0)")
    exit_at = statements.index("exit 1", held_at)
    remove_at = statements.index("Remove-Item $File -Force")
    assert held_at < exit_at < remove_at, (
        f"顺序不对（占用检测 {held_at} / exit 1 {exit_at} / Remove-Item {remove_at}）："
        "「不硬删」那一格必须是**顺序**上的，否则它是一句空话"
    )

    # ④ 四个后缀
    assert '$Sidecars = @("", "-journal", "-wal", "-shm")' in statements, statements[:400]

    # ⚠️ 反空转：缺省（不给 -Reset）时**一个 Remove-Item 都不落在试用库上**
    assert "if ($Reset) {" in statements
    reset_at = statements.index("if ($Reset) {")
    assert statements.index("Remove-Item $File -Force") > reset_at


# ===========================================================================
# ⑤ 试用库的名字：一个所有者，而 .gitignore 与它不许漂开
# ===========================================================================


def test_the_trial_database_name_has_one_owner_and_gitignore_agrees():
    """``pe_trial.db`` 这个名字：``trial.ps1`` 是所有者，``.gitignore`` 逐字同意它。

    三拍（⚠️ 两侧不同源：一侧是脚本、一侧是 ``.gitignore``、第三侧是 git 自己）：

    ① ``trial.ps1`` 里它**恰好出现一次作为 ``$TrialDbName`` 的赋值**
       （别处一律用那个变量，于是「改名」只改一处）；
    ② ``.gitignore`` 有那**四行**（本体 + ``-journal`` / ``-wal`` / ``-shm``），
       姿势与 ``pe_demo.db`` 那一条逐字相同；
    ③ ⚠️ **git 自己**也认为它被忽略、且它**没有被入库**
       （``check-ignore`` 与 ``ls-files`` 两侧都问一次）。

    ⚠️ 第 ③ 拍是本条的**牙**：一份试用库里是一整份仿真名册与体测数据，
    而 git 历史**删不掉**——一次误提交等于把 60 个人的健康档案永久留在版本控制里
    （与 ``.gitignore`` 里 ``backend/backups/`` 那一段逐字同一条理由）。
    """
    statements = _statements()
    assert f'$TrialDbName = "{TRIAL_DB_NAME}"' in statements, (
        f"trial.ps1 里那个名字不是 ${TRIAL_DB_NAME}"
    )
    # ① 字面量在**代码段**里只出现那一次（别处一律用 $TrialDbName / $TrialDbPath）
    assert statements.count(f'"{TRIAL_DB_NAME}"') == 1, (
        f"{TRIAL_DB_NAME!r} 在代码段里出现了 {statements.count(TRIAL_DB_NAME)} 次："
        "改名要改两处的话，漏掉的那一处会让试用档写进演示库"
    )
    assert "Join-Path $Backend $TrialDbName" in statements

    # ② .gitignore 的四行
    ignored = GITIGNORE.read_bytes().decode("utf-8").splitlines()
    for line in TRIAL_DB_IGNORE_LINES:
        assert line in ignored, (
            f".gitignore 里少了 {line!r}（四行：本体 + SQLite 的三个侧车文件）"
        )

    # ③ git 自己也这么说
    checked = subprocess.run(
        ("git", "check-ignore", "-v", f"backend/{TRIAL_DB_NAME}"),
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert checked.returncode == 0, (
        f"git 不认为 backend/{TRIAL_DB_NAME} 被忽略：{checked.stdout!r} {checked.stderr!r}"
    )
    assert _git("ls-files", "--", f"backend/{TRIAL_DB_NAME}").strip() == "", (
        f"backend/{TRIAL_DB_NAME} **被入库了**：一份试用库是一整份名册与体测数据，"
        "而 git 历史删不掉"
    )
    # ⚠️ 禁区那一格顺手也问一次（它恒为 False，是本仓收工清单的第一格）
    assert not (BACKEND_DIR / "pe.db").exists(), "禁区 backend/pe.db 存在"
    assert _git("ls-files", "--", "backend/pe.db").strip() == ""


def test_python_side_deliberately_has_no_trial_db_url_constant():
    """``app/main.py`` 里**刻意没有** ``TRIAL_DB_URL``：Python 侧一个消费者都没有。

    ⚠️ 这一条钉的是一个**刻意的缺席**（硬规矩 #50 的另一半：一个恒用不到的东西
    与一个真的东西在颜色上无法区分，故「不加」也要有一条守卫，否则下一个人
    「顺手对称一下」加一个没人读的常量是绿的）。
    ⚠️ 对照物是 :data:`app.main.DEMO_DB_URL`：那一个**有** Python 消费者
    （``_resolve_db_url`` 的回落、``demo.ps1`` 与 ``serve.ps1`` 都从它读），
    故它是「演示库叫什么」的唯一所有者；而试用库只有 ``trial.ps1`` 一个消费者。
    """
    main_source = (BACKEND_DIR / "app" / "main.py").read_bytes().decode("utf-8")
    assert "TRIAL_DB_URL" not in main_source, (
        "app/main.py 里出现了 TRIAL_DB_URL：Python 侧一个消费者都没有，"
        "加它就是死配置（试用库的名字的唯一所有者是 scripts/trial.ps1 的 $TrialDbName）"
    )
    assert "pe_trial" not in main_source, main_source[:200]
    # ⚠️ 反空转：对照物**确实**在（否则上面两拍可能只是因为文件被指错了）
    assert "DEMO_DB_URL" in main_source


# ===========================================================================
# ⑥ 参数面：缺省端口、以及它不与另外四个有文档的端口撞
# ===========================================================================


def test_trial_ps1_defaults_to_a_port_that_collides_with_none_of_the_others():
    """缺省端口是 **8030**、参数面是四个，⚠️ 而那个端口与本仓另外四个有文档的端口全错开。

    ⚠️ 错开是**承重**的、不是洁癖：``smoke.mjs`` 的第三档（试用档）要与产品档
    **同时**起着对拍（一个浏览器窗口挂告示、另一个不挂），撞端口就只能串行跑，
    而串行跑的那一档下「告示不泄漏到别的档」这半句无从取证。
    ⚠️ 期望侧是**字面量**（:data:`TRIAL_PORT` 与 :data:`OTHER_DOCUMENTED_PORTS`），
    不从被测脚本读回来跟自己比。
    """
    code = _trial_ps1_code()
    start = code.index("param(")
    block = code[start:code.index(")", start)]
    # ⚠️ **Plan 07 Task 4 把它从三个抬到四个**（``-Build``：不透传 ``-SkipBuild``）。
    #    那一格是「可分发试用包只装 Python 就能起」的**承重要求**（``trial.ps1`` 是
    #    包里那个一条命令的入口，而那台机器上很可能没有 node），逐字理由见
    #    :func:`test_trial_ps1_defaults_to_skip_build_and_only_builds_when_asked`。
    assert sorted(re.findall(r"\$(\w+)", block)) == [
        "Build", "Lan", "Port", "Reset",
    ], block
    assert f"[int]$Port = {TRIAL_PORT}" in block, block
    assert "[switch]$Lan" in block and "[switch]$Reset" in block, block
    assert "[switch]$Build" in block, block
    # ⚠️ 缺省值不与另外四个撞（8000 手工演示 / 8010 demo.ps1 / 8020 serve.ps1 / 5173 vite）
    for port in OTHER_DOCUMENTED_PORTS:
        assert f"[int]$Port = {port}" not in block, (
            f"试用档的缺省端口撞上了 {port}（那一档已经有主了）"
        )
    assert TRIAL_PORT not in OTHER_DOCUMENTED_PORTS


def test_trial_ps1_sets_pe_trial_to_one_and_reads_the_tier_from_nothing_else():
    """``PE_TRIAL`` 在本脚本里**只被设成 ``"1"``**，⚠️ 一个别的值都不出现。

    ⚠️ 两拍：① 赋值那一行逐字是 ``$env:PE_TRIAL = "1"``（``app.deploy.is_trial``
    只认 ``"1"`` 与 ``"0"``，其余一律 ``ValueError`` ⇒ 服务起不来）；
    ② 本脚本**不碰** ``PE_ENV``（试用档刻意留在缺省的 ``dev``：明文 http 上跑 ``prod``
    会让浏览器拒收 ``Secure`` cookie，症状是「登录 200、下一个请求 401」，
    spec §13.11.3）——它只**打印**实测到的那一格。
    """
    statements = _statements()
    assert statements.count('$env:PE_TRIAL = "1"') == 1, statements[:400]
    # ⚠️ 把「赋成了什么」抓出来与字面量比，而**不用**一个带 `\s*` + 负向前瞻的正则：
    #    `\s*` 会回溯到 0 个空白，于是在 `= "1"` 的**那个空格**处就匹配上了
    #    （本波首跑实测红在自己身上）。抓值这一侧没有回溯，且报错里能看到实收的值。
    assigned = re.findall(r"\$env:PE_TRIAL\s*=\s*(\S+)", statements)
    assert assigned == ['"1"'], (
        f"PE_TRIAL 被赋成了 {assigned}（app.deploy.is_trial() 只认 '1' 与 '0'，"
        "其余一律 ValueError ⇒ 服务起不来）"
    )
    assert not re.search(r"\$env:PE_ENV\s*=", statements), (
        "trial.ps1 设了 PE_ENV：档位是**部署事实**、归运维的环境变量，"
        "而试用档刻意留在缺省的 dev 档（明文 http 上 prod 的 Secure cookie 会被浏览器拒收）"
    )
    # ⚠️ 反空转：它确实**打印**了实测到的档位（不是一句写死的「dev」）
    assert "$env:PE_ENV" in statements


# ===========================================================================
# ⑦ 它不成为演示口令的第二个所有者
# ===========================================================================


def test_trial_ps1_does_not_become_a_second_owner_of_the_demo_credentials():
    """演示口令与学号**一个都不许抄**在这里（唯一所有者是 ``demo_bootstrap.py``）。

    ⚠️ 姿势与 ``tests/test_serve.py`` 的
    :func:`test_serve_ps1_does_not_become_a_second_owner_of_the_demo_credentials`
    逐字同款：抄第二份的话，改口令的人会漏改一处，而漏改的那一处是
    **要念给甲方听的**那一处。⚠️ 工号 ``T0001`` / ``T0002`` / ``T0003`` 是允许的
    （``demo.ps1`` 与 ``serve.ps1`` 也逐字印它们）。
    """
    whole = TRIAL_PS1.read_bytes()[3:].decode("utf-8")
    for needle in ("pe-demo-2025", "DEMO_PASSWORD ="):
        assert needle not in whole, f"trial.ps1 里抄了一份 {needle!r}"
    assert re.search(r"\b20\d{8}\b", whole) is None, (
        "trial.ps1 里抄了一个学号形状的字面量：名册由 app/seed/population.py 现造，"
        "而 demo.ps1 曾因为抄了一个从来不在册的学号把演示带进 403（Plan 06 终审 I1）"
    )
# ===========================================================================
# ⑧ Plan 07 Task 4：缺省 ``-SkipBuild``（只装 Python 也能起）+ 给试用者念的三行
# ===========================================================================


def test_trial_ps1_defaults_to_skip_build_and_only_builds_when_asked():
    """**缺省**透传 ``-SkipBuild`` 给 ``serve.ps1``，而 ``-Build`` 是收回它的唯一开关。

    ⚠️ 为什么这一格是承重的（实施计划 07 §4 / 派单 Task 4 §1.4）：可分发试用包的目标
    口径逐字是「甲方 IT 能在**他们自己的**机器上、**只装 Python** 就起一份来试用」。
    ``serve.ps1`` 的 node 检查在同一波搬进了它 ② 的 ``if ($NeedBuild)`` 里面
    （:func:`tests.test_serve.test_node_is_checked_only_when_a_build_is_actually_needed`），
    故「不构建」与「不查 node」是**同一格的两半**：本脚本不透传 ``-SkipBuild`` 的话，
    那台没有 node 的机器就会停在「找不到 node」上 —— 而包里带的本来就是预构建的
    ``frontend/dist``，它压根不需要 node。

    四拍：

    ① 那一行**在场**且是**条件**的（``if (-not $Build)``）：无条件加 ``-SkipBuild``
       就等于把 ``-Build`` 变成一个恒不起作用的旗标（一档看得见的谎）；
    ② ``$Build`` 在**语句**里恰好三行：一行声明（``[switch]$Build``）+ 两行使用
       （那个条件、以及把它打印给运维看的那一句），⚠️ 反空转：少了声明 = 旗标不存在，
       少了那两行 = 旗标是死的（给了它与不给它一模一样）；
    ③ ``-Lan`` 那一行的形状**一个字都没变**（它自己的守卫按字面钉着，两侧不同源）；
    ④ ``-SkipBuild`` **不**写死在 ``$ServeArguments`` 的初始字面量里
       （写在那里的话 ``-Build`` 就收不回它了）。
    """
    code = _trial_ps1_code()
    statements = _statements()

    # ①
    assert 'if (-not $Build) { $ServeArguments += "-SkipBuild" }' in statements, (
        "缺省没有透传 -SkipBuild（或那一行不是条件的）：只装了 Python 的机器于是会停在"
        "「找不到 node」上，而包里带的本来就是预构建的 dist"
    )
    # ②（⚠️ 声明那一行也在**语句**里：它不以 ``#`` 开头，故 :func:`_statements` 不剥它）
    uses = [line for line in statements.splitlines() if "$Build" in line]
    assert len(uses) == 3, uses
    assert sum(1 for line in uses if line.strip() == "[switch]$Build") == 1, uses
    assert any("-not $Build" in line and '"-SkipBuild"' in line for line in uses), uses
    assert any("Write-Host" in line and "if ($Build)" in line for line in uses), (
        "它没有把「本次会不会重建前端」打印给运维看（反静默：那一档在屏幕上"
        "原本与「查过了」长得一模一样）"
    )
    # ③（⚠️ 与 :func:`test_trial_ps1_delegates_to_serve_ps1_instead_of_starting_a_second_server`
    #    的那一拍同形，而两侧各自独立地钉一次：那一拍钉「-Lan 是条件透传的」，
    #    本拍钉「加了 -SkipBuild 之后 -Lan 那一行没被顺手改掉」）
    assert 'if ($Lan) { $ServeArguments += "-Lan" }' in statements
    # ④
    head = statements[
        statements.index("$ServeArguments = @("):statements.index("$ServeArguments = @(") + 300
    ]
    assert "-SkipBuild" not in head.splitlines()[0], head.splitlines()[0]
    assert "[switch]$Build" in code


def test_trial_ps1_prints_the_trial_only_lines_and_never_reprints_the_accounts():
    """给试用者念的**三行**在场，而**链接与三类账号一个都不抄**（那是 ``serve.ps1`` ⑤ 的活）。

    ⚠️ 两半各挡一档失效：

    ① 少了那三行 ⇒ 甲方跑完一条命令，屏幕上只有运维口径的环境变量与端口，
       而「数据是仿真的、请勿录入真实学生信息」这一句**没人念给他听**
       （页面上挂着同一条告示，而告示要在浏览器里才看得见；终端是运维念给甲方听的那一份）；
    ② 抄了链接与账号 ⇒ **第二个所有者**：``serve.ps1`` 的 ⑤ 已经逐行印了 ``$Base/``、
       学生 / ``T0001`` / ``T0002`` / ``T0003`` 与「口令的唯一所有者是
       ``demo_bootstrap.py`` 的 ``DEMO_PASSWORD``」，而本脚本是它的**调用者**、
       两个进程共用同一个控制台 ⇒ 抄一份就会「改一处漏一处」，
       而漏掉的那一处正是要念给甲方听的那一处（与
       :func:`test_trial_ps1_does_not_become_a_second_owner_of_the_demo_credentials`
       逐字同一条理由，那一拍钉口令与学号，本拍钉链接与工号）。
    """
    statements = _statements()

    # ① 三行各在场，⚠️ 而「请勿录入真实学生信息」恰好一次（0 = 被删了；≥2 = needle 有歧义）
    assert statements.count("请勿录入真实学生信息") == 1, statements[:400]
    assert "怎么重置" in statements and "-Reset" in statements
    assert "2026-10-15-甲方试用说明书.md" in statements, (
        "它没有把甲方指向那一份说明书（本文是**时点快照**，逐字口径住在文档里）"
    )
    # ② 链接与三类账号一个都不抄
    for needle in ("$Base/", "T0001", "T0002", "T0003"):
        assert needle not in statements, (
            f"trial.ps1 里抄了一份 {needle!r}：那一格的唯一所有者是 serve.ps1 的 ⑤"
        )


#: 甲方试用说明书。⚠️ 它是 ``trial.ps1`` ⑤ b ③ 指向的那一份，也是 ⑤ b ③ 那个
#: 「八节：…」目录的**期望侧**（两侧不同源：期望侧现场解析文档的 ``##`` 标题）。
GUIDE_MD = REPO_ROOT / "Document" / "2026-10-15-甲方试用说明书.md"


def _guide_section_titles() -> list[str]:
    """说明书里那八个 ``## N. 标题`` 的**标题本体**（去掉括号补充与 ``**``）。"""
    text = GUIDE_MD.read_bytes().decode("utf-8")
    titles: list[str] = []
    for line in text.splitlines():
        hit = re.match(r"^##\s+(\d+)\.\s+(.+?)\s*$", line)
        if hit:
            titles.append(re.split(r"（", hit.group(2).replace("**", ""), 1)[0].strip())
    return titles


def test_trial_ps1_prints_a_table_of_contents_that_matches_the_guide():
    """⑤ b ③ 那一行「八节：…」与说明书里**真的**那八个 ``##`` 标题逐个对账（终审 S4-2）。

    病灶：改前那一行写「八节」而只列了 **7** 项（漏了 §1「这是什么」），且把 §5 的
    标题写成「16 条路由」—— 而 §5 的标题逐字是「其余几条路由」（它自己说完整清单在
    spec §13.6）。⚠️ 那一行是**打印给甲方看的目录**，故它必须是真话。

    三拍：

    ① 件数相符（「八节」= 说明书里 8 个 ``##``，一行不多一行不少）；
    ② 逐个标题**按顺序**逐字相同（期望侧现算文档，⚠️ 不抄脚本里那一行）；
    ③ 反空转：改前那一行（7 项 + 「16 条路由」）必须**对不上**①②。
    """
    statements = _statements()
    toc_lines = [line for line in statements.splitlines() if "（八节：" in line]
    assert len(toc_lines) == 1, toc_lines
    listed = [item.strip() for item in
              toc_lines[0].split("（八节：", 1)[1].split("）", 1)[0].split(" / ")]

    titles = _guide_section_titles()
    # ③ 反空转：期望侧**真的有** 8 个标题（否则①②会因为两侧都空而假绿）
    assert len(titles) == 8, titles
    # ①
    assert len(listed) == len(titles), (
        f"那一行列了 {len(listed)} 项，而说明书有 {len(titles)} 个 ## 标题（改前是 7 vs 8）"
    )
    # ②
    assert listed == titles, (listed, titles)
    # ③ 改前那一行必须对不上
    stale = ["三条打开方式", "账号", "四条试用路线", "16 条路由",
             "须知", "怎么重置", "出问题怎么自查"]
    assert listed != stale and "16 条路由" not in listed, listed


def test_trial_ps1_counts_the_students_from_the_database_instead_of_hardcoding_sixty():
    """⑤ b ① 那一行的 N **从库里数**，⚠️ 不写死 60（终审 S4-3）。

    病灶：那一个数的所有者是 ``demo_bootstrap.py`` 的 ``--students`` argparse 缺省
    （本脚本第 ③ 步逐字写着「--students / --seed 刻意**不传**」），而 ⑤ b ① 改前
    逐字印着「库里 60 名学生」⇒ 同一件事两个所有者，而漏改的那一处正是**要念给
    甲方听**的那一处（``App.vue`` 的告示读 ``/api/health`` 的 ``students``，
    它的注释逐字交代了为什么不写死）。

    ⚠️ 为什么走库、不走 ``/api/health``：那一段打印排在 ``serve.ps1`` 起来**之前**，
    端口上还没有任何东西在听。

    四拍：

    ① 语句里**没有**「库里 60 名学生」那个字面量（改前的形状）；
    ② 有一句 ``select count(*) from student`` 真的打在 ``$TrialDbPath`` 上；
    ③ 数不出来时**不印数字**、并印一句「没能从库里数出来」（一句假话比一句
       「这一格我没数出来」坏得多）；
    ④ 反空转：``请勿录入真实学生信息`` 仍然恰好一次 ⇒ ②③ 不是靠把整段删掉换来的绿。
    """
    statements = _statements()
    lines = statements.splitlines()

    # ①
    assert "库里 60 名学生" not in statements, "⑤ b ① 又写死了 60（S4-3 的病灶）"
    assert not re.search(r"库里\s*60\s*名学生", statements), statements[:400]
    # ②
    hits = [line for line in lines if "select count(*) from student" in line]
    assert len(hits) == 1, hits
    assert "$TrialDbPath" in hits[0], hits[0]
    assert "python -c" in hits[0] and "sqlite3" in hits[0], (
        "那一句不是**真的**去读库（`python -c` + `sqlite3`）：形状漂了"
    )
    # ③
    assert "没能从库里数出来" in statements, (
        "数不出来那一档不再说人话了：它必须**不印数字**并把原因印出来"
    )
    assert "$null -ne $StudentCount" in statements, "那两档（数出来了 / 没数出来）不再分开走"
    # ④
    assert statements.count("请勿录入真实学生信息") == 1, statements[:400]
