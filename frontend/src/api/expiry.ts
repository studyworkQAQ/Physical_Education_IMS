/**
 * `api/expiry.ts` —— **「会话失效了」这一个事件的发布/订阅口**（Plan 05A Task 3）。
 *
 * ---------------------------------------------------------------------------
 * 为什么需要它（一个 20 行的叶子模块，而不是一行 `router.replace`）
 * ---------------------------------------------------------------------------
 * `client.ts` 是全前端**唯一**直接调 `fetch` 的地方（单一所有者），故「任何端点回了
 * 401 `unauthenticated`」这一档也只有它能看见。而正确的反应是**两件与 HTTP 无关的事**：
 * 清掉本地会话状态（`stores/session.ts`）+ 跳 `/login?next=<原路径>`（`router`）。
 *
 * ⚠️ 直接在 `client.ts` 里 `import { router }` 会造出一个**导入环**：
 * `client` → `router` → `stores/session` → `api/auth` → `client`。
 * ESM 大多数时候能绕过去（函数体里的引用是活绑定），而它失败的方式是
 * 「某一次打包顺序变了、`router` 在 `client` 求值时还是 TDZ」——一个只在生产构建里
 * 出现、且报在离真因很远的地方的 `ReferenceError`。
 *
 * 故这里放一个**没有任何依赖的叶子**：`client.ts` 只 `fire`，`main.ts` 在装配时
 * `subscribe`。依赖方向因此是「装配点知道零件、零件不知道装配点」，与本仓
 * `ApiErrorBanner` 的模块级单例（`useApiError`）同一条口径。
 */

/** 一次会话失效的现场。`request` 是「哪一次请求撞上的」（`METHOD URL`），
 *  `path` 是**当时浏览器所在的前端路由**（登录之后要回到那里去）。 */
export interface ExpiryEvent {
  readonly request: string
  readonly code: string
}

type Handler = (event: ExpiryEvent) => void

/** ⚠️ 只留一个订阅者（`main.ts`）：两个订阅者会各跳一次 `/login`，
 *  于是 `next` 里带的是**第二次**跳转时的路径（`/login` 自己）。 */
let handler: Handler | null = null

/** 装配点（`main.ts`）注册那一个反应。 */
export function onSessionExpired(next: Handler): void {
  handler = next
}

/** `client.ts` 在识别出「会话失效」时调它。**没有订阅者就什么也不做**
 *  （单元测试与 `smoke.mjs` 那种没有装配点的场合不该炸）。 */
export function fireSessionExpired(event: ExpiryEvent): void {
  handler?.(event)
}
