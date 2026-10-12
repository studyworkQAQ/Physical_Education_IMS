/**
 * `main.ts` —— 装配点。
 *
 * ⚠️ 六个样式文件的 **import 顺序是承重的**：`fonts.css` 只声明 `@font-face`
 * （字体面的唯一住址，交付前收尾波起**自托管**、不再从 Google Fonts 的 CDN 拉），
 * `tokens.css` 只声明自定义属性（它不含任何选择器），`base.css` / `student.css` /
 * `teacher.css` / `admin.css` 都要 `var(--…)` 它们。反过来写不会报错（自定义属性
 * 与 `@font-face` 的解析都发生在计算值/字体匹配阶段，与声明顺序无关），
 * 但**同名的覆盖**就会，故一律按
 * 「字体面 → 令牌 → 基础 → 学生端布局 → 教师端布局 → 管理台布局」排。
 * ⚠️ `fonts.css` 排在最前还有一层意思：它是**唯一**一个会在首屏触发网络请求的
 *    样式文件（4 个 woff2），而它替掉的那三条 CDN `<link>` 此前住在 `index.html`
 *    的 `<head>` 里 —— 换到这一层之后，产物里 `fonts.googleapis.com` 出现 **0** 次
 *    （守卫在 `scripts/check-dist.mjs`）。
 * ⚠️ `student.css` / `teacher.css` / `admin.css` 三者之间**没有**覆盖关系
 * （三组类名不重叠：`.s-*` / `.t-*`+`.bs-*` / `.a-*`），故它们的先后不承重；
 * 排在一起是为了「布局层在最后」。
 * ⚠️ **Plan 05B：`lane.css` 删了**（分道线母题整体退场，计划 §2 第 1 条），
 *    于是那一层从六个文件变成五个；**交付前收尾波又把 `fonts.css` 加回来**
 *    （它是字体面、不是布局层，故仍是「布局层五个」）。区块序号那一格搬进了
 *    `SectionHead.vue` 自己的 `<style scoped>`（它是那个视觉元素的唯一消费者）。
 *
 * ⚠️ `app.config.errorHandler` 是本前端**唯一**的未捕获异常出口：它把
 * `ApiError` 送进 `ApiErrorBanner` 的常驻位（于是「某处忘了 try/catch」不会
 * 退化成一条只在 devtools 里的红字），其余异常照常 `console.error`。
 * 它**不吞**异常：仍然重新打印，故开发期的堆栈不会被藏起来。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ Plan 05A Task 3 加的两件事
 * ---------------------------------------------------------------------------
 * 1. **`onSessionExpired` 的订阅**（④）：`client.ts` 是唯一直接调 `fetch` 的地方，
 *    故「任何端点回了 401 `unauthenticated`」也只有它看得见；而正确的反应
 *    （清会话 + 跳登录页）要 `router` 与 `stores/session`。让 `client.ts` 直接
 *    import 它们会造出 `client → router → session → api/auth → client` 的导入环，
 *    故那里只 `fire`、这里 `subscribe`（逐字理由见 `api/expiry.ts` 的文件头）。
 * 2. **深链接身份降级成 DEV-only**（③）：`adoptFromUrl` 搬进了 `src/dev/`，
 *    而这里那一个 `if (import.meta.env.DEV)` 是它在生产构建里**被整个摇掉**的机制。
 *    守卫是 `scripts/check-dist.mjs`（断言 `dist/` 里 `adoptFromUrl` 出现 0 次）。
 *    ⚠️⚠️ 而它**调用点的位置**在本波（终审 I5）从「挂载之前」挪到了
 *    「`session.ensureRestored()` 之后、挂载之前」——逐字理由见 ③ 那一段。
 */
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { ApiError } from './api/client'
import { onSessionExpired } from './api/expiry'
import { useApiError } from './components/ApiErrorBanner.vue'
import { adoptFromUrl } from './dev/identity-url'
import { router } from './router'
import { useIdentityStore } from './stores/identity'
import { useSessionStore } from './stores/session'
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/student.css'
import './styles/teacher.css'
import './styles/admin.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// ④ 「会话失效」的唯一反应。**装配点知道零件、零件不知道装配点。**
let redirecting = false
onSessionExpired((event) => {
  const session = useSessionStore()
  const current = router.currentRoute.value
  // ⚠️ 一个页面常常并发发好几个请求（`Dashboard.vue` 是 4 个），会话过期时它们
  //    **一起**回 401。不挡住的话会跳 4 次，而 `next` 里带的是第 4 次那一刻的路径
  //    （已经是 `/login` 了）—— 于是「登录后回到刚才那一页」这一格静默失效。
  if (redirecting || current.path === '/login' || current.path === '/bind') return
  session.forget()
  session.status = 'anon'
  // ⚠️ **不静默跳走**（派单第 4 点）：先把「为什么你被弹回来了」写进 store，
  //    登录页会把它显示在表单上方。用户填了一半的表单确实会丢 ——
  //    本原型不做草稿保存（如实记录），故这一句至少要说清「丢的是什么」。
  session.setNotice(
    `会话已失效，请重新登录（${event.request} 回了 401 ${event.code}）。` +
      `登录之后会回到 ${current.fullPath}。⚠️ 那一页上没提交的输入已经丢了。`,
  )
  redirecting = true
  void router
    .replace({ path: '/login', query: { next: current.fullPath } })
    .finally(() => {
      redirecting = false
    })
})

app.config.errorHandler = (err, _instance, info) => {
  // ⚠️ 只有 `ApiError` 进横幅。渲染期的一般异常（`TypeError` 之类）进横幅
  //    会把「代码有 bug」显示成「后端出错了」，那是两种完全不同的下一步。
  if (err instanceof ApiError) {
    useApiError().raise(err)
  }
  console.error('[unhandled]', info, err)
}

/** 挂载。**`app.mount('#app')` 的唯一住址**：下面两支都只调它。 */
function mount(): void {
  app.mount('#app')
}

// ③ ⚠️ 深链接身份（`?student=4&as_of=2025-10-12`）：DEV-only，且**排在
//    `session.ensureRestored()` 之后、挂载之前**（终审 I5 改的一格）。
//
//    ⚠️⚠️ 本处此前是「**挂载之前**、会话还没问过」就认，理由是「页面组件的
//    `onMounted` 里就要发请求，晚一步认第一屏就是 401」。那个理由对**页面组件**成立，
//    而对**第一个请求**恰好是反的：第一个请求就是 `ensureRestored()` 自己发的
//    `GET /api/auth/me`，而它由 `router.beforeEach` 在 `app.use(router)` 那一刻就
//    触发了 —— 于是 URL 上那个**未经验证**的身份会先被写进 `stores/identity`，
//    再被 `client.ts` 读出来贴到 `/api/auth/me` 上。终审用 CDP 实测到的形状是：
//      +406ms  GET /api/auth/me                        身份头 X-Student-Id: 4  ← URL 认出来的假身份
//      +435ms  GET /api/students/5/home                身份头 X-Student-Id: 5  ← session.adopt() 已跑
//    （登录成 #5、URL 上写 `?student=4`。）今天它无害只是**巧合**：`/api/auth/me`
//    依赖 `current_session`、刻意不回落请求头（`deps.py`），而演示/生产后端整个忽略
//    那两个头。没有任何断言钉住它，故本波同时补了守卫（`smoke.mjs` 第 14 步末）。
//
//    ⚠️ **挪到 `ensureRestored()` 之后不花任何额外时间**：`router.beforeEach` 本来就
//    `await` 了同一个（memo 过的）Promise，任何页面组件都在它之后才可能挂载，
//    故首屏本来就在这一次请求之后 —— 这里只是把「认 URL 身份」排进同一条队。
//
//    ⚠️ **后端不可达时不认**：那一支 `status` 停在 `'unknown'`、守卫放行、
//    `session.adopt()` 不跑，于是一个未经验证的 id 会被写进**持久化**的
//    `stores/identity`（`localStorage`），留给下一次刷新。故只在真的问过后端之后才认。
//
//    ⚠️ 它不删查询串：`?as_of=` 一类参数还要被页面自己读（`route.query`）。
//    ⚠️ **一处如实记录的行为变化（硬规矩 #39）**：改动前 `session.adopt()` 的
//    「session → identity」兼容桥总在 `adoptFromUrl` **之后**跑，故一个与会话不符的
//    `?student=` 会被静默冲掉（URL 那一格事实上是死的）。挪了顺序之后 URL 那一格
//    **赢了**，于是 `?student=1`（而会话是 #4）会真的去打 `/api/students/1/home`
//    → 后端 `require_scope` 按**会话**判、回 **403**（横幅会说清「不是你的数据」）。
//    这是有意的：那一格本来就是 DEV 工具（`src/dev/identity-url.ts` 的三条纪律之一
//    就是「只在参数存在时才动状态」），而**响亮地 403 比静默地忽略 URL 好** ——
//    本波修的正是「账面说的与代码做的相反」这一族。⚠️ 而拆掉那座兼容桥本身
//    **不是本波的活**（05B 待清扫第 14 条），故这里一行都没动它。
//    ⚠️⚠️ **整个分支只在 DEV 构建里存在**：`import.meta.env.DEV` 是编译期常量，
//    生产构建里 Vite 把它替换成 `false`，Rollup 于是删掉这个 `if` 块、
//    连带把 `src/dev/identity-url.ts` 整个摇掉（它没有别的消费者、也没有副作用）。
//    故生产那一支**同步**挂载，与改动前逐字同形。
if (import.meta.env.DEV) {
  void (async (): Promise<void> => {
    let restored = false
    try {
      await useSessionStore().ensureRestored()
      restored = true
    } catch {
      // 后端不可达（不是 401）：`status` 停在 `unknown`，守卫会放行。见上面那一格。
    }
    if (restored) {
      const identity = useIdentityStore()
      if (adoptFromUrl(identity, window.location.search)) {
        console.info('[identity] 已从 URL 认出开发期身份：', identity.summary)
      }
    }
    mount()
  })()
} else {
  mount()
}
