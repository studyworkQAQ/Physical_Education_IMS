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

        pe-<UTC 时间戳>.db            一份库（⚠️ 明文还是加密由**产物头**决定，见下）
        pe-<UTC 时间戳>.db.sha256     侧车：sha256=<64 个十六进制> + bytes=<字节数>

    ⚠️⚠️ **可选加密（Plan 08 Task 3）**：环境变量 ``PE_BACKUP_KEY`` 在，产物就是一份
    **自描述**的加密档（魔数 ``PEBACKUP`` + 版本 + KDF 参数 + 每份自己的盐与 IV +
    AES-256-CBC 的密文 + 尾部 32 字节的 HMAC-SHA256，encrypt-then-MAC）；不在，
    产物就是**改前那一份明文** SQLite，⚠️ 而脚本会打印一段响亮的 ⚠️ 说明
    「这一份是明文的，含全校学生的出生日期与体成分」——**不是** raise
    （改前的缺省行为就是不加密，raise 会把既有用户打死）。
    ⚠️ **文件名与侧车两档都一样**，故 ``restore.ps1`` 两种都吃（它按产物头认，
    ⚠️ 不按扩展名 —— 改前那些明文备份已经在甲方手上了）。
    ⚠️ 侧车算的是**产物文件本身**（加密档就是「头 + 密文 + MAC」那一份），
    理由与逐字口径见 ``backup.py`` 模块 docstring 的「可选加密」那一节。

    ⚠️⚠️ **本文件刻意没有一个 ``-Key`` 参数**：口令走**环境变量**，
    因为 Windows 上任何同机进程都能用 ``Get-CimInstance Win32_Process``
    读到别人**完整的命令行**（一个 ``-Key`` 会让口令明文出现在进程表里、
    也会被任何一份进程审计日志收走）。⚠️ 同理它也**从不打印**那个口令的任何一部分
    （长度、sha、base64 都不印），报错里只说「口令不对 / 缺口令」。
    ⚠️ 而**口令丢了那一份就打不开**（本仓刻意不做密钥托管）：请把它记在
    与备份**分开**的地方。

    ⚠️ 侧车**不是** coreutils 的 ``sha256sum`` 格式（一行装不下「字节数」那一格，
    而半兼容比明显是自己的格式更坏），故 ``sha256sum -c`` 用不了它；
    校验请走 ``restore.py``（它两格都验），或手工::

        Get-FileHash -Algorithm SHA256 backend\backups\pe-….db

    ⚠️⚠️ **它缺省不删旧备份**（Plan 08 Task 3 之前是「从不删」，之后是「你不说就不删」）：
    要它只留最近 N 份请给 ``-Keep N``。判据、失效方向（先逐个打印要删哪几份与它们的
    字节数/sha256 → 再删 → 删完复核）、``-Keep 0`` 为什么被拒、以及
    「``.sha256`` 侧车跟着一起删」这四格的**唯一所有者**是 ``backup.py``
    （``BACKUP_NAME_RE`` / ``MIN_KEEP`` / ``prune_backups``）；⚠️ 本文件**一个数字都不复述**。

.PARAMETER DbUrl
    要备份的库 URL（``sqlite:///…``）。缺省读 ``PE_DB_URL``，再缺省是
    ``app.main.DEMO_DB_URL``（= ``backend/pe_demo.db``，与 ``demo.ps1`` 一致）。
    ⚠️ **刻意不回落到 ``app.config.DEFAULT_DB_URL``**：那一个逐字指向禁区
    ``backend/pe.db``（它不得存在）。⚠️ 而 ``backup.py`` 里还有一道**禁区守卫**：
    显式把 ``pe.db`` 或 ``backend/data/**`` 下的任何东西交给它，一律当场退出。

.PARAMETER Dir
    备份落在哪个目录。缺省 ``backend/backups/``。

.PARAMETER Keep
    只留最近 N 份，其余的连 ``.sha256`` 侧车一起删。⚠️ **缺省不给 = 一份都不删**
    （与 Task 3 之前的行为逐字相同）。⚠️ 类型是 ``string`` 而不是 ``int``：
    本包装**只在非空时才往下传**（与 ``-DbUrl`` / ``-Dir`` 同一条姿势，也与
    ``retention.ps1`` 那四个天数参数逐字同款），于是「没给」与「给了一个值」
    在 argparse 那侧可分辨，缺省值与下界因此**只有 ``backup.py`` 一个所有者**。
    ⚠️ 删备份**不可逆**，故 ``backup.py`` 会先把要删的那几份逐个打印出来
    （文件名 / 字节数 / sha256 的前 16 位 / 侧车在不在），删完再复核一遍。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1
    # 备份 PE_DB_URL（或演示库），打印备份路径 / 字节数 / sha256 的前 16 位

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Dir D:\pe-backups
    # 落到别的盘（生产上通常是一个加密卷或一块单独的备份盘）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Keep 14
    # 备份完只留最近 14 份（⚠️ 会先逐个打印要删哪几份、删完再复核；不可逆）

.EXAMPLE
    $env:PE_BACKUP_KEY = "<一个只有运维知道的口令>"
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Keep 14
    # 加密档 + 只留最近 14 份。⚠️ 恢复时同一个环境变量也要在

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Keep 0
    # ⚠️ **拒绝**并退出码 2：0 的字面意思是「一份都不留」（连刚做出来的那一份也删），
    #    而那几乎肯定不是运维想要的 ⇒ 那一档连这一次备份都不做
#>
[CmdletBinding()]
param(
    [string]$DbUrl = "",
    [string]$Dir = "",
    [string]$Keep = ""
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
if (-not [string]::IsNullOrEmpty($Keep)) { $Arguments += @("--keep", $Keep) }

python @Arguments
$Code = $LASTEXITCODE
if ($Code -ne 0) {
    Write-Host ""
    Write-Host "   备份**没有**成功（退出码 $Code）。上面那句 stderr 就是原因；"
    Write-Host "   最常见的三档是「库路径写错了」、「禁区」（backend/pe.db 不得存在）、"
    Write-Host "   以及「-Keep 低于下界」（⚠️ 那一档下这一次备份也**没有做**，"
    Write-Host "   备份目录里一个文件都没动；那个数的唯一所有者是 backup.py 的 MIN_KEEP）。"
}
exit $Code
