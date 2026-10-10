"""Task 9 落地脚本 05：写 backend/scripts/demo.ps1（UTF-8 **带 BOM** + CRLF）。

⚠️ **为什么带 BOM**（这一格是本脚本存在的全部理由）：开发机的 shell 是
**Windows PowerShell 5.1**，它读一个**没有 BOM** 的 ``.ps1`` 时按系统 ANSI 代码页
（简体中文机器上是 GBK/936）解码，而本文件里有大量中文注释与中文字符串——
UTF-8 的字节按 GBK 解出来是乱码，``Write-Host`` 打出来的是一堆问号，
而**脚本本身仍然跑得动**（乱码只落在字符串字面量里），于是这个失效是静默的。
PowerShell 7+ 缺省按 UTF-8 读、不需要 BOM，但本仓的开发机是 5.1。
⚠️ 与 commit 信息刻意相反（那一份要求 UTF-8 **无** BOM）：两个消费者的解码规则不同，
git 把 BOM 当成消息正文的头三个字节、而 PowerShell 把它当成编码声明。
⚠️ 行尾用 CRLF：``.gitattributes`` 只钉了 ``backend/data/**`` 与 ``.superpowers/**``，
``*.ps1`` 不在任何一条规则里，故 ``core.autocrlf=true`` 会让它在 index 里是 LF、
在工作树里是 CRLF——与本仓其余文件的现状一致。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
TARGET = ROOT / "backend" / "scripts" / "demo.ps1"

BODY = r'''<#
.SYNOPSIS
    一条命令把「体育闭环原型系统」跑起来（Plan 03 Task 9）。

.DESCRIPTION
    五步：① 删掉旧的演示库 → ② 把 ``PE_DB_URL`` / ``PE_CSV_DIR`` 指到演示位置 →
    ③ 灌数据（``scripts/demo_bootstrap.py``：组织结构 + 一学期体测 CSV + 反馈三源 +
    一次每日批处理）→ ④ 复核两个禁区没被写到 → ⑤ 起 uvicorn 并打印 URL。

    ⚠️ **它写的是 ``backend/pe_demo.db``、不是 ``backend/pe.db``**：后者是本仓禁区
    （``app.config.DEFAULT_DB_URL`` 指的就是它，语义是「``app.seed.generate`` 写出来的
    那份不可复现的库」，**不得存在**）。演示库的 URL 从 ``app.main.DEMO_DB_URL`` 读出来、
    **不在本文件里敲第二遍路径**（那是第二个所有者），并已进 ``.gitignore``。

    ⚠️ **第一步必须删旧库**：``app.db.session.init_db`` 走 ``Base.metadata.create_all``，
    对**已存在的表原样跳过**——故一个旧库不会报错、也不会补上新增的 NOT NULL 列，
    端点会在离真因很远的地方 500（Plan 03 Task 2 撞过一次，那次是
    ``training_log.submitted_at``）。⚠️ 本仓不做迁移：schema 改动等于重建库。

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
Write-Host "== 体育闭环原型系统 · 演示 =="
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
$env:PE_DB_URL = $DbUrl
$env:PE_CSV_DIR = $CsvDir
Write-Host "   PE_DB_URL  = $env:PE_DB_URL"
Write-Host "   PE_CSV_DIR = $env:PE_CSV_DIR"

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
$seedFiles = @(Get-ChildItem $ForbiddenCsv -File -ErrorAction SilentlyContinue)
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
Write-Host "   身份用请求头传（原型口径，没有真实鉴权）："
Write-Host "     X-Teacher-Staff-No: T0001     X-Student-Id: 1"
Write-Host "   一条闭环（spec §1.3 的三段）可以这样点："
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
Write-Host "   Ctrl-C 停止。库文件留在 $DbPath（已进 .gitignore）。"
Write-Host ""
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
'''

TARGET.parent.mkdir(parents=True, exist_ok=True)
raw = BODY.replace("\n", "\r\n").encode("utf-8")
TARGET.write_bytes(b"\xef\xbb\xbf" + raw)
written = TARGET.read_bytes()
bom = written.startswith(b"\xef\xbb\xbf")
crlf = written.count(b"\r\n")
bare = written.count(b"\n") - crlf
print(f"写出 {TARGET}")
print(f"  bytes={len(written)} BOM={bom} CRLF={crlf} bare LF={bare} lines={crlf + bare}")
assert bom and bare == 0
sys.exit(0)
