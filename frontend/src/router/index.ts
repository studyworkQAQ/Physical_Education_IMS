/**
 * `router/index.ts` —— **三条路由树**（计划 Task 1 第 10 步）。
 *
 *     /s/*      学生端 H5（375px，浅底 `--paper`）        → Task 2 的 6 个页面
 *     /t/*      教师端 + 大屏（1440px，深底 `--ink`）      → Task 3 的 4 个页面
 *     /admin/*  管理台（一个通用组件 + 一份 23 行资源目录） → Task 4 的 3 个页面
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 本文件是 Task 2–4 的**约束**，不是它们的草稿
 * ---------------------------------------------------------------------------
 * 13 条路由，**6 条 `/s/*` 由 Task 2 交付、4 条 `/t/*` 由 Task 3 交付、
 * 3 条 `/admin/*` 由 Task 4 交付** —— 占位页（`views/admin/AdminPlaceholder.vue`）
 * 已随 Task 4 一并删掉，`meta.intent` 那一格也随之退场（它当初的用途逐字是
 * 「一句话说明这一页要渲染什么，替换 `component:` 时可以把它删掉」）。
 * 于是本文件今天只有**一棵真的路由树**，不再兼作三个 Task 的待办清单。
 *
 * ⚠️ **`meta.surface` 决定底色**（`App.vue` 读它给外壳加 `.surface-ink`）：
 * 只有 `/t/dashboard` 是深底。理由：大屏是投影场景（计划 Task 3 逐字
 * 「1440px、深底、字号下限 18px」），而教师端的另外三个页面（周报 / 预警队列 /
 * 学生详情）是**在办公室的显示器上点着用的**，深底会让它们的表格与表单
 * 全部要写第二套对比度。故深底只给大屏那一块。
 *
 * ⚠️ **`meta.requires` 声明这一页要哪种身份**，`App.vue` 据此在壳上提示
 * 「请先在身份切换器里选一个学生」。**不做路由守卫跳转**（非目标第 1 条：
 * 不做真实登录，故没有「登录页」可跳）—— 挡事故、不挡攻击。
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/* ------------------------------------------------------------------ 学生端
   ⚠️ Task 2 已交付：6 个页面一律**静态 import**（不做 `() => import(…)` 的懒加载）。
   理由：学生端 6 个页面共享同一批组件（`StudentNav` / `LaneDivider` / `StatBlock`）
   与同一份 `present.ts`，懒加载切出来的 chunk 里几乎全是重复的那一层；
   而 H5 的第一屏是「点开链接就要能打卡」，多一次往返比多几十 KB 更贵。
   Task 3 的大屏与 Task 4 的管理台**该**懒加载（它们与学生端没有共享面）。 */
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
    /** 这一页由哪个 Task 落地。⚠️ Task 4 之后**没有任何组件读它**（读它的那个
     *  占位页已删）—— 它今天纯粹是**文档**：13 条路由各自属于哪个 Task，
     *  在路由树这一个住址里就能读到。 */
    task: string
    /** 底色。缺省 `paper`。 */
    surface?: 'paper' | 'ink'
    /** 宽壳（1440px）。⚠️ 与 `surface` **是两件事**（Plan 04 Task 3 把它们拆开）：
     *  `surface` 管底色（只有大屏是 `ink`），`wide` 管壳宽（4 条 `/t/*` 全带）。
     *  Task 1 曾把宽壳绑在 `surface === 'ink'` 上，于是教师端另外三页被挤进
     *  学生端的 375px 壳里 —— 计划非目标第 5 条逐字是「教师端按 1440px 宽设计」，
     *  没有说「只有大屏那一页」。 */
    wide?: boolean
    /** 这一页要哪种身份。缺省 `none`（48 个 GET 匿名，故「没身份」不是错误）。
     *  ⚠️ 3 条 `/admin/*` **刻意不带**它：管理台的读全部匿名，只有写要教师头，
     *  而写按钮的可见性由页面自己判并就地说明（壳上一条常驻的「这一页要教师身份」
     *  会把「我只是来看看列表」也说成一件缺东西的事）。 */
    requires?: 'student' | 'teacher' | 'none'
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/s/home' },

  /* ------------------------------------------------------------------ 学生端
     计划 Task 2 的 6 个页面，顺序与那张表逐行同序。
     ⚠️ **Task 2 已交付**：`component:` 已从占位页换成真页面，`meta.intent` 一并删掉
        （Task 1 的注释逐字写了「替换 `component:` 时可以把它删掉」—— 端点与口径
        现在写在每个页面自己的文件头注释里，那里才是它的住址；留在 `meta` 上
        就是第二个所有者，而它会先漂）。                                      */
  {
    path: '/s',
    redirect: '/s/home',
    meta: { title: '学生端', task: 'Task 2' },
  },
  {
    path: '/s/home',
    name: 'student-home',
    component: Home,
    meta: { title: '首页', task: 'Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/weekly-sheet',
    name: 'student-weekly-sheet',
    component: WeeklySheet,
    meta: { title: '本周训练单', task: 'Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/check-in',
    name: 'student-check-in',
    component: CheckIn,
    meta: { title: '每日打卡', task: 'Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/rpe',
    name: 'student-rpe',
    component: RpeEntry,
    meta: { title: '课堂快评', task: 'Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/mini-test',
    name: 'student-mini-test',
    component: MiniTest,
    meta: { title: '二次小测', task: 'Task 2 · 已交付', requires: 'student' },
  },
  {
    path: '/s/notifications',
    name: 'student-notifications',
    component: Notifications,
    meta: { title: '消息中心', task: 'Task 2 · 已交付', requires: 'student' },
  },

  /* ------------------------------------------------------------------ 教师端
     计划 Task 3 的 4 个页面。⚠️ 只有大屏是深底。
     ⚠️ **Task 3 已交付**：`component:` 已从占位页换成真页面，`meta.intent` 一并删掉
        （Task 1 的注释逐字写了「替换 `component:` 时可以把它删掉」—— 端点与口径
        现在写在每个页面自己的文件头注释里，那里才是它的住址）。
     ⚠️ **懒加载**（`() => import(…)`）：Task 1 的注释逐字要求了它
        （「Task 3 的大屏与 Task 4 的管理台**该**懒加载」）。⚠️ 而它当时给的理由
        「它们与学生端没有共享面」在 Task 3 之后**已经不完全成立**（教师端与学生端
        现在共用 `present.ts` / `LaneDivider` / `StatBlock`），故这里如实改写理由：
        大屏那一块拖着 3 个图表组件与一整套 `--fs-bs-*` 的排版，而**学生端 H5 的
        第一屏是「点开链接就要能打卡」**（Task 1 逐字），不该为一个教师才看的页面
        多下载几十 KB。共享的那一层仍然在主 chunk 里，故不会重复下载。           */
  {
    path: '/t',
    redirect: '/t/dashboard',
    meta: { title: '教师端', task: 'Task 3' },
  },
  {
    path: '/t/dashboard',
    name: 'teacher-dashboard',
    component: () => import('../views/teacher/Dashboard.vue'),
    meta: {
      title: '班级大屏',
      task: 'Task 3 · 已交付',
      surface: 'ink',
      wide: true,
      requires: 'teacher',
    },
  },
  {
    path: '/t/report',
    name: 'teacher-class-report',
    component: () => import('../views/teacher/ClassReport.vue'),
    meta: { title: '班级周报', task: 'Task 3 · 已交付', wide: true, requires: 'teacher' },
  },
  {
    path: '/t/alerts',
    name: 'teacher-alert-queue',
    component: () => import('../views/teacher/AlertQueue.vue'),
    meta: { title: '预警队列', task: 'Task 3 · 已交付', wide: true, requires: 'teacher' },
  },
  {
    path: '/t/students/:studentId',
    name: 'teacher-student-detail',
    component: () => import('../views/teacher/StudentDetail.vue'),
    meta: { title: '学生详情', task: 'Task 3 · 已交付', wide: true, requires: 'teacher' },
  },

  /* ------------------------------------------------------------------ 管理台
     计划 Task 4：**一个通用组件 + 一份 23 行的资源目录**，不是 23 套页面。
     故只有三条路由，`resource` 与 `id` 都是路径参数，
     由 `catalog/resources.ts` 那一行决定渲染什么。
     ⚠️ **Task 4 已交付**：三条的 `component:` 已从占位页换成真页面
        （`AdminPlaceholder.vue` 随之删掉），`meta.intent` 一并删掉
        （口径现在写在每个页面自己的文件头注释里，那里才是它的住址）。
     ⚠️ **三条都带 `wide`**：管理台是桌面上点着用的运维工具，最宽的一张表是
        体测成绩（21 列），塞进学生端的 375px 壳里只能横向滚三屏。
        而 `surface` 仍是缺省的 `paper`（深底只有大屏那一块 —— 投影场景才需要）。
     ⚠️ **`requires` 一律缺省 `none`**：23 个资源的读全部匿名，故「没选身份」
        不是错误。写按钮的可见性由页面自己判（`identity.canWriteAsTeacher`），
        并在非教师身份时**就地说明**为什么要选一个教师 —— 比在壳上挂一条
        常驻的「这一页要教师身份」更准（读根本不要）。                      */
  {
    path: '/admin',
    name: 'admin-index',
    component: () => import('../views/admin/ResourceIndex.vue'),
    meta: { title: '资源目录', task: 'Task 4 · 已交付', wide: true },
  },
  {
    path: '/admin/:resource',
    name: 'admin-list',
    component: () => import('../views/admin/ResourceList.vue'),
    meta: { title: '资源列表', task: 'Task 4 · 已交付', wide: true },
  },
  {
    path: '/admin/:resource/:id',
    name: 'admin-detail',
    component: () => import('../views/admin/ResourceDetail.vue'),
    meta: { title: '资源详情', task: 'Task 4 · 已交付', wide: true },
  },

  /* 打错的 URL 不该是白屏。⚠️ 不是 404 页面：本原型没有「找不到」这一档的视觉预算。 */
  { path: '/:pathMatch(.*)*', redirect: '/s/home' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
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
 */
export const TREES = [
  { name: 'student-home', label: '学生端', to: '/s/home', caps: 'STUDENT · H5' },
  { name: 'teacher-dashboard', label: '教师端', to: '/t/dashboard', caps: 'TEACHER · WALL' },
  { name: 'admin-index', label: '管理台', to: '/admin', caps: 'ADMIN · CRUD' },
] as const
