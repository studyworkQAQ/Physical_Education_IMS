/**
 * `api/auth.ts` —— `/api/auth/*` 那**五个**端点在前端的唯一住址（Plan 05A Task 3）。
 *
 * ==============================  ====  ==============  ==========================
 * 路径                             码    身份             本模块的函数
 * ==============================  ====  ==============  ==========================
 * ``POST /api/auth/students/bind``  204  匿名            {@link bindStudent}
 * ``POST /api/auth/teachers/bind``  204  匿名            {@link bindTeacher}
 * ``POST /api/auth/login``          200  匿名            {@link login}
 * ``POST /api/auth/logout``         204  cookie 会话     {@link logout}
 * ``GET  /api/auth/me``             200  cookie 会话     {@link fetchMe}
 * ==============================  ====  ==============  ==========================
 *
 * ⚠️ 是 **5** 个不是 6 个：本仓不做 refresh 令牌，会话用**滑动过期**
 * （后端 `app/auth/sessions.py` 的 `resolve` 每次请求把 `expires_at` 往后推）。
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
 * | `forbidden` | 403 | 绑定时「学号/工号不在册 **或** 验身材料不符」（后端刻意同形） |
 * | `unprocessable_value` | 422 | 弱口令（< 8 字符）。⚠️ 前端**也**拦一道，见 {@link MIN_PASSWORD_LENGTH} |
 * | `request_validation_failed` | 422 | 请求体缺字段（前端的 bug） |
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
 *  @throws {ApiError} 401 `unauthenticated` */
export async function fetchMe(): Promise<SessionIdentity> {
  const raw: unknown = await apiRequest('GET', '/api/auth/me')
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

/** 一个 `ApiError` 的 code 是不是「会话/口令」这一族里的某一个。
 *  ⚠️ 给 `Login.vue` / `Bind.vue` 的分支表用；未知 code 一律走 `default`（不静默）。 */
export function isAuthCode(code: string): boolean {
  return (
    code === 'password_not_bound' ||
    code === 'invalid_credentials' ||
    code === 'password_already_bound'
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
      return '口令不正确。请重新输入（本原型不做登录失败锁定，也不做口令找回）。'
    case 'password_already_bound':
      return `这个${noun}已经绑定过口令了：一个账号只能绑定一次。请直接登录。`
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
