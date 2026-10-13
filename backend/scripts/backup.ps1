<#
.SYNOPSIS
    一条命令在线备份本系统的 SQLite 库（Plan 06 Task 6）。

.DESCRIPTION
    ⚠️ **本文件是一个薄包装**：全部逻辑住在 ``scripts/backup.py``（可测试、可守卫），
    本文件只做三件事 —— ① 把工作目录切到 ``backend/``（``app.config.BACKEND_DIR``
    是绝对路径、不依赖 CWD，而 ``python scripts/backup.py`` 要能 import 到 ``app`` 包）；
    ② 把参数原样交过去；③ 把 Python 的退出码原样交回来。
    ⚠️ 于是「备份怎么做」这件事**只有一个所有者**：改口径请改 ``backup.py``，
    不要在这里再实现一遍（``backend/scripts/demo.ps1`` 对 ``demo_bootstrap.py``
    是同一条纪律）。

    它做的是 SQLite 的**在线**备份（``sqlite3`` 的 ``backup()`` API），
    **不是复制文件**：复制在写进行中会坏（一次写事务的新页此刻还在 ``-journal``
    或 ``-wal`` 里，主库文件**不是一个自洽的库**）。故本命令**可以在服务跑着的时候做**
    ——那是「每天夜里 cron 一次」能成立的前提。逐字理由见 ``backup.py`` 的模块 docstring。

    产物是**两个**文件（缺省落在 ``backend/backups/``，已进 ``.gitignore``）::

        pe-<UTC 时间戳>.db            一份可以直接用任何 SQLite 客户端打开的库
        pe-<UTC 时间戳>.db.sha256     侧车：sha256=<64 个十六进制> + bytes=<字节数>

    ⚠️ 侧车**不是** coreutils 的 ``sha256sum`` 格式（一行装不下「字节数」那一格，
    而半兼容比明显是自己的格式更坏），故 ``sha256sum -c`` 用不了它；
    校验请走 ``restore.py``（它两格都验），或手工::

        Get-FileHash -Algorithm SHA256 backend\backups\pe-….db

.PARAMETER DbUrl
    要备份的库 URL（``sqlite:///…``）。缺省读 ``PE_DB_URL``，再缺省是
    ``app.main.DEMO_DB_URL``（= ``backend/pe_demo.db``，与 ``demo.ps1`` 一致）。
    ⚠️ **刻意不回落到 ``app.config.DEFAULT_DB_URL``**：那一个逐字指向禁区
    ``backend/pe.db``（它不得存在）。⚠️ 而 ``backup.py`` 里还有一道**禁区守卫**：
    显式把 ``pe.db`` 或 ``backend/data/**`` 下的任何东西交给它，一律当场退出。

.PARAMETER Dir
    备份落在哪个目录。缺省 ``backend/backups/``。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1
    # 备份 PE_DB_URL（或演示库），打印备份路径 / 字节数 / sha256 的前 16 位

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Dir D:\pe-backups
    # 落到别的盘（生产上通常是一个加密卷或一块单独的备份盘）
#>
[CmdletBinding()]
param(
    [string]$DbUrl = "",
    [string]$Dir = ""
)

$ErrorActionPreference = "Stop"

# ⚠️ 一律以 backend/ 为工作目录（与 demo.ps1 同一条理由，逐字见它的注释）。
$Backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Backend

# ⚠️ 参数**只在非空时才往下传**：给一个空串会让 argparse 认为「显式传了一个空值」，
#    而 backup.py 的缺省解析（PE_DB_URL > DEMO_DB_URL）就永远走不到了。
$Arguments = @("scripts/backup.py")
if (-not [string]::IsNullOrEmpty($DbUrl)) { $Arguments += @("--db-url", $DbUrl) }
if (-not [string]::IsNullOrEmpty($Dir)) { $Arguments += @("--dir", $Dir) }

python @Arguments
$Code = $LASTEXITCODE
if ($Code -ne 0) {
    Write-Host ""
    Write-Host "   备份**没有**成功（退出码 $Code）。上面那句 stderr 就是原因；"
    Write-Host "   最常见的一档是「库路径写错了」与「禁区」（backend/pe.db 不得存在）。"
}
exit $Code
