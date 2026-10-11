# Plan 04 Task 3 实现报告 —— 后端小修波（2 处）+ 教师端 4 个页面

> **日期**：2026-10-11 · **分支**：`feature/plan-04-frontend` · **起点 HEAD**：`b30a748`
> **commit**：`8217e72`（后端小修波，单独一个）→ `66f9df7`（教师端共享层）→
> `0a74054`（4 个页面 + 路由接线）→ 本报告的 commit
> **派单**：先做后端小修波（Task 2 顶回的 2 处 Critical），再做实施计划 04 的 Task 3。
> 本报告的每一格都是**实测**出来的；推断的那几格都标了「推断」。

---

## 1. 环境与服务状态

| 项 | 实测值 | 派单期望 | 结论 |
|---|---|---|---|
| Node | v24.19.0 | v24.19.0 | ✅ |
| npm | 11.17.0 | 11.17.0 | ✅ |
| FastAPI | 0.141.1 | 0.141.1 | ✅ |
| SQLAlchemy | 2.1.3 | 2.1.3 | ✅ |
| Python | 3.11.1 | —— | 记录 |
| 分支 / 起点 | `feature/plan-04-frontend` @ `b30a748`，工作树干净 | 同 | ✅ 未切分支、未 push |

**服务**：

* 开工时 **uvicorn `127.0.0.1:8000`（PID 42132）与 vite `::1:5173`（PID 56520）都起着**
  （Task 2 留的）。按派单要求**先查再决定**：`Get-NetTCPConnection -LocalPort 8000,5173`。
* ⚠️ 小修波改了后端代码而那个 uvicorn **没有 `--reload`**，故杀掉 PID 42132 后重起：
  `PE_DB_URL = app.main.DEMO_DB_URL`（`sqlite:///…/backend/pe_demo.db`，从唯一所有者读、
  不在命令行敲第二遍）、`PE_CSV_DIR = $env:TEMP\pe_demo_csv_task3`、
  `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（新 PID 14608）。
* vite（PID 56520）**复用**，未重启（HMR 吃下了全部前端改动；最终取证前又 `npm run build` 复核）。
* ⚠️ **演示库没有重跑 `demo.ps1`**：开工时实测它与派单清单逐字吻合
  （2 学期 / 60 学生 / 3 教师 / 5 教学班 / 120 选课 / 60 处方 / 8 课次 / 240 快评 /
  **841** 打卡 / 180 小测 / **30** 预警 / **19** 通知 / 5 周报；`exercises` 与
  `prescription_templates` 恒 0 行）。⚠️ 841 ≠ 840、且 19 条通知里 1 条 `is_read=true`：
  那是 **Task 2 的真 HTTP 取证留下的痕迹**（一次打卡 + 一次标已读），不是旧库。
  ⚠️ 本报告第 5 节的处置取证又改了它一次（见 §5.4），故**复现本报告前请先重跑
  `demo.ps1`**（它自带两道禁区守卫；⚠️ 它的缺省端口是 **8010** 不是 8000）。

---

## 2. 后端小修波（两处，都是 Task 2 顶回的 Critical）

### 2.1 修 1 · 补 `GET /api/students/{student_id}/notifications`

**落地位置**：`backend/app/api/routers/dashboard.py`（**已有的住址**，没有新建 router 文件）。
选它的理由：本模块的自述就是「读端点的家」（改前四个、改后五个），而
`POST /api/notifications/{id}/read` 住的 `alerts.py` 自述是「这两张表在 API 侧唯一的
**写入方**」—— 一个 GET 放进「写入方」的模块里会让那句自述过期。

**新端点的路径与身份要求**（`app.openapi()["paths"]` 实测）：

```
GET /api/students/{student_id}/notifications
  security   = [{"X-Student-Id": []}]          ← 与 POST …/read 同档（学生头）
  判定        = current_student + require_scope(session, student_id, requester)
  response   = list[NotificationRead]           ← 全仓**第一个**回裸数组的读端点
  operationId = student_notifications_api_students__student_id__notifications_get
```

**不写第二份过滤逻辑（单一所有者）**：`dashboard.py:489-497` 原本把
「`recipient_kind == "student"` ∧ `recipient_id == student_id` ∧ `is_read == False`」
裸写在 `student_home` 里。本波把它抽成 `_student_notifications(student_id, *, unread_only)`，
返回一个 `Select`（**不是**行）：

* `student_home` 的角标 = `select(func.count()).select_from(_student_notifications(…, unread_only=True).subquery())`
  —— 仍然是一次 COUNT，不把行拉进内存；
* 新端点 = `_student_notifications(student_id).order_by(created_at.desc(), id.desc())`
  —— 排序是**展示口径**、不是筛选口径，故不住在助手里面（「新的在上面」这件事
  现在只有一个住址，前端 `Notifications.vue` 的 `.sort()` 已删）。

**为什么响应体是裸数组而不是 `Page`**：本端点没有分页参数（演示库一人一条），
回一个恒等于行数的 `total` 与两个恒为 `200` / `0` 的 `limit` / `offset` 是三个
**没有信息的键**，而前端会为它们写一段翻页代码。若将来要分页，正确做法是把
`Page` 挂上来，**不是**在客户端截断（docstring 逐字写了这条）。

**路由顺序**：三段路径，与泛型的 `/api/students/{student_id}`（两段）和
`/api/notifications/{notification_id}`（前缀就不同）都**不同形** → 顺序不承重；
仍排在 `catalog` 之前（「特例一律在泛型之前」那条不需要逐个论证的规则）。
⚠️ 它**不在** `test_feedback.py::_LITERAL_TAILED_SPECIAL_ROUTES` 那一族里：
那份清单钉的是「与 `{path}/{占位}` **同形**（两段、末段一个占位）」的特例。

**守卫（4 条，`tests/api/test_dashboard.py` 新支 E2）**：

1. `test_the_notification_list_returns_only_the_requesters_rows_newest_first` ——
   200 + 只含自己的 + 新的在前；含两个反例（发给别人的、`recipient_kind="teacher"` 而
   `recipient_id` **恰好等于**请求者学号的那一行）+ 反空转（库里确有 4 行）+
   从 `/openapi.json` 实读 `NotificationRead` 的 10 列与响应体逐行对账；
2. `test_the_notification_list_endpoint_is_scoped_to_the_requester` ——
   匿名 401 `unauthenticated` / 教师头 401 / 读别人的 **403 `forbidden`** /
   学号不在册 **403 `forbidden`**（后两档刻意同形）；
3. `test_the_notification_list_and_the_unread_badge_agree` —— **单一所有者守卫**：
   列表里 `is_read` 为假的行数 == `/home` 的 `unread_notifications`，标已读前后
   两边**同时**增减（三拍）；
4. `test_a_student_with_no_notifications_gets_an_empty_list_not_a_404` —— 一条都没有是
   `200 + []`，不是 404（演示库上 60 个学生里 41 个就是这一档）。

**真 HTTP 实测**（`$env:TEMP\pe_task3_fixwave.py`，改后的 uvicorn 上）：

```
① X-Student-Id: 4 读自己的        -> 200  [{"id": 1, …, "recipient_id": 4, …}]（1 行）
② X-Student-Id: 4 读学生 5 的      -> 403  {"error": {"code": "forbidden",
                                       "message": "学生 4 无权访问学生 5 的数据", …}}
③ 匿名                            -> 401  {"error": {"code": "unauthenticated", …}}
④ X-Teacher-Staff-No: T0001       -> 401  unauthenticated
⑤ X-Student-Id: 999999            -> 403  {"error": {"code": "forbidden",
                                       "message": "身份 999999 不是一个在册学生", …}}
对拍：/home 的 unread_notifications = 0 == 新端点列出来的未读行数 0   ✅
```

### 2.2 修 2 · 摘掉 `GET /api/mini-tests/normalized` 的教师头

**落地位置**：`backend/app/api/routers/feedback.py` 的 `normalized_scores`：
删掉 `dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]`、删掉形参
`staff_no: str = Depends(current_teacher)`、删掉函数体第一行 `require_teacher(session, staff_no)`。
（`require_teacher` / `current_teacher` / `TEACHER_STAFF_NO_SCHEME` 在本模块仍被其余
四个教师端点用着，import 不动。）

**⚠️ 派单要求「若实测发现『不新增泄漏面』的论证不成立就顶回来、不要改」。实测成立，逐格对账**：

| 本端点回的字段 | 匿名侧的出处 | 新数据？ |
|---|---|---|
| `entries[i].student_id` | `GET /api/mini-tests` 的同名列 | 否 |
| `entries[i].mini_test_id` | 同上（那一行的 `id`） | 否 |
| `entries[i].squat_score` | 同上（= `squat_30s_count`，spec §8.1） | 否 |
| `entries[i].shuttle_score` / `composite` | 由 `shuttle_20m_s`（同上）+ `GET /api/enrollments`（匿名）的班内分组**现算** | 否（纯函数） |
| `sections[i].course_section_id` / `scored_count` | `GET /api/enrollments` + 上面那些行 | 否 |
| `unassigned[i]` | 同上（`student_id` + `mini_test_id`） | 否 |

即「匿名 list 本来就能读到全部 180 行原始成绩，而 normalized 只是它们的班内百分位换算」。
这张表写进了端点 docstring 首节，并由新守卫
`tests/api/test_feedback.py::test_the_normalized_route_is_anonymous_and_a_student_can_read_it`
**逐格断言**（不只是断状态码）：三种身份一律 200 且响应体逐字相同、OpenAPI 不带
`security`（含反空转：同一份 spec 里确有 ≥9 个带 security 的 GET）、entry 的键集合恰好那 5 个、
`squat_score` 与匿名 list 的 `squat_30s_count` 逐字相等。
⚠️ docstring 里还留了一句绊网：「若将来往 `NormalizedEntryRead` 上加**任何一列原始数据**，
本节这张表就不再成立，那时要重新裁定身份口径」。

**摘 security 前后的实测状态码**（真 HTTP）：

```
                        改前        改后
匿名                    401         200   ← 派单要求的那一档
学生头 X-Student-Id: 1  401         200
教师头 T0001            200         200
三者响应体逐字相同？     ——        True（5 个 section、scored_count 30/30/20/20/20、unassigned []）
```

### 2.3 那条全仓级断言改成了什么

`tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes`
的 `expected` 清单**换了一个成员**：`+ ("/api/students/{student_id}/notifications", "get"): "X-Student-Id"`、
`- ("/api/mini-tests/normalized", "get"): "X-Teacher-Staff-No"`。于是：

* `len(expected)` **仍是 19**、`len(all_security)` **仍是 45**（+1 −1）—— 数值不变；
* 但 docstring 与末尾注释都改写成「**成员清单变了**」这一档，并逐字记下连带口径：
  路径模板 64 → **65**、操作 92 → **93**、GET 57 → **58**（匿名 47 → **48**、挂 security 的 10 → **10**）；
  并写明「数值不变**不能**被读成『本拍没被这次改动碰到』—— 恰恰相反，这两次改动一进一出，
  而本拍的 `expected` 清单是它们唯一的登记处」。

### 2.4 小修波的验收

| 验收项 | 结果 |
|---|---|
| `python -m pytest -q` | **1255 → 1260 passed**（+5 条新守卫；既有 1255 一条没退步） |
| `--cov=app.domain --cov-branch` | **1259 passed, 1 skipped**；四格**逐字不变** `1268 / Miss 0 / 376 / BrPart 0 / 100%`。⚠️ 那 1 个 skip 是**既有的**：`tests/pipeline/test_backfill.py:298-305` 在检测到 trace 钩子（coverage）时跳过墙钟断言，与本波无关 |
| 端点 | 64 路径 / 92 操作 → **65 / 93**（`app.openapi()["paths"]` 实测，不用 `len(app.routes)`） |
| 挂 security 的操作数 | **仍 45**（+1 −1） |
| GET 口径 | 57 → **58**（匿名 47 → **48**、挂 security 10 → **10**） |
| 五个指纹 | ①`D2C8E539E2FA0029` ②`5394B37F01DAC9AC` ③`822CB86A5E998301` ④`E48E3AC82BB45BB7` 四个**逐字相同**；⑤ 18 套处方模板 **18 个文件 / 合计 123 848 B** 与基线逐字相同（⚠️ 合计指纹 `83DA02814A29679C` 的**算式**我没能复现，见 §7 待清扫 3） |
| `git diff b30a748 HEAD -- backend/data` | **空** |
| `Test-Path backend\pe.db` | **False** |
| `backend/data/seed/` | **0 文件** |
| commit | **单独一个**：`8217e72`（9 个文件：后端 2 生产 + 3 测试 + 前端 4 消费端） |

⚠️ commit `8217e72` 里带了 4 个前端文件（`endpoints.ts` / `types.ts` / `MiniTest.vue` /
`Notifications.vue`）：它们是修 1/修 2 的**直接消费端**（派单修 1 ③ 逐字要求改
`listMyNotifications` 的函数体），与「Task 3 的前端代码」不是一回事，故留在小修波里。

---

## 3. 4 个页面逐个（端点实测路径 / 读了哪些字段 / null 怎么显示）

⚠️ 身份口径先说清楚（派单第 1 条顶回的那一档，我**自己**从 `/openapi.json` 复核过）：
GET 共 **58** 个 = **48 匿名 + 10 挂 security**；大屏那两个 GET
（`/api/dashboard/class/{id}` 与 `/api/dashboard/weekly-class-report/{id}`）**确实挂教师头**，
且过 `require_teaches_section`（实测 T0001 读班 2/4/5 一律 **403 `forbidden`**）。
故 4 个教师页**必须在教师身份下工作**（`IdentitySwitcher` 能切、`?teacher=T0001` 深链接也能认）。

### 3.1 大屏 `views/teacher/Dashboard.vue`（`/t/dashboard`，深底 `--ink`）

| 端点（实测路径） | 身份 | 读了哪些字段 |
|---|---|---|
| `GET /api/teachers?limit=200` | 匿名 | `staff_no` / `id` / `name`（工号 → teacher.id） |
| `GET /api/course-sections?limit=200` | 匿名 | `id` / `teacher_id` / `name` / `grouping_mode`（→「我任教的班」） |
| `GET /api/enrollments?limit=200` | 匿名 | `course_section_id` / `student_id`（名册；预警的班级归属靠它反查） |
| `GET /api/alerts?limit=200` | 匿名 | `id` / `level` / `rule_id` / `status` / `student_id` / `triggered_at` |
| `GET /api/students?limit=200` | 匿名 | `id` / `name`（榜上与名单上要显示人） |
| `GET /api/class-sessions?limit=200` | 匿名 | `id` / `course_section_id` / `session_date` / `period` / `rpe_opened` |
| `GET /api/dashboard/class/{course_section_id}?as_of=` | **教师头** | 顶栏 9 键 + `blocks` 7 键 + `rpe_threshold_lines` + `screen_thresholds` |
| `GET /api/class-sessions/{id}/rpe-token` | **教师头** | `class_session_id` / `rpe_token`（**每个班只读一次**、缓存） |
| `POST /api/class-sessions/{id}/open-rpe` | **教师头** | `rpe_token` / `already_open`（**只在点按钮时发**） |

**null 的处置**：`rpe_summary.mean` → StatBlock「—」+ caption「这一周没有课堂快评（不是 0 分）」；
`rpe_summary.curve[i]` → 「—」+「无快评」；`checkin_rate_by_layer[层].rate` → 「—」+ 空的虚线轨道；
`abnormal_roster[i].peak_rpe` → 「—」；`layer_distribution.previous` / `flow.has_previous=false` →
「暂无环比数据」（与「本周无人流动」**不混为一谈**）；`alert_summary[档]` 缺键 → 「—」。

**⚠️ 派单第 3 条顶回的那一档在这里不成立**：整屏响应体的 `blocks` **七个键里根本没有训练量**
（`layer_distribution` / `rpe_summary` / `checkin_rate_by_layer` / `progress_board` /
`alert_summary` / `suggestion` / `abnormal_roster`），故「本周概览」**结构上不可能**撞上
跨单位求和。本页把这件事**写在页面上**（「本块没有『本周训练量』：整屏响应体的七个键里
根本没有训练量那一格……」），而不是默默不提。

**口令投屏**：优先 `GET …/rpe-token`（派单第 15/16 条与 fix 波 2 顶回 2 的理由）；
`rpe_opened` 为假 → **409 `rpe_not_opened`** 渲染成「这一节课还没发起」+ 发起按钮；
口令用 56px Barlow Condensed 800 + 0.14em 字距反白投屏（宽度算式见 §6）。
演示库的 8 节课只排给了班 1 与班 2，故班 3/4/5 的那一格是「这个班还没有课次」的空态。

### 3.2 班级周报 `views/teacher/ClassReport.vue`（`/t/report`，浅底）

| 端点 | 身份 | 读了哪些字段 |
|---|---|---|
| `GET /api/teachers` / `GET /api/course-sections` / `GET /api/students` | 匿名 | 同上 |
| `GET /api/weekly-class-reports?limit=200` | 匿名 | `course_section_id` / `week`（只为了知道哪几周**有**周报；⚠️ 它的 list 项排掉了全部 5 个聚合列，故**不能**替代下一行） |
| `GET /api/dashboard/weekly-class-report/{course_section_id}?week=` | **教师头** | 12 列全给：5 个 `JsonText` 聚合列 + `suggestion` + `generated_at` + `batch_id` |

5 个聚合列各一块（① 分层分布 + 环比流动 / ② 人均 RPE + 7 天 / ③ 三层完成率 /
④ 进步榜 / ⑤ 预警汇总）。`suggestion` **原样显示**（编者按那一块，页面上写明
「本页不按 mean_rpe 再判一次」）。
⚠️ `week` 缺省时后端取「这个班**已存下来的最新一周**」（`ORDER BY week DESC LIMIT 1`），
**不是** `as_of` 所属的那一周 —— 故本页不需要传 `as_of`，也不会因为「真实今天是 2026-10-11」而读空。
⚠️ 404 `no_weekly_report` → 「本周周报将在周日生成」+ 后端判据 + 去大屏的按钮，**不渲染成一堆 0**
（取证见 §5.2 的 `?week=5` 深链接）。

### 3.3 预警队列 `views/teacher/AlertQueue.vue`（`/t/alerts`，浅底）

| 端点 | 身份 | 读了哪些字段 |
|---|---|---|
| `GET /api/alerts?limit=200` | 匿名 | 13 个 list 键（⚠️ 不含 `trigger_snapshot`） |
| `GET /api/students` / `course-sections` / `teachers` / `enrollments` | 匿名 | 姓名 / 班名 / 我的班 / 名册反查 |
| `POST /api/alerts/{alert_id}/handle?as_of=` | **教师头** | 响应 4 键 `alert` / `action` / `adjustment` / `notification` |
| `GET /api/teacher/students/{id}/weekly-sheet?as_of=` | **教师头** | 处置成功后**回读**训练单（派单逐字要求） |

四档筛选（level / status / 归属 / 教学班）**一律客户端**（约束第 9 条），且这件事
**写在页面上**（「`?level=red` 会被 FastAPI 静默忽略」）。筛选档支持从 URL 初始化
（`?scope=section` 等），理由见 §5.3。
三个动作按钮从 `present.ts` 的 `HANDLE_ACTION_OPTIONS` 渲染（字面值仍由
`api/types.ts` 的 `HANDLE_ACTIONS` 持有）；`status != 'pending'` 的行按钮**不出现**（不是禁用）
并写明 409 `alert_not_pending` 的理由（0.8 × 0.8 = 0.64）。
`reduce_20pct` 的 `adjustment === null` 渲染成「本周已经减过量了，本次未再减」
（**有信息的一档**，HTTP 仍是 200、status 仍变 handled）。
处置成功后回读训练单，把 `factorSentenceOf(...)`（「本周减量 20%（由 N 条红色预警触发）」）
与**按单位分列**的训练量显示出来（⚠️ 刻意不加总，页面上写明 `prescription_stage.py:411-417` 的理由）。

### 3.4 学生详情 `views/teacher/StudentDetail.vue`（`/t/students/:studentId`，浅底）

| 端点 | 身份 | 读了哪些字段 |
|---|---|---|
| `GET /api/students/{id}` | 匿名 | 6 列（姓名/学号/性别/出生/院系/年级） |
| `GET /api/teacher/students/{id}/weekly-sheet?as_of=` | **教师头** | 6 键（约束第 14 条：走这个变体） |
| `GET /api/mini-tests?limit=200` | 匿名 | 客户端按 `student_id` 过滤；**顺带**给出 `semester_id` / `week`（normalized 的两个必填参数） |
| `GET /api/mini-tests/normalized?semester_id=&week=` | **匿名**（小修波后） | `sections[].entries[]` 5 键 + `scored_count` + `unassigned` |
| `GET /api/stratification-results?limit=200` + `GET /api/stratification-results/{id}` | 匿名 | list 8 键 + 详情的 `input_snapshot.reason`（list 排掉了 `input_snapshot`） |
| `GET /api/alerts?limit=200` | 匿名 | 客户端按 `student_id` 过滤（他的预警 + GREEN_MASTERY 的行） |

**⚠️️ `/api/students/{id}/home` 在教师身份下的实测状态码与处置（派单点名的顶回候选 ②）**：

```
GET /api/students/1/home                          + X-Teacher-Staff-No: T0001  -> 401 unauthenticated
GET /api/students/1/weekly-sheet                  + 同上                      -> 401 unauthenticated
GET /api/students/1/training-logs/completion-rate + 同上                      -> 401 unauthenticated
GET /api/students/1/prescriptions/current         + 同上                      -> 401 unauthenticated
GET /api/students/1/notifications                 + 同上                      -> 401 unauthenticated
（学生 1 确实由 T0001 本学期任教：他选在班 1 与班 5，班 1 是 T0001 的）
```

即**学生侧五个端点一个都不能用教师头读**，而 `client.ts` 一次只注入一个身份头 →
「教师身份」与「读 `/home`」结构上互斥（与小修波之前的 `normalized` 同型）。
**处置 = 降级但不撒谎**，逐格找替代来源，找不到的**点名说找不到**：

| `/home` 的那一格 | 本页的替代 | 代价（写在页面上） |
|---|---|---|
| `stratification` | 匿名 `stratification-results` 的 list + detail | **拿不到 `explanation`**（它是端点用 `explain()` 现算的，库里没有这一列）；给的是同一份快照里的 `reason` + 命中规则行 |
| `weekly_sheet` | **教师侧变体**，响应体逐字相同 | 无 |
| `pending_rpe` | ——（学生的待办不是教师要看的东西） | 点名说拿不到 |
| `unread_notifications` | ——（那是**他的**未读数） | 点名说拿不到 |
| `badges.count` | 只把 `GREEN_MASTERY` 的**行**列出来 | **不给计数**（再数一遍就是那个 COUNT 的第二份实现） |

页面上有一块「教师身份读不到的五个端点」的说明区域，把上面那五个 401 的**实测原文**
贴出来，并写明**顶回**：要补齐的正确形状是给 `/home` 加一个教师侧变体
（`GET /api/teacher/students/{id}/home`，过 `require_teaches_student`），与既有的
`/api/teacher/students/{id}/weekly-sheet` 同一条处置；后端**刻意不**把学生侧端点改成
「学生或教师任一即可」（一个双身份闸门要判两条规则、失败码不同）。那是后端改动，本 Task 无权做。

---

## 4. 4 个图表组件的数据形状与 SVG 实现要点

| 组件 | 数据形状（实测） | SVG 实现要点 |
|---|---|---|
| `charts/LayerDonut.vue` | `layer_distribution.by_layer` = `{red:3, yellow:17, green:10, insufficient_data:0}`（大屏现算与周报存的那一行**同形状**） | 一个 `<circle>` 一段弧，`pathLength="100"` 让**弧长就是百分比**（不必算 2πr）；`rotate(-90)` 让第一段从 12 点起；`insufficient_data` **中性着色**（染成红/黄/绿是撒谎）；`total === 0` **不画环**；变体只声明 `color`，弧用 `stroke: currentColor`、图例色块用 `background: currentColor` → 环与图例结构上不可能漂；动效只有「段淡入」（`--dur-lane`/`--ease-lane`，母题①） |
| `charts/CompletionBars.vue` | `checkin_rate_by_layer` = 每层 `{students, measured, rate\|null}`（实测 `insufficient_data.rate === null`） | **条是 SVG、文字是 HTML**：`viewBox` 等比缩放会连字一起缩，而大屏有 18px 字号下限；`viewBox="0 0 100 10"` + `preserveAspectRatio="none"` 让轨道宽度就是百分比（只有矩形、没有圆，故 `none` 不失真）；`rate === null` 画成**空的虚线轨道**（`vector-effect="non-scaling-stroke"`）+ 「—」，**不是** 0% 的实心条；动效只有「条从左长出来」 |
| `charts/ProgressBoard.vue` | `progress_board` = `{top_n:10, top:[{student_id, change_pct}×10], regressed:[×16], unchanged:0, unmeasured:0}` | **两侧共用一个标尺**（`maxAbs` 跨 top 与 regressed；各归各的失效形态是「−10% 画得与 +235% 一样长」）；进步向右 / 退步向左，中轴是 3px 的分道线粗线；**排序与分组后端已做完**（top 降序 / regressed 升序 / 已切成两个数组）→ 派单点名的「代价过大就顶回」**不必顶**，前端只定标与画条；三档空态措辞不同（`unmeasured>0` / `unchanged>0` / 都没有），因为它们指向的下一步不同 |
| `charts/RpeTrend.vue`（Task 2 既有，未改） | 学生自己的 `rpe_record` | 本 Task **没有**复用它画班级曲线：班级的 `rpe_summary.curve` 是「每天一个均值」而它是「每次一个整数」，形状不同；大屏/周报的 7 天用一排**计时牌格子**（`null` → 「—」+「无快评」）而不是第四种图 |

⚠️ 四个组件**都不发请求**（数据由页面给）：「读哪个端点」因此只有一个住址。
⚠️ 没有引 ECharts、没有引任何 UI 库（`grep -i 'echarts|element-plus|vuetify|naive-ui'` 全仓 0 命中）。

---

## 5. 真实渲染取证

### 5.1 方法（Task 2 踩过三个坑，照它的口径办）

* `msedge --headless=new --dump-dom --force-prefers-reduced-motion --virtual-time-budget=25000`；
  ⚠️ 必须加 reduced-motion，否则抓到 StatBlock 滚动中途那一帧；
* ⚠️ PowerShell 的 `& msedge … > file` 得 0 字节 → 用 `Start-Process -RedirectStandardOutput`；
* ⚠️ vite 只绑 `::1` → base 用 `localhost` 不用 `127.0.0.1`；
* 断言一律在**去掉全部空白**之后比对（`--dump-dom` 的序列化在标签边界留换行，
  一段被 `<strong>` 切成三截的话纯文本里就多两个空格 —— 不去空白等于把断言绑在排版上）；
* 脚本：`$env:TEMP\pe_task3_dumpdom.ps1`（10 条 URL）+ `$env:TEMP\pe_task3_assert.py`
  （**147 条断言，全绿，exit 0**）+ `$env:TEMP\pe_task3_show.py`（按关键词打印上下文）。
* ⚠️ 另外用 `--screenshot` 截了 3 张 1440px 的图**人眼复核**（`$env:TEMP\pe_task3_shot\`）：
  正是这一步抓到了两个 DOM 断言抓不到的排版 bug（见 §7 没按派单做的 4/5）。

### 5.2 10 条 URL 各自断言到的 DOM 关键内容（每条一行）

1. `/t/dashboard?teacher=T0001&as_of=2025-10-12` —— 深底壳 + 不对称网格三档类名
   （`bs-grid__alerts/layers/overview`）+「行政班01 / WEEK 6 / 名册 30 人」+ 八个区块标题 +
   环形图四档「红色层 3 10.0% / 黄色层 17 56.7% / 绿色层 10 33.3% / 数据不足 0 0.0%」+
   预警三档「7/3/4 条待处理」+ 对拍「按名册反查 7/3/4 vs 后端 alert_summary.pending 7/3/4 → 一致」+
   人均 RPE 6.37 + 锚点「略微吃力」+ 环比 +0.10 +「暂无环比数据」+ 完成率 50.0/62.7/55.0% +
   「数据不足 — 0 / 0 人」+ 口令 `4C51674D` + 异常名单 5 人 + 进步榜 +235.88% / −64.84% +
   「只轮播我任教的 2 个班」+「已停用自动轮播」（reduced-motion）。
2. `/t/report?teacher=T0001` —— 「班级周报 · 第 6 周」+ 编者按「维持当前强度」+
   ①–⑤ 五块标题 +「生成于 2025-10-12 00:00」+「暂无环比数据」+ 三层完成率 +
   进步榜 top_n=10 / 退步 16 人 + 预警汇总 8/0/0 + 周次选择器「最新一份（后端缺省）」。
3. `/t/report?teacher=T0001&week=5` —— **404 那一档**：「本周周报将在周日生成」+
   `report_stage.REPORT_WEEKDAY = 6` + `no_weekly_report` +「不会把这一档渲染成一堆 0」+
   后端 message「第 5 周没有周报」；且**一个 `50.0%` 都没出现、①–⑤ 一块都没渲染**。
4. `/t/alerts?teacher=T0001` —— 「共 30 条 · 红 11 / 黄 6 / 绿 13 · 待处理 29 / 已处理 1 /
   已忽略 0 · 学生级 30 / 班级级 0」+ 四档筛选 +「全部在客户端做」+ 三个动作按钮 +
   三条规则的中文 + 去重靠 DB 的说明。
5. `/t/alerts?…&scope=section` —— **班级级空态**：「这一档筛选下没有预警（班级级）」+
   「这不是坏了」+ `YELLOW_CLASS_RPE_HIGH` + 均值上界 6.93 +「把『归属』切回全部或学生级」；
   且没有把空态渲染成任何一条预警。
6. `/t/alerts?…&status=handled` —— 筛出 1 条；处置痕迹被翻成中文
   （「减量 20%：Plan04 Task3 的真 HTTP 取证：教师点了一次减量 20%」，裸 token 不出现）；
   三个按钮的 hint 一个都不出现 + 备注输入框不出现 +「三个按钮因此不出现（不是禁用）」+ 409 的理由。
7. `/t/students/1?teacher=T0001` —— 「周晨阳 / 2025060001 / 法学院」+「黄色层」+
   「无短板但体成分异常」+「R1,R2,Y1,Y2」+ 教师侧变体的 URL +「本周减量 20%（由 1 条红色预警触发）」+
   「训练量（按单位分列） 103.8 分钟（3 个动作）」+ 系数 0.80 + 两个班的百分位
   （教学班 1 班内 30 人 / 教学班 5 班内 20 人）+ 折返 15.0 +「比他慢的人数」+
   五个 401 的实测原文 +「已顶回控制者」。
8. `/t/students/1?teacher=T0002` —— **403 那一档**：「forbidden · 403」+
   「不是本学期任教他的老师」+ `course_section.teacher_id` +「上学期教过他」+
   后端 message 原文；姓名仍然渲染（`readStudent` 是匿名的），但训练单那一块退化成错误。
9. `/s/notifications?student=4` —— 新端点的口径写在页面上 +「本周电子勋章」+「共 1 条」+
   「未读 0 条」+「已读过」+「既不做客户端过滤、也不再 .sort()」；旧的「不存在」那句已消失。
10. `/s/mini-test?student=1` —— 班内百分位**真的渲染出来了**（「班内 30 人有成绩」/
    「班内 20 人有成绩」/ 折返 15.0 / 综合分 20.5 / 比他慢的人数）；旧的 401 解释文字
    （「这一格学生身份读不到」「挂的是 X-Teacher-Staff-No」）**一个都不出现**。

### 5.3 为什么给预警队列与周报加了「筛选/周次可从 URL 初始化」

`--dump-dom` 的无头取证**点不了按钮、也填不了输入框**。派单逐字要求「班级级筛选档要能
优雅地显示空态」与「非周日没有当周周报 → 显示『本周周报将在周日生成』」，而没有深链接的话
这两个状态**只能靠读代码断言它存在、拿不出它真的渲染出来的证据**。故加了
`?scope=` / `?status=` / `?level=` / `?section=`（预警队列）与 `?week=` / `?section=`（周报），
不合格的值一律退回缺省（与 `stores/identity.ts` 的 `adoptFromUrl` 同一条口径）。
⚠️ 顺带的好处：一条「只看红色待处理」的链接是可以分享的。

### 5.4 处置一条预警的真 HTTP 取证（原文节选，全文在 `$env:TEMP\pe_task3_handle_out.txt`）

```
>>> POST /api/alerts/1/handle?as_of=2025-10-12
    X-Teacher-Staff-No: T0001
    body: {"action": "reduce_20pct", "note": "Plan04 Task3 的真 HTTP 取证：教师点了一次减量 20%"}
<<< 200
    {"alert":{…,"status":"handled",
              "handled_action":"reduce_20pct: Plan04 Task3 的真 HTTP 取证：教师点了一次减量 20%",
              "handled_at":"2026-10-11T19:06:01.010110",…},
     "action":"reduce_20pct",
     "adjustment":null,                      ← **有信息的一档**：那一周已经有 auto 调整了
     "notification":{"id":20,…,"title":"本周训练量已减 20%",
                     "body":"…本周训练单的系数是 0.80（= 骨架 × 本周全部微调的连乘，相当于减了 20%）…"}}

改前 GET /api/teacher/students/1/weekly-sheet -> factor 0.8 / reasons ["RED_RPE_SUSTAINED"]
改后 同一个请求                              -> factor 0.8 / reasons ["RED_RPE_SUSTAINED"]   ← 逐字不变
>>> POST /api/alerts/1/handle（再处置一次）   -> 409 {"error":{"code":"alert_not_pending",…}}
>>> POST /api/alerts/2/handle {"action":"note","note":"   "} -> 422 unprocessable_value
>>> POST /api/alerts/2/handle {"action":"ACTION_REDUCE"}     -> 422 request_validation_failed
        detail.msg = "Value error, action 的取值必须是 ['ignore', 'note', 'reduce_20pct'] 之一，收到 'ACTION_REDUCE'"
改后 GET /api/alerts?limit=200  -> 30 行，status = {handled: 1, pending: 29}
改后 GET /api/notifications     -> total 20（改前 19），学生 1 多了 id=20 那一条
```

⚠️ 三个值得记进账本的实测：
1. **`adjustment === null` 而 `notification` 非 null** —— 与 `alerts.py` 的 docstring 逐字吻合
   （「一处方一周至多一条 auto 调整」，教师这一次点击有效的部分是「看过了 + 推了消息」），
   而训练单 factor **前后逐字不变** —— 约束第 13 条的那句话在真链路上成立。
2. **`ACTION_REDUCE` 是常量名、不是值**：送它得到 422，后端把三档**值**
   `['ignore', 'note', 'reduce_20pct']` 点名报了出来。派单第 6 条写的
   「三档字面写出（`ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`）」指的是
   `app/api/routers/alerts.py` 里的**常量名**；Task 1 在 `types.ts` 里写的**值**才是对的。
3. 这次取证**改了演示库**（alert #1 → handled、通知 19 → 20）。`pe_demo.db` 已进
   `.gitignore`、不入库；§5.2 的 DOM 取证是在它**之前**完成的（故 dump 里是 30 pending /
   19 通知），而 §5.2 的第 4/6 条是在它**之后**重跑的（故是 29 pending / 1 handled）——
   两批数字不同是**有意的**，恰好证明页面读的是活的后端。

---

## 6. 设计一致性自查

* **有没有写死 hex**：`grep '#[0-9a-fA-F]{3,8}'` 在 `frontend/src` 下只命中两类 ——
  `tokens.css` 的令牌定义（唯一住址），与 `base.css:286` 的 `#a93623`
  （**Task 2 已登记的待清扫**，本波没有增加第二个）。⚠️ `teacher.css:332-333` 的两个 hex
  在**注释**里（记录对比度实算值），不是色值声明。
* **有没有自己画 border**：区块分隔一律 `LaneDivider.vue` / `lane.css`；表格内部用
  `--border-hairline` / `--border-hairline-on-ink`（与 `base.css` 的 `.data-table` 同一条口径：
  分道线是**区块级**母题，铺到每一行会让整页都是线）。
* **有没有引入新 UI 库 / ECharts**：0（§4 已述）。图标一律内联 SVG 或 Unicode（✓ ✗ ⚠️ ←→）。
* **数字字体**：一律 `Barlow Condensed` / `JetBrains Mono` + `tabular-nums`（`.num` / `.data` /
  StatBlock / 图表的数字格）。
* **深底上三色的对比度实测值**（`$env:TEMP\pe_task3_contrast.py`，从 tokens.css 的**值**实算、
  不抄它注释里的数；WCAG 2.x 相对亮度公式）：

  | 前景 | 底 `--ink` | 底 `--ink-raised`（面板） | 底 `--ink-sunken`（图表凹槽） |
  |---|---|---|---|
  | `--red-on-ink` #e8695c | 5.92 | 5.44 | 6.21 |
  | `--amber-on-ink` #e8b44a | 9.90 | 9.10 | 10.40 |
  | `--moss-on-ink` #7fb98c | 8.26 | 7.59 | 8.67 |
  | `--track-on-ink` #e4674f | 5.69 | 5.23 | 5.98 |
  | `--paper` #f4f0e6 | 16.52 | 15.18 | 17.36 |
  | `--paper-soft` #cdc4b4 | 10.88 | 10.00 | 11.43 |
  | `--paper-faint` #8d8478 | 5.11 | **4.69**（最低） | 5.37 |
  | pill：`--*-on-ink` on `--*-wash-on-ink` | 4.74 / 6.92 / 6.42 | | |

  **26 对全部 ≥ 4.5:1**（AA 正文线）。⚠️ 对照组：若把学生端的 `--*-on-paper` 用在大屏上，
  只有 2.63–3.24:1 —— 这正是「三色在深底上要用 `--*-on-ink` 变体」的实测理由。
* **字号下限 18px（大屏）**：`.bs-*` 一组一律 `--fs-bs-*`（下限 `--fs-bs-small` = 18px）；
  StatBlock 的 `tone="ink"` 档把标签/数字/说明全部抬到 `--fs-bs-*`。实测修掉两处破下限的：
  `0.86em` 的 id 小字（大屏上 = 15.5px）在 `ProgressBoard` 与 `Dashboard` 各收回 1em；
  分道线的道次编号（10px）与拉丁小标签（11px）在 `.surface-ink` 下抬到 18px
  （**不动 `--lane-num-size` 那个令牌**，否则母题有两个尺寸的第二个所有者）。
  ⚠️ 学生端/办公室那三页的下限仍是 11px（375px 手机与显示器不是投影）。
* **动效只用在高价值时刻**：① 载入时分道线从左划出（`--lane-index` × 60ms stagger）；
  ② StatBlock 数字滚动；③ 大屏 5 秒轮播的 200ms `out-in` 过渡 + 进度条。
  没有 hover 浮动、没有视差。`prefers-reduced-motion` 时：base.css 的总开关压掉全部动画，
  **且大屏不自动轮播**（总开关压不掉「内容自己会变」，故页面自己判一次）。
* **大屏不出现横向滚动**：⚠️ 这一格的验证方法是**算术 + 截图人眼复核**，不是浏览器量出来的
  （`--dump-dom` 给不出 `scrollWidth`）。算术：12 列网格每列 97.67px（1392px 内容宽、gap 20px），
  每排的跨度合计都是 12；两个实测出来的最小内容宽（CompletionBars 一行 366px、RPE 七天每格
  120px）都小于它们所在面板的内容宽（418.7px / 889.3px）。截图复核见 §5.1。
  ⚠️ 这一轮**真的抓到了两处会溢出的排版**并已修（§7 没按派单做的 4/5）。

---

## 7. 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 7.1 待清扫（6 条）

1. **`base.css:286` 的 `#a93623`**（Task 2 登记的，全仓唯一写在 tokens.css 之外的色值）—— 本波未动。
2. **`tokens.css:29` 的注释说 `--ink-faint` 对 paper ≈ 4.6:1，实测是 4.31:1** —— 低于 AA 正文线 4.5。
   它是**学生端/办公室页**的元信息字色（本波没引入、也没加重它的使用）；
   大屏那一侧用的是 `--paper-faint`（4.69–5.37:1，过线）。建议下一波把 `--ink-faint` 压深一档。
3. **18 套处方模板的合计指纹 `83DA02814A29679C` 与 `backend/data` 全量指纹 `DD64C37D7D48057B`
   的算式没能复现**（试了 12 种拼接口径都不等于）。替代判据（**更强**）：
   `git diff b30a748 HEAD -- backend/data` 为空 + `git status -- backend/data` 干净 +
   模板 18 个文件 / 合计 123 848 B + data 全量 24 个文件 + 四个单文件指纹逐字相同。
   ⚠️ 算这两个合计指纹的脚本当年住在 TEMP、已删，故口径失传 —— 建议把算式写进
   `tests/` 或 Plan 03 的报告里，否则下一次还是只能靠 git。
4. **`0.6275 × 100` 在浮点下是 `62.74999…` → `toFixed(1)` 给 `62.7%`**（不是 62.8%）。
   一个 0.05pp 的舍入 artifact；`present.ts` 的 `toPercent` 与 `CompletionBars` 同一条算式，
   故学生端与教师端**一致地**显示 62.7%。要修就得在后端的 `RATE_PRECISION` 那一档修，
   前端自己 round 一次就是第二个所有者。
5. **`training_log`（841 行）与 `rpe_record`（240 行）仍然只能「拉全量 + 客户端过滤」**：
   小修波只给 `notifications` 开了服务端窄端点。要不要给这两张表也开，留给控制者裁定
   （`endpoints.ts` 的那一节注释逐字记了这件事）。
6. **演示库被处置取证改过一次**（alert #1 → handled、通知 19 → 20）。`pe_demo.db` 不入库；
   Task 5 开工前按派单惯例重跑 `demo.ps1` 即可（⚠️ 它的缺省端口是 8010）。

### 7.2 关切（2 条，都是既有的、本波只复核）

1. 教师侧的写入端点（`overrides` / `regenerate` / `handle` / `open-rpe` / `batch` / `run-daily`）
   今天只过「在册」闸门、不过任教关系闸门（`feedback.py` 模块 docstring 逐字登记过）；
   本波**没有**收窄它们（那会改掉教师端的可点范围，移交 Plan 04 的控制者）。
2. 大屏的异常名单阈值（`screen_thresholds` = 3 天 / RPE > 8）与预警判据线（7 / 9）是**两套并存**的
   东西（`dashboard.py` 的 docstring 逐字），页面上已写明「不得混用」。

### 7.3 没按派单做的地方（6 处，逐条给理由）

1. **`endpoints.ts` 不止改了 `listMyNotifications` 的函数体**：按本文件自己的约定
   （「每个端点一个函数」）新增了 `listStudentNotifications`，`listMyNotifications` 的**签名逐字不变**、
   函数体改走它（`Notifications.vue` 的数据接线因此一行没动）。
   ⚠️ 同时更正了 4 处**已过期**的注释（「不存在这个端点」「47 个 GET 全部匿名」等）——
   留着假话比多改一行注释更糟。
2. **`Notifications.vue` 与 `MiniTest.vue` 不是「一行都没改」**：Task 2 那句「后端一改本页一行
   都不用动」在**渲染**上成立（MiniTest 的成功支路真的零改动亮起来了），但两页都**故意**把
   口径写成了页面内容（「这个端点不存在」「挂的是 X-Teacher-Staff-No / 学生头 401」），
   后端一改那些话就成了假话。故：MiniTest 的 401 解释块换成**与 code 无关**的一档
   （只报 code/status/message，不再对身份口径下断言）；Notifications 的第 01/03 块按新口径改写、
   并删掉客户端 `.sort()`（排序搬进服务端了，「新的在上面」现在只有一个住址）。
3. **`present.ts` 从 `views/student/present.ts` 搬到了 `src/present.ts`**（派单写的就是 `src/present.ts`，
   而 Task 2 把它建在了学生端目录下）。搬动只改了 6 个学生端页面的 import 路径，一个函数都没动；
   理由：它现在是**两端共用**的标签所有者，留在 `views/student/` 下会让教师页面写出
   `../../views/student/present` 这种跨端伸手的 import。
4. **修了 `App.vue` 的一格（Task 1 的潜在 bug）**：`.body--wide` 原本绑在 `meta.surface === 'ink'` 上，
   于是教师端另外三页被挤进学生端的 375px 壳里（1440px 截图上 30 行预警竖成一列窄条）。
   计划非目标第 5 条逐字是「教师端按 1440px 宽设计」，没有说「只有大屏那一页」。
   故新增 `meta.wide`（4 条 `/t/*` 全带），宽壳与深底**各管一件事**。
5. **给预警队列与周报加了「筛选/周次可从 URL 初始化」**（§5.3）：无头取证点不了按钮，
   没有它就拿不出「班级级空态」与「404 no_weekly_report」真的渲染出来的证据。
6. **commit 的切分与派单建议略有不同**：派单建议 ② = 「4 个图表组件 + teacher.css」、
   ③ = 「4 个页面 + 路由 + endpoints/present」。实际 ② = 共享层（teacher.css + TeacherNav +
   3 个图表 + present.ts 搬迁与扩展 + 6 个学生页 import + WeeklySheet 的 factorSentence 委托 +
   main.ts），③ = 4 个页面 + router + App.vue。理由：`present.ts` 的搬迁与扩展是**共享层**的活，
   放进「页面」那个 commit 会让 ② 单独 checkout 出来编译不过。

### 7.4 顶回控制者的地方（2 处顶回 + 2 处「不必顶」的核实）

**顶回 1（Critical 级）**：`GET /api/students/{id}/home` 在教师身份下是 **401**，而派单把它列进了
学生详情页的端点清单。处置 = 降级但不撒谎（§3.4 的那张表）+ 页面上贴五个 401 的实测原文 +
给出正确形状（给 `/home` 加教师侧变体）。**这是后端改动，本 Task 无权做**，故顶回。

**顶回 2**：派单第 3 条说「大屏的『本周概览』会撞跨单位求和那一档，也必须按单位分列」。
**实测不成立**：整屏响应体的 `blocks` 七个键里**根本没有训练量**，故大屏结构上不可能撞那一档。
（学生端首页与教师端学生详情**确实**有训练量，两处都按单位分列、都不加总。）
页面上把这件事写明，而不是默默不提。

**不必顶 1**：派单点名的顶回候选 ③（「若 progress_board 要排序+分组+双向条形而代价过大就顶回」）。
实测**代价不在前端**：后端已把 `top` 降序、`regressed` 升序排好并切成两个数组，前端只定标与画条。
Task 1 那句「只核到数据形状够简单、没有实测渲染代价」的担心在这里落空了。

**不必顶 2（但给了处置）**：派单点名的顶回候选 ④（「5 秒轮播与 StatBlock 数字滚动会不会打架」）。
**会**，如果什么都不做：`rollTo` 从当前显示值滚到新值，切班时「行政班01 的 6.37」会**变形**成
「提升班的 5.9」，读起来像同一个班的数字在抽搐。三条处置：① `:key="sectionId"` 挂在被轮播的
子树上 → 切换是**重建**，数字从 0 滚到新值（一次干净的「计时牌归零再走」）；② `Transition
mode="out-in"` + 200ms → 任何时刻只有一帧在场，且 200ms ≪ 5000ms 的停留；③ reduced-motion 时
**根本不自动轮播**。外加一条 5 秒进度条回答「还有多久切下一个班」。

**逐条核过、决定不顶的派单决定**：① 修 2 的「不新增泄漏面」论证（逐字段对账后成立，§2.2）；
② 「预警是 30 行不是 11 行」（实测 30，页面上把 11 是红色那一档写清楚）；③ 「RPE 是 CR-10、
7–8 琥珀 / 9–10 砖红」（`present.ts` 的 `RPE_SCALE` / `rpeToneOf` 两端共用）；④ 「list 项键集合
用 types.ts 的 23 个手写类型」（未重推，直接用）；⑤ 「三档动作字面写出」（值在 `types.ts`，
标签在 `present.ts`，`Record<HandleAction, …>` 是编译期穷尽性守卫）；⑥ 「14 个错误 code 的清单」
（`client.ts` 的 `ERROR_CODES` 已含全部，本波新碰到的 `alert_not_pending` / `no_weekly_report` /
`forbidden` / `unprocessable_value` / `request_validation_failed` 五档都在页面上给了人话）；
⑦ 「通知一人一条，教师端若要显示本班通知要按班级过滤，代价过大就只显示计数」——
实测代价**不大**（`enrollments` 是匿名的，一次 200 行），故大屏直接列出本班学生的预警行，
没有退化成只显示计数；⑧ 「exercise / prescription_template 恒 0 行」（本波没读这两个资源）；
⑨ 「as_of 一律 2025-10-12」（4 个页面全部从 `identity.asOf` 取，缺省就是它）。

---

## 8. 最终验收

| 验收项 | 结果 |
|---|---|
| `npm run build` | **退出码 0**；114 modules；主 chunk **CSS 59.83 kB**（gzip 9.69）/ **JS 225.10 kB**（gzip 81.08）；懒加载 chunk：Dashboard 21.52/8.49、StudentDetail 27.45/9.91、AlertQueue 19.66/7.64、ClassReport 16.56/6.91、ProgressBoard 11.19/4.16、TeacherNav 2.71/1.39（kB，JS/gzip）；CSS chunk 2.36–11.85 kB |
| `@ts-ignore` / `as any` | **0 / 0**（`vue-tsc -b` 全绿） |
| 后端 `pytest -q` | **1260 passed**（1255 + 5 条新守卫；既有一条没退步） |
| 后端覆盖率四格 | **1268 / Miss 0 / 376 / BrPart 0 / 100%**（逐字不变） |
| 端点 | **65 路径模板 / 93 操作 / 挂 security 45**（`app.openapi()["paths"]`） |
| GET 口径 | 58 = 48 匿名 + 10 挂 security |
| 禁区 ① | `backend/pe.db` **不存在** |
| 禁区 ② | `backend/data/seed/` **0 文件** |
| 禁区 ③ | `git diff b30a748 HEAD -- backend/data` **为空**（且 `git status -- backend/data` 干净） |
| 禁区 ④ | 四个单文件指纹**逐字相同**：`D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` |
| 禁区 ⑤ | 18 套处方模板 **18 个文件 / 合计 123 848 B**、data 全量 **24 个文件**，与基线逐字相同（⚠️ 合计指纹的算式失传，见 §7.1-3） |
| 真实渲染取证 | 10 条 URL、**147 条断言全绿**（exit 0）+ 3 张 1440px 截图人眼复核 |
| 处置预警的真 HTTP | 200（`adjustment: null` + 通知 id 20）→ 训练单 factor 前后逐字不变 → 再处置 409 `alert_not_pending` → 空备注 422 → 非法 action 422 并点名三档合法值 |
| `git status --short`（结案时） | **空** |

**commit**：

| sha | 一句话 |
|---|---|
| `8217e72` | 后端小修波：补 `GET /api/students/{id}/notifications`（学生头 + require_scope，过滤条件抽成单一所有者）+ 摘掉 `normalized` 的教师头（泄漏面逐字段对账后成立）+ 5 条守卫 + 全仓级断言的成员清单换血（数值 19/45 不变）+ 前端消费端 |
| `66f9df7` | 教师端共享层：`teacher.css`（两档布局 + 不对称网格的跨度算式）+ `TeacherNav` + 3 个手写 SVG 图表 + `present.ts` 搬到 `src/` 并加教师端那一节 |
| `0a74054` | 教师端 4 个页面 + 路由接线（4 条 `/t/*` 换真页面、懒加载）+ `App.vue` 的宽壳与深底拆开（`meta.wide`） |
| 本报告的 commit | 取证与报告 |

**Task 5 的蓝本**（留在 `$env:TEMP`，未删）：
Task 2 的 `pe_dom_evidence_t2.py` / `pe_http_evidence_t2.py`（派单点名不要删的两个）+
本波的 `pe_task3_dumpdom.ps1`（10 条 URL 的 dump）/ `pe_task3_assert.py`（147 条断言）/
`pe_task3_handle.py`（处置链的真 HTTP）/ `pe_task3_contrast.py`（对比度实算）/
`pe_task3_show.py`（按关键词打印 DOM 上下文）。
