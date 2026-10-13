# 品牌与密度波（2026-10-13）—— 实现者报告

分支 `brand/xmu-and-density`（自 `main` @ `6a00fe9` 起，未 push、未碰 main）。
三件事：① 系统改名 + 厦门大学品牌接入；② 教师大屏「本周概览 / 数据水位」那一排的密度与留白；
③ 重拍 15 张交付截图。

commits：
  ① `de6f312` feat(frontend)!: 品牌素材入库 + 主蓝换成厦大蓝 #122e66
  ② `36d094c` feat(frontend)!: 改名「厦大体育数智系统」+ 厦门大学品牌锁排
  ③ `c1809b6` fix(frontend): 教师大屏密度（ⓘ 折叠 + 7 天条 + 概览并排 + 面板等高）
  ④ 本 commit（重拍 15 张截图 + 本报告 + `shots.mjs` 的图片就绪门 + 登录页副题去重）
  ⚠️ ④ 的 sha 不写进本文件（自指会让「字节数与入库 blob 一致」这一格永远对不上）；
     读 `git log --oneline -1`。

---

## 1. 环境

| 项 | 实测 |
|---|---|
| Node | v24.19.0 |
| npm | 11.17.0 |
| Python | 3.11.1 |
| git | 2.55.0.windows.5（`core.autocrlf` 实测 `true`） |
| 后端 | `http://127.0.0.1:8000`（跑前实测为**干净演示库**，见 §7 的 8 个资源行数） |
| 前端 | `http://localhost:5173`（vite） |
| 业务日 | 2025-10-12 |
| 演示账号 | 口令 `pe-demo-2025`；学生 `2023120001`(id 4)、教师 `T0001`、管理员 `T0003` |

⚠️ 开工第一件事（硬规矩 #73）：`node --version; npm --version` → **v24.19.0 / 11.17.0**，已记在本节。

---

## 2. 品牌

### 2.1 两个矢量素材入库

| 入库路径 | 字节 | sha256[:16] | 与源文件逐字相同 | 入库 blob 字节 |
|---|---|---|---|---|
| `frontend/src/assets/brand/xmu-emblem.svg`（校徽，源 `xmu-logo.svg`） | 52 095 | `394C0A85CEBB5A45` | **True** | 52 095 |
| `frontend/src/assets/brand/xmu-wordmark.svg`（嘉庚体校名，源 `xmu-zi-jiageng.svg`） | 15 975 | `17E74386647229A2` | **True** | 15 975 |

· 两者都是纯矢量（`<path>` 10 + 1 个，无 `<image>` / `<text>` / `<style>`），`fill` 逐字 `#122e66`。
· 固有尺寸：校徽 1066.6667²（1:1）；校名 533.33417 × 145.65753（宽高比 **3.662:1**，
  该比值住在 `src/brand.ts` 的 `WORDMARK_RATIO`，不写第二份）。
· **鲁迅体不用**（控制者裁定）：它只有位图（`.jpg` / `.pdf`），36–64px 的报头/锁排档会发虚。
· `.gitignore` 没有忽略 svg（根 `.gitignore` 与 `frontend/.gitignore` 都只忽略
  `node_modules/` / `dist/` / 日志 / 编辑器文件）。
· ⚠️ **`.gitattributes` 新增一条**：`frontend/src/assets/brand/*.svg -text`。
  理由：两个源文件实测是**纯 LF、无 BOM**（91 / 46 个 LF、0 个 CRLF），而本机
  `core.autocrlf` 是 `true` —— 不钉的话下一次 checkout 会把它们重写成 CRLF，
  字节数当场变假（52 095 → 52 186、15 975 → 16 021）。亲验：
  `git check-attr text eol -- frontend/src/assets/brand/xmu-emblem.svg` → `text: unset`。
  改后 `.gitattributes` = 7 386 B、纯 CRLF、sha256[:16] `6CBB91EFED6BA115`。

### 2.2 tokens 里动了哪几个色

**新增 0 个色令牌；改值 5 个**（`src/styles/tokens.css`，唯一住址）：

| 令牌 | 改前 | 改后 | 关键实测比值 |
|---|---|---|---|
| `--primary` | `#1668b3` | **`#122e66`**（厦大蓝，与两个 svg 的 fill 同值） | 对白底 **13.06:1** |
| `--primary-hover` | `#12599c` | **`#2e5299`** | 对白底 7.55:1；白字在其上 7.55:1 |
| `--primary-press` | `#0e4c86` | **`#0d2350`** | 对白底 15.29:1；在 `--primary-faint` 上 12.24:1 |
| `--primary-faint` | `#e8f1fa` | **`#e3e6ed`**（厦大蓝在白底上 12% 的 tint） | `--primary` 在其上 10.45:1；对白底 1.25 |
| `--on-primary-dim` | `#d9e7f4` | **`#a0abc2`**（厦大蓝与白按 0.60 混合） | 在 `--primary` 上 **5.66:1** |

四条重算的结论（逐字写进了 tokens.css 的注释）：
1. `#122e66` 对白底实测 **13.06:1** —— 派单估的「约 10.9:1」**偏低**，实测更好（见 §6 顶回 ④）。
2. 常态已经 13.06:1，故**悬停的方向从「变深」翻成「变浅」**：再往深走在投影上看不出
   状态变化；往浅走到 7.55:1 才是一档看得见的 hover，且仍远高于 AA。
3. 极浅底取派单给的 8%–12% 带的**上界 12%**：8% / 10% 与 `--surface-sunken`(#EDF2F8) 的
   区分度只有 1.03 / 1.07，12% 是 1.11、对白底 1.25（旧值 `#e8f1fa` 对白底只有 1.14）。
4. `--on-primary-dim` 不再走「淡到刚好压线」的配方（旧值在旧主蓝上 4.55:1，离 AA 只差 0.05）：
   改成 5.66:1，「次要」交给色相（发灰的钢蓝 vs 纯白）去说。

⚠️ 语义三色（红/琥珀/绿）与中性色（墨/表面/边框）**一档没动** —— 换主色不是换整套皮肤。
⚠️ 六个文件里引用旧比值（5.73:1 / 4.55:1）的**注释**同步改成实测值
（`App.vue` / `IdentitySwitcher.vue` / `StudentNav.vue` / `TeacherNav.vue` / `admin.css` /
`Dashboard.vue`）—— 一个印着过期数字的注释比没有注释更坏。

### 2.3 对比度取证（44 对，与 Plan 05B 报告 §6 **同一口径**）

前景/背景的值一律从 `tokens.css` **现读**（剥注释后取 `--x: #hex;`，共 22 个令牌），
WCAG 2.x 相对亮度公式。结果：

· 44 对：**不过 AA(4.5:1) 的文字对 0 处；不过图形 3:1 的对 0 处**；自校（黑 on 白）= 21.00。
· 文字对最低的一对从改前的 **4.55:1**（`--on-primary-dim` on `--primary`）
  **抬到 4.64:1**（`--ink-faint` on `--surface-sunken`）。

**文字对最低的 5 对（升序）**：

| 比值 | 前景 | 背景 | 用法 |
|---|---|---|---|
| **4.64:1** | `--ink-faint` #616D82 | `--surface-sunken` #EDF2F8 | 「不知道」那个破折号 `.unknown` |
| **4.78:1** | `--red` #C0392B | `--red-faint` #FCEDEC | 红色 pill / 徽章（淡底 + 深字） |
| **4.83:1** | `--red` #C0392B | `--surface-sunken` #EDF2F8 | 红色（空态底） |
| **4.91:1** | `--ink-faint` #616D82 | `--surface` #F5F8FC | 辅助文字（分区底） |
| **4.95:1** | `--amber` #8F5E00 | `--surface-sunken` #EDF2F8 | 琥珀（空态底） |

非文字里最低的三对（都过 3:1 或标了「装饰，不单独承重」）：
`--border-input` on `--surface` **3.21:1** ✓、`--border-input` on `--bg` **3.42:1** ✓、
`--on-primary` on `--border-input` **3.42:1** ✓；装饰档 `--border-strong` 1.72:1 /
`--border` 1.28:1（不单独承重，分隔靠白 vs 极浅冷灰的填充差）。

⚠️ **顺手量到一个新陷阱并写进 tokens.css 的注释**：`--ink-faint` 在新的 `--primary-faint`
上只有 **4.18:1**（不过 AA）。今天全仓 0 处这么用（`--primary-faint` 的引用点一律配
`--primary-press`），而本波新加的「ⓘ 口径」折叠条 hover 时**只改字色、不加底**，
正是为了不掉进这一格。

本波新增的图形对（不在那 44 对里，单列）：7 天条的柱 `--primary` on `--surface-raise`
**13.06:1** ✓、on `--surface-sunken` **11.60:1** ✓（图形需 3:1）。

### 2.4 `check:tokens` 与 svg 的 glob

`npm run check:tokens` **仍绿**：扫描面 33 → **35 个文件**（多了 `BrandLockup.vue` 与
`CaliberNote.vue`），tokens.css 之外 0 处色值字面量。
⚠️ **守卫的 glob 不需要为品牌素材收窄、也不需要开豁免**：`scripts/check-tokens.mjs` 的
扫描面是 `SCANNED_EXTENSIONS = new Set(['.css', '.vue'])`，`.svg` **不在面里**（亲验：
加素材前后该守卫的「扫描面」只随 .css/.vue 的个数变）。派单里担心的「svg 里的 #122e66
把守卫扫红」不会发生；反过来本波在 `brand.ts` 的文件头逐字警告了**不要内联 svg 进 .vue**
（内联才会让那 10 处 fill 落进扫描面）。

---

## 3. 改名

### 3.1 旧名字「体育闭环原型系统」的用户可见命中（7 处字面 + 4 处同族）

| # | 住址 | 改前 | 改后 |
|---|---|---|---|
| 1 | `frontend/index.html` `<title>` | 体育闭环原型系统 | **厦大体育数智系统** |
| 2 | `frontend/index.html` `<meta name="description">` | 体育闭环原型系统 —— … | 厦大体育数智系统 —— …（并补一句品牌） |
| 3 | `frontend/src/App.vue` 报头 `<h1>`（全站唯一） | 体育闭环原型系统 | 搬进 `BrandLockup variant="masthead"`（读 `brand.ts`） |
| 4 | `frontend/src/router/index.ts` `document.title`（2 处字面量） | `` `${title} · 体育闭环原型系统` `` | `` `${title} · ${SYSTEM_NAME}` `` |
| 5 | `frontend/package.json` `description` | 体育闭环原型系统 · 前端… | 厦大体育数智系统 · 前端… |
| 6 | `backend/scripts/demo.ps1` 第 64 行 `Write-Host` | `== 体育闭环原型系统 · 演示 ==` | `== 厦大体育数智系统 · 演示 ==` |
| 7 | `frontend/src/App.vue` 页脚 colophon 开头 | `原型系统 · 已做真实鉴权…` | 删掉那四个字（版本行改由锁排印） |

同族（不是旧名字、但同属「原型阶段的自我描述」，一并处理）：
· 报头 kicker `PHYSICAL EDUCATION · CLOSED LOOP` 与登录页同一行 → **`PHYSICAL EDUCATION · LAYERED PRESCRIPTION`**
  （「闭环」与「原型」同族；副题该说系统**做什么**。派单授权「保留或换，但不要再叫 prototype」）。
· 报头 `北欧公共标识 / NORDIC SIGNAGE` 那一行 → **删掉**（设计语言的自述不是产品内容；
  设计语言的取证住址在 `tokens.css` 的文件头）。
· 登录页 `.auth__fine`「本原型**不做**口令找回…」→「本**系统**不做…」。

**没改**（逐字记录，见 §6）：
· `backend/app/main.py:174` `FastAPI(title="体育闭环原型系统")` —— 它是 `/docs` 与
  `/openapi.json` 的标题、**用户可见**，但本波禁改 `backend/app/**` 的生产代码 → **顶回**。
· `backend/scripts/demo.ps1:3` 的 `.SYNOPSIS`（comment-based help，属 docstring）→ 按派单不改。
· `Document/` 下各计划文档与 spec 正文的旧名字 → 历史记录，不改（spec 只在 §13 点一段，见下）。
· 渲染文本里其余 6 处「本原型」（`Bind.vue` ×3、`api/auth.ts`、`api/client.ts`、
  `ApiErrorBanner.vue`、`Home.vue`）→ 待清扫（§6）。

### 3.2 `document.title` 实测值

CDP 实测（`/t/dashboard`）：**`"班级大屏 · 厦大体育数智系统"`**；`/login` 等无 `meta.title`
的路由落到 `SYSTEM_NAME` 本身。`<h1>` 实测全站恰好一个：`["厦大体育数智系统"]`。

### 3.3 登录页锁排长什么样（一句话）

居中一列：64px 圆形盾徽 → 184×50 的嘉庚体「廈門大學」→ 24px 厦大蓝的系统名
→ 12px 全大写拉丁副题 `PHYSICAL EDUCATION · LAYERED PRESCRIPTION` → 12px、字距 0.24em、
厦大蓝的校训「止 於 至 善」（读起来像一枚印章，不是标语）。
报头档 = 36px 盾徽 + `XIAMEN UNIVERSITY` + 系统名（`<h1>`）；页脚档 = 112px 嘉庚体校名 +
校训 + `厦大体育数智系统 · v0.1.0`（版本号编译期取自 `package.json`，见 `vite.config.ts` 的 `define`）。
三档的住址是 `components/BrandLockup.vue`（唯一）；名字/素材 URL 的住址是 `src/brand.ts`。

### 3.4 两个字节级敏感文件的改后状态

· `backend/scripts/demo.ps1`：**19 563 B**（改前同）、UTF-8 **带 BOM**（前 3 字节 `ef bb bf`）、
  纯 CRLF **267/267**、0 个裸 LF、sha256[:16] **`A075D2F0871DF37A`**。
  ⚠️ 只按字节改（python `read_bytes`/`write_bytes`），没碰 IDE 的编辑工具（它吃过两次 BOM）。
  `smoke.mjs` 第 17 步 ① 的三条字节级断言（BOM / 纯 CRLF / `-DryRun` 行为）实测仍绿。
· `Document/2026-09-28-体育闭环原型-设计spec.md`：**205 466 B**（改前 204 473）、
  **1 675 行**（`\n` 计数；编辑器口径 1 676，派单写的 1 666 是改前的编辑器口径）、
  **无 BOM**、纯 CRLF 1 675/1 675、sha256[:16] **`A4C072354CA82AA5`**。
  改动 = §13 顶部加**一段**（10 行）改名说明：说清新名字、说清 spec 全篇仍用旧名字是**有意的**
  （审计链里的引文不得改假）、并点出旧名字今天只剩的两处代码（`main.py` 的 title 与
  `demo.ps1` 的 `.SYNOPSIS`）。⚠️ 比派单的「一句」多了几行，理由见 §6。

---

## 4. 密度：5 条诊断的逐条复核

复核手段：改前/改后各跑一次 CDP 几何探针（`getBoundingClientRect`，1440×2200，
同一个干净演示库），加上人眼看 `Document/shot-09-t-dashboard.png`。

### 诊断 ① 「每个面板底部的 `bs-fine` 是松散感的主要来源」—— **同意**

实测改前：6 块 `.bs-fine` 合计 **518.3px**（顶栏 1 块 28.8px + 面板里 5 块 489.6px）；
面板里那 5 块占所在面板高度的 **21%–28%**（分层 144.0/524.0、概览 144.0/685.5、
课堂 RPE 86.4/351.8、预警 57.6/819.3、口令 57.6/592.9）。它们是 18px 的长句、
夹着 `code` 与后端字段名 —— 给审计看的内容占了投屏的 prime space。判定成立。

**ⓘ 折叠的形态**：`<details class="bs-cal">` + `<summary>ⓘ 口径</summary>`，
**默认收起**、原生零 JS 零依赖、可键盘操作；展开的正文 = 原 `.bs-fine` 的**全部内容逐字**
（一个字没删 —— 硬规矩 #39 的审计链）。住址：组件 `components/CaliberNote.vue`（无 `<style>` 块），
样式 `.bs-cal*` 在 `styles/teacher.css`（`.bs-*` 一族的唯一住址）。
⚠️ 顶栏那一块 `.bs-fine`（含「暂停轮播」按钮）**没动** —— 它含功能控件，不是口径说明。
⚠️ 实测改后：`.bs-fine` 合计 518.3 → **28.8px**（只剩顶栏那一块）；5 个 `.bs-cal` 各 32px、全 `open=false`。

⚠️⚠️ **撞到一个坑并留下了守卫**：Chrome 收起 `<details>` 用的是
`::details-content { content-visibility: hidden }`，而它隐含 `contain: size` —— 包装盒压成 0 高、
**子树却照样排版**，`getClientRects()` 返回非空矩形；而 §4.1 守卫的 `visible(el)` 只看
`visibility`/`display`/`opacity` 三个计算值（`content-visibility` 不在里面，实测仍是 `visible`）。
首跑 t-dashboard **7 处假重叠**（最坏 ratio 0.852：面板 3 的口径正文 × 「本周（水位 2025-10-12)」）。
处置：`.bs-cal:not([open]) > .bs-cal__body { display: none }` —— `display:none` 的子树不生成盒、
`getClientRects()` 返回 0 个矩形，守卫按既有口径（`rects.length === 0` → 跳过）放过。
逐字取证写在 teacher.css 那条规则的注释里。**展开态另跑了一次同一谓词：0 重叠 / 0 溢出**
（5 个全展开后面板高度 875.7/875.7、586.7/586.7、649.3/649.3、672.1、415.2，仍逐排等高）。

### 诊断 ② 「RPE 7 天条在稀疏周上是 6 个空洞」—— **同意结论，修正机制**

实测改前：`.bs-days` 122.2px，且 `day0 == dayOn == 122.2` —— **7 格完全等高**。
也就是说改前**根本没有柱状图**：它是 7 个「3px 顶边 + 16px padding + 三行 18/32/18px 文字」的
灰瓷砖，有值与无值一样高。演示库这一周只有 1 节课有快评，故 6 格是「— / 无快评」的空瓷砖 ——
「6 个洞」的观感成立，但机制不是「6 根高柱」，而是「7 块等高的砖」。

改后：一张真的柱状图 —— 柱在一条**共享基线**上生长（改前是每格自己一条 3px 的**顶**边，
「基线」被说了 7 遍且说的是顶上）；空日只剩 **2px 的基线刻度** + 弱化标签（18px 灰、常规字重）；
有值的日升起成实心厦大蓝的柱，日期与数值升一档（墨色 / 600）；绘图带里一条**周均值虚线参考线**
（读后端 `rpe_summary.mean`，本页不再算第二遍；数值在面板右上 aside 逐字印出
「本周均值 6.37（虚线）· 上周均值 6.27」）。
**高度：自然高 122.2 → 72.8px（−40.4%）**，算式逐字在 Dashboard.vue 的样式注释里
（绘图带 24 含 2px 基线 + 缝 2 + 两行 18×1.3 = 46.8）。
⚠️ 「—」与「0」的区分纪律**没有破**，且现在有两重：文字侧「无快评」vs「0.0 · N 份」；
图形侧浅灰 2px 刻度 vs 实心柱（`.bs-day__bar--on { block-size: max(2px, var(--bs-bar)) }`
保证 RPE 真的是 0 的那天也有一根看得见的柱）。
⚠️ **渲染态**的 `.bs-days` 是 **243.2px** 而不是 72.8px —— 见诊断 ④ 与 §6 顶回 ②。

### 诊断 ③ 「本周概览两个大数上下叠，把面板撑高」—— **同意**

实测改前：两个 `StatBlock` = 105.6 + 138.4 = **244.0px** 两行；面板 4 列（416px 可用宽），
一个 56px 的数字独占一行、左右各 ~150px 的白。改后：**左右并排**（`.bs-duo`，
`repeat(2, minmax(0, 1fr))`）→ 105.6px 一行；右边那个 StatBlock 的 caption 挪成**整行**的一条注
（文字逐字不动，宽度 202 → 416px，于是它从 3 行变回 1 行）。
3 行 `bs-row`：上下 padding 8→4px、行高 1.6→1.3、并加 **leader line（点线）**
（`border-block-end: 2px dotted`，一个 `aria-hidden` 的空 span，故不参与重叠求交）：
**136.4 → 96.2px**。面板整体 **685.5 → 418.7px（−38.9%）**。

### 诊断 ④ 「同一排面板高度对齐，内容少的不留底部空洞」—— **同意（并顶回半条，见 §6）**

实测改前三排的锯齿状白合计 **885.9px**（第 1 排 819.3−524.0 = 295.3、第 2 排 685.5−351.8 = 333.7、
第 3 排 592.9−336.0 = 256.9）。改后 `.bs-grid { align-items: stretch }` + 两条配套：
`.bs-cal { margin-block-start: auto }`（口径条钉在面板底部）与 `.bs-panel__fill`
（图表那一格吃掉剩余高度：能长的长 —— RPE 的绘图带 `flex: 1 1 auto`；不能长的居中 ——
分层环写死 200×200、三层完成率的四行是内容定高的）。
实测改后逐排等高：794.1/794.1、418.7/418.7、567.7/567.7、672.1、415.2 —— 锯齿 = **0**。

### 诊断 ⑤ 「不动 20% 阈值、不引入阴影/渐变/纹理」—— **遵守**

· §4.1 的 20% 重叠阈值一个字没动（`smoke.mjs` 未改谓词）。
· 零阴影 / 零渐变 / 零纹理：点线用 `border-block-end: dotted`、参考线用 `border-block-start: dashed`
  （虚线是本仓**既有**语汇：`.bs-empty__mark-hair` 与 `.cbars__track--void` 早就在用）；
  「靠填充差让面板站出来」保住（白面板 vs `--surface` 的极浅冷灰底），只是主色换成厦大蓝一族。

### 4.1 `shot-09` 改前 / 改后的面板高度实测（CDP，1440×2200，同一干净演示库）

| 面板 | 改前 h | 改后 h | 说明 |
|---|---|---|---|
| 1 预警队列（8 列） | 819.3 | 794.1 | −25.2（口径折叠） |
| 2 分层分布（4 列） | 524.0 | **794.1** | stretch 到与 1 等高；环居中 |
| 3 本周概览（4 列） | 685.5 | **418.7** | −38.9% |
| 4 课堂快评 7 天（8 列） | 351.8 | **418.7** | stretch；绘图带吸收剩余高度 |
| 5 三层完成率（4 列） | 336.0 | **567.7** | stretch；图居中 |
| 6 口令投屏（8 列） | 592.9 | 567.7 | −25.2 |
| 7 异常名单（12 列） | 672.1 | 672.1 | 整排，不变 |
| 8 进步榜（12 列） | 415.2 | 415.2 | 整排，不变 |
| `.bs-grid` 合计 | 3 281.1 | **2 963.8** | −9.7% |
| 整页 scrollHeight | 4 155 | **3 843** | −312 |
| 报头 `.masthead` | 98.6 | 85.0 | 少一行开发者自述 |
| 页脚 `.colophon` | 70.6 | 90.0 | 多了品牌块 |
| `.bs-fine` 合计 | 518.3（6 块） | **28.8（1 块）** | 顶栏那块留着 |
| `.bs-days`（7 天条） | 122.2 | 自然 **72.8** / 渲染 243.2 | 见 §6 顶回 ② |
| `.bs-rows`（3 行） | 136.4 | 96.2 | 行距收紧 + 点线 |
| 两个大数 | 105.6 + 138.4 | 105.6 + 105.6 | 并排 |
| 排内锯齿白 | 885.9 | **0** | stretch |

---

## 5. 截图

`node scripts/shots.mjs` 退出码 **0**，**15 / 15** 张写进 `Document/`，且与 `main` 的 blob
**逐张不同**（`git hash-object` vs `git rev-parse main:Document/shot-*.png`，15 张全异）。
跑前实测两个服务起着、演示库干净（8 个资源行数 60/3/19/60/840/240/5/32、预警全 pending、
class-sessions 8、semesters 2）。

⚠️ `shots.mjs` 本波加了一格**图片就绪门**：`SETTLE` 里多一个
`pendingImages = [...document.images].filter(i => !i.complete).length`，轮询到 0 才截。
理由：`Page.captureScreenshot` 不等图片，只等 `sleep(500)`；本波起报头与登录页各挂一个
`<img>`（52 095 B / 15 975 B 的 svg），一个没到的图片在交付图上是一块空白，而空白看起来像
「品牌没做」、且没有任何守卫会报（§4.1 的谓词只看文本）。15 张全部 `imgs待=0`。
⚠️ 顺手修了该文件里一句**已经撒谎的注释**（「字体要从 Google Fonts 拉，故不能禁网」——
自交付前收尾波 ② 字体自托管之后就是假的）。

---

## 6. 顶回 / 没按派单做的 / 待清扫

### 6.1 顶回（5 处）

**① `backend/app/main.py` 的 `FastAPI(title="体育闭环原型系统")` 没改。**
它是 `/docs` 与 `/openapi.json` 的标题、**用户可见**，是改名清单里唯一漏不掉的一处；
但派单禁改 `backend/app/**` 的生产代码（「若你认为改名需要后端配合，顶回来」）。
故顶回：请控制者裁定是开一个后端小波改它，还是接受 `/docs` 上暂时留着旧名字。

**② 诊断 ② 的「整条高度收紧约 40%」与诊断 ④ 的「同一排等高、不留底部空洞」在第 2 排互相打架。**
概览面板改后 418.7px，7 天条的自然高 253.2px（面板口径）—— 若两条都照字面执行，
要么 7 天条被拉回 ~194px 的绘图带（违反 40%），要么面板底部留 165px 的洞（违反 ④）。
本波按 **④ 优先**：绘图带 `flex: 1 1 auto` 吸收剩余高度（柱跟着长高，投影上更可读），
故**渲染态**的 `.bs-days` 是 243.2px；而「收紧 40%」在**自然高**上成立（122.2 → 72.8 = −40.4%）。
两个数都报在这里，不藏。

**③ 「ⓘ 口径」的位置：派单第一句说「面板右上角」，而它自己的第 4 条说「把 ⓘ 折叠与 caption
钉在底部」。两者只能取一个。** 本波取**底部**（`.bs-cal { margin-block-start: auto }`）：
右上角要么与 `.t-subhead` 的 aside 抢一行（4 个面板的 aside 已经是满的）、要么得绝对定位
（与 §4.1 的重叠守卫对着干）；底部一行 32px、右对齐、`--ink-faint`，读起来像卡片页脚，
且天然满足第 4 条。

**④ 派单说「`#122e66` 在白底上约 10.9:1」—— 实测是 13.06:1。** 方向一致（都过 AA 且余量很大），
只是派单那个数偏低；所有派生色的取值都按 13.06:1 重算，故这一条只影响派单里的估算、不影响结论。

**⑤ 诊断 ② 的机制描述「6 格是『—/无快评』的高列」不精确**：改前 7 格**完全等高**（122.2px，
`day0 == dayOn`），那里**没有柱状图**，是 7 块灰瓷砖。「6 个洞」的观感成立，但改法不是
「把空柱压矮」，而是「先有一张图」。已按后者实现。

### 6.2 没按派单字面做的（4 处，都已在正文交代）

1. spec §13 加了**一段（10 行）**而不是「一句」：因为诚实的记录需要点出旧名字今天仅剩的
   两处代码住址（`main.py` 的 title、`demo.ps1` 的 `.SYNOPSIS`），一句话装不下。
2. `shots.mjs` 加了图片就绪门 + 修了一句撒谎的注释（派单没要求改它）。
3. 登录页卡片里那行 `.auth__kicker`（拉丁副题）**删掉了**：锁排已经印了同一行，
   实测截图上它变成上下相隔 ~400px 的同一句话印两遍。
4. 「本原型」→「本系统」只改了登录页一处；其余 6 处渲染文本（见下）留待清扫，
   因为其中 3 处是错误提示串、改它们属于另一条一致性线。

### 6.3 待清扫（6 条）

1. `backend/app/main.py:174` 的 `FastAPI(title=…)` 旧名字（等控制者裁定，§6.1 ①）。
2. `backend/scripts/demo.ps1:3` `.SYNOPSIS` 里的旧名字（docstring，按派单不改）。
3. 渲染文本里的「本原型」6 处：`views/auth/Bind.vue:111,310,318`、`api/auth.ts:201`、
   `api/client.ts:157`、`components/ApiErrorBanner.vue:101`、`views/student/Home.vue:460`。
4. `/login` 上 `IdentitySwitcher` 的「01 IDENTITY」块排在品牌锁排**之上**（壳的常驻位），
   交付观感上略怪；挪它要动壳的结构，属另一波。
5. 第 1 排分层面板 stretch 后环上下各 ~150px 的居中留白（环写死 200×200，长不了；
   放大它会推翻 `LayerDonut.vue` 里那条「200px 是给图例留 202px」的实测算式）。
6. 没有 favicon：浏览器会请求 `/favicon.ico` 得 404。交付前可把校徽裁一个 `.ico`/`.png` 进去。

---

## 7. 最终验收

| 项 | 结果 |
|---|---|
| `npm run build` | 退出码 **0**；**138 modules**（基线 129）；`index-*.css` **65.20 kB**（基线 62.79）、`index-*.js` **167.03 kB**（基线 165.70）；两个 svg 作为资产单独发出（52.09 / 15.97 kB） |
| `npm run check:tokens` | **绿**，扫描面 **35** 个文件（基线 33），tokens.css 之外 0 处色值 |
| `npm run check:dist` | **绿**（adoptFromUrl 0 次、两个 Google Fonts 域各 0 次、woff2 恰好 4 个、三个正控都在） |
| `npm run smoke` | **18 步 / 499 断言 / 退出码 0**（与基线同数）；第 14 步 109/109 全绿 |
| §4.1 重叠 / 溢出 | 15 条路由 **0 / 0**（smoke 第 14 步）；另用同一谓词单跑 8 条路由打印 0/0，**展开态**（5 个 ⓘ 全开）也 0/0 |
| `@ts-ignore` / `as any` | 扫 51 个 `.ts/.vue/.css`，**0 处** |
| 新增依赖 | **0**（`dependencies` 与 `devDependencies` 与 `main` 逐字相同；`scripts` 无增删） |
| 后端测试 | **1340 passed**（134.8s）；`app/domain` 覆盖率 **1268 / 0 / 376 / 0 / 100%**（与基线逐字相同） |
| 四个指纹 | `national_standard_2014.csv` / `exercises.yaml` / `equivalence.yaml` / `alert_rules.yaml` 四条 `*_fingerprint_is_pinned` **全 PASSED** |
| 18 模板指纹 | `tests/domain/test_prescription_templates.py::test_template_yaml_fingerprints_are_pinned` **PASSED**（同文件 `test_all_eighteen_share_the_same_review_and_version_block` 亦 PASSED） |
| `backend/pe.db` | 存在 = **False** |
| `backend/data/seed/` | **0** 个文件 |
| spec | **205 466 B / 1 675 行（\n 计数；编辑器口径 1 676）/ 纯 CRLF / 无 BOM / sha256[:16] `A4C072354CA82AA5`** |
| demo.ps1 | **19 563 B / 纯 CRLF 267/267 / 带 BOM / sha256[:16] `A075D2F0871DF37A`** |
| 截图 | 15 / 15 更新，与 `main` 逐张不同 |
| 报告自身 | 字节数与入库 blob 一致（见 commit ④ 之后的 `git cat-file -s` 复核） |

⚠️ 跑完 smoke 之后演示库**已被写脏**（它自己会打印这件事）；15 张截图是在**脏之前**拍的。
下一次要重拍请先重跑 `backend/scripts/demo.ps1`。
