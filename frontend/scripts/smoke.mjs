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
 * 怎么跑
 * ---------------------------------------------------------------------------
 *     # ① 起后端（**必须**先复原演示库：本脚本会写库，且第 0 步要核实行数）
 *     powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -Port 8000
 *     # ② 起前端（第 14 步要它）
 *     cd frontend; npm run dev
 *     # ③ 跑
 *     cd frontend; npm run smoke
 *
 * 退出码 **0** = **18 步全绿**（编号 0–17）。任何一步的任何一条断言红了都是 **1**。
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
 * ⚠️ **第 17 步是终审 fix 波新增的**：4 条**不需要浏览器**的守卫，钉的是
 * 「一句写死的话不得与真实值漂开」这一族（I2 / I4 / M1 / M5）。
 * （未绑定 → 绑定四档 → 登录 → me → 登出 → 旧 cookie 401 → subject 被删 → 401，
 * 外加三档授权）。
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
 *  ⚠️ **needle 一律只在它的返回值里找**：不给「原文里出现」留第二个出口。 */
function toPlainText(html) {
  return stripEmbedded(html).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
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

await step(1, 'GET /api/health → tables == 28 且 students > 0', async () => {
  const res = await req('GET', '/api/health')
  eq('200', res.status, 200)
  eq('status == ok', res.json?.status, 'ok')
  // ⚠️ **28 而不是 27**（Plan 06 Task 5）：新增了 `audit_log`（请求审计留痕）。
  //    Plan 06 Task 3 那一次是 26 → 27（+`login_attempt`，登录限流的计数存储），
  //    Plan 05A Task 1 是 25 → 26（+`user_session`）。
  //    ⚠️ 本端点是**匿名**的（Task 5 那 48 → 44 个匿名 GET 的裁定里它保持匿名：
  //    它是存活探针，回三格 `status/tables/students`，一格秘密都不含）。
  //    ⚠️⚠️ 而 **Plan 06 Task 4 之后它刻意仍然只有三格**：`PE_ENV` 的值不回给匿名
  //    （把「这是一个开发档：CORS 全开、请求头身份可用」告诉探测者，正是他要挑的目标）。
  //    下面那一拍「恰好 3 个键」因此同时是**档位不泄漏**的取证；
  //    后端那一侧的守卫是 `tests/test_main.py` 的
  //    `test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller`
  //    （判据更强：dev 与 prod 两档下 `/api/health` 与 `/openapi.json` 的响应体**逐字节相同**）。
  eq('tables == 28（Plan 06 Task 3 是 27；+audit_log）', res.json?.tables, 28)
  check('students > 0', (res.json?.students ?? 0) > 0, `students=${res.json?.students}`)
  // ⚠️ /api/health 是「24 个未定型响应」里唯一不是 list 的那一个，
  //    故它的形状由 api/types.ts 手写补上（约束第 5 条）。
  eq('响应恰好 3 个键（未定型 → 前端手写的 HealthRead）',
    Object.keys(res.json ?? {}).sort().join(','), 'status,students,tables')
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
await step(12, '从 /openapi.json 反查 catalog/resources.ts 的 23 行（6 拍）', async () => {
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
  eq('路径模板 74 个（Plan 06 Task 10 起 73 → 74：+/api/teacher/students/{id}/normalized）',
    apiPaths.length, 74)
  eq('操作 102 个（Task 10 起 101 → 102）', ops, 102)
  eq('挂 security 的 84 个（Plan 05A 是 52；安全收紧波 +28；收尾波 ③ +1；Task 5 +1 = audit-logs；'
    + 'Task 9 +1 = normalized/me；Task 10 +1 = teacher/…/normalized）', secured, 84)
  eq('GET 63 个（Task 10 起 62 → 63：+GET /api/teacher/students/{id}/normalized）', gets, 63)
  eq('其中匿名 GET 15 个（安全收紧波之前是 44；收尾波 ③ 又关掉 normalized 那一扇；'
    + 'Task 5 / Task 9 / Task 10 各加一个端点都挂 security，故这一格三波都不变）', getsAnon, 15)

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
    { name: 's-mini-test', url: '/s/mini-test', jar: studentJar(STUDENT), size: [375, 2400],
      needles: ['二次小测', '30 秒深蹲'] },
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
    { name: 'admin-index', url: '/admin', jar: 'admin', size: [1440, 3000],
      needles: ['资源目录', '23 resources', '可写 9', '只读 14', '体育专家维护的知识资产'] },
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
    { name: 'admin-audit-logs', url: '/admin/audit-logs', jar: 'admin', size: [1440, 2400],
      needles: ['审计留痕', '/api/audit-logs', '仅 role=admin 可读', '身份类型',
        'subject_kind', '/api/auth/login'] },
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

  /** 导航到一条路由、轮询到关键内容都出现（或超时），返回那份 DOM 原文。 */
  async function dumpRoute(route) {
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
    const wanted = route.needles.filter((n) => n !== undefined)
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

  for (const route of ROUTES) {
    const { html, at } = await dumpRoute(route)
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
  }

  /* ⚠️ 档位判定的**收尾一拍**：16 条路由必须给出同一个档位，且不许是 `unknown`。
     它是上面那两格（每条路由各自的 `tier !== 'unknown'`）之外唯一一条
     **说出「本次量的是哪一档」**的断言 —— 取证要能从日志里读出「这一遍跑的是
     产品档、地板取的是 6000」，而不是靠人去推。
     ⚠️ 「一致」那一格挡的是混合态：例如某一条路由因为一次失败的导航拿到了
     一份**没有**任何标记的错误页，它会单独掉到 `unknown`（那一条自己已经会红），
     而本拍把这件事在总结里说清楚，免得 16 行红里看不出是「一档认不出」还是「全档认不出」。 */
  check('§Tier 16 条路由的构建档判定**一致**（dev 档地板 20000 / 产品档地板 6000，各只在自己的档上生效）',
    TIERS_SEEN.length === ROUTES.length
      && new Set(TIERS_SEEN).size === 1
      && TIERS_SEEN[0] !== 'unknown',
    `${TIERS_SEEN.length}/${ROUTES.length} 条给了判定，取值 = ${[...new Set(TIERS_SEEN)].join(',')}`)

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
  check('⑦ cookie **不带** Secure（本机不是 PE_ENV=production；生产上它必须在）',
    !/;\s*secure/i.test(setCookieRaw), maskedRaw)
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
   ⚠️⚠️ **终审 fix 波新增的一步：4 条不需要浏览器的守卫**（I2 / I4 / M1 / M5）。
   前 17 步（0–16）验的是「后端与前端对接得上」；本步验的是**账面不得与代码打架** ——
   那 4 条的共同形状是「一句写死的话与真实值漂开了」，而它们各自**都没有守卫**
   （这正是它们能活到今天的原因，与 I1 那个假学号同族）。

   ⚠️ 与第 15 步一样，本步**不需要后端也不需要前端起着**；而 ① 那一拍要
   **PowerShell 与 Python**（它 spawn 一次 `backend/scripts/demo.ps1 -DryRun`，约 15 秒，
   库与 CSV 都落在 `$env:TEMP`、跑完自己删掉，故它不脏演示库、也不碰两个禁区）。
   ⚠️ 四拍各自都带**反例/非空转**那一边（硬规矩 #50 / #107）：一条「0 处 offender」
   的断言，若不同时证明「谓词对已知反例确实会报」，那它与「谓词写坏了」在输出上
   是同一个样子。 */
await step(17, '终审 fix 波的 4 条静态守卫：demo.ps1 强制关掉身份头开关 / toPlainText / surface 字面值 / 破折号的唯一住址', async () => {
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
out('      ⚠️ 「过期行的清理任务」是原型刻意不做的一档，已登记为待清扫（spec §13）。')
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
