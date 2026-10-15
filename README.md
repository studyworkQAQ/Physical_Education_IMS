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
