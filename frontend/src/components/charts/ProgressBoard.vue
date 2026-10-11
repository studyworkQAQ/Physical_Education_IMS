<script lang="ts">
/** 进步榜的一行。⚠️ 普通 `<script>`：本类型要被调用方 `import type`。 */
export interface ProgressEntry {
  readonly student_id: number
  /** 百分比变化（可正可负）。实测演示库：`235.88` … `-64.84`。 */
  readonly change_pct: number
}

/** `weekly_class_report.progress_board` / 大屏 `blocks.progress_board` 的形状。
 *  实测五个键：`top_n` / `top` / `regressed` / `unchanged` / `unmeasured`。 */
export interface ProgressBoardData {
  readonly top_n: number
  readonly top: readonly ProgressEntry[]
  readonly regressed: readonly ProgressEntry[]
  readonly unchanged: number
  readonly unmeasured: number
}
</script>

<script setup lang="ts">
/**
 * `charts/ProgressBoard.vue` —— **进步榜 / 退步名单**（手写 SVG，计划第 3 节：不引 ECharts）。
 *
 * ---------------------------------------------------------------------------
 * 数据形状（⚠️ 本组件**不发请求**：数据由页面给，于是「读哪个端点」只有一个住址）
 * ---------------------------------------------------------------------------
 * 一个 {@link ProgressBoardData}。两个消费者给的是**同一个形状**：
 *  - 大屏：`GET /api/dashboard/class/{id}` 的 `blocks.progress_board`（现算）；
 *  - 班级周报：`GET /api/dashboard/weekly-class-report/{id}` 的 `progress_board`
 *    （周日存下来的那一行）。
 *
 * ⚠️⚠️ **计划约束第 12 条**：进步榜一律读这一格，**不要**自己去调
 * `GET /api/mini-tests/normalized` 拼 —— 两者的算式已经统一到一个住址
 * （`app/domain/report.py`），但**窗口不同**（周报比的是「上一次小测 vs 这一次」，
 * normalized 给的是「这一周的班内百分位」），拼出来会与周报上的数不一致。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 顶回控制者的一处「不必顶」：排序与分组**后端已经做完了**
 * ---------------------------------------------------------------------------
 * 派单点名了这一格可能是本 Task 的顶回处（「若 `progress_board` 要排序+分组+
 * 双向条形而代价过大，在本 Task 顶回」）。实测**代价不在前端**：
 * 响应体里 `top` 已按 `change_pct` **降序**、`regressed` 已按 **升序**
 * （最负的在前）排好，且**已经分成两个数组**（不是让前端按符号切）。
 * 实测演示库（教学班 1）：`top` 10 行（235.88 → 39.97）、`regressed` 16 行
 * （-64.84 → -10.21）、`unchanged: 0`、`unmeasured: 0`、`top_n: 10`。
 * 故本组件只做两件事：**定标**（两侧共用一个 max）与**画条**。
 *
 * ---------------------------------------------------------------------------
 * SVG 实现要点
 * ---------------------------------------------------------------------------
 *  - **条是 SVG（`<rect>`）、文字是 HTML**：与 `CompletionBars.vue` 同一条取舍，
 *    理由逐字写在那里（SVG 的 `viewBox` 等比缩放会连字一起缩，而大屏有 18px 的
 *    **字号下限**）。
 *  - ⚠️ **两侧共用一个标尺**（`maxAbs = max(|change_pct|)` 跨两个数组）：
 *    各归各的失效形态很具体 —— 演示库上 `top` 的最大值是 `235.88`、
 *    `regressed` 的最大绝对值是 `64.84`，若各自归一，一个 −10% 的退步会画得
 *    与一个 +235% 的进步**一样长**，而教师看的是「谁变化大」。
 *  - ⚠️ 两侧**方向相反**（进步向右、退步向左），中轴是一条 3px 的墨/纸线
 *    = 分道线母题的粗线那一档（`--lane-thick`）。
 *  - ⚠️ 动效只有一处：条从中轴**长出去**（`transform: scaleX(0→1)`，
 *    两侧的 `transform-origin` 各在自己的中轴侧），用既有的
 *    `--dur-lane` / `--ease-lane`。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 空态与「没有可比数据」是两档
 * ---------------------------------------------------------------------------
 * `top` 与 `regressed` 都空时，先看 `unmeasured`：
 *  - `unmeasured > 0` → 「这一周没有可比的两次小测（N 人测不足两次）」；
 *  - `unmeasured === 0` 而 `unchanged > 0` → 「 everybody 的综合分一模一样」；
 *  - 两个都是 0 → 「这个班这一周没有小测」。
 * 三者措辞不同，因为它们指向的**下一步**不同（补录 / 无需动作 / 去录成绩）。
 */
import { computed } from 'vue'

interface Props {
  board: ProgressBoardData
  /** `ink` = 教师大屏（深底 → 三色用 `--*-on-ink` 变体）。 */
  tone?: 'paper' | 'ink'
  /** 每一侧最多画几行。⚠️ 缺省 = 后端的 `top_n`（进步榜那侧）与 8（退步那侧）：
   *  大屏一屏放不下 16 行退步，而「前 8 个」已经足够教师决定找谁谈话。 */
  limitTop?: number | null
  limitRegressed?: number | null
  /** `student_id` → 姓名。⚠️ 由**页面**给（本组件不发请求）：
   *  姓名要另调 `GET /api/students`（匿名），而「读哪个端点」只能有一个住址。
   *  给不出来（还没加载完 / 那个学生不在名册里）就只显示 id。 */
  nameOf?: ((studentId: number) => string | null | undefined) | null
  caption?: string
}

const props = withDefaults(defineProps<Props>(), {
  tone: 'paper',
  limitTop: null,
  limitRegressed: null,
  nameOf: null,
  caption: '',
})

interface Bar {
  studentId: number
  name: string | null
  change: number
  /** 0–100 的长度（与 `viewBox="0 0 100 10"` 同口径）。 */
  width: number
  side: 'top' | 'regressed'
}

/** ⚠️ 两侧共用的标尺（见文件头那段）。0 时一律退回 1，避免除零。 */
const maxAbs = computed(() => {
  const all = [...props.board.top, ...props.board.regressed]
  const m = all.reduce((acc, e) => Math.max(acc, Math.abs(e.change_pct)), 0)
  return m > 0 ? m : 1
})

function toBars(entries: readonly ProgressEntry[], side: 'top' | 'regressed', limit: number | null): Bar[] {
  const rows = limit === null ? entries : entries.slice(0, limit)
  return rows.map((e) => ({
    studentId: e.student_id,
    name: props.nameOf ? (props.nameOf(e.student_id) ?? null) : null,
    change: e.change_pct,
    width: Math.max(0, Math.min(100, (Math.abs(e.change_pct) / maxAbs.value) * 100)),
    side,
  }))
}

const topLimit = computed(() => props.limitTop ?? props.board.top_n ?? null)
const regressedLimit = computed(() => props.limitRegressed ?? 8)

const topBars = computed(() => toBars(props.board.top, 'top', topLimit.value))
const regressedBars = computed(() =>
  toBars(props.board.regressed, 'regressed', regressedLimit.value),
)

const topHidden = computed(() => Math.max(0, props.board.top.length - topBars.value.length))
const regressedHidden = computed(() =>
  Math.max(0, props.board.regressed.length - regressedBars.value.length),
)

const isEmpty = computed(() => topBars.value.length === 0 && regressedBars.value.length === 0)

/** 三档空态的措辞（见文件头那段）。 */
const emptyKind = computed<'unmeasured' | 'unchanged' | 'none'>(() => {
  if (props.board.unmeasured > 0) return 'unmeasured'
  if (props.board.unchanged > 0) return 'unchanged'
  return 'none'
})

function changeText(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

const summary = computed(() => {
  if (isEmpty.value) return '这一周没有可比的进步榜'
  return (
    `进步榜：进步 ${props.board.top.length} 人（最多 ${changeText(
      props.board.top[0]?.change_pct ?? 0,
    )}），退步 ${props.board.regressed.length} 人（最多 ${changeText(
      props.board.regressed[0]?.change_pct ?? 0,
    )}），不变 ${props.board.unchanged} 人，测不足两次 ${props.board.unmeasured} 人`
  )
})
</script>

<template>
  <figure class="pboard" :class="props.tone === 'ink' ? 'pboard--on-ink' : ''">
    <div v-if="isEmpty" class="pboard__empty">
      <svg class="pboard__empty-mark" viewBox="0 0 88 20" aria-hidden="true">
        <path class="pboard__empty-line" d="M44 2 V18" />
        <path class="pboard__empty-hair" d="M4 10 H40" />
        <path class="pboard__empty-hair" d="M48 10 H84" />
      </svg>
      <p class="pboard__empty-title zh-title">
        <template v-if="emptyKind === 'unmeasured'">这一周没有可比的两次小测</template>
        <template v-else-if="emptyKind === 'unchanged'">全班综合分一模一样</template>
        <template v-else>这个班这一周没有小测</template>
      </p>
      <p class="pboard__empty-note">
        <template v-if="emptyKind === 'unmeasured'">
          <strong class="num">{{ board.unmeasured }}</strong> 个人测不足两次 ——
          进步榜比的是「上一次小测 vs 这一次」，只测过一次的人**无定义**
          （不是 0%，也不是「没进步」）。⚠️ 下一步是补录：
          <code>POST /api/mini-tests/batch</code>（教师头）。
        </template>
        <template v-else-if="emptyKind === 'unchanged'">
          <strong class="num">{{ board.unchanged }}</strong> 个人的综合分与上一次
          **完全相同**（差值恰好 0）。⚠️ 这一档不需要任何动作，
          它与「读不到数据」是两件事。
        </template>
        <template v-else>
          <code>top</code> 与 <code>regressed</code> 都是空的，而
          <code>unchanged</code> / <code>unmeasured</code> 也都是
          <strong class="num">0</strong> —— 即这个班在这一周**一行小测都没有**。
          ⚠️ 小测每两周一次（spec §8.1），故「这一周没有」是常态、不是故障。
        </template>
      </p>
    </div>

    <template v-else>
      <div class="pboard__cols" :aria-label="summary">
        <!-- 进步榜：条向**右**长 -->
        <section class="pboard__col">
          <header class="pboard__head">
            <span class="pboard__headzh zh-title">进步榜</span>
            <span class="pboard__headn num">
              {{ board.top.length }} 人<template v-if="topHidden > 0">（只画前 {{ topBars.length }}）</template>
            </span>
          </header>
          <ol class="pboard__list">
            <li v-for="(bar, i) in topBars" :key="`top-${bar.studentId}`" class="pboard__row">
              <span class="pboard__rank num">{{ i + 1 }}</span>
              <span class="pboard__who">
                <span class="pboard__name">{{ bar.name ?? '—' }}</span>
                <span class="pboard__id num">#{{ bar.studentId }}</span>
              </span>
              <span class="pboard__barwrap pboard__barwrap--top">
                <svg class="pboard__svg" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
                  <rect
                    class="pboard__fill pboard__fill--moss"
                    x="0"
                    y="0"
                    :width="bar.width.toFixed(3)"
                    height="10"
                  />
                </svg>
              </span>
              <span class="pboard__val num pboard__val--moss">{{ changeText(bar.change) }}</span>
            </li>
          </ol>
        </section>

        <!-- 退步名单：条向**左**长（⚠️ 与进步榜共用一个标尺） -->
        <section class="pboard__col">
          <header class="pboard__head">
            <span class="pboard__headzh zh-title">退步名单</span>
            <span class="pboard__headn num">
              {{ board.regressed.length }} 人<template v-if="regressedHidden > 0">（只画前 {{ regressedBars.length }}）</template>
            </span>
          </header>
          <ol class="pboard__list">
            <li v-for="(bar, i) in regressedBars" :key="`reg-${bar.studentId}`" class="pboard__row">
              <span class="pboard__rank num">{{ i + 1 }}</span>
              <span class="pboard__who">
                <span class="pboard__name">{{ bar.name ?? '—' }}</span>
                <span class="pboard__id num">#{{ bar.studentId }}</span>
              </span>
              <span class="pboard__barwrap pboard__barwrap--reg">
                <svg class="pboard__svg" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
                  <rect
                    class="pboard__fill pboard__fill--red pboard__fill--rtl"
                    :x="(100 - bar.width).toFixed(3)"
                    y="0"
                    :width="bar.width.toFixed(3)"
                    height="10"
                  />
                </svg>
              </span>
              <span class="pboard__val num pboard__val--red">{{ changeText(bar.change) }}</span>
            </li>
          </ol>
        </section>
      </div>

      <figcaption class="pboard__caption">
        <span v-if="caption">{{ caption }}</span>
        <span class="pboard__fine">
          两侧共用一个标尺（最长的一格 =
          <strong class="num">{{ maxAbs.toFixed(2) }}%</strong>）·
          不变 <strong class="num">{{ board.unchanged }}</strong> 人 ·
          测不足两次 <strong class="num">{{ board.unmeasured }}</strong> 人 ·
          <code>top_n = {{ board.top_n }}</code>
        </span>
      </figcaption>
    </template>
  </figure>
</template>

<style scoped>
/* ⚠️ 一个色值都不写死：全部走 tokens.css 的自定义属性。 */
.pboard {
  margin: 0;
  min-width: 0;
}

.pboard__cols {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.pboard__col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.pboard__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
  padding-block-end: var(--space-1);
  border-block-end: var(--lane-thick) solid var(--ink);
}

.pboard--on-ink .pboard__head {
  border-block-end-color: var(--paper);
}

.pboard__headzh {
  font-size: var(--fs-body);
  font-weight: var(--fw-zh-title-700);
}

.pboard--on-ink .pboard__headzh {
  font-size: var(--fs-bs-subtitle);
  color: var(--paper);
}

.pboard__headn {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.pboard--on-ink .pboard__headn {
  font-size: var(--fs-bs-small);
  color: var(--paper-faint);
}

.pboard__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.pboard__row {
  display: grid;
  grid-template-columns: 1.6em minmax(5em, auto) minmax(40px, 1fr) 5em;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--fs-small);
}

.pboard--on-ink .pboard__row {
  /* ⚠️ 大屏的字号下限是 18px */
  font-size: var(--fs-bs-small);
  grid-template-columns: 2em minmax(6em, auto) minmax(50px, 1fr) 6.5em;
}

.pboard__rank {
  color: var(--ink-faint);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.pboard--on-ink .pboard__rank {
  color: var(--paper-faint);
}

.pboard__who {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  min-width: 0;
  overflow: hidden;
}

.pboard__name {
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pboard--on-ink .pboard__name {
  color: var(--paper);
}

.pboard__id {
  color: var(--ink-faint);
  font-size: 0.86em;
  white-space: nowrap;
}

.pboard--on-ink .pboard__id {
  color: var(--paper-faint);
  /* ⚠️ 大屏的字号下限是 18px：`0.86em` 在纸上（13px → 11px）没问题，
     在投影上（18px → 15.5px）就破了下限，故这一档收回 1em。 */
  font-size: 1em;
}

.pboard__barwrap {
  display: block;
  min-width: 0;
  position: relative;
}

.pboard__svg {
  display: block;
  width: 100%;
  height: 12px;
}

.pboard--on-ink .pboard__svg {
  height: 18px;
}

.pboard__fill {
  transform-origin: left center;
  animation: pboard-grow var(--dur-lane) var(--ease-lane) both;
}

/* 退步那一侧的条从**右端**长出来（中轴在右） */
.pboard__fill--rtl {
  transform-origin: right center;
}

@keyframes pboard-grow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.pboard__fill--moss {
  fill: var(--moss-on-paper);
}
.pboard__fill--red {
  fill: var(--red-on-paper);
}

.pboard--on-ink .pboard__fill--moss {
  fill: var(--moss-on-ink);
}
.pboard--on-ink .pboard__fill--red {
  fill: var(--red-on-ink);
}

.pboard__val {
  text-align: right;
  font-variant-numeric: tabular-nums lining-nums;
  font-weight: 600;
}

.pboard__val--moss {
  color: var(--moss-on-paper);
}
.pboard__val--red {
  color: var(--red-on-paper);
}

.pboard--on-ink .pboard__val--moss {
  color: var(--moss-on-ink);
}
.pboard--on-ink .pboard__val--red {
  color: var(--red-on-ink);
}

.pboard__caption {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-block-start: var(--space-3);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.pboard--on-ink .pboard__caption {
  font-size: var(--fs-bs-small);
  color: var(--paper-soft);
}

.pboard__fine {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.pboard--on-ink .pboard__fine {
  font-size: var(--fs-bs-small);
  color: var(--paper-faint);
}

/* ---------------------------------------------------------------- 空态 */
.pboard__empty {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--paper-sunken);
  border-inline-start: var(--lane-thick) solid var(--rule-hairline);
}

.pboard--on-ink .pboard__empty {
  background: var(--ink-sunken);
  border-inline-start-color: var(--rule-hairline-on-ink);
}

.pboard__empty-mark {
  width: 132px;
  height: auto;
}

.pboard__empty-line {
  stroke: var(--ink);
  stroke-opacity: 0.34;
  stroke-width: 3;
}

.pboard__empty-hair {
  stroke: var(--track);
  stroke-opacity: 0.55;
  stroke-width: 1;
  stroke-dasharray: 6 5;
}

.pboard--on-ink .pboard__empty-line {
  stroke: var(--paper);
}

.pboard--on-ink .pboard__empty-hair {
  stroke: var(--track-on-ink);
}

.pboard__empty-title {
  font-size: var(--fs-body);
  font-weight: var(--fw-zh-title-700);
}

.pboard--on-ink .pboard__empty-title {
  font-size: var(--fs-bs-subtitle);
  color: var(--paper);
}

.pboard__empty-note {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.pboard--on-ink .pboard__empty-note {
  font-size: var(--fs-bs-small);
  color: var(--paper-soft);
}
</style>
