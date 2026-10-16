#!/usr/bin/env node
/**
 * `scripts/check-dist.mjs` —— **生产构建的静态守卫**（Plan 05A Task 3；
 * 交付前收尾波 ② 把它从「一条」扩成「两组」）。
 *
 * ---------------------------------------------------------------------------
 * 它钉的是哪两句话
 * ---------------------------------------------------------------------------
 * **第一组（Plan 05A Task 3）**：计划 §4.3 逐字要求「`adoptFromUrl()` … 仅在
 * `import.meta.env.DEV` 为真时生效；**生产构建里它必须不存在** —— 要有一条守卫
 * 证明它被摇掉了（`npm run build` 之后 grep `dist/` 里不含 `adoptFromUrl`）」。
 *
 * ⚠️ **为什么这一条不能靠读源码**：`main.ts` 里那一处调用包在
 * `if (import.meta.env.DEV) { … }` 里，而 `import.meta.env.DEV` 是**编译期常量**
 * —— 「生产构建里它不存在」这句话的真值只在 `dist/` 里，源码上永远看得到它。
 * 于是唯一的判据是**读产物**。
 *
 * **第二组（交付前收尾波 ②）**：字体已**自托管**（`src/styles/fonts.css` +
 * `src/assets/fonts/` 的 4 个 woff2），故产物里不得再出现 Google Fonts 的两个域，
 * 而自托管的字体**必须真的在**产物里。⚠️ 这一格与第一组不同：它**两侧都要扫**
 * （源码 + 产物），因为「源里有、产物里没有」在这里不是摇树、只可能是压缩器把
 * 一段 CSS 吃了 —— 而那一段恰恰是承重的（`ascent-override` 是「挡住字体也不许
 * 重叠」那条交付判据的实现，逐字取证见 `src/styles/fonts.css` 的文件头）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它自带反空转（硬规矩 #50：一条恒真的守卫与一条真的守卫在颜色上无法区分）
 * ---------------------------------------------------------------------------
 * 「`dist/` 里 0 次」有若干个假绿来源，逐个堵：
 *  1. **`dist/` 根本不存在 / 是空的** → 本脚本缺省会**自己跑一次 `npm run build`**
 *     （`--no-build` 可以关掉），并断言那一次退出码是 0；
 *  2. **谓词写坏了**（串拼错、扫描没递归进子目录）→ **反向**断言 `adoptFromUrl`
 *     在 `src/dev/identity-url.ts` 与 `src/main.ts` 里**确实存在**：
 *     源里有、产物里没有，才叫「被摇掉了」；
 *  3. **扫到的文件太少**（路径指错、只扫了 `.js`）→ 断言扫到的文件数与总字节数
 *     都够大，并把逐文件的命中数打出来；
 *  4. **（第二组）「0 次」是因为字体压根没进产物** → 正向断言 woff2 恰好 4 个、
 *     `Hanken Grotesk` / `Hanken Grotesk Fallback` / `ascent-override` 三个串各 ≥ 1 次；
 *  5. **（第二组）「0 次」是因为剥注释的谓词把整份文件吃空了** → 三拍自校
 *     （一个真引用必须**保住**、一句 HTML 提及与一句 CSS 提及必须**吃掉**）。
 *
 * ---------------------------------------------------------------------------
 * 怎么跑
 * ---------------------------------------------------------------------------
 *     cd frontend
 *     npm run check:dist          # 缺省：dist/ 不存在时先跑一次 npm run build
 *     node scripts/check-dist.mjs --no-build   # 只扫已有的 dist/（缺了就红）
 *     node scripts/check-dist.mjs --build      # 强制重新构建再扫
 *
 * 退出码 **0** = 全绿。⚠️ `smoke.mjs` 的第 15 步会 `spawn` 它一次
 * （与 `check-tokens.mjs` 并排：「`npm run smoke` 全绿」应当**蕴含**
 * 「设计令牌没有散开」、「开发工具没有漏进生产」与「字体没有留在 CDN 上」三件事）。
 *
 * ⚠️ **零依赖**：只用 `node:fs` / `node:path` / `node:child_process`，
 * 与 `smoke.mjs` / `check-tokens.mjs` 同一条口径（本仓前端至今 0 个新增依赖，
 * Plan 05A 也是 0 —— 派单允许的 Playwright/Puppeteer 最终没有引入，
 * 理由见 `smoke.mjs` 第 14 步的文件头；交付前收尾波自托管字体也**没有**引入
 * `@fontsource/*` 一类的包，woff2 是静态文件）。
 */
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HERE, '..')
const DIST = path.join(FRONTEND, 'dist')
const SRC = path.join(FRONTEND, 'src')

/** 要在产物里**找不到**的那个串（计划 §4.3 点名的那一个）。 */
const FORBIDDEN = 'adoptFromUrl'

/** ⚠️ **交付前收尾波 ② 加的第二组禁用串**：Google Fonts 的 CDN。
 *  本前端的字体自 `src/styles/fonts.css` 起**自托管**（woff2 入库在
 *  `src/assets/fonts/`），故产物里再出现这两个域就说明有人把 `<link>` / `@import`
 *  加回去了 —— 而那一格不是审美问题：`fonts.css` 的文件头逐字记着三组对照实验，
 *  实测**挡掉 CDN 时 11 条路由里 6 条会报文本重叠**（合计 15 处），放行时 0 处。
 *  甲方的内网大概率直接挡这两个域，于是「产物里 0 次」是**交付判据**。
 *  ⚠️ 两个串分开数（不是一个 `googleapis` 通配）：`fonts.gstatic.com` 才是字体文件
 *  的住址，只挡 `fonts.googleapis.com` 的话 CSS 到得了、woff2 到不了，那是**最坏**
 *  的一档（`font-display: swap` 会一直用回退字体，而回退字体的度量与 Hanken
 *  Grotesk 差 11.5%）。 */
const FORBIDDEN_CDN = ['fonts.googleapis.com', 'fonts.gstatic.com']

/** ⚠️ **Plan 07 Task 7 加的第三组禁用串**：会随身份/数据变假的**渲染正文**。
 *
 *  病灶（终审 S1-2 / S3-1）：发给甲方的 `dist` 里有 **5 处**「不做登录失败锁定」
 *  （`views/auth/Login.vue` 登录页正文 · `App.vue` 16 条路由的页脚 ·
 *  `components/ApiErrorBanner.vue` 401 的处置建议 · `api/client.ts` · `api/auth.ts`），
 *  而锁定自 Plan 06 Task 3 起**真的在**：2026-10-16 实测同一个学号 5 发坏口令
 *  （0.083/0.048/0.050/0.050/0.061 s）之后第 6 发 **0.017 s** 返回（= 锁定档一次
 *  PBKDF2 都不跑的签名），而**用正确口令也是同一份** 401 / 82 B /
 *  sha256[:16] `D6CA996C91CFADAA`；同批交付的说明书 §6⑤ 说的正好相反
 *  ⇒ 两份交付物在**安全**话题上互相打脸，而甲方落地的第一页就是登录页。
 *  第 6 处是 `views/student/MiniTest.vue` 的「走的是**匿名** `GET /api/mini-tests`
 *  （180 行全量）」：实测匿名 **401**、学生 **3 行**、教师 **123 行**、管理员才是
 *  **180 行**，openapi 上它挂着 security。
 *
 *  ⚠️ 判据一律是**正则**、且字符类里排掉 `。；\n`：改后的真话里「不做口令找回 …。」
 *  与「登录失败锁定**已做**」同在一个文本节点，而**构建会把换行压成空格**
 *  ⇒ 不排掉句号就会恒红，而下一个人唯一的出路是把断言删掉（硬规矩 #109）。
 *  ⚠️ 而「`Login.vue` 那一处」要单独一条：它的 `不做` 被 `<strong>` 隔开，
 *  构建后 `不做` 与 `口令找回 / 登录失败锁定 …` 是**两个字符串字面量**
 *  ⇒ 上面那条正则抓不到它，得按它改前那个清单的形状抓。
 *
 *  ⚠️⚠️ **两侧都扫，而产物那一侧才是这一格的牙**：本条的失效形态正是
 *  「改了源、忘了重建」—— 那时源侧绿、产物侧红。故产物那一侧读的是**磁盘上
 *  真的那一份**（不触发构建），一份陈的产物当场红。 */
const FORBIDDEN_STALE_CLAIM = [
  { label: '「不做…登录失败锁定」（锁定自 Plan 06 Task 3 起真的在）',
    re: /不做[^。；\n]{0,24}登录失败锁定/g },
  { label: '「口令找回 / 登录失败锁定」这份清单（Login.vue 改前的形状；构建后 `不做` 被 <strong> 隔成另一个字面量，故单列一条）',
    re: /口令找回 \/ 登录失败锁定/g },
  { label: '「它走的是匿名」（MiniTest.vue 改前；`GET /api/mini-tests` 挂 security，匿名 401）',
    re: /它走的是匿名/g },
  { label: '「180 行全量」（MiniTest.vue 改前；服务端按身份筛，学生只有 3 行）',
    re: /180 行全量/g },
]

/** 反空转（STALE_CLAIM 那一组自己的正控）：`BAD` 必须**每条都命中**（否则谓词是空的），
 *  `GOOD` 必须**每条都不命中**（否则改后的真话会恒红，而那条断言活不过下一波）。
 *  ⚠️ `GOOD` 是照改后那六处的真实措辞抄的，不是随手编的一句好话。 */
const STALE_CAL_BAD = '本系统不做口令找回 / 登录失败锁定 / 图形验证码 / OAuth。'
  + '它走的是匿名 GET，180 行全量 + 客户端按 student_id 过滤。'
const STALE_CAL_GOOD = '本系统不做口令找回 / 图形验证码 / OAuth。'
  + '口令连错多次会被临时锁定，稍后再试；被锁时看到的仍然是「口令不正确」。'
  + '登录失败锁定已做：阈值与逐字口径见 spec §13.4.6。'
  + '它走的是 GET /api/mini-tests（要会话：匿名打过去是 401；服务端按身份筛，'
  + '学生只拿到自己那几行，管理员才是全量）。'

/** 反空转第 2 条：这个串必须在**源码**里找得到（否则谓词是空的）。 */
const MUST_EXIST_IN_SRC = ['dev/identity-url.ts', 'main.ts']

/** ⚠️ 反空转（CDN 那一组自己的正控）：`FORBIDDEN_CDN` 的「0 次」有三个假绿来源 ——
 *  ① 字体压根没进产物（`fonts.css` 没被 import / Vite 没把 woff2 当资产）；
 *  ② `@font-face` 被压缩器整段摇掉；③ **度量对齐的那三个 override 被摇掉**
 *  （那一条是「挡住字体也不许重叠」的实现，见 `fonts.css` 第 ③ 段）。
 *  故这三件事各断言一次：产物里 woff2 的个数、`Hanken Grotesk` 这个族名、
 *  以及 `ascent-override` 这个描述符。 */
const MUST_EXIST_IN_DIST = ['Hanken Grotesk', 'Hanken Grotesk Fallback', 'ascent-override']
/** 自托管的 woff2 在 `src/assets/fonts/` 里有 4 个（latin + latin-ext × 两个族）。 */
const EXPECTED_WOFF2 = 4

/** 产物里要扫的扩展名。⚠️ 含 `.map`：一个 sourcemap 里留着
 *  `adoptFromUrl` 等于把那段代码原文交给了任何拿到产物的人。 */
const SCANNED_EXTENSIONS = new Set(['.js', '.mjs', '.cjs', '.css', '.html', '.svg', '.json', '.map'])

const argv = new Set(process.argv.slice(2))
const forceBuild = argv.has('--build')
const noBuild = argv.has('--no-build')

let failures = 0

function out(line = '') {
  process.stdout.write(line + '\n')
}

function check(label, ok, detail = '') {
  const pass = ok === true
  if (!pass) failures += 1
  out(`  ${pass ? '✓' : '✗'} ${label}${detail === '' ? '' : `  →  ${detail}`}`)
  return pass
}

/** 递归收集文件（⚠️ 不递归的话 `dist/assets/*.js` 一个都扫不到，那正是主 chunk 的住址）。 */
function walk(dir) {
  const found = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) found.push(...walk(full))
    else if (entry.isFile()) found.push(full)
  }
  return found
}

/** 数一个**带 `g` 的正则**命中几次。⚠️ 每次都新建一个同源的 RegExp：
 *  带 `g` 的正则有 `lastIndex` 状态，共用一个实例去数两个文件会漏。 */
function countMatches(text, re) {
  const fresh = new RegExp(re.source, re.flags)
  let count = 0
  while (fresh.exec(text) !== null) count += 1
  return count
}

function countIn(text, needle) {
  let count = 0
  let from = 0
  for (;;) {
    const at = text.indexOf(needle, from)
    if (at === -1) return count
    count += 1
    from = at + needle.length
  }
}

/** 整块剥掉**块**注释（把它们换成等长的空格，行数因此不变）。
 *  ⚠️ 与 `check-tokens.mjs` 的同名函数同一条口径，而**刻意不剥 `//` 行注释**：
 *  `https://` 里就有一个 `//`，剥行注释会把一个真引用从 `https:` 之后整段吃掉
 *  —— 那才是真正的假绿（硬规矩 #109：「文本里出现某串」要分清**本身**与**提及**，
 *  而这里的处置必须偏向「宁可多报一句提及，不可吃掉一个真引用」）。 */
function stripComments(text) {
  const blank = (match) => match.replace(/[^\n]/g, ' ')
  return text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank)
}

out('')
out('== check-dist：生产构建里不得留下开发工具 ==')
out(`   dist = ${DIST}`)

/* ------------------------------------------------------------------ ① 构建 */

const distExists = fs.existsSync(DIST)
if (forceBuild || (!distExists && !noBuild)) {
  out(`   dist/ ${distExists ? '已存在，但 --build 要求重建' : '不存在'} → 跑一次 npm run build`)
  const run = spawnSync('npm', ['run', 'build'], { cwd: FRONTEND, encoding: 'utf8', shell: true })
  if (run.stdout) out(run.stdout.trim().split('\n').slice(-12).map((l) => `     ${l}`).join('\n'))
  if (run.status !== 0 && run.stderr) out(`     stderr: ${run.stderr.trim().slice(-800)}`)
  check('npm run build 退出码 0', run.status === 0, `status=${run.status}`)
} else if (!distExists) {
  check('dist/ 存在（--no-build 时它必须已经在了）', false, `缺 ${DIST}；请去掉 --no-build`)
}

/* ---------------------------------------------------- ② 反空转：源码里有它 */

for (const rel of MUST_EXIST_IN_SRC) {
  const file = path.join(SRC, rel)
  const exists = fs.existsSync(file)
  const text = exists ? fs.readFileSync(file, 'utf8') : ''
  check(
    `源码里确实有 ${FORBIDDEN}（src/${rel}）`,
    exists && countIn(text, FORBIDDEN) > 0,
    exists ? `${countIn(text, FORBIDDEN)} 处` : '文件不存在',
  )
}

/* -------------------------------------------------------- ③ 扫产物，逐个报 */

if (fs.existsSync(DIST)) {
  const all = walk(DIST)
  const scanned = all.filter((f) => SCANNED_EXTENSIONS.has(path.extname(f).toLowerCase()))
  const skipped = all.length - scanned.length
  let totalBytes = 0
  const hits = []
  /** 每个 CDN 串各自的命中（分开报，理由见 `FORBIDDEN_CDN` 的注释）。 */
  const cdnHits = new Map(FORBIDDEN_CDN.map((n) => [n, []]))
  /** 正控：`MUST_EXIST_IN_DIST` 里每个串在产物里出现的次数。 */
  const distHits = new Map(MUST_EXIST_IN_DIST.map((n) => [n, 0]))
  /** 每条「会变假的散文」各自的命中（分开报：红的时候要能直接看出是哪一处）。 */
  const staleHits = new Map(FORBIDDEN_STALE_CLAIM.map((e) => [e.label, []]))
  for (const file of scanned) {
    /* ⚠️ **产物这一侧也剥块注释**，与下面源码那一侧用**同一个**谓词。
       这一格是实测逼出来的、不是想出来的：Vite **不剥 `index.html` 里的 HTML 注释**
       （CSS 的注释它剥、HTML 的不剥），而 `index.html` 的注释里逐字**提到**了这两个域
       （交代它们为什么被删）→ 首跑当场两条红（`index.html ×2`）。那是**提及**、不是引用，
       运行时一个跨域请求也不会发（硬规矩 #109）。⚠️ 处置选「把谓词做准」而不是
       「把注释删掉」：注释是这一格的取证住址，删掉它等于把「为什么产物里没有 CDN」
       这件事的书面理由一起删了。⚠️ 而谓词做准之后，一个真的 `<link href=…>` 仍然会被抓到
       —— 那正是上面自校 ① 钉住的那一半。 */
    const text = stripComments(fs.readFileSync(file, 'utf8'))
    totalBytes += Buffer.byteLength(text, 'utf8')
    const n = countIn(text, FORBIDDEN)
    if (n > 0) hits.push(`${path.relative(DIST, file)} ×${n}`)
    for (const needle of FORBIDDEN_CDN) {
      const k = countIn(text, needle)
      if (k > 0) cdnHits.get(needle).push(`${path.relative(DIST, file)} ×${k}`)
    }
    for (const needle of MUST_EXIST_IN_DIST) {
      distHits.set(needle, distHits.get(needle) + countIn(text, needle))
    }
    for (const entry of FORBIDDEN_STALE_CLAIM) {
      const k = countMatches(text, entry.re)
      if (k > 0) staleHits.get(entry.label).push(`${path.relative(DIST, file)} ×${k}`)
    }
  }
  out(`   扫了 ${scanned.length} 个文件（${(totalBytes / 1024).toFixed(1)} kB），跳过 ${skipped} 个非文本`)
  check('扫到的文件数 ≥ 3（index.html + 主 chunk 的 js 与 css）', scanned.length >= 3, `${scanned.length} 个`)
  check('扫到的总字节数 ≥ 100 kB（否则说明扫错了目录）', totalBytes >= 100_000, `${totalBytes} bytes`)
  check(
    `dist/ 里 ${FORBIDDEN} 出现 0 次（它必须被 Rollup 摇掉）`,
    hits.length === 0,
    hits.length === 0 ? '0 次' : hits.join(' | '),
  )

  /* ④ **交付前收尾波 ②**：产物里不得留下 Google Fonts 的 CDN，而自托管的字体
        必须**真的在**产物里（后半句是前半句的反空转正控，见 MUST_EXIST_IN_DIST）。 */
  out('')
  out('   -- 字体自托管（交付前收尾波 ②）--')
  const woff2 = all.filter((f) => path.extname(f).toLowerCase() === '.woff2')
  let woff2Bytes = 0
  for (const f of woff2) woff2Bytes += fs.statSync(f).size
  for (const f of woff2.sort()) out(`     ${path.relative(DIST, f)}  ${(fs.statSync(f).size / 1024).toFixed(2)} kB`)
  check(
    `dist/ 里自托管的 woff2 恰好 ${EXPECTED_WOFF2} 个（latin + latin-ext × 两个族）`,
    woff2.length === EXPECTED_WOFF2,
    `${woff2.length} 个 / ${woff2Bytes} bytes`,
  )
  for (const needle of MUST_EXIST_IN_DIST) {
    check(`dist/ 里确实有 ${JSON.stringify(needle)}（否则上面那几条「0 次」是空转）`,
      distHits.get(needle) > 0, `${distHits.get(needle)} 次`)
  }
  for (const needle of FORBIDDEN_CDN) {
    const where = cdnHits.get(needle)
    check(`dist/ 里 ${needle} 出现 0 次（字体已自托管，运行时不发跨域请求）`,
      where.length === 0, where.length === 0 ? '0 次' : where.join(' | '))
  }
  /* ④b **Plan 07 Task 7**：产物里不得留下「会随身份/数据变假的渲染正文」。
        ⚠️ 这一组是**本条的牙**：失效形态是「改了源、忘了重建」，那时源侧绿、这里红。
        上面那段扫描读的是磁盘上真的那一份，故一份陈的产物当场被抓。 */
  out('')
  out('   -- 渲染正文里的过期断言（Plan 07 Task 7 · 终审 S1-2 / S3-1）--')
  for (const entry of FORBIDDEN_STALE_CLAIM) {
    const where = staleHits.get(entry.label)
    check(`dist/ 里 ${entry.label} 出现 0 次`,
      where.length === 0, where.length === 0 ? '0 次' : where.join(' | '))
  }

  /* ⚠️ 源码那一侧的那一组断言在**下面**（它不依赖 `dist/`，故不能住在这个 `if` 里）。 */

  /* ⑤ 主 chunk 的大小也报一行（不是断言：它会随每次改动漂，钉住它只会天天红）。 */
  const assets = fs.existsSync(path.join(DIST, 'assets')) ? fs.readdirSync(path.join(DIST, 'assets')) : []
  for (const name of assets.filter((n) => n.endsWith('.js') || n.endsWith('.css')).sort()) {
    const size = fs.statSync(path.join(DIST, 'assets', name)).size
    out(`     assets/${name}  ${(size / 1024).toFixed(2)} kB`)
  }
}

/* -------------------------------------------------- ⑤ 源码那一侧：CDN 也是 0 次
   ⚠️ 产物是源物的函数，但「源里有、产物里没有」在这一格**不是**摇树（它只可能是
   压缩器把一段 CSS 吃了），故两侧都要 0。⚠️ 而源码那一侧**必须先剥块注释**：
   `index.html` / `src/main.ts` / `src/styles/fonts.css` 三处的注释里都**逐字提到**了
   这两个域（交代它们为什么被删掉、以及删掉它们的取证），那是**提及**、不是引用。
   不剥的话这一格会**恒红**，而下一个人唯一的出路就是把断言删掉（硬规矩 #109）。
   ⚠️ `.ts` 也在扫描面里：`main.ts` 是 `fonts.css` 唯一的 import 点，而 Vite 的
   `index.html` 也可以写 `<script>` 内联，故不能只扫 `.css` / `.html`。 */
{
  /* 反例先验（硬规矩 #107）：`stripComments` 必须**保住**一个真引用、
     又必须**吃掉**一句提及。少了这两拍，下面那个「0 次」可能只是谓词把整份文件
     吃空了（例如把 `//` 也当注释剥掉，于是 `https://…` 从冒号之后整段消失）。 */
  const CAL_REFERENCE = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X" />'
  const CAL_MENTION = '<!-- 甲方内网大概率直接挡 fonts.googleapis.com 与 fonts.gstatic.com -->'
  const CAL_BLOCK_MENTION = '/* 产物里 fonts.gstatic.com 出现 0 次 */'
  check('自校 ①：剥注释之后一个**真引用**仍然被数到（谓词没把 `https://` 吃掉）',
    countIn(stripComments(CAL_REFERENCE), FORBIDDEN_CDN[0]) === 1,
    `${countIn(stripComments(CAL_REFERENCE), FORBIDDEN_CDN[0])} 次（应为 1）`)
  check('自校 ②：剥注释之后一句 HTML **提及**不再被数到',
    countIn(stripComments(CAL_MENTION), FORBIDDEN_CDN[0]) === 0
      && countIn(stripComments(CAL_MENTION), FORBIDDEN_CDN[1]) === 0,
    `${countIn(stripComments(CAL_MENTION), FORBIDDEN_CDN[0])} / ${countIn(stripComments(CAL_MENTION), FORBIDDEN_CDN[1])} 次（应为 0 / 0）`)
  check('自校 ③：剥注释之后一句 CSS **提及**也不再被数到',
    countIn(stripComments(CAL_BLOCK_MENTION), FORBIDDEN_CDN[1]) === 0,
    `${countIn(stripComments(CAL_BLOCK_MENTION), FORBIDDEN_CDN[1])} 次（应为 0）`)

  /* 反例先验（硬规矩 #107）：那一组「会变假的散文」的谓词必须**抓得到**改前那六处的
     形状、又必须**放过**改后的真话。少了这两拍，下面那两条「0 次」可能只是正则写歪了
     （例如把 `。` 也放进字符类，于是跨句一律不匹配 = 恒绿）。 */
  for (const entry of FORBIDDEN_STALE_CLAIM) {
    check(`自校 ①：${entry.label} 的谓词**抓得到**改前那句`,
      countMatches(STALE_CAL_BAD, entry.re) > 0, `${countMatches(STALE_CAL_BAD, entry.re)} 次（应 ≥ 1）`)
    check(`自校 ②：${entry.label} 的谓词**放过**改后那句（否则恒红）`,
      countMatches(STALE_CAL_GOOD, entry.re) === 0, `${countMatches(STALE_CAL_GOOD, entry.re)} 次（应为 0）`)
  }

  const SRC_EXTENSIONS = new Set([...SCANNED_EXTENSIONS, '.html', '.ts', '.vue'])
  const srcFiles = [path.join(FRONTEND, 'index.html'), ...walk(SRC)]
    .filter((f) => SRC_EXTENSIONS.has(path.extname(f).toLowerCase()))
  const srcCdn = []
  const srcStale = []
  let srcBytes = 0
  for (const f of srcFiles) {
    /* ⚠️ 剥块注释是承重的：改后那六处都留了一段 HTML/JS 注释**逐字记下改前那句**
       （那是这一格的取证住址）。不剥的话这一条会恒红在「提及」上（硬规矩 #109）。 */
    const text = stripComments(fs.readFileSync(f, 'utf8'))
    srcBytes += text.length
    for (const needle of FORBIDDEN_CDN) {
      const k = countIn(text, needle)
      if (k > 0) srcCdn.push(`${path.relative(FRONTEND, f)}:${needle} ×${k}`)
    }
    for (const entry of FORBIDDEN_STALE_CLAIM) {
      const k = countMatches(text, entry.re)
      if (k > 0) srcStale.push(`${path.relative(FRONTEND, f)}:${entry.label} ×${k}`)
    }
  }
  check(`源码里 ${FORBIDDEN_CDN.join(' / ')} 也是 0 次（剥块注释后扫了 ${srcFiles.length} 个文件）`,
    srcCdn.length === 0, srcCdn.length === 0 ? '0 次' : srcCdn.join(' | '))
  check('而它确实扫到了东西（≥ 20 个文件 / ≥ 100 kB，否则上面那条又是空转）',
    srcFiles.length >= 20 && srcBytes >= 100_000, `${srcFiles.length} 个 / ${srcBytes} 字符`)
  check(`源码里那 ${FORBIDDEN_STALE_CLAIM.length} 条「会变假的渲染正文」也是 0 次（剥块注释后扫的同一批文件）`,
    srcStale.length === 0, srcStale.length === 0 ? '0 次' : srcStale.join(' | '))
}

out('')
if (failures === 0) {
  out(`✓ 全绿：生产构建里 ${FORBIDDEN} 出现 0 次、${FORBIDDEN_CDN.join(' 与 ')} 各出现 0 次、`
    + `${FORBIDDEN_STALE_CLAIM.length} 条「会变假的渲染正文」各出现 0 次，`
    + '而源码里前者确实存在、产物里自托管的字体确实存在（谓词都不是空的）')
} else {
  out(`✗ ${failures} 条红了`)
}
out('')
process.exit(failures === 0 ? 0 : 1)
