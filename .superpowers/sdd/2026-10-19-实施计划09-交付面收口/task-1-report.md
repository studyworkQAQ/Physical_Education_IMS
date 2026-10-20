># 实施计划 09 · Task 1 实现者报告 —— 构建清单（G22 的代码级收口）

> 分支 **`p09/delivery-surface`**；起点 **`beed5e0`**（只有计划文档那一个 commit）；基线 **`main` = `42dc849`**。
> 本波 **5** 个 commit：**`06b252a`** ①（清单的生成）· **`0dee8a2`** ②（`serve.ps1` 改判据 + `smoke.mjs` 头表）· **`af7a424`** ③（守卫 + 变异）· **`0cc54de`** ④（文档）· ⑤（本报告）。
> ⚠️ **未 push**（派单纪律）；⚠️ **一次都没碰 `main`**；⚠️ **一次都没重启 8030、一次都没杀 PID 36876 / 57488**（它们在开工时**已经不在**，见 §1）。
> ⚠️ 本报告**刻意不印自己的字节数与 sha256**（不动点问题；Plan 07 Task 8 在这一族连踩四次）。

---

## ① 环境 + 开工五格

### 1.1 环境（开工第一件事，硬规矩 #73）

| 格 | 实测 |
|---|---|
| `node --version` | **v24.19.0** |
| `python --version` | **Python 3.11.1**（无 venv） |
| PowerShell | **5.1.26100.9711**（Desktop） |
| 局域网 IPv4 | **192.168.31.11** |
| 本机 `LastBootUpTime` | ⚠️ **2026-10-20 09:41:15**（开工探针跑在 09:52:37）⇒ **本机在我接手前 11 分钟刚重启过** |
| 仓库 | HEAD = `beed5e0`，`main` = `42dc849`，`git status --porcelain` = **空** |

### 1.2 ⚠️⚠️ 开工五格 —— **两格量不到，因为甲方那一侧已经全死了**

派单逐字要求「量五格并报进报告」。**实测结果与派单给的现场不符**，如实报：

| # | 格 | 派单说的 | 开工实测 | 判 |
|---|---|---|---|---|
| 1 | uvicorn PID **36876**（127.0.0.1:8030） | 在跑 | **不在**（`Get-CimInstance Win32_Process` 里没有它） | ❌ |
| 2 | `cloudflared` PID **57488** / wrapper **58416** | 在跑 | **都不在** | ❌ |
| 3 | `backend/pe_trial.db` | 1 630 208 B / `382B507454143274` / mtime 2026-10-19 12:30:48 | **1 630 208 B / `382B507454143274` / 2026-10-19 12:30:48** | ✅ **逐字相符** |
| 4 | `frontend/dist` | 27 文件 / 708 583 B / `index.html` 2 567 B / `7EF16470CD6CE9BB` / 构建戳 02:27:05 | **27 文件 / 708 583 B / `index.html` 2 567 B / `7EF16470CD6CE9BB` / 27 个文件 mtime 全是 2026-10-19 02:27:05** | ✅ **逐字相符** |
| 5 | 8030 与甲方 URL 各一次匿名 health | 200 且 `tables:30` | 8030 → `WinError 10061 由于目标计算机积极拒绝，无法连接`；`Test-NetConnection 127.0.0.1:8030` → **False**；`https://hub-inns-holmes-theme.trycloudflare.com/api/health` → `URLError [Errno 2]` | ❌ **两格都量不到** |

**根因（有据可查，不是猜的）**：`LastBootUpTime = 2026-10-20 09:41:15` ⇒ **机器重启过**。
一并死掉的还有派单点名「不许杀」的那三个：**5173 的 vite（PID 43520）与其父 `npm run dev`（38900）**、
两个 `@deepseek-ai/dsh web`（**14368 / 16404**）—— 开工时 `Get-CimInstance` 里
**一个 node / python / cloudflared 进程都没有**（只有我自己的探针）。
`Get-NetTCPConnection -State Listen` 里 8000 / 8020 / 8030 / 5173 **一个都不在听**。

⚠️ **我没有去恢复它们**（派单的头号纪律是「不要重启 8030、重启窗口由控制者排」；
而隧道与 vite 同样不在我的授权范围里）。⇒ **甲方那条活链接从 09:41:15 起就是断的**，
本波**一次都没加重它的状态**（它已经断了），⚠️ 而这也意味着本波那一次 `npm run build`
**没有**当着任何活服务的面换掉前端。

### 1.3 ⚠️ 顺带一格：重启之后源面的 mtime 被**批量抬起来了**（那颗地雷今天更满膛）

重启后 `09:43:44` 有一大批文件的工作树 mtime 被改写（`backend/app/**`、`backend/tests/**` 等，
实测 60+ 个）。⚠️ 而 `frontend/src` 那 4 个「引信文件」的开工 mtime 是：

| 文件 | 开工 mtime |
|---|---|
| `src/views/teacher/StudentDetail.vue` | 2026-10-19 **11:47:20** |
| `src/views/auth/Bind.vue` | 2026-10-20 **09:43:49** |
| `src/views/admin/ResourceIndex.vue` | 2026-10-20 **09:43:49** |
| `src/api/generated/schema.d.ts` | 2026-10-19 **19:38:12** |

而 `dist/index.html` 的构建戳是 2026-10-19 **02:27:05** ⇒ **改前的 mtime 判据在今天这台机器上
必然重建**（4 个里最新的比构建戳新 1 天 7 小时）。⚠️ 而它们的**内容**与 HEAD 逐字相同
（`git status --porcelain` 为空）⇒ 「内容同步、mtime 不同步」这一格**今天仍然成立**。

### 1.4 基线复核（⚠️ 两处与派单给的数对不上，如实报）

| 文件 | 派单说的 | 开工实测（工作树） | 判 |
|---|---|---|---|
| spec | 1 133 967 B | **1 133 967 B** / **10 700** 行 / CRLF **10 700** / 裸 LF **0** / blob **1 123 267** B / 工作树 sha256[:16] `9342F4D55FCB10F4` / blob sha256[:16] `55F6DA53…`（改前） | ✅ |
| README | **15 478 B / 208 行** | **19 070 B / 243 行**（blob 18 827 B / sha16 `E470AE2FC55C8B24`） | ⚠️ **对不上** |
| 说明书 | 37 123 B / 179 行 | **37 123 B / 179 行**（`46E105CDB93D524B`） | ✅ |
| 计划 09 文档 | 14 027 B / 71 行 / `F018251500F294F3` | **14 027 B / 71 行 / `F018251500F294F3`** | ✅ |
| `frontend/src` | **65** 个文件 | **59** 个文件（`git ls-files frontend/src` = 59，磁盘 = 59，两侧相同） | ⚠️ **见下** |

⚠️ **README 那一格**：派单写 15 478 B / 208 行，实测 19 070 B / 243 行（`main` = `42dc849` 上就是
19 070 / 243，本波开工时 `git status` 为空 ⇒ **不是本波之前的谁改的**）。⚠️ 我**没有**去改它，
只如实报这一处数字差异（与 spec §13.15 第 8 条那格「`108 B` 复现不出来」同一条处置：如实记，不猜）。

⚠️ **`frontend/src` 是 59 个、不是 65 个**：**65 是「源面」的数，不是 `src` 的数**。
源面 = `src/**` 的 **59** 个 + **6** 个单文件（`index.html` / `package.json` / `vite.config.ts` /
`tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`）= **65** ⇒ 与 spec §15 G22 与计划 09 §1
钉的那个数**逐字相符**。⚠️ 而**两处散文都写着「`src` 那 65 个文件」/「`src/**` + 5 个配置文件」**，
两个措辞都不准（一个是把源面算成了 `src`，一个是把 6 个单文件数成了 5 个）⇒
本波把 `smoke.mjs` 那两处改对了（§8），⚠️ spec §15 G22 的那一句是**历史取证原文**、按体例不重写。

---

## ② 清单的形状

### 2.1 名字与住址

**`frontend/dist/.build-manifest.json`**（⚠️ 派单说「名字与形状你定」，我沿用了它给的那个名字）。
⚠️ 前导点是刻意的：它**不是**要发给浏览器的资产（`app/static.py` 的白名单只认那五个扩展名 +
`assets/` 前缀 ⇒ 它一个字节都不会被 HTTP 发出去）。

### 2.2 七个字段（派单要求的五格 + 两格自证）

| # | 字段 | 取值形状 | 它答的是哪一问 |
|---|---|---|---|
| ① | `schemaVersion` | `1`（整数） | 清单**自己的形状版本** ⇒ 将来加字段时把它 +1，读它的两侧就认得出「这是一份旧清单」并折向重建，而不是猜着读 |
| ② | `builtAt` | `"2026-10-20T10:59:40+08:00"` | **构建时刻**，⚠️ **带一个显式的 UTC 偏移**。本仓既有口径是 `+08:00`，而写它的一侧**现场取本机偏移**、不写死（写死一个 `+08:00` 等于把实现者那台机器焊进交付物，姿势逐字同 `serve.ps1` 的 `-Lan` 那一段「一个 IP 都不写死」）。⚠️ 秒级、**不带毫秒**：清单要能按字节对账 |
| ③ | `gitSha` | 40 位小写十六进制，**或 `null`** | **那次 build 的 commit** ⇒ 「这份产物是哪一个 commit 构建的」第一次可查（G22 的另一半）。⚠️ 一台没有 git 的机器上它是 `null`，⚠️ 而「问不到」与「问到了、是干净的」是两件事 ⇒ 用 `null` 分开，不许静默当成净构建 |
| ④ | `dirty` | `true` / `false` / `null` | **整个工作树**脏不脏（`git status --porcelain` 非空） |
| ⑤ | `dirtySources` | 字符串数组 / `null` | ⚠️ **源面**里当时没提交的那几个（`dirty` 的子集）。**它才是「这份产物能不能由 `gitSha` 复现」的判据**：一次只改了文档的未提交改动让 `dirty=true`，而产物**仍然**逐字节可复现 |
| ⑥ | `sourceRoots` | 7 个字符串 | **源面的根**（相对 `frontend/`）⇒ 「什么算源」的**唯一所有者**，`serve.ps1` 与 `check-dist.mjs` 都从这里**读回来** |
| ⑦ | `sources` | 65 个 `路径 → sha256` | 源面**逐文件的 sha256**。⚠️ 键是**相对 `frontend/` 的 posix 路径**（实测：0 个反斜杠 / 0 个绝对路径 / 0 个 `..` / 0 个盘符）；⚠️ 值是**小写** 64 位十六进制；⚠️ 落盘前**按字典序排序**（`readdirSync` 的顺序是文件系统给的，排序之后「同样的一份 src 构建两次，除 `builtAt` 外逐字节相同」） |

### 2.3 一份**真清单**的逐字内容（本波那一次真构建产出的那一份，7 021 B）

```json
{
  "schemaVersion": 1,
  "builtAt": "2026-10-20T10:59:40+08:00",
  "gitSha": "0dee8a23771d684fad29d0839b5a351953f45de6",
  "dirty": true,
  "dirtySources": [],
  "sourceRoots": [
    "src", "index.html", "package.json", "vite.config.ts",
    "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json"
  ],
  "sources": {
    "index.html":              "a64dc8cda6ad4132…",
    "package.json":            "fca169cade1bd6e8…",
    "src/App.vue":             "30bd94eaa966…",
    …（⚠️ 中间 61 个刻意截断显示：它们是 65 个源面文件里剩下的那些，
       逐个都在清单里、逐个都与磁盘上的字节相符 —— 见 §2.4 的实测）…
    "tsconfig.json":           "ad28d132ee48…",
    "tsconfig.node.json":      "a9e6c7f6fd3e…",
    "vite.config.ts":          "fbf87736fc22d371…"
  }
}
```

⚠️ **截断的只是本报告的显示**（65 × 64 位十六进制印全了会把这一节撑成 4 页），
**清单文件里一个都不少**：实测 `sources` = **65** 条、键在文件里**就是字典序**、
值**全是** 64 位小写十六进制、**65/65** 个哈希与 `frontend/` 磁盘上的字节**逐个相符**。

⚠️ 这一份的 `dirty=true` 而 `dirtySources=[]` —— **本波结构上不可能有一次「净构建」**，
理由是一格**循环依赖**：清单是**构建产物**，而守卫（`check:dist` 的 ④d 组、`package.ps1`
的 `$MustContain`）**依赖清单存在** ⇒ 守卫落地的那一刻工作树必然脏（那 5 个未提交的守卫文件）。
⚠️ 而这正是 `dirtySources` 那一格存在的理由：它答的是「**源面**干净吗」，
而源面在 `0dee8a2` 上**一格都不脏**（实测 `git status --porcelain -- <源面 7 个根>` = 空）
⇒ 这份产物**可以由 `0dee8a2` 复现**。`serve.ps1` 与 `check:dist` 都会把这一格**念出来**。

### 2.4 谁写它 —— 三个候选的成本对比（派单 §1 第 2 条点名要说明）

**裁定：`frontend/vite.config.ts` 里的一个内联 vite 插件（`closeBundle` 钩子）。**

| 候选 | 成本 | 判 |
|---|---|---|
| **① vite 内联插件**（选它） | `package.json` 的 `build` 脚本**一个字都不用改**（它今天逐字是 `vue-tsc -b && vite build`，而 README「一条命令跑起来」第 ② 条与说明书 §2 都逐字写着那条命令 ⇒ 改它就是改「一条命令」那一格、两份文档跟着核）；⚠️ 而**任何**一条会跑 `vite build` 的路都自动得到清单（`npm run build` / `serve.ps1` 的 ② / `check-dist.mjs` 自己那一次兜底构建 / 本波做实验用的 `npx vite build --outDir <scratch>`）⇒ **它不可能「构建过了而清单不在」**。⚠️ 零新增依赖（`node:child_process` / `node:crypto` / `node:fs` / `node:path` 全是 Node 自带）。⚠️ 而它只有 `closeBundle` 一个钩子 ⇒ 不参与任何哈希、**不改 bundle 的指纹**（§6 实测：27 个既有产物逐字节未变） | ✅ |
| ② `npm run build` 后面串一步脚本 | 要改 `package.json` 的 `build`（= 改「一条命令跑起来」那一格，说明书与 README 两处跟着核）；⚠️ 而且**串的那一步可以被绕过**（谁直接跑 `vite build` 就没有清单）⇒「清单缺失」会变成常态而不是异常，而「清单缺失」的失效方向是**重建** ⇒ 那一档下每次手跑 `vite build` 之后的第一次 `serve.ps1` 都白重建一次 | ❌ |
| ③ `serve.ps1` 自己在构建之后写 | ⚠️ 只覆盖 `serve.ps1` 这一条路：手跑 `npm run build` 出来的 `dist` **没有**清单；而 `package.ps1` **刻意不构建**、它打的是「**别人**构建出来的那一份」⇒ 甲方那份包**大概率没有清单** ⇒ G22 的另一半（「它是哪一个 commit 构建的」）在**最需要它的那一份产物**上仍然答不出来。⚠️ 另外它要第二次实现「枚举源面 + 算哈希」（PowerShell 一份、Node 一份），而 ① 只需要一份 | ❌ |

⚠️ 一句话：**① 是唯一一个「与构建同生共死」的位置。**

### 2.5 ⚠️ 它进不进 `dist` 的产物计数（派单 §1 第 3 条：先把两个数的关系量清）

**量清了**：`check-dist.mjs` 的 `SCANNED_EXTENSIONS` = `.js .mjs .cjs .css .html .svg .json .map`。
`dist` 改前 **27** 个文件里，**不被计入的那 4 个是 4 个 `.woff2`**（`hanken-grotesk-var-latin{,-ext}` +
`jetbrains-mono-var-latin{,-ext}`，扩展名不在集合里）⇒ **27 = 23 + 4**，与派单给的
「产物侧 23 个 / 596.2 kB」**逐字对上**（实测那一行逐字是
`扫了 23 个文件（596.2 kB），跳过 4 个非文本`）。

**裁定：清单算产物。** 它是一个 `.json` ⇒ 天然落在 `SCANNED_EXTENSIONS` 里，**不需要**为它写一行代码。
⚠️ 而**刻意不给它开一个排除口**：那会是**放宽判据**，而它里面住的是 65 个源面路径与哈希，
正是「产物里不许留下什么」那一族该扫的东西（实测：5 组禁用串在 24 个文件上仍然各 **0** 次）。

⇒ **产物侧 23 → 24 个 / 596.2 → 603.0 kB**；**`dist` 27 → 28 文件 / 708 583 → 715 604 B**。
⚠️ 判据一条都**没放宽**：改前那几条（`扫到的文件数 ≥ 3`、`总字节 ≥ 100 kB`、`woff2 恰好 4 个`、
5 组禁用串各 0 次、`maskFileCalls == scanned.length`）全部逐字保留，
⚠️ 而最后那一条的**计数跟着从 23 变成 24**（它是「本组真的走了几次读盘」的反空转，
所以它必须跟着涨 —— 实测逐字 `计数 24 == 扫到的 24 个文件`）。

### 2.6 `.gitignore` / `.gitattributes` / `package.ps1`（派单 §1 第 4 条）

- ⚠️ **顶回派单的一处事实**：派单说「`.gitattributes` 把 `frontend/dist` 排除在入库之外」。
  **现量核实不是它**：`git check-ignore -v frontend/dist/.build-manifest.json` →
  **`frontend/.gitignore:18:dist/`**。⚠️ `.gitattributes` 只钉**行尾与二进制属性**，不做排除
  （它给 `*.woff2` 钉 `binary`、给两个品牌 svg 与 `.superpowers/**` 钉 `-text`）。
  ⇒ 结论不变（清单**不入库**），但**挡它的是 `.gitignore` 不是 `.gitattributes`**。
- **`package.ps1` 要把它打进包** ⇒ 两件事都做了：
  ① **静态**：`$IncludeRoots` 含 `frontend`、枚举用 `Get-ChildItem -Force`（**含点文件**），
     而两份排除清单（`$ExcludeFileNames` = `.gitignore` / `.gitattributes`；
     `$ExcludeFilePatterns` = `*.pyc` `*.pyo` `*.db` `*.db-journal` `*.db-wal` `*.db-shm`
     `.coverage` `.DS_Store` `Thumbs.db`）**一个都不匹配** `.build-manifest.json` ⇒ 它**本来就**会进包；
  ② ⚠️ **运行时**：往 `$MustContain` 加了 `frontend\dist\.build-manifest.json`（**17 → 18**），
     并在 `backend/tests/test_package.py` 的 `REQUIRED_ENTRIES` 里**独立**加了同一格
     （两侧各自抄一份，漂开时两条守卫一起红）。
- ⚠️ **于是「它真的进了包」是实测过的，不是「留给 Task 4 验」**：`test_package.py` 的 `package`
  fixture 会**真的打一个包**（落到 pytest 的 `tmp_path`，⚠️ 不往 `dist-pack\` 里写）并逐个对账
  ⇒ 本波那次全量 **1784 passed** 里就包含它。⚠️ 本波**没有**往 `dist-pack\` 打任何包
  （那两个既有包 `…20261017-031056.zip` / `…20261019-195539.zip` 一个都没动）。

---

## ③ `serve.ps1` 的新判据

### 3.1 改前 / 改后的判据，逐字

**改前**（`scripts/serve.ps1` 文件头 `.DESCRIPTION` 那一节，`beed5e0` 上逐字）：

```
源面 = ``src/**`` 的全部文件 + ``index.html`` / ``package.json`` /
``vite.config.ts`` / ``tsconfig*.json`` 五个单文件；构建戳 = ``dist\index.html``
的 ``LastWriteTimeUtc``（``npm run build`` 一定会写它）。
**源面里最新的一个 mtime 比构建戳新 → 重建。**
```

代码那一侧（`0dee8a2^` 上逐字，本波整段删掉）：

```powershell
$Stamp = (Get-Item $DistIndex).LastWriteTimeUtc
$Newest = ($Sources | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
…
if ($Newest -gt $Stamp) { $NeedBuild = $true; Write-Host "   源面比构建戳**新** → 要构建" }
else { Write-Host "   dist 不比 src 旧 → 跳过构建" }
```

**改后**（`.DESCRIPTION` 新增那一节的抬头 + 那张六行表；代码那一侧换成一次函数调用）：

```
⚠️ 「dist 是不是由这一份 src 构建的」的判据：**构建清单里的 sha256**
…
今天的判据：**``dist\.build-manifest.json``**。… **本脚本现场枚举源面、逐个算 sha256、
与清单对账**：文件集合与每一个哈希都相符 ⇒ 这份 ``dist`` 就是由这一份 ``src`` 构建的
⇒ **不重建**（⚠️ mtime 一律不看 …）。
```

```powershell
} else {
    # ⚠️ 判据的**唯一所有者**是上面那个函数（逐字口径写在 .DESCRIPTION 的那张表里）。
    $Verdict = Get-BuildManifestVerdict -FrontendDir $Frontend -ManifestPath $ManifestPath -SchemaVersion $ManifestSchemaVersion
    if (-not $Verdict.Fresh) { $NeedBuild = $true; Write-Host ("   ⇒ 要构建（{0}）" -f $Verdict.Reason) }
    else { Write-Host ("   ⇒ 跳过构建（{0}）" -f $Verdict.Reason) }
}
```

⚠️ **判据的唯一所有者落在一处**（派单 §1 第 5 条）：那个函数住在 `serve.ps1` 里、
**只被定义一次、只被调用一次**（守卫按位置钉住那唯一一次调用在 ② 那一段里）。
⚠️ 而「**什么算源**」的唯一所有者是 `frontend/vite.config.ts` 的 `BUILD_MANIFEST_SOURCE_ROOTS`
—— `serve.ps1` 从清单的 `sourceRoots` 那一格**读回来**，⚠️ 改前它自己列的那一份
`$SourceRoots`（7 个字面路径）**整段删掉了**，而守卫反向钉住
「`tsconfig.app.json` / `tsconfig.node.json` / `$SourceRoots` 一个字都不许再出现在代码段里」。

### 3.2 六档失效方向 —— **每一档一次实测的逐字输出**

⚠️ 全部是**跑出来的**：把 `Get-BuildManifestVerdict` 整段切出来（下界是 `serve.ps1` 里
那一行**哨兵注释**），在 `%TEMP%\p09t1\fresh\<case>\` 的**合成树**上真跑
（26 档逐个跑过，⚠️ 一次都没写 `frontend/dist`）。下面挑派单点名的那几档，逐字抄。

**档 1 · 清单缺失 ⇒ 折向重建 + 人话**

```
   构建清单 C:\…\04-manifest-missing\dist\.build-manifest.json **不在**
     ⇒ 这份 dist 说不清它是哪一次构建、由哪一份 src 产出的（无从对账）
     ⇒ 折向**重建**：构建清单不在
       （失效方向与改前的 mtime 判据同一条：宁可多花十几秒重建一次，
        也不把一份说不清出处的产物当成产品档发出去）
   VERDICT FRESH=False REASON=构建清单不在
```

**档 2 · 版本不认 ⇒ 折向重建 + 人话**

```
   构建清单的形状版本是 `2`，而本脚本认的是 `1`
     ⇒ 一份旧清单**不许**被静默当成新版读（将来加字段时把版本号 +1，
        于是旧清单在这一档被认出来、折向重建，而不是被猜着读）
     ⇒ 折向**重建**：构建清单的形状版本不认（2 ≠ 1）
   VERDICT FRESH=False REASON=构建清单的形状版本不认（2 ≠ 1）
```

**档 3 · git sha 对不上 ⇒ ⚠️ 顶回：**不**重建，只印出处**（真仓库上跑的，`HEAD = e9f33f133227…`）

```
   构建清单 ✓：源面 31 个文件的 sha256 与磁盘**逐个相符**
     ⇒ 这份 dist 就是由这一份 src 构建的（⚠️ mtime 一次都没看）
     构建时刻 2026-10-20T10:16:18+08:00（清单里带 UTC 偏移；本仓既有口径 +08:00，而写它的一侧现场取本机偏移）
     出处：commit 000000000000，而 HEAD 是 e9f33f133227 ⇒ 构建之后又有过提交
       ⚠️ 这一格**刻意不折向重建**（顶回，逐字理由见 .DESCRIPTION 那张表的第 4 行）：
          源面 31 个哈希刚刚逐个相符 ⇒ 「dist 是不是由这一份 src 构建的」已经被完整回答；
          而**只改一个文档**的提交也会让 git sha 落后 ⇒ 拿它当新鲜度判据，就是把 G22 那颗
          地雷换个引信重新装上膛（触发条件从「一次批量写回」变成「一次 commit」，形状相同）。
     净构建：构建那一刻整个工作树都是干净的 ⇒ 上面那个 commit sha 足以复现这份产物
   VERDICT FRESH=True REASON=清单与源面 31 个哈希逐个相符
```

**档 4 · 工作树脏 ⇒ ⚠️ 顶回：**不**重建，只印一段 ⚠️**

```
     ⚠️ 这是一次**脏构建**：源面有 2 个文件当时没提交（src/f01.ts、vite.config.ts）
       ⇒ 上面那个 commit sha **不足以复现它**。⚠️ 而这一格也**刻意不折向重建**（顶回，
          逐字理由见 .DESCRIPTION 那张表的第 5 行）：折向重建会**自环** —— 重建之后工作树
          仍然脏（本脚本不清理它），于是每次跑都重建、永远停不下来。
   VERDICT FRESH=True REASON=清单与源面 31 个哈希逐个相符
```

**另外四档（同样各跑过一次，都折向重建、都印了人话）**

| 档 | 逐字那一句（第一行） | `FRESH` |
|---|---|---|
| 清单读不懂 | `构建清单 …\05-bad-json\dist\.build-manifest.json **读不懂**（不是一个合法的 JSON：Invalid object passed in, ':' or '}' expected. (7): { not json）` | `False` |
| 少一格字段（**七个字段各造一次**，7 档） | `构建清单里**没有 \`gitSha\`** 那一格（本脚本认的是这 7 个字段）` | `False` |
| 路径键不稳定（反斜杠 / 绝对路径各一档） | `构建清单里有一个**不稳定**的源面路径：\`src\f01.ts\`` → `⇒ 键必须是**相对 frontend/ 的 posix 路径**（不许绝对路径、不许反斜杠、不许 \`..\`）…` | `False` |
| 哈希形状不对 | `构建清单里 \`src/f01.ts\` 的哈希不是一个 64 位的十六进制串` | `False` |
| `sources` 为空 / `sourceRoots` 为空 / `builtAt` 为空 | `构建清单的 \`sources\` 一格都没有 ⇒ 「空集合 == 空集合」会假绿，本脚本不认` / `…\`sourceRoots\` 一格都没有 ⇒ 本脚本不知道该扫哪些根` / `…\`builtAt\` 是空的（构建时刻那一格不许是空的）` | `False` ×3 |
| 源面被搬空（反空转） | `throw`：`源面只扫到 9 个文件（要 ≥ 20）：… 可能被搬空或路径指错了，本脚本不敢断言 dist 是新的` | **退出码 1** |

⚠️ **每一档都印了人话**（派单 §1 第 6 条：「今天那次误触发的教训是：它重建了，而没人知道为什么」）。
⚠️ 而且**不止印一句**：所有折向重建的档共用一个 `_Fail` 收尾，它**必定**再印两行
（`⇒ 折向**重建**：<理由>` + `（失效方向与改前的 mtime 判据同一条：宁可多花十几秒重建一次，
也不把一份说不清出处的产物当成产品档发出去）`），而守卫对**每一档**都断言这两行在场。

### 3.3 ⚠️ **顶回控制者的倾向 2 处**（派单 §1 第 6 条与 §3 第 ② 点明允许）

控制者倾向「四档一律折向重建」。⚠️ **其中两档不能折**：

**顶回 1 · `gitSha` ≠ HEAD 不该折向重建。** 两条理由：
① 源面那 65 个哈希**刚刚逐个相符** ⇒「dist 是不是由这一份 src 构建的」已经被**完整**回答，
   git sha 在这一格上**没有信息量**（它答的是另一件事：出处）；
② ⚠️ 拿它当**新鲜度**判据 = 一次**只改了文档**的提交也会让下一次产品档跑法**当场重建**
   —— 那是把 G22 那颗地雷**换个引信重新装上膛**（触发条件从「一次与内容无关的批量写回」
   变成「一次与内容无关的 commit」，**形状逐字相同**，而后者比前者**更频繁**）。
⚠️ **本波实测到这一格**：清单是 `0dee8a2` 构建的，而 HEAD 在我提交守卫与文档之后前进到
`af7a424` → `0cc54de` ⇒ 判据仍然答「**不需要构建**」（§4.3 的逐字输出）。
⚠️ 同一条裁定也适用于 `check:dist`（§5.2）。

**顶回 2 · 脏构建不该折向重建。** 一条**决定性**理由：**折向重建会自环** ——
重建之后工作树**仍然脏**（`serve.ps1` 不清理它、也不该清理它），于是**每次跑都重建、
永远停不下来**。⚠️ 而哈希已经忠实记下了「构建那一刻源面长什么样」⇒ 源面再动一个字节，
「内容真的变了」那一档就会抓到。⇒ `dirty` / `dirtySources` 是一格**如实说**的出处信息，
不是一个新鲜度判据。
⚠️ 而「脏构建」这件事**并没有被放过**：`dirtySources` 非空时 `serve.ps1` 印的是一段**响亮的 ⚠️**
（「上面那个 commit sha **不足以复现它**」），`check:dist` 也把它印在「出处」那一行里。

**顺带一格（不是顶回，是补充裁定）· 本机问不到 git。** 甲方 IT 那台机器上大概率没有 git
（`package.ps1` 的目标口径逐字是「只装 Python 就能起一份」）⇒「没有 git」**不许**变成
「必须装 node 才能起」。处置：只跳过**出处**那一格的比对、印一句人话
（`出处：**问不到** —— 构建那台机器上没有 git、或那里不是一个仓库 ⇒ gitSha 是 null`），
⚠️ 而**核心判据一次都不碰 git**（它只用 PowerShell 自己的 `Get-FileHash`）。
⚠️ 实测过这一档（合成树上把三格都设成 `null`）：`FRESH=True`，且印的是
`工作树：构建那台机器上**问不到** git ⇒ 脏不脏未知（⚠️ 不当成「干净」）`，
⚠️ 而**不**印「净构建」（把 `null` 当成 `false` 念就是一句假话）。

### 3.4 `-SkipBuild` 那一档：**改完之后那两句逐字仍然成立**（实测）

产品档 smoke 那一次真的用了 `serve.ps1 -Port 8041 -SkipBuild`，日志逐字：

```
   -SkipBuild：不判新鲜度，直接用现有的 dist（构建戳 10/20/2026 10:59:40）
     （清单说它是 2026-10-20T10:59:40+08:00 由 commit 0dee8a23771d 构建的；⚠️ -SkipBuild 下本脚本**不比**它与源面）
   ⇒ 本次**不需要构建**：本脚本到这一行为止一次都没查 node、一次都没调 npm
```

⚠️ 两句都在，**逐字未变**；⚠️ 多出来的那一行是**新增的出处提示**（只念、不比、不重建）。
⚠️ 而「一次都没查 node、一次都没调 npm」**仍然为真**（⚠️ 并且**一次都没调 git**）：
`-SkipBuild` 那一档**刻意不调** `Get-BuildManifestVerdict`，守卫按**位置**钉住
那唯一一次调用排在 `} elseif ($SkipBuild) {` **之后**；⚠️ 而 `-- ② b  npm run build` 那一段
在整份日志里**一次都没出现**（实测 `'-- ② b' in log` = **False**）。

---

## ④ ⚠️ 本波的核心实测：「源变了但内容没变 ⇒ **不重建**」

### 4.1 合成树上（26 档里的核心两格）

```
########## 02-mtime-only ##########
      [fixture] 4 个 src 文件的 mtime 抬到 2026-10-20 19:32:15；dist/index.html 的构建戳压到 2026-10-19 02:27:05
   |    构建清单 ✓：源面 31 个文件的 sha256 与磁盘**逐个相符**
   |      ⇒ 这份 dist 就是由这一份 src 构建的（⚠️ mtime 一次都没看）
   | VERDICT FRESH=True REASON=清单与源面 31 个哈希逐个相符

########## 03-content-changed ##########
   |    构建清单与现场源面**对不上** ⇒ 这份 dist 不是由这一份 src 构建的
   |      1 个文件的**内容变了**：src/f01.ts
   |      ⇒ 这一档就是「源真的改了」，改前的 mtime 判据在这一档也是重建（缺省行为不变）
   | VERDICT FRESH=False REASON=源面与清单不符：多 0 / 少 0 / 内容变了 1
```

### 4.2 ⚠️ **真树上、真脚本上**（这一格才是派单要的那个「真做出来」）

在**真的** `frontend/` 上，把 G22 那**四个引信文件**的 mtime 逐个抬到 **+9 小时**
（`os.utime`，⚠️ **只动时间戳、一个字节都没改**，实测每个文件改前改后 sha256 相同、
`git status --porcelain` 全程为空）：

```
=== 1. touch the four files of the G22 fuse (mtime ONLY) ===
   src/views/teacher/StudentDetail.vue        mtime 2026-10-19 11:47:20 -> 2026-10-20 20:49:30   sha unchanged = True
   src/views/auth/Bind.vue                    mtime 2026-10-20 09:43:49 -> 2026-10-20 20:49:30   sha unchanged = True
   src/views/admin/ResourceIndex.vue          mtime 2026-10-20 09:43:49 -> 2026-10-20 20:49:30   sha unchanged = True
   src/api/generated/schema.d.ts              mtime 2026-10-19 19:38:12 -> 2026-10-20 20:49:30   sha unchanged = True
   git status --porcelain = ''
    newest src mtime > dist build stamp = True      ← ⚠️ 改前的 mtime 判据在这一档**必然重建**
```

然后跑**真的 `scripts/serve.ps1`、不带 `-SkipBuild`**（端口 8043，`PE_DB_URL` 指到 `%TEMP%` 里
自己灌的库，⚠️ 一次都没碰 `pe_trial.db`）：

```
-- ② 前端构建产物 --
   构建清单 ✓：源面 65 个文件的 sha256 与磁盘**逐个相符**
     ⇒ 这份 dist 就是由这一份 src 构建的（⚠️ mtime 一次都没看）
     构建时刻 2026-10-20T10:59:40+08:00（清单里带 UTC 偏移；本仓既有口径 +08:00，而写它的一侧现场取本机偏移）
     出处：commit 0dee8a23771d，而 HEAD 是 0cc54def915d ⇒ 构建之后又有过提交
     工作树当时有未提交改动，而**源面一格都不脏** ⇒ 这份产物仍然可以由上面那个 commit 复现
   ⇒ 跳过构建（清单与源面 65 个哈希逐个相符）
   ⇒ 本次**不需要构建**：本脚本到这一行为止一次都没查 node、一次都没调 npm
```

⚠️ 服务照常起来了（`GET /api/health` → **200** `{"status":"ok","tables":30,"students":0,"trial":false}`，
8.2 s），⚠️ 而 `-- ② b  npm run build` 那一段在整份日志里**一次都没出现**
（实测 `'-- ② b' in log` = **False**）。
⚠️ 如实记一处**看起来像反例、其实不是**的：日志里 `'npm run build'` 这个串**出现了** ——
那是 ⑤ 那一段印给人看的散文（「前端跑的是 npm run build 出来的静态文件」）与
我新加的那一行（「改一行 src\ 要重跑本脚本…」），是**提及**、不是**调用**（硬规矩 #109）；
「真的构建过没有」的判据是 `-- ② b` 那一段在不在，它**不在**。

### 4.3 「源内容真的变了 ⇒ 重建」——同样在真树上

改 `frontend/src/brand.ts` **一个字节**（追加 `\n// p09t1 one byte`），
⚠️ 只跑那个**判据函数**（不跑整个 `serve.ps1`，于是它**不会**真的构建）：

```
=== 4. one byte of a real src file changed -> must say rebuild ===
   target = src/brand.ts   sha 49C960A4EECE9CE6 -> FCA0BF9BCA3066B5
   |    构建清单与现场源面**对不上** ⇒ 这份 dist 不是由这一份 src 构建的
   |      1 个文件的**内容变了**：src/brand.ts
   |      ⇒ 这一档就是「源真的改了」，改前的 mtime 判据在这一档也是重建（缺省行为不变）
   | FRESH=False|REASON=源面与清单不符：多 0 / 少 0 / 内容变了 1
   restore: sha 49C960A4EECE9CE6  逐字节还原 = True
   git status --porcelain = ''
   复绿: rc=0 FRESH=True
```

⚠️ **逐字节还原**（sha256 `49C960A4EECE9CE6` 改前 == 还原后，⚠️ **不靠 `git checkout`**），
`git status --porcelain` 复验为空，判据复绿。

### 4.4 ⚠️ 结论：**G22 那颗地雷今天拆了**

判据是派单给的那一句：「**一次与内容无关的批量写回还能不能触发重建**」。
答案：**不能**了 —— 而这一格是**在真树、真脚本、真端口上跑出来的**，不是读代码读出来的。

---

## ⑤ 守卫清单 + 8 格变异取证

### 5.1 守卫清单

**`backend/tests/test_serve.py` 新增 9 条**（后端 **1775 → 1784**）。
⚠️ 其中 **5** 条是把判据函数**整段切出来、在合成树上真跑**（硬规矩 #89）：

| 条 | 它钉的是 | 拍数 |
|---|---|---|
| `test_the_freshness_judgment_is_the_build_manifest_and_not_the_mtime` | 判据只有一处调用且在 ② 里 · ⚠️ **② 那一段里 `LastWriteTimeUtc` 0 次、`LastWriteTime` 恰好 1 次**（那一次是 `-SkipBuild` 那一行**打印**构建戳，不是判据）· `Measure-Object` / `$Newest` / `$Stamp` 一个都不许留 · `Get-FileHash`+`SHA256`+`ToLowerInvariant` 在场 · `-SkipBuild` 那一档**不调**判据函数（位置判据）· ⚠️ 源面的根**一个都不许**抄第二份 · `$NeedBuild = $true` 仍恰好 2 处 | 6 |
| `test_a_source_whose_mtime_moved_but_whose_content_did_not_does_not_trigger_a_rebuild` | ⚠️ **本波的全部意义**（含夹具自校：mtime 确实被抬了、内容确实没变） | 3 |
| `test_a_source_whose_content_really_changed_does_trigger_a_rebuild` | 上一条的**反空转**：改一个字节 / 加一个文件 / 删一个文件 ⇒ 三档都 `FRESH=False` 且**点名**是哪一个 | 3 |
| `test_the_manifest_failure_directions_fold_to_a_rebuild_and_each_prints_why` | **十档**（清单不在 / 读不懂 / 版本不认 / 七个字段各少一格 / `sources` 空 / `sourceRoots` 空 / `builtAt` 空 / 反斜杠键 / 绝对路径键 / 哈希形状不对）⇒ 每档 `FRESH=False` **且** stdout 里有「折向**重建**」+ 那一档自己的关键词 | 16 |
| `test_a_null_git_sha_is_legal_and_is_not_read_as_clean` | `null` 三格合法；⚠️ 而「问不到」不许被念成「净构建」 | 4 |
| `test_a_lagging_git_sha_or_a_dirty_build_is_reported_but_does_not_force_a_rebuild` | ⚠️ **顶回那两格**的可执行形式（起一个**真的** git 仓库）；⚠️ 含**对照拍**（`gitSha == HEAD` 时印的是另一句 ⇒ 上一句不是恒真） | 8 |
| `test_the_anti_idle_guard_still_throws_when_the_source_surface_is_gutted` | 源面被搬空到 20 个以下 ⇒ **退出码非 0** + 那一句人话在 stderr | 3 |
| `test_the_build_manifest_contract_is_the_same_text_in_all_three_owners` | 文件名三处 · 形状版本**四处**（三个住址 + 形参缺省值）· 七个字段名三处各自全部在场 · ⚠️ **③b** `vite.config.ts` 的清单**对象字面量**里七格逐个在场 · `serve.ps1` 与 `check-dist.mjs` 那两份**有序清单**逐项相同 · 源面 7 个根的取值相同 · 反空转（三个文件都真的读到了） | 5 |
| `test_the_build_manifest_is_gitignored_but_packed` | ① 它**不入库**（`git check-ignore` 实测）；② 它**进包**（`$MustContain` 里有它，而两份排除清单都不匹配这个名字） | 3 |

**`frontend/scripts/check-dist.mjs` 新增 ④d 一组（14 条断言）**：清单在场 / 七个字段各一条 /
形状版本 / `builtAt` 带显式 UTC 偏移（正则钉） / `gitSha` 40-hex 或 null / `dirty` bool 或 null /
`dirtySources` 字符串数组或 null / `sourceRoots` 非空 / 65 个路径全是稳定 posix 相对路径 /
65 个哈希全是 64 位小写十六进制 / ⚠️ **本组的牙**（清单**逐个**描述了磁盘上这一份源面）
/ 外加两行「出处」的**报告**（不是断言）。

**`scripts/package.ps1` + `backend/tests/test_package.py`**：`$MustContain` **17 → 18**、
`REQUIRED_ENTRIES` **独立**加同一格、`MUST_CONTAIN_ITEMS` 跟着抬到 **18**。

### 5.2 ⚠️ `check:dist` **该不该**加「清单里的 gitSha 必须等于 HEAD」那一组（派单 §1 第 10 条）

**裁定：不加。** 两条理由（⚠️ 逐字写在那一组的代码注释里，取证住址在那里）：
① 它会让「**构建之后又提交了一次文档**」变成红 —— 而文档提交不改源面 ⇒ 那 65 个哈希
   **仍然逐个相符**，红的只有 git sha 这一格。那是一个**假红**，而下一个人唯一的出路
   就是把断言删掉（硬规矩 #109）。⚠️ 控制者的提示是对的：**这一组大概率是错的判据**，
   我核过之后同意；
② ⚠️ 更要紧的是同一条裁定在 `serve.ps1` 那一侧的后果（§3.3 顶回 1）：拿 git sha 当
   **新鲜度**判据 = 把 G22 那颗地雷换个引信重新装上膛。
⇒ git sha 在 `check:dist` 里只**报**（那两行「出处」），不**判**。
⚠️ 而 `check:dist` **确实加了一组**（④d 的 14 条），加的是**内容对账**那一格
—— 它把「产物是不是由这一份 src 构建的」变成**静态可查**，`--no-build` 也咬得到。

### 5.3 定点变异 **8 格**（派单要 ≥5；每格：改 → 跑 → **必须红** → **逐字节还原**（sha 对账，⚠️ 不靠 `git checkout`）→ `git status` 复验 → 复绿）

| # | 变异 | 改的是哪个文件 | 红在哪一条 | 还原 sha256[:16] 对账 | 复绿 |
|---|---|---|---|---|---|
| **M1** | ⚠️ **把判据改回 mtime**：函数里两处 `Get-FileHash … SHA256` 换成 `LastWriteTimeUtc.Ticks` | `scripts/serve.ps1` | `test_the_freshness_judgment_is_the_build_manifest_and_not_the_mtime` · `test_a_source_whose_mtime_moved_but_whose_content_did_not_does_not_trigger_a_rebuild` · `test_a_null_git_sha_is_legal_and_is_not_read_as_clean` · `test_a_lagging_git_sha_or_a_dirty_build…` · `test_serve_ps1_runs_the_five_documented_steps_in_order`（**5 条红**） | `99E6B8DDDE6254B5` → **`8C489D26F443D349`** ✅ | ✅ 51 passed |
| **M2** | ⚠️ **把 git sha 那一格从清单里去掉**：删掉 `gitSha: git.gitSha,` | `frontend/vite.config.ts` | `test_the_build_manifest_contract_is_the_same_text_in_all_three_owners`（**③b 那一拍**） | `919182B720DC1156` → **`FBF87736FC22D371`** ✅ | ✅ |
| **M3** | ⚠️ **把「脏不脏」那一格去掉**：删掉 `dirty: git.dirty,` | `frontend/vite.config.ts` | 同上（**③b**） | `53335A86AFB81781` → **`FBF87736FC22D371`** ✅ | ✅ |
| **M4** | ⚠️ **把「清单缺失」那一档改成静默不重建**：整个 `if (-not (Test-Path …))` 块换成 `return @{ Fresh = $true; … }` | `scripts/serve.ps1` | `test_the_manifest_failure_directions_fold_to_a_rebuild_and_each_prints_why` | `C6344B60D79987F3` → **`8C489D26F443D349`** ✅ | ✅ |
| **M5** | ⚠️ **把版本号那一格去掉**：`if ($Version -ne [string]$SchemaVersion)` → `if ($false -and …)` | `scripts/serve.ps1` | 同上 | `0EE2A682466A4669` → **`8C489D26F443D349`** ✅ | ✅ |
| **M6** | 读它的那一侧**字段清单少一格**：`foreach ($Field in @(…))` 里删掉 `'dirty'` | `scripts/serve.ps1` | `test_the_build_manifest_contract…`（有序清单逐项比对）+ `test_the_manifest_failure_directions…`（**2 条红**） | `F06ADC41F2C20378` → **`8C489D26F443D349`** ✅ | ✅ |
| **M7** | **源面的根抄第二份**：在函数里硬写一行 `$Roots = @("src", …7 个…)` | `scripts/serve.ps1` | `test_the_freshness_judgment_is_the_build_manifest_and_not_the_mtime`（**第 ⑤ 拍**） | `0E7FB5AD1882D05F` → **`8C489D26F443D349`** ✅ | ✅ |
| **M8** | ⚠️ **`check:dist` 那一组的牙被放宽**：`added/gone/changed === 0` → `>= 0` | `frontend/scripts/check-dist.mjs` | **staged 负控**（在 `%TEMP%` 里抄一棵 `frontend` + **真** `dist` + **真**清单，改 `src/App.vue` 一个字节）：基线 = 原样 **rc 0** / 负控 **rc 1** 且点名 `src/App.vue`；变异后 = 负控 **rc 0**（**牙被拔了**）⇒ 抓到 | `39F0D29DA958A457` → **`2A947727820A4B13`** ✅ | ✅ 原样 rc 0 / 负控 rc 1 |

⚠️ **8/8 全部：红了 → 逐字节还原（sha256 与改前**逐字相同**）→ `git status --porcelain`
复验只有本波那 7 个待提交文件（`git status` 那 7 项一个不多一个不少）→ 复绿。**
⚠️ **两侧不同源**：M1/M4/M5/M6/M7 的红是**跑 PowerShell** 跑出来的（期望侧是 Python 的
`hashlib` 与本文件里抄下来的字面量，被测侧是 `serve.ps1` 自己那段 `Get-FileHash`）；
M2/M3 的红是**三个住址的字面量互相对账**；M8 的红是 `check-dist.mjs` 自己的**正/负控对**。

---

## ⑥ 那一次真构建

### 6.1 之前：所有实验性构建一律 scratch outDir（⚠️ 一次都没写 `frontend/dist`）

```
cd frontend; npx vite build --outDir "$env:TEMP\p09t1\scratch1" --emptyOutDir
✓ 141 modules transformed.  ✓ built in 495ms
[build-manifest] C:\Users\whwenhao\AppData\Local\Temp\p09t1\scratch1\.build-manifest.json
                 源面 65 个文件的 sha256 · 2026-10-20T10:16:18+08:00 · beed5e0724cd（⚠️ 脏构建）
```

对账（scratch vs 当时的 `frontend/dist`）：`dist 27 文件 / 708 583 B` · `scratch 28 文件 / 715 628 B` ·
`only in scratch = ['.build-manifest.json']` · **`common=27 identical=27 differing=0`**
⇒ **插件不改 bundle 的指纹**（它只有 `closeBundle` 一个钩子，不参与任何哈希）。

### 6.2 ⚠️ 最后一次 `npm run build`（写进 `frontend/dist`）—— 本波**只跑了这一次**

跑之前先把旧 `dist` 的 **27 个文件逐个 sha256 记下来**（`%TEMP%\p09t1\dist_before.json`）：

```
cd frontend; npm run build
✓ 141 modules transformed.  ✓ built in 428ms
[build-manifest] …\frontend\dist\.build-manifest.json
                 源面 65 个文件的 sha256 · 2026-10-20T10:59:40+08:00 · 0dee8a23771d（⚠️ 脏构建）
```

### 6.3 跑之后逐个对比

| 格 | 旧 | 新 |
|---|---|---|
| 文件数 | **27** | **28** |
| 总字节 | **708 583** | **715 604** |
| `only in BEFORE`（消失的） | — | **0 个** |
| `only in AFTER`（新增的） | — | **1 个 = `.build-manifest.json`** |
| 共有文件 | 27 | **`identical=27` / `differing=0`** |

⚠️ **派单期望的是「26 个逐字未变 + 新增 1 个清单」，实测是「27 个逐字未变 + 新增 1 个清单」**
（比期望还多一个未变的）。⚠️ 那 27 个**逐个**都对过 sha256，包括：

| 文件 | 字节 | sha256[:16] | 变了吗 |
|---|---|---|---|
| `index.html` | 2 567 | **`7EF16470CD6CE9BB`** | ❌ **逐字未变** |
| `assets/index-DG9aiaVT.js` | 252 261 | `A4D69E154A97886D` | ❌ 未变 |
| `assets/index-D_BSV8Ho.css` | 66 664 | `741C8D1CEC8A4084` | ❌ 未变 |
| 其余 24 个（含 4 个 woff2、2 个品牌 svg、18 个懒加载 chunk） | — | — | ❌ 全部未变 |
| `.build-manifest.json` | **7 021** | **`B5138B8127DA29E4`** | ✅ **新增** |

⚠️⚠️ **bundle 哈希一个都没变**（`index-DG9aiaVT.js` / `index-D_BSV8Ho.css` 与 18 个懒加载
chunk 的**文件名**逐字相同）⇒ **甲方已打开的页面去懒加载旧 chunk 不会 404**
（那是 Plan 08 Task 4 亲历过的那个形状；本波**没有**造成它）。
⚠️ 只有 27 个文件的 **mtime** 从 `2026-10-19 02:27:05` 变成 **`2026-10-20 10:59:40`**
—— 而 mtime 从本波起**不再是任何判据**。

**构建时刻 = 2026-10-20 10:59:40（+08:00）**；清单记的 `gitSha` = **`0dee8a2`**（= commit ②），
`dirty = true` 而 `dirtySources = []`（⚠️ 结构上不可能有净构建，理由见 §2.3）。

⚠️ **如实报一格**：本波**只在 §6.1 与 §6.2 各跑过一次 `vite build`**，其中**只有 §6.2 那一次
写进了 `frontend/dist`**（派单逐字允许「`npm run build` 只能跑一次」，而 §6.1 那一次是
`npx vite build --outDir <scratch>`、⚠️ 一次都没写 `frontend/dist`）。
⚠️ 我**没有**为了验任何东西而先写一次 `frontend/dist`（§3.2 / §4 的全部实测都在
`%TEMP%` 的合成树上、或用 `-FrontendDir`/`-ManifestPath` **形参**指向别处）。

---

## ⑦ 构建之后立刻跑的那些（逐格）

| 格 | 命令 | 结果 |
|---|---|---|
| `check:dist` | `npm run check:dist -- --no-build` | ✅ **退出码 0**、全绿。`扫了 **24** 个文件（**603.0 kB**），跳过 **4** 个非文本`（改前 23 / 596.2 kB / 4）；5 组禁用串各 **0** 次（`adoptFromUrl` · `fonts.googleapis.com` · `fonts.gstatic.com` · `****-**-**` · 5 条「会变假的渲染正文」）；`maskFileCalls 计数 **24** == 扫到的 **24** 个文件`；woff2 恰好 **4** 个 / 97 348 B；④d 一组 **14 条全绿**，含牙那一行 `清单**逐个**描述了磁盘上这一份源面（多 0 / 少 0 / 内容变了 0） → 65 个文件逐个相符`；出处两行 `构建时刻 2026-10-20T10:59:40+08:00 · commit 0dee8a23771d…` / `工作树：⚠️ 工作树当时有未提交改动，而源面一格都不脏 ⇒ 仍然可复现`；源码侧 `扫了 56 个文件 / 1440078 字符`（⚠️ 派单交代过这一格会随 `schema.d.ts` 的工作树行尾漂 11 127，本波实测**没漂**，因为开工时它是 CRLF 而本波没跑 `gen:api` 改写它 —— 跑了，见下面那一行，⚠️ 而跑完**逐字节还原**了） |
| `check:tokens` | `npm run check:tokens` | ✅ **退出码 0**、`扫描面 **36** 个文件（下界 25）`、`全绿：36 个文件里，tokens.css 之外一个色值字面量都没有` |
| **三档 smoke** | 见下 | ✅ **三档各 18/18 步全绿、退出码 0** |
| 后端全量 | `python -m pytest --no-cov -q` | ✅ **1784 passed**（基线 **1775** ⇒ **+9** = 本波新增的 9 条守卫），270.62 s |
| 覆盖率三口径四格 | `--cov=app.domain` / `--cov=app` / `--cov=scripts --cov=app.static` / 再各一次带 `--cov-branch` | ✅ **四格逐字未变**（见 §10） |
| `gen:api` ×2 | `npm run gen:api` 连跑两次 | ✅ **两次 `git diff` 都为空**；⚠️ 但**字节会变**（见下面 ⑦.1） |
| `alembic heads` | `python -m alembic heads`（`PE_DB_URL` 指到 `%TEMP%` 里的探针库） | ✅ **`a1af54889103 (head)`** —— **单头**；`alembic history` = **6** 个 revision |
| `alembic check` | 同上 | ✅ **`No new upgrade operations detected.` / 退出码 0** ⇒ **残差 diff = 0** |
| 表数 | 探针库的 `sqlite_master` | ✅ `type='table'` = **31**（30 张业务表 + `alembic_version`）⇒ **表数仍 30** |
| openapi | `python backend/scripts/dump_openapi.py` | ✅ **455 301 B / sha256[:16] `7D75650765F2B65D`**、**77 路径 / 106 操作 / 挂 security 87 / GET 65 / securitySchemes 3** ⇒ **逐字未变**（本波后端产品代码一行都没动，`git diff 42dc849 HEAD -- backend/app backend/scripts` **为空**，实测复核过） |

### 7.1 三档 smoke（⚠️ 一律 `-SkipBuild`；⚠️ **公网档不跑**）

| 档 | 怎么起的（⚠️ 全是**我自己的**实例，端口 8040+） | 步数 | 断言 | 退出码 | 用时 |
|---|---|---|---|---|---|
| **dev** | `backend\scripts\demo.ps1 -Port 8040`（灌 `backend\pe_demo.db` + 起服务）+ `npm run dev -- --port 5174 --strictPort`（`PE_API_TARGET=http://127.0.0.1:8040`）；`PE_API_BASE=http://127.0.0.1:8040` `PE_WEB_BASE=http://localhost:5174` | **18/18** | **819 绿 / 0 红** | **0** | 90.3 s |
| **产品档** | 先 `demo.ps1 -Port 8040` 重灌一份干净的库并停掉，再 `scripts\serve.ps1 -Port 8041 **-SkipBuild**`；`PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8041` | **18/18** | **819 绿 / 0 红** | **0** | 88.5 s |
| **试用档** | `$env:PE_DB_URL=sqlite:///%TEMP%/p09t1/pe_trial_probe.db` + `scripts\trial.ps1 -Port 8042 -Reset -Force`（缺省透传 `-SkipBuild`）；`PE_TRIAL=1` | **18/18** | **851 绿 / 0 红** | **0** | 86.3 s |
| **公网档** | ⚠️ **不跑**（派单逐字要求；终审裁定「删数不复述」，而量它要 `-Reset`、甲方那份库不许 `-Reset`） | — | — | — | — |

⇒ **819 / 819 / 851 与基线逐字相同**（一个都没减，也没有新增 —— 本波没有改任何产品面行为）。
⚠️ **`5173` 一次都没碰**（它在开工时就已经死了；我起的是 **5174**）。

### 7.2 ⚠️ `gen:api` 的一格如实记（它是本波新判据下**唯一**剩下的「内容无关」引信）

`npm run gen:api` 连跑两次，**两次 `git diff --stat -- frontend/src/api/generated/schema.d.ts` 都为空** ✅
（派单要的那一格成立）。⚠️ 但**工作树字节会变**：

| 时点 | 字节 | LF | CRLF | sha256[:16] |
|---|---|---|---|---|
| 跑之前（`autocrlf` checkout 出来的形状） | **574 499** | 11 127 | **11 127** | `FA7EBE734BBD1182` |
| 第 1 次 `gen:api` 之后 | **563 372** | 11 127 | **0** | `2166B3426E9A01F6` |
| 第 2 次 `gen:api` 之后 | **563 372** | 11 127 | **0** | `2166B3426E9A01F6`（逐字节相同 ⇒ 生成器是稳定的） |
| ⚠️ 逐字节还原之后 | **574 499** | 11 127 | 11 127 | **`FA7EBE734BBD1182`**（== 跑之前 ✅） |

差值恰好 **11 127** = 行数（spec §13.27.9.9 登记过的那一格特例：工具写 **LF**、
`autocrlf` checkout 成 **CRLF**，两份 `hash-object` 成同一个 blob `41437e22…` ⇒ **可逆成立**）。

⚠️ **后果如实说**：清单哈希的是**工作树上的字节**，故一次 `gen:api` 会把 `schema.d.ts` 从
CRLF 改写成 LF ⇒ **清单对不上 ⇒ 折向一次重建**。⚠️ 三格如实记：
① 这一档比改前的 mtime 引信**窄得多**（它只在文件字节**真的**变了时才响，而 mtime 是
   **碰一下就响**），且折向**安全**的那一侧；
② ⚠️ 连带一格：`gen:api` 之后 `git status --porcelain` 会把 `schema.d.ts` 报成 ` M`
   （而 `git diff` 是空的）⇒ 那一刻若构建，清单会记下 `dirty=true` 且
   `dirtySources=["src/api/generated/schema.d.ts"]`，⚠️ 而它的 **blob 其实一个字节都没变**
   （一格**假阳性**的「脏源面」；如实报，不掩盖）；
③ **长期解**是给那一个文件在 `.gitattributes` 上钉 `-text`（工具写什么就 checkout 什么），
   ⚠️ 而本波**一个字都不许改** `.gitattributes` ⇒ **没做**，报成 **G25 候选**（§9）。
⚠️ 而本波**没有**把清单留在对不上的状态：跑完 `gen:api` 之后**逐字节还原**了那个文件
（sha256 对账 `FA7EBE734BBD1182`，⚠️ **不靠 `git checkout`**），`git status --porcelain` 复验为空，
⚠️ 并复跑了 `check:dist --no-build`（牙那一行仍是「65 个文件逐个相符」）与判据函数（`FRESH=True`）。

---

## ⑧ 文档

### 8.1 改了哪几处

| 文件 | 改了什么 |
|---|---|
| `frontend/vite.config.ts` | 新增那个内联插件 + 一整段「为什么住在这里」的三候选成本对比（**68 → 299** 行） |
| `scripts/serve.ps1` | `.DESCRIPTION` 里「mtime 判据」那一节**整段换成**「构建清单判据」+ 一张**六行失效方向表**；`.PARAMETER SkipBuild` 补「本波之后这一档一格都没变、而它仍然是活服务机器上的正确姿势（理由换了）」；新增 `$ManifestName` / `$ManifestPath` / `$ManifestSchemaVersion` 三个变量 + `Get-BuildManifestVerdict` 一个函数 + 一行**哨兵注释**（切片下界）；② 那一段的 mtime 判据整段删掉、换成一次函数调用；`-SkipBuild` 那一档新增一行**出处提示**；⑤ 那一段的散文跟着改对（**639 → 862** 行） |
| `frontend/scripts/smoke.mjs` | ⚠️ **派单点名要改的那张「三档怎么跑」的表**：产品档那一格加了 `-SkipBuild` 的提示；表下面新增一段 ⚠️⚠️「产品档那一格为什么写了 `-SkipBuild`」（含「口径松了一半」的交代）；另改**两处**描述判据的散文（前置条件 §D7 那一段与第 14 步里那一段）。⚠️ 顺带修一处**既有的数目错误**：改前两处都写「5 个配置文件」，而单文件其实是 **6** 个（59 + 6 = **65**）（**6382 → 6398** 行） |
| `frontend/scripts/check-dist.mjs` | 新增 `node:crypto` 的 import、`BUILD_MANIFEST_*` 五个常量 + `sha256Of()`、**④d 一组（14 条断言 + 2 行出处报告）**、收尾那一句「全绿」补上清单那一格（**542 → 682** 行） |
| `scripts/package.ps1` | `$MustContain` **17 → 18**（加 `frontend\dist\.build-manifest.json` + 一段「为什么它本来就会进包、而本行钉的是另一件事」）；文件头「保留真实时间戳」那一段**改对**（改前逐字写着「`serve.ps1` 判『要不要重建』读的正是那两个 mtime」⇒ 今天会变成假话）（**678 → 693** 行） |
| `scripts/trial.ps1` | **两处**散文里的「照它自己那套 **mtime** 判据」改对（`.DESCRIPTION` 与 `.PARAMETER Build`）（**551 → 554** 行） |
| `backend/tests/test_serve.py` | 既有的那一行 `assert "LastWriteTimeUtc" in code`（「比 src 旧」的判据）改成钉**新**判据 + 一段交代；新增 ⑨ 一整节（9 条守卫 + 8 个 helper/常量）（**2323 → 2953** 行） |
| `backend/tests/test_package.py` | `REQUIRED_ENTRIES` 加一格、`MUST_CONTAIN_ITEMS` **17 → 18**（**630 → 637** 行） |
| `README.md` | ⚠️ **三处**（见 8.3）（**243 → 258** 行） |
| `Document/…设计spec.md` | ⚠️ **两处**（见 8.4）（**10 700 → 10 775** 行） |

### 8.2 ⚠️ `package.json` 的 `build` 脚本：**一个字都没改**

它今天仍然逐字是 **`vue-tsc -b && vite build`**。
⇒ README「一条命令跑起来」第 ② 条与说明书 §2 那两处逐字写着它的地方**不需要跟着核**
（⚠️ 我仍然核了：README 那一处逐字仍是 `powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Port 8020 -SkipBuild`，
说明书 §2 那一条命令也一个字没动）。
⚠️ 而这正是 §2.4 选「vite 内联插件」的**第一条理由**：候选 ② 会逼着改这一格。
⚠️ 另外 `frontend/package.json` 的 `dependencies`（3 项）与 `devDependencies`（7 项）
**一个都没加**（新增依赖：前端 **0**、后端 **0**）。

### 8.3 ⚠️ README 与 §13.15 第 1 条那三处「一律 `-SkipBuild`」的口径：**松了一半**（附实测支撑）

| 那一半 | 处置 | ⚠️ 实测支撑（派单逐字要求「松口径必须有实测支撑」） |
|---|---|---|
| 「**mtime 会误触发** ⇒ 一律带 `-SkipBuild`」 | ⚠️ **退休** | ① **合成树**：4 个源文件 mtime 抬到 **+9 h**、`dist/index.html` 构建戳压回 `2026-10-19 02:27:05` ⇒ `FRESH=True`「源面 31 个文件的 sha256 与磁盘**逐个相符**（⚠️ mtime 一次都没看）」；② **真树 + 真脚本**：把 G22 那**四个引信文件**的 mtime 逐个抬到 `2026-10-20 20:49:30`（比构建戳新 9 h 50 m，`git status` 全程为空）⇒ 真的 `serve.ps1`**不带** `-SkipBuild` 跑出「`⇒ 跳过构建（清单与源面 65 个哈希逐个相符）`」+「`⇒ 本次**不需要构建**：…一次都没查 node、一次都没调 npm`」，`-- ② b` 一次都没出现，服务照常 200 / `tables:30`（§4.2 的逐字输出）；③ **反向**：改 `src/brand.ts` 一个字节 ⇒ 当场 `FRESH=False` 并点名是哪一个（§4.3） |
| 「**重建要排一次真窗口**」 | ⚠️ **留着** | `serve.ps1` **按请求从磁盘读 `dist`** ⇒ 源**真的**改了时它仍然会当场 `npm run build`，把已打开页面的懒加载 chunk 换掉（404）⇒ 活服务机器上仍然一律带 `-SkipBuild`。⚠️ 而这一格今天**由 ③ 那一次实测反向支撑**：它证明了「内容变了 ⇒ 重建」仍然为真 ⇒ 纪律不能整条撤掉 |

**改的三处**（README 两处 + spec §13.15 第 1 条；⚠️ 历史原文一律逐字保留）：
① README「一条命令跑起来」第 ② 条 —— 那一段散文改成一张**三行对照表**
   （判据 / 为什么要带 `-SkipBuild` / 不变的那一半），并补一格新能力（清单里记着
   git sha、构建时刻与工作树脏不脏 ⇒「这份产物是哪一个 commit 构建的」可查）；
   ⚠️ 也如实交代「`touch dist\index.html` 去骗它」那一招今天**已经不管用**了；
② README「试用包」那一段 —— 补一句「包里那份清单会告诉你它是哪一个 commit 构建的；
   ⚠️ 包里没有 `.git`，故那一台机器上 `serve.ps1` 只**念**这一格、比不了 HEAD，
   而它的核心判据一次都不碰 git」；
③ README `PE_ALLOW_SELF_BIND` 那一段的命令注释 —— 理由从「不带它会顺带重建」改成
   「不带它、**又恰好改过 `frontend\src`** 的话会顺带重建」；
④ spec **§13.15 第 1 条**「本波复核」那一格 —— 追加 Plan 09 Task 1 的处置
   （含六档失效方向的一句话摘要 + 顶回两格 + 取证住址）。

### 8.4 ⚠️ **G22 在 spec 里怎么处置**

住在 **§15 G22** 那一条的**末尾**，在既有那段「**怎么做**（若将来要改）」之后**追加九格**
（清单的七个字段 / 谁写它与三个候选的成本对比 / 判据的唯一所有者 / 六档失效方向 /
⚠️ **顶回两格**及其理由 / `-SkipBuild` 一格没变 / 守卫 / 产物计数 / ⚠️ **两格如实记的残余**）。
⚠️ **本条的划掉（`~~G22~~`）留到结案波**（Task 6，派单逐字要求）；⚠️ 而 G22 那段
**历史取证原文一个字都没重写**（它记的是 2026-10-19 的实物，绑时点的账不重写）。

### 8.5 ⚠️ 说明书 **179 行有没有变**：**没有**

现量核实：`Document/2026-10-15-甲方试用说明书.md` 里 `SkipBuild` / `mtime` / `npm run build` /
`重建` **0 命中** ⇒ 本波**一个字都没改它**，它仍是 **37 123 B / 179 行**（上限 **200**）、
sha256[:16] `46E105CDB93D524B`（与开工逐字相同）。
⚠️ 计划 09 文档同样一个字没改（**14 027 B / 71 行 / `F018251500F294F3`**）。

---

## ⑨ 待清扫 / 关切 / 没按派单做的 / ⚠️ 顶回

### 9.1 ⚠️ 顶回（累计 **259 → 265**，本波 **+6**；⚠️ 其中 **1** 处 Critical）

| # | 顶回的是 | 我的裁定 | 级别 |
|---|---|---|---|
| **1** | 派单 §1 第 6 条「控制者倾向：四档一律折向重建」里的**「git sha 对不上」那一档** | **不折向重建**，只印出处。⚠️ 折了就是把 G22 换个引信重新装上膛（一次**文档提交**就会当着甲方的面重建前端，而那个触发条件比原来**更频繁**）；⚠️ 而内容哈希已经**完整**回答了新鲜度那一问 ⇒ git sha 在这一格上没有信息量。**实测支撑**：§4.2 那一次真跑，清单在 `0dee8a2`、HEAD 在 `0cc54de`，判据仍答「不需要构建」 | ⚠️ **Critical** |
| **2** | 同一格里的**「工作树脏」那一档** | **不折向重建**，只印一段 ⚠️。⚠️ 折了会**自环**（重建之后工作树仍然脏，于是每次跑都重建、永远停不下来）；⚠️ 而 `dirtySources` 已经把「能不能由那个 commit 复现」说清了 | 高 |
| **3** | 派单 §1 第 10 条「`check:dist` 要不要加『git sha == HEAD』那一组」 | **不加**（控制者已提示它大概率是错判据，⚠️ 我核过之后**同意**，理由两条逐字写进那一组的代码注释）。⚠️ 而 `check:dist` **确实加了**一组（④d 的 14 条），加的是**内容对账** | 中 |
| **4** | 派单 §1 第 4 条「`.gitattributes` 把 `frontend/dist` 排除在入库之外（⚠️ 现量核实）」 | ⚠️ **现量核实的结果与派单不符**：挡它的是 **`frontend/.gitignore:18` 的 `dist/`**（`git check-ignore -v` 实测），⚠️ **不是** `.gitattributes`（那一份只钉行尾与二进制属性，不做排除）。⇒ 结论不变（清单不入库），但**住址要改对** | 低 |
| **5** | 派单 §1 第 1 条「`src` 那 **65** 个文件」 | ⚠️ **65 不是 `src` 的数，是「源面」的数**：`frontend/src` 实测 **59** 个（`git ls-files` 与磁盘两侧相同），源面 = 59 + **6** 个单文件 = **65**。⚠️ 而 `smoke.mjs` 与 `serve.ps1` 改前都把那 6 个写成「**5** 个配置文件」⇒ 本波把 `smoke.mjs` 那两处改对了；⚠️ spec §15 G22 的那一句是**历史取证原文**、按体例不重写 | 低 |
| **6** | 派单基线里「README **15 478 B / 208 行**」 | ⚠️ **复现不出来**：`main` = `42dc849` 上实测 **19 070 B / 243 行**，而开工时 `git status --porcelain` 为空 ⇒ 不是本波之前的谁改的。⚠️ 我**没有**去动它，只如实记（处置同 spec §13.15 第 8 条那格「`108 B` 复现不出来」） | 低 |

### 9.2 关切（⚠️ 建议登记进 §15，编号**先现量核过**：G 组今天最大号是 **G23** ⇒ 下面用 **G24 / G25**）

- **G24 候选 · 源面不含 `package-lock.json`**：一次只改锁文件的 `npm install`，
  **mtime 判据与内容判据都看不出来**（改前也不含 ⇒ 不是本波引入的）。
  ⚠️ 本波**刻意不扩面**：`65` 这个数被 spec §15 G22 与计划 09 §1 逐字钉着，
  扩面等于改历史取证的口径 ⇒ 留给下一波裁（裁的话是 **66**，两处历史原文按体例不重写、
  只在新节里记新值）。
- **G25 候选 · `schema.d.ts` 的行尾会在 `gen:api` 之后翻一次**（§7.2 逐格实测）：
  工具写 **LF**、`autocrlf` checkout 成 **CRLF** ⇒ 一次 `gen:api` 让**字节**变、
  而 **`git diff` 为空**，于是清单对不上、折向一次重建。
  ⚠️ 连带一格假阳性：那一刻 `git status --porcelain` 会把它报成 ` M`，
  若正好在那时构建，清单会记下 `dirtySources=["src/api/generated/schema.d.ts"]`
  而它的 **blob 一个字节都没变**。
  **长期解**：给那一个文件在 `.gitattributes` 上钉 `-text`
  （⚠️ 本波**一个字都不许改** `.gitattributes` ⇒ **没做**）。
- **一格小的、如实报**：`vite.config.ts` 里那个插件收尾印的一行是
  `<sha>（⚠️ 脏构建）`，它只看 `dirty`、**不看** `dirtySources` ⇒ 本波那一次真构建
  （`dirty=true` 而 `dirtySources=[]`，即「源面一格都不脏、仍然可复现」）被它印成了
  「⚠️ 脏构建」。⚠️ **它是一句真话**（工作树当时确实脏），只是**不够精确**；
  ⚠️ 而**精确的那一格两个读者都印对了**（`serve.ps1`：「工作树当时有未提交改动，
  而**源面一格都不脏** ⇒ 这份产物仍然可以由上面那个 commit 复现」；
  `check:dist`：同一句）。⚠️ **本波没有去改它**：改它要动 `vite.config.ts`（它在源面里）
  ⇒ 就得**再跑一次 `npm run build`**，而派单逐字要求「`npm run build` 只能跑一次」
  ⇒ **顶回给控制者裁**（要改的话是 3 行、并且要重排一次构建窗口）。

### 9.3 待清扫

- `%TEMP%\p09t1\` **整棵**（探针脚本 15 份 + `scratch1\`（一份完整构建产物）+
  `fresh\`（26 棵合成树）+ `freshgit\`（一个合成的 git 仓库）+ `cdstage\` / `mutstage\`
  （两棵 staged 的 `frontend` 副本）+ `smokelogs\`（6 份日志）+ `dist_before.json` /
  `cov.json` / `openapi.json` / `schema.d.ts.before` / `pe_serve_probe.db` /
  `pe_trial_probe.db` / `alembic_probe.db`）⇒ **收尾删净并复验**（§10）。
  ⚠️ **不动** `p07ctl`、`pe_trial_csv_41684`、`pe_tunnel_8030`，
  ⚠️ 也**不动**那约 **28 处**更早的 `%TEMP%` 残留（不在本波授权范围）。
- `backend\pe_demo.db` **被重灌过两次**（`demo.ps1` 的既有行为：删旧库重灌）——
  dev 档 smoke 一次、产品档 smoke 之前一次。⚠️ 它是 gitignored 的演示库、
  `.gitignore` 里逐字写着「可以随时删掉重建」⇒ **不是违规**，
  ⚠️ 但它是一格**本波造成的状态变化**，如实报（姿势同 Plan 08 Task 8 报告里那一格）。
  ⚠️ 另外 smoke **写脏了**它（第 2/5/6/9/10 步，`smoke.mjs` 文件头逐字交代过）⇒
  下一个要用 dev 档/产品档 smoke 的人**要先重跑 `demo.ps1`**。
- `backend\.coverage` 被本波那 4 次覆盖率跑改写过（gitignored）。
- ⚠️ **甲方那一侧需要控制者做的事**（§10 收尾五格）：**8030 与公网隧道在开工时就已经死了**
  （本机 09:41:15 重启）⇒ 重启窗口要做的事**比派单预想的多**（见 §10.3）。

### 9.4 ⚠️ 没按派单做的（**0** 处刻意偏离；**3** 处如实报的差异）

| # | 派单说的 | 我做的 | 为什么 |
|---|---|---|---|
| 1 | 「期望是『**26** 个逐字未变 + 新增 1 个清单』」 | 实测 **27** 个逐字未变 + 新增 1 个 | ⚠️ **比期望更好**（期望里那一个「会变的」其实也没变）；`index.html` 与两个主 chunk 的 sha256 全部逐字未变 |
| 2 | 「`npm run build` 只能跑一次、且必须是本波的最后一步之一」 | ✅ **只跑了一次**写进 `frontend/dist`（§6.2），⚠️ 而它**不是**时间轴上的最后一步（后面还有 smoke 与文档）| ⚠️ 顺序是**故意**的：清单是**构建产物**、而 `package.ps1` 的 `$MustContain` 与 `check:dist` 的 ④d 组**依赖它存在** ⇒ 先构建才能让守卫全绿；⚠️ 而构建之后**没有任何一步动过源面**（`git status` 与判据都复验过 ⇒ `FRESH=True`） |
| 3 | 「四档失效方向」 | 我做了**六档**（+「清单读不懂」与「本机问不到 git」） | ⚠️ 不减少、只增加：派单那四档逐个都有实测，另两档是实物逼出来的（一个坏 JSON、一台没有 git 的甲方机器） |

---

## ⑩ 最终验收

### 10.1 逐格

| 格 | 基线 | 本波实测 | 判 |
|---|---|---|---|
| 后端 `pytest --no-cov` | **1775 passed** | **1784 passed**（270.62 s） | ✅ **+9**（只增不减） |
| 后端 `--cov` | 1774 + 1 skipped | **1783 passed + 1 skipped** | ✅ **+9** |
| 覆盖率 · `app/domain` | **1268 / 0 / 376 / 0 / 100%** | **1268 / 0 / 376 / 0 / 100%**（18 个模块） | ✅ **逐字未变** |
| 覆盖率 · `app` | **7661 / 209 / 1860 / 121** | **7661 / 209 / 1860 / 121**（98 个模块，97%） | ✅ **逐字未变** |
| 覆盖率 · `scripts` + `app.static` | **1172 / 217 / 336 / 49** | **1172 / 217 / 336 / 49**（7 个模块） | ✅ **逐字未变** |
| 覆盖率 · TOTAL | **8753 / 423 / 2168 / 169** | **8753 / 423 / 2168 / 169**（104 个模块，94%） | ✅ **逐字未变** |
| 表数 | **30**（`sqlite_master` **31**） | **30**（`sqlite_master` `type='table'` = **31**，含 `alembic_version`） | ✅ |
| 迁移链 | **6 单头** `a1af54889103` | `alembic heads` = **`a1af54889103 (head)`**；`alembic history` = **6** 个 revision | ✅ |
| 残差 diff | **0** | `alembic check` = **`No new upgrade operations detected.` / rc 0** | ✅ |
| openapi | **455 301 B / `7D75650765F2B65D`**、77 / 106 / 87 / 65 / 3 | **455 301 B / `7D75650765F2B65D`**、**77 / 106 / 87 / 65 / 3** | ✅ **逐字未变** |
| `gen:api` ×2 | `git diff` 空 | **两次都空**（⚠️ 而工作树字节会翻 CRLF→LF，§7.2；本波逐字节还原并对账） | ✅ |
| 三档 smoke | **819 / 819 / 851**，各 18 步 / rc 0 | **819 / 819 / 851**，各 **18/18** / **rc 0** | ✅ **逐字未变** |
| `check:tokens` | **36**（下界 25） | **36**（下界 25），退出码 **0** | ✅ |
| `check:dist` 产物侧 | **23** 个 / **596.2 kB** | **24** 个 / **603.0 kB**，跳过 **4** 个非文本，退出码 **0** | ⚠️ **+1 / +6.8 kB = 那份清单**（§2.5 的裁定；⚠️ 判据一条都没放宽） |
| 5 组禁用串 | 各 **0** 次 | 各 **0** 次（在 **24** 个文件上） | ✅ |
| 新增依赖 | 后端 0 / 前端 0 | **后端 0 / 前端 0**（`dependencies` 3 项、`devDependencies` 7 项，一个都没加） | ✅ |
| `frontend/dist` | **27** 文件 / **708 583 B** / `index.html` 2 567 B / `7EF16470CD6CE9BB` / 构建戳 02:27:05 | **28** 文件 / **715 604 B** / `index.html` **2 567 B / `7EF16470CD6CE9BB`（逐字未变）** / 构建戳 **2026-10-20 10:59:40** / 新增 `.build-manifest.json` **7 021 B / `B5138B8127DA29E4`** | ⚠️ **变了（派单预告过）**，⚠️ 而 **bundle 哈希一个都没变** ⇒ 甲方已打开的页面**不会** 404 |
| 依赖清单守卫 | 一字不红 | `tests/test_dependencies.py` 全绿（在 1784 里） | ✅ |
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | **四个逐个命中**（`national_standard_2014.csv` / `exercises.yaml` / `exercise_equivalence.yaml` / `alert_rules.yaml`），`backend/data/**` = **24** 个文件 | ✅ |
| 18 个模板指纹 | 全中 | `pytest tests/test_refdata.py --no-cov -q` → **16 passed**（那 18 个指纹的唯一所有者） | ✅ |
| `git diff 42dc849 HEAD -- backend/data` | 空 | **空** | ✅ |
| `git diff 42dc849 HEAD -- backend/app backend/scripts` | — | **空**（⚠️ 本波后端产品代码**一行都没动**） | ✅ |
| `backend/pe.db` | 不得存在 | **False**（不存在） | ✅ |
| `backend/data/seed/` | 0 文件 | **0** 文件 | ✅ |
| 八处 gitignore 项 | 未入库 | `backend/pe.db` · `pe_demo.db` · `pe_trial.db` · `backend/backups/` · `backend/data/seed/` · `frontend/dist/` · `tools/` · `.trial/` ⇒ **8/8 `tracked=0` 且 `ignored=True`** | ✅ |
| 六份 manifest + `.gitattributes` + `.gitignore` + `alembic.ini` | 零 diff | ⚠️ **现量核实：本仓在库的 manifest 形状文件只有 4 份**（`backend/pyproject.toml` · `frontend/package.json` · `frontend/package-lock.json` · `backend/alembic.ini`；`requirements.txt` / `uv.lock` / `pnpm-lock.yaml` **都不存在**）⇒ 那 4 份 + `.gitattributes` + `.gitignore` = **6 个文件**，`git diff 42dc849 HEAD --` 与 `git status --porcelain --` **都是空** | ✅ **零 diff**（⚠️ 而「六份 manifest」这个措辞与实物不符，如实报） |
| `dist-pack\` 那两个包 | 别删 | **一个都没动**（本波**不打包**） | ✅ |
| `backend/backups/` 那两份 | 别删也别入库 | 没动、`tracked=0` | ✅ |

### 10.2 收尾五格（⚠️ 与开工那次同一套探针，逐格复量）

| # | 格 | 收尾实测 | 判 |
|---|---|---|---|
| 1 | PID **36876** / **57488** | ⚠️ **仍然不在**（开工时就已经不在，本机 09:41:15 重启过）；⚠️ **我一次都没杀任何进程、一次都没重启 8030** | ⚠️ **如实报：甲方那一侧从开工起就是断的** |
| 2 | `backend/pe_trial.db` | **1 630 208 B / sha256[:16] `382B507454143274` / mtime 2026-10-19 12:30:48`** —— 与开工**逐字相同** | ✅ **一个字节都没动** |
| 3 | 甲方 URL 匿名 health | ⚠️ **量不到**（隧道进程不在；开工时同样量不到） | ⚠️ 需要控制者重开 |
| 4 | 我自己起的进程 | `Get-NetTCPConnection -State Listen` 里 **8000 / 8020 / 8030 / 8040 / 8041 / 8042 / 8043 / 5173 / 5174 一个都不在听**；`Get-CimInstance` 里**没有**任何 `serve.ps1` / `trial.ps1` / `demo.ps1` / `vite` / `smoke` 进程（只剩探针自己） | ✅ **全停** |
| 5 | `%TEMP%\p09t1` | 见 §10.4 | ✅ |

### 10.3 ⚠️ 控制者的重启窗口要做哪几件事（⚠️ 比派单预想的多）

派单说「本波无迁移 ⇒ 只需重启」。⚠️ **而实测下来不止**，因为**机器重启过、甲方那一侧全死了**：

1. ⚠️ **重开公网隧道**（`scripts/tunnel.ps1 -Port 8030`）—— quick tunnel 已死过五次，
   而这一次是**整台机器重启**带走的；⚠️ **URL 会变**（`hub-inns-holmes-theme.trycloudflare.com`
   大概率作废）⇒ 要**重新发给甲方**；
2. **重起试用档服务**（`scripts/trial.ps1 -Port 8030`，⚠️ **不带** `-Reset`、
   `$env:PE_ENV='prod'` + `PE_TRIAL=1`；⚠️ 它会读现成的 `backend/pe_trial.db`，
   **一个字节都不会改**）；
3. ⚠️ **本波无迁移**（迁移链仍 6 单头、残差 diff 仍 0、表数仍 30）⇒ **不需要** `alembic upgrade`；
4. **匿名复核公网 URL**（`GET /api/health` → 200 且 `tables:30`）；
5. **通知甲方 Ctrl-F5**。⚠️ 而这一格本波的风险**比派单预想的低**：
   **bundle 哈希一个都没变**（`index.html` / `index-DG9aiaVT.js` / `index-D_BSV8Ho.css` /
   18 个懒加载 chunk 的文件名与 sha256 **逐字未变**）⇒ **已打开的页面去懒加载旧 chunk
   不会 404**；⚠️ 严格说甲方那一份前端**内容上没有任何变化**（唯一新增的是
   `.build-manifest.json`，而它**不会被 HTTP 发出去**）⇒ Ctrl-F5 只是保险，不是必需；
6. ⚠️ 顺带：如果控制者要恢复自己的 5173 vite 与两个 `dsh web`，它们也在 09:41:15 那次重启里死了。

### 10.4 `%TEMP%\p09t1` 的清扫

⚠️ **时序如实说**（姿势同 Plan 08 Task 8）：`p09t1` 那一棵的删除发生在**本报告入库之后**
（本报告与写它的脚本都住在那棵树里 ⇒ 它无法在自己被删掉之前复验自己已经被删掉）；
⚠️ 那一次删除与复验的结果由本波在**交回控制者的最终回复**里给出。
⚠️ **不动** `p07ctl`、`pe_trial_csv_41684`、`pe_tunnel_8030`，
⚠️ 也**不动**那约 28 处更早的 `%TEMP%` 残留（不在本波授权范围，Task 8 报过、控制者还没裁）。

### 10.5 commit

| # | sha | 一句话 | ⚠️ 自洽吗 |
|---|---|---|---|
| ① | **`06b252a`** | `feat(frontend)`：vite 内联插件在 `closeBundle` 写 `dist/.build-manifest.json`（七个字段） | ✅ 自洽：它只**产出**清单，没有消费者，`dist` 一个字节都没动 ⇒ 全量与三档 smoke 在这个 commit 上照旧绿 |
| ② | **`0dee8a2`** | `feat(scripts)`：`serve.ps1` 改判据（比清单、不看 mtime）+ `smoke.mjs` 头表 + `test_serve.py` 那一处既有断言跟着改 | ✅ 自洽：`pytest tests/test_serve.py` → **42 passed**（那一条钉 mtime 的既有断言与本 commit 同一个 commit 改对）；⚠️ 而 `dist` 里此时**还没有**清单 ⇒ 判据会答「清单不在 → 重建」，⚠️ 那是**设计好的失效方向**、不是红 |
| ③ | **`af7a424`** | `test(guards)`：`test_serve.py` 新增 9 条 + `check-dist.mjs` ④d 一组 + 清单进包两侧各钉一次 | ✅ 自洽：这个 commit 之前 `dist` 已经重建过（§6.2）⇒ `check:dist --no-build` **rc 0**、`pytest --no-cov` **1784 passed**（含 `test_package.py` 那个**真的打了一个包**的 fixture ⇒「清单进包」是运行时验过的） |
| ④ | **`0cc54de`** | `docs`：README 三处「一律 `-SkipBuild`」松一半 + spec §13.15 第 1 条 + §15 G22 的处置 | ✅ 自洽：纯文档，⚠️ 一个都不在源面里 ⇒ 清单仍然 `FRESH=True`（⚠️ 而这正是 §3.3 顶回 1 的**实物证据**：`gitSha=0dee8a2` 落后于 HEAD `0cc54de`，判据仍答「不需要构建」） |
| ⑤ | *(本报告)* | `docs(sdd)`：Task 1 实现者报告（11 节） | ✅ 同上：`.superpowers/**` 不在源面里 |

---

## ⑪ 行尾复核（逐个被改文件；⚠️ 判据是「**双向逐字节可逆**」）

⚠️ 对 `Document/**` 与 README，「工作树字节 == blob 字节」按设计**不成立**
（差值恰好 = CRLF 行数），故正确判据是**双向可逆**：
`worktree == CRLF(blob)` **且** `blob == LF(worktree)`。

| 文件 | `git ls-files --eol` | 工作树 | blob | `wt == fwd(blob)` | `blob == rev(wt)` | BOM |
|---|---|---|---|---|---|---|
| `frontend/vite.config.ts` | `i/lf w/crlf attr/` | 299 行 / 0 裸 LF | LF | ✅ **True** | ✅ **True** | 无（改前也无） |
| `scripts/serve.ps1` | `i/lf w/crlf attr/text eol=crlf` | 862 行 / 0 裸 LF | LF | ✅ | ✅ | ⚠️ **UTF-8 + BOM**（改前改后都在；PowerShell 5.1 承重） |
| `scripts/package.ps1` | `i/lf w/crlf attr/text eol=crlf` | 693 行 / 0 裸 LF | LF | ✅ | ✅ | **UTF-8 + BOM** |
| `scripts/trial.ps1` | `i/lf w/crlf attr/text eol=crlf` | 554 行 / 0 裸 LF | LF | ✅ | ✅ | **UTF-8 + BOM** |
| `frontend/scripts/check-dist.mjs` | `i/lf w/crlf attr/` | 682 行 / 0 裸 LF | LF | ✅ | ✅ | 无 |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | 6398 行 / 0 裸 LF | LF | ✅ | ✅ | 无 |
| `backend/tests/test_serve.py` | `i/lf w/crlf attr/` | 2953 行 / 0 裸 LF | LF | ✅ | ✅ | 无 |
| `backend/tests/test_package.py` | `i/lf w/crlf attr/` | 637 行 / 0 裸 LF | LF | ✅ | ✅ | 无 |
| `README.md` | `i/lf w/crlf attr/` | **21 138 B** / 258 行 / CRLF 258 / 0 裸 LF | **20 880 B** | ✅ | ✅ | 无 |
| `Document/…设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | **1 144 222 B** / **10 775** 行 / CRLF 10 775 / 0 裸 LF | **1 133 447 B** | ✅ | ✅ | 无 |
| `Document/…甲方试用说明书.md` | `i/lf w/crlf attr/text eol=crlf` | **37 123 B / 179 行**（⚠️ **一个字没改**） | 36 944 B | ✅ | ✅ | 无 |
| `Document/…实施计划09….md` | `i/lf w/crlf attr/text eol=crlf` | **14 027 B / 71 行**（⚠️ **一个字没改**） | 13 956 B | ✅ | ✅ | 无 |
| `.superpowers/**`（本报告） | `-text` | ⚠️ **纯 LF、无 BOM**（写它的脚本按二进制写 `\n`） | == 工作树 | ✅（`-text` ⇒ 双向零转换） | ✅ | 无 |

⚠️ **本波一次行尾/BOM 事故都没发生**（那一族此前已发生六次）。⚠️ 做法逐字交代：
**所有**对被跟踪文件的编辑都走一个二进制模式的 Python helper（读 → 归一到 LF → 改 →
按 CRLF + 原 BOM 状态写回），**每改完一个文件当场核** `git ls-files --eol`；
⚠️ 而所有 PowerShell 探针一律写成 **UTF-8 + BOM + CRLF** 的 `.ps1` 文件再跑
（**一次都没用** `python -c` 嵌双引号、也**一次都没**把带中文的 `.ps1` 写成无 BOM ——
本波亲验过一次那条坑：内联 `powershell -Command "$PSVersionTable…"` 里的 `$` 被吃掉、
当场 ParserError，于是所有 PowerShell 探针都改走 `-File`）。
⚠️ 定点变异那 8 格也**一律按字节**改、**按字节**还原（sha256 对账，⚠️ 一次都没用 `git checkout`）。

---

## 一句话总判断

⚠️ **G22 那颗地雷今天拆了。** 判据是派单给的那一句：「**一次与内容无关的批量写回还能不能
触发重建**」—— 答案**不能**了，而这一格是**在真树、真脚本、真端口上跑出来的**：
把 G22 那**四个引信文件**的 mtime 逐个抬到构建戳之后 9 小时 50 分（`git status` 全程为空、
四个文件的 sha256 一个都没变），真的 `scripts/serve.ps1`**不带** `-SkipBuild` 跑出来的是
「`⇒ 跳过构建（清单与源面 65 个哈希逐个相符）`」+「`⇒ 本次**不需要构建**：本脚本到这一行为止
一次都没查 node、一次都没调 npm`」，`-- ② b  npm run build` 一次都没出现，服务照常 200 / `tables:30`；
⚠️ 而改其中**一个字节**当场答「要构建」并点名是哪一个文件 ⇒ 判据**没有**被放宽成「一律不重建」。
⚠️ 顺带把 G22 的**另一半**也收了：`dist` 从此自带一份构建清单，「这份产物是哪一个 commit 构建的」
第一次可查，⚠️ 而它**进包**（`$MustContain` + `REQUIRED_ENTRIES` 两侧各钉一次，
且由那个**真的打了一个包**的 fixture 运行时验过）。
⚠️ 而本波那一次真构建对甲方那一侧的**内容影响是零**：27 个既有产物**逐字节未变**
（`index.html` `7EF16470CD6CE9BB`、`index-DG9aiaVT.js`、`index-D_BSV8Ho.css` 与 18 个懒加载
chunk 的文件名与 sha256 全部相同）⇒ 已打开的页面**不会** 404；唯一新增的是
`.build-manifest.json`（7 021 B），⚠️ 而它**不会被 HTTP 发出去**。
