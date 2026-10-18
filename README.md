# 厦大体育数智系统（原型）

厦门大学体育课的「体测 → 分层 → 处方 → 三源采集 → 预警 → 周报」闭环原型：
后端 FastAPI + SQLAlchemy 2 + SQLite（alembic 迁移链），前端 Vue 3 + Vite + Pinia。
⚠️ **完整规格、全部运行口径与交付须知住在
[`Document/2026-09-28-体育闭环原型-设计spec.md`](Document/2026-09-28-体育闭环原型-设计spec.md)
的 §13**；本文件只是入口，**一个数都不复述**（复述就是第二个所有者）。

## 一条命令跑起来

⚠️ 下面一律是 **Windows PowerShell 5.1** 的语法（`;` 分隔，**没有** `&&`），在**仓库根**执行。

**① 演示档** —— 灌一份演示库 + 起服务（前台，`Ctrl-C` 停；⚠️ 人数由 `demo.ps1 -Students` 决定，那个缺省值的唯一所有者是 `backend/scripts/demo_bootstrap.py` 的 argparse，本文件刻意不抄一个数字）：

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -Port 8000
```

**② 产品档** —— 一个 uvicorn 同时服务 API 与 `frontend\dist`（含 SPA fallback）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Port 8020
```

⚠️ `serve.ps1` 自己判 `dist` 是不是比 `src` 旧并重建；要强制用现有的 dist 加 `-SkipBuild`。
⚠️ 它**不灌数据**（那是 `demo.ps1` 的活）。⚠️ 而产品档缺省是 **dev 档**（cookie 不带
`Secure`、CORS 挂 `*`）：上 HTTPS 反代之后必须自己设 `PE_ENV=prod` 与 `PE_CORS_ORIGINS`。

**③ 前端开发档**（vite 热重载；另开一个终端，后端仍要起着）：

```powershell
cd frontend; npm install; npm run dev
```

vite 自己打印端口（本机实测：5173 被别的进程占着时它落到 **5174**）。
⚠️ 是 `localhost` 不是 `127.0.0.1`：vite 只绑 `::1`。

## 试用包（甲方 IT 在**他们自己的**机器上起一份）

⚠️ 这一档与上面三条**都不同**：它的口径是「在**别的**机器上、**只装 Python** 就起一份」
（⚠️ 不需要 Node、不需要 `npm install`、不需要 git；包里带的是**预构建**的 `frontend\dist`）。

```powershell
# 在仓库根打包（⚠️ 它不构建前端：frontend\dist 不在就报一句人话让你先构建）
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
```

产出 `dist-pack\pe-ims-trial-<时间戳>.zip`（⚠️ 已进 `.gitignore`；本机实测
**347 个文件**）：里面是 `backend\`（含 `data\` 那 24 个国标 / 常模 / 处方模板文件、
`migrations\`，⚠️ **以及 `tests\` 那 71 个测试文件**）+ `frontend\`（`dist` 预构建
+ 整条构建链）+ `Document\`（⚠️ **29 个文件** = 13 份 `.md` + 15 张截图 + 1 份 `.doc`；
那 13 份 `.md` 是 spec、甲方试用说明书、以及 11 份实施计划与取证记录）
+ `scripts\` + 本文件。**不含** `.git`、`node_modules`、任何 `.db`、`.superpowers\`
那一份内部账本，以及 `tools\`（本机的隧道工具；公网链接由我方开，见说明书 §2 ①）。

⚠️ 上面那两类「本来不给甲方看、而包里带着」的东西**刻意留着**，理由同一条：本包
同时是**技术对接依据**，而对接工程师要复核某一格口径时，`backend\tests\` 里那 71 个
文件是**可执行的判据**（比一段散文更难漂），`Document\` 里那 11 份计划是「这一格
为什么是这样」的**决策记录**。⚠️ 它们里面会有内部措辞（波次编号、顶回、待清扫），
读的时候请以 spec 与甲方试用说明书为准。

解包到一个**空目录**之后，那台机器上要有的只有 Python 3.11+，两步：
⚠️ **建议那个目录名不含空格**（例如 `D:\pe-ims\`，而不是 `D:\体育系统 试用\`）：
本版本已经能在含空格的路径下起服务，而那条路径上要经过的第三方工具
（压缩软件、Python 的包管理、机房里的安全软件）未必都能。

```powershell
python -m pip install -e backend                              # 装运行时依赖（清单 = 包里的 backend\pyproject.toml）
powershell -ExecutionPolicy Bypass -File scripts\trial.ps1    # 灌一份全新试用库 → 起服务 → 打印链接与账号
```

⚠️ 缺依赖时那第二条命令会**自己检查并把上面第一条打印出来**，而**不替你 `pip install`**
（静默改你那台机器的 Python 环境不是交付物该有的形状）。
⚠️ **包里没有一份「锁定版本」的文件**（`requirements.txt` / `*.lock` 一个都没有）：
上面那第一条装到的，是**你装的那一刻** PyPI 上满足 `backend\pyproject.toml` 那几条范围的
**最新**小版本，可能比本仓开发时用的更新。我方实测过更新的一档：`/openapi.json` 与开发环境
**逐字节相同**、说明书 §4 那四条试用路线的后端面全通 —— ⚠️ 那是**一次实测**、
**不是一条可以依赖的性质**（取舍与 Plan 08 的做法住在 spec §15 **G5**；给试用者念的
那一份是说明书 §2 ③，两边**刻意不互相抄**）。
⚠️ 它缺省**不重建前端**（`trial.ps1` 透传 `-SkipBuild`），故一次都不查 node；
改了 `frontend\src` 要看见变化，请加 `-Build`（那就要 Node 20+ 与 `npm install` 跑过）。
⚠️ 要重置回一份干净的仿真库：`Ctrl-C` 停掉，再跑同一条并加 `-Reset`
（⚠️ 人数本文件**刻意不写**：它的唯一所有者是 `demo_bootstrap.py` 的 `--students`，
而服务起来之后页面上那条告示里的 N 是从库里真数出来的 —— 抄一份在这里就是第二个所有者）。

给试用者念的那一份是包里的 `Document\2026-10-15-甲方试用说明书.md`；
本文件是给开发者的入口 —— 两者**刻意不互相抄**（抄就是第二个所有者，改一处漏一处）。

## 起来之后看哪儿

| 去处 | 它是什么 |
|---|---|
| `http://<host>/` | 未登录会被路由守卫送去 `/login?next=<原路径>` |
| `http://<host>/api/health` | 存活探针，**四格** `{"status","tables","students","trial"}`（⚠️ 第四格 `trial` 是 Plan 07 Task 1 加的：只有试用档为 `true`，前端顶那条「试用环境」告示读的就是它） |
| `http://<host>/docs` · `/redoc` · `/openapi.json` | 接口契约（⚠️ 两档都公开，见 §13.15 第 10 条） |
| `http://<host>/admin` | 管理台：23 个资源的目录 + 审计留痕（**仅 `role='admin'`**） |

## 演示账号去哪儿看

口令、管理员、以及一个**真**学号都由 `demo.ps1` 的 `[6/7]` 那一步**从库里打印**
（本文件刻意不抄第二份：抄了就会漏改，而漏改的那一处是要念给甲方听的）。
教师 `T0001` / `T0002`（`role='teacher'`）· 管理员 `T0003`（`role='admin'`）。

## 16 条路由去哪儿看

唯一所有者是 `frontend/src/router/index.ts` 的 `routes` 数组；
一张**逐条实测过**的表（路径 / 是什么 / 要什么身份）在 spec **§13.6**。

## 运维：留存清理（⚠️ 它**不会自己跑**）

四张表会随使用**单调增长**：`login_attempt` / `user_session` / `audit_log` /
`read_audit_log`（后两张是审计痕迹，含个人健康数据）。清它们的**唯一**命令是：

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\retention.ps1 -DryRun   # 先看将删多少行（⚠️ 一行都不删）
powershell -ExecutionPolicy Bypass -File backend\scripts\retention.ps1           # 真删（⚠️ 不可撤销）
```

⚠️ Windows 上没有 cron ⇒ 要它每天夜里自己跑，请让下面这一条**打印**出计划任务的注册
命令，再自己粘到一个**管理员**命令行里（⚠️ 它**不自动注册**，与 `serve.ps1` 不自动改
防火墙同一条口径：静默改甲方的机器不是交付物该有的形状）：

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\register_retention_task.ps1 -DbUrl "sqlite:///<绝对路径>/pe_trial.db"
```

⚠️ 三件事如实说：① **删之前不自动备份** —— 要留后路请**先**跑一次
`backend\scripts\backup.ps1`（注册脚本会把「备份任务排在清理前面 30 分钟」那一条也
打印出来）；② 四个保留窗口的缺省值与下界**只有一个所有者**
（`backend\scripts\retention.py`），本文件刻意**不抄一个数字** —— 跑一次 `-DryRun`
就会把四张表各自的窗口与截止时刻逐行打印出来；③「为什么是这四个数、判据长什么样、
守卫与定点变异」住在 spec **§13.24**，而给甲方念的那一句在 spec **§13.15 第 6 条**。

## 运维：备份与恢复（⚠️ 加密是**可选**的、缺省**不加密**）

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1                 # 备一份（⚠️ 缺省一份旧的都不删）
powershell -ExecutionPolicy Bypass -File backend\scripts\backup.ps1 -Keep 14        # 备一份并只留最近 14 份
$env:PE_BACKUP_KEY = "<一个只有运维知道的口令>"                                     # ⚠️ 设了它，产物才是**加密档**
powershell -ExecutionPolicy Bypass -File backend\scripts\restore.ps1 pe-<UTC 时间戳>.db   # 恢复（⚠️ 先停服务）
```

⚠️ 四件事如实说：① **不设 `PE_BACKUP_KEY` 就是明文** —— 产物是一个任何 SQLite 客户端
都能直接打开的整库副本（里面是全校学生的出生日期、体成分、体测结果与处方），
脚本会把这一段**响亮地**打印出来（⚠️ 不是报错：改前的缺省行为就是不加密）；
② **口令不走命令行**（`backup.ps1` 刻意**没有** `-Key` 参数：Windows 上任何同机进程
都读得到别人完整的命令行），⚠️ 也**从不打印**它的任何一部分（长度、sha、base64 都不印）；
③ **口令丢了那一份就打不开**（本仓刻意不做密钥托管、也没有第二个后门：
`restore --no-verify` 跳的是侧车那一格，完整性校验那一格跳不掉），
请把它记在与备份**分开**的地方；④ ⚠️ **弱口令 + PBKDF2 也挡不住离线爆破** ——
这一层是「**备份文件被捡到也读不出**」级别的保护，⚠️ **不是**全盘加密的替代品
（在线的那一份库今天**仍然是明文**）。
⚠️ 恢复吃**两种**产物（改前那些明文备份照样恢复得了）：它按**产物头**认、不按扩展名。
⚠️ 产物形状、为什么不是 AES-GCM、四档失败方向、`-Keep` 的判据与守卫/定点变异
住在 spec **§13.25**，而给甲方念的那一句在 spec **§13.15 第 7 条**。

## 交付须知

spec **§13.15**（11 条，逐条都写了「实测取证住在哪一节」）。
