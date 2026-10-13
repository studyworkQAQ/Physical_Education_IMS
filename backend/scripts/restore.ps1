<#
.SYNOPSIS
    一条命令从一份备份恢复本系统的 SQLite 库（Plan 06 Task 6）。

.DESCRIPTION
    ⚠️ **本文件是一个薄包装**：全部逻辑住在 ``scripts/restore.py``（可测试、可守卫），
    本文件只做三件事 —— ① 把工作目录切到 ``backend/``；② 把参数原样交过去；
    ③ 把 Python 的退出码原样交回来。⚠️ 「恢复怎么做」这件事**只有一个所有者**。

    四步的顺序是**承重的**（逐字理由见 ``restore.py`` 的模块 docstring 第一节）：

    1. **校验侧车** —— sha256 与字节数**两格都要吻合**；不吻合就**拒绝**（退出码 2）。
       ⚠️ 派单 §2 第 3 条逐字要求的那一档：一份被改过 1 个字节的备份在 sha 上就完全不同，
       而它**看起来**是好的（能被 sqlite3 打开一半），故一律拒绝。
    2. **探写锁** —— 目标库正被别的进程占着（SQLite 的写锁）时报一句**可读的**人话
       （「请先停服务」），不是 ``sqlite3.OperationalError`` 的裸栈。
       ⚠️ 而它是**尽力**的：SQLite 的锁是事务级的，一个开着连接却空闲的 uvicorn 不持锁，
       故「没报错」**不等于**「服务停了」——请自己先停。
    3. **自动留后路** —— 覆盖**之前**先给当前库做一份 ``…-pre-restore.db`` 备份。
       ⚠️ 它挡的不是「备份坏了」（第 1 步已经挡了），而是**「人选错了备份」**：
       一份 sha 完全吻合、而内容是三个月前的备份，恢复上去就把这三个月删了，
       而那一档**没有任何校验能挡住**。
    4. **覆盖 + 自检** —— 用 ``backup()`` 反向拷（不是 ``copyfile``：目标上可能还挂着
       ``-journal`` / ``-wal``，文件级覆盖会让主库与它的 journal 对不上），
       然后打印表数、``alembic_version`` 与 ``student`` 行数。

    ⚠️ **恢复前请先停服务**（Ctrl-C 那个 uvicorn）。⚠️ 而**恢复之后不要跑
    ``demo.ps1``**：它的第一步就是删掉演示库重灌，那会把刚恢复的这份当场抹掉。
    要起服务请手工跑（``demo.ps1`` 的模块注释里有那三行）。

.PARAMETER Backup
    备份文件名或路径。⚠️ 只给一个**文件名**时按 ``-Dir``（缺省 ``backend/backups/``）去拼，
    于是可以直接把 ``backup.ps1`` 打印的那一行原样粘过来。

.PARAMETER Dir
    只给文件名时去哪个目录找它。

.PARAMETER DbUrl
    恢复成哪个库。缺省与 ``backup.ps1`` 逐字同源（``PE_DB_URL`` > ``DEMO_DB_URL``）。
    ⚠️ 禁区守卫同样在（``backend/pe.db`` 与 ``backend/data/**`` 一律拒绝）。

.PARAMETER NoVerify
    跳过侧车校验。⚠️ **侧车丢了才用**：它把「这一份没有被动过」这个断言从脚本
    转移到了人身上。⚠️ 它**只**跳过第 1 步，第 2/3/4 步一律照跑。

.PARAMETER NoAutoBackup
    覆盖前不给当前库留后路。⚠️ 恢复因此变成**不可逆**的动作。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 pe-20261013T030405Z.db
    # 从 backend\backups\ 里那一份恢复；会先校验、再自动备份当前库、然后覆盖

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 D:\offsite\pe-….db -Dir D:\offsite
    # 从别的盘上那一份恢复
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Backup,
    [string]$Dir = "",
    [string]$DbUrl = "",
    [switch]$NoVerify,
    [switch]$NoAutoBackup
)

$ErrorActionPreference = "Stop"

$Backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Backend

# ⚠️ 参数**只在非空时才往下传**（与 backup.ps1 同一条理由）。
$Arguments = @("scripts/restore.py", $Backup)
if (-not [string]::IsNullOrEmpty($Dir)) { $Arguments += @("--dir", $Dir) }
if (-not [string]::IsNullOrEmpty($DbUrl)) { $Arguments += @("--db-url", $DbUrl) }
if ($NoVerify) { $Arguments += "--no-verify" }
if ($NoAutoBackup) { $Arguments += "--no-auto-backup" }

Write-Host "== 厦大体育数智系统 · 恢复 =="
Write-Host "   ⚠️⚠️ 请先停服务（Ctrl-C 那个 uvicorn）；恢复会**覆盖**目标库。"
Write-Host "   ⚠️ 恢复之后**不要**跑 demo.ps1（它第一步就删掉演示库重灌）。"
Write-Host ""

python @Arguments
$Code = $LASTEXITCODE
if ($Code -ne 0) {
    Write-Host ""
    Write-Host "   恢复**没有**执行（退出码 $Code）。⚠️ 目标库因此**没有被改动**："
    Write-Host "   校验、探锁与自动备份都排在覆盖之前，任何一步失败都发生在动手之前。"
}
exit $Code
