import { readFileSync } from 'node:fs'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// ---------------------------------------------------------------------------
// ⚠️ **版本号的唯一住址是 `package.json` 的 `version`**（品牌与密度波）。
//    页脚那一行「版本」由 `src/brand.ts` 的 `VERSION` 读它，而 `brand.ts` 那一侧
//    只有一句 `declare const __PE_VERSION__: string` —— 编译期由下面这个 `define`
//    替换掉。⚠️ 刻意**不**在 `src/` 里 `import … from '../package.json'`：
//    那会把整份 package.json（含 `//` 那一段几百字、写给开发者的 smoke 警告）
//    打进**客户端产物**，而它不该发到浏览器上。
// ⚠️ 读文件用 `node:fs` 而不是 JSON import：`tsconfig.node.json` 是
//    `nodenext` + `verbatimModuleSyntax`，JSON 模块要额外写 import attributes，
//    而这里只需要一个字符串。
// ---------------------------------------------------------------------------
const PKG_VERSION = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
).version as string

// ---------------------------------------------------------------------------
// ⚠️ 后端地址只有一个住址：下面这个常量。
//
// 缺省 `http://127.0.0.1:8000` —— 计划第 1 节约束第 21 条的起服务口径。
// 用环境变量 `PE_API_TARGET` 覆盖（例如把演示后端起在 8011 时：
//   `$env:PE_API_TARGET="http://127.0.0.1:8011"; npm run dev`）。
//
// ⚠️ **走代理就不用碰 CORS**：**开发档**（`PE_ENV` 未设或 `=dev`，也就是本代理
//    唯一会碰到的那一档）后端 `app/main.py` 的 CORSMiddleware 是
//    `allow_origins=["*"]` 且**不带** `allow_credentials`，而浏览器规范禁止
//    `Access-Control-Allow-Origin: *` 与 credentials 并存 —— 一旦 `client.ts` 设了
//    `credentials: 'include'`，所有跨域请求会当场失败。开发期一律由下面这段
//    `server.proxy` 把 `/api` 转到同源，于是根本不存在跨域。
//    ⚠️ Plan 06 Task 4 起后端**生产档**改成读 `PE_CORS_ORIGINS`（缺省空 = 一个
//    `CORSMiddleware` 都不挂 = 拒绝跨域），白名单非空时带 `allow_credentials=True`；
//    那一档下前端要么同源、要么按 `client.ts` 顶部那五件事一起改。
//    ⚠️ 而 `prod` 下后端装配完还有一道**启动自检**：CORS 被挂成 `*`、或 cookie 的
//    `Secure` 没开 → `raise`，服务起不来。逐字见 spec §13.8。
// ⚠️ 但 `npm run build` 出来的是静态文件、没有代理，故 `client.ts` 的 baseURL
//    从 `import.meta.env.VITE_API_BASE ?? ''` 取：开发时是空串（走代理），
//    生产时由部署方注入。
// ---------------------------------------------------------------------------
const API_TARGET = process.env.PE_API_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  define: {
    __PE_VERSION__: JSON.stringify(PKG_VERSION),
  },
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
