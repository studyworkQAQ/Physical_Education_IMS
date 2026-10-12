<script setup lang="ts">
/**
 * `SectionHead.vue` —— **区块序号 + 拉丁小标题 + 一条细规则线**。
 *
 * ⚠️ 它是 Plan 05B 之前那个 `LaneDivider.vue` 的**同一个组件换了皮**（props 形状
 * 逐字保留：`index` / `label` / `tone` / `level`），不是新组件 + 逐处替换 ——
 * 故 23 个调用点一个都没改语义，只改了 import 的名字与文件名。
 * 换皮的内容（计划 §2 第 1 条）：
 *   旧：`01 ▬▬▬▬▬▬▬▬▬`（粗线 3px 墨 + 偏移 6px 的 1px 砖红细线）= 分道线母题
 *   新：`[01] ALERTS ───────────`（**20×20 圆角小方块、主蓝底、白字、居中序号**，
 *       放在标题左侧，右边一条 1px 的浅灰规则线把行补满）= 北欧公共标识的做法
 * ⚠️ 「区块序号」这个**功能**保留（它有助于大屏扫读），只是形状换了。
 *
 * ⚠️ 动效：旧版有「线从左划出」的 staggered reveal（`--lane-index` 驱动 delay）。
 *    计划 §3 逐字删掉它，故本组件**不含任何动画**，也不再往 CSS 传 `--lane-index`。
 *
 * 用法：
 *   <SectionHead :index="2" label="分层分布" />
 *   <SectionHead :index="1" tone="board" level="red" />   ← 教师大屏（字号抬到 18px 下限）
 */
import { computed } from 'vue'

interface Props {
  /** 区块序号（1 起），渲染成两位补零的 `01` `02` …（标识系统的编号牌）。 */
  index?: number
  /** 小标题（可选）。⚠️ 它是**装饰性**的重复，故 `aria-hidden`：
   *  调用方应当已经有一个真的 `<h2>`。 */
  label?: string
  /** 排版档。`board` = 教师大屏那一档（方块 28px、字号抬到 18px 的下限）。
   *  ⚠️ 它**不再**管底色：大屏在 Plan 05B 翻成了浅底，全站只有一套颜色。 */
  tone?: 'paper' | 'board'
  /** 语义变体：只染**序号方块**的底色（红/黄/绿），规则线永远是中性灰 ——
   *  把线也染了的话「这是一条分隔线」与「这是一条红色预警」会混成一件事。 */
  level?: 'default' | 'red' | 'amber' | 'moss'
}

const props = withDefaults(defineProps<Props>(), {
  index: 1,
  label: '',
  tone: 'paper',
  level: 'default',
})

/** 补零到两位：`01` `02` …（编号牌的排法，与旧版逐字相同）。 */
const displayNumber = computed(() => String(Math.max(0, props.index)).padStart(2, '0'))

const classes = computed(() => [
  'section',
  props.tone === 'board' ? 'section--board' : '',
  props.level === 'default' ? '' : `section--${props.level}`,
])
</script>

<template>
  <div :class="classes">
    <span class="section__chip num" aria-hidden="true">{{ displayNumber }}</span>
    <span v-if="label" class="section__label" aria-hidden="true">{{ label }}</span>
    <span class="section__rule" aria-hidden="true"></span>
  </div>
</template>

<style scoped>
/* ⚠️ 这里出现的**颜色一律取自 tokens.css**（唯一住址，`npm run check:tokens` 看着）。
   尺寸也尽量走令牌（`--chip-size` / `--chip-font` / `--bar-hair`），
   于是「序号方块多大」这件事仍然只有一个所有者。 */
.section {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

/* 20×20 的圆角小方块：主蓝底、白字、序号居中（计划 §2 第 1 条逐字） */
.section__chip {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  inline-size: var(--chip-size);
  block-size: var(--chip-size);
  border-radius: var(--chip-radius);
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--chip-font);
  line-height: 1;
  font-variant-numeric: tabular-nums lining-nums;
  user-select: none;
}

/* 语义档：只换方块底色。⚠️ 三个色值对 `--on-primary`（白字）都过 AA：
   红 5.44 / 琥珀 5.57 / 绿 5.62（实算表见 Plan 05B 报告 §6）。 */
.section--red .section__chip {
  background: var(--red);
}
.section--amber .section__chip {
  background: var(--amber);
}
.section--moss .section__chip {
  background: var(--green);
}

.section__label {
  flex: 0 0 auto;
  min-width: 0;
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-soft);
  white-space: nowrap;
}

/* 把这一行补满的那条 1px 规则线（北欧标识里的「粗标题 + 细规则线」） */
.section__rule {
  flex: 1 1 auto;
  min-width: 0;
  block-size: var(--bar-hair);
  background: var(--border);
}

/* ------------------------------------------------- 大屏那一档（投影：18px 下限）
   ⚠️ 方块要跟着字号长：18px 的序号塞进 20px 的方块里会顶到边。 */
.section--board .section__chip {
  inline-size: var(--chip-size-board);
  block-size: var(--chip-size-board);
  border-radius: var(--radius);
  font-size: var(--fs-bs-small);
}

.section--board .section__label {
  font-size: var(--fs-bs-small);
}
</style>
