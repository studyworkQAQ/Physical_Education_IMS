# 实施计划 04 · Task 1 实现报告 —— 工程骨架 + 设计系统 + 类型化客户端 + 身份切换器

> **日期**：2026-10-11 · **分支**：`feature/plan-04-frontend` · **起点 HEAD**：`ba87156`
> **范围**：计划第 5 节 Task 1 的第 2–10 步（第 1 步经核实是多余的，见第 6 节）
> **交付**：5 个 commit（4 个装 `frontend/` 的 28 个文件 + 1 个装本报告）、`frontend/` 从无到有（`npm run build` 退出码 **0**、无 TS 报错）

---

## ① 环境

硬规矩 #73（环境先行）的三行原文：

```
$ node --version
v24.19.0
$ npm --version
11.17.0
$ python -c "import fastapi, sqlalchemy; print(fastapi.__version__, sqlalchemy.__version__)"
0.141.1 2.1.3
```

| | 版本 | 判据 |
|---|---|---|
| Node.js | **v24.19.0** | ✅ Vite 8 要求 20.19+ / 22.12+，24 远超 |
| npm | **11.17.0** | ✅ |
| Python | 3.11.1（无 venv） | ✅ |
| FastAPI | **0.141.1** | ✅ 与 `crud.py:590` 注释里那个「本机 FastAPI 0.141.1 亲跑验证」同版本 |
| SQLAlchemy | **2.1.3** | ✅ |
| 操作系统 | Windows + PowerShell 5.1 | ⚠️ 全部写文件走 python；`;` 分隔；无 `&&` |

**没有触发「立刻停手报回」的两档**：Node 版本够；`import fastapi, sqlalchemy` 没有 `ImportError: DLL load failed`。

---

## ② 工程骨架

### 2.1 `package.json` 的依赖逐个版本号

**dependencies**（3 个）

| 包 | 声明 | 实装（`npm ls`） |
|---|---|---|
| `pinia` | `^3.0.4` | — |
| `vue` | `^3.5.43` | — |
| `vue-router` | `^4.6.4` | — |

**devDependencies**（7 个）

| 包 | 声明 |
|---|---|
| `@types/node` | `^24.13.3` |
| `@vitejs/plugin-vue` | `^6.0.10` |
| `@vue/tsconfig` | `^0.9.1` |
| `openapi-typescript` | `^7.13.0` |
| `typescript` | `~5.9.3` |
| `vite` | `^8.3.4` |
| `vue-tsc` | `^3.3.13` |

`npm ls --depth=0` 的**实装**版本（与声明的 `^` 区间对得上）：

```
├── openapi-typescript@7.13.0
├── pinia@3.0.4
├── typescript@5.9.3
├── vite@8.3.4
├── vue-router@4.6.4
├── vue-tsc@3.3.13
└── vue@3.5.43
```

⚠️ `@types/node@^24.13.3`、`@vitejs/plugin-vue@^6.0.10`、`@vue/tsconfig@^0.9.1` 是 `npm ls` 那一屏没打出来的三个（它们不在 `--depth=0` 的直接依赖树的第一屏上），声明版本见上表。

**scripts**（5 个，⚠️ `smoke` 是 Task 5 的活，今天**没有**）：

```json
{
  "dev": "vite",
  "build": "vue-tsc -b && vite build",
  "preview": "vite preview",
  "gen:api": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/schema.d.ts"
}
```

⚠️ **没有 `frontend/scripts/gen-api.mjs`**：派单说「若你不用 `openapi-typescript` 的 CLI 直调」才要它。我们**就是**直调 CLI（`npm run gen:api` 那一行），故不造这个文件 —— 造了就是给一个一行命令加一层壳。

### 2.2 `vite.config.ts` 的代理配置（原文）

```ts
const API_TARGET = process.env.PE_API_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
```

⚠️ 与派单逐字一致的那三件事：`target` 是 `http://127.0.0.1:8000`、`changeOrigin: true`、**没有** `credentials`。
多出来的一件是 `PE_API_TARGET` 环境变量覆盖（缺省仍是 8000）—— `demo.ps1` 的缺省端口是 **8010**（实测 `$Port = 8010`），故「用 demo.ps1 起后端 + 用 dev server 连它」这一档不必改代码。

### 2.3 `client.ts` 的 baseURL

```ts
const BASE_URL: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
```

开发时是空串（走代理，同源，不存在跨域）；生产时由部署方注入 `VITE_API_BASE`。`tsconfig.app.json` 的 `"types": ["vite/client"]` 是 `import.meta.env` 能被认出来的前提（⚠️ 本工程**没有** `src/vite-env.d.ts`，也不需要）。

### 2.4 `npm run build` 的退出码与产物大小

```
> vue-tsc -b && vite build
vite v8.3.4 building client environment for production...
✓ 63 modules transformed.
dist/index.html                   1.89 kB │ gzip:  1.20 kB
dist/assets/index-B-WoZeAF.css   26.78 kB │ gzip:  5.31 kB
dist/assets/index-C7PRNDIB.js   135.96 kB │ gzip: 51.16 kB
✓ built in 203ms
BUILD_EXIT=0
```

| 产物 | 大小 | gzip |
|---|---|---|
| `dist/index.html` | 1.89 kB | 1.20 kB |
| `dist/assets/index-B-WoZeAF.css` | 26.78 kB | 5.31 kB |
| `dist/assets/index-C7PRNDIB.js` | 135.96 kB | 51.16 kB |

⚠️ **`vue-tsc -b` 是这次交付里最有用的一拍**：它在 `catalog/resources.ts` 上查出 **17 条** `TS2322`（详见第 6 节「顶回」的第 5 处），在 `endpoints.ts` 上查出 **21 条**（`PageQuery` 是 `interface` 而不是 `type`）。两者都不是渲染 bug，都是**类型系统层面的谎**，而 `npm run dev` 一律不报。

---

## ③ 设计系统

### 3.1 `tokens.css` 的全部自定义属性（**110 个**，从文件里正则出来的，不是手数）

⚠️ 它是设计令牌的**唯一住址**：文件里不含任何选择器，`base.css` / `lane.css` / 五个组件一律 `var(--…)` 它。

| # | 属性 | 值 |
|---|---|---|
| 1 | `--ink` | `#14110f` |
| 2 | `--paper` | `#f4f0e6` |
| 3 | `--track` | `#be3f2b` |
| 4 | `--paper-sunken` | `#e9e3d4` |
| 5 | `--paper-raised` | `#fbf8f1` |
| 6 | `--ink-soft` | `#4a423a` |
| 7 | `--ink-faint` | `#7a6f62` |
| 8 | `--rule-hairline` | `#cdc4b2` |
| 9 | `--ink-raised` | `#1e1a17` |
| 10 | `--ink-sunken` | `#0c0a09` |
| 11 | `--paper-soft` | `#cdc4b4` |
| 12 | `--paper-faint` | `#8d8478` |
| 13 | `--rule-hairline-on-ink` | `#38312b` |
| 14 | `--red-on-paper` | `#b3352b` |
| 15 | `--amber-on-paper` | `#8a5a10` |
| 16 | `--moss-on-paper` | `#3e6647` |
| 17 | `--track-on-paper` | `#be3f2b` |
| 18 | `--red-on-ink` | `#e8695c` |
| 19 | `--amber-on-ink` | `#e8b44a` |
| 20 | `--moss-on-ink` | `#7fb98c` |
| 21 | `--track-on-ink` | `#e4674f` |
| 22 | `--red` | `#b3352b` |
| 23 | `--amber` | `#c98a22` |
| 24 | `--moss` | `#4c7a57` |
| 25 | `--red-wash` | `#f2ddd8` |
| 26 | `--amber-wash` | `#f3e6cc` |
| 27 | `--moss-wash` | `#dfe7dc` |
| 28 | `--red-wash-on-ink` | `#3a1f1c` |
| 29 | `--amber-wash-on-ink` | `#3a2f16` |
| 30 | `--moss-wash-on-ink` | `#1d2c22` |
| 31 | `--font-display` | `'Barlow Condensed', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif` |
| 32 | `--font-zh-title` | `'Noto Serif SC', 'Songti SC', 'SimSun', 'PingFang SC', 'Microsoft YaHei', serif` |
| 33 | `--font-body` | `'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif` |
| 34 | `--font-data` | `'JetBrains Mono', 'Barlow Condensed', 'PingFang SC', 'Microsoft YaHei', ui-monospace, monospace` |
| 35 | `--fw-display-600` | `600` |
| 36 | `--fw-display-700` | `700` |
| 37 | `--fw-display-800` | `800` |
| 38 | `--fw-zh-title-700` | `700` |
| 39 | `--fw-zh-title-900` | `900` |
| 40 | `--fw-body-400` | `400` |
| 41 | `--fw-body-500` | `500` |
| 42 | `--fs-hero` | `clamp(56px, 15vw, 104px)` |
| 43 | `--fs-display` | `clamp(34px, 9vw, 56px)` |
| 44 | `--fs-title` | `24px` |
| 45 | `--fs-subtitle` | `18px` |
| 46 | `--fs-body` | `15px` |
| 47 | `--fs-small` | `13px` |
| 48 | `--fs-micro` | `11px` |
| 49 | `--fs-bs-hero` | `clamp(72px, 6vw, 128px)` |
| 50 | `--fs-bs-display` | `56px` |
| 51 | `--fs-bs-title` | `32px` |
| 52 | `--fs-bs-subtitle` | `24px` |
| 53 | `--fs-bs-body` | `20px` |
| 54 | `--fs-bs-small` | `18px` |
| 55 | `--lh-tight` | `0.92` |
| 56 | `--lh-heading` | `1.18` |
| 57 | `--lh-body` | `1.62` |
| 58 | `--tracking-condensed` | `0.01em` |
| 59 | `--tracking-lane-num` | `0.08em` |
| 60 | `--tracking-caps` | `0.14em` |
| 61 | `--lane-thick` | `3px` |
| 62 | `--lane-thin` | `1px` |
| 63 | `--lane-offset` | `6px` |
| 64 | `--lane-rule-height` | `calc(var(--lane-thick) + var(--lane-offset) + var(--lane-thin))` |
| 65 | `--lane-num-size` | `10px` |
| 66 | `--lane-num-weight` | `800` |
| 67 | `--lane-num-tracking` | `var(--tracking-lane-num)` |
| 68 | `--lane-num-width` | `18px` |
| 69 | `--lane-gap` | `10px` |
| 70 | `--lane-block-gap` | `28px` |
| 71 | `--space-1` | `4px` |
| 72 | `--space-2` | `8px` |
| 73 | `--space-3` | `12px` |
| 74 | `--space-4` | `16px` |
| 75 | `--space-5` | `24px` |
| 76 | `--space-6` | `32px` |
| 77 | `--space-7` | `48px` |
| 78 | `--space-8` | `64px` |
| 79 | `--space-9` | `96px` |
| 80 | `--w-student` | `375px` |
| 81 | `--w-teacher` | `1440px` |
| 82 | `--gutter` | `16px` |
| 83 | `--bleed` | `-16px` |
| 84 | `--grid-columns` | `12` |
| 85 | `--grid-gap` | `20px` |
| 86 | `--span-alerts` | `5` |
| 87 | `--span-layers` | `4` |
| 88 | `--span-overview` | `3` |
| 89 | `--radius-none` | `0` |
| 90 | `--radius-sharp` | `2px` |
| 91 | `--radius-stamp` | `4px` |
| 92 | `--border-hairline` | `1px solid var(--rule-hairline)` |
| 93 | `--border-hairline-on-ink` | `1px solid var(--rule-hairline-on-ink)` |
| 94 | `--border-ink` | `2px solid var(--ink)` |
| 95 | `--shadow-paper` | `0 1px 0 rgba(20, 17, 15, 0.06), 0 8px 20px -14px rgba(20, 17, 15, 0.35)` |
| 96 | `--shadow-raised` | `0 2px 0 rgba(20, 17, 15, 0.08), 0 18px 34px -20px rgba(20, 17, 15, 0.45)` |
| 97 | `--grain-opacity` | `0.035` |
| 98 | `--track-arc-opacity` | `0.06` |
| 99 | `--track-arc-radius` | `1400px` |
| 100 | `--reveal-stagger` | `60ms` |
| 101 | `--dur-lane` | `620ms` |
| 102 | `--dur-roll` | `900ms` |
| 103 | `--dur-stamp` | `460ms` |
| 104 | `--dur-fast` | `140ms` |
| 105 | `--ease-lane` | `cubic-bezier(0.22, 1, 0.36, 1)` |
| 106 | `--ease-stamp` | `cubic-bezier(0.34, 1.56, 0.64, 1)` |
| 107 | `--ease-linear` | `linear` |
| 108 | `--focus-ring` | `2px solid var(--track)` |
| 109 | `--focus-ring-on-ink` | `2px solid var(--track-on-ink)` |
| 110 | `--focus-offset` | `2px` |

### 3.2 四款字体的 family 名与 weight

| 用途 | family | weights | 回退栈（`--font-*` 里给全） |
|---|---|---|---|
| 数字与拉丁标题 | `Barlow Condensed` | 500 / 600 / 700 / **800** | `'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif` |
| 中文标题 | `Noto Serif SC` | **700 / 900** | `'Songti SC', 'SimSun', 'PingFang SC', 'Microsoft YaHei', serif` |
| 正文 | `Noto Sans SC` | 400 / 500 / 700 | `'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif` |
| 数据表格与代码 | `JetBrains Mono` | 400 / 600 | `'Barlow Condensed', 'PingFang SC', 'Microsoft YaHei', ui-monospace, monospace` |

`index.html` 里的那一条 Google Fonts URL（`preconnect` 两个域 + `display=swap`）：

```
https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800&family=JetBrains+Mono:wght@400;600&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@700;900&display=swap
```

⚠️ 技能明令禁止的 Inter / Roboto / Arial / system-ui **一个都没有**；也**没有**收敛到 Space Grotesk。
⚠️ `Barlow Condensed` 多请求了 **500** 一档（计划只写 600/700/800）—— `--fw-display-600` 之下还要有一档更轻的拉丁小标题，否则 `.caps` 在 11px 上会糊成一团。这是**一处对计划的加宽**，记在第 6 节。

### 3.3 分道线母题的三个尺寸值

| | 令牌 | 值 | 出处 |
|---|---|---|---|
| 粗线 | `--lane-thick` | **3px**，色 `--ink`（深底换 `--paper`） | 计划第 2 节 / Task 1 第 5 步逐字 |
| 细线 | `--lane-thin` | **1px**，色 `--track` | 同上 |
| 偏移 | `--lane-offset` | **6px**（细线相对粗线向下） | 同上 |
| 道次编号 | `--lane-num-size` / `-weight` / `-tracking` | **10px** / **800** / **0.08em**，family `Barlow Condensed` | 同上 |
| 合成 | `--lane-rule-height` | `calc(3px + 6px + 1px)` = **10px** | 派生 |
| 占位 | `--lane-num-width` | 18px（两个数字等宽，保证各区块的线左端对齐） | 实现者加 |

实现：`.lane__rule::before`（粗）+ `::after`（细，`top: calc(var(--lane-thick) + var(--lane-offset))`），两条都是 `transform: scaleX(0→1)` + `transform-origin: left center`，`animation-delay: calc(var(--lane-index, 0) * var(--reveal-stagger))`（60ms 递增），细线再 +90ms（读起来是「一条线，然后是它的影子」）。keyframes：`lane-draw` / `lane-block-in`；盖章动效的 `stamp-hit` / `stamp-spread` 在 `StampFeedback.vue` 里。

⚠️ **一个静默失效点已在 `lane.css` 里挡掉**：`.lane` 与 `.lane-block` 上**不能**声明 `--lane-index: 0` —— 元素自身的声明会盖掉从父级继承下来的值，于是整页的 stagger 全部退化成 delay 0。缺省值一律写在 `var(--lane-index, 0)` 里。

### 3.4 纸张纹理的实现方式

两层，都不引图片文件：

1. **纸的颗粒**（`base.css` 的 `body::before`）：一个 **data URI 的内联 SVG**，`<feTurbulence type='fractalNoise' baseFrequency='0.84' numOctaves='4' stitchTiles='stitch'/>` + `<feColorMatrix type='saturate' values='0'/>`（去饱和）铺满一张 260×260 的 `<rect>`，`background-size: 260px 260px` 平铺，`opacity: var(--grain-opacity)` = **0.035**（计划第 2 节逐字），`position: fixed` + `pointer-events: none`（颗粒是「纸」的属性，滚动时不跟着走）。`#app` 用 `position: relative; z-index: 1` 压在它之上。
2. **跑道弧**（`base.css` 的 `.surface-ink`，只给教师大屏）：`repeating-radial-gradient(circle at 112% -18%, …)` 的同心弧（= 分道线在大尺度上的样子）叠一层 `radial-gradient(var(--track-arc-radius) … at 112% -18%, rgba(190,63,43,.14), transparent 62%)`，`--track-arc-radius: 1400px`（大半径、偏在右上角）、`--track-arc-opacity: 0.06`，`background-attachment: fixed`。

### 3.5 语义三色的两个变体与实测对比度

⚠️ **计划给的三个原色里有两个在 `--paper` 上不过 WCAG AA 的 4.5:1**，故 `on-paper` 那一档压深过（原色值另存 `--red` / `--amber` / `--moss` 给色块与图例用）：

| 语义 | 计划给的原色 | 在 `--paper` 上 | 对比度 | 在 `--ink` 上 | 对比度 |
|---|---|---|---|---|---|
| red | `#B3352B` | `--red-on-paper: #b3352b` | 5.33:1 ✅ | `--red-on-ink: #e8695c` | 5.97:1 ✅ |
| amber | `#C98A22` | `--amber-on-paper: **#8a5a10**`（压深） | 5.20:1 ✅ （原色只有 **2.58:1** ❌） | `--amber-on-ink: #e8b44a` | 9.99:1 ✅ |
| moss | `#4C7A57` | `--moss-on-paper: **#3e6647**`（压深） | 5.77:1 ✅ （原色只有 **4.36:1** ❌） | `--moss-on-ink: #7fb98c` | 8.26:1 ✅ |
| track | `#BE3F2B` | `--track-on-paper: #be3f2b` | 4.69:1 ✅ | `--track-on-ink: #e4674f` | 5.74:1 ✅ |

⚠️ `--track`（#BE3F2B）与 `--red`（#B3352B）**刻意不同色值**：前者是母题/点缀，后者是红色预警。同色的话，大屏上「一条分道线」会被读成「一条红色预警」。

### 3.6 三个原子组件

| 组件 | 字节 | 要点 |
|---|---|---|
| `LaneDivider.vue` | 2 338 | props `index` / `label` / `tone: paper\|ink` / `level: default\|red\|amber\|moss`。⚠️ **组件里零样式**，全在 `lane.css`（母题的住址）。`index` 同时驱动 stagger 的 `--lane-index`。语义变体**只换细线颜色**，粗线永远是墨/纸。 |
| `StatBlock.vue` | 7 230 | props `value: number \| null \| undefined` / `label` / `unit` / `decimals` / `tone` / `size: hero\|display\|body` / `caption` / `level`。**数字滚动**用 `requestAnimationFrame`，时长**从 CSS 令牌读**（`getComputedStyle(…).getPropertyValue('--dur-roll')`），不写第二份字面量。⚠️ `value` 为 `null`/`undefined` → 渲染 `.unknown` 的「—」，**不是 0**（约束第 10 条）。 |
| `StampFeedback.vue` | 6 719 | props `visible` / `text` / `caption` / `tone: moss\|track\|red\|amber` / `surface: paper\|ink`。`scale(1.4→1)` + 一次轻微旋转 + 印泥色扩散（`stamp-hit` / `stamp-spread`）。 |

⚠️ 全局 `@media (prefers-reduced-motion: reduce)` 把三处动效一起关掉（`animation-duration: 0.01ms !important`）。

---

## ④ API 层

### 4.1 `openapi-typescript` 的版本与产物的取值路径

**版本：`openapi-typescript@7.13.0`**（⚠️ 是 v7 不是 v8 —— 派单说「自己选一个当前稳定的」，v7.13.0 是 7.x 的末版；v8 的 `components['schemas']` 引用方式变了，而本仓的 23 个手写 list 类型全部靠 `components['schemas']['XRead']` 取值，升 v8 要重写 `types.ts` 的每一行，收益为 0。

产物：`frontend/src/api/generated/schema.d.ts`，**338 756 B / 7 971 行**，**已入库**。

命令（`npm run gen:api`）：

```
openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/schema.d.ts
✨ openapi-typescript 7.13.0
🚀 http://127.0.0.1:8000/openapi.json → src/api/generated/schema.d.ts [165ms]
```

⚠️⚠️ **Task 2–4 照这个取值路径写**（v7 的形状，实测）：

```ts
import type { components, operations, paths } from './generated/schema'

// ① 一个 Read/Create/Update 模型
type S = components['schemas']
type StudentRead = S['StudentRead']          // → { id: number; student_no: string; … }

// ② 一个操作的响应体（**detail 端点可用，list 端点是 { [key: string]: unknown }**）
type Op = operations['list_rows_api_students_get']
type Body = Op['responses'][200]['content']['application/json']

// ③ 从路径进（v7 的 paths 只给到 operationId，**不给**内联的响应体）
type P = paths['/api/students']['get']       // → { parameters: …; responses: … }（v7 里是内联展开的）
```

⚠️ **v7 与派单里写的取值路径的一处差别**：派单说 v7 是 `paths["/x"]["get"]["responses"][200]["content"]["application/json"]`。实测 v7.13.0 的 `paths` 里**每个 method 只给一行** `get: operations["<operationId>"]`，**响应体内联在 `operations` 那一侧**。故要拿响应体必须走 `operations['<operationId>']['responses'][200]['content']['application/json']`。`operationId` 是 FastAPI 自动生成的（`list_rows_api_students_get` / `read_one_api_students__student_id__get` / `create_row_api_students_post` …），**不是**我们起的名字 → 记在第 6 节「顶回」第 2 处。

`parameters` 一侧仍然是内联的，可以直接读：

```ts
operations['list_rows_api_students_get']['parameters']['query']  // → { limit?: number; offset?: number }
operations['create_row_api_students_post']['parameters']['header'] // → { "x-teacher-staff-no"?: string | null }
```

**产物的稳定性**：重跑一次 `npm run gen:api`，SHA256 逐字不变 —— `A40DD5ECF198BCE7EA79ED513A6966A209E4B4072FB93578124CBFF72E9022F3`，338 756 B 前后相同。

### 4.2 实测那 24 个未定型响应的清单

数法（**运行时口径**，不是正则数源码）：`GET /openapi.json` → 遍历 64 个 `/api/` 路径模板的 92 个操作，挑出「某个 2xx 响应的 `content['application/json'].schema` 逐字是 `{"type": "object", "additionalProperties": true}`」的。

**命中 24 个，与计划的 24 逐字一致**：

| # | 操作 | | # | 操作 |
|---|---|---|---|---|
| 1 | `GET /api/alerts [200]` | | 13 | `GET /api/notifications [200]` |
| 2 | `GET /api/body-compositions [200]` | | 14 | `GET /api/percentile-snapshots [200]` |
| 3 | `GET /api/class-sessions [200]` | | 15 | `GET /api/prescription-templates [200]` |
| 4 | `GET /api/course-sections [200]` | | 16 | `GET /api/prescriptions [200]` |
| 5 | `GET /api/derived-metrics [200]` | | 17 | `GET /api/rpe-records [200]` |
| 6 | `GET /api/enrollments [200]` | | 18 | `GET /api/semesters [200]` |
| 7 | `GET /api/exercises [200]` | | 19 | `GET /api/stratification-results [200]` |
| 8 | `GET /api/fitness-test-batches [200]` | | 20 | `GET /api/students [200]` |
| 9 | `GET /api/fitness-test-results [200]` | | 21 | `GET /api/teachers [200]` |
| 10 | `GET /api/health [200]` | | 22 | `GET /api/training-logs [200]` |
| 11 | `GET /api/interest-surveys [200]` | | 23 | `GET /api/weekly-adjustments [200]` |
| 12 | `GET /api/mini-tests [200]` | | 24 | `GET /api/weekly-class-reports [200]` |

**从产物里独立复核了一遍**（不同源，故不是自证）：`schema.d.ts` 里 `[key: string]: unknown;` 逐字出现 **42** 次，其中

- **24** 次落在 `export interface operations { … }` 内 → 就是上面这 24 个；
- **18** 次落在 `export interface components { … }` 内 → Read 模型上那些自由形状的 JSON 列；
- **0** 次落在 `export interface paths { … }` 内（v7 的 `paths` 只放 `operations[…]` 的引用）。

⚠️ `types.ts:7764-7775` 那条行号引用**实测准确**：那正是 `list_rows_api_alerts_get` 的 `responses` 块，第 7772 行逐字是 `[key: string]: unknown;`。

### 4.3 23 个手写 list 类型：字段数与 `list_exclude`

⚠️⚠️ **这一节是对计划约束第 5 条的更正**，是本 Task 最重要的一处发现。详见第 6 节「顶回」第 1 处。

后端 `app/api/crud.py:582-585` 的算式逐字是：

```python
excluded = (
    tuple(list_exclude) if list_exclude is not None else _json_text_columns(model)
)
kept = [column.name for column in table.columns if column.name not in excluded]
```

即：**没有显式声明 `list_exclude` 的资源，排掉的是 `_json_text_columns(model)` 自动探测出来的全部 `JsonText` 列**（判据是 `isinstance(column.type, JsonText)`，`crud.py:237-259`；它的 docstring 逐字写了「实测全库 21 个 `JsonText` 列，其中 19 个落在这 23 个资源上，分布在 8 张表」）。

| # | 资源 | `*Read` | Read 字段数 | **生效的** excluded | 排掉几列 | **list 项字段数** | 实测 | 显式 `list_exclude` | 口径 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `semesters` | `SemesterRead` | 6 | — | **0** | **6** | 6 | — | 实测响应体 |
| 2 | `teachers` | `TeacherRead` | 3 | — | **0** | **3** | 3 | — | 实测响应体 |
| 3 | `students` | `StudentRead` | 7 | — | **0** | **7** | 7 | — | 实测响应体 |
| 4 | `course-sections` | `CourseSectionRead` | 6 | — | **0** | **6** | 6 | — | 实测响应体 |
| 5 | `enrollments` | `EnrollmentRead` | 4 | — | **0** | **4** | 4 | — | 实测响应体 |
| 6 | `fitness-test-batches` | `FitnessTestBatchRead` | 6 | — | **0** | **6** | 6 | — | 实测响应体 |
| 7 | `fitness-test-results` | `FitnessTestResultRead` | 21 | — | **0** | **21** | 21 | — | 实测响应体 |
| 8 | `body-compositions` | `BodyCompositionRead` | 8 | — | **0** | **8** | 8 | — | 实测响应体 |
| 9 | `interest-surveys` | `InterestSurveyRead` | 7 | `dimensions`, `raw_answers` | **2** | **5** | 5 | — | 实测响应体 |
| 10 | `percentile-snapshots` | `PercentileSnapshotRead` | 14 | — | **0** | **14** | 14 | — | 实测响应体 |
| 11 | `derived-metrics` | `DerivedMetricsRead` | 11 | `annual_change`, `body_comp_reasons`, `weaknesses` | **3** | **8** | 8 | — | 实测响应体 |
| 12 | `stratification-results` | `StratificationResultRead` | 10 | `input_snapshot` | **1** | **9** | 9 | — | 实测响应体 |
| 13 | `exercises` | `ExerciseRead` | 7 | `targets` | **1** | **6** | 空表 | — | 目录（演示库该表为空，无法实测） |
| 14 | `prescription-templates` | `PrescriptionTemplateRead` | 10 | — | **0** | **10** | 空表 | — | 目录（演示库该表为空，无法实测） |
| 15 | `prescriptions` | `PrescriptionRead` | 16 | `assembly_snapshot`, `safety_substitutions`, `teacher_overrides`, `training_package`, `trigger_reasons` | **5** | **11** | 11 | — | 实测响应体 |
| 16 | `weekly-adjustments` | `WeeklyAdjustmentRead` | 8 | — | **0** | **8** | 8 | — | 实测响应体 |
| 17 | `class-sessions` | `ClassSessionRead` | 6 | — | **0** | **6** | 6 | `rpe_token` | 实测响应体 |
| 18 | `rpe-records` | `RpeRecordRead` | 6 | — | **0** | **6** | 6 | — | 实测响应体 |
| 19 | `training-logs` | `TrainingLogRead` | 11 | — | **0** | **11** | 11 | — | 实测响应体 |
| 20 | `mini-tests` | `MiniTestRead` | 10 | `item_combo` | **1** | **9** | 9 | — | 实测响应体 |
| 21 | `alerts` | `AlertRead` | 14 | `trigger_snapshot` | **1** | **13** | 13 | — | 实测响应体 |
| 22 | `notifications` | `NotificationRead` | 10 | — | **0** | **10** | 10 | — | 实测响应体 |
| 23 | `weekly-class-reports` | `WeeklyClassReportRead` | 12 | `alert_summary`, `checkin_rate_by_layer`, `layer_distribution`, `progress_board`, `rpe_summary` | **5** | **7** | 7 | — | 实测响应体 |

合计：Read 字段 **213** 个，相对 `*Read` 生效的 excluded **19** 个（分布在 **8** 个资源上，即那 8 张有 `JsonText` 列的表）。

⚠️ 第 17 行（`class-sessions`）读起来像是「声明了 `list_exclude` 却什么都没排」—— **这是对的**，两列说的不是一件事：`显式 list_exclude` 那一列是后端目录里写了什么（`("rpe_token",)`，它排的是**表列**），`生效的 excluded` 那一列是**相对 `*Read` 字段集**少了什么。`rpe_token` 在收尾小修波里已经从 `ClassSessionRead` 上摘掉了，故它不在 Read 的 6 个字段里、也就不可能出现在这个差集里。实测匿名 `GET /api/class-sessions` 的 `items[0]` 键集合逐字是 `batch_id, course_section_id, id, period, rpe_opened, session_date` —— **不含口令** ✅。

**对称差核对**（手写类型声明排掉的 vs 实测/目录里少掉的，逐个资源比集合）：

✅ **23/23 的对称差全为空** —— `types.ts` 里每一个 `OmitStrict<…>` 排掉的键集合，与后端 `kept` 的补集逐个相等。

⚠️ 两个资源在演示库里是**空表**（`exercises` / `prescription-templates`，`total=0`），故它们的 list 键集合**无法实测**。`exercises` 的那一列（`targets`）由 `_json_text_columns` 的口径 + `catalog/resources.ts` 的 `listExclude` 双重确认；`prescription-templates` 一个 `JsonText` 列都没有，故 list 键集合 == Read 字段集（10）。⚠️ **Task 5 的联调脚本应当在灌过参考数据的库上把这两个补齐**（记在第 6 节待清扫）。

⚠️ `OmitStrict<T, K extends keyof T>` 而不是原生 `Omit`：原生 `Omit` 对「`K` 不在 `T` 上」**静默通过**，而那正是本文件最容易变成一句谎的地方 —— 后端哪天把一个 `JsonText` 列从 Read 模型上摘掉（正如收尾小修波对 `rpe_token` 做的那样），原生 `Omit` 照样编译通过，而这一行会声称有一个 list 端点根本不返回的字段。加了 `K extends keyof T` 之后，那一档是 `npm run build` 的红。**这条守卫本轮已经抓到过一次真东西**（`class-sessions`：`rpe_token` 早已不在 `ClassSessionRead` 上，写 `OmitStrict<…, 'rpe_token'>` 会当场编译报错，见第 6 节顶回第 1 处）。

### 4.4 `client.ts` 的四件职责各自的落地行号

⚠️ **恰好四件，没有第五件**（不重试、不缓存、不管 loading —— 那些是调用方的事）。

| # | 职责 | 落地位置 | 关键行 |
|---|---|---|---|
| ① | 注入身份头（从 `stores/identity` 读） | `identityHeaders()` 定义在 **288-300**，调用在 **313**（`...identityHeaders()`） | ⚠️ **一次只注入一个头**；未选身份返回 `{}`（47 个 GET 全部匿名，故「没身份」不是错误） |
| ② | 把 `{"error":{code,message,detail}}` 解析成 `ApiError` 并抛出 | `class ApiError` 在 **208-246**；解析与抛出在 **331-349**（`throw new ApiError(…)` 在 **348**） | ⚠️ 解析失败**退化**而不是二次抛错（反代造的 502/504 可能是 HTML 或空体）→ 退回 `http_<status>` |
| ③ | 拼 `as_of` / `limit` / `offset` 查询参数 | `buildQuery()` 在 **266-278**，拼接在 **310**（`const url = \`${BASE_URL}${path}${buildQuery(init.query)}\``） | `null`/`undefined` 一律**不拼进查询串**；空对象返回空串（不是 `?`） |
| ④ | `204` 不解析 body | **326-329**（`if (res.status === 204 \|\| res.status === 205) return undefined as T`） | ⚠️ 排在 `!res.ok` **之前**；实测后端有 **8** 个 `204`，全是 DELETE |

**`credentials` 的核实**：`client.ts` 里 `credentials` 一词只出现在**注释**里（第 14/17/18/19/24 行，解释为什么不设），`fetchInit` 的构造（**316-322**）里**没有**这个键，第 **318** 行还留了一句 `// ⚠️ 没有 credentials。理由见本文件顶部那段。`

### 4.5 完整的错误 code 清单（AST 实测）

**数法**（硬规矩 #89：AST 口径，不用正则数源码）：对 `backend/app/**/*.py` 做 `ast.walk`，挑出全部 `error_response(…)` 调用点（**15** 个），把**第 2 个位置实参**解出来（它是 `code`；字面量直接取，是名字的回到模块级常量表取）；再把 `app/api/errors.py:56-63` 的 `_CODE_BY_STATUS` 与 `errors.py:142` 那句 `f"http_{status}"` 折算进来。⚠️ 派单说「`Grep` 后端 `app/api/` 下全部 `code=` 或 `"code":` 的命中」—— **那个 grep 抓不到**：15 个调用点里 `code` 一律是**位置实参**，全仓 `code=` 的 16 处命中**全部**是 `status_code=`（记在第 6 节顶回第 3 处）。

**合计 14 个具名 code + 1 个 `http_*` 家族。**

| # | code | HTTP | 唯一住址（触发点） | 语义 | 横幅 tone |
|---|---|---|---|---|---|
| 1 | `unauthenticated` | 401 | `errors.py:57` 的 `_CODE_BY_STATUS[401]`；由 `deps.py:147`（缺 `X-Student-Id`）与 `deps.py:160`（缺 `X-Teacher-Staff-No` **或它全空白**）的 `HTTPException(401)` 折出来 | 没有带身份请求头 | error |
| 2 | `forbidden` | 403 | `errors.py:58`；**五个**触发点：`deps.py:204`（越权）/ `deps.py:209`（学号不在册）/ `deps.py:244`（工号不在册，`require_teacher`）/ `deps.py:291`（`require_teaches_section`）/ `deps.py:350`（`require_teaches_student`） | ⚠️ 「不是这个人」与「不在册」**刻意同形** | error |
| 3 | `not_found` | 404 | `errors.py:59`；`crud.py:348` 的 `_get_or_404` + `errors.py:118` 的 `NoResultFound` 处理器 | 查不到那一行 | error |
| 4 | `integrity_conflict` | 409 | `errors.py:60`；三个来源同一个 code：`errors.py:112` 的全局 `IntegrityError` 处理器 / `crud.py:697`（POST 撞自然键）/ `crud.py:763`（DELETE 被 `restrict` 挡住） | ⚠️ **计划写的 `conflict` 不存在**，逐字是 `integrity_conflict` | error |
| 5 | `unprocessable_value` | 422 | `errors.py:61` + `errors.py:103`（`ValueError` 处理器，消息**原话照发**） | 值在业务上不成立 | error |
| 6 | `request_validation_failed` | 422 | `errors.py:127-132`（Pydantic 的请求校验，`detail` 是带 `loc` 的清单） | ⚠️ `X-Student-Id: abc`（头存在但不是整数）是**这一档的 422**，不是 401 | error |
| 7 | `internal_error` | 500 | `errors.py:62` + `errors.py:153`（消息固定「服务器内部错误」，`detail` 恒为 `null`） | 没人接的异常；堆栈只进日志 | error |
| 8 | `alert_not_pending` | 409 | `alerts.py:240`，常量 `ALERT_NOT_PENDING` 在 `alerts.py:184` | 处置一条 `status != 'pending'` 的预警 | error |
| 9 | `not_recipient` | 403 | `alerts.py:444`，常量 `NOT_RECIPIENT` 在 `alerts.py:193` | 标已读时那条消息不是发给他的（**或它不存在** —— 两档刻意同形） | error |
| 10 | `no_weekly_report` | 404 | `dashboard.py:322`，常量 `NO_WEEKLY_REPORT` 在 `dashboard.py:170` | 那个班那一周没有周报（**只在周日生成**） | **info** |
| 11 | `rpe_not_opened` | 409 | `feedback.py:498`（教师读口令）与 `feedback.py:550`（学生交快评），**逐字同码**；常量在 `feedback.py:271` | 这节课还没发起课堂快评 | error |
| 12 | `invalid_rpe_token` | 403 | `feedback.py:559`，常量 `CODE_INVALID_RPE_TOKEN` 在 `feedback.py:278` | 口令不匹配（⚠️ 不做过期） | error |
| 13 | `no_active_prescription` | 404 | `prescription.py:234`（`_weekly_sheet_response`，学生侧与教师侧共用）与 `prescription.py:290`（`/prescriptions/current`）；常量在 `prescription.py:145` | 那一天没有生效的处方（**常态，不是故障**） | **info** |
| 14 | `outside_microcycle` | 404 | `prescription.py:242`，常量 `OUTSIDE_MICROCYCLE` 在 `prescription.py:160` | 有处方，但 `as_of` 落在微周期之外 | **info** |
| 15 | `http_<状态码>` | 任意 | `errors.py:142` 的 `_CODE_BY_STATUS.get(status, f"http_{status}")` | ⚠️ **开放的**家族。今天最常见 `http_405`：14 个只读资源不注册 POST/PATCH/DELETE | error |

⚠️ **`ApiErrorBanner.vue` 按上表的 `code` 分支，不按 `message` 字符串匹配**（`message` 只作为原文显示 —— `integrity_conflict` 在 `restrict` 那一档由后端点名了子表，比前端能写的任何一句都具体）。**有 `default` 分支**（`FALLBACK`），未知 code 显示 `code` + `message` 原文，**不静默**。

⚠️ 三档 tone 是 `info` 不是 `error`（`no_weekly_report` / `no_active_prescription` / `outside_microcycle`）：它们是「没有」不是「坏了」。用红色横幅渲染它们会教用户忽略红色横幅 —— 而下一次真正的 `forbidden` 会被一起忽略掉。`dashboard.py:164-166` 的注释逐字要求了这一点（「前端应把这一档渲染成『本周的周报周日晚上生成，先看大屏』，而不是一条错误横幅」）。

**与计划约束第 8 条那份 11 个清单的对账**：

| 计划写的 | 实测 |
|---|---|
| `unauthenticated` | ✅ 存在 |
| `unknown_teacher` | ❌ **不存在**（全仓 0 命中）→ 工号不在册是 **403 `forbidden`**（`deps.py:242-246`） |
| `unknown_student` | ❌ **不存在** → 学号不在册是 **403 `forbidden`**（`deps.py:207-211`） |
| `forbidden` | ✅ |
| `not_found` | ✅ |
| `invalid_rpe_token` | ✅ |
| `rpe_not_opened` | ✅ |
| `rpe_already_submitted` | ❌ **不存在** → 重复交快评撞 `uq_rpe_record_session_student`，由全局 `IntegrityError` 处理器折成 **409 `integrity_conflict`**（`feedback.py:540-545` 的 docstring 逐字写了「本函数不自己接」） |
| `no_active_prescription` | ✅ |
| `alert_not_pending` | ✅ |
| `conflict` | ❌ **不存在** → 逐字是 `integrity_conflict` |
| *(计划没写)* | ➕ 漏了 **8 个**：`not_recipient` `no_weekly_report` `outside_microcycle` `request_validation_failed` `unprocessable_value` `integrity_conflict` `internal_error` `http_*` |

### 4.6 其余实测口径（`endpoints.ts` / `types.ts` / `stores/identity.ts`）

- **路径与操作计数**：`/openapi.json` 实测 **64** 个 `/api/` 路径模板、**92** 个操作、**45** 个挂 `security`、**8** 个 `204`（全是 DELETE）—— 与计划的 64 / 92 / 45 逐字一致；`19 个特例` = 92 − 26（泛型 CRUD 写入）− 47（匿名 GET）✅。
- **securitySchemes**：`['X-Teacher-Staff-No', 'X-Student-Id']` —— 逐字就是那两个头。
- **分页信封是 4 个键**：实测 `GET /api/students?limit=200` 的顶层键集合是 `items,limit,offset,total`（⚠️ 计划约束第 9 条只写了 2 个）。`limit` / `offset` 是**服务端生效的那一份**，故算「下一页的 offset」要读它、不要读自己发出去的那份。实测 `limit` 的 openapi schema 是 `{maximum: 200, minimum: 1, default: 50}`、`offset` 是 `{minimum: 0, default: 0}`。
- **detail 路径的参数名**：实测 `/api/students/{student_id}` 与 `/api/fitness-test-batches/{fitness_test_batch_id}` 的 parameter name 逐字是 `student_id` / `fitness_test_batch_id`（**不是** `pk_value`，约束第 7 条 ✅；后者是 23 行里唯一的手工覆盖，自动推导对 `-es` 结尾的复数会多留一个 `e`）。
- **通知端点的确切路径**（计划 Task 2 标了「实现者要实测」）：实测**不存在** `GET /api/students/{id}/notifications`。只有 `GET /api/notifications`（匿名，泛型 list **没有筛选参数**）+ `GET /api/notifications/{id}` + `POST /api/notifications/{id}/read`（学生头）。⚠️ 故学生端的消息中心必须**客户端过滤** `recipient_kind === 'student' && recipient_id === 我`（`?recipient_id=1` 会被 FastAPI **静默忽略**）。
- **`HANDLE_ACTIONS` 三档读不到 openapi 的 enum**（约束第 17 条不成立，记在第 6 节顶回第 4 处）：实测 `components.schemas.AlertHandleCreate.properties.action` 逐字是 `{"type": "string", "title": "Action"}`，**没有 `enum`** —— 闸门是 `app/api/schemas/alerts.py` 的一个 `field_validator`，Pydantic 的 validator 不进 JSON Schema。全库 `components.schemas` 里 **唯一的** enum schema 是 `OverrideKind`（`weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`），因为它是 `str, Enum`。故 `types.ts` 字面写出三档 (`reduce_20pct` / `ignore` / `note`，⚠️ 值是**下划线**风格)，唯一所有者是后端 `schemas/alerts.py` 的 `HANDLE_ACTIONS`，Task 5 要对拍一次。
- **`stores/identity.ts`**：`DEMO_AS_OF = '2025-10-12'`；`localStorage` 键 `pe.identity.v1`（**带版本号**）；读回来时三层防御（`localStorage` 不可用 / 形状不是本版本 / `asOf` 不是 `YYYY-MM-DD`），一律**退回缺省值而不抛错**。

---

## ⑤ 壳与占位页

### 5.1 三条路由树的路径清单

`router/index.ts` 实测 **17 条路由记录** = **13 条挂组件** + **4 条 redirect**。

| # | path | name | → | `meta.title` | Task | surface | requires |
|---|---|---|---|---|---|---|---|
| 1 | `/` | — | redirect `/s/home` | — | — | paper | none |
| 2 | `/s` | — | redirect `/s/home` | 学生端 | Task 2 | paper | none |
| 3 | `/s/home` | `student-home` | component | 首页 | Task 2 | paper | student |
| 4 | `/s/weekly-sheet` | `student-weekly-sheet` | component | 本周训练单 | Task 2 | paper | student |
| 5 | `/s/check-in` | `student-check-in` | component | 每日打卡 | Task 2 | paper | student |
| 6 | `/s/rpe` | `student-rpe` | component | 课堂快评 | Task 2 | paper | student |
| 7 | `/s/mini-test` | `student-mini-test` | component | 二次小测 | Task 2 | paper | student |
| 8 | `/s/notifications` | `student-notifications` | component | 消息中心 | Task 2 | paper | student |
| 9 | `/t` | — | redirect `/t/dashboard` | 教师端 | Task 3 | paper | none |
| 10 | `/t/dashboard` | `teacher-dashboard` | component | 班级大屏 | Task 3 | ink | teacher |
| 11 | `/t/report` | `teacher-class-report` | component | 班级周报 | Task 3 | paper | teacher |
| 12 | `/t/alerts` | `teacher-alert-queue` | component | 预警队列 | Task 3 | paper | teacher |
| 13 | `/t/students/:studentId` | `teacher-student-detail` | component | 学生详情 | Task 3 | paper | teacher |
| 14 | `/admin` | `admin-index` | component | 资源目录 | Task 4 | paper | none |
| 15 | `/admin/:resource` | `admin-list` | component | 资源列表 | Task 4 | paper | none |
| 16 | `/admin/:resource/:id` | `admin-detail` | component | 资源详情 | Task 4 | paper | none |
| 17 | `/:pathMatch(.*)*` | — | redirect `/s/home` | — | — | paper | none |

⚠️ **本文件是 Task 2–4 的约束**：每条路由的 `meta.intent` 逐字写明了它将来打哪个端点、哪一档要小心（例如 `/t/students/:studentId` 那条写着「⚠️ 走 `/api/teacher/students/{id}/weekly-sheet`，不是学生侧那条，走错会 401」）。那三个 Task 的活是**逐条把 `component:` 换掉**，不是重写这棵树。

⚠️ `meta.surface` 只有 `/t/dashboard` 是 `ink`：大屏是投影场景（计划 Task 3 逐字「1440px、深底」），而教师端另外三页是在办公室的显示器上点着用的，深底会让它们的表格与表单全部要写第二套对比度。

⚠️ **不做路由守卫跳转**：本原型没有登录页（非目标第 1 条），故「要学生身份」那一档只在壳上**提示**（`App.vue` 的 `identityHint`），不拦截。

### 5.2 `IdentitySwitcher` 实测拉到的学生数与教师数

**走的是 Vite dev server 的代理**（`http://localhost:5173/api/…` → `127.0.0.1:8000`），即 `client.ts` + `endpoints.ts` + 代理三件事一起验的：

```
GET http://localhost:5173/api/health        → 200 {"status":"ok","tables":25,"students":60}
GET http://localhost:5173/api/students?limit=200
    → 200  total=60  items=60  envelope keys=['items', 'limit', 'offset', 'total']
      first: {"id":1,"student_no":"2025060001","name":"周晨阳",…}
      last : {"id":60,"student_no":"2025090003","name":"何冠宇",…}
GET http://localhost:5173/api/teachers?limit=200
    → 200  total=3  items=3
      [{"id":1,"staff_no":"T0001","name":"陈国华"},
       {"id":2,"staff_no":"T0002","name":"林慧敏"},
       {"id":3,"staff_no":"T0003","name":"赵志刚"}]
```

| | 实测 | 计划说的 |
|---|---|---|
| **学生** | **60**（`total=60`，`items` 也是 60，没被 `limit=200` 截断） | 60 ✅ |
| **教师** | **3**（`T0001` 陈国华 / `T0002` 林慧敏 / `T0003` 赵志刚） | 派单说「若干」→ 实测 **3** |

浏览器里渲染出来的那一行（Edge 无头 `--dump-dom` 的 DOM 原文）：

```html
<strong data-v-18601afa="" class="data">未选择身份</strong>
<span data-v-18601afa="" class="switcher__counts num"> 名单：60/60 学生 · 3/3 教师 </span>
```

⚠️ 这一行是**承重的**：`60/60` 与 `3/3` 分别是 `students.value.length` 与 `studentTotal.value`，故它同时证明了「请求通了」「拿到 60 条」「没有被 `limit` 截断」三件事。两个 `<!--v-if-->` 是「名单被截断」与「名单没拉到」那两段提示**没有**渲染 —— 即没有静默失败。

### 5.3 `as_of` 的缺省值

**`2025-10-12`**（`stores/identity.ts` 的 `DEMO_AS_OF`，唯一所有者是后端 `scripts/demo_bootstrap.py` 的同名常量）。切换器里它渲染成 `<input type="date">` 的值，旁边一句：`✓ 这就是**演示库的业务日**（学期第 6 周的周日）`；改成别的日期时那句变成 `⚠️ 演示库的业务日是 [2025-10-12]。用别的日期很可能查不到数据（周报只在周日生成、处方有微周期有效期）`，并且那个日期是一个**按钮**，点一下回去。

### 5.4 三个占位页与壳的渲染取证（Edge 无头 `--dump-dom`）

⚠️ 这一节是「页面真的渲染出来了」的证据。`npm run build` 只证明类型对、`curl /` 只证明 dev server 在发 HTML，两者都**不**证明 Vue 挂载成功。
本机没有浏览器自动化工具，故用 Edge 的无头模式（`msedge.exe --headless=new --virtual-time-budget=15000 --dump-dom <url>`）跑真渲染引擎，对每条路由 dump 出 DOM 再核标记：

| URL | DOM 字节 | 核到的标记 |
|---|---|---|
| `/s/home` | 50 304 | 刊名「体育闭环原型系统」✅ 副题「田径场年鉴」✅ `aria-label="身份切换器"` ✅ `as_of` = `2025-10-12` ✅ 匿名档那句「47 个 GET 一律匿名」✅ `STUDENT · H5 · 375PX` ✅ `Task 2` ✅ `.lane__num` / `.lane__rule` ✅ `StatBlock` 的 null → 「—」✅ `.surface-paper` ✅ 身份提示「这一页要…」✅ `<h2>` = 「首页」✅ |
| `/s/weekly-sheet` | 50 274 | `weekly-sheet` / `factor` / `reasons` / `Task 2` ✅ `<h2>` = 「本周训练单」✅ `<title>` = 「本周训练单 · 体育闭环原型系统」✅ |
| `/s/rpe` | 50 249 | 「口令」/「RPE」/ `Task 2` ✅ `<h2>` = 「课堂快评」✅ |
| `/t/dashboard` | 51 010 | `TEACHER · WALL · 1440PX` ✅ `Task 3` ✅ **`.surface-ink`** ✅ 「大屏口径」那段 ✅ `.lane--red` ✅ `no_weekly_report` 的口径 ✅ 身份提示（要教师身份）✅ |
| `/t/students/12` | 50 443 | `teacher/students` ✅ `Task 3` ✅ `<h2>` = 「学生详情」✅ |
| `/admin` | 49 530 | `ADMIN · CRUD · 23 RESOURCES` ✅ `Task 4` ✅ `<h2>` = 「资源目录」✅ |
| `/admin/students/7` | 49 757 | `resource = students` ✅ `id = 7` ✅ 「✓ 目录里有这一行」✅ 只读理由（spec §4.4 那句「体育专家维护的知识资产」）✅ |
| `/admin/not-a-resource` | 49 809 | 「目录里**没有**这一行」✅ —— **不白屏** |

⚠️ **一处诚实的缺口**：那 60 个 `<option>`（学生下拉框的选项）**没有**被 dump 到 —— 因为初始状态 `role === null`（匿名档），`v-if="role === 'student'"` 的那个 `<select>` 根本不渲染，这是**设计如此**（不是 bug）。要 dump 到它需要一次点击，而无头 `--dump-dom` 不能交互。它迭代的是**同一个** `students.value` 数组（就是渲染出 `60/60` 的那一个），故风险很低；**Task 5 第 5 步的浏览器取证要把它点一遍**（记在第 6 节待清扫）。

### 5.5 壳的四个常驻位

`App.vue` 只做四件事：① 报头（刊名 + 三棵树的导航，导航项来自 `router/index.ts` 导出的 `TREES`）；② **`IdentitySwitcher` 的常驻位**（每条路由上都在场）；③ **`ApiErrorBanner` 的常驻位**（渲染在报头之下、`<main>` 之上，于是错误出现/消失不会把内容顶下去又顶回来）；④ `<RouterView>` + 一个 colophon 页脚（把当前 `as_of` 与身份摘要常驻显示出来，投屏时一眼能看到「现在是谁、哪一天」）。

⚠️ 横幅的状态是**模块级 `shallowRef`**，不是 Pinia store，出口是 `useApiError()`（与组件同一个 SFC，单一所有者）。理由：计划第 3 节逐字写了 Pinia「只存三样：当前身份、当前学期/`as_of`、服务端缓存」，一条转瞬即逝的错误提示三样都不是（不持久化、不跨页共享、没有派生状态）。`main.ts` 的 `app.config.errorHandler` 把没人 catch 的 `ApiError` 送进去，⚠️ 但**只送 `ApiError`**：渲染期的一般异常（`TypeError` 之类）进横幅会把「代码有 bug」显示成「后端出错了」，那是两种完全不同的下一步；它也不吞异常，仍然 `console.error`。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者

### 6.1 ⚠️⚠️ 顶回控制者：**5 处**（其中 2 处 Critical）

#### 顶回 1（**Critical**）—— 计划约束第 5 条「list 项的键集合」说反了

**计划逐字**：「list 项的键集合 = 该资源 `schemas.read` 的字段 减去 `list_exclude` —— 这个差集**今天只有 `class-sessions` 一个资源非空**（`list_exclude=("rpe_token",)`）」。

**实测（23/23 逐个资源打了 `GET /api/<资源>?limit=1`，比 `items[0]` 的键集合）**：

- **list 键集合 ≠ `*Read` 字段集的资源是 8 个，差 19 个列**（`interest-surveys` 2 / `derived-metrics` 3 / `stratification-results` 1 / `exercises` 1 / `prescriptions` 5 / `mini-tests` 1 / `alerts` 1 / `weekly-class-reports` 5）；
- 再加上 `class-sessions`（显式 `list_exclude=("rpe_token",)` 排掉的是**表列**，而那一列早已不在 `ClassSessionRead` 上，故它对 `*Read` 的差集**为空**）→ **相对表列集少列的资源是 9 个、20 个列**；
- ⚠️ 那 **8 张表 / 19 个 `JsonText` 列**与后端 `crud.py:243-245` 的 docstring 逐字吻合（「实测全库 21 个 `JsonText` 列，其中 19 个落在这 23 个资源上，分布在 8 张表：`prescription` 与 `weekly_class_report` 各 5 个、`derived_metrics` 3 个、`interest_survey` 2 个，`stratification_result` / `exercise` / `mini_test` / `alert` 各 1 个」）。

而 `class-sessions` 恰恰是**唯一**一个 list 键集合与 `*Read` 字段集**逐字相等**的资源（两边都是 6 个键）—— **与计划说的那一句正好相反**。

**根因**（后端 `crud.py:582-585` 的原文）：
```python
excluded = (tuple(list_exclude) if list_exclude is not None else _json_text_columns(model))
```
`list_exclude` 是**覆盖**自动探测，不是**追加**。没显式声明的 22 个资源排掉的是`_json_text_columns(model)`（判据 `isinstance(column.type, JsonText)`，`crud.py:237-259`；它的 docstring 逐字写了「全库 21 个 `JsonText` 列，19 个落在这 23 个资源上，分布在 8 张表」—— 与我实测的 19 个逐字吻合）。
而 `class-sessions` 显式声明了 `("rpe_token",)`，覆盖掉自动探测出来的**空元组**（`class_session` 表一个 `JsonText` 列都没有，`catalog.py:427` 的注释逐字交代了这件事），同时 `rpe_token` 早在收尾小修波里就从 `ClassSessionRead` 上摘掉了 —— 故它的差集为空。

**失效形态（若照计划写）**：8 个 list 类型会声明一批 API 根本不返回的字段，于是 `row.progress_board` 在编译期是 `unknown`、在运行时是 `undefined`，管理台的列表页会渲染出一片空白或 `NaN`。⚠️ 而它**静默**：类型对、请求 200、只是那一格没有值 —— 正是约束第 10 条（「不知道」不得显示成「0」）最容易被违反的地方。

**处置**：`types.ts` 的 23 行按**生效的** excluded 写，`OmitStrict` 逐个钉住；23/23 的对称差实测为空（第 4.3 节）。`catalog/resources.ts` 因此有**两个**字段：`listExclude`（生效的）与 `listExcludeDeclared`（显式声明的），于是 Task 4 的管理台能说清「这一列为什么在列表里没有」。

⚠️ **顺带抓到一处派单里的连带错误**：派单第 4 节说「今天只有 `class-sessions` 有 `list_exclude`（排 `rpe_token`），其余 22 个的 list 键集合 == `*Read` 的字段集」。前半句对（实测 `catalog.RESOURCES` 里只有那一行有 `list_exclude` 键非空），**后半句错**（8 个不相等）。

#### 顶回 2（**Critical**）—— `openapi-typescript` v7 的取值路径与派单写的不符

**派单逐字**：「v7 是 `paths["/x"]["get"]["responses"][200]["content"]["application/json"]`」。

**实测 v7.13.0 的产物**：`interface paths` 里每个 method **只有一行引用**，响应体**内联在 `operations` 那一侧**：
```ts
"/api/students": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get: operations["list_rows_api_students_get"];   // ← 只有这一行
    post: operations["create_row_api_students_post"];
}
```
故要拿响应体必须走 `operations['<operationId>']['responses'][200]['content']['application/json']`。`operationId` 是 **FastAPI 自动生成的**（`list_rows_api_<资源>_get` / `read_one_api_<资源>__<pk>__get` / `create_row_api_<资源>_post` / …），不是我们起的名字。

**失效形态**：Task 2–4 若照派单那条路径写，`paths['/api/x']['get']['responses']` 在类型上是 `never`/不存在，**每一个**取值点都编译报错 —— 这是响的那一档，但会浪费掉一轮。⚠️ 更重要的是：本 Task **没有**让 `endpoints.ts` 走 `paths[…]` 取值，而是走 `components['schemas']['XRead']`（detail 端点）+ `types.ts` 的手写 list 类型（list 端点），**两条都不依赖 `paths` 的形状**，故 v7→v8 的升级代价被隔离在了 0。

**给 Task 2–4 的口径**（写进第 4.1 节了）：模型走 `components['schemas'][…]`；操作走 `operations['<operationId>']`；`paths` 只用来看「这个路径上有哪些 method」。

#### 顶回 3 —— 派单第 5 节给的取证方法（`Grep` `code=`）抓不到错误 code

**派单逐字**：「`Grep` 后端 `app/api/` 下全部 `code=` 或 `"code":` 的命中」。

**实测**：`Grep 'code='` 在 `backend/app` 下命中 **16** 处，**全部**是 `status_code=`；`Grep '"code":\s*"[a-z_]+"'` 命中 **0** 处。原因：`error_response(status_code, code, message, detail)` 的 `code` 一律是**第 2 个位置实参**，从来不用关键字传；而唯一的 `"code":` 字面量在 `errors.py:84` 那一行 `content={"error": {"code": code, …}}` 里，`code` 是个**变量名**不是字面量。

**处置**：改用 AST（`ast.walk` 找 `error_response` 的 `Call`，解第 2 个位置实参，名字回模块级常量表取），命中 **15** 个调用点、**9** 个具名 code；再折 `_CODE_BY_STATUS` 的 6 个与 `http_*` 家族 → **14 + 1**（第 4.5 节）。⚠️ 这也符合硬规矩 #89（运行时/AST 口径，不用正则数源码）。

#### 顶回 4 —— 计划约束第 17 条「从 `/openapi.json` 读枚举」做不到

**计划逐字**：「`action` ∈ `ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`… ⚠️ 前端要从 `/openapi.json` 读枚举，不要抄字符串。」

**实测**：`components.schemas.AlertHandleCreate.properties.action` 逐字是 `{"type": "string", "title": "Action"}` —— **没有 `enum`**。那三档的闸门是 `app/api/schemas/alerts.py` 的一个 `field_validator`，而 Pydantic 的 validator **不进 JSON Schema**。全库 `components.schemas`（**86** 个）里唯一的 enum schema 是 `OverrideKind`（它是 `str, Enum`，故生成出来是字面量联合）—— 两档不同源。

**处置**：`types.ts` 字面写出 `HANDLE_ACTIONS = { reduce: 'reduce_20pct', ignore: 'ignore', note: 'note' }`，注释里点名唯一所有者是后端 `schemas/alerts.py:79` 的 `HANDLE_ACTIONS`，并留一条 **Task 5 要对拍**的守卫（`smoke.mjs` 从后端 import 那个元组比一次）。⚠️ 值是**下划线**风格（`reduce_20pct`），与 URL 的连字符惯例相反 —— 抄的时候最容易错这一格。

#### 顶回 5 —— `catalog/resources.ts` 的 `RESOURCES` 类型标注是一句**编译不过的谎**

这一处不是计划的错，是**本轮既有产物**（Task 1 的一次未完成运行留下的）的错，由 `vue-tsc -b` 查出来，故记在这里以免下一个人以为是新引入的。

原文是 `export const RESOURCES: readonly ResourceEntry[] = […]`，而 `ResourceEntry<R extends ResourceName = ResourceName>` 的 `displayFields` 是 `readonly (keyof ListItemByResource[R] & string)[]`。`ListItemByResource[ResourceName]` 是 23 个 list 项类型的**并集**，而 `keyof` 一个并集得到的是**交集** —— 实测塌成 `"id"`（23 个资源唯一共有的键）。于是 22 行逐个报 `TS2322: Type '"student_id"' is not assignable to type '"id"'`（**17 条**编译错误）。

**处置**：拆出 `ResourceEntryBase`（`displayFields: readonly string[]`，字段说明全在这里）让数组用它；`ResourceEntry<R>` 改为 `extends ResourceEntryBase` 只负责把三个字段收窄，仍是 `defineResource<R>` 的形参类型 —— **逐行的类型安全一点没丢**（`displayFields` 挑了一个 list 端点不返回的列，仍然是 `npm run build` 的红），丢掉的只是「数组这一层的 `R`」，而一个数组本来就必须是同质的。`resourceByName()` 的返回类型同步改成 `ResourceEntryBase | undefined`。

⚠️ **同族的第二处**（也由 `vue-tsc` 查出，**21 条**）：`types.ts` 的 `PageQuery` 原本是 `interface`，而 `client.ts` 的 `ApiRequestInit.query` 是 `Record<string, QueryValue>`。TypeScript **只给「对象字面量类型」隐式索引签名，不给 `interface`**（interface 是开放的，declaration merging 可以随时加成员），故 23 个 list 函数逐个报 `Index signature for type 'string' is missing in type 'PageQuery'`。改成 `type PageQuery = { … }` 即绿。⚠️ 两处的教训都写进了源码注释，因为它们是 **Task 2–4 会再踩一次**的形状（新页面一定会定义自己的查询袋类型）。

### 6.2 逐条核过的决定（**没有**顶回的那些）

派单第 7 节点名了三处「最可能顶回」，我逐个在真实产物上核过：

| 决定 | 核法 | 结论 |
|---|---|---|
| **纯 CSS 而不是 Tailwind/UnoCSS** | 数了一下 bespoke 的量：`tokens.css` **110** 个令牌、`lane.css` 174 行里 4 个 keyframes + 母题的两个伪元素 + 6 个语义/底色变体、`base.css` 417 行里两层纹理（内联 SVG `feTurbulence` + `repeating-radial-gradient` 的跑道弧）| **不顶回** ✅ 这些东西在原子化 CSS 里要么变成 一堆 `arbitrary value`（`[background-image:url(data:image/svg+xml,…)]`），要么仍然要一个 `@layer components`。而 `tokens.css` 已经把原子化想要的好处拿到了 |
| **手写 SVG 而不是 ECharts** | Task 1 **不做图**（4 个 chart 组件是 Task 2/3 的活）；只核了「数据形状简不简单」：`layer_distribution` / `rpe_summary` / `checkin_rate_by_layer` / `progress_board` 四个都是后端算好的扁平 JSON | **不顶回（今天）** ⚠️ 但我**没有实测过渲染代价**，故这一条我只能核到「数据形状够简单」。若 Task 3 发现 `progress_board` 需要排序 + 分组 + 双向条形，请在**那个 Task** 里顶回，不要等到写了一半 |
| **23 个手写 list 类型的必要性** | 在**真实产物**上复核：`schema.d.ts` 里 `operations` 内 `[key: string]: unknown;` 逐字 **24** 次（第 4.2 节） | **不顶回** ✅ codegen 的产物对这 24 个**确实**一点用没有（`res.items[0].name` 一次都不类型安全）。终审的实测在真产物上成立 |
| 计划约束第 8 条的错误 code 清单 | AST 实测（第 4.5 节） | **顶回**（4 个不存在、漏 8 个）→ 顶回 3 |
| 计划约束第 9 条的分页信封「2 个键」 | 实测顶层键集合 | **半顶回**：是 **4 个键**（`items,limit,offset,total`）。已写进 `types.ts` 的 `Page<T>` 与第 4.6 节。⚠️ 这一条我没单列成一处顶回，因为它不改任何行为，只是计划少写了两个键 |
| 计划第 3 节末尾「`frontend/` 在 `.gitignore` 里被忽略了」 | `Get-Content .gitignore \| Select-String frontend` → **只命中一行 `frontend/dist/`**；`git check-ignore -v frontend/package.json` → **无输出、exit 1** | **确认控制者的更正**：计划那一句是错的，Task 1 第 1 步多余，已跳过。仍按派单要求做了核实动作 + 显式写了 `frontend/.gitignore` |
| 计划自审第 4 条「`19 个特例` 是 fix 波 2 之后的数，实现者开工时要复核」 | 92 操作 − 26 泛型写入 − 47 匿名 GET = **19** | **复核通过** ✅ |
| 计划的 8 个运行时数字（23 资源 / 14 只读 / 9 可写 / 26 CRUD 写入 / 19 特例 / 45 挂 security / 92 操作 / 24 未定型响应） | 全部从 `/openapi.json` 与 `catalog.RESOURCES` 实测 | **8/8 逐字吻合** ✅（含 `on_delete`：restrict 12 / forbid 10 / cascade 1；`securitySchemes` 恰好是那两个头） |

### 6.3 ⚠️⚠️ 关切（**Critical**，与本 Task 无关，但本轮当场抓到并已处置）

**IDE 又把一份陈旧且截断的缓存写回了磁盘。**

本轮开工时 `git status --short` 只有 `?? frontend/`（工作树干净，与派单一致）。而在本 Task 中途的某一刻，

```
 M .superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-2-report.md
   1 file changed, 1 insertion(+), 687 deletions(-)
   HEAD 版本 83 042 B  →  磁盘上 31 506 B   （净丢 51 536 B）
```

**证据它是陈旧缓冲区、不是有意的编辑**：被删掉的内容里**逐字包含**这一段 ——

> 【修复轮 2 补注】本节（§F.1–§F.6）此前只存在于编辑器未落盘的缓冲区中，磁盘上的报告文件只有 §1–§7；修复轮 2 已将其原样补回磁盘。

即：**修复轮 2 补回去的那 687 行，本轮又被写回成修复轮 2 之前的样子**。新增的那 1 行是一个行尾空行。本 Task 从未读写过这个文件。

**处置**：① 先把被截断的那一份备份到 `%TEMP%\pe_fe_stale_plan01_task2_report.md`（31 506 B，什么都没丢）；② `git restore -- <那一个文件>`（**单文件**，不是 `git restore .`）还原到 HEAD；③ 复核还原后大小 = **83 042 B** = HEAD，`git status --short` 回到只有 `?? frontend/`。

⚠️ **请控制者注意**：这与派单第 6 节点名的那个失效形态逐字同一个（「IDE 曾把陈旧且截断的缓存写回磁盘，Plan 02 永久丢了约 107 KB」）。**它这次不是历史事故，是在本轮会话里实时发生的**，而且目标换成了 Plan 01 的报告。两条建议：① 本轮之后**立刻复核一次** `git status --short` 与 `.superpowers/**/*.md` 的字节数，别等到下一个 Task 开工；② 本报告本身就是用 python 一次性写盘、不经编辑器工具的（派单第 6 节的要求），但**它落盘之后仍然可能被同一个机制改回去** —— 建议控制者收到本报告后立刻 `git add` + commit，把它固化进 HEAD。

### 6.4 待清扫（**5 条**）

| # | 条 | 归谁 |
|---|---|---|
| 1 | **现存的 `backend/pe_demo.db` 与计划约束第 22 条的演示库清单不符**：实测 `notifications` 只有 **1** 条（计划说 **19** 条 = 电子勋章 13 + 补练提醒 6），而且那 1 条是 `title="本周训练量已减 20%"` / `is_read=true` / `created_at=2026-10-10T16:43:12` / `alert_id=null` / `prescription_id=null` —— 它是一次**人工处置预警**留下的痕迹，不是批处理产物。其余 10 项逐字吻合（2 学期 / 60 学生 / 5 教学班 / 120 选课 / 60 处方 / 8 课次 / 240 快评 / 840 打卡 / 180 小测 / 11 预警 / 5 周报）。⚠️ 另：`exercises` 与 `prescription-templates` 两张表是**空的**（`total=0`）—— 计划没把它们列进演示库清单，但 Task 4 的管理台要读它们、第 4.3 节那两个「无法实测」也卡在这里。**Task 5 开工前请重跑 `backend\scripts\demo.ps1` 灌一份干净的库**（它自带两道禁区守卫，写的是 `pe_demo.db` 不是禁区）。 | Task 5 |
| 2 | **`IdentitySwitcher` 的学生下拉框（60 个 `<option>`）没有被渲染取证**：初始是匿名档，`<select>` 不渲染；无头 `--dump-dom` 不能交互。**Task 5 第 5 步的浏览器取证要点一遍**：选「学生」→ 下拉框出现 60 项 → 选一个 → `client.ts` 开始带 `X-Student-Id` → 学生端页面能读到数据。 | Task 5 |
| 3 | **`exercises` / `prescription-templates` 两个 list 类型的键集合是推出来的、不是实测的**（演示库里那两张表是空的）。`exercises` 排 `targets` 由 `_json_text_columns` 的口径 + `catalog/resources.ts` 双重确认，但**没有响应体原文**。灌过参考数据之后补一次实测。 | Task 5 |
| 4 | **`smoke` 这个 npm script 还不存在**（`package.json` 只有 dev/build/preview/gen:api 四个），`frontend/scripts/smoke.mjs` 也没有 —— 两者都是 Task 5 的活，派单也这么划的。⚠️ 但 `package.json` 的 `scripts` 里**没有留占位**，Task 5 要自己加一行。 | Task 5 |
| 5 | **`src/components/charts/` 目录还不存在**（File Structure 里列了 4 个手写 SVG 图表组件）。Task 1 的派单把它划给了 Task 2/3（`RpeTrend` 在 Task 2 的 Files 里、另 3 个在 Task 3 的 Files 里），故本 Task **刻意没建**空目录（git 不跟踪空目录）。 | Task 2/3 |

### 6.5 没按派单做的地方（**4 处**，逐个说明理由）

| # | 派单说的 | 我做的 | 理由 |
|---|---|---|---|
| 1 | 「**Create**：`frontend/` 下的全部」 | ⚠️ **`frontend/` 今天已经存在**，而且里面已有 Task 1 第 3–8 步的绝大部分产物（未入库、`git status` 显示 `?? frontend/`）：`package.json` / `vite.config.ts` / `tsconfig*` / `index.html` / `tokens.css` / `base.css` / `lane.css` / `LaneDivider.vue` / `StatBlock.vue` / `StampFeedback.vue` / `generated/schema.d.ts` / `client.ts` / `types.ts` / `endpoints.ts` / `identity.ts` / `catalog/resources.ts`。**但它是半成品且当时编译不过**：`main.ts` 还 import 一个不存在的 `./style.css`、`App.vue` 还 import 一个不存在的 `./components/HelloWorld.vue`，`router/` `views/` `IdentitySwitcher.vue` `ApiErrorBanner.vue` **全部不存在**。| **派单第 2 节「`frontend/` 目录今天不存在（你要建它）」这一条前提是错的。** 我逐个读了既有产物、核实了它们引用的每一条后端事实（错误 code 清单、24 个未定型响应、9 个资源的 list 差集、23 行目录），**结论是质量达标且与我的独立实测逐字一致**，故**保留并补完**而不是推倒重建 —— 重建会丢掉约 130 KB 已核实过的注释与实测取证，而收益为 0。本轮**新写**的是：`.gitignore`（重写）、`main.ts`、`App.vue`、`router/index.ts`、`IdentitySwitcher.vue`、`ApiErrorBanner.vue`、三个占位页；**修**的是 `catalog/resources.ts`（顶回 5）、`types.ts` 的 `PageQuery`（顶回 5 的同族）。⚠️ 这一处**请控制者复核**：若你要求「从零重建」，请明说，我可以删掉重来。 |
| 2 | 「`npm create vite@latest frontend -- --template vue-ts`」 | 没跑（既有产物已经是那个模板的产物，且模板残留 `HelloWorld.vue` / `style.css` / `public/vite.svg` / `src/assets/` 已被清干净 —— 实测这四个路径全部 `Test-Path` 为 `False`） | 再跑一次会覆盖掉已有的 8 个配置文件 |
| 3 | 「`frontend/scripts/gen-api.mjs`（若你不用 `openapi-typescript` 的 CLI 直调）」 | **没建**这个文件 | 我们**就是**直调 CLI（`npm run gen:api` 那一行），派单的条件不成立。给一个一行命令包一层 `.mjs` 是纯增熵 |
| 4 | 「建议 3–4 个 commit」 | 做了 **4** 个 frontend 的 commit（与建议一致），**外加打算再做 1 个 `docs(sdd)` commit 装本报告** | 报告的 sha 无法写进报告自己，故它是第 5 个。⚠️ 若控制者不想让报告入库，请把那个 commit 撤掉（前 4 个 commit 只含 `frontend/` 下的 28 个文件，与报告无关） |

⚠️ **`index.html` 多请求了 `Barlow Condensed` 的 500 一档**（计划只写 600/700/800）—— 这一处是既有产物的决定，我核实后**保留**：`.caps` 那一类 11px 的全大写拉丁小标题在 600 上会糊，500 才读得清。记在这里而不单列成一处顶回，因为它不影响任何口径。

---

## ⑦ 最终验收

| # | 判据 | 结果 | 证据 |
|---|---|---|---|
| 1 | `npm run dev` 起得起 | ✅ | `VITE v8.3.4 ready in 340 ms` → `Local: http://localhost:5173/`；`GET /` 回 1 468 B 的 HTML，含 `<div id="app">`、`fonts.gstatic.com` 的 preconnect、`/src/main.ts` 的 module script |
| 2 | 代理通（`/api` → `127.0.0.1:8000`） | ✅ | 走 `localhost:5173` 打 `/api/health` → 200 `{"status":"ok","tables":25,"students":60}`；响应头里 `server: uvicorn`、`vary: Origin` |
| 3 | 身份切换器拉到真实名单 | ✅ | **60 学生 / 3 教师**，DOM 里渲染出 `名单：60/60 学生 · 3/3 教师`（第 5.2 节） |
| 4 | `npm run build` 退出码 **0** 且无 TS 报错 | ✅ | `vue-tsc -b && vite build` → `✓ 63 modules transformed`、`✓ built in 203ms`、`BUILD_EXIT=0`；产物 1.89 kB / 26.78 kB / 135.96 kB（gzip 1.20 / 5.31 / 51.16） |
| 5 | `npm run gen:api` 可重跑且产物稳定 | ✅ | 重跑前后 SHA256 逐字相同 `A40DD5EC…9022F3`、338 756 B 相同 |
| 6 | 三条路由树都能渲染 | ✅ | Edge 无头 dump 了 **8** 条 URL，全部渲染出壳 + 身份切换器 + 对应占位页；`/t/dashboard` 拿到 `.surface-ink`；`/admin/not-a-resource` 显示「目录里没有这一行」而**不白屏**（第 5.4 节） |
| 7 | **`Test-Path backend\pe.db` 是 `False`** | ✅ | `pe.db exists (should be False): **False**` |
| 8 | `backend/data/seed/` 仍 **0** 文件 | ✅ | `data/seed file count (should be 0): **0**` |
| 9 | `backend/data/**` 一个字节没动 | ✅ | `git status --short` 里 `backend/` 下**没有任何条目**；本 Task 从未写入 `backend/`（只读它、只 `import` 它做实测）；也**从未跑过** `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` |
| 10 | `git status --short` 里没有 `node_modules` | ✅ | `git add --dry-run frontend` 列出 **28** 个文件，逐个是源码/配置；`git status --short` 收尾为 `(clean)` |
| 11 | `src/api/generated/schema.d.ts` **入库了** | ✅ | 那 28 个文件里逐字有 `add 'frontend/src/api/generated/schema.d.ts'`；`frontend/.gitignore` 用两条否定式规则钉住它 |
| 12 | 没改 `backend/` 下的任何生产代码 | ✅ | 4 个 commit 的 `create mode` 清单里**只有** `frontend/` 下的路径；探针脚本一律放 `%TEMP%`（后端的架构守卫会 AST 解析工作树里全部 `.py`，含未入库的） |
| 13 | 没 push、没切分支、没碰 main | ✅ | 全程在 `feature/plan-04-frontend`；`git log --oneline` 的 HEAD 从 `ba87156` 前进到 `14c7eff`，`ba87156` 仍在链上 |

### commit sha

```
14c7eff feat(frontend): 壳与三条路由树 —— 身份切换器代替登录页、错误横幅按 code 分支、三个占位页
0b27e02 feat(frontend): 类型化 API 层 —— codegen 产物 + 23 个手写 list 类型 + 四件事的 fetch 封装
2a9c548 feat(frontend): 设计系统《田径场年鉴》—— 令牌唯一住址 + 分道线母题 + 三个原子组件
eab21c8 build(frontend): 工程骨架 —— Vite 8.3 / Vue 3.5 / TS 5.9，/api 代理到 127.0.0.1:8000
ba87156 docs: 实施计划 04 —— Vue3 前端（22 条对齐约束 + 《田径场年鉴》美学方向 + 5 个 Task）
```

| sha | 一句话 | 文件数 | 行数 |
|---|---|---|---|
| `eab21c8` | 工程骨架 —— Vite 8.3 / Vue 3.5 / TS 5.9，`/api` 代理到 `127.0.0.1:8000` | 8 | +1 879 |
| `2a9c548` | 设计系统《田径场年鉴》—— 令牌唯一住址 + 分道线母题 + 三个原子组件 | 6 | +1 318 |
| `0b27e02` | 类型化 API 层 —— codegen 产物 + 23 个手写 list 类型 + 四件事的 fetch 封装 | 6 | +10 181 |
| `14c7eff` | 壳与三条路由树 —— 身份切换器代替登录页、错误横幅按 code 分支、三个占位页 | 8 | +1 785 |

合计 **28 个文件 / +15 163 行**（其中 `generated/schema.d.ts` 一个文件占 7 971 行）。

### 28 个入库文件逐个

```
eab21c8 build(frontend): 工程骨架 —— Vite 8.3 / Vue 3.5 / TS 5.9，/api 代理到 127.0.0.1:8000
frontend/.gitignore
frontend/index.html
frontend/package-lock.json
frontend/package.json
frontend/tsconfig.app.json
frontend/tsconfig.json
frontend/tsconfig.node.json
frontend/vite.config.ts
2a9c548 feat(frontend): 设计系统《田径场年鉴》—— 令牌唯一住址 + 分道线母题 + 三个原子组件
frontend/src/components/LaneDivider.vue
frontend/src/components/StampFeedback.vue
frontend/src/components/StatBlock.vue
frontend/src/styles/base.css
frontend/src/styles/lane.css
frontend/src/styles/tokens.css
0b27e02 feat(frontend): 类型化 API 层 —— codegen 产物 + 23 个手写 list 类型 + 四件事的 fetch 封装
frontend/src/api/client.ts
frontend/src/api/endpoints.ts
frontend/src/api/generated/schema.d.ts
frontend/src/api/types.ts
frontend/src/catalog/resources.ts
frontend/src/stores/identity.ts
14c7eff feat(frontend): 壳与三条路由树 —— 身份切换器代替登录页、错误横幅按 code 分支、三个占位页
frontend/src/App.vue
frontend/src/components/ApiErrorBanner.vue
frontend/src/components/IdentitySwitcher.vue
frontend/src/main.ts
frontend/src/router/index.ts
frontend/src/views/admin/AdminPlaceholder.vue
frontend/src/views/student/StudentPlaceholder.vue
frontend/src/views/teacher/TeacherPlaceholder.vue
```

### 各文件字节数

| 文件 | 字节 |
|---|---|
| `frontend/.gitignore` | 1,802 |
| `frontend/index.html` | 1,800 |
| `frontend/package-lock.json` | 57,876 |
| `frontend/package.json` | 802 |
| `frontend/src/App.vue` | 7,675 |
| `frontend/src/api/client.ts` | 19,183 |
| `frontend/src/api/endpoints.ts` | 38,806 |
| `frontend/src/api/generated/schema.d.ts` | 338,756 |
| `frontend/src/api/types.ts` | 21,680 |
| `frontend/src/catalog/resources.ts` | 21,510 |
| `frontend/src/components/ApiErrorBanner.vue` | 15,662 |
| `frontend/src/components/IdentitySwitcher.vue` | 14,699 |
| `frontend/src/components/LaneDivider.vue` | 2,338 |
| `frontend/src/components/StampFeedback.vue` | 6,719 |
| `frontend/src/components/StatBlock.vue` | 7,230 |
| `frontend/src/main.ts` | 1,576 |
| `frontend/src/router/index.ts` | 9,394 |
| `frontend/src/stores/identity.ts` | 8,056 |
| `frontend/src/styles/base.css` | 10,809 |
| `frontend/src/styles/lane.css` | 5,917 |
| `frontend/src/styles/tokens.css` | 9,788 |
| `frontend/src/views/admin/AdminPlaceholder.vue` | 4,369 |
| `frontend/src/views/student/StudentPlaceholder.vue` | 3,445 |
| `frontend/src/views/teacher/TeacherPlaceholder.vue` | 4,819 |
| `frontend/tsconfig.app.json` | 430 |
| `frontend/tsconfig.json` | 119 |
| `frontend/tsconfig.node.json` | 558 |
| `frontend/vite.config.ts` | 1,481 |

---

## 附：本轮用过的探针（一律放 `%TEMP%`，**没有进仓库**）

| 文件 | 干什么 |
|---|---|
| `pe_fe_probe_codes.py` | AST 出 `backend/app/**/*.py` 里全部 `error_response(…)` 的 `code` 实参 + `_CODE_BY_STATUS` + `HTTPException` 的状态码分布 |
| `pe_fe_probe_api.py` | `/api/health`、`/openapi.json` 的路径/操作/security/未定型响应计数、`catalog.RESOURCES` 的 23 行、23 个 list 端点的 `items[0]` 键集合、学生与教师名单 |
| `pe_fe_probe_catalog.py` | `catalog.RESOURCES` 每行的 `writable` / `on_delete` / `list_exclude` / `natural_key` / `pk_alias` + 每个 `*Read` 的 `model_fields` |
| `pe_fe_probe_diff.py` | 上面两份的**对称差**：实测 list 键集合 vs（Read 字段 − 生效 excluded） |
| `pe_fe_probe_openapi.py` | `AlertHandleCreate.action` 有没有 enum、全库有哪些 enum schema、detail 路径的 parameter name、`Page` 的 query schema、8 个 `204` 的清单 |
| `pe_fe_probe_proxy.py` | 走 **Vite dev server 的代理**打 `/api/health` `/api/students` `/api/teachers`，并核 `GET /` 回的 HTML |
| `pe_fe_probe_dom.py` / `pe_fe_probe_dom2.py` | Edge 无头 `--dump-dom` 渲染 8 条 URL，逐个核标记（含把 DOM 写成 utf-8 文件，避开 PowerShell 重定向的 UTF-16LE） |
| `pe_fe_probe_counts.py` | `tokens.css` 的自定义属性计数、`router/index.ts` 的路由计数、各文件字节数 |
| `pe_fe_commit.py` | 4 个 commit：逐个文件 `git add` + UTF-8 无 BOM 的消息文件 + `git commit -F` |

⚠️ 这些**都不在仓库里**（`git status --short` 收尾为 clean，`git ls-tree -r HEAD frontend` 只有 28 个文件），**且跑完已从 `%TEMP%` 删掉**（派单第 6 节的要求；共删 27 项，含 `pe_fe_edge_profile/` 那个 Edge 无头的临时用户目录）。⚠️ **唯一保留的一份**是 `%TEMP%\pe_fe_stale_plan01_task2_report.md`（31 506 B）—— 那是第 6.3 节里 Plan 01 报告被 IDE 截断后的那一份，留给控制者取证用，**不是探针**。后端的架构守卫会 AST 解析工作树里全部 `.py`（含未入库的），故探针一律住在 `%TEMP%`。

