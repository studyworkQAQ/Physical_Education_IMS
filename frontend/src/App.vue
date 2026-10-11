<script setup lang="ts">
/**
 * `App.vue` —— **壳**。
 *
 * 四件事，不多做：
 *  1. 报头（masthead）：刊名 + 三棵树的导航（`router/index.ts` 的 `TREES`）；
 *  2. **`IdentitySwitcher` 的常驻位** —— 它在每一条路由上都在场，因为「我是谁」
 *     与「我在哪一页」是两件独立的事（口径：读侧大部分匿名、写请求一律要头，
 *     另有几个按人收窄的窄读端点也要头；⚠️ **具体多少个刻意不写在这里**，
 *     机器口径见 `api/client.ts` 的 `identityHeaders` 注释）；
 *  3. **`ApiErrorBanner` 的常驻位** —— 渲染在报头之下、`<main>` 之上，
 *     于是错误出现/消失不会把内容顶下去又顶回来；
 *  4. `<RouterView>`。
 *
 * ⚠️ **底色由路由的 `meta.surface` 决定**，不是由组件自己决定：
 * 只有 `/t/dashboard` 是 `ink`（大屏是投影场景，计划 Task 3 逐字「1440px、深底」）。
 * 深底一律加在**外壳**上（`.surface-ink`），于是 `base.css` 里那一批
 * `.surface-ink .xxx` 的规则（卡片 / 按钮 / pill / `.unknown`）全部自动生效，
 * 页面自己不必写第二套。
 *
 * ⚠️ **不做路由守卫跳转**：本原型没有登录页（非目标第 1 条），故「要学生身份」
 * 那一档只**提示**，不拦截。挡事故、不挡攻击。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import ApiErrorBanner from './components/ApiErrorBanner.vue'
import IdentitySwitcher from './components/IdentitySwitcher.vue'
import { TREES } from './router'
import { useIdentityStore } from './stores/identity'

const route = useRoute()
const identity = useIdentityStore()

const surface = computed(() => (route.meta.surface === 'ink' ? 'surface-ink' : 'surface-paper'))

/** ⚠️ **宽壳与深底是两件事**（Plan 04 Task 3 修的一格）。
 *  Task 1 把 `.body--wide` 绑在 `meta.surface === 'ink'` 上，于是只有大屏是 1440px，
 *  而教师端的另外三页（周报 / 预警队列 / 学生详情）被挤进了学生端的 375px 壳里 ——
 *  一个要放 30 行预警与四档筛选的页面在 375px 下只能竖着排成一列窄条。
 *  计划非目标第 5 条逐字是「学生端按 375px 宽设计（手机）、**教师端按 1440px 宽设计**」，
 *  没有说「只有大屏那一页」。故宽壳改由 `meta.wide` 声明（4 条 `/t/*` 路由都带），
 *  深底仍然只由 `meta.surface` 声明 —— 两者**各管一件事**，不再互相搭车。 */
const wide = computed(() => route.meta.wide === true || route.meta.surface === 'ink')

/** 当前在哪一棵树上（导航的高亮）。⚠️ 按路径前缀判，不按 `route.name`：
 *  13 条路由的名字要逐个列进来，而前缀只有三个。 */
const activeTree = computed(() => {
  const path = route.path
  if (path.startsWith('/t')) return '/t'
  if (path.startsWith('/admin')) return '/admin'
  return '/s'
})

/** 一棵树的入口 URL → 它的前缀（`/s/home` → `/s`，`/admin` → `/admin`）。 */
function treePrefix(to: string): string {
  const parts = to.split('/')
  return parts.length > 2 ? `/${parts[1]}` : to
}

/** 这一页要身份、而当前没有对的那一个 → 提示一句。 */
const identityHint = computed(() => {
  const needs = route.meta.requires ?? 'none'
  if (needs === 'none') return ''
  if (needs === 'student' && identity.canWriteAsStudent) return ''
  if (needs === 'teacher' && identity.canWriteAsTeacher) return ''
  return needs === 'student'
    ? '这一页要**学生**身份：请在下面的身份切换器里选一个学生（否则会 401 unauthenticated，或读到别人的数据时 403 forbidden）。'
    : '这一页要**教师**身份：请在下面的身份切换器里选一个教师（后端 45 个挂 security 的操作里，写入侧一律要 X-Teacher-Staff-No）。'
})
</script>

<template>
  <div class="app" :class="surface">
    <header class="masthead">
      <div class="masthead__inner" :class="{ 'masthead__inner--wide': wide }">
        <div class="masthead__title">
          <p class="masthead__kicker caps">PHYSICAL EDUCATION · CLOSED LOOP</p>
          <h1 class="zh-title masthead__name">体育闭环原型系统</h1>
          <p class="masthead__sub display">田径场年鉴 / ATHLETICS ALMANAC</p>
        </div>

        <nav class="masthead__nav" aria-label="三个端">
          <RouterLink
            v-for="tree in TREES"
            :key="tree.name"
            class="navlink"
            :class="{ 'navlink--on': activeTree === treePrefix(tree.to) }"
            :to="tree.to"
          >
            <span class="navlink__caps caps">{{ tree.caps }}</span>
            <span class="navlink__label zh-title">{{ tree.label }}</span>
          </RouterLink>
        </nav>
      </div>
    </header>

    <div class="body" :class="{ 'body--wide': wide }">
      <!-- ② 身份切换器的常驻位 -->
      <IdentitySwitcher />

      <!-- ③ 错误横幅的常驻位 -->
      <ApiErrorBanner />

      <p v-if="identityHint" class="identity-hint" role="status">{{ identityHint }}</p>

      <main class="main">
        <RouterView />
      </main>

      <footer class="colophon">
        <p class="caps">COLOPHON</p>
        <p class="colophon__text">
          原型系统 · 不做真实登录/推送/第三方对接。身份走两个请求头
          （<code class="data">X-Student-Id</code> / <code class="data">X-Teacher-Staff-No</code>）。
          业务日 <code class="data">{{ identity.asOf }}</code> ·
          {{ identity.summary }}。
        </p>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.app {
  min-height: 100dvh;
}

.masthead {
  border-block-end: var(--lane-thick) solid currentColor;
  position: relative;
}

/* 报头下面那条偏移的细线 = 分道线母题在页面尺度上的一次复用 */
.masthead::after {
  content: '';
  position: absolute;
  inset-inline: 0;
  top: calc(100% + var(--lane-offset));
  height: var(--lane-thin);
  background: var(--track);
}

.masthead__inner {
  max-width: var(--w-student);
  margin-inline: auto;
  padding: var(--space-4) var(--gutter) var(--space-3);
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
}

.masthead__inner--wide {
  max-width: var(--w-teacher);
  padding-inline: var(--space-5);
}

.masthead__kicker {
  color: var(--ink-faint);
}

.surface-ink .masthead__kicker {
  color: var(--paper-faint);
}

.masthead__name {
  font-size: var(--fs-title);
  letter-spacing: 0.02em;
}

.masthead__sub {
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--track);
}

.surface-ink .masthead__sub {
  color: var(--track-on-ink);
}

.masthead__nav {
  display: flex;
  gap: var(--space-2);
}

.navlink {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--rule-hairline);
  border-radius: var(--radius-sharp);
  text-decoration: none;
  color: var(--ink-soft);
}

.navlink:hover {
  border-color: currentColor;
}

.navlink--on {
  color: var(--paper);
  background: var(--ink);
  border-color: var(--ink);
}

.surface-ink .navlink {
  border-color: var(--rule-hairline-on-ink);
  color: var(--paper-soft);
}

.surface-ink .navlink--on {
  color: var(--ink);
  background: var(--track-on-ink);
  border-color: var(--track-on-ink);
}

.navlink__label {
  font-size: var(--fs-small);
  font-weight: var(--fw-zh-title-700);
}

.body {
  max-width: var(--w-student);
  margin-inline: auto;
  padding: var(--space-4) var(--gutter) var(--space-7);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.body--wide {
  max-width: var(--w-teacher);
  padding-inline: var(--space-5);
}

.identity-hint {
  padding: var(--space-2) var(--space-3);
  border-inline-start: var(--lane-thick) solid var(--amber-on-paper);
  background: var(--amber-wash);
  color: var(--amber-on-paper);
  font-size: var(--fs-small);
}

.surface-ink .identity-hint {
  border-inline-start-color: var(--amber-on-ink);
  background: var(--amber-wash-on-ink);
  color: var(--amber-on-ink);
}

.main {
  min-height: 40dvh;
}

.colophon {
  margin-block-start: var(--space-6);
  padding-block-start: var(--space-3);
  border-block-start: var(--border-hairline);
  color: var(--ink-faint);
}

.surface-ink .colophon {
  border-block-start-color: var(--rule-hairline-on-ink);
  color: var(--paper-faint);
}

.colophon__text {
  font-size: var(--fs-micro);
}
</style>
