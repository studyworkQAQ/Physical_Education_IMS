<script lang="ts">
/** 一行。⚠️ 普通 `<script>`：本类型要被调用方 `import type`，而 `<script setup>`
 *  里不能有 ES module 导出（与 `RpeTrend.vue` / `LayerDonut.vue` 同一个办法）。 */
export interface CompletionRow {
  /** 后端那一格的键（`red` / `yellow` / `green` / `insufficient_data`）。 */
  readonly key: string
  /** 中文标签（由 `present.ts` 的 `LAYER_SLOTS` 给，本组件不自己映射）。 */
  readonly zh: string
  /** `.cbars__bar--*` 的那一档（`insufficient_data` 是 `default` = 中性）。 */
  readonly level: 'red' | 'amber' | 'moss' | 'default'
  /** 这一层的名册人数。 */
  readonly students: number
  /** 这一层里「分母非零、算得出完成率」的人数。 */
  readonly measured: number
  /** ⚠️ **可能是 `null`**：那一层没有人时后端给 `null`（计划约束第 10 条：
   *  「不知道」不得显示成「0」）。`null` → 显示「—」+ 一个空的虚线轨道，
   *  **不是**一条 0% 的实心条。 */
  readonly rate: number | null
}
</script>

<script setup lang="ts">
/**
 * `charts/CompletionBars.vue` —— **三层完成率**（手写 SVG，计划第 3 节：不引 ECharts）。
 *
 * ---------------------------------------------------------------------------
 * 数据形状（⚠️ 本组件**不发请求**：数据由页面给，于是「读哪个端点」只有一个住址）
 * ---------------------------------------------------------------------------
 * 一个 {@link CompletionRow} 数组，来自 `checkin_rate_by_layer`。两个消费者给的是
 * **同一个形状**（`{students, measured, rate}` 三格）：
 *  - 大屏：`GET /api/dashboard/class/{id}` 的 `blocks.checkin_rate_by_layer`；
 *  - 班级周报：`GET /api/dashboard/weekly-class-report/{id}` 的 `checkin_rate_by_layer`。
 *  实测演示库（教学班 1）：
 *  `{"red":{"students":3,"measured":3,"rate":0.5},
 *    "yellow":{"students":17,"measured":17,"rate":0.6275},
 *    "green":{"students":10,"measured":10,"rate":0.55},
 *    "insufficient_data":{"students":0,"measured":0,"rate":null}}`
 *  ⚠️ **第四档的 `rate` 就是 `null`**（那一层 0 人）—— 那是本组件最要紧的一格，
 *  也是计划约束第 10 条点名的四个可空字段之一。
 *
 * ---------------------------------------------------------------------------
 * SVG 实现要点（⚠️ 与 `LayerDonut` / `ProgressBoard` 同一条取舍，理由逐字写在下面）
 * ---------------------------------------------------------------------------
 *  - **条形本体是 SVG**（一个 `<rect>` 的轨道 + 一个 `<rect>` 的填充），
 *    而**文字是 HTML**。理由：SVG 的 `viewBox` 是等比缩放的，字会跟着一起缩，
 *    而大屏有 **18px 的字号下限**（投影场景）—— 一个被缩放到 1.7× 的 11px 字
 *    既过不了下限、也在投影上糊掉。故这里让 SVG 只负责「画图形」、
 *    CSS 负责「排字」，两边各做自己擅长的事。
 *  - ⚠️ 于是那个 `viewBox="0 0 100 10"` 配 `preserveAspectRatio="none"`：
 *    轨道的宽度**就是百分比**（`x=0..100`），拉伸不会失真，因为它只有矩形、
 *    没有文字也没有圆（圆被拉成椭圆才是 `none` 的坑）。
 *  - ⚠️ 虚线轨道用 `vector-effect="non-scaling-stroke"`：`preserveAspectRatio="none"`
 *    会把描边一起拉扁，这一格让描边宽度**不受**缩放影响。
 *  - **`rate === null` 的那一档刻意画成「空的虚线轨道」**：一条 0 长度的实心条
 *    会被读成「完成率是 0%」，而那是一句假话（后端说的是「这一层没有人、
 *    完成率无定义」）。数值那一格同时显示「—」。
 *  - ⚠️ 动效只有一处：填充条从左**长出来**（`transform: scaleX(0→1)`，
 *    `transform-origin: left`），用既有的 `--dur-base` / `--ease-out`。
 *    它是计划第 2 节动效①（分道线从左到右划出）在条形上的同一母题。
 */
import { computed } from 'vue'

import { UNKNOWN } from '../../present'

interface Props {
  rows: readonly CompletionRow[]
  /** `board` = 教师大屏那一档（Plan 05B 翻浅底之后）：只抬字号（18px 下限）与
   *  环/条的尺寸，**颜色与浅底各页同一套**（`--*-on-ink` 一族令牌已删）。 */
  tone?: 'paper' | 'board'
  caption?: string
}

const props = withDefaults(defineProps<Props>(), { tone: 'paper', caption: '' })

/** 只画有人/有数的那几档？⚠️ **不**：四档一律画。
 *  少画一档的失效形态是「大屏上只有三条，教师以为这个班只有三层」。
 *  而 `insufficient_data` 那一档在演示库上恒为 0 人 + `rate: null`，
 *  它出现在图上正是「这一层没有人」这句话的可视化。 */
const visible = computed(() => props.rows)

const isEmpty = computed(() => props.rows.length === 0)

function pct(rate: number | null): string {
  return rate === null ? UNKNOWN : `${(rate * 100).toFixed(1)}%`
}

/** 填充条的宽度（0–100，与 `viewBox` 的宽度同口径）。`null` → 0（且不画填充）。 */
function widthOf(rate: number | null): number {
  if (rate === null) return 0
  return Math.max(0, Math.min(100, rate * 100))
}

const summary = computed(() => {
  if (isEmpty.value) return '没有按层的完成率数据'
  const parts = props.rows.map(
    (r) => `${r.zh} ${r.rate === null ? '无定义' : `${(r.rate * 100).toFixed(1)}%`}（${r.measured}/${r.students} 人）`,
  )
  return `三层完成率：${parts.join('，')}`
})
</script>

<template>
  <figure class="cbars" :class="props.tone === 'board' ? 'cbars--board' : ''">
    <div v-if="isEmpty" class="cbars__empty">
      <p class="cbars__empty-title zh-title">没有按层的完成率</p>
      <p class="cbars__empty-note">
        后端没有给 <code>checkin_rate_by_layer</code> 的任何一档。
        ⚠️ 这与「三层都是 0%」是两件事（计划约束第 10 条）。
      </p>
    </div>

    <template v-else>
      <div class="cbars__list" role="img" :aria-label="summary">
        <div v-for="row in visible" :key="row.key" class="cbars__row">
          <span class="cbars__zh">{{ row.zh }}</span>

          <span class="cbars__barwrap">
            <svg class="cbars__svg" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
              <!-- 轨道。⚠️ `rate === null` 时换成**虚线空轨道**（见文件头那段） -->
              <rect
                v-if="row.rate !== null"
                class="cbars__track"
                x="0"
                y="0"
                width="100"
                height="10"
              />
              <rect
                v-else
                class="cbars__track cbars__track--void"
                x="0.5"
                y="0.5"
                width="99"
                height="9"
                vector-effect="non-scaling-stroke"
              />
              <rect
                v-if="row.rate !== null"
                class="cbars__fill"
                :class="`cbars__fill--${row.level}`"
                x="0"
                y="0"
                :width="widthOf(row.rate).toFixed(3)"
                height="10"
              />
            </svg>
          </span>

          <!-- ⚠️ `null` → 「—」，不是 `0%` -->
          <span class="cbars__val num" :class="{ 'cbars__val--void': row.rate === null }">
            {{ pct(row.rate) }}
          </span>
          <span class="cbars__n num">{{ row.measured }} / {{ row.students }} 人</span>
        </div>
      </div>

      <figcaption v-if="caption" class="cbars__caption">{{ caption }}</figcaption>
    </template>
  </figure>
</template>

<style scoped>
/* ⚠️ 一个色值都不写死：全部走 tokens.css 的自定义属性。 */
.cbars {
  margin: 0;
  min-width: 0;
}

.cbars__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

/* 四列网格：中文标签 / 条 / 百分数 / 人数。
   ⚠️ 用网格而不是 flex：四行的条因此**左端对齐、右端也对齐**，
   而 flex 的 `1fr` 在标签字数不同时会给出不等宽的条。
   ⚠️⚠️ 两端那三列一律 `auto`、只有条那一列是 `minmax(…, 1fr)`：`auto` 列取
   **本列各行内容的最大宽**（故仍然对齐），而它的最小内容宽是可测的
   —— 实测这一行的最小内容宽是 366px（标签「数据不足」72 + 条 60 + 「62.7%」90
   + 「17 / 17 人」108 + 三个 gap 36）。⚠️ 此前写的是 `5.5em`/`8.5em` 两个固定列，
   最小宽 467px，而大屏的 4 列面板只有 418.7px → **横向溢出**。 */
.cbars__row {
  display: grid;
  grid-template-columns: auto minmax(60px, 1fr) auto auto;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--fs-small);
}

.cbars--board .cbars__row {
  /* ⚠️ 大屏的字号下限是 18px */
  font-size: var(--fs-bs-small);
}

.cbars__zh {
  color: var(--ink-soft);
  white-space: nowrap;
}

.cbars__barwrap {
  display: block;
  min-width: 0;
}

.cbars__svg {
  display: block;
  width: 100%;
  height: 14px;
}

.cbars--board .cbars__svg {
  height: 20px;
}

.cbars__track {
  fill: var(--surface-sunken);
}

/* `rate === null`：空的虚线轨道（「这一层没有人」而不是「完成率 0%」） */
.cbars__track--void {
  fill: none;
  /* ⚠️ 虚线轨道用 --border-strong（1.72:1）而不是 --border（1.28:1）：
     它要表达「这一层没有人」，得看得见（图形对比 WCAG 1.4.11 要 3:1 的是
     **控件**边界；这一格是数据图形，取「看得清」的那一档即可）。 */
  stroke: var(--border-strong);
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.cbars__fill {
  transform-origin: left center;
}

.cbars__fill--red {
  fill: var(--red);
}
.cbars__fill--amber {
  fill: var(--amber);
}
.cbars__fill--green {
  fill: var(--green);
}
.cbars__fill--default {
  fill: var(--ink-faint);
}

.cbars__val {
  text-align: right;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums lining-nums;
}

.cbars__val--void {
  color: var(--ink-faint);
  letter-spacing: 0.06em;
}

.cbars__n {
  text-align: right;
  color: var(--ink-faint);
  font-variant-numeric: tabular-nums lining-nums;
  white-space: nowrap;
}

.cbars__caption {
  margin-block-start: var(--space-2);
  font-size: var(--fs-small);
  color: var(--ink-faint);
}

.cbars--board .cbars__caption {
  font-size: var(--fs-bs-small);
}

/* ---------------------------------------------------------------- 空态 */
.cbars__empty {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-accent) solid var(--border);
}

.cbars__empty-title {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.cbars--board .cbars__empty-title {
  font-size: var(--fs-bs-subtitle);
}

.cbars__empty-note {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.cbars--board .cbars__empty-note {
  font-size: var(--fs-bs-small);
}
</style>
