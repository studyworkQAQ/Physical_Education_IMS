<#
.SYNOPSIS
    一条命令起**试用档**（Plan 07 Task 1）：灌一份**专用试用库** → 设 ``PE_TRIAL=1``
    → **委托** ``scripts\serve.ps1`` 起产品档。

.DESCRIPTION
    四步：① 两道禁区守卫（``backend\pe.db`` 不得存在、试用库的 URL 不得指向它）
    → ② ``-Reset`` 时删掉旧试用库（**先取证、再查占用**）→ ③ 灌库（库不在才灌；
    走 ``backend\scripts\demo_bootstrap.py``，即 ``demo.ps1`` 用的**同一套**生成器）
    → ④ 设三个环境变量、``powershell -File`` 委托 ``scripts\serve.ps1``。

    ------------------------------------------------------------------------
    ⚠️ 它**不是**第二个服务器启动器
    ------------------------------------------------------------------------
    起 uvicorn、判 ``dist`` 新鲜度、健康检查、打印 URL 与账号、``finally`` 兜住子进程
    ——那些一律是 ``scripts\serve.ps1`` 的活，本文件**一行都不重写**，只在第 ④ 步
    用 ``powershell -File`` 把它叫起来（⚠️ 不用 ``&`` 调用运算符：``serve.ps1`` 末尾
    有一句 ``exit $Code``，而在同一会话里 ``&`` 一个含 ``exit`` 的脚本，退出语义
    在 5.1 上不如另起一个进程清楚；另起一个进程还顺带让 ``$LASTEXITCODE`` 有定义）。
    环境变量是**进程级**的（``$env:``），子进程照继承，故 ``PE_DB_URL`` /
    ``PE_CSV_DIR`` / ``PE_TRIAL`` 三个都由本文件设一次就够。

    ------------------------------------------------------------------------
    ⚠️ 试用库与演示库**分开**：``backend\pe_trial.db``
    ------------------------------------------------------------------------
    ``backend\pe_demo.db`` 既是开发靶子又是演示数据，而 ``frontend\scripts\smoke.mjs``
    一跑就把它写脏（它自己印一段「已经写脏了演示库」）。给甲方点的那一份必须有
    自己的库，于是本文件用 ``backend\pe_trial.db``：
      · ⚠️ 已进 ``.gitignore``（四行：本体 + ``-journal`` / ``-wal`` / ``-shm``，
        照 ``pe_demo.db`` 那一条的姿势；守卫是 ``backend/tests/test_trial.py``）；
      · ⚠️ 它的名字**只有一个所有者**：本文件下面那个 ``$TrialDbName``。
        ``app\main.py`` 里刻意**没有** ``TRIAL_DB_URL`` 常量——Python 侧一个消费者都没有，
        加一个没人读的常量就是硬规矩 #50 说的那种「恒用不到的东西」；
        而「本文件与 ``.gitignore`` 不许漂开」由那条守卫按字面钉住（两侧不同源）。
      · ⚠️ 禁区 ``backend\pe.db`` **仍然不许存在**（它是 ``app.seed.generate`` 写出来的
        那份不可复现的库）；``backend\data\**`` 一字节都不许动，``backend\data\seed\``
        恒为 0 文件。故第 ① 步与第 ⑤ 步各有一道复核，姿势逐字抄 ``demo.ps1`` 的 ⑤
        与 ``serve.ps1`` 的 ③ a（⚠️ **不写第二套判据**）。

    ------------------------------------------------------------------------
    ⚠️ 灌库走 ``demo.ps1`` 的**同一套**生成器，⚠️ 不写第二个灌库器
    ------------------------------------------------------------------------
    实测过 ``demo.ps1`` 是怎么灌的：它调
    ``python scripts/demo_bootstrap.py --db-url <url> --csv-dir <dir> --students N --seed S``
    （**不是** ``app.seed``，也不是那三个禁跑 CLI —— ``app.seed.generate`` /
    ``app.pipeline.backfill`` / ``app.pipeline.daily`` 的 ``main()`` 各自把缺省值写死在
    两个禁区上）。故本文件调**同一个入口**、同一套参数名。
    ⚠️ 而 ``--students`` 与 ``--seed`` **刻意不传**：``demo_bootstrap.py`` 的 argparse
    缺省就是 60 与 20250828（``demo.ps1`` 那两个 ``[int]`` 参数的缺省也是这两个数），
    在本文件里再敲一遍就是第二个所有者。要换人数请直接调 ``demo_bootstrap.py``。
    ⚠️ ``demo_bootstrap.py`` 自带两道前置守卫（``--csv-dir`` 撞上 ``backend\data\seed``
    或 ``--db-url`` 的 basename 是 ``pe.db`` 都当场 ``SystemExit``），故第 ① 步那两道
    是**第三、第四道**，不是唯一的一道。

    ------------------------------------------------------------------------
    ⚠️ 缺省**复用**已有的试用库；``-Reset`` 才删了重灌
    ------------------------------------------------------------------------
    甲方试用一定会写脏它（绑定、打卡、快评、预警处置），而**同一天里反复重跑本脚本
    不该把他们刚敲进去的东西冲掉** —— 那正是「一键重置」要单独做成一个旗标的理由。
    故：库不在 → 灌；库在 → 复用（``init_db`` 会自己 ``upgrade head`` 补 schema，
    故换过版本也照样起得来）；``-Reset`` → 删掉重灌。
    ⚠️ ``-Reset`` **删之前**做两件事：① 打印删的是什么（路径 + 字节数 + sha256[:16]，
    四个后缀逐个）；② 试一次**独占打开**，打不开就说明有进程持有它 —— 那时
    **报一句人话并非 0 退出**，⚠️ 不硬删（前几波踩过「文件被进程占用而
    ``PermissionError``」，而那一句报错离真因有一层）。

.PARAMETER Port
    端口，缺省 **8030**。⚠️ 刻意**不与** ``serve.ps1`` 的 8020、``demo.ps1`` 的 8010、
    vite 的 5173、后端手工演示常用的 8000 撞 —— 于是「试用档与产品档同时在跑、
    两个浏览器窗口对拍」是合法的（``smoke.mjs`` 的第三档正是那么跑的）。

.PARAMETER Lan
    **透传**给 ``scripts\serve.ps1`` 的那个同名旗标（Plan 07 Task 2）：绑 ``0.0.0.0``、
    打印本机全部 LAN IPv4 的 URL、打印一条 ``netsh advfirewall`` 放行命令、
    打印一段明文局域网的响亮告示。⚠️ 本文件**不自己实现**任何一格（不写第二套）。
    ⚠️ 档位留在 **dev**：明文 http 上跑 ``prod`` 会让浏览器拒收 ``Secure`` cookie
    （症状是「登录 200、下一个请求 401」，spec §13.11.3），逐字理由见 ``serve.ps1`` 的
    ``.PARAMETER Lan``。

.PARAMETER Reset
    删掉旧的 ``backend\pe_trial.db``（连同 ``-journal`` / ``-wal`` / ``-shm``）再重灌。
    ⚠️ 删之前的取证与占用检测见上面 ``.DESCRIPTION`` 的最后一段。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\trial.ps1
    # 灌（或复用）backend\pe_trial.db，然后在 http://127.0.0.1:8030 上起试用档（前台，Ctrl-C 停）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\trial.ps1 -Reset -Lan
    # 删掉旧试用库重灌一份干净的，并绑 0.0.0.0 让同一网段的机器也打得开
#>
[CmdletBinding()]
param(
    [int]$Port = 8030,
    [switch]$Lan,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

# ⚠️ 本文件与 serve.ps1 同住**仓库根**的 scripts\ 下（它同时碰 backend\ 与那份脚本），
#    故 .. 是仓库根（与 serve.ps1 逐字同一条口径）。
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $RepoRoot "backend"
$ServePs1 = Join-Path $PSScriptRoot "serve.ps1"

#: 试用库的名字。⚠️ **本文件是它在全仓的唯一所有者**（逐字理由见 .DESCRIPTION）。
$TrialDbName = "pe_trial.db"
$TrialDbPath = Join-Path $Backend $TrialDbName
# ⚠️ URL 的拼法逐字抄 demo.ps1 的 -DryRun 那一支：Windows 的绝对路径要先正斜杠化，
#    而**剥路径**那一侧（如果需要）一律用 sqlalchemy 的 make_url，不做字符串替换。
$TrialDbUrl = "sqlite:///" + ($TrialDbPath -replace '\\', '/')

Write-Host "== 厦大体育数智系统 · 试用档 =="
Write-Host "   repo      = $RepoRoot"
Write-Host "   backend   = $Backend"
Write-Host "   试用库    = $TrialDbPath"
Write-Host "   委托      = $ServePs1（本文件刻意不是第二个服务器启动器）"

# ---------------------------------------------------------------------------
# ① 禁区守卫（姿势逐字抄 serve.ps1 的 ③ a 与 demo.ps1 的 ⑤；⚠️ 不写第二套判据）
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ① 禁区守卫 --"

$ForbiddenDb = Join-Path $Backend "pe.db"
if (Test-Path $ForbiddenDb) {
    throw "禁区：$ForbiddenDb 存在。它**不得存在**（它是 app.seed.generate 写出来的那份不可复现的库）。本脚本一次都不建它，故它是别的进程留下的；请手工删掉再重跑。"
}
# ⚠️ 判据与 serve.ps1 的 ③ a **逐字同形**（同一个正则、同一句人话的形状）：
#    两份各写一套的话，改一处漏一处，而漏掉的那一处是**要交给甲方跑**的那一处。
if ($TrialDbUrl -match '(^|/)pe\.db$') {
    throw ("禁区：试用库的 URL 指向 backend\pe.db（实测 " + $TrialDbUrl + "）。那个文件**不得存在**——请查上面那个 `$TrialDbName`（它是这个名字的唯一所有者）。")
}
Write-Host "   backend\pe.db 不存在 ✓   试用库的 URL 不指向它 ✓（$TrialDbUrl）"

if (-not (Test-Path $ServePs1)) {
    throw "找不到 $ServePs1：本脚本**委托**它起服务（刻意不自己写第二个启动器）。请查仓库根的 scripts\ 目录。"
}

# ---------------------------------------------------------------------------
# ② -Reset：先取证、再查占用、然后才删
# ---------------------------------------------------------------------------
$Sidecars = @("", "-journal", "-wal", "-shm")

if ($Reset) {
    Write-Host ""
    Write-Host "-- ② -Reset：删掉旧试用库 --"

    $Existing = @()
    foreach ($Suffix in $Sidecars) {
        $Candidate = "$TrialDbPath$Suffix"
        if (Test-Path $Candidate) { $Existing += $Candidate }
    }
    if ($Existing.Count -eq 0) {
        Write-Host "   没有旧库可删（$TrialDbPath 与它的三个侧车文件一个都不在）→ 直接灌一份新的"
    } else {
        # --- ② a  删之前**打印删的是什么**（路径 + 字节数 + sha256[:16]）---
        Write-Host ("   删之前先取证（" + $Existing.Count + " 个文件）：")
        foreach ($File in $Existing) {
            $Item = Get-Item $File
            $Digest = (Get-FileHash -Path $File -Algorithm SHA256).Hash.Substring(0, 16)
            Write-Host ("     " + $File + "   " + $Item.Length + " B   sha256[:16]=" + $Digest + "   改于 " + $Item.LastWriteTime)
        }

        # --- ② b  有进程持有它就**不删**（报一句人话、退出非 0）---
        # ⚠️ 判据是一次**独占打开**（FileShare.None）：SQLite 打开库时给的是
        #    FILE_SHARE_READ|WRITE，故一个活着的 uvicorn 会让本尝试抛 IOException。
        #    ⚠️ 刻意**不**用「端口上有没有 listener」当唯一判据：持有这个文件的
        #    也可能是另一个还没起完的 demo_bootstrap.py、或一个开着库的 DB 浏览器。
        $Held = @()
        foreach ($File in $Existing) {
            try {
                $Stream = [System.IO.File]::Open($File, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
                $Stream.Close()
                $Stream.Dispose()
            } catch {
                $Held += $File
            }
        }
        if ($Held.Count -gt 0) {
            $Listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
            $Who = if ($Listeners.Count -gt 0) { "端口 $Port 上的 PID " + ($Listeners[0].OwningProcess) } else { "端口 $Port 上没有 listener，故持有它的是别的进程" }
            Write-Host ""
            Write-Host ("   ⚠️ 删不掉：" + ($Held -join "、") + " 正被别的进程持有（独占打开失败）。")
            Write-Host ("      $Who。")
            Write-Host "      本脚本**不硬删**：在一个还开着的 SQLite 库上删文件，得到的是一份半截的库，"
            Write-Host "      而下一次起服务时 alembic 会在离真因很远的地方炸。"
            Write-Host "      处置：先停掉那个进程（Ctrl-C 掉正在跑的 trial.ps1 / serve.ps1，或 Stop-Process -Id <PID>），再重跑本脚本。"
            exit 1
        }

        # --- ② c  删 ---
        foreach ($File in $Existing) {
            Remove-Item $File -Force
            Write-Host "   删掉 $File"
        }
        foreach ($File in $Existing) {
            if (Test-Path $File) { throw "删不掉 $File（独占打开通过了，却仍然删不掉：权限？）" }
        }
        Write-Host "   复核：四个后缀一个都不在了 ✓"
    }
} else {
    Write-Host ""
    if (Test-Path $TrialDbPath) {
        $Item = Get-Item $TrialDbPath
        Write-Host ("-- ② 复用已有的试用库（" + $Item.Length + " B，改于 " + $Item.LastWriteTime + "）--")
        Write-Host "   ⚠️ 它可能已经被试用者写脏（绑定 / 打卡 / 快评 / 预警处置）。要一份干净的请加 -Reset。"
    } else {
        Write-Host "-- ② 试用库不在 → 下面第 ③ 步灌一份新的 --"
    }
}

# ---------------------------------------------------------------------------
# ③ 灌库（只在库不在时）：走 demo.ps1 用的**同一个** Python 入口
# ---------------------------------------------------------------------------
# ⚠️ CSV 落在 $env:TEMP：backend\data\** 一个字节都不许动，
#    而 backend\data\seed\ 更是恒为 0 文件的禁区（与 demo.ps1 逐字同一条理由）。
$CsvDir = Join-Path $env:TEMP ("pe_trial_csv_" + $PID)

if (-not (Test-Path $TrialDbPath)) {
    Write-Host ""
    Write-Host "-- ③ 灌试用库（backend\scripts\demo_bootstrap.py，与 demo.ps1 同一套生成器）--"
    if (Test-Path $CsvDir) { Remove-Item $CsvDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $CsvDir | Out-Null
    Write-Host "   --db-url  = $TrialDbUrl"
    Write-Host "   --csv-dir = $CsvDir（跑完第 ⑥ 步删掉）"
    Write-Host "   --students / --seed 刻意**不传**：缺省的唯一所有者是 demo_bootstrap.py 的 argparse"
    # ⚠️ 一律以 backend/ 为工作目录：`python scripts/demo_bootstrap.py` 要能 import
    #    到 `app` 包（与 demo.ps1 / serve.ps1 逐字同一条口径）。
    Set-Location $Backend
    python scripts/demo_bootstrap.py --db-url $TrialDbUrl --csv-dir $CsvDir
    if ($LASTEXITCODE -ne 0) { throw "灌库失败（退出码 $LASTEXITCODE），不起服务。上面那段就是原因。" }
    if (-not (Test-Path $TrialDbPath)) { throw "demo_bootstrap.py 退出码 0，而 $TrialDbPath 仍然不在：--db-url 被改过？" }
} else {
    Write-Host ""
    Write-Host "-- ③ 跳过灌库（库已经在；要重灌请加 -Reset）--"
}

# ---------------------------------------------------------------------------
# ④ 禁区复核（照 demo.ps1 的 ⑤：灌完之后再查一次，不只在前面查）
# ---------------------------------------------------------------------------
if (Test-Path $ForbiddenDb) { throw "禁区被写到了：$ForbiddenDb（本文件不该产生它）" }
# ⚠️ -Recurse 是承重的（Plan 03 全分支终审的 M2）：不带它的话，
#    「有人在 data/seed/2025/ 下写了一堆 CSV」这一档会静默通过复核。
$SeedFiles = @(Get-ChildItem (Join-Path $Backend "data\seed") -File -Recurse -ErrorAction SilentlyContinue)
if ($SeedFiles.Count -gt 0) { throw "禁区被写到了：backend\data\seed（应当恒为 0 文件，实测 $($SeedFiles.Count) 个）" }
Write-Host ""
Write-Host "   禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓"

# ---------------------------------------------------------------------------
# ⑤ 设三个环境变量 → 委托 serve.ps1
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ⑤ 委托 scripts\serve.ps1 起试用档 --"

$env:PE_DB_URL = $TrialDbUrl
$env:PE_CSV_DIR = $CsvDir
# ⚠️⚠️ 这一格是**试用档之所以是试用档**的全部机制：
#    · app\deploy.py 的 is_trial() 读它（认不出的值一律 ValueError，故失效方向是
#      「服务起不来」而不是「静默不挂告示」；它只认 "1" 与 "0"）；
#    · GET /api/health 把它作为第四格 `trial` 回给前端；
#    · frontend\src\App.vue 在挂载时读那一格，于是 16 条路由上都挂着那条告示
#      「试用环境 · 数据为高保真仿真（N 名学生均为虚构） · 请勿录入真实学生信息」。
#    ⚠️ 档位**不能写死在前端**：frontend\dist 是同一份构建产物（逐字理由见 App.vue 的文件头）。
$env:PE_TRIAL = "1"
Write-Host "   PE_DB_URL  = $env:PE_DB_URL"
Write-Host "   PE_CSV_DIR = $env:PE_CSV_DIR（临时目录，退出时删）"
Write-Host "   PE_TRIAL   = $env:PE_TRIAL（⇒ is_trial() 为真 ⇒ /api/health 的 trial 一格为 true ⇒ 页面上挂着试用告示）"
Write-Host "   PE_ENV     = $(if ([string]::IsNullOrEmpty($env:PE_ENV)) { '未设（= dev 档；⚠️ 试用档刻意留在 dev：明文 http 上 prod 的 Secure cookie 会被浏览器拒收）' } else { $env:PE_ENV })"
Write-Host "   端口       = $Port（⚠️ 刻意不与 serve.ps1 的 8020 撞，于是两档可以同时起着对拍）"
Write-Host ""
Write-Host "   ⚠️ 下面那一段是 serve.ps1 打的（它做健康检查时会把 /api/health 的响应体原文印出来，"
Write-Host "      那一行里应当能看见 `"trial`":true —— 那就是本档生效的现场证据）。"
Write-Host ""

# ⚠️ 另起一个 powershell 进程（不用 `&` 调用运算符）：serve.ps1 末尾有一句 exit $Code，
#    而另起一个进程让退出码走 $LASTEXITCODE 这条**明确**的路；环境变量是进程级的，
#    子进程照继承，故上面那三个 $env: 不需要再传一遍。
$ServeArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ServePs1, "-Port", "$Port")
if ($Lan) { $ServeArguments += "-Lan" }
Write-Host ("   → powershell " + ($ServeArguments -join " "))
Write-Host ""

$Code = 1
try {
    & powershell @ServeArguments
    $Code = $LASTEXITCODE
} finally {
    # ⚠️ 收尾：那个 CSV 临时目录是本脚本自己造的（demo.ps1 造的叫 pe_demo_csv_*，
    #    它**不**自己删 —— 本文件删自己那一份，不留垃圾在 $env:TEMP 里）。
    if (Test-Path $CsvDir) {
        Remove-Item $CsvDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Host "   收尾：$CsvDir 已删掉（试用库 $TrialDbPath 留着，下次跑本脚本会复用它）"
    }
}

Write-Host ""
Write-Host "   试用档已停（退出码 $Code）。"
exit $Code
