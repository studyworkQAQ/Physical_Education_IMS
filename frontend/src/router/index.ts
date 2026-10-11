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
 * 13 条路由里，**6 条 `/s/*` 已由 Task 2 换成真页面**；`/t/*` 的 4 条与
 * `/admin/*` 的 3 条仍指向两个占位页（`views/teacher|admin/*Placeholder.vue`），
 * `meta.title` 与 `meta.task` 写明了每一条由谁替换、渲染什么。
 * Task 3–4 的活是**逐条把 `component:` 换掉**，而不是重写这棵树 ——
 * 于是「教师端读学生详情走哪条 URL」这件事只有一个住址，
 * 改路由不用同时改三个 Task 的文档。
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

import AdminPlaceholder from '../views/admin/AdminPlaceholder.vue'
import TeacherPlaceholder from '../views/teacher/TeacherPlaceholder.vue'

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
    /** 这一页由哪个 Task 落地。⚠️ 占位页把它显示出来，于是「这是占位」不会被误读成 bug。 */
    task: string
    /** 底色。缺省 `paper`。 */
    surface?: 'paper' | 'ink'
    /** 这一页要哪种身份。缺省 `none`（47 个 GET 全部匿名，故「没身份」不是错误）。 */
    requires?: 'student' | 'teacher' | 'none'
    /** 一句话说明这一页要渲染什么。Task 2–4 替换 `component:` 时可以把它删掉。 */
    intent?: string
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
     计划 Task 3 的 4 个页面。⚠️ 只有大屏是深底。                              */
  {
    path: '/t',
    redirect: '/t/dashboard',
    meta: { title: '教师端', task: 'Task 3' },
  },
  {
    path: '/t/dashboard',
    name: 'teacher-dashboard',
    component: TeacherPlaceholder,
    meta: {
      title: '班级大屏',
      task: 'Task 3',
      surface: 'ink',
      requires: 'teacher',
      intent:
        'GET /api/dashboard/class/{course_section_id} —— 1440px 深底、5 秒轮播教学班、不对称网格（预警 5 / 分层 4 / 概览 3）、发起课堂快评并投屏口令',
    },
  },
  {
    path: '/t/report',
    name: 'teacher-class-report',
    component: TeacherPlaceholder,
    meta: {
      title: '班级周报',
      task: 'Task 3',
      requires: 'teacher',
      intent:
        'GET /api/dashboard/weekly-class-report/{course_section_id} —— 5 个聚合列各一块；404 no_weekly_report → 「本周周报将在周日生成」',
    },
  },
  {
    path: '/t/alerts',
    name: 'teacher-alert-queue',
    component: TeacherPlaceholder,
    meta: {
      title: '预警队列',
      task: 'Task 3',
      requires: 'teacher',
      intent:
        'GET /api/alerts?limit=200（客户端过滤 level/status/course_section_id）+ POST /api/alerts/{id}/handle',
    },
  },
  {
    path: '/t/students/:studentId',
    name: 'teacher-student-detail',
    component: TeacherPlaceholder,
    meta: {
      title: '学生详情',
      task: 'Task 3',
      requires: 'teacher',
      intent:
        '⚠️ GET /api/teacher/students/{id}/weekly-sheet（不是学生侧那条，走错会 401）+ /home + /api/mini-tests/normalized',
    },
  },

  /* ------------------------------------------------------------------ 管理台
     计划 Task 4：**一个通用组件 + 一份 23 行的资源目录**，不是 23 套页面。
     故只有三条路由，`resource` 与 `id` 都是路径参数，
     由 `catalog/resources.ts` 那一行决定渲染什么。                            */
  {
    path: '/admin',
    name: 'admin-index',
    component: AdminPlaceholder,
    meta: {
      title: '资源目录',
      task: 'Task 4',
      intent: '23 个资源的目录；⚠️ 只读的 14 个要标出来并说明理由（spec §4.4）',
    },
  },
  {
    path: '/admin/:resource',
    name: 'admin-list',
    component: AdminPlaceholder,
    meta: {
      title: '资源列表',
      task: 'Task 4',
      intent:
        '分页（limit/offset）+ 新建 + 行内删除；⚠️ 只读资源的写按钮**不出现**（不是禁用）；restrict 删除失败 → 409 要说清「还被谁引用」',
    },
  },
  {
    path: '/admin/:resource/:id',
    name: 'admin-detail',
    component: AdminPlaceholder,
    meta: {
      title: '资源详情',
      task: 'Task 4',
      intent:
        '读单条（含被 list 排掉的那些 JsonText 列）+ 编辑；⚠️ forbid 的 10 个资源没有 DELETE 端点（405）',
    },
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
