<script lang="ts">
/**
 * ⚠️ 这一格是**普通 `<script>`**（不是 `<script setup>`）：`RpePoint` 要被调用方
 * `import type` 进来，而 `<script setup>` 里不能有 ES module 导出
 * （编译器会当场报 “`<script setup>` cannot contain ES module exports”）。
 * `ApiErrorBanner.vue` 导出 `useApiError` 用的是同一个办法（两个 script 块会被
 * 合并成同一个模块，故 setup 块里可以直接用这里声明的类型）。
 */

/** 一个点。⚠️ `rpe` **不允许 null**：「没交」的课次请在调用方就剔掉 ——
 *  把 null 折成 0 画上去，就是把「不知道」讲成「毫无感觉」（约束第 10 条），
 *  而 0 在这套量表上是一次真实的、有意义的作答。 */
export interface RpePoint {
  /** 0–10 的整数（`RpeRecordRead.rpe`）。 */
  rpe: number
  /** 横轴第一行（本仓给的是课次日期的 `MM-DD`）。 */
  label: string
  /** 横轴第二行（本仓给的是「第 N 节」），可省。 */
  sub?: string
}
</script>

<script setup lang="ts">
/**
 * `charts/RpeTrend.vue` —— **我的课堂 RPE 趋势**（手写 SVG，计划第 3 节：不引 ECharts）。
 *
 * ---------------------------------------------------------------------------
 * 数据形状（⚠️ 本组件**不发请求**：数据由页面给，于是「读哪个端点」只有一个住址）
 * ---------------------------------------------------------------------------
 * `points` 是一个**已按时间升序**的 {@link RpePoint} 数组（三格：`rpe` / `label` / `sub`）。
 * 本页面的唯一数据源是 `endpoints.ts` 的 `listMyRpeRecords`
 * （`GET /api/rpe-records` 翻页收集 + 客户端按 `student_id` 过滤），
 * 横轴文字由课次表（`GET /api/class-sessions`）join 出来。
 *
 * ⚠️ RPE 的值域是 **0–10**，所有者是 `app/domain/prescription/assembler.py` 的
 * `_RPE_MIN` / `_RPE_MAX`（那里逐字写了「**不是** Borg 经典的 6–20」）。
 *
 * ---------------------------------------------------------------------------
 * 图上的三条线各有出处（不是我挑的装饰）
 * ---------------------------------------------------------------------------
 *  - **9–10 的红色带**：`RED_RPE_SUSTAINED` = 「RPE 连续 ≥ 9 分」（`alerts.py:180-181`）。
 *    学生在这张图上看得见自己离那条线有多近，是本页面存在的理由。
 *  - **7 分那条虚线**：`YELLOW_CLASS_RPE_HIGH` = 「课堂 RPE 均值 > 7 分」（`alerts.py:184-185`）。
 *    ⚠️ 它是**班级均值**的阈值、不是个人的，故图上写的是「班均阈值」而不是「你的上限」。
 *  - **0 / 5 / 10 三对分道线**：`lane.css` 的母题（粗线 3px 墨 + 偏移 6px 的 1px 砖红）
 *    在图表尺度上的一次复用 —— 于是这张图与页面其余部分看起来是同一个系统。
 *
 * ⚠️ 动效只有一处：折线**从左到右划出**（`pathLength="100"` + `stroke-dashoffset`），
 *  用的是 `--dur-lane` / `--ease-lane` 两个既有令牌。它是计划第 2 节动效①
 *  （「分道线从左到右划出」）在折线上的同一个母题，**不是**第四种动效。
 */
import { computed } from 'vue'

interface Props {
  points: readonly RpePoint[]
  /** 图下方那行小字（本仓用它写「共 N 次 · 均值 X 分」）。 */
  caption?: string
}

const props = withDefaults(defineProps<Props>(), { caption: '' })

/* --------------------------------------------------------------- 画布几何
   ⚠️ 用固定的 viewBox + `width:100%; height:auto`：等比缩放，于是文字不会变形。
      320 × 168 是 375px 视口减去两侧 16px 出血内边距之后的**内容宽**（343px）
      再留一点余量；渲染时它会被拉到 343px 宽。                               */
const W = 320
const H = 168
const PAD_L = 24
const PAD_R = 10
const PAD_T = 20
const PAD_B = 30
const PLOT_W = W - PAD_L - PAD_R
const PLOT_H = H - PAD_T - PAD_B

/** RPE 的值域两端（与后端 `_RPE_MIN` / `_RPE_MAX` 逐字相同）。 */
const RPE_MIN = 0
const RPE_MAX = 10
/** `RED_RPE_SUSTAINED` 的阈值。 */
const RED_FROM = 9
/** `YELLOW_CLASS_RPE_HIGH` 的阈值（班级均值）。 */
const AMBER_FROM = 7

function yOf(rpe: number): number {
  return PAD_T + PLOT_H * (1 - (rpe - RPE_MIN) / (RPE_MAX - RPE_MIN))
}

function xOf(i: number): number {
  const n = props.points.length
  if (n <= 1) return PAD_L + PLOT_W / 2
  return PAD_L + (PLOT_W * i) / (n - 1)
}

const isEmpty = computed(() => props.points.length === 0)
const isSingle = computed(() => props.points.length === 1)

/** 折线的 `points` 属性。 */
const polyline = computed(() =>
  props.points.map((p, i) => `${xOf(i).toFixed(2)},${yOf(p.rpe).toFixed(2)}`).join(' '),
)

/** 每个点：坐标 + 显示串。 */
const dots = computed(() =>
  props.points.map((p, i) => ({
    cx: xOf(i),
    cy: yOf(p.rpe),
    rpe: p.rpe,
    label: p.label,
    sub: p.sub ?? '',
    /** 数字标在点的上方；贴着顶（rpe=10）时翻到下方，否则会被裁掉。 */
    textY: p.rpe >= RPE_MAX - 0.6 ? yOf(p.rpe) + 14 : yOf(p.rpe) - 8,
    hot: p.rpe >= RED_FROM,
  })),
)

/** 三对分道线（0 / 5 / 10）。 */
const gridlines = computed(() =>
  [RPE_MIN, (RPE_MIN + RPE_MAX) / 2, RPE_MAX].map((v) => ({
    value: v,
    y: yOf(v),
    label: String(v),
  })),
)

const redBand = computed(() => ({
  y: yOf(RPE_MAX),
  height: Math.max(0, yOf(RED_FROM) - yOf(RPE_MAX)),
}))

const amberLine = computed(() => yOf(AMBER_FROM))

/** `aria-label`：一张图对读屏的人要能讲成一句话。 */
const summary = computed(() => {
  if (isEmpty.value) return '还没有课堂快评记录'
  const values = props.points.map((p) => p.rpe)
  const last = values[values.length - 1]
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  return `课堂 RPE 趋势：共 ${values.length} 次，最近一次 ${last} 分，均值 ${mean.toFixed(1)} 分（满标 10 分）`
})
</script>

<template>
  <figure class="trend">
    <!-- ⚠️ 空态**不画 SVG**：一张空的坐标系会被读成「我一直是 0 分」，
         而 0 分在这套量表上是「毫无感觉」—— 那是一次真实作答（约束第 10 条）。 -->
    <div v-if="isEmpty" class="trend__empty">
      <svg class="trend__empty-mark" viewBox="0 0 48 24" aria-hidden="true">
        <path d="M2 18 H46" class="trend__empty-line" />
        <path d="M2 22 H46" class="trend__empty-hair" />
      </svg>
      <p class="trend__empty-title zh-title">还没有课堂快评记录</p>
      <p class="trend__empty-note">
        老师在课上发起快评、你交过一次之后，这里就会出现一条趋势线。
      </p>
    </div>

    <svg
      v-else
      class="trend__svg"
      :viewBox="`0 0 ${W} ${H}`"
      role="img"
      :aria-label="summary"
      preserveAspectRatio="xMidYMid meet"
    >
      <title>课堂 RPE 趋势</title>
      <desc>{{ summary }}</desc>

      <!-- 凹槽底：计时牌的那一块 -->
      <rect class="trend__well" :x="PAD_L" :y="PAD_T" :width="PLOT_W" :height="PLOT_H" />

      <!-- 9–10 的红色带（RED_RPE_SUSTAINED 的阈值） -->
      <rect class="trend__redband" :x="PAD_L" :y="redBand.y" :width="PLOT_W" :height="redBand.height" />
      <text class="trend__redlabel" :x="PAD_L + PLOT_W - 2" :y="redBand.y + 10" text-anchor="end">
        ≥9 连续三次 → 减量
      </text>

      <!-- 三对分道线 -->
      <g v-for="line in gridlines" :key="line.value">
        <line class="trend__grid" :x1="PAD_L" :y1="line.y" :x2="PAD_L + PLOT_W" :y2="line.y" />
        <text class="trend__tick num" :x="PAD_L - 6" :y="line.y + 3" text-anchor="end">
          {{ line.label }}
        </text>
      </g>

      <!-- 班均阈值 7 分（虚线，不是分道线：它是「参考」而不是「刻度」） -->
      <line class="trend__amber" :x1="PAD_L" :y1="amberLine" :x2="PAD_L + PLOT_W" :y2="amberLine" />
      <text class="trend__amberlabel" :x="PAD_L + 2" :y="amberLine - 4">班均阈值 7</text>

      <!-- 折线：从左到右划出（母题①） -->
      <polyline
        v-if="!isSingle"
        class="trend__line"
        :points="polyline"
        pathLength="100"
        fill="none"
      />

      <!-- 点与数字 -->
      <g v-for="(dot, i) in dots" :key="`${dot.label}-${i}`">
        <circle class="trend__dot" :class="{ 'trend__dot--hot': dot.hot }" :cx="dot.cx" :cy="dot.cy" r="4" />
        <text class="trend__value num" :class="{ 'trend__value--hot': dot.hot }" :x="dot.cx" :y="dot.textY" text-anchor="middle">
          {{ dot.rpe }}
        </text>
        <text class="trend__xlabel" :x="dot.cx" :y="H - PAD_B + 14" text-anchor="middle">
          {{ dot.label }}
        </text>
        <text v-if="dot.sub" class="trend__xsub" :x="dot.cx" :y="H - PAD_B + 25" text-anchor="middle">
          {{ dot.sub }}
        </text>
      </g>
    </svg>

    <figcaption v-if="caption || isSingle" class="trend__caption">
      <span v-if="isSingle" class="trend__single">
        只有一次记录 —— 一个点画不出趋势，先交下一次快评。
      </span>
      <span v-if="caption">{{ caption }}</span>
    </figcaption>
  </figure>
</template>

<style scoped>
/* ⚠️ 一个色值都不写死：全部走 tokens.css 的自定义属性（设计令牌的唯一住址）。
   ⚠️ SVG 的 `fill` / `stroke` 一律写在 CSS 里而不是 presentation attribute 上：
      `var()` 在属性里虽然今天的三个引擎都吃，但在 CSS 里是**规范保证**的。 */
.trend {
  margin: 0;
}

.trend__svg {
  width: 100%;
  height: auto;
  overflow: visible;
}

.trend__well {
  fill: var(--paper-sunken);
}

.trend__redband {
  fill: var(--red-wash);
}

.trend__redlabel {
  fill: var(--red-on-paper);
  font-family: var(--font-body);
  font-size: 9px;
  font-weight: var(--fw-body-500);
}

.trend__grid {
  stroke: var(--ink);
  stroke-width: var(--lane-thick);
  stroke-opacity: 0.16;
}

.trend__tick {
  fill: var(--ink-faint);
  font-size: 10px;
  font-weight: 600;
}

.trend__amber {
  stroke: var(--amber-on-paper);
  stroke-width: var(--lane-thin);
  stroke-dasharray: 4 3;
}

.trend__amberlabel {
  fill: var(--amber-on-paper);
  font-family: var(--font-body);
  font-size: 9px;
}

.trend__line {
  stroke: var(--track);
  stroke-width: 2.5;
  stroke-linejoin: round;
  stroke-linecap: round;
  /* ⚠️ `pathLength="100"` 让 dash 的长度与实际像素无关，于是这一段不用去算折线有多长 */
  stroke-dasharray: 100;
  stroke-dashoffset: 100;
  animation: rpe-draw var(--dur-lane) var(--ease-lane) forwards;
}

@keyframes rpe-draw {
  to {
    stroke-dashoffset: 0;
  }
}

.trend__dot {
  fill: var(--paper-raised);
  stroke: var(--ink);
  stroke-width: 2;
}

.trend__dot--hot {
  stroke: var(--red-on-paper);
  fill: var(--red-wash);
}

.trend__value {
  fill: var(--ink);
  font-family: var(--font-display);
  font-weight: var(--fw-display-800);
  font-size: 13px;
  font-variant-numeric: tabular-nums lining-nums;
}

.trend__value--hot {
  fill: var(--red-on-paper);
}

.trend__xlabel {
  fill: var(--ink-soft);
  font-family: var(--font-data);
  font-size: 9px;
  font-variant-numeric: tabular-nums;
}

.trend__xsub {
  fill: var(--ink-faint);
  font-family: var(--font-body);
  font-size: 8px;
}

/* ------------------------------------------------------------- 空态 */
.trend__empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--paper-sunken);
  border-inline-start: var(--lane-thick) solid var(--rule-hairline);
}

.trend__empty-mark {
  width: 72px;
  height: auto;
}

.trend__empty-line {
  stroke: var(--ink);
  stroke-opacity: 0.28;
  stroke-width: 3;
}

.trend__empty-hair {
  stroke: var(--track);
  stroke-opacity: 0.5;
  stroke-width: 1;
}

.trend__empty-title {
  font-size: var(--fs-body);
  font-weight: var(--fw-zh-title-700);
}

.trend__empty-note {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.trend__caption {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-block-start: var(--space-2);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.trend__single {
  color: var(--amber-on-paper);
}
</style>
