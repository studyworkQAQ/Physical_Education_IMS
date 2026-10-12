# 待清扫波 · 实现者报告

- **分支**：`chore/stale-prose-sweep`（从 `main` 的 `00ca488` 起）
- **commit**：① `e42e53f`（清1+清2，后端散文，6 文件 +54 −24）· ② `8225a09`（清3，codegen 重跑，2 文件 +651 −31）· ③ `c4a8900`（清4+清5，前端 12 文件 +136 −97）· ④ 本 commit（清6 + `_creds_check.py` 入库 + 本报告）
- **结论**：7 条里 **6 条清了、1 条整条顶回**（清7）。**顶回控制者 3 处**、**没按派单做的地方 5 处**（都是小的范围外延，逐个交代在 §5.3 / §5.4）。
- ⚠️ **后端行为一格未动**：改的全是 docstring / 注释 / CSS 注释 / 守卫散文 + 清4 的模板文本节点（渲染结果逐字不变）+ 清5 的两个 TS 字面值（union 类型，`vue-tsc` 兜着）。
- ⚠️ 验收全绿：后端 **1333 passed**、前端 `smoke.mjs` **18 步（0–17）/ 408 断言 / 退出码 0**（406 → 408 是清4 那 2 拍新守卫）、`npm run build` 退出码 0、`check:tokens` / `check:dist` 绿、四个指纹 + 18 个模板指纹逐字不变、`backend/data` 一个字节没动、前后端新增依赖 0。

---

## ① 环境与服务状态

### 1.1 开工第一件事（硬规矩 #73）

```
node --version    → v24.19.0
npm --version     → 11.17.0
python -c "import fastapi, sqlalchemy; print(fastapi.__version__, sqlalchemy.__version__)"
                  → 0.141.1 2.1.3
```

Python 3.11.1（无 venv，`C:\Python`）。与派单给的基线**逐格相同**。

### 1.2 服务状态（开工时实测）

```
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen
  ::1        5173  OwningProcess 16316   ← 控制者/终审者起的 vite（长跑态）
  127.0.0.1  8000  OwningProcess 69068   ← 终审者起的 uvicorn（demo.ps1 起的，服务 pe_demo.db）
```

### 1.3 ⚠️ 本波重启了这两个服务（派单说「uvicorn 不用重启」，前提不成立 —— 见 §5.4 第 5 条）

| 时机 | 动作 | 为什么必须 |
| --- | --- | --- |
| 清1+清2 改完之后 | 杀 69068 → `demo.ps1 -Port 8000`（重灌演示库 + 起服务） | **Pydantic 模型与端点的 docstring 会进 openapi**：实测 `components.schemas.TeacherRead.description` = **951 字符**、`ClassSessionRead` = **2 070 字符**、`PendingRpeRead` = 523、`RpeTokenRead` = 841。清2 改的正是这些 docstring → 不重启则 `gen:api` 会产出一份**与 HEAD 不一致**的 `schema.d.ts`（那恰好就是本波要清的那类陈旧产物）。同时 `smoke.mjs` 第 0 步要一个**刚复原**的演示库（实测开工时那个库是脏的：`semester` 3 行含「联调脚本建的学期」、`class_session` 10 行、`training_log` 841 行、`user_session` 26 行）。 |
| 第一次 smoke 出 4 条假红之后 | 杀 5173 → `npm run dev` 重起；再杀 8000 → `demo.ps1` 重灌 | 排除**陈旧的 vite dev server**（详见 §5.5）。 |

⚠️ `demo.ps1` 自带两道禁区守卫，两次重灌都打印了「`禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`」。它灌的 CSV 落在 `$env:TEMP\pe_demo_csv_<pid>`、**不碰** `backend/data/**`，且它**一条 `python -m …` 都没有**（不调 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`）。

### 1.4 基线复核（一律运行时口径，`app.openapi()` / AST / 实测响应体）

| 格 | 派单给的基线 | 本波实测（改前） | |
| --- | --- | --- | --- |
| `app.openapi()["paths"]`（全部 = `/api/` 前缀） | 71 | **71** | ✅ |
| operations | 99 | **99** | ✅ |
| 挂 `security` 的操作 | 52 | **52** | ✅ |
| GET | 60 | **60** | ✅ |
| 匿名 GET / 挂 security 的 GET | 44 / 16 | **44 / 16** | ✅ |
| `components.securitySchemes` | 3 | **3**（`X-Student-Id`、`X-Teacher-Staff-No`、`pe_session`） | ✅ |
| `Base.metadata.tables` | 26 | **26** | ✅ |
| 扫描面（`test_layering.SCANNED_DIRS`） | 66 | **66**（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | ✅ |
| `catalog.RESOURCES` | 23 | **23** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`tests/db/test_models.py:687` 自己断言） | ✅ |
| `test_prescription_api.py` 的 `expected` 清单 | —（派单没给） | **22 项**（AST 数 `ast.Dict`） | ⚠️ 见清1 |
| 前端路由 | 15 | **15**（`smoke.mjs:1582` 的 `eq(..., ROUTES.length, 15)` 绿） | ✅ |

---

## ② 7 条逐个

### 清1 · `backend/app/api/routers/dashboard.py:85-93` 那份历史流水账 → **改了（取派单的选项 ②）**

**改前原文（要点）**：82-93 共 12 行，是逐波追加的账 ——
「`expected` 清单由 **12 项扩到 16 项**」→「Plan 04 Task 3 的小修波之后是 **19 项**、挂 `security` 的操作数仍是 **45**」→「Plan 04 收尾波之后是 **20 项**、挂 `security` 的操作数是 **46**，`/api/` 路径模板 65 → **66**、操作 93 → **94**、GET 58 → **59**、匿名仍是 **48**、挂 `security` 的 GET 10 → **11**」。

**实测是不是 still true**：**6 个数全部过期**。

| 那串账写的 | 今天实测（运行时口径） |
| --- | --- |
| `expected` 16 / 19 / 20 项 | **22 项** |
| 挂 `security` 的操作 45 / 46 | **52** |
| `/api/` 路径模板 65 / 66 | **71** |
| 操作 93 / 94 | **99** |
| GET 58 / 59 | **60** |
| 匿名 GET 48 | **44** |
| 挂 `security` 的 GET 10 / 11 | **16** |

**改后**：整段删掉，换成一句指向机器口径的话（派单给的选项 ②，也是控制者倾向的那一侧）——
端点族一律 `app.openapi()["paths"]`（并逐字带上「**不是** `len(app.routes)`，FastAPI 0.141.1 的 `include_router` 是惰性的，按它数会假绿」那条既有警告）、`expected` 的项数由那条守卫自己数、前端那一侧的反查住在 `frontend/scripts/smoke.mjs` 第 12 步。
⚠️ **保留了那条规范**：「每加一个带身份的特例端点都要回来加一行——这是**有意的**」。它是**规则**、不是计数，删掉它会让下一个人以为那份清单可以不动。
⚠️ 顺带把「本模块每个带身份的端点在那份清单里各占一行，而**每一行为什么挂哪一个头**的理由逐字写在对应那个端点函数自己的 docstring 首节（不在本处汇总）」写进去 —— 原文点名的 3 个函数（`student_notifications` / `teacher_student_home` / `normalized_scores`）不是本模块在那份清单里的全部行，逐字点名会是一个新的过期面。

**⚠️ 比派单点名的 85-93 多改了 82-84**（记进 §5.4 第 1 条）：那 3 行的「由 12 项扩到 16 项」同样过期（实测 22），而留着它会与紧邻的「本处不再复述任何计数」**自相矛盾**。

---

### 清2 · `schemas/*` 与 `catalog.py` 里「泛型 GET 一律匿名」那一族 → **改了 6 处、顶回 4 处、另发现 2 处 fix 波漏登记的假话**

**方法**：先 `Grep` 出全族（`一律匿名|缺省.{0,4}匿名`），再**逐个用真 HTTP**（匿名打过去看状态码）验它说的是不是 still true。

**匿名真 HTTP 实测表**（`urllib`，不发任何身份头、不带 cookie）：

| 端点 | 匿名状态码 | 响应体的键 |
| --- | --- | --- |
| `GET /api/teachers` | **401** | — |
| `GET /api/teachers/1` | **401** | — |
| `GET /api/students` | **401** | — |
| `GET /api/students/1` | **401** | — |
| `GET /api/class-sessions` | **200** | — |
| `GET /api/class-sessions/1` | **200** | `batch_id, course_section_id, id, period, rpe_opened, session_date` ← **不含 `rpe_token`** |
| `GET /api/mini-tests/1` | **200** | `entered_by, id, item_combo, normalized_score, semester_id, shuttle_20m_s, squat_30s_count, student_id, tested_on, week` |
| `GET /api/enrollments/1` | **200** | `course_section_id, id, semester_id, student_id` |
| `GET /api/rpe-records` · `GET /api/course-sections` | **200** | — |

**逐个判定与处置**：

| # | 住址（实测行号） | 它说的是什么 | 实测 | 判定 | 处置 |
| --- | --- | --- | --- | --- | --- |
| 1 | `schemas/organisation.py:120`（`TeacherRead`） | 「泛型 `GET` **一律**匿名……『任何人 `GET /api/teachers/{id}` 就能读到全校教师的口令哈希』」 | `/api/teachers{,/{id}}` = **401** | **前提假** | 「一律」→「**缺省**」+ 指向 `catalog` 模块 docstring + 明写**结论只会更强**（摘掉那一格是纵深防御的**第二层**，第一层是那个教职闸门；闸门哪天为别的理由放开时凭据仍不在响应体里，故处置一个字不改） |
| 2 | `schemas/organisation.py:135`（`password_bound_at` 的「代价」） | 「**匿名** `GET /api/teachers` 因此泄漏『哪些工号已注册』」 | **401** | **假** ⚠️ **fix 波那 7 处里没有登记它** | 改成「读到这一格的人因此知道……」+ 明写这一档泄漏比原文**窄**，而计划 §3.3 裁定接受的那一档**仍成立且与名册无关**（403 `password_not_bound` vs 401 `invalid_credentials` 那个区分本身就给出信号） |
| 3 | `schemas/feedback.py:83`（`ClassSessionRead`） | 「理由是**泛型 `GET` 一律匿名**」 | `/api/class-sessions` = **200** | 前提**仍真** | 「一律」→「缺省」+ 明写「`class-sessions` **不在**那 2 个例外里、实测匿名仍是 200，故下面那一句论证一字不变」+ 指向 `catalog`。**与 `routers/feedback.py:437-442`（终审 I3 已改过的那一段）逐字同构** |
| 4 | `schemas/feedback.py:371`（`RpeTokenRead`） | 「理由逐字见那个模型的 docstring 首段：**泛型 `GET` 一律匿名**，而口令是……」 | 同上 | 前提仍真，但它是**第二份复述** | 改成只指过去（「理由逐字见那个模型的 docstring 首段，本处刻意不复述第二份」） |
| 5 | `schemas/dashboard.py:349`（`PendingRpeRead`） | 「（泛型 `GET` **一律**匿名，故把它留在读模型上等于将这扇闸门摊给任何调用方）」 | 说的是 `class-sessions`，**200** | 前提**仍真** | 「一律」→「缺省」+ 明写实测 200 + 指向 `catalog` |
| 6 | `routers/catalog.py:230`（`teachers` 行的 `list_exclude` 注释） | 「`GET /api/teachers` **是匿名的**」 | **401** | **假** ⚠️ **fix 波那 7 处里也没有登记它**；且它与**上面 4 行**的 `"read_requires_staff": True` 同屏打脸 | 改成「摊给任何**读得到本端点**的人」+ 明写「本行**照旧要**：它是纵深防御的第二层」 |
| 7 | `routers/catalog.py:219` | 「……全部验身材料 —— **匿名可读时**，『读过一次 GET /api/teachers 的人』可以给任何工号绑口令」 | — | **仍真**（反事实句：说的正是 Plan 05A Task 5 **之前**的状态，而它第一句就是「本行的两个 GET 从『匿名』改成『要教职身份』」） | **不改**（见下面的顶回） |
| 8 | `routers/catalog.py:255` | 同 7 的学生那一侧 | — | **仍真**（同上） | **不改** |
| 9 | `routers/catalog.py:263` | 「与 teachers 那一行同一条理由（**凭据不得匿名可读**）」 | — | **仍真**（规范句，不是对现状的断言） | **不改** |
| 10 | `routers/catalog.py:472` | 「它是『`rpe_token` **不再匿名可读**』这件事的另一半」 | `/api/class-sessions` = **200** | **仍真** | **不改** |
| + | `api/crud.py:260-262` | 那份「哪些文件**只指过去、不复述**」的清单 | — | 被本波改长了 | **连带补齐**（加 `api/schemas/feedback.py` 与 `api/schemas/dashboard.py`，并记下改对的那 3 处假话）—— 否则它自己就成了过期散文 |

**⚠️ 顶回（第 1 处）**：fix 波登记的 `catalog.py:219 / 255 / 263 / 472` 那 **4 处实测全部仍真**，且它们**不是**「泛型 GET 一律匿名」那条规则的复述、而是**本行自己的理由**（219/255 是反事实句、263 是规范句、472 说的是 class-sessions）。而 `catalog.py` 正是「那一个住址」所在的文件（:41 与 :45-53）——**自己指向自己没有意义**。派单说「真的就保留但改成指向 `catalog.py:45-51` 那一个住址（不要各自复述）」，对这 4 处**不适用**，故保留原文。
⚠️ 反过来，fix 波那 7 处里**漏了 2 处真的假话**（`organisation.py:135` 与 `catalog.py:230`）—— 本波实测出来并改对了。**其中 `catalog.py:230` 那一处最危险**：它与上面 4 行的 `read_requires_staff: True` 在同一屏互相打脸，照着它读的人会以为 `GET /api/teachers` 没有身份闸门。

**⚠️ 一并复核为「不动」的同族**（硬规矩 #109：分清它本身还是对它的提及）：
`schemas/auth.py:104`（引号里的**旧文**，外面套着「本处此前写的是……」，是终审 I3 改对的那一处）、`schemas/organisation.py:215/219/221`（I3 已改对）、`schemas/auth.py:79-88 / 110`（I3 已改对）、`crud.py:118`（已是「**缺省**匿名」）、`crud.py:206/209`（说的是「Plan 04 定下的那条规则」与「它在 Plan 05A 之后不再对全部 23 个资源成立」，两句都真）、`routers/feedback.py:438`（I3 已改对）、`routers/dashboard.py:679-691`（I3 已改对）、`routers/catalog.py:41 / 45-53`（**就是那一个住址**）。

---

### 清3 · 重跑 `npm run gen:api` → **改了；⚠️ 而实质收益远大于派单预估**

详见 §3（专节）。一句话：入库那份 codegen 产物**早于 Plan 05A**，整个 `/api/auth/*` 家族（5 条路径 / 5 个操作 / 4 个 schema）都不在里面；重跑之后 paths 66 → **71**、operations 94 → **99**、`components.schemas` 85 → **89**，**消失的 0 个**。派单点名要核实的三件事逐个都过了。**不是整文件重写**（640 + / 26 −，产物 8 848 行）。

---

### 清4 · 模板文本节点里的 27 处 `>—<` → **改了（27/27 全换），守卫也扩了**

详见 §4（专节）。一句话：实测 **27 处 / 7 个 .vue**（不是 fix 波记的「约 30 处 / 10 个 .vue」，**那两个数都不对**），而 **27 处全部**是「不知道 / 无数据」语义（`<span class="unknown">—</span>` 这一个形状），**破折号 0 处、范围符 `A—B` 0 处** → 全换、没有一处需要保留。守卫**扩到模板文本节点了**（第 17 步 ④ 新增 2 拍），断言 406 → **408**。

---

### 清5 · `meta.surface` 的取值名 `paper` / `ink` → **改了（`'base' | 'board'`）**

| 格 | 改前 | 改后 |
| --- | --- | --- |
| `router/index.ts` 类型声明 | `surface?: 'paper' \| 'ink'` | **`surface?: 'base' \| 'board'`** |
| `router/index.ts` 唯一一处设值（`/t/dashboard`） | `surface: 'ink',` | **`surface: 'board',`** |
| `App.vue` 唯一一处比较 | `route.meta.surface === 'ink' ? 'surface-board' : 'surface-base'` | **`=== 'board'`**（三元两支一字未动） |
| **那层源码面守卫的期望集合** | `const ALLOWED = new Set(['paper', 'ink'])` | **`new Set(['base', 'board'])`** + 新加一个 `const RENAMED_AWAY = ['paper', 'ink']` |
| 第 17 步 ③ 第三拍 | 「而 `'board'` **不是** meta.surface 的字面值」 | **翻转**成「改名之前的那两个值（`paper` / `ink`）**不再**是 meta.surface 的字面值」 |
| 第 17 步 ③ 第四拍（反例） | 谓词 `/tone\?:\s*'paper'\s*\|\s*'board'/` | **谓词一字未改**（仍在 `SectionHead.vue` 里命中），**标签改对了** |

⚠️ **③ 那一组的拍数不变**（仍是 4 拍），故第 17 步的断言数只由清4 那 2 拍抬（25 → 27）。

⚠️ **第四拍为什么必须改标签而不是删**：改名之后 `meta.surface` 与组件 `tone` 那**两根轴共用** `'board'` 这个词（此前它们共用的是 `'paper'`：`tone?: 'paper' | 'board'` × 6 个组件 vs `surface?: 'paper' | 'ink'`）—— 即「两根轴有一个词重叠」这件事**改名前后都成立、只是重叠的那个词换了**，故「grep 到 `'board'`」判定不了任何事。这正是 fix 波顶回终审「`'board'` 全仓不存在」那一条时钉下来的事实，本波把它如实改写而不是删掉。

⚠️ **收益比派单预估的大**（派单说「收益只是名字好听」）：`styles/base.css:131-155` 那 **25 行注释存在的唯一理由**就是「类名与字面值刻意不同词」，而它本身构成一个**误改陷阱** —— 逐字写着「照着它去把 `App.vue` 的 `'ink'` 改成 `'board'` 的人会**静默**让大屏丢掉 `.surface-board`、拿到 `--bg` 的纯白」。改名之后**陷阱与解释它的 20 行一起消失**（base.css 19 + / 20 −，净减 1 行）。两条守卫都留着：第 14 步查**渲染真值**（15 条路由逐条 CDP 取 `.app` 的 class）、第 17 步 ③ 查**源码面**。

**实测**：`routerLiterals = ["board"]`、`appLiterals = ["board"]`；第 14 步 15 条路由的渲染真值一格没变（`t-dashboard` = `surface-board`、其余 14 条 = `surface-base`），**109/109 绿**。

---

### 清6 · 删掉 05A 的旧截图 → **删了 4 张；⚠️ 而派单的事实前提不成立（顶回第 2 处）**

**实测 `Get-ChildItem Document\*.png`（改前 19 张）**：

| 文件名 | 字节 | mtime | `git log --diff-filter=A` |
| --- | --- | --- | --- |
| `2026-10-11-screenshot-admin-index.png` | 385 437 | 2026-10-11 21:31:13 | **`21be43b` docs(sdd): Plan04 Task 4+5 报告与联调取证** |
| `2026-10-11-screenshot-admin-list.png` | 165 070 | 2026-10-11 21:31:13 | 同上 |
| `2026-10-11-screenshot-student-home.png` | 105 413 | 2026-10-11 21:31:13 | 同上 |
| `2026-10-11-screenshot-teacher-dashboard.png` | 378 966 | 2026-10-11 21:31:13 | 同上 |
| `shot-01-login.png` … `shot-15-admin-detail.png`（15 张） | 123 831 – 2 695 614 | 2026-10-12 17:37:56 | **`ac89ed0` test(frontend): Plan 05B Task 6 —— …… + 15 张截图** |

⚠️ **顶回的事实部分**：
1. `Document/` 下**没有**任何文件名形如 `*2026-10-12*` / `auth-*` / `login-*` 的 png（`shot-01-login.png` 是 05B 的那 15 张之一，**不能删**）。派单给的两个文件名特征**都匹配不到东西**。
2. 那 4 张**不是 Plan 05A 的**：它们是 **Plan 04 Task 5** 的交付物（入库于 `21be43b`，且被 `2026-10-11-实施计划04-Vue3前端/task-5-report.md:76-79` 与 `Document/2026-10-11-前后端联调取证.md:3838-3841` 逐字引用）。**05B 报告 §13 第 6 条把它们写成「Plan 05A 的 4 张旧截图」，归属错了。**

⚠️ **仍然删了**（内容确实过期：拍的是《田径场年鉴》旧皮肤，已被 05B 的 15 张 `shot-*` 取代，而 05B 报告 §13 已登记「可删」），**但连带处理了引用** —— 否则散文会指向不存在的文件，那正是本波要防的失效形态：

| 引用方 | 处置 | 理由 |
| --- | --- | --- |
| `Document/2026-10-11-前后端联调取证.md:3836-3841` | **改了**：4 行用 `~~删除线~~` 划掉 + 补一段说明（「已于 2026-10-12 的待清扫波删掉、取代它的是入库的 15 张 `shot-01..15`」+ 更正归属为 Plan 04 Task 5 / `21be43b`） | 那份文档是**入库交付物**、且是一份**取证记录**：「当时人眼复核过哪几张」本身就是历史事实的一部分，**整行抹掉**会让本节读起来像「当时没截图」。故划掉而不删行。⚠️ 本节其余的取证结论（needle 清单、`--dump-dom` 那一档的限制、附 C 的 9 个可写资源写操作矩阵）**与皮肤无关**，一字未改。字节 101 695 → **102 679**、行 3 949 → **3 960**、仍纯 CRLF / 无 BOM。 |
| `.superpowers/sdd/2026-10-11-实施计划04-Vue3前端/task-5-report.md:76-79` | **没动** | 那是**账本**（历史记录）。删改账本等于改写取证；本报告的这一节就是它的更正住址。 |

**结果**：`Document/` 下剩 **15 张 png**，全部是 `shot-01..shot-15`（派单要的那个数）。

---

### 清7 · `Level` 的槽位名 `moss` → **⚠️ 整条顶回不改**

**实测**（`Grep moss` 于 `frontend/src`）：**35 处 / 13 个文件**。分布：

| 住址 | 处数 | 它是什么 |
| --- | --- | --- |
| `src/present.ts` | **6** | `:145` **导出的公开类型** `export type Level = 'red' \| 'amber' \| 'moss'` · `:150` `LABEL_TO_LEVEL` 的 `green: 'moss'` · `:153` docstring · `:486` `LAYER_SLOTS` 的 `{ key: 'green', zh: '绿色层', level: 'moss' }` · `:527` **导出函数签名** `factorToneOf(...): 'default' \| 'red' \| 'moss'` · `:530` `return 'moss'` |
| `src/styles/tokens.css` | **4** | `:106-108` 逐字写着「⚠️ 槽位名仍叫 `moss`（`present.ts` 是 `Level` 类型的**唯一所有者、逐字禁改**，它导出的是 `'red'\|'amber'\|'moss'`），但**颜色令牌**叫 `--green`」；`:27` 与 `:29` 是 05B 的**删除记录**里列的 `--moss-on-ink` / `--moss-wash-on-ink`（历史清单，**不是活令牌** —— 实测 `tokens.css` 里今天没有任何 `--moss*` 定义） |
| `src/components/SectionHead.vue` | 2 | prop union `level?: 'default' \| 'red' \| 'amber' \| 'moss'` + **CSS 类** `.section--moss { background: var(--green) }` |
| `src/components/StatBlock.vue` | 2 | prop union + **CSS 类** `.stat__value--moss { color: var(--green) }` |
| `src/components/SuccessMark.vue` | 4 | docstring + prop union `tone?: 'moss' \| 'primary' \| 'red' \| 'amber'` + **缺省值** `tone: 'moss'` + **CSS 类** `.mark--moss` |
| `src/components/charts/CompletionBars.vue` | 1 | `readonly level: 'red' \| 'amber' \| 'moss' \| 'default'`（+ 对应的 `.cbars__bar--moss`） |
| 6 个页面（`CheckIn` 2 · `Home` 2 · `ClassReport` 4 · `StudentDetail` 2 · `Dashboard` 2 · `MiniTest` 1 · `WeeklySheet` 3） | 16 | 传 `level="moss"` / `tone="moss"` |

**顶回的三条理由**：

1. **派单自己给的判据被触发了**：「若它牵动 `present.ts` 或 `tokens.css` 的**公开名字**，顶回来」→ **两者都牵动了**。`present.ts` 那 6 处里有**导出的公开类型 `Level`** 与**导出函数 `factorToneOf` 的返回类型**；`tokens.css:106-108` 更是逐字写着 `present.ts` 是「`Level` 类型的唯一所有者、**逐字禁改**」。
2. **派单的前提「只是内部槽位名（不影响渲染结果）」不成立**：`moss` 经 `level` / `tone` prop 拼进 class 名（`StatBlock.vue:69` 逐字是 `` `stat__value--${props.level}` ``），**直接进 DOM**，而 4 个组件各自有一条 `.xxx--moss` 的 CSS 规则在等它。改它是「改 2 个导出类型的公开签名 + 4 个 CSS 类名 + 13 个文件」，**不是**改一个内部符号。
3. **它已经被登记在唯一所有者的注释里**（`tokens.css:106-108` 那一段就是这条命名债的账面，且它同时交代了「槽位名叫 `moss`、颜色令牌叫 `--green`」这个刻意的分工）—— 不是无主的散落复述，故它不构成本波要防的那个失效形态（「9 处复述只更新了 1 处」）。

**结论**：记成**已知命名债**，账面仍在 `tokens.css:106-108`。真要改，它属于一次**跨 13 个文件的公开改名波**（收益只是名字好听，风险面覆盖 15 条路由的渲染 + 4 个 CSS 类名 + 2 个导出签名），不属于清扫波。

---

## ③ 清3 的 diff 规模（专节）

### 3.1 规模

| 格 | HEAD（入库那份） | 重跑后 | |
| --- | --- | --- | --- |
| `git diff --numstat` | — | **640 + / 26 −** | 合计 666 行 |
| 字节（blob / 工作树） | **355 599** / 363 832（工作树当时是 CRLF） | **392 139** | |
| 行 | **8 234** | **8 848** | |
| 行尾 | blob `i/lf`（工作树 `w/crlf`） | **LF**（codegen 产物口径） | 见 3.4 |

⚠️ **不是整文件重写**：8 848 行里只动了 666 行（7.5%）。`openapi-typescript` 版本没抖（仍是 **7.13.0**，`package.json` 的 `devDependencies` 与 HEAD **逐字相同**）。

### 3.2 ⚠️ 实质收益：入库那份产物**早于 Plan 05A**

派单（与 fix 波报告 §7.1 第 3 条）说的是「它只差注释文本、类型一格没变」。**实测不成立** —— 那份产物根本不含整个 `/api/auth/*` 家族：

| 面 | HEAD | 重跑后 | 新增 | 消失 |
| --- | --- | --- | --- | --- |
| `paths` | **66** | **71** | **+5**：`/api/auth/login`、`/api/auth/logout`、`/api/auth/me`、`/api/auth/students/bind`、`/api/auth/teachers/bind` | **0** |
| `operations` | **94** | **99** | **+5**：`login_…`、`logout_…`、`me_…`、`bind_student_…`、`bind_teacher_…` | **0** |
| `components.schemas` | **85** | **89** | **+4**：`LoginCreate`、`SessionIdentityRead`、`StudentBindCreate`、`TeacherBindCreate` | **0** |

（数法：`git show HEAD:…` 与重跑后的产物各自用同一个正则抽 `interface paths` / `interface operations` / `components.schemas` 三段里的键，做集合差 —— **不是**数行。）

⚠️ 于是「640 行新增」里有相当一部分是**这 5 条路径 + 5 个操作 + 4 个 schema 的结构**，而不只是 description 文本。这也解释了为什么必须重启 uvicorn 才跑（§1.3）。

### 3.3 派单点名要核实的三件事

| # | 要核实的 | 实测 | |
| --- | --- | --- | --- |
| ① | `npm run build` 仍退出码 0 | **0**（`vue-tsc -b && vite build`，636 ms / 重跑后 335 ms）。产物形状变了而 `endpoints.ts` / `types.ts` 引用它的地方**一格没红** —— 那 +5/+5/+4 全是**加法**，没有改任何既有形状 | ✅ |
| ② | 那 24 个未定型响应仍是 `Record<string, unknown>` / `{[key: string]: unknown}` | `[key: string]: unknown;` 出现次数 **42 → 42**（不变）；「200 响应体是那 5 行未定型形状」**HEAD 24 处 / 重跑后 24 处**；`types.ts` 头部点名的 **24 个操作名 24/24 都还在**、且逐个复核仍是未定型。⚠️ 产物用的是 **index-signature** 写法（`"application/json": {` / `[key: string]: unknown;` / `};`，5 行），`Record<string, unknown>` 那一种写法住在**手写**的 `types.ts` 里 —— 两者都没变 | ✅ |
| ③ | `smoke.mjs` 第 12 步第 ⑤ 拍仍绿 | **绿**：「⑤ 23 个 list 端点的响应**全部**未定型 → actual=23 expected=23」、「⑤ 没有一个 list 端点是定型的（否则 `types.ts` 那一格是冗余）」、「⑤ `/api/health` 也未定型（24 = 23 + 1）→ actual=true」。第 12 步整体 **22/22** | ✅ |

### 3.4 行尾

codegen 产物是 **LF**，而 `frontend/**` 工作树其余文件是 CRLF（`git ls-files --eol` 报 `i/lf w/crlf`）。按派单「**`schema.d.ts` 重跑后的行尾以 codegen 产物为准**」保留 LF。⚠️ 入库 blob 本来就是 `i/lf`，故 **git 层面一致**：`git diff` 只报那 666 行、没有整文件重写，即为证。git 会打印一句 `warning: … LF will be replaced by CRLF the next time Git touches it` —— 那是 `core.autocrlf` 的常规提示，不影响入库内容。

### 3.5 连带改了 `src/api/types.ts` 的头部（同一份文件、被本波实测判成过期）

- 删掉两个过期计数：「后端 **92** 个操作里有 24 个……」与「遍历 **64** 个 `/api/` 路径模板的 **92** 个操作」→ 实测已漂到 **99 / 71**，故改成指向 `app.openapi()` 的机器口径（硬规矩 #111）。⚠️ **那 24 个的逐端点清单一个字没动**（它才是要钉的那一格，且今天仍逐字成立：23 个泛型 list + `/api/health`）。
- 如实交代那份「压成一行」的产物样例与产物**逐字不同**（产物里它是 5 行、带分号；要当 needle 请用 `[key: string]: unknown;`）。
- 删掉会漂的**行号**引用（原文写 `schema.d.ts:7764-7775`，重跑之后那一段已在 **8630**）。

### 3.6 ⚠️ 本波**新登记**的一个第二个所有者（没动）

`src/api/auth.ts` 手写了 `SessionIdentity` / `AuthKind` / `SessionRole` 等类型（它 `import { ApiError, apiRequest } from './client'`，**不**读 `generated/schema`），而重跑之后产物里也有 `SessionIdentityRead`。把 `auth.ts` 改成读产物是**结构性**改动（要动 13 个页面里读「我是谁」的那些），不属于清扫波 → 记进 §5.1 待清扫。

---

## ④ 清4 的 27 处语义分布（专节）

### 4.1 实测（用 `smoke.mjs` 第 17 步 ④ 的**同一个**剥注释谓词，`/* */` 与 `<!-- -->` 挖空成空格故行号不变）

**27 处 / 7 个 `.vue`**：

| 文件 | 处数 |
| --- | --- |
| `src/views/teacher/StudentDetail.vue` | **14** |
| `src/views/teacher/AlertQueue.vue` | **4** |
| `src/views/student/MiniTest.vue` | **4** |
| `src/views/student/Notifications.vue` | **2** |
| `src/components/StatBlock.vue` | **1** |
| `src/views/student/CheckIn.vue` | **1** |
| `src/views/teacher/ClassReport.vue` | **1** |
| **合计** | **27** |

⚠️ **fix 波记的两个数都不对**：它写的是「全仓实测约 **30** 处、散在 **10** 个 `.vue` 里」（`fix-wave-report.md:470` 与 `smoke.mjs` 第 17 步 ④ 尾巴那段注释里也逐字写着「约 30 处 / 10 个 .vue」）。实测是 **27 处 / 7 个文件**。⚠️ 而它**打印出来的那个数**（`textNodes`）是对的 —— 错的只是散文里那两个手写的估计值。本波把那段散文换成了实测值 + 逐文件分布。

### 4.2 语义分布（派单点名要的）

| 语义 | 处数 | 处置 |
| --- | --- | --- |
| **「不知道 / 无数据」**（`<span class="unknown">—</span>`；StatBlock 那一处是 `class="unknown stat__value stat__value--unknown"` + `aria-label="无数据"`） | **27** | **全换成 `{{ UNKNOWN }}`** |
| 破折号（散文标点） | **0** | — |
| 范围符 `A—B` | **0** | — |
| **合计** | **27** | **换了 27 / 保留 0** |

⚠️ **派单担心的「27 处里大部分不是『不知道』语义」实测不成立** —— 27 处**全部**裹在 `class="unknown"` 里（`StatBlock.vue` 那一处还额外带 `aria-label="无数据"`），一处例外都没有。故**没有顶回这一条**、也没有为了凑数乱换。

逐处形态（27 处只有两种）：
- **26 处**：`<span class="unknown">—</span>`（多数外面套一个 `<template v-if="xxx === null">`，例如 `StudentDetail.vue:544` `<template v-if="explanation === null">`、`Notifications.vue:226` `<template v-if="item.alert_id === null">`）
- **1 处**（`StatBlock.vue:78-80`）：跨 3 行的 `<span v-if="isUnknown" class="unknown stat__value stat__value--unknown" aria-label="无数据"\n  >—</span\n>` —— 那种 `>—</span\n>` 的写法是为了**不引入空白**，本波改成 `>{{ UNKNOWN }}</span\n>`，空白形状一字未动

### 4.3 代价比 fix 波估的小一档

fix 波说「把它们换成 `{{ UNKNOWN }}` 要给其中 **6 个文件各加一次 import**」。**实测只需 1 个**：7 个文件里 **6 个本来就 import 了 `UNKNOWN`**（fix 波自己换那 12 个引号字面量时加的：`CheckIn.vue:56`、`MiniTest.vue:62`、`Notifications.vue:46`、`AlertQueue.vue:84`、`ClassReport.vue:62`、`StudentDetail.vue:88`），只有 `components/StatBlock.vue` 需要新加一行 `import { UNKNOWN } from '../present'`（与同目录的 `IdentitySwitcher.vue:42` 同一种相对路径）。

### 4.4 守卫**扩到模板文本节点了**（派单点名要的）

`smoke.mjs` 第 17 步 ④ 新增 **2 拍**（`out(...)` 那行打印保留，改成断言 + 反例）：

1. `④ src/**/*.vue 的**模板文本节点**里 0 处 >—<（清4：27 处全部换成 {{ UNKNOWN }}）` —— 谓词与改前那行打印**逐字同一个**（剥注释后 `indexOf('>—<')` 逐行扫），故它不是新发明的判据、是把原来只打印的那一格**升成会红的断言**；`detail` 带逐个 `file:line`。
2. `④ 反例：谓词**会**命中一处硬编码的模板文本节点（硬规矩 #107）` —— needle 用 `['<span class="unknown">', '</span>'].join(DASH)` **拼出来**、不写成字面量（#109）。

⚠️ 两拍的 needle（`>${DASH}<`）一律由既有的 `const DASH = '—'` 拼出来。⚠️ 本谓词只扫 `src/**/*.vue`、扫不到 `scripts/` 下的 `smoke.mjs` 自己，故不存在自我命中；但同一档纪律照办（上一拍那个 `FAKE_EXIT` 就是这么写的）。

**实测输出**：
```
扫了 27 个 .vue 文件，代码里引号包着的「—」共 0 处
模板文本节点 >—< 共 0 处（清4 之后应当是 0）
✓ ④ src/**/*.vue 的**模板文本节点**里 0 处 >—<（清4：27 处全部换成 {{ UNKNOWN }}）  →  []
✓ ④ 反例：谓词**会**命中一处硬编码的模板文本节点（硬规矩 #107）  →  <span class="unknown">—</span>
```

### 4.5 断言数 406 → **408**（连带改了 `package.json`）

清4 那 2 拍让第 17 步从 25 拍变成 **27 拍**、总数 406 → **408**。⚠️ `frontend/package.json` 的 `"//"` 字段里逐字写着「smoke 是 **18 步（0–17）/ 406 条断言**」，被本波自己改假了 → 按清1 的**同一档处置**：**删数而不是改数**，改成「smoke 是 **18 步（0–17）**；⚠️ **断言条数本处刻意不复述**（它每一波都在长，复述就是第二个所有者 —— 硬规矩 #111；要那个数请读脚本自己收尾打印的『总结』那一段）」。

### 4.6 渲染结果逐字不变

`UNKNOWN === '—'`（`present.ts` 导出的唯一所有者，第 17 步 ④ 有一拍专门钉它还在），故 `{{ UNKNOWN }}` 渲染出来的 DOM 文本与改前**逐字相同**。实测第 14 步 15 条路由的**重叠 / 溢出 / needle / surface class** 四族断言 **109/109 绿**，`check:dist` 的产物大小只动了 +0.1 kB（`StatBlock.vue` 那一行 import）。

---

## ⑤ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 5.1 待清扫（沿用 + 本波新登记 4 条）

| # | 条 | 状态 |
| --- | --- | --- |
| 1 | **`session → identity` 那座兼容桥**（05B 待清扫第 14 条 / fix 波 §7.1 第 6 条） | 派单逐字排除（「它是**结构性**的，13 个页面都从 `identity` 读『我是谁』」）。**本波一行没动** |
| 2 | **终审 I6：44 个匿名 GET 放行整套化名健康档案** | 派单逐字排除（产品裁定，已写进 spec §1.2 的 12 条已知局限）。下一步该收的是「带 `student_id` 的约 10 张表」，属**安全收紧波**。**本波一行没动**（清2 只改散文、没收紧任何端点：实测匿名 GET 仍是 **44** 个） |
| 3 | `verify_password` 的迭代次数上界（终审 M6）与会话恢复那一帧 ANONYMOUS（M7，spec §13.4.2 已点过一句） | 派单逐字排除。本波没动 |
| 4 | **清7 的 `moss` 命名债** | **本波顶回**（§2 清7）。账面仍在 `tokens.css:106-108`（唯一所有者的注释里）。真要改是一次跨 13 个文件的**公开改名波** |
| 5 | **新登记**：`src/api/auth.ts` 手写的 `SessionIdentity` 与 codegen 产物里新出现的 `SessionIdentityRead` 成了**第二个所有者** | 清3 重跑之后才有的（此前产物里根本没有 auth 家族）。改成读产物是结构性改动 |
| 6 | **新登记**：`tests/**` 里还有 **13 处**「一律匿名」同族散文 | `test_crud.py:492 / 1146 / 1767 / 1824 / 2615`、`test_feedback.py:416`、`test_prescription_api.py:1425 / 1456 / 1475 / 1515 / 1642 / 1708 / 1724`。**逐个看过：没有一处是假的** —— 全部是历史陈述 / 规范陈述 / 断言消息，而 `test_prescription_api.py:1642` 那句「其余 **21** 个资源的 GET 一律匿名」今天**逐字成立**（23 − 2 = 21）。派单点名的是 `schemas/*` 与 `catalog.py`，故本波没动它们 |
| 7 | **新登记**：`smoke.mjs` 第 14 步对 **dev server 的新鲜度敏感**、而它自己不检查这一档 | 本波实测到的一次假红（§5.5）。要么在第 14 步开头加一拍「dev server 起于何时 / 是否见过本波的改动」，要么在文件头把「跑之前先重起 `npm run dev`」写成硬要求（今天只写了「跑之前先重跑 `demo.ps1`」） |
| 8 | 沿用 `demo.ps1` 自己登记的那一条：「addon 训练量未指定」的 warning 与 `prescription.status=needs_review` **不是一件事** | `demo.ps1` 的 `[7/7]` 那一步逐字写着「两者的差别已登记为待清扫」。本波没动 |

### 5.2 关切

- ⚠️ **`schema.d.ts` 与后端 docstring 是耦合的**：本波实测到「改一句模型 docstring → openapi 的 description 变 → `schema.d.ts` 变」。而 05A / 05B / fix 波三波都禁改 `src/api/**`，于是**每一波改后端散文都在给 `schema.d.ts` 加一份陈旧**。建议在每一波的验收清单里加一条「若本波改了任何进 openapi 的 docstring，就要重跑 `gen:api`」，否则这条待清扫会**每波重新长出来**。
- ⚠️ **控制者那个长跑的 vite dev server 会给出假红**（§5.5）。它的失效形态很坏：4 条红全是「文本内容重叠」，读起来像「本波把布局改坏了」。
- ⚠️ **演示库现在是脏的**（本波最后一次 `smoke` 跑完的状态）。要再跑 `smoke` 请先 `demo.ps1`。⚠️ 本波收尾时把后端**重灌了一次并让服务留在 8000 上跑**（详见 §6.2），故交给控制者的是一个**干净的库 + 起着的后端 + 起着的 vite**。

### 5.3 ⚠️ 顶回控制者的地方（**3 处**）

| # | 顶回什么 | 理由要点 |
| --- | --- | --- |
| **1** | **清2 的一部分**：fix 波登记的 `catalog.py:219 / 255 / 263 / 472` 那 **4 处不改** | 实测**全部仍真**：219/255 是**反事实句**（「匿名可读时……」，说的正是 Plan 05A Task 5 之前的状态，而它第一句就是「本行的两个 GET 从『匿名』改成『要教职身份』」）、263 是**规范句**（「凭据不得匿名可读」）、472 说的是 `class-sessions`（实测匿名仍 **200**）。而它们**不是**那条规则的复述、是**本行自己的理由**；且 `catalog.py` 正是「那一个住址」所在的文件（:41 与 :45-53）—— **自己指向自己没有意义**。⚠️ 反过来，那 7 处里**漏了 2 处真的假话**（`organisation.py:135`、`catalog.py:230`），本波实测出来并改对了；其中 `catalog.py:230` 与它**上面 4 行**的 `read_requires_staff: True` 同屏打脸，是这一族里**最危险**的一处 |
| **2** | **清6 的事实前提**：派单说「Plan 05A 那一波截过几张图，文件名形如 `*2026-10-12*` 或 `auth-*` / `login-*`」 | 实测 `Document/` 下**没有任何**这样的 png。只有 4 张 `2026-10-11-screenshot-*.png`（mtime 2026-10-11 21:31:13），而 `git log --diff-filter=A` 实测它们由 **`21be43b`「docs(sdd): Plan04 Task 4+5 报告与联调取证」** 入库 —— 是 **Plan 04 Task 5** 的交付物，**不是 05A 的**（05B 报告 §13 第 6 条把归属写错了）。⚠️ **删除照做**（内容确实过期：旧皮肤、已被 05B 的 15 张取代），但**连带改了 1 处入库文档的引用**（`Document/2026-10-11-前后端联调取证.md`：4 行划掉 + 一段说明 + 更正归属），否则散文会指向不存在的文件 —— 那正是本波要防的失效形态。Plan 04 的**账本没动**（改账本等于改写取证） |
| **3** | **清7 整条**：`Level` 的槽位名 `moss` **不改** | 派单自己给的判据是「若它牵动 `present.ts` 或 `tokens.css` 的**公开名字**，顶回来」→ **两者都牵动了**（`present.ts` 6 处含**导出的公开类型** `Level` 与**导出函数** `factorToneOf` 的返回类型；`tokens.css:106-108` 逐字写着 `present.ts` 是「`Level` 类型的唯一所有者、**逐字禁改**」）。且派单的前提「只是内部槽位名（**不影响渲染结果**）」**不成立**：`moss` 经 `level` / `tone` prop 拼进 class 名（`` `stat__value--${props.level}` ``）**直接进 DOM**，4 个组件各有一条 `.xxx--moss` 的 CSS 规则在等它。实测 **35 处 / 13 个文件**。而它**已经被登记在唯一所有者的注释里**（不是无主的散落复述），故不构成本波要防的那个失效形态 |

⚠️ 另外**逐条核过并同意**派单的决定（没有顶回）：
- **清1 取选项 ②**（整段删掉、换成指向机器口径的话）—— 实测 6 个数**全部**过期，且这份账已经过期三次；同意「复述就是第二个所有者」。
- **清3 值得跑**（派单留了「若 diff 巨大且没有实质收益就顶回」的口子）—— 实测 **有实质收益**（整个 `/api/auth/*` 家族 5 路径 / 5 操作 / 4 schema 此前**根本不在产物里**），且**不是**版本抖动（openapi-typescript 仍 7.13.0、`devDependencies` 与 HEAD 逐字相同），故**没有顶回**。
- **清4 不顶回**（派单留了「若大部分不是『不知道』语义就顶回」的口子）—— 实测 27 处**全部**是「不知道」语义、破折号与范围符各 **0** 处，故全换。
- **清5 值得改**（派单留了「若收益不抵风险就顶回」的口子）—— 实测收益比派单预估的大（`base.css` 那 25 行注释**存在的唯一理由**就是「类名与字面值不同词」，而它本身构成一个误改陷阱；改名之后陷阱与解释它的 20 行一起消失），且 `vue-tsc` 兜着类型安全、第 14 步的渲染真值守卫 109/109 绿，故**没有顶回**。⚠️ 顺带核实了「两根轴共用一个词」这件事**改名前后都成立**（此前共用 `'paper'`、之后共用 `'board'`），故改名**没有**让轴之间更容易混。
- **清6 的删除动作本身**同意（内容确实过期），只顶回它的**事实前提**与**归属**。
- **§2 的 4 条排除项**（兼容桥 / I6 / M6+M7 / 后端行为）逐字遵守，**一行没动**。

### 5.4 ⚠️ 没按派单做的地方（**5 处**，都是小的范围外延，逐个交代）

| # | 派单说的 | 本波实际做的 | 为什么 |
| --- | --- | --- | --- |
| 1 | 清1 点名 `dashboard.py:**85-93**`（9 行） | 改了 **82-93**（12 行） | 82-84 那 3 行的「由 **12 项扩到 16 项**」**同样过期**（实测 `expected` = **22 项**）。留着它会与紧邻的「本处不再复述任何计数」**自相矛盾** —— 那正是本波要清的失效形态 |
| 2 | 清2 点名「7 处」 | 改了 **6 处**（含 fix 波**没登记**的 2 处）、顶回 **4 处**、并**连带**改了 `crud.py:260-262` 那份「哪些文件只指过去」的清单 | 顶回的 4 处见 §5.3 第 1 条；新发现的 2 处（`organisation.py:135`、`catalog.py:230`）实测是**假的**，不改就是留一句假话；`crud.py` 那份清单被本波改长了，不补齐它自己就成了过期散文 |
| 3 | 清3 只说「重跑 `gen:api`」+ 核实三件事 | **连带**改了 `src/api/types.ts` 头部（删 2 个过期计数、交代样例的压缩写法、删掉会漂的行号） | 那 2 个计数（「92 个操作」「64 个路径模板」）实测已漂到 **99 / 71**，而派单本来就要求「若 codegen 产物形状变了要同步 `types.ts` 头部注释」；§3 的纪律也允许改注释/散文。**那 24 个的逐端点清单一个字没动** |
| 4 | 清4 只说「换 + 扩守卫」 | **连带**改了 `frontend/package.json` 的 `"//"`（删掉「406 条断言」那个数） | 那 2 拍新守卫是派单点名要的，而它**把这句散文改假了**（406 → 408）。按清1 的同一档处置：**删数而不是改数** |
| 5 | §0 说「**本波不改后端生产代码**（除散文注释），故 **uvicorn 不用重启**」 | **重启了 uvicorn 两次、vite 一次** | 派单的前提不成立：**Pydantic 模型与端点的 docstring 会进 openapi**（实测 `TeacherRead.description` = 951 字符、`ClassSessionRead` = 2 070 字符），故清2 改的**正是进 openapi 的文本** —— 不重启则 `gen:api` 会产出一份与 HEAD 不一致的 `schema.d.ts`（恰好就是本波要清的那类陈旧产物）。第二次重启 + vite 那次是为了排除陈旧 dev server（§5.5）。⚠️ 重启用的是 `demo.ps1`（它自带禁区守卫，两次都打印了「`backend\pe.db` 不存在、`backend\data\seed\` 仍为 0 文件 ✓」），**没有**跑 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` |

⚠️ 另外 **1 处刻意不做**：清6 里 `Document/2026-10-11-前后端联调取证.md` 的那 4 行**划掉而不整行删除**（派单只说「删掉旧截图」，没说怎么处理引用）。理由见 §2 清6 的表。

### 5.5 ⚠️ 一次假红（如实记，硬规矩 #39）

**第一次跑 `npm run smoke` 退出码 1**：第 14 步 **105/109**，4 条「没有文本内容重叠（§4.1）」红在 `s-home` / `s-weekly-sheet` / `s-check-in` / `s-rpe`：

```
s-home         span「本周训练量 · 分钟」[33,890,106,17] × span「108.0」[33,901,132,71]  ratio 0.342
s-weekly-sheet span「06」[42,1148,22,26] × span「速度柔韧」[41,1170,24,17]  ratio 0.218（07–12 同型，共 7 对）
s-check-in     span「本周打卡完成率」[33,965,91,17] × span「100.0」[33,976,132,71]  ratio 0.342
s-rpe          span「5」[134,1794,17,40] × span「适中」[132,1828,20,15]  ratio 0.331（+「10」×「力竭极限」0.33）
```

**判定：不是本波改动造成的。** 三条证据：
1. **4 条里有 3 条落在本波一行没碰的文件**（`Home.vue` / `WeeklySheet.vue` / `RpeEntry.vue` —— 清4 碰的是 `CheckIn` / `MiniTest` / `Notifications` / `AlertQueue` / `ClassReport` / `StudentDetail` / `StatBlock`，清5 碰的是 `App.vue` / `router/index.ts` / `base.css` / `smoke.mjs`）；
2. **构建产物与基线同量级**（CSS **61.02 kB** 一分不差、JS **165.70** vs 基线 165.69），`check:tokens` 绿；
3. 那 4 处重叠全是「数字与它下面那行标签压了 4–6px」的**垂直节奏**问题，纯 CSS 驱动，而 CSS 字节数没变。

**处置**：**重启前后端**（`demo.ps1 -Port 8000` 重灌 + `npm run dev` 重起）后重跑 → **18/18 步全绿 / 408 断言 / 0 红 / 退出码 0**。

**真因**：控制者那个**长跑的 vite dev server**（PID 16316，在本波改 `.vue` / `.ts` **之前**起的）处于陈旧态 —— HMR 对 `router/index.ts` 这类**模块图**的改动经常要整页重载才干净。⚠️ 这一格记进 §5.1 待清扫第 7 条：**smoke 第 14 步对 dev server 的新鲜度敏感，而它自己不检查这一档**（它的文件头只写了「跑之前先重跑 `demo.ps1`」，没写「先重起 `npm run dev`」）。

---

## ⑥ 最终验收

### 6.1 后端

| 格 | 基线 | 本波实测 | |
| --- | --- | --- | --- |
| `python -m pytest -q` | 1333 passed | **1333 passed**, 1 warning（204.21 s），退出码 **0** | ✅ |
| `python -m pytest -q --cov=app/domain --cov-branch` | 1332 + 1 skipped | **1332 passed, 1 skipped**, 1 warning（363.61 s），退出码 **0** | ✅ |
| `app/domain` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **TOTAL 1268 · 0 · 376 · 0 · 100%**（18 个文件**逐个** 100%） | ✅ |
| 表数 | 26 | **26** | ✅ |
| 扫描面 | 66 | **66**（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | ✅ |
| 端点：路径 / 操作 | 71 / 99 | **71 / 99** | ✅ |
| 挂 `security` 的操作 | 52 | **52** | ✅ |
| GET（匿名 + 挂 security） | 60（44 + 16） | **60（44 + 16）** | ✅ |
| `securitySchemes` | 3 格 | **3**（`X-Student-Id`、`X-Teacher-Staff-No`、`pe_session`） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✅ |
| `catalog.RESOURCES` | 23 | **23** | ✅ |

### 6.2 前端

| 格 | 基线 | 本波实测 | |
| --- | --- | --- | --- |
| 路由条数 | 15 | **15**（`smoke.mjs:1582` 那一拍绿） | ✅ |
| `npm run build` 退出码 | 0 | **0** | ✅ |
| 产物 CSS | 61.02 kB | **`index-Db3TVHCJ.css` 61.02 kB**（gzip 8.89）—— **一分不差** | ✅ |
| 产物 JS | 165.69 kB | **`index-UryyTQo3.js` 165.70 kB**（gzip 58.02）—— +0.01 = `StatBlock.vue` 那一行 import | ✅ |
| `npm run check:tokens` | 绿（32 文件） | 退出码 **0**，「✓ 扫描面 **32** 个文件（下界 25）」「✓ 全绿：32 个文件里，`tokens.css` 之外一个色值字面量都没有」 | ✅ |
| `npm run check:dist` | 绿（22 文件 / 465.5 kB） | 退出码 **0**，「扫了 **22** 个文件（**465.6 kB**），跳过 0 个非文本」「`dist/` 里 `adoptFromUrl` 出现 **0** 次，而源码里它确实存在（**8** 处：`src/dev/identity-url.ts` 3 + `src/main.ts` 5）」 | ✅ |
| `npm run smoke` | 18 步 / 406 断言 / 退出码 0 | **18 步（0–17）全绿 / 408 断言（408 绿 / 0 红）/ 退出码 0** | ✅ **+2 断言** |
| `@ts-ignore` / `as any` | 0 | **0** | ✅ |
| 新增依赖 | 0 | 前端 `dependencies` 与 `devDependencies` 与 HEAD **逐字相同**；`backend/pyproject.toml` **未被修改**（`git diff --numstat` 空）→ **0** | ✅ |

**smoke 逐步**（`408 = 23+5+10+9+7+9+10+41+14+13+17+6+22+15+109+8+63+27`）：

| 步 | 断言 | | 步 | 断言 | |
| --- | --- | --- | --- | --- | --- |
| 00 登录三种角色 + 演示库复原核实 | 23/23 | ✅ | 09 预警处置 | 13/13 | ✅ |
| 01 `/api/health` → tables == 26 | 5/5 | ✅ | 10 写入侧强制（401/403/201） | 17/17 | ✅ |
| 02 建课次 → 201 且不含 `rpe_token` | 10/10 | ✅ | 11 只读资源被写 → 405 | 6/6 | ✅ |
| 03 `open-rpe` + 匿名 list 不含口令 | 9/9 | ✅ | **12 从 `/openapi.json` 反查 23 行（5 拍）** | **22/22** | ✅ |
| 04 匿名读口令 401 / 教师读 200 | 7/7 | ✅ | 13 学生端那两个新端点 | 15/15 | ✅ |
| 05 交快评 201 / 再交 409 | 9/9 | ✅ | **14 15 条路由的 CDP DOM 取证** | **109/109** | ✅ |
| 06 打卡 201 | 10/10 | ✅ | 15 两个构建守卫 | 8/8 | ✅ |
| 07 weekly-sheet | 41/41 | ✅ | 16 鉴权全链路 | 63/63 | ✅ |
| 08 教师大屏 | 14/14 | ✅ | **17 4 条静态守卫** | **27/27**（基线 25） | ✅ |

### 6.3 禁区与指纹

| 格 | 实测 | |
| --- | --- | --- |
| `Test-Path backend\pe.db` | **False** | ✅ |
| `backend/data/seed/` 文件数（`-Recurse`） | **0** | ✅ |
| `git diff 00ca488 HEAD -- backend/data` | **空** | ✅ |
| `git status --short -- backend/data` | **空** | ✅ |
| `backend/data/**` 文件数 | **24**（5 个数据文件 + 18 个处方模板 + 1 个 README） | ✅ |
| 四个单文件指纹（sha256[:16]） | `national_standard_2014.csv` **D2C8E539E2FA0029** · `exercises.yaml` **5394B37F01DAC9AC** · `exercise_equivalence.yaml` **822CB86A5E998301** · `alert_rules.yaml` **E48E3AC82BB45BB7** → **逐字不变** | ✅ |
| 18 个模板指纹 | `test_template_yaml_fingerprints_are_pinned` 在 **1333 passed** 里**绿**；18 个逐文件 sha256[:16] 见**附录 A** | ✅ |
| `Document/` 下的 png | **15 张**（全部 `shot-01..shot-15`） | ✅ |
| `backend/` 下被本波改动的文件 | **6 个**（全是散文）——`git diff 00ca488 HEAD --numstat -- backend/` 实测 6 行；`backend/pyproject.toml` 不在其中 | ✅ |

### 6.4 交给控制者的运行态

- **后端**：`demo.ps1 -Port 8000` 在后台跑着（**刚重灌过**，`[7/7]` 复核：semester 2 / student 60 / course_section 5 / enrollment 120 / prescription 60 / weekly_adjustment 13 / class_session 8 / rpe_record 240 / training_log 840 / mini_test 180 / alert 32 / notification 19 / weekly_class_report 5），`http://127.0.0.1:8000/docs` 可用。
- **前端**：`npm run dev` 在后台跑着，`http://localhost:5173`（**本波重起过**，故不是陈旧态）。
- ⚠️ 演示口令 `pe-demo-2025`；管理员 `T0003`；教师 `T0001` / `T0002`；学生任何一个在册学号（例 `2025060001`）。
- ⚠️ **本波没有 push、没有碰 `main`**（`git log --oneline` 实测 4 个 commit 全在 `chore/stale-prose-sweep` 上，`main` 仍是 `00ca488`）。

### 6.5 commit sha

| # | sha | 内容 | 规模 |
| --- | --- | --- | --- |
| ① | **`e42e53f`** | `docs(api)`: 清1 + 清2（后端散文） | 6 文件 **+54 −24** |
| ② | **`8225a09`** | `chore(frontend)`: 清3（codegen 重跑 + `types.ts` 头部连带） | 2 文件 **+651 −31**（`schema.d.ts` 640/26、`types.ts` 11/5） |
| ③ | **`c4a8900`** | `fix(frontend)`: 清4 + 清5（清7 顶回） | 12 文件 **+136 −97** |
| ④ | 本 commit | `chore(sdd)`: 清6（删 4 张旧截图 + 更正 1 处引用）+ `_creds_check.py` 入库 + 本报告 | 见下 |

---

## 附录 A · `backend/data/**` 的 24 个逐文件 sha256[:16]（实测，全部逐字不变）

```
E48E3AC82BB45BB7      6037  data/alert_rules.yaml                    ← 派单点名的四个之一
822CB86A5E998301      8245  data/exercise_equivalence.yaml           ← 派单点名的四个之一
5394B37F01DAC9AC     23247  data/exercises.yaml                      ← 派单点名的四个之一
1962FEC6FB2CA852      5103  data/indicator_ranges.yaml
D2C8E539E2FA0029     21412  data/national_standard_2014.csv          ← 派单点名的四个之一
89842C7A0D8A6EA0      7293  data/prescription/GRN-END-ABN-13.yaml
3B1DA3AAB8D6A322      5983  data/prescription/GRN-END-NOR-14.yaml
9ADB0CAC53A572F1      7020  data/prescription/GRN-SPD-ABN-17.yaml
2389C1A03E6ABBCE      5710  data/prescription/GRN-SPD-NOR-18.yaml
91E660991C717944      7092  data/prescription/GRN-STR-ABN-15.yaml
A5B406807FDEF7CC      5782  data/prescription/GRN-STR-NOR-16.yaml
C0C61D2140A521D0      6865  data/prescription/RED-END-ABN-01.yaml
FE91666F74C08CAF      6863  data/prescription/RED-END-NOR-02.yaml
8E396D8BF85B6DBD      7930  data/prescription/RED-SPD-ABN-05.yaml
0EDDE329A6CA61AE      7928  data/prescription/RED-SPD-NOR-06.yaml
8F4D51E3377FA814      7872  data/prescription/RED-STR-ABN-03.yaml
3E8C365CD0B4C133      7870  data/prescription/RED-STR-NOR-04.yaml
D301AE8D8D3D6B7E      6480  data/prescription/YEL-END-ABN-07.yaml
F08B64A00D974F18      6478  data/prescription/YEL-END-NOR-08.yaml
FA81CAD1B9050A9E      7211  data/prescription/YEL-SPD-ABN-11.yaml
524CD251936C79B1      7209  data/prescription/YEL-SPD-NOR-12.yaml
033CFAA2D1F93503      6132  data/prescription/YEL-STR-ABN-09.yaml
C1CDF7D18A1F87E4      6130  data/prescription/YEL-STR-NOR-10.yaml
5CCE72B74D1EB711     10830  data/README_national_standard.md
```

（`data/prescription/*.yaml` 实测 **18 个**文件 = `test_template_yaml_fingerprints_are_pinned` 钉的那 18 个；`data/seed/` **0 文件**；`pe.db` **不存在**。）

## 附录 B · 本波用过的探针（一律写在 `$env:TEMP`、跑完已删）

`sweep_probe_runtime.py`（openapi / 表数 / 扫描面 / `_MODELS_PUBLIC_BASELINE` / `expected` 项数）· `sweep_probe_http.py`（匿名真 HTTP 取状态码 + 响应体键集）· `sweep_probe_db.py`（只读 `mode=ro` 打开 `pe_demo.db` 数行、判脏）· `sweep_probe_openapi_desc.py`（证 docstring 会进 openapi 的 description）· `sweep_probe_schema.py`（`git show HEAD:` 与重跑后产物做集合差）· `sweep_probe_dash.mjs`（27 处 `>—<` 的逐处上下文）· `sweep_probe_guards.mjs`（离线复算第 17 步 ③④ 的全部谓词）· `sweep_probe_final.py`（禁区 / 指纹 / 依赖 / png 计数）· `sweep_dump.py` / `sweep_dump_fe.py`（按字节 dump 指定行区间，绕开 Read 工具的行号偏移）· `sweep_edit_backend.py` / `sweep_edit_c4.py` / `sweep_edit_c5.py` / `sweep_fix_e1.py` / `sweep_fix_types.py` / `sweep_edit_c6doc.py`（字节级替换，每处断言「恰好命中 1 次」，写回复核字节数与行尾）· `sweep_mkmsg1..3.py`（commit 信息，UTF-8 无 BOM）。

⚠️ **`_creds_check.py` 不是本波的探针** —— 它是控制者上一轮留下实测登录账号的取证脚本，按派单**入库**（住在账本目录里是对的）。⚠️ 它含演示口令 `pe-demo-2025` 字面量，而那一串是**公开的**（`demo.ps1` 每次跑都打印它、spec §13 也记着它、`smoke.mjs:140` 也抄了一份），故不是泄漏。
