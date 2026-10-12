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
      /** 道次编号 01–06：与 `SectionHead` 同一套母题。 */
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
/* ⚠️ Plan 05B：这一格从「跑道导航」换成了北欧标识的**编号牌**：
   ① **不再出血**（旧版 `margin-inline: var(--bleed)` + 自己补 `padding-inline`；
      计划 §2 第 5 条要求学生端统一 16px 边距、不出血 —— 那 16px 由 `App.vue`
      的 `.body` 一处给，本组件不再写第二份）；
   ② 左端那条「竖过来的分道线」（`::before` 的 3px 竖条）删掉，
      换成 `.snav__lane` 自己长成那个 20×20 的主蓝序号方块（与 `SectionHead`
      同一个视觉元素，尺寸同读 `--chip-size`）。 */
.snav {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.snav__cell {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 56px;
  padding: var(--space-2);
  background: var(--surface-raise);
  border: var(--border-hairline);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--ink-soft);
  overflow: hidden;
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.snav__cell:hover {
  border-color: var(--primary);
  background: var(--primary-faint);
  color: var(--primary-press);
}

/* 当前页：一整块主蓝 + 白字（斯德哥尔摩地铁的站名牌就是这一手）。
   ⚠️ 白字对主蓝 5.73:1，过 AA；右上角那个极小缩写用 `--on-primary-dim`（4.55:1）。 */
.snav__cell--on {
  color: var(--on-primary);
  background: var(--primary);
  border-color: var(--primary);
}

.snav__cell--on:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  color: var(--on-primary);
}

/* 序号方块：20×20、圆角、主蓝底、白字、居中（计划 §2 第 1 条）。
   选中态**反白**（白底蓝字），于是「哪一格是当前页」在两处各说了一次。 */
.snav__lane {
  display: grid;
  place-items: center;
  inline-size: var(--chip-size);
  block-size: var(--chip-size);
  border-radius: var(--chip-radius);
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-ui);
  font-size: var(--chip-font);
  font-weight: var(--fw-700);
  line-height: 1;
  font-variant-numeric: tabular-nums lining-nums;
}

.snav__cell--on .snav__lane {
  background: var(--on-primary);
  color: var(--primary);
}

.snav__title {
  font-size: var(--fs-small);
  font-weight: var(--fw-700);
  line-height: 1.2;
  white-space: nowrap;
}

/* ⚠️ 字号从写死的 9px 抬到 `--fs-micro`（12px）：9px 的拉丁缩写在
   北欧标识那一族里根本不存在（公共标识的字号下限比这高得多），
   而 `--ink-faint` 在 12px 上是 5.23:1 ✓。
   ⚠️ 它仍是 absolute 定位在右上角，与左上角的方块、底部的中文标题
      三者的矩形两两不相交（§4.1 的重叠守卫会实测这件事）。 */
.snav__caps {
  position: absolute;
  inset-block-start: var(--space-2);
  inset-inline-end: var(--space-2);
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  color: var(--ink-faint);
}

.snav__cell--on .snav__caps {
  color: var(--on-primary-dim);
}
</style>
