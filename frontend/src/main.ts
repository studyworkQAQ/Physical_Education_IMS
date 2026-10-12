/**
 * `main.ts` —— 装配点。
 *
 * ⚠️ 五个样式文件的 **import 顺序是承重的**：`tokens.css` 只声明自定义属性
 * （它不含任何选择器），`base.css` / `lane.css` / `student.css` / `teacher.css` /
 * `admin.css` 都要 `var(--…)` 它们。反过来写不会报错（自定义属性的解析发生在
 * 计算值阶段，与声明顺序无关），但**同名的覆盖**就会，故一律按
 * 「令牌 → 基础 → 母题 → 学生端布局 → 教师端布局 → 管理台布局」排。
 * ⚠️ `student.css` / `teacher.css` / `admin.css` 三者之间**没有**覆盖关系
 * （三组类名不重叠：`.s-*` / `.t-*`+`.bs-*` / `.a-*`），故它们的先后不承重；
 * 排在一起是为了「布局层在最后」。
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
import './styles/tokens.css'
import './styles/base.css'
import './styles/lane.css'
import './styles/student.css'
import './styles/teacher.css'
import './styles/admin.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// ③ ⚠️ 深链接身份（`?student=4&as_of=2025-10-12`）在**挂载之前**认：
//    页面组件的 `onMounted` 里就要发请求，而 DEV 的身份头由 `client.ts` 从
//    `stores/identity` 读 —— 晚一步认，第一屏就是 401（而那一屏的横幅会把人支去查后端）。
//    ⚠️ 它不删查询串：`?as_of=` 一类参数还要被页面自己读（`route.query`）。
//    ⚠️⚠️ **整个分支只在 DEV 构建里存在**：`import.meta.env.DEV` 是编译期常量，
//    生产构建里 Vite 把它替换成 `false`，Rollup 于是删掉这个 `if` 块、
//    连带把 `src/dev/identity-url.ts` 整个摇掉（它没有别的消费者、也没有副作用）。
if (import.meta.env.DEV) {
  const identity = useIdentityStore()
  if (adoptFromUrl(identity, window.location.search)) {
    console.info('[identity] 已从 URL 认出开发期身份：', identity.summary)
  }
}

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

app.mount('#app')
