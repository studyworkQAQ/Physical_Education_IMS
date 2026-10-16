# Plan 07 Task 11 实现者报告 —— 交付前最后一个窗口（G15 + G14 + 重建产物 + 最后一次重打包）

> 分支 `p07/final-polish`（从 `p07/delivery-final` = `02a7a89` 起）。
> ⚠️ 本报告**刻意不印自己的字节数与 sha256**（不动点问题；Task 8 在这一族连踩四次，
> 教训在 `task-8-report.md` §8.6）。
> ⚠️ 按派单：**没碰 `main`、没 push、没自己合并**；甲方那两个进程（PID 45156 / 37196）
> **一根汗毛都没动**（开工与收尾各量一遍，见 §1.3 与 §1.5）。

---

## 1. 环境 + 开工五格与收尾五格

### 1.1 环境（硬规矩 #73：开工第一件事）

```
node --version   → v24.19.0        （基线 v24.19.0 ✓）
python --version → Python 3.11.1   （基线 3.11.1 ✓，无 venv）
npm --version    → 11.17.0         （基线 11.17.0 ✓）
git HEAD（开工） → 02a7a89         分支 p07/delivery-final，git status 空
git checkout -b p07/final-polish   → Switched to a new branch ✓（起点 02a7a89）
```

### 1.2 开工先复核的那 6 个 sha —— **逐个对上** ✅

`git log --oneline -6` 实测：

```
02a7a89 docs(report): 把 task-10-report §8 的 commit 表补齐到与实物一致
a1e2737 docs(report): 订正 task-10-report §8.5 里两句与实物不符的话
7a4b5fb docs(spec+ledger+progress+report): Task 10 交付收尾波的结案节 + 台账划 6 补 6 + 实现者报告
0447379 fix(scripts): G9 + G7 + G12 —— 三条脚本缺陷各收窄一格判据
414eca7 refactor(frontend): G11 —— 甲方看得见的正文里不再印波次编号与 file:line
fb2e8d4 fix(frontend): G8 —— 401 错误横幅不再跨过登录留在下一个身份的页面上
```

⇒ 与派单 §0 逐字相同（`02a7a89` / `a1e2737` / `7a4b5fb` / `0447379` / `414eca7` / `fb2e8d4`）。
⚠️ `main` 实测仍停在 `dd48b2a`（本波一次都没碰它）。

### 1.3 开工五格（⚠️ 逐个亲量，不是抄派单）

| 格 | 实测 | 判定 |
|---|---|---|
| ① 试用档服务 PID **45156** | `python`，start **2026/10/16 0:36:05**，监听 `127.0.0.1:8030` | ✅ 与派单逐字对上 |
| ② 公网隧道 PID **37196** | `cloudflared`，start **2026/10/16 10:14:35** | ✅ 与派单逐字对上 |
| ③ `backend\pe_trial.db` | **1 589 248 B / sha256[:16] `40D7B5F78A7C36CB`** | ✅ 逐字对上 |
| ③b `.trial\public-url.txt` | **1 701 B / `0899037E4A220B01`**；里面那条 URL = `https://related-llp-briefing-holds.trycloudflare.com` | ✅ 逐字对上 |
| ④ `frontend\dist` | **29 文件 / 686 680 B**；`index.html` **2 729 B / `AC8484448A88779D`** | ✅ 逐字对上 |
| ⑤ 甲方 URL 匿名 health | `GET /api/health` → **200 / 54 B** / `{"status":"ok","tables":28,"students":60,"trial":true}`；`GET /health` → 200 / 2 729 B（= SPA 外壳） | ✅ |

⚠️ 全程**只发匿名 GET**：一次都没登录、一次都没写、没跑 `-Reset`、没写 `pe_trial.db`、
没用 `tunnel.ps1` 打 8030。
⚠️ 另外四个不许杀的进程开工时都在：vite 5173（PID **43520**）与其父 `npm run dev`（PID **38900**）、
两个 `@deepseek-ai/dsh web`（PID **14368 / 16404**）—— 收尾时**同样都在**（§1.5）。

### 1.4 我自己起的实例（⚠️ 一律 8040+，一律我自己在 `$env:TEMP\p07t11\` 里灌的库）

| 端口 | 是什么 | 库 |
|---|---|---|
| **8040** | 产品档 `serve.ps1 -SkipBuild` + `PE_DB_URL`（G15/G14 的改前改后取证、smoke dev/产品档的 API 侧） | `$TEMP\p07t11\pe_t11.db`（每跑一次 smoke 换一份刚灌的） |
| **8042** | 我自己的 vite（`PE_API_TARGET=http://127.0.0.1:8040`）；⚠️ **不碰**别人的 5173 | — |
| **8043** | **原件** `trial.ps1 -Port 8043` + `PE_DB_URL`（G7 的端到端复验 + smoke 试用档） | `$TEMP\p07t11\pe_t11_trial.db`（由 `trial.ps1` 第 ③ 步自己灌） |
| **8044** | **解包目录**里那份 `trial.ps1`（六格 ②⑤；含空格与中文的目录） | `$TEMP\p07t11\体育系统 试用 pack3\backend\pe_trial.db` |

⚠️ **G7 那一格先实测复核过才用它**（派单点名要复验）：
`$env:PE_DB_URL` 指到 `$TEMP\p07t11\pe_t11.db` 之后跑 `trial.ps1 -Port 8040 -Reset`
（**不给 `-Force`**）→ 它打印「⚠️ -Reset **拒绝了**：要删的库**不是**本脚本缺省的那一份」
+ 缺省那一份是哪一份 + 我这一次指向哪一份 + 「确认要删就再加一个 -Force」，**退出码 1**，
⚠️ 而甲方那一份 `backend\pe_trial.db` **一个字节都没动**（紧接着复量：1 589 248 B / `40D7B5F78A7C36CB`）。
随后 8043 那一次**端到端**也走通了：`PE_DB_URL` 被尊重（打印的「试用库」就是我 TEMP 里那一份）、
库不在 → 自己灌 → 起服务 → `/api/health` 回 `"trial":true`。

### 1.5 收尾五格（⚠️ 与 §1.3 同一段脚本、同一条口径，收尾再量一遍）

| 格 | 收尾实测 | 判定 |
|---|---|---|
| ① PID **45156** | `python`，start **2026/10/16 0:36:05** —— **仍在** | ✅ 没被杀、没被重启 |
| ② PID **37196** | `cloudflared`，start **2026/10/16 10:14:35** —— **仍在** | ✅ 没被杀、没被重启 |
| ③ `backend\pe_trial.db` | **1 589 248 B / `40D7B5F78A7C36CB`** | ✅ **逐字未变** |
| ③b `.trial\public-url.txt` | **1 701 B / `0899037E4A220B01`** | ✅ **逐字未变** |
| ④ `frontend\dist` | **29 文件 / 686 788 B**；`index.html` **2 729 B / `3A6E04ED9FE1622E`** | ✅ 本波重建过（新旧对照见 §4.2） |
| ⑤ 甲方 URL | `GET /api/health` → **200 / 54 B / `trial:true`**；`GET /login` → **200 / 2 729 B / `3A6E04ED9FE1622E`** = 本地新 `index.html` **逐字节相同**，引用的是 **`index-CD9fWvKJ.js` + `index-D2BHlq_t.css`**（= 新哈希） | ✅ **仍 200、且服务的是新版** |

⚠️ 另外四个不许杀的进程收尾同样都在：**43520 / 38900 / 14368 / 16404**（`Get-Process` 逐个列出来核过）。
⚠️ **我自己起的进程全部已停**：`Get-NetTCPConnection -State Listen` 收尾实测只有
`::1:5173`（PID 43520，**别人的** vite）与 `127.0.0.1:8030`（PID 45156，**甲方的**）——
**8040 / 8042 / 8043 / 8044 一个都不在**。⚠️ CDP 无头浏览器由探针自己 `kill('SIGKILL')` +
等 `exit` + 删 profile；收尾实测 `$env:TEMP` 下 `p07t11*` 的残留是 **0 个**。

---

## 2. G15 —— `/login` 上那块 401 横幅的 advice 有两处半假

### 2.1 Task 10 报告里的原文（⚠️ 先 `Grep` 拿到的，不是凭派单转述）

`task-10-report.md` **L736-742**（§7.1 待清扫第 3 条）逐字：

> 3. **G15** · `/login` 上那块 401 横幅的 advice 有**两处半假**：① 登出之后落在 `/login` 上时
>    「送你去的登录页」就是**当前这一页**；② 而「回到刚才那一页」在**登出**这一档不成立
>    （`onLogout()` 做的是 `router.replace('/login')`，**不带** `?next=`）。
>    ⚠️ 在**会话过期**那一档两句都成立（`main.ts` 的订阅者带 `next`）⇒ 这是
>    「同一句话被两个时机共用、而只对其中一个为真」。⚠️ **本波刻意没改它**：…

以及 **L766-771**（§7.2 关切第 2 条）逐字：

> 2. ⚠️ **G15 是甲方**看得见**的**：照说明书 §4 路线二第 7 步走，登出之后落在 `/login` 上
>    会看到一块红色 401 横幅，而它那句「前端会把你送去登录页 / 登录之后回到刚才那一页」
>    在那一刻是半假的（⚠️ 它**不再**跨到下一个身份上 —— 那一格已修）。
>    ⚠️ 本波**没改它**…⚠️ 若控制者认为交付前该改，那是**一行**的事
>    （改 `ApiErrorBanner.vue` 的 `BRANCHES.unauthenticated.advice`）…

⇒ 它实测到的**那两处**就是上面 ① ②，住址是 `BRANCHES.unauthenticated.advice`。

### 2.2 我自己的复现取证（改前；真浏览器 + 真鼠标 + CDP，**产品档**）

harness：`$TEMP\p07t11\probe-before.mjs`（自建，姿势逐字抄 `smoke.mjs` 第 14 步：
headless Edge + `--remote-debugging-port=0` + `Target.attachToTarget{flatten:true}` +
`Input.dispatchMouseEvent` 三发真鼠标 + `Input.insertText` 真键盘 +
`Network.requestWillBeSent/responseReceived` 逐请求状态码 + `Runtime.evaluate` 抓 DOM）。
打在**产品档**（8040 + 改前的 `dist` = Task 10 于 00:03:00 重建的那一份）上
⇒ 与甲方看到的那一份**逐字同一个产物**。

路径：教师 `T0001` 从**登录表单**登进去 → `/t/alerts`（说明书 §4 路线二第 7 步逐字要甲方走的那一页）
→ **真鼠标**点「登出」→ 落 `/login`。抓到（逐字）：

```
cls     = banner banner--error banner--loud
code    = unauthenticated            status = 401
where   = GET /api/students?limit=200
advice  = 会话失效了（pe_session cookie 缺失、已过期或已登出）。前端会把你送去登录页，登录之后回到刚才那一页。
message = 缺少身份：需要一个有效的 pe_session cookie（请先 POST /api/auth/login）。⚠️ 请求头
          X-Teacher-Staff-No 被忽略：PE_ALLOW_HEADER_IDENTITY 不是 1
location.pathname = /login
location.search   = ""                     ← ⚠️ **空串**（⇒ ② 成立）
.auth__notice     = 已登出（服务端那一行 user_session 已被吊销，旧 cookie 立刻失效）。
```

同一次登出的逐请求时序（与 Task 10 §G8-② 的形状逐字对上，⚠️ 本波**一格未修** G13）：

```
POST /api/auth/logout          → 204
GET  /api/alerts?limit=200     → 401
GET  /api/students?limit=200   → 401
GET  /api/course-sections?…    → 200   ← 它是那 7 个匿名读之一
GET  /api/teachers?limit=200   → 401
GET  /api/enrollments?limit=200→ 401
⇒ 6 发 / 4 条 401
```

⇒ **两处半假逐格复现上了**：
① 抓到那一刻 `location.pathname` 就是 `/login` —— 「送你去的登录页」= **当前这一页**；
② `location.search` 实测就是**空串**，而 `views/auth/Login.vue` 的 `safeNext()` 在 `next`
   缺失时返回 `session.homePath` ⇒「回到刚才那一页」**不成立**（登录后落在自己那一端的首页）。

⚠️ 而**会话中途过期**那一档两句都成立（同样真浏览器取到，见 §3.4：删掉 `pe_session` cookie →
改业务日触发一批读 → 401 → 落到 `/login?next=/t/alerts`，`.auth__notice` 逐字是
「会话已失效，请重新登录（GET /api/teachers?limit=200 回了 401 unauthenticated）。
**登录之后会回到 /t/alerts**。⚠️ 那一页上没提交的输入已经丢了。」）。

### 2.3 改前 / 改后原文（逐字）

**改前**（`frontend/src/components/ApiErrorBanner.vue` 的 `BRANCHES.unauthenticated.advice`）：

> 会话失效了（pe_session cookie 缺失、已过期或已登出）。前端会把你送去登录页，登录之后回到刚才那一页。

**改后**（同一个住址，⚠️ 仍然只有一处）：

> 会话失效了（pe_session cookie 缺失、已过期或已登出）。请重新登录：会话中途过期时登录之后回到你刚才那一页，主动登出时登录之后落在你自己那一端的首页。

⚠️ **改法不是分成两档**：分支表的键是 **code**（约束第 8 条：按 `code` 分支、不按 `message`），
它读不到路由；而给它加一个「我是从哪一条路来的」入参等于把 **UI 的措辞耦进 HTTP 层**
（与 `client.ts` 刻意不含处置建议同一条口径）。故改成「**对两个时机都为真**的一句」。
⚠️ 也**不是**给 `onLogout()` 补 `?next=`（那会是一个**新的行为裁定** —— 与 Task 10 的建议同一条）。
⚠️ 口径与 Task 7 修 S1-2 那一族一致：**页面上不写死任何阈值数字**（那一句里今天一个数字都没有；
锁定阈值那一句仍住在 spec §13.4.6）；⚠️ 也**不含波次编号与 `file:line`**（Task 10 · G11 那一条口径）。
⚠️ 那段说明**写在块注释里**（不是 `//`）：`check-dist.mjs` 的 `stripComments` 剥块注释而
**刻意不剥** `//`，故写在 `//` 里的一句**提及**会被当成**本身**数到（硬规矩 #109）。

### 2.4 needle 无歧义的实测（⚠️ 先量后断言；本仓前几波在这上面栽过三次）

**改前**那一页上逐个量（`document.body.innerText` 与 `document.documentElement.outerHTML` 两侧都量）：

| needle | innerText | outerHTML |
|---|---|---|
| `会话失效了` | **1** | **1** |
| `前端会把你送去登录页` | **1** | **1** |
| `登录之后回到刚才那一页` | **1** | **1** |
| `pe_session cookie 缺失` | **1** | **1** |
| `登录页` | **1** | **1** |
| `刚才那一页` | **1** | **1** |

**改后**新那两句在 `toPlainText(document.documentElement.outerHTML)`（终审 I4 的单一所有者）上：

| needle | 主动登出那一档 | 会话过期那一档 |
|---|---|---|
| `会话中途过期时登录之后回到你刚才那一页` | **1** | **1** |
| `主动登出时登录之后落在你自己那一端的首页` | **1** | **1** |
| `前端会把你送去登录页`（改前的） | **0** | **0** |
| `登录之后回到刚才那一页`（改前的） | **0** | **0** |

⚠️ **两个时机各钉一遍**（不是只钉登出那一档）：新那一句是**两个时机共用**的，
故它得在两档都成立、且在两档都**只出现一次**。
⚠️ 另核：`Grep '前端会把你送去登录页|登录之后回到刚才那一页|会话失效了'` 打在
**说明书**与 **README** 上 **0 命中** ⇒ 那两份交付文档**不引用**这一句，
故本波**一个字节都没改它们**（Task 9 刚修的那 12 处也一个都没被改回去）。
⚠️ 全仓另有 4 处引用改前那句：spec §15 的 **G8** 与 **G15** 登记原文、
`smoke.mjs` §G8 的 docblock、`stores/session.ts` 的 `adopt()` docblock ——
**全是开发文档/注释**，按本仓「结案总账不重写」的口径**一个字都没改**
（spec §15 G15 只**加**了一行「✅ 已修 —— 本条划掉」+ 指针）。

### 2.5 守卫与定点变异

守卫：`smoke.mjs` 第 14 步新增 **§G15-①②③④⑤**（逐格说明住在那一段的 docblock 里）：
① needle 无歧义（各恰好 1 次）② 改前那两句半假一个都不在 ③ 新那两句都在
④ **取证**：主动登出那一档 `location.search` 里**没有** `next=`（⇒ 新句子的**后半**才是这一档的真话）
⑤ **取证**：会话过期那一档 `search` 里**有** `next=`、且 `session.notice` **点名了**回到哪一页
（⇒ 新句子的**前半**也是真话）。

**定点变异**（实测）：把那一句改回改前那两句半假 → **§G15-①②③⑤ 当场红**
（dev 档整轮 smoke，与 G14 那一个变异同跑一轮：**17/18 步 · 797 绿 / 6 红 · 退出码 1**；
红的 6 条逐条是 §G14-③、§G14-④、§G15-①、§G15-②、§G15-③、§G15-⑤）。
⚠️ §G15-④ 在那一轮**仍然绿**（它钉的是「登出不带 `next=`」这个**后端/路由事实**，
与 advice 的措辞无关）⇒ 前提没变、只有判据变红，这正是定点变异要的形状。

---

## 3. G14 —— 错误横幅「**换页要清**」今天没实现

### 3.1 复现取证（改前；真浏览器 + 真鼠标 + CDP，**产品档**）

harness：`$TEMP\p07t11\probe-g14.mjs`（同一套姿势）。

⚠️ **第一次没复现**（如实记）：我先按派单的提示去造「访问一个**越权**资源」——
教师 `T0001` 打开 `/t/students/1`。实测那一页**一条横幅都没有**：`StudentDetail.vue`
把 `sheetError` / `homeError` / `normalizedError` 一律**就地渲染**、刻意不进常驻位
（`/api/teacher/students/1/home` 对 T0001 是 **200**；换成 id=2 才 **403**，
而那一档同样就地渲染 ⇒ 仍然 0 条横幅）。
⇒ 换一条**真的会 `raise`** 的路径：管理台详情页打一个**不存在的主键**
（`views/admin/ResourceDetail.vue` 走 `useAsync`，⚠️ **不带** `silent`，故 catch 会 `raise`）。

改前实测（管理员 `T0003` 从登录表单登进去 → `/admin/students/99999`）：

```
GET /api/students/99999 → 404 not_found

详情页上   {"count":1,"loud":1,"code":"not_found","status":"404",
            "where":"GET /api/students/99999","path":"/admin/students/99999"}
真鼠标点报头导航「教师端」→ /t/dashboard
换页之后   {"count":1,"loud":1,"code":"not_found","status":"404",
            "where":"GET /api/students/99999","path":"/t/dashboard"}      ← ⚠️ **原样跟过去**
history.back() → /t/dashboard
之后       {"count":1,"loud":1,"code":"not_found",…,"path":"/t/dashboard"} ← ⚠️ 同样跟过去
对照：Page.navigate 到 /admin（= **整页刷新**）
之后       {"count":0,…}                                                  ← 只有刷新会清
```

⇒ **G14 成立、且没有被 G8 覆盖**：G8 修的是「换**身份**要清」（`adopt()` / `forget()`），
本条是「换**页**要清」；两格的实测形状上面各有一份，互不蕴含。
⚠️ 结构面同一条结论：改前 `Grep dismiss` 全仓只有 **3** 个调用方
（横幅自己那个「关闭 ✕」+ `session.ts` 的两处），**一个都不在路由上**。

### 3.2 清理时机的单一所有者

修法：`frontend/src/router/index.ts` 里**一个**

```ts
router.beforeEach(() => {
  useApiError().dismiss()
})
```

注册在那个会话守卫**之前**（⇒ 它是这一次导航上第一个跑的钩子）。
⚠️ **单一所有者**：全站只有这一处，**13 个业务页面一行都没动**（派单逐字要求
「不要每个页面各清一次」）。⚠️ `dismiss()` 的调用方因此 3 → **4**，
而后三者**各是它那一格的唯一住址**（✕ = 用户手工、`adopt`/`forget` = 换身份、本钩子 = 换页）。
⚠️ 依赖方向没有环：`router → ApiErrorBanner → api/client → stores/identity`，回不到 `router`；
⚠️ 而 `router/index.ts` **已经**通过 `stores/session` 间接依赖它了 ⇒ 这一行
**没有给产物增加任何一个模块**（产物那 29 个文件一个都没多）。

### 3.3 为什么是 `beforeEach` 而不是派单举的 `afterEach`（⚠️ **顶回**，派单 §4 ②）

`api/client.ts` 是**先** `fireSessionExpired`（⇒ `main.ts` 那个订阅者**同步**调
`session.forget()` + `router.replace('/login?next=…')`）**后** `throw`
（⇒ `composables/useAsync.ts` 的 catch 才 `raise`）。于是「清理点」与「raise」谁先谁后
**不由代码顺序决定、而由那一次微任务/宏任务交织决定**：

* 落在 `raise` 之前 ⇒ 那一块「响亮」的过期横幅被**保住**；
* 落在 `raise` 之后 ⇒ 它被**擦掉**（= 把横幅改成静默，派单明令不许）。

**两种都实测过**（同一套 harness，同一格判据：删掉 `pe_session` cookie → 改业务日触发一批读 →
落到 `/login?next=…` → 量横幅）：

| 清理点 | 档 | 落到 `/login?next=` | 横幅 | 判定 |
|---|---|---|---|---|
| `beforeEach`（本波选的） | dev（8042） | ✅ `?next=/t/alerts` | `count=1 / loud=1 / code=unauthenticated` | 保住了 |
| `beforeEach` | **产品档**（8040 + 新 `dist`） | ✅ `?next=/t/alerts` | `count=1 / loud=1 / code=unauthenticated` | 保住了 |
| `afterEach`（变异） | dev（8042） | ✅ `?next=/t/alerts` | `count=1 / loud=1 / code=unauthenticated` | **也**保住了 |

⚠️ **如实交代**：`afterEach` 只在 **dev 档**跑过一遍；产品档上**没有**再跑它，
因为那要**再重建一次 `dist`**、而本波只允许重建一次（且每一次重建都要打扰甲方一次）。
⇒ 所以「`afterEach` 会擦掉横幅」这句**本波没有实测到**，报告里**不这么写**
（源码 docblock 里也已按这一格实测边界逐字订正过 —— 那一次订正只动注释，
重建之后产物**逐字节未变**，见 §4.1）。

**选 `beforeEach` 的理由因此不是「afterEach 实测坏了」，而是它严格更早**：
会被 `beforeEach` 擦掉的情形是会被 `afterEach` 擦掉的那个集合的**真子集**
（`raise` 早于第一个 `beforeEach` 的那一档两者都擦；`raise` 落在两者之间的那一档
**只有** `afterEach` 擦）。⇒ 在「今天两种都绿」的前提下取**严格更安全**的那一个。

⚠️ 而「今天落在安全的那一侧」**不是靠运气留着的**：新加的 **§G14-⑥** 把它钉住了
（真删一次 cookie、真造一次过期，断言「落到 `/login?next=…` **且**横幅仍在、仍是
`banner--loud`、`code` 仍是 `unauthenticated`」）—— 谁把清理点挪到交织的另一侧，那一拍当场红。
⚠️ 这一拍同时就是派单点名要复跑的那一格，见 §3.4。

⚠️ **派单举的另一个选项「`useApiError` 自己订阅路由」不可行**（也顶回）：
那要 `ApiErrorBanner.vue` import `router`，而 `router/index.ts` → `stores/session.ts` →
`ApiErrorBanner.vue` ⇒ **导入环**；且环上那一次 `router.afterEach(…)` 要在**模块求值期**就跑，
而那一刻 `router` 可能还没被 `createRouter` 造出来。

### 3.4 「`dismiss` 恒早于 `raise`」那条守卫的复跑（派单 §1 第 2 件 ③）

Task 10 是**逐字论证**这一格的（`api/client.ts` 先 fire 后 throw）。本波做了两件事：

1. **复跑它那条既有守卫**：`smoke.mjs` 第 14 步 **§G8-①…⑧ 八拍全绿**（三档各一遍）。
   改后在 `/login` 上抓到的横幅原文（产品档，逐字）：
   ```
   §G8 /login 上那块横幅的原文：unauthenticated 401 GET /api/students?limit=200
   §G8-② 反空转：登出那一刻确实有请求回了 401 → 401 = 4 条 / 共 6 发   ✅
   §G8-③ 反空转：那一刻横幅真的被挂上了、是 banner--loud、code 是 unauthenticated ✅
   §G8-⑤⑥ 换身份登录之后 .banner = 0 / banner--loud = 0 / 正文里没有 unauthenticated ✅
   §G8-⑦⑧ 业务日 as_of 跨身份照旧保留（设计）/ 没有上一个身份的任何痕迹 ✅
   ```
   ⇒ **G8 那一格一格未退**，而「主动登出之后 `/login` 上那块横幅照旧响亮」也被本波新钩子保住了。
2. **把它从论证升级成运行时断言**：新增 **§G14-⑥**（会话过期那一档）+ **§G15-④⑤**
   （两个时机各自的 `?next=` 事实）。⚠️ 于是「横幅不许被改静默」今天有**两个时机各一条**
   运行时断言，而不只是一段注释里的推理。

### 3.5 §G14-⑤ 第一版是**假绿**的（⚠️ 本波自己抓到并修掉；硬规矩 #50）

§G14-⑤ 要钉的是「**另一条**换页路径（popstate）同样清掉了」。第一版它是这么写的：
`Page.navigate` 回详情页 → 撞 404 → `history.back()` → 断言横幅为 0。

⚠️ 而 `Page.navigate` 换一个**文档** ⇒ 随后那一次 `history.back()` 是**整页刷新**
（模块级 `shallowRef` 随文档一起重置）⇒「横幅不在」与本次修法**无关**。

**实测证据**（不是推理）：§2.5/§3.7 那一个定点变异跑完，**§G14-③④ 红了、而 §G14-⑤ 仍然绿**
（`797 绿 / 6 红` 那 6 条里没有它）⇒ 它是一条恒绿的守卫。

**改法**：改成**同文档内**的 SPA 导航 —— 从页面里取
`document.querySelector('#app').__vue_app__.config.globalProperties.$router`
（Vue 3 在 `app.mount()` 里写上去的，dev 与产物里都在，⚠️ **零新增依赖**）→ `router.push`
进详情页 → 撞 404 → `history.back()` 走 popstate；⚠️ 并给它**自带两拍前提**
（router 取得到、back 之后真的换了页）。

**改完重跑同一个变异**（快探针，同一形状）：

```
② 详情页横幅        {"count":1,"loud":1,"code":"not_found","path":"/admin/students/99999"}
③ 真鼠标换页之后    {"count":1,…,"path":"/t/dashboard"}     ← 变异下红（与 §G14-③ 同）
⑤ router.push 之后  {"count":1,"loud":1,"code":"not_found","path":"/admin/students/99999"}
⑤ history.back() 后 {"count":1,…,"path":"/t/dashboard"}     ← ⚠️ **变异下现在也红了**
```

而**带修法**跑同一段：③ `count=0`、⑤ `count=0`（dev 档与产品档各一遍，都绿）。
⇒ ⑤ 从「恒绿」变成「红绿可分辨」。三档整轮 smoke 复跑：**805 / 805 / 837 全绿**（§5.3）。

### 3.6 同族自查（派单 §1 第 2 件 ④）：**不换页**那一格今天仍然没清 ⇒ 登记为 **G19**

**结构面**（`Grep dismiss` 现量）：`composables/useAsync.ts` 的 `reload()` **成功那一支**
一行都不碰那个单例（它只把页面自己的 `error.value` 置回 `null`）⇒ 凡是
「**不换页**、同一次读取由失败转成功」都会把上一轮那块横幅留下。

**运行面**（真浏览器 + 真键盘 + 真鼠标，产品档 8040）：`/s/check-in` 交一个后端不认的值 →
`POST /api/training-logs → 422 request_validation_failed` ⇒ 横幅挂出来；
然后在**同一页**改成合法值再交一次 → `POST → 201` ⇒ 横幅**还在**（逐字）：

```
① 422 之后 {"count":1,"loud":1,"code":"request_validation_failed","status":"422",
            "where":"POST /api/training-logs","path":"/s/check-in?date=2025-12-01"}
② 201 之后 {"count":1,"loud":1,"code":"request_validation_failed","status":"422",
            "where":"POST /api/training-logs","path":"/s/check-in?date=2025-12-01"}
```

⚠️ **本波刻意不修它**（纪律：只修点名的两条，其余一律登记），三条技术理由：
① 病灶**不在路由上**，故 §3.2 那个钩子结构上盖不到它；
② 修它要么动 `useAsync`（⚠️ 而它**盖不到** `views/student/CheckIn.vue` 那一处**手动** `raise`，
   那正是本波唯一取到运行时证据的一条路径），要么各页面各清一次（派单明令禁止）；
③ 一个「只清自己 raise 的那一条」的正确写法要给那个单例加一次**身份比较**
   （`current === 我 raise 的那一个`）—— 那是给交付前最后一个窗口加一块新的共享状态语义。
⇒ 登记为 **G19**（spec §15 逐字给了 Plan 08 的做法：一对 `raiseIfOwner` / `dismissIfOwner`，
于是**仍然是一个所有者**，而 13 个页面里只有**两个**手动 raise 的地方要各加一行）。

⚠️ 探针手法如实交代：取 ② 那一次证据之前先把 `form.noValidate = true`
（`duration_min` 的 `min="0"` 会被**浏览器原生校验**拦在 `submit` 之前，
实测 `-1` 直发后端是 **422 `greater_than_equal`**）。它只为让那一次 422 发得出去，
**不是**被测面的一部分（被测面是横幅的生命周期）。

⚠️ 而 `CheckIn.vue` 那一档 **409 `integrity_conflict` 刻意不进红色横幅**（它是页面内容）——
**设计**，本波一个字都没动（派单逐字点名过）。

**另外扫过的三格（都不成立，如实记）**：
① **换身份** = G8 已修（§3.4 复跑过）；② **整页刷新** = 模块级 ref 随文档重置，
   改前改后都清（§3.1 那一行对照实测）；③ **学生访问 `/admin/*`** = 守卫弹回自己的首页 +
   一句 `session.notice`，**根本不进页面组件的 `setup()`** ⇒ 结构上产生不了横幅
   （实测：学生登录 → `Page.navigate` 到 `/admin/students/99999` → 落 `/s/home`、`count=0`）。

### 3.7 定点变异（摘掉清理那一步 → 红）

见 §2.5 与 §3.5：两轮变异。第一轮（advice 改回半假 + 摘掉 `beforeEach`，同跑一轮 dev 档 smoke）
= **797 绿 / 6 红 / 退出码 1**，6 红逐条 §G14-③、§G14-④、§G15-①、§G15-②、§G15-③、§G15-⑤；
第二轮（只摘掉 `beforeEach`，快探针同形状）= §G14-③ **与** §G14-⑤ 都红。
⚠️ 两轮变异都已还原：收尾 `git status --porcelain` **空**、`git diff HEAD` **空**，
且 §7 那一批「五份 manifest / `.gitattributes` / `.gitignore` 对 `02a7a89` 零 diff」全绿。

---

## 4. 重建与最后一次重打包

### 4.1 重建时刻（⚠️ 本波只重建这一次；随后那一次是**纯注释**订正，产物逐字未变）

```
npx vue-tsc -b   → 退出码 0（先行；改完两条各跑过一次，两次都 0）
npm run build    → 开始 2026-10-17 02:30:02 +08:00
                   结束 2026-10-17 02:30:09 +08:00   （✓ built in 373ms，退出码 0）
```

⚠️ 随后因为**一处纯注释**的措辞订正（`router/index.ts` 里「两种都实测过」那一句要按
§3.3 的实测边界写清「`afterEach` 只在 dev 档跑过」）又跑了一次 `npm run build`
（**02:35:18** 完成）：

```
两份逐文件 sha 清单对比 → identical = True   （29 文件 / 686 788 B，一格不差）
```

⇒ **甲方那条链接只换过一次版**（02:30:09 那一刻）；02:35:18 那一次写下去的是**同一批字节**。
⚠️ 本波全部功能验证（G15/G14 的改后取证、两轮定点变异、dev 档 smoke）一律走
**我自己的 vite（8042）+ 产品档后端（8040）**，故重建**之前**就做完了 ——
与 Task 10 同一条姿势。

### 4.2 新旧哈希对照

`frontend/dist`：**29 文件 / 686 680 B → 29 文件 / 686 788 B**（**+108 B**）。
逐格：**逐字未变 17 / 同名而内容变 1（`index.html`）/ 改名字 11** ⇒ **12 / 29 个哈希换了**。
⚠️ 与派单预判的「改任何 `.vue` 都会换 **12/29** 个哈希」**逐字对上**。

派单点名的那三个：

| | 改前 | 改后 |
|---|---|---|
| `index.html` | 2 729 B / `AC8484448A88779D` | **2 729 B / `3A6E04ED9FE1622E`** |
| 入口 JS | `index-DahkQ_Ao.js` 175 726 B / `BDB6730D6CCAD2B4` | **`index-CD9fWvKJ.js` 175 834 B / `012E148DC2CA8A0C`** |
| 入口 CSS | `index-CXfWaVPp.css` 65 374 B / `08D2A30C44B70252` | **`index-D2BHlq_t.css` 65 374 B / `AE1857BB40A981A6`** |

改了名字的 11 个（逐个都量过）：`index-*.js`、`index-*.css`，以及 9 个懒加载 chunk
`AlertQueue` / `AuditLogList` / `ClassReport` / `Dashboard` / `ResourceDetail` / `ResourceList` /
`StudentDetail` / `TeacherNav` / `contract`。
⚠️ **那 9 个 chunk 的字节数一格都没变**（例如 `AlertQueue` 两侧都是 22 187 B、
`StudentDetail` 两侧都是 43 348 B），只换了名字 —— 那正是 Vue scoped-CSS 的 `data-v-` id
由**源内容**派生的结果（派单逐字预告过「这是预期的」）。
⚠️ 入口 CSS 同样**字节数不变**（65 374 B）而 sha 变，同一条理由。
⚠️ 逐字未变的那 17 个：4 个自托管 woff2、2 个品牌 svg、favicon、以及 10 个没被这次改动
波及的 chunk/资产。

### 4.3 甲方那条 URL 的匿名复核（⚠️ 只发匿名 GET）

```
base = https://related-llp-briefing-holds.trycloudflare.com   （读自 .trial\public-url.txt）

GET /api/health                → 200   54 B  {"status":"ok","tables":28,"students":60,"trial":true}
GET /login                     → 200  2 729 B  sha256[:16]=3A6E04ED9FE1622E
GET /                          → 200  2 729 B  sha256[:16]=3A6E04ED9FE1622E
   两份 index.html 引用的 assets = index-CD9fWvKJ.js + index-D2BHlq_t.css      ← **新**哈希
   与本地新 index.html 逐字节相同 = True
GET /assets/index-CD9fWvKJ.js  → 200  175 834 B / 012E148DC2CA8A0C  ← 与本地**逐字节相同**
GET /assets/index-D2BHlq_t.css → 200   65 374 B / AE1857BB40A981A6  ← 与本地**逐字节相同**
GET /assets/index-DahkQ_Ao.js  → **404**   ← 旧哈希已不在 ⇒ 活链接**确实**切到了新版
```

⇒ **甲方需要做的唯一一件事是 Ctrl-F5**（已经打开的页面在懒加载一条没访问过的路由时会 404 一次）。

### 4.4 派单 §2 那九步逐步的取证（⚠️ 顺序承重；G18 的病灶正是 ⑥ 排在 ⑤ 之前）

| 步 | 要求 | 实测 | 判定 |
|---|---|---|---|
| 1 | 先做完第 1、2 件（改前端源） | `34917a4` 之前完成；改前改后各有运行时取证（§2.2 / §3.1 / §3.4） | ✅ |
| 2 | `npx vue-tsc -b` 绿 → `npm run build` → `check:tokens` / `check:dist` 绿 | vue-tsc 退出码 **0**（三次）；build **02:30:02 → 02:30:09**，退出码 **0**；`check:tokens` **36 文件 / 下界 25 / offender 0**；`check:dist` **全绿**（§5.5） | ✅ |
| 3 | 匿名复核甲方那条 URL 仍 200 且服务的是新哈希 | §4.3 逐行（含旧哈希 **404** 那一格反证） | ✅ |
| 4 | 三档 smoke + 全量 pytest | §5.3（**805 / 805 / 837**，三档各 **18/18 步 · 0 红 · 退出码 0**）+ §5.1（**1633 passed**） | ✅ |
| 5 | **然后才**改文档 | spec **§13.23**（新，8 个小节）+ §15 台账（划掉 G14/G15/G18、补 **G19**、组 G 标题计数 12 → **10 在册**）+ `progress.md`（§1 补一条 Task 11 + 新增 §5）= commit **`be13fa9`** | ✅ |
| 6 | **最后**重打包 | `scripts\package.ps1` 退出码 **0**，产出 `pe-ims-trial-20261017-031056.zip`（⚠️ 排在 `be13fa9` **之后**） | ✅ |
| 7 | 报旧包三个数之后删掉旧包，`dist-pack\` 只留一份 | 旧包三个数已报（§4.6）→ 删掉 → `dist-pack\` 实测 **1 个文件** | ✅ |
| 8 | 包内 `dist` 与仓库 `dist` 逐文件 sha 相同 + 含空格中文目录里起服务通 | 六格 ③（§4.5）+ 六格 ②⑤（§4.7） | ✅ |
| 9 | 不动点：包那三个数只进报告、报告不进包；报告的 sha 不印进报告自己 | 本报告**刻意不印**自己的字节数/sha；spec §13.23.6 逐字交代了为什么那三个数**不写进 spec**（spec 进包 ⇒ 会构成循环） | ✅ |

### 4.5 Task 4 那六格逐格复核（⚠️ ④ 与 ⑥ 两格 = **G18 的验收**）

| 格 | 判据 | 实测 | 判定 |
|---|---|---|---|
| ① | 新包三个数与旧包对照 | 见 §4.6 | ✅ |
| ② | 解包后 health 200 + **16 条路由逐条 200** | `/api/health` → **200 / 54 B** / `{"status":"ok","tables":28,"students":60,"trial":true}`；**16/16** 条路由 200、每条 **2 729 B** 且 `<div id="app">` 在场、**与仓库新 `index.html` 逐字节相同**；服务出去的产物 = **`index-CD9fWvKJ.js` + `index-D2BHlq_t.css`**（= 新哈希） | ✅（详见 §4.7） |
| ③ | 包内 `dist` 与仓库 `dist` **逐文件 sha 相同** | 两侧各 **29 文件 / 686 788 B**；只在包里 **0** / 只在仓库里 **0** / 同名而 sha 不同 **0** | ✅ |
| **④** | 包内**说明书**与仓库那份**逐字节相同** | 两侧各 **29 811 B / `B6B37D236532F426`**（175 行）⇒ **逐字节相同** | ✅ |
| ⑤ | **含空格与中文的目录**里起服务通 | 见 §4.7（`$TEMP\p07t11\体育系统 试用 pack3\`） | ✅ |
| **⑥** | 包内 **spec** 与仓库那份**逐字节相同**（⚠️ Task 9 实测包里那份少 448 行；Task 10 留下 **G18**） | 两侧各 **833 667 B / 8 058 行 / `FB8D9B5A369CC109`** ⇒ **逐字节相同**；⚠️ 并且**包内那份 spec 含本波刚写的结案节**（逐个 needle 在**包内**那一份上数：`### 13.23 Plan 07 Task 11` **1** 次 · `#### 13.23.6 重建产物 + 最后一次重打包` **1** 次 · `- **G19 · 错误横幅在「**不换页**` **1** 次 · `✅ **Plan 07 Task 11 已处置 —— 本条划掉**` **1** 次 · `✅ **Plan 07 Task 11 已修 —— 本条划掉**` **1** 次 · `**十件在册**（G1/G2/G3/G4/G5/G6/G13/G16/G17/G19）` **1** 次） | ✅ **G18 变绿** |
| 附 | 包里的 **README + 四个脚本**与仓库逐字节相同 | `README.md` 7 267 B / `E0229E74C83D355A` · `trial.ps1` 41 523 B / `0D00814BB2BB7EA1` · `tunnel.ps1` 91 278 B / `D4D095FF8C318422` · `serve.ps1` 47 990 B / `93E7F727F6746613` · `package.ps1` 45 126 B / `35F4FC02414C7BAA` —— **五个都 ✓** | ✅ |

⚠️ **G18 的验收就是 ⑥ 那一格**：Task 10 的病灶是「重打包发生在 spec 那个 commit **之前**」，
故包里那份 spec 是「台账未结案」的那一份。本波把顺序倒过来（§4.4 第 5→6 步），
于是包里那份 spec **逐字节等于**仓库最终态、且**含 §13.23 与 G19**。
⚠️ 而 ④ 那一格（说明书）本波**不需要**变：两份交付文档都不引用被改的那一句（§2.4 实测 0 命中），
故它一个字节都没动、仍然逐字节相同。

### 4.6 新包三个数与旧包对照（⚠️ 报完即删旧包）

| | 旧包（Task 10 打的那一份） | **新包（本波）** |
|---|---|---|
| 文件名 | `pe-ims-trial-20261017-000506.zip` | **`pe-ims-trial-20261017-031056.zip`** |
| 字节数 | **10 417 600 B** | **10 451 259 B**（**+33 659 B**） |
| sha256[:16] | **`C442737A325528D1`** | **`327D54A30C55E6D2`** |
| 文件数 | **339** | **339**（一格不变） |

⚠️ `+33 659 B` 而文件数不变的理由：本波改的是**已有文件的内容** ——
spec **+26 047 B**（§13.23 新 8 小节 + §15 台账划 3 补 1）、`smoke.mjs` **+21 400 B**
（§G14/§G15 两组守卫；⚠️ `frontend/scripts/**` 整个进包）、
`ApiErrorBanner.vue` 与 `router/index.ts` 的净增落在 `dist` 里（**+108 B**）。
⚠️ 包内分组实测：`Document` **28 个 / 8 398 096 B** · `backend` **207 个 / 6 388 115 B** ·
`frontend` **99 个 / 3 103 774 B** · `scripts` **4 个 / 225 917 B** · `README.md` **1 个 / 7 267 B**
（⚠️ 与 Task 10 那一份逐格同形，只有 `Document` 与 `frontend` 两组的字节数长了）。

**旧包已删**（`Remove-Item`），收尾实测 `dist-pack\` 里 **只有 1 个文件** =
`pe-ims-trial-20261017-031056.zip` / 10 451 259 B。
⚠️ `package.ps1` 自己**刻意不删旧包**（它逐字打印「那是你的产物，一个打包脚本替你做删除决定
是静默的那一类事故」），故删除是本波按派单手工做的那一步。

### 4.7 含空格与中文的目录里起服务（终审 S1-1 的复验路径；Task 7 修过、Task 9/10 各复验过一次）

解包目录逐字是 `$env:TEMP\p07t11\体育系统 试用 pack3\`（⚠️ **含空格 + 含中文**），
在**正常终端**里跑包里那份 `scripts\trial.ps1 -Port 8044`（⚠️ 走**缺省**库路径 =
`<解包目录>\backend\pe_trial.db`，⚠️ 于是它**碰不到**甲方那一份）：

```
① 禁区守卫     backend\pe.db 不存在 ✓ / 试用库的 URL 不指向它 ✓
③ 灌库         [1/7]…[7/7] 全过；semester 2 / student 60 / course_section 5 / enrollment 120 /
               prescription 60 / class_session 8 / rpe_record 240 / training_log 840 /
               mini_test 180 / alert 32 / notification 19 / weekly_class_report 5
④ 禁区复核     backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓
⑤ 起服务       uvicorn PID 23996 → http://127.0.0.1:8044
               /api/health → 200（轮询 1 次）{"status":"ok","tables":28,"students":60,"trial":true}
⑤b 念三行      「库里 60 名学生的姓名、学号与体测成绩全部由生成器造出」（N 从库里真数出来的）
```

⇒ **六格 ⑤ 通**（⚠️ 这一格与 Task 10 的 G17 不同档：G17 是「**无控制台** +
`Start-Process -RedirectStandardOutput`」那一档下的 mojibake，本波**没有**去碰它，
它也**不在**本波范围里；本波跑的是**正常终端**那一档，与甲方 IT 的用法逐字同形）。

**六格 ②** 逐条（打在 8044 上）：`/api/health` → **200 / 54 B**；
**16/16** 条路由（`/login`、`/bind`、`/s/home`、`/s/weekly-sheet`、`/s/check-in`、`/s/rpe`、
`/s/mini-test`、`/s/notifications`、`/t/dashboard`、`/t/report`、`/t/alerts`、`/t/students/4`、
`/admin`、`/admin/audit-logs`、`/admin/students`、`/admin/students/4`）**全部 200**、
每条 **2 729 B** 且 `<div id="app">` 在场、且与仓库新 `index.html` **逐字节相同**；
`/login` 引用的 assets = **`index-CD9fWvKJ.js` + `index-D2BHlq_t.css`**。

⚠️ 8044 收尾已 `StopCommand`；`$env:TEMP` 下我造的 `p07t11\`（含那个解包目录）已删净并复验（§7）。

---

## 5. 测试面

### 5.1 `pytest`：**1633 → 1633 passed**（一格未变）

| 命令（cwd = `backend\`） | 结果 | 用时 |
|---|---|---|
| `python -m pytest -q --no-header --no-cov` | **1633 passed**, 1 warning | 184.11 s |

⚠️ **本波后端产品代码 0 行改动** ⇒ 这个数字**应当**不变，而它确实没变
（新增的守卫一律住在 `frontend/scripts/smoke.mjs` 里，不进 pytest 的面）。

### 5.2 覆盖率三口径四格（⚠️ 与基线**逐字相同**）

| 口径（⚠️ 第三格 canonical 写法是**点号** `--cov=app.static`） | Stmts | Miss | Branch | BrPart | Cover | 基线 |
|---|---|---|---|---|---|---|
| `--cov=app/domain --cov-branch` | **1268** | **0** | **376** | **0** | **100%** | 1268/0/376/0/100% ✅ 逐字相同 |
| `--cov=app --cov-branch` | **7311** | **201** | **1778** | **115** | **96%** | 7311/201/1778/115 ✅ 逐字相同 |
| `--cov=scripts --cov=app.static --cov-branch` | **583** | **173** | **164** | **24** | **69%** | 583/173/164/24 ✅ 逐字相同 |

三口径各 **1632 passed, 1 skipped**（与基线同形）。用时 299.71 s / 309.26 s / 286.77 s。
⚠️ `Cover` 列**不是**基线（派单逐字交代过），故上表按 Stmts/Miss/Branch/BrPart 四格对账。

### 5.3 `smoke.mjs` 三档：**770 / 770 / 802 → 805 / 805 / 837**（各 **+35**）

| 档 | 怎么跑的 | 步数 | 断言 | 退出码 | 第 14 步 |
|---|---|---|---|---|---|
| **dev** | `PE_API_BASE=http://127.0.0.1:8040 PE_WEB_BASE=http://localhost:8042`（⚠️ **重起过一次 vite**：smoke 文件头把「跑之前重起 `npm run dev`」写成硬要求，§D7 那一拍对模块图的新鲜度敏感） | **18/18 全绿** | **805 绿 / 0 红** | **0** | 272/272 |
| **产品档** | `PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8040`（`serve.ps1 -SkipBuild`，同源） | **18/18 全绿** | **805 绿 / 0 红** | **0** | 272/272 |
| **试用档** | `PE_TRIAL=1 PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8043`（⚠️ **原件** `trial.ps1` + `PE_DB_URL` 起的，顺带端到端复验 G7） | **18/18 全绿** | **837 绿 / 0 红** | **0** | 304/304 |

⚠️ **断言数只增不减**：三档各 **+35**（= §G14 那一组 + §G15 那一组；⚠️ **步数仍是 18**，
因为两组都加在第 14 步**里面**）。试用档比另两档多 32 条是那 16 条路由 × 2 拍试用告示
（本波一格未动）。
⚠️ 每档跑之前一律**换一份刚灌的库**（smoke 会写脏演示库，它自己的第 0 步就是
「你是不是忘了复原」的守卫）。

### 5.4 ⚠️ 公网档**没跑**（如实记；与 Task 10 同一条处置）

派单逐字：「⚠️ **公网档 Task 10 没跑**，基线仍是 Task 8 的 **778**；⚠️ **本波也不要打甲方那条**」。
⇒ 本波**一次都没打甲方那条 URL 上的任何鉴权/写入路径**（§4.3 那 6 发全是匿名 GET）。
⚠️ 也**没有**为了这一格另开第二条公网隧道，理由三条（与 Task 10 §7.3 逐字同一条）：
① 三档（dev / 产品档 / 试用档）是**明令**的，三档全绿；② 在**甲方正在试用**的当口
再开一条公网入口是一次**新的暴露面**（`tunnel.ps1` 自己那六条风险告示逐字写着
「随机不等于鉴权」）；③ 本波改的两条**与 cookie 的 `Secure` / 隧道边缘**都无关
（改的是一句 advice 的措辞与一个路由钩子），而公网档独有的那一格判据
（`PE_COOKIE_SECURE`）本波**一个字都没碰**。

### 5.5 两个静态守卫

```
npm run check:tokens → 扫描面 36 个文件（下界 25）· offender 0 · 退出码 0   ✅ 一格未退
npm run check:dist   → 全绿 · 退出码 0
   · 产物里 adoptFromUrl 出现 0 次（而源码里确实存在 ⇒ 谓词不空转）
   · fonts.googleapis.com / fonts.gstatic.com 各 0 次（源码侧扫了 56 个文件、1 360 000 字符，同样 0 次）
   · 4 条「会变假的渲染正文」各 0 次，而 4 条谓词的**反空转**（抓得到改前那句 / 放过改后那句）8 拍全绿
   · 自托管的字体确实在产物里（⇒「0 次」不是因为字体压根没进产物）
```

⚠️ **本波没有引入任何新的裸值**：改的是一句中文 advice 与一个路由钩子，
`<style>` 一个字都没动 ⇒ `check:tokens` 的 36 / 下界 25 一格未退（派单 §1 第 1 件 ④）。

---

## 6. 待清扫 / 关切 / 没按派单做的 / **顶回**

### 6.1 待清扫（本波新登记 **1** 条，住 spec §15 **G19**）

1. **G19** · 错误横幅在「**不换页**、同一个页面上先失败后成功」时不清
   （= G14 的**同族残留**，而 G14 本身已划掉）。运行时取证在 §3.6
   （`/s/check-in` 的 422 → 201，两份逐字 JSON）。⚠️ Plan 08 的做法逐字写在 §15 G19 里
   （给那个单例加一对 `raiseIfOwner` / `dismissIfOwner` ⇒ **仍然是一个所有者**）。

⚠️ 既有的 **G13 / G16 / G17** 三条本波**一格未动**（派单逐字要求「不要顺手做」）：
· **G13**（登出白发一整批注定 401 的读请求 = 公网档 5 趟边缘往返）—— ⚠️ 本波实测它**还在**：
  §2.2 那一次登出仍是 **6 发 / 4 条 401**，与 Task 10 逐字同形（⇒ §G8-② 那两拍仍绿）；
· **G16**（不渲染处的同族开发账本，含 `README:94`）；
· **G17**（`PE_DB_URL` 的编码边界；⚠️ 本波跑的是**正常终端**那一档，两次都全通，
  与 Task 10 的判定一致，**没有**去碰「无控制台 + 重定向」那一档）。
⚠️ 以及 spec §15 台账其余各条（本波之后 **34 条在册 / 7 组**）一条都没动。

⚠️ 另外 **2 条**是既有的、本波**没有**动：`$env:TEMP` 下我造的 `p07t11\`
（收尾已删净并复验，§7）、`pe_trial_csv_41684`（**8030 正在用**，派单明令不许删，✓ 留着）。
⚠️ 而 Task 10 留下的 `p07t10-cdp-2VHmiR\`（一个 CDP profile 目录）**不在本波责任面**，
我**没碰**（收尾实测它仍在）。

### 6.2 关切（**3** 条）

1. ⚠️⚠️ **甲方需要 Ctrl-F5**（本波唯一需要他们做的动作）：`dist` 已在
   **2026-10-17 02:30:09 +08:00** 重建，那条活链接**已自动切到新版**
   （§4.3：新哈希在、**旧哈希 404**），而**已经打开的页面**在懒加载一条没访问过的路由时会
   404 一次。⚠️ 随后 02:35:18 那一次重建写下去的是**同一批字节**（`identical = True`）
   ⇒ 甲方只被换过**一次**版。
2. ⚠️ **合并 `main` 之后还要不要再重打一次包**（派单 §6 第 11 条点名要想清楚的一格）：
   **不需要**。判据三条，逐条实测过：
   ① 合并是 **ff**（`main` 在 `dd48b2a`，而 `p07/final-polish` 从 `02a7a89` 起、
      `02a7a89` 的祖先里就含 `dd48b2a` 之后那 6 个 commit ⇒ ff 不改任何文件内容）；
   ② **打包时的工作树 == 交付的 commit**：`package.ps1` 跑在 `be13fa9` 已提交之后，
      而那一刻 `git status --porcelain` **空**、`git diff HEAD` **空**（§7 收尾复量同样空）
      ⇒ 包里的每一个字节都来自 `be13fa9` 那棵树；
   ③ 六格 ③④⑥ + 附（README 与四个脚本）**逐文件/逐字节**相同（§4.5）⇒ 包与仓库最终态一致。
   ⚠️ **唯一的例外情形**（如实交代）：若控制者在合并**之后**又往 `main` 上追加了任何
   改到 `Document/**`、`README.md`、`scripts/**`、`backend/**`、`frontend/dist` 的 commit，
   那一份包就**过期**了、要重打；⚠️ 而只加 `.superpowers/**`（例如本报告本身）
   **不需要**重打 —— 报告**不进包**（`package.ps1` 的排除清单里逐字有 `.superpowers`）。
3. ⚠️ **G19 是甲方看得见的**（虽然比 G15 轻一档）：在打卡页撞一次 422 之后就地改对再交，
   头顶那块「请求参数没通过校验」会留着。⚠️ 它**不是假话**（那一次 422 确实发生过），
   且有一条**手工出口**（横幅自己那个「关闭 ✕」）⇒ 本波判定它**不是交付阻塞项**，
   登记交 Plan 08。

### 6.3 没按派单做的（**2** 处，如实记）

1. ⚠️ **公网档 smoke 仍然没跑**（理由三条见 §5.4；派单本波逐字写的是「本波也不要打甲方那条」）。
2. ⚠️ **commit 用了 3 个，不是建议的 4 个**。派单建议 ①G15 ②G14 ③重建取证+文档 ④报告。
   实测拆不开 ①②：两条改动**共用** `ApiErrorBanner.vue`（G15 改那一句 advice，
   而它的 docblock 与 `dismiss()` 的注释要同时交代 G14 的新调用方），
   而两组守卫是 `smoke.mjs` 第 14 步里**同一段连续插入**（§G14 那一组的 `g14*` 助手
   被 §G15 那一组**复用**）⇒ 按文件拆会得到两个**都不自洽**的中间 commit
   （① 里没有 §G15 的守卫、② 里的 §G15 助手引用一个不存在的块），
   而按 hunk 拆要**交互式暂存**（派单明令不用 `-i`）。
   ⇒ 合成 `34917a4` 一个自洽 commit（message 里逐字交代了为什么合成一个）。
   ⚠️ 派单说的「④ 报告」与「重打包不产出 commit」两条本波照办：
   `dist-pack/` 与 `frontend/dist` 都在 `.gitignore` 里，**没有为凑数入库任何 gitignore 项**
   （§7 逐个核过 8 处）。

### 6.4 **顶回**（**2** 处）

1. ⚠️ **G14 的清理时机：`router.beforeEach`，不是派单举的 `afterEach`**（派单 §4 ②）。
   逐字理由与实测表在 §3.3。⚠️ **顶回的是「举例」而不是「裁定」**：派单写的是
   「例如 `router/index.ts` 的 `afterEach` **或** `useApiError` 自己订阅路由」，
   两个例子我都核过 —— 第二个**结构上不可行**（导入环 + 模块求值期就要用 `router`），
   第一个**今天能过**而 `beforeEach` 严格更安全。⚠️ **单一无疑点**：派单要求的
   「单一所有者」「不要每个页面各清一次」「不许把横幅改成静默」三条**全部满足**，
   且各有一条运行时断言钉住（§G14-③④⑤ 与 §G14-⑥）。
2. ⚠️ **G15 该不该在本波修：同意控制者的改判，不顶回**（派单 §4 ① 要我核这一格）。
   核的结论：Task 10 说「那是**一行**的事」—— 实测**确凿**（改的就是
   `BRANCHES.unauthenticated.advice` 那一个字符串字面量），⚠️ 而它担心的
   「改它要连着改 spec」也**确凿但很轻**：全仓引用改前那句的 4 处**全是开发文档/注释**，
   按「结案总账不重写」的口径**一个字都不用改**，只需在 §15 G15 上**加**一行划掉 + 指针
   （本波就是这么做的）；⚠️ 两份**交付**文档（说明书 / README）**0 命中**
   ⇒ 不需要动它们、也不需要重打说明书那一格。⇒ **边际成本确实是 0，同意修**。

⚠️ 另外核过而**没有**顶回的裁定（派单 §4 列的 5 个可能点里的其余 3 个）：
· **③ G14 是否其实已被 G8 覆盖** —— **不是**，§3.1 给了两格各自的实测形状（换身份清、换页不清）；
· **④「后端产品代码不许动」** —— 本波**一行都没动**，且两条的根因**都在前端**
  （一句 UI 措辞 + 一个路由钩子），⇒ 无需顶回；`openapi` 逐字未变就是这一格的机器证据；
· **⑤ 重打包的顺序（§2 那九步）** —— **顺序是对的**，本波逐步照做（§4.4），
  且第 9 步那个「不动点」判断成立（报告不进包 ⇒ 不构成循环）。

---

## 7. 最终验收（⚠️ 逐格亲量）

| 格 | 实测 | 判定 |
|---|---|---|
| 表数 | `len(Base.metadata.tables)` = **28**；`/api/health` 三档都回 `"tables":28` | ✅ |
| 迁移链 | `alembic history` = **4 个 revision / 单头**：`<base>` → `53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → **`0ac943e0da9b (head)`** | ✅ 仍 4、仍单头 |
| 残差 diff | `tests/db/test_migration_chain.py` → **8 passed**（含 `test_the_migration_chain_is_in_sync_with_the_models`） | ✅ 仍 **0** |
| 扫描面 | `app/pipeline 10 + app/db 14 + app/domain 18 + app/api 26 + app/auth 4` = **72** 个 `.py` | ✅ |
| `_MODELS_PUBLIC_BASELINE` | AST 读 `tests/db/test_models.py` 那一个 list → 长度 **33** | ✅ |
| 黄金用例 | `tests/fixtures/golden_cases.json` → `input` **14** 例 / `expected` **14** 例 | ✅ |
| 未定型响应 | openapi 上 200 的 schema 是 `additionalProperties: true` 的 object = **24** 个（23 个泛型 list + `/api/health`，逐个路径已列出） | ✅ |
| openapi 五格 | **74 路径 / 102 操作 / 挂 security 84 / GET 63（15 匿名 + 48）/ securitySchemes 3**；catch-all **0** | ✅ 五格全对 |
| openapi 字节 | **420 367 B / sha256[:16] `6058F97F09B35855`** | ✅ **逐字未变**（本波只改前端 ⇒ 应当不变，而它确实没变） |
| `check:tokens` | **36 文件 / 下界 25 / offender 0** | ✅ 一格未退 |
| `check:dist` | **全绿**（含 8 拍反空转） | ✅ |
| 依赖清单守卫 | `backend/pyproject.toml` · `frontend/package.json` · `frontend/package-lock.json` · `.gitattributes` · `.gitignore` 对 `02a7a89` **零 diff**（`git diff --stat` 逐个空）；新增依赖**后端 0 / 前端 0** | ✅ 一字不红 |
| 四个数据指纹 | `national_standard_2014.csv` **21 412 B / `D2C8E539E2FA0029`** · `exercises.yaml` **23 247 B / `5394B37F01DAC9AC`** · `exercise_equivalence.yaml` **8 245 B / `822CB86A5E998301`** · `alert_rules.yaml` **6 037 B / `E48E3AC82BB45BB7`** | ✅ 四个逐个对上 |
| 18 模板指纹 | `backend/data/prescription/*.yaml` **18 个**，逐个 sha 已量（`RED-END-ABN-01` `C0C61D2140A521D0` … `GRN-SPD-NOR-18` `2389C1A03E6ABBCE`）；`backend/data/**` 合计 **24 个入库文件** | ✅ |
| `git diff 02a7a89 HEAD -- backend/data` | **空** | ✅ |
| `backend/pe.db` | 存在 = **False** | ✅ |
| `backend/data/seed/` | **0 文件**（`-Recurse` 数过） | ✅ |
| 八处 gitignore 项 | `backend/pe.db` · `backend/pe_demo.db` · `backend/pe_trial.db` · `backend/backups` · `frontend/dist` · `tools` · `.trial` · `dist-pack` —— `git ls-files` 里**各 0 个文件** | ✅ 一个都没入库 |
| 收尾五格 | §1.5 逐格（PID 45156 / 37196 仍在、`pe_trial.db` 与 `public-url.txt` **逐字未变**、`dist` 29 文件、甲方 URL **仍 200 且服务的是新哈希**） | ✅ |
| 我自己起的进程 | **全部已停**：8040 / 8042 / 8043 / 8044 收尾在 `Get-NetTCPConnection -State Listen` 里**一个都不在**；CDP 无头浏览器逐个 `kill` + 删 profile，`$env:TEMP` 下 `p07t11*` 残留 **0 个**；我自己的隧道**一条都没开**（§5.4） | ✅ |
| `$env:TEMP\p07t11` | 已 `Remove-Item -Recurse -Force` 并**复验**：`p07t11` 存在 = **False**；⚠️ 连带删掉我造的 `pe_trial_csv_15376`（8043 那一次）与 `pe_trial_csv_52072`（8044 那一次）—— ⚠️ 两个都是我起的 `trial.ps1` 造的，而它们**没有**被脚本自己的 `finally` 删掉（因为我是用 `StopCommand` 停的）⇒ 手工补删并复验 | ✅ 已删净 |
| ⚠️ 该留的三个 | `pe_trial_csv_41684`（**8030 正在用**）· `p07ctl` · `pe_tunnel_8030` —— 收尾实测**三个都还在** | ✅ 一个都没删 |
| spec | 工作树 **833 667 B / 8 058 行 / 全 CRLF（裸 LF 0）/ 无 BOM / sha256[:16] `FB8D9B5A369CC109`**；入库 blob `7e1b89df9031` **825 609 B / 8 058 裸 LF / `A202AE5464266EAD`**（⚠️ 两个口径都报；差值 **8 058 B** == CRLF 行数，按设计） | ✅ |
| 说明书 | **29 811 B / 175 行**（上限 200）/ `B6B37D236532F426` —— **一个字节都没动** | ✅ |
| README | **7 267 B / 111 行** / `E0229E74C83D355A` —— **一个字节都没动**（⚠️ 它那 1 处波次编号仍是 **G16 ③**） | ✅ |
| `progress.md` | **35 850 B / 427 行 / 纯 LF / 无 BOM**（`-text` ⇒ 工作树 == blob，差值 0） | ✅ |
| commit | `34917a4`（G15 + G14 + 守卫 + 变异）· `be13fa9`（spec §13.23 + §15 台账 + progress.md）· 本报告那一个（见下） | ✅ |

⚠️ **报告的 sha 刻意不印进报告自己**（派单 §2 第 9 步；前几波在这上面连踩四次，
教训在 `task-8-report.md` §8.6）。

---

## 8. 行尾复核（⚠️ 逐个被改文件，**双向可逆**判据）

⚠️ 判据用派单点名的那一条：对 `Document/**` 与 README，「工作树字节 == blob 字节」**按设计不成立**
（差值恰好 = CRLF 行数）⇒ 正确判据是**双向逐字节可逆**：
**正向** `git hash-object <file>`（走 clean 过滤器）== index 里那一个 blob 的 sha；
**反向** `git checkout-index` 到一个空目录 == 工作树那一份（逐字节）；
外加 `git status --porcelain` 与 `git diff HEAD` 都空。
⚠️ Task 10 在这一格上先用错判据报了 9 格假红 —— 本波**没有**重犯。

| 文件 | 工作树 | 正向 | 反向 | `git ls-files --eol` |
|---|---|---|---|---|
| `Document/2026-09-28-体育闭环原型-设计spec.md` | 833 667 B / CRLF 8 058 / 裸 LF **0** / BOM False | `7e1b89df9031` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/text eol=crlf` |
| `.superpowers/…/progress.md` | 35 850 B / CRLF **0** / 裸 LF 427 / BOM False | `69b56830477c` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/lf attr/-text` |
| `Document/2026-10-15-甲方试用说明书.md`（**未改**，一并核） | 29 811 B / CRLF 175 / 裸 LF 0 | `cdf244451e07` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/text eol=crlf` |
| `README.md`（**未改**，一并核） | 7 267 B / CRLF 111 / 裸 LF 0 | `0751c6c69498` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/` |
| `frontend/src/components/ApiErrorBanner.vue` | 20 313 B / CRLF 447 / 裸 LF **0** / BOM False | `1796a7da7aba` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/` |
| `frontend/src/router/index.ts` | 27 868 B / CRLF 464 / 裸 LF **0** / BOM False | `2df64f87d8a7` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/` |
| `frontend/scripts/smoke.mjs` | 434 474 B / CRLF 6 045 / 裸 LF **0** / BOM False | `9c65f953ab00` == index blob ✅ | 逐字节相同 ✅ | `i/lf w/crlf attr/` |
| 本报告 `.superpowers/…/task-11-report.md` | 纯 LF / 无 BOM（写完当场用同一套脚本核过，双向可逆 ✅） | 见 §7 那个 commit | — | `i/lf w/lf attr/-text` |

⚠️ **编辑手法**：`.ts` / `.vue` / `.mjs` 三个文件用编辑工具改完之后，**每个文件当场**跑一次
「二进制模式统一成 CRLF」的 Python 脚本再核 `git ls-files --eol`
（第一次核就抓到 `router/index.ts` 是 `w/mixed` —— 我插入的那 49 行是裸 LF，
而文件其余 404 行是 CRLF ⇒ 归一之后变成 `w/crlf`，与仓库里每一个同族文件同形）；
`Document/**` 的两个文件与 `progress.md` 一律用 **Python 二进制模式**插入
（spec 写 CRLF、progress.md 写 LF），⚠️ 一次都没用 `sed` / `awk` / heredoc。
⚠️ 收尾实测：`git status --porcelain` **空**、`git diff HEAD` **空** ⇒ 没有任何一行
「只差行尾」的幽灵改动。

⚠️ **`.ps1` 一个都没改**（本波只动前端 + smoke + 文档），故「CRLF+BOM」那一格本波不涉及；
而包里那四个 `.ps1` 与仓库**逐字节相同**（§4.5 附格，含 BOM 在内）。

---

## 9. commit 与自洽性

| # | sha | 一句话 | 自洽？ |
|---|---|---|---|
| ① | **`34917a4`** | `fix(frontend)`: G15 + G14 —— `/login` 那句 advice 改成真话 + 错误横幅「换页要清」（含 §G14/§G15 两组守卫与两轮定点变异的逐字交代） | ✅ 自洽（`vue-tsc` 0 · `node --check` 0 · 三档 smoke 805/805/837 全绿 · 后端 0 行 ⇒ 不依赖 ②） |
| ② | **`be13fa9`** | `docs(spec+ledger+progress)`: Task 11 的结案节 §13.23 + 台账划 3 补 1 + `progress.md` §1/§5 | ✅ 自洽（纯文档；⚠️ 它**必须**排在重打包之前 —— 那正是 G18 的处置） |
| ③ | 本报告那一个 | `docs(report)`: Task 11 实现者报告 | ✅ 自洽（纯文档，**不进包**） |

⚠️ **重打包不产出 commit**（派单逐字）：`dist-pack/` 与 `frontend/dist` 都在 `.gitignore` 里，
**没有为凑数入库任何 gitignore 项**（§7 逐个核过 8 处，各 0 个文件）。
⚠️ Task 10 的第 ④ 个 commit 是空的；本波**没有**造空 commit（§6.3 第 2 条逐字交代了
为什么是 3 个而不是建议的 4 个）。
⚠️ 全程 **没 push、没碰 `main`、没自己合并**（`main` 收尾仍在 `dd48b2a`）。
