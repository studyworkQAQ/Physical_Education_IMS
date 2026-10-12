# 交付前收尾波 · 实现者报告

> 分支 `harden/fonts-and-overlaps`（自 `main` @ `48b45da` 起）·  2026-10-12
> 四件：① `smoke.mjs` 第 14 步的布局重叠红（根因 + 修）② 字体自托管 ③ 关掉
> `GET /api/mini-tests/normalized` 的匿名门 ④ 两条便宜的待清扫。
> **结论：四件全做完，`smoke.mjs` 18/18 全绿 / 499 断言 / 退出码 0，后端 1340 passed，
> 零新增依赖，禁区一个字节没动。顶回 10 处（其中 3 处 Critical）。**

---

## ① 环境

开工第一件事（硬规矩 #73），逐字实测：

| 项 | 实测 | 派单给的 |
|---|---|---|
| Node | `v24.19.0` | v24.19.0 ✓ |
| npm | `11.17.0` | 11.17.0 ✓ |
| FastAPI / SQLAlchemy | `0.141.1` / `2.1.3` | 同 ✓ |
| Python | 3.11.1（无 venv，`C:\Python`） | 同 ✓ |

* 仓库：`git status --short` 开工时**空**，`HEAD = 48b45da3f865322127032933cf1706c8e4fd32a7`。
* 分支：`git checkout -b harden/fonts-and-overlaps` 成功，全程**没有 push、没有碰 main**。
* 服务：`Get-NetTCPConnection -LocalPort 8000,5173 -State Listen` 开工时两个都在
  （`127.0.0.1:8000` = uvicorn、`::1:5173` = vite）。改了后端之后**重灌并重启了两次**
  （`backend\scripts\demo.ps1 -Port 8000`），每次跑 `smoke.mjs` 之前都是一份刚复原的演示库。
* 无头浏览器：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  （`smoke.mjs` 的 `spawnHeadless()` 候选表里第一个命中的），`--headless=new`
  `--force-prefers-reduced-motion` `--remote-debugging-port=0`，CDP 走 Node 24 自带的全局 `WebSocket`。
* 外网：派单说「间歇性不可达」。**本波全程实测可达**（Google Fonts 的 CSS 与
  `fonts.gstatic.com` 的 woff2 各下载成功，无一次重试）。⚠️ 这一点很关键：
  它让「自托管」这条主路走通了，于是派单 §2.2 那条「保留 CDN + 度量对齐」的退路
  **不需要动用** —— 但我把它实现成了**无论自托管成功与否都生效**的兜底（见 §3 的第三件事）。
* 探针一律放 `$env:TEMP`（4 个：`pe-overlap-probe.mjs` / `pe-font-metrics.mjs` /
  `pe-normalized-probe*.py` / `pe-demo-hints.py` / `pe-accept-probe.py` / `pe-eol*.py` /
  `pe-commit.py`），写完先 `py_compile`，收工时删掉。工作树里**没有**留下任何探针。

---

## ② 第 ① 件：那几条布局重叠红的根因

### 2.0 ⚠️ 先顶回基线：不是 3 红，是 **4 红**

派单逐字写「487 绿 + 3 红」，红在 `s-home` / `s-weekly-sheet` / `s-check-in`。
**开工第一件事就是原样跑一次 `node frontend/scripts/smoke.mjs`，实测：**

```
步数 17/18 全绿 · 断言 486 绿 / 4 红
第 14 步 · 105/109 条断言
  ✗ s-home          → 1 处
  ✗ s-weekly-sheet  → 7 处
  ✗ s-check-in      → 1 处
  ✗ s-rpe           → 2 处      ← ⚠️ 派单没点这一条
```

`退出码 = 1`。故基线是 **4 红 / 11 处重叠 / 4 条路由**，不是 3 红。
`s-rpe` 那两处的原文（逐字抄自那一跑的输出）：

```
[{"a":"span「5」","b":"span「适中」","aRect":[134,1794,17,40],"bRect":[132,1828,20,15],"ratio":0.331},
 {"a":"span「10」","b":"span「力竭极限」","aRect":[201,1926,33,40],"bRect":[198,1960,40,15],"ratio":0.33}]
```

另三处的原文（与派单说的「同 aRect/bRect/ratio」核对：`s-home` 与 `s-check-in` 逐字相同，
`s-weekly-sheet` 的 7 处逐字相同）：

```
s-home          span「本周训练量 · 分钟」[33,890,106,17]  vs span「108.0」[33,901,132,71]   ratio 0.342
s-check-in      span「本周打卡完成率」  [33,965,91,17]   vs span「100.0」[33,976,132,71]  ratio 0.342
s-weekly-sheet  span「06」[42,1148,22,26] vs span「速度柔韧」[41,1170,24,17] ratio 0.218   （06..12 共 7 处，ratio 全是 0.218）
```

⚠️ 而**最坏情况比这更宽**：下面的实验 A 实测出 **6 条路由 / 15 处**
（多出来的是 `t-dashboard` 1 处、`t-report` 2 处、`admin-index` 1 处）。
`smoke.mjs` 那一跑没报它们，只因为跑到那几条时 webfont 已经就位了
（学生端那 6 条排在 15 条路由的前面）。**故「3 红」与「18/18 全绿」两次矛盾观察
都不是这个失效的全貌，它是一个随时间变化的竞态。**

### 2.1 对照实验（三组，改前）

探针：`$env:TEMP\pe-overlap-probe.mjs`（临时、不入库）。它复用 `smoke.mjs` 的姿势
——同一个 `spawnHeadless()` 参数、同一个 `LAYOUT_PROBE` 谓词（逐字同源）、
同一套 `Network.setCookie` + `Emulation.setDeviceMetricsOverride` + 轮询 needle。
挡字体用 `Network.setBlockedURLs`。除了重叠数，它还报两样东西：

1. `document.fonts` 的面数与就位数、`document.fonts.status`；
2. **度量探针**：往页面上塞一个 `font-size:100px; line-height:1` 的隐藏 span，
   用 `Range.getClientRects()` 量它的 content-area 高度 → 直接读出「实际生效字体的
   ascent+descent 比 R」。

三组的原始输出（每组 11 条路由；下面只摘每组的度量行与合计）：

**实验 B（放行字体 + 等 `document.fonts.ready`）**
```
[allow] s-home: 叶子 111 重叠 0 | fontStatus=loaded faces=335(loaded 43) HG=true Noto=true JBM=true
      度量(100px content-area 高)：栈=130 HG700=130 HG800=130 Noto=145 YaHei=132 SimSun=100
…（11 条路由全部 faces=335 / 栈=130 / 重叠 0）
[allow] 合计重叠 0 处
```

**实验 A（挡掉 `fonts.googleapis.com` + `fonts.gstatic.com`）**
```
[block] s-home: 叶子 111 重叠 1 | fontStatus=loaded faces=0(loaded 0) HG=true/true/true Noto=true JBM=true
      度量(100px content-area 高)：栈=145 HG700=145 HG800=145 Noto=145 YaHei=132 SimSun=100
      span「本周训练量 · 分钟」 [33,890,111,17] fs=12px lh=19.2px cls=stat__label caps
   vs span「108.0」 [33,901,133,71] fs=48.75px lh=50.7px cls=stat__value num--hero stat__value--hero
      ratio=0.342
[block] s-weekly-sheet: 叶子 241 重叠 7 | faces=0
      span「06」 [42,1147,21,26] fs=18px lh=18px cls=strip__d num
   vs span「速度柔韧」 [41,1169,24,17] fs=12px lh=13.8px cls=strip__tag
      ratio=0.208            （06/07/08/09/10/11/12 共 7 处，ratio 全是 0.208）
[block] s-check-in: 叶子 228 重叠 1 | faces=0      ratio=0.342（同 s-home 的形状）
[block] s-rpe: 叶子 150 重叠 2 | faces=0
      span「5」 [134,1797,17,40] fs=28px lh=28px cls=step__n num
   vs span「适中」 [132,1831,20,15] fs=10px lh=12px cls=step__zh     ratio=0.331
      span「10」 [201,1929,33,40] fs=28px lh=28px vs span「力竭极限」 [198,1963,40,15]  ratio=0.33
[block] t-dashboard: 叶子 320 重叠 1 | faces=0        ← ⚠️ smoke 那一跑没报
      span「人均课堂 RPE」 [41,1761,123,26] fs=18px lh=28.8px
   vs span「6.37」 [41,1781,115,81] fs=56px lh=58.24px cls=stat__value num stat__value--display
      ratio=0.223
[block] t-report: 叶子 288 重叠 2 | faces=0           ← ⚠️ 同上
      span「本周人均」 [518,883,52,17] fs=12px lh=19.2px vs span「6.37」 [518,894,99,70] fs=48px lh=49.92px  ratio=0.342
      span「10 月 12 日」 [875,1079,29,17] fs=12px lh=15px vs span「6.4」 [875,1091,36,35] fs=24px lh=24.96px ratio=0.294
[block] admin-index: 叶子 231 重叠 1 | faces=0        ← ⚠️ 同上
      h2「资源目录」 [24,372,192,70] fs=48px lh=60px cls=zh-title a-head__title
   vs p「/admin · 23 resource」 [24,437,138,19] fs=13px lh=20.8px cls=a-head__path data
      ratio=0.263
[block] 合计重叠 15 处
```

**实验 C（放行字体，但**不等** swap —— 即 `smoke.mjs` 今天的姿势）**
```
[allow/nowait] s-home: 叶子 111 重叠 1 | fontStatus=loading faces=335(loaded 2) HG=false/false/false
      度量：栈=145 HG700=145 …
      span「本周训练量 · 分钟」 [33,890,106,17] vs span「108.0」 [33,901,132,71]  ratio=0.342
[allow/nowait] s-weekly-sheet: 重叠 0 | fontStatus=loaded faces=335(loaded 46) 栈=130
…（其余 9 条 0 处）
[allow/nowait] 合计重叠 1 处
```

### 2.2 字体度量（canvas 的 `fontBoundingBoxAscent/Descent`，100px 字号）

探针 `$env:TEMP\pe-font-metrics.mjs`，在一个真的加载了 CDN 字体的页面上量：

| 字体 | ascent | descent | **R = content-area / em** |
|---|---|---|---|
| **Hanken Grotesk**（webfont，400 与 700 同值） | 100 | 30 | **1.30** |
| **JetBrains Mono**（webfont） | 116 | 29 | **1.45** |
| **Noto Sans SC**（本机装了它） | 116 | 29 | **1.45** |
| Microsoft YaHei（700 / 400） | 106 | 26 | 1.32 |
| Segoe UI | 108 | 25 | 1.33 |
| Consolas / Cascadia Mono / Arial | 92/25 · 93/23 · 91/21 | | 1.17 / 1.16 / 1.12 |
| SimSun / SimHei | 86 | 14 | 1.00 |
| 泛型 `sans-serif`（本机） | 116 | 29 | 1.45 |

⚠️ **两个取证陷阱，都踩过并记下来**：

1. **`document.fonts.check()` 在无 `@font-face` 时恒真**（实验 A 里 `faces=0` 而
   `HG=true/true/true`）—— 它的语义是「不需要额外的面就能渲染」，于是「一款面都没有」
   恰好让它返回 `true`。**它不能当「字体加载了」的判据**（硬规矩 #107 的同一族）。
   本波改用的判据是 `document.fonts.size`（335 ↔ 5 ↔ 0）与上面的度量探针。
2. 「PingFang SC(缺)」「Source Han Sans SC(缺)」两行量出来也是 **1.45**，
   与 Noto Sans SC 逐字相同 —— 那不是巧合：**本机装了 Noto Sans SC**，
   而改前 `--font-ui` 的第二位就是它。故实验 A 里顶上来的是**本机的 Noto Sans SC**
   （1.45），不是 Microsoft YaHei（1.32）。⚠️ 换句话说「回退到哪一款」是**逐机器**的，
   这正是「布局不得取决于哪一款字体在用」这条要求的实证依据。

### 2.3 根因结论

**控制者的假设成立，但只成立一半 —— 它是「字体度量」，而不只是「CDN 不可达」。**

机制（逐字）：`Range.getClientRects()` 量到的行内文本盒高 = 字体的 **content-area**
（`ascent + descent`），**与 `line-height` 无关**。当 `line-height` < R 时，行内盒会
**上下各溢出 `(R − lh) / 2 × font-size`**，压进相邻行的文本盒；
`smoke.mjs` 第 14 步 §4.1 的谓词（交集 > 较小者的 20%）于是报红。

代入实测数字（`s-home` 的那一对，改前）：

```
.num--hero   fs = 48.75px（= clamp(48px, 13vw, 88px) 在 375px 视口上）
             lh = var(--lh-tight) = 1.04 → 行盒 50.70px
  R = 1.30（HG 就位）  → content-area 63.4px → 上溢 (63.4−50.7)/2 = 6.35px
  R = 1.45（回退）     → content-area 70.7px → 上溢 (70.7−50.7)/2 = 10.0px
.stat 的 flex gap = var(--space-1) = 4px，标签那一行自己不外溢（12px × 1.45 = 17.4 < lh 19.2）
  → 交集高 = 上溢 − gap = 6.35 − 4 = 2.35px（HG 就位）  /  10.0 − 4 = 6.0px（回退）
  → ratio = 111 × 2.35 / (111 × 17) = 0.138（**过**，但只剩 0.062 的余量）
          = 111 × 6.0  / (111 × 17) = 0.353（**红**；实测 0.342，差在取整与 x 方向）
```

⚠️ 于是「HG 就位时绿」不是因为它安全，而是因为**它离阈值只有 0.062**。
这也解释了两次矛盾的观察：**同一个失效，量取那一刻字体在不在位决定它是红是绿**
—— 冷缓存 / CDN 被挡 / swap 还没发生 → 红；命中缓存 → 绿。
实验 C 单独复现了「网络通也照样红」那一支（`fontStatus=loading`、335 个面里只就位 2 个），
故它**不只是**网络问题，**是一个竞态**。而 `s-weekly-sheet` 那 7 处的
`ratio = 0.208` 离阈值 0.2 只差 **0.008** —— 改前最险的一格。

### 2.4 修法

⚠️ **没有**动重叠阈值（20% 逐字保留），也**没有**动 §4.1 的谓词一个字
（硬规矩 #92：守卫要能抓真失效；把阈值调高是把守卫调钝）。
修的是布局的**度量余量**，两层，各自独立成立：

**第一层 · 行高下界（commit `1342c68`）**

| 令牌 / 选择器 | 改前 | 改后 | 为什么是这个值 |
|---|---|---|---|
| `--lh-tight`（`tokens.css`） | `1.04` | **`1.3`** | 1.3 = Hanken Grotesk 自己的 R → **溢出恒为 0** |
| `--lh-heading`（`tokens.css`） | `1.25` | **`1.3`** | 同上；`.zh-title` 在 48px 下改前溢出 4.8px |
| `.strip__d`（`WeeklySheet.vue`） | `line-height: 1` | `var(--lh-tight)` | fs 18px，改前上下各溢出 4.05px |
| `.strip__tag`（`WeeklySheet.vue`） | `line-height: 1.15` | `var(--lh-tight)` | fs 12px，改前溢出 1.8px |
| `.step__n`（`RpeEntry.vue`） | `line-height: 1` | `var(--lh-tight)` | fs 28px，改前上下各溢出 6.3px |
| `.step__zh`（`RpeEntry.vue`） | `line-height: 1.2` | `var(--lh-tight)` | fs 10px |

四处 `.vue` 一律改走 `var(--lh-tight)` 而不是写死数字 —— **单一所有者**在
`tokens.css`，那一格的注释里写着完整的算式与三组实验的指针。
⚠️ 另有 6 处 `line-height: 1 / 1.2 / 1.25`（`SectionHead.vue`、`StudentNav.vue`、
`TeacherNav.vue`、`admin.css:148` 的固定尺寸序号块、`ClassReport.vue:773`、
`RpeEntry.vue:636`）**刻意没动**：它们在最坏例实验里也是 0 重叠（邻居够远 / 在固定尺寸盒里），
改它们是无证据的视觉扰动。判据是实验，不是「把所有小于 1.3 的行高一律抬上去」。

**第二层 · 让 R 恒定（commit `0219006`，详见 §3）**：自托管 + 度量对齐的回退面，
把 `--font-ui` 那一栈的 R **钉死在 1.30**，与「哪一款字体在用」无关。
于是 `lh = 1.3` 时溢出恒为 0，**布局几何不再有第二个自由度**。

### 2.5 修后实测（四组 × 15 条路由）

| 实验 | woff2 | 度量 override | `document.fonts.size` | 栈的 content-area @100px | **重叠** |
|---|---|---|---|---|---|
| B `allow` + 等 `fonts.ready` | 放行 | 在 | 5（就位 2–3） | **130** | **0 处 / 15 路由** |
| C `allow` + **不等** swap | 放行 | 在 | 5 | **130** | **0 处 / 15 路由** |
| A `block`（`*.woff2*` + CDN 四个域全挡） | **挡** | 在 | 5（就位 1） | **130**（而 `HG700` 已是 **145**） | **0 处 / 15 路由** |
| **WORST** = A + 强拆 override（注入一个无 override 的 1.45em 面当 `--font-ui`） | **挡** | **拆掉** | 6 | **145** | **0 处 / 15 路由** |

⚠️ 第三行是本波最有用的一格读数：woff2 被挡掉之后 `HG700` 的 content-area 变成 **145**
（Hanken Grotesk 真的不可达了），而 `--font-ui` 那一栈仍然是 **130** ——
**度量对齐的回退面在承重**。
⚠️ 第四行（WORST）证明**第一层自己也站得住**：把 override 拆掉、R 回到 1.45，
15 条路由仍然 0 重叠。故两层是**互为冗余**的，不是「一层遮住了另一层的失效」。

`smoke.mjs` 第 14 步：**105/109 → 109/109**，15 条路由的 `布局守卫` 一行行都是
`重叠 0 处、非故意横向溢出 0 处`（原文见 §7）。

---

## ③ 第 ② 件：字体自托管

### 3.1 自托管成功了吗 —— **成功了，主路走通，退路没动用（但实现了）**

外网本波全程可达，woff2 一次下成、零重试。

⚠️ **一个实测出来的坑（顶回 6）**：派单说「下载 400/500/600/700/800 里实际用到的字重」。
先 `Grep` 数了一遍：`--fw-400…800` 五档**全部**有消费者（`--fw-800` 只在
`base.css` 的 `.num--hero` 一处，其余四档在 28 个文件里 89 处），故五档都要。
**但下载下来发现 5 档指向逐字相同的同一个 woff2**：向
`css2?family=Hanken+Grotesk:wght@400;500;600;700;800` 要 CSS，Google 回 **20 个**
`@font-face`（5 档 × 4 个 subset），而同一 subset 的 5 档 `src` 是**同一个 URL**
—— 那一个文件是带 `wght` 轴的**可变字体**。JetBrains Mono 同形（400 与 700 同一个文件）。
本波第一版照派单做，下了 **14 个文件**，`sha256` 一量只有 **4 个唯一**
（10 个是副本，白下 3.5 倍字节）。故最终按可变字体声明：一档字重区间一个 `@font-face`。

### 3.2 woff2 清单（`frontend/src/assets/fonts/`，全部入库）

| 文件 | 字节 | sha256 前 16 位 | 上游 |
|---|---|---|---|
| `hanken-grotesk-var-latin.woff2` | **34 704** | `E9201EDDF1D41D0B` | `fonts.gstatic.com/s/hankengrotesk/v12/…pd59A.woff2` |
| `hanken-grotesk-var-latin-ext.woff2` | **19 588** | `768AF2923E0AB154` | 同族 `…T59CjCQ.woff2` |
| `jetbrains-mono-var-latin.woff2` | **31 432** | `83C005D49D8A6A50` | `fonts.gstatic.com/s/jetbrainsmono/v24/…Px7cwhsk.woff2` |
| `jetbrains-mono-var-latin-ext.woff2` | **11 624** | `DB5FF4DB83E58042` | 同族 `…PxDcwg.woff2` |
| **合计** | **97 348** | | 4 个文件 |

四个都以 `wOF2` 开头（下下来当场核过魔数）。
`unicode-range` 逐字抄自 Google 的 CSS（`latin` 与 `latin-ext` 各一份），
故 `latin-ext` 那两份是**零运行时成本**的保险：带 `unicode-range` 的分片，
浏览器只在页面上真的出现那个区间的字符时才去下载它。

⚠️ **入库字节数 == 磁盘字节数**（派单点名要核的一格，`git cat-file -s` 实测）：

```
hanken-grotesk-var-latin.woff2         disk= 34704 blob= 34704 equal=True sha_disk=E9201EDDF1D41D0B sha_blob=E9201EDDF1D41D0B same=True
hanken-grotesk-var-latin-ext.woff2     disk= 19588 blob= 19588 equal=True sha_disk=768AF2923E0AB154 sha_blob=768AF2923E0AB154 same=True
jetbrains-mono-var-latin.woff2         disk= 31432 blob= 31432 equal=True sha_disk=83C005D49D8A6A50 sha_blob=83C005D49D8A6A50 same=True
jetbrains-mono-var-latin-ext.woff2     disk= 11624 blob= 11624 equal=True sha_disk=DB5FF4DB83E58042 sha_blob=DB5FF4DB83E58042 same=True
git ls-files --eol → i/-text w/-text attr/-text   （四个都是，即双向零转换）
git check-attr binary → binary: set / text: unset
```

为此在 `.gitattributes` 末尾加了 `*.woff2 binary`（+15 行注释）。
理由：`core.autocrlf` 本机实测是 `true`，而 git 判「是不是文本」是**启发式**的
（前 8000 字节有没有 NUL）—— woff2 是 brotli 压缩流，命中 NUL 的概率很高、
但那是**概率**、不是保证；一旦某个分片碰巧不含 NUL 就会被当文本做 LF→CRLF 转换，
那个文件**再也解不开**（woff2 的头里写着原文长度与压缩流长度）。
本仓已为「按字节哈希的东西随平台配置漂移」付过一次代价（`.gitattributes` 里
`backend/data/` 那一段记着 21412 字节 LF ↔ 21915 字节 CRLF），故不赌启发式。
⚠️ 另核过 `.gitignore`：**没有任何规则忽略 `*.woff2`**（根上那份、`frontend/.gitignore`
那份都逐行看过），故不需要加否定式规则。

### 3.3 `index.html` 改了什么

删掉三行（两条 `preconnect` + 一条 `stylesheet`）：

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" />
```

`<head>` 里换成一段**短**注释指向 `src/styles/fonts.css`。
⚠️ 注释是**短**的，这一格是实测逼出来的（顶回 9）：第一版我把完整的取证表写进了
`index.html` 的注释，结果 `check:dist` 首跑**两条红**（`dist/index.html ×2`）——
**Vite 不剥 HTML 注释**（CSS 的它剥），于是那段注释原样进了产物、也原样发到客户端。
处置有两条，**两条都做了**：① 把 `check-dist` 的谓词做准（产物侧也剥块注释，
与源码侧用同一个 `stripComments`，并加 3 拍自校证明它「保住真引用、吃掉提及」）；
② 把 `index.html` 的注释收成 11 行指针，完整取证搬进 `fonts.css` 的文件头
（CSS 注释会被压缩器剥掉 → 写在那里是**零成本**的）。
`index.html` 因此从 2214 B 降到 **1833 B**。

`src/main.ts`：`import './styles/fonts.css'` 加在 `tokens.css` **之前**
（六个样式文件的顺序注释同步改写：「字体面 → 令牌 → 基础 → 三套布局」）。

`src/styles/tokens.css`：
```css
--font-ui:
  'Hanken Grotesk', 'Hanken Grotesk Fallback', 'PingFang SC', 'Hiragino Sans GB',
  'Microsoft YaHei', 'Source Han Sans SC', sans-serif;
--font-data: （与 --font-ui 逐字相同，改前也相同）
--font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace;  ← 一字未动
```

⚠️ **`Noto Sans SC` 从栈里摘掉了**（这就是「中文走系统栈」的落地）。
新文件 `src/styles/fonts.css`（11 532 B / 160 行 CRLF）是 `@font-face` 的**唯一住址**：
4 个自托管面（`font-weight: 400 800` / `400 700` 的区间声明）+ **1 个度量对齐的回退面**。

### 3.4 度量对齐的回退面（派单 §2.2 那条退路，实现成**永远生效**的兜底）

```css
@font-face {
  font-family: 'Hanken Grotesk Fallback';
  font-style: normal;
  font-weight: 400 800;
  src: local('PingFang SC'), local('Hiragino Sans GB'), local('Microsoft YaHei'),
    local('Source Han Sans SC'), local('Noto Sans CJK SC');
  size-adjust: 100%;
  ascent-override: 100%;
  descent-override: 30%;
  line-gap-override: 0%;
}
```

* 三个 override 的值**不是估的**：canvas 实测 Hanken Grotesk 的
  `fontBoundingBoxAscent = 100`、`fontBoundingBoxDescent = 30`（100px 字号）→ R = 1.30。
* `line-gap-override: 0%` 同样承重：不少系统中文字体带非零 line gap，不钉成 0 的话替身仍会偏高。
* `size-adjust: 100%`（= 不缩放字形）是**有意**的：缩放能顺带对齐字宽，但它是**一个数**、
  对不齐两档字重（Microsoft YaHei 的数字宽度 400 是 58.64、700 是 61.67，
  而 Hanken Grotesk 两档都是 56），硬凑一档会让另一档更歪。
  实测横向也没有代价：挡字体时整页 `scrollWidth` 360 / `innerWidth` 375、
  非故意横向溢出 **0 处**。
* `local()` 五个候选**都不在**时这一个面加载失败 → `--font-ui` 继续往后走它自己那条
  系统栈。故这一格只会**改善**最坏情况，不会让任何一台机器比改前更差。
* ⚠️ 它的价值由 §2.5 的第三行实测钉住：挡掉 woff2 后 `HG700 = 145` 而 **栈 = 130**。

### 3.5 产物里还有没有 `fonts.googleapis.com` —— **0 次**

新守卫**并入 `scripts/check-dist.mjs`**（派单给的两个选项里选了这个：它与既有的
「产物里不得留 `adoptFromUrl`」是同一个形状 —— 「一个串在 `dist/` 里出现 0 次」，
共用同一次构建与同一个 `walk()`，不另起一个脚本）。

怎么跑：
```
cd frontend
npm run check:dist                              # dist/ 不在时先自己跑一次 npm run build
node scripts/check-dist.mjs --no-build          # 只扫已有的 dist/
node scripts/check-dist.mjs --build             # 强制重建再扫
```
`smoke.mjs` 第 15 步会 `spawn` 它一次（8/8 仍绿）。实测输出（最后一跑）：

```
  ✓ dist/ 里 adoptFromUrl 出现 0 次（它必须被 Rollup 摇掉）  →  0 次
   -- 字体自托管（交付前收尾波 ②）--
     assets\hanken-grotesk-var-latin-CaVRRdDk.woff2  33.89 kB
     assets\hanken-grotesk-var-latin-ext-Dg-wlmqe.woff2  19.13 kB
     assets\jetbrains-mono-var-latin-6fWv1k7M.woff2  30.70 kB
     assets\jetbrains-mono-var-latin-ext-DIC32ArD.woff2  11.35 kB
  ✓ dist/ 里自托管的 woff2 恰好 4 个（latin + latin-ext × 两个族）  →  4 个 / 97348 bytes
  ✓ dist/ 里确实有 "Hanken Grotesk"（否则上面那几条「0 次」是空转）  →  7 次
  ✓ dist/ 里确实有 "Hanken Grotesk Fallback"（…）  →  3 次
  ✓ dist/ 里确实有 "ascent-override"（…）  →  1 次
  ✓ dist/ 里 fonts.googleapis.com 出现 0 次（字体已自托管，运行时不发跨域请求）  →  0 次
  ✓ dist/ 里 fonts.gstatic.com 出现 0 次（…）  →  0 次
  ✓ 自校 ①：剥注释之后一个**真引用**仍然被数到（谓词没把 `https://` 吃掉）  →  1 次（应为 1）
  ✓ 自校 ②：剥注释之后一句 HTML **提及**不再被数到  →  0 / 0 次（应为 0 / 0）
  ✓ 自校 ③：剥注释之后一句 CSS **提及**也不再被数到  →  0 次（应为 0）
  ✓ 源码里 fonts.googleapis.com / fonts.gstatic.com 也是 0 次（剥块注释后扫了 22 个文件）  →  0 次
  ✓ 而它确实扫到了东西（≥ 20 个文件 / ≥ 100 kB，否则上面那条又是空转）  →  22 个 / 607240 字符
✓ 全绿：… （三条谓词都不是空的）            退出码 0
```

反空转一共 **5 拍**（硬规矩 #50）：woff2 恰好 4 个、`Hanken Grotesk` /
`Hanken Grotesk Fallback` / `ascent-override` 各 ≥ 1 次、剥注释谓词的 3 拍自校。
⚠️ 其中 `ascent-override` 那一拍是**实测出来的风险**、不是想出来的：
压缩器完全可能吃掉一个它不认识的 `@font-face` 描述符，而那一格正是
「挡住字体也不许重叠」的实现。实测 esbuild **没有**吃掉它（1 次）。
⚠️ 而 `stripComments` **刻意不剥 `//` 行注释**：`https://` 里就有一个 `//`，
剥行注释会把一个真引用从冒号之后整段吃掉 —— 那才是真正的假绿（自校 ① 钉的就是它）。

`npm run check:tokens` 仍然全绿，⚠️ **`@font-face` 的 `url(...)` 没有触发它**
（派单担心的那一格，实测不成立）：它扫的是 hex 与 `rgb(`/`hsl(`，
而 `fonts.css` 里一个色值字面量都没有。扫描面 **32 → 33** 个文件（多了 `fonts.css`），
offender 仍是 **0**，退出码 0。

### 3.6 中文走系统栈

按控制者的裁定做，**没有顶回**（实测支持它）：Noto Sans SC 的中文全量约 8–10 MB、
Google 把它切成约 100 个 `unicode-range` 分片（改前 `document.fonts.size` 实测 **335**，
改后 **5**），「只下用到的分片」在静态构建里做不到；而任何中文环境都必然带一款系统黑体。
落地是两处：`tokens.css` 的 `--font-ui` / `--font-data` 里
`'Noto Sans SC'` → `'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Source Han Sans SC', sans-serif`，
以及回退面的 `local()` 候选列表（同一条栈）。
⚠️ **附带的好处正是 §2 那个失效的根治**：中文不再有「加载中」这个状态。
⚠️ 代价如实记：中文的**字形**从此逐 OS 而异（Windows 雅黑 / macOS 苹方），
「视觉一致性」这件事在中文这一侧没有单一所有者了（登记为待清扫 2）。

⚠️ **顶回 2**：派单说「两款字体」，而 `index.html` 实际拉的是**三款** ——
还有 `JetBrains Mono 400/700`。它在 `--font-mono` 上有 **8 处**消费者
（`base.css` 1 / `admin.css` 5 / `teacher.css` 1 / `ApiErrorBanner.vue` 1），
用在口令输入框与错误 code / JSON 原文上。**要「产物里不含 CDN」就必须一起处置它**，
故一并自托管（2 个 woff2、43 056 B），而不是把它掉到 Consolas。

**零新增依赖**：woff2 是静态文件，`package.json` / `package-lock.json` /
`backend/requirements.txt` 三者 `git diff 48b45da` **全空**（实测）。
⚠️ 特别是**没有**引 `@fontsource/*`（派单点名要先顶回才能引的那一族）。

---

## ④ 第 ③ 件：`GET /api/mini-tests/normalized` 的匿名门

### 4.1 响应字段实测（派单点名要核的那一格）

演示库上 `semester_id=2` 有三个有小测的周次：`(2,2) (2,4) (2,6)`。取 `week=2`
（5 个 section、`scored_count` 30/30/20/20/20、`unassigned` 空）实测：

```
顶层键:            ['sections', 'semester_id', 'unassigned', 'week']
section 键:        ['course_section_id', 'entries', 'scored_count']
entry 键:          ['composite', 'mini_test_id', 'shuttle_score', 'squat_score', 'student_id']
entry 样本:        {"student_id": 1, "mini_test_id": 1, "squat_score": 39.0,
                    "shuttle_score": 25.0, "composite": 32.0}
entry 里出现原始列名（shuttle_20m_s / squat_30s_count / item_combo / tested_on）的次数: 0
```

**逐行对账**（`normalized` 的教职档 ↔ `GET /api/mini-tests` 的原始列，120 行）：

```
squat_score == squat_30s_count：相同 120 行 / 不同 0 行 / 名册缺 0 行
样本 (student_id, squat_score, squat_30s_count, shuttle_20m_s, shuttle_score, composite):
   (1,  39.0, 39, 40.5, 25.0,  32.0)
   (3,  18.0, 18, 41.4, 18.33, 18.17)
   (7,  22.0, 22, 36.4, 41.67, 31.83)
   (11, 20.0, 20, 30.0, 85.0,  52.5)
composite 与 shuttle_score 同时非空的行数: 120（→ squat 可被逐行反推）
```

**结论（逐字回答派单的问题）**：

| 派单点名的原始值 | 在不在响应里 |
|---|---|
| `shuttle_20m_s` | **不在**（只有换算后的百分位 `shuttle_score`） |
| `squat_30s_count` | ⚠️ **在** —— 以 `squat_score` 这个名字，**逐行相等**（120/120） |

⚠️ 而且不止一格：`composite = (squat_score + shuttle_score) / 2`，
故 `squat = 2 × composite − shuttle_score` **可逐行反推**（120 行两格都非空）。
**只摘 `squat_score` 一格等于没摘。**

对照实测（同一份取证里一并做的）：

```
匿名 GET /api/mini-tests/normalized            → 422（缺参数）  ← 派单说的那一格，复核为真
匿名 GET /api/mini-tests/normalized?…&week=6   → 200            ← 门是开的
匿名 GET /api/mini-tests?limit=5               → 401
匿名 GET /api/enrollments?limit=5              → 401
匿名 GET /api/students?limit=5                 → 401
学生 GET /api/mini-tests?limit=200             → 200，items=3，其中不是自己的 = 0
学生/教师/管理员 GET normalized                → 200 / 200 / 200，学生档与管理员档**逐字相同**
```

⚠️ 于是「Plan 04 摘掉教师头」当年靠的那张对账表（「它回的每一格都是匿名
`GET /api/mini-tests` + `GET /api/enrollments` 已经给出去的东西的纯函数」），
**两条腿都被安全收紧波抽掉了** —— 而 `normalized` 仍然匿名，
它于是从「不新增泄漏面」变成**本仓最后一个匿名的学生键读端点**。

### 4.2 ⚠️ 顶回（Critical）：改成了什么身份

派单的裁定是「挂任意已登录身份、**不做自过滤**」，并附了证伪条件：
「若含原始值（`squat_30s_count` / `shuttle_20m_s`），**顶回来**」。**条件触发了。**

派单给的另一条路是「教职-only + 学生页降级」。**本波两条都没照抄，取了中间**，
判据是控制者自己写下的那条风险排序（「百分位换算结果」比「原始体测值」弱一档）：

1. **挂 `Security(STUDENT_ID_SCHEME)` + `Security(TEACHER_STAFF_NO_SCHEME)`（OR 语义）
   + `Depends(current_reader)`** → 匿名 **401**、学生 200、教职 200。
   ⚠️ `current_reader` 是安全收紧波已经建好的三档身份依赖（`app/api/deps.py:444`），
   返回值语义是「学生 → `student.id`；教职 → `None`；匿名 → 当场 401」，
   故**不需要碰 `app/api/deps.py`**（派单的允许清单里没有它）。
2. **学生档列级收窄**（`reader is not None` 那一支，9 行代码）：别人的行
   `squat_score` / `composite` 置 `None`，本人的照常给；`unassigned` 只留本人。
3. **全班的 `shuttle_score` 刻意不动** —— 学生端要靠它算「比自己慢的人数」与名次
   （`MiniTest.vue` 的 `mySections`），收成 `student_self` 会让名次恒为 1。

于是三条裁定目标同时兑现：① 匿名门关上；② **`MiniTest.vue` 一行代码没改**照常工作
（实测：本页只读 `shuttle_score`、`student_id`、`scored_count` 与**本人**那一行的
`squat_score` / `composite`，四者都照常给值）；③ 原始值不外流。

⚠️ **为什么这条比派单的 fallback 好**：教职-only 会让计划分给学生页的「班内百分位」
在**交付物**上消失（`MiniTest.vue` 会恒走 `normalizedError` 那一块「有解释的区域」）。
⚠️ **为什么这条比派单的原裁定好**：原裁定会让每个登录学生读到全班
（演示库上 5 个班、每班 20–30 人）的 30 秒深蹲**原始次数**，
而那正是安全收紧波刚在 `/api/mini-tests` 上用 `student_self` 关掉的东西。

⚠️ 实现细节里两个便宜的运气：
* 收窄走 `None`、**不是删键** → 响应 schema 一格不动（`NormalizedEntryRead` 那两格
  **本来就**声明成 `float | None`，「没测折返」那一档就是 `None`）。
  故**没有碰 `app/api/schemas/feedback.py`**，`gen:api` 的 diff 里也没有 schema 变化。
* 代价如实记（硬规矩 #39）：响应体从此**随身份而变**，OpenAPI 表达不了这件事
  （它只有一张 schema），只能靠 `normalized_scores` 的 docstring + 2 条测试钉住。

### 4.3 口径变化（运行时口径，`app.openapi()["paths"]`）

| 口径 | 改前 | 改后 |
|---|---|---|
| 路径模板 | 71 | **71**（不变） |
| 操作 | 99 | **99**（不变） |
| **挂 `security` 的操作** | 80 | **81** |
| GET 总数 | 60 | **60**（不变） |
| **匿名 GET** | 16 | **15** |
| 挂 security 的 GET | 44 | **45** |
| `securitySchemes` | 3（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | **3**（不变） |
| `normalized` 的 `security` | `<没有这一格>` | `[{'X-Student-Id': []}, {'X-Teacher-Staff-No': []}]` |
| `normalized` 的 `parameters` | `semester_id, week` | `semester_id, week, x-student-id, x-teacher-staff-no` |

⚠️ **顶回 4**：派单预告「`test_crud.py:969` 的 `anonymous == 7` 会红」。
**实测不受影响**（全量测试跑过，那一拍仍绿）。理由：它数的是
`catalog.RESOURCES` 那 **23 行**里 `read_scope is None` 的行数
（实际行号是 `test_crud.py:1026`，不是 969），而 `normalized` 是**特例端点**、
不在这 23 行里。改前改后都是 **7**。

跟着改的断言与账面（一律先跑全量收进来，硬规矩 #88）：

* `tests/api/test_feedback.py`：旧的
  `test_the_normalized_route_is_anonymous_and_a_student_can_read_it`（它断的正是
  「三种身份响应体逐字相同」）换成**两条** ——
  `test_normalized_scores_is_not_readable_anonymously`（四拍：匿名 401 +
  不带参数也是 **401 而不是 422** + 两种登录身份 200 + 不在册工号 403 +
  OpenAPI 声明面 + 反空转）与
  `test_a_student_session_reads_the_whole_class_percentile_but_no_raw_squat_count`
  （五拍：全班百分位照常给〔含「三个百分位互不相同」的反空转〕/ 原始值只对本人给 /
  **而它确实是原始值**〔教职档 ↔ `GET /api/mini-tests` 逐行对账 + 反推算式〕/
  键集合不变 / `unassigned` 只留本人〔两侧都验：在班里的看到空表、没编班的仍看得到自己〕）。
* `tests/api/test_prescription_api.py`：全仓级 `expected` 清单 **22 → 23** 项、
  合计 **80 → 81**。⚠️ 本端点是清单里**唯一**一格「值为两个 scheme」的，
  故那个循环从「单名」改成「名字或元组」；`crud` 那一圈 **77 → 76**（99 − 23），
  `>= 70` 的空转下界仍成立、刻意不抬。
* `catalog.py` **两处 docstring**（模块头那张三档表下面的一段 + `mini-tests` 那一行的
  行内注释）此前逐字写着「它今天匿名、已登记为待清扫」—— 一并改写。
  ⚠️ **23 行声明一个字没动**（派单的禁区），`app/auth/**` 与 `crud.py` 的 `read_scope`
  机制也一个字没动。
* `smoke.mjs` 第 13 步：那一发匿名调用改成 `as: 'teacher'`，并从 **1 拍扩成 6 拍**
  （三档身份 + 收窄的两侧 + 键集合），**15 → 24 条断言**；第 12 步那两格计数改成
  **81 / 15**。⚠️ 派单只点了「第 13 步若有匿名调用要改」，**第 12 步那两格是跑出来才发现的**。

### 4.4 `npm run gen:api` 的 diff 规模与三项核实

```
openapi-typescript 7.13.0 → src/api/generated/schema.d.ts [368.1ms]   退出码 0
git diff --stat:  1 file changed, 74 insertions(+), 29 deletions(-)
schema.d.ts:  改前 413 238 B / 9 022 行  →  改后 408 515 B / 9 067 行（+45 行）
```

diff **全部落在 `/api/mini-tests/normalized` 那一格**：docstring 被搬进 JSDoc
（占绝大部分行数）、新增 `security`、新增两个请求头参数。
⚠️ 字节数**变小**而行数变多，是因为改前的工作树是 CRLF、`gen:api` 写的是 LF
（9 022 行的 CR 差 ≈ 9 kB）；`core.autocrlf=true` 的 clean 过滤两侧都归一到 LF，
故 **blob 的 diff 只有那 +74/−29**（`git diff --stat` 已证）。

三项核实（派单点名的）：

1. **`npm run build` 仍绿**：退出码 **0**，CSS **62.79 kB** / JS **165.70 kB**（129 → 133 modules，多的 4 个是 woff2）。
2. **那 24 个未定型响应逐字不变**：`smoke.mjs` 第 12 步第 ⑤ 拍
   （`23 个 list 端点的响应全部未定型` + `/api/health 也未定型（24 = 23 + 1）`）**仍绿**，
   第 12 步整体 **102/102**。⚠️ 本端点有 `response_model=NormalizedScoreRead`
   （实测响应 schema 带 `$ref`），本来就在那 24 个之外，故结构上不可能被它碰到。
3. **第 12 步第 ⑤ 拍仍绿** —— 同上，逐字见 `smoke-final2.txt`。

⚠️ 顺手实测到一格（已写进测试注释）：`Depends(current_reader)` 的 `Header()` 形参
在 OpenAPI 的 `parameters[i].name` 里是**全小写**（`x-student-id`），
而 `Security(APIKeyHeader(name="X-Student-Id"))` 在 `components.securitySchemes` 里
**保留原样大小写** —— 同一个请求头在一份 spec 里有两种大小写。
第一版断言按原样大小写比，当场红。

---

## ⑤ 第 ④ 件：两条便宜的待清扫

### ④.1 `demo.ps1` 末尾那一批提示 URL

⚠️ **顶回 5**：派单说「那 **4** 行今天打过去是 401」。**实测是 7 行**（改前），
而收尾波 ③ 关掉 `normalized` 那扇门之后是 **8 行全 401**。逐个匿名实发（改前）：

```
GET  /api/students/1/prescriptions/current?as_of=2025-10-12  -> 401
GET  /api/students/1/weekly-sheet?as_of=2025-10-12           -> 401
GET  /api/alerts?limit=50                                    -> 401
POST /api/alerts/1/handle?as_of=2025-10-12                   -> 401
GET  /api/notifications?limit=50                             -> 401
GET  /api/dashboard/class/1?week=6&as_of=2025-10-12          -> 401
POST /api/pipeline/run-daily                                 -> 401
GET  /api/mini-tests/normalized?semester_id=2&week=6         -> 200  ← 改前；改后 401
```

派单给了两个选项（「加一句要先登录」**或**「换成仍匿名的端点」），**两条都做了**：
① 在清单头上印三行「一律要登录会话 + 是哪两波收的 + 怎么登录」；
② 另给 **3 条仍然匿名**的当例子（实测各 200）：`/api/health`、
`/api/exercises?limit=50`、`/api/percentile-snapshots?limit=50`
—— 于是「不登录也能点通一条」这个演示动作还在。
（实测仍匿名的完整一档是 `/api/health` + 7 个参考数据资源，与 §4.3 的「匿名 GET 15」对得上。）

**BOM 与行尾**（派单点名要按字节量、且 IDE 的编辑工具吃过它两次）：

| | bytes | BOM | CRLF | 裸 LF |
|---|---|---|---|---|
| 改前 | 17 818 | **True** | 250 | **0** |
| 改后 | **19 563** | **True** | **267** | **0** |

`sha256` 前 16 位 = `2680F534535A1DFB`。
⚠️ 全程用 **python 按字节改**（读 `rb` → 断言 BOM 在、断言无裸 LF → 替换 → 写 `wb`），
**没有**用 IDE 的 SearchReplace 碰这个文件。
⚠️ 改完实跑了一次 `demo.ps1 -Port 8000`，中文渲染正常（BOM 在 → PowerShell 5.1
不会按 ANSI 静默乱码），禁区复核那一行照常打印
（`backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`）。
⚠️ 那一批 `Write-Host` 住在 `-DryRun` 的 `exit 0` **之后**，故 `smoke.mjs` 第 17 步 ①
那一拍（它 spawn 一次 `-DryRun`）不受影响：实测 **27/27 仍绿**，
其中「UTF-8 带 BOM」与「纯 CRLF（0 个裸 LF）」两拍就是钉这件事的。

### ④.2 `smoke.mjs` 第 0 步的注释「7 张表」

实测那个对象字面量有 **8** 个键（`students` / `teachers` / `notifications` /
`prescriptions` / `training-logs` / `rpe-records` / `weekly-class-reports` / `alerts`），
而**紧跟其后**的注释自己就写着「**8** 个里的 6 个从 `undefined` 改成 `'teacher'`」
—— 同一个对象上两个数打架，错的是前一句。改成「**8 个资源**」，
并顺带把「张表」换成「个资源」：本行数的是 **HTTP 面**的 `total`，
不是 `sqlite_master` 里的表（那一份是 **26** 张，由第 1 步的 `GET /api/health` 钉；
两种口径以运行时为准，硬规矩 #103）。
⚠️ 它与 ③ 的 `smoke.mjs` 改动同一个文件，故搭 commit ③ 的车（见 §6「没按派单做的」）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / 顶回

### 6.1 顶回（**10 处**，其中 3 处 Critical）

| # | 顶回 | 级别 | 实测依据 |
|---|---|---|---|
| 1 | **基线「487 绿 + 3 红」是假的**：实测 **486 绿 + 4 红**，`s-rpe` 也红（2 处）；而最坏情况是 **6 条路由 / 15 处**（多出来的是 `t-dashboard` / `t-report` / `admin-index`） | Critical | §2.0 与 §2.1 实验 A 的逐字输出 |
| 2 | **派单说「两款字体」，`index.html` 实际拉三款**（还有 `JetBrains Mono 400/700`，8 处消费者）。要「产物里不含 CDN」就必须一起处置 → 一并自托管 | 中 | `Grep --font-mono` 8 处；§3.6 |
| 3 | **「不做自过滤」那条裁定的前提是假的**：`squat_score` **就是** `squat_30s_count`（120/120 逐行相等），且 `composite` 能反推它 → 改成**列级收窄**，而不是派单的 fallback（教职-only + 学生页降级） | **Critical** | §4.1 的逐行对账与反推算式 |
| 4 | **派单预告 `test_crud.py` 的 `anonymous == 7` 会红 —— 实测不受影响**（它数的是 `RESOURCES` 那 23 行，`normalized` 是特例端点、不在里面）。⚠️ 派单给的行号 969 也不对，实际是 **1026** | 中 | 全量 1340 passed，那一拍绿 |
| 5 | **`demo.ps1` 不是「那 4 行」是 401，是 7 行**（改前）/ **8 行**（改后） | 低 | §5 的逐个实发 |
| 6 | **「下载 5 个字重」会白下 3.5 倍字节**：Google 对多字重查询发的是**可变字体**，同一 subset 的 5 档指向逐字相同的同一个 woff2。本波第一版实测踩到（14 个文件里 10 个是副本） | 中 | §3.1 的 sha256 去重 |
| 7 | **`document.fonts.check()` 在无 `@font-face` 时恒真**（实验 A 里 `faces=0` 而 `HG=true`），不能当「字体加载了」的判据 | 中 | §2.2 陷阱 1（硬规矩 #107） |
| 8 | **`ascent-override` 被压缩器吃掉是一个真实风险**（它是「挡住字体也不许重叠」的实现）→ 已加正控断言；实测 esbuild 没吃 | 中 | §3.5 的 `→ 1 次` |
| 9 | **Vite 不剥 `index.html` 的 HTML 注释**（CSS 的它剥）→「产物里 0 次 CDN」这条守卫首跑**恒红**，因为注释里逐字**提到**了那两个域（提及 vs 引用，硬规矩 #109）。处置：把谓词做准（剥块注释 + 3 拍自校）**并且**把 `index.html` 的注释收成指针 | **Critical** | §3.3 / §3.5 |
| 10 | 派单只点了「第 13 步若有匿名调用要改」，**第 12 步那两格计数（80 / 16）也要改** —— 跑出来才发现 | 低 | §4.3 |

### 6.2 没按派单做的（3 处，都在上面顶回里有对应条目）

1. **没走「教职-only + 学生页降级」那条 fallback**，改用列级收窄（顶回 3）。
   ⚠️ 若控制者更想要「响应与身份无关」，那条路仍然可走，代价逐字写在
   `normalized_scores` 的 docstring 末节与本报告 §4.2。
2. **没把 `--font-mono` 掉到系统等宽栈**，而是自托管了 JetBrains Mono（顶回 2）。
3. **改了 `catalog.py`**（派单的允许清单里没有它）—— 但改的**只有两处 docstring**，
   派单禁的那 **23 行声明一个字没动**，`app/auth/**` 与 `crud.py` 的 `read_scope`
   机制也一个字没动。理由：那两处逐字写着「它今天匿名、已登记为待清扫」，
   不改就是账面与代码相反（而本仓的整个纪律就是不允许这件事）。
4. ⚠️ 派单**建议** 4 个 commit，我做了 **4 个**；但 ④.2（`smoke.mjs` 第 0 步注释）
   搭了 commit ③ 的车 —— 它与 ③ 的 `smoke.mjs` 改动同一个文件，
   拆开要么用交互式 staging（派单禁止 `-i`）、要么在 ③ 里留一句假注释。

### 6.3 待清扫（**6 条**）

1. **`normalized` 的响应体随身份而变，OpenAPI 表达不了**。要消除它，正解是把
   `squat_score` / `composite` 从 `NormalizedEntryRead` 上**摘掉**
   （学生页实测不读别人的那两格；教师页 `StudentDetail.vue:277` 读，需一并核），
   那要动 `app/api/schemas/feedback.py`（**本波禁区**）。
2. **中文改走系统栈后，中文字形逐 OS 而异**（Windows 雅黑 / macOS 苹方），
   「视觉一致性」在中文这一侧没有单一所有者。要收回就得引 subset 工具（会破零依赖纪录）。
3. **`--font-mono` 没有度量对齐的回退面**（JBM 的 R = 1.45，Consolas = 1.17）。
   实测那一族今天两处都不重叠（回退只会让盒子**变小**），故本波没做；
   ⚠️ 但若将来给等宽那一族加紧贴行高，要补一个同形的 `JetBrains Mono Fallback`。
4. **`.step__zh` 的 `font-size: 10px`** 低于 `--fs-micro`(12px) 那一档，
   而 `tokens.css` 的注释逐字说「12px + `--ink-faint`(5.23:1) 才过 AA」。
   本波只改了它的**行高**、没动字号（超出范围）。
5. **`smoke.mjs` 第 14 步的 CDP 量取不等 `document.fonts.ready`**。自托管 + 度量对齐
   之后这不再是失效源（§2.5 的 nowait 组 0 重叠），但「量取时机与字体就绪无关」
   今天靠的是**布局不变性**、不是一个显式的等待。要更稳可在 `dumpRoute` 里加一次
   `await document.fonts.ready`（本波刻意没加：那会把守卫变松，而布局不变性是被
   WORST 那一组证明过的更强性质）。
6. **`schema.d.ts` 的工作树行尾会被 `gen:api` 从 CRLF 翻成 LF**（blob 不受影响，
   因为 `autocrlf=true` 的 clean 过滤两侧都归一到 LF）。每次重跑 `gen:api` 都翻一次，
   值得给它一行 `.gitattributes` 或一条守卫。

### 6.4 关切（2 条）

1. ⚠️ **`--lh-tight` 1.04 → 1.3 是一处视觉变化**（大数字的行盒高 +25%：
   学生首页 50.7 → 63.4px，教师大屏 58.2 → 72.8px）。本波只用**几何判据**
   （重叠守卫 + 横向溢出 + 整页 `scrollWidth`）验过，**没有做过截图比对**。
   `frontend/scripts/shots.mjs` 在仓里，建议交付前人眼过一遍那 15 条路由。
2. ⚠️ **中文从 Noto Sans SC 换成系统黑体也是视觉变化**（本机上尤其明显：
   改前中文渲染在 CDN 的 Noto Sans SC 上，改后渲染在 Microsoft YaHei 上）。
   这是控制者裁定的既有代价，但同样建议过一遍眼。

---

## ⑦ 最终验收

### 后端

| 项 | 基线 | **实测** |
|---|---|---|
| `python -m pytest -q` | 1339 passed | **1340 passed**，退出码 **0**（135.91 s）；1 条旧测试换成 2 条新的 → +1 |
| `app/domain/` 覆盖率（`--cov=app/domain --cov-branch`） | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%**（`TOTAL` 行逐字相同；那一跑是 1339 passed + 1 skipped） |
| 表数（`Base.metadata.tables`，运行时口径） | 26 | **26** |
| 架构守卫扫描面（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | 66 | **66**（本波一个新 `.py` 都没加） |
| 路径模板 / 操作（`app.openapi()["paths"]`） | 71 / 99 | **71 / 99** |
| 挂 `security` 的操作 | 80 | **81** |
| GET：匿名 / 挂 security | 16 / 44 | **15 / 45** |
| `securitySchemes` | 3 | **3** |

### 前端

| 项 | 基线 | **实测** |
|---|---|---|
| `npm run build` | 退出码 0，CSS 61.02 kB / JS 165.70 kB | 退出码 **0**，CSS **62.79 kB**（gzip 9.36）/ JS **165.70 kB**（gzip 58.02，**逐字不变**），`✓ built in 380ms` |
| `npm run check:tokens` | 绿 | **绿**，扫描面 32 → **33** 个文件，offender **0**，退出码 0 |
| `npm run check:dist` | 绿 | **绿**，退出码 0；新增 **11 拍**（4 个正控 + 2 个 CDN 零命中 + 3 拍自校 + 源码侧 2 拍） |
| `@ts-ignore` / `@ts-expect-error` / `as any` | 0 | **0**（`Grep` 全 `src/` 无命中） |
| 路由条数 | 15 | **15**（`smoke.mjs` 第 14 步 `eq('路由条数 = 15…')` 仍绿） |
| **新增依赖**（前端 + 后端） | 0 | **0** —— `git diff 48b45da -- package.json package-lock.json backend/requirements.txt` **全空** |
| `document.fonts.size` | 335 | **5**（4 个自托管面 + 1 个回退面） |

### `smoke.mjs`（一份刚重灌的演示库上跑的）

```
EXITCODE=0
步数 18/18 全绿 · 断言 499 绿 / 0 红
  第 00 步 25/25 · 第 01 步 5/5   · 第 02 步 10/10 · 第 03 步 9/9
  第 04 步 7/7   · 第 05 步 9/9   · 第 06 步 10/10 · 第 07 步 41/41
  第 08 步 14/14 · 第 09 步 13/13 · 第 10 步 17/17 · 第 11 步 6/6
  第 12 步 102/102（含第 ⑤ 拍「24 个未定型响应」）
  第 13 步 24/24（改前 15/15）
  第 14 步 109/109（改前 105/109）
  第 15 步 8/8   · 第 16 步 63/63 · 第 17 步 27/27
```

第 14 步的 15 条 `布局守卫` 行，逐字（**重叠一律 0 处**）：

```
login             叶子   63 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
bind              叶子   81 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
s-home            叶子  111 · 重叠 0 · 溢出 0 · scrollWidth  375/375
s-weekly-sheet    叶子  241 · 重叠 0 · 溢出 0 · scrollWidth  360/375
s-check-in        叶子  228 · 重叠 0 · 溢出 0 · scrollWidth  360/375
s-rpe             叶子  150 · 重叠 0 · 溢出 0 · scrollWidth  360/375
s-mini-test       叶子  170 · 重叠 0 · 溢出 0 · scrollWidth  360/375
s-notifications   叶子  169 · 重叠 0 · 溢出 0 · scrollWidth  360/375
t-dashboard       叶子  320 · 重叠 0 · 溢出 0 · scrollWidth 1425/1440
t-report          叶子  288 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
t-alerts          叶子 1153 · 重叠 0 · 溢出 0 · scrollWidth 1425/1440
t-student-detail  叶子  478 · 重叠 0 · 溢出 0 · scrollWidth 1425/1440
admin-index       叶子  231 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
admin-list        叶子  202 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
admin-detail      叶子   66 · 重叠 0 · 溢出 0 · scrollWidth 1440/1440
```

⚠️ 叶子数与改前**逐字相同**（63/81/111/241/228/150/170/169/320/288/1153/478/231/202/66）
—— 即页面内容一格没少，变的只有几何。

### 禁区与指纹

```
backend/pe.db 存在                     = False      ✓
backend/data/seed/ 文件数              = 0          ✓
backend/data/ 文件总数                 = 24（6 个根下 + 18 个模板）
git diff --stat 48b45da HEAD -- backend/data   → 空 ✓（一个字节没动）
```

四个指纹（`sha256` 前 16 位，逐个反查到文件）：

| 指纹 | 文件 |
|---|---|
| `D2C8E539E2FA0029` | `backend/data/national_standard_2014.csv` ✓ |
| `5394B37F01DAC9AC` | `backend/data/exercises.yaml` ✓ |
| `822CB86A5E998301` | `backend/data/exercise_equivalence.yaml` ✓ |
| `E48E3AC82BB45BB7` | `backend/data/alert_rules.yaml` ✓ |

18 个模板指纹（`backend/data/prescription/*.yaml`，**18 个**，逐个实测）：

```
GRN-END-ABN-13 89842C7A0D8A6EA0   GRN-END-NOR-14 3B1DA3AAB8D6A322
GRN-SPD-ABN-17 9ADB0CAC53A572F1   GRN-SPD-NOR-18 2389C1A03E6ABBCE
GRN-STR-ABN-15 91E660991C717944   GRN-STR-NOR-16 A5B406807FDEF7CC
RED-END-ABN-01 C0C61D2140A521D0   RED-END-NOR-02 FE91666F74C08CAF
RED-SPD-ABN-05 8E396D8BF85B6DBD   RED-SPD-NOR-06 0EDDE329A6CA61AE
RED-STR-ABN-03 8F4D51E3377FA814   RED-STR-NOR-04 3E8C365CD0B4C133
YEL-END-ABN-07 D301AE8D8D3D6B7E   YEL-END-NOR-08 F08B64A00D974F18
YEL-SPD-ABN-11 FA81CAD1B9050A9E   YEL-SPD-NOR-12 524CD251936C79B1
YEL-STR-ABN-09 033CFAA2D1F93503   YEL-STR-NOR-10 C1CDF7D18A1F87E4
```

⚠️ 全程**没有**跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`。
演示库只由 `demo.ps1`（走 `scripts/demo_bootstrap.py`，它自带禁区守卫）重灌。

### 行尾与 BOM（`read_bytes()` 实测）

| 文件 | bytes | BOM | CRLF | 裸 LF |
|---|---|---|---|---|
| `backend/scripts/demo.ps1` | 19 563 | **True** | 267 | **0** |
| `frontend/src/styles/fonts.css`（新） | 11 532 | False | 160 | **0** |
| `frontend/src/styles/tokens.css` | 21 009 | False | 284 | 0 |
| `frontend/index.html` | 1 833 | False | 31 | 0 |
| `frontend/src/main.ts` | 10 034 | False | 161 | 0 |
| `frontend/scripts/check-dist.mjs` | 18 211 | False | 307 | 0 |
| `frontend/scripts/smoke.mjs` | 173 551 | False | 2 653 | 0 |
| `frontend/src/views/student/MiniTest.vue` | 27 741 | False | 598 | **0**（首测是 MIXED 16 个裸 LF，已统一） |
| `frontend/src/views/student/RpeEntry.vue` | 27 429 | False | 699 | 0 |
| `frontend/src/views/student/WeeklySheet.vue` | 20 442 | False | 539 | 0 |
| `.gitattributes` | 5 585 | False | 65 | 0 |
| `backend/app/api/routers/feedback.py` | 71 821 | False | 1 161 | 0 |
| `backend/app/api/routers/catalog.py` | 52 931 | False | 824 | 0 |
| `backend/tests/api/test_feedback.py` | 112 035 | False | 1 924 | 0 |
| `backend/tests/api/test_prescription_api.py` | 114 004 | False | 1 949 | 0 |

⚠️ `frontend/src/api/generated/schema.d.ts` 是唯一一个改后工作树为 **LF** 的文件
（`gen:api` 写的），blob 不受影响（见 §4.4），已登记为待清扫 6。

### commit（4 个，全部在 `harden/fonts-and-overlaps` 上，**没有 push**）

| sha | 一句话 | 文件数 |
|---|---|---|
| `1342c68` | fix(frontend): 收尾波 ① —— 把布局从「取决于哪一款字体在用」里救出来 | 3（+63 / −18） |
| `0219006` | feat(frontend): 收尾波 ② —— 字体自托管，运行时零跨域请求 | 9（+347 / −37，含 4 个 woff2 与 `fonts.css` 两个新文件） |
| `22af44c` | fix(security)!: 收尾波 ③ —— 关掉 `GET /api/mini-tests/normalized` 那扇匿名门 | 7（+567 / −202） |
| （本 commit） | chore(backend)+docs(sdd): 收尾波 ④ —— `demo.ps1` 的提示 URL 不再骗人 + 实现者报告 | 2 |

`git add` 一律**按文件名逐个加**（含 4 个 woff2），全程没有 `git add -A`；
commit 信息一律 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。

---

*本报告由 python 写盘（纯 LF，与同目录的 `report.md` 同口径）；写完按字节复核过，
入库 blob 的字节数与磁盘逐字相同（`.superpowers/**  -text` → git 双向零转换）。*
