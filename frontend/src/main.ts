/**
 * `main.ts` —— 装配点。
 *
 * ⚠️ 四个样式文件的 **import 顺序是承重的**：`tokens.css` 只声明自定义属性
 * （它不含任何选择器），`base.css` / `lane.css` / `student.css` 都要 `var(--…)` 它们。
 * 反过来写不会报错（自定义属性的解析发生在计算值阶段，与声明顺序无关），
 * 但**同名的覆盖**就会，故一律按「令牌 → 基础 → 母题 → 学生端布局」排。
 *
 * ⚠️ `app.config.errorHandler` 是本前端**唯一**的未捕获异常出口：它把
 * `ApiError` 送进 `ApiErrorBanner` 的常驻位（于是「某处忘了 try/catch」不会
 * 退化成一条只在 devtools 里的红字），其余异常照常 `console.error`。
 * 它**不吞**异常：仍然重新打印，故开发期的堆栈不会被藏起来。
 */
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { ApiError } from './api/client'
import { useApiError } from './components/ApiErrorBanner.vue'
import { router } from './router'
import { useIdentityStore } from './stores/identity'
import './styles/tokens.css'
import './styles/base.css'
import './styles/lane.css'
import './styles/student.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// ⚠️ 深链接身份（`?student=4&as_of=2025-10-12`）在**挂载之前**认：
//    页面组件的 `onMounted` 里就要发请求，而请求头由 `client.ts` 从本 store 读 ——
//    晚一步认，第一屏就是 401（而那一屏的横幅会把人支去查后端）。
//    ⚠️ 它不删查询串：`?date=` 一类参数还要被页面自己读（`route.query`）。
if (useIdentityStore().adoptFromUrl(window.location.search)) {
  console.info('[identity] 已从 URL 认出身份：', useIdentityStore().summary)
}

app.config.errorHandler = (err, _instance, info) => {
  // ⚠️ 只有 `ApiError` 进横幅。渲染期的一般异常（`TypeError` 之类）进横幅
  //    会把「代码有 bug」显示成「后端出错了」，那是两种完全不同的下一步。
  if (err instanceof ApiError) {
    useApiError().raise(err)
  }
  console.error('[unhandled]', info, err)
}

app.mount('#app')
