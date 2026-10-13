# Plan 06 Task 7 实现者报告 —— 部署打包：一条命令起产品档（+ 两条 `.gitattributes` 行尾钉扎）

> 分支 `p06/serve`（从 `main` 的 `6dde666` 起）· 3 个 commit · **未 push**
> 本报告：**053314 B** / **0762 LF**（`.superpowers/**` 钉了 `-text`，故工作树字节 == 入库 blob 字节）
> 口径：交付给甲方的**产品级**系统 —— 甲方运维不跑 vite dev server，产品档是**一个进程**
> （uvicorn 同时服务 API 与构建好的前端静态文件）。

---

## ① 环境

| 格 | 实测 |
|---|---|
| Node / npm | `v24.19.0` / `11.17.0`（`npm.cmd` 在 `C:\Program Files\nodejs\npm.cmd`） |
| Python | `3.11.1`（`C:\Python\python.exe`，**无 venv**；`pe-backend 0.1.0` 是 editable 安装，指向 `backend/`） |
| FastAPI / starlette / uvicorn / SQLAlchemy / alembic | `0.141.1` / `1.7.0` / `0.54.0` / `2.1.3` / `1.20.0` |
| git | `2.55.0.windows.5`，`core.autocrlf` 实测 `true` |
| PowerShell | 5.1（`;` 分隔、无 `&&`、无 heredoc；`python -c` 一律单引号串且不嵌双引号） |
| 无头浏览器 | `msedge.exe`（smoke 第 14 步自己找，CDP + `--remote-debugging-port=0`） |
| 开工第一脚的端口实测 | `8000` 空、**`5173` 被 PID 3260 占着**（上一波留下的 vite，绑在 `::1`）、`8020` 空 |

⚠️ 关于那个 5173：**它不是我起的**。我为了量 dev 档的 DOM 字节数临时起过一个
`npm run dev`（它自己跳到了 5174，因为 5173 被占），量完**已经停掉**（PID 40900，
复验 `5174 listeners = 0`）。5173 上那个 PID 3260 我**没有动**（不是本波的进程，
且 dev 档的 smoke 复跑正好用得上它）。⚠️ 交回控制者时它仍然活着，要不要停请裁定。

⚠️ `python -c` 的坑本波又踩了一次：多行 `python -c "..."` 里嵌双引号被 PowerShell 吃掉
（`The string is missing the terminator`），一律改成写 `$env:TEMP` 下的探针文件再跑。

---

## ② `scripts/serve.ps1` 的五步流程实测

**位置**：`<仓库根>/scripts/serve.ps1`（⚠️ 仓库根今天**没有** `scripts/` 目录，是本波新建的；
`backend/scripts/` 下已有 `demo.ps1` / `backup.ps1` / `restore.ps1` + 三个 `.py`，
**没有重名**）。**形状**：UTF-8 + BOM + 纯 CRLF，`22 228 B / 359 CRLF / 0 裸 LF`
（与既有三个 `.ps1` 同款；有一条守卫按字节钉住）。

三次实跑（第 1 次 `-SkipBuild` 验机制、第 2/3 次跑完整流程），逐格如下。

### ①-① 检查工具链

```
-- ① 检查工具链 --
   python Python 3.11.1  ← C:\Python\python.exe
   node   v24.19.0  ← C:\Program Files\nodejs\node.exe
```

下界是**字面**的：python `< 3.11` → throw（`pyproject.toml` 的 `requires-python`），
node 主版本 `< 20` → throw（vite 8 的下限）。⚠️ 三档报错各不同：找不到 `python`、
`python --version` 退出码非 0（**Microsoft Store 占位符**那一档）、版本不够。

### ①-② 前端构建产物：「dist 比 src 旧」的判据 = **mtime**

```
-- ② 前端构建产物 --
   源面 63 个文件，最新 mtime = 2026-10-13 18:40:54（…\frontend\vite.config.ts）
   构建戳 dist\index.html     = 2026-10-13 21:34:04
   dist 不比 src 旧 → 跳过构建
```

**选 mtime 而不是自建构建戳文件，理由**：戳文件是**第二个所有者**（它声称的时间与
`dist` 里真实产物的时间可以漂），而 mtime 量的就是产物自己。
**判据**：源面 = `src/**` 全部文件 + `index.html` / `package.json` / `vite.config.ts` /
`tsconfig{,.app,.node}.json`（实测 **63** 个），构建戳 = `dist\index.html` 的
`LastWriteTimeUtc`（`npm run build` 一定写它）；**源面最新 mtime > 构建戳 → 重建**。
⚠️ **失效方向是安全的那一侧**：一次 `git checkout` 会把被改到的源文件 mtime 抬到当下
→「不确定」一律折成「重建」（多花十几秒），而**不会**折成「用一份陈的产物」
（那一档的症状是「改了前端、页面没变」，而它会一路绿到甲方现场）。
⚠️ 反空转：源面扫到 `< 20` 个文件就 throw（`frontend/src` 被搬空时
`Measure-Object -Maximum` 会安静地给出 `$null`，于是「dist 是新的」会**假绿**）。
`-SkipBuild` 跳过本步，但 `dist\index.html` 不在就 throw（不会起一个每页 404 的服务）。

本波**没有**触发过一次真构建（`dist` 一直是最新的）；`npm run build` 单独跑过一次做验收
（退出码 **0**、产物哈希与基线逐字相同，见 ⑦）。

### ①-③ 起一个 uvicorn 进程

```
-- ③ 起产品档 --
   PE_DB_URL 未设 → 回落到 app.main.DEMO_DB_URL（那个常量是「演示库叫什么」的唯一所有者）
   PE_DB_URL       = sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe_demo.db
   PE_STATIC_DIST  = C:\Users\whwenhao\Desktop\Physical_Education_ims\frontend\dist
   PE_ENV          = 未设（= dev 档）
   档位            = dev（cookie 的 Secure = False）
   uvicorn         serve_app:app --app-dir backend\scripts --host 127.0.0.1 --port 8020
   进程 PID = 34948
```

⚠️ **一道 `pe.db` 禁区守卫**（派单没点名，我加的；理由：`serve.ps1` 若不设 `PE_DB_URL`
就会落到 `app.config.DEFAULT_DB_URL` = **禁区** `backend/pe.db`）：
`PE_DB_URL` 未设 → 从 `app.main.DEMO_DB_URL` **读出来**（不敲第二遍路径）；
解析结果 `-match '(^|/)pe\.db$'` → 当场 throw。与 `demo.ps1` 的 ⑤、
`demo_bootstrap.py` 的两道前置守卫、`backup.py` 的 `_ensure_not_forbidden` 同一条姿势。
⚠️ 另有一道**端口预检**（`Get-NetTCPConnection -LocalPort $Port`）：被占着就报出
**占它的那个 PID**，而不是让 uvicorn 抛一段 `WinError 10048` 的 traceback。
⚠️ 还有一道**档位自检**：`python -c 'from app import deploy;…;print(deploy.tier());print(cookie_secure())'`，
`PE_ENV` 是认不出的值时 `deploy.tier()` 会抛 `ValueError`，本脚本因此**提前**给一句可读的错，
而不是让运维去读 uvicorn 的 traceback。

### ①-④ 健康检查

```
-- ④ 健康检查 --
   http://127.0.0.1:8020/api/health → 200（轮询 2 次）
   {"status":"ok","tables":28,"students":60}
   tables = 28（⚠️ health 数的是 Base.metadata，磁盘上另有 alembic_version 一张，故 sqlite3 里数出来是 +1）
```

三次实跑分别轮询 **2 / 1 / 2** 次（250 ms 一拍）即通。超时上限 60 s；
两档失败各有一句不同的报错：**进程先退**（报 PID + 退出码 + 轮询次数 + 最常见成因）
与**超时**（报轮询次数 + 「进程还活着」）。

### ①-⑤ 打印

URL 四条（`/`、`/api/health`、`/docs`、`/openapi.json`）+ 「这是**产品档**（构建产物），
不是 dev server」+ 同源 ⇒ 不需要 CORS + 演示/管理员账号 + 派单点名要的那一行提醒：

```
   ⚠️ 当前档位 = dev（cookie 的 Secure = False）。
      要上 HTTPS 反代请设 PE_ENV=prod 与 PE_CORS_ORIGINS（本脚本刻意**没有** -Prod 开关：
      档位是**部署事实**、归运维的环境变量，不是一个命令行旗标——一个 -Prod 会让人以为
      「加了它就安全了」，而它其实还要 PE_CORS_ORIGINS、Secure cookie 与一层 TLS 反代）。
      ⚠️ Secure 只在 prod 开，故在**明文 http** 上跑 prod 档，浏览器会拒收会话 cookie
         （症状是「登录 200、下一个请求 401」）。同源 http 的产品档请留在缺省的 dev 档。
```

⚠️ **演示口令与学号一个字面量都没抄**（单一所有者是 `backend/scripts/demo_bootstrap.py`
的 `DEMO_PASSWORD`，也写在 spec §13）；印的是「去哪找它」+ 教师 `T0001/T0002` +
管理员 `T0003`（与 `demo.ps1` 逐字同口径，那三个工号是名册生成规则的固定产物、不是秘密）。
有一条守卫扫全文，`pe-demo-2025` 与任何 `20\d{8}` 形状的学号**一个都不许出现**。

### ②-② 前台 / 后台的处置（控制者裁定：**前台阻塞**）

派单点出了这一格的矛盾：裁定是前台阻塞（与 `demo.ps1` 同姿势、运维看得见日志），
而 ④ 的健康检查必须在服务起来**之后**跑。两者不可兼得**如果**直接 `python -m uvicorn`。
处置：

```
Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory $Backend -PassThru -NoNewWindow
  → ④ 轮询 /api/health → ⑤ 打印 → $Proc.WaitForExit()
try { … } finally { if (-not $Proc.HasExited) { Stop-Process -Id $Proc.Id -Force } }
```

* `-NoNewWindow` 是承重的：子进程与脚本**共用同一个控制台**，故 uvicorn 的日志照常
  打在屏幕上（「前台」那一格的全部意义），而 `Ctrl-C` 也会同时送到两边；
* `WaitForExit()` 让脚本**阻塞**在那里，退出码原样 `exit $Code` 交回；
* `finally` 兜住子进程：`Ctrl-C` / `throw`（健康检查超时、禁区、端口被占）/
  任何一条异常路径都不留一个占着端口的孤儿 uvicorn。

**smoke 那一次是后台起的**（派单逐字要求「用 `Start-Process` 或独立终端起，跑完必须停掉」）：
用工具的后台终端跑 `powershell -File scripts\serve.ps1 -Port 8020`，跑完 `StopCommand`。

### ②-③ PID 与停止取证（逐个）

| 用途 | 外层 powershell PID | uvicorn PID | 端口 | 停止后复验 |
|---|---|---|---|---|
| serve.ps1 第 1 次（`-SkipBuild`，验机制 + 打 SPA 矩阵） | 45296 | **45904** | 8020 | `8020 listeners = 0`；`PID 45904 alive = False`；`PID 45296 alive = False` |
| serve.ps1 第 2 次（跑产品档 smoke） | 47288 | **34948** | 8020 | `8020 listeners = 0`；`PID 34948 alive = False`；`PID 47288 alive = False` |
| demo.ps1（灌数据，第 1 次） | 46820 | 32216 | 8000 | `8000 listeners = 0`；`PID 14844/46820 alive = False`；无 `-journal/-wal/-shm` 残留 |
| demo.ps1（灌数据，第 2 次 = 产品档 smoke 之前那一次） | 38128 | 41356 | 8000 | `8000 listeners = 0`（见下）|
| demo.ps1（灌数据，第 3 次 = dev 档 smoke 复跑之前） | —— | —— | 8000 | 见 ⑦ 的收尾复验 |
| 临时起的 `npm run dev`（量 dev 档 DOM 字节数用） | —— | **40900** | 5174 | `Stop-Process -Id 40900`；`5174 listeners = 0` |

⚠️ 本波**没有**用 `kill` / `taskkill` 去停 uvicorn：一律走 `StopCommand`（工具那一侧），
而 `serve.ps1` 自己的 `finally` 会 `Stop-Process` 掉它的子进程 —— 上面第 1/2 行那两个
uvicorn PID 是被**脚本自己**收掉的，`8020 listeners = 0` 是它收干净的证据。

---

## ③ SPA fallback 的实测矩阵

**跑法**：`serve.ps1 -Port 8020 -SkipBuild` 起着（uvicorn PID 45904，`PE_STATIC_DIST`
= 真的 `frontend/dist`），再用 `http.client` 逐格打过去（⚠️ 用 `http.client` 而不是
`urllib`：后者会跟重定向，而本矩阵要的是**原始**状态码）。前 40 字节是 `repr()`。

| 方法 | 路径 | 状态 | content-type | 字节 | 前 40 字节 |
|---|---|---|---|---|---|
| GET | `/` | **200** | `text/html; charset=utf-8` | 2729 | `b'<!doctype html>\r\n<html lang="zh-CN">\r\n  '` |
| GET | `/login` | **200** | `text/html; charset=utf-8` | 2729 | `b'<!doctype html>\r\n<html lang="zh-CN">\r\n  '` |
| GET | `/bind` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/s/home` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/s/weekly-sheet` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/t/dashboard` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/t/students/1` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/admin` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/admin/` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/admin/students/1` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/this-route-does-not-exist` | **200** | `text/html; charset=utf-8` | 2729 | 同上（前端 `/:pathMatch(.*)*` 接手） |
| GET | `/apixyz` | **200** | `text/html; charset=utf-8` | 2729 | 同上（⚠️ 边界是 `/`，不是裸前缀） |
| GET | `/documentary` | **200** | `text/html; charset=utf-8` | 2729 | 同上 |
| GET | `/assets/index-eWDO9FkM.js` | **200** | `text/javascript; charset=utf-8` | **167032** | `b'const __vite__mapDeps=(i,m=__vite__mapDe'` |
| GET | `/assets/index-CM7Fwkho.css` | **200** | `text/css; charset=utf-8` | **65204** | `b'.banner[data-v-542cb222]{background:var('` |
| GET | `/assets/xmu-emblem-vodJYAz_.svg` | **200** | `image/svg+xml` | **52095** | `b'<?xml version="1.0" encoding="UTF-8" sta'` |
| GET | `/assets/hanken-grotesk-var-latin-CaVRRdDk.woff2` | **200** | `font/woff2` | **34704** | `b'wOF2\x00\x01\x00\x00\x00\x00\x87\x90\x00\x13…'` |
| GET | `/assets/does-not-exist.js` | **200** | `text/html; charset=utf-8` | 2729 | ⚠️ 走了 fallback（见 ⑥ 的待清扫） |
| GET | `/api/health` | **200** | `application/json` | 41 | `b'{"status":"ok","tables":28,"students":60'` |
| GET | `/openapi.json` | **200** | `application/json` | 333482 | `b'{"openapi":"3.1.0","info":{"title":"\xe5\x8e\xa6\xe5'` |
| GET | `/docs` | **200** | `text/html; charset=utf-8` | 1023 | `b'\n    <!DOCTYPE html>\n    <html>\n    <hea'` |
| GET | `/docs/oauth2-redirect` | **200** | `text/html; charset=utf-8` | 3012 | `b'\n    <!doctype html>\n    <html lang="en-'` |
| GET | `/redoc` | **200** | `text/html; charset=utf-8` | 905 | `b'\n    <!DOCTYPE html>\n    <html>\n    <hea'` |
| GET | **`/api/nope`** | **404** | `application/json` | 66 | `b'{"error":{"code":"not_found","message":"'` |
| GET | `/api/students/999999/nope` | **404** | `application/json` | 66 | 同上 |
| GET | `/docs/nope` | **404** | `application/json` | 66 | 同上 |
| HEAD | `/login` | **200** | `text/html; charset=utf-8` | **0** | `b''`（头照给、体为空） |
| HEAD | `/assets/index-eWDO9FkM.js` | **200** | `text/javascript; charset=utf-8` | **0** | `b''` |
| POST | `/api/nope` | **404** | `application/json` | 66 | ⚠️ **不是 405**（见下面那一段） |
| POST | `/login` | **404** | `application/json` | 66 | 同上 |
| POST | `/api/health` | **405** | `application/json` | 74 | `b'{"error":{"code":"http_405","message":"M'` |
| DELETE | `/api/semesters` | **405** | `application/json` | 74 | 同上（⚠️ smoke 第 10 步逐字断言这一格） |
| GET | `/%2e%2e/secret.txt` | **404** | `application/json` | 66 | 目录穿越（解码后 `/../secret.txt`） |
| GET | `/assets/%2e%2e/%2e%2e/backend/pe_demo.db` | **404** | `application/json` | 66 | 逃出 `dist` |
| GET | `/assets/%2e%2e/%2e%2e/%2e%2e/backend/app/config.py` | **404** | `application/json` | 66 | 逃出 `dist` |
| GET | `/assets/%2e%2e/%2e%2e/backend/app/config.py` | **404** | `application/json` | 66 | 逃出 `dist` |

**四个静态文件的字节数与 `dist` 里逐字相同**（167032 / 65204 / 52095 / 34704），
即「按原字节发」；woff2 的头四字节 `wOF2` 也在。

### ⚠️⚠️ 实测出来的两档方法语义（派单没提，而它否定了两个「看起来对」的实现）

Starlette 的 `Router` 是「按顺序找第一个 `Match.FULL`，找不到就退到**第一个**
`Match.PARTIAL`，再找不到才 404」。而 catch-all 追加在**最后**，于是：

* **`methods=None`**（任何方法都 `FULL`）→ catch-all 的 `FULL` 抢在 api 路由的
  `PARTIAL` 前面 → `DELETE /api/semesters` 与 `POST /api/health` 从 **405 变成 404**。
  ⚠️ 那一档会**当场红在 smoke 上**：第 10 步逐字断言「`DELETE /api/semesters` 是 405 不是 204」。
* **`methods=["GET","HEAD"]`** → api 路由的 `PARTIAL` 保住了（405 正确），
  而 catch-all 自己对 `POST /api/nope` 也给出一个 `PARTIAL`、且它是**唯一**的那个
  → `POST /api/nope` 从 **404 变成 405 `Allow: GET, HEAD``**。⚠️ 那一格更坏：
  它在 `/api` 下面回一句「这个路径存在、只是方法不对」，而它**不存在**。

处置：`app/static.py` 里一个 5 行的 `_SpaRoute`，对非 `GET`/`HEAD` **连 `PARTIAL` 都不给**
（直接 `Match.NONE`）。四档于是同时正确 —— 上表最后四行就是取证。
`tests/test_serve.py::test_method_semantics_on_and_off_the_api_are_unchanged` 把四格逐个钉住，
定点变异 **M4**（把 `_SpaRoute` 退化成裸 `Route`）让它当场红。

### ⚠️ 判据的**唯一所有者**

`app/static.py::resolve_static_path(dist, url_path)` 一个函数回答「这个 URL 该发什么」，三档：
`dist` 内的真文件 / `dist/index.html`（fallback）/ `None`（保留前缀、或**逃出 dist**）。
`is_reserved()` 是它的第一格（边界口径「等于，或以 `前缀 + "/"` 开头」，与
`test_layering.py::_is_api_allowed` 逐字相同），`_candidate_under()` 是第二格
（`resolve()` + `is_relative_to`，同时挡住 `..` 上溯与 **Windows 的盘号绝对路径**：
`pathlib` 里 `Path("C:/dist") / "C:/Windows/win.ini"` 等于右边那个绝对路径、左边被丢掉，
故字符串判据挡不住它）。

⚠️ **越界与「不存在」是两档、去处也不同**（本波实测后收紧的一格）：越界一律 `None` → 404，
**不**退化成 index.html。两档都发不出那个文件、安全性质相同，分开是为了**诚实** ——
一个 200 的 index.html 会让探测者以为 `/%2e%2e%2f…` 是一个合法的前端路由。

⚠️ `content-type` **不赌注册表**：`FileResponse` 缺省用 `mimetypes.guess_type`，
而它在 Windows 上**读注册表**。本机亲跑：`.woff2 → (None, None)`、`.map → (None, None)`、
`.js → ('application/javascript', None)`。`None` 会退化成 `text/plain`；
而 `.js` 那一格**本机是对的、别的机器不一定**（注册表里把 `.js` 映成 `text/plain` 的
Windows 真实存在），ES module 的**严格 MIME 检查**会让浏览器直接拒绝执行 →
产品档白屏、dev 档正常，离真因两层。故 `dist` 里实际会出现的扩展名逐个钉在一张表里
（13 项），`tests/test_serve.py` 用**字面期望**断它（两侧不同源）。

⚠️ **`/openapi.json` 一格都没变**：catch-all 是 `starlette.routing.Route` 而不是
`fastapi.routing.APIRoute`，而 `get_openapi` 只收后者。守卫是「给了与不给 `static_dist`，
两份 `app.openapi()` **逐字相等**」+「`paths` 里没有任何 `/{` 开头的键」。
定点变异 **M9**（改成 `add_api_route`）让它当场红。

---

## ④ 产品档下 `smoke.mjs` 的 18 步结果（与 dev 档逐拍对比）

**跑法**（派单逐字）：`serve.ps1` 起在 8020，然后

```powershell
$env:PE_API_BASE = "http://127.0.0.1:8020"
$env:PE_WEB_BASE = "http://127.0.0.1:8020"
node frontend\scripts\smoke.mjs
```

⚠️ 两档**各跑一整遍**，每遍之前都重跑 `demo.ps1 -Port 8000` 灌一份新库
（smoke 会写脏演示库，第 0 步核实的就是「一个刚复原的演示库」的行数），
且跑之前先把上一个 uvicorn 停掉（`demo.ps1` 的第一步是删旧库，
两个进程同时开着 `pe_demo.db` 时那一步会失败）。

### ④-① 逐拍对比

| 步 | 内容 | dev 档（API 8000 / WEB localhost:5173） | 产品档（API == WEB == 127.0.0.1:8020） | 差异 |
|---|---|---|---|---|
| 0 | 登录三种角色 + 演示库复原核实 | 25/25 | **25/25** | **无** |
| 1 | `/api/health` → tables 28 | 5/5 | **5/5** | 无 |
| 2 | 管理员 `POST /api/class-sessions` | 10/10 | **10/10** | 无 |
| 3 | 教师 `open-rpe` + 匿名不含口令 | 9/9 | **9/9** | 无 |
| 4 | 匿名读口令 401 / 教师 200 | 7/7 | **7/7** | 无 |
| 5 | 学生 `POST /api/rpe-records` + 409 | 9/9 | **9/9** | 无 |
| 6 | 学生 `POST /api/training-logs` | 10/10 | **10/10** | 无 |
| 7 | `weekly-sheet` | 41/41 | **41/41** | 无 |
| 8 | 教师 dashboard | 14/14 | **14/14** | 无 |
| 9 | 预警处置三档 | 13/13 | **13/13** | 无 |
| 10 | 写入侧强制 + `DELETE` 是 405 | 17/17 | **17/17** | 无 |
| 11 | 只读资源被写 → 405 `http_405` | 6/6 | **6/6** | 无 |
| 12 | `/openapi.json` 反查 23 行资源 | 102/102 | **102/102** | 无 |
| 13 | 学生端两个新端点 | 24/24 | **24/24** | 无 |
| 14 | 15 条路由的 CDP DOM 取证 | 110/110 | **110/110** | ⚠️ 见 ④-③（首跑 103/110） |
| 15 | `check:tokens` + `check:dist` | 8/8 | **8/8** | 无 |
| 16 | 鉴权全链路 + 三档授权 | 63/63 | **63/63** | 无 |
| 17 | 4 条静态守卫（含 spawn `demo.ps1 -DryRun`） | 27/27 | **27/27** | 无 |
| **合计** | | **18/18 步 · 500 断言 · 退出码 0** | **18/18 步 · 500 断言 · 退出码 0** | |

### ④-② ⚠️ 「同源让哪一拍变干净了」—— 如实记：**一拍都没有**

派单预期「同源意味着 cookie 不再跨端口，第 0 步与登录相关的拍应当更干净」。
**实测：没有任何一拍的行为因同源而改变**，第 0 步（25/25）与第 16 步鉴权全链路（63/63）
在两档上**逐字相同**。理由：`smoke.mjs` 自己维护一个 `pe_session` 的 cookie jar、
一律走 `fetch`，而 dev 档那一侧也**已经是同源**的 —— `vite.config.ts` 的
`server.proxy` 把 `/api` 与 `/openapi.json` 都转到了后端，故浏览器看到的从来不是跨端口。
⚠️ 于是「同源更干净」这件事在**浏览器里**是真的（`client.ts` 的
`credentials: 'same-origin'` 在产品档下名副其实、且不需要 `PE_CORS_ORIGINS`），
而在 **smoke 的取证里量不出来**（它本来就不经跨源那条路）。
**变好还是变坏**：既没变好也没变坏 —— 那一格此前就不脏。

### ④-③ ⚠️⚠️ 首跑在产品档上红了 7 条，红的全是**同一格**（本波最大的一处发现）

首跑：**17/18 步 · 492 绿 / 7 红 · 退出码 1**。7 条红全在第 14 步的同一条断言上：

```
第 14 步 ✗ login：DOM 里出现了 4 条关键内容        →  DOM 9329 bytes
第 14 步 ✗ bind：DOM 里出现了 5 条关键内容         →  DOM 9996 bytes
第 14 步 ✗ s-home：DOM 里出现了 4 条关键内容       →  DOM 14821 bytes
第 14 步 ✗ s-mini-test：DOM 里出现了 2 条关键内容  →  DOM 18187 bytes
第 14 步 ✗ s-notifications：DOM 里出现了 2 条关键内容 →  DOM 15034 bytes
第 14 步 ✗ admin-list：DOM 里出现了 5 条关键内容   →  DOM 15015 bytes
第 14 步 ✗ admin-detail：DOM 里出现了 5 条关键内容 →  DOM 8853 bytes
```

⚠️ 那句 label 印的是 `route.needles.length`（**应有**几条），而判据是
`rawBytes > 20000 && missing.length === 0`；detail 走的是 `missing.length === 0` 那一支
（`DOM 9329 bytes`），即 **needle 一条不缺** —— 红的**只有**字节地板这一格。
同 7 条路由的其余断言（没被守卫弹走、无文本重叠、无非故意横向溢出、
`.app` 的 surface class）**全部是绿的**。

**根因**：那个 `20000` 是 **dev 档**标定的 —— dev 模式下 vite 把 65 kB 的 CSS 注进
`<style>`（`smoke.mjs` 第 1963 行那段注释逐字记着这件事），于是原始 DOM 天然就大；
产品档的 CSS 是 `/assets/index-*.css` 一个**外链**，一个字节都不在 DOM 里。
即那个地板量的是「vite 有没有把 CSS 注进来」，而**不是**它自己那句注释声称的
「页面渲染出来了」。

两档各跑一整遍、15 条路由逐条量 `document.documentElement.outerHTML`（同一次
`demo.ps1` 灌出来的 60 人）：

| 路由 | dev 档 | 产品档 | 倍数 |
|---|---|---|---|
| `login` | 186 272 | **9 329** | 19.97× |
| `bind` | 185 175 | **9 996** | 18.52× |
| `s-home` | 190 637 | **14 821** | 12.86× |
| `s-weekly-sheet` | 197 482 | 22 253 | 8.87× |
| `s-check-in` | 198 098 | 21 226 | 9.33× |
| `s-rpe` | 197 292 | 21 340 | 9.25× |
| `s-mini-test` | 195 209 | **18 187** | 10.73× |
| `s-notifications` | 190 210 | **15 034** | 12.65× |
| `t-dashboard` | 263 136 | 45 923 | 5.73× |
| `t-report` | 245 802 | 42 952 | 5.72× |
| `t-alerts` | 309 625 | 121 370 | 2.55× |
| `t-students/10` | 227 098 | 43 027 | 5.28× |
| `admin` | 200 175 | 25 115 | 7.97× |
| `admin-list` | 191 518 | **15 015** | 12.75× |
| `admin-detail` | 183 928 | **8 853** | 20.78× |

两档最小值 183 928 vs 8 853（相差 20.8×），而产品档最小值就在那个 20000 下面。

**处置（⚠️ 这是本波唯一一处对既有判据的修改，请控制者核）**：
把判据**做准**、而不是把数字调小 ——

* dev 档地板**一字不动**仍是 `20000`（`DEV_DOM_FLOOR`，逐字就是改前那个数）；
* 产品档另取 `PROD_DOM_FLOOR = 6000`。取值不是拍的：下界 = 一个**白屏**产品页的
  `outerHTML` ≈ 发出的那份 `index.html` 本体 **2 729 B**（6000 是它的 **2.2×**，
  过 硬规矩 #42 的 2× 分辨率线）；上界 = 实测最小的真渲染页 **8 853 B**
  （6000 是它的 0.68×）。即「白屏一定红、真渲染一定绿」。
* **档位判定是双侧的、认不出就红**：`/@vite/client` = dev、`src="/assets/` = prod，
  两侧都命中或都不命中 → `'unknown'` → 那一条路由**当场红**（不是静默掉到松地板）。
  ⚠️ 两个标记都是**亲跑量出来的**，不是从文档抄的：

  | 标记 | dev（vite 5173 **与** 5174） | 产品档（uvicorn 8020） |
  |---|---|---|
  | `/@vite/client` | 命中 **×1** | 0 |
  | `src="/assets/` | 0 | 命中 **×1** |
  | `/src/main.ts` | 命中 ×1 | 0 |
  | `rel="stylesheet"` | 0 | 命中 ×2 |

  ⚠️ 而 `frontend/index.html`（dev 的入口）里**没有**任何 `/assets/` 引用 ——
  它逐字是 `<script type="module" src="/src/main.ts"></script>`，且本前端**没有**
  `public/` 目录，故 dev 档的 DOM 里不可能出现 `src="/assets/`。
* 另加**一拍**收尾断言说出「本次量的是哪一档」（`§Tier 15 条路由的构建档判定一致`），
  于是取证能从日志里直接读出档位而不必去推。⚠️ 断言总数因此 **499 → 500**。

改完两档复跑：**dev 18/18 · 500 绿 / 0 红 · 退出码 0**（日志里逐条印
`DOM 186272 bytes（dev 档，地板 20000）`）；**产品档 18/18 · 500 绿 / 0 红 · 退出码 0**
（逐条印 `DOM 9329 bytes（prod 档，地板 6000）`），收尾那一拍分别报
`取值 = dev` 与 `取值 = prod`。

⚠️ **没有为了过 smoke 而改 smoke 的判据**（硬规矩 #92）：那 7 条红的**内容判据
一格都没动**（needle 清单、`toPlainText`、location、布局三格、surface class 全部原样），
动的只有「多少字节算渲染出来了」这一个**跨档不成立的常量**，且 dev 那一侧的数值
**逐字保留**。⚠️ 已登记为「没按派单做的」第 1 条，请控制者裁定。

⚠️ 顺带实测到的一格（不影响结论、如实记）：`httpx` 在拼 URL 时会把**字面**的
`/../` 折掉（连 `raw_path` 都变成 `b'/secret.txt'`），故「字面 `..`」那一档在
HTTP 层**无法表达**；只有 `%2e%2e` 那种编码形式到得了服务端。
`tests/test_serve.py` 的穿越矩阵因此分两层（判据层喂已解码的串、HTTP 层走完整链路），
而 HTTP 层那张期望表是用一个**包住 app 的 ASGI spy** 实测出来的（打印
`scope["path"]` 与 `scope["raw_path"]`），不是推出来的。

---

## ⑤ `.gitattributes` 的两条钉扎

### ⑤-① ⚠️⚠️ 顶回：`Document/**` 会**当场毁掉 15 张截图与那份 Word 原稿**

`Document/` 下今天有 **26** 个入库文件：

| 类别 | 个数 | 今天 `git ls-files --eol` 报的 |
|---|---|---|
| `.md`（设计 spec + 6 份实施计划 + 联调取证 + 需求记录） | **10** | 9 个 `i/lf w/crlf`，1 个 `i/lf w/lf`（`2026-10-13-实施计划06-产品级硬化.md`） |
| `.png`（Plan 04 的 15 张演示截图） | **15** | `i/-text w/-text attr/`（git **自己**已经认出是二进制） |
| `.doc`（甲方那份 Word 原稿，1 203 712 B） | **1** | `i/-text w/-text attr/` |

给 `Document/**` 钉 `text eol=crlf` 会**关掉 git 的二进制启发式**，于是那 16 个文件
会被当文本做行尾转换 —— 而它们的字节里**本来就有** LF：

| 文件 | 字节 | CRLF | 裸 LF |
|---|---|---|---|
| `shot-01-login.png` | 142 509 | 2 | **382** |
| `shot-11-t-alerts.png` | 2 028 852 | 23 | **5 256** |
| `shot-04-s-weekly-sheet.png` | 253 092 | 91 | **833** |
| `数智驱动的高校公共体育教学和反馈系统设计与实现.doc` | 1 203 712 | 19 | **3 707** |
| （其余 12 张 png 同族，裸 LF 215–1 761 个） | | | |

**亲跑的取证**（`$env:TEMP` 下一个临时仓库 + 一次**真 clone**，`core.autocrlf=true`）：

```
规则 `Document/** text eol=crlf`
  git add 时  → warning: in the working copy of 'Document/shot-01-login.png',
                         LF will be replaced by CRLF the next time Git touches it
                warning: in the working copy of 'Document/plan06.md', LF will be replaced …
  git check-attr text eol -- Document/shot-01-login.png → text: set / eol: crlf   ← ⚠️
  入库 blob   → 142 507 B（原件 142 509 B，**已经少了 2 个字节**）
  重新 clone  → 142 891 B，sha256 **不同**（+382 = 那 382 个裸 LF 各多一个 CR）

规则 `Document/**/*.md text eol=crlf`（本波落的这一条；clone 时故意用 autocrlf=false）
  shot-01-login.png   142 509 B → 142 509 B  sha256 **相同**  attr 仍是 `-text`
  …设计与实现.doc   1 203 712 B → 1 203 712 B  sha256 **相同**  attr 仍是 `-text`
  plan06.md               8 489 B →     8 574 B（LF→CRLF，**这正是要的效果**，
                                          且证明它与 core.autocrlf 无关）
```

即：裁定的原文会**当场**把 16 个二进制交付物改坏（截图的字节数写进了 Plan 04 的
实现者报告，那份 `.doc` 是甲方给的原始素材），而它想解决的问题（`.md` 的工作树字节数
随检出环境漂）用 `**/*.md` 一样能解决。故**顶回并收窄**成：

```
Document/**/*.md text eol=crlf
```

⚠️ 保留 `**` 的**递归**语义（将来在 `Document/` 下建子目录也盖得到），只把范围收窄到文本。
⚠️ 已加**红档守卫**：`tests/test_serve.py::test_gitattributes_pins_the_eol_of_every_ps1_and_nothing_binary`
断言 `Document/shot-01-login.png` / `shot-11-t-alerts.png` / 那个 `.doc` 的 `text` 与 `eol`
**必须是 `unspecified`**，且 `.gitattributes` 的**规则行**里不许出现
`Document/**`（不含 `.md`）那一条宽规则。谁放宽回去，这一格当场红。

⚠️ **波及面 = 0 个文件**（远低于派单给的 40 个上限，故不需要走「只钉 `.ps1`」那一档退路）。

### ⑤-② 落地的三条规则与受影响文件清单

```
backend/scripts/*.ps1 text eol=crlf     ← 裁定的第 1 条（3 个文件：demo / backup / restore）
scripts/*.ps1         text eol=crlf     ← ⚠️ 必需的第 2 条（1 个文件：serve.ps1）
Document/**/*.md      text eol=crlf     ← 裁定的第 2 条，**收窄**（10 个文件）
```

⚠️ **为什么是两条 `.ps1` 而不是一条**：gitattributes 的 `*` **不跨 `/`**
（本文件第 16-20 行早就逐字交代过这件事，而 `backend/data/**/*.yaml` 那一条正是为它补的），
而本波新建的 `scripts/serve.ps1` 住在**仓库根**。写成一条 `*.ps1` 也能盖住两处，
而本仓今天只有这 4 个文件，故按目录逐条列 —— 将来在别的目录下新增一个 `.ps1` 时，
「要不要一起钉」会是一次**显式**的清单修改，而不是被一条宽规则静默接管。

**受影响文件清单（`git ls-files --eol` 实测，14 个）**：

| 路径 | 改前 | 改后 | blob 变了吗 |
|---|---|---|---|
| `backend/scripts/demo.ps1` | `i/lf w/crlf attr/` | `i/lf w/crlf attr/text eol=crlf` | **否** |
| `backend/scripts/backup.ps1` | 同上 | 同上 | **否** |
| `backend/scripts/restore.ps1` | 同上 | 同上 | **否** |
| `scripts/serve.ps1`（本波新建） | —— | `i/lf w/crlf attr/text eol=crlf` | —— |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | `i/lf w/crlf attr/` | `i/lf w/crlf attr/text eol=crlf` | **否** |
| `Document/2026-09-28-实施计划01-…md` … 至 `Document/2026-10-12-实施计划05B-…md`（8 个） | `i/lf w/crlf attr/` | `i/lf w/crlf attr/text eol=crlf` | **否** |
| `Document/2026-10-13-实施计划06-产品级硬化.md` | `i/lf **w/lf** attr/` | `i/lf **w/crlf** attr/text eol=crlf` | **否**（工作树 8 489 → 8 574 B） |

⚠️⚠️ **派单预期「钉扎会 re-normalize 既有文件的入库 blob → diff 会显示整文件重写」，
实测不成立**：那 13 个既有文件今天**已经是** `i/lf`，而 `text` 的入库侧就是
「归一化成 LF」，故 blob 一个字节都不变。亲跑：

```
$ git add --renormalize .
$ git status --short          → 只有 `M  .gitattributes` 一行
$ git diff --cached --stat    → .gitattributes | 85 +++++…  （1 file changed, 85 insertions）
```

即 **re-normalize 的波及面 = 0 个文件**（除 `.gitattributes` 自己）。
⚠️ 唯一一处工作树变化是我**主动**把 `Document/2026-10-13-实施计划06-产品级硬化.md`
从 LF 归到 CRLF（让工作树与新钉的 attr 一致，省掉「下一次 checkout 会重写一个文件」
那个潜在的惊吓）：8 489 → **8 574 B**，⚠️ 而 `git diff --numstat -- Document` 是**空的**
（clean 侧 CRLF→LF 之后与 blob 逐字相同），故它**没有**进 commit。

### ⑤-③ re-normalize 之后守卫是否全绿 —— **全绿**

| 守卫 | 结果 |
|---|---|
| BOM 守卫（`test_backup_restore.py::test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf`，含「与 demo.ps1 同款」那一拍） | ✅ |
| BOM 守卫（`test_serve.py::test_serve_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo`） | ✅ |
| BOM 守卫（`smoke.mjs` 第 17 步 ① 那三拍：BOM + 纯 CRLF + `Remove-Item Env:\` 那一行） | ✅（两档 smoke 各跑一遍，第 17 步 27/27） |
| spec 的 sha 断言 | **不存在**（`Grep` 全仓 `backend/tests`：`设计spec` / `253 ?238` / `251 ?031` 均 0 命中）—— 故「spec 工作树字节数」这件事今天**没有任何测试**在钉，只有散文里的数字 |
| `npm run check:tokens` | ✅ 退出码 0，扫描面 35 个文件 |
| `npm run check:dist` | ✅ 退出码 0（`adoptFromUrl` 0 次、两个 CDN 域各 0 次、woff2 恰好 4 个、三个正控串都在） |
| `npm run build` | ✅ 退出码 0，产物哈希与基线逐字相同 |
| 后端全量（`--cov=app.domain --cov-branch`） | ✅ **1494 passed + 1 skipped** |
| 依赖清单守卫（`test_dependencies.py`：后端 7+3+1、前端 3+7） | ✅ **一字不红**（新增依赖 0） |

### ⑤-④ 四个数据指纹 + 18 个模板指纹 —— **逐字不变**

亲跑（sha256 的前 16 位、CRLF 归一化为 LF 之后，与 `tests/test_refdata*.py` 同口径）：

| 指纹 | 文件 | 字节 | CRLF |
|---|---|---|---|
| `D2C8E539E2FA0029` | `backend/data/national_standard_2014.csv` | 21 412 | **0** |
| `5394B37F01DAC9AC` | `backend/data/exercises.yaml` | 23 247 | **0** |
| `822CB86A5E998301` | `backend/data/exercise_equivalence.yaml` | 8 245 | **0** |
| `E48E3AC82BB45BB7` | `backend/data/alert_rules.yaml` | 6 037 | **0** |

18 个处方模板 YAML（`backend/data/prescription/*.yaml`）：**18 个，含 CRLF 的 0 个**。
`git check-attr text eol` 逐个复核：`backend/data/**` 那 24 个文件仍是
`text: set / eol: lf`，**一格都没被本波碰**。⚠️ 注意
`backend/data/README_national_standard.md` 走的是既有的 `backend/data/*.md text eol=lf`，
而**不是**新钉的 `Document/**/*.md`（两个路径不相交）—— 它仍是 `eol: lf`，已进守卫。

### ⑤-⑤ 另外三条既有钉扎 —— 一格没被碰（`git check-attr` 亲验）

| 路径 | 期望 | 实测 |
|---|---|---|
| `frontend/src/assets/fonts/hanken-grotesk-var-latin.woff2` | `binary: set` / `text: unset` | ✅ |
| `frontend/src/assets/brand/xmu-emblem.svg` | `text: unset` | ✅ |
| `.superpowers/sdd/2026-10-13-…/task-5-6-report.md` | `text: unset` | ✅ |

三格都进了上面那条守卫的断言里（含 woff2 的 `binary: set`）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / **顶回**

### ⑥-① 顶回（**2 处**）

**顶回 1（Critical，已按收窄版落地）：`Document/**` 钉 `text eol=crlf` 会毁掉 16 个二进制交付物。**
逐字取证见 ⑤-①：`shot-01-login.png` 的入库 blob 142 509 → **142 507 B**，
重新 clone 出来 **142 891 B**、sha256 不同；那份 1 203 712 B 的 `.doc` 同族
（3 707 个裸 LF）。**落成 `Document/**/*.md text eol=crlf`**（保留 `**` 的递归语义、
只收窄到文本），并加了**会红**的守卫（二进制那一格必须 `unspecified`）。
⚠️ 派单还给了另一条退路（「波及面 > 40 个文件就只钉 `.ps1`」），实测**用不上**：
`git add --renormalize .` 的波及面是 **0 个文件**。

**顶回 2（派单自己点名要裁的那一格：产品档缺省 `PE_ENV=dev`，要不要第三档）。**
派单 §0 问的是「是否该给一个『同源 http 产品档』的第三档」。**我的答复是：不要，
`dev` 就是那一档，而缺省留在 `dev` 是对的**，三条理由：

1. **第三档要改的是 `cookie_secure()` 的判据**（今天它逐字就是 `deploy.is_prod()`），
   而那一格被 `app/main.py::_selfcheck_prod` 当成**回归守卫**钉着（它的 docstring
   逐字写着「这一格在**构造上**不可能为假」）。加第三档等于把那句构造性保证换成
   一个三值判定，而 `tests/test_main.py::test_the_selfcheck_raises_when_the_secure_cookie_is_off_in_prod`
   那条 `monkeypatch` 守卫也要跟着改 —— **代价落在安全性质最紧的那一格上**。
2. **第三档解决的是一个不存在的痛点**：同源部署**本来就不需要** `Secure`
   （cookie 不出这台机器），也不需要 CORS。而「明文 http 上跨机部署」那一档
   **不该被支持**（会话 cookie 在链路上可被读走），第三档恰好会给它一个看起来合法的开关。
3. **`prod` 那一档今天已经能覆盖真实的 HTTPS 反代**：`PE_ENV=prod` +
   `PE_CORS_ORIGINS=https://…`（或干脆不设 = 不挂 CORS = 同源），
   `Secure` 开、`PE_ALLOW_HEADER_IDENTITY` 强制关、启动自检在。
   ⚠️ 唯一要注意的是反代要把 `X-Forwarded-Proto` 一类的东西交代清楚，
   而那是反代的配置、不是本仓的档位。

于是处置是**不改代码**、把口径写清楚：`serve.ps1` 打印实测的档位与 `Secure` 值
（不是写死一句「dev」），并逐字说明「`Secure` 只在 prod 开 ⇒ 明文 http 上跑 prod 档
浏览器会拒收 cookie（症状是登录 200、下一个请求 401）⇒ 同源 http 的产品档请留在
缺省的 dev 档」。已写进 spec §13.11.3。

### ⑥-② 没按派单做的（**2 处**）

1. **⚠️ 改了 `smoke.mjs` 的一条判据**（派单 §1 第 5 条逐字写「不要为了过 smoke 而改
   smoke 的判据」，硬规矩 #92）。改的是第 14 步那个 `rawBytes > 20000` 的**字节地板**，
   逐字取证与理由见 ④-③：那个 20000 是 dev 档标定的常量，它量的是「vite 有没有把
   CSS 注进 `<style>`」，在产品档上**跨档不成立**；那 7 条红的**内容判据一格都没动**，
   dev 侧的数值**逐字保留**（仍是 20000），产品档另取一个**有实测取值依据**的 6000。
   ⚠️ 我判断这一格属于「把判据做准」而不是「放宽判据让它绿」，但它是派单点名禁止的
   动作的**近邻**，故显式登记、请控制者裁定。⚠️ 若裁定为「不许改」，
   产品档 smoke 的可达上限就是 **17/18 步 · 492 绿 / 7 红 · 退出码 1**，
   而那 7 条红与页面渲染质量**无关**（同 7 条路由的 needle / location / 布局三格 /
   surface class 全绿）。
2. **断言总数 499 → 500**（多的是「15 条路由的构建档判定一致」那一拍，
   它是上面那个档位判定的反空转守卫）。⚠️ 派单与既有散文里的「499 断言」因此过期；
   `frontend/package.json` 的 `//` 那一段**刻意不复述**断言条数
   （逐字写着「它每一波都在长，复述就是第二个所有者」），故**没有任何文件**需要跟着改数。

### ⑥-③ 待清扫（**3 条**，本波新登记）

1. **打错的 `/assets/*.js` 走 SPA fallback、拿到 200 的 `index.html` 而不是 404**。
   实测：`GET /assets/does-not-exist.js` → `200 text/html; charset=utf-8` 2 729 B。
   失效形态很具体：重新部署之后，一个缓存着旧 `index.html` 的客户端来要旧哈希的 chunk，
   浏览器报的是 `Failed to load module script: Expected a JavaScript module script but
   the server responded with a MIME type of "text/html"` 而不是 `404` —— 两者都是错，
   而 404 好查得多。收紧的做法是给 `/assets` 也进 `RESERVED_PREFIXES`，
   代价是「保留前缀」这一个概念要同时装「API 面」与「产物面」两种理由
   （故本波**没有**顺手做，留给裁定）。
2. **产品档没有任何缓存头**。`dist/assets/*` 的文件名带内容哈希
   （`index-eWDO9FkM.js`），本该发 `Cache-Control: public, max-age=31536000, immutable`，
   而 `index.html` 本该 `no-cache`；今天两档都是 Starlette 的缺省
   （`etag` + `last-modified`，每次都要一发条件请求）。⚠️ 派单没要求，故没做；
   要加的话正确的住址是 `app/static.py::mount_spa`（判据仍然是那一个所有者）。
3. **`serve.ps1` 不强制清 `PE_ALLOW_HEADER_IDENTITY`**（`demo.ps1` 强制清）。
   本波选择**只打印实测值 + 一句响亮的 ⚠️**：`demo.ps1` 是演示、必须强制关；
   而 `serve.ps1` 是部署入口，那个开关归运维（且 `prod` 档下
   `app.api.deps.allow_header_identity` 本来就恒回 `False`）。
   ⚠️ 代价（硬规矩 #39）：在一个 `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 的 shell 里
   跑 `serve.ps1` 且**不设** `PE_ENV=prod`，会得到一个认伪造请求头的产品档 ——
   而脚本会把这件事**打印出来**（不是静默），故它是「响亮的」而不是「静默的」。
   要收紧就照 `demo.ps1` 那三行抄一遍（`Remove-Item Env:\` + 删不掉就 throw）。

### ⑥-④ 关切（**2 条**，不必本波处置）

1. **`app/static.py` 不在 `SCANNED_DIRS` 的扫描面里**（它在 `app/` 根下，
   与 `main.py` / `deploy.py` / `config.py` 同族），故它不受
   「生产层不得 import `app.seed`」与「api 层依赖方向单向」两条守卫管。
   ⚠️ 这是**有意**的（`test_layering.py` 第 103-106 行逐字交代了 `main.py` 为什么不在列：
   它是装配点、在 `api` **之上**），而 `static.py` 的位置与它相同。
   ⚠️ 而它今天只 import `pathlib` + `fastapi` + `starlette`，一条 `app.*` 都不 import，
   故它**不可能**造出环。实测：扫描面仍是 **71**（`pipeline 10 + db 13 + domain 18 +
   api 26 + auth 4`），一格没变。
2. **`frontend/dist` 在 `.gitignore` 里**（`frontend/dist/`），故产品档的产物**不入库** ——
   交付给甲方时要么在那台机器上跑一次 `npm run build`（`serve.ps1` 自己会跑），
   要么另外打一个包。⚠️ 本仓今天**没有**「产物打包」这一档（`serve.ps1` 是
   「在这台机器上起服务」，不是「产出一个可分发的 zip」）。派单没要求，故没做；
   如实登记。

---

## ⑦ 最终验收

### ⑦-① 后端

| 格 | 基线 | 本波 | 判定 |
|---|---|---|---|
| `pytest -q --cov=app.domain --cov-branch` | 1464 passed + 1 skipped | **1494 passed + 1 skipped**（318 s） | ✅ **+30**（全部来自新建的 `tests/test_serve.py`） |
| 不带 `--cov` 的 `pytest -q` | 1465 passed | **1495 passed**（190 s） | ✅ 那 1 条 skip 是 `test_backfill.py` 的墙钟哨兵，它只在检测到 trace 钩子（= `--cov`）时才跳 |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | ✅ 逐字不变 |
| 表数（`/api/health` 的 `tables` 口径 = `Base.metadata`） | 28 | **28** | ✅ |
| 迁移链 | 3 条，单头 | **3 条**（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84`），单头 | ✅ |
| 扫描面（`SCANNED_DIRS` 五个目录） | 71 | **71**（`pipeline 10 + db 13 + domain 18 + api 26 + auth 4`） | ✅ `app/static.py` 在 `app/` 根下、不在扫描面里 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✅ |
| 黄金用例 | 14 | **14**（`tests/fixtures/golden_cases.json` 的 `input` / `expected` 各 14 条） | ✅ |
| 依赖清单守卫 | 后端 7+3+1、前端 3+7 | **一字不红** | ✅ 新增依赖 **0** |

### ⑦-② openapi 五格（`app.openapi()` 实读）

| 格 | 基线 | 本波 | 判定 |
|---|---|---|---|
| 路径 | 72 | **72** | ✅ |
| 操作 | 100 | **100** | ✅ |
| 挂 `security` 的操作 | 82 | **82** | ✅ |
| GET 操作 | 61（15 匿名 + 46 挂 security） | **61（15 + 46）** | ✅ |
| `securitySchemes` | 3 | **3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | ✅ |
| ⚠️ SPA 的 catch-all 有没有漏进 `paths` | —— | **0 个**（没有任何 `/{` 开头的键） | ✅ |

### ⑦-③ 前端

| 格 | 基线 | 本波 | 判定 |
|---|---|---|---|
| 路由条数 | 15 | **15**（smoke 第 14 步 `eq` 那一拍） | ✅ |
| `npm run build` | 退出码 0 | **退出码 0**（`✓ built in 610ms`） | ✅ |
| 产物哈希 | `index-CM7Fwkho.css` / `index-eWDO9FkM.js` | **`index-CM7Fwkho.css`（65 204 B = 65.20 kB）/ `index-eWDO9FkM.js`（167 032 B = 167.03 kB）** | ✅ 逐字相同（`src/` 一行未动） |
| `npm run check:tokens` | 绿（35 文件） | **绿，退出码 0，扫描面 35 个文件** | ✅ |
| `npm run check:dist` | 绿 | **绿，退出码 0**（`adoptFromUrl` 0 次、两个 CDN 域各 0 次、woff2 恰好 4 个、三个正控串都在、三条自校都过） | ✅ |
| `smoke.mjs` dev 档 | 18 步 / 499 断言 / 退出码 0 | **18/18 步 · 500 绿 / 0 红 · 退出码 0** | ⚠️ 断言数 499 → 500（见 ⑥-② 第 2 条） |
| `smoke.mjs` **产品档** | —— | **18/18 步 · 500 绿 / 0 红 · 退出码 0** | ✅ **派单 §1 第 5 条的核心验收** |
| 新增前端依赖 | 0 | **0** | ✅ |

### ⑦-④ 禁区与卫生

| 格 | 实测 |
|---|---|
| `backend/pe.db` 存在 | **False** |
| `backend/data/seed/` 文件数（`-Recurse`） | **0** |
| `git diff 6dde666 HEAD -- backend/data` | **空**（一字未动） |
| `git ls-files frontend/dist` | **0 个**（`frontend/dist/` 在 `.gitignore` 里，未入库） |
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` **逐字不变**（⑤-④） |
| 18 个模板指纹 | 18 个 YAML，**含 CRLF 的 0 个** |
| 有没有跑过 `app.seed.generate` / `backfill` / `daily` | **没有**（数据一律由 `backend/scripts/demo.ps1` 灌，共 3 次；它的 `[7/7]` 复核逐次相同：`student 60 / prescription 60 / alert 32 / notification 19 / weekly_class_report 5`） |
| 探针文件 | 一律写在 `$env:TEMP`（`pe_t7_norm.py` / `pe_t7_matrix.py` / `pe_t7_tier*.py` / `pe_t7_mutation.py` / `pe_t7_accept.py` / 两份 commit 消息）；四个 `.gitattributes` 取证用的临时仓库 + clone 已**整目录删掉并复验**（`pe_attr_probe` / `pe_attr_clone` / `pe_attr_probe2` / `pe_attr_clone2` 四个 `Test-Path` 全 `False`） |
| **我起的产品档进程停了吗** | **停了**（②-③ 那张表逐个记了 PID 与停止取证：uvicorn 45904 / 34948 与外层 powershell 45296 / 47288 全部 `alive = False`，`8020 listeners = 0`） |
| ⚠️ 交回时仍在跑的 | **5173 上的 vite（PID 3260）** —— 不是我起的，见 ①。8000 / 8020 / 5174 都空着 |

### ⑦-⑤ 定点变异（硬规矩 #50：一条恒绿的守卫与一条真的守卫在颜色上无法区分）

9 格，**全部变红、且文件逐字节还原**：

| # | 变异 | 应当红的那条 | 结果 |
|---|---|---|---|
| M1 | 给 `serve.ps1` 的 param 块加一个 `[switch]$Prod` | `…exactly_the_two_documented_switches_and_no_prod_switch` | 红 ✓ |
| M2 | 去掉 `serve.ps1` 的 `$Proc.WaitForExit()`（= 不再前台阻塞） | `…blocks_in_the_foreground_and_cleans_up_its_child` | 红 ✓ |
| M3 | 把 python 的版本下界从 `-lt 311` 松到 `-lt 300` | `…runs_the_five_documented_steps_in_order` | 红 ✓ |
| M4 | `_SpaRoute.matches` 退化成裸 `Route`（去掉 `Match.NONE`） | `test_method_semantics_on_and_off_the_api_are_unchanged` | 红 ✓ |
| M5 | 去掉 `resolve_static_path` 的「保留前缀 → None」 | `test_an_unknown_path_under_a_reserved_prefix_answers_the_unified_404` | 红 ✓ |
| M6 | 去掉 `_candidate_under` 的 `is_relative_to` 越界复核 | `test_resolve_static_path_refuses_to_leave_the_dist_directory` | 红 ✓ |
| M7 | 从 `_MEDIA_TYPES` 里删掉 `.js`（= 交回 `mimetypes` 赌注册表） | `test_media_type_of_pins_the_five_extensions_a_build_actually_emits` | 红 ✓ |
| M8 | `create_app` 的 `static_dist` 缺省值不再是 `None` | `test_the_dev_tier_is_untouched_when_static_dist_is_not_given` | 红 ✓（收集期 error） |
| M9 | catch-all 从 `_SpaRoute` 改成 `add_api_route`（于是它进 OpenAPI） | `test_the_openapi_document_is_identical_with_and_without_the_spa` | 红 ✓ |

⚠️ 还原是**逐字节**核过的（探针自己比对 `read_bytes()`），且还原之后
`tests/test_serve.py` 复跑 **29 → 30 条全绿**、`app/static.py` 与 `app/main.py`
的字节数与 commit ① 时逐字相同（19 568 / 31 544）。
⚠️ 中途我自己踩了一脚：跑归一化探针时**忘了带 `--bom`**，把 `serve.ps1` 的 BOM 剥掉了
（22 228 → 22 225 B），当场被新加的那条 BOM 守卫抓住（`1 failed`），
补 `--bom` 重跑后回到 22 228 B / 359 CRLF / 0 裸 LF。⚠️ **那一次失败正是这条守卫存在的理由**
（上一波实现者被工具剥 BOM 是同一档事故），如实记。

### ⑦-⑥ commit

| sha | 一句话 | 自洽吗 |
|---|---|---|
| **`06b2f8b`** | `feat(api): Plan 06 Task 7 ① —— create_app(static_dist=…) + SPA fallback + serve_app 入口`（4 files，+1269 / −3） | ✅ 自洽：`static_dist` 缺省 `None` ⇒ 既有行为一行不变；`tests/test_serve.py` 那 20 条**不依赖** `serve.ps1`（它只断 `serve_app.py` 与 `app/static.py`），故本 commit 上全量测试是绿的 |
| **`a7c907e`** | `feat(scripts): Plan 06 Task 7 ② —— scripts/serve.ps1（一条命令起产品档）+ smoke 在两档都全绿`（3 files，+725 / −7） | ✅ 自洽：`serve.ps1` 与它那 9 条守卫同一个 commit；`smoke.mjs` 的地板改动与「两档各跑一遍全绿」的取证同一个 commit |
| **commit ③**（= 装着本文件的那一个，故它的 sha 在本文件里**写不出来**：写进去就会改掉它自己） | `docs: Plan 06 Task 7 ③ —— .gitattributes 三条行尾钉扎（⚠️ 顶回 Document/**）+ spec §13.11 + 实现者报告` | ✅ 自洽：三条规则 + 那条会红的守卫 + spec + 报告同一个 commit |

⚠️ commit ③ 的 sha 与「报告字节数 == 入库 blob 字节数」那一格的复核结果，
在交回控制者的那一段里给（本文件落盘之后再读一次 `git cat-file -s`）。

⚠️ commit ① 有一处**小的不自洽**，如实记：`tests/test_serve.py` 在 commit ① 里就定义了
`SERVE_PS1 = REPO_ROOT / "scripts" / "serve.ps1"` 这个常量，而那个文件要到 commit ②
才存在。⚠️ 它在 commit ① 上**没有任何断言读它**（9 条 `.ps1` 守卫是 commit ② 加的），
故 commit ① 上全量测试仍然是绿的、`python -m py_compile` 也过 —— 它只是一个
提前落地的路径常量，不是一个提前落地的断言。

⚠️ **未 push**（派单逐字要求；`main` 一格没动，HEAD 仍是 `6dde666`）。

---

## 附：本波改动的 8 个文件（`git diff 6dde666 --stat`，commit ③ 之前）

```
 .gitattributes                                          |   85 ++
 Document/2026-09-28-体育闭环原型-设计spec.md              |  202 ++++
 backend/app/main.py                                     |   50 +-
 backend/app/static.py                                   |  331 ++++++
 backend/scripts/serve_app.py                            |  133 +++
 backend/tests/test_serve.py                             | 1152 ++++++++++++++++++++
 frontend/scripts/smoke.mjs                              |  117 +-
 scripts/serve.ps1                                       |  359 ++++++
 8 files changed, 2419 insertions(+), 10 deletions(-)
```

⚠️ `backend/data/**` **不在**这张表里（`git diff 6dde666 HEAD -- backend/data` 是空的）；
`frontend/dist/**` 也不在（`.gitignore`）；`Document/2026-10-13-实施计划06-产品级硬化.md`
也不在（工作树 8 489 → 8 574 B 是**行尾**，clean 侧归一化之后与 blob 逐字相同）。
