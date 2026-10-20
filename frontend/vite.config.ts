import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

import vue from '@vitejs/plugin-vue'
import { defineConfig, type Plugin } from 'vite'

// ---------------------------------------------------------------------------
// ⚠️ **版本号的唯一住址是 `package.json` 的 `version`**（品牌与密度波）。
//    页脚那一行「版本」由 `src/brand.ts` 的 `VERSION` 读它，而 `brand.ts` 那一侧
//    只有一句 `declare const __PE_VERSION__: string` —— 编译期由下面这个 `define`
//    替换掉。⚠️ 刻意**不**在 `src/` 里 `import … from '../package.json'`：
//    那会把整份 package.json（含 `//` 那一段几百字、写给开发者的 smoke 警告）
//    打进**客户端产物**，而它不该发到浏览器上。
// ⚠️ 读文件用 `node:fs` 而不是 JSON import：`tsconfig.node.json` 是
//    `nodenext` + `verbatimModuleSyntax`，JSON 模块要额外写 import attributes，
//    而这里只需要一个字符串。
// ---------------------------------------------------------------------------
const PKG_VERSION = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
).version as string

// ---------------------------------------------------------------------------
// ⚠️ 后端地址只有一个住址：下面这个常量。
//
// 缺省 `http://127.0.0.1:8000` —— 计划第 1 节约束第 21 条的起服务口径。
// 用环境变量 `PE_API_TARGET` 覆盖（例如把演示后端起在 8011 时：
//   `$env:PE_API_TARGET="http://127.0.0.1:8011"; npm run dev`）。
//
// ⚠️ **走代理就不用碰 CORS**：**开发档**（`PE_ENV` 未设或 `=dev`，也就是本代理
//    唯一会碰到的那一档）后端 `app/main.py` 的 CORSMiddleware 是
//    `allow_origins=["*"]` 且**不带** `allow_credentials`，而浏览器规范禁止
//    `Access-Control-Allow-Origin: *` 与 credentials 并存 —— 一旦 `client.ts` 设了
//    `credentials: 'include'`，所有跨域请求会当场失败。开发期一律由下面这段
//    `server.proxy` 把 `/api` 转到同源，于是根本不存在跨域。
//    ⚠️ Plan 06 Task 4 起后端**生产档**改成读 `PE_CORS_ORIGINS`（缺省空 = 一个
//    `CORSMiddleware` 都不挂 = 拒绝跨域），白名单非空时带 `allow_credentials=True`；
//    那一档下前端要么同源、要么按 `client.ts` 顶部那五件事一起改。
//    ⚠️ 而 `prod` 下后端装配完还有一道**启动自检**：CORS 被挂成 `*`、或 cookie 的
//    `Secure` 没开 → `raise`，服务起不来。逐字见 spec §13.8。
// ⚠️ 但 `npm run build` 出来的是静态文件、没有代理，故 `client.ts` 的 baseURL
//    从 `import.meta.env.VITE_API_BASE ?? ''` 取：开发时是空串（走代理），
//    生产时由部署方注入。
// ---------------------------------------------------------------------------
const API_TARGET = process.env.PE_API_TARGET ?? 'http://127.0.0.1:8000'

// ---------------------------------------------------------------------------
// ⚠️⚠️ 构建清单（Plan 09 Task 1 = spec §15 **G22** 的代码级收口）
//
// 改前 `scripts/serve.ps1` 判「要不要重建 `dist`」用的是 **mtime**：源面里最新的
// 一个 mtime 比 `dist/index.html` 的构建戳新就重建。⚠️ 那个判据的失效方向是**故意**
// 折向重建的（「不确定」比「用一份陈产物」便宜），而代价是**一次与内容无关的批量
// 写回就能触发它**：`npm run gen:api` 重写一次 `schema.d.ts`、一次编辑器批量保存、
// 一次 `git checkout`、一次开机后的 checkout，都能把源面的 mtime 抬到构建戳之后
// —— 而那 4 个文件的**内容**与 HEAD 逐字相同。⚠️ 它**按请求从磁盘读 `dist`**，
// 于是不带 `-SkipBuild` 跑一次产品档 = 当场 `npm run build` = 活链接的前端在
// 几十秒内被换掉，而**已经打开的页面**去懒加载旧 chunk 会 404。
//
// 本波把判据换成**内容**：构建结束时写一份 `.build-manifest.json` 进 `dist/`，
// 里面是源面逐文件的 sha256 + 构建时刻 + 那次 build 的 git sha + 工作树脏不脏
// + 清单自己的形状版本。于是两件事同时成立：
//   ① 「源变了但内容没变」**不再触发重建**（G22 的那颗地雷被拆掉）；
//   ② 「这份产物是哪一个 commit 构建的」**第一次变得可查**（G22 的另一半，
//      与已划掉的 G10/G18 同族：包是一份时点快照，而快照今天自带出处）。
//
// ⚠️ **为什么住在这里（一个 vite 内联插件）而不是别处** —— 三个候选的成本对比：
//   ① **本档**（`closeBundle` 钩子）：`package.json` 的 `build` 脚本**一个字都不用改**
//      （它今天逐字是 `vue-tsc -b && vite build`，而 README「一条命令跑起来」第 ② 条
//      与说明书 §2 都逐字写着那条命令 ⇒ 改它就是改「一条命令」那一格、两份文档跟着核）；
//      而**任何**一条会跑 `vite build` 的路都自动得到清单（`npm run build`、
//      `serve.ps1` 的 ②、`check-dist.mjs` 自己那一次兜底构建、以及本波做实验用的
//      `npx vite build --outDir <scratch>`）⇒ 它不可能「构建过了而清单不在」。
//   ② 在 `build` 脚本后面串一步（`vue-tsc -b && vite build && node scripts/x.mjs`）：
//      要改 `package.json`（上面那一格的代价），⚠️ 而且**串的那一步可以被绕过**
//      （谁直接跑 `vite build` 就没有清单），于是「清单缺失」变成常态而不是异常。
//   ③ `serve.ps1` 自己在构建之后写：⚠️ 那份清单只覆盖了 serve.ps1 这一条路，
//      手跑 `npm run build` 出来的 `dist` 没有清单 ⇒ 而 `package.ps1` **刻意不构建**、
//      它打的就是「别人构建出来的那一份」⇒ 甲方那份包大概率没有清单。
//   ⇒ 选 ①：**它是唯一一个「与构建同生共死」的位置**。
//
// ⚠️ **零新增依赖**：`node:child_process` / `node:crypto` / `node:fs` / `node:path`
//   全是 Node 自带的（派单 §2 逐字要求「构建清单只能用标准库/BCL 生成」），
//   `package.json` 的 dependencies 与 devDependencies 一个字都没动。
// ---------------------------------------------------------------------------

/** 清单的**形状版本**（派单 §1 第 1 条 ⑤）。⚠️ 将来加字段时把它 +1，于是
 *  「一份旧清单」在读它的两侧都是**读不懂 ⇒ 折向重建 / 红**，而不是被静默当成新版。
 *  ⚠️ 这个数字与下面那个文件名各有**三个住址**（本文件 = 写它的一侧；
 *  `scripts/serve.ps1` 与 `frontend/scripts/check-dist.mjs` = 读它的两侧），
 *  三处必须逐字相同 ⇒ 守卫是 `backend/tests/test_serve.py` 的
 *  `test_the_build_manifest_contract_is_the_same_text_in_all_three_owners`
 *  （⚠️ 那一条按**字面量**钉，不从任一侧读回来跟自己比）。 */
const BUILD_MANIFEST_SCHEMA_VERSION = 1

/** 清单住在 `dist/` 里的**文件名**。⚠️ 前导点是刻意的：它不是要发给浏览器的资产
 *  （`app/static.py` 的白名单只认那五个扩展名 + `assets/` 前缀 ⇒ 它一个字节都不会
 *  被 HTTP 发出去），而 `frontend/.gitignore` 的 `dist/` 已经把它排除在入库之外
 *  （⚠️ 现量核实：`git check-ignore -v frontend/dist/.build-manifest.json` →
 *  `frontend/.gitignore:18:dist/`；⚠️ 而**不是** `.gitattributes` 挡的 ——
 *  那一份只钉行尾与二进制属性，不做排除）。
 *  ⚠️ 而它**要进包**：`scripts/package.ps1` 的 `$IncludeRoots` 含 `frontend`、
 *  枚举用 `Get-ChildItem -Force`（含点文件），而两份排除清单都不匹配这个名字
 *  ⇒ 它自动进包；⚠️ 并且已写进 `$MustContain` 与
 *  `backend/tests/test_package.py` 的 `REQUIRED_ENTRIES`（两侧各自独立地钉一次），
 *  于是「甲方那份包答不出它是哪一个 commit 构建的」这一档会**响亮地**失败。 */
const BUILD_MANIFEST_FILE = '.build-manifest.json'

/** **源面**：一份构建由哪些文件决定（相对 `frontend/`）。⚠️ 与改前 `serve.ps1` ②
 *  里那份 `$SourceRoots` 是**同一个集合**（`src/**` 的 59 个 + 6 个单文件 = **65** 个），
 *  而**从本波起本数组是它的唯一所有者**：`serve.ps1` 与 `check-dist.mjs` 都从清单的
 *  `sourceRoots` 那一格读回来，两侧于是不可能各自漂开一份「什么算源」。
 *  ⚠️ 刻意**不含** `package-lock.json`（如实记为一格已知的洞：一次 `npm install`
 *  只改锁文件时，mtime 判据与内容判据**都**看不出来 ⇒ 已报进 Task 1 报告的
 *  「关切」，本波刻意不扩面，因为 **65** 这个数被 spec §15 G22 与计划 09 §1
 *  逐字钉着，扩面等于改历史取证的口径）。 */
const BUILD_MANIFEST_SOURCE_ROOTS = [
  'src',
  'index.html',
  'package.json',
  'vite.config.ts',
  'tsconfig.json',
  'tsconfig.app.json',
  'tsconfig.node.json',
]

/** ⚠️ 反空转（硬规矩 #50；姿势逐字同改前 `serve.ps1` ② 里那一道 `< 20 就 throw`）：
 *  源面被搬空 / 路径指错时哈希表会是空的，而「空 == 空」为真 ⇒ 「dist 是新的」会假绿。 */
const BUILD_MANIFEST_MIN_FILES = 20

function walkSourceFiles(dir: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) found.push(...walkSourceFiles(full))
    else if (entry.isFile()) found.push(full)
  }
  return found
}

/** 枚举源面并逐个算 sha256。⚠️ 键是**相对 `frontend/` 的 posix 路径**
 *  （派单 §1 第 1 条：不许含绝对路径、不许反斜杠/正斜杠混用）；⚠️ 而**按字节**哈希
 *  工作树上那一份（不是 git blob）：读它的两侧（`serve.ps1` 的 `Get-FileHash`、
 *  `check-dist.mjs` 的 `node:crypto`）量的也是磁盘字节，故三侧同源。
 *  ⚠️ 代价如实记：换一台 `core.autocrlf` 配置不同的机器 checkout，`schema.d.ts`
 *  一类文件的**字节**会变 ⇒ 清单对不上 ⇒ 折向重建（安全的那一侧）。 */
function collectSourceSurface(frontendDir: string): Record<string, string> {
  const hashes = new Map<string, string>()
  for (const root of BUILD_MANIFEST_SOURCE_ROOTS) {
    const full = join(frontendDir, root)
    const stat = statSync(full, { throwIfNoEntry: false })
    const files = stat?.isDirectory() ? walkSourceFiles(full) : stat?.isFile() ? [full] : []
    for (const file of files) {
      const rel = relative(frontendDir, file).split(/[\\/]+/).join('/')
      hashes.set(rel, createHash('sha256').update(readFileSync(file)).digest('hex'))
    }
  }
  if (hashes.size < BUILD_MANIFEST_MIN_FILES) {
    throw new Error(
      `[build-manifest] 源面只扫到 ${hashes.size} 个文件（要 ≥ ${BUILD_MANIFEST_MIN_FILES}）：`
      + `${frontendDir} 可能被搬空或路径指错了，本插件不敢写一份会假绿的清单`,
    )
  }
  /* ⚠️ 排序后再落盘：`readdirSync` 的顺序是文件系统给的，而清单要能**按字节**对账
     （「同样的一份 src 构建两次，除了 builtAt 那一格以外逐字节相同」）。 */
  const surface: Record<string, string> = {}
  for (const rel of [...hashes.keys()].sort()) surface[rel] = hashes.get(rel)!
  return surface
}

/** 构建时**现场**问 git：那一次 build 的 commit、工作树脏不脏、以及**源面**里
 *  当时没提交的是哪几个。
 *  ⚠️ 三格全部允许 `null`：一台**没有 git** 的机器也要能构建（甲方 IT 那台就是），
 *  而「问不到」与「问到了、是干净的」是两件事 ⇒ 用 `null` 与 `false` 分开，
 *  不许把「问不到」静默当成「干净」（那正是硬规矩 #109 说的那一档假绿）。
 *  ⚠️ `dirtySources` 才是「这份产物能不能由 `gitSha` 复现」的判据：一次只改了
 *  文档的未提交改动让 `dirty=true`，而产物**仍然**逐字节可复现。 */
function collectGitInfo(frontendDir: string) {
  const run = (args: string[]): string | null => {
    try {
      return execFileSync('git', args, {
        cwd: frontendDir,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      })
    } catch {
      return null
    }
  }
  const head = run(['rev-parse', 'HEAD'])
  const gitSha = head !== null && /^[0-9a-f]{40}\s*$/.test(head) ? head.trim() : null
  const whole = run(['status', '--porcelain'])
  const dirty = whole === null ? null : whole.trim().length > 0
  let dirtySources: string[] | null = null
  if (dirty === false) {
    dirtySources = []
  } else if (dirty === true) {
    /* ⚠️ `git status --porcelain` 的路径一律相对**仓库根**，而源面的键相对
       `frontend/` ⇒ 那个前缀**现场问 git**（`rev-parse --show-prefix`），
       不写死 `frontend/`（写死就是把本仓的目录名焊进逻辑里）。 */
    const raw = run(['rev-parse', '--show-prefix'])
    const prefix = raw === null ? '' : raw.trim()
    const scoped = run(['status', '--porcelain', '--', ...BUILD_MANIFEST_SOURCE_ROOTS])
    dirtySources = scoped === null
      ? null
      : scoped
          .split('\n')
          .filter((line) => line.trim() !== '')
          .map((line) => {
            let path = line.slice(3).trim()
            const arrow = path.lastIndexOf(' -> ')
            if (arrow !== -1) path = path.slice(arrow + 4).trim()
            if (path.startsWith('"') && path.endsWith('"')) path = path.slice(1, -1)
            return prefix !== '' && path.startsWith(prefix) ? path.slice(prefix.length) : path
          })
          .sort()
  }
  return { gitSha, dirty, dirtySources }
}

/** 构建时刻。⚠️ **带本机实际的 UTC 偏移**（本仓既有口径是 `+08:00`，而这里
 *  **现场取**、不写死：写死一个 `+08:00` 等于把实现者那台机器焊进交付物，
 *  姿势逐字同 `serve.ps1` 的 `-Lan` 那一段「一个 IP 都不写死」）。
 *  ⚠️ 秒级精度、不带毫秒：清单要能按字节对账，而毫秒那一位每次都不一样。 */
function localTimestampWithOffset(at: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  const minutes = -at.getTimezoneOffset()
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  return (
    `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`
    + `T${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`
    + `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  )
}

/** 那个插件本体。⚠️ 它只有 `closeBundle` 一个钩子（= 全部产物都落盘之后），
 *  于是清单**不在** vite 自己的资产表里、也不参与任何哈希 ⇒ 它不会反过来
 *  改掉 bundle 的指纹（本波实测复核：26 个既有产物逐字节未变）。 */
function buildManifestPlugin(): Plugin {
  let frontendDir = ''
  let outDir = ''
  return {
    name: 'pe-build-manifest',
    apply: 'build',
    configResolved(config) {
      frontendDir = config.root
      outDir = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      const sources = collectSourceSurface(frontendDir)
      const git = collectGitInfo(frontendDir)
      const manifest = {
        schemaVersion: BUILD_MANIFEST_SCHEMA_VERSION,
        builtAt: localTimestampWithOffset(new Date()),
        gitSha: git.gitSha,
        dirty: git.dirty,
        dirtySources: git.dirtySources,
        sourceRoots: [...BUILD_MANIFEST_SOURCE_ROOTS],
        sources,
      }
      const target = join(outDir, BUILD_MANIFEST_FILE)
      writeFileSync(target, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
      const provenance = git.gitSha === null
        ? 'git 问不到（本机没有 git / 不在仓库里）⇒ 出处那一格是 null'
        : `${git.gitSha.slice(0, 12)}${git.dirty === true ? '（⚠️ 脏构建）' : '（净构建）'}`
      console.log(
        `[build-manifest] ${target}\n`
        + `                 源面 ${Object.keys(sources).length} 个文件的 sha256 · `
        + `${manifest.builtAt} · ${provenance}`,
      )
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), buildManifestPlugin()],
  define: {
    __PE_VERSION__: JSON.stringify(PKG_VERSION),
  },
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      // ⚠️ 管理台的表单是**契约驱动**的（`src/api/contract.ts` 读
      //    `components.schemas[*Create | *Update]` 决定画哪几格），而
      //    `/openapi.json` **不在 `/api` 前缀下** → 不加这一条，开发期它会打到
      //    vite 自己身上（回一份 index.html，于是 `JSON.parse` 当场失败）。
      //    后端地址仍然只有 `API_TARGET` 一个住址。
      '/openapi.json': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
