<script lang="ts">
/**
 * ⚠️ 普通 `<script>`（不是 `<script setup>`）：`LayerCounts` 要被调用方 `import type`
 * 进来，而 `<script setup>` 里不能有 ES module 导出（编译器会当场报错）。
 * 与 `charts/RpeTrend.vue` 的 `RpePoint` 同一个办法。
 */

/** `layer_distribution.by_layer` 的**四个**键（实测逐字：
 *  `{"red": 3, "yellow": 17, "green": 10, "insufficient_data": 0}`）。
 *  ⚠️ 第四档不是分层结果、是「数据不足以分层」，故它**中性着色**。 */
export interface LayerCounts {
  readonly red: number
  readonly yellow: number
  readonly green: number
  readonly insufficient_data: number
}
</script>

<script setup lang="ts">
/**
 * `charts/LayerDonut.vue` —— **分层分布环形图**（手写 SVG，计划第 3 节：不引 ECharts）。
 *
 * ---------------------------------------------------------------------------
 * 数据形状（⚠️ 本组件**不发请求**：数据由页面给，于是「读哪个端点」只有一个住址）
 * ---------------------------------------------------------------------------
 * 一个 {@link LayerCounts}（四个整数）。两个消费者给的是**同一个形状**：
 *  - 大屏：`GET /api/dashboard/class/{id}` 的 `blocks.layer_distribution.by_layer`（现算）；
 *  - 班级周报：`GET /api/dashboard/weekly-class-report/{id}` 的 `layer_distribution.by_layer`
 *    （周日存下来的那一行）。
 *  ⚠️ 两者的**键集与算法逐字相同**（后端守卫
 *  `test_the_dashboard_and_the_stored_report_agree_on_the_same_sunday` 把六个共有键
 *  钉成相等），故一个组件够用、不需要两档。
 *
 * ---------------------------------------------------------------------------
 * SVG 实现要点
 * ---------------------------------------------------------------------------
 *  - **一个 `<circle>` 一段弧**，靠 `stroke-dasharray` + `stroke-dashoffset` 切段：
 *    这是 donut 最省的写法（不用算 `arc` 的大角度标志位，也不会在 100% 那一档
 *    退化成一个点）。⚠️ `pathLength="100"` 是**承重**的：它把周长归一成 100，
 *    于是每段的长度**就是百分比**，不必去算 `2πr`（`RpeTrend.vue` 的折线描边
 *    用的是同一个技巧）。
 *  - `transform="rotate(-90)"` 让第一段从 **12 点**起（否则从 3 点起，
 *    而「红→黄→绿」顺时针从 12 点开始是年鉴/计时牌的读法）。
 *  - ⚠️ **动效只有一处**：环从 0 转到就位（`stroke-dashoffset` 的一次过渡），
 *    用既有的 `--dur-base` / `--ease-out`。它是计划第 2 节动效①
 *    （「从左到右划出」）在环上的同一母题，**不是**第四种动效。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 空态：`total === 0` 时**不画环**
 * ---------------------------------------------------------------------------
 * 一个 0 人的环会被读成「这个班 100% 是某一档」或「画坏了」。计划约束第 10 条
 * 的同一族：「没有」与「0」是两件事。⚠️ 演示库上这一档走不到（5 个班各 20–30 人），
 * 但一个刚建、还没选课的班就是它。
 */
import { computed } from 'vue'

import { LAYER_SLOTS } from '../../present'

interface Props {
  counts: LayerCounts
  /** `board` = 教师大屏那一档（Plan 05B 翻浅底之后）：只抬字号（18px 下限）与
   *  环/条的尺寸，**颜色与浅底各页同一套**（`--*-on-ink` 一族令牌已删）。 */
  tone?: 'paper' | 'board'
  /** 环下方那行小字。 */
  caption?: string
  /** 环心的大标题（缺省「名册」）。 */
  centerLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  tone: 'paper',
  caption: '',
  centerLabel: '名册',
})

const total = computed(() =>
  LAYER_SLOTS.reduce((sum, slot) => sum + (props.counts[slot.key] ?? 0), 0),
)

interface Segment {
  key: string
  zh: string
  level: string
  count: number
  /** 百分比；`total === 0` 时是 `null`（→ 显示「—」，不是 0%）。 */
  pct: number | null
  /** `pathLength="100"` 归一之后的弧长。 */
  dash: number
  /** 累积的偏移（负值 = 顺时针推进）。 */
  offset: number
}

/** ⚠️ 顺序固定 = `LAYER_SLOTS` 的顺序（红→黄→绿→数据不足），
 *  于是环上的分段与图例、与 `CompletionBars` 的三条横向条**同一个序**。 */
const segments = computed<Segment[]>(() => {
  const sum = total.value
  let cursor = 0
  return LAYER_SLOTS.map((slot) => {
    const count = props.counts[slot.key] ?? 0
    const pct = sum === 0 ? null : (count / sum) * 100
    const dash = sum === 0 ? 0 : (count / sum) * 100
    const seg: Segment = {
      key: slot.key,
      zh: slot.zh,
      level: slot.level,
      count,
      pct,
      dash,
      offset: -cursor,
    }
    cursor += dash
    return seg
  })
})

/** 图例（与 `segments` 同源，故不会漂）。 */
const legend = computed(() => segments.value)

const summary = computed(() => {
  if (total.value === 0) return '这个班还没有分层结果（名册 0 人）'
  const parts = segments.value
    .filter((s) => s.count > 0)
    .map((s) => `${s.zh} ${s.count} 人（${(s.pct ?? 0).toFixed(1)}%）`)
  return `分层分布：名册 ${total.value} 人，${parts.join('，')}`
})
</script>

<template>
  <figure class="donut" :class="props.tone === 'board' ? 'donut--board' : ''">
    <div v-if="total === 0" class="donut__empty">
      <svg class="donut__empty-mark" viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="18" class="donut__empty-ring" />
      </svg>
      <p class="donut__empty-title zh-title">还没有分层结果</p>
      <p class="donut__empty-note">
        名册是 <strong class="num">0</strong> 人。⚠️ 这与「四层都是 0%」是两件事：
        分层是批处理产物（<code>stratification_result</code>），一个还没选课、
        或还没跑过每日批处理的班就是这一档。
      </p>
    </div>

    <template v-else>
      <div class="donut__figure">
        <svg
          class="donut__svg"
          viewBox="0 0 120 120"
          role="img"
          :aria-label="summary"
          preserveAspectRatio="xMidYMid meet"
        >
          <title>分层分布</title>
          <desc>{{ summary }}</desc>

          <!-- 凹槽底：一整圈，做「计时牌的那一块」 -->
          <circle class="donut__well" cx="60" cy="60" r="46" pathLength="100" />

          <g transform="rotate(-90 60 60)">
            <circle
              v-for="seg in segments"
              :key="seg.key"
              class="donut__seg"
              :class="`donut__seg--${seg.level}`"
              cx="60"
              cy="60"
              r="46"
              pathLength="100"
              :stroke-dasharray="`${seg.dash.toFixed(4)} ${(100 - seg.dash).toFixed(4)}`"
              :stroke-dashoffset="seg.offset.toFixed(4)"
            />
          </g>

          <!-- 环心：名册人数（计时牌的那个大数字） -->
          <!-- ⚠️ y 的取值被 §4.1 的重叠守卫钉着：大数字的 em 盒（含下行留白）
               与下面那行小标签的 em 盒若相碰 >20% 就会红。58/74 在环放大到
               200px（大屏档）时相碰 7px，故拉开到 56/79。 -->
          <text class="donut__total num" x="60" y="56" text-anchor="middle">{{ total }}</text>
          <text class="donut__centerlabel" x="60" y="79" text-anchor="middle">
            {{ centerLabel }}
          </text>
        </svg>

        <ul class="donut__legend">
          <li v-for="item in legend" :key="item.key" class="donut__legendrow">
            <span class="donut__swatch" :class="`donut__seg--${item.level}`" aria-hidden="true"></span>
            <span class="donut__legendzh">{{ item.zh }}</span>
            <span class="donut__legendnum num">{{ item.count }}</span>
            <!-- ⚠️ `total === 0` 时不画环，故这里的 `pct` 恒非 null；
                 仍然写成 `?? '—'` 是为了「不知道不得显示成 0」那一档不留活口。 -->
            <span class="donut__legendpct num">{{
              item.pct === null ? '—' : `${item.pct.toFixed(1)}%`
            }}</span>
          </li>
        </ul>
      </div>

      <figcaption v-if="caption" class="donut__caption">{{ caption }}</figcaption>
    </template>
  </figure>
</template>

<style scoped>
/* ⚠️ 一个色值都不写死：全部走 tokens.css 的自定义属性。
   ⚠️ SVG 的 `fill` / `stroke` 一律写在 CSS 里而不是 presentation attribute 上
      （`var()` 在属性里虽然三个引擎都吃，但在 CSS 里是规范保证的）。 */
.donut {
  margin: 0;
  min-width: 0;
}

.donut__figure {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-4);
}

.donut__svg {
  flex: 0 0 auto;
  width: 168px;
  height: 168px;
  overflow: visible;
}

/* ⚠️ 大屏那一档把环放大到 200px：viewBox 是 120，故缩放是 1.67×，
   环心那行 11px 的中文标签渲染出来是 18.3px —— 过了 18px 的**字号下限**
   （投影场景）。⚠️ 学生端/办公室那一档是 1.4×（15.4px），那里下限是 11px。
   ⚠️ 不取 220px 的原因在图例那一侧：大屏的分层面板只有 4 列（418.7px），
   220px 的环 + 16px gap 之后图例只剩 182px，而图例一行的最小内容宽实测 182px
   （色块 12 + 「数据不足」72 + 人数 + 百分数 + 三个 gap），于是「数据不足」
   四个字会折成两行 —— 实测截图上就是这么坏的。200px 给图例留出 202px。 */
.donut--board .donut__svg {
  width: 200px;
  height: 200px;
}

.donut__well {
  fill: none;
  stroke: var(--surface-sunken);
  stroke-width: 16;
}

.donut__seg {
  fill: none;
  stroke: currentColor;
  stroke-width: 16;
  /* ⚠️ 段与段之间留一条极窄的缝：一个没有缝的 donut 在投影上会糊成一圈 */
  stroke-linecap: butt;
  /* ⚠️ Plan 05B：「环从 0 扫到满」的 reveal 动效删了（与分道线的 staggered reveal
     同一族；计划 §3 把动效缩到 hover/focus + 大屏轮播那一处）。删掉它还有一个
     实在的好处：15 张截图与重叠守卫取到的是**终态**，不必等动画。 */
}

/* 三色 + 中性档。⚠️ 变体只声明 **`color`**，而弧用 `stroke: currentColor`、
   图例的色块用 `background: currentColor` —— 于是「环上的颜色」与「图例的颜色」
   结构上不可能漂（它们是同一条声明）。
   ⚠️ `insufficient_data` 刻意**不染语义色**：把「数据不足」染成红/黄/绿里的
   任何一个都是撒谎（计划约束第 10 条的同一族）。 */
.donut__seg--red {
  color: var(--red);
}
.donut__seg--amber {
  color: var(--amber);
}
.donut__seg--green {
  color: var(--green);
}
.donut__seg--default {
  color: var(--ink-faint);
}

.donut__total {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: 30px;
  fill: var(--ink);
  font-variant-numeric: tabular-nums lining-nums;
}

.donut__centerlabel {
  font-family: var(--font-ui);
  font-size: 11px;
  fill: var(--ink-faint);
}

/* ---------------------------------------------------------------- 图例 */
.donut__legend {
  flex: 1 1 160px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  list-style: none;
  margin: 0;
  padding: 0;
}

.donut__legendrow {
  /* ⚠️ 三列 `auto` + 色块一列：`auto` 取本列各行内容的最大宽，故四行仍然对齐；
     而它的最小内容宽是**可测**的（12 + 72 + 20 + 54 + 三个 gap 24 = 182px），
     写死 `1fr` 的话中文标签会被挤到折行（实测截图上「数据不足」折成了两行）。 */
  display: grid;
  grid-template-columns: 12px auto auto auto;
  align-items: baseline;
  gap: var(--space-2);
  padding: 2px 0;
  border-block-end: var(--border-hairline);
  font-size: var(--fs-small);
}

.donut--board .donut__legendrow {
  /* ⚠️ 大屏的字号下限是 18px（`--fs-bs-small`）：投影上再小就糊了。 */
  font-size: var(--fs-bs-small);
}

.donut__legendrow:last-child {
  border-block-end: none;
}

.donut__swatch {
  width: 12px;
  height: 12px;
  /* 与环上的弧同一个颜色（`.donut__seg--*` 只声明 `color`，两处都读它） */
  background: currentColor;
}

.donut__legendzh {
  color: var(--ink-soft);
  white-space: nowrap;
}

.donut__legendnum {
  font-weight: 600;
  color: var(--ink);
}

.donut__legendpct {
  color: var(--ink-faint);
  text-align: right;
  white-space: nowrap;
}

.donut__caption {
  margin-block-start: var(--space-2);
  font-size: var(--fs-small);
  color: var(--ink-faint);
}

.donut--board .donut__caption {
  font-size: var(--fs-bs-small);
}

/* ---------------------------------------------------------------- 空态 */
.donut__empty {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-accent) solid var(--border);
}

.donut__empty-mark {
  width: 56px;
  height: auto;
}

.donut__empty-ring {
  fill: none;
  stroke: var(--ink);
  stroke-opacity: 0.28;
  stroke-width: 6;
  stroke-dasharray: 6 5;
}

.donut__empty-title {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.donut--board .donut__empty-title {
  font-size: var(--fs-bs-subtitle);
}

.donut__empty-note {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.donut--board .donut__empty-note {
  font-size: var(--fs-bs-small);
}
</style>
