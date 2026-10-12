# Plan 05A Task 3 + Task 4 + Task 5 实现者报告

> **日期**：2026-10-12 · **分支**：`feature/plan-05a-auth`（**未切分支、未 push、未碰 main**）
> **起点**：`3cdf2dc`（Task 1+2 的报告 commit）· **本波 6 个 commit**：见 §8
> **上游**：`Document/2026-10-12-实施计划05A-真实鉴权与管理员角色.md`（211 行 / 26 431 B）
> **交付**：Task 3（前端登录/绑定/路由守卫）+ Task 4（演示账号 + `smoke.mjs` 17 步 + 全链路联调）+ Task 5（spec 勘误 + 48 个匿名 GET 的重新裁定 + 待清扫）
> **一句话结论**：**后端 1333 passed**（1331 → 1333，+2 条新守卫）、**`app/domain/` 覆盖率 1268/0/376/0/100% 逐字未变**、
> **`smoke.mjs` 17/17 步全绿 / 305 条断言 / 退出码 0**（且是在 `PE_ALLOW_HEADER_IDENTITY=1` **已撤掉**之后跑的）、
> **`npm run build` 退出码 0**、**`check:tokens` 与 `check:dist` 都绿**、**0 个 `@ts-ignore` / `as any`**、
> **后端与前端新增依赖都是 0**、**`backend/data/**` 一个字节没动**、**`pyproject.toml` 一字未改**。
> **顶回 7 处**（§7.4）· **没按派单做的地方 6 处**（§7.3）· **待清扫 12 条开放**（§7.1）

---

## ① 环境与基线复现（含派单 §2 那几处的实测复核）

### 1.1 环境（硬规矩 #73：开工第一件事）

| 项 | 实测 |
|---|---|
| Node | **v24.19.0** |
| npm | **11.17.0** |
| Python | **3.11.1**（无 venv；`C:\Python`） |
| FastAPI / SQLAlchemy / Starlette | **0.141.1 / 2.1.3 / 1.7.0** |
| 分支 / HEAD 起点 | `feature/plan-05a-auth` / **`3cdf2dc`**（工作树干净，除一个 Task 1+2 留下的**未入库**探针 `_verify_t12.py`，见 §7.1 第 15 条） |

⚠️ 派单给的环境清单里**没有 Starlette 的版本**（它写的是「FastAPI 0.141.1 / SQLAlchemy 2.1.3 / Pydantic 2.13.5」），
而派单要求的那条命令会打印 Starlette —— 实测是 **1.7.0**。Pydantic 未在本波被触碰。

### 1.2 ⚠️ 那个跑着旧代码的 uvicorn（派单点名要马上处理的一格）

开工实测：`Get-NetTCPConnection -LocalPort 8000,5173 -State Listen` →
**`127.0.0.1:8000` PID 19068**（Task 1+2 之前起的 uvicorn）+ **`::1:5173` PID 16316**（vite dev）。
`Test-Path backend\pe_demo.db` → **True**（旧 schema 的库）。

处置（逐字按派单）：① `Stop-Process -Id 19068`；② `Remove-Item backend\pe_demo.db`；
③ 重跑 `backend\scripts\demo.ps1 -Port 8000`（它的第一步本来就是删旧演示库）。
⚠️ 本波总共重灌了**两次**演示库（Task 4 一次、Task 5 撤掉过渡开关之后一次），两次的 `[7/7]` 复核逐字相同。
⚠️ 另一个坑：`$env:` 是**终端级**的，而我在同一个终端里手工起过一次带
`PE_ALLOW_HEADER_IDENTITY=1` 的 uvicorn —— 撤掉过渡开关那一次跑 `demo.ps1` 之前
**显式 `Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY`** 并核实 `Test-Path Env:\…` 是 `False`，
否则「撤干净了」这句话会是假的（Task 1+2 的待清扫第 11 条正是这一族）。

### 1.3 ⚠️ 派单 §2 那几处的**逐条实测复核**（派单要求「每一条事实都请你实测复核」）

| 派单说的 | 实测 | 结论 |
|---|---|---|
| §2.2 `login` 的 body 形状「请你实测确认」 | `app/api/schemas/auth.py` 的 `LoginCreate` 逐字是 `kind: str` + `login: str` + `password: SecretStr`（`kind` 有一个 `field_validator` 走 `one_of(…, UserSession.KINDS)`）；实发 `POST /api/auth/login {"kind":"teacher","login":"T0003","password":"…"}` → **200** + `{"kind","id","name","role","student_no","staff_no"}` | ✅ **派单说的对**：是 `kind` + **`login`**（一个字段承载两种登录名），不是 `student_no`/`staff_no` |
| §2.2 出生日期那一列叫 `birth` | `app/db/models/organisation.py:125` 是 `birth: Mapped[dt.date] = mapped_column(Date)`；`StudentBindCreate.birth: dt.date` | ✅ **逐字确认**（Task 1+2 顶回第 2 条成立） |
| §2.2 教师是 `{staff_no, name, password}` | `TeacherBindCreate` = `staff_no: str` + `name: str` + `password: SecretStr`；`teacher` 表实测有 `name` 列 | ✅ |
| §2.4 `PE_ALLOW_HEADER_IDENTITY` **不住在** `app/config.py`，「请你实测它住在哪」 | 住在 **`app/api/deps.py`**：`ALLOW_HEADER_IDENTITY_ENV_VAR = "PE_ALLOW_HEADER_IDENTITY"`（第 167 行）+ `ALLOW_HEADER_IDENTITY_DEFAULT = "0"`（第 176 行）+ `allow_header_identity()`（第 179 行，**在请求时**读环境变量）。`app/config.py` 实测只 `import pathlib`，`__all__` 是 4 个路径/URL/时区常量 | ✅ **派单说的对**（Task 1+2 顶回第 4 条成立） |
| §2.3 cookie 的 **8 个参数** | `sessions.cookie_kwargs()` 实测**返回 7 个键**：`key` / `value` / `max_age`(7200) / `path`("/") / `httponly`(True) / `secure`(False，仅 `PE_ENV=production` 为 True) / `samesite`(**小写 `"lax"``**)；**`domain` 是刻意不传的第 8 格**（不是一个值为 `None` 的参数）。实发取证：`pe_session=<64 字符>; HttpOnly; Max-Age=7200; Path=/; SameSite=lax`；登出：`pe_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Max-Age=0; Path=/; SameSite=lax` | ⚠️ **顶回 7**（措辞）：是「**7 个键 + 1 个刻意不传**」，不是「8 个参数」。⚠️ 而 `SameSite` 的**值是小写**，故断言一律按小写（`smoke.mjs` 第 16 步的 ⑦ 那几拍）；写成 `Lax` 会让「有人把它改成大写」这一档静默通过 |
| §2.1 五个端点与每一档 code | `smoke.mjs` **第 16 步的 63 条断言**逐个实测通过（含 204/403/401/409/422 的每一档、`me` 与 `login` **逐字同形**、跨 kind **403**、登出后旧 cookie **401**、subject 被删后没登出过的 cookie 也 **401**） | ✅ |
| §2.4 管理台 26 个写入操作只认管理员（匿名 401 / 普通教师 403 / 管理员 201） | `smoke.mjs` 第 2 步（`class-sessions`）与第 10 步（`semesters` / `teachers`）各三拍实测通过 | ✅ |
| §2.4 管理员越过任教范围闸门 | 第 7 步新增一拍：先**现算**出 `T0003` 本学期**不**教学生 4（`course_section.teacher_id ⋈ enrollment`），再断 `GET /api/teacher/students/4/home` 以管理员会话 → **200** 且是 9 键的 `/home` 形状 | ✅（⚠️ 若不先算「他确实不带这个班」，这一拍什么也没证明） |
| 后端基线 1331 passed / 26 张表 / 扫描面 66 / 71 路径 / 99 操作 / 48 security / 60 GET（48 匿名 + 12 挂 security）/ 3 格 schemes / `_MODELS_PUBLIC_BASELINE` 33 | 开工复核：**1331 passed**、表 **26**、扫描面 **66**（pipeline 10 + db 12 + domain 18 + api 23 + auth 3）、**71 / 99 / 48 / 60（48 匿名 + 12 挂 security）**、schemes **3 格**、`models.__all__` **14** | ✅ 逐格对上 |
| 前端基线 13 条路由 / smoke 16 步 199 断言 / build 119 modules（CSS 65.78 / JS 148.15）/ `src/` 42 文件 | 开工复核：路由 **13 条业务路由**（+ `/`、`/s`、`/t`、catch-all 四条非页面）、`smoke.mjs` **1205 行 / 71 780 B**、`src/` **42 文件** | ✅ |

### 1.4 本波**收尾**的同一批口径（对照 §1.3 的开工值）

| 量 | 开工 | 收尾 | 变了吗 |
|---|---|---|---|
| 后端 passed | 1331 | **1333** | +2（本波新加的两条守卫） |
| 带 `--cov` | 1330 + 1 skipped | **1332 + 1 skipped** | 同步 +2 |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | **逐字未变** |
| 表数 | 26 | **26** | 未变 |
| 扫描面 | 66 | **66** | 未变（本波没加后端模块文件） |
| `/api/` 路径模板 / 操作 | 71 / 99 | **71 / 99** | 未变 |
| 挂 `security` 的操作 | 48 | **52** | **+4**（Task 5：4 个名册读） |
| GET / 匿名 GET | 60 / 48 | **60 / 44** | 匿名 **−4** |
| `securitySchemes` | 3 格 | **3 格** | 未变 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | 未变 |
| 前端路由 | 13 条业务路由 | **15 条**（+ `/login` + `/bind`；`/` 从 `redirect` 改成 `meta.root` 的真路由） | +2 |
| `smoke.mjs` | 16 步 / 199 断言 | **17 步（0–16）/ 305 断言 / 退出码 0** | +1 步 / +106 断言 |
| `npm run build` | 119 modules / CSS 65.78 / JS 148.15 | **129 modules / CSS 70.22 kB（gzip 10.86）/ JS 166.88 kB（gzip 58.35）** | +10 modules |
| `src/` 文件数 | 42 | **48**（+6：`api/auth.ts`、`api/expiry.ts`、`stores/session.ts`、`dev/identity-url.ts`、`views/auth/{Login,Bind}.vue`） | +6 |
| `frontend/scripts/` | 2 | **3**（+ `check-dist.mjs`） | +1 |

---

## ② Task 3：前端登录 / 绑定 / 路由守卫

### 2.1 交付的文件

**新建（6）**：`src/api/auth.ts`、`src/api/expiry.ts`、`src/stores/session.ts`、
`src/dev/identity-url.ts`、`src/views/auth/Login.vue`、`src/views/auth/Bind.vue`
**修改（10）**：`src/api/client.ts`、`src/router/index.ts`、`src/main.ts`、`src/App.vue`、
`src/stores/identity.ts`、`src/components/IdentitySwitcher.vue`、`src/components/ApiErrorBanner.vue`、
`src/views/admin/{ResourceList,ResourceDetail}.vue`、`package.json`
**新守卫（1）**：`frontend/scripts/check-dist.mjs`（`npm run check:dist`）

### 2.2 ⚠️ `session.ts` 与 `identity.ts` **分开**（派单要求在报告里说明理由）

三条理由，每条都对应一个真实的失效形态：

1. **权威性不同**。会话的唯一真相是后端 `user_session` 表 + 那个 `HttpOnly` cookie，
   故 `session.ts` 里的东西是一份**缓存**，刷新方式是「问一次 `GET /api/auth/me`」；
   而 `identity.ts` 的 `asOf`（业务日）是**纯本地偏好**、没有服务端对应物、刷新之后必须从
   `localStorage` 读回来（否则演示会退回「今天」而查不到任何数据）。
   ⚠️ 把一份「缓存」与一份「偏好」塞进同一个持久化快照，失效形态是
   「换了一个人登录而 `asOf` 被冲掉」或反过来「登出了而身份还在」。
2. **生命周期不同**。会话在 401 / 登出 / 吊销时**必须**清空；`asOf` 在这三种情况下都**不该**动
   （`identity.ts` 的 `clearIdentity()` 逐字写着「不清 `asOf`」）。
3. **`role` 是三值、不是两值**。`IdentityRole` 是 `'student' | 'teacher'`（它服务那两个请求头，
   而请求头里没有 role 这一格）；会话的 `role` 是 `'student' | 'teacher' | 'admin'`，
   而**路由守卫的三档全依赖它**。把 `admin` 加进 `IdentityRole` 会让 `client.ts` 的
   `identityHeaders()` 多出一个它无法表达的状态（没有「管理员请求头」这种东西）。

⚠️ **一座单向兼容桥（派单没料到的一格，如实记）**：Plan 04 的 **13 个业务页面全部**从
`identity.studentId` / `identity.teacherStaffNo` 读「我是谁」（既用它拼 URL 里的 `{id}`，
也用 `v-if="identity.studentId === null"` 决定渲不渲染空态）。逐个改 13 个页面会把
「加一个登录页」变成「动 13 个页面的取数逻辑」—— 而那正是 **Plan 05B（视觉重构）要再动一遍的
同一批文件**，两波改动叠在一起会让「哪一次改坏了」无从判断。故 `session.adopt()` **单向回写**
`identity.ts`（`forget()` 也单向清它），13 个页面**一行都没改**。
⚠️ 方向是单向的：反过来（identity → session）不成立，因为 identity 里那份可以被 DEV 切换器随手改，
而会话只有后端能改。⚠️ 代价：那份镜像会进 `localStorage`（`identity.ts` 是持久化的）。
**已登记为待清扫**（§7.1 第 14 条：Plan 05B 应当把 13 个页面改成直接读 `session`，然后拆掉这座桥）。

### 2.3 ⚠️⚠️ 「刷新页面之后怎么恢复会话」的做法（派单点名要说清的一格）

cookie 是 `HttpOnly` 的（`cookie_kwargs` 的 `httponly=True`），故 **JS 读不到它** ——
`document.cookie` 里没有 `pe_session`，「靠读 cookie 判断我登录了没」这条路**结构上不存在**。
也**不把它抄进 `localStorage`**：那会造出第二个真相（浏览器里的 cookie 还在而 `localStorage` 被清了，
或反过来），两者不一致时的表现是「页面认为登录了、每一个请求都 401」。

故恢复会话只有**一条**路：**首次导航时打一次 `GET /api/auth/me`**。

* 住址：`stores/session.ts` 的 `ensureRestored()`；`router/index.ts` 的 `beforeEach` 在**每一次**导航上调它。
* **只发一次**：模块级 `restoring`（合并并发的）+ `asked`（合并串行的）。少了 `asked`，
  一个未登录的用户点 15 条路由就是 15 次 `me`。
* ⚠️ `status` 的**初值是 `'unknown'` 而不是 `'anon'`**：那两档在守卫里必须分开，
  否则守卫会在 `me` 回来之前就把一个已登录的用户弹去 `/login`（闪一下再跳回来）。
* ⚠️ **401 不抛**（它是「没登录」这个正常答案），**其余错误抛**：后端没起 / 代理没通时
  把用户弹去登录页是一句假话。那一档 `status` 退回 `'unknown'`、`asked` 退回 `false`
  （下一次导航再试一次），守卫**放行**，让页面自己的错误横幅说真因。
* ⚠️ `client.ts` 认出 401 `unauthenticated` 之后**广播**一次（`api/expiry.ts`），
  装配点（`main.ts`）据此清会话 + 跳 `/login?next=<原路径>`。
  **排除 `/api/auth/*`**：`me` 的 401 是恢复会话的正常答案，在那里跳转会造出
  「守卫问 me → 401 → 跳 /login → 守卫再问 me」的循环；`login` 的 401 是 `invalid_credentials`
  （口令错），不是会话没了，故判据是 **`code === 'unauthenticated'`** 而不是 `status === 401`。

### 2.4 登录页 / 绑定页的字段与错误档

**`/login`**（`views/auth/Login.vue`）
* 两档身份（**学生 / 教师**，⚠️ 管理员不单列 —— 它就是一行 `role='admin'` 的 `teacher`）；
  登录名字段是**一个** `login`（标签随档位换成「学号」/「工号」），与后端 `LoginCreate` 逐字对应。
* 登录后按 `role` 跳：学生 → `/s/home`、教师 → `/t/dashboard`、管理员 → `/admin`
  （住址是 `session.homePath` getter，**不写第二份**）。
* 三档错误按 **`code`** 分支（`api/auth.ts` 的 `authAdvice`）：`password_not_bound` → 一句人话 +
  「去绑定」的入口（并把 `kind` 与刚输的登录名带过去）；`invalid_credentials` → 停在原页 +
  **清空口令框**（不清的话浏览器自动填充会把一个已知错的串填回来）；`request_validation_failed` →
  明说「这一档通常是前端的 bug」。
* ⚠️ **`?next=` 做了开放重定向校验**（派单没点，实现者补的一格）：只接受「以单个 `/` 开头、
  且第二个字符不是 `/` 或 `\`」的串。`/login?next=https://evil.example` 与
  `/login?next=//evil.example`（协议相对 URL）都会被退回 `homePath`。
* 「首次使用？去绑定口令」的入口在（`RouterLink` → `/bind?kind=…&login=…`）。

**`/bind`**（`views/auth/Bind.vue`）
* 学生：学号 + **出生日期**（`<input type="date">` → `YYYY-MM-DD`，与 `birth: dt.date` 对上）；
  教师：工号 + 姓名。两档都是 新口令 + 确认。
* **前端拦两道、后端是唯一权威**：① 弱口令 < 8（`MIN_PASSWORD_LENGTH` 是后端那个常量的**镜像**，
  两处不一致时以后端为准）；② **两次输入不一致**（⚠️ 后端不管这一格 —— 它的请求体里只有一个
  `password`，「确认口令」纯粹是 UI 概念；不拦的话「打错了确认框」会静默地把第一格设成口令）。
* 四档错误：`unprocessable_value`（弱口令）/ `forbidden`（不在册**或**验身材料不符，后端刻意同形，
  故本页把后端那句 message 原样显示）/ **`password_already_bound` → 说人话**
  （「这个学号已经绑定过口令了：一个账号只能绑定一次，请直接登录」+ 去登录的入口 +
  「忘了口令要找教务干事把 `password_hash` 置回 NULL」）/ `request_validation_failed`。
* ⚠️ **204 之后自己再登录一次**（后端刻意不自动登录），然后按 `role` 跳首页；
  那一次登录若失败，**不静默**：把用户送去 `/login` 并带上刚输的登录名 + 一句
  「口令已经绑定成功了，而随后那一次自动登录没有成功」。
* ⚠️ 单选按钮用 **`:checked` + `@change`，不是 `v-model`**：`v-model` 会先改掉 `kind`、再触发 `change`，
  于是 `pickKind` 里「同一个档位就直接返回」那一支恒成立，「换档位要清掉上一档的输入」静默失效
  （实现者第一版就写成了 `v-model`，读代码时抓出来）。

⚠️ **两页一律用现有的 `tokens.css` 类与令牌**（`.card` / `.field` / `.field__label` / `.input` /
`.btn` / `.btn--primary` / `.btn--ghost` / `.pill` / `.caps` / `.zh-title` / `.data` / `LaneDivider`），
`<style scoped>` 里**一个色值字面量都没有**（`npm run check:tokens` 绿），
故 Plan 05B 换肤时它们跟着 `tokens.css` 一起变、**不必重做两遍**。

### 2.5 `client.ts` 的 `credentials` 与那条注释

* `fetchInit` 里显式写了 **`credentials: 'same-origin'`**。
* ⚠️ **文件头那一整段「不设 `credentials`」的注释已改写**（它引用的是 Plan 04 Global Constraints 第 1 条）：
  保留了「`'include'` 与 `allow_origins=["*"]` 并存会让所有跨域请求当场失败」那一段论证
  （它对 `'include'` 仍然成立），并写明**它对 `'same-origin'` 不成立**（Vite 代理让浏览器看到同源，
  同源请求根本不走 CORS）。⚠️ 也写清了「显式写出来」的意义：它把「本前端假定同源部署」这个前提
  **写进了代码**，于是若部署方把 `VITE_API_BASE` 指到跨源地址，`credentials` 的语义会立刻从
  「带上」变成「不带」（会话静默失效、每个端点 401），而那一格正是排查时第一个要看的地方。
* ⚠️ **CORS 一行都没动**（计划 §2.2 的更正成立：同源部署不触发那一档）。
* 跨源部署要改的**五件事**逐字写进了 spec §13.4.5（含「§1.2 第 5 条那条 CSRF 论证在 ①② 落地后当场失效」）。
* ⚠️ **身份头注入降级成 DEV-only**（`if (!import.meta.env.DEV) return {}`）：派单没点这一格，
  实现者补的。理由是「不发」比「发了被忽略」强 —— 一个被忽略的头**仍然会被 FastAPI 解析**，
  而 `X-Student-Id: abc` 那种格式错的头会得到 **422** 而不是 200（后端 `current_student` 的
  docstring 逐字记了那个坑，Task 1+2 的关切第 5 条）。

### 2.6 路由守卫的三档（**实测**，不是读代码）

`router/index.ts` 的 `beforeEach`。`meta.requires` 的取值域从 `'student' | 'teacher' | 'none'`
改成 **`'student' | 'staff' | 'admin' | 'none'`**（类型是 `stores/session.ts` 的 `RouteRequirement`，
两处**同一个类型**，故不可能对同一档给出两个答案）：

| 前缀 | `requires` | 判据（`session.satisfies`） |
|---|---|---|
| `/s/*`（6 条） | `student` | `kind === 'student'` |
| `/t/*`（4 条） | **`staff`** | `kind === 'teacher'`（`role` 是 `teacher` **或** `admin`） |
| `/admin/*`（3 条） | **`admin`** | `kind === 'teacher' && role === 'admin'` |
| `/login`、`/bind` | `none` + `public` | 谁都能看；⚠️ **已登录还去登录页 → 弹回自己的首页** |
| `/`（`meta.root`） | — | 送去**他自己那个角色**的首页；未登录 → `/login` |

⚠️ `teacher` → **`staff`** 是承重的：管理员也是一行 `teacher`，而计划 §3.6 第 2 条 + §4.2 逐字裁定
「`admin` 访问 `/t/*` 是允许的」，旧名字会把管理员排除在外。
⚠️ `/admin/*` 三条从**缺省 `none`** 改成字面的 `admin`（Plan 04 那时「管理台的读全部匿名」，
Task 2 之后 26 个写入仅管理员、Task 5 之后两个名册读要教职身份，故整棵树要 `admin`）。
⚠️ `/` 从 `redirect: '/s/home'` 改成一条真路由 + `meta.root`：`redirect` 的函数形式在**守卫之前**求值，
而那一刻会话还没恢复（恢复要一次异步的 `me`），故它只能给出一个错的答案。

**三种落空各有一个明确的去处**（计划 §4.2「不要只显示空白」）：
① 没登录 → `/login?next=<原路径>`；② 角色不符 → 跳**自己的**首页 + 把一句说明写进
`session.notice`（由 `IdentitySwitcher` 的会话条渲染）；③ 后端不可达 → **放行**（见 §2.3 末条）。

**实测取证**（`smoke.mjs` 第 14 步，CDP + 无头浏览器）：
* 「未登录访问 `/s/home` → `location` 是 `/login?next=/s/home`」✅（且登录页**真的渲染出来了**，不是白屏）；
* **三种角色各跳到自己的首页** ✅：15 条路由逐条按 `jar` 种 cookie 后导航，
  学生 6 条以 `student:4` 的 cookie 落在 `/s/*`、教师 4 条以 `teacher`(T0001) 落在 `/t/*`、
  管理台 3 条以 `admin`(T0003) 落在 `/admin/*`，**并逐条断言「没有被弹到 `/login`」**
  （反假绿：一条业务路由若被弹走，它的关键内容一定全缺，而「弹到登录页」与「页面渲染坏了」是两种真因）；
* 「管理员也是 `staff`」✅：`admin` cookie 打开 `/t/*` 与 `/admin/*` 都渲染成功（第 14 步的
  `admin-index` / `admin-list` / `admin-detail` 三条），且 `admin-list` 的关键内容里含
  `＋ 新建一行`、`admin-detail` 含 `✎ 编辑` —— 那两个按钮的可见性判据已从
  `identity.canWriteAsTeacher` 抬成 **`session.isAdmin`**（Plan 05A Task 2 之后管理台仅管理员）。

### 2.7 `adoptFromUrl()` 的降级与那条守卫

* **搬出 store**：`stores/identity.ts` 的 action → **`src/dev/identity-url.ts` 的一个函数**。
  ⚠️ 搬走的理由不是整理，而是一条可执行的性质：**生产构建里它必须不存在**，
  而一个 store 的 action **结构上做不到**（store 本体一定在产物里）。
  独立模块 + `main.ts` 里那一个 `if (import.meta.env.DEV) { … }`，才能让 Rollup
  ① 删掉那个 `if` 块 ② 发现该模块的导出再无使用者 ③ 把整个模块从产物里摇掉。
* ⚠️ 那个模块对 store 只有 `import type`（编译期擦掉），故它对 store **没有运行时依赖**。
* **守卫**：`frontend/scripts/check-dist.mjs`（`npm run check:dist`），**机器可跑**：
  1. `dist/` 不存在（或给了 `--build`）时**自己跑一次 `npm run build`** 并断言退出码 0；
  2. 递归扫 `dist/` 下 `.js/.mjs/.cjs/.css/.html/.svg/.json/**.map**` 共 **21 个文件 / 478.8 kB**，
     断言 `adoptFromUrl` 出现 **0** 次（⚠️ 含 `.map`：一个 sourcemap 里留着它等于把那段代码原文
     交给了任何拿到产物的人）；
  3. ⚠️ **反空转（硬规矩 #50）**：**反向**断言它在 `src/dev/identity-url.ts`（实测 **3** 处）与
     `src/main.ts`（实测 **4** 处）里**确实存在** —— 源里有、产物里没有，才叫「被摇掉了」；
     并断言扫到的文件数 ≥ 3、总字节 ≥ 100 kB（否则「0 次」可能只是路径指错了）。
* **实测**：`npm run check:dist` 退出码 **0**，输出 `✓ dist/ 里 adoptFromUrl 出现 0 次（它必须被 Rollup 摇掉）  →  0 次`。
* ⚠️ 它也被挂进了 `smoke.mjs` 的**第 15 步**（与 `check-tokens.mjs` 并排 + 各自的反空转拍），
  故「`npm run smoke` 全绿」**蕴含**「设计令牌没有散开」与「开发工具没有漏进生产」两件事。
* ⚠️ `IdentitySwitcher.vue` 里那个 DEV-only 的切换器同样受 `import.meta.env.DEV` 约束；
  而 `smoke.mjs` 第 14 步**一个 `?student=` / `?teacher=` 都不再用**（改由 CDP 的
  `Network.setCookie` 种 cookie），故「取证依赖那条深链接」这件事已经**不存在** ——
  那正是计划 §2.4「05A 必须先于 05B」要的那个结果。

### 2.8 `IdentitySwitcher.vue` → 「当前身份 + 登出」

**两半**：① **会话条（永远渲染）** = role pill（`STUDENT` / `TEACHER` / **`ADMIN`** / `ANONYMOUS`）
+ `session.summary` + **登出按钮** + `session.notice`（守卫弹回来 / 会话过期 / 登出之后写下的那一句）；
② **切换器（仅 `import.meta.env.DEV`）** = 原来那两个下拉框（派单逐字允许「开发模式下额外保留切换能力」）。
⚠️ **`as_of` 的输入留在这个组件里**（它此前就住在这里，且是全站唯一能改业务日的入口；
业务日是演示口径的一部分、与「我是谁」无关，故登出**不清**它）。
⚠️ **登出「一定成功」**（即使后端那一次失败）：`POST /api/auth/logout` 在**没有会话**时回 401，
而那时用户想做的事正是「回到未登录状态」；把 401 抛回去会让登出按钮在会话已过期之后**点不动**。
代价如实记：cookie 是 HttpOnly 的、前端清不掉它，故服务端那一次失败时浏览器里还留着一个 cookie ——
但服务端那一行会在 `SESSION_TTL`（2 h）之后自己过期，而 UI 已经与现实一致。
⚠️ DEV 那一半的名单加载**只在 `session.isStaff` 时**发（Task 5 之后名册要教职身份；
一个学生会话在这里只会拿到 403，而那一条 403 会把横幅占满、把真因盖掉）。
⚠️ `App.vue`：`identityHint` **退场**（守卫会拦住身份不符的导航，故「页面已经渲染出来了、
而身份不够」这一档不再存在，那条 `.identity-hint` CSS 也一并删掉）；导航按
`session.satisfies` **过滤**（与守卫**同一个函数**，故「画出来的入口」与「点了不会被弹回来的入口」
恒为同一批）+ 未登录时整个 `<nav>` 不画；colophon 从「不做真实登录」改成「已做真实鉴权 + 已知局限」。

### 2.9 Task 3 的验收（逐条）

| 验收项 | 结果 |
|---|---|
| `npm run build` 退出码 0 | ✅ **0**（129 modules；主 chunk CSS **70.22 kB** / JS **166.88 kB**） |
| 0 个 `@ts-ignore` / `as any` | ✅ **0**（`rg '@ts-ignore|@ts-expect-error|as any' frontend/src` 无命中） |
| `npm run check:tokens` 绿 | ✅ 绿（扫描面 **33** 个文件，下界 25；`tokens.css` 之外一个色值字面量都没有） |
| 未登录访问 `/s/home` 会跳 `/login?next=/s/home` | ✅ 无头浏览器实测（§2.6） |
| 三种角色各跳到自己的首页 | ✅ 15 条路由逐条实测（§2.6） |
| `dist/` 里 grep 不到 `adoptFromUrl` | ✅ **0 次 / 21 个文件 / 478.8 kB**，且源码里 3 + 4 次（反空转） |

---

## ③ Task 4：演示账号 + `smoke.mjs` 改造 + 全链路联调

### 3.1 演示口令与管理员

| 项 | 值 | 住址（唯一所有者） |
|---|---|---|
| **演示口令** | **`pe-demo-2025`**（12 字符 > `MIN_PASSWORD_LENGTH` 8） | `backend/scripts/demo_bootstrap.py` 的 **`DEMO_PASSWORD`** |
| **管理员** | **`T0003` 赵志刚**（`role='admin'`） | 同文件的 **`DEMO_ADMIN_STAFF_NO`** |
| 教师（普通） | `T0001` 陈国华 / `T0002` 林慧敏（`role='teacher'`） | `app/seed/sections.py` 的 `TEACHER_NAMES` |
| 学生 | **60 个全部绑定**（同一个口令） | `[6/7]` 那一步 |
| `PBKDF2_ITERATIONS`（演示脚本内） | **100 000** | 同文件的 **`DEMO_PBKDF2_ITERATIONS`**（+ `--pbkdf2-iterations` 可覆盖） |

⚠️ **口令不用 `12345678` 这类**（派单逐字要求）：它能过后端的弱口令检查（只判长度 ≥ 8、不判复杂度），
但演示口令会被人抄去试别的系统，而 `12345678` 是撞库字典的第一行。
`pe-demo-2025` 的三格各有出处：`pe` = Physical Education（仓库目录名 `Physical_Education_ims`）、
`demo` 说明它是演示值、`2025` 是演示库那个学年。

⚠️⚠️ **管理员不是派单举例的 `T0001`，而是 `T0003`**（**顶回 3**）。理由是一条实测出来的冲突：
`T0001` 是 `smoke.mjs` 全程用来验**任教范围闸门**的那个普通教师，而管理员会**越过**那道闸门
（计划 §3.6 第 2 条）。把 `T0001` 提成管理员会让第 7 步的两拍**由 403 变成 200**：
「学生 4 不在 T0001 本学期任教的班里 → 403」与「教师侧 `/home` 对不任教的学生 → 403」。
那两拍钉的是**闸门本身**、不是「T0001 这个人」，故正确姿势是：让 smoke 继续用一个
`role='teacher'` 的工号验闸门、另用一个 `role='admin'` 的工号验管理台。
⚠️ 取 `T0003` 而不是 `T0002`：`make_sections` 按 `teachers[index % len(teachers)]` 轮转发班，
而 smoke 第 2 步取的是 `GET /api/course-sections?limit=5` 的**第一行**（= 行政班01 = T0001 的班）、
第 8 步的大屏也读它 —— 故 `T0001` 必须**继续带班**且保持 `role='teacher'`；
`T0003` 带不带班对 smoke 都不重要（它只被用来做管理台的写入）。
⚠️ 而「T0003 确实不带学生 4 的班」在第 7 步是**现算**出来的（`course_section.teacher_id ⋈ enrollment`），
不是假设 —— 少了那一拍，「T0003 恰好也带这个班」会让「管理员越过闸门 → 200」变成一条什么也没证明的绿。

⚠️ **`demo.ps1` 刻意不抄第二份口令字面量**：它只打印「去哪一行找它」。
抄一份到 shell 里的话，改口令的人会漏改一处，而漏改的那一处正是**演示时要念给人听**的那一处。

### 3.2 `PBKDF2_ITERATIONS` 在演示脚本里的值与理由

**值 = 100 000**（控制者裁定），**生产缺省 600 000 一个字没变**
（`app/auth/passwords.py` 的 `PBKDF2_DEFAULT_ITERATIONS`；那条「生产缺省 ≥ 600 000」的守卫读的是常量本身）。

⚠️ **实现者复核后同意这个值，但把理由换成更硬的一条**（**顶回 6**）：
控制者给的理由是「60 人 × 600 000 会很慢（约 18 秒）」—— 那是**成本**论证，
而下一个人完全可以说「18 秒吃得下，安全优先」。真正硬的理由是**收益为零**：
迭代次数保护的是**泄漏的哈希**不被离线爆破，而演示库的口令是**明文公开**的
（`[6/7]` 的 stdout + `demo.ps1` 的打印 + spec §13 + 登录页的提示），
故这里**没有任何东西需要保护**；600 000 只会让 `demo.ps1` 慢约 16 秒而换不到一点安全。
⚠️ 实测口径：63 个账号 × 600 000 ≈ 19 s，而 `demo.ps1` 的 `elapsed` 哨兵阈值是 90 s、
Plan 03 实测 43.96 / 48.37 s（余量 1.86×）→ 加上 19 s 余量掉到 1.34×；100 000 则约 3 s。
⚠️ **自描述串让两种迭代次数在同一个库里并存且都能校验**：`hash_password` 把迭代次数写进串里，
`verify_password` **先解析出那个数、再用它重算**。而 uvicorn 那个进程**不设**本变量
（`demo.ps1` 里没有它），故演示时经 `/api/auth/*/bind` 新绑的口令用的是**生产缺省 600 000**
—— `smoke.mjs` 第 16 步就是这么绑的，且登录成功，故这一格是**被真的验证过**的。
⚠️ 派单说「若你有更好的办法（例如只给少数几个账号绑密码），顶回来」：**没有**。
只给少数账号绑会让「随手挑一个学号登录」大概率失败，而那看起来像口令错了
（`[7/7]` 的 offenders 因此用**相等**而不是 `> 0` 当判据）。

### 3.3 `demo_bootstrap.py` 的改动（⚠️ 只改了派单允许的两个后端脚本之一）

* 新增 `[6/7]` 一步（原 `[6/6]` 复核顺延成 `[7/7]`，5 个 label 一并改）：
  绑 60 个学生 + 3 个教师的口令、把 `T0003` 的 `role` 置成 `admin`、**打印**口令与管理员。
* ⚠️ **哈希一律走 `app.auth.passwords.hash_password`**（单一所有者），**不自己算**：
  一份手写的 `hashlib.pbkdf2_hmac(...)` 会在「换算式」那一天静默地与 `verify_password` 漂开。
* ⚠️ 迭代次数经**环境变量**注入（`iterations()` 在**调用时**读它），故只影响这一个进程。
* ⚠️ `role` 的字面值 **`DEMO_ADMIN_ROLE = "admin"` 是写死的**、不 import `app.api.deps.ADMIN_ROLE`：
  `tests/architecture/test_layering.py` 是 AST 扫 `backend/` 下**全部** `.py` 的
  （含 `scripts/`，实测 140 个文件），为一个字面值去新加一条 `scripts → app.api` 的边不值。
  ⚠️ 而「写死」的风险由一道**显式词表断言**顶住：`DEMO_ADMIN_ROLE not in Teacher.ROLES` 就
  `SystemExit`（否则 DB 的 `ck_teacher_role` 会把它挡成一句 SQLite 原文的 `IntegrityError`，
  报错在离真因很远的一格上）。
* `[7/7]` 的 `offenders` 加两格：「口令绑全了」（**相等**判据，理由见 §3.2 末）与「至少一个管理员」。
* ⚠️ **修了一个实测撞出来的 bug**：`commit()` 会 expire 全部 ORM 实例、`with Session(...)` 一退出就
  detached，故要打印的那几格必须在 commit **之前**摘成普通值 —— 第一次跑 `demo.ps1` 就炸在
  一行 `print` 的 f-string 里（`DetachedInstanceError`），离真因「ORM 实例的生命周期」隔了两层。
* ⚠️ **行尾与 BOM 复核**：`demo_bootstrap.py` 是 **CRLF / 无 BOM**（改前 26 965 B / 432 CRLF；
  改后 **39 933 B / 611 CRLF / 无 BOM**），全程用 SearchReplace + python，`python -m py_compile` 绿。

### 3.4 ⚠️ `demo.ps1` 的 BOM 事故（实测撞到、已修，如实记）

`demo.ps1` 是 **UTF-8 带 BOM + CRLF**（派单逐字警告过：PowerShell 5.1 会把无 BOM 的中文 `.ps1`
按 ANSI **静默乱码**）。**IDE 的 SearchReplace 工具在写回时把 BOM 吃掉了** ——
改完实测 `bom=False`。已用 python 把 `\xef\xbb\xbf` 补回去并复核：
**14 752 B / 223 CRLF / `bom=True` / sha256[:16] `6D2D0EB00D0B13DF`**。
⚠️ 这是派单点名的那一族事故的**第二次**发生（fix 波 1 是第一次），故登记为待清扫
（§7.1 第 20 条：**改 `demo.ps1` 之后一律用 `read_bytes()` 复核 BOM**，
或干脆全程用 python 改它）。

### 3.5 `smoke.mjs` 的 17 步逐步结果（**实测**，退出码 0）

| 步 | 标题（截断） | 断言 | 结果 |
|---|---|---|---|
| 00 | 登录三种角色 + 演示库复原核实 | 23/23 | 绿 |
| 01 | `GET /api/health` → tables == **26** 且 students > 0 | 5/5 | 绿 |
| 02 | **管理员** POST `/api/class-sessions` → 201 且无 `rpe_token`；**普通教师 → 403** | 10/10 | 绿 |
| 03 | 教师 `open-rpe` 拿到口令；匿名 list 的响应体原文里不含那串口令 | 9/9 | 绿 |
| 04 | 匿名读口令 → 401；教师读 → 200 且与第 3 步逐字相同 | 7/7 | 绿 |
| 05 | 学生 POST `/api/rpe-records` → 201；再交 → 409 `integrity_conflict` | 9/9 | 绿 |
| 06 | 学生 POST `/api/training-logs` → 201 且四格服务端填 | 10/10 | 绿 |
| 07 | weekly-sheet / home 的两侧变体 + 越权 + **管理员越过任教闸门** | 41/41 | 绿 |
| 08 | 教师 dashboard：三层完成率不是全 0、`progress_board` 非空 | 14/14 | 绿 |
| 09 | 预警处置三档 + 非法 action 422 且点名合法值 | 13/13 | 绿 |
| 10 | 写入侧：匿名 401 / **普通教师 403** / **管理员 201**；DELETE 是 405 | 17/17 | 绿 |
| 11 | 只读资源被写 → 405 `http_405` | 6/6 | 绿 |
| 12 | 从 `/openapi.json` 反查 `catalog/resources.ts` 的 23 行（5 拍） | 22/22 | 绿 |
| 13 | `/api/students/{id}/notifications` 与 `/api/mini-tests/normalized` | 15/15 | 绿 |
| 14 | **15 条路由**的无头浏览器 DOM 取证（**CDP + cookie**） | 33/33 | 绿 |
| 15 | 两个构建守卫：`check:tokens` + `check:dist` | 8/8 | 绿 |
| **16** | **鉴权全链路**（派单点名的「第 17 步」） | **63/63** | 绿 |
| | **合计** | **305 绿 / 0 红** | **17/17 步全绿 · 退出码 0** |

⚠️ **步数编号的裁定**（**顶回 5**）：派单同时写「**17 步全绿**」与「**新增第 17 步**」。
取 **1-based** 读法 → 步号 **0–16** 共 **17** 步，「第 17 步」= index **16**（鉴权全链路）。
⚠️ 于是 `check-dist` 那一格**折进了第 15 步**（与 `check-tokens` 并排成「两个构建守卫」）
而不是新开一步 —— 否则会变成 18 步，与「17 步全绿」冲突。派单自己给的两个可选住址
（「放进 `smoke.mjs` 或 `check-tokens.mjs` 旁边一个新 script」）**两个都做了**：
新 script `check-dist.mjs` + `smoke.mjs` 第 15 步 `spawn` 它一次。

### 3.6 ⚠️ cookie jar 怎么维护的（**顶回 1：不引 `undici` 的 `CookieJar`**）

Node 的 `fetch`（undici）**默认不存 cookie**。派单允许「或用 `undici` 的 `CookieJar`，
⚠️ 那是新依赖，若能用几十行自己维护就别引」——**实现者选择自己维护**：

* `JARS: Map<string, string>`（身份名 → `pe_session=…` 那一份 `Cookie` 头原文）。
* `loginJar(name)`：按名字查 `STAFF_JARS`（`teacher` → T0001 / `admin` → T0003），
  或从 `student:<id>` 里解出代理键、经 `studentNoOf(id)` 查一次名册换成**学号**，
  再打 `POST /api/auth/login`，从响应头取出 cookie 存进 jar。
* `ensureJar(name)`：**懒登录**（缺就先登），故 16 个步骤里每一步只写 `as: 'teacher'`，
  「谁先登录」由第一次用到它的那一步决定，不必在开头排一个登录顺序。
* `req(method, path, {as, cookie, …})`：`as` → 从 jar 取 cookie；`cookie` → **绕过 jar**
  直接给一份原文（⚠️ 只给第 16 步用：「登出之后**旧** cookie 还在不在效」那一拍要发的
  正是一个 jar 里已经不存在的串）。
* ⚠️ **用 `headers.getSetCookie()` 而不是 `headers.get('set-cookie')`**：后者在**多个**
  `Set-Cookie` 头上会用 `", "` 把它们拼成一串，而登出那一发的
  `expires=Thu, 01 Jan 1970 00:00:00 GMT` 里就有一个逗号 → 按逗号切会切坏。
  本仓今天每次只设一个 cookie，但那一格是**真的**会被踩到的。
* ⚠️ **cookie 与口令在 stdout 与 transcript 里一律掩掉**（只留前 22 个字符）：
  `PE_SMOKE_TRANSCRIPT` 写出的那份文档是**入库**的（`Document/2026-10-11-前后端联调取证.md`
  就是这么生成的），把一个活的会话令牌写进 git 等于把「谁都能当这个管理员」也写进 git。
* 实 measurement：一次跑下来建了 **5 个 jar**（`teacher` / `admin` / `student:4` / `student:5` / `student:10`）。

⚠️ **本脚本一个身份请求头都不发**（`TEACHER_HEADER` / `studentHeader` 两个常量已删）：
故「`PE_ALLOW_HEADER_IDENTITY=1` 还开着」与「撤掉了」对本脚本**没有区别** ——
那正是「过渡态真的撤干净了」可被判定的前提（§6）。

### 3.7 ⚠️ 浏览器自动化用了什么（**顶回 2：没有加任何 devDependency**）

派单：「控制者倾向引入 Playwright 或 Puppeteer 作为前端 devDependency …
**若你有不加依赖的办法（例如让 `--dump-dom` 之前先访问一个能设 cookie 的 URL、或用 CDP 直接连），顶回来并说明**。」

**实现者用 CDP 直接连，`package.json` 的 `dependencies` 与 `devDependencies` 一格没动**：

* **为什么 `--dump-dom` 不行**：它是「起浏览器 → 加载 URL → 把 DOM 打到 stdout → 退出」，
  **没有任何设 cookie 的入口**。而 Plan 05A 之后身份只走 `pe_session`（HttpOnly，故页面脚本也写不了它），
  且 `adoptFromUrl()` 已降级成 DEV-only —— 于是 `--dump-dom` 打开任何一条业务路由都会被守卫弹到
  `/login`，13 条路由的取证会**全部**变成「登录页的 DOM」。⚠️ 而前端是 **CSR**，
  故也**不能**用 `fetch` 拿 HTML 代替（派单自己也点了这一格）。
* **零依赖为什么可行**：Node **v24.19.0** 有**全局 `WebSocket`**（22 起不再要 flag），
  而 Edge/Chrome 的 `--headless=new --remote-debugging-port=0` 会把 DevTools 的 ws 地址打到
  **stderr**（逐字形状 `DevTools listening on ws://127.0.0.1:<port>/devtools/browser/<uuid>`）。
  两者拼起来 ~110 行就是一个够用的 CDP 客户端：
  `Target.createTarget` → `Target.attachToTarget{flatten:true}` → `Network.enable` →
  每条路由 `Network.clearBrowserCookies` + `Network.setCookie{name,value,url}` →
  `Emulation.setDeviceMetricsOverride`（375 / 1440 两档视口）→ `Page.navigate` →
  **轮询** `Runtime.evaluate` 取 `document.documentElement.outerHTML` 与
  `location.pathname + location.search`。
* ⚠️ 代价对比：Playwright 要拉一个 **~150 MB** 的浏览器下载，而本机已经装着 Edge；
  本仓前端至今**零新增依赖**（Plan 01–05A 全程），为一个取证脚本破这个例不值。
* **三个坑逐个绕开**：① `--force-prefers-reduced-motion` 仍然加（否则抓到 `StatBlock`
  数字滚动的中途帧）；② **不用 shell 重定向**（Node 的 `spawn` 直接收 stdout/stderr）；
  ③ vite 只绑 `::1` → 基址是 `localhost`。
* ⚠️ **`--virtual-time-budget` 不再需要**（**顶回 2 的附带一条**）：轮询「关键内容都出现了没有」
  比虚拟时钟更贴判据 —— 虚拟时钟会在网络请求还在飞的时候就宣布预算用完，
  而那正是 Plan 04 撞到 95.7 的那一族失效。
* ⚠️ **一个实测撞到的坑**：`child.kill('SIGKILL')` 是异步的，而 Windows 上 Chromium 的
  `--user-data-dir` 在进程还活着的一刻是被**独占打开**的，故紧跟着的 `fs.rmSync` 会得到
  **`EPERM: permission denied`**（不是 ENOENT，`force: true` 挡不住它）。
  处置：① 先等 `exit` 事件（5 s 上限）② `rmSync` 加 `maxRetries: 10, retryDelay: 400`
  ③ 仍删不掉就**只警告、不判红**（一个留在 `$env:TEMP` 下的目录不是本步要证的事，
  而把它判红会让「15 条路由全部取证成功」这一次运行因为一个清理动作而红）。
* ⚠️ 路由从 **13 条扩到 15 条**（+ `/login` + `/bind`，**顶回 4**：派单说的是 13 条，
  而 Plan 05A 新建了两页，不取证就等于「登录页渲染得出来」这句话没有可执行判据），
  并**额外**实测「未登录访问 `/s/home` → `/login?next=/s/home`」与「登录页不是白屏」。
* ⚠️ **URL 里一个 `?student=` / `?teacher=` / `?as_of=` 都没有了**：身份由 `jar` 决定、
  业务日由 `stores/identity.ts` 的 `DEMO_AS_OF` 决定（一个全新的浏览器 profile 里
  `localStorage` 是空的 → 一定落到那个缺省值）。⚠️ 这同时是「取证不再依赖
  `adoptFromUrl()`」的可执行证明。

### 3.8 第 16 步（鉴权全链路）的 63 条断言都验了什么

① 管理员建一个新教师 `SMOKE16` → 201，且 `role` 缺省是 **`teacher`**（漏写 `role` 的失效方向是
少给权限）、`password_bound_at` 是 `null`、响应里**没有** `password_hash`；
② 未绑定就登录 → **403 `password_not_bound`**；
③ 绑定的四档失败：**422 `unprocessable_value`**（弱口令，排最前）/ **403 `forbidden`**（验身材料不符）/
不在册也是 **403 且 message 与上一档逐字相同**（不给区分信号）/ **422 `request_validation_failed`**
（缺字段，且响应体里**没有**刚提交的口令 —— `SecretStr` + 按键名脱敏两道）；
④ 绑定成功 → **204 + 空响应体 + 不种 cookie**；
⑤ 再绑一次 → **409 `password_already_bound`**；⚠️ 而「已绑定 **+** 验身材料不符」实测是 **403**
（**顶回 7 的附带一条**：403 那一档**先**判，故 409 只对**拿着正确验身材料**的人可见 ——
那正是「409 排在 403 之后」要的效果，实现者第一版把它写成了 409、当场红，已按实际改写并把理由写反的地方纠正）；
⑥ 口令错 → **401 `invalid_credentials`**（与 ② 刻意可区分）；
⑦ 登录成功 → 200 + `pe_session=<64 字符>` + cookie 的 **7 个参数逐个断言**
（`HttpOnly` / `Max-Age=7200` / `Path=/` / **`SameSite=lax` 小写** / **不带 `Domain`** / **不带 `Secure`**）
+ 响应体**恰好 6 个键**且 `staff_no` 与 `student_no` 互斥；
⑧ `GET /api/auth/me` 与登录的响应体**逐字相同**（`meRes.text === loggedIn.text`）；匿名 `me` → 401；
⑨ 三档授权：**普通教师写管理台 → 403 `forbidden`** / **管理员写 → 201** /
⑩ **学生 cookie 打教师端点 → 403**（跨 kind，不是 401）+ 学生 cookie 读名册 → 401 或 403；
⑪ 登出 → 204 + `pe_session=""; Max-Age=0; expires=…1970…` 且 `Path`/`SameSite`/`HttpOnly`
与种下时**逐字相同**（RFC 6265 的删除按 `(name, domain, path)` 三元组匹配）+
**再用那一份旧 cookie → 401**（登出是真的失效）+ 重复登出 → 401；
⑫ **subject 已从名册上删掉 → 那一份 cookie 当场失效**：⚠️ 这一拍**另建一个人**
（`SMOKE16C`：建 → 绑 → 登录 → `me` 200 → 删掉他 → **同一份从没登出过的 cookie** → 401），
因为 ⑪ 那一份已经吊销了，拿它再测一次会得到一个 401 而**什么也没证明**（假绿）。
这一格钉的是 `user_session.subject_id` **刻意不是外键**（多态外键在 SQL 里不存在）的补偿机制
（`sessions.resolve` 每次回查 subject 行、查无此人当场吊销）—— 计划 §3.1 逐字称之为
「本计划最容易漏的一格」；
⑬ 收尾：把本步建的三行**都删掉**，并断言名册回到 **3** 个教师（本步一行都没留下）。

### 3.9 Task 4 的验收

| 验收项 | 结果 |
|---|---|
| `smoke.mjs` 退出码 0、17 步全绿 | ✅ **0 / 17 步 / 305 断言 / 0 红** |
| `demo.ps1` 跑完之后三种角色各有一个可登录的账号 | ✅ 学生（60 个全部）/ 教师（T0001、T0002）/ 管理员（T0003），第 0 步逐个登录并断言 `me` 的 `role` |
| 登录口令被打印出来 | ✅ `[6/7]` 那一步 + `demo.ps1` 的「演示账号」段（后者只指路、不抄第二份字面量） |

---

## ④ Task 5 第 1 步：spec 勘误

`Document/2026-09-28-体育闭环原型-设计spec.md`（⚠️ 全程用 **python** 改，不用编辑器工具）：

| | 改前 | 改后 |
|---|---|---|
| 字节数 | **170 629 B** | **189 889 B** |
| 行数 | 1322 | **1514**（CRLF 计数 **1513**） |
| 行尾 | **CRLF**（1322/1322，纯 CRLF） | **CRLF**（1513/1513，纯 CRLF，**保持**） |
| BOM | 无 | **无**（保持） |
| sha256[:16] | **`042250572DEB0394`** | **`89EC13281E9D71E0`** |

⚠️ **改前先用 `read_bytes()` 复核过**：实测 `170 629 B / 1322 CRLF / 无 BOM / 042250572DEB0394`，
与派单给的值**逐字相同**（`.gitattributes` 的范围只限 `backend/data/**` 与 `.superpowers/**`，
故 `Document/**` 在 `core.autocrlf=true` 下是「index LF / 工作树 CRLF」）。

**§1.2 改了什么**：把「在运维、**鉴权**、推送、多租户等生产基础设施上明确降级」里的
「鉴权」摘出来，加一段「**已做真实鉴权**」（绑定 → 登录 → HttpOnly cookie 会话 → 校验 →
登出真的吊销；`role` 影响的两件事；PBKDF2-SHA256 600 000 次迭代 + 自描述串 + `compare_digest`；
**后端零新增依赖**）+ 一张 **12 条已知局限**表：
① 不做口令找回 ② 不做失败锁定/**也不做限速**（600 000 次迭代 ⇒ 试口令同时是**廉价 CPU DoS**：
一个请求换服务端 ~0.3 s）③ **不做防枚举**（`password_not_bound` 与 `invalid_credentials`
两档区分泄漏了「在不在册」，含控制者接受的三条理由）④ **绑定验身材料 `birth` / `name` 本身的强度**
（Task 5 之前匿名可读、之后要教职身份，**残余风险如实写**：一个教职可以给一个还没绑定的账号抢先绑口令）
⑤ **不做 CSRF 双重提交令牌**（两条顶住 + ⚠️「第 ② 条依赖同源前提，跨源部署当场失效」逐字写进去）
⑥ `Lax` 不挡同站子域、也不挡用户被诱导在本站点上发请求 ⑦ `role` 在 `user_session` 上冗余存的
**真实代价**（降权对权限立刻生效、对前端路由要等重登）⑧ `subject_id` 不是外键 + 补偿机制
⑨ 过期/吊销行不清理（**是空间问题不是安全问题**，守卫在场）⑩ 不做一键登出全部设备
⑪ 不做 OAuth/SSO/CAS ⑫ 不做 RBAC 矩阵、不建权限表。

**§13 加了「登录」那一节**（§13.4 整节改写，从「身份：两个请求头（**没有真实鉴权**）」
改成「身份与登录（Plan 05A 起：**真实鉴权**，一个 `pe_session` cookie）」，五个小节）：
* **13.4.1 三种角色** —— ⚠️ 管理员**不是**第三种 `kind`（`LoginCreate.kind` 的取值域唯一所有者是
  `UserSession.KINDS`），故登录表单只有两档、而**跳哪个首页**由 `role` 决定；`role` 只影响两件事。
* **13.4.2 五个端点** —— 逐档 code 表 + 「名册已存在 + 首次绑定，不是自助注册」+
  **请求体字段名逐字**（⚠️ `birth` 不是 `birth_date`；登录是 `kind`+`login`+`password`）+
  「绑定成功不自动登录」+ 「竞态的判据是影响行数」+ **cookie 的七个参数**（含
  `SameSite=lax` 小写与「不设 `Domain`」的理由）+ 「HttpOnly ⇒ 前端只能问 `me`」+
  「滑动过期，不做 refresh 令牌」。
* **13.4.3 演示账号** —— 三种角色 / 口令 **`pe-demo-2025`** / 管理员 **`T0003` 赵志刚** /
  `demo.ps1` 的用法（含 ⚠️「口令的唯一所有者是 `DEMO_PASSWORD`，`demo.ps1` 刻意不抄第二份」/
  ⚠️「管理员刻意不是 T0001」/ ⚠️「`PBKDF2_ITERATIONS` 的演示值 100 000 与理由」/
  ⚠️「`create_all` 对已存在的表原样跳过、不会补列，故手工留下的旧演示库会 500」）。
* **13.4.4 读的一侧** —— 44 匿名 + 4 要教职身份，含「为什么是教职而不是任何已登录的人」、
  代价、以及**三条守卫的名字**。
* **13.4.5 跨源部署那一档** —— **五件事一起改**（少任何一件都静默失效），
  并逐字写明「§1.2 第 5 条那条 CSRF 论证的第 ② 半在 ①② 落地之后**当场失效**」；
  外加「Swagger UI **设不了** HttpOnly cookie，故在 `/docs` 上试登录的正确姿势是直接打
  `POST /api/auth/login`，`pe_session` 那一格是**声明性**的」。
* ⚠️ **§13.3（三个禁区 CLI）一个字没动** —— Plan 03 fix 波 2 刚改过它（当时是为了不再教人跑
  那三个禁区 CLI），派单逐字要求「不要把它改回去」。
* **§13.5** 的端点计数从 64/92/45 改成 **71/99/52**，并逐格写清每一波是怎么变的
  （Plan 03 结案 64/92/45 → Plan 04 收尾波 66/94/46 → Plan 05A Task 1 71/99/48 →
  Task 2 **不动这三格**（改的是判定不是载体）→ Task 5 71/99/**52**），
  以及机器口径的**两个**住址（后端那条全仓级断言 + 前端 `smoke.mjs` 第 12 步，两处刻意不合并）。

---

## ⑤ Task 5 第 2 步：48 个匿名 GET 的重新裁定

### 5.1 判据（只有一条）

> **这个响应体里有没有「能拿来绑定/接管账号」的材料？** 有 → 要身份；没有 → 保留 Plan 04 的刻意取舍。

⚠️ **刻意不一刀切**：Plan 04 偏离 ⑦ 的论证是「在不加强制的前提下声明 `security` 是一份
反方向的假契约」，而它的**前提**是「本系统不做真实鉴权」—— Plan 05A 做了，故前提没了、
要重新过一遍；但「重新过一遍」的结论**不是**「全部收紧」，而是「按判据逐个过」。
⚠️ **大屏匿名可读那一档没有被推翻**：大屏读的是 `/api/dashboard/*`（仍匿名），不是名册。

### 5.2 ⚠️ `birth` 那一格：选了 **(b)**，不是控制者倾向的 (a)（**顶回 4**）

**(b) = 把 `GET /api/students` 与 `GET /api/students/{id}` 整个改成要教职身份。**
三条理由（每条都是实测出来的，不是推的）：

1. **(a) 修不了教师那一侧**。教师的验身材料是 `staff_no` + `name`，而 `name` **摘不掉**
   （教师端的大屏/周报/预警队列/`TeacherNav` 到处要显示同事与学生的姓名，
   `course_section.teacher_id` 也要靠它翻成人名）。故 (a) 只堵一半。
   ⚠️⚠️ 而**教师那一侧比学生那一侧更严重**（**顶回 5**，派单与计划都只点了学生那一侧）：
   `GET /api/teachers` 匿名返回的 `staff_no` 与 `name` **就是完整的验身材料**
   （学生那一侧至少还要一个 `birth`），而 **`role` 也在同一个响应体里并排躺着** ——
   于是「读过一次 `GET /api/teachers` 的人」可以给**任何**工号绑口令，
   包括挑一个 `role='admin'` 的工号绑成自己的（`bind` 不看 role、也不改 role，
   但登录之后他就是那个管理员）。**实测取证**：改前匿名 `GET /api/teachers?limit=5` → **200**，
   响应体逐字含 `{"id":3,"staff_no":"T0003","name":"赵志刚","role":"admin",…}`。
2. **(a) 还要给管理台另开一条能读到 `birth` 的路**（派单自己点了这一格：「管理台要能编辑 `birth`」），
   而那只有两种形状，两种都更贵：
   * 让 read-one 的**响应形状随身份变化** → 推翻 `response_model`，并当场红掉
     `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them` 那套
     「list 键集合 = 全部列 − JsonText 列 − 秘密列」的**三方对拍**（而 `_SERVER_GENERATED_HIDDEN_COLUMNS`
     那一档的语义是「**服务端生成**、且是秘密」，`birth` 是用户提交的列、**不是**服务端生成的，
     把它塞进去会让那份清单的语义变成一句假话）；
   * 新加一个窄端点（例如 `GET /api/students/{id}/identity-record`，仅管理员）→
     **+1 路径模板 +1 操作**，⚠️ 而前端那个管理台是**数据驱动**的
     （`ResourceDetail.vue` 按 `RESOURCES` 的一行 + `/openapi.json` 渲染），
     它**不会**去调一个 bespoke 端点 —— 于是「教务干事看得到出生日期」这件事仍然不成立，
     除非再改前端。
3. **(b) 一个机制同时关掉两侧的洞，且管理台的列可见性一格不少**（`StudentRead` 仍然 8 列、
   `TeacherRead` 仍然 5 列，故 `_SERVER_GENERATED_HIDDEN_COLUMNS` 的 3 格与
   `declares_list_exclude == 3` 两条断言**一个字都不用改**）。

⚠️ **(b) 的残余风险如实记**（已写进 spec §1.2 第 4 条）：一个**已登录的教职**仍然能读到全校的
`birth` / `name`，故他可以给一个**还没绑定**的账号抢先绑口令（`bind` 只对
`password_hash IS NULL` 的行放行，故它挡不住抢占）。生产要换成不可猜的验身材料
（一次性绑定链接 / 校园卡后台校验）。⚠️ 而这一档比改前**严格更窄**：改前是**任何匿名调用方**。

⚠️ **为什么收得比「任何已登录的人」更窄**（要**教职**）：实测前端 13 个页面里读
`/api/students` 的是 4 个教师页（`Dashboard` / `ClassReport` / `AlertQueue` / `TeacherNav`）
+ 3 个管理台页 + 那个 DEV-only 的切换器；**学生页一个都不读**（它们一律走
`/api/students/{id}/home` 那类按人收窄的窄端点）。故要求学生身份没有任何收益，
而要求教职把「学生抢先绑同学」那一档也关掉了。

### 5.3 落地形状（⚠️ **没有动泛型工厂的核心**）

* `app/api/crud.py`：加一个 `_require_staff_identity`（= `current_teacher` + `require_staff` 的组合，
  与既有的 `_require_admin_identity` 逐字同构）+ 一个 `read_guarded` 列表 +
  `build_crud_router` 的一个**可选 kwarg** `read_requires_staff: bool = False`
  （挂进两个 `GET` 的 `dependencies=`）+ **第 8 道导入期校验**（`readable=False` 时这一格无从生效，
  与第 7 道 `require_admin × writable` 同一条口径）。
  ⚠️ 派单说「若你发现干净的做法需要动泛型工厂的核心，先顶回来再动」——
  **不需要**：加一个缺省为 `False` 的 kwarg + 一个 `dependencies=` 实参，21 行的行为一格没变。
* `app/api/routers/catalog.py`：`students` 与 `teachers` 两行**字面写出**
  `"read_requires_staff": True`（⚠️ 缺省值是 `False`，故「忘了写」= 静默退回匿名可读，
  与 `on_delete` / `require_admin` 同一条纪律：必须字面写、且有守卫钉住「键在不在」）。
* ⚠️ **`Security(TEACHER_STAFF_NO_SCHEME)` 与 `Depends(_require_staff_identity)` 成对挂**
  （P4-A5 那条口径：只挂判定则前端从 spec 上看不出来要带身份、一接就 401；
  只挂声明则 spec 上写了而实际谁都放行，因为那个 scheme 是 `auto_error=False` 的）。

### 5.4 那三条守卫的名字（派单点名要报）

| 守卫 | 面 | 钉什么 |
|---|---|---|
| **`tests/api/test_crud.py::test_exactly_two_resources_declare_read_requires_staff`** | 声明面 | `RESOURCES` 里**恰好 2 行**字面写了这一格、且是 `("/api/students", "/api/teachers")`；**另外 21 行不得写它**（写 `False` 也不行）。⚠️ 少了「另外 21 行」那一拍，「把闸门挂到全部 23 个资源上」是静默的 |
| **`tests/api/test_crud.py::test_the_two_roster_resources_admit_only_staff_reads`** | 行为面（五拍） | 匿名 **401 `unauthenticated`** / 不在册的工号 **403 `forbidden`** / 普通教师 **200** / 管理员 **200** / ⚠️ **反假绿**：那两份响应体里**确实**有 `birth` 与 `{staff_no, name}`（否则「404 也不是 200」能让前四拍绿），且 openapi 的 `security` 逐字是 `[{"X-Teacher-Staff-No": []}]` |
| **`tests/api/test_crud.py::test_all_twenty_three_resources_are_listable`**（既有条，本波加了一拍） | 反面 | **`anonymous == 21`**：另外 21 个资源的 list **仍然匿名可读**，且那一档**确实没带头**（`got.request.headers.get("X-Teacher-Staff-No") is None`） |
| **`tests/api/test_prescription_api.py::test_the_identity_schemes_are_registered_as_openapi_security_schemes`**（既有条，本波改口径） | 全仓级 | 带 `security` 的 CRUD GET **恰好**是那 4 个（`staff_only_reads` 字面清单）、`expected_crud_security` **26 → 30**、挂 security 的操作数 **48 → 52** |

⚠️ 派单要求「**无论选哪个，都要有一条守卫钉住『匿名调用方拿不到 `birth`』**」：
上面第 2 条的**第 ① 拍**（匿名 `GET /api/students` 与 `GET /api/students/{id}` → **401**）
就是它 —— 下一个人把 `read_requires_staff` 删掉、或给 `StudentRead` 加回一列，都会当场红。

### 5.5 ⚠️ 48 个匿名 GET 的逐个裁定表

判据见 §5.1。「列」一栏是**实测响应体**（`items[0]` 的键集合，运行时口径，不是读源码）。

**A. 改成「要教职身份」的 4 个**（2 个资源 × 集合/成员）

| 资源 / 端点 | 改前匿名返回的列 | 裁定 | 理由 |
|---|---|---|---|
| `GET /api/students` | `id, student_no, name, sex, **birth**, department, grade, password_bound_at`（8 列，`password_hash` 已被 Task 1 的 `list_exclude` 排掉） | **要教职身份** | `birth` **正是**学生绑定口令的验身材料 → 匿名可读 = 谁都能给谁绑口令再登录成他 |
| `GET /api/students/{student_id}` | 同上 8 列 | **要教职身份** | 同上（⚠️ 只收 list 不收 read-one 的话，扫 60 个 id 就绕过去了） |
| `GET /api/teachers` | `id, **staff_no**, **name**, role, password_bound_at`（5 列） | **要教职身份** | ⚠️ `staff_no` + `name` **合起来就是教师绑定的全部验身材料**，且 `role` 并排躺着 → 能挑一个 `admin` 工号绑成自己的。**这一格派单与计划都没点到** |
| `GET /api/teachers/{teacher_id}` | 同上 5 列 | **要教职身份** | 同上 |

**B. 仍匿名的 44 个**（逐个过了一遍；按资源归组，`/api/health` 与
`/api/mini-tests/normalized` 两个特例单列）

| # | 端点（集合 + 成员各一个，除注明外） | 实测列数与关键列 | 裁定 | 理由（判据：有没有「能拿来绑定/接管账号」的材料） |
|---|---|---|---|---|
| 1 | `/api/health` | 3：`status, tables, students` | **仍匿名** | 存活探针（`demo.ps1` / CI / 反代都要能不登录打它）；一格秘密都不含 |
| 2 | `/api/semesters` | 6：`name, start_date, end_date, weeks, is_current` | **仍匿名** | 全库的时间轴锚点，无个人信息 |
| 3 | `/api/course-sections` | 6：`name, grouping_mode, schedule_text, semester_id, **teacher_id**` | **仍匿名** | ⚠️ `teacher_id` 是**代理键**、不是工号；要翻成人名必须读 `/api/teachers`（已收）。故它单独不构成验身材料 |
| 4 | `/api/enrollments` | 4：`student_id, course_section_id, semester_id` | **仍匿名** | 纯代理键的关系表；「谁在哪个班」不含姓名/学号/出生日期 |
| 5 | `/api/fitness-test-batches` | 6：`academic_year, source, test_date, timepoint, semester_id` | **仍匿名** | 批次元数据，不含个人 |
| 6 | `/api/fitness-test-results` | **21**：`student_id, height_cm, weight_kg, vital_capacity_ml, sprint_50m_s, …, total_score, national_grade` | **仍匿名**（⚠️ 关切） | **不含**验身材料，故按判据保留；⚠️ 但它是**学生健康数据**（全校 60 人的体测成绩），已登记为待清扫第 13 条（生产要收） |
| 7 | `/api/body-compositions` | 8：`student_id, weight_kg, body_fat_pct, muscle_mass_kg, smi, measured_on, device` | **仍匿名**（⚠️ 关切） | 同上（体成分 = 健康数据） |
| 8 | `/api/interest-surveys` | 5：`student_id, total_score, filled_on, semester_id` | **仍匿名** | 只有一个总分，无自由文本 |
| 9 | `/api/mini-tests` | 9：`student_id, squat_30s_count, shuttle_20m_s, normalized_score, entered_by, week, …` | **仍匿名** | ⚠️ `entered_by` 是**工号字符串**（不是外键）。⚠️ 但「工号」单独不是验身材料（教师绑定要工号 **+ 姓名**），而姓名已随 `/api/teachers` 收走 |
| 10 | `/api/mini-tests/normalized`（特例） | `{semester_id, week, sections:[{course_section_id, scored_count, entries:[{student_id, composite, …}]}]}` | **仍匿名** | Plan 04 Task 3 刻意摘掉教师头（学生页要渲染班内百分位）；每一格都是 #9 + #4 两份匿名数据的**纯函数**（那张逐字对账表住在 `feedback.normalized_scores` 的 docstring） |
| 11 | `/api/class-sessions` | 6：`course_section_id, session_date, period, rpe_opened, batch_id` | **仍匿名** | ⚠️ **`rpe_token` 已被 Plan 03 收尾小修波从两半都摘掉**（`ClassSessionRead` + `list_exclude`）；教师读它走 `GET …/rpe-token`（要教职身份）。`smoke.mjs` 第 3 步逐字扫整份响应体原文钉住这一格 |
| 12 | `/api/rpe-records` | 6：`class_session_id, student_id, rpe, elapsed_seconds, submitted_at` | **仍匿名** | 一个 1–10 的主观强度值，不含验身材料 |
| 13 | `/api/training-logs` | 11：`student_id, log_date, completed, duration_min, feeling, late, is_rest_day, source, submitted_at, batch_id` | **仍匿名**（⚠️ 关切） | 不含验身材料；⚠️ 是行为数据，同第 13 条待清扫 |
| 14 | `/api/prescriptions` | 11：`student_id, template_ref, generated_on, valid_from, valid_to, microcycle_weeks, label_at_generation, status, previous_had_overrides, batch_id`（⚠️ 5 个 `JsonText` 列被自动 `list_exclude` 排掉，read-one 才含） | **仍匿名** | 处方**元数据**；具体的训练内容在 read-one 的 JsonText 列里，仍是「体育专家维护的知识资产 + 该学生的分层结果」，不含验身材料 |
| 15 | `/api/weekly-adjustments` | 8：`prescription_id, week, factor, reason, source, created_at, batch_id` | **仍匿名** | 一个乘数 + 一句理由 |
| 16 | `/api/stratification-results` | 9：`student_id, label, hit_rules, valid_from, valid_to, percentile_source, computed_on, batch_id` | **仍匿名** | 红/黄/绿标签 + 命中规则（spec §9.2 逐字要求「分层标签可点击展开命中规则」，即**可解释性本身就是产品需求**） |
| 17 | `/api/derived-metrics` | 8：`student_id, trend, valid_count, weakness_count, body_comp_abnormal, computed_on, batch_id` | **仍匿名** | 三个聚合量，无原始测量值 |
| 18 | `/api/percentile-snapshots` | 14：`age_group, sex, item, p10…p75, sample_size, source, semester_id, batch_id, computed_on` | **仍匿名** | **群体**分位数（按龄组 × 性别），一行都不指向个人 |
| 19 | `/api/alerts` | 13：`student_id, rule_id, level, status, triggered_at, handled_action, handled_at, subject_key, window_key, semester_id, course_section_id, batch_id` | **仍匿名** | 预警是**教师端大屏/队列**的输入（Plan 04 的取舍：大屏匿名可读）；不含验身材料。⚠️ 处置它（`POST …/handle`）要教职身份 |
| 20 | `/api/notifications` | 10：`recipient_id, recipient_kind, title, **body**, channel, is_read, alert_id, prescription_id, created_at` | **仍匿名**（⚠️ 关切） | 不含验身材料；⚠️ 但 `title`/`body` 是**发给某个学生的话**（「发给我的消息」那一档已经有一个挂 security 的窄端点 `/api/students/{id}/notifications`）。同第 13 条待清扫 |
| 21 | `/api/weekly-class-reports` | 7：`course_section_id, semester_id, week, suggestion, generated_at, batch_id`（⚠️ 3 个 `JsonText` 列 list 不含） | **仍匿名** | **班级**级（不是个人级）；spec §8.5 的那两项产出本来就是给教师大屏与展示用的 |
| 22 | `/api/exercises` | （演示库 0 行；read-one 含 `code, name, category, …`） | **仍匿名** | 体育专家维护的**知识资产**（spec §4.4：改阈值走版本控制与评审，不在运行时改库）；`writable=False` |
| 23 | `/api/prescription-templates` | （演示库 0 行；read-one 含 18 套模板的 YAML 折算） | **仍匿名** | 同上（知识资产，`writable=False`） |

⚠️ 上表 23 行里 21 行是「集合 + 成员」两个端点（`/api/health` 与
`/api/mini-tests/normalized` 各 1 个），故 21 × 2 + 2 = **44**，与运行时口径逐字对上
（`app.openapi()["paths"]` 实测：GET 60 = 匿名 **44** + 挂 security **16**）。

⚠️ **挂 security 的 16 个 GET**（对照用，本波 +4）：`/api/auth/me`、
`/api/class-sessions/{id}/rpe-token`、`/api/class-sessions/{id}/rpe-status`、
`/api/dashboard/class/{id}`、`/api/dashboard/weekly-class-report/{id}`、
`/api/students/{id}/home`、`/api/students/{id}/notifications`、
`/api/students/{id}/prescriptions/current`、`/api/students/{id}/training-logs/completion-rate`、
`/api/students/{id}/weekly-sheet`、`/api/teacher/students/{id}/home`、
`/api/teacher/students/{id}/weekly-sheet`，**+ 本波新加的 4 个名册读**。

### 5.6 连带的既有测试改动（8 条红 → 全绿）

| 红的条 | 怎么改 |
|---|---|
| `test_all_twenty_three_resources_are_listable` | 加 `admin_headers`，**只对声明了 `read_requires_staff` 的 2 行带头**（⚠️ 一律带头会让「闸门挂到全部 23 个资源上」静默）；`total == 1` 对那 2 行放宽成 `>= 1`（因为 `admin_headers` 夹具**自己也插一行 `teacher`**，实测 `/api/teachers` 是 2 行），判据换成「`seeded` 那一行在不在 `items` 里」；另 21 行**仍然严格 `== 1`** |
| `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them` | 同上（`staff_headers` 只给那 2 行） |
| `test_delete_returns_204_and_the_row_is_gone` | 「删掉之后 read-one → 404」那一拍加 `headers=admin_headers` |
| `test_an_admin_can_create_and_delete_while_a_teacher_cannot` | 同上 |
| `test_on_delete_restrict_names_the_blocking_child_table` | 「被挡住的那一行还在 → 200」那一拍加 `headers=admin_headers` |
| `test_every_writable_resource_admits_only_an_admin_mutation` | 「GET 仍然匿名」那三行改成**按 `read_requires_staff` 分档**：声明了的断「匿名 401 / 管理员 200 / **普通教师 200** / openapi 的 security 逐字」，没声明的照旧断「匿名 200 + 两个 `"security" not in …`」。⚠️ **两侧都在场**（硬规矩 #50） |
| `test_the_identity_schemes_are_registered_as_openapi_security_schemes` | ③ 读的一侧从「一个 `security` 都不带」改成「**恰好**那 4 个」（`staff_only_reads` 字面清单 + 逐格断言 scheme）；`expected_crud_security` **26 → 30**；合计 **48 → 52**；`len(expected)` 仍 **22**（那 4 个是 CRUD、不是特例端点，故 `crud` 那一圈的操作数仍 77） |
| `test_no_credential_column_appears_in_any_response_body` | 那 4 个名册读改成**先以管理员登录**再打。⚠️ 而「先登出、再登录」这个顺序是**承重的**：它顺带证明了登出真的清掉了 cookie（否则那 4 个请求会是「带着上一个学生的会话」发出去的，而学生身份打名册是 403） |

⚠️ **`app/auth/**`、`app/api/routers/auth.py`、`app/api/deps.py` 的鉴权核心一个字都没改**
（派单的禁区）。本波改的后端文件只有 `app/api/crud.py`（+1 个闸门函数、+1 个 kwarg、
+1 道导入期校验、+1 个 `dependencies=` 实参）与 `app/api/routers/catalog.py`（2 行各 +1 个键 + 模块 docstring）。

---

## ⑥ Task 5 第 3 步：撤掉过渡开关之后 `smoke.mjs` 是否仍全绿

**是。✅ 17/17 步全绿、305 条断言、0 红、退出码 0。**

* 撤掉的动作：`demo.ps1` 里 `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 那一行**删除**，
  并把「③ 三个环境变量」改成「③ 两个环境变量」、把打印从
  `PE_ALLOW_HEADER_IDENTITY = 1 (过渡态，Task 5 撤掉)` 改成
  `PE_ALLOW_HEADER_IDENTITY 未设（= 生产缺省 "0"：只认 pe_session cookie…）`；
  「身份有两条通道」那一段改成「身份**只有一条**通道」并明写
  「手工发 `X-Teacher-Staff-No` / `X-Student-Id` 在本进程上**没有任何效力**」。
  ⚠️ 那段散文**保留**（不是删掉就算完）：它逐字记了「为什么当初必须打开」与
  「为什么现在可以撤」，以及「要在本机临时打开请在**另一个**终端里设」。
* ⚠️ **判据是硬的**：撤掉之后**重跑了 `demo.ps1`（重灌演示库）+ `smoke.mjs`**，
  而那个脚本**一个身份请求头都不发**（`TEACHER_HEADER` / `studentHeader` 两个常量已删，
  一律走自己维护的 cookie jar），故「过渡态真的撤干净了」与「联调仍然通」是**同一件事**。
* ⚠️ 复核了终端级的残留：跑 `demo.ps1` 之前显式
  `Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY` 并断 `Test-Path Env:\…` 是 **False**
  （我在同一个终端里手工起过一次带 `=1` 的 uvicorn；`$env:` 是终端级的，
  不清掉的话「撤干净了」这句话会是假的）。
* ⚠️ 撤掉之后**演示仍然跑得起来**（派单逐字点名的顺序约束：「撤掉之后前端必须真的能登录，
  否则演示就跑不起来了 —— 故顺序是硬的：Task 3 与 Task 4 先做完」）：
  Task 3 交付了 `/login` 与 `/bind`，Task 4 让 63 个账号都有了口令、且有了管理员。
  `smoke.mjs` 第 14 步的 15 条路由取证就是这一句的可执行证明（它跑的正是**前端**）。

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 7.1 待清扫（**12 条开放** = Task 1+2 那 12 条里剩 5 条 + 本波新增 7 条）

**Task 1+2 报的 12 条，逐条结清**（用 `Grep` 取它报告的 §7.1，未打开整份报告）：

| # | 条目 | 状态 |
|---|---|---|
| 1 | 撤掉 `demo.ps1` 的 `PE_ALLOW_HEADER_IDENTITY=1` | ✅ **本波做掉**（§6） |
| 2 | `user_session` 的过期行清理任务 | ⏳ **生产**（原型不做定时进程）。⚠️ **派单要求「核实守卫在不在」→ 已核实，在场 3 条**：`tests/api/test_auth_api.py::test_an_expired_session_is_401_but_is_not_marked_as_revoked`、`tests/auth/test_sessions.py::test_revoke_writes_revoked_at_and_is_idempotent`、`…::test_a_session_whose_subject_has_been_deleted_is_revoked_in_the_row`（+ `tests/api/test_auth_api.py::test_a_session_whose_subject_has_been_deleted_is_revoked_on_the_next_request`）。故它只是**空间**问题、不是安全问题。已写进 spec §1.2 第 9 条 |
| 3 | 登录端点的速率限制（CPU DoS 那一面） | ⏳ **生产**。已写进 spec §1.2 第 2 条（含「一个请求换服务端 ~0.3 s」的算式） |
| 4 | CSRF 双重提交令牌（仅跨源部署时需要） | ✅ **已逐字写进 spec**（§1.2 第 5 条 + §13.4.5 的「五件事一起改」）；⏳ 实现仍是「跨源才做」 |
| 5 | `GET /api/students` 匿名返回 `birth` | ✅ **本波做掉**（§5） |
| 6 | `password_bound_at` 匿名可读 | ✅ **被同一改动一并解决**（那 4 个名册读不再匿名）。⚠️ 对**教职**仍可读，与登录两档 code 的泄漏同源（计划 §3.3 已裁定接受），已写进 spec §13.4.4 |
| 7 | `require_staff` + `_teacher_id_of` 是两次查询 | ⏳ **后续**（一次签名改动，不是语义改动；超出本波范围） |
| 8 | `revoke_all_for(kind, subject_id)`（一键登出全部设备） | ⏳ **后续**。已写进 spec §1.2 第 10 条 |
| 9 | `demo_bootstrap.py` 绑演示口令 + 造第一个管理员 | ✅ **本波做掉**（§3.1–§3.3） |
| 10 | spec §1.2 与 §13 要改 | ✅ **本波做掉**（§4） |
| 11 | 重启那个跑着旧代码的 uvicorn + 删旧 `pe_demo.db` | ✅ **本波做掉**（§1.2；共重灌两次） |
| 12 | `Teacher.ROLES` 与 `UserSession.ROLES` 是两份词表 | ⏳ **后续**。⚠️ 本波**局部缓解**：`demo_bootstrap.py` 加了一道显式词表断言（`DEMO_ADMIN_ROLE not in Teacher.ROLES` → `SystemExit`），故「写死的字面值与词表漂开」在演示脚本这一侧是响的 |

**本波新增 7 条**：

| # | 条目 | 归谁 |
|---|---|---|
| 13 | **44 个匿名 GET 里仍有大量学生个人数据**：`/api/fitness-test-results`（21 列体测成绩）、`/api/body-compositions`、`/api/training-logs`、`/api/notifications`（含 `title` / `body` 自由文本）、`/api/rpe-records`、`/api/mini-tests`。⚠️ 它们**不含凭据材料**故按 §5.1 的判据保留匿名（那是 Plan 04 的刻意取舍），但一个匿名调用方今天仍能读到全校 60 人的体测与健康数据。⚠️ **本波刻意没有改它**：改它等于把 44 个全收成要登录，那会推翻「大屏匿名可读」并连带改掉前端多处与 `smoke.mjs` 第 0/12 步的口径 | **生产**（或 Plan 05B 之后单开一波） |
| 14 | **`session → identity` 的单向兼容桥**（§2.2）：Plan 05B 应当把 13 个业务页面改成直接读 `session.id` / `session.staffNo`，然后拆掉这座桥（连带 `identity.ts` 就能瘦成「只有 `asOf`」） | Plan 05B |
| 15 | **`.superpowers/sdd/2026-10-12-…/_verify_t12.py`**：Task 1+2 留下的**未入库**探针仍在工作树里（硬规矩 #108 要求探针放 `$env:TEMP` 并跑完删掉）。⚠️ 本波**没有删它**（不是我的产物、且删别人的取证文件是一次不可逆动作），只登记 | 控制者 |
| 16 | `smoke.mjs` 第 14 步的 CDP 轮询上界是 **45 s/路由**，15 条最坏 11 分钟（实测远小于此）。可以给一个 `PE_SMOKE_ROUTE_TIMEOUT` | 后续 |
| 17 | `check-dist.mjs` 在 `dist/` 缺失时会**自己跑一次 `npm run build`**（~20 s），故那时 `npm run smoke` 的耗时含一次构建（`--no-build` 可以关掉，而 `smoke.mjs` 第 15 步的反空转那一拍正是用 `--no-build` 跑的） | 已知取舍 |
| 18 | **三个写入端点仍只过在册闸门、不过任教关系闸门**（`POST …/overrides` / `POST …/regenerate` / `POST …/alerts/{id}/handle`）：任何在册教师（含管理员）可以覆盖任何学生的处方。⚠️ 这是 Plan 03 Task 8 就登记过的既有关切、Task 1+2 的关切第 6 条也重述过，**本波没有改它**（收窄是一次一行的改动，但会改掉 Plan 04 教师端的可点范围） | 后续 |
| 19 | `Login.vue` 与 `Bind.vue` 各有一份**逐字重复**的 scoped CSS（~60 行）。Vue 的 scoped CSS 不给「跨组件共享一段规则」任何机制（`:deep()` 是往子组件里钻、不是往外共享），而提到 `styles/*.css` 会造出**第四个**布局层文件（`student`/`teacher`/`admin` 之外）→ Plan 05B 换肤时顺手收 | Plan 05B |
| 20 | ⚠️ **改 `demo.ps1` 之后一律用 `read_bytes()` 复核 BOM**：本波实测 IDE 的 SearchReplace 工具**把 BOM 吃掉了**（§3.4），已用 python 补回。这是派单点名的那一族事故的**第二次**发生 | 纪律 |

### 7.2 关切（硬规矩 #39，7 条）

1. **一个已登录的教职仍能给一个「还没绑定」的账号抢先绑口令**（验身材料对教职可读，
   而 `bind` 只对 `password_hash IS NULL` 的行放行）。比改前**严格更窄**（改前是任何匿名调用方），
   但没有归零。已写进 spec §1.2 第 4 条。
2. **44 个匿名 GET 里的学生健康/行为数据**（待清扫第 13 条）。
3. **`session.adopt()` 会把会话镜像写进 `localStorage`**（经 `identity.ts`）：登出时 `forget()` 会清它，
   而「浏览器崩在登出之前」会留下一个**过期的镜像**。⚠️ 它不构成安全问题（后端只认 cookie，
   而那份 cookie 已经在服务端过期/吊销），失效形态是「刷新后守卫弹去登录页、
   而 `identity.summary` 短暂显示上一个人」—— 已由 `session.summary` 取代 `identity.summary`
   在壳上的显示，故用户看不到它；但 `IdentitySwitcher` 的 DEV 那一半会。
4. **`ensureRestored()` 在「后端不可达」时让守卫放行**：于是一个未登录用户在后端挂掉时
   会看到 `/s/home` 的**空态 + 一条错误横幅**，而不是登录页。⚠️ 这是刻意的
   （把「后端没起」翻译成「请先登录」是一句假话，而用户会照它去做），
   但它的**观感**是「页面看起来坏了」。
5. **`smoke.mjs` 第 16 步会留下 3 行 `user_session`**（那张表不在 23 个资源里、没有端点，
   故删不掉）。它们 ① 2 小时后自己过期 ② subject 已删 → `resolve` 回查时当场吊销，故不可用。
   ⚠️ 而 `smoke.mjs` 第 0 步**不数** `user_session`（它数的是 7 张业务表），故重复跑不受影响。
6. **演示库上 63 个账号共用一个口令**：演示时若有人当场改口令，`smoke.mjs` 第 0 步会红。
   ⚠️ 这是**设计出来的响亮失败**（`loginJar` 的错误消息逐字点名了「先重跑 demo.ps1」）。
7. **`/api/mini-tests/normalized` 仍然是匿名的、且它按 `student_id` 给出班内 `composite`**：
   Plan 04 Task 3 的逐字对账表论证了「它不新增泄漏面」（每一格都是 #9 + #4 两份匿名数据的纯函数）。
   ⚠️ 那个论证在本波**仍然成立**（#9 与 #4 都保留匿名），故没有改它；
   但若将来把 #9 收成要身份，**这一格要一起收**（否则它的「纯函数」前提就少了一半输入）。

### 7.3 没按派单做的地方（**6 处**）

| # | 派单说的 | 我做的 | 理由 |
|---|---|---|---|
| 1 | 「**新增第 17 步**覆盖鉴权本身」+「验收：**17 步全绿**」 | 步号 **0–16** 共 **17** 步；鉴权全链路是 index **16**（= 1-based 的第 17 步）；`check-dist` **折进第 15 步**（与 `check-tokens` 并排）而不是新开一步 | 派单两句话在「18 步」的读法下互相矛盾。取 1-based 读法两句话**同时成立**（§3.5）。⚠️ 派单给的两个可选住址（`smoke.mjs` 或 `check-tokens.mjs` 旁边一个新 script）**两个都做了** |
| 2 | 「第 14 步的 **13 条路由** DOM 取证」 | **15 条**（+ `/login` + `/bind`），并额外实测「未登录 → `/login?next=/s/home`」 | Plan 05A 新建了两页；不取证就等于「登录页渲染得出来」这句话没有可执行判据。⚠️ 而派单 Task 3 的验收项「未登录访问 `/s/home` 会跳 `/login?next=/s/home`」本来就要一条判据，两处合成一拍 |
| 3 | 「`IdentitySwitcher.vue` **换成**『当前身份 + 登出按钮』」 | 换成两半：会话条（永远渲染）**+ 保留 `as_of` 输入 + DEV-only 的切换器** | ① `as_of` 此前就住在这个组件里、且是全站唯一能改业务日的入口（业务日与「我是谁」无关，登出不该清它）；② 派单自己逐字写了「**开发模式下额外保留切换能力**」 |
| 4 | 「可能 `src/api/auth.ts`」 | 建了它，**另加一个 `src/api/expiry.ts`**（派单没点） | `client.ts` 是唯一直接调 `fetch` 的地方，故 401 只有它看得见；而正确的反应要 `router` 与 `session`。直接 import 会造出 `client → router → session → api/auth → client` 的**导入环**（它失败的方式是「某一次打包顺序变了、`router` 在 `client` 求值时还是 TDZ」，只在生产构建里出现）。故用一个零依赖的叶子做发布/订阅 |
| 5 | 「`src/stores/session.ts`（与 `identity.ts` 分开还是合并**由你定**）」 | 分开 + **一座单向兼容桥**（`session.adopt()` 回写 `identity`） | 派单没料到 Plan 04 的 **13 个业务页面全部**从 `identity` 读「我是谁」（§2.2）。逐个改会把「加一个登录页」变成「动 13 个页面的取数逻辑」，而那正是 Plan 05B 要再动一遍的同一批文件 |
| 6 | Task 5 第 4 步「至少处理这三条」 | 三条**都处理了**，但「`user_session` 过期行清理」是**核实守卫 + 写进 spec**、不是实现清理任务 | 派单自己写的是「原型可以不做清理任务，但要有守卫钉住『过期/吊销的会话不能用』—— Task 1+2 说已经有了，**核实**」。已核实（4 条守卫的名字见 §7.1 第 2 行） |

### 7.4 ⚠️ 顶回控制者的地方（**7 处**）

| # | 顶回什么 | 类型 | 证据 |
|---|---|---|---|
| **1** | Task 4「控制者倾向引入 **Playwright 或 Puppeteer** 作为前端 devDependency」 | **不加依赖也能做**（派单逐字邀请顶回，并自己点了「或用 CDP 直接连」） | Node **v24.19.0** 有**全局 `WebSocket`**；Edge 的 `--headless=new --remote-debugging-port=0` 把 DevTools 的 ws 地址打到 **stderr**。~110 行的 CDP 客户端就跑通了 15 条路由的取证（`smoke.mjs` 第 14 步 **33/33 绿**）。⚠️ `package.json` 的 `dependencies` 与 `devDependencies` **一格没动**，而 Playwright 要拉 ~150 MB 浏览器下载 |
| **2** | Task 4「或用 `undici` 的 `CookieJar`，⚠️ 那是新依赖」 | **不加依赖** | 自己维护 ~40 行（`JARS` + `loginJar` + `ensureJar` + `cookieFrom`）。⚠️ 而**顺带查出一格派单没点的坑**：必须用 `headers.getSetCookie()`，`headers.get('set-cookie')` 在多个 `Set-Cookie` 头上会用 `", "` 拼接，而登出那一发的 `expires=Thu, 01 Jan 1970 …` 里就有一个逗号 → 按逗号切会切坏 |
| **3** | Task 4「把演示库的某一个教师（**例如 `T0001` 陈国华**）的 `role` 设成 `admin`」 | **换成 `T0003`** | `T0001` 是 `smoke.mjs` 全程用来验**任教范围闸门**的普通教师，而管理员**越过**那道闸门 → 把 T0001 提成管理员会让第 7 步两拍「不任教 → 403」变成 **200**（假绿）。⚠️ 派单写的是「例如」，且第 7 节逐字邀请顶回 |
| **4** | Task 5「`birth` 那一格**控制者倾向 (a)**（摘列 + `list_exclude` + 隐藏列清单加一格 + 三拍守卫）」 | **选 (b)**（那 4 个名册读整个改成要教职身份） | 三条实测理由见 §5.2：(a) **修不了教师那一侧**（`name` 摘不掉）；(a) 还要给管理台另开一条读 `birth` 的路，而那要么让 read-one 的**响应形状随身份变化**（当场红掉那套三方对拍，且 `birth` 不是「服务端生成」的列、塞进 `_SERVER_GENERATED_HIDDEN_COLUMNS` 会让那份清单的语义变成假话），要么新加一个**数据驱动的管理台根本不会去调**的窄端点；(b) 一个机制关掉两侧、且管理台的列可见性一格不少。⚠️ 派单逐字写了「你实测后自己定并说明理由」 |
| **5** | ⚠️ **派单与计划都漏了一格**：教师那一侧的洞比学生那一侧**更严重** | **计划漏了一格**（实测出来的洞） | `GET /api/teachers` 匿名返回 `staff_no` **与** `name` —— 那**两格合起来就是教师绑定的全部验身材料**（学生那一侧至少还要一个 `birth`），而 **`role` 也在同一个响应体里**。实测取证：改前匿名 → **200** + `{"id":3,"staff_no":"T0003","name":"赵志刚","role":"admin",…}` → 任何匿名调用方都能把一个 `role='admin'` 的工号绑成自己的、然后登录成管理员。⚠️ 派单 §2.5 第 2 条与计划 §3.2 都**只点了学生那一侧** |
| **6** | Task 4「`PBKDF2_ITERATIONS` 在演示脚本里应当用生产值还是测试值？… 60 人 × 600 000 会很慢（每人大约 0.3 秒 → 18 秒）。**控制者裁定：设成 100 000**」 | **同意值，但换掉理由**（并加一个 `--pbkdf2-iterations`） | 「慢」是**成本**论证，下一个人完全可以说「18 秒吃得下，安全优先」。真正硬的理由是**收益为零**：迭代次数保护的是**泄漏的哈希**，而演示口令是**明文公开**的（脚本 stdout + `demo.ps1` + spec §13 + 登录页提示），故这里没有任何东西需要保护。⚠️ 派单邀请「若你有更好的办法（例如只给少数几个账号绑密码），顶回来」：**没有** —— 只绑少数账号会让「随手挑一个学号登录」大概率失败，而那看起来像口令错了 |
| **7** | §2.3「cookie 的 **8 个参数**（实测）」 | **是「7 个键 + 1 个刻意不传」** | `sessions.cookie_kwargs()` 实测**返回 7 个键**（`key`/`value`/`max_age`/`path`/`httponly`/`secure`/`samesite`）；`domain` **不在返回的 dict 里**（它的 docstring 逐字写着「刻意不传 `domain`：不传就是宿主限定」）。⚠️ 把它数成「第 8 个参数」会让下一个人以为 `domain=None` 是一个显式传出去的值 —— 而 `set_cookie(domain=None)` 与「不传 `domain`」在 Starlette 里**不是同一件事**。⚠️ 附带一条：`SameSite` 的**值是小写 `lax`**，故断言一律按小写（写成 `Lax` 会让「有人把它改成大写」静默通过） |

⚠️ **另外三处「实测推翻了我自己的第一版实现」**（不是顶回控制者，同样记录，硬规矩 #39）：
① `smoke.mjs` 第 16 步的「已绑定 + 验身材料不符」我第一版断成 **409**，实测是 **403**
（后端 403 那一档**先**判，故 409 只对拿着正确验身材料的人可见 —— 而那正是
「409 排在 403 之后」要的效果，我把理由写反了）；
② `Login.vue` 的档位单选我第一版用 `v-model` + `@change`，而 `v-model` 会**先**改掉 `kind`
→ `pickKind` 的「同一档就直接返回」那一支恒成立 → 「换档位清掉上一档的输入」静默失效
（改成 `:checked` + `@change`）；
③ `demo_bootstrap.py` 的 `[6/7]` 我第一版在 `with Session(...)` **之外**读 `t.staff_no`，
实测 `DetachedInstanceError`（`commit()` 会 expire 实例）—— 第一次跑 `demo.ps1` 就炸在一行
`print` 的 f-string 里，离真因隔两层。

⚠️ **派单里我逐条核过、结论是「派单说的对」的决定**（§1.3 那张表的全部 ✅ 行）：
`login` 的 body 形状、`birth` 的列名、`PE_ALLOW_HEADER_IDENTITY` 住在 `app/api/deps.py`、
五个端点的逐档 code、cookie 的 `max_age=7200` 与 `samesite` 小写与「不设 domain」、
管理台 26 个写入仅管理员的三拍、管理员越过任教闸门、`_MODELS_PUBLIC_BASELINE` 仍 33、
spec 的 `042250572DEB0394`、`demo.ps1` 是 UTF-8 带 BOM + CRLF、
以及「Task 3/4 必须先于 Task 5 第 3 步」那条硬顺序。

---

## ⑧ 最终验收

### 8.1 后端

| 项 | 基线（Task 1+2 之后） | **本波收尾** |
|---|---|---|
| passed | 1331 | **1333**（+2 条新守卫） |
| 带 `--cov` | 1330 + 1 skipped | **1332 + 1 skipped** |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%**（**逐字未变**；`--cov-branch` 实测 TOTAL 行逐字相同） |
| 表数 | 26 | **26** |
| 扫描面 | 66（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | **66**（逐格相同） |
| `/api/` 路径模板 / 操作 | 71 / 99 | **71 / 99** |
| 挂 `security` 的操作 | 48 | **52**（+4 个名册读） |
| GET / 匿名 GET | 60 / 48 | **60 / 44** |
| `securitySchemes` | 3 格 | **3 格**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`models.__all__` 仍 14） |
| `pyproject.toml` | 522 B / `4BFACC372BA60A3A` | **522 B / `4BFACC372BA60A3A`**（`git diff 3cdf2dc HEAD -- backend/pyproject.toml` **空**）→ **后端新增依赖 = 0** |

### 8.2 禁区与指纹

| 项 | 结果 |
|---|---|
| 四个单文件指纹 | ✅ **逐字不变**：`D2C8E539E2FA0029` = `data/national_standard_2014.csv`、`5394B37F01DAC9AC` = `data/exercises.yaml`、`822CB86A5E998301` = `data/exercise_equivalence.yaml`、`E48E3AC82BB45BB7` = `data/alert_rules.yaml`（4/4 命中，缺 0） |
| 18 个模板指纹 | ✅ 由 `test_template_yaml_fingerprints_are_pinned` 钉住，而它在 **1333 passed** 里（`backend/data/prescription/` 下实测 **18** 个 YAML，逐个 sha256[:16] 已打印复核） |
| `git diff 3cdf2dc HEAD -- backend/data` | ✅ **空**（工作树对 `3cdf2dc` 的 `git diff -- backend/data` 也**空**） |
| `Test-Path backend\pe.db` | ✅ **False** |
| `backend/data/seed/` 文件数 | ✅ **0**（目录存在、`-Recurse` 数下来 0 个文件） |
| 没跑过 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` | ✅（要数据一律走 `backend/scripts/demo.ps1`） |
| 探针脚本的位置 | ✅ 4 个探针全部写在 `$env:TEMP`（`pe_t4_mech.py` / `pe_probe_cookie.py` / `pe_append_guards.py` / `pe_spec_edit.py` / `pe_commit*.py` / `pe_verify_final.py` / `pe_fix_bom.py`），**仓库里一个都没留**；每个都先 `python -m py_compile` 或直接跑通 |

### 8.3 前端

| 项 | 结果 |
|---|---|
| `npm run build` | ✅ 退出码 **0**；**129 modules**（119 → 129）；主 chunk **CSS 70.22 kB**（gzip 10.86）/ **JS 166.88 kB**（gzip 58.35）；`dist/index.html` 2.01 kB |
| `@ts-ignore` / `@ts-expect-error` / `as any` | ✅ **0**（`frontend/src` 全域无命中） |
| `npm run check:tokens` | ✅ 绿（扫描面 **33** 个 `.css`/`.vue`，下界 25；`tokens.css` 之外一个色值字面量都没有）→ **新增的两页没引入散落色值** |
| `npm run check:dist`（新守卫） | ✅ 绿（`dist/` **21 个文件 / 478.8 kB** 里 `adoptFromUrl` **0 次**；反空转：源码里 `dev/identity-url.ts` **3** 处 + `main.ts` **4** 处） |
| `npm run smoke` | ✅ **17/17 步全绿 · 305 断言 · 0 红 · 退出码 0**（且是在过渡开关撤掉、演示库重灌之后跑的） |
| 新增依赖 | ✅ **0**（`dependencies` 3 个、`devDependencies` 7 个，**一格没动**） |
| `src/` 文件数 | 42 → **48**（`.vue` 27 / `.ts` 15 / `.css` 6） |

### 8.4 文档

| 文件 | 改前 | 改后 |
|---|---|---|
| `Document/2026-09-28-体育闭环原型-设计spec.md` | 170 629 B / 1322 行 / 1322 CRLF / 无 BOM / `042250572DEB0394` | **189 889 B / 1514 行 / 1513 CRLF / 无 BOM / `89EC13281E9D71E0`** |
| `backend/scripts/demo.ps1` | 12 620 B / 202 CRLF / **带 BOM** / `B1592677432AF878` | **14 752 B / 223 CRLF / 带 BOM** / `6D2D0EB00D0B13DF`（⚠️ BOM 被工具吃掉过一次，已用 python 补回并复核） |
| `backend/scripts/demo_bootstrap.py` | 26 965 B / 432 CRLF / 无 BOM / `980091E07AC68763` | **39 933 B / 611 CRLF / 无 BOM**（`py_compile` 绿） |
| `frontend/scripts/smoke.mjs` | 71 780 B / 1205 CRLF / `7928A706217A5805` | **120 321 B / 1917 CRLF / `E1362B9204B81F60`**（`node --check` 绿） |
| `frontend/scripts/check-dist.mjs`（新建） | — | **8 073 B / 173 CRLF / `BF71FE35A6875BB6`** |
| `backend/app/api/crud.py` | — | **58 143 B / 904 CRLF / `5D32D92421B0A600`**（+`_require_staff_identity` / +`read_requires_staff` / +第 8 道校验） |
| `backend/app/api/routers/catalog.py` | — | **32 370 B / 574 CRLF / `0CE38B0F643CD784`**（`students` / `teachers` 两行各 +1 个键） |

### 8.5 本波的 6 个 commit

| sha | 一句话 |
|---|---|
| **`499d103`** | Task 3-A：`api/auth.ts` + `api/expiry.ts` + `stores/session.ts` + `views/auth/{Login,Bind}.vue` + `client.ts` 的 `credentials: 'same-origin'` 与 401 广播 + 横幅 14 → 17 个 code |
| **`6a946f2`** | Task 3-B：路由守卫三档 + `IdentitySwitcher` 换成会话条 + `adoptFromUrl` 搬进 `src/dev/` 并降级 DEV-only + `scripts/check-dist.mjs` 那条「build 里摇掉了」的守卫 + 管理台写按钮的判据抬成 `session.isAdmin` |
| **`c20bf09`** | Task 4-A：`demo_bootstrap.py` 的 `[6/7]` —— 63 个演示口令（`pe-demo-2025`）+ 第一个管理员（`T0003`）+ `PBKDF2_ITERATIONS` 的演示值与两道 offenders |
| **`11131e0`** | Task 4-B：`smoke.mjs` 改成「先登录」的姿势（cookie jar / CDP 取代 `--dump-dom` / 15 条路由 / 第 16 步鉴权全链路）→ **17 步 / 305 断言 / 退出码 0** |
| **`2a97800`** | Task 5：4 个名册读改成要教职身份（`read_requires_staff` + `_require_staff_identity` + 3 条守卫）+ 撤掉 `demo.ps1` 的过渡开关 + spec §1.2/§13.4/§13.5 勘误 |
| **`<本 commit>`** | 本报告 |

⚠️ **`git add` 一律按文件名逐个加**（每次加之前先跑 `git status --short`）；
`node_modules` / `pe_demo.db` / `frontend/dist` 一个都没进（三者都在 `.gitignore` 里，已复核）。
⚠️ commit 信息一律用 python 写 UTF-8 **无 BOM** 的临时文件（`$env:TEMP`）+ `git commit -F`。
⚠️ **没有 push**。

### 8.6 ⚠️ 一个行尾口径的实测发现（本波踩到、已处置）

`core.autocrlf` 实测是 **`true`**，`.gitattributes` 只覆盖 `backend/data/**`（`text eol=lf`）与
`.superpowers/**`（`-text`），故 `frontend/**` 与 `Document/**` 是「**index LF / 工作树 CRLF**」。
⚠️ **IDE 的 `Write` 工具写新文件时用的是 LF**，于是新建的 6 个前端文件在工作树里是 LF、
而同目录的既有文件是 CRLF（`git ls-files --eol` 会报 `i/lf w/lf`，与邻居的 `w/crlf` 不一致）。
处置：用 python 把本波**新建与整文件重写**的 10 个前端文件统一转成 CRLF
（`main.ts` / `router/index.ts` / `IdentitySwitcher.vue` / `api/auth.ts` / `api/expiry.ts` /
`stores/session.ts` / `views/auth/{Login,Bind}.vue` / `dev/identity-url.ts` / `scripts/check-dist.mjs`），
复核 `git ls-files --eol` 全部是 **`i/lf w/crlf`**（与 `smoke.mjs` 等既有文件逐字同形）。
⚠️ 用 SearchReplace **局部编辑**的文件（`client.ts` / `App.vue` / `identity.ts` /
两个 admin 视图 / `ApiErrorBanner.vue` / `package.json` / `crud.py` / `catalog.py` /
三个测试文件 / spec / `demo_bootstrap.py`）**自动保持了原行尾**，无需处理。
⚠️ 而 **BOM 会被 SearchReplace 吃掉**（只有 `demo.ps1` 有 BOM，已修 + 登记为待清扫第 20 条）。
