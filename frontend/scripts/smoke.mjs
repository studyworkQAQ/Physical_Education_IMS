#!/usr/bin/env node
/**
 * `scripts/smoke.mjs` —— **真实联调**（计划 Task 5：本计划唯一的「测试」）。
 *
 * ---------------------------------------------------------------------------
 * 它是什么 / 它不是什么
 * ---------------------------------------------------------------------------
 * 它是「**前后端能对接的上**」这句用户裁定的**唯一可执行判据**：
 * 用**真 `fetch`**（不是 FastAPI 的 `TestClient`）打真 uvicorn，走完一条业务链，
 * 把每一步的**请求原文与响应原文**打出来，最后按断言的成败给退出码。
 *
 * 它**不是**前端单测（计划非目标第 4 条：前端逻辑的正确性由后端 1260 条测试兜着，
 * 前端自己的风险全在「对接」上）。它也**不是** E2E 框架 —— 没有 Playwright、
 * 没有断言库、没有 describe/it；一个文件、零依赖、`node` 直接跑。
 *
 * ---------------------------------------------------------------------------
 * 怎么跑（⚠️ 两个前置条件都是**硬要求**：少一个就会读到假红）
 * ---------------------------------------------------------------------------
 *     # ① 起后端（**必须**先复原演示库：本脚本会写库，且第 0 步要核实行数）
 *     powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -Port 8000
 *     # ② 起前端（第 14 步要它）—— ⚠️ **必须是本波重起的那一个**，理由见下面那一节
 *     cd frontend; npm run dev
 *     # ③ 跑
 *     cd frontend; npm run smoke
 *
 * 退出码 **0** = **18 步全绿**（编号 0–17）。任何一步的任何一条断言红了都是 **1**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ **三档都要跑全绿**（Plan 07 Task 1 起；改前是两档）
 * ---------------------------------------------------------------------------
 * 同一份代码要在三档上各跑一整遍，而三档的差别**不在**本脚本里（它只读环境变量）：
 *
 * | 档 | 后端 | 前端 | 库 | `PE_TRIAL` | 跑法 |
 * |---|---|---|---|---|---|
 * | **dev 档** | `demo.ps1 -Port 8000` | `npm run dev`（⚠️ 5173 被别的进程占着时用 `-- --port 5174 --strictPort`） | `backend/pe_demo.db` | 未设 | `PE_API_BASE=http://127.0.0.1:8000 PE_WEB_BASE=http://localhost:5174 npm run smoke` |
 * | **产品档** | `scripts/serve.ps1 -Port 8020` | 同一个 uvicorn 同源发 `dist` | `backend/pe_demo.db` | 未设 | `PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8020 npm run smoke` |
 * | **试用档** | `scripts/trial.ps1 -Port 8030 [-Reset]` | 同一个 uvicorn 同源发 `dist` | `backend/pe_trial.db` | **1** | `PE_TRIAL=1 PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8030 npm run smoke` |
 * | **公网档** | `trial.ps1 -Port 8030 -Reset`（⚠️ 起它的那个终端里先 `$env:PE_ENV='prod'`）+ `scripts/tunnel.ps1 -Port 8030` | 同一个 uvicorn，**经 cloudflared 的 quick tunnel** | `backend/pe_trial.db` | **1** | `PE_TRIAL=1 PE_COOKIE_SECURE=1 PE_API_BASE=PE_WEB_BASE=https://<rand>.trycloudflare.com npm run smoke` |
 *
 * ⚠️ **公网档那一次还要多设一个 `PE_COOKIE_SECURE=1`**（Plan 07 Task 3）：那一档跑
 * `PE_ENV=prod`（隧道边缘是 HTTPS ⇒ cookie 的 `Secure` **成立**、且**必须**在），
 * 而另外三档一律是 `dev`（明文 http ⇒ `Secure` 必须**不在**，否则浏览器拒收、
 * 症状是「登录 200、下一个请求 401」，spec §13.11.3）。第 16 步 ⑦ 那一拍因此
 * **按档取期望**（姿势与上面的 `PE_TRIAL` 逐字同一条：期望侧 = 本进程的环境变量，
 * 被测侧 = HTTP 响应头，两侧不同源）。⚠️ 它**不是**放宽判据：两个方向的失效都响亮
 * —— 在 prod 上忘了设 ⇒ 那一拍红（本波首跑就是这么抓到的，199 s / 710 绿 1 红），
 * 在 dev 上多设了 ⇒ 同一拍也红。
 *
 * ⚠️ **试用档那一次要同时给本脚本设 `PE_TRIAL=1`**：第 14 步「16 条路由上有没有
 * 那条告示」的**期望侧**取自本进程的环境变量，⚠️ 刻意**不**取自 `/api/health`
 * （那会与 `App.vue` 同源 ⇒ 后端把 `trial` 答错时期望侧跟着错 ⇒ 「告示泄漏到别的档」
 * 这一档恒绿）。忘了设的话第 1 步那一拍当场红（响亮，不静默）。
 * ⚠️ 三档各跑一遍因此同时给出两侧的证据：试用档 **16/16 条有告示**、
 * dev 档与产品档 **0/16 条有告示**。⚠️ 而每一档跑之前都要有一份**刚灌出来的库**
 * （第 0 步核实的就是行数）：dev 档与产品档重跑 `demo.ps1`、试用档加 `-Reset`。
 * ⚠️ 端口刻意全错开（8000 / 8020 / 8030 / 5174），故「两档同时起着对拍」是合法的。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 前置条件 ②：跑之前**重起一次 `npm run dev`**（Plan 06 Task 13 / D7 写成硬要求）
 * ---------------------------------------------------------------------------
 * 第 14 步对 **dev server 的新鲜度敏感**，而它此前**自己不检查这一档**
 * （品牌波 §5.1 第 7 条，登记至今）。⚠️ 失效形态很坏：一个跑了几小时、期间源码被改过
 * 很多轮的 vite 会给出**假红**，而那几条红读起来像「本波把布局改坏了」——
 * 品牌波实测过一次，4 条红全是「文本内容重叠」。
 * 根因是 **HMR 对「模块图」那一类改动经常要整页重载才干净**：`router/index.ts`
 * （加/删了一条路由）、`main.ts`（改了启动顺序）、`stores/*.ts`（改了单例的形状）
 * 这些**不是**「换一个组件的渲染函数」那一档，热替换会把新旧两份模块**同时**留在图里，
 * 而第 14 步量的是**渲染后的真值**（DOM 上的文本与矩形），于是它量到的是一个
 * 谁都没写过的混合态。⚠️ 故纪律是：**Ctrl-C 掉那个 vite 再起一次**（刷新页面不够）。
 *
 * ⚠️ **本波同时给它加了一拍真检查**（第 14 步的 §D7，不只是一句散文）：期望侧是
 * **现场从磁盘读**的 `src/router/index.ts` 里全部 `path: '…'` 字面量，被测侧是
 * dev server 此刻**服务出来的那一份**模块文本（`GET /src/router/index.ts`）；
 * 两者不一致就红，而那一句报错直接说「重起 npm run dev」。
 * ⚠️ 它**不写死一个标记串**：写死就等于「每次跑之前要记得改它」= 又一个待清扫项。
 * ⚠️ **产品档自动跳过**，而「这是哪一档」的判据是 **content-type 而不是状态码**
 * （两档各实测过一次：产品档的 SPA fallback 对 `/src/router/index.ts` 也回 **200**，
 * 回的是 index.html；vite 则把 `/src/**.ts` 服务成 `text/javascript`）：
 * 产品档的新鲜度由 `scripts/serve.ps1` 的 ② 那一步**自己判**
 * （源面 `src/**` + 5 个配置文件的最新 mtime vs `dist/index.html` 的构建戳，
 * 源面新就重跑 `npm run build`；⚠️ 并且有一道反空转 —— 源面扫到的文件数 `< 20` 就
 * `throw`，否则「dist 是新的」会假绿）。故本拍在两档都**不会**假红。
 *
 * ⚠️⚠️ **Plan 05A Task 4 之后它「先登录」**：身份不再走 `X-Student-Id` /
 * `X-Teacher-Staff-No` 两个请求头，而是走 `pe_session` **cookie**。Node 的 `fetch`
 * 默认不存 cookie，故本脚本自己维护一个 jar（`JARS` + `ensureJar`，逐字理由见
 * 「cookie jar」那一节）。⚠️ 三个身份：
 *   · `teacher` = **T0001**（`role='teacher'`，验任教范围闸门）
 *   · `admin`   = **T0003**（`role='admin'`，验管理台的 26 个写入操作）
 *   · `student:4`（以及 `student:5` 等，验学生侧的窄端点与越权）
 * 口令是 `demo_bootstrap.py` 的 `DEMO_PASSWORD`（`demo.ps1` 跑完会打印它）。
 *
 * 环境变量（都有缺省值）：
 *   `PE_API_BASE`   后端基址，缺省 `http://127.0.0.1:8000`
 *   `PE_WEB_BASE`   前端基址，缺省 `http://localhost:5173`
 *                   ⚠️ 是 `localhost` 不是 `127.0.0.1`：vite 只绑 `::1`
 *   `PE_BROWSER`    无头浏览器的可执行文件（缺省在几个常见路径里找）
 *   `PE_SMOKE_TRANSCRIPT`  给了就把每一步的请求/响应原文写成 JSON
 *                   （`Document/2026-10-11-前后端联调取证.md` 由它生成）
 *                   ⚠️ **cookie 与口令在 transcript 与 stdout 里一律掩掉**：
 *                   那份文档是**入库**的，把一个活的会话令牌写进 git 等于
 *                   把「谁都能当这个管理员」也写进 git。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它对**后端登录限流**的依赖（Plan 06 Task 3 起）：缺省阈值必须 ≥ 2
 * ---------------------------------------------------------------------------
 * 后端自 Plan 06 Task 3 起对 `POST /api/auth/login` 做限流与锁定：同一
 * `(kind, login)` 在 15 分钟内失败 **5** 次 → 锁 15 分钟，而**锁内那一档回的是与
 * 正常口令错逐字相同的 `401 invalid_credentials`**（不是 423/429；控制者 2026-10-13
 * 的改判，理由是 423/429 会额外告诉探测者「这个标识存在且已被锁」= 一个枚举信号）。
 * 阈值是三格环境变量：`PE_LOGIN_MAX_FAILS` / `PE_LOGIN_WINDOW_MIN` / `PE_LOGIN_LOCK_MIN`
 * （所有者是 `backend/app/auth/policy.py`）。
 *
 * **本脚本对同一个 `(kind, login)` 最多只制造 1 次被计数的失败**，逐格取证如下
 * （`Grep -n "password:" scripts/smoke.mjs` 可复核：**12** 处，其中打在
 * `/api/auth/login` 上的只有 **5** 处 —— `loginJar()` 一处、第 16 步四处）：
 *   · `loginJar()`（三个 jar：`teacher` = T0001 / `admin` = T0003 / `student:4`）
 *     → 一律用**正确**的演示口令，且它自己 `check(status === 200)`，故失败就是红、
 *     不会重试；**0 次**失败；
 *   · 第 16 步 ②（`SMOKE16` 未绑定就登录）→ **403 `password_not_bound`**。
 *     ⚠️ 那一档**一行都不写**（`app/auth/policy.py` 的模块 docstring 第三节：
 *     它没有口令参与，计数它挡不住任何一次口令猜测，而它会把一个把学号打错五次的
 *     新生从「请先绑定」变成「口令不正确」）；**0 次**被计数的失败；
 *   · 第 16 步 ⑥（`SMOKE16` 口令错）→ **401 `invalid_credentials``**；
 *     这是本脚本**唯一**一次被计数的失败 = **1 次**；
 *   · 第 16 步 ⑦（`SMOKE16` 口令对）→ 200，而成功登录**清零**，
 *     故那 1 次在同一个 step 内就被抹掉了；
 *   · 第 16 步 ⑫（`SMOKE16C`）→ 200；**0 次**失败。
 *
 * ⚠️ 于是两个结论，都可以复核：
 *   ① **缺省阈值 5 绰绰有余**，本脚本**不需要**任何后门环境变量
 *      （⚠️ 派单逐字禁止开那种后门：它会让守卫测的不是真路径）。
 *      真正的下界是 **`PE_LOGIN_MAX_FAILS >= 2`** ——若有人把它设成 1，
 *      第 16 步 ⑥ 那一次失败就会把 `SMOKE16` 锁住，于是 ⑦ 拿**正确**的口令
 *      也进不去（锁内回的还是同一个 401），本脚本会红在第 16 步 ⑦；
 *   ② **重复跑不会累积**：一次绿的 run 结束时 `login_attempt` 里**没有任何
 *      `ok = false` 的行**（唯一那一次已被 ⑦ 清零），故「跑五次 smoke 把自己锁在门外」
 *      这一档不存在。⚠️ 而「跑完演示库就脏了」那条纪律**不变**（下面那一节），
 *      它的理由与限流无关。
 *      ⚠️⚠️ **Plan 06 Task 10 起②那一句有一个例外，如实记**：第 16 步 ⑭ 那一组
 *      **刻意**制造 3 次被计数的**绑定**失败（它要的就是「锁得住」这一格的端到端证据），
 *      故 run 结束时 `login_attempt` 里会留下 3 行 `ok = false`、键是
 *      `bind:SMOKE10BIND`。⚠️ 而它**不碰任何真账号**（那是两个不在册的假学号），
 *      且锁定档**不写行**，故「跑五次 smoke」只会把这 3 行留在库里、
 *      不会把任何真账号锁在门外 —— 而演示库本来就是一次性的（下面那一节）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它对**后端绑定限流**的依赖（Plan 06 Task 10 起）：缺省阈值必须 ≥ 3
 * ---------------------------------------------------------------------------
 * 后端自本波起对两个 `bind` 端点（`POST /api/auth/{students,teachers}/bind`）
 * 也做限流与锁定：同一个
 * `(kind, 用途=bind, 标识)` 在 **15** 分钟内失败 **3** 次 → 锁 **60** 分钟，
 * 而**锁内那一档回的是与「验身材料不符」逐字相同的 `403 forbidden`**
 * （控制者裁定，与上面登录那一次改判同一条理由）。三格环境变量是
 * `PE_BIND_MAX_FAILS` / `PE_BIND_WINDOW_MIN` / `PE_BIND_LOCK_MIN`
 * （所有者同样是 `backend/app/auth/policy.py`）。
 *
 * ⚠️⚠️ **本脚本对任何一个真账号最多只制造 1 次被计数的绑定失败**，逐格取证：
 *   · 第 16 步 ③（`SMOKE16` 姓名不符）→ **1 次**；而 ④ 那次**成功**绑定会**清零**，
 *     故它在同一个 step 内就被抹掉了；
 *   · 第 16 步 ③（`NOSUCH99` 不在册）→ **1 次**（另一个键，与上面那个不相干）；
 *   · 第 16 步 ⑤（`SMOKE16` 姓名不符）→ **1 次**（此时已绑定，但那一档排在 409 之前）；
 *   · 第 16 步 ⑭（`SMOKE10BIND` ×3 + `SMOKE10BIND2` ×1）→ **刻意打到锁**，
 *     两个键都是**不在册的假学号**，故它锁不住任何真账号；
 *   · 第 16 步 ③ 那一发「请求体缺字段」是 **422 `request_validation_failed`**
 *     （Pydantic 那一档，根本没进端点体）→ **0 次**。
 *
 * ⚠️ 于是真正的下界是 **`PE_BIND_MAX_FAILS >= 3`**：若有人把它设成 1，
 * 第 16 步 ③ 那一次失败就会把 `SMOKE16` 的**绑定**锁住，于是 ④ 拿**正确**的姓名
 * 也绑不上（锁内回的还是同一个 403），本脚本会红在第 16 步 ④。
 * ⚠️ 而 ⑭ 那一组反过来要求 **`PE_BIND_MAX_FAILS <= 3`**（它打 3 次就断第 4 次是锁内）：
 * 两格合起来 = 本脚本要求那一格**恰好是缺省值 3**，故它**同时**是「缺省值没被人改过」
 * 的端到端守卫。⚠️ 本脚本**不需要**任何后门环境变量（派单逐字禁止开那种后门）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它是**一次性**的：跑完演示库就脏了
 * ---------------------------------------------------------------------------
 * 第 2 步建了一节课、第 5 步交了一条快评、第 6 步打了一次卡、第 9 步处置了一条
 * 预警、第 10 步建了一个学期。故**再跑一次之前一律先重跑 `demo.ps1`**：
 * 第 0 步核实的就是「一个刚复原的演示库」的行数，脏库上它会红。
 * 这是有意的：第 0 步同时充当「你是不是忘了复原」的守卫。
 *
 * ⚠️ **本脚本刻意不自己复原**（Plan 04 收尾波核实过、并选了「打印警告」这一侧）：
 * 那 5 样里有 4 样是可删的，但删它们要按外键顺序逐个来（`rpe_record` 指着
 * `class_session`、`notification` 指着 `alert`、而第 9 步处置过的那条 `alert` 上
 * 还挂着一条 `weekly_adjustment`），而**第 10 步那个学期删不掉**：
 *
 *     `semesters` 在 `catalog.RESOURCES` 里是 `on_delete="forbid"`
 *       → 后端**根本不注册** `DELETE /api/semesters/{id}`
 *       → 打过去是 **405 `http_405`**（不是 409、也不是 204）
 *
 * ⚠️ 于是「删不掉」的那一档是 **`forbid`（端点不存在 → 405）**，
 * **不是** `restrict`（端点存在、删的时候被子表挡住 → 409 `integrity_conflict`）。
 * 两档在本仓**同时存在**、且都在第 10 步里被断言过：`semesters` 是前者，
 * `students` 是后者（一个学生被 12 张表指着 → 409）。
 * 派单里「实测是 `restrict`、DELETE 返回 405」那半句把两档混在了一起：
 * **405 是 `forbid` 的表现，`restrict` 的表现是 409**。
 * ⚠️ 一个「自己复原」的实现要么绕过 HTTP 直接删库（那就不是联调脚本了）、
 * 要么给 `semesters` 开一个 DELETE 端点（那会推翻 `forbid` 那条口径：
 * 「全库的时间轴锚点，9 张表按 semester_id 归组，删一个学期没有安全语义；
 * 『这个学期不要了』的正确做法是把 is_current 置 False」）。两者都比
 * 「跑完打印一句『请重跑 demo.ps1』」贵，故本脚本选后者，并在**开头**也打印一次
 * （跑完才看到的话，已经脏了）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ **18 步（0–17）与本文件里那 18 个 `step(...)` 逐一对应**
 * ---------------------------------------------------------------------------
 * 第 14 步（16 条路由的 DOM 取证）**不能**用 HTTP 代替：它证明的是「Vue 真的
 * 渲染出来了、而且渲染的是后端给的那份数据」，而 `fetch` 只证明 API 通。
 * 故它在本脚本里**真的起一个无头浏览器**，而 Plan 05A Task 4 把姿势从
 * `--dump-dom` 换成了 **CDP**（`--dump-dom` 没有任何设 cookie 的入口，
 * 于是它在 Plan 05A 之后只能取到登录页的 DOM）。逐字理由与「不引
 * Playwright/Puppeteer」的顶回见那一步上方的注释。
 * ⚠️ 三个坑（Plan 04 Task 2/3 踩过，本脚本逐个绕开）：
 *  ① 必须 `--force-prefers-reduced-motion`，否则抓到 `StatBlock` 数字滚动**中途**
 *     那一帧（Task 2 实测到 95.7 而不是 100.0）；
 *  ② PowerShell 的 `& msedge … > file` 会得到 **0 字节** → 本脚本用 Node 的
 *     `spawn` 直接收 stdout/stderr，不经过 shell 重定向；
 *  ③ vite 只绑 `::1` → 基址是 `localhost`。
 *
 * ⚠️ **第 15 步不需要后端也不需要前端**：它 `spawn` 两个静态守卫
 * （`check-tokens.mjs` 色值唯一住址 + `check-dist.mjs` 生产构建里没有 `adoptFromUrl`）。
 * 把它们挂在这里的理由是「`npm run smoke` 全绿」应当**蕴含**「设计令牌没有散开」
 * 与「开发工具没有漏进生产」，而两者也都可以单独跑。
 *
 * ⚠️ **第 16 步是 Plan 05A Task 4 新增的**（派单逐字点名的「第 17 步」= 0 起的第 16 个）：
 * 前 15 步用会话当**载体**验业务规则，第 16 步验**载体本身**
 * （未绑定 → 绑定四档 → 登录 → me → 登出 → 旧 cookie 401 → subject 被删 → 401，
 * 外加三档授权）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 第 17 步的**前置条件与耗时**（Plan 06 Task 13 / D8 写清；Task 11 登记的两条）
 * ---------------------------------------------------------------------------
 * 第 17 步是终审 fix 波新增的**结构面守卫**，今天 **10** 条（① demo.ps1 强制关掉身份头
 * 开关 / ② `toPlainText`（⚠️ 含 Plan 07 Task 8 按终审 S4-15 加的 ②′/②′′/②′′′ 三拍）
 * / ③ `surface` 字面值 / ④ 破折号的唯一住址 / ⑤ `serve.ps1`
 * 也强制关（B3）/ ⑥ router 的静态段必须排在 `:resource` 之前（B5）/ ⑦ 单页取值不许
 * 静默截断（B4）/ ⑧ 会话恢复那一帧的结构面（C3）/ ⑨ 试用告示的唯一住址与
 * 「读不到就不挂」（Plan 07 Task 1）/ ⑩ 原生校验拦下 submit 时不许静默 + `step` 的
 * 口径不许被前端发明第二次（Plan 07 Task 5b）。
 * ⚠️ 改前这一段逐字写着「今天 **9** 条」而只列到 ⑨ —— ⑩ 是 Task 5b 加的、这一份
 * 目录没跟着改，而 `step(17, …)` 的**标题**那时已经写着「10 条」⇒ 同一件事两个
 * 所有者、其中一个过期（终审 **F6** 的同族；本波顺手改对，并把 ⑩ 补进下面那两格
 * 「要不要后端起着」的口径里 —— 它只读源码）。它**不需要浏览器**，
 * 而「不需要后端起着」那半句**只对 ①–⑥、⑨ 与 ⑩ 成立**：
 *
 * | 拍 | 要什么起着 | 墙钟（⚠️ 本机 2026-10-15 实测；Task 11 那一波量到的值并列在后面） |
 * |---|---|---|
 * | ① | **PowerShell + Python**（spawn 一次 `backend/scripts/demo.ps1 -DryRun`；库与 CSV 都落在 `$env:TEMP`、跑完自己删，故它不脏演示库、也不碰两个禁区） | **5.2 s**（Task 11 量到约 15 s） |
 * | ②③④⑥⑧⑨⑩ | 只要文件系统（读源码） | < 1 s |
 * | ⑤ | **PowerShell + Python**（spawn 一次 `scripts/serve.ps1 -SkipBuild`，⚠️ 而端口是**先用一个 `net.Server` 占住**再交给 `-Port` 的，于是它停在 ③d 那一道端口预检、**一个 uvicorn 都不起**；那一次里 `serve.ps1` 自己又 spawn 两次 `python -c`） | **2.7 s**（Task 11 量到 3–5 s） |
 * | ⑦ | **后端起着**（③④ 两拍打真端点：`limit=200` 与 `limit=1` 各一遍） | 约 1 s |
 *
 * ⚠️ 于是 ①+⑤ 那两次「spawn 一个 PowerShell 脚本」是本脚本墙钟里最大的一块可省成本，
 * 而它的**绝对值随机器漂**：Task 11 量到 18–20 s / 全跑 ~30 s（≈ 一半），
 * 本波在同一台机器上量到 **7.9 s / 32.1 s ≈ 1/4**。⚠️ 故这里**只钉口径、不钉数**：
 * 比例 = 那两次 spawn 的墙钟 ÷ 全跑墙钟，要报就当场量（`Measure-Command`）。
 * ⚠️⚠️ **控制者裁定：这两拍刻意不拆成单独的 npm script** —— 拆开就会在日常跑里被忘掉
 * （`npm run smoke` 绿了、而那两条守卫静默失效），故它们**留在第 17 步里**、
 * 让「smoke 全绿」永远蕴含它们。⚠️ 这一取舍的账写在 spec §13.11.4
 * （「结构面守卫吃掉 smoke 墙钟的约 1/4，这是有意的取舍」）。
 */
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/* ==========================================================================
   口径常量（⚠️ 每一个都有出处，改它之前先去读那一处）
   ========================================================================== */

const API = process.env.PE_API_BASE ?? 'http://127.0.0.1:8000'
const WEB = process.env.PE_WEB_BASE ?? 'http://localhost:5173'
const TRANSCRIPT = process.env.PE_SMOKE_TRANSCRIPT ?? ''

/** ⚠️⚠️ **本脚本跑在哪一档**（Plan 07 Task 1 加的第三档）。
 *
 *  两档 → 三档：**dev 档**（后端 8000 + vite 5174）、**产品档**（`scripts/serve.ps1`
 *  同源）、**试用档**（`scripts/trial.ps1` = 产品档 + `PE_TRIAL=1` + `backend/pe_trial.db`）。
 *
 *  ⚠️ **期望侧刻意取自本进程的环境变量，而不是取自被测的那个后端**：
 *  第 14 步要断言「16 条路由上**有没有**那条试用告示」，而告示是 `App.vue` 按
 *  `GET /api/health` 的 `trial` 一格渲染的。若期望侧也去读那一次 HTTP 响应，
 *  两侧就**同源**了 —— 后端把 `trial` 答错（例如开发档上答 `true`）时，
 *  期望侧会跟着错，于是「告示泄漏到别的档」这一档**恒绿**。
 *  故跑第三档的人要**同时**给本脚本设 `PE_TRIAL=1`：
 *  期望侧 = 环境变量、被测侧 = HTTP + 渲染出来的 DOM，三侧两两不同源。
 *
 *  ⚠️ 失效方向是**响亮**的：忘了设（或设了而后端没设）⇒ 第 1 步那一拍当场红，
 *  而不是安静地少测一档。 */
const TRIAL_EXPECTED = (process.env.PE_TRIAL ?? '').trim() === '1'

/** **cookie 的 `Secure` 在不在**（Plan 07 Task 3 的公网档）。
 *
 *  判据的**所有者是后端**：`app/auth/sessions.py` 的 `cookie_secure()` 按
 *  `app/deploy.py` 的档位答（`prod` → 带、`dev` → 不带）。本脚本刻意**不去问**它
 *  （那会与被测侧同源），而是照 `TRIAL_EXPECTED` 的同一条姿势由**跑的人声明**：
 *  · 另外三档（dev / 产品 / 试用）一律 `PE_ENV` 未设 = dev ⇒ **不设**本变量；
 *  · 公网档跑 `PE_ENV=prod`（隧道边缘是 HTTPS，故 `Secure` 成立）⇒ 设 `PE_COOKIE_SECURE=1`。
 *
 *  ⚠️ 两个方向的失效都**响亮**（硬规矩 #92：这不是放宽判据）：
 *  在 prod 上忘了设 ⇒ 第 16 步 ⑦ 那一拍红（本波首跑实测：18 步 / 710 绿 / **1 红** /
 *  199 s，红的原文是「cookie **不带** Secure」而响应头里**有** `; Secure`）；
 *  在 dev 上多设了 ⇒ 同一拍同样红。 */
const COOKIE_SECURE_EXPECTED = (process.env.PE_COOKIE_SECURE ?? '').trim() === '1'

/** **演示库的业务日**（学期第 6 周的周日）。⚠️ 唯一所有者是
 *  `backend/scripts/demo_bootstrap.py` 的 `DEMO_AS_OF`。用「今天」当 `as_of`
 *  会让训练单与周报全空（周报只在周日生成）。 */
const AS_OF = '2025-10-12'
/** 教师身份（3 个之一：T0001 陈国华 / T0002 林慧敏 / T0003 赵志刚）。
 *  ⚠️ **`role='teacher'`（普通教师）**：本脚本用它验**任教范围闸门**
 *  （`require_teaches_student` / `require_teaches_section`），而管理员会**越过**那道闸门
 *  （计划 §3.6 第 2 条），故拿管理员验它会得到一片假绿。 */
const TEACHER = 'T0001'
/** **管理员**工号（`role='admin'`）。⚠️ 唯一所有者是 `backend/scripts/demo_bootstrap.py`
 *  的 `DEMO_ADMIN_STAFF_NO`（它在 `[6/7]` 那一步把 T0003 提成管理员并打印出来）。
 *  本脚本用它验**管理台的 26 个写入操作**（Plan 05A Task 2 之后仅管理员）。
 *  ⚠️ 派单举的例子是「例如 T0001」，实现者换成了 T0003 —— 理由逐字写在
 *  `DEMO_ADMIN_STAFF_NO` 的注释里（把 T0001 提成管理员会让第 7 步那两拍
 *  「不任教 → 403」变成 200，那是假绿）。 */
const ADMIN = 'T0003'
/** **演示口令**。⚠️ 唯一所有者是 `backend/scripts/demo_bootstrap.py` 的 `DEMO_PASSWORD`
 *  （`demo.ps1` 跑完会把它打印出来，spec §13 也记着它）。本脚本抄一份字面量在这里
 *  是有意的第二所有者 —— 它是一个**联调脚本的输入**，而不是一个要被派生的值；
 *  两处不一致时第 0 步的登录会当场 401（响亮，不静默）。 */
const DEMO_PASSWORD = 'pe-demo-2025'
/** 学生身份。⚠️ 用 4 而不是 1：学生 1 的未读消息 / 勋章 / 待交快评全空
 *  （Plan 04 Task 2 的取证主身份就是它）。 */
const STUDENT = 4
/** 第 2 步建的那节课落在这一天 —— ⚠️ **不能**用 `AS_OF`：
 *  演示库的 8 节课已经占着 `2025-10-12` 前后的日子，而
 *  `(course_section_id, session_date, period)` 是唯一键，撞了是 409。 */
const NEW_SESSION_DATE = '2025-10-13'
/** 第 6 步打卡落在这一天。⚠️ 同理：`training_log` 是 840 行 = 60 人 × 14 天，
 *  演示区间里每一天每个人都已经有一行了，`(student_id, log_date)` 唯一 → 409。 */
const NEW_LOG_DATE = '2025-10-13'

/* ==========================================================================
   ⚠️⚠️ cookie jar（Plan 05A Task 4：16 步全部改成「先登录」的姿势）
   ==========================================================================
   Node 的 `fetch`（undici）**默认不存 cookie**：`Set-Cookie` 只是响应头上的一个串，
   下一个请求不会自动带上它。而 Plan 05A 之后身份**只**走 `pe_session` cookie
   （`PE_ALLOW_HEADER_IDENTITY` 的生产缺省是 `"0"`，且 Task 5 会把 `demo.ps1` 里
   那个过渡态的 `=1` 撤掉），故本脚本必须自己维护一个 jar。

   ⚠️ **不引 `undici` 的 `CookieJar`**（派单允许顶回）：那是一个新依赖，
   而本脚本要的事只有三件 —— ① 从 `Set-Cookie` 里取出 `pe_session=…` ②
   在后续请求上把它作为 `Cookie` 发出去 ③ 按「身份名」分开存。
   三件加起来不到 40 行，而本仓前端至今**零新增依赖**（Plan 01–05A 全程），
   为一个 jar 破这个例不值。⚠️ 而 Playwright/Puppeteer 那一格也**没有引入**
   （第 14 步改用 CDP + Node 24 自带的 `WebSocket`，逐字理由见那一步的注释）。 */

/** 身份名 → 那一份 cookie 串（`pe_session=…`，即 `Cookie` 头的原文）。 */
const JARS = new Map()

/** 学生身份的 jar 名。⚠️ 用**代理键**当后缀（`student:4`）而不是学号：
 *  本脚本的 13 个断言一律以 `student.id` 为主语（URL 里的 `{student_id}` 就是它），
 *  而学号要额外查一次名册才知道 —— 让 jar 名与断言用同一个键，少一次间接。 */
const studentJar = (id = STUDENT) => `student:${id}`

/** 教职身份的 jar 名 → 登录用的 `kind` + `login`。 */
const STAFF_JARS = {
  teacher: { kind: 'teacher', login: TEACHER },
  admin: { kind: 'teacher', login: ADMIN },
}

/** 学号名册（`student.id` → `student.student_no`），懒加载一次。
 *  ⚠️ 登录要的是**学号**（`POST /api/auth/login` 的 `login` 那一格），
 *  而本脚本的断言一律用**代理键**，故需要这一张对照表。 */
let STUDENT_NOS = null

async function studentNoOf(id) {
  if (STUDENT_NOS === null) {
    // ⚠️ 用**教师**会话读名册：Plan 05A Task 5 把 `GET /api/students` 改成了要教职身份
    //    （那一份列表含 `birth`，而 `birth` 正是学生绑定口令的验身材料）。
    const page = await req('GET', '/api/students?limit=200', { as: 'teacher', quiet: true, record: false })
    STUDENT_NOS = new Map((page.json?.items ?? []).map((s) => [s.id, s.student_no]))
  }
  const no = STUDENT_NOS.get(id)
  if (no === undefined) throw new Error(`名册里没有 student.id=${id}（jar 登不进去）`)
  return no
}

/** 从响应头里取出 `pe_session=…`。⚠️ 用 `getSetCookie()`（undici 给的多值取法）：
 *  `headers.get('set-cookie')` 在**多个** `Set-Cookie` 头时会用 `", "` 把它们拼成一串，
 *  而 cookie 的 `Expires` 值里就有一个逗号（`Mon, 12 Oct 2026 …`），
 *  按逗号切会切坏。本仓今天每次只设一个 cookie，但登出那一发是
 *  `pe_session=""; expires=Thu, 01 Jan 1970 …`，故这一格是**真的**会被踩到的。 */
function cookieFrom(res) {
  const all = typeof res.headers.getSetCookie === 'function'
    ? res.headers.getSetCookie()
    : [res.headers.get('set-cookie')].filter(Boolean)
  for (const raw of all) {
    const pair = String(raw).split(';')[0].trim()
    if (pair.startsWith('pe_session=') && pair.length > 'pe_session='.length) return pair
  }
  return null
}

/** 打一次登录、把那一份 cookie 存进 jar，并返回它。 */
async function loginJar(name) {
  let cred = STAFF_JARS[name]
  if (cred === undefined) {
    const m = /^student:(\d+)$/.exec(name)
    if (m === null) throw new Error(`不认识的 jar 名 ${JSON.stringify(name)}`)
    cred = { kind: 'student', login: await studentNoOf(Number(m[1])) }
  }
  const res = await req('POST', '/api/auth/login', {
    body: { kind: cred.kind, login: cred.login, password: DEMO_PASSWORD },
    quiet: true,
  })
  if (res.status !== 200) {
    throw new Error(
      `登录失败（${name} = ${cred.kind}/${cred.login}）：${res.status} ${codeOf(res)} —— ` +
      `演示口令是 ${JSON.stringify(DEMO_PASSWORD)}，而演示库由 backend/scripts/demo_bootstrap.py 的 [6/7] 那一步绑定。` +
      `⚠️ 403 password_not_bound 意味着你跑的不是刚重灌的演示库（请先重跑 demo.ps1）`,
    )
  }
  const cookie = cookieFrom(res)
  if (cookie === null) throw new Error(`登录 ${name} 成功（200）而响应里没有 Set-Cookie: pe_session=…`)
  JARS.set(name, cookie)
  out(`    🔑 已登录 ${name}（${cred.kind} ${cred.login}）→ ${cookie.slice(0, 22)}…（${cookie.length} 字符）`)
  return cookie
}

/** 取一个 jar（缺就先登录）。⚠️ **懒登录**：16 个步骤里每一步只写 `as: 'teacher'`，
 *  「谁先登录」这件事由第一次用到它的那一步决定，不必在开头排一个登录顺序。 */
async function ensureJar(name) {
  if (!JARS.has(name)) await loginJar(name)
  return JARS.get(name)
}

/* ==========================================================================
   断言与打印
   ========================================================================== */

const STEPS = []
let CURRENT = null
let PASSED = 0
let FAILED = 0

function out(line = '') {
  process.stdout.write(line + '\n')
}

/** 一条断言。⚠️ **不抛**：一步里的一条红了不该把后面 14 步一起带走
 *  （那会让「哪几处对接不上」变成一件要跑 15 次才知道的事）。 */
function check(label, ok, detail = '') {
  const pass = ok === true
  if (pass) PASSED += 1
  else FAILED += 1
  CURRENT.checks.push({ label, ok: pass, detail: String(detail) })
  out(`    ${pass ? '✓' : '✗'} ${label}${detail === '' ? '' : `  →  ${detail}`}`)
  return pass
}

/** 相等断言（打出来的 detail 是两边的值，红了不用再去猜）。 */
function eq(label, actual, expected) {
  return check(label, actual === expected, `actual=${fmt(actual)} expected=${fmt(expected)}`)
}

function fmt(value) {
  if (typeof value === 'string') return value.length > 200 ? `${value.slice(0, 200)}…` : value
  try {
    const text = JSON.stringify(value)
    return text.length > 200 ? `${text.slice(0, 200)}…` : text
  } catch {
    return String(value)
  }
}

/* ==========================================================================
   HTML → 文本。**单一所有者**（终审 I4）
   ==========================================================================
   ⚠️⚠️ 本处此前有**两份**剥法、强度不同、而在同一个闭包里**同名**（都叫 `plain`，
   相隔 90 行）：第 14 步轮询那一份只剥标签（`.replace(/<[^>]+>/g,' ')`），
   于是**标签里的 CSS / JS 文本留着**；断言那一份先整块剥掉 style 与 script。
   dev 模式下 vite 把每个 SFC 与全局 css 都作为 style 元素注进 DOM，故一句
   **含 needle 的 CSS 注释**就能顶替真正文。终审用 node 复现过：把 `base.css` 里
   `.num--hero` 上方那句注释（「首页的本周训练量、大屏的关键指标」）连同它的选择器
   一起包进一个 style 元素，弱的那一份对 needle「的本周」得 `true`、强的那一份得 `false`。

   ⚠️ 弱的那一份当时只用在**轮询退出条件**上（不是断言，故失效方向是红不是绿），
   而它带的正是 05B 刚从断言里摘掉的那个 `|| html.includes(n)` 形状 ——
   同一屏的注释却写着「这一格把谓词的假出口**永久关掉**」。两个后果：
    ① 一个 needle 撞上 CSS 注释，轮询就在**第一拍** break，「等到渲染完」这件事失效
       → 慢页面上是**假红**，而 detail 会把真因说成「页面渲染坏了」；
    ② 两个同名不同强度的变量摆在一个闭包里，下一个人把弱的那份抄去当断言，假绿就回来。
   故两份合成下面这一个住址，**轮询与断言共用它**。守卫是第 17 步那一拍。 */

/** 整块剥掉 style 与 script（它们的**文本**不是页面正文）。 */
function stripEmbedded(html) {
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')
}

/** 剥掉 style/script 整块 → 剥掉剩下的标签 → 把空白压成单个空格。
 *  ⚠️ **needle 一律只在它的返回值里找**：不给「原文里出现」留第二个出口。
 *  ⚠️⚠️ **它反转义 HTML 实体**（Plan 07 Task 8 · 终审 **S4-15** 本波修掉；改前它刻意
 *  不反转义，那一份取舍逐字记在 spec §15 **F7**，该条本波已划掉）。断言拿到的 `html`
 *  是 `element.outerHTML`，而 HTML 的**片段序列化算法**在文本节点里只转义四个字符：
 *  `&` → `&amp;`、U+00A0 → `&nbsp;`、`<` → `&lt;`、`>` → `&gt;`（⚠️ **标签本身不转义**：
 *  `<form` 在 `outerHTML` 里逐字还在；`"` 与 `'` 只在**属性值**里转义，文本节点里原样）。
 *  改前本函数只剥标签与压空白 ⇒ 那四个实体**原样留在返回值里**，于是**含 `<` / `>` /
 *  `&` 的 needle 永远匹配不上真正文**。⚠️ 而失效方向是**有方向性的**（这一句是本格
 *  最容易被读反的地方，故逐字写出）：
 *   · **正向**断言（要 `….includes(needle)` 为真）→ 永**红**：响亮，会被发现；
 *   · **反向**断言（要 `!….includes(needle)` 为真）→ 永**绿**：**静默**，才是危险的那一档。
 *  ⚠️ **本波实测的级联面 = 0 条 needle**（决定「修 vs 登记」的那一格，探针与口径在
 *  `task-8-report.md` §2）：剥完注释之后本文件有 **137** 处字面量 needle（其中反向
 *  **19** 处），含裸 `<` / `>` / `&` 的**只有 1** 处（第 ⑩ 拍那个 `'<form'` 过滤器，
 *  ⚠️ 它的 receiver 是**源码**、不过本函数），含 `&lt;` / `&gt;` / `&amp;` / `&nbsp;`
 *  **转义形式**的 **0** 处 ⇒ 反转义**不可能**改掉任何一条既有断言的颜色：它只会
 *  **删**字符（`&gt;` 4 个 → `>` 1 个）、一个都不插，故「凭空造出一个新匹配」要求
 *  needle 里含那四个字符之一，而那一条今天不存在。⇒ 终审给的「十几条要跟着改」
 *  那一档豁免条件**不成立**，按裁定修。
 *  ⚠️ 而模板里**真的**有实体（所以本格不是纯理论）：`src/**` 实测 `&lt;` × **1**
 *  （`views/teacher/StudentDetail.vue`）、`&gt;` × **7**（`Dashboard.vue` × 4 /
 *  `RpeEntry.vue` / `AlertQueue.vue` / `ClassReport.vue` 各 1）、`&amp;` 与 `&nbsp;`
 *  各 **0** ⇒ 改前那 8 处页面上明明显示 `<` / `>`，而本函数的返回值里是
 *  `&lt;` / `&gt;`（本格修的就是它）。
 *  ⚠️ **反转义之后新长出来的那一格潜伏风险**（方向恰好反过来）：needle 若写**转义形式**
 *  （`&gt;` 一类）就永远匹配不上、而**反向**断言因此永绿 ⇒ 由下面第 ② 拍的
 *  ②′ / ②′′ / ②′′′ 钉住（②′ 禁转义形式的 needle，②′′ 是它的反空转，
 *  ②′′′ 直接打在本函数那四步上）。 */
function toPlainText(html) {
  return stripEmbedded(html)
    .replace(/<[^>]+>/g, ' ')
    // ⚠️ 四个实体、⚠️⚠️ **`&amp;` 必须最后**：否则 `&amp;lt;` 会被解两次成 `<`，
    //    凭空造出一个假标签（spec §15 F7 那一份「怎么做」逐字点明了这一格）。
    //    ⚠️ 也必须在**剥标签之后**：先解 `&lt;` 再剥标签会把正文里的 `<` 当成标签吃掉。
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, '\u00a0')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
}

async function step(no, title, fn) {
  CURRENT = { no, title, exchanges: [], checks: [], startedAt: new Date().toISOString() }
  STEPS.push(CURRENT)
  out('')
  out('='.repeat(78))
  out(`【${no}】${title}`)
  out('='.repeat(78))
  try {
    await fn()
  } catch (err) {
    // 一步炸了（例如后端没起）：记一条红，继续下一步 —— 一次跑完才知道全貌。
    FAILED += 1
    CURRENT.checks.push({ label: '这一步没有抛异常', ok: false, detail: String(err?.stack ?? err) })
    out(`    ✗ 这一步抛了异常：${err?.message ?? err}`)
  }
  CURRENT.ok = CURRENT.checks.every((c) => c.ok)
  out(`  —— 第 ${no} 步：${CURRENT.ok ? '全绿' : '有红'}（${CURRENT.checks.filter((c) => c.ok).length}/${CURRENT.checks.length} 条断言）`)
}

/* ==========================================================================
   HTTP：本脚本唯一发请求的地方（⚠️ 每一次都记进 transcript）
   ========================================================================== */

const TRUNCATE = 1400

/**
 * @param {object} opts
 * @param {object} [opts.body]     JSON 请求体（给了就带 `Content-Type`）
 * @param {string} [opts.as]       **用哪一个 jar**（`'teacher'` / `'admin'` / `'student:4'`）。
 *                                 缺省 = 匿名。⚠️ jar 不在就**当场登录一次**（懒登录）。
 * @param {string} [opts.cookie]   绕过 jar、直接给一份 `Cookie` 头的原文。
 *                                 ⚠️ 只给第 16 步用（「登出之后**旧** cookie 还在不在效」
 *                                 那一拍要发的正是一个 jar 里已经不存在的串）。
 * @param {object} [opts.headers]  额外的头。⚠️ **不要**用它传身份：Plan 05A 之后
 *                                 身份走 cookie，而 `PE_ALLOW_HEADER_IDENTITY` 的
 *                                 过渡态在 Task 5 被撤掉，一个请求头身份在生产档下
 *                                 会被后端**完全忽略**（于是「绿」变成假绿）。
 * @param {boolean} [opts.record]  缺省 true；`/openapi.json` 那种 278 KB 的响应传 false
 * @param {boolean} [opts.quiet]   不把响应体打到 stdout（transcript 里仍然全量）
 */
async function req(method, urlPath, opts = {}) {
  const url = urlPath.startsWith('http') ? urlPath : API + urlPath
  const headers = { Accept: 'application/json', ...(opts.headers ?? {}) }
  // ⚠️ cookie 的两个来源：显式给的（第 16 步的旧 cookie）优先于 jar。
  const cookie = opts.cookie ?? (opts.as ? await ensureJar(opts.as) : null)
  if (cookie) headers.Cookie = cookie
  const init = { method, headers }
  if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(opts.body)
  }
  const res = await fetch(url, init)
  const text = await res.text()
  let json = null
  try {
    json = text === '' ? null : JSON.parse(text)
  } catch {
    json = null // 不是 JSON（例如 405 的 HTML）：只留原文
  }

  const record = {
    method,
    url,
    // ⚠️ **cookie 一律掩掉**（只留前 22 个字符）：它是一个活的会话令牌，
    //    而 `PE_SMOKE_TRANSCRIPT` 会把本对象整份写进一个**入库**的取证文档
    //    （`Document/2026-10-11-前后端联调取证.md` 就是这么生成的）。
    //    把令牌写进 git 等于把「谁都能当这个管理员」也写进 git。
    requestHeaders: { ...headers, ...(cookie ? { Cookie: `${cookie.slice(0, 22)}…（已掩）` } : {}) },
    as: opts.as ?? (cookie ? '(显式 cookie)' : null),
    requestBody: opts.body ?? null,
    status: res.status,
    responseBodyBytes: Buffer.byteLength(text, 'utf8'),
    responseBody: opts.record === false ? `__omitted__ (${Buffer.byteLength(text, 'utf8')} bytes)` : text,
  }
  if (CURRENT !== null) CURRENT.exchanges.push(record)

  out(`  → ${method} ${url}`)
  out(`    身份: ${opts.as ?? (cookie ? '(显式 cookie)' : '（匿名）')}`)
  if (opts.body !== undefined) {
    // ⚠️ 口令在 stdout 上也掩掉：`demo.ps1` 的输出会被贴进报告与聊天窗口。
    const shown = { ...opts.body }
    if (typeof shown.password === 'string') shown.password = '***（演示口令，见 demo.ps1 的输出）'
    out(`    请求体: ${JSON.stringify(shown)}`)
  }
  out(`  ← ${res.status} ${res.statusText}  (${record.responseBodyBytes} bytes)`)
  if (!opts.quiet) {
    const shown = text.length > TRUNCATE ? `${text.slice(0, TRUNCATE)}…（截断，全文在 transcript 里）` : text
    out(`    ${shown === '' ? '(空响应体)' : shown}`)
  }
  return { status: res.status, text, json, headers: res.headers }
}

/** 后端统一错误体里的 `code`。⚠️ 一律按 code 断言，不按 message
 *  （message 是给人看的中文，会变；约束第 8 条）。 */
function codeOf(res) {
  return res.json?.error?.code ?? null
}
function messageOf(res) {
  return res.json?.error?.message ?? null
}

/* ==========================================================================
   第 0 步要用的：演示库复原核实
   ========================================================================== */

/** 一个泛型 list 端点的 `total`（⚠️ 信封是 4 个键：items/limit/offset/total）。
 *  @param {string} [as] jar 名。⚠️ **安全收紧波起 16 个资源要身份**：
 *  13 个学生键资源（`read_scope="staff_taught"`：匿名 401 / 学生只读自己的 /
 *  **教师只读自己任教班级的学生行** / 管理员全读）+ 3 个仅教职
 *  （`students` / `teachers` / `weekly-class-reports`）。
 *  ⚠️⚠️ **Plan 06 Task 8 之后「教职那一档是全读」这句话只对 `staff` 那 3 个成立**：
 *  那 13 个学生键资源的教师档是**按任教范围收窄**的，故要数**全表**行数一律传
 *  `'admin'`（管理员越过任教范围）。⚠️ 若传一个学生 jar，`total` 会变成
 *  「**我的**行数」（后端让 `total` 与 `items` 走同一个 `WHERE`，那是
 *  `app/api/crud.py::_list_page` 的口径），下面那张表的期望值就全错了。
 *  ⚠️ 只有 7 个参考数据资源仍匿名（`semesters` / `course-sections` /
 *  `fitness-test-batches` / `percentile-snapshots` / `exercises` /
 *  `prescription-templates` / `class-sessions`），本表里一个都没有。 */
async function totalOf(resource, as) {
  const res = await req('GET', `/api/${resource}?limit=1`, { as, quiet: true })
  return res.json?.total ?? null
}

/* ==========================================================================
   18 步（0–17）
   ========================================================================== */

const SHARED = {}

/* ⚠️ **开头就打印一次**（Plan 04 收尾波加的）：本脚本会写脏演示库，而「跑完才警告」
   等于没警告 —— 那 5 样写入里有一样（第 10 步建的学期）是**删不掉的**，
   `semesters` 是 `on_delete="forbid"`、后端根本不注册 DELETE 端点，打过去是 405。
   完整交代见文件头「它是**一次性**的」那一节。 */
out('')
out('⚠️⚠️ 本脚本会**写脏演示库**（建一节课 / 交一条快评 / 打一次卡 / 处置一条预警 /')
out('    建一个**删不掉**的学期）。跑完请重跑 backend\\scripts\\demo.ps1 再跑第二次；')
out('    第 0 步核实的就是「一个刚复原的演示库」的行数，脏库上它会红。')

await step(0, '登录三种角色 + 演示库复原核实（⚠️ 跑本脚本之前一律先重跑 backend/scripts/demo.ps1）', async () => {
  /* ---------------------------------------------------- ⓪ 三种角色各登录一次
     ⚠️ **本步是「16 步全部改成先登录的姿势」的入口**（Plan 05A Task 4）：
     后面每一步只写 `as: 'teacher'` / `as: 'admin'` / `as: studentJar(4)`，
     而 jar 是**懒登录**的（`ensureJar`）。这里先把三个都建出来，理由有两条：
      1. 「演示库上到底有没有人能登录」是**最先**要知道的事 —— 若 `[6/7]` 那一步
         没跑（例如用了一个旧的 pe_demo.db），失败要落在第 0 步的一句人话上，
         而不是散在后面 16 步的 401 里；
      2. 后面每一步都依赖它，而懒登录会在**第一次用到**的那一步打印一行 🔑，
         于是「哪一步偷偷换了一个身份」在 stdout 上是看得见的。               */
  for (const name of ['teacher', 'admin', studentJar(STUDENT)]) {
    const cookie = await ensureJar(name)
    check(`${name} 登录拿到了 pe_session cookie（64 字符的不透明 id）`,
      /^pe_session=[A-Za-z0-9_-]{64}$/.test(cookie), `${cookie.length} 字符`)
  }
  const meAsAdmin = await req('GET', '/api/auth/me', { as: 'admin', quiet: true })
  eq('管理员的 GET /api/auth/me → 200', meAsAdmin.status, 200)
  eq('而它的 role 确实是 admin（管理台那 26 个写入操作的判据）', meAsAdmin.json?.role, 'admin')
  eq('它的 staff_no 与 DEMO_ADMIN_STAFF_NO 逐字相同', meAsAdmin.json?.staff_no, ADMIN)
  const meAsTeacher = await req('GET', '/api/auth/me', { as: 'teacher', quiet: true })
  eq('普通教师的 role 是 teacher（**不是** admin）', meAsTeacher.json?.role, 'teacher')

  // ⚠️ **8 个资源**的行数 = demo_bootstrap.py 第 [7/7] 步「全部从库里数出来」的那一份。
  //    ⚠️⚠️ 本处此前逐字写的是「**7** 张表」（交付前收尾波 ④ 改的）：实测下面那个
  //    对象字面量有 **8** 个键（`students` / `teachers` / `notifications` /
  //    `prescriptions` / `training-logs` / `rpe-records` / `weekly-class-reports` /
  //    `alerts`），而紧跟在后面的那句注释自己就写着「**8** 个里的 6 个从 `undefined`
  //    改成 `'teacher'`」—— 同一个对象上两个数打架，而错的是这一句。
  //    ⚠️ 顺带把「张表」换成「个资源」：本行数的是 **HTTP 面**的 `total`
  //    （`GET /api/<资源>?limit=1`），不是 `sqlite_master` 里的表 —— 那一份是 28 张
  //    （⚠️ Plan 06 Task 5 起；`sqlite_master` 里还会多一张 `alembic_version`，故磁盘库上
  //    `SELECT count(*) FROM sqlite_master WHERE type='table'` 实测是 **29**），
  //    由第 1 步的 `GET /api/health` 钉（两种口径以运行时为准，硬规矩 #103）。
  const expected = {
    // ⚠️⚠️ **安全收紧波：8 个里的 6 个从 `undefined`（匿名）改成 `'teacher'`**。
    //    本表里**没有一个**资源仍然匿名可读：`students` / `teachers` 自 Plan 05A
    //    Task 5 起要教职身份（那两份列表含 `birth` / `name`，正是绑定口令的验身材料），
    //    而 `notifications` / `prescriptions` / `training-logs` / `rpe-records` /
    //    `weekly-class-reports` / `alerts` 六个自本波起也要身份
    //    （前五个是学生键、最后一个是「班级键但 `progress_board` 里逐条带 `student_id`」）。
    // ⚠️⚠️ **Plan 06 Task 8：那 5 个学生键资源改用 `'admin'`，判据（行数）一个字没改**。
    //    理由是它们的 `read_scope` 从 `student_self`（教职全读）改成了 `staff_taught`
    //    （**教师只读自己本学期任教班级的学生行**），故用教师 jar 数出来的不再是全表：
    //    实测 T0001（任教 41 / 60 人）读到 `notifications` 12（全表 19）、
    //    `prescriptions` 41（60）、`training-logs` 574（840）、`rpe-records` 164（240）、
    //    `alerts` 21（32）。⚠️ 而**管理员越过任教范围**（与 `require_teaches_student`
    //    同一条口径），故 `'admin'` 那一档仍然是全表行数 —— 本表要数的正是
    //    「一个刚复原的演示库有多少行」，与「谁能读到多少」是两件事。
    //    ⚠️ 后一件事由第 12 步 ⑦ 那一拍钉（本波新加）。
    // ⚠️⚠️ **Plan 06 Task 8b：`weekly-class-reports` 也从 `'teacher'` 改成 `'admin'`，
    //    行数（5）一个字没改**。理由与上面那 5 个逐字同构：它的 `read_scope` 从
    //    `"staff"`（任何在册教职全读）改成了**第五档** `"staff_taught_section"`
    //    （`WHERE course_section_id IN (我本学期任教的班)`），故教师 jar 数出来的
    //    不再是全表 —— 实测 T0001（任教班 1 与 3）读到 **2**（全表 5）。
    //    ⚠️ 而本表要数的是「一个刚复原的演示库有多少行」，与「谁能读到多少」是
    //    两件事，故按本表既有的约定换成不被收窄的那一档（`'admin'`）而**不是**
    //    把 5 改成 2（硬规矩 #92：判据本身不许改，改的只是取数用的身份）。
    //    ⚠️ 「T0001 读到 2 / T0003 读到 5」那一格由第 12 步 **⑧** 那一拍钉（本波新加）。
    //    ⚠️ `students` / `teachers` 两个**仍然用 `'teacher'`**：它们是
    //    `read_scope="staff"`（任何在册教职全读），Task 8b 没动它们。
    students: [60, 'teacher'],
    teachers: [3, 'teacher'],
    notifications: [19, 'admin'],
    prescriptions: [60, 'admin'],
    'training-logs': [840, 'admin'],
    'rpe-records': [240, 'admin'],
    'weekly-class-reports': [5, 'admin'],
    // ⚠️ **32 而不是 30**（Plan 04 收尾波改的）：`GREEN_MASTERY` 与
    //    `RED_MINITEST_DROP` 的综合分此前读 `mini_test.normalized_score` 那一列
    //    （演示库上由 `demo_data` 灌成近似值），本波改成了与进步榜**同一个算式**
    //    现算（`app.domain.report.mini_test_scores`）→ 红牌里的小测下降从 5 条变 7 条。
    //    ⚠️ 新分布是 `demo.ps1` 重灌之后**实测**出来的（第 [7/7] 步「预警按规则」
    //    那一行逐字是 `{GREEN_MASTERY: 13, RED_MINITEST_DROP: 7,
    //    RED_RPE_SUSTAINED: 6, YELLOW_CHECKIN_GAP: 6}`），不是推出来的。
    alerts: [32, 'admin'],
  }
  for (const [resource, [want, as]] of Object.entries(expected)) {
    eq(`${resource} 的行数`, await totalOf(resource, as), want)
  }
  // ⚠️ **演示库上「人人能登录」这一格也要核实**（Plan 05A Task 4 的 `[6/7]`）。
  //    ⚠️⚠️ **安全收紧波换了核实姿势**：此前这一拍读 `password_bound_at`
  //    （`StudentRead` / `TeacherRead` 都含它，故一次 list 就能数出「谁还没绑」），
  //    而那一列本波被摘掉了（裁定 3：它等于「哪些账号还能被抢占绑定」的清单，
  //    逐字理由见 `app/api/schemas/organisation.py` 的 `TeacherRead`）。
  //    摘掉之后 HTTP 面上**没有**批量判据了 —— 那正是摘它的目的。
  //    故本拍改成**真的登录**三个演示学号（派单 §0 给的那三个）：
  //    它证明的是「能登录」本身，比读一个时间戳**更强**
  //    （时间戳在、而口令哈希坏了也会绿）。
  //    ⚠️ 三个学号走 `ensureJar` 的懒登录，于是「学号 → 代理键」那张对照表
  //    （`studentNoOf`）也顺带被核实了一次（它读的是要教职身份的 `/api/students`）。
  for (const id of [4, 5, 1]) {
    const cookie = await ensureJar(studentJar(id))
    check(`学生 ${id} 能登录（演示口令对全部在册学生有效）`,
      /^pe_session=[A-Za-z0-9_-]{64}$/.test(cookie), `${cookie.length} 字符`)
  }
  const teacherRoster = await req('GET', '/api/teachers?limit=50', { as: 'teacher', quiet: true })
  const admins = (teacherRoster.json?.items ?? []).filter((t) => t.role === 'admin').map((t) => t.staff_no)
  eq('恰好 1 个管理员', admins.length, 1)
  eq('而它就是 DEMO_ADMIN_STAFF_NO', admins[0], ADMIN)
  // ⚠️⚠️ **Plan 06 Task 8 把这一发的身份从教师换成了管理员**，而**判据一个字都没改**
  //    （仍然是「32 条 / 13 红 / 13 GREEN_MASTERY / 全 pending / 全学生级」）。
  //    理由：`alerts` 的 `read_scope` 从 `student_self`（教职全读）改成了
  //    `staff_taught`（**教师只读自己本学期任教班级的学生行**），故 T0001 实测只读到
  //    **21** 条（他的任教范围是 41 / 60 人），而本拍要的是**全校**的分布。
  //    ⚠️ 管理员越过任教范围（与 `require_teaches_student` 同一条口径），故仍是全表 32。
  //    ⚠️ 而「教师那一档读到的是收窄后的行数、且 `total` 与 `items` 同源」
  //    由第 12 步 ⑦ 那一拍钉（本波新加）。
  const alerts = await req('GET', '/api/alerts?limit=200', { as: 'admin', quiet: true })
  const rows = alerts.json?.items ?? []
  const byLevel = {}
  const byStatus = {}
  const byRule = {}
  for (const row of rows) {
    byLevel[row.level] = (byLevel[row.level] ?? 0) + 1
    byStatus[row.status] = (byStatus[row.status] ?? 0) + 1
    byRule[row.rule_id] = (byRule[row.rule_id] ?? 0) + 1
  }
  out(`    预警分布 level=${JSON.stringify(byLevel)} status=${JSON.stringify(byStatus)}`)
  out(`    预警分布 rule_id=${JSON.stringify(byRule)}`)
  eq('预警 13 红 + 13 绿 + 6 黄 = 32', rows.length, 32)
  eq('其中红色 13 条（RED_MINITEST_DROP 7 + RED_RPE_SUSTAINED 6）', byLevel.red ?? 0, 13)
  eq('其中 GREEN_MASTERY 13 条（绿牌数与改前相同，红牌那两条规则里的 5 → 7 才是变化）',
    byRule.GREEN_MASTERY ?? 0, 13)
  eq('全部 pending（刚复原的库上没有人处置过）', byStatus.pending ?? 0, 32)
  eq('预警全是学生级（course_section_id 恒为 null）',
    rows.every((r) => r.course_section_id === null && r.student_id !== null), true)
})

await step(1, 'GET /api/health → tables == 30 且 students > 0', async () => {
  const res = await req('GET', '/api/health')
  eq('200', res.status, 200)
  eq('status == ok', res.json?.status, 'ok')
  // ⚠️ **30 而不是 29**（**Plan 08 Task 4**）：新增了 `bind_token`（**一次性绑定令牌**，
  //    答「教务干事给哪一个还没绑定的账号发过一张凭据」）。⚠️ 它是**第三张**鉴权表、
  //    与 `user_session` / `login_attempt` 同住 `app/db/models/auth.py`，
  //    由**第六条**迁移 `a1af54889103` 建（迁移链 5 → **6**，仍单头）。
  // ⚠️ 改前是 **29 而不是 28**（Plan 08 Task 1）：新增了 `read_audit_log`（**敏感读**留痕，
  //    答「谁在什么时候翻过哪个学生的档案」）。⚠️ 它是**第二张**审计表、
  //    与 `audit_log` 同住 `app/db/models/audit.py`，由**第五条**迁移
  //    `03331a689ee4` 建（迁移链 4 → **5**，仍单头）。
  // ⚠️ 再改前是 **28 而不是 27**（Plan 06 Task 5）：新增了 `audit_log`（请求审计留痕）。
  //    Plan 06 Task 3 那一次是 26 → 27（+`login_attempt`，登录限流的计数存储），
  //    Plan 05A Task 1 是 25 → 26（+`user_session`）。
  //    ⚠️ 本端点是**匿名**的（Task 5 那 48 → 44 个匿名 GET 的裁定里它保持匿名：
  //    它是存活探针，回三格 `status/tables/students`，一格秘密都不含）。
  //    ⚠️⚠️ 而 **Plan 06 Task 4 之后它刻意仍然只有三格**：`PE_ENV` 的值不回给匿名
  //    （把「这是一个开发档：CORS 全开、请求头身份可用」告诉探测者，正是他要挑的目标）。
  //    ⚠️⚠️ **Plan 08 Task 4 的 `PE_ALLOW_SELF_BIND` 同样一个字都不回**
  //    （那一格是「这一台关不关自助绑定」，把它告诉匿名等于给探测者一张攻击面地图；
  //    后端那一侧的守卫是 `tests/test_main.py` 的
  //    `test_the_trial_switch_never_touches_the_openapi_document` 同族）。
  //    下面那一拍「恰好 4 个键」因此同时是**档位不泄漏**的取证；
  //    后端那一侧的守卫是 `tests/test_main.py` 的
  //    `test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller`
  //    （判据更强：dev 与 prod 两档下 `/api/health` 与 `/openapi.json` 的响应体**逐字节相同**）。
  eq('tables == 30（Plan 08 Task 1 是 29；Plan 08 Task 4 +bind_token）',
    res.json?.tables, 30)
  check('students > 0', (res.json?.students ?? 0) > 0, `students=${res.json?.students}`)
  // ⚠️ /api/health 是「24 个未定型响应」里唯一不是 list 的那一个，
  //    故它的形状由 api/types.ts 手写补上（约束第 5 条）。
  // ⚠️⚠️ **Plan 07 Task 1：3 个键 → 4 个键**（+`trial`）。⚠️ 那一格**不违反**
  //    上面「PE_ENV 的值不回给匿名」那一条：`PE_TRIAL` 与 `PE_ENV` 正交（试用档今天
  //    就是 `PE_ENV=dev` + `PE_TRIAL=1`），而它答的那件事**本来就印在每一个页面上**
  //    （`App.vue` 的那条告示），故不是秘密。后端那一侧的守卫是 `tests/test_main.py` 的
  //    `test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller`
  //    （判据更强：**同一个** `PE_TRIAL` 下，dev 与 prod 两档的响应体逐字节相同）。
  //    ⚠️ 而它是**未定型响应**（返回注解 `dict[str, object]`）⇒ 加这一格
  //    **不改 `/openapi.json` 的响应 schema 一个字节**、五格一个都不变
  //    （守卫是 `tests/test_main.py` 的 `test_the_trial_switch_never_touches_the_openapi_document`）。
  eq('响应恰好 4 个键（未定型 → 前端手写的 HealthRead；Plan 07 Task 1 加了 trial）',
    Object.keys(res.json ?? {}).sort().join(','), 'status,students,tables,trial')

  /* ⚠️⚠️ **Plan 07 Task 1 新加的三拍**（第三档 = 试用档的入口取证）。
     ① `trial` 是**布尔**：`App.vue` 判的是 `health.trial === true`，
        故后端回一个 `"1"` / `"true"` 字符串的话，告示会**静默不挂**（那一格是
        「页面上少一句真话」，而不是一个看得见的报错）；
     ② 与本进程的 `PE_TRIAL` **一致**：⚠️ 两侧不同源（环境变量 vs HTTP）；
     ③ 把这一格记进 `SHARED`，第 14 步用它当「16 条路由上该不该有告示」的期望侧之一。
     ⚠️ 三档各跑一整遍时，本步打印的那一行就是「`/api/health` 的 `trial` 在这一档
        是什么值」的**唯一**机器口径（实施计划 07 派单 §1.5 新增拍 ③）。 */
  check('trial 那一格是**布尔**（不是 "1" / "true" 一类字符串；App.vue 判的是 === true）',
    typeof res.json?.trial === 'boolean',
    `typeof=${typeof res.json?.trial} 值=${JSON.stringify(res.json?.trial)}`)
  eq(`trial 与本进程的 PE_TRIAL 一致（期望侧 ${TRIAL_EXPECTED ? '= 1（试用档）' : '未设/0（不是试用档）'}；⚠️ 两侧不同源：环境变量 vs HTTP）`,
    res.json?.trial, TRIAL_EXPECTED)
  SHARED.healthTrial = res.json?.trial === true
  SHARED.healthStudents = res.json?.students
  out(`    档位口径：PE_TRIAL=${TRIAL_EXPECTED ? '1' : '（未设）'} ⇒ /api/health 的 trial=${String(res.json?.trial)}`
    + ` ⇒ 第 14 步期望 16 条路由上${SHARED.healthTrial ? '**都挂着**' : '**都没有**'}那条试用告示`
    + `（students=${String(res.json?.students)}）`)
})

await step(2, '管理员 POST /api/class-sessions → 201 且响应里没有 rpe_token；普通教师 → 403', async () => {
  const sections = await req('GET', '/api/course-sections?limit=5', { quiet: true })
  const sectionId = sections.json.items[0].id
  SHARED.sectionId = sectionId
  /* ⚠️ **本步的身份从「教师」换成了「管理员」**（Plan 05A Task 2）：
     `class-sessions` 是 9 个可写资源之一，而用户 2026-10-12 逐字裁定
     「管理员这个角色接管管理台（23 个资源的增删改查）」，故后端 `crud.py` 的
     `require_teacher` 改成了 `require_admin` —— 一个 `role='teacher'` 的会话
     打过去是 **403 forbidden**（不是 401：它已经被认出来了，只是不够）。
     ⚠️ 于是本步是**三拍**（与后端 `test_every_writable_resource_admits_only_an_admin_mutation`
     同形）：匿名 401 / 普通教师 403 / 管理员 201。                             */
  const res = await req('POST', '/api/class-sessions', {
    as: 'admin',
    body: { course_section_id: sectionId, session_date: NEW_SESSION_DATE, period: 5, rpe_opened: false },
  })
  eq('201', res.status, 201)
  SHARED.sessionId = res.json?.id ?? null
  check('拿到了 id', Number.isInteger(SHARED.sessionId), `id=${SHARED.sessionId}`)
  // ⚠️ 这一拍是 Plan 03 收尾 fix 波 2 的口径：`ClassSessionRead` 是 6 列，
  //    rpe_token 已从读模型上摘掉（本仓第一个与 DB 列不逐字对齐的 *Read）。
  check('响应里**没有** rpe_token', !('rpe_token' in (res.json ?? {})),
    `键集合=${Object.keys(res.json ?? {}).sort().join(',')}`)
  eq('响应恰好 6 个键', Object.keys(res.json ?? {}).length, 6)
  eq('rpe_opened 是 false（还没发起快评）', res.json?.rpe_opened, false)

  // 匿名写 → 401（fix 波 1 给 9 个可写资源的写入侧全挂上了身份闸门）
  const anon = await req('POST', '/api/class-sessions', {
    body: { course_section_id: sectionId, session_date: NEW_SESSION_DATE, period: 6 },
  })
  eq('匿名 POST → 401', anon.status, 401)
  eq('匿名 POST 的 code 是 unauthenticated', codeOf(anon), 'unauthenticated')

  // 普通教师写 → 403（Plan 05A Task 2 新增的那一拍）
  const asTeacher = await req('POST', '/api/class-sessions', {
    as: 'teacher',
    body: { course_section_id: sectionId, session_date: NEW_SESSION_DATE, period: 6 },
  })
  eq('**普通教师** POST → 403（管理台的写入侧仅 role=admin）', asTeacher.status, 403)
  eq('那一档的 code 是 forbidden（不是 unauthenticated：它已经被认出来了）',
    codeOf(asTeacher), 'forbidden')
  check('message 里点名了 role 的当前值（前端要能翻成一句人话）',
    typeof messageOf(asTeacher) === 'string' && messageOf(asTeacher).includes('teacher'),
    `message=${messageOf(asTeacher)}`)
})

await step(3, '教师头 open-rpe 拿到口令；匿名 GET /api/class-sessions 的响应体里不含那串口令', async () => {
  const res = await req('POST', `/api/class-sessions/${SHARED.sessionId}/open-rpe`, {
    as: 'teacher',
    body: {},
  })
  eq('200', res.status, 200)
  SHARED.token = res.json?.rpe_token ?? null
  check('拿到了口令（非空串）', typeof SHARED.token === 'string' && SHARED.token.length > 0,
    `rpe_token=${SHARED.token}`)
  eq('already_open == false（第一次发起）', res.json?.already_open, false)
  eq('rpe_opened == true', res.json?.rpe_opened, true)

  // ⚠️ 这一拍是 fix 波 2「顶回 1」抓到的那个洞的**回归守卫**：
  //    光把 rpe_token 从 ClassSessionRead 上摘掉堵不住泛型 list（list 不走
  //    response_model），另一半是 catalog.RESOURCES 里那唯一一行 list_exclude。
  const list = await req('GET', '/api/class-sessions?limit=200', { quiet: true })
  eq('匿名 list → 200', list.status, 200)
  check('匿名 list 的**整份响应体原文**里不含那串口令', !list.text.includes(SHARED.token),
    `口令=${SHARED.token}，响应 ${list.text.length} 字符`)
  const mine = (list.json?.items ?? []).find((r) => r.id === SHARED.sessionId)
  check('那一节课在 list 里', mine !== undefined, `id=${SHARED.sessionId}`)
  eq('而它的键集合里没有 rpe_token（6 个键）', Object.keys(mine ?? {}).length, 6)
  check('list 项不含 rpe_token', !('rpe_token' in (mine ?? {})),
    `键集合=${Object.keys(mine ?? {}).sort().join(',')}`)
})

await step(4, '匿名读口令 → 401；教师头读 → 200 且口令与第 3 步逐字相同', async () => {
  const anon = await req('GET', `/api/class-sessions/${SHARED.sessionId}/rpe-token`)
  eq('匿名 → 401', anon.status, 401)
  eq('匿名的 code 是 unauthenticated', codeOf(anon), 'unauthenticated')

  const asTeacher = await req('GET', `/api/class-sessions/${SHARED.sessionId}/rpe-token`, {
    as: 'teacher',
  })
  eq('教师头 → 200', asTeacher.status, 200)
  eq('口令与第 3 步逐字相同（open-rpe 不重新生成）', asTeacher.json?.rpe_token, SHARED.token)
  eq('响应恰好 2 个键', Object.keys(asTeacher.json ?? {}).sort().join(','), 'class_session_id,rpe_token')

  // ⚠️ 约束第 16 条：没发起过快评的课次读口令是 **409 rpe_not_opened**（不是 404、不是 null）
  // ⚠️ 建这节课要**管理员**（Plan 05A Task 2：泛型 CRUD 的写入侧仅 role=admin）。
  const fresh = await req('POST', '/api/class-sessions', {
    as: 'admin',
    body: { course_section_id: SHARED.sectionId, session_date: NEW_SESSION_DATE, period: 7 },
  })
  SHARED.unopenedSessionId = fresh.json?.id ?? null
  const notOpened = await req('GET', `/api/class-sessions/${SHARED.unopenedSessionId}/rpe-token`, {
    as: 'teacher',
  })
  eq('未发起的课次读口令 → 409', notOpened.status, 409)
  eq('那一档的 code 是 rpe_not_opened', codeOf(notOpened), 'rpe_not_opened')
})

await step(5, '学生头 POST /api/rpe-records（带第 3 步的口令）→ 201；再交一次 → 409 integrity_conflict', async () => {
  const res = await req('POST', '/api/rpe-records', {
    as: studentJar(),
    body: { class_session_id: SHARED.sessionId, rpe: 8, rpe_token: SHARED.token },
  })
  eq('201', res.status, 201)
  eq('student_id 由服务端从请求头填（不是请求体）', res.json?.student_id, STUDENT)
  check('submitted_at 由服务端填（请求体里没送、响应里有）',
    typeof res.json?.submitted_at === 'string', `submitted_at=${res.json?.submitted_at}`)
  eq('elapsed_seconds 没送就是 null（可空、无缺省）', res.json?.elapsed_seconds, null)
  eq('rpe 逐字回显', res.json?.rpe, 8)

  // ⚠️ 顶回：计划原文写的是「403 rpe_already_submitted」。**那个 code 不存在**：
  //    同一节课交第二次撞 DB 的 uq_rpe_record_session_student，
  //    由全局 IntegrityError 处理器折成 409 integrity_conflict。
  const again = await req('POST', '/api/rpe-records', {
    as: studentJar(),
    body: { class_session_id: SHARED.sessionId, rpe: 9, rpe_token: SHARED.token },
  })
  eq('再交一次 → 409', again.status, 409)
  eq('code 是 integrity_conflict（不是 rpe_already_submitted）', codeOf(again), 'integrity_conflict')

  // 口令错了是 403 invalid_rpe_token（⚠️ 与「没发起」那一档不同码）
  const wrongToken = await req('POST', '/api/rpe-records', {
    as: studentJar(5),
    body: { class_session_id: SHARED.sessionId, rpe: 6, rpe_token: 'not-the-real-token' },
  })
  eq('口令错 → 403', wrongToken.status, 403)
  eq('code 是 invalid_rpe_token', codeOf(wrongToken), 'invalid_rpe_token')
})

await step(6, '学生头 POST /api/training-logs → 201 且 submitted_at / late / source / batch_id 都是服务端填的', async () => {
  const body = { log_date: NEW_LOG_DATE, completed: true, duration_min: 42, feeling: 'moderate' }
  const res = await req('POST', '/api/training-logs', { as: studentJar(), body })
  eq('201', res.status, 201)
  eq('student_id 由服务端从请求头填', res.json?.student_id, STUDENT)
  eq('log_date 逐字回显', res.json?.log_date, NEW_LOG_DATE)
  check('submitted_at 在响应里、而**不在**请求体里',
    typeof res.json?.submitted_at === 'string' && !('submitted_at' in body),
    `submitted_at=${res.json?.submitted_at}`)
  check('late 在响应里、而**不在**请求体里（服务端按 00:00–22:00 窗口算）',
    typeof res.json?.late === 'boolean' && !('late' in body), `late=${res.json?.late}`)
  check('source 在响应里、而**不在**请求体里', 'source' in (res.json ?? {}) && !('source' in body),
    `source=${res.json?.source}`)
  check('batch_id 在响应里、而**不在**请求体里', 'batch_id' in (res.json ?? {}) && !('batch_id' in body),
    `batch_id=${res.json?.batch_id}`)
  check('响应比请求体多的那几格（= 服务端填的那些）',
    Object.keys(res.json ?? {}).length - Object.keys(body).length >= 4,
    `响应 ${Object.keys(res.json ?? {}).length} 键 / 请求体 ${Object.keys(body).length} 键`)

  const again = await req('POST', '/api/training-logs', { as: studentJar(), body })
  eq('同一天再打一次 → 409（uq_training_log_student_day）', again.status, 409)
  eq('code 是 integrity_conflict', codeOf(again), 'integrity_conflict')
})

await step(7, `学生头 GET /api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF} → factor 与 sessions[].blocks 非空`, async () => {
  const res = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    as: studentJar(),
  })
  eq('200', res.status, 200)
  const sheet = res.json ?? {}
  check('factor 是一个数', typeof sheet.factor === 'number', `factor=${sheet.factor}`)
  // ⚠️ **顶回派单第 7 步的措辞**：响应体里**没有**顶层的 `blocks`。实测形状是
  //    `{week, factor, reasons, sources, paused, sessions: [{day, focus, blocks: [...]}]}`
  //    —— `blocks` 在 `sessions[]` 里面（一天一组）。故断言落在 sessions 与
  //    「全部 sessions 的 blocks 合起来非空」这两格上。
  check('sessions 非空', Array.isArray(sheet.sessions) && sheet.sessions.length > 0,
    `sessions=${Array.isArray(sheet.sessions) ? sheet.sessions.length : typeof sheet.sessions}`)
  const blockCount = (sheet.sessions ?? []).reduce((n, s) => n + (Array.isArray(s.blocks) ? s.blocks.length : 0), 0)
  check('sessions[].blocks 合起来非空', blockCount > 0, `${blockCount} 个 block`)
  check('reasons 是一个数组', Array.isArray(sheet.reasons), `reasons=${fmt(sheet.reasons)}`)
  check('sources 与 reasons 等长（约束第 13 条那一句要靠它们算）',
    Array.isArray(sheet.sources) && sheet.sources.length === (sheet.reasons ?? []).length,
    `sources=${fmt(sheet.sources)}`)

  // ⚠️ 约束第 14 条：**教师会话**调学生侧那个端点是 **403**（Plan 05A 之前是 401）。
  //    改的理由逐字写在后端 `app/api/deps.py` 的 `current_student` 里：请求者
  //    **已经登录了**，只是不是这个端点要的那一类人 —— `unauthenticated` 说的是
  //    「我不知道你是谁」，而这里我们知道。故跨 kind 一律 403 `forbidden`。
  const asTeacher = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  eq('教师会话调学生侧的 weekly-sheet → 403（**不是 401**：跨 kind）', asTeacher.status, 403)
  eq('code 是 forbidden', codeOf(asTeacher), 'forbidden')

  // ⚠️ 教师侧的变体只对**他本学期任教的学生**开放（`require_teaches_student`）。
  //    故这里从数据里**现找**一个 T0001 教的学生，而不是拿学生 4 硬试：
  //    实测学生 4 不在 T0001 的班里（下面那一拍专门断言这个 403）。
  // ⚠️ `/api/teachers` 自 Plan 05A Task 5 起**要教职身份**（那一份列表含
  //    `staff_no` + `name`，正是教师绑定口令的全部验身材料），故带 `as: 'teacher'`。
  //    ⚠️ 漏掉它的失效形态很隐蔽：401 的响应体里没有 `items`，于是 `me` 是
  //    `undefined`、`taught` 是空数组，而本步接下来那一拍会红在
  //    「找得到一个 T0001 本学期任教的学生」上 —— 离真因（名册读要身份）隔了两层。
  const teachers = (await req('GET', '/api/teachers?limit=50', { as: 'teacher', quiet: true })).json?.items ?? []
  const me = teachers.find((t) => t.staff_no === TEACHER)
  const sections = (await req('GET', '/api/course-sections?limit=50', { quiet: true })).json?.items ?? []
  const mine = sections.filter((s) => s.teacher_id === me?.id).map((s) => s.id)
  // ⚠️ 安全收紧波起带教师 jar：`enrollments` 是学生键资源（`student_id ↔
  //    course_section_id`，即「谁在哪个班」；匿名 401）。
  // ⚠️⚠️ **Plan 06 Task 8 之后这一发拿到的不再是「全校」的选课关系**：
  //    `enrollments` 的 `read_scope` 改成了 `staff_taught`，故 T0001 读到的是
  //    **他任教的 41 个学生**的选课行（实测 `total=82` = 41 人 × 每人 2 个班），
  //    而**不是**全表 120 行。⚠️ 而本拍的判据**照旧成立**、一个字都没改：
  //    它下面还要按 `mine`（`course_section.teacher_id == 我`）再筛一次，
  //    而「我任教的那些班的选课行」恰好全部落在我可见的行里
  //    （那些行的 `student_id` 按定义就在我的任教范围里）→ `taught` 仍是 50 项 / 41 人。
  //    ⚠️ 漏掉身份头的失效形态与上面 `/api/teachers` 那一格逐字同构（401 的响应体里
  //    没有 `items` → `taught` 是空数组 → 红在离真因两层远的地方）。
  const enrollments = (await req('GET', '/api/enrollments?limit=200', { as: 'teacher', quiet: true })).json?.items ?? []
  const taught = enrollments.filter((e) => mine.includes(e.course_section_id)).map((e) => e.student_id)
  SHARED.teacherId = me?.id ?? null
  SHARED.mySections = mine
  SHARED.taughtStudent = taught[0] ?? null
  // ⚠️ **Plan 06 Task 8 加的**：第 12 步 ⑦ 那一拍要「T0001 任教的学生 id 集合」，
  //    而它的唯一算式就是上面这两行（名册 → 我任教的班 → 选课行）。存进 SHARED
  //    而不是在第 12 步重算一遍：两份算式漂了之后，⑦ 那一拍会红在
  //    「教师读到的行不属于他任教的学生」上，而真因是两处的集合不一样。
  SHARED.taughtStudents = [...new Set(taught)]
  out(`    ${TEACHER} = teacher #${me?.id}（${me?.name}），任教 ${mine.length} 个班、名册 ${taught.length} 人`)
  check('找得到一个 T0001 本学期任教的学生', SHARED.taughtStudent !== null, `student_id=${SHARED.taughtStudent}`)

  const asStudent = await req('GET', `/api/students/${SHARED.taughtStudent}/weekly-sheet?as_of=${AS_OF}`, {
    as: studentJar(SHARED.taughtStudent),
    quiet: true,
  })
  const teacherVariant = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/weekly-sheet?as_of=${AS_OF}`, {
    as: 'teacher',
    quiet: true,
  })
  eq('学生侧（本人头）→ 200', asStudent.status, 200)
  eq('教师侧变体 → 200', teacherVariant.status, 200)
  eq('两个变体的响应体**逐字相同**（后端把函数体抽成了 _weekly_sheet_response）',
    teacherVariant.text, asStudent.text)

  // 不在自己班里的学生 → 403 forbidden（判据是 enrollment ⋈ course_section.teacher_id）
  const notMine = await req('GET', `/api/teacher/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  check(`学生 ${STUDENT} 不在 ${TEACHER} 本学期任教的班里 → 403`, notMine.status === 403,
    `status=${notMine.status}`)
  eq('code 是 forbidden', codeOf(notMine), 'forbidden')

  // 越权：学生 5 的头去读学生 4 的训练单
  const cross = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    as: studentJar(5),
  })
  eq('越权 → 403', cross.status, 403)
  eq('code 是 forbidden', codeOf(cross), 'forbidden')

  /* ---------------------------------------------------------------- 第 7 步 bis
     ⚠️ **收尾波加的一拍**：`/home` 的教师侧变体（Task 3 顶回的那一条落地）。
     与 weekly-sheet 同一条处置：后端把函数体抽成了 `dashboard._student_home_response`
     两处共用，故两个端点的响应体**逐字相同**。
     ⚠️ 三格聚合量**逐个造成非零再比**（否则「两边都是空」也相等，那是假绿）：
       · `explanation`   —— Task 3 说「教师身份下拿不到那一段中文」，这里断它非空；
       · `badges.count`  —— 从 `/api/alerts` 里**现找**一个有 GREEN_MASTERY 且由
                            T0001 本学期任教的学生（不写死学号）；
       · `pending_rpe`   —— ⚠️ 刚复原的演示库上它**对 41 个人全是空数组**（实测：
                            `demo_data` 让每个在册学生都交了每一节已发起快评的课），
                            故这里用**本脚本自己造的那一节课**（第 2 步建、第 3 步发起
                            快评、只有学生 4 交过）+ `as_of=2025-10-13`（那一节课所在的
                            学期周的第 1 天）把它逼成非空 —— 于是「待办卡片」这一格
                            是被**真的**验证过的，不是只验了「键在」。 */
  const homeAsStudent = await req('GET', `/api/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`, {
    as: studentJar(SHARED.taughtStudent),
    quiet: true,
  })
  const homeAsTeacher = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`, {
    as: 'teacher',
    quiet: true,
  })
  eq('学生侧 /home（本人头）→ 200', homeAsStudent.status, 200)
  eq('教师侧 /home 变体 → 200', homeAsTeacher.status, 200)
  eq('两个 /home 变体的响应体**逐字相同**（后端抽成了 _student_home_response）',
    homeAsTeacher.text, homeAsStudent.text)
  const home = homeAsTeacher.json ?? {}
  eq('/home 恰好 9 个键', Object.keys(home).sort().join(','),
    'as_of,badges,pending_rpe,semester_id,stratification,student_id,unread_notifications,week,weekly_sheet')
  check('① explanation 非空（Task 3 说教师身份下拿不到的那一段中文）',
    typeof home.stratification?.explanation === 'string' && home.stratification.explanation.length > 0,
    `${(home.stratification?.explanation ?? '').length} 字符`)
  check('② unread_notifications 是一个数', typeof home.unread_notifications === 'number',
    `unread=${fmt(home.unread_notifications)}`)
  check('③ badges 是 {count, latest} 两格', typeof home.badges?.count === 'number'
    && ('latest' in (home.badges ?? {})), `badges=${fmt(home.badges)}`)

  // ③ 的非零档：现找一个有 GREEN_MASTERY 且由 T0001 本学期任教的学生
  const alertRows = (await req('GET', '/api/alerts?limit=200', { as: 'teacher', quiet: true })).json?.items ?? []
  const greenHolders = alertRows.filter((a) => a.rule_id === 'GREEN_MASTERY').map((a) => a.student_id)
  const badged = greenHolders.find((id) => taught.includes(id)) ?? null
  check('找得到一个「有绿牌 ∧ 由 T0001 本学期任教」的学生', badged !== null,
    `绿牌 ${greenHolders.length} 人，其中 T0001 任教的 ${greenHolders.filter((id) => taught.includes(id)).length} 人`)
  if (badged !== null) {
    const badgedHome = await req('GET', `/api/teacher/students/${badged}/home?as_of=${AS_OF}`, {
      as: 'teacher', quiet: true,
    })
    eq(`学生 ${badged} 的教师侧 /home → 200`, badgedHome.status, 200)
    check(`学生 ${badged} 的 badges.count > 0（后端按本学期 COUNT，前端不自己数）`,
      (badgedHome.json?.badges?.count ?? 0) > 0, `badges=${fmt(badgedHome.json?.badges)}`)
  }

  // ①/② 之外的第四格 pending_rpe：用本脚本自己造的那一节课把它逼成非空
  const classmate = enrollments
    .filter((e) => e.course_section_id === SHARED.sectionId && e.student_id !== STUDENT)
    .map((e) => e.student_id)[0] ?? null
  check(`班 ${SHARED.sectionId} 里找得到一个不是学生 ${STUDENT} 的人`, classmate !== null,
    `classmate=${classmate}`)
  if (classmate !== null) {
    const pendingHome = await req('GET', `/api/teacher/students/${classmate}/home?as_of=${NEW_SESSION_DATE}`, {
      as: 'teacher', quiet: true,
    })
    eq(`学生 ${classmate} 的教师侧 /home（as_of=${NEW_SESSION_DATE}）→ 200`, pendingHome.status, 200)
    const pending = pendingHome.json?.pending_rpe ?? []
    check('④ pending_rpe 里出现了第 2 步建、第 3 步发起快评的那一节课（他没交）',
      pending.some((p) => p.class_session_id === SHARED.sessionId),
      `pending=${fmt(pending)}`)
    // ⚠️ 反证：交了的那个人（学生 4）在同一节课上**不该**还有待办。
    //    走学生侧那一条（他本人调它是 200），响应体与教师侧逐字相同。
    const submitted = await req('GET', `/api/students/${STUDENT}/home?as_of=${NEW_SESSION_DATE}`, {
      as: studentJar(STUDENT), quiet: true,
    })
    eq(`学生 ${STUDENT}（第 5 步交过那一节课的快评）的学生侧 /home → 200`, submitted.status, 200)
    check('反证：他的 pending_rpe 里**没有**那一节课（交了就不该再挂在待办上）',
      !(submitted.json?.pending_rpe ?? []).some((p) => p.class_session_id === SHARED.sessionId),
      `pending=${fmt(submitted.json?.pending_rpe)}`)
  }

  // 教师侧 /home 的四档身份：不任教的教师 → 403、学生会话 → **403**（跨 kind）、
  // 匿名 → 401、**管理员（不带这个班）→ 200**（Plan 05A §3.6 第 2 条：越过任教闸门）。
  const homeNotMine = await req('GET', `/api/teacher/students/${STUDENT}/home?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  check(`学生 ${STUDENT} 不在 ${TEACHER} 本学期任教的班里 → /home 也是 403`,
    homeNotMine.status === 403, `status=${homeNotMine.status}`)
  eq('code 是 forbidden', codeOf(homeNotMine), 'forbidden')
  const homeWithStudentHeader = await req(
    'GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`,
    { as: studentJar(SHARED.taughtStudent) })
  eq('学生会话调教师侧 /home → 403（Plan 05A 之前是 401：跨 kind 是「认出来了、但不是那一类人」）',
    homeWithStudentHeader.status, 403)
  eq('code 是 forbidden', codeOf(homeWithStudentHeader), 'forbidden')
  const homeAnon = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`)
  eq('匿名调教师侧 /home → 401', homeAnon.status, 401)
  eq('匿名的 code 是 unauthenticated（**这一档没变**：真的不知道你是谁）',
    codeOf(homeAnon), 'unauthenticated')
  /* ⚠️ **管理员越过任教范围闸门**（Plan 05A Task 2 的实测三拍之一：
     带班教师 200 / 不带班教师 403 / 管理员（不带班）200）。
     ⚠️ 而「不带班」是**现算**出来的、不是假设的：`course_section.teacher_id`
     ⋈ `enrollment` 给出 T0003 本学期教谁，下面那一拍先断言学生 4 **不在**里面 ——
     少了这一拍，「T0003 恰好也带这个班」会让 200 变成一条什么也没证明的绿。
     ⚠️ 这一拍同时也是「`role='admin'` 不只是一个标签」的可执行判据：
     若不放行，管理员进了 `/t/dashboard` 却读不到任何班的数据（计划 §7 自审第 5 条）。 */
  const adminRow = (await req('GET', '/api/teachers?limit=50', { as: 'admin', quiet: true })).json?.items ?? []
  const adminId = adminRow.find((t) => t.staff_no === ADMIN)?.id ?? null
  const adminSections = ((await req('GET', '/api/course-sections?limit=50', { as: 'admin', quiet: true })).json?.items ?? [])
    .filter((s) => s.teacher_id === adminId).map((s) => s.id)
  const adminTaught = new Set(
    ((await req('GET', '/api/enrollments?limit=200', { as: 'admin', quiet: true })).json?.items ?? [])
      .filter((e) => adminSections.includes(e.course_section_id)).map((e) => e.student_id),
  )
  check(`管理员 ${ADMIN}（teacher #${adminId}）本学期**不**教学生 ${STUDENT}`,
    adminId !== null && !adminTaught.has(STUDENT),
    `${ADMIN} 任教 ${adminSections.length} 个班、名册 ${adminTaught.size} 人`)
  const homeAsAdmin = await req('GET', `/api/teacher/students/${STUDENT}/home?as_of=${AS_OF}`, {
    as: 'admin', quiet: true,
  })
  eq(`管理员（${ADMIN}，不带学生 ${STUDENT} 的班）调教师侧 /home → 200（越过了任教闸门）`,
    homeAsAdmin.status, 200)
  check('而它回的确实是一份 /home（9 个键，与学生侧变体同形）',
    Object.keys(homeAsAdmin.json ?? {}).length === 9,
    `键=${Object.keys(homeAsAdmin.json ?? {}).sort().join(',')}`)
  // ⚠️ 而学生侧那一条路径**今天仍然**拒绝教师会话（那不是缺陷，是「一个端点一道闸门」）
  const teacherOnStudentHome = await req('GET', `/api/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  eq('教师会话调**学生侧** /home → 仍然 403（故必须有变体）', teacherOnStudentHome.status, 403)
})

await step(8, '教师头 dashboard：三层完成率不是全 0、progress_board 非空', async () => {
  const dash = await req('GET', `/api/dashboard/class/${SHARED.sectionId}?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  eq('class dashboard → 200', dash.status, 200)
  check('响应非空对象', dash.json !== null && typeof dash.json === 'object', `键=${Object.keys(dash.json ?? {}).join(',')}`)

  const report = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?as_of=${AS_OF}`, {
    as: 'teacher',
  })
  eq('weekly-class-report → 200', report.status, 200)
  const byLayer = report.json?.checkin_rate_by_layer
  check('checkin_rate_by_layer 非空', byLayer !== null && typeof byLayer === 'object',
    `键=${Object.keys(byLayer ?? {}).join(',')}`)
  const rates = Object.values(byLayer ?? {}).map((x) => x?.rate)
  out(`    三层 rate = ${JSON.stringify(rates)}`)
  check('三层完成率**不是全 0**', rates.some((r) => typeof r === 'number' && r > 0), JSON.stringify(rates))
  check('至少有一层非 null（⚠️ null 是「那一层没人」，不得显示成 0）',
    rates.some((r) => r !== null && r !== undefined), JSON.stringify(rates))
  const board = report.json?.progress_board
  check('progress_board 非空', board !== null && board !== undefined
    && (Array.isArray(board) ? board.length > 0 : Object.keys(board).length > 0),
    `${Array.isArray(board) ? `数组 ${board.length} 项` : `对象 ${Object.keys(board ?? {}).length} 键`}`)
  check('suggestion 是后端算好的一句话（前端不再判一次）',
    typeof report.json?.suggestion === 'string' && report.json.suggestion.length > 0,
    `suggestion=${report.json?.suggestion}`)

  // ⚠️ 约束第 19 条：周报**只在周日**生成，故「那一周还没有周报」是 404 no_weekly_report，
  //    不是 200 一堆 0。
  // ⚠️⚠️ 而本端点的参数是 **`week`，不是 `as_of`**（实测：`?as_of=2025-10-15`
  //    被 FastAPI **静默忽略**、照样回最新那一份 —— 约束第 9 条那一族的又一例）。
  //    故 404 只能用 `?week=7` 试（演示库只生成到第 6 周）。
  const ignored = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?as_of=2025-10-15`, {
    as: 'teacher',
    quiet: true,
  })
  eq('⚠️ ?as_of= 在本端点被静默忽略（它只认 week）→ 仍然 200', ignored.status, 200)
  eq('忽略之后回的是「已存下来的最新一周」= 第 6 周', ignored.json?.week, 6)

  const explicit = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?week=6`, {
    as: 'teacher',
    quiet: true,
  })
  eq('?week=6 → 200', explicit.status, 200)
  eq('回的确实是第 6 周', explicit.json?.week, 6)

  const noReport = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?week=7`, {
    as: 'teacher',
  })
  eq('?week=7（那一周还没到周日）→ 404', noReport.status, 404)
  eq('code 是 no_weekly_report（不是通用的 not_found）', codeOf(noReport), 'no_weekly_report')
})

await step(9, '预警处置：reduce_20pct → 200；再处置 → 409 alert_not_pending；非法 action → 422 且点名合法值', async () => {
  const list = await req('GET', '/api/alerts?limit=200', { as: 'teacher', quiet: true })
  const rows = list.json?.items ?? []
  const pendingRed = rows.find((r) => r.level === 'red' && r.status === 'pending')
  check('有 pending 的红色预警', pendingRed !== undefined, `共 ${rows.length} 行`)
  SHARED.alertId = pendingRed?.id ?? null
  out(`    挑中 alert #${SHARED.alertId} rule_id=${pendingRed?.rule_id} student_id=${pendingRed?.student_id}`)

  // ⚠️ 约束第 17 条（Task 3 顶回的那一处）：三档的**真值**是
  //    ['ignore','note','reduce_20pct']，而计划正文写的 ACTION_REDUCE / ACTION_IGNORE /
  //    ACTION_NOTE 是 app/api/routers/alerts.py 里的**常量名**，送上去是 422。
  const res = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    as: 'teacher',
    body: { action: 'reduce_20pct' },
  })
  eq('处置 → 200', res.status, 200)
  eq('alert.status 变成 handled', res.json?.alert?.status ?? res.json?.status, 'handled')
  out(`    adjustment=${fmt(res.json?.adjustment)}`)
  out(`    notification=${fmt(res.json?.notification)?.slice(0, 160)}`)

  const again = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    as: 'teacher',
    body: { action: 'ignore' },
  })
  eq('再处置一次 → 409', again.status, 409)
  eq('code 是 alert_not_pending', codeOf(again), 'alert_not_pending')

  // ⚠️ 「枚举不在契约里」时唯一能做的机器守卫：送一个非法值，
  //    断言 422 **并且响应里点名了三档合法值**。
  const bad = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    as: 'teacher',
    body: { action: 'ACTION_REDUCE' },
  })
  eq('非法 action（计划正文写的那个常量名）→ 422', bad.status, 422)
  const badText = bad.text
  for (const legal of ['ignore', 'note', 'reduce_20pct']) {
    check(`422 的响应里点名了合法值 ${legal}`, badText.includes(legal), '')
  }
  check('422 的 code 是 unprocessable_value 或 request_validation_failed',
    ['unprocessable_value', 'request_validation_failed'].includes(codeOf(bad)), `code=${codeOf(bad)}`)

  // 三档合法值**都**被接受（在另外三条 pending 预警上逐个试）
  const rest = rows.filter((r) => r.status === 'pending' && r.id !== SHARED.alertId)
  for (const action of ['ignore', 'note']) {
    const target = rest.shift()
    if (!target) {
      check(`还有一条 pending 预警可以试 ${action}`, false, '预警不够用了')
      continue
    }
    const r = await req('POST', `/api/alerts/${target.id}/handle?as_of=${AS_OF}`, {
      as: 'teacher',
      body: action === 'note' ? { action, note: '联调脚本写的备注' } : { action },
      quiet: true,
    })
    eq(`action=${action} 被接受 → 200`, r.status, 200)
  }
  // note 而备注为空 → 422（约束：这一档的闸门在 domain 层）
  const noteTarget = rest.shift()
  if (noteTarget) {
    const r = await req('POST', `/api/alerts/${noteTarget.id}/handle?as_of=${AS_OF}`, {
      as: 'teacher',
      body: { action: 'note', note: '   ' },
    })
    eq("action=note 而 note 是空白 → 422", r.status, 422)
  }
})

await step(10, '写入侧强制：匿名 POST /api/semesters → 401；普通教师 → 403；管理员 → 201；⚠️ DELETE 是 405 不是 204', async () => {
  const body = { name: '联调脚本建的学期（删不掉，见下面）', start_date: '2026-02-23', end_date: '2026-07-05', weeks: 18 }
  const anon = await req('POST', '/api/semesters', { body })
  eq('匿名 → 401', anon.status, 401)
  eq('code 是 unauthenticated', codeOf(anon), 'unauthenticated')

  /* ⚠️ **Plan 05A Task 2 把这一拍从「教师头 → 201」改成了三拍**：
     用户 2026-10-12 逐字裁定「管理员这个角色接管管理台（23 个资源的增删改查）」，
     故后端 `crud.py` 的 `require_teacher` → `require_admin`，9 个可写资源的
     POST/PATCH/DELETE 一共 **26** 个操作从「任何在册教师可写」变成「仅管理员可写」。
     ⚠️ 于是「教师 → 201」这条断言**必须**改成「教师 → 403」，否则本脚本会
     在一个已经收紧了的后端上**红**，而下一个人会以为是后端坏了。            */
  const asTeacher = await req('POST', '/api/semesters', { as: 'teacher', body })
  eq('普通教师 → 403（管理台仅 role=admin）', asTeacher.status, 403)
  eq('code 是 forbidden', codeOf(asTeacher), 'forbidden')

  const asAdmin = await req('POST', '/api/semesters', { as: 'admin', body })
  eq('管理员 → 201', asAdmin.status, 201)
  const semesterId = asAdmin.json?.id ?? null
  check('拿到了 id', Number.isInteger(semesterId), `id=${semesterId}`)

  // ⚠️⚠️ **顶回派单第 10 步**（Plan 04 那一波就顶过，原文照留）：派单写的是
  //    「再 DELETE 它 → 断言 204」。实测 `semesters` 是 23 行里唯一
  //    「**可写 + on_delete='forbid'**」的资源，后端**根本不注册** DELETE 端点
  //    → 打过去是 **405 http_405**。（派单第 12 步自己也写了「`semesters` 除外，
  //    它是 `forbid` 故没有 DELETE」。）
  const del = await req('DELETE', `/api/semesters/${semesterId}`, { as: 'admin' })
  eq('DELETE /api/semesters/{id} → 405（不是 204）', del.status, 405)
  eq('code 是 http_405', codeOf(del), 'http_405')

  // 故「建了再删掉、拿到一个真的 204」这一拍换一个 restrict 的资源来做：teachers
  const created = await req('POST', '/api/teachers', {
    as: 'admin',
    body: { staff_no: 'SMOKE01', name: '联调脚本建的教师' },
  })
  eq('POST /api/teachers → 201', created.status, 201)
  eq('而新建的教师缺省**不是**管理员（role 的缺省值来自 Teacher.DEFAULT_ROLE）',
    created.json?.role, 'teacher')
  const teacherId = created.json?.id ?? null
  const removed = await req('DELETE', `/api/teachers/${teacherId}`, { as: 'admin' })
  eq('DELETE /api/teachers/{id} → 204', removed.status, 204)
  eq('204 没有响应体', removed.text, '')
  const goneAnon = await req('GET', `/api/teachers/${teacherId}`, { as: 'admin' })
  eq('删掉之后 read-one → 404', goneAnon.status, 404)

  // restrict：删一行被子表指着的学生 → 409，且 message 点名了子表
  const restricted = await req('DELETE', `/api/students/${STUDENT}`, { as: 'admin' })
  eq('删一个被 12 张表指着的学生 → 409', restricted.status, 409)
  eq('code 是 integrity_conflict', codeOf(restricted), 'integrity_conflict')
  check('message 里点名了子表（「还被谁引用」在这一句里，不在 detail 里）',
    typeof messageOf(restricted) === 'string' && messageOf(restricted).includes('仍指向它'),
    `message=${messageOf(restricted)}`)
  eq('detail 是 null（后端把信息放在 message 里）', restricted.json?.error?.detail, null)
})

await step(11, '只读资源被写 → 405 且 code 是 http_405（约束第 20 条）', async () => {
  const anon = await req('POST', '/api/prescriptions', { body: { student_id: STUDENT } })
  eq('匿名 POST /api/prescriptions → 405', anon.status, 405)
  eq('code 是 http_405', codeOf(anon), 'http_405')

  const asTeacher = await req('POST', '/api/prescriptions', {
    as: 'teacher',
    body: { student_id: STUDENT },
  })
  eq('**教师头**也一样是 405（端点根本不注册，与身份无关）', asTeacher.status, 405)
  eq('code 是 http_405', codeOf(asTeacher), 'http_405')

  const del = await req('DELETE', '/api/alerts/1', { as: 'teacher' })
  eq('DELETE 一个 forbid 的资源 → 405', del.status, 405)
  eq('code 是 http_405', codeOf(del), 'http_405')
})

/* ------------------------------------------------------------------ 第 12 步
   ⚠️ 从 /openapi.json **反查** catalog/resources.ts 的 23 行（计划第 4 节要求的守卫）。
   目录是用 Node 的类型剥离**直接 import 那个 .ts 文件**读出来的
   （`import type` 会被擦掉，故它不需要 vite / tsc）—— 不是正则抠源码文本，
   于是「目录里到底写了什么」这一侧也是运行时口径。                       */
await step(12, '从 /openapi.json 反查 catalog/resources.ts 的 23 行（6 拍 + 终审 S2-① 的 5 拍）', async () => {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const catalogUrl = new URL('../src/catalog/resources.ts', `file://${path.resolve(here)}/`).href
  const catalog = await import(catalogUrl)
  const RESOURCES = catalog.RESOURCES
  out(`    已 import ${catalogUrl}`)
  out(`    目录里 ${RESOURCES.length} 行；可写 ${RESOURCES.filter((r) => r.writable).length}、`
    + `只读 ${RESOURCES.filter((r) => !r.writable).length}`)

  const spec = await req('GET', '/openapi.json', { record: false, quiet: true })
  eq('/openapi.json → 200', spec.status, 200)
  const paths = spec.json?.paths ?? {}
  const apiPaths = Object.keys(paths).filter((p) => p.startsWith('/api/'))
  out(`    /api/ 路径模板 ${apiPaths.length} 个`)

  const methodsOf = (p) => Object.keys(paths[p] ?? {}).filter((m) => ['get', 'post', 'put', 'patch', 'delete'].includes(m))

  // ① 每个资源都存在（集合路径 + 成员路径）
  let missing = []
  for (const entry of RESOURCES) {
    const detail = `${entry.path}/{${entry.pkField}}`
    if (!(entry.path in paths)) missing.push(`集合 ${entry.path}`)
    if (!(detail in paths)) missing.push(`成员 ${detail}`)
  }
  check('① 23 个资源的集合路径与成员路径都在 openapi 里', missing.length === 0, missing.join(' | '))
  eq('① 目录恰好 23 行', RESOURCES.length, 23)

  /* ⚠️⚠️ **Plan 06 Task 15 / 终审 S2-①**：`/admin` 首页那段「三个口径」散文里有**两个
     写死的计数**（`ANONYMOUS_READABLE` / `ANONYMOUS_GETS`），而它们是前端目录
     `catalog/resources.ts` **派生不出来**的 —— 那一份刻意不带后端 `read_scope` 那一格
     （五档表住在 `app/api/routers/catalog.py` 的模块 docstring 里）。
     ⚠️ 改前那一段逐字写着「**读是匿名的**：23 个资源的列表与详情都不需要身份
     （后端 **48 个匿名 GET** 里就包括这 23 个 list 与 23 个 read-one）」，而本波重新实测：
     匿名可读的资源只有 **7** 个（另 16 个匿名 list 一律 401）、openapi 上没有 `security`
     键的 GET 是 **15** 个 ⇒ 一段与鉴权实物**相反**的散文，而甲方打开管理台就看到它。
     ⚠️ 而它当时**没有任何守卫**：本步①–⑥数的一律是目录那 23 行的结构，第 14 步
     admin-index 的 5 条 needle 一条都不碰那三句（637/0 全绿）。
     ⚠️ 于是本组是那两个字面量的**期望侧**：从 `/openapi.json` 现量「哪些操作没有
     `security` 键」，再与 `ResourceIndex.vue` 源码里的字面量对拍
     （两侧不同源，硬规矩 #35；与本仓 `_MODELS_PUBLIC_BASELINE` 钉 33 同一条姿势）。 */
  {
    const FIVE = ['get', 'post', 'put', 'patch', 'delete']
    const isAnon = (op) => op !== undefined && !('security' in op)
    const anonGets = []
    const anonWrites = []
    for (const p of Object.keys(paths)) {
      for (const m of FIVE) {
        const op = paths[p]?.[m]
        if (!isAnon(op)) continue
        if (m === 'get') anonGets.push(p)
        else anonWrites.push(`${m.toUpperCase()} ${p}`)
      }
    }
    const anonCollections = RESOURCES
      .filter((e) => isAnon(paths[e.path]?.get))
      .map((e) => e.resource)
    out(`    openapi 上没有 security 键的操作 ${anonGets.length + anonWrites.length} 个`
      + `（GET ${anonGets.length} / 写 ${anonWrites.length}）`)
    out(`    其中集合 GET 匿名的资源 ${anonCollections.length} 个：${anonCollections.join(', ')}`)
    out(`    匿名的写操作：${anonWrites.join(' | ')}`)

    const vueRoot = path.resolve(here, '..')
    const vueSrc = fs.readFileSync(
      path.join(vueRoot, 'src/views/admin/ResourceIndex.vue'), 'utf8')
    const litOf = (name) => {
      const m = vueSrc.match(new RegExp(`const ${name} = (\\d+)`))
      return m === null ? null : Number(m[1])
    }
    const wantReadable = litOf('ANONYMOUS_READABLE')
    const wantGets = litOf('ANONYMOUS_GETS')
    check('§S2-① 守卫不空转：从 ResourceIndex.vue 的**源码**里读到了那两个写死的计数（非 null）',
      wantReadable !== null && wantGets !== null,
      `ANONYMOUS_READABLE=${wantReadable} ANONYMOUS_GETS=${wantGets}`)
    eq('§S2-① 页面上写的「匿名可读的资源数」== openapi 现量的（集合 GET 没有 security 键）',
      anonCollections.length, wantReadable)
    eq('§S2-① 页面上写的「匿名 GET 数」== openapi 现量的（15 = 7 个 list + 7 个 read-one + /api/health）',
      anonGets.length, wantGets)
    check('§S2-① 而那 7 个匿名可读的**都不含学生键**（students / teachers 两行必须在要身份那一侧：'
      + '它们正是绑定口令的验身材料）',
      anonCollections.length === 7
        && !anonCollections.includes('students') && !anonCollections.includes('teachers'),
      anonCollections.join(', '))
    check('§S2-① 而 23 个资源上**一个匿名写操作都没有**（3 个匿名 POST 全在 /api/auth/*：'
      + '登录与两个绑定 ⇒ 页面上「写仅管理员」那一句不会漂成「匿名可写」）',
      anonWrites.every((s) => s.includes('/api/auth/')) && anonWrites.length === 3,
      anonWrites.join(' | '))
  }

  // ② writable=false 的 14 个确实没有 POST/PATCH/DELETE
  const ro = RESOURCES.filter((r) => !r.writable)
  eq('② 只读的有 14 个', ro.length, 14)
  const roLeaks = []
  for (const entry of ro) {
    const detail = `${entry.path}/{${entry.pkField}}`
    const all = [...methodsOf(entry.path), ...methodsOf(detail)]
    for (const m of ['patch', 'delete']) {
      if (all.includes(m)) roLeaks.push(`${entry.resource} 有 ${m.toUpperCase()}`)
    }
    // ⚠️ POST 这一格要小心：`rpe-records` / `training-logs` / `mini-tests` 三个
    //    只读资源**确实有** POST，但那是**特例端点**（学生头 / 教师头的窄端点），
    //    不是泛型 CRUD 的写入侧。判据是它的 operationId：泛型工厂生成的是
    //    `create_row_api_<资源>_post`。
    const post = paths[entry.path]?.post
    if (post && String(post.operationId ?? '').startsWith('create_row_')) {
      roLeaks.push(`${entry.resource} 有泛型 create_row POST`)
    }
  }
  check('② 14 个只读资源都没有泛型 CRUD 的写入端点', roLeaks.length === 0, roLeaks.join(' | '))
  const specialPost = ro.filter((e) => methodsOf(e.path).includes('post')).map((e) => e.resource)
  out(`    ⚠️ 其中 ${specialPost.length} 个只读资源有**特例** POST（不是泛型写入侧）：${specialPost.join(', ')}`)

  // ③ writable=true 的 9 个三个都有（semesters 除外，它是 forbid 故没有 DELETE）
  const rw = RESOURCES.filter((r) => r.writable)
  eq('③ 可写的有 9 个', rw.length, 9)
  const rwLeaks = []
  for (const entry of rw) {
    const detail = `${entry.path}/{${entry.pkField}}`
    const base = methodsOf(entry.path)
    const det = methodsOf(detail)
    if (!base.includes('post')) rwLeaks.push(`${entry.resource} 缺 POST`)
    if (!det.includes('patch')) rwLeaks.push(`${entry.resource} 缺 PATCH`)
    const wantDelete = entry.onDelete !== 'forbid'
    if (wantDelete !== det.includes('delete')) {
      rwLeaks.push(`${entry.resource} 的 DELETE 与 on_delete=${entry.onDelete} 不符（有=${det.includes('delete')}）`)
    }
    if (entry.hasDeleteEndpoint !== det.includes('delete')) {
      rwLeaks.push(`${entry.resource} 的 hasDeleteEndpoint=${entry.hasDeleteEndpoint} 与 openapi 不符`)
    }
  }
  check('③ 9 个可写资源 POST/PATCH 齐全、DELETE 与 on_delete 一致（semesters 无 DELETE）',
    rwLeaks.length === 0, rwLeaks.join(' | '))
  eq('③ 其中恰好 8 个有 DELETE（semesters 是 forbid）',
    rw.filter((e) => e.hasDeleteEndpoint).length, 8)

  // ④ 每个资源的 pkField 与 openapi 里那个成员路径的参数名逐字相同
  const pkMismatch = []
  for (const entry of RESOURCES) {
    const detail = `${entry.path}/{${entry.pkField}}`
    const op = paths[detail]?.get
    const names = (op?.parameters ?? []).filter((p) => p.in === 'path').map((p) => p.name)
    if (names.length !== 1 || names[0] !== entry.pkField) {
      pkMismatch.push(`${entry.resource}: 目录=${entry.pkField} openapi=${names.join('/')}`)
    }
    // 顺带核实「路径模板里的花括号名」也逐字相同（FastAPI 用它做函数签名）
    if (!detail.includes(`{${entry.pkField}}`)) pkMismatch.push(`${entry.resource}: 模板不含 {${entry.pkField}}`)
  }
  check('④ 23 个 pkField 与 openapi 的成员路径参数名逐字相同', pkMismatch.length === 0, pkMismatch.join(' | '))
  eq('④ 其中 -es 复数的那一个（fitness-test-batches）是手工覆盖的',
    RESOURCES.find((r) => r.resource === 'fitness-test-batches')?.pkField, 'fitness_test_batch_id')

  // ⑤ 每个 list 端点的响应确实**未定型**（→ types.ts 那 23 个手写类型是必要的）
  const untyped = []
  const typed = []
  for (const entry of RESOURCES) {
    const schema = paths[entry.path]?.get?.responses?.['200']?.content?.['application/json']?.schema
    const isUntyped = schema?.type === 'object' && schema?.additionalProperties === true
      && !('$ref' in (schema ?? {})) && !schema?.oneOf && !schema?.anyOf && !schema?.allOf && !schema?.properties
    if (isUntyped) untyped.push(entry.resource)
    else typed.push(`${entry.resource}=${JSON.stringify(schema)?.slice(0, 90)}`)
  }
  eq('⑤ 23 个 list 端点的响应**全部**未定型', untyped.length, 23)
  check('⑤ 没有一个 list 端点是定型的（否则 types.ts 那一格是冗余）', typed.length === 0, typed.join(' | '))
  const health = paths['/api/health']?.get?.responses?.['200']?.content?.['application/json']?.schema
  eq('⑤ /api/health 也未定型（24 = 23 + 1）',
    health?.type === 'object' && health?.additionalProperties === true, true)

  // on_delete 的三档计数（目录 ↔ 后端 catalog.RESOURCES）
  const counts = { restrict: 0, forbid: 0, cascade: 0 }
  for (const entry of RESOURCES) counts[entry.onDelete] = (counts[entry.onDelete] ?? 0) + 1
  out(`    on_delete: restrict=${counts.restrict} forbid=${counts.forbid} cascade=${counts.cascade}`)
  eq('⑤ on_delete restrict 12', counts.restrict, 12)
  eq('⑤ on_delete forbid 10', counts.forbid, 10)
  eq('⑤ on_delete cascade 1', counts.cascade, 1)
  eq('⑤ cascade 的那一个是 class-sessions',
    RESOURCES.filter((r) => r.onDelete === 'cascade').map((r) => r.resource).join(','), 'class-sessions')

  // 全库口径（⚠️ 一律用 app.openapi() 的 paths，不用 len(app.routes)：
  //    FastAPI 0.141.1 的 include_router 是惰性的，按 routes 数的守卫是假绿的）
  let ops = 0
  let secured = 0
  let gets = 0
  let getsAnon = 0
  for (const p of apiPaths) {
    for (const m of methodsOf(p)) {
      ops += 1
      const op = paths[p][m]
      if (op.security) secured += 1
      if (m === 'get') {
        gets += 1
        if (!op.security) getsAnon += 1
      }
    }
  }
  out(`    操作 ${ops} 个 / 挂 security ${secured} 个 / GET ${gets} 个（匿名 ${getsAnon}）`)
  // ⚠️ **这五格在 Plan 04 的 5 个 Task + 收尾波里变了 4 次，Plan 05A 又变了两次**，
  //    故每一格都写明了「上一次是多少、这一次为什么变」。
  //    Plan 05A Task 1：+5 个 `/api/auth/*` 端点（1 个新路径模板 `/api/auth/me` 等，
  //      其中 `GET /api/auth/me` 挂 security、`POST /api/auth/logout` 挂 security）；
  //    Plan 05A Task 2：挂 security 的**操作数不变**（管理员就是一行 `teacher`，
  //      故 OpenAPI 那一格 `Security(TEACHER_STAFF_NO_SCHEME)` 一个字都没改，
  //      改的只是**判定**：`require_teacher` → `require_admin`）；
  //    Plan 05A Task 5：`GET /api/students{,/{id}}` 与 `GET /api/teachers{,/{id}}`
  //      那 **4** 个操作从匿名改成要教职身份（那两份列表含绑定口令的验身材料）
  //      → 挂 security 48 → **52**、匿名 GET 48 → **44**。
  //    ⚠️⚠️ **安全收紧波：52 → 80、匿名 GET 44 → 16**（+28 = 13 个学生键资源 × 2 个 GET
  //      + `weekly-class-reports` × 2）。理由是终审 I6：那 44 个匿名 GET 虽然没有一个
  //      返回验身材料或人名，却放行了**整套以 `student_id`（1–60 的小整数）为键的
  //      健康档案** —— 「任何已登录的学生只要把 cookie 丢掉，就能匿名读全校 60 人的
  //      健康档案」。⚠️ 而**路径模板 / 操作 / GET 三个数一个都没变**
  //      （71 / 99 / 60）：本波只改**谁能读**，不加也不删端点。
  //      逐字的三档名单住在 `backend/app/api/routers/catalog.py` 的模块 docstring。
  //    ⚠️⚠️ **交付前收尾波 ③：80 → 81、匿名 GET 16 → 15**（+1 = 那扇安全收紧波点名
  //      却没关的门 `GET /api/mini-tests/normalized`）。⚠️ 它是**特例端点**、不在
  //      `catalog.RESOURCES` 那 23 行里，故 `test_crud.py` 的 `anonymous == 7`
  //      那一拍**不受影响**（它数的是 23 行里 `read_scope is None` 的行数，实测仍是 7）。
  //      ⚠️ 而它挂的是**两个** scheme（学生头 **或** 教师头，OR 语义），且端点里对
  //      学生档做了**列级**收窄（实测 `squat_score` 逐行等于 `squat_30s_count`、
  //      `composite` 又能反推它 → 两格对别人的行置 `null`）。
  //      ⚠️⚠️ **Plan 06 Task 9 把那一格列级收窄抬成了 schema 级摘列**（那两格已从
  //      `NormalizedEntryRead` 上摘掉，见上面 Task 9 那一段），故本段是**历史**。
  //      逐字取证与三档身份的守卫在**第 13 步**；后端的对账表住在 `feedback.py` 的
  //      `normalized_scores`。
  //      ⚠️ 路径模板 / 操作 / GET 三个数**仍然一个都没变**（71 / 99 / 60）。
  // ⚠️⚠️ **Plan 06 Task 5 把四格各抬了一格**（+ `GET /api/audit-logs`：审计留痕的
  //    管理员只读端点，spec §13.9）：路径模板 71 → **72**、操作 99 → **100**、
  //    挂 security 81 → **82**、GET 60 → **61**。
  //    ⚠️ 而**匿名 GET 仍是 15**（新端点挂 security）、`securitySchemes` **仍是 3**
  //    （它挂的是既有的 `X-Teacher-Staff-No`，没引入第四个 scheme）。
  //    ⚠️ 它**不进** `catalog/resources.ts` 的那 23 行（派单 §1 第 5 条：它是特例端点，
  //    同 `/api/health` 那一族），故本步①–④那几拍（数的是 23 行）**一个都没变**。
  //    ⚠️ 后端那一侧的同一条对账住在
  //    `tests/api/test_prescription_api.py::test_the_identity_schemes_are_registered_as_openapi_security_schemes`
  //    （两处刻意不合并，硬规矩 #103 的「两个住址」那一档）。
  // ⚠️⚠️ **Plan 06 Task 9 又把四格各抬了一格**（+ `GET /api/mini-tests/normalized/me`：
  //    `NormalizedEntryRead` **摘掉** `squat_score` / `composite` 两格之后，
  //    「本人读自己那三格」搬到的那一个**仅学生**窄端点）：
  //    路径模板 72 → **73**、操作 100 → **101**、挂 security 82 → **83**、GET 61 → **62**。
  //    ⚠️ 而**匿名 GET 仍是 15**（新端点挂 security）、`securitySchemes` **仍是 3**
  //    （它挂的是既有的 `X-Student-Id`，没引入第四个 scheme）。
  //    ⚠️ 它挂的是**一个** scheme，⚠️ **刻意不是** `normalized` 那一项的两个：
  //    本端点**不接受教职**（`Depends(current_student)` 只认学生，教师/管理员 cookie 是
  //    **403**），故 OR 语义在这里是一句假话。四档矩阵在**第 13 步**逐字钉。
  //    ⚠️ 摘列的那一半（`normalized` 的 entries 从五格变三格）**不动这五格任何一格**：
  //    它改的是 `components.schemas`，不是 `paths`。⚠️ 而它动的正是「OpenAPI 是不是
  //    真契约」这一格 —— 改前那两格随身份而变（学生档对别人的行置 `null`），
  //    而 OpenAPI 只有一张 schema，故生成出来的 `schema.d.ts` 宣称它们永远有值。
  //    ⚠️ 它**不进** `catalog/resources.ts` 的那 23 行（特例端点），
  //    故本步①–④那几拍（数的是 23 行）**一个都没变**。
  // ⚠️⚠️ **Plan 06 Task 10 又把四格各抬了一格**（+ `GET /api/teacher/students/{id}/normalized`：
  //    Task 9 把 `squat_score` / `composite` 两格从 `NormalizedEntryRead` 上摘掉之后，
  //    教师端「学生详情」页的「小测综合分」那一格没了，Task 9 因此顶回「正确的形状是
  //    另开一条教师侧变体」——本波落地）：
  //    路径模板 73 → **74**、操作 101 → **102**、挂 security 83 → **84**、GET 62 → **63**。
  //    ⚠️ 而**匿名 GET 仍是 15**（新端点挂 security）、`securitySchemes` **仍是 3**
  //    （它挂的是既有的 `X-Teacher-Staff-No`，没引入第四个 scheme）。
  //    ⚠️ 它与 `/api/teacher/students/{id}/weekly-sheet`（Task 8）与 `…/home`（Plan 04
  //    收尾波）两个既有教师侧变体**同址、同姿势**：同一道 `require_teaches_student`
  //    （管理员越过任教范围）、而响应模型**复用**学生侧那一个 `NormalizedSelfRead`
  //    （故 `/openapi.json` 上两个端点指向**同一格** schema，前端生成的 TS 类型只有一份）。
  //    ⚠️ 四档 + 管理员矩阵在**第 13 步**逐字钉；三格同源的真取证在**第 14 步**。
  //    ⚠️ 它**不进** `catalog/resources.ts` 的那 23 行（特例端点），
  //    故本步①–④那几拍（数的是 23 行）**一个都没变**。
  //    ⚠️⚠️ 而**第二件事（绑定限流）不动这五格任何一格**：`bind` 两个端点各多了一个
  //    `request: Request` 形参，而 FastAPI 对 `Request` 标注特殊处理、**不进 OpenAPI**
  //    （与 Plan 06 Task 3 给 `login` 加同一个形参时逐字同一条口径），
  //    故「路径 / 操作数 / 挂 security 的操作数」三格一个都没变。⚠️ 而它们的
  //    **docstring 就是 `/openapi.json` 的 `description`**，故 `npm run gen:api`
  //    的产物**仍然变了**（那一格由第 15 步之外的那条后端守卫钉：
  //    `test_the_generated_typescript_client_matches_the_current_openapi_document`）。
  // ⚠️⚠️ **Plan 08 Task 1 又把四格各抬了一格**（+ `GET /api/read-audit-logs`：
  //    **敏感读**留痕的管理员只读端点；派单 §2 第 8 条裁定「与既有 `/api/audit-logs`
  //    同一条口径」，故它挂的是既有的 `X-Teacher-Staff-No`）：
  //    路径模板 74 → **75**、操作 102 → **103**、挂 security 84 → **85**、GET 63 → **64**。
  //    ⚠️ 而**匿名 GET 仍是 15**、`securitySchemes` **仍是 3**、
  //    「未定型响应」**仍是 24**（新端点有 `response_model=ReadAuditLogPageRead`，
  //    故它是**定型**的；那 24 个 = 23 个泛型 list + `/api/health`，一个都没动）。
  //    ⚠️ 它**不进** `catalog/resources.ts` 的那 23 行（特例端点，与 `/api/audit-logs`
  //    同一族），故本步①–④那几拍（数的是 23 行）**一个都没变**。
  //    ⚠️⚠️ 而**读审计本身不动这五格任何一格**：判据住在中间件里
  //    （`app/api/read_audit.py` 的那张「路由模板 → 归类」表），
  //    **46 个敏感读端点一个字节都没改** —— 那正是派单 §2 第 3 条那个取舍要的形状
  //    （`Depends(...)` / 装饰器两个候选都要改 46 个端点，而「忘了挂」是静默的）。
  //    ⚠️ 而 `/openapi.json` 的**字节仍然变了**（420 367 → 428 074 B）：
  //    新端点自己的那一份 schema + description。
  eq('路径模板 75 个（Plan 08 Task 1 起 74 → 75：+/api/read-audit-logs）',
    apiPaths.length, 75)
  eq('操作 103 个（Plan 08 Task 1 起 102 → 103）', ops, 103)
  eq('挂 security 的 85 个（Plan 05A 是 52；安全收紧波 +28；收尾波 ③ +1；Task 5 +1 = audit-logs；'
    + 'Task 9 +1 = normalized/me；Task 10 +1 = teacher/…/normalized；'
    + 'Plan 08 Task 1 +1 = read-audit-logs）', secured, 85)
  eq('GET 64 个（Plan 08 Task 1 起 63 → 64：+GET /api/read-audit-logs）', gets, 64)
  eq('其中匿名 GET 15 个（安全收紧波之前是 44；收尾波 ③ 又关掉 normalized 那一扇；'
    + 'Task 5 / Task 9 / Task 10 / Plan 08 Task 1 各加一个端点都挂 security，'
    + '故这一格四波都不变）', getsAnon, 15)

  // ⑥ ⚠️ **安全收紧波新加的一拍**（控制者裁定 5 逐字要求）：
  //    「学生键资源匿名读 = 401」。⚠️ 它**必须实发请求**，不能只读 openapi 的
  //    `security` 那一格：`Security(...)` 只**声明**（`auto_error=False`，缺头不抛），
  //    判定由 `Depends(...)` 做 —— 只挂前者会得到「spec 上写了、实际谁都放行」，
  //    而那一档在 openapi 面上与「挂对了」**逐字相同**。
  //    ⚠️ 清单**字面写死**（硬规矩 #35），不从 `paths` 反推：两侧同源的话，
  //    「把某一行的 read_scope 改回 None」会同时改掉两边、断言恒成立。
  //    ⚠️ 13 个学生键资源 × 2 个 GET = 26 发，逐个断 401 + `unauthenticated`。
  const studentKeyed = [
    'enrollments', 'fitness-test-results', 'body-compositions', 'interest-surveys',
    'derived-metrics', 'stratification-results', 'prescriptions', 'weekly-adjustments',
    'rpe-records', 'training-logs', 'mini-tests', 'alerts', 'notifications',
  ]
  eq('⑥ 学生键资源恰好 13 个（与后端 catalog 的三档表对拍）', studentKeyed.length, 13)
  let anonDenied = 0
  for (const resource of studentKeyed) {
    const detailKey = Object.keys(paths).find(
      (p) => p.startsWith(`/api/${resource}/{`) && p.split('/').length === 4,
    )
    check(`⑥ ${resource} 在 openapi 里有成员路径`, detailKey !== undefined, String(detailKey))
    for (const url of [`/api/${resource}`, `/api/${resource}/424243`]) {
      const anon = await req('GET', url, { quiet: true, record: false })
      // ⚠️ 成员那一发用**不存在**的主键 424243：401 必须排在 404 之前
      //    （身份依赖在路由匹配之后、端点体之前跑），故两档都应当是 401。
      //    ⚠️ 若它回 404，说明闸门根本没挂上（路由匹配到了、端点体跑了）。
      if (!check(`⑥ 匿名 GET ${url} → 401`, anon.status === 401, `${anon.status}`)) continue
      check(`⑥ 而它的 code 是 unauthenticated`, codeOf(anon) === 'unauthenticated', String(codeOf(anon)))
      anonDenied += 1
    }
    // ⚠️ 绿档同时在场（硬规矩 #50）：同一个 URL 带**教师** jar 就不是 401
    //    （否则「后端整个挂了」也能让上面 26 拍全绿）。
    // ⚠️⚠️ **Plan 06 Task 8 改了这一拍的说明文字、没改它的判据**：
    //    改前它写的是「教职那一档是全读」，而今天教师档读到的是**收窄后**的行数
    //    （`read_scope="staff_taught"`）。⚠️ 状态码仍然是 200 —— 第四档收的是
    //    「读到多少行」，不是「能不能读」，故本拍的判据（`status === 200`）
    //    一个字都不用改；「读到多少行」由下面 ⑦ 那一拍钉。
    const asStaff = await req('GET', `/api/${resource}?limit=1`, { as: 'teacher', quiet: true, record: false })
    check(`⑥ 教师会话 GET /api/${resource} → 200（第四档：能读，但只读自己任教班级的学生行）`,
      asStaff.status === 200, `${asStaff.status}`)
  }
  eq('⑥ 26 发匿名请求全部 401（13 个资源 × 集合 + 成员）', anonDenied, 26)

  /* ⑦ ⚠️⚠️ **Plan 06 Task 8 新加的一拍**（派单 §4 第 3 条逐字要求的
     「`total` 过滤断言」）：教师档读到的是**收窄后**的行数，而 `total` 与 `items`
     **走同一个 WHERE**。
     ⚠️ 三格判据，各挡一个失效形态：
     · **教师 < 管理员**：挡「第四档整个没生效」（那会让两个数相等 = 全校全读）；
     · **每一行的 `student_id` 都在第 7 步算出来的任教名册里**：挡「过滤条件写错成
       恒真」与「按别的键过滤」；
     · **`items.length === total`**（在 `limit=200` 覆盖得住的前提下）：挡
       「在 Python 里筛了 items、却把全表计数留给 total」——那个失效会让前端
       分页器显示一个翻不到的页数。
     ⚠️ 两个数**字面写死**（硬规矩 #35：演示库的 seed 是 20250828、60 人，
     与第 0 步那一批「32 / 13 / 6」同一条口径）。改前实测（教师档 = 全校全读）：
     `training-logs` 是 **840**、`alerts` 是 **32**；改后 T0001 是 **574** / **21**
     （他任教 41 / 60 人）。
     ⚠️⚠️ 而**管理员档的 `training-logs` 是 841 而不是 840**：第 6 步用学生 4 的头
     自己打过一次卡（`POST /api/training-logs`），故到第 12 步时全表多了一行。
     ⚠️ 那一行**不在** T0001 的任教范围里（学生 4 不在他的班里 —— 第 7 步逐字断言过
     这一格），故教师档仍然是 574。⚠️ 于是「841 vs 574」这一对数字同时钉住了两件事：
     「第四档生效了」与「第 6 步那次写入落在了谁身上」。                        */
  const taughtIds = new Set(SHARED.taughtStudents ?? [])
  check('⑦ 第 7 步算出来的任教名册非空（否则下面三拍全是空转）',
    taughtIds.size > 0, `${taughtIds.size} 人`)
  for (const [resource, wantTeacher, wantAdmin] of [
    ['training-logs', 574, 841],
    ['alerts', 21, 32],
  ]) {
    const asTeacher = await req('GET', `/api/${resource}?limit=200`,
      { as: 'teacher', quiet: true, record: false })
    const asAdmin = await req('GET', `/api/${resource}?limit=200`,
      { as: 'admin', quiet: true, record: false })
    const t = asTeacher.json ?? {}
    const a = asAdmin.json ?? {}
    eq(`⑦ /api/${resource}：教师档 total = ${wantTeacher}（T0001 任教的 41 人的行数）`,
      t.total, wantTeacher)
    eq(`⑦ /api/${resource}：管理员档 total = ${wantAdmin}（全表；改前教师档也是这个数）`,
      a.total, wantAdmin)
    check(`⑦ /api/${resource}：教师档 < 管理员档（第四档真的生效了，不是「两档都全读」）`,
      (t.total ?? 0) < (a.total ?? 0), `${t.total} vs ${a.total}`)
    check(`⑦ /api/${resource}：教师档的每一行都属于他任教的学生`,
      (t.items ?? []).every((r) => taughtIds.has(r.student_id)),
      `${(t.items ?? []).length} 行；不在名册里的 `
      + `${(t.items ?? []).filter((r) => !taughtIds.has(r.student_id)).length} 行`)
    // ⚠️ 「`total` 与 `items` 同源」这一拍**分两支**，而分支点是 `limit=200`
    //    截不截得完（`alerts` 21 行截得完、`training-logs` 574 行截不完）：
    //    · 截得完 → `items.length === total`（「在 Python 里筛了 items、却把全表计数
    //      留给 total」那一档会红）；
    //    · 截不完 → `items.length === 200`，即 **LIMIT 作用在已过滤的行上**。
    //      那一格正是派单 §1「SQL 层做，不要拉全量再在 Python 里过滤」的可执行判据：
    //      若实现是先 `LIMIT 200` 再在 Python 里筛，教师档的 items 会**少于** 200
    //      （200 行全校打卡里属于他的只有约 137 行），而 `total` 还会是 840。
    if ((t.total ?? 0) <= 200) {
      check(`⑦ /api/${resource}：total 与 items 同源（items.length === total）`,
        (t.items ?? []).length === t.total, `${(t.items ?? []).length} vs ${t.total}`)
    } else {
      check(`⑦ /api/${resource}：LIMIT 作用在**已过滤**的行上（items 满 200）`,
        (t.items ?? []).length === 200, `${(t.items ?? []).length} 行 / total ${t.total}`)
    }
  }

  /* ⑧ ⚠️⚠️ **Plan 06 Task 8b 新加的一拍**（第五档 `staff_taught_section` 的
     端到端取证）：`weekly-class-reports` 是**班级键**资源，而它的
     `progress_board` 那个 JSON 列逐条带 `student_id` + `change_pct`（= 那个班的进步榜）。
     改前它是 `read_scope="staff"`（任何在册教职全读），故 T0001 能
     `GET /api/weekly-class-reports/{1..5}` 五个各 200、读到**别的班**的进步榜
     （Task 8 顶回 2）。⚠️ 而**前端页面上看不出这一格**：教师端周报页读的是
     `GET /api/dashboard/weekly-class-report/{id}`，那一个早就有
     `require_teaches_section` —— 泄漏面是 **API**，不是 UI，故只有本步能钉它。
     ⚠️ 三格判据与 ⑦ 那三格**同构**，只是键从**学生**换成**班**：
     · **教师 < 管理员**：挡「第五档整个没生效」（两个数相等 = 全校全读）；
     · **每一行的 `course_section_id` 都在第 7 步算出来的「我任教的班」里**：
       挡「过滤条件写错成恒真」与「按别的键过滤」；
     · **read-one 与 list 同源**：教师读**别的班**那一份 → 403、读**自己班**那一份 → 200。
     ⚠️ 两个数**字面写死**（硬规矩 #35：演示库 5 个班各一份周报；
     T0001 任教班 1 与 3 → 2 份）。
     ⚠️⚠️ 而 `SHARED.mySections` 的算式是 `course_section.teacher_id == 我`
     （**不判学期**），后端第五档的算式（`taught_section_ids`）**判学期**；
     演示库上两者是同一个集合（`app/seed/generate.py` 把每一个班都写进
     `is_current` 那一个学期），故本拍成立。⚠️ 一个跨学期的班一旦出现，
     本拍会红在「教师档的每一行都挂在他任教的班上」——那是**真红**，
     届时期望侧要改成从后端读，而不是把这一拍删掉。
     ⚠️⚠️ 而 Task 8b 的另一半（**第二根轴** orphan：班级级预警 / 发给教师的站内信）
     在 smoke 上**没有对应的一拍**，且这不是漏掉的：演示库里那两类行各是 **0**
     （班级级规则 `YELLOW_CLASS_RPE_HIGH` 的阈值是班级 RPE 均值 > 7，实测最高 6.93；
     19 行站内信全是 `recipient_kind='student'`），而 `backend/data/**` 是指纹禁区、
     一个字节都不许动，故 smoke 造不出那两类行。那一格是 **pytest-only 覆盖**
     （`tests/api/test_crud.py` 用夹具造行，三条守卫 + 六个定点变异），
     已登记为待清扫：「若要 smoke 也覆盖，需要一个不碰指纹禁区的造数入口」。   */
  const mySections = new Set(SHARED.mySections ?? [])
  check('⑧ 第 7 步算出来的「我任教的班」非空（否则下面几拍全是空转）',
    mySections.size > 0, `${mySections.size} 个班：${JSON.stringify([...mySections])}`)
  {
    const reportsAsTeacher = await req('GET', '/api/weekly-class-reports?limit=200',
      { as: 'teacher', quiet: true, record: false })
    const reportsAsAdmin = await req('GET', '/api/weekly-class-reports?limit=200',
      { as: 'admin', quiet: true, record: false })
    const t = reportsAsTeacher.json ?? {}
    const a = reportsAsAdmin.json ?? {}
    eq('⑧ /api/weekly-class-reports：教师档 total = 2（T0001 任教的班 1 与 3 各一份）',
      t.total, 2)
    eq('⑧ /api/weekly-class-reports：管理员档 total = 5（全表；改前教师档也是这个数）',
      a.total, 5)
    check('⑧ 教师档 < 管理员档（第五档真的生效了，不是「两档都全读」）',
      (t.total ?? 0) < (a.total ?? 0), `${t.total} vs ${a.total}`)
    check('⑧ 教师档的每一行都挂在他任教的班上',
      (t.items ?? []).every((r) => mySections.has(r.course_section_id)),
      `${(t.items ?? []).length} 行；不在「我任教的班」里的 `
      + `${(t.items ?? []).filter((r) => !mySections.has(r.course_section_id)).length} 行`)
    check('⑧ total 与 items 同源（items.length === total）',
      (t.items ?? []).length === t.total, `${(t.items ?? []).length} vs ${t.total}`)
    const theirs = (a.items ?? []).find((r) => !mySections.has(r.course_section_id)) ?? null
    check('⑧ 管理员档里找得到一份**不是**他任教的班的周报（否则下面三拍是空转）',
      theirs !== null,
      theirs === null ? '（没有）' : `#${theirs.id} 挂班 ${theirs.course_section_id}`)
    if (theirs !== null && (t.items ?? []).length > 0) {
      const denied = await req('GET', `/api/weekly-class-reports/${theirs.id}`,
        { as: 'teacher', quiet: true, record: false })
      eq(`⑧ 教师 read-one 别的班那一份（#${theirs.id}）→ 403`, denied.status, 403)
      eq('⑧ 而它的 code 是 forbidden', codeOf(denied), 'forbidden')
      const allowed = await req('GET', `/api/weekly-class-reports/${t.items[0].id}`,
        { as: 'teacher', quiet: true, record: false })
      eq('⑧ 教师 read-one **自己班**那一份 → 200（绿档同时在场，硬规矩 #50）',
        allowed.status, 200)
      const board = (allowed.json ?? {}).progress_board
      check('⑧ 而自己班那一份的响应体里确实有 progress_board、且它里面确实带 student_id'
        + '（反空转：上面那个 403 挡住的正是这一格泄漏面，不是「响应体本来就空」）',
        Array.isArray(board?.top) && board.top.some((r) => Number.isInteger(r.student_id)),
        JSON.stringify(board ?? null).slice(0, 90))
    }
  }
})

await step(13, '学生端那三个窄端点：/api/students/{id}/notifications、/api/mini-tests/normalized 与 /normalized/me', async () => {
  // ⚠️ 这两个端点是 Plan 04 Task 3 的后端小修波加的 / 摘的：
  //    前者是新加的窄端点（学生头、裸数组、服务端已过滤 + 已排序），
  //    后者是**摘掉了教师头**（改成匿名）。
  const mine = await req('GET', `/api/students/${STUDENT}/notifications`, { as: studentJar() })
  eq('学生头 → 200', mine.status, 200)
  check('响应是**裸数组**（不是分页信封：本端点刻意不回那三个无信息的键）',
    Array.isArray(mine.json), Array.isArray(mine.json) ? `${mine.json.length} 条` : typeof mine.json)
  const rows = Array.isArray(mine.json) ? mine.json : []
  check('只含自己的行', rows.every((r) => String(r.recipient_id) === String(STUDENT)),
    `recipient_id=${JSON.stringify([...new Set(rows.map((r) => r.recipient_id))])}`)
  check('已按 created_at 降序（排序在服务端，前端不要再 sort）',
    rows.every((r, i) => i === 0 || rows[i - 1].created_at >= r.created_at), `${rows.length} 条`)
  const shapeOk = rows.every((r) => typeof r.id === 'number' && 'is_read' in r && 'title' in r)
  check('每一项都是 NotificationRead 的形状（10 列）', shapeOk,
    rows.length > 0 ? `键数=${Object.keys(rows[0]).length}` : '（0 条，跳过键数核实）')

  const anon = await req('GET', `/api/students/${STUDENT}/notifications`)
  eq('匿名 → 401', anon.status, 401)
  eq('code 是 unauthenticated', codeOf(anon), 'unauthenticated')

  const cross = await req('GET', `/api/students/${STUDENT}/notifications`, { as: studentJar(5) })
  eq('越权（学生 5 读学生 4 的）→ 403', cross.status, 403)
  eq('code 是 forbidden', codeOf(cross), 'forbidden')

  const asTeacher = await req('GET', `/api/students/${STUDENT}/notifications`, { as: 'teacher' })
  eq('教师会话 → 403（本端点只做学生侧；Plan 05A 之前是 401，跨 kind 改成 403）',
    asTeacher.status, 403)
  eq('code 是 forbidden', codeOf(asTeacher), 'forbidden')

  /* ⚠️⚠️ **交付前收尾波 ③ 改了本端点的身份口径**：改前它是**匿名**的
     （Plan 04 Task 3 的小修波摘掉了教师头），那一波给它挂上了「学生或教职皆可」。
     理由是安全收紧波已经把它当年那张对账表的两条腿都抽掉了（匿名读
     `/api/mini-tests` 与 `/api/enrollments` 今天各是 **401**），于是它成了
     **最后一个匿名的学生键读端点**。⚠️ 而它不能只挂身份：实测
     `entries[i].squat_score` **逐行等于** `mini_test.squat_30s_count`
     （spec §8.1「深蹲得分 = 次数」），`composite` 又能把它反推出来，
     故端点对**学生档做了列级收窄**（那两格对别人的行是 `null`），
     而全班的 `shuttle_score`（百分位）照常给 —— `MiniTest.vue` 要它算名次。
     逐字取证住在 `backend/app/api/routers/feedback.py` 的 `normalized_scores`。

     ⚠️⚠️ **Plan 06 Task 8 又给它加了行级收窄**（派单 §2 点名要一起关的那个跨范围洞）：
     收尾波之后它对**教师没有任何任教闸门**，故任何教师能读到全校 5 个班的班内百分位
     （改前实测：T0001 只任教班 1 与班 3，却拿到 **5** 个班的 `entries`，
     即班 2 / 班 4 / 班 5 的逐人百分位与深蹲次数）。今天三档：
     学生只留自己 `enrollment` 的班、教师只留自己任教的班、管理员全留。
     ⚠️⚠️ 而派单 §2 写的处置是「否则 **403**」，实测下那一格**无对象**（已顶回）：
     本端点**没有** `course_section_id` 这个查询参数（签名逐字只有
     `semester_id` + `week` 两格），故不存在「请求某一个班的百分位」这个动作
     —— 它一次就把全部班都回了。于是收窄只能是**响应级**的（裁 `sections` 数组）。
     ⚠️ 于是下面这一组从「6 拍」变成「13 拍」：三档身份 + 裁班的两侧 + 列级收窄的
     两侧 + 键集合 + `unassigned` 的两档。

     ⚠️⚠️ **Plan 06 Task 9 把「列级收窄」那两拍换成了「schema 级摘列」的三拍**：
     `squat_score` 与 `composite` 已从 `NormalizedEntryRead` 上**摘掉**，故班级端点的
     `entries[i]` 今天只有三格（`student_id` / `mini_test_id` / `shuttle_score`），
     而**四种身份的键集合逐字相同**（响应体不再有任何一列随身份而变；随身份而变的
     只有「哪些班」，那是上面 Task 8 那一节的事）。
     ⚠️ 摘列的理由是**契约面**的：列级收窄让同一个操作的响应体随身份而变，
     而 OpenAPI 只有一张 schema → `npm run gen:api` 生成出来的 `schema.d.ts`
     宣称「那两格永远有值」，是一份**假契约**。
     ⚠️ 本人那两格搬到了 `GET /api/mini-tests/normalized/me`（**仅学生本人**）上，
     它的形状**恒定**（恒为「调用者自己的那几行、全列」），故它是真契约。
     ⚠️ 于是下面这一组再加「窄端点四档矩阵 + 两个端点对同一格逐字相等 + 窄端点只回
     本人的行」三组拍。 */
  const nUrl = '/api/mini-tests/normalized?semester_id=2&week=6'
  const nAnon = await req('GET', nUrl, { quiet: true })
  eq('mini-tests/normalized 匿名 → 401（改前是 200；不带参数那一发改前是 422）',
    nAnon.status, 401)
  eq('code 是 unauthenticated', codeOf(nAnon), 'unauthenticated')
  const nBare = await req('GET', '/api/mini-tests/normalized', { quiet: true })
  eq('⚠️ 不带查询参数那一发也是 401 而**不是** 422（422 = 过了鉴权、挂在参数校验 = 门还开着）',
    nBare.status, 401)

  // ⚠️ **管理员档是下面两侧比对的基准**（他越过任教范围 → 5 个班全留）。
  //    改前这一组用**教师档**当基准，而本波之后教师档自己就是被收窄的那一侧，
  //    拿它当基准会让「裁班」这件事无从对照（两侧同源 = 断言恒成立）。
  const asAdmin = await req('GET', nUrl, { as: 'admin', quiet: true })
  eq('管理员会话 → 200', asAdmin.status, 200)
  const aSections = asAdmin.json?.sections ?? []
  const aIds = aSections.map((s) => s.course_section_id).sort((x, y) => x - y)
  eq('管理员档：5 个班全留（越过任教范围）', aIds.length, 5)
  const aEntries = aSections.flatMap((s) => s.entries ?? [])

  const normalized = await req('GET', nUrl, { as: 'teacher', quiet: true })
  eq('教职会话 → 200', normalized.status, 200)
  // ⚠️ `scored_count` **不在顶层**：响应体是
  //    `{semester_id, week, sections: [{course_section_id, scored_count, entries: [...]}]}`。
  const sections = normalized.json?.sections ?? []
  check('sections 非空', sections.length > 0, `${sections.length} 个班`)
  check('每个班都带 scored_count（约束第 11 条：== 1 时前端要显示「无排名」）',
    sections.length > 0 && sections.every((s) => typeof s.scored_count === 'number'),
    `scored_count=${JSON.stringify(sections.map((s) => s.scored_count))}`)
  // ⚠️⚠️ **Plan 06 Task 9 改了本拍的判据**（改前断的是「每一项都有 composite」）：
  //    `composite` 与 `squat_score` 已从 `NormalizedEntryRead` 上摘掉，
  //    故本拍今天断的是「每一项都**只有**那三格、且 `shuttle_score` 是数或 null」。
  //    ⚠️ 这不是放宽判据（硬规矩 #92）：改前那一拍钉的是「有值」，
  //    而它钉的那一格**已经不在契约里了**；今天钉的是「键集合恰好是三格」，
  //    它比改前**更强**（改前多给一列也绿，今天多给一列当场红）。
  check('教职档：entries 里每一项的键集合**恰好**是那三格（Plan 06 Task 9 的 schema 级摘列）',
    sections.every((s) => Array.isArray(s.entries) && s.entries.every((e) =>
      JSON.stringify(Object.keys(e).sort())
        === JSON.stringify(['mini_test_id', 'shuttle_score', 'student_id']))),
    `第一个班 ${sections[0]?.entries?.length ?? 0} 项；`
    + `键=${JSON.stringify(Object.keys(sections[0]?.entries?.[0] ?? {}).sort())}`)
  check('教职档：那两格**一个都不在**（`squat_score` 逐行等于 `squat_30s_count`、'
    + '`composite` 能反推它 → 两格必须一起摘，只摘一格等于没摘）',
    sections.every((s) => s.entries.every((e) => !('squat_score' in e) && !('composite' in e))),
    `含 squat_score 的 ${sections.flatMap((s) => s.entries).filter((e) => 'squat_score' in e).length} 项`)
  out(`    scored_count = ${JSON.stringify(sections.map((s) => s.scored_count))}`)

  /* ⚠️⚠️ **行级收窄（本波新加的三拍）**：教师只留自己任教的班。
     期望侧是第 7 步算出来的 `SHARED.mySections`（从 `/api/course-sections` 按
     `teacher_id == 我` 反查），而后端那一份判据住在 `app/api/deps.py` 的
     `taught_section_ids`（SQL 层）—— **两侧不同源**，同源的话「把裁班写成恒真」
     会同时改掉两边、断言恒成立。                                              */
  const tIds = sections.map((s) => s.course_section_id).sort((x, y) => x - y)
  eq(`教师档：只留 ${TEACHER} 任教的 ${SHARED.mySections.length} 个班（实测是 1 与 3）`,
    JSON.stringify(tIds),
    JSON.stringify([...SHARED.mySections].sort((x, y) => x - y)))
  check('教师档：管理员那 5 个班里**别的班一个都没漏进来**（改前这一拍会红：5 == 5）',
    tIds.length < aIds.length && tIds.every((id) => aIds.includes(id)),
    `教师 ${JSON.stringify(tIds)} / 管理员 ${JSON.stringify(aIds)}`)
  check('教师档：**整班一起留**（留下的每个班，行数与 scored_count 与管理员档逐字相同）'
    + '—— 裁的是班、不是班里的人，否则百分位与名次会静默漂移',
    tIds.length > 0 && tIds.every((id) => {
      const mine = sections.find((s) => s.course_section_id === id)
      const full = aSections.find((s) => s.course_section_id === id)
      return mine.entries.length === full.entries.length
        && mine.scored_count === full.scored_count
    }),
    `教师 ${JSON.stringify(sections.map((s) => s.entries.length))} / `
    + `管理员 ${JSON.stringify(aSections.map((s) => s.entries.length))}`)

  // ⚠️ 学生档：只留自己 enrollment 的班，而班内的百分位照常给（前端要它算名次），
  //    那两格原始值只对本人给。
  const asStudent = await req('GET', nUrl, { as: studentJar(), quiet: true })
  eq('学生会话 → 200（学生页要照常工作）', asStudent.status, 200)
  const sSections = asStudent.json?.sections ?? []
  const sEntries = sSections.flatMap((s) => s.entries ?? [])
  // ⚠️ 期望侧从**他自己**读 `/api/enrollments` 拿（`staff_taught` 档下学生只读自己的行），
  //    而不是从教师档或管理员档推 —— 三档各算一次，任一份算错都会红在这里。
  const myEnrollments = (await req('GET', '/api/enrollments?limit=200',
    { as: studentJar(), quiet: true })).json?.items ?? []
  const mySectionIds = [...new Set(myEnrollments.map((e) => e.course_section_id))]
    .sort((x, y) => x - y)
  eq(`学生档：只留他自己 enrollment 的 ${mySectionIds.length} 个班（演示库上每人恰好 2 个）`,
    JSON.stringify(sSections.map((s) => s.course_section_id).sort((x, y) => x - y)),
    JSON.stringify(mySectionIds))
  check(`学生档：${TEACHER} 任教的那 2 个班一个都不在里面`
    + `（学生 ${STUDENT} 不在他的任教范围里，第 7 步已实测过这一格）`,
    sSections.every((s) => !tIds.includes(s.course_section_id)),
    `学生 ${JSON.stringify(sSections.map((s) => s.course_section_id))} / 教师 ${JSON.stringify(tIds)}`)
  check('学生档：他那些班的**行数、student_id 与百分位**与管理员档逐字相同'
    + '（裁的是班、不是班里的人 → 名次因此不是恒为 1）',
    sEntries.length > 0 && sSections.every((s) => {
      const full = aSections.find((x) => x.course_section_id === s.course_section_id)
      return full !== undefined
        && s.entries.length === full.entries.length
        && s.entries.every((e, i) => e.student_id === full.entries[i].student_id
          && e.shuttle_score === full.entries[i].shuttle_score)
    }),
    `学生 ${sEntries.length} 行 / 管理员 ${aEntries.length} 行；`
    + `百分位=${JSON.stringify(sEntries.slice(0, 4).map((e) => e.shuttle_score))}`)
  const myRows = sEntries.filter((e) => e.student_id === STUDENT)
  const otherRows = sEntries.filter((e) => e.student_id !== STUDENT)
  /* ⚠️⚠️ **Plan 06 Task 9 换了这三拍的判据**（改前断的是「本人那两格照常给值、
     别人的行那两格一律 null、键集合与管理员档逐字相同（收窄走 null、不是删键）」）。
     那三拍钉的是**列级**收窄，而本波把它抬成了 **schema 级摘列**：那两格今天
     **对谁都不存在**。⚠️ 判据因此更强了（硬规矩 #92 的正面读法：不是放宽，
     是「改前多给一列也绿、今天多给一列当场红」）：
     ① 学生 / 教师 / 管理员三档的键集合**逐字相同**（= 响应体不再随身份而变）；
     ② 那两格在**任何一档**里都不出现（`in` 判定，不是 `=== null`：
        `null` 与「没有这个键」在 JS 里是两件事，而今天应当是后者）；
     ③ 本人的那两格改由**窄端点**给（下面那一组）。                        */
  const keySetOf = (entries) => [...new Set(entries.map((e) => JSON.stringify(Object.keys(e).sort())))]
  check('① 学生 / 教师 / 管理员三档的 entries 键集合**逐字相同**'
    + '（= 响应体不再有任何一列随身份而变；随身份而变的只有「哪些班」）',
    sEntries.length > 0 && tIds.length > 0 && aEntries.length > 0
      && JSON.stringify(keySetOf(sEntries)) === JSON.stringify(keySetOf(aEntries))
      && JSON.stringify(keySetOf(aEntries))
        === JSON.stringify(keySetOf(sections.flatMap((s) => s.entries ?? []))),
    `学生=${JSON.stringify(keySetOf(sEntries))} 管理员=${JSON.stringify(keySetOf(aEntries))} `
    + `教师=${JSON.stringify(keySetOf(sections.flatMap((s) => s.entries ?? [])))}`)
  check('② `squat_score` 与 `composite` 在**任何一档**里都不再出现'
    + '（⚠️ 判据是 `in`，不是 `=== null`：那两格今天根本不在契约里）',
    [...sEntries, ...aEntries, ...sections.flatMap((s) => s.entries ?? [])]
      .every((e) => !('squat_score' in e) && !('composite' in e)),
    `三档合计 ${sEntries.length + aEntries.length + sections.flatMap((s) => s.entries ?? []).length} 行`)
  check(`②bis 而本人（#${STUDENT}）那一行**仍在**（${myRows.length} 行；`
    + '⚠️ `>= 1` 而不是 `== 1`：一个学生同一学期可能在两个班）',
    myRows.length >= 1 && myRows.every((e) => typeof e.shuttle_score === 'number'),
    myRows.length >= 1 ? JSON.stringify(myRows) : `本人行数 ${myRows.length}`)
  check(`②ter 别人的行**照常给全**（${otherRows.length} 行）：摘的是**列**、不是行`,
    otherRows.length > 0 && otherRows.every((e) => 'shuttle_score' in e),
    `${otherRows.length} 行`)

  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 06 Task 9 新加的一组：窄端点 `GET /api/mini-tests/normalized/me`**
     它是 schema 级摘列**欠下的那一格的还账**（本人要看自己的深蹲得分与综合分，
     而 `MiniTest.vue` 第 02 块的两个 `StatBlock` 读的就是它）。
     ⚠️ 它存在的**全部理由**是「形状恒定」：恒为「调用者自己的那几行、全列」，
     故 `schema.d.ts` 上说有值的格，响应里就有值 —— 那正是班级端点此前给不出的。
     ------------------------------------------------------------------ */
  const meUrl = '/api/mini-tests/normalized/me?semester_id=2&week=6'
  const meAnon = await req('GET', meUrl, { quiet: true })
  eq('窄端点：匿名 → 401', meAnon.status, 401)
  eq('窄端点：code 是 unauthenticated', codeOf(meAnon), 'unauthenticated')
  const meBare = await req('GET', '/api/mini-tests/normalized/me', { quiet: true })
  eq('窄端点：不带查询参数那一发也是 401 而**不是** 422（先过鉴权、后挂校验）',
    meBare.status, 401)
  const meTeacher = await req('GET', meUrl, { as: 'teacher', quiet: true })
  eq('窄端点：普通教师 → **403**（「『我自己』对教职无意义」；⚠️ 不是 401：'
    + '请求者已经被认出来了，只是不是这个端点要的那一类人）', meTeacher.status, 403)
  eq('窄端点：教师那一档 code 是 forbidden', codeOf(meTeacher), 'forbidden')
  const meAdmin = await req('GET', meUrl, { as: 'admin', quiet: true })
  eq('窄端点：管理员 → **403**（管理员也是一行 teacher，故他也没有「我自己」那个学生）',
    meAdmin.status, 403)
  eq('窄端点：管理员那一档 code 是 forbidden', codeOf(meAdmin), 'forbidden')

  const meSelf = await req('GET', meUrl, { as: studentJar(), quiet: true })
  eq('窄端点：学生本人 → 200', meSelf.status, 200)
  const selfBody = meSelf.json ?? {}
  check('窄端点：响应体恰好三个信封键（⚠️ **没有** `unassigned`：那一格是班级端点的，'
    + '而两个键集合不同形正是「本拍没有落到班级端点上」的证据）',
    JSON.stringify(Object.keys(selfBody).sort()) === JSON.stringify(['sections', 'semester_id', 'week']),
    JSON.stringify(Object.keys(selfBody).sort()))
  const selfRows = selfBody.sections ?? []
  check(`窄端点：${mySectionIds.length} 个班各一行（= 他 enrollment 的那几个班，`
    + '与班级端点学生档的班号逐字相同 → 两个端点共用同一份判据）',
    selfRows.length === mySectionIds.length
      && JSON.stringify(selfRows.map((r) => r.course_section_id).sort((x, y) => x - y))
        === JSON.stringify(mySectionIds),
    `窄=${JSON.stringify(selfRows.map((r) => r.course_section_id))} `
    + `班级=${JSON.stringify(sSections.map((s) => s.course_section_id).sort((x, y) => x - y))}`)
  check('窄端点：每一行**恰好五格、且三格分数都是数**（全列 → 它是真契约）',
    selfRows.length > 0 && selfRows.every((r) =>
      JSON.stringify(Object.keys(r).sort()) === JSON.stringify(
        ['composite', 'course_section_id', 'mini_test_id', 'shuttle_score', 'squat_score'])
      && typeof r.squat_score === 'number' && typeof r.composite === 'number'),
    selfRows.length > 0 ? JSON.stringify(selfRows) : '0 行')
  /* ⚠️ **两个端点对同一格必须逐字相等**（后端两个端点共用 `_normalized_sections`）。
     少了这一拍，「有人给窄端点另写了一份分组/取样」是静默的：两边的断言各自都绿，
     而学生在同一屏上会看到「折返班内百分位」与「小测综合分」出自两套样本。 */
  /* ⚠️⚠️ **配对键必须是 `course_section_id`，不是 `mini_test_id`**（首跑实测到的红）：
     一个学生同一学期在**两个班**（行政班 + 分层班），而他那一周只有**一行** `mini_test`
     —— 后端因此把**同一行**投进两个班的 `entries` 里（各自算一次班内百分位）。
     实测学生 #4 第 6 周：两个班的 `mini_test_id` **都是 124**，而 `shuttle_score`
     分别是 98.33 与 92.5。故按 `mini_test_id` 配对会把两个班配到同一行上、
     于是「逐字相等」这一拍在**正确的实现上也会红**（首跑就是这么红的）。
     ⚠️ 判据本身一个字没改（仍然是「两个端点对同一格逐字相等」），改的只是配对键。 */
  check('窄端点 ↔ 班级端点：同一个班的 `shuttle_score` 与 `mini_test_id` 逐字相等（取样只有一份）',
    selfRows.length > 0 && selfRows.every((r) => {
      const section = sSections.find((s) => s.course_section_id === r.course_section_id)
      const twin = (section?.entries ?? []).find((e) => e.student_id === STUDENT)
      return twin !== undefined && twin.shuttle_score === r.shuttle_score
        && twin.mini_test_id === r.mini_test_id
    }),
    JSON.stringify(selfRows.map((r) => [r.course_section_id, r.mini_test_id, r.shuttle_score])))
  /* ⚠️ **而它确实是原始值**：`squat_score` 逐行等于 `mini_test.squat_30s_count`。
     少了这一拍，「摘列」挡住的可能是空气。⚠️ 期望侧从他**自己**的
     `GET /api/mini-tests`（`student_self` 档）读，两侧不同源。 */
  const myRaw = (await req('GET', '/api/mini-tests?limit=200',
    { as: studentJar(), quiet: true })).json?.items ?? []
  const rawById = new Map(myRaw.map((r) => [r.id, r]))
  check(`窄端点：squat_score 逐行等于 mini_test.squat_30s_count（对账 ${myRaw.length} 行原始成绩）`,
    selfRows.length > 0 && selfRows.every((r) => {
      const source = rawById.get(r.mini_test_id)
      return source !== undefined && source.student_id === STUDENT
        && r.squat_score === source.squat_30s_count
    }),
    JSON.stringify(selfRows.map((r) => [r.mini_test_id, r.squat_score,
      rawById.get(r.mini_test_id)?.squat_30s_count])))
  check('窄端点：composite 与那两格自洽（两项等权平均，⚠️ 用**未 round** 的百分位算完再 round，'
    + '故只到「两位小数内相等」这一档）',
    selfRows.every((r) => r.composite === null
      || Math.abs(2 * r.composite - r.shuttle_score - r.squat_score) < 0.05),
    JSON.stringify(selfRows.map((r) => [r.squat_score, r.shuttle_score, r.composite])))
  /* ⚠️ **越权那一档在签名上就不存在**：本端点没有 `student_id` 这个查询参数，
     故「请求别人的行」不是一个能被闸门挡下的动作 —— 它根本无从表达。
     ⚠️ 多送一个 `student_id` 会被 FastAPI **静默忽略**，回的仍然是本人的行。 */
  const sneaky = await req('GET',
    `/api/mini-tests/normalized/me?semester_id=2&week=6&student_id=${STUDENT + 1}`,
    { as: studentJar(), quiet: true })
  eq('窄端点：多送一个 `student_id` 仍然是 200（它被静默忽略）', sneaky.status, 200)
  check('窄端点：而它回的**仍然是本人的行**（`student_id` 恒取自会话、不接受入参）',
    JSON.stringify((sneaky.json?.sections ?? []).map((r) => r.mini_test_id).sort())
      === JSON.stringify(selfRows.map((r) => r.mini_test_id).sort()),
    JSON.stringify((sneaky.json?.sections ?? []).map((r) => r.mini_test_id)))
  const spec13 = await req('GET', '/openapi.json', { quiet: true, record: false })
  const meOp = spec13.json?.paths?.['/api/mini-tests/normalized/me']?.get
  check('窄端点：OpenAPI 上只挂 `X-Student-Id` **一个** scheme（⚠️ 不是班级端点那两个的 OR）',
    JSON.stringify(meOp?.security ?? null) === JSON.stringify([{ 'X-Student-Id': [] }]),
    JSON.stringify(meOp?.security ?? null))
  check('窄端点：OpenAPI 的 query 参数**恰好两个**（`student_id` 不在签名上）',
    JSON.stringify((meOp?.parameters ?? []).filter((p) => p.in === 'query').map((p) => p.name).sort())
      === JSON.stringify(['semester_id', 'week']),
    JSON.stringify((meOp?.parameters ?? []).map((p) => [p.name, p.in])))
  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 06 Task 10 新加的一组：教师侧变体
     `GET /api/teacher/students/{id}/normalized`**
     它是 Task 9「schema 级摘列」顶回的那一条的落地：教师端「学生详情」页要看到
     **被查看的那个学生**的「小测综合分」与「深蹲得分」，而 `NormalizedEntryRead`
     上那两格已经摘掉、本人那两格又只住在**仅学生可读**的 `/normalized/me` 上
     （教职打它是 403：「『我自己』对教职无意义」）。
     ⚠️ 它与 `/api/teacher/students/{id}/weekly-sheet`（Task 8）与 `…/home`
     （Plan 04 收尾波）两个既有变体**同址、同姿势**（同一道 `require_teaches_student`、
     同一个 `NormalizedSelfRead` schema），故本组的拍法与第 7 步那两拍平行。
     ------------------------------------------------------------------ */
  const TAUGHT = SHARED.taughtStudent
  // ⚠️ 查询参数**从数据里推**、不写死：`semester_id` 与 `week` 取「他最近一次小测」
  //    那一行（与 `StudentDetail.vue` 的 `pickedWeek` 同一条口径），于是演示库换了
  //    周次本组也不用改。
  const taughtRaw = (await req('GET', '/api/mini-tests?limit=200',
    { as: 'teacher', quiet: true, record: false })).json?.items ?? []
  const taughtRows = taughtRaw.filter((r) => r.student_id === TAUGHT)
  check(`教师侧变体：找得到 T0001 任教的学生（#${TAUGHT}）的小测行`,
    taughtRows.length > 0, `${taughtRows.length} 行`)
  const taughtWeek = Math.max(...taughtRows.map((r) => r.week))
  const taughtSemester = taughtRows.find((r) => r.week === taughtWeek)?.semester_id
  const tvQuery = `semester_id=${taughtSemester}&week=${taughtWeek}`
  const tvUrl = `/api/teacher/students/${TAUGHT}/normalized?${tvQuery}`

  // ① 匿名 → 401
  const tvAnon = await req('GET', tvUrl, { quiet: true })
  eq('教师侧变体：匿名 → 401', tvAnon.status, 401)
  eq('教师侧变体：code 是 unauthenticated', codeOf(tvAnon), 'unauthenticated')
  // ② 学生**会话** → 403（⚠️ 不是 401：请求者已经被认出来了，只是不是这一类人）
  const tvAsStudent = await req('GET', tvUrl, { as: studentJar(TAUGHT), quiet: true })
  eq('教师侧变体：学生**会话** → 403（他有 /normalized/me，本端点不接受学生）',
    tvAsStudent.status, 403)
  eq('教师侧变体：学生那一档 code 是 forbidden', codeOf(tvAsStudent), 'forbidden')
  // ③ 不任教他的教师 → 403（⚠️ 学生 4 不在 T0001 本学期任教的班里，第 7 步已实测过同一件事）
  const tvNotTaught = await req('GET',
    `/api/teacher/students/${STUDENT}/normalized?${tvQuery}`, { as: 'teacher', quiet: true })
  eq(`教师侧变体：T0001 读**不在**他班里的学生 ${STUDENT} → 403（require_teaches_student）`,
    tvNotTaught.status, 403)
  eq('教师侧变体：不任教那一档 code 是 forbidden', codeOf(tvNotTaught), 'forbidden')
  // ④ 任教他的教师 → 200
  const tvTeacher = await req('GET', tvUrl, { as: 'teacher', quiet: true })
  eq(`教师侧变体：T0001 读他任教的学生 #${TAUGHT} → 200`, tvTeacher.status, 200)
  // ⑤ 管理员（**不带任何班**）→ 200：越过任教范围，与 /home、/weekly-sheet 同一条口径
  const tvAdmin = await req('GET', tvUrl, { as: 'admin', quiet: true })
  eq('教师侧变体：管理员 T0003（不带任何班）→ 200（越过任教范围，既有口径）',
    tvAdmin.status, 200)

  /* ⑥ ⚠️⚠️ **算式复用的取证**：管理员档的响应体与学生本人读 `/normalized/me` 的
     响应体**整个字符串逐字相同**。⚠️ 两侧不同源（一侧教师 cookie、一侧学生 cookie），
     故它挡得住「新端点在 router 里重算了一遍综合分」这一档 —— 重算的实现会让两侧
     漂开（哪怕只漂在小数点第二位），而重算那一侧自己的断言还是绿的。
     ⚠️ 而管理员**不带任何班** ⇒ 不裁班 ⇒ 他看到的就是本人的全集，故两档可以直接比。 */
  const tvSelf = await req('GET',
    `/api/mini-tests/normalized/me?${tvQuery}`, { as: studentJar(TAUGHT), quiet: true })
  eq('教师侧变体：学生本人读 /normalized/me → 200（对照组）', tvSelf.status, 200)
  eq('教师侧变体（管理员档）↔ /normalized/me：**整个响应体逐字相同**'
    + '（同一个 NormalizedSelfRead schema + 同一份投影 + 同一个算式）',
    tvAdmin.text, tvSelf.text)

  /* ⑦ **裁班**：教师档只留他本学期任教的班。⚠️ 这一拍是本端点最容易做错的地方，
     而它的失效是**静默**的：若实现是「过闸门 → 把这个学生全部班里的行都回出去」，
     则 T0001 会读到他在**别人班**里的班内百分位 —— 那正是 Plan 06 Task 8 花了
     一整个 Task 在 `/api/mini-tests/normalized` 上关掉的**跨教师读口**。 */
  const tvTeacherSections = (tvTeacher.json?.sections ?? []).map((r) => r.course_section_id)
  const tvAdminSections = (tvAdmin.json?.sections ?? []).map((r) => r.course_section_id)
  check('教师侧变体：**按任教范围裁班**（教师档的班号是管理员档的子集，且全在 T0001 任教的班里）',
    tvTeacherSections.length > 0
      && tvTeacherSections.every((s) => tvAdminSections.includes(s) && SHARED.mySections.includes(s)),
    `教师=${JSON.stringify(tvTeacherSections)} 管理员=${JSON.stringify(tvAdminSections)} `
    + `T0001任教=${JSON.stringify(SHARED.mySections)}`)
  check('教师侧变体：同班那一行与管理员档**逐字相同**（裁的是**行**、不是**值**）',
    tvTeacherSections.every((s) => JSON.stringify(
      (tvTeacher.json?.sections ?? []).find((r) => r.course_section_id === s))
      === JSON.stringify((tvAdmin.json?.sections ?? []).find((r) => r.course_section_id === s))),
    JSON.stringify(tvTeacher.json?.sections))

  // ⑧ 形状恒定：每一行**恰好五格**、三格分数都是数（全列 → 真契约）
  check('教师侧变体：每一行恰好五格、且三格分数都是数（全列 → 它是真契约）',
    (tvTeacher.json?.sections ?? []).length > 0
      && tvTeacher.json.sections.every((r) =>
        JSON.stringify(Object.keys(r).sort()) === JSON.stringify(
          ['composite', 'course_section_id', 'mini_test_id', 'shuttle_score', 'squat_score'])
        && typeof r.squat_score === 'number' && typeof r.composite === 'number'),
    JSON.stringify(tvTeacher.json?.sections))
  check('教师侧变体：composite 与那两格自洽（两项等权平均，⚠️ 用**未 round** 的百分位算完再 round）',
    (tvTeacher.json?.sections ?? []).every((r) => r.composite === null
      || Math.abs(2 * r.composite - r.shuttle_score - r.squat_score) < 0.05),
    JSON.stringify((tvTeacher.json?.sections ?? []).map((r) => [r.squat_score, r.shuttle_score, r.composite])))

  // ⑨ 两个查询参数都必填（与既有 normalized 同形）
  const tvNoParams = await req('GET', `/api/teacher/students/${TAUGHT}/normalized`,
    { as: 'teacher', quiet: true })
  eq('教师侧变体：缺两个查询参数 → 422（与 /normalized、/normalized/me 同形）',
    tvNoParams.status, 422)

  // ⑩ 声明面：一个 scheme + 两个必填 query + 与 /me **指向同一个 schema**
  const tvOp = spec13.json?.paths?.['/api/teacher/students/{student_id}/normalized']?.get
  check('教师侧变体：OpenAPI 上只挂 `X-Teacher-Staff-No` **一个** scheme',
    JSON.stringify(tvOp?.security ?? null) === JSON.stringify([{ 'X-Teacher-Staff-No': [] }]),
    JSON.stringify(tvOp?.security ?? null))
  check('教师侧变体：OpenAPI 的 query 参数**恰好两个且都必填**（`semester_id` / `week`）',
    JSON.stringify((tvOp?.parameters ?? []).filter((p) => p.in === 'query')
      .map((p) => [p.name, p.required]).sort()) === JSON.stringify([['semester_id', true], ['week', true]]),
    JSON.stringify((tvOp?.parameters ?? []).map((p) => [p.name, p.in, p.required])))
  check('教师侧变体：200 的响应 schema 与 `/normalized/me` **是同一个 $ref**'
    + '（故前端生成的 TS 类型只有一份，而「教师侧与学生侧逐字同形」是类型上成立的）',
    JSON.stringify(tvOp?.responses?.['200']?.content?.['application/json']?.schema ?? null)
      === JSON.stringify(meOp?.responses?.['200']?.content?.['application/json']?.schema ?? null)
      && tvOp?.responses?.['200']?.content?.['application/json']?.schema?.$ref
        === '#/components/schemas/NormalizedSelfRead',
    JSON.stringify(tvOp?.responses?.['200']?.content?.['application/json']?.schema ?? null))

  // ⚠️ **教师档的 `unassigned` 恒为空**（本波新加的一格收窄，已顶回）：
  //    `unassigned` 的定义是「本学期没有任何 enrollment 行」，而「我任教的学生」的定义
  //    恰恰是「在我任教的班里有一条 enrollment 行」—— 两个集合必然不相交。
  //    逐字理由住在 `normalized_scores` 的函数体注释里。
  eq('教师档：unassigned 恒为空', (normalized.json?.unassigned ?? []).length, 0)
  eq('学生档：unassigned 只留本人（他在班里，故是空）',
    (asStudent.json?.unassigned ?? []).length, 0)
  check('管理员档：unassigned 照常给（演示库上实测 0 行，故本拍只断它是一个数组）',
    Array.isArray(asAdmin.json?.unassigned), `${(asAdmin.json?.unassigned ?? []).length} 行`)
})

/* ------------------------------------------------------------------ 第 14 步
   ⚠️ 浏览器侧的取证。**这一条不能用 HTTP 代替**：它证明的是「Vue 真的渲染出来了、
   而且渲染的是后端给的那份数据」，而 fetch 只证明 API 通。

   ⚠️⚠️ **Plan 05A Task 4 把它从 `--dump-dom` 换成了 CDP**（派单点名的一格）：
   `--dump-dom` 是「起一个浏览器、加载一个 URL、把 DOM 打到 stdout、退出」，
   它**没有任何设 cookie 的入口**。而 Plan 05A 之后身份只走 `pe_session`
   （HttpOnly，故页面脚本也写不了它），且 `adoptFromUrl()` 那条深链接已经降级成
   DEV-only 的开发工具 —— 于是 `--dump-dom` 打开任何一条业务路由都会被
   路由守卫弹到 `/login`，13 条路由的取证会**全部**变成「登录页的 DOM」。

   ⚠️ **控制者倾向引入 Playwright/Puppeteer（前端 devDependency），实现者顶回**：
   派单自己点了另一条路（「或用 CDP 直接连」），而它在本机是**零依赖**可行的 ——
   Node **24.19.0** 有全局 `WebSocket`（22 起不再要 flag），Edge/Chrome 的
   `--headless=new --remote-debugging-port=0` 会把 DevTools 的 ws 地址打到 stderr。
   两者拼起来就是一个够用的 CDP 客户端（下面 ~110 行）：
     `Target.createTarget` → `Target.attachToTarget{flatten:true}` → `Network.setCookie`
     → `Page.navigate` → 轮询 `Runtime.evaluate` 取 `document.documentElement.outerHTML`。
   ⚠️ 于本仓前端至今**零新增依赖**（Plan 01–05A 全程；`package.json` 的
   devDependencies 一格没动），而 Playwright 会拉一个 ~150 MB 的浏览器下载。
   ⚠️ 三个坑仍然逐个绕开：① `--force-prefers-reduced-motion`（Plan 05B 删掉了
   `StatBlock` 的数字滚动与 4 个图表的 draw/grow 之后，这一条兜的是大屏轮播的
   200ms 过渡与加载条；它**留着**是因为可达性要求用户能关动效）② 不用 shell 重定向
   （Node 的 `spawn` 直接收 stdout/stderr）③ vite 只绑 `::1` → 基址是 `localhost`。
   ⚠️ 而 `--virtual-time-budget` **不再需要**：轮询「关键内容都出现了没有」
   比虚拟时钟更贴判据（虚拟时钟会在网络请求还在飞的时候就宣布预算用完）。   */

/** 起一个无头浏览器（`--remote-debugging-port=0` = 让操作系统挑一个空端口），
 *  从 stderr 里读出 DevTools 的 ws 地址。
 *  @returns {Promise<{child: import('node:child_process').ChildProcess, wsUrl: string, workRoot: string}>} */
async function spawnHeadless() {
  const candidates = [
    process.env.PE_BROWSER,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean)
  const browser = candidates.find((p) => fs.existsSync(p))
  if (browser === undefined) {
    throw new Error(`找不着无头浏览器（试过了 ${candidates.length} 个路径；用 PE_BROWSER 指定）`)
  }
  const workRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pe-smoke-cdp-'))
  const args = [
    '--headless=new', '--disable-gpu', '--no-sandbox',
    // ⚠️ 坑 ①：不加这一条会抓到 StatBlock 数字滚动**中途**那一帧
    //    （Plan 04 Task 2 实测到 95.7 而不是 100.0）。
    '--force-prefers-reduced-motion',
    '--remote-debugging-port=0',
    `--user-data-dir=${path.join(workRoot, 'profile')}`,
    'about:blank',
  ]
  const child = spawn(browser, args, { windowsHide: true })
  const wsUrl = await new Promise((resolve, reject) => {
    let stderr = ''
    const timer = setTimeout(() => reject(new Error(`30 s 内没等到 DevTools 的 ws 地址；stderr=${stderr.slice(-400)}`)), 30000)
    child.stderr.on('data', (d) => {
      stderr += d.toString('utf8')
      // 逐字形状：`DevTools listening on ws://127.0.0.1:53792/devtools/browser/<uuid>`
      const m = /DevTools listening on (ws:\/\/\S+)/.exec(stderr)
      if (m !== null) { clearTimeout(timer); resolve(m[1]) }
    })
    child.on('error', (err) => { clearTimeout(timer); reject(err) })
    child.on('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`浏览器提前退出（code=${code}）；stderr=${stderr.slice(-400)}`))
    })
  })
  return { child, wsUrl, workRoot, browser }
}

/** 一个**够用**的 CDP 客户端（Node 自带的全局 `WebSocket`，零依赖）。 */
function cdpConnect(wsUrl) {
  if (typeof WebSocket !== 'function') {
    throw new Error('本 Node 没有全局 WebSocket（需要 ≥ 22；实测本机是 ' + process.version + '）')
  }
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl)
    const pending = new Map()
    const listeners = new Map()
    let nextId = 1
    const api = {
      /** 发一条命令。`sessionId` 是 `Target.attachToTarget{flatten:true}` 给的那一个。 */
      send(method, params = {}, sessionId) {
        const id = nextId++
        const msg = { id, method, params }
        if (sessionId !== undefined) msg.sessionId = sessionId
        return new Promise((res, rej) => {
          pending.set(id, { res, rej })
          ws.send(JSON.stringify(msg))
        })
      },
      on(method, cb) {
        if (!listeners.has(method)) listeners.set(method, new Set())
        listeners.get(method).add(cb)
      },
      close() { try { ws.close() } catch { /* 已经断了 */ } },
    }
    ws.addEventListener('message', (ev) => {
      let msg
      try {
        msg = JSON.parse(typeof ev.data === 'string' ? ev.data : Buffer.from(ev.data).toString('utf8'))
      } catch { return }
      if (msg.id !== undefined && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id)
        pending.delete(msg.id)
        if (msg.error) rej(new Error(`${msg.error.message ?? JSON.stringify(msg.error)}`))
        else res(msg.result)
      } else if (msg.method !== undefined && listeners.has(msg.method)) {
        for (const cb of listeners.get(msg.method)) cb(msg.params)
      }
    })
    ws.addEventListener('open', () => resolve(api))
    ws.addEventListener('error', () => reject(new Error(`CDP 的 WebSocket 打不开：${wsUrl}`)))
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** §4.1 的机器守卫：「不能出现文本内容重叠」+「排版不干净（横向溢出）」。
 *  谓词（计划 §4.1 逐字）：
 *   ① TreeWalker 过 SHOW_TEXT，取每个非空文本节点的 parentElement（同一元素去重）；
 *   ② 过滤零面积与 visibility:hidden / display:none / opacity:0；
 *   ③ 两两求交，交集面积 > 两者中较小者的 20% 且**不是祖先-后代关系** → 重叠；
 *   ④ 溢出：任何 scrollWidth > clientWidth+1 的元素，但**放行自己声明了
 *      overflow-x: auto/scroll 的容器**（管理台 21 列的表与 JSON 原文块是
 *      故意可滚的；计划 §4.1 那一句「没有任何元素」若照字面执行会把它们判红，
 *      而那是设计不是失效 —— 这一条收窄在报告 §5 里逐字说明了）。
 *      整页另断言 documentElement.scrollWidth <= window.innerWidth。 */
const LAYOUT_PROBE = `(() => {
  const visible = (el) => {
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none') return false
    if (Number.parseFloat(cs.opacity) === 0) return false
    return true
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null)
  const items = []
  let node = walker.nextNode()
  while (node !== null) {
    const textNode = node
    const el = node.parentElement
    node = walker.nextNode()
    const text = textNode.nodeValue
    if (text === null || text.trim() === '' || el === null) continue
    if (!visible(el)) continue
    /* ⚠️ 取**逐行片段**而不是元素的 union rect：一个折行的行内元素（长 code /
       长 strong）的 getBoundingClientRect 是它所有行片的并集，会盖住同段落里
       别的行 —— 视觉上并不重叠却会被 union rect 判成重叠（本波首跑实测的假阳性）。
       Range.getClientRects 给的是每一行片各自的矩形。 */
    const range = document.createRange()
    range.selectNodeContents(textNode)
    const rects = []
    for (const r of range.getClientRects()) {
      if (r.width > 0 && r.height > 0) rects.push(r)
    }
    if (rects.length === 0) continue
    items.push({ el, rects, tag: el.tagName.toLowerCase(), text: text.trim().slice(0, 20) })
  }
  const overlaps = []
  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) {
      const a = items[i]
      const b = items[j]
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue
      let worst = 0
      let hitA = null
      let hitB = null
      for (const ra of a.rects) {
        for (const rb of b.rects) {
          const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)
          const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top)
          if (w <= 0 || h <= 0) continue
          const inter = w * h
          const smaller = Math.min(ra.width * ra.height, rb.width * rb.height)
          if (smaller <= 0) continue
          const ratio = inter / smaller
          if (ratio > worst) {
            worst = ratio
            hitA = ra
            hitB = rb
          }
        }
      }
      if (worst <= 0.2 || hitA === null) continue
      overlaps.push({
        a: a.tag + '「' + a.text + '」',
        b: b.tag + '「' + b.text + '」',
        aRect: [hitA.x, hitA.y, hitA.width, hitA.height].map((v) => Math.round(v)),
        bRect: [hitB.x, hitB.y, hitB.width, hitB.height].map((v) => Math.round(v)),
        ratio: Number(worst.toFixed(3)),
      })
    }
  }
  const overflows = []
  for (const el of document.querySelectorAll('*')) {
    if (el.scrollWidth <= el.clientWidth + 1) continue
    const ox = getComputedStyle(el).overflowX
    if (ox === 'auto' || ox === 'scroll') continue
    overflows.push({
      text: String(el.textContent ?? '').trim().slice(0, 20),
      tag: el.tagName.toLowerCase(),
      cls: String(el.getAttribute('class') ?? '').slice(0, 48),
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
    })
  }
  return JSON.stringify({
    leaves: items.length,
    overlapCount: overlaps.length,
    overlaps: overlaps.slice(0, 10),
    overflowCount: overflows.length,
    overflows: overflows.slice(0, 10),
    pageScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  })
})()`

await step(14, '16 条路由的无头浏览器 DOM 取证（CDP + cookie；14 条业务路由 + /login + /bind）', async () => {
  let headless = null
  try {
    headless = await spawnHeadless()
  } catch (err) {
    check('起得来一个无头浏览器（Edge / Chrome）', false, String(err?.message ?? err))
    return
  }
  check(`起得来一个无头浏览器（${path.basename(headless.browser)}，CDP @ ${headless.wsUrl.replace(/\/devtools.*/, '/…')}）`,
    true, '')

  // 前端起着吗？
  let webUp = false
  for (const base of [WEB, WEB.replace('localhost', '[::1]')]) {
    try {
      const r = await fetch(base + '/', { signal: AbortSignal.timeout(5000) })
      if (r.ok) { webUp = true; break }
    } catch { /* 试下一个 */ }
  }
  check(`前端起着（${WEB}）`, webUp, webUp ? '' : '请先 `cd frontend; npm run dev`')
  if (!webUp) { headless.child.kill('SIGKILL'); return }

  /* ⚠️⚠️ **Plan 06 Task 13 新加（D7）：dev server 的「模块新鲜度」一拍**。
     ⚠️ 它守的就是本文件头「前置条件 ②」那一节写的事：第 14 步量的是**渲染后的真值**，
     而一个陈旧的 vite 会把新旧两份模块同时留在图里（HMR 对 `router/index.ts` 这类
     **模块图**的改动经常要整页重载才干净）→ **假红**，而那几条红读起来像
     「本波把布局改坏了」（品牌波 §5.1 第 7 条实测过一次：4 条红全是「文本内容重叠」）。
     ⚠️ 判据**两侧不同源**：期望侧现场从磁盘读、被测侧问 dev server 要它此刻服务的那一份。
     ⚠️ 而它**不写死一个标记串**（写死 = 「每次跑之前要记得改它」= 又一个待清扫项）。
     ⚠️ **产品档自动跳过**：`dist` 里没有 `/src/**`，`fetch` 拿不到 200 ⇒ 那一档的新鲜度
     由 `scripts/serve.ps1` 的 ② 那一步自己判（源面 mtime vs 构建戳 + 一道
     「源面 < 20 个文件就 throw」的反空转）。⚠️ 于是本拍在两档都不会假红。
     ⚠️ 反空转那一边是下面第一条断言：切不出 ≥ 20 条路径字面量就说明**期望侧**坏了
     （正则漂了 / 文件搬走了），而不是「dev server 是新鲜的」。 */
  {
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
    const routerFile = path.join(root, 'frontend', 'src', 'router', 'index.ts')
    const routerSrc = fs.readFileSync(routerFile, 'utf8')
    const wantPaths = [...routerSrc.matchAll(/path:\s*'([^']+)'/g)].map((m) => m[1])
    check('§D7 非空转：从磁盘上的 router/index.ts 里切得出路由路径字面量（≥ 20 条）',
      wantPaths.length >= 20, `切出 ${wantPaths.length} 条：${JSON.stringify(wantPaths.slice(0, 5))}…`)
    /* ⚠️⚠️ 「这是哪一档」的判据**不能是状态码**（本波两档各实测过一次才发现）：
       产品档的 SPA fallback 对 `/src/router/index.ts` 也回 **200**（回的是 index.html），
       而 dev 档对一个不存在的路径同样回 **200 text/html**。两档唯一的差别在
       **content-type**：vite 把 `/src/**.ts` 服务成 `text/javascript`，
       而两边的 fallback 都是 `text/html`。⚠️ 用状态码判的话本拍在产品档上会
       **假红**（拿 index.html 去比路由字面量，21 条全「缺」）。 */
    let served = null
    let ctype = ''
    try {
      const r = await fetch(WEB.replace(/\/$/, '') + '/src/router/index.ts',
        { signal: AbortSignal.timeout(10000) })
      ctype = String(r.headers.get('content-type') ?? '')
      served = (r.ok && !ctype.includes('text/html')) ? await r.text() : null
    } catch { served = null }
    if (served === null) {
      out(`    §D7 ${WEB}/src/router/index.ts 的 content-type 是 ${JSON.stringify(ctype)}`
        + '（不是 JS 模块）⇒ 这是**产品档**（SPA fallback 回的是 index.html），'
        + '新鲜度由 serve.ps1 的 ② 那一步判，本拍跳过')
    } else {
      const missing = wantPaths.filter((p) => !served.includes(p))
      out(`    §D7 dev server 服务出来的那份 router 模块 ${served.length} 字符，`
        + `磁盘上的 ${wantPaths.length} 条路径字面量缺 ${missing.length} 条`)
      check('§D7 dev server 服务出来的那份 router 模块**含磁盘上的全部路由路径**'
        + '（缺 = 那个 vite 是陈旧的：HMR 没把模块图的改动吃干净 → **重起 npm run dev**）',
        missing.length === 0,
        `缺 ${missing.length} 条：${JSON.stringify(missing.slice(0, 5))}`)
    }
  }

  // 真名单：断言「页面渲染的是后端给的那份数据」要用**真名字**，不能写死。
  // ⚠️ 带 `as: 'teacher'`：Plan 05A Task 5 之后 `GET /api/students` 要教职身份。
  const students = await req('GET', `/api/students?limit=200`, { as: 'teacher', quiet: true, record: false })
  const allStudents = students.json?.items ?? []
  const me = allStudents.find((s) => s.id === STUDENT)
  // ⚠️ 教师端的「学生详情」只对**他本学期任教的学生**开放，故这一条路由用
  //    第 7 步现找到的那一个（学生 4 不在 T0001 的班里，用它只会渲染出 403 面板）。
  const taught = allStudents.find((s) => s.id === SHARED.taughtStudent)
  const section = (await req('GET', `/api/course-sections?limit=5`, { as: 'teacher', quiet: true })).json?.items?.[0]
  out(`    学生 #${STUDENT} = ${me?.student_no} ${me?.name}；`
    + `T0001 名册里的 #${taught?.id} = ${taught?.student_no} ${taught?.name}；`
    + `教学班 #${section?.id} = ${section?.name}`)

  /* ⚠️⚠️ **Plan 06 Task 10 新加：教师页那一块三格的「真取证」期望值**（派单 §1.8）。
     ⚠️ 它**不是**静态文字 needle，而是「页面上渲染出来的那个数字 == 后端那一个端点
     此刻回的那一格」——两侧不同源（一侧是 CDP 抓到的 DOM 文本、一侧是 HTTP 响应体），
     故它挡得住「Vue 把 `null` 渲染成了 0」「读错了字段」「前端自己算了一遍」三档。
     ⚠️ 期望值的推法与 `StudentDetail.vue` **同一条口径**：从他自己那些小测行里取
     **最近一次**（`week` 最大）的那一行，用它的 `semester_id` + `week` 去打教师侧变体。
     ⚠️ 而格式化按 `StatBlock` 的规则（`value.toFixed(decimals)`）：综合分 2 位、深蹲 1 位。 */
  const detailRaw = (await req('GET', '/api/mini-tests?limit=200',
    { as: 'teacher', quiet: true, record: false })).json?.items ?? []
  const detailRows = detailRaw.filter((r) => r.student_id === taught?.id)
  const detailWeek = detailRows.length > 0 ? Math.max(...detailRows.map((r) => r.week)) : null
  const detailSemester = detailRows.find((r) => r.week === detailWeek)?.semester_id ?? null
  const detailVariant = await req('GET',
    `/api/teacher/students/${taught?.id}/normalized?semester_id=${detailSemester}&week=${detailWeek}`,
    { as: 'teacher', quiet: true, record: false })
  const detailSections = detailVariant.json?.sections ?? []
  const wantComposite = detailSections.map((r) => r.composite.toFixed(2))
  const wantSquat = detailSections.map((r) => r.squat_score.toFixed(1))
  const wantShuttle = detailSections.map((r) => r.shuttle_score.toFixed(1))
  out(`    教师侧变体（#${taught?.id}，semester=${detailSemester} week=${detailWeek}）：`
    + `${detailSections.length} 个班 → 综合分 ${JSON.stringify(wantComposite)}、`
    + `深蹲 ${JSON.stringify(wantSquat)}、折返百分位 ${JSON.stringify(wantShuttle)}`)
  /** 把页面上全部 `StatBlock` 的 (label, value) 两格抓出来。
   *  ⚠️ 读的是 `.stat__label` 与 `.stat__value` 两个**类名**（`StatBlock.vue` 的模板），
   *  故它同时挡住「那一格根本没渲染」与「渲染了但读错了字段」两档。 */
  const STAT_PROBE = `JSON.stringify([...document.querySelectorAll('.stat')].map((el) => ({
    label: (el.querySelector('.stat__label')?.textContent ?? '').trim(),
    value: (el.querySelector('.stat__value')?.textContent ?? '').trim(),
  })))`

  /* ⚠️⚠️ **Plan 06 Task 13 新加（D6）：学生端小测页 `/s/mini-test` 那三格的「真取证」
     期望值**。⚠️ 它收掉的是 Task 9 登记的那条待清扫：改前那一条路由的 needle 是
     **静态文字**（`['二次小测', '30 秒深蹲']`），而静态 needle 的失效形态是
     「页面把数算错了、或读了别的字段，只要那几个字还在，拍就绿」
     （Task 10 只收了教师页那一格，本波照**同一姿势**收学生页）。
     ⚠️ 两侧**不同源**：期望侧是 HTTP 响应体、被测侧是 CDP 抓到的 DOM 文本，
     故它挡得住「Vue 把 `null` 渲染成了 0」「读错了字段」「前端自己算了一遍」三档。
     ⚠️ 期望值的推法与 `MiniTest.vue` **同一条口径**：查询参数取自
     `GET /api/students/{id}/home` 的 `semester_id` + `week`（页面就是这么发的），
     三格各自的来源是 ——「小测综合分」← **窄端点** `/normalized/me` 的 `composite`（2 位）、
     「折返班内百分位」← **班级端点** `/normalized` 里**我**那一行的 `shuttle_score`（1 位）、
     「深蹲得分」← 窄端点的 `squat_score`（1 位）；小数位数按 `StatBlock` 的规则
     （`value.toFixed(decimals)`，模板里逐格写着 2 / 1 / 1）。
     ⚠️ 而 `null` 那一档 `StatBlock` 渲染「—」（`present.ts` 的 `UNKNOWN`，U+2014）、
     **不是** 0 —— 期望侧照同一规则算，故「把不知道讲成 0」会让本拍红。
     ⚠️ 「哪几个班」由 `mySections` 的过滤决定（只留 `entries` 里有我那一行的班），
     期望侧逐字复刻那一次过滤，故三格的**顺序**也是同源的。 */
  const mtHome = (await req('GET', `/api/students/${STUDENT}/home?as_of=${AS_OF}`,
    { as: studentJar(STUDENT), quiet: true, record: false })).json
  const mtQuery = `semester_id=${mtHome?.semester_id}&week=${mtHome?.week}`
  const mtNorm = (await req('GET', `/api/mini-tests/normalized?${mtQuery}`,
    { as: studentJar(STUDENT), quiet: true, record: false })).json
  const mtSelf = (await req('GET', `/api/mini-tests/normalized/me?${mtQuery}`,
    { as: studentJar(STUDENT), quiet: true, record: false })).json
  const mtSelfBy = new Map((mtSelf?.sections ?? []).map((s) => [s.course_section_id, s]))
  /** `null` / `undefined` → 「—」（与 `StatBlock` 逐字同一条规则），否则 `toFixed`。 */
  const mtText = (v, decimals) => (v === null || v === undefined ? '\u2014' : v.toFixed(decimals))
  const mtMine = (mtNorm?.sections ?? [])
    .map((sec) => {
      const entry = (sec.entries ?? []).find((e) => e.student_id === STUDENT)
      if (!entry) return null
      const self = mtSelfBy.get(sec.course_section_id) ?? null
      return {
        composite: mtText(self?.composite, 2),
        shuttle: mtText(entry.shuttle_score, 1),
        squat: mtText(self?.squat_score, 1),
      }
    })
    .filter(Boolean)
  const wantMtComposite = mtMine.map((r) => r.composite)
  const wantMtShuttle = mtMine.map((r) => r.shuttle)
  const wantMtSquat = mtMine.map((r) => r.squat)
  out(`    小测页期望值（#${STUDENT}，${mtQuery}）：${mtMine.length} 个班 → `
    + `综合分 ${JSON.stringify(wantMtComposite)}、折返 ${JSON.stringify(wantMtShuttle)}、`
    + `深蹲 ${JSON.stringify(wantMtSquat)}`)

  /* ⚠️ **URL 里一个 `?student=` / `?teacher=` 都没有了**（Plan 05A Task 4）：
     身份由 `jar` 那一格决定，本步在导航之前用 CDP 的 `Network.setCookie`
     把 `pe_session` 种进浏览器。⚠️ 这同时是「`adoptFromUrl()` 已经降级成
     DEV-only 开发工具、而取证不再依赖它」的可执行证明 —— 若那一条深链接还是
     取证的入口，本步在生产构建上就无从跑起。
     ⚠️ `as_of` 也不用带了：`stores/identity.ts` 的 `DEMO_AS_OF` 就是演示日，
     而一个全新的浏览器 profile 里 `localStorage` 是空的 → 一定落到那个缺省值。 */
  const ROUTES = [
    { name: 'login', url: '/login', jar: null, size: [1440, 1600],
      needles: ['登录', '名册已存在、口令首次自绑', 'pe_session', '首次使用？去绑定口令'] },
    { name: 'bind', url: '/bind', jar: null, size: [1440, 2000],
      needles: ['首次绑定口令', '出生日期（验身材料）', '再输一次', '绑定口令并登录', 'birth'] },
    { name: 's-home', url: '/s/home', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['的本周', me?.name, me?.student_no, '本周训练量'] },
    { name: 's-weekly-sheet', url: '/s/weekly-sheet', jar: studentJar(STUDENT), size: [375, 3000],
      needles: ['本周训练单', '第 6 周'] },
    { name: 's-check-in', url: '/s/check-in', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['每日打卡', '提交时刻与「是否迟交」都由服务端算'] },
    { name: 's-rpe', url: '/s/rpe', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['课堂快评', '口令请照老师投屏上的那一串手输'] },
    /* ⚠️ `折返班内百分位` 是 **Plan 06 Task 13** 加的第 3 条 needle（D6）。⚠️ 它的作用
       **不只是**「文字在不在」：那个 label 住在 `mySections` 的循环里，而 `mySections`
       只在 `GET /api/mini-tests/normalized` 与 `/normalized/me` **两次都回来之后**才非空，
       故它是「异步请求已经落地」的**闸门** —— `dumpRoute` 是轮询到全部 needle 都出现
       才返回的，少了它，下面那三拍真取证可能在 `Promise.all` 落地之前就把 DOM 抓走
       （= 假红）。⚠️ 与教师页那一格的 `小测综合分` 是同一条姿势（那里的注释逐字写着
       这一格为什么承重）。「那一格里是不是后端给的那个数」仍然**不靠** needle，
       靠下面那三拍。 */
    { name: 's-mini-test', url: '/s/mini-test', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['二次小测', '30 秒深蹲', '折返班内百分位'] },
    { name: 's-notifications', url: '/s/notifications', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['消息中心', '未读'] },
    { name: 't-dashboard', url: '/t/dashboard', jar: 'teacher', size: [1440, 2400],
      needles: ['ALERTS', 'LAYERS', 'THIS WEEK', 'CHECK-IN', section?.name] },
    { name: 't-report', url: '/t/report', jar: 'teacher', size: [1440, 3000],
      needles: ['班级周报', '① 分层分布', '③ 三层完成率', '④ 进步榜'] },
    { name: 't-alerts', url: '/t/alerts', jar: 'teacher', size: [1440, 2400],
      needles: ['预警队列', 'FILTERS', 'QUEUE'] },
    // ⚠️ 后两条 needle 是 Plan 04 收尾波加的：`可解释性展开` 与 `他的今日` 两块
    //    只出现在 `GET /api/teacher/students/{id}/home` 真的被调通并渲染出来之后。
    // ⚠️⚠️ `小测综合分` 是 **Plan 06 Task 10** 加的：Task 9 的 schema 级摘列让那一格
    //    从页面上消失了（本波由教师侧变体还回来）。⚠️ 而它作为 needle 的作用**不只是**
    //    「文字在不在」——`dumpRoute` 是**轮询到全部 needle 都出现才返回**的，
    //    故它同时保证下面那两拍真取证读到的是**异步请求已经落地之后**的那一帧
    //    （少了它，DOM 可能在 `Promise.all` 回来之前就被抓走，于是那两拍会假红）。
    //    ⚠️ 而「那一格里**是不是数**、是不是后端给的那个数」由下面那两拍钉，
    //    **不靠** needle（Task 9 登记过一条待清扫：`/s/mini-test` 的 needle 是静态文字，
    //    故它证明不了「渲染出来的是后端那份数据」；本波在教师页这一格上做的是真取证）。
    { name: 't-student-detail', url: `/t/students/${taught?.id}`, jar: 'teacher', size: [1440, 3000],
      needles: [taught?.name, '当前分层', '本周训练单', '可解释性展开', '他的今日', '小测综合分'] },
    /* ⚠️ **Plan 06 Task 15 / 终审 S2-①**：后三条 needle 是本波新加的，钉的正是改前
       那段与鉴权实物**相反**的散文（「读是匿名的 / 48 个匿名 GET / 写要教师身份
       require_teacher / 去左上角的身份切换器选一个教师」）。⚠️ 而那三条同时列在
       `uniqueNeedles` 里 —— 因为终审 S3-⑦ 查出过**同一族的另一种失效**：
       一个 needle 在页面上有**两处**同串时，它被另一处满足了，于是改坏它要钉的那一段
       仍然全绿。故本波对每一条新 needle 都断言「它在正文里**恰好 1 处**」。 */
    { name: 'admin-index', url: '/admin', jar: 'admin', size: [1440, 3000],
      needles: ['资源目录', '23 resources', '可写 9', '只读 14', '体育专家维护的知识资产',
        '读要身份，只有 7 个例外', '写仅管理员', '换身份请登出再登录',
        /* ⚠️ **Plan 08 Task 4 加的两条**：第 06 块（一次性绑定令牌）的抬头与
           那一句「自助绑定今天默认仍然开着」。⚠️ 后一条同时列进 `uniqueNeedles`
           （终审 S3-⑦ 那一条同族：一个 needle 在页面上有两处同串时，
           它被另一处满足了，于是改坏它要钉的那一段仍然全绿）。 */
        'ONE-TIME BIND TOKEN', 'PE_ALLOW_SELF_BIND'],
      uniqueNeedles: ['读要身份，只有 7 个例外', '写仅管理员', '换身份请登出再登录',
        'PE_ALLOW_SELF_BIND'] },
    { name: 'admin-list', url: '/admin/students', jar: 'admin', size: [1440, 2000],
      needles: ['学生', '/api/students', '共 60 行', me?.name, '＋ 新建一行'] },
    { name: 'admin-detail', url: `/admin/students/${STUDENT}`, jar: 'admin', size: [1440, 2000],
      needles: [`学生 #${STUDENT}`, me?.student_no, me?.name, '✎ 编辑', 'student_no'] },
    /* ⚠️⚠️ **Plan 06 Task 9 加的第 16 条**：管理台的审计只读页（Task 5 的后置部分）。
       ⚠️ 五条 needle 里前四条是**页面结构**（抬头 / 端点路径 / 权限那一格 / 两个过滤
       下拉的标签），第五条 `/api/auth/login` 是**后端给的那份数据**：第 0 步那三次登录
       各自留下了一行审计（`should_record` 认 POST），故它证明的是「Vue 渲染出来的
       是端点回的行」，不只是「页面没白屏」。⚠️ 而 `subject_kind` 那一格是九列里
       最容易与「凭空加一列」混淆的一个，故它也在 needle 里（它是列头的 slug）。
       ⚠️ **九列一个都不多**这件事由后端 `AuditLogRead` 的 9 格 + 前端
       `AuditLogList.vue` 的 `satisfies` / `switch` 穷尽性检查在**编译期**钉，
       本拍只钉渲染面。 */
    /* ⚠️⚠️ **Plan 06 Task 15 / 终审 S3-⑦**：第 4 条 needle 改前是裸的 `'身份类型'`，
       而页面上有**两处**同串 —— 列头（`AuditLogList.vue:116`）与过滤器下拉的标签
       （`:331`）。终审把列头那一处的 `label` 改成「身份种类」，smoke 仍然 **637 绿 / 0 红**
       （needle 被过滤器那一处满足了）⇒ 九列的**列头文案**当时没有任何守卫。
       ⚠️ 处置两格：① 本条 needle 换成 `'身份类型 subject_kind'` —— 那是 `<th>` 里
       「label 文本 + 紧跟的 `<code>` slug」被 `toPlainText` 折叠之后的形状，
       **只可能在列头出现**（过滤器那一处的下文是「（不过滤） 教师 · teacher」）；
       ② 它同时进 `uniqueNeedles`（断言恰好 1 处），而九列逐个的字面量断言在下面
       `route.name === 'admin-audit-logs'` 那一块里（DOM vs 后端响应体，两侧不同源）。 */
    { name: 'admin-audit-logs', url: '/admin/audit-logs', jar: 'admin', size: [1440, 2400],
      needles: ['审计留痕', '/api/audit-logs', '仅 role=admin 可读', '身份类型 subject_kind',
        'subject_kind', '/api/auth/login'],
      uniqueNeedles: ['身份类型 subject_kind'] },
  ]
  eq('路由条数 = 16（学生端 6 + 教师端 4 + 管理台 **4** + 鉴权 2）', ROUTES.length, 16)

  /* ⚠️ **未登录访问业务路由会被守卫弹到 `/login?next=…`** —— 这一格是路由守卫的
     验收面（派单 Task 3 第 5 点），故在浏览器里**实测**一次，不只是读代码。 */
  const cdp = await cdpConnect(headless.wsUrl)
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true })
  await cdp.send('Page.enable', {}, sessionId)
  await cdp.send('Runtime.enable', {}, sessionId)
  await cdp.send('Network.enable', {}, sessionId)

  /** 导航到一条路由、轮询到关键内容都出现（或超时），返回那份 DOM 原文。
   *  ⚠️ `extraNeedles`（Plan 07 Task 1）：**只进轮询的退出条件、不进 `missing` 那一拍**。
   *  试用告示是 `App.vue` 在 `onMounted` 里问完 `/api/health` 之后才渲染的，
   *  比页面自己那些请求**晚一帧**；不把它加进轮询条件的话，本步会在告示落地之前
   *  就把 DOM 抓走 ⇒ 试用档上那几拍**假红**（而 detail 会把真因说成「页面渲染坏了」）。
   *  ⚠️ 而它刻意**不混进** `route.needles`：那一拍断的是「这条路由自己的关键内容」，
   *  告示是**跨 16 条路由的同一件事**，混在一起就看不出是哪一档坏了。 */
  async function dumpRoute(route, extraNeedles = []) {
    const [width, height] = route.size
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    if (route.jar !== null) {
      const raw = JARS.get(route.jar) ?? (await ensureJar(route.jar))
      const value = raw.slice('pe_session='.length)
      const set = await cdp.send('Network.setCookie', {
        name: 'pe_session', value, url: WEB, httpOnly: true, sameSite: 'Lax',
      }, sessionId)
      if (set?.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(set)}`)
    }
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width, height, deviceScaleFactor: 1, mobile: false }, sessionId)
    await cdp.send('Page.navigate', { url: WEB + route.url }, sessionId)
    const wanted = [...route.needles.filter((n) => n !== undefined), ...extraNeedles]
    const deadline = Date.now() + 45000
    let html = ''
    for (;;) {
      const res = await cdp.send('Runtime.evaluate',
        { expression: 'document.documentElement.outerHTML', returnByValue: true }, sessionId)
      html = String(res?.result?.value ?? '')
      // ⚠️ 轮询的退出条件与下面那条断言**共用 `toPlainText`**（终审 I4）：本处此前是
      //    弱剥（只剥标签、style/script 的文本留着）+ `|| html.includes(n)` 那个假出口，
      //    于是一个撞上 CSS 注释的 needle 会让轮询在第一拍就 break（假红，且 detail
      //    会把真因说成「页面渲染坏了」）。现在两个出口都没有了。
      const plain = toPlainText(html)
      if (wanted.every((n) => plain.includes(n))) break
      if (Date.now() > deadline) break
      await sleep(300)
    }
    const finalUrl = await cdp.send('Runtime.evaluate',
      { expression: 'location.pathname + location.search', returnByValue: true }, sessionId)
    return { html, at: String(finalUrl?.result?.value ?? '') }
  }

  // 守卫那一拍的实测（不带任何 cookie 打开 /s/home）
  const bounced = await dumpRoute({
    name: 'guard', url: '/s/home', jar: null, size: [1440, 1200],
    // ⚠️ 关键内容取**登录页**的（不是 /s/home 的）：断言的正是「它被弹到了那里、
    //    而且登录页真的渲染出来了」。
    needles: ['登录', '名册已存在、口令首次自绑', '首次使用？去绑定口令'],
  })
  check('未登录访问 /s/home → 被守卫弹到 /login?next=/s/home（`next` 带着原路径，'
    + '于是登录后能回来；派单 Task 3 第 4/5 点的验收面）',
    bounced.at.startsWith('/login')
      && decodeURIComponent(bounced.at).includes('next=/s/home'),
    `location=${bounced.at}`)
  // ⚠️ 与上面同一条纪律：只在剥掉 style/script 的正文里找（防 CSS 注释假绿）
  const bouncedPlain = toPlainText(bounced.html)
  check('而登录页**渲染出来了**（不是白屏；计划 §4.2 逐字要求「不要只显示空白」）',
    ['登录', '名册已存在、口令首次自绑', '首次使用？去绑定口令']
      .every((n) => bouncedPlain.includes(n)),
    `DOM ${Buffer.byteLength(bounced.html, 'utf8')} bytes`)

  /* ⚠️⚠️ **Plan 06 Task 9 新加的一拍（派单 §2 第 6 条：admin 档与非 admin 档各一拍）**：
     管理台的审计只读页**只有 admin 能进**，而它复用的是**既有那一套**路由守卫
     （`router/index.ts` 上那一条路由的 `meta.requires: 'admin'`，与另外三条 `/admin/*`
     逐字同形；判据是 `stores/session.ts` 的 `satisfies`），**没有写第二套**。
     ⚠️ 于是一个普通教师（`role='teacher'`）直接访问 `/admin/audit-logs` 会被
     `router.beforeEach` 弹回**他自己的**首页 + 一句 `session.notice`
     （计划 §4.2 逐字要求「不要只显示空白」），而不是进去看到一个到处是 403 的页面。
     ⚠️ 期望侧照 `homeOf` 那一格写死：`kind === 'teacher' && role !== 'admin'` → `/t/dashboard`。
     ⚠️ 学生那一档走的是同一段代码、只是 `homePath` 换成 `/s/home`，故本拍取**教职**
     这一侧（它是安全上更吃紧的一档：一个在册教职、但不是管理员）。 */
  const auditBlocked = await dumpRoute({
    name: 'guard-audit-logs', url: '/admin/audit-logs', jar: 'teacher', size: [1440, 2000],
    // ⚠️ 关键内容取**班级大屏**的（不是审计页的）：断言的正是「他被弹到了那里、
    //    而且大屏真的渲染出来了」—— 与上面 `guard` 那一拍取登录页内容同一条纪律。
    needles: ['ALERTS', 'LAYERS', 'THIS WEEK', 'CHECK-IN'],
  })
  const auditBlockedPlain = toPlainText(auditBlocked.html)
  check('§Task9 普通教师访问 /admin/audit-logs → 被守卫弹回 /t/dashboard（**不是**白屏、'
    + '**不是**一个 403 页；复用既有那一套 `meta.requires` 守卫）',
    auditBlocked.at.startsWith('/t/dashboard'), `location=${auditBlocked.at}`)
  check('§Task9 而大屏**渲染出来了**（计划 §4.2：不要只显示空白）',
    ['ALERTS', 'LAYERS', 'THIS WEEK'].every((n) => auditBlockedPlain.includes(n)),
    `DOM ${Buffer.byteLength(auditBlocked.html, 'utf8')} bytes`)
  /* ⚠️ **反假绿**：上面两拍在「审计页压根没建出来」时也全绿（守卫照样弹回大屏）。
     故本拍点名断「审计页的内容一个字都没漏给他」——它与 admin 档那一拍
     （needle 命中 `审计留痕`）互为红绿两侧（硬规矩 #50）。 */
  check('§Task9 而审计页的内容**一个字都没漏给他**（`审计留痕` / `subject_kind` 都不在正文里）',
    !auditBlockedPlain.includes('审计留痕') && !auditBlockedPlain.includes('subject_kind'),
    `location=${auditBlocked.at}`)

  /* ------------------------------------------------------------------
     终审 I1 的守卫：**登录页上印出来的登录名示例必须真在册**。

     ⚠️ 为什么要有这一拍：`Login.vue` 的学生档提示此前逐字写着「学号形如 2025010004」，
     而演示库的名册由 `app/seed/population.py` 按「入学年 + 院系码 + 序号」现造，
     那串**从来不在册** → 一个人照着登录页自己的提示输进去，第一屏就是 403
     `password_not_bound`，而那一句 403 说的是「不在名册上」，会把他支去查后端。
     同一个字面量还有三个住址（`demo_bootstrap.py` / `demo.ps1` / spec §13），
     四个都已改成「只描述格式」或「指向那个从库里取值的唯一所有者」。
     ⚠️ 而它**能活到今天**正是因为没有守卫：本脚本的 `studentNoOf()` 是懒加载真名册的，
     故那个字面量一次都没被执行到。
     ⚠️ 谓词形状：学生档 = 10 位数字（`(?<!\d)\d{10}(?!\d)`），教师档 = `T` + 4 位数字。
     两档都跑，因为教师档**今天确实印着一个例子**（`T0001`）→ 它给这条守卫提供了
     「非空转」的那一半证据（硬规矩 #50），而学生档那一半由下面第 ① 拍的反例提供。 */
  {
    const staffPage = await req('GET', '/api/teachers?limit=50', { as: 'teacher', quiet: true, record: false })
    const staffNos = new Set((staffPage.json?.items ?? []).map((t) => t.staff_no))
    const studentNos = new Set(allStudents.map((s) => s.student_no))
    /** 从一段**正文**（`toPlainText` 的返回值）里摘出登录名形状的串。 */
    const examplesIn = (plain, kind) => [...plain.matchAll(
      kind === 'student' ? /(?<!\d)\d{10}(?!\d)/g : /\bT\d{4}\b/g,
    )].map((m) => m[0])

    check('§I1 守卫不空转的前提 ①：名册读得到（60 个学号 / 3 个工号）',
      studentNos.size === 60 && staffNos.size === 3,
      `学号 ${studentNos.size} 个、工号 ${staffNos.size} 个`)
    // ① 反例先验（硬规矩 #107）：谓词必须**会**命中那个假学号，而它必须**不在**名册里。
    //    少了这两拍，「0 个 offender」可能只是谓词根本不会命中任何东西。
    check('§I1 守卫不空转的前提 ②：终审点名的 2025010004 形状上会被谓词命中',
      examplesIn('学号形如 2025010004。', 'student').includes('2025010004'), '')
    check('§I1 守卫不空转的前提 ③：而它确实**不在**名册里（故它当年就是一个假例子）',
      !studentNos.has('2025010004'), `名册里第一个学号是 ${[...studentNos][0]}`)

    const studentExamples = examplesIn(bouncedPlain, 'student')
    out(`    学生档登录页正文里的「10 位数字」串 ${studentExamples.length} 个：${JSON.stringify(studentExamples)}`)
    const studentOffenders = studentExamples.filter((n) => !studentNos.has(n))
    check('§I1 学生档：登录页印的每一个「学号形状」的串都在册（今天 0 个 —— 本页刻意只描述格式、不举例）',
      studentOffenders.length === 0, `offender=${JSON.stringify(studentOffenders)}`)

    const teacherLogin = await dumpRoute({
      name: 'login-teacher', url: '/login?kind=teacher', jar: null, size: [1440, 1600],
      needles: ['工号', '首次使用？去绑定口令'],
    })
    const teacherPlain = toPlainText(teacherLogin.html)
    const teacherExamples = teacherPlain === '' ? [] : examplesIn(teacherPlain, 'teacher')
    out(`    教师档登录页正文里的「T+4 位」串 ${teacherExamples.length} 个：${JSON.stringify(teacherExamples)}`)
    check('§I1 教师档：那一格**非空**（本页确实印着 T0001 这个例子，故下面那拍不是空转）',
      teacherExamples.length >= 1, JSON.stringify(teacherExamples))
    const teacherOffenders = teacherExamples.filter((n) => !staffNos.has(n))
    check('§I1 教师档：登录页印的每一个「工号形状」的串都在册',
      teacherOffenders.length === 0, `offender=${JSON.stringify(teacherOffenders)}`)
  }

  /* ------------------------------------------------------------------
     §4.1 谓词的**已知反例**那一拍（硬规矩 #107）：先在一个故意做坏的页面上
     证明谓词会报，再对 16 条真路由断言 0 处。没有这一拍，「0 处」可能只是
     谓词根本不会命中任何东西（Plan 03 终审查出的「路由遮蔽扫描假绿」同一族）。
     反例页里同时放了三个**不该**被报的东西：嵌套的父子文本（祖先-后代）、
     一个自己声明了 overflow-x:auto 的容器（故意的滚动容器）、以及一段
     不重叠的普通文本 —— 于是这一拍同时验了谓词的三个出口。            */
  {
    const BAD_PAGE =
      'data:text/html;charset=utf-8,' +
      encodeURIComponent(
        '<body>' +
          '<span style="position:absolute;left:10px;top:10px;width:220px">重叠甲 AAAA</span>' +
          '<span style="position:absolute;left:40px;top:16px;width:220px">重叠乙 BBBB</span>' +
          '<p style="margin:0;position:absolute;left:10px;top:300px;width:400px">' +
          '嵌套的 <em>父子文本 <strong>不该被报</strong> 因为祖先-后代</em></p>' +
          '<div style="position:absolute;left:10px;top:340px;width:120px;overflow-x:auto;' +
          'white-space:nowrap">故意的滚动容器故意很长很长很长很长很长很长</div>' +
          '<div style="position:absolute;left:10px;top:380px;width:120px;white-space:nowrap">' +
          '非故意的横向溢出也很长很长很长很长很长很长很长</div>' +
          '</body>',
      )
    const { targetId: badTarget } = await cdp.send('Target.createTarget', { url: 'about:blank' })
    const { sessionId: badSession } = await cdp.send('Target.attachToTarget', { targetId: badTarget, flatten: true })
    await cdp.send('Page.enable', {}, badSession)
    await cdp.send('Runtime.enable', {}, badSession)
    await cdp.send(
      'Emulation.setDeviceMetricsOverride',
      { width: 600, height: 600, deviceScaleFactor: 1, mobile: false },
      badSession,
    )
    await cdp.send('Page.navigate', { url: BAD_PAGE }, badSession)
    await sleep(400)
    const badRes = await cdp.send(
      'Runtime.evaluate',
      { expression: LAYOUT_PROBE, returnByValue: true },
      badSession,
    )
    const bad = JSON.parse(String(badRes?.result?.value ?? '{}'))
    out(`    反例页：叶子 ${bad.leaves} 个、重叠 ${bad.overlapCount} 处、非故意溢出 ${bad.overflowCount} 处`)
    check('§4.1 谓词对**已知反例**会报重叠（两个 absolute 的 span 叠在一起）',
      (bad.overlapCount ?? 0) >= 1, JSON.stringify(bad.overlaps ?? []))
    check('§4.1 谓词报的那一处确实是那两个 span（不是别的东西）',
      JSON.stringify(bad.overlaps ?? []).includes('重叠甲') && JSON.stringify(bad.overlaps ?? []).includes('重叠乙'),
      JSON.stringify(bad.overlaps ?? []))
    check('§4.1 谓词**不**报嵌套的父子文本（祖先-后代排除是承重的）',
      (bad.overlapCount ?? 99) === 1, `重叠 ${bad.overlapCount} 处（应为 1）`)
    check('§4.1 溢出谓词放行 overflow-x:auto 的容器、但报 visible 的那一个',
      (bad.overflowCount ?? 0) === 1 && JSON.stringify(bad.overflows ?? []).includes('非故意的横向溢出'),
      JSON.stringify(bad.overflows ?? []))
    await cdp.send('Target.closeTarget', { targetId: badTarget })
  }
  /* ------------------------------------------------------------------------
     ⚠️⚠️ 「DOM 有多少字节」这个地板**按构建档取**（Plan 06 Task 7 实测出来的）。

     改前这里是一个写死的 `rawBytes > 20000`，而那个 20000 是**dev 档**标定的：
     dev 模式下 vite 把每个 SFC 的 css 与全局 css 都作为 `<style>` 注进 DOM
     （本文件第 1963 行那段注释逐字记着这件事），于是光那 65 kB 的 `index.css`
     就把每一条路由的原始 DOM 顶到 20 kB 以上。**产品档**（`npm run build` 的产物
     由 uvicorn 同源发出来，Plan 06 Task 7 的那个档）恰恰相反：CSS 是
     `/assets/index-*.css` 一个**外链**，一个字节都不在 DOM 里。

     实测（同一份代码、同一个演示库、同一次 `demo.ps1` 灌出来的 60 人；
     两档各跑一整遍 smoke，逐条量 `document.documentElement.outerHTML` 的字节数）：

         路由                dev 档（vite 5173）   产品档（uvicorn 8020）   倍数
         login                        186 272                9 329        19.97×
         bind                         185 175                9 996        18.52×
         s-home                       190 637               14 821        12.86×
         s-weekly-sheet               197 482               22 253         8.87×
         s-check-in                   198 098               21 226         9.33×
         s-rpe                        197 292               21 340         9.25×
         s-mini-test                  195 209               18 187        10.73×
         s-notifications              190 210               15 034        12.65×
         t-dashboard                  263 136               45 923         5.73×
         t-report                     245 802               42 952         5.72×
         t-alerts                     309 625              121 370         2.55×
         t-students/10                227 098               43 027         5.28×
         admin                        200 175               25 115         7.97×
         admin-list                   191 518               15 015        12.75×
         admin-detail                 183 928                8 853        20.78×

     ⚠️ 两档的**最小值**分别是 183 928（dev）与 8 853（产品档），相差 20.8×；
     而 dev 档最小值 183 928 只比那个写死的 20000 高出 9.2×，产品档最小值 8 853
     **就在它下面**。于是「一个写死的 20000」在产品档上红了 **7 条**
     （login / bind / s-home / s-mini-test / s-notifications / admin-list / admin-detail），
     而这 7 条的**内容断言全部是绿的**：`missing.length === 0`（needle 一条不缺）、
     没有被守卫弹到 /login、没有文本重叠、没有横向溢出、`.app` 的 surface class 正确。
     红的原因**只有**字节地板这一格 —— 它量的是「vite 有没有把 CSS 注进来」，
     而不是它自己那句注释声称的「页面渲染出来了」。

     ⚠️ **处置是「把判据做准」，不是「把数字调小」**（硬规矩 #92 的正面读法：
     不许为了让一个坏掉的东西看起来绿而放宽判据；而这里东西没坏，坏的是
     一个**跨档不成立的常量**）。故 dev 档的地板**一字不动**仍是 20000，
     产品档另取一个 6000，两者的取值理由都在下面那两行注释里。

     ⚠️ **档位判定是双侧的、且认不出就红**（硬规矩 #50：一个恒用不到的分支
     与一个真的分支在颜色上无法区分 —— 若只看「有没有 `/@vite/client`」，
     那么 vite 哪天改了那个脚本名，dev 档就会**静默地**掉到 6000 那个松地板上，
     而 20000 那道守卫从此恒绿）。两个标记都是本 Task 亲跑量出来的：

         标记                       dev（vite 5173/5174）   产品档（uvicorn 8020）
         `/@vite/client`            命中 ×1                 0
         `src="/assets/`            0                       命中 ×1
         `/src/main.ts`             命中 ×1                 0

     （命令：`http.client` 各打一发 `GET /login`，逐个数子串。）
     ⚠️ 而 `frontend/index.html` 里**没有**任何 `/assets/` 引用（它的入口逐字是
     `<script type="module" src="/src/main.ts">`），且本前端没有 `public/` 目录，
     故 dev 档的 DOM 里不可能出现 `src="/assets/`。两侧都命中或都不命中 → `unknown` → 红。 */
  const DEV_DOM_MARKER = '/@vite/client'
  const PROD_DOM_MARKER = 'src="/assets/'
  /** dev 档的地板：**改前那个数，一字不动**（它标定的就是 vite 注入 CSS 之后的 DOM）。 */
  const DEV_DOM_FLOOR = 20000
  /** 产品档的地板。⚠️ 取值不是拍的，两侧各留 ≥ 1.5×（硬规矩 #42 的分辨率线）：
   *   下界 = 一个**白屏**的产品档页面（JS 没跑起来）的 `outerHTML` ≈ 发出的那份
   *   `index.html` 本体 = **2729 B**；上界 = 本次实测最小的那条真渲染页面
   *   （`admin-detail` **8853 B**）。6000 对前者是 2.2×、对后者是 0.68×，
   *   即「白屏一定红、真渲染一定绿」，而两档之间没有第三条路。 */
  const PROD_DOM_FLOOR = 6000

  /** 一份 DOM 属于哪个构建档；认不出（两个标记都命中或都不命中）回 `'unknown'`。 */
  function buildTierOf(dom) {
    const dev = dom.includes(DEV_DOM_MARKER)
    const prod = dom.includes(PROD_DOM_MARKER)
    if (dev === prod) return 'unknown'
    return dev ? 'dev' : 'prod'
  }

  /** 本次运行里 16 条路由各自的档位判定（收尾时断言它们**一致**）。 */
  const TIERS_SEEN = []

  /* ⚠️⚠️ **Plan 07 Task 1：试用告示的 needle**。
     ⚠️ 取「请勿录入真实学生信息」这一段，而**不是**「试用环境」或「高保真仿真」：
     那两段在页面上有第二处同串的风险（`Login.vue` / `Bind.vue` 的说明文字与
     `App.vue` 的页脚都在讲身份与数据这一类事），而这一段是那条告示**独有**的祈使句。
     ⚠️ 而「它确实无歧义」不靠这句注释，靠下面第 ② 拍（在正文里**恰好 1 处**）——
     Plan 06 Task 15 / 终审 S3-⑦ 刚修过一格 needle 歧义，同一族失效不许再犯。 */
  const TRIAL_NEEDLE = '请勿录入真实学生信息'

  /** 本次运行里 16 条路由各自「有没有告示」的实测（收尾时与档位对拍）。 */
  const TRIAL_NOTES = []

  for (const route of ROUTES) {
    const { html, at } = await dumpRoute(route, TRIAL_EXPECTED ? [TRIAL_NEEDLE] : [])
    const body = stripEmbedded(html)
    const plain = toPlainText(html)
    /* ⚠️ Plan 05B：needle 只在**剥掉 style/script 之后**的正文里找。
       旧写法多了一个 `|| html.includes(n)` 的出口，而 dev 模式下 vite 会把每个
       SFC/全局 css 作为 <style> 注进 DOM —— 于是一句**含 needle 的 CSS 注释**就能
       顶替真正文让断言假绿。本波实测抓到一次：s-home 的 needle「的本周」与
       「本周」+「训练量」连成的那五个字命中的是 base.css 里 .num--hero 那句注释
       （「首页的本周训练量、大屏的关键指标」），而页面真实状态是 403 横幅 +
       空白正文（Home.vue 读了一个 Plan 05A 已收成教职专用的端点）。两处都已修
       （注释改写 + Home.vue 改读会话），而这一格把**断言**里的假出口关掉了。
       ⚠️⚠️ 而 05B 那句「永久关掉」当时只对本行成立：**上面 `dumpRoute` 的轮询退出
       条件里还留着同一个 `|| html.includes(n)`**（终审 I4 查出来的），且那一处的
       `plain` 是**弱剥**（只剥标签）—— 与本行同名、强度不同、相隔 90 行。
       两处今天都改成读 `toPlainText` 那一个住址了，守卫是第 17 步那一拍。 */
    const missing = route.needles.filter((n) => n !== undefined && !plain.includes(n))
    const rawBytes = Buffer.byteLength(html, 'utf8')
    if (CURRENT !== null) {
      CURRENT.exchanges.push({
        method: 'CDP-DUMP-DOM',
        url: WEB + route.url,
        requestHeaders: { Cookie: route.jar === null ? '（匿名）' : '（已从 jar 种进浏览器，值已掩）' },
        as: route.jar,
        requestBody: null,
        status: 200,
        responseBodyBytes: rawBytes,
        responseBody: `__dom__ ${route.needles.length} 条断言，缺 ${missing.length} 条：${missing.join(' | ')}`,
        domBytes: rawBytes,
        domMissing: missing,
        domFinalLocation: at,
      })
    }
    out(`  → CDP ${WEB}${route.url}  (jar=${route.jar ?? '（匿名）'})`)
    out(`  ← DOM=${rawBytes} bytes（剥掉 style/script 后 ${body.length}）  location=${at}`)
    /* ⚠️ 门槛卡在**原始 DOM** 的字节数上，不是剥掉 style/script 之后的：
       dev 模式下 vite 把 CSS 与模块加载器都注进 `<style>` / `<script>`，
       剥完之后剩下的正文只有几 KB —— 拿它当「页面渲染出来了」的判据会假红。
       ⚠️⚠️ 而「原始 DOM 有多少字节」这件事**跨构建档不成立**（产品档的 CSS 是外链、
       一个字节都不在 DOM 里），故地板按档取：逐字理由、两档的实测表与
       6000 / 20000 两个数的取值依据都在上面 `DEV_DOM_MARKER` 那一段注释里。 */
    const tier = buildTierOf(html)
    TIERS_SEEN.push(tier)
    const domFloor = tier === 'dev' ? DEV_DOM_FLOOR : PROD_DOM_FLOOR
    const markersHit = (html.includes(DEV_DOM_MARKER) ? 1 : 0)
      + (html.includes(PROD_DOM_MARKER) ? 1 : 0)
    check(`${route.name}：DOM 里出现了 ${route.needles.length} 条关键内容`,
      tier !== 'unknown' && rawBytes > domFloor && missing.length === 0,
      missing.length !== 0
        ? `缺 ${missing.map((m) => JSON.stringify(m)).join(' | ')}（location=${at}）`
        : (tier === 'unknown'
          ? `认不出构建档：${DEV_DOM_MARKER} 与 ${PROD_DOM_MARKER} 两个标记命中了 ${markersHit} 个（应当恰好 1 个），于是地板无从取`
          : `DOM ${rawBytes} bytes（${tier} 档，地板 ${domFloor}）`))
    // ⚠️ **反假绿**：一条业务路由若被守卫弹到了 /login，它的关键内容一定全缺，
    //    但「弹到登录页」与「页面渲染坏了」是两种真因，故把最终 location 也断一遍。
    if (route.jar !== null) {
      check(`${route.name}：没有被守卫弹到 /login（cookie 真的生效了）`,
        !at.startsWith('/login'), `location=${at}`)
    }

    /* ---------------------------------------------------- Plan 07 Task 1 的试用告示
       ⚠️ 三档各跑一整遍时，本块是「告示**只**在试用档出现」的唯一运行时证据。
       ⚠️⚠️ 期望侧取自**本进程的 `PE_TRIAL`**，⚠️ 不是取自 `/api/health`：
       告示是 `App.vue` 按那一次 HTTP 响应渲染的，期望侧若也读它，两侧就**同源**了
       —— 后端把 `trial` 答错（例如开发档上答 `true`）时期望侧会跟着错，
       于是「告示泄漏到别的档」这一档**恒绿**（硬规矩 #35）。
       三档的取值：dev 档与产品档 `PE_TRIAL` 未设 ⇒ 16 条路由**都没有**；
       试用档（`scripts/trial.ps1` 起的）⇒ 16 条路由**都有**。
       ⚠️ 三拍：① 有没有 == 该不该有；② 试用档下它在正文里**恰好 1 处**（无歧义）；
       ③ 试用档下告示里那个「N 名学生均为虚构」的 N == `/api/health` 的 `students`
       （DOM vs HTTP，两侧不同源 ⇒ 「在前端写死一个 60」会红）。 */
    const hasTrialNote = plain.includes(TRIAL_NEEDLE)
    TRIAL_NOTES.push(hasTrialNote)
    check(`${route.name}：试用告示${TRIAL_EXPECTED ? '**在**' : '**不在**'}`
      + `（期望侧 = 本进程的 PE_TRIAL=${TRIAL_EXPECTED ? '1' : '（未设）'}；被测侧 = 渲染出来的 DOM 正文）`,
      hasTrialNote === TRIAL_EXPECTED,
      `正文里${hasTrialNote ? '有' : '没有'} ${JSON.stringify(TRIAL_NEEDLE)}，本档期望${TRIAL_EXPECTED ? '有' : '没有'}`)
    if (TRIAL_EXPECTED) {
      const noteHits = plain.split(TRIAL_NEEDLE).length - 1
      check(`${route.name}：试用告示的 needle 在正文里**恰好 1 处**`
        + '（无歧义 ⇒ 它真的钉住了那一处；两处同串的话把 App.vue 那一条删掉仍然绿，终审 S3-⑦）',
        noteHits === 1, `${noteHits} 处`)
      const wantCount = `（${SHARED.healthStudents} 名学生均为虚构）`
      check(`${route.name}：告示里「N 名学生均为虚构」的 N == /api/health 的 students`
        + '（DOM vs HTTP，两侧不同源 ⇒ 在前端写死一个数会红）',
        plain.includes(wantCount), `正文里找 ${JSON.stringify(wantCount)}`)
    }

    /* ---------------------------------------------------------- §4.1 的机器守卫
       ⚠️ 用户 7 条要求里唯一能机器判定的一条：「不能出现文本内容重叠」。
       故它必须是守卫（会红），不能只靠人眼看截图。⚠️ 取值时机就是 dumpRoute
       轮询到关键内容都出现之后 —— 与截图/needle 同一个页面状态。 */
    const layoutRes = await cdp.send(
      'Runtime.evaluate',
      { expression: LAYOUT_PROBE, returnByValue: true },
      sessionId,
    )
    const layout = JSON.parse(String(layoutRes?.result?.value ?? '{}'))
    out(`    布局守卫：含文本叶子 ${layout.leaves} 个、重叠 ${layout.overlapCount} 处、`
      + `非故意横向溢出 ${layout.overflowCount} 处、整页 scrollWidth ${layout.pageScrollWidth}`
      + ` / innerWidth ${layout.innerWidth}`)
    check(`${route.name}：没有文本内容重叠（§4.1；谓词已在反例页上验过会报）`,
      (layout.overlapCount ?? 1) === 0,
      JSON.stringify(layout.overlaps ?? []))
    check(`${route.name}：没有非故意的横向溢出（overflow-x 可见却 scrollWidth 超出的元素）`,
      (layout.overflowCount ?? 1) === 0,
      JSON.stringify(layout.overflows ?? []))
    check(`${route.name}：整页没有横向滚动条（documentElement.scrollWidth <= innerWidth）`,
      (layout.pageScrollWidth ?? 1e9) <= (layout.innerWidth ?? 0),
      `scrollWidth=${layout.pageScrollWidth} innerWidth=${layout.innerWidth}`)

    /* ---------------------------------------------------------- 终审 M1 的机器守卫
       ⚠️ 它守的是**渲染后的真值**：外壳（`.app`）上到底挂的是哪个 class。
       来历：`base.css` 那两个 surface 类的注释一度逐字写着「判据是 `meta.surface
       === 'board'`」，而当时 `'board'` **不在取值域里**（`RouteMeta` 声明的是
       `'paper' | 'ink'`）—— 照着那一句去改 `App.vue` 的人会**静默**让大屏丢掉
       `.surface-board`、拿到 `--bg` 的纯白，于是 05B「靠填充差让白面板站出来」的
       核心手法当场失效；而 `check:tokens` 只查色值、`vue-tsc` 拦不到注释里的字面值。
       ⚠️ 待清扫波已把字面值改成 `base` / `board`（与类名同词），那个陷阱不再存在，
       而**本拍照旧留着**：它是唯一一条查渲染真值的（第 17 步 ③ 只查源码面，
       「注释与代码一致」这件事只有真渲染一次才算数）。
       ⚠️ 16 条路由逐条断（不只断大屏）：少了另外 15 条，「大屏拿到了 surface-board」
       可能只是因为它两条都拿到了。 */
    const surfaceRes = await cdp.send('Runtime.evaluate',
      { expression: 'document.querySelector(".app")?.className ?? ""', returnByValue: true }, sessionId)
    const surfaceClass = String(surfaceRes?.result?.value ?? '')
    const wantBoard = route.name === 't-dashboard'
    check(`${route.name}：外壳（.app）拿到的 surface class 是 ${wantBoard ? 'surface-board' : 'surface-base'}（M1）`,
      surfaceClass.includes(wantBoard ? 'surface-board' : 'surface-base')
        && !surfaceClass.includes(wantBoard ? 'surface-base' : 'surface-board'),
      `class=${JSON.stringify(surfaceClass)}`)

    /* -------------------------------------------------- Plan 06 Task 15 的两块新取证
       ① `uniqueNeedles`：逐条断言「这个 needle 在正文里**恰好 1 处**」。
          ⚠️ 它钉的不是「文字在不在」，而是「这条 needle **有没有歧义**」——
          终审 S3-⑦ 的失效形状逐字是：needle 在页面上有两处同串，于是改坏它要钉的
          那一处仍然全绿。⚠️ 只对**指名**的几条断（不是全部 needle）：`me?.name`
          一类 legitimately 会出现多次，一刀切会假红。
       ② `admin-audit-logs`：九列列头逐个断言（DOM vs 后端响应体，两侧不同源）。 */
    for (const n of route.uniqueNeedles ?? []) {
      const hits = plain.split(n).length - 1
      check(`${route.name}：needle ${JSON.stringify(n)} 在正文里**恰好 1 处**`
        + '（无歧义 ⇒ 它真的钉住了那一段；两处同串的话改坏那一段仍然全绿，终审 S3-⑦）',
        hits === 1, `${hits} 处`)
    }
    if (route.name === 'bind') {
      /* ⚠️⚠️ **Plan 08 Task 4 的两拍**：`/bind` 页从本波起有**两档**
         （缺省档 = 自助绑定；`?token=…` 档 = 一次性令牌），而派单 §2 第 8 条逐字要求
         「**缺省档的 UI 一格都不许变**（开关是**服务端**的事，前端不该猜）」。

         ⚠️ 那一格的可执行形式是下面这**三拍**（缺任何一拍都会有一个改法绿着通过）：

         ① **缺省档的 DOM 形状**：那四个既有输入框（`#bind-student-no` / `#bind-birth`
            / `#bind-staff-no` / `#bind-name`）中「学生那一半」**在**、
            radio **恰好 2 个**（不是 3 个）、而 `#bind-token` **不存在**。
            ⚠️ 少了「radio 恰好 2 个」这一拍，「顺手加第三个『令牌』radio」
            ——那是本件**最容易**被做成的改法——会绿着通过，而它恰好把
            「缺省档一格都没变」那句话变成假的；
         ② **令牌档的 DOM 形状**：真的 `Page.navigate` 到 `/bind?token=…`，断言
            `#bind-token` **在**且它的值就是 URL 上带来的那一串、
            radio 那一组**整组不渲染**（0 个）、`#bind-birth` **不存在**
            （⇒ 令牌档**不**问出生日期，那正是这条更强的路的全部理由）；
         ③ **两档的按钮文案不同**（`绑定口令并登录` vs `用令牌绑定口令`）：
            令牌档**不自动登录**（后端 204 没有响应体 ⇒ 前端读不出学号，
            逐字理由见 `views/auth/Bind.vue` 的 `submit()`），故按钮上不许承诺「并登录」。

         ⚠️ **两档都不提交**（不真的发一次兑换）：本步的判据是**渲染形状**，
         而「令牌能不能兑换」由第 16 步的鉴权全链路 + 后端 `tests/api/test_bind_token.py`
         的 24 条守卫钉；在这里再发一次会让「一张令牌只能用一次」那一格
         在两步之间互相消耗（第 16 步就拿不到活令牌了）。 */
      const DEFAULT_PROBE = 'JSON.stringify({'
        + 'token: !!document.querySelector("#bind-token"),'
        + 'studentNo: !!document.querySelector("#bind-student-no"),'
        + 'birth: !!document.querySelector("#bind-birth"),'
        + 'radios: document.querySelectorAll("input[name=bind-kind]").length,'
        + 'submit: document.querySelector(".auth__actions button[type=submit]")?.textContent?.trim() ?? ""'
        + '})'
      const before = JSON.parse(String((await cdp.send('Runtime.evaluate',
        { expression: DEFAULT_PROBE, returnByValue: true }, sessionId))?.result?.value ?? '{}'))
      check('§Task4-① /bind **缺省档**的 DOM 形状一格未变（没有 #bind-token、radio 恰好 2 个、学号与出生日期两格都在）',
        before.token === false && before.studentNo === true && before.birth === true
          && before.radios === 2 && before.submit.includes('绑定口令并登录'),
        JSON.stringify(before))

      const PROBE_TOKEN = 'SEL_probe_smoke.nope-not-a-real-secret'
      await cdp.send('Page.navigate',
        { url: `${WEB}/bind?token=${encodeURIComponent(PROBE_TOKEN)}` }, sessionId)
      const deadlineToken = Date.now() + 30000
      let tokenDom = {}
      for (;;) {
        tokenDom = JSON.parse(String((await cdp.send('Runtime.evaluate', {
          expression: 'JSON.stringify({'
            + 'value: document.querySelector("#bind-token")?.value ?? null,'
            + 'radios: document.querySelectorAll("input[name=bind-kind]").length,'
            + 'birth: !!document.querySelector("#bind-birth"),'
            + 'studentNo: !!document.querySelector("#bind-student-no"),'
            + 'password: !!document.querySelector("#bind-password"),'
            + 'confirm: !!document.querySelector("#bind-confirm"),'
            + 'submit: document.querySelector(".auth__actions button[type=submit]")?.textContent?.trim() ?? ""'
            + '})',
          returnByValue: true,
        }, sessionId))?.result?.value ?? '{}'))
        if (tokenDom.value !== null) break
        if (Date.now() > deadlineToken) break
        await sleep(300)
      }
      check('§Task4-② /bind?token=… **令牌档**：#bind-token 在、值就是 URL 上那一串、radio 整组不渲染、且**不问出生日期**',
        tokenDom.value === PROBE_TOKEN && tokenDom.radios === 0
          && tokenDom.birth === false && tokenDom.studentNo === false
          && tokenDom.password === true && tokenDom.confirm === true,
        JSON.stringify(tokenDom))
      check('§Task4-③ 令牌档的按钮文案**不承诺**「并登录」（后端 204 没有响应体 ⇒ 前端读不出学号，故它把人送去 /login）',
        String(tokenDom.submit ?? '').includes('用令牌绑定口令')
          && !String(tokenDom.submit ?? '').includes('并登录'),
        JSON.stringify(tokenDom.submit ?? ''))
      // ⚠️ 导航回去：下面那些**跨路由**的收尾拍（§Tier / §Trial / 布局谓词）
      //    读的是「本条路由的那一帧」，把它留在令牌档会让它们量到错的形状。
      await cdp.send('Page.navigate', { url: WEB + route.url }, sessionId)
      await sleep(600)
    }
    if (route.name === 'admin-index') {
      /* ⚠️⚠️ **Plan 08 Task 4 的第 06 块**：一次性绑定令牌的签发面板住在 `/admin`
         这一页上（⚠️ **不新开路由**，故本步那一条「路由条数 = 16」逐字未变）。
         三拍：① 那一块的抬头与两个控件（`#bt-kind` / `#bt-login`）**在**；
         ② 台账那张表**渲染出来了**（`.a-table thead th` 恰好 8 个列头）——
         ⚠️ 它是「`GET /api/auth/bind-tokens` 真的被调通并渲染」的闸门：
         一个 403/401 会让 `<tbody>` 只剩那一行空态，而列头**照旧**是 8 个，
         故本拍**另加**一条「表格里出现了后端给的那一个字段名 slug」；
         ③ ⚠️ **明文令牌此刻不在 DOM 里**（还没签发过 ⇒ `#bt-plaintext` 不存在）。
         那一拍钉的是「明文只在签发那一刻出现一次」在**前端**也成立
         （后端那一半由 `tests/api/test_bind_token.py` 的
         `test_the_listing_never_returns_the_plaintext_nor_the_hash` 钉）。 */
      const panel = JSON.parse(String((await cdp.send('Runtime.evaluate', {
        expression: 'JSON.stringify({'
          + 'kind: !!document.querySelector("#bt-kind"),'
          + 'login: !!document.querySelector("#bt-login"),'
          + 'ths: [...document.querySelectorAll(".a-table thead th")].length,'
          + 'slugs: [...document.querySelectorAll(".a-table thead th code")].map(c => c.textContent.trim()).join(","),'
          + 'plaintext: !!document.querySelector("#bt-plaintext"),'
          + 'headings: [...document.querySelectorAll(".a-page section")].length'
          + '})',
        returnByValue: true,
      }, sessionId))?.result?.value ?? '{}'))
      check('§Task4-④ /admin 第 06 块：签发面板的两个控件在、台账 8 个列头逐字对得上、而**明文令牌不在 DOM 里**',
        panel.kind === true && panel.login === true && panel.ths === 8
          && panel.slugs === 'id,kind,login,issued_at,expires_at,used_at,issued_by'
          && panel.plaintext === false,
        JSON.stringify(panel))
    }
    if (route.name === 'admin-audit-logs') {
      /* ⚠️ 期望侧是**字面量**（本波在渲染出来的 DOM 上实测的九个 (label, key)），
         被测侧是 `.a-table thead th` 的真文本 —— 两侧不同源。
         ⚠️ 而九列的**字段名**那一侧另有一道交叉验证：与后端 `GET /api/audit-logs`
         真回的那一行的**键顺序**逐字对拍（`AuditLogRead` 的九格；§13.9 那条
         「九格全是标量、一个都不多」的裁定在 UI 上的唯一可见面就是这九列）。
         ⚠️ 改前这一格只有裸 needle `'身份类型'`（歧义，见上面 ROUTES 那一段注释），
         终审把列头 label 改成「身份种类」→ smoke 637/0 全绿。 */
      const WANT_COLUMNS = [
        ['行 id', 'id'], ['时刻', 'at'], ['身份类型', 'subject_kind'], ['身份 id', 'subject_id'],
        ['工号', 'staff_no'], ['方法', 'method'], ['路径', 'path'], ['状态码', 'status'],
        ['对象', 'target'],
      ]
      const thRes = await cdp.send('Runtime.evaluate', {
        expression: 'JSON.stringify([...document.querySelectorAll(".a-table thead th")].map('
          + '(th) => [th.childNodes[0]?.textContent?.trim() ?? "",'
          + ' th.querySelector("code")?.textContent?.trim() ?? ""]))',
        returnByValue: true,
      }, sessionId)
      const ths = JSON.parse(String(thRes?.result?.value ?? '[]'))
      out(`    审计页列头 ${ths.length} 个：${JSON.stringify(ths.map((t) => t[0]))}`)
      eq('§S3-⑦ 审计页的列头**恰好 9 个**（AuditLogRead 的九格，一个都不多）',
        ths.length, WANT_COLUMNS.length)
      check('§S3-⑦ 九列的**中文列头文案 + 字段 slug 逐个逐字相同、且顺序相同**'
        + '（期望侧是本波实测的字面量，被测侧是渲染出来的 `<th>`；改一个字就红）',
        JSON.stringify(ths) === JSON.stringify(WANT_COLUMNS),
        `DOM=${JSON.stringify(ths)}`)
      const auditRow = await req('GET', '/api/audit-logs?limit=1',
        { as: 'admin', quiet: true, record: false })
      const backendKeys = Object.keys(auditRow.json?.items?.[0] ?? {})
      out(`    后端那一行的键顺序：${JSON.stringify(backendKeys)}`)
      eq('§S3-⑦ 交叉验证：后端 `GET /api/audit-logs` 真回的那一行**也是 9 个键**', backendKeys.length, 9)
      check('§S3-⑦ 交叉验证：九列的 slug 与后端响应体的**键顺序逐字相同**'
        + '（DOM vs HTTP，两侧不同源 ⇒ 「列头对不上后端字段名」会红）',
        JSON.stringify(ths.map((t) => t[1])) === JSON.stringify(backendKeys),
        `DOM=${JSON.stringify(ths.map((t) => t[1]))} API=${JSON.stringify(backendKeys)}`)

      /* ⚠️⚠️ **Plan 08 Task 1 新加的六拍**：管理台「写 / 读」切换的运行时取证。
         ⚠️ 派单 §2 第 7 条裁定**不新开页面**（新开会让路由数 16 → 17，而本步上面那句
         `eq('路由条数 = 16…')`、甲方试用说明书 §5、README 三处都钉着 16），
         故「读」那一档是**页面内的一个状态**，而它因此**只有本步能验**：
         路由表、`ROUTES` 那 16 条、`check:dist` 的产物清单都看不见它。
         ⚠️ 六拍各挡一件事：① 切换按钮在（钩子是 `data-audit-tab="read"`）；
         ② 切过去之后列头**仍然恰好 9 个**（⚠️ 承重：两张表 `v-if` 互斥，
         同时渲染的话 `querySelectorAll('.a-table thead th')` 会数到 **18**，
         而上面「写」档那三拍会一起红 —— 那是本波最容易踩的一格）；
         ③ 读档九列的中文列头 + slug 逐个逐字相同、且顺序相同；
         ④ 后端 `GET /api/read-audit-logs` 真回的那一行**也是 9 个键**；
         ⑤ 读档九列的 slug 与后端响应体的**键顺序逐字相同**（DOM vs HTTP，两侧不同源）；
         ⑥ 那张表**真的有行**（⚠️ 反空转：少了本拍，「端点没挂上」与「今天没人翻过档案」
         在颜色上不可分辨 —— 而本步前面已经打了几十个敏感读，故它必须 > 0）。 */
      const WANT_READ_COLUMNS = [
        ['行 id', 'id'], ['时刻', 'at'], ['身份类型', 'subject_kind'], ['身份 id', 'subject_id'],
        ['工号', 'staff_no'], ['路由模板', 'route'], ['学生 id', 'student_id'],
        ['状态码', 'status'], ['对象', 'target'],
      ]
      const clicked = await cdp.send('Runtime.evaluate', {
        expression: '(() => { const b = document.querySelector(\'[data-audit-tab="read"]\');'
          + ' if (!b) return \'NO-BUTTON\'; b.click(); return \'CLICKED\' })()',
        returnByValue: true,
      }, sessionId)
      check('§P8T1-① 页面上有一个「读审计」的切换按钮（`data-audit-tab="read"`）'
        + '（⚠️ 派单 §2 第 7 条裁定「不新开页面」，故路由数仍是 16、'
        + '而这一档只有本步能验）',
        String(clicked?.result?.value) === 'CLICKED', String(clicked?.result?.value))
      /* 轮询到读档那张表的列头换过来（最多 8 s）。⚠️ 不用一次 `setTimeout`：
         切换会触发一次 `useAsync.reload()`，而列头是 `v-if` 换表的**同一帧**、
         行是**下一帧**，故判据取「slug 里出现了 `route`」而不是「行数 > 0」。 */
      let readThs = []
      for (let i = 0; i < 40; i += 1) {
        const r = await cdp.send('Runtime.evaluate', {
          expression: 'JSON.stringify([...document.querySelectorAll(".a-table thead th")].map('
            + '(th) => [th.childNodes[0]?.textContent?.trim() ?? "",'
            + ' th.querySelector("code")?.textContent?.trim() ?? ""]))',
          returnByValue: true,
        }, sessionId)
        readThs = JSON.parse(String(r?.result?.value ?? '[]'))
        if (readThs.some((t) => t[1] === 'route')) break
        await new Promise((r2) => setTimeout(r2, 200))
      }
      out(`    读档列头 ${readThs.length} 个：${JSON.stringify(readThs.map((t) => t[0]))}`)
      eq('§P8T1-② 切到「读」档之后列头**仍然恰好 9 个**（⚠️ 两张表 `v-if` 互斥：'
        + '同时渲染的话这一格会是 18，而上面「写」档那三拍会一起红）',
        readThs.length, WANT_READ_COLUMNS.length)
      check('§P8T1-③ 读档九列的**中文列头文案 + 字段 slug 逐个逐字相同、且顺序相同**'
        + '（期望侧是本波实测的字面量，被测侧是渲染出来的 `<th>`；改一个字就红）',
        JSON.stringify(readThs) === JSON.stringify(WANT_READ_COLUMNS),
        `DOM=${JSON.stringify(readThs)}`)
      const readRow = await req('GET', '/api/read-audit-logs?limit=1',
        { as: 'admin', quiet: true, record: false })
      const readBackendKeys = Object.keys(readRow.json?.items?.[0] ?? {})
      out(`    后端读档那一行的键顺序：${JSON.stringify(readBackendKeys)}`)
      eq('§P8T1-④ 交叉验证：后端 `GET /api/read-audit-logs` 真回的那一行**也是 9 个键**',
        readBackendKeys.length, 9)
      check('§P8T1-⑤ 交叉验证：读档九列的 slug 与后端响应体的**键顺序逐字相同**'
        + '（DOM vs HTTP，两侧不同源 ⇒ 「列头对不上后端字段名」会红）',
        JSON.stringify(readThs.map((t) => t[1])) === JSON.stringify(readBackendKeys),
        `DOM=${JSON.stringify(readThs.map((t) => t[1]))}`
        + ` API=${JSON.stringify(readBackendKeys)}`)
      check('§P8T1-⑥ 反空转：那张表**真的有行**（本步之前已经打了几十个敏感读，'
        + '故 `total` 必须 > 0；少了本拍，「端点没挂上」与「今天没人翻过档案」'
        + '在颜色上不可分辨）',
        (readRow.json?.total ?? 0) > 0, `total=${readRow.json?.total}`)
      out(`    读档 total=${readRow.json?.total} · 最新一行 route=`
        + `${JSON.stringify(readRow.json?.items?.[0]?.route)}`
        + ` student_id=${JSON.stringify(readRow.json?.items?.[0]?.student_id)}`)
    }

    /* ---------------------------------------------------- Plan 06 Task 10 的真取证
       ⚠️ 只打在 `t-student-detail` 上：那一条路由的第 03 块自本波起又有三格
       （「小测综合分」/「折返班内百分位」/「深蹲得分」），而其中**两格**读的是
       Plan 06 Task 10 新加的教师侧变体 `GET /api/teacher/students/{id}/normalized`。
       ⚠️ 三拍各自挡一件事：
       ① 那一格**真的渲染出数**、且与后端回的 `composite` 逐字相等（含小数位数）；
       ② 「深蹲得分」那一格本波**改回读变体**（Task 9 的降级处置是读原始行的
          `squat_30s_count`）——⚠️ 两个来源今天数值相同，故本拍钉的**不是**数值、
          而是「三格同源」这件事在渲染面上成立（`selfOf(...)` 查不到时会渲染「—」，
          那与一个数**不同形**，故本拍同时挡住「变体没被调通」那一档）；
       ③ 「折返班内百分位」仍然读**班级端点**（全班的 `shuttle_score`，本页要它算
          `sample`/`slower`/`tied`/`rank`），而它与变体给的那一格**逐字相等**
          ——两侧在后端共用同一份分组与算式，故这一拍是「同源」的**交叉验证**。
       ⚠️ 而「三格有没有重叠/溢出」不需要本波另写：上面那三拍布局守卫
       （`overlapCount` / `overflowCount` / `pageScrollWidth`）对 16 条路由逐条都跑，
       那一块从两格变回三格之后它们照旧必须全绿。 */
    if (route.name === 't-student-detail') {
      const statsRes = await cdp.send('Runtime.evaluate',
        { expression: STAT_PROBE, returnByValue: true }, sessionId)
      const stats = JSON.parse(String(statsRes?.result?.value ?? '[]'))
      const valueOf = (label) => stats.filter((s) => s.label === label).map((s) => s.value)
      check('t-student-detail：「小测综合分」那一格**真的渲染出数**，且与教师侧变体的 '
        + '`composite` 逐字相等（真取证：两侧不同源，DOM 文本 vs HTTP 响应体）',
        valueOf('小测综合分').length > 0
          && JSON.stringify(valueOf('小测综合分')) === JSON.stringify(wantComposite),
        `DOM=${JSON.stringify(valueOf('小测综合分'))} API=${JSON.stringify(wantComposite)}`)
      check('t-student-detail：「深蹲得分」那一格同样读的是变体的 `squat_score`'
        + '（本波改回三格同源，不再读原始行的 `squat_30s_count`）',
        valueOf('深蹲得分').length > 0
          && JSON.stringify(valueOf('深蹲得分')) === JSON.stringify(wantSquat),
        `DOM=${JSON.stringify(valueOf('深蹲得分'))} API=${JSON.stringify(wantSquat)}`)
      check('t-student-detail：「折返班内百分位」读班级端点、而与变体的 `shuttle_score` '
        + '逐字相等（后端两个端点共用同一份分组与算式 → 交叉验证）',
        valueOf('折返班内百分位').length > 0
          && JSON.stringify(valueOf('折返班内百分位')) === JSON.stringify(wantShuttle),
        `DOM=${JSON.stringify(valueOf('折返班内百分位'))} API=${JSON.stringify(wantShuttle)}`)
    }

    /* ---------------------------------------------------- Plan 06 Task 13 的真取证（D6）
       ⚠️ 只打在 `s-mini-test` 上，姿势与上面教师页那三拍**逐字同款**
       （期望侧取 API、被测侧用 CDP 抓 `.stat__label` / `.stat__value`，两侧不同源）。
       ⚠️ 三格各自的来源**不同**：综合分与深蹲读**窄端点** `/normalized/me`、
       折返百分位读**班级端点** `/normalized` 里我那一行，故这三拍同时钉住
       「两个端点都被调通了」与「Vue 没有把两格的来源接反」——
       而后者正是「静态 needle 证明不了」的那一档（Task 9 登记的待清扫）。
       ⚠️ **没有放宽任何既有判据**：改前那两条静态 needle（`二次小测` / `30 秒深蹲`）
       逐字保留，本波只是**加**了第三条 needle（闸门）与三拍真取证。 */
    if (route.name === 's-mini-test') {
      const statsRes = await cdp.send('Runtime.evaluate',
        { expression: STAT_PROBE, returnByValue: true }, sessionId)
      const stats = JSON.parse(String(statsRes?.result?.value ?? '[]'))
      const valueOf = (label) => stats.filter((s) => s.label === label).map((s) => s.value)
      check('s-mini-test：「小测综合分」那一格**真的渲染出数**，且与窄端点 `/normalized/me` 的 '
        + '`composite` 逐字相等（真取证：两侧不同源，DOM 文本 vs HTTP 响应体）',
        valueOf('小测综合分').length > 0
          && JSON.stringify(valueOf('小测综合分')) === JSON.stringify(wantMtComposite),
        `DOM=${JSON.stringify(valueOf('小测综合分'))} API=${JSON.stringify(wantMtComposite)}`)
      check('s-mini-test：「折返班内百分位」读的是**班级端点**里我那一行的 `shuttle_score`'
        + '（⚠️ 与上一格来源不同，故本拍同时钉住两个端点都被调通、且没有接反）',
        valueOf('折返班内百分位').length > 0
          && JSON.stringify(valueOf('折返班内百分位')) === JSON.stringify(wantMtShuttle),
        `DOM=${JSON.stringify(valueOf('折返班内百分位'))} API=${JSON.stringify(wantMtShuttle)}`)
      check('s-mini-test：「深蹲得分」读窄端点的 `squat_score`，而 `null` 那一档渲染的是「—」'
        + '不是 0（期望侧按 `StatBlock` 同一条规则算，故「把不知道讲成 0」会红）',
        valueOf('深蹲得分').length > 0
          && JSON.stringify(valueOf('深蹲得分')) === JSON.stringify(wantMtSquat),
        `DOM=${JSON.stringify(valueOf('深蹲得分'))} API=${JSON.stringify(wantMtSquat)}`)
    }
  }

  /* ⚠️ 档位判定的**收尾一拍**：16 条路由必须给出同一个档位，且不许是 `unknown`。
     它是上面那两格（每条路由各自的 `tier !== 'unknown'`）之外唯一一条
     **说出「本次量的是哪一档」**的断言 —— 取证要能从日志里读出「这一遍跑的是
     产品档、地板取的是 6000」，而不是靠人去推。
     ⚠️ 「一致」那一格挡的是混合态：例如某一条路由因为一次失败的导航拿到了
     一份**没有**任何标记的错误页，它会单独掉到 `unknown`（那一条自己已经会红），
     而本拍把这件事在总结里说清楚，免得 16 行红里看不出是「一档认不出」还是「全档认不出」。 */
  /* ⚠️ Plan 07 Task 1 的**收尾一拍**：把「本档 16 条路由上告示的实测条数」说出来并断言。
     它是上面那 16 拍之外唯一一条**说出总数**的断言 —— 取证要能从日志里一眼读出
     「这一遍跑的是试用档、16/16 条都挂着告示」，而不是靠人数 16 行 ✓。
     ⚠️ 而它同时是「告示不泄漏到别的档」那一半的**总数口径**：
     dev 档与产品档上它必须是 0/16。 */
  check(`§Trial 16 条路由上试用告示的**条数**与本档一致（PE_TRIAL=${TRIAL_EXPECTED ? '1' : '（未设）'} ⇒ 期望 ${TRIAL_EXPECTED ? ROUTES.length : 0} 条）`,
    TRIAL_NOTES.length === ROUTES.length
      && TRIAL_NOTES.every((seen) => seen === TRIAL_EXPECTED),
    `${TRIAL_NOTES.filter(Boolean).length}/${TRIAL_NOTES.length} 条有告示（期望 ${TRIAL_EXPECTED ? ROUTES.length : 0}）`)

  check('§Tier 16 条路由的构建档判定**一致**（dev 档地板 20000 / 产品档地板 6000，各只在自己的档上生效）',
    TIERS_SEEN.length === ROUTES.length
      && new Set(TIERS_SEEN).size === 1
      && TIERS_SEEN[0] !== 'unknown',
    `${TIERS_SEEN.length}/${ROUTES.length} 条给了判定，取值 = ${[...new Set(TIERS_SEEN)].join(',')}`)

  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 07 Task 5b 缺陷 ①**：「每日打卡」点「提交打卡」之后
     **一个请求都没发出去、而页面上一个字都没多**。

     改前的运行时取证（真鼠标点击 `Input.dispatchMouseEvent` + CDP，dev 档，学生 #4）：
       · `input[name="duration_min"]` 的 `step` 属性 = `0.5`，而它被 `CheckIn.vue` 的一个
         `watch` **预填**成库里那一行的真值 `30.9`（学生 4 的 2025-10-12 那一行）；
       · ⇒ `validity.stepMismatch === true`、`validationMessage` = 「请输入一个有效的值。
         最接近的两个有效值为 30.5 和 31。」、`form.checkValidity() === false`、
         `form.noValidate === false`；
       · ⇒ 点了「提交打卡」之后 `POST /api/training-logs` **0 次**（同屏 11 个 `/api`
         请求，点击前后逐字相同），`.s-notice` / 横幅 / `[role=alert]` **一个都没多**，
         只有 `document.activeElement` 变成了 `duration_min`（浏览器聚焦了那一格，
         而它那个原生气泡在页面里留不下任何痕迹）。
     ⚠️ 而它**不是**一个边角案例：演示库 840 行 `training_log` 里 `duration_min` 非空的
       628 行，小数位数实测是「1 位 565 行 / 0 位 63 行」，327 个 distinct 值里
       **258 个不是 0.5 的整数倍** ⇒ 任何学生选任何一天都大概率撞上。

     ⚠️ 本波实测还挖出**同一格里第三个静默**（比派单点的那一格更靠上游）：
       `durationText` 声明成 `Ref<string>`，而 Vue 的 `vModelText` 对
       `<input type="number">` **在运行时把值转成 number** ⇒ `submit()` 里那句
       `durationText.value.trim()` 当场 `TypeError`，而它抛在 `submitting.value = true`
       **之后**、`try` **之前** ⇒ `finally` 不跑 ⇒ 按钮**永久**停在「正在提交…」且
       disabled、**一个请求都没发**（CDP 实测原文：`[unhandled] native event handler
       TypeError: durationText.value.trim is not a function at submit (…/CheckIn.vue:157)`）。
       即：那一格的占位符逐字写着「例如 35」，而**照着它做就必中**。
       它此前一直没被发现，是因为同一个输入框上还有上面那个 `step` 静默先把它挡住了。

     ------------------------------------------------------------------
     这四组拍各钉什么（⚠️ 判据两侧**不同源**：期望侧是 HTTP 响应体，
     被测侧是 CDP 抓到的 DOM 文本与真鼠标点击之后浏览器真的发出去的那些请求）
     ------------------------------------------------------------------
       §CI-1  预填路径：库里那一行的一位小数被预填进去之后，表单**必须合法**、
              点提交**必须真的发出** `POST /api/training-logs`，且页面上看得见反馈。
              ⚠️ 把 `step` 改回 `0.5` → 本组红（定点变异实测过，见实现者报告 §3）。
       §CI-2  成功路径：**真键盘**输一个一位小数 → 201 + **可见的成功反馈**
              （`SuccessMark` 的「已打卡」只停留 `--dur-check-hold`，故要轮询）。
              ⚠️ 把 `String(durationText.value)` 改回 `durationText.value` → 本组红。
       §FV-1  **反静默**（本缺陷的真正病灶）：造一个必然校验失败的输入（清空必填的
              `log_date`）→ 断言 ① 一个请求都没发出去 ② 用户**看得见**一句人话
              （哪个字段 / 为什么 / 该怎么改 / 「没有发出任何请求」）。
              ⚠️ 摘掉表单上那个 `:ref="bindForm"` → 本组红。
       §FV-2  而那一句人话**不是打卡页自己写的一份**：登录页留空点「登录」是同一档
              失效（两个 `required` 拦下 submit，而 `submit()` 里那句本地检查根本跑不到），
              故在同一处断言它也看得见同一族那句话 ⇒ 处置是**共用**的。
     ------------------------------------------------------------------ */
  {
    /** 这一组打出去的写请求（POST）。⚠️ `cdp.on` 的监听器是一个 `Set`，
     *  故本监听器与下面 §I5 那一个互不相干、各收各的。 */
    const WRITES = []
    const WRITE_BY_ID = new Map()
    cdp.on('Network.requestWillBeSent', (p) => {
      if (p.request?.method !== 'POST') return
      const short = String(p.request?.url ?? '').replace(/^https?:\/\/[^/]+/, '')
      if (!short.startsWith('/api/')) return
      const rec = { requestId: p.requestId, path: short, body: String(p.request.postData ?? ''), status: null }
      WRITE_BY_ID.set(p.requestId, rec)
      WRITES.push(rec)
    })
    cdp.on('Network.responseReceived', (p) => {
      const rec = WRITE_BY_ID.get(p.requestId)
      if (rec !== undefined) rec.status = p.response.status
    })

    async function evaluate(expression) {
      const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true }, sessionId)
      if (r?.exceptionDetails !== undefined) {
        out(`    ⚠️ evaluate 抛了：${JSON.stringify(r.exceptionDetails).slice(0, 300)}`)
      }
      return r?.result?.value
    }

    /** ⚠️ 断言用的页面正文一律走 `toPlainText`（终审 I4 的单一所有者）：
     *  不给「needle 撞上一段 CSS 注释」留第二个出口。 */
    async function plainOf() {
      return toPlainText(String(await evaluate('document.documentElement.outerHTML') ?? ''))
    }

    /** 轮询**浏览器里**的一个谓词（返回 true 就停）。⚠️ 它只能读页面，
     *  读不到 Node 这一侧的变量 —— 那一类等待用下面那个 `untilWrites`。 */
    async function untilTrue(expression, timeoutMs, what) {
      const t0 = Date.now()
      for (;;) {
        if (await evaluate(expression) === true) return Date.now() - t0
        if (Date.now() - t0 > timeoutMs) {
          check(`§前置 等到「${what}」`, false, `${timeoutMs} ms 内没等到`)
          return -1
        }
        await sleep(200)
      }
    }

    /** 轮询到「POST 的条数比 `before` 多」为止（Node 这一侧的等待）。 */
    async function untilWrites(before, timeoutMs = 15000) {
      const t0 = Date.now()
      while (WRITES.length === before && Date.now() - t0 < timeoutMs) await sleep(150)
      return WRITES.length - before
    }

    /** 换一份 cookie + 换一档视口 + 导航。⚠️ 姿势逐字抄上面 `dumpRoute` 的前半段。 */
    async function navAs(jar, url, width = 430, height = 1800) {
      await cdp.send('Network.clearBrowserCookies', {}, sessionId)
      if (jar !== null) {
        const raw = JARS.get(jar) ?? (await ensureJar(jar))
        const set = await cdp.send('Network.setCookie', {
          name: 'pe_session', value: raw.slice('pe_session='.length),
          url: WEB, httpOnly: true, sameSite: 'Lax',
        }, sessionId)
        if (set?.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(set)}`)
      }
      await cdp.send('Emulation.setDeviceMetricsOverride',
        { width, height, deviceScaleFactor: 1, mobile: false }, sessionId)
      await cdp.send('Page.navigate', { url: WEB + url }, sessionId)
    }

    /** **真鼠标**点一个按钮：scrollIntoView → 量矩形 → moved/pressed/released 三发。
     *  ⚠️ 刻意不用 `el.click()`：本缺陷的判据正是「浏览器那一条交互式校验的路径」，
     *  而 §CI-1/§CI-2 要证明的是「一次真人点击之后请求真的发出去了」。
     *  @returns 那一个矩形（外加「那一点上到底是哪个元素」，供反空转断言）。 */
    async function realClick(selector) {
      await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(selector)})
        if (b !== null) b.scrollIntoView({ block: 'center' })
        return b !== null })()`)
      await sleep(500)
      const raw = await evaluate(`(() => {
        const b = document.querySelector(${JSON.stringify(selector)})
        if (b === null) return 'null'
        const r = b.getBoundingClientRect()
        const x = r.x + r.width / 2
        const y = r.y + r.height / 2
        const hit = document.elementFromPoint(x, y)
        return JSON.stringify({ x, y, text: b.textContent.trim(), disabled: b.disabled,
          hitTag: hit === null ? null : hit.tagName,
          hitInside: hit === null ? false : (b.contains(hit) || hit.contains(b)) })
      })()`)
      const rect = JSON.parse(String(raw ?? 'null'))
      if (rect === null) return null
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
      return rect
    }

    /** 取一个 POST 的响应体（`Network.getResponseBody`）。取不到就返回 null，
     *  由调用它的那几拍自己判红（不在这里判 —— 那不是本拍的被测面）。 */
    async function bodyOf(rec) {
      try {
        const r = await cdp.send('Network.getResponseBody', { requestId: rec.requestId }, sessionId)
        return JSON.parse(r.body)
      } catch (err) {
        out(`    ⚠️ 取不到 ${rec.path} 的响应体（${err?.message ?? err}）`)
        return null
      }
    }

    const FORM_PROBE = `(() => {
      const form = document.querySelector('form.form')
      if (form === null) return JSON.stringify(null)
      const dur = document.querySelector('input[name="duration_min"]')
      const date = document.querySelector('input[name="log_date"]')
      const btn = document.querySelector('form.form button[type="submit"]')
      return JSON.stringify({
        step: dur === null ? null : dur.getAttribute('step'),
        durValue: dur === null ? null : dur.value,
        stepMismatch: dur === null ? null : dur.validity.stepMismatch,
        validationMessage: dur === null ? null : dur.validationMessage,
        logDate: date === null ? null : date.value,
        checkValidity: form.checkValidity(),
        noValidate: form.noValidate,
        submitText: btn === null ? null : btn.textContent.trim(),
      })
    })()`

    /* ---------------- 期望侧：从 HTTP 现算，不写死 ---------------- */
    const myRows = []
    for (let offset = 0; offset < 2000; offset += 200) {
      const page = await req('GET', `/api/training-logs?limit=200&offset=${offset}`,
        { as: studentJar(STUDENT), quiet: true, record: false })
      const items = page.json?.items ?? []
      myRows.push(...items.filter((r) => r.student_id === STUDENT))
      if (items.length < 200) break
    }
    check(`§CI-0 反空转：泛型 list 翻页收到了学生 #${STUDENT} 的打卡行（≥ 1 行）`,
      myRows.length >= 1, `${myRows.length} 行`)

    /** 「不是 0.5 的整数倍」—— 即改前那个 `step="0.5"` **一定**会拦下的那一族。
     *  ⚠️ 用 `Math.round` 而不是 `%`：浮点上 `30.9 % 0.5` 是 `0.40000000000000213`，
     *  而 `23.0 % 0.5` 是 `0`，两者都「对」，但写成 `!== 0` 会把 `0.1 + 0.2` 那一类
     *  表示误差也算进去；这里要的是「离最近的 0.5 的整数倍有多远」。 */
    const offGrid = (v) => Math.abs(v * 2 - Math.round(v * 2)) > 1e-9
    const prefillRow = myRows
      .filter((r) => r.completed === true && r.duration_min !== null && offGrid(r.duration_min))
      .sort((a, b) => b.log_date.localeCompare(a.log_date))[0] ?? null
    check('§CI-0 反空转：库里**有**一行「completed 且 duration_min 不是 0.5 的整数倍」'
      + '（否则 §CI-1 证明不了 step 那一格 —— 那正是本缺陷的触发条件）',
      prefillRow !== null,
      prefillRow === null ? '一行都没有' : `${prefillRow.log_date} → ${prefillRow.duration_min}`)

    const taken = new Set(myRows.map((r) => r.log_date))
    /** 找一个库里**没有**行的日期（§CI-2 要一个 201，§FV-1 要一个干净表单）。 */
    function freeDateAfter(from) {
      const base = Date.parse(`${from}T00:00:00Z`)
      for (let i = 1; i <= 90; i += 1) {
        const next = new Date(base + i * 86_400_000).toISOString().slice(0, 10)
        if (!taken.has(next)) return next
      }
      return null
    }
    const freeDateA = prefillRow === null ? null : freeDateAfter(prefillRow.log_date)
    // ⚠️ **先把它记进 `taken` 再找第二个**（首跑实测到的红：两次都回 `2025-10-14`）。
    //    改前那一份给 `freeDateAfter` 加了一个 `skip` 实参，而 `skip` 只是把起点往后挪，
    //    `taken` 里仍然没有第一个日期 ⇒ 「往后数第 2 个」在第一个日期本身就不在 `taken`
    //    里时**还是它自己**。⚠️ 而它不只是难看：§CI-2 会在 §FV-1 那一天留下一行，
    //    于是 §FV-1 那张「干净表单」实际上带着一次预填（本拍碰巧仍然绿，
    //    而「碰巧」不是判据 —— 硬规矩 #92）。
    if (freeDateA !== null) taken.add(freeDateA)
    const freeDateB = prefillRow === null ? null : freeDateAfter(prefillRow.log_date)
    check('§CI-0 找得到两个库里还没有行的日期（§CI-2 要一个 201，§FV-1 要一个干净表单）',
      freeDateA !== null && freeDateB !== null && freeDateA !== freeDateB,
      `${freeDateA} / ${freeDateB}`)
    out(`    期望侧：预填用 ${prefillRow?.log_date}（duration_min=${prefillRow?.duration_min}）、`
      + `成功路径用 ${freeDateA}、反静默用 ${freeDateB}`)

    /* ============================== §CI-1 预填路径 ============================== */
    if (prefillRow !== null) {
      await navAs(studentJar(STUDENT), `/s/check-in?date=${prefillRow.log_date}`)
      await untilTrue(`!!document.querySelector('input[name="duration_min"]')`, 45000, '打卡表单渲染出来')
      await sleep(1500)
      const s1 = JSON.parse(String(await evaluate(FORM_PROBE) ?? 'null'))
      eq('§CI-1 那一格被**预填**成了库里那一行的真值（这就是触发条件，不是本拍造的）',
        s1?.durValue, String(prefillRow.duration_min))
      eq('§CI-1 而它**不** stepMismatch（改前 `step="0.5"` + 一位小数 ⇒ true）',
        s1?.stepMismatch, false)
      eq('§CI-1 故整张表单是合法的（改前实测 `form.checkValidity() === false`）',
        s1?.checkValidity, true)
      eq('§CI-1 反空转：这张表单**没有**关掉原生校验（`novalidate` 会让本组拍变成空转）',
        s1?.noValidate, false)

      const writesBefore = WRITES.length
      const rect1 = await realClick('form.form button[type="submit"]')
      check('§CI-1 真鼠标点在了「提交打卡」那一个按钮上（反空转：那一点上就是它、且它没被禁用）',
        rect1 !== null && rect1.hitTag === 'BUTTON' && rect1.hitInside === true
          && String(rect1.text).includes('提交') && rect1.disabled === false,
        JSON.stringify(rect1))
      await untilWrites(writesBefore)
      await sleep(1500)
      const posted = WRITES.slice(writesBefore).filter((w) => w.path === '/api/training-logs')
      check('§CI-1 点「提交打卡」之后 `POST /api/training-logs` **真的发出去了**'
        + '（改前实测 0 次：原生校验拦在 submit 之前，页面不报错、不打日志、不发请求）',
        posted.length === 1, `${posted.length} 次；这一屏一共 ${WRITES.length - writesBefore} 个 POST`)
      if (posted.length === 1) {
        eq('§CI-1 而它的状态码是 409（那一天库里已经有一行了 —— 一天一行是这张表的口径）',
          posted[0].status, 409)
        let sent = null
        try { sent = JSON.parse(posted[0].body) } catch { /* 下面那一拍会说 */ }
        check('§CI-1 请求体是那 5 个键（`log_date / completed / duration_min / feeling / is_rest_day`）'
          + '，一个都不多（`student_id` / `submitted_at` / `late` / `source` / `batch_id` 一律服务端填）',
          sent !== null && Object.keys(sent).length === 5
            && ['log_date', 'completed', 'duration_min', 'feeling', 'is_rest_day']
              .every((k) => Object.prototype.hasOwnProperty.call(sent, k)),
          JSON.stringify(sent))
        eq('§CI-1 而请求体里的 `duration_min` 就是**预填的那个一位小数**（没被前端改写过）',
          sent?.duration_min, prefillRow.duration_min)
        eq('§CI-1 响应体是后端那个统一错误形状（`error.code = integrity_conflict`）',
          (await bodyOf(posted[0]))?.error?.code, 'integrity_conflict')
      }
      const plain1 = await plainOf()
      check('§CI-1 页面上出现了**可见**的反馈（那一句 409 的人话，`.s-notice` 里）',
        plain1.includes('你已经打过卡了') && plain1.includes('integrity_conflict'),
        plain1.includes('你已经打过卡了') ? '有' : '没有')
    }

    /* ============================== §CI-2 成功路径 ============================== */
    if (freeDateA !== null) {
      await navAs(studentJar(STUDENT), `/s/check-in?date=${freeDateA}`)
      await untilTrue(`!!document.querySelector('input[name="duration_min"]')`, 45000, '打卡表单渲染出来')
      await sleep(1200)
      // ⚠️ **真键盘**输入（`Input.insertText`）而不是 `el.value = …`：本拍要走的正是
      //    `vModelText` 那条运行时路径 —— 它对 `type="number"` 会把值转成 number，
      //    而改前 `submit()` 里那句 `.trim()` 就是在那里炸的（上面文件头第三格）。
      await evaluate(`document.querySelector('input[name="duration_min"]').focus()`)
      await cdp.send('Input.insertText', { text: '30.9' }, sessionId)
      await sleep(500)
      const s2 = JSON.parse(String(await evaluate(FORM_PROBE) ?? 'null'))
      eq('§CI-2 真键盘输进去的是一位小数 30.9', s2?.durValue, '30.9')
      eq('§CI-2 而它**不** stepMismatch（改前 `step="0.5"` 会拦下 30.9）', s2?.stepMismatch, false)
      eq('§CI-2 故整张表单是合法的', s2?.checkValidity, true)

      const writesBefore = WRITES.length
      await realClick('form.form button[type="submit"]')
      // ⚠️ `SuccessMark` 只停留 `--dur-check-hold`（`tokens.css`，实测 1600 ms）就自己收起，
      //    故「可见的成功反馈」这一拍**必须轮询**，不能等 POST 落地之后再看。
      let sawMark = false
      const markT0 = Date.now()
      while (Date.now() - markT0 < 12000) {
        if ((await plainOf()).includes('已打卡')) { sawMark = true; break }
        await sleep(120)
      }
      await untilWrites(writesBefore)
      await sleep(800)
      const posted = WRITES.slice(writesBefore).filter((w) => w.path === '/api/training-logs')
      check('§CI-2 点「提交打卡」之后 `POST /api/training-logs` **真的发出去了**',
        posted.length === 1, `${posted.length} 次`)
      if (posted.length === 1) {
        eq('§CI-2 而它的状态码是 **201**（这一天库里没有行）', posted[0].status, 201)
        let sent = null
        try { sent = JSON.parse(posted[0].body) } catch { /* 下面那一拍会说 */ }
        eq('§CI-2 请求体里 `duration_min` 就是手输的那个 30.9（一位小数原样上去）',
          sent?.duration_min, 30.9)
        eq('§CI-2 而 `log_date` 就是 URL 上那一个库里还没有行的日期', sent?.log_date, freeDateA)
        const created = await bodyOf(posted[0])
        check('§CI-2 响应体形状对：`source = checkin`、`batch_id = null`、有 `id` 与 `submitted_at`'
          + '（那几格一律服务端填，前端传不了）',
          created?.source === 'checkin' && created?.batch_id === null
            && typeof created?.id === 'number' && typeof created?.submitted_at === 'string',
          JSON.stringify(created)?.slice(0, 220))
        eq('§CI-2 而响应体里的 `duration_min` 就是 30.9（后端收下一位小数：它的口径里'
          + '只有 `ge=0`，**没有** `multipleOf`）', created?.duration_min, 30.9)
      }
      check('§CI-2 页面上出现了**可见的成功反馈**（`SuccessMark` 的「已打卡」）',
        sawMark, sawMark ? '看见了' : '12 s 内一次都没看见')
      /* ⚠️⚠️ **轮询**、不再是「一次定值 `sleep(800)` + 一次快照」（Plan 07 Task 8 ·
         **公网档首跑真抓到的**判据缺陷；上面那个 `sleep(800)` 保留 —— 它护的是
         `posted` / `bodyOf` 那几拍要读到完整响应体，⚠️ 而它**不再**充当本拍的判据）。
         为什么定值不够：`views/student/CheckIn.vue` 的 `submit()` 在 POST 成功之后
         **还要 `await reload()`** 才走到 `finally`（`submitting.value = false` 排在
         reload **之后**）⇒「按钮多久恢复」等于「一次读请求的往返」。本机实测：
         同源/局域网那三档 < 800 ms（故改前那个定值一直够、这一格从没露过），
         而**公网档**经 Cloudflare 边缘一趟就超了 ⇒ 首跑 777 绿 / **1 红**，红的就是
         这一拍，⚠️ 而同组的「POST 发出去了 / 201 / 请求体 / 响应体 / `SuccessMark`
         的『已打卡』」五拍**全绿**（⇒ 写路径是好的，卡的只是按钮那一格）。
         ⚠️ **改成轮询不是放宽判据**（硬规矩 #92）：本拍要区分的是「**永久**卡住」
         （改前那个 `TypeError` 抛在 `try` 之前 ⇒ `finally` 不跑 ⇒ 永久 disabled、
         只能刷新页面）与「一会儿就好」。15 s 上限照样抓住「永久」那一档；
         而 800 ms 那个**定值**抓住的是「比一次读请求的往返快」—— 那不是本缺陷的判据，
         是一格**随链路时延漂**的东西（于是它在四档里三档绿、一档红）。
         ⚠️ detail 里印的是**实测毫秒数**，它同时是本格诊断的取证：> 0 就证明
         总等待 > 800 ms ⇒「定值不够」而不是「按钮真的坏了」。
         ⚠️ 而「`submitting` 一直握着 `reload()`」本身是一格**产品面**的耦合（写已经
         成功了，按钮却因为一次无关的读而仍 disabled）⇒ 登记在 spec §15 **G6**，
         本波**不动**它（动它要重建 `dist`，而甲方此刻正在用那条公网链接）。 */
      let submitCleared = false
      let clearedMs = -1
      let lastSubmitText = ''
      const clearT0 = Date.now()
      while (Date.now() - clearT0 < 15000) {
        const s2b = JSON.parse(String(await evaluate(FORM_PROBE) ?? 'null'))
        lastSubmitText = String(s2b?.submitText ?? '')
        if (!lastSubmitText.includes('正在提交')) {
          submitCleared = true
          clearedMs = Date.now() - clearT0
          break
        }
        await sleep(150)
      }
      check('§CI-2 而提交按钮**没有**卡在「正在提交…」（改前那一格 `TypeError` 之后 `finally` 不跑，'
        + '按钮**永久** disabled ⇒ 用户只能刷新页面；⚠️ 判据是**轮询**、上限 15 s，'
        + '理由与「为什么改前那个定值 800 ms 在公网档不够」逐字见上面那段）',
      submitCleared,
      submitCleared
        ? '定值 800 ms 之后又等了 ' + String(clearedMs) + ' ms 才恢复（⇒ 总 ≥ '
          + String(800 + clearedMs) + ' ms；⚠️ 这一段里含一次 `reload()` 的往返）'
        : '15 s 内一次都没恢复（最后一次读到 ' + lastSubmitText + '）')
    }

    /* ============================== §FV-1 反静默（打卡页）============================== */
    if (freeDateB !== null) {
      await navAs(studentJar(STUDENT), `/s/check-in?date=${freeDateB}`)
      await untilTrue(`!!document.querySelector('input[name="log_date"]')`, 45000, '打卡表单渲染出来')
      await sleep(1200)
      // ⚠️ 造一个**必然**校验失败的输入：把必填的 `log_date` 清空。
      //    用「写 value + 派发 input 事件」而不是真键盘 —— `type="date"` 的清空在键盘上
      //    是一串分段退格、跨浏览器形状不一；而本拍要钉的是**校验失败之后用户看不看得见**，
      //    不是「怎么把它弄空的」。
      await evaluate(`(() => { const el = document.querySelector('input[name="log_date"]')
        el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); return el.value })()`)
      await sleep(500)
      const s3 = JSON.parse(String(await evaluate(FORM_PROBE) ?? 'null'))
      eq('§FV-1 前提：`log_date` 已经被清空（它是 `required` ⇒ valueMissing）', s3?.logDate, '')
      eq('§FV-1 前提：于是整张表单**不**合法（否则本拍什么也证明不了）', s3?.checkValidity, false)

      const writesBefore = WRITES.length
      await realClick('form.form button[type="submit"]')
      await sleep(2000)
      eq('§FV-1 校验失败 ⇒ **一个 POST 都没发出去**（「不发请求」那一半的判据）',
        WRITES.length - writesBefore, 0)
      const plain3 = await plainOf()
      const alertCount = Number(await evaluate(`document.querySelectorAll('[role="alert"]').length`) ?? 0)
      check('§FV-1 而用户**看得见**一句人话（改前实测：页面上一个字都没多）',
        plain3.includes('表单没有提交出去'), plain3.includes('表单没有提交出去') ? '看得见' : '看不见')
      check('§FV-1 那一句点名了**哪个字段**（用它自己的 label 文本，不是 name 属性）',
        plain3.includes('训练日 log_date'), plain3.includes('训练日 log_date') ? '点名了' : '没点名')
      check('§FV-1 那一句给了**为什么**（读浏览器自己的 `validationMessage`，不重算第二份）',
        plain3.includes('浏览器给的理由'), plain3.includes('浏览器给的理由') ? '给了' : '没给')
      check('§FV-1 那一句给了**该怎么改**', plain3.includes('这一格是必填的'),
        plain3.includes('这一格是必填的') ? '给了' : '没给')
      check('§FV-1 而那一句**明说「没有发出任何请求」**（本缺陷最贵的一格：不说它，用户会'
        + '以为卡交上去了，而打卡完成率是 spec §8.1 点名的 RCT 关键过程指标）',
        plain3.includes('发出任何请求'), plain3.includes('发出任何请求') ? '明说了' : '没说')
      check('§FV-1 它挂在一个 `role="alert"` 上（读屏也会念，不只是画出来）',
        alertCount > 0, `${alertCount} 个`)
    }

    /* ============== §FV-2 反静默（登录页 ⇒ 那个处置是**共用**的）============== */
    {
      await navAs(null, '/login', 1440, 1600)
      await untilTrue(`!!document.querySelector('.auth__form button[type="submit"]')`, 45000, '登录页渲染出来')
      await sleep(800)
      const writesBefore = WRITES.length
      const rect = await realClick('.auth__form button[type="submit"]')
      check('§FV-2 真鼠标点在了「登录」那一个按钮上（反空转）',
        rect !== null && rect.hitTag === 'BUTTON' && rect.hitInside === true,
        JSON.stringify(rect))
      await sleep(1500)
      eq('§FV-2 两个 `required` 都空着 ⇒ `POST /api/auth/login` **一个都没发出去**'
        + '（⚠️ 于是本拍也**不消耗**任何一次登录失败计数：`login_attempt` 一行都不写）',
        WRITES.slice(writesBefore).filter((w) => w.path === '/api/auth/login').length, 0)
      const plain = await plainOf()
      check('§FV-2 而登录页上也**看得见同一族那句人话** ⇒ 那个处置是**共用**的'
        + '（住址是 `composables/useFormValidity.ts`），不是打卡页自己写的一份',
        plain.includes('表单没有提交出去'), plain.includes('表单没有提交出去') ? '看得见' : '看不见')
      // ⚠️ needle 取**整句**而不是裸的「学号」：登录页的字段标签本来就写着「学号」，
      //    一个裸 needle 会被那一处满足（终审 S3-⑦ 查出过的同族假绿）。
      // ⚠️⚠️ 而它取的是「**第一格是**「学号」」那一档的形状，不是「「学号」这一格」：
      //    本页**两个** `required` 都空着（学号 + 口令），故浏览器对两格各触发一次
      //    `invalid`，`useFormValidity` 报的是**总数 + 第一格**（首跑实测到的红：
      //    按「只有一格不合格」那一档的措辞去断言，needle 一个字都不匹配）。
      //    ⚠️ 那一档本身就是本拍要证的事：两格都不合格时用户也得看得见，
      //    而且看得见的是「一共几格 + 先改哪一格」。
      check('§FV-2 而它点名的是**登录页自己的**那一格（⇒ 不是一句写死的通用话）',
        plain.includes('第一格是「学号」'),
        plain.includes('第一格是「学号」') ? '点名了「学号」' : '没点名')
      check('§FV-2 而它同时报出了**一共几格不合格**（本页两格都空着 ⇒ 那一档的措辞是'
        + '「N 格没通过…」而不是「「X」这一格…」；少了总数，用户改完一格还会再撞一次）',
        plain.includes('2 格没通过浏览器自带的校验'),
        plain.includes('2 格没通过浏览器自带的校验') ? '报了 2 格' : '没报')
    }

    // ⚠️ 把视口交还给下面 §I5 / §C3（它们量的是 1440 那一档的桌面页）。
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: 1440, height: 2400, deviceScaleFactor: 1, mobile: false }, sessionId)
  }

  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 07 Task 5b 缺陷 ②**：`/t/students/:id` 第 06 块有一句**随 id 变假**的散文。

     改前的运行时取证（教师 T0001，真浏览器，两个 case 各抓一次 DOM）：
       · case A（学生 1，T0001 **任教**他，教师侧变体 200）：第 06 块那个 `<pre>` 的末行是
         「（请求头一律是 X-Teacher-Staff-No: T0001；学生 1 **确实**由该教师本学期任教）」→ 真；
       · case B（学生 4，T0001 **不任教**他，教师侧变体 403）：同一行逐字变成
         「…学生 4 **确实**由该教师本学期任教」→ **假**，而**同一屏**上第 02 块与第 05 块
         正各挂着一块 `forbidden · 403`「当前身份不是本学期任教他的老师」。
     ⚠️ 而它还教用户用 `X-Teacher-Staff-No` 那个请求头 —— 那条通道要「开发档构建」
       **且**「后端显式设 `PE_ALLOW_HEADER_IDENTITY=1`」两个条件同时成立，而交付的脚本
       一律强制清掉它、`prod` 档下 `allow_header_identity()` 结构上恒 False。
     ⚠️ 本波顺带实测出**同一块里另外三句假话**（都是 Plan 05A 换掉身份载体之后过期的）：
       ① 抬头「教师头调学生侧端点仍然是 401」+「Task 3 的实测原文，收尾波之后逐字仍成立」；
       ② 那个 `<pre>` 里五行「-> 401 unauthenticated」—— 教师**会话**打那五条实测是
          **403 forbidden**，401 只属于「完全没有会话」那一档；
       ③ 「`client.ts` 一次只注入一个身份头」—— 生产构建里 `identityHeaders()` 恒回空对象。

     下面这几拍钉的是「那一句断言**随真实状态变**」，而**判据只有一个所有者**：
     期望侧是 HTTP（教师侧变体 `/home` 的 200 / 403），被测侧是渲染出来的 DOM 文本，
     而页面那一句读的是**同一个** 403/200 的结果（`StudentDetail.vue` 的 `teachesHere`），
     不自己再判一次任教关系。⚠️ 两句 needle **互斥**，故「写死一句」当场红。
     ------------------------------------------------------------------ */
  {
    const NEEDLE_TAUGHT = '后端确认「本学期任教他」'
    const NEEDLE_NOT_TAUGHT = '后端说「不在他本学期任教的任何教学班里」'
    const STALE = '确实由该教师本学期任教'

    async function evaluate2(expression) {
      const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true }, sessionId)
      return r?.result?.value
    }

    async function navTeacher(id) {
      await cdp.send('Network.clearBrowserCookies', {}, sessionId)
      const raw = JARS.get('teacher') ?? (await ensureJar('teacher'))
      const set = await cdp.send('Network.setCookie', {
        name: 'pe_session', value: raw.slice('pe_session='.length),
        url: WEB, httpOnly: true, sameSite: 'Lax',
      }, sessionId)
      if (set?.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(set)}`)
      await cdp.send('Emulation.setDeviceMetricsOverride',
        { width: 1440, height: 3000, deviceScaleFactor: 1, mobile: false }, sessionId)
      await cdp.send('Page.navigate', { url: `${WEB}/t/students/${id}` }, sessionId)
    }

    /** 导航 + 轮询到第 06 块那一句落定，返回 `toPlainText` 之后的正文。
     *  ⚠️ 退出条件里**两句 needle 都要试**：本拍要证的正是「哪一句出现取决于 id」，
     *  故不能只等其中一句（那会让另一档变成一次 45 s 的超时）。 */
    async function grabDetail(id) {
      await navTeacher(id)
      const t0 = Date.now()
      let plain = ''
      for (;;) {
        plain = toPlainText(String(await evaluate2('document.documentElement.outerHTML') ?? ''))
        if (plain.includes('STUDENT ONLY')
          && (plain.includes(NEEDLE_TAUGHT) || plain.includes(NEEDLE_NOT_TAUGHT))) break
        if (Date.now() - t0 > 45000) break
        await sleep(300)
      }
      out(`    /t/students/${id} → 抓到 ${plain.length} 字符（${Date.now() - t0} ms）`)
      return plain
    }

    check('§TD-0 反空转：两个 case 的 id **不是同一个**（否则「两句 needle 互斥」无从谈起）',
      taught?.id !== STUDENT, `任教=#${taught?.id} 不任教=#${STUDENT}`)

    // ---- 期望侧：HTTP，两档各一次（与被测侧不同源）----
    const homeTaught = await req('GET', `/api/teacher/students/${taught?.id}/home?as_of=${AS_OF}`,
      { as: 'teacher', quiet: true, record: false })
    const homeNot = await req('GET', `/api/teacher/students/${STUDENT}/home?as_of=${AS_OF}`,
      { as: 'teacher', quiet: true, record: false })
    eq(`§TD-0 期望侧 ①：教师侧变体对 #${taught?.id}（他任教的）回 200`, homeTaught.status, 200)
    eq(`§TD-0 期望侧 ②：而对 #${STUDENT}（他不任教的）回 403`, homeNot.status, 403)
    eq('§TD-0 而那个 403 的 code 是 forbidden（页面那一句读的就是这一格，本页不自己再判一次）',
      codeOf(homeNot), 'forbidden')

    const plainTaught = await grabDetail(taught?.id)
    const plainNot = await grabDetail(STUDENT)

    check(`§TD-1 任教那一屏（#${taught?.id}）说的是「${NEEDLE_TAUGHT}」`,
      plainTaught.includes(NEEDLE_TAUGHT), plainTaught.includes(NEEDLE_TAUGHT) ? '是' : '不是')
    check(`§TD-2 不任教那一屏（#${STUDENT}）说的是「${NEEDLE_NOT_TAUGHT}」`,
      plainNot.includes(NEEDLE_NOT_TAUGHT), plainNot.includes(NEEDLE_NOT_TAUGHT) ? '是' : '不是')
    check('§TD-3 两句**互斥** ①：任教那一屏里找不到「不任教」那一句',
      !plainTaught.includes(NEEDLE_NOT_TAUGHT),
      plainTaught.includes(NEEDLE_NOT_TAUGHT) ? '找到了（⇒ 两句不互斥）' : '找不到')
    check('§TD-4 两句**互斥** ②：不任教那一屏里找不到「任教」那一句'
      + '（⚠️ 与上一拍合起来才是「写死一句就会红」的判据）',
      !plainNot.includes(NEEDLE_TAUGHT),
      plainNot.includes(NEEDLE_TAUGHT) ? '找到了（⇒ 写死了一句）' : '找不到')
    check(`§TD-5 改前那句写死的断言（「${STALE}」）在两屏上都**一个字节都不剩**`,
      !plainTaught.includes(STALE) && !plainNot.includes(STALE),
      `任教屏=${plainTaught.includes(STALE)} 不任教屏=${plainNot.includes(STALE)}`)
    check('§TD-6 而不任教那一屏上，第 02/05 块那两块 403 的真话**照旧在**'
      + '（本波修的是那句假话，不是把真话一起删掉）',
      plainNot.includes('不是本学期任教他的老师'),
      plainNot.includes('不是本学期任教他的老师') ? '在' : '不在')
    check('§TD-7 请求头通道那一段**没有被删掉**（本仓的页面散文是可解释性资产），'
      + '而它现在说的是真话：点名了那个环境变量、点名了那个函数、并说清在甲方手上不可能生效',
      plainNot.includes('PE_ALLOW_HEADER_IDENTITY') && plainNot.includes('不可能生效')
        && plainNot.includes('allow_header_identity'),
      `PE_ALLOW_HEADER_IDENTITY=${plainNot.includes('PE_ALLOW_HEADER_IDENTITY')} `
      + `不可能生效=${plainNot.includes('不可能生效')} `
      + `allow_header_identity=${plainNot.includes('allow_header_identity')}`)
    /* ⚠️⚠️ needle 里**一个 `>` 都不能有**（首跑实测到的红，而那一格是本仓的一个潜伏陷阱，
       已登记为待清扫）：被测侧是 `document.documentElement.outerHTML`，而 DOM 的序列化
       规范会把文本节点里的 `>` 转义成 `&gt;`（`<` → `&lt;`、`&` → `&amp;`、U+00A0 →
       `&nbsp;` 同理）。`toPlainText` 只剥标签与压空白，**不反转义实体**，
       于是页面正文里那句 `教师会话 -> 403 forbidden` 在 `plainNot` 里逐字是
       `教师会话 -&gt; 403 forbidden` —— needle 永远匹配不上，而失效方向是**红**
       （不是假绿，故它不危险，只是会把下一个人支去改页面散文）。
       ⚠️ 本波**刻意不改** `toPlainText`（它是终审 I4 的单一所有者，而第 17 步 ② 那五拍
       钉着它对已知反例的判定；在一个缺陷修复波里改它属于超范围，且「加一次实体反转义」
       会不会把某一条既有 needle 从绿变红要另做一遍全量取证）。处置：needle 绕开
       `<` / `>` / `&`，并把这一格如实记进报告与待清扫。 */
    check('§TD-8 而那一块**不再**声称「教师头调学生侧端点仍然是 401」（本波实测：教师**会话**'
      + '打那五条是 403 forbidden，401 只属于没有会话那一档）',
      !plainNot.includes('教师头调学生侧端点仍然是 401')
        && plainNot.includes('教师会话是 403，没有会话才是 401'),
      `旧抬头还在=${plainNot.includes('教师头调学生侧端点仍然是 401')} `
      + `新抬头在=${plainNot.includes('教师会话是 403，没有会话才是 401')}`)
    check('§TD-8′ 而那个 `<pre>` 里**每一行**都给了两档实测（教师会话 / 没有会话），'
      + '不是只留一句结论（⚠️ needle 数的是 `403 forbidden` 的出现次数 ≥ 5，'
      + '即五条路径逐条都在；⚠️ 刻意不用带 `>` 的串，理由见上面那一段）',
      plainNot.split('403 forbidden').length - 1 >= 5,
      `${plainNot.split('403 forbidden').length - 1} 次`)
  }

  /* ------------------------------------------------------------------
     终审 I5 的守卫：**DEV 深链接导航时，第一个 /api 请求不得带未验证的身份头**。

     ⚠️ 改前实测到的形状（登录成 #4、URL 上写 `?student=1`）：
       +494ms  GET /api/auth/me                  身份头 X-Student-Id: 1   ← URL 认出来的假身份
       +521ms  GET /api/students/4/home          身份头 X-Student-Id: 4   ← session.adopt() 已跑
     根因是 `main.ts` 在**会话还没问过**之前就把 URL 上那个身份写进了 `client.ts`
     会读的那个 store；本波把它挪到了 `session.ensureRestored()` 之后（逐字理由见
     `main.ts` 的 ③）。⚠️ 今天它无害只是**巧合**（`/api/auth/me` 依赖 `current_session`、
     刻意不回落请求头，而演示/生产后端整个忽略那两个头），而**没有任何断言**钉住它。
     ⚠️ 谓词只认**后端** API：dev 下 vite 也会请求 `/src/api/client.ts` 这类模块 URL，
     一个 `includes('/api/')` 的谓词会把它们算进来、于是「第一个请求」永远是模块请求
     （实现者首跑实测到的假绿，故这里用 `startsWith('/api/')`）。 */
  {
    const seen = []
    let collecting = true
    cdp.on('Network.requestWillBeSent', (p) => {
      if (!collecting) return
      const short = String(p.request?.url ?? '').replace(/^https?:\/\/[^/]+/, '')
      if (!short.startsWith('/api/')) return
      const h = p.request?.headers ?? {}
      seen.push({
        url: short,
        student: h['X-Student-Id'] ?? h['x-student-id'] ?? null,
        teacher: h['X-Teacher-Staff-No'] ?? h['x-teacher-staff-no'] ?? null,
      })
    })
    const other = allStudents.find((s) => s.id !== STUDENT)
    check('§I5 反例前提：URL 上要认的那个学生与会话里那个**不是同一个人**（否则这一拍什么也证明不了）',
      other !== undefined && other.id !== STUDENT, `会话=#${STUDENT} URL=#${other?.id}`)
    // ⚠️ **先把 localStorage 清干净**（首跑实测到的假红）：上面 16 条路由的取证已经
    //    用管理员 jar 打开过 `/admin`，而 `session.adopt()` 的「session → identity」
    //    兼容桥会把 `T0003` 写进**持久化**的 `stores/identity` → 本拍导航时
    //    `/api/auth/me` 会带上 `X-Teacher-Staff-No: T0003`。那**不是**本拍要抓的东西
    //    （它是上一份会话遗留的、曾经被后端验证过的身份，属于 05B 待清扫第 14 条
    //    「拆那座桥」的面，不是本波的活）；本拍要抓的是**URL 认出来的**那一个。
    //    故按终审的复现姿势来：一个干净的 profile（空 localStorage）+ 一份学生 cookie。
    await cdp.send('Runtime.evaluate', { expression: 'localStorage.clear()', returnByValue: true }, sessionId)
    const lsLen = await cdp.send('Runtime.evaluate',
      { expression: 'localStorage.length', returnByValue: true }, sessionId)
    eq('§I5 localStorage 已清空（否则这一拍会被上一份会话的持久化身份污染）',
      Number(lsLen?.result?.value ?? -1), 0)
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    const rawCookie = JARS.get(studentJar(STUDENT)) ?? (await ensureJar(studentJar(STUDENT)))
    const cookieSet = await cdp.send('Network.setCookie', {
      name: 'pe_session', value: rawCookie.slice('pe_session='.length),
      url: WEB, httpOnly: true, sameSite: 'Lax',
    }, sessionId)
    check('§I5 会话 cookie 种进浏览器了', cookieSet?.success === true, JSON.stringify(cookieSet))
    const deepLink = `${WEB}/s/home?student=${other.id}&as_of=${AS_OF}`
    out(`    导航到 ${deepLink}`)
    await cdp.send('Page.navigate', { url: deepLink }, sessionId)
    await sleep(6000)
    collecting = false
    for (const [i, r] of seen.slice(0, 5).entries()) {
      const heads = r.student !== null ? `X-Student-Id: ${r.student}`
        : (r.teacher !== null ? `X-Teacher-Staff-No: ${r.teacher}` : '（无身份头）')
      out(`    +${i} ${r.url}   ${heads}`)
    }
    check('§I5 抓到了后端请求（守卫不空转）', seen.length >= 1, `${seen.length} 个`)
    eq('§I5 第一个后端请求就是 GET /api/auth/me（会话恢复那一次）',
      seen[0]?.url?.split('?')[0], '/api/auth/me')
    check('§I5 而那第一个请求**不带任何身份头** —— URL 上那个未验证的身份不得先于会话进 store',
      seen.length > 0 && seen[0].student === null && seen[0].teacher === null,
      JSON.stringify(seen[0] ?? null))
    // ⚠️ 如实记（硬规矩 #39）：挪了顺序之后 URL 那一格**赢了** session→identity 那座桥，
    //    故第二个请求会去打 `/api/students/{URL 上那个 id}/home` 并被后端按**会话**判成 403。
    //    那是有意的（响亮的 403 好过静默忽略 URL），逐字理由见 main.ts 的 ③。
    out(`    ⚠️ 后续请求（会 403，这是有意的：URL 身份 ≠ 会话身份，后端按会话判）：`
      + `${seen.slice(1, 4).map((r) => r.url).join(' , ')}`)
  }

  /* §C3（Plan 06 Task 12 / 老终审 M7）：**会话恢复的那一帧不许说「未登录」/ 画 ANONYMOUS**。
     ⚠️ 改前实测的形状（读代码 + 本拍真取证）分两半：
       · 「已登录的用户被弹去 /login 再弹回来」那一半 **结构上不可达** ——
         `router.beforeEach` 在任何判定之前 `await session.ensureRestored()`，
         而 `status` 的初值是 `'unknown'` 不是 `'anon'`（`stores/session.ts` 文件头末节）。
         ⚠️ 那一格由第 17 步 ⑧ 的源码面断言钉住（否则下一个人把 `await` 挪走是静默的）。
       · 「闪一帧 ANONYMOUS / 未登录」那一半 **在产品档上真的会被看见**：
         `main.ts` 的产品那一支是**同步** `mount()`（DEV 那一支才 `await ensureRestored()`
         之后再挂载），故 App.vue 的报头/会话条/页脚会先渲染一帧，
         而那时 `kind` 还是 `null` ⇒ `roleLabel` 画 `ANONYMOUS`、`session.summary` 说「未登录」。
         ⚠️ 两句都是**假话**（cookie 还在、`me` 只是还没回来）。
     ⚠️ 修法不是 `v-if` 白屏（那也是一帧坏体验），而是给这两格一个 **pending 档**
       （判据的唯一住址是 store 的 `isPending`），措辞与本仓既有的 pending 口径同族
       （`读取中…` / `加载中…` / `登出中…`），故**不引入任何新的 CSS 裸值**。
     ⚠️⚠️ 取样手法是承重的：把 **`/api/auth/me` 这一个请求**用 `Fetch` 域扣住，
       而**不是**把整个网络拖慢 —— 后者会连 JS 产物一起拖住，于是取样到的那一帧
       是「什么都还没挂载」的白屏，证明不了任何事（那一拍由下面的「已经挂载」断言挡）。 */
  {
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    const raw = JARS.get('admin') ?? (await ensureJar('admin'))
    const set = await cdp.send('Network.setCookie', {
      name: 'pe_session', value: raw.slice('pe_session='.length), url: WEB,
      httpOnly: true, sameSite: 'Lax',
    }, sessionId)
    if (set?.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(set)}`)
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: 1440, height: 2400, deviceScaleFactor: 1, mobile: false }, sessionId)

    const paused = []
    cdp.on('Fetch.requestPaused', (p) => { paused.push(p) })
    await cdp.send('Fetch.enable',
      { patterns: [{ urlPattern: '*/api/auth/me*', requestStage: 'Request' }] }, sessionId)
    const grab = async () => {
      const res = await cdp.send('Runtime.evaluate',
        { expression: 'document.documentElement.outerHTML', returnByValue: true }, sessionId)
      return toPlainText(String(res?.result?.value ?? ''))
    }

    await cdp.send('Page.navigate', { url: WEB + '/admin/audit-logs' }, sessionId)
    const heldFrom = Date.now()
    while (paused.length === 0 && Date.now() - heldFrom < 30000) await sleep(100)
    check('§C3 前提：/api/auth/me 真的被扣住了（否则下面那一帧什么也证明不了）',
      paused.length >= 1, `${paused.length} 个`)
    await sleep(1500)
    const pending = await grab()
    /* ⚠️⚠️ **两档的形状不同，而这是实测出来的**（本机亲跑）：
       · **产品档**：`main.ts` 的 `else` 那一支是**同步** `mount()`，故 `me` 被扣住时
         应用**已经挂载**、而 `kind` 还是 `null` ⇒ 改前那一帧真的画 `ANONYMOUS`
         并说「未登录」。那一档要断言的是「它现在说 pending」。
       · **dev 档**：`main.ts` 的 `if (import.meta.env.DEV)` 那一支
         **先 `await ensureRestored()` 再 `mount()`**，故 `me` 被扣住时应用
         **根本还没挂载**（DOM 就是 `index.html` 那个占位）⇒ M7 那一帧在 dev 档
         **结构上不可达**。⚠️ 那一格是**好消息**、要照实钉住：它说明「产品档上
         看得见的那一帧」不是 HttpOnly cookie 的固有代价，而只是「产品档选择了
         不阻塞首屏」的代价 —— 而修法是给那一帧一个 pending 档，不是去阻塞首屏。
       ⚠️ 判档**复用**第 14 步上面那一批路由已经算出来的 `TIERS_SEEN`（而那一格
       由 `§Tier` 那一条断言钉住「16 条路由的判定一致」）。⚠️ 刻意**不**对
       这一帧的 DOM 再判一次：`me` 被扣住时（dev 档）DOM 还停在 `index.html`
       的占位上，而 `buildTierOf` 认的两个标记一个在注入的脚本里、一个在构建产物里
       ⇒ 那一帧判出来是 `unknown`（本机实测踩过）。档是**服务**的属性、
       不是某一帧 DOM 的属性，故读上面那一份。 */
    const tier = TIERS_SEEN[0] ?? 'unknown'
    check('§C3 认得出构建档（复用上面 16 条路由那一份判定，而不是对这一帧再判一次）',
      tier === 'dev' || tier === 'prod', `${tier} / TIERS_SEEN=${JSON.stringify(TIERS_SEEN)}`)
    check('§C3 ① me 未落定的那一帧里**没有** ANONYMOUS（改前 roleLabel 在这一帧就是它）',
      !pending.includes('ANONYMOUS'), '')
    check('§C3 ② 那一帧里也**没有**「未登录」（改前页脚与会话条在这一帧都说它）',
      !pending.includes('未登录'), '')
    if (tier === 'dev') {
      check('§C3(dev) ③ 取证：`me` 被扣住时应用**还没挂载**（DEV 那一支先 await 再 mount，'
        + '故 M7 那一帧在 dev 档结构上不可达 —— DOM 是 index.html 的占位、不是 ANONYMOUS）',
      !pending.includes('当前身份') && !pending.includes('PENDING'), pending.slice(0, 120))
    } else {
      check('§C3(prod) ③ 取样不是白屏：那一帧**已经挂载**（会话条画出来了）',
        pending.includes('当前身份'), pending.slice(0, 200))
      check('§C3(prod) ④ 那一帧说的是 pending 那一档：roleLabel = PENDING…、'
        + 'summary = 身份未确认…、store 的 status = restoring（三格都在，'
        + '缺一格都说明判据没接上）',
        pending.includes('PENDING') && pending.includes('身份未确认')
          && pending.includes('会话状态 restoring'),
        `PENDING=${pending.includes('PENDING')} 身份未确认=${pending.includes('身份未确认')} `
        + `restoring=${pending.includes('会话状态 restoring')}`)
    }
    check('§C3 ⑤ 而那一帧**没有**被弹去 /login（守卫 await 了 me；两档都断，'
      + '因为「已登录的人被弹去登录页」这半格在两档都不可达）',
      !pending.includes('请先登录'), '')

    for (const p of paused) {
      await cdp.send('Fetch.continueRequest', { requestId: p.requestId }, sessionId)
    }
    await cdp.send('Fetch.disable', {}, sessionId)
    const settleFrom = Date.now()
    let settled = pending
    while (Date.now() - settleFrom < 45000) {
      settled = await grab()
      if (settled.includes('会话状态 authed')) break
      await sleep(250)
    }
    check('§C3 ⑥ 放行之后会话**落定**了（status = authed，pending 那一档不是常驻的）',
      settled.includes('会话状态 authed') && !settled.includes('身份未确认')
        && !settled.includes('PENDING'), `authed=${settled.includes('会话状态 authed')}`)
    check('§C3 ⑦ 落定之后 roleLabel 是 ADMIN、summary 是「管理员 <工号>」（真话照说）',
      settled.includes('ADMIN') && settled.includes(`管理员 ${ADMIN}`),
      `ADMIN=${settled.includes('ADMIN')} 管理员 ${ADMIN}=${settled.includes(`管理员 ${ADMIN}`)}`)

    /* ⚠️ **反空转（本组最要命的一拍）**：「问过了、答案是匿名」那一档**仍然**要说
       「未登录」/ 画 ANONYMOUS —— 那是真话。少了本拍，「把 pending 判据写成恒真」
       （于是全站永远显示「身份未确认…」）会让上面几拍全绿。 */
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    await cdp.send('Page.navigate', { url: WEB + '/login' }, sessionId)
    const anonFrom = Date.now()
    let anon = ''
    while (Date.now() - anonFrom < 45000) {
      anon = await grab()
      if (anon.includes('会话状态 anon')) break
      await sleep(250)
    }
    check('§C3 ⑧ 反空转：匿名那一档**照旧**说「未登录」/ 画 ANONYMOUS（真话必须照说）',
      anon.includes('会话状态 anon') && anon.includes('未登录') && anon.includes('ANONYMOUS'),
      `anon=${anon.includes('会话状态 anon')} 未登录=${anon.includes('未登录')} `
      + `ANONYMOUS=${anon.includes('ANONYMOUS')}`)
  }

  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 07 Task 10 · G8**：教师端登出之后那一块 401「loud」错误横幅
     **跨过登录**留在下一个身份的页面上（spec §13.21.7 的 G8；Task 9 判它 **S2**，
     因为它出现在说明书 §4 路线二第 7 步**逐字要甲方做**的那一串上）。

     改前的运行时取证（真浏览器 + 真鼠标 `Input.dispatchMouseEvent` + CDP，
     **产品档**，本波亲跑；两份日志在 task-10-report.md §2）：
       · 以 T0001 登录 → `/t/alerts` → 真鼠标点「登出」；
       · `POST /api/auth/logout → 204` 落在 **+4175 → +4212 ms**，而**紧接着**
         （+4212 / +4213，即吊销之后 0–1 ms）**发出 5 个 GET**：
             /api/alerts           401     /api/students        401
             /api/course-sections  200 ←   它是那 7 个匿名读之一
             /api/teachers         401     /api/enrollments     401
         ⇒ **恰好 4 条 401**，与 Task 9「三次登出三次都数到那 4 条」逐字对上；
       · ⚠️ 而它们**不是**「登出那一刻还在飞的旧请求」（spec G8 改前那一句是推断）：
         它们的**发出时刻在 204 之后**，是 `views/teacher/AlertQueue.vue` 那一句
         `watch([() => identity.teacherStaffNo, () => identity.asOf], () => void reload())`
         被 `stores/session.ts` 的 `forget()` → `clearIdentity()` 触发之后**新发的一批**。
         ⚠️ 反证也实测过：同一次登出在 `/t/dashboard` 上是 **0 发** ——
         `Dashboard.vue` 的 load 第一行有 `if (staffNo === null) return null` 那一格早退，
         而 `AlertQueue.vue` 没有；
       · 其中一条被 `composables/useAsync.ts` 的 catch `raise` 进 `ApiErrorBanner.vue`
         的**模块级单例**，而改前那个单例的清理入口**只有一个**（横幅自己那个「关闭 ✕」）
         ⇒ 它跨过 `/login`、跨过下一次登录，落在**学生**首页上。横幅原文（逐字）：
         `unauthenticated` / `401` / `GET /api/students?limit=200` /
         「会话失效了（pe_session cookie 缺失、已过期或已登出）。**前端会把你送去登录页**，
         登录之后回到刚才那一页。」—— ⚠️ 而那一句在那一刻是**假话**
         （用户已经以另一个身份登录了，且 `onLogout()` 的 `router.replace('/login')`
         **不带** `?next=`，故「回到刚才那一页」也不成立）。

     修法（⚠️ **单一所有者**，派单逐字要求「清它的地方应当是身份变化那一格，
     而不是每个页面各清一次」）：`stores/session.ts` 的 `adopt()` 与 `forget()`
     各调一次 `useApiError().dismiss()` —— 「后端认我是谁」在全前端只有这两个写入口。
     ⚠️ **它不是把横幅改静默**（Plan 06 终审要的那个「响亮」一格未动）：真正的会话
     过期仍然会挂出来，因为 `api/client.ts` 是**先** `fireSessionExpired`（⇒ `main.ts`
     调 `forget()` ⇒ dismiss）**后** `throw`（⇒ `useAsync` 的 catch 才 `raise`）。
     ⚠️ **定点变异**（本波实测）：把 `adopt()` 里那一行 `useApiError().dismiss()` 去掉
     → 下面 §G8-⑤ 那两拍当场红（§G8-②③ 仍然绿，即前提没变、只有判据变红）。

     这一组钉的八格：
       §G8-①②③ **前提 / 反空转**：教师真的从表单登进去了、登出那一刻**确实**产生了
                  401、而 401 **确实**把一块 `banner--loud` 挂上了（少了这两拍，
                  下面「横幅不在」可能只是因为**从来没在过** = 假绿）；
       §G8-④    前提：换身份（学生）登录成功、且学生首页真的渲染出来了；
       §G8-⑤⑥   **判据**：换身份之后 `.banner` 为 0、`banner--loud` 为 0、
                  正文里没有 `unauthenticated`、会话条说的是**新**身份；
       §G8-⑦⑧   **同族自查**：业务日 `as_of` 跨身份**照旧保留**（⚠️ 那是**设计**、
                  不是残留：`stores/identity.ts` 的 `clearIdentity()` docstring 逐字写了
                  「不清 `asOf`」——业务日是查询口径、与「我是谁」无关；本拍把它钉住，
                  于是下一个人改了它会红），而页面上**没有**上一个身份的任何痕迹。 */
  {
    /** 本组自己的请求时序。⚠️ `cdp.on` 的监听器是一个 `Set`，故本监听器与上面
     *  §CI / §I5 那两个互不相干、各收各的。 */
    const G8_LOG = []
    const G8_BY_ID = new Map()
    let g8Phase = 'g8-before'
    cdp.on('Network.requestWillBeSent', (p) => {
      const url = String(p.request?.url ?? '')
      if (!url.includes('/api/')) return
      const rec = {
        phase: g8Phase,
        method: p.request.method,
        url: url.replace(/^https?:\/\/[^/]+/, ''),
        status: null,
      }
      G8_BY_ID.set(p.requestId, rec)
      G8_LOG.push(rec)
    })
    cdp.on('Network.responseReceived', (p) => {
      const rec = G8_BY_ID.get(p.requestId)
      if (rec !== undefined) rec.status = p.response.status
    })

    const g8Eval = async (expression) => {
      const r = await cdp.send('Runtime.evaluate',
        { expression, returnByValue: true, awaitPromise: true }, sessionId)
      if (r?.exceptionDetails !== undefined) {
        out(`    ⚠️ §G8 evaluate 抛了：${JSON.stringify(r.exceptionDetails).slice(0, 300)}`)
      }
      return r?.result?.value
    }
    const g8Json = async (e) => JSON.parse(String(await g8Eval(e) ?? 'null'))
    /** ⚠️ 正文一律走 `toPlainText`（终审 I4 的单一所有者）：不给「needle 撞上一段
     *  CSS/JS 原文」留第二个出口。 */
    const g8Text = async () => toPlainText(String(await g8Eval('document.documentElement.outerHTML') ?? ''))
    const g8Until = async (expression, what, timeoutMs = 60000) => {
      const t0 = Date.now()
      for (;;) {
        if (await g8Eval(expression) === true) return true
        if (Date.now() - t0 > timeoutMs) {
          check(`§G8 等到「${what}」`, false, `${timeoutMs} ms 内没等到`)
          return false
        }
        await sleep(200)
      }
    }
    /** **真鼠标**点一下（姿势逐字抄上面 §CI 那个 `realClick`：scrollIntoView → 量矩形 →
     *  moved/pressed/released 三发）。⚠️ 刻意不用 `el.click()`：本组要证明的是
     *  「一次真人点击之后浏览器真的发出了那一串请求」。 */
    const g8Click = async (selector) => {
      await g8Eval(`(() => { const b = document.querySelector(${JSON.stringify(selector)})
        if (b !== null) b.scrollIntoView({ block: 'center' }); return b !== null })()`)
      await sleep(350)
      const rect = await g8Json(`(() => {
        const b = document.querySelector(${JSON.stringify(selector)})
        if (b === null) return 'null'
        const r = b.getBoundingClientRect()
        const x = r.x + r.width / 2
        const y = r.y + r.height / 2
        const hit = document.elementFromPoint(x, y)
        return JSON.stringify({ x, y, text: (b.textContent ?? '').trim().slice(0, 20),
          hit: hit === null ? false : (b.contains(hit) || hit.contains(b)) })
      })()`)
      check(`§G8 反空转：\`${selector}\` 在页面上、且那一点上就是它自己`,
        rect !== null && rect.hit === true, JSON.stringify(rect))
      if (rect === null) return
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
    }
    const g8Fill = async (selector, text) => {
      await g8Click(selector)
      await g8Eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)})
        if (el !== null) el.value = ''; return true })()`)
      await cdp.send('Input.insertText', { text }, sessionId)
      await sleep(150)
    }
    /** 走**登录表单**登进去。⚠️ 刻意不用 CDP 种 cookie：本组要的是「换身份登录」
     *  那一条真路径（`Login.vue` 的 submit → `session.login()` → `adopt()`），
     *  而 `adopt()` 正是本次修法的那个清理点。 */
    const g8Login = async (kind, name) => {
      if (!await g8Until(`document.querySelector('#login-name') !== null`, '登录表单出现')) return
      /* ⚠️ 那一格单选按钮是**视觉隐藏**的（`.auth__kinds input` 与 `IdentitySwitcher`
         的 `.role input` 同款：`position:absolute; opacity:0`），故点它的中心点会命中
         外面那个 `<label>` 而不是它自己 ⇒ 一律点 **label**（`:has()` 选中含那个 value 的
         那一个）。本波第一次跑就用 `input[...]` 当场撞上了这一格。 */
      if (kind === 'teacher') await g8Click('label.kind:has(input[value="teacher"])')
      await g8Fill('#login-name', name)
      await g8Fill('#login-password', DEMO_PASSWORD)
      await g8Click('form.auth__form button[type="submit"]')
    }
    const BANNER_PROBE = `(() => {
      const all = [...document.querySelectorAll('.banner')]
      const b = all[0] ?? null
      return JSON.stringify({
        count: all.length,
        loud: document.querySelectorAll('.banner--loud').length,
        cls: b === null ? null : b.getAttribute('class'),
        code: b === null ? null : (b.querySelector('.banner__code')?.textContent ?? '').trim(),
        status: b === null ? null : (b.querySelector('.banner__status')?.textContent ?? '').trim(),
        where: b === null ? null : (b.querySelector('.banner__where')?.textContent ?? '').trim(),
        advice: b === null ? null : (b.querySelector('.banner__advice')?.textContent ?? '').trim(),
      })
    })()`
    const ASOF_PROBE = `(() => {
      let stored = null
      try { stored = JSON.parse(localStorage.getItem('pe.identity.v1') ?? 'null')?.asOf ?? null }
      catch { stored = null }
      return JSON.stringify({ stored, input: document.querySelector('#identity-asof')?.value ?? null })
    })()`

    /* ---- ① 教师从**表单**登录 → 去预警队列页 ---- */
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: 1440, height: 2400, deviceScaleFactor: 1, mobile: false }, sessionId)
    g8Phase = 'g8-login-teacher'
    await cdp.send('Page.navigate', { url: WEB + '/login' }, sessionId)
    await g8Login('teacher', TEACHER)
    check('§G8-① 前提：教师从**登录表单**登进去了（落到 /t/dashboard）',
      await g8Until(`location.pathname.startsWith('/t/dashboard')`, '落到 /t/dashboard'), '')
    await cdp.send('Page.navigate', { url: WEB + '/t/alerts' }, sessionId)
    check('§G8-① 前提：到了预警队列页（说明书 §4 路线二第 7 步逐字要甲方走的那一页）',
      await g8Until(
        `location.pathname.startsWith('/t/alerts') && document.body.innerText.includes('预警队列')`,
        '预警队列渲染完'), '')
    await sleep(1200)
    const asOfBefore = await g8Json(ASOF_PROBE)
    check('§G8-① 反空转：业务日那一格读得出来（否则 §G8-⑦ 是假绿）',
      asOfBefore.stored !== null && asOfBefore.input === asOfBefore.stored, JSON.stringify(asOfBefore))

    /* ---- ② 真鼠标点「登出」 ---- */
    const g8Mark = G8_LOG.length
    g8Phase = 'g8-logout'
    await g8Click('.switcher__actions button.btn--ghost')
    check('§G8-② 前提：登出之后落在 /login',
      await g8Until(`location.pathname === '/login'`, '落到 /login'), '')
    await sleep(2500)
    const during = G8_LOG.slice(g8Mark)
    const n401 = during.filter((r) => r.status === 401).length
    out(`    §G8 登出那一段的逐请求（${during.length} 发）：`
      + during.map((r) => `${r.method} ${r.url} → ${r.status}`).join('；'))
    /* ⚠️⚠️ 反空转（本组最要命的两拍）：下面「横幅不在」那一格只有在「横幅**真的**被
       挂上过」时才有意义。⚠️ 若哪天这两拍红了、而红的原因是「登出不再发那一批读请求」
       （即上游那一格 —— 页面那句 watch 在 `clearIdentity()` 之后仍然重读 —— 被修掉了），
       那么 §G8-⑤⑥ 会**假绿**：此时**不要删这两拍**，改成手工把一条 `unauthenticated`
       raise 进常驻位（`useApiError().raise(…)`）再走一遍换身份登录。 */
    check('§G8-② 反空转：登出那一刻**确实**有请求回了 401（改前实测 4 条；'
      + '它们是 `clearIdentity()` 触发页面那句 watch 之后**新发**的一批，'
      + '⚠️ 不是在飞的旧请求 —— 发出时刻全在 `POST /api/auth/logout → 204` **之后**）',
      n401 >= 1, `401 = ${n401} 条 / 共 ${during.length} 发`)
    check('§G8-② 取证：那一批里 `/api/course-sections` 是 **200**（它是 7 个匿名读之一）'
      + '而其余要身份的那几发是 401 —— 于是「4 条 401 / 5 发」这个形状是**可解释**的，'
      + '不是一个随机数',
      during.some((r) => r.url.startsWith('/api/course-sections') && r.status === 200), '')
    const atLogin = await g8Json(BANNER_PROBE)
    check('§G8-③ 反空转：那一刻横幅**真的被挂上了**、是 `banner--loud` 那一档、'
      + '而它的 code 是 `unauthenticated`',
      atLogin.count >= 1 && atLogin.loud >= 1 && atLogin.code === 'unauthenticated',
      JSON.stringify(atLogin))
    out(`    §G8 /login 上那块横幅的原文：${atLogin.code} ${atLogin.status} ${atLogin.where}`
      + ` — ${atLogin.advice}`)

    /* ---- ③ 换身份登录（学生，另一棵树上）---- */
    g8Phase = 'g8-login-student'
    const g8StudentNo = await studentNoOf(STUDENT)
    await g8Login('student', g8StudentNo)
    check('§G8-④ 前提：换身份登录成功、落到学生首页',
      await g8Until(`location.pathname.startsWith('/s/home')`, '落到 /s/home'), '')
    check('§G8-④ 前提：学生首页**真的渲染出来了**（不是白屏、不是还在 loading）',
      await g8Until(`document.body.innerText.includes('本周训练量')`, '学生首页渲染完'), '')
    await sleep(1200)

    /* ---- ④ 判据 ---- */
    const after = await g8Json(BANNER_PROBE)
    check('§G8-⑤ **判据**：换身份登录之后页面上**没有任何** `.banner`'
      + '（改前那一块 401 横幅就挂在这里，跨过了整个登录）',
      after.count === 0, JSON.stringify(after))
    check('§G8-⑤ **判据**：更没有 `banner--loud`（Plan 06 终审要的那个「响亮」档）',
      after.loud === 0, `loud = ${after.loud}`)
    const g8Body = await g8Text()
    check('§G8-⑥ **判据**：正文里**没有** `unauthenticated` 那一个 code'
      + '（它是后端给**程序**看的机器串，挂在学生首页上只会让人以为这个学生出了事）',
      !g8Body.includes('unauthenticated'), '')
    const g8Who = String(await g8Eval(
      `(document.querySelector('.switcher__who')?.innerText ?? '').replace(/\\s+/g, ' ').trim()`) ?? '')
    check(`§G8-⑥ **判据**：会话条说的是**新**身份（学生 + ${g8StudentNo}），`
      + `不是上一个教师 ${TEACHER}`,
      g8Who.includes('STUDENT') && g8Who.includes(g8StudentNo) && !g8Who.includes(TEACHER), g8Who)

    /* ---- ⑤ 同族自查 ---- */
    const asOfAfter = await g8Json(ASOF_PROBE)
    check('§G8-⑦ 同族：业务日 `as_of` 跨身份**照旧保留**（⚠️ 这是**设计**、不是残留：'
      + '`stores/identity.ts` 的 `clearIdentity()` docstring 逐字写了「不清 `asOf`」，'
      + '理由是业务日属于查询口径、与「我是谁」无关。本拍把那一格钉住，'
      + '于是下一个人顺手把它清了会红）',
      asOfAfter.stored === asOfBefore.stored && asOfAfter.input === asOfBefore.stored,
      `登出前 ${JSON.stringify(asOfBefore)} → 换身份登录后 ${JSON.stringify(asOfAfter)}`)
    const g8Teachers = (await req('GET', '/api/teachers?limit=200',
      { as: 'teacher', quiet: true, record: false })).json?.items ?? []
    const g8T1 = g8Teachers.find((t) => t.staff_no === TEACHER)
    check('§G8-⑦ 反空转：期望侧真的取到了上一个身份的姓名（否则下一拍是假绿）',
      g8T1 !== undefined && String(g8T1.name).length > 0, JSON.stringify(g8T1?.name ?? null))
    check(`§G8-⑧ 同族：学生首页的正文里**没有**上一个身份的任何痕迹`
      + `（工号 ${TEACHER} 与姓名 ${g8T1?.name} 一个都不出现）`,
      g8T1 !== undefined && !g8Body.includes(TEACHER) && !g8Body.includes(String(g8T1.name)), '')
  }

  /* ------------------------------------------------------------------
     ⚠️⚠️ **Plan 07 Task 11 · G14**：错误横幅「**换页要清**」今天没实现。

     `components/ApiErrorBanner.vue` 的文件头从 Plan 04 起就逐字写着那块横幅状态
     「不持久化、**不跨页共享（换页要清）**、也没有派生状态」，而改前 `dismiss()`
     只有三个调用方 —— 横幅自己那个「关闭 ✕」、`stores/session.ts` 的 `adopt()` 与
     `forget()`（= Task 10 · G8 补的「**换身份**要清」）⇒ **换页不清**。

     改前的运行时取证（真浏览器 + 真鼠标 `Input.dispatchMouseEvent` + CDP，**产品档**，
     本波亲跑；两份日志在 task-11-report.md §3）：
       · 管理员从**登录表单**登进去 → `/admin/students/99999` →
         `GET /api/students/99999 → 404 not_found` → 横幅挂出来了
         （`.banner` 1 条 / `banner--loud` 1 条 / `where` = `GET /api/students/99999`）；
       · 真鼠标点报头导航去 `/t/dashboard` ⇒ 那一块横幅**原样跟过去**
         （逐字：`{"count":1,"loud":1,"code":"not_found","status":"404",
         "where":"GET /api/students/99999","path":"/t/dashboard"}`），
         说的却是**上一页**的事；`history.back()` 那一档同样跟过去；
       · 只有**整页刷新**会清掉它（模块级 `shallowRef` 随文档一起重置）——
         改前实测 `Page.navigate` 到 `/admin` 之后 `count` 才是 0。

     修法（⚠️ **单一所有者**，派单逐字要求「在路由变化那一格清一次 …
     不要每个页面各清一次」）：`router/index.ts` 里**一个** `router.beforeEach`
     ⇒ `useApiError().dismiss()`，注册在那个会话守卫**之前**，13 个业务页面一行都没动。
     ⚠️ **为什么是 `beforeEach` 而不是 `afterEach`**：两种都实测过、**两种今天都保住了**
     §G14-⑥ 那一格（会话过期仍然响亮），而 `beforeEach` 严格更早 ⇒ 会被它擦掉的情形是
     `afterEach` 的一个**真子集** ⇒ 取严格更安全的那一个。逐字理由住在那个钩子的 docblock 里。
     ⚠️ **定点变异**（本波实测两轮）：把那个 `router.beforeEach` 整块删掉 →
     §G14-③④ 当场红（dev 档整轮 smoke：**797 绿 / 6 红**，另 4 红是 §G15 那一组的；
     §G14-①②⑥ 与 §G15-④ 仍然绿，即前提没变、只有判据变红）。
     ⚠️ 而 §G14-⑤ **第一版是假绿的**（它那时用 `Page.navigate` 换文档，于是
     `history.back()` 成了整页刷新）⇒ 改成同文档内 `router.push` + popstate 之后
     又跑了一遍同一个变异：⑤ 那一格**红了**（`count` 1 → 0 的那一格变成 1 → 1）。
     逐字取证见 task-11-report.md §3.5。

     这一组钉的六格：
       §G14-①② **前提 / 反空转**：管理员真的从表单登进去了、那个 404 **真的**把一块
                 `banner--loud` 挂上了（少了这两拍，下面「横幅不在」可能只是因为
                 **从来没在过** = 假绿）；
       §G14-③④ **判据**：真鼠标点报头导航换页之后 `.banner` 为 0、`banner--loud` 为 0、
                 正文里没有 `not_found` 那一个 code；
       §G14-⑤   **判据（另一条换页路径）**：**同文档内** `router.push` 再撞一次 404、
                 然后 `history.back()` 走 popstate ⇒ 同样清掉了
                 （⚠️ 它自带两拍前提：router 取得到、back 之后真的换了页）；
       §G14-⑥   ⚠️**不许把横幅改成静默**（Plan 06 终审要的那个「响亮」）：真删一次
                 `pe_session` cookie 造一次**会话中途过期** ⇒ 必须落到 `/login?next=…`
                 **且**横幅仍在、仍是 `banner--loud`、`code` 仍是 `unauthenticated`。
                 ⚠️ 这一拍同时就是派单点名要复跑的那一格（Task 10 逐字论证过
                 「`dismiss` 恒早于 `raise`」，本波把它从**论证**升级成**运行时断言**）。 */
  {
    const g14Eval = async (expression) => {
      const r = await cdp.send('Runtime.evaluate',
        { expression, returnByValue: true, awaitPromise: true }, sessionId)
      if (r?.exceptionDetails !== undefined) {
        out(`    ⚠️ §G14 evaluate 抛了：${JSON.stringify(r.exceptionDetails).slice(0, 300)}`)
      }
      return r?.result?.value
    }
    const g14Json = async (e) => JSON.parse(String(await g14Eval(e) ?? 'null'))
    /** ⚠️ 正文一律走 `toPlainText`（终审 I4 的单一所有者）：不给「needle 撞上一段
     *  CSS/JS 原文」留第二个出口。 */
    const g14Text = async () => toPlainText(String(await g14Eval('document.documentElement.outerHTML') ?? ''))
    const g14Until = async (expression, what, timeoutMs = 60000) => {
      const t0 = Date.now()
      for (;;) {
        if (await g14Eval(expression) === true) return true
        if (Date.now() - t0 > timeoutMs) {
          check(`§G14 等到「${what}」`, false, `${timeoutMs} ms 内没等到`)
          return false
        }
        await sleep(200)
      }
    }
    /** **真鼠标**点一下（姿势逐字抄上面 §G8 那个 `g8Click`）。 */
    const g14Click = async (selector) => {
      await g14Eval(`(() => { const b = document.querySelector(${JSON.stringify(selector)})
        if (b !== null) b.scrollIntoView({ block: 'center' }); return b !== null })()`)
      await sleep(350)
      const rect = await g14Json(`(() => {
        const b = document.querySelector(${JSON.stringify(selector)})
        if (b === null) return 'null'
        const r = b.getBoundingClientRect()
        const x = r.x + r.width / 2
        const y = r.y + r.height / 2
        const hit = document.elementFromPoint(x, y)
        return JSON.stringify({ x, y, text: (b.textContent ?? '').trim().slice(0, 20),
          hit: hit === null ? false : (b.contains(hit) || hit.contains(b)) })
      })()`)
      check(`§G14 反空转：\`${selector}\` 在页面上、且那一点上就是它自己`,
        rect !== null && rect.hit === true, JSON.stringify(rect))
      if (rect === null) return
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
      await cdp.send('Input.dispatchMouseEvent',
        { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 }, sessionId)
    }
    const g14Fill = async (selector, text) => {
      await g14Click(selector)
      await g14Eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)})
        if (el !== null) el.value = ''; return true })()`)
      await cdp.send('Input.insertText', { text }, sessionId)
      await sleep(150)
    }
    /** 走**登录表单**登进去（姿势逐字抄上面 §G8 那个 `g8Login`）。 */
    const g14Login = async (kind, name) => {
      if (!await g14Until(`document.querySelector('#login-name') !== null`, '登录表单出现')) return
      if (kind === 'teacher') await g14Click('label.kind:has(input[value="teacher"])')
      await g14Fill('#login-name', name)
      await g14Fill('#login-password', DEMO_PASSWORD)
      await g14Click('form.auth__form button[type="submit"]')
    }
    const G14_BANNER = `(() => {
      const all = [...document.querySelectorAll('.banner')]
      const b = all[0] ?? null
      return JSON.stringify({
        count: all.length,
        loud: document.querySelectorAll('.banner--loud').length,
        code: b === null ? null : (b.querySelector('.banner__code')?.textContent ?? '').trim(),
        status: b === null ? null : (b.querySelector('.banner__status')?.textContent ?? '').trim(),
        where: b === null ? null : (b.querySelector('.banner__where')?.textContent ?? '').trim(),
        advice: b === null ? null : (b.querySelector('.banner__advice')?.textContent ?? '').trim(),
        path: location.pathname,
        search: location.search,
        notice: (document.querySelector('.auth__notice')?.textContent ?? '').trim(),
      })
    })()`
    /** 一个不存在的主键。⚠️ 刻意用 99999 而不是「某个越权的学生 id」：越权那一档
     *  要按**当前身份**现算（本波实测 T0001 对 60 个学号里 41 个有权、19 个 403），
     *  而 404 与身份无关 ⇒ 这一拍在三档上都是同一个形状。 */
    const GHOST = 99999

    /* ---- ① 管理员从表单登录 → 去一个不存在的资源详情 ---- */
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: 1440, height: 2400, deviceScaleFactor: 1, mobile: false }, sessionId)
    await cdp.send('Page.navigate', { url: WEB + '/login' }, sessionId)
    await g14Login('teacher', ADMIN)
    check('§G14-① 前提：管理员从**登录表单**登进去了（落到 /admin）',
      await g14Until(`location.pathname === '/admin'`, '落到 /admin'), '')
    await sleep(1200)
    await cdp.send('Page.navigate', { url: `${WEB}/admin/students/${GHOST}` }, sessionId)
    check(`§G14-① 前提：到了 /admin/students/${GHOST}（一个不存在的主键）`,
      await g14Until(`location.pathname === '/admin/students/${GHOST}'`, '落到详情页'), '')
    await sleep(2500)

    /* ---- ② 反空转：横幅真的被挂上了 ---- */
    const g14Raised = await g14Json(G14_BANNER)
    out(`    §G14 详情页上那块横幅的原文：${g14Raised.code} ${g14Raised.status} ${g14Raised.where}`
      + ` — ${g14Raised.advice}`)
    check('§G14-② 反空转：那个 404 **真的**把一块横幅挂上了、是 `banner--loud` 那一档、'
      + 'code 是 `not_found`、`where` 点名的就是那一个不存在的主键'
      + '（少了本拍，下面「横幅不在」可能只是因为**从来没在过** = 假绿）',
      g14Raised.count >= 1 && g14Raised.loud >= 1 && g14Raised.code === 'not_found'
        && String(g14Raised.where ?? '').includes(`/api/students/${GHOST}`),
      JSON.stringify(g14Raised))

    /* ---- ③④ 判据：真鼠标点报头导航换页 ---- */
    await g14Click('.masthead__nav a[href="/t/dashboard"]')
    check('§G14-③ 前提：真鼠标点报头导航之后**换页成功了**（落到 /t/dashboard）',
      await g14Until(`location.pathname === '/t/dashboard'`, '落到 /t/dashboard'), '')
    await sleep(2500)
    const g14AfterNav = await g14Json(G14_BANNER)
    check('§G14-③ **判据**：换页之后页面上**没有任何** `.banner`'
      + '（改前那一块 404 横幅就原样跟到这里，说的却是上一页的事）',
      g14AfterNav.count === 0, JSON.stringify(g14AfterNav))
    check('§G14-④ **判据**：更没有 `banner--loud`，而正文里**没有** `not_found` 那一个 code',
      g14AfterNav.loud === 0 && !(await g14Text()).includes('not_found'), `loud = ${g14AfterNav.loud}`)

    /* ---- ⑤ 判据（另一条换页路径）：popstate ---- */
    /* ⚠️⚠️ 这一格**必须走同文档内的 SPA 导航**，不能用 `Page.navigate` —— 本波定点变异
       实测到的一次**假绿**：`Page.navigate` 换一个**文档**，于是随后那一次
       `history.back()` 是**整页刷新**（模块级 `shallowRef` 随文档一起重置）⇒
       「横幅不在」与本次修法**无关**，把清理那一步摘掉它照样绿（变异那一轮
       §G14-③④ 红了、而改前那一版 §G14-⑤ **仍然绿**，日志在 task-11-report.md §3.5）。
       故这里改用 `router.push` 进详情页（同一个文档、同一条守卫链），再 `history.back()`
       走 popstate —— 两条都是 SPA 的换页路径，而 popstate 与「点链接」不是同一条代码路径。
       ⚠️ `$router` 从 `#app` 上那个 `__vue_app__` 取（Vue 3 在 `app.mount()` 里写上去的，
       dev 与产物里都在），⚠️ **零新增依赖**。 */
    const g14Pushed = await g14Eval(`(async () => {
      const r = document.querySelector('#app')?.__vue_app__?.config?.globalProperties?.$router
      if (r === undefined || r === null) return false
      await r.push(${JSON.stringify(`/admin/students/${GHOST}`)})
      return true
    })()`)
    check('§G14-⑤ 前提：从页面里取到了那个 router、并用 `router.push` 走**同文档内**的'
      + ' SPA 导航进了详情页（取不到 / 换文档都会让下面那两拍变成假绿）',
      g14Pushed === true
        && await g14Until(`location.pathname === '/admin/students/${GHOST}'`, '落到详情页'),
      JSON.stringify(g14Pushed))
    await sleep(2500)
    const g14Again = await g14Json(G14_BANNER)
    check('§G14-⑤ 反空转：再撞一次那个 404，横幅**又**挂上了（否则下一拍是假绿）',
      g14Again.count >= 1 && g14Again.code === 'not_found', JSON.stringify(g14Again))
    await g14Eval('history.back(); true')
    check('§G14-⑤ 前提：`history.back()` 之后**真的**换页了（走 popstate，仍在同一个文档里）',
      await g14Until(`location.pathname !== '/admin/students/${GHOST}'`, '离开详情页'), '')
    await sleep(2500)
    const g14AfterBack = await g14Json(G14_BANNER)
    check('§G14-⑤ **判据**：popstate 那一条换页路径同样清掉了',
      g14AfterBack.count === 0, JSON.stringify(g14AfterBack))

    /* ---- ⑥ ⚠️ 不许把横幅改成静默：真造一次「会话中途过期」 ---- */
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    await cdp.send('Page.navigate', { url: WEB + '/login' }, sessionId)
    await g14Login('teacher', TEACHER)
    check('§G14-⑥ 前提：教师从**登录表单**登进去了（落到 /t/dashboard）',
      await g14Until(`location.pathname === '/t/dashboard'`, '落到 /t/dashboard'), '')
    await cdp.send('Page.navigate', { url: WEB + '/t/alerts' }, sessionId)
    check('§G14-⑥ 前提：到了预警队列页',
      await g14Until(`document.body.innerText.includes('预警队列')`, '预警队列渲染完'), '')
    await sleep(1500)
    /* ⚠️ 删掉那个 HttpOnly 的 cookie = **服务端那一行还活着、而浏览器把它丢了**，
       形状与「会话过期」逐字同一个（后端只看 cookie）。⚠️ 两个 origin 各删一次：
       本脚本的 WEB 可能是 localhost 也可能是 127.0.0.1。 */
    await cdp.send('Network.deleteCookies', { name: 'pe_session', url: WEB }, sessionId)
    await cdp.send('Network.deleteCookies',
      { name: 'pe_session', url: WEB.replace('localhost', '127.0.0.1') }, sessionId)
    /* 触发一批新读请求：改业务日 `as_of`（页面那句 watch 会重读）。
       ⚠️ 刻意不用「点导航」：报头那一排只有 TREES 的三条，而换页会**先**清横幅，
       于是「过期横幅还在不在」会被换页那一格自己答掉，证明不了任何事。 */
    await g14Eval(`(() => {
      const el = document.querySelector('#identity-asof')
      if (el === null) return false
      el.value = '2025-10-11'
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
      return true
    })()`)
    check('§G14-⑥ 前提：会话过期之后落到 /login **且带着 `?next=`**'
      + '（`main.ts` 那个订阅者带的；⚠️ 与「主动登出」那一档的**唯一**区别就是它）',
      await g14Until(`location.pathname === '/login' && location.search.includes('next=')`,
        '落到 /login?next=…'), String(await g14Eval('location.pathname + location.search')))
    await sleep(2500)
    const g14Expired = await g14Json(G14_BANNER)
    out(`    §G14-⑥ 过期那一刻 /login 上那块横幅的原文：${g14Expired.code} ${g14Expired.status}`
      + ` ${g14Expired.where}`)
    check('§G14-⑥ **判据（不许改静默）**：会话中途过期时那块横幅**照旧响亮**'
      + '（`.banner` ≥ 1、`banner--loud` ≥ 1、code 仍是 `unauthenticated`）——'
      + '即「换页要清」那一格**没有**把 Plan 06 终审要的那个「响亮」一起清掉',
      g14Expired.count >= 1 && g14Expired.loud >= 1 && g14Expired.code === 'unauthenticated',
      JSON.stringify(g14Expired))

    /* ------------------------------------------------------------------
       ⚠️⚠️ **Plan 07 Task 11 · G15**：`/login` 上那块 401 横幅的 advice 有**两处半假**。

       改前那一句逐字是：
         「会话失效了（pe_session cookie 缺失、已过期或已登出）。
           **前端会把你送去登录页，登录之后回到刚才那一页**。」
       而它在**主动登出**那一档两处都半假（Task 10 登记为 G15，本波真浏览器复现，
       取证见 task-11-report.md §2）：
         ① 登出之后用户**已经站在**登录页上 —— 「送你去的登录页」就是当前这一页；
         ② `IdentitySwitcher` 的 `onLogout()` 走 `session.logout()` →
            `router.replace('/login')`，**不带** `?next=`，而 `views/auth/Login.vue` 的
            `safeNext()` 在 `next` 缺失时返回 `session.homePath` ⇒「回到刚才那一页」不成立。
       ⚠️ 而在**会话中途过期**那一档两句**都**成立（`main.ts` 的订阅者带 `next`，
       且它先把「回到哪里」写进 `session.notice`）⇒ 病灶是「同一句话被两个时机共用、
       而只对其中一个为真」。

       改后那一句（⚠️ 对**两个**时机都为真，且**不含任何阈值数字** —— 与本仓
       「页面上不写死数字、具体数字住 spec」那一条口径一致）：
         「会话失效了（pe_session cookie 缺失、已过期或已登出）。请重新登录：
           会话中途过期时登录之后回到你刚才那一页，主动登出时登录之后落在你自己那一端的首页。」

       这一组钉的五格（⚠️ 前四格打在**主动登出**那一档、第五格打在**会话过期**那一档，
       两档合起来才证明「新那一句对两个时机都为真」）：
       §G15-① **needle 无歧义**：新那两句在 `toPlainText(outerHTML)` 里**各恰好 1 次**
               （⚠️ 本仓前几波在「页面上还有第二处同串」上栽过三次，故这一拍排在最前面：
               少了它，②③ 那两拍可能只是在数一段脚本原文）；
       §G15-② **判据**：改前那两句半假**一个都不在**了；
       §G15-③ **判据**：新那两句**都在**；
       §G15-④ **取证**：这一档 `location.search` 里**没有** `next=` ⇒ 新句子的**后半**
               才是这一档的真话（⚠️ 它同时是 §G15-③ 那半句的**前提**，不是重复）；
       §G15-⑤ **取证**：会话过期那一档 `search` 里**有** `next=`、且 `session.notice`
               **点名了**回到哪一页 ⇒ 新句子的**前半**也是真话。
       ⚠️ **定点变异**（本波实测）：把那一句改回改前那两句半假 → §G15-①②③ 当场红。 */
    const G15_NEW_A = '会话中途过期时登录之后回到你刚才那一页'
    const G15_NEW_B = '主动登出时登录之后落在你自己那一端的首页'
    const G15_OLD_A = '前端会把你送去登录页'
    const G15_OLD_B = '登录之后回到刚才那一页'
    /** 计数一律打在 `toPlainText` 的返回值上（终审 I4 的单一所有者）。 */
    const countOf = (haystack, needle) => haystack.split(needle).length - 1

    /* §G15-⑤ 先钉住（此刻浏览器就停在「会话过期」那一档的 /login?next=… 上）。 */
    check('§G15-⑤ 取证：**会话过期**那一档 `?next=` 真的在、且 `session.notice` **点名了**'
      + '回到哪一页 ⇒ 新那句子的**前半**（「会话中途过期时登录之后回到你刚才那一页」）'
      + '在这一档是真话',
      g14Expired.search.includes('next=') && g14Expired.notice.includes('登录之后会回到'),
      JSON.stringify({ search: g14Expired.search, notice: g14Expired.notice.slice(0, 90) }))
    const g15ExpiredPlain = await g14Text()
    check('§G15-⑤ 取证：而那一块横幅的 advice 在**这一档**也是新那一句'
      + '（两个时机共用同一句 ⇒ 两句都得在这一档成立）',
      countOf(g15ExpiredPlain, G15_NEW_A) === 1 && countOf(g15ExpiredPlain, G15_NEW_B) === 1,
      JSON.stringify({ a: countOf(g15ExpiredPlain, G15_NEW_A), b: countOf(g15ExpiredPlain, G15_NEW_B) }))

    /* 换成「主动登出」那一档：教师 → /t/alerts → 真鼠标点「登出」→ /login。 */
    await cdp.send('Network.clearBrowserCookies', {}, sessionId)
    await cdp.send('Page.navigate', { url: WEB + '/login' }, sessionId)
    await g14Login('teacher', TEACHER)
    await g14Until(`location.pathname === '/t/dashboard'`, '落到 /t/dashboard')
    await cdp.send('Page.navigate', { url: WEB + '/t/alerts' }, sessionId)
    await g14Until(`document.body.innerText.includes('预警队列')`, '预警队列渲染完')
    await sleep(1500)
    await g14Click('.switcher__actions button.btn--ghost')
    check('§G15-④ 前提：真鼠标点「登出」之后落在 /login',
      await g14Until(`location.pathname === '/login'`, '落到 /login'), '')
    await sleep(2500)
    const g15Logout = await g14Json(G14_BANNER)
    out(`    §G15 /login 上那块横幅的 advice 原文（逐字）：${g15Logout.advice}`)
    check('§G15-④ 取证：**主动登出**那一档 `location.search` 里**没有** `next=`'
      + '（`onLogout()` 的 `router.replace(\'/login\')` 不带它）⇒ 改前那句'
      + '「登录之后回到刚才那一页」在这一档是**假话**，而新那句子的**后半**才是真话',
      g15Logout.search === '' && g15Logout.count >= 1 && g15Logout.code === 'unauthenticated',
      JSON.stringify({ search: g15Logout.search, count: g15Logout.count, code: g15Logout.code }))

    const g15Plain = await g14Text()
    check('§G15-① **needle 无歧义**：新那两句在整页正文里**各恰好 1 次**'
      + '（⚠️ 本仓前几波在「页面上还有第二处同串」上栽过三次；'
      + '0 次 = 判据是空的，≥ 2 次 = 这一拍数不到它自己以为的那一处）',
      countOf(g15Plain, G15_NEW_A) === 1 && countOf(g15Plain, G15_NEW_B) === 1,
      JSON.stringify({ a: countOf(g15Plain, G15_NEW_A), b: countOf(g15Plain, G15_NEW_B) }))
    check('§G15-② **判据**：改前那两句半假**一个都不在**了',
      countOf(g15Plain, G15_OLD_A) === 0 && countOf(g15Plain, G15_OLD_B) === 0,
      JSON.stringify({ oldA: countOf(g15Plain, G15_OLD_A), oldB: countOf(g15Plain, G15_OLD_B) }))
    check('§G15-③ **判据**：新那两句**都在**（渲染出来的那一块 `.banner__advice` 上）',
      String(g15Logout.advice ?? '').includes(G15_NEW_A)
        && String(g15Logout.advice ?? '').includes(G15_NEW_B),
      JSON.stringify(g15Logout.advice))
  }

  cdp.close()
  // ⚠️ **先等浏览器真的退出、再删那个 profile 目录**（实测踩过的坑）：
  //    `kill('SIGKILL')` 是异步的，而 Windows 上 Chromium 的 `--user-data-dir`
  //    里那些文件在进程还活着的一刻是被**独占打开**的，于是紧跟着的
  //    `fs.rmSync` 会得到 `EPERM: permission denied`（不是 ENOENT，`force: true` 挡不住它）。
  //    故这里 ① 等 `exit` 事件（带 5 s 上限）② 给 rmSync 加 `maxRetries`
  //    ③ 仍然删不掉就**只警告、不判红**：一个留在 `$env:TEMP` 下的空目录
  //    不是本步要证的事，而把它判红会让「16 条路由全部取证成功」这一次运行
  //    因为一个清理动作而红（硬规矩：断言要钉被测面，不钉脚手架）。
  const exited = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), 5000)
    headless.child.once('exit', () => { clearTimeout(timer); resolve(true) })
    headless.child.kill('SIGKILL')
  })
  try {
    fs.rmSync(headless.workRoot, { recursive: true, force: true, maxRetries: 10, retryDelay: 400 })
    out(`    浏览器已退出（${exited}），临时 profile ${headless.workRoot} 已删掉`)
  } catch (err) {
    out(`    ⚠️ 浏览器已退出（${exited}），而临时 profile 删不掉（不影响任何断言）：${err?.code ?? err}`)
  }
})

/* ------------------------------------------------------------------ 第 15 步
   ⚠️ **两个静态守卫**（Plan 04 收尾波加了第一个，Plan 05A Task 3 加了第二个）：
   ① `check-tokens.mjs` —— 色值的唯一住址是 `src/styles/tokens.css`。它是 Plan 05B
      换肤（R1「简洁、蓝白色调、浅色系、按钮圆角」）的**前置条件**：那次重构的
      可执行判据是「改一个文件、全站变色」，而这句话只有在「色值真的只住在
      `tokens.css` 里」时才成立。
   ② `check-dist.mjs` —— **生产构建里不得留下 `adoptFromUrl`**（计划 §4.3 逐字要求
      「要有一条守卫证明它被摇掉了」）。⚠️ 这一条**只能读产物**：源码上那个
      `if (import.meta.env.DEV)` 永远看得见，「生产构建里它不存在」的真值只在 `dist/`。
      故它会自己跑一次 `npm run build`（`dist/` 不在时），并**反向**断言那个串在
      源码里确实存在（否则「0 次」可能只是谓词写坏了，硬规矩 #50）。
   ⚠️ 两步都**不需要后端也不需要前端起着**（纯静态 + 一次构建），故本步与第 17 步是
   18 步里唯二可以在两个服务都没起的情况下跑的：`npm run check:tokens` / `npm run check:dist`
   （⚠️ 第 17 步的 ① 那一拍要 PowerShell 与 Python —— 它 spawn 一次 `demo.ps1 -DryRun`）。
   ⚠️ 挂在这里的理由是「`npm run smoke` 全绿」应当**蕴含**「设计令牌没有散开」
   与「开发工具没有漏进生产」两件事。 */
await step(15, '两个构建守卫：check:tokens（色值唯一住址）+ check:dist（生产构建里没有 adoptFromUrl）', async () => {
  const here = path.dirname(fileURLToPath(import.meta.url))
  for (const [label, script, greenNeedle] of [
    ['check-tokens', 'check-tokens.mjs', '全绿'],
    ['check-dist', 'check-dist.mjs', '全绿'],
  ]) {
    const target = path.resolve(here, script)
    check(`${label}：守卫脚本存在`, fs.existsSync(target), target)
    if (!fs.existsSync(target)) continue
    const run = spawnSync(process.execPath, [target], { encoding: 'utf8', cwd: path.resolve(here, '..') })
    const stdout = run.stdout ?? ''
    for (const line of stdout.split('\n')) {
      if (line.includes('✓') || line.includes('✗')) out(`    ${line}`)
    }
    eq(`${label}：退出码 0`, run.status, 0)
    check(`${label}：它自报了「${greenNeedle}」那一行`, stdout.includes(greenNeedle),
      `stdout ${stdout.length} 字符`)
    if (run.stderr) out(`    stderr: ${run.stderr.trim().slice(-400)}`)
  }
  // ⚠️ 反空转（两条各自一份，理由逐字写在各自脚本的文件头）：
  //    · check-tokens 必须数到 tokens.css 自己的色值（≥ 20），否则「0 处 offender」
  //      可能只是谓词写坏了 / 路径指错了；
  //    · check-dist 必须扫到足够多的产物字节（≥ 100 kB），否则「0 次命中」同理。
  const tokensRun = spawnSync(process.execPath, [path.resolve(here, 'check-tokens.mjs')], { encoding: 'utf8' })
  const tokenLine = (tokensRun.stdout ?? '').split('\n').find((l) => l.includes('tokens.css 里有')) ?? ''
  out(`    ${tokenLine.trim()}`)
  check('check-tokens 数到了 tokens.css 自己的色值（≥ 20，否则谓词或路径坏了）',
    Number(tokenLine.match(/(\d+) 处/)?.[1] ?? 0) >= 20, tokenLine.trim())
  const distRun = spawnSync(process.execPath, [path.resolve(here, 'check-dist.mjs'), '--no-build'], { encoding: 'utf8' })
  const distLine = (distRun.stdout ?? '').split('\n').find((l) => l.includes('扫了')) ?? ''
  out(`    ${distLine.trim()}`)
  check('check-dist 扫到了产物（≥ 3 个文件，否则它扫错了目录）',
    Number(distLine.match(/扫了 (\d+) 个文件/)?.[1] ?? 0) >= 3, distLine.trim())
})

/* ------------------------------------------------------------------ 第 16 步
   ⚠️⚠️ **Plan 05A Task 4 新增的一步：鉴权本身**（派单逐字点名的第 17 步 =
   0 起的第 16 个）。前 15 步验的是**业务规则**（它们用会话当载体），
   本步验的是**载体本身**：绑定 → 登录 → me → 登出 → 旧 cookie 失效，
   以及三档授权（普通教师写管理台 403 / 管理员 201 / 学生 cookie 打教师端点 403）。

   ⚠️ 它**不复用**前面那些 jar：本步要验的正是「一个新账号从无到有」的全过程，
   故它自己建一个教师行（`SMOKE16`，管理员建、用完删掉），
   于是「未绑定 → 绑定 → 登录」三拍都落在一个**真的没绑过**的账号上。
   ⚠️ 用教师而不是学生：学生行由 `POST /api/students` 建，而一个学生行会立刻
   被 12 张表指着（`on_delete='restrict'`），删不掉 → 演示库会脏一行。
   教师行只在 `course_section.teacher_id` 与 `mini_test.entered_by` 上被指，
   新建的那一个两格都空 → 删得掉（第 10 步的 `SMOKE01` 就是这么做的）。 */
await step(16, '鉴权全链路：未绑定 → 绑定 → 登录 → me → 登出 → 旧 cookie 401；三档授权', async () => {
  const STAFF = 'SMOKE16'
  const NEW_PASSWORD = 'smoke-sixteen-2025'

  // ① 管理员建一个新教师（`role` 缺省 = teacher，**不是** admin）
  const created = await req('POST', '/api/teachers', {
    as: 'admin', body: { staff_no: STAFF, name: '联调脚本第 16 步建的教师' },
  })
  eq('① 管理员 POST /api/teachers → 201', created.status, 201)
  const newId = created.json?.id ?? null
  check('拿到了 id', Number.isInteger(newId), `id=${newId}`)
  eq('① 而它缺省**不是**管理员（漏写 role 得到的是普通教师：失效方向是少给权限）',
    created.json?.role, 'teacher')
  // ⚠️⚠️ **安全收紧波把这一拍反了过来**：此前它是
  //    `eq('① password_bound_at 是 null（还没绑定）', created.json?.password_bound_at, null)`，
  //    而那一列本波从 `TeacherRead` / `StudentRead` 与两行的 `list_exclude` 上一起摘掉了
  //    （裁定 3：它等于「哪些账号还能被抢占绑定」的清单）。
  //    ⚠️ 而**下面 ② 那一拍照样能证明「还没绑定」**：`POST /api/auth/login` 的
  //    403 `password_not_bound` 逐人给出了同一个答案 —— 摘掉那一列损失的只是
  //    「一次 list 就能批量数出谁没绑」，那正是本波要拿走的能力。
  check('① 响应里**没有** password_bound_at（安全收紧波摘的：它是「还能被抢占绑定」的清单）',
    !('password_bound_at' in (created.json ?? {})), `键=${Object.keys(created.json ?? {}).sort().join(',')}`)
  check('① 响应里**没有** password_hash（凭据不是响应体的一格）',
    !('password_hash' in (created.json ?? {})), `键=${Object.keys(created.json ?? {}).sort().join(',')}`)

  // ② 未绑定就登录 → 403 password_not_bound（**不是** 401：该去绑定，不是该重输）
  const notBound = await req('POST', '/api/auth/login', {
    body: { kind: 'teacher', login: STAFF, password: NEW_PASSWORD },
  })
  eq('② 未绑定就登录 → 403', notBound.status, 403)
  eq('② code 是 password_not_bound（前端据此把用户送去 /bind）',
    codeOf(notBound), 'password_not_bound')

  // ③ 绑定的四档失败，逐个试（顺序与后端 `bind_teacher` 的判定顺序一致）
  const weak = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: STAFF, name: '联调脚本第 16 步建的教师', password: '短' },
  })
  eq('③ 弱口令（< 8 字符）→ 422', weak.status, 422)
  eq('③ 而 code 是 unprocessable_value（**不是** request_validation_failed：两档不同）',
    codeOf(weak), 'unprocessable_value')
  const wrongName = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: STAFF, name: '不是这个名字', password: NEW_PASSWORD },
  })
  eq('③ 验身材料不符 → 403', wrongName.status, 403)
  eq('③ code 是 forbidden', codeOf(wrongName), 'forbidden')
  const unknown = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: 'NOSUCH99', name: '谁', password: NEW_PASSWORD },
  })
  eq('③ 不在册 → 也是 403（与「验身材料不符」**同码同 message**，不给区分信号）',
    unknown.status, 403)
  eq('③ 两档的 message 逐字相同', messageOf(unknown), messageOf(wrongName))
  const missing = await req('POST', '/api/auth/teachers/bind', { body: { staff_no: STAFF } })
  eq('③ 请求体缺字段 → 422', missing.status, 422)
  eq('③ 而 code 是 request_validation_failed', codeOf(missing), 'request_validation_failed')
  check('③ 422 的响应体里**没有**刚提交的那个口令（SecretStr + 按键名脱敏两道）',
    !missing.text.includes(NEW_PASSWORD), `${missing.text.length} 字符`)

  // ④ 绑定成功 → 204，且**不自动登录**（不回 Set-Cookie）
  const bound = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: STAFF, name: '联调脚本第 16 步建的教师', password: NEW_PASSWORD },
  })
  eq('④ 绑定 → 204', bound.status, 204)
  eq('④ 204 没有响应体', bound.text, '')
  eq('④ 而它**不**种 cookie（绑定与登录是两件事）', cookieFrom(bound), null)

  // ⑤ 再绑一次 → 409 password_already_bound（⚠️ 它排在 403 之后）
  const twice = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: STAFF, name: '联调脚本第 16 步建的教师', password: NEW_PASSWORD },
  })
  eq('⑤ 再绑一次 → 409', twice.status, 409)
  eq('⑤ code 是 password_already_bound（前端要说人话：「请直接登录」）',
    codeOf(twice), 'password_already_bound')
  const wrongAfterBound = await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: STAFF, name: '不是这个名字', password: NEW_PASSWORD },
  })
  /* ⚠️⚠️ **本拍实测是 403，不是 409**（实现者第一版写成了 409、当场红，故按实际改写）。
     后端 `bind_teacher` 的判定顺序逐字是：
       ① `ensure_acceptable(password)`  → 422 unprocessable_value（弱口令，排最前）
       ② `teacher is None or teacher.name != payload.name` → **403 forbidden**
       ③ `_bind_credential(...) == 0`（WHERE 里带 `password_hash IS NULL`）→ 409
     故「验身材料不符」在 ② 就被拦下，**永远走不到 ③**。
     ⚠️ 而那正是「409 排在 403 之后」这条顺序要的效果：一个**不知道**验身材料的人
     无论这个账号绑没绑过，拿到的都是同一句 403 —— 他读不出「绑定过了没有」。
     反过来（409 先判）就会让「先拿一个错名字试一次、看是 403 还是 409」
     成为一次有效的探测。⚠️ 于是 409 只对**拿着正确验身材料**的人可见，
     而那一档本来就是合法用户（他真的绑过了、该去登录）。 */
  eq('⑤ ⚠️ 已绑定 + 验身材料不符 → 仍然是 **403**（③ 那一档排在 409 之前，'
    + '故一个不知道验身材料的人读不出「绑定过了没有」）',
    wrongAfterBound.status, 403)
  eq('⑤ code 是 forbidden', codeOf(wrongAfterBound), 'forbidden')
  eq('⑤ 而 message 与「不在册」那一档逐字相同（不给区分信号）',
    messageOf(wrongAfterBound), messageOf(unknown))

  // ⑥ 口令错 → 401 invalid_credentials（与「未绑定」那两档**刻意可区分**）
  const wrongPassword = await req('POST', '/api/auth/login', {
    body: { kind: 'teacher', login: STAFF, password: 'not-the-password' },
  })
  eq('⑥ 口令错 → 401', wrongPassword.status, 401)
  eq('⑥ code 是 invalid_credentials（前端据此清空口令框、而不是把人送去 /bind）',
    codeOf(wrongPassword), 'invalid_credentials')

  // ⑦ 登录成功 → 200 + Set-Cookie + 六格响应体
  const loggedIn = await req('POST', '/api/auth/login', {
    body: { kind: 'teacher', login: STAFF, password: NEW_PASSWORD },
  })
  eq('⑦ 登录 → 200', loggedIn.status, 200)
  const freshCookie = cookieFrom(loggedIn)
  check('⑦ Set-Cookie 里有 pe_session=<64 字符>（secrets.token_urlsafe(48)）',
    freshCookie !== null && /^pe_session=[A-Za-z0-9_-]{64}$/.test(freshCookie),
    freshCookie === null ? '（没有）' : `${freshCookie.length} 字符`)
  // ⚠️ 大小写**逐字取自实测**（`Set-Cookie: pe_session=…; HttpOnly; Max-Age=7200;
  //    Path=/; SameSite=lax`）：`SameSite` 的**值是小写 `lax`** —— 后端
  //    `sessions.cookie_kwargs` 的注释逐字交代了为什么（Starlette 只认
  //    `"lax"`/`"strict"`/`"none"`/`False`，写 `"Lax"` 会原样落进响应头、
  //    而部分浏览器不接受）。故下面一律按小写断言，不做大小写无关的比较
  //    —— 「大小写无关」会让「有人把它改成 `Lax`」这一档静默通过。
  const setCookieRaw = (loggedIn.headers.getSetCookie?.() ?? [loggedIn.headers.get('set-cookie')])[0] ?? ''
  const maskedRaw = freshCookie === null ? setCookieRaw : setCookieRaw.split(';')[0] + '; …（令牌已掩）'
  for (const attr of ['HttpOnly', 'Max-Age=7200', 'Path=/', 'SameSite=lax']) {
    check(`⑦ cookie 带 ${attr}（逐字，含大小写）`, setCookieRaw.includes(attr), maskedRaw)
  }
  check('⑦ cookie **不带** Domain（宿主限定；写 domain 会让它对 *.localhost 全部子域可见）',
    !/;\s*domain=/i.test(setCookieRaw), maskedRaw)
  check(`⑦ cookie ${COOKIE_SECURE_EXPECTED ? '**带**' : '**不带**'} Secure`
    + (COOKIE_SECURE_EXPECTED
      ? '（公网档 = PE_ENV=prod：隧道边缘是 HTTPS，故 Secure 成立且**必须**在）'
      : '（本机不是 PE_ENV=production；生产上它必须在）'),
    (COOKIE_SECURE_EXPECTED === /;\s*secure/i.test(setCookieRaw)), maskedRaw)
  eq('⑦ 响应体恰好 6 个键（login 与 me 逐字同形）',
    Object.keys(loggedIn.json ?? {}).sort().join(','), 'id,kind,name,role,staff_no,student_no')
  eq('⑦ role 是 teacher', loggedIn.json?.role, 'teacher')
  eq('⑦ staff_no 是它、而 student_no 是 null（两格互斥）', loggedIn.json?.staff_no, STAFF)
  eq('⑦ student_no 是 null', loggedIn.json?.student_no, null)

  // ⑧ me → 与登录的响应体**逐字相同**
  const meRes = await req('GET', '/api/auth/me', { cookie: freshCookie })
  eq('⑧ 带新 cookie 的 GET /api/auth/me → 200', meRes.status, 200)
  eq('⑧ 而它与登录的响应体逐字相同（同一个 SessionIdentityRead + 同一个 _identity_body）',
    meRes.text, loggedIn.text)
  const meAnon = await req('GET', '/api/auth/me')
  eq('⑧ 匿名 GET /api/auth/me → 401', meAnon.status, 401)
  eq('⑧ code 是 unauthenticated', codeOf(meAnon), 'unauthenticated')

  // ⑨ 三档授权（用这一个新教师 = 一个**普通**教师）
  const teacherWrites = await req('POST', '/api/semesters', {
    cookie: freshCookie,
    body: { name: '第 16 步不该建成的学期', start_date: '2027-02-22', end_date: '2027-07-04', weeks: 18 },
  })
  eq('⑨ 普通教师写管理台 → 403', teacherWrites.status, 403)
  eq('⑨ code 是 forbidden', codeOf(teacherWrites), 'forbidden')
  const adminWrites = await req('POST', '/api/teachers', {
    as: 'admin', body: { staff_no: 'SMOKE16B', name: '管理员建的第二个人（马上删）' },
  })
  eq('⑨ 管理员写管理台 → 201', adminWrites.status, 201)
  const adminWritesId = adminWrites.json?.id ?? null
  // ⑩ 学生 cookie 打教师端点 → 403（跨 kind）
  const studentOnTeacher = await req('GET', `/api/teacher/students/${STUDENT}/home?as_of=${AS_OF}`, {
    as: studentJar(STUDENT),
  })
  eq('⑩ 学生 cookie 打教师端点 → 403（不是 401：它已经被认出来了，只是不是那一类人）',
    studentOnTeacher.status, 403)
  eq('⑩ code 是 forbidden', codeOf(studentOnTeacher), 'forbidden')
  const studentOnRoster = await req('GET', '/api/teachers?limit=5', { as: studentJar(STUDENT) })
  check('⑩ 学生 cookie 读名册 → 401 或 403（Plan 05A Task 5 之后它要教职身份）',
    studentOnRoster.status === 401 || studentOnRoster.status === 403,
    `status=${studentOnRoster.status}`)

  // ⑪ 登出 → 204 + cookie 过期，而**旧 cookie 立刻失效**（服务端会话表的全部价值）
  const loggedOut = await req('POST', '/api/auth/logout', { cookie: freshCookie })
  eq('⑪ 登出 → 204', loggedOut.status, 204)
  const clearRaw = (loggedOut.headers.getSetCookie?.() ?? [loggedOut.headers.get('set-cookie')])[0] ?? ''
  check('⑪ 登出的 Set-Cookie 把 pe_session 清掉（Max-Age=0 + expires=1970）',
    /pe_session="";/.test(clearRaw) && clearRaw.includes('Max-Age=0') && clearRaw.includes('1970'),
    clearRaw.slice(0, 120))
  check('⑪ 而它的 Path/SameSite/HttpOnly 与种下时逐字相同（差一个字符就删不掉那一格：'
    + 'RFC 6265 的删除按 (name, domain, path) 三元组匹配）',
    clearRaw.includes('Path=/') && clearRaw.includes('SameSite=lax') && clearRaw.includes('HttpOnly'),
    clearRaw.slice(0, 120))
  const afterLogout = await req('GET', '/api/auth/me', { cookie: freshCookie })
  eq('⑪⚠️ 登出之后**再用那一份旧 cookie** → 401（登出是真的失效，不是客户端把串丢掉）',
    afterLogout.status, 401)
  eq('⑪ code 是 unauthenticated', codeOf(afterLogout), 'unauthenticated')
  const logoutTwice = await req('POST', '/api/auth/logout', { cookie: freshCookie })
  eq('⑪ 重复登出 → 401（先撞 current_session 那道闸门；「幂等」指的是服务端不改坏数据）',
    logoutTwice.status, 401)

  /* ⑫ **subject 已从名册上删掉 → 那一份 cookie 当场失效**（计划 §3.1 逐字点名的
     「本计划最容易漏的一格」）。
     ⚠️ `user_session.subject_id` **刻意不是外键**（它要同时指向 `student.id` 与
     `teacher.id`，而多态外键在 SQL 里不存在），故删一个教师**不会**级联吊销他的
     会话行、`crud._child_tables` 也探测不到它。处置是 `sessions.resolve` 每次
     都回查 subject 行、查无此人就当场吊销。
     ⚠️ 本拍**必须用一个没登出过的 cookie**：⑪ 那一份已经吊销了，
     拿它再测一次会得到一个 401 而什么也没证明（假绿）。故这里另建一个人。 */
  const ghost = await req('POST', '/api/teachers', {
    as: 'admin', body: { staff_no: 'SMOKE16C', name: '第 16 步 ⑫ 用的那个人（马上被删）' },
  })
  eq('⑫ 管理员建第三个人 → 201', ghost.status, 201)
  const ghostId = ghost.json?.id ?? null
  await req('POST', '/api/auth/teachers/bind', {
    body: { staff_no: 'SMOKE16C', name: '第 16 步 ⑫ 用的那个人（马上被删）', password: NEW_PASSWORD },
    quiet: true,
  })
  const ghostLogin = await req('POST', '/api/auth/login', {
    body: { kind: 'teacher', login: 'SMOKE16C', password: NEW_PASSWORD }, quiet: true,
  })
  eq('⑫ 他登录成功 → 200', ghostLogin.status, 200)
  const ghostCookie = cookieFrom(ghostLogin)
  const ghostMe = await req('GET', '/api/auth/me', { cookie: ghostCookie, quiet: true })
  eq('⑫ 删之前 me → 200', ghostMe.status, 200)
  const ghostGone = await req('DELETE', `/api/teachers/${ghostId}`, { as: 'admin' })
  eq('⑫ 管理员把他从名册上删掉 → 204', ghostGone.status, 204)
  const ghostAfter = await req('GET', '/api/auth/me', { cookie: ghostCookie })
  eq('⑫⚠️ 删掉之后**同一份 cookie**（从没登出过）→ 401（resolve 回查 subject + 当场吊销）',
    ghostAfter.status, 401)
  eq('⑫ code 是 unauthenticated', codeOf(ghostAfter), 'unauthenticated')

  // ⑬ 收尾：把本步建的两行删掉（第三行已在 ⑫ 删了）
  const removedA = await req('DELETE', `/api/teachers/${newId}`, { as: 'admin' })
  eq('⑬ 删掉 SMOKE16 → 204', removedA.status, 204)
  const removedB = await req('DELETE', `/api/teachers/${adminWritesId}`, { as: 'admin' })
  eq('⑬ 删掉 SMOKE16B → 204', removedB.status, 204)
  const teachersAfter = await req('GET', '/api/teachers?limit=50', { as: 'admin', quiet: true })
  eq('⑬ 名册回到 3 个教师（本步一行都没留下；⚠️ user_session 的三行会留着，'
    + '它们 2 小时后自己过期，而 subject 已删 → 立刻不可用）',
    teachersAfter.json?.total, 3)

  /* ⑭ ⚠️⚠️ **Plan 06 Task 10 新加的一组：绑定限流**（派单 §2）。
     ⚠️ 改前的形状是一个**真的洞**：绑定用的验身材料是**弱材料**（学生 = 学号 +
     出生日期，教师 = 工号 + 姓名，spec §1.2 第 4 条），而 `bind` 两个端点
     **完全没有限流** —— 一个匿名调用方可以对一个**还没绑定**的账号反复猜出生日期，
     猜中就**抢到**那个账号的口令（而本原型没有口令找回，被抢的人再也进不去）。
     ⚠️ 本波给它接上了 Plan 06 Task 3 那一套机器（所有者 `app/auth/policy.py`、
     存储 `login_attempt`），而**键多了一维「用途」**：与登录共用一个键的话，
     「猜出生日期猜错三次」会把那个账号的**登录**也锁掉 = 把限流变成拒绝服务。
     ⚠️ 阈值另有一组（`PE_BIND_MAX_FAILS` / `PE_BIND_WINDOW_MIN` / `PE_BIND_LOCK_MIN`，
     缺省 **3 / 15 / 60**，⚠️ 一律比登录那一组更严：出生日期只有约 2 900 个可信取值，
     故 5 次 / 锁 15 分钟 = 480 次/天 = 16.5%/天/账号被猜中，3 次 / 锁 60 分钟
     = 72 次/天 = 2.5%/天/账号）。逐字算术住在 `app/auth/policy.py` 的模块 docstring。
     ⚠️⚠️ 本组**一律用一个不在册的假学号**（`SMOKE10BIND`）：它不碰任何真账号，
     于是「把某个演示账号锁 60 分钟」这件事故在本脚本上不可能发生
     （⚠️ 而本组之前那几拍对 `SMOKE16` 只失手过 **1** 次就绑定成功了，
     而成功会**清零**，故它离阈值 3 还差两次 —— 本波没有改掉本步任何一拍的期望值）。
     ⚠️ 五档矩阵 / 交叉不污染 / 定点变异 / 三格可调这四件在**后端**钉得更细
     （`tests/auth/test_policy.py` 第 ⑦ 节 + `tests/api/test_auth_api.py` ①-c 节）；
     本组要的是**产品档**上那三格端到端的证据：锁得住、锁内不可分辨、不污染登录。 */
  const GUESS = 'SMOKE10BIND'
  const guessBody = { student_no: GUESS, birth: '2005-03-04', password: NEW_PASSWORD }
  const g1 = await req('POST', '/api/auth/students/bind', { body: guessBody, quiet: true })
  eq('⑭ 绑定材料不符（不在册）→ 403', g1.status, 403)
  eq('⑭ code 是 forbidden', codeOf(g1), 'forbidden')
  await req('POST', '/api/auth/students/bind', { body: guessBody, quiet: true, record: false })
  const g3 = await req('POST', '/api/auth/students/bind', { body: guessBody, quiet: true, record: false })
  eq('⑭ 第 3 次（= `PE_BIND_MAX_FAILS` 的缺省）仍然 403 —— 它是**最后一次**写行的',
    g3.status, 403)
  eq('⑭ 而它与第 1 次的**响应体原始字节**逐字相同', g3.text, g1.text)
  const g4 = await req('POST', '/api/auth/students/bind', { body: guessBody, quiet: true })
  eq('⑭ 第 4 次 = **锁内** → 仍然 403（⚠️ 不是 423/429：另给一个码就是枚举信号'
    + '「这个标识存在且已被锁」，与 Plan 06 Task 3 对登录那一次的改判同一条理由）',
    g4.status, 403)
  eq('⑭ 锁内那一发的响应体与「材料不符」那一发**逐字相同**（控制者裁定）', g4.text, g1.text)
  eq('⑭ 而 message 也逐字相同（`_BIND_FORBIDDEN_MESSAGE` 是那一句的唯一住址）',
    messageOf(g4), messageOf(g1))
  /* ⚠️ **交叉不污染**（本件最容易做错的一格）：绑定被打锁之后，一个**真**账号的
     登录照旧 200。⚠️ 少了这一拍，「两个用途共用一个键」的实现会让一个匿名调用方
     只要拿别人的学号乱猜出生日期，就能把那个人锁在**自己的账号**外面 ——
     而他自己连提示都得不到（登录锁定档回的是与「口令不正确」逐字相同的 401）。 */
  const stillIn = await req('POST', '/api/auth/login', {
    body: { kind: 'student', login: await studentNoOf(STUDENT), password: DEMO_PASSWORD },
    quiet: true, record: false,
  })
  eq('⑭ **交叉不污染**：绑定被打锁之后，真账号（学生 4）的登录照旧 200'
    + '（限流没有变成拒绝服务）', stillIn.status, 200)
  /* ⚠️ 绿档（硬规矩 #50）：换一个假学号，绑定端点**照旧走得通**（403 = 材料不符那一档，
     而不是「整个端点被锁死」）—— 于是上面那三拍 403 不是因为端点坏了。
     ⚠️ 而「锁是**按标识**的、不是按进程/IP 的」这一格在响应上**不可判定**
     （锁定档与材料不符逐字相同，那正是裁定要的），故它由后端那两条守卫钉：
     `test_the_lock_is_per_identity_not_per_process`（登录侧，既有）与
     `test_a_bind_lock_does_not_lock_the_same_persons_login_and_vice_versa`（绑定侧，本波）。 */
  const otherGuess = await req('POST', '/api/auth/students/bind', {
    body: { ...guessBody, student_no: 'SMOKE10BIND2' }, quiet: true, record: false,
  })
  eq('⑭ 换一个假学号：绑定端点**没有**被整个锁死（锁是按标识的）', otherGuess.status, 403)
})

/* ------------------------------------------------------------------ 第 17 步
   ⚠️⚠️ **终审 fix 波新增的一步：4 条不需要浏览器的守卫**（I2 / I4 / M1 / M5），
   **Plan 06 Task 11 又加了 2 条**（⑤ B3 / ⑥ B5，同样是「不需要浏览器」那一族）。
   前 17 步（0–16）验的是「后端与前端对接得上」；本步验的是**账面不得与代码打架** ——
   那 4 条的共同形状是「一句写死的话与真实值漂开了」，而它们各自**都没有守卫**
   （这正是它们能活到今天的原因，与 I1 那个假学号同族）。
   ⚠️ Task 11 加的那两条形状不同：它们钉的是**两处结构纪律**
   （⑤ 产品档也强制关掉请求头身份通道、⑥ 路由树里静态段必须声明在带参段之前），
   而两者此前的失效方向都是**静默**的（⑤ 是「绕过整个鉴权」、⑥ 是「一页管理台
   显示成一个叫 audit-logs 的资源」——不是白屏，很难查）。

   ⚠️ 与第 15 步一样，本步**不需要前端起着**；而 ① 那一拍要
   **PowerShell 与 Python**（它 spawn 一次 `backend/scripts/demo.ps1 -DryRun`，约 15 秒，
   库与 CSV 都落在 `$env:TEMP`、跑完自己删掉，故它不脏演示库、也不碰两个禁区）。
   ⚠️⚠️ 而「**不需要后端起着**」那半句自 Plan 06 Task 11 起**只对 ①–⑥ 成立**：
   ⑤ 那一拍要 spawn 一次 `scripts/serve.ps1 -SkipBuild`（⚠️ 让它停在起子进程之前的
   办法是**先用一个 `net.Server` 把一个端口占住**、再把那个端口交给 `-Port`，于是它
   throw 在 ③d 那一道端口预检上、**一个 uvicorn 都不起**；⚠️ 本处改前逐字写的是
   「用一个认不出的 `PE_ENV` 让它 throw」，而那一条路**下面 ⑤ 的注释里已经写明踩过坑**：
   `serve.ps1` 的 ③a 那一次 `python -c 'from app.main import DEMO_DB_URL'` 会更早炸掉，
   脚本停在强制清**之前**、探针红在自己身上 —— Plan 06 Task 13 把本句改成与代码一致），
   ⑦ 那一拍的 ③④ 两拍要打真端点（`limit=200` 与 `limit=1` 各一遍）。
   如实记，不改那两拍的形状。⚠️ 两次 spawn 的墙钟与「要什么起着」的逐拍清单
   见**本文件头**的「第 17 步的前置条件与耗时」那一节（Plan 06 Task 13 / D8）。
   ⚠️ 四拍各自都带**反例/非空转**那一边（硬规矩 #50 / #107）：一条「0 处 offender」
   的断言，若不同时证明「谓词对已知反例确实会报」，那它与「谓词写坏了」在输出上
   是同一个样子。 */
await step(17, '静态守卫 10 条：demo.ps1 强制关掉身份头开关 / toPlainText / surface 字面值 / 破折号的唯一住址 / serve.ps1 也强制关（B3） / router 的静态段必须排在 :resource 之前（B5） / 单页取值不许静默截断（B4） / 会话恢复那一帧的结构面（C3）+ 那一次问后端**有上限**（Task 15 / 终审 S3-⑤） / 试用告示的唯一住址与「读不到就不挂」（Plan 07 Task 1） / 原生校验拦下 submit 时不许静默 + `step` 的口径不许被前端发明第二次（Plan 07 Task 5b）', async () => {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const repoRoot = path.resolve(here, '../..')
  const frontendRoot = path.resolve(here, '..')

  /* ① 终审 I2：demo.ps1 对 PE_ALLOW_HEADER_IDENTITY 必须**强制**、不能只声明。
     ⚠️ 改前的形状：`demo.ps1` 只设 PE_DB_URL / PE_CSV_DIR，全文没有一行删它，
     而 139 与 185-186 两处都是**无条件** Write-Host「未设」。于是在一个
     `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 的 shell 里跑它，会得到一个**认伪造请求头**
     的 uvicorn，而脚本两次告诉用户相反的话 —— 恰好把 `deps.py` 那条「失效方向是
     安全的」性质反转成了静默打开。 */
  {
    const ps1 = path.join(repoRoot, 'backend', 'scripts', 'demo.ps1')
    check('① demo.ps1 存在', fs.existsSync(ps1), ps1)
    const bytes = fs.readFileSync(ps1)
    const src = bytes.toString('utf8')
    // --- 源码面：机制在不在，以及它的两个字节级前提 ---
    check('① 源码里真的有那一行强制（Remove-Item Env:\\PE_ALLOW_HEADER_IDENTITY）',
      src.includes('Remove-Item Env:\\PE_ALLOW_HEADER_IDENTITY'), '')
    check('① 而它仍是 UTF-8 **带 BOM**（IDE 的编辑工具吃过它两次；PowerShell 5.1 会把无 BOM 的中文 .ps1 按 ANSI 静默乱码）',
      bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf,
      `前 3 字节 = ${[...bytes.subarray(0, 3)].map((b) => b.toString(16)).join(' ')}`)
    const nCrlf = (src.match(/\r\n/g) ?? []).length
    const nLf = (src.match(/\n/g) ?? []).length
    check('① 而它仍是纯 CRLF（0 个裸 LF）', nCrlf === nLf, `CRLF ${nCrlf} / LF ${nLf}`)
    // --- 行为面：在一个 =1 的 shell 里跑 -DryRun ---
    const run = spawnSync('powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1, '-DryRun'],
      {
        encoding: 'utf8',
        cwd: path.join(repoRoot, 'backend'),
        env: { ...process.env, PE_ALLOW_HEADER_IDENTITY: '1' },
      })
    const stdout = `${run.stdout ?? ''}${run.stderr ?? ''}`
    const line = stdout.split(/\r?\n/).find((l) => l.includes('PE_ALLOW_HEADER_IDENTITY 进本脚本时实测')) ?? ''
    out('    在 PE_ALLOW_HEADER_IDENTITY=1 的 shell 里跑 -DryRun，它打印的是：')
    out(`    ${line.trim()}`)
    eq('① 退出码 0（它没 throw，也没炸）', run.status, 0)
    check('① 它打印的是**实测值 =1**（改前那一句无条件写的是「未设」）',
      line.includes('=1'), JSON.stringify(line.trim()))
    check('① 而它同时说清本进程已被清成「未设」（= 生产缺省 "0"）',
      line.includes('未设'), JSON.stringify(line.trim()))
    check('① 改前那句无条件的假话在整份输出里 0 次',
      !stdout.includes('PE_ALLOW_HEADER_IDENTITY 未设（= 生产缺省'), '')
    check('① 反例（非空转）：本文件确实在讲这个开关（needle 家族还在），'
      + '而那句无条件的假话在**源码**里也是 0 次',
      src.includes('PE_ALLOW_HEADER_IDENTITY')
        && !src.includes('PE_ALLOW_HEADER_IDENTITY 未设（= 生产缺省'), '')
    check('① 而这条链真的走完了（打印了 [7/7] 的复核与禁区那一行）',
      stdout.includes('[7/7]') && stdout.includes('禁区复核'), `stdout ${stdout.length} 字符`)
  }

  /* ② 终审 I4：`toPlainText` 不给 CSS/JS 注释留假出口。 */
  {
    // ⚠️ 终审复现用的那一份最小 HTML：needle「的本周」只出现在 style 的注释里。
    const CSS_ONLY = '<style>/* 首页的本周训练量、大屏的关键指标 */ .num--hero{}</style>'
    const NEEDLE = '的本周'
    /** 改前 `dumpRoute` 轮询里那一份**弱剥**（只剥标签，style/script 的文本留着）。 */
    const weak = (h) => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
    check('② 反例（硬规矩 #107）：弱剥**会**被骗（于是旧轮询会在第一拍就 break）',
      weak(CSS_ONLY).includes(NEEDLE) || CSS_ONLY.includes(NEEDLE), '')
    check('② 而 toPlainText **不会**被骗 —— 轮询因此不会在第一拍 break',
      !toPlainText(CSS_ONLY).includes(NEEDLE), JSON.stringify(toPlainText(CSS_ONLY)))
    const GOOD = `${CSS_ONLY}<main><h1>赵婉清 的本周训练量</h1></main>`
    check('② 正例：needle 在真正文里时 toPlainText **会**命中（谓词不是恒假）',
      toPlainText(GOOD).includes(NEEDLE) && toPlainText(GOOD).includes('赵婉清'), '')
    check('② script 里的文本同样被剥掉（两半都是承重的）',
      !toPlainText('<script>const a = "训练量"</script><p>别的东西</p>').includes('训练量'), '')
    // --- 源码面：那一个假出口不得再出现在**代码**里 ---
    /** 剥 JS 注释：块注释整块挖空（保留换行故行号不变）、整行的 `//` 注释挖空。
     *  ⚠️ 刻意**不**剥行尾的 `//`：那会把 `http://` 一类串也咬掉。 */
    const stripJsComments = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const selfSrc = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8')
    const codeOnly = stripJsComments(selfSrc)
    // ⚠️⚠️ **needle 必须拼出来、不能写成字面量**（硬规矩 #109，首跑实测到的自我命中）：
    //    这一拍的标签与谓词里若直接写那个串，它自己就是一处**代码里**的出现，
    //    于是「代码里 0 次」当场红在自己身上。故拆成两半再 `join('')`。
    const FAKE_EXIT = ['|| html.', 'includes(n)'].join('')
    check(`② ${FAKE_EXIT} 那个假出口不再出现在本文件的**代码**里（只允许出现在注释里）`,
      !codeOnly.includes(FAKE_EXIT), '')
    check('② 反例（两个方向都验，硬规矩 #109 + #50）：那几处提及**全在注释里**（故原文有、'
      + '剥完没有），而两处只在**代码**里的串剥完仍在 —— 少了后半句，「剥完没有」'
      + '可能只是剥注释的谓词把整份文件都咬掉了（⚠️ 本谓词是**挖空**成空格、长度不变，'
      + '故「长度还很大」证明不了任何事，首跑就是这么写错的）',
      selfSrc.split(FAKE_EXIT).length - 1 >= 1
        && codeOnly.includes('function toPlainText(html)')
        && codeOnly.includes('await step(17,'),
      `原文 ${selfSrc.split(FAKE_EXIT).length - 1} 处提及，剥注释后 0 处`)

    /* --- S4-15（Plan 07 Task 8 **修**）：needle 不许写**转义形式**（`&lt;` / `&gt;` /
       `&amp;` / `&nbsp;`）—— `toPlainText` 本波起反转义了，它的返回值里那四个串
       一个都不会再出现，故那种 needle 永远匹配不上。
       ⚠️ 这一格与改前恰好**互为镜像**：改前危险的是「needle 含**裸** `<` / `>` / `&`」，
       改后危险的是「needle 含**转义形式**」，而两者是同一个笔误的两半。
       ⚠️ 失效方向仍然只有一档是静默的：**反向**断言永绿、正向断言永红（会被发现）。
       ⚠️ **判据（控制者裁定「判据你定并说明」，逐字交代）**：扫本文件**剥完注释**的
       源码（`codeOnly`）里全部 `.includes(` / `.indexOf(` / `.split(` / `.startsWith(` /
       `.endsWith(` 调用的第一个**字面量**实参，凡命中 `&(lt|gt|amp|nbsp);` 一律违规
       —— ⚠️ **正反两向一起禁**（改前那一版刻意只扫反向）。理由：正向那一档虽然只会
       永红（响亮），但它是**同一个笔误**，禁在一起才是一条口径而不是一条半；⚠️ 而它
       今天**不误报**（本波实测正反两向的命中都是 **0**），故不是「拿一条恒真的守卫换
       一个假的安全感」（硬规矩 #50 那一档只在**会误报**时才成立）。
       ⚠️ **本波实测的扫描面与命中数**：字面量 needle **137** 处（其中反向 **19** 处、
       反向调用一共 **33** 处），含转义形式的 **0** 处 ⇒ **误报 0**。
       ⚠️ 另有若干 needle 是**动态**的（模板串/变量），本拍**看不到** ⇒ 如实记：
       这一格是「尽力」而不是「穷尽」，穷尽要一个 JS AST（本仓刻意不引依赖）。
       ⚠️ ②′′ 那两个下界（100 / 15）刻意取得比实测值（137 / 19）**松一格**：它们是
       「扫描面没被写空」的判据，不是「一处都不许增删」的变更探测器（硬规矩 #35 的
       那一侧：下界取紧了就变成一条易假红的守卫）。
       ⚠️ 扫描面是 `codeOnly`，故本段注释与 `toPlainText` 函数体里那些实体串
       不会被自己数进去（硬规矩 #109）。 */
    const LITERAL_NEEDLE = /\.\s*(?:includes|indexOf|split|startsWith|endsWith)\s*\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)/g
    const NEGATED_CALL = /!\s*[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*|\s*\[[^\]]*\]|\s*\([^)]*\))*\s*\.\s*(?:includes|indexOf)\s*\(/g
    const NEGATED_LITERAL = /!\s*[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*|\s*\[[^\]]*\]|\s*\([^)]*\))*\s*\.\s*(?:includes|indexOf)\s*\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)/g
    const ENTITY_FORM = /&(?:lt|gt|amp|nbsp);/
    const needles = [...codeOnly.matchAll(LITERAL_NEEDLE)]
      .map((m) => (m[1] ?? m[2] ?? m[3] ?? ''))
    const negatedAll = [...codeOnly.matchAll(NEGATED_CALL)]
    const negatedNeedles = [...codeOnly.matchAll(NEGATED_LITERAL)]
      .map((m) => (m[1] ?? m[2] ?? m[3] ?? ''))
    const offenders = needles.filter((n) => ENTITY_FORM.test(n))
    check('②′ S4-15：字面量 needle 不许写**转义形式**（`&lt;` / `&gt;` / `&amp;` / '
      + '`&nbsp;`）—— `toPlainText` 本波起反转义了，它的返回值里那四个串一个都不会有，'
      + '故那种 needle 永远匹配不上（**反向**断言因此永绿 = 静默；正向断言只会永红）',
    offenders.length === 0, JSON.stringify(offenders))
    check('②′′ 反空转：②′ 那一拍**真的扫到了东西**（本文件今天有 ≥ 100 处字面量 '
      + 'needle、≥ 15 处反向调用、≥ 15 处反向且字面；⚠️ 少了这一拍，「把整个扫描面'
      + '写错成一个空集」也能绿）',
    needles.length >= 100 && negatedAll.length >= 15 && negatedNeedles.length >= 15,
    `字面 needle ${needles.length} 处 / 反向调用 ${negatedAll.length} 处`
      + ` / 其中反向且字面 ${negatedNeedles.length} 处`)
    /* ②′′′ 反空转之二：`toPlainText` 那四步反转义**真的在**。⚠️ **少了这四拍，「把
       反转义整段删掉」也能全绿** —— 因为今天没有一条 needle 含那四个字符（上面实测），
       删掉它一条断言都不会红；这正是终审 S4-15 说的「潜伏」那一档 ⇒ 守卫必须打在
       **函数本身**上，不能只打在 needle 上（硬规矩 #50：一条恒真的守卫与一条真的守卫
       在颜色上无法区分）。⚠️ 第 3 拍钉的是 `&amp;` **必须最后**替换：`&amp;lt;` 只解
       一层成 `&lt;`（解两次就成 `<`，凭空造出一个假标签）。⚠️ 第 4 拍钉的是
       `&nbsp;` → U+00A0 → 再被最后那一步压成一个普通空格（`src/**` 与 `dist` 今天
       实测 **0** 处，而它是序列化算法会产生的第四个实体，故一并钉住、免得更下一个
       人再查一遍）。⚠️ 四拍的 receiver 都是**合成的**串、不打后端 ⇒ 不需要任何服务
       起着，也不需要浏览器。 */
    /* ⚠️ 期望值首尾各**一个空格**：本函数把标签换成空格而**刻意不 trim**
       （`includes` 判据下首尾空白不影响任何一条断言，而 trim 会是一格没人要的行为改动）。
       ⚠️ 这一格是本波**首跑真抓到的**：写这拍时照着「→ `a>b`」想当然，dev 档首跑
       就红在 `actual= a>b`（看着一样、差在首尾那两个空格上）⇒ 期望值改成实测值，
       ⚠️ 而**不是**给 `toPlainText` 加一个 `.trim()`（那会动四档全部断言的公共所有者）。 */
    eq('②′′′ 反转义真的在：`<p>a&gt;b</p>` → ` a>b `（标签换成空格故首尾各留一个、'
      + '本函数刻意不 trim；`&gt;` 解成 `>`）',
      toPlainText('<p>a&gt;b</p>'), ' a>b ')
    eq('②′′′ 反转义真的在：`a &amp; b` → `a & b`', toPlainText('a &amp; b'), 'a & b')
    eq('②′′′ `&amp;` 必须**最后**替换：`&amp;lt;` 只解一层 → `&lt;`（解两次会凭空造出'
      + '一个假标签）', toPlainText('&amp;lt;'), '&lt;')
    eq('②′′′ 第四个实体：`a&nbsp;b` → `a b`（U+00A0 被最后那一步的空白压缩收成一个'
      + '普通空格）', toPlainText('a&nbsp;b'), 'a b')
  }

  /* ③ 终审 M1 + 待清扫波：`meta.surface` 的字面值只有 base / board 两个 ——
        那两个撒谎的旧名字（`paper` / `ink`）不得回流。 */
  {
    /** 剥注释（JS 块注释 + 整行 `//` + HTML 注释），挖空成空格故行号/长度不变。
     *  ⚠️ 这一格**必须**先剥注释（硬规矩 #109）：M1/M2 的改动说明与待清扫波的改名
     *  说明里都逐字引用了旧字面值，首跑实测 App.vue 因此匹配到 3 处而不是 1 处 ——
     *  三处同值故那一拍仍然绿，而它数的其实是「代码 1 处 + 提及 2 处」。 */
    const stripSrcComments = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const routerSrc = stripSrcComments(fs.readFileSync(path.join(frontendRoot, 'src/router/index.ts'), 'utf8'))
    const appSrc = stripSrcComments(fs.readFileSync(path.join(frontendRoot, 'src/App.vue'), 'utf8'))
    const sectionHeadSrc = fs.readFileSync(path.join(frontendRoot, 'src/components/SectionHead.vue'), 'utf8')
    const routerLiterals = [...routerSrc.matchAll(/\bsurface:\s*'([^']+)'/g)].map((m) => m[1])
    const appLiterals = [...appSrc.matchAll(/meta\.surface\s*===\s*'([^']+)'/g)].map((m) => m[1])
    const ALLOWED = new Set(['base', 'board'])
    /** 待清扫波改名之前的那两个值（`ink` = 墨，大屏翻浅底之后它会撒谎）。 */
    const RENAMED_AWAY = ['paper', 'ink']
    out(`    router/index.ts 的**代码**里设的 surface 字面值 = ${JSON.stringify(routerLiterals)}`)
    out(`    App.vue 的**代码**里比的 surface 字面值        = ${JSON.stringify(appLiterals)}`)
    check('③ router/index.ts 设的每一个都在 {base, board} 里（非空转：≥ 1 个）',
      routerLiterals.length >= 1 && routerLiterals.every((v) => ALLOWED.has(v)), JSON.stringify(routerLiterals))
    check('③ App.vue 比的每一个都在 {base, board} 里（非空转：**恰好 1 个** —— M2 删掉死支之后只剩那一处）',
      appLiterals.length === 1 && appLiterals.every((v) => ALLOWED.has(v)), JSON.stringify(appLiterals))
    check('③ 而改名之前的那两个值（paper / ink）**不再**是 meta.surface 的字面值'
      + '（待清扫波：ink = 墨，大屏翻浅底之后它会撒谎）',
      RENAMED_AWAY.every((v) => !routerLiterals.includes(v) && !appLiterals.includes(v)),
      JSON.stringify({ routerLiterals, appLiterals }))
    // ⚠️ 反例（硬规矩 #109 + #50）：`'board'` 这个词**同时**是组件 `tone` 那个 prop 的
    //    字面值（`tone?: 'paper' | 'board'`），与 `meta.surface` 是**两根轴** ——
    //    那是 fix 波顶回终审「'board' 全仓不存在」那一条时钉下来的事实。
    //    ⚠️ 改名之后两根轴**共用** `'board'` 这个词（此前它们共用的是 `'paper'`），
    //    故「grep 到 'board'」判定不了任何事；少了这一拍，上面那条「旧名字不回流」
    //    可能被读成「'board' 是本波新发明的词」。
    check("③ 反例：'board' 也是组件 tone 的字面值（另一根轴；两根轴共用这个词，故不能靠 grep 它判定任何事）",
      /tone\?:\s*'paper'\s*\|\s*'board'/.test(sectionHeadSrc), '')
  }

  /* ④ 终审 M5：那个「不知道」的破折号只有一个住址（`src/present.ts` 的 UNKNOWN）。 */
  {
    const DASH = '—'
    /** 剥注释（与 check-tokens.mjs 同口径）：挖空但保留换行，故行号仍对得上。 */
    const stripComments = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
    /** 引号（单/双/反引号）里包着的**单个** U+2014。⚠️ 中文破折号「——」是散文标点、
     *  不是那个占位符，故两侧都排除掉它自己。 */
    const quotedDash = () => /(['"`])(?<!—)—(?!—)\1/g
    const walk = function* (dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) yield* walk(full)
        else yield full
      }
    }
    const offenders = []
    let scanned = 0
    for (const file of walk(path.join(frontendRoot, 'src'))) {
      if (!file.endsWith('.vue')) continue
      scanned += 1
      const code = stripComments(fs.readFileSync(file, 'utf8'))
      code.split(/\r?\n/).forEach((lineText, i) => {
        for (const m of lineText.matchAll(quotedDash())) {
          offenders.push(`${path.relative(frontendRoot, file)}:${i + 1} ${m[0]}`)
        }
      })
    }
    out(`    扫了 ${scanned} 个 .vue 文件，代码里引号包着的「${DASH}」共 ${offenders.length} 处`)
    check('④ 守卫不空转：扫到了 ≥ 20 个 .vue 文件', scanned >= 20, `${scanned} 个`)
    check('④ 反例：谓词**会**命中一处硬编码（硬规矩 #107）',
      [...`{{ a ?? '${DASH}' }}`.matchAll(quotedDash())].length === 1, '')
    const DASH_CONTROL = "const s = '——'"
    check('④ 反例：而它**不**命中引号里的中文破折号「——」（那是散文标点，不是那个占位符）',
      [...DASH_CONTROL.matchAll(quotedDash())].length === 0, DASH_CONTROL)
    check(`④ src/**/*.vue 的**代码**里 0 处引号包着的「${DASH}」（唯一住址是 present.ts 的 UNKNOWN）`,
      offenders.length === 0, JSON.stringify(offenders))
    const presentSrc = fs.readFileSync(path.join(frontendRoot, 'src/present.ts'), 'utf8')
    check('④ 而那个唯一住址**还在**（否则「0 处」可能只是所有者也被删了）',
      /export const UNKNOWN = '—'/.test(presentSrc), '')
    /* ------------------------------------------------------ 待清扫波（清4）新增两拍
       **模板文本节点**里的那一族也归到 UNKNOWN 这一个住址。
       ⚠️ 改前实测（**不是** fix 波记的「约 30 处 / 散在 10 个 .vue」—— 那两个数都不对，
       硬规矩 #111）：**27 处 / 7 个 .vue**（StudentDetail 14 · AlertQueue 4 · MiniTest 4 ·
       Notifications 2 · StatBlock 1 · CheckIn 1 · ClassReport 1），而 27 处**全部**是
       `<span class="unknown">…</span>` 这一个形状、语义一律是「不知道 / 无数据」；
       破折号与范围符（`A—B`）实测 **0 处**，故 27 处**全换**、没有一处保留。
       ⚠️ 代价也比 fix 波估的小一档：7 个文件里 **6 个本来就 import 了 UNKNOWN**
       （fix 波自己换那 12 个字面量时加的），只有 `components/StatBlock.vue` 需要
       新加一行 import。渲染结果逐字不变（`UNKNOWN === '—'`），故第 14 步那 16 条
       路由的重叠/溢出守卫与 needle 断言都不受影响。 */
    const TEXT_DASH = `>${DASH}<`
    const textNodes = []
    for (const file of walk(path.join(frontendRoot, 'src'))) {
      if (!file.endsWith('.vue')) continue
      const code = stripComments(fs.readFileSync(file, 'utf8'))
      code.split(/\r?\n/).forEach((lineText, i) => {
        let at = -1
        while ((at = lineText.indexOf(TEXT_DASH, at + 1)) !== -1) {
          textNodes.push(`${path.relative(frontendRoot, file)}:${i + 1}`)
        }
      })
    }
    out(`    模板文本节点 ${TEXT_DASH} 共 ${textNodes.length} 处（清4 之后应当是 0）`)
    check(`④ src/**/*.vue 的**模板文本节点**里 0 处 ${TEXT_DASH}（清4：27 处全部换成 {{ UNKNOWN }}）`,
      textNodes.length === 0, JSON.stringify(textNodes))
    // ⚠️ 反例（硬规矩 #107）：谓词**会**命中一处硬编码的模板文本节点。
    //    needle 一律拼出来、不写成字面量（#109）：本谓词只扫 src/**/*.vue、扫不到
    //    scripts/ 下的本文件，但同一档纪律照办（上一拍那个 FAKE_EXIT 就是这么写的）。
    const TEXT_NODE_COUNTER = ['<span class="unknown">', '</span>'].join(DASH)
    check('④ 反例：谓词**会**命中一处硬编码的模板文本节点（硬规矩 #107）',
      TEXT_NODE_COUNTER.split(TEXT_DASH).length - 1 === 1, TEXT_NODE_COUNTER)
  }

  /* ⑤ Plan 06 Task 11 / B3：**产品档也强制关掉请求头身份通道**（改前 serve.ps1 只
        打印实测值 + 一句 ⚠️「本脚本不替你清掉它……开关归运维」）。
     ⚠️ 那一句话前半句对、后半句危险：产品档**缺省留在 dev 档**（Task 7 的裁定：
     同源 http 上跑 prod 档，浏览器会拒收 Secure cookie），而
     `allow_header_identity()` **只在 PE_ENV=prod 下恒回 False** —— 于是
     「dev 档 + 运维不小心设了那个变量」= 请求头身份通道开着 = **绕过整个鉴权**
     （X-Student-Id / X-Teacher-Staff-No 没有签名、没有过期、没有吊销）。
     ⚠️ 与 ① 同一条姿势：源码面 + **行为面**各一拍，且**不写第二套** ——
     那一段是从 demo.ps1 里现场切出来逐字比对的（期望侧是 demo.ps1 的文件内容）。
     ⚠️ 行为面怎么在**不起服务**的前提下跑它：**先把一个端口占住**（下面用一个
     `net.Server` 监听 0 号端口、拿它实际分到的那一个），再把那个端口交给 `-Port`。
     `serve.ps1` 的 ③d 那一道端口预检排在强制清（③b2）**之后**、起子进程（③e）
     **之前**，故它一定先打印强制清那一行、再 throw、且一个 uvicorn 都不起。
     ⚠️ 首跑实测踩过另一条路：给它一个认不出的 `PE_ENV`、想让它停在 ③c（档位自检），
     而 ③a 那一次 `python -c 'from app.main import DEMO_DB_URL'` **更早就炸了**
     （`import app.main` → 模块级 `create_app()` → `deploy.tier()` 抛 ValueError），
     于是脚本停在强制清**之前**、那一行压根没打印 —— 探针红在自己身上。 */
  {
    const ps1 = path.join(repoRoot, 'scripts', 'serve.ps1')
    check('⑤ serve.ps1 存在（仓库根的 scripts\\，不是 backend\\scripts\\）',
      fs.existsSync(ps1), ps1)
    const bytes = fs.readFileSync(ps1)
    const src = bytes.toString('utf8')
    const NEEDLE = ['Remove-Item Env:\\', 'PE_ALLOW_HEADER_IDENTITY'].join('')
    check('⑤ 源码里真的有那一行强制（' + NEEDLE + '）', src.includes(NEEDLE), '')
    const nCrlf = (src.match(/\r\n/g) ?? []).length
    const nLf = (src.match(/\n/g) ?? []).length
    check('⑤ 而它仍是 UTF-8 **带 BOM** + 纯 CRLF（前几波被工具剥过三次 BOM）',
      bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf && nCrlf === nLf,
      `BOM ${bytes[0] === 0xef} / CRLF ${nCrlf} / LF ${nLf}`)
    // --- 源码面 · 逐字同款（单一所有者是 demo.ps1）---
    const demoSrc = fs.readFileSync(path.join(repoRoot, 'backend', 'scripts', 'demo.ps1'), 'utf8')
    const START = '$HeaderIdentityInherited = [Environment]::GetEnvironmentVariable'
    const END = "{ '未设' } else { '=' + $HeaderIdentityNow }"
    const from = demoSrc.indexOf(START)
    const to = demoSrc.indexOf(END, from)
    check('⑤ 非空转：从 demo.ps1 里切得出那一段', from >= 0 && to > from, `${from}/${to}`)
    const canon = demoSrc.slice(from, to + END.length)
    check('⑤ 而那一段（' + canon.length + ' 字符）在 serve.ps1 里**逐字**在 —— '
      + '不写第二套，故两份漂了当场红', canon.length > 200 && src.includes(canon), '')
    check('⑤ 改前那句「开关归运维」不再出现在**语句**里（⚠️ 注释里逐字引用了它来说明'
      + '为什么改判，而提及不是本身，硬规矩 #109）',
      !src.split(/\r?\n/)
        .filter((l) => !l.trim().startsWith('#'))
        .join('\n')
        .includes('开关归运维'), '')
    // --- 行为面：在一个 =1 的 shell 里跑它（先把一个端口占住，让它停在 ③d）---
    const { createServer } = await import('node:net')
    const squatter = createServer()
    await new Promise((resolve) => squatter.listen(0, '127.0.0.1', resolve))
    const busyPort = squatter.address().port
    out('    先占住 127.0.0.1:' + busyPort + '，再把它交给 -Port（于是脚本会停在 ③d 的端口预检、一个 uvicorn 都不起）')
    const run = spawnSync('powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1,
        '-Port', String(busyPort), '-SkipBuild'],
      {
        encoding: 'utf8',
        cwd: repoRoot,
        env: { ...process.env, PE_ALLOW_HEADER_IDENTITY: '1' },
      })
    await new Promise((resolve) => squatter.close(resolve))
    const stdout = `${run.stdout ?? ''}${run.stderr ?? ''}`
    const line = stdout.split(/\r?\n/)
      .find((l) => l.includes('PE_ALLOW_HEADER_IDENTITY 进本脚本时实测')) ?? ''
    out('    在 PE_ALLOW_HEADER_IDENTITY=1 + 一个认不出的 PE_ENV 下跑它，它打印的是：')
    out(`    ${line.trim()}`)
    check('⑤ 它打印的是**实测值 =1**（改前只打印、不清）', line.includes('=1'),
      JSON.stringify(line.trim()))
    check('⑤ 而它同时说清本进程已被**强制**清成「未设」且请求头通道**已关闭**',
      line.includes('强制') && line.includes('未设') && line.includes('已关闭'),
      JSON.stringify(line.trim()))
    check('⑤ 它随后在**起子进程之前**就 throw 了（退出码非 0 ⇒ 一个端口都没占）',
      run.status !== 0, `退出码 ${run.status}`)
    check('⑤ 而 throw 的正是 ③d 那一道**端口预检**（= 强制清排在它之前，'
      + '故那一行已经打印过了；⚠️ 而它排在 ③e 起子进程之前，故一个 uvicorn 都没起）',
      stdout.includes('已经被占着'), stdout.slice(-260))
    /* ⚠️ 如实记（硬规矩 #39）：本拍证明的是「**脚本进程**里那个变量被清掉了」，
       而「起来的服务上请求头通道真的是关的」那一格是**跨进程**的，本步不验它
       （验它要真起一个 uvicorn，而第 0–16 步已经在用两个端口了）。
       那一格的取证住在 Task 11 的实现者报告里：真起一次产品档、真发三发请求
       （X-Student-Id / X-Teacher-Staff-No: T0001 / X-Teacher-Staff-No: T0003）
       一律 **401 unauthenticated**，而同一时刻真 cookie 那一档照常 **200**。
       ⚠️ 而「子进程继承的是本进程**当时**的环境块」这一格由后端那条守卫钉：
       `tests/test_serve.py` 的
       `test_serve_ps1_force_clears_the_header_identity_channel_with_the_same_lines_demo_ps1_uses`
       第 ③ 拍断言那一次 Remove-Item 排在 Start-Process **之前**。 */
  }

  /* ⑥ Plan 06 Task 11 / B5：**同一父段下「一个静态、一个带参」的路由，
        静态的那一条必须声明在带参的那一条之前。**
     ⚠️ 它收的是 Task 9 登记的一条：`/admin/audit-logs` 必须排在 `/admin/:resource`
     之前，而**改前没有任何守卫钉住这个顺序**。下一次有人加一页管理台页面并把它排在
     `:resource` 之后，那页会被 `:resource` 吃掉 —— 而失效形态是「页面显示成一个叫
     audit-logs 的资源」（`ResourceList.vue` 的 UNKNOWN RESOURCE 那一屏），
     **不是白屏**，很难归因。
     ⚠️⚠️ 相撞面**不是**手写清单：它用 **Vue Router 自己的匹配器**算出来 ——
     对每一对 (i 静态, j 带参)，建一个**只有 j 一条路由**的 memory-history router，
     问它「i 那个路径命中你吗」。于是「什么叫会被吃掉」这件事只有一个所有者
     （vue-router 的打分/匹配实现），本拍不自作主张写一份正则。
     ⚠️ 而**顺序**那一格必须另外断：vue-router 4 按「静态段 > 动态段」打分，
     故整棵树建起来之后 `resolve()` 命中的**永远**是静态那一条 —— 也就是说
     「解析结果对」证明不了「声明顺序对」，而后者才是读代码时能回答「谁先匹配」
     的那一格（`src/router/index.ts` 的注释逐字写着这个理由）。两拍因此都在。 */
  {
    const { createRouter, createMemoryHistory } = await import('vue-router')
    const stripSrcComments = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const routerSrc = stripSrcComments(
      fs.readFileSync(path.join(frontendRoot, 'src/router/index.ts'), 'utf8'))
    const at = routerSrc.indexOf('const routes: RouteRecordRaw[] = [')
    check('⑥ 非空转：找得到那个 routes 数组', at >= 0, `${at}`)
    const block = routerSrc.slice(at, routerSrc.indexOf('\n]', at) + 2)
    /** `routes` 数组里的 path 字面量，**顺序就是声明顺序**（本拍要判的正是它）。 */
    const paths = [...block.matchAll(/\bpath:\s*'([^']+)'/g)].map((m) => m[1])
    eq('⑥ routes 数组里的 path 字面量条数（⚠️ 比第 14 步那 16 条**渲染**路由多 4 条：'
      + '/s 与 /t 两条重定向、/ 那条 root、以及 /:pathMatch(.*)* 那条兜底）',
    paths.length, 20)
    const isStatic = (p) => !p.includes(':')
    const mk = (list) => createRouter({
      history: createMemoryHistory(),
      routes: list.map((p, k) => ({ path: p, name: `r${k}`, component: { render: () => null } })),
    })
    /** 相撞面：[静态那条的下标, 带参那条的下标]。
     *  ⚠️ 静音 `console.warn`：一个「只有 j 一条路由」的 router 去 resolve 别的路径，
     *  **不命中就是它要的答案**，而 vue-router 会为每一次不命中打一条
     *  `[Vue Router warn]: No match found for location with path …`（实测 96 条）。
     *  那些警告是本拍的**正常工作产物**、不是异常，故就地吞掉、出了这段再还原。 */
    const collisions = []
    const realWarn = console.warn
    console.warn = () => {}
    try {
      for (let i = 0; i < paths.length; i += 1) {
        if (!isStatic(paths[i])) continue
        for (let j = 0; j < paths.length; j += 1) {
          if (i === j || isStatic(paths[j])) continue
          if (mk([paths[j]]).resolve(paths[i]).name === 'r0') collisions.push([i, j])
        }
      }
    } finally {
      console.warn = realWarn
    }
    out(`    相撞面 ${collisions.length} 对（左 = 静态，右 = 会吃掉它的带参路由）：`)
    for (const [i, j] of collisions) {
      out(`      [${String(i).padStart(2)}] ${paths[i].padEnd(28)} ←会被← [${String(j).padStart(2)}] ${paths[j]}`)
    }
    check('⑥ 非空转：相撞面 ≥ 2 对，且**包含** (/admin/audit-logs, /admin/:resource) 那一对'
      + '（少了它，「0 处倒序」可能只是相撞面根本没算出来）',
    collisions.length >= 2
        && collisions.some(([i, j]) => paths[i] === '/admin/audit-logs'
          && paths[j] === '/admin/:resource'), `${collisions.length} 对`)
    const outOfOrder = collisions.filter(([i, j]) => i > j)
    check('⑥ 每一对里**静态的那一条都声明在带参的那一条之前**（0 处倒序）',
      outOfOrder.length === 0,
      JSON.stringify(outOfOrder.map(([i, j]) => `${paths[j]} 排在了 ${paths[i]} 之前`)))
    // 第二拍：整棵树建起来之后，Vue Router 自己解析每一个静态路径命中的都是它自己那一条
    const full = mk(paths)
    const misResolved = paths
      .map((p, i) => [p, i, full.resolve(p).name])
      .filter(([p, i, name]) => isStatic(p) && name !== `r${i}`)
    check('⑥ 而整棵树建起来之后，Vue Router **自己**解析每一个静态路径命中的都是它自己那一条'
      + '（⚠️ 这一拍在倒序时**也**绿 —— vue-router 4 按「静态 > 动态」打分；'
      + '故上面那一拍顺序断言才是有牙的那一条，本拍钉的是「相撞面算得对」）',
    misResolved.length === 0, JSON.stringify(misResolved))
  }

  /* ⑦ Plan 06 Task 11 / B4：**单页取值不许静默截断**。
     ⚠️ 它收的是 Task 8 登记的一条待清扫。⚠️ 而 Task 8 记的「4 处」本波实测**数少了**：
     `limit: 200` 今天出现在 **7 个组件 / 24 个调用点**（另外三处是 `StudentDetail.vue`
     3 发、`MiniTest.vue` 1 发、`RpeEntry.vue` 1 发）。失效方向是「**少给数据而不说**」：
     `limit` 的上界是 200，而甲方现场跑一年之后某些资源必然超过它（演示库上
     `training_log` 已经 840 行、`enrollment` 120 行 —— 人数上到 100 人以上就溢），
     改前那一档的表现是「页面照常渲染、只是少了后面的行」，而用户看不出来。
     ⚠️ 控制者裁定**不重构成全量分页**（那是产品决策），要的是「不许静默」：
     24 处一律走 `api/endpoints.ts` 的 `listOnePage`，它算出 `missing` 与一句人话
     `note`，7 个组件各自把 `note` 绑进模板（`t-block__note` / `s-block__note`，
     ⚠️ 都是既有类，故 `check:tokens` 一格都不退）。
     ⚠️ 四拍：**①②源码面**（唯一住址 + 7 个组件都真的画出来了）、
     **③④行为面**（今天 9 个资源在 limit=200 下**一处都不截断** ⇒ 显示结果一格都没变；
     而 limit=1 时**真的会截断** ⇒ 那个判据不是恒假）。
     ⚠️⚠️ 本拍要**后端起着**（③④ 打真端点），故第 17 步此前那句「不需要后端也不需要
     前端起着」自本波起只对 ①–⑥ 成立 —— 已如实改在那一段的注释里。 */
  {
    const stripBoth = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const walkSrc = function* (dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) yield* walkSrc(full)
        else yield full
      }
    }

    /* ① 源码面：`limit: 200` 这个字面量在 src/** 的**代码**里 0 处
          （唯一住址是 endpoints.ts 的 SINGLE_PAGE_LIMIT）。 */
    const bareLimit = []
    let scannedSrc = 0
    for (const file of walkSrc(path.join(frontendRoot, 'src'))) {
      if (!/\.(vue|ts)$/.test(file)) continue
      scannedSrc += 1
      if (/limit:\s*200/.test(stripBoth(fs.readFileSync(file, 'utf8')))) {
        bareLimit.push(path.relative(frontendRoot, file))
      }
    }
    out(`    src/** 扫了 ${scannedSrc} 个 .vue/.ts；代码里还写着 \`limit: 200\` 的 = ${bareLimit.length} 处`)
    check('⑦① 守卫不空转：扫到了 ≥ 30 个 .vue/.ts', scannedSrc >= 30, `${scannedSrc} 个`)
    check('⑦① src/** 的**代码**里 0 处裸 `limit: 200`（改前是 7 个组件 / 24 处）',
      bareLimit.length === 0, JSON.stringify(bareLimit))
    const endpointsSrc = stripBoth(fs.readFileSync(path.join(frontendRoot, 'src/api/endpoints.ts'), 'utf8'))
    check('⑦① 反例：那个唯一住址**还在**（否则「0 处」可能只是所有者也被删了），'
      + '而它仍然是 200、且缺省参数用的就是它',
      /export const SINGLE_PAGE_LIMIT = 200/.test(endpointsSrc)
        && /limit: number = SINGLE_PAGE_LIMIT/.test(endpointsSrc), '')
    check('⑦① 而「还差多少条」的算式是 `total - items.length`（不是别的）',
      /Math\.max\(0, page\.total - page\.items\.length\)/.test(endpointsSrc), '')

    /* ② 源码面：7 个组件各自把那句话**绑进了模板**（用户看得见）。 */
    const SEVEN = [
      ['src/components/TeacherNav.vue', 'truncation'],
      ['src/views/teacher/AlertQueue.vue', 'data?.truncation'],
      ['src/views/teacher/ClassReport.vue', 'data?.truncation'],
      ['src/views/teacher/Dashboard.vue', 'data?.truncation'],
      ['src/views/teacher/StudentDetail.vue', 'data?.truncation'],
      ['src/views/student/MiniTest.vue', 'data?.truncation'],
      ['src/views/student/RpeEntry.vue', 'data?.truncation'],
    ]
    const blind = []
    for (const [rel, needle] of SEVEN) {
      const src = fs.readFileSync(path.join(frontendRoot, rel), 'utf8')
      const code = stripBoth(src)
      const callsHelper = /listOnePage\(/.test(code) && /truncationNoteOf\(/.test(code)
      // ⚠️ 模板那一格**不剥注释**：`v-if` 就在模板里，而本仓的 .vue 注释是 HTML 注释，
      //    剥掉之后 `v-if="…"` 仍在（它不是注释），故这里读原文更贴近「渲染出来的是什么」。
      const renders = src.includes(`v-if="${needle}"`)
        && /class="[ts]-block__note">\{\{ (data\.)?truncation \}\}/.test(src)
      if (!callsHelper || !renders) blind.push(`${rel}（走助手 ${callsHelper} / 渲染 ${renders}）`)
    }
    check('⑦② 7 个组件**逐个**都①走 `listOnePage`+`truncationNoteOf`、'
      + '②把那句话绑进了模板（`v-if` + 一个 note 类）', blind.length === 0, JSON.stringify(blind))
    eq('⑦② 反空转：那一份清单**恰好 7 个**（= 本波实测的组件数，不是 Task 8 记的 4 个）',
      SEVEN.length, 7)

    /* ③ 行为面：今天**一处都不截断** ⇒ 「不改任何一处今天的显示结果」那一格的可执行形式。
          ⚠️ 用 `as: 'admin'`：管理员越过任教范围闸门、看到的是**全表**，
          故它是最坏的那一档（教师档只会更少）。 */
    const RESOURCES = ['teachers', 'students', 'course-sections', 'enrollments', 'alerts',
      'class-sessions', 'weekly-class-reports', 'mini-tests', 'stratification-results']
    const truncatedToday = []
    for (const resource of RESOURCES) {
      const res = await req('GET', `/api/${resource}?limit=200`,
        { as: 'admin', quiet: true, record: false })
      if (res.status !== 200) {
        truncatedToday.push(`${resource} → HTTP ${res.status}`)
        continue
      }
      const { items, total } = res.json ?? {}
      if (!Array.isArray(items)) {
        truncatedToday.push(`${resource} → 响应体没有 items`)
        continue
      }
      out(`    /api/${resource}?limit=200 → total ${total} / items ${items.length}`)
      if (total !== items.length) truncatedToday.push(`${resource}: total ${total} > items ${items.length}`)
    }
    check('⑦③ 演示库上那 9 个资源在 limit=200 下 **total == items.length**'
      + '（⇒ `note` 恒为 null ⇒ `v-if` 恒假 ⇒ 今天的 DOM 一个字节都没变）',
    truncatedToday.length === 0, JSON.stringify(truncatedToday))

    /* ④ 行为面：把 limit 压到 1，那个判据**真的会响**（不必造 200 行数据）。 */
    const one = await req('GET', '/api/alerts?limit=1', { as: 'admin', quiet: true, record: false })
    eq('⑦④ GET /api/alerts?limit=1 → 200', one.status, 200)
    const items1 = one.json?.items
    const total1 = one.json?.total
    check('⑦④ 而它**真的**截断了（items 恰好 1 行、total 严格大于 1）'
      + '⇒ `listOnePage` 的 `missing > 0`、`note` 非 null',
    Array.isArray(items1) && items1.length === 1 && typeof total1 === 'number' && total1 > 1,
    JSON.stringify({ items: items1?.length, total: total1 }))
    check('⑦④ 于是那句提示会带上**两个数**（一共 total1 条 / 还差 total1-1 条）——'
      + '⚠️ 期望侧照 endpoints.ts 的算式现算，不把那句话抄一份在这里',
    typeof total1 === 'number' && total1 - 1 > 0, `missing = ${Number(total1) - 1}`)
  }

  /* ⑧ Plan 06 Task 12 / C3（老终审 M7）：**会话恢复那一帧**的**结构面**。
     ⚠️ 运行时那一半住在第 14 步的 §C3（真扣住 `/api/auth/me`、真取那一帧的 DOM）；
     本拍钉的是**源码结构**，因为运行时那一拍只证明「今天对」，而下面五格是
     「下一个人改坏了会**静默**退化」的地方 —— 派单逐字要求的就是这一条
     （「否则下一次有人改路由守卫顺序就会静默退化」）：
       ① 初值是 `'unknown'` 不是 `'anon'`（两档在守卫里必须分开，
          `stores/session.ts` 文件头末节逐字写了理由）；
       ② `router.beforeEach` **先 await** `ensureRestored()`、**再**读 `isAuthenticated`
          （顺序是承重的：反过来就是一个已登录的用户被弹去 `/login` 再弹回来）；
       ③ 「会话还没落定」这个谓词在 `src/**` 里**只有一处**（store 的 `isPending`）；
       ④ 两个消费者（`summary` / `roleLabel`）都走 ③ 那一个；
       ⑤ **反空转**：`'未登录'` 与 `ANONYMOUS` 两句真话**都还在**
          （否则「把 pending 判据写成恒真」会让第 14 步 §C3 的①–④全绿）。 */
  {
    const stripBoth = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const readSrc = (rel) => fs.readFileSync(path.join(frontendRoot, rel), 'utf8')
    const walkSrc = function* (dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) yield* walkSrc(full)
        else yield full
      }
    }
    const sessionSrc = stripBoth(readSrc('src/stores/session.ts'))
    const routerSrc = stripBoth(readSrc('src/router/index.ts'))
    const switcherSrc = stripBoth(readSrc('src/components/IdentitySwitcher.vue'))

    check('⑧① 会话 store 的初值是 `status: \'unknown\'`（⚠️ 不是 `\'anon\'`：'
      + '两档在守卫里必须分开，否则 `me` 回来之前就会把一个已登录的用户弹去 /login）',
    /status:\s*'unknown'/.test(sessionSrc), '')

    const guardAt = routerSrc.indexOf('router.beforeEach(')
    const awaitAt = routerSrc.indexOf('await session.ensureRestored()', guardAt)
    const authedAt = routerSrc.indexOf('session.isAuthenticated', guardAt)
    check('⑧② `router.beforeEach` **先 await** `ensureRestored()`、**再**读 `isAuthenticated`'
      + '（顺序是承重的：反过来就是 M7 那一格「弹去 /login 再弹回来」）',
    guardAt >= 0 && awaitAt > guardAt && authedAt > awaitAt,
    JSON.stringify({ guardAt, awaitAt, authedAt }))

    /* ③ 那个谓词在 src/** 的**代码**里只出现一次（唯一住址 = store 的 isPending）。 */
    const predicateHits = []
    let scanned = 0
    /** ⚠️ `path.relative` 在 Windows 上给的是**反斜杠**，而清单里写的是正斜杠 ——
     *  不归一的话本拍会红在 `["src\\stores\\session.ts",1]` 上（本机实测踩过）。 */
    const relOf = (file) => path.relative(frontendRoot, file).split(path.sep).join('/')
    for (const file of walkSrc(path.join(frontendRoot, 'src'))) {
      if (!/\.(vue|ts)$/.test(file)) continue
      scanned += 1
      const code = stripBoth(readSrc(relOf(file)))
      const hits = (code.match(/=== 'restoring'/g) ?? []).length
      if (hits > 0) predicateHits.push([relOf(file), hits])
    }
    const totalHits = predicateHits.reduce((sum, [, n]) => sum + n, 0)
    check('⑧③ 守卫不空转：src/** 扫到了 ≥ 30 个 .vue/.ts', scanned >= 30, `${scanned} 个`)
    check('⑧③ 「会话还没落定」那个谓词在 src/** 的代码里**恰好 1 处**'
      + '（= store 的 `isPending`；两处各写一遍的话，加第五个状态只会改到其中一处）',
    totalHits === 1 && predicateHits[0]?.[0] === 'src/stores/session.ts',
    JSON.stringify(predicateHits))
    check('⑧③ 而 `isPending` 那个 getter 真的存在、且两档都算「没落定」',
      /isPending\(state\): boolean \{[\s\S]{0,120}status === 'unknown'[\s\S]{0,40}=== 'restoring'/.test(sessionSrc), '')

    check('⑧④ 两个消费者都走 `isPending`：`summary` 的 pending 档 + `roleLabel` 的 PENDING 档',
      /if \(this\.isPending\) return '身份未确认…'/.test(sessionSrc)
        && /if \(session\.isPending\) return 'PENDING…'/.test(switcherSrc), '')

    check('⑧⑤ 反空转：「未登录」与 `ANONYMOUS` 两句**真话**都还在'
      + '（「问过了、答案是匿名」那一档必须照说；少了本拍，把 pending 判据写成恒真是绿的）',
      sessionSrc.includes("return '未登录'") && switcherSrc.includes("return 'ANONYMOUS'"), '')

    /* ⑦⑧⑨ **Plan 06 Task 15（终审 S3-⑤）**：那一次「问后端我是谁」必须**有上限**，
       而超时之后必须落到一个**可读的错误态**（不是无限期的「身份未确认…」）。
       ⚠️ 改前的形状（本波用 CDP 的 `Fetch` 域真扣住 `/api/auth/me` 取过运行时证）：
       产品档上扣住 **19 s**，+2.1 / +6.2 / +11.1 / +18.6 s 四个取样点**全部**停在
       「身份未确认… / 会话状态 restoring」，DOM 正文一动不动是 1111 字符，
       既没横幅也没任何超时字样；放行之后 262 ms 落定 `authed`。
       ⚠️ 而那一档运行时取证**刻意不进 smoke**：它要给每一步加 10 s 墙钟，
       而本脚本两档今天各 ~30 s（§13.11.4 记着「结构面守卫吃掉约 1/4」那一笔账，
       再加 1/3 就不成比例了）。故这里钉**源码结构**的五格。 */
    const authSrc = stripBoth(readSrc('src/api/auth.ts'))
    check('⑧⑥ `ensureRestored` 那一次 fetchMe **真的传了** `AbortSignal.timeout(RESTORE_TIMEOUT_MS)`'
      + '（改前逐字是 `await fetchMe()`：一个挂住的 /api/auth/me 会让页面无限期停在「身份未确认…」）',
    /await fetchMe\(AbortSignal\.timeout\(RESTORE_TIMEOUT_MS\)\)/.test(sessionSrc), '')
    check('⑧⑥ 而 `api/auth.ts` 的 `fetchMe` **真的把 signal 转交**给 `apiRequest`'
      + '（少这一格，上面那一拍就是空转：signal 会在中途被丢掉）',
    /export async function fetchMe\(signal\?: AbortSignal\)/.test(authSrc)
        && /apiRequest\('GET', '\/api\/auth\/me', \{ signal \}\)/.test(authSrc), '')
    check('⑧⑦ 上限是一个**具名的字面量常量**（唯一所有者），且落在 5–30 s 这个区间里'
      + '（太短会把一次正常的慢查询误判成挂住，太长就等于没有）',
    (() => {
      const m = sessionSrc.match(/export const RESTORE_TIMEOUT_MS = ([\d_]+)/)
      if (m === null) return false
      const ms = Number(m[1].replace(/_/g, ''))
      out(`    RESTORE_TIMEOUT_MS = ${ms} ms`)
      return ms >= 5000 && ms <= 30000
    })(), '')
    check('⑧⑦ 超时那一档有**自己的状态**（`timed_out`），而它**不算** pending'
      + '（`isPending` 的两档判据逐字未变 ⇒ 上面 ⑧③ 那一条「恰好 1 处」照旧成立）',
    /'unknown' \| 'restoring' \| 'authed' \| 'anon' \| 'timed_out'/.test(sessionSrc)
        && /isPending\(state\): boolean \{[\s\S]{0,120}status === 'unknown'[\s\S]{0,40}=== 'restoring'/.test(sessionSrc)
        && !/isPending\(state\): boolean \{[\s\S]{0,200}timed_out/.test(sessionSrc), '')
    check('⑧⑧ 超时之后有**出路**：一句就地说明（`setNotice`）+ 一个刷新入口'
      + '（`IdentitySwitcher` 里那一个「⟳ 刷新页面」按钮），而会话条不再说「身份未确认…」',
    /this\.status = 'timed_out'/.test(sessionSrc)
        && /if \(state\.status === 'timed_out'\) return '身份确认超时…'/.test(sessionSrc)
        && /if \(session\.status === 'timed_out'\) return 'TIMEOUT'/.test(switcherSrc)
        && switcherSrc.includes('刷新页面')
        && /reloadPage\(\): void \{[\s\S]{0,80}location\.reload\(\)/.test(switcherSrc), '')
  }

  /* ⑨ **Plan 07 Task 1**：试用告示的**唯一住址**是 `App.vue`、它挂在 `v-if="trial"` 上、
     `trial` 那一格由 `getHealth()` 填、而 `/api/health` **读不到就不挂**。
     ⚠️⚠️ 它补的是第 14 步那三拍补不到的**另一半**（硬规矩 #50 的红绿两侧）：
     第 14 步量的是渲染后的真值，而在 **dev 档与产品档**下「告示不在」这一档与
     「`App.vue` 里那一条被人删掉了」在颜色上**无法区分**（两档都绿）——
     于是「把横幅从根组件挪走」这个定点变异只有**试用档那一遍**才抓得到，
     而试用档不是每波都跑（它要另灌一个库、另起一个服务）。本拍从**源码面**钉住它，
     三档都跑，故它不需要任何服务起着。
     ⚠️ 五拍：① 全 `src/**` 的**代码**里含那条文案的文件恰好 1 个 = `src/App.vue`
     （⇒ 唯一住址；两处各写一遍的话，改一处漏一处，而漏掉的那一处是**给甲方看的**）；
     ② 它挂在一个 `v-if="trial"` 上（⇒ 档位判据是后端给的那一格，**不是写死在前端**：
     `frontend/dist` 是同一份构建产物，写死的话产品档也会挂着一条假话）；
     ③ `trial` 那一格由 `getHealth()` 填（⇒ 前端确实是**问后端**的，
     不是判 `location.hostname`、也不是 `import.meta.env` 的构建期常量）；
     ③′ ⚠️ **反假绿**：③ 那一拍在「`catch` 那一支把 `trial` 设成 `true`」时**也绿**
     （读不到就挂告示 ⇒ 后端没起来时开发档也挂一条试用告示 = 一句假话），
     故另钉住控制者裁定的那一格：**读不到就不挂**；
     ④ 反空转：`src/**` 扫到了 ≥ 30 个 `.vue`/`.ts`。 */
  {
    const stripBoth = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const walkSrc = function* (dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) yield* walkSrc(full)
        else yield full
      }
    }
    const NOTE = '请勿录入真实学生信息'
    const noteFiles = []
    let noteScanned = 0
    for (const file of walkSrc(path.join(frontendRoot, 'src'))) {
      if (!/\.(vue|ts)$/.test(file)) continue
      noteScanned += 1
      if (stripBoth(fs.readFileSync(file, 'utf8')).includes(NOTE)) {
        noteFiles.push(path.relative(frontendRoot, file).split(path.sep).join('/'))
      }
    }
    out(`    src/** 扫了 ${noteScanned} 个 .vue/.ts；代码里含那条告示文案的 = ${noteFiles.length} 个文件`)
    check('⑨④ 守卫不空转：src/** 扫到了 ≥ 30 个 .vue/.ts', noteScanned >= 30, `${noteScanned} 个`)
    check('⑨① 试用告示的文案在 src/** 的**代码**里恰好 1 个文件（唯一住址 = src/App.vue，'
      + '16 条路由共用那一处 ⇒ 挪走任何一条路由都还看得见）',
    noteFiles.length === 1 && noteFiles[0] === 'src/App.vue', JSON.stringify(noteFiles))
    const appSrc = stripBoth(fs.readFileSync(path.join(frontendRoot, 'src/App.vue'), 'utf8'))
    check('⑨② 而那一条挂在 `v-if="trial"` 上（⇒ 档位判据是**后端给的那一格**，'
      + '不是写死在前端的构建期常量）',
    /<p v-if="trial"[^>]*>/.test(appSrc), '')
    check('⑨③ 而 `trial` 那一格由 `getHealth()` 填（⇒ 前端是**问后端**的：'
      + '不是判 location.hostname、也不是 import.meta.env）',
    /const health = await getHealth\(\)/.test(appSrc)
        && /trial\.value = health\.trial === true/.test(appSrc), '')
    check('⑨③′ 而 `/api/health` **读不到就不挂**告示（控制者裁定；反过来那一档会让'
      + '「后端没起来」时的开发档也挂一条试用告示 = 一句假话）',
    /catch \{[\s\S]{0,400}trial\.value = false/.test(appSrc), '')
  }

  /* ⑩ **Plan 07 Task 5b 缺陷 ①/②**：「原生校验拦下 submit 时不许静默」的**源码面**，
     外加「`step` 的口径不许被前端发明第二次」与「『他任不任教这个学生』不许有第二个判据」。
     ------------------------------------------------------------------------
     ⚠️⚠️ 它补的是第 14 步那几组拍补不到的**另一半**（硬规矩 #50 的红绿两侧）：
     第 14 步的 §CI-1/§CI-2/§FV-1/§FV-2 量的是**渲染后的真值**，而它们只在
     「今天这三张表单」上量。于是下面两档失效在颜色上与「修好了」**无法区分**：
       · 有人**新加**一张带 `required` / `step` 的表单而没有接那个共用处置
         ⇒ 它又会静默，而第 14 步的 4 组拍一张都不会红（它们只走既有的三张）；
       · 有人把某一格的 `step` 从 `any` 改成一个**数字**（例如又写回 `0.5`）
         ⇒ 若那一格今天恰好没有一位小数的预填值，§CI-1 也照样绿，
         而下一次数据精度变了就又是一个静默（本缺陷的原始形状）。
     本拍从**源码面**钉住这两档，三档都跑，且不需要任何服务起着。
     ------------------------------------------------------------------------
     ⚠️ 六拍：① 那句人话的文案在 `src/**` 的**代码**里恰好 1 个文件
     = `src/composables/useFormValidity.ts`（⇒ 单一所有者；每个表单各写一份的话，
     改一处漏一处，而漏掉的那一处正是「点了没反应」）；
     ② 反空转：`src/**` 扫到了 ≥ 25 个 `.vue`、其中含 `<form` 的 ≥ 5 个；
     ③ **每一张带原生约束的表单都接上了那个处置**（约束 = `required` / `pattern` /
     `minlength` / `maxlength` / `step` / `min` / `max`，⚠️ 只认**属性位置**上的
     —— 谓词要求它前面是空白、后面是 `=`/空白/`>`/`/`，故 `v-for="step in …"`
     与 `class="step__n"` 都不会被算成约束）；
     ④ 而**没有**约束的那几张表单刻意**不**接（`RpeEntry.vue` 与管理台那两张
     契约驱动的表单：它们把 number 一律画成 `type="text"`、由 `api/contract.ts` 的
     `assembleBody` 自己报错）—— 接上去是一条**恒不触发**的死路径（硬规矩 #50）；
     ⑤ `src/**` 的模板里 `step="<数字>"` 出现 **0** 次：步长口径的所有者是
     **后端 schema**（`multiple_of`），前端写一个数字 `step` 就是第二个所有者，
     而它的失效方向是**静默**（本缺陷逐字就是这个形状）；
     ⚠️ 扫描面**改前只是 `src/views/`**，Plan 07 Task 8 按终审 S4-8 放宽到全 `src/`
     （与 ②③④ 那三拍同一个 `srcDir`）：改前「往 `src/components/` 里加一张带约束的
     表单」这一档抓不到，而今天 `components/` 下 0 个 `<form>` ⇒ 那是**巧合**不是契约。
     ⑤′ 是它的反空转：断言扫描面**同时**含 ≥ 16 个 `views/` 的 `.vue` 与 ≥ 13 个
     `components/` 的 `.vue`（目录改名之后「0 次」会变成扫空扫出来的假绿）；
     ⑥ 缺陷 ② 的源码面：那句写死的断言（「确实由该教师本学期任教」）在 `src/**`
     的代码里 **0** 次，而「他任不任教这个学生」的判据在前端**恰好 1 个文件**
     （`views/teacher/StudentDetail.vue` 的 `teachesHere`，它读的是那一次
     `/home` 教师侧变体的 200/403，⚠️ 不自己再判一次任教关系）。 */
  {
    const stripBoth = (t) => t
      .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
      .replace(/^[ \t]*\/\/.*$/gm, (m) => m.replace(/[^\n]/g, ' '))
    const walk = function* (dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) yield* walk(full)
        else yield full
      }
    }
    const rel = (f) => path.relative(frontendRoot, f).split(path.sep).join('/')

    /** 原生约束的谓词。⚠️ 只认**属性位置**：前面是空白（故 `v-for="step in RPE_SCALE"`
     *  与 `class="step__n"` 都不算），后面是 `=` / 空白 / `>` / `/`（故 `step--on`
     *  与 `minimum` 都不算）。⚠️ `required` 那一类布尔属性后面直接是空白或 `>`。 */
    const CONSTRAINT = /[\s](?:v-bind:|:)?(required|pattern|minlength|maxlength|step|min|max)(?=[\s="'/>/])/g
    const NUMERIC_STEP = /[\s](?:v-bind:|:)?step="\s*[0-9.]/g

    const srcDir = path.join(frontendRoot, 'src')
    let vueCount = 0
    const withForm = []
    const filesWith = (needle) => {
      const hits = []
      for (const file of walk(srcDir)) {
        if (!/\.(vue|ts)$/.test(file)) continue
        if (stripBoth(fs.readFileSync(file, 'utf8')).includes(needle)) hits.push(rel(file))
      }
      return hits
    }

    for (const file of walk(srcDir)) {
      if (!file.endsWith('.vue')) continue
      vueCount += 1
      const code = stripBoth(fs.readFileSync(file, 'utf8'))
      if (!code.includes('<form')) continue
      const constraints = [...new Set([...code.matchAll(CONSTRAINT)].map((m) => m[1]))].sort()
      withForm.push({
        file: rel(file),
        constraints,
        wired: code.includes('useFormValidity'),
      })
    }

    check('⑩② 守卫不空转：`src/**` 扫到了 ≥ 25 个 `.vue`、其中含 `<form` 的 ≥ 5 个',
      vueCount >= 25 && withForm.length >= 5, `${vueCount} 个 .vue / ${withForm.length} 个含 <form`)
    out(`    含 <form 的 ${withForm.length} 个文件（约束 → 有没有接那个共用处置）：`)
    for (const f of withForm) {
      out(`      ${f.file.padEnd(38)} [${f.constraints.join(', ')}] → useFormValidity=${f.wired}`)
    }

    const phrase = filesWith('表单没有提交出去')
    check('⑩① 那句人话的文案在 `src/**` 的**代码**里恰好 1 个文件'
      + '（唯一住址 = `src/composables/useFormValidity.ts`）',
      phrase.length === 1 && phrase[0] === 'src/composables/useFormValidity.ts',
      JSON.stringify(phrase))

    const shouldWire = withForm.filter((f) => f.constraints.length > 0)
    check('⑩③ **每一张带原生约束的表单都接上了那个共用处置**（改前是 0/3：'
      + '原生校验拦下 submit 时页面不报错、不打日志、不发请求）',
      shouldWire.length >= 3 && shouldWire.every((f) => f.wired),
      `${shouldWire.filter((f) => f.wired).length}/${shouldWire.length} 接了：`
      + JSON.stringify(shouldWire.map((f) => f.file)))
    const shouldNot = withForm.filter((f) => f.constraints.length === 0)
    check('⑩④ 而**没有**约束的那几张刻意**不**接（接上去是一条恒不触发的死路径，'
      + '硬规矩 #50）—— 它们的错话各有自己的住址（`assembleBody` / `canSubmit`）',
      shouldNot.length >= 2 && shouldNot.every((f) => !f.wired),
      JSON.stringify(shouldNot.map((f) => f.file)))

    /* ⚠️ 扫描面 = **整个 `src/`**（Plan 07 Task 8 · 终审 S4-8）。改前这里是
       `walk(viewsDir)`，于是 `src/components/` 下的表单不在扫描面里；今天那一格是空的
       （实测 `components/` 的 13 个 `.vue` 里 0 个 `<form>`、0 个数字 `step`），故改前
       没有漏 —— 而「没有漏」是数据的巧合，不是守卫的性质。⚠️ 与 ②③④ 那三拍用**同一个**
       `srcDir`：两处扫描面不一致正是终审把整组读成「只扫 views/」的原因
       （`composables/useFormValidity.ts` 的文件头此前也照着 ⑩⑤ 那么写，本波一并改对）。 */
    let numericSteps = 0
    const numericWhere = []
    const numericSurface = { views: 0, components: 0 }
    for (const file of walk(srcDir)) {
      if (!file.endsWith('.vue')) continue
      const where = rel(file)
      if (where.startsWith('src/views/')) numericSurface.views += 1
      else if (where.startsWith('src/components/')) numericSurface.components += 1
      const code = stripBoth(fs.readFileSync(file, 'utf8'))
      const hits = [...code.matchAll(NUMERIC_STEP)]
      if (hits.length > 0) {
        numericSteps += hits.length
        numericWhere.push(`${where} ×${hits.length}`)
      }
    }
    eq('⑩⑤ `src/**` 的模板里 `step="<数字>"` 出现 **0** 次（步长口径的所有者是后端'
      + ' schema 的 `multiple_of`；前端写一个数字 `step` 就是第二个所有者，而它的失效方向'
      + '是**静默** —— 本缺陷逐字就是这个形状）', numericSteps, 0)
    if (numericSteps > 0) out(`    ⚠️ 命中在：${numericWhere.join('、')}`)
    /* ⑩⑤′ 反空转（S4-8 的另一半）：上面那个「0 次」有一个假绿来源是**扫空了**
       （`views/` 或 `components/` 被改名 ⇒ `walk` 一个文件都不给 ⇒ 恒 0）。
       下界取今天实测的真值（16 / 13）：少一个 `.vue` 就红，多几个不红（那是正常的长）。 */
    check('⑩⑤′ 反空转：⑩⑤ 的扫描面**同时**覆盖 `src/views/`（≥ 16 个 `.vue`）与'
      + ' `src/components/`（≥ 13 个 `.vue`）—— 否则那个「0 次」可能只是目录改名后扫空了',
      numericSurface.views >= 16 && numericSurface.components >= 13,
      `views ${numericSurface.views} / components ${numericSurface.components}`)

    const stale = filesWith('确实由该教师本学期任教')
    eq('⑩⑥ 缺陷 ②：那句**随 id 变假**的写死断言在 `src/**` 的代码里 0 个文件', stale.length, 0)
    const judge = filesWith('本学期任教他')
    check('⑩⑥′ 而「他任不任教这个学生」的判据在前端**恰好 1 个文件**'
      + '（`views/teacher/StudentDetail.vue`；它读的是那一次 `/home` 教师侧变体的 200/403）',
      judge.length === 1 && judge[0] === 'src/views/teacher/StudentDetail.vue',
      JSON.stringify(judge))
    const detailSrc = stripBoth(fs.readFileSync(
      path.join(frontendRoot, 'src/views/teacher/StudentDetail.vue'), 'utf8'))
    check('⑩⑥″ 而那一个判据读的是**同一次** HTTP 的结果（`homeError.code === \'forbidden\'`），'
      + '⚠️ 不自己再判一次任教关系（那是后端 `require_teaches_student` 的活；前端重算一遍'
      + '就是第二个所有者，而两份漂开之后的症状正是本缺陷：一屏上既说 403 又说「确实任教」）',
      /teachesHere[\s\S]{0,600}homeError\.code === 'forbidden'/.test(detailSrc)
        && /boolean \| null/.test(detailSrc), '')
  }
})

/* ==========================================================================
   收尾
   ========================================================================== */

out('')
out('='.repeat(78))
out('总结')
out('='.repeat(78))
for (const s of STEPS) {
  const ok = s.checks.every((c) => c.ok)
  out(`  ${ok ? '绿' : '红'}  第 ${String(s.no).padStart(2, '0')} 步 · ${s.title.slice(0, 60)} · ${s.checks.filter((c) => c.ok).length}/${s.checks.length} 条断言`)
}
const greenSteps = STEPS.filter((s) => s.checks.every((c) => c.ok)).length
out('')
out(`  步数 ${greenSteps}/${STEPS.length} 全绿 · 断言 ${PASSED} 绿 / ${FAILED} 红`)
out(`  后端 ${API} · 前端 ${WEB} · as_of ${AS_OF}`)
out(`  身份（**cookie 会话**，不是请求头）：教师 ${TEACHER}（role=teacher）· `
  + `管理员 ${ADMIN}（role=admin）· 学生 #${STUDENT} · 口令见 demo.ps1 的 [6/7] 输出`)
out(`  jar ${JARS.size} 个：${[...JARS.keys()].join(', ')}`)
out('')
if (FAILED > 0) {
  out('红的断言：')
  for (const s of STEPS) {
    for (const c of s.checks) {
      if (!c.ok) out(`  第 ${s.no} 步 ✗ ${c.label}  →  ${c.detail}`)
    }
  }
  out('')
}
out('⚠️⚠️ 本脚本**已经写脏了演示库**：再跑一次之前先重跑 backend\\scripts\\demo.ps1')
out('    脏在它建/改的 5 样东西上：第 2 步一节课（+ 第 4 步又一节未发起快评的）、')
out('    第 5 步一条快评、第 6 步一次打卡、第 9 步一条被处置的预警（+ 它写的一条')
out('    weekly_adjustment）、第 10 步一个学期 + 一次「建了又删掉」的教师。')
out('    ⚠️ 其中**第 10 步那个学期删不掉**：`semesters` 在 catalog.RESOURCES 里是')
out('      `on_delete="forbid"` → 后端**根本不注册** DELETE /api/semesters/{id}')
out('      → 打过去是 **405 http_405**（⚠️ 不是 `restrict`；`restrict` 的表现是')
out('      端点存在、删的时候被子表挡住 → **409 integrity_conflict**，')
out('      第 10 步里 `DELETE /api/students/{id}` 那一拍就是它）。')
out('    ⚠️ 第 16 步（Plan 05A Task 4 新增）建的三个教师**都删掉了**（⑬ 那一拍断言')
out('      名册回到 3 行），故它不脏名册；而它留下的 **3 行 user_session** 删不掉')
out('      （那张表不在 23 个资源里、没有端点），但它们①2 小时后自己过期')
out('      ②subject 已从名册上删掉 → `sessions.resolve` 回查时当场吊销，故不可用。')
out('      ⚠️ 「过期行的清理任务」自 Plan 08 Task 2 起**有了**（backend/scripts/retention.ps1，')
out('        口径正文 spec §13.24）；⚠️ 而它**不会自己跑**（Windows 上没有 cron，注册计划任务的')
out('        命令由 backend/scripts/register_retention_task.ps1 **打印**），且本脚本刻意不调它')
out('        —— 联调脚本不删行，而那 3 行 2 小时后自己过期、且已被当场吊销。')
out('    ⚠️ 本脚本**刻意不自己复原**（理由与两档的完整交代见文件头）：自己复原要么')
out('      绕过 HTTP 直接删库（那它就不是联调脚本了），要么给 semesters 开一个 DELETE')
out('      端点（那会推翻 `forbid` 那条口径）。第 0 步因此同时充当「你是不是忘了复原」')
out('      的守卫：脏库上它会红在行数上。')

if (TRANSCRIPT) {
  const payload = {
    generatedAt: new Date().toISOString(),
    api: API,
    web: WEB,
    asOf: AS_OF,
    teacher: TEACHER,
    admin: ADMIN,
    student: STUDENT,
    // ⚠️ **jar 里的 cookie 一律不写进 transcript**（那份文档是入库的）。
    jars: [...JARS.keys()],
    summary: { steps: STEPS.length, greenSteps, passed: PASSED, failed: FAILED },
    steps: STEPS,
  }
  fs.writeFileSync(TRANSCRIPT, JSON.stringify(payload, null, 1), 'utf8')
  out(`transcript → ${TRANSCRIPT} (${fs.statSync(TRANSCRIPT).size} bytes)`)
}

process.exit(FAILED === 0 && greenSteps === STEPS.length ? 0 : 1)
