#!/usr/bin/env node
/**
 * `scripts/check-tokens.mjs` —— **色值只有一个住址**的可执行守卫（Plan 04 收尾波 清 1）。
 *
 * ---------------------------------------------------------------------------
 * 它断言什么
 * ---------------------------------------------------------------------------
 * 扫 `frontend/src/**\/*.{css,vue}`，断言**除 `src/styles/tokens.css` 之外**
 * 一个色值字面量都没有：
 *
 *   * hex：`#rgb` / `#rgba` / `#rrggbb` / `#rrggbbaa`（后面必须是一个词边界）；
 *   * 函数式：`rgb(` / `rgba(` / `hsl(` / `hsla(`。
 *
 * 命中一处就是退出码 **1**，并把 `文件:行:命中` 逐条打出来。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 为什么要有这一条（Plan 05 的前置条件）
 * ---------------------------------------------------------------------------
 * Plan 05 的 R1 要把《田径场年鉴》整套视觉换成「简洁、蓝白色调、浅色系、按钮圆角」。
 * 那次换肤的**可执行判据**是「改一个文件、全站变色」——而这句话只有在
 * 「色值真的只住在一个文件里」时才成立。故本守卫不是洁癖，它是那次重构的前置条件：
 * 它把「唯一住址」从一句写在注释里的纪律变成一个会红的判据。
 *
 * ⚠️ 落地时实测散落的色值是 **7 处**（`base.css` 6 + `IdentitySwitcher.vue` 1，
 * 其中 `rgba(244, 240, 230, .35)` 逐字重复了两遍），已全部收进 `tokens.css`
 * 的「叠色」那一组（`--offset-shadow-on-ink` / `--hover-wash-on-ink` /
 * `--zebra-wash-on-paper` / `--track-hover` / `--track-arc-line` / `--track-arc-glow`）。
 *
 * ---------------------------------------------------------------------------
 * 怎么跑
 * ---------------------------------------------------------------------------
 *     cd frontend; npm run check:tokens
 * 零依赖、`node` 直接跑（与 `scripts/smoke.mjs` 同一条纪律）。
 * `smoke.mjs` 的第 15 步也会 `spawn` 它一次，故「15 步全绿」里含着本守卫。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 谓词的两个已知假阳性，以及它怎么被收窄的（硬规矩 #107）
 * ---------------------------------------------------------------------------
 * 1. **注释里的色值**。`admin.css` 与 `teacher.css` 的注释里逐字写着 `#a93623` /
 *    `#B3352B` / `#E8695C`（前者是一条待清扫记录、后两者是对比度的实算说明），
 *    `tokens.css` 自己的注释里也有 6 处（`paper=#F4F0E6` 一类）。
 *    那是**对色值的提及**、不是色值本身（硬规矩 #109），故本脚本**先剥注释再扫**：
 *    `/* … *\/` 与 `<!-- … -->` 两种，剥的时候把非换行字符换成空格，
 *    于是行号仍然对得上原文。
 * 2. **`#` 后跟 3/4/6/8 个十六进制字符的其它东西**。实测过三个已知反例：
 *    `#app`（CSS 的 id 选择器）不命中（`p` 不是十六进制字符，词边界不成立）、
 *    `url(#lg1)`（SVG 的引用）不命中（`l`/`g` 不是十六进制字符）、
 *    `pathLength=100` 不命中（没有 `#`）。⚠️ 而**真的会**命中的反例有两个，
 *    都写进了下面的 :data:`NEGATIVE_CONTROLS` / :data:`KNOWN_FALSE_POSITIVES`：
 *    `硬规矩 #101`（`101` 恰好是 3 个十六进制字符 —— 靠「先剥注释」消掉，
 *    它只出现在注释里）与 `a#fff0`（一个 4 位十六进制的 id 选择器与 4 位 hex 色值
 *    **在语法上无法区分** —— 全仓今天没有这种 id，若将来出现，正确处置是给它改名，
 *    不是放宽谓词）。
 *
 * ⚠️ **落地时自己撞上的一次假 offender**（留在这里给下一个人）：在 `admin.css` 的
 *    **注释里**写了一个 glob（`src/` 后跟「星号星号斜杠星号」），而 CSS 的注释
 *    在**第一个** `*\/` 就结束了 —— 于是那半段注释被当成 CSS 解析，本守卫报出 4 处
 *    offender（全在注释里）。⚠️ 这**不是**谓词太严：本脚本的剥注释与 CSS 解析器
 *    **同口径**（`/* … *\/` 惰性匹配到第一个终止符），而红的方向是安全的那一侧。
 *    处置是改写那句注释，不是放宽守卫。
 *
 * ⚠️ **它守不住什么**（如实记录）：
 *   * 具名色（`white` / `black` / `transparent` / `currentColor`）不在谓词里。
 *     全仓实测一个都没有（`transparent` 除外，而它是关键字、不是色值）；
 *     要收它得先有一份具名色白名单，代价大于收益。
 *   * `.ts` / `.html` 不扫：`src/api/generated/schema.d.ts` 是 openapi-typescript
 *     **生成**的（346 KB，里面是后端 docstring 的原文，含 `硬规矩 #101` 那一类串），
 *     改它等于改生成物；`index.html` 实测 0 处色值。
 *   * `styles/*.css` 之外的**行内 style**（`<div :style="…">`）里若写色值会被抓到
 *     （`.vue` 是整文件扫的），但 `<script>` 里拼出来的色值字符串抓不到。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '../src')
/** **唯一允许出现色值字面量的那一个文件**（设计令牌的住址）。 */
const TOKENS = path.join(SRC, 'styles', 'tokens.css')
const SCANNED_EXTENSIONS = new Set(['.css', '.vue'])

/** hex 色值：只认 CSS 合法的 3 / 4 / 6 / 8 位，且后面必须是一个词边界。
 *  ⚠️ 刻意**不**写成 `{3,8}`：那会把 `#12345`（5 位，不是合法色值）也算进来。 */
const HEX = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g
/** 函数式色值。⚠️ `rgba?` / `hsla?` 各自的 `a` 变体都收进来。 */
const FUNCTIONAL = /\b(?:rgba?|hsla?)\(/g

/** 剥注释：把 `/* … *\/` 与 `<!-- … -->` 里的非换行字符换成空格（行号因此不变）。 */
function stripComments(text) {
  const blank = (match) => match.replace(/[^\n]/g, ' ')
  return text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank)
}

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) yield* walk(full)
    else yield full
  }
}

function hitsIn(text) {
  const hits = []
  text.split('\n').forEach((line, index) => {
    for (const match of line.matchAll(HEX)) hits.push({ line: index + 1, what: match[0], text: line.trim() })
    for (const match of line.matchAll(FUNCTIONAL)) hits.push({ line: index + 1, what: match[0], text: line.trim() })
  })
  return hits
}

function out(line = '') {
  process.stdout.write(line + '\n')
}

let failures = 0
function fail(message) {
  failures += 1
  out(`  ✗ ${message}`)
}

out('='.repeat(78))
out('check-tokens —— 色值的唯一住址是 src/styles/tokens.css')
out('='.repeat(78))

/* --------------------------------------------------------------------------
   自校 ①：谓词对**已知反例**的判定（硬规矩 #107）
   --------------------------------------------------------------------------
   ⚠️ 这一段是「谓词本身对不对」的守卫，与「仓库里有没有 offender」是两件事。
   少了它的话，一次把谓词写坏（例如漏了 `#`）会让下面的扫描**空转全绿**。 */

/** 必须**不**命中的（不是色值，或只是对色值的提及）。 */
const NEGATIVE_CONTROLS = [
  '#app',                              // CSS 的 id 选择器
  'url(#lg1)',                         // SVG 的引用
  'url(#gradient-1)',                  // 同上，带连字符
  'pathLength=100',                    // SVG 属性，没有 #
  '#12345',                            // 5 位，不是合法的 CSS hex
  '#a1b2c3d4e5',                       // 10 位，同上
  'grid-template-rows: repeat(2, 1fr)',
  'var(--track)',
  'href="#top"',
]
/** 必须**命中**的（四种合法长度的 hex + 四个函数式）。 */
const POSITIVE_CONTROLS = [
  '#fff', '#ffff', '#ffffff', '#ffffffff',
  'rgb(1, 2, 3)', 'rgba(1, 2, 3, .4)', 'hsl(210 100% 50%)', 'hsla(210, 100%, 50%, .5)',
]
/** 已知会命中、但**只出现在注释里**的假阳性（靠「先剥注释」消掉）。
 *  ⚠️ 三个样本都**必须包在注释里**：`硬规矩 #101` 裸着写的话它就是一处真命中
 *  （`101` 恰好是 3 个十六进制字符 + 一个词边界），本自校的第一格就写错过一次。 */
const KNOWN_FALSE_POSITIVES = ['/* 硬规矩 #101 */', '/* #a93623 */', '<!-- #fff -->']

out('')
out('【自校 ①】谓词对已知反例的判定')
for (const sample of NEGATIVE_CONTROLS) {
  const hits = hitsIn(stripComments(sample))
  if (hits.length !== 0) fail(`负控 ${JSON.stringify(sample)} 被误判成色值：${JSON.stringify(hits)}`)
}
out(`  ✓ ${NEGATIVE_CONTROLS.length} 个负控一个都没命中（含 url(#id) / #app / #12345）`)
for (const sample of POSITIVE_CONTROLS) {
  if (hitsIn(stripComments(sample)).length === 0) fail(`正控 ${JSON.stringify(sample)} 没有被识别成色值`)
}
out(`  ✓ ${POSITIVE_CONTROLS.length} 个正控全部命中`)
for (const sample of KNOWN_FALSE_POSITIVES) {
  const raw = hitsIn(sample).length
  const stripped = hitsIn(stripComments(sample)).length
  if (raw === 0) fail(`假阳性样本 ${JSON.stringify(sample)} 在**原文**上就没命中，本自校失去意义`)
  if (stripped !== 0) fail(`假阳性样本 ${JSON.stringify(sample)} 剥注释后仍然命中（${stripped} 处）`)
}
out(`  ✓ ${KNOWN_FALSE_POSITIVES.length} 个「注释里的色值」剥注释后都不命中（原文上确实命中，故剥注释是承重的）`)

/* --------------------------------------------------------------------------
   自校 ②：`tokens.css` 必须存在、且它自己**必须**有色值
   --------------------------------------------------------------------------
   ⚠️ 它是「扫描没有空转」的对照：若谓词写坏了或 `SRC` 指错了，
   tokens.css 那一侧会数出 0，而 offender 也会是 0 → 两边都绿。 */

out('')
out('【自校 ②】tokens.css 是那个唯一住址')
if (!fs.existsSync(TOKENS)) {
  fail(`找不到 ${path.relative(process.cwd(), TOKENS)}`)
} else {
  const tokenHits = hitsIn(stripComments(fs.readFileSync(TOKENS, 'utf8')))
  // ⚠️ 下界 **20** 而不是实测的 34：加/并令牌都会正常地改变它，写死实测值会让
  //    一次合法的令牌整理变红。20 的含义是「它不可能是空的」。
  if (tokenHits.length < 20) {
    fail(`tokens.css 里只数到 ${tokenHits.length} 处色值（下界 20）——谓词或路径可能坏了`)
  } else {
    out(`  ✓ tokens.css 里有 ${tokenHits.length} 处色值字面量（它是唯一允许的住址）`)
  }
}

/* --------------------------------------------------------------------------
   正题：扫 src/**\/*.{css,vue}，tokens.css 之外一个色值都不许有
   -------------------------------------------------------------------------- */

out('')
out('【正题】tokens.css 之外的色值字面量')
const scanned = []
const offenders = []
for (const file of walk(SRC)) {
  if (!SCANNED_EXTENSIONS.has(path.extname(file))) continue
  scanned.push(file)
  const rel = path.relative(SRC, file).replaceAll('\\', '/')
  if (path.resolve(file) === TOKENS) continue
  for (const hit of hitsIn(stripComments(fs.readFileSync(file, 'utf8')))) {
    offenders.push(`${rel}:${hit.line}: ${hit.what}   ← ${hit.text}`)
  }
}
// ⚠️ 把扫描面**打出来**（不是只打一个数）：「扫了哪些文件」与「扫到几个 offender」
//    是两件事，前者是后者的分母，而分母错了的话「0 处」没有意义。
out(`  扫描面 ${scanned.length} 个文件（.css + .vue），其中 .css 是：`)
for (const file of scanned.filter((f) => f.endsWith('.css'))) {
  out(`    · ${path.relative(SRC, file).replaceAll('\\', '/')}`)
}

// ⚠️ 空转守卫：目录被搬空 / 路径指错时上面那个循环一条都不跑、offenders 恒为 []。
//    25 = 落地时实测 31（6 个 .css + 25 个 .vue）的下界；取 25 而不是 31 是给
//    「两个组件合并成一个」这类合法重构留一格（下界只能在它已经成立的前提下抬）。
if (scanned.length < 25) {
  fail(`只扫到 ${scanned.length} 个 .css/.vue（下界 25）——SRC 可能指错了: ${SRC}`)
} else {
  out(`  ✓ 扫描面 ${scanned.length} 个文件（下界 25）`)
}

out('')
if (offenders.length === 0) {
  out(`✓ 全绿：${scanned.length} 个文件里，tokens.css 之外一个色值字面量都没有`)
} else {
  out(`✗ ${offenders.length} 处色值字面量住在 tokens.css 之外：`)
  for (const line of offenders) out(`    ${line}`)
  out('')
  out('  处置：给它起一个**按用途**的名字（不要 --color-1 这种），搬进')
  out('        src/styles/tokens.css，然后把这里改成 var(--那个名字)。')
  out('        理由：Plan 05 要换肤，「改一个文件、全站变色」是它的可执行判据。')
  failures += 1
}

out('')
out(`退出码 ${failures === 0 ? 0 : 1}`)
process.exit(failures === 0 ? 0 : 1)
