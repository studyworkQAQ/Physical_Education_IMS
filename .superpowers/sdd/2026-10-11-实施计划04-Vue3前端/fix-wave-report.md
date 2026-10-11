# Plan 04 收尾波（fix wave）结案报告 —— 三组遗留

- **分支**：`fix/plan-04-leftovers`（从 `main` = `9be4258` 起）
- **commit**：`405faf6`（第 1 组）→ `11ea1bf`（第 2 组）→ `9586015`（第 3 组）→ 本报告（第 4 个）
- **未 push**（按纪律，控制者 fast-forward 合并）
- **一句话结论**：三组全部落地。**顶回 5 处**（其中 1 处 Critical：派单对第 2 组后果的描述不成立，照它修会漏掉真正全死的那条规则）。**没按派单做的地方 5 处**（全部写明理由）。后端 **1270 passed**（+10）、`app/domain` 覆盖率四格逐字不变、`smoke.mjs` **16/16 步全绿 / 199 断言 / 退出码 0**、`npm run build` 退出码 0、五个禁区逐字未动。

---

## ① 环境与服务状态

**开工第一件事（硬规矩 #73）实测**：

| 项 | 实测值 |
|---|---|
| `node --version` | **v24.19.0** |
| `npm --version` | **11.17.0** |
| `python -c "import fastapi, sqlalchemy; …"` | **0.141.1 / 2.1.3** |
| Python | 3.11.1（无 venv，`C:\Python\python.exe`） |
| `ImportError: DLL load failed` | **没有撞上** |

**开工时的仓库状态**：`HEAD = 9be4258`、`git status --short` 空（逐字核实）。

**服务**：开工时 `127.0.0.1:8000`（uvicorn，PID 6120，**指向旧代码**）与 `::1:5173`（vite，PID 56520）都在听。

- ⚠️ **uvicorn 重启了 3 次**（它没有 `--reload`，而本波改了后端代码）：本波一律用
  `backend\scripts\demo.ps1 -Port 8000` 起（它自带两道禁区守卫、每次先删旧演示库再灌）。
  ⚠️ **`demo.ps1` 的缺省端口是 8010、不是 8000**（实测 `param([int]$Port = 8010)`），
  而 `smoke.mjs` 的 `PE_API_BASE` 缺省是 `http://127.0.0.1:8000`、`npm run gen:api`
  也把 8000 写死在 script 里 → **必须显式传 `-Port 8000`**。
- ⚠️⚠️ **vite dev server 也被我重启了一次，而这不是我的改动导致的**：第一次跑
  `smoke.mjs` 时第 14 步（13 条路由的 DOM 取证）**13 条全红**，每条的 DOM 都只有
  **1916 bytes**（= `index.html` 外壳），dump 出来的 HTML 末尾挂着 `<vite-error-overlay>`。
  逐个模块实测：`/src/App.vue`、`/src/components/IdentitySwitcher.vue`、
  **`/src/components/ApiErrorBanner.vue`（本波一个字节都没碰）**、
  `/src/views/teacher/StudentDetail.vue` **一律 500**，而 `/src/router/index.ts`、
  `/src/stores/identity.ts`、`/src/api/client.ts`、`/src/api/endpoints.ts` 与 6 个 `.css`
  **一律 200** → 是那个**长跑的 dev server 的 `@vitejs/plugin-vue` 坏了**（对所有 SFC 都失败），
  不是任何一个 SFC 有问题；同一时刻 `npm run build`（vue-tsc + vite build）**退出码 0**。
  杀掉 PID 56520、重起 `npm run dev` 之后 13 条路由全绿（DOM 从 1916 B 变成 181 152 B）。
  ⚠️ 留给下一个人的判据：**「所有 `.vue` 都 500 而 `.ts`/`.css` 都 200，且 `vite build` 是绿的」
  = dev server 该重启了**，不要去改组件。

**⚠️⚠️ 一次分支事故（不是本波代码的问题，但必须报）**：本波开工时按派单建了
`fix/plan-04-leftovers` 并切过去（`git rev-parse --abbrev-ref HEAD` 当时逐字返回它）。
在实现过程中，**另一个代理在同一个工作树上**建了 `feature/plan-05-auth`、切过去、
并提交了 `e5efe6e`（`Document/2026-10-11-实施计划05-真实鉴权与管理员角色.md`，155 行）。
于是我的第 1 组 commit 落到了 `feature/plan-05-auth` 上（`67ee3bc`）。reflog 逐字为证：

```
67ee3bc HEAD@{0}: commit: feat(api+frontend): 教师侧 GET /api/teacher/students/{id}/home…
e5efe6e HEAD@{1}: commit: docs: 实施计划 05 —— 真实鉴权 + 管理员角色…
9be4258 HEAD@{2}: checkout: moving from fix/plan-04-leftovers to feature/plan-05-auth
9be4258 HEAD@{3}: checkout: moving from main to fix/plan-04-leftovers     ← 本波开工
```

**处置**（两步都不丢任何东西）：① `git checkout fix/plan-04-leftovers` +
`git cherry-pick 67ee3bc` → 我的组 1 在**我的分支**上是 `405faf6`（父 = `9be4258`）；
② `git branch -f feature/plan-05-auth e5efe6e` → 把对方分支还原成**它自己的**那一个提交，
我的 commit 不再挂在上面。
⚠️ **控制者要知道的两件事**：
(a) `67ee3bc` 这个 sha 现在只存在于 reflog 里，内容与 `405faf6` 逐字相同；
(b) 我 checkout 回自己分支之后，`Document/2026-10-11-实施计划05-真实鉴权与管理员角色.md`
**从工作树里消失了**（它只被 `e5efe6e` 追踪，而 `fix/plan-04-leftovers` 基于 `9be4258`）——
它在 `feature/plan-05-auth` 里是安全的，`git log --oneline -1 feature/plan-05-auth -- <该文件>`
实测返回 `e5efe6e`。**共享工作树上并行开两条分支会互相踩 HEAD**，建议下一波给每个代理
一个 `git worktree`。

**另一次意外（也已处置）**：`Document/2026-10-11-需求记录-Plan05的两项重构要求.md`
在本波中途被 **IDE 的 Markdown 格式化器**改写了（`---` → `***`、`**` 被转义、表格重排，
31 插入 / 23 删除），而本波**一个字节都没打算动它**。用 `git restore -- <该文件>` 救回，
之后 `git status --short` 里它不再出现。⚠️ 这正是派单点名的那个失效形态
（「IDE 曾把陈旧且截断的缓存写回磁盘」）的一个新变种：**它不需要我打开那个文件**，
`Grep` 扫过它就够触发了。

---

## ② 第 1 组：教师侧的 `/home` 变体

### 新端点

| 项 | 值 |
|---|---|
| 路径 | **`GET /api/teacher/students/{student_id}/home`** |
| 查询参数 | `as_of`（缺省 = 服务端当天；它同时决定「本周是第几周」与「按哪一个学期判任教关系」） |
| 身份 | `staff_no: str = Depends(current_teacher)` |
| 作用域闸门 | **`require_teaches_student(session, staff_no, student_id, current_semester_of(session, day).id)`** |
| OpenAPI 声明 | `dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]` |
| `response_model` | **`StudentHomeRead`**（与学生侧**同一个**；实测两个端点在 `/openapi.json` 上指向同一个 `$ref`） |
| 住址 | `backend/app/api/routers/dashboard.py`（与既有的 `teacher_weekly_sheet` 并排） |

### `home` 的函数体抽成了什么

**`_student_home_response(session, student_id, day) -> dict`**，住在同一个
`app/api/routers/dashboard.py` 里（⚠️ 与 `_weekly_sheet_response` 不同：那一个的两个消费者
分处 `prescription.py` 与 `dashboard.py`，故它住在 `prescription.py`；本波两个消费者
**都在** `dashboard.py`，故不需要跨模块搬家）。

- `student_home` 现在只有两行：`require_scope(...)` + `return _student_home_response(...)`。
- `teacher_student_home` 也是两行：`require_teaches_student(...)` + `return _student_home_response(...)`。
- **没有复制粘贴第二份**。守卫是「两侧响应体**原文**逐字相同」（比 `resp.text`，不比
  `resp.json()`：后者会让「键序不同」与「浮点表示不同」静默通过）。
- ⚠️ **一个取舍如实记**（派单第 ③ 条问的「函数体能不能干净地抽」）：能，但它内部**自己**
  解析学期（`current_semester_of(session, day)`），而教师侧的闸门也要那个学期 →
  **教师侧那条路径上 `current_semester_of` 被查两次**。我选了「两个调用方入参逐字同形」
  而不是「把 `semester` 提成入参」：那是一次按 `is_current` 的单行查找，与首页本身那五段
  查询相比可忽略，换来的是「首页的学期」不可能与调用方各判一次而分叉。理由写在它的
  docstring 里（含硬规矩 #39 的代价段）。

### `require_teaches_student` 的学期限定：**带上了**

第四个入参传的是 `current_semester_of(session, day).id`，形状与 `teacher_weekly_sheet`
逐字相同。⚠️ 而「哪一个是本学年」的所有者是
`app.pipeline.percentile_stage.current_semester_of`，本模块**不自己查一遍 `semester` 表**。
链路（`teacher.staff_no → teacher.id → course_section.teacher_id → enrollment.course_section_id
→ enrollment.student_id`，且 `enrollment.semester_id` 与 `course_section.semester_id`
**两行都必须**等于入参那一个）由 `deps.require_teaches_student` 持有，本波**没有**改它。

### 4 条守卫（+ 1 条学期限定），全在 `tests/api/test_dashboard.py` 新支 D′

| # | 派单要求 | 守卫名 | 实测 |
|---|---|---|---|
| ① | 教师头 + 自己班的学生 → 200 且响应体与学生侧逐字相同（**两侧不同源**） | `test_the_teacher_and_the_student_variants_of_the_home_page_return_the_same_body` | 绿 |
| ② | 教师头 + 不属于自己班的学生 → 403 `forbidden` | `test_the_home_page_teacher_variant_requires_the_teaching_relation` | 绿 |
| ③④ | 匿名 → 401；学生头调教师端点 → 401 | `test_the_home_page_teacher_variant_rejects_anonymous_and_student_callers` | 绿 |
| 附 | 学期限定是承重的 | `test_teaching_last_semester_does_not_grant_access_to_the_home_page` | 绿 |

⚠️ **① 那一条比派单要求的更严一格**（这是本波唯一一处「守卫设计上的加料」，理由写在
它的 docstring 与夹具 `_seed_a_full_home` 里）：首页那五格里有**三格是聚合量**
（待办 / 未读数 / 勋章计数），而 Task 3 的降级交付丢掉的正是它们。若不先把三格造成非零，
「两侧都是空首页」也**逐字相等** → 抽没抽共用函数都绿。故夹具先造
（一行分层 + 一节课 + 4 条通知 + 1 条 `GREEN_MASTERY`），再断言
`explanation == _expected_explanation()`（在测试里**直接调 domain** 的 `explain`，
两侧不同源）、`pending_rpe == [{…}]`、`unread_notifications == 2`、
`badges == {"count": 1, "latest": "2025-09-10T06:00:00"}`，**然后**才比 `resp.text`。

`tests/api/test_dashboard.py`：**40 → 44 passed**。

### 挂 security 的操作数 / GET 数（全部用 `app.openapi()["paths"]` 实测，不用 `len(app.routes)`）

| 口径 | 改前 | 改后 |
|---|---|---|
| `/api/` 路径模板 | 65 | **66** |
| `/api/` 操作 | 93 | **94** |
| 挂 `security` 的操作 | **45** | **46** |
| GET | **58** | **59** |
| 其中匿名 GET | 48 | **48**（不变） |
| 其中挂 security 的 GET | 10 | **11** |
| 表数 | 25 | **25**（不变） |

### 那条全仓级断言改成了什么

`tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes`：

- `expected` 清单 **19 → 20 项**，新加的一行是
  `("/api/teacher/students/{student_id}/home", "get"): "X-Teacher-Staff-No"`，
  行内注释写了「为什么加」「它与 `weekly-sheet` 那一对是同一条处置」「它是四段路径、
  与 catalog 不同形故 include 顺序不承重」。
- `assert len(all_security) == 45` → **`== 46`**（消息里的算式同步改成「20 特例 + 26 CRUD 写入」）。
- `assert len(expected) == 19` → **`== 20`**。
- ⚠️ `assert len(crud) >= 70` **不动**：新路径进了 `expected` 就同时从 `crud` 里出去，
  故 `crud` 的操作数**不变**（74）。这一格实测过、并在注释里写明，免得下一个人以为漏改。
- **docstring 按硬规矩 #88 改写**，说明「口径为什么又变了」：它**没有**推翻
  「读 ⇒ 一律匿名」——挂 `security` 的理由与 `weekly-sheet` 那一对（Task 8 起就在清单里）
  逐字相同，即「一个**按人**收窄的读端点，它的收窄判据本身就是身份」
  （`require_scope` 问「是不是本人」、`require_teaches_student` 问「**本学期**是不是教他」），
  而「匿名」意味着「不收窄」。故每加一个这样的窄读端点，清单长一行、合计 +1，
  而**匿名 GET 的个数不动**（48）。⚠️ 它同时点明了这一格与收尾小修波那一格
  （`rpe-token`，那是「把一个秘密从匿名读模型上摘下来」）**不是同一件事**。

### 前端：撤掉了哪三处降级说明

| # | Task 3 的降级说明（原文位置） | 本波改成了什么 |
|---|---|---|
| (a) | 第 01 块末尾那段「⚠️ 这一格**不是**从 `/home` 读的（那个端点教师身份 401）…… 代价：`/home` 会给一段现算的中文 `explanation` …… 教师身份下拿不到那一段」 | **撤掉**。第 01 块新增一行「可解释性展开」，**原样显示** `/home` 给的 `stratification.explanation`；那段说明换成「为什么表头几格读匿名 list、而这一格读 `/home`」（`/home` 只给最新一行，而本页要显示全部历史行数与有效期） |
| (b) | 第 04 块末尾那段「⚠️ 本页**不给「勋章数」这个计数**：`/home` 的 `badges.count` 是 `COUNT(*) …`，前端再数一遍就是那个算式的**第二份**」 | **撤掉**。第 04 块的副标题现在给出**后端算的** `badges.count` + `badges.latest`；那段说明换成「两个数刻意都显示、且不合并」（表格里的行数是**跨学期**的，因为泛型 list 没有筛选参数；计数是**本学期**的），并点名 Task 3 当时为什么只能列行 |
| (c) | 第 05 块整块「教师身份读不到的五个端点」里的「拿不到的三格（待办 / 未读数 / 勋章计数）**点名说拿不到**」+「已顶回控制者：…… 那是后端改动，本 Task 无权做」 | **撤掉**。第 05 块整块换成「**他的今日**」：逐条列出 `pending_rpe`（哪一天、第几节、课次 id）、`unread_notifications` 计数、`badges.count`/`latest`、以及 `/home` 里那一格 `weekly_sheet` 的摘要。原第 05 块的**实测记录**降为第 06 块（标题改成「教师头调学生侧端点仍然是 401」，副标题「Task 3 的实测原文，收尾波之后逐字仍成立」），并给五条各加一行「**教师端走：**…」。⚠️ 保留它的理由：那五条路径**今天仍然**是 401，那不是缺陷、是「一个端点一道闸门」的口径；删掉它会让下一个人以为可以拿教师头去调学生侧端点 |

`frontend/src/api/endpoints.ts` 加 `getTeacherStudentHome(studentId, {asOf})`；
`StudentDetail.vue` 的 `useAsync` 里加一次 `getTeacherStudentHome`（`try/catch` 形状与
`weekly-sheet` 那次逐字相同，唯一要分支的错误是 **403 `forbidden`**，因为 `/home`
**不会** 404——后端把「任何一格缺数据」都折成 `null`）。
⚠️ 一处 vue-tsc 的实测坑：`weekly_sheet?: … | null` 是**可选**且可空，
故模板里 `home.weekly_sheet === null` **收窄不掉 `undefined`**（`TS18048`），
加了一个 `homeSheet` computed 把两档一起折成 `null`。

### `explanation` 与待办 / 未读数 / 勋章计数**是否真的显示出来了**

**是，四格全部实测到了**（无头浏览器 `--dump-dom`，学生 11 / `T0001` / `as_of=2025-10-12`，
DOM 181 152 B，`vite-error-overlay` 不在）：

| 格 | 页面上渲染出来的原文（节选） |
|---|---|
| `explanation` | `可解释性展开 黄色层 ← 短板 ≥2 项且体成分未判为异常（规则 Y3）。依据：你的 肺活量、立定跳远、1 分钟仰卧起坐 在校内同龄女生中低于 P25（6 个有效项里 3 项短板）；体脂率 27.7% 未超过女生 28% 阈值；历史趋势无可比历史，年均变化无从比较（无历史体测，或计分项里有缺测使国标总分不可比）。`（384 字符） |
| `unread_notifications` | `他的未读消息 1 条未读` |
| `badges` | `电子勋章（本学期） 1 枚 · 最近一枚 2025-10-12 00:00`；第 04 块副标题 `后端算的勋章数 1 枚 （最近一枚 2025-10-12 00:00 ）` |
| `weekly_sheet`（`/home` 里那一格） | `微周期第 1 周 · 系数 0.80 （与第 02 块同一份数据）` |
| `pending_rpe` | ⚠️ **`本周没有待交的（pending_rpe 是空数组）`** —— 见下面那一格如实交代 |

⚠️⚠️ **`pending_rpe` 的如实交代（不假装它能显示非空）**：这一格**端点确实返回、
页面确实渲染**，但**刚复原的演示库上它对 T0001 的 41 个学生全是空数组**（实测：逐个调
`/api/teacher/students/{id}/home?as_of=2025-10-12`，`pending_rpe.length > 0` 的一个都没有）——
因为 `demo_data` 让每个在册学生都交了每一节已发起快评的课。
故 `smoke.mjs` 第 7 步 bis **不用演示库的既有数据验它**，而是用**本脚本自己造的那一节课**
（第 2 步建在 `2025-10-13`、第 3 步发起快评、只有学生 4 交过）+ `as_of=2025-10-13`
把它逼成非空，断言 `pending_rpe` 里出现了 `SHARED.sessionId`，**并且反证**学生 4
（他交过）的 `pending_rpe` 里**没有**那一节课。⚠️ 于是「待办卡片」这一格是被**真的**
验证过的，不是只验了「键在」——但**演示时如果只看 `as_of=2025-10-12`，这一格会显示
「本周没有待交的」，那不是 bug**。

---

## ③ 第 2 组：`GREEN_MASTERY` 读的数与进步榜算的数

### 我的实测诊断（探针写在 `$env:TEMP`、`py_compile` 过、跑完删掉）

**诊断成立**，但**派单对后果的描述不成立**。逐格实测：

| 探针问的 | 实测答 |
|---|---|
| `_mini_test_improved` 读的是哪个入参 | 源码里逐字三行：`(older.normalized_score, newer.normalized_score, False)` / `(older.squat_30s_count, …)` / `(older.shuttle_20m_s, …)`。**调 `mini_test_scores(` 吗 → False** |
| `_student_signals` 组装 `mini_test_scores` 用的是列还是函数 | `scored = [row for row in minis if row.normalized_score is not None]` + `mini_test_scores=tuple(row.normalized_score for row in scored)`。**调 domain 的 `mini_test_scores()` 吗 → False** |
| `alert_stage` 有 import `app.domain.report` 吗 | **False**（改前） |
| `POST /api/mini-tests/batch` 写那一列吗 | **不写**：`feedback.py:917` 逐字是 `normalized_score=None`，行内注释「⚠️ 留 NULL：读侧现算」 |
| 演示库 `mini_test.normalized_score` | **180 行 / 180 行非空**（唯一写入方 `demo_data`） |
| 改前演示库 `alert` 分布 | **30 行**：`GREEN_MASTERY` 13 / `RED_MINITEST_DROP` 5 / `RED_RPE_SUSTAINED` 6 / `YELLOW_CHECKIN_GAP` 6（= 11 红 + 13 绿 + 6 黄） |

**⚠️⚠️ 顶回（Critical）**：派单说「**故在生产数据上 `GREEN_MASTERY` 事实上永不触发
（`mini_test_improved` 恒为假）**」——**实测不成立**。`_mini_test_improved` 的判据是
「三个指标里**任一**改善 ≥ 3%」，而另两个指标（`squat_30s_count` / `shuttle_20m_s`）
是**教师批量录入真的会写的原始列**。探针四个场景：

| 场景 | 那一列 | 深蹲 | 折返 | `_mini_test_improved` 实测 |
|---|---|---|---|---|
| A 演示库形状 | 100 → 110 | 30 → 33 | 30 → 29 | **True** |
| B **生产形状** | NULL | 30 → 33（+10%） | 30 → 29 | **True** ← 派单说这一档恒假 |
| C 生产形状 | NULL | 30 → 30 | 30 → 30 | False |
| D 同 C | NULL | 30 → 30 | 30 → 30 | False |

`normalized_score` 为 NULL 只是让那一项被 `if old is None … continue` **跳过**，
另两项仍然做功。故生产路径上 `GREEN_MASTERY` **只是丢掉了三个指标里的一个**
（判据变紧，不是恒假）。

**真正恒为假的是 `RED_MINITEST_DROP`**：它的判据 `StudentSignals.mini_test_scores`
在生产数据上是**空元组**（`scored` 的筛选条件就是「那一列非空」）→ domain 记
`insufficient_points` → **一条红牌都不落**，而那个留痕长得与「他真的只测了一次」
**一模一样**。⚠️ 于是缺陷比派单描述的**更严重**（一条规则全死，而不是一条规则少一个指标），
但**形状不同**：派单指着绿灯，实际全死的是红灯。
**照派单的原话去修、只改 `mini_test_improved` 的组装，会把真正全死的那一条留在原地。**
（本波两处都改了，见下面。）

### 改动的落地位置

| 住址 | 改了什么 |
|---|---|
| `app/pipeline/alert_stage.py` **新增** `_mini_test_composites(session, semester_id, mini_by_student) -> dict` | 每个学生的综合分序列，与 `mini_by_student[student_id]` **同序等长**。按 `enrollment` 认班（`mini_test` 没有 `course_section_id` 列）→ 按「班 × 周」挑样本（`shuttle_20m_s` 非空的行，含他自己）→ 调 **`app.domain.report.mini_test_scores`**。诊断与两档口径决定全写在它的 docstring 首节 |
| 同上 `_mini_test_improved(minis, composites, improve_pct)` | 三个指标的第一项从 `older/newer.normalized_score` 换成 `composites[-2] / composites[-1]`。⚠️ 另两项不动（它们是原始列，生产路径上有值） |
| 同上 `_student_signals(…, composites, …)` | 新增 `composites` 入参；`scored` 从「列非空的行」变成 `[(row, value) for row, value in zip(minis, composites, strict=True) if value is not None]`；`mini_test_scores` / `mini_test_ids` 各取一半（同序等长由 `strict=True` 兜） |
| 同上 `evaluate_alerts` | 批级预取里加一次 `_mini_test_composites(...)`（**整批算一次、逐人复用**，不逐人查）。⚠️ 于是模块 docstring 里那句「常数次查询（6 次…）」改成 **7 次**（+ 选课一次），并按它自己的纪律注明「这里刻意不写死 N 以外的那个 N」 |
| `app/pipeline/report_stage.py` / `app/domain/report.py` / `app/db/models/feedback.py` / `app/api/routers/feedback.py` / `app/pipeline/daily.py` | **只改 docstring**：五处「已登记为关切并移交 Plan 04」/「那一列仍有两个读者」/「Task 9 修掉了一半、留下了另一半」按实际改写成「**本波已解决**，那一列在生产代码里一个读者都没有了」，并各留一句残留代价 |

⚠️ **没有在 `alert_stage` 里重抄算式**：`tests/domain/test_report.py` 那条 AST 守卫
（`shuttle_percentile` + `mini_test_scores` 的**定义份数 == 2**、且住址都在
`app/domain/report.py`）**实测仍绿**。
⚠️ **`pipeline → domain` 是允许的**（派单要我自己实测）：`tests/architecture` **75 passed**，
`test_api_layer_dependency_direction_is_one_way` 与
`test_production_layers_never_import_app_seed` 都绿 —— 那两条只禁 `app.api` 与 `app.seed`。
⚠️ **`alert_stage` 刻意不 import `report_stage._composite_of`**：那会是一个**导入环**
（`report_stage` 已经在模块级 import `alert_stage` 的 `semester_week_of` /
`semester_week_range`）。而「按班 × 周挑样本」那一半**本来就是各调用方自己写**——
`mini_test_scores` 的 docstring 逐字交代了这条分工（「分组代码各自留在 I/O 层、
算式只有这一份」），今天已有两个先例（`feedback.normalized_scores` 与
`report_stage._composite_of`）。两侧口径由新守卫钉成逐字相等（见下）。

**两档口径决定（都写进了 docstring，硬规矩 #39）**：

1. **一个学生在两个班**（行政班 + 分层班并存；演示库上每个人都恰好 2 个）→ 按
   `course_section_id` **升序取第一个**（`ORDER BY student_id, course_section_id` +
   `setdefault`，故确定、不随一次 SQL 的结果序变）。⚠️ 而**他的行仍然进每一个他选了的班的
   样本**（口径同 `class_snapshot` 的 `roster` 与 `normalized_scores` 的按班分组）——
   少了这一格，一个班的样本会只剩「以它为第一个班的那些人」，百分位随编班方式漂移。
   ⚠️ 这一格是我**自己撞出来的**：第一版按「每人只归一个班」建 cohort，
   `test_a_student_in_two_sections_…` 实测 `45.0` 而不是 `57.5`，才暴露出来。
2. **不在任何班的学生** → 综合分一律 `None`（**不是**「拿所有无班的人当一个假班」）：
   「班内百分位」对他无定义，口径逐字同 `normalized_scores` 的 `unassigned` 那一档。
   顺带也避开了 `shuttle_percentile` 的「空样本 → `ZeroDivisionError`、刻意不兜底」契约。

### 6 条新守卫（`tests/pipeline/test_alert_stage.py` 新支 E′）+ 变异自证

`test_the_squat_for_composite_round_trip_is_exact`（夹具自校）·
`test_a_production_shaped_mini_test_row_feeds_the_drop_rule` ·
`test_the_mastery_rule_reads_the_computed_composite_not_the_raw_columns` ·
`test_the_alert_stage_composite_agrees_with_the_report_stage_one` ·
`test_a_student_in_two_sections_is_scored_against_the_lowest_section_id` ·
`test_a_student_without_a_section_gets_no_composite`

- **靶心那一条的造法是承重的**：`test_the_mastery_rule_…` 让**他自己**两次的原始测量值
  一模一样（深蹲 30、折返 10.0），只让**同班的人**变（第 2 周有人跑 5.0、第 4 周有人跑 20.0）
  → 班内百分位 25.0 → 75.0 → 综合分 27.5 → 52.5（+90.9%），而两个原始指标的改善率
  **都是 0%**。于是「`mini_test_improved` 为真」**只可能**来自综合分那一项。
- **三侧对账**：`_mini_test_composites` ↔ `report_stage._composite_of` ↔ **手算字面量**
  `52.5` / `37.5`（样本 `[10.0, 14.0]`：10.0 那一个有 1 个更慢 + 1 个并列 →
  `(1+0.5)/2×100 = 75.0` → `(30+75)/2 = 52.5`）。⚠️ 只有字面量那一侧能挡住
  「两侧一起改错」：前两侧都调 `mini_test_scores`，它们相等这件事**看似恒真**。
- **变异自证（实测，不是推理）**：把 `_mini_test_composites` 的循环体改回
  `tuple(row.normalized_score for row in rows)`，跑 5 条：
  **`5 failed, 1 warning`，退出码 1**（`test_a_student_without_a_section_…` 也红了 ——
  它的第一版只断「他没有红牌」，变异后**人人**都没有红牌故它假绿；我因此给它加了反空转：
  同一次求值里**另一个人真的拿到红牌**）。还原后 `read_bytes()` 与备份**逐字节相同**。
- **端到端那一格也红**：`test_end_to_end.py::test_the_whole_loop_runs_over_real_http`
  在变异下 `alert_count` 从 3 掉到 2。

⚠️ **夹具连带改动（两处，都是本波直接造成的）**：

- `tests/pipeline/test_alert_stage.py::_mini` **不再往那一列灌数**（`normalized_score` 一律
  `NULL`），而 `score=` 入参改成「**想要的综合分**」→ 经 `_squat_for_composite`
  换算成深蹲次数（单人班 + 折返一律 `SHUTTLE_TIED = 30.0` → 百分位恒 50.0 →
  `composite = (squat + 50) / 2`，故 `squat = 2 × composite − 50`；算式**字面写在测试里**，
  不调 `app.domain.report`）。⚠️ 于是「三次小测 100 → 90 → 80」这类既有措辞**仍然逐字为真**，
  8 个既有调用点一个都没改。**改之前本文件那六条测试全靠灌列**——那正是本波要修的陷阱
  在夹具里的翻版（测试绿、而生产数据上那条规则恒 `insufficient_points`）。
- `tests/pipeline/test_report_stage.py::_mini` 删掉了那个**已无人使用**的 `score` 入参
  （实测全文件 0 个调用点传它），并把「要给值只是为了 `GREEN_MASTERY` 那几条
  （那一处**仍读列**）」那半句按实际改写。

⚠️ **`test_end_to_end.py` 的 ③bis 改回走 HTTP**（派单没要求，理由充分）：它此前是
「本文件唯一一处不走 HTTP 的写入」，而它绕开 HTTP 的**唯一理由**逐字写在它自己的
docstring 里——「`mini_test.normalized_score` 那一列没有任何 HTTP 写入方」。
那个理由随本波**消失了**，故它改成调 `POST /api/mini-tests/batch`，并因此**顺带**成了
「教师批量录入的那一行喂得动 `RED_MINITEST_DROP`」的端到端证据。
⚠️ **改之前这一格是假绿的**：它靠一处生产路径上不存在的写入（`demo_data` 才写那一列）
把规则喂亮。⚠️ 深蹲次数由 `MINI_TEST_SQUATS = tuple(int(2 * score - 50) …)` 从
`MINI_TEST_SCORES` 换算，`shuttle_20m_s` 一律 12.0（他独自在样本里 → 百分位 50.0），
`alert_count == 3` 的断言**逐字不变**且实测仍绿。

### 演示库重灌后 `alert` 的新分布（`demo.ps1` 跑了 **3** 次，逐字可复现）

```
alert                  32        （改前 30）
预警按规则            {'GREEN_MASTERY': 13, 'RED_MINITEST_DROP': 7,
                      'RED_RPE_SUSTAINED': 6, 'YELLOW_CHECKIN_GAP': 6}
按 level              red 13 / green 13 / yellow 6     （改前 red 11 / green 13 / yellow 6）
按 status             pending 32
weekly_adjustment      13
```

**只有 `RED_MINITEST_DROP` 5 → 7 变了**（+2 行），红 11 → 13，全表 30 → 32。
`GREEN_MASTERY` **仍是 13**、`RED_RPE_SUSTAINED` 仍是 6、`YELLOW_CHECKIN_GAP` 仍是 6。
⚠️ 绿牌数不变是**巧合而不是「没生效」**：演示库上那一列本来就有值（180/180），
换成现算之后触发的是同一批人。⚠️ 其余 12 张表的行数**一律不变**
（semester 2 / student 60 / course_section 5 / enrollment 120 / prescription 60 /
class_session 8 / rpe_record 240 / training_log 840 / mini_test 180 / notification 19 /
weekly_class_report 5）。⚠️ 5 份周报的「预警汇总合计」跟着变（15 / 17 / 11 / 11 / 10），
三层完成率不变。

### 同步更正的三处（与**不改**的一处）

1. **Plan 04 计划**（`Document/2026-10-11-实施计划04-Vue3前端.md`）：
   ⚠️ **顶回**——派单说「Global Constraints 提到的『30 行』」，而计划里**没有**「30 行」：
   两处写的是「**11 条预警**」（Global Constraints 第 22 条、Task 3 的验收那一行），
   而那个 11 数的是**红色**那一档、不是全表（`smoke.mjs` 第 0 步钉的一直是 30）。
   已把两处改成 **32 条（13 红 + 13 绿 + 6 黄，并按 rule_id 展开）**，
   并在第 22 条下面加了一段脚注，把「11 → 30 → 32」这段历史与「为什么变」写清楚
   （含连带的 openapi 口径 65→66 / 93→94 / 45→46 / 58→59 / 匿名仍 48）。
   ⚠️ 用 python 写的，实测**改前改后都是 CRLF-only + 无 BOM**，`git diff --stat` 只有
   **4 插入 / 3 删除**（没有被 IDE 的 Markdown 格式化器重排）。
2. **`smoke.mjs` 第 0 步**：`alerts` 30 → **32**、`其中红色 11 条` → **13**、
   `全部 pending` 30 → **32**；标题那句 `预警 11 红 + 13 绿 + 6 黄 = 30` →
   `13 红 + 13 绿 + 6 黄 = 32`；另加一行按 `rule_id` 的分布打印 +
   一条 **`GREEN_MASTERY == 13`** 的独立断言（因为「绿牌数没变、变的是红牌里的 5 → 7」
   是这次改动最容易被读错的地方）。
3. **`demo.ps1`**：**不用改**（它的 [6/6] 步是「全部从库里数出来」，不是自报的期望值）。
4. ⚠️ **Plan 04 Task 3/5 报告里的数字一律没改**（它们是当时的取证，改了就是伪造历史）。

### 覆盖率四格

```
app/domain: 18 个文件  Stmts=1268  Miss=0  Branch=376  BrPart=0  →  100%
```

**与基线逐字相同**（1268 / 0 / 376 / 0 / 100%）—— 因为本波在 `app/domain/` 下
**只改了 docstring**（`report.py` 的 ③ 段与 `progress_board`），一行代码都没动。
全仓 TOTAL：6168 stmts / 170 miss / 1438 branch / 92 BrPart / 96%。
⚠️ 如实记：`app/pipeline/alert_stage.py` 是 244 stmts / 5 miss / 88 branch / 3 BrPart（98%），
未覆盖的 5 行与 3 个部分分支**全部是改前就有的**（762→767 / 772→774 是完成率与中断
那两段的边界、1105 是 `semester_week_of` 的 `raise ValueError`、1335-1341 是班级级的
`except Exception` 分支），我新加的 `_mini_test_composites` **两档分支都被覆盖**
（两个班 / 没有班各一条测试）。`app/api/routers/dashboard.py` 是 98 / 0 / 12 / 1（99%），
那一个部分分支 `523->565` 是 `if week is not None:` 的 `week is None` 档
（`as_of` 早于开学日），改前就在（我只是把代码搬进了 `_student_home_response`）。

---

## ④ 第 3 组：三条待清扫

### 清 1（⚠️ Plan 05 换肤的前置条件）

**实测有多少处散落色值**（先写了一个临时 Node 探针数全仓，跑完删掉）：

| 文件 | 处数 | 逐处 |
|---|---|---|
| `src/styles/base.css` | **6** | 132 `rgba(244,240,230,var(--track-arc-opacity))` · 137 `rgba(190,63,43,0.14)` · **286 `#a93623`** · 298 `rgba(244,240,230,0.35)` · 302 `rgba(244,240,230,0.08)` · 403 `rgba(20,17,15,0.028)` |
| `src/components/IdentitySwitcher.vue` | **1** | 407 `rgba(244,240,230,0.35)` |
| **合计（真色值）** | **7** | 其中 `rgba(244,240,230,.35)` **逐字重复了两遍** |
| `src/styles/admin.css:16` | (1) | ⚠️ **注释里的提及**（`#a93623`，Task 2 报的那条待清扫记录） |
| `src/styles/teacher.css:332-333` | (2) | ⚠️ **注释里的提及**（`#B3352B` / `#E8695C`，对比度实算说明） |
| `src/api/generated/schema.d.ts:2841` | (1) | ⚠️ **不是色值**：后端 docstring 原文里的「硬规矩 `#101`」（`.ts` 本来就不在扫描面里） |
| `frontend/index.html` | **0** | 去注释后 0 处 |
| `src/styles/tokens.css` | 34（改前）/ **40**（改后） | 唯一允许的住址 |

⚠️ **顶回**：派单说的「**1 个 hex + 2 个 rgba**」不准 —— 实测是 **7 处**（1 个 hex + 6 个 rgba，
分布在 2 个文件）。按硬规矩 #109，那 3 处注释里的 hex 是**对色值的提及**、不是色值本身，
故不计入（但守卫必须能把它们排掉，见下）。

**收进 `tokens.css` 的 6 个新令牌**（新一组「叠色：纸/墨 + 一个 alpha」，命名一律按**用途**、
不按色值 —— 按色值命名的话 Plan 05 换成蓝白浅色之后名字会当场撒谎）：

| 变量名 | 值 | 吃掉的处数 | 用途 |
|---|---|---|---|
| `--offset-shadow-on-ink` | `rgba(244,240,230,.35)` | **2**（base.css:298 + IdentitySwitcher.vue:407） | 深底上 `2px 2px 0` 那个偏移硬阴影的颜色 |
| `--hover-wash-on-ink` | `rgba(244,240,230,.08)` | 1 | 深底上按钮/选项悬停的那一层极淡纸色 |
| `--zebra-wash-on-paper` | `rgba(20,17,15,.028)` | 1 | 浅底表格的斑马纹 |
| `--track-hover` | `#a93623` | 1 | 主按钮悬停：比 `--track` 深一档的砖红（**Task 2 报的那条待清扫**） |
| `--track-arc-line` | `rgba(244,240,230,var(--track-arc-opacity))` | 1 | 大屏跑道弧的细线（复用既有的 `--track-arc-opacity`） |
| `--track-arc-glow` | `rgba(190,63,43,.14)` | 1 | 大屏跑道弧的那层辉光（= `--track` 的 14%） |

**6 个令牌吃掉 7 处字面量**；`base.css` 与 `IdentitySwitcher.vue` 改成 `var(--…)`，
渲染结果**逐字不变**（色值一个都没动，只是搬了家）。

**守卫**：新文件 **`frontend/scripts/check-tokens.mjs`** + `package.json` 里的
**`"check:tokens": "node scripts/check-tokens.mjs"`**（零依赖、纯静态、不碰网络）。
`smoke.mjs` 的**第 15 步**也 `spawnSync` 它一次，故「`npm run smoke` 全绿」**蕴含**
「设计令牌没有散开」，而它自己也能单独跑（Plan 05 换肤时会一直跑它）。

**谓词怎么排除假阳性**（派单第 ② 条问的「会不会误伤 `url(#id)`」）：

1. **先剥注释再扫**：`/* … */` 与 `<!-- … -->` 两种，剥的时候把非换行字符换成空格
   （行号因此仍然对得上原文）。→ 那 3 处注释里的提及被消掉。
2. **hex 只认 CSS 合法的 3 / 4 / 6 / 8 位，且后面必须是一个词边界**：
   `/#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/`。
   ⚠️ **刻意不写 `{3,8}`**：那会把 `#12345`（5 位，不是合法色值）也算进来。
3. **函数式**：`/\b(?:rgba?|hsla?)\(/`（把 `hsl(` / `hsla(` 一起收进来 ——
   换肤很可能用 HSL，漏了它就是守卫上的一个洞）。
4. **9 个负控逐个断言不命中**（硬规矩 #107：先对已知反例验证谓词）：
   `#app`（CSS 的 id 选择器；`p` 不是十六进制字符 → 词边界不成立）、
   `url(#lg1)` / `url(#gradient-1)`（SVG 引用）、`pathLength=100`（没有 `#`）、
   `#12345`（5 位）、`#a1b2c3d4e5`（10 位）、`grid-template-rows: repeat(2, 1fr)`、
   `var(--track)`、`href="#top"`。
5. **8 个正控逐个断言命中**：`#fff` / `#ffff` / `#ffffff` / `#ffffffff` /
   `rgb(1,2,3)` / `rgba(1,2,3,.4)` / `hsl(210 100% 50%)` / `hsla(210,100%,50%,.5)`。
6. **3 个「注释里的色值」样本**：断言它们在**原文**上命中（否则本自校失去意义）、
   剥注释后**不**命中（证明剥注释是承重的）。
7. **反空转**：`tokens.css` 自己必须数到 **≥ 20** 处（实测 40）；扫描面 **≥ 25**
   个 `.css`/`.vue`（实测 **31** = 6 css + 25 vue）。少了这两格，
   「0 处 offender」与「谓词写坏了 / `SRC` 指错了」在颜色上无法区分。

**已知的两个真会命中的反例（都写进了脚本的 docstring）**：
`硬规矩 #101`（`101` 恰好是 3 个十六进制字符 + 词边界）—— 靠「先剥注释」消掉，
它只出现在注释里；`a#fff0`（一个 4 位十六进制的 id 选择器与 4 位 hex 色值**在语法上无法
区分**）—— 全仓今天没有这种 id，若将来出现，正确处置是**给它改名**，不是放宽谓词。

⚠️⚠️ **落地时自己撞上两次同一个坑，已写进两处注释留给下一个人**：
我在 `admin.css` 的**注释里**写了一个 glob（`src/` 后跟「星号 星号 斜杠 星号」），
又写了一个裸的注释终止符 —— 而 **CSS 的注释在第一个终止符就结束了**，
于是后面那半段注释被当成 CSS 解析。两个后果都实测到了：
① `check-tokens.mjs` 报出 **4 处假 offender**（全在注释里）；
② **`npm run build` 直接失败**（`lightningcss` 的 minifyCSS 抛错，退出码 2）。
⚠️ 这**不是**守卫太严：它的剥注释与 CSS 解析器**同口径**，而 ② 说明连浏览器/构建器
也会读错。处置是**改写那句注释**（把那三个字符用中文 spelled out），不是放宽守卫。
`check-tokens.mjs` 自己的 JSDoc 里同样两处用 `*\/` 转义（JS 块注释里 `\` 无义、
但 `*` 后面不接 `/` 就不会终止注释）。

**守卫实测**：`npm run check:tokens` → 负控 9 ✓ / 正控 8 ✓ / 假阳性样本 3 ✓ /
`tokens.css` 40 处 ✓ / 扫描面 31 ✓ / **全绿：31 个文件里，`tokens.css` 之外一个色值字面量都没有** /
**退出码 0**。

### 清 2（两处过期注释）

派单点名的两处，**都改成了不写死数字**：

| 文件 | 改前 | 改后 |
|---|---|---|
| `src/api/client.ts`（`identityHeaders` 的 JSDoc） | `⚠️ 未选身份时返回空对象 —— **47 个 GET 全部匿名**（计划约束第 3 条），故「没选身份」不是错误，只是不能写。` | 只说口径（匿名 GET 是本仓的常态；计划那句「GET 全部匿名」的措辞是错的，Task 2 顶回过），**并显式声明「本处刻意不写多少个」**，把机器口径指向两个住址：`scripts/smoke.mjs` 的**第 12 步**（从 `/openapi.json` 反查，逐个 (路径, 方法) 看有没有 `security`）与后端 `test_the_identity_headers_are_registered_as_openapi_security_schemes`（字面清单 + 全仓合计断言） |
| `src/App.vue`（文件头第 2 条） | `（约束：47 个 GET 匿名、写请求要头）` | `（口径：读侧大部分匿名、写请求一律要头，另有几个按人收窄的窄读端点也要头；⚠️ **具体多少个刻意不写在这里**，机器口径见 api/client.ts 的 identityHeaders 注释）` |

⚠️ **顺手清了同族的另外三处**（派单没点名；同一个数在 Plan 04 的 5 个 Task + 收尾波里
变了 4 次，留着就一定会再过期一次）：

- `src/api/endpoints.ts` 文件头第 1 条那一大段硬编码（`GET 共 58 = 48 匿名 + 10 挂 security`、
  `26 + 9 = 35`、`45 − 35 = 10`、`19 个特例端点里 11 个教师头 / 8 个学生头`）
  → 换成「刻意不写各有多少个 + 机器口径的两个住址 + 想知道某一个端点要哪个头就看
  **它自己那一格的注释**（那一格与端点定义住在一起、不会与合计数字一起过期）」。
- `src/api/endpoints.ts` 里 `listStudentNotifications` 的「47 个匿名 GET 里已经包括 …」
  → 改成「那一堆匿名 GET 里已经包括 …；⚠️ 具体多少个刻意不写在这里」。
- `src/router/index.ts` 的 `requires` 那一格「48 个 GET 匿名」→ 同上处置。

### 清 3（`smoke.mjs` 会写脏演示库）

**「删不掉的学期」到底是哪一档 —— 实测清楚了，⚠️ 顶回派单**：

> 派单原文：「含一个**删不掉**的学期 —— 第 10 步建的 `semesters` 是 `on_delete='forbid'`…
> ⚠️ **不对，`semesters` 实测是 `restrict`**，Task 4/5 的报告说它 DELETE 返回 405；
> 请你实测清楚到底是哪一档、为什么删不掉」

**实测结论：是 `forbid`，不是 `restrict`。** 证据链（三段都是运行时/源码口径）：

1. `backend/app/api/routers/catalog.py:186` —— `semesters` 那一行逐字是
   `"on_delete": ON_DELETE_FORBID`，行内注释「全库的时间轴锚点：9 张表按 semester_id 归组，
   删一个学期没有安全语义。『这个学期不要了』的正确做法是把 is_current 置 False」。
2. 泛型工厂对 `forbid` 的资源**根本不注册 DELETE 端点** → 打过去是
   **405 `http_405`**（`smoke.mjs` 第 10 步与第 11 步各断言过一次，后端
   `test_prescription_api.py` 那句「26 而不是 27」也是它）。
3. ⚠️ 而 **`restrict` 的表现是 409 `integrity_conflict`**：端点**存在**、删的时候被子表挡住。
   同一步里 `DELETE /api/students/4` 那一拍就是它（实测 409，且 `message` 点名了子表
   「仍指向它」）。`catalog.py` 里 23 个资源的分布是 **restrict 12 / forbid 10 / cascade 1**
   （`smoke.mjs` 第 12 步逐格断言）。

⚠️ **派单那半句把两档混在了一起**：「实测是 `restrict`、DELETE 返回 405」——
**405 是 `forbid` 的表现，`restrict` 的表现是 409**。`smoke.mjs` 第 10 步此前印的
「`semesters` 是 23 行里唯一『可写 + `on_delete="forbid"`』的资源」是**对的**，
（⚠️ 严格说「唯一」也不准：可写的 9 个里 `semesters` 是唯一 `forbid` 的，
而全仓 `forbid` 的资源有 10 个，另 9 个是只读的、本来就没有 DELETE。）

**处置：选了「打印警告」这一侧**（控制者的倾向），**没有**做「自己复原」。理由逐条：

- 自己复原要么**绕过 HTTP 直接删库**（那它就不是联调脚本了，而「用真 `fetch` 打真 uvicorn」
  是它存在的全部理由），要么**给 `semesters` 开一个 DELETE 端点**（那会推翻 `forbid`
  那条口径，而那条口径的理由是「9 张表按 semester_id 归组，删一个学期没有安全语义」）。
- 而那 5 样写入**不只**那个学期：第 2 步一节课 + 第 4 步又一节（未发起快评的）、
  第 5 步一条快评、第 6 步一次打卡、第 9 步一条被处置的预警（+ 它写的一条
  `weekly_adjustment`）+ 第 10 步一次「建了又删掉」的教师。删它们要按外键顺序逐个来
  （`rpe_record → class_session`、`notification → alert`、`weekly_adjustment → alert`），
  代价高且容易漏 —— 而**漏一个的表现是「第二次跑红在第 0 步」**，与「忘了重灌」同形，
  反而更难查。

落地：

- **开头**打印一次警告（`⚠️⚠️ 本脚本会写脏演示库（建一节课 / 交一条快评 / 打一次卡 /
  处置一条预警 / 建一个删不掉的学期）。跑完请重跑 backend\scripts\demo.ps1 再跑第二次；
  第 0 步核实的就是「一个刚复原的演示库」的行数，脏库上它会红。`）——
  ⚠️ 派单要的就是这一句，理由是「跑完才看到的话，已经脏了」。
- **收尾**那一段从 2 行扩到 11 行：点名 5 样写入、点名 `forbid` → 405 与
  `restrict` → 409 两档的区别（并指出第 10 步里哪一拍是哪一档）、点名「刻意不自己复原」
  与「第 0 步因此同时充当『你是不是忘了复原』的守卫」。
- **文件头**那一节从 5 行扩到 24 行，同一条处置的完整版（含「一个『自己复原』的实现
  要么…要么…」那段论证）。
- **`package.json` 的 `smoke` script 描述**：JSON 不支持注释，故用 npm 的约定
  **`"//"` 键**（`package.json` 顶层，紧挨 `description`），逐字写明
  「`npm run smoke` 会**写脏演示库**（第 2 步…第 10 步建一个学期——而 `semesters` 是
  `on_delete='forbid'`、DELETE 端点根本不注册，故那一行删不掉）。跑完请重跑
  `backend/scripts/demo.ps1` 再跑第二次；smoke 的第 0 步核实的就是…脏库上它会红。
  ⚠️ `npm run check:tokens` 是只读的」。

### ⚠️ 本波**不清**的 2 条（派单留给 Plan 05 或更后）—— 我也认为不便宜，没顺手做

- **④ `interest-surveys` 的 JSON 文本域只有 parse 级校验**：要清它得引入一套 JSON Schema
  校验器 + 给 23 个资源里那几个 `JsonText` 列各写一份字段契约，而契约的**所有者**该是谁
  （`app/db/models` 还是 `app/api/schemas`）本身要先裁定一次。不便宜。
- **⑤ 管理台刻意无筛选（大表只能翻页）**：要清它得给泛型 list 端点加筛选参数
  （那是后端 API 面的改动，会动 `Page` 的契约与 `catalog.RESOURCES` 的每一行），
  而派单第 12 条已经裁定过「前端客户端过滤」是当前口径。不便宜。

---

## ⑤ `smoke.mjs` 重跑：**16 步 / 199 条断言 / 退出码 0**

⚠️ **步数从 15 变成 16**：派单说「`smoke.mjs` 也要加一步（或在第 7 步里加一拍）覆盖新端点」——
**我两者都做了**（第 7 步加一拍覆盖新端点；另加第 15 步跑 `check-tokens`）。

```
步数 16/16 全绿 · 断言 199 绿 / 0 红
后端 http://127.0.0.1:8000 · 前端 http://localhost:5173 · as_of 2025-10-12 · 教师 T0001 · 学生 4
退出码 0
```

| 步 | 标题（截断） | 断言 | 本波动的地方 |
|---|---|---|---|
| 00 | 演示库复原核实 | **12**/12 | `alerts` 30 → **32**、红 11 → **13**、pending 30 → **32**；+ `rule_id` 分布打印与 `GREEN_MASTERY == 13` 断言 |
| 01 | `/api/health` → tables == 25 | 5/5 | — |
| 02 | 教师头 POST class-sessions → 201 | 7/7 | — |
| 03 | open-rpe 拿口令；匿名 list 里不含它 | 9/9 | — |
| 04 | 匿名读口令 401 / 教师头 200 | 7/7 | — |
| 05 | 学生头 POST rpe-records → 201 / 再交 409 | 9/9 | — |
| 06 | 学生头 POST training-logs → 201 | 10/10 | — |
| 07 | weekly-sheet（学生侧 + 教师侧变体） | **38**/38 | **+ 第 7 步 bis**：`/home` 教师侧变体一整拍 |
| 08 | 教师头 dashboard / 周报 | 14/14 | — |
| 09 | 预警处置三档 + 409 + 422 | 13/13 | — |
| 10 | 写入侧强制（semesters DELETE 是 405） | 13/13 | — |
| 11 | 只读资源被写 → 405 | 6/6 | — |
| 12 | 从 `/openapi.json` 反查 23 行（5 拍） | **22**/22 | 路径模板 65→**66**、操作 93→**94**、挂 security 45→**46**、GET 58→**59**、匿名 GET 仍 **48** |
| 13 | 学生端那两个新端点 | 14/14 | — |
| 14 | 13 条路由的无头浏览器 DOM 取证 | **16**/16 | `t-student-detail` 加两条 needle（`可解释性展开` / `他的今日`） |
| 15 | **`npm run check:tokens`（新）** | **4**/4 | 退出码 0 + 自报「全绿」+「`tokens.css` 里有 40 处」（反空转，≥ 20） |
| | **合计** | **199** | 基线 15 步 / 172 断言 |

**第 7 步 bis 的 12 条断言**（新端点的联调守卫）：学生侧 200 · 教师侧 200 ·
**两侧 `resp.text` 逐字相同** · `/home` 恰好 9 个键 · `explanation` 非空（实测 384 字符）·
`unread_notifications` 是数 · `badges` 是 `{count, latest}` 两格 ·
从 `/api/alerts` **现找**一个「有绿牌 ∧ 由 T0001 本学期任教」的学生（实测找到 8 个，
取第一个）并断言他的 `badges.count > 0` · 班里找得到一个不是学生 4 的人 ·
用**本脚本自己造的那一节课** + `as_of=2025-10-13` 断言 `pending_rpe` 里出现了它 ·
**反证**学生 4（他交过）的 `pending_rpe` 里**没有**它 · 不任教 403 `forbidden` ·
学生头 401 `unauthenticated` · 匿名 401 `unauthenticated` · 反方向（教师头调学生侧）仍 401。

⚠️ **第一次跑是 15 绿 / 1 红**（第 14 步 13 条全红），而**原因不在本波代码里**：
那个长跑的 vite dev server 对**所有** `.vue` 返回 500（连本波一个字节都没碰的
`ApiErrorBanner.vue` 也是），而 `npm run build` 同一时刻是绿的 → 重启 dev server 后
16/16 全绿。完整判据写在 ① 节。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 顶回控制者的地方：**5 处**（其中 1 处 Critical）

| # | 顶回什么 | 实测证据 | 严重度 |
|---|---|---|---|
| **1** | **第 2 组：「生产数据上 `GREEN_MASTERY` 事实上永不触发（`mini_test_improved` 恒为假）」不成立** | `_mini_test_improved` 是「三个指标里**任一**改善 ≥ 3%」，另两个（`squat_30s_count` / `shuttle_20m_s`）是教师批量录入**真的会写**的原始列。探针场景 B（列 NULL、深蹲 30→33）实测返回 **True**。**真正恒不触发的是 `RED_MINITEST_DROP`**（判据 100% 是那一列 → 空元组 → 恒 `insufficient_points`，而那个留痕与「他真的只测了一次」同形） | **Critical**：照派单原话只改 `mini_test_improved` 的组装，会把**真正全死的那一条规则**留在原地，而报告会写「已解决」 |
| **2** | **第 3 组清 1：散落色值不是「1 个 hex + 2 个 rgba」，是 7 处** | 探针逐个命中：`base.css` 6（132 / 137 / 286 / 298 / 302 / 403）+ `IdentitySwitcher.vue` 1（407）；另有 3 处是**注释里的提及**（`admin.css:16`、`teacher.css:332-333`），按硬规矩 #109 不计入 | 中：照「3 处」写守卫会漏 4 处，而漏掉的那 4 处正是换肤时会漏改的 |
| **3** | **第 3 组清 3：删不掉的学期是 `forbid`（405），不是 `restrict`** | `catalog.py:186` 逐字 `ON_DELETE_FORBID`；`forbid` → `DELETE` 端点根本不注册 → **405 `http_405`**；`restrict` → 端点存在、被子表挡住 → **409 `integrity_conflict`**（同一步里 `DELETE /api/students/4` 那一拍）。⚠️ 派单那半句「实测是 `restrict`、DELETE 返回 405」把两档混了 | 中：写进代码注释就会把下一个人指错方向 |
| **4** | **第 2 组第 3 条：Plan 04 计划的 Global Constraints 里没有「30 行」** | 两处写的是「**11 条预警**」（第 22 条与 Task 3 的验收行），而那个 11 数的是**红色**那一档、不是全表（`smoke.mjs` 第 0 步钉的一直是 30）。已按 32（13+13+6）更正两处 + 加一段脚注把「11 → 30 → 32」这段历史写清 | 低：改的是散文，但按派单原话去找「30 行」会找不到、于是不改 |
| **5** | **验收第 8 条：第五个指纹「18 套处方模板合计 `83DA02814A29679C`」的算法在派单里没给，我复现不出来** | 后端钉的是 **18 个逐文件指纹**（`tests/domain/test_prescription_templates.py::test_template_yaml_fingerprints_are_pinned`，`TEMPLATE_FINGERPRINTS` 18 项，sha256 前 16 位大写、**先归一化为 LF**）。我用三种自然组合都试过：按名排序拼接字节后 sha256 前 16 位 = `42B46A2F1F326900`；18 个 16 位十六进制串直接连接再哈希 = `192749BA0A7A6926`；换行连接再哈希 = `38A1098683B8F513` —— **都不是 `83DA02814A29679C`**。故改用**更强的两道**（见 ⑦） | 低：结论不变（`backend/data/**` 一个字节都没动），但「五个指纹逐字不变」这句我不能照抄 |

⚠️ 另外**两处不算顶回、但要显式交代的核实结果**（派单点名要我实测的）：

- **第 2 组第 2 条「`pipeline` import `domain` 是允许的，但请你自己实测确认」** →
  **实测确认允许**：`tests/architecture` **75 passed**（含
  `test_api_layer_dependency_direction_is_one_way` 与
  `test_production_layers_never_import_app_seed`），那两条只禁 `app.api` 与 `app.seed`。
  守卫**没有红**，故不需要顶回。
- **第 1 组第 ③ 条「若你实测发现 `home` 的函数体没法干净地抽成共用（例如它内部依赖了
  `current_student` 的返回对象）」** → **能干净地抽**：它内部**不**依赖 `requester`
  （`require_scope` 是唯一用到它的地方，抽出来之后留在端点里）。唯一的取舍是
  「学期解析在函数体内部」→ 教师侧那条路径上 `current_semester_of` 被查两次；
  我选了保持两个调用方入参逐字同形，代价写进 docstring。故不需要顶回，也不需要替代方案。

### 没按派单做的地方：**5 处**（全部写明理由）

1. **第 2 组：我同时改了 `StudentSignals.mini_test_scores`（`RED_MINITEST_DROP` 的判据），
   派单只点名 `mini_test_improved`。** 理由：两处读的是**同一列**、要的是**同一个算式**、
   改的是**同一段代码**（`_student_signals` 里相邻的三行），而后者才是**真的全死**那一条
   （见顶回 #1）。只修一半会留下「一条规则在生产数据上恒不触发」而报告写「已解决」——
   那正是本波要消灭的那类误导。⚠️ 代价：`alert` 分布因此变了（5 → 7），
   派单预期的是「`GREEN_MASTERY` 变」，实测变的**恰好不是它**。
2. **清 2 顺手清了另外三处同族过期数字**（`endpoints.ts` 文件头那段 58/48/10 的硬编码、
   `endpoints.ts` 里 `listStudentNotifications` 的「47 个匿名 GET」、
   `router/index.ts` 的「48 个 GET 匿名」）。理由：派单自己给了判据
   （「这个数在 Plan 04 的 5 个 Task 里变了 4 次，写死就一定会再过期一次」），
   而这三处与它点名的两处是**同一个数**。
3. **`smoke.mjs` 从 15 步变成 16 步**（派单说「加一步**或**在第 7 步里加一拍」，我两者都做了）。
   理由：新端点要的是**联调**守卫（真 `fetch` + 真身份头），`check-tokens` 要的是
   **静态**守卫（不碰网络），两者的失败原因完全不同，挤在一步里会让「哪一类坏了」
   变成一件要看断言名才知道的事。
4. **`test_end_to_end.py` 的 ③bis 从「直接落库」改成「走 HTTP」**（派单没要求）。
   理由：它绕开 HTTP 的**唯一理由**（「那一列没有 HTTP 写入方」）随本波**消失了**；
   留着就是一处「生产路径上不存在的写入把测试喂绿」，而改完它**顺带**成了
   「教师批量录入的行喂得动 `RED_MINITEST_DROP`」的端到端证据。
   ⚠️ `alert_count == 3` 的断言逐字不变、实测仍绿。
5. **`test_report_stage._mini` 删掉了那个已无人使用的 `score` 入参**（派单没要求）。
   理由：它的 docstring 因本波变成假的（「要给值只是为了 `GREEN_MASTERY` 那几条
   （那一处**仍读列**）」），而实测全文件 **0 个**调用点传它 —— 留着一个
   「会把数灌进一列没人读的列」的入参，正是本波要消灭的那类陷阱。

### 待清扫 / 关切（本波新登记 3 条 + 沿用 4 条）

**新登记**：

1. **`mini_test.normalized_score` 那一列如今在生产代码里一个读者都没有**（只剩
   `MiniTestRead` 把它读出去给调用方看，以及 `demo_data` 写它）。于是一个读
   `GET /api/mini-tests` 的调用方会看到「演示库上它有值、生产库上它恒空」。
   清它要动 schema（删列 = 一次迁移）与演示数据生成器，**不在本波范围里**。
   已写在 `MiniTest` 模型、`domain/report.py`、`report_stage.py`、`feedback.py`
   四处 docstring 里（互相指向同一个住址）。
2. **`alert_stage` 那一份 `mini_test` 查询不夹周次上界**（⚠️ **改前就有**，本波只换了
   「分从哪来」、没换「读哪些行」）：`report_stage.class_snapshot` 显式夹了
   `MiniTest.week <= week` 并写明「不夹上界的话，周日生成第 3 周的周报会把第 4 周那份
   还没发生的小测当成『本次』——一次静默的**读未来**」，而预警这一侧没夹 →
   教师录入了未来周次的成绩（`MiniTest.week` 刻意没有「不得录未来周次」的 CHECK），
   当天的批处理就会把它算进 `RED_MINITEST_DROP` 的三个点里。
   修它要同时改 `tests/pipeline/test_alert_stage.py` 里**六条**测试的夹具
   （它们的小测周次全在 `as_of` 之后），不是一次能顺手做完的改动。
   已写在 `_mini_test_composites` 的 docstring 末段。
3. **一个学生在两个班时，预警侧只有一个综合分**（按 `course_section_id` 升序取第一个班），
   而周报侧两个班各有一个 → 两侧**不保证**相同。⚠️ 这与本波修掉的那条关切**不是同一件事**
   （那条是「算式不同源」，已解决；这条是「预警按**人**落、周报按**班**算」的结构差异）。
   要消除它就得让 `alert` 也按班落，那是 schema 改动。已写在两处 docstring 里。

**沿用（本波没动）**：

4. 三个写入端点（教师覆盖 / 手动重生成 / 预警处置）仍只过 `require_teacher`（在册），
   不过任教关系闸门（Plan 03 起登记的关切）。
5. `interest-surveys` 的 JSON 文本域只有 parse 级校验（派单点名本波不清）。
6. 管理台刻意无筛选，大表只能翻页（派单点名本波不清）。
7. ⚠️ **本波新发现、但刻意没改的一处过期散文**：`app/api/routers/feedback.py:94` 与 `:504`
   两处仍写「已移交 Plan 04」/「收窄它们是一次一行的改动，已移交 Plan 04」，
   而 Plan 04 已结案、那两处说的是「把三个写入端点的作用域从『在册教师』收窄到
   『任教关系』」（= 上面第 4 条）——它**没被做**，故那两句现在是过期的。
   ⚠️ 不改的理由：改它等于把第 4 条关切重新裁定一次（是「收窄」还是「刻意不收窄」），
   那是一次口径决定、不是一次文案修正，超出本波三组的范围。

---

## ⑦ 最终验收

| 项 | 基线 | 本波结案 | 判据 |
|---|---|---|---|
| 后端 passed（不带 `--cov`） | 1260 | **1270 passed, 1 warning in 145.21s** | `python -m pytest -q --no-cov` |
| 后端 passed（带 `--cov`） | 1259 + 1 skipped | **1269 passed, 1 skipped in 288.81s** | `--cov=app --cov-branch` |
| `app/domain/` 覆盖率四格 | 1268 / Miss 0 / 376 / BrPart 0 / 100% | **1268 / Miss 0 / 376 / BrPart 0 / 100%**（18 个文件，**逐字不变**） | 同上 |
| 全仓 TOTAL | — | 6168 stmts / 170 miss / 1438 branch / 92 BrPart / **96%** | 同上 |
| 表数 | 25 | **25** | `len(Base.metadata.tables)` |
| 扫描面（`SCANNED_DIRS` 四层） | 60 | **60**（本波没往 `app/` 加 `.py`） | `app/{pipeline,db,domain,api}` 的 `.py` 数 |
| `backend/**/*.py` | 130 | **130** | `pathlib.rglob` |
| `/api/` 路径模板 | 65 | **66** | `app.openapi()["paths"]`（⚠️ **不用** `len(app.routes)`） |
| `/api/` 操作 | 93 | **94** | 同上 |
| 挂 `security` 的操作 | **45** | **46** | 同上 |
| GET | **58** | **59** | 同上 |
| 匿名 GET / 挂 security 的 GET | 48 / 10 | **48 / 11** | 同上 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`tests/db/test_models.py` 两条断言绿） | 全量测试 |
| 黄金用例 | 14 | **14**（`tests/integration/test_golden_cases.py` 全绿） | 全量测试 |
| `frontend/src/**` 文件数 | 42 | **42**（新文件在 `scripts/`，不在 `src/`） | `Get-ChildItem -Recurse -File` |
| `npm run build` | 退出码 0（119 modules，CSS 65.50 kB / JS 148.05 kB） | **退出码 0**（**119 modules**，主 chunk CSS **65.78 kB** / JS **148.15 kB**，gzip 10.51 / 52.62） | `vue-tsc -b && vite build` |
| `@ts-ignore` / `as any` | 0 | **0** | `Select-String -Path src\*.ts,src\**\*.ts,src\**\*.vue,src\*.vue` |
| `npm run check:tokens` | （不存在） | **退出码 0**（负控 9 / 正控 8 / 假阳性样本 3 / tokens.css 40 处 / 扫描面 31） | 新守卫 |
| `smoke.mjs` | 15 步 / 172 断言 / 退出码 0 | **16 步 / 199 断言 / 0 红 / 退出码 0** | `npm run smoke` |

### 禁区（五道，逐条实测）

| 禁区 | 实测 |
|---|---|
| **五个指纹逐字不变** | ① `D2C8E539E2FA0029`（国标评分表）② `5394B37F01DAC9AC`（动作库）③ `822CB86A5E998301`（等价表）④ `E48E3AC82BB45BB7`（预警规则）—— 四个由 `tests/test_refdata.py` / `test_refdata_prescription.py` / `test_refdata_alerts.py` 里的**字面量**钉住，实测 **107 passed**。⑤ 「18 套处方模板合计 `83DA02814A29679C`」—— ⚠️ **顶回 #5**：那一格的**组合算法派单没给**，我用三种自然组合都复现不出该值；后端钉的是 **18 个逐文件指纹**（`test_template_yaml_fingerprints_are_pinned`，实测 **1 passed**，且 `len(TEMPLATE_FINGERPRINTS) == 18`）。故第 ⑤ 个改用**更强的两道**：逐文件指纹测试绿 + 下面那条 `git diff` 为空（字节级同一，比任何组合哈希都强） |
| **`git diff 9be4258 HEAD -- backend/data` 为空** | **空**（`git diff --stat 9be4258 -- backend/data` 无输出）；另 `backend/data/**` 实测 **24 个文件**、一个都没进本波的 `git status` |
| **`Test-Path backend\pe.db`** | **False** |
| **`backend/data/seed/` 文件数** | **0**（目录存在、0 文件） |
| **`git status --short` 里没有 `node_modules` / `pe_demo.db` / `frontend/dist`** | **一个都没有**（`git check-ignore -v` 实测 `backend/.coverage` 命中 `.gitignore:7`、`backend/pe_demo.db` 命中 `.gitignore:38`；`frontend/.gitignore` 盖住 `node_modules` 与 `dist`） |
| **`demo.ps1` 自带的两道禁区守卫** | 每次跑都打印 `禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`（本波跑了 **3** 次，3 次都 ✓） |
| **没跑过三个 CLI** | `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` **一次都没跑**（要数据一律走 `demo.ps1`） |

### 行尾与 BOM（`read_bytes()` 实测，改前改后都量过）

- `backend/**`：`core.autocrlf=true`，工作树 **CRLF-only**、入库 **LF-only**（HEAD 的 blob
  实测 `CRLF=0`）—— 与基线同档。
- `frontend/**`：实测**全部 CRLF-only + 无 BOM**（`tokens.css` 194 CRLF / `base.css` 416 /
  `admin.css` 467 / `IdentitySwitcher.vue` 414 / `client.ts` 352 / `App.vue` 271 /
  `endpoints.ts` 1004 / `router/index.ts` 226 / `smoke.mjs` 1010 / `package.json` 28 /
  `StudentDetail.vue` 1059）。⚠️ 新文件 `check-tokens.mjs` 是 **LF-only**
  （`Write` 工具写的；`smoke.mjs` 在 HEAD 上也是 LF-only，故同档），
  `autocrlf=true` 下一次检出会变 CRLF。
- ⚠️ 三个文件在工作树里是 **MIXED**（`endpoints.ts` 1037 CRLF / 1038 LF、
  `tokens.css` 211/213、`schema.d.ts` LF-only）：那是 `SearchReplace` 插入的新行用 LF、
  而 `schema.d.ts` 是 `openapi-typescript` 生成的。⚠️ **入库后一律归一化为 LF**
  （git 自己打了三条 `LF will be replaced by CRLF the next time Git touches it` 的 warning），
  故 `git diff --stat` 只有我改的那些行（`endpoints.ts` 50 行 / `tokens.css` 19 行 /
  `schema.d.ts` 271 行），**没有整文件的行尾翻动**。
- `Document/2026-10-11-实施计划04-Vue3前端.md`：改前改后都是 **CRLF-only + 无 BOM**，
  `git diff --stat` **4 插入 / 3 删除**（没被 IDE 的 Markdown 格式化器重排）。

### commit

| sha | 内容 |
|---|---|
| **`405faf6`** | 第 1 组：教师侧 `/home` 变体 + `_student_home_response` 抽取 + 5 条守卫 + 全仓断言口径 19/45 → 20/46 + 前端接线与三处降级说明撤销 + `schema.d.ts` 重生成（6 文件，+982 / −123） |
| **`11ea1bf`** | 第 2 组：综合分改成与进步榜同一个算式 + 6 条新守卫 + 变异自证 + 5 处过期 docstring + 两处夹具 + ③bis 改回走 HTTP + Plan 04 计划的预警数更正（10 文件，+657 / −106） |
| **`9586015`** | 第 3 组：6 个新令牌吃掉 7 处散落色值 + `check-tokens.mjs` + `smoke.mjs`（第 0 步新分布 / 第 7 步 bis / 第 12 步新口径 / 第 14 步两条 needle / 第 15 步 / 写脏处置）+ 五处过期注释（10 文件，+512 / −32） |
| 第 4 个 | 本报告 |

⚠️ **中间两个 commit 上 `npm run smoke` 会红在第 0 步**（行数口径滞后一次）：
`smoke.mjs` 一个文件同时承载三组的改动（组 2 的第 0 步、组 1 的第 7 步 bis、组 3 的第 15 步），
逐组拆不开、而 `git add -p` 是交互式的（本波禁用）。**最终状态 16/16 全绿已实测**。
⚠️ 同理 `405faf6` 上 `check-tokens.mjs` 还不存在（它在 `9586015`），
故 `9586015` 之前的 commit 上 `npm run check:tokens` 会报「找不到文件」。

### 交回时的运行状态

- `127.0.0.1:8000`：uvicorn（`demo.ps1 -Port 8000` 起的，**指向本波的新代码**），
  `GET /api/health` → `{"status":"ok","tables":25,"students":60}`。
- `backend/pe_demo.db`：**刚重灌过、干净的**（第 3 次 `demo.ps1`，`alert` 32 行、
  分布 `{GREEN_MASTERY: 13, RED_MINITEST_DROP: 7, RED_RPE_SUSTAINED: 6, YELLOW_CHECKIN_GAP: 6}`）。
  ⚠️ 已 gitignored、**没有**加进 git。
- `::1:5173`：vite dev server（**本波重启过**，理由见 ①）。
- ⚠️ `feature/plan-05-auth` 被我还原到 `e5efe6e`（它自己的提交），
  而 `Document/2026-10-11-实施计划05-真实鉴权与管理员角色.md` 因此**不在当前工作树里**
  （它在 `e5efe6e` 里是安全的）。**控制者若要继续 Plan 05，先 `git checkout feature/plan-05-auth`。**
