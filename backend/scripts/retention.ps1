<#
.SYNOPSIS
    一条命令清掉四张表的过期行（Plan 08 Task 2）：``login_attempt`` / ``user_session``
    （**只清已过期的**）/ ``audit_log`` / ``read_audit_log``。

.DESCRIPTION
    ⚠️ **本文件是一个薄包装**：全部逻辑住在 ``scripts/retention.py``（可测试、可守卫），
    本文件只做三件事 —— ① 把工作目录切到 ``backend/``（``app.config.BACKEND_DIR``
    是绝对路径、不依赖 CWD，而 ``python scripts/retention.py`` 要能 import 到 ``app`` 包）；
    ② 把参数原样交过去；③ 把 Python 的退出码原样交回来。
    ⚠️ 于是「清哪四张表、按哪一列、缺省留几天」这件事**只有一个所有者**：
    改口径请改 ``retention.py``，不要在这里再实现一遍（``backend/scripts/backup.ps1``
    对 ``backup.py`` 是同一条纪律）。⚠️ 本文件里因此**一个天数字面量都没有**。

    ⚠️⚠️ 它是**破坏性**的：删掉的行**不可撤销**，而删掉的是含个人健康数据的审计痕迹。
    故 ``retention.py`` 的形状是「**先逐表预告将删多少行 → 再删 → 删完对账**」，
    实删与预告不符就**整批回滚**（一行都不删）+ 退出码 **2**。
    ⚠️ **第一次跑请先加 ``-DryRun``**：那一档一条 ``DELETE`` 都不会构造、
    连写锁都不取，故可以在甲方服务正跑着的时候安全地看一遍。

    ⚠️ 它**不会**自动备份（裁定与三条理由逐字见 ``retention.py`` 模块 docstring
    的「它**不**自动备份」那一节，口径正文在 spec §13.24）。要留后路请**先**跑一次
    ``backend\scripts\backup.ps1``；``backend\scripts\register_retention_task.ps1`` 打印的
    那一对计划任务命令就是这个顺序（备份排在清理前面 30 分钟）。

.PARAMETER DbUrl
    要清理的库 URL（``sqlite:///…``）。缺省读 ``PE_DB_URL``，再缺省是
    ``app.main.DEMO_DB_URL``（= ``backend/pe_demo.db``，与 ``backup.ps1`` 一致）。
    ⚠️ **刻意不回落到 ``app.config.DEFAULT_DB_URL``**：那一个逐字指向禁区
    ``backend/pe.db``（它不得存在）。⚠️ 而 ``retention.py`` 里还有一道**禁区守卫**
    （复用 ``backup.py`` 的 ``_ensure_not_forbidden``，**不是**第二份）：
    显式把 ``pe.db`` 或 ``backend/data/**`` 下的任何东西交给它，一律当场退出码 2。

.PARAMETER DryRun
    **一行都不删**：只打印四张表各自「将删多少行」，并复核总行数没变。

.PARAMETER SessionDays
    ``user_session`` 的保留窗口（天）。⚠️ 类型是 ``string`` 而不是 ``int``：
    本包装**只在非空时才往下传**（与 ``-DbUrl`` 同一条姿势），于是「没给」与
    「给了一个值」在 argparse 那侧可分辨，缺省值因此**只有 ``retention.py`` 一个所有者**。
    ⚠️ 判据锚在 ``expires_at`` 上，故一个还在有效期里的会话对**任何**窗口都删不到。

.PARAMETER LoginAttemptDays
    ``login_attempt`` 的保留窗口（天）。⚠️ 它对限流本身**没有影响**：
    判「锁」只看 ``max(window, lock)`` 之内（登录 15 分钟、绑定 60 分钟，spec §13.4.6）。

.PARAMETER AuditDays
    ``audit_log``（**写**审计）的保留窗口（天）。⚠️ 它有一个**下界**
    （spec §13.9.1 逐字「写审计**不少于 1 年**」；那个数的唯一所有者是
    ``retention.py`` 的 ``AUDIT_MIN_DAYS``），低于它会被拒（退出码 2 + 一句人话）。

.PARAMETER ReadAuditDays
    ``read_audit_log``（**敏感读**审计）的保留窗口（天）。⚠️ 它**刻意短于**写审计
    （spec §13.9.1 逐字点名了那一个数），理由见 ``retention.py`` 的
    ``DEFAULT_READ_AUDIT_DAYS`` 注释。⚠️ 四个缺省值一律**不在本文件里复述**：
    跑一次 ``-DryRun``，它会把四张表各自的窗口与截止时刻逐行打印出来。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\retention.ps1 -DryRun
    # 先看一遍：四张表各自「将删多少行」，⚠️ 一行都不删

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\retention.ps1
    # 真删（⚠️ 不可撤销）。缺省库是 PE_DB_URL（再缺省 backend\pe_demo.db）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\retention.ps1 -DbUrl "sqlite:///C:/pe/pe_trial.db" -ReadAuditDays 30
    # 指定库 + 把读审计的窗口收短（⚠️ 写审计那一格有一个下界，低于它会被拒）
#>
[CmdletBinding()]
param(
    [string]$DbUrl = "",
    [switch]$DryRun,
    [string]$SessionDays = "",
    [string]$LoginAttemptDays = "",
    [string]$AuditDays = "",
    [string]$ReadAuditDays = ""
)

$ErrorActionPreference = "Stop"

# ⚠️ 一律以 backend/ 为工作目录（与 backup.ps1 / demo.ps1 同一条理由，逐字见它们的注释）。
$Backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Backend

# ⚠️ 参数**只在非空时才往下传**：给一个空串会让 argparse 认为「显式传了一个空值」，
#    而 retention.py 的缺省解析（--db-url > PE_DB_URL > DEMO_DB_URL、四个窗口 >
#    四个 PE_RETENTION_*_DAYS > 四个 DEFAULT_*_DAYS）就永远走不到了。
$Arguments = @("scripts/retention.py")
if (-not [string]::IsNullOrEmpty($DbUrl)) { $Arguments += @("--db-url", $DbUrl) }
if ($DryRun) { $Arguments += "--dry-run" }
if (-not [string]::IsNullOrEmpty($SessionDays)) { $Arguments += @("--session-days", $SessionDays) }
if (-not [string]::IsNullOrEmpty($LoginAttemptDays)) { $Arguments += @("--login-attempt-days", $LoginAttemptDays) }
if (-not [string]::IsNullOrEmpty($AuditDays)) { $Arguments += @("--audit-days", $AuditDays) }
if (-not [string]::IsNullOrEmpty($ReadAuditDays)) { $Arguments += @("--read-audit-days", $ReadAuditDays) }

python @Arguments
$Code = $LASTEXITCODE
if ($Code -ne 0) {
    Write-Host ""
    Write-Host "   清理**没有**执行（退出码 $Code）：上面那句 stderr 就是原因。"
    Write-Host "   最常见的三档是「库路径写错了」「窗口低于下界（写审计那一格的下界是"
    Write-Host "   retention.py 的 AUDIT_MIN_DAYS，来历是 spec §13.9.1「不少于 1 年」）」、"
    Write-Host "   以及「实删与预告不符 ⇒ 四张表已全部回滚，一行都没删」。"
}
exit $Code
