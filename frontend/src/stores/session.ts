/**
 * `stores/session.ts` —— **服务端 cookie 会话在前端的镜像**（Plan 05A Task 3）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 为什么它与既有的 `stores/identity.ts` **分开**（派单要求说明理由）
 * ---------------------------------------------------------------------------
 * 两个 store 装的是**两件不同的事**，而把它们合成一个会让三件事同时变坏：
 *
 * 1. **权威性不同**。会话的**唯一真相**是后端 `user_session` 那张表 +
 *    那个 `HttpOnly` 的 `pe_session` cookie（JS 读不到它）。故本 store 里的东西
 *    是一份**缓存**，它的刷新方式是「问一次 `GET /api/auth/me`」，
 *    而不是「读一次 `localStorage`」。
 *    而 `identity.ts` 里的 `asOf`（业务日）是**纯本地偏好**：它没有服务端对应物，
 *    刷新之后必须从 `localStorage` 读回来，否则演示会退回「今天」而查不到任何数据。
 *    ⚠️ 把一份「缓存」与一份「偏好」塞进同一个持久化快照，失效形态是
 *    「换了一个人登录、而 `asOf` 被冲掉」或者反过来「登出了、而身份还在」。
 * 2. **生命周期不同**。会话在 401 / 登出 / 吊销时**必须**清空；
 *    `asOf` 在这三种情况下都**不该**动（`identity.ts` 的 `clearIdentity()` 逐字
 *    写了「不清 `asOf`」，因为业务日是演示口径的一部分、与「我是谁」无关）。
 * 3. **`role` 是三值、不是两值**。`identity.ts` 的 `IdentityRole` 是
 *    `'student' | 'teacher'`（它服务的是那两个请求头，而请求头里没有 role 这一格）；
 *    会话的 `role` 是 `'student' | 'teacher' | 'admin'`，而**路由守卫的三档**
 *    （`/s/*`、`/t/*`、`/admin/*`）全依赖它。把 `admin` 加进 `IdentityRole`
 *    会让 `client.ts` 的 `identityHeaders()` 多出一个它无法表达的状态
 *    （没有「管理员请求头」这种东西）。
 *
 * ⚠️ 于是分工是：**本 store = 「后端认我是谁」**，`identity.ts` = **「我在看哪一天」
 * + 一个 DEV-only 的请求头身份工具**（Plan 05A 之后请求头那条通道只在
 * `PE_ALLOW_HEADER_IDENTITY=1` 时存在，故它降级成了开发工具）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 「刷新页面之后怎么恢复会话」（派单点名要说清的一格）
 * ---------------------------------------------------------------------------
 * cookie 是 `HttpOnly` 的（后端 `app/auth/sessions.py` 的 `cookie_kwargs`：
 * `httponly=True`），故 **JS 读不到它** —— `document.cookie` 里没有 `pe_session`，
 * 「靠读 cookie 判断我登录了没」这条路**结构上不存在**。
 * 也不把它抄进 `localStorage`：那会造出第二个真相（浏览器里的 cookie 还在、
 * 而 `localStorage` 被清了，或反过来），而两者不一致时的表现是「页面认为登录了、
 * 每一个请求都 401」。
 *
 * 故恢复会话只有**一条**路：**应用启动/首次导航时打一次 `GET /api/auth/me`**。
 *  * 200 → 那六格就是「我是谁」，`status = 'authed'`；
 *  * 401 → `status = 'anon'`，路由守卫把用户送去 `/login?next=<原路径>`。
 *
 * ⚠️ 那一次请求由 {@link useSessionStore.ensureRestored} 发起，且**只发一次**
 * （它缓存 in-flight 的 Promise）：路由守卫在每一次导航上都会调它，
 * 而不 memo 的话「一次刷新」会变成「13 条路由各问一次 me」。
 * ⚠️ 而 `status` 的**初值是 `'unknown'` 而不是 `'anon'`**：那两档在守卫里必须分开，
 * 否则守卫会在 `me` 回来之前就把一个已登录的用户弹去 `/login`（闪一下再跳回来）。
 */
import { defineStore } from 'pinia'

import {
  type AuthKind,
  type SessionIdentity,
  type SessionRole,
  fetchMe,
  login as loginRequest,
  logout as logoutRequest,
} from '../api/auth'
import { useIdentityStore } from './identity'

/** 一条路由**要求**哪种身份。⚠️ 与 `router/index.ts` 的 `meta.requires` 逐字同源
 *  （那个 `declare module` 里的联合类型就是这四个值）。
 *
 *  * `none`   —— 不要身份（`/login`、`/bind`）；
 *  * `student`—— 要学生会话（6 条 `/s/*`）；
 *  * `staff`  —— 要**教职**会话，`role ∈ {teacher, admin}`（4 条 `/t/*`）；
 *  * `admin`  —— 要 `role == 'admin'`（3 条 `/admin/*`）。
 *
 *  ⚠️ `staff` 而不是 `teacher`：管理员**也是**一行 `teacher`（`kind` 仍是 `teacher`），
 *  而计划 §3.6 第 2 条裁定「管理员越过任教范围闸门」，§4.2 裁定「`admin` 访问 `/t/*`
 *  是允许的」—— 用 `teacher` 当这一档的名字会把管理员排除在外。 */
export type RouteRequirement = 'none' | 'student' | 'staff' | 'admin'

/** 会话的四种状态。⚠️ `'unknown'` 与 `'anon'` **必须分开**（文件头末节）。 */
export type SessionStatus = 'unknown' | 'restoring' | 'authed' | 'anon'

interface SessionState {
  status: SessionStatus
  kind: AuthKind | null
  id: number | null
  name: string | null
  role: SessionRole | null
  studentNo: string | null
  staffNo: string | null
  /** 一条**就地**说明：角色不符被弹回自己的首页、或会话过期被送去登录页时，
   *  目标页要能说清「你为什么在这里」。⚠️ 它是内存态（不持久化）：
   *  刷新之后还在的话会变成一句没人知道从哪来的旧话。 */
  notice: string
}

function initial(): SessionState {
  return {
    status: 'unknown',
    kind: null,
    id: null,
    name: null,
    role: null,
    studentNo: null,
    staffNo: null,
    notice: '',
  }
}

/** 三种角色各自的首页（计划 §4.1 逐字要求的那三格）。 */
function homeOf(kind: AuthKind | null, role: SessionRole | null): string {
  if (kind === 'student') return '/s/home'
  if (kind === 'teacher') return role === 'admin' ? '/admin' : '/t/dashboard'
  return '/login'
}

/** in-flight 的那一次 `GET /api/auth/me`。⚠️ 模块级而不是 state 里：
 *  一个 `Promise` 不该被 Pinia 深度响应化（它会尝试代理 `Promise` 的内部槽，
 *  而在某些实现上那会让 `await` 拿到一个代理而不是原对象）。 */
let restoring: Promise<void> | null = null

/** 已经问过后端一次了（答案不管是 `authed` 还是 `anon`）。
 *  ⚠️ 它挡的是「一个未登录的用户点 13 条路由 → 13 次 `me`」：
 *  `restoring` 只能合并**同时**发生的那些，串行的导航各自会再问一次。
 *  ⚠️ 唯一会被清回 `false` 的一档是「后端不可达」——那时答案是「不知道」，
 *  下一次导航该再试一次（后端可能刚起来）。 */
let asked = false

export const useSessionStore = defineStore('session', {
  state: (): SessionState => initial(),

  getters: {
    /** 后端认出了我。 */
    isAuthenticated(state): boolean {
      return state.status === 'authed' && state.kind !== null
    },
    /** **会话还没落定**：那一次 `GET /api/auth/me` 还没有答案。
     *
     *  ⚠️⚠️ 它是「这一帧**该不该说『未登录』**」这件事在全前端的**唯一判据**
     *  （Plan 06 Task 12 / C3；老终审 M7）。两个消费者：本文件的 {@link summary}
     *  与 `components/IdentitySwitcher.vue` 的 `roleLabel`。⚠️ 两处各写一遍
     *  `status === 'unknown' || status === 'restoring'` 的话，下一个人加第五个状态
     *  （例如 `'retrying'`）只会改到其中一处，而漏掉的那一处**静默地**继续说
     *  「未登录」——那正是 M7 那一帧的失效形态。
     *
     *  ⚠️ **两档都算「没落定」**，逐格：
     *   * `'unknown'` —— 初值（一次刷新后的第一帧），**以及**「后端不可达」那一支
     *     （{@link ensureRestored} 刻意退回 `unknown` 而不是 `anon`：把「后端没起」
     *     翻译成「请先登录」是一句假话，逐字理由见那个 action 的注释）；
     *   * `'restoring'` —— 请求在路上。
     *
     *  ⚠️ **它刻意不等于 `!isAuthenticated`**：后者把「问过了、答案是匿名」
     *  （`'anon'`）也算进去，而那一档说「未登录」是**真话**、必须照说。
     *
     *  ⚠️ 而「已登录的用户会不会被弹去 `/login` 再弹回来」那一半**结构上不可达**：
     *  `router.beforeEach` 在任何判定之前 `await session.ensureRestored()`
     *  （`router/index.ts`），而初值是 `'unknown'` 不是 `'anon'`（本文件头末节）。
     *  ⚠️ 那一格由 `scripts/smoke.mjs` 的
     *  「§Task12 会话恢复的那一帧不会说『未登录』」那一条守卫钉住
     *  （它同时钉守卫的 `await` 顺序，故「下一个人把 `await` 挪走」会红）。 */
    isPending(state): boolean {
      return state.status === 'unknown' || state.status === 'restoring'
    },
    /** 是不是教职（教师**或**管理员）。 */
    isStaff(state): boolean {
      return state.kind === 'teacher'
    },
    /** 是不是管理员。⚠️ 判据是 `role`、不是 `kind`：管理员就是一行
     *  `role='admin'` 的 `teacher`，故 `kind` 仍然是 `'teacher'`。 */
    isAdmin(state): boolean {
      return state.kind === 'teacher' && state.role === 'admin'
    },
    /** 我这个角色该落地的首页。 */
    homePath(state): string {
      return homeOf(state.kind, state.role)
    },
    /** 给人看的一行：「学生 <学号> · <姓名>」/「管理员 T0003 · 赵志刚」。
     *  ⚠️ 学生那一格刻意用**占位符**而不是一串具体数字（终审 I1 的同族，实现者在本波
     *  扫到的第 5 个住址）：演示库的学号由 `app/seed/population.py` 按「入学年 + 院系码
     *  + 序号」现造，一个写死的例子会在改 `--students` / `--seed` 之后变假。
     *  教师那一格的 `T0003` 留着 —— 它是 `demo_bootstrap.py` 的 `DEMO_ADMIN_STAFF_NO`，
     *  一个固定工号。 */
    summary(state): string {
      // ⚠️ **会话没落定时不说「未登录」**（Plan 06 Task 12 / C3；老终审 M7）：
      //    那一帧的 `kind` 是 `null` 只因为 `me` 还没回来，而把一个已登录的用户
      //    说成「未登录」是一句假话（它会同时出现在页脚与 `IdentitySwitcher`
      //    的会话条上，两处都读本格 ⇒ 改一处就够）。
      //    ⚠️ 措辞用 `…` 结尾，与本仓既有的 pending 口径逐字同族
      //    （`'读取中…'` / `'加载中…'` / `'登出中…'` / `'名单加载中…'`），
      //    故**不引入任何新的 CSS 裸值**（`npm run check:tokens` 不受影响）。
      //    ⚠️ 判据走 {@link isPending}（`this`），不在这里再写一遍状态清单。
      if (this.isPending) return '身份未确认…'
      if (state.kind === null) return '未登录'
      const label = state.kind === 'student' ? '学生' : state.role === 'admin' ? '管理员' : '教师'
      const login = state.studentNo ?? state.staffNo ?? ''
      return `${label} ${login}${state.name ? ` · ${state.name}` : ''}`
    },
  },

  actions: {
    /** 这一条路由的要求，我这个会话满不满足。
     *  ⚠️ 未登录时 `none` 之外的三档一律 `false`（守卫据此弹去 `/login`）。 */
    satisfies(need: RouteRequirement): boolean {
      if (need === 'none') return true
      if (!this.isAuthenticated) return false
      if (need === 'student') return this.kind === 'student'
      if (need === 'staff') return this.isStaff
      return this.isAdmin
    },

    /** 把后端那六格装进 state。
     *
     *  ⚠️⚠️ **它同时把「我是谁」回写进 `stores/identity.ts`**（一座**兼容桥**）：
     *  Plan 04 的 13 个业务页面一律从 `identity.studentId` / `identity.teacherStaffNo`
     *  读「我是谁」（既用它拼 URL 里的 `{id}`，也用 `v-if="identity.studentId === null"`
     *  决定渲不渲染空态）。Plan 05A 之后真相搬到了本 store，而**逐个改 13 个页面**
     *  会把「加一个登录页」变成「动 13 个页面的取数逻辑」——那正是 Plan 05B
     *  （视觉重构）要再动一遍的那 13 个文件，两波改动叠在同一批文件上会让
     *  「哪一次改坏了」无从判断。
     *  故这里做单向回写（session → identity），13 个页面一行都不用改。
     *  ⚠️ 方向是**单向**的：反过来（identity → session）不成立，因为 identity 里
     *  那份可以被 DEV 切换器随手改，而会话只有后端能改。
     *  ⚠️ 代价（如实记）：`identity.ts` 是**持久化**的，故登出之前那份镜像会留在
     *  `localStorage` 里；`forget()` 因此也调 `clearIdentity()`（它刻意不清 `asOf`）。 */
    adopt(identity: SessionIdentity): void {
      this.status = 'authed'
      this.kind = identity.kind
      this.id = identity.id
      this.name = identity.name
      this.role = identity.role
      this.studentNo = identity.studentNo
      this.staffNo = identity.staffNo
      const dev = useIdentityStore()
      if (identity.kind === 'student') {
        dev.becomeStudent(
          identity.id,
          identity.studentNo === null ? identity.name : `${identity.studentNo} ${identity.name}`,
        )
      } else {
        dev.becomeTeacher(identity.staffNo ?? '', identity.name)
      }
    },

    /** 清空。⚠️ **不清 `notice`**：清掉会话之后紧接着要显示的那一句正是 notice。
     *  ⚠️ 它**也**清掉 `stores/identity.ts` 里那份镜像（{@link adopt} 写进去的），
     *  否则登出之后 13 个页面还会以为自己知道「我是谁」。
     *  ⚠️ 而 `asOf` 不动（`clearIdentity()` 的 docstring 逐字写了理由）。 */
    forget(): void {
      const notice = this.notice
      Object.assign(this, initial(), { notice })
      useIdentityStore().clearIdentity()
    },

    /**
     * 问一次 `GET /api/auth/me`，把结果装进 state。**幂等且只发一次请求**。
     *
     * ⚠️ `force` 只给「刚刚登录/登出完、要立刻反映新状态」那一档用；
     * 路由守卫一律走缓存（`restoring` 那个 in-flight Promise）。
     * ⚠️ 401 **不抛**（它是「没登录」这个正常答案），其余错误**抛**：
     * 后端没起 / 代理没通时把用户弹去登录页是一句假话，
     * 而那一档应当让横幅显示真因（`client.ts` 抛的 `ApiError`）。
     */
    async ensureRestored(force = false): Promise<void> {
      if (!force && asked) return
      if (restoring !== null) return restoring
      this.status = 'restoring'
      restoring = (async () => {
        try {
          this.adopt(await fetchMe())
          asked = true
        } catch (err) {
          if (isUnauthenticated(err)) {
            this.forget()
            this.status = 'anon'
            asked = true
          } else {
            // ⚠️ 后端不可达：退回 `unknown` 而不是 `anon`。守卫对 `unknown` 的处理
            //    是「放行 + 让页面自己的错误横幅说话」，于是「后端没起」表现为
            //    一条 `http_500` / `TypeError` 横幅，而不是「请先登录」那句假话。
            //    ⚠️ 且 `asked` 保持 `false`：下一次导航再试一次（后端可能刚起来）。
            this.forget()
            this.status = 'unknown'
            throw err
          }
        } finally {
          restoring = null
        }
      })()
      return restoring
    },

    /** 登录。⚠️ 成功时后端已经种下 cookie，故这里只需要把那六格装进 state。 */
    async login(kind: AuthKind, loginName: string, password: string): Promise<SessionIdentity> {
      const identity = await loginRequest(kind, loginName, password)
      this.adopt(identity)
      this.notice = ''
      return identity
    },

    /**
     * 登出。⚠️ **后端失败也要清本地**：
     * `POST /api/auth/logout` 在没有会话时回 401（后端 `current_session` 的判定），
     * 而那时用户想做的事正是「回到未登录状态」——把 401 抛回去会让「登出」按钮
     * 在会话已过期之后**点不动**（表现为一条红色横幅 + 仍然停在原页）。
     * ⚠️ 反过来，一个 500 也不该把用户锁在页面上：cookie 是 HttpOnly 的、
     * 前端清不掉它，但**清空本地状态 + 跳登录页**至少让 UI 与现实一致，
     * 而服务端那一行会在 `SESSION_TTL`（2 小时）之后自己过期。如实记录。
     */
    async logout(): Promise<void> {
      try {
        await logoutRequest()
      } catch {
        // 见上面那段：登出的本地效果不依赖服务端那一次成功。
      }
      this.forget()
      this.status = 'anon'
    },

    setNotice(notice: string): void {
      this.notice = notice
    },

    clearNotice(): void {
      this.notice = ''
    },
  },
})

/** 是不是「401 `unauthenticated`」那一档。
 *  ⚠️ 不 `import { ApiError }` 到签名上（那会让本模块的公开面依赖 HTTP 层），
 *  而是**结构判**：`status === 401 && code === 'unauthenticated'`。 */
function isUnauthenticated(err: unknown): boolean {
  return (
    typeof err === 'object' &&
    err !== null &&
    (err as { status?: unknown }).status === 401 &&
    (err as { code?: unknown }).code === 'unauthenticated'
  )
}
