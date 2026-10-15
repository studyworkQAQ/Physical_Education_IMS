# 厦大体育数智系统（原型）

厦门大学体育课的「体测 → 分层 → 处方 → 三源采集 → 预警 → 周报」闭环原型：
后端 FastAPI + SQLAlchemy 2 + SQLite（alembic 迁移链），前端 Vue 3 + Vite + Pinia。
⚠️ **完整规格、全部运行口径与交付须知住在
[`Document/2026-09-28-体育闭环原型-设计spec.md`](Document/2026-09-28-体育闭环原型-设计spec.md)
的 §13**；本文件只是入口，**一个数都不复述**（复述就是第二个所有者）。

## 一条命令跑起来

⚠️ 下面一律是 **Windows PowerShell 5.1** 的语法（`;` 分隔，**没有** `&&`），在**仓库根**执行。

**① 演示档** —— 灌一份 60 人的演示库 + 起服务（前台，`Ctrl-C` 停）：

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

产出 `dist-pack\pe-ims-trial-<时间戳>.zip`（⚠️ 已进 `.gitignore`）：里面是 `backend\`
（含 `data\` 那 24 个国标 / 常模 / 处方模板文件与 `migrations\`）+ `frontend\`
（`dist` 预构建 + 整条构建链）+ `Document\`（spec 与甲方试用说明书 = 技术对接依据）
+ `scripts\` + 本文件。**不含** `.git`、`node_modules`、任何 `.db`、内部账本，
以及 `tools\`（本机的隧道工具；公网链接由我方开，见说明书 §2 ①）。

解包到一个**空目录**之后，那台机器上要有的只有 Python 3.11+，两步：

```powershell
python -m pip install -e backend                              # 装运行时依赖（清单 = 包里的 backend\pyproject.toml）
powershell -ExecutionPolicy Bypass -File scripts\trial.ps1    # 灌一份全新试用库 → 起服务 → 打印链接与账号
```

⚠️ 缺依赖时那第二条命令会**自己检查并把上面第一条打印出来**，而**不替你 `pip install`**
（静默改你那台机器的 Python 环境不是交付物该有的形状）。
⚠️ 它缺省**不重建前端**（`trial.ps1` 透传 `-SkipBuild`），故一次都不查 node；
改了 `frontend\src` 要看见变化，请加 `-Build`（那就要 Node 20+ 与 `npm install` 跑过）。
⚠️ 要重置回干净的 60 人仿真库：`Ctrl-C` 停掉，再跑同一条并加 `-Reset`。

给试用者念的那一份是包里的 `Document\2026-10-15-甲方试用说明书.md`；
本文件是给开发者的入口 —— 两者**刻意不互相抄**（抄就是第二个所有者，改一处漏一处）。

## 起来之后看哪儿

| 去处 | 它是什么 |
|---|---|
| `http://<host>/` | 未登录会被路由守卫送去 `/login?next=<原路径>` |
| `http://<host>/api/health` | 存活探针，三格 `{"status","tables","students"}` |
| `http://<host>/docs` · `/redoc` · `/openapi.json` | 接口契约（⚠️ 两档都公开，见 §13.15 第 10 条） |
| `http://<host>/admin` | 管理台：23 个资源的目录 + 审计留痕（**仅 `role='admin'`**） |

## 演示账号去哪儿看

口令、管理员、以及一个**真**学号都由 `demo.ps1` 的 `[6/7]` 那一步**从库里打印**
（本文件刻意不抄第二份：抄了就会漏改，而漏改的那一处是要念给甲方听的）。
教师 `T0001` / `T0002`（`role='teacher'`）· 管理员 `T0003`（`role='admin'`）。

## 16 条路由去哪儿看

唯一所有者是 `frontend/src/router/index.ts` 的 `routes` 数组；
一张**逐条实测过**的表（路径 / 是什么 / 要什么身份）在 spec **§13.6**。

## 交付须知

spec **§13.15**（11 条，逐条都写了「实测取证住在哪一节」）。
