#!/usr/bin/env node
/**
 * `scripts/shots.mjs` —— **15 条路由各截一张图**（Plan 05B 计划 §4.2 第 6 条）。
 *
 * ---------------------------------------------------------------------------
 * 它证明什么
 * ---------------------------------------------------------------------------
 * 「像不像北欧公共标识」是用户 7 条要求里**唯一不能机器判定**的那几条之一
 * （计划 §8 自审第 4 项逐字承认了这一点：「简洁」「干净」是主观的）。
 * 故本脚本的产物是**给人眼复核用的**：控制者拿这 15 张图当判据。
 * ⚠️ 它不是守卫、不进 `npm run smoke`（一个「截图好不好看」的断言只会是假绿）。
 *
 * ⚠️ 它能机器判定的那一半在 `smoke.mjs` 第 14 步：文本重叠守卫 + 横向溢出守卫
 *   （计划 §4.1）。两者是互补的，不是一个代替另一个。
 *
 * ---------------------------------------------------------------------------
 * 怎么跑
 * ---------------------------------------------------------------------------
 *     cd frontend; node scripts/shots.mjs
 * ⚠️ **刻意不挂 `npm run shots`**：那要改 `package.json`，而 Plan 05B 的验收里
 *    有一格是「`package.json` 有没有被改」（它守的是「前后端新增依赖都是 0」这个
 *    从 Plan 01 一路保到今天的纪录）。为了一个截图脚本把那一格验收变成「改过、
 *    但请你自己去 diff 里确认只多了一行 scripts」不值 —— 故用 `node` 直接跑。
 * 需要：① 后端起着（`backend/scripts/demo.ps1`，缺省 `http://127.0.0.1:8000`）
 *       ② 前端起着（`npm run dev`，缺省 `http://localhost:5173` —— ⚠️ 是
 *          `localhost` 不是 `127.0.0.1`：vite 只绑 `::1`）
 *       ③ 一个干净的重演示库（登录要用演示口令；库被 `smoke.mjs` 写脏不影响本脚本，
 *          但「学生 4 的未读/勋章/待交快评」那几格在脏库上可能是空的）
 * 环境变量：`PE_API_BASE` / `PE_WEB_BASE` / `PE_BROWSER` / `PE_SHOTS_DIR`
 *          （缺省把图写进仓库根的 `Document/`）
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 零依赖（与 `smoke.mjs` 第 14 步同一套姿势）
 * ---------------------------------------------------------------------------
 * 不引 Playwright / Puppeteer：Node **24** 自带全局 `WebSocket`，Edge/Chrome 的
 * `--headless=new --remote-debugging-port=0` 会把 DevTools 的 ws 地址打到 stderr，
 * 两者拼起来就是一个够用的 CDP 客户端。本仓前端至今**零新增依赖**（Plan 01–05B）。
 *
 * ⚠️ 三个已知坑（都绕开了）：
 *   ① `--force-prefers-reduced-motion`：让 CSS 动画/过渡立刻落到终态，
 *      否则截到的是「加载中」或动画中途那一帧。⚠️ Plan 05B 删掉了 `StatBlock`
 *      的数字滚动与 4 个图表的 draw/grow，故这一条今天兜的主要是
 *      大屏轮播的 200ms 过渡与那条加载条；
 *   ② 不用 shell 重定向（Node 的 `spawn` 直接收 stdout/stderr）；
 *   ③ 文件名**一律 ASCII**（Plan 04 Task 5 的教训：PowerShell 5.1 读无 BOM UTF-8
 *      的 `.ps1` 会写坏中文名，而截图是要交给人眼复核的，名字坏了就找不着）。
 *
 * ⚠️ 大屏那个 5 秒轮播是 JS 计时器（不受 ① 影响），故本脚本在页面稳定后
 *    **立刻**截图（不等），拍到的一定是第一个教学班。
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const API = process.env.PE_API_BASE ?? 'http://127.0.0.1:8000'
const WEB = process.env.PE_WEB_BASE ?? 'http://localhost:5173'
const OUT = process.env.PE_SHOTS_DIR ?? path.resolve(HERE, '../../Document')

/** **演示口令**。⚠️ 唯一所有者是 `backend/scripts/demo_bootstrap.py` 的
 *  `DEMO_PASSWORD`（与 `smoke.mjs` 同一条纪律：抄一份字面量在联调脚本里，
 *  两处不一致时登录会当场 401，响亮不静默）。 */
const DEMO_PASSWORD = 'pe-demo-2025'
const TEACHER = 'T0001'
const ADMIN = 'T0003'
/** 学生身份用 4（与 `smoke.mjs` 同一个理由：学生 1 的未读/勋章/待交快评全空）。 */
const STUDENT = 4

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const out = (s = '') => process.stdout.write(s + '\n')

/* ==========================================================================
   ① 登录拿 cookie（自己维护一个 jar，与 `smoke.mjs` 同一套姿势）
   ========================================================================== */

/** 从响应头里取出 `pe_session=…`。⚠️ 必须用 `getSetCookie()`：
 *  `headers.get('set-cookie')` 在**多个** `Set-Cookie` 头时会用 `", "` 拼接，
 *  而 cookie 的 `Expires` 值里就有逗号（`Mon, 12 Oct 2026 …`），按逗号切会切坏。
 *  （这是 Plan 05A 查出来的一个坑，本脚本照它的结论写。） */
function cookieFrom(res) {
  const all =
    typeof res.headers.getSetCookie === 'function'
      ? res.headers.getSetCookie()
      : [res.headers.get('set-cookie')].filter(Boolean)
  for (const raw of all) {
    const pair = String(raw).split(';')[0].trim()
    if (pair.startsWith('pe_session=') && pair.length > 'pe_session='.length) return pair
  }
  return null
}

async function api(method, url, { body, cookie } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (cookie) headers.Cookie = cookie
  const res = await fetch(API + url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  })
  const text = await res.text()
  let json = null
  try {
    json = JSON.parse(text)
  } catch {
    /* 不是 JSON（例如 204） */
  }
  return { status: res.status, json, cookie: cookieFrom(res) }
}

async function login(kind, login) {
  const res = await api('POST', '/api/auth/login', {
    body: { kind, login, password: DEMO_PASSWORD },
  })
  if (res.status !== 200 || res.cookie === null) {
    throw new Error(
      `登录失败（${kind}/${login}）：${res.status} ${JSON.stringify(res.json ?? {}).slice(0, 200)}\n` +
        `  ⚠️ 演示口令是 ${DEMO_PASSWORD}；403 password_not_bound 意味着演示库不是刚重灌的` +
        `（请先跑 backend/scripts/demo.ps1）`,
    )
  }
  return res.cookie
}

/* ==========================================================================
   ② 一个**够用**的 CDP 客户端（Node 自带的全局 `WebSocket`，零依赖）
   ========================================================================== */

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
  const workRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pe-shots-cdp-'))
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    // ⚠️ 坑 ①：不加这一条会截到过渡/加载动画的中途帧
    '--force-prefers-reduced-motion',
    '--remote-debugging-port=0',
    `--user-data-dir=${path.join(workRoot, 'profile')}`,
    // ⚠️ 这一行原来写的是「字体要从 Google Fonts 拉，故不能禁网」—— 自交付前收尾波 ②
    //    字体**自托管**之后那句话就是假的（`index.html` 里一个 `<link>` 都没有了）。
    //    `--lang=zh-CN` 本身仍然要留：它决定无头浏览器用哪一套系统中文栈排版，
    //    而中文的度量是本仓布局几何的一格前提（见 tokens.css 的 `--lh-tight`）。
    '--lang=zh-CN',
    'about:blank',
  ]
  const child = spawn(browser, args, { windowsHide: true })
  const wsUrl = await new Promise((resolve, reject) => {
    let stderr = ''
    const timer = setTimeout(
      () => reject(new Error(`30 s 内没等到 DevTools 的 ws 地址；stderr=${stderr.slice(-400)}`)),
      30000,
    )
    child.stderr.on('data', (d) => {
      stderr += d.toString('utf8')
      const m = /DevTools listening on (ws:\/\/\S+)/.exec(stderr)
      if (m !== null) {
        clearTimeout(timer)
        resolve(m[1])
      }
    })
    child.on('error', (err) => {
      clearTimeout(timer)
      reject(err)
    })
    child.on('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`浏览器提前退出（code=${code}）；stderr=${stderr.slice(-400)}`))
    })
  })
  return { child, wsUrl, workRoot, browser }
}

function cdpConnect(wsUrl) {
  if (typeof WebSocket !== 'function') {
    throw new Error('本 Node 没有全局 WebSocket（需要 ≥ 22；实测本机是 ' + process.version + '）')
  }
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl)
    const pending = new Map()
    let nextId = 1
    const api = {
      send(method, params = {}, sessionId) {
        const id = nextId++
        const msg = { id, method, params }
        if (sessionId !== undefined) msg.sessionId = sessionId
        return new Promise((res, rej) => {
          pending.set(id, { res, rej })
          ws.send(JSON.stringify(msg))
        })
      },
      close() {
        try {
          ws.close()
        } catch {
          /* 已经断了 */
        }
      },
    }
    ws.addEventListener('message', (ev) => {
      let msg
      try {
        msg = JSON.parse(typeof ev.data === 'string' ? ev.data : Buffer.from(ev.data).toString('utf8'))
      } catch {
        return
      }
      if (msg.id !== undefined && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id)
        pending.delete(msg.id)
        if (msg.error) rej(new Error(`${msg.error.message ?? JSON.stringify(msg.error)}`))
        else res(msg.result)
      }
    })
    ws.addEventListener('open', () => resolve(api))
    ws.addEventListener('error', () => reject(new Error(`CDP 的 WebSocket 打不开：${wsUrl}`)))
  })
}

/* ==========================================================================
   ③ 主流程
   ========================================================================== */

fs.mkdirSync(OUT, { recursive: true })

out('='.repeat(78))
out('shots —— 15 条路由各截一张图（学生端 375px / 教师端与管理台 1440px）')
out(`  后端 ${API}   前端 ${WEB}   输出 ${OUT}`)
out('='.repeat(78))

// 后端与前端起着吗？
for (const [label, url] of [
  ['后端', API + '/openapi.json'],
  ['前端', WEB + '/'],
]) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(8000) })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    out(`✓ ${label}起着（${url}）`)
  } catch (err) {
    out(`✗ ${label}没起（${url}）：${err?.message ?? err}`)
    out('  处置：后端跑 backend/scripts/demo.ps1；前端跑 cd frontend; npm run dev')
    process.exit(1)
  }
}

/* ⚠️ 名册那四个端点在 Plan 05A 之后**都要教职身份**（`GET /api/students` 逐字
   要 staff；`/api/teachers` 那一格是 05A 顶回来的匿名泄漏，也已收紧），
   故顺序是「先登教师 → 再用他的 cookie 拉名单 → 再登学生」，不能反过来。 */
const teacherJar = await login('teacher', TEACHER)
const teachers = (await api('GET', '/api/teachers?limit=50', { cookie: teacherJar })).json?.items ?? []
const me = teachers.find((t) => t.staff_no === TEACHER)
const sections = (await api('GET', '/api/course-sections?limit=50', { cookie: teacherJar })).json?.items ?? []
const mine = sections.filter((s) => s.teacher_id === me?.id).map((s) => s.id)
const enrollments = (await api('GET', '/api/enrollments?limit=200', { cookie: teacherJar })).json?.items ?? []
const taught = enrollments.filter((e) => mine.includes(e.course_section_id)).map((e) => e.student_id)
const students = (await api('GET', '/api/students?limit=200', { cookie: teacherJar })).json?.items ?? []
const studentNo = students.find((s) => s.id === STUDENT)?.student_no
if (me === undefined || taught[0] === undefined || studentNo === undefined) {
  out(`✗ 真名单算不出来（teacher=${me?.id} taught=${taught[0]} student_no=${studentNo}）`)
  out('  ⚠️ 这通常意味着演示库不是刚重灌的：请先跑 backend/scripts/demo.ps1')
  process.exit(1)
}
out(`✓ 真名单：T0001 = teacher #${me.id}；他名册里的第一个学生 = #${taught[0]}；学生 #${STUDENT} = ${studentNo}`)

const JARS = new Map()
JARS.set('teacher', teacherJar)
JARS.set('admin', await login('teacher', ADMIN))
JARS.set('student', await login('student', studentNo))
out(`✓ 三个身份都登进去了（teacher / admin / student），cookie 各 ${[...JARS.values()].map((c) => c.length).join(' / ')} 字符`)

/** 15 条路由。⚠️ `size` 与 `smoke.mjs` 第 14 步逐字同档（375 / 1440），
 *  于是「截图看到的」与「重叠守卫量到的」是同一个视口。
 *  ⚠️ `mirror`：导航**之前**用 `Page.addScriptToEvaluateOnNewDocument` 把
 *  `stores/identity` 的 localStorage 镜像写好。理由（实测，不是猜）：
 *  直接种 cookie 打开业务路由时，页面第一帧的 `identity.studentId` 还是 null，
 *  要等 `GET /api/auth/me` 回来由 `session.adopt()` 回写镜像；而 DEV 切换器的
 *  `devRole` 计算属性在这个窗口里会把身份设成「名册第一行」（学生 1），
 *  于是一个学生会话去读学生 1 的行 → 403 forbidden → 横幅盖住整页、
 *  正文空白（本波实测复现，`mirror` 最终又会被 adopt 写回 4，故日志里看不出来）。
 *  一个**真的登录过的用户**刷新页面时镜像本来就在 localStorage 里，
 *  故先写镜像不是造假，而是把截图对齐「登录过的用户打开这个 URL」的真实形态。
 *  ⚠️ 根因在 `stores/session.ts` 与 `IdentitySwitcher.vue` 的 DEV 半之间的竞态，
 *  而 `src/stores/**` 在 Plan 05B 的禁改清单里 → 本波只绕开、不修，已记进报告待清扫。 */
const MIRROR = {
  student: {
    role: 'student',
    studentId: STUDENT,
    studentLabel: `${studentNo} ${students.find((s) => s.id === STUDENT)?.name ?? ''}`.trim(),
    teacherStaffNo: null,
    teacherLabel: null,
    asOf: '2025-10-12',
  },
  teacher: {
    role: 'teacher',
    studentId: null,
    studentLabel: null,
    teacherStaffNo: TEACHER,
    teacherLabel: teachers.find((t) => t.staff_no === TEACHER)?.name ?? null,
    asOf: '2025-10-12',
  },
  admin: {
    role: 'teacher',
    studentId: null,
    studentLabel: null,
    teacherStaffNo: ADMIN,
    teacherLabel: teachers.find((t) => t.staff_no === ADMIN)?.name ?? null,
    asOf: '2025-10-12',
  },
}

const ROUTES = [
  { name: 'login', url: '/login', jar: null, size: [1440, 1200] },
  { name: 'bind', url: '/bind', jar: null, size: [1440, 1400] },
  { name: 's-home', url: '/s/home', jar: 'student', size: [375, 2400] },
  { name: 's-weekly-sheet', url: '/s/weekly-sheet', jar: 'student', size: [375, 2600] },
  { name: 's-check-in', url: '/s/check-in', jar: 'student', size: [375, 2400] },
  { name: 's-rpe', url: '/s/rpe', jar: 'student', size: [375, 2400] },
  { name: 's-mini-test', url: '/s/mini-test', jar: 'student', size: [375, 2400] },
  { name: 's-notifications', url: '/s/notifications', jar: 'student', size: [375, 2000] },
  { name: 't-dashboard', url: '/t/dashboard', jar: 'teacher', size: [1440, 2200] },
  { name: 't-report', url: '/t/report', jar: 'teacher', size: [1440, 2600] },
  { name: 't-alerts', url: '/t/alerts', jar: 'teacher', size: [1440, 2200] },
  { name: 't-student-detail', url: `/t/students/${taught[0]}`, jar: 'teacher', size: [1440, 2600] },
  { name: 'admin-index', url: '/admin', jar: 'admin', size: [1440, 2600] },
  { name: 'admin-list', url: '/admin/students', jar: 'admin', size: [1440, 1800] },
  { name: 'admin-detail', url: `/admin/students/${STUDENT}`, jar: 'admin', size: [1440, 2000] },
]
if (ROUTES.length !== 15) throw new Error(`路由条数应当是 15，实测 ${ROUTES.length}`)

const headless = await spawnHeadless()
out(`✓ 无头浏览器起来了（${path.basename(headless.browser)}）`)
const cdp = await cdpConnect(headless.wsUrl)

/** 页面稳定了没有：① 没有「加载中」那一格了 ② 字体加载完了 ③ 至少渲染出正文
 *  ④ **图片都到位了**（品牌与密度波加的一格）。
 *  ⚠️ ④ 不是多余的：本波起报头与登录页各挂一个 `<img>`（厦门大学的校徽与嘉庚体校名，
 *  52 095 B / 15 975 B 的 svg），而 `Page.captureScreenshot` **不等**图片 ——
 *  它只等 `sleep(500)`。一个没到的图片在截图上是一块**空白**，而空白在交付图上
 *  看起来就像「品牌没做」，且没有任何守卫会报（`smoke.mjs` 第 14 步的谓词只看文本）。
 *  `img.complete` 对「已经在缓存里」与「解码完了」两种情况都为真，故它是够用的一格。 */
const SETTLE = `(() => {
  const loading = document.querySelectorAll('.s-loading, .t-loading').length
  const fonts = document.fonts ? document.fonts.status : 'loaded'
  const bytes = document.body ? document.body.innerText.length : 0
  const pendingImages = [...document.images].filter((i) => !i.complete).length
  return JSON.stringify({ loading, fonts, bytes, pendingImages, ready: document.readyState })
})()`

/** ⚠️ **每条路由开一个新标签页**（而不是一个标签页里串行导航）：
 *  `ApiErrorBanner` 是模块级单例、`stores/identity` 是持久化镜像，
 *  一个标签页里「上一条路由的残留状态」会漏进下一条路由的截图
 *  （实测：`/bind` → `/s/home` 串行时，s-home 的截图上挂着一条
 *  与本页无关的 403 横幅）。人眼复核要的是「直接打开这个 URL 看到的样子」，
 *  故一条路由 = 一次全新的页面加载。 */
async function shootRoute(route, index) {
  const [width, height] = route.size
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true })
  await cdp.send('Page.enable', {}, sessionId)
  await cdp.send('Runtime.enable', {}, sessionId)
  await cdp.send('Network.enable', {}, sessionId)
  await cdp.send('Network.clearBrowserCookies', {}, sessionId)
  if (route.jar !== null) {
    const value = JARS.get(route.jar).slice('pe_session='.length)
    const set = await cdp.send(
      'Network.setCookie',
      { name: 'pe_session', value, url: WEB, httpOnly: true, sameSite: 'Lax' },
      sessionId,
    )
    if (set?.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(set)}`)
  }
  await cdp.send(
    'Emulation.setDeviceMetricsOverride',
    { width, height, deviceScaleFactor: 1, mobile: false },
    sessionId,
  )
  if (route.jar !== null) {
    await cdp.send(
      'Page.addScriptToEvaluateOnNewDocument',
      {
        source: `localStorage.setItem('pe.identity.v1', ${JSON.stringify(JSON.stringify(MIRROR[route.jar]))});`,
      },
      sessionId,
    )
  }
  await cdp.send('Page.navigate', { url: WEB + route.url }, sessionId)

  // 轮询到「加载中」消失且字体就绪（上限 45 s，与 smoke 第 14 步同档）
  const deadline = Date.now() + 45000
  let state = {}
  for (;;) {
    const res = await cdp.send('Runtime.evaluate', { expression: SETTLE, returnByValue: true }, sessionId)
    try {
      state = JSON.parse(String(res?.result?.value ?? '{}'))
    } catch {
      state = {}
    }
    if (state.loading === 0 && state.fonts === 'loaded' && state.bytes > 200
      && state.pendingImages === 0) break
    if (Date.now() > deadline) break
    await sleep(300)
  }
  await sleep(500) // 让最后一批数据渲染完（轮播/图表的过渡是 200–240ms）

  const at = await cdp.send(
    'Runtime.evaluate',
    { expression: 'location.pathname + location.search', returnByValue: true },
    sessionId,
  )
  /* ⚠️ 把身份镜像也打出来：`stores/identity` 是持久化的（localStorage），而 13 个
     业务页面从它读「我是谁」。截图上若挂着一条 403 横幅，第一嫌疑人就是
     「镜像里的 id 与会话里的 id 不一致」—— 这一格让那种失效在日志里看得见。 */
  const mirror = await cdp.send(
    'Runtime.evaluate',
    { expression: 'localStorage.getItem("pe.identity.v1") ?? "(none)"', returnByValue: true },
    sessionId,
  )
  /* ⚠️ 把本页实际发出的 /api/* 请求与其状态码也打出来：截图上若挂着横幅，
     这一格直接说出是哪一个请求、几号状态码（比人眼读截图快一个量级）。 */
  const reqs = await cdp.send(
    'Runtime.evaluate',
    {
      expression:
        "JSON.stringify(performance.getEntriesByType('resource')" +
        ".filter((e) => e.name.includes('/api/'))" +
        ".map((e) => e.name.replace(location.origin, '') + ' → ' + e.responseStatus))",
      returnByValue: true,
    },
    sessionId,
  )
  const reqList = JSON.parse(String(reqs?.result?.value ?? '[]'))
  let mirrorBrief = '(none)'
  try {
    const m = JSON.parse(String(mirror?.result?.value ?? '"(none)"'))
    mirrorBrief = m === null ? '(none)' : `${m.role ?? '-'}#${m.studentId ?? m.teacherStaffNo ?? '-'}`
  } catch {
    mirrorBrief = String(mirror?.result?.value ?? '').slice(0, 40)
  }
  const shot = await cdp.send(
    'Page.captureScreenshot',
    { format: 'png', captureBeyondViewport: true, fromSurface: true },
    sessionId,
  )
  const file = path.join(OUT, `shot-${String(index).padStart(2, '0')}-${route.name}.png`)
  fs.writeFileSync(file, Buffer.from(shot.data, 'base64'))
  const kb = (fs.statSync(file).size / 1024).toFixed(1)
  out(
    `  → ${route.name.padEnd(18)} ${String(width).padStart(4)}px  ` +
      `location=${String(at?.result?.value ?? '')}  mirror=${mirrorBrief}  ` +
      `loading=${state.loading} fonts=${state.fonts} text=${state.bytes} `
      + `imgs待=${state.pendingImages}  ` +
      `${path.basename(file)} ${kb} kB`,
  )
  for (const r of reqList) out(`      · ${r}`)
  await cdp.send('Target.closeTarget', { targetId })
  return file
}

let index = 0
const written = []
for (const route of ROUTES) {
  index += 1
  written.push(await shootRoute(route, index))
}

cdp.close()
const exited = await new Promise((resolve) => {
  const timer = setTimeout(() => resolve(false), 5000)
  headless.child.once('exit', () => {
    clearTimeout(timer)
    resolve(true)
  })
  headless.child.kill('SIGKILL')
})
try {
  fs.rmSync(headless.workRoot, { recursive: true, force: true, maxRetries: 10, retryDelay: 400 })
} catch {
  /* 一个留在 $env:TEMP 下的空目录不是本脚本要证的事 */
}

out('')
out(`✓ ${written.length} / ${ROUTES.length} 张截图写进 ${OUT}（浏览器已退出：${exited}）`)
for (const f of written) out(`    · ${f}`)
process.exit(written.length === ROUTES.length ? 0 : 1)
