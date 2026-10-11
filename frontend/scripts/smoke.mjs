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
 * 退出码 **0** = 16 步全绿。任何一步的任何一条断言红了都是 **1**。
 *
 * 环境变量（都有缺省值）：
 *   `PE_API_BASE`   后端基址，缺省 `http://127.0.0.1:8000`
 *   `PE_WEB_BASE`   前端基址，缺省 `http://localhost:5173`
 *                   ⚠️ 是 `localhost` 不是 `127.0.0.1`：vite 只绑 `::1`
 *   `PE_BROWSER`    无头浏览器的可执行文件（缺省在几个常见路径里找）
 *   `PE_SMOKE_TRANSCRIPT`  给了就把每一步的请求/响应原文写成 JSON
 *                   （`Document/2026-10-11-前后端联调取证.md` 由它生成）
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
 * ⚠️ 16 步（0–15）与本文件里那 16 个 `step(...)` 逐一对应
 * ---------------------------------------------------------------------------
 * 第 14 步（13 条路由的 DOM 取证）**不能**用 HTTP 代替：它证明的是「Vue 真的
 * 渲染出来了、而且渲染的是后端给的那份数据」，而 `fetch` 只证明 API 通。
 * 故它在本脚本里**真的起一个无头浏览器**（`child_process.spawn` + `--dump-dom`），
 * 于是「16 步全绿」与「退出码 0」仍然是一件事。
 * ⚠️ 三个坑（Plan 04 Task 2/3 踩过，本脚本逐个绕开）：
 *  ① 必须 `--force-prefers-reduced-motion`，否则抓到 `StatBlock` 数字滚动**中途**
 *     那一帧（Task 2 实测到 95.7 而不是 100.0）；
 *  ② PowerShell 的 `& msedge … > file` 会得到 **0 字节** → 本脚本用 Node 的
 *     `spawn` 直接收 stdout，不经过 shell 重定向；
 *  ③ vite 只绑 `::1` → 基址是 `localhost`。
 *
 * ⚠️ **第 15 步（Plan 04 收尾波加的）不需要后端也不需要前端**：它 `spawn` 一次
 * `node scripts/check-tokens.mjs`（色值唯一住址的守卫，Plan 05 换肤的前置条件）。
 * 把它挂在这里的理由是「`npm run smoke` 全绿」应当**蕴含**「设计令牌没有散开」，
 * 而它自己也可以单独跑（`npm run check:tokens`，零依赖、不碰网络）。
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
/** 教师身份（3 个之一：T0001 陈国华 / T0002 林慧敏 / T0003 赵志刚）。 */
const TEACHER = 'T0001'
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

const TEACHER_HEADER = { 'X-Teacher-Staff-No': TEACHER }
const studentHeader = (id = STUDENT) => ({ 'X-Student-Id': String(id) })

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
 * @param {object} [opts.headers]  身份头
 * @param {boolean} [opts.record]  缺省 true；`/openapi.json` 那种 278 KB 的响应传 false
 * @param {boolean} [opts.quiet]   不把响应体打到 stdout（transcript 里仍然全量）
 */
async function req(method, urlPath, opts = {}) {
  const url = urlPath.startsWith('http') ? urlPath : API + urlPath
  const headers = { Accept: 'application/json', ...(opts.headers ?? {}) }
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
    requestHeaders: headers,
    requestBody: opts.body ?? null,
    status: res.status,
    responseBodyBytes: Buffer.byteLength(text, 'utf8'),
    responseBody: opts.record === false ? `__omitted__ (${Buffer.byteLength(text, 'utf8')} bytes)` : text,
  }
  CURRENT.exchanges.push(record)

  out(`  → ${method} ${url}`)
  const identityHeader = Object.keys(headers).find((k) => k.toLowerCase().startsWith('x-'))
  out(`    身份头: ${identityHeader ? `${identityHeader}: ${headers[identityHeader]}` : '（匿名）'}`)
  if (opts.body !== undefined) out(`    请求体: ${JSON.stringify(opts.body)}`)
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

/** 一个泛型 list 端点的 `total`（⚠️ 信封是 4 个键：items/limit/offset/total）。 */
async function totalOf(resource) {
  const res = await req('GET', `/api/${resource}?limit=1`, { quiet: true })
  return res.json?.total ?? null
}

/* ==========================================================================
   15 步
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

await step(0, '演示库复原核实（⚠️ 跑本脚本之前一律先重跑 backend/scripts/demo.ps1）', async () => {
  // 7 张表的行数 = demo_bootstrap.py 第 [6/6] 步「全部从库里数出来」的那一份。
  const expected = {
    students: 60,
    notifications: 19,
    prescriptions: 60,
    'training-logs': 840,
    'rpe-records': 240,
    'weekly-class-reports': 5,
    // ⚠️ **32 而不是 30**（Plan 04 收尾波改的）：`GREEN_MASTERY` 与
    //    `RED_MINITEST_DROP` 的综合分此前读 `mini_test.normalized_score` 那一列
    //    （演示库上由 `demo_data` 灌成近似值），本波改成了与进步榜**同一个算式**
    //    现算（`app.domain.report.mini_test_scores`）→ 红牌里的小测下降从 5 条变 7 条。
    //    ⚠️ 新分布是 `demo.ps1` 重灌之后**实测**出来的（第 [6/6] 步「预警按规则」
    //    那一行逐字是 `{GREEN_MASTERY: 13, RED_MINITEST_DROP: 7,
    //    RED_RPE_SUSTAINED: 6, YELLOW_CHECKIN_GAP: 6}`），不是推出来的。
    alerts: 32,
  }
  for (const [resource, want] of Object.entries(expected)) {
    eq(`${resource} 的行数`, await totalOf(resource), want)
  }
  const alerts = await req('GET', '/api/alerts?limit=200', { quiet: true })
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

await step(1, 'GET /api/health → tables == 25 且 students > 0', async () => {
  const res = await req('GET', '/api/health')
  eq('200', res.status, 200)
  eq('status == ok', res.json?.status, 'ok')
  eq('tables == 25', res.json?.tables, 25)
  check('students > 0', (res.json?.students ?? 0) > 0, `students=${res.json?.students}`)
  // ⚠️ /api/health 是「24 个未定型响应」里唯一不是 list 的那一个，
  //    故它的形状由 api/types.ts 手写补上（约束第 5 条）。
  eq('响应恰好 3 个键（未定型 → 前端手写的 HealthRead）',
    Object.keys(res.json ?? {}).sort().join(','), 'status,students,tables')
})

await step(2, '教师头 POST /api/class-sessions → 201 且响应里没有 rpe_token', async () => {
  const sections = await req('GET', '/api/course-sections?limit=5', { quiet: true })
  const sectionId = sections.json.items[0].id
  SHARED.sectionId = sectionId
  const res = await req('POST', '/api/class-sessions', {
    headers: TEACHER_HEADER,
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

  // 匿名写 → 401（fix 波 1 给 9 个可写资源的写入侧全挂上了 require_teacher）
  const anon = await req('POST', '/api/class-sessions', {
    body: { course_section_id: sectionId, session_date: NEW_SESSION_DATE, period: 6 },
  })
  eq('匿名 POST → 401', anon.status, 401)
  eq('匿名 POST 的 code 是 unauthenticated', codeOf(anon), 'unauthenticated')
})

await step(3, '教师头 open-rpe 拿到口令；匿名 GET /api/class-sessions 的响应体里不含那串口令', async () => {
  const res = await req('POST', `/api/class-sessions/${SHARED.sessionId}/open-rpe`, {
    headers: TEACHER_HEADER,
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
    headers: TEACHER_HEADER,
  })
  eq('教师头 → 200', asTeacher.status, 200)
  eq('口令与第 3 步逐字相同（open-rpe 不重新生成）', asTeacher.json?.rpe_token, SHARED.token)
  eq('响应恰好 2 个键', Object.keys(asTeacher.json ?? {}).sort().join(','), 'class_session_id,rpe_token')

  // ⚠️ 约束第 16 条：没发起过快评的课次读口令是 **409 rpe_not_opened**（不是 404、不是 null）
  const fresh = await req('POST', '/api/class-sessions', {
    headers: TEACHER_HEADER,
    body: { course_section_id: SHARED.sectionId, session_date: NEW_SESSION_DATE, period: 7 },
  })
  SHARED.unopenedSessionId = fresh.json?.id ?? null
  const notOpened = await req('GET', `/api/class-sessions/${SHARED.unopenedSessionId}/rpe-token`, {
    headers: TEACHER_HEADER,
  })
  eq('未发起的课次读口令 → 409', notOpened.status, 409)
  eq('那一档的 code 是 rpe_not_opened', codeOf(notOpened), 'rpe_not_opened')
})

await step(5, '学生头 POST /api/rpe-records（带第 3 步的口令）→ 201；再交一次 → 409 integrity_conflict', async () => {
  const res = await req('POST', '/api/rpe-records', {
    headers: studentHeader(),
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
    headers: studentHeader(),
    body: { class_session_id: SHARED.sessionId, rpe: 9, rpe_token: SHARED.token },
  })
  eq('再交一次 → 409', again.status, 409)
  eq('code 是 integrity_conflict（不是 rpe_already_submitted）', codeOf(again), 'integrity_conflict')

  // 口令错了是 403 invalid_rpe_token（⚠️ 与「没发起」那一档不同码）
  const wrongToken = await req('POST', '/api/rpe-records', {
    headers: studentHeader(5),
    body: { class_session_id: SHARED.sessionId, rpe: 6, rpe_token: 'not-the-real-token' },
  })
  eq('口令错 → 403', wrongToken.status, 403)
  eq('code 是 invalid_rpe_token', codeOf(wrongToken), 'invalid_rpe_token')
})

await step(6, '学生头 POST /api/training-logs → 201 且 submitted_at / late / source / batch_id 都是服务端填的', async () => {
  const body = { log_date: NEW_LOG_DATE, completed: true, duration_min: 42, feeling: 'moderate' }
  const res = await req('POST', '/api/training-logs', { headers: studentHeader(), body })
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

  const again = await req('POST', '/api/training-logs', { headers: studentHeader(), body })
  eq('同一天再打一次 → 409（uq_training_log_student_day）', again.status, 409)
  eq('code 是 integrity_conflict', codeOf(again), 'integrity_conflict')
})

await step(7, `学生头 GET /api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF} → factor 与 sessions[].blocks 非空`, async () => {
  const res = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    headers: studentHeader(),
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

  // ⚠️ 约束第 14 条：教师用自己的头调**学生侧**那个端点是 401（不是 403）
  const asTeacher = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
  })
  eq('教师头调学生侧的 weekly-sheet → 401', asTeacher.status, 401)
  eq('code 是 unauthenticated', codeOf(asTeacher), 'unauthenticated')

  // ⚠️ 教师侧的变体只对**他本学期任教的学生**开放（`require_teaches_student`）。
  //    故这里从数据里**现找**一个 T0001 教的学生，而不是拿学生 4 硬试：
  //    实测学生 4 不在 T0001 的班里（下面那一拍专门断言这个 403）。
  const teachers = (await req('GET', '/api/teachers?limit=50', { quiet: true })).json?.items ?? []
  const me = teachers.find((t) => t.staff_no === TEACHER)
  const sections = (await req('GET', '/api/course-sections?limit=50', { quiet: true })).json?.items ?? []
  const mine = sections.filter((s) => s.teacher_id === me?.id).map((s) => s.id)
  const enrollments = (await req('GET', '/api/enrollments?limit=200', { quiet: true })).json?.items ?? []
  const taught = enrollments.filter((e) => mine.includes(e.course_section_id)).map((e) => e.student_id)
  SHARED.teacherId = me?.id ?? null
  SHARED.mySections = mine
  SHARED.taughtStudent = taught[0] ?? null
  out(`    ${TEACHER} = teacher #${me?.id}（${me?.name}），任教 ${mine.length} 个班、名册 ${taught.length} 人`)
  check('找得到一个 T0001 本学期任教的学生', SHARED.taughtStudent !== null, `student_id=${SHARED.taughtStudent}`)

  const asStudent = await req('GET', `/api/students/${SHARED.taughtStudent}/weekly-sheet?as_of=${AS_OF}`, {
    headers: studentHeader(SHARED.taughtStudent),
    quiet: true,
  })
  const teacherVariant = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/weekly-sheet?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
    quiet: true,
  })
  eq('学生侧（本人头）→ 200', asStudent.status, 200)
  eq('教师侧变体 → 200', teacherVariant.status, 200)
  eq('两个变体的响应体**逐字相同**（后端把函数体抽成了 _weekly_sheet_response）',
    teacherVariant.text, asStudent.text)

  // 不在自己班里的学生 → 403 forbidden（判据是 enrollment ⋈ course_section.teacher_id）
  const notMine = await req('GET', `/api/teacher/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
  })
  check(`学生 ${STUDENT} 不在 ${TEACHER} 本学期任教的班里 → 403`, notMine.status === 403,
    `status=${notMine.status}`)
  eq('code 是 forbidden', codeOf(notMine), 'forbidden')

  // 越权：学生 5 的头去读学生 4 的训练单
  const cross = await req('GET', `/api/students/${STUDENT}/weekly-sheet?as_of=${AS_OF}`, {
    headers: studentHeader(5),
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
    headers: studentHeader(SHARED.taughtStudent),
    quiet: true,
  })
  const homeAsTeacher = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
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
  const alertRows = (await req('GET', '/api/alerts?limit=200', { quiet: true })).json?.items ?? []
  const greenHolders = alertRows.filter((a) => a.rule_id === 'GREEN_MASTERY').map((a) => a.student_id)
  const badged = greenHolders.find((id) => taught.includes(id)) ?? null
  check('找得到一个「有绿牌 ∧ 由 T0001 本学期任教」的学生', badged !== null,
    `绿牌 ${greenHolders.length} 人，其中 T0001 任教的 ${greenHolders.filter((id) => taught.includes(id)).length} 人`)
  if (badged !== null) {
    const badgedHome = await req('GET', `/api/teacher/students/${badged}/home?as_of=${AS_OF}`, {
      headers: TEACHER_HEADER, quiet: true,
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
      headers: TEACHER_HEADER, quiet: true,
    })
    eq(`学生 ${classmate} 的教师侧 /home（as_of=${NEW_SESSION_DATE}）→ 200`, pendingHome.status, 200)
    const pending = pendingHome.json?.pending_rpe ?? []
    check('④ pending_rpe 里出现了第 2 步建、第 3 步发起快评的那一节课（他没交）',
      pending.some((p) => p.class_session_id === SHARED.sessionId),
      `pending=${fmt(pending)}`)
    // ⚠️ 反证：交了的那个人（学生 4）在同一节课上**不该**还有待办。
    //    走学生侧那一条（他本人调它是 200），响应体与教师侧逐字相同。
    const submitted = await req('GET', `/api/students/${STUDENT}/home?as_of=${NEW_SESSION_DATE}`, {
      headers: studentHeader(STUDENT), quiet: true,
    })
    eq(`学生 ${STUDENT}（第 5 步交过那一节课的快评）的学生侧 /home → 200`, submitted.status, 200)
    check('反证：他的 pending_rpe 里**没有**那一节课（交了就不该再挂在待办上）',
      !(submitted.json?.pending_rpe ?? []).some((p) => p.class_session_id === SHARED.sessionId),
      `pending=${fmt(submitted.json?.pending_rpe)}`)
  }

  // 教师侧 /home 的三档身份：不任教 → 403、学生头 → 401、匿名 → 401
  const homeNotMine = await req('GET', `/api/teacher/students/${STUDENT}/home?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
  })
  check(`学生 ${STUDENT} 不在 ${TEACHER} 本学期任教的班里 → /home 也是 403`,
    homeNotMine.status === 403, `status=${homeNotMine.status}`)
  eq('code 是 forbidden', codeOf(homeNotMine), 'forbidden')
  const homeWithStudentHeader = await req(
    'GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`,
    { headers: studentHeader(SHARED.taughtStudent) })
  eq('学生头调教师侧 /home → 401', homeWithStudentHeader.status, 401)
  eq('code 是 unauthenticated', codeOf(homeWithStudentHeader), 'unauthenticated')
  const homeAnon = await req('GET', `/api/teacher/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`)
  eq('匿名调教师侧 /home → 401', homeAnon.status, 401)
  eq('匿名的 code 也是 unauthenticated', codeOf(homeAnon), 'unauthenticated')
  // ⚠️ 而学生侧那一条路径**今天仍然**是 401（那不是缺陷，是「一个端点一道闸门」）
  const teacherOnStudentHome = await req('GET', `/api/students/${SHARED.taughtStudent}/home?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
  })
  eq('教师头调**学生侧** /home → 仍然 401（故必须有变体）', teacherOnStudentHome.status, 401)
})

await step(8, '教师头 dashboard：三层完成率不是全 0、progress_board 非空', async () => {
  const dash = await req('GET', `/api/dashboard/class/${SHARED.sectionId}?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
  })
  eq('class dashboard → 200', dash.status, 200)
  check('响应非空对象', dash.json !== null && typeof dash.json === 'object', `键=${Object.keys(dash.json ?? {}).join(',')}`)

  const report = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
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
    headers: TEACHER_HEADER,
    quiet: true,
  })
  eq('⚠️ ?as_of= 在本端点被静默忽略（它只认 week）→ 仍然 200', ignored.status, 200)
  eq('忽略之后回的是「已存下来的最新一周」= 第 6 周', ignored.json?.week, 6)

  const explicit = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?week=6`, {
    headers: TEACHER_HEADER,
    quiet: true,
  })
  eq('?week=6 → 200', explicit.status, 200)
  eq('回的确实是第 6 周', explicit.json?.week, 6)

  const noReport = await req('GET', `/api/dashboard/weekly-class-report/${SHARED.sectionId}?week=7`, {
    headers: TEACHER_HEADER,
  })
  eq('?week=7（那一周还没到周日）→ 404', noReport.status, 404)
  eq('code 是 no_weekly_report（不是通用的 not_found）', codeOf(noReport), 'no_weekly_report')
})

await step(9, '预警处置：reduce_20pct → 200；再处置 → 409 alert_not_pending；非法 action → 422 且点名合法值', async () => {
  const list = await req('GET', '/api/alerts?limit=200', { quiet: true })
  const rows = list.json?.items ?? []
  const pendingRed = rows.find((r) => r.level === 'red' && r.status === 'pending')
  check('有 pending 的红色预警', pendingRed !== undefined, `共 ${rows.length} 行`)
  SHARED.alertId = pendingRed?.id ?? null
  out(`    挑中 alert #${SHARED.alertId} rule_id=${pendingRed?.rule_id} student_id=${pendingRed?.student_id}`)

  // ⚠️ 约束第 17 条（Task 3 顶回的那一处）：三档的**真值**是
  //    ['ignore','note','reduce_20pct']，而计划正文写的 ACTION_REDUCE / ACTION_IGNORE /
  //    ACTION_NOTE 是 app/api/routers/alerts.py 里的**常量名**，送上去是 422。
  const res = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
    body: { action: 'reduce_20pct' },
  })
  eq('处置 → 200', res.status, 200)
  eq('alert.status 变成 handled', res.json?.alert?.status ?? res.json?.status, 'handled')
  out(`    adjustment=${fmt(res.json?.adjustment)}`)
  out(`    notification=${fmt(res.json?.notification)?.slice(0, 160)}`)

  const again = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
    body: { action: 'ignore' },
  })
  eq('再处置一次 → 409', again.status, 409)
  eq('code 是 alert_not_pending', codeOf(again), 'alert_not_pending')

  // ⚠️ 「枚举不在契约里」时唯一能做的机器守卫：送一个非法值，
  //    断言 422 **并且响应里点名了三档合法值**。
  const bad = await req('POST', `/api/alerts/${SHARED.alertId}/handle?as_of=${AS_OF}`, {
    headers: TEACHER_HEADER,
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
      headers: TEACHER_HEADER,
      body: action === 'note' ? { action, note: '联调脚本写的备注' } : { action },
      quiet: true,
    })
    eq(`action=${action} 被接受 → 200`, r.status, 200)
  }
  // note 而备注为空 → 422（约束：这一档的闸门在 domain 层）
  const noteTarget = rest.shift()
  if (noteTarget) {
    const r = await req('POST', `/api/alerts/${noteTarget.id}/handle?as_of=${AS_OF}`, {
      headers: TEACHER_HEADER,
      body: { action: 'note', note: '   ' },
    })
    eq("action=note 而 note 是空白 → 422", r.status, 422)
  }
})

await step(10, '写入侧强制：匿名 POST /api/semesters → 401；教师头 → 201；⚠️ DELETE 是 405 不是 204', async () => {
  const body = { name: '联调脚本建的学期（删不掉，见下面）', start_date: '2026-02-23', end_date: '2026-07-05', weeks: 18 }
  const anon = await req('POST', '/api/semesters', { body })
  eq('匿名 → 401', anon.status, 401)
  eq('code 是 unauthenticated', codeOf(anon), 'unauthenticated')

  const asTeacher = await req('POST', '/api/semesters', { headers: TEACHER_HEADER, body })
  eq('教师头 → 201', asTeacher.status, 201)
  const semesterId = asTeacher.json?.id ?? null
  check('拿到了 id', Number.isInteger(semesterId), `id=${semesterId}`)

  // ⚠️⚠️ **顶回派单第 10 步**：派单写的是「再 DELETE 它 → 断言 204」。
  //    实测 `semesters` 是 23 行里唯一「**可写 + on_delete='forbid'**」的资源，
  //    后端**根本不注册** DELETE 端点 → 打过去是 **405 http_405**。
  //    （派单第 12 步自己也写了「`semesters` 除外，它是 `forbid` 故没有 DELETE」。）
  const del = await req('DELETE', `/api/semesters/${semesterId}`, { headers: TEACHER_HEADER })
  eq('DELETE /api/semesters/{id} → 405（不是 204）', del.status, 405)
  eq('code 是 http_405', codeOf(del), 'http_405')

  // 故「建了再删掉、拿到一个真的 204」这一拍换一个 restrict 的资源来做：teachers
  const created = await req('POST', '/api/teachers', {
    headers: TEACHER_HEADER,
    body: { staff_no: 'SMOKE01', name: '联调脚本建的教师' },
  })
  eq('POST /api/teachers → 201', created.status, 201)
  const teacherId = created.json?.id ?? null
  const removed = await req('DELETE', `/api/teachers/${teacherId}`, { headers: TEACHER_HEADER })
  eq('DELETE /api/teachers/{id} → 204', removed.status, 204)
  eq('204 没有响应体', removed.text, '')

  // restrict：删一行被子表指着的学生 → 409，且 message 点名了子表
  const restricted = await req('DELETE', `/api/students/${STUDENT}`, { headers: TEACHER_HEADER })
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
    headers: TEACHER_HEADER,
    body: { student_id: STUDENT },
  })
  eq('**教师头**也一样是 405（端点根本不注册，与身份无关）', asTeacher.status, 405)
  eq('code 是 http_405', codeOf(asTeacher), 'http_405')

  const del = await req('DELETE', '/api/alerts/1', { headers: TEACHER_HEADER })
  eq('DELETE 一个 forbid 的资源 → 405', del.status, 405)
  eq('code 是 http_405', codeOf(del), 'http_405')
})

/* ------------------------------------------------------------------ 第 12 步
   ⚠️ 从 /openapi.json **反查** catalog/resources.ts 的 23 行（计划第 4 节要求的守卫）。
   目录是用 Node 的类型剥离**直接 import 那个 .ts 文件**读出来的
   （`import type` 会被擦掉，故它不需要 vite / tsc）—— 不是正则抠源码文本，
   于是「目录里到底写了什么」这一侧也是运行时口径。                       */
await step(12, '从 /openapi.json 反查 catalog/resources.ts 的 23 行（5 拍）', async () => {
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
  // ⚠️ **这五格在 Plan 04 的 5 个 Task + 收尾波里变了 4 次**，故每一格都写明了
  //    「上一次是多少、这一次为什么变」。收尾波这一次：+ `GET /api/teacher/students/{id}/home`
  //    （Task 3 顶回的那一条落地：学生侧的 `/home` 挂学生头、教师调它 401）。
  //    ⚠️ 它是**挂 security 的 GET**，故「匿名 GET」那一格**不动**（48）——
  //    本仓「读 ⇒ 一律匿名」的口径没有被它推翻，它挂 security 的理由与
  //    `weekly-sheet` 那一对逐字相同（一个**按人**收窄的读端点，收窄判据本身就是身份）。
  eq('路径模板 66 个（收尾波 65 → 66）', apiPaths.length, 66)
  eq('操作 94 个（收尾波 93 → 94）', ops, 94)
  eq('挂 security 的 46 个（收尾波 45 → 46 = 20 特例 + 26 CRUD 写入）', secured, 46)
  eq('GET 59 个（收尾波 58 → 59）', gets, 59)
  eq('其中匿名 GET 48 个（**不变**：新加的那一个是挂 security 的窄读）', getsAnon, 48)
})

await step(13, '学生端那两个新端点：/api/students/{id}/notifications 与 /api/mini-tests/normalized', async () => {
  // ⚠️ 这两个端点是 Plan 04 Task 3 的后端小修波加的 / 摘的：
  //    前者是新加的窄端点（学生头、裸数组、服务端已过滤 + 已排序），
  //    后者是**摘掉了教师头**（改成匿名）。
  const mine = await req('GET', `/api/students/${STUDENT}/notifications`, { headers: studentHeader() })
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

  const cross = await req('GET', `/api/students/${STUDENT}/notifications`, { headers: studentHeader(5) })
  eq('越权（学生 5 读学生 4 的）→ 403', cross.status, 403)
  eq('code 是 forbidden', codeOf(cross), 'forbidden')

  const asTeacher = await req('GET', `/api/students/${STUDENT}/notifications`, { headers: TEACHER_HEADER })
  eq('教师头 → 401（本端点只做学生侧）', asTeacher.status, 401)

  const normalized = await req('GET', '/api/mini-tests/normalized?semester_id=2&week=6', { quiet: true })
  eq('mini-tests/normalized 匿名 → 200（fix 波摘掉了教师头）', normalized.status, 200)
  // ⚠️ `scored_count` **不在顶层**：响应体是
  //    `{semester_id, week, sections: [{course_section_id, scored_count, entries: [...]}]}`。
  const sections = normalized.json?.sections ?? []
  check('sections 非空', sections.length > 0, `${sections.length} 个班`)
  check('每个班都带 scored_count（约束第 11 条：== 1 时前端要显示「无排名」）',
    sections.length > 0 && sections.every((s) => typeof s.scored_count === 'number'),
    `scored_count=${JSON.stringify(sections.map((s) => s.scored_count))}`)
  check('entries 里每一项都有 composite（班内百分位的输入）',
    sections.every((s) => Array.isArray(s.entries) && s.entries.every((e) => typeof e.composite === 'number')),
    `第一个班 ${sections[0]?.entries?.length ?? 0} 项`)
  out(`    scored_count = ${JSON.stringify(sections.map((s) => s.scored_count))}`)
})

/* ------------------------------------------------------------------ 第 14 步
   ⚠️ 浏览器侧的取证。**这一条不能用 HTTP 代替**：它证明的是「Vue 真的渲染出来了、
   而且渲染的是后端给的那份数据」，而 fetch 只证明 API 通。               */
await step(14, '13 条路由的无头浏览器 DOM 取证（--dump-dom + 关键内容断言）', async () => {
  // 找浏览器
  const candidates = [
    process.env.PE_BROWSER,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean)
  const browser = candidates.find((p) => fs.existsSync(p))
  check('找得到一个无头浏览器（Edge / Chrome）', browser !== undefined, browser ?? `试过了 ${candidates.length} 个路径`)
  if (!browser) return

  // 前端起着吗？
  let webUp = false
  for (const base of [WEB, WEB.replace('localhost', '[::1]')]) {
    try {
      const r = await fetch(base + '/', { signal: AbortSignal.timeout(5000) })
      if (r.ok) { webUp = true; break }
    } catch { /* 试下一个 */ }
  }
  check(`前端起着（${WEB}）`, webUp, webUp ? '' : '请先 `cd frontend; npm run dev`')
  if (!webUp) return

  // 真名单：断言「页面渲染的是后端给的那份数据」要用**真名字**，不能写死
  const students = await req('GET', `/api/students?limit=200`, { quiet: true })
  const allStudents = students.json?.items ?? []
  const me = allStudents.find((s) => s.id === STUDENT)
  // ⚠️ 教师端的「学生详情」只对**他本学期任教的学生**开放，故这一条路由用
  //    第 7 步现找到的那一个（学生 4 不在 T0001 的班里，用它只会渲染出 403 面板）。
  const taught = allStudents.find((s) => s.id === SHARED.taughtStudent)
  const section = (await req('GET', `/api/course-sections?limit=5`, { quiet: true })).json?.items?.[0]
  out(`    学生 #${STUDENT} = ${me?.student_no} ${me?.name}；`
    + `T0001 名册里的 #${taught?.id} = ${taught?.student_no} ${taught?.name}；`
    + `教学班 #${section?.id} = ${section?.name}`)

  const ROUTES = [
    { name: 's-home', url: `/s/home?student=${STUDENT}&as_of=${AS_OF}`, size: '375,2400',
      needles: ['的本周', me?.name, me?.student_no, '本周训练量'] },
    { name: 's-weekly-sheet', url: `/s/weekly-sheet?student=${STUDENT}&as_of=${AS_OF}`, size: '375,3000',
      needles: ['本周训练单', '第 6 周'] },
    { name: 's-check-in', url: `/s/check-in?student=${STUDENT}&as_of=${AS_OF}`, size: '375,2400',
      needles: ['每日打卡', '提交时刻与「是否迟交」都由服务端算'] },
    { name: 's-rpe', url: `/s/rpe?student=${STUDENT}&as_of=${AS_OF}`, size: '375,2400',
      needles: ['课堂快评', '口令请照老师投屏上的那一串手输'] },
    { name: 's-mini-test', url: `/s/mini-test?student=1&as_of=${AS_OF}`, size: '375,2400',
      needles: ['二次小测', '30 秒深蹲'] },
    { name: 's-notifications', url: `/s/notifications?student=${STUDENT}&as_of=${AS_OF}`, size: '375,2400',
      needles: ['消息中心', '未读'] },
    { name: 't-dashboard', url: `/t/dashboard?teacher=${TEACHER}&as_of=${AS_OF}`, size: '1440,2400',
      needles: ['ALERTS', 'LAYERS', 'THIS WEEK', 'CHECK-IN', section?.name] },
    { name: 't-report', url: `/t/report?teacher=${TEACHER}&as_of=${AS_OF}`, size: '1440,3000',
      needles: ['班级周报', '① 分层分布', '③ 三层完成率', '④ 进步榜'] },
    { name: 't-alerts', url: `/t/alerts?teacher=${TEACHER}&as_of=${AS_OF}`, size: '1440,2400',
      needles: ['预警队列', 'FILTERS', 'QUEUE'] },
    // ⚠️ 后两条 needle 是**收尾波加的**：`可解释性展开` 与 `他的今日` 两块在
    //    Task 3 的降级交付里**不存在**（那时 `/home` 教师身份 401，页面显示的是一段
    //    「教师身份读不到的五个端点」的说明）。它们出现在 DOM 里，就证明
    //    `GET /api/teacher/students/{id}/home` 真的被调通、且渲染出来了。
    { name: 't-student-detail', url: `/t/students/${taught?.id}?teacher=${TEACHER}&as_of=${AS_OF}`, size: '1440,3000',
      needles: [taught?.name, '当前分层', '本周训练单', '可解释性展开', '他的今日'] },
    { name: 'admin-index', url: '/admin', size: '1440,3000',
      needles: ['资源目录', '23 resources', '可写 9', '只读 14', '体育专家维护的知识资产'] },
    { name: 'admin-list', url: `/admin/students?teacher=${TEACHER}`, size: '1440,2000',
      needles: ['学生', '/api/students', '共 60 行', me?.name, '＋ 新建一行'] },
    { name: 'admin-detail', url: `/admin/students/${STUDENT}?teacher=${TEACHER}`, size: '1440,2000',
      needles: [`学生 #${STUDENT}`, me?.student_no, me?.name, '✎ 编辑', 'student_no'] },
  ]
  eq('路由条数 = 13（学生端 6 + 教师端 4 + 管理台 3）', ROUTES.length, 13)

  const workRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pe-smoke-browser-'))
  for (const route of ROUTES) {
    const profile = path.join(workRoot, `profile-${route.name}`)
    const args = [
      '--headless=new', '--disable-gpu', '--no-sandbox',
      // ⚠️ 坑 ①：不加这一条会抓到 StatBlock 数字滚动**中途**那一帧
      '--force-prefers-reduced-motion',
      '--virtual-time-budget=25000', '--run-all-compositor-stages-before-draw',
      `--window-size=${route.size}`, `--user-data-dir=${profile}`, '--dump-dom',
      WEB + route.url,
    ]
    const dom = await new Promise((resolve) => {
      // ⚠️ 坑 ②：不用 shell 重定向（PowerShell 的 `& msedge … > file` 得到 0 字节），
      //    直接收子进程的 stdout。
      const child = spawn(browser, args, { windowsHide: true })
      let stdout = ''
      let stderr = ''
      const timer = setTimeout(() => child.kill('SIGKILL'), 90000)
      child.stdout.on('data', (d) => { stdout += d.toString('utf8') })
      child.stderr.on('data', (d) => { stderr += d.toString('utf8') })
      child.on('close', (code) => {
        clearTimeout(timer)
        resolve({ stdout, stderr, code })
      })
      child.on('error', (err) => { clearTimeout(timer); resolve({ stdout: '', stderr: String(err), code: -1 }) })
    })
    const html = dom.stdout
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')
    const plain = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
    const missing = route.needles.filter((n) => n !== undefined && !plain.includes(n) && !html.includes(n))
    CURRENT.exchanges.push({
      method: 'DUMP-DOM',
      url: WEB + route.url,
      requestHeaders: {},
      requestBody: null,
      status: dom.code === 0 ? 200 : dom.code,
      responseBodyBytes: Buffer.byteLength(dom.stdout, 'utf8'),
      responseBody: `__dom__ ${route.needles.length} 条断言，缺 ${missing.length} 条：${missing.join(' | ')}`,
      domBytes: Buffer.byteLength(dom.stdout, 'utf8'),
      domMissing: missing,
      domStderrTail: dom.stderr.slice(-300),
    })
    out(`  → DUMP-DOM ${WEB}${route.url}`)
    out(`  ← exit=${dom.code} DOM=${Buffer.byteLength(dom.stdout, 'utf8')} bytes（剥掉 style/script 后 ${html.length}）`)
    // ⚠️ 门槛卡在**原始 DOM** 的字节数上，不是剥掉 style/script 之后的：
    //    dev 模式下 vite 把 CSS 与模块加载器都注进 `<style>` / `<script>`，
    //    剥完之后剩下的正文只有几 KB —— 拿它当「页面渲染出来了」的判据会假红。
    const rawBytes = Buffer.byteLength(dom.stdout, 'utf8')
    check(`${route.name}：DOM 里出现了 ${route.needles.length} 条关键内容`,
      dom.code === 0 && rawBytes > 20000 && missing.length === 0,
      missing.length === 0
        ? `DOM ${rawBytes} bytes`
        : `缺 ${missing.map((m) => JSON.stringify(m)).join(' | ')}`)
  }
  fs.rmSync(workRoot, { recursive: true, force: true })
})

/* ------------------------------------------------------------------ 第 15 步
   ⚠️ **收尾波加的一步**：色值的唯一住址守卫（`scripts/check-tokens.mjs`）。
   它是 Plan 05 换肤（R1「简洁、蓝白色调、浅色系、按钮圆角」）的**前置条件**：
   那次重构的可执行判据是「改一个文件、全站变色」，而这句话只有在
   「色值真的只住在 `src/styles/tokens.css` 里」时才成立。
   ⚠️ 它**不需要后端也不需要前端**（纯静态扫描），故本步是 16 步里唯一一步
   可以在两个服务都没起的情况下单独跑：`npm run check:tokens`。
   ⚠️ 挂在这里的理由是「`npm run smoke` 全绿」应当**蕴含**「设计令牌没有散开」。 */
await step(15, 'npm run check:tokens —— 色值的唯一住址是 src/styles/tokens.css', async () => {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const script = path.resolve(here, 'check-tokens.mjs')
  check('守卫脚本存在', fs.existsSync(script), script)
  const run = spawnSync(process.execPath, [script], { encoding: 'utf8' })
  const stdout = run.stdout ?? ''
  for (const line of stdout.split('\n')) {
    if (line.includes('✓') || line.includes('✗')) out(`    ${line}`)
  }
  eq('退出码 0', run.status, 0)
  check('它自报了「全绿」那一行', stdout.includes('全绿'), `stdout ${stdout.length} 字符`)
  // ⚠️ 反空转：那一句「tokens.css 里有 N 处色值」必须出现，且 N 要够大 ——
  //    否则「0 处 offender」可能只是谓词写坏了 / 路径指错了（守卫自己的自校 ②）。
  const tokenLine = stdout.split('\n').find((l) => l.includes('tokens.css 里有')) ?? ''
  out(`    ${tokenLine.trim()}`)
  check('它数到了 tokens.css 自己的色值（≥ 20，否则谓词或路径坏了）',
    Number(tokenLine.match(/(\d+) 处/)?.[1] ?? 0) >= 20, tokenLine.trim())
  if (run.stderr) out(`    stderr: ${run.stderr.trim()}`)
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
out(`  后端 ${API} · 前端 ${WEB} · as_of ${AS_OF} · 教师 ${TEACHER} · 学生 ${STUDENT}`)
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
    student: STUDENT,
    summary: { steps: STEPS.length, greenSteps, passed: PASSED, failed: FAILED },
    steps: STEPS,
  }
  fs.writeFileSync(TRANSCRIPT, JSON.stringify(payload, null, 1), 'utf8')
  out(`transcript → ${TRANSCRIPT} (${fs.statSync(TRANSCRIPT).size} bytes)`)
}

process.exit(FAILED === 0 && greenSteps === STEPS.length ? 0 : 1)
