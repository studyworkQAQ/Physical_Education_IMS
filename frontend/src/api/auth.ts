/**
 * `api/auth.ts` —— `/api/auth/*` 那**八个**端点在前端的唯一住址
 * （Plan 05A Task 3 建五个；**Plan 08 Task 4** 加三个）。
 *
 * ==============================  ====  ==============  ==========================
 * 路径                             码    身份             本模块的函数
 * ==============================  ====  ==============  ==========================
 * ``POST /api/auth/students/bind``  204  匿名            {@link bindStudent}
 * ``POST /api/auth/teachers/bind``  204  匿名            {@link bindTeacher}
 * ``POST /api/auth/bind-with-token`` 204 匿名            {@link bindWithToken}
 * ``POST /api/auth/login``          200  匿名            {@link login}
 * ``POST /api/auth/logout``         204  cookie 会话     {@link logout}
 * ``GET  /api/auth/me``             200  cookie 会话     {@link fetchMe}
 * ``POST /api/auth/bind-tokens``    201  **仅管理员**    {@link issueBindToken}
 * ``GET  /api/auth/bind-tokens``    200  **仅管理员**    {@link listBindTokens}
 * ==============================  ====  ==============  ==========================
 *
 * ⚠️ 是 **5** 个不是 6 个：本仓不做 refresh 令牌，会话用**滑动过期**
 * （后端 `app/auth/sessions.py` 的 `resolve` 每次请求把 `expires_at` 往后推）。
 * ⚠️⚠️ **Plan 08 Task 4 之后本模块确实有了「第二种令牌」**，而它与 refresh 令牌
 * 是两件不同的事：绑定令牌是**尚未认证**的人用来设置第一份口令的一次性凭据，
 * 不是用来续会话的。故「不做 refresh」那一句一个字都没变。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 请求体的字段名逐字取自后端 `app/api/schemas/auth.py`（实测，不是抄计划）
 * ---------------------------------------------------------------------------
 * * 学生绑定是 **`birth`**，不是计划 §3.2 写的 `birth_date` —— DB 列实测叫 `birth`
 *   （`app/db/models/organisation.py:125`），而本仓约定「请求体字段名与 DB 列名逐字相同」。
 *   计划那一格已被 Task 1 的实现者顶回并改正。
 * * 教师绑定是 **`staff_no` + `name`**（`teacher` 表实测有 `name` 列）。
 * * 登录是 **`kind` + `login` + `password`**：⚠️ **一个 `login` 字段承载两种登录名**
 *   （学号或工号），而不是 `student_no` / `staff_no` 两个可选字段。理由逐字写在
 *   `LoginCreate` 的 docstring 里（两个可选字段要一条「恰好一个非空」的互斥校验，
 *   而 Pydantic 表达它时 `loc` 指不到具体字段，前端就不知道该把红框画在哪一格上）。
 * * ⚠️ **令牌绑定是 `token` + `password`，就两格**（Plan 08 Task 4）：
 *   它**刻意不含** `kind` / 学号 / 出生日期 —— 令牌**自带目标**
 *   （`bind_token.kind` + `bind_token.login` 两列），再交一遍就是第二份「这次是给谁绑」，
 *   而两份漂开的失效形态是「令牌发给 A、请求体写的是 B」。逐字理由见
 *   后端 `TokenBindCreate` 的 docstring。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 错误档：前端一律按 `code` 分支（`ApiError.code`），不按 `message`
 * ---------------------------------------------------------------------------
 * 三个自定义 code 不在后端 `_CODE_BY_STATUS` 那张表里（它按状态码折不出它们），
 * 故 `client.ts` 的 `ERROR_CODES` 里没有它们、`describeCode` 会落到 `http_<status>`
 * 那一档。⚠️ **那是无害的**：本模块的两个消费者（`Login.vue` / `Bind.vue`）自己
 * 按 code 分支并给出人话，横幅只是补充显示后端那句原文。
 *
 * | code | 状态 | 前端该做什么 |
 * |---|---|---|
 * | `password_not_bound` | 403 | 送他去 `/bind`（并把 `kind` 与登录名带过去） |
 * | `invalid_credentials` | 401 | 停在登录页、清空口令框 |
 * | `password_already_bound` | 409 | 「这个账号已经绑定过了，请直接登录」 |
 * | `forbidden` | 403 | 绑定时「学号/工号不在册 **或** 验身材料不符」（后端刻意同形）；<br>令牌档「令牌不正确」；⚠️ **自助绑定被关掉时也是它**（后端那句原文点名了 `PE_ALLOW_SELF_BIND`） |
 * | `bind_token_spent` | 409 | **Plan 08 Task 4**：「这张令牌已经用过了」→ 叫他找教务干事重签 |
 * | `bind_token_expired` | 403 | **Plan 08 Task 4**：「这张令牌过期了」→ 同上 |
 * | `unprocessable_value` | 422 | 弱口令（< 8 字符）。⚠️ 前端**也**拦一道，见 {@link MIN_PASSWORD_LENGTH} |
 * | `request_validation_failed` | 422 | 请求体缺字段（前端的 bug） |
 * | `not_found` | 404 | **Plan 08 Task 4**：签发令牌时「这个学号/工号不在册」 |
 */
import { ApiError, apiRequest } from './client'

/** `kind` 的取值域。⚠️ 唯一所有者是后端 `UserSession.KINDS`；本处是它在 TS 里的镜像。
 *  **管理员不在里面**：管理员就是一行 `role='admin'` 的 `teacher`（用户 2026-10-12 裁定），
 *  故登录表单只有两档，而**跳哪个首页**由响应体里的 `role` 决定。 */
export const AUTH_KINDS = ['student', 'teacher'] as const
export type AuthKind = (typeof AUTH_KINDS)[number]

/** `role` 的取值域（学生恒为 `student`；教师是 `teacher` 或 `admin`）。 */
export const SESSION_ROLES = ['student', 'teacher', 'admin'] as const
export type SessionRole = (typeof SESSION_ROLES)[number]

/** 口令的最短长度。⚠️ **镜像**后端 `app/auth/passwords.py` 的 `MIN_PASSWORD_LENGTH`。
 *  前端拦一道只为省一次往返；**后端那一道是唯一权威**（它给 422 `unprocessable_value`，
 *  而前端这一道给一句就地提示，两者刻意不共用措辞）。 */
export const MIN_PASSWORD_LENGTH = 8

/** `POST /api/auth/login` 与 `GET /api/auth/me` 的响应体（**逐字同形**：后端两个端点
 *  共用同一个 `SessionIdentityRead` 与同一个 `_identity_body`）。
 *
 *  ⚠️ 六格而不是五格：后端把 `Identity.login` **拆成 `student_no` / `staff_no` 两格**
 *  （互斥、另一个为 `null`），因为前端要按 `kind` 显示「学号」或「工号」两个不同的
 *  中文标签，而一个字段名给不出标签。本模块再把它们收成 camelCase 的
 *  {@link SessionIdentity.studentNo} / {@link SessionIdentity.staffNo}。 */
export interface SessionIdentity {
  readonly kind: AuthKind
  readonly id: number
  readonly name: string
  readonly role: SessionRole
  readonly studentNo: string | null
  readonly staffNo: string | null
}

/**
 * 后端那六格 → {@link SessionIdentity}；**形状不对就返回 `null`**。
 *
 * ⚠️ 为什么不写 `res as SessionIdentity`：`apiRequest<T>` 的 `T` 是一个**断言**，
 * 不是校验。后端加/改一格时，一个 `as` 会让「`role` 是 `undefined`」静默流进
 * 路由守卫，而 `undefined === 'admin'` 是 `false` —— 失效方向虽然安全（少给权限），
 * 表现却是「管理员进了 `/admin` 看到一句『你不是管理员』」，离真因隔一整层
 * （后端 `GET /api/auth/me` 的 docstring 逐字描述过这个形状）。
 * 故这里逐格验，验不过就当成「没有会话」，让用户重新登录。
 */
function parseIdentity(raw: unknown): SessionIdentity | null {
  if (typeof raw !== 'object' || raw === null) return null
  const body = raw as Record<string, unknown>
  const kind = body.kind
  const role = body.role
  if (typeof kind !== 'string' || !AUTH_KINDS.includes(kind as AuthKind)) return null
  if (typeof role !== 'string' || !SESSION_ROLES.includes(role as SessionRole)) return null
  if (typeof body.id !== 'number' || typeof body.name !== 'string') return null
  return {
    kind: kind as AuthKind,
    id: body.id,
    name: body.name,
    role: role as SessionRole,
    studentNo: typeof body.student_no === 'string' ? body.student_no : null,
    staffNo: typeof body.staff_no === 'string' ? body.staff_no : null,
  }
}

/** 后端回了 200 而形状不对时抛它（`parseIdentity` 返回 `null` 的那一档）。
 *  ⚠️ 它**不是** `ApiError`：那一类说的是「后端拒绝了」，这一类说的是「后端答应了、
 *  而说的话前端听不懂」。两者的下一步动作不同（前者看 code，后者看后端是不是漂了）。 */
export class UnexpectedIdentityBody extends Error {
  readonly raw: unknown
  constructor(raw: unknown) {
    super('GET /api/auth/me 或 POST /api/auth/login 的响应体不是预期的六格')
    this.name = 'UnexpectedIdentityBody'
    this.raw = raw
  }
}

/** 登录。成功时后端**同时**种下 `Set-Cookie: pe_session`（HttpOnly，故 JS 读不到）。
 *  @throws {ApiError} 403 `password_not_bound` / 401 `invalid_credentials` / 422 */
export async function login(
  kind: AuthKind,
  loginName: string,
  password: string,
): Promise<SessionIdentity> {
  const raw: unknown = await apiRequest('POST', '/api/auth/login', {
    body: { kind, login: loginName, password },
  })
  const parsed = parseIdentity(raw)
  if (parsed === null) throw new UnexpectedIdentityBody(raw)
  return parsed
}

/** 我是谁。⚠️ **它是「刷新页面之后怎么恢复会话」的唯一答案**：cookie 是 HttpOnly 的，
 *  前端读不到它，故「我登录了没」只能问后端。401 就是「没登录」（或已过期/已吊销）。
 *
 *  @param signal ⚠️ **Plan 06 Task 15（终审 S3-⑤）加的**：那一次「问后端我是谁」必须有
 *    **上限**。改前本函数**不传** `signal`（`api/client.ts` 只把它当可选入参转交），
 *    于是一个接了 TCP 连接却不响应的 `/api/auth/me` 会让 `router.beforeEach` 里那一次
 *    `await session.ensureRestored()` **无限期**挂住 ⇒ 页面永远停在「身份未确认…」。
 *    唯一的调用方（`stores/session.ts` 的 `ensureRestored`）传的是
 *    `AbortSignal.timeout(RESTORE_TIMEOUT_MS)`；到点时 `fetch` 抛一个
 *    `name === 'TimeoutError'` 的 `DOMException`（**不是** `ApiError`），由调用方分支。
 *  @throws {ApiError} 401 `unauthenticated`；`DOMException` `TimeoutError`（到点没回答） */
export async function fetchMe(signal?: AbortSignal): Promise<SessionIdentity> {
  const raw: unknown = await apiRequest('GET', '/api/auth/me', { signal })
  const parsed = parseIdentity(raw)
  if (parsed === null) throw new UnexpectedIdentityBody(raw)
  return parsed
}

/** 登出：后端**吊销** `user_session` 那一行（写 `revoked_at`）+ 让 cookie 过期。
 *  ⚠️ 于是旧 cookie 立刻不能用 —— 这是本仓选「服务端会话表」而不是「签名 cookie」的
 *  第一条理由（`smoke.mjs` 第 17 步专门钉这一拍）。
 *  @throws {ApiError} 401 `unauthenticated`（本来就没登录） */
export async function logout(): Promise<void> {
  await apiRequest<void>('POST', '/api/auth/logout')
}

/** 学生**首次**绑定口令：学号 + **出生日期** + 新口令 → 204。
 *
 * ⚠️ **成功后不自动登录**（后端刻意不回 `Set-Cookie`）：绑定与登录是两件事，
 * 故 `Bind.vue` 在 204 之后自己再打一次 {@link login}。
 * @throws {ApiError} 422 `unprocessable_value`（弱口令，排最前）/
 *   403 `forbidden`（不在册或出生日期不符，**两档同形**）/
 *   409 `password_already_bound`（排在 403 之后）/ 422 `request_validation_failed` */
export async function bindStudent(
  studentNo: string,
  birth: string,
  password: string,
): Promise<void> {
  await apiRequest<void>('POST', '/api/auth/students/bind', {
    body: { student_no: studentNo, birth, password },
  })
}

/** 教师**首次**绑定口令：工号 + 姓名 + 新口令 → 204。四档与 {@link bindStudent} 同构。
 *  ⚠️ `role` **不由本端点决定**（绑定不会把人变成管理员）；`role` 只能由
 *  `POST/PATCH /api/teachers`（仅管理员）改。 */
export async function bindTeacher(
  staffNo: string,
  name: string,
  password: string,
): Promise<void> {
  await apiRequest<void>('POST', '/api/auth/teachers/bind', {
    body: { staff_no: staffNo, name, password },
  })
}

/* ===========================================================================
   ⚠️⚠️ Plan 08 Task 4：**一次性绑定令牌**那三个
   =========================================================================== */

/** **用一次性令牌**首次绑定口令：令牌 + 新口令 → 204（⚠️ 匿名）。
 *
 * ⚠️⚠️ **请求体只有两格**（`token` + `password`）：令牌**自带目标**，故这里
 * **不交** `kind`、学号或出生日期。逐字理由见本文件头第四节与后端
 * `TokenBindCreate` 的 docstring。
 *
 * ⚠️ **它是那条「更强的路」**：`birth` 在这里一个字都不参与判定，故
 * 「读过名册的教职能替任何未绑定账号抢绑」在本端点上不成立。
 * ⚠️ 而它**不受** `PE_ALLOW_SELF_BIND` 那个开关影响（开关只管上面两个自助端点），
 * 于是「先验证令牌流程通了、再关掉自助绑定」这个切换顺序中间没有一刻是「谁都绑不上」。
 *
 * ⚠️ **成功后不自动登录**（与 {@link bindStudent} 逐字同一条口径）：
 * `Bind.vue` 在 204 之后自己再打一次 {@link login}。
 * @throws {ApiError} 422 `unprocessable_value`（弱口令，排最前）/
 *   403 `forbidden`（令牌不正确 / 被限流锁定，**两档同形**）/
 *   409 `bind_token_spent`（这张已经用过了）/
 *   403 `bind_token_expired`（这张过期了）/
 *   409 `password_already_bound`（目标账号已经绑过了）/ 422 `request_validation_failed` */
export async function bindWithToken(token: string, password: string): Promise<void> {
  await apiRequest<void>('POST', '/api/auth/bind-with-token', {
    body: { token, password },
  })
}

/** {@link issueBindToken} 的响应体（七格）。
 *
 *  ⚠️⚠️ **`token` 那一格是明文，而它只在这一个响应里出现一次**：后端库里存的是
 *  PBKDF2 哈希（`app/auth/passwords.py` 那一套，与口令同一条口径），
 *  故 {@link listBindTokens} **读不回**它。⇒ 调用方（管理台那一格面板）
 *  **必须当场把它显示出来**，页面一刷新就再也拿不到了。
 *  ⚠️ 这一格与 `class_session.rpe_token`（教师念给学生的一次性快评口令）同族，
 *  而两者**刻意不同档**：那一格每次 GET 都能重新读到（它是「一节课的口令」，
 *  教师会在课堂上反复看一眼），本格**不能**（它是一张能接管一个账号的凭据）。 */
export interface IssuedBindToken {
  readonly id: number
  readonly kind: AuthKind
  readonly login: string
  readonly token: string
  readonly issuedAt: string
  readonly expiresAt: string
  readonly issuedBy: string | null
}

/** {@link listBindTokens} 的一行（**七格 = 后端 9 列减去 `token_id` 与 `token_hash`**）。
 *
 *  ⚠️ **没有明文、也没有哈希**：后端 `BindTokenRead` 结构上就没有那两格，
 *  故「明文只出现一次」在**读侧**也成立（不是靠前端克制住不显示）。 */
export interface BindTokenRow {
  readonly id: number
  readonly kind: AuthKind
  readonly login: string
  readonly issuedAt: string
  readonly expiresAt: string
  readonly usedAt: string | null
  readonly issuedBy: string | null
}

/** `GET /api/auth/bind-tokens` 的四个信封键（与泛型 list 逐字同形）。 */
export interface BindTokenPage {
  readonly items: readonly BindTokenRow[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}

/** 后端那七格 → {@link IssuedBindToken}；**形状不对就抛**（不用 `as` 断言）。
 *
 *  ⚠️ 为什么逐格验：`apiRequest<T>` 的 `T` 是一个**断言**、不是校验，
 *  而本函数交出去的那一格 `token` 是**一次性**的 —— 一个 `undefined` 会被
 *  管理台画成一个空框，教务干事抄下那个空框交给学生，而**库里那张令牌是真的**
 *  （于是没人能用它，也没人知道为什么）。逐格验把那一档变成一句响亮的报错。
 *  ⚠️ 姿势与 {@link parseIdentity} 同一条，差别在失效方向：那一格返回 `null`
 *  （「没有会话」是一个可接受的答复），本格**必须抛**（「签发成功了、而明文丢了」
 *  不是一个可接受的答复）。 */
function parseIssued(raw: unknown): IssuedBindToken {
  if (typeof raw !== 'object' || raw === null) {
    throw new UnexpectedBindTokenBody(raw)
  }
  const body = raw as Record<string, unknown>
  const kind = body.kind
  if (
    typeof body.id !== 'number' ||
    typeof kind !== 'string' ||
    !AUTH_KINDS.includes(kind as AuthKind) ||
    typeof body.login !== 'string' ||
    typeof body.token !== 'string' ||
    body.token === '' ||
    typeof body.issued_at !== 'string' ||
    typeof body.expires_at !== 'string'
  ) {
    throw new UnexpectedBindTokenBody(raw)
  }
  return {
    id: body.id,
    kind: kind as AuthKind,
    login: body.login,
    token: body.token,
    issuedAt: body.issued_at,
    expiresAt: body.expires_at,
    issuedBy: typeof body.issued_by === 'string' ? body.issued_by : null,
  }
}

/** 后端回了 201 而形状不对时抛它。⚠️ 与 {@link UnexpectedIdentityBody} 同族同理由。 */
export class UnexpectedBindTokenBody extends Error {
  readonly raw: unknown
  constructor(raw: unknown) {
    super('POST /api/auth/bind-tokens 的响应体不是预期的七格（明文令牌可能已经丢了：库里那一张仍然活着，请重签一张）')
    this.name = 'UnexpectedBindTokenBody'
    this.raw = raw
  }
}

/** （**仅管理员**）签发一张一次性绑定令牌 → 201 + **明文令牌（只回这一次）**。
 *
 * @throws {ApiError} 401 `unauthenticated`（匿名）/ 403 `forbidden`（学生 cookie、
 *   或在册教师但不是管理员）/ 404 `not_found`（这个学号/工号不在册）/
 *   409 `password_already_bound`（**这个账号已经绑定过口令了 ⇒ 拒发**，
 *   逐字理由见后端 `issue_bind_token` 的 docstring 第 2 档）/ 422 */
export async function issueBindToken(
  kind: AuthKind,
  loginName: string,
): Promise<IssuedBindToken> {
  const raw: unknown = await apiRequest('POST', '/api/auth/bind-tokens', {
    body: { kind, login: loginName },
  })
  return parseIssued(raw)
}

/** （**仅管理员**）已签发令牌的一页（`id DESC` = 最新在前）。
 *
 *  ⚠️ **响应体里没有明文、也没有哈希**（{@link BindTokenRow} 的 docstring）。
 *  ⚠️ 两个时刻格是 **naive 本地时刻**（后端 `app/auth/sessions.py` 的 `now()`：
 *  先转到 `Asia/Shanghai`、再摘掉 tzinfo），故序列化成 `2026-10-18T10:00:00`
 *  而**不带** `Z` 后缀。⚠️ 前端**不得**按 UTC 解释它们（差 8 小时）——
 *  与 `api/types.ts` 里 `AuditLogItem.at` 那一条逐字同一条口径。
 *  @throws {ApiError} 401 / 403（与 {@link issueBindToken} 同一条身份口径） */
export async function listBindTokens(limit = 50, offset = 0): Promise<BindTokenPage> {
  const raw = await apiRequest<Record<string, unknown>>(
    'GET',
    `/api/auth/bind-tokens?limit=${limit}&offset=${offset}`,
  )
  const items = Array.isArray(raw.items) ? (raw.items as Record<string, unknown>[]) : []
  return {
    items: items.map((row) => ({
      id: Number(row.id),
      kind: (row.kind === 'teacher' ? 'teacher' : 'student') as AuthKind,
      login: String(row.login ?? ''),
      issuedAt: String(row.issued_at ?? ''),
      expiresAt: String(row.expires_at ?? ''),
      usedAt: typeof row.used_at === 'string' ? row.used_at : null,
      issuedBy: typeof row.issued_by === 'string' ? row.issued_by : null,
    })),
    total: Number(raw.total ?? 0),
    limit: Number(raw.limit ?? limit),
    offset: Number(raw.offset ?? offset),
  }
}

/** 一个 `ApiError` 的 code 是不是「会话/口令」这一族里的某一个。
 *  ⚠️ 给 `Login.vue` / `Bind.vue` 的分支表用；未知 code 一律走 `default`（不静默）。 */
export function isAuthCode(code: string): boolean {
  return (
    code === 'password_not_bound' ||
    code === 'invalid_credentials' ||
    code === 'password_already_bound' ||
    code === 'bind_token_spent' ||
    code === 'bind_token_expired'
  )
}

/** 把一档 `ApiError` 折成一句**就地**的人话（画在表单下方，不是横幅）。
 *  ⚠️ 后端的 `message` 仍然会被横幅原样显示，故这里只写「下一步做什么」。 */
export function authAdvice(err: unknown, kind: AuthKind): string {
  if (!(err instanceof ApiError)) return '请求没有到后端（后端没起、或代理没通）。看浏览器控制台。'
  const noun = kind === 'student' ? '学号' : '工号'
  switch (err.code) {
    case 'password_not_bound':
      return `这个${noun}还没有绑定口令（或不在名册上）。请先走下面的「首次绑定口令」。`
    case 'invalid_credentials':
      /* ⚠️ 改前这一句逐字写着「本原型不做登录失败锁定，也不做口令找回」，而锁定自
         Plan 06 Task 3 起真的在，且**这一档就是锁定档**（后端回的是与「口令错」
         逐字节相同的 401，理由见 api/client.ts 的 `invalid_credentials`）。
         ⇒ 改后不再叫人「反复重输」：重输解不开锁、也不会把锁推后。见 spec §13.20。
         ⚠️ 本段刻意用**块注释**而不是 `//`：理由见 components/ApiErrorBanner.vue
         同位置那一段（`stripComments` 不剥 `//`，写在 `//` 里的提及会被数成本身）。 */
      return '口令不正确。请重新输入（连错多次会被临时锁定，稍后再试；本原型不做口令找回）。'
    case 'password_already_bound':
      return `这个${noun}已经绑定过口令了：一个账号只能绑定一次。请直接登录。`
    case 'bind_token_spent':
      /* ⚠️ **Plan 08 Task 4**。这一档**刻意与 `forbidden` 可区分**（后端给了它自己的
         code），逐字理由见后端 `BIND_TOKEN_SPENT` 的注释：走到这一档的人**已经持有
         那张凭据**，故告诉他「它用过了」不泄漏任何东西，而不告诉他会让一个合法新生
         反复重输、然后被绑定限流锁 60 分钟。 */
      return '这张绑定令牌已经用过了（一张令牌只能兑换一次）。请直接登录；'
        + '若你并没有绑定成功，请找教务干事重签一张。'
    case 'bind_token_expired':
      return '这张绑定令牌已经过期了。请找教务干事重签一张（过期令牌不能续期）。'
    case 'unprocessable_value':
      return `口令至少 ${MIN_PASSWORD_LENGTH} 个字符。${err.message}`
    case 'forbidden':
      return err.message
    case 'request_validation_failed':
      return `请求体没通过校验（${err.message}）。⚠️ 这一档通常是前端的 bug，不是用户输错了。`
    default:
      return `${err.code}：${err.message}`
  }
}
