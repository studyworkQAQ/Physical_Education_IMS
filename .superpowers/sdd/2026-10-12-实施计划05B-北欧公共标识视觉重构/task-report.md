# Plan 05B 实现者报告 —— 视觉重构：北欧公共标识

> 分支 `feature/plan-05b-nordic` · 起点 `4cee7f2` · 6 个实现 commit + 本报告 commit
> 实现者按派单 §5 的 6 个 Task 顺序做完，**没有停在中间态**。

---

## 1. 环境与基线复现

开工第一拍（硬规矩 #73，逐字实测）：

| 项 | 值 |
|---|---|
| Node | v24.19.0 |
| npm | 11.17.0 |
| FastAPI / SQLAlchemy | 0.141.1 / 2.1.3（Python 3.11.1，无 venv；**无** `ImportError: DLL load failed`） |
| 分支 / HEAD 起点 | `feature/plan-05b-nordic` @ `4cee7f2`，工作树干净 |
| 服务 | 后端 `127.0.0.1:8000`（本波重灌过两次演示库，见 §7 待清扫 0）、前端 `::1:5173` vite dev |

基线复现：

| 基线项 | 派单给的值 | 本波实测 |
|---|---|---|
| 后端 pytest（带 `--cov`） | 1332 passed + 1 skipped（=1333 口径） | **1332 passed, 1 skipped**（281 s），`app/domain` 1268 stmts / 0 miss / **100%** |
| 后端表数 / 端点 | 26 表 / 71 路径 99 操作 | 未动后端（`git diff 4cee7f2 HEAD -- backend` 空），pytest 全绿即复现 |
| smoke（改前） | 17 步 / 305 断言 / 退出码 0 | 改后 **17 步 / 354 断言 / 退出码 0**（+49 = 反例页 4 + 每路由 3×15） |
| `npm run build`（改前） | 退出码 0 / 129 modules / CSS 70.22 kB / JS 166.88 kB | 改后 **退出码 0 / 129 modules / 主 chunk CSS 61.02 kB（gzip 8.89）/ JS 165.57 kB（gzip 58.05）** |
| `check:tokens`（改前） | 绿 / 33 文件 | 绿 / **32 文件**（少的那 1 个是删掉的 `lane.css`；下界 25 仍满足） |
| `@ts-ignore` / `@ts-expect-error` / `as any` | 0 | **0**（全 `src/**/*.{ts,vue}` 实测） |
| 新增依赖 | 0 | **0**（`git diff 4cee7f2 HEAD -- frontend/package.json frontend/package-lock.json` 空） |

⚠️ modules 数在 Task 1 结束时是 128（删 `lane.css` −1），Task 2 加回 `SectionHead.vue`
与 `SuccessMark.vue`（+2）、删 `LaneDivider.vue` 与 `StampFeedback.vue`（−2）后又回到 **129**。

---

## 2. 令牌

### 2.1 删除顺序（计划 §3 的警告怎么落的）

**先改引用、后删令牌**，用一次性 codemod（`$env:TEMP` 探针，跑完即删）做到：
phase A 令牌改名（长名优先）→ phase B 上下文相关声明改写（`--paper`/`--ink` 的两义、
偏移硬阴影、`--shadow-*`、`--bleed`）→ 然后才重写 `tokens.css` 与 `base.css`、删 `lane.css`。
收尾用一个自写探针 `tokenrefs.mjs` 断言「src 下每一个 `var(--x)` 都有所有者」：
**0 处无主引用**（唯一例外 `--bs-dwell`，它由 `Dashboard.vue` 的行内 `:style` 声明、
跨文件消费，属已知好的那一族）。

⚠️ 过程中自己撞了两个 codemod bug，都已在同一波内修掉并留了注释：
① `--track → --primary` 把同趟生成的 `--tracking-*` 前缀吃掉（全仓 27 处
`--primarying-caps`），加 `--track(?!ing)` 边界修复；
② 「删 `.surface-ink` 规则块」那一拍的正则会从**提到 `.surface-ink` 的注释**开始匹配，
吃掉注释终止符与紧随其后的规则块（6 个文件受损，其中 `App.vue` 的 `<script>` 被吃、
`vue-tsc` 当场报 13 个错）—— 处置是 `git checkout HEAD --` 那 6 个文件、
重跑不含该相的 codemod、被删块改由手改。这两条都写进了相关文件的注释。

### 2.2 新令牌（`tokens.css`，82 个自定义属性；色值字面量 22 处）

表面：`--bg #FFFFFF`、`--surface #F5F8FC`、`--surface-raise #FFFFFF`、`--surface-sunken #EDF2F8`、
`--border #DCE4EE`、`--border-strong #B9C7D9`、`--border-input #7E8CA0`（**新增**，见 §6）。
墨：`--ink #101828`、`--ink-soft #475467`、`--ink-faint #616D82`。
主蓝：`--primary #1668B3`、`--primary-hover #12599C`、`--primary-press #0E4C86`、
`--primary-faint #E8F1FA`、`--on-primary #FFFFFF`、`--on-primary-dim #D9E7F4`。
语义：`--red #C0392B`/`--red-faint #FCEDEC`、`--amber #8F5E00`/`--amber-faint #FDF4E3`、
`--green #2A7549`/`--green-faint #E9F4EE`。
字体：`--font-ui`（Hanken Grotesk + Noto Sans SC 回退）、`--font-data`（同栈 + tabular-nums）、
`--font-mono`（JetBrains Mono，仅口令/错误 code/JSON 原文）。
字重 `--fw-400…800`；字号 `--fs-hero clamp(48,13vw,88)` / `--fs-display clamp(30,8vw,48)` /
`--fs-title 24` / `--fs-subtitle 18` / `--fs-body 15` / `--fs-small 13` / `--fs-micro 12`；
大屏 `--fs-bs-hero clamp(72,6vw,128)` / `--fs-bs-display 56` / `--fs-bs-title 32` /
`--fs-bs-subtitle 24` / `--fs-bs-small 18`（下限，重测后不动，理由在文件里）。
行高字距 `--lh-tight 1.04` / `--lh-heading 1.25` / `--lh-body 1.6` /
`--tracking-title -0.01em` / `--tracking-caps 0.08em`。
图形符号 `--chip-size 20` / `--chip-size-board 28` / `--chip-radius` / `--chip-font 12` /
`--bar-accent 3` / `--bar-hair 1`。
间距 `--space-1…9`（4/8/12/16/24/32/48/64/96）。
布局 `--w-student 375` / `--w-teacher 1440` / `--gutter 16` / `--grid-columns 12` /
`--grid-gap 24` / `--span-alerts 8` / `--span-layers 4` / `--span-overview 4`。
形状 `--radius-sm 6` / `--radius 10` / `--radius-btn 8` / `--radius-lg 12` / `--border-hairline`。
动效 `--dur-fast 140ms` / `--dur-base 240ms` / `--dur-check 200ms` / `--dur-check-hold 1600ms` /
`--ease-out`。焦点 `--focus-ring 2px solid var(--primary)` / `--focus-offset 2px`。

### 2.3 删掉的令牌（61 个名字）

`--track` `--track-hover` `--track-on-paper` `--track-on-ink` `--track-arc-line`
`--track-arc-glow` `--track-arc-opacity` `--track-arc-radius`；
`--paper` `--paper-raised` `--paper-sunken` `--paper-soft` `--paper-faint`；
`--ink-raised` `--ink-sunken`；
**全部 `--*-on-ink`**：`--red-on-ink` `--amber-on-ink` `--moss-on-ink` `--red-wash-on-ink`
`--amber-wash-on-ink` `--moss-wash-on-ink` `--rule-hairline-on-ink`
`--border-hairline-on-ink` `--focus-ring-on-ink`（`--track-on-ink` 已计在上面）；
Plan 04 收尾波 6 个里的 3 个：`--offset-shadow-on-ink` `--hover-wash-on-ink` `--zebra-wash-on-paper`；
分道线全族：`--lane-thick` `--lane-thin` `--lane-offset` `--lane-rule-height` `--lane-num-size`
`--lane-num-weight` `--lane-num-tracking` `--lane-num-width` `--lane-gap` `--lane-block-gap`；
`--bleed` `--grain-opacity` `--shadow-paper` `--shadow-raised`；
`--font-display` `--font-zh-title` `--font-body`；
`--fw-display-600/700/800` `--fw-zh-title-700/900` `--fw-body-400/500`；
`--dur-roll` `--dur-stamp` `--dur-lane` `--reveal-stagger` `--ease-stamp`；
`--radius-none` `--radius-sharp` `--radius-stamp`；`--tracking-condensed` `--tracking-lane-num`。

⚠️ 计划 §3 还点了 `--chalk`：**实测全仓 0 处**（它从来没被建出来过）—— 计划引用了一个
不存在的东西，如实记录（计划自审第 3 项「要实测」的那一族）。
⚠️ 改名而非删除的：`--red-on-paper→--red`、`--amber-on-paper→--amber`、`--moss-on-paper→--green`、
`--*-wash→--*-faint`、`--rule-hairline→--border`、`--font-body/--font-display→--font-ui`。
⚠️ 本波收尾又删了 3 个**死令牌**：`--ease-linear`、`--fs-bs-body`（两者 05A 时就 0 引用）、
`--border-strong-line`（本波引入后发现 0 引用，自己删自己）。

### 2.4 `check:tokens` 的反空转下界：**没有调**

计划担心删令牌后不足 20 处。实测新 `tokens.css` 有 **22 处**色值字面量 ≥ 下界 20 ✓；
扫描面 33 → **32** 个文件 ≥ 下界 25 ✓。9 负控 / 8 正控仍全过（守卫自带自校）。

---

## 3. 五处结构性产物逐个的处置

1. **分道线母题：整体删除。** `styles/lane.css` 删（`main.ts` 的 import 同删）；
   `LaneDivider.vue` → **`SectionHead.vue`，同一个组件换了皮**（props 形状逐字保留
   `index/label/tone/level`，23 个调用点只改 import 名与文件名，**不是**新组件+逐处替换）；
   新形状 = 20×20 圆角小方块（主蓝底、白字、居中序号）+ 拉丁小标题 + 1px 规则线；
   两个导航与管理台目录页的「道次编号」换成同一个方块（尺寸同读 `--chip-size`）；
   报头的双线（3px 墨 + 偏移细线）→ 一条 1px 浅灰；14 个文件 60 处 `lane-block` 类与
   `:style="{ '--lane-index': N }"` 全删；staggered reveal 删。
2. **教师大屏翻浅底。** `.surface-ink` → `.surface-board`（`--surface` 极浅冷灰底，
   面板白）；`--*-on-ink` 一族全删；4 个图表与 4 个组件里的 `.xxx--on-ink`/`.surface-ink`
   覆盖块：颜色声明删光、**只留字号/尺寸那一档**（18px 下限仍在）；对比度重测见 §6。
3. **纸张纹理与跑道弧：两个都删。** `body::before` 的 `feTurbulence` 颗粒、
   `.surface-ink` 的 `repeating-radial-gradient` + `radial-gradient` 辉光、
   `StampFeedback` 章面的颗粒层，全删；全仓 `linear-gradient`/`radial-gradient`/
   `feTurbulence` 现在**只出现在注释里**（实测 grep）。层次靠 `--surface` /
   `--surface-sunken` 与白卡片的填充差；**零投影**（全仓仅剩 3 处
   `box-shadow: inset 0 -3px 0 <语义色>` 的「选中态下沿色条」，是平色条不是层次阴影）。
4. **四款字体 → 两款。** `index.html` 的 Google Fonts URL 换成
   Hanken Grotesk 400/500/600/700/800 + Noto Sans SC 400/500/700 + JetBrains Mono 400/700；
   `Noto Serif SC` 与 `Barlow Condensed` 删。为窄体调过的全部重调：字重映射
   display-800→700 / display-700→600 / zh-title-900→700（800 只留给纯数字的 `.num--hero`）；
   字距 0.14em→0.08em、新增 `--tracking-title -0.01em`；`--lh-tight` 0.92→1.04；
   `--fs-micro` 11→12px；视图里 10 处写死的 9px → 12px。等宽只留给口令投屏、
   错误 code、JSON 原文/请求体预览（全局 `code,kbd,samp,pre` 规则）。
5. **出血与不对称网格 → 规整。** `--bleed` 删；学生端 16px 边距只由 `App.vue` 的
   `.body` 一处给（`.s-card`/`StudentNav` 不再负边距）；大屏跨度 5/4/3 → **8/4、4/8、4/8、12、12**
   （逐排凑满 12 列、自动放置不留洞），「预警队列最重要」用 8 列的**面积**表达；
   `--grid-gap` 20→24px（8 的倍数），4 列面板可用宽 418.7→416px，仍大于
   `CompletionBars` 一行的实测最小内容宽 366px。

---

## 4. 动效

删掉的两个（计划点名）+ 同族两个（本波扩展，理由：与 ① 同一族 reveal，且删掉后
截图与守卫取到确定终态）：
① 分道线 staggered reveal（母题没了）；② `StampFeedback` 的盖章（印泥扩散+旋转+颗粒）
→ **`SuccessMark.vue`：200ms 对勾淡入**（`--dur-check`）；③ `StatBlock` 的数字滚动 →
**直接显示终值**（控制者裁定，同意：理由逐字写在 `StatBlock.vue` 文件头 —— 简洁、
取证坑消失、大屏每 5 秒重滚是干扰）；④ 4 个图表的 draw/grow/sweep。
保留：hover / `:focus-visible` 状态变化、大屏轮播的 200ms 过渡与 5 秒进度条（功能性）、
加载条的滑动段、对勾淡入。
**`:focus-visible`**：`base.css` 全局 `outline: var(--focus-ring)`（2px 主蓝）+
`outline-offset: 2px`，不靠浏览器默认；输入框额外 `border-color: var(--primary)`。
⚠️ `--force-prefers-reduced-motion`：**已不再为数字滚动所必需**（滚动删了），
但 smoke/shots 仍带着它 —— 今天它兜的是轮播过渡与加载条，且减动效本身是可达性要求。
⚠️ `SuccessMark` 的 `done` 时机 = 淡入 200ms **+ 停留 1600ms**（`--dur-check-hold`）：
调用方靠 `done` 收起这一格，若可见时长=淡入时长，「已打卡」三个字还没读完就消失。

---

## 5. §4.1 的重叠守卫

### 5.1 谓词实现（`smoke.mjs` 第 14 步，`LAYOUT_PROBE`）

TreeWalker 过 `SHOW_TEXT` 取每个非空文本节点的 `parentElement`；过滤零面积与
`visibility:hidden`/`display:none`/`opacity:0`；**对每个文本节点取 `Range.getClientRects()`
的逐行片段**两两求交；交集 > 较小者 20% 且非祖先-后代 → 重叠，输出双方
tagName + 文本前 20 字 + 两个 rect。溢出：`scrollWidth > clientWidth+1` 且
`overflow-x` 不是 `auto/scroll` → 报；整页另断言 `documentElement.scrollWidth <= innerWidth`。

⚠️ **逐行片段是对计划字面的一处修正**（第一版用 element 的 `getBoundingClientRect`）：
一个折行的行内元素（长 `<code>`/`<strong>`）的 union rect 会盖住同段落别的行，
首跑 15 条路由里 9 条因此假红（ratio 0.43–1 的「重叠」全是这种）。改逐行片段后
假阳性清零、真重叠仍命中（下面 3 处真重叠就是它抓出来的）。

⚠️ **溢出谓词放行 `overflow-x: auto/scroll` 的容器** —— 这是对计划 §4.1 字面
（「没有任何元素 scrollWidth > clientWidth+1」）的**顶回**：管理台 21 列的表
（`.a-scroll`）与详情页 JSON 原文（`.a-kv__pre`）是**故意**可横向滚的，照字面执行它们必红，
而那是设计不是失效。放行后仍断言整页无横向滚动条，故「页面级」的干净没有被放松。

### 5.2 已知反例那一拍的取证（硬规矩 #107）

一个 `data:` URL 的故意做坏页（两个 absolute span 叠放 + 嵌套父子文本 +
一个 auto 滚动容器 + 一个 visible 溢出容器），4 条断言全绿：
`反例页：叶子 8 个、重叠 1 处、非故意溢出 1 处`；
① 会报重叠 ✓ ② 报的确实是那两个 span（`重叠甲`/`重叠乙`）✓
③ 嵌套父子不报（重叠恰为 1 处）✓ ④ 放行 auto、报 visible 那一个 ✓。

### 5.3 15 条路由各自的重叠数 / 溢出数（最终一次 smoke，全 0）

| 路由 | 视口 | 含文本叶子 | 重叠 | 非故意溢出 | 整页 scrollWidth / innerWidth |
|---|---|---|---|---|---|
| login | 1440 | 63 | 0 | 0 | 1440 / 1440 |
| bind | 1440 | 81 | 0 | 0 | 1440 / 1440 |
| s-home | 375 | 111 | 0 | 0 | 375 / 375 |
| s-weekly-sheet | 375 | 241 | 0 | 0 | 360 / 375 |
| s-check-in | 375 | 228 | 0 | 0 | 360 / 375 |
| s-rpe | 375 | 150 | 0 | 0 | 360 / 375 |
| s-mini-test | 375 | 170 | 0 | 0 | 360 / 375 |
| s-notifications | 375 | 169 | 0 | 0 | 360 / 375 |
| t-dashboard | 1440 | 320 | 0 | 0 | 1425 / 1440 |
| t-report | 1440 | 288 | 0 | 0 | 1440 / 1440 |
| t-alerts | 1440 | 1153 | 0 | 0 | 1425 / 1440 |
| t-student-detail | 1440 | 478 | 0 | 0 | 1425 / 1440 |
| admin-index | 1440 | 231 | 0 | 0 | 1440 / 1440 |
| admin-list | 1440 | 202 | 0 | 0 | 1440 / 1440 |
| admin-detail | 1440 | 69 | 0 | 0 | 1440 / 1440 |

守卫首跑抓出并修掉的 3 处**真**问题：
① 大屏异常名单里 `.bs-alert__rule` 与 `.bs-alert__nums` 共用一个 grid area →
两个 grid item 完全叠放（ratio=1）→ 给 `nums` 独立一行；
② `LayerDonut` 环心大数字与小标签的 em 盒在环放大到 200px 时相碰 7px（ratio 0.264）→
y 从 58/74 拉开到 56/79；
③ `s-notifications` 的长 code 串把 375px 整页顶出横向滚动（scrollWidth 422）→
全局 `code,kbd,samp,pre { overflow-wrap: anywhere }`；以及 `t-report` 的 7 天条
每格 43px 放不下 60px 的日期 → 收内边距/字距并允许折两行。

### 5.4 顺手修掉的一格假绿（硬规矩 #109）

第 14 步 needle 原来有 `|| html.includes(n)` 的出口，而 dev 模式把 css 作为 `<style>`
注进 DOM：一句含 needle 的 CSS 注释就能顶替真正文。实测 `s-home` 的 needle
「的本周」与「本周训练量」命中的是 `base.css` 里 `.num--hero` 的注释，而页面真实状态是
403 横幅 + 空白正文。处置：needle 只在剥掉 style/script 的正文里找（守卫弹回那一拍同改），
`base.css` 那句注释改写（写这段时自己又踩了一次：第一版把那个串逐字写进了警告里）。

---

## 6. 对比度实测表（WCAG 2.x 相对亮度，读 `tokens.css` 的运行时口径）

44 对，**文字对 0 处不过 AA(4.5:1)**，图形对 0 处不过 3:1；
文字对里最低的一对 = `--on-primary-dim` on `--primary` = **4.55:1**。
自校：黑 on 白 = 21.00 ✓。

﻿tokens.css 里数到 22 个 hex 令牌
| 前景 | 值 | 背景 | 值 | 比值 | AA(4.5:1) / 图形(3:1) | 用法 |
|---|---|---|---|---|---|---|
| `--ink` | #101828 | `--bg` | #FFFFFF | **17.75:1** | ✓ | 正文/标题（全站） |
| `--ink` | #101828 | `--surface` | #F5F8FC | **16.66:1** | ✓ | 正文/标题（分区底） |
| `--ink` | #101828 | `--surface-raise` | #FFFFFF | **17.75:1** | ✓ | 正文/标题（卡片白） |
| `--ink` | #101828 | `--surface-sunken` | #EDF2F8 | **15.77:1** | ✓ | 正文/标题（空态底、斑马纹、输入框底） |
| `--ink` | #101828 | `--primary-faint` | #E8F1FA | **15.54:1** | ✓ | 悬停/选中的极浅底上的字 |
| `--ink-soft` | #475467 | `--bg` | #FFFFFF | **7.69:1** | ✓ | 次要文字（元信息行） |
| `--ink-soft` | #475467 | `--surface` | #F5F8FC | **7.22:1** | ✓ | 次要文字（分区底） |
| `--ink-soft` | #475467 | `--surface-raise` | #FFFFFF | **7.69:1** | ✓ | 次要文字（卡片） |
| `--ink-soft` | #475467 | `--surface-sunken` | #EDF2F8 | **6.83:1** | ✓ | 次要文字（说明块 `.s-notice` / `.t-notice`） |
| `--ink-soft` | #475467 | `--primary-faint` | #E8F1FA | **6.73:1** | ✓ | 悬停底上的次要文字 |
| `--ink-faint` | #616D82 | `--bg` | #FFFFFF | **5.23:1** | ✓ | 辅助文字（12px 的 `--fs-micro`） |
| `--ink-faint` | #616D82 | `--surface` | #F5F8FC | **4.91:1** | ✓ | 辅助文字（分区底） |
| `--ink-faint` | #616D82 | `--surface-raise` | #FFFFFF | **5.23:1** | ✓ | 辅助文字（卡片） |
| `--ink-faint` | #616D82 | `--surface-sunken` | #EDF2F8 | **4.64:1** | ✓ | 「不知道」那个破折号 `.unknown` |
| `--primary` | #1668B3 | `--bg` | #FFFFFF | **5.73:1** | ✓ | 链接、kicker、序号方块旁的强调字 |
| `--primary` | #1668B3 | `--surface` | #F5F8FC | **5.38:1** | ✓ | 同上（分区底） |
| `--primary` | #1668B3 | `--surface-raise` | #FFFFFF | **5.73:1** | ✓ | 同上（卡片） |
| `--primary` | #1668B3 | `--primary-faint` | #E8F1FA | **5.02:1** | ✓ | 选中行的文字 |
| `--primary-press` | #0E4C86 | `--bg` | #FFFFFF | **8.76:1** | ✓ | 按压态的文字/链接 |
| `--primary-press` | #0E4C86 | `--primary-faint` | #E8F1FA | **7.67:1** | ✓ | 悬停底上的链接 |
| `--on-primary` | #FFFFFF | `--primary` | #1668B3 | **5.73:1** | ✓ | 主按钮的字（`.btn--primary`） |
| `--on-primary` | #FFFFFF | `--primary-hover` | #12599C | **7.16:1** | ✓ | 主按钮悬停 |
| `--on-primary` | #FFFFFF | `--primary-press` | #0E4C86 | **8.76:1** | ✓ | 主按钮按压 |
| `--on-primary-dim` | #D9E7F4 | `--primary` | #1668B3 | **4.55:1** | ✓ | 选中导航格里那个极小拉丁缩写 |
| `--red` | #C0392B | `--bg` | #FFFFFF | **5.44:1** | ✓ | 红色预警的文字 |
| `--red` | #C0392B | `--surface` | #F5F8FC | **5.11:1** | ✓ | 红色预警（分区底） |
| `--red` | #C0392B | `--surface-raise` | #FFFFFF | **5.44:1** | ✓ | 红色预警（卡片） |
| `--red` | #C0392B | `--red-faint` | #FCEDEC | **4.78:1** | ✓ | 红色 pill / 徽章（淡底 + 深字） |
| `--red` | #C0392B | `--surface-sunken` | #EDF2F8 | **4.83:1** | ✓ | 红色（空态底） |
| `--amber` | #8F5E00 | `--bg` | #FFFFFF | **5.57:1** | ✓ | 黄色预警 / 「值未知」的文字 |
| `--amber` | #8F5E00 | `--surface` | #F5F8FC | **5.23:1** | ✓ | 黄色预警（分区底） |
| `--amber` | #8F5E00 | `--surface-raise` | #FFFFFF | **5.57:1** | ✓ | 黄色预警（卡片） |
| `--amber` | #8F5E00 | `--amber-faint` | #FDF4E3 | **5.10:1** | ✓ | 琥珀 pill / `.s-unknown` / `.t-notice--warn` |
| `--amber` | #8F5E00 | `--surface-sunken` | #EDF2F8 | **4.95:1** | ✓ | 琥珀（空态底） |
| `--green` | #2A7549 | `--bg` | #FFFFFF | **5.62:1** | ✓ | 「正常/已完成」的文字 |
| `--green` | #2A7549 | `--surface` | #F5F8FC | **5.27:1** | ✓ | 同上（分区底） |
| `--green` | #2A7549 | `--surface-raise` | #FFFFFF | **5.62:1** | ✓ | 同上（卡片） |
| `--green` | #2A7549 | `--green-faint` | #E9F4EE | **4.98:1** | ✓ | 绿色 pill / 徽章 |
| `--green` | #2A7549 | `--surface-sunken` | #EDF2F8 | **4.99:1** | ✓ | 绿色（空态底） |
| `--border-input` | #7E8CA0 | `--bg` | #FFFFFF | **3.42:1** | ✓ | ⚠️ 非文字：表单控件的边界（WCAG 1.4.11 要求 3:1） |
| `--border-input` | #7E8CA0 | `--surface` | #F5F8FC | **3.21:1** | ✓ | ⚠️ 非文字：表单控件的边界（分区底） |
| `--border-strong` | #B9C7D9 | `--bg` | #FFFFFF | **1.72:1** | —（装饰，不单独承重） | ⚠️ 非文字（装饰）：图表网格 / 卡片里的次级分隔 |
| `--border` | #DCE4EE | `--bg` | #FFFFFF | **1.28:1** | —（装饰，不单独承重） | ⚠️ 非文字（装饰）：卡片边框（分隔同时靠白 vs 极浅冷灰的填充差） |
| `--on-primary` | #FFFFFF | `--border-input` | #7E8CA0 | **3.42:1** | ✓ | ⚠️ 非文字：主按钮底 vs 相邻的输入框边 |

共 44 对；文字对里最低的一对：--on-primary-dim on --primary = 4.55:1（选中导航格里那个极小拉丁缩写）
不过 AA(4.5:1) 的文字对：0 处
不过图形 3:1 的对：0 处
自校（黑 on 白，应为 21.00）：21.00

⚠️ 与计划建议值不同、以实测为准压深的三档（计划 §3 授权「实现者应当自己调」）：
`--ink-faint` #79839A→**#616D82**（建议值实测 3.80:1，而本仓把它用在 12–13px 元信息上，
且它还要站在 `--surface-sunken` 上）；`--amber` #9A6700→**#8F5E00**（建议值在自己那档
淡底上 4.46:1）；`--green` #2E7D52→**#2A7549**（4.47:1）。
⚠️ **新增 `--border-input #7E8CA0`**：WCAG 1.4.11 要求「识别控件所必需的边界」≥3:1，
而 `--border`(1.28:1)/`--border-strong`(1.72:1) 不够；它只用在表单控件的边
（实测 3.42:1 on 白、3.21:1 on `--surface`）。那两档浅色**不是失误**：卡片/分区的分隔
同时靠白 vs 极浅冷灰的填充差表达，边框不单独承重（表里标「装饰，不单独承重」）。
⚠️ 大屏 18px 下限**重测后不动**：翻浅底后投影可读性变好（投影仪在亮环境把深底洗成灰底，
暗底亮字的损失远大于亮底暗字），且最浅字色已 ≥4.6:1；抬到 20px 会让 `CompletionBars`
一行最小内容宽从 366px 涨到 ~406px，逼近 4 列面板的 416px。

---

## 7. 截图、待清扫、关切、没按派单做的地方、顶回

### 7.1 15 张截图（`Document/`，ASCII 文件名，学生端 375 / 教师与管理台 1440）

`Document/shot-01-login.png`、`shot-02-bind.png`、`shot-03-s-home.png`、
`shot-04-s-weekly-sheet.png`、`shot-05-s-check-in.png`、`shot-06-s-rpe.png`、
`shot-07-s-mini-test.png`、`shot-08-s-notifications.png`、`shot-09-t-dashboard.png`、
`shot-10-t-report.png`、`shot-11-t-alerts.png`、`shot-12-t-student-detail.png`、
`shot-13-admin-index.png`、`shot-14-admin-list.png`、`shot-15-admin-detail.png`。
取证脚本 `frontend/scripts/shots.mjs`（CDP + Node 24 全局 WebSocket，零依赖；
每条路由一个新标签页 + 导航前写好 identity 的 localStorage 镜像，对齐「登录过的用户
刷新页面」的真实形态；`--force-prefers-reduced-motion`）。

### 7.2 待清扫（8 条，编号 0–7）

0. **演示库当前是干净的**（本波最后重灌过一次 `demo.ps1`）；但 smoke 会写脏它，
   下一次跑 smoke 前请重灌（第 0 步会红在行数上，那是它的守卫职责）。
1. `router/index.ts` 的 `meta.surface: 'ink'` 字面值与实义不符（它今天选的是「大屏排版档」
   不是深底）—— 该文件在禁改清单里，映射写在 `App.vue`，留待下一波改名。
2. `IdentitySwitcher` 的 DEV 半与 `session.adopt()` 之间存在竞态窗口（`devRole` 的 setter
   可能把身份设成「名册第一行」）；根因在 `src/stores/**`（禁改），本波用 shots 的镜像预写绕开。
3. `frontend/package.json` 的 `description` 仍写《田径场年鉴》—— 为保住
   「package.json 有没有被改」这格验收，本波一个字节没动它。
4. `present.ts` 的 `Level` 槽位名仍叫 `moss`（颜色令牌已叫 `--green`）—— 禁改文件，
   故类名 `.pill--moss` / `.stat__value--moss` 沿用槽位名。
5. 教师端 `.t-*` 与大屏 `.bs-*` 两套类名今天只分**字号阶梯**（颜色已同一套），未来可合并。
6. `Document/` 里 Plan 05A 的 4 张旧截图（`2026-10-11-screenshot-*.png`）是旧设计，可删。
7. needle 假绿还有一族没钉死：「正文里恰好有同名字串」（例如空态文案里出现 '未读'）。
   要彻底钉死得给 needle 加选择器级断言，代价大，登记不修。

### 7.3 关切（2 条）

· 12px 的 `--fs-micro` 在 375px 下仍是个别窄格的极限（`t-day` 的日期折成两行）；
  未来加更长的日期格式要重跑第 14 步守卫。
· 大屏口令面板在 <1200px 视口下 8 列会变窄，`--fs-bs-hero` 的口令靠
  `overflow-wrap: anywhere` 折行兜底（不横向溢出，但会两行）。

### 7.4 没按派单字面做的地方（7 处，逐条给理由）

1. 间距令牌名保留 `--space-*` 而非计划建议的 `--gap-*`：同一套值、同一个唯一住址，
   改名要动 364 处引用而视觉收益为 0。
2. 溢出谓词放行 `overflow-x: auto/scroll` 容器（§5.1，同时记为顶回）。
3. `SuccessMark` 可见时长 = 200ms 淡入 + 1600ms 停留（计划只钉了淡入时长）。
4. `shots.mjs` 不挂 `npm run shots`（`package.json` 一个字节不动）。
5. 删了 4 个图表的 draw/grow/sweep（计划 §3 的三处清单之外的同族动效）。
6. 计划 §3 与 §2 自相矛盾的两处取值：`--radius-lg` 取 §2 的 12px（卡片）而非 §3 的 16px；
   对比度三档与 `--fs-micro` 以实测为准（§6）。
7. commit `089c0ca`（Task 3）的消息把 `Home.vue` 的修复记在 Task 3 名下，而代码实际落在
   `3643023`（Task 2，因为那次 `git add frontend/src` 是整目录加的）—— 消息归属误差，
   代码只有一份，不重写历史。

### 7.5 顶回控制者的地方：**1 处**

**顶回 ①**：§4.1「没有任何元素 `scrollWidth > clientWidth + 1`」的字面 →
放行自己声明了 `overflow-x: auto/scroll` 的容器（理由 §5.1：管理台 21 列表与 JSON 原文块
是故意的滚动容器，照字面必红且红错了方向）。

计划点名的三处「最可能顶回」，逐条核过、**都不顶回**：
① **删数字滚动** —— 同意并执行：`StatBlock.vue` 文件头记了三条理由（简洁、取证坑消失、
大屏每 5 秒重滚是干扰）；不认为大屏因此显呆（轮播过渡与进度条仍在，数字直接给终值
在投影上反而更稳）。
② **Hanken Grotesk** —— 同意：实测截图里 12–88px 各档与中文混排干净、字重 400–800
够用（800 只给纯数字）；它不在 `frontend-design` 技能的禁用名单里。
③ **20% 阈值** —— 同意：实测命中分布是 1 / 0.94 / 0.45 / 0.264（真重叠）对
0（其余 15 路由），阈值既没漏报也没误报；0.264 那一处（环心 em 盒相碰）确实是
人眼看不出不舒服、但盒子真碰了的那一族，报它对。
另核过而未顶回的：`--space` vs `--gap`（记为 deviation ①）、`--radius-lg` 12 vs 16
（取更具体的 §2）、对比度三档（计划自己授权以实测为准）。

---

## 8. 最终验收

| 项 | 结果 |
|---|---|
| `npm run build` | 退出码 **0**；**129 modules**；主 chunk **CSS 61.02 kB**（gzip 8.89）/ **JS 165.57 kB**（gzip 58.05） |
| `@ts-ignore` / `@ts-expect-error` / `as any` | **0** |
| `npm run check:tokens` | 绿（32 文件；tokens.css 22 处色值 ≥ 下界 20；9 负控 8 正控全过） |
| `npm run check:dist` | 绿（smoke 第 15 步内含；`dist/` 里 `adoptFromUrl` 0 次） |
| `npm run smoke` | **17/17 步全绿、354 断言 0 红、退出码 0**（305 → 354） |
| 后端 pytest | **1332 passed + 1 skipped**（带 `--cov`；=派单的 1333 口径），`app/domain` 1268/0/100% |
| `git diff 4cee7f2 HEAD -- backend` | **空** |
| `git diff 4cee7f2 HEAD -- backend/data` | 空；四个单文件指纹与 18 套模板指纹由 pytest 内的 |
| | `test_national_standard_csv_fingerprint_is_pinned`（D2C8E539E2FA0029）、 |
| | `test_exercises_yaml_fingerprint_is_pinned`、`test_equivalence_yaml_fingerprint_is_pinned`、 |
| | `test_alert_rules_yaml_fingerprint_is_pinned`、`test_template_yaml_fingerprints_are_pinned` 钉住，全过 |
| `Test-Path backend\pe.db` | **False**；`backend/data/seed/` **0 文件** |
| `package.json` / `package-lock.json` | **未被改**（diff 空；新增依赖 0） |
| 行尾 | `frontend/**` 工作树统一 CRLF（本波新建/整写文件逐个转过；`demo.ps1` 一个字节没碰） |

commit（起点 `4cee7f2` 之后）：

| sha | 内容 |
|---|---|
| `2ef14e1` | Task 1 令牌与基座 |
| `3643023` | Task 2 原子组件换皮（含 Home.vue 的 403 修复） |
| `089c0ca` | Task 3 学生端 6 页 |
| `8ae1aa7` | Task 4 教师端 4 页 + 4 图表 |
| `0b43e21` | Task 5 管理台 3 页 + 登录/绑定 2 页 |
| `ac89ed0` | Task 6 重叠守卫 + 15 张截图 + 收尾清扫 |
