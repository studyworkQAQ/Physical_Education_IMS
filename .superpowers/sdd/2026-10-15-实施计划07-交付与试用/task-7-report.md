# 实施计划 07 · Task 7 —— 终审修复波（S1 × 2 + S2 × 2 + S3 × 7 = 11 条，逐条改前/改后取证）

> 口径与同目录既有六份逐字相同：**甲方此刻正拿着一条公网链接在试用**。
> 本波一次都没碰那条链接的服务与库：自己起的实例一律在 **8040+ / 8000 / 8020** 端口、
> 用自己在 `%TEMP%\p07t7\` 下灌的库；对那条公网 URL **只发匿名 GET**。
> ⚠️ `npm run build` 跑了（S1-2 与 S3-1 必须重建产物，控制者已授权），
> 重建之后**匿名复核过**那条活链接仍在服务、且服务的正是新哈希（见 §1 收尾五格第 ⑤ 格）。
> ⚠️ S4 那 16 条与结案留下一波（Task 8）；本波顺手做了 **S4-6**（过期的 openapi 计数，
> 因为它随包交付）与 **S4-11**（`tunnel.ps1` 的 `Start-Process` 同族，因为与 S1-1 同一段修法）。
> ⚠️ 本报告**刻意不印自己的字节数与 sha**（不动点问题）。

---

## ① 环境 · 开工五格 · 收尾五格 · 我起过哪些进程

### 1.1 环境（开工第一件事，硬规矩 #73）

```
node --version   → v24.19.0
python --version → Python 3.11.1        （⚠️ 无 venv，一律系统 Python）
npm --version    → 11.17.0
git --version    → git version 2.55.0.windows.5
分支             → p07/review-fixes（从 main 起，HEAD = a45a3f0）
```

### 1.2 开工五格（2026-10-16 10:29–10:33 量）

| # | 格 | 实测量 | 与派单一致？ |
|---|---|---|---|
| ① | 试用档服务 | `python` **PID 45156** 在 `127.0.0.1:8030` 上 listen（`Get-NetTCPConnection` 的 `OwningProcess` = 45156） | ✅ |
| ② | 公网隧道 | `cloudflared` **PID 37196** + 外层 wrapper `powershell` **PID 48932**，两者都在 | ✅ |
| ③ | `backend/pe_trial.db` | **1 589 248 B / sha256[:16] `40D7B5F78A7C36CB`** | ✅ 逐字相同 |
| ④ | `frontend/dist` | **29 个文件 / 687 224 B**；五个发给甲方的哈希逐个对上：`index-DrDy4l90.css`(`82F1894CCB69C169`) · `index-DYNl778Q.js`(`364F903607EDCDAB`) · `StudentDetail-Bw86stl2.js`(`F07F8F27D9C54568`) · `AuditLogList-CqjFciNR.js`(`7C3EBE46550A4B48`) · `ResourceIndex-DqalY3wm.js`(`588A301421A96F2F`) | ✅ |
| ⑤ | 公网 URL 匿名 health | `GET https://related-llp-briefing-holds.trycloudflare.com/api/health` → **200 / 54 B** `{"status":"ok","tables":28,"students":60,"trial":true}` | ✅ |

**终审报告入库前的四数复核**（派单 §0 要求，⚠️ 一个字都没改）：

| 格 | 派单给的 | 本波实测 | |
|---|---|---|---|
| 字节数 | 118 408 B | **118 408 B** | ✅ |
| 行数 / 行尾 | 1084 行 / 纯 LF | LF **1084** / CRLF **0** / 裸 LF **1084** | ✅ |
| BOM | 无 | **无** | ✅ |
| sha256[:16] | `7DA1D7FF84272B6D` | **`7DA1D7FF84272B6D`** | ✅ |

入库后 `git cat-file -s HEAD:<该文件>` = **118 408**（= 工作树字节）、
`git ls-files --eol` = `i/lf w/lf attr/-text` ⇒ **工作树字节 == 入库 blob**。

### 1.3 收尾五格（2026-10-16 12:26 量）

| # | 格 | 实测量 | |
|---|---|---|---|
| ① | 8030 | `Get-Process -Id 45156` → **python 仍在**；8030 的 listener `OwningProcess` 仍是 **45156** | ✅ **没被杀、没被重启** |
| ② | 隧道 | **PID 37196（cloudflared）与 48932（wrapper）都仍在** | ✅ |
| ③ | `pe_trial.db` | **1 589 248 B / `40D7B5F78A7C36CB`** | ✅ **逐字未变**（本波一次都没写它、也没跑 `-Reset`） |
| ④ | `frontend/dist` | **29 个文件 / 687 804 B**；哈希已换（新旧对照见 §3.3） | ✅ 按授权重建 |
| ⑤ | 公网 URL | `/api/health` → **200** `{"status":"ok","tables":28,"students":60,"trial":true}`；`/login` → **200 / 2 729 B** 且引用的是 **`assets/index-Bb2uTFzm.js` + `assets/index-D22u2MPR.css`**（= 本波重建的新哈希） | ✅ **仍在服务、且服务的是新版** |

### 1.4 本波起过哪些进程（**全部已停并复验**）

| 实例 | 端口 | 库 | 干什么用 | 收尾 |
|---|---|---|---|---|
| A | 8041 | `%TEMP%\p07t7\体育系统 试用\backend\pe_trial.db`（旧包解到**含空格与中文**的目录） | **S1-1 改前复现**（真跑） | 已停（它自己 `throw` 退出码 1） |
| B | 8042 | `%TEMP%\p07t7\old\backend\pe_lock.db` | S1-2 的**锁定运行时取证** + S2-1 的真走一遍 + S3-1 的四档实测 | 已停 |
| C | 8000 | `backend/pe_demo.db`（`demo.ps1` 自己删旧库重灌） | smoke **dev 档** | 已停 |
| D | 8020 | `%TEMP%\p07t7\smoke\prod.db` | smoke **产品档** | 已停 |
| E | 8043 | `%TEMP%\p07t7\smoke\trial.db`（`PE_TRIAL=1`） | smoke **试用档** | 已停 |
| F | 8044 | `%TEMP%\p07t7\体育系统 试用\backend\pe_trial.db`（**新包**解到含空格与中文的目录） | **S1-1 改后端到端** + P8②⑤ | 已停 |

收尾复核：`Get-NetTCPConnection -LocalPort 8000,8020,8041,8042,8043,8044 -State Listen` → **0 个 listener**。
⚠️ **`backend/pe_demo.db` 已按开工量到的字节还原**（1 597 440 B / `5F289B248CBD507A`；
smoke 会写脏它，故本波开工先备份、收尾逐字节还原）。
⚠️ **5173 那个 vite 不是本波起的**（实测 PID 43520、`StartTime 2026-10-16 09:26:55`，
早于本波开工；派单说它「已经不见了」，而它**在**）⇒ **本波没杀它**，
dev 档 smoke 直接复用了它（先核过它服务的正是本波改后的源：
`GET http://localhost:5173/src/views/auth/Login.vue` 的正文里搜得到「连错多次会被临时锁定」）。
⚠️ 一次都没跑 `tunnel.ps1`（它会覆盖 `.trial\public-url.txt` 并多开一条公网入口）。

---

## ② P1 = S1-1（Critical）· 解包到含空格的路径时服务起不来

### 2.1 改前复现取证（**本波自己跑的，不采信终审**）

做法：把**今天在发给甲方的那个包**（`pe-ims-trial-20261016-032033.zip`）解到
`%TEMP%\p07t7\体育系统 试用\`（= 派单点名的那个形状：含空格 **且** 含中文），
复制一个已灌好的库进去（⚠️ 按派单裁定**不灌库**），跑
`serve.ps1 -Port 8041 -SkipBuild`（`PE_DB_URL` 指到那个含空格的库、`PE_TRIAL=1`）。

结果：**退出码 1**。日志原文（`%TEMP%\p07t7\before_serve.log`，3 351 B）：

```
   uvicorn         serve_app:app --app-dir backend\scripts --host 127.0.0.1 --port 8041
   进程 PID = 20472
-- ④ 健康检查 --
Usage: python -m uvicorn [OPTIONS] APP
Try 'python -m uvicorn --help' for help.

Error: Got unexpected extra argument (试用\backend\scripts)
uvicorn 在健康检查通过之前就退出了（PID 20472，退出码 ，轮询了 1 次）：上面那段日志就是原因。…
At C:\Users\whwenhao\AppData\Local\Temp\p07t7\体育系统 试用\scripts\serve.ps1:474 char:13
```

⇒ 与终审 §4.3 的取证**逐字同形**（连 `serve.ps1:474` 那一句 `throw` 的原文都一样）。
⚠️ 同一次实验里 `pip install` 那一步没跑（本机依赖已装），而**灌库那一步本波单独核过**：
`demo_bootstrap.py --db-url sqlite:///C:/…/p07t7/old/backend/pe_trial.db --csv-dir …`
退出码 **0**、`[1/7]…[7/7]` 全跑完、库 **1 589 248 B**（与控制者那份逐字节同长）
⇒ **「灌库通、只坏在起服务」这一格成立**。

### 2.2 修法与理由（⚠️ 派单给了两档，本波选「给那个元素自带引号」）

**选它、不选 `& $PythonExe @Arguments` 的逐字理由**：`&` 会**阻塞**到子进程退出，
于是 ④ 那一圈「一边轮询 `/api/health`、一边看 `$Proc.HasExited`」就没了
（它要的正是「服务起着的同时脚本继续往下走」）；而 `$Proc.Id`（⑤ 要打印 PID）与
`finally` 里那次 `Stop-Process`（Ctrl-C / `throw` 都要兜住子进程，不留占着端口的孤儿）
也都要那个 `Process` 对象。⇒ **保住 `Start-Process` 的形状**，只把命令行**自己拼对**：

```powershell
function Format-NativeArgumentList {
    param([Parameter(Mandatory = $true)][string[]]$Elements)
    $Quoted = foreach ($Element in $Elements) {
        if ($Element -notmatch '[\s"]') { $Element; continue }
        # MSVCRT 的 argv 规则：\" 才是一个字面的引号，而紧贴引号之前的反斜杠要成对翻倍
        $Escaped = $Element -replace '(\\*)"', '$1$1\"'
        $Escaped = $Escaped -replace '(\\+)$', '$1$1'
        '"' + $Escaped + '"'
    }
    return ($Quoted -join ' ')
}
…
$ArgumentText = Format-NativeArgumentList -Elements $Arguments
$Proc = Start-Process -FilePath $PythonExe -ArgumentList $ArgumentText -WorkingDirectory $Backend -PassThru -NoNewWindow
```

⚠️ `-ArgumentList` 从**数组**换成**一个字符串**是承重的：数组那一档 `Start-Process`
自己用空格连接、一个引号都不加（就是病灶）；字符串那一档它**原样**交给 `CreateProcess`。
⚠️ 既有的两条守卫一个字都没被踩坏：`code.count("& $PythonExe") == 4`、
`code.count("-FilePath $PythonExe") == 1`、`code.count('"-m"') == 1`、
`code.index("Start-Process -FilePath $PythonExe")` 全都仍然成立。

### 2.3 ⚠️ 全仓 `Start-Process -ArgumentList` 同族清单（派单 P1② 要求的逐个判）

`Grep 'Start-Process'` 全仓 `**/*.ps1` → **一共 2 处调用点**（另 2 处命中是注释）：

| # | 住址 | 含空格的元素 | 会不会被打断 | 处置 |
|---|---|---|---|---|
| 1 | `scripts/serve.ps1:449`（改后 :483） | `--app-dir` = `<仓库根>\backend\scripts` | **会** | **本条已修** |
| 2 | `scripts/tunnel.ps1:656`（改后 :697，`Start-Process @StartArguments`） | `--logfile` / `-E` 的值 = `$env:TEMP\pe_tunnel_<Port>\…`，而 **Windows 的用户名可以带空格** | **会**（终审 S4-11） | **同批已修**：就地修在 `Resolve-TunnelBackend` 里（`$QuotedLogFile` / `$QuotedSshDebugFile`） |

⚠️ 派单点名的另外六个脚本**逐个判过、都不会**被空格打断：

| 脚本 | 它怎么起子进程 | 判定 |
|---|---|---|
| `scripts/trial.ps1` | `& powershell @ServeArguments`（**调用运算符 + splatting**） | ✅ PowerShell 自己给含空格的元素加引号（终审 §4.3 也实测这一步在含空格路径上**通**） |
| `scripts/package.ps1` | **一个子进程都不起**（走 .NET 的 `ZipArchive.CreateEntry`） | ✅ 不适用 |
| `backend/scripts/demo.ps1` | `python scripts/demo_bootstrap.py --db-url $DbUrl --csv-dir $CsvDir …`、`python -m uvicorn …`（**原生命令直调**） | ✅ 同上 |
| `backend/scripts/backup.ps1` | `python @Arguments`（**splatting 到原生命令**） | ✅ 同上 |
| `backend/scripts/restore.ps1` | `python @Arguments` | ✅ 同上 |
| `scripts/tunnel.ps1:441` | `& $Exe @NativeArguments`（调用运算符 + splatting，只用于 `--version` 一类探测） | ✅ 同上 |

⇒ **同族一共 2 处，2 处都修了；其余 6 个脚本 0 处需要修。**
⚠️ 而这一格留下了一个**真实的债**并登记进 §15 台账 **G4**：那条引号规则今天有
**两个所有者**（`serve.ps1` 的一个函数 + `tunnel.ps1` 里内联的两段）。
⚠️ **刻意如此**：`Resolve-TunnelBackend` 被 `test_tunnel.py` **整段切出来在干净
PowerShell 里真跑**，住在函数外面的共享 helper 切不到（那一拍会红在「找不到命令」上、
离真因有一层）；而本仓四个 `.ps1` 之间**没有** include 机制。

### 2.4 守卫的形状与取舍（⚠️ 派单 P1③ 给了两档，本波选「断言命令行」）

**选「断言拼出来的命令行逐字正确」，不选「在守卫里真跑一次起服务」，逐字取舍**：
真跑一次要复制一个 1.5 MB 的库、绑一个端口、等 uvicorn 起来（本机实测 6–10 秒），
于是这一格会把「一套 **205 秒**跑完、**一个端口都不绑**的单元套件」变成
「要抢端口、会被防火墙与杀软干扰的集成测试」；而失效形态（元素没被加引号）
在**拼出来的那个字符串**上已经完全可见。

**守卫**（`backend/tests/test_serve.py`，新增
`test_the_uvicorn_command_line_survives_a_path_with_spaces_and_cjk_characters`，五拍）：
把 `Format-NativeArgumentList` **切出来在干净 PowerShell 里真跑**
（姿势与 `test_tunnel.py` 那条 `-Protocol` 三档的守卫逐字相同），
① 含空格**与中文**的路径 → 命令行**逐字节**等于期望值；② 不含空格的元素**一个引号都不加**
（否则 `-m` 会变成 `"-m"`，撞本文件既有的 `code.count('"-m"') == 1` 那一拍）；
③ 既含空格又以反斜杠结尾 → 收尾反斜杠**翻倍**、且一个字面的引号转义成 `\"`；
④ `-ArgumentList` 拿到的确实是 `$ArgumentText` 而**不是** `$Arguments`；
⑤ **反空转**：把函数换成「原样 `-join ' '`」（= 改前 `Start-Process` 自己的行为）→ ①当场对不上。
⚠️ 另加 `test_the_two_logfile_arguments_survive_a_temp_path_with_spaces`（三拍 + 反空转）钉住同族第 2 处。
⚠️ 两条都在 snippet 开头设 `[Console]::OutputEncoding = UTF8`：否则 PowerShell 5.1 按
OEM 代码页（本机 936）写 stdout，含中文的期望值会**红在编码上**、离真因有一层。

**⚠️ 派单要求「若选断言命令行，必须再补一条真跑的取证」—— 已补，见下面 2.5。**

### 2.5 含空格路径的**端到端**取证：改前红 → 改后绿

| 档 | 目录 | 包 | 命令 | 结果 |
|---|---|---|---|---|
| **改前** | `%TEMP%\p07t7\体育系统 试用\` | 旧包 `…032033.zip` | `serve.ps1 -Port 8041 -SkipBuild` | ❌ **退出码 1**，`Error: Got unexpected extra argument (试用\backend\scripts)`（§2.1） |
| **改后** | `%TEMP%\p07t7\体育系统 试用\`（删掉重解） | **新包** `…115923.zip` | `serve.ps1 -Port 8044 -SkipBuild` | ✅ **起来了**（PID 13252，健康检查**轮询 1 次**就 200） |

改后那一次的现场证据（`serve.ps1` 自己印的）：

```
PE_DB_URL       = sqlite:///C:/Users/whwenhao/AppData/Local/Temp/p07t7/体育系统 试用/backend/pe_trial.db
uvicorn         serve_app:app --app-dir backend\scripts --host 127.0.0.1 --port 8044
进程 PID = 13252
http://127.0.0.1:8044/api/health → 200（轮询 1 次）
```

⚠️ 那一格 `PE_DB_URL` 里**也有空格**，它照常работал（原生直调那一档 PowerShell 自己加引号）。

### 2.6 定点变异

| 变异 | 结果 |
|---|---|
| `serve.ps1`：`-ArgumentList $ArgumentText` → `-ArgumentList $Arguments`（= 改前） | ❌ **红**：「起 uvicorn 那一句没有改用拼好的字符串：数组那一档不给含空格的元素加引号」 |
| `tunnel.ps1`：`'--logfile', $QuotedLogFile` → `'--logfile', $LogFile` | ❌ **红**：`test_the_orphan_cleanup_only_kills_processes_that_carry_this_scripts_own_marker` |

两次还原后**逐字节相同**（`serve.ps1` sha256[:16] `93E7F727F6746613`）。

### 2.7 README 与说明书 §2③ 的那一句（⚠️ 修好之后**仍然要**）

按派单裁定加了，措辞逐字是「**建议**解包到一个不含空格的目录（例如 `D:\pe-ims\`，
而不是 `D:\体育系统 试用\`）：本版本已经能在含空格的路径下起服务，而那条路径上
要经过的第三方工具（压缩软件、Python 的包管理、机房里的安全软件）未必都能」。
⚠️ 两处措辞刻意**不完全相同**（README 面向 IT、说明书面向甲方），而**判据是同一条**：
「建议」而不是「必须」，且逐字承认本版本已能在含空格路径下起服务。

---

## ③ P2 = S1-2（Critical）· 五处「不做登录失败锁定」

### 3.1 锁定行为的**运行时复现**（改前取证；本波自己在 8042 上真发，一次都没碰 8030）

同一个学号 `2023120001`，`POST /api/auth/login`：

| 发 | 口令 | 状态 | 耗时 | 体 | sha256[:16] |
|---|---|---|---|---|---|
| 1 | 坏 | 401 | **0.083 s** | 82 B | `D6CA996C91CFADAA` |
| 2 | 坏 | 401 | 0.048 s | 82 B | `D6CA996C91CFADAA` |
| 3 | 坏 | 401 | 0.050 s | 82 B | `D6CA996C91CFADAA` |
| 4 | 坏 | 401 | 0.050 s | 82 B | `D6CA996C91CFADAA` |
| 5 | 坏 | 401 | 0.061 s | 82 B | `D6CA996C91CFADAA` |
| **6** | 坏 | 401 | **0.017 s** ← 锁定档**一次 PBKDF2 都不跑**的签名 | 82 B | `D6CA996C91CFADAA` |
| **7** | **正确口令 `pe-demo-2025`** | **401** | 0.038 s | **82 B** | **`D6CA996C91CFADAA`** ← **与「口令错」逐字节相同** |
| 8 | 坏 | 401 | 0.029 s | 82 B | — ← 重输**不会**把锁推后 |

⇒ **锁定真的在**，而五处散文说它不在；且与同批交付的说明书 §6⑤（「连错 **5** 次会被锁
**15** 分钟」）**正好相反**。响应体逐字是
`{"error":{"code":"invalid_credentials","message":"口令不正确","detail":null}}`。

### 3.2 五处改前 / 改后原文

| # | 住址 | 改前（逐字） | 改后（逐字） |
|---|---|---|---|
| 1 | `views/auth/Login.vue`（**登录页正文** = 甲方落地的第一页） | `本系统<strong>不做</strong>口令找回 / 登录失败锁定 / 图形验证码 / OAuth。忘了口令要找教务干事把 password_hash 置回 NULL（逐字局限见 spec §1.2 与 §13）。` | `本系统<strong>不做</strong>口令找回 / 图形验证码 / OAuth。忘了口令要找教务干事把 password_hash 置回 NULL（逐字局限见 spec §1.2 与 §13）。⚠️ 口令<strong>连错多次会被临时锁定</strong>，稍后再试即可；被锁时看到的仍然是「口令不正确」（阈值与逐字口径见 spec §13.4.6）。` |
| 2 | `App.vue`（**16 条路由的页脚**，覆盖面最大的一处） | `⚠️ 不做口令找回 / 登录失败锁定 / CSRF 双重提交令牌（逐字局限见 spec §1.2 与 §13）。` | `⚠️ 不做口令找回 / CSRF 双重提交令牌（逐字局限见 spec §1.2 与 §13）。` 换行接 `登录失败锁定<strong>已做</strong>：口令连错多次会被临时锁定，稍后再试（阈值与逐字口径见 spec §13.4.6）。` |
| 3 | `components/ApiErrorBanner.vue`（**401 的处置建议** = 被锁的人真会读到的那一句） | `口令不正确。⚠️ 本原型不做口令找回、也不做登录失败锁定；忘了口令要找教务干事把那一列置回 NULL。` | `口令不正确。⚠️ 连错多次会被临时锁定，稍后再试（反复重输不会把锁推后）；本原型不做口令找回，忘了口令要找教务干事把那一列置回 NULL。` |
| 4 | `api/client.ts`（**代码注释** + hint） | `hint: '口令不正确。本原型不做登录失败锁定，也不做口令找回。'` | `hint: '口令不正确。连错多次会被临时锁定，稍后再试；本原型不做口令找回。'`，并在上面那段块注释里补上「**这一档同时就是锁定档**：后端回的是与『口令错』逐字节相同的 401，故前端**结构上分辨不出**」的逐字理由 |
| 5 | `api/auth.ts`（**代码注释** + `authAdvice`） | `return '口令不正确。请重新输入（本原型不做登录失败锁定，也不做口令找回）。'` | `return '口令不正确。请重新输入（连错多次会被临时锁定，稍后再试；本原型不做口令找回）。'`，并补「改后不再叫人反复重输：重输解不开锁、也不会把锁推后」 |

⚠️ **口径按派单裁定执行、本波不顶回**：页面上**只说**「连错多次会被临时锁定，稍后再试」，
**不写具体数字**（三个阈值都是环境变量 `PE_LOGIN_MAX_FAILS` / `PE_LOGIN_WINDOW_MIN` /
`PE_LOGIN_LOCK_MIN`，唯一所有者是 `app/auth/policy.py`；写在页面上就是第二个所有者），
数字住在 **spec §13.4.6**。⚠️ 而**说明书 §6⑤ 保留了数字**（5 次 / 15 分钟 / 绑定侧 3 次 60 分钟）：
它本来就逐字声明了「本文是一份时点快照」，本波只给它补了一句
「这几个数都是服务端可配的，逐字口径与唯一所有者见 spec §13.4.6」+
「⚠️ 反复重输**不会**把锁推后」+ 一句交代**页面上为什么刻意不写数字**。
⚠️ 甲方需不需要在页面上看见数字：本波判断**不需要**（登录页那句已经告诉了他
「稍后再试」这个唯一正确的动作；而数字写上去就是一个会漂的第二个所有者）。

### 3.3 重建：`npm run build` 退出码 **0** / 141 modules / **29** 个产物 / **687 804 B**

**新旧哈希对照**（⚠️ 派单点名的五个 + 另外八个也换了）：

| 产物 | 改前 | 改后 | |
|---|---|---|---|
| `index-*.css` | `index-DrDy4l90.css` `82F1894CCB69C169` | **`index-D22u2MPR.css`** `729E4707DB46386A` | 换 |
| `index-*.js` | `index-DYNl778Q.js` `364F903607EDCDAB` | **`index-Bb2uTFzm.js`** `CB0DE5B563D64635` | 换 |
| `StudentDetail-*.js` | `StudentDetail-Bw86stl2.js` `F07F8F27D9C54568` | **`StudentDetail-h6aK5CtQ.js`** `812ADC29F97FD8EC` | 换 |
| `AuditLogList-*.js` | `AuditLogList-CqjFciNR.js` `7C3EBE46550A4B48` | **`AuditLogList-CeNceCxw.js`** `1E0555E7BBC20780` | 换 |
| `ResourceIndex-*.js` | `ResourceIndex-DqalY3wm.js` `588A301421A96F2F` | **`ResourceIndex-DqalY3wm.js`** `588A301421A96F2F` | ⚠️ **未变**（它不依赖被改的那几个模块） |

另外换了哈希的 8 个：`AlertQueue-DSyjjO54→CWAqRkoy` · `ClassReport-CvHc20C6→BVfjiYPU` ·
`Dashboard-BW1Md8vq→1t88iHx6` · `ResourceDetail-_NkQTBXW→Dfk8NjCn` ·
`ResourceList-CJBc19M7→CaU1n8Ww` · `TeacherNav-BLSivO07→CSFry9_K` ·
`contract-DR13tLzv→DdJhOU9y` · `index.html`（`691505145535C4AD`→`EC322B31AD0039FD`）。
**未变**的：`ProgressBoard-BGXMH9jO` · `SectionHead-DZfcemhW` · `resources-CuRO6meR` ·
7 个 `.css`（除 `index`）· 4 个 `.woff2` · 2 个 `.svg`。
（原因：它们都直接或间接 import `api/client.ts` / `App.vue`，那两处一改哈希就换。）

⚠️ **重建之后匿名复核那条活链接**（派单逐字要求）：
`GET https://related-llp-briefing-holds.trycloudflare.com/login` → **200 / 2 729 B**，
`index.html` 里引用的正是 **`assets/index-Bb2uTFzm.js` + `assets/index-D22u2MPR.css`**；
`/api/health` → **200**。⇒ **那条活链接自动切到了新版**，中间没有可观察到的中断。

### 3.4 ⚠️ 产物里旧串 **0 命中**的取证

用二进制安全的 Python 扫（不靠 PowerShell 的编码）：

| 目录 | `不做登录失败锁定` | `登录失败锁定` | `它走的是匿名` | `180 行全量` |
|---|---|---|---|---|
| **改前**的 `frontend/dist`（= 今天发给甲方的那一份） | **3** | **5** | **1** | **1** |
| **改前**的解包目录 `…\old\frontend\dist` | **3** | **5** | **1** | **1** |
| **改后**的 `frontend/dist` | **0** | **1**（= `App.vue` 改后那句真话「登录失败锁定**已做**」） | **0** | **0** |
| **改后**的新包解包目录（见 §7） | **0** | 同上 | **0** | **0** |

⇒ 五处旧串在产物里**0 命中**（`登录失败锁定` 还剩 1 次，是改后那句**真话**）。

### 3.5 新守卫（派单 P2④：源与产物两侧都要断言，⚠️ 产物侧要能在**没重建**时红）

`frontend/scripts/check-dist.mjs` 加了**第三组禁用串** `FORBIDDEN_STALE_CLAIM`（4 条正则），
**源与产物两侧都扫**，每条各带两拍自校（抓得到改前那句 / 放过改后那句）：

| # | 判据（正则） | 它钉的是哪一处 |
|---|---|---|
| 1 | `/不做[^。；\n]{0,24}登录失败锁定/` | `App.vue` · `ApiErrorBanner.vue` · `client.ts` · `auth.ts` |
| 2 | `/口令找回 \/ 登录失败锁定/` | `Login.vue`（它的 `不做` 被 `<strong>` 隔开，构建后是**两个字符串字面量**，第 1 条抓不到） |
| 3 | `/它走的是匿名/` | `MiniTest.vue`（S3-1） |
| 4 | `/180 行全量/` | `MiniTest.vue`（S3-1） |

⚠️ **产物那一侧才是这一格的牙，本波实测过它真的有牙**：改完源、**重建之前**跑一次
`check:dist --no-build` → **产物侧 4 条全红**（`assets\index-DYNl778Q.js ×5 / ×2 / ×1 / ×1`）、
源侧绿；重建之后**两侧全绿、退出码 0**。⇒ 「改了源、忘了重建」这一失效形态被抓到。

⚠️ 判据用**正则**而不是逐字串（那一族在五处长成五个形状），且字符类里**排掉 `。；\n`**：
改后的真话里「不做口令找回 …。」与「登录失败锁定**已做**」同在一个文本节点，
而**构建会把换行压成空格** ⇒ 不排掉句号就会**恒红**，而下一个人唯一的出路是把断言删掉
（硬规矩 #109）。
⚠️ **本波自己踩过一格并如实记**：取证注释起初写成 `//`，源侧当场红 2 处
（`api/auth.ts` 与 `components/ApiErrorBanner.vue`）—— `stripComments` 剥**块**注释而
**刻意不剥** `//`（`https://` 里就有一个 `//`），于是写在 `//` 里的一句**提及**被数成了**本身**。
处置是**把谓词做准的那一半（不剥 `//`）不动、把取证注释改成块注释**，
并在两处各写了一句「为什么这里必须用块注释」。
⚠️ 顺带把 `.vue` 加进了源码侧的扫描面（此前 `SRC_EXTENSIONS` 里**没有** `.vue`，
而这一族 6 处里有 3 处是 `.vue`；加进去之后 CDN 那一组仍然 0 命中、扫到 **56** 个文件）。

`npm run check:dist -- --no-build`：扫了 **25** 个产物文件（**575.9 kB**）、跳过 4 个非文本；
源码侧扫了 **56** 个文件；**退出码 0 / 0 条红**。
`npm run check:tokens`：**36** 个文件（下界 25）· **退出码 0**。

### 3.6 ⚠️ 同族自查清单（派单 P2⑤：找别的「不做 X」而 X 其实已经做了的句子）

`Grep '不做|不实现|没有做|不支持|刻意不|一律不|不提供'` 扫 `frontend/src/**` → **80 行命中**；
再逐个判「它说的是不是一件**已经做了**的事」。**挖出 2 处、2 处都修了**（都在后端）：

| # | 住址 | 改前（逐字） | 实物 | 处置 |
|---|---|---|---|---|
| 1 | `backend/app/auth/passwords.py:235-236` | `计划 §1 的非目标里逐字列了「图形验证码 / 登录失败锁定」，复杂度规则与它们是同一档（原型**不做防暴力破解**，故复杂度规则的收益为零…）` | 锁定**做了**（Plan 06 Task 3）⇒「原型不做防暴力破解」是假的 | ✅ **已修**：保留历史陈述 + 补一段「⚠️ 那一档的前提在 Plan 06 Task 3 之后**只对一半成立**」（锁定做了、图形验证码没做），并逐字交代**`MIN_PASSWORD_LENGTH = 8` 的裁定一个字都不变**（复杂度规则挡的是「离线拿到哈希之后爆破」，与锁定挡的「在线试口令」不是同一件事） |
| 2 | `backend/tests/api/test_crud.py:1997` | `而原型没有找回流程、**也没有登录失败锁定**，故泄漏是**不可撤销**的。` | 同上 | ✅ **已修**：删掉假的那半句 + 补「⚠️ 而**本条的结论一个字都不变**：口令哈希泄漏之后是**离线**爆破，锁定在那一档一次都不参与」 |

⚠️ **刻意不改的同族命中**（逐个判过，都不是假话）：

| 住址 | 那句 | 为什么不是假话 |
|---|---|---|
| `app/auth/passwords.py:322`（**运行时 422 的 message**） | `本原型不做复杂度规则、也不做找回` | **两句都真**（只判长度 8、不判复杂度；确实没有找回流程） |
| `frontend/src/views/auth/Bind.vue`（渲染正文 2 处） | `不做复杂度规则、不做找回` / `本原型不做找回` | 同上，**真** |
| `views/student/Home.vue:470`、`present.ts:317` | `原型不做真实推送，只有站内消息` | **真**（spec §8.3 逐字，`notification.channel` 实测只有 `in_app` 一个值） |
| `views/student/CheckIn.vue`（渲染正文 3 处） | `后端刻意不做「补卡覆盖旧行」` | **真**（实测同一天第二次打卡 → 409 `integrity_conflict`；说明书路线一第 5 步写的就是它） |
| `App.vue:62` · `router/index.ts:13,15` · `IdentitySwitcher.vue:8` · `stores/identity.ts:8` | 「Plan 04 那一版**逐字写着**『不做路由守卫跳转 / 不做真实登录鉴权』」 | 那是**准确的历史陈述**（引号里是旧文件的原文），不是当前断言 |
| `api/client.ts:203` · `api/endpoints.ts:1044` · `views/admin/ResourceList.vue:48-51` · `views/admin/AuditLogList.vue:44` · `views/student/Notifications.vue:154` · `composables/useFormValidity.ts:57,64` 等 | 各种「刻意不做 X」 | 逐个核过实物为真（不做过期 / 不做翻页收集 / 不做客户端过滤 / 不记请求体 / 不用 `alert()` …），**都是设计裁定而不是过期陈述** |
| `Document/2026-10-12-实施计划05A-…md:31` | 非目标清单里的「登录失败锁定」 | 那是一份**绑时点**的历史计划文档（与 Plan 06 的计划文档「一个字都不许改」同一条纪律） |
| `spec:4397`（§1.2 第 2 条） | `~~不做登录失败锁定 / 限速~~ → **已收**` | **已经是真话**（Plan 06 就划掉了）⇒ 假话只在**前端那五处**，spec 不欠账 |
| Plan 06 修过的那四处（管理台首页「读是匿名的」/ `Notifications.vue`「48 个匿名 GET」/ `endpoints.ts` 教师端降级 / `t-subhead__aside`「· 匿名」） | — | 本波**逐个复核过**：`Notifications.vue` 的渲染正文今天写的是「63 个 GET = 15 匿名 + 48 挂 security」，与 openapi 实测逐字相同（见 §5.2） |

⇒ **存量确实还有（2 处），本波全修了；修不了的 0 处。**

---

## ④ P3 + P4

### 4.1 P3 = S2-1 · 真走那一步的取证（**本波自己走的**，在 8042 上、用自己的库副本）

选了**另一条**红色预警走（避免与 §3.1 的锁定取证互相干扰）：`alert id 7` /
`student_id 11` / 学号 `2024060001` / 规则 `RED_RPE_SUSTAINED` / `prescription_id 11`。

| 步 | 实发 | 实测 |
|---|---|---|
| 点前 | `GET /api/alerts?limit=200&as_of=2025-10-12`（教师 T0001） | **21** 条 · level `red 9 / green 8 / yellow 4` · status `pending 20 / handled 1` |
| 点前 | `GET /api/weekly-adjustments?limit=200` | **9 行**，`sources = {'auto': 9}`、`factors = {0.8: 9}`，那 9 个 `prescription_id` 逐字是 **1 / 11 / 24 / 25 / 28 / 31 / 41 / 45 / 46** |
| 点前 | `GET /api/students/11/weekly-sheet?as_of=2025-10-12`（学生本人会话） | 200 · `{"week": 1, "factor": 0.8, "paused": false}` |
| **点** | `POST /api/alerts/7/handle?as_of=2025-10-12 {"action":"reduce_20pct"}` | **200** · 响应键 `['alert','action','adjustment','notification']` · **`adjustment` = `null`** · `notification` = `{id 21, recipient_kind student, recipient_id 1, …}` 标题「本周训练量已减 20%」 |
| 点后 | `GET /api/weekly-adjustments?limit=200` | **9 行**（一行都没多） |
| 点后 | `GET /api/students/11/weekly-sheet?as_of=2025-10-12` | 200 · `{"week": 1, "factor": **0.8**, "paused": false}` ← **系数没变** |
| 点后 | `GET /api/notifications`（学生本人） | **2** 条（`5 本周电子勋章` + **`21 本周训练量已减 20%`**）← 消息**真的推到了** |
| 点后 | `GET /api/alerts?limit=200` | status `pending **19** / handled **2**` ← 顶行**真的变了** |

推送正文（逐字，与说明书引文相同）：
`老师看过你的预警（RED_RPE_SUSTAINED）之后给本周减了量：本周训练单的系数是 0.80（= 骨架 × 本周全部微调的连乘，相当于减了 20%）。打开「本周训练单」看到的就是这个量。`

⇒ **「四格全对、而训练单那一半不变」成立**，且**不是第一条恰好不成立**：
那 9 行 `source='auto'` 的 0.8 调整**逐个**对着 T0001 那 9 条红色预警的学生
⇒ 「无 auto 调整的红色预警」= **0** 条，**结构性的**。

### 4.2 ⚠️ spec 里那一格核过了 —— **没有同族假话**

`spec §8.4`（周周微调）的勘误第 1 条逐字写着：「**`source = "auto"` 的写入方是
`app.pipeline.alert_stage._write_auto_adjustment`**：一条 `red` 预警落库的**同一批**里
就自动写一条 `factor = 0.8` / `reason = <规则 ID>` / `source = "auto"` 的调整，
**不等教师点击**」；而「去重的两道闸门」那一段逐字写着：
「⚠️ 而 ① 命中时**消息照发**：教师点了『减量 20%』，学生就该被告知『本周的量减了 20%』
—— **哪怕那一条调整是管道几天前就写好的**」。
⇒ **spec 从来没有承诺「点一次就一定再减 20%」**；假话**只在说明书**。
处置按派单：**只改说明书**（不动代码、不动 dist）。

### 4.3 P3 的改法（说明书路线二）

第 7 步保留真的那一半（「消息中心当场多一条、那条预警的状态与顶上的计数也当场变」），
**新增第 8 步**逐字交代：训练单系数**通常「本次未再减」**、那四个字**是页面自己会显示的、
不是坏了**、为什么（一处方一周至多一条 auto 调整，否则会是 `0.8 × 0.8 = 0.64` 的一次
没人知道发生了的连乘）、以及**演示库上每一条红色预警都是这个形状**（那 9 个学生都已经
有一条自动调整）⇒ 点哪一条都一样；要看「系数真的再变一次」请让我方换一份
没跑过自动管道的库。

### 4.4 P4 = S2-2 · 三处「一档 → 两档」的改前 / 改后

| # | 住址 | 改前（逐字） | 改后（要点） |
|---|---|---|---|
| 1 | 说明书 **§2①** | `进程一停，链接立刻失效（打开会看到 Cloudflare 自己的一页错误，写着 error code: 1033，⚠️ **不是**「连不上」）。失效就找我方重开…` | 「失效有**两种样子**：① 打开是 Cloudflare 自己的一页英文错误；② 浏览器直接说「找不到服务器」。⚠️ **两档都不会自己恢复**（我方那台机器上的脚本**刻意不自动重开** —— 自动重开会换掉你们手上那条链接），一律找我方重开」 |
| 2 | 说明书 **§8①** | `若打开看到的是 Cloudflare 的一页 error code: 1033，就是这一档（链接已失效，**不是**你们网络不通）。` | 「失效有**两种样子**：一页英文错误，**或**浏览器直接说「找不到服务器」—— **两档都是链接已失效、都不会自己恢复**」+ 补 P7③ 要的那一句 + 补「找我方之前先换一个网络 / 换一台机器打开**同一条**地址，排除你们自己这一侧」 |
| 3 | `tunnel.ps1` 写进 `.trial\public-url.txt` 的那一句 | `（实测变成 Cloudflare 自己的一页错误）；重跑 scripts\tunnel.ps1 会得到一个**全新的随机地址**。` | 「失效有**两种形状**：① Cloudflare 自己的一页英文错误（写着 `error code: 1033` = 边缘 HTTP `$EdgeDeadStatus`）；② 浏览器直接说「找不到服务器」（主机名已被边缘撤掉，DNS 解析不到）⇒ **两档都找我方重开**」+「⚠️ 它**不会自动恢复**」 |
| 4 | **spec §13.17.5** | `⚠️ 即它**不是**「连不上」——Cloudflare 的边缘**会答**` | 保留 ①（它是真的），**新增一格**把 ② 补上，含一张两档对照表（浏览器上看到什么 / 本机实测的判据：530 时 `Response` 是 `HttpWebResponse`，NXDOMAIN 时 `Response` 是 **`$null`**、`Status` = `ConnectFailure`），并逐字记「**代码本来就没问题**（④ b 与 ⑦ 两处都先判 `$null`），**欠的只是文档**」 |

⚠️ **给甲方的话一律说人话**：`530` / `NXDOMAIN` / `error code: 1033` 这些词
**一个都没进说明书**（技术细节留在 spec §13.17.5 与 `tunnel.ps1` 的注释里，
而写进 URL 文件的那一份因为是给运维读的，保留了 `error code: 1033` 与状态码变量）。

---

## ⑤ P5 = S3-1 · 第 20 处会随身份变假的散文

### 5.1 `MiniTest.vue` 改前 / 改后

**改前**（渲染正文，逐字）：

```
上面第 01 块的<strong>原始成绩</strong>不受影响：它走的是匿名
<code>GET /api/mini-tests</code>（180 行全量 + 客户端按 <code>student_id</code> 过滤），
与本块是两个独立的请求。
```

**本波实测四档**（在 8042 上，⚠️ 派单要求「自己实测今天的四档状态码与它返回多少行」）：

| 档 | 实发 `GET /api/mini-tests` | 状态 | 行数 / 体 |
|---|---|---|---|
| 匿名 | 同上 | **401 `unauthenticated`** | 249 B（「缺少身份：需要一个有效的 pe_session cookie…」） |
| 学生会话（`2025060001`） | 同上 | **200** | **3 行**（= 只有他自己那几行） |
| 教师会话（`T0001`） | 同上 | **200** | **123 行**（= 他任教的那几个班） |
| 管理员会话（`T0003`） | 同上 | **200** | **180 行**（才是全量） |

openapi 上它挂着 security：`[{"X-Student-Id": []}, {"X-Teacher-Staff-No": []}]`。
⇒ **两半都假**：它**要会话**（不是匿名），而且是**服务端按身份筛**（不是「全量拉下来客户端筛」）。

**改后**（渲染正文，逐字）：

```
上面第 01 块的<strong>原始成绩</strong>不受影响：它走的是
<code>GET /api/mini-tests</code>（⚠️ <strong>要会话</strong>：匿名打过去是
<code>401</code>；而且<strong>服务端按身份筛</strong> —— 学生只拿到自己
那几行，教师拿到自己任教班的，管理员才是全量），与本块是两个独立的请求。
```

⚠️ 上面留了一段 **HTML 注释**逐字记下改前那句与四档实测（那是这一格的取证住址），
并点名它与 spec §13.18.5 的 #4/#5/#12 **同族同形**、而 `MiniTest.vue` **不在 Plan 07 的 diff 里**
⇒ Task 5b 的自查整个漏掉了它。⚠️ 与 S1-2 **同一次**重建 dist。

### 5.2 ⚠️ 全仓「渲染正文里的断言句」完整清单（派单 P5③ 要求的判据）

做法：Python 脚本扫 `frontend/src/**/*.vue`，**只取顶层 `<template>` 段**、
**剥掉 HTML 注释**，然后按行找含断言词（`匿名 / 不需要身份 / 全量 / 一律 / 都 / 恒 /
永远 / 不做 / 不写 / 任何`）的中文行。
⇒ **候选 109 行**，其中**含强断言词（匿名 / 全量 / 一律 / 不需要身份）的 28 行**。
逐个核实物的结论：**只有 1 行是假的**。

| 住址（行号是 `Grep` 的真行号） | 那句断言 | 实物（本波实测） | 判定 |
|---|---|---|---|
| `views/student/MiniTest.vue:407-408` | 「走的是**匿名** `GET /api/mini-tests`（180 行全量 + 客户端按 `student_id` 过滤）」 | 匿名 **401**；学生 **3 行** / 教师 **123** / 管理员 **180** | ❌ **假** → **已修** |
| `views/admin/ResourceIndex.vue:143,146,147` | 「{{ total }} 个资源里匿名可读的只有那 {{ ANONYMOUS_READABLE }} 个」「其余一律要 `pe_session`」「匿名打过去是 401」 | 常量实测 `ANONYMOUS_READABLE = 7`；openapi 实测匿名 GET **15** 个，逐个都是参考数据/群体统计 | ✅ 真（`computed`，不是写死） |
| `views/admin/ResourceIndex.vue:154-156` | 「后端 openapi 上匿名 GET 一共 {{ ANONYMOUS_GETS }} 个 …；另有 **3** 个匿名 POST = 登录与两个绑定」 | `ANONYMOUS_GETS = 15`；实测匿名 POST **恰好 3** 个 = `/api/auth/login` + `/api/auth/students/bind` + `/api/auth/teachers/bind`；匿名其它方法 **0** | ✅ 真 |
| `views/admin/ResourceIndex.vue:150,160,161,167,169` | 「验身材料匿名一律不给」「POST/PATCH/DELETE 一共 {{ writeOps }} 个操作一律挂 `require_admin`」 | openapi 实测挂 security 的操作 **84** 个；终审路线三逐格核过 9 可写 / 14 只读 | ✅ 真 |
| `views/admin/AuditLogList.vue:267,272,277,279,299,363,417,419` | 「四个口径一律是后端的既有裁定」「**GET 一律不记**」「九格全是标量，一个请求体都不落」「本页**没有任何写操作**」「都不注册（打过去是 405）」 | 审计表实测 **9** 列；跑 15 个写请求之后 `methods = {'POST': 15}`、**0 个 GET** | ✅ 真 |
| `views/teacher/AlertQueue.vue:528` | 「`?level=red` 会被 FastAPI **静默忽略**（不报错、只返回全量）」 | 实发 `?level=red&limit=200` → **200 / 21 行**（红 9 / 黄 4 / 绿 8），与不带参数**逐字相同** | ✅ 真 |
| `views/teacher/AlertQueue.vue:456,538,541,565-590,751` | 「那一档的计数都是**我这一个范围**里的，管理员登录看到的是全校」等 | 与终审路线二第 4 步的实测一致（21 / 红9 黄4 绿8） | ✅ 真 |
| `views/student/Notifications.vue:173-180` | 「匿名打 `GET /api/notifications` 是 **401**」「只有 7 个资源匿名可读」「**63 个 GET = 15 匿名 + 48 挂 security**」 | openapi 实测 GET **63** = **15** 匿名 + **48** 挂 security、schemes **3**、paths **74**、ops **102** | ✅ 真（这是 Plan 06 **改后**的文案；它引号里那句「48 个匿名 GET」是**被驳斥的旧话**，不是断言） |
| `views/student/Notifications.vue:121,154,168,172` | 「本页既不做客户端过滤、也不再 `.sort()`」「改前这一段还接着写了三句，**三句今天都是假话**」 | 同上（那一格是 Plan 06 的修正记录） | ✅ 真 |
| `views/teacher/Dashboard.vue:527,550,707,817,840,911` | 「`require_teaches_section` —— 不是自己任教的班一律 403」「`curve` 恒为 **7** 格」「『读』一律走 `GET …/rpe-token`」 | 与 §13.4.4 的裁定一致；终审路线四实测 4 节已发起课次的口令逐个 200、`curve` 7 格 | ✅ 真 |
| `views/teacher/StudentDetail.vue:755,938,1029,1042,1048,1128,1163,1221,1245,1250,1273,1290,1300,1308,1314` | 「两行的 `semester_id` 都必须等于 as_of 所属的那个学期」「`schema.d.ts` 宣称『这两格永远有值』是一份**假契约**」「**交付的那几个脚本一律把它关掉**」「`allow_header_identity()` **结构上恒 False**」 | `serve.ps1` / `demo.ps1` 都**强制清** `PE_ALLOW_HEADER_IDENTITY`（两条守卫钉住「逐字同一段」）；那一格「假契约」是 §13.18.4 已结案的真实取证 | ✅ 真 |
| `views/teacher/ClassReport.vue:456,484,490,534,539,601,620` | 「『不是你的班』**刻意同形**，都报 403」「`curve` 恒为 7 格」「某一层的 rate 是 null 时显示「—」，**不是** 0%」 | 与 §13.4.4 / 终审路线三的实测一致 | ✅ 真 |
| `views/student/CheckIn.vue:299,362,485,534,557` | 「提交时刻与「是否迟交」都由服务端算 —— 前端传不了，也改不了」「迟交与休息日打卡都**不计入**分子」「后端刻意不做覆盖」 | 实测同一天第二次打卡 → **409 `integrity_conflict`**；`feedback.py` 的口径逐字如此 | ✅ 真 |
| `views/student/Home.vue:279,287,343,365,458` | 「两档 404 都折成了 `null`」「都**不计入**完成率」「原型不做真实推送」 | 与 `dashboard._student_home_response` 的实测一致 | ✅ 真 |
| `views/student/WeeklySheet.vue:254` · `views/student/RpeEntry.vue:332` · `views/student/MiniTest.vue:366,367,386,416` | 「这一周没有任何调整时 `factor` 就是模板值」「三周前没交的仍然可以补交（后端刻意不做过期）」「进步榜一律读班级周报的 `progress_board`」「端点的 `semester_id` 与 `week` 都是**必填**」 | 逐个与后端实现/spec 一致 | ✅ 真 |
| `views/admin/ResourceDetail.vue:335,373,376,459` · `views/admin/ResourceList.vue:420,429,494` | 「匿名打过去是 401」「`*Update` 的每一格在**请求模型**上都是 optional」「表单里出现的每一格都来自 `/openapi.json`」 | 与 openapi 实测一致 | ✅ 真 |
| `views/auth/Bind.vue:287,327,336` | 「不做复杂度规则、不做找回」「一个账号只能绑定一次」 | `MIN_PASSWORD_LENGTH = 8` 且**只判长度不判复杂度**（`passwords.py` 逐字）；绑定 409 排在 403 之后 | ✅ 真 |
| `components/charts/*.vue`（`CompletionBars:107-108` · `LayerDonut:136` · `ProgressBoard:189-195`） | 「这与「三层都是 0%」是两件事」「`top` 与 `regressed` 都是空的」 | 都是**空态/未知态**的口径说明，与 §13 的裁定一致 | ✅ 真 |

⇒ **挖出 1 处假的、修了 1 处、登记 0 处**。
⚠️ **不在本类、本波没扫的**（如实报）：① 各 `.vue` 的 **`<script>` docblock** 13 个文件
（spec §13.18.5 待清扫 ①）；② **后端 docstring** 里的同族身份口径假话
（`app/api/routers/dashboard.py:859`、`feedback.py:1205` 的「前端一次只注入一个身份头」）
—— ⚠️ 后者**会动 openapi 字节**（它们是**路由函数**的 docstring，与 §6 那六处不同），
故仍留作自己的一波；③ `Notifications.vue` 空态写死的「19 条通知 / 19 个学生 id」；
④ `.auth__advice` 两份 CSS；⑤ `smoke.mjs` 的 `toPlainText` 不反转义实体（S4-15）。

---

## ⑥ P6 五处 + P7

### 6.1 P6 逐条改前 / 改后

| # | 住址 | 改前 | 改后 | 核实物 |
|---|---|---|---|---|
| **S3-2** | 说明书 §0 | `（下称 **spec**，5400 余行，给开发者与对接工程师读）` | `（下称 **spec**，给开发者与对接工程师读）` —— **删掉数字** | spec 改前实测 **6233 行**（差 833 行 / 13%）。⚠️ 派单给了两档，本波选**删掉**：写任何具体行数都是**第二个所有者**，而 spec 每一波都在长 —— ⚠️ **本波自己就把它从 6233 抬到 6635 行**，那正是「写一个行数就会漂」的现场证据 |
| **S3-3** | 说明书 §2① | `（⚠️ 这个文件在隧道退出时会被脚本自己删掉 —— 留一份写着死链接的文件比没有文件更坏）` | 加但书：「**正常停止**（在它的终端里 `Ctrl-C`）时会被脚本自己删掉；⚠️ 而**被硬杀**（IDE 的停止按钮 / 任务管理器 / 断电）时它可能**留下来**、而里面写着一条**已经失效**的地址 ⇒ 一律以我方最新通知为准」+ 一句「我方那台机器上的自检若发现链接可能已死，会往这个文件里**追加**几行说明（追加、不重写，所以上面那条链接还在）」 | spec §13.17.5 已登记那一格（`finally` 跑不到）；⚠️ 同批也把 **`tunnel.ps1` 写进那个文件的表头**改成了同一句但书（改前它也无条件说「会被删掉」） |
| **S3-4** | 说明书 §8② | `⚠️ 这一格你们自己改不了（它是服务端的环境变量），请找我方。` | 分**三档**：「**我方给的那条公网链接**（§2①）你们改不了、请找我方；**机房里自己起的局域网那一份**（§2②）与**你们自己机器上解包起的那一份**（§2③）都能自己改 —— 起服务的那个终端里会打印一段 ⚠️，逐字写着处置（大意是：明文 http 上请把 `PE_ENV` 去掉、回到缺省档，或者去掉 `-Lan`）」 | `serve.ps1` 实测**两处**都打印：⑤ 那一段**无条件**打印「当前档位 / Secure 只在 prod 开 / 在明文 http 上跑 prod 档浏览器会拒收会话 cookie」；`-Lan` + `prod` 那一档另打印「· 只是局域网明文试用 → 去掉 PE_ENV（回到缺省的 dev 档），或去掉 -Lan；」 |
| **S3-5** | README **三处** | ① `/api/health`「三格 `{"status","tables","students"}`」② 包里 `Document\`「spec 与甲方试用说明书」③ **没提** `backend\tests\` | ① → 「**四格** `{"status","tables","students","trial"}`（第四格 `trial` 是 Plan 07 Task 1 加的：只有试用档为 `true`，前端顶那条告示读的就是它）」② → 「**28 个文件** = 12 份 `.md` + 15 张截图 + 1 份 `.doc`；那 12 份 `.md` 是 spec、甲方试用说明书、以及 10 份实施计划与取证记录」③ → 补「⚠️ **以及 `tests\` 那 70 个测试文件**」+ 一整段逐字交代**为什么留着**（可执行的判据 + 决策记录）与「里面会有内部措辞（波次编号、顶回、待清扫），请以 spec 与说明书为准」 | 解包实测：`Document\` **28**（`.md` **12** / `.png` **15** / `.doc` **1**）、`backend\tests\` **70**、`backend\data\` **24**、`frontend\dist\` **29**、zip 内 **339** 个文件；`/api/health` 实测四格。⚠️ **终审报的是「11 份 .md」，本波实测 12 份**（总数 28 对；12+15+1=28） |
| **S3-7** | 说明书 §8 | **一个字都没提**「业务日 `as_of`」那个输入框 | **新增第 4 步**（标题同时从「三步」改成「四步」）：「页面上一片空 / 说没有训练单 / 说这一周没有数据 → 看会话条上那个**日期**（它叫「业务日」）：整套仿真数据是按 **`2025-10-12`** 那一天造的，而那个输入框缺省也正是这一天。⚠️ 把它改成今天会让**大部分板块当场空掉** —— **那是口径、不是坏了**。改回 `2025-10-12` 就都回来了。⚠️ 它记在**浏览器本地**，所以换一台机器、换一个浏览器、或清过一次浏览器数据，都要重新设一次。」 | 终审实测 `weekly_sheet = null` / `week = 59` / `weekly-sheet` → **404 `no_active_prescription`**；那个输入框在 **16 条路由**上都在场（`IdentitySwitcher.vue`），缺省值的所有者是 `stores/identity.ts` 的 `DEMO_AS_OF` |

**说明书改后：165 行**（上限 **200**；改前 160）· **25 136 B** · sha256[:16] `269AB1742C726D3B` ·
**纯 CRLF**（crlf 165 / 裸 LF 0）· **无 BOM**。
⚠️ 四条既有纪律逐个复核（派单点名「别弄坏」）：
`&&` **0** 处 · **没写死公网主机名**（`trycloudflare.com` 只出现 **1** 次，在
「链接的形状是 `https://<随机三段单词>.trycloudflare.com`」那一句里，且逐字写着
「每次重开都变，所以本文不印某一条具体地址」；那条具体主机名 `related-llp-…` 实测 **0** 命中）·
**内部术语**只用了说明书里本来就有的 `PE_ENV` / `-Lan` / spec 章节号 ·
行尾仍**纯 CRLF、无 BOM**。
**README 改后：6211 B**（改前 5006）· 103 行 · sha256[:16] `8E105A3B99892055` · 纯 CRLF · 无 BOM。

### 6.2 P7 = S3-6 · watchdog

| 格 | 改前 | 改后 |
|---|---|---|
| **① 缺省值** | `[int]$Watchdog = 0`（= 关） | **`[int]$Watchdog = 60`**；⚠️ `0` **仍然可用** = 显式关掉，⑦ 那一圈的循环体在那一档与改前**逐字相同**（`Start-Sleep -Seconds 2` + `Write-NewTunnelLog`，一格都不许多） |
| **② 报警落点** | 只 `Write-Host` 到一个没人看的终端 | 除了打印，**还往 `.trial\public-url.txt` 里 `[System.IO.File]::AppendAllText` 追加六行**：一个空行 + 「⚠️ `<时刻>` 自检报警：上面这条链接**可能已经死了**」+「从 `<起点时刻>` 起连续 N 拍打不通（最后一次 = 什么形状）」+「而隧道进程还活着（PID …）」+「⚠️ 它**不会自动恢复**：本脚本刻意不自动重开（重开会换掉你们手上那条链接）」+「重开 `scripts\tunnel.ps1` 会得到一个**全新的地址**，请把它重新发给试用者」。⚠️ **追加、不重写、不删**（重写会把 `url` / `隧道 PID` / 两格 health 一起冲掉，于是「死的是**哪一条**链接」反而查不到；而那个文件此刻正是**唯一**写着链接的地方）。⚠️ 编码与 ⑤ 那一次写入**逐字相同**（UTF-8 **带 BOM** + CRLF）；⚠️ 文件不在时 `Test-Path` 兜住、只打印一句说明 |
| **③ 说明书 §8①** | 没有那一句 | 补「⚠️ **两档都不会自己恢复**（我方那台机器上的脚本**刻意不自动重开** —— 自动重开会换掉你们手上那条链接），一律找我方重开」 |
| **④ 文档** | `.DESCRIPTION` / `.PARAMETER Watchdog` 写「缺省 **0 = 关**」「只打印」 | 改成「缺省 **60**」「只**报警**」，并**新加一节**逐字交代缺省值为什么从 0 抬到 60（含「换来的是『与本波之前逐字相同』，这个交换在交付期不划算」）；小标题 `⚠️ ``-Watchdog``：长跑期的自检，⚠️ **只打印、不自动重开**` → `…**只报警、不自动重开**` |
| **⑤ 新增的状态量** | 三个（`$WatchdogFailures` / `$WatchdogProbes` / `$WatchdogAlarmShown`） | **四个**：多了 `$WatchdogFailingSince`（第一拍不通时记下起点）—— 追加进文件的那一行要报「从什么时候起」，否则读的人只知道「死了」不知道「死了多久」，就判不了「要不要现在重开」 |

⚠️ **「不自动重开」那条裁定一个字都没动**（Task 4 立的、Task 6 终审也同意）。
⚠️ **一次都没碰控制者那条活隧道**（它今天已经带着 `-Watchdog 60` 在跑；本波一次都没跑 `tunnel.ps1`）。

**守卫与定点变异**（`backend/tests/test_tunnel.py`）：
那条测试从**五拍**抬到**八拍**并改名 `test_the_watchdog_defaults_to_off_and_only_prints_never_reopens`
→ **`test_the_watchdog_defaults_to_sixty_and_alarms_without_reopening`**
（新增：`AppendAllText($UrlFile` 恰好一次 / 不许 `WriteAllText` / 不许 `Remove-Item` /
`Test-Path` 兜住 / 逐字有「**不会自动恢复**」与「**全新的地址**」/ 报了 `$WatchdogFailingSince`）；
参数面那条从 `assert "[int]$Watchdog = 0"` 改成 `= 60` 且**不许**再出现 `= 0`。

| 变异 | 结果 |
|---|---|
| **W1** `[int]$Watchdog = 60` → `= 0` | ❌ **红**（`test_the_parameter_face_gains_two_values_and_still_has_no_switch`） |
| **W2** `AppendAllText($UrlFile` → `WriteAllText($UrlFile`（追加改成重写） | ❌ **红**（「报警那一拍没有往 URL 文件里**追加**」） |
| **W3** 追加 → `Remove-Item $UrlFile -Force; WriteAllText(…)`（删掉再写） | ❌ **红** |
| **W4** `'--logfile', $QuotedLogFile` → `'--logfile', $LogFile` | ❌ **红**（孤儿标记那一条守卫） |

四次还原后**逐字节相同**（`tunnel.ps1` sha256[:16] **`C70D17171720D95D`**）。
`tests/test_tunnel.py`：**19 passed**（改前 18，+1 = 本波新加的那条）。
`tests/test_serve.py`：**41 passed**（改前 40，+1）。
⚠️ 三个 `.ps1` 逐个核过：`serve.ps1` **47 990 B / BOM ✓ / crlf 639 / 裸 LF 0**、
`tunnel.ps1` **81 237 B / BOM ✓ / crlf 1097 / 裸 LF 0**、
（`trial.ps1` / `package.ps1` / `demo.ps1` / `backup.ps1` / `restore.ps1` 本波**一个字都没动**）；
`[System.Management.Automation.Language.Parser]::ParseFile` 对 `serve.ps1` 与 `tunnel.ps1`
各 **0 错误**。⚠️ **本波没有再剥掉任何 BOM**（前几波那四次事故没有重演：
一律用 Python 二进制模式编辑，每改完一个文件当场核 `git ls-files --eol` + BOM + 裸 LF 数）。

---

## ⑦ P8（重打包）+ P9（openapi 计数）

### 7.1 新包与旧包对照

| 格 | 旧包 | 新包 |
|---|---|---|
| 文件名 | `pe-ims-trial-20261016-032033.zip` | **`pe-ims-trial-20261016-115923.zip`** |
| 字节数 | **10 305 418 B** | **10 339 554 B**（+34 136 B） |
| sha256[:16] | **`EC05579FC28D19D8`** | **`1EA5C0C0A4CD7CE8`** |
| 文件数 | **339** | **339**（一个不多一个不少） |

⚠️ **旧包已删**（派单裁定：删掉旧的，`dist-pack\` 会累积是 Task 4 登记的待清扫，
甲方拿到两份会困惑）；**删之前先报了它的字节数与 sha**（上表）。
删后 `dist-pack\` 里**只有 1 个包**。
⚠️ `package.ps1` 退出码 **0**；它自己印了一句「⚠️ staging 删不掉：
`%TEMP%\pe_package_39164`（有进程持有它？请手工删）」—— 那是 **S4-16** 登记的既有形状
（**不是静默**，脚本自己说了）。本波尝试手工删它，**仍删不掉**（有进程持有）；
`%TEMP%` 里今天剩 **2** 个 `pe_package_*`（其中 1 个是终审复核窗口之前就在的）。

### 7.2 六格复核

| # | 格 | 实测 | |
|---|---|---|---|
| ① | 新包字节数与文件数 | 10 339 554 B / **339** 文件（与旧包对照见上表） | ✅ |
| ② | 解包 → `/api/health` 200 + **16 条路由逐条 200** | 解到 `%TEMP%\p07t7\new\`（不含空格）核了 5 个关键文件；⚠️ **16 条路由那一次是在含空格与中文的解包目录里跑的**（第 ⑤ 格，端口 **8044**）：`/api/health` → **200** `{"status":"ok","tables":28,"students":60,"trial":true}`；**16 条路由 16 × 200**，每条都回**同一份 2 729 B 的 `index.html`**（sha256[:12] `ec322b31ad00` = 本波重建的那一份）；另加 `/`、`/s`、`/t`、`/nope-not-a-route` 四条 → **200**；`/openapi.json` → **200 / 420 367 B / `6058F97F09B35855`**；`/docs` → 200 / 1 023 B；`/redoc` → 200 / 905 B | ✅ |
| ③ | 解包目录里的 `dist` 与本波重建的那一份**逐字节相同** | 文件清单**逐个相同**（29 vs 29，`same list = True`）；**逐文件 sha256 比对 → 0 处不同**；派单点名的 5 个哈希逐个 `OK`（`index.html` `EC322B31AD0039FD` · `index-Bb2uTFzm.js` `CB0DE5B563D64635` · `index-D22u2MPR.css` `729E4707DB46386A` · `StudentDetail-h6aK5CtQ.js` `812ADC29F97FD8EC` · `AuditLogList-CeNceCxw.js` `1E0555E7BBC20780` · 另加 `ResourceIndex-DqalY3wm.js` `588A301421A96F2F`） | ✅ |
| ④ | 在解包目录里搜 P2 那五处旧串 | **`frontend/dist/**` → 0 命中**（`不做登录失败锁定` / `口令找回 / 登录失败锁定` / `它走的是匿名` / `180 行全量` 四个判据全 0）。⚠️ **如实报**：包里另有 **8 个文件**含这些串，而它们**全是「提及」不是「本身」**：6 个前端源文件里的**取证注释**（块注释/HTML 注释，`check-dist.mjs` 的 `stripComments` 会剥掉、构建也剥掉）、`check-dist.mjs` 自己的**判据字面量**、以及 **spec**（它必须逐字引改前那句才说得清修了什么）。**渲染给甲方的那一份（`dist`）0 命中** | ✅ |
| ⑤ | **含空格与中文的路径**（= S1-1 的复现路径） | 见 §2.5：**改后绿** —— 同一个目录形状 `%TEMP%\p07t7\体育系统 试用\`、换成**新包**重解、`serve.ps1 -Port 8044 -SkipBuild` **起来了**（PID 13252、健康检查轮询 1 次就 200）+ 上面 ② 那 16 条路由 | ✅ **修完在这里变绿了** |
| ⑥ | 旧包删不删 | **删了**（删前先报字节数与 sha，见 7.1） | ✅ |

**包里另外逐个核过的**：`README.md` / 说明书 / spec / `scripts\serve.ps1` / `scripts\tunnel.ps1` /
`backend\app\api\audit.py` 六个文件与仓库工作树**逐字节相同**（sha256 逐个 `OK`）；
`Document\` = **28**（`.md` 12 / `.png` 15 / `.doc` 1）；`backend\tests\` = **70**；
`backend\data\` = **24**；**不含**任何 `.db`、不含 `.git/`、不含 `tools/`、
不含 `.superpowers/`、不含 `node_modules`。

### 7.3 P9 · `gen:api` 与五格

| 格 | 实测 |
|---|---|
| `npm run gen:api` 退出码 | **0**（`dump_openapi.py` 打出「420367 字节 / 74 路径 / 102 操作」+ `openapi-typescript 7.13.0`，151.2 ms） |
| `/openapi.json` 改前 → 改后 | **420 367 B / `6058F97F09B35855`** → **420 367 B / `6058F97F09B35855`** ⇒ ⚠️⚠️ **逐字节相同、一个字节都没变** |
| **五格** | **74 路径 / 102 操作 / 挂 security 84 / GET 63（15 匿名 + 48 挂 security）/ securitySchemes 3** —— 逐字不变（本波另用离线 `create_app()` 现场数了一遍，与 HTTP 那一侧同值） |
| catch-all（非 `/api` 开头的路径模板） | **0** |
| 未定型响应 | **24**（= 23 个泛型 list + `/api/health`；`tests/test_main.py:774` 钉住） |
| `expected` | **26**（`tests/api/test_prescription_api.py:2034` 钉住） |
| `gen:api` 一致性守卫 | ✅ 绿（`test_the_offline_dump_is_byte_identical_to_the_http_endpoint`） |
| `schema.d.ts` 的**行尾**（⚠️ 派单要求「自己实测并报」） | `gen:api` 写出的是 **LF**：**521 153 B / 裸 LF 10 446 / CRLF 0**；而 `.gitattributes` + `core.autocrlf=true` 会归一 ⇒ **`git diff --exit-code` 退出码 0（空 diff）**，与 §15 台账 **F3** 那一格逐字同形。已 `git checkout` 还原成入库口径的 **CRLF**：**531 599 B / crlf 10 446 / 裸 LF 0 / sha256[:16] `665E54A6CD2AB57F`**，与改前**逐字节相同** ⇒ `git status` 里没有它 |

⚠️⚠️ **本波实测出一个与派单/终审预期不同的结论，如实报**：
派单说「这三处是 docstring，改它们会改 openapi 的 description 字节 ⇒ 必须重跑 `gen:api`」。
**实测：一个字节都没改到 openapi。** 理由是这六处**都不是路由函数的 docstring** ——
`app/static.py` 与 `app/api/audit.py` 的那四处是**模块 docstring**，
`audit.py:241`（`target_of`）与 `:365`（审计中间件）是**非路由函数**的 docstring，
而 FastAPI 只把**路由函数**的 docstring 渲染进 `description`。
⇒ **P9 的代价是 0**（`gen:api` 与五格复核仍然照做了，因为那是唯一能证明「代价是 0」的办法）。
⚠️ 而这也说明 §13.18.5 待清扫 ② 那一族（`routers/dashboard.py:859`、`routers/feedback.py:1205`
的「前端一次只注入一个身份头」）**才是真的会动 openapi 字节的那一类** ——
它们是**路由函数**的 docstring，故本波**没动**（它必须是自己的一波）。

### 7.4 ⚠️ P9 同族计数清单（后端 docstring + 前端注释里的 openapi 计数）

`Grep '72 (个)?路径|99 (个)?操作|71 (个)?路径|60 个 GET|44 个?匿名|48 个匿名|63 (个)?GET|102 (个)?操作|74 (个)?路径|路径模板'`
全仓 → **命中 60 行**，逐个判过：

| 类 | 处数 | 处置 |
|---|---|---|
| **需要改的**（当前断言、且已过期） | **6** | ✅ **全改了**：`app/static.py:85`（72/100 → 74/102）· `app/api/audit.py:41`（99/60 → 102/63）· `:45`（44 匿名 → 63 个 GET 其中 15 匿名）· `:241`（71 → 74）· `:365`（60 → 63）· `app/api/routers/__init__.py:103`（63/91 → 74/102）。每处都补了一句「⚠️ 那是**时点快照**，确切的五格由 `smoke.mjs` 现场数 `/openapi.json`」，并登记 §15 台账 **F6**（「它们会再漂，而今天没有守卫钉它们」） |
| **准确的历史陈述**（绑时点，刻意不改） | **9** | `spec:1632`（那张表逐字记着「Plan 06 Task 5 起是 72 / Task 9 起是 73 / Task 10 起是 74」）· `spec:1652`、`:2146`、`:3416`（各波「实测五格逐字不变」的时点记录）· `spec:2637`、`:2645`（Plan 06 Task 3/4 的时点）· `spec:1492-1547`、`:4336`、`:4406`（安全收紧波「44 匿名 / 48 个匿名 GET」的裁定记录）· `Document/2026-10-11-实施计划04-…`、`…05A…`、`…05B…`、`…前后端联调取证.md`（**绑时点的历史计划文档**，与 F5 同一条纪律：一个字都不改） |
| **前端注释**（`smoke.mjs` 里的 71/99/60 → 72/73/100/101 一串） | **7** | 逐个核过：那是 `smoke.mjs` 逐波记的**增量史**（「路径模板 71 → **72**、操作 99 → **100**…」），每一句都绑着一个波次 ⇒ **准确的历史陈述，不改** |
| **前端里已经做对的那一格** | **2** | `api/types.ts:26` 与 `api/endpoints.ts:22` 逐字写着「**路径模板数与操作数本处刻意不复述**（硬规矩 #111）」⇒ Plan 04 收尾波就做对了，**本波拿它当 F6 的样板** |
| **`Notifications.vue:19`**（`<script>` docblock 里的「48 个匿名 GET」） | **1** | 属 §13.18.5 待清扫 ①（docblock 大扫应当独立成波），**本波不动**；⚠️ 而它同文件 **:178** 的**渲染正文**今天写的是「63 个 GET = 15 匿名 + 48 挂 security」= **真话**（§5.2 已核） |

⇒ **挖出 6 处需要改的、6 处全修了；19 处是准确的历史陈述、刻意不改。**

---

## ⑧ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 8.1 ⚠️ 顶回：**0 处**

派单 §4 列了 7 个「本波最可能顶回」的点，**逐个核过、一个都不顶回**：

| # | 派单问的那一格 | 本波的判断 |
|---|---|---|
| ① | P1 的修法（引号 vs `&`）与守卫形状（真跑 vs 断言命令行） | **两档裁定都同意**。引号那一档的逐字理由见 §2.2（`&` 会阻塞，④ 那一圈轮询与 `finally` 收子进程都要那个 `Process` 对象）；守卫形状那一档见 §2.4（真跑会把一套 205 秒、一个端口都不绑的套件变成要抢端口的集成测试），⚠️ 而派单要求的「必须再补一条真跑的取证」**已补**（§2.5 改前红/改后绿） |
| ② | P2 页面上要不要写具体数字（5 次 / 15 分钟） | **同意不写**。登录页那句已经给了唯一正确的动作（「稍后再试」）；数字写上去就是一个会漂的第二个所有者（三个阈值都是环境变量）。⚠️ 而**说明书 §6⑤ 保留数字**是对的：它逐字声明了自己是「一份时点快照」，且本波给它补了「这几个数都是服务端可配的，唯一所有者见 spec §13.4.6」 |
| ③ | P6-S3-2 的「不写具体行数」 | **同意，且本波有一个新证据**：本波自己就把 spec 从 6233 行抬到了 **6635** 行 ⇒ 写「约 6000 行」在本波之内就会漂 4%。已按「删掉数字」执行 |
| ④ | P7 的缺省 60 与「追加而不是重写」 | **两档都同意**。缺省 60：「进程在、链接死」是两波里**亲自撞到两次**的那一档，而它只报警、不改变任何行为。追加而不重写：重写会把 `url` / `隧道 PID` / 两格 health 一起冲掉，于是「死的是**哪一条**链接」反而查不到；而那个文件此刻正是**唯一**写着链接的地方 |
| ⑤ | P8 删旧包对不对 | **同意**。删之前先报了字节数与 sha（§7.1）；`dist-pack\` 已进 `.gitignore`，故删它不影响版本控制，而甲方拿到两份会困惑（且旧包里的 `dist` 有 5 处关于安全的假话） |
| ⑥ | P9 值不值得为三处 docstring 动 openapi 字节 | ⚠️ **这一格的前提本波实测推翻了**：它们**一个字节都没动到 openapi**（都是模块/非路由函数的 docstring，FastAPI 不渲染它们），故「值不值得」这个问题不成立 —— **代价是 0**，做了只有好处。⚠️ 而**真正会动 openapi 字节**的那一族（§13.18.5 待清扫 ②：`routers/dashboard.py:859`、`feedback.py:1205`）本波**没动**，它必须是自己的一波 |
| ⑦ | S1-2 的定级（终审说「若控制者认为应按『文案撒谎』归 S3，本席不争」；控制者裁定按 **S1**） | **同意按 S1 处理**。理由与本波自己的取证一致：① 它与**同批交付**的说明书 §6⑤ 在**安全**话题上互相打脸（两份交付物说法相反）；② 甲方落地的**第一页**就是它（`Login.vue` 的登录页正文）；③ 而 `App.vue` 那一处在 **16 条路由的页脚**上，覆盖面是全站的；④ `ApiErrorBanner.vue` 那一处是**被锁的人真会读到的处置建议**，改前它把人支去「反复重输」—— 那是一个**会让人做无效动作**的错误指引，不只是措辞不好看 |

### 8.2 没按派单做的：**0 处**

派单 §1 的 11 条与 §2 的 8 步**逐条做过**。⚠️ 三处**在派单之外多做**的，逐个交代：

| 多做的 | 为什么 |
|---|---|
| **S4-6** 的六处过期 openapi 计数 | 派单 §1 的 P9 **逐字要求**本波做（「S4 但本波顺手做，因为它随包交付」）⇒ 不是多做 |
| **S4-11**（`tunnel.ps1` 的 `Start-Process` 同族） | 派单 P1② **逐字要求**「全仓搜同族…逐个判」，而终审也点了 `tunnel.ps1:648/656`；⚠️ 本波正在改 `tunnel.ps1`（P4/P7），**同一段代码、同一条修法、同一批守卫**，分两波做会两次动同一个函数、两次跑同一批变异 ⇒ 一并修了 |
| `check-dist.mjs` 把 `.vue` 加进源码侧扫描面 | P2④ 要求「`frontend/src/**` 里都不含那一族串」，而这一族 6 处里**有 3 处是 `.vue`** —— 不加就是**守卫扫不到它要守的东西**（假绿）。加进去之后 CDN 那一组仍然 0 命中（扫到 56 个文件），故**没有引入恒红** |
| §15 台账 **F / G 两个组标题的件数** | 终审 **S4-4** 说那两个标题的件数是错的；本波要往两组各加一条，**两个标题都得动** ⇒ 顺带改对了（⚠️ S4-4 本身留下一波结案） |

⚠️ **S4 其余 14 条一条都没修**（留下一波 Task 8）。

### 8.3 待清扫（本波新登记 / 仍然开着的）

| # | 条 | 住址 |
|---|---|---|
| 1 | **F6（本波新登记）** 散文与注释里的 openapi 计数会随端点增删而漂，而**没有守卫钉它们**。本波改了六处并给每处补了「那是时点快照」的 ⚠️，而**成因没治** | spec §15 F6 |
| 2 | **G4（本波新登记）** `Start-Process -ArgumentList` 的引号规则今天有**两个所有者**（`serve.ps1` 的函数 + `tunnel.ps1` 内联的两段）。⚠️ 刻意如此（理由逐字记着），而「第三个 `Start-Process`」要自己再写一遍。**建议下一波**加一条跨脚本的形状守卫（凡 `-ArgumentList` 后面跟的是数组变量就红） | spec §15 G4 |
| 3 | **§13.18.5 待清扫 ①**：13 个文件的 `<script>` docblock 同族过期散文（含 `Notifications.vue:19` 的「48 个匿名 GET」） | spec §13.18.5 |
| 4 | **§13.18.5 待清扫 ②**：后端**路由函数** docstring 里的同族假话（`routers/dashboard.py:859`、`feedback.py:1205`）—— ⚠️ 这一族**真的会动 openapi 字节**，必须自己一波 | spec §13.18.5 |
| 5 | **§13.18.5 待清扫 ③④**：`Notifications.vue` 空态写死的「19 条通知 / 19 个学生 id」· `.auth__advice` 两份 CSS | spec §13.18.5 |
| 6 | **S4-10** 公网档 smoke 的盲区**变宽了**：本波换了产物哈希，而公网档自 Task 3 之后没跑过（本波按派单**没跑**） | 终审 §7.3 |
| 7 | **S4-16** `package.ps1` 的 staging 残渣：本波这一次也留了 1 个（`pe_package_39164`，**手工也删不掉**、有进程持有）；`%TEMP%` 里今天共 2 个 | 终审 S4-16 |
| 8 | **S4-7** spec §13.15 第 10 条与 §15 D2 仍写 `/openapi.json` 是 **417 032 B**，而今天实测仍是 **420 367 B**（本波核过、**没改**，留下一波） | 终审 S4-7 |
| 9 | **G2** 打卡页那句「页面下方把 `source` 写成 `student`」的笔误（说明书路线一第 6 步逐字记着「我方已登记待修」）—— 本波**没修**（不在 11 条里） | spec §15 G2 |

### 8.4 关切（**不是缺陷**）

1. ⚠️ **5173 上有一个不是本波起的 vite**（PID 43520，`StartTime 09:26:55`，早于本波开工）。
   派单说它「已经不见了」，而它**在**。本波**没杀它**（不是自己的进程），
   dev 档 smoke 直接复用了它 —— ⚠️ 复用之前先核过它服务的正是本波改后的源
   （`GET /src/views/auth/Login.vue` 的正文里搜得到「连错多次会被临时锁定」）。
   ⇒ 若控制者认为那一个应当清掉，请自己处置（本波不敢杀别人的进程）。
2. ⚠️ **`backend/pe_demo.db` 被 smoke 写脏过**（那是 smoke 文件头逐字交代的既有形状）。
   本波开工先备份、收尾**逐字节还原**（1 597 440 B / `5F289B248CBD507A`）⇒ 净变化 0。
3. ⚠️ **`.trial\public-url.txt` 本波一个字都没动**（它此刻正写着那条**活着**的链接，
   由控制者那条隧道维护）。⚠️ 而 P7 的「追加六行」这一格本波**没有端到端真跑过**
   —— 跑 `tunnel.ps1` 会覆盖那个文件并多开一条公网入口（派单逐字禁止）。
   ⇒ 那一格的可执行判据是 `test_tunnel.py` 的**八拍守卫 + 四格定点变异**；如实记（硬规矩 #39）。
4. ⚠️ **产物哈希换了，而甲方手上那条链接是自动切过去的**：静态文件按请求从磁盘读，
   故重建之后立刻生效。本波**匿名复核过**它 200 且服务的是新哈希（§1.3 第 ⑤ 格）。
   ⚠️ 而**浏览器缓存**那一格：`index.html` 是 `no-cache`（每次回源校验），
   带指纹的 `assets/*` 是 `immutable` ⇒ 甲方**刷新一次**就会拿到新版，不会卡在旧哈希上。

---

## ⑨ 最终验收

### 9.1 测试与守卫

| 格 | 基线 | 本波 | |
|---|---|---|---|
| `pytest`（`--no-cov`） | **1623 passed**（193 s） | **1625 passed**（**205.18 s**） | ✅ **+2** = 本波新增的两条守卫（`test_serve.py` 的 S1-1 那条 + `test_tunnel.py` 的日志路径引号那条） |
| `pytest`（带 `--cov`） | **1622 passed + 1 skipped** | **1624 passed + 1 skipped**（三口径各跑一遍，逐个都是这个数） | ✅ **+2** |
| 覆盖率 ①`--cov=app.domain --cov-branch` | **1268 / 0 / 376 / 0 / 100%** | **1268 / 0 / 376 / 0 / 100%** | ✅ **逐字不变** |
| 覆盖率 ②`--cov=app --cov-branch` | **7311 / 201 / 1778 / 115** | **7311 / 201 / 1778 / 115**（96%） | ✅ **逐字不变** |
| 覆盖率 ③`--cov=scripts --cov=app.static --cov-branch` | **583 / 173 / 164 / 24** | **583 / 173 / 164 / 24**（69%） | ✅ **逐字不变**（⚠️ `Cover` 列不是基线，spec §12 有裁定） |
| 表数 | **28** | **28**（`/api/health` 的 `tables`，三个实例逐个都是 28） | ✅ |
| 迁移链 | **4 单头** | **4 个文件**：`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b`（本波**不动 schema**） | ✅ |
| 残差 diff | **0** | **0**（`tests/db/test_migration_chain.py` 的「在 head 上跑 autogenerate 比较应当无 diff」那一拍绿） | ✅ |
| 扫描面 | **72** | **72**（`tests/architecture/test_layering.py:781`：pipeline 10 + db 14 + domain 18 + …） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | **33** | **33**（本波现场数了那份清单的项数） | ✅ |
| 黄金用例 | **14** | **14**（`tests/integration/test_golden_cases.py`：`len(_CASES["input"]) == 14` / `len(_CASES["expected"]) == 14` / `len(set(_CASE_IDS)) == 14`） | ✅ |
| 未定型响应 | **24** | **24**（= 23 个泛型 list + `/api/health`） | ✅ |
| `expected` | **26** | **26** | ✅ |
| openapi 五格 | **74 / 102 / 84 / 63（15+48）/ 3** | **74 / 102 / 84 / 63（15+48）/ 3** | ✅ **一格都没变** |
| catch-all | **0** | **0** | ✅ |
| `/openapi.json` | **420 367 B / `6058F97F09B35855`** | **420 367 B / `6058F97F09B35855`** | ✅ ⚠️ **派单预期「P9 会改 description → 字节会变」，实测一个字节都没变**（理由见 §7.3） |
| `npm run build` | 退出码 0 | **退出码 0** / 141 modules / **29** 产物 / **687 804 B** | ✅ 新旧哈希对照见 §3.3 |
| `npm run check:tokens` | **36** / 下界 25 | **36** 个文件 / 下界 25 / **退出码 0** | ✅ |
| `npm run check:dist` | 25 产物 / **787 824** 字符（`--no-build` 口径 **589 118 B**） | 产物侧扫了 **25** 个文件 / **575.9 kB**；源码侧扫了 **56** 个文件（⚠️ 比基线多，因为本波把 `.vue` 加进了扫描面）/ **退出码 0** | ✅（⚠️ 两个数与基线**口径不同**：基线那两格是**源码侧**的字符数与 `--no-build` 的字节数，本波把新加的那一组也一起报了；**退出码 0 / 0 条红**是同一格） |
| 依赖清单守卫 | 一字不红 | ✅ **一字不红**（`tests/test_dependencies.py` 绿；**新增依赖：后端 0 / 前端 0**） | ✅ |
| `smoke.mjs` **dev 档** | **739** | **18/18 步全绿 · 739 断言绿 / 0 红 · 退出码 0** | ✅ **逐字相同** |
| `smoke.mjs` **产品档** | **739** | **18/18 步全绿 · 739 断言绿 / 0 红 · 退出码 0** | ✅ **逐字相同** |
| `smoke.mjs` **试用档** | **771** | **18/18 步全绿 · 771 断言绿 / 0 红 · 退出码 0** | ✅ **逐字相同** |
| `smoke.mjs` **公网档** | 711（Task 3 时点的旧值） | ⚠️ **本波没跑**（派单逐字禁止；且它会打甲方的库）⇒ 那一格的盲区**变宽了**（本波换了产物哈希），登记为待清扫（S4-10） | ⚠️ 如实报 |

### 9.2 禁区与纪律

| 格 | 实测 | |
|---|---|---|
| 四个数据指纹 | ✅ 全绿（`tests/test_refdata.py` 的 `STANDARD_FINGERPRINT = "D2C8E539E2FA0029"` 那一族逐条过；本波**一个字节都没动** `backend/data/**`） | ✅ |
| 18 个模板指纹 | ✅ 全绿（`tests/test_refdata_prescription.py`；`sum(len(t.addons) …) == 24` 那一拍也绿） | ✅ |
| `git diff a45a3f0 HEAD -- backend/data` | **空**（`--stat` 一行都没有） | ✅ |
| `backend/data/` 入库文件数 | **24** | ✅ |
| `backend/pe.db` | **False**（不存在） | ✅ |
| `backend/data/seed/` | **0** 个文件 | ✅ |
| 八处 gitignore 项 | `git ls-files` 按 `pe.db$|pe_demo.db|pe_trial.db|^backend/backups|^frontend/dist|^tools/|^\.trial/|^dist-pack` 过滤 → **0 命中** | ✅ **一个都没入库** |
| 四份 manifest + `.gitattributes` + `.gitignore` | `git diff --stat a45a3f0 HEAD -- backend/pyproject.toml frontend/package.json .gitattributes .gitignore` → **空** | ✅ **零 diff** |
| 禁跑的三个 CLI | 一次都没跑（`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`）；灌库一律走 `backend/scripts/demo_bootstrap.py`（与 `demo.ps1` / `trial.ps1` 同一个入口） | ✅ |
| 本波起的进程 | **全部已停并复验**（8000 / 8020 / 8041–8044 六个端口 **0 个 listener**） | ✅ |
| 控制者的两个进程 | **PID 45156（8030）与 37196（隧道，含 wrapper 48932）都仍在** | ✅ |
| `%TEMP%\p07t7` | ⚠️ **本报告写完之后才删**（探针与三个库副本都在里面）；删后复验见 §9.4 | — |
| ⚠️ 没删控制者的 `pe_trial_csv_41684` | 本波一次都没碰它（`Remove-Item` 一律指名自己的子目录） | ✅ |

### 9.3 文档的四个数（两个口径）

| 文件 | 工作树字节 | 行 | 行尾 | BOM | sha256[:16] | 入库 blob |
|---|---|---|---|---|---|---|
| `Document/2026-09-28-体育闭环原型-设计spec.md` | **678 829 B** | **6635** | **纯 CRLF**（crlf 6635 / 裸 LF **0**） | 无 | **`788FBD9FD423B9E8`** | `i/lf w/crlf attr/text eol=crlf` ⇒ 入库是 **LF**（`core.autocrlf=true` 归一） |
| `Document/2026-10-15-甲方试用说明书.md` | **25 136 B** | **165**（上限 **200**） | 纯 CRLF（裸 LF 0） | 无 | `269AB1742C726D3B` | 同上 |
| `README.md` | **6 211 B** | 103 | 纯 CRLF（裸 LF 0） | 无 | `8E105A3B99892055` | `i/lf w/crlf attr/` |
| `scripts/serve.ps1` | **47 990 B** | 639 | 纯 CRLF（裸 LF 0） | **有 BOM** ✅ | `93E7F727F6746613` | `i/lf w/crlf attr/text eol=crlf` |
| `scripts/tunnel.ps1` | **81 237 B** | 1097 | 纯 CRLF（裸 LF 0） | **有 BOM** ✅ | `C70D17171720D95D` | 同上 |

spec 改前是 **640 524 B / 6233 行 / `83659183907E9F60`** ⇒ 本波 **+38 305 B / +402 行**
（新增 §13.20 九个小节 + §13.17.5 的两档那一格 + §13.17.9 ③ 的四格裁定 + §13.18.5 的收口 + §15 的 F6/G4）。

### 9.4 commit sha

| # | sha | 一句话 | 自洽？ |
|---|---|---|---|
| ① | **`7e933eb`** | 终审报告原样入库（四数复核过，一个字没改） | ✅ 自洽（只加一份只读报告） |
| ② | **`678ca6d`** | 前端六处假话改真话 + `check-dist.mjs` 第三组禁用串 | ✅ 自洽（源与守卫同时改；⚠️ `dist` 已进 `.gitignore` 故不入库，那一份靠重打包交付） |
| ③ | **`39191c4`** | `serve.ps1` 的 S1-1 + `tunnel.ps1` 同族与 watchdog + 两条守卫 | ✅ 自洽（脚本与守卫同一个 commit，任何一个单独回滚都会红） |
| ④ | **`15608a6`** | 后端六处过期计数 + 两处 S1-2 同族注释 | ✅ 自洽（全是注释/docstring，openapi 逐字节不变） |
| ⑤ | **`f0c7996`** | 说明书七处 + README 三处 | ✅ 自洽（纯文档） |
| ⑥ | **本 commit** | spec（§13.17.5 / §13.17.9 / §13.18.5 / 新 §13.20 / §15 F6+G4）+ 本报告 | ✅ 自洽 |

⚠️ **六个 commit 逐个自洽**：任意一个单独 checkout 出来，`pytest` 都不会红
（②的守卫与源同时改；③的脚本与守卫同时改；④⑤是纯文档/注释；①只加一份只读文件）。
⚠️ **没有 push、没有碰 main**（`git branch --show-current` 全程是 `p07/review-fixes`）。

---

## ⑩ 行尾复核（逐个被改文件的 `git ls-files --eol`，两个口径）

| 文件 | `i/`（入库 blob） | `w/`（工作树） | `attr/` | 该文件的口径 | |
|---|---|---|---|---|---|
| `.superpowers/sdd/2026-10-15-实施计划07-交付与试用/task-6-review.md` | **lf** | **lf** | **`-text`** | `.superpowers/**` = LF | ✅ |
| `.superpowers/sdd/…/task-7-report.md`（本文件） | **lf** | **lf** | **`-text`** | 同上 | ✅ |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | lf | **crlf** | `text eol=crlf` | `Document/**/*.md` = CRLF | ✅ |
| `Document/2026-10-15-甲方试用说明书.md` | lf | **crlf** | `text eol=crlf` | 同上 | ✅ |
| `README.md` | lf | **crlf** | （空 = `core.autocrlf=true`） | 工作树 CRLF / 入库 LF | ✅ |
| `scripts/serve.ps1` | lf | **crlf** | `text eol=crlf` | `.ps1` = CRLF **+ BOM** | ✅（BOM 实测在） |
| `scripts/tunnel.ps1` | lf | **crlf** | `text eol=crlf` | 同上 | ✅（BOM 实测在） |
| `frontend/scripts/check-dist.mjs` | **lf** | crlf | （空） | `.mjs` 入库 blob = LF | ✅ |
| `frontend/src/App.vue` | **lf** | crlf | （空） | `.vue` 入库 blob = LF | ✅ |
| `frontend/src/api/auth.ts` | **lf** | crlf | （空） | `.ts` 入库 blob = LF | ✅ |
| `frontend/src/api/client.ts` | **lf** | crlf | （空） | 同上 | ✅ |
| `frontend/src/api/generated/schema.d.ts` | **lf** | **crlf** | （空） | ⚠️ `gen:api` 写出 LF、已 `git checkout` 还原成 CRLF（**531 599 B / `665E54A6CD2AB57F`**，与改前逐字节相同）⇒ `git diff` 为空 | ✅ |
| `frontend/src/components/ApiErrorBanner.vue` | **lf** | crlf | （空） | `.vue` 入库 blob = LF | ✅ |
| `frontend/src/views/auth/Login.vue` | **lf** | crlf | （空） | 同上 | ✅ |
| `frontend/src/views/student/MiniTest.vue` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/app/static.py` | **lf** | crlf | （空） | `.py` 入库 blob = LF | ✅ |
| `backend/app/api/audit.py` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/app/api/routers/__init__.py` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/app/auth/passwords.py` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/tests/api/test_crud.py` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/tests/test_serve.py` | **lf** | crlf | （空） | 同上 | ✅ |
| `backend/tests/test_tunnel.py` | **lf** | crlf | （空） | 同上 | ✅ |

⇒ **20 个被改/新增文件逐个核过，两个口径都对**：入库 blob 一律 **LF**，
工作树按各自口径（`.superpowers/**` = LF；`Document/**/*.md` 与 `.ps1` = CRLF；
其余 = `core.autocrlf=true` 检出成 CRLF）。
⚠️ **裸 LF 数在每个被改文件上都是 0**（用 Python 二进制模式逐个量过），
⚠️ **BOM 只在两个 `.ps1` 上、且都还在**（前几波那四次「剥掉 BOM」的事故没有重演：
本波一律用 Python 二进制模式编辑，`Doc.write()` 会原样保留 BOM 与原行尾，
每改完一个文件当场打印 `bytes / bom / eol`，并在收尾用 `git ls-files --eol` 复核一遍）。
