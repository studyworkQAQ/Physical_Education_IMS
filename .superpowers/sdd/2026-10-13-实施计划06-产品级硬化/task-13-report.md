# Plan 06 Task 13 · 交付前收口波（第三批：**散文 / 台账 / 结案**）—— 实现者报告

> **结论速览**：**顶回 10 处 / 0 次 Critical**（逐条见 §⑨-1）；**没按派单字面做的 3 处**
> （§⑨-2）；后端 **1562 → 1565 collected**（**1564 passed + 1 skipped** 带 `--cov`、
> **1565 passed** 不带，**两档都亲跑**）；`app/domain/` 覆盖率四格 **一格未动**；
> smoke 两档 **18/18 步 · 637 断言 · 0 红 · 退出码 0**（dev 32.1 s / 产品档 30.1 s）；
> openapi 五格**一格都没变**；表数 **28**、迁移链**仍 4 单头**、新增依赖 **0**；
> 四个数据指纹 + 18 个模板指纹**逐字不变**；两个禁区全程干净；
> `$env:TEMP` 上 **125** 个陈旧 `pe_*` 探针**统一删净并复验**；
> spec **425 949 → 487 224 B**（+ 新增 §13.14 结案节、§15 的延后台账 16 条）；
> 账本 **新建** `progress.md`（Plan 06 此前没有这一份）。
> ⚠️ **全分支终审是下一波（Task 14），本波没做**（派单逐字）。

---

## ① 环境

| 格 | 实测值 |
|---|---|
| 硬规矩 #73（开工第一件事） | `node --version` → **v24.19.0**；`python --version` → **Python 3.11.1**；`npm --version` → **11.17.0** |
| 库版本 | FastAPI **0.141.1** / SQLAlchemy **2.1.3** / alembic **1.20.0** / pydantic **2.13.5**（无 venv，`C:\Python\python.exe`） |
| 起点 | `main` @ **`b4f09ac`**，工作树干净、与 origin 同步 |
| 分支 | **`p06/prose-ledger-closeout`**（本波全程**没有 push**、**没有碰 main**） |
| 后端 | `backend\scripts\demo.ps1 -Port 8000`（**本波起了 3 次**：D2/D3/D5 的实测各一次、smoke 两档各一次；每次都重灌演示库） |
| 前端 dev | `npm run dev -- --port 5174 --strictPort`（**本波起的**，`PE_WEB_BASE=http://localhost:5174`） |
| 前端 5173 | ⚠️ 有一个**不是本波起的** vite（**PID 20240**，`::1:5173`）——按派单纪律**全程没动它**，本波一律用 5174 |
| 产品档 | `scripts\serve.ps1 -Port 8020 -SkipBuild`（本波起的，跑完产品档 smoke 后**已停**） |
| 探针住址 | `$env:TEMP\p06t13\`（**11** 个脚本；⚠️ 删除排在最后一个 commit 之后，见 §⑨-4） |

---

## ② D1 + D2 · 交付文档的正确性（甲方要读的那几页 + 两个脚本打印的 URL）

### ②-1 今天真实的 **16** 条路由（`Grep` + 起服务实测，不是读代码推的）

唯一所有者是 `frontend/src/router/index.ts` 的 `routes` 数组，实测 **20** 条路由记录，
其中 **16** 条是可导航的叶子页（= `smoke.mjs` 第 14 步 `ROUTES` 的那 16 条）：

| 分组 | 路径 | `meta.requires` | 在 smoke 的 `ROUTES` 里吗 |
|---|---|---|---|
| 鉴权 | `/login` | `none` + `public` | ✅ |
| 鉴权 | `/bind` | `none` + `public` | ✅ |
| 根 | `/` | `none` + `root` | ❌（守卫一律重定向，组件永不渲染） |
| 学生端 | `/s` | —（`redirect: '/s/home'`） | ❌（自己什么都不渲染） |
| 学生端 | `/s/home` `/s/weekly-sheet` `/s/check-in` `/s/rpe` `/s/mini-test` `/s/notifications` | `student` ×6 | ✅ ×6 |
| 教师端 | `/t` | —（`redirect: '/t/dashboard'`） | ❌ |
| 教师端 | `/t/dashboard` `/t/report` `/t/alerts` `/t/students/:studentId` | `staff` ×4 | ✅ ×4 |
| 管理台 | `/admin` `/admin/audit-logs` `/admin/:resource` `/admin/:resource/:id` | `admin` ×4 | ✅ ×4（后两条用**具体实例** `/admin/students`、`/admin/students/4`） |
| 兜底 | `/:pathMatch(.*)*` | —（`redirect: '/s/home'`） | ❌ |

⚠️ **20 与 16 的差别逐字**：`20 − 4 = 16`，那 4 条是「自己什么都不渲染」的记录
（`/`、`/s`、`/t`、catch-all）；而 16 条里有 **2** 条是**动态**记录，smoke 用具体实例跑。
⚠️ 于是「路由数 16」的判据是 smoke 那一条断言
（`路由条数 = 16（学生端 6 + 教师端 4 + 管理台 4 + 鉴权 2）`），
而**改路由树的人要改的是 `routes` 数组那 20 条**。

### ②-2 §13.6 改前 / 改后

| | 改前（逐字） | 改后 |
|---|---|---|
| 代码块 | `npm install && npm run dev` + `#   http://localhost:5173/m/        学生端 H5` + `#   http://localhost:5173/screen/   教师大屏` | `npm install && npm run dev` + `#   http://localhost:5173/          打开就是登录页（未登录访问任何业务路由都会被守卫送去 /login?next=<原路径>）` + 「是 `localhost` 不是 `127.0.0.1`：vite 只绑 `::1`」+ 产品档指回 §13.11 |
| 正文 | （无路由清单） | ① 一段 blockquote 交代**改前那两条 URL 逐字是什么、为什么今天是错的**（打开是兜底重定向 → `/s/home` → 守卫 → `/login?next=/s/home`）；② **20 条记录 × 4 列**的真实路由清单（分组 / 路径 / 它是什么 / `meta.requires`）；③ 「20 与 16 是同一棵树的两次数法」那一段；④ 「身份只有一个住址」与「角色不够时弹回他自己的首页 + 一句 `session.notice`」两格 |

### ②-3 ⚠️ 全仓活文档里另外写着 `/m/` 或 `/screen/` 的地方（`Grep` 全仓 `.md`，逐个报）

| # | 住址 | 它是什么 | 本波怎么处置 |
|---|---|---|---|
| 1 | `spec §3.2 目录结构`（`:200-201`） | `routes-mobile/ 学生端 H5，挂载于 /m/*` + `routes-screen/ 教师大屏，挂载于 /screen/*` | **不改写**（绑时点的历史陈述，硬规矩 #66）→ 在那棵树下面加一段 blockquote 指针：Plan 04 真建的是 `views/{student,teacher,admin,auth}/` + 一棵树，前缀 `/s/*` 与 `/t/*`，真实清单见 §13.6 |
| 2 | `spec §3.4 两个刻意的架构取舍`（`:219`） | 「前端单应用、两套路由树。`/m/*` … `/screen/*` …」 | 同上 → 加一段 blockquote：「单应用 + 两套路由树」这个**取舍兑现了**，而前缀名是旧口径，见 §13.6 |
| 3 | `spec §9.1 教师大屏（`/screen/*`）` | 历史设计节 | **不改写** → 标题下加一行指针（派单逐字要求的那一句） |
| 4 | `spec §9.2 学生端 H5（`/m/*`）` | 历史设计节 | 同上 |
| 5 | `spec §13.6`（`:2516-2517`） | **运行方式**（甲方运维会照着敲） | **改写**（本节唯一一处改写，理由：它是活文档） |
| — | `.superpowers/**/task-8b-report.md:595` | 历史报告里**登记过这一条待清扫** | ⚠️ **账本不改写**（派单逐字排除 `.superpowers/**`） |
| — | `Document/` 的其余 `.md`（计划 04 / 05A / 05B、`前后端联调取证.md`） | 实测**没有**把 `/m/` 或 `/screen/` 当今天的路由用（那些文件里的 URL 一律是 `localhost:5173/s/*`、`/t/*`、`/admin/*`） | 不动 |
| — | `demo.ps1` / `serve.ps1` 打印的 URL | 实测**都没有**印 `/m/` 或 `/screen/`（`demo.ps1:231` 印的是 `http://localhost:5173` 根 + 「未登录会被送去 `/login?next=<原路径>`」；`serve.ps1` 印的是 `$Base/` + 「SPA fallback：`/login`、`/s/*`、`/t/*`、`/admin/*`」） | 不动（**两处都与今天的真实路由一致**） |

### ②-4 `demo.ps1` 打印的 URL **逐条真发请求**实测（后端 8000，匿名 = 不带任何 cookie 与请求头）

| # | 它印的那一条 | 它印的话 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | `GET /api/students/1/prescriptions/current?as_of=2025-10-12` | 「一律要登录会话 … 直接打开一律 401」 | **401** `unauthenticated` | ✅ 不骗人 |
| 2 | `GET /api/students/1/weekly-sheet?as_of=2025-10-12` | 同上 | **401** | ✅ |
| 3 | `GET /api/alerts?limit=50` | 同上 | **401** | ✅ |
| 4 | `POST /api/alerts/{id}/handle?as_of=2025-10-12` | 同上 | **401** | ✅（⚠️ 匿名发它是安全的：`Security` 依赖先解析，故不会有副作用） |
| 5 | `GET /api/notifications?limit=50` | 同上 | **401** | ✅ |
| 6 | `GET /api/dashboard/class/1?week=6&as_of=2025-10-12` | 同上 | **401** | ✅ |
| 7 | `POST /api/pipeline/run-daily` | 同上 | **401** | ✅（⚠️ 本波**刻意没有**带会话发它：它会把周报的「预警汇总」清零，而脚本自己已经印了那一句警告） |
| 8 | `GET /api/mini-tests/normalized?semester_id=2&week=6` | 同上 | **401** | ✅ |
| 9 | `GET /api/health` | 「不登录也点得通 …（实测各 200）」+ 注释 **`# 28 张表 + 各表行数`** | **200**，而响应体逐字是 `{"status":"ok","tables":28,"students":60}` —— **一格各表行数都没有** | ⚠️ **注释骗人 → 已修** |
| 10 | `GET /api/exercises?limit=50` | 同上 + 注释 `# 动作库（不含任何学生键）` | **200 而 `{"items":[],"total":0}`** —— 演示库上 `exercise` 表**恒 0 行** | ⚠️ **例子骗人 → 已换** |
| 11 | `GET /api/percentile-snapshots?limit=50` | 同上 | **200**，24 行真数据 | ✅ 不动 |
| 12 | `http://localhost:5173`（前端） | 「另开一个终端 `cd frontend; npm run dev`」+「未登录访问任何页面都会被路由守卫送去 `/login?next=<原路径>`」 | 本波的 vite 在 **5174**（5173 被 PID 20240 占着）；`GET /` → **200 text/html**，未登录导航被守卫弹走由 smoke 第 14 步逐条实测（16 条路由「没有被守卫弹到 /login」那一拍两档全绿） | ✅ 不骗人（5173 是 vite 的**缺省**端口，脚本印的是缺省档） |

⚠️ **第 10 条的实测细节**（它不是「收紧」造成的，是数据形状）：`exercise` 与
`prescription_template` 两张表在演示库上**恒 0 行** —— 动作库住在
`backend/data/exercises.yaml`、18 套处方模板住在 `backend/data/prescription/*.yaml`，
由 `app.refdata_prescription` 在**运行时加载**、**从不入库**（`demo_bootstrap.py` 里
`exercise` / `PrescriptionTemplate` 一次都没出现，实测 `Grep` 0 命中）。
⚠️ 于是拿 `/api/exercises` 当「点得通的例子」= 念一条 URL 出来、点开是一个空列表。

**修法（`demo.ps1:257-273`，⚠️ UTF-8 + BOM + 纯 CRLF 一格未退，`Parser::ParseFile` 0 错误）**：

| | 改前 | 改后 |
|---|---|---|
| 第 9 条的注释 | `# 28 张表 + 各表行数` | `# {"status","tables","students"} 三格` + 追加两行 `Write-Host`：「它**不给各表行数**（逐表行数在上面 `[7/7]` 那一步）」 |
| 第 10 条 | `GET /api/exercises?limit=50   # 动作库（不含任何学生键）` | `GET /api/semesters?limit=50   # 学期（时间轴锚点，不含任何学生键）` —— **实测 200 且 2 行真数据** |
| 新增 | — | 两行 `Write-Host` 说清 `/api/exercises` 与 `/api/prescription-templates` 匿名各 200 而演示库上**各 0 行**、以及为什么（YAML 运行时加载、从不入库）；外加 **13 行注释**把这次逐条实测的取证记在脚本里（下一波不用再量一遍） |

### ②-5 `serve.ps1` 打印的 URL **逐条真发请求**实测（产品档 8020）

| # | 它印的那一条 | 实测 | 判定 |
|---|---|---|---|
| 1 | `前端 + API      http://127.0.0.1:8020/` | **200**，2 729 B，`text/html`，含 `<div id="app">` | ✅ |
| 2 | `存活探针        /api/health` | **200** `{"status":"ok","tables":28,"students":60}` | ✅ |
| 3 | `Swagger UI      /docs` | **200**，1 023 B，`text/html`（Swagger 的 HTML 头） | ✅ |
| 4 | `OpenAPI JSON    /openapi.json` | **200**，**417 032 B**，`application/json`，`info.title` = **厦大体育数智系统** | ✅ |
| 5 | 「含 SPA fallback：`/login`、`/s/*`、`/t/*`、`/admin/*` 的深链接一律回 `index.html`」 | 逐条实测 **8** 个深链接（`/login`、`/s/home`、`/s/mini-test`、`/t/dashboard`、`/admin`、`/admin/audit-logs`、`/admin/students/4`、`/no-such-page`）→ **各 200、各 2 729 B、各含 `<div id="app">`** | ✅ 那一句逐字成立 |

⚠️ **`serve.ps1` 一行都没改**（派单：「若全部一致，报取证即可，不要为了改而改」）。
⚠️ 对照：同一个 `GET /` 打在 **dev 档后端**（`demo.ps1` 的 8000）上是 **404**
——那是**对的**（dev 档不挂静态文件，前端由 vite 服务），而 `demo.ps1` 也**没有**印
`/` 这一条，故两个脚本各自印的 URL 都与自己那一档的事实一致。

---

## ③ D3 + D4 + D5

### ③-1 D3 · 今天 **15** 个匿名 GET 的**键级**取证（⚠️ 结论：**没有**仍然不该匿名的）

openapi 五格实测（`GET /openapi.json` 现算，不是读代码）：
**74 路径 / 102 操作 / 挂 security 84 / GET 63（匿名 15 + 挂 security 48）/ securitySchemes 3**，
非 `/api` 的路径模板 **0** 个（catch-all 没漏进 `paths`）。

15 条 = **7 个不含任何学生键的资源 × list / read-one 各一条 + `GET /api/health`**。
逐个真发（匿名、不带任何 cookie 与请求头，`limit=200`）：

| # | 路径模板 | list | read-one | 响应体的**全部**键（递归实测） | 为什么可以匿名 |
|---|---|---|---|---|---|
| 1 | `/api/semesters` | 200（2 行） | 200 | `id / name / start_date / end_date / weeks / is_current` | 时间轴锚点；`name` 是**学期名**（`2025-2026-1`） |
| 2 | `/api/course-sections` | 200（5 行） | 200 | `id / semester_id / teacher_id / name / schedule_text / grouping_mode` | 排课事实；`name` 是**班名**（`行政班01`）。⚠️ `teacher_id` 是代理键，而「id ↔ 工号 ↔ 姓名」那张表要教职身份；「谁在这个班」住在 `enrollment`（第四档） |
| 3 | `/api/fitness-test-batches` | 200（4 行） | 200 | `id / semester_id / timepoint / test_date / source / academic_year` | **批次**元数据，一条成绩都不含（成绩在 `fitness-test-results`，第四档） |
| 4 | `/api/percentile-snapshots` | 200（24 行） | 200 | `id / semester_id / computed_on / batch_id / item / sex / age_group / p10 / p20 / p25 / p50 / p75 / sample_size / source`（**14** 列） | **群体**分位数：最细的切片是「学期 × 项目 × 性别 × 年级组」，14 列里没有一格能落到一个人身上 |
| 5 | `/api/exercises` | 200（**0 行**） | **404** `not_found` | `items / total / limit / offset`（空） | 动作库是知识资产、不含任何学生键；⚠️ 表恒 0 行（§②-4） |
| 6 | `/api/prescription-templates` | 200（**0 行**） | **404** `not_found` | 同上 | 18 套模板同理 |
| 7 | `/api/class-sessions` | 200（8 行） | 200 | `id / course_section_id / session_date / period / rpe_opened / batch_id` | 课表事实 + 「快评开了没」一个布尔；⚠️ 唯一的秘密 `rpe_token` 两侧都已摘掉（读模型 + `list_exclude`），而学生端 `RpeEntry.vue` 正是要读它 |
| 8 | `/api/health` | 200 | —（无 read-one） | `status / tables / students` | 存活探针；`students: 60` 是一个**聚合计数** |

⚠️ **取证强度**：本波不是只看第一行的键，而是把 15 条的响应体**递归全部键**列了一遍
（`limit=200`），并用一组提示词（`student` / `name` / `birth` / `body_fat` / `muscle` /
`score` / `label` / `hit_rules` / `feeling` / `rpe` / `reason` / `recipient` / `password`）
逐键筛：**命中 3 个键，全是假阳性** —— `rpe_opened`（布尔）、`name`（学期名 / 班名）、
`students`（`/api/health` 的计数）。⚠️ 于是 I6 原文点名的那一整套（体成分 / 体测原始值 +
6 项得分 / 分层 `label` + `hit_rules` / `body_comp_abnormal` / 处方 / 840 条训练日志 /
240 条 RPE / 32 条预警 / 19 条站内消息 / 兴趣问卷 / `enrollments`）**今天一律要身份**。
**→ 0 处 Critical。**

### ③-2 D3 · 台账那一条改前 / 改后（⚠️ 顶回：它**不在** §1.2）

⚠️ 派单说「在 spec §1.2 的台账里找到那一条」，**实测它不在 §1.2**（§1.2 今天 18 条，
逐条 `Grep` 过，没有一条是它）。它今天的住址是 **§13.4.4**：安全收紧波把整段改写成了
「五档」，而 I6 的原文作为**引用块**留在那里（`:1364-1374`）。品牌波报告 §5.1 第 2 条
那句「已写进 spec §1.2 的 12 条已知局限」绑的是**那个时点**（§1.2 当时是 12 条）。

| | 改前（§13.4.4 的形状） | 改后 |
|---|---|---|
| 结案标注 | **没有**。节标题写着「此前是『44 匿名 + 4 仅教职』」，正文第一段写着「**安全收紧波再把那 44 个里的一批收掉**」，而 I6 那一段原文**没有**删除线、也**没有**今天的实测数 | 在那一段与 I6 原文之间插入一整块「**台账结案标注（Plan 06 Task 13 写入）**」：~~**终审 I6：「44 个匿名 GET 放行整套以 `student_id` 为键的健康档案」**~~ → **已被安全收紧波收掉**（Task 8 加第四档、Task 8b 加第五档 + 第二根轴）；品牌波台账 §5.1 第 2 条由本段结案 |
| 实测数 | 只有历史值 44 / 16（`:1454` 那张表，绑安全收紧波时点） | 今天 **15 匿名 / 48 挂 security**，openapi 五格 **74/102/84/63(15+48)/3**，catch-all **0**；15 条逐个真发的码（**13 × 200 + 2 × 404**，那两个 404 是表恒 0 行、不是收紧） |
| 键级取证 | 无 | 上面那张 8 行表（响应体的**全部**键 + 逐资源「为什么可以匿名」） |
| 历史原文 | 在（引用块） | **仍在**（本波只在它**前面**加标注，并明写「下面是安全收紧波时点的原文，刻意保留」，照 §1.2 第 13/14/17/18 条那四格的形状：新口径在前、原文在后） |

### ③-3 D4 · 迁移 4 的 `downgrade`

**改前实测**（`0ac943e0da9b_login_attempt_login_widen_to_64.py`）：`upgrade` 与 `downgrade`
都包在 `with op.batch_alter_table('login_attempt')` 里，`downgrade` 做的是
`alter_column('login', existing_type=String(64), type_=VARCHAR(32), existing_nullable=False)`；
模块 docstring 里**已经**有一段「`downgrade` 是有意义的、但它有代价」（`:66-70`），
而 **`downgrade()` 自己的 docstring 只有 `"""Downgrade schema."""` 一句**
—— 而做回滚的人看的是**函数**，不是模块头。

**改后**（⚠️ **只加注释，DDL 一个字都没改**）：`downgrade()` 的 docstring 里写明
① `batch_alter_table` 是 **SQLite 专用姿势**（`render_as_batch = True` 是为它开的）；
② 验证它的那条守卫（`test_the_column_width_migration_round_trips_and_keeps_every_row`：
灌一行 37 字符的绑定键 → `upgrade head` → `downgrade -1` → `upgrade head`，逐字比那一行）
**跑的也是 SQLite**；③ 换后端之后的两种失效（**PG** 当场失败 `value too long`；
**MySQL** 非严格模式静默截断 ⇒ 两个只在第 33 个字符之后分岔的绑定键撞成同一个串
⇒ 两个标识**共用一个限流计数器**）；④ **控制者裁定本仓不做跨后端支持**，
故这里**没有**、也**不要**加 PG / MySQL 的分支。
**spec §13.7** 加了同口径的一段（挂在「② SQLite 的 ALTER 一律要批处理」那一条之后，
并明写 Task 11 登记的待清扫第 3 条**由此结案**）。

**复核**：`py_compile` 退出码 0；`tests/db/test_migration_chain.py` +
`test_migration_baseline.py` + `tests/architecture/test_docstring_references.py` →
**34 passed**（⚠️ 新 docstring 里那两条 `:func:` 引用都指得到真名）；
**迁移链仍是 4 单头**（本波没动 schema）。

### ③-4 D5 · addon warning vs `prescription.status='needs_review'`（**实测两者的触发条件**）

| | 「addon 训练量未指定」那条 warning | `status = 'needs_review'` |
|---|---|---|
| 谁产出 | `app/domain/prescription/safety.py:333-336`：③ 那一段每**追加**一个 addon block 就追加一条 | 同一模块 ④⑤：`substitute is None`（`:352-354`）⇒ `SafetyOutcome.needs_review = True` |
| 触发条件 | 模板上**有** `addons`（体脂率异常 / 肌肉量 < P10 那两档会追加能量消耗模块） | 模板里有 `impact_level: high` 的动作、**且** BMI > 30 或肌肉量 < P10 命中了换动作那一档、**且** `exercise_equivalence.yaml` 里查不到低冲击替身 |
| 落库在哪一列 | **一列都不落**：`prescription_stage.py:1304-1310` 把 `safety.warnings` 逐条 `logger.warning` 打出来就完了。⚠️ **实测**：`prescription` 的 **16** 列里**没有** `warnings` 这一列，四个 JSON 列（`assembly_snapshot` / `safety_substitutions` / `training_package` / `trigger_reasons`）里也**搜不到**那句原文 | `prescription.status`（经 `active_or_needs_review`，**`needs_review` 优先于 `active`**） |
| 演示库实测 | `assembly_snapshot.safety_triggers` 只有两种取值：**42 行 `[]`** + **18 行 `["body_fat_abnormal"]`**；那 18 行正是 `training_package` 里含 `energy_expenditure_plus*` 的 **18** 张 ⇒ **每生成一批处方，屏幕上就是 18 条这一族的 warning** | **0** 张（60 张处方**全部** `active`）；`safety_substitutions` 非空的行 **0** |
| ⚠️ 「0 张」的原因 | — | **不是**「映射表里的替身够用」：60 行**全部**带 `safety_skipped = ["muscle_p10_missing"]`（另 5 行 `bmi_missing`、3 行 `muscle_mass_missing`），故「高冲击 → 换低冲击」那一支在演示数据上**一次都没被触发过**。那一格由 `tests/pipeline/test_prescription_stage.py::test_needs_review_when_no_equivalent_exercise` 用**合成输入**钉住，不靠演示数据 |

**写进了哪一节：§7.4**（选它的理由：那一节正是 `safety.py` 的规格住址，
而 `needs_review` 的定义就在**上一句**；§13.1 只加一行指针，不复述第二份）。
⚠️ §7.4 改前那一句逐字是「安全规则命中但映射表找不到等价动作时…**生成 `warning` 级日志，
处方状态置 `needs_review`**」—— 它对**那一个**触发条件是真的，而读者会把
「`warning` 级日志」与「`needs_review`」读成一件事，故本波在它下面加了一整块
（含上面那张表 + 「为什么这一格值得单写一节」+ 「本仓不改那条日志前缀」的裁定）。

⚠️ **顶回派单的第 ③ 点**：`demo.ps1` `[7/7]` 那一句打印**本身没有撒谎** ——
`demo_bootstrap.py:554-558` 逐字写着「它只由『安全规则命中却找不到等价动作』置位；
上面那批…warning 日志**不**改这一列」，两件事**已经区分开了**。
⚠️ 真正会让人误读的是**另一处**：`prescription_stage.py:1308-1309`（与 `:1512-1513`
的手工重生成那一支）把 `safety.warnings` 里**每一条**都套上前缀
「学生 %s 的处方（模板 %s）**需要人工复核**：%s」，而「需要人工复核」正是
`needs_review` 那一档在教师端的措辞。**裁定：不改那一句日志**
（它是 §7.4「不静默跳过」那一格的既有实现，改措辞要连 `tests/pipeline/` 的 caplog
断言一起动、收益只是修辞），把误读风险**逐字写进 §7.4**；
`demo_bootstrap.py` 那一句只把末尾「两者的差别已登记为待清扫」改成
「**已写进 spec §7.4**（Plan 06 Task 13 结案）」（实测重跑 `demo.ps1`，那一行照常打印）。

---

## ④ D6 · `/s/mini-test` 的静态 needle → **真取证**

### ④-1 那一页今天显示哪几个数、各自的 API 来源（先实测）

`MiniTest.vue` 的第 02 块（`SectionHead :index="2" label="PERCENTILE"`）对
`mySections` 的**每一个班**渲染 **3** 个 `StatBlock`：

| 页面上的 label | 取值 | API 来源 | 小数位 |
|---|---|---|---|
| 小测综合分 | `row.self?.composite` | **窄端点** `GET /api/mini-tests/normalized/me?semester_id&week`（`NormalizedSelfSectionRead`） | **2** |
| 折返班内百分位 | `row.entry.shuttle_score` | **班级端点** `GET /api/mini-tests/normalized?semester_id&week` 里 `entries[]` 中 `student_id === 我` 的那一行 | **1** |
| 深蹲得分 | `row.self?.squat_score` | 同窄端点 | **1** |

⚠️ 查询参数由页面自己推：`GET /api/students/{id}/home?as_of` 的 `semester_id` + `week`
（`MiniTest.vue:104-123`）；「哪几个班」由 `mySections` 过滤（只留 `entries` 里
有我那一行的班，`:233-257`）；`null` 那一档 `StatBlock` 渲染 `UNKNOWN`（`—`，U+2014）、
**不是** 0（`StatBlock.vue:62-65` + `present.ts:52`）。

### ④-2 真取证怎么做的（**照 Task 10 给教师页那一格的同一姿势**）

* **期望侧**（HTTP）：在 `ROUTES` 之前用**学生 jar** 依次打
  `/api/students/4/home?as_of=2025-10-12` → `/api/mini-tests/normalized?…` →
  `/api/mini-tests/normalized/me?…`，然后**逐字复刻** `mySections` 那一次过滤与
  `StatBlock` 的 `toFixed(decimals)` / `null → '—'` 规则，算出三组期望串。
* **被测侧**（CDP）：复用既有的 `STAT_PROBE`（抓 `.stat` 下的
  `.stat__label` / `.stat__value` 两格文本），按 label 取值后与期望侧
  `JSON.stringify` 逐字比。⚠️ **两侧不同源**（一侧是 DOM 文本、一侧是响应体），
  故它挡得住「Vue 把 `null` 渲染成了 0」「读错了字段」「前端自己算了一遍」三档。
* **闸门**：给那一条路由**加了第三条 needle** `折返班内百分位` —— 那个 label 住在
  `mySections` 的循环里，两次异步请求没回来它就是空的；`dumpRoute` 是**轮询到全部
  needle 都出现才返回**的，故少了它，三拍真取证可能在 `Promise.all` 落地之前就把 DOM
  抓走（= 假红）。⚠️ 与教师页那一格的 `小测综合分` 是同一条姿势。
* ⚠️ **没有放宽任何既有判据**（硬规矩 #92）：改前那两条静态 needle
  （`二次小测` / `30 秒深蹲`）**逐字保留**，本波只是**加**。

### ④-3 断言数与两档结果

| 档 | 改前 | 改后 | 差 | 实测 |
|---|---|---|---|---|
| dev（后端 8000 + vite **5174**） | **632** | **637** | **+5** = 小测页 3 拍 + §D7 2 拍 | 18/18 步 · **637 绿 / 0 红** · 退出码 **0** · **32.1 s** |
| 产品档（`serve.ps1 -Port 8020 -SkipBuild`，同源） | **633** | **637** | **+4** = 小测页 3 拍 + §D7 **1** 拍（新鲜度那一拍在产品档**跳过**） | 18/18 步 · **637 绿 / 0 红** · 退出码 **0** · **30.1 s** |

⚠️ **两档的断言数从此相同**：改前产品档比 dev 档多 1 条（§C3 在产品档是 8 拍、
dev 档 7 拍），本波 dev 档比产品档多 1 条（§D7 的新鲜度拍只在 dev 档跑），两个 ±1 抵掉。
算术：dev `632 + 3 + 2 = 637`、产品档 `633 + 3 + 1 = 637`。

**真取证的实测输出**（两档逐字相同）：

```
小测页期望值（#4，semester_id=2&week=6）：2 个班 → 综合分 ["66.67","63.75"]、折返 ["98.3","92.5"]、深蹲 ["35.0","35.0"]
✓ s-mini-test：「小测综合分」… 逐字相等   →  DOM=["66.67","63.75"] API=["66.67","63.75"]
✓ s-mini-test：「折返班内百分位」读的是**班级端点**里我那一行  →  DOM=["98.3","92.5"] API=["98.3","92.5"]
✓ s-mini-test：「深蹲得分」… `null` 那一档渲染的是「—」不是 0  →  DOM=["35.0","35.0"] API=["35.0","35.0"]
```

**定点变异**（与 §D7 的变异同一次跑，两处同时）：把期望侧综合分的小数位由 **2 改成 1**
⇒ 那一拍**红**，报文逐字是 `DOM=["66.67","63.75"] API=["66.7","63.8"]`
（⚠️ 即「前端把数算错了 / 读错了字段」这一档今天会响）。

---

## ⑤ D7 + D8 · 探针的纪律收口

### ⑤-1 D7 · `smoke.mjs` 文件头改前 / 改后

| | 改前（逐字） | 改后 |
|---|---|---|
| 「怎么跑」的标题 | `怎么跑` | `怎么跑（⚠️ 两个前置条件都是**硬要求**：少一个就会读到假红）` |
| ② 那一行 | `# ② 起前端（第 14 步要它）` | `# ② 起前端（第 14 步要它）—— ⚠️ **必须是本波重起的那一个**，理由见下面那一节` |
| 前置条件 ② | **只有**「跑之前先重跑 `demo.ps1`」（在「它是**一次性**的」那一节里） | 新增一整节「⚠️ 前置条件 ②：跑之前**重起一次 `npm run dev`**（Plan 06 Task 13 / D7 写成硬要求）」：① 第 14 步对 dev server 新鲜度**敏感**而它此前**自己不检查**（品牌波 §5.1 第 7 条）；② **失效形态很坏**（品牌波实测过一次假红，4 条红全是「文本内容重叠」，读起来像「本波把布局改坏了」）；③ **为什么**：HMR 对「模块图」那一类改动经常要整页重载才干净（`router/index.ts` / `main.ts` / `stores/*.ts` **不是**「换一个组件的渲染函数」那一档，热替换会把新旧两份模块**同时**留在图里），而第 14 步量的是**渲染后的真值**；④ 纪律是 **Ctrl-C 掉那个 vite 再起一次**（刷新页面不够）；⑤ **产品档不受这一格影响** + `serve.ps1` 自己判新鲜度的逐字口径 |

### ⑤-2 D7 · 「便宜的真检查」——**做了**（⚠️ 而首版的判据是错的，两档各跑一次才发现）

* **判据两侧不同源**：期望侧现场从磁盘读 `frontend/src/router/index.ts` 的
  全部 `path: '…'` 字面量（正则 `/path:\s*'([^']+)'/g`，实测切出 **21** 条），
  被测侧 `fetch(WEB + '/src/router/index.ts')` 拿 dev server **此刻服务的那一份**模块文本，
  逐个断「磁盘上有的，服务出来的那份里也在」；缺一条就红，报错直接说
  「那个 vite 是陈旧的 → **重起 `npm run dev`」」。
* ⚠️ **它不写死一个标记串**：写死就等于「每次跑之前要记得改它」= 又一个待清扫项
  （派单点名的那个便宜做法，实测**这一版更便宜也更不容易假红**）。
* ⚠️ **反空转**：另加一拍断「从磁盘上切得出 ≥ 20 条路径字面量」，
  否则「正则漂了 / 文件搬走了」与「dev server 是新鲜的」在输出上同形。
* ⚠️⚠️ **首版用状态码判「这是哪一档」，是错的**（两档各跑一次才发现，如实记）：
  **产品档的 SPA fallback 对 `/src/router/index.ts` 也回 200**（回的是 `index.html`），
  而 dev 档对一个不存在的路径同样回 **200 `text/html`**。两档唯一的差别在
  **content-type**：vite 把 `/src/**.ts` 服务成 `text/javascript`。
  ⚠️ 用状态码判的话本拍在产品档上会**假红**（拿 `index.html` 去比路由字面量，21 条全「缺」）。
  改后产品档实测输出：`§D7 http://127.0.0.1:8020/src/router/index.ts 的 content-type 是
  "text/html; charset=utf-8"（不是 JS 模块）⇒ 这是**产品档**…本拍跳过`。
* **定点变异**：往期望侧的路径清单里塞一个磁盘上不存在的路径 `__pe_stale_probe__`
  ⇒ 那一拍**红**，报文 `缺 1 条：["__pe_stale_probe__"]`。

### ⑤-3 D7③ · `serve.ps1` 的新鲜度判据**今天还在**（复核取证）

`scripts/serve.ps1:148-190`（② 那一步）逐格复核：
① `dist\index.html` 不在 ⇒ 要构建（`-SkipBuild` 时直接 `throw`）；
② `-SkipBuild` ⇒ 不判新鲜度、并打印构建戳；
③ 否则源面 = `frontend/src/**` + **5 个配置文件**（`index.html` / `package.json` /
`vite.config.ts` / `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json` —— 实测 6 个
`Join-Path`，其中 1 个是目录），取**最新 mtime** 与 `dist\index.html` 的
`LastWriteTimeUtc` 比，源面新 ⇒ `npm run build`；
④ **反空转**（`:176-178`）：`if ($Sources.Count -lt 20) { throw … }` —— 源面被搬空时
`Measure-Object -Maximum` 会安静地给 `$null`，而 `$null -gt $Stamp` 为假 ⇒
「dist 是新的」会**假绿**。⚠️ 本波实测那次跑（`-SkipBuild`）打印的是
`源面 … 个文件` 那一支的替代行：`-SkipBuild：不判新鲜度，直接用现有的 dist（构建戳 10/15/2026 00:30:37）`。

### ⑤-4 D8 · 第 17 步的前置条件与耗时（文件头新增一张表）

| 拍 | 要什么起着 | 墙钟（本机 2026-10-15 实测 / Task 11 那次并列） |
|---|---|---|
| ① | **PowerShell + Python**（spawn 一次 `demo.ps1 -DryRun`；库与 CSV 都落在 `$env:TEMP`、跑完自己删） | **5.2 s**（Task 11 量到约 15 s） |
| ②③④⑥⑧ | 只要文件系统（读源码） | < 1 s |
| ⑤ | **PowerShell + Python**（spawn 一次 `serve.ps1 -SkipBuild`，⚠️ 端口是**先用一个 `net.Server` 占住**再交给 `-Port`，于是它停在 ③d 的端口预检、一个 uvicorn 都不起） | **2.7 s**（Task 11 量到 3–5 s） |
| ⑦ | **后端起着**（③④ 两拍打真端点：`limit=200` 与 `limit=1` 各一遍） | 约 1 s |
| （第 15 步） | 两个 node 脚本 | `check-tokens` **0.1 s** + `check-dist` **0.1 s**（⚠️ `dist` 已在；否则 `check-dist` 会自己跑一次 `npm run build`） |

⚠️⚠️ **顶回派单给的那个比例**：派单要求在 spec 里记「smoke 的墙钟里**约 2/3** 花在
结构面守卫上」。本机实测那两次 spawn 是 **5.2 + 2.7 = 7.9 s**，全跑 **32.1 s** ⇒
**约 1/4**；Task 11 在同一格上量到的是 **18–20 s / ~30 s ≈ 一半**。
⚠️ 于是这一格的**绝对值随机器漂**（磁盘缓存 / 负载），spec 与文件头都**只钉口径不钉数**
（比例 = 那两次 spawn 的墙钟 ÷ 全跑墙钟，要报就当场 `Measure-Command`）。
⚠️ **控制者裁定「不拆成单独的 npm script」照办**，取舍的账写在 **§13.11.4**
（「结构面守卫吃掉 smoke 墙钟的约 1/4（Task 11 那一次是约 1/2），这是有意的取舍」）。
⚠️ 顺手修掉一句**已经过期**的注释：第 17 步那一段改前逐字写着「⑤ 那一拍…
**用一个认不出的 `PE_ENV`** 让它在起子进程之前就 throw」，而代码今天用的是
「先占住一个端口」—— ⑤ 自己的注释里写明 PE_ENV 那条路**踩过坑**
（`serve.ps1` 的 ③a 那一次 `python -c` 会更早炸掉、脚本停在强制清**之前**、
探针红在自己身上）。已改成与代码一致。

---

## ⑥ D9-① · `$env:TEMP` 上陈旧 `pe_*` 探针的统一清理

### ⑥-1 删前清点（**按名字族汇总**，不逐个列 125 行）

顶层 `pe_*` 条目 **125** 个（**97** 个目录 + **28** 个文件）/ **21** 个名字族：

| 名字族 | 个数 | | 名字族 | 个数 |
|---|---|---|---|---|
| `pe_edge_*` | **34** | | `pe_fr1_*` | 3 |
| `pe_demo_*` | **20** | | `pe_fr2_*` | 3 |
| `pe_dom_*` | **17** | | `pe_replay_*` | 3 |
| `pe_rr_*` | **14** | | `pe_t1_*` | 2 |
| `pe_t5_*` | 6 | | `pe_verify_*` | 2 |
| `pe_t4_*` | 5 | | `pe_ab_*` / `pe_csv_*` / `pe_fe_*` / `pe_http_*` | 各 1 |
| `pe_idx_*` | 4 | | `pe_p2_*` / `pe_rv_*` / `pe_sweep_*` | 各 1 |
| `pe_task3_*` | 4 | | `pe_vite.txt` | 1 |

⚠️ 派单说「约 122 个」，本波开工时量到 **123**，而清理那一刻是 **125**
—— 差的那 2 个是本波自己跑 `demo.ps1` 时它建的 `pe_demo_csv_<pid>`
（**它跑完不会自己删**，这一格已写进 §12 那段纪律里）。

### ⑥-2 删除与复验

* ⚠️ **删之前先确认没有进程持有它们**：先停掉本波起的两个服务
  （`demo.ps1` 的 8000 与 `serve.ps1` 的 8020，`Get-NetTCPConnection` 实测两个端口
  占用数都归 **0**，`Get-Process python` 实测 **0** 个），再逐个删。
* **删除尝试 125 个 / 失败 0 处**（`shutil.rmtree` + `os.remove`，异常逐个捕获并打印；
  ⚠️ 前几波踩过的「tee 日志被进程占用 ⇒ `PermissionError`」这一次**没有**出现）。
* **删后复验**：`os.listdir($env:TEMP)` 里以 `pe_` 开头的条目 **0** 个；
  并对删前那 125 个名字逐个 `os.path.exists` → **全 False**（残留清单 `[]`）。
* ⚠️ **只删 `pe_*`**：本波自己的 `$env:TEMP\p06t13\` **不以 `pe_` 开头**，
  故它天然不在删除面里（复验打印 `p06t13 还在吗 = True`）；
  非 `pe_*` 的任何东西**一个都没碰**。
* **纪律写进 §12**（选 §12 而不是 §13 的理由：探针是**测试工件**，而 §12 是本仓
  测试纪律的住址 —— 它已经带着一条关于契约测试的勘误）：
  「① 住址一律是 `$env:TEMP\<波次标识>\` 的一个**子目录**（`p06t9`…`p06t13`），
  不要往根上撒 `pe_*`；② 跑完**删那一个子目录并复验**，删之前先确认没有进程持有它」，
  并逐字记了本次清理的实测数与「`pe_demo_csv_*` 是 `demo.ps1` 自己建的、
  服务在跑时被持有 ⇒ 清理排在停服务之后」那一格。

---

## ⑦ D9-② + D9-③ · Task 11 与 Task 12 那两批台账的**逐条裁定**

⚠️⚠️ **顶回派单的归属**：派单的「D9-② Task 11 新登记 6 条」那张表里那 6 条
（UA / CSV 长度 / `ensure_fits` 优先级 / unused-import / `width.py:161` / `_HISTORICAL`）
**逐字住在 `task-12-report.md` §⑦ 的「待清扫（6 条，本波新登记）」**；
而派单的「D9-③ Task 12 新登记 6 条」点名的那一格（`path` 截断后撞成同一格）
**逐字住在 `task-12-report.md` §⑦ 的「关切（2 条）」第 2 条**。
⚠️ 处置：**不按标签、按内容全覆盖** —— Task 11 的 6 条 + Task 12 的 6 条 + Task 12 的
2 条关切 = **14 条**，逐条给裁定。

| 来源 | 条 | 裁定 | 落在哪个文件哪一节 / 理由 |
|---|---|---|---|
| T11 #1 | `audit_log.path` 是 `String(256)` 而存客户端可控原文、**没有**宽度守卫 | **已被前波收掉** | Task 12 / C1 的 `truncate` 那一档 + `tests/api/test_column_widths.py` 的分类账（`_REQUEST_METADATA` 第一行就是它）；本波复核守卫**仍在**（16 passed） |
| T11 #2 | `audit_log.target` 是 `String(64)`，特例端点的取法要再核 | **已被前波收掉** | 同上（`_REQUEST_METADATA` 第二行）；端到端那一拍实测 `PATCH /api/students/<400 字符>` 落库 **64** 且以 `…[cut]` 结尾（§13.13.1） |
| T11 #3 | 迁移 4 的 `downgrade` 在 PG/MySQL 上不安全 | **做**（D4） | 迁移 4 的 `downgrade()` docstring + spec §13.7；⚠️ 只加注释、DDL 一个字没改 |
| T11 #4 | `gen:api` 写出的 `schema.d.ts` 是 LF | **划掉**（派单给了口子） | 实测：`gen:api`（离线，**2.34 s**）写出 **517 231 B / 10 402 个裸 LF**，而 **`git diff` 为空**（blob 本来就是 LF、`autocrlf` 归一）⇒ **就入库而言不需要还原**；残余只在 `git ls-files --eol` 的 `w/crlf → w/lf`。本波仍还原成 CRLF（**527 633 B / 0 裸 LF**）。→ §15 的 **F3**（划掉并记实测） |
| T11 #5 | 第 17 步「不需要后端起着」只对 ①–⑥ 成立 | **做**（D8①） | `smoke.mjs` 文件头新增那张逐拍表 + 第 17 步那一段注释同步（含修掉「认不出的 `PE_ENV`」那一句过期话） |
| T11 #6 | 第 17 步 ⑤ 会 spawn powershell + 两次 python，约 18–20 s = smoke 的一半 | **做**（D8②，⚠️ **顶回那个比例**） | 本机实测 **7.9 s / 32.1 s ≈ 1/4**；spec §13.11.4 记「约 1/4（Task 11 那次约 1/2）」+「不拆成单独 npm script」的取舍 |
| T12 #1 | UA 要不要进审计 | **不做** | spec **§13.9** 新增「边界的另一半」一节（UA 不存 / `ip` 只在 `login_attempt` 上且只是事后线索、不解析 XFF / 其余请求头不存），⚠️ 与该节既有的「不记请求体是**结构性质**」不冲突（同一句话的两半）；并指名那两条既有守卫。§13.13.1 那句「已登记待清扫」按结案姿势改成「裁定不做 → 见 §13.9」 |
| T12 #2 | CSV 摄取路径字段长度无校验 | **延后到 Plan 07** | §15 的 **C3**（收口点应是 `cleaning_log` **剔除**而不是 422 —— 数据管道的既有形状，交付前不动） |
| T12 #3 | `ensure_fits` 排在 `repo.upsert` 之前 ⇒「超宽 + 撞键」得 422 而不是 409 | **做**（加守卫） | 新守卫 `test_an_overlong_field_beats_a_natural_key_conflict_because_ensure_fits_runs_first`（三拍含反空转）；spec §13.13.1 记裁定与理由 |
| T12 #4 | unused-import 守卫 | **延后** | §15 的 **F1**（要先定「什么时候允许一个只被散文引用的 import」—— 而 §13.13.4 那条守卫**要求**引用指得到真名，故「为了散文而 import」在本仓是合法形状，朴素守卫会把它判成违规） |
| T12 #5 | `app/db/width.py:161` 极窄列那一支今天不可达 | **做**（**保留 + 加守卫**） | 新守卫 `test_the_truncation_owner_stays_bounded_on_a_column_narrower_than_the_marker`（合成宽度 1…6）。⚠️ **实测理由**：定点变异把那一支删掉之后，`width=1` 那一档走 `value[:-5] + 标记`，而 Python 的**负数切片**是「从尾巴往前留」⇒ 返回 **501** 个字符（一个比声明宽度长 500 倍的串），正好把 `app/db/width` 存在的全部理由反过来 ⇒ 它**不是**死代码，是**失效方向的最后一道** |
| T12 #6 | `_HISTORICAL` 那 6 个名字将来若被建回来要跟着删 | **写进台账** | §15 的 **F2**。⚠️ **反腐坏守卫今天怎么写的**（取证）：`tests/architecture/test_docstring_references.py:324-357` 第 ② 拍**两半** —— 「清单里没人再提的名字 ⇒ 断言失败并说『删掉它们』」+「清单里的名字**又存在了**（有人把那个测试建回来）⇒ 断言失败并说『从清单里删掉』」，外加 `assert len(_HISTORICAL) == 6`。故**不需要人记着** |
| T12 关切 1 | `ensure_fits` 是一次逐列 Python 循环（9 个可写资源的 POST/PATCH 各多一次） | **延后** | §15 的 **E2**（含实测耗时对比与「要省就把宽度表缓存成常驻 dict」的做法） |
| T12 关切 2 | `path` 截断后「只在第 257 字符之后不同的两条路径」会撞成同一格 | **做**（加守卫钉住那个**前提**） | 新守卫 `test_the_longest_route_template_sits_well_inside_the_audit_path_width`：最长路径模板 **× 2 < `audit_log.path` 的声明宽度**。⚠️ **实测最长模板是 56 字符**（`/api/students/{student_id}/training-logs/completion-rate`）而**不是** Task 12 报告写的 47；`String(256)` 的一半是 128 ⇒ 余量 **2.3 倍**，结论不变。⚠️ **而那个数漂了正是加守卫的理由**（只写在报告里的实测值会漂）。spec §13.13.1 逐字记了这一格 |

### ⑦-1 那 3 条新守卫的**定点变异**（三处同时，一次 pytest）

| 变异 | 期望红的那一条 | 实测报文（逐字） |
|---|---|---|
| **M1** `app/api/crud.py`：`create_row` 去掉 `ensure_fits` | T12 #3 那条 | `FAILED …ensure_fits_runs_first - AssertionError: {"error":{"code":"integrity_conflict",…}}` / `assert 409 == 422` |
| **M2** `app/db/width.py`：删掉 `if keep <= 0: return OVERLONG_SUFFIX[:width]` 那一支 | T12 #5 那条 | `assert ('zzz…zzz…[cut]' is not None and **501 <= 1**)` ← 一个比声明宽度长 500 倍的串 |
| **M3** `app/db/models/audit.py`：`String(256)` → `String(64)` | T12 关切 2 那条 | `assert (56 * 2) < 64` + 「最长路径模板 `/api/students/{student_id}/training-logs/completion-rate` 是 56 字符…」 |

**3 failed（正是要的 3 条）→ 逐个还原 → 复跑 `tests/api/test_column_widths.py` = 16 passed**。
⚠️ `tests/api/test_column_widths.py` 从 **13** 条长到 **16** 条；
`tests/architecture/test_docstring_references.py` 一并复核绿（新 docstring 里的
`:func:` / `:data:` 引用都指得到真名）。

---

## ⑧ D9-④ + D9-⑤ · 延后台账与 Plan 06 结案

### ⑧-1 §15 扩到几条

**改前**：§15 是 **18 行**（「第二批：激励与研究支撑」2 条 + 「第三批：生产化与推广」
5 条 + 一段依赖关系），**没有**任何「刻意没做的收尾」。
**改后**：新增一整块「**⚠️ Plan 06 结案时点的「延后台账」**」，**16 条**，分 6 组
（体例照 §15 既有的「加粗小标题 + 项目符号」，**不另起一套**），每条一律给
「**是什么** → **为什么今天不做** → **怎么做**（+ 指针）」三格：

| 组 | 条 |
|---|---|
| **A. 前端结构债** | A1 `session → identity` 兼容桥（实测 **17 个文件**引用 `useIdentityStore`、其中 **10** 个是页面组件；品牌波口径「13 个页面」）／A2 `moss` 命名债（**35 处 / 13 个文件**，唯一所有者的注释今天在 `tokens.css:139-141`）／A3 `SessionIdentity` 的第二个所有者 |
| **B. 缺的运维作业** | B1 读审计表（→ §13.9）／B2 `audit_log` 保留归档／B3 过期行清理（`login_attempt` + `user_session` 合成一个）／B4 反代级全局限速（→ §1.2 第 16 条）／B5 跨站部署那五件事的 ③④⑤ |
| **C. schema 与数据形状** | C1 `progress_board` 拆子表（拆完自动落进那条遍历守卫）／C2 「谁被锁过」查不出来（= 迁移 4→5）／C3 CSV 摄取路径的字段长度 |
| **D. 需产品负责人裁定** | D1 UI 上印不印后端模块路径 / 私有名（实测 **15 处 / 10 个页面文件**；⚠️ **边界写清了**：API 响应体里不许有内部标识符**已钉死**，而页面散文里的「算式住在 `app/domain/report.py`」是本仓的**可解释性惯例**） |
| **E. 性能** | E1 判 admin 多查一次 `teacher` 表／E2 `ensure_fits` 的逐列循环 |
| **F. 守卫与惯例** | F1 unused-import 守卫／F2 `_HISTORICAL` 那 6 个名字（已有反腐坏守卫）／~~F3 `gen:api` 的行尾~~ → **实测后划掉** |

⚠️ 派单列的是 **14** 项，本波写进去 **16** 条：多出的 2 条是 Task 12 的**关切 1**
（`ensure_fits` 的性能，→ E2）与 Task 12 的**待清扫 6**（`_HISTORICAL`，→ F2）
—— 派单把后者放在 D9-②③ 的裁定里、而它的**落账处**只能是 §15，故一并写全。

### ⑧-2 结案节住哪儿、体例照谁

**先 `Grep` 了前几个计划怎么在 spec 里结案**（`Grep "结案" Document/*.md`）：
**没有一个计划单开过结案节** —— Plan 03 的结案是「§13 整体改写」（`:1220`
「本节自 Plan 03 结案（2026-10-08）起整体改写」）+ 账本 `progress.md` 的
「Plan 03 的最终账面」那一节；Plan 04 / 05A / 05B 各自把结案写成对应章节开头那一句。
**本波的选择**：在 **§13 末尾新增 §13.14**，体例照 §13.12 / §13.13
（「Task N：一句话」+ 分小节）。**两条理由**（逐字写在那一节开头的 blockquote 里）：
① Plan 06 的每一个 Task 已经在 §13.4.x 与 §13.7–§13.13 里各自落了一节，
唯独「整计划的那本账」没有住址；② 计划 §10 那 5 条验收口径需要一个**逐格对账**的地方，
而对账表只住在实现者报告里就会随报告一起过期（报告**绑时点**、spec 是**活文档**）。
⚠️ 六个小节：**13.14.1** 本波 D1–D9 一览（11 行表）／**13.14.2** Plan 06 的 **13** 个
波次一览（commit 区间 + 一句话 + 报告文件名）／**13.14.3** 计划 §10 那 **5** 条的
**逐格对账**／**13.14.4** 数字总账／**13.14.5** §1.2 台账的结案标注复核（8 行表）／
**13.14.6** 延后台账的指针（→ §15）。

### ⑧-3 计划 §10 那 **5** 条验收口径的逐格对账（⚠️ 计划文档**一个字都没改**）

| # | 计划原文（逐字） | 今天实测 | 达标 | 取证住址 |
|---|---|---|---|---|
| 1 | 「后端 passed 数只增不减；`app/domain/` 覆盖率四格 **1268/0/376/0/100%** 不许退（新增模块自己的覆盖率单独报）」 | **1564 passed + 1 skipped**（带 `--cov`，291.41 s）/ **1565 passed**（不带，172.69 s）；开工 **1340**。覆盖率四格 **1268 / 0 / 376 / 0 / 100%**（一格未退） | ✅ | §⑨-3 |
| 2 | 「`smoke.mjs` 在**产品档**（Task 7 那个档）下 18 步全绿、退出码 0」 | 产品档 **18/18 · 637 · 0 红 · 退出码 0 · 30.1 s**；dev 档同样 **18/18 · 637 · 0 · 32.1 s**。⚠️ 断言数从计划时点的 **499** 长到 **637** | ✅ | §④-3 / §⑨-3 |
| 3 | 「四个数据指纹 + 18 个模板指纹逐字不变；`backend/pe.db` 不存在；`backend/data/seed/` 0 文件」 | 四个数据指纹**逐字对**（`D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7`，现算 vs 测试常量）；**18** 个模板指纹**不符 0 条**、磁盘上 `prescription/` 下 `.yaml` **18** 个；`pe.db` **False**；`data/seed/` **0** 文件 | ✅ | §⑨-4 |
| 4 | 「**新增依赖只有 alembic 一个**；前端新增依赖 0」 | 后端 `dependencies` **7 + `alembic==1.20.0`** + `dev` **3**；前端 `dependencies` **3** / `devDependencies` **7**；`tests/test_dependencies.py` **一字不红**（在 1565 里）。⚠️ 本波新增依赖 **0** | ✅ | §⑨-3 |
| 5 | 「每个 Task 一份预检探针（Ruling 1 的强度），变异测试在 Task 3 / Task 8 要求（其余 Task 若实现者认为必要可自行加）」 | ⚠️ **部分达标，如实记**：13 个波次各有**一份实现者报告**（本波之后账本目录下 **11** 份），而「预检探针」那一份**没有单独入库** —— Plan 06 各波的探针一律落在 `$env:TEMP\<波次标识>\` 并在收尾删净（§12 那条纪律），故今天的可复核面是**报告里的实测数字**、不是探针文件本身（Plans 01–03 的账本目录下确实有 `t*_probes/` 入库，那一批的口径不同）。⚠️ 变异测试**超额**：计划只在 Task 3 / 8 要求，实测 Task 3（7 处）/ 8 / 8b / 9 / 10 / 11 / 12（7 处）/ **13（5 处：smoke 2 + 后端 3）** 都做了 | ⚠️ 部分 | §12 + 各波报告 |

⚠️ **计划时点的预期 vs 今天**（派单要求如实写、**不改计划文档**）：
断言数 **499 → 637**、路由 **15 → 16**、迁移链 **0 → 4**、表数 **26 → 28**、
openapi **71/99/81/60(15+45)/3 → 74/102/84/63(15+48)/3**、
后端 collected **1340 → 1565**。⚠️ 计划 §9 逐字把「**全分支终审** + 推送 `origin/main`」
排进 Task 9，而它**没有**在 Task 9 里做（Task 9 做的是 schema 级摘列 + 审计页）；
控制者把它单独排成**下一波 Task 14** —— 这一格已在 §13.14.2 的表末与 `progress.md`
的「Task 14」那一节如实登记。

### ⑧-4 数字总账（关键几格；完整表在 spec §13.14.4）

| 格 | 开工 | 结案 | 差 |
|---|---|---|---|
| 后端 collected | **1340** | **1565** | **+225** |
| `app/domain/` 覆盖率四格 | 1268/0/376/0/100% | **同** | 一格未动 |
| 表数（health 口径） | **26** | **28** | +2（`login_attempt` / `audit_log`）；⚠️ `sqlite_master` 里另有 `alembic_version` ⇒ 数出来是 **29** |
| 迁移链 | **0** | **4 单头** | +4 |
| 前端路由 | 15 / 19 | **16 / 20** | +1 / +1 |
| smoke 断言 | 499 | **637 / 637** | +138 |
| openapi 五格 | 71/99/81/60(15+45)/3 | **74/102/84/63(15+48)/3** | +3/+3/+3/+3（**匿名 GET 0**）/0 |
| 新增依赖 | — | 后端 **+1**（alembic）、前端 **+0** | — |
| 顶回 | 累计 185 处 / 16 次 Critical | **+10 处 / 0 次 Critical** ⇒ **195 / 16** | — |

⚠️ **顶回派单给的两个数**：① 「计划开工时的 **1426**」—— 实测开工是 **1340**
（`task-1-2-report.md:539`），**1426** 是 **Task 3/4 结案**那个时点
（`task-3-4-report.md:595`）；② 「未定型响应 **26**」—— 实测是**两个不同的口径**：
**未定型响应 24**（smoke 第 12 步 ⑤：23 个 list + `/api/health`；本波亲跑 openapi
**现算 = 24**，逐个列在 §⑨-3）与 `test_prescription_api.py` 的 `expected` **26**
（那是**特例端点清单**，`assert len(expected) == 26`，与「挂 security **84** =
26 特例 + 26 CRUD 写入 + 6 仅教职读 + 26 学生键读」那个算式同源）。

### ⑧-5 `progress.md` 续了哪几波

⚠️ **顶回**：派单说「账本 `progress.md` 更新（先 `Grep` 它今天的形状，不要整份读；
三份 `progress.md` 都很大）…若它已经记到某一波，从那儿续」。
**实测 Plan 06 根本没有 `progress.md`**：全仓只有 **3** 份（Plans 01 / 02 / 03 各一份），
而 Plans 04 / 05A / 05B / 品牌波 / 安全收紧波 / 收尾波 / Plan 06 **都没有**
—— 那几波的账本形状是「一波一份实现者报告」。
**处置**：**新建** `.superpowers/sdd/2026-10-13-实施计划06-产品级硬化/progress.md`
（**16 671 B / 233 行 / LF / 无 BOM**，与账本目录里那 10 份报告同一口径：
`.superpowers/** -text` ⇒ 工作树字节 == 入库 blob），并且**从 Task 1 起写全 13 个波次**
（只写 7–13 会让这一份账本从中间开始、读不出计划的形状）。
内容：§0 计划的形状 + **开工时点的账面**（8 格）／§1 波次账（Task 1→13 各一节：
commit 逐个列 + 做了什么 + **账面怎么变** + 顶回 + 报告与 spec 的住址；
末尾一节 Task 14 = **尚未做**的全分支终审）／§2 Plan 06 的最终账面（10 格）+
两个指针（§13.14.3 的对账表、§15 的延后台账）。
⚠️ 它**刻意不复述细节**（细节的唯一住址是那 11 份报告与 spec），故它不会成为第二个所有者。
⚠️ **本波没有动那 10 份历史报告**（账本不改写，硬规矩 #66）。

---

## ⑨ 待清扫 / 关切 / 没按派单做的 / **顶回** + 最终验收

### ⑨-1 **顶回**（**10** 处；**0** 次 Critical）

| # | 顶回什么 | 理由要点（详址） |
|---|---|---|
| 1 | **D8② 那个「约 2/3」** | 本机实测 **7.9 s / 32.1 s ≈ 1/4**（Task 11 那次 ≈ 一半）⇒ 这一格的绝对值**随机器漂**，故 spec 与文件头都**只钉口径不钉数**（§⑤-4） |
| 2 | **D9-②/③ 两批台账的归属** | 派单标「Task 11 新登记 6 条」的那 6 条实测住在 `task-12-report.md`；派单标「Task 12」并点名的那一格实测是 task-12 的**关切**第 2 条 ⇒ 处置：不按标签、**14 条全覆盖**（§⑦） |
| 3 | **D3「在 §1.2 的台账里找到那一条」** | 实测**不在 §1.2**（18 条逐条 `Grep` 过），它住在 **§13.4.4** 的 I6 引用块里；品牌波那句「已写进 §1.2 的 12 条已知局限」绑的是那个时点（§③-2） |
| 4 | **D5「若 `demo.ps1` 那一句打印本身在撒谎就修脚本」** | 实测它**没有撒谎**（`demo_bootstrap.py:554-558` 已经正确区分两者）；真正会让人误读的是 `prescription_stage.py:1308` 的日志前缀「需要人工复核」⇒ **裁定不改那一句日志**（改措辞要连 caplog 断言一起动、收益只是修辞），把误读风险写进 §7.4（§③-4） |
| 5 | **D9-④ 第 10 条「要动 6 个页面」** | 实测 **15 处 / 10 个页面文件**（`<code>….py</code>` 那一档，逐个列在 §15 的 D1） |
| 6 | **D9-⑤「计划 §10 只有 6 行」** | 实测是 **5 条**验收口径（第 6 行是标题与空行的行数） |
| 7 | **D9-⑤「`progress.md` 更新…从那儿续」** | 实测 Plan 06 **没有**这一份（Plans 04/05A/05B 也没有）⇒ 新建，并从 **Task 1** 起写全 13 个波次（§⑧-5） |
| 8 | **数字总账「计划开工时 1426」** | 实测开工是 **1340**；1426 是 Task 3/4 结案那个时点（§⑧-4） |
| 9 | **「未定型响应 26」** | 实测是两个口径：未定型响应 **24**（本波 openapi 现算）／`expected` **26** 是**特例端点清单**（§⑧-4） |
| 10 | **Task 12 报告里「最长路径模板 47 字符」** | 实测 **56**（`/api/students/{student_id}/training-logs/completion-rate`）⇒ 结论不变（56×2=112 < 256，余量 2.3 倍），而**那个数漂了正是把它钉进守卫的理由**（§⑦ T12 关切 2） |

⚠️ **另有一处自己的错、当场抓到并改了**（不算顶回，如实记）：§D7 那一拍首版用
**状态码**判「这是哪一档」，而产品档的 SPA fallback 对 `/src/router/index.ts` 也回
**200**（`index.html`）⇒ 若不两档都跑就会**假红**；判据改成 **content-type**
（vite 服务成 `text/javascript`）（§⑤-2）。
⚠️ **逐条核过并同意**的控制者裁定（没有顶回）：D4「本仓不做跨后端支持」／
D7「产品档不受这一格影响」／D8「不把那两拍拆成单独的 npm script」／
D9-①「本波统一删 `$env:TEMP` 上的陈旧探针」／D9-②#1「UA 不做」／
D9-②#2「CSV 延后到 Plan 07」／D9-③「`path` 撞格可接受、但前提要写清」／
D9-④ 第 10 条给的**边界口径**（API 响应体里不许有内部标识符 **已钉死**，
而页面散文里的模块路径是**可解释性惯例**）—— ⚠️ 这一格本波**核过并同意**：
两件事的失效方向不同（前者是**响应体**、任何匿名调用方都能读到；后者是**页面散文**、
在 `/t/*` 与 `/admin/*` 的路由守卫之后），故边界成立。

### ⑨-2 没按派单字面做的（**3** 处，逐个如实记）

1. **commit 数**：派单建议 4–5 个（① D1+D2+D5、② D3+D4、③ D6+D7+D8、④ D9-①②③、
   ⑤ D9-④⑤），实际是 **5** 个，而**分组与派单不同** —— ①②**合并**了（两批都改 `spec`，
   而 `git add` 是**按文件**的、本波不开交互式暂存，拆开就得把同一个文件在两个 commit 里
   各写一半；⚠️ 合并后那一个仍然自洽：D1–D5 全是「交付文档与台账的正确性」），
   多出的第 5 个是**补记 sha** 的那一个（把 §13.14.2 / `progress.md` / 本报告里的
   「本波末」占位换成真实 commit 链，照 Task 12 的 `b4f09ac` 先例）。
2. **D7② 的「便宜的真检查」换了判据**：派单举的例子是「断言 dev server 服务的某个
   模块里含一个**本波源码里的标记串**」，本波做的是「磁盘上的**全部** `path:` 字面量
   ⊆ dev server 服务出来的那一份模块文本」—— 后者**不需要**每波维护一个标记串
   （写死标记串 = 「每次跑之前要记得改它」= 又一个待清扫项）。
3. **D9-① 的清理时点**：派单要求「删净并复验」，本波**分两次**删 ——
   主体那 **125** 个在停服务之后一次删净并复验（§⑥），
   而**最后一次** `demo.ps1`（为跑最终验收的 dev 档 smoke）又建了一个
   `pe_demo_csv_<pid>`，它在收尾时**再删一次并复验**（见 §⑨-4 的卫生格）。

### ⑨-3 本波**新登记**的待清扫（**4** 条）

1. ⚠️ `prescription_stage.py:1308-1309`（与 `:1512-1513` 的手工重生成那一支）把
   `safety.warnings` 里**每一条**都套上「**需要人工复核**」这个前缀，
   而那正是 `needs_review` 那一档在教师端的措辞 ⇒ 读日志的人会把两件事当成一件。
   本波裁定**不改**（§③-4），而这一格**仍然在**：要改的话得连
   `tests/pipeline/` 的 caplog 断言一起动。⚠️ 交代已写进 §7.4。
2. ⚠️ `exercise` 与 `prescription_template` 两张表在演示库上**恒 0 行**
   （动作库与 18 套模板住在 `backend/data/` 的 YAML、运行时加载、从不入库），
   而管理台的资源目录把它们与另外 21 个资源**并列**列出 ⇒ 甲方点进
   `/admin/exercises` 会看到「共 0 行」。⚠️ 本波只修了 `demo.ps1` 那条骗人的例子
   （§②-4），**没有**动 UI；要不要在那两行上标一句「本仓从 YAML 加载、不入库」
   是**产品口径**，留给下一波裁定。
3. ⚠️ `spec §3.2` 那棵目录树里写的是 `backend/data/prescriptions/`，
   而磁盘上是 `backend/data/prescription/`（**无 s**）。§3.2 是历史设计节
   （本波已给它加了指向 §13.6 的指针），故**不改写**；如实记。
4. ⚠️ `progress.md` 的**体例**在 Plans 04–06 之间断了三代（那几波只有
   「一波一份实现者报告」）。本波为 Plan 06 新建了一份，而 Plans 04 / 05A / 05B /
   品牌波 / 安全收紧波 / 收尾波**仍然没有**。要不要补是账本口径的决定，不是本波的范围。

### ⑨-4 关切（**2** 条）

* ⚠️ **本波改了 `demo.ps1` 的打印**，而 `smoke.mjs` 第 17 步 ① 会 spawn
  `demo.ps1 -DryRun` 并断言它打印的某几行、⑤ 会从 `demo.ps1` 里**现场切一段**
  （`$HeaderIdentityInherited = …` 到 `{ '未设' } else { '=' + $HeaderIdentityNow }`）
  再断言 `serve.ps1` 里逐字有它。⚠️ 本波改的是**文件末尾那一段提示 URL**
  （`:257-273`），与那两处**都不相交**；两档 smoke 复跑全绿（含第 17 步 59/59）
  即这一格的取证。
* ⚠️ **`npm run build` 的产物哈希与派单给的基线不同**：派单写
  `index-DwZqq7MF.js` / `StudentDetail-D-ttLtZL.js` / `AuditLogList-BKStMt_y.js`，
  本波实测 **`index-BCWjM00F.js`** / **`StudentDetail-BQenvJ7d.js`** /
  **`AuditLogList-DmETt2XK.js`**（CSS 那一个 **`index-v1XDnUhk.css`** 逐字相同）。
  ⚠️ **不是本波改出来的**：`task-12-report.md:585-586` 逐字记着 Task 12 自己
  **构建了两次**（第二次改 `AuditLogList.vue` 之后），留下的是第二次的哈希
  （`index-BCWjM00F.js`），而它那张表里写的是第一次的。⚠️ 本波在**未改任何
  `frontend/src/**`** 的前提下重建，逐字复现了磁盘上那一份 ⇒ 产物是**确定的**、
  漂的是报告里的那一格数字。

### ⑨-5 最终验收

**后端**（`backend/`，`PE_DB_URL` 指到 `$env:TEMP\p06t13\`）

| 格 | 基线（`b4f09ac`） | 本波 |
|---|---|---|
| 全量（`--cov=app/domain --cov-branch`） | 1561 passed + 1 skipped（288 s） | **1564 passed + 1 skipped**（**291.41 s**）← **净新增 3 条**（§⑦ 那三条守卫），**亲跑** |
| 全量（不带 `--cov`） | 1562 passed（164 s） | **1565 passed**（**172.69 s**），**亲跑**（⚠️ 不是折算） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%**（**一格未变**；18 个文件逐个 100%） |
| `warnings summary` | 1 条 starlette | **1 条 starlette**（未变） |
| 表数（health 口径） | 28 | **28**（`GET /api/health` 实测 `{"status":"ok","tables":28,"students":60}`；`sqlite_master` 里 `type='table'` 是 **29** = +`alembic_version`） |
| **迁移链** | 4 单头 | **4 单头**（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b`；⚠️ 本波**没动** schema，只给迁移 4 加了 docstring） |
| 架构守卫扫描面 | 72 | **72**（`pipeline 10 + db 14 + domain 18 + api 26 + auth 4`；本波一个模块都没加） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`assert len(...) == 33` 在 1565 里） |
| `_MODELS_SUBMODULES` | 8 | **8**（`organisation / assessment / derived / prescription / feedback / ops / auth / audit`，现算） |
| 黄金用例 | 14 | **14**（`test_golden_cases.py` 收集 **19** 条、id 到 `[13-GC14]`，现算） |
| 未定型响应 | 26（派单口径） | ⚠️ **两个口径都报**：未定型响应 **24**（openapi 现算：23 个泛型 list + `/api/health`，逐个列在 §③-1 之外的那份探针输出里）／`test_prescription_api.py` 的 `expected`（= **特例端点清单**）**26**，`assert len(expected) == 26` 绿 |
| 依赖清单守卫 | 后端 7+3+1、前端 3+7 | **一字不红**（`tests/test_dependencies.py` 在 1565 里；**新增依赖 0**） |

**openapi 五格（⚠️ 一格都没变）**

```
路径 74 / 操作 102 / 挂 security 84 / GET 63（匿名 15 + 挂 security 48）/ securitySchemes 3
非 /api 的路径模板 = []          ← catch-all 0 个漏进 paths
```

**前端**

| 格 | 基线 | 本波 |
|---|---|---|
| `npm run build` | 退出码 0 | **退出码 0**（`vue-tsc -b` 也过，`✓ built in 344ms`） |
| 产物哈希 | `index-v1XDnUhk.css` / `index-DwZqq7MF.js` / `StudentDetail-D-ttLtZL.js` / `AuditLogList-BKStMt_y.js` | **`index-v1XDnUhk.css`（65.20 kB）/ `index-BCWjM00F.js`（168.82 kB）/ `StudentDetail-BQenvJ7d.js`（39.16 kB）/ `AuditLogList-DmETt2XK.js`（9.55 kB）**（⚠️ 与基线的差异**不是本波改出来的**，逐字见 §⑨-4 第 2 条） |
| 路由条数 | 16 / 20 | **16 / 20**（未改） |
| `check:tokens` | 绿（扫描面 36、下界 25） | **绿**（`✓ 全绿：36 个文件里，tokens.css 之外一个色值字面量都没有`，退出码 0） |
| `check:dist` | 绿（25 产物 / 780 131 字符） | **绿**（`25 个 / 780131 字符`，退出码 0；`adoptFromUrl` 0 次、两个字体 CDN 各 0 次、三条自校都在） |
| **smoke dev 档** | 18 步 / 632 断言 / 0 / 30.1 s | **18/18 步 · 637 断言 · 0 红 · 退出码 0 · 32.1 s**（后端 8000 + vite **5174**） |
| **smoke 产品档** | 18 步 / 633 断言 / 0 / 30.7 s | **18/18 步 · 637 断言 · 0 红 · 退出码 0 · 30.1 s**（`serve.ps1 -Port 8020 -SkipBuild`，同源） |
| `gen:api` | 离线、2.33–2.94 s | **离线、2.34 s、退出码 0**；`[dump_openapi] 417032 字节 / 74 路径 / 102 操作`；⚠️ 产物 **`git diff` 为空**（行尾那一格见 §⑨-6） |
| 新增依赖 | 0 | **0** |

**禁区与卫生**

| 格 | 实测 |
|---|---|
| 四个数据指纹 | **逐字对**：`national_standard_2014.csv` = `D2C8E539E2FA0029`（21 412 B）／`exercises.yaml` = `5394B37F01DAC9AC`（23 247 B）／`exercise_equivalence.yaml` = `822CB86A5E998301`（8 245 B）／`alert_rules.yaml` = `E48E3AC82BB45BB7`（6 037 B）——**现算 vs 测试常量逐个比**（LF 归一口径） |
| 18 个模板指纹 | 期望侧 **18** 条（`TEMPLATE_FINGERPRINTS`）× 磁盘 `backend/data/prescription/*.yaml` **18** 个 → **不符 0 条** |
| `git diff b4f09ac HEAD -- backend/data` | **空**（一字节没动） |
| `backend/pe.db` | **不存在**（`Test-Path` → False；每次跑完全套件后都复核过） |
| `backend/data/seed/` | 目录存在、**文件数 0** |
| `frontend/dist` 是否入库 | `git ls-files frontend/dist` → **0** 个文件 |
| `.gitattributes` | `git diff b4f09ac HEAD -- .gitattributes` → **空**（一条都没碰） |
| 本波起的进程 | `demo.ps1`（8000）与 `serve.ps1`（8020）**都已停**、vite（5174）**已停**；⚠️ 5173 上那个 **PID 20240** 不是本波起的、**全程没动** |
| `$env:TEMP` | 主体清理：**125 → 0**（失败 0 处、逐个 `os.path.exists` 复验为 False）；收尾再删最后一次 `demo.ps1` 建的 `pe_demo_csv_<pid>` 与本波的 `p06t13\`（⚠️ 写本报告的那个脚本自己住在里面，故删除排在最后一个 commit 之后；复验输出逐字贴在控制者回复里） |

**spec**

| 格 | 改前 | 改后 |
|---|---|---|
| 字节数（工作树） | 425 949 B | **487 278 B** |
| 行数（CRLF） | 4 038 | **4 601** |
| 行尾 | 全 CRLF / 裸 LF 0 / 无 BOM | **全 CRLF / 裸 LF 0 / 无 BOM** |
| sha256[:16]（工作树口径） | `f083261a4985dad5` | **`d5fe2ec56c333ef9`** |
| sha256[:16]（LF 归一口径） | `1e6a44addc96d7b0` | **`dc47b0d9808a5c98`** |

⚠️ 上面那四个数是在**本波最后一个 commit**（补记 sha 的那一个）之后现算的：
那一个 commit 也改了 spec 一行（§13.14.2 的 Task 13 那格 commit 区间），
故 `10514ed` 时点的值是 487 224 B / `a57d2b2f739cfd17` / `6034ac561198bff7`
——**两个时点都记在这里**，免得下一个人拿旧值对不上账。
| 新增的节 | — | **§13.14**（.1–.6，兼 Plan 06 结案节）；§15 的「延后台账」16 条；§7.4 / §12 / §13.1 / §13.4.4 / §13.6 / §13.7 / §13.9 / §13.11.4 / §13.13.1 各一处 |

**commit 链与行尾复核**

| commit | 内容 | 自洽吗 |
|---|---|---|
| `58b9640` | ① D1–D5（spec 7 处 + `demo.ps1` + `demo_bootstrap.py` + 迁移 4） | ✅（`Parser::ParseFile` 0 错误、`py_compile` 0、两条迁移守卫 + 文档引用守卫 34 passed） |
| `b0fe767` | ③ D6+D7+D8（`smoke.mjs` + spec §13.11.4） | ✅（`node --check` 0；两档 smoke 各跑一整遍 18/18 · 637 · 0） |
| `4ee8063` | ④ D9-①②③（3 条新守卫 + spec §12 / §13.9 / §13.13.1） | ✅（`test_column_widths.py` 16 passed + `test_docstring_references.py` 绿；3 处定点变异逐个红） |
| `10514ed` | ⑤ D9-④⑤（spec §15 + §13.14 + `progress.md` 新建 + 本报告） | ✅（纯文档 + 账本；spec 的行尾与 sha 当场复核） |
| 补记 sha 的那一个 | 把 §13.14.2 / `progress.md` / 本表里的「本波末」占位换成真实 commit 链（照 Task 12 的 `b4f09ac` 先例） | ✅（纯文档） |

| 被改文件 | `git ls-files --eol` | 工作树字节 / 行尾 / BOM |
|---|---|---|
| `Document/2026-09-28-…设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | 487 224 B / **全 CRLF、裸 LF 0** / 无 BOM |
| `Document/2026-10-13-实施计划06-….md` | `i/lf w/crlf attr/text eol=crlf` | **未改**（⚠️ 计划文档刻意一个字都没动） |
| `backend/scripts/demo.ps1` | `i/lf w/crlf attr/text eol=crlf` | 21 898 B / 全 CRLF、裸 LF 0 / **BOM 在**（smoke 第 17 步 ① 钉着这一格） |
| `backend/scripts/demo_bootstrap.py` | `i/lf w/crlf attr/` | 41 658 B / 全 CRLF、裸 LF 0 / 无 BOM |
| `backend/migrations/versions/0ac943e0da9b_….py` | `i/lf w/crlf attr/` | 8 932 B / 全 CRLF、裸 LF 0 / 无 BOM |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | **301 642 B** / 全 CRLF、裸 LF 0 / 无 BOM（`node --check` 退出码 0） |
| `backend/tests/api/test_column_widths.py` | `i/lf w/crlf attr/` | 60 052 B / 全 CRLF、裸 LF 0 / 无 BOM |
| `frontend/src/api/generated/schema.d.ts` | `i/lf **w/crlf** attr/` | 527 633 B / 全 CRLF、**裸 LF 0** / 无 BOM（⚠️ `gen:api` 之后**还原过**；`git diff` 为空） |
| `.superpowers/…/progress.md`（新） | `attr/-text` ⇒ 工作树 == blob | **16 671 B / 233 行 / LF / 无 BOM** |
| `.superpowers/…/task-13-report.md`（新） | `attr/-text` ⇒ 工作树 == blob | ⚠️ **自指**：本报告的字节数写进它自己就会改变它，故这一格不在报告里报数；「工作树字节数 == `git cat-file -s` 的入库 blob」那一格的实测值逐字贴在控制者回复里（本波**不做**第二次「补记 sha」的 commit，Task 12 做过一次 `b4f09ac`） |

⚠️ **两个口径都报**（本机 `core.autocrlf=true`）：上表的 `i/lf` 是**入库 blob** 的行尾、
`w/crlf` 是**工作树**的行尾；`.superpowers/**` 因为 `-text` 而**两个口径相同**（都是 LF）。
