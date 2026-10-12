<script setup lang="ts">
/**
 * `LaneDivider.vue` —— **分道线母题**（本设计识别性的来源）。
 *
 * 形状：`01 ▬▬▬▬▬▬▬▬▬▬`（粗线 3px `--ink`）+ 下方偏移 6px 的细线 1px `--primary`。
 * ⚠️ **区块分隔一律用它，不用普通 `border`**（计划第 2 节）。
 * ⚠️ 尺寸与动效全在 `styles/lane.css`，本组件**不含一行样式** —— 那是母题的住址。
 *
 * 用法：
 *   <LaneDivider :index="2" label="分层分布" />
 *   <LaneDivider :index="1" tone="ink" level="red" />   ← 教师大屏（深底）上的预警区块
 */
import { computed } from 'vue'

interface Props {
  /** 道次编号（1 起）。⚠️ 它同时驱动 staggered reveal 的 `animation-delay`：
   *  第 N 块延迟 (N−1) × 60ms（`--dur-base`）。 */
  index?: number
  /** 右端的拉丁/中文小标题（可选）。⚠️ 它是**装饰性**的重复，故 `aria-hidden`：
   *  调用方应当已经有一个真的 `<h2>`。 */
  label?: string
  /** 底色。`ink` = 教师大屏那一档（粗线换成 `--paper`、细线换成 `--primary`）。 */
  tone?: 'paper' | 'ink'
  /** 语义变体。⚠️ **只换细线的颜色**，粗线永远是墨/纸 —— 母题的形状不能被语义色
   *  改掉，否则「这是一条分道线」与「这是一条红色预警」会混成一件事。 */
  level?: 'default' | 'red' | 'amber' | 'moss'
}

const props = withDefaults(defineProps<Props>(), {
  index: 1,
  label: '',
  tone: 'paper',
  level: 'default',
})

/** 补零到两位：`01` `02` …（计时牌/年鉴的排法）。 */
const displayNumber = computed(() => String(Math.max(0, props.index)).padStart(2, '0'))

/** 传给 CSS 的 `--lane-index`：第一块延迟 0，之后每块 +60ms。 */
const laneIndex = computed(() => Math.max(0, props.index - 1))

const classes = computed(() => [
  'lane',
  props.tone === 'ink' ? 'lane--on-ink' : '',
  props.level === 'default' ? '' : `lane--${props.level}`,
])
</script>

<template>
  <div :class="classes" :style="{ '--lane-index': laneIndex }">
    <span class="lane__num num" aria-hidden="true">{{ displayNumber }}</span>
    <span class="lane__rule" aria-hidden="true"></span>
    <span v-if="label" class="lane__label" aria-hidden="true">{{ label }}</span>
  </div>
</template>
