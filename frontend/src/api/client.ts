/**
 * `client.ts` —— `fetch` 的一层薄封装。**职责恰好五件**（Plan 04 Task 1 的四件 +
 * Plan 05A Task 3 加的第五件）：
 *
 *  1. 注入身份头（**仅 DEV 构建**，从 `stores/identity` 读；见下面那一节）；
 *  2. 把后端的统一错误体 `{"error": {code, message, detail}}` 解析成 {@link ApiError}
 *     并抛出（带 `code`）；
 *  3. 拼查询参数（`as_of` / `limit` / `offset` / …）；
 *  4. **`204` 不解析 body**（`res.json()` 在 204 上会抛 `SyntaxError`；
 *     ⚠️ 后端的 **8** 个 DELETE 端点全是 204：`teachers` / `students` /
 *     `course-sections` / `enrollments` / `fitness-test-batches` /
 *     `body-compositions` / `interest-surveys` / `class-sessions`）；
 *  5. **认出「会话失效」那一档并广播它**（401 `unauthenticated` → `api/expiry.ts`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `credentials: 'same-origin'`（Plan 05A Task 3 改的一格）
 * ---------------------------------------------------------------------------
 * **本处此前逐字写着「不设 `credentials`」**，引用的是 Plan 04 的 Global Constraints
 * 第 1 条：后端 `app/main.py` 的 CORSMiddleware 是 `allow_origins=["*"]` 且**不带**
 * `allow_credentials`，而浏览器规范禁止 `Access-Control-Allow-Origin: *` 与
 * credentials 并存 —— 一旦设了 `credentials: 'include'`，**所有跨域请求当场失败**
 * （不是「cookie 没带上」，是整个响应被浏览器丢掉）。
 *
 * ⚠️ **那一段论证在 Plan 05A 之后只对 `'include'` 成立，对 `'same-origin'` 不成立**
 * （计划 §2.2 的更正）：`vite.config.ts` 的 `server.proxy` 把 `/api` 转到同源，
 * 故浏览器看到的是**同源请求**，`SameSite=Lax` 的第一方 cookie 照常发出去，
 * 而 CORS 一行都不用动（同源请求根本不走 CORS）。
 *
 * ⚠️ 而**显式写出 `'same-origin'` 是有意义的、不是一句废话**（同源下它本来就是
 * `fetch` 的缺省值）：它把「本前端假定同源部署」这个前提**写在了代码里**。
 * 于是若部署方把 `VITE_API_BASE` 指到一个跨源地址，`credentials` 的语义
 * 会立刻从「带上」变成「不带」（会话静默失效、每个端点 401），
 * 而那一格正是排查时第一个要看的地方 —— 不写出来，「同源」这个前提就是隐形的。
 * ⚠️ **跨源部署要连 CORS 一起改**（spec §13.4.5 逐字记了那一档）：
 * ① `allow_origins` 改成显式白名单（不能是 `*`）② `allow_credentials=True`
 * ③ cookie 加 `Secure` 且 `SameSite=None` ④ 本处改成 `'include'`
 * ⑤ **补 CSRF 双重提交令牌**（计划 §3.5 那条论证依赖同源前提）。
 * ⚠️ **Plan 06 Task 4 兑现了后端那两格（①②）**：生产档（`PE_ENV=prod`）下
 * `allow_origins` 读 `PE_CORS_ORIGINS`（逗号分隔白名单，**缺省空 = 一个
 * `CORSMiddleware` 都不挂** = 拒绝跨域），白名单非空时带 `allow_credentials=True`；
 * 而 `prod` 下装配完还有一道**启动自检**，CORS 被挂成 `*` 或 `Secure` 没开就
 * `raise`（服务起不来）。⚠️ **③④⑤ 仍然没做**（`samesite` 恒为 `"lax"`），
 * 故本处那句「本前端假定同源部署」的前提**一字未变**。逐字见 spec §13.8。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 身份头降级成 DEV-only（Plan 05A Task 3）
 * ---------------------------------------------------------------------------
 * Plan 05A 之后**真实的身份载体是 `pe_session` cookie**（HttpOnly，故 JS 读不到），
 * 而 `X-Student-Id` / `X-Teacher-Staff-No` 那两个头只在后端
 * `PE_ALLOW_HEADER_IDENTITY=1` 时被接受（生产缺省是 `"0"` = 只认 cookie）。
 * ⚠️ **Plan 06 Task 4 起它在 `PE_ENV=prod` 下被强制关**（设成 `1` 也忽略，
 * 只在装配时打一条 warning），故「生产构建里一个身份头都不发」这一格
 * 从「前端的自律」升级成「后端也不认」——两侧同时关掉。
 * 故本处**只在 DEV 构建里**注入它们（配合 `stores/identity` 那个 DEV-only 的
 * 身份切换器 / `src/dev/identity-url.ts` 的深链接）；`import.meta.env.DEV` 是
 * 编译期常量，Vite 在生产构建里会把那一支整个摇掉。
 * ⚠️ 生产构建里**一个身份头都不发**：那正是「请求头那条通道是过渡态」的可执行形式。
 */
import { fireSessionExpired } from './expiry'
import { useIdentityStore } from '../stores/identity'

/**
 * baseURL 的**唯一住址**。
 * 开发时是空串（走 `vite.config.ts` 的 proxy）；生产时由部署方注入 `VITE_API_BASE`。
 */
const BASE_URL: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

/** 身份头的名字。⚠️ 与后端 `app/api/deps.py` 的 `Header(None)` 形参名逐字对应
 *  （FastAPI 把 `x_student_id` 折成 `X-Student-Id`）。 */
export const STUDENT_HEADER = 'X-Student-Id'
export const TEACHER_HEADER = 'X-Teacher-Staff-No'

/**
 * 后端可能回给前端的**全部** `error.code`。
 *
 * ⚠️ **前端一律按 `code` 分支，不要按 `message` 字符串匹配** —— `message` 是给
 * 人看的中文、会随措辞调整（后端 `app/api/errors.py` 的模块 docstring 逐字写了
 * 「``code`` 是给**程序**看的稳定标识，``message`` 是给**人**看的」）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 这份清单是**实测**出来的，不是抄计划的（计划约束第 8 条那份 11 个的清单
 * 里有 **4 个不存在**：`unknown_teacher` / `unknown_student` /
 * `rpe_already_submitted` / `conflict`。见 task-1-report.md 第 5 节）
 * ---------------------------------------------------------------------------
 *
 * 数法（硬规矩 #89：AST 口径，不用正则数源码）：对 `backend/app/api/**.py`
 * 做 `ast.walk`，挑出全部 `error_response(...)` 调用点（**15** 个），把第 2 个
 * 位置实参（`code`）解出来；解不出来的（传的是名字而不是字面量）逐个回源码读；
 * 再把 `app/api/errors.py` 的 `_CODE_BY_STATUS` 与 `http_<状态码>` 那一档折算进来。
 *
 * 合计 **17 个具名 code + 1 个 `http_*` 家族**（Plan 04 是 14 个；Plan 05A Task 1
 * 给 `/api/auth/*` 加了 3 个：`password_not_bound` / `invalid_credentials` /
 * `password_already_bound`。⚠️ 那 3 个**不走** `_CODE_BY_STATUS`
 * （它按状态码折不出它们：403 折出来的是 `forbidden`、401 是 `unauthenticated`、
 * 409 是 `integrity_conflict`），而是经 `app/api/errors.py` 的 `error_response`
 * 直接出去 —— 后端 `app/api/routers/auth.py` 的模块 docstring 逐字交代了这个形状）。
 */
export const ERROR_CODES = {
  /* ---- 全局异常处理器的 6 档（app/api/errors.py）---- */

  /** **401**。缺会话（Plan 05A 之前是「缺身份请求头」）。触发点：
   *  `app/api/deps.py` 的 `current_session`（`GET /api/auth/me` / `POST /api/auth/logout`
   *  缺 `pe_session` cookie 或那一行已过期/已吊销），以及 `current_student` /
   *  `current_teacher` 的**第三档**（既没有有效 cookie、过渡通道又关着）。
   *  由 `errors.py` 的 `_http_exception` 按 `_CODE_BY_STATUS[401]` 折成本 code。
   *  ⚠️ `client.ts` 认出它之后会广播一次「会话失效」（`api/expiry.ts`），
   *  装配点（`main.ts`）据此清掉 `stores/session.ts` 并跳 `/login?next=<原路径>`。
   *  ⚠️ 计划说的 `unknown_teacher` / `unknown_student` **不存在**：
   *  「工号/学号不在册」是 **403 `forbidden`**（见下面那一档），不是 401。 */
  unauthenticated: { status: 401, hint: '没有有效的会话。请重新登录（pe_session cookie 缺失、已过期或已吊销）。' },

  /** **403**。「你不是这个人」与「这个人不在册」**刻意同形**（`app/api/deps.py`
   *  的 `require_scope` docstring 逐字写了理由：区分两者等于把在册名单告诉调用方）。
   *  五个触发点：
   *   - `deps.py:202` —— `X-Student-Id` 与目标数据的所有者不是同一个人（越权）；
   *   - `deps.py:207` —— 那个学号在 `student` 表里查无此人；
   *   - `deps.py:242` —— 那个工号在 `teacher` 表里查无此人（`require_teacher`）；
   *   - `deps.py:289` —— 这个教学班不是他任教的班（`require_teaches_section`）；
   *   - `deps.py:348` —— 这个学生不在他**本学期**任教的任何班里（`require_teaches_student`）。 */
  forbidden: { status: 403, hint: '当前身份无权访问这一份数据（或这个身份不在册）。' },

  /** **404**。查不到那一行。两个来源：`app/api/crud.py:348` 的 `_get_or_404`
   *  （`raise HTTPException(404)`）与 `errors.py:118` 的 `NoResultFound` 处理器
   *  （`scalar_one()` / `one()` 查不到行）。 */
  not_found: { status: 404, hint: '这一行不存在（或它的 id 打错了）。' },

  /** **409**。撞约束。三个来源，**同一个 code**：
   *   - `errors.py:112` 的全局 `IntegrityError` 处理器（`message` 是 DBAPI 的原文，
   *     例如 `UNIQUE constraint failed: student.student_no`）；
   *   - `crud.py:697` —— POST 撞自然键（`upsert` 撞键不抛异常，故由端点判）；
   *   - `crud.py:763` —— DELETE 被 `on_delete='restrict'` 挡住（**有子表指着它**）。
   *  ⚠️ 计划约束第 8 条写的是 `conflict`，**那个 code 不存在**，逐字是
   *  `integrity_conflict`（`errors.py:60` 的 `_CODE_BY_STATUS[409]`）。
   *  ⚠️ 第三档对管理台最重要：横幅要说清「这个 X 还被 N 个 Y 引用」，
   *  而「N 个 Y」在 `message` 里（后端点名了子表），**不在 `detail` 里**。 */
  integrity_conflict: { status: 409, hint: '与库里已有的一行冲突，或这一行还被别的数据引用着。' },

  /** **422**。domain 层或 YAML 加载器抛的 `ValueError`（`errors.py:103`）。
   *  `message` 是**原话照发**（它逐字写明「哪个键、哪个文件、期望什么」）。
   *  例如 `POST /api/alerts/{id}/handle` 的 `action='note'` 而备注为空。 */
  unprocessable_value: { status: 422, hint: '这个值在业务上不成立（后端把原因写在下面那句话里）。' },

  /** **422**。Pydantic 的请求校验失败（`errors.py:129`）。`detail` 是那份带
   *  `loc` 的清单。⚠️ 计划约束第 4 条专门点过这一档：若 `loc` 里是
   *  `["path", "xxx_id"]`，那**几乎一定是路由顺序或路径拼错**，不是数据问题。
   *  ⚠️ 另一个后果：`X-Student-Id: abc`（头存在但不是整数）是**本 code 的 422**，
   *  不是 401（`deps.py:139-143` 的 docstring 逐字交代了）。 */
  request_validation_failed: { status: 422, hint: '请求参数没通过校验（下面列出的是哪一格）。' },

  /** **500**。任何没人接的异常（`errors.py:153`）。`message` 固定成「服务器内部错误」、
   *  `detail` 恒为 `null` —— 堆栈只进日志、不进响应体。 */
  internal_error: { status: 500, hint: '服务器内部错误（堆栈在后端日志里，不在这里）。' },

  /* ---- 特例端点自己造的 10 档（Plan 05A 起：原 7 档 + `/api/auth/*` 的 3 档）---- */

  /** **403**。`POST /api/auth/login`：这个学号/工号**不在册**、或**在册但没绑口令**。
   *  触发点：`app/api/routers/auth.py` 的 `login`，code 常量是那里的
   *  `PASSWORD_NOT_BOUND`。⚠️ 它与 `invalid_credentials` **刻意可区分**
   *  （两档的下一步动作相反：一个该去绑定、一个该重输口令），代价是泄漏了
   *  「这个学号在不在册」——控制者裁定接受，已写进 spec 的已知局限。 */
  password_not_bound: { status: 403, hint: '这个账号还没有绑定口令（或不在名册上）：请先走绑定流程。' },

  /** **401**。`POST /api/auth/login`：绑过口令、而口令不对。
   *  ⚠️ 它**不该**触发 `api/expiry.ts` 的「会话失效」广播（我们已经在登录页上了），
   *  故 `apiRequest` 的判据是 `code === 'unauthenticated'` 而不是 `status === 401`。
   *  ⚠️⚠️ **这一档同时是「已被锁」那一档**：同一个标识在窗口内失败到阈值之后，
   *  后端回的是与「口令错」**逐字节相同**的 401 / 82 B（`invalid_credentials`），
   *  故前端**结构上分辨不出**「口令错」与「被锁」（那是刻意的：不给撞库的人
   *  「这个账号存在且已被锁」这个信号）。⇒ 于是这一句 hint 不许说「不做锁定」
   *  （改前逐字写着「本原型不做登录失败锁定，也不做口令找回」= 一句关于安全的假话，
   *  终审 S1-2），也不许承诺「再试一次就好」。逐字口径见 spec §13.4.6 与 §13.20。 */
  invalid_credentials: { status: 401, hint: '口令不正确。连错多次会被临时锁定，稍后再试；本原型不做口令找回。' },

  /** **409**。`POST /api/auth/{students,teachers}/bind`：这个账号已经绑定过了。
   *  ⚠️ 它**排在 403 之后**（后端 `bind_student` 的 docstring 逐字交代了理由：
   *  反过来会让一个不知道验身材料的人读出「这个学号绑定过了没有」）。
   *  ⚠️ 判据是 UPDATE 的**影响行数**（`WHERE … AND password_hash IS NULL`），
   *  不是「先读出来看是不是 NULL」——后者是 check-then-act，两个并发请求都能过。 */
  password_already_bound: { status: 409, hint: '这个账号已经绑定过口令了：一个账号只能绑定一次，请直接登录。' },

  /** **409**。处置一条 `status != 'pending'` 的预警。
   *  触发点：`app/api/routers/alerts.py:240-249`，code 常量在 `alerts.py:184`。
   *  ⚠️ 它挡的是「减量 20%」被点两次：本周训练单是该周全部 factor 的**累乘**，
   *  再点一次就是 0.8 × 0.8 = 0.64。教师改主意的正确处置是等下一轮求值。 */
  alert_not_pending: { status: 409, hint: '这条预警已经处置过了，不能再处置一次。' },

  /** **403**。`POST /api/notifications/{id}/read`：那条消息不是发给请求头里这个
   *  学生的（**或它根本不存在** —— 两档刻意同形，理由见 `alerts.py:186-193`：
   *  `notification.id` 是连续代理键，区分两者等于让「扫一遍 id」成为一次有效探测）。
   *  触发点：`alerts.py:444-452`，code 常量在 `alerts.py:193`。 */
  not_recipient: { status: 403, hint: '这条消息不是发给当前这个学生的。' },

  /** **404**。这个教学班在那一周没有班级周报。
   *  触发点：`app/api/routers/dashboard.py:322-330`，code 常量在 `dashboard.py:170`。
   *  ⚠️ `weekly_class_report` **只在周日**的批处理里生成（`report_stage.REPORT_WEEKDAY = 6`）
   *  → 前端要显示「本周周报将在周日生成」，**不要显示成一堆 0**（计划约束第 19 条）。 */
  no_weekly_report: { status: 404, hint: '这个班在那一周还没有周报（周报只在周日的批处理里生成）。' },

  /** **409**。这节课还没发起课堂快评（`rpe_opened` 为假，**或** `rpe_token` 为空）。
   *  两个触发点，**逐字同码**：`app/api/routers/feedback.py:498-508`（教师读口令）
   *  与 `feedback.py:550-557`（学生交快评）。code 常量在 `feedback.py:271`。
   *  ⚠️ 它**必须**排在验口令之前：一节课还没发起时 `rpe_token IS NULL`，
   *  先验口令会把「老师还没发起」报成「你口令错了」，而教师要做的事完全不同。 */
  rpe_not_opened: { status: 409, hint: '教师还没有发起这节课的课堂快评。' },

  /** **403**。学生交的口令与课次上的那一串不匹配。
   *  触发点：`feedback.py:559-564`，code 常量在 `feedback.py:278`。
   *  ⚠️ 口令由教师在课堂上投屏、学生**手输**（计划约束第 15 条）；
   *  ⚠️ **不做过期**。
   *  ⚠️ 「同一节课交第二次」**不是**本 code：它撞 DB 的
   *  `uq_rpe_record_session_student`，由全局 `IntegrityError` 处理器折成
   *  **409 `integrity_conflict`**（`feedback.py:540-545` 的 docstring 逐字交代了
   *  「本函数不自己接」）。计划里那个 `rpe_already_submitted` **不存在**。 */
  invalid_rpe_token: { status: 403, hint: '口令不对。请照着老师投屏上的那一串重新输入。' },

  /** **404**。这个学生在那一天没有生效的处方。
   *  两个触发点：`app/api/routers/prescription.py:290-297`
   *  （`GET /api/students/{id}/prescriptions/current`）与 `prescription.py:234-239`
   *  （`_weekly_sheet_response`，学生侧与教师侧的 weekly-sheet 共用它）。
   *  code 常量在 `prescription.py:145`。
   *  ⚠️ 处方不每天重发，「没有」是常态、不是故障。 */
  no_active_prescription: { status: 404, hint: '这一天没有生效的处方（处方只在五条触发之一成立时才生成）。' },

  /** **404**。有处方，但 `as_of` 落在它的微周期之外。
   *  触发点：`prescription.py:242-250`，code 常量在 `prescription.py:160`。
   *  ⚠️ 与上一档是**两种提示**：那一档是「等下一次批处理」，这一档是「该换处方了」。 */
  outside_microcycle: { status: 404, hint: '那一天不在这张处方的微周期有效期内（通常意味着该换处方了）。' },

  /** **任意未被上面 6 个状态码覆盖的状态码**。`errors.py:142` 的
   *  `_CODE_BY_STATUS.get(status, f"http_{status}")`。
   *  ⚠️ 今天最常见的一档是 **`http_405`**：14 个只读资源根本不注册
   *  POST / PATCH / DELETE，打过去就是 405（计划约束第 20 条）。
   *  它不是一个字面量 code，故 {@link isErrorCode} 用前缀判它。 */
  http_405: { status: 405, hint: '这个资源不允许这个操作（只读资源没有新建/编辑/删除端点）。' },
} as const

/** `ERROR_CODES` 的键。⚠️ 它是 `string` 的一个子集，但**不是**后端 code 的全集：
 *  后端可以回任何 `http_<状态码>`，故 {@link ApiError.code} 的类型是 `string`。 */
export type ErrorCode = keyof typeof ERROR_CODES

/** 一个 code 的元信息（状态码 + 一句给人看的话）。 */
export interface ErrorCodeMeta {
  readonly status: number
  readonly hint: string
}

/** 查一个 code 的元信息；不认识的一律落到 `http_<status>` 那一档。 */
export function describeCode(code: string, status: number): ErrorCodeMeta {
  const known = (ERROR_CODES as Record<string, ErrorCodeMeta | undefined>)[code]
  if (known) return known
  const byStatus = (ERROR_CODES as Record<string, ErrorCodeMeta | undefined>)[`http_${status}`]
  return byStatus ?? { status, hint: `后端回了一个前端不认识的错误码：${code}` }
}

/** 后端统一错误体的形状（`app/api/errors.py:84` 是它在全仓的唯一住址）。 */
export interface ErrorBody {
  error: {
    code: string
    message: string
    detail: unknown
  }
}

/**
 * 所有非 2xx 一律抛它。
 *
 * ⚠️ `code` 的类型是 `string` 而不是 {@link ErrorCode}：后端那句
 * `f"http_{exc.status_code}"` 是**开放的**（加一个新状态码就有一个新 code），
 * 把它收窄成字面量联合等于让「后端加一档」在前端变成一次类型错误 ——
 * 而那一次错误会落在离真因很远的地方。分支时请用 `describeCode`。
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: unknown
  /** 出错的请求（方法 + 完整 URL）。⚠️ 只用于日志与横幅的折叠区，不含请求体。 */
  readonly request: string

  constructor(init: {
    status: number
    code: string
    message: string
    detail: unknown
    request: string
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.detail = init.detail
    this.request = init.request
  }

  /** 这一档的元信息（状态码 + 一句人话）。 */
  get meta(): ErrorCodeMeta {
    return describeCode(this.code, this.status)
  }
}

/** 查询参数的值域。`null` / `undefined` 一律**不拼进查询串**（后端把
 *  「参数没传」与「参数是 null」当两件事，而 `as_of=null` 会被 Pydantic 折成 422）。 */
export type QueryValue = string | number | boolean | null | undefined

/**
 * 查询袋。
 *
 * ⚠️⚠️ **传进来的具体类型必须是 `type` 别名，不能是 `interface`**：
 * TypeScript 只给「对象字面量类型」隐式索引签名，**不给 `interface`**
 * （interface 是开放的，declaration merging 可以随时给它加成员，
 * 故编译器不敢假设它只有已声明的那几个键）。写成
 * `interface PageQuery { limit?: number }` 再传给 `query`，会报
 * `Index signature for type 'string' is missing in type 'PageQuery'`
 * —— 而且它会在**每一个**调用点上各报一次（实测 21 处）。
 * `types.ts` 的 `PageQuery` 因此是 `type`。
 */
export type Query = Record<string, QueryValue>

export interface ApiRequestInit {
  /** 查询参数。`null` / `undefined` 的键会被丢掉。 */
  query?: Query
  /** 请求体。有它就把 `Content-Type` 设成 `application/json`。 */
  body?: unknown
  /** 透传给 `fetch`（用于取消）。 */
  signal?: AbortSignal
  /** 额外的头。**不要**用它传身份（身份由 store 注入，两个住址会打架）。 */
  headers?: Record<string, string>
}

/** 拼查询串。空对象返回空串（不是 `?`）。 */
export function buildQuery(query?: Query): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) continue
    params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

/**
 * 当前**开发期**身份 → 请求头。
 *
 * ⚠️ **`import.meta.env.DEV` 是编译期常量**：生产构建里本函数体整个被摇掉，
 * 于是「生产前端会不会发出一个可伪造的身份头」这一档的答案是**结构上的不会**
 * （后端生产缺省 `PE_ALLOW_HEADER_IDENTITY="0"` 时它本来也会被忽略，
 * 但「不发」比「发了被忽略」强：一个被忽略的头仍然会被 FastAPI **解析**，
 * 而 `X-Student-Id: abc` 那种格式错的头会得到 422 而不是 200 ——
 * 后端 `app/api/deps.py` 的 `current_student` docstring 逐字记了那个坑）。
 *
 * ⚠️ **一次只注入一个头**：身份切换器选的是「我是学生 N」**或**「我是教师 X」，
 * 不是两个都选。两个头都发虽然在今天的后端上无害（每个端点只读自己那一个），
 * 但会让「这一行是谁写的」变成一件要读两个地方才能回答的事
 * （`teacher_overrides.teacher_staff_no` 与 `rpe_record.student_id` 都来自请求头）。
 *
 * ⚠️ 未选身份时返回空对象。**Plan 05A 之后这不是常态而是异常**：真实的身份载体
 * 是 `pe_session` cookie（浏览器自己带），故「没有请求头」在生产上就是正常状态。
 * ⚠️ **本处刻意不写「多少个匿名 GET」**（Plan 04 收尾波改的）：那个数在 Plan 04 的
 * 5 个 Task + 收尾波里变了 4 次，Plan 05A Task 5 又改了一次（48 → 44，
 * 因为 `GET /api/students` 与 `GET /api/teachers` 那 4 个操作改成了要教职身份）。
 * 机器口径有两个住址：`scripts/smoke.mjs` 的**第 12 步**（从 `/openapi.json` 反查，
 * 逐个 (路径, 方法) 看有没有 `security`）与后端
 * `tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes`。
 */
function identityHeaders(): Record<string, string> {
  if (!import.meta.env.DEV) return {}
  const identity = useIdentityStore()
  if (identity.role === 'student' && identity.studentId !== null) {
    return { [STUDENT_HEADER]: String(identity.studentId) }
  }
  if (identity.role === 'teacher' && identity.teacherStaffNo !== null) {
    return { [TEACHER_HEADER]: identity.teacherStaffNo }
  }
  return {}
}

/**
 * 发一个请求。**这是本前端唯一直接调 `fetch` 的地方**（单一所有者）：
 * 「身份头怎么注入」「错误体怎么解析」「204 怎么处理」「会话失效怎么广播」
 * 四件事都只有这一份实现。
 *
 * @typeParam T 2xx 的响应体类型。`204` 的端点请用 `void`（它会 `return undefined`）。
 */
export async function apiRequest<T>(
  method: string,
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}${buildQuery(init.query)}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...identityHeaders(),
    ...init.headers,
  }

  const fetchInit: RequestInit = {
    method,
    headers,
    signal: init.signal,
    // ⚠️ 显式写出同源前提（理由见文件头那一节）。
    credentials: 'same-origin',
  }
  if (init.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    fetchInit.body = JSON.stringify(init.body)
  }

  const res = await fetch(url, fetchInit)

  // ④ 204 / 205 没有 body。`res.json()` 会抛 SyntaxError: Unexpected end of JSON input。
  if (res.status === 204 || res.status === 205) {
    return undefined as T
  }

  if (!res.ok) {
    // ② 统一错误体。⚠️ 解析失败要退化而不是二次抛错：405 那一档 FastAPI 会带
    //    一个 body，但 502/504 这类由反代造的响应可能是 HTML 或空体。
    let code = `http_${res.status}`
    let message = res.statusText || `HTTP ${res.status}`
    let detail: unknown = null
    try {
      const payload = (await res.json()) as Partial<ErrorBody>
      const body = payload?.error
      if (body) {
        code = body.code ?? code
        message = body.message ?? message
        detail = body.detail ?? null
      }
    } catch {
      // 响应体不是 JSON：保留 status 折算出来的 code。
    }
    // ⑤ 会话失效。**两个排除项都是承重的**：
    //    · `/api/auth/*` —— 登录口令错是 401 `invalid_credentials`（不该跳登录页，
    //      我们已经在登录页上了），而 `GET /api/auth/me` 的 401 是
    //      `stores/session.ts` 恢复会话时的**正常答案**（在那里跳转会造出
    //      「守卫问 me → 401 → 跳 /login → 守卫再问 me」的循环）；
    //    · 只认 `unauthenticated` 这一个 code —— 401 `invalid_credentials`
    //      说的是「口令错了」，不是「会话没了」。
    if (code === 'unauthenticated' && !path.startsWith('/api/auth/')) {
      fireSessionExpired({ request: `${method} ${url}`, code })
    }
    throw new ApiError({ status: res.status, code, message, detail, request: `${method} ${url}` })
  }

  return (await res.json()) as T
}
