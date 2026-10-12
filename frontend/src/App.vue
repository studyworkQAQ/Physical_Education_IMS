<script setup lang="ts">
/**
 * `App.vue` —— **壳**。
 *
 * 四件事，不多做：
 *  1. 报头（masthead）：刊名 + 三棵树的导航（`router/index.ts` 的 `TREES`）；
 *  2. **`IdentitySwitcher` 的常驻位** —— 它在每一条路由上都在场。
 *     ⚠️ Plan 05A Task 3 之后它是「**当前身份 + 登出**」（不再是「代替登录页」的
 *     身份切换器；那一半只在 DEV 构建里存在）；
 *  3. **`ApiErrorBanner` 的常驻位** —— 渲染在报头之下、`<main>` 之上，
 *     于是错误出现/消失不会把内容顶下去又顶回来；
 *  4. `<RouterView>`。
 *
 * ⚠️ **表面由路由的 `meta.surface` 决定**，不是由组件自己决定：
 * 只有 `/t/dashboard` 是 `board`（⚠️ 待清扫波把这个字面值从《田径场年鉴》留下的
 * `ink` 改成了 `board`，与它选中的那个 CSS 类**同词**；
 * **它选的是「大屏那一档排版」而不是「深底」** —— Plan 05B 把大屏翻成了浅底）。
 * 表面一律加在**外壳**上（`.surface-board` / `.surface-base`），于是 `base.css`
 * 里那一层底色自动生效，页面自己不必写第二套。
 *
 * ⚠️⚠️ **Plan 04 那一版本文件逐字写着「不做路由守卫跳转」**（那时没有登录页，
 * 故「要学生身份」那一档只提示、不拦截）。Plan 05A Task 3 之后守卫是真的
 * （`router/index.ts` 的 `beforeEach`），于是本文件里的 `identityHint`
 * **退场了**：能被渲染出来的页面，身份一定是够的 —— 再挂一条常驻的
 * 「这一页要教师身份」会变成一句永远为假的提示。
 * 剩下的两格是：① 导航按 `session.satisfies` **过滤**（一个学生不该看到
 * 「管理台」这个入口：点它只会被守卫弹回来 + 一句说明，那是「教用户点一个
 * 必然失败的按钮」）；② 未登录时导航**整个不画**（登录页上没有可去的地方）。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import ApiErrorBanner from './components/ApiErrorBanner.vue'
import IdentitySwitcher from './components/IdentitySwitcher.vue'
import { TREES } from './router'
import { useIdentityStore } from './stores/identity'
import { useSessionStore } from './stores/session'

const route = useRoute()
const identity = useIdentityStore()
const session = useSessionStore()

const surface = computed(() => (route.meta.surface === 'board' ? 'surface-board' : 'surface-base'))

/** ⚠️ **宽壳与底色是两件事**（Plan 04 Task 3 修的一格）。
 *  Task 1 把 `.body--wide` 绑在 `meta.surface` 上，于是只有大屏是 1440px，
 *  而教师端的另外三页（周报 / 预警队列 / 学生详情）被挤进了学生端的 375px 壳里 ——
 *  一个要放 30 行预警与四档筛选的页面在 375px 下只能竖着排成一列窄条。
 *  计划非目标第 5 条逐字是「学生端按 375px 宽设计（手机）、**教师端按 1440px 宽设计**」，
 *  没有说「只有大屏那一页」。故宽壳改由 `meta.wide` 声明（4 条 `/t/*` 路由都带），
 *  底色仍然只由 `meta.surface` 声明 —— 两者**各管一件事**，不再互相搭车。
 *  ⚠️⚠️ 本处此前逐字是 `route.meta.wide === true || route.meta.surface === 'ink'`
 *  （⚠️ `'ink'` 是**当时**那个字面值的名字；待清扫波已把它改成 `'board'`，
 *  故本行是一句**历史引文**、不是现在时的断言），
 *  而**第二个从句是死支**（终审 M2）：全仓只有 `/t/dashboard` 一条设了 `surface`，
 *  而那一条**同时**带 `wide: true`。于是上面那段注释说「不再互相搭车」、代码却仍然搭着
 *  —— 注释与代码在同一屏互相打脸。删的是**代码那半**（注释才是那一格的裁定）。
 *  ⚠️ 它也不只是难看：留着它，下一个加一条 `surface: 'board'` 而**不想**要宽壳的路由的人
 *  会得到一个他从未声明过的 1440px 壳。 */
const wide = computed(() => route.meta.wide === true)

/** 当前在哪一棵树上（导航的高亮）。⚠️ 按路径前缀判，不按 `route.name`：
 *  路由的名字要逐个列进来，而前缀只有三个。 */
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

/** **我这个会话进得去的**那几棵树。⚠️ 判据是 `session.satisfies`（与路由守卫
 *  同一个函数、同一个住址），故「画出来的入口」与「点了不会被弹回来的入口」
 *  恒为同一批 —— 两处各写一份判据的话，它们会在下一次改口径时漂开。 */
const visibleTrees = computed(() => TREES.filter((tree) => session.satisfies(tree.requires)))
</script>

<template>
  <div class="app" :class="surface">
    <header class="masthead">
      <div class="masthead__inner" :class="{ 'masthead__inner--wide': wide }">
        <div class="masthead__title">
          <p class="masthead__kicker caps">PHYSICAL EDUCATION · CLOSED LOOP</p>
          <h1 class="zh-title masthead__name">体育闭环原型系统</h1>
          <p class="masthead__sub display">北欧公共标识 / NORDIC SIGNAGE</p>
        </div>

        <nav v-if="session.isAuthenticated" class="masthead__nav" aria-label="三个端">
          <RouterLink
            v-for="tree in visibleTrees"
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
      <!-- ② 会话条（当前身份 + 登出）的常驻位 -->
      <IdentitySwitcher />

      <!-- ③ 错误横幅的常驻位 -->
      <ApiErrorBanner />

      <main class="main">
        <RouterView />
      </main>

      <footer class="colophon">
        <p class="caps">COLOPHON</p>
        <p class="colophon__text">
          原型系统 · <strong>已做真实鉴权</strong>（Plan 05A）：首次绑定口令 → 登录 →
          <code class="data">HttpOnly</code> 的 <code class="data">pe_session</code>
          cookie 会话（滑动过期 2 小时）→ 登出**真的吊销**服务端那一行。
          ⚠️ 不做口令找回 / 登录失败锁定 / CSRF 双重提交令牌（逐字局限见 spec §1.2 与 §13）。
          业务日 <code class="data">{{ identity.asOf }}</code> ·
          {{ session.summary }}。
        </p>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* ⚠️ Plan 05B：报头下面那两条线（3px 墨 + 偏移 6px 的 1px 砖红 = 分道线母题
   在页面尺度上的一次复用）删掉了，换成**一条 1px 的浅灰规则线** ——
   北欧标识的分隔靠一条细线加留白，不靠双线母题。
   ⚠️ 于是 `.masthead` 上的 `position: relative` 也不再需要（没有绝对定位的伪元素了）。
   ⚠️ 而 `.surface-board .xxx` 那一组覆盖全部删掉了：大屏翻浅底之后，
      两档表面的**颜色是同一套**（差异只在 `base.css` 给的那一层极浅冷灰底），
      留着 6 条同值覆盖就是死配置。 */
.app {
  min-height: 100dvh;
}

.masthead {
  border-block-end: var(--border-hairline);
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

.masthead__name {
  font-size: var(--fs-title);
}

.masthead__sub {
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--primary);
}

.masthead__nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.navlink {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  border: var(--border-hairline);
  border-radius: var(--radius-btn);
  background: var(--surface-raise);
  text-decoration: none;
  color: var(--ink-soft);
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.navlink:hover {
  border-color: var(--primary);
  background: var(--primary-faint);
  color: var(--primary-press);
}

/* 当前那一棵树：一整块主蓝 + 白字（对主蓝 5.73:1，过 AA） */
.navlink--on {
  color: var(--on-primary);
  background: var(--primary);
  border-color: var(--primary);
}

.navlink--on:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  color: var(--on-primary);
}

.navlink__label {
  font-size: var(--fs-small);
  font-weight: var(--fw-700);
}

/* ⚠️ 学生端统一 16px 边距（`--gutter`）、**不出血**（计划 §2 第 5 条）：
   全站只有这一处给那 16px，卡片与导航都不再自己写 `margin-inline: -16px`。 */
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

/* ⚠️ Plan 04 那一版这里有一条 `.identity-hint`（「这一页要学生身份，请去切换器里选」）。
   Plan 05A Task 3 之后路由守卫会**拦住**身份不符的导航（弹回自己的首页 + 一句
   `session.notice`，那一句由 `IdentitySwitcher` 的 `.switcher__warn` 渲染），
   故「页面已经渲染出来了、而身份不够」这一档不再存在，那条规则随之删掉。 */
.main {
  min-height: 40dvh;
}

.colophon {
  margin-block-start: var(--space-6);
  padding-block-start: var(--space-3);
  border-block-start: var(--border-hairline);
  color: var(--ink-faint);
}

.colophon__text {
  font-size: var(--fs-micro);
}
</style>
