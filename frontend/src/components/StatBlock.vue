<script setup lang="ts">
/**
 * `StatBlock.vue` —— 一个大数字 + 它的标签（+ 可选的单位与一行说明）。
 *
 * ⚠️⚠️ **Plan 05B：数字滚动删掉了**（计划 §3 的动效第 ③ 条，控制者裁定）。
 * 旧版本在这里跑一个 `requestAnimationFrame` 的 easeOutQuint 滚动（900ms，
 * 时长从 `--dur-roll` 读），理由是「计时牌的感觉」。删掉它的三条理由：
 *   ① 用户要「简洁」，而滚动是《田径场年鉴》识别性最强的一处动效；
 *   ② 它是**取证的一个坑**：无头浏览器抓到的是滚动中途那一帧
 *      （Plan 04 Task 2 实测到 95.7 而不是 100.0），于是要靠
 *      `--force-prefers-reduced-motion` 绕开 —— 删掉它，那个坑一起消失；
 *   ③ 大屏每 5 秒切一个班，旧版每切一次就重滚一遍（`Dashboard.vue` 的文件头
 *      为此专门写了「用 `:key` 让它重建而不是变形」那一整段）—— 一个每 5 秒
 *      重新跑一次 900ms 动画的屏幕，在投影上是**干扰**而不是信息。
 * 于是本组件今天**不含任何动画、不含任何 `requestAnimationFrame`**：
 * `value` 是什么就显示什么（`toFixed(decimals)`，不做别的加工）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️「不知道」不得显示成「0」（计划约束第 10 条）
 * ---------------------------------------------------------------------------
 * `value` 为 `null` / `undefined` 时本组件渲染一个 `.unknown` 的破折号「—」，
 * **不是** `0`、不是 `0%`、不是 `0.0`。已知会出现 null 的字段：
 * `completion_rate`（无处方时）、`checkin_rate_by_layer[层].rate`（那一层没人时）、
 * `mean_rpe`（那一周没有快评时）、`normalized_score`（样本不足时）。
 * ⚠️ 这一档**在组件里拦**而不是让每个调用方自己判：漏判的失效形态是「大屏上
 * 一个 0%」，而它在投影上看起来完全正常 —— 那是本项目最响的一条纪律要防的形状。
 */
import { computed } from 'vue'

import { UNKNOWN } from '../present'

interface Props {
  /** ⚠️ `null` / `undefined` → 渲染「—」。这是本组件存在的理由之一。 */
  value: number | null | undefined
  /** 指标名（给人看的一行）。 */
  label: string
  /** 单位，例如 `%` / `min` / `次`。 */
  unit?: string
  /** 小数位数。⚠️ 一律 `toFixed`，不做四舍五入之外的加工。 */
  decimals?: number
  /** 排版档。`board` = 教师大屏（字号抬到 `--fs-bs-*`，下限 18px）。
   *  ⚠️ 它**不再**管底色：大屏在 Plan 05B 翻成了浅底，全站只有一套颜色。 */
  tone?: 'paper' | 'board'
  /** 字号档。`hero` = 最大的那一档数字。 */
  size?: 'hero' | 'display' | 'body'
  /** 标签下面的一行补充说明（可选）。 */
  caption?: string
  /** 语义色，用于「这个数是好是坏」（可选）。⚠️ 只染数字，不染标签。 */
  level?: 'default' | 'red' | 'amber' | 'moss'
}

const props = withDefaults(defineProps<Props>(), {
  unit: '',
  decimals: 0,
  tone: 'paper',
  size: 'display',
  caption: '',
  level: 'default',
})

/** ⚠️ 这一格是本组件最重要的判断（见文件顶部那段）。 */
const isUnknown = computed(() => props.value === null || props.value === undefined)

/** 直接显示终值（滚动已删）。 */
const text = computed(() => (props.value ?? 0).toFixed(props.decimals))

const valueClass = computed(() => [
  'stat__value',
  props.size === 'hero' ? 'num--hero' : 'num',
  `stat__value--${props.size}`,
  props.level === 'default' ? '' : `stat__value--${props.level}`,
])
</script>

<template>
  <div class="stat" :class="props.tone === 'board' ? 'stat--board' : ''">
    <span class="stat__label caps">{{ label }}</span>
    <span class="stat__figure">
      <!-- ⚠️ null → 「—」，不是 0 -->
      <span v-if="isUnknown" class="unknown stat__value stat__value--unknown" aria-label="无数据"
        >{{ UNKNOWN }}</span
      >
      <span v-else :class="valueClass">{{ text }}</span>
      <span v-if="unit && !isUnknown" class="stat__unit">{{ unit }}</span>
    </span>
    <span v-if="caption" class="stat__caption">{{ caption }}</span>
  </div>
</template>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.stat__label {
  color: var(--ink-soft);
}

.stat__figure {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  /* 数字与单位在基线上对齐 */
  min-width: 0;
}

.stat__value {
  color: var(--ink);
  /* ⚠️ tabular-nums 由 .num / .num--hero 带上（base.css），这里不重复 */
}

.stat__value--display {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-display);
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings: 'tnum' 1, 'lnum' 1;
  letter-spacing: var(--tracking-title);
}

.stat__value--body {
  font-size: var(--fs-title);
}

/* ⚠️ 三个语义档：色值一律取自 tokens.css，且对白底都过 AA
   （红 5.44 / 琥珀 5.57 / 绿 5.62，实算表见 Plan 05B 报告 §6）。 */
.stat__value--red {
  color: var(--red);
}
.stat__value--amber {
  color: var(--amber);
}
.stat__value--moss {
  color: var(--green);
}

.stat__value--unknown {
  font-size: var(--fs-title);
}

.stat__unit {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-small);
  color: var(--ink-faint);
}

.stat__caption {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

/* ------------------------------------------------- 大屏那一档（投影：18px 下限）
   ⚠️ 翻浅底之后这一组**只管字号**，不再管颜色 —— 旧版那 6 条
      `.stat--on-ink .xxx { color: var(--*-on-ink) }` 全部删掉了
      （`--*-on-ink` 一族令牌已不存在，留着就是死配置）。 */
.stat--board .stat__label {
  font-size: var(--fs-bs-small);
}

.stat--board .stat__value--display {
  font-size: var(--fs-bs-display);
}

.stat--board .stat__value--body {
  font-size: var(--fs-bs-subtitle);
}

.stat--board .stat__value--unknown {
  font-size: var(--fs-bs-subtitle);
}

.stat--board .stat__caption,
.stat--board .stat__unit {
  font-size: var(--fs-bs-small);
}
</style>
