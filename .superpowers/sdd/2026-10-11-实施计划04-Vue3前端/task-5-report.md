# Plan 04 Task 5 实现报告 —— 真实联调（15 步全绿 / 退出码 0）

> **日期**：2026-10-11 · **分支**：`feature/plan-04-frontend`
> **交付**：`frontend/scripts/smoke.mjs`、`package.json` 的 `smoke` script、
> `Document/2026-10-11-前后端联调取证.md`（97 747 B / 3 949 行）、4 张截图
> **commit**：`99dc94a`（smoke.mjs + script）；取证文档 / 截图 / 两份报告在下一个 commit 入库

---

## 1. `smoke.mjs` 的 15 步逐步结果

跑法：`demo.ps1 -Port 8000` 复原演示库 → `npm run dev` → `npm run smoke`。
**退出码 0**；**15/15 步全绿**；**172 条断言 0 红**。逐步：

| 步 | 结果 | 关键断言值 |
|---|---|---|
| 0 演示库复原核实 | 绿 11/11 | 7 张表 60/19/60/840/240/5/30；预警红 11 绿 13 黄 6、全 pending、全学生级 |
| 1 `/api/health` | 绿 5/5 | `tables == 25`、`students == 60`、响应恰好 3 键（未定型 → 手写 `HealthRead`） |
| 2 教师头建课次 | 绿 7/7 | 201；响应**没有** `rpe_token`、恰好 6 键；匿名 POST → 401 `unauthenticated` |
| 3 open-rpe + 匿名 list 不含口令 | 绿 9/9 | 口令 16 字符；匿名 `GET /api/class-sessions` 的**整份原文**不含它；list 项 6 键无口令 |
| 4 读口令的身份 | 绿 7/7 | 匿名 401；教师头 200 且与第 3 步逐字相同；未发起的课次 409 `rpe_not_opened` |
| 5 学生交快评 | 绿 9/9 | 201（`student_id` 由头填、`submitted_at` 服务端填）；再交 409 `integrity_conflict`；错口令 403 `invalid_rpe_token` |
| 6 学生打卡 | 绿 10/10 | 201；`submitted_at`/`late`/`source`/`batch_id` 都在响应里而**不在**请求体里；同日再打 409 |
| 7 学生训练单 | 绿 16/16 | `factor` 是数、`sessions[].blocks` 合计非空；教师头调学生侧 401；教师侧变体与本人侧**逐字相同**；不在自己班里 403 `forbidden`；越权 403 |
| 8 大屏与周报 | 绿 14/14 | 班 1 三层完成率 0.5/0.6275/0.55（不是全 0、且有非 null）；`progress_board` 非空；`?week=7` → 404 `no_weekly_report`；⚠️ `?as_of=` 在本端点被静默忽略 |
| 9 预警处置 | 绿 13/13 | `reduce_20pct` → 200；再处置 409 `alert_not_pending`；送 `ACTION_REDUCE`（计划正文写的常量名）→ **422 且响应点名** `ignore`/`note`/`reduce_20pct`；`ignore` 与 `note` 各 200；`note` 空白 → 422 |
| 10 写入侧强制 | 绿 13/13 | 匿名 POST semesters 401；教师头 201；**DELETE 405 `http_405`**（顶回，见第 4 节）；teachers 建+删 201/204；restrict 删学生 1 → 409 且 message 点名 12 张子表、`detail` 为 null |
| 11 只读被写 | 绿 6/6 | 匿名与教师头 POST `/api/prescriptions` 都是 405 `http_405`；DELETE `/api/alerts/1` 405 |
| 12 反查目录（5 拍） | 绿 22/22 | 见第 2 节 |
| 13 学生端两个新端点 | 绿 14/14 | 学生头 200 且**裸数组**、只含自己、已按 `created_at` 降序；匿名 401；越权 403；教师头 401；`/api/mini-tests/normalized` 匿名 200、`sections[].scored_count` 齐全 |
| 14 13 条路由 DOM | 绿 16/16 | 见第 3 节 |

⚠️ 第 0 步同时是「你是不是忘了重跑 `demo.ps1`」的守卫：本脚本会写脏演示库
（含一个 `forbid` 删不掉的学期），脏库上第 0 步必红。

## 2. 第 12 步的 5 拍

目录是**用 Node 24 的类型剥离直接 `import` 那个 `.ts` 文件**读出来的
（`import type` 会被擦掉，故不需要 vite / tsc；不是正则抠源码文本）。

| 拍 | 结果 |
|---|---|
| ① 23 个资源的集合路径与成员路径都在 `/openapi.json` 里 | ✅ 23/23 |
| ② `writable=false` 的 14 个没有泛型 CRUD 的 POST/PATCH/DELETE | ✅ 14/14。⚠️ 其中 `rpe-records` / `training-logs` / `mini-tests` **有特例 POST**（学生头/教师头的窄端点），判据是 operationId 不是 `create_row_*` |
| ③ `writable=true` 的 9 个 POST/PATCH 齐全、DELETE 与 `on_delete` 一致 | ✅ 9/9；`semesters`（forbid）无 DELETE → 全库只有 **8** 个 DELETE |
| ④ 每个 `pkField` 与成员路径的参数名逐字相同 | ✅ 23/23（含 `fitness-test-batches` → `fitness_test_batch_id` 那唯一一处手工覆盖） |
| ⑤ 每个 list 端点的响应确实未定型 | ✅ 23/23 全是 `{type:object, additionalProperties:true}`（加 `/api/health` 共 24）→ `api/types.ts` 的 23 个手写类型是**必要的** |

顺带从同一份 openapi 数出：路径模板 **65** / 操作 **93** / 挂 security **45** /
GET **58** = 匿名 **48** + 挂 security **10** —— 与派单逐字一致。

## 3. 第 14 步：13 条路由的 DOM 断言逐条

needle 里的姓名/学号/班名**不是写死的**：脚本先 `GET /api/students?limit=200` 与
`GET /api/course-sections?limit=5` 取真值当 needle，故「页面渲染的是后端给的那份数据」
也被断言到了。

| 路由 | 断言到的关键内容 |
|---|---|
| `/s/home?student=4&as_of=2025-10-12` | 「的本周」+ 赵锦程（真姓名）+ 2023120001（真学号）+「本周训练量」 |
| `/s/weekly-sheet?student=4&…` | 「本周训练单」+「第 6 周」 |
| `/s/check-in?student=4&…` | 「每日打卡」+「提交时刻与『是否迟交』都由服务端算」 |
| `/s/rpe?student=4&…` | 「课堂快评」+「口令请照老师投屏上的那一串手输」 |
| `/s/mini-test?student=1&…` | 「二次小测」+「30 秒深蹲」 |
| `/s/notifications?student=4&…` | 「消息中心」+「未读」 |
| `/t/dashboard?teacher=T0001&…` | ALERTS / LAYERS / THIS WEEK / CHECK-IN + 行政班01（真班名） |
| `/t/report?teacher=T0001&…` | 「班级周报」+「① 分层分布」+「③ 三层完成率」+「④ 进步榜」 |
| `/t/alerts?teacher=T0001&…` | 「预警队列」+ FILTERS + QUEUE |
| `/t/students/{T0001 任教的学生}?…` | 那个学生的真姓名 +「当前分层」+「本周训练单」 |
| `/admin` | 「资源目录」+「23 resources」+「可写 9」+「只读 14」+ spec §4.4 那句 |
| `/admin/students?teacher=T0001` | 「学生」+ `/api/students` +「共 60 行」+ 赵锦程 +「＋ 新建一行」 |
| `/admin/students/4?teacher=T0001` | 「学生 #4」+ 2023120001 + 赵锦程 +「✎ 编辑」+ `student_no` |

**截图（人眼复核过，存进 `Document/`）**：

- `Document/2026-10-11-screenshot-student-home.png`（375×1600）
- `Document/2026-10-11-screenshot-teacher-dashboard.png`（1440×1400）
- `Document/2026-10-11-screenshot-admin-index.png`（1440×1800）
- `Document/2026-10-11-screenshot-admin-list.png`（1440×1400）

⚠️ 管理台的「新建/编辑/删除」**无法**用 `--dump-dom` 交互取证，故用了三层替代：
① 真 HTTP 取证（9 个资源逐个建/改/删 + restrict 的 409 原文 + cascade 的前后计数，
见取证文档附 C）；② `?new=1` / `?edit=1` 深链接让表单在 DOM 里渲染出来，并断言字段清单
（semesters 5 格 / interest-surveys 6 格含两个 JSON 文本域 / class-sessions 5 格**无** `rpe_token`）；
③ 表单把「将提交的请求体 / 差集」渲染成文本，编辑表单刚打开时差集为 `{}`（0 格）——
这证明预填逐字等于 read-one 的原值。

## 4. 待清扫 / 关切 / 没按派单做的 / 顶回

**顶回（3 处）**：

1. **派单第 10 步「再 DELETE 它 → 断言 204」是错的**：`semesters` 是 23 行里唯一
   「可写 + `on_delete='forbid'`」的资源，后端**不注册** DELETE → 实测 **405 `http_405`**。
   （派单第 12 步自己也写了「`semesters` 除外，它是 `forbid` 故没有 DELETE」。）
   脚本改为断言 405，并另用 `teachers` 做「建 → 删 = 201 → 204」的真取证。
2. **派单第 7 步「断言 `factor` 与 `blocks` 非空」的形状不对**：响应体**没有**顶层 `blocks`，
   它在 `sessions[].blocks`（一天一组）。断言改为 `sessions` 非空 + 全部 `blocks` 合计非空。
   同一步还发现教师侧变体只对「他本学期任教的学生」开放：**学生 4 不在 T0001 的班里**
   （`require_teaches_student` → 403），故「两个变体逐字相同」那一拍改用脚本现找的一个
   T0001 任教的学生，并把「学生 4 → 403」单独断言成一条。
3. **派单第 8 步用 `as_of` 试「非周日 404」试不出来**：`/api/dashboard/weekly-class-report`
   的参数是 **`week`**，`?as_of=` 被 FastAPI **静默忽略**（约束第 9 条那一族的又一例）。
   脚本两拍都断言：`?as_of=2025-10-15` → 200 且回第 6 周（证明它被忽略）；
   `?week=7` → 404 `no_weekly_report`。

**没按派单做的（2 处）**：

1. **第 14 步做进了 `smoke.mjs` 内部**（`child_process.spawn` 起无头浏览器），而不是
   派单字面的「smoke 之外另跑」。理由：派单的验收是「`node frontend/scripts/smoke.mjs`
   退出码 0、15 步全绿」，而第 14 步是 15 步之一；让它留在脚本外，「退出码 0」就证明不了
   「13 条路由真的渲染出来了」。脚本内绕开了三个已知的坑（`--force-prefers-reduced-motion` /
   不经 shell 重定向 / 基址 `localhost`）。找不到浏览器或前端没起时第 14 步**红**，不静默跳过。
2. 取证文档里的分页响应只展开前 6 行 + 信封四键（否则一份 200 行的 list 会把文档撑到几百 KB）；
   全文在 `PE_SMOKE_TRANSCRIPT` 指向的 JSON 里（`/openapi.json` 那份 278 KB 只记字节数）。

**待清扫（2 条）**：

1. smoke 跑完的演示库是脏的（第 2/4/5/6/9/10 步的写入，含一个删不掉的学期）——
   文档第 0 节与脚本结尾都写了「再跑之前先重跑 `demo.ps1`」。
2. `Document/` 下的截图是 ASCII 文件名（PowerShell 5.1 读无 BOM UTF-8 的 `.ps1`
   会把中文文件名写坏，第一版落地成了乱码名）。

**关切（1 条）**：第 14 步 13 次起浏览器约 40–60 秒，是整条 smoke 里最慢的一段；
若以后进 CI，建议把 `--virtual-time-budget` 调小或并行。

## 5. 最终验收

- `node frontend/scripts/smoke.mjs` **退出码 0**，**15/15 步全绿**，172 条断言 0 红。
- 取证文档 `Document/2026-10-11-前后端联调取证.md`：**97 747 B / 3 949 行**，
  每一步都有请求与响应原文（分页只展前 6 行 + 信封，全文在 transcript）。
- 跑完复核：`Test-Path backend\pe.db` = **False**；`backend/data/seed/` = **0 文件**；
  `git status --short` 里没有 `node_modules` / `pe_demo.db` / `frontend/dist`。
- 后端**没改一个字节**，故：
  - `python -m pytest -q`（不带 coverage）= **1260 passed**。⚠️ 带 `--cov` 跑是
    **1259 passed + 1 skipped**：`tests/pipeline/test_backfill.py` 里那条墙钟断言在
    `sys.gettrace() is not None` 时**自己 skip**（coverage 会装 trace 钩子），
    不带 coverage 单跑该文件 8/8 通过。两个口径都对，差别只在跑法。
  - `--cov=app.domain --cov-branch` 的 TOTAL 四格 = **1268 / 0 / 376 / 0 / 100%**，逐字不变。
  - 端点 **65 个路径模板 / 93 个操作 / 45 挂 security / GET 58（48 匿名 + 10 挂 security）**，
    逐字不变（smoke 第 12 步从活的 `/openapi.json` 现数）。
- `npm run build` 退出码 0；0 个 `@ts-ignore` / `as any`。
- commit：`99dc94a`（smoke.mjs + package.json）。
