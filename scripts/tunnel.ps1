<#
.SYNOPSIS
    一条命令开一条**公网隧道**（Plan 07 Task 3）：把一个**已经在本地跑着**的试用档接到公网上，
    于是甲方在**任何网络**（家里 / 手机流量 / 校园网外的会议室）都能点开同一条链接。

.DESCRIPTION
    七步：① 数并清掉上一轮留下的孤儿隧道进程（⚠️ 保守判据，宁可漏杀不可误杀）
    → ② 解析后端（``cloudflared`` / ``ssh``；⚠️ **一个函数**决定「用哪个后端、
    用什么参数起它、从哪一份日志里抓 URL」）→ ③ 健康检查那个本地端口
    （打不通就**报一句人话并退出非 0**）→ ④ 起隧道进程、从它的日志里抓出公网 URL、
    并**真发一次请求复核它活着**（不是「抓到字符串就算成功」）→ ⑤ 把 URL 写进
    ``.trial\public-url.txt``（⚠️ 已进 ``.gitignore``）→ ⑥ 打印**六条**风险告示
    → ⑦ **前台阻塞**（``Ctrl-C`` 停；``finally`` 杀掉隧道进程并复核进程归零）。

    ------------------------------------------------------------------------
    ⚠️ 它**不起服务**、也**不灌数据**（那两个所有者一个都不当）
    ------------------------------------------------------------------------
    起 uvicorn 是 ``scripts\serve.ps1`` 的活，灌试用库是 ``scripts\trial.ps1`` 的活
    （姿势与 ``trial.ps1`` 委托 ``serve.ps1`` 那一条逐字同一个理由：**第二个启动器**
    意味着「服务怎么起」有了两个住址，改一处漏一处，而漏掉的那一处是要交给甲方跑的）。
    故本文件第 ③ 步健康检查打不通时，它**不替你去起服务**，只把该跑哪一条命令说清楚。

    ------------------------------------------------------------------------
    ⚠️ 档位裁定（实施计划 07 §3）：公网档跑 **prod**
    ------------------------------------------------------------------------
    隧道的**边缘是 HTTPS**：Cloudflare 在它的边缘终结 TLS，回源到本机是明文
    ``http://127.0.0.1:<Port>``。于是浏览器看到的是一个 ``https://`` 站点 ⇒
    cookie 的 ``Secure`` **成立**、不会被拒收；同源 ⇒ **不需要** CORS
    （``PE_CORS_ORIGINS`` 可以留空 —— 空 = 不挂 ``CORSMiddleware``，本波实测过 prod 照样起得来）；
    ``prod`` 还会关掉请求头身份通道并跑一遍启动自检（spec §13.8 / §13.11）。

    ⚠️ 这一格与 ``serve.ps1 -Lan`` 那一档**相反**，而两档都**不许改**：
      · **局域网档 = ``dev``**：明文 http 上浏览器**拒收** ``Secure`` cookie，
        症状是「登录 200、下一个请求 401」（Plan 06 Task 7 论证过，spec §13.11.3）；
      · **公网档 = ``prod``**：边缘是 HTTPS，故 ``Secure`` 成立。
    ⚠️ 于是两处打印的档位提示刻意是**两段不同的话**（守卫
    ``backend/tests/test_tunnel.py`` 的
    ``test_the_public_tier_hint_and_the_lan_tier_hint_are_two_different_passages``
    钉住「一段里那句无歧义的话不出现在另一段里」，两侧不同源）。

    ⚠️ 本脚本**不设** ``PE_ENV``：档位是**部署事实**、归运维的环境变量，
    不是一个命令行旗标（与 ``serve.ps1`` 刻意没有 ``-Prod`` 开关逐字同一条理由）。
    它只**读**并**打印**档位，并在实测到 ``dev`` 时打一段 ⚠️（**不是** ``throw``：
    ``dev`` 在隧道下也**能登** —— HTTPS 页面上收一张非 ``Secure`` 的 cookie 是允许的，
    本波用真浏览器实测过；``throw`` 会把一档能用的退路一起打死）。

    ------------------------------------------------------------------------
    ⚠️ 链接的寿命 = 本进程的寿命（这一句必须印出来）
    ------------------------------------------------------------------------
    quick tunnel 的地址是 Cloudflare **当场随机发**的（形状
    ``https://<三个单词>.trycloudflare.com``）：**每次重开都变**、进程一死就失效
    （实测变成 Cloudflare 自己的一页错误，不是「连不上」）。故 ⑥ 那一段与
    ``.trial\public-url.txt`` 里都逐字写着这一句，⚠️ 不许让人以为链接是永久的。
    也正因如此，``finally`` 会把那个 URL 文件**删掉**：留一份写着死链接的文件，
    比没有文件更坏（下一个人会照着它去点）。

.PARAMETER Port
    本地端口，缺省 **8030** —— 与 ``scripts\trial.ps1`` 对齐（那一个是「给甲方点的那一份」）。
    ⚠️ 本脚本**只读**这个端口上的服务，一个字节都不写它。

.PARAMETER Backend
    隧道后端：``auto``（缺省）/ ``cloudflared`` / ``ssh``。

    ``auto`` = 先找 ``cloudflared``（``PATH`` → 本仓 ``tools\cloudflared.exe`` →
    winget 的 ``Links`` 目录），一个都找不到才回落到 ``ssh``
    （本机自带的 OpenSSH + ``localhost.run``，**零安装**）。

    ⚠️⚠️ ``ssh`` 那一支**没有**被端到端验证过，如实交代（本机 + 本波那个网络的实测）：
    ``localhost.run:22`` 的 **TCP 连接与 SSH banner 都正常**（实测 251 ms 内收到
    ``SSH-2.0-russh_0.63.3``），而**密钥交换那一档挂住** —— 30 秒以上零输出、
    连 ``-o ConnectTimeout=12`` 都不触发（那一条只管 TCP），最终报一句
    ``ssh_dispatch_run_fatal: Connection to 35.171.254.69 port 22: Connection timed out``；
    ``-p 443`` 变体被对端**直接关闭**（原文 ``Connection closed by 35.171.254.69 port 443``）。
    故那一支今天只有「**失败得响亮**」这一格被验证过（下面那道前置探测 + 一个更短的
    URL 上限 + 超时之后把全部日志原文打出来），「真的能拿到 URL」那一格**没有**。
    ⚠️ 它留在代码里的理由是：换一台机器/换一个网络它就是一档**零安装**的退路，
    而把它删掉等于让那台机器上的人重新实现一遍。
    **cloudflared 是本波唯一被端到端验证过的后端**（六格取证见实现者报告）。

.EXAMPLE
    # 终端 A（公网档：prod + 试用库）
    $env:PE_ENV = 'prod'; powershell -ExecutionPolicy Bypass -File scripts\trial.ps1 -Port 8030 -Reset

    # 终端 B（⚠️ 请在**同样设过** $env:PE_ENV 的终端里跑，否则第 ③ 步报的档位只是本进程看到的）
    powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1 -Port 8030

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1 -Port 8030 -Backend ssh
    # 强制走零安装的 ssh 后端（⚠️ 见 .PARAMETER Backend 里那段如实交代）
#>
[CmdletBinding()]
param(
    [int]$Port = 8030,
    [ValidateSet('auto', 'cloudflared', 'ssh')]
    [string]$Backend = 'auto'
)

$ErrorActionPreference = "Stop"

# ⚠️ 承重的：PowerShell 5.1 的 .NET 缺省只谈 TLS 1.0/1.1，而 Cloudflare 的边缘一律要
#    TLS 1.2+ ⇒ 不设这一格，第 ④ 步那个「复核 URL 活着」会在本机报一句
#    「基础连接已经关闭: 发送时发生错误」，而真因是**协议版本**（离真因有一层，
#    与 serve.ps1 文件头记的那一类「WinError 10048」同款坑）。
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $RepoRoot "backend"

#: 公网 URL 落在哪个文件。⚠️ 路径的**唯一所有者**是本行（``.gitignore`` 里那一条
#: 与守卫 ``backend/tests/test_tunnel.py`` 都按字面钉它，两侧不同源）。
#: ⚠️ 为什么写文件而不只打印：链接要能被**别人**读到、能被**脚本**读到，
#: 而不只闪在一个终端上（终端一滚就没了，而甲方要的是那一条能点的地址）。
$TrialDir = Join-Path $RepoRoot ".trial"
$UrlFile = Join-Path $TrialDir "public-url.txt"

$LocalBase = "http://127.0.0.1:$Port"
$LocalHealth = "$LocalBase/api/health"

$HealthTimeoutSeconds = 60
$UrlTimeoutSeconds = 120
$ReachTimeoutSeconds = 90

#: 抓公网 URL 的正则 —— ⚠️ **全仓只有这一处**（单一所有者）。
#: · ``trycloudflare.com`` = cloudflared 的 quick tunnel；``lhr.life`` = localhost.run。
#: · ⚠️ 刻意**不**用宽松的 ``https://\S+``：cloudflared 的日志里有
#:   ``https://www.cloudflare.com/website-terms/``、``https://developers.cloudflare.com/...``
#:   与 ``region1.v2.argotunnel.com`` 一类地址，宽松正则会把**第一个**抓到的当成隧道地址
#:   （而那一行恰好是免责声明里的条款链接 —— 于是一条「打不开的公网链接」被印给甲方）。
$TunnelUrlPattern = 'https://[a-z0-9]+(?:-[a-z0-9]+)*\.(?:trycloudflare\.com|lhr\.life)'

#: 隧道日志的临时目录名。⚠️ 它**同时是孤儿清理的判据**：本脚本起的隧道进程，
#: 命令行里一定含 ``pe_tunnel_<Port>``（cloudflared 走 ``--logfile``、ssh 走 ``-E``），
#: 而别人的隧道进程一定不含。故「只杀自己留下的那一些」是可判的（见第 ① 步）。
$LogDirName = "pe_tunnel_$Port"
$LogDir = Join-Path $env:TEMP $LogDirName
$LogFile = Join-Path $LogDir "tunnel.log"
$ErrFile = Join-Path $LogDir "stderr.log"
$OutFile = Join-Path $LogDir "stdout.log"
$SshDebugFile = Join-Path $LogDir "ssh-debug.log"

Write-Host "== 厦大体育数智系统 · 公网隧道 =="
Write-Host "   repo      = $RepoRoot"
Write-Host "   本地服务  = $LocalBase（⚠️ 本脚本**只读**它，不起它、不写它）"
Write-Host "   URL 文件  = $UrlFile"
Write-Host "   隧道日志  = $LogDir"

# ---------------------------------------------------------------------------
# ① 上一轮留下的孤儿隧道进程：先数、打印、然后只杀**自己的**
# ---------------------------------------------------------------------------
# ⚠️ 为什么要有这一步（Task 1+2 登记过一条待清扫：「进程被工具硬杀时 finally 跑不到，
#    留下临时目录」）：本脚本被硬杀（IDE 的停止按钮 / 任务管理器 / 断电）时 ``finally``
#    跑不到 ⇒ 隧道进程**活着**、而没人看着它的 URL ⇒ 一个**没人管的公网入口**一直开着。
#    那一档比留一个临时目录坏得多，故这里补一道。
# ⚠️⚠️ 判据刻意**保守**（宁可漏杀不可误杀）：两条**同时**成立才杀 ——
#    ① 进程名恰好是 ``cloudflared.exe`` / ``ssh.exe``；
#    ② 它的**命令行**里含本脚本自己的标记 ``pe_tunnel_<Port>``。
#    ⚠️ 只按进程名杀就是**杀别人的进程**：一台机器上完全可能同时跑着甲方 IT 自己的
#    named tunnel、另一份仓库的 quick tunnel、或另一个端口上的隧道。
Write-Host ""
Write-Host "-- ① 上一轮留下的孤儿隧道进程 --"

$Orphans = @(Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe' OR Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($LogDirName) })
if ($Orphans.Count -eq 0) {
    Write-Host "   没有。判据（两条**同时**成立才算）：进程名是 cloudflared.exe / ssh.exe，"
    Write-Host "   且**命令行里含本脚本自己的标记** $LogDirName（别人的隧道进程不含它 ⇒ 不会被误杀）。"
} else {
    Write-Host ("   ⚠️ 数到 " + $Orphans.Count + " 个（命令行里都含标记 $LogDirName，即本脚本上一轮留下的）：")
    foreach ($Orphan in $Orphans) {
        Write-Host ("     PID " + $Orphan.ProcessId + "  " + $Orphan.Name)
        Write-Host ("       命令行 = " + $Orphan.CommandLine)
        Stop-Process -Id $Orphan.ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
        if (Get-Process -Id $Orphan.ProcessId -ErrorAction SilentlyContinue) {
            Write-Host ("       → ⚠️ 停不掉（权限？）：请手工 Stop-Process -Id " + $Orphan.ProcessId + " -Force")
        } else {
            Write-Host "       → 已停（它开着的那条公网链接随之失效）"
        }
    }
}

# ⚠️ 上一轮留下的 URL 文件：那条链接**已经死了**（隧道进程寿命 = 链接寿命），
#    留着它等于留下一句看得见的谎，故当场删掉、并说清为什么。
if (Test-Path $UrlFile) {
    Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue
    Write-Host "   上一轮留下了 $UrlFile → 已删（那条链接随上一轮的隧道进程一起死了，留着是撒谎）"
}

# ⚠️ 旧的隧道日志**必须清掉**：第 ④ 步是从这份文件里正则抓 URL 的，
#    一份上一轮的日志会让它**当场抓到一条死链接**并报成功（失效方向是静默的，
#    于是「甲方点开是个错误页」会一路绿到交付现场）。
foreach ($Stale in @($LogFile, $ErrFile, $OutFile, $SshDebugFile)) {
    if (Test-Path $Stale) { Remove-Item $Stale -Force -ErrorAction SilentlyContinue }
}
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

# ---------------------------------------------------------------------------
# ② 解析后端 —— ⚠️ **单一所有者**
# ---------------------------------------------------------------------------
# ⚠️ **单一所有者**：「用哪个后端、用什么参数起它、从哪一份文件里抓 URL」三件事
#    **只在本函数里决定一次**（控制者裁定）。⚠️ 抓 URL 的**正则**不在这里，
#    它是文件头那个 $TunnelUrlPattern（同样只有一处）：正则要跟着**两家服务商**走，
#    而后端选择要跟着**这台机器上装了什么**走，两者的变化理由不同，
#    故住在两个地方、各只有一个住址。
# ⚠️ 本函数**刻意不用** PowerShell 的块注释形式：守卫按字面钉「本文件里那个
#    块注释收尾符只出现**一次**」（即文件头 comment-based help 的收尾），
#    第二处会让守卫的切法失效（姿势同 tests/test_trial.py 的 _trial_ps1_code）。
function Resolve-TunnelBackend {
    param([string]$Requested)

    # --- cloudflared：PATH → 本仓 tools\ → winget 的 Links -------------------
    # ⚠️ 顺序是承重的：``PATH`` 优先，于是运维自己装的那一份（winget / 手工）赢；
    #    本仓 ``tools\cloudflared.exe`` 是**次选**（Plan 07 Task 3 的路 B：
    #    winget 的 MSI 要 UAC 提权，在无人值守的那一档上会**挂住**，
    #    而一个 55 MB 的独立二进制下载下来就能跑，⚠️ ``tools/`` 已进 ``.gitignore``、
    #    二进制不入库）。
    $CloudflaredExe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrEmpty($CloudflaredExe)) {
        foreach ($Candidate in @(
                (Join-Path $RepoRoot "tools\cloudflared.exe"),
                (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\cloudflared.exe")
            )) {
            if (Test-Path $Candidate) { $CloudflaredExe = $Candidate; break }
        }
    }

    # --- ssh：PATH → Windows 自带的 OpenSSH ----------------------------------
    $SshExe = (Get-Command ssh -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrEmpty($SshExe)) {
        $BuiltIn = Join-Path $env:SystemRoot "System32\OpenSSH\ssh.exe"
        if (Test-Path $BuiltIn) { $SshExe = $BuiltIn }
    }

    $Chosen = $Requested
    if ($Chosen -eq 'auto') {
        if (-not [string]::IsNullOrEmpty($CloudflaredExe)) { $Chosen = 'cloudflared' }
        elseif (-not [string]::IsNullOrEmpty($SshExe)) { $Chosen = 'ssh' }
        else { $Chosen = '' }
    }

    if ($Chosen -eq 'cloudflared') {
        if ([string]::IsNullOrEmpty($CloudflaredExe)) {
            throw "找不到 cloudflared：PATH 上没有，$RepoRoot\tools\cloudflared.exe 也不在，winget 的 Links 目录里也没有。装它（winget install --id Cloudflare.cloudflared）或下载那个独立二进制到 tools\cloudflared.exe（⚠️ tools\ 已进 .gitignore，不入库），或加 -Backend ssh 走零安装的那一支。"
        }
        return [pscustomobject]@{
            Name                = 'cloudflared'
            Exe                 = $CloudflaredExe
            # ⚠️ ``--logfile`` 是承重的**两格**：① 它是抓 URL 的那一份日志
            #    （本机实测：cloudflared 把 ``https://<三个单词>.trycloudflare.com``
            #    打在 **stderr**，stdout 恒为 0 字节；给了 ``--logfile`` 之后
            #    那一份完整日志同时落在这个文件里，于是「读哪一股」有确定答案）；
            #    ② 它让本进程的**命令行里含标记** ``pe_tunnel_<Port>``，
            #    于是第 ① 步能认出「这是我自己留下的孤儿」。
            # ⚠️ ``--no-autoupdate``：交付物不该在甲方机器上偷偷换自己的版本。
            Arguments           = @('tunnel', '--url', $LocalBase, '--no-autoupdate', '--logfile', $LogFile)
            RedirectStandardError = $ErrFile
            RedirectStandardOutput = $OutFile
        }
    }

    if ($Chosen -eq 'ssh') {
        if ([string]::IsNullOrEmpty($SshExe)) {
            throw "找不到 ssh：PATH 上没有，$env:SystemRoot\System32\OpenSSH\ssh.exe 也不在。装 cloudflared（见上一条那一句人话）或装 Windows 的 OpenSSH 客户端。"
        }
        return [pscustomobject]@{
            Name                = 'ssh'
            Exe                 = $SshExe
            # ⚠️ ``-E`` 把 ssh 自己的调试日志写到 ``$LogDir`` 下 —— 于是**它的命令行里
            #    也含标记** ``pe_tunnel_<Port>``（与 cloudflared 的 ``--logfile`` 同一条
            #    理由：第 ① 步那两道保守判据要能认出自己留下的孤儿）。
            #    ⚠️ 而抓 URL 读的是 **stderr 重定向**那一份（``$LogFile``）：
            #    localhost.run 把 ``https://<rand>.lhr.life`` 打在 stderr 上，
            #    ``-E`` 那个文件只有 ssh 自己的调试行。
            Arguments           = @(
                '-o', 'StrictHostKeyChecking=accept-new',
                '-o', 'ExitOnForwardFailure=yes',
                '-o', 'ServerAliveInterval=15',
                '-E', $SshDebugFile,
                '-R', "80:localhost:$Port",
                'nokey@localhost.run'
            )
            RedirectStandardError = $LogFile
            RedirectStandardOutput = $OutFile
        }
    }

    $CloudflaredShown = if ([string]::IsNullOrEmpty($CloudflaredExe)) { '无' } else { $CloudflaredExe }
    $SshShown = if ([string]::IsNullOrEmpty($SshExe)) { '无' } else { $SshExe }
    throw ("本机上**两个后端都找不到**（cloudflared 实测到 = " + $CloudflaredShown + "；ssh 实测到 = " + $SshShown + "）。处置：winget install --id Cloudflare.cloudflared，或把那个独立二进制下载到 tools\cloudflared.exe（⚠️ tools\ 已进 .gitignore，二进制不入库）。")
}

$Tunnel = Resolve-TunnelBackend -Requested $Backend
Write-Host ""
Write-Host "-- ② 后端 --"
Write-Host ("   选定     = " + $Tunnel.Name + "（-Backend $Backend）")
Write-Host ("   可执行   = " + $Tunnel.Exe)

# --- 跑一个外部命令并把它的 stdout+stderr 一起收成字符串 -------------------------
# ⚠️ 承重的：本文件第 0 行是 $ErrorActionPreference = "Stop"，而 PowerShell 5.1 在
#    那一档下会把**外部命令写到 stderr 的每一行**包成一个 ErrorRecord 并**抛**
#    （本机实测的原文是 ``NativeCommandError``，与 trial.ps1 里记的那一格同款）。
#    而 ``ssh -V`` **恰好**把版本打在 stderr 上、python 的 alembic/日志行也在 stderr 上
#    ⇒ 不降这一档，「读个版本号」会变成一次脚本终止。
#    ⚠️ 只在本函数**内部**降（函数作用域），出去之后仍是 Stop。
function Invoke-QuietNative {
    param([string]$Exe, [string[]]$NativeArguments)
    $Previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        return ((& $Exe @NativeArguments) 2>&1 | ForEach-Object { $_.ToString() })
    } finally {
        $ErrorActionPreference = $Previous
    }
}

# --- 后端版本（写进 URL 文件，将来换机器时对得上是哪一份二进制）-----------------
$TunnelVersion = ''
try {
    if ($Tunnel.Name -eq 'cloudflared') {
        $TunnelVersion = (Invoke-QuietNative -Exe $Tunnel.Exe -NativeArguments @('--version') | Select-Object -First 1)
    } else {
        # ⚠️ ssh -V 把版本打在 **stderr** 上（不是 stdout），故上面那个收两股流的辅助是承重的。
        $TunnelVersion = (Invoke-QuietNative -Exe $Tunnel.Exe -NativeArguments @('-V') | Select-Object -First 1)
    }
} catch { $TunnelVersion = '读不出版本' }
if ([string]::IsNullOrWhiteSpace($TunnelVersion)) { $TunnelVersion = '读不出版本' }
$TunnelVersion = $TunnelVersion.ToString().Trim()
Write-Host ("   版本     = " + $TunnelVersion)
# ⚠️ 本脚本**一次都不改防火墙**（连一条 netsh 命令都不打印）：隧道是一条**出站**连接
#    （cloudflared 主动拨到 Cloudflare 的边缘，走 443 / QUIC），故**不需要任何入站放行**
#    —— Windows 的防火墙缺省就放行出站。⚠️ 这与 ``serve.ps1 -Lan`` 那一档**相反**：
#    那一档要让**别的机器连进来**，故它打印一条 netsh advfirewall 的入站规则。
#    （守卫：``backend/tests/test_tunnel.py`` 的
#    ``test_tunnel_ps1_never_touches_the_firewall_because_a_tunnel_is_outbound_only``。）
Write-Host "   防火墙   = 本脚本**一次都不碰**（连一条 netsh 都不打印）：隧道是一条**出站**连接"
Write-Host "              （cloudflared 主动拨到 Cloudflare 的边缘，走 443 / QUIC），故不需要任何入站放行。"
Write-Host "              ⚠️ 这与 serve.ps1 -Lan 那一档**相反**：那一档要让别的机器**连进来**，故它打印一条 netsh。"

# --- ssh 那一支的前置 TCP 探测：⚠️ 让它**失败得快而响亮** ----------------------
# ⚠️ 本机实测（Plan 07 Task 3）：TCP 与 SSH banner 都正常（251 ms 内收到
#    ``SSH-2.0-russh_0.63.3``），挂的是**密钥交换**那一档 —— 30 秒以上零输出。
#    故本探测挡的是**更外面那一圈**（22 端口出站被封 / 需要代理，那是企业网上
#    最常见的一档，症状是 TCP 都连不上）；⚠️ 它**挡不住**「TCP 通而 KEX 挂住」，
#    那一档由下面 ④ a 的**更短 URL 上限**（ssh = 45 秒）+ 每 10 秒一行进度
#    + 超时后把全部日志原文打出来兜住（逐字理由见 .PARAMETER Backend）。
if ($Tunnel.Name -eq 'ssh') {
    Write-Host "   前置探测 = TCP 连 localhost.run:22（⚠️ 这一支在本波实测的那个网络上**没通过** KEX，见 .PARAMETER Backend）"
    $Probe = New-Object System.Net.Sockets.TcpClient
    try {
        $Task = $Probe.ConnectAsync('localhost.run', 22)
        if (-not $Task.Wait(8000)) {
            Write-Host ""
            Write-Host "   ⚠️ 8 秒内连不上 localhost.run:22 ⇒ 这个网络的 22 端口出站不通（或要走代理）。"
            Write-Host "      处置：装 cloudflared（它走 443/QUIC，本波实测通）—— winget install --id Cloudflare.cloudflared，"
            Write-Host "            或把独立二进制下载到 tools\cloudflared.exe，然后重跑本脚本（缺省的 -Backend auto 会挑它）。"
            exit 1
        }
        Write-Host "   前置探测 = TCP 通（⚠️ 而「SSH 的密钥交换能不能过」是**另一格**，本波在那台机器上实测**没过**："
        Write-Host "                banner 251 ms 就到了，KEX 却挂住 30 秒以上零输出）"
        # ⚠️ ssh 那一支的 URL 上限**更短**：localhost.run 通的时候是 2 秒内就把地址打在
        #    stderr 上的，故 45 秒还不出来就说明这一档不通 —— 让运维等 120 秒没有意义。
        $UrlTimeoutSeconds = 45
    } finally {
        $Probe.Close(); $Probe.Dispose()
    }
}

# ---------------------------------------------------------------------------
# ③ 健康检查那个本地端口（⚠️ 打不通就报一句人话、退出非 0；**不自己起服务**）
# ---------------------------------------------------------------------------
# ⚠️ 姿势逐字照 serve.ps1 的 ④：轮询、超时、把真因说清楚。
Write-Host ""
Write-Host "-- ③ 健康检查（本地）--"

$Deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
$LocalBody = $null
$Tries = 0
while ((Get-Date) -lt $Deadline) {
    $Tries += 1
    try {
        $Probe = Invoke-WebRequest -Uri $LocalHealth -UseBasicParsing -TimeoutSec 3
        if ($Probe.StatusCode -eq 200) { $LocalBody = $Probe.Content; break }
    } catch {
        # 还没监听 / 还在建表：继续轮询。⚠️ 刻意不打印每一次失败（60 秒 ×2 次/秒 = 120 行噪音）。
    }
    Start-Sleep -Milliseconds 500
}

if ($null -eq $LocalBody) {
    Write-Host ""
    Write-Host ("   ⚠️ $LocalHealth 在 $HealthTimeoutSeconds 秒内没有回 200（轮询了 $Tries 次）。")
    Write-Host "      本脚本**不自己起服务**（那是第二个所有者：起 uvicorn 归 scripts\serve.ps1，灌试用库归 scripts\trial.ps1）。"
    Write-Host ""
    Write-Host ("      请先在**另一个终端**里跑：scripts\trial.ps1 -Port $Port -Reset")
    Write-Host "      （公网档还要先设 `$env:PE_ENV='prod'` —— 隧道边缘是 HTTPS，故 Secure cookie 成立；"
    Write-Host "       逐字理由见本文件 .DESCRIPTION 的「档位裁定」那一段），再跑本脚本。"
    $Listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($Listeners.Count -eq 0) {
        Write-Host ("      实测：端口 $Port 上**没有任何 listener** ⇒ 服务没起（或起在别的端口上）。")
    } else {
        Write-Host ("      实测：端口 $Port 上有 listener（PID " + $Listeners[0].OwningProcess + "），而 /api/health 没有回 200 ⇒ 起在那个端口上的**不是本系统的服务**，或它还在启动中。")
    }
    exit 1
}

$LocalHealthObject = ($LocalBody | ConvertFrom-Json)
Write-Host ("   $LocalHealth → 200（轮询 $Tries 次）")
Write-Host ("   " + $LocalBody)

# --- 档位：⚠️ 本进程读到的那一格，而服务是**另一个进程**起的 --------------------
# ⚠️ 判据的所有者是 backend\app\deploy.py 的 tier() 与 app\auth\sessions.py 的
#    cookie_secure()（与 serve.ps1 的 ③ c 同一个探针；⚠️ 本文件不自己实现一套档位判定）。
# ⚠️⚠️ 如实说清它的**局限**：本脚本与服务是两个进程，环境变量不共享。
#    若运维在终端 A 里 `$env:PE_ENV='prod'` 起了服务、却在**没设** PE_ENV 的终端 B 里
#    跑本脚本，下面这一格会显示 dev —— 那不是服务真的在 dev 档。
#    故打印时逐字写明「本进程」，并指向服务那个终端里 serve.ps1 打的那一行。
$Tier = '读不出'
$CookieSecure = '读不出'
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not [string]::IsNullOrEmpty($PythonExe)) {
    try {
        Push-Location $BackendDir
        $TierProbe = @(Invoke-QuietNative -Exe $PythonExe -NativeArguments @(
                '-c', 'from app import deploy;from app.auth.sessions import cookie_secure;print(deploy.tier());print(cookie_secure())'
            ) | Where-Object { $_.Trim().Length -gt 0 })
        Pop-Location
        if ($TierProbe.Count -ge 2) {
            $Tier = $TierProbe[0].Trim()
            $CookieSecure = $TierProbe[$TierProbe.Count - 1].Trim()
        }
    } catch {
        Pop-Location
    }
}
Write-Host ("   档位（**本进程**的 PE_ENV = " + $(if ([string]::IsNullOrEmpty($env:PE_ENV)) { '未设' } else { $env:PE_ENV }) + "）= $Tier（cookie 的 Secure = $CookieSecure）")
if ($Tier -eq 'prod') {
    Write-Host "      ✓ 公网档就是这一档：隧道边缘是 HTTPS（Cloudflare 终结 TLS、回源是明文 $LocalBase），"
    Write-Host "        故 Secure cookie 在浏览器侧**成立**、不会被拒收；同源 ⇒ 不需要 CORS，PE_CORS_ORIGINS 可以留空。"
} elseif ($Tier -eq 'dev') {
    Write-Host "      ⚠️ 实测是 dev 档（本进程）。dev 在隧道下**也能登**：HTTPS 页面上收一张**非** Secure 的 cookie 是允许的"
    Write-Host "         （本波用真浏览器实测过），故它是一档**可用的退路**、本脚本不 throw。"
    Write-Host "         而公网档的正确档位是 **prod**（多三样：Secure cookie、请求头身份通道强制关、启动自检会跑）。"
    Write-Host "         要切过去：Ctrl-C 停掉服务 → 在起服务的那个终端里 `$env:PE_ENV='prod'` → 重跑 trial.ps1 与本脚本。"
}
Write-Host "      ⚠️ 这一格是**本进程**读到的：服务是**另一个进程**起的，环境变量不共享。"
Write-Host "         以起服务那个终端里 serve.ps1 打的「档位 = …（cookie 的 Secure = …）」那一行为准。"
Write-Host "      ⚠️ 对照：``serve.ps1 -Lan`` 那一档必须留在 **dev** —— 局域网是**明文 http**，"
Write-Host "         prod 的 Secure cookie 会被浏览器**拒收**，症状是「登录 200、下一个请求 401」（spec §13.11.3）。"

# ---------------------------------------------------------------------------
# ④ 起隧道 → 抓 URL → **真发一次请求复核它活着**
# ---------------------------------------------------------------------------
# ⚠️ **读一份别人正在写的文件**的唯一住址。
# ⚠️⚠️ 这一格是本波**实测**抓到的一个真 bug（不是想出来的）：原来两处直接用
#    ``[System.IO.File]::ReadAllText($Path)``，而它以 ``FileShare.Read`` 打开
#    ——即「只允许别人也**读**」。而 cloudflared 的 ``--logfile`` 是**写**句柄，
#    两个共享模式互斥 ⇒ ``ReadAllText`` **当场抛 IOException**，
#    被下面那个 ``catch { return }`` 静默吃掉 ⇒ 抓 URL 的循环**空转到超时**，
#    而屏幕上「隧道日志」一行都不打（本机亲验：URL 早就在 tunnel.log 里了、
#    cloudflared 也活着，而脚本停在那一句正则上不动）。
#    修法是显式给 ``FileShare.ReadWrite``（Python 的 ``open(...,'rb')`` 与
#    ``Get-Content`` 缺省就是这个语义，故探针读得到、而 .NET 那一档读不到）。
#    ⚠️ 而「静默吃掉」这一档也一并修了：连续读不出来就**打印**，不再闷着。
function Read-TunnelLogText {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $Stream = $null
    $Reader = $null
    try {
        $Stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $Reader = New-Object System.IO.StreamReader($Stream)
        return $Reader.ReadToEnd()
    } catch {
        return $null
    } finally {
        if ($null -ne $Reader) { $Reader.Dispose() }
        if ($null -ne $Stream) { $Stream.Dispose() }
    }
}

# 把隧道日志里**新长出来的**那几行打到屏上（⑦ 前台阻塞那一段靠它保持日志活着）。
function Write-NewTunnelLog {
    param([string]$Path)
    $All = Read-TunnelLogText -Path $Path
    if ($null -eq $All) { return }
    if ($All.Length -le $script:Echoed) { return }
    $New = $All.Substring($script:Echoed)
    $script:Echoed = $All.Length
    foreach ($Line in ($New -split "`r?`n")) {
        if ($Line.Trim().Length -gt 0) { Write-Host ("      | " + $Line.TrimEnd()) }
    }
}

# ⚠️ **抓 URL 的唯一住址**：从给定的几份日志里按 $TunnelUrlPattern 抓第一个匹配。
function Get-TunnelUrl {
    param([string[]]$Paths)
    foreach ($Path in $Paths) {
        $All = Read-TunnelLogText -Path $Path
        if ($null -eq $All) { continue }
        $Match = [regex]::Match($All, $TunnelUrlPattern)
        if ($Match.Success) { return $Match.Value }
    }
    return $null
}

$script:Echoed = 0
$PublicUrl = $null
$Proc = $null
$Code = 0

Write-Host ""
Write-Host "-- ④ 起隧道 --"

try {
    $StartArguments = @{
        FilePath               = $Tunnel.Exe
        ArgumentList           = $Tunnel.Arguments
        WorkingDirectory       = $RepoRoot
        PassThru               = $true
        NoNewWindow            = $true
        RedirectStandardOutput = $Tunnel.RedirectStandardOutput
        RedirectStandardError  = $Tunnel.RedirectStandardError
    }
    Write-Host ("   " + $Tunnel.Name + " " + ($Tunnel.Arguments -join ' '))
    $Proc = Start-Process @StartArguments
    Write-Host ("   进程 PID = " + $Proc.Id + "（⚠️ 链接的寿命 = 这个进程的寿命）")
    Write-Host ("   抓 URL 读的是 = " + $LogFile + "（cloudflared 走 --logfile；ssh 走 stderr 重定向。")
    Write-Host ("                    ⚠️ 本机实测 cloudflared 把 URL 打在 **stderr**、stdout 恒为 0 字节）")
    Write-Host ("   正则（单一所有者）= " + $TunnelUrlPattern)
    Write-Host ""

    # --- ④ a  轮询日志抓 URL -------------------------------------------------
    $UrlDeadline = (Get-Date).AddSeconds($UrlTimeoutSeconds)
    $UrlStartedAt = Get-Date
    $NextProgressSeconds = 10
    while ((Get-Date) -lt $UrlDeadline) {
        if ($Proc.HasExited) { break }
        Start-Sleep -Milliseconds 500
        Write-NewTunnelLog -Path $LogFile
        $PublicUrl = Get-TunnelUrl -Paths @($LogFile, $ErrFile)
        if (-not [string]::IsNullOrEmpty($PublicUrl)) { break }
        # ⚠️ **反静默**（本波实测抓到的那一格）：读不出日志时上面两个函数都安静地返回，
        #    于是「等 URL」与「读不到日志」在屏幕上长得一模一样。故每 10 秒打一行进度，
        #    把「等了多久 / 日志多少字节 / 进程还活着吗」三格摆出来。
        $ElapsedSeconds = [int]((Get-Date) - $UrlStartedAt).TotalSeconds
        if ($ElapsedSeconds -ge $NextProgressSeconds) {
            $NextProgressSeconds += 10
            $LogText = Read-TunnelLogText -Path $LogFile
            $LogShown = if ($null -eq $LogText) { '读不出来（⚠️ 文件被独占？）' } else { ($LogText.Length.ToString() + ' 字符') }
            Write-Host ("      …还在等公网 URL（已等 " + $ElapsedSeconds + " 秒 / 上限 " + $UrlTimeoutSeconds + "；tunnel.log = " + $LogShown + "；进程 " + $(if ($Proc.HasExited) { '已退出' } else { 'PID ' + $Proc.Id + ' 还活着' }) + "）")
        }
    }

    if ([string]::IsNullOrEmpty($PublicUrl)) {
        Write-Host ""
        if ($Proc.HasExited) {
            Write-Host ("   ⚠️ 隧道进程在抓到 URL 之前就退出了（PID " + $Proc.Id + "，退出码 " + $Proc.ExitCode + "）。")
        } else {
            Write-Host ("   ⚠️ $UrlTimeoutSeconds 秒内没有从日志里抓到公网 URL（进程 PID " + $Proc.Id + " 还活着）。")
        }
        Write-Host "      下面是**全部**几份日志的原文（真因在里面；最常见的一档是本机出网被封 / 需要代理）："
        foreach ($Dump in @($LogFile, $ErrFile, $OutFile, $SshDebugFile)) {
            if (Test-Path $Dump) {
                Write-Host ("      --- " + $Dump + " ---")
                $DumpText = Read-TunnelLogText -Path $Dump
                if ($null -eq $DumpText) {
                    Write-Host "      | （读不出来：文件被别的进程独占？）"
                } else {
                    foreach ($Line in ($DumpText -split "`r?`n")) {
                        if ($Line.Trim().Length -gt 0) { Write-Host ("      | " + $Line.TrimEnd()) }
                    }
                }
            }
        }
        throw "拿不到公网 URL，本脚本不开一条**没验证过**的链接（宁可失败得响亮，也不印一条打不开的地址给甲方）。"
    }

    Write-Host ""
    Write-Host ("   ✓ 抓到公网 URL = " + $PublicUrl)

    # --- ④ b  **真发一次请求复核它活着** -------------------------------------
    # ⚠️ 承重的：抓到一串字符**不等于**那条链接打得开。quick tunnel 自己就印一句
    #    "it may take some time to be reachable"，而 Cloudflare 边缘在源站不可达时
    #    回的是**它自己的一页 5xx**（HTTP 层面「有响应」，而对甲方是打不开的）。
    #    故这里必须**穿过公网**打一次 /api/health，并要求它回的 tables 与本地那一格**逐字相同**
    #    （⚠️ 与本地比、而不是写死一个数字：那个数的所有者是 schema，
    #    在本文件里敲第二遍就是第二个所有者 —— 改表的人会漏改这里）。
    Write-Host ""
    Write-Host "-- ④ b 复核这条公网 URL 真的活着 --"
    $RemoteHealthUrl = $PublicUrl.TrimEnd('/') + "/api/health"
    $ReachDeadline = (Get-Date).AddSeconds($ReachTimeoutSeconds)
    $RemoteBody = $null
    $RemoteStatus = 0
    $RemoteTries = 0
    $LastFailure = ''
    while ((Get-Date) -lt $ReachDeadline) {
        $RemoteTries += 1
        try {
            $Remote = Invoke-WebRequest -Uri $RemoteHealthUrl -UseBasicParsing -TimeoutSec 15
            $RemoteStatus = [int]$Remote.StatusCode
            if ($RemoteStatus -eq 200) { $RemoteBody = $Remote.Content; break }
            $LastFailure = "HTTP $RemoteStatus"
        } catch {
            $LastFailure = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    }

    if ($null -eq $RemoteBody) {
        throw ("穿过公网打不通：" + $RemoteHealthUrl + " 在 " + $ReachTimeoutSeconds + " 秒内没有回 200（试了 " + $RemoteTries + " 次，最后一次是 " + $LastFailure + "）。隧道进程还活着而这一格不通，最常见的一档是 Cloudflare 边缘还没就绪或本机出网被限；上面 ④ a 那段日志是现场。")
    }
    $RemoteObject = ($RemoteBody | ConvertFrom-Json)
    Write-Host ("   GET " + $RemoteHealthUrl + " → " + $RemoteStatus + "（试了 " + $RemoteTries + " 次）")
    Write-Host ("   " + $RemoteBody)
    if ($RemoteObject.status -ne 'ok') {
        throw ("公网那一格回的不是 ok（实测 status = " + $RemoteObject.status + "）：隧道通了，而源站不健康。")
    }
    if ([string]$RemoteObject.tables -ne [string]$LocalHealthObject.tables) {
        throw ("公网那一格的 tables = " + $RemoteObject.tables + "，而本地是 " + $LocalHealthObject.tables + " ⇒ 这条隧道**没有**打到本机的 " + $LocalBase + "（打到别的东西上了）。")
    }
    Write-Host ("   ✓ 复核通过：公网那一格与本地那一格**逐字同形**（tables = " + $LocalHealthObject.tables + "、trial = " + $LocalHealthObject.trial + "）⇒ 这条链接真的通到本机的 $Port 端口")

    # -----------------------------------------------------------------------
    # ⑤ 把 URL 写进 .trial\public-url.txt（⚠️ 已进 .gitignore）
    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- ⑤ 写 URL 文件 --"
    if (-not (Test-Path $TrialDir)) { New-Item -ItemType Directory -Force -Path $TrialDir | Out-Null }
    $NowText = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
    $UrlLines = @(
        '# 厦大体育数智系统 · 公网试用链接',
        ('# ⚠️ 本文件由 scripts\tunnel.ps1 写；已进 .gitignore（链接是临时的，不该入版本控制）。'),
        ('# ⚠️ 本文件在隧道进程退出时会被**删掉**：留一份写着死链接的文件比没有文件更坏。'),
        '',
        ('url        = ' + $PublicUrl),
        ('起于       = ' + $NowText),
        ('后端       = ' + $Tunnel.Name + '（' + $Tunnel.Exe + '）'),
        ('后端版本   = ' + $TunnelVersion),
        ('本地端口   = ' + $Port + '（' + $LocalBase + '）'),
        ('本地 health= ' + $LocalBody),
        ('公网 health= ' + $RemoteBody + '   ← 写这个文件之前**真发过一次请求**复核它活着'),
        ('档位       = ' + $Tier + '（cookie 的 Secure = ' + $CookieSecure + '；⚠️ 这是 tunnel.ps1 **本进程**读到的，服务是另一个进程起的）'),
        ('隧道 PID   = ' + $Proc.Id),
        '',
        '⚠️ 本链接只在隧道进程活着时有效，重开会变：',
        ('   它的寿命 = 上面那个隧道进程（PID ' + $Proc.Id + '）的寿命。进程一停，这个地址立刻失效'),
        '   （实测变成 Cloudflare 自己的一页错误）；重跑 scripts\tunnel.ps1 会得到一个**全新的随机地址**。',
        '   ⚠️ 它是公网可达的：任何知道它的人都能打开。风险告示六条见终端里 ⑥ 那一段（或 scripts\tunnel.ps1 的源码）。'
    )
    # ⚠️ UTF-8 **带 BOM** + CRLF：这个文件是给**人**用记事本打开读的（甲方 IT 要抄那条链接），
    #    而没有 BOM 的 UTF-8 在老记事本里按 ANSI(GBK) 解码 ⇒ 中文全是乱码。
    #    （与本仓 .ps1 一律 BOM+CRLF 同一条理由；⚠️ 本文件**不入库**，故不受入库 blob 口径约束。）
    [System.IO.File]::WriteAllText($UrlFile, (($UrlLines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($true)))
    Write-Host ("   已写 " + $UrlFile + "（" + (Get-Item $UrlFile).Length + " B，UTF-8+BOM+CRLF）")
    Write-Host "   ⚠️ 为什么写文件而不只打印：链接要能被**别人**读到、能被**脚本**读到，而不只闪在一个终端上。"

    # -----------------------------------------------------------------------
    # ⑥ 六条风险告示（⚠️ 响亮；姿势照 serve.ps1 的 -Lan 那一段）
    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- ⑥ ⚠️⚠️⚠️ 公网暴露的风险告示（六条，念给甲方听之前先自己念一遍）--"
    Write-Host ""
    Write-Host ("   ① 这条链接是**公网可达**的：任何知道它的人都能打开，")
    Write-Host ("      不限本校园网、不限本机、不需要 VPN。地址是随机发的（不易猜），")
    Write-Host ("      而**随机不等于鉴权** —— 它一旦被转发到群里，就等于公开。")
    Write-Host ("        " + $PublicUrl)
    Write-Host ("   ② **演示口令是公开的**：它的唯一所有者是 backend\scripts\demo_bootstrap.py 的")
    Write-Host ("      DEMO_PASSWORD（也写在 spec §13），本文件刻意**不抄一份字面量**在这里。")
    Write-Host ("      ⇒ 任何打开这条链接的人都能登进**任何一个**在册学号 / 工号（含管理员）。")
    Write-Host ("   ③ 未绑定的账号可以被**抢绑**（spec §1.2 第 4 条）：绑定材料是「学号 + 姓名」，")
    Write-Host ("      两样都在公开的名册里 ⇒ 陌生人可以把别人的账号绑到自己的会话上。")
    Write-Host ("   ④ GET 读操作今天**不留审计**（spec §1.2 第 14 条 / §13.9）：")
    Write-Host ("      谁读了哪个学生的体测 / 体成分 / 处方，事后**查不出来**（只有写入操作留痕）。")
    Write-Host ("   ⑤ **不要录入真实学生信息**：这是一份试用环境，库里 60 名学生均为虚构；")
    Write-Host ("      页面上也挂着同一条告示（frontend\src\App.vue，16 条路由都看得见）。")
    Write-Host ("      真实的健康档案一旦敲进来，它就在公网上、而读它的人查不出来（见 ④）。")
    Write-Host ("   ⑥ **链接的寿命 = 本进程的寿命**：Ctrl-C 停掉本脚本，这个地址立刻失效；")
    Write-Host ("      重跑本脚本会得到一个**全新的随机地址**（旧地址不会复活）。")
    Write-Host ("      ⇒ 发给甲方之前请确认这个终端会一直开着；要长期链接请上 named tunnel + 一个真域名。")
    Write-Host ""

    # -----------------------------------------------------------------------
    # ⑦ 前台阻塞（Ctrl-C 停）
    # -----------------------------------------------------------------------
    Write-Host "-- ⑦ 隧道开着（前台；Ctrl-C 停）--"
    Write-Host ("   给甲方点的那一条 = " + $PublicUrl + "/")
    Write-Host ("   登录页            = " + $PublicUrl + "/login")
    Write-Host ("   存活探针          = " + $RemoteHealthUrl)
    Write-Host ("   URL 文件          = " + $UrlFile)
    Write-Host ("   隧道日志          = " + $LogDir)
    Write-Host "   Ctrl-C 停止。"
    Write-Host ""

    while (-not $Proc.HasExited) {
        Start-Sleep -Seconds 2
        Write-NewTunnelLog -Path $LogFile
    }
    # ⚠️ ``$Proc.Refresh()`` 是承重的：``Start-Process -PassThru`` 给的那个对象
    #    不刷新时 ``ExitCode`` 会是 ``$null``。本机实测过这一格：隧道进程被**外面**
    #    杀掉之后，末尾那一句印出来的是「隧道已停（退出码 ）」—— 一个空格，
    #    而运维真正要知道的是「它是自己死的、还是我停的」。
    $Proc.Refresh()
    $Code = $Proc.ExitCode
    if ($null -eq $Code) { $Code = 1 }
    if ($Code -ne 0) {
        Write-Host ""
        Write-Host ("   ⚠️ 隧道进程是**自己退出**的（退出码 " + $Code + "），不是本脚本停的它")
        Write-Host ("      ⇒ 那条公网链接已经失效。真因在上面那段隧道日志里（也留在 " + $LogDir + "）。")
    }
} finally {
    # ⚠️ 兜住隧道进程：Ctrl-C / throw / 任何一条异常路径都不该留下一个**开着公网入口**的孤儿。
    #    （⚠️ 而「被工具硬杀」那一档 finally 跑不到 ⇒ 第 ① 步那道孤儿清理是它的补网。）
    if ($null -ne $Proc -and -not $Proc.HasExited) {
        Write-Host ""
        Write-Host ("   停掉隧道进程（PID " + $Proc.Id + "）…")
        Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
    }

    # --- 复核归零：进程 -------------------------------------------------------
    Start-Sleep -Milliseconds 800
    $Leftovers = @(Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe' OR Name='ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($LogDirName) })
    Write-Host ""
    if ($Leftovers.Count -eq 0) {
        Write-Host ("   复核 · 隧道进程归零 = ✓ 0 个（判据同 ①：命令行里含本脚本的标记 " + $LogDirName + "）")
    } else {
        $LeftoverPids = (($Leftovers | ForEach-Object { "PID " + $_.ProcessId }) -join '、')
        Write-Host ("   复核 · 隧道进程归零 = ⚠️ 还剩 " + $Leftovers.Count + " 个：" + $LeftoverPids + " → 请手工 Stop-Process -Id <PID> -Force")
    }

    # --- 复核 · 本地服务**不该**被带走 ----------------------------------------
    # ⚠️ 这一格是有意的：隧道死了不该带走服务（两者是两个进程，而运维要能
    #    「只重开隧道、不动服务」—— 那正是本脚本与 trial.ps1 分成两个所有者的理由）。
    try {
        $After = Invoke-WebRequest -Uri $LocalHealth -UseBasicParsing -TimeoutSec 5
        Write-Host ("   复核 · 本地服务 = ✓ 还活着（$LocalHealth → " + [int]$After.StatusCode + "）⇒ 隧道死了**没有**带走服务，重跑本脚本即可拿到一条新链接")
    } catch {
        Write-Host ("   复核 · 本地服务 = ⚠️ 打不通了（$LocalHealth）：它本来不归本脚本管（是 trial.ps1 / serve.ps1 起的），请查那个终端")
    }

    # --- URL 文件：删掉（那条链接已经失效，留着是撒谎）-------------------------
    if (Test-Path $UrlFile) {
        Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue
        Write-Host ("   收尾 · $UrlFile 已删（上面那条链接随隧道进程一起失效了，留一份写着死链接的文件比没有更坏）")
    }
    if (Test-Path $TrialDir) {
        $Remaining = @(Get-ChildItem $TrialDir -Force -ErrorAction SilentlyContinue)
        if ($Remaining.Count -eq 0) {
            Remove-Item $TrialDir -Force -ErrorAction SilentlyContinue
            Write-Host ("   收尾 · $TrialDir 已空 → 目录也删掉（⚠️ 它已进 .gitignore，故留着也不会入库；删掉是为了不留一个空目录）")
        }
    }
    # ⚠️ $LogDir **刻意留着**（与 trial.ps1 删自己那个 CSV 临时目录不同）：
    #    它是「隧道为什么失败」的唯一现场，删掉它等于把下一次排障的证据一起删了。
    #    它按端口命名、每次跑本脚本时自己清空，故不会累积。
    Write-Host ("   隧道日志留着 = " + $LogDir + "（排障用；下一次跑本脚本会清空它）")
}

Write-Host ""
Write-Host ("   隧道已停（退出码 " + $Code + "）。上面那条公网链接现在**已经失效**。")
exit $Code
