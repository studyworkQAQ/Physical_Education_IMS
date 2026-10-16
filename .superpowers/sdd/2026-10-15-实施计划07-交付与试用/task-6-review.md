# 实施计划 07 · Task 6 —— 全分支终审报告（只读、对抗性）

> 2026-10-16 · 复核席：Task 6（全分支终审）。**本席只读**：没有改仓库里任何一个文件、
> 没有 commit / push / 建分支。唯一的写入是本文件，以及 `$env:TEMP\p07t6\` 下的探针与
> 解包目录（跑完已删净并复验）。
> ⚠️ 本文件刻意**不印自己的字节数 / sha256**（不动点问题）。

---

## ① 复核范围 · 环境 · 开工五格与收尾五格 · 我起了哪些服务

### 1.1 复核范围（自己核实过，不是抄派单）

| 格 | 实测 |
|---|---|
| 分支 / HEAD | `main` / `a45a3f01421af53c16b858cb46983bcf50dfdc15` |
| 起点 | `fedf24f`（Plan 06 Task 15 结案 + 🏁 Plan 06 全计划结案） |
| `git log --oneline fedf24f..HEAD` | **26** 个 commit（含 1 个 merge：`6a6ac1f`） |
| `git diff --shortstat fedf24f..HEAD` | **38 files changed, 13585 insertions(+), 144 deletions(-)** |
| 开工时 `git status --porcelain` | 空（工作树干净） |
| 两条支线 | `p07/trial-guide`（`a35babd`→`65c5885`，说明书）· `p07/trial-defects`（`b86645d`→`65e3bb2`，缺陷修复），在 `6a6ac1f` 合流 |

26 个 commit 的波次归属（按提交时刻）：Task 1+2（`a40db5a`…`71d1e4f`）· Task 3
（`dd667cc`…`42031de`）· Task 5（`a35babd`…`65c5885`）· Task 5b（`b86645d`…`65e3bb2`）·
Task 4（`f3f16a6`…`a45a3f0`）。

### 1.2 环境

`node v24.19.0` · `Python 3.11.1`（`C:\Python\python.exe`，无 venv）· `pip 22.3.1` ·
fastapi **0.141.1** / starlette **1.7.0** / SQLAlchemy **2.1.3** / pydantic **2.13.5** /
alembic **1.20.0** / pandas **3.0.6** / numpy **2.4.6** · `node` 在
`C:\Program Files\nodejs\node.exe` · 局域网 IPv4 **`192.168.31.11`（WLAN，本机数到的唯一一个）** ·
PowerShell 5.1。⚠️ 派单说的「本机到 Cloudflare 边缘的 QUIC/UDP 路径今天是断的」本席
**没有复验**（那要打断 UDP 出网，本席没有那个手段，与 Task 4 如实交代的同一格）。

### 1.3 开工五格（2026-10-16 03:47–03:52 量）

| # | 格 | 开工实测 |
|---|---|---|
| ① | uvicorn PID **45156** | 活着，`python`，StartTime `2026-10-16 0:36:05`；`netstat` 命中 `TCP 127.0.0.1:8030 LISTENING 45156` |
| ② | cloudflared PID **45016** | 活着，StartTime `2026-10-16 0:39:43`，Path `…\Physical_Education_ims\tools\cloudflared.exe` |
| ③ | `backend/pe_trial.db` | **1 589 248 B** / sha256[:16] **`40D7B5F78A7C36CB`** / mtime `2026-10-15 19:43:25`（⚠️ 被 45156 持有，`Get-FileHash` 读不动，本席改用 `[System.IO.File]::Open(…,'Read','ReadWrite')` 共享读算的） |
| ④ | `frontend/dist` | **29 个文件 / 687 224 B**；五个产物哈希 `index-DrDy4l90.css` 65 374 B `82F1894CCB69C169` · `index-DYNl778Q.js` 175 589 B `364F903607EDCDAB` · `StudentDetail-Bw86stl2.js` 43 595 B `F07F8F27D9C54568` · `AuditLogList-CqjFciNR.js` 9 553 B `7C3EBE46550A4B48` · `ResourceIndex-DqalY3wm.js` 9 144 B `588A301421A96F2F`；全部 mtime `2026-10-16 00:36:04` |
| ⑤ | 公网 URL | `https://paris-condo-terms-composed.trycloudflare.com/api/health` → **200** `{"status":"ok","tables":28,"students":60,"trial":true}` |

### 1.4 收尾五格（2026-10-16 09:41–09:49 量）

| # | 格 | 收尾实测 | 与开工逐字相同？ |
|---|---|---|---|
| ① | PID 45156 | 活着，StartTime `2026-10-16 0:36:05`，`TCP 127.0.0.1:8030 LISTENING 45156` | ✅ |
| ② | PID 45016 | 活着，StartTime `2026-10-16 0:39:43` | ✅ |
| ③ | `pe_trial.db` | **1 589 248 B** / **`40D7B5F78A7C36CB`** / mtime `2026-10-15 19:43:25` | ✅ 逐字相同 |
| ④ | `frontend/dist` | **29 个文件 / 687 224 B**，五个哈希逐个与开工相同（见 §1.3） | ✅ 逐字相同 |
| ⑤ | 公网 URL | ❌ **没回 200**：`Invoke-WebRequest` 三发全失败（`基础连接已经关闭: 发送时发生错误`，各约 7.2 s），`Resolve-DnsName` → **`DNS name does not exist`**；等 45 s 再打一发仍然 NXDOMAIN | ❌ **变了** |
| 附 | `.trial\public-url.txt` | 1 472 B / sha256[:16] `0AB5FAF553A5A1E7` | ✅ 逐字未变（本席一次都没写它） |
| 附 | `git status --porcelain` | 只有本报告一个未跟踪文件 | ✅ |

⚠️⚠️ **第 ⑤ 格是本席唯一没能「逐字未变」交回的一格，而它不是本席造成的**，取证如下（这一格
同时是本波最有价值的**现场证据**，见 §⑥ 的 S2-2 与 S3-6）：

* 本地 `http://127.0.0.1:8030/api/health` → **200** `{"status":"ok","tables":28,"students":60,"trial":true}` ⇒ **服务没死**；
* 本机出网正常：`https://www.cloudflare.com/cdn-cgi/trace` → **200**（`fl=1164f36`）⇒ **不是本机断网**；
* `trycloudflare.com` 本身解析正常（AAAA `2606:4700::6810:e684`）⇒ **不是 DNS 整体故障**，是**那一个 quick tunnel 主机名被边缘撤掉了**；
* `cloudflared` PID 45016 **仍然活着**（StartTime 未变）。
* ⇒ 形状逐字是 spec §13.17 记的那一档：**进程在、链接死**。本席对那条 URL 只发过**两发匿名
  `GET /api/health`**（开工一发、收尾一发），一次都没登录、一次都没写、一次都没碰
  PID 45016 / 45156 / `.trial\`。

### 1.5 本席起过哪些服务（**全部已停并复验**）

| 实例 | 端口 | 档 | 库 | 起来做什么 | 收尾 |
|---|---|---|---|---|---|
| A | **8041** | `PE_TRIAL=1` + dev | 解包目录里 trial.ps1 自己灌的 `…\unpack\backend\pe_trial.db` | F3「一条命令起服务」、F4 只读核验、F2 试用档一侧 | 已停（PID 544 已杀） |
| B | **8042** | `PE_TRIAL=0` + dev | `…\p07t6\notrial.db`（A 那个库的 `sqlite3 .backup()` 副本） | F2 两档鉴权逐字对比、F6 写入实测、登录锁定取证 | 已停（PID 3688 已杀） |
| C | **8043** | `-Lan` + dev | `…\p07t6\landev.db`（副本） | F2 `-Lan` 四格 | 已停 |
| D | **8044** | `-Lan` + `PE_ENV=prod` | `…\p07t6\lanprod.db`（副本） | F2 `-Lan`+prod 的裁定 | 已停 |
| E | **8045** | 含空格与中文的路径 | `…\p07t6\体育系统 试用\backend\pe_trial.db` | F3 路径形状（**它自己就失败退出了**，见 S1-1） | 已退出 |

复核：`Get-NetTCPConnection -State Listen` 在 **8040–8050 区间 0 个 listener**；
`$env:TEMP\p07t6` 已删净（`Test-Path` = False）；本席自己产生的 3 个
`pe_package_*` staging 目录已删并复验。⚠️ 刻意**没动**两个不属于本席的：
`pe_trial_csv_41684`（mtime `2026-10-15 19:43:22`，是 **8030 那个服务正在用的
`PE_CSV_DIR`**，删了会让甲方那一份的 `POST /api/pipeline/run-daily` 当场失败）与
`pe_package_12228`（mtime `2026-10-16 03:38:47`，在本席开工之前就在）。

⚠️ 本席**一次都没有**：杀/重启 45156 或 45016、对 8030 或那条公网 URL 发任何登录/写入
请求（只有匿名 `GET /api/health`）、`-Reset`、写 `pe_trial.db`、跑 `npm run build`、跑
`tunnel.ps1`。

---

## ② F1 · 守卫的强度（23 条定点变异）

### 2.1 基线

六个 Plan 07 守卫文件先跑绿：`test_package.py + test_trial.py + test_tunnel.py +
test_deploy.py` = **55 passed / 4.23 s**；`test_serve.py + test_main.py` =
**66 passed / 8.76 s**（一律 `--no-cov -q -p no:cacheprovider`）。合计 **121 条**。

### 2.2 变异结果表（23 条；每条改一处 → 跑守卫 → 从 TEMP 里的备份逐字节还原 → 复验 sha）

| # | 变异（被测文件） | 跑的守卫 | 预期 | 实测 | 还原 |
|---|---|---|---|---|---|
| P1 | `package.ps1`：把 `".superpowers"` 从 `$ExcludeDirNames` 拿掉（= Task 4 自报的 **M2'**） | 全 6 个（121 条） | GREEN | **GREEN**（121 passed） | ✅ |
| P2 | `package.ps1`：把 `".trial"` 从 `$ExcludeDirNames` 拿掉（本席自己找的同族第二个） | 全 6 个 | GREEN | **GREEN**（121 passed） | ✅ |
| P3 | `package.ps1`：把 `"dist-pack"` 从 `$ExcludeDirNames` 拿掉 | 全 6 个 | GREEN | **RED**（1 failed / 120 passed） | ✅ |
| P4 | `package.ps1`：把 `"*.db"` 从 `$ExcludeFilePatterns` 拿掉 | `test_package.py` | RED | **RED**（4 passed / 4 errors） | ✅ |
| P5 | `package.ps1`：`$MustContainDataCount = 24` → `20`（放宽下界） | `test_package.py` | ? | **GREEN**（8 passed） | ✅ |
| P6 | `package.ps1`：`$MaxFiles = 2000` → `200000`（放宽上界） | `test_package.py` | ? | **GREEN**（8 passed） | ✅ |
| P7 | `package.ps1`：「两份清单打架」那条 `throw` 退回 `Write-Host`（= **撤销 `8304175`**） | `test_package.py` | ? | **GREEN**（8 passed） | ✅ |
| P8 | `package.ps1`：把 `$MustContain` 里 `"frontend\src\App.vue"` 那一行删掉 | `test_package.py` | ? | **GREEN**（8 passed） | ✅ |
| S1 | `serve.ps1`：缺省 `-Port 8020` → `8030`（与 trial.ps1 撞） | `test_serve.py` | RED | **RED**（1 failed / 39 passed） | ✅ |
| S2 | `serve.ps1`：`$BindAddress` 不看 `-Lan`、一律 `0.0.0.0` | `test_serve.py` | RED | **RED** | ✅ |
| S3 | `serve.ps1`：删掉强制清 `PE_ALLOW_HEADER_IDENTITY` 那一句 | `test_serve.py` | RED | **RED** | ✅ |
| S4 | `serve.ps1`：node 检查所在那个 `if ($NeedBuild)` → `if ($false)` | `test_serve.py` | ? | **RED** | ✅ |
| T1 | `trial.ps1`：`backend\pe.db` 那道禁区守卫 → `if ($false)` | `test_trial.py` | RED | **RED**（1 failed / 11 passed） | ✅ |
| T2 | `trial.ps1`：缺省 `-Port 8030` → `8020` | `test_trial.py` | RED | **RED** | ✅ |
| T3 | `trial.ps1`：不再透传 `-SkipBuild` | `test_trial.py` | RED | **RED** | ✅ |
| T4 | `trial.ps1`：`$TrialDbName = "pe_trial.db"` → `"pe_demo.db"` | `test_trial.py` | RED | **RED** | ✅ |
| D1 | `deploy.py`：`is_trial()` 多接受一个 `"true"` | `test_deploy.py` | RED | **RED**（1 failed / 16 passed） | ✅ |
| D2 | `main.py`：`/api/health` 摘掉 `"trial": deploy.is_trial()` | `test_main.py` | RED | **RED**（3 failed / 23 passed） | ✅ |
| U1 | `tunnel.ps1`：`-Protocol` 摘掉 `[ValidateSet('auto','quic','http2')]` | `test_tunnel.py` | RED | **RED**（1 failed / 17 passed） | ✅ |
| U2 | `tunnel.ps1`：`$EdgeDeadStatus = 530` → `599` | `test_tunnel.py` | RED | **RED** | ✅ |
| U3 | `tunnel.ps1`：cloudflared 的 `Arguments` 里摘掉 `'--protocol', $ChosenProtocol` | `test_tunnel.py` | RED | **RED** | ✅ |
| U4 | `tunnel.ps1`：`[int]$Watchdog = 0` → `60`（缺省从「关」变「开」） | `test_tunnel.py` | RED | **RED** | ✅ |
| U5 | `tunnel.ps1`：`$WatchdogAlarmAfter = 3` → `1` | `test_tunnel.py` | ? | **RED** | ✅ |

**23 条里 17 条红、6 条绿**；**23 条全部逐字节还原**，收尾 `git status --porcelain` = 空。

### 2.3 Task 4 那个 **M2'** 自述：**为真**

自述是「把 `.superpowers` 从排除清单拿掉不影响包内容，因为它不在进包的五个顶层里」。
本席实测 **P1 = GREEN（121 条全过）**，而**理由也与自述一致**：`package.ps1:165-171` 的
`$IncludeRoots` 只有 `backend / frontend / Document / scripts / README.md` 五个，
`.superpowers` 在**仓库根**下 ⇒ 它是被**进包清单**挡住的，`$ExcludeDirNames` 里那一条是
`package.ps1:347-353` 自己逐字交代的**第二道**（防「有人把 `$IncludeRoots` 放宽」）。
⚠️ 而**真守卫不靠它**：`test_package.py:66` 的
`FORBIDDEN_SEGMENTS = (".git", "node_modules", ".superpowers", "tools")` 是**测试侧的字面量**，
直接判 zip 中央目录的条目名（`_central_directory_names()` 不经任何解压库，
理由在 `test_package.py:152-159`：`zipfile` 会把 `\` 归一成 `/`，用它判分隔符是假绿）。

### 2.4 本席自己找的**同族假变异**

* **P2（`.trial`）= GREEN** —— 与 M2' 完全同形（在仓库根、不在五个顶层里），**这是本席独立找到的第二个**。
* ⚠️ 而**同族的第三个（P3，`dist-pack`）却是红的**，理由有意思：`test_package.py:248`
  钉的是 `statements.count('"dist-pack"') == 2`（一次是 `$DefaultOutDirName` 的所有者赋值、
  一次是排除清单里那一条防御性的第二道）⇒ 「拿掉排除清单里那一条」会把计数打到 1 而当场红。
  **同一个形状的三个名字，两个绿一个红**：不是守卫不一致，而是 `dist-pack` 另有「一个所有者 +
  `.gitignore` 逐字同意」那一族守卫顺带钉住了它的**出现次数**。
* **P5 / P6 / P8 = GREEN** —— 放宽 `package.ps1` **脚本内**那三份自检（数据文件数下界、
  文件数上界、`$MustContain` 的 17 项）没有任何守卫会红。⚠️ **这不构成假守卫**：
  `test_package.py:69-72` 逐字写着「期望侧是**字面量**、不从 `package.ps1` 的 `$MustContain`
  读回来跟自己比（那是同源断言）。⚠️ 而它刻意与脚本里那一份**不完全相同**：两侧各自独立地
  钉一次，漂开时两条守卫一起红」，而 `REQUIRED_ENTRIES` / `MAX_FILES = 2000` /
  `assert len(data) >= 24` 三个都是**测试侧字面量**。⇒ 放宽脚本内那一份副本，测试侧那一份
  仍然守着实物；只是「脚本内的自检被悄悄放宽」这件事**没人钉**。记 **S4-9**。
* **P7 = GREEN** —— **撤销 `8304175` 那一条 fix（`throw` → `Write-Host`）没有任何守卫会红**。
  那一条 fix 修的是「两份清单打架时走 `exit 1` ⇒ `trap` 不触发 ⇒ staging 泄漏」，
  而今天 `$IncludeRoots ∩ $ExcludeDirNames = ∅` ⇒ **那条路径结构上不可达**，
  于是它是一条**没有守卫、且今天不可达**的修复。记 **S4-9**。

### 2.5 自指守卫搜寻：**没有找到**

按「期望侧与被测侧同源 ⇒ 永绿」这个形状逐个抽验了本波新增的守卫，**六处都是两侧不同源**：

| 守卫 | 期望侧 | 被测侧 |
|---|---|---|
| `test_package.py` 的包内容清单 | 测试文件的 `REQUIRED_ENTRIES` / `FORBIDDEN_SEGMENTS` **字面量** | zip **中央目录的原始字节** |
| `test_package.py` 的 `dist-pack` 一个所有者 | 测试侧 `OUT_DIR_NAME = "dist-pack"` + `.gitignore` 的**文件内容** + `git check-ignore`（**三侧**） | `package.ps1` 的代码段 |
| `test_serve.py::test_the_runtime_dependency_list_is_parsed_from_the_manifest_not_copied` | Python 的 **`tomllib`** 解析同一份 manifest | `serve.ps1` 里那段 **PowerShell** 解析（切出来在 `tmp_path` 里真跑） |
| `test_serve.py` 的强制清 `PE_ALLOW_HEADER_IDENTITY` | **从 `demo.ps1` 现场切出那一段** | `serve.ps1` 里逐字有它 |
| `test_tunnel.py::test_the_protocol_flag_is_passed_through_verbatim_in_all_three_tiers` | 测试里的**字面量命令行** | 把 `Resolve-TunnelBackend` **切出来在干净 PowerShell 里真跑三档**（+ 反空转第 ② 拍：三档拼出来的命令行**互不相同**） |
| `test_trial.py` 的 `pe_trial.db` 名字 | `.gitignore` 的**文件内容** + git 自己 | `trial.ps1` 的 `$TrialDbName` |

⚠️ 特别核了 `test_tunnel.py:810-874`：它**不是**读字符串，而是真的把函数切出来执行、
断言三档各拼出 `--protocol <原值>`、`--protocol` 排在 `--logfile` **之前**、
孤儿标记 `pe_tunnel_<Port>` 一个参数都没少、且 **ssh 那一支一个 `--protocol` 都没有**。
U1 / U3 两条变异都把它打红 ⇒ 它**有牙**。

---

## ③ F2 · 试用档的正确性与**安全**

### 3.1 ⚠️ `PE_TRIAL` 与权限**正交**：**没有放宽任何一格**

做法：两个实例、**同一份库内容**（B 是 A 那个库的 `sqlite3 .backup()` 副本，
`journal_mode = delete` 故备份一致）、同一套 39 个请求、逐格比
「状态码 + 响应体 sha256[:12] + 字节数」。

**39 格里只有 2 格不同，两格都可解释：**

| 差异格 | A（`PE_TRIAL=1`，8041） | B（`PE_TRIAL=0`，8042） | 判定 |
|---|---|---|---|
| `GET /api/health` | 200 / **54 B** / `c7a16fd52213` | 200 / **55 B** / `6c7600006173` | ✅ **就是 `trial` 那一格**（`"trial":true` 11 字符 vs `"trial":false` 12 字符 ⇒ 差 1 字节，与实测的 54/55 逐字吻合） |
| `GET /api/audit-logs`（管理员） | 200 / **1061 B** / `a1ad8e0c0b56` | 200 / **1061 B** / `804f7ae57de6` | ✅ **同状态码、同字节数**；逐格 diff 之后**只有 `at` 一列不同**（两个实例各自的登录时刻），`total=8` / `limit=50` / `offset=0` / 其余 8 列逐字相同 |

**其余 37 格逐字节相同**，覆盖：匿名 6 格（`/api/health`、`/api/semesters`、
`/api/course-sections`、`/api/students` → 401、`/api/audit-logs` → 401、
`/api/auth/me` → 401）· 匿名页面 2 格（`/login`、`/admin` 都回同一份 2 729 B 的
`index.html`）· `/openapi.json`（两档都是 **420 367 B**）· 坏口令登录（两档都是
**401 / 82 B**）· 学生 12 格 · 教师 10 格 · 管理员 4 格 · 三次登录本身。

**逐格状态码（两档完全一致）：**

| 身份 | 请求 | 两档同为 |
|---|---|---|
| 匿名 | `GET /api/students` / `/api/audit-logs` / `/api/auth/me` | **401** |
| 匿名 | `POST /api/auth/login`（坏口令） | **401**（82 B） |
| 学生 `2023120001` | `GET /api/students/4/home`（自己） | **200** |
| 学生 | `GET /api/students/5/home`（别人） | **403** |
| 学生 | `GET /api/audit-logs` / `/api/students` / `/api/dashboard/class/1` / `/api/teachers` | **403 ×4** |
| 学生 | `GET /api/alerts` | **200**，⚠️ 而响应体**只有他自己那一行**（`total=1`，`student_id=4`）⇒ 不是泄漏 |
| 教师 `T0001` | `GET /api/alerts` | **200**（`total=21`） |
| 教师 `T0001` | `GET /api/dashboard/class/1`（自己班） | **200** |
| 教师 `T0001` | `GET /api/dashboard/class/2`（别人的班） | **403** |
| 教师 `T0001` | `GET /api/audit-logs`（仅管理员） | **403** |
| 教师 `T0001` | `GET /api/teacher/students/4/home`（不在他班上） | **403** |
| 管理员 `T0003` | `GET /api/audit-logs` / `/api/students` / `/api/alerts` | **200 ×3** |

⇒ **结论：试用档放宽的权限是 0 格**。「试用」在本仓**不是**「降低门槛」的同义词：
`PE_TRIAL` 只驱动 `/api/health` 的第四格与前端那条告示，鉴权链一格都没碰。
（这与 `deploy.py:84-100` 的设计论证一致：`is_trial()` 与 `tier()` 正交。）

### 3.2 告示会不会泄漏到别的档 / 会不会该在的时候不在

⚠️ **本席没有跑浏览器、也没有跑 `smoke.mjs`**（跑 smoke 会写脏库，而本席的纪律是不碰
甲方那一份；本席自己的实例也不值得为这一格起 4 档），故「16 条路由**渲染后**逐条量」
这一格是**结构与两端取证**，不是 DOM 实测。三格证据：

1. **后端两端**：A（`PE_TRIAL=1`）的 `/api/health` 回 `"trial":true`；B（`PE_TRIAL=0`）回
   **55 B**（= `"trial":false`，与 54 B 的差正好是 `false` 比 `true` 多一个字符）⇒
   「档不档」是**后端说的**，而同一份 `dist` 服务两档。
2. **前端结构**：`App.vue:88` `const trial = ref(false)`（**缺省不挂**）、
   `App.vue:199` `<p v-if="trial" class="trial-note" role="status">`、
   `App.vue:200` 的 N 是 `{{ trialStudents }}`，而 `trialStudents` 取自
   `App.vue:124` `trialStudents.value = health.students` ⇒ **N 是从 `/api/health` 的
   `students` 取的，不是写死 60**（`App.vue:90-96` 的注释逐字交代了为什么不写死）。
   `catch` 那一支（`App.vue:125-129`）刻意把 `trial` 置回 `false` = 「读不到就不挂」。
3. **产物**：在**发给甲方的那一份** `frontend/dist/assets/index-DYNl778Q.js` 里搜到
   `试用环境` / `高保真仿真` / `请勿录入真实学生信息` / `名学生均为虚构` 各 1 处 ⇒
   告示**确实在甲方加载的那个 chunk 里**。
4. **16 条路由的住址是本席自己数的**（不抄报告）：`router/index.ts` 的 `routes` 数组
   **20 条** = **16 条页面** + `/`（root）+ `/s`（redirect）+ `/t`（redirect）+
   `/:pathMatch(.*)*`（catch-all）。16 条逐个在 A 上匿名 `GET` → **16 × 200**，
   且回的**都是同一份 2 729 B 的 `index.html`**（sha[:12] `691505145535`）⇒ SPA fallback 对
   16 条逐条成立；告示挂在 `App.vue`（根组件）上，故「16 条都看得见」在结构上成立。
   另测 `/`、`/s`、`/t`、`/nope-not-a-route` 四条也都是同一份 `index.html`（200）。

⚠️ **如实报**：「dev 档与产品档下 16 条路由逐条**渲染后**确认没有告示（0/16）」这一格
本席**未能核验**（要浏览器 / smoke）。本席能证的是：`v-if="trial"` + 后端回 `false` +
缺省 `ref(false)` + `catch` 也置 `false` ⇒ 结构上不可能挂出来。

### 3.3 `-Lan` 那一档的安全面（实例 C：8043，绑 `0.0.0.0` + dev 档 + 明文 http）

| 格 | 实测 |
|---|---|
| ① 从 `192.168.31.11:8043` 真发请求 · health | **200** `{"status":"ok","tables":28,"students":60,"trial":true}` |
| ① · 深链接 | `GET /s/check-in` → **200** / 2 729 B / html；`GET /admin/audit-logs` → **200**（同一份 `index.html`，前端守卫再弹） |
| ① · 登录 | `POST /api/auth/login` → **200** `{"kind":"student","id":4,"name":"赵锦程",…}` |
| ① · 带 cookie 的下一个请求 | `GET /api/auth/me` → **200**（同一身份）；`GET /api/students/4/home?as_of=2025-10-12` → **200 / 5 408 B** ⇒ **明文 http 上会话成立**（dev 档不带 `Secure`） |
| ① 附 · 匿名读业务端点 | `GET /api/students` → **401**（`unauthenticated`），响应体里逐字写着「⚠️ 请求头 `X-Teacher-Staff-No` 被忽略：`PE_ALLOW_HEADER_IDENTITY` 不是…」⇒ 请求头身份通道**关着** |
| ② 防火墙没被自动改 | `netsh advfirewall firewall show rule name=XMU-PE-IMS-TCP-8043` → **`No rules match the specified criteria.`** ✅ 脚本只打印、没动 |
| ③ 告示文本在 | 终端逐字打出 `-Lan` 那一大段：绑 `0.0.0.0`「同一个网段里的任何人都打得开」/「明文 http：口令、`pe_session` cookie、学生姓名与体测数据在网线上都是明文」/「未绑定的账号可以被**抢绑**」/「GET 读操作今天**不留审计**」 |
| ③ 附 · cookie 属性 | 原始 `Set-Cookie`：`pe_session=…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax` ⇒ **没有 `Secure`**（dev 档，与文档逐字一致） |
| ③ 附 · LAN URL | `http://192.168.31.11:8043/        ← WLAN`，并注明「本机数到 **1** 个 IPv4 地址」⇒ **现场数、不写死** |

⚠️ **`netsh` 那两条命令的语法本席自己核过（没执行）**：
`netsh advfirewall firewall add rule name=XMU-PE-IMS-TCP-8043 dir=in action=allow protocol=TCP localport=8043`
与 `netsh advfirewall firewall delete rule name=XMU-PE-IMS-TCP-8043` —— 五个 `key=value`
全是 `netsh advfirewall firewall add rule` 的合法参数名，`name=` 不带引号也成立
（值里没有空格），`delete rule` 只需 `name=` ⇒ **两条都能原样贴进 PS 5.1 跑**。
⚠️ 端口是**插值出来的**（`$Port`），不是写死的 8030 ⇒ 换 `-Port` 时命令跟着变，不撒谎。

### 3.4 ⚠️ `-Lan` + `PE_ENV=prod`：**只打印不 raise** —— 本席判断这个裁定**是对的**

实测（实例 D：8044）：`serve.ps1 -Port 8044 -SkipBuild -Lan` 在 `PE_ENV=prod` 下
**照常起来**（健康检查 200），并在 `-Lan` 那一段之后**多打一整段**：

```
⚠️⚠️⚠️ -Lan 与 PE_ENV=prod **同时**出现（实测档位 prod，cookie 的 Secure = True）：
   明文 http + Secure cookie ⇒ **浏览器拒收那张 cookie**，症状是「登录 200、下一个请求 401」
   ——即上面那些局域网 URL 点开之后**登不进去**。本脚本**不阻止**这一档，处置二选一：
     · 只是局域网明文试用 → 去掉 PE_ENV（回到缺省的 dev 档），或去掉 -Lan；
     · 真要上生产 → 前面挂一层 TLS 反代并设 PE_CORS_ORIGINS（那时 -Lan 绑 0.0.0.0 是合法的）。
```

而 `Secure` 那一格是**真的**：同一个实例上原始 `Set-Cookie` 实测
`pe_session=…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax; **Secure**`。

**判断**：`serve.ps1:573-585` 的裁定（「TLS 反代就在同一台机器上、反代再转发到
`0.0.0.0:<port>`」是一档合法形状，raise 会把它一起打死）**成立**，而**「甲方 IT 会不会就
这么起一个登不进去的服务」这一格被那段打印兜住了**：它点名了症状（登录 200、下一个请求 401）、
点名了后果（那些局域网 URL 点开之后登不进去）、并给了**两条**处置，其中第一条正是对的。
⇒ **不是静默失效**，本席**不报发现**。
⚠️ 但**说明书那一侧有一格漏了**：见 **S3-4** 与 **S4-12**。

### 3.5 `PE_TRIAL` 的坏值 raise（抽 3 个）

⚠️ 本席**没有**逐个起服务实测（起一次 uvicorn 要几秒，而 14 个坏值 × 两档不划算），
改走两条更硬的取证：

1. **变异 D1**：把 `deploy.py:270` 的 `if raw == TRIAL_ON:` 放宽成
   `if raw == TRIAL_ON or raw == "true":` → `test_deploy.py` **当场红**（1 failed / 16 passed）
   ⇒ 「`true` / `yes` / `on` 一律 `ValueError`」那一格**有牙**、且是**可执行**判据。
2. **代码路径**：`deploy.py:267-279` 的 `is_trial()` 在**调用时**读环境变量（不是 import 时），
   认不出的值 `raise ValueError`；而 `main.py:532` 的 `/api/health` 每个请求都调它一次、
   `create_app()` 装配时也调一次，且 `app.main` 有一条模块级 `app = create_app()` ⇒
   **装配期起不来**（uvicorn 直接抛）与**请求期 500/422** 两条路都在。
   ⚠️ 「请求期是 422 还是 500」本席**未能核验**（`ValueError` 从 `/api/health` 里抛出来时
   FastAPI 的处置取决于有没有挂 exception handler；派单写的是 422，本席没有实发过一发坏值请求）。

---

## ④ F3 · 交付可用性（本席的重心之一）

### 4.1 检材

`dist-pack\pe-ims-trial-20261016-032033.zip` **在磁盘上**（gitignore，未入库；
`git check-ignore` 那一拍由 `test_package.py` 钉），**10 305 418 B**（与自报逐字相同），
本席自己量的 sha256[:16] = **`EC05579FC28D19D8`**。⚠️ 本席**没有**重跑 `package.ps1`
（不需要：那一份在，且它跑一次要抄 17 MiB；而 F1 的 8 次 `test_package.py` 已经各真打过一次包）。

### 4.2 ⚠️⚠️ **`pip install` 那一格：通**（甲方 IT 的第一步）

**选的姿势**：在 `$env:TEMP\p07t6\venv`（`python -m venv`，**不带** `--system-site-packages`）
里跑 —— 于是「装成不成」问的是一个**干净的**解释器，而**一个字节都没进本席的全局环境**
（控制者的机器没被污染）。⚠️ 没用 `--dry-run`：它只解析 metadata、证明不了
「editable 装完之后 `import app.main` 真能成」。

| 格 | 实测 |
|---|---|
| 命令 | 在解包目录里 `python -m pip install -e backend`（= README:57 那一条，逐字） |
| 结果 | **退出码 0 / 34 s** |
| 装了什么 | `Successfully built pe-backend`；`Successfully installed … alembic-1.20.0 fastapi-**0.143.2** numpy-2.4.6 pandas-3.0.6 **pe-backend-0.1.0** pydantic-2.14.1 pyyaml-6.0.3 sqlalchemy-**2.1.4** starlette-**1.8.0** uvicorn-0.54.0 Mako-1.4.3 …`（27 个） |
| 装完能不能 import | `import app.main, fastapi, sqlalchemy, alembic, pandas, numpy, yaml, uvicorn` → **`app.main OK`** |

⚠️⚠️ **顺带量到一格本波四份报告都没量的事**：`backend/pyproject.toml` 除
`alembic==1.20.0` 外**六项全都没有上界**，故**甲方今天装到的不是本仓开发环境那一套**：

| 包 | 本仓开发环境 | 解包后新装 |
|---|---|---|
| fastapi | 0.141.1 | **0.143.2** |
| starlette | 1.7.0 | **1.8.0** |
| SQLAlchemy | 2.1.3 | **2.1.4** |
| pydantic | 2.13.5 | **2.14.1** |
| pandas / numpy / alembic / uvicorn | 3.0.6 / 2.4.6 / 1.20.0 / 0.54.0 | **逐字相同** |

**而这一格漂得无害（本席实测过，不是推断）**：把 `/openapi.json` 在两套环境里各生成一遍，
**逐字节相同** —— 两档都是 **420 367 B / sha256[:16] `6058F97F09B35855` / 74 路径 /
102 操作 / 挂 security 84 / GET 63（15 匿名）/ securitySchemes 3 / catch-all 0**。
⇒ 契约面不漂。⚠️ 而**运行时行为**本席也顺带覆盖了：实例 A/B/C/D 全部跑在
**venv 那一套（fastapi 0.143.2）**上，§③ 的 39 格鉴权矩阵、§④ 的 16 条路由、
§⑤ 的全部数字都是在它上面量出来的 ⇒ 甲方那一套依赖**今天能跑通全部四条路线的后端面**。
记 **S4-13**（没有 lockfile ⇒ 甲方装到什么版本是「打包那天之后 PyPI 上最新的那一套」，
今天恰好无害，而这不是一个可以依赖的性质）。

### 4.3 ⚠️⚠️ **含空格与中文的路径：`pip install` 通、灌库通、而起服务那一步**当场失败****

做法：把解包目录整棵抄到 `$env:TEMP\p07t6\体育系统 试用\`（= 派单点名的那个形状），
另建 `venv2`，在**它里面**跑 `pip install -e backend`，再在 **PATH 里没有 node** 的
子进程里跑 `scripts\trial.ps1 -Port 8045`。

| 步 | 结果 |
|---|---|
| 抄过去 | 446 个文件（多出来的是第一次解包后 `pip install -e` 生的 `pe_backend.egg-info` 与 `__pycache__`、以及那一份 `pe_trial.db`；本席把 `pe_trial.db*` 先删了，强制走灌库那一路） |
| 最长绝对路径 | **151 字符**（`…\体育系统 试用\backend\migrations\versions\0ac943e0da9b_login_attempt_login_widen_to_64.py`）⇒ 离 260 还有 **109** 字符 |
| `pip install -e backend` | **退出码 0** ✅（editable 的 `.pth` 里那个含空格与中文的路径写得对） |
| `trial.ps1` ①–④ | ✅ 禁区守卫过；✅ 灌库**成功** —— `--db-url sqlite:///C:/…/体育系统 试用/backend/pe_trial.db`（**URL 里带空格**）与 `--csv-dir C:\…\pe_trial_csv_46764` 都没被打断，`[1/7]…[7/7]` 全部跑完（60 人 / 840 行打卡 / 32 条预警 / 19 条消息，与不含空格那一份逐字相同） |
| `trial.ps1` ⑤ 委托 | ✅ `powershell -File "C:\…\体育系统 试用\scripts\serve.ps1" -Port 8045 -SkipBuild`（splatting 把含空格的元素正确加了引号） |
| `serve.ps1` ①–③ | ✅ python 版本检查、7 项依赖检查、`-SkipBuild` 不查 node、`PE_STATIC_DIST` 都对 |
| `serve.ps1` ③ e 起 uvicorn | ❌ **失败** |

**原文（uvicorn 自己打的）**：

```
Usage: python -m uvicorn [OPTIONS] APP
Try 'python -m uvicorn --help' for help.

Error: Got unexpected extra argument (试用\backend\scripts)
```

紧跟着一句 `serve.ps1:474` 的 `throw`：「uvicorn 在健康检查通过之前就退出了（PID 22604，
退出码 ，轮询了 1 次）…最常见的一档是 `PE_STATIC_DIST` 指的目录里没有 `index.html`，
或 `PE_DB_URL` 指到了一个建不出来的库。」→ 退出码 **1**。

**根因（最小复现，本席亲跑）**：

```powershell
# ❌ Start-Process -ArgumentList 不给含空格的元素加引号
Start-Process -FilePath python -ArgumentList @("-c","import sys;print(sys.argv)","--app-dir","C:\…\space dir") -NoNewWindow -Wait
#   → python 只收到 "-c import"，当场 SyntaxError: invalid syntax

# ✅ 直接调用（&）会加引号
python -c "import sys;print(sys.argv)" --app-dir $d
#   → ['-c', '--app-dir', 'C:\\Users\\…\\space dir']
```

病灶在 `scripts\serve.ps1:436-441 + 449`：

```powershell
$Arguments = @("-m","uvicorn","serve_app:app","--app-dir",(Join-Path $Backend "scripts"),"--host",$BindAddress,"--port","$Port")
$Proc = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory $Backend -PassThru -NoNewWindow
```

⇒ 见 **S1-1**。

### 4.4 一条命令起服务 + **16 条路由**（不含空格的路径上：全通）

实例 A（`…\p07t6\unpack\`，PATH 里 `node` 实测为 **空**：`(Get-Command node).Source` = `[]`）：

* `scripts\trial.ps1 -Port 8041` → 灌库 ✅ → 委托 `serve.ps1 -Port 8041 -SkipBuild` ✅ →
  健康检查 **200** `{"status":"ok","tables":28,"students":60,"trial":true}` ✅
* `serve.ps1` 自己印的那一行是**现场证据**：`⇒ 本次**不需要构建**：本脚本到这一行为止一次都没查 node、一次都没调 npm` ✅
* **16 条路由**（本席自己从 `router/index.ts` 数的，见 §3.2 第 4 条）匿名 `GET` → **16 × 200**，
  每条都回同一份 2 729 B 的 `index.html`；另加 `/`、`/s`、`/t`、`/nope-not-a-route` 四条 → 200；
  `/api/health` 200 / `/openapi.json` **200 / 420 367 B** / `/docs` 200 / 1 023 B /
  `/redoc` 200 / 905 B ✅
* 停干净：`Stop-Process` 之后 `Get-NetTCPConnection -State Listen` 在 8040–8050 区间 **0 个 listener** ✅

### 4.5 包内容：**该有的逐个在、不该有的一个都不在**

339 个条目（**全是文件条目，0 个目录条目**）；解包到磁盘后 **339 个文件 / 17 728 278 B**。

| 顶层 | 实测 | 自报 | |
|---|---|---|---|
| `Document` | 28 | 28 | ✅ |
| `backend` | 207 | 207 | ✅ |
| `frontend` | 99 | 99 | ✅ |
| `scripts` | 4 | 4 | ✅ |
| `README.md` | 1 | 1 | ✅ |

**该有的（逐个命中）**：`backend/app/` **96** · `backend/migrations/` **7** ·
`backend/data/` **24** ✅（与 `$MustContainDataCount` 和 `test_package.py` 的 `>= 24` 都对上）·
`backend/scripts/` **8**（含 `demo_bootstrap.py` 与 `serve_app.py`）· `backend/pyproject.toml` ·
`backend/alembic.ini` · `frontend/dist/` **29** ✅ · `frontend/src/` **59** ·
`frontend/package.json` + `package-lock.json` + `vite.config.ts` + 3 个 tsconfig + `index.html` ·
`scripts/` 4 个 `.ps1` · `Document/` 的 spec（**640 524 B**，与仓库里那一份**逐字节相同**）
与甲方试用说明书（**21 632 B**，逐字节相同）· 根 `README.md`。

**不该有的（正则扫全部 339 个条目名，命中 0）**：`(^|/)\.git(/|$)` · `node_modules` ·
`\.db$` · `\.superpowers` · `(^|/)tools/` · `backups` · `(^|/)\.trial/` ·
`__pycache__` · `\.pytest_cache` · `-journal|-wal|-shm` ⇒ **0 命中** ✅

**最长条目路径 = 75 字符**（`backend/migrations/versions/0ac943e0da9b_login_attempt_login_widen_to_64.py`）
⇒ 解包到 45 字符的 TEMP 前缀下是 **125**，解包到含中文的前缀下是 **151**，
**离 260 分别还有 135 / 109 字符**。⚠️ Task 4 实测的「299 字符长路径在 PS 5.1 下两个压缩
API 都读不了」那一格与今天这个包**无缘**（差 109 字符以上）。

**入口脚本的 BOM / 行尾**（本席直接读 zip 里的字节，不经解压库）：
`serve.ps1` 45 052 B · `trial.ps1` 27 375 B · `tunnel.ps1` 72 777 B · `package.ps1` 40 827 B ·
`backend/scripts/demo.ps1` 25 820 B —— **五个都是 BOM=True、纯 CRLF、0 个裸 LF** ✅
（BOM 是承重的：PS 5.1 读没有 BOM 的 `.ps1` 会按 GBK 解码，而这些文件里全是中文注释）。

⚠️ **包里带的东西比 README 说的多**（见 **S3-5**）：`backend/tests/` **70** 个文件、
`Document/` 里除 spec 与说明书之外还有 **9** 份内部文档（7 份实施计划 + 联调取证 + 需求记录）、
**15** 张截图、**1** 份 `.doc`。

### 4.6 `frontend` 带整条构建链：**帮助还是困惑**

* **包里摆着什么**：`package.json` + `package-lock.json` + `src/` 59 个文件 + `vite.config.ts` +
  3 个 tsconfig + `index.html`，**以及**预构建的 `dist/` 29 个文件。
* **README 怎么说**（README:40-41 与 63-64）：「它的口径是「在**别的**机器上、**只装 Python**
  就起一份」（⚠️ 不需要 Node、不需要 `npm install`、不需要 git；包里带的是**预构建**的
  `frontend\dist`）」·「它缺省**不重建前端**（`trial.ps1` 透传 `-SkipBuild`），故一次都不查
  node；改了 `frontend\src` 要看见变化，请加 `-Build`（那就要 Node 20+ 与 `npm install` 跑过）」。
* **甲方照它跑 `npm install` 会发生什么**（判断 + 包里的说明文字取证，**没真跑**）：
  ① `package-lock.json` 在 ⇒ `npm install` 会照 lockfile 装出一棵确定的依赖树；
  ② 而 README 明确说**不需要**它，且 `trial.ps1` 缺省透传 `-SkipBuild` ⇒ **跑了也不影响起服务**；
  ③ 真正的风险是**顺序**：一个先跑了 `npm install`、再跑 `trial.ps1 -Build` 的人，会让
  `serve.ps1` 走 `npm run build`（`vue-tsc -b + vite build`）⇒ **它会清空并重写
  `frontend/dist`**，而那正是缺省路径在发的产物。⚠️ 这一格 README **没有警告**
  （它只说「要 Node 20+ 与 `npm install` 跑过」，没说「那会重建你正在发的那一份 dist」）。
* **本席的判断**：带整条构建链**利大于弊**（它是「与乐跑工程团队谈对接的技术依据」那一格的
  载体，也把「包里的 `src` 与 `dist` 是不是同一份源码」变成可核验的），而 README 那两句
  「不需要 Node」把困惑压住了。**建议的最小处置**：README 的 `-Build` 那一句后面补半句
  「⚠️ 它会**重写** `frontend\dist`（= 你正在发的那一份产物）」。**不构成发现**，记在 §⑧ 的注意事项里。

### 4.7 `README.md`：**没有第二个所有者** ✅

说明书 §2 ③ 逐字写着「一律以包里的 `README` 为准」⇒ 本席把包里那一份与仓库里那一份
**逐字节比**：**SAME**（两边都是 5 006 B / sha256[:12] `701df1af3dcd`）。
另比了 14 个关键文件（说明书 / spec / 四个 `.ps1` / `pyproject.toml` / `deploy.py` /
`main.py` / `dist/index.html` / 两个产物 / `App.vue` / `router/index.ts`）——
**15 个全部 SAME** ⇒ **包 = HEAD 的源码 + HEAD 的产物，一个字节都不差**。

### 4.8 三条链接的命令语法（只读核，没执行 `tunnel.ps1`）

| 出处 | 打印出来的东西 | 语法核验 |
|---|---|---|
| `serve.ps1` ⑤ | `http://127.0.0.1:$Port/` · `/api/health` · `/docs` · `/openapi.json` | ✅ 四条都是插值出来的、端口不写死 |
| `serve.ps1` ⑤ b（`-Lan`） | `http://<现场数出来的 IPv4>:$Port/   ← <网卡名>` | ✅ 实测 `http://192.168.31.11:8043/ ← WLAN` |
| `serve.ps1` ⑤ b（`-Lan`） | 两条 `netsh advfirewall firewall add/delete rule` | ✅ 见 §3.3 |
| `trial.ps1` ⑤ b | 三行「数据是仿真的 / 怎么重置 / 完整说明在哪」，并**刻意不抄**链接与账号（`trial.ps1:344-352` 逐字交代了为什么不抄） | ✅ 不是第二个所有者 |
| `tunnel.ps1` ⑦ | `$PublicUrl/` · `$PublicUrl/login` · `$RemoteHealthUrl` · `$UrlFile` · `$LogDir` · 协议 · 自检 | ✅ 全是变量插值；**一个写死的公网主机名都没有** |

---

## ⑤ F4 · 说明书的真话率（本席的第二重心）

### 5.1 可验证断言逐条核验（**33 条**；一律在本席自己的实例上验，一次都没打 8030）

| # | 断言（出处） | 实测 | 判定 |
|---|---|---|---|
| 1 | §0 「spec，**5400 余行**」 | `Get-Content …设计spec.md).Count` = **6233** | ❌ **错** → **S3-2** |
| 2 | §0 本文「八节」 | 实测 §1–§8 共 **8** 节 | ✅ |
| 3 | §2① 链接形状 `https://<随机三段单词>.trycloudflare.com` | 实测两条真链接都是三段单词（`paris-condo-terms-composed` / `podcasts-mitchell-donald-americas`） | ✅ |
| 4 | §2① 「进程一停，链接立刻失效（打开会看到 Cloudflare 自己的一页错误，写着 `error code: 1033`，⚠️ **不是**「连不上」）」 | ⚠️ 实测今天这一档是 **DNS NXDOMAIN**（`Resolve-DnsName` → `DNS name does not exist`；`Invoke-WebRequest` → `基础连接已经关闭`），而 `cloudflared` **进程还活着**；浏览器上就是「找不到服务器」= **恰恰是「连不上」** | ❌ **只对 530 那一档成立** → **S2-2** |
| 5 | §2① 我方开一条的两个终端命令（`$env:PE_ENV='prod'` + `trial.ps1 -Port 8030 -Reset` / `tunnel.ps1 -Port 8030`） | 参数名与缺省值逐个对：`trial.ps1` 有 `-Port`(8030)/`-Lan`/`-Reset`/`-Build`，`tunnel.ps1` 有 `-Port`(8030)/`-Backend`/`-Protocol`/`-Watchdog` | ✅ 语法正确、可贴进 PS 5.1 |
| 6 | §2① 「`.trial\public-url.txt` 在隧道退出时会被脚本自己删掉」 | 磁盘上**正躺着一份写着死链接的它**（1 472 B / `0AB5FAF553A5A1E7`，`url = …podcasts-mitchell-donald-americas…`、`隧道 PID = 10128`，而 **PID 10128 不在**、那条 URL 实测连不上） | ❌ **无条件地说，是假的** → **S3-3** |
| 7 | §2① 「随附的可分发包里**不含**这个 55 MB 的二进制」 | 包里 `(^|/)tools/` 命中 **0**；本机 `tools\cloudflared.exe` = **55 365 048 B** | ✅ |
| 8 | §2② `trial.ps1 -Lan` 会打印 `http://<本机 IPv4>:8030/`，且地址是**现场数**的 | 实测打印 `http://192.168.31.11:8043/ ← WLAN` + 「本机数到 1 个 IPv4 地址」 | ✅ |
| 9 | §2② 「明文 http」+「终端会把 `netsh …` 原样打印（脚本**不会**自己去改防火墙）」 | `show rule name=XMU-PE-IMS-TCP-8043` → `No rules match…`；cookie 无 `Secure` | ✅ |
| 10 | §2③ 「以包里的 `README` 为准」 | 包里那份与仓库那份**逐字节相同** | ✅（没有第二个所有者） |
| 11 | §3 学生 `2023120001` = 赵锦程 | 库里 `(4, '赵锦程')`；登录回 `{"kind":"student","id":4,"name":"赵锦程","student_no":"2023120001"}` | ✅ |
| 12 | §3 学生 `2025060001` = 周晨阳 | 库里 `(1, '周晨阳')` | ✅ |
| 13 | §3 教师 `T0001` 陈国华 / `T0002` 林慧敏 / 管理员 `T0003` 赵志刚（`role='admin'`） | 库里 `(1,'T0001','陈国华','teacher') (2,'T0002','林慧敏','teacher') (3,'T0003','赵志刚','admin')` | ✅ |
| 14 | §3 「`T0001` = 行政班01 + 提升班」 | `/api/course-sections`：id1 行政班01 `teacher_id=1`、id3 提升班 `teacher_id=1` | ✅ |
| 15 | §3 「大屏上写着「我任教的 2 个班 / **50 人次**」，学生下拉里 30 人、预警队列 **21** 条」 | `enrollment`：班1 **30** + 班3 **20** = **50** ✅；`/api/alerts`(T0001) `total=**21**` ✅ | ✅ |
| 16 | §3 「`T0002` = 行政班02 + 强化班（预警 **23** 条）」 | id2 行政班02 / id4 强化班 都 `teacher_id=2` ✅；**23** 条本席**未实发**（要登 T0002 再打一发） | ⚠️ **半核验**（班的归属对，23 那个数未测） |
| 17 | §3 「打开别的班的学生详情会得到一句「当前身份不是本学期任教他的老师」」 | 实测 T0001 打学生 4 / 5 都是 **403**，而**原文不是这一句**：「学生 4 不在教师 'T0001' 于学期 2 任教的任何教学班里（或这个学生不存在）：判据是 `enrollment ⋈ course_section.teacher_id`…」 | ⚠️ **意思对、引文不是原文**（它是转述而非逐字引用，而说明书用了引号）→ **S4-14** |
| 18 | §3 口令 `pe-demo-2025`，唯一所有者是 `demo_bootstrap.py` 的 `DEMO_PASSWORD` | 三个实例上都用它登录成功；`serve.ps1:504-506` 与 `trial.ps1:344-352` 都**刻意不抄字面量** | ✅ |
| 19 | §4 路线一第 1 步 告示文案「试用环境 · 数据为高保真仿真（60 名学生均为虚构） · 请勿录入真实学生信息」 | `App.vue:200` 逐字是它（N 用 `{{ trialStudents }}` 插值）；四段文字都在**发给甲方的** `index-DYNl778Q.js` 里 | ✅ |
| 20 | §4 路线一第 3 步 本周训练量 **108.0 分钟**（3 个动作） | `/api/students/4/home?as_of=2025-10-12` → `weekly_sheet.sessions[0].blocks` **3** 块、`weekly_volume` 各 36.0 ⇒ **108.0** | ✅ |
| 21 | 同上 打卡完成率 **100.0%**（**3 / 3** 个处方训练日） | `completion-rate?semester_id=2&week=6` → `completion_rate=1.0, numerator=3, denominator=3, expected_days=['2025-10-06','2025-10-07','2025-10-08']` | ✅ |
| 22 | 同上 待办 **0** 项 / 分层 **黄色层** + 「短板 ≥2 项且体成分未判为异常（规则 Y3）」/ 未读消息 **1** / 电子勋章 **1** | `pending_rpe=[]`；`stratification.label='yellow'`、`explanation` 逐字含「短板 ≥2 项且体成分未判为异常（**规则 Y3**）」；`unread_notifications=1`；`badges.count=1` | ✅ |
| 23 | §4 路线一第 4 步 训练日 **3** / 休息日 **4**、本周系数 **×1.00** | `weekly-sheet?as_of=2025-10-12` → `sessions` **3** 天（day 1/2/3）、`factor=1.0` | ✅ |
| 24 | §4 路线一第 5 步 「我的打卡记录」**14 行**，标记列有 `demo` / `迟交` / `休息日`，且「这一周（以及往前 14 天）每一天都已经有记录」 | `training-logs?student_id=4&semester_id=2&week=6` → `total=**14**`；14 个 distinct 日期 `2025-09-29…2025-10-12`（连续 14 天）；`source` 全是 `demo`；`late` **2** 行；`is_rest_day` **4** 行 | ✅ |
| 25 | §4 路线一第 6 步 「标记列写着 `checkin`；⚠️ 页面下方那句注释把这一档写成了 `student`，那是页面自己的笔误，我方已登记待修」 | 实发 `POST /api/training-logs` → **201**，`"source": "**checkin**"` ✅；`CheckIn.vue:637-638` 逐字写「`student` 才是从本页交上去的」✅；**已登记**：spec §15 的 **G2** 逐字是「打卡页有一句**随数据变假**的散文：`source` 的取值（Plan 07 Task 4 实测到）」✅ | ✅ **三格全对**（含「已登记待修」那一句） |
| 26 | §4 路线一第 7 步 课堂快评 **4** 次、均值 **5.75** | `rpe-records?student_id=4&semester_id=2` → `total=4`，值 `[6,8,4,5]`，均值 **5.75** | ✅ |
| 27 | §4 路线一第 8 步 3 次小测（第 2/4/6 周）；教学班 2 折返 **98.3** / 名次 **第 1 / 30**；教学班 4 **92.5** / **第 2 / 20** | `normalized/me?semester_id=2&week=2/4/6` 各回 sections 2 与 4 ✅；week6：section2 `shuttle_score=**98.33**`、`scored_count=**30**`，而全量里 98.33 是最高 ⇒ **第 1**；section4 `**92.5**`、`scored_count=**20**`，全量里 97.5（student 37）更高 ⇒ **第 2** | ✅ |
| 28 | §4 路线一第 9 步 1 条未读「本周电子勋章」 | `/api/students/4/notifications` → 1 条，`title='本周电子勋章'`、`is_read=False` | ✅ |
| 29 | §4 路线二第 3 步 班级周报（班1）：红 **3** / 黄 **17** / 绿 **10**、名册 **30**、人均课堂 RPE **6.37**（环比 **+0.10**）、三层完成率 红 **50.0%** / 黄 **62.7%** / 绿 **55.0%**、建议「维持当前强度」 | `weekly-class-report/1?as_of=2025-10-12` → `by_layer {red:3,yellow:17,green:10,insufficient_data:0}`、`rpe_summary.mean=6.3667`（渲染 6.37）、`delta=0.1`、`checkin_rate_by_layer {red:0.5, yellow:0.6275, green:0.55}`、`suggestion='维持当前强度'` | ✅ **逐格对** |
| 30 | §4 路线二第 4 步 预警队列「共 **21** 条 · 红 **9** / 黄 **4** / 绿 **8** · 待处理 **21** / 已处理 0 / 已忽略 0」 | `/api/alerts`(T0001) → `total=21`，`levels {red:9, yellow:4, green:8}`，`status {pending:21}` | ✅ **逐格对** |
| 31 | §4 路线二第 6 步「第一条红色预警（「课堂 RPE 连续 3 次 ≥ 9 分」· 周晨阳 #1）」 | 第一条红色 = `id 1`、`student_id 1`（周晨阳）、`rule_id RED_RPE_SUSTAINED`；规则人话见 `domain/alerts.py:180`「② RPE 连续 ≥ 9 分（连续 3 次课堂快评）」 | ✅ |
| 32 | §4 路线二第 6/7 步「待处理 **20** / 已处理 **1**」+ 学生消息中心多一条「本周训练量已减 20%」，正文逐字 | 实发 `POST /api/alerts/1/handle?as_of=2025-10-12 {"action":"reduce_20pct"}` → **200**；`alert.status='handled'`、`handled_action='reduce_20pct'`；`/api/alerts` → `{handled:1, pending:20}` ✅；学生 1 的 notifications **0 → 1**，`title='本周训练量已减 20%'`，`body` 与说明书引文**逐字相同** ✅ | ✅ 两格都对 |
| 33 | §4 路线二第 7 步「**这就是闭环**：教师点一下，学生的**训练单**与消息中心同时变」 | ⚠️ 响应里 **`"adjustment": null`**；`weekly_adjustment` 点前点后都是 **13 行**；学生 1 的 `weekly-sheet?as_of=2025-10-12` 系数**点前 0.8 / 点后 0.8**、`sources` 两度都是 `['auto']` ⇒ **训练单没变** | ❌ **错** → **S2-1** |

（路线三、路线四的断言见 §5.2 的实走记录。）

**统计：33 条里 对 30 / 错 3（#1 #4 #33）/ 半核验 1（#16）/ 引文不逐字 1（#17）。**
⚠️ #6 也判错，故**错的一共 4 条**（#1 #4 #6 #33）。

### 5.2 四条试用路线的实走逐步记录

⚠️ **姿势如实说**：本席**没有开浏览器**（本席的工具面里没有可用的浏览器自动化，而派单的
纪律也不允许把 smoke 打到任何一份真库上）。四条路线一律按「**页面读哪个端点、传什么参数**」
在源码里定位（`endpoints.ts` + 各 `.vue`），再**实发同一组请求**、比对说明书写的数字与文案；
「点哪儿看见什么」那一层用**渲染出来的 template 正文**（剥掉 HTML 注释之后）核。
⇒ **数据面与文案面是实测的，像素面不是。**

#### 路线一 · 学生端（`2023120001`）—— **走通**

| 步 | 说明书写的 | 实测 | |
|---|---|---|---|
| 1 | 落登录页，顶上一条告示 | `/login` → 200 同一份 `index.html`；告示四段文字都在 `index-DYNl778Q.js` 里；`/api/health` 回 `trial:true` + `students:60` ⇒ N=60 | ✅ |
| 2 | 登录 → 会话条「学生 2023120001 · 赵锦程」 | `POST /api/auth/login` → 200 `{"kind":"student","id":4,"name":"赵锦程","student_no":"2023120001"}` | ✅ |
| 3 | 首页六格 | 见 §5.1 #20–#22，**逐格对** | ✅ |
| 4 | 本周训练单 | `weekly-sheet?as_of=2025-10-12` → 200，3 个训练日 / `factor=1.0` / 每天 3 个动作 | ✅ |
| 5 | 每日打卡：14 行 + 已有记录那天点提交 → **409 且页面看得见人话** | 14 行 ✅；实发 `POST /api/training-logs {log_date:'2025-10-12',…}` → **409** `{"error":{"code":"integrity_conflict","message":"UNIQUE constraint failed: training_log.student_id, training_log.log_date"}}`；而 `CheckIn.vue:255` 渲染的人话与说明书引文**逐字相同**：「这一天（…）你已经打过卡了：一天只能有一行，后端刻意不做「补卡覆盖旧行」…」；⚠️ 提交按钮只 `:disabled="submitting"`（`CheckIn.vue:535`），**没有**被 `alreadyLogged` 禁用 ⇒ 请求**真的发出去**（与说明书逐字一致） | ✅ |
| 6 | 换一天 + `30.9` → 201 + 绿色「已打卡」 | 实发 `{log_date:'2025-12-12', duration_min:30.9,…}` → **201**，回 `id 841 / source='checkin' / late=false / submitted_at=…`；`CheckIn.vue:545-551` 是 `<SuccessMark :visible="stamp" text="已打卡" tone="moss">`（`moss` = 绿），`stampCaption` 逐字含「服务端记于 …」 | ✅（含说明书自己披露的 `student`/`checkin` 笔误） |
| 7 | 课堂快评 4 次 / 均值 5.75 / 口令只能手输 | 见 #26；`RpeEntry.vue` 的提交按钮是 `:disabled="!canSubmit"`（`useFormValidity.ts:78` 逐字记着这一格） | ✅ |
| 8 | 二次小测 3 次 + 班内百分位 | 见 #27 | ✅ |
| 9 | 消息中心 1 条未读 → 标为已读 | 1 条未读 ✅；「点标为已读 → 未读 1/1 变 0/1」本席**没有实发**（那会写脏 A 实例，而 A 是只读核验用的）⇒ **未核验** | ⚠️ 半 |

#### 路线二 · 教师端 —— **走通到第 6 步，第 7 步的「训练单变」不成立**

| 步 | 实测 | |
|---|---|---|
| 1–2 | T0001 登录 200；任教班 = id1 行政班01 + id3 提升班；`enrollment` 30+20 = **50 人次** | ✅ |
| 3 | 班级周报（班1）**逐格对**（#29） | ✅ |
| 4 | 预警队列 **21 / 红9 黄4 绿8 / 待处理21** 逐格对（#30）；页面写明范围是「我本学期任教班级的学生」这一格本席按 `AlertQueue.vue` 的渲染正文核（未逐字抄） | ✅ |
| 5 | 点学生名 → 学生详情：本席实发 T0001 对**不在他班上**的学生 4/5 → **403**（#17）；对他班上的学生（实测 T0001 可读 **41** 人：`[1,3,6,7,8,10,11,…]`）→ 200 | ✅（**41/60** 与 spec §1.2 第 13 条逐字相同） |
| 6 | 「减量 20%」→ 200、`status→handled`、`handled_action='reduce_20pct'`、消息推给学生、顶行变「待处理 20 / 已处理 1」 | ✅ **五格全对** |
| 6 附 | ⚠️ 说明书**没提**卡片下方还会出现的一整段：`AlertQueue.vue:727-733` 会渲染「⚠️ `adjustment` 是 `null` —— **这是有信息的一档，不是失败**：一处方一周**至多一条** `source='auto'` 的调整…那一周已经减过量了，故本次**未再减**。」（那四个字**在发给甲方的** `AlertQueue-DSyjjO54.js` 里搜得到） | ⚠️ 说明书漏了 → **S2-1** |
| 7 | 学生 `2025060001` 登录 → 消息中心多一条，正文**逐字相同** ✅；⚠️ 而「训练单…变」**不成立**：系数点前点后都是 **0.80**、`sources` 两度都是 `['auto']`、`weekly_adjustment` 两度都是 **13 行** | ❌ → **S2-1** |

⚠️ **而且不是「第一条恰好不成立」**：本席把 T0001 那 **9** 条红色预警逐个查了
（学生 `1 / 11 / 24 / 25 / 28 / 31 / 41 / 45 / 46`），**9 个全都在那 13 行 `source='auto'`
的调整里** ⇒ 「没有 auto 调整的红色预警」= **0** 条 ⇒ 教师点**任何**一条红色预警都拿不到
一次可见的系数变化。**这一格在演示库上是结构性的，不是巧合。**

#### 路线三 · 管理台（`T0003`）—— **走通**

| 步 | 说明书写的 | 实测 | |
|---|---|---|---|
| 1 | 资源目录 **23** 个资源，每格标「可写 / 只读」，写明「写仅管理员」 | `frontend/src/catalog/resources.ts` 里 `path:` 条目 **23** 个；`writable: true` **9** 个 / `false` **14** 个 | ✅ |
| 2 | 学生分页「1–20 / 共 **60** 行」，列 id / 学号 / 名称 / 性别 / 年级 / 院系 / 操作 | `GET /api/students?limit=20` → `total=60`、返回 20 行；行内键 `{id, student_no, name, sex, birth, department, grade}` ⇒ 六个数据列 + 操作列 | ✅ |
| 3 | 资源详情页逐列列出（含出生日期），「✎ 编辑」「← 列表」「目录」；**23 个资源里只有 9 个可写、其余 14 个只读** | `GET /api/students/4` → 200，含 `birth: '2005-05-01'`；**9 / 14** 与 `catalog/resources.ts` 逐字相同；⚠️ 交叉核验：openapi 上 **9** 个资源族有写操作、共 **26** 个（8 族 ×3 + `semesters` ×2）⇒ 与 `demo_bootstrap.py` 打印给甲方的「管理台 **26** 个写入操作仅它可用」**逐字相符** | ✅ |
| 4 | 审计留痕**只读**、最新在前、**九列**；「只记写操作…一行 `GET` 都没有」 | `GET /api/audit-logs` → 列名恰好 **9** 个：`at / id / method / path / staff_no / status / subject_id / subject_kind / target`；本席在 A 实例上跑了 15 个写请求之后 `total=15`，`methods = {'POST': 15}`，**0 个 GET** | ✅ |
| 4 附 | 「走完本文四条路线之后实测 **21** 行」 | ⚠️ **无法核验**：那个数取决于确切的点击序列（登出也是 `POST`、也记一行），本席的走法不同 ⇒ 得到 15。**形状（全是 POST、0 个 GET）已核验**，**21 这个数未核验** | ⚠️ |
| 5 | 筛选器：每页 20/50/200、按身份类型、按方法、⟳ 重读 | 只核了 `limit=20` 与 `limit=200` 两档真的生效（`total` 不变、返回行数变）；UI 上那几个控件**没在浏览器里点** | ⚠️ 半 |

#### 路线四 · 教师大屏（`T0001`）—— **走通**

| 步 | 说明书写的 | 实测（`/api/dashboard/class/{1,3}?as_of=2025-10-12`） | |
|---|---|---|---|
| 2 | 第 **01** 块：待处理 **15** / 本班共 **15** 条，红 **8** / 黄 **3** / 绿 **4** | `alert_summary` = red `{pending:8}` / yellow `{pending:3}` / green `{pending:4}` ⇒ **15 / 15**，**逐格对** | ✅ |
| 3 | 第 **02** 块 名册 **30**：红3/黄17/绿10/数据不足0；第 **03** 块 人均课堂 RPE **6.37** · 学期第 **6** 周 · 建议「维持当前强度」；第 **05** 块 三层完成率；第 **07** 块 异常名单 **5 人**，逐人写「断卡几天 · 峰值 RPE」 | `roster_size=30`、`by_layer {3,17,10,0}`、`rpe_summary.mean=6.3667`、`week=6`、`suggestion='维持当前强度'`、`checkin_rate_by_layer {0.5, 0.6275, 0.55}`、`abnormal_roster` **n=5** 且逐人带 `gap_days` 与 `peak_rpe`（`[{1,['rpe_high'],1,10},{10,['checkin_gap'],3,5},{11,…,0,10},{31,…,0,10},{41,…,0,9}]`） | ✅ **逐格对** |
| 4 | 点班次标签 `2 · 提升班` → 名册 **20**、待处理 **11 / 11**、异常名单 **0** | 提升班 = `course_section_id **3**`：`roster_size=20`、`alert_summary` 3+2+6 = **11**、`abnormal_roster=[]` ⇒ **三个数全对**。⚠️ 而标签上那个「2」是**屏上第 2 个班次标签**、不是 section id（id 是 3）⇒ 说明书的写法与屏幕一致、**不误导** | ✅ |
| 5 | 第 **06** 块：演示库里有 **4 节已发起的课次**；口令 8 位；课次 **#1 = `4C51674D`**、课次 **#3 = `D2476ADA`** | `class_session` 表 8 行、`rpe_opened` 全为 1，而 **`course_section_id` 只有 1 与 2** ⇒ T0001（任教 1 与 3）只看得到 section 1 的 **4** 节（id 1/3/5/7）✅；`GET /api/class-sessions/{1..8}/rpe-token` 全 200、各 8 位，**#1 = `4C51674D`** ✅、**#3 = `D2476ADA`** ✅ | ✅ **两个口令逐字对** |
| 4 附 | 「这一屏会自动轮播；若浏览器开了「减少动态效果」，它会停用自动轮播并提示手动点」 | **未核验**（要浏览器） | ⚠️ |

### 5.3 甲方视角的可读性

| 格 | 实测 | |
|---|---|---|
| 内部术语 | 全文搜 `read_scope` / `orphan` / `未定型响应` / `Task 4` / `Task 5b` / `Plan 0` → **0 命中** ✅。⚠️ 有 5 处**指针式**提及是刻意保留的（`spec §13.17.2` / `spec §13.6` / `spec §13.15` / `backend/scripts/demo_bootstrap.py` 的 `DEMO_PASSWORD` / `scripts\tunnel.ps1`），都是「去哪儿看」而不是内部黑话 | ✅ |
| `&&` | 全文 **0 处** ✅（三处命令块一律用换行或 `;`） | ✅ |
| 写死的公网主机名 | **0 处** ✅ —— §2① 逐字写「每次重开都变，所以本文不印某一条具体地址」 | ✅ |
| 口令旁边那三件事 | §3 的 ①「它是**公开的**演示口令，任何知道它的人都能登进**任何一个**账号（含管理员）」②「正式部署**必须换掉**它」+「本系统**不做口令找回**」③「唯一所有者是 `demo_bootstrap.py` 的 `DEMO_PASSWORD`…改了那里就要**重印本说明书**」⇒ **三件都在** | ✅ |
| 须知那 8 条挑得对不对 | §6 自己交代「spec §13.15 一共 **11** 条，本文挑了其中 **8** 条（第 **2、3、4、5、6、7、8、10** 条）…没有挑的三条是第 **1、9、11** 条」⇒ 本席把 §13.15 那 11 条逐条读了：**挑的与没挑的逐字对上**，没挑的三条确实是「产品档环境变量与 CORS」「换数据库后端前的两件事」「覆盖率三口径」= 给开发者/运维的 | ✅ |
| ⚠️ 「读操作不留审计」与「未绑定账号可被抢绑」在不在最前面 | §6 开头逐字写「下面四条排在最前面，因为它们最容易出事」，四条是 ①数据是仿真的 ②**公网链接公开可达 + 口令公开 + 没绑口令的账号会被抢绑** ③**读操作不留痕、写操作全部留痕** ④一键重置 ⇒ **两条都在最前面那四条里**（②③） | ✅ |
| 200 行上限 | **160 行** / 21 632 B（`Get-Content).Count` 与 `Get-Item.Length` 双量） | ✅ |

### 5.4 说明书 ↔ spec 的第二个所有者（抽 5 处）

| # | 处 | 它是抄还是给指针 | |
|---|---|---|---|
| 1 | §5 末「完整的 16 条路由清单（含每条要什么身份）见 **spec §13.6**，本文不抄第二份」+ §5 那张表**只有 1 行**（`/bind`） | ✅ **给指针**。⚠️ 并核了 Task 5 那个裁定「只给四条路线覆盖不到的那几条」：今天**确实是 1 行**，而「16 个页面里的 15 个」这个算术也自洽（16 − 1 = 15） | ✅ |
| 2 | §6 末「逐字口径见 **spec §13.15**」+ 逐条交代挑了哪 8 条 | ✅ 给指针（**没有**把 11 条抄一遍） | ✅ |
| 3 | §2① 末「核对方法、以及本仓那一份的核对结果见 **spec §13.17.2**」 | ✅ 给指针（**没有**抄 checksum） | ✅ |
| 4 | §3 口令那一格：不抄口令的**所有者**，只指 `demo_bootstrap.py` 的 `DEMO_PASSWORD` 那一行 | ✅ 给指针（口令字面量出现 **3** 次：账号表 1 次 + 三件事里 2 次，而**每一次都是要念给甲方听的**，不是第二份定义） | ✅ |
| 5 | §4 各步的数字（108.0 / 100.0% / 21 条 / 6.37 / 15 人 / `4C51674D` …） | ⚠️ **这些是抄的**（它们是**实走取证**的一部分，不是口径）—— §4 开头已经用两句免责兜住：「下面每一步都在真机上逐步走过一遍」「文中那些数字取自**刚灌出来**的试用库；你们试用之后（处置过预警、标过已读）它们会变」⇒ **是有意的时点快照，不是第二个所有者**。⚠️ 代价如实说：本席实测这 **26** 个数字今天**逐个仍对**（§5.1 / §5.2），而它们的寿命 = 那份库的干净程度 | ⚠️ 有意为之，可接受 |

---

## ⑥ F5 + F6

### 6.1 F5 · 隧道档四格

| 格 | 取证 | 结论 |
|---|---|---|
| **`-Protocol` 三档拼装** | ① 读代码：`tunnel.ps1:372` `Arguments = @('tunnel','--url',$LocalBase,'--no-autoupdate','--protocol',$ChosenProtocol,'--logfile',$LogFile)` —— **原样**传，脚本不在自己这一层实现回落；② 变异 **U3**（摘掉 `'--protocol', $ChosenProtocol`）→ `test_tunnel.py` **红**；③ 变异 **U1**（摘掉 `[ValidateSet('auto','quic','http2')]`）→ **红**；④ 那条守卫本身**是可执行的**：`test_tunnel.py:810-874` 把 `Resolve-TunnelBackend` **切出来在干净 PowerShell 里真跑三档**，断言三档各拼出 `--protocol <原值>`、**互不相同**（反空转）、`--protocol` 排在 `--logfile` 之前、孤儿标记 `pe_tunnel_<Port>` 一个参数都没少、且 **ssh 那一支一个 `--protocol` 都没有** | ✅ **`ValidateSet` 真的承重**（cloudflared 静默接受 `--protocol bogus`，故它是唯一那道闸；摘掉它守卫当场红） |
| **530 判据** | ① `tunnel.ps1:232` `$EdgeDeadStatus = 530`，而 `:221-231` 逐字记了它的响应形状（`Invoke-WebRequest` 会**抛** `WebException`、`[int]$_.Exception.Response.StatusCode` = 530、`ContentType` = `text/plain; charset=UTF-8`、`Status` = `ProtocolError`；⚠️ 而「压根连不上」那一档 `Response` 是 `$null`、`Status` 是 `ConnectFailure` ⇒ **取状态码之前必须先判 `$null`**）；② 变异 **U2**（530 → 599）→ `test_the_edge_530_is_recognised_and_never_reaches_the_url_file` **当场红** ⇒ 「抓到 URL 但复核回 530 时不许把死链接写进 `.trial/public-url.txt`」那一格**有牙**。⚠️ 本席**没有**自己起一个本地假 530 端点复现（那需要另起一个 HTTP 服务并改 hosts / 用 `--url` 指过去；变异 U2 已经是可执行判据的等价证据） | ✅ 判据在、且有守卫；⚠️ 但它**只认 530**，见 **S2-2** |
| **watchdog** | ① 缺省 `[int]$Watchdog = 0` = 关，变异 **U4**（0 → 60）→ **红** ⇒ 缺省被钉住；② 连续几拍才报 = `$WatchdogAlarmAfter = 3`，变异 **U5**（3 → 1）→ **红** ⇒ 也被钉住；③「只打印不重开」：`tunnel.ps1:902-…` 那段只 `Invoke-WebRequest` + `Write-Host`，**没有任何 `Start-Process` / 重启**；④ `tunnel.ps1:884-889` 在缺省档下**自己把这一格的后果说出来**：「自检 = 关（`-Watchdog` 缺省 0）⚠️ 于是「隧道进程活着、而那条链接已经死了」那一档本脚本**不会**告诉你（本波实测到过：quic 跑约 3 小时后本机 UDP 出网断了，进程还在、URL 回 HTTP 530）。要长跑请加 `-Watchdog 60`。」 | ⚠️ 见下面的**判断** |
| **`.trial/public-url.txt` 的生命周期** | ① `tunnel.ps1:992-996` 在 `finally` 里删它（并印一句为什么）；② `tunnel.ps1:293-298` 在**开工时**也删上一轮留下的那一份（「留着它等于留下一句看得见的谎」）；③ 而 spec **5099-5102** 逐字登记了那一格的洞：「⚠️⚠️ **硬杀那一档 `finally` 跑不到**…`cloudflared` 作为**孤儿活着**、`.trial/public-url.txt` 也**留着**」；④ **实测今天磁盘上就是那一档**：文件在（1 472 B / `0AB5FAF553A5A1E7`），里面写着 `url = …podcasts-mitchell-donald-americas…`、`隧道 PID = 10128`，而 **PID 10128 不在**、那条 URL 实测连不上；⑤ ⚠️ 而 Task 4 自报「已按开工量到的字节还原（1472 B / `0AB5FAF553A5A1E7`）」—— 本席量的**逐字相同** ⇒ **Task 4 真的还原了**，这份死链接文件是 **Task 3 那一轮**留下的、不是 Task 4 漏的 | ⚠️ 见 **S3-3** |

⚠️ **watchdog「只打印不重开」对不对 —— 本席的判断：裁定对，缺省错，落点也错。**

1. **「不自动重开」是对的**，理由与脚本自己写的一致且本席同意：quick tunnel 的地址是
   Cloudflare 当场随机发的，自动重开会**换掉甲方手上那条链接**（他们已经把它发进群、写进邮件、
   投在屏上了）—— 一条换掉地址的自愈比一条看得见的死链更坏。
2. ⚠️ **而「只打印到一个没人看的终端」在今天这格事故里等于没打印**。本席的现场证据（§1.4 第 ⑤ 格）：
   链接在复核窗口内死了（DNS 已被撤），`cloudflared` **进程还活着**，
   机器上**没有任何一处**说它死了 —— 没有 watchdog（控制者是手工起的隧道）、
   而唯一那个「链接住在哪」的文件（`.trial/public-url.txt`）指向**另一条也死掉的**链接。
   甲方那边只是「打不开」，而**谁知道要重开**？没人。
3. **最小处置**（⚠️ **不是**改「不自动重开」那条裁定）：
   ① `-Watchdog` 的**缺省从 `0` 改成一个非 0 值**（例如 `60`）—— 它今天缺省关，而
   「进程在、链接死」是**本波亲自撞到的那一档**，不是理论档；缺省关掉一个只打印、
   不改变任何行为的自检，换来的是「与本波之前逐字相同」，这个交换在今天不划算；
   ② 报警那一拍除了 `Write-Host` 之外，**再写一行进 `.trial/public-url.txt`**
   （例如把 `url = …` 那一行改成 `url = ⚠️ 已失效（<时刻> 起连续 3 拍不通）…`）——
   那个文件是甲方/运维**真会去读**的地方，而终端不是；
   ③ 说明书 §8 第 1 步补一句「⚠️ 链接失效**不会**自动恢复，必须我方人工重开」；
   ④ 若要更狠：`-Watchdog` 报警时**可选**地发一次本机通知（`msg *` 一类）——
   但那是新功能，本席**不建议**在交付前加。
   ⇒ 记 **S3-6**。

⚠️ **QUIC 断掉那一档 `tunnel.ps1` 今天能不能自己发现**：**不能**（`-Watchdog` 缺省 0）。
⚠️ **spec §13.17.9 与 `.DESCRIPTION` 有没有把这一格写清**：**写清了**（`tunnel.ps1:106-115`
的 `.DESCRIPTION` 有专节「⚠️ `-Watchdog`：长跑期的自检，⚠️ **只打印、不自动重开**」，
并把「自动重开会换掉甲方手上那条链接」的理由逐字写了；`.PARAMETER Watchdog` 也写了
「缺省 **0 = 关**」）⇒ **文档不欠账，欠的是缺省值**。

⚠️ **本席一次都没跑 `tunnel.ps1`**（它会覆盖 `.trial\public-url.txt`）⇒ 上面四格全部是
「读代码 + 定点变异打红可执行守卫 + 磁盘实物」三种取证，**没有**端到端跑一次隧道。

### 6.2 F6 · 缺陷修复的完整性（Task 5b 那三格）

#### 6.2.1 打卡表单四格（**真提交过**，在实例 B / 8042 上，一次都没碰 8030）

| 格 | 实发 | 结果 |
|---|---|---|
| ① 已有记录那天 | `POST /api/training-logs {"log_date":"2025-10-12","completed":true,"duration_min":30.9,"feeling":"easy","is_rest_day":true}` | **409** `integrity_conflict`，`message` 逐字 `UNIQUE constraint failed: training_log.student_id, training_log.log_date`。**页面看得见人话**：`CheckIn.vue:553-557` 渲染 `{{ submitError.code }} · {{ submitError.status }}` + `submitAdvice`（`:255`）+ `<code>{{ submitError.message }}</code>`；而 `:244` 逐字是 `if (err.code !== 'integrity_conflict') useApiError().raise(err)` ⇒ **409 刻意不进红色横幅**（它是页面内容，不是系统坏了） |
| ② 换一天 + `30.9` | `POST … {"log_date":"2025-12-12","duration_min":30.9,…}` | **201**，回 `{"id":841,…,"duration_min":30.9,…,"source":"checkin","batch_id":null}`。**绿色「已打卡」**：`CheckIn.vue:545-551` `<SuccessMark :visible="stamp" text="已打卡" tone="moss">`（`moss` = 绿，spec §15 A2 逐字记着「色值今天已经是 `--green: #2a7549`」），`stampCaption` = `${log_date} · 按时/迟交 · 服务端记于 ${…}` |
| ③ `duration_min` 后端会拒的值 | `-1` → **422** `greater_than_equal`（`ctx.ge=0.0`）；`"abc"` → **422** `float_parsing`（`unable to parse string as a number`） | **用户看得见、不是静默**：`CheckIn.vue:257-259` 对 `unprocessable_value` / `request_validation_failed` 各给一句人话（「提交的值没通过校验。⚠️ 检查 `duration_min` 是不是一个 ≥ 0 的数、`log_date` 是不是 `YYYY-MM-DD`」），由 `:553-557` 那块画出来；⚠️ 而这两档**会**进红色横幅（只有 409 不进） |
| ④ 必填项留空 | 缺 `log_date` → **422** `missing`；缺 `completed` → **422** `missing` | ✅ 后端拒。⚠️ 而**前端更早一档**：`log_date` 那个 `<input>` 带 `required`（`CheckIn.vue:390`）⇒ 原生校验在 `submit` **之前**就拦下，由 `useFormValidity` 说出「表单没有提交出去：「<label>」这一格没通过浏览器自带的校验」+ 浏览器给的理由 + 一句下一步 + 「⚠️ 本次**没有**发出任何请求」，画在提交按钮**上面**（`:529-532`，`role="alert"`） |

⚠️ **顺带实测到一格没有上界的**：`duration_min = 1000000000.0` → **201 收下**
（`{"id":842,…,"duration_min":1000000000.0,…}`）。后端只有 `ge=0`、前端只有
`min="0" step="any"` ⇒ **一次十亿分钟的打卡是合法的**。非本波引入，记 **S4-5**。

#### 6.2.2 ⚠️ 反静默的覆盖面：**本席自己数了一遍，没有第 4 张该挂而没挂**

扫 `frontend/src/**` 全部 `.vue`（**排除** `api/generated/`），判据是「`<template>` 里
有 `<form>`」：

| 文件 | `<form>` | 输入控件 | 带原生约束的属性 | 挂了 `useFormValidity` |
|---|---|---|---|---|
| `views/student/CheckIn.vue` | 1 | 3 | `required`×1 · `step`×1 · `min`×1 · `type="number"`×1 · `type="date"`×1 | ✅ |
| `views/auth/Login.vue` | 1 | 3 | `required`×2 | ✅ |
| `views/auth/Bind.vue` | 1 | 7 | `required`×6 · `type="date"`×1 | ✅ |
| `views/student/RpeEntry.vue` | 1 | 2 | **0** | —（不需要） |
| `views/admin/ResourceList.vue` | 1 | 4 | **0** | —（不需要） |
| `views/admin/ResourceDetail.vue` | 1 | 3 | **0** | —（不需要） |

⇒ 全仓 **6** 张 `<form>`，其中**带原生约束的恰好 3 张，3 张全挂了**，
**「有约束却没挂」= 0 张** ✅ —— Task 5b 的自述（「今天挂了它的三张表单 = 本仓**全部**
带原生约束的表单」）**为真**。⚠️ 而 `Login` / `Bind` 的 `required` 会撞同一族静默这一点，
Task 5b 也自己点到了，且**已经挂上**（不是只登记）。
⚠️ `src/components/` 下 **0 个 `<form>`** ⇒ 那三张没挂的（`RpeEntry` 的
`:disabled="!canSubmit"`、管理台两张把 number 画成 `type="text"` 再由 `api/contract.ts`
的 `assembleBody` 自己报错）挂上去确实是恒不触发的死路径。
⚠️ **一格守卫范围的小口子**：`smoke.mjs` 第 17 步 §FormValidity 那一拍只扫 `src/views/`
（`useFormValidity.ts:81-83` 逐字交代），而今天 `src/components/` 下 0 个 `<form>` ⇒
**今天没有漏**，而「往 `components/` 里加一张带约束的表单」不会被抓到。记 **S4-8**。

#### 6.2.3 `durationText` 那一格：修法的形状对，同族自查**干净**

* **修法**：`CheckIn.vue:153` `const durationText = ref<string | number>('')`（**不再是
  `Ref<string>`**），`:219` `const duration = String(durationText.value).trim()`，
  预填那一处 `:200` 也是 `String(existing.duration_min)`。⇒ `vModelText` 在
  `type="number"` 上运行时给的 `number` 不会再让 `.trim()` 抛 `TypeError`。
  `:131-152` 的注释把病灶、CDP 实测原文（`[unhandled] native event handler TypeError:
  durationText.value.trim is not a function`）、以及「它此前一直没被发现是因为同一个输入框上
  还有第二个静默（`step="0.5"`）」三格都记了。
* **`step` 那一格也改了**：`CheckIn.vue:474` 实测 `step="any"`（改前 `step="0.5"`），
  `:439-466` 逐字交代了为什么改成 `any`（后端只有一个下界 `ge=0`、**没有** `multiple_of`）
  以及「两件事**都做了**」（改 `step` + 挂 `useFormValidity`）。
* **同族自查**（还有没有别的 `Ref<string>` 绑在 `type="number"` 上）：本席扫了
  `src/**` 全部 `type="number"` 的输入控件 —— 只有 `CheckIn.vue` 那一处；
  管理台两张表单把 number 一律画成 `type="text"`（`useFormValidity.ts:78-79` 逐字记着这一格），
  故**没有第二处同族**。⚠️ 这一格本席是**静态**核的（读源码 + 数控件），
  没有在浏览器里逐个触发；标「静态核验，未做运行时同族扫描」。

#### 6.2.4 19 处会随 id/身份变假的散文：抽 5 处 + **第 20 处找到了**

spec §13.18.5 那张表是 **12 行**（其中 #2 含 3 处、#11 含 4 个文件 × 2 处 ⇒ 合起来是派单说的
**19 处**），另登记 **4 类**待清扫（① `<script>` docblock 13 个文件 ② 后端 docstring
③ `Notifications.vue` 空态写死的「19 条通知 / 19 个学生 id」 ④ `.auth__advice` 两份 CSS）。
⚠️ 派单说的第 5 类（`toPlainText` 不反转义实体）不在 §13.18.5 那 4 条里，见 §6.2.5。

**抽验 5 处（判据：改前那句假话今天在**渲染出来的** template 正文里还有没有；剥掉 HTML 注释）**

| # | 抽的那一处 | 实测 | |
|---|---|---|---|
| #1 | `StudentDetail.vue` 第 06 块「学生 N **确实**由该教师本学期任教」 | template 里 **0** 命中 ⇒ 已修 | ✅ |
| #4 | `StudentDetail.vue` 第 03 块「读的是**匿名的** `GET /api/stratification-results`」 | template 里只在一条 **HTML 注释**（`:719`「⚠️ 改前这一格写的是…openapi 上它挂 security…」）里出现 ⇒ 渲染面已修 | ✅ |
| #7 | `Dashboard.vue` 空态「挂 `X-Teacher-Staff-No`…T0001 陈国华（班 1+3）…」 | `X-Teacher-Staff-No` **0** 命中、`陈国华` **0** 命中（整份文件都没有）⇒ 已修 | ✅ |
| #10 | `Home.vue` 空态「三个挂 `X-Student-Id`…`?student=4`…60 个学生，其中 **4、11、15、17** 四个」 | `X-Student-Id` **0** 命中；`4、11、15、17` 只在**两条 HTML 注释**（`:244`/`:251`，逐字解释为什么删）里 ⇒ 渲染面已修 | ✅ |
| #11 | `CheckIn.vue` / `RpeEntry.vue` / `WeeklySheet.vue` 空态「身份切换器」 | 三个文件的 template 里 **0** 命中（`RpeEntry.vue` 整份文件剩 1 处在 `<script>` 里 = 登记的待清扫 ①） | ✅ |

⇒ **抽的 5 处（覆盖 7 个文件）真修了**。#12 那处见下面 S3-5（**修了、但没照自己写的处置修完**）。

⚠️⚠️ **第 20 处：找到了，在 `MiniTest.vue`（一个 Task 5b 整个漏掉的文件）** → 见 **S3-1**。

#### 6.2.5 ⚠️ `toPlainText` 不反转义 HTML 实体：**今天没有让任何一条 smoke 拍变成永绿**

* **病灶成立**：`smoke.mjs:496-498` `toPlainText(html)` = `stripEmbedded(html)`
  → `.replace(/<[^>]+>/g,' ')` → `.replace(/\s+/g,' ')`，**一步都不反转义实体**
  （全文件搜 `replace(/&` = **0** 命中）；而它吃的 html 一律是
  `document.documentElement.outerHTML`（`:2763` / `:3375` / `:3761`）⇒ 文本里的
  `>` 在 `outerHTML` 里是 `&gt;`，任何含 `>` 的 needle **永远匹配不上**。Task 5b 的顶回①**为真**。
* ⚠️ **而失效方向要分清**：「永远匹配不上」让**正向**断言（`check(…, text.includes(needle))`）
  **永红**（会被立刻发现），只有**反向**断言（`check(…, !text.includes(needle))`）才会**永绿**。
* **本席把全部 `.includes(` 都扫了**（正向 + 反向，参数用括号配平切出来）：
  * **反向**且 needle 含 `<` / `>` / `&` 的：**恰好 1 条** —— `smoke.mjs:5157` 的
    `!…includes('<form')`。⚠️ 而它**不是永绿**：`<form` 是**标签**，`outerHTML` 里标签
    **不被转义**（被转义的是文本内容），故有 form 时它真会命中、没 form 时真不命中 ⇒ 判据有效。
  * **正向**且 needle 含 `<` / `>` / `&` 的：**0 条**。
* ⇒ **结论：今天没有任何一条 smoke 拍因为这一格而永绿。** 它是一格**潜伏**风险
  （下一个人写一条「页面正文里不许出现 `a > b` 这类含 `>` 的串」的反向断言就会踩到，
  而它会**静默永绿**）。最小处置：`toPlainText` 末尾补一步
  `.replace(/&gt;/g,'>').replace(/&lt;/g,'<').replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;/g,"'")`
  （⚠️ `&amp;` 要**最后**替换，否则 `&amp;gt;` 会被解两次），并加一条反空转守卫
  （喂一段含 `&gt;` 的 html，断言剥完能搜到 `>`）。**不需要重建 dist**（`smoke.mjs` 不进包也不进 dist）。
  记 **S4-15**。

---

## ⑦ F7 · 数字与台账

### 7.1 断言核验表（**31 条**，除 §5.1 那 33 条之外的）

| # | 断言（出处） | 实测 | |
|---|---|---|---|
| 1 | 后端 openapi：**74 路径 / 102 操作 / 挂 security 84 / GET 63（15 匿名 + 48）/ securitySchemes 3** | 进程内 `create_app().openapi()`：**74 / 102 / 84 / 63（15 匿名）/ 3** | ✅ 逐格 |
| 2 | openapi **420 367 B / sha256[:16] `6058F97F09B35855`** | 紧凑 `json.dumps`（`ensure_ascii=False, separators=(',',':')`）= **420 367 B / `6058F97F09B35855`**；⚠️ 并从**跑着的服务**上 `GET /openapi.json` 也是 **420 367 B**（sha[:12] `6058f97f09b3`）⇒ 两个口径同一个数 | ✅ |
| 3 | openapi **catch-all 0** | 路径里 `{…path}` 形状 = **0** | ✅ |
| 4 | 「三档 `PE_TRIAL` 下逐字节相同」 | ⚠️ 本席只实测**两档**（`PE_TRIAL=1` 与 `=0`）：两档的 `GET /openapi.json` 都是 **420 367 B / `6058f97f09b3`** ⇒ 两档相同；**第三档（`prod`）未实测**（要再起一个 `PE_ENV=prod` 实例） | ⚠️ 两档已核 |
| 5 | 表 **28 张**（`sqlite_master` **29**） | `/api/health` 回 `tables: 28`；本席那份灌出来的库 `sqlite_master` 里 `type='table'` = **29**（28 + `alembic_version`） | ✅ |
| 6 | 迁移链 **4 单头**：`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b` | 灌库时 alembic 逐条打印：`-> 53e5a548c40e`（基线，「Plan 06 之前那 26 张表」）→ `0b7da3d20211`（`login_attempt`）→ `7f3923d8af84`（`audit_log`）→ `0ac943e0da9b`（`login_attempt.login` 32→64）⇒ **4 条、单头、顺序逐字相同** | ✅ |
| 7 | 16 条路由（`routes` 数组 **20**） | `router/index.ts` 里 `routes` = **20** 条 = 16 页面 + `/` + `/s` + `/t` + catch-all | ✅ |
| 8 | `frontend/dist` **29** 个文件 | **29**（开工与收尾各量一次，且 5 个产物哈希逐字未变） | ✅ |
| 9 | 包 **10 305 418 B / 339 文件**（Document 28 / backend 207 / frontend 99 / scripts 4 / README 1） | 逐字相同（§4.1 / §4.5） | ✅ |
| 10 | `tools/cloudflared.exe` **55 365 048 B** | 实测 **55 365 048 B**（mtime `2026-10-15 17:25:18`） | ✅ |
| 11 | cloudflared version `2026.10.0` | `.trial\public-url.txt` 里逐字记着 `cloudflared version 2026.10.0 (built 2026-10-05T08:39 UTC)`；⚠️ 本席**没有**自己跑 `cloudflared --version`（那要动 `tools\`，而它是 gitignore 的本机工具）；官方 checksum 的独立比对是 Task 3 做的（spec §13.17.2），本席**未复验** | ⚠️ 半 |
| 12 | `serve.ps1` 参数面 `-Port`(8020) / `-SkipBuild` / `-Lan` | `serve.ps1:123-127` 逐字三个，`-Port` 缺省 **8020** | ✅ |
| 13 | `trial.ps1` 参数面 `-Port`(8030) / `-Lan` / `-Reset` / `-Build` | `trial.ps1:124-131` 逐字四个，`-Port` 缺省 **8030** | ✅ |
| 14 | `tunnel.ps1` 参数面 `-Port`(8030) / `-Backend auto\|cloudflared\|ssh` / `-Protocol auto\|quic\|http2` / `-Watchdog <秒>`(缺省 0) | `tunnel.ps1:177-189` 逐字四个，`ValidateSet` 两组取值逐字相同，`$Watchdog` 缺省 **0** | ✅ |
| 15 | `pyproject.toml` / `package.json` / `.gitattributes` 对 `fedf24f` **零 diff** | `git diff --stat fedf24f..HEAD` 的 38 个文件里**没有**这三个 | ✅ |
| 16 | `.gitignore` 只加了 `dist-pack/` 一行非注释 | ⚠️ `git diff --stat` 报 `.gitignore | 51 +`（**51 行**）⇒ **不是「只加了一行」**。⚠️ 而 `dd667cc` 的 commit message 逐字是「忽略 `tools/` 与 `.trial/`（Plan 07 Task 3 的两样本机产物）」⇒ 51 行里含注释与那两条。本席**没有逐行 diff** 它 ⇒ 判「**未能核验**：派单说的『只加了 `dist-pack/` 一行非注释』与 `--stat` 的 51 行不矛盾（那 51 行里可以只有一行是 `dist-pack/`），但本席没有逐行数非注释行」 | ⚠️ 未核验 |
| 17 | 演示口令唯一所有者 = `demo_bootstrap.py` 的 `DEMO_PASSWORD` | `serve.ps1:504-506` 与 `trial.ps1:344-352` 都**刻意不抄字面量**并逐字说明理由；`test_trial.py` 有一条 `test_trial_ps1_does_not_become_a_second_owner_of_the_demo_credentials` | ✅ |
| 18 | 「管理台 **23** 个资源 / **9** 可写 / **14** 只读」 | `catalog/resources.ts`：`path:` **23**、`writable: true` **9**、`false` **14** | ✅ |
| 19 | 「管理台 **26** 个写入操作」（`demo_bootstrap.py` 灌库时打印给甲方） | openapi 的 39 个非 GET 操作里，**13** 个不是管理台的 CRUD 写（4 个 auth + `pipeline/run-daily` + `alerts/{id}/handle` + `notifications/{id}/read` + `class-sessions/{id}/open-rpe` + `rpe-records` + `training-logs` + `mini-tests/batch` + `prescriptions/{id}/overrides` + `prescriptions/{id}/regenerate`）⇒ 39 − 13 = **26**，分布在 **9** 个资源族上（8 族 ×3 + `semesters` ×2 = 26）⇒ 与「9 个可写」**互洽** | ✅ |
| 20 | spec §15 台账 **24 条 / 7 组** | 逐条数：**24** 条（A1-A3 / B1-B5 / C1-C3 / D1-D4 / E1-E2 / F1,F2,F4,F5 / G1-G3，**0 个重号**）、**7** 组（A–G） | ✅ 逐字 |
| 21 | §15 A2「`moss` **35 处 / 13 个文件**」 | 实测 `frontend/src/**` 的 `.vue/.ts/.css` 里 `moss` **35** 命中 / **13** 个文件 | ✅ 逐字 |
| 22 | §15 F5「Plan 01 计划文档里那 **24** 处 `&&`」 | 实测那份文档里含 `&&` 的**行数 = 24**（⚠️ 而 `&&` 的**出现次数 = 26**）⇒ 台账按**行**数，**24 为真** | ✅ |
| 23 | §15 D4「浏览器标签上没有图标」 | `frontend/dist/index.html` 里 `rel="icon"` / `favicon` **0** 命中（dist 里那 2 个 `.svg` 是校徽与校名锁排，不是 favicon）⇒ **仍然没做** | ✅ 台账为真 |
| 24 | §15 G2「打卡页有一句随数据变假的散文：`source` 的取值」 | `CheckIn.vue:637-638` 仍然写「`student` 才是从本页交上去的」，而后端实发回的是 `checkin` ⇒ **仍然没修，且台账说得很准** | ✅ 台账为真 |
| 25 | §15 G1「`tunnel.ps1 -Backend ssh` 的成功路径未验证」 | 本席**也没验**（要一个 ssh 后端）⇒ 台账为真 | ✅ |
| 26 | §15 G3「包里的 `scripts\tunnel.ps1` 找不到 `cloudflared`，会回落到 G1 那一支」 | 包里 `(^|/)tools/` 命中 **0** ⇒ 包里确实没有那个二进制；而 `tunnel.ps1:345-349` 的 `auto` 逻辑是「cloudflared 在就选它、否则选 ssh」⇒ **台账为真** | ✅ |
| 27 | §15 B1「读审计表」/ C2「谁被锁过查不出来」 | 实测 `audit_log` 的列恰好 **9** 个（`at/id/method/path/staff_no/status/subject_id/subject_kind/target`），**没有任何一格能装「这一次是锁定」**；且 15 个写请求之后 `methods` 全是 `POST`、**0 个 GET** ⇒ **两条都仍然没做** | ✅ 台账为真 |
| 28 | §13.15 第 10 条 / §15 D2「`/openapi.json` **417 032 B**」 | 今天 **420 367 B**（§13.16 那张表**已经记了** 417 032 → 420 367 这一格，而 §13.15 第 10 条与 §15 D2 两处旧数**没跟着改**） | ❌ 过期 → **S4-7** |
| 29 | `backend/app/static.py:85`「本仓的基线是 **72** 路径」· `app/api/audit.py:41`「**99** 个操作里 **60** 个是 GET」· `audit.py:241`「**71** 个路径模板」 | 今天 **74 / 102 / 63 / 74** ⇒ **三处都过期**，而它们都在 `backend/app/**` 里 ⇒ **随包交付给甲方** | ❌ → **S4-6** |
| 30 | 局域网 IPv4 `192.168.31.11` | `Get-NetIPAddress -AddressFamily IPv4`（滤掉 `127.*` 与 `169.254.*`）= **192.168.31.11 / WLAN**，且是**唯一一个** | ✅ |
| 31 | 说明书 §8③「单次隧道往返 5.6–6.3 秒 ⇒ 告示最坏约 11–13 秒」 | ⚠️ **未能核验**：那要对着公网链接反复打 `GET /api/health` 计时，而本席的纪律是「只允许匿名 `GET /api/health` 与匿名 `GET` 页面」——本席只打了**一发**（开工那一格），没做多次计时；且收尾时那条链接已经死了 | ⚠️ 未核验 |

### 7.2 §15 台账 **24 条**的抽验（反查「有没有其实做了而台账说没做」）

抽了 **6 条**（A2 / B1 / C2 / D4 / F5 / G1·G2·G3），**逐条都仍然没做**（#21–#27），
**没有一条是「其实做了而台账说没做」**。⚠️ 另发现台账自己的**两处组内件数与条目不符**
（F 组标题「三件」而列了 4 条；G 组标题「一件」而列了 3 条；**总数 24 / 7 组是对的**）→ **S4-4**。

### 7.3 ⚠️ 盲区：**公网档 smoke 自 Task 3 之后没有重跑过**

* **事实核**：自报的四档断言数是 dev **739** / 产品档 **739** / 试用档 **771** / 公网档 **711**，
  而公网档那 **711** 是 **Task 3 时点**的值；此后 **Task 5b 给 smoke 加了约 60 条断言**
  （`smoke.mjs` 在 `fedf24f..HEAD` 的 diff 里是 **+902 行**）、**Task 4 又改了三个脚本**
  （`serve.ps1` +244 / `tunnel.ps1` +1012 / `package.ps1` +624）⇒ **「公网档今天是不是绿的」无人知晓**。
* ⚠️ **本席不能跑它**：公网档要穿过那条公网链接打真请求，而**任何登录都会往
  `user_session` 与 `audit_log` 各写一行**，甲方在审计留痕页上会看见（派单 §2 逐字禁止）。
  而本席也**没有**在自己起的实例上跑 smoke —— smoke 会写脏它所指向的那一份库，
  而本席的 A 实例是 F4 只读核验的检材，写脏它就等于把自己的取证弄脏。
* ⚠️ **而这一格今天更吃紧了**：本席收尾时那条公网链接**已经死了**（§1.4 第 ⑤ 格）⇒
  今天**根本跑不了**公网档。
* **处置建议**（给控制者）：
  1. **等甲方试用结束之后**，由控制者在一个**独立的**试用库上（`trial.ps1 -Reset` 起一份新的、
     或另建一个 `PE_DB_URL` 指到 TEMP 里的库）**重开一条隧道**（`tunnel.ps1 -Protocol http2 -Watchdog 60`
     —— ⚠️ 带 `http2`，因为本机今天的 QUIC 路径按派单说是断的），然后跑一遍**公网档** smoke；
  2. 跑之前先确认 `PE_COOKIE_SECURE` 那一档（`2ee49cf` 加的第四档判据）取的是**公网档的期望**；
  3. ⚠️ 跑完**不要**把那条链接发给甲方之前不复核 —— 照 `tunnel.ps1` 的 ④ b，
     它会自己复核一次（并且今天起认得 530）；
  4. 把结果（四档的断言数）补进 spec §13.16/§13.17/§13.18 的那张三档表，
     并**明确标注**公网档那一格的**时点**（今天是 Task 3 时点的旧值）。

### 7.4 ⚠️ 甲方在用的那一份 `dist` 是**哪个 commit** 构建的：**是 HEAD（`a45a3f0`）的源码**

三格交叉取证（⚠️ 本席**没有**跑 `npm run build`，那会清空甲方正在收的产物）：

1. **时刻**：`frontend/dist` 全部 29 个文件的 mtime 都是 **`2026-10-16 00:36:04`**；
   而 `git log -- frontend/src frontend/package.json frontend/vite.config.ts` 的最新一条是
   **`41b7b91`（`2026-10-16 00:08:57`）**，merge `6a6ac1f` 是 **`00:35:34`**，
   HEAD `a45a3f0` 是 `03:34:59`（**只改报告**）⇒ **构建发生在 merge 之后、
   而此后 `frontend/` 的源码一个字节都没再改过**。
2. **产物内容**：在**甲方正在收的那一份** `index-DYNl778Q.js` / `AlertQueue-DSyjjO54.js` 里
   搜到只有 Task 1 与 Task 5b 之后才会存在的串 —— `表单没有提交出去`（Task 5b 的
   `useFormValidity`）· `本次**没有**发出任何请求`（同）· `这一天已经有一行了`（Task 5b 缺陷 ①）·
   `未再减`（`AlertQueue.vue` 的 `adjustment: null` 那一档）· `试用环境` / `高保真仿真` /
   `请勿录入真实学生信息` / `名学生均为虚构`（Task 1 的告示）· `身份确认超时` ⇒
   **10 个串逐个命中**，dist **确实含 Plan 07 的前端改动**。
3. **包 ↔ 仓库**：包里的 `frontend/dist/index.html` 与两个产物、以及 `frontend/src/App.vue` /
   `router/index.ts`，与仓库 HEAD 的那几份**逐字节相同**（§4.7）⇒ 甲方拿到的包 = HEAD。

⇒ **不构成 S1/S2**：甲方在用的产物与 HEAD 的源码**一致**。
⚠️ 如实交代这一格的**限度**：本席证的是「构建时刻晚于最后一次源码改动 + 产物里含新代码 +
包与仓库逐字节相同」，**不是**「重新构建一次会得到逐字节相同的产物」（那要跑 `npm run build`，
被禁止）。这三格合起来足以排除「甲方在用旧代码」，但不足以排除「vite 的产物不确定性」
（那一格本仓另有 `check:dist` 25 产物 / 787 824 字符 与 `--no-build` 口径 589 118 B 两个口径，
本席**没有复跑**它们 ⇒ 两个口径本席**都未核验**，如实记）。

---

## ⑧ F8 · 交付就绪度总判断 + 全部发现的分级汇总

### 8.1 甲方老师今天拿着那条公网链接 + 那份说明书，能不能自己走完四条路线？

**⚠️ 今天不能 —— 但阻塞项不在代码里，在链接上。**

* **链接**：本席收尾时那条公网 URL 已经 **DNS NXDOMAIN**（§1.4 第 ⑤ 格），而 `cloudflared`
  进程还活着、`.trial\public-url.txt` 指向**另一条也死掉的**链接 ⇒ **必须先由控制者重开一条**。
  ⚠️ 这**不是**代码缺陷（quick tunnel 的寿命本来就等于隧道进程的寿命，说明书 §2① 与 §8① 都写了），
  而它是**今天交付的第一个动作**。
* **重开之后**：以 §5.2 的实走结果为准 —— **路线一（学生端）走通**（9 步里 8 步实测对，
  第 9 步「标为已读」未实发）；**路线三（管理台）走通**（5 步全对）；
  **路线四（教师大屏）走通**（5 步的数字逐个对，含两个 8 位课堂口令逐字对）；
  **路线二（教师端）走到第 6 步全对，卡在第 7 步的那半句**：消息中心**会**多一条
  （正文与说明书逐字相同），而**训练单不会变**（系数本来就是 0.80）⇒ 见 **S2-1**。
* **说明书的真话率**：33 条可验证断言里 **对 29 / 错 4**（spec 行数、`error code: 1033`
  那一档的排他性、`public-url.txt` 会被删掉、「训练单与消息中心同时变」）。
  ⚠️ **数字面的准确率很高**（26 个业务数字逐个对上，含 `98.33` / `6.37` / `+0.10` /
  `62.7%` / `4C51674D` / `D2476ADA` 这一类），错的**四条全是「关于系统行为的断言」**，
  不是数出来的数。

### 8.2 甲方 IT 拿着那个 zip，能不能在他们自己的机器上起一份？

**⚠️ 只在解包路径不含空格时能。**

* ✅ **第一步（`python -m pip install -e backend`）通** —— 在干净 venv 里 **退出码 0 / 34 s**，
  装完 `import app.main` OK；**含空格与中文的路径下也通**（venv2，退出码 0）。
* ✅ **灌库通** —— `trial.ps1` 在含空格与中文的路径下把 60 人仿真库灌出来了
  （`--db-url` 里带空格也没断，`[1/7]…[7/7]` 与不含空格那一份逐字相同）。
* ❌ **起服务那一步在含空格的路径下当场失败**（`Error: Got unexpected extra argument
  (试用\backend\scripts)`）⇒ 见 **S1-1**。
* ✅ 不含空格的路径下**一条命令起服务 + 16 条路由逐条 200 + 停干净**（§4.4），
  且**全程 PATH 里没有 node**（实测 `(Get-Command node).Source` = 空，而 `serve.ps1`
  自己印「本次**不需要构建**：一次都没查 node、一次都没调 npm」）。
* ✅ 包内容：该有的 17 格 `$MustContain` 逐个在、`backend/data` **24** 个在、
  `frontend/dist` **29** 个在；不该有的（`.git` / `node_modules` / `*.db` / `.superpowers` /
  `tools` / `backups` / `.trial` / `__pycache__` / `.pytest_cache`）**0 命中**。
* ⚠️ **多带的**（README 没说）：`backend/tests/` **70** 个文件、`Document/` 里 **9** 份内部文档 +
  **15** 张截图 + **1** 份 `.doc` ⇒ 见 **S3-5**。
* ✅ **README 没有第二个所有者**（包里那份与仓库那份逐字节相同）。
* ✅ 最长条目路径 **75** 字符 ⇒ 离 260 至少 **109** 字符余量（Task 4 实测的「299 字符长路径
  两个压缩 API 都读不了」那一格与本包无缘）。

### 8.3 最小阻塞项（按严重度排序）

1. **重开一条公网链接**（运维动作，不是代码）—— 今天那条已经死了；⚠️ 顺手把
   `.trial\public-url.txt` 那份**写着死链接**的处理掉（重开一次 `tunnel.ps1` 会在开工时自己删它）。
2. **S1-1**：`serve.ps1` 的 `Start-Process -ArgumentList` 不给含空格的元素加引号 ⇒
   解包到带空格的路径**起不来**。⚠️ 若本波不修，**至少**在 README 与说明书 §2③ 各加一句
   「解包到一个**不含空格**的目录」（一句话的文档处置，能当场把这一格从「起不来」降到「照着做就行」）。
3. **S1-2**：发给甲方的 `dist` 里有 **5 处**「不做登录失败锁定」，而锁定**真的在**，
   且与同批交付的说明书 §6⑤ 直接互相打脸 ⇒ 要**重建 dist**（改的是 `App.vue` /
   `Login.vue` / `ApiErrorBanner.vue` / `client.ts` / `auth.ts` 五处文案）。
4. **S2-1**：说明书路线二第 6/7 步 —— 只改**说明书**（不动代码、不动 dist）。
5. **S2-2**：说明书 §2① / §8① 的「`error code: 1033`，⚠️ 不是「连不上」」—— 只改**说明书**
   （今天这一档实测是 NXDOMAIN = 恰恰是「连不上」）。
6. **S3-1**：`MiniTest.vue:416-418` 的「匿名 `GET /api/mini-tests`」—— 要与 S1-2 **同一次**重建 dist。

### 8.4 交付时必须一并说明的注意事项

**spec §13.15 那 11 条之外，本计划新增的（本席实测过或亲自撞到的）：**

| # | 注意事项 | 取证 |
|---|---|---|
| 1 | ⚠️ **链接的寿命可能比隧道进程更短**：本席实测到一档「`cloudflared` 进程活着、而主机名已被边缘撤掉（DNS NXDOMAIN）」—— 说明书只写了 530 + `error code: 1033` 那一档 | §1.4 第 ⑤ 格 / **S2-2** |
| 2 | ⚠️ **`.trial\public-url.txt` 今天可能写着一条死链接**（硬杀那一档 `finally` 跑不到，spec 5099-5102 已登记）；而控制者手工起的隧道**不写**这个文件 ⇒「链接住在哪」有两个形状，交付前应当**只留一个** | §6.1 第四格 / **S3-3** |
| 3 | ⚠️ **解包路径不要含空格**（除非先修 S1-1） | §4.3 / **S1-1** |
| 4 | ⚠️ **`dist-pack\` 会累积**：`package.ps1` **不删**旧的包（`package.ps1:96` 逐字写着），本机今天已经有 1 个 10 MiB 的；⚠️ 而它已进 `.gitignore`，故不会入库，只会占盘 | §4.1 |
| 5 | ⚠️ **`package.ps1` 会在 `$env:TEMP` 里留 staging 残渣**：本席 8 次跑动留了 **3** 个 `pe_package_*`（各 2–4 个文件 / 约 145 KB），且 **03:38:47 那一份在本席开工之前就在** ⇒ 与本波变异无关。⚠️ 它**不是静默**的（`package.ps1:616-617` 会打印「⚠️ staging 删不掉…请手工删」） | §1.5 / **S4-16** |
| 6 | ⚠️ **包里带 `backend/tests/` 70 个文件**与 9 份内部实施计划文档（README 没说）⇒ 交付时要么说明「这是技术对接依据的一部分」，要么把它们从 `$IncludeRoots` 里剔掉 | §4.5 / **S3-5** |
| 7 | ⚠️ **甲方装到的依赖版本与我们的开发环境不同**（fastapi 0.143.2 vs 0.141.1 等），今天**实测无害**（openapi 逐字节相同、四条路线的后端面全通），而这不是一个可以依赖的性质（没有 lockfile） | §4.2 / **S4-13** |
| 8 | ⚠️ **告示可能晚 11–13 秒才挂上**（说明书 §8③ 自己写了；本席**未能核验**那个秒数） | §7.1 #31 |
| 9 | ⚠️ **页面上有一个「业务日 `as_of`」输入框**（`IdentitySwitcher.vue:273-274`，16 条路由都在场），缺省是演示库的业务日 `2025-10-12`（`stores/identity.ts:45` 的 `DEMO_AS_OF`，持久化在 `localStorage`）。⚠️ **甲方把它改成今天，全站的数据面就会空掉**：本席实测不带 `as_of`（= 今天 `2026-10-16`）时 `/api/students/4/home` 的 `weekly_sheet = null`、`week = 59`，而 `/api/students/4/weekly-sheet` 直接 **404 `no_active_prescription`**（原文「学生 4 在 2026-10-16 没有生效的处方」）。**说明书一个字都没提这一格**，§8「出问题怎么自查」的三步也不覆盖它 ⇒ 建议在 §8 加第 4 步：「页面上一片空 / 说没有训练单 → 看会话条上那个『业务日 as_of』是不是被改过，改回 `2025-10-12`」 | **S3-7** |
| 10 | ⚠️ **`duration_min` 没有上界**（实测 1e9 分钟 → 201 收下）⇒ 试用时能造出一行荒谬的打卡 | **S4-5** |
| 11 | ⚠️ **`trial.ps1` 会打印「库里 60 名学生」与「八节：…」两处写死的数**（前者与 `demo_bootstrap.py` 的 argparse 缺省是两个所有者；后者只列了 7 项、且把 §5 的标题写成「16 条路由」） | **S4-2 / S4-3** |
| 12 | ⚠️ **公网档 smoke 是 Task 3 时点的旧值**，今天没人知道它绿不绿（且链接已死，今天跑不了） | §7.3 / **S4-10** |

### 8.5 全部发现的分级汇总

**S1 = 2 条 · S2 = 2 条 · S3 = 7 条 · S4 = 16 条**（合计 27 条）

#### S1（Critical）

| # | 一句话 |
|---|---|
| **S1-1** | **解包到含空格的路径时服务起不来**：`serve.ps1:449` 的 `Start-Process -ArgumentList` 不给含空格的元素加引号 ⇒ `--app-dir C:\…\体育系统 试用\backend\scripts` 被切成两截，uvicorn 原文 `Error: Got unexpected extra argument (试用\backend\scripts)`；而 README:54 与说明书 §2③ **一个字都没提**路径形状 |
| **S1-2** | **发给甲方的 `dist` 里有 5 处「不做登录失败锁定」，而锁定真的在**：`Login.vue:254`（登录页正文）· `App.vue:219`（16 条路由的页脚）· `ApiErrorBanner.vue:101`（401 的处置建议）· `client.ts:166` · `auth.ts:209`；实测 5 次坏口令之后第 6 次 **0.026 s** 返回（前 5 次 0.046–0.059 s = 锁定档一次 PBKDF2 都不跑的签名）、且**用正确口令也是同一份 401 / 82 B**；而同批交付的说明书 §6⑤ 说的正好相反（「连错 **5** 次会被锁 **15** 分钟」） |

#### S2（高）

| # | 一句话 |
|---|---|
| **S2-1** | **说明书路线二第 7 步的「闭环」承诺在演示库上不成立**：教师点「减量 20%」→ 200 / `handled` / 消息推给学生（正文逐字对）/ 顶行变「待处理 20 / 已处理 1」全都对，⚠️ 而响应里 `"adjustment": null`、`weekly_adjustment` 两度都是 13 行、学生训练单系数**点前点后都是 0.80** ⇒「训练单与消息中心同时变」的那一半**不变**；⚠️ 而且 T0001 那 **9** 条红色预警的学生**逐个**都已有 `source='auto'` 的 0.8 调整 ⇒ **点哪一条都一样**；⚠️ 页面自己是诚实的（`AlertQueue.vue:727-733` 会渲染「本次**未再减**」），而说明书没提这一段会出现 |
| **S2-2** | **说明书 §2① / §8① 把「链接死了」的症状写成一档、并逐字排除另一档**：它说「打开会看到 Cloudflare 自己的一页错误，写着 `error code: 1033`，⚠️ **不是**「连不上」」，而本席**今天亲自撞到的那一档是 DNS NXDOMAIN**（浏览器上就是「找不到服务器」= 恰恰是「连不上」）⇒ 自查第 1 步会把甲方指反方向；`.trial\public-url.txt` 表头那句「（实测变成 Cloudflare 自己的一页错误）」与 spec §13.17 的同一句同样只对 530 那一档成立 |

#### S3（中）· 7 条

| # | 一句话 |
|---|---|
| **S3-1** | **第 20 处散文**：`MiniTest.vue:416-418` 的**渲染正文**逐字写「它走的是**匿名** `GET /api/mini-tests`（180 行全量 + 客户端按 `student_id` 过滤）」，而实测匿名 **401**、openapi 上它**挂着 security**；⚠️ 它与 §13.18.5 已修的 #4/#5/#12 同族同形，而那一节逐字写着「这两类**必须本波修完**」，且 `MiniTest.vue` **不在 Plan 07 的 diff 里** ⇒ 那一波自查**整个漏掉了这个文件**，也**不在**它登记的 4 类待清扫里 |
| **S3-2** | 说明书 §0 说 spec 是「**5400 余行**」，实测 **6233 行**（差 833 行 / 13%） |
| **S3-3** | 说明书 §2① 无条件地说 `.trial\public-url.txt`「在隧道退出时会被脚本自己删掉」，而磁盘上今天正躺着一份**写着死链接**的它（1 472 B / `0AB5FAF553A5A1E7`、`隧道 PID = 10128` 而 PID 10128 不在、那条 URL 实测连不上），而**活着的**链接住在**另一个地方**（控制者手工起的 PID 45016）⇒「链接住在哪」今天有两个形状、而文件里那一个是死的。⚠️ 硬杀那一档 `finally` 跑不到是**已登记**的（spec 5099-5102），说明书没带那个但书 |
| **S3-4** | 说明书 §8 第 2 步说「这一格**你们自己改不了**（它是服务端的环境变量），请找我方」—— 对 §2②（`-Lan`）与 §2③（他们自己的机器）两档是**假的**：`serve.ps1:582` 自己就打印「去掉 `PE_ENV`（回到缺省的 dev 档），或去掉 `-Lan`」 |
| **S3-5** | **README 两处与包里的实物不符**（而说明书 §2③ 逐字说「一律以包里的 `README` 为准」⇒ README 就是这一格的唯一所有者）：① README:75 说 `/api/health` 是「三格 `{"status","tables","students"}`」，实测**四格**（多 `trial`，Plan 07 Task 1 加的）；② README:50 说包里的 `Document\` 是「spec 与甲方试用说明书」，实测 **28 个文件**（11 份 .md + 15 张截图 + 1 份 .doc），且 README **没提**包里带 `backend/tests/` **70** 个文件 |
| **S3-6** | **watchdog 的缺省值**：`-Watchdog` 缺省 **0 = 关**，而「进程在、链接死」是本波**亲自撞到**的那一档（且本席在复核窗口内又撞到一次）；缺省关掉一个**只打印、不改变任何行为**的自检，换来的是「与本波之前逐字相同」，在今天不划算。⚠️「**不自动重开**」那条裁定本席**同意**（自动重开会换掉甲方手上那条链接，比一条看得见的死链更坏）；欠的是缺省值与落点（打印到没人看的终端 vs 写进那个真会被读的文件） |
| **S3-7** | **说明书一个字都没提「业务日 `as_of`」那个输入框**：它在 16 条路由上都在场（`IdentitySwitcher.vue:273-274`），缺省 `2025-10-12`；甲方把它改成今天，全站数据面**当场空掉**（实测 `weekly_sheet = null` / `week = 59` / `weekly-sheet` → **404 `no_active_prescription`**），而 §8「出问题怎么自查」的三步不覆盖这一档 |

#### S4（低）· 16 条

| # | 一句话 |
|---|---|
| **S4-1** | `App.vue:91` 的注释写「`scripts/trial.ps1 -Students` 可以改它」—— `trial.ps1` **没有** `-Students` 参数（参数面是 `-Port`/`-Lan`/`-Reset`/`-Build`），而它逐字写着「`--students` 与 `--seed` **刻意不传**」；属 §13.18.5 待清扫 ① 那一族，而那 13 个文件里**没有点名** `App.vue` ⇒ 建议补进台账 |
| **S4-2** | `trial.ps1:359` 打印「**八节**：三条打开方式 / 账号 / 四条试用路线 / **16 条路由** / 须知 / 怎么重置 / 出问题怎么自查」—— 只列了 **7** 项（漏 §1「这是什么」），且 §5 的标题是「其余几条路由」不是「16 条路由」（§5 自己说完整清单在 spec §13.6） |
| **S4-3** | `trial.ps1:354` 打印「库里 **60** 名学生」是写死的，而告示那一格的 N 是从 `/api/health` 取的（`App.vue:90-96` 逐字交代了为什么不写死）⇒ 同一件事两个所有者 |
| **S4-4** | §15 台账 **F 组**标题写「三件」而列了 **4** 条（F1/F2/F4/F5；F3 已划掉）、**G 组**标题写「一件」而列了 **3** 条（G1/G2/G3）；⚠️ 总数 **24 条 / 7 组是对的** |
| **S4-5** | `duration_min` 只有下界 `ge=0`、**没有上界**：实测 `1000000000.0` → **201** 收下（前端也只有 `min="0" step="any"`，没有 `max`）⇒ 一次十亿分钟的打卡是合法的。非本波引入 |
| **S4-6** | 三处**随包交付**的代码注释里 openapi 计数过期：`app/static.py:85`「基线是 **72** 路径」· `app/api/audit.py:41`「**99** 个操作里 **60** 个是 GET」· `audit.py:241`「**71** 个路径模板」，而今天是 **74 / 102 / 63 / 74**。非本波引入 |
| **S4-7** | spec **§13.15 第 10 条**与 **§15 D2** 都写 `/openapi.json` 是 **417 032 B**，而今天是 **420 367 B**（§13.16 那张表已经记了这一格的改动，两处旧数没跟着改） |
| **S4-8** | `smoke.mjs` 第 17 步 §FormValidity 那一拍只扫 `src/views/`；今天 `src/components/` 下 **0** 个 `<form>` ⇒ 今天没有漏，而「往 `components/` 里加一张带约束的表单」不会被抓到 |
| **S4-9** | `package.ps1` 里那 4 份**脚本内自检**（`$MustContainDataCount=24` / `$MaxFiles=2000` / `$MustContain` 的 17 项 / 「两份清单打架」那条 `throw`）被放宽或撤销时**没有任何守卫会红**（变异 P5/P6/P7/P8 全绿）。⚠️ **这不是假守卫**：`test_package.py` 自己有一份**字面量**的 `REQUIRED_ENTRIES` / `MAX_FILES=2000` / `>= 24`，两侧不同源（文件里逐字写了这条纪律）⇒ 真守卫在，只是脚本内那几份副本没人钉。⚠️ 其中 **P7 = 撤销 `8304175`**，而那一条路径今天**结构上不可达**（`$IncludeRoots ∩ $ExcludeDirNames = ∅`） |
| **S4-10** | **公网档 smoke 盲区**：711 是 Task 3 时点的值，此后 smoke +902 行、三个脚本大改 ⇒ 今天绿不绿无人知晓（且链接已死，今天跑不了）。处置见 §7.3 |
| **S4-11** | `tunnel.ps1:648/656` 与 S1-1 **同族**（`Start-Process -ArgumentList`），其中 `--logfile $LogFile` 在 `$env:TEMP` 下（`tunnel.ps1:246-247`）⇒ **用户名带空格**的机器上同样会被切开 |
| **S4-12** | `-Lan` + `PE_ENV=prod` 的**裁定是对的**（§3.4），而说明书 §2① 让甲方在终端 A 里设 `$env:PE_ENV='prod'`、§2② 的 `-Lan` 又没有任何一句「先确认 `PE_ENV` 没设成 prod」，而 `$env:` 在同一个终端里**会留下** ⇒ 一个照 §2① 再照 §2② 的人会起一个**登不进去**的服务（`serve.ps1` 会打一大段 ⚠️，故不是静默） |
| **S4-13** | `backend/pyproject.toml` 除 `alembic==1.20.0` 外**六项都没有上界**，也没有 lockfile ⇒ 甲方装到的是「打包那天之后 PyPI 上最新的那一套」（今天实测 fastapi 0.143.2 / starlette 1.8.0 / SQLAlchemy 2.1.4 / pydantic 2.14.1，与本仓的 0.141.1 / 1.7.0 / 2.1.3 / 2.13.5 不同）。⚠️ **今天实测无害**（openapi 逐字节相同 + 四条路线的后端面全通），而那不是一个可以依赖的性质 |
| **S4-14** | 说明书 §3 教师那一行用**引号**给了一句「当前身份不是本学期任教他的老师」，而 403 的**原文不是它**（实测原文：「学生 4 不在教师 'T0001' 于学期 2 任教的任何教学班里（或这个学生不存在）：判据是 `enrollment ⋈ course_section.teacher_id`…」）⇒ **意思对、引文不是逐字**；§8 末「把页面上那句**原文**发给我方」那一条依赖甲方抄原文，故引号里的东西最好逐字 |
| **S4-15** | `smoke.mjs:496-498` 的 `toPlainText` **不反转义 HTML 实体**（Task 5b 的顶回①为真），⚠️ 而**今天没有让任何一条拍永绿**：反向断言里 needle 含 `<`/`>`/`&` 的**只有 1 条**（`:5157` 的 `!…includes('<form')`，而 `<form` 是**标签**、`outerHTML` 不转义标签 ⇒ 判据有效），正向断言里含这三个字符的 **0 条**。它是一格**潜伏**风险（下一个人写一条含 `>` 的反向 needle 就会静默永绿）；最小处置是在 `toPlainText` 末尾补一步实体反转义（`&amp;` 最后替换）+ 一条反空转守卫 |
| **S4-16** | `package.ps1` 会在 `$env:TEMP` 里留 staging 残渣：本席 8 次跑动留了 **3** 个 `pe_package_*`（各剩 2–4 个文件、约 145 KB，剩的**都是 `scripts\*.ps1`**），而 **03:38:47 那一份在本席开工之前就在** ⇒ 与本波变异无关。⚠️ 它**不是静默**的（`package.ps1:616-617` 会打印「⚠️ staging 删不掉…请手工删」），而 `8304175` 修的是「两份清单打架」那两条 `throw` 路径 ⇒ 这是**另一条**路径 |

### 8.6 ⚠️ 本席这一席的置信度与**没查透**的面（如实报）

**查透了（有运行时取证）：**

* **F3 交付可用性** —— 本席认为这是本次最扎实的一面：`pip install` 两遍（干净路径 + 含空格与中文）
  都是**真装**（不是 `--dry-run`）；一条命令起服务在 **PATH 无 node** 的子进程里真起来并
  **16 条路由逐条 200**；包内容 339 个条目逐个扫过（该有的 / 不该有的 / 最长路径 / BOM / CRLF）；
  包里 15 个关键文件与仓库 HEAD **逐字节比过**；含空格路径那一格**抓到了 S1-1 并做了最小复现**。
* **F2 试用档安全** —— **39 格两档逐字对比**（同库内容、同请求序列），差异 2 格且都可解释 ⇒
  「试用档放宽了 0 格权限」这一句是**实测**的，不是推断。`-Lan` 四格从**真的局域网地址**
  `192.168.31.11:8043` 上发过请求，防火墙**没被改**（`show rule` 实测查不到），
  cookie 属性用**原始 `Set-Cookie`** 核过两档（dev 无 `Secure` / prod 有）。
  登录锁定做了**运行时取证**（5 发坏口令 + 第 6 发的时序 + 正确口令也被拒）。
* **F4 说明书真话率（数字面）** —— **33 条断言逐条实发**，26 个业务数字**逐个对上**
  （含 `4C51674D` / `D2476ADA` / `98.33` / `6.37` / `+0.10` / `62.7%` / `15 人` / `11/11` 这一类），
  四条路线**实走**（写入那两步是真写的，写在**本席自己的库副本**上）。
* **F1 守卫强度** —— **23 条定点变异**，每条都有 pytest 的实测结果，**23 条全部逐字节还原**
  且收尾 `git status --porcelain` 为空；自指守卫**逐个抽验了 6 处**，都是两侧不同源。
* **F7 数字与台账** —— **31 条**断言 + §15 那 24 条里抽了 **6 条反查**；
  「甲方在用的 dist 是哪个 commit」用**三格交叉**定案（时刻 / 产物内容 / 包↔仓库逐字节）。

**没查透（如实报，不装作查全了）：**

1. ⚠️ **一次浏览器都没开**。⇒ 四格后果：
   ①「16 条路由**渲染后**逐条有/无告示」（0/16 与 16/16 两档）本席**只做了结构与两端取证**
   （后端 `trial` 两档 + `v-if="trial"` + 缺省 `false` + `catch` 也置 `false` + 告示四段文字
   在发给甲方的 chunk 里），**没有 DOM 实测**；
   ② 打卡表单四格里「**用户看得见**」那一半，本席证的是「后端真回了 409/201/422 + 渲染它的
   template 正文与 `useFormValidity` 的措辞逐字在那儿」，**没有点过那个按钮**；
   ③ `durationText` 的 `TypeError` 那一格本席**没有复现**（只核了修法的形状与同族）；
   ④ 大屏的自动轮播 / 「减少动态效果」那一档**完全没碰**。
2. ⚠️ **一次 `smoke.mjs` 都没跑**（四档都没跑）。⇒ 自报的 **739 / 739 / 771 / 711** 四个断言数
   **一个都没复现**；`check:tokens` **36**/下界 25 与 `check:dist` **25 产物 / 787 824 字符**
   （以及 `--no-build` 口径 **589 118 B**）**都没复现**。理由：跑 smoke 会写脏它所指向的库，
   而本席的 A 实例是 F4 只读核验的检材；公网档更是要打甲方的库（派单禁止）。
3. ⚠️ **一次 `npm run build` 都没跑**（派单禁止）。⇒ §7.4 的结论是「三格交叉」而**不是**
   「重建会得到同一份产物」。
4. ⚠️ **一次 `tunnel.ps1` 都没跑**（派单禁止：它会覆盖 `.trial\public-url.txt`）。
   ⇒ F5 四格全部是「读代码 + 定点变异打红**可执行**守卫 + 磁盘实物」，**没有**端到端起过一条隧道；
   530 那一格本席**没有**自己起假端点复现（变异 U2 打红的那条守卫本身就是「起一个本地假 530
   端点」的可执行判据，故等价证据在，而本席没有独立复现）；
   `-Backend ssh` 那一支**完全没验**（与 §15 G1 一致）。
5. ⚠️ **后端 1623 条测试一次都没跑全**（只跑了 Plan 07 那 6 个文件的 **121** 条 + 变异期间
   反复跑它们）。⇒ **1623 / 1622+1 skipped** 与覆盖率三口径四格**一个都没复现**；
   `Cover` 列的口径裁定（spec §12）本席**没有复核**。
6. ⚠️ **`PE_TRIAL` 的 14 个坏值只做了变异取证**（D1 打红 ⇒ 「`true`/`yes`/`on` 一律 raise」有牙），
   **没有逐个起服务实测**；「请求期是 422 还是 500」本席**未能核验**。
7. ⚠️ **说明书 §8③ 那个「11–13 秒」没验**（要对公网链接反复计时；本席只打了**一发**，
   且收尾时链接已死）。
8. ⚠️ **`git diff` 的 38 个文件里没有逐行读完的**：`smoke.mjs`（+902 行）、`test_serve.py`
   （+459）、`test_tunnel.py`（+1050）、`test_trial.py`（+587）、`test_package.py`（+487）、
   `tunnel.ps1`（+1012）、`package.ps1`（+624）本席都是**定点读 + Grep**，不是通读。
9. ⚠️ **`.gitignore` 那 51 行没逐行数**（§7.1 #16 判「未能核验」）。
10. ⚠️ **`cloudflared` 的官方 checksum 没有独立复验**（Task 3 做过，spec §13.17.2 记着；
    本席只量了本机那一份的字节数 55 365 048 B）。

**总体置信度自评**：**F3 / F2 / F4（数字面）/ F1 / F7 高**（都有本席自己跑的运行时取证，
且 S1-1 有最小复现、S1-2 有产物内命中 + 锁定时序、S2-1 有写入前后的库对账、
S2-2 有 DNS 与出网的对照实验）；**F5 中**（守卫是可执行的、且被变异打红，但本席没端到端跑过隧道）；
**F6 的 UI 半边中偏低**（后端面全实测，前端面是源码 + 产物取证，没有 DOM）。
⚠️ 本席**查出 2 条 S1**，而派单提醒过「0 条 S1 是完全可能的结果」—— 本席逐条给了
运行时取证与定级理由，其中 **S1-2 的定级依据是「文档让甲方做错事」+ Plan 06 终审把同族
（「与鉴权实物相反的页面散文」）定为 Critical 的同一条口径**；⚠️ 如实说明：它**不是**安全漏洞
（锁定确实在、且是更严的那一侧），若控制者认为应按「文案撒谎」归 S3，本席**不争**，
但它**必须修**、且要**重建 dist**（甲方此刻正在收的那一份里就有它）。

---

## 附 · 本席的探针清单（跑完已随 `$env:TEMP\p07t6` 删净）

`probe_zip.py`（zip 条目面）· `probe_unpack.py`（解包 + 包↔仓库逐字节）·
`probe_openapi.py`（两环境的 openapi 对账）· `probe_paths.py`（102 个操作的路径面）·
`probe_routes.py`（16 条路由 + 4 条非页面 + 4 个文档端点）· `probe_copydb.py`（库副本 + 事实面）·
`probe_authmatrix.py`（39 格两档鉴权矩阵）· `probe_f2b.py`（audit 差异定位 / 学生读 alerts /
教师 403 原文 / T0001 可读 41 人 / **登录锁定取证**）· `probe_guide_student.py` +
`probe_guide_stu2.py` + `probe_guide_staff.py` + `probe_board.py`（说明书四条路线的数字）·
`probe_writes.py`（打卡四格 + 第一次 handle）· `probe_handle.py` + `probe_handle2.py`
（`as_of` 走 query 之后的 handle + `weekly_adjustment` 对账）· `probe_alerts2.py`
（9 条红色预警逐个查 auto 调整）· `probe_forms.py`（全仓 `<form>` 与原生约束扫描）·
`probe_smoke_needles.py`（`toPlainText` 与正/反向 needle 扫描）· `probe_mutate.py`（23 条定点变异驱动器）·
`probe_prose.py` + `probe_prose2.py`（19 处抽验 + 第 20 处搜寻）· `probe_minitest.py`
（`/api/mini-tests` 匿名与否）· `probe_ledger.py`（§15 台账 24/7）。

日志：`pipinstall-plain.log` · `pipinstall-cn.log` · `trial-8041.log` · `trial-8045.log` ·
`serve-8043-lan.log` · `serve-8044-lanprod.log` · `mutate.log` · `f2b.log` ·
`guide_student.log` · `guide_stu2.log` · `guide_staff.log` · `writes.log` · `handle.log` ·
`handle2.log` · `prose.log` · `prose2.log` · `ledger.log` · `openapi-repoenv.json` ·
`openapi-venv.json`（两档逐字节相同的实证）。

⚠️ 关键原文一律**抄进了本报告**（S1-1 的 uvicorn 报错与最小复现、S1-2 的锁定时序、
S2-1 的 `adjustment: null` 与 13 行对账、S2-2 的 NXDOMAIN），故探针删净之后本报告**自足**；
要重跑任何一格，照 §8.6 与上面这份清单里的名字重建即可。
