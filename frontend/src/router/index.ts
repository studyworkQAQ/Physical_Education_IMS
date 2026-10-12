/**
 * `router/index.ts` —— **三条路由树 + 两页鉴权**（Plan 04 Task 1 建的树，
 * Plan 05A Task 3 加的守卫）。
 *
 *     /login    登录（Plan 05A Task 3）                          → `views/auth/Login.vue`
 *     /bind     首次绑定口令（Plan 05A Task 3）                  → `views/auth/Bind.vue`
 *     /s/*      学生端 H5（375px，浅底 `--paper`）               → Plan 04 Task 2 的 6 个页面
 *     /t/*      教师端 + 大屏（1440px，深底 `--ink`）            → Plan 04 Task 3 的 4 个页面
 *     /admin/*  管理台（一个通用组件 + 一份 23 行资源目录）      → Plan 04 Task 4 的 3 个页面
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 全局前置守卫（Plan 05A Task 3；**Plan 04 那一版本文件逐字写着「不做路由守卫跳转」**）
 * ---------------------------------------------------------------------------
 * Plan 04 的非目标第 1 条是「不做真实登录/鉴权」，故那时「要学生身份」那一档
 * 只**提示**、不拦截（挡事故、不挡攻击）。Plan 05A 做了真实鉴权，
 * 于是三档要求变成了可执行的：
 *
 * | 前缀 | `meta.requires` | 判据（`stores/session.ts` 的 `satisfies`） |
 * |---|---|---|
 * | `/s/*` | `student` | `kind === 'student'` |
 * | `/t/*` | `staff` | `kind === 'teacher'`（`role` 是 `teacher` **或** `admin`） |
 * | `/admin/*` | `admin` | `kind === 'teacher' && role === 'admin'` |
 * | `/login`、`/bind` | `none` + `public` | 谁都能看 |
 *
 * 三种落空各有一个**明确的去处**（计划 §4.2 逐字要求「不要只显示空白」）：
 *  1. **没登录** → `/login?next=<原路径>`（登录成功后回到那里）；
 *  2. **角色不符** → 跳**自己的**首页，并把一句说明写进 `session.notice`
 *     （`IdentitySwitcher` 的会话条会显示它）。⚠️ 例：一个学生点了报头上的
 *     「管理台」，他会落到 `/s/home` + 一句「管理台要 role='admin'」，
 *     而不是一片空白或一个 403 横幅；
 *  3. **后端不可达**（`ensureRestored()` 抛的不是 401）→ **放行**，让页面自己的
 *     错误横幅说真因。⚠️ 这一档是刻意的：把「后端没起」翻译成「请先登录」
 *     是一句假话，而用户会照它去做（反复登录、反复失败），离真因越来越远。
 *
 * ⚠️ **`admin` 访问 `/t/*` 是允许的**（计划 §3.6 第 2 条 + §4.2）：管理员越过
 * 任教范围闸门，故大屏/周报对他是有意义的。反过来（教师访问 `/admin/*`）不行。
 *
 * ⚠️ **守卫在每一次导航上都会调 `session.ensureRestored()`**，而那个 action
 * 内部 memo 了「已经问过一次」（`stores/session.ts` 的模块级 `asked`），
 * 故一次页面刷新只发**一次** `GET /api/auth/me`，不是 13 次。
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import Bind from '../views/auth/Bind.vue'
import Login from '../views/auth/Login.vue'
import { useSessionStore } from '../stores/session'
import type { RouteRequirement } from '../stores/session'

/* ------------------------------------------------------------------ 学生端
   ⚠️ Plan 04 Task 2 已交付：6 个页面一律**静态 import**（不做 `() => import(…)` 的懒加载）。
   理由：学生端 6 个页面共享同一批组件（`StudentNav` / `LaneDivider` / `StatBlock`）
   与同一份 `present.ts`，懒加载切出来的 chunk 里几乎全是重复的那一层；
   而 H5 的第一屏是「点开链接就要能打卡」，多一次往返比多几十 KB 更贵。
   Plan 04 Task 3 的大屏与 Task 4 的管理台**该**懒加载（它们与学生端没有共享面）。 */
import CheckIn from '../views/student/CheckIn.vue'
import Home from '../views/student/Home.vue'
import MiniTest from '../views/student/MiniTest.vue'
import Notifications from '../views/student/Notifications.vue'
import RpeEntry from '../views/student/RpeEntry.vue'
import WeeklySheet from '../views/student/WeeklySheet.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（壳的 `<h1>` 与 `document.title` 都用它）。 */
    title: string
    /** 这一页由哪个 Task 落地。⚠️ 它今天纯粹是**文档**：路由各自属于哪个计划/Task，
     *  在路由树这一个住址里就能读到（读它的那个占位页早已删掉）。 */
    task: string
    /** 底色那一档。缺省 `base`。
     *  ⚠️ **两个字面值今天都是浅底**（Plan 05B 把大屏翻浅了，终审 M3 补的一格）：
     *  `base` → `.surface-base`（`--bg`，白）、`board` → `.surface-board`（`--surface`，
     *  一档极浅冷灰）。⚠️ 它选的是**「大屏那一档排版」**，不是「深底」。
     *  ⚠️⚠️ **字面值与 CSS 类名今天同词**（待清扫波改的）：此前它们是 `paper` / `ink`
     *  —— `ink`（墨）是《田径场年鉴》留下的名字，大屏翻浅底之后它会**撒谎**，
     *  05B 把这一格登记成命名债、fix 波靠「改注释 + 两层守卫」管住它。本波把名字本身
     *  改对了，于是「类名与字面值不同词」那件需要 25 行注释去解释、且解释本身构成
     *  一个误改陷阱的事**一起消失了**。
     *  ⚠️ 「字面值 → CSS 类名」的映射仍然只有一个住址：`App.vue` 的 `surface` computed。
     *  ⚠️ 守卫有两条（都在 `scripts/smoke.mjs`）：第 14 步逐条路由用 CDP 取外壳 `.app`
     *  的 class（**渲染真值**，15 条全断），第 17 步 ③ 剥注释后断言字面值
     *  ⊆ `{base, board}` 且 `paper` / `ink` 不回流（**源码面**）。 */
    surface?: 'base' | 'board'
    /** 宽壳（1440px）。⚠️ 与 `surface` **是两件事**（Plan 04 Task 3 把它们拆开）：
     *  `surface` 管底色（只有大屏是 `board`），`wide` 管壳宽（4 条 `/t/*` 全带）。 */
    wide?: boolean
    /**
     * 这一页要哪种身份。缺省 `none`。
     *
     * ⚠️ **Plan 05A Task 3 把取值域从 `'student' | 'teacher' | 'none'` 改成
     * `'student' | 'staff' | 'admin' | 'none'`**（类型是 `stores/session.ts` 的
     * {@link RouteRequirement}，两处逐字同源）。改的两格：
     *  * `teacher` → `staff`：管理员**也是**一行 `teacher`，而计划 §4.2 逐字裁定
     *    「`admin` 访问 `/t/*` 是允许的」，旧名字会把管理员排除在外；
     *  * 3 条 `/admin/*` 从**缺省 `none`** 改成字面的 `admin`：Plan 04 那时
     *    「管理台的读全部匿名、只有写要教师头」，故壳上不挂常驻提示；
     *    Plan 05A Task 2 之后 26 个写入操作**仅管理员**，而 Task 5 又把
     *    `GET /api/students` 与 `GET /api/teachers` 改成了要教职身份，
     *    于是「管理台整棵树要 admin」成了事实。
     *
     * ⚠️ 它同时是**守卫的判据**与**壳上提示的判据**（`App.vue`），
     * 故「这一页要谁」只有一个住址。
     */
    requires?: RouteRequirement
    /** 不要会话也能看（`/login`、`/bind`）。⚠️ 与 `requires: 'none'` 是两件事：
     *  `public` 的路由在**已登录**时会被守卫弹回自己的首页（否则登录页会在
     *  一个已登录用户的浏览器里变成一个可以反复登录的怪地方）。 */
    public?: boolean
    /** 是不是根路径 `/`。守卫据此把用户送到**他自己那个角色**的首页
     *  （学生 `/s/home`、教师 `/t/dashboard`、管理员 `/admin`），
     *  而不是写死一个 —— Plan 04 那一版写死了 `/s/home`。 */
    root?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  /* ------------------------------------------------------------------ 鉴权
     ⚠️ **静态 import**（不懒加载）：`/login` 是未登录用户看到的**第一屏**，
     为它多一次往返等于把「打开就要能登录」这一格让掉。两页加起来只有几 KB。 */
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { title: '登录', task: 'Plan 05A Task 3', requires: 'none', public: true },
  },
  {
    path: '/bind',
    name: 'bind',
    component: Bind,
    meta: { title: '首次绑定口令', task: 'Plan 05A Task 3', requires: 'none', public: true },
  },

  /* ------------------------------------------------------------------ 根
     ⚠️ **不再是 `redirect: '/s/home'`**（Plan 04 那一版是）：三种角色各有各的首页，
     而 `redirect` 的函数形式在**守卫之前**求值 —— 那一刻会话还没恢复
     （恢复要一次 `GET /api/auth/me`，是异步的），故它只能给出一个错的答案。
     于是根路径改成一条真的路由（`meta.root`），由守卫在恢复会话之后再决定去哪。
     ⚠️ `component` 永远不会渲染（守卫对 `root` 一律返回一个重定向），
     故它是一个返回 `null` 的内联组件，不是第二个文件。 */
  {
    path: '/',
    name: 'root',
    component: { render: () => null },
    meta: { title: '正在进入', task: 'Plan 05A Task 3', requires: 'none', root: true },
  },

  /* ------------------------------------------------------------------ 学生端
     Plan 04 Task 2 的 6 个页面，顺序与那张表逐行同序。 */
  {
    path: '/s',
    redirect: '/s/home',
    meta: { title: '学生端', task: 'Plan 04 Task 2' },
  },
  {
    path: '/s/home',
    name: 'student-home',
    component: Home,
    meta: { title: '首页', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/weekly-sheet',
    name: 'student-weekly-sheet',
    component: WeeklySheet,
    meta: { title: '本周训练单', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/check-in',
    name: 'student-check-in',
    component: CheckIn,
    meta: { title: '每日打卡', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/rpe',
    name: 'student-rpe',
    component: RpeEntry,
    meta: { title: '课堂快评', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/mini-test',
    name: 'student-mini-test',
    component: MiniTest,
    meta: { title: '二次小测', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/notifications',
    name: 'student-notifications',
    component: Notifications,
    meta: { title: '消息中心', task: 'Plan 04 Task 2 · 已交付', requires: 'student' },
  },

  /* ------------------------------------------------------------------ 教师端
     Plan 04 Task 3 的 4 个页面。⚠️ 只有大屏是深底；4 条都带 `wide`。
     ⚠️ **`requires` 是 `staff` 而不是 `teacher`**：管理员也走这一档
     （计划 §3.6 第 2 条：管理员越过任教范围闸门，故大屏对他有意义）。 */
  {
    path: '/t',
    redirect: '/t/dashboard',
    meta: { title: '教师端', task: 'Plan 04 Task 3' },
  },
  {
    path: '/t/dashboard',
    name: 'teacher-dashboard',
    component: () => import('../views/teacher/Dashboard.vue'),
    meta: {
      title: '班级大屏',
      task: 'Plan 04 Task 3 · 已交付',
      surface: 'board',
      wide: true,
      requires: 'staff',
    },
  },
  {
    path: '/t/report',
    name: 'teacher-class-report',
    component: () => import('../views/teacher/ClassReport.vue'),
    meta: { title: '班级周报', task: 'Plan 04 Task 3 · 已交付', wide: true, requires: 'staff' },
  },
  {
    path: '/t/alerts',
    name: 'teacher-alert-queue',
    component: () => import('../views/teacher/AlertQueue.vue'),
    meta: { title: '预警队列', task: 'Plan 04 Task 3 · 已交付', wide: true, requires: 'staff' },
  },
  {
    path: '/t/students/:studentId',
    name: 'teacher-student-detail',
    component: () => import('../views/teacher/StudentDetail.vue'),
    meta: { title: '学生详情', task: 'Plan 04 Task 3 · 已交付', wide: true, requires: 'staff' },
  },

  /* ------------------------------------------------------------------ 管理台
     Plan 04 Task 4：**一个通用组件 + 一份 23 行的资源目录**，不是 23 套页面。
     ⚠️ **三条都带 `wide`**（最宽的一张表是体测成绩，21 列），`surface` 仍是缺省的
     `base`。⚠️ 本处此前还给那半句加了个括号「（深底只有大屏那一块 —— 投影场景才
     需要）」，而它自 Plan 05B 起**过期了**（终审 M3）：05B 把大屏翻成了浅底，
     `.surface-board` 今天给的是 `--surface`（一档极浅冷灰），`board` 那个字面值选的
     是「大屏那一档排版」而**不是**深底 —— 逐字交代住在 `base.css` 那两个类的注释
     与上面 `RouteMeta.surface` 的 docstring 里，本处不复述第二份。
     ⚠️ **三条都带 `requires: 'admin'`**（Plan 05A Task 3）：Plan 04 那时它们缺省
     `none`，理由是「23 个资源的读全部匿名」；Plan 05A Task 2 把 26 个写入操作改成
     仅管理员、Task 5 又把两个名册资源的读改成要教职身份，故整棵树要 `admin`。
     ⚠️ 于是「一个普通教师点了报头上的管理台」会被守卫弹回 `/t/dashboard` +
     一句说明，而不是进去看到一个到处是 403 的页面。 */
  {
    path: '/admin',
    name: 'admin-index',
    component: () => import('../views/admin/ResourceIndex.vue'),
    meta: { title: '资源目录', task: 'Plan 04 Task 4 · 已交付', wide: true, requires: 'admin' },
  },
  {
    path: '/admin/:resource',
    name: 'admin-list',
    component: () => import('../views/admin/ResourceList.vue'),
    meta: { title: '资源列表', task: 'Plan 04 Task 4 · 已交付', wide: true, requires: 'admin' },
  },
  {
    path: '/admin/:resource/:id',
    name: 'admin-detail',
    component: () => import('../views/admin/ResourceDetail.vue'),
    meta: { title: '资源详情', task: 'Plan 04 Task 4 · 已交付', wide: true, requires: 'admin' },
  },

  /* 打错的 URL 不该是白屏。⚠️ 不是 404 页面：本原型没有「找不到」这一档的视觉预算。
     ⚠️ 它落到 `/s/home`，故守卫会接手：未登录 → `/login?next=/s/home`，
     教师/管理员 → 弹回自己的首页 + 一句说明。 */
  { path: '/:pathMatch(.*)*', redirect: '/s/home' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/* ==========================================================================
   全局前置守卫（Plan 05A Task 3）
   ========================================================================== */

/** 三档要求各自的那一句「你为什么被弹回来了」。⚠️ 它要说清**要求什么**与
 *  **你是什么**，只说「无权限」的话用户会以为自己的登录坏了、去反复重登。 */
const MISMATCH_NOTICE: Record<Exclude<RouteRequirement, 'none'>, string> = {
  student: '这一页要**学生**会话，而你登录的是教职身份。已把你送回教职端的首页。',
  staff: '这一页要**教职**会话（教师或管理员），而你登录的是学生。已把你送回学生端首页。',
  admin:
    '管理台（23 个资源的增删改查）自 Plan 05A 起**仅 role=admin 可用**，' +
    '而你这个工号不是管理员。课堂功能（大屏 / 周报 / 预警队列）不受影响，已把你送回那里。',
}

router.beforeEach(async (to) => {
  const session = useSessionStore()

  // ⚠️ **每一次导航都问一次「后端认我是谁」**，而 `ensureRestored` 内部 memo 了它：
  //    一次刷新只有一次 `GET /api/auth/me`。这就是「刷新页面之后怎么恢复会话」的答案
  //    （cookie 是 HttpOnly 的，JS 读不到，故只能问后端；逐字理由见
  //    `stores/session.ts` 的文件头末节）。
  try {
    await session.ensureRestored()
  } catch {
    // 后端不可达（不是 401）：`status` 停在 `unknown`。**放行**，让页面自己的
    // 错误横幅说真因 —— 把「后端没起」翻译成「请先登录」是一句假话。
    return true
  }

  // ① 根路径 → 送去**他自己那个角色**的首页（未登录 → 登录页）。
  if (to.meta.root === true) {
    return session.isAuthenticated ? session.homePath : '/login'
  }

  // ② 公开页（登录 / 绑定）。⚠️ 已登录的人还去登录页 → 弹回自己的首页：
  //    否则「登录两次」会种下第二个会话行，而第一个还活着（多设备登录是合法状态，
  //    但在同一个浏览器里它只表现为「登出登不掉」的困惑）。
  if (to.meta.public === true) {
    if (session.isAuthenticated) return session.homePath
    return true
  }

  const need: RouteRequirement = to.meta.requires ?? 'none'
  if (need === 'none') return true

  // ③ 没登录 → `/login?next=<原路径>`。
  if (!session.isAuthenticated) {
    return { path: '/login', query: { next: to.fullPath } }
  }

  // ④ 角色不符 → 自己的首页 + 一句说明（计划 §4.2：不要只显示空白）。
  if (!session.satisfies(need)) {
    session.setNotice(MISMATCH_NOTICE[need])
    return session.homePath
  }

  session.clearNotice()
  return true
})

/** 换页时把标题带上：「体育闭环原型系统」是常量，页面名是变量。 */
router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${title} · 体育闭环原型系统` : '体育闭环原型系统'
})

/**
 * 三棵树的入口，给壳上的导航用。
 *
 * ⚠️ 它是**第三个**住址（路由树本身、`meta.title`、这里），故刻意做得极薄：
 * 只有三个常量，且 `to` 直接指向上面那棵树里已存在的 `name`
 * （打错一个名字 → `router.push` 在开发期就报 `No match for …`）。
 * ⚠️ `requires` 那一格是给 `App.vue` **过滤**用的（一个学生不该看到「管理台」这个
 * 入口 —— 点它只会被守卫弹回来 + 一句说明，那是「教用户点一个必然失败的按钮」）。
 * 它**不是**第二个判据：守卫读的是路由树上的 `meta.requires`，本处只在
 * `App.vue` 里被用来决定「这一个 navlink 画不画」。
 */
/** 一棵树在报头导航上的那一格。⚠️ `requires` 的类型是 {@link RouteRequirement}，
 *  与路由树的 `meta.requires` **同一个类型**（于是「导航画不画」与「守卫放不放行」
 *  不可能对同一档给出两个答案）。 */
interface TreeEntry {
  readonly name: string
  readonly label: string
  readonly to: string
  readonly caps: string
  readonly requires: RouteRequirement
}

export const TREES: readonly TreeEntry[] = [
  { name: 'student-home', label: '学生端', to: '/s/home', caps: 'STUDENT · H5', requires: 'student' },
  { name: 'teacher-dashboard', label: '教师端', to: '/t/dashboard', caps: 'TEACHER · WALL', requires: 'staff' },
  { name: 'admin-index', label: '管理台', to: '/admin', caps: 'ADMIN · CRUD', requires: 'admin' },
]
