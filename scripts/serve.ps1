<#
.SYNOPSIS
    一条命令起**产品档**（Plan 06 Task 7）：**一个** uvicorn 进程同时服务 ``/api``
    与 ``frontend/dist`` 的构建产物，甲方运维**不需要** ``vite dev server``。

.DESCRIPTION
    五步：① 检查工具链（python ≥ 3.11、node ≥ 20）→ ② 判 ``frontend/dist`` 是不是
    比 ``frontend/src`` 旧，是就跑 ``npm run build`` → ③ 起**一个** uvicorn
    （入口是 ``backend/scripts/serve_app.py``，它读 ``PE_STATIC_DIST`` 之后调
    ``create_app(static_dist=…)``，于是 FastAPI 自己服务静态文件 + SPA fallback）
    → ④ 轮询 ``/api/health`` 直到 200（超时 / 进程先退 → 退出非 0）→ ⑤ 打印 URL、
    演示与管理员账号、以及「这是产品档、不是 dev server」。

    ⚠️ **它是前台阻塞的**（与 ``backend/scripts/demo.ps1`` 同一个姿势）：日志直接打在
    本终端上，``Ctrl-C`` 停。⚠️ 而 ``finally`` 那一段会**兜住子进程**：
    ``Ctrl-C`` / ``throw`` / 任何一条异常路径都会把 uvicorn 停掉，
    不留一个占着端口的孤儿。

    ------------------------------------------------------------------------
    ⚠️ 它**不灌数据**（与 ``demo.ps1`` 的分工）
    ------------------------------------------------------------------------
    要一个能点起来的库，请先跑 ``backend\scripts\demo.ps1``（它灌
    ``backend\pe_demo.db`` 并自带两道禁区守卫），然后跑本脚本。
    本脚本只**服务**那个库：``PE_DB_URL`` 已设就用它，未设就回落到
    ``app.main.DEMO_DB_URL``（= ``backend\pe_demo.db``，⚠️ 那个常量是「演示库叫什么」
    的**唯一所有者**，本文件不在这里敲第二遍路径）。
    ⚠️ **刻意不回落到 ``app.config.DEFAULT_DB_URL``**：那一个逐字指向禁区
    ``backend\pe.db``（它不得存在）。本文件另有一道守卫：解析出来的 URL 以
    ``pe.db`` 结尾就当场 ``throw``——与 ``demo.ps1`` 的 ⑤、``demo_bootstrap.py``
    的两道前置守卫、``backup.py`` 的 ``_ensure_not_forbidden`` 同一条姿势。

    ------------------------------------------------------------------------
    ⚠️ 「dist 比 src 旧」的判据：**mtime**，构建戳是 ``dist\index.html``
    ------------------------------------------------------------------------
    源面 = ``src/**`` 的全部文件 + ``index.html`` / ``package.json`` /
    ``vite.config.ts`` / ``tsconfig*.json`` 五个单文件；构建戳 = ``dist\index.html``
    的 ``LastWriteTimeUtc``（``npm run build`` 一定会写它）。
    **源面里最新的一个 mtime 比构建戳新 → 重建。**

    为什么选 mtime 而不是一个自建的构建戳文件：戳文件是**第二个所有者**
    （它声称的时间与 ``dist`` 里真实产物的时间可以漂），而 mtime 量的就是产物自己。
    ⚠️ 失效方向是**安全**的那一侧：一次 ``git checkout`` 会把被改到的源文件的 mtime
    抬到当下 → 于是「不确定」一律折成「重建」（多花十几秒），
    而**不会**折成「用一份陈的产物」（那一档的症状是「改了前端、页面没变」，
    而它会一路绿到甲方现场）。
    ⚠️ 反空转：源面扫到的文件数 ``< 20`` 就 ``throw``（``frontend/src`` 被搬空或
    路径指错时，``Measure-Object -Maximum`` 会安静地给出一个 ``$null``，
    于是「dist 是新的」会**假绿**）。

.PARAMETER Port
    uvicorn 的端口。⚠️ 缺省 **8020**：与 ``demo.ps1`` 的 8010、vite 的 5173、
    以及后端手工演示常用的 8000 都错开，于是「产品档与 dev 档同时在跑」是合法的
    （``smoke.mjs`` 的产品档变体正是这么跑的：
    ``PE_API_BASE`` 与 ``PE_WEB_BASE`` 都指到本端口，即**同源**）。
    ⚠️ 端口被占着时本脚本**当场**报出占它的那个 PID，而不是让 uvicorn 抛一段
    ``WinError 10048`` 的 traceback（``demo.ps1`` 的文件头逐字记着那一格「离真因有一层」）。

.PARAMETER SkipBuild
    **跳过 ②**（不判新鲜度、不构建），直接用现有的 ``dist``。
    ⚠️ 它**不是**「dist 不存在也照样起」：``dist\index.html`` 不在就 ``throw``
    ——那正是 ``app.static.mount_spa`` 在装配期抛 ``FileNotFoundError`` 的同一档，
    而本脚本提前一步报，省得运维去读一段 Python traceback。
    ⚠️ 用途：连续两次跑本脚本时省掉那十几秒（第一次已经构建过、
    而 ``src`` 一行都没动），以及在**没有** node 的机器上起一个已经构建好的产物。

.PARAMETER Lan
    **局域网档**（Plan 07 Task 2）：把 uvicorn 绑到 ``0.0.0.0`` 而不是缺省的
    ``127.0.0.1``，于是同一个 WiFi / 有线网段里的**别的机器**也打得开。
    ⚠️ **缺省仍然只绑 ``127.0.0.1``，一格都不变**：不加这个旗标时，本脚本的行为
    与 Plan 06 Task 7 交付的那一版逐字相同（守卫是 ``backend/tests/test_serve.py`` 的
    ``test_serve_ps1_binds_loopback_by_default_and_all_interfaces_only_with_lan``）。

    加了它，⑤ 那一步会多打印三样东西：
      ① 本机**全部** LAN IPv4 的 URL（``Get-NetIPAddress`` 现场数，⚠️ 一个都不写死：
         写死一个 ``192.168.x.x`` 等于把「本波实现者的那台机器」焊进交付物，
         而甲方 IT 的机器不是它）；一块网卡都数不到时打印一句人话，
         而不是打印一个空列表；
      ② 一条 ``netsh advfirewall firewall add rule …`` 命令 + 一句为什么要跑它。
         ⚠️ **本脚本不自动改防火墙**：那要管理员权限，而**静默提权不是交付物该有的形状**
         （一次 ``powershell -File serve.ps1 -Lan`` 不该弹出 UAC、更不该在没人看见的
         情况下往系统防火墙上写一条入站放行）；
      ③ 一段**响亮**的告示：这是**明文** http、不要传真实数据、演示口令是公开的、
         任何能连到这个网段的人都打得开。

    ⚠️⚠️ **档位裁定（实施计划 07 §2，本文件不推翻它）**：局域网档必须留在 **``dev``** 档。
    ``prod`` 会开 cookie 的 ``Secure``，而明文 http 上浏览器**拒收** ``Secure`` cookie
    ⇒ 症状是「登录 200、下一个请求 401」（Plan 06 Task 7 论证过，spec §13.11.3）。
    ⚠️ 而 ``-Lan`` 与 ``PE_ENV=prod`` **同时出现**时本脚本**不阻止**、只打印一段 ⚠️：
    「运维在 TLS 反代后面用 ``-Lan`` 绑 ``0.0.0.0``」是一档**合法**形状
    （反代就在同一台机器上，边缘是 HTTPS），``raise`` 会把它一起打死。
    与实施计划 07 Task 3 的隧道档对照：那一档边缘是 HTTPS，故 ``prod`` 成立。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\serve.ps1
    # 需要时构建，然后在 http://127.0.0.1:8020 上起产品档（前台，Ctrl-C 停）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Lan
    # 绑 0.0.0.0：打印本机全部 LAN IPv4 的 URL + 一条 netsh 放行命令 + 一段明文告示
    #   （⚠️ 档位留在 dev；要 ``prod`` 请先有一层 TLS 反代，见 .PARAMETER Lan）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Port 8021 -SkipBuild
    # 换一个端口、不重建（dist 必须已经在）

.EXAMPLE
    $env:PE_ENV = "prod"; $env:PE_CORS_ORIGINS = "https://pe.xmu.edu.cn"
    powershell -ExecutionPolicy Bypass -File scripts\serve.ps1
    # ⚠️ 生产档由**运维自己设环境变量**，本脚本刻意**没有** ``-Prod`` 开关
    #   （理由见下面 ⑤ 那一段打印的原文）。
#>
[CmdletBinding()]
param(
    [int]$Port = 8020,
    [switch]$SkipBuild,
    [switch]$Lan
)

$ErrorActionPreference = "Stop"

# ⚠️ 本文件住在**仓库根**的 scripts\ 下（与 backend\scripts\ 区分：那一层是后端自己的
#    三个脚本，本文件是**跨包**的——它同时碰 frontend\ 与 backend\），故 .. 是仓库根。
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"
$Dist = Join-Path $Frontend "dist"
$DistIndex = Join-Path $Dist "index.html"
$Base = "http://127.0.0.1:$Port"

# ⚠️ **绑定地址**（Plan 07 Task 2）。⚠️ 缺省逐字仍是 ``127.0.0.1``：
#    不加 ``-Lan`` 时本脚本与 Plan 06 Task 7 那一版**一格都不变**（连这一行的取值都不变），
#    守卫是 ``backend/tests/test_serve.py`` 的
#    ``test_serve_ps1_binds_loopback_by_default_and_all_interfaces_only_with_lan``。
#    ⚠️ 变量名刻意**不是** ``$Host``：那是 PowerShell 的自动变量（``$Host.UI`` 一类），
#    给它赋值在 5.1 上是一句 ``Cannot overwrite variable Host because it is read-only or constant``。
#    ⚠️ 而健康检查（④）与 ⑤ 那一段打印的 ``$Base`` **一律仍是 127.0.0.1**：
#    绑 ``0.0.0.0`` 的进程在回环上照样可达，故「本机自检」这一格两档同形；
#    局域网那几个 URL 是 ⑤ 里**另算**的（它要现场数网卡，不能靠 ``$Base``）。
$BindAddress = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }

# 健康检查的超时（秒）。⚠️ 它盖得住两件事：uvicorn 起来（约 1 秒）与
# ``init_db`` 走一遍 alembic 迁移链（一个空库上实测约 1 秒，一个要 ``upgrade head``
# 的旧库上更久）。60 秒是给「机器很慢 / 库很大」留的余量，而超时的那一句
# 报错会说清是**哪一格**没通。
$HealthTimeoutSeconds = 60

Write-Host "== 厦大体育数智系统 · 产品档 =="
Write-Host "   repo     = $RepoRoot"
Write-Host "   backend  = $Backend"
Write-Host "   frontend = $Frontend"

# ---------------------------------------------------------------------------
# ① 检查工具链
# ---------------------------------------------------------------------------
# ⚠️ 报**可读的错**而不是让 uvicorn / npm 在很远的地方炸：本机没有 venv，
#    ``python`` 可能是 Microsoft Store 的那个占位符（它会打开商店、退出码 9009），
#    而 ``node`` 缺失时 ``npm run build`` 的报错是「'npm' 不是内部或外部命令」。
Write-Host ""
Write-Host "-- ① 检查工具链 --"

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrEmpty($PythonExe)) {
    throw "找不到 python：本系统要 Python 3.11 或更新（pyproject.toml 的 requires-python）。请装它、或把它加进 PATH。"
}
$PythonBanner = (& $PythonExe --version)
if ($LASTEXITCODE -ne 0) { throw "python --version 失败（退出码 $LASTEXITCODE）：$PythonExe 可能不是一个真的解释器（Microsoft Store 的占位符就是这一档）" }
$PythonParts = ($PythonBanner -replace '^[^0-9]*', '').Split('.')
$PythonMajor = [int]$PythonParts[0]
$PythonMinor = [int]$PythonParts[1]
if (($PythonMajor * 100 + $PythonMinor) -lt 311) {
    throw "Python 版本不够：实测 $PythonBanner（$PythonExe），要 3.11 或更新（pyproject.toml 的 requires-python）"
}
Write-Host "   python $PythonBanner  ← $PythonExe"

$NodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrEmpty($NodeExe)) {
    throw "找不到 node：构建前端要 Node 20 或更新（vite 8 的下限）。请装它、或把它加进 PATH；已经有一份构建好的 dist 的话可以加 -SkipBuild。"
}
$NodeBanner = (& $NodeExe --version)
$NodeMajor = [int](($NodeBanner -replace '^[^0-9]*', '').Split('.')[0])
if ($NodeMajor -lt 20) {
    throw "Node 版本不够：实测 $NodeBanner（$NodeExe），要 20 或更新（vite 8 的下限）"
}
Write-Host "   node   $NodeBanner  ← $NodeExe"

# ---------------------------------------------------------------------------
# ② 前端构建产物：不存在 / 比 src 旧 → npm run build
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ② 前端构建产物 --"

$NeedBuild = $false
if (-not (Test-Path $DistIndex)) {
    if ($SkipBuild) {
        throw "-SkipBuild 要求 dist 已经在：缺 $DistIndex。请去掉 -SkipBuild 让本脚本自己构建一次。"
    }
    $NeedBuild = $true
    Write-Host "   缺 $DistIndex → 要构建"
} elseif ($SkipBuild) {
    Write-Host "   -SkipBuild：不判新鲜度，直接用现有的 dist（构建戳 $((Get-Item $DistIndex).LastWriteTime)）"
} else {
    # ⚠️ 源面与构建戳的取法逐字写在 .PARAMETER 上面那一段（-SkipBuild 的说明之前）。
    $SourceRoots = @(
        (Join-Path $Frontend "src"),
        (Join-Path $Frontend "index.html"),
        (Join-Path $Frontend "package.json"),
        (Join-Path $Frontend "vite.config.ts"),
        (Join-Path $Frontend "tsconfig.json"),
        (Join-Path $Frontend "tsconfig.app.json"),
        (Join-Path $Frontend "tsconfig.node.json")
    )
    $Sources = @()
    foreach ($Root in $SourceRoots) {
        if (Test-Path $Root -PathType Container) { $Sources += @(Get-ChildItem $Root -Recurse -File) }
        elseif (Test-Path $Root -PathType Leaf) { $Sources += @(Get-Item $Root) }
    }
    # ⚠️ 反空转（硬规矩 #50）：源面被搬空 / 路径指错时 $Newest 会是 $null，
    #    而 `$null -gt $Stamp` 为假 → 「dist 是新的」会**假绿**、于是一份陈产物
    #    被当成产品档发给甲方。
    if ($Sources.Count -lt 20) {
        throw "源面只扫到 $($Sources.Count) 个文件（要 ≥ 20）：$Frontend 可能被搬空或路径指错了，本脚本不敢断言 dist 是新的"
    }
    $Stamp = (Get-Item $DistIndex).LastWriteTimeUtc
    $Newest = ($Sources | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    $NewestFile = ($Sources | Where-Object { $_.LastWriteTimeUtc -eq $Newest } | Select-Object -First 1).FullName
    Write-Host ("   源面 {0} 个文件，最新 mtime = {1:yyyy-MM-dd HH:mm:ss}（{2}）" -f $Sources.Count, $Newest.ToLocalTime(), $NewestFile)
    Write-Host ("   构建戳 dist\index.html     = {0:yyyy-MM-dd HH:mm:ss}" -f $Stamp.ToLocalTime())
    if ($Newest -gt $Stamp) {
        $NeedBuild = $true
        Write-Host "   源面比构建戳**新** → 要构建"
    } else {
        Write-Host "   dist 不比 src 旧 → 跳过构建"
    }
}

if ($NeedBuild) {
    $NpmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrEmpty($NpmExe)) {
        throw "找不到 npm.cmd：构建前端要它（node 在 $NodeExe，而 npm 不在 PATH 上？）"
    }
    Write-Host ""
    Write-Host "-- ② b  npm run build（vue-tsc -b + vite build）--"
    Set-Location $Frontend
    & $NpmExe run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build 失败（退出码 $LASTEXITCODE），不起服务。上面那段就是原因；最常见的一档是 vue-tsc 的类型错误。" }
    if (-not (Test-Path $DistIndex)) { throw "npm run build 退出码 0，而 $DistIndex 仍然不在：vite 的 outDir 被改过？" }
    Write-Host "   构建完成 → $Dist"
}

# ---------------------------------------------------------------------------
# ③ 起一个 uvicorn 进程（前台；Ctrl-C 停）
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ③ 起产品档 --"

# ⚠️ 一律以 backend/ 为工作目录：`python -m uvicorn` 把 CWD 放进 sys.path，
#    而 `app` 包在 backend/ 下（与 demo.ps1 / backup.ps1 同一条口径）。
Set-Location $Backend

# --- ③ a  库：PE_DB_URL > app.main.DEMO_DB_URL，且**永不**是禁区的 pe.db -------
if ([string]::IsNullOrEmpty($env:PE_DB_URL)) {
    $Probed = (& $PythonExe -c 'from app.main import DEMO_DB_URL;print(DEMO_DB_URL)')
    if ($LASTEXITCODE -ne 0) { throw "读不出 app.main.DEMO_DB_URL（Python 依赖有问题？）：$Probed" }
    $env:PE_DB_URL = ($Probed | Select-Object -Last 1).ToString().Trim()
    Write-Host "   PE_DB_URL 未设 → 回落到 app.main.DEMO_DB_URL（那个常量是「演示库叫什么」的唯一所有者）"
}
if ($env:PE_DB_URL -match '(^|/)pe\.db$') {
    throw ("禁区：PE_DB_URL 指向 backend\pe.db（实测 " + $env:PE_DB_URL + "）。那个文件**不得存在**——它是 app.seed.generate 写出来的那份不可复现的库。要演示数据请先跑 backend\scripts\demo.ps1，或把 PE_DB_URL 指到别的库。")
}
Write-Host "   PE_DB_URL       = $env:PE_DB_URL"

# --- ③ b  产物目录：serve_app.py 只认这一个环境变量 --------------------------
# ⚠️ `frontend\dist` 的绝对路径**只在本文件里算一次**：serve_app.py 刻意不知道
#    仓库长什么样（tests/test_serve.py 的
#    test_the_entry_module_is_utf8_without_bom_and_never_names_the_dist_directory
#    把那一格钉住了），于是「产物在哪」只有一个所有者。
$env:PE_STATIC_DIST = $Dist
Write-Host "   PE_STATIC_DIST  = $env:PE_STATIC_DIST"
Write-Host "   PE_ENV          = $(if ([string]::IsNullOrEmpty($env:PE_ENV)) { '未设（= dev 档）' } else { $env:PE_ENV })"
# --- ③ b2  请求头身份通道：**强制关**（Plan 06 Task 11 / B3，与 demo.ps1 逐字同一段）----
# ⚠️⚠️ 本处此前只**打印**实测值 + 一句 ⚠️（原文逐字是「生产档（PE_ENV=prod）下
#    app.api.deps 一律忽略它；本脚本**不**替你清掉它（与 demo.ps1 不同：那一个是演示、
#    必须强制关；本脚本是部署入口，开关归运维）」）。控制者于 Plan 06 Task 11 改判为
#    「serve.ps1 也强制清」，实现者复核后**同意**，逐字理由：
#      · 产品档是**交付给甲方运维跑的那一档**，而它**缺省留在 dev 档**（Task 7 的裁定：
#        同源 http 上跑 prod 档，浏览器会拒收 Secure cookie，症状是「登录 200、
#        下一个请求 401」，见 ⑤ 那一段的原文）。
#      · 于是「dev 档 + 运维不小心设了 PE_ALLOW_HEADER_IDENTITY」= **请求头身份通道开着**，
#        而那一档是**绕过整个鉴权**的：X-Student-Id / X-Teacher-Staff-No 没有签名、
#        没有过期、没有吊销 ⇒ 任何人都可以自称任何学号（含管理员那个工号 T0003）。
#      · ⚠️ 生产档（PE_ENV=prod）下 app.api.deps 一律忽略它，故那一档是安全的 ——
#        而**安全的不是本脚本缺省的那一档**。改前那一句「开关归运维」把一档
#        「绕过整个鉴权」的开关交出去了，而它换来的只是「内网调试时少设一次环境变量」。
#    ⚠️ **不给开关**（控制者裁定，实现者同意，⚠️ 顶回派单 §2 B3 第 ③ 条问的那一格）：
#      产品档就是产品档。要一个认请求头的**开发档**，请在另一个终端里
#      `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 再手工起 uvicorn（demo.ps1 的注释里
#      逐字写着那一格；`$env:` 是进程级的，不写注册表、也不留给下一个终端）。
#      ⚠️ 而本脚本会强制清掉它，故「靠 serve.ps1 起一个认请求头的后端」是行不通的。
# ⚠️⚠️ **下面那一段是从 backend\scripts\demo.ps1 逐字抄过来的**（那一段是这个开关的
#    单一所有者；⚠️ 不写第二套：两份的话，改一处漏一处，而漏掉的那一处是**产品档**）。
#    守卫是 tests/test_serve.py 的
#    test_serve_ps1_force_clears_the_header_identity_channel_with_the_same_lines_demo_ps1_uses
#    ——它**从 demo.ps1 里现场切出那一段**、再断言本文件里逐字有它，
#    故「两份漂了」当场红（⚠️ 两侧不同源：期望侧是 demo.ps1 的文件内容，不是本文件的）。
$HeaderIdentityInherited = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY -ErrorAction SilentlyContinue
$HeaderIdentityNow = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
if (-not [string]::IsNullOrEmpty($HeaderIdentityNow)) {
    throw ("PE_ALLOW_HEADER_IDENTITY 删不掉（本进程实测仍是 " + $HeaderIdentityNow + "）：本脚本一律以生产缺省 0 起 uvicorn（只认 pe_session cookie）。请手工清掉它再重跑。")
}
# ⚠️ 打印的是「进本脚本时实测到什么」+「本脚本把它变成了什么」两格，不是一句写死的「未设」。
$HeaderIdentityShown = if ([string]::IsNullOrEmpty($HeaderIdentityInherited)) { '未设' } else { '=' + $HeaderIdentityInherited }
$HeaderIdentityNowShown = if ([string]::IsNullOrEmpty($HeaderIdentityNow)) { '未设' } else { '=' + $HeaderIdentityNow }
Write-Host "   PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 $HeaderIdentityShown → 本进程已**强制**清成 $HeaderIdentityNowShown（= 生产缺省 `"0`"：只认 pe_session cookie；⚠️ 请求头身份通道**已关闭**）"

# --- ③ c  档位自检：PE_ENV 认不出的话，uvicorn 会在很远的地方抛 ----------------
$TierProbe = (& $PythonExe -c 'from app import deploy;from app.auth.sessions import cookie_secure;print(deploy.tier());print(cookie_secure())')
if ($LASTEXITCODE -ne 0) { throw "读不出部署档位：$TierProbe（PE_ENV 认不出的值会让 app.deploy.tier() 抛 ValueError，而 uvicorn 只会给你一段 traceback）" }
$Tier = ($TierProbe | Select-Object -First 1).ToString().Trim()
$CookieSecure = ($TierProbe | Select-Object -Last 1).ToString().Trim()
Write-Host "   档位            = $Tier（cookie 的 Secure = $CookieSecure）"

# --- ③ d  端口：被占着就报出那个 PID，不要让 uvicorn 抛 WinError 10048 ----------
$InUse = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($InUse.Count -gt 0) {
    throw "端口 $Port 已经被占着（PID $($InUse[0].OwningProcess)）：换一个 -Port，或先停掉那个进程。"
}

# --- ③ e  起进程 -------------------------------------------------------------
# ⚠️ 用 Start-Process 而不是直接 `python -m uvicorn`：④ 那一步的健康检查必须
#    **在**服务起来之后、而脚本又要**前台阻塞**（控制者裁定：与 demo.ps1 同姿势，
#    运维看得见日志）。直接调 python 的话这两件事不可兼得。
#    ⚠️ -NoNewWindow 是承重的：子进程因此与本脚本**共用同一个控制台**，
#    于是 uvicorn 的日志照常打在屏幕上，而 Ctrl-C 也会同时送到两边。
$Arguments = @(
    "-m", "uvicorn", "serve_app:app",
    "--app-dir", (Join-Path $Backend "scripts"),
    "--host", $BindAddress,
    "--port", "$Port"
)
Write-Host "   uvicorn         serve_app:app --app-dir backend\scripts --host $BindAddress --port $Port"
Write-Host "   绑定            $BindAddress（$(if ($Lan) { '-Lan：本机全部网卡，同一网段的别的机器打得开' } else { '缺省：只有本机能连' })）"
Write-Host ""

$Proc = $null
$Code = 0
try {
    $Proc = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory $Backend -PassThru -NoNewWindow
    Write-Host "   进程 PID = $($Proc.Id)"

    # -----------------------------------------------------------------------
    # ④ 健康检查：轮询 /api/health 直到 200
    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- ④ 健康检查 --"
    $Deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $HealthBody = $null
    $Tries = 0
    while ((Get-Date) -lt $Deadline) {
        Start-Sleep -Milliseconds 250
        $Tries += 1
        if ($Proc.HasExited) { break }
        try {
            $Probe = Invoke-WebRequest -Uri "$Base/api/health" -UseBasicParsing -TimeoutSec 2
            if ($Probe.StatusCode -eq 200) { $HealthBody = $Probe.Content; break }
        } catch {
            # 还没监听 / 还没建完表：继续轮询。⚠️ 刻意**不**打印每一次失败——
            # 60 秒 ×4 次/秒 = 240 行噪音，而真因（进程退了 / 超时）在下面两句里。
        }
    }
    if ($null -eq $HealthBody) {
        if ($Proc.HasExited) {
            throw "uvicorn 在健康检查通过之前就退出了（PID $($Proc.Id)，退出码 $($Proc.ExitCode)，轮询了 $Tries 次）：上面那段日志就是原因。最常见的一档是 PE_STATIC_DIST 指的目录里没有 index.html，或 PE_DB_URL 指到了一个建不出来的库。"
        }
        throw "健康检查超时：$HealthTimeoutSeconds 秒内 $Base/api/health 没有回 200（轮询了 $Tries 次，进程 PID $($Proc.Id) 还活着）。请查上面那段 uvicorn 日志。"
    }
    $Health = ($HealthBody | ConvertFrom-Json)
    Write-Host "   $Base/api/health → 200（轮询 $Tries 次）"
    Write-Host ('   ' + $HealthBody)
    Write-Host "   tables = $($Health.tables)（⚠️ health 数的是 Base.metadata，磁盘上另有 alembic_version 一张，故 sqlite3 里数出来是 +1）"

    # -----------------------------------------------------------------------
    # ⑤ 打印
    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- ⑤ 产品档起着（前台；Ctrl-C 停）--"
    Write-Host "   前端 + API      $Base/"
    Write-Host "   存活探针        $Base/api/health"
    Write-Host "   Swagger UI      $Base/docs"
    Write-Host "   OpenAPI JSON    $Base/openapi.json"
    Write-Host ""
    Write-Host "   ⚠️⚠️ 这是**产品档**：一个 uvicorn 进程同时服务 /api 与 frontend\dist 的构建产物"
    Write-Host "      （含 SPA fallback：/login、/s/*、/t/*、/admin/* 的深链接一律回 index.html），"
    Write-Host "      **不是** vite dev server（5173）。前端跑的是 npm run build 出来的静态文件，"
    Write-Host "      改一行 src\ 要重跑本脚本（它会自己判 dist 是不是比 src 旧，或加 -SkipBuild 强制用现有的）。"
    Write-Host "      ⚠️ 同源 ⇒ cookie 不跨端口，前端 src\api\client.ts 的 baseURL 是空串（= 同源），"
    Write-Host "         故本档**不需要** CORS，也不需要 PE_CORS_ORIGINS。"
    Write-Host ""
    Write-Host "   ⚠️ 本脚本**不灌数据**（那是 backend\scripts\demo.ps1 的活）。演示账号："
    Write-Host "      学生     任何一个在册学号（demo.ps1 的 [6/7] 会从库里打印一个**真**例子）"
    Write-Host "      教师     T0001 / T0002（role='teacher'）"
    Write-Host "      管理员   T0003（role='admin'；管理台 23 个资源的增删改查**仅**它可写）"
    Write-Host "      口令     本文件**刻意不抄一份字面量**在这里：唯一所有者是"
    Write-Host "               backend\scripts\demo_bootstrap.py 的 DEMO_PASSWORD（也写在 spec §13）。"
    Write-Host "               ⚠️ 抄第二份的话，改口令的人会漏改一处，而漏改的那一处是**要念给甲方听的**那一处。"
    Write-Host "      库       $env:PE_DB_URL"
    Write-Host ""
    Write-Host "   ⚠️ 当前档位 = $Tier（cookie 的 Secure = $CookieSecure）。"
    Write-Host "      要上 HTTPS 反代请设 PE_ENV=prod 与 PE_CORS_ORIGINS（本脚本刻意**没有** -Prod 开关："
    Write-Host "      档位是**部署事实**、归运维的环境变量，不是一个命令行旗标——一个 `-Prod` 会让人以为"
    Write-Host "      「加了它就安全了」，而它其实还要 PE_CORS_ORIGINS、Secure cookie 与一层 TLS 反代）。"
    Write-Host "      ⚠️ Secure 只在 prod 开，故在**明文 http** 上跑 prod 档，浏览器会拒收会话 cookie"
    Write-Host "         （症状是「登录 200、下一个请求 401」）。同源 http 的产品档请留在缺省的 dev 档。"
    Write-Host ""
    # -----------------------------------------------------------------------
    # ⑤ b  -Lan：局域网 URL + 防火墙命令 + 两段告示（Plan 07 Task 2）
    # -----------------------------------------------------------------------
    # ⚠️ 整块**只在 -Lan 下打印**：缺省档（只绑 127.0.0.1）的输出与 Plan 06 Task 7
    #    交付的那一版**逐字相同**，一个字节都不多（守卫是 backend/tests/test_serve.py 的
    #    test_serve_ps1_binds_loopback_by_default_and_all_interfaces_only_with_lan）。
    # ⚠️ 下面那些 URL 与那条 netsh 命令一律用**单引号串 + 拼接**，不用双引号串里的
    #    反引号转义 —— 与 backend/scripts/demo.ps1 那一段「8 条要点通的 URL」同一条姿势
    #    （单引号串不插值、也不需要转义 `"`，而 netsh 与 URL 里两种字符都可能出现）。
    if ($Lan) {
        Write-Host ""
        Write-Host "   ⚠️⚠️⚠️ -Lan：本进程绑在 $BindAddress 上，**同一个网段里的任何人都打得开**"
        Write-Host "      · 这是**明文 http**：口令、pe_session cookie、学生姓名与体测数据在网线上都是明文。"
        Write-Host "      · **不要传真实数据**：局域网试用请一律用仿真库（backend\scripts\demo.ps1 灌的那一份，"
        Write-Host "        或 scripts\trial.ps1 灌的试用库）。要上真数据请先有一层 TLS 反代。"
        Write-Host "      · 演示口令是**公开的**：它的唯一所有者是 backend\scripts\demo_bootstrap.py 的"
        Write-Host "        DEMO_PASSWORD（也写在 spec §13），本文件刻意**不抄一份字面量**在这里。"
        Write-Host "      · 未绑定的账号可以被**抢绑**（spec §1.2 第 4 条），而 GET 读操作今天**不留审计**"
        Write-Host "        （spec §1.2 第 14 条 / §13.9）：谁读过什么，事后查不出来。"
        Write-Host ""

        # --- 本机**全部** LAN IPv4：现场数，⚠️ 一个都不写死 -------------------------
        # ⚠️ 过滤掉 127.*（回环，别人打不开）与 169.254.*（APIPA 自动私有地址：
        #    DHCP 没给到地址时 Windows 自己挑的，它**不在**任何可路由的网段上）。
        # ⚠️ 刻意**不**写死一个 192.168.x.x：那是本波实现者那台机器今天的地址，
        #    甲方 IT 的机器不是它 —— 写死等于让脚本在交付现场**撒一个看得见的谎**。
        $LanAddresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' })
        if ($LanAddresses.Count -eq 0) {
            # ⚠️ 一块网卡都没有时**报一句人话**，而不是打印一个空列表：
            #    一个空的「局域网链接：」小节读起来像脚本坏了，而真因在网卡上。
            Write-Host "      ⚠️ 本机**一块可用的 IPv4 网卡都没数到**（过滤掉 127.* 与 169.254.* 之后是空的）。"
            Write-Host "         常见原因：断网 / 网卡被禁用 / 只拿到一个 169.254.* 的自动私有地址。"
            Write-Host "         本进程仍然绑在 $BindAddress 上、**本机**照旧打得开（$Base/），而别的机器打不开。"
            Write-Host "         自查：Get-NetIPAddress -AddressFamily IPv4 | Format-Table IPAddress, InterfaceAlias"
        } else {
            Write-Host ('      局域网链接（本机数到 ' + $LanAddresses.Count + ' 个 IPv4 地址）：')
            foreach ($Address in $LanAddresses) {
                Write-Host ('        http://' + $Address.IPAddress + ':' + $Port + '/        ← ' + $Address.InterfaceAlias)
            }
            Write-Host "      ⚠️ 上面这些 URL **只在同一个网段里有效**，而地址通常是 DHCP 给的："
            Write-Host "         换一次网络、或路由器重新分配一次，它们就变了（本脚本每次现场数，故不会撒谎）。"
        }
        Write-Host ""

        # --- 防火墙：打印命令 + 一句为什么，⚠️ 不自动改 ------------------------------
        Write-Host "      防火墙：Windows 缺省**会挡住**从别的机器进来的连接（「本机打得开、同事打不开」就是这一档）。"
        Write-Host "      请以**管理员**身份跑一次下面这一条（端口用的是本进程的 $Port，⚠️ 不写死）："
        Write-Host ('        netsh advfirewall firewall add rule name=XMU-PE-IMS-TCP-' + $Port + ' dir=in action=allow protocol=TCP localport=' + $Port)
        Write-Host "      ⚠️ 为什么是这一条：它只放行**这一个 TCP 端口的入站**（dir=in / protocol=TCP / localport=$Port），"
        Write-Host "         不动出站、不放开别的端口、也不建一个「全允许」的规则；而它的名字里带着端口号，"
        Write-Host "         于是试用结束之后删得掉："
        Write-Host ('        netsh advfirewall firewall delete rule name=XMU-PE-IMS-TCP-' + $Port)
        Write-Host "      ⚠️ 本脚本**不自动改防火墙**：那要管理员权限，而**静默提权不是交付物该有的形状**"
        Write-Host "         （一次 -File serve.ps1 -Lan 不该弹出 UAC，更不该在没人看见的情况下往系统防火墙上写一条入站放行）。"
        Write-Host ""

        # --- -Lan 与 PE_ENV=prod 同时出现：⚠️ 不阻止，只说清后果 ----------------------
        # ⚠️ 控制者裁定「不 raise」，实现者复核后同意：「TLS 反代就在同一台机器上、
        #    反代再转发到 0.0.0.0:<port>」是一档**合法**形状（边缘是 HTTPS，故 Secure
        #    cookie 成立），raise 会把它一起打死。与实施计划 07 Task 3 的隧道档对照：
        #    那一档边缘也是 HTTPS，故 prod 成立。
        if ($Tier -eq 'prod') {
            Write-Host "   ⚠️⚠️⚠️ -Lan 与 PE_ENV=prod **同时**出现（实测档位 $Tier，cookie 的 Secure = $CookieSecure）："
            Write-Host "      明文 http + Secure cookie ⇒ **浏览器拒收那张 cookie**，症状是「登录 200、下一个请求 401」"
            Write-Host "      ——即上面那些局域网 URL 点开之后**登不进去**。本脚本**不阻止**这一档，处置二选一："
            Write-Host "        · 只是局域网明文试用 → 去掉 PE_ENV（回到缺省的 dev 档），或去掉 -Lan；"
            Write-Host "        · 真要上生产 → 前面挂一层 TLS 反代并设 PE_CORS_ORIGINS（那时 -Lan 绑 0.0.0.0 是合法的）。"
            Write-Host ""
        }
    }

    Write-Host "   Ctrl-C 停止。"
    Write-Host ""

    $Proc.WaitForExit()
    $Code = $Proc.ExitCode
} finally {
    # ⚠️ 兜住子进程：Ctrl-C / throw / WaitForExit 被打断，任何一条路径都不该留下
    #    一个占着 $Port 的孤儿 uvicorn（下一个人撞上去时看到的是一句 WinError 10048）。
    if ($null -ne $Proc -and -not $Proc.HasExited) {
        Write-Host ""
        Write-Host "   停掉 uvicorn（PID $($Proc.Id)）…"
        Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "   产品档已停（退出码 $Code）。"
exit $Code
