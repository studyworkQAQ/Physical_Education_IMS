<#
.SYNOPSIS
    产出一个**可分发的试用包**（Plan 07 Task 4）：``dist-pack\pe-ims-trial-<时间戳>.zip``。
    甲方 IT 解包之后，在**只装了 Python 3.11+** 的机器上一条命令就能起一份来试用
    （⚠️ 不需要 Node、不需要 ``npm install``、不需要 git）。

.DESCRIPTION
    六步：① 前置检查（``frontend\dist`` 在不在、``backend\pyproject.toml`` 在不在）
    → ② 按**两份清单**（进包的顶层 / 排除的目录名与文件通配）把文件抄进一个 staging 目录
    → ③ 复核 staging（必须含 / 必须不含 / 文件数与字节数 / 最长相对路径）
    → ④ 压成 zip → ⑤ **打开那个 zip** 再复核一遍（条目名、条目数、
    逐条目的 sha256 与 staging 里的原文件对账）→ ⑥ 打印清单、大小与「解包之后怎么起」。

    ------------------------------------------------------------------------
    ⚠️ 它**不构建前端**（第二个所有者一个都不当）
    ------------------------------------------------------------------------
    「怎么构建」的唯一所有者是 ``scripts\serve.ps1`` 的 ②（它自己判 ``dist`` 是不是比
    ``src`` 旧，必要时跑 ``npm run build``）。本文件只在 ``dist\index.html`` 不在时
    **报一句人话并退出非 0**，⚠️ 不替你去构建：一个打包脚本偷偷跑一次 ``npm run build``
    会让「包里那份产物是哪一次构建出来的」变成一件没人知道的事
    （姿势同 ``scripts\tunnel.ps1`` 的「不自己起服务」、``scripts\trial.ps1`` 的
    「不自己写第二个启动器」）。
    ⚠️ 同理它**不灌库**：包里一个 ``.db`` 都不放（``*.db`` 在排除清单里，
    而 ⑤ 那一格按字面钉住），首次启动由 ``scripts\trial.ps1`` 自己灌
    （走 ``backend\scripts\demo_bootstrap.py``，即 ``demo.ps1`` 用的**同一套**生成器）。

    ------------------------------------------------------------------------
    ⚠️ 为什么带 ``frontend\src`` 与整条构建链，而不只带 ``dist``
    ------------------------------------------------------------------------
    控制者裁定「带 ``src``」（spec 是技术对接依据、甲方 IT 可能要读），并把
    「带 ``src`` 但不带构建链会不会造成困惑」这一格交给实现者实测。
    **实测结论：只带 ``src`` 确实是困惑的那一档**，故本文件带的是**整个 ``frontend\``
    减去 ``node_modules\``** —— ``package.json`` / ``package-lock.json`` /
    ``vite.config.ts`` / ``tsconfig*.json`` / ``index.html`` / ``scripts\*.mjs`` 一并进包。
    理由是失效方向：
      · 只带 ``src`` 而不带 ``package.json`` ⇒ ``serve.ps1``（不带 ``-SkipBuild`` 时）
        会去扫那五个单文件、扫不到，于是一份**不可构建**的源树摆在包里，
        而屏幕上没有任何一处说清「这一份是给你读的、不是给你构建的」；
      · 带整条链 ⇒ 甲方 IT 真装了 Node 之后 ``npm install; npm run build`` **跑得起来**
        （``package-lock.json`` 在，装出来的版本与我们构建 ``dist`` 时一致），
        而缺省路径（``trial.ps1`` 透传 ``-SkipBuild``）**一次都不碰 node**。
    ⚠️ 代价如实说：包因此多了约 100 个文件 / 2.9 MiB（其中 ``dist`` 0.69 MiB、
    ``src`` 里最大的一份是自动生成的 ``api\generated\schema.d.ts``）。

    ------------------------------------------------------------------------
    ⚠️ 压缩**不用** ``Compress-Archive``、也**不用** ``ZipFile.CreateFromDirectory``
    ------------------------------------------------------------------------
    两档都实测过，而**两档都不合格**，理由不是速度而是**条目名里的分隔符**。

    · **速度**（5 万个 40 字节的小文件、同一棵 staging 树）：``Compress-Archive``
      **300.1 秒**、``Expand-Archive`` 回读 **381.6 秒**；``ZipFile.CreateFromDirectory``
      **10.6 秒**（快 28 倍），两者产物**字节数逐字相同**（都是 6 645 022 B、
      50 000 个条目）。⚠️ 而本包只有三百多个文件，两档都是**零点几秒**
      ⇒ 速度不是本包的裁定理由（虽然它足以否掉 ``Compress-Archive``）。
    · ⚠️⚠️ **分隔符**（裁定理由在这一格）：拿一棵 3 个文件的小树
      （``top.txt`` / ``a\mid.txt`` / ``a\b\deep.txt``）分别用三档压一遍，
      再**直接读 zip 中央目录的原始字节**（⚠️ 不经任何解压库），实测：
        - ``Compress-Archive``            → ``a\mid.txt``、``a\b\deep.txt``（**反斜杠**）
        - ``ZipFile.CreateFromDirectory`` → 同上（**反斜杠**）
        - 手工 ``ZipArchive.CreateEntry`` → ``a/mid.txt``、``a/b/deep.txt``（**正斜杠**）
      ZIP 的规范（APPNOTE 4.4.17.1）要求条目名一律用 ``/``，而 PS 5.1 / .NET Framework
      那两档写的是 Windows 的 ``\`` ⇒ 在 Linux 的 ``unzip`` 与一部分解压工具下，
      解出来的**不是目录树**，而是一个名字里带着反斜杠的**平文件**
      （字面叫 ``a\b\deep.txt``）——包就废了，而 Windows 自己的「全部解压缩」
      恰好认得它，故这一档在开发机上**看不出来**。
      ⇒ 本文件用第三档：自己开一个 ``ZipArchive``、逐个 ``CreateEntry``，
      条目名**显式**把 ``\`` 换成正斜杠。
    · ⚠️ 顺带把每个条目的 ``LastWriteTime`` 设成**源文件**的那一个
      （``CreateFromDirectory`` 就是这么做的；``CreateEntry`` 的缺省是 ``Now``）。
      ⚠️⚠️ **Plan 09 Task 1 之后这一格不再是承重的**（改前那段逐字写着
      「解包出来的 ``dist`` 与 ``src`` 会**一样新**，而 ``serve.ps1`` 判『要不要重建』
      读的正是那两个 mtime」）：``serve.ps1`` 从此读的是
      ``frontend\dist\.build-manifest.json`` 里那一份**源面逐文件 sha256**、
      **不是** mtime（spec §15 **G22** 的代码级收口）⇒ 解包出来的 ``dist`` 与 ``src``
      谁新谁旧它一眼都不看，而包里那 65 个哈希与解包后的磁盘字节**逐个相符**
      （压缩是原字节流拷贝、⑤ 又逐条目对了一次 sha256 ⇒ 哈希不会因为打包而漂）
      ⇒ 甲方那台机器上**一次都不会重建**（那台机器大概率没有 node）。
      ⚠️ 而保留真实时间戳仍然做：它是**免费**的，而且让人一眼看得出包里那份产物
      是哪一天的 —— 只是不再靠它兜住判据。
    · ⚠️⚠️ **一个会让人假绿的坑（本波亲验，如实记）**：Python 的
      ``zipfile.namelist()`` 会把条目名里的 ``\`` **悄悄换成正斜杠**再交给你
      ⇒ 用它去看上面那两个包，报的是「0 个反斜杠条目，一切正常」。
      本波第一版就是这么量的、而且**量绿了**；是 ⑤ b 那一格用 .NET 侧把条目名
      读回来对账时才发现两边对不上（.NET 给的是 ``backend\pyproject.toml``，
      字符 92）。故 ⑤ 与本文件的守卫**都按原始字节**判：守卫是
      ``backend/tests/test_package.py`` 的
      ``test_the_zip_entry_names_use_forward_slashes_as_the_zip_format_requires``，
      它自己解析中央目录、一个解压库都不用。
    · ⚠️ 它**不是**新增依赖：``System.IO.Compression`` 与
      ``System.IO.Compression.FileSystem`` 都是 .NET Framework 的 BCL 程序集
      （``Add-Type -AssemblyName`` 只是把它们加载进会话），
      ``pyproject.toml`` / ``package.json`` 一个字都没改。
    · ⚠️ 而**行尾**：压缩是原字节流拷贝（``Stream.CopyTo``），⑤ 又对**整包**
      逐条目对了一次 sha256 ⇒「打包改了行尾 / 剥了 BOM」这一档在两道地方都会红。
    · ⚠️⚠️ **长路径**：两档在 PS 5.1 / .NET Framework 下**都**读不了超过 260 字符的
      路径（实测：一个 364 字符的路径，``Compress-Archive`` 报 ``PathNotFound``、
      ``ZipFile`` 报 ``DirectoryNotFoundException``）⇒ 换一个 API 解决不了它。
      本包的实测最长相对路径是 **75 字符**（``backend\migrations\versions\…``），
      加上仓库根的绝对前缀也远在 260 以内；而 ③ 那一步仍然**钉了一道上界**，
      于是将来有人加了一个很深的目录时会**响亮地**失败，而不是产出半个包。

    ------------------------------------------------------------------------
    ⚠️ ``dist-pack\`` 已进 ``.gitignore``；本脚本**不删**旧的包
    ------------------------------------------------------------------------
    一个包里是一整份可交付产物（十几 MiB），入库等于把它永久留在 git 历史里
    （历史删不掉），故那一行是必须的。⚠️ 而本脚本刻意**不删** ``dist-pack\`` 下
    已有的包：那是你的产物，一个打包脚本替你做删除决定是**静默**的那一类事故
    （姿势同 ``serve.ps1`` 的「不自动改防火墙」、``trial.ps1`` 的「不硬删一个被持有的库」）。
    它只把「现在有几个、共多大」打印出来，删不删由你决定。

.PARAMETER OutDir
    zip 落到哪个目录。⚠️ 缺省是**空串**，解析成 ``<仓库根>\dist-pack``
    （⚠️ 那个目录名的唯一所有者是本文件的 ``$DefaultOutDirName``，
    而它与 ``.gitignore`` 里那一行不许漂开：守卫
    ``backend/tests/test_package.py`` 的
    ``test_the_output_directory_has_one_owner_and_gitignore_agrees`` 按字面钉两侧）。
    给它的用处：① 测试把包落到一个临时目录里，不在仓库里堆产物；
    ② 甲方 IT 想把包直接产出到 U 盘或一个共享目录上。
    ⚠️ 目录不在就**创建**它（``-Force``），而**不清空**它。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\package.ps1
    # 产出 dist-pack\pe-ims-trial-<yyyyMMdd-HHmmss>.zip 并打印「进了什么 / 排除了什么」

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\package.ps1 -OutDir D:\deliver
    # 换一个落地目录（⚠️ 它不构建前端：dist 不在就先跑一次 scripts\serve.ps1）
#>
[CmdletBinding()]
param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# ⚠️ 本文件住在**仓库根**的 scripts\ 下（与 serve.ps1 / trial.ps1 / tunnel.ps1 同一层）：
#    它同时碰 backend\ 与 frontend\ 与 Document\，故不属于任何一包（理由逐字同
#    tests/test_serve.py 的 test_serve_ps1_lives_at_the_repo_root_and_not_under_backend_scripts）。
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

#: 落地目录名的**唯一所有者**（⚠️ 与 .gitignore 里那一行不许漂开，守卫按字面钉两侧）。
$DefaultOutDirName = "dist-pack"

#: 包名的前缀。⚠️ 时间戳的格式是 ``yyyyMMdd-HHmmss``（实施计划 07 §4 逐字要求）：
#:    它排得序、念得出来、而秒级足够（一秒钟内打两个包不是本脚本要支持的形状）。
$PackagePrefix = "pe-ims-trial-"

#: staging 目录：⚠️ 落在 ``$env:TEMP`` 下、按 PID 命名，**退出时删掉**
#:    （姿势逐字同 trial.ps1 的 ``$CsvDir``：自己造的垃圾自己收）。
$Stage = Join-Path $env:TEMP ("pe_package_" + $PID)

#: ⚠️⚠️ staging 的收尾**只有一个所有者**（Plan 07 Task 8 · 终审 S4-16）。
#:    改前是**两份**逐字相同的 ``Remove-Item $Stage -Recurse -Force -ErrorAction
#:    SilentlyContinue``（下面那个 ``trap`` 里一份、⑥ 之后一份），而两份都会**部分失败**：
#:    PS 5.1 的 ``Remove-Item -Recurse`` 在一棵三百多个文件的树上会间歇性地只删掉一部分
#:    （本机 ``$env:TEMP`` 上那一份残渣实测剩 **3** 个文件、**全是** ``scripts\*.ps1``：
#:    ``pe_package_12228``，145 204 B），而 ``-ErrorAction SilentlyContinue`` 把真因吞掉
#:    ⇒ 屏幕上只有一行「⚠️ staging 删不掉」，``$env:TEMP`` 里躺着十几 MiB。
#:    ⚠️ 它**不是静默**的（那一行会打印），故 S4-16 不是一格假绿；而「响亮、但每一次
#:    都要人手去删」仍然是一个缺陷，且它会在甲方 IT 的机器上一样发生。
#:    修法：一个函数 + **有界重试**（那一格是瞬时的句柄竞争，等一下多半就删得掉），
#:    两个调用点一律走它，⚠️ 而删不掉时**把剩下哪几个文件报出来**（改前只说「删不掉」，
#:    于是人要自己去 ``$env:TEMP`` 里翻）。
function Remove-Staging {
    for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
        if (-not (Test-Path $Stage)) { return $true }
        Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path $Stage)) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return (-not (Test-Path $Stage))
}

#: 删不掉时报给人看的那一格（⚠️ 只在 ``Remove-Staging`` 回了 ``$false`` 之后才调用，
#:    故它不在正常路径上花时间）。
function Get-StagingLeftovers {
    if (-not (Test-Path $Stage)) { return @() }
    return @(Get-ChildItem -LiteralPath $Stage -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName.Substring($Stage.Length + 1) })
}

# ⚠️ **兜住 staging**：下面任何一条 ``throw`` 都不该留下一个十几 MiB 的临时树
#    （姿势同 ``trial.ps1`` 收尾删自己那个 ``$CsvDir``、``serve.ps1`` 的 ``finally`` 兜住
#    uvicorn：自己造的垃圾自己收，而「异常路径」正是最容易漏收的那一条）。
#    ⚠️ 用 ``trap`` 而不是把 ③–⑥ 整块缩进进一个 ``try``：后者会让这一百多行的
#    判据全部右移一格，而下一个人加一拍时漏缩进就是**静默**地跳出了保护圈。
#    ⚠️ 它兜不住 ``Ctrl-C`` 与「被工具硬杀」那一档（那时脚本一行都跑不到）；
#    那一档留下的是一个 ``$env:TEMP`` 下的目录，无害，且它按 PID 命名、不累积。
#    ⚠️⚠️ 而它**同样兜不住 ``exit``**（``exit`` 不是一个错误，``trap`` 因此一行都不跑）
#    ⇒ staging 建好之后的任何一条失败路径都**必须是 ``throw``、不许是 ``exit 1``**。
#    今天那三条 ``exit 1``（缺 ``frontend\dist\index.html`` / 缺 ``backend\pyproject.toml``
#    / 进包清单里的某个顶层不在）全部排在 ② 建 staging **之前**，故它们不泄漏；
#    而「哪一条排在前面」是一个**顺序**性质、读一眼看不出来 ⇒ 由
#    ``backend/tests/test_package.py`` 的
#    ``test_the_staging_cleanup_has_one_owner_and_there_is_no_exit_after_staging_exists``
#    按**行号**钉住（把 ② 之后的任何一条 ``throw`` 改回 ``exit 1`` 都会当场红 ——
#    那正是 commit ``8304175`` 修的实况，也是终审 S4-9 的 P7 那一格定点变异）。
trap {
    $Cleaned = Remove-Staging
    Write-Host ""
    Write-Host ("   ⚠️ 打包失败：" + $_.Exception.Message)
    if ($Cleaned) {
        Write-Host ("      staging " + $Stage + " 已删掉（⚠️ 没有产出任何包）。")
    } else {
        $Left = @(Get-StagingLeftovers)
        Write-Host ("      ⚠️ staging 删不掉：" + $Stage + "（重试 3 次之后仍剩 " + $Left.Count + " 个文件：" + (($Left | Select-Object -First 5) -join "、") + "）")
        Write-Host ("         有进程持有它？请手工删（⚠️ 没有产出任何包）。")
    }
    exit 1
}

# ---------------------------------------------------------------------------
# 两份清单：⚠️ **本文件是它们的唯一所有者**（守卫按字面钉，不从 staging 反推）
# ---------------------------------------------------------------------------
#: 进包的**顶层**（相对仓库根）。⚠️ 一份**显式**清单，而不是「仓库根下除了 X 都要」：
#:    后者的失效方向是静默的 —— 谁在仓库根丢一个 ``credentials.xlsx``，它就进包了。
$IncludeRoots = @(
    "backend",
    "frontend",
    "Document",
    "scripts",
    "README.md"
)

#: 排除的**目录名**（任何深度上撞到就整棵子树不进包，⚠️ 且不往里递归：
#:    ``node_modules`` 与 ``.git`` 各有几万个文件，先进去再过滤是几十秒的白工）。
$ExcludeDirNames = @(
    ".git",              # 版本控制的历史（⚠️ 里面是全部被删掉的旧库与旧产物）
    ".pytest_cache",     # pytest 的缓存
    ".superpowers",      # ⚠️ 内部账本（SDD 的 18 份实现者报告 + 台账），不是给甲方的
    ".trial",            # scripts\tunnel.ps1 写的公网链接（一条**公网可达**的临时地址）
    "dist-pack",         # 本脚本自己的产物（⚠️ 把上一个包打进下一个包是套娃）
    "tools",             # ⚠️ 55 MB 的 cloudflared.exe：隧道是**我方这一侧**的事，
                         #    而说明书 §2 ① 已经写了「怎么自己拿一个可信的 cloudflared」
    "node_modules",      # 前端的依赖树（几万个文件；⚠️ 缺省路径一次都不碰 node）
    "__pycache__",       # Python 的字节码缓存
    "backups"            # backend\backups\：一整份库（含全部学生的健康档案）
)

#: 排除的**目录名后缀**（``pe_backend.egg-info`` 一类由 setuptools 生成的东西）。
$ExcludeDirSuffixes = @(".egg-info")

#: 排除的**文件通配**。⚠️ ``*.db`` 与它的三个侧车后缀是承重的：包里一个 ``.db`` 都不许有
#:    （``pe_trial.db`` 是甲方正在用的那一份、``pe_demo.db`` 是开发靶子，
#:    两份都含一整份仿真名册；首次启动由 trial.ps1 自己灌）。
$ExcludeFilePatterns = @(
    "*.pyc", "*.pyo",
    "*.db", "*.db-journal", "*.db-wal", "*.db-shm",
    ".coverage",
    ".DS_Store", "Thumbs.db"
)

#: 排除的**文件名**（任何深度）。⚠️ git 自己的两个文件不进包：**包不是一个 git 仓库**，
#:    摆一份 ``.gitignore`` 在里面只会让人以为它还是。
$ExcludeFileNames = @(".gitignore", ".gitattributes")

#: ⚠️ **必须含**的清单（派单 Task 4 §1.7 ① 的前半）。⚠️ 它钉的是「包**能起**」：
#:    少任何一格，解包之后那一条命令就跑不起来，或跑起来是一份没有数据的空壳。
#:    ⚠️ 而 ``backend\data\`` 那 24 个指纹文件由 ``$MustContainDataCount`` 那一格
#:    **按数量**钉（逐个抄 24 个文件名到这里就是第二个所有者：改数据的人会漏改这里）。
$MustContain = @(
    "README.md",
    "backend\pyproject.toml",
    "backend\alembic.ini",
    "backend\app\main.py",
    "backend\migrations\env.py",
    "backend\scripts\demo_bootstrap.py",
    "backend\scripts\serve_app.py",
    "frontend\dist\index.html",
    # ⚠️ **Plan 09 Task 1 加的**：构建清单（spec §15 G22 的另一半 —— 「这份产物是
    #    哪一个 commit 构建的」从今天起可查）。⚠️ 它**本来就会**进包（``$IncludeRoots``
    #    含 ``frontend``、枚举用 ``Get-ChildItem -Force`` 含点文件、而两份排除清单都不
    #    匹配这个名字），故本行钉的是**另一件事**：少一份清单要**响亮地**失败，
    #    而不是让甲方拿到一份说不清出处的 ``dist``。
    #    ⚠️ 期望侧另有一份**独立**的字面量住在 ``backend/tests/test_package.py`` 的
    #    ``REQUIRED_ENTRIES``（两侧不同源，漂开时两条守卫一起红）。
    "frontend\dist\.build-manifest.json",
    "frontend\package.json",
    "frontend\vite.config.ts",
    "frontend\src\App.vue",
    "frontend\src\router\index.ts",
    "Document\2026-09-28-体育闭环原型-设计spec.md",
    "Document\2026-10-15-甲方试用说明书.md",
    "scripts\serve.ps1",
    "scripts\trial.ps1",
    "scripts\package.ps1"
)

#: ⚠️ ``backend\data\`` 下进包的文件数**下界**。实测那 24 个入库文件（四个数据指纹 +
#:    18 个模板指纹 + 两个 README 一类），故下界取 **24**：少了就说明有数据没进包，
#:    而一份缺了国标评分表的库会在离真因很远的地方炸（分层那一步读不出评分表）。
$MustContainDataCount = 24

#: ⚠️ **必须不含**的五格（派单 Task 4 §1.7 ① 的后半，逐字点名了这五个）。
#:    判据落在 **zip 的条目名**上（不是 staging）：那才是甲方拿到的东西。
#:    ⚠️ 每条都是一个**整段路径**的正则（``(^|/)名字(/|$)``），故 ``.gitignore``
#:    不会被 ``\.git`` 那条误伤（而它本来也在 $ExcludeFileNames 里）。
$ForbiddenEntryPatterns = @(
    '(^|/)\.git(/|$)',
    '(^|/)node_modules(/|$)',
    '(^|/)\.superpowers(/|$)',
    '(^|/)tools(/|$)',
    '\.db(-journal|-wal|-shm)?$'
)

#: ⚠️ 包大小与文件数的**四个界**（派单 Task 4 §1.7 ②）。⚠️ **上界才是这一格的牙**：
#:    它挡的是「必须不含的清单守卫漏掉」那一档 —— 一个 ``node_modules`` 是
#:    5 万个文件 / 200 MiB 以上，一个 ``.git`` 是几千个文件，一个
#:    ``tools\cloudflared.exe`` 是 55 MiB ⇒ 三个都会把下面某一格顶穿。
#:    取值的来历（实测本波交付时是 **339 个文件 / 约 9.8 MiB**；⚠️ 那个数会跟着仓库
#:    长，本处只是给下面四个界一个来历、**不是**要钉住它 —— 硬规矩 #111）：
#:      · 文件数上界 **2 000**（约 6 倍余量；而 node_modules 是 5 万 ⇒ 差 25 倍，抓得住）；
#:      · zip 字节上界 **48 MiB**（约 5 倍余量；而光一个 cloudflared.exe 就 55 MiB
#:        ⇒ 它**自己一个**就顶穿这一格，抓得住）。
#:    ⚠️ **下界只为挡「包被掏空」**（``$IncludeRoots`` 被清空 / 某一棵顶层树整棵没抄进来
#:    ⇒ 0 个文件、或只剩 scripts+README 的一两 MiB），⚠️ 刻意取得**很松**：
#:    「少一格该有的东西」由上面那份 ``$MustContain``（17 个**具体路径**）精确地挡，
#:    而下界取紧了就变成一条**易假红**的守卫（删掉一张截图就红），那不是它的活。
$MaxFiles = 2000
$MaxZipBytes = 48MB
$MinFiles = 150
$MinZipBytes = 2MB

#: ⚠️ 最长相对路径的上界。来历逐字见 .DESCRIPTION 的「长路径」那一段：
#:    PS 5.1 / .NET Framework 下两个压缩 API **都**读不了 > 260 字符的路径，
#:    而失效是**静默**的（产出半个包）。实测今天最长是 75，故上界取 200
#:    （留出 staging 与解包目录的前缀余量，而在撞到 260 之前就会响亮地失败）。
$MaxRelativePathLength = 200

if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot $DefaultOutDirName }
$Stamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$ZipPath = Join-Path $OutDir ($PackagePrefix + $Stamp + ".zip")

Write-Host "== 厦大体育数智系统 · 可分发试用包 =="
Write-Host "   repo      = $RepoRoot"
Write-Host "   落地目录  = $OutDir"
Write-Host "   包        = $ZipPath"
Write-Host "   staging   = $Stage（临时目录，退出时删）"

# ---------------------------------------------------------------------------
# ① 前置检查
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ① 前置检查 --"

$DistIndex = Join-Path $RepoRoot "frontend\dist\index.html"
if (-not (Test-Path $DistIndex)) {
    Write-Host ""
    Write-Host "   ⚠️ 缺 $DistIndex"
    Write-Host "      包里带的是**预构建**的前端产物，而它现在不在 ⇒ 打出来的包解包之后起不来"
    Write-Host "      （serve_app.py 会在装配期抛 FileNotFoundError）。"
    Write-Host "      ⚠️ 本脚本**刻意不替你构建**：「怎么构建」的唯一所有者是 scripts\serve.ps1 的 ②，"
    Write-Host "         一个打包脚本偷偷跑一次 npm run build 会让「包里那份产物是哪一次构建出来的」"
    Write-Host "         变成一件没人知道的事。请先跑一条，再重跑本脚本："
    Write-Host "        powershell -ExecutionPolicy Bypass -File scripts\serve.ps1"
    Write-Host "      （它自己判 dist 是不是比 src 旧、必要时构建；构建完 Ctrl-C 停掉即可。"
    Write-Host "       或直接在 frontend\ 里跑 npm run build。）"
    exit 1
}
$Manifest = Join-Path $RepoRoot "backend\pyproject.toml"
if (-not (Test-Path $Manifest)) {
    Write-Host ""
    Write-Host "   ⚠️ 缺 $Manifest：那是运行时依赖清单的唯一所有者（serve.ps1 的 ① 现场读它、"
    Write-Host "      并把它翻译成一条 python -m pip install -e backend 给人看）。没有它，"
    Write-Host "      解包之后那台机器上的人连「该装什么」都问不出来。"
    exit 1
}
foreach ($Root in $IncludeRoots) {
    if (-not (Test-Path (Join-Path $RepoRoot $Root))) {
        Write-Host ""
        Write-Host "   ⚠️ 进包清单里的 $Root 不在仓库根下：清单漂了，还是仓库被搬空了？"
        exit 1
    }
}
$BuiltAt = (Get-Item $DistIndex).LastWriteTime
Write-Host "   frontend\dist\index.html 在（构建戳 $BuiltAt）✓"
Write-Host "   backend\pyproject.toml 在 ✓   进包的顶层 $($IncludeRoots.Count) 项都在 ✓"
Write-Host "   ⚠️ 本脚本**不构建、不灌库**（两个所有者一个都不当；理由见 .DESCRIPTION）"

# ---------------------------------------------------------------------------
# ② 抄进 staging（⚠️ 逐文件 File.Copy = 原字节，一个字符都不改）
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ② 抄进 staging --"

if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Test-DirExcluded {
    param([string]$Name)
    if ($ExcludeDirNames -contains $Name) { return $true }
    foreach ($Suffix in $ExcludeDirSuffixes) {
        if ($Name.EndsWith($Suffix)) { return $true }
    }
    return $false
}

function Test-FileExcluded {
    param([string]$Name)
    if ($ExcludeFileNames -contains $Name) { return $true }
    foreach ($Pattern in $ExcludeFilePatterns) {
        if ($Name -like $Pattern) { return $true }
    }
    return $false
}

# ⚠️ **两份清单打架**就当场报、不猜（本波加的）。为什么要有这一道：进包清单是
#    **显式**的（五个顶层），而排除清单里的 ``.git`` / ``.superpowers`` / ``.trial`` /
#    ``dist-pack`` / ``tools`` 五个今天在**仓库根**下、不在这五个顶层里 ⇒ 它们是靠
#    进包清单挡住的，排除清单那五条是**第二道**（防的是「有人把 $IncludeRoots 放宽」）。
#    而没有这一道的话，「有人把 ``.superpowers`` 加进 $IncludeRoots」这一档会一路走到
#    ⑤ 才被那五条正则抓住 —— 报错在**压缩之后**，而真因在**两份清单互相矛盾**上
#    （离真因有一层）。故这里提前一步、把话说在点子上。
foreach ($Root in $IncludeRoots) {
    $Leaf = Split-Path $Root -Leaf
    if ((Test-Path (Join-Path $RepoRoot $Root) -PathType Container) -and (Test-DirExcluded -Name $Leaf)) {
        Write-Host ""
        Write-Host ("   ⚠️ 两份清单打架了：$Root 同时出现在**进包的顶层**与**排除的目录名**里。")
        Write-Host "      本脚本不敢猜哪一份是真的。⚠️ 而 .git / .superpowers / .trial / dist-pack / tools"
        Write-Host "      五个是**必须不含**的（它们是内部账本、版本历史、一条公网地址与一个 55 MB 的二进制），"
        Write-Host "      故要改的一定是**进包**那一侧。"
        # ⚠️ 这里**必须 throw 而不是 exit 1**：文件头那个 trap 兜的是**错误**，
        #    而 `exit` 不是错误 ⇒ 走 exit 的话 staging（十几 MiB）会留在 $env:TEMP 里。
        #    本波实测到过：6 个 pe_package_* 目录全是这一条路径留下的。
        throw "两份清单打架了（$Root）：请把它从 `$IncludeRoots 里拿掉，或从 `$ExcludeDirNames 里拿掉——⚠️ 而 .git / .superpowers / .trial / dist-pack / tools 五个是必须不含的。"
    }
    if ((Test-Path (Join-Path $RepoRoot $Root) -PathType Leaf) -and (Test-FileExcluded -Name $Leaf)) {
        Write-Host ""
        # ⚠️ 同上：throw 而不是 exit 1，于是那个 trap 会把 staging 收掉。
        throw ("两份清单打架了：$Root 是一个**文件**，而它撞上排除清单（$Leaf）。")
    }
}

$ExcludedDirs = @{}
$ExcludedFiles = @{}
$Copied = @()
$Pending = New-Object System.Collections.Stack
foreach ($Root in $IncludeRoots) {
    $Pending.Push(@{ Full = (Join-Path $RepoRoot $Root); Rel = $Root })
}
while ($Pending.Count -gt 0) {
    $Node = $Pending.Pop()
    if (Test-Path -LiteralPath $Node.Full -PathType Container) {
        foreach ($Child in (Get-ChildItem -LiteralPath $Node.Full -Force)) {
            $Rel = $Node.Rel + "\" + $Child.Name
            if ($Child.PSIsContainer) {
                if (Test-DirExcluded -Name $Child.Name) {
                    $ExcludedDirs[$Child.Name] = [int]$ExcludedDirs[$Child.Name] + 1
                    continue
                }
                $Pending.Push(@{ Full = $Child.FullName; Rel = $Rel })
            } else {
                if (Test-FileExcluded -Name $Child.Name) {
                    $ExcludedFiles[$Child.Name] = [int]$ExcludedFiles[$Child.Name] + 1
                    continue
                }
                $Pending.Push(@{ Full = $Child.FullName; Rel = $Rel })
            }
        }
    } else {
        $Destination = Join-Path $Stage $Node.Rel
        $Parent = Split-Path $Destination -Parent
        if (-not (Test-Path $Parent)) { New-Item -ItemType Directory -Force -Path $Parent | Out-Null }
        # ⚠️ File.Copy 是**原字节**拷贝：不过文本、不转行尾、不加不减 BOM。
        #    （「打包不该改行尾」那一格的机制就在这里；⑤ 还会逐条目对一次 sha256。）
        [System.IO.File]::Copy($Node.Full, $Destination, $true)
        $Item = Get-Item -LiteralPath $Destination
        $Copied += [pscustomobject]@{
            Rel   = $Node.Rel
            Bytes = $Item.Length
            # ⚠️ 源文件的改动时刻：④ 那一步把它写进条目的 LastWriteTime
            #    （逐字理由见 .DESCRIPTION 的「分隔符」那一段最后一条）。
            Stamp = (Get-Item -LiteralPath $Node.Full).LastWriteTime
        }
    }
}

$TotalBytes = ($Copied | Measure-Object -Property Bytes -Sum).Sum
if ($Copied.Count -lt 1) { throw "一个文件都没抄进 staging（$Stage）：进包清单或排除清单被改坏了。" }
Write-Host "   抄了 $($Copied.Count) 个文件、$TotalBytes B（$([math]::Round($TotalBytes / 1MB, 2)) MiB）"

# ---------------------------------------------------------------------------
# ③ 复核 staging
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ③ 复核 staging --"

foreach ($Required in $MustContain) {
    if (-not (Test-Path (Join-Path $Stage $Required))) {
        throw "包里缺了 $Required（**必须含**的清单里的一格）：少了它，解包之后那一条命令跑不起来、或跑起来是一份空壳。"
    }
}
$DataFiles = @(Get-ChildItem (Join-Path $Stage "backend\data") -File -Recurse -ErrorAction SilentlyContinue)
if ($DataFiles.Count -lt $MustContainDataCount) {
    throw "backend\data 下只抄到 $($DataFiles.Count) 个文件（下界 $MustContainDataCount）：国标评分表 / 常模 / 处方模板没进包，而一份缺了它们的库会在离真因很远的地方炸（分层那一步读不出评分表）。"
}
$Longest = ($Copied | Sort-Object { $_.Rel.Length } -Descending | Select-Object -First 1)
if ($Longest.Rel.Length -gt $MaxRelativePathLength) {
    throw "最长的相对路径是 $($Longest.Rel.Length) 字符（$($Longest.Rel)），超过上界 $MaxRelativePathLength：PS 5.1 / .NET Framework 下两个压缩 API 都读不了 > 260 字符的路径，而失效是**静默**的（会产出半个包）。请把那个目录改浅一点。"
}
Write-Host "   **必须含** $($MustContain.Count) 格逐个在场 ✓   backend\data 下 $($DataFiles.Count) 个文件（下界 $MustContainDataCount）✓"
Write-Host "   最长相对路径 = $($Longest.Rel.Length) 字符（$($Longest.Rel)）；上界 $MaxRelativePathLength ✓"
if ($Copied.Count -lt $MinFiles -or $Copied.Count -gt $MaxFiles) {
    throw "文件数 $($Copied.Count) 落在 [$MinFiles, $MaxFiles] 之外：少了 = 进包清单被改坏了，多了 = 有东西（最可能是 node_modules 或 .git）漏进了包。"
}
Write-Host "   文件数 $($Copied.Count) 落在 [$MinFiles, $MaxFiles] ✓"

# ---------------------------------------------------------------------------
# ④ 压成 zip（.NET 的 ZipFile；⚠️ 为什么不是 Compress-Archive 见 .DESCRIPTION）
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ④ 压成 zip --"

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
# ⚠️ **逐个条目自己写**，不用 CreateFromDirectory：那一档在 PS 5.1 / .NET Framework 下
#    会把条目名里的分隔符写成 Windows 的反斜杠，而 ZIP 的规范要正斜杠
#    （实测与逐字理由见 .DESCRIPTION 的「分隔符」那一段）。
#    ⚠️ 而条目**按相对路径排序**写入：于是同一棵 staging 树打出来的包，
#    条目顺序是确定的（两个包之间只剩下时间戳那一格不同，比对起来看得清）。
$ZipStream = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::CreateNew)
$ZipWrite = New-Object System.IO.Compression.ZipArchive($ZipStream, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($Item in ($Copied | Sort-Object -Property Rel)) {
        $SourceFile = Join-Path $Stage $Item.Rel
        # ⚠️ 条目名一律正斜杠（这一行就是本文件不用那两个 API 的全部理由）。
        $EntryName = $Item.Rel -replace '\\', '/'
        $Entry = $ZipWrite.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $Entry.LastWriteTime = $Item.Stamp
        $InStream = [System.IO.File]::OpenRead($SourceFile)
        try {
            $OutStream = $Entry.Open()
            try { $InStream.CopyTo($OutStream) } finally { $OutStream.Dispose() }
        } finally { $InStream.Dispose() }
    }
} finally {
    $ZipWrite.Dispose()
    $ZipStream.Dispose()
}
$Stopwatch.Stop()
if (-not (Test-Path $ZipPath)) { throw "压缩没有抛，而 $ZipPath 仍然不在。" }
$ZipBytes = (Get-Item $ZipPath).Length
Write-Host "   $ZipPath"
Write-Host "   $ZipBytes B（$([math]::Round($ZipBytes / 1MB, 2)) MiB），用了 $([math]::Round($Stopwatch.Elapsed.TotalSeconds, 1)) 秒"
if ($ZipBytes -gt $MaxZipBytes) {
    throw "包 $ZipBytes B 超过上界 $MaxZipBytes：有东西漏进了包（最可能是 node_modules 的几万个小文件，或 tools\cloudflared.exe 那 55 MiB —— 光它一个就顶穿这一格）。"
}
if ($ZipBytes -lt $MinZipBytes) {
    throw "包只有 $ZipBytes B（下界 $MinZipBytes）：进包清单被改坏了，或压缩产出了半个包。"
}
Write-Host "   包大小落在 [$([math]::Round($MinZipBytes / 1MB, 1)) MiB, $([math]::Round($MaxZipBytes / 1MB, 1)) MiB] ✓"

# ---------------------------------------------------------------------------
# ⑤ **打开那个 zip** 再复核一遍（⚠️ 判据落在甲方拿到的那一份上，不是 staging）
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ⑤ 复核 zip 本身 --"

$Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $EntryNames = @($Archive.Entries | ForEach-Object { $_.FullName })

    # --- ⑤ a  必须不含的五格（逐条正则打在**条目名**上）---
    foreach ($Pattern in $ForbiddenEntryPatterns) {
        $Hits = @($EntryNames | Where-Object { $_ -match $Pattern })
        if ($Hits.Count -gt 0) {
            throw ("包里出现了**必须不含**的东西（正则 $Pattern，撞到 " + $Hits.Count + " 个，头三个是 " + (($Hits | Select-Object -First 3) -join "、") + "）")
        }
    }
    Write-Host "   **必须不含**的 $($ForbiddenEntryPatterns.Count) 格逐条为 0 ✓（.git / node_modules / .superpowers / tools / *.db）"

    # --- ⑤ b  必须含的那几格也在**条目名**里（⚠️ zip 里的分隔符是 /）---
    foreach ($Required in $MustContain) {
        $Entry = $Required -replace '\\', '/'
        if ($EntryNames -notcontains $Entry) {
            throw "zip 里缺了条目 $Entry（staging 里有、zip 里没有 ⇒ 压缩那一步漏了它）"
        }
    }
    Write-Host "   **必须含**的 $($MustContain.Count) 格在 zip 的条目名里逐个在场 ✓"

    # --- ⑤ c  条目数与 staging 对账 ---
    if ($EntryNames.Count -ne $Copied.Count) {
        throw "zip 里有 $($EntryNames.Count) 个条目，而 staging 里抄了 $($Copied.Count) 个文件：两边对不上。"
    }
    Write-Host "   条目数 $($EntryNames.Count) == staging 的文件数 $($Copied.Count) ✓"

    # --- ⑤ d ⚠️ 逐条目对 sha256：证明「打包一个字节都没改」（含行尾与 BOM）---
    $Sha = [System.Security.Cryptography.SHA256]::Create()
    $Compared = 0
    foreach ($Entry in $Archive.Entries) {
        if ($Entry.Name.Length -eq 0) { continue }   # 目录条目
        $Source = Join-Path $Stage ($Entry.FullName -replace '/', '\')
        if (-not (Test-Path -LiteralPath $Source)) { throw "zip 里的条目 $($Entry.FullName) 在 staging 里没有对应文件" }
        $EntryStream = $Entry.Open()
        try {
            $Left = [System.BitConverter]::ToString($Sha.ComputeHash($EntryStream))
        } finally { $EntryStream.Dispose() }
        $Right = [System.BitConverter]::ToString($Sha.ComputeHash([System.IO.File]::OpenRead($Source)))
        if ($Left -ne $Right) {
            throw "条目 $($Entry.FullName) 的 sha256 与 staging 里那一份**不同**：压缩改了字节（最可能的一档是行尾被当文本转换过）。"
        }
        $Compared += 1
    }
    Write-Host "   逐条目 sha256 对账：$Compared 个条目**全部**与 staging 里的原文件逐字相同 ✓"
    # ⚠️ 而分隔符那一格由 ⑤ e 单独钉（它读的是**条目名的原始字符**，
    #    一个反斜杠都不许有；理由逐字见 .DESCRIPTION）。
    Write-Host "   ⚠️ 那一格同时钉住了行尾与 BOM：.ps1 仍是 UTF-8+BOM+CRLF、Document\**\*.md 仍是 CRLF、"
    Write-Host "      backend\data\** 仍是 LF —— 打包**一个字节都没改**（④ 那一步是原字节流拷贝）。"

    # --- ⑤ e ⚠️ 条目名一律正斜杠（ZIP 的规范；两个现成 API 在 PS 5.1 下都写反斜杠）---
    $BackslashEntries = @($EntryNames | Where-Object { $_.Contains([string][char]92) })
    if ($BackslashEntries.Count -gt 0) {
        throw ("zip 里有 " + $BackslashEntries.Count + " 个条目的名字带着**反斜杠**（头三个是 " + (($BackslashEntries | Select-Object -First 3) -join "、") + "）：ZIP 的规范要正斜杠，而带着反斜杠的包在 Linux 的 unzip 下解出来的是一个名字里带反斜杠的**平文件**、不是目录树。④ 那一步的 -replace 被改坏了？")
    }
    $NestedEntries = @($EntryNames | Where-Object { $_.Contains('/') })
    Write-Host ("   条目名的分隔符：反斜杠 0 个 ✓，而带正斜杠的有 " + $NestedEntries.Count + " 个（⇒ 上面那一格不是因为包里压根没有子目录）")
} finally {
    $Archive.Dispose()
}

# ---------------------------------------------------------------------------
# ⑥ 打印：进了什么 / 排除了什么 / 解包之后怎么起
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "-- ⑥ 进了什么 / 排除了什么 --"

Write-Host "   进了什么（按顶层分组）："
foreach ($Group in ($Copied | Group-Object { ($_.Rel -split '\\')[0] } | Sort-Object { -($_.Group | Measure-Object -Property Bytes -Sum).Sum })) {
    $Sum = ($Group.Group | Measure-Object -Property Bytes -Sum).Sum
    Write-Host ("     {0,-14} {1,5} 个文件 {2,10} B（{3,6} MiB）" -f $Group.Name, $Group.Count, $Sum, [math]::Round($Sum / 1MB, 2))
}
Write-Host ""
Write-Host "   排除了什么（⚠️ 目录名撞到就整棵子树不进包；括号里是本次实测撞到的次数）："
foreach ($Name in ($ExcludedDirs.Keys | Sort-Object)) {
    Write-Host ("     目录 {0,-18} × {1}" -f $Name, $ExcludedDirs[$Name])
}
foreach ($Name in ($ExcludedFiles.Keys | Sort-Object)) {
    Write-Host ("     文件 {0,-18} × {1}" -f $Name, $ExcludedFiles[$Name])
}
Write-Host "   排除清单（唯一所有者是本文件上面那几个数组）："
Write-Host ("     目录名 " + ($ExcludeDirNames -join "、"))
Write-Host ("     目录名后缀 " + ($ExcludeDirSuffixes -join "、") + "；文件名 " + ($ExcludeFileNames -join "、"))
Write-Host ("     文件通配 " + ($ExcludeFilePatterns -join "、"))
Write-Host ""
$Existing = @(Get-ChildItem $OutDir -Filter ($PackagePrefix + "*.zip") -File -ErrorAction SilentlyContinue)
$ExistingBytes = ($Existing | Measure-Object -Property Length -Sum).Sum
Write-Host ("   $OutDir 里现在有 $($Existing.Count) 个包、共 $([math]::Round($ExistingBytes / 1MB, 1)) MiB。")
Write-Host "   ⚠️ 本脚本**不删旧的包**：那是你的产物，一个打包脚本替你做删除决定是静默的那一类事故。"
Write-Host ""
Write-Host "-- ⑥ b  这个包发给甲方之后，他们那边怎么起 --"
Write-Host "   ① 解包到一个**空目录**里（zip 的根就是仓库根的形状：backend\ frontend\ Document\ scripts\ README.md）。"
Write-Host "   ② 那台机器上要有的：**只有 Python 3.11 或更新**（⚠️ 不需要 Node、不需要 npm install、不需要 git）。"
Write-Host "   ③ 装运行时依赖（⚠️ 一条命令；清单的唯一所有者是包里的 backend\pyproject.toml）："
Write-Host "        python -m pip install -e backend"
Write-Host "      ⚠️ 少了什么，包里那条命令会**自己检查并打印这一行**（它刻意不替你 pip install）。"
Write-Host "   ④ 在**解包出来的那个目录**里跑一条命令（灌一份全新试用库 → 起服务 → 打印链接与账号）："
Write-Host "        powershell -ExecutionPolicy Bypass -File scripts\trial.ps1"
Write-Host "      ⚠️ 它缺省透传 -SkipBuild，故一次都不查 node、一次都不调 npm（用的是包里预构建的 frontend\dist）。"
# ⚠️ 改前这里写死「60 人」（Plan 07 Task 8 · 终审 S4-3 的同族自查）：本脚本**不灌库、
#    不起服务**（``test_the_packager_never_builds_seeds_serves_or_installs_anything``
#    钉着的那四件事），故它手上既没有库、也没有 ``/api/health`` 可读 —— 那一档下最诚实的
#    做法是**不印那个数**（它的唯一所有者是 ``demo_bootstrap.py`` 的 ``--students``，
#    而运行时读它的唯一所有者是 ``/api/health``）。
Write-Host "      ⚠️ 要重置回一份干净的仿真库：Ctrl-C 停掉，再跑同一条并加 -Reset。"
Write-Host "         （人数由 demo_bootstrap.py 的 --students 决定；服务起来之后，页面上那条告示里的 N 是从库里真数出来的。）"
Write-Host "   ⑤ 给试用者念的那一份是包里的 Document\2026-10-15-甲方试用说明书.md。"
Write-Host "   ⚠️ 包里**不含**隧道工具（tools\ 在排除清单里），故包里那份 scripts\tunnel.ps1"
Write-Host "      在你们机器上会回落到 ssh 那一支（本波实测：找不到 cloudflared 时它选 ssh，"
Write-Host "      而那一支的成功路径至今未验证过，见它的 .PARAMETER Backend）。"
Write-Host "      ⚠️ **公网链接是我方这一侧的事**：要一条公网可达的地址请找我方开；"
Write-Host "      自己取一份可信 cloudflared 的办法见说明书 §2 ①。"
Write-Host ""

# ---------------------------------------------------------------------------
# 收尾：staging 是自己造的垃圾，自己收（⚠️ zip 留着）
# ---------------------------------------------------------------------------
if (Test-Path $Stage) {
    # ⚠️ 走上面那个**唯一**的所有者（S4-16）：改前这里与 ``trap`` 里各有一份逐字相同的
    #    ``Remove-Item … -ErrorAction SilentlyContinue``，而两份都会部分失败。
    if (Remove-Staging) {
        Write-Host "   收尾：staging $Stage 已删掉（包留在 $ZipPath）"
    } else {
        $Left = @(Get-StagingLeftovers)
        Write-Host ("   ⚠️ staging 删不掉：" + $Stage + "（重试 3 次之后仍剩 " + $Left.Count + " 个文件：" + (($Left | Select-Object -First 5) -join "、") + "）")
        Write-Host "      有进程持有它？请手工删。⚠️ 包**已经产出**了，这一格只影响 $env:TEMP 里的残渣。"
    }
}
Write-Host ""
Write-Host "   ✓ 包已产出：$ZipPath"
exit 0
