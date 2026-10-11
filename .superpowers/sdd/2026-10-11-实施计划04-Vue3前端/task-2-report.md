# Plan 04 · Task 2 实现报告 —— 学生端 H5（6 个页面 + 1 个图表组件）

> **日期**：2026-10-11 · **分支**：`feature/plan-04-frontend`
> **基线**：`f586eef`（Task 1 交付完 + 计划更正入库）
> **本 Task 的 3 个 commit**：`6f480cb`（共享层）→ `9baf2ba`（6 个页面 + 路由接线）→ 本报告
> **结论**：**2 处 Critical 顶回 + 7 处其它顶回（合计 9 处）**；`npm run build` 退出码 **0**；
> 7 条 URL 的真实渲染取证 **81 条断言全绿**；3 个写端点的真 HTTP 取证 **全绿**。

---

## 1. 环境与演示库核实

### 1.1 工具链（与 Task 1 逐字相同）

| | 实测 |
|---|---|
| `node --version` | **v24.19.0** |
| `npm --version` | **11.17.0** |
| Vite | 8.3.4 |
| Vue | 3.5.43 |
| TypeScript | 5.9.3 |
| `vue-tsc` | 3.3.13 |
| Edge（无头取证用） | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |

### 1.2 开工时撞到的两件事

1. **Task 1 留了两个进程在跑**：`5173`（vite，pid 56520）与 `8000`（uvicorn，pid 54884）。
   5173 复用了；**8000 那个必须停掉** —— 它指的正是那个**旧演示库**
   （`pe_demo.db` 的 `LastWriteTime = 2026-10-10 16:43:13`，`notifications` 只有 1 条、
   `exercises` 与 `prescription-templates` 是空表）。停掉之后重跑
   `backend\scripts\demo.ps1 -Port 8000`（**用 `-Port 8000`**，因为 `vite.config.ts`
   的代理写死了 8000，而 demo.ps1 的缺省端口是 8010）。
   ⚠️ Vite 只绑在 **`::1`**（IPv6 localhost），故取证一律用 `http://localhost:5173`，
   用 `http://127.0.0.1:5173` 会「无法连接到远程服务器」。
2. **取证跑完又重灌了一次**：HTTP 取证会改演示库（+1 行 `training_log`、1 条通知变已读），
   故在 commit 之前重跑 `demo.ps1` 把它复原，再**按「DOM 取证先、HTTP 取证后」的顺序重跑一遍**，
   于是入库代码与取证结果一一对应。下面 1.3 的行数是**复原之后、取证之前**的口径。

### 1.3 演示库 25 张表的行数（`sqlite3` 只读连接直数，不是数源码）

派单第 3 节第 4 步要核的 **7 个表**：

| 表 | 期望 | 实测 | |
|---|---|---|---|
| `student` | 60 | **60** | ✓ |
| `notification` | 19 | **19** | ✓ |
| `prescription` | 60 | **60** | ✓ |
| `training_log` | 840 | **840** | ✓ |
| `rpe_record` | 240 | **240** | ✓ |
| `weekly_class_report` | 5 | **5** | ✓ |
| `alert` | 11 | **30** | ⚠️ 见顶回 4（**不是数据问题**：11 是其中 `level='red'` 的行数） |

其余 18 张（一并记下，Task 3/4 要用）：

```
alert 30            body_composition 240   class_session 8       cleaning_log 133
course_section 5    daily_sync_run 2       derived_metrics 120   enrollment 120
exercise 0          fitness_test_batch 4   fitness_test_result 240  interest_survey 120
mini_test 180       notification 19        percentile_snapshot 24   prescription 60
prescription_template 0   rpe_record 240   semester 2            stratification_result 120
student 60          teacher 3              training_log 840      weekly_adjustment 10
weekly_class_report 5                                             TABLES 25
```

`alert` 的 30 行实测分布（这一格解开了「11」的谜）：

```
by level : {'red': 11, 'green': 13, 'yellow': 6}
by status: {'pending': 30}          ← 全部未处置
by rule  : {'RED_RPE_SUSTAINED': 6, 'RED_MINITEST_DROP': 5,
            'GREEN_MASTERY': 13, 'YELLOW_CHECKIN_GAP': 6}
student_id 非空: 30 / 30            ← 全是学生级，没有班级级的行
```

⚠️ **13 绿 + 6 黄 = 19 = 通知条数**（`GREEN_MASTERY` → 电子勋章 13 条、
`YELLOW_CHECKIN_GAP` → 补练提醒 6 条），而两条 `RED_*` **刻意不自动推送**
（spec §8.2：教师点一次「减量」学生才收到）。故计划里那份清单是**自洽**的，
只是「11 条预警」数的是**红色**那一部分。

### 1.4 ⚠️ `exercise` 与 `prescription_template` 是 0 行 —— Task 1 的诊断要更正

Task 1 的待清扫第 1 条把这两张空表算作「旧库的症状」。**重灌之后它们仍然是 0 行**，
故那不是症状、是 `demo_bootstrap` 的**常态**：动作库与处方模板的**运行时所有者是 YAML**
（`app/refdata_prescription.py:282` 的 `exercises()` 是「进程内单例，只读参考数据，
一个进程加载一次」），DB 里那两张表只是镜像，`demo_bootstrap` 不灌它们。
**对 Task 4 的后果**：管理台的 23 个资源里，`exercises` 与 `prescription-templates`
两个的列表页**注定是空的**，而它们是**刻意只读**的那两个（spec §4.4）——
不要把这当成 bug 去修，也不要在验收里要求它们非空。

---

## 2. 6 个页面逐个（端点一律**实测**：`/openapi.json` 的 `security` + 活的响应体）

**公共口径**（6 个页面都一样，故只在这里说一次）：

- **身份**：`identity.studentId` 为 `null` 时一律渲染一块**带下一步**的空态
  （「请在身份切换器里选一个学生，或在 URL 上加 `?student=4`」），**不发请求**、不假装在加载。
- **`as_of`**：一律用 store 里的 `2025-10-12`（演示库的业务日 = 学期第 6 周的周日）。
- **业务日与周次是两件事**：`home.week = 6` 是**学期周**，`weekly_sheet.week = 1` 是
  **微周期周**。6 个页面里凡出现「第 N 周」都写明是哪一种（这一格最容易静默做错）。
- **换身份/换业务日会重读**（`watch([studentId, asOf], reload)`）：`as_of` 是查询参数，
  不是渲染期的过滤条件。
- **错误**：`ApiError` 默认送 `ApiErrorBanner` 的常驻位；**「不是错误」的那几档**
  （`no_active_prescription` / `outside_microcycle` / 小测的 401 / 打卡与快评的 409）
  在页面里就地接住、渲染成**内容**，不进红色横幅 —— 横幅会把「设计如此」讲成「出事了」。

---

### 2.1 首页 `/s/home`（`Home.vue`，476 行）

**端点（实测）**

| # | 方法与路径 | security | 用途 |
|---|---|---|---|
| 1 | `GET /api/students/{student_id}` | 匿名 | 姓名/学号/院系（深链接进来时 store 里没有 label） |
| 2 | `GET /api/students/{student_id}/home?as_of=` | **`X-Student-Id`** | 主数据，9 个键 |
| 3 | `GET /api/students/{student_id}/training-logs/completion-rate?semester_id=&week=` | **`X-Student-Id`** | 待办里的「训练日未计入」那一批 |

⚠️ ③ 必须排在 ② 之后（**不是并发**）：它的 `semester_id` / `week` 两个参数都是**必填**，
而它们的值只能从 ② 读出来（实测 `semester_id=2`、`week=6`）。

**响应里读了哪些字段**

- ② 的 9 个键：`student_id / as_of / semester_id / week / stratification / weekly_sheet /
  pending_rpe / unread_notifications / badges`。
  `stratification` 用了 `label / reason / explanation / hit_rules / percentile_source / computed_on`
  （**没有**读 `input_snapshot` —— 那是 27 个键的大对象，首页用不上，读了就是白传）；
  `badges` 用了 `count / latest`；`weekly_sheet` 用了 `week / factor / sessions[].day /
  sessions[].focus / sessions[].blocks[].{exercise_ref,weekly_volume,volume_unit}`。
- ③ 用了 `completion_rate / numerator / denominator / expected_days / completed_days /
  prescription_week / paused / reason`。

**四个区块**：`01` 计时牌（本周训练量 + 完成率）· `02` 待办 · `03` 我的分层 · `04` 消息与勋章。

**⚠️「本周训练量」不能是一个数（顶回 8）**

计划 Task 2 的表格写的是「本周训练量（**数字滚动**）」，读起来像一个大数字。实测不行：
`prescription_stage.py:411-417` 逐字交代「**刻意不加任何跨单位的周总量汇总字段**……
`volume_unit` 的实测值域是 `{min, reps, unspecified}` 且**同一周里三个并存**
（红层 `RED-END-ABN-01` + 体成分异常那一档就是），把它们相加就是 Plan 02 Task 5 的
F1-1 那个『混合量纲 float』错误 —— **48 分钟 + 120 次 = 168 什么？**」

故首页**按 `volume_unit` 分列**，每一种单位一个 `StatBlock`（`size="hero"`，数字滚动照做）。
演示库的学生 1 与学生 4 都只有 `min` 一种，故看起来是一个数；红层那一张处方会是两个。

另外两条实测口径：

- **`weekly_volume` 已经乘过 `factor`**：模板第 1 周是 `43.2`、训练单上是 `34.6`
  （= 43.2 × 0.8）。故前端**不再乘第二次**。
- **按 `exercise_ref` 去重**：同一个动作在 day 1/2/3 各出现一次，而 `weekly_volume` 是
  **每周**的量（三处都是 34.6）→ 不去重就会数三遍。
  实测学生 4：3 个动作 × 36.0 = **108.0 分钟**（系数 1.00）；
  学生 1：3 × 34.6 = **103.8 分钟**（系数 0.80），页面显示 `103.8`。
- **`volume_unit === 'unspecified'` 不进合计**：它的 `weekly_volume` 实测是 `0.0`
  （`demo_bootstrap` 的那批 warning 逐字说「需教师用 VOLUME_SCALE 覆盖」），
  而「没指定」不是「0 分钟」。故另起一行写「另有 N 个附加模块**未指定训练量**」。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| `weekly_sheet` 整个是 `null` | `.s-empty`「**本周还没有训练单**」+ 一句「后端把两档 404 都折成了 null，要分辨请打开训练单那一页」 |
| `weekly_sheet` 在、但所有 `volume_unit` 都是 `unspecified` | `.s-unknown`「**本周训练量未知**」——⚠️ 与上一格**是两块不同的 UI**（派单第 6 节逐字要求） |
| `completion_rate` 为 `null` | `StatBlock` 渲染「**—**」（组件里拦，不是页面里判）+ 一块 `.s-unknown` 原样带出后端的 `reason`（三档各不相同，`feedback.py:761-768`） |
| ③ 整个读不到（`ApiError`） | `.s-notice--warn` 显示 `code · status` + `message` 原文，**其余三个区块照常渲染**（后端 `home` 自己就是这个口径：`dashboard.py:522-526`「首页是一屏，一格缺数据不该让整屏失败」） |
| `stratification` 为 `null` | `.s-empty`「还没有分层结果」 |
| `badges.latest` 为 `null` | 「**—**」（`stampOf()` 只在非空时调用） |
| `semester_id` / `week` 为 `null` | `num()` → 「**—**」 |

**待办的口径（容易做错，故写明）**：`expected_days − completed_days`。
⚠️ 而后端的 `completed_days`（`feedback.py:810-817`）已经排除了**补卡**
（`submitted_at.date() != log_date`）、**迟交**（`late`）与**休息日打卡**三种 ——
故「库里有那一行」≠「计入完成率」。页面的措辞因此是
「**X 月 X 日的训练还没计入完成率**」而不是「你还没打卡」，并附一句口径说明。

---

### 2.2 本周训练单 `/s/weekly-sheet`（`WeeklySheet.vue`，500 行）

**端点（实测）**：`GET /api/students/{student_id}/weekly-sheet?as_of=` · **`X-Student-Id`** · 200。
（教师读同一份数据要走 `/api/teacher/students/{id}/weekly-sheet`，约束第 14 条 —— 那是 Task 3。）

**响应体 6 个键**（实测学生 1）：

```json
{"week": 1, "factor": 0.8, "reasons": ["RED_RPE_SUSTAINED"], "sources": ["auto"],
 "paused": false, "sessions": [{"day": 1, "focus": "速度柔韧", "blocks": [ …4 个… ]}, …day 2, day 3…]}
```

`blocks[j]` 是 `AssembledBlockRead` 的 10 个键：
`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone /
structure / weekly_volume / volume_unit / sessions_per_week`。

**⚠️ 约束第 13 条那一句话是怎么落地的**

`factorSentence` 按 `sources[i]` **分别数**，而不是一律说「红色预警」
（`weekly.py:365-384` 逐字：`sources` 可以是 `("teacher","auto")`，两者并存时仍然相乘）：

```
reasons.length === 0 或 |1 − factor| 取整为 0  → 「本周不调整（系数 1.00）」
factor < 1                                     → 「本周减量 {round((1−factor)×100)}%（由 {auto} 条红色预警触发 + {teacher} 条教师手工调整）」
factor > 1                                     → 「本周加量 …%（由 …）」
```

`reasons = ["RED_RPE_SUSTAINED","RED_MINITEST_DROP"]` + `sources = ["auto","auto"]` + `factor = 0.8`
→ 逐字得到派单要的那一句：**「本周减量 20%（由 2 条红色预警触发）」**。

并且下面**永远**跟着一段解释（不是只在两条时才出现）：
「⚠️ 为什么两条红色预警只减了 20%？用户裁定：『一处方一周至多减一次』。`factor` 是这一周
全部调整的**累乘**，而 `source='auto'` 那一档在写入侧就有『已有一行就不再写』的闸门
（`alert_stage._auto_adjustment_exists`）—— 否则两条红色规则会把这一周乘成 0.8 × 0.8 = 0.64。
故教师端的预警队列里看得见**两行红色**，而这里只有**一个减量**：这不是 bug，是裁定。」

⚠️ **演示库上这一档造不出来**：`weekly_adjustment` 只有 10 行，每行一个不同的
`prescription_id`、`week` 全是 1、`source` 全是 `auto`、`factor` 全是 0.8 ——
即**一处方一周恰好一条**，故 `reasons` 实测长度恒为 1。两条那一档只在
`("teacher","auto")` 并存时可达，而 `"teacher"` **今天没有生产写入方**
（`weekly.py:381-384` 逐字交代，只在测试里可达）。代码按 N 条写，不按 1 条写。

**其它区块**：`02` 一周七日（**7 格恒在**，训练日墨底、休息日纸底、业务日压一条砖红粗线）；
`03…N` 每个训练日一块（`LaneDivider` 的道次编号从 `03` 起递增，`--lane-index` 同步递增，
于是 staggered reveal 是连续的）。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| 整个端点 404 `no_active_prescription` | `.s-unknown`「**这一天没有生效的处方**」+ `code · status` + `message` 原文 + 「等下一次批处理」 |
| 整个端点 404 `outside_microcycle` | `.s-unknown`「**这一天不在处方的微周期里**」+ 原文 + 「该换处方了」——⚠️ 与上一格**是两句不同的话**（`ApiErrorBanner` 也是这个分档） |
| `block.hr_zone` 为 `null`（演示库里**全是** null） | 「**—**」 |
| `block.volume_unit === 'unspecified'` | 「**未指定**」+ 一句「附加模块要教师用 VOLUME_SCALE 定量」，**不显示 `0.0`** |
| `block.structure` 是空对象（附加模块实测就是 `{}`） | 「模板未给组次结构」（`structure` 的类型是 `{[key:string]: unknown}`，故三个键都做了 `typeof === 'number'` 的窄化） |
| `sessions[i].blocks` 是空数组 | `.s-empty`「这一天没有安排动作」 |
| `sources[i]` 越界（`reasons` 与 `sources` 长度不等） | `sourceZh(UNKNOWN)` → 「—」 |
| `paused === true` | 一块 `.s-notice--warn`，并**照原样列出训练日**（后端 `weekly_sheet_payload` 逐字：「暂停」与「本周量为 0」是两件不同的事，清空 `sessions` 会让两者在学生端长得一模一样） |

---

### 2.3 每日打卡 `/s/check-in`（`CheckIn.vue`，674 行）

**端点（实测）**

| # | 方法与路径 | security |
|---|---|---|
| 1 | `GET /api/students/{id}/home?as_of=` | **学生头**（只为拿 `semester_id` / `week`） |
| 2 | `GET /api/students/{id}/training-logs/completion-rate?semester_id=&week=` | **学生头** |
| 3 | `GET /api/students/{id}/weekly-sheet?as_of=` | **学生头**（选中那天练什么） |
| 4 | `GET /api/training-logs?limit=…&offset=…` | 匿名 · **翻页收集 + 客户端按 `student_id` 过滤** |
| 5 | `POST /api/training-logs` | **学生头** · 201 |

⚠️ ④ 为什么要翻页：演示库 `training_log` 是 **840 行**，而 `limit` 的上界是 **200**
→ 5 页。`endpoints.ts` 新加的 `collectPages()` 带一个 **`cap = 1200`** 的硬上界
（没有上界的收集循环在「`total` 与实际行数不符」时会转 forever），撞到上界就把
`truncated = true` 如实交给页面显示。

**⚠️⚠️ 请求体只有 5 个键（派单逐字要求的那一格）**

`CheckIn.vue` 的 `submit()` 逐字构造：

```json
{"log_date": "2025-10-13", "completed": true, "duration_min": 35.0,
 "feeling": "moderate", "is_rest_day": false}
```

**`submitted_at` / `late` / `student_id` / `source` / `batch_id` 一个都不传。**
理由不是「传了会被忽略」这么轻：`late` 的判定式是 `submitted_at.time() > CHECKIN_DEADLINE`
（22:00，`feedback.py:674-676`），而完成率是 **RCT 的关键过程指标** ——
让前端能传 `late` 就等于让前端能伪造完成率。

真 HTTP 取证的响应（第 4 节 A1）证实四个都是服务端填的：
`submitted_at = "2026-10-11T17:02:32.739765"`（真实的今天，不是 `log_date`）、
`late = false`（17:02 < 22:00）、`source = "checkin"`、`batch_id = null`。

**`feeling` 的值域**：`easy` / `moderate` / `hard`（`TrainingLog.FEELINGS`，DB 上有 CHECK）。
中文标签「轻松 / 适中 / 吃力」由前端映射 —— 所有者是 `present.ts` 的 `FEELINGS`
（`feedback.py:397-400` 逐字「存英文 token，**中文标签由前端映射**」）。
三个大按钮，每个带一句人话（「做完还能再聊两句」/「有点喘，但撑得住」/「最后几下是咬着牙的」）。

**盖章动效**：`StampFeedback` `tone="moss"`、`text="已打卡"`，
`caption` = `{log_date} · {按时|迟交（22:00 后）} · 服务端记于 {submitted_at}`。
⚠️ 只在 **201** 之后出现（计划第 2 节：它是三个动效里最贵的一个，只用在「一次真的写进了库」的时刻）。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| `completion_rate` 为 `null` | `StatBlock`「**—**」+ `.s-unknown`「完成率没有定义（**不是 0%**）」+ 后端那句 `reason` 原文 |
| `prescription_week` / `prescription_id` 为 `null` | `num()` → 「—」 |
| `duration_min` 为 `null` | 历史表里「**—**」（`num(row.duration_min, 1)`） |
| `feeling` 为 `null` | 「**—**」（`feelingZh()` 对空值返回 `UNKNOWN`；认不出的 token **原样带出**，不猜） |
| `batch_id` 为 `null`（学生交的**恒为** null） | 「**—**（不属于任何批次）」+ 一句为什么（`feedback.py:683-684`：NULL 让它天然躲过「重放那天先删后算」） |
| `rate` 整个读不到 | `.s-notice--warn` 显示 code + message，表单**照常可用** |
| `weekly_sheet` 整个读不到（两档 404） | 表单的副标题变成「这一天不在本周训练单上」，`expected_days` 空 → 休息日自动勾上 |

**空态 vs null**：历史表为空时那块 `.s-empty` 逐字写了
「⚠️ 这一格与『完成率未知』是两件事：这里说的是 `training_log` 表里**一行都没有**，
上面那格说的是有行、但完成率没有定义。」

**409 的人话**：「这一天（{date}）你已经打过卡了：一天只能有一行，后端刻意不做
『补卡覆盖旧行』—— 那样会让『他当时交的是什么』在库里查不到。」
⚠️ 并且在**提交之前**就挡：`alreadyLogged` 由 ④ 的结果算出来，选中已打卡的日期时
先显示一块 `.s-notice--warn`，而不是让用户点了才吃 409。

---

### 2.4 课堂快评 `/s/rpe`（`RpeEntry.vue`，617 行）

**端点（实测）**

| # | 方法与路径 | security |
|---|---|---|
| 1 | `GET /api/students/{id}/home?as_of=` | **学生头**（`pending_rpe`） |
| 2 | `GET /api/class-sessions?limit=200` | 匿名（课次下拉） |
| 3 | `GET /api/rpe-records`（翻页收集 + 客户端过滤） | 匿名（我已交过哪些 + 趋势图） |
| 4 | `POST /api/rpe-records` | **学生头** · 201 |

**⚠️ 口令必须手输（约束第 15 条）—— 三个入口都拿不到，逐一实测过**

| 入口 | 实测 |
|---|---|
| `GET /api/class-sessions/{id}` / 泛型 list | 键集合 = `batch_id,course_section_id,id,period,rpe_opened,session_date` —— **不含 `rpe_token`** |
| `GET /api/class-sessions/{id}/rpe-token` 匿名 | **401** `unauthenticated`「缺少身份请求头 X-Teacher-Staff-No」 |
| 同上，**学生头** | **401**（⚠️ 不是 403：这一格缺的是**教师头**，`X-Student-Id` 在不在场都不影响 `current_teacher` 的判定） |
| 同上，教师头 | 200，与 `open-rpe` 回的那一串**逐字相同** |

故页面上那个输入框旁边**永远**有一段解释：「学生端**拿不到**口令……这不是缺功能 ——
口令的用途就是挡住『猜一个 `class_session_id` 乱交』（spec §4.5）。」
`input` 加了 `letter-spacing: 0.22em` + `text-transform: uppercase`，因为实测口令是
`iZl1C0sFNF804_UZ` / `fKeYwsgsQO19LKZ-` 这种 16 字符的串，**0/O、1/l 要能分辨**。

**⚠️ RPE 的 11 个大按钮：375px 下的实际布局（顶回 6 的答案）**

**结论：好用，但要 4×3 而不是 11 连排。**

```
内容宽 = 375 − 16×2（出血内边距）= 343px
grid-template-columns: repeat(4, 1fr); gap: 8px
→ 每格 ≈ (343 − 3×8) / 4 ≈ 79.75px 宽 × min-height 74px 高     ← 两个方向都过 44px 触控下限
→ 3 行 = 11 个按钮 + 1 格图例（第 12 格填掉 4×3 的缺口，不留空洞）
→ 总高 ≈ 3×74 + 2×8 = 238px
```

每格是「**28px 的 Barlow Condensed 800 数字** + 10px 的四字中文锚点」。
选中的那一格翻成墨底纸字 + `2px 2px 0 var(--track)` 的硬阴影（与 `.btn:active` 同一套语言）。
语义色**只出现在下沿那一条 3px 的内阴影**上（7–8 琥珀、9–10 砖红）——
与 `lane.css` 的 `.lane--red` 同一条口径：「只换细线的颜色，母题的形状不能被语义色改掉」。

⚠️ **不用横向滚动的 11 连排**：11 × 44px = 484px > 343px，必然要滚，
而「滚出视野的按钮等于不存在」——`10 = 力竭` 恰恰是最该被看见的那一个
（它触发 `RED_RPE_SUSTAINED`）。⚠️ 也**不用滑块**：滑块在 11 个离散档上
既难点准（一档 ≈ 31px）、又没法在拇指下面显示文字。

按钮组下面是一块**计时牌读数**（`readout`）：56px 的数字 + 中文锚点 + Borg 英文原文，
未选时显示 `?` / 「还没选」/ `PICK ONE`。

**11 档的文字用的是哪一套（派单要问的那一格）**

**Borg CR-10 的标准语言锚点的中文对译，不是自己编的一套。**
⚠️ 先更正派单的措辞：本仓的 RPE 是 **0–10**，而 0–10 恰好就是 **Borg 的 CR-10 标度**；
「Borg 量表」通常被人想到的那张 **6–20** 是 1970 年的原始 RPE 表，
后端在**四处**逐字钉住了「**不是** 6–20」（`assembler.py:235-238` 与 `:464-467`，
出处是 spec 的四处原文）。故 11 档 = CR-10 的 11 个整数档，逐条对译：

| RPE | 中文（`present.ts` 的 `RPE_SCALE`） | Borg CR-10 原文 | 染色 |
|---|---|---|---|
| 0 | 毫无感觉 | Nothing at all | — |
| 1 | 极其轻松 | Extremely weak | — |
| 2 | 非常轻松 | Very weak | — |
| 3 | 比较轻松 | Weak | — |
| 4 | 略微轻松 | Somewhat weak | — |
| 5 | 适中 | Moderate | — |
| 6 | 略微吃力 | Somewhat strong | — |
| 7 | 比较吃力 | Strong | 琥珀 |
| 8 | 非常吃力 | Very strong | 琥珀 |
| 9 | 极其吃力 | Extremely strong | 砖红 |
| 10 | 力竭极限 | Maximal | 砖红 |

⚠️ **7/8 与 9/10 的染色不是我挑的**，取自后端两条规则的阈值：
`YELLOW_CLASS_RPE_HIGH` =「课堂 RPE 均值 > **7** 分」、`RED_RPE_SUSTAINED` =「RPE 连续 ≥ **9** 分」。
第 12 格（图例）逐字写着「7–8 班均 > 7 触发」「9–10 连续三次触发减量」——
于是学生按下的那个按钮与教师在预警队列里看到的那一条**同一套阈值**。

**三个错误码各一句人话**（`ADVICE` 表，按 `code` 分支，不按 `message`）

| code | 页面上那一句 |
|---|---|
| `invalid_rpe_token`(403) | 「口令不对。请照着老师投屏上的那一串**重新手输**（注意 0 与 O、1 与 l）—— 学生端读不到口令，这是设计：口令的存在就是为了挡住『猜一个 class_session_id 乱交』。」 |
| `rpe_not_opened`(409) | 「老师还没有发起这节课的快评。等老师在教师端点『发起课堂快评』并把口令投屏之后再交（口令为空与 rpe_opened 为假是同一档，后端刻意不区分）。」 |
| `integrity_conflict`(409) | 「你这一节课已经交过了。一节课一个学生只能交一次（DB 上有唯一约束）—— 少了它，连点两次『提交』会让教师端的『课堂 RPE 均值』把你算两遍、已提交名单显示 101%。」 |

⚠️ 三档**一律不送红色横幅**：它们每一档用户要做的下一步都不同，是**页面内容**。
另外还给了 `not_found` / `unauthenticated` / `forbidden` 三档，未知 code 落到 `message` 原文。

**`elapsed_seconds` 是前端量的**：`RpeSubmitCreate.elapsed_seconds`（`number|null`，min 0）
是「提交耗时秒」，而 `submit_rpe` **不填它**（它只填 `student_id` 与 `submitted_at`）——
「学生从看到题到按下提交花了多久」是**只有前端知道**的量。
计时从「课次与口令都就位」那一刻起（不是从组件挂载：挂载到看清投屏口令之间那几秒不是作答时间），
每 200ms 刷新一次，显示在区块右上角「用时 N.N 秒」，提交时 round 到 0.1 秒。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| `pending_rpe` 是空数组（**演示库上恒为空**：8 节课 × 30 人 = 240 条，全交满了） | `.s-empty`「本周没有还没交的快评」+ 后端的判据原文（`dashboard.py:450-487`：本周内、我选课的班、`rpe_opened`、我没交过）+「三周前没交的仍可补交，后端刻意不做过期」+「要交某一节请在下面自己挑课次」 |
| `rpe_record.elapsed_seconds` 为 `null` | 「—」 |
| 选中的课次不在 list 里 | 下拉项退化成「课次 {id}」 |
| 趋势图一个点都没有 | `RpeTrend` 的空态（**不画坐标系**，见第 3 节） |

---

### 2.5 二次小测 `/s/mini-test`（`MiniTest.vue`，528 行）

**端点（实测）**

| # | 方法与路径 | security | 学生身份下 |
|---|---|---|---|
| 1 | `GET /api/students/{id}/home?as_of=` | **学生头** | 200 |
| 2 | `GET /api/mini-tests?limit=200` | 匿名 | 200（180 行，客户端过滤出我的 3 行） |
| 3 | `GET /api/mini-tests/normalized?semester_id=&week=` | ⚠️**教师头** | **401** |

**⚠️⚠️ 顶回 2（Critical）就在这里**，详见第 6 节。降级后的页面：

- **区块 01「我的 3 次小测」永远有数据**（走匿名的 ②）：周次 / 测于 / 深蹲 30s / 折返 20m / 标准化分。
  实测学生 1 的三行是第 2/4/6 周（`normalized_score` = 21.75 / 20.90 / 14.50）。
  一个「看哪一次」的切换器（第 2/4/6 周）驱动区块 01 的高亮与区块 03 的原始成绩。
- **区块 02「班内百分位」**：401 时渲染一块 `.s-notice`，写清 code、`X-Teacher-Staff-No`、
  `feedback.py` 的那行形参、以及「换成教师身份（`T0001`/`T0002`/`T0003`，或 URL 上加
  `?teacher=T0001`）就能看到」，并**明说本页不会在前端重算百分位**
  （算式只有一个住址 `app/domain/report.py`，后端有 AST 守卫
  `test_the_mini_test_normalization_has_exactly_one_definition` 数定义份数 == 1）。
- **区块 02 的成功支路已实现且已核过输入形状**（真 HTTP 取证 D3）：
  200 时按班分组渲染，每个班一块。⚠️ **今天它渲染不出来**（`client.ts` 一次只注入一个头，
  故「有 studentId」与「能读 normalized」互斥），代码里逐字写了这件事与保留它的三条理由；
  控制者一旦改后端，**本页一行都不用改**就会亮起来。

**⚠️ `scored_count == 1` → 「无排名」（约束第 11 条）**

后端 `shuttle_percentile` 的算式（`app/domain/report.py:599-639`）：

```
PR = (比自己慢的人数 + 0.5 × 与自己并列的人数) / 样本数 × 100
```

`n = 1` 时它给 **50.0**，而那个函数的注释逐字承认「单人班给 50.0 在真实数据下
**看起来像真排过名**……本函数**刻意不改**：什么时候不该显示一个数是**展示层**的口径」。
故 `MiniTest.vue` 里 `v-if="row.section.scored_count === 1"` 渲染一块 `.s-unknown`
「**无排名**」，并把 50.0 的来历写出来（`(0 + 0.5 × 1) / 1 × 100 = 50.0`）。

⚠️ **演示库上这一档造不出来**：5 个班的 `scored_count` 实测是 **30 / 30 / 20 / 20 / 20**
（真 HTTP 取证 D3 的原文），最小的是 20。要有 `scored_count == 1`，得有一个班只有一个人测了折返。
代码仍然实现了它，并对拍过后端的算式。

**「比自己慢的人数」怎么来的（不是重算百分位）**

= 同一个班里 `shuttle_score` **严格小于**我的人数。
理由：折返跑秒数越少越好，故「比我慢」⟺「百分位比我低」；而并列的人百分位**相同**
（中点口径），于是「严格小于」恰好就是后端算式里那个「比自己慢的人数」。
同理「与你并列」= `shuttle_score === 我` 的人数、「班内名次」= `1 + 比我高的人数`。
⚠️ 分母用的是**同班里 `shuttle_score` 非空的行数**（不是 `scored_count`）——
后端逐字交代「`shuttle_20m_s IS NULL` 的行不进百分位样本」。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| `mini_test.squat_30s_count` / `shuttle_20m_s` / `normalized_score` 为 `null` | `num()` → 「**—**」，并在表下写明「一个没测的人若被当成『最差的那个』，会把全班的百分位一起往下拽」 |
| `entries[].composite` / `shuttle_score` / `squat_score` 为 `null` | `StatBlock`「**—**」；「比你慢的人数」→「**—**（你这次没测折返）」 |
| 我在 `unassigned` 里 | `.s-unknown`「你不在任何教学班里 → 班内百分位**无定义**」+ 后端三种候选处置的原文（只有「点名报出来」不撒谎） |
| 那一周没有我的行 | `.s-empty`「第 N 周没有你的小测行」+「上面第 01 块列出的是你**全部**三次成绩」 |
| `home.semester_id` / `week` 为 `null` | 不调 ③，`num()` → 「—」 |
| `item_combo` | 恒显示「**—**」+ 一句「泛型 list 把这一列排掉了，要它得读单条」（`mini-tests` 是 8 个「list 比 `*Read` 少列」的资源之一，排 1 列） |

---

### 2.6 消息中心 `/s/notifications`（`Notifications.vue`，334 行）

**⚠️⚠️ 端点路径是实测的（顶回 1，Critical）**

计划猜的 `GET /api/students/{id}/notifications` **不存在**。实测 `/openapi.json` 里
含 `notification` 的路径**只有三条**：

```
GET  /api/notifications                        security = null（匿名）   opId=list_rows_api_notifications_get
GET  /api/notifications/{notification_id}      security = null（匿名）   opId=read_one_api_notifications__notification_id_get
POST /api/notifications/{notification_id}/read security = [{"X-Student-Id": []}]  opId=mark_notification_read_…
```

**本页用的两个**：

| # | 方法与路径 | security |
|---|---|---|
| 1 | `GET /api/notifications?limit=…&offset=…` | 匿名 · **翻页收集 + 客户端过滤** `recipient_kind === 'student' && recipient_id === 我` |
| 2 | `POST /api/notifications/{notification_id}/read` | **学生头** · 200 |

**演示库的 19 条实测形状**（一人一条，发给 19 个**不同**的学生）：

```
recipient_kind : {'student'}        channel : {'in_app'}       is_read=true : 0 / 19
title          : {'本周电子勋章': 13, '补练提醒': 6}
recipient_id   : 4,5,6,10,11,15,17,25,26,35,38,40,43,47,48,53,54,56,60   ← 各 1 条
created_at     : 全部 2025-10-12T00:00:00
```

⚠️ **故任何一个学生最多只能看到 1 条**（顶回 5：派单第 8 节第 4 条要的
「消息中心有 19 条通知」与正确行为**冲突**）。本页按**正确**的那一边做，
并在空态里把这件事讲清楚：「演示库里一共有 19 条，而它们是**一人一条**发给了 19 个不同的学生
（4、5、6、10、11、15、17、25、26、35、38、40、43、47、48、53、54、56、60）。换一个身份就能看到那一条。」

**`is_read` 的视觉区分（三件一起变）**

| | 未读 | 已读 |
|---|---|---|
| 左端色带 | `--lane-thick`(3px) `--track` | 3px `--moss-on-paper` |
| 底色 | `--paper-raised` + `--shadow-paper` | `--paper-sunken`（凹下去） |
| 标题/正文 | `--fw-zh-title-900` / `--ink-soft` | 降到 `--fw-body-400` / `--ink-faint` |
| 徽章 | `.pill--red`「未读」 | 描边 pill「已读」 |
| 按钮 | `.btn--primary`「标为已读」 | 一行 `.caps`「已读过」（**按钮不出现**，不是禁用） |

⚠️ **只变一件的话，在投影或色弱的情况下就读不出来** —— 故四件一起变。

**`not_recipient`(403) 这一档**（派单点名要处理）：那一行下面就地渲染一块
`.s-notice--warn`，写「这条消息不是发给你的（或者它根本不存在 —— 后端刻意让这两档同形：
`notification.id` 是连续的代理键，区分两者等于让『扫一遍 id』成为一次有效的探测）」。
真 HTTP 取证 C1 拿到了这一档的原文（学生 4 去读 id=2，那是学生 5 的）。

**页面上还写了一段「这一页读的是哪个端点」**（区块 `01`）：把顶回 1 如实摆给用户看 ——
计划猜的端点不存在、只能客户端过滤、这挡住了「页面显示别人的消息」但**挡不住**
「任何调用方匿名 GET 一次就读到全部 19 条」，以及后端其实已经会按学生过滤
（`dashboard.py:489-497` 的 `unread_notifications`）。
区块 `03` 是**对拍**：本页客户端数出来的未读数 vs `/home` 服务端数出来的那一个，
并写明「不等就说明客户端过滤的判据与后端不是同一套」。

**可能是 `null` 的字段 → 显示成了什么**

| 字段 | 显示 |
|---|---|
| `alert_id` 为 `null` | 「**—**」 |
| `prescription_id` 为 `null`（演示库 19 条**全是** null） | 「**—**」 |
| 列表为空 | `.s-empty`（上面那段解释），**不是**一行灰字 |

---

## 3. `RpeTrend.vue` 的数据形状与 SVG 实现要点（328 行）

### 3.1 数据形状

```ts
export interface RpePoint {
  rpe: number      // 0–10 的整数（RpeRecordRead.rpe）
  label: string    // 横轴第一行，本仓给的是课次日期的 MM-DD
  sub?: string     // 横轴第二行，本仓给的是「第 N 节」
}
interface Props { points: readonly RpePoint[]; caption?: string }
```

⚠️ **`rpe` 不允许 `null`**：「没交」的课次要在**调用方**就剔掉。把 `null` 折成 0 画上去
就是约束第 10 条那一档，而 0 在这套量表上是「毫无感觉」—— 一次真实的、有意义的作答。

⚠️ **本组件不发请求**（数据由页面给），于是「读哪个端点」只有一个住址：
`RpeEntry.vue` 用 `listMyRpeRecords(id)`（`GET /api/rpe-records` 翻页收集 + 按 `student_id` 过滤），
按 `submitted_at` 升序，再用 `GET /api/class-sessions` 的表 join 出横轴文字。

⚠️ **`RpePoint` 住在一个普通 `<script lang="ts">` 块里**，不在 `<script setup>` 里 ——
`<script setup>` 不能有 ES module 导出（编译器当场报
“`<script setup>` cannot contain ES module exports”）。
`ApiErrorBanner.vue` 导出 `useApiError` 用的是同一个办法（两个 script 块会被合并成同一个模块）。

### 3.2 SVG 实现要点

| 要点 | 做法 | 为什么 |
|---|---|---|
| 画布 | 固定 `viewBox="0 0 320 168"` + `width:100%; height:auto` | 等比缩放 → 文字不变形。320 是 343px 内容宽留一点余量 |
| 底色 | `--paper-sunken` 的一块 `rect` | 计时牌的「凹槽」 |
| 网格 | `0 / 5 / 10` 三条 `stroke-width: var(--lane-thick)`、`stroke-opacity: .16` | **分道线母题在图表尺度上的复用**，于是这张图与页面其余部分看起来是同一个系统 |
| 红色带 | `yOf(10)` 到 `yOf(9)` 的一块 `--red-wash` + 右上角一行「≥9 连续三次 → 减量」 | 出处是 `RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」（`alerts.py:180-181`）—— 学生看得见自己离那条线有多近，这是本页存在的理由 |
| 阈值虚线 | `yOf(7)` 一条 `stroke-dasharray: 4 3` 的 `--amber-on-paper` + 「班均阈值 7」 | 出处是 `YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」。⚠️ 措辞刻意是「**班均**阈值」而不是「你的上限」——它是班级作用域的规则 |
| 折线 | `<polyline pathLength="100">` + `stroke-dasharray:100; stroke-dashoffset:100→0`，`animation: rpe-draw var(--dur-lane) var(--ease-lane)` | ⚠️ `pathLength="100"` 让 dash 长度与实际像素无关，于是**不用去算折线有多长**（点一动就要重算）。它是计划第 2 节动效①（「从左到右划出」）在折线上的同一母题，**不是第四种动效** |
| 点 | `r=4`、fill `--paper-raised`、stroke `--ink` 2px；`rpe ≥ 9` 的那几个换成 `--red-on-paper` + `--red-wash` | 与红色带同一套阈值 |
| 数字 | 点上方 8px，Barlow Condensed 800 / 13px / `tabular-nums`；⚠️ `rpe ≥ 9.4` 时翻到点**下方** 14px | 不翻的话 `10` 那个数字会被画布上沿裁掉 |
| 色值 | **一个都不写死**：SVG 的 `fill`/`stroke` 一律写在 `<style scoped>` 里而不是 presentation attribute 上 | `var()` 在属性里今天三个引擎都吃，但在 CSS 里是**规范保证**的 |
| 单点 | `points.length === 1` 时**不画折线**，只画一个点 + 一行「只有一次记录 —— 一个点画不出趋势，先交下一次快评」 | 一个点画不出线；硬画成「一条水平线」会被读成「一直很稳定」 |
| 空态 | **完全不画 SVG**：一段文字 + 一个「一条没画完的分道线」的小 mark | ⚠️ 一张空的坐标系会被读成「我一直是 0 分」，而 0 分是「毫无感觉」—— 一次真实作答 |
| 可访问性 | `role="img"` + `aria-label`（「共 N 次，最近一次 X 分，均值 Y 分（满标 10 分）」）+ `<title>`/`<desc>` | 一张图对读屏的人要能讲成一句话 |
| 减少动效 | 不需要自己写：`base.css` 的 `@media (prefers-reduced-motion: reduce)` 把所有 `animation-duration` 压到 0.01ms | 单一所有者 |

---

## 4. 真实渲染取证

### 4.1 取证口径（⚠️ 三条，第三条是踩出来的）

1. **无头浏览器**：Edge `--headless=new --dump-dom`。
   ⚠️ 必须用 `Start-Process -RedirectStandardOutput`（或 python 的 `subprocess.call(stdout=f)`）；
   PowerShell 的 `& msedge … > file` 会得到一个 **0 字节**的文件（GUI 子系统的 stdout 不走那条管道）。
2. **身份走 URL 深链接**：`?student=4&as_of=2025-10-12`。
   ⚠️ `--dump-dom` **不能交互**，也就点不了 `IdentitySwitcher`；而 6 个页面里有 5 个要学生头。
   故落在 `stores/identity.ts` 的 `adoptFromUrl()`（**一处**，不是派单建议的「6 个页面组件里各开一个调试入口」），
   由 `main.ts` 在**挂载之前**调一次（页面组件的 `onMounted` 里就要发请求，晚一步第一屏就是 401）。
   ⚠️ 它**不是调试后门**、主张**保留**：本仓没有登录页（非目标第 1 条），
   而「切换器」只能被人点 —— 一条被推送出去的链接（学校推送、教师投屏上的二维码）
   落地时没有人去点它。详见顶回 7。
3. **⚠️ 必须加 `--force-prefers-reduced-motion`**（这一条是踩出来的）：
   不加它，`--dump-dom` 抓到的是 `StatBlock` **数字滚动中途**的那一帧 ——
   实测首页的完成率显示 **95.7** 而不是 **100.0**、训练量显示 **103.4** 而不是 **108.0**
   （`1 − (1 − t)^5 = 0.957` → t ≈ 0.47，正是 900ms 滚动跑到一半）。
   **那不是 bug，是取证姿势。** 加上它走的是 `prefersReducedMotion()` 那一支（直接落到目标值），
   顺带把 reduced-motion 的降级路径也验了。
4. 其余旗标：`--virtual-time-budget=20000`（让 fetch 与 Vue 挂载在 dump 之前跑完）、
   `--window-size=375,1400`、`--run-all-compositor-stages-before-draw`、
   每条 URL 一个**独立的** `--user-data-dir`（`localStorage` 不串味）。
   ⚠️ Vite 只绑 `::1`，故 base 是 `http://localhost:5173`。

### 4.2 7 条 URL 与各自断言到的 DOM 关键内容 —— **81 条断言，0 处缺失**

| # | URL（`http://localhost:5173` + 下面这一段） | DOM 字节 | 断言 | 结果 |
|---|---|---|---|---|
| 1 | `/s/home?student=4&as_of=2025-10-12` | 103 937 | 14 | ✓ |
| 2 | `/s/home?student=1&as_of=2025-10-12` | 104 353 | 8 | ✓ |
| 3 | `/s/weekly-sheet?student=4&as_of=2025-10-12` | 110 787 | 11 | ✓ |
| 4 | `/s/check-in?student=4&as_of=2025-10-12` | 110 941 | 14 | ✓ |
| 5 | `/s/rpe?student=4&as_of=2025-10-12` | 110 086 | 13 | ✓ |
| 6 | `/s/mini-test?student=4&as_of=2025-10-12` | 104 214 | 11 | ✓ |
| 7 | `/s/notifications?student=4&as_of=2025-10-12` | 102 346 | 10 | ✓ |

⚠️ **为什么主页跑两次**：学生 4 的待办恰好是空的（3 个训练日全计入了完成率、
`pending_rpe` 也是空），故另跑学生 1（完成率 1/3、有 2 个训练日没计入）来证**待办列表非空**。
两个身份合起来才把首页的两条支路都走到。

**逐条断言到的关键内容**（原文，`missing` 全是空数组）：

1. **首页 · 学生 4**：`赵锦程 的本周` / `WEEK 6 · 2025-10-12 · 周日` / `VOLUME / RATE` /
   `本周训练量 · 分钟` / **`108.0`** / `3 个动作 · 已含本周系数 1.00` / `本周打卡完成率` /
   **`100.0`** / `3 / 3 个处方训练日` / `黄色层` / `命中的决策表行` / `R1 · R2 · Y1 · Y2 · Y3` /
   `未读消息` / `电子勋章`
2. **首页 · 学生 1**：`周晨阳 的本周` / `本周训练量 · 分钟` / `已含本周系数 0.80` /
   **`33.3`**（= 0.3333 × 100）/ `1 / 3 个处方训练日` / **`的训练还没计入完成率`** /
   **`去打卡`** / `微周期第 1 周 · 训练日`
3. **本周训练单**：`本周训练单` / `WEEKLY SHEET · 2025-10-12 · 周日` /
   `骨架第 1 周 × 本周调整系数` / `这一周的七天` / `训练日` / `休息日` / `SEVEN DAYS` /
   `每周量` / `心率区间` / `组次` / `动作代号`
4. **每日打卡**：`每日打卡` / `DAILY LOG` / `本周打卡完成率` / `交一次卡` /
   `训练日 log_date` / `今天练了吗 completed` / `自评感受 feeling` / `轻松` / `适中` / `吃力` /
   **`只会发出 5 个键`** / **`log_date / completed / duration_min / feeling / is_rest_day`** /
   `我的打卡记录` / `提交打卡`
5. **课堂快评**：`课堂快评` / `CLASS RPE · 0–10` / `还没交的课堂快评` /
   `本周没有还没交的快评` / `课堂口令 rpe_token` / **`只能手输`** / **`毫无感觉`**（RPE 0）/
   **`力竭极限`**（RPE 10）/ **`极其吃力`**（RPE 9）/ `适中`（RPE 5）/
   **`9–10 连续三次触发减量`**（第 12 格图例）/ `我的课堂 RPE 趋势` / `提交快评`
6. **二次小测**：`二次小测` / `MINI TEST` / **`我的 3 次小测`** / `深蹲 30s` / `折返 20m` /
   `标准化分` / `班内百分位` / **`unauthenticated`** / **`这一格学生身份读不到`** /
   **`X-Teacher-Staff-No`** / `不会`（「本页**不会**在前端重算一遍百分位」）
7. **消息中心**：`消息中心` / `INBOX · IN_APP` / **`这一页读的是哪个端点`** / **`不存在`** /
   `recipient_kind` / `站内消息` / **`本周电子勋章`** / `未读` / **`标为已读`** / `站内消息`

⚠️ 断言的是**内容**而不是「不白屏」：每一条都对应一个「静默做错」的失效形态
（数字滚动没落定、单位没分列、系数乘了两次、口令框被做成自动填、401 被吞成空白、
客户端过滤没生效于是显示别人的消息……）。

### 4.3 从 DOM 里抄出来的关键数值原文（⚠️ 这一节是「不是只断言不白屏」的证据）

```
首页 · 学生 4
  VOLUME / RATE  本周训练量 · 分钟  108.0 分钟  3 个动作 · 已含本周系数 1.00
                 本周打卡完成率  100.0 %  3 / 3 个处方训练日
  LAYER          黄色层 · 判定理由「短板 ≥2 项且体成分未判为异常」· 命中 R1 · R2 · Y1 · Y2 · Y3
                 百分位口径 national · 算于 2025-10-12
  INBOX / BADGE  未读消息 1 条 · 电子勋章 1 枚 · 最近一枚勋章 2025-10-12 00:00
  TO DO          0 项 →「这一周没有待办」（3 个训练日全计入了、pending_rpe 是空）

首页 · 学生 1
  VOLUME / RATE  本周训练量 · 分钟  103.8 分钟  3 个动作 · 已含本周系数 0.80
                 另有 1 个附加模块 未指定训练量（不计入上面的合计）
                 本周打卡完成率  33.3 %  1 / 3 个处方训练日
  TO DO          2 项 →「10 月 06 日 的训练还没计入完成率」+「10 月 08 日 …」各带一个「去打卡」
  页脚           微周期第 1 周 · 训练日 2025-10-06、2025-10-07、2025-10-08

本周训练单 · 学生 4
  FACTOR         骨架第 1 周 × 本周调整系数  ×1.00 →「本周不调整（系数 1.00）」
                 「这一周没有任何调整：reasons 是空数组，factor 就是模板第 1 周的骨架量。」
  SEVEN DAYS     训练日 3 天 / 休息日 4 天
                 一 06 速度柔韧 · 二 07 速度柔韧 · 三 08 速度柔韧 · 四 09 休息 · 五 10 休息 · 六 11 休息 · 日 12 休息
                 「粗框的那一天是业务日 2025-10-12（周日）」
  DAY 1/2/3      各 3 个动作（每个都带 组次 / 每周量 / 每周次数 / 心率区间 / 强度 / 动作代号 六行）

每日打卡 · 学生 4
  COMPLETION     本周打卡完成率 100.0 %   一 10-06 已计入 · 二 10-07 已计入 · 三 10-08 已计入
  SUBMIT         「这一天不在本周训练单上」（缺省日期 = 业务日 2025-10-12 = 周日 = 休息日）
                 日期芯片 10 月 06 日 周一 / 10 月 07 日 … / 业务日 2025-10-12
                 「只会发出 5 个键：log_date / completed / duration_min / feeling / is_rest_day」

课堂快评 · 学生 4
  PENDING        「本周没有还没交的快评」+ 后端判据原文 +「三周前没交的仍可补交，后端刻意不做过期」
  SUBMIT         课次下拉 8 节 · 口令框「只能手输」· 11 个按钮（0 毫无感觉 … 10 力竭极限）
                 第 12 格图例「0–6 不触发预警 / 7–8 班均 > 7 触发 / 9–10 连续三次触发减量」
  TREND          我的课堂 RPE 趋势 4 次 · 5(09-21 第3节) → 4(09-28) → 8(10-05) → 6(10-12)
                 aria-label =「课堂 RPE 趋势：共 4 次，最近一次 6 分，均值 5.8 分（满标 10 分）」
                 caption =「共 4 次 · 均值 5.75 分」  ← 图上还画着「≥9 连续三次 → 减量」与「班均阈值 7」

二次小测 · 学生 4
  MY SCORES      我的 3 次小测（第 2 / 4 / 6 周）· 深蹲 30s / 折返 20m / 标准化分 三列
  PERCENTILE     「unauthenticated · 401 —— 这一格学生身份读不到」+ X-Teacher-Staff-No
                 +「本页**不会**在前端重算一遍百分位」

消息中心 · 学生 4
  ENDPOINT       「这一页读的是哪个端点」+「计划里猜的 GET /api/students/{id}/notifications **不存在**」
                 + 客户端过滤的判据 + 「挡不住『任何调用方匿名 GET 一次就读到全部 19 条』」
  MESSAGES       未读 1 / 1 ·「本周电子勋章」· 正文原文 · 未读 pill ·「标为已读」按钮
                 元信息 6 行：id / 收件人 student #4 / 渠道 站内消息 / 推于 2025-10-12 00:00 /
                 来源预警 alert #2 / 关联处方 —
```

### 4.4 三个写端点的真 HTTP 取证（`--dump-dom` 不能交互 → 改用真 HTTP，Task 5 的预演）

⚠️ body **逐字照页面组件里那个对象**，不是照 schema 的 `required` 凑一个最小 body ——
要证的是「**页面发的那一个**」能过。全部 20 步全绿（脚本退出码 0）。

**A. `POST /api/training-logs`（学生头）**

```
-- A1 学生 1 交 2025-10-13 的卡（库里原本没有这一天）
   REQUEST  POST http://127.0.0.1:8000/api/training-logs
   HEADERS  {"Accept": "application/json", "X-student-id": "1", "Content-type": "application/json"}
   BODY     {"log_date": "2025-10-13", "completed": true, "duration_min": 35.0, "feeling": "moderate", "is_rest_day": false}
   STATUS   201  Location: /api/training-logs/841
   RESPONSE {"id":841,"student_id":1,"log_date":"2025-10-13","submitted_at":"2026-10-11T17:02:32.739765",
             "completed":true,"duration_min":35.0,"feeling":"moderate","is_rest_day":false,
             "late":false,"source":"checkin","batch_id":null}
   ✓ submitted_at 由服务端填  ✓ late 由服务端算  ✓ student_id 来自请求头
   ✓ source 由服务端填        ✓ batch_id 恒为 null  ✓ duration_min / feeling 原样回读

-- A2 同一天再交一次 → 撞 uq_training_log_student_day
   BODY     （与 A1 逐字相同）
   STATUS   409
   RESPONSE {"error":{"code":"integrity_conflict",
             "message":"UNIQUE constraint failed: training_log.student_id, training_log.log_date","detail":null}}
```

⚠️ A1 证实了 `late = false`：`submitted_at` 是**真实的今天** 17:02（< 22:00），
而 `log_date` 是 2025-10-13 —— **`log_date` 不参与 `late` 的判定**
（`feedback.py:674-676`：「spec 说的是『22:00 **后提交**』，主语是提交时刻，不是『在补哪一天』」），
且**补卡照收**、只是不计入完成率（`submitted_at.date() != log_date`）。

**B. `POST /api/rpe-records`（学生头，口令手输）—— 9 步**

```
-- B1 教师建一节课           POST /api/class-sessions  {"course_section_id":1,"session_date":"2025-10-12","period":5}
   STATUS 201  Location: /api/class-sessions/9
   RESPONSE {"id":9,"course_section_id":1,"session_date":"2025-10-12","period":5,"rpe_opened":false,"batch_id":null}
   ✓ 响应体里**没有** rpe_token（键集合 = batch_id,course_section_id,id,period,rpe_opened,session_date）

-- B2 还没发起就交           STATUS 409
   RESPONSE {"error":{"code":"rpe_not_opened","message":"课次 9（2025-10-12 第 5 节）还没有发起课堂快评：
             rpe_opened=False、rpe_token 为空。教师端要先点「发起课堂快评」（POST /api/class-sessions/9/open-rpe）"}}
   ⚠️ 用的是**错口令**，却回 rpe_not_opened 而不是 invalid_rpe_token —— 证实那一道闸门排在验口令之前

-- B3 教师发起快评           POST /api/class-sessions/9/open-rpe   STATUS 200
   RESPONSE {"class_session_id":9,"rpe_opened":true,"rpe_token":"iZl1C0sFNF804_UZ","already_open":false}

-- B4 口令打错               STATUS 403
   RESPONSE {"error":{"code":"invalid_rpe_token","message":"课堂快评口令不匹配（课次 9）。
             口令由教师在课堂上投屏，长度是 16 个字符"}}

-- B5 学生用**手输的正确口令**交（body 逐字照 RpeEntry.vue 的 submit()）
   BODY     {"class_session_id": 9, "rpe": 7, "rpe_token": "iZl1C0sFNF804_UZ", "elapsed_seconds": 12.3}
   STATUS   201  Location: /api/rpe-records/241
   RESPONSE {"id":241,"class_session_id":9,"student_id":1,"rpe":7,
             "submitted_at":"2026-10-11T17:02:32.905651","elapsed_seconds":12.3}
   ✓ student_id 来自请求头  ✓ submitted_at 由服务端填  ✓ rpe 原样回读
   ✓ elapsed_seconds 原样回读（**前端量、后端不填**）

-- B6 同一节课再交一次       STATUS 409
   RESPONSE {"error":{"code":"integrity_conflict",
             "message":"UNIQUE constraint failed: rpe_record.class_session_id, rpe_record.student_id"}}
   ⚠️ 逐字证实计划里那个 `rpe_already_submitted` **不存在**，撞唯一约束就是 `integrity_conflict`

-- B7 匿名 GET /api/class-sessions?limit=200   STATUS 200（9 条）
   ✓ 响应体里**不含**口令 iZl1C0sFNF804_UZ（fix 波 2 顶回 1 那个洞的回归守卫）
   ✓ list 项的键集合 = batch_id,course_section_id,id,period,rpe_opened,session_date

-- B8 匿名读口令             GET /api/class-sessions/9/rpe-token   STATUS 401
   RESPONSE {"error":{"code":"unauthenticated","message":"缺少身份请求头 X-Teacher-Staff-No"}}
-- B9 **学生头**读口令       STATUS 401（⚠️ 不是 403：缺的是教师头，X-Student-Id 在不在场都不影响判定）
-- B10 教师头读口令          STATUS 200  {"class_session_id":9,"rpe_token":"iZl1C0sFNF804_UZ"}  ← 与 B3 逐字相同
```

**C. `POST /api/notifications/{id}/read`（学生头）**

```
-- C1 学生 4 去读学生 5 的那一条（id=2）  STATUS 403
   RESPONSE {"error":{"code":"not_recipient","message":"消息 2 不是发给学生 4 的（或它不存在）：
             notification 的收件人是多态的（recipient_kind + recipient_id 两列），本端点只认
             recipient_kind = 'student' ∧ recipient_id = 请求头里那个学号。⚠️ 两档刻意同形（都报 403）：
             notification.id 是连续的代理键，区分「不存在」与「不是你的」等于让「扫一遍 id」成为一次有效的探测"}}
-- C2 学生 4 读**自己的**那一条（id=1）   STATUS 200
   RESPONSE {"id":1,…,"is_read":true,…}      ← 只改 is_read、**不删行**
```

**D. `GET /api/mini-tests/normalized`（顶回 2 的实测证据）**

```
-- D1 学生头 X-Student-Id: 1   STATUS 401  {"error":{"code":"unauthenticated","message":"缺少身份请求头 X-Teacher-Staff-No"}}
-- D2 匿名                     STATUS 401  （同上）
-- D3 教师头 T0001             STATUS 200
   sections=5  unassigned=0
     班 1 scored_count=30 entries=30     班 2 scored_count=30 entries=30
     班 3 scored_count=20 entries=20     班 4 scored_count=20 entries=20     班 5 scored_count=20 entries=20
   entries[0] 的键集合 = composite,mini_test_id,shuttle_score,squat_score,student_id
   entries[0] = {"student_id":1,"mini_test_id":121,"squat_score":26.0,"shuttle_score":15.0,"composite":20.5}
   ⚠️ 同一个学生 1 在班 5 里是 {"shuttle_score":7.5,"composite":16.75} —— 逐字证实
      「一个学生同一学期可能在两个班、百分位各不相同」（后端因此按班分组而不平铺）
   ⚠️ 5 个班的 scored_count 最小是 20 → 「scored_count == 1 → 无排名」这一档**演示库上造不出来**
```

**E. 收尾**

```
-- E1 教师 DELETE /api/class-sessions/9   STATUS 204（全库唯一的 cascade，连带删掉 B5 那条快评）
-- E2 rpe-records    total = 240  ✓ 回到原状
-- E3 class-sessions total = 8    ✓ 回到原状
-- E4 training-logs  total = 841  ⚠️ = 840 + A1 那一行（training-logs 是**只读资源**，没有 DELETE 端点）
```

⚠️ **取证对演示库的净影响**（`pe_demo.db` 已进 `.gitignore`、**不入库**；重跑 `demo.ps1` 即复原）：
`training_log` 840 → **841**（学生 1 / 2025-10-13 / `source='checkin'`）；
`notification` id=1 的 `is_read` false → **true**。`class_session` 与 `rpe_record` 已复原。

---

## 5. 设计一致性自查

### 5.1 有没有写死 hex？—— **我的 11 个文件里 0 处**

对 `frontend/src/**/*.{vue,ts,css}` 全量 grep `#[0-9a-fA-F]{3,8}\b|rgba?\(`，命中 43 处，分布：

| 文件 | 命中 | 判定 |
|---|---|---|
| `styles/tokens.css` | 33（全是 `--xxx: #……` 的声明 + 2 处注释里的对比度出处） | ✓ **它就是唯一住址** |
| `styles/base.css` | 6（`rgba()` 的 4 处 + **`#a93623`** 1 处） | Task 1 的。⚠️ `#a93623`（`.btn--primary:hover`）是**唯一一个写在令牌之外的色值** → 记进待清扫 1 |
| `components/IdentitySwitcher.vue` | 1（`rgba(244,240,230,.35)`，与 base.css:298 逐字重复） | Task 1 的 → 待清扫 1 |
| `api/generated/schema.d.ts` | 1（注释里的 `id = 0`，不是色值） | 假阳性 |
| `styles/student.css` | ~~1~~ → **0** | ⚠️ 我原先写了 `rgba(20,17,15,.06)` 给行内 `code` 做底，**自查时改掉**了 → `var(--paper-raised)` |
| **Task 2 的 6 个 .vue + present.ts + useAsync.ts + StudentNav.vue + RpeTrend.vue** | **0** | ✓ |

### 5.2 有没有自己画 border 而不用 `lane.css`？—— **区块级 0 处**

- **区块分隔**（源码里 **20 处** `.lane-block` + **20 个** `<LaneDivider>`；
  其中 `WeeklySheet.vue` 有一处是 `v-for`，故学生 4 实际渲染出 **21** 个带分道线的区块：
  首页 4 + 训练单 5（系数 1 + 七日 1 + 训练日 3）+ 打卡 3 + 快评 3 + 小测 3 + 消息 3）
  一律用 `LaneDivider.vue`，
  道次编号 `01…0N` 连续递增、`--lane-index` 同步递增（于是 staggered reveal 是连续的 60ms 阶梯）。
  **一处 `border-bottom` 当区块分隔都没有。**
- 组件内**确实**出现了 `border:` —— 但全是「表单控件 / 卡片 / 芯片」这一类**元素级**的边，
  且一律写 `var(--border-hairline)` 或 `1px solid var(--rule-hairline)`（即 base.css 的
  `.card` / `.input` / `.btn` 同一套语言）。这与 `lane.css` 的文件头口径一致：
  「分道线是**区块级**的母题，铺到每一行会让整页都是线，识别性反而没了」。
- **母题的三次额外复用**（都是「同一个系统里的东西」的信号，不是新形状）：
  ① `StudentNav` 每一格左端那条 3px 竖线（选中换成 `--track`）；
  ② `RpeTrend` 的 0/5/10 三条网格线用 `--lane-thick`；
  ③ `.s-loading` 的加载指示就是**一条反复划出的分道线**（复用 `lane.css` 的 `@keyframes lane-draw`，
  不引入新的 keyframes）。

### 5.3 有没有引入新 UI 库？—— **0 个**

`frontend/package.json` **一个字节都没改**（本 Task 没碰它）：

```
dependencies    : pinia ^3.0.4, vue ^3.5.43, vue-router ^4.6.4
devDependencies : @types/node, @vitejs/plugin-vue, @vue/tsconfig,
                  openapi-typescript ^7.13.0, typescript ~5.9.3, vite ^8.3.4, vue-tsc ^3.3.13
```

Element Plus / Vuetify / Naive UI / Tailwind / UnoCSS / ECharts / axios **一个都没有**。
图标一律**内联 SVG**（空态那个「一条没画完的分道线」）或 Unicode（`✓` `✗` `⚠` `—` `×`）。

### 5.4 动效是否只在那三处？—— **是**

| 动效 | 住址 | 本 Task 的使用点 |
|---|---|---|
| ① 分道线从左到右划出 | `lane.css` 的 `@keyframes lane-draw` + `.lane-block` | 21 个区块（`--lane-index` 递增 60ms）+ `.s-loading` + `RpeTrend` 的折线（`pathLength=100` + dashoffset，同一条曲线同一组令牌） |
| ② 数字滚动 | `StatBlock.vue` | 首页 4 处（每种单位 1 个训练量 + 完成率 + 未读 + 勋章）、打卡页 1 处（完成率 hero）、小测页 3 处/班（综合分 / 折返百分位 / 深蹲得分） |
| ③ 盖章 | `StampFeedback.vue` | **只有 2 处**：打卡 201（`tone="moss"`「已打卡」）与快评 201（`tone="track"`「已提交」） |

**没有做**：hover 浮动、视差滚动、页面转场、骨架屏闪烁、进度条动画。
`:hover` 只改底色/边框色（继承 base.css 的 `.btn`），`transition` 只用 `--dur-fast`(140ms)。
⚠️ `@media (prefers-reduced-motion: reduce)` 由 `base.css` 一处兜住，本 Task 不写第二份。

### 5.5 375px 与出血

- 6 个页面一律 `.s-page`（单列）+ `.s-card`（`margin-inline: var(--bleed)` = −16px、
  `padding-inline: var(--gutter)` = 16px）→ 卡片**出血到屏幕边缘**，内容宽 343px。
- 触控目标实测：RPE 按钮 ≈ 80 × 74px、`feeling` 三按钮 ≈ 109 × 62px、
  导航 6 格 ≈ 109 × 52px、日期芯片 ≈ 高 28px（⚠️ 这一格低于 44px，记进待清扫 3）。
- **没有横向滚动**：唯一可能溢出的是打卡页的历史表（5 列 × `--fs-micro`），
  实测 375px 下不溢出（`.data-table td` 的 `padding-inline-end` 压到 `--space-1`）。

---

## 6. 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 6.1 顶回控制者：**9 处**（其中 **2 处 Critical**）

---

**顶回 1（Critical）·「消息中心」的端点不存在，客户端过滤堵不住那个洞**

- **计划/派单说**：Task 2 的表格写 `GET /api/students/{id}/notifications`，并标了「⚠️ 实现者要实测确切路径」；
  派单第 5 节逐字：「若它其实只有泛型的 `GET /api/notifications?limit=…`（没有按学生过滤的端点），
  那前端就得客户端过滤 —— 但那样会读到别人的通知，是个洞 → 顶回来。」
- **实测**：正是后者。`/openapi.json` 里含 `notification` 的路径只有三条
  （`GET /api/notifications` 匿名 / `GET /api/notifications/{id}` 匿名 /
  `POST /api/notifications/{id}/read` 学生头），**没有**任何按学生过滤的 list。
  而泛型 list **没有筛选参数**（约束第 9 条：`?recipient_id=4` 会被 FastAPI **静默忽略**）。
- **我做了什么**：`endpoints.ts` 的 `listMyNotifications()` 翻页收集 + 客户端过滤
  `recipient_kind === 'student' && recipient_id === 我`。**页面是对的**（只显示我的），
  并且第 01 区块把这件事**写在页面上**给用户看。
- **为什么仍然是个洞**：洞在 **API** 上、不在页面上 —— 任何调用方匿名 GET 一次
  就读到全部 19 条（含发给别人的姓名无关的正文、`alert_id`、`prescription_id`）。
- **⚠️ 但请连同约束第 1 条一起裁定**：本仓的口径是「**挡事故、不挡攻击**」
  （`deps.py:3-7`），而 92 个操作里 **47 个 GET 是匿名的**，其中已经包括
  `GET /api/students`（60 个学生的姓名/学号/院系/出生日期）、`GET /api/alerts`、
  `GET /api/prescriptions`。故「匿名能读到别人的通知」与「匿名能读到别人的出生日期」
  是**同一档**，不是通知独有的新洞。
- **建议**：**开一个几行的小修波**补 `GET /api/students/{student_id}/notifications`
  （学生头 + `require_scope`），因为后端**已经会**按学生过滤 ——
  `dashboard.py:489-497` 的 `unread_notifications` 就是服务端按
  `recipient_kind + recipient_id + is_read` 数出来的。补上它之后前端只改
  `listMyNotifications` 一个函数体（**签名不变**），页面一行都不用动。
  **不补也能演示**，但请在验收文档里把这一档如实记成已知边界。

---

**顶回 2（Critical）·`GET /api/mini-tests/normalized` 挂的是教师头，而计划把它分给了学生页**

- **计划/派单说**：Task 2 的表格把「二次小测」页的端点写成 `GET /api/mini-tests/normalized`；
  派单第 8 节第 4 条要求「小测页有百分位」。
- **实测**：`/openapi.json` 的 `security` 是 `[{"X-Teacher-Staff-No": []}]`，
  `feedback.py:935-972` 的第一行形参就是 `staff_no: str = Depends(current_teacher)` + `require_teacher(...)`。
  三种身份实测：**教师头 → 200 / 学生头 → 401 / 匿名 → 401**（第 4.4 节 D1–D3 的原文）。
- **后果**：学生身份下这一页**读不到班内百分位**。而 `client.ts` 一次只注入一个头
  （`stores/identity.ts`：「一次只有一种身份」），故「有 `studentId`」与「能读 normalized」
  在今天的架构下**互斥** —— 换教师身份也救不了（那样就没有 studentId 了）。
- **我做了什么（降级但不撒谎）**：① 原始成绩走**匿名**的 `GET /api/mini-tests`（永远有：
  每个学生 3 行，第 2/4/6 周）；② 401 渲染成一块**有解释的区域**（code、要哪个头、
  后端那行形参、换成 `T0001` 或 `?teacher=T0001` 就能看到），
  **不**进红色横幅（横幅会把「设计如此」讲成「出事了」）；
  ③ **不在前端重算百分位** —— 算式只有一个住址（`app/domain/report.py`），
  后端有 AST 守卫 `test_the_mini_test_normalization_has_exactly_one_definition` 数定义份数 == 1，
  前端再写一份就是第二个所有者；④ 成功支路**照样实现**（含 `scored_count == 1` → 「无排名」
  与「比自己慢的人数」），并在代码里逐字写明「今天渲染不出来」+ 保留它的三条理由。
- **建议（三选一，按代价从小到大）**：
  **(a)** 把那个 GET 的 `dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]` 摘掉 →
  它变成第 48 个匿名 GET，与「大屏与列表要能匿名读」的口径一致，前端**一行都不用改**就亮；
  ⚠️ 代价是任何调用方能读到全校 5 个班的百分位（**与顶回 1 同一档**：匿名 list 本来就能读到
  全部 180 行小测原始成绩，含 `student_id` + 秒数 + 次数 —— 故摘掉它**不新增**泄漏面，
  只是把已经能算出来的东西算好了给出去）；
  **(b)** 补一个学生侧变体 `GET /api/students/{id}/mini-tests/normalized`（学生头 + `require_scope`，
  只回我在的那几个班）—— 最干净，但要动 `feedback.py` 与 1255 条测试；
  **(c)** 什么都不做，把「学生端看不到班内百分位」如实记成已知边界。
  **我推荐 (a)**：一行、与既有口径一致、不新增泄漏面。

---

**顶回 3（Major）·约束第 3 条那句「47 个 GET 全部匿名 …… 所有读请求可以不带[头]」是说漏了的**

- **计划逐字**：「92 个操作里 45 个挂 `security`：26 个是泛型 CRUD 的写入侧 + 19 个特例端点。
  **47 个 GET 全部匿名**（大屏与列表要能匿名读）。⚠️ 故：所有写请求必须带教师头，
  **所有读请求可以不带**。」
- **实测**：92 个操作里 **GET 有 57 个**，其中 **47 个匿名、10 个挂 security**。
  那 10 个是：

  ```
  GET /api/class-sessions/{id}/rpe-status                     教师头
  GET /api/class-sessions/{id}/rpe-token                      教师头
  GET /api/dashboard/class/{course_section_id}                教师头
  GET /api/dashboard/weekly-class-report/{course_section_id}  教师头
  GET /api/mini-tests/normalized                              教师头   ← 顶回 2 就是它
  GET /api/students/{id}/home                                 学生头
  GET /api/students/{id}/prescriptions/current                学生头
  GET /api/students/{id}/training-logs/completion-rate        学生头
  GET /api/students/{id}/weekly-sheet                         学生头
  GET /api/teacher/students/{id}/weekly-sheet                 教师头
  ```
- **判定**：「**47 个** GET 匿名」这个**数字是对的**，但「**47 个 GET 全部匿名**」这个**措辞**
  会被读成「GET 一共 47 个、全都匿名」，而紧跟着那句「**所有读请求可以不带**」
  在这 10 个上**逐字是错的**。Task 1 的 `endpoints.ts` 其实已经逐个标对了
  （它给这 10 个都写了「**学生头**」/「**教师头**」），故这一档**没有害到 Task 1**；
  而它**害到了 Task 2** —— 计划把 `mini-tests/normalized` 分给学生页，正是因为「读请求可以不带头」。
- **建议**：把约束第 3 条改成「**57 个 GET 里 47 个匿名、10 个挂 security（6 教师头 + 4 学生头，
  清单如上）**；故『读请求一律可以不带身份』**不成立**，逐个查 `security`」。
  ⚠️ Task 3 会再撞一次：大屏那两个 GET 都要教师头。

---

**顶回 4（Major，但**不是**数据问题）·派单期望的「`alert` 应 11」与实测 30 不符 —— 11 数的是红色那一档**

- **派单第 3 节第 4 步逐字**：「`alert` 应 11」。计划约束第 22 条也写「**11 条预警**」。
- **实测**（重灌之后）：`alert` 表 **30 行** = `red` **11** + `green` **13** + `yellow` **6**，
  `status` 全是 `pending`，`student_id` 全非空。
- **判定**：**不是数据没灌对，是那份清单数的是「红色预警」。** 证据是它**自洽**：
  `green 13 + yellow 6 = 19`，而 19 正是通知条数（`GREEN_MASTERY` → 电子勋章 13 条、
  `YELLOW_CHECKIN_GAP` → 补练提醒 6 条；两条 `RED_*` **刻意不自动推送**）。
  故「11 / 19」这两个数出自同一次统计，只是 11 数的是 `level='red'`。
- **后果与建议**：Task 3 的验收逐字写着「用演示库能看到……**11 条预警**」——
  照它写断言会**红**（大屏读到的是 30 行）。建议改成
  「**30 行预警，其中 11 行红色**（`RED_RPE_SUSTAINED` 6 + `RED_MINITEST_DROP` 5）、
  13 行绿色、6 行黄色，全部 `pending`」。
  ⚠️ 顺带一条给 Task 3 的实测事实：**30 行全是学生级**（`student_id` 非空 30/30），
  故 `YELLOW_CLASS_RPE_HIGH`（班级作用域）在演示库上**一行都没有** ——
  教师端若按 `course_section_id` 过滤班级级预警会得到空列表，那不是 bug。

---

**顶回 5（Major）·派单第 8 节第 4 条「消息中心有 19 条通知」与正确行为冲突**

- **派单逐字**：「6 个页面各自的关键数据要非空……**消息中心有 19 条通知**。」
- **实测**：19 条是**一人一条**发给 19 个**不同**的学生
  （`recipient_id` = 4,5,6,10,11,15,17,25,26,35,38,40,43,47,48,53,54,56,60，各 1 条）。
  故**任何一个学生最多只能看到 1 条**；要看到 19 条就必须**不过滤**，
  而那正是顶回 1 说的那个洞（页面会显示别人的消息）。
- **我做了什么**：按**正确**的那一边做（严格过滤），取证用**学生 4**（他有 1 条未读 + 1 枚勋章），
  并把「19 条是一人一条」这件事**写进空态**（于是换一个身份看到 0 条时不会以为页面坏了）。
- **建议**：把验收改成「消息中心对**学生 4** 显示 **1 条未读**，并能标为已读；
  对**学生 1** 显示设计过的空态（并说明 19 条是发给哪 19 个人的）」。
  ⚠️ 若控制者想要「一屏看见 19 条」的演示效果，那应该做在**教师端/管理台**
  （`/admin/notifications` 的列表页，Task 4），而不是学生端。

---

**顶回 6（Minor）·派单说「每个按钮要显示 **Borg 量表**那一档的文字」—— 0–10 是 **CR-10**，不是 6–20 那张**

- **派单逐字**：「RPE 是 0–10，用 11 个大按钮……**每个按钮要显示 Borg 量表那一档的文字**」。
- **实测**：后端在**四处**逐字钉住「**不是** Borg 经典的 6–20」
  （`assembler.py:235-238` 与 `:464-467`，出处是 spec 的四处原文：
  `rpe_record` 表字段「RPE 0–10」、§8.2 小标题「课堂端 RPE（0–10 主观疲劳）」、
  `RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」、`YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」）。
- **判定**：这一档**不冲突，但措辞会误导** —— 「Borg 量表」在中文语境里常被理解成 6–20 那张
  （1970 年的原始 RPE 表），而 0–10 是 **Borg CR-10**。若照 6–20 那张的文字去填 11 个按钮，
  就会得到「7 分 = 非常吃力（6–20 表上 7 是『极轻松』）」这类**语义错位**，
  而错位的后果是「同一个 7 分在两个班里不是一个意思」→ `YELLOW_CLASS_RPE_HIGH` 的
  「均值 > 7」失去可比性。
- **我做了什么**：用 **CR-10 的 11 个标准语言锚点的中文对译**（第 2.4 节那张表，
  0 = Nothing at all … 10 = Maximal），住址在 `present.ts` 的 `RPE_SCALE`（**单一所有者**），
  并把 7/8 与 9/10 的染色**取自后端两条规则的阈值**。
- **建议**：把措辞改成「**Borg CR-10**（0–10）的语言锚点」。

---

**顶回 7（Minor）·深链接身份放在 `stores/identity.ts`（一处），不是「6 个页面组件里各一个调试入口」；并主张**保留****

- **派单逐字**：「若做不到，就改为在页面组件里支持一个 `?student=1` 的**调试入口** ——
  但那要写明它是调试用的、并在 Task 5 之前决定去留。」
- **实测**：`--dump-dom` **确实**做不到「先写 `localStorage` 再导航」——
  它在首次 load 之后就 dump 并退出，没有注入脚本的时机；
  用一个同源的 `seed.html` 先写再跳转也不行（`--dump-dom` 不跟重定向后的第二帧）。
  另外两个候选也都不划算：给 6 个页面各开一个入口 = **6 个住址**（正是派单要防的形状）；
  给 Vite 加一个 dev-only 中间件 = 改 Task 1 的工程配置、且生产构建里没有它。
- **我做了什么**：`stores/identity.ts` 加一个 action `adoptFromUrl(search)`，
  `main.ts` 在**挂载之前**调一次（页面组件的 `onMounted` 里就要发请求，晚一步第一屏就是 401）。
  支持 `?student=N` / `?teacher=T0001` / `?as_of=YYYY-MM-DD` / `?label=…`，
  三条纪律：只在参数存在时才动状态（刷新不会冲掉已选的身份）、不合格的值一律**忽略**
  （不抛错、不写 `localStorage`）、一次只认一种身份（与 `client.ts`「一次只注入一个头」同一口径）。
- **⚠️ 主张保留（不当调试后门）**：本仓**没有登录页**（非目标第 1 条），
  而「身份切换器」只能被**人**点。一条被推送出去的链接（学校推送、教师投屏上的二维码、
  以及 Task 5 的联调取证）落地时**没有人去点它** —— 一个真的 H5 打卡入口本来就是
  「一条带身份的链接」。故它不是调试用的，它是「没有登录页」这个决定的**必要补充**。
  ⚠️ 它**不构成鉴权**（`?student=5` 就能变成学生 5），而本仓的身份头**本来就不构成鉴权**
  （`X-Student-Id: 5` 一样能变成学生 5）——「挡事故、不挡攻击」。
- **给 Task 5 的一条**：`smoke.mjs` 的浏览器侧取证可以直接用这一格，不必再想办法注入 `localStorage`。

---

**顶回 8（Minor）·「本周训练量」不能是**一个**数**

- **计划逐字**：Task 2 的表格「本周训练量（**数字滚动**）」，读起来像一个大数字；
  计划第 2 节也说「数字滚动……只用于大屏的关键指标与**学生的本周训练量**」。
- **实测**：`prescription_stage.py:411-417` 逐字「**刻意不加任何跨单位的周总量汇总字段**……
  `volume_unit` 的实测值域是 `{min, reps, unspecified}` 且**同一周里三个并存**
  （红层 `RED-END-ABN-01` + 体成分异常那一档就是），把它们相加就是 Plan 02 Task 5 的
  F1-1 那个『混合量纲 float』错误 —— **48 分钟 + 120 次 = 168 什么？**」，
  并且有守卫 `test_the_sheet_has_no_cross_unit_total_field`（**按键集相等**断言）。
- **我做了什么**：首页**按 `volume_unit` 分列**，每一种单位一个 `StatBlock`（`size="hero"`，
  数字滚动照做）；`unspecified` **不进合计**、另起一行写「另有 N 个附加模块**未指定训练量**」。
  演示库上学生 1/4 都只有 `min` 一种，故看起来仍是一个数；红层那一张处方会是两个。
- **建议**：把计划那一格改成「本周训练量（**按单位分列**，数字滚动）」。
  ⚠️ Task 3 的大屏「本周概览」会撞同一档。

---

**顶回 9（Minor）·我在派单的 Create 清单之外加了 4 个文件**

派单的 Create 清单是「6 个页面 + `RpeTrend.vue`」。我另外加了 4 个，每个的理由都写在那个文件的头部：

| 文件 | 行数 | 为什么非加不可 |
|---|---|---|
| `src/styles/student.css` | 285 | 派单第 6 节逐字要求「6 个页面必须长得像**同一套**设计」。若把 `.s-page` / `.s-card` / `.s-empty` / `.s-unknown` / `.s-notice` 写进 6 个 `<style scoped>`，漂开的形态是「首页的卡片出血 16px、打卡页出血 12px」—— 而两者各自的截图都好看。它与 `base.css`（全局）/ `lane.css`（母题）是同一层的东西：**布局类的住址**，不含一个令牌 |
| `src/views/student/present.ts` | 246 | 后端**刻意只存英文 token、把中文标签留给前端**（`feedback.py:397-400` 逐字「中文标签由前端映射」）。前端因此是那些标签的**所有者**，而所有者只能有一个住址。含 `feeling` 三档、预警规则 5 档（`RuleId` 的实测键集）、`volume_unit` 三档、RPE 11 档、`toPercent()`（×100 只做一次）、周一起的日期算术 |
| `src/composables/useAsync.ts` | 93 | 6 个页面各抄 20 行「loading/error/data + 竞态守卫」的失效形态不是「代码长」，而是**6 份会各自漂开**：同一个后端故障在 6 个页面上长 6 个样子。⚠️ 它**刻意不是**缓存层（计划第 3 节：Pinia 只存三样，「服务端缓存」今天没有住址）—— 没有 TTL、没有去重、换页就重读 |
| `src/components/StudentNav.vue` | 147 | `App.vue` 的报头只有三棵树的入口，而 Task 1 已经把 6 条 `/s/*` 路由建好了。没有这一格，那 6 条路由**只能靠手敲 URL 到达** —— 而计划第 0 节的判据逐字是「起两个服务、**点着**走完一条业务链」 |

⚠️ 四个都**不引入任何依赖**（`package.json` 一个字节没改），且**都不含设计令牌**。

### 6.2 没按派单做的地方：**3 处**

1. **深链接身份的位置**：派单说「在**页面组件**里支持一个 `?student=1` 的调试入口」，
   我做在 `stores/identity.ts` 的 `adoptFromUrl()`（**一处**而不是 6 处），
   并主张它**不是**调试用的（顶回 7）。
2. **`?student=1` 换成了 `?student=4`**：派单举的例子是学生 1，而学生 1 的
   `unread_notifications = 0`、`badges.count = 0`、`pending_rpe = []` —— 消息中心与勋章两格全空。
   实测 60 个学生里只有 19 个「有未读或有勋章」，其中**学生 4** 同时有
   1 条未读 + 1 枚勋章 + 黄色层，故取证主身份用 4；
   ⚠️ 但首页**另外跑了一次学生 1**（他的完成率是 1/3、有 2 个训练日没计入 → 待办非空，
   而学生 4 的待办恰好是空的）。两个身份合起来才把首页的两条支路都走到。
3. **commit 的切法**：派单建议「① 6 个页面 + RpeTrend；② router 与 endpoints 的接线；③ 取证与报告」。
   我切成了「① **共享层**（student.css / present.ts / useAsync.ts / StudentNav.vue / RpeTrend.vue /
   identity.ts / main.ts）→ ② **6 个页面 + 接线**（含删掉占位页）→ ③ 报告」。
   理由：按派单的切法，commit ① 会让 `router/index.ts` 仍然 import 一个**已删除**的
   `StudentPlaceholder.vue`（那 6 个页面此时还没被引用），于是 ① 单独 checkout 出来**不能构建**。
   我这个切法**两个 commit 各自都能构建**（① 时占位页还在、路由没动；② 时才一起换）。

### 6.3 待清扫：**5 条**

1. **`base.css:286` 的 `#a93623`**（`.btn--primary:hover`）是**全仓唯一一个写在 `tokens.css`
   之外的色值** —— 它是 `--track`(#BE3F2B) 压深一档的 hover 色。建议在 `tokens.css` 里加一个
   `--track-pressed` 并把这一行换掉（`IdentitySwitcher.vue:407` 与 `base.css:298` 那两处
   `rgba(244,240,230,.35)` 同理：它们逐字重复，应当提成一个 `--shadow-on-ink`）。
   ⚠️ **本 Task 没动它们**：那是 Task 1 的文件，改它属于「顺手改进」而不是本 Task 的活。
2. **`exercise` 与 `prescription_template` 两张表恒为 0 行**（第 1.4 节）。
   ⚠️ 这**不是**「旧库的症状」（Task 1 的诊断要更正），重灌之后仍是 0：
   动作库的运行时所有者是 YAML（`refdata_prescription.py:282` 的 `exercises()` 是进程内单例）。
   **对 Task 4 的后果**：管理台那 23 个资源里有 2 个的列表页**注定是空的**，
   而它们恰好是**刻意只读**的那两个（spec §4.4）。验收不要要求它们非空。
3. **打卡页的日期芯片高约 28px**，低于 44px 的触控下限（同一页的 `feeling` 三按钮是 62px、
   RPE 是 74px，都过）。它旁边有一个 `<input type="date">` 兜底，故不是死路，
   但手机上会难点。**建议**：把芯片的 `padding` 抬到 `--space-2 var(--space-3)`（→ 约 36px），
   或者干脆去掉芯片、只留 `<input type="date">` + 一个「今天」按钮。
4. **`GET /api/training-logs` 要翻 5 页**（840 行 / `limit` 上界 200）才能过滤出我的 14 行，
   打卡页每次挂载都做一次；快评页同理（240 行 → 2 页）。
   ⚠️ 这是约束第 9 条（泛型 list 没有筛选参数）的直接代价，**不是**本页的问题。
   若控制者愿意开小修波，给泛型 list 加一个 `student_id` 查询参数（或者补
   `GET /api/students/{id}/training-logs`）能把这两页的请求数从 5+2 降到 1+1。
   `collectPages()` 的 `cap = 1200` 是那一天的护栏：真实数据超过它时会显示
   「⚠️ 只收到前 N 行（收集上限）」而不是静默截断。
5. **本 Task 的 4 个探针脚本留在 `%TEMP%`**（`pe_probe*_t2.py` / `pe_count_t2.py` /
   `pe_dom_evidence_t2.py` / `pe_http_evidence_t2.py` / `pe_write_msgs_t2.py`），
   跑完**已按要求不进仓库**。⚠️ 其中 `pe_http_evidence_t2.py` 是 Task 5 `smoke.mjs`
   第 ②③④⑤⑥ 步的**现成蓝本**（12 步里有 5 步已经写好并跑绿了），
   建议在 Task 5 开工前把它翻译成 `.mjs` 而不是重写。

### 6.4 关切（不阻塞，但下一个人要知道）

1. **`RpeEntry.vue` 的「用时」计时从「课次 + 口令都就位」起算**，不是从组件挂载。
   理由：挂载到用户看清投屏口令之间那几秒不是作答时间。
   ⚠️ 但它**含**了「用户在 11 个按钮上犹豫」的时间 —— 而 spec 那一列的语义是「提交耗时秒」，
   犹豫本来就是它要量的东西。若将来要做「作答时长」的研究，这一格的口径要写进 spec。
2. **`WeeklySheet.vue` 的 `reasons`/`sources` 是两条平行数组**（按下标配对），
   后端没有把它们做成 `[{reason, source}]`。我按下标配对并对越界做了兜底
   （`sources[i] ?? UNKNOWN`）。⚠️ 若后端哪天改了顺序，前端会**静默**配错对
   （把「教师手工调整」标成「红色预警」）—— 这是一个跨进程的隐式契约，建议 Task 5 的
   `smoke.mjs` 加一条对拍：`len(reasons) == len(sources)`。
3. **`home.weekly_sheet` 与 `weekly-sheet` 端点是同一份数据的两个投影**
   （后端 `_sheet_or_none` 就是调 `_weekly_sheet_response`），故首页与训练单页
   各请求一次会拿到**逐字相同**的 6 个键。今天不做缓存（`useAsync` 刻意不是缓存层），
   代价是多一次请求；好处是「教师刚处置完预警、学生刷新就看到减量后的训练单」（约束第 13 条）。
4. **`notifications` 的排序是客户端做的**（后端给的是 `id` 升序，实测 1,2,3…）。
   按 `created_at` 倒序、再按 `id` 倒序。⚠️ 演示库里 19 条的 `created_at` **全部相同**
   （`2025-10-12T00:00:00`），故实际排序由 `id` 决定。

---

## 7. 最终验收

### 7.1 `npm run build`（`vue-tsc -b && vite build`）

```
> physical-education-ims-frontend@0.1.0 build
> vue-tsc -b && vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 90 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   1.89 kB │ gzip:  1.20 kB
dist/assets/index-S63pvW4H.css   51.32 kB │ gzip:  8.79 kB
dist/assets/index-R6HMct7M.js   215.22 kB │ gzip: 76.96 kB

✓ built in 293ms
BUILD_EXIT=0
```

| | Task 1 | **Task 2** | Δ |
|---|---|---|---|
| 退出码 | 0 | **0** | — |
| modules | 63 | **90** | +27 |
| `index.html` | 1.89 kB | **1.89 kB** | 0 |
| CSS | 26.78 kB | **51.32 kB** | +24.54（`student.css` + 6 个页面的 scoped） |
| JS | 135.96 kB | **215.22 kB** | +79.26（6 个页面 + 4 个共享文件） |
| gzip（CSS / JS） | — | **8.79 / 76.96 kB** | — |

⚠️ **一个 `// @ts-ignore` 都没有**，也没有 `@ts-expect-error` / `as any`。
第一轮构建报了 **3 个真错误**（两处 `completion_rate` 可能为 `null` 却直接 `* 100`、
一处未使用的 import），全部**修掉**而不是绕过 —— 那两个 null 错误正是约束第 10 条
要防的形状，`vue-tsc` 替我抓到了。

### 7.2 `npm run dev` 与 6 条路由

`npm run dev` 起得来（Task 1 留的那个进程一直在跑，vite 8.3.4，绑 `::1:5173`）。
6 条 `/s/*` 路由**全部渲染**（第 4.2 节的 7 次 `--dump-dom`，81 条断言全绿）。
`/` 与 `/s` 仍然 redirect 到 `/s/home`；打错的 URL 仍然 redirect 到 `/s/home`（Task 1 的兜底）。

### 7.3 禁区复核（5 个结论）

| # | 复核项 | 结果 |
|---|---|---|
| 1 | `Test-Path backend\pe.db` | **False** ✓ |
| 2 | `backend/data/seed/` 的文件数（`-File -Recurse`） | **0** ✓ |
| 3 | `git status --short` 里有没有 `node_modules` | **没有** ✓ |
| 4 | `git status --short` 里有没有 `pe_demo.db` | **没有** ✓（它在 `.gitignore` 里） |
| 5 | `git diff HEAD -- backend/data` | **空** ✓（`--stat` 无输出） |

⚠️ 另外：`demo.ps1` 自带两道禁区守卫，两次重灌都打印了
「禁区复核：`backend\pe.db` 不存在、`backend\data\seed\` 仍为 0 文件 ✓」。
**`backend/` 下的生产代码一个字节都没改**（`git status` 里没有任何 `backend/` 条目）。

### 7.4 `git status --short`（commit 之后）

```
（空 —— 工作树干净）
```

### 7.5 3 个 commit

| sha | 一句话 |
|---|---|
| **`6f480cb`** | `feat(frontend): 学生端的共享层 —— 展示口径 / 四态读取 / 跑道导航 / RPE 趋势图`（7 个文件：`student.css` / `present.ts` / `useAsync.ts` / `StudentNav.vue` / `RpeTrend.vue` / `main.ts` / `identity.ts`） |
| **`9baf2ba`** | `feat(frontend): 学生端 6 个页面 + 路由接线 —— 首页/训练单/打卡/快评/小测/消息中心`（9 个条目：6 个新页面 + `router/index.ts` + `endpoints.ts` + 删掉 `StudentPlaceholder.vue`） |
| **（本报告）** | `docs(sdd): Plan04 Task 2 实现报告 —— 2 处 Critical 顶回 + 6 页真实渲染取证 + 3 个写端点的真 HTTP 取证` |

`git diff --stat 6f480cb~1 HEAD`（前两个 commit 合计）：

```
 frontend/src/api/endpoints.ts                     |  95 +++
 frontend/src/components/StudentNav.vue            | 162 +++++
 frontend/src/components/charts/RpeTrend.vue       | 377 +++++++++++
 frontend/src/composables/useAsync.ts              | 102 +++
 frontend/src/main.ts                              |  16 +-
 frontend/src/router/index.ts                      |  88 ++-
 frontend/src/stores/identity.ts                   |  50 ++
 frontend/src/styles/student.css                   | 332 ++++++++++
 frontend/src/views/student/CheckIn.vue            | 745 ++++++++++++++++++++++
 frontend/src/views/student/Home.vue               | 519 +++++++++++++++
 frontend/src/views/student/MiniTest.vue           | 576 +++++++++++++++
 frontend/src/views/student/Notifications.vue      | 369 +++++++++++
 frontend/src/views/student/RpeEntry.vue           | 695 ++++++++++++++++++++
 frontend/src/views/student/StudentPlaceholder.vue | 109 ----
 frontend/src/views/student/WeeklySheet.vue        | 559 ++++++++++++++++
 frontend/src/views/student/present.ts             | 284 +++++++++
 16 files changed, 4914 insertions(+), 164 deletions(-)
```

⚠️ `frontend/package.json` / `package-lock.json` / `vite.config.ts` / `tsconfig*.json` /
`index.html` / `src/api/generated/schema.d.ts` / `src/api/types.ts` **一个字节都没改**
（`types.ts` 不需要改：6 个页面用的响应模型全部在 codegen 产物里，
含 `AssembledSessionRead` / `AssembledBlockRead` / `NormalizedEntryRead` /
`NormalizedSectionRead` / `PendingRpeRead` / `BadgeRead` / `StratificationRead`）。

### 7.6 计划 Task 2 的验收逐条对拍

| 计划的验收 | 结果 |
|---|---|
| 手机视口（375px）下 6 个页面都能走完 | ✓ `--window-size=375,1400`，7 次 dump 全部渲染；`StudentNav` 让 6 页互相可达 |
| 用演示库的真实学生能看到**非空的训练单** | ✓ 学生 4：微周期第 1 周、系数 1.00、3 个训练日 × 4 个动作；学生 1：系数 0.80、`reasons=["RED_RPE_SUSTAINED"]` |
| 能**打卡成功** | ✓ 真 HTTP 取证 A1：201、`Location: /api/training-logs/841`、四个服务端字段都填了 |
| 能**手输口令交快评** | ✓ 真 HTTP 取证 B5：201、`Location: /api/rpe-records/241`、口令是从 B3 的教师端拿的（学生端三个入口都拿不到，逐一实测过） |
| 口令从教师端拿（见 Task 3） | ✓ 本 Task 用 `POST /api/class-sessions/{id}/open-rpe`（教师头）代替；Task 3 应当优先用 `GET …/rpe-token`（计划第 8 节自审第 5 条） |
| 派单第 8 节第 1 条：build 退出码 0、无 TS 报错 | ✓ 见 7.1 |
| 派单第 8 节第 2 条：dev 起得来、6 条路由都能渲染 | ✓ 见 7.2 |
| 派单第 8 节第 3 条：真实渲染取证 + 两个 POST 的真 HTTP | ✓ 见 4.2 / 4.3 / 4.4（**7 条 URL / 81 断言**，**3 个写端点 / 20 步全绿**） |
| 派单第 8 节第 4 条：6 个页面各自的关键数据非空 | **5 / 6 完全达成**，第 6 个（消息中心的「19 条」）与正确行为冲突 → **顶回 5**；另小测页的「百分位」被顶回 2 挡住，已降级但不撒谎 |
| 派单第 8 节第 5 条：禁区复核 | ✓ 见 7.3 |

---

## 附：本 Task 交付的文件清单

**Create（11 个）**

```
frontend/src/styles/student.css                  285 行    9 236 B
frontend/src/composables/useAsync.ts              93 行    4 870 B
frontend/src/components/StudentNav.vue           147 行    5 233 B
frontend/src/components/charts/RpeTrend.vue      328 行   12 355 B
frontend/src/views/student/present.ts            246 行   14 298 B
frontend/src/views/student/Home.vue              476 行   21 677 B
frontend/src/views/student/WeeklySheet.vue       500 行   20 018 B
frontend/src/views/student/CheckIn.vue           674 行   27 844 B
frontend/src/views/student/RpeEntry.vue          617 行   26 429 B
frontend/src/views/student/MiniTest.vue          528 行   24 742 B
frontend/src/views/student/Notifications.vue     334 行   15 746 B
```

**Modify（4 个）**：`src/router/index.ts`（6 条 `/s/*` 换成真页面、删掉 `meta.intent`）、
`src/api/endpoints.ts`（+95 行：`collectPages()` 与三个「翻页收集 + 客户端过滤」助手）、
`src/stores/identity.ts`（+50 行：`adoptFromUrl()`）、`src/main.ts`（+16 行：挂载前认深链接身份 + import `student.css`）。

**Delete（1 个）**：`src/views/student/StudentPlaceholder.vue`（109 行，已被 6 个真页面取代；
`/t/*` 与 `/admin/*` 的两个占位页**原样保留**给 Task 3/4）。

**没碰**：`backend/**`（生产代码一个字节都没改）、`frontend/package.json`、
`vite.config.ts`、`tsconfig*.json`、`index.html`、`src/api/generated/schema.d.ts`、
`src/api/types.ts`、`src/api/client.ts`、Task 1 的三个原子组件与 `tokens.css` / `base.css` / `lane.css`。
