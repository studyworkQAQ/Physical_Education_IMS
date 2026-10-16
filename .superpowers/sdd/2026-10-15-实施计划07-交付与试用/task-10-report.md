# Plan 07 Task 10 —— 交付收尾波 · 实现者报告

> 分支 `p07/delivery-final`（起点 `dd48b2a` = `main`，工作树开工时干净）。
> ⚠️ **没有 push、没有碰 `main`**。
> 五件按顺序做完：G8（S2）→ G11（页面文案收口）→ G9 + G7 + G12（三条脚本缺陷）→
> 重建 `dist` **一次** → 重打包 **一次** + Task 4 那六格逐格复核。
> ⚠️ 本报告**刻意不印自己的字节数与 sha256**（不动点问题；Task 8 在这一族连踩四次，
> 教训在 `task-8-report.md` §8.6）。

---

## 1. 环境 + 开工五格

### 1.1 环境（硬规矩 #73：开工第一件事）

```
node --version   → v24.19.0        （基线 v24.19.0 ✓）
python --version → Python 3.11.1   （基线 3.11.1 ✓，无 venv）
npm              → 11.17.0
git HEAD（开工） → dd48b2af85dbb88444d025279da7855b8a208c73
git status       → 空（工作树干净）
分支             → git checkout -b p07/delivery-final ✓
```

### 1.2 开工五格（⚠️ 逐个亲量，不是抄派单）

| 格 | 判据 | 开工时实测 | 收尾时实测 |
|---|---|---|---|
| ① 试用档服务 | uvicorn PID **45156**、StartTime `2026-10-16 0:36:05`、监听 `127.0.0.1:8030` | ✅ `python` / `2026-10-16 00:36:05` / 8030 在听 | ✅ **同一格逐字未变**（`python 2026-10-16 00:36:05`） |
| ② 公网隧道 | `cloudflared` PID **37196**、StartTime `10:14:35` | ✅ `cloudflared` / `2026-10-16 10:14:35` | ✅ **逐字未变** |
| ③ 试用库 | `backend/pe_trial.db` = **1 589 248 B** / sha256[:16] **`40D7B5F78A7C36CB`** | ✅ `1589248` / `40D7B5F78A7C36CB` | ✅ **逐字未变** |
| ④ 产物 | `frontend/dist` = **29 文件 / 687 804 B**，三个 sha：`index-C6De3tZH.css` 65 374/`B1F39AA52898F17A`、`index-jhn2Va5H.js` 176 169/`4A26DE4D7740DEFC`、`index.html` 2 729/`F7F3B41842D7F119` | ✅ 29 文件 / 687 804 B，**三个 sha 逐个对上** | ⚠️ **本波刻意重建了一次**（控制者已授权）⇒ 29 文件 / **686 680 B**，三个 sha 全换（§5.2） |
| ⑤ 甲方 URL | 匿名 health 200 / **54 B** / 墙钟约 5.8 s | ✅ 200 / 54 B / 6.0 s（⚠️ 打的是 `/api/health`；`/healthz` 会落 SPA fallback 回 2 729 B 的 index.html） | ✅ 200 / **54 B** / 5.8 s，而 `/login` 已在服务**新哈希**（§5.3） |

⚠️ `.trial\public-url.txt` 开工 **1 701 B / `0899037E4A220B01`** → 收尾 **1 701 B /
`0899037E4A220B01`**（**逐字未变**，见 §4.1 的 G9 行为取证与 §8 的收尾复核）。

### 1.3 开工前置：6 个孤儿 `msedge.exe`

派单给的 6 个 PID 逐个核过**父进程已 GONE**（`3420` / `40276` / `18720` 三个都 `GONE`），
命令行里的 marker 也对上（`pe-smoke-cdp-dE7BSB` × 2 / `p07t5-cdp-z2OJpb` × 2 /
`p07t5-cdp-5icbsR` × 2），然后**只杀这 6 个 PID**：

```
18776 GONE · 41836 GONE · 30024 GONE · 28516 GONE · 44904 GONE · 31404 GONE
复验：Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" |
      Where CommandLine -match 'pe-smoke-cdp-|p07t5-cdp-|p07t9'  → Count = 0 ✓
```

⚠️ 别的 `msedge.exe` 一个都没碰（当时本机另有 30 个 msedge 进程，全部留着）。
⚠️ 派单点名不许杀的 4 个进程全程活着：vite 5173（PID **43520**）与其父 `npm run dev`
（PID **38900**）、两个 `@deepseek-ai/dsh web`（PID **14368 / 16404**）—— 一个都没动。

### 1.4 我自己起的实例（⚠️ 一律 8040+，一律我自己在 TEMP 里灌的库）

| 端口 | 干什么 | 库 |
|---|---|---|
| 8040 | 产品档（`serve.ps1 -SkipBuild` + `PE_DB_URL`）；G8 复现、smoke dev/产品档的 API 侧 | `$TEMP\p07t10\pe_t10_{g8,mut,dev2,dev3,prod,dev4}.db`（每跑一次 smoke 换一份刚灌的） |
| 8042 | 我自己的 vite（`PE_API_TARGET=http://127.0.0.1:8040`）；⚠️ **不碰**别人的 5173 | — |
| 8043 | **原件** `trial.ps1` + `PE_DB_URL`（G7 的端到端取证、G12 的持锁取证） | `pe_t10_trial.db` |
| 8044 / 8045 | **解包目录**里那份 `trial.ps1`（六格 ②⑤；8044 走缺省、8045 走 `PE_DB_URL`） | `<解包目录>\backend\pe_trial.db` / `pe_env2.db` |

⚠️ **G7 修好之前一次都没用 `trial.ps1` 起自己的实例**（派单明令）：G8 的复现与前三次
smoke 一律走 `serve.ps1` + `PE_DB_URL`；G7 修好并**当场验过第二道闸**之后才用 `trial.ps1`。

---

## 2. G8 —— 401 横幅跨过登录留在下一个身份的页面上（**S2**）

### 2.1 复现取证（改前；真浏览器 + 真鼠标 + CDP）

harness：`$TEMP\p07t10\repro-g8.mjs`（自建，姿势逐字抄 `smoke.mjs` 第 14 步：
headless Edge + `--remote-debugging-port=0` + `Target.attachToTarget{flatten:true}` +
`Input.dispatchMouseEvent` 三发真鼠标 + `Input.insertText` 真键盘 +
`Network.requestWillBeSent/responseReceived` 逐请求状态码 + `Runtime.evaluate` 抓 DOM）。
打在**产品档**（8040 + 改前的 `dist`）上 ⇒ 与甲方看到的那一份逐字同一个产物。

**第一次跑没复现**（如实记）：我先在 `/t/dashboard` 上登出，那一档**一条 401 都没有**、
横幅也没挂上。查源码找到理由：`Dashboard.vue` 的 load 第一行有
`if (staffNo === null) return null` 那一格**早退**。换到 `/t/alerts`（说明书 §4 路线二
第 7 步逐字要甲方走的那一页）之后**一次就复现**，且形状与 Task 9 逐字对上。

改前的逐请求时序（`t` 相对 harness 起点，单位 ms）：

```
① T0001 从登录表单登进去 → /t/dashboard → Page.navigate /t/alerts → 预警队列渲染完
   identity = {"role":"teacher","teacherStaffNo":"T0001","teacherLabel":"陈国华","asOf":"2025-10-12"}
   横幅：不在（.banner = null）

② 真鼠标点「登出」（按钮矩形 x=1363 y=159.78 text="登出" hitInside=true）
   +4175 → +4212   POST 204  /api/auth/logout                ← 会话在这里被吊销
   +4212 → +4223   GET  401  /api/alerts?limit=200           ⚠️401
   +4213 → +4223   GET  401  /api/students?limit=200         ⚠️401
   +4213 → +4224   GET  200  /api/course-sections?limit=200     ← 7 个匿名读之一
   +4213 → +4224   GET  401  /api/teachers?limit=200         ⚠️401
   +4213 → +4224   GET  401  /api/enrollments?limit=200      ⚠️401
   ⇒ 401 合计 4 条（与 Task 9「三次登出三次都数到那 4 条」逐字相同）
   落到 /login（+6841ms）；横幅：**在** class="banner banner--error banner--loud"

③ 换身份登录 T0002（真键盘填表单、真鼠标点提交）
   落到 /t/dashboard（+10289ms），15 个请求全 200、0 条 401
   identity = {"role":"teacher","teacherStaffNo":"T0002","teacherLabel":"林慧敏",…}
   横幅：**仍在** ← ⚠️⚠️ 这就是 G8
```

横幅原文（逐字，改前，挂在 **T0002 的大屏**上）：

```
code    = unauthenticated
status  = 401
where   = GET /api/students?limit=200
advice  = 会话失效了（pe_session cookie 缺失、已过期或已登出）。前端会把你送去登录页，
          登录之后回到刚才那一页。
message = 缺少身份：需要一个有效的 pe_session cookie（请先 POST /api/auth/login）。
          ⚠️ 请求头 X-Teacher-Staff-No 被忽略：PE_ALLOW_HEADER_IDENTITY 不是 1
```

⚠️ 那句 advice 在那一刻是**假话**（用户已经以 T0002 登录了）—— Task 9 的判词逐字对上。

### 2.2 根因（⚠️ **实测**，不是猜；⚠️ 与 spec §15 G8 改前那一句推断**不同**）

spec §15 G8 改前逐字写着「成因（**可推断**，本波没有改代码去证）：点『登出』那一刻
教师端还有请求在飞（班级大屏每 5 秒自动轮播 + 预警页）」。⚠️ **那一句是错的**，逐格：

1. **谁把横幅置上**：那 5 个 GET 的**发出时刻是 +4212 / +4213**，而
   `POST /api/auth/logout → 204` 落在 **+4175 → +4212** ⇒ 它们**全部在吊销之后才发出**，
   ⚠️ 不是「登出那一刻还在飞的旧请求」。发它们的人是 `views/teacher/AlertQueue.vue:178`
   那一句 `watch([() => identity.teacherStaffNo, () => identity.asOf], () => void reload())`
   —— `stores/session.ts` 的 `logout()` → `forget()` → `useIdentityStore().clearIdentity()`
   把 `teacherStaffNo` 置成 `null`，那句话就触发了一次重读。
   ⚠️ **反证也量过**：同一次登出在 `/t/dashboard` 上是 **0 发**，因为 `Dashboard.vue:139`
   有 `if (staffNo === null) return null` 那一格早退；`AlertQueue.vue` / `ClassReport.vue` /
   `StudentDetail.vue` 与学生端那 6 页（`Home` / `WeeklySheet` / `CheckIn` / `RpeEntry` /
   `MiniTest` / `Notifications`）**都没有**它。
   ⚠️ 于是「4 条 401 / 5 发」这个形状**是可解释的**：`/api/course-sections` 是
   §13.4.4 那 7 个匿名读之一 ⇒ 200，其余 4 个要身份 ⇒ 401。
2. **谁本该清它**：`ApiErrorBanner.vue:51` 的 `const current = shallowRef<ApiError|null>(null)`
   是一个**模块级单例**，而 `dismiss()` 改前**只有一个**调用方 —— 模板里那个「关闭 ✕」按钮
   （`ApiErrorBanner.vue:251`）。⚠️ 全仓 `Grep useApiError|dismiss\(\)|raise\(` 实测：
   `raise()` 有 4 个调用方（`main.ts:95` 的 `errorHandler`、`composables/useAsync.ts:85`、
   `IdentitySwitcher.vue:197`、`CheckIn.vue:244`），而 `dismiss()` **只有那 1 个**。
   ⇒ 「身份变化」那一格上**一个清理点都没有**，这就是病灶。
3. **它为什么留在下一个身份的页面上**：`useAsync.reload()` 的 catch 在组件**卸载之后**
   仍然会跑（它没有卸载守卫），于是 `raise` 发生在 `router.replace('/login')` 之后；
   而单例既不随路由清、也不随身份清 ⇒ 一路挂到 T0002 的大屏上。
   ⚠️ `client.ts` 那一次 `fireSessionExpired` **没有**造成第二次跳转：`main.ts` 的订阅者
   第一行就 `if (redirecting || current.path === '/login' || …) return`（那一刻已经在 `/login`）。

### 2.3 修法（⚠️ **单一所有者** = 派单逐字要求的「身份变化那一格」）

`frontend/src/stores/session.ts`：`adopt()` 与 `forget()` 各调一次 `useApiError().dismiss()`。

- ⚠️ **为什么是这两处**：「后端认我是谁」在全前端**只有这两个写入口**（都在本文件），
  故它们就是「身份变化」那一格的唯一住址。⚠️ **不是每个页面各清一次**（派单明令）。
- ⚠️ **不是把横幅整个删掉、也不是改成静默**（Plan 06 终审要的那个「响亮」一格未动）：
  真正的会话过期仍然会挂出来 —— `api/client.ts` 是**先** `fireSessionExpired`
  （⇒ `main.ts` 的订阅者调 `forget()` ⇒ dismiss）**后** `throw`
  （⇒ `useAsync` 的 catch 才 `raise`）⇒ **dismiss 恒早于 raise**，顺序是承重的。
- ⚠️ 一个 store 从 `.vue` 里 import 的姿势**逐字抄既有的** `composables/useAsync.ts:21`
  （`useApiError` 住在 `ApiErrorBanner.vue` 的第一个 `<script lang="ts">` 块里）；
  依赖方向没有环：`session → ApiErrorBanner → api/client → stores/identity`，回不到本文件。
- ⚠️ 顺手把 `ApiErrorBanner.vue` 的 docblock 改对了：那个文件头逐字写着横幅状态
  「不持久化、**不跨页共享（换页要清）**、也没有派生状态」，而「换页要清」那一格
  **改前没有实现**（`dismiss()` 只有一个调用方）。本波补上的是**其中一格**
  （「**换身份**要清」），而「换页要清」仍然没做 ⇒ 已在 docblock 里如实写明并登记为 **G14**。
  ⚠️ 这是「账面说的与代码做的相反」那一族，本仓反复修的就是它。

### 2.4 同族自查（派单点名 4 格 + 我加的 1 格；⚠️ 一律实测）

| UI 状态 | 住址 | 跨身份残留吗（实测） | 判定 |
|---|---|---|---|
| 错误横幅 | `ApiErrorBanner.vue` 的模块级单例 | 改前**残留**（§2.1 ③）→ 改后**不残留**（`.banner` = null / `banner--loud` = 0 / 正文里 `unauthenticated` 0 命中） | ✅ **本波修掉** |
| **业务日 `as_of`** | `localStorage['pe.identity.v1']` 的 `asOf` 一格 | **残留**：手工改成 `2025-10-08` → 整页重载（仍是 T0002，页面上那个 `#identity-asof` 输入框显示 `2025-10-08`）→ 真鼠标登出（`/login` 上仍是 `2025-10-08`）→ 换身份登录学生 `2023120001`（`/s/home` 上**仍是** `2025-10-08`，`localStorage` 与输入框两格都是） | ⚠️ **那是设计、不是缺陷**：`stores/identity.ts` 的 `clearIdentity()` docstring 逐字写了「**不清 `asOf`** —— 业务日是演示口径的一部分，与『我是谁』无关」，`stores/session.ts` 的 `forget()` docstring 也逐字引了它。⚠️ 已**加一拍把它钉住**（§G8-⑦），于是下一个人顺手清了会红 |
| 页面数据 | 各页面自己的 `useAsync` ref | **不残留**：换身份登录学生之后，`/s/home` 的正文里上一个教师的工号 `T0001` 与姓名 `陈国华` **各 0 命中**（期望侧的姓名是现场从 `/api/teachers` 取的，不是写死的） | ✅ |
| 试用告示 | `App.vue` 的 `trial` / `trialStudents` | **与身份无关**：它是 `onMounted` 里读**一次** `/api/health` 的 `trial` 一格（**进程事实**、不随路由重打）⇒ 结构上不可能跨身份残留。⚠️ 运行面也核过：试用档（8044）smoke 断言 16/16 条路由都挂着告示、产品档与 dev 档 0/16 | ✅ |
| DEV-only 请求头切换器的 `students`/`teachers`/`studentTotal`/`teacherTotal`/`loadFailure` | `IdentitySwitcher.vue` 的组件级 ref（它常驻 `App.vue`、**不随路由卸载**） | **在 dev 构建里会留在内存中**（`loadRosters` 的第一行是 `if (!IS_DEV \|\| !session.isStaff) return`，故 `isStaff` 由真变假那一档**不清**它）；⚠️ 而登出后 `devRole` 落成 `'none'`、那两个 `<select>` **不渲染**（`v-if="devRole === 'student'/'teacher'"`），且再登录时 `watch(() => session.isStaff, loadRosters)` 会重拉 | ⚠️ **不进产物**（`import.meta.env.DEV` 那一半被 Rollup 整个摇掉，守卫是 `check:dist`）⇒ 甲方结构上看不到。已登记为 **G14** 的同族一行 |
| `session.notice` | `stores/session.ts` | **不残留**：`login()` 里 `this.notice = ''`；而 `forget()` **刻意保留**它（清掉会话之后紧接着要显示的那一句正是 notice）—— 实测换身份登录后 `.switcher__warn` 为空 | ✅ |

### 2.5 守卫：smoke 新拍 + 定点变异

`frontend/scripts/smoke.mjs` 第 14 步末尾（`cdp.close()` 之前）新增 **§G8** 一组，
**16 拍**（⚠️ 加在第 14 步**里面**，故四档的**步数仍是 18**、而断言数增）：

| 拍 | 钉什么 |
|---|---|
| §G8-① ×3 | 前提：教师从**登录表单**登进去（不是 CDP 种 cookie）、到了预警队列页、业务日那一格读得出来（反空转） |
| §G8-② ×3 | 前提/反空转：登出后落在 `/login`；**登出那一刻确实有请求回 401**；那一批里 `/api/course-sections` 是 **200** 而其余是 401（⇒「4/5」这个形状可解释、不是随机数） |
| §G8-③ ×1 | 反空转：那一刻横幅**真的被挂上了**、是 `banner--loud`、code 是 `unauthenticated` |
| §G8-④ ×2 | 前提：换身份（学生）登录成功、且学生首页**真的渲染出来了** |
| §G8-⑤⑥ ×4 | **判据**：`.banner` 为 0 / `banner--loud` 为 0 / 正文里没有 `unauthenticated` / 会话条说的是**新**身份 |
| §G8-⑦⑧ ×3 | 同族：`as_of` 跨身份**照旧保留**（把设计钉住）+ 反空转（期望侧真取到了上一个身份的姓名）+ 正文里没有上一个身份的任何痕迹 |
| 另有 8 拍 | `realClick` 自带的反空转（每个选择器都断言「在页面上、且那一点上就是它自己」） |

⚠️ §G8-②③ 那三拍的注释里**逐字写了**「若哪天它们红了、而红的原因是 G13 被修掉了
（登出不再发那一批读请求），**不要删这两拍**，改成手工把一条 `unauthenticated`
raise 进常驻位再走一遍换身份登录」—— 否则 §G8-⑤⑥ 会**假绿**。

**定点变异**（`$TEMP\p07t10\mutate-g8.py`：把 `adopt()` 里那一行 dismiss 换成一句注释）：

| | 结果 |
|---|---|
| 变异后跑 smoke dev 档 | **退出码 1**；`步数 17/18`、`断言 767 绿 / 3 红` |
| 红的三拍 | §G8-⑤「没有任何 `.banner`」（实测 `{"count":1,"loud":1,"cls":"banner banner--error banner--loud","code":"unauthenticated","status":"401","where":"GET /api/alerts?limit=200",…}`）· §G8-⑤「更没有 `banner--loud`」（`loud = 1`）· §G8-⑥「正文里没有 `unauthenticated`」 |
| 仍然绿的 | §G8-②③ 的**前提**三拍（401 = 4 条 / 横幅确实被挂上）⇒ **判据接得上、不是恒真** |
| 装回复核 | `session.ts` 回到 **27 525 B**、`MUTANT` 字样 0 命中、`useApiError().dismiss()` **2** 次（`adopt` + `forget`） |

### 2.6 改后取证（真浏览器，同一份 harness、同一条路线）

| 时刻 | 改前 | 改后 |
|---|---|---|
| ② 登出后落在 `/login` | 横幅**在**（`unauthenticated` / 401 / `GET /api/students?limit=200`） | 横幅**在**（同一块；⚠️ 这一格**没变** —— 见 §7 的 **G15**） |
| ③ 换身份登录后的大屏 | 横幅**在** ← **G8** | 横幅**不在**（`.banner` = null） ✅ |
| 401 条数 | 4 | **4**（⚠️ 一格没变：本波修的是「横幅跨身份残留」，不是「登出白发 5 个请求」；后者是 **G13**） |

⚠️ 改后取证跑了两遍：**dev 档**（vite 8042，harness 直跑）与**产品档/试用档**
（smoke §G8 那一组，8040 与 8044 各一遍）⇒ 两档都绿。

---

## 3. G11 —— 用户裁定的页面文案收口

### 3.1 裁定与范围

用户 2026-10-16 亲自裁定的口径逐字：「**只去掉波次编号与 file:line**」——
页面**保留**「为什么是这个数」的解释（本仓的可解释性资产），而把纯开发账本换成业务口径。

⚠️ 范围**只限渲染出来的正文**。`<script>` 的 docblock、代码注释、后端 docstring
**一个字都没动**（登记为 **G16**）。

### 3.2 重扫口径（⚠️ 自己写扫描器，不只信 Task 9 那份清单）

`$TEMP\p07t10\scan-g11.py`：一个**带 mini-lexer 的注释剥离器**（认得字符串与模板串里的
假注释；`.vue` 分别取最外层 `<template>` 与 `<script>` 两块），**两个面分开数**：

- **A 面** = `.vue` 的 `<template>` 里、**HTML 注释之外**的文本（甲方直接看得见）；
- **B 面** = `.ts` / `<script>` 里、**JS 注释之外**的字符串字面量（⚠️ 再人工判「会不会被渲染」）。

判据 13 条：`Plan \d+` / `Task \d+[a-z]?` / `\w+\.py:\d+` / `\w+\.(vue|ts|mjs):\d+` /
`read_scope` / `OrphanOwner` / `StudentOwner` / `crud\.py` / `deps\.py` / 终审 / 硬规矩 /
待清扫 / 波次名（品牌波 / 密度波 / 安全收紧波 / 收尾波）。

| | 改前 | 改后 |
|---|---|---|
| 合计 | **59 处 / 12 个文件** | **19 处 / 1 个文件** |
| **A 面** | **37** | **0** ✅ |
| B 面 | 22 | 19（⚠️ **全是** `router/index.ts` 的 `meta.task`） |

⇒ 本次实改 **40 处 / 12 个文件** = A 面 37 + B 面里**真的会渲染**的 3：
`StudentDetail.vue:163/168` 那两个 `instead:` 串（经 `{{ ep.instead }}` 渲染，`:1353`）、
`router/index.ts:315` 的 `MISMATCH_NOTICE.admin`（经 `session.setNotice()` 渲染进
`.switcher__warn`）。
⚠️ B 面剩下的 19 处 `meta.task` **一个都没动**：全仓 **0 个消费者**
（`Grep 'meta\.task'` 无命中；`App.vue` 只读 `meta.surface` 与 `meta.wide`、
`afterEach` 只读 `meta.title`）⇒ **不渲染**、不在范围 ⇒ 登记为 **G16 ①**。

### 3.3 完整清单（40 处：文件 / 行 / 判据 / 改后）

⚠️ 行号是**改前**的。`原文` 一栏只摘命中判据的那一段（逐字），`改后` 一栏给要点。

| # | 文件 | 行 | 判据 | 原文（逐字摘） | 改后 |
|---|---|---|---|---|---|
| 1 | `src/App.vue` | 225 | Plan 编号 | `<strong>已做真实鉴权</strong>（Plan 05A）：首次绑定口令 → 登录 →` | 删掉 `（Plan 05A）`（页脚在 **16 条路由**上都在场，是这一族覆盖面最大的一处） |
| 2 | `views/admin/ResourceDetail.vue` | 334 | Plan+Task | `PATCH 挂了 require_admin（Plan 05A Task 2），` | `PATCH **只认管理员会话**（读写两侧的完整五档口径见 spec §13.4.4），` |
| 3 | `views/admin/ResourceIndex.vue` | 168 | Plan+Task | `…不受这一格影响；而 require_teacher 这个名字自 Plan 05A Task 2 起**已经不存在**（它当时判的是「任何在册教师可写」，改名成了 require_staff）。` | `…不受这一格影响（读写两侧的完整五档口径见 spec §13.4.4）。` ⚠️ 那一段是**纯改名史**、没有业务口径可换，故整句删（不是删整段） |
| 4 | `views/admin/ResourceList.vue` | 364 | Task 编号 | `RESOURCES 里大概也没有（Task 5 的联调脚本会从 /openapi.json 反查两边）。` | `…（前端目录与后端清单由联调守卫按 /openapi.json 逐行反查对账）。` |
| 5 | 同上 | 430 | Plan+Task | `require_admin（Plan 05A Task 2；匿名写 → 401…` | `require_admin（口径见 spec §13.4.4；匿名写 → 401…` |
| 6 | 同上 | 447 | py 行号 + crud.py | `（crud.py:582-585）。` | `（那一条口径与全部运行须知见 spec §13）。` |
| 7 | `views/auth/Bind.vue` | 337 | Plan+Task | `⚠️ 验身材料…**弱材料**：Plan 05A Task 5 之前它们匿名可读，之后要教职身份才可读。` | `…**弱材料**：读那两份名册**要教职身份**（它们正是绑定口令的验身材料，故收得最紧）。逐字局限见 spec §1.2 与 §13。` |
| 8 | `views/student/Home.vue` | 354 | py 行号 | `都**不计入**完成率（feedback.py:810-817）。` | `都**不计入**完成率（判据与逐字口径见 spec §8.1）。` |
| 9 | `views/student/Notifications.vue` | 167 | Plan+Task | `⚠️ 这个端点是 **Plan 04 Task 3 的后端小修波**加的。此前本页只能「GET /api/notifications 翻页收集 + 客户端过滤」…` | `⚠️ 本页**刻意不走**「…翻页收集 + 客户端过滤」那一条…后端因此另给了这一条**已经按收件人过滤好**的窄端点。` |
| 10 | 同上 | 173–187 | 波次名 + 开发账本 | ⚠️ Task 9 点名的**那整段**：`⚠️⚠️ 改前这一段还接着写了三句，**三句今天都是假话**（2026-10-15 逐格重测…）「那个匿名 list 今天仍然存在…」…「本仓的读侧口径是『读 ⇒ 一律匿名』」—— 安全收紧波之后…「48 个匿名 GET 里已经包括…」…那两个数的机器口径有两个住址：scripts/smoke.mjs 第 12 步与后端 tests/api/test_prescription_api.py…` | 换成**今天的真话**：`⚠️⚠️ **读侧一律要会话**（2026-10-15 逐格重测…）：匿名打 GET /api/notifications 是 **401**；只有**少数几个**资源匿名可读，而 GET /api/students **不在**其中…「哪几个资源匿名可读 / 哪几个操作挂了 security」这两个数**本页刻意不复述**：机器口径住在联调守卫与后端那条同名断言里…完整的读写五档口径见 spec §13.4.4。` |
| 11 | `views/student/RpeEntry.vue` | 335 | py 行号 | `而我还**没有**交过的那几节课（dashboard.py:450-487）。` | `…（判据与逐字口径见 spec §8.1）。` |
| 12 | `views/teacher/AlertQueue.vue` | 463 | read_scope | `后端 GET /api/alerts 的 read_scope="staff_taught" 已经在 SQL 层按 enrollment ⋈ course_section.teacher_id 收窄，` | `后端 GET /api/alerts **已经在 SQL 层**按「选课名册 ⋈ 这个班的任课教师」收窄（判据在 spec §13.4.7），` ← ⚠️ 派单给的那个例子，逐字照做 |
| 13 | 同上 | 546 | Plan+Task | `⚠️ **本处此前逐字写的是另一个理由，而它自 Plan 06 Task 8b 起是假的**：原文说「就算触发了教师也读不到…」` | `⚠️ 而**「就算触发了教师也读不到」不是理由**：后端给「一行没有学生所有者的预警」…补了**第二根轴**…` |
| 14 | 同上 | 549 | Task 编号 | `那是 Task 8 登记在案的一格 **Critical**（失效方向静默：200、只是少一行），本波已修：` | 并入上一条，只留业务事实（第二根轴 + 谁读得到谁读不到） |
| 15 | 同上 | 554 | crud.py | `逐字取证住在 backend/app/api/crud.py 的` | `第二根轴的判据与它那一条失效方向的逐字取证见 spec §13.4.8。` |
| 16 | 同上 | 555 | OrphanOwner | `OrphanOwner 与 _orphan_condition。` | 同上（并入 §13.4.8 那一个指针） |
| 17 | 同上 | 580 | Plan+Task | `或（自 Plan 06 Task 8 起多出来的第三种）` | `或（第三种，它来自「按任教范围收窄」那一条口径）` |
| 18 | 同上 | 609 | Plan+Task | `GET /api/alerts 自 Plan 06 Task 8b 起对「一行没有学生所有者的预警」按…判` | `GET /api/alerts 对「一行没有学生所有者的预警」按…判（spec §13.4.8）` |
| 19 | 同上 | 780 | py 行号 | `⚠️ 刻意不加总：prescription_stage.py:411-417 逐字禁止跨单位求和（「48 分钟 + 120 次 = 168 什么？」），且有守卫按键集断言。` | `⚠️ 刻意不加总：后端**逐字禁止**跨单位求和（同一句人话留着），且有守卫按键集断言（处方那一层的口径见 spec §7）。` |
| 20 | `views/teacher/ClassReport.vue` | 494 | Plan 编号 | `⚠️ 改前这一格逐字是「没有带上 X-Teacher-Staff-No」—— Plan 05A 之后身份走 pe_session cookie，而那个请求头…一个字节都不看。` | `⚠️ 身份**只**走 pe_session cookie，任何身份请求头在交付的三档上**一个字节都不看**（spec §13.4）。` |
| 21 | `views/teacher/StudentDetail.vue` | 163 | Plan+波次（**B 面，会渲染**） | `instead: 'GET /api/teacher/students/{id}/home（Plan 04 收尾波新加，响应体逐字相同）'` | `…（教师侧变体，响应体与学生侧逐字相同）` |
| 22 | 同上 | 168 | Plan+Task（**B 面，会渲染**） | `instead: '…/weekly-sheet（Plan 03 Task 8 加的）'` | `…/weekly-sheet（教师侧变体）` |
| 23 | 同上 | 582 | Task 编号 | `路由是 /t/students/:studentId（Task 1 定的，带一个必填的路径参数），` | `…（带一个必填的路径参数），` |
| 24 | 同上 | 734 | Plan+Task | `⚠️ **这一格在 Plan 04 Task 3 是拿不到的**（那时 /home 只有学生侧端点、教师头调它 401），本页当时显示的是同一份快照里的 reason 并点名说明了信息量少一层。` | `⚠️ 这一格读的是**教师侧变体**：/home 的学生侧端点只认学生本人的会话（教师会话调它是 403），故后端另给了一条教师侧的路径。本块显示的是**后端算好的原文**，前端不自己重建（两个变体同址同姿势，口径见 spec §13.4.10）。` |
| 25 | 同上 | 736 | 波次名 | `收尾波加了教师侧变体之后那段说明**已撤掉**，这里是后端算好的原文。` | 并入 #24 |
| 26 | 同上 | 1058 | Plan+Task | `⚠️⚠️ **本块那三格自 Plan 06 Task 10 起又齐了**（Task 9 一度只剩两格，如实交代它的来龙去脉）：后端当时把 squat_score 与…` | `⚠️⚠️ **本块那三格今天同源、齐了**（来龙去脉如实交代）：后端一度把 squat_score 与…` |
| 27 | 同上 | 1080 | Task 编号 | `（Task 9 的降级处置是读原始行的 mini_test.squat_30s_count）：` | `（不再是读原始行 mini_test.squat_30s_count 那一档降级处置）：` |
| 28 | 同上 | 1086 | Plan+Task | `否则它会把 Plan 06 Task 8 在班级端点上关掉的**跨教师读口**重新开一个。` | `否则它会把班级端点上**已经关掉**的那个跨教师读口重新开一个。` |
| 29 | 同上 | 1161 | Plan+Task | `⚠️ **这一格在 Plan 04 Task 3 是拿不到的**（那时本页只显示行、并点名说「不给勋章数这个计数」）。` | `⚠️ 这一格读的也是**教师侧变体**：学生侧端点只认学生本人的会话，故教师端有自己的一条路径（口径见 spec §13.4.10）。` |
| 30 | 同上 | 1162 | 波次名 | `收尾波加了教师侧变体之后那段说明**已撤掉**。` | 并入 #29 |
| 31 | 同上 | 1259 | Plan+Task | `⚠️ **这一整块在 Plan 04 Task 3 是不存在的**：那时 /home 只有学生侧端点…` | `⚠️ **这一整块走的是教师侧变体**：/home 的学生侧端点只认学生本人的会话…` |
| 32 | 同上 | 1261 | Plan 编号 | `（Plan 04 的请求头时代量到的是 **401**，` | 删（那段「401→403 的时代差」是纯开发账本） |
| 33 | 同上 | 1262 | Plan 编号 | `Plan 05A 换了身份载体之后那一档变成了 403，逐字取证见下面第 06 块）` | `（逐字取证见下面第 06 块）` |
| 34 | 同上 | 1265 | 波次名 | `收尾波加了教师侧变体（响应体与学生侧**逐字相同**：后端把函数体抽成了 dashboard._student_home_response 两处共用），三样都能显示了，那三处降级说明**已撤掉**。` | `教师侧变体的响应体与学生侧**逐字相同**（后端两处共用同一个响应装配，故「同形」是结构上成立的、不是一句约定），三样都能显示（口径见 spec §13.4.10）。` |
| 35 | 同上 | 1290 | Plan+Task | `2026-10-15 重测过（Plan 04 Task 3 那份「401」的实测原文是请求头时代量的，已过期）` | `2026-10-15 在产品档上逐条实发重测过（更早那一份「401」的实测原文是身份还走请求头那个时代量的，已过期）` |
| 36 | 同上 | 1298 | Plan 编号 | `下面五个端点都 Depends(current_student)，而 Plan 05A 之后「我是谁」的**唯一**载体是…` | `下面五个端点都 Depends(current_student)，而「我是谁」的**唯一**载体是…` ⚠️ 见 §3.5：这一处**回收过一次** |
| 37 | 同上 | 1344 | deps.py | `而 prod 档下 app/api/deps.py 的 allow_header_identity() **结构上恒 False**` | `而 prod 档下后端那个 allow_header_identity() 开关 **结构上恒 False**` ⚠️ 见 §3.5 |
| 38 | 同上 | 1363 | Plan+Task | `weekly-sheet 那一条是 Plan 03 Task 8 加的，` | `weekly-sheet 与 home 各有一条` |
| 39 | 同上 | 1364 | Plan+波次 | `home 那一条是 Plan 04 收尾波加的（第 05 块就是它）。` | `（第 05 块用的就是 home 那一条）。` |
| 40 | `src/router/index.ts` | 315 | Plan 编号（**B 面，会渲染**） | `'管理台（23 个资源的增删改查）自 Plan 05A 起**仅 role=admin 可用**，'` | `'管理台（23 个资源的增删改查）**仅 role=admin 可用**，'` |

### 3.4 与 Task 9 那一份的差（派单点名要报）

Task 9 的 **F-16**（`task-9-report.md` L367，逐字）点名了 **4 个页面上的 5 种形状**：
预警队列页的 `read_scope="staff_taught"` 段 + `Plan 06 Task 8b` / `Task 8` / `crud.py` 的
`OrphanOwner` + `_orphan_condition` 段、课堂快评页的 `dashboard.py:450-487`、
首页的 `feedback.py:810-817`、消息中心那整段开发账本。
（派单把它概括为「15 处 / 10 个文件」；⚠️ 我在 `task-9-report.md` 与 spec §15 G11 两处
都 `Grep` 过 `15 处` / `10 个文件`，**0 命中** ⇒ 那两个数不在 Task 9 的产物里，
本波按**自己重扫出来的 40 处 / 12 个文件**报，并逐条对上它点名的形状。）

| | Task 9 | 本波 |
|---|---|---|
| 数量 | 4 个页面上的 5 种形状（派单概括为 15 处 / 10 个文件） | **40 处 / 12 个文件**（A 面 37 + 会渲染的 B 面 3） |
| 取证面 | 浏览器里的 `document.body.innerText` | **渲染正文的源**（模板文本节点 + 会渲染的字符串常量） |

⚠️ **差的理由是取证面不同、不是谁漏了**：`innerText` 是**布局感知**的，折叠着的
`<details>`（本仓那一批「ⓘ 口径 / 可解释性展开」区块正是它）里的文本
`display:none` ⇒ **不进 `innerText`**。本波量的是源，故把折叠区块里的也算进来了
（例如 `StudentDetail.vue` 那 17 处里有 13 处在折叠区块内）。
⚠️ **Task 9 点名的那 5 种形状逐个都在本波这 40 处里**（#10 = 消息中心那整段、
#11 = `dashboard.py:450-487`、#8 = `feedback.py:810-817`、#12 = `read_scope="staff_taught"`、
#13–#16 = `Plan 06 Task 8b` / `Task 8` / `crud.py` / `OrphanOwner` + `_orphan_condition`）。

### 3.5 needle 被迫改了几条：**0 条**（⚠️ 首跑红过 1 拍，处置是**收回我的多改**）

首跑 smoke dev 档红了 **1** 拍：第 14 步 **§TD-7**「请求头通道那一段没有被删掉…
点名了那个环境变量、**点名了那个函数**、并说清在甲方手上不可能生效」，
实测 `allow_header_identity=false` —— 因为我把它改成了「认不认身份请求头」的开关。

⚠️ 处置**不是**改 needle（硬规矩 #92：needle 跟着文案改可以、判据不许放宽；而这一格
连 needle 都不该动）：那一处我**多改了**一个函数名，而它既不是波次编号也不是 `file:line`
⇒ **按用户的窄口径收回来**，只去掉 `app/api/deps.py` 那一个 file 引用，
函数名 `allow_header_identity()` 留着。同族的那一处（#36 `Depends(current_student)`）
也一并收回。⇒ **§TD-7 自己就绿了，0 条 needle 被迫改**。

### 3.6 守卫复跑

| 守卫 | 结果 |
|---|---|
| `npm run check:tokens` | **36 个文件（下界 25）/ offender 0 / 退出码 0** ✅ 一格未退 |
| `npm run check:dist` | 退出码 0；**25 产物 / 574.8 kB**（基线 25 / 575.9 kB）；全部自校拍绿 |
| `npx vue-tsc -b` | 退出码 **0** |
| smoke 四档 needle | dev **770 绿 / 0 红** · 产品档 **770 绿 / 0 红** · 试用档 **802 绿 / 0 红**（§6） |
| DOM 的重叠 / 溢出 / 整页滚动条 | 三档的第 14 步**逐条路由**都绿（`overlapCount` / `overflowCount` 全 0）⇒ 文案变短没有把布局改坏 |
| 说明书 / README 引用核 | `Grep 'read_scope\|OrphanOwner\|Plan 0\|Task \d\|\.py:\d\|收尾波\|require_teacher\|安全收紧波'` 在**说明书**上 **0 命中** ⇒ Task 9 刚修的那 12 处**一个都没被改回去**；README 有 **1 处**波次编号（L94），⚠️ 它是**文档**不是页面正文 ⇒ 登记为 **G16 ③** |

---

## 4. G9 + G7 + G12 —— 三条脚本缺陷

### 4.1 G9 · `tunnel.ps1` 会删掉并改写另一条仍活着的隧道那一份 URL 文件

**改前取证**（Task 9 的实测，本波逐格复核过判据）：那一份从 **1 701 B /
`0899037E4A220B01`** 被改写成 **2 406 B / `B01E1E1911A550F0`**；脚本给的理由
「那条链接随上一轮的隧道进程一起死了」在那一档是**假的**。
⚠️ 判据缺陷：`tunnel.ps1` 改前 L316 逐字是 `if (Test-Path $UrlFile) { Remove-Item … }`
—— **按「文件在不在」判**，而同一个文件里第 ① 步对孤儿**进程**的判据是按 marker
`pe_tunnel_<Port>` 收窄的（写得很对）⇒ **两格判据的收窄程度不一样**。

**修法**（⚠️ 单一所有者）：一个新函数 `Get-UrlFileOwner`，把那两格判据**统一收窄到
「标记 + 端口」**：读那一份文件**自己记着**的两个数（⑤ 那一次写入的 `本地端口` 与
`隧道 PID` 两行），再拿标记去问本机有没有活着的隧道进程。
⚠️ 标记的拼法**不敲第二遍**：从 `$LogDirName`（`"pe_tunnel_$Port"`，既有守卫按字面钉着它）
派生 —— `"pe_tunnel_"` 里没有数字，故一次 `Replace` 只可能命中末尾那一个。
⚠️ 五档返回值一律**折向「不动它」**（证明不了它是我的，就不删）：

| State | 判据 | 处置 |
|---|---|---|
| `absent` | 文件不在 | 无 |
| `mine` | 它记的端口 == 本进程端口，**且**本进程那个标记上没有活着的隧道 | **删掉并改写**（⚠️ 一条隧道的常规用法恒落这一档 ⇒ **缺省行为一格不变**） |
| `other-alive` | 它记的是另一个端口，而那一条**还活着** | **不删不改** + 一句人话 + 自己的链接另写带端口后缀的一份 |
| `other-dead` | 它记的是另一个端口，那一条已经死了 | **仍然不删不改**（派单逐字要求「不属于我的就不要删、不要改」），而「它死了」由那一句人话**响亮地**说 |
| `unknown` | 文件在、而 `本地端口` 那一行读不出来 | **不删不改** |

⚠️ **选「另写一个带端口后缀的文件」而不是「只打在终端上」**（派单给的两种形状，选一种并说明）：
链接要能被**别人**读到、能被**脚本**读到，而不只闪在一个终端上（终端一滚就没了）——
那正是 ⑤ 那一步当初写文件的理由（它自己的注释逐字写着）。
⚠️ 实现上是把 `$UrlFile` **重新赋值**（`Join-Path $TrialDir ("public-url-" + $Port + ".txt")`），
于是下游三处（⑤ 写 / ⑦ watchdog 追加 / finally 删除）**一个都没改**，
而它们的既有守卫按字面钉着 `$UrlFile` 这个名字 ⇒ **一次改判据、三处都跟着走**。
⚠️ 那一个拼接**不含** `public-url.txt` 这个子串，故既有守卫
`statements.count("public-url.txt") == 1`（路径只有一个所有者）**仍然成立**。

**行为取证**（⚠️ 只读、不开隧道、不出网：把那个函数**原样切出来**在干净 PowerShell 里
真跑，姿势逐字抄 `test_tunnel.py` 的 `_backend_resolver` + `_run_ps1`）：

```
被测的那一份文件 = <repo>\.trial\public-url.txt（1701 B，sha256[:16]=0899037E4A220B01）
它自己记着的两行：本地端口 = 8030（…） / 隧道 PID = 37196     ← ⚠️ 甲方那一条，真的活着

-- 以 -Port 8041 开一条新隧道时（= Task 9 出事的那一档）
   State=other-alive  RecPort=8030  RecPid=37196  RecMarker=pe_tunnel_8030
   ⇒ 本进程**不动它**，自己的链接另写 .trial\public-url-8041.txt     ← ✅ G9 修掉了
-- 以 -Port 8030 开
   State=other-alive（⚠️ 因为标记 pe_tunnel_8030 上**还有活着的进程**；
   真跑时第 ① 步会先杀掉那个孤儿，届时 LiveMine=0 ⇒ 落 `mine`。
   ⚠️ 杀不掉时答 other-alive 是**保守**的那一侧，正是本函数要的失效方向）
-- 合成文件三档：absent → absent ✓ / 没有「本地端口」那一行 → unknown ✓ /
   记着端口 9999 而它不在 → other-dead（RecMarker=pe_tunnel_9999）✓
-- 收尾复验：甲方那一份仍是 1701 B / sha256[:16]=0899037E4A220B01 ✓ 逐字未变
```

**守卫**：`backend/tests/test_tunnel.py` 新增
`test_the_url_file_is_only_touched_when_this_process_owns_it`（**6 拍**：
① 判据恰好一个函数 ② 按「标记 + 端口」判（读文件自己记着的两个数、标记从 `$LogDirName`
派生、五档一个不少）③ 删除被那个判据闸住 + **红档半边**「文件在就删」那一格不在了
④ 另写带端口后缀的一份 + `public-url.txt` 在语句里仍恰好一次 ⑤ 下游三处一个都没改
（改指派排在三处**之前**）⑥ 打印一句人话（反静默））。
**定点变异**：把 `if ($UrlFileOwner.State -eq 'mine') {` 改回 `if (Test-Path $UrlFile) {`
→ 那一条**当场红**（退出码 1）；装回后 `tunnel.ps1` 的 sha256[:16] **`D4D095FF8C318422`
逐字相同**。

### 4.2 G7 · `trial.ps1` 尊重 `PE_DB_URL` + `-Reset` 的第二道闸

**改前取证**：`trial.ps1:141-146` 逐字是 `$TrialDbPath = Join-Path $Backend $TrialDbName`
（**写死**），参数面只有 `-Port` / `-Lan` / `-Reset` / `-Build`（**一个换库的旋钮都没有**），
而第 ⑤ 步还**自己设** `$env:PE_DB_URL`（于是外面设的那一个被它冲掉）⇒
**任何人在这台机器上跑 `trial.ps1 -Reset` 都会删掉甲方正在用的那一份库**。
⚠️ Task 8 与 Task 9 都被迫绕开它（用 `serve.ps1` + `PE_DB_URL` **复刻**同一档）。

**修法与选择**（⚠️ 派单要求选一种并说明；spec §15 G7 原提的是加一个 `-DbPath`，
**本波顶回了它**，见 §7.4）：选 **`PE_DB_URL`**，三条理由：

1. `PE_DB_URL` 已经是本仓「用哪个库」的**唯一口径**（`serve.ps1` 的 ③ a 就读它，
   而它自己那条 `pe.db` 禁区守卫也建在它上面）⇒ 加 `-DbPath` 会造出**第二个所有者**；
2. **交付面一个旋钮都不多**：本脚本随包交给甲方 IT，参数面每多一个就要跟着改
   说明书 §2 ③ 与 README；而环境变量那一侧它们**一个字都不用改**
   （那两份文档今天印的都是不带任何换库参数的缺省命令）；
3. 剥路径**不做字符串替换**、一律走 `sqlalchemy` 的 `make_url`，与本文件既有那条注释、
   `demo.ps1` 的 `-DryRun` 那一支逐字同一条口径。

⚠️ 只接 **sqlite**，别的方言 `throw`（灌库走 `demo_bootstrap.py`，而试用档的全部取证
都在 SQLite 上做的）。⚠️ 那一句 `python -c` 的**引号口径是承重的**（本波实测踩到，
就是派单点过名的那个坑）：脚本本体里**一个双引号都不能有** —— PS 5.1 把含空格的实参
用一对双引号包起来交给 `CreateProcess` 而**不转义**里面的双引号，实测
`u.database or ""` 当场 `SyntaxError: unterminated string literal`；
「有没有库文件名」那一格改由 python 侧打成 `True/False`（**不**靠 `None` 的字面量）。
姿势与本文件既有那一句「数学生人数」的 `python -c` 逐字相同。

**第二道闸**（⚠️ 派单问「若你认为该反过来，顶回来」→ **不反过来，同意派单**）：
`if ($TrialDbFromEnv -and -not $Force) { …人话… ; exit 1 }`，
排在**任何删除动作之前**（顺序是承重的，与「占用检测排在 `Get-FileHash` 之前」同一条口径）。
⚠️ **闸只在「目标库不是缺省那一份」时开口** ⇒ **缺省行为一格都不变**；
反过来（缺省也要 `-Force`）会把甲方 IT 手上那一条已经写进说明书与 README 的命令改坏。

**缺省行为不变的取证**（⚠️ 不是读字符串：把「解析试用库路径」那一段**切出来真跑**，
`$Backend` 指到 `C:\pe-trial-probe-does-not-exist\backend`；`Join-Path` 不查存在性 ⇒
一个字节都不碰磁盘。⚠️ 盘符必须**存在**：本机实测 `Q:\…` 会得到一个**非终止**错误
「Cannot find drive 'Q'」⇒ 路径为空而退出码仍是 0 = **静默**，故探针里把
`$ErrorActionPreference` 设成 `Stop`）：

| 档 | 实测 |
|---|---|
| `PE_DB_URL` **未设** | `PATH=C:\pe-trial-probe-does-not-exist\backend\pe_trial.db` / `FROMENV=False` / `URL=sqlite:///C:/pe-trial-probe-does-not-exist/backend/pe_trial.db` ✅ **与改前逐字同形** |
| `PE_DB_URL` **已设** | 三格都换成那一份，`FROMENV=True`（第二道闸的判据就是它） |
| 一个 `postgresql+psycopg2://` 的 URL | **退出非 0** + 一句「只接 sqlite」（不静默地拿它当路径用） |

**端到端取证**（⚠️ **原件**，不是复刻 ⇒ **spec §15 G7 那格「复刻不是原件」的盲区关掉了**）：

```
$env:PE_DB_URL = sqlite:///$TEMP/p07t10/pe_t10_trial.db
scripts\trial.ps1 -Port 8043
  → 试用库 = …\pe_t10_trial.db（不是 backend\pe_trial.db）
  → ①–⑤ 步全过、委托 serve.ps1、/api/health → 200
    {"status":"ok","tables":28,"students":60,"trial":true}
  → ⚠️ 甲方那份 backend\pe_trial.db 一个字节都没动（收尾 1 589 248 B / 40D7B5F78A7C36CB）

$env:PE_DB_URL 同上 + scripts\trial.ps1 -Reset -Port 8043      ← **不给 -Force**
  → ⚠️ -Reset **拒绝了**：要删的库**不是**本脚本缺省的那一份。
       缺省那一份   = …\backend\pe_trial.db
       你这一次指向 = …\pe_t10_trial.db
       来源         = 环境变量 PE_DB_URL（本脚本自 Plan 07 Task 10 起尊重它）
       ⚠️ 那一份可能是**别人正在用的库**（例如甲方手上那一份试用库），
          而一份被删掉的库是**找不回来**的。
       确认要删就再加一个 -Force：…trial.ps1 -Reset -Force
  → 退出码 **1**；库仍在 = **1 589 248 B**、sha256[:16] **`428385E76A2C9C63`**（改前同一个值）✅
```

**守卫**：`test_trial.py` 新增
`test_trial_ps1_respects_pe_db_url_and_gates_a_non_default_reset`（**4 拍**，其中 ①②③
是**把那一段切出来真跑**、④ 是源码面钉闸的顺序）。
**定点变异 ×2**：① 把 `if (-not [string]::IsNullOrEmpty($env:PE_DB_URL))` 改成 `if ($false)`
（= 回到路径写死）→ **红**；② 把 `if ($TrialDbFromEnv -and -not $Force)` 改成 `if ($false)`
（= 摘掉第二道闸）→ **红**。两次装回后 `trial.ps1` 的 sha256[:16] 逐字相同。

### 4.3 G12 · `-Reset` 那句「正被别的进程持有」的 suspects 收窄

**改前取证**（Task 9 实测）：退出码 1、库没被删（✓），而它列的 **4** 个 suspects 是
「PID 48144（127.0.0.1:8043）、PID 13560（0.0.0.0:8042）、PID 12940（127.0.0.1:8041）、
**PID 45156（127.0.0.1:8030）**」，其中只有第一个可能持有那一份库；
⚠️ 最坏的一档是有人照着去 `Stop-Process` 那个 **8030 = 甲方正在用的服务**。
判据（改前 `trial.ps1:225-228` 逐字）是「本机全部 **python 进程 ∩ 正在监听的 PID**」。

**⚠️ Windows 上拿不到「谁持有这个文件」的可靠判据**（派单点名要选并说明，本波**如实交代**）：
那一格的正解是 **Restart Manager**（`RmStartSession` / `RmRegisterResources` / `RmGetList`），
而在 PowerShell 里要用它就得 `Add-Type` 一段 C# 的 P/Invoke ——
本脚本是**随包交给甲方 IT 跑的**，而他们那台机器上的 PowerShell 很可能处在
**ConstrainedLanguage** 档（组策略 / WDAC 常见），那一档下 `Add-Type` **直接被挡**
⇒ 一个「在本机绿、在甲方机器上抛一段 PowerShell 原文报错」的判据**比没有判据更坏**。
而 `Get-Process | Where-Object { $_.Modules }` 也做不到（那一个列的是**已加载的 DLL**、
不含数据文件）；`openfiles.exe` 要全局开 `maintain-objects-list` + 管理员。
⇒ **选派单给的「退一步」那一档**：只报「被某个进程持有」+ **对应端口**（本次 `-Port`）上
的那一个候选，⚠️ 并**说清它不一定是持有者**，同时把**可靠**的那一条自查路径
（`resmon.exe` → CPU →「关联的句柄」）交给人。
⚠️ 代价如实记：Task 9 那一档（`-Port 8031` 而持有者在 8030）下本段会说
「端口 8031 上没有 listener」—— 一句真话、而不指向持有者；⚠️ 而它**同时**把 `resmon`
那一条可靠出路印出来了，故不再是「一句真话而一点用都没有」（改前那一格正是这样）。

**行为取证**（真跑；库被我自己那个 8043 上的 uvicorn **真的**持有）：

| 档 | 退出码 | 库 | 打印的 suspects |
|---|---|---|---|
| C1 `-Reset -Force -Port 8043`（持有者就在本次 `-Port` 上） | **1** | 没被删（1 589 248 B 未变） | 「端口 8043（本脚本这一次要起服务的那个端口）上的 listener 是 **PID 8856** —— ⚠️ 它**不一定**是持有这个文件的那一个…」= **只列那一个** |
| C2 `-Reset -Force -Port 8099`（持有者在别的端口） | **1** | 没被删（同上） | 「端口 8099 上没有 listener ⇒ 持有它的**不是**本脚本要起的那一个服务；⚠️ 本脚本在 Windows 上判不出「谁持有这个文件」…故**不列一份会让人去杀错进程的清单**」 |
| 两档共同 | — | — | 都印 `resmon.exe → CPU 选项卡 →「关联的句柄」`；⚠️ 两档输出里**都没有 `45156`**（甲方那个 8030），也**都没有**旧文案「N 个 python 进程正在监听端口」 |

**守卫**：`test_trial.py` 既有那条改 **4 拍**（⚠️ 方向是**收紧**、不是放宽）：
`Get-Process -Name python` **必须不在**语句里（放宽回去就红）·
`Get-NetTCPConnection -State Listen -LocalPort $Port` 必须在 ·
那句「不列一份会让人去杀错进程的清单」必须在 · `resmon.exe` 那条出路必须在。
**定点变异**：把判据换回「本机全部 python 进程 ∩ 正在监听的 PID」→ **当场红**；
装回后 sha256[:16] 逐字相同。

### 4.4 三个脚本的语法与形状复核

| | 结果 |
|---|---|
| PowerShell AST 解析（`Parser::ParseFile`） | `trial.ps1` **SYNTAX OK**（tokens 1602）· `tunnel.ps1` **SYNTAX OK**（tokens 5435） |
| `#>` 个数（守卫按 `body.count("#>") == 1` 切代码段） | 两个文件都 **恰好 1** ✅（⚠️ 新加的代码一律用 `#` 行注释，一个块注释都没写） |
| BOM + CRLF | `trial.ps1` 41 523 B / BOM=True / CRLF 551 / 裸 LF 0；`tunnel.ps1` 91 278 B / BOM=True / CRLF 1208 / 裸 LF 0 |
| `trial.ps1` 参数块的 `$` 名字 | `['Build','Force','Lan','Port','Reset']`（⚠️ 新加的注释里**一个 ASCII 右括号都没有** —— 守卫用「第一个 ASCII 右括号」切参数块） |
| `pytest tests/test_trial.py tests/test_tunnel.py tests/test_serve.py` | **78 passed**（基线 76；+2 条新守卫） |

---

## 5. 重建产物 + 重打包 + Task 4 那六格

### 5.1 重建时刻

```
npx vue-tsc -b     → 退出码 0（先行；改完 G8 与 G11 各跑过一次，两次都 0）
npm run build      → 开始 2026-10-17 00:02:56 +08:00
                     结束 2026-10-17 00:03:00 +08:00   （✓ built in 500ms，退出码 0）
```

⚠️ **本波只重建这一次**（派单逐字要求）。⚠️ 而重建**之前**的全部功能验证一律走
**我自己的 vite（8042）+ 产品档后端（8040）**，故 G8 的改后取证与三轮 smoke
都是在**旧产物还挂着**的时候做完的 —— 甲方那条链接只在 00:03:00 这一刻换过一次。

### 5.2 新旧哈希对照

`frontend/dist`：**29 文件 / 687 804 B → 29 文件 / 686 680 B**（**−1 124 B** =
G11 把开发账本换成业务口径之后正文变短）。逐格：**逐字未变 13 / 换名字 15 /
`index.html` 内容变 1**。

派单点名的那三个：

| 产物 | 改前 | 改后 |
|---|---|---|
| `index.html` | 2 729 B / `F7F3B41842D7F119` | 2 729 B / **`AC8484448A88779D`** |
| 主 CSS | `assets/index-C6De3tZH.css` 65 374 B / `B1F39AA52898F17A` | `assets/index-CXfWaVPp.css` 65 374 B / **`08D2A30C44B70252`** |
| 主 JS | `assets/index-jhn2Va5H.js` 176 169 B / `4A26DE4D7740DEFC` | `assets/index-DahkQ_Ao.js` 175 726 B / **`BDB6730D6CCAD2B4`** |

换名字的 15 个（旧 → 新，字节 / sha256[:16]）：

| 旧 | 新 |
|---|---|
| `AlertQueue-BzTGYm0y.css` 3933/`098CD38930FAC99C` | `AlertQueue-8Ls9FlIi.css` 3933/`6669D3636D8ACAC3` |
| `AlertQueue-DATJms7k.js` 22560/`D427302143B069D1` | `AlertQueue-ZvrY-qvj.js` 22187/`F1844A66D162695A` |
| `AuditLogList-CcjIUHJJ.js` 9553/`192ECBDEB0014CCC` | `AuditLogList-pR_Wt5J_.js` 9553/`00AF972749D2CF1F` |
| `ClassReport-Cfi6f8J8.js` 16893/`A085ECBCC28686FB` | `ClassReport-Db-QWurH.js` 16836/`B7DE3BE1C49BBC7F` |
| `ClassReport-D4ubkA9O.css` 2547/`FBFAD2CF34FDA25D` | `ClassReport-CubUjfI1.css` 2547/`48E398FD0648F292` |
| `Dashboard-DJe5Dc-9.js` 22985/`AF1149105A10993B` | `Dashboard-DAnSoE_Y.js` 22985/`DB960FC5DB0EA500` |
| `ResourceDetail-Dv3_1PVG.js` 12227/`D7F1C0F80CD72AC0` | `ResourceDetail-C7ZvMGZR.js` 12383/`3D1BD3BB05487092` |
| `ResourceIndex-DqalY3wm.js` 9144/`588A301421A96F2F` | `ResourceIndex-B7JHSI8U.js` 8974/`122C8690E8C4DDAD` |
| `ResourceList-BrSZ_Hde.js` 16631/`5D01CB304A5B7C18` | `ResourceList-Ba94nyo4.js` 16641/`6647A965E34BCE4C` |
| `StudentDetail-B25kLg7Z.js` 43595/`8DBE5F64CE72EB8A` | `StudentDetail-DiUOUcLh.js` 43348/`CB88A591E0DD3C96` |
| `StudentDetail-DMe4T_S4.css` 2547/`0A9A02929B24F50F` | `StudentDetail-C4xmZ49B.css` 2547/`CE718835A5590D27` |
| `TeacherNav-BRwUzxFV.js` 4394/`71FC6B4F7A4016AF` | `TeacherNav-DWuyrXMz.js` 4394/`8664F804C5728FFE` |
| `contract-DhB9q9tM.js` 2335/`06C2B95A95A1CB1E` | `contract-CSSO9fSo.js` 2335/`44CDB69618E58A89` |
| `index-C6De3tZH.css` 65374/`B1F39AA52898F17A` | `index-CXfWaVPp.css` 65374/`08D2A30C44B70252` |
| `index-jhn2Va5H.js` 176169/`4A26DE4D7740DEFC` | `index-DahkQ_Ao.js` 175726/`BDB6730D6CCAD2B4` |

逐字未变的 13 个：4 个 woff2、2 个 svg、`SectionHead-{DZfcemhW.js,D8xp8nwc.css}`、
`ProgressBoard-{BGXMH9jO.js,I9MasTHy.css}`、`resources-CuRO6meR.js`、
`TeacherNav-CDBSzZ-C.css`、`Dashboard-DBVBMkeT.css`。

⚠️ 换名字的 15 个里 **6 个的字节数一格没变**（`AlertQueue.css` 3933 / `AuditLogList.js` 9553 /
`ClassReport.css` 2547 / `Dashboard.js` 22985 / `StudentDetail.css` 2547 /
`TeacherNav.js` 4394 / `contract.js` 2335）⇒ 印证了 §13.21.5 已经量过的那一格：
**Vue scoped-CSS 的 `data-v-` id 由源文件内容派生**，故改一个 `.vue`（哪怕只改注释）
就会连带换掉它与它的消费者的哈希。**本波改文案必然换哈希 = 预期的**。

`check:dist` 的扫描面：**25 个文件 / 575.9 kB → 25 个文件 / 574.8 kB**（判据与下界一格未动）。

### 5.3 甲方那条 URL 的匿名复核（⚠️ 一个登录/写入请求都没发）

```
URL = https://related-llp-briefing-holds.trycloudflare.com   （从 .trial\public-url.txt 现读）
  /api/health → 200 / 54 B / 墙钟 6.3 s / {"status":"ok","tables":28,"students":60,"trial":true}
  /login      → 200 / 2 729 B / sha256[:16] AC8484448A88779D / 墙钟 6.0 s
                它引用的产物 = index-DahkQ_Ao.js + index-CXfWaVPp.css
  ⇒ 与本地**新** index.html 逐字相同（本地 sha256[:16] 也是 AC8484448A88779D）
  ⇒ **那条活链接已经在服务新版**（静态文件按请求从磁盘读，故不需要重启任何进程）
```

⚠️ 收尾又复核了一遍（§8）：`/api/health` 200 / **54 B** / 墙钟 **5.8 s**、
`/login` 200 / 2 729 B / `AC8484448A88779D` ⇒ 与基线的「匿名 health 200 / 54 B / 约 5.8 s」
**同一形状**，只是产物换成了新的那一份。
⚠️ 而**已经打开的页面**在懒加载一条没访问过的路由时会 404 一次 ⇒
**控制者需要通知甲方 Ctrl-F5**（这是本波唯一需要甲方做的动作）。

### 5.4 重打包 + Task 4 那六格逐格复核

`scripts\package.ps1` 重跑一次（⚠️ **本波只重打这一次**），退出码 0。

| | 旧包 | 新包 |
|---|---|---|
| 名字 | `pe-ims-trial-20261016-182257.zip` | **`pe-ims-trial-20261017-000506.zip`** |
| 字节 | **10 369 851 B** | **10 417 600 B**（**+47 749 B**） |
| 文件数 | **339** | **339**（一格不变） |
| sha256[:16] | **`4C3D45EF5B7D5F57`** | **`C442737A325528D1`** |

⚠️ 报完那三个数之后**旧包已删掉**（派单要求）；`dist-pack\` 里现在只有新包一个。
⚠️ 包内的分组：`Document` 28 个 / 8 331 812 B · `backend` 207 个 / 6 388 115 B ·
`frontend` 99 个 / 3 072 037 B · `scripts` 4 个 / 225 917 B · `README.md` 1 个 / 7 267 B。
⚠️ `+47 749 B` 而文件数不变的理由：本波改的是**已有文件的内容**
（`trial.ps1` +10 941 B、`tunnel.ps1` +7 029 B、两个测试文件 +10 371 B 与 +6 629 B、
12 个 `.vue`/`.ts` 净 −1 124 B 落在 `dist` 里），而 `scripts/**` 与 `backend/tests/**`
都整个进包。

**六格逐格**：

| 格 | 判据 | 实测 | 判定 |
|---|---|---|---|
| ① | 新包三个数与旧包对照 | 见上表 | ✅ |
| ② | 解包后 health 200 + **16 条路由逐条 200** | `/api/health` → 200 / **54 B** / `{"status":"ok","tables":28,"students":60,"trial":true}`；**16/16** 条路由 200 且回 SPA 外壳（每条 2 729 B、`<div id="app">` 在场）；服务出去的产物 = `index-DahkQ_Ao.js` + `index-CXfWaVPp.css` | ✅ |
| ③ | 包内 `dist` 与仓库 `dist` **逐文件 sha 相同** | 两侧各 **29 文件 / 686 680 B**；只在包里 **0** / 只在仓库里 **0** / 同名而 sha 不同 **0** | ✅ |
| ④ | 包内**说明书**与仓库那份**逐字节相同**（⚠️ G10 必须在本波变绿） | 两侧各 **29 811 B / `B6B37D236532F426`**（176 行含末尾空行 = 编辑器口径 **175 行**） | ✅ **G10 变绿** |
| ⑤ | **含空格与中文的目录**里起服务通（终审 S1-1 的复验路径） | 解包到 `$TEMP\p07t10\体育系统 试用 pack2`（含空格 = True、含中文 = True），跑**包里那份** `trial.ps1 -Port 8044`（⚠️ **缺省**、不带 `PE_DB_URL`）：灌库 7 步全过（60 学生 / 32 预警 / 5 周报，与仓库侧逐字同形）→ 起服务 → health 200 / `trial:true` → 16 条路由全 200。**另跑一档**：`PE_DB_URL` 指向同一个含空格+中文的目录（`-Port 8045`）⇒ 也全通 | ✅ |
| ⑥ | 包内 **spec** 与仓库那份**逐字节相同**（⚠️ Task 9 实测包里那份少 **448 行**） | 打包那一刻两侧各 **767 383 B / 7364 行 / `FD68CFFD8526448C`** ⇒ **逐字节相同** ✅；⚠️ 而本波**随后**又给 spec 加了 §13.22 与 §15 的结案（→ 807 620 B / 7775 行），那一部分**不在这个包里** | ✅（⚠️ 残留如实记为 **G18**） |
| 附 | 包里的**四个脚本**与仓库逐字节相同 | `trial.ps1` 41 523 B / `0D00814BB2BB7EA1` · `tunnel.ps1` 91 278 B / `D4D095FF8C318422` · `serve.ps1` 47 990 B / `93E7F727F6746613` · `package.ps1` 45 126 B / `35F4FC02414C7BAA` —— **四个都 ✓** | ✅ |

⚠️ **格 ⑥ 那一句如实交代（硬规矩 #39）**：派单逐字要求「包只重打一次」，而那一次
排在 spec 的本波更新**之前** ⇒ 包里那份 spec 是「含 G7–G12 六条**未结案**台账」的那一份。
⚠️ 它**不是** G10 那一格缺陷的复现：G10 的实物是「包里的**说明书**是改前的
（12 处假话都还在）+ 包里的 spec 少 **448 行**」⇒ 甲方会照着假话做；
而本波包里那一份**说明书 / dist / 四个脚本**都与仓库**逐字节（逐文件）相同**，
差的只是「我方内部台账的结案节」，⚠️ 而甲方 IT 要的运行口径（§13.1–§13.21）**全在包里**。
⇒ 登记为 **G18**，交控制者裁定。

⚠️ **格 ⑤ 的路上踩到两件事，都如实记**：
1. 我自己的探针用 `Start-Process -ArgumentList <数组>` 起 `trial.ps1`，而解包目录名含空格
   ⇒ `-File` 的值被切成两截（**终审 S1-1 那一族，这次踩在我自己的探针上**，
   产品侧那一格由 `serve.ps1` 的 `Format-NativeArgumentList` 早就修好了）。
   改成自带引号之后通过。
2. 同一次探针里（`-WindowStyle Hidden` + `-RedirectStandardOutput`，即**无控制台**）
   灌库当场 `sqlite3.OperationalError: unable to open database file`。
   ⚠️ **排查过程**（四步，全部实测）：① 四档路径形状（纯 ASCII / 有空格 / 有中文 /
   中文+空格）直连 `create_engine` **全过**；② 同四档走 `app.db.session.init_db`
   （= alembic 那一条路径）**全过**；③ 单独量那一次 `python -c` 的往返：
   `[Console]::OutputEncoding` 本机实测就是 **utf-8 / codepage 65001**，
   `make_url` 剥出来的 `database` 与原串 `-ceq` 为 **True**（两档都对，
   把 `[Console]::OutputEncoding` 显式设成 UTF-8 之后也对）；④ **同一个包、同一个 URL、
   同一个含空格+中文的目录**，在**正常终端**里跑**两次都全通**（8044 走缺省、8045 走
   `PE_DB_URL`，两档都灌库 + 起服务 + `trial:true`）。
   ⇒ 真因**最可能**是「无控制台 + 重定向」那一档下 PS 5.1 解子进程 stdout 的口径不同，
   ⚠️ 而本波**没有把它钉死**（要钉死得再造一个无控制台的父进程并逐字节比对，
   那一格与交付面无关）。⚠️ 失效方向是**响亮**的（`throw` + 退出码 1 + **不硬删**）。
   ⇒ 登记为 **G17**，并给了彻底免疫的做法。

---

## 6. 测试与 smoke

### 6.1 `pytest`：1631 → **1633**

| 跑法 | 结果 | 墙钟 |
|---|---|---|
| `python -m pytest -q --no-header --no-cov` | **1633 passed**（基线 **1631**，**+2** = G7 与 G9 各一条新守卫） | 187 s（`185.22s`） |
| `… --cov=app/domain --cov-branch --cov-report=term` | **1632 passed, 1 skipped** | 312 s（`299.64s`） |
| `… --cov=app --cov-branch …` | **1632 passed, 1 skipped** | 313 s（`310.99s`） |
| `… --cov=scripts --cov=app.static --cov-branch …` | **1632 passed, 1 skipped** | 289 s（`286.64s`） |

⚠️ 四遍退出码全 **0**。⚠️ 那 1 条 skipped 与基线同一格（带 `--cov` 时的那一条）。

### 6.2 覆盖率三口径四格：**一格都没退**（三格与基线**逐字相同**）

| 口径（⚠️ 第三格 canonical 写法是**点号** `--cov=app.static`） | Stmts | Miss | Branch | BrPart | Cover | 基线 |
|---|---|---|---|---|---|---|
| `--cov=app/domain --cov-branch` | **1268** | **0** | **376** | **0** | **100%** | 1268/0/376/0/100% ✅ 逐字相同 |
| `--cov=app --cov-branch` | **7311** | **201** | **1778** | **115** | **96%** | 7311/201/1778/115 ✅ 逐字相同 |
| `--cov=scripts --cov=app.static --cov-branch` | **583** | **173** | **164** | **24** | **69%** | 583/173/164/24 ✅ 逐字相同 |

⚠️ 三格逐字相同的理由：本波**一行后端产品代码都没动**（`git diff dd48b2a HEAD --name-only`
里 `backend/` 下只有 `tests/test_trial.py` 与 `tests/test_tunnel.py` 两个**测试**文件）。
⚠️ `Cover` 列不是基线（spec §12 有裁定），故上表把它印出来只是随手一记。

### 6.3 `smoke.mjs`：三档全绿（⚠️ 断言数只增不减）

| 档 | 跑法 | 步数 | 断言 | 退出码 | 基线 |
|---|---|---|---|---|---|
| **dev** | `PE_API_BASE=http://127.0.0.1:8040 PE_WEB_BASE=http://localhost:8042`（⚠️ **重起过一次 vite**：smoke 文件头把「跑之前重起 `npm run dev`」写成硬要求，D7 那一拍对模块图的新鲜度敏感） | **18/18** | **770 绿 / 0 红** | **0** | 746 ⇒ **+24** |
| **产品档** | `PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8040`（`serve.ps1 -SkipBuild`，同源） | **18/18** | **770 绿 / 0 红** | **0** | 746 ⇒ **+24** |
| **试用档** | `PE_TRIAL=1 PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8044`（⚠️ **解包目录里那份 `trial.ps1` 起的原件**） | **18/18** | **802 绿 / 0 红** | **0** | 778 ⇒ **+24** |
| **公网档** | ⚠️ **本波没跑** | — | — | — | 778 |

⚠️ **步数仍是四档各 18**：§G8 那一组是**加在第 14 步里面**的（复用它的 CDP 会话与
无头浏览器），故步数不变、断言数 +24。
⚠️ 三档各自跑之前都换了一份**刚灌出来的库**（第 0 步核实的就是行数：
60 学生 / 32 预警全 pending / 3 教师 / 恰好 1 个管理员 / 5 周报…，三档全绿）。
⚠️ 第 14 步的断言数：dev 与产品档 **237 → 269**（+32 = §G8 的 16 拍 + `realClick`
自带的反空转拍），试用档同步。
⚠️ **DOM 的重叠 / 溢出 / 整页滚动条**：三档的第 14 步对 **16 条路由逐条**量，
`overlapCount` 与 `overflowCount` 全 **0** ⇒ G11 把文案改短没有把布局改坏。
⚠️ **公网档为什么没跑**（派单：「若要跑，开你自己的第二条隧道打你自己的实例」）：
见 §7.3。

---

## 7. 待清扫 / 关切 / 没按派单做的 / **顶回**

### 7.1 待清扫（本波新登记 **6** 条，逐条住 spec §15 **G13–G18**）

1. **G13** · 登出会触发一整批「注定 401」的读请求（= **G8 的上游**，本波只修了横幅那一格）。
   ⚠️ 单一所有者的位置不好挑：逐页加早退是 8 个文件各写一遍（正是派单禁止的
   「每个页面各清一次」那一族），而改 `useAsync` 要给它一个「身份还在不在」的谓词
   （一个共享 composable 与 `stores/identity` 之间的新耦合，13 个页面都走它）。
   建议做法与「改完 §G8-②③ 会红、那时该怎么办」都逐字写在 spec §15 G13 里。
2. **G14** · `ApiErrorBanner.vue` 文件头那句「不跨页共享（**换页要清**）」**没有实现**
   （本波只补了「换**身份**要清」）；⚠️ 同族一行：DEV-only 切换器的
   `students`/`teachers`/`loadFailure` 三个 ref 在 dev 构建里跨身份留在内存中
   （**不进产物**、且登出后不渲染 ⇒ 甲方看不见）。
3. **G15** · `/login` 上那块 401 横幅的 advice 有**两处半假**：① 登出之后落在 `/login` 上时
   「送你去的登录页」就是**当前这一页**；② 而「回到刚才那一页」在**登出**这一档不成立
   （`onLogout()` 做的是 `router.replace('/login')`，**不带** `?next=`）。
   ⚠️ 在**会话过期**那一档两句都成立（`main.ts` 的订阅者带 `next`）⇒ 这是
   「同一句话被两个时机共用、而只对其中一个为真」。⚠️ **本波刻意没改它**：
   它既不含波次编号也不含 `file:line`（用户裁定的范围之外），而那一句被 §15 G8 的
   登记原文**逐字引用**过 ⇒ 改它要连着改 spec。交控制者裁定。
4. **G16** · 同一族的开发账本住在**不渲染**的地方（三处，本波刻意不动）：
   ① `router/index.ts` 的 **19** 处 `meta.task`（**0 个消费者**）② **13** 个 `.vue` 的
   `<script>` docblock（派单逐字交代「已登记为另一类待清扫」）③ 根 `README.md` 的 **1** 处
   波次编号（L94）—— ⚠️ README **进包**，故甲方 IT 读得到它，优先级高于 ①②。
5. **G17** · G7 那一格在「`PE_DB_URL` 含非 ASCII 路径 **且** 父进程是一个**无控制台**的
   `Start-Process -RedirectStandardOutput`」下会把路径弄成 mojibake（⇒ 灌库
   `unable to open database file`、退出码 1、**不硬删**）。⚠️ 正常终端里两次实测都全通、
   单独量那一次编码往返也逐字相同 ⇒ 真因**最可能**在无控制台那一档的 stdout 解码口径，
   本波**没有钉死**。彻底免疫的做法（写临时文件 + `ReadAllText(…, UTF8)`）写在 spec §15 G17。
6. **G18** · 本波那个包里的 spec 是「台账**未结案**」的那一份（派单要求「包只重打一次」，
   而那一次排在 spec 更新之前）。⚠️ 与 G10 的严重性差一个量级（§5.4 逐格交代）。
   ⚠️ **建议**在把链接 + zip 发出去**之后**再排一次重打包窗口（zip 是**离线**交付物，
   重打**不会再打扰甲方**）。

⚠️ 另外 **3 条**是既有的、本波**没有**动：`$env:TEMP` 下我造的 `p07t10\`（收尾已删净并复验，§8.5）、
`pe_trial_csv_41684`（**8030 正在用**，派单明令不许删，✓ 留着）、
以及 Task 9 留下的 `p07t9\`（不在本波责任面，⚠️ 我**没碰**）。

### 7.2 关切（**3** 条）

1. ⚠️⚠️ **甲方需要 Ctrl-F5**（本波唯一需要他们做的动作）：`dist` 已在
   **2026-10-17 00:03:00 +08:00** 重建，那条活链接**已自动切到新版**，
   而**已经打开的页面**在懒加载一条没访问过的路由时会 404 一次。
2. ⚠️ **G15 是甲方**看得见**的**：照说明书 §4 路线二第 7 步走，登出之后落在 `/login` 上
   会看到一块红色 401 横幅，而它那句「前端会把你送去登录页 / 登录之后回到刚才那一页」
   在那一刻是半假的（⚠️ 它**不再**跨到下一个身份上 —— 那一格已修）。
   ⚠️ 本波**没改它**（理由见 §7.1 第 3 条），⚠️ 若控制者认为交付前该改，那是**一行**的事
   （改 `ApiErrorBanner.vue` 的 `BRANCHES.unauthenticated.advice`），
   而**代价是再重建一次 `dist` + 再重打一次包 + 再打扰甲方一次** ⇒ 本波**不建议**。
3. ⚠️ **G13 在公网档上是 5 趟边缘往返**：每次登出白发 5 个请求（其中 4 个 401），
   而 §13.21.4 实测每趟 959–1 110 ms ⇒ 甲方经隧道登出时会多等约 1 秒。
   ⚠️ 没有数据损坏、没有请求丢失、横幅也不再残留（G8 已修）。

### 7.3 没按派单做的（**1** 处，如实记）

⚠️ **公网档 smoke 没跑**（派单：「⚠️ 公网档若要跑，开你自己的第二条隧道打你自己的实例」）。
理由三条：① 派单用的是「**若**要跑」，三档（dev / 产品档 / 试用档）是**明令**的，
三档全绿；② 公网档要多一个 `PE_ENV=prod` 的实例（本波 8040/8043/8044/8045 四个实例
都是 dev 档，起 prod 档还要 `PE_CORS_ORIGINS`）+ 一条真的公网隧道，
而在**甲方正在试用**的当口再开一条公网入口是一次**新的暴露面**
（`tunnel.ps1` 自己那六条风险告示逐字写着「随机不等于鉴权」）；
③ G9 的判据已经用**更强的**姿势取到行为证据 —— 把那个函数**原样切出来真跑**，
打在甲方那一份**真活着**的 URL 文件上（`RecPort=8030` / `RecPid=37196` /
`RecMarker=pe_tunnel_8030` ⇒ `other-alive` ⇒ 不动它），⚠️ 那正是 Task 9 出事的那一档，
而它**不需要**为了取证再开一条公网入口。
⚠️ 代价如实记：公网档的断言数（基线 **778**）本波**没有复核**；
⚠️ 而它与试用档的差异只在 `PE_COOKIE_SECURE=1` 那一拍（第 16 步 ⑦ 按档取期望）
与墙钟，§G8 那一组在两档上跑的是**同一段代码**。

### 7.4 **顶回**（**1** 处）

⚠️ **G7 的形状：顶回 spec §15 G7 原提的「加一个 `-DbPath <path>`」，改用 `$env:PE_DB_URL`。**
spec §15 G7 的「怎么做（Plan 08，⚠️ 建议排第一）」逐字写着
「给 `trial.ps1` 加一个 `-DbPath <path>`（缺省仍是 `backend\pe_trial.db`，⚠️ 于是
「唯一所有者」那一格改成「**缺省值**的唯一所有者」，守卫跟着改**判据**而不是删掉）」。
派单把选择权交给我（「⚠️ 你选一种并说明」），我选 `PE_DB_URL` 并**顶回** `-DbPath`，
三条理由（逐字也写进了 `trial.ps1` 的 `.DESCRIPTION` 与 spec §13.22.4）：
① `PE_DB_URL` **已经是**本仓「用哪个库」的唯一口径（`serve.ps1` 的 ③ a 就读它、
而它自己那条 `pe.db` 禁区守卫也建在它上面）⇒ 加 `-DbPath` 会造出**第二个所有者**
（正是 spec 那一句自己担心的事，而它没意识到 `PE_DB_URL` 已经在了）；
② **交付面一个旋钮都不多**：`trial.ps1` 是随包交给甲方 IT 跑的，参数面每多一个就要
跟着改说明书 §2 ③ 与 README（spec G7 自己也写了这一条代价），而环境变量那一侧
它们**一个字都不用改**；③ 「唯一所有者 → 缺省值的唯一所有者」那一格**照样要做**
（`$DefaultTrialDbPath = Join-Path $Backend $TrialDbName`），既有守卫
`assert "Join-Path $Backend $TrialDbName" in statements` 与
`statements.count('"pe_trial.db"') == 1` **两条都不用改**（实测都仍绿）⇒
比 `-DbPath` 那一格**少改一条守卫**。
⚠️ 而派单要的第二道闸（`-Force`）**照做**，且**方向不反过来**（理由见 §4.2）。

⚠️ **其余 5 处派单点名的「最可能顶回」，逐个核过、都不顶**：
① **G8 的根因不在后端**（后端那 4 个 401 是**正确**行为：会话已吊销 ⇒ 401；
病灶在前端「登出触发重读」+「横幅没有身份级的清理点」两格）⇒ 「后端产品代码原则上不动」
**一条都没破**（`git diff dd48b2a HEAD --name-only` 里 `backend/` 下只有两个**测试**文件）；
② **G11 一条 needle 都没伤到**（首跑红的那 1 拍是我多改了函数名，收回后自绿，§3.5）；
③ **G9 选「另写带端口后缀的文件」**（理由见 §4.1）；
④ **G7 的第二道闸方向对**（缺省不走闸 ⇒ 缺省行为一格不变；反过来会改坏甲方手上
那条已写进说明书与 README 的命令）；
⑤ **G12 在 Windows 上拿不到可靠判据**（Restart Manager 要 `Add-Type`，而甲方那台机器
可能在 ConstrainedLanguage 档下直接挡掉它）⇒ 选派单给的「退一步」那一档。

---

## 8. 最终验收

### 8.1 后端与契约面

| 格 | 基线 | 本波实测 | 判定 |
|---|---|---|---|
| 表数 | 28 | **28**（`/api/health` 的 `tables` 一格；甲方那条 URL 与我的 4 个实例都回 28） | ✅ |
| 迁移链 | **4 单头** | `tests/db/test_migration_baseline.py::test_the_chain_has_exactly_one_head_today` 绿；四遍灌库日志里都逐字是 `53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`（**4 步、单头**） | ✅ |
| 残差 diff | **0** | `test_the_migrated_database_matches_base_metadata_table_by_table` + `test_alembic_upgrade_head_and_create_all_agree_table_by_table` 绿 | ✅ |
| 扫描面 | 72 | `tests/architecture` + `tests/db` + `tests/test_refdata.py` **133 passed**（含扫描面那一条） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | 同上（133 passed 里含它） | ✅ |
| 黄金用例 | 14 | 同上 | ✅ |
| 未定型响应 | 24 | 同上 | ✅ |
| **openapi 五格** | 74 路径 / 102 操作 / 挂 security 84 / GET 63（15 匿名 + 48）/ securitySchemes 3 | **74 / 102 / 84 / 63（15 + 48）/ 3** ← 逐格相同 | ✅ |
| **openapi 字节与 sha** | **420 367 B / `6058F97F09B35855`** | **420 367 B / `6058F97F09B35855`** ⇒ **逐字未变**（⚠️ 本波只改前端与脚本、不改后端 docstring，故这一格**应当**不变，实测确实不变） | ✅ |
| 依赖清单守卫 | 一字不红 | `pyproject.toml` / `package.json` / `package-lock.json` **零 diff**；新增依赖 **后端 0 / 前端 0**；`test_tunnel.py::test_cloudflared_is_a_machine_tool_and_never_enters_a_manifest` 绿 | ✅ |

### 8.2 数据与禁区面

| 格 | 实测 |
|---|---|
| 四个数据指纹 | `tests/test_refdata.py` 绿（`D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7`） |
| 18 个模板指纹 | 同上（`test_refdata.py` 那一条逐个对账） |
| 24 个入库文件 | `backend/data/**` 一个字节没动：`git diff dd48b2a HEAD -- backend/data` → **空** ✅ |
| `backend/pe.db` | **不存在**（`False`）✅ |
| `backend/data/seed/` | **0 文件**（`-Recurse` 数）✅ |
| 八处 gitignore 项 | `pe.db` / `pe_demo.db` / `pe_trial.db` / `backups` / `frontend/dist` / `tools` / `.trial` / `dist-pack` —— `git ls-files` 底下**各 0 个文件** ✅ |
| 四份 manifest + `.gitattributes` + `.gitignore` | `backend/pyproject.toml` / `frontend/package.json` / `frontend/package-lock.json` / `.gitattributes` / `.gitignore` —— **零 diff** ✅ |
| 禁跑的三个 CLI | `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` **一次都没跑**（灌库一律走 `backend/scripts/demo_bootstrap.py`） |

### 8.3 本波改到的文件（**19** 个；⚠️ 后端产品代码 **0** 个）

```
backend/tests/test_trial.py            backend/tests/test_tunnel.py
frontend/scripts/smoke.mjs             frontend/src/App.vue
frontend/src/components/ApiErrorBanner.vue
frontend/src/router/index.ts           frontend/src/stores/session.ts
frontend/src/views/admin/ResourceDetail.vue
frontend/src/views/admin/ResourceIndex.vue
frontend/src/views/admin/ResourceList.vue
frontend/src/views/auth/Bind.vue       frontend/src/views/student/Home.vue
frontend/src/views/student/Notifications.vue
frontend/src/views/student/RpeEntry.vue
frontend/src/views/teacher/AlertQueue.vue
frontend/src/views/teacher/ClassReport.vue
frontend/src/views/teacher/StudentDetail.vue
scripts/trial.ps1                      scripts/tunnel.ps1
```

⚠️ 加上第 ⑤ 个 commit 的三份文档（spec / `progress.md` / 本报告），共 **22** 个文件。
⚠️ `backend/app/**`、`backend/scripts/**`、`backend/migrations/**`、`backend/data/**`
**一个字节都没动** ⇒ 「后端产品代码原则上不动」这一格**守住了**（G8 的根因确实在前端，
§7.4 ①）。

### 8.4 收尾五格（⚠️ 与 §1.2 开工那五格对拍）

| 格 | 收尾实测 | 判定 |
|---|---|---|
| ① PID **45156** | `python` / StartTime **`2026-10-16 00:36:05`** / 8030 在听 | ✅ **仍在，逐字未变** |
| ② PID **37196** | `cloudflared` / StartTime **`2026-10-16 10:14:35`** | ✅ **仍在，逐字未变** |
| ③ `backend/pe_trial.db` | **1 589 248 B** / sha256[:16] **`40D7B5F78A7C36CB`** | ✅ **逐字未变** |
| ④ 甲方 URL | `/api/health` **200 / 54 B / 墙钟 5.8 s**；`/login` **200 / 2 729 B / `AC8484448A88779D`**，引用 `index-DahkQ_Ao.js` + `index-CXfWaVPp.css`，**与本地新 `index.html` 逐字相同** | ✅ **仍 200，且服务的是新哈希** |
| ⑤ `.trial\public-url.txt` | **1 701 B** / sha256[:16] **`0899037E4A220B01`** | ✅ **逐字未变**（G9 那一格的现场复核） |

### 8.5 我自己起的进程 / 孤儿 / TEMP（⚠️ 全部停净并复验）

| | 处置 | 复验 |
|---|---|---|
| 8040 产品档 `serve.ps1` | 起了 4 次（每次换一份刚灌的库），逐个 `StopCommand` | 收尾 `Get-NetTCPConnection -State Listen` 里 **8040 不在** ✅ |
| 8042 我自己的 vite | 起了 2 次（G8 改后取证一次、dev 档 smoke 前按硬要求重起一次），逐个 `StopCommand` | **8042 不在** ✅ |
| 8043 `trial.ps1`（G7/G12 取证） | `StopCommand` | **8043 不在** ✅ |
| 8044 / 8045 解包目录里的 `trial.ps1`（六格 ②⑤） | 8044 `StopCommand`；8045 `StopCommand` | **8044 / 8045 都不在** ✅ |
| 6 个孤儿 `msedge.exe` | 开工时杀掉（§1.3）；本波自己起的 headless Edge 都由 harness 自己 `kill('SIGKILL')` + 删 profile | 收尾复验：命令行含 `pe-smoke-cdp-` / `p07t5-cdp-` / `p07t9` / `p07t10-cdp-` 的 msedge = **0 个** ✅ |
| `$env:TEMP\p07t10\` | 探针、日志、5 个库、解包目录（含空格+中文）、`csv*` 全在里面 | **已删净并复验**（见下；⚠️ 之后为了订正本报告 §8.5 这两句话又**重建过一次** `p07t10`，改完**再删净并复验** ⇒ 交付时点它是**不存在**的） |
| ⚠️ **不许删的三个** | `p07ctl` / `pe_trial_csv_41684`（8030 正在用的 `PE_CSV_DIR`）/ `pe_tunnel_8030` | **一个都没碰** ✅（⚠️ 我自己那几次 `trial.ps1` 造的 `pe_trial_csv_*` 里，只有 `_43120` 是脚本自己在 `finally` 里删掉的；`_41356` / `_47396` / `_4796` / `_51728` 四个因为我是**硬停**的、`finally` 跑不到 ⇒ **收尾手工删净并复验**：`$env:TEMP` 下今天只剩 `pe_trial_csv_41684` 与 `pe_tunnel_8030` 两个，都是派单明令不许删的） |

### 8.6 文档面（新字节数 / 行数）

| 文档 | 基线 | 本波 |
|---|---|---|
| **spec** | 767 383 B / 7363 行 / 全 CRLF / `FD68CFFD8526448C` | **807 620 B / 7775 行**/ **全 CRLF**（CRLF 3888 处、裸 LF **0**）/ **无 BOM** / sha256[:16] 见下 §9 |
| **说明书** | 29 811 B / 175 行（上限 **200**，余量 25） | **29 811 B / 175 行 —— 一个字节都没动** ✅（⚠️ 本波刻意没改它：G11 改的是**页面**文案，说明书里 0 处引用了那些原文，§3.6） |
| **README** | 7 267 B / 111 行 | **7 267 B / 111 行 —— 一个字节都没动**（⚠️ 它那 1 处波次编号登记为 **G16 ③**） |
| **`progress.md`** | 20 080 B / 244 行 | **28 002 B / 337 行**（纯 LF、无 BOM） |

⚠️ spec 加了 **§13.22**（新，7 个小节）+ §15 台账（划掉 G7–G12 六条、补 **G13–G18** 六条、
两处计数更新：总数那一行与 G 组标题「十二件 → 十八件」）。
⚠️ **台账 36 → 36 在册**（划掉 6、新补 6），**已划掉 2 → 8**。

### 8.7 commit

| # | sha | 一句话 | 自洽吗 |
|---|---|---|---|
| ① | **`fb2e8d4`** | `fix(frontend)`: G8 —— 401 横幅不再跨过登录留在下一个身份的页面上（复现 + 修 + smoke §G8 16 拍 + 定点变异） | ✅ 自洽（改 + 守卫同一个 commit；跑得出 770 绿） |
| ② | **`414eca7`** | `refactor(frontend)`: G11 —— 甲方看得见的正文里不再印波次编号与 file:line（40 处 / 12 个文件） | ✅ 自洽（`vue-tsc` 0 / `check:tokens` 绿 / smoke 三档绿） |
| ③ | **`0447379`** | `fix(scripts)`: G9 + G7 + G12 —— 三条脚本缺陷各收窄一格判据（+2 条守卫、改 3 条既有断言、4 条定点变异） | ✅ 自洽（`pytest` 78 passed；⚠️ 不依赖 ①②） |
| ④ | —（**空**） | 重建 `dist` + 重打包 + 六格复核 | ⚠️ **没有可提交的内容**：`frontend/dist` 与 `dist-pack` **都在 `.gitignore` 里**（八处 gitignore 项之二）⇒ 这一件只产出**产物**与**取证**，不产出 commit。⚠️ 如实记，**没有**为了凑五个 commit 而入库任何 gitignore 项 |
| ⑤ | 本 commit | `docs(spec+ledger+progress+report)`: §13.22 新 + §15 台账划掉 6 补 6 + `progress.md` §4 + 本报告 | ✅ 自洽 |

⇒ **本波 4 个 commit**（派单建议 5 个；第 ④ 个结构上不存在，理由如上）。
⚠️ **没有 push**（`main` 上那 15 个待推的 commit 由控制者负责重试）。

---

## 9. 行尾复核（逐个被改文件，两个口径 + 双向可逆）

⚠️ 一律用 **Python 二进制模式**改文件（派单：行尾/BOM 事故已发生四次）；
每改完一个文件**当场**核 `git ls-files --eol`。
⚠️ 判据是**双向逐字可逆**（工作树 →LF 化 == 入库 blob，且 blob →CRLF 化 == 工作树）
+ **裸 LF = 0**，⚠️ 而不是「工作树字节 == blob 字节」（本机 `core.autocrlf=true`，
那一个等式按设计**不成立**，差值恰好 = CRLF 行数；Task 9 在这一格上自己纠正过一次）。

| 文件 | `git ls-files --eol` | 工作树 | 入库 blob | 双向可逆 |
|---|---|---|---|---|
| `frontend/src/stores/session.ts` | `i/lf w/crlf attr/` | 27 525 B / CRLF 441 / 裸 LF 0 / 无 BOM | 27 084 B / LF 441 | ✅ |
| `frontend/src/components/ApiErrorBanner.vue` | `i/lf w/crlf attr/` | 17 771 B / CRLF 422 / 裸 LF 0 / 无 BOM | 17 349 B / LF 422 | ✅ |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | 410 903 B / CRLF 5716 / 裸 LF 0 / 无 BOM | 405 187 B / LF 5716 | ✅ |
| `frontend/src/views/teacher/StudentDetail.vue` | `i/lf w/crlf attr/` | 81 774 B / CRLF 1521 / 裸 LF 0 / 无 BOM | 80 253 B / LF 1521 | ✅ |
| `scripts/trial.ps1` | `i/lf w/crlf attr/text eol=crlf` | 41 523 B / CRLF 551 / 裸 LF 0 / **BOM=True** | 40 972 B / LF 551 / **BOM=True** | ✅ |
| `scripts/tunnel.ps1` | `i/lf w/crlf attr/text eol=crlf` | 91 278 B / CRLF 1208 / 裸 LF 0 / **BOM=True** | 90 070 B / LF 1208 / **BOM=True** | ✅ |
| `backend/tests/test_trial.py` | `i/lf w/crlf attr/` | 50 615 B / CRLF 845 / 裸 LF 0 / 无 BOM | 49 770 B / LF 845 | ✅ |
| `backend/tests/test_tunnel.py` | `i/lf w/crlf attr/` | 85 466 B / CRLF 1371 / 裸 LF 0 / 无 BOM | 84 095 B / LF 1371 | ✅ |
| 其余 9 个 `.vue` / `.ts`（G11） | `i/lf w/crlf attr/` | 逐个核过：CRLF、裸 LF **0**、无 BOM | LF | ✅ |
| `Document/…设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | 807 620 B / **全 CRLF** / 裸 LF **0** / 无 BOM | LF | ✅ |
| `.superpowers/…/progress.md` | `i/lf **w/lf** attr/-text` | 28 002 B / **纯 LF** / CRLF **0** / 无 BOM | **与工作树逐字节相同** | ✅ |
| `.superpowers/…/task-10-report.md`（本文件） | `i/lf w/lf attr/-text` | **纯 LF** / CRLF 0 / 无 BOM | 与工作树逐字节相同 | ✅ |

⚠️ 三份文档（spec / 说明书 / `progress.md`）改完之后 `git status` 与 `git diff HEAD`
都**只剩本波该改的那些**（无行尾噪声、无 BOM 事故）；
`pytest tests/test_trial.py tests/test_tunnel.py tests/test_serve.py tests/test_main.py
tests/test_package.py tests/test_refdata.py tests/seed/test_fitness.py
tests/api/test_prescription_api.py` 在文档改完之后重跑一遍 = **187 passed**
（⚠️ 那 6 个文件里有 4 个**读文档**，故这一遍是承重的）。

---

## 10. 一句话总判断

**能把「链接 + zip + 说明书」交给甲方。**
Task 9 顶回不自修的那一条 **S2**（G8）已修、有守卫（smoke §G8 16 拍）与定点变异（3 拍红）；
甲方看得见的正文里**一处波次编号 / `file:line` 都不剩**（A 面 37 → **0**，
且 **0 条 needle 被迫改**）；三条脚本缺陷各自的判据都收窄了、而**缺省行为一格都没变**
（G7 的缺省档有**可执行**取证）；那个 zip 里的**说明书 / spec / dist / 四个脚本**
与仓库**逐字节（逐文件）相同**（六格 ④⑥ = G10 变绿）；
`pytest` **1633 passed**、覆盖率三口径四格与基线**逐字相同**、`openapi` **420 367 B /
`6058F97F09B35855` 逐字未变**、smoke 三档 **770 / 770 / 802 全绿**；
甲方那两个进程（**45156** / **37196**）与那份库（**1 589 248 B / `40D7B5F78A7C36CB`**）
**一个字节都没动**，那条活链接**仍 200 且已在服务新哈希**。

⚠️ **甲方需要做的唯一一件事：Ctrl-F5**（`dist` 已在 2026-10-17 00:03:00 +08:00 重建，
链接已自动切到新版，而**已经打开的页面**在懒加载一条没访问过的路由时会 404 一次）。

⚠️ 交回控制者裁定的两件：**G18**（要不要在发出去之后再排一次重打包窗口，
让包里的 spec 也带上结案节 —— ⚠️ **建议要**，而它不会再打扰甲方）与
**G15**（`/login` 上那句半假的 advice 改不改 —— ⚠️ **本波不建议**，
因为改它的代价是再重建一次 + 再重打一次 + 再打扰甲方一次）。
