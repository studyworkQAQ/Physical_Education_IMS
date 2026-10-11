<script setup lang="ts">
/**
 * `StatBlock.vue` —— **计时牌**：一个大数字 + 它的标签，载入/变更时**滚动到位**。
 *
 * 计划第 2 节的动效第 ② 条：「数字滚动到位（计时牌的感觉，只用于大屏的关键指标
 * 与学生的本周训练量）」。⚠️ **克制**：它只在这里出现，不要把它铺到每一个数字上。
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'

interface Props {
  /** ⚠️ `null` / `undefined` → 渲染「—」。这是本组件存在的理由之一。 */
  value: number | null | undefined
  /** 指标名（给人看的一行）。 */
  label: string
  /** 单位，例如 `%` / `min` / `次`。 */
  unit?: string
  /** 小数位数。⚠️ 一律 `toFixed`，不做四舍五入之外的加工。 */
  decimals?: number
  /** 底色。`ink` = 教师大屏。 */
  tone?: 'paper' | 'ink'
  /** 字号档。`hero` = 计时牌的那个大数字。 */
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

/**
 * 滚动时长**从 CSS 令牌读**（`--dur-roll`），不在这里写第二份字面量。
 * 读不到（SSR、令牌被删）就退回 900ms —— 那是 tokens.css 里今天的值。
 */
function rollDurationMs(): number {
  const fallback = 900
  if (typeof window === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--dur-roll')
    .trim()
  const n = Number.parseFloat(raw)
  if (!Number.isFinite(n) || n <= 0) return fallback
  return raw.endsWith('ms') ? n : n * 1000
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** easeOutQuint —— 与 `--ease-lane` 同一条曲线：冲出去、稳稳停住。 */
function easeOutQuint(t: number): number {
  return 1 - Math.pow(1 - t, 5)
}

const displayed = ref(0)
let frame = 0

function stop(): void {
  if (frame !== 0) {
    cancelAnimationFrame(frame)
    frame = 0
  }
}

function rollTo(target: number): void {
  stop()
  if (prefersReducedMotion()) {
    displayed.value = target
    return
  }
  const from = displayed.value
  if (from === target) return
  const duration = rollDurationMs()
  const startedAt = performance.now()
  const step = (now: number): void => {
    const t = Math.min(1, (now - startedAt) / duration)
    displayed.value = from + (target - from) * easeOutQuint(t)
    if (t < 1) {
      frame = requestAnimationFrame(step)
    } else {
      displayed.value = target
      frame = 0
    }
  }
  frame = requestAnimationFrame(step)
}

watch(
  () => props.value,
  (next) => {
    if (next === null || next === undefined) return
    rollTo(next)
  },
  { immediate: true },
)

onBeforeUnmount(stop)

/** ⚠️ 这一格是本组件最重要的判断（见文件顶部那段）。 */
const isUnknown = computed(() => props.value === null || props.value === undefined)

const text = computed(() => displayed.value.toFixed(props.decimals))

const valueClass = computed(() => [
  'stat__value',
  props.size === 'hero' ? 'num--hero' : 'num',
  `stat__value--${props.size}`,
  props.level === 'default' ? '' : `stat__value--${props.level}`,
  props.tone === 'ink' ? 'stat__value--on-ink' : '',
])
</script>

<template>
  <div class="stat" :class="props.tone === 'ink' ? 'stat--on-ink' : ''">
    <span class="stat__label caps">{{ label }}</span>
    <span class="stat__figure">
      <!-- ⚠️ null → 「—」，不是 0 -->
      <span v-if="isUnknown" class="unknown stat__value stat__value--unknown" aria-label="无数据"
        >—</span
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

.stat--on-ink .stat__label {
  color: var(--paper-soft);
}

.stat__figure {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  /* 数字与单位在基线上对齐 —— 计时牌的那一档 */
}

.stat__value {
  color: var(--ink);
  /* ⚠️ tabular-nums 由 .num / .num--hero 带上（base.css），这里不重复 */
}

.stat__value--on-ink {
  color: var(--paper);
}

.stat__value--display {
  font-family: var(--font-display);
  font-weight: var(--fw-display-800);
  font-size: var(--fs-display);
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings: 'tnum' 1, 'lnum' 1;
}

.stat__value--body {
  font-size: var(--fs-title);
}

.stat__value--red {
  color: var(--red-on-paper);
}
.stat__value--amber {
  color: var(--amber-on-paper);
}
.stat__value--moss {
  color: var(--moss-on-paper);
}

.stat--on-ink .stat__value--red {
  color: var(--red-on-ink);
}
.stat--on-ink .stat__value--amber {
  color: var(--amber-on-ink);
}
.stat--on-ink .stat__value--moss {
  color: var(--moss-on-ink);
}

.stat__value--unknown {
  font-size: var(--fs-title);
}

.stat__unit {
  font-family: var(--font-display);
  font-weight: var(--fw-display-600);
  font-size: var(--fs-small);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-faint);
}

.stat--on-ink .stat__unit {
  color: var(--paper-faint);
}

.stat__caption {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.stat--on-ink .stat__caption {
  color: var(--paper-soft);
}

/* 大屏（投影）：字号一律抬到 --fs-bs-* 那一档，下限 18px */
.stat--on-ink .stat__label {
  font-size: var(--fs-bs-small);
}

.stat--on-ink .stat__value--display {
  font-size: var(--fs-bs-display);
}

.stat--on-ink .stat__value--body {
  font-size: var(--fs-bs-subtitle);
}

.stat--on-ink .stat__caption,
.stat--on-ink .stat__unit {
  font-size: var(--fs-bs-small);
}
</style>
