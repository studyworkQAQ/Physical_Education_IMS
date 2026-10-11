<script setup lang="ts">
/**
 * `StudentNav.vue` —— 学生端 6 个页面的**跑道导航**（3 × 2 的一排起跑位）。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个组件（Task 2 加的，计划的 File Structure 里没有它）
 * ---------------------------------------------------------------------------
 * `App.vue` 的报头只有三棵树的入口（学生端 / 教师端 / 管理台），而 Task 1 的
 * `router/index.ts` 已经把 6 条 `/s/*` 路由建好了。没有这一格，那 6 条路由
 * **只能靠手敲 URL 到达** —— 一个「能点着走完一条业务链」的原型（计划第 0 节的判据）
 * 就不能从首页走到打卡页。
 *
 * ⚠️ **375px 下不用横向滚动的 tab bar**：6 个 tab × 每个 44px 的最小触控宽度
 * = 264px 看似放得下，但加上中文标签就得 6 × 76px = 456px → 必然要滚，
 * 而「要滚才看得见的导航」在演示时等于「看不见的导航」。故这里用 3 × 2 的网格，
 * 6 个入口一屏全在（每格约 110 × 52px，两个方向都过了 44px 的触控下限）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 两个所有者，各自只管一件事
 * ---------------------------------------------------------------------------
 *  - **标题**读 `router` 的 `meta.title`（那是它的唯一住址，Task 1 立的规矩）；
 *  - **顺序**由下面那个 `ORDER` 数组定（`router.getRoutes()` 的返回序是匹配器的
 *    打分序，不是声明序 —— 靠它就等于把导航的顺序交给路由表的内部实现）。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/** 6 条 `/s/*` 路由的 `name`，**顺序就是显示的顺序**（与计划 Task 2 那张表逐行同序）。 */
const ORDER = [
  'student-home',
  'student-weekly-sheet',
  'student-check-in',
  'student-rpe',
  'student-mini-test',
  'student-notifications',
] as const

/** 每一格右上角那个极小的拉丁缩写：计时牌上的「项目代码」。 */
const CAPS: Record<string, string> = {
  'student-home': 'HOME',
  'student-weekly-sheet': 'SHEET',
  'student-check-in': 'LOG',
  'student-rpe': 'RPE',
  'student-mini-test': 'TEST',
  'student-notifications': 'INBOX',
}

const router = useRouter()
const route = useRoute()

const items = computed(() => {
  const all = router.getRoutes()
  return ORDER.map((name, i) => {
    const record = all.find((r) => r.name === name)
    return {
      name,
      to: record?.path ?? '/s/home',
      title: record?.meta.title ?? name,
      caps: CAPS[name] ?? '',
      /** 道次编号 01–06：与 `LaneDivider` 同一套母题。 */
      lane: String(i + 1).padStart(2, '0'),
      on: route.name === name,
    }
  })
})
</script>

<template>
  <nav class="snav" aria-label="学生端的六个页面">
    <RouterLink
      v-for="item in items"
      :key="item.name"
      class="snav__cell"
      :class="{ 'snav__cell--on': item.on }"
      :to="item.to"
      :aria-current="item.on ? 'page' : undefined"
    >
      <span class="snav__lane num" aria-hidden="true">{{ item.lane }}</span>
      <span class="snav__title zh-title">{{ item.title }}</span>
      <span class="snav__caps caps" aria-hidden="true">{{ item.caps }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.snav {
  /* ⚠️ 出血到屏幕边缘（计划第 2 节的布局语言）：`.bleed` 是 base.css 的类，
     但导航还要在出血之后自己把内边距补回来，故这里直接写两个令牌。 */
  margin-inline: var(--bleed);
  padding-inline: var(--gutter);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}

.snav__cell {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-1);
  min-height: 52px;
  padding: var(--space-2) var(--space-2) var(--space-2) var(--space-3);
  background: var(--paper-raised);
  border: 1px solid var(--rule-hairline);
  border-radius: var(--radius-sharp);
  text-decoration: none;
  color: var(--ink-soft);
  overflow: hidden;
}

/* 左端那条竖线 = 分道线母题竖过来（粗线 3px 墨 + 偏移 6px 的 1px 砖红） */
.snav__cell::before {
  content: '';
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  width: var(--lane-thick);
  background: var(--rule-hairline);
}

.snav__cell--on {
  color: var(--paper);
  background: var(--ink);
  border-color: var(--ink);
}

.snav__cell--on::before {
  background: var(--track);
}

.snav__lane {
  font-size: var(--lane-num-size);
  font-weight: var(--lane-num-weight);
  letter-spacing: var(--lane-num-tracking);
  line-height: 1;
  color: var(--track);
}

.snav__cell--on .snav__lane {
  color: var(--track-on-ink);
}

.snav__title {
  font-size: var(--fs-small);
  font-weight: var(--fw-zh-title-700);
  line-height: 1.2;
  white-space: nowrap;
}

.snav__caps {
  position: absolute;
  inset-block-start: var(--space-2);
  inset-inline-end: var(--space-2);
  font-size: 9px;
  color: var(--ink-faint);
}

.snav__cell--on .snav__caps {
  color: var(--paper-faint);
}
</style>
