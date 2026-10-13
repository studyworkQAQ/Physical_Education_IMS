<#
.SYNOPSIS
    一条命令把「厦大体育数智系统」跑起来（Plan 03 Task 9）。

.DESCRIPTION
    五步：① 删掉旧的演示库 → ② 把 ``PE_DB_URL`` / ``PE_CSV_DIR`` 指到演示位置 →
    ③ 灌数据（``scripts/demo_bootstrap.py``：组织结构 + 一学期体测 CSV + 反馈三源 +
    **两次**每日批处理，理由见那个脚本的模块 docstring 第四节）→ ④ 复核两个禁区
    没被写到 → ⑤ 起 uvicorn 并打印 URL。

    ⚠️ **它写的是 ``backend/pe_demo.db``、不是 ``backend/pe.db``**：后者是本仓禁区
    （``app.config.DEFAULT_DB_URL`` 指的就是它，语义是「``app.seed.generate`` 写出来的
    那份不可复现的库」，**不得存在**）。演示库的 URL 从 ``app.main.DEMO_DB_URL`` 读出来、
    **不在本文件里敲第二遍路径**（那是第二个所有者），并已进 ``.gitignore``。

    ⚠️ **第一步仍然删旧库，但理由自 Plan 06 Task 1 起换了**：改前 ``init_db`` 走
    ``Base.metadata.create_all``，对已存在的表原样跳过、不会补新增的 NOT NULL 列，
    端点会在离真因很远的地方 500（Plan 03 Task 2 撞过一次，那次是
    ``training_log.submitted_at``）。**现在 ``init_db`` 走 alembic 迁移链**
    （``backend/migrations/``），旧库会被 ``upgrade head`` 补齐，那一档已经不存在了。
    删旧库的理由换成了「**演示必须可复现**」：下面 ④ 那一步打印的各表行数、以及
    ``demo_bootstrap.py`` 的 [6/7] 从库里取的那个**真**学号，都是演示时**要念给甲方听的**，
    而它们只有在「库是从零灌出来的」时候才是同一组数。
    ⚠️ **生产上不要删库**：甲方现场那份库里是一学期的真实数据。升级版本走迁移链
    （``init_db`` 会自己 ``upgrade head``），改模型的流程见 spec §13.7。

    ⚠️ **一条 ``python -m …`` 都没有**：``app.seed.generate`` / ``app.pipeline.backfill`` /
    ``app.pipeline.daily`` 三个 CLI 的 ``main()`` 各自把缺省值写死在**两个禁区**上
    （``backend/data/seed/`` 与 ``backend/pe.db``）。故本脚本一律调
    ``scripts/demo_bootstrap.py``，那里面是 import 函数 + 显式传路径，
    并且**自带两道前置守卫**（``--csv-dir`` 撞上 ``backend/data/seed`` 或
    ``--db-url`` 以 ``pe.db`` 结尾都当场 ``SystemExit``）。

.PARAMETER Port
    uvicorn 的端口。⚠️ 缺省 **8010** 而不是 8000：8000 常常已经被别的进程占着
    （例如另一次演示），而 uvicorn 撞端口时的报错离真因有一层。

.PARAMETER Students
    演示库的人数。60 人实测约 3 秒灌完；500 人是 ``app.seed.config`` 的分布定标口径、
    灌一次约 20 秒，要跑「分层分布落在 20/45/35 的 ±5 pp 内」那一档才需要它。

.PARAMETER DryRun
    **只灌数据、不起服务，且一个文件都不留在 ``backend/`` 下**（库与 CSV 都落在
    ``$env:TEMP`` 的一个子目录里，跑完删掉）。给 CI 用：它证明这条链跑得通，
    而不需要有人去 ``Ctrl-C`` 一个前台的 uvicorn。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1
    # 灌 backend\pe_demo.db，然后在 http://127.0.0.1:8010 上起服务（前台，Ctrl-C 停）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -DryRun
    # 只灌一个临时库并打印各表行数，退出码 0 = 这条链跑得通；不留任何文件
#>
[CmdletBinding()]
param(
    [int]$Port = 8010,
    [int]$Students = 60,
    [int]$Seed = 20250828,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ⚠️ 一律以 backend/ 为工作目录：app.config.BACKEND_DIR 是绝对路径（不依赖 CWD），
#    但 `python scripts/demo_bootstrap.py` 与 `python -m uvicorn app.main:app` 都要
#    能 import 到 `app` 包，而 pyproject.toml 的 pythonpath=["."] 只对 pytest 生效。
$Backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Backend
Write-Host "== 厦大体育数智系统 · 演示 =="
Write-Host "   backend = $Backend"

# ---------------------------------------------------------------------------
# ① 演示库的 URL 与路径：从 app.main.DEMO_DB_URL 读（**唯一所有者**）
# ---------------------------------------------------------------------------
# ⚠️ 用 sqlalchemy.engine.make_url 剥路径，而不是在 PowerShell 里做字符串替换：
#    `sqlite:///C:/x/pe_demo.db` 的第三段之后全是路径，而 Windows 的盘号里就有一个冒号，
#    手工 `-replace '^sqlite:///',''` 在 UNC 路径（sqlite:////server/share/x.db）上会错。
$probe = python -c "from app.main import DEMO_DB_URL; from sqlalchemy.engine import make_url; print(DEMO_DB_URL); print(make_url(DEMO_DB_URL).database)"
if ($LASTEXITCODE -ne 0) { throw "读不出 app.main.DEMO_DB_URL（Python 环境或依赖有问题？）" }
$DemoDbUrl = ($probe | Select-Object -First 1).Trim()
$DemoDbPath = ($probe | Select-Object -Last 1).Trim()
Write-Host "   DEMO_DB_URL = $DemoDbUrl"

if ($DryRun) {
    $Work = Join-Path $env:TEMP ("pe_demo_dryrun_" + $PID)
    if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    $DbPath = Join-Path $Work "pe_demo.db"
    $DbUrl = "sqlite:///" + ($DbPath -replace '\\', '/')
    $CsvDir = Join-Path $Work "lepao"
    Write-Host "   -DryRun：库与 CSV 都落在 $Work（跑完删掉，backend/ 下不留文件）"
} else {
    $DbPath = $DemoDbPath
    $DbUrl = $DemoDbUrl
    # ⚠️ CSV 也落在 $env:TEMP：backend/data/** 一个字节都不许动，
    #    而 backend/data/seed/ 更是恒为 0 文件的禁区。
    $CsvDir = Join-Path $env:TEMP ("pe_demo_csv_" + $PID)
}

# ---------------------------------------------------------------------------
# ② 删掉旧的演示库（**在设 PE_DB_URL 之前**，避免删错文件时已经指过去了）
# ---------------------------------------------------------------------------
if (-not $DryRun) {
    foreach ($suffix in @("", "-journal", "-wal", "-shm")) {
        $stale = "$DemoDbPath$suffix"
        if (Test-Path $stale) {
            Remove-Item $stale -Force
            Write-Host "   删掉旧库 $stale"
        }
    }
    if (Test-Path $DemoDbPath) { throw "删不掉旧库 $DemoDbPath（被别的进程占着？）" }
}

# ---------------------------------------------------------------------------
# ③ 两个环境变量：PE_DB_URL（app.main 的覆盖口）+ PE_CSV_DIR（pipeline router 的覆盖口）
# ---------------------------------------------------------------------------
# ⚠️ PE_CSV_DIR **必须在起 uvicorn 之前设**：POST /api/pipeline/run-daily 在**请求时**
#    读它（不是 import 时），但 `app = create_app()` 是 app.main 的模块级语句，
#    而 PE_DB_URL 那一侧是 import 时读的——两个都提前设，省得记谁先谁后。
#
# ⚠️⚠️ **本处此前还设了第三个：`$env:PE_ALLOW_HEADER_IDENTITY = "1"`**
#    （Plan 05A Task 1 加的、逐字注明是「有意的过渡态，Task 5 撤掉」）。
#    **Plan 05A Task 5 已把它撤掉**，理由与时机逐字如下：
#      · 它的作用是让 `current_student` / `current_teacher` 在没有 `pe_session`
#        cookie 时**回落到请求头**。生产缺省是 `"0"`（只认 cookie），
#        而 `tests/conftest.py` 把它设成 `"1"`（故 1333 条测试一条都没改）。
#      · 它当初必须在演示里打开：那时前端还没有登录页，撤掉它等于
#        「演示库起来之后每一个要身份的端点都 401」。
#      · 而 Plan 05A Task 3 交付了 `/login` 与 `/bind`、Task 4 让
#        `demo_bootstrap.py` 给演示库的 63 个账号绑了口令并造出了管理员，
#        故**前端今天真的能登录** —— 过渡态的前提消失了。
#    ⚠️ **撤掉它的可执行判据是 `frontend/scripts/smoke.mjs` 仍然 17 步全绿**：
#    那个脚本一律用 cookie（它自己维护一个 jar，**一个身份请求头都不发**），
#    故「过渡态真的撤干净了」与「联调仍然通」是同一件事。
#    ⚠️ 撤掉之后，一个手工发的 `X-Teacher-Staff-No: T0001` 在演示库上**不再有任何效力**
#    （后端会完全忽略它）——那正是「挡事故、也挡攻击」的方向。
#    ⚠️ 要在本机临时打开它（例如用 Swagger 试一个老姿势），请在**另一个**终端里
#    `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 再起 uvicorn；`$env:` 是进程级的，
#    不会写进注册表、也不会留给下一个终端。
#    ⚠️ 而**本脚本会强制清掉它**（下面那一段），故那个姿势只对**手工起的** uvicorn 有效
#    —— 想靠 `demo.ps1` 起一个认请求头的后端是行不通的，那正是下面那一段要的事。
# ⚠️⚠️ **强制，不是声明**（终审 I2）：这个开关的失效方向本来是**安全**的
#    （`app/api/deps.py` 的 docstring 逐字写了「写错一个值会**关掉**过渡通道……
#    而不是打开它」），而本处此前用一句**无条件**的 Write-Host「…未设…」代替了强制
#    —— 恰好把那条性质反转成了**静默打开**：在同一个 shell 里跑过 Plan 05A 那一版
#    （`8596043`，它确实设过 =1），或把它设进了用户/机器级环境，就会得到一个
#    **认伪造请求头**的 uvicorn，而脚本两次告诉用户相反的话。下一个人会在同一个终端里
#    反复跑本脚本，之后他所有的鉴权实测都是在测一个认请求头的后端、而以为自己在测生产档。
#    故这里 ① 删掉进程级的那一份（`Remove-Item Env:\` 只动进程，不碰注册表）
#          ② 删不掉就 throw —— 与本文件既有的两道**禁区守卫**（⑤ 那一步）同一个姿势
#          ③ 打印**实测值**，不打印一句写死的话。
#    ⚠️ 下面这几个变量是本文件里关于这个开关的**单一所有者**：⑥ 那一步的第二次打印也读它们。
$HeaderIdentityInherited = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY -ErrorAction SilentlyContinue
$HeaderIdentityNow = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
if (-not [string]::IsNullOrEmpty($HeaderIdentityNow)) {
    throw ("PE_ALLOW_HEADER_IDENTITY 删不掉（本进程实测仍是 " + $HeaderIdentityNow + "）：本脚本一律以生产缺省 0 起 uvicorn（只认 pe_session cookie）。请手工清掉它再重跑。")
}
# ⚠️ 打印的是「进本脚本时实测到什么」+「本脚本把它变成了什么」两格，不是一句写死的「未设」。
$HeaderIdentityShown = if ([string]::IsNullOrEmpty($HeaderIdentityInherited)) { '未设' } else { '=' + $HeaderIdentityInherited }
$HeaderIdentityNowShown = if ([string]::IsNullOrEmpty($HeaderIdentityNow)) { '未设' } else { '=' + $HeaderIdentityNow }

$env:PE_DB_URL = $DbUrl
$env:PE_CSV_DIR = $CsvDir
Write-Host "   PE_DB_URL  = $env:PE_DB_URL"
Write-Host "   PE_CSV_DIR = $env:PE_CSV_DIR"
Write-Host "   PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 $HeaderIdentityShown → 本进程已**强制**清成 $HeaderIdentityNowShown（= 生产缺省 `"0`"：只认 pe_session cookie；Plan 05A Task 5 撤掉了那个过渡态的 =1）"

# ---------------------------------------------------------------------------
# ④ 灌数据
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- 灌数据（$Students 人 / seed=$Seed）--"
python scripts/demo_bootstrap.py --db-url $DbUrl --csv-dir $CsvDir --students $Students --seed $Seed
if ($LASTEXITCODE -ne 0) { throw "数据准备失败（退出码 $LASTEXITCODE），不起服务" }

# ---------------------------------------------------------------------------
# ⑤ 复核两个禁区
# ---------------------------------------------------------------------------
$ForbiddenDb = Join-Path $Backend "pe.db"
$ForbiddenCsv = Join-Path $Backend "data\seed"
if (Test-Path $ForbiddenDb) { throw "禁区被写到了：$ForbiddenDb（本文件不该产生它）" }
# ⚠️ -Recurse 是承重的（Plan 03 全分支终审的 M2）：禁区那条纪律是
#    「backend/data/seed/ 恒为 0 文件」，而不带 -Recurse 的 Get-ChildItem -File
#    **看不见子目录里的文件**，于是「有人在 data/seed/2025/ 下写了一堆 CSV」
#    这一档会静默通过复核。
$seedFiles = @(Get-ChildItem $ForbiddenCsv -File -Recurse -ErrorAction SilentlyContinue)
if ($seedFiles.Count -gt 0) { throw "禁区被写到了：$ForbiddenCsv（应当恒为 0 文件）" }
Write-Host ""
Write-Host "   禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓"

if ($DryRun) {
    Remove-Item $Work -Recurse -Force
    Write-Host "   -DryRun 收尾：$Work 已删掉"
    exit 0
}

# ---------------------------------------------------------------------------
# ⑥ 起服务（前台；Ctrl-C 停）
# ---------------------------------------------------------------------------
$Base = "http://127.0.0.1:$Port"
Write-Host ""
Write-Host "-- 起服务 --"
Write-Host "   Swagger UI      $Base/docs"
Write-Host "   OpenAPI JSON    $Base/openapi.json"
Write-Host "   存活探针        $Base/api/health"
Write-Host ""
Write-Host "   身份**只有一条**通道（Plan 05A Task 5 撤掉了请求头那个过渡态）："
Write-Host "     首次绑定 POST /api/auth/students/bind（学号 + 出生日期 + 新口令）"
Write-Host "              POST /api/auth/teachers/bind（工号 + 姓名 + 新口令）"
Write-Host "     登录     POST /api/auth/login  → Set-Cookie: pe_session（HttpOnly，故 JS 读不到）"
Write-Host "     我是谁   GET  /api/auth/me     登出 POST /api/auth/logout（**真的吊销**服务端那一行）"
Write-Host "     ⚠️ 手工发 X-Teacher-Staff-No / X-Student-Id 在本进程上**没有任何效力**"
Write-Host "        （PE_ALLOW_HEADER_IDENTITY 本进程实测 $HeaderIdentityNowShown = 生产缺省 `"0`" = 只认 cookie；进本脚本时它是 $HeaderIdentityShown，③ 那一步已强制清掉）。"
# ⚠️ 演示口令、管理员、**以及一个真学号**都**不在本文件里写第二遍**（单一所有者是
#    scripts/demo_bootstrap.py 的 DEMO_PASSWORD / DEMO_ADMIN_STAFF_NO，以及它 [6/7]
#    那一步**从库里取**的那一个 student_no）。
#    本处只把「去哪一行找它」说出来 —— 抄一份字面量到这里的话，
#    改口令的人会漏改一处，而漏改的那一处是**演示时要念给人听**的那一处。
#    ⚠️ 学号那一格此前正是这么抄的（「例如 2025010004」，终审 I1）：名册由
#    app/seed/population.py 按「入学年 + 院系码 + 序号」现造，那串**从来不在册**，
#    照着它登录是 403 password_not_bound（而那句 403 说的是「不在名册上」，会把人支去查后端）。
Write-Host ""
Write-Host "   ⚠️⚠️ 演示账号（口令、管理员、一个真学号都由上面 [6/7] 那一步打印，也写在 spec §13）："
Write-Host "      学生     任何一个在册学号（上面 [6/7] 那一步从库里打印了一个**真**例子）+ 演示口令"
Write-Host "      教师     T0001 / T0002（role='teacher'）+ 演示口令"
Write-Host "      管理员   T0003（role='admin'）+ 演示口令"
Write-Host "      ⚠️ 管理台（23 个资源的增删改查）自 Plan 05A Task 2 起**仅管理员**可写："
Write-Host "         用 T0001 登录去写会得到 403 forbidden，那不是坏了，是口径。"
Write-Host "      ⚠️ 前端在 http://localhost:5173（另开一个终端 cd frontend; npm run dev）："
Write-Host "         未登录访问任何页面都会被路由守卫送去 /login?next=<原路径>。"
# ⚠️⚠️ 交付前收尾波 ④.1：下面那 8 条提示 URL **一律要登录会话**（pe_session cookie），
#    浏览器直接打开一律 401。改前这一段只印 URL、不印这件事，而实测（匿名逐个打过去）
#    当时就已经有 **7** 条是 401 了（安全收紧波把学生键资源都收了），
#    收尾波 ③ 关掉 mini-tests/normalized 那扇门之后是 **8 条全 401**。
#    ⚠️ 于是「照着屏幕上的 URL 点一下」这个演示动作在今天**必然失败**，
#    而失败的样子（401 unauthenticated）会让人以为是后端坏了。
#    处置：① 把「要先登录」印在清单头上；② 另给 3 条**仍然匿名**的当例子
#    （参考数据与群体统计那一档，实测各 200），于是「不登录也能点通一条」这件事还在。
Write-Host ""
Write-Host "   ⚠️⚠️ 下面这 8 条**一律要登录会话**（pe_session cookie），浏览器直接打开一律 401："
Write-Host "      安全收紧波起学生键资源要身份，收尾波 ③ 又关上了最后那扇门（mini-tests/normalized）。"
Write-Host "      要点通它们请先登录：POST /api/auth/login 换 cookie，或直接在 5173 的前端上登录。"
Write-Host "   一条闭环（spec §1.3 的三段）登录后可以这样点："
# ⚠️ 下面这几行一律用**单引号**串 + 拼接，不用双引号串里的反引号转义：
#    单引号串不插值、也不需要转义 `"`，而 JSON 与查询串里两种字符都有。
Write-Host ('     GET  ' + $Base + '/api/students/1/prescriptions/current?as_of=2025-10-12')
Write-Host ('     GET  ' + $Base + '/api/students/1/weekly-sheet?as_of=2025-10-12')
Write-Host ('     GET  ' + $Base + '/api/alerts?limit=50                    # 教师端的预警队列')
Write-Host ('     POST ' + $Base + '/api/alerts/{id}/handle?as_of=2025-10-12   {"action": "reduce_20pct"}')
Write-Host ('     GET  ' + $Base + '/api/notifications?limit=50               # 学生端的消息中心')
Write-Host ('     GET  ' + $Base + '/api/dashboard/class/1?week=6&as_of=2025-10-12')
Write-Host ('     POST ' + $Base + '/api/pipeline/run-daily                   {"business_date": "2025-10-12"}')
Write-Host ('     GET  ' + $Base + '/api/mini-tests/normalized?semester_id=2&week=6')
Write-Host ""
Write-Host "   ⚠️ 不登录也点得通的只有参考数据与群体统计那一档（实测各 200），例如："
Write-Host ('     GET  ' + $Base + '/api/health                               # 28 张表 + 各表行数')
Write-Host ('     GET  ' + $Base + '/api/exercises?limit=50                   # 动作库（不含任何学生键）')
Write-Host ('     GET  ' + $Base + '/api/percentile-snapshots?limit=50        # 常模分位数（群体统计）')
# ⚠️ 上面 run-daily 那一条**演示时要慎用**（Plan 03 全分支终审的 I1 留下的一个已知边界）：
#    那个端点走的是 run_daily 的**缺省** now（真实时钟），而不是 business_now(as_of)。
#    生产上 as_of == 今天，故两者等价；而演示库的 as_of 是 2025-10-12（一个历史日），
#    于是点它一次会让 alert.triggered_at 落到「真实的今天」、与报表周窗口不相交，
#    weekly_class_report.alert_summary 会**变回 9 个 0**（教师大屏的「本周预警汇总」空掉）。
#    要重灌演示库请重跑 demo.ps1（它走的 scripts/demo_bootstrap.py 会注入 business_now）。
Write-Host '   ⚠️ 上面 run-daily 那一条在演示库上会把周报的「预警汇总」清零'
Write-Host '      （端点用真实时钟，而演示的 as_of 是历史日）；要重灌请重跑 demo.ps1'
Write-Host ""
Write-Host "   Ctrl-C 停止。库文件留在 $DbPath（已进 .gitignore）。"
Write-Host ""
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
