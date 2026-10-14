# Plan 06 Task 9 —— 实现者报告（两件功能：schema 级摘列 + 管理台审计只读页）

> 分支 `p06/schema-audit-page`（从 `main` 的 `a37a7f5` 起）。
> ⚠️ **本波只做计划 §9 的第 1、3 两条**：清扫 / 终审 / 推送**都不在本波**
> （分别是 Task 10 / Task 11），一件都没顺手做。
> ⚠️ **没有 push**（派单点名「有 9 个 commit 待推、网络间歇性失败、控制者会重试」）。

---

## ① 环境

| 项 | 实测 |
|---|---|
| 开工第一件事（硬规矩 #73） | `node --version` → **v24.19.0**；`python --version` → **Python 3.11.1**；`npm --version` → **11.17.0** |
| 仓库根 | `c:\Users\whwenhao\Desktop\Physical_Education_ims` |
| 分支 / 起点 | `p06/schema-audit-page`，`git checkout -b` 时 HEAD = **`a37a7f5`**、工作树干净 |
| `core.autocrlf` | **`true`**（⚠️ 见 §⑦ 那一格「行尾口径的实测更正」） |
| 服务 | 本波起过的进程：`demo.ps1 -Port 8000`（3 次，各灌一遍演示库）、一个临时 `uvicorn app.main:app --port 8000`（只为 `gen:api`）、`npm run dev -- --port 5174 --strictPort`、`scripts\serve.ps1 -Port 8020`。**收尾时全部已停**（§⑧）。 |
| ⚠️ 5173 | 开工时实测 **5173 上有一个不是本波起的 vite**（PID 20240，`::1`）→ **没杀它**，dev 档改用 **5174** + `PE_WEB_BASE=http://localhost:5174`（派单点名的处置） |
| 演示账号 | 口令 `pe-demo-2025`；学生 `2023120001`（id **4**，班 2+4）、教师 `T0001`（班 1+3）、管理员 `T0003`；业务日 `2025-10-12`；`semester_id=2` |
| 探针目录 | `$env:TEMP\p06t9\`（删前那一刻实测 **37** 个条目 = **36** 个文件 + 1 个 `__pycache__\`：4 份 HTTP 实测探针（`probe1`–`probe4.py`）、3 份 CDP 真渲染探针（`probe5`–`probe7.mjs`）、**14** 份编辑脚本（`edit_feedback` / `edit_tests` / `edit_docs` / `edit_fe1`–`edit_fe7` / `edit_smoke1`–`edit_smoke3` / `edit_spec`）、3 份工具（`edio.py` 行尾助手 / `to_lf.py` / `recrlf.py`）、3 份 commit 消息（`msg-1`–`msg-3.txt`）、4 份运行日志（`smoke-dev` / `smoke-prod` / `pytest-nocov` / `pytest-cov`）、2 份提交与复核脚本（`commit.py` / `commit3.py`）、`write_report.py`、`fix_report_count.py`（就是本段这一次更正）、`verify_forbidden.py`；⚠️ `$env:TEMP` 里那 106 个之前各波留下的 `pe_*` 探针**一个都没碰**）。⚠️ 另外 3 个 CDP 无头浏览器的临时 profile 目录（`p06t9-cdp-*` / `p06t9-cdp6-*` / `p06t9-cdp7-*`）也一并删掉并复验（§⑧） |

---

## ② 摘列**前**的实测（不是读代码推的，是真 HTTP + cookie 会话）

探针 `$env:TEMP\p06t9\probe1.py`（已入库登记，见 §⑧）；`GET /api/mini-tests/normalized?semester_id=2&week=6`：

| 身份 | `sections` | `entries[i]` 的键集合 | `squat_score` / `composite` 非空的行数 | `unassigned` |
|---|---|---|---|---|
| 学生 `2023120001`（#4） | `[2, 4]`（`scored_count` 30 / 20） | `composite, mini_test_id, shuttle_score, squat_score, student_id`（**五格**） | **每班恰好 1 行**（= 本人）；而 `shuttle_score` 30 / 20 行**全非空** | 0 |
| 教师 `T0001` | `[1, 3]` | **逐字相同的五格** | 30 + 20 = **50 行全非空** | 0 |
| 管理员 `T0003` | `[1,2,3,4,5]` | 同上 | **120 行全非空** | 0 |
| 匿名 | —— | —— | **401** `unauthenticated`（`PE_ALLOW_HEADER_IDENTITY` 未设，请求头被忽略） | —— |

学生 #4 自己那一行（week 6）：`{"student_id":4,"mini_test_id":124,"squat_score":35.0,"shuttle_score":98.33,"composite":66.67}`（班 2）与 `{...,"shuttle_score":92.5,"composite":63.75}`（班 4）。

### 2.1 `MiniTest.vue`（学生页）**用不用**那两格 —— **用**

| 用在哪 | 逐字位置（改前） | 读的是谁的行 |
|---|---|---|
| 第 02 块「小测综合分」`StatBlock` | `:value="row.entry.composite"`（原 392 行） | **本人**那一行 |
| 第 02 块「深蹲得分」`StatBlock` | `:value="row.entry.squat_score"`（原 415 行） | **本人**那一行 |
| 第 02 块「折返班内百分位」+ `sample`/`slower`/`tied`/`rank` | `row.entry.shuttle_score` + `mySections` 遍历**全班** | 全班（算名次必须要全班） |
| 第 02 块「小测行 id」 | `row.entry.mini_test_id` | 本人 |

⚠️ 它**不是**表格列、也**不是**「自己那一行高亮」，而是两个 `StatBlock`（大数字）。
⚠️ `mySections` 只挑「里面有我这一行」的班，故那两格**恒为本人**的值 —— 学生档今天
看到的是「**自己那行有值、别人全 `null`**」（不是全 `null`）。

### 2.2 教师档 / 管理员档用不用 `normalized` —— **教师页用，管理台不用**

`Grep frontend/src` 的实测：读 `normalized` 的页面**只有两个** ——
`views/student/MiniTest.vue` 与 `views/teacher/StudentDetail.vue`。
（`ClassReport.vue` / `Dashboard.vue` 里各有一句 caption **逐字写着「不要自己去调
`GET /api/mini-tests/normalized` 拼榜」**，那是反面提示、不是调用。）

⚠️⚠️ **`StudentDetail.vue`（教师页）也读那两格**（原 842 / 863 行：
`:value="row.entry.composite"` 与 `:value="row.entry.squat_score"`，读**被查看的学生**
那一行）。⚠️ 于是派单 §1 那句「**管理台/教师页不受影响**」的前提**不成立** ——
已顶回（§⑦ 第 1 条）。管理台**没有**页面读 `normalized`（`Grep` 实测 0 处）。

### 2.3 那两格是不是「空气」—— **不是**（对账过）

学生 #4 的 `GET /api/mini-tests?limit=200`（`student_self` 档）实测 3 行：
`{id:4, week:2, squat_30s_count:30}` / `{id:64, week:4, squat_30s_count:23}` /
`{id:124, week:6, squat_30s_count:35}` —— 而窄端点回的 `squat_score` 是 **35.0**，
逐行相等（spec §8.1「深蹲得分 = 次数（直接用）」）。

---

## ③ 摘列后的 schema 与**窄端点的取舍**

### 3.1 摘列

`NormalizedEntryRead`：**五格 → 三格** = `student_id` / `mini_test_id` / `shuttle_score`。
⚠️ 从此该 schema **不含任何随身份而变的列**。
⚠️ **Task 8 那根「响应级裁班」的轴保留**（它收的是「哪些行」，不是「哪些列」）。

摘列后的实测复跑（探针 `probe3.py`）：三档的 `entries[i]` 键集合**逐字相同** =
`{mini_test_id, shuttle_score, student_id}`，而 `sections` 仍然按身份裁班
（`[2,4]` / `[1,3]` / `[1..5]`，`entries` 合计 50 / 50 / 120 行）。

`NormalizedScoreRead` 的 docstring 里把「哪些**行**随身份而变（分页/过滤的常规形状，
OpenAPI 表达不了行数）」与「哪些**列**恒不变（故 `schema.d.ts` 是真契约）」写成了两句话，
免得下一个人把两件事再混起来。

### 3.2 窄端点：**加了**（实测确认学生页需要）

派单的证伪条件是「若实测发现学生页确实需要自己那两格」—— §② 的实测**触发了它**
（两个 `StatBlock` 读的就是本人那一行的 `composite` / `squat_score`），故**加**。

| 项 | 落地 |
|---|---|
| 路径 | `GET /api/mini-tests/normalized/me?semester_id=&week=` |
| 函数 / 响应模型 | `normalized_scores_self` → `NormalizedSelfRead`（+ `NormalizedSelfSectionRead`） |
| 形状 | `{semester_id, week, sections:[{course_section_id, mini_test_id, squat_score, shuttle_score, composite}]}` —— **恒为「调用者自己的那几行、全列」** |
| 身份依赖 | `Depends(current_student)`（**只认学生**；教师/管理员 cookie 403、匿名 401）—— 既有唯一所有者，本端点**一行判定都不写** |
| OpenAPI 声明 | `dependencies=[Security(STUDENT_ID_SCHEME)]` —— ⚠️ **一个** scheme，**刻意不是**班级端点那两个的 OR（本端点不接受教职，OR 语义在这里是一句假话） |
| `student_id` 入参 | **没有**这个查询参数（恒取自会话）→「请求别人的行」在**签名上就不存在** |
| 分组与算式 | 与班级端点**共用** `_normalized_sections` + `_enrolled_sections`（本波拆出的两个私有助手），三格一律出自 `app/domain/report.py::mini_test_scores` |

### 3.3 四档矩阵（真 cookie，生产档；`probe3.py` 实测 + 后端 pytest + smoke 各钉一遍）

| 调用方 | 码 | `error.code` | 由谁给出 |
|---|---|---|---|
| 匿名 | **401** | `unauthenticated` | `app.api.deps.current_student` |
| 学生（`2023120001`） | **200** | —— | 同上；实测回 2 个班：班 2 `squat 35.0 / shuttle 98.33 / composite 66.67`、班 4 `35.0 / 92.5 / 63.75` |
| 教师（`T0001`） | **403** | `forbidden` | 同上（「一个教师/管理员的 cookie 不能当学生用」） |
| 管理员（`T0003`） | **403** | `forbidden` | 同上 |

⚠️ **不带查询参数那一发**：匿名 **401**（不是 422）、教师 **403** —— 先过鉴权、后挂校验。
⚠️ **开发档请求头那一档的码不同**（如实记，与 §13.9 审计端点同族）：
`PE_ALLOW_HEADER_IDENTITY=1` 下 `X-Teacher-Staff-No`（在册教师 / 管理员 / 不在册三种）
在 `current_student` 眼里都等于「没有身份」→ **401**，不是 403。两档都拒绝访问，
故不构成漏洞；守卫 `test_the_normalized_me_route_in_the_dev_header_tier` 把它钉住。

### 3.4 「形状恒定」这一格怎么验的

* 多送一个 `student_id=5` 查询参数 → **200**、且回的**仍然是本人**（#4）的那几行
  （FastAPI 静默忽略未声明的查询参数）。后端与 smoke 各有一拍。
* `sections` 的 `course_section_id` 列表与班级端点**学生档**的班号**逐字相同**
  （同一条 `enrollment` 判据）。
* 每个班的 `shuttle_score` / `mini_test_id` 与班级端点里本人那一行**逐字相等**
  （共用取样）。⚠️ **首跑红了这一拍**，红的是**取证**不是实现：配对键原本写的是
  `mini_test_id`，而一个学生同一学期在两个班、那一周只有**一行** `mini_test` →
  后端把同一行投进两个班的 `entries` 各算一次百分位，实测两个班的 `mini_test_id`
  **都是 124**（`shuttle_score` 分别是 98.33 与 92.5）。改成按 `course_section_id`
  配对后绿，**判据一个字没改**。

### 3.5 前端跟随

* **`MiniTest.vue`（学生页）**：两个 `StatBlock` 改读 `row.self?.composite` /
  `row.self?.squat_score`；两次请求 `Promise.all` **并行**发（同一组查询参数），
  任何一次失败落**同一块**「有解释的区域」（刻意不给窄端点单开一块错误区：
  两块会说同一句话）。`mySections` 多带一格 `self: SelfSection | null`
  （查不到 → `StatBlock` 渲染「—」，**不是** 0；今天不可达，留着是让
  「后端把两个端点的判据写岔了」在屏上可见而不是白屏）。
  ⚠️ **只改学生页**（派单口径）。
  **真渲染取证**（产品档 8020、学生 #4、`home.week=6`；探针 `probe5.mjs`）：
  教学班 2 → 综合分 **66.67** / 折返 **98.3** / 深蹲 **35.0** / 比你慢 29 人 / 并列 1 人 /
  名次 第 1 / 30 / 小测行 id 124；教学班 4 → **63.75** / **92.5** / **35.0** / 18 人 / 1 人 /
  第 2 / 20 / 124 —— 与窄端点回的 JSON 逐字对上，`.s-notice` = `null`、`.s-unknown` = **0** 块。
  ⚠️ **为什么要有这一份取证**：`smoke.mjs` 第 14 步对 `/s/mini-test` 的两条 needle
  （`二次小测` / `30 秒深蹲`）都是**静态模板文字**，故轮询会在异步数据落地之前就退出 ——
  那一拍证明「没白屏」，**证明不了**第 02 块渲染出了数。判据不许改（硬规矩 #92），
  故单独量一次（已登记为待清扫，§⑦）。
* **`StudentDetail.vue`（教师页）**：⚠️ 派单说「教师页不受影响」，实测**不成立**（§②.2）。处置：
  ① 「深蹲得分」改读本页**已经拿到**的 `pickedMiniTest.squat_30s_count`
  （与 `normalized` 请求同一行推出来的 `semester_id` + `week`，故两格说的是同一次小测；
  逐行相等由后端守卫钉住）→ **显示出来的数一个字节都没变**；
  ② 「小测综合分」本波**不再显示**（教师会话打窄端点是 403，而本页**刻意不在前端重算**：
  综合分与百分位同源，重算就是第二个所有者），页面上如实交代（块末新增一段
  `t-block__why`）并给出正确形状（另开教师侧变体）。
  **真渲染取证**（产品档 8020、T0001 看学生 #10、`probe6.mjs`）：教学班 1（班内 30 人有成绩）
  → 折返 **83.3** / 深蹲 **32.0**（= 该周原始行的 `squat_30s_count` 32）/ 比他慢 24 人 /
  并列 2 人 / 名次 第 5 / 30；`StatBlock` **两格**（改前三格）。
  ⚠️ 教师打窄端点实测 **403**；班级端点 `entries[0]` 的键集合实测
  `["mini_test_id","shuttle_score","student_id"]`。
* ⚠️ **`.sd-stats` / `.sect__stats` 都是 `display:flex; flex-wrap:wrap`**（实测两处 CSS），
  故少一个 `StatBlock` **不塌宽**；smoke 第 14 步两档各 16 条路由的
  「无重叠 / 无非故意横向溢出 / 无整页横向滚动条」全绿（§⑥）。
  ⚠️ **没有引入任何新的裸值**：两个页面**一行 CSS 都没改**。

---

## ④ openapi 五格 · catch-all · securitySchemes · 断言同步 · `gen:api`

| 格 | 改前 | 改后 | 由谁钉 |
|---|---|---|---|
| 路径模板 | **72** | **73** | `smoke.mjs` 第 12 步 |
| 操作 | **100** | **101** | 同上 |
| 挂 `security` 的操作 | **82** | **83** | 同上 + 后端 `test_prescription_api.py` 的 `len(all_security)` |
| GET | **61** | **62** | `smoke.mjs` 第 12 步 |
| 其中**匿名** GET | **15** | **15**（不变；新端点挂 security） | 同上 |
| `components.securitySchemes` | **3** | **3**（不变；挂的是既有的 `X-Student-Id`） | 后端 `test_prescription_api.py` + 新加的一条 smoke 拍 |
| 挂 security 的 GET | 46 | **47** | 后端（算式注释） |
| catch-all 漏进 `paths` | **0** | **0**（探针 `probe2.py`：可疑形状 0 个、含 `pathMatch` 的路径 0 个） | —— |
| 顶层 `spec.security` | `None` | `None` | 后端 |
| 表数（health 口径） | 28 | **28** | `smoke.mjs` 第 1 步 |

⚠️ **摘列的那一半（`components.schemas`）不动这五格任何一格** —— 它改的是 schema、不是 `paths`。
⚠️ 匿名 GET 的 **15** 条名单逐字复核过（`probe2.py`）：`class-sessions` ×2 /
`course-sections` ×2 / `exercises` ×2 / `fitness-test-batches` ×2 / `health` /
`percentile-snapshots` ×2 / `prescription-templates` ×2 / `semesters` ×2 —— 一个学生键都没有。

**新操作的声明面**（`probe2.py` 实测）：
`security = [{"X-Student-Id": []}]`；`parameters = [semester_id(query,必填), week(query,必填), x-student-id(header,可选)]`；
`operationId = normalized_scores_self_api_mini_tests_normalized_me_get`；`responses = [200, 422]`。
⚠️ `/api/mini-tests*` 今天 5 条路径：``（集合 GET）`` / `batch`(post) / `normalized`(get) /
`normalized/me`(get) / `{mini_test_id}`(get) —— 新路径**四段**，与泛型的**三段**不同形，
故 include 顺序对它不承重；⚠️ 而它仍然进了 `_LITERAL_TAILED_SPECIAL_ROUTES` 那份绊网清单。

**全仓钉这些数的断言：同步了 3 处**

| # | 住址 | 改了什么 |
|---|---|---|
| 1 | `frontend/scripts/smoke.mjs` 第 12 步 | 五格 `72/100/82/61/15` → **`73/101/83/62/15`** + 一段 Task 9 的来历注记 |
| 2 | `backend/tests/api/test_prescription_api.py` | `expected` **24 → 25** 项（新增 `("/api/mini-tests/normalized/me","get"): "X-Student-Id"` + 一段行内注记）、`len(all_security)` **82 → 83**、算式注记 `24 特例 + …` → `25 特例 + …`、docstring 首段「Task 9 起是 25 项」；⚠️ 顺手改正了两处**已过期**的数（「其余 20 格是请求头名」→ **23**、「一个 scheme 名（22 格）」→ **24**，两处都是 Plan 05A 时点的数、Task 5 与 Task 9 各加一格之后没跟上） |
| 3 | `backend/tests/api/test_feedback.py` | `_LITERAL_TAILED_SPECIAL_ROUTES` **3 → 4** 项 + 第 ② 拍的行为面证据（断**窄端点专属**的三键信封，与班级端点的四键不同形，故它同时挡住「落到了班级端点上」那一档） |

⚠️ `crud` 那一圈的操作数**不变**（76 = 101 − 25）：新端点是特例端点，进了 `expected`
就同时从 `crud` 出去，故 `>= 70` 的空转下界仍然成立、**刻意不抬**。
⚠️ `student_self_reads`（26 项）与 `staff_only_reads`（6 项）**都没动**：
那两份是「23 个资源 × 集合/成员」的全集口径，本端点不是资源。

**`npm run gen:api`**：退出码 **0**（`openapi-typescript 7.13.0`，459.9 ms）；
产物 `frontend/src/api/generated/schema.d.ts` 的 diff = **269 insertions / 68 deletions**
（`git diff --numstat`）。⚠️ Task 8b 那条一致性守卫
`test_the_generated_typescript_client_matches_the_current_openapi_document` **绿**
（改前它是本波唯一那条红：`当前 /openapi.json 里有 149 行 description 不在 schema.d.ts 里`）。
⚠️ 生成器写出来的是 **LF**，本波按仓库工作树的既有口径还原成 CRLF
（`i/lf w/crlf`，与 Task 8b 入库时一致）。

---

## ⑤ 管理台审计只读页

| 项 | 落地 |
|---|---|
| 路由 | **`/admin/audit-logs`**，name **`admin-audit-logs`**，`component: () => import('../views/admin/AuditLogList.vue')`，`meta = { title: '审计留痕', task: 'Plan 06 Task 9 · 已交付', wide: true, requires: 'admin' }` |
| **路由数** | **15 → 16**（⚠️ 这里数的是 `smoke.mjs` 第 14 步 `ROUTES` 那一组 = 14 条业务 + `/login` + `/bind`；`router/index.ts` 的 `routes` 数组本身是 19 → **20** 项，含 3 个 redirect / root / catch-all，那一格没有守卫钉它）。钉路由数的那一条断言已同步（`eq('路由条数 = 16（学生端 6 + 教师端 4 + 管理台 **4** + 鉴权 2）', ROUTES.length, 16)`） |
| 路由顺序 | 排在 **`/admin/:resource` 之前**：`audit-logs` 形状上能被 `:resource` 吃掉，而它**不是** 23 个资源之一 → 被吃掉就会落到 `ResourceList.vue` 的「UNKNOWN RESOURCE」那一屏。⚠️ vue-router 4 按「静态段 > 动态段」打分，故顺序今天**不承重**；写在前面是让「谁先匹配」在读代码时就能回答 |
| 用的端点 | **只用既有的** `GET /api/audit-logs` —— ⚠️ **一个新端点都没加** |
| 参数名（实测端点声明后照抄） | 分页 **`limit`**（∈[1,200]，缺省 50）/ **`offset`**（≥0）；两个过滤 **`subject_kind`**（∈ `anonymous`/`student`/`teacher`）/ **`method`**（∈ `POST`/`PATCH`/`DELETE`，后端**先归一化成大写**再校验，故 `?method=post` 是 200）。⚠️ 域外值是 **422 `unprocessable_value`**（实测 `subject_kind=bogus` → 422 且点名合法值；`limit=500` → 422 `request_validation_failed`） |
| `AuditLogRead` 的真实字段（9 格，实测 `probe1.py`） | `id` / `at` / `subject_kind` / `subject_id` / `staff_no` / `method` / `path` / `status` / `target` |
| 展示了哪几列 | **就是那 9 格，一列不多**：`行 id id` / `时刻 at` / `身份类型 subject_kind` / `身份 id subject_id` / `工号 staff_no` / `方法 method` / `路径 path` / `状态码 status` / `对象 target` |
| ⚠️ **没有**的列 | **请求体**（结构上不存在）、**耗时**、**ip**、**user-agent** —— 派单 §2 第 3 条点名的后三格在 `AuditLogRead` 里**一个都没有**，已顶回（§⑦ 第 3 条）；页面上出现的那两句「一个请求体都不落」「没有耗时 / ip / user-agent」是**散文**、不是列 |
| 排序 / 信封 | `items` 按 **`id DESC`**（最新在前，与泛型 list 的升序相反）；四个信封键 `items`/`total`/`limit`/`offset`；`total` 是**过滤后**的计数。⚠️ 分页器读**响应体里**的 `offset`，不读自己发出去的 ref |
| 角色守卫复用的是哪一套 | **既有那一套，没有写第二套**：`meta.requires: 'admin'`（与另外三条 `/admin/*` 逐字同形）→ `router.beforeEach` → `stores/session.ts` 的 `satisfies('admin')`（= `kind === 'teacher' && role === 'admin'`）。⚠️ 后端那道 `require_admin` 照旧在（前端守卫挡的是「教用户点一个必然失败的按钮」，**不是**安全边界） |
| 非 admin 访问落到哪儿（实测） | 普通教师 → **`/t/dashboard`**，大屏照常渲染（产品档 **44 046 B** / dev 档 **262 122 B**），而「审计留痕」与 `subject_kind` **一个字都不在**他拿到的正文里；⚠️ 学生那一档走同一段代码、只是 `homePath` 换成 `/s/home`（本波取**教职**这一侧实测：它是安全上更吃紧的一档 —— 一个在册教职、但不是管理员） |
| 隐私 | 本页只画端点已经给的 9 格，**不**回查名册把 `subject_id` 补成人名（`AuditLogRead` 的既有裁定：鉴权失败时**根本不知道**是谁，而事后补出来的 id 会把「撞门的人」伪装成「在册的人」）。⚠️ 于是本页**不是**绕过 Task 5 那条隐私取证守卫的路：守卫扫的是**落库的 9 列**，本页画的就是那 9 列，一格不多 |
| 「恰好九格」怎么钉 | **编译期三道**：① `as const satisfies readonly { key: keyof AuditLogItem; label: string }[]`（多一列 / 写错一个键 → 红）；② `cellOf` 那个**不写 `default`** 的 `switch`（少一个 `case` → 返回类型带上 `undefined`、与声明的 `string` 冲突 → 红）；③ 一道双向 `Exclude` 型的 `_NineColumns`（`vue-tsc -b` 退出码 **0**） |
| 入口 | `ResourceIndex.vue` 新增第 04 块（`NOT A RESOURCE`，一个 `RouterLink` → `/admin/audit-logs`）。⚠️ 没有入口的页面等于不存在（深链接只有取证脚本会走）；⚠️ 而它**刻意不进** `RESOURCES` 那 23 行（进去会让后端读写矩阵的 23/9/14 与 smoke 第 12 步一起红） |
| 新增 CSS | **0 行**（复用 `.a-page` / `.a-head*` / `.a-note*` / `.a-toolbar` / `.a-pager*` / `.a-actions` / `.btn` / `.a-btn--sm` / `.select` / `.a-select--inline` / `.a-scroll` / `.data-table.a-table` / `.a-empty*` / `.a-count` / `.a-mt` / `.a-slug` / `.pill`+三个 `.pill--*` / `.a-pill--neutral` / `.a-pill--solid`）。⚠️ `check:tokens` 的**结论一字未变**（「tokens.css 之外一个色值字面量都没有」），扫描面 35 → **36** 个文件只是因为多了一个 `.vue`（下界是 25） |
| 新增依赖 | **0**（后端 `pyproject.toml` 与前端 `package.json` 都**一个字没改**） |
| **产品档深链接实测** | `scripts\serve.ps1 -Port 8020`（探针 `probe4.py`）：`GET /admin/audit-logs` → **200 + `index.html`（2 729 B，`text/html; charset=utf-8`）**；`HEAD` → 200 / 0 B；`POST` / `PUT` / `DELETE` / `PATCH` → **404 `{"error":{"code":"not_found",…}}`（`application/json`，66 B）** —— Task 7 的 `_SpaRoute` 对非 GET/HEAD **不给** PARTIAL，实测确认。⚠️ 同一发也复核了 `/admin`、`/admin/students`、`/admin/students/4`、`/s/mini-test`、`/login`、一条打错的 URL（各 200 + 2 729 B `index.html`）与两个产物（`/assets/index-NK5dQM2J.js` 167 826 B、`/assets/index-CPgg7MK0.css` 65 204 B） |
| **真渲染取证（管理员档，产品档 8020）** | 探针 `probe7.mjs`：`document.title` = **「审计留痕 · 厦大体育数智系统」**；抬头 pills = `共 59 行` / `仅 role=admin 可读` / `只读 · 无写操作`；**列头 9 个**（逐字见上）；**50 行**（每页缺省 50）；第一行 = `59 / 2026-10-14 14:45:53 / 教职 / 3 / T0003 / POST / /api/auth/login / 200 / —`；分页器 `1–50 / 共 59 行`；三个下拉的取值域 = `[20,50,200]` / `[（不过滤）,anonymous,student,teacher]` / `[（不过滤）,POST,PATCH,DELETE]`；`<section>` 3 个。⚠️ `at` **只切串、不建 `Date`**（naive 本地时刻，任何时区换算都差 8 小时）→ 新增 `present.ts::stampSecondsOf`（**秒级**；`stampOf` 是分钟级，而「一次登录 + 紧接着一次写」可以落在同一分钟里，两行显示成同一个时刻会让人以为「记重了」） |
| ⚠️ 空态 | 两档文案：有过滤时**先说「这一格可能是过滤造成的」**（并印出当前两个过滤值），无过滤时说「演示库刚复原时它就是 0 行（`demo.ps1` 灌数据走**进程内**调用、不经过 HTTP）」。⚠️ 换过滤 / 换每页行数一律把 `offset` 归零 —— 否则「第 3 页」在一个只剩 1 页的结果集上是空的，而空态会说「今天没有删除操作」（一句由分页造成的假话） |

---

## ⑥ `smoke.mjs` 两档结果

| 档 | 命令 | 步数 | 断言 | 退出码 |
|---|---|---|---|---|
| **dev** | 后端 `demo.ps1 -Port 8000` + `npm run dev -- --port 5174 --strictPort`，`PE_WEB_BASE=http://localhost:5174` | **18/18 全绿** | **560 绿 / 0 红** | **0** |
| **产品档** | `scripts\serve.ps1 -Port 8020`（同源），`PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8020` | **18/18 全绿** | **560 绿 / 0 红** | **0** |

改前基线是 **18 步 / 531 断言**，故本波 **+29**：

| 步 | 改前 | 改后 | 加了什么 |
|---|---|---|---|
| 12 | 124 | **124** | 五格数字同步（**不增拍**） |
| 13 | 33 | **53**（+20） | 「列级收窄」三拍 → 「schema 级摘列」**四**拍（+1）；「教职档 entries 都有 composite」→ 「键集合恰好三格」+「那两格一个都不在」（+1）；窄端点那一组 **18** 拍（四档矩阵 8 + 信封键 1 + 班号 1 + 五格 1 + 逐字相等 1 + `squat_score`↔`squat_30s_count` 对账 1 + `composite` 自洽 1 + 越权那一档 2 + OpenAPI 声明面 2） |
| 14 | 110 | **119**（+9） | `ROUTES` 15 → **16**（`admin-audit-logs`，admin 档一条路由 = **+6** 拍）；非 admin 档 **+3** 拍（`guard-audit-logs`：弹到 `/t/dashboard` / 大屏渲染出来了 / 审计页内容一个字都没漏给他） |
| 其余 15 步 | 264 | **264** | 一字未动 |

⚠️ **判据一字未放宽**（硬规矩 #92）。第 13 步那三拍是「**换**判据」而不是「放宽」：
改前断「别人的两格是 `null`」，今天断「那两格在**任何一档**里都不出现」——
用 `in` 判定而不是 `=== null`（`null` 与「没有这个键」在 JS 里是两件事，今天应当是后者），
故它比改前**更强**：多给一列当场红。

**第 14 步两档的逐条实测**（新路由 + 受摘列影响的两条）：

| 路由 | dev 档 DOM | 产品档 DOM | needle | 重叠 | 溢出 | `.app` |
|---|---|---|---|---|---|---|
| `admin-audit-logs`（新） | **197 332 B**（地板 20 000） | **22 537 B**（地板 6 000） | 6/6 | 0 | 0（`scrollWidth 1425 ≤ innerWidth 1440`） | `surface-base` |
| `s-mini-test`（摘列影响） | 196 611 B | 18 187 B | 2/2 | 0 | 0（`360 ≤ 375`） | `surface-base` |
| `t-student-detail`（摘列影响） | 226 692 B | 41 077 B | 5/5 | 0 | 0（`1425 ≤ 1440`） | `surface-base` |
| `guard-audit-logs`（非 admin 那一拍，不在 `ROUTES` 里） | 262 122 B | 44 046 B | 4/4（取**大屏**的内容） | —— | —— | —— |

⚠️ §Tier 那一拍两档各是「**16/16** 条给了判定，取值 = `dev`」/「= `prod`」。
⚠️ 新路由的产品档 DOM **22 537 B** 远在 6 000 那个地板之上（3.8×），
故「白屏一定红、真渲染一定绿」那条分辨率线**没有被本波推动**。

**首跑红了一拍**（不是判据错、是取证错）：见 §3.4 末段（配对键 `mini_test_id` → `course_section_id`）。
改完 dev 档与产品档各重跑一整遍（每次之前都重跑 `demo.ps1` 复原演示库），两档全绿。

---

## ⑦ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 7.1 顶回（**4 处**）

1. ⚠️⚠️ **派单 §1 的「管理台/教师页不受影响」实测不成立**（本波最实的一处）。
   `Grep` + 真渲染双向取证：`views/teacher/StudentDetail.vue` 的第 04 块**也读**
   `row.entry.composite` 与 `row.entry.squat_score`（对**被查看的学生**，不是「我自己」）。
   故摘列**必然**动到教师页。本波按裁定照做（窄端点**只**给学生、教职 403），
   教师页的处置是：「深蹲得分」改读本页已经拿到的 `squat_30s_count`（**数一个字节没变**），
   「小测综合分」本波**不再显示** + 页面上如实交代。**请控制者裁定那一格**：
   * **建议的形状**（与本仓既有口径一致）：另开一条**教师侧变体**
     `GET /api/teacher/students/{id}/normalized`，闸门用 `require_teaches_student`、
     响应体与 `NormalizedSelfRead` **逐字同形** —— 与本页已经在用的
     `GET /api/teacher/students/{id}/home`（Plan 04 收尾波落地的那一次顶回）
     **同一条处置**。⚠️ 依据是 `deps.require_teaches_student` docstring 里逐字写着的那条
     既有口径：「那个学生侧端点**刻意不接受** `X-Teacher-Staff-No`……故**教师端必须有
     自己的一条路径**」。
   * ⚠️ **本波刻意没做它**：派单逐字是「加且只加一个窄端点」，而「教职该拿到别的形状」
     是派单点名要顶回的那一格（§4 第 ② 条），故不自行扩权。
   * ⚠️ 也**没有**给 `/me` 开一条教职的路（那会让同一个路径有两种身份、两种判据，
     正是上面那条既有口径反对的形状）。
   * 教师今天要看综合分：班级周报的 `progress_board`（约束第 12 条：算式同源、窗口不同）。
2. ⚠️ **派单 §2 第 3 条点名的三格在契约里不存在**：「展示：时间、身份（工号/学号）、方法、
   路径、状态码、**耗时**、**ip**、**user-agent** 等」。实测 `AuditLogRead` 的 9 格里
   **没有**耗时 / ip / user-agent（那张表 9 列里根本没有它们的位置），
   而「身份」也**不是**学号：`subject_id` 是**代理键**（`student.id` / `teacher.id`），
   `staff_no` 才是工号且**只对教职有值**。⚠️ 派单同一条也写了「以 `AuditLogRead` schema
   的真实字段为准（`Grep` 出来照抄，不要凭空加列）」—— 本波照**后半句**执行，
   故页面上是 9 列、一个都不多。⚠️ 若要 ip / 耗时 / user-agent，那是**一次表结构改动**
   （要配一条迁移，`§13.7`）+ 一次隐私重新裁定（ip 是个人数据），不在本波。
3. ⚠️ **派单 §2 第 6 条的「15 → 16」那个数指的是一组特定的路由**：`smoke.mjs` 第 14 步的
   `ROUTES`（14 条业务 + `/login` + `/bind`），而 `router/index.ts` 的 `routes` 数组本身
   是 **19 → 20** 项（含 `/s`、`/t` 两个 redirect、`/`（root）与 catch-all）。
   两个数都对、说的不是一件事；有守卫钉的是**前者**，本波同步的也是前者。
   ⚠️ 顺带如实记：管理台的**第 4 条**路由今天与 `/admin/:resource` **形状相撞**
   （`audit-logs` 能被 `:resource` 吃掉），本波靠「排在前面 + vue-router 的静态段优先」
   两件事兜住；⚠️ 而**没有守卫钉这一格**（`_LITERAL_TAILED_SPECIAL_ROUTES` 那份绊网
   钉的是**后端**的路由遮蔽，不是前端 router 的打分）。已登记为待清扫。
4. ⚠️ **派单 §0 的「后端 py/ts/vue 与 `backend/data/**` 是 LF」这一格与工作树实测不符**
   （不是错、是口径要说清）：本机 `core.autocrlf=true`，故**全部**文本文件的工作树都是
   **CRLF**、而 index/入库 blob 是 **LF**（`git ls-files --eol` 实测未改动的
   `backend/app/main.py` / `tests/api/test_audit_api.py` / `frontend/src/router/index.ts` /
   `frontend/src/api/generated/schema.d.ts` 一律是 `i/lf  w/crlf`）。
   ⚠️ 本波**第一次编辑时踩到了它**：编辑工具把两个 `.py` 写成 `i/lf  w/lf`
   （= 与其余全部文件不同形），当场发现、当场还原成 `w/crlf`，
   此后**一律用 Python 脚本编辑**（`$env:TEMP\p06t9\edio.py`：读进来折成 LF 做替换、
   写回去还原成 CRLF），并**每改完一个文件就核** `git ls-files --eol`。
   ⚠️ 入库侧一个字节都没差（`i/lf` 恒成立），故不构成事故；如实记是为了让
   「LF」那一句在下一次派单里写准（**入库 blob 是 LF、工作树是 CRLF**）。

### 7.2 没按派单做的（**2 处**，都在 §7.1 里逐字交代过）

1. 派单 §1 说「管理台/教师页不受影响」→ 实测不成立，**教师页改了**（顶回第 1 条）。
2. 派单 §2 第 3 条点名的耗时 / ip / user-agent 三列 → **契约里没有**，**没画**（顶回第 2 条）。
   ⚠️ 除这两处外，派单逐条照做；「加且只加一个窄端点」也照做（**只加了 1 个**）。

### 7.3 本波新登记的待清扫（**5 条**）

1. **教师端的「小测综合分」**：正确的形状是 `GET /api/teacher/students/{id}/normalized`
   （§7.1 第 1 条）。⚠️ 它会让 openapi 五格再各抬一格（73/101/83/62 → 74/102/84/63），
   并要重跑 `gen:api`。
2. **`smoke.mjs` 第 14 步对 `/s/mini-test` 的两条 needle 都是静态模板文字**，
   故那一拍证明「没白屏」、证明不了第 02 块渲染出了数（本波用一次性 CDP 探针补的取证，
   §3.5）。⚠️ 判据不许改（硬规矩 #92），要改得由控制者裁定「把 needle 换成数据相关的」。
3. **前端 router 的「静态段 vs `:resource`」没有守卫**（§7.1 第 3 条）。
4. **`_enrolled_sections` 在一次请求里被查了两次**（`normalized_scores` 自己算
   `allowed_sections` 要一次、`_normalized_sections` 内部再算一次）：`enrollment` 演示库上
   120 行，故代价可忽略；要收成一次就得让 `_normalized_sections` 也接受 `sections_of`
   入参（= 两个调用方各自负责传对），本波选了「简单 > 省一次 SELECT」。
5. **`NormalizedEntryRead` / `NormalizedSectionRead` / `UnassignedEntryRead` 三个 import
   在 `feedback.py` 里只被 docstring 引用**（改前就是这样，本波没动）。⚠️ 摘列之后
   `NormalizedEntryRead` 那三处 docstring 引用已改指向 `NormalizedSelfSectionRead`，
   故 import 与引用今天**对得上**，但「一个只被散文引用的 import」这一格本身仍是债。

### 7.4 关切（沿用既有登记，本波没有新增）

* **`composite` 的量纲是混的**（次数 vs 百分位）—— 它今天住在
  `NormalizedSelfSectionRead` 的 docstring 里（改前住在 `NormalizedEntryRead`），
  措辞随之搬了一次，**内容一个字没改**。
* **`unassigned` 对教师恒为空**（Task 8 登记）—— 本波没动。
* **审计的「谁看过审计」查不到**（Task 5 登记）—— 本波**加了一页**去读它，
  而那一页自己**不产生审计行**（GET 不记），故这一格**仍然**查不到；
  页面上把这句写明了。

---

## ⑧ 最终验收

### 8.1 后端

| 项 | 基线 | 本波实测 | |
|---|---|---|---|
| `pytest`（不带 `--cov`） | 1502 passed | **1505 passed**（151.38 s） | ✅ +3 = 新加的三条 |
| `pytest --cov=app/domain --cov-branch` | 1501 passed + 1 skipped | **1504 passed + 1 skipped**（322.88 s = 5:22） | ✅ +3 |
| `app/domain/` 覆盖率四格 | **1268 / 0 / 376 / 0 / 100%** | **1268 / 0 / 376 / 0 / 100%**（`TOTAL` 行逐字相同；18 个模块各自都是 100%，其中 `app/domain/report.py` 是 121 stmts / 40 branch） | ✅ 一格未退 |
| 表数（health 口径） | 28 | **28**（`{"status":"ok","tables":28,"students":60}`，两档各实测一次） | ✅ |
| 扫描面 | **71**（pipeline 10 + db 13 + domain 18 + api 26 + auth 4） | **71**（本波**没有新增 `.py` 模块**：schema 加在既有的 `app/api/schemas/feedback.py`、路由加在既有的 `app/api/routers/feedback.py`） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | **33** | **33**（`tests/db/test_models.py` 两条 `len(...) == 33` 绿） | ✅ |
| `_MODELS_SUBMODULES` | **8**（含 `audit`） | **8** | ✅ |
| 黄金用例 | **14** | **14**（`tests/integration/test_golden_cases.py` 全绿） | ✅ |
| 迁移链 | **3** 单头（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84`） | **3** 单头，逐字未变（`demo.ps1` 三次灌库各跑了一遍 `alembic upgrade`，日志逐字是那三条） | ✅ |
| 依赖清单守卫 | 后端 7+3+1、前端 3+7 | **一字不红**（`pyproject.toml` 与 `package.json` 本波**一个字都没改**；那两条守卫在 1505 passed 里） | ✅ |

### 8.2 前端

| 项 | 基线 | 本波实测 | |
|---|---|---|---|
| `npm run build` | 退出码 0 | **退出码 0**（`vue-tsc -b && vite build`，367–372 ms，140 modules） | ✅ |
| 产物哈希 | `index-Dm5ljZoJ.css` / `index-COTDuJIB.js` | **`index-CPgg7MK0.css`（65 204 B）** / **`index-NK5dQM2J.js`（167 826 B）**；新 chunk **`AuditLogList-C3Vmc5lG.js`（9.44 kB / gzip 4.44 kB）** | ✅ 变了（应当变） |
| `npm run check:tokens` | 绿（35 文件） | **绿，退出码 0**；扫描面 **35 → 36** 个文件（下界 25），结论逐字未变：「tokens.css 之外一个色值字面量都没有」 | ✅ |
| `npm run check:dist` | 绿 | **绿，退出码 0**（`adoptFromUrl` 0 次、`fonts.googleapis.com` / `fonts.gstatic.com` 各 0 次，而三条谓词都不空转：25 个文件 / 756 627 字符） | ✅ |
| `npm run gen:api` | —— | **退出码 0**，产物 diff **269 + / 68 −**；一致性守卫绿 | ✅ |
| `vue-tsc -b` | —— | **退出码 0**（本波跑了 3 次，各 0） | ✅ |
| `node --check frontend/scripts/smoke.mjs` | —— | **退出码 0**（改了 4 次，每次都核） | ✅ |
| 路由数（smoke 第 14 步那一组） | 15 | **16** | ✅ 守卫同步 |
| 新增依赖 | 0 | **0** | ✅ |

### 8.3 禁区与指纹（探针 `verify_forbidden.py`，口径逐字照 `tests/test_refdata.py`：`sha256(把 CRLF 归一化成 LF 的字节)[:16].upper()`）

| 项 | 实测 |
|---|---|
| 四个数据指纹 | **4/4 逐字不变**：`national_standard_2014.csv` = **`D2C8E539E2FA0029`**（21 412 B）、`exercises.yaml` = **`5394B37F01DAC9AC`**（23 247 B）、`exercise_equivalence.yaml` = **`822CB86A5E998301`**（8 245 B）、`alert_rules.yaml` = **`E48E3AC82BB45BB7`**（6 037 B） |
| 18 个模板指纹 | `backend/data/prescription/` **恰好 18 个 `.yaml`**、**18 个互不相同**的指纹（前三个：`GRN-END-ABN-13` = `89842C7A0D8A6EA0`、`GRN-END-NOR-14` = `3B1DA3AAB8D6A322`、`GRN-SPD-ABN-17` = `9ADB0CAC53A572F1`） |
| `git diff a37a7f5 HEAD -- backend/data` | **空**（`--stat` 与 `git status --short -- backend/data` 都是空） |
| `backend/pe.db` | **False**（不存在） |
| `backend/data/seed/` | 目录存在、**0 文件** |
| `backend/data/**` 一字节没动 | ✅（上面三条一起证明）；⚠️ 本波**一次都没跑** `app.seed.generate` / `backfill` / `daily`，要数据一律用 `demo.ps1` |
| `frontend/dist` 未入库 | ✅ `git ls-files -- frontend/dist` **空**；`git check-ignore -v` → `frontend/.gitignore:18:dist/` |
| `.gitattributes` | **一个字节没改**（`git diff --stat a37a7f5 HEAD -- .gitattributes` 空） |
| 两个 `scripts` 目录 | **一个字节没改**（`git diff --stat a37a7f5 HEAD -- backend/scripts scripts` 空）；4 个 `.ps1` 的 **BOM 全在**（`demo.ps1` 20 167 B / 273 CRLF、`serve.ps1` 22 228 B / 359 CRLF、`backup.ps1` 3 826 B / 73、`restore.ps1` 4 866 B / 91） |
| 行尾 | 本波改过的 **14** 个文件逐个核过 `git ls-files --eol`，一律 **`i/lf`**；工作树与其余全部文件同形（`w/crlf`，`core.autocrlf=true` 的既有状态）。⚠️ `.superpowers/**` 是 `attr/-text`，故**本报告是纯 LF**（与 `task-8-report.md` / `task-8b-report.md` 逐字同形） |
| 本波起的进程 | **全部已停**（§8.5） |
| `$env:TEMP\p06t9` | **已删并复验**（§8.5） |

### 8.4 spec

| 项 | 改前 | 改后 |
|---|---|---|
| 字节数 | 316 380 B | **336 741 B** |
| 行数 | 2 851 | **3 067**（+216） |
| 行尾 | 全 CRLF | **全 CRLF**（3 067 个 CRLF、**0** 个裸 LF） |
| BOM | 无 | **无** |
| `sha256[:16]` | `865840cd3909db59` | **`f62529910792a5ff`** |

改了 **7 处**：① §1.2 第 14 条（结案那一格追加 Task 9 的第三步）；② §13.4.4 那段历史注记
（追加 Task 9 的指针）；③ §13.4.7 第 5 条（「列级收窄照旧保留」那两句**已过期**，
按硬规矩 #66 保留原文 + 就地标注过期）；④ **新 §13.4.9**（摘列 + 窄端点，含四档矩阵、
真渲染取证、五格、守卫清单）；⑤ §13.5（五格 72/100/82/61 → **73/101/83/62**）；
⑥ §13.9（新增「管理台的审计只读页」一节）；⑦ §13.11.4（断言数 531 → **560** +
两档实测 + 首跑那一红的取证）。

### 8.5 收尾（进程 / 探针 / 报告字节）

* 本波起过的 **4** 个服务进程全部已停：`demo.ps1 -Port 8000`（3 次）、
  临时 `uvicorn app.main:app --port 8000`、`npm run dev -- --port 5174`、
  `scripts\serve.ps1 -Port 8020`。⚠️ **5173 上那个不是本波起的 vite 没有被杀**
  （派单点名），收尾复验它**仍然在听**。
* `$env:TEMP\p06t9\`（**36** 个条目 = 35 个文件 + 1 个 `__pycache__\`，逐类清单见 §①）**已删**，删完复验 `os.path.isdir` → **False**；
  3 个 CDP 临时 profile 目录（`p06t9-cdp-*` / `p06t9-cdp6-*` / `p06t9-cdp7-*`）也已删并复验。
  ⚠️ `$env:TEMP` 里之前各波留下的 `pe_*` 探针**一个都没碰**。
* 本报告的字节数与入库 blob 的复核见下面那一行（写完之后核的）。

### 8.6 commit

| # | sha | 一句话 | 自洽吗 |
|---|---|---|---|
| ① | **`9a6e2cd`** | `fix(api)`: 后端摘列 + 窄端点 + 守卫同步 + `gen:api` 产物 + 前端 API 层与两个消费页 | ⚠️ **部分**：`pytest` 1505 全绿、`vue-tsc -b` 0、`npm run build` 0；而 `smoke.mjs` 在这一格上是**红的**（第 12 步五格与第 13 步还是旧判据）—— 它的同步随第 14 步那一拍一起落在 ②（同一个文件，而第 14 步那一拍要有那条新路由才跑得起来）。如实记。 |
| ② | **`61cda72`** | `feat(frontend)`: 管理台审计只读页 + 路由 + 目录入口 + `smoke.mjs` 两档同步 | ✅ 自洽：两档 smoke 各 18/18 · 560 · 退出码 0 |
| ③ | （本 commit） | `docs`: spec 7 处 + 实现者报告 | ✅ 只动 `Document/**` 与 `.superpowers/**` |

⚠️ **没有 push**（派单点名）。⚠️ **没有碰 `main`**。
