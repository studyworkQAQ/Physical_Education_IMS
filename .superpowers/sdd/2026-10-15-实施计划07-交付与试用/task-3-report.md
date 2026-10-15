# Plan 07 Task 3 实现者报告 —— 公网隧道档（`cloudflared` + `scripts/tunnel.ps1`）

> 分支 `p07/tunnel`，起点 `71d1e4f`（`main`，工作树干净）。
> ⚠️ 本文件刻意**不印自己的字节数与 sha256**（不动点问题；Task 1+2 在这上面绕了两圈）。
> ⚠️ 本文件里出现的公网地址一律写作 `https://<rand>.trycloudflare.com`：
> 随机那一段**逐条抹掉**，免得有人照着去撞。取完证之后**全部隧道进程都已停**（§8 有复核）。

---

## ① 环境 + 基线复核

开工第一件事（硬规矩 #73）：

```
$ node --version; python --version
v24.19.0
Python 3.11.1
```

| 格 | 派单给的基线 | 本波实测 | 结论 |
|---|---|---|---|
| 分支起点 | `main` @ `71d1e4f`，工作树干净 | `git checkout -b p07/tunnel` 之后 `git rev-parse --short HEAD` = `71d1e4f`，`git status --short` 空 | ✓ |
| 后端测试 | 1593 passed（`--no-cov`） | **1606 passed**（`--no-cov`，216.37 s） | +13（本波新增的 13 条守卫），**只增不减** ✓ |
| 后端测试（带 cov） | 1592 passed + 1 skipped | **1605 passed + 1 skipped** | 同形状 ✓（⚠️ 见 §7 待清扫第 1 条） |
| 表数 | 28（`sqlite_master` 29） | `pe_trial.db` 与 `pe_demo.db` 各 **29**（28 业务表 + `alembic_version`），`student` 各 60 | ✓ |
| 迁移链 | 4 单头 | `alembic heads` → **`0ac943e0da9b (head)`**（一个头）；`alembic history` **4** 行 | ✓ 本波不动 schema |
| openapi 五格 | 74 / 102 / 84 / 63（15 匿名 + 48）/ 3 | **74 / 102 / 84 / 63（15 + 48）/ 3** | ✓ 逐格相同 |
| openapi 未定型响应 | 24 | **24** | ✓ |
| openapi catch-all | 0 | **0** | ✓ |
| openapi JSON | 420 367 B / sha256[:16] `6058F97F09B35855` | **420 367 B / `6058F97F09B35855`**，三档 `PE_TRIAL`（未设 / `0` / `1`）**逐字节相同**（不同 sha 的个数 = 1） | ✓ **一个字节都没变** |
| `npm run build` | 退出码 0 + 五个产物哈希 | 退出码 **0**（392 ms），`index-Dm53XXz-.css` / `index-Wfsbvc3G.js` / `StudentDetail-kQIIimXN.js` / `AuditLogList-CKJ4Vvz4.js` / `ResourceIndex-DqalY3wm.js` | ✓ **五个哈希逐个相同** |
| `check:tokens` | 绿（36 / 下界 25） | 绿：**36** 个文件（下界 25），「tokens.css 之外一个色值字面量都没有」 | ✓ |
| `check:dist` | 绿（25 产物 / 787 824 字符） | 绿：**25** 个 / **787824** 字符 | ✓ |
| 新增依赖 | 后端 0、前端 0 | 后端 **0**、前端 **0**（`cloudflared` 一个 manifest 都不进，有守卫钉住） | ✓ |
| 扫描面 / `_MODELS_PUBLIC_BASELINE` / `_MODELS_SUBMODULES` / 黄金用例 / 残差 diff | 72 / 33 / 8 / 14 / 0 | 由 **1606 passed / 0 failed** 的那一整套守卫覆盖（`tests/architecture/test_layering.py`、`tests/db/test_migration_chain.py` 等），本波一行生产代码都没改 ⇒ 全部照旧绿 | ✓ |

⚠️ 本波**没有改任何生产代码**：改动面是 `scripts/tunnel.ps1`（新）、
`backend/tests/test_tunnel.py`（新）、`backend/tests/test_serve.py`（两处清单）、
`frontend/scripts/smoke.mjs`（一个按档声明的期望值）、`.gitignore`（两行）、spec（§13.17）。

⚠️ 环境实测（与派单 §0 一致）：局域网 IPv4 `192.168.31.11`（WLAN，只此一块）；
`ssh` 在 `C:\WINDOWS\System32\OpenSSH\ssh.exe`；出网 443 通；
5173 上那个**不是任何人起的** vite（PID 20240）本波**一次都没动**（§8 复核它仍在）。
⚠️ 而 `cloudflared` / `ngrok` / `frpc` 开工时全 MISSING，`winget` 在
`C:\Users\whwenhao\AppData\Local\Microsoft\WindowsApps\winget.exe`。

---

## ② 工具落地（三条路按顺序试完）

### 路 A · `winget install --id Cloudflare.cloudflared` → **没装上**

命令原文与输出原文（逐字）：

```
$ winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements --silent
已找到 cloudflared [Cloudflare.cloudflared] 版本 2026.10.0
此应用程序由其所有者授权给你。
Microsoft 对第三方程序包概不负责，也不向第三方程序包授予任何许可证。
正在下载 https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-windows-amd64.msi
已成功验证安装程序哈希
正在启动程序包安装...
```

⚠️ 然后**停在最后那一行四分多钟不动**（本波等了 4 分钟，期间并行把路 B 跑完了）。
诊断：这个包是 **MSI**，MSI 是**机器级**安装 ⇒ 要 **UAC 提权**，而 `--silent`
并不能免掉那个框；在无人值守（或 Agent 跑的）那一档上**没人能点它** ⇒ 挂住。
处置：停掉 winget，走路 B。⚠️ **这一格是「路 A 在交付现场也会挂」的证据**：
甲方 IT 若在自己的机器上跑同一条命令，会撞同一个框（除非他以管理员身份跑）。

* 复核：winget **没有**留下任何东西 —— `cloudflared` 至今**不在 PATH 上**，
  `%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe` 也不存在。
  这一点由 `tunnel.ps1` 第 ② 步的输出**反证**：它打印的
  `可执行 = C:\…\Physical_Education_ims\tools\cloudflared.exe`
  ⇒ PATH 那一档**落空了**、才回落到本仓 `tools\`（三档找法的顺序是承重的）。

### 路 B · 直接下载独立二进制 → **第 1 次就成**

```
$u = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
Invoke-WebRequest -Uri $u -OutFile tools\cloudflared.exe -UseBasicParsing -TimeoutSec 180
```

写成了一个最多 4 次的重试循环（派单 §0 警告过下载也可能间歇性失败）。
**实测：`attempt 1` 就 `OK`，一次都没重试。**

| 格 | 实测值 |
|---|---|
| 落地路径 | `C:\Users\whwenhao\Desktop\Physical_Education_ims\tools\cloudflared.exe`（⚠️ **不在** `backend/` 或 `frontend/` 下，理由见下） |
| 文件大小 | **55 365 048 B** |
| sha256（全） | `86AEE4017B26625CEE8484C113558F48EFFA4CD47F7AA05FCF425604E5D2B23C` |
| sha256[:16] | `86AEE4017B26625C` |
| 重试次数 | **1 次尝试、0 次重试** |
| `--version` 原文 | `cloudflared version 2026.10.0 (built 2026-10-05T08:39 UTC)` |

⚠️ **一次两侧不同源的交叉核对**（派单只要求「把你下到的那一格的 sha 记下来」，
这一格是白捡的）：cloudflared **自己启动时**在日志里打印

```
INF Version 2026.10.0 (Checksum 86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c)
```

与 `Get-FileHash` 量到的那 64 个十六进制字符**逐字相同**。
⚠️ 如实交代它的**局限**：那是二进制**自报**的校验值，不是从 Cloudflare 官方
checksum 文件独立取来的 ⇒ 它能挡「下载被截断/写坏」，**挡不住**「下载源被换掉」。
派单明说不要求比对官方 checksum 文件，故此处只记值 + 记局限。

⚠️ **为什么落在 `tools\` 而不在 `backend\` 或 `frontend\`**：那两处各有一道**扫描面**
守卫（`backend/tests/architecture/test_source_hygiene.py` 扫全仓 `.py`、
`test_layering.py` 按目录数文件、`smoke.mjs` 第 15 步的 `check:dist` 数 `dist` 产物），
往里塞一个 55 MB 的 `.exe` 会让「扫到多少个文件 / 多少字符」那一格漂，
而漂的样子是**守卫红在一个与真因无关的地方**。`tools/` 是新建的第三处，
一个守卫都不碰它，且已进 `.gitignore`（`git check-ignore -v` 实测：
`.gitignore:106:tools/   tools/cloudflared.exe`）。

### 路 C · 零安装的 SSH 反向隧道 → **今天不通**（三轮实测）

| # | 命令 | 结果（原文） |
|---|---|---|
| C1 | `ssh -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes -R 80:localhost:8099 nokey@localhost.run` | 45 s 后 stderr 只有一行：`ssh_dispatch_run_fatal: Connection to 35.171.254.69 port 22: Connection timed out` |
| C2 | 同上 + `-o ConnectTimeout=12`，重试一次 | **30 s 零输出**（`exited=False`，stdout 0 B / stderr 0 B）⇒ `ConnectTimeout` **压根没触发**，说明卡点不在 TCP 连接 |
| C3 | `ssh -p 443 …  nokey@localhost.run` | **1 s** 就退：`Connection closed by 35.171.254.69 port 443` |

⚠️ 为了把「卡在哪一圈」定下来，本波另外单独量了一次**裸 TCP + banner**：

```
TCP connect within 8s = True (251 ms)
banner bytes = 22 : SSH-2.0-russh_0.63.3
```

⇒ **TCP 通、SSH banner 也在 251 ms 内到达**，挂的是**密钥交换（KEX）那一圈**。
⚠️ 这个结论直接改了 `tunnel.ps1` 里那段散文的措辞（改前写的是「握手被中间设备吃掉」，
那是**推断**；改后写的是实测的三格：TCP 通 / banner 251 ms / KEX 挂住 30 s+ 零输出）。

⚠️ 而它同时说明：**一道「TCP 能不能连」的前置探测挡不住这一档**。
故 `ssh` 那一支的兜底是三样一起：前置 TCP 探测（挡「22 出站被封」那一档，
那是企业网上最常见的）+ **更短的 URL 上限**（`ssh` = 45 s，而 `cloudflared` = 120 s；
`localhost.run` 通的时候是 2 s 内就把地址打在 stderr 上的）+ 每 10 s 一行进度 +
超时后把全部日志原文打出来 + `throw` + 退出码非 0。

**`-Backend ssh` 的实测（端到端跑过一遍）**：

```
-- ② 后端 --
   选定     = ssh（-Backend ssh）
   可执行   = C:\WINDOWS\System32\OpenSSH\ssh.exe
   版本     = OpenSSH_for_Windows_…（略）
   前置探测 = TCP 通（⚠️ 而「SSH 的密钥交换能不能过」是**另一格**，本波在那台机器上实测**没过**：
                banner 251 ms 就到了，KEX 却挂住 30 秒以上零输出）
-- ④ 起隧道 --
   ssh -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -E …\pe_tunnel_8030\ssh-debug.log -R 80:localhost:8030 nokey@localhost.run
      …还在等公网 URL（已等 10 秒 / 上限 45；tunnel.log = 0 字符；进程 PID 27192 还活着）
      …还在等公网 URL（已等 20 秒 / 上限 45；…）
      …还在等公网 URL（已等 30 秒 / …）
      …还在等公网 URL（已等 40 秒 / …）
   ⚠️ 45 秒内没有从日志里抓到公网 URL（进程 PID 27192 还活着）。
      下面是**全部**几份日志的原文（真因在里面…）
   停掉隧道进程（PID 27192）…
   复核 · 隧道进程归零 = ✓ 0 个
   复核 · 本地服务 = ✓ 还活着（http://127.0.0.1:8030/api/health → 200）
EXITCODE = 1 ; WALLCLOCK = 48 s
```

⇒ **「失败得响亮」这一格是端到端验证过的**（48 s、退出码 1、进程收干净、本地服务没被带走）。
⚠️ **「真的能拿到 URL」那一格没有验证过**（本机这个网络过不去 KEX）。
这一格逐字写进了 `tunnel.ps1` 的 `.PARAMETER Backend`、spec §13.17.2 与下面 §7 的顶回第 2 条。

### 三条路的结论

**cloudflared 是本波唯一被端到端验证过的后端。** `-Backend` 的缺省 `auto`
先找 cloudflared（`PATH` → 本仓 `tools\cloudflared.exe` → winget 的 `Links`），
一个都找不到才回落到 `ssh`。

---

## ③ `scripts/tunnel.ps1`

### 参数面（⚠️ 只有两个）

| 参数 | 缺省 | 说明 |
|---|---|---|
| `-Port` | **8030** | 与 `scripts/trial.ps1` 的缺省**对齐**（守卫按字面钉「两个文件的缺省是同一个数」，两侧不同源） |
| `-Backend` | `auto` | `ValidateSet('auto','cloudflared','ssh')`；`auto` = 先找 cloudflared、找不到再用 ssh |

⚠️ 刻意**没有**的三样：`-Prod`（档位是部署事实、归运维的环境变量，与 `serve.ps1`
逐字同一条理由）、`-Reset` / 任何灌库参数（那是 `trial.ps1` 的活）、
`-Lan`（隧道与绑定地址无关：`cloudflared` 一律回源到 `127.0.0.1`）。
守卫有一拍钉住「参数面里没有第三个开关」。

### 七步

| 步 | 做什么 | 实测证据 |
|---|---|---|
| ① | 数并清掉上一轮留下的**孤儿隧道进程**；删掉陈旧 URL 文件；清空旧隧道日志 | **命中过一次真的孤儿**（见下面「孤儿清理」那一节） |
| ② | `Resolve-TunnelBackend`（**单一所有者**）+ 读版本 + `ssh` 前置 TCP 探测 + 「不碰防火墙」那一段 | `选定 = cloudflared（-Backend auto）` / `版本 = cloudflared version 2026.10.0 (built 2026-10-05T08:39 UTC)` |
| ③ | 轮询 `http://127.0.0.1:<Port>/api/health`；打不通就**报一句人话 + `exit 1`** | `→ 200（轮询 1 次）` + `{"status":"ok","tables":28,"students":60,"trial":true}` |
| ④ | 起隧道 → 抓 URL → **穿过公网**复核它活着 | `✓ 抓到公网 URL = https://<rand>.trycloudflare.com`；`GET <url>/api/health → 200（试了 1 次）`；`✓ 复核通过：公网那一格与本地那一格逐字同形（tables = 28、trial = True）` |
| ⑤ | 写 `.trial/public-url.txt`（UTF-8+BOM+CRLF） | `已写 …\.trial\public-url.txt（1474 B，UTF-8+BOM+CRLF）` |
| ⑥ | **六条**风险告示 | 见下面「六条告示原文」 |
| ⑦ | 前台阻塞（`Ctrl-C` 停）；`finally` 杀进程 + 复核归零 + 复核本地服务还活着 + 删 URL 文件 | 见 §6 |

### 健康检查（③）：它**不自己起服务**

打不通时打印的原文（逐字）：

```
   ⚠️ http://127.0.0.1:8030/api/health 在 60 秒内没有回 200（轮询了 N 次）。
      本脚本**不自己起服务**（那是第二个所有者：起 uvicorn 归 scripts\serve.ps1，灌试用库归 scripts\trial.ps1）。

      请先在**另一个终端**里跑：scripts\trial.ps1 -Port 8030 -Reset
      （公网档还要先设 $env:PE_ENV='prod' —— 隧道边缘是 HTTPS，故 Secure cookie 成立；
       逐字理由见本文件 .DESCRIPTION 的「档位裁定」那一段），再跑本脚本。
      实测：端口 8030 上**没有任何 listener** ⇒ 服务没起（或起在别的端口上）。
```

⚠️ 最后那一行是**实测**的（`Get-NetTCPConnection -LocalPort … -State Listen`），
于是「服务没起」与「起在那个端口上的是别的东西（会报出 PID）」是两档不同的话。

### 抓 URL：读的是哪一股输出

⚠️ **实测**（不是读文档推的）：

| 后端 | stdout | stderr | `--logfile` 那一份 |
|---|---|---|---|
| `cloudflared`（不给 `--logfile`，只重定向两股流） | **0 字节** | 5 869 B，**URL 在这里** | — |
| `cloudflared`（给 `--logfile` + 重定向两股流） | 0 字节 | 5 869 B | **7 489 B，URL 在这里**，而且是**完整**那一份（JSON 行） |
| `ssh` + `localhost.run` | 0 字节 | URL 应当在这里（⚠️ 本波**没验证过**，KEX 过不去） | — |

⇒ `tunnel.ps1` 的取法：`cloudflared` 走 `--logfile`（`$LogFile`），`ssh` 走 **stderr 重定向**
（也落到 `$LogFile`）；抓 URL 的那个函数**一律扫 `$LogFile` 与 `$ErrFile` 两份**，
于是两个后端共用同一条路径。

⚠️ `--logfile` 是**承重两格**：① 它是抓 URL 的那一份日志；
② 它让隧道进程的**命令行里含标记** `pe_tunnel_<Port>`（`ssh` 那一支同理用 `-E`），
于是第 ① 步的孤儿判据能认出自己留下的那些。

**正则（⚠️ 全仓只有这一处 = 单一所有者）**：

```
https://[a-z0-9]+(?:-[a-z0-9]+)*\.(?:trycloudflare\.com|lhr\.life)
```

⚠️ 为什么不用宽松的 `https://\S+` —— 这是**实测**出来的，不是想出来的。
`cloudflared` 日志的**第一行**就是免责声明，逐字含两条链接：

```
INF Thank you for trying Cloudflare Tunnel. … subject to the Cloudflare Online Services Terms of
Use (https://www.cloudflare.com/website-terms/), … by following:
https://developers.cloudflare.com/cloudflare-one/connections/connect-apps
INF Requesting new quick Tunnel on trycloudflare.com...
INF +------…------+
INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
INF |  https://<rand>.trycloudflare.com                                        |
```

⇒ 宽松正则会抓到 **`https://www.cloudflare.com/website-terms/`**，
于是「一条打不开的公网链接」被印给甲方。
守卫 `test_the_url_regex_has_one_owner_and_picks_the_tunnel_not_the_disclaimer`
里有一拍是**行为**取证：把正则从文件里读出来、拿上面这份实测日志喂它，
断言它抓到 `trycloudflare.com` 那一条；**再断言一条宽松正则在同一份输入上会抓错**
（⇒ 红绿两侧都在场，硬规矩 #50）。⚠️ 而它也认 `lhr.life`（`localhost.run` 那一家），
因为**后端有两个而正则只有一个住址**。

⚠️ 顺带实测到的一格：URL 那一行**后面跟着一串补齐横幅宽度的空格**，
故正则的右边界必须是「字符类不匹配空格」而不是 `\S+`（`[a-z0-9]` + `-` 正好做到）。

### `.trial/public-url.txt` 的内容原文

⚠️ 路径的唯一所有者是 `tunnel.ps1` 的 `$UrlFile`；`.gitignore` 里那一条与守卫都按字面钉它
（三侧不同源：脚本 / `.gitignore` 文本 / `git check-ignore` 自己的判定）。
实测 `git check-ignore -v .trial/public-url.txt` → `.gitignore:116:.trial/`。

写出来的那一份（1 474 B，UTF-8 + BOM + 18 个 CRLF + 0 个裸 LF；随机段已抹）：

```
# 厦大体育数智系统 · 公网试用链接
# ⚠️ 本文件由 scripts\tunnel.ps1 写；已进 .gitignore（链接是临时的，不该入版本控制）。
# ⚠️ 本文件在隧道进程退出时会被**删掉**：留一份写着死链接的文件比没有文件更坏。

url        = https://<rand>.trycloudflare.com
起于       = 2026-10-15 18:00:00 +08:00
后端       = cloudflared（C:\Users\whwenhao\Desktop\Physical_Education_ims\tools\cloudflared.exe）
后端版本   = cloudflared version 2026.10.0 (built 2026-10-05T08:39 UTC)
本地端口   = 8030（http://127.0.0.1:8030）
本地 health= {"status":"ok","tables":28,"students":60,"trial":true}
公网 health= {"status":"ok","tables":28,"students":60,"trial":true}   ← 写这个文件之前**真发过一次请求**复核它活着
档位       = prod（cookie 的 Secure = True；⚠️ 这是 tunnel.ps1 **本进程**读到的，服务是另一个进程起的）
隧道 PID   = 21956

⚠️ 本链接只在隧道进程活着时有效，重开会变：
   它的寿命 = 上面那个隧道进程（PID 21956）的寿命。进程一停，这个地址立刻失效
   （实测变成 Cloudflare 自己的一页错误）；重跑 scripts\tunnel.ps1 会得到一个**全新的随机地址**。
   ⚠️ 它是公网可达的：任何知道它的人都能打开。风险告示六条见终端里 ⑥ 那一段（或 scripts\tunnel.ps1 的源码）。
```

⚠️ 派单 §2 第 3 条要求的五样（URL / 起于何时 / 后端是哪个 / 本地端口 /
「本链接只在隧道进程活着时有效，重开会变」）**逐个在场**，
另外多三样（后端版本、本地与公网两格 health 的原文、隧道 PID）——
多出来的三样都是**排障要用的**：换机器时对得上是哪一份二进制、
「这条链接当时真的通过吗」有现场、以及孤儿清理时能认出是哪个进程。

⚠️ **UTF-8 带 BOM** 是有意的：这个文件是给**人**用记事本打开读的（甲方 IT 要抄那条链接），
而没有 BOM 的 UTF-8 在老记事本里按 ANSI(GBK) 解码 ⇒ 中文全是乱码。
⚠️ 而它**不入库**，故不受「入库 blob」口径约束（`.superpowers/**` 与 `.py` 那两套都不管它）。

### 六条风险告示原文（⑥ 那一段，逐字）

```
-- ⑥ ⚠️⚠️⚠️ 公网暴露的风险告示（六条，念给甲方听之前先自己念一遍）--

   ① 这条链接是**公网可达**的：任何知道它的人都能打开，
      不限本校园网、不限本机、不需要 VPN。地址是随机发的（不易猜），
      而**随机不等于鉴权** —— 它一旦被转发到群里，就等于公开。
        https://<rand>.trycloudflare.com
   ② **演示口令是公开的**：它的唯一所有者是 backend\scripts\demo_bootstrap.py 的
      DEMO_PASSWORD（也写在 spec §13），本文件刻意**不抄一份字面量**在这里。
      ⇒ 任何打开这条链接的人都能登进**任何一个**在册学号 / 工号（含管理员）。
   ③ 未绑定的账号可以被**抢绑**（spec §1.2 第 4 条）：绑定材料是「学号 + 姓名」，
      两样都在公开的名册里 ⇒ 陌生人可以把别人的账号绑到自己的会话上。
   ④ GET 读操作今天**不留审计**（spec §1.2 第 14 条 / §13.9）：
      谁读了哪个学生的体测 / 体成分 / 处方，事后**查不出来**（只有写入操作留痕）。
   ⑤ **不要录入真实学生信息**：这是一份试用环境，库里 60 名学生均为虚构；
      页面上也挂着同一条告示（frontend\src\App.vue，16 条路由都看得见）。
      真实的健康档案一旦敲进来，它就在公网上、而读它的人查不出来（见 ④）。
   ⑥ **链接的寿命 = 本进程的寿命**：Ctrl-C 停掉本脚本，这个地址立刻失效；
      重跑本脚本会得到一个**全新的随机地址**（旧地址不会复活）。
      ⇒ 发给甲方之前请确认这个终端会一直开着；要长期链接请上 named tunnel + 一个真域名。
```

⚠️ 六条**各在无歧义串上钉住**，且守卫要求「每条在**语句**里恰好出现 1 次、
在一条 `Write-Host` 里」（⇒ 挪进注释也算删掉）；③④ 两条还必须**点名** spec
（`spec §1.2 第 4 条` / `spec §1.2 第 14 条 / §13.9`），因为那两条不是本波新发明的风险。
⚠️ 而 ② 那一条**指着唯一所有者说话**、不抄字面量：守卫扫**整个文件**（含注释）断言
`pe-demo-2025` 与 `DEMO_PASSWORD =` 一次都不出现，且没有任何学号形状的字面量
（`\b20\d{8}\b`）——姿势与 `test_trial.py` / `test_serve.py` 的同名一条逐字同款。

### 前台 / `finally` / 孤儿清理的实测

**孤儿清理**：派单 §2 第 5 条要求「实测『被硬杀』时会不会留下孤儿 `cloudflared`」。
实测方法：先起一轮隧道（`cloudflared` PID 12484），然后
`Stop-Process -Id <tunnel.ps1 那个 powershell> -Force`（⚠️ **不带树**，模拟 IDE 的停止按钮 /
任务管理器）。结果：

```
--- 硬杀脚本之后 ---
孤儿 cloudflared PID 12484
  "C:\…\tools\cloudflared.exe" tunnel --url http://127.0.0.1:8030 --no-autoupdate --logfile C:\…\pe_tunnel_8030\tunnel.log
--- .trial\public-url.txt ---
仍在（⇒ finally 没跑到，与派单预判一致）
url        = https://<rand>.trycloudflare.com
隧道 PID   = 12484
```

⇒ **会留下孤儿**，而且是一个**没人看着的公网入口**（比留一个临时目录坏得多）。
下一轮 `tunnel.ps1` 的第 ① 步**命中**了它：

```
-- ① 上一轮留下的孤儿隧道进程 --
   ⚠️ 数到 1 个（命令行里都含标记 pe_tunnel_8030，即本脚本上一轮留下的）：
     PID 12484  cloudflared.exe
       命令行 = "C:\…\tools\cloudflared.exe" tunnel --url http://127.0.0.1:8030 --no-autoupdate --logfile C:\…\pe_tunnel_8030\tunnel.log
       → 已停（它开着的那条公网链接随之失效）
   上一轮留下了 C:\…\.trial\public-url.txt → 已删（那条链接随上一轮的隧道进程一起死了，留着是撒谎）
```

⚠️ **判据刻意保守**（宁可漏杀不可误杀），**两条同时成立**才杀：
① 进程名恰好是 `cloudflared.exe` / `ssh.exe`（在 WQL 的 `-Filter` 里收窄，
不是在 PowerShell 侧枚举全部进程再筛）；② 它的**命令行**里含本脚本自己的标记
`pe_tunnel_<Port>`。⚠️ 只按进程名杀就是**杀别人的进程** —— 一台机器上完全可能
同时跑着甲方 IT 自己的 named tunnel、另一份仓库的 quick tunnel、或另一个端口上的隧道。
杀之前还**先打印**它是谁（PID + 完整命令行），于是一次误杀是**看得见**的。
守卫有一拍是**红档半边**：全文不许出现 `Stop-Process -Name …` 一类按名字裸杀的写法。

⚠️ 标记落在命令行里的方式是**两个后端各一个**：`cloudflared` 的 `--logfile <logdir>\tunnel.log`、
`ssh` 的 `-E <logdir>\ssh-debug.log` —— 两者的路径里都含 `pe_tunnel_<Port>`。
⚠️ 而 `<Port>` 在标记里 ⇒ **两个端口上的两轮互不相干**（8030 那一轮不会去动 8031 的隧道）。

⚠️ **旧隧道日志必须清掉**（第 ① 步做）：④ 是从这份文件里正则抓 URL 的，
一份上一轮的日志会让它**当场抓到一条死链接**并报成功 —— 失效方向是**静默**的，
于是「甲方点开是个错误页」会一路绿到交付现场。

**`finally`（优雅退出那一档，实测原文）**：

```
   复核 · 隧道进程归零 = ✓ 0 个（判据同 ①：命令行里含本脚本的标记 pe_tunnel_8030）
   复核 · 本地服务 = ✓ 还活着（http://127.0.0.1:8030/api/health → 200）⇒ 隧道死了**没有**带走服务，重跑本脚本即可拿到一条新链接
   收尾 · C:\…\.trial\public-url.txt 已删（上面那条链接随隧道进程一起失效了，留一份写着死链接的文件比没有更坏）
   收尾 · C:\…\.trial 已空 → 目录也删掉（⚠️ 它已进 .gitignore，故留着也不会入库；删掉是为了不留一个空目录）
   隧道日志留着 = C:\Users\whwenhao\AppData\Local\Temp\pe_tunnel_8030（排障用；下一次跑本脚本会清空它）

   隧道已停（退出码 …）。上面那条公网链接现在**已经失效**。
```

⚠️ 三件事方向不同、都要做：**杀**隧道进程、**复核归零**（用与 ① 同一条判据再数一次，
不是「杀了就算」）、**复核本地服务还活着**（隧道死了不该带走服务 —— 那正是本脚本与
`trial.ps1` 分成两个所有者的理由：运维要能「只重开隧道、不动服务」）。

⚠️ 隧道日志目录**刻意留着**（与 `trial.ps1` 删自己那个 CSV 临时目录**不同**）：
它是「隧道为什么失败」的唯一现场，删掉它等于把下一次排障的证据一起删了；
它按端口命名、每次跑本脚本时自己清空，故不会累积。守卫有一拍是**红档半边**：
`finally` 里不许出现 `Remove-Item $LogDir`。

⚠️ **实测抓到的一格小疵并已修**：`Start-Process -PassThru` 给的那个对象不刷新时
`ExitCode` 是 `$null` ⇒ 末尾那一句印出来的是「隧道已停（退出码 ）」——**一个空格**，
而运维真正要知道的是「它是自己死的、还是我停的」。修法是加 `$Proc.Refresh()` +
`$null` 兜底成 1 + 退出码非 0 时**多说一句**「隧道进程是自己退出的 ⇒ 那条链接已失效，
真因在上面那段日志里（也留在 `<logdir>`）」。

### 文件形状

| 格 | 实测 |
|---|---|
| 字节 | **50 128 B** |
| 行尾 | **761 个 CRLF / 0 个裸 LF** |
| BOM | **有**（`EF BB BF`） |
| 块注释收尾符 | 恰好 **1** 个（守卫按字面钉它；函数里一律用 `#` 行注释，⚠️ 理由写在脚本里） |
| PowerShell 语法 | `[System.Management.Automation.Language.Parser]::ParseFile` → **parse errors = 0** |
| `git ls-files --eol` | `i/lf  w/crlf  attr/text eol=crlf`（与另外 5 个 `.ps1` 逐字同款；⚠️ **`.gitattributes` 一个字都没改** —— 既有的 `scripts/*.ps1 text eol=crlf` 那条规则本来就盖得住它） |

⚠️ 写文件一律用 **Python 二进制模式**（`b"\xef\xbb\xbf" + text.replace("\n","\r\n")`），
每改完当场核 BOM / CRLF / 裸 LF / parse errors 四格 —— 本仓为此付过四次代价。
⚠️ 而**首跑就抓到过一个真语法错**（一行 `Write-Host "…"` 末尾多了一个没有配对 `(` 的 `)`），
是 `ParseFile` 报出来的、不是跑出来的 ⇒ 那一格「先 parse 再跑」的顺序是承重的。

---

## ④ 档位六格端到端取证

⚠️ 派单 §3 明令：**不许用「非浏览器客户端」代替浏览器**（非浏览器客户端会照发
`Secure` cookie，测不出浏览器拒收那一格 —— Plan 06 Task 15 就如实记过那一格没复现）。
故第 1、4 两格用的是 **CDP + 真 Edge 无头**（姿势逐字照 `smoke.mjs` 第 14 步那一套
零依赖 CDP 客户端），量的是 `Network.getAllCookies` 给的「浏览器**实际存下的**那一格」，
而不只是响应头里的那一格。

### 格 1 · `prod` + 隧道 + 真浏览器（CDP）→ **能登录，下一个请求 200**

命令（两个终端）：

```
# 终端 A
$env:PE_ENV='prod'; $env:PE_TRIAL='1'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\trial.ps1 -Port 8030 -Reset
# 终端 B
$env:PE_ENV='prod'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tunnel.ps1 -Port 8030
```

服务端起的档位（终端 A 里 `serve.ps1` 打的原文）：

```
   PE_ENV          = prod
   PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 未设 → 本进程已**强制**清成 未设（= 生产缺省 "0"…）
   档位            = prod（cookie 的 Secure = True）
```

探针（`$env:TEMP\p07t3\grid1.mjs`，口令**从 `demo_bootstrap.py` 的 `DEMO_PASSWORD`
现场读出来**、探针里不抄字面量；账号 `2025060001`）：

```
== ① 打开 https://<rand>.trycloudflare.com/login ==
location = /login
试用告示（/login，渲染后）= "试用环境 · 数据为高保真仿真（60 名学生均为虚构） · 请勿录入真实学生信息"
表单选择器实测 = ["INPUT:identity-asof:input","INPUT:radio:","INPUT:radio:","INPUT:login-name:input data","INPUT:login-password:input","BUTTON:submit:btn btn--primary"]

== ② 真填表 + 真点提交 ==
填表 = filled 2025060001 / 12 chars
登录后 location.pathname = /s/home

== ③ Set-Cookie 原文（浏览器**收到**的那一份）==
    => pe_session=<64 字符不透明 id>; HttpOnly; Max-Age=7200; Path=/; SameSite=lax; Secure

== ④ 浏览器**实际存下**的 cookie（Network.getAllCookies）==
   {"name":"pe_session","domain":"<rand>.trycloudflare.com","path":"/","secure":true,
    "httpOnly":true,"sameSite":"Lax","session":false,"expires":1792066195.909192}

== ⑤ **下一个请求**（带浏览器自己那张 cookie）==
  GET /api/auth/me -> {"status":200,"body":"{\"kind\":\"student\",\"id\":1,\"name\":\"周晨阳\",
                       \"role\":\"student\",\"student_no\":\"2025060001\",\"staff_no\":null}"}
```

| 判据 | 实测 | 结论 |
|---|---|---|
| `Set-Cookie` 原文含 `; Secure` | `pe_session=…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax; **Secure**` | ✓ |
| 浏览器**实际存下**的 `secure` 属性 | **`true`** | ✓ **浏览器收下了它** |
| 登录 → 下一个请求 | `GET /api/auth/me` → **200**（**不是 401**），响应体是正确的学生身份 | ✓ |
| 路由跳转 | `/login` → `/s/home` | ✓ |
| 告示在公网档也在 | `/login` 与登录后页面上都渲染出「试用环境 · 数据为高保真仿真（60 名学生均为虚构） · 请勿录入真实学生信息」 | ✓ |

⇒ **控制者裁定的「公网档跑 prod」实测成立。**

⚠️ 如实记两处探针噪声（都**不是**档位问题）：
① 首跑时 `/login` 上那一格告示量到 `null` —— 那是**时序**：告示是 `App.vue` 在
`onMounted` 里问完 `/api/health` 之后才渲染的，比页面自己那些请求**晚一帧**
（`smoke.mjs` 第 14 步的 `extraNeedles` 逐字记着这一格）。加了轮询之后复跑，
两条页面上都量到了。② 探针第一版打的 `GET /api/students/me/weekly-sheet` 回 **422** ——
那是**探针打错了路径**（真路径是 `/api/students/{id}/weekly-sheet`，`me` 被当成 `{id}` 解析）；
改成正确路径之后回 **404 `no_active_prescription`**，理由是「学生 1 在 **2026-10-15**
没有生效的处方」——即它用的是**今天的真实日期**而不是演示库的业务日 `2025-10-12`。
⚠️ 而这一格反而**证明鉴权通过了**（它走到了业务规则那一层，而不是 401）。

### 格 2 · `prod` + 隧道 + `smoke.mjs` 全量 → 见 §5

### 格 3 · `prod` 的启动自检 + `PE_CORS_ORIGINS` 未设时 prod 能不能起 → **能起**

实测环境：`$env:PE_ENV='prod'`、`$env:PE_TRIAL='1'`，而 **`PE_CORS_ORIGINS` 一次都没设**
（起服务那个终端里实测 `[$env:PE_CORS_ORIGINS]` = `[]`，空串）。结果：

```
   PE_ENV          = prod
   档位            = prod（cookie 的 Secure = True）
   进程 PID = 34700
-- ④ 健康检查 --
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8030 (Press CTRL+C to quit)
   http://127.0.0.1:8030/api/health → 200（轮询 1 次）
   {"status":"ok","tables":28,"students":60,"trial":true}
```

⇒ **`prod` + `PE_CORS_ORIGINS` 未设 = 起得来**，`Application startup complete.` 打印了、
健康检查 200。⚠️ 与 spec §13.8 的论证逐字吻合：那条自检是「`prod` 下若
`PE_CORS_ORIGINS` 未设**而代码仍要挂 `*`** → `raise`」，而**空 = 不挂 `CORSMiddleware`**
⇒ 压根不走到那个 `raise`。⚠️ 而隧道是**同源**的（浏览器眼里的 origin 就是那个
`https://<rand>.trycloudflare.com`，前端与 API 同一个 origin），故本档**不需要** CORS。
**没有 raise，故不需要处置。**

### 格 4 · `dev` + 隧道（对照组）→ **也能登录**，是一档可用的退路

命令：起服务那个终端里 `Remove-Item Env:\PE_ENV`（实测 `PE_ENV = []`），
`serve.ps1` 打印 `档位 = dev（cookie 的 Secure = False）`；然后同一个 `tunnel.ps1`。

`tunnel.ps1` 在实测到 `dev` 时打印的原文（⚠️ **只打印、不 `throw`**）：

```
   档位（**本进程**的 PE_ENV = 未设）= dev（cookie 的 Secure = False）
      ⚠️ 实测是 dev 档（本进程）。dev 在隧道下**也能登**：HTTPS 页面上收一张**非** Secure 的 cookie 是允许的
         （本波用真浏览器实测过），故它是一档**可用的退路**、本脚本不 throw。
         而公网档的正确档位是 **prod**（多三样：Secure cookie、请求头身份通道强制关、启动自检会跑）。
         要切过去：Ctrl-C 停掉服务 → 在起服务的那个终端里 $env:PE_ENV='prod' → 重跑 trial.ps1 与本脚本。
```

真浏览器（同一个 CDP 探针）的实测：

```
== ③ Set-Cookie 原文 ==
    => pe_session=<64 字符>; HttpOnly; Max-Age=7200; Path=/; SameSite=lax
       ⚠️ **没有** Secure
== ④ 浏览器实际存下的 ==
   {"name":"pe_session","domain":"<rand>.trycloudflare.com","path":"/","secure":false,
    "httpOnly":true,"sameSite":"Lax","session":false,…}
== ⑤ 下一个请求 ==
  GET /api/auth/me -> {"status":200,…}
```

⇒ **`dev` + 隧道**：`Set-Cookie` 里**没有** `Secure`、浏览器存下的是 `secure: false`、
而它**照样存下了**（HTTPS 页面上收一张非 `Secure` 的 cookie 是允许的 ——
`Secure` 是「只许走 https」的约束，不是「必须 https 才有」），下一个请求 **200**。

⚠️ **这一格的意义**（派单 §3 第 4 条）：万一 `prod` 在隧道下不通，`dev` 是一档可用的退路。
本波 `prod` 那一格是通的（格 1），故 `dev` **不是**今天的处置，而是一条**备胎**——
而它被实测过，故「备胎是好的」这句话有据。⚠️ 也正因如此 `tunnel.ps1` 在 `dev` 上
**不 `throw`**：`throw` 会把一档能用的退路一起打死。

⚠️ 与 `-Lan` 那一档的**差别**要点名清楚（这是本 Task 与 Task 2 的接缝）：
`-Lan` 是**明文 http** ⇒ `prod` 的 `Secure` cookie 会被浏览器**拒收** ⇒「登录 200、
下一个请求 401」；隧道是 **HTTPS 边缘** ⇒ `Secure` **成立**。故
**局域网必须 `dev`、公网应当 `prod`**，两档相反、都不许改，
而两处打印的档位提示是**两段不同的话**（守卫
`test_the_public_tier_hint_and_the_lan_tier_hint_are_two_different_passages` 钉住
「一段里那句独有的话不出现在另一段里」，两侧不同源：`公网档就是这一档：隧道边缘是 HTTPS`
只在 `tunnel.ps1` 里、`同一个网段里的任何人都打得开` 只在 `serve.ps1` 里）。

### 格 5 · 隧道断了会怎样 → 见 §6

### 格 6 · 16 条路由逐条走公网 URL → **16/16 全 200**

探针 `$env:TEMP\p07t3\grid6.py`（对 `https://<rand>.trycloudflare.com` **真发请求**）。
派单点名「至少七条真发请求」，本波**十六条全发**：

| 路由 | 状态 | content-type | 前 40 字节 |
|---|---|---|---|
| `/` | 200 | `text/html; charset=utf-8` | `<!doctype html>\r <html lang="zh-CN">\r   ` |
| `/login` | 200 | 同上 | 同上 |
| `/bind` | 200 | 同上 | 同上 |
| `/s/home` | 200 | 同上 | 同上 |
| `/s/weekly-sheet` | 200 | 同上 | 同上 |
| `/s/check-in` | 200 | 同上 | 同上 |
| `/s/rpe` | 200 | 同上 | 同上 |
| `/s/mini-test` | 200 | 同上 | 同上 |
| `/s/notifications` | 200 | 同上 | 同上 |
| `/t/dashboard` | 200 | 同上 | 同上 |
| `/t/report` | 200 | 同上 | 同上 |
| `/t/alerts` | 200 | 同上 | 同上 |
| `/t/students/4` | 200 | 同上 | 同上 |
| `/admin` | 200 | 同上 | 同上 |
| `/admin/audit-logs` | 200 | 同上 | 同上 |
| `/admin/students` | 200 | 同上 | 同上 |

⇒ **200 的路由数 = 16 / 16**。⚠️ 十六条的前 40 字节**逐字相同**是**应有的**：
它们是 SPA，`app.static.mount_spa` 的 fallback 一律回同一份 `index.html`
（`/` 的那一份实测 1 825 字符，里面引的是 `dist/assets/index-Wfsbvc3G.js`
—— ⚠️ 与 `npm run build` 的产物哈希**逐字相同**，即公网上发出去的确实是那份构建产物）。

**告示那一格（`trial`）在公网档也在**：

```
GET <url>/api/health -> 200 {"status": "ok", "tables": 28, "students": 60, "trial": true}
trial is True  ✓   tables == 28  ✓   students == 60
```

⚠️ 而「告示**渲染出来了**」不是靠这一格推的，是靠格 1 的 CDP 量的**渲染后 DOM 文本**
（`/login` 与登录后 `/s/home` 两处都量到那条告示的完整字面）；
`smoke.mjs` 第 14 步在公网档上又量了一遍**全部 16 条路由**（193/193 条断言全绿，
其中含「16 条路由上试用告示的**条数**与本档一致 ⇒ 期望 16 条」那一拍）。

---

## ⑤ `smoke.mjs` 走公网 URL

### 首跑：**18 步 / 710 绿 / 1 红 / 退出码 1 / 199 s**（如实报）

命令：

```
$env:PE_TRIAL='1'; $env:PE_API_BASE=$u; $env:PE_WEB_BASE=$u   # $u = .trial\public-url.txt 里那条
npm run smoke
```

红的那**一拍**（逐字原文）：

```
第 16 步 ✗ ⑦ cookie **不带** Secure（本机不是 PE_ENV=production；生产上它必须在）
        →  pe_session=Ec48n4xSUt-…; …（令牌已掩）
```

⚠️ **是哪一拍、为什么**（派单 §3 第 2 条要求逐条解释）：
第 16 步 ⑦ 那一拍**写死**期望「cookie **不带** `Secure`」，而它自己的文案就写着理由
——「本机不是 `PE_ENV=production`；生产上它必须在」。公网档跑 **`prod`**
⇒ 那一拍的**前置条件不再成立**：响应头里**有** `; Secure`（这是**对的**，
格 1 已经用真浏览器量过浏览器收下了它），而断言期望它**没有** ⇒ 红。
⚠️ 即：**红的不是产品，是那一拍的期望侧对档位无感**。
本仓此前只有三档，三档一律 `dev`，故「写死 dev 的期望」在当时是**对的**；
公网档是**第四档**，它把这个隐含前提暴露出来了。

### 处置：按档**声明**期望，⚠️ 不是删掉那一拍（硬规矩 #92）

照 `PE_TRIAL` 的**既有姿势**（期望侧 = 本进程的环境变量、被测侧 = HTTP 响应头，
**两侧不同源**）加一个 `PE_COOKIE_SECURE`：

```js
const COOKIE_SECURE_EXPECTED = (process.env.PE_COOKIE_SECURE ?? '').trim() === '1'
…
check(`⑦ cookie ${COOKIE_SECURE_EXPECTED ? '**带**' : '**不带**'} Secure`
  + (COOKIE_SECURE_EXPECTED
    ? '（公网档 = PE_ENV=prod：隧道边缘是 HTTPS，故 Secure 成立且**必须**在）'
    : '（本机不是 PE_ENV=production；生产上它必须在）'),
  (COOKIE_SECURE_EXPECTED === /;\s*secure/i.test(setCookieRaw)), maskedRaw)
```

⚠️ **两个方向的失效都响亮**（这是「不是放宽判据」的判据）：
在 `prod` 上忘了设 ⇒ 那一拍红（**就是上面那次首跑**，本波亲手复现过）；
在 `dev` 上多设了 ⇒ 同一拍**同样红**。
⚠️ 而全仓**只有一处**断言 `Secure`（`Grep` 实测：`smoke.mjs` 里 `[Ss]ecure` 命中的
非注释行只有那一拍），故「按档取期望」只有一个住址。

⚠️ 另外三档**一个字节都不受影响**：不设该变量时 `COOKIE_SECURE_EXPECTED === false`，
而 `false === /;\s*secure/i.test(x)` 与改前的 `!/;\s*secure/i.test(x)` **逐字等价**；
变的只有断言**文案**（它把「本档期望什么」说出来）。
⚠️ 而这句话本波**没有靠读代码推断**：三档**逐档重跑**过（下表）。

### 四档的实测结果

| 档 | 后端 | `PE_TRIAL` | `PE_COOKIE_SECURE` | 步数 | 断言 | 退出码 | 墙钟 |
|---|---|---|---|---|---|---|---|
| **dev 档** | `demo.ps1 -Port 8000` + vite `--port 5174 --strictPort` | 未设 | 未设 | **18/18 全绿** | **679 绿 / 0 红** | **0** | 56 s |
| **产品档** | `serve.ps1 -Port 8020 -SkipBuild`（同源） | 未设 | 未设 | **18/18 全绿** | **679 绿 / 0 红** | **0** | 34 s |
| **试用档** | `trial.ps1 -Port 8030 -Reset`（同源） | **1** | 未设 | **18/18 全绿** | **711 绿 / 0 红** | **0** | 42 s |
| **公网档** | `trial.ps1 -Port 8030 -Reset`（`PE_ENV=prod`）+ `tunnel.ps1 -Port 8030` | **1** | **1** | **18/18 全绿** | **711 绿 / 0 红** | **0** | **197 s** |

⚠️ 三档本地数字与派单基线**逐个相同**（679 / 679 / 711），⇒ 那一处改动确实没有动到它们。

### 公网档那一遍的逐拍数字（与本地试用档**逐拍相同**）

```
绿  第 00 步 · 登录三种角色 + 演示库复原核实 · 25/25
绿  第 01 步 · GET /api/health → tables == 28 且 students > 0 · 7/7
绿  第 02 步 · 管理员 POST /api/class-sessions → 201 … · 10/10
绿  第 03 步 · 教师头 open-rpe 拿到口令 … · 9/9
绿  第 04 步 · 匿名读口令 → 401；教师头读 → 200 · 7/7
绿  第 05 步 · 学生头 POST /api/rpe-records → 201；再交 → 409 · 9/9
绿  第 06 步 · 学生头 POST /api/training-logs → 201 · 10/10
绿  第 07 步 · GET /api/students/4/weekly-sheet?as_of=2025-10-12 · 41/41
绿  第 08 步 · 教师头 dashboard · 14/14
绿  第 09 步 · 预警处置 · 13/13
绿  第 10 步 · 写入侧强制（401 / 403 / 201）· 17/17
绿  第 11 步 · 只读资源被写 → 405 http_405 · 6/6
绿  第 12 步 · 从 /openapi.json 反查 catalog/resources.ts 的 23 行 · 129/129
绿  第 13 步 · 学生端那三个窄端点 · 72/72
绿  第 14 步 · 16 条路由的无头浏览器 DOM 取证（CDP + cookie）· 193/193
绿  第 15 步 · check:tokens + check:dist · 8/8
绿  第 16 步 · 鉴权全链路 · 72/72      ← 首跑红的那一步，修完 72/72
绿  第 17 步 · 静态守卫 9 条 · 69/69
   步数 18/18 全绿 · 断言 711 绿 / 0 红
   后端 https://<rand>.trycloudflare.com · 前端 https://<rand>.trycloudflare.com · as_of 2025-10-12
```

而修完之后那一拍的原文变成了：

```
✓ ⑦ cookie **带** Secure（公网档 = PE_ENV=prod：隧道边缘是 HTTPS，故 Secure 成立且**必须**在）
   →  pe_session=jA7cqebLEgrY…; …（令牌已掩）
```

### 与 711 的差、以及 197 s

* **断言数与本地试用档同为 711，差 0**，而**逐拍**数字也逐档相同（上表）⇒
  「公网档因为 `prod` 而让某一拍行为不同」的**只有第 16 步 ⑦ 那一拍**，
  而它不是「少测了一拍」，是**期望侧翻了个方向**（不带 `Secure` → 带 `Secure`）。
  ⚠️ 派单 §3 第 2 条要求的「如实报是哪一拍、为什么」就是上面那一节。
* **墙钟 197 s vs 本地 42 s**：差**全部**是隧道往返（每一个 HTTP 请求都要
  本机 → Cloudflare 边缘（实测 `location=hkg01` / `hkg08`）→ 回本机）。
  最吃它的是第 14 步（16 条路由的 CDP 取证，每条都要轮询到关键内容出现）
  与第 12 步（129 条断言、逐个资源打 `/openapi.json` 与列表端点）。
  ⚠️ 而 197 s 里**没有**一拍因为超时而假红 ⇒ 判据的超时余量在公网档上也够。

⚠️ **这一格是「甲方能完整用一遍」的最强证据**（派单 §3 第 2 条语）：
18 步全绿意味着「登录 → 建课 → 发口令 → 交快评 → 打卡 → 看训练单 → 看 dashboard →
处置预警 → 管理台写入 → 405/403/401 三档授权 → 16 条路由真渲染 → 两个构建守卫 →
鉴权全链路 → 9 条静态守卫」**整条路**是**穿过公网**走通的，而不只是在回环上走通。
⚠️ 而它**确实把试用库写脏了**（`smoke.mjs` 自己印那一段），故跑之前一律
`trial.ps1 -Port 8030 -Reset`（本波每一档跑之前都重灌过）。

---

## ⑥ 隧道断了的取证

### 方法

隧道进程被**外面**杀掉（`Stop-Process -Id <cloudflared PID> -Force`），
`$env:TEMP\p07t3\grid5.py` 随后对那条 URL **真发请求**。

### URL 变成什么（原文）

```
URL(redacted) = https://<rand>.trycloudflare.com

== GET <BASE>/api/health ==
  HTTPError status = 530 <none>
  content-type = text/plain; charset=UTF-8
  server = cloudflare  cf-ray = a4ae138708b8f554-LAX
  bytes = 17
  first 600 = error code: 1033

== GET <BASE>/login ==
  HTTPError status = 530 <none>
  content-type = text/plain; charset=UTF-8
  server = cloudflare  cf-ray = a4ae13aaec240916-LAX
  bytes = 17
  first 600 = error code: 1033
```

⚠️ **结论（与直觉相反的一格，故必须实测）**：它**不是**「连不上」——
Cloudflare 的边缘**会答**，答的是 **HTTP 530** + `server: cloudflare` +
17 字节的 `text/plain`，正文逐字是 **`error code: 1033`**。
⇒ 「链接有没有失效」**不能**靠「连不上 / DNS 解析不了」判，
而要靠**状态码与响应体**判。⚠️ 这一格对甲方文档也有用：甲方点开看见的
不是一片空白，而是 Cloudflare 的一页错误（`1033` = 「Argo Tunnel error」），
说明书里应当把这一句写进去（Task 5）。

### 本地服务是否还活着 → **活着**

```
== 本地服务是否还活着（隧道死了不该带走它）==
  http://127.0.0.1:8030/api/health -> 200 {"status":"ok","tables":28,"students":60,"trial":true}
```

⇒ **隧道死了没有带走服务**（两者是两个进程）。`tunnel.ps1` 的 `finally` 里
**也复核这一格**并把它打印出来（原文见 §3），于是运维当场就知道
「重跑本脚本即可拿到一条新链接」而不需要去重启服务。
⚠️ 那正是本脚本与 `trial.ps1` 分成两个所有者的**全部理由**：
运维要能「只重开隧道、不动服务」（甲方正在用的会话不该因为一次隧道重开而断）。

### 另一档：脚本被硬杀（`finally` 跑不到）

见 §3「孤儿清理」那一节：硬杀 `tunnel.ps1` 之后 `cloudflared` **作为孤儿活着**、
`.trial/public-url.txt` **也留着**（即一份写着**仍然有效**的公网地址的文件留在磁盘上，
而没人看着它）。下一轮的第 ① 步把它数出来、打印、停掉，并删掉那份陈旧文件。
⚠️ 而**优雅退出**那一档（`Ctrl-C` / 隧道进程自己死 / `throw`）`finally` 会跑到：
杀进程 + 复核归零 + 复核本地服务 + **删 URL 文件** + 删空的 `.trial\` 目录
（实测：`.trial 目录已不在`、`孤儿 = 0`）。

---

## ⑦ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 顶回（**5 处**）

**顶回 1 · 派单 §3 第 2 条「`GET <url>/api/health` → 200 且 `tables` 是 **28**」——把 `28` 写进脚本是第二个所有者。**
`tunnel.ps1` 的 ④ b 改成把公网那一格的 `tables` 与**本地那一格**比
（`[string]$RemoteObject.tables -ne [string]$LocalHealthObject.tables` ⇒ `throw`）。
理由：`28` 的所有者是 **schema**（`/api/health` 现场答的那一格），在一个 PowerShell
脚本里敲第二遍就是第二个所有者 —— 改表的人会漏改这里，而漏改的样子是
「隧道明明通了、脚本却说没通」（或反过来）。⚠️ 而「与本地比」严格**更强**：
它不只证明「那一边有个健康的服务」，还证明「**这条隧道打到的就是本机这个端口上的服务**」
（打到别的东西上时两格会不同）。守卫里有一拍是红档半边：
`assert not re.search(r"tables\D{0,6}28", statements)` —— 谁把 `28` 写死进去当场红。
⚠️ 本波实测那两格是 `28` 与 `28`，故派单要的那一句**事实**照旧成立，只是判据换了个更强的形状。

**顶回 2 · 派单 §1 路 C 的「脚本要能同时支持两种后端」——条件没触发，而我还是做了，⚠️ 并如实标出它没被验证。**
派单那一格的裁定原文是「**若走到路 C**，脚本要能同时支持两种后端」。
本波**没有**走到路 C（路 B 一次成功），故那条裁定**没有触发**。
而派单 §6 第 ④ 条同时邀请了顶回：「若路 A 一次成功，可以只做 A 并把 B/C 写成文档里的退路」。
本波的处置是**做了两个后端**（`-Backend auto|cloudflared|ssh`，判据单一所有者
= `Resolve-TunnelBackend` 一个函数），理由是「换一台机器/换一个网络，`ssh` 是**零安装**的退路」。
⚠️⚠️ **而这里必须响亮地说清它的验证边界**：`ssh` 那一支**只有「失败得响亮」这一格被端到端验证过**
（§2 路 C 那一段的 48 s / 退出码 1 实测），「真的能拿到 URL」那一格**没有** ——
本机这个网络过不去 KEX。⇒ **交付物里今天有一支没被验证过的代码路径。**
控制者若认为「一支没验证过的路径不该进交付物」，处置是**删掉 `ssh` 那一支**、
把 `-Backend` 收成只有 `cloudflared`，并在 `.PARAMETER` 里把路 C 写成文档中的退路
（`ssh -R 80:localhost:<port> nokey@localhost.run`）。**这一格请控制者裁定。**

**顶回 3 · 派单 §2 第 5 条「起之前先数一下有没有上一轮留下的、**监听同一端口**的孤儿」——这个判据对隧道进程不适用。**
`cloudflared` **不监听**本地端口（它是**主动拨出去**的：`--url http://127.0.0.1:8030`
是它的**回源目标**，不是它的监听地址；它唯一监听的是自己的 metrics 端口，实测
`Starting metrics server on 127.0.0.1:20241/metrics`，而那个端口是它自己挑的、
与 `-Port` 无关）。⇒ 「监听同一端口」数不到任何孤儿。
本波换成的判据是**命令行里含本脚本自己的标记** `pe_tunnel_<Port>`
（`cloudflared` 走 `--logfile`、`ssh` 走 `-E`，两者的路径里都含它），
**并且**进程名恰好是 `cloudflared.exe` / `ssh.exe` —— 两条**同时**成立才杀。
⚠️ 它比「监听同一端口」**更保守也更准**：不带端口信息的别人的隧道不会被误杀，
而**另一个端口上**的本脚本孤儿也照样能认出来（那正是「硬杀之后重开一个别的端口」那一档）。
本机实测命中过（§3）。

**顶回 4 · 本波改了 `frontend/scripts/smoke.mjs` 与 `backend/tests/test_serve.py`，两个都不在派单的文件清单里。**
* `smoke.mjs`：不改它，「公网档 smoke 全绿」这一格**不可能达成**（第 16 步 ⑦ 恒红），
  而派单 §3 第 2 条把这一格称为「甲方能完整用一遍的**最强证据**」。
  改法照 `PE_TRIAL` 的既有姿势（按档声明、两侧不同源、两个方向都响亮），
  ⚠️ **不是**放宽判据（硬规矩 #92）——首跑那次红就是它「会红」的证据。逐字理由见 §5。
* `test_serve.py`：**必须**改，否则它当场红两处 ——
  ① `assert len(rows) == 5`（`git ls-files --eol -- "*.ps1"` 的行数：本波加了第 6 个 `.ps1`）；
  ② `assert sorted(...) == ["serve.ps1", "trial.ps1"]`（仓库根 `scripts/` 的显式清单）。
  ⚠️ 两处都是**清单**，不是判据；⚠️ 而 **`.gitattributes` 一个字都没改**
  （既有的 `scripts/*.ps1 text eol=crlf` 那条规则的 `*` 本来就盖得住新文件，
  `git check-attr` 实测 `text: set / eol: crlf`）。

**顶回 5 · 派单 §6 第 ⑤ 条问「隧道下跑 smoke 全量值不值得」——同意控制者，值得，⚠️ 但要把成本说清。**
成本实测：**197 s**（本地 42 s）+ 把试用库写脏（故跑之前一律 `-Reset`，本波每档都重灌过）。
收益实测：它抓到了**唯一**那一拍「期望侧对档位无感」的问题（首跑 710 绿 / 1 红），
而那一格**用任何非浏览器客户端都测不出来**（`fetch` / `curl` / `Invoke-WebRequest`
照收 `Secure` cookie，不实施浏览器的安全策略）。⇒ **不跑它，本波会交出一个
「prod 在隧道下第 16 步 ⑦ 恒红」而没人知道的交付物。** 故不顶回，只是把账记清。

⚠️ 派单 §6 另外三格**核过、不顶回**：
① 「公网档跑 `prod`」——**实测成立**（格 1：`Set-Cookie` 含 `; Secure`、浏览器实存
`secure: true`、下一个请求 200），故**不退回 dev**；
② URL 文件路径 `.trial/public-url.txt`——同意（`git check-ignore` 实测被忽略、
`git ls-files` 底下空、路径只有一个所有者）；
③ 孤儿清理的判据会不会误杀——不会（两条同时成立 + 杀之前先打印完整命令行；
守卫另有红档半边钉住「不许出现 `Stop-Process -Name …` 一类裸杀」）。

### 没按派单做的（**3 处**，都在上面顶回里逐字交代过，此处只列清单）

1. `tables` 不与写死的 `28` 比，而与**本地那一格**比（顶回 1）。
2. 孤儿的判据不是「监听同一端口」，而是「命令行含本脚本的标记」（顶回 3）。
3. 多改了两个派单没点名的文件（`smoke.mjs` / `test_serve.py`），理由逐字见顶回 4。

⚠️ 另有**一处是加、不是减**（派单没要求，本波加了，如实报）：
`.trial/public-url.txt` 在 `finally` 里被**删掉**、陈旧的那一份在第 ① 步被**删掉**。
理由：那个文件的全部内容就是「**现在**能点的那一条链接」，
留一份写着死链接的文件比没有文件更坏（下一个人会照着它去点）。
⚠️ 而派单 §2 第 3 条要的是「链接要能被别人读到、能被脚本读到」——
它在**隧道活着的那个窗口里**照旧可读（那也正是它有效的唯一窗口）。

### 待清扫（**6 条**）

1. ⚠️ **`tests/pipeline/test_backfill.py` 那个 `sys.gettrace()` 跳过是「顺序敏感」的**（既有问题，本波没碰它）。
   同一个 `--cov=app/domain` 命令跑了**两遍**，两遍的结果不同：
   第一遍 `1606 passed`（**0 skipped**），第二遍 `1605 passed, 1 skipped`。
   那一拍的判据是 `if sys.gettrace() is not None: pytest.skip(...)`，
   而 `sys.gettrace()` 是不是 `None` 取决于 coverage 装的是 C tracer 还是 Python tracer
   ——本机 `pytest-randomly` 每遍换种子 ⇒ 顺序不同 ⇒ 那一格翻面。
   ⚠️ 它**不影响**任何断言的真假（跳的是「墙钟数量级哨兵」那一拍），
   而它会让「1592 + 1 skipped」这类基线数字**在两次跑之间漂一格**。
   处置建议：把判据从 `sys.gettrace()` 换成「`COVERAGE_PROCESS_START` / `--cov` 是不是在场」
   一类**与顺序无关**的信号。⚠️ 本波**没改它**（不在派单范围内，且改它要动一条既有的
   Ruling 12 的论证）。
2. ⚠️ **硬杀 `trial.ps1` 会留下 `pe_trial_csv_<PID>` 在 `%TEMP%`**（Task 1+2 登记过同一条，本波**又实测到一次**）。
   本波亲眼见到的两个：`pe_trial_csv_29480`（第一次硬杀留下的）、
   `pe_trial_csv_13292` / `pe_trial_csv_31188`（后续几轮）。
   它们的 `finally` 与 `tunnel.ps1` 的 `finally` 一样跑不到。
   ⚠️ 而 `tunnel.ps1` 为自己那一格**补了网**（第 ① 步的孤儿清理 + 陈旧 URL 文件清理），
   `trial.ps1` **没有**对应的补网 ⇒ **建议给 `trial.ps1` 也加一道**（判据同形：
   目录名前缀 `pe_trial_csv_` + 那个 PID 已经不在了）。⚠️ 本波收尾时手工清掉了它们（§8 有复核）。
3. ⚠️ **`ssh` 后端的「真的能拿到 URL」那一格没被验证**（本机这个网络过不去 KEX）。
   见顶回 2。⚠️ 若控制者裁定保留这一支，建议在**一台 22 端口出站放开的机器**上补一次端到端取证，
   并把 `lhr.life` 那个形状的实测原文补进 spec §13.17.2。
4. ⚠️ **`ssh` 那一支的 `ssh-debug.log` 读不出来**（`-E` 那个文件被 ssh 独占）。
   失败时那一段日志转储对它打印的是「（读不出来：文件被别的进程独占？）」。
   ⚠️ 影响很小（真因在 stderr 那一份里，而那一份是重定向到 `$LogFile` 的、读得到），
   而它是一处**看得见**的诊断缺口。处置建议：`-E` 那个文件也换成 `FileShare.ReadWrite`
   之外的姿势（例如干脆不给 `-E`，标记改落在别处）。
5. ⚠️ **`tools/cloudflared.exe` 的 sha256 没有与 Cloudflare 官方 checksum 文件独立比对过。**
   本波记了下载到的那一格（`86AEE401…D2B23C`），并与 cloudflared **自报**的
   `Checksum` 交叉核对过（逐字相同）——⚠️ 而自报值挡不住「下载源被换掉」。
   派单明说不要求比对官方 checksum 文件。处置建议：Task 4 的可分发 zip 若要把
   `cloudflared` 打进包里，**那时**必须补一次官方 checksum 的独立比对。
6. ⚠️ **quick tunnel 的地址是临时的**（每次重开都变、进程一死就失效），
   故「给甲方一条能长期用的链接」这件事**今天做不到**。
   `tunnel.ps1` 的 ⑥ 第 ⑥ 条与 URL 文件里都逐字写着这一句，
   并指了出路（「要长期链接请上 named tunnel + 一个真域名」）。
   ⚠️ 那一档要一个 Cloudflare 账号 + 一个真域名，**超出本计划范围**（计划 §3 只要 quick tunnel）。

### 关切（不顶回，但请控制者知道）

* ⚠️ **覆盖率口径 ②③ 的 `Cover` 那一列与基线记录差 1 / 5 点，而四个格子逐格相同。**
  本波复核到「这一差不可能由本波产生」（`backend/app` 与 `backend/scripts` 对 `71d1e4f`
  **零 diff**、测试数只增、随机序与固定序两遍逐字相同），逐条证据与三种量法的数
  都在 §8 那一节。⚠️ 请控制者裁定**基线口径**（带不带 `--cov-branch`），
  并把裁定结果写回账本 —— 否则下一波会再撞一次同一个 1 / 5 点。
* ⚠️ **公网档上「抢绑 + 无读审计」两条同时成立**，而这两条是 spec §13.15「给甲方念的那一页」
  的第 1 条。公网档是三条链接里唯一一条「任何知道地址的人都能打开」的 ⇒
  Task 5 的说明书里，公网那一条链接旁边**必须**把六条告示一起印上（计划 §5 第 ⑥ 点已经要求了）。
* ⚠️ **`tunnel.ps1` 打印的档位是「本进程读到的」，不是「服务实际的档位」**：
  两者是两个进程、环境变量不共享。若运维在终端 A 里设了 `PE_ENV=prod` 起服务、
  却在**没设**它的终端 B 里跑 `tunnel.ps1`，第 ③ 步会显示 `dev` —— 那不是服务真的在 dev 档。
  本波**没有**去猜服务的档位（Windows 上读另一个进程的环境块要 P/Invoke，
  而用一个错判据去冒充真值比不判更坏），而是逐字打印「**本进程**」两个字 +
  指向「起服务那个终端里 `serve.ps1` 打的那一行」。
  ⚠️ 故 `.EXAMPLE` 里逐字写了「请在**同样设过** `$env:PE_ENV` 的终端里跑」。
  ⚠️ 若控制者认为这一格必须**实测服务侧**，唯一干净的姿势是给 `/api/health` 加一格
  —— 而那会改 openapi 的响应体形状（虽然 `/api/health` 是「未定型响应」之一、
  加一格**不改 schema 一个字节**，见 `tests/test_main.py` 的 `HEALTH_UNTYPED_SCHEMA`），
  但会**破**「恰好四格」那道守卫。⇒ 本波**刻意没做**，请控制者裁定要不要做。

---

## ⑧ 最终验收

### 测试与覆盖率

| 格 | 基线 | 本波实测 | 结论 |
|---|---|---|---|
| 后端 passed（`--no-cov`） | 1593 | **1606 passed**（216.37 s，退出码 0） | **+13，只增不减** ✓ |
| 后端 passed（带 `--cov`） | 1592 + 1 skipped | **1605 passed + 1 skipped**（三次带 cov 的跑逐次相同：288.14 / 294.63 / 300.43 / 279.55 / 280.49 s） | 同形状 ✓（⚠️ §7 待清扫第 1 条） |
| 覆盖率 ① `app/domain` | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%** | ✓ **逐格相同** |
| 覆盖率 ② `app` | 7311 / 201 / 1778 / 115 / **97%** | **7311 / 201 / 1778 / 115 / 96%** | 前四格**逐格相同**；`Cover` 那一列差 1 点 ⚠️ 见下 |
| 覆盖率 ③ `scripts` + `app.static` | 583 / 173 / 164 / 24 / **74%** | **583 / 173 / 164 / 24 / 69%** | 前四格**逐格相同**；`Cover` 那一列差 5 点 ⚠️ 见下 |

⚠️⚠️ **`Cover` 那一列的两处差，如实报，并且它不可能是本波造成的**（四条证据）：

1. **`git diff --stat 71d1e4f HEAD -- backend/app` 与 `-- backend/scripts` 都是空的** ——
   本波**一行生产 Python 都没改**（全部改动面就 5 个文件：`.gitignore` /
   `scripts/tunnel.ps1` / `backend/tests/test_tunnel.py` / `backend/tests/test_serve.py` /
   `frontend/scripts/smoke.mjs`，其中三个是测试与脚本、两个不是 Python 生产码）。
   **没被改的源，覆盖率不可能因为「加了 13 条测试」而下降。**
2. **四个格子（Stmts / Miss / Branch / BrPart）逐格与基线相同** —— 而 `Cover` 那一列
   **不是**这四格的纯函数：coverage 的分母是 `Stmts + Branch`、分子是
   `已执行语句 + 已执行分支弧`，而**「已执行分支弧」这一格 term 报告不打印**
   （它由 `n_missing_branches` 决定）。⇒ 四格全同而 `Cover` 差几点，在算术上是可能的。
3. **不是测试顺序噪声**：口径 ③ 跑了**两遍**，一遍 `pytest-randomly` 随机序、
   一遍 `-p no:randomly` 固定序，两遍**逐字相同**（都是 `583 173 164 24 69%`，
   逐文件也相同：`app\static.py 80/3/28/1/96%`、`backup.py 142/14/40/6/88%`、
   `demo_bootstrap.py 145/112/30/2/20%`、`dump_openapi.py 39/20/8/2/45%`、
   `restore.py 157/23/52/12/82%`、`serve_app.py 20/1/6/1/92%`）。
4. 本机 coverage 实测是 **`Coverage.py, version 7.16.2 with C extension`**；
   而 coverage 的分支百分比**算法在版本间改过**。⚠️ 基线那两个百分数是哪一版、
   哪一条命令行量出来的，本波**无从复核**（报告里不印别人的取证过程）。

⇒ **结论：口径 ① 逐格相同；口径 ②③ 的四个格子逐格相同、`Cover` 那一列与基线的记录差
1 / 5 点，而这一差**不可能**由本波产生**（证据 1–3）。⚠️ 已登记为 §7 的**关切**一条，
请控制者用同一条命令行重量一次基线以对齐（本波用的三条命令行逐字写在下面）。

```
python -m pytest -q --no-header --cov=app/domain --cov-branch --cov-report=term
python -m pytest -q --no-header --cov=app        --cov-branch --cov-report=term
python -m pytest -q --no-header --cov=scripts --cov=app.static --cov-branch --cov-report=term
```

⚠️ 覆盖率第 ③ 口径**首跑量错了一次**，如实记：那条命令写的是 `--cov=app/static`
（**斜杠**），coverage 把它当成**模块名**去 import，报了
`CoverageWarning: Module app/static was never imported` ⇒ 那一遍只量到 `scripts`
（TOTAL **503 / 170 / 66%**），少了 `app.static` 那 **80** 条语句。
改成**点号**（`--cov=app.static`）之后 Stmts 从 503 变成 **583**，与基线对上。
⚠️ 前两口径首跑也**没带** `--cov-branch`，故只量到语句（`1268/0/100%` 与 `7311/201/97%`
——⚠️ 注意不带 branch 时口径 ② 的 `Cover` 是 **97%**，与基线记录的那个 97% 相同；
带上 branch 之后才变 96%）。⇒ **基线那两个百分数很可能是「不带 `--cov-branch`」量出来的**，
而那与它同时给出的 Branch/BrPart 两格矛盾（不带 branch 是不打印那两格的）。
这一格本波**不下断言**，只把两种量法的数都摆出来，请控制者裁定基线口径。

### 结构面 / 契约面 / 构建面

| 格 | 基线 | 本波实测 |
|---|---|---|
| 表数 | 28（`sqlite_master` 29） | `pe_trial.db` 29 / `pe_demo.db` 29（28 + `alembic_version`），`student` 各 60 ✓ |
| 迁移链 | 4 单头 | `alembic heads` = **`0ac943e0da9b (head)`** 一个头；`history` **4** 行 ✓ |
| 模型↔迁移残差 diff | 0 | 由 1606 passed 的 `tests/db/test_migration_chain.py` 覆盖 ⇒ **0** ✓（本波不动 schema） |
| 扫描面 / `_MODELS_PUBLIC_BASELINE` / `_MODELS_SUBMODULES` / 黄金用例 | 72 / 33 / 8 / 14 | 由 `tests/architecture/test_layering.py` 等覆盖，**1606 passed / 0 failed** ⇒ 逐个照旧 ✓ |
| openapi 五格 | 74 / 102 / 84 / 63（15+48）/ 3 | **74 / 102 / 84 / 63（15+48）/ 3** ✓ |
| openapi 未定型响应 / catch-all / `expected` | 24 / 0 / 26 | **24 / 0**；`expected` 那一格由 `smoke.mjs` 第 12 步的 **129/129** 条断言覆盖（四档全绿）✓ |
| openapi JSON | 420 367 B / `6058F97F09B35855` | **420 367 B / `6058F97F09B35855`**，三档 `PE_TRIAL` 逐字节相同 ✓ **一个字节都没变** |
| `npm run build` | 退出码 0 + 五个哈希 | 退出码 **0**；`index-Dm53XXz-.css` / `index-Wfsbvc3G.js` / `StudentDetail-kQIIimXN.js` / `AuditLogList-CKJ4Vvz4.js` / `ResourceIndex-DqalY3wm.js` ✓ 逐个相同 |
| `check:tokens` | 绿（36 / 下界 25） | 绿：**36** / 下界 25 ✓ |
| `check:dist` | 绿（25 产物 / 787 824 字符） | 绿：**25** / **787824** ✓ |
| 依赖清单守卫 | 一字不红 | **一字不红**：`pyproject.toml` / `package.json` / `.gitattributes` 三份对 `71d1e4f` 的 `git diff --stat` **全空**；`tests/test_dependencies.py` 6 条全绿；新增守卫 `test_cloudflared_is_a_machine_tool_and_never_enters_a_manifest` 也绿 ✓ |
| smoke 四档 | 三档 679 / 679 / 711 | **dev 679（56 s）· 产品 679（34 s）· 试用 711（42 s）· 公网 711（197 s）**，四档各 **18/18 步全绿 · 退出码 0** ✓ |

### 数据面与禁区

| 格 | 实测 |
|---|---|
| 四个数据指纹 + 18 个模板指纹 | 由 `tests/test_refdata.py`（16 条）/ `test_refdata_alerts.py`（35 条）/ `test_refdata_prescription.py`（56 条）覆盖，**全绿** ⇒ 逐字不变 ✓ |
| `git diff 71d1e4f HEAD -- backend/data` | **空** ✓ |
| `backend/pe.db` | **不存在**（`Test-Path` = `False`）✓ |
| `backend/data/seed/` | **0 文件**（`-Recurse` 数过）✓ |
| `pe_trial.db` / `tools` / `.trial` / `dist` / `backups` 未入库 | `git ls-files -- .trial tools` **空**；`git check-ignore -v` 逐个命中：`tools/cloudflared.exe`→`.gitignore:106:tools/`、`.trial/public-url.txt`→`.gitignore:116:.trial/`、`backend/pe_trial.db`→`:61`、`backend/pe_demo.db`→`:42`、`frontend/dist`→`frontend/.gitignore:18:dist/` ✓ |
| 三份 manifest + `.gitattributes` | `git diff --stat 71d1e4f -- backend/pyproject.toml frontend/package.json .gitattributes` **全空** ⇒ 零 diff ✓ |
| 禁跑的三个 CLI | `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` **一次都没跑**（灌库一律走 `demo_bootstrap.py`，由 `trial.ps1` / `demo.ps1` 调）✓ |

### 进程与临时目录（收尾复核）

| 格 | 实测 |
|---|---|
| 本波起的进程 | 8000 / 8010 / 8020 / 8030 / 5174 上的服务**全部已停**；**隧道进程全部已停**（`Get-CimInstance … Name='cloudflared.exe'` = **0 个**；`ssh.exe` = **0 个**）；**没有孤儿** ✓ |
| 5173 上那个不是我的 vite | **PID 20240 仍在**（本波一次都没动它）✓ |
| 公网链接 | **全部已关**（六条隧道地址逐条随进程一起失效；§6 实测过失效后的形状是 530 / `error code: 1033`）✓ |
| `$env:TEMP\p07t3\` | 已删并复验（见下） |
| `pe_trial_csv_*` / `pe_demo_csv_*` | 已删并复验（⚠️ 其中 `pe_trial_csv_29480` 是**硬杀**留下的，`finally` 没跑到 —— §7 待清扫第 2 条） |
| CDP 探针的 `p07t3-cdp-*` | 已删并复验（`Count = 0`） |
| `%TEMP%\pe_tunnel_8030\` | **刻意留着**（`tunnel.ps1` 的设计：它是排障现场，按端口命名、每次跑自己清空，故不累积）⚠️ 如实报：这一格是本波**没有**清的临时目录，理由逐字写在脚本的 `finally` 里 |
| `git status` | 干净（只剩本波该提交的那些，提交后为空）✓ |

### commit

| sha | 一句话 | 自洽吗 |
|---|---|---|
| `dd667cc` | `chore(gitignore)`：忽略 `tools/` 与 `.trial/` | ✓ 自洽（两条规则不要求目录存在；`git check-ignore` 当场可验） |
| `19e8322` | `feat(scripts+guards)`：`scripts/tunnel.ps1` + 13 条守卫 + `test_serve.py` 两处清单 | ✓ 自洽（依赖 `dd667cc` 的 `.gitignore` 两行，而它在前；`test_serve.py` 的 `len(rows)==6` 要求 `tunnel.ps1` 已入库，同一个 commit 里一起 `git add`） |
| `2ee49cf` | `feat(smoke)`：第四档「公网档」+ `PE_COOKIE_SECURE` | ✓ 自洽（不设该变量时三档行为逐字不变） |
| `<本报告那一个>` | `docs(spec)+report`：spec §13.17（8 小节）+ 本报告 | ✓ 自洽 |

⚠️ 四个 commit **逐个自洽**：任意一个 checkout 出来，`pytest` 都不会因为
「守卫要求的东西还没入库」而红（第 2 个 commit 依赖第 1 个的 `.gitignore`，
顺序是对的；第 3、4 个互不依赖）。

### spec

| 格 | 改前 | 改后 |
|---|---|---|
| 字节 | 549 289 B | **569 535 B** |
| 行 | 5192 | **5429** |
| 行尾 | 全 CRLF / 0 裸 LF | **全 CRLF（5429）/ 0 裸 LF** |
| BOM | 无 | **无** |
| sha256[:16]（工作树口径） | `03E0A4941F90AA6A` | **`102FE0C623F320E4`** |
| sha256[:16]（LF 归一口径） | `ED4A1AD9B89739AF` | **`9DF81386A199EE3E`**（LF 归一后 564 106 B） |

新增 **§13.17**（8 小节）：13.17.1 三条链接的档位矩阵（公网 = `prod`、局域网 = `dev`，
两档相反且都不许改）· 13.17.2 `cloudflared` 是本机工具不是项目依赖（三条路的实测）·
13.17.3 `tunnel.ps1` 的形状（七步、三个所有者一个都不当）· 13.17.4 两个**实测**抓到的真 bug ·
13.17.5 链接的寿命 = 进程的寿命，而硬杀会留下一个没人管的公网入口 ·
13.17.6 六条风险告示与 §1.2 / §13.9 / §13.15 的接线 ·
13.17.7 `smoke.mjs` 的第四档与 `PE_COOKIE_SECURE` · 13.17.8 定点变异四格。
⚠️ 而 `## 14. 待确认事项清单` 仍**恰好一处**（插入点核过），`### 13.16` 与 §14/§15 一个字节都没动。

### 定点变异（四格，派单 §4 第 ④ 条）

| # | 变异 | 守卫 | 结果 | 还原后 |
|---|---|---|---|---|
| M1 | 健康检查那一支改成恒不触发（`if ($null -eq $LocalBody)` → `if ($false)`） | `test_tunnel_ps1_health_checks_the_local_port_and_refuses_to_start_a_second_server` | **红 ✓**（`健康检查失败那一支不见了`） | 绿 ✓ |
| M2 | 「穿过公网复核」改成打**本地**那一格（`-Uri $RemoteHealthUrl` → `-Uri $LocalHealth`） | `test_the_public_url_is_reverified_over_the_internet_before_it_is_handed_out` | **红 ✓**（`④ b 不再穿过公网打 /api/health 了`） | 绿 ✓ |
| M3 | 把 `tools/` 从 `.gitignore` 拿掉 | `test_the_url_file_path_has_one_owner_and_gitignore_agrees` | **红 ✓**（`.gitignore 里少了 'tools/'`） | 绿 ✓ |
| M4 | 六条告示删一条（第 ③ 条抢绑） | `test_the_six_public_exposure_warnings_are_each_pinned_on_an_unambiguous_string` | **红 ✓**（`在语句里出现了 0 次（要恰好 1 次）`） | 绿 ✓ |

⚠️ 还原是**按字节核的**：改前存 sha256、改后 `shutil.copy2` 还原再比一次，
实测 `tunnel.ps1` sha256[:16] = `BDF22833C4B8D270`、`.gitignore` = `7D55F39AED2EA61B`，
两个都**与变异前逐字一致**。

⚠️ 写守卫时**自己踩到两格 needle 歧义**（与 §13.16.7 的 M5 同一族，如实记）：
① 「语句里不许出现 `uvicorn`」红在了 ③ 那一句人话上（它**印着**「起 uvicorn 归
`scripts\serve.ps1`」——那是指着别人说话）；② 「`dev` 那一档不许 `throw`」红在了
那一档自己的散文上（它**印着**「故它是一档可用的退路、本脚本不 throw」）。
两处的处置同一条：判据从「文本里含不含这个词」抬成「有没有一行**以它开头** /
在一条 `Write-Host` 里」——**提及不是本身**（硬规矩 #109）。
⚠️ 首跑 3 条红里第三条是 `test_serve.py` 那份 `scripts/` 清单（见顶回 4）。

---

## ⑨ 行尾复核（逐个被改文件，两个口径）

本机 `core.autocrlf` 实测 = **`true`**（`git config core.autocrlf`）。

| 文件 | `git ls-files --eol` | 工作树实测 | 该文件的口径 | 结论 |
|---|---|---|---|---|
| `.gitignore` | `i/lf  w/crlf  attr/` | 7 485 B / **116 CRLF / 0 裸 LF** / 无 BOM | 入库 LF、工作树 CRLF（靠 autocrlf） | ✓ |
| `scripts/tunnel.ps1` | `i/lf  w/crlf  attr/text eol=crlf` | **50 128 B / 761 CRLF / 0 裸 LF / 有 BOM** | `.ps1` = **CRLF + BOM**，且 `attr` 钉住检出恒 CRLF | ✓ |
| `backend/tests/test_tunnel.py` | `i/lf  w/crlf  attr/` | 46 890 B / **729 CRLF / 0 裸 LF** / 无 BOM | `.py` 入库 blob = **LF** | ✓ |
| `backend/tests/test_serve.py` | `i/lf  w/crlf  attr/` | 与改前同口径（只改了清单里的三处文字） | 同上 | ✓ |
| `frontend/scripts/smoke.mjs` | `i/lf  w/crlf  attr/` | 与改前同口径 | `.mjs` 入库 blob = **LF** | ✓ |
| `Document/2026-09-28-…设计spec.md` | `i/lf  w/crlf  attr/text eol=crlf` | **569 535 B / 5429 CRLF / 0 裸 LF / 无 BOM** | `Document/**/*.md` = **CRLF**（attr 钉住） | ✓ |
| `.superpowers/sdd/…/task-3-report.md`（本文件） | `i/-text  w/-text  attr/-text`（`.superpowers/**  -text`） | **纯 LF / 0 裸 CRLF / 无 BOM** | `.superpowers/**` = **`-text`**（双向零转换 ⇒ 工作树字节 == 入库 blob 字节） | ✓ |

⚠️ `backend/tests/test_tunnel.py` 有一格**如实记**：Write 工具首写出来是**纯 LF**
（`i/lf w/lf`），与本目录其余 `.py` 的工作树口径（`w/crlf`）不一致 ——
**入库 blob 两者都是 LF**（`autocrlf=true` 的 clean 侧），故守卫与 diff 都不受影响
（`git diff --exit-code` 退出码 0、`git diff --cached --stat` 空）。
本波仍把工作树**归一成 CRLF** 与同目录一致，免得下一次 `checkout` 触发一次
「git  touched it」的整文件重写；归一之后 `git status` 里那一格 `M` 是**stat 缓存**
（`git diff` 内容为空），`git add` 刷新之后消失。

⚠️ **两个口径都报**（派单 §5 要求）：
* **入库 blob 口径**：`.gitignore` / 三个 `.py` / `.mjs` / spec = **LF**；
  `scripts/tunnel.ps1` = **LF**（`attr/text eol=crlf` 的入库侧就是归一化成 LF）；
  本报告 = **LF**（`-text`，与工作树逐字节相同）。
* **工作树口径**：`.gitignore` / 三个 `.py` / `.mjs` / spec / `tunnel.ps1` = **CRLF**；
  本报告 = **LF**（`.superpowers/**  -text` ⇒ 不转换）。
* ⚠️ `tunnel.ps1` 的 **BOM 只在文件里、不在 blob 里**是错的口径 —— 本仓的 BOM
**入库也带着**（`attr/text eol=crlf` 只规定行尾，不剥 BOM），
故 `git cat-file -s` 出来的 blob 与工作树字节数**只差行尾**（761 个 CR）。

### 工作树字节 vs 入库 blob 字节（`git cat-file -s` 逐个核过）

| 文件 | 工作树 | 入库 blob | 差 | 该文件的 CRLF 个数 | 差 == CRLF 个数 |
|---|---|---|---|---|---|
| `Document/2026-09-28-…设计spec.md` | 569 535 | 564 106 | 5 429 | 5 429 | ✓ |
| `scripts/tunnel.ps1` | 50 128 | 49 367 | 761 | 761 | ✓ |
| `backend/tests/test_tunnel.py` | 46 890 | 46 161 | 729 | 729 | ✓ |
| `backend/tests/test_serve.py` | 104 421 | 102 621 | 1 800 | 1 800 | ✓ |
| `frontend/scripts/smoke.mjs` | 332 149 | 327 529 | 4 620 | 4 620 | ✓ |
| `.gitignore` | 7 485 | 7 369 | 116 | 116 | ✓ |
| `.superpowers/sdd/…/task-3-report.md`（本文件） | — | — | **0** | **0** | ✓ **逐字节相同**（`attr/-text` ⇒ 双向零转换） |

⚠️ 「差 == 该文件的 CRLF 个数」这一格是**承重的**：它证明工作树与 blob 的差别
**恰好只是行尾**，没有第二个字节级的意外（例如 BOM 被剥掉、或某处被工具重写）。
六个 CRLF 文件的差**逐个**等于它自己的 CRLF 个数；而本文件（`.superpowers/**  -text`）
的差是 **0**，即**工作树字节 == 入库 blob 字节**，与同目录的 `task-1-2-report.md`
口径**逐字相同**（两者都是 `i/lf w/lf attr/-text`）。
⚠️ 本文件**刻意不印自己的字节数与 sha256**（不动点问题；Task 1+2 在这上面绕了两圈）。

⚠️ 提交后 `git status --short` **为空**；未入库的产物逐个核过：
`git ls-files -- .trial tools` = 空、`-- "*.db"` = 空、`-- frontend/dist` = 空、
`-- backend/backups` = 空。
