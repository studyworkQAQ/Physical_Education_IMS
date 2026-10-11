import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// ---------------------------------------------------------------------------
// ⚠️ 后端地址只有一个住址：下面这个常量。
//
// 缺省 `http://127.0.0.1:8000` —— 计划第 1 节约束第 21 条的起服务口径。
// 用环境变量 `PE_API_TARGET` 覆盖（例如把演示后端起在 8011 时：
//   `$env:PE_API_TARGET="http://127.0.0.1:8011"; npm run dev`）。
//
// ⚠️ **走代理就不用碰 CORS**：后端 `app/main.py` 的 CORSMiddleware 是
// `allow_origins=["*"]` 且**不带** `allow_credentials`，而浏览器规范禁止
// `Access-Control-Allow-Origin: *` 与 credentials 并存 —— 一旦 `client.ts` 设了
// `credentials: 'include'`，所有跨域请求会当场失败。开发期一律由下面这段
// `server.proxy` 把 `/api` 转到同源，于是根本不存在跨域。
// ⚠️ 但 `npm run build` 出来的是静态文件、没有代理，故 `client.ts` 的 baseURL
// 从 `import.meta.env.VITE_API_BASE ?? ''` 取：开发时是空串（走代理），
// 生产时由部署方注入。
// ---------------------------------------------------------------------------
const API_TARGET = process.env.PE_API_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      // ⚠️ 管理台的表单是**契约驱动**的（`src/api/contract.ts` 读
      //    `components.schemas[*Create | *Update]` 决定画哪几格），而
      //    `/openapi.json` **不在 `/api` 前缀下** → 不加这一条，开发期它会打到
      //    vite 自己身上（回一份 index.html，于是 `JSON.parse` 当场失败）。
      //    后端地址仍然只有 `API_TARGET` 一个住址。
      '/openapi.json': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
