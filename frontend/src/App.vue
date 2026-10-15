<script setup lang="ts">
/**
 * `App.vue` —— **壳**。
 *
 * 五件事，不多做：
 *  0. **试用告示的常驻位**（Plan 07 Task 1）：⚠️ 只在**试用档**出现，
 *     而「这是哪一档」**只有后端知道**（逐字理由见下面那一节）；
 *  1. 报头（masthead）：**厦门大学品牌锁排**（`BrandLockup variant="masthead"`：
 *     校徽 + 拉丁校名 + 系统名「厦大体育数智系统」，⚠️ 系统名那一格是全站唯一的
 *     `<h1>`，它住在 `BrandLockup` 里）+ 三棵树的导航（`router/index.ts` 的 `TREES`）；
 *  2. **`IdentitySwitcher` 的常驻位** —— 它在每一条路由上都在场。
 *     ⚠️ Plan 05A Task 3 之后它是「**当前身份 + 登出**」（不再是「代替登录页」的
 *     身份切换器；那一半只在 DEV 构建里存在）；
 *  3. **`ApiErrorBanner` 的常驻位** —— 渲染在报头之下、`<main>` 之上，
 *     于是错误出现/消失不会把内容顶下去又顶回来；
 *  4. `<RouterView>`。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 试用告示：档位**不能写死在前端**（Plan 07 Task 1 的设计核心）
 * ---------------------------------------------------------------------------
 * `frontend/dist` 是**同一份**构建产物：开发档（vite）、产品档（`scripts/serve.ps1`
 * 的 uvicorn 同源）、试用档（`scripts/trial.ps1`：产品档 + `PE_TRIAL=1` + 一个专用库）
 * 跑的是逐字节相同的那些 js/css。于是「我是不是试用档」只有两条路可走，
 * 而两条都错：
 *
 *  * **构建期注入**（`import.meta.env.VITE_TRIAL`）⇒ 一份 `dist` 只能服务一档，
 *    而产品档也会挂着「请勿录入真实学生信息」；
 *  * **前端读自己的 URL**（`hostname` 长得像 `192.168.*` 就算试用）⇒ 一句会随
 *    甲方网络拓扑变假的判据，而它失效的样子是「静默不挂告示」。
 *
 * 故**由后端回答**：`app/deploy.py` 的 `is_trial()`（读 `PE_TRIAL`，认不出的值
 * **raise**，于是失效方向是「服务起不来」）→ `GET /api/health` 的 `trial` 一格
 * → 本文件在**挂载时打一次**。⚠️ 那个端点是**匿名**的，故未登录也读得到
 * （`/login` 与 `/bind` 两条路由也要看得见告示 —— 那正是试用者最先落地的两页）。
 * ⚠️ 而它是「24 个未定型响应」之一，故加那一格**不改 `/openapi.json` 的响应 schema
 * 一个字节**（后端 `app/main.py` 里 `health` 的 docstring 逐字记了这一格与它的取证）。
 *
 * ⚠️ **本仓此前没有任何一处读 `/api/health`**（`api/endpoints.ts` 的 `getHealth()`
 * 有定义、0 个调用点，实测过），故本文件那一次调用是**新增的一次**、不是复用。
 * 一次挂载只打一次；它不随路由变化重打（档位是**进程事实**，不是页面事实）。
 * ⚠️ 而它**排在那一次「问后端我是谁」之后**（`await session.ensureRestored()`，
 * 零额外请求：那一个 Promise 是 memo 过的），逐字理由见下面 `onMounted` 里的注释
 * ——一句话版：`smoke.mjs` 第 14 步 §I5 钉着「第一个后端请求必须是 `/api/auth/me`
 * 且不带身份头」，那是终审 I5 的落点，⚠️ 不许为了让本文件通过而放宽它。
 *
 * ⚠️⚠️ **读不到就不挂**（控制者裁定，实现者复核后同意，逐字理由）：
 * `/api/health` 打不通 = 后端没起来 = 这个页面**本来就是坏的**（每一个业务端点
 * 都会失败、`ApiErrorBanner` 会挂出真因），此时再挂一条「试用环境」是**噪声**，
 * 而且它会与「后端不可达」那一档的真因抢注意力。⚠️ 反过来那一档（「不确定就告示」）
 * 的代价是：开发档与产品档在后端没起时也挂一条试用告示 —— 那是一条**假话**
 * （那两个档的库里可以是真数据），而本仓的纪律是「宁可少说一句，不说一句假的」。
 * ⚠️ 于是 `catch` 那一支**刻意静默**：它不 `raise` 进 `ApiErrorBanner`
 * （一条红色的「后端出错了」会把「后端没起来」这件事说两遍）。
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
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getHealth } from './api/endpoints'
import ApiErrorBanner from './components/ApiErrorBanner.vue'
import BrandLockup from './components/BrandLockup.vue'
import IdentitySwitcher from './components/IdentitySwitcher.vue'
import { TREES } from './router'
import { useIdentityStore } from './stores/identity'
import { useSessionStore } from './stores/session'

const route = useRoute()
const identity = useIdentityStore()
const session = useSessionStore()

/** 是不是试用档（`GET /api/health` 的 `trial` 一格）。⚠️ 缺省 `false` = **不挂告示**，
 *  即「读不到就不挂」那一档与「后端说不是」那一档在渲染面上同形（理由见文件头）。 */
const trial = ref(false)

/** 告示里那个「N 名学生均为虚构」的 N。⚠️ 取自 `/api/health` 的 `students` 一格
 *  （一次真查询的结果），**不写死 60**：`scripts/trial.ps1 -Students` 可以改它，
 *  而写死就是那个数的第二个所有者（改一处漏一处，漏的那一处印在页面上）。
 *  ⚠️ 缺省 0 而**不是** `null`：`v-if="trial"` 成立就意味着那次 `/api/health`
 *  成功了，于是本格一定是后端给的那个数 —— 留一个 `null` 分支等于留一条恒用不到的
 *  死支（硬规矩 #50：一个恒用不到的分支与一个真的分支在颜色上无法区分）。 */
const trialStudents = ref(0)

onMounted(async () => {
  /* ⚠️⚠️ **先 `await session.ensureRestored()`，再问 `/api/health`** —— 这一行是承重的，
     删掉它 `smoke.mjs` 第 14 步的 §I5 那两拍会当场红（本波在产品档上实测到过）：
     §I5 断言「**第一个**后端请求就是 `GET /api/auth/me`（会话恢复那一次），且它
     **不带任何身份头**」，来历是终审 I5 —— 改前 `main.ts` 在会话还没问过之前就认了
     URL 上那个**未经验证**的身份，于是第一个请求带着一个伪造得出来的 `X-Student-Id`。
     ⚠️ 而**产品档**的 `main.ts` 是**同步** `mount()`（只有 DEV 那一支先 `await`），
     故本组件的 `onMounted` 会抢在路由守卫之前跑 —— 一个直接发出去的 `getHealth()`
     就成了第一个请求。⚠️ 它今天**无害**（`/api/health` 是匿名的、一个身份都不看，
     而生产构建里 `identityHeaders()` 恒回空对象），但「无害」是巧合不是契约：
     那条守卫钉的正是「**任何**请求都不得先于会话恢复」，而放松它等于把 I5 那一格
     重新打开一条缝（硬规矩 #92：不许为了让新代码通过而放宽既有判据）。
     ⚠️ **成本是零**：`ensureRestored()` 缓存 in-flight 的 Promise（`stores/session.ts`
     文件头逐字写着「只发一次」，路由守卫每次导航都调它），故本行**不多打一次**
     `/api/auth/me`，只是排在它后面。
     ⚠️ 代价如实记（硬规矩 #39）：告示因此**晚一帧**出现（会话恢复回来之后），
     而 `/api/auth/me` 有上限（`RESTORE_TIMEOUT_MS`）⇒ 最坏情况下告示晚那么久；
     超时或失败都落到下面那个 `catch`，即「读不到就不挂」。 */
  try {
    await session.ensureRestored()
  } catch {
    // 会话恢复失败/超时：不拦着下面那一次（它自己也有 catch）。
  }
  try {
    const health = await getHealth()
    trial.value = health.trial === true
    trialStudents.value = health.students
  } catch {
    // ⚠️ **刻意静默**：不挂告示、也不把这一条送进 `ApiErrorBanner`
    //    （逐字裁定与理由见文件头「读不到就不挂」那一节）。
    trial.value = false
  }
})

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
        <BrandLockup variant="masthead" />

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
      <!-- ⓪ 试用告示的常驻位（Plan 07 Task 1）。⚠️ **普通流里的一格**，不是 fixed/sticky：
           一条固定横幅最容易犯的就是遮住内容或与报头重叠，而 smoke 第 14 步对 16 条路由
           逐条量「文本内容重叠 / 横向溢出 / 整页滚动条」（判据一字不许放宽）。
           ⚠️ 文案写在**一行**上：Vue 模板的空白压缩会把跨行的文本折成一个空格，
           于是「（60」与「名学生…」分成两行写的话会渲染成「（60 名学生…」。 -->
      <p v-if="trial" class="trial-note" role="status">
        <strong>试用环境</strong> · 数据为<strong>高保真仿真</strong>（{{ trialStudents }} 名学生均为虚构） · <strong>请勿录入真实学生信息</strong>
      </p>

      <!-- ② 会话条（当前身份 + 登出）的常驻位 -->
      <IdentitySwitcher />

      <!-- ③ 错误横幅的常驻位 -->
      <ApiErrorBanner />

      <main class="main">
        <RouterView />
      </main>

      <footer class="colophon">
        <BrandLockup variant="colophon" />
        <p class="colophon__text">
          <strong>已做真实鉴权</strong>（Plan 05A）：首次绑定口令 → 登录 →
          <code class="data">HttpOnly</code> 的 <code class="data">pe_session</code>
          cookie 会话（滑动过期 2 小时）→ 登出<strong>真的吊销</strong>服务端那一行。
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

/* ⚠️ 试用告示（Plan 07 Task 1）。**零个新色值**：五个声明逐字取自既有 token，
   与 `IdentitySwitcher.vue` 的 `.switcher__warn` 同一组（那一格是**scoped** 的、
   跨组件用不到；`teacher.css` 的 `.t-block__note` 与 `student.css` 的 `.s-block__note`
   是全局的、但**带端前缀** —— 把 `.t-` 挂到学生端那 6 条路由上是第二个所有者，
   故本处自己写一条，而色值一律 `var(--…)`。`npm run check:tokens` 的 offender 仍是 0）。 */
.trial-note {
  padding: var(--space-2) var(--space-3);
  background: var(--amber-faint);
  color: var(--amber);
  border-radius: var(--radius);
  font-size: var(--fs-small);
}

.masthead {
  border-block-end: var(--border-hairline);
}

.masthead__inner {
  max-width: var(--w-student);
  margin-inline: auto;
  padding: var(--space-3) var(--gutter);
  display: flex;
  flex-wrap: wrap;
  /* ⚠️ 改前是 `flex-end`：那时报头左侧是**三行文字**（kicker + h1 + sub），
     底对齐才让右侧那一排导航格与刊名坐在同一条基线上。品牌与密度波之后左侧是
     「校徽 + 两行文字」的一个**块**（`BrandLockup variant="masthead"`），
     块与块之间该用的是垂直居中。 */
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.masthead__inner--wide {
  max-width: var(--w-teacher);
  padding-inline: var(--space-5);
}

/* ⚠️ 品牌与密度波删掉了四条死配置：`.masthead__title` / `.masthead__kicker` /
   `.masthead__name` / `.masthead__sub`。报头左侧那一整块的住址搬进了
   `components/BrandLockup.vue`（品牌锁排的唯一住址），留在这里就是第二个所有者。 */

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

/* 当前那一棵树：一整块主蓝（厦大蓝）+ 白字（对主蓝 13.06:1，过 AA） */
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
  /* ⚠️ 品牌与密度波：页脚现在是「品牌块（嘉庚体校名 + 校训 + 版本行）+ 一段
     说明文字」两格，故它自己变成一个纵向 flex —— 品牌块的住址在
     `BrandLockup variant="colophon"`，本处只管两格之间的那一道间距。 */
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.colophon__text {
  font-size: var(--fs-micro);
}
</style>
