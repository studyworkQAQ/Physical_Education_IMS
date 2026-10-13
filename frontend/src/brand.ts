/**
 * `brand.ts` —— **系统名与厦门大学品牌素材的唯一住址**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 为什么会有这个文件（品牌与密度波）
 * ---------------------------------------------------------------------------
 * 本波把系统从「体育闭环原型系统」改名为「**厦大体育数智系统**」，并接入甲方的
 * 品牌素材（校徽 + 嘉庚体校名）。改名的失效形态是「改了 5 处、漏了第 6 处」：
 * 旧名字此前有 **4 个住址**（`index.html` 的 `<title>`、`router/index.ts` 的
 * `document.title`、`App.vue` 报头那个 `<h1>`、`package.json` 的 description），
 * 而其中两个（`index.html` 与 `package.json`）**在 TS 之外**，`vue-tsc` 拦不到。
 * 故凡是能被 TS 引用的那几格，一律收到这里来：
 *   · 系统名 / 拉丁副题 / 校名 / 校训 / 版本号
 *   · 两个矢量素材的 URL（`import` 它们 = Vite 负责指纹与缓存，
 *     而不是有人手写一条 `/src/assets/…` 的路径）
 * ⚠️ 剩下的两个住址（`index.html` 的 `<title>` 与 `package.json` 的 description）
 *    **收不进来**：前者在 Vue 挂载之前就要生效（一个空白的 `<title>` 会闪一下），
 *    后者是 npm 的元数据。故本文件的文件头逐字点出这两处，改名时三处一起改。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 素材是**复制进仓库**的，不引用仓库外的路径
 * ---------------------------------------------------------------------------
 * 源文件在甲方给的 `xmulogo/` 目录下（`xmu-logo.svg` / `xmu-zi-jiageng.svg`）。
 * 交付物不得依赖某台机器上的桌面目录，故两个文件被逐字节复制成
 *   `src/assets/brand/xmu-emblem.svg`    52095 B  sha256[:16]=394C0A85CEBB5A45
 *   `src/assets/brand/xmu-wordmark.svg`  15975 B  sha256[:16]=17E74386647229A2
 * （与源文件 `identical_to_source=True`，实测记录见本波报告 §2）。
 * ⚠️ `.gitattributes` 给这两个文件钉了 `-text`：本机 `core.autocrlf` 是 `true`，
 *    而素材是**纯 LF、无 BOM**，不钉的话一次 checkout 就把它们重写成 CRLF、
 *    上面那两个字节数当场变假。
 * ⚠️ **鲁迅体校名不用**（控制者裁定）：它只有位图（`.jpg` / `.pdf`），
 *    在报头那一档 36px 的高度上会发虚；嘉庚体是矢量，缩到多小都是锐的。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 两个 svg 里的 `#122e66` 与 `tokens.css` 的 `--primary` 是**同一个蓝**
 * ---------------------------------------------------------------------------
 * 素材自带的 fill 逐字是 `#122e66`，而本波把 `--primary` 也取成了这个值 ——
 * 于是「校徽的蓝」与「界面的蓝」不可能漂开。⚠️ 那两处 svg 里的字面量**不构成
 * 第二个色值所有者**：`scripts/check-tokens.mjs` 的扫描面是
 * `SCANNED_EXTENSIONS = {.css, .vue}`，`.svg` 不在面里（守卫的 glob 因此
 * **不需要**为品牌素材收窄、也不需要开豁免）。
 * ⚠️⚠️ 反过来讲：**不要把这两个 svg 内联进 `.vue`**。内联会让那 10 处
 *    `fill:#122e66` 落进守卫的扫描面，`check:tokens` 当场报 10 处 offender ——
 *    而正确的处置是保持 `<img src>`（本文件导出的就是给 `<img>` 用的 URL）。
 */
import emblemUrl from './assets/brand/xmu-emblem.svg'
import wordmarkUrl from './assets/brand/xmu-wordmark.svg'

/** ⚠️ 由 `vite.config.ts` 的 `define` 在编译期替换成 `package.json` 的 `version`。
 *  故「版本号」也只有一个住址：改 `package.json` 的 `version`，页脚那一行跟着变。
 *  ⚠️ 不在这里写死一个字面量，正因为它能从别处读出来（硬规矩 #111）。 */
declare const __PE_VERSION__: string

/** 系统名（改名之后）。⚠️ 旧名字「体育闭环原型系统」是历史，见本波报告 §3 的命中清单。 */
export const SYSTEM_NAME = '厦大体育数智系统'

/** 一行小字的拉丁副题。
 *  ⚠️ 旧的那一行是 `PHYSICAL EDUCATION · CLOSED LOOP`；控制者裁定「不要再叫
 *  prototype」，而 `CLOSED LOOP`（闭环）同样是**原型阶段**的自我描述 ——
 *  交付给甲方的一行副题应当说这个系统**做什么**，故换成分层运动处方。 */
export const SYSTEM_SUBTITLE = 'PHYSICAL EDUCATION · LAYERED PRESCRIPTION'

/** 校名（简体，用于报头那行拉丁小标题与 `alt`）。 */
export const UNIVERSITY_NAME = '厦门大学'

/** 校名的拉丁写法。⚠️ 素材外圈逐字是 `UNIVERSITAS AMOIENSIS`（拉丁文校名），
 *  而报头那一行给人读的是英文，故两者都在场：徽里是拉丁文、报头是英文。 */
export const UNIVERSITY_NAME_EN = 'XIAMEN UNIVERSITY'

/** 校训。⚠️ 它逐字来自校徽那条绶带（`止於至善`），按控制者裁定只在
 *  **登录页**与**页脚 colophon** 各排一行小字（品牌元素，不做大标语）。 */
export const MOTTO = '止於至善'

/** 版本号（编译期从 `package.json` 取）。 */
export const VERSION: string = __PE_VERSION__

/** 校徽（圆形盾徽：外圈「廈門大學」+「UNIVERSITAS AMOIENSIS」，中心盾与楼，
 *  绶带「止於至善」）。⚠️ 固有尺寸 1066.6667 × 1066.6667（1:1）。 */
export const BRAND_EMBLEM: string = emblemUrl

/** 嘉庚体「廈門大學」横排书法字。⚠️ 固有尺寸 533.33417 × 145.65753
 *  （宽高比 **3.662 : 1**，故给宽度就能算高度，不要两边都写死）。 */
export const BRAND_WORDMARK: string = wordmarkUrl

/** 嘉庚体校名的宽高比（上面那两个固有尺寸相除）。
 *  ⚠️ 它是**素材的几何**、不是设计令牌，故住在这里而不是 `tokens.css`
 *  （那个文件是「颜色/字号/间距/圆角」的唯一住址，不管某个 svg 有多宽）。 */
export const WORDMARK_RATIO = 533.33417 / 145.65753
