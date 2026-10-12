#!/usr/bin/env node
/**
 * `scripts/check-dist.mjs` —— **生产构建的摇树守卫**（Plan 05A Task 3）。
 *
 * ---------------------------------------------------------------------------
 * 它钉的是哪一句话
 * ---------------------------------------------------------------------------
 * 计划 §4.3 逐字要求：「`adoptFromUrl()` … 仅在 `import.meta.env.DEV` 为真时生效；
 * **生产构建里它必须不存在** —— 要有一条守卫证明它被摇掉了
 * （`npm run build` 之后 grep `dist/` 里不含 `adoptFromUrl`）」。
 *
 * ⚠️ **为什么这一条不能靠读源码**：`main.ts` 里那一处调用包在
 * `if (import.meta.env.DEV) { … }` 里，而 `import.meta.env.DEV` 是**编译期常量**
 * —— 「生产构建里它不存在」这句话的真值只在 `dist/` 里，源码上永远看得到它。
 * 于是唯一的判据是**读产物**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它自带反空转（硬规矩 #50：一条恒真的守卫与一条真的守卫在颜色上无法区分）
 * ---------------------------------------------------------------------------
 * 「`dist/` 里 0 次」有三个假绿来源，逐个堵：
 *  1. **`dist/` 根本不存在 / 是空的** → 本脚本缺省会**自己跑一次 `npm run build`**
 *     （`--no-build` 可以关掉），并断言那一次退出码是 0；
 *  2. **谓词写坏了**（串拼错、扫描没递归进子目录）→ **反向**断言 `adoptFromUrl`
 *     在 `src/dev/identity-url.ts` 与 `src/main.ts` 里**确实存在**：
 *     源里有、产物里没有，才叫「被摇掉了」；
 *  3. **扫到的文件太少**（路径指错、只扫了 `.js`）→ 断言扫到的文件数与总字节数
 *     都够大，并把逐文件的命中数打出来。
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
 * 「设计令牌没有散开」与「开发工具没有漏进生产」两件事）。
 *
 * ⚠️ **零依赖**：只用 `node:fs` / `node:path` / `node:child_process`，
 * 与 `smoke.mjs` / `check-tokens.mjs` 同一条口径（本仓前端至今 0 个新增依赖，
 * Plan 05A 也是 0 —— 派单允许的 Playwright/Puppeteer 最终没有引入，
 * 理由见 `smoke.mjs` 第 14 步的文件头）。
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

/** 反空转第 2 条：这个串必须在**源码**里找得到（否则谓词是空的）。 */
const MUST_EXIST_IN_SRC = ['dev/identity-url.ts', 'main.ts']

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
  for (const file of scanned) {
    const text = fs.readFileSync(file, 'utf8')
    totalBytes += Buffer.byteLength(text, 'utf8')
    const n = countIn(text, FORBIDDEN)
    if (n > 0) hits.push(`${path.relative(DIST, file)} ×${n}`)
  }
  out(`   扫了 ${scanned.length} 个文件（${(totalBytes / 1024).toFixed(1)} kB），跳过 ${skipped} 个非文本`)
  check('扫到的文件数 ≥ 3（index.html + 主 chunk 的 js 与 css）', scanned.length >= 3, `${scanned.length} 个`)
  check('扫到的总字节数 ≥ 100 kB（否则说明扫错了目录）', totalBytes >= 100_000, `${totalBytes} bytes`)
  check(
    `dist/ 里 ${FORBIDDEN} 出现 0 次（它必须被 Rollup 摇掉）`,
    hits.length === 0,
    hits.length === 0 ? '0 次' : hits.join(' | '),
  )

  /* ④ 主 chunk 的大小也报一行（不是断言：它会随每次改动漂，钉住它只会天天红）。 */
  const assets = fs.existsSync(path.join(DIST, 'assets')) ? fs.readdirSync(path.join(DIST, 'assets')) : []
  for (const name of assets.filter((n) => n.endsWith('.js') || n.endsWith('.css')).sort()) {
    const size = fs.statSync(path.join(DIST, 'assets', name)).size
    out(`     assets/${name}  ${(size / 1024).toFixed(2)} kB`)
  }
}

out('')
if (failures === 0) {
  out(`✓ 全绿：生产构建里 ${FORBIDDEN} 出现 0 次，而源码里它确实存在（谓词不是空的）`)
} else {
  out(`✗ ${failures} 条红了`)
}
out('')
process.exit(failures === 0 ? 0 : 1)
