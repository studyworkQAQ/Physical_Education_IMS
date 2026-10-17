<#
.SYNOPSIS
    打印「每天夜里自动跑一次留存清理」那一条 Windows **计划任务**的注册命令
    —— ⚠️ **本脚本自己不注册**（Plan 08 Task 2）。

.DESCRIPTION
    Windows 上没有 cron，故「周期性地跑一次 ``backend\scripts\retention.ps1``」
    只能靠**计划任务**（Task Scheduler / ``schtasks``）。

    ⚠️⚠️ **本脚本只打印命令、不执行它**，与 ``scripts\serve.ps1 -Lan`` 打印那一对
    ``netsh advfirewall`` 命令**同一条口径**：注册一个计划任务要管理员权限、
    会在这台机器上留下一个**系统对象**（而它会在此后每天夜里删掉一批行），
    故**静默改甲方的机器不是交付物该有的形状**。⚠️ 本脚本因此**不自动注册**：
    它把要跑的那一条命令**原文**打印出来，由运维自己粘到一个**管理员**命令行里跑，
    并配一条对应的**注销**命令（试用结束之后删得掉）。

    ⚠️ **它为什么住在 ``backend\scripts\`` 下、而不是仓库根的 ``scripts\``**：
    那一层的既有四个（``serve`` / ``trial`` / ``tunnel`` / ``package``）各自都
    **同时碰 ``backend\`` 与 ``frontend\``**（或 ``.trial\`` / ``tools\``），
    故不属于任何一包；而本脚本只碰 ``backend\scripts\`` 下的两个包装
    （``retention.ps1`` 与 ``backup.ps1``）与这台机器的计划任务，
    于是它与那两个包装**同住一层**（守卫是 ``tests/test_serve.py`` 的
    ``test_serve_ps1_lives_at_the_repo_root_and_not_under_backend_scripts``，
    它按字面钉住仓库根那一层的清单）。

    它打印的四条（一律是**原文**，路径与库 URL 都是现场算出来的绝对值、一个都不写死）：

      ① ``schtasks /Create …``  —— 每天 ``-At`` 那一刻跑一次留存清理；
      ② ``schtasks /Run …``     —— 立刻手工触发一次（注册完**当场验**它真的跑得起来）；
      ③ ``schtasks /Query …``   —— 看它上一次跑的结果码（``Last Result`` 应当是 0）；
      ④ ``schtasks /Delete …``  —— 注销（与 ① 一对，照 ``serve.ps1 -Lan`` 打印
                                   ``netsh … add rule`` / ``netsh … delete rule`` 那一对的姿势）。

    ⚠️ 另打印一条**建议**：把 ``backend\scripts\backup.ps1`` 也注册成一个计划任务、
    排在清理**前面 30 分钟**。理由是清理**不会**自动备份（裁定与三条理由逐字见
    ``backend\scripts\retention.py`` 模块 docstring 的「它**不**自动备份」那一节：
    今天的备份是**明文**整库副本、而 ``backup.ps1`` 从不删旧的 ⇒ 自动备份等于每天
    多留一份含全校学生健康数据的明文副本）。⚠️ 而它是**两个任务**而不是
    「一个任务里串两条命令」：``schtasks /TR`` 里再嵌一层 ``cmd /c a && b``
    就是第三套引号规则（spec §15 G4 已经登记过两套），本脚本不添第三套。

    ⚠️ **``/TR`` 里那些 ``\"``**：那是 ``schtasks`` 自己在 ``/TR`` 一个参数里嵌引号的
    写法（**不是** PowerShell 的转义）。路径里有空格时它们是承重的
    （spec §13.21 抓到过「含空格路径起不来」那一族），故本脚本一律打印带它们的形状。

    ⚠️ **缺省这一条只在「当前用户登录着」的时候跑**：``schtasks /Create`` 不带
    ``/RU`` 时建出来的任务跑在交互式会话里。要它**无人值守**地跑，得加
    ``/RU <用户> /RP <口令>``（或 ``/RU SYSTEM``，而那一档下 ``PE_DB_URL`` 与
    用户级环境变量都读不到，故必须显式传 ``-DbUrl``）。⚠️ 那是一次**口令策略**判断
    （口令要不要落进任务定义里、用不用 gMSA），本脚本**不替运维做**，
    只把这一格如实打印出来。

.PARAMETER DbUrl
    **必填**：要清理的库 URL（``sqlite:///…``）。⚠️ 刻意**没有**缺省值 ——
    一个计划任务每天夜里跑，而「它清的是哪个库」这件事猜错的代价是
    「演示库天天被清、甲方那一份天天不清」（两格都**静默**）。
    去哪儿拿这个值：① ``$env:PE_DB_URL``；② 跑一次
    ``backend\scripts\retention.ps1 -DryRun``，把它打印的「库」那一行抄过来
    （⚠️ 那一行是**路径**，前面补上 ``sqlite:///`` 并把反斜杠换成正斜杠）。

.PARAMETER At
    每天什么时候跑（24 小时制 ``HH:mm``）。缺省 **03:30** —— 夜里、且与那条建议的
    备份任务（``-BackupAt``，缺省 **03:00**）差 30 分钟。

.PARAMETER TaskName
    计划任务的名字。缺省 ``XMU-PE-IMS-Retention``，与 ``serve.ps1 -Lan`` 打印的
    防火墙规则名（``XMU-PE-IMS-TCP-<端口>``）同一个前缀，于是「这一套系统在这台机器上
    留下过哪些系统对象」一次 ``schtasks /Query`` 就问得出来。

.PARAMETER BackupAt
    建议的那条**备份**任务每天什么时候跑。缺省 **03:00**（= ``-At`` 之前 30 分钟）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\register_retention_task.ps1 -DbUrl "sqlite:///C:/pe/backend/pe_trial.db"
    # 打印四条命令原文 + 那条建议的备份任务；⚠️ 一条都不执行

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\register_retention_task.ps1 -DbUrl "sqlite:///C:/pe/backend/pe_trial.db" -At 02:00 -TaskName XMU-PE-Retention
    # 换时刻与任务名（⚠️ 注销那一条会跟着换，故这一对恒成对）
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DbUrl,
    [string]$At = "03:30",
    [string]$TaskName = "XMU-PE-IMS-Retention",
    [string]$BackupAt = "03:00"
)

$ErrorActionPreference = "Stop"

# ⚠️ 两个包装与本文件**同住一层**（理由见 .DESCRIPTION 那一段），故一律用
#    $PSScriptRoot 拼绝对路径：计划任务里的 /TR 需要绝对路径（它的工作目录不由我们定）。
$RetentionPs1 = Join-Path $PSScriptRoot "retention.ps1"
$BackupPs1 = Join-Path $PSScriptRoot "backup.ps1"

if (-not (Test-Path -LiteralPath $RetentionPs1)) {
    throw "找不到 $RetentionPs1 —— 本脚本要与 backend\scripts\retention.ps1 同在一个仓库里跑"
}
if ($DbUrl -notmatch '^sqlite:///') {
    throw "-DbUrl 要的是一个 SQLAlchemy 的库 URL（以 sqlite:/// 开头），收到 '$DbUrl'。⚠️ 本脚本刻意不替你猜：一个每天夜里跑的任务清错了库是静默的"
}
if ($At -notmatch '^\d{2}:\d{2}$') {
    throw "-At 要的是 24 小时制的 HH:mm（/ST 那一格的取值），收到 '$At'"
}

$BackupTaskName = $TaskName + "-Backup"

Write-Host ""
Write-Host "== 厦大体育数智系统 · 留存清理的计划任务 =="
Write-Host "   要跑的   $RetentionPs1"
Write-Host "   要清的库 $DbUrl"
Write-Host "   每天     $At（⚠️ 缺省这一条只在**当前用户登录着**的时候跑，见下面 ③）"
Write-Host ""
Write-Host "   ⚠️⚠️ 本脚本**不自动注册**：下面四条一律是**打印**，请自己粘到一个"
Write-Host "      **管理员**身份的命令行里跑。理由与 serve.ps1 -Lan 不自动改防火墙逐字相同："
Write-Host "      注册计划任务要提权、会在这台机器上留下一个每天夜里删行的系统对象，"
Write-Host "      而静默改甲方的机器不是交付物该有的形状。"
Write-Host ""
Write-Host ('   ① 注册（⚠️ /TR 里那些 \" 是 schtasks 自己嵌引号的写法，请**原样**粘贴）：')
Write-Host ('        schtasks /Create /TN ' + $TaskName + ' /SC DAILY /ST ' + $At + ' /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"' + $RetentionPs1 + '\" -DbUrl \"' + $DbUrl + '\""')
Write-Host "      ⚠️ 刻意**不带 /F**：同名的任务已经存在时它当场报错，而不是静默覆盖掉"
Write-Host "         一个别人注册过的任务（要重注册就先跑下面 ④ 那一条）。"
Write-Host ""
Write-Host "   ② 注册完**当场验一次**（它会真删一批过期行；想只看不动就先手工跑一次 -DryRun）："
Write-Host ('        schtasks /Run /TN ' + $TaskName)
Write-Host "      然后看结果码与上一次跑的时刻（``Last Result`` 应当是 0；2 = 被拒/回滚）："
Write-Host ('        schtasks /Query /TN ' + $TaskName + ' /V /FO LIST')
Write-Host "      ⚠️ 那份历史里只有结果码，而四张表各删了多少行在 ``retention.py`` 打印的"
Write-Host "         那几行里 —— 要留住它请在 ① 的 /TR 里把输出重定向到一个日志文件"
Write-Host "         （本脚本不替你决定落在哪，也不替你建那个文件）。"
Write-Host ""
Write-Host "   ③ 要它**无人值守**地跑（当前用户没登录也跑）：给 ① 加上 /RU 与 /RP。"
Write-Host "      ⚠️ 那是一次口令策略判断（口令会落进任务定义里），本脚本**不替你做**，"
Write-Host "         也不打印一个带口令的命令原文。用 /RU SYSTEM 那一档下**用户级**环境变量"
Write-Host "         读不到，故 -DbUrl 必须像上面那样**显式**传（本脚本打印的形状已经传了）。"
Write-Host ""
Write-Host "   ④ 注销（与 ① 一对；试用/交付结束之后请把这台机器上的这两个对象删掉）："
Write-Host ('        schtasks /Delete /TN ' + $TaskName + ' /F')
Write-Host ""
Write-Host "   ⚠️ 建议：**再注册一条备份任务，排在清理前面 30 分钟**（清理不会自动备份，"
Write-Host "      逐字理由见 retention.py 的模块 docstring 与 spec §13.24）："
Write-Host ('        schtasks /Create /TN ' + $BackupTaskName + ' /SC DAILY /ST ' + $BackupAt + ' /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"' + $BackupPs1 + '\" -DbUrl \"' + $DbUrl + '\""')
Write-Host ('        schtasks /Delete /TN ' + $BackupTaskName + ' /F')
Write-Host "      ⚠️ 两个任务而不是「一个任务里串两条命令」：后者要在 /TR 里再嵌一层"
Write-Host "         cmd /c 与 &&，那是第三套引号规则（spec §15 G4 已登记过两套）。"
Write-Host "      ⚠️ 而 backup.ps1 今天**不做**保留策略（每跑一次多一份明文整库副本、"
Write-Host "         从不删旧的）。给它一个 -Keep 是 Plan 08 **Task 3** 的事；"
Write-Host "         在那之前请自己定期清 backend\backups\（或把它指到一个加密卷上：-Dir）。"
Write-Host ""
Write-Host "   要改窗口：⚠️ 四个缺省值与四个下界的**唯一所有者**是 backend\scripts\retention.py"
Write-Host "      （DEFAULT_*_DAYS / MIN_DAYS / AUDIT_MIN_DAYS），本脚本**一个数字都不复述**；"
Write-Host "      要看这四个数是多少，跑一次 -DryRun —— 它会把四张表各自的窗口与截止时刻逐行打印。"
Write-Host "      要覆盖请给 ① 的 /TR 加上例如 -ReadAuditDays 30，或设一个**机器级**环境变量"
Write-Host "      PE_RETENTION_READ_AUDIT_DAYS（⚠️ 写审计那一格有一个下界：spec §13.9.1 逐字"
Write-Host "      「写审计**不少于 1 年**」，低于它会被拒 + 退出码 2）。"
Write-Host ""
exit 0
