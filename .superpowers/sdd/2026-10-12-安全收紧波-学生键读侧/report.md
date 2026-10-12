# 安全收紧波 · 学生键读侧 —— 实现者报告

分支 `harden/student-keyed-reads`（从 `main` 的 `5218eb4` 起）。
**不 push、不碰 main**（控制者 fast-forward 合并）。

一句话结论：终审 I6 那一扇「丢掉 cookie 就能匿名读全校 60 人健康档案」的门**已经关上**——
泛型读改成三档（7 匿名 / 13 学生键自过滤 / 3 仅教职），匿名 GET 44 → **16**、
挂 security 的操作数 52 → **80**，而路径模板 71 / 操作 99 / GET 60 / securitySchemes 3
**四个数一个都没变**（本波只改「谁能读」，不加不删端点）。后端 **1339 passed**、
`app/domain/` 覆盖率四格 **1268/0/376/0/100%** 逐字不变、前端 `npm run build` 退出码 **0**
且产物大小逐字不变。

⚠️ 而 `npm run smoke` 的退出码是 **1**，**基线（`5218eb4`）上实测也是 1**——
详见第 ⑥ 节的顶回 8（那是第 14 步 3 条既有的 DOM 布局重叠红，与本波无关，
本波已用 `git stash` 在起点上跑过一次对照实测来证明这件事）。

---

## ① 环境与基线复现

硬规矩 #73：开工第一件事实测三个版本。

| 项 | 实测 | 派单给的 | 一致 |
|---|---|---|---|
| Node | **v24.19.0** | v24.19.0 | ✓ |
| npm | **11.17.0** | 11.17.0 | ✓ |
| FastAPI | **0.141.1** | 0.141.1 | ✓ |
| SQLAlchemy | **2.1.3** | 2.1.3 | ✓ |
| Python | 3.11.1（无 venv，`C:\Python`） | 3.11.1 | ✓ |

开工时的服务状态（`Get-NetTCPConnection -LocalPort 8000,5173 -State Listen`）：
`::1:5173`（PID 59924）与 `127.0.0.1:8000`（PID 50672）都在听；
`git status --short` 空、HEAD = `5218eb4` ✓

后端基线复现（改任何代码**之前**跑的）：

```
1333 passed, 1 warning in 135.07s (0:02:15)
```

`app.openapi()` 口径的基线（探针实测，不是 `len(app.routes)`）：

| 口径 | 实测 | 派单给的 |
|---|---|---|
| `Base.metadata.tables` | **26** | 26 ✓ |
| `/api/` 路径模板 | **71** | 71 ✓ |
| 操作 | **99** | 99 ✓ |
| 挂 `security` 的操作 | **52** | 52 ✓ |
| GET | **60** | 60 ✓ |
| 其中匿名 GET | **44** | 44 ✓ |
| `securitySchemes` | **3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | 3 ✓ |
| 全局 `security` | `None` | — |

`spec` 开工时实测（`read_bytes()`，不是编辑器显示的行数）：
**191 076 B / 1 526 行 / 1 525 CRLF / 无 BOM / sha256[:16] `00732A13CE0BE2C1`** ——
与派单给的**逐字一致** ✓

---

## ② 裁定 1 的实测清单

### ②.1 含 `student_id` 列的资源：**11 个**（不是「约 10 个」）

遍历 `catalog.RESOURCES` 的 23 行、对每个资源的 `model.__table__.columns` 与
`schemas.read.model_fields` **两侧都查**（运行时口径，硬规矩 #89）：

| # | 资源 | 表 | `student_id` 在列上 | 在 `*Read` 上 | 该表可空？ |
|---|---|---|---|---|---|
| 1 | `/api/enrollments` | `enrollment` | ✓ | ✓ | NOT NULL |
| 2 | `/api/fitness-test-results` | `fitness_test_result` | ✓ | ✓ | NOT NULL |
| 3 | `/api/body-compositions` | `body_composition` | ✓ | ✓ | NOT NULL |
| 4 | `/api/interest-surveys` | `interest_survey` | ✓ | ✓ | NOT NULL |
| 5 | `/api/derived-metrics` | `derived_metrics` | ✓ | ✓ | NOT NULL |
| 6 | `/api/stratification-results` | `stratification_result` | ✓ | ✓ | NOT NULL |
| 7 | `/api/prescriptions` | `prescription` | ✓ | ✓ | NOT NULL |
| 8 | `/api/rpe-records` | `rpe_record` | ✓ | ✓ | NOT NULL |
| 9 | `/api/training-logs` | `training_log` | ✓ | ✓ | NOT NULL |
| 10 | `/api/mini-tests` | `mini_test` | ✓ | ✓ | NOT NULL |
| 11 | `/api/alerts` | `alert` | ✓ | ✓ | ⚠️ **nullable=True** |

⚠️ 控制者预估的 10 个 + `enrollments` = **11**，与实测逐字对上 ✓
⚠️ `alert.student_id` **可空**是实测出来的（班级级预警 `YELLOW_CLASS_RPE_HIGH`
没有主人），它决定了两件事：list 的 `WHERE student_id = :me` 对 NULL 行天然不匹配
（SQL 三值逻辑，不需要额外写 `IS NOT NULL`），read-one 那一侧 `_owner_of_row`
把 NULL 折成 `NOT_STUDENT_OWNED` → `require_scope` 403。
⚠️ 这一格在真链路上有后果：`tests/api/test_end_to_end.py` 步骤 ⑤ 断言
`alerts` 的 `total == 3`（含 1 条班级级），改用**学生**头会变成 2，
故那一发必须用教职头（已写进注释）。

### ②.2 间接可达：**2 个**（派单只点了 1 个）

反向遍历 26 张表的外键、看哪一张能一跳到达「含 `student_id` 的表」：

```
weekly_adjustment  -> ['prescription']
notification       -> ['alert', 'prescription']
```

⚠️ 而 `notification` 的**真正**学生键不是那两个外键，而是 `recipient_id`
（多态：装的是 `student.id` 还是 `teacher.id` 由并排的 `recipient_kind` 决定）。
它**没有** `student_id` 列，故「含 `student_id` 列」这个谓词**会漏掉它** ——
那正是派单 §2 逐字警告「不要靠推断」的实证。

演示库只读实测（`mode=ro` 打开 `backend/pe_demo.db`，一个字节都没写）：

| 实测项 | 值 |
|---|---|
| `notification` 行数 | **19** |
| `recipient_kind` 分布 | **`[('student', 19)]`**（全部发给学生） |
| `NotificationRead` 含 | `title` **与** `body` |
| `body` 原文样例 | 「本周训练完成度 100%，而且二次小测有指标在进步。这一条已经记进你的电子勋章记录。」 |
| `Notification.RECIPIENT_KINDS` | **`{'student', 'teacher'}`** |
| `weekly_adjustment` 行数 | **13** |
| `reason` 实测取值 | `RED_RPE_SUSTAINED` / `RED_MINITEST_DROP`（**分层规则码**，不是自由文本） |
| `prescription` 行数 / `student` 行数 | **60 / 60** → `prescription.id` 与 `student.id` 一一对应 |
| `weekly_class_report.progress_board` 原文开头 | `{"top_n": 10, "top": [{"student_id": 10, "change_pct": 235.88}, {"student_id": 36, …` |

**判断**：

* `weekly-adjustments` → **收**。`prescription_id` 在演示库上就是一个学生代理键
  （60 张处方 / 60 人），而 `reason` 是分层规则码，合起来等于「全校谁被降了量、
  因为他是红层且 RPE 持续偏高」——与 `stratification_result` 的 `label` + `hit_rules`
  是同一类信息。⚠️ 代价：**前端没有一个页面读它**（实测 `views/**` 里
  `listWeeklyAdjustments` / `readWeeklyAdjustment` **零调用**），
  只有管理台的泛型 `listResource` 会走到，而管理员已登录 → 教职全读。
* `notifications` → **收**（多态键）。⚠️ 学生端**不**读泛型这一圈：
  `Notifications.vue` 走 `GET /api/students/{id}/notifications`（特例、学生头、
  服务端已过滤）；泛型这一圈的消费者只有管理台。
* `weekly-class-reports` → **收成 `staff`**（⚠️ 与派单「它是班级键」的暗示不同，见顶回 2）。
  `student_id` 埋在 `progress_board` 这个 **JSON 列里面**，SQL 层的 `WHERE` 够不着它
  （要做到就得把那一列拆成子表 = 一次 schema 改动，超出本波范围）；
  而它唯一的前端消费者是教师页 `views/teacher/ClassReport.vue`
  （`listWeeklyClassReports({limit:200})`，已在 `/t/*` 的路由守卫之后），
  学生端一个页面都不读它。
* `percentile-snapshots` → **不收**。实测 14 列全是群体统计
  （`semester_id` / `batch_id` / `item` / `sex` / `age_group` / 五个分位数 /
  `sample_size` / `source`），没有任何一格能落到一个人身上。
  ⚠️ 学生端的「班内百分位」读的是 `/api/mini-tests/normalized`，那是另一个端点。
* `fitness-test-batches` → **不收**（`semester_id` / `timepoint` / `test_date` /
  `source` / `academic_year`，逐人的成绩在 `fitness_test_result`，那一行已收）。
* `class-sessions` → **不收**（裁定 4 点名要复核的那一行）。三条依据：
  ① 键是 `course_section_id` / `session_date` / `period`，不含任何学生键；
  ② 它身上唯一的秘密 `rpe_token` **两侧都已摘掉**——read-one 走
  `response_model=ClassSessionRead`（那一列自 Plan 03 收尾小修波起不在模型上），
  list **不走** `response_model`，故 `RESOURCES` 那一行显式写了
  `"list_exclude": ("rpe_token",)`（实测 read-one 的字段集是
  `['batch_id','course_section_id','id','period','rpe_opened','session_date']`，
  **确实不含** `rpe_token`）；③ 剩下 5 列是「哪一节课什么时候上、快评开了没」，
  而学生端 `RpeEntry.vue` 正是要读它才知道该给哪节课交快评。

### ②.3 最终收紧清单与 `read_scope` 的 23 行声明

**13 个 `student_self` + 3 个 `staff` + 7 个 `None` = 23** ✓

| 资源 | `read_scope` | `student_owner` |
|---|---|---|
| `/api/enrollments` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/fitness-test-results` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/body-compositions` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/interest-surveys` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/derived-metrics` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/stratification-results` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/prescriptions` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/rpe-records` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/training-logs` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/mini-tests` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/alerts` | `student_self` | `StudentOwner(column="student_id")` |
| `/api/notifications` | `student_self` | `StudentOwner(column="recipient_id", kind=("recipient_kind","student"))` |
| `/api/weekly-adjustments` | `student_self` | `StudentOwner(column="prescription_id", via=("prescription","student_id"))` |
| `/api/students` | `staff` | —（改前是 `read_requires_staff: True`，行为逐字不变） |
| `/api/teachers` | `staff` | —（同上） |
| `/api/weekly-class-reports` | `staff` | — |
| `/api/semesters` | `None` | — |
| `/api/course-sections` | `None` | — |
| `/api/fitness-test-batches` | `None` | — |
| `/api/percentile-snapshots` | `None` | — |
| `/api/exercises` | `None` | — |
| `/api/prescription-templates` | `None` | — |
| `/api/class-sessions` | `None` | — |

⚠️ **`read_requires_staff` 被删掉了**（不是与 `read_scope` 并存）：
`"staff"` 与 `read_requires_staff=True` 行为逐字相同（同一个
`_require_staff_identity`、同一个 `Security(TEACHER_STAFF_NO_SCHEME)`），
留两个开关就是两个所有者，而下一个人会问「两个都写会怎样」。

⚠️ **单一判据**：`StudentOwner` 是「哪一列是学生键」的**唯一**声明，
`_owner_filter`（list 的 `WHERE`）与 `_owner_of_row`（read-one 的取值）都只读它，
故「list 放行了而 read-one 挡住」这类分叉在结构上不可能发生。
read-one 的 403 **整个交给** `require_scope`，`crud.py` 里一行
`raise HTTPException(403)` 都没有（派单 §2 第 3 条「不要写第二份过滤逻辑」）。
⚠️ 多态键的「这行不属于任何学生」折成 `NOT_STUDENT_OWNED = -1`
（`student.id` 是 SQLite 的 rowid 别名、恒 >= 1，故它不可能撞上任何在册学生），
于是判定仍然可以整个交给 `require_scope`。

⚠️ **工厂加了第 9/10/11 道导入期校验**：`student_owner` 在 `student_self` 档**必填**
（`StudentOwner.column` 有缺省值 `"student_id"`，「忘了写」在 11 个直接键资源上会
**恰好**是对的，而在 `notifications` / `weekly-adjustments` 上会静默地去过滤一个
不存在的列）、在非该档**必须省略**、列名与中间表**必须真的存在**
（写错一个列名是 `import app.api.routers.catalog` 当场 `ValueError`、
`uvicorn` 起不来，而不是运行时 500 或「过滤条件恒假 → 学生看到空列表」）。

---

## ③ 三档读权限的实测矩阵

### ③.1 真 HTTP（生产档：`PE_ALLOW_HEADER_IDENTITY` 未设 = 只认 `pe_session` cookie）

后端由 `backend\scripts\demo.ps1 -Port 8000` 重启（它自带两道禁区守卫、
删旧演示库重灌、并打印演示口令与管理员工号）。
四个会话都是**真的登录**换来的 cookie：学生 #4 赵锦程（`2023120001`）、
学生 #5 赵婉清（`2024090001`）、教师 `T0001`、管理员 `T0003`。
探针 `mode=ro` 只读、跑完删掉、放 `$env:TEMP`（不在仓库里）。

`A.total` = 学生 #4 会话读 list 拿到的 `total`；`staff.total` = 教师会话读到的 `total`
（= 全表行数，因为教职那一档是全读）；`ownOne` / `otherOne` = read-one
自己的行 / **别人的**行（那一行的 id 是从教师的全读结果里挑「不在 A 的 items 里」的第一个）。

| 资源 | 匿名 list | 匿名 read-one | A.total | A.items | **otherOne** | staff.total | 教师 list | 管理员 list |
|---|---|---|---|---|---|---|---|---|
| `enrollments` | **401** | **401** | 2 | 2 | **403** | 120 | 200 | 200 |
| `fitness-test-results` | **401** | **401** | 4 | 4 | **403** | 240 | 200 | 200 |
| `body-compositions` | **401** | **401** | 4 | 4 | **403** | 240 | 200 | 200 |
| `interest-surveys` | **401** | **401** | 2 | 2 | **403** | 120 | 200 | 200 |
| `derived-metrics` | **401** | **401** | 2 | 2 | **403** | 120 | 200 | 200 |
| `stratification-results` | **401** | **401** | 2 | 2 | **403** | 120 | 200 | 200 |
| `prescriptions` | **401** | **401** | 1 | 1 | **403** | 60 | 200 | 200 |
| `weekly-adjustments` | **401** | **401** | **0** | 0 | **403** | 13 | 200 | 200 |
| `rpe-records` | **401** | **401** | 4 | 4 | **403** | 240 | 200 | 200 |
| `training-logs` | **401** | **401** | **14** | 14 | **403** | **840** | 200 | 200 |
| `mini-tests` | **401** | **401** | 3 | 3 | **403** | 180 | 200 | 200 |
| `alerts` | **401** | **401** | **1** | 1 | **403** | **32** | 200 | 200 |
| `notifications` | **401** | **401** | 1 | 1 | **403** | 19 | 200 | 200 |
| `students` | **401** | — | 学生 **403** | — | — | 60 | 200 | 200 |
| `teachers` | **401** | — | 学生 **403** | — | — | 3 | 200 | 200 |
| `weekly-class-reports` | **401** | — | 学生 **403** | — | — | 5 | 200 | 200 |
| `semesters` | 200 | — | — | — | — | 2 | — | — |
| `course-sections` | 200 | — | — | — | — | 5 | — | — |
| `fitness-test-batches` | 200 | — | — | — | — | 4 | — | — |
| `percentile-snapshots` | 200 | — | — | — | — | 24 | — | — |
| `exercises` | 200 | — | — | — | — | **0** | — | — |
| `prescription-templates` | 200 | — | — | — | — | **0** | — | — |
| `class-sessions` | 200 | — | — | — | — | 8 | — | — |

**探针自报 `failures = 0`**（每一格都与期望逐字相符）。

⚠️ 三个承重的读数：

* `training-logs` 的 `total` 从 **840 → 14**（学生 #4 自己的 14 天打卡）：
  这一格同时证明「过滤在 SQL 层」与「`total` 与 `items` 走同一个 `WHERE`」。
  若实现是「拉全量再在 Python 里筛」，`total` 会仍是 840，
  而前端分页器会显示一个翻不到的页数。
* `alerts` 的 `total` 从 **32 → 1**：那 32 条里有班级级的（`student_id` 为 NULL），
  **无主的行不给学生** —— 这是可空键那一档的直接后果。
* `weekly-adjustments` 的 `A.total == 0` 而 `otherOne == 403`：
  学生 #4 今天没有微调行，但**间接键**（`prescription_id` → `prescription.student_id`）
  的 read-one 判定仍然正确地拒了他读别人的行。

⚠️ `exercises` 与 `prescription-templates` 的 `total == 0`：演示库上这两张表是**空的**
（`demo_bootstrap.py` 不灌参考数据）。⚠️ 与本波无关（两行都是 `read_scope: None`、
匿名 200），已登记为待清扫/关切。

### ③.2 pytest（过渡通道：`tests/conftest.py` 把 `PE_ALLOW_HEADER_IDENTITY` 设成 `"1"`）

新守卫 `test_the_student_keyed_resources_admit_three_read_tiers`：
16 个非匿名资源 × 两个 GET × 五档身份，**逐个实发请求**。

| 档 | 断言 | 发数 |
|---|---|---|
| ① 匿名 | list 与 read-one 都 **401 `unauthenticated`** | 16 × 2 = **32** |
| ② 学生自己 | list **200** 且 `total == 1` 且 `items` 的 id 清单 == `[seeded 那一行]` | 13 |
| ③ 学生别人 | list **200** 且 `total == 0` 且 `items == []`；read-one **403 `forbidden`** | 13 × 2 |
| ②′ staff 档的学生 | **401**（⚠️ 不是 403，见顶回 3）+ 教师会话 **200** | 3 × 2 |
| ④⑤ 教职全读 | 普通教师与管理员各自 list **200** 且 `total == 1`、read-one **200** | 13 × 2 × 2 |

⚠️ ③ 那一档刻意用**另一个在册学生**（守卫自己插一行 `student_no='S2025777'`）
而不是一个编造的 id：`require_scope` 有两支（不是本人 / 不在册），
一个编造的 id 只会走到第二支，于是「第一支被写反」是绿的。

⚠️ 多态键那一档另有专条 `test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student`：
它造一行 `recipient_kind='teacher'` 而 `recipient_id` **恰好等于那个学生的 id** 的通知
（最刁钻的反例：少了 `StudentOwner.kind` 那一格，它会**正好**落进学生的自过滤里），
断三拍——学生 read-one **403** / 学生的 list 里不含它（而发给学生的 `seeded` 那一行照旧在、
`total == 1`）/ 教职 read-one **200**（绿档同时在场）。

---

## ④ `password_bound_at` 的摘除

### ④.1 谁在读它（派单要求「先实测有没有谁真的在读它」）

全仓 grep `password_bound_at`（49 处命中），**生产代码里的消费者是 0 个**：

| 位置 | 是不是消费者 | 处置 |
|---|---|---|
| `frontend/src/**` | ⚠️ **只有 `api/generated/schema.d.ts`**（codegen 产物） | 重跑 `gen:api` 自动同步 |
| `frontend/src/api/types.ts` | **没有**（23 个 list 类型是 `= S['*Read']` 的**别名**，不是手写字段集） | 只改注释里的数字（见顶回 6） |
| `frontend/src/catalog/resources.ts` 的 `displayFields` | ⚠️ **没有它**（派单担心的那一格不成立） | 无需改 |
| `frontend/src/present.ts` | **没有** | 无需改 |
| `frontend/scripts/smoke.mjs` | ✅ **2 处**：第 0 步的 `unbound` 过滤、第 16 步 ① 的 `eq(... , null)` | 两处都改（见 ⑤） |
| `backend/app/api/schemas/organisation.py` | ✅ 两个 `*Read` 各一格 | **摘列** |
| `backend/app/api/routers/catalog.py` | ✅ 两行的 `list_exclude` | **各加一格** |
| `backend/app/api/routers/auth.py:123` | 写入侧（`bind` 端点 `.values(...)`） | **不动**（它就是要写这一列） |
| `backend/scripts/demo_bootstrap.py:451,454` | 写入侧（灌演示库时绑定） | **不动** |
| `backend/app/db/models/organisation.py:106,132` | **DB 列** | **不动**（列还在，只是不暴露） |
| `backend/tests/api/test_auth_api.py:971-973` | ✅ 断言它**在**响应体里 | **反转**成断言它不在 |
| `backend/tests/api/test_crud.py:1753-1754` | 档 1 清单（`*Create`/`*Update` 不含它） | **不动**（那一档本来就对） |

### ④.2 四处缺一不可（照 fix 波 2 处理 `rpe_token` 的形状）

1. **读模型摘列**：`StudentRead`（9 列暴露 8 → **7**：`id, student_no, name, sex, birth,
   department, grade`）、`TeacherRead`（6 列暴露 5 → **4**：`id, staff_no, name, role`）。
   两个数都是 `python -c` 实读的 `model_fields`，不是数出来的。
2. **`catalog.RESOURCES` 两行的 `list_exclude`**：`("password_hash",)` →
   `("password_hash", "password_bound_at")`。
   ⚠️ 这一半**必须**改：泛型 list **不走** `response_model`
   （它显式只 SELECT `kept` 那些列、手工拼 dict），只摘读模型堵不住 list ——
   那正是 Plan 03 收尾小修波给 `rpe_token` 补第二半时逐字记下的失效形态。
3. **档 2 清单 `_SERVER_GENERATED_HIDDEN_COLUMNS`**：3 格 → **5 格**。
   ⚠️ 两个数**分开钉**：`len(...) == 3`（几个资源有例外，不变）与
   `sum(len(v)) == 3 → 5`（几列被摘）。少了后者，「给一个资源摘第二列」是静默的。
   逐格点名的那份字面清单也扩成 5 项。
4. **三拍守卫**：`test_password_bound_at_is_absent_from_both_the_read_model_and_the_list`
   ——① read-one 不含（`.json()` 与 `.text` 两侧都断）② list 不含
   （整份响应体原文 + 逐 item）③ **绿档**：两个端点仍 200 且其余各列都在
   （学生 **7** 列 / 教师 **4** 列，且 list 的键集合 == read-one 的键集合）。

⚠️ 而「这一列**今天还在 DB 上**、只是不暴露」由既有的
`test_every_read_schema_covers_exactly_the_model_columns` 钉住（它**反向**也钉：
档 2 清单里点名的列必须①真的是该表的一列、②真的**不在**读模型上）。
⚠️ 「`*Create` / `*Update` 也不含它」由档 1 清单（`_SERVER_FILLED_COLUMNS`）钉住，未动。

### ④.3 代价（硬规矩 #39，如实记）

管理台从此看不到「谁还没注册」这一列。而那一格**没有任何前端消费者**（见 ④.1），
且「某个具体的人绑没绑」仍由 `POST /api/auth/login` 的
403 `password_not_bound` vs 401 `invalid_credentials` **逐人**给出。
⚠️ 于是 §1.2 第 3 条那一档泄漏**不变**，变的是「一次 list 就能批量数出全部」
这个能力被拿走了 —— 即 §1.2 第 4 条那条已知局限从「可批量枚举 + 可抢占」
窄化成「可逐个探测 + 可抢占」，**本条不撤销**（抢占本身仍然可能，绑定端点没变）。

---

## ⑤ 连带

### ⑤.1 后端计数

| 口径 | 改前 | 改后 | 备注 |
|---|---|---|---|
| 挂 `security` 的操作 | **52** | **80** | +28 = 13 × 2 学生键读 + 1 × 2 周报读 |
| GET | 60 | **60** | 不变 |
| 其中**匿名 GET** | **44** | **16** | −28 |
| 挂 `security` 的 GET | 16 | **44** | +28 |
| `/api/` 路径模板 | 71 | **71** | 不变（不加不删端点） |
| 操作 | 99 | **99** | 不变 |
| `securitySchemes` | 3 | **3** | 不变（**没有**新增第四个） |
| CRUD 那一圈的操作数 | 77 | **77** | 不变（那 28 个 GET 本来就在里面，只是从「不带」翻成「带」） |
| `Base.metadata.tables` | 26 | **26** | 不变 |
| 架构守卫扫描面 | 66 | **66** | 不变（`test_production_layers_never_import_app_seed`：pipeline 10 + db 12 + domain 18 + api 23 + auth 3；本波一个新 `.py` 文件都没加） |

⚠️ `student_self` 那一档的两个 GET 各挂**两个** scheme
（`[{"X-Student-Id":[]},{"X-Teacher-Staff-No":[]}]`，OpenAPI 的数组是 **OR** 语义），
因为三档里学生与教职都能过。⚠️ 它**刻意不声明** `pe_session`：
本仓既有口径是「泛型端点一律声明请求头 scheme，cookie 那一格只由
`/api/auth/me` 与 `/api/auth/logout` 声明」，而 `current_reader` **同样**认 cookie。

⚠️ 全仓级断言 `test_the_identity_schemes_are_registered_as_openapi_security_schemes`
按 #88 先跑全量收红、再改写：`len(all_security) == 52` → **80**、
`len(expected_crud_security) == 30` → **56**（= 9 POST + 9 PATCH + 8 DELETE
+ 6 仅教职读 + 24 学生键读），docstring 里写明了口径为什么又变。
⚠️ 新增 `student_self_reads` 的 **26 项字面清单**（硬规矩 #35，不从 `RESOURCES` 反推），
并按**全集口径**逐个断言 scheme 形状 —— 因为 `/api/rpe-records` 与 `/api/training-logs`
两个**集合路径**被 `crud` 的「按 path 整条排除」吃掉了（它们的 `post` 在 `expected` 里），
少了全集那一拍这两个 GET 就**谁也没钉**。

### ⑤.2 `anonymous == 21` → **7**（⚠️ 它不在 `smoke.mjs`，见顶回 4）

`backend/tests/api/test_crud.py::test_all_twenty_three_resources_are_listable`：
判据从 `spec.get("read_requires_staff", False)` 换成 `spec["read_scope"] is not None`，
`anonymous == 21` → **`anonymous == 7`**，并保留了「反假绿：匿名那一档**真的**没带头」
那一拍。⚠️ 一律带**教职**头（而不是「学生键资源带学生头」）：本条钉的是
「路由挂上了、数得到 `seeded` 那一行」，而教职那一档是全读，故 23 行可以用同一个身份跑完。

`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
的判据同样换成 `read_scope is not None`（16 行带头、7 行不带），
并写明「带教职头而不是学生头」的理由（带学生头的话 `seeded` 那一行的所有者未必是它，
`items` 可能是空的 → 本条空转全绿）。

`test_the_scope_hook_rejects_a_mismatched_identity_with_403` 的 ② 那一拍
**前提被推翻了**（它此前拿 `/api/training-logs/{id}` 当「不要求身份」的例子，
而那一行今天是 `student_self`、匿名 401）→ 改成再建一个**合成的**匿名路由
（同一个模型、同一行、差别只有那个钩子），于是对比仍然是干净的。
③ 那一拍的判据从「只有探针有那两个请求头」改成「**7 个匿名参考数据资源一个都没有**」
（本波把「要身份的路由」从 1 个抬到 27 个，那些端点上出现这两个头是**对的**）。

### ⑤.3 `smoke.mjs`

| 改动 | 位置 |
|---|---|
| 挂 security `52` → **`80`**、匿名 GET `44` → **`16`** | 第 12 步 |
| **新加第 ⑥ 拍**：13 个学生键资源 × 集合/成员 = **26 发匿名请求**逐个断 401 + `unauthenticated`，每个资源再补一发教师会话的 200（绿档同时在场）；步数标题「5 拍」→「**6 拍**」 | 第 12 步 |
| 第 12 步的断言数 22 → **102** | — |
| 8 张表的行数核实里 **6 个**从匿名改成 `as: 'teacher'`（`notifications` / `prescriptions` / `training-logs` / `rpe-records` / `weekly-class-reports` / `alerts`）；`totalOf` 的注释写明「一律用教职 jar，否则 `total` 会变成『我的行数』」 | 第 0 步 |
| 「人人能登录」那一拍**换姿势**：从「读 `password_bound_at` 数谁没绑」改成「**真的登录**三个演示学号（`2023120001` / `2024090001` / `2025060001`）」——它证明的是「能登录」本身，比读一个时间戳**更强** | 第 0 步 |
| 4 处匿名读改成 `as: 'teacher'`（`alerts` ×3、`enrollments` ×1），每处写明漏掉它的失效形态 | 第 0 / 7 / 8 / 9 步 |
| `eq('password_bound_at 是 null')` 反成 `check('响应里没有 password_bound_at')`；⚠️ 而下面 ② 那一拍（未绑定就登录 → 403 `password_not_bound`）**照样能证明「还没绑定」** | 第 16 步 ① |
| 断言总数 408 → **490**（487 绿 + 3 既有红） | — |

### ⑤.4 `gen:api` 重跑的 diff 规模与三项核实

派单纪律：改了会进 openapi 的 docstring / security 声明就要重跑 `npm run gen:api`。

```
before  400 986 B /  8 848 行 / sha256[:16] 189D68CF04A67354
after   404 216 B /  9 023 行 / sha256[:16] 2720DBFCD6E3134F
git diff --numstat  →  +247 / −72（319 行变动）
```

三项核实：

1. **`npm run build` 退出码 `0`**，产物大小**逐字不变**：
   `dist/assets/index-Db3TVHCJ.css 61.02 kB │ gzip: 8.89 kB`、
   `dist/assets/index-UryyTQo3.js 165.70 kB │ gzip: 58.02 kB`
   （两个 hash 与基线逐字相同 → 运行时字节没变，改的只有 `.d.ts` 与注释）。
2. **那 24 个未定型响应仍逐字未定型**：`smoke.mjs` 第 12 步第 ⑤ 拍
   （23 个 list + `/api/health` 全部 `type: object` + `additionalProperties: true`）
   **全绿**，整步 **102/102**。
3. **第 12 步第 ⑤ 拍仍绿** ✓（同上；`check('⑤ 没有一个 list 端点是定型的')` 也绿）。

⚠️ `check:tokens` 绿（扫描面 **32** 个文件 / 下界 25，`tokens.css` 之外一个色值字面量都没有）、
`check:dist` 绿（生产构建里 `adoptFromUrl` 出现 **0** 次，而源码里它确实存在 → 谓词不是空的）。

### ⑤.5 前端改了哪几个文件（**3 个**）

| 文件 | 改了什么 |
|---|---|
| `frontend/scripts/smoke.mjs` | 见 ⑤.3 |
| `frontend/src/api/types.ts` | **只改注释**：`TeacherListItem` 的「`TeacherRead` 的 **3** 个字段」实测校正成 **4**（Plan 05A 加了 `role` 与两个凭据列之后就没跟上）；`StudentListItem` 的「7 个字段」摘列后**恰好回到 7**、数字不用改。⚠️ 类型定义一行都没动：23 个 list 类型一律是 `= S['*Read']` 的**别名**，故摘列**自动**传导（见顶回 6） |
| `frontend/src/api/generated/schema.d.ts` | `npm run gen:api` 的产物（见 ⑤.4） |

⚠️ **一个 `.vue` / `.css` / `present.ts` / `tokens.css` 都没改** ——
这是第 ⑥ 节顶回 8（第 14 步那 3 条 DOM 布局重叠红与本波无关）的结构性依据。

⚠️ `IdentitySwitcher.vue` **一行都没改**，理由见顶回 5。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### ⑥.1 顶回控制者的地方（**10 处**）

**顶回 1 —— 裁定 1 的清单漏了 `notifications`（多态键），最终收紧 13 个而不是 11 个。**
派单预估「约 10 个 + `enrollments`」= 11，与「含 `student_id` 列」的实测逐字对上；
但实测另外查出 **2 个不是那个谓词能挑出来的**：`notifications`
（`recipient_id` + `recipient_kind`，演示库 19 行**全部**发给学生、
`NotificationRead` 含 `title` **与** `body`）与 `weekly-adjustments`
（`prescription_id` → `prescription.student_id`，而 60 张处方 / 60 人 →
`prescription_id` 就是学生代理键）。⚠️ 派单 §2 自己逐字警告过
「不要靠『字段里有 `student_id` 就自动收紧』的推断……会漏掉 `enrollments` 这种双键的」
——`notifications` 正是同一个警告的**第二个**实证，而它比 `enrollments` 更隐蔽
（`enrollments` 至少真的有 `student_id` 列）。故新守卫
`test_every_student_keyed_resource_declares_a_non_null_read_scope` **只覆盖 11 行**，
另 2 行由 `test_the_read_scope_tiers_are_pinned_to_those_seven_thirteen_and_three`
的字面名单兜住，两条各钉一半。

**顶回 2 —— `weekly-class-reports` 我收了（收成 `staff`），而派单把它列在
「这几个是班级/处方键而不是学生键」那一组里。**
派单要求「逐个判断它们是否间接暴露学生级数据」，实测答案是**是**：
`progress_board` 那个 JSON 列里**逐条带 `student_id` + `change_pct`**
（原文开头逐字 `{"top_n": 10, "top": [{"student_id": 10, "change_pct": 235.88}, …]}`，
即「本周进步榜 top 10」）。⚠️ 但我**没有**把它收成 `student_self`：
`student_id` 埋在 JSON 列**里面**，SQL 层的 `WHERE` 够不着它（要做到就得拆子表 =
一次 schema 改动）。收成 `staff` 的代价是「一个学生从此读不到自己班的周报（403 跨 kind）」，
而实测学生端**一个页面都不读它**（唯一消费者是教师页 `ClassReport.vue`，
已在 `/t/*` 的路由守卫之后），故不破坏任何既有页面。

**顶回 3 —— 裁定 2 那张表里「学生会话 → 403」这一格，在 `staff` 档上实测是 401。**
派单的表只给了 `student_self` 档的 403（那一格实测成立 ✓）。
而 `staff` 档（`students` / `teachers` / `weekly-class-reports`）在**请求头通道**下
带 `X-Student-Id` 打过去实测是 **401 `unauthenticated`**：`current_teacher` 只认 cookie 与
`X-Teacher-Staff-No`，一个学生头对它而言就是「没有教师身份」。
只有 **cookie 通道**下（生产档）才是 403（跨 kind）。⚠️ 两档都**拒绝**，
差别只是「我不知道你是谁」与「我知道你是谁、但你不是教职」。
⚠️ 顺带查出一处**既有的假话**：`_require_staff_identity` 的 docstring 此前逐字写着
守卫是「三拍：匿名 401 / **学生会话 403** / 教师与管理员 200」，
而 `test_the_two_roster_resources_admit_only_staff_reads` 实际测的是
「**不在册的工号** 403」。已按实际改写（那一格在 Plan 05A 就写错了，不是本波造成的）。

**顶回 4 —— `anonymous == 21` 那一拍不在 `smoke.mjs`，在 `backend/tests/api/test_crud.py:969`。**
派单裁定 5 逐字写的是「**`smoke.mjs` 第 12 步**有一拍是 05A 加的 `anonymous == 21`」。
实测：`smoke.mjs` 全文 grep `anonymous` / `21` 都**没有**那一拍
（第 12 步钉的是 `getsAnon == 44`，变量名叫 `getsAnon`）；
`anonymous == 21` 逐字住在 `tests/api/test_crud.py` 的
`test_all_twenty_three_resources_are_listable`。⚠️ 两处我都改了
（后端 `21 → 7`；`smoke.mjs` 第 12 步 `44 → 16`、`52 → 80`，并按裁定 5 新加第 ⑥ 拍），
故裁定的**意图**完整落地了，只是位置与派单说的不同。

**顶回 5 —— 裁定 5 担心的 `IdentitySwitcher` 那一格，实测已经在 Plan 05A Task 5 改过了。**
派单说「`IdentitySwitcher` 的 DEV-only 名册加载在收紧后匿名会 401 →
请实测它在『DEV + 头通道』下是否仍工作；若它其实走 cookie 通道，则要改成
『先登录再拉名册』或降级」。实测 `frontend/src/components/IdentitySwitcher.vue:150`
逐字是 `if (!IS_DEV || !session.isStaff) return`，且第 146 行的注释逐字写着
「⚠️ **Plan 05A Task 5 之后 `GET /api/students` 与 `GET /api/teachers` 要教职身份**」
——即它**已经是**「先登录成教职再拉名册」，而且它走的是 **cookie 通道**
（`client.ts` 的 `credentials`），不是头通道（`PE_ALLOW_HEADER_IDENTITY` 在生产档是 `0`）。
⚠️ 而 `students` / `teachers` 两行的档位本波**没有变**
（`read_requires_staff: True` → `read_scope: "staff"`，行为逐字相同）。
故**一行都没改**，也不需要改。

**顶回 6 —— `types.ts` 的 23 个 list 类型不是「手写字段集」，是 `= S['*Read']` 的别名。**
派单裁定 5 说「学生与教师那两个 list 类型的字段集要同步（它们的口径是
『`*Read` 减去生效的排除集』）」。实测 `frontend/src/api/types.ts:167,170` 逐字是
`export type TeacherListItem = S['TeacherRead']` 与
`export type StudentListItem = S['StudentRead']` ——**别名**，不是手写字段集。
故摘列之后重跑 `gen:api` 就**自动**同步了，「同步」不是一个要人记得做的动作。
⚠️ 要改的只有注释里那个**数字**，而它是**陈旧的**：`TeacherListItem` 的注释
逐字写着「**3** 个字段」，实测摘列前是 5、摘列后是 **4**
（Plan 05A 给 `teacher` 加了 `role` 与两个凭据列之后就没跟上）；
`StudentListItem` 的注释写着「**7** 个字段」，实测摘列前是 8、摘列后**恰好回到 7**。
两个都已按实测校正（并把「无排除」与后端 `list_exclude` 的关系写清楚）。

**顶回 7 —— §1.2 的 12 条已知局限表里没有「44 个匿名 GET 放行化名健康档案」那一条。**
派单裁定 6 说「§1.2 的 12 条已知局限表里那条……要改写成收紧后的口径」。
实测（grep 全文 `健康档案` / `化名` / `I6` / `44 个匿名`）：**§1.2 的 12 条里没有那一条**。
唯一相关的是第 4 条（绑定用的验身材料是弱材料），而它说的是
「Plan 05A Task 5 **之前**它们匿名可读」——一句**历史叙述**，不是 I6 那一格。
故我没有「改写」它，而是：① 在第 4 条末尾补了 `password_bound_at` 摘除的影响
（「可批量枚举 + 可抢占」→「可逐个探测 + 可抢占」，本条**不撤销**）；
② **新增第 13 条**（教师任教范围闸门不扩到泛型读 —— 派单要求保留的那一条）；
③ **新增第 14 条**（`GET /api/mini-tests/normalized` 仍匿名且回学生键数据）。
⚠️ 于是那张表从 12 条变成 **14 条**。

**顶回 8 —— 派单给的前端基线「`smoke.mjs` 18 步 / 408 断言 / 退出码 0」里，
「退出码 0」不成立；实测基线就是 17/18 步全绿、405 绿 + 3 红 = 408 断言、退出码 1。**
⚠️ 这一格我做了**对照实测**而不是推断：`git stash push` 全部 13 个改动 →
工作树回到 `5218eb4` → 停后端 → `demo.ps1` 重灌干净演示库（旧代码）→
`npm run smoke`。结果逐字是：

```
步数 17/18 全绿 · 断言 405 绿 / 3 红
红  第 14 步 · 15 条路由的无头浏览器 DOM 取证 · 106/109 条断言
BASELINE_SMOKE_EXIT=1
```

那 3 条红与本波跑出来的**逐字相同**（同样的 `aRect` / `bRect` / `ratio`）：

| 页 | 重叠的两个文本节点 | ratio |
|---|---|---|
| `s-home` | `span「本周训练量 · 分钟」` × `span「108.0」`（`bRect` 高 **71**px） | **0.342** |
| `s-weekly-sheet` | `span「06」…「12」` × `span「速度柔韧」`/`span「休息」`（**7 处**） | **0.218** |
| `s-check-in` | `span「本周打卡完成率」` × `span「100.0」`（`bRect` 高 **71**px） | **0.342** |

⚠️ 阈值是 `worst <= 0.2` 跳过（`smoke.mjs:1547`），故 0.218 与 0.342 都报。
⚠️ **结构性依据**：本波**一个 `.vue` / `.css` / `present.ts` / `tokens.css` 都没改**
（`git status` 只有 13 个文件：10 个后端 + `smoke.mjs` + `types.ts` + `schema.d.ts`，
后两个都是纯类型 / 注释，编译后被擦掉），而那 3 页的数据全部来自
**特例端点**（`getStudentHome` / `getCompletionRate` / `getWeeklySheet`，本波一个都没动）。
⚠️ 我还排除了两个替代解释：① **vite dev server 陈旧**——已停掉 PID 59924、
重起一个新的，重跑后 3 条红的几何数据**逐字相同**；② **库状态不同**——
两次都是 `demo.ps1` 刚重灌的干净库。
⚠️ 处置：**不修**（它是 Plan 05B 视觉重构 / 清扫波的遗留，属布局层，
修它会牵动 `.vue` 与 `.css`，而那正是本波刻意不碰的面），登记为待清扫第 6 条。
⚠️ 于是「`smoke.mjs` 必须仍 18 步全绿」这一条验收项**在基线上就不成立**，
本波做到的是「**红的条数与逐字内容都不变**（3 条），绿的从 405 涨到 **487**」。

**顶回 9 —— §13.4.4 里有一句假话，本波一并改对。**
原文逐字是「⚠️ 而『大屏匿名可读』那一档**没有被推翻**：大屏读的是
`/api/dashboard/*`（仍然匿名），不是名册」。实测：匿名
`GET /api/dashboard/class/1?week=6&as_of=2025-10-12` → **401**
（`dashboard` 那 6 个端点自 Plan 03 Task 8 起就各自挂着 `Security(...)`）。
⚠️ 终审 I3 已经在 `crud.py` 的 `_require_staff_identity` 里改对了这一句
（并逐字写明「它写下来的当天就是假的，不是后来才过期的」），
而 **spec 这一份漏了**。本波改写 §13.4.4 时一并补上。

**顶回 10 —— 裁定 2 的实现要点里「`require_scope` 今天读 `X-Student-Id`，
本波之后它应当优先读会话」这个前提不成立，故本波没有改造它。**
派单 §2 末条逐字写的是「⚠️ `require_scope` 今天是怎么取学生身份的，请实测并复用同一个来源
（它在 Plan 03 Task 1 建的，读 `X-Student-Id`；本波之后它应当**优先读会话**，
与 `current_student` 的双通道一致）」。实测
`def require_scope(session: Session, student_id: int, requester_id: int) -> None`
——**两个入参都是 `int`，它自己不取身份**；「优先读会话还是优先读请求头」
这件事住在调用方的身份依赖里。而 `current_student` 自 Plan 05A 起**已经是**
「先看 `pe_session` cookie，没有才在 `PE_ALLOW_HEADER_IDENTITY=1` 时回落 `X-Student-Id`；
生产缺省 `0` 下请求头被完全忽略」。⚠️ 故**无需改造**，本波做的是：
① 新依赖 `current_reader` **复用同一个双通道口径**（一次解析、就地分三档）；
② 把 `require_scope` docstring 里那句过期的「（即 `X-Student-Id`）」改成
「本函数自己不取身份 + 今天两个调用方各用哪个依赖」，于是它不会再因为多一个调用方而过期。
⚠️ 这也回答了派单 §4 点名的第 ③ 处可能顶回：「若这会破坏 1333 条测试里的某些假设，
顶回来」——**它不会**，因为我根本没改它的行为，只改了它的 docstring。

### ⑥.2 关切（如实记，硬规矩 #39）

1. **`GET /api/mini-tests/normalized` 是一扇还没关的门**（派单裁定 2 明写特例端点本波不动，
   而它**恰好**是「实测是匿名的且返回学生键数据」的那一档，故按派单要求顶回来）。
   它匿名回 `entries[].student_id` + `squat_score` / `shuttle_score` / `composite`
   （外加 `unassigned[].student_id`）。⚠️ Plan 04 Task 3 摘掉它的教师头时，
   论证是「它不新增泄漏面：每一格都是匿名 `GET /api/mini-tests` + 匿名
   `GET /api/enrollments` 已经给出去的东西的纯函数」——
   ⚠️ **那个前提被本波推翻了**（那两个端点今天都要身份），
   于是它成了**唯一**一个匿名给出 `student_id` + 三个分数的入口。
   ⚠️ 收它的难点：学生端 `MiniTest.vue` 要的是**全班**的 entries（否则算不出班内百分位），
   故收不成 `student_self`；收成 `staff` 会让那一页降级成「拿不到班内百分位」
   （那页今天已有 `normalizedError` 那条降级路径，故技术上可行）。
   已写进 spec §1.2 第 14 条与 §13.4.4。
2. **`weekly_class_report.progress_board` 里的 `student_id` 埋在 JSON 列里**，
   SQL 层够不着 → 本波只能收成 `staff`（学生一个都读不到），
   而不是「学生只读自己班的」。要真正做到得把那一列拆成子表（一次 schema 改动）。
3. **`_require_staff_identity` 那一档的「学生会话」没有守卫**：
   `test_the_two_roster_resources_admit_only_staff_reads` 测的是「不在册的工号 403」，
   而 cookie 通道下「学生 cookie 打 staff 档 → 403」这一档**今天没有任何测试覆盖**
   （本波的新守卫走请求头通道，量到的是 401）。已登记为待清扫第 4 条。
4. **`exercises` 与 `prescription-templates` 两张表在演示库上是空的**（`total == 0`）。
   与本波无关（两行都是 `read_scope: None`、匿名 200），但演示时
   「动作库」与「模板库」两个管理台页面会是空表。已登记为待清扫第 7 条。
5. **`require_staff` 与 `_teacher_id_of` 的两次点查**（Plan 05A 自己登记的待清扫）：
   本波让 `current_reader` 在请求头通道下也调 `require_staff`，
   于是「教职那一档」在过渡通道下多一次 `teacher` 表点查。
   ⚠️ 生产档（只认 cookie）下**不走**这一支，故对生产无影响。

### ⑥.3 待清扫（**9 条**）

| # | 条 | 出处 |
|---|---|---|
| 1 | `GET /api/mini-tests/normalized` 仍匿名且回学生键数据；收它要先裁定「班内百分位该由谁给」 | 关切 1 / spec §1.2 第 14 条 |
| 2 | `weekly_class_report.progress_board` 的 `student_id` 埋在 JSON 列里，要按学生收窄得拆子表 | 关切 2 |
| 3 | 「一个**新的**多态/间接学生键资源被加成匿名」仍然只能靠人：新守卫只覆盖含 `student_id` 列的 11 行，另 2 行靠字面名单。要机器化就得给 `StudentOwner` 加一条「反向遍历全部外键、看能不能一跳到达 `student`」的探测 —— 而那正是派单点名不要的「推断」 | 顶回 1 |
| 4 | cookie 通道下「学生 cookie 打 `staff` 档 → 403」这一档没有任何测试覆盖 | 关切 3 |
| 5 | `require_staff` 与 `_teacher_id_of` 的两次点查收敛成一次（Plan 05A 登记的，本波未做） | 关切 5 |
| 6 | **`smoke.mjs` 第 14 步的 3 条 DOM 布局重叠红**（`s-home` / `s-weekly-sheet` / `s-check-in`）：基线就有、与本波无关，但它让 `npm run smoke` 的退出码**恒为 1**，于是「退出码 0」这个验收项在本仓今天无法达成 | 顶回 8 |
| 7 | `exercises` 与 `prescription-templates` 在演示库上是空表（`demo_bootstrap.py` 不灌参考数据） | 关切 4 |
| 8 | `smoke.mjs` 第 0 步的注释逐字写着「**7** 张表的行数」，而 `expected` 那个对象实测有 **8** 个键（`students` / `teachers` / `notifications` / `prescriptions` / `training-logs` / `rpe-records` / `weekly-class-reports` / `alerts`）。⚠️ 本波改的是那 8 个**值**（6 个从 `undefined` 改成 `'teacher'`），没动那句注释 —— 它是既有的小不一致 | 本波实测 |
| 9 | **`backend\scripts\demo.ps1` 末尾「一条闭环可以这样点」那 8 行提示里，有 4 行的 URL 今天打过去是 401**：`GET /api/alerts?limit=50`（教师端的预警队列）、`GET /api/notifications?limit=50`（学生端的消息中心）、`GET /api/students/1/prescriptions/current`、`GET /api/students/1/weekly-sheet` —— 前两个是本波收的泛型读，后两个是**特例端点**（它们自 Plan 03 Task 8 / Plan 04 起就各自挂着 `Security(...)`，故那两行**在本波之前就已经是过期文案**）。⚠️ 那不是安全洞（401 正是本波要的行为），只是文案与行为不符；而 `demo.ps1` 的上文已经写了「未登录访问任何页面都会被路由守卫送去 `/login?next=<原路径>`」，故在浏览器里点仍然走得通（先登录、cookie 自动带上）。⚠️ **本波刻意没改它**：派单逐字列出的改动面里没有 `demo.ps1`，而它是两道禁区守卫的住址。⚠️ 改它**不会**让 `smoke.mjs` 第 17 步 ① 红——实测那一条钉的是「强制关掉身份头开关」那一段的字节级前提（`src.includes('Remove-Item Env:\\PE_ALLOW_HEADER_IDENTITY')` 一类），不是这段提示文案 | 本波实测 |

### ⑥.4 没按派单做的地方（**3 处**）

1. **commit 分组与派单建议的不同**（派单建议 ①`crud.py` 的开关 + 声明 + 守卫 +
   过滤/403；②`password_bound_at` 摘列 + 三拍守卫 + `types.ts` 同步；
   ③`smoke.mjs` / 前端 / `gen:api`；④spec + 报告）。
   实际是 ①`crud.py` + `deps.py` + `catalog.py`（机制 + 接线）／
   ②`schemas/organisation.py` + `schemas/auth.py` + 5 个测试文件（摘列 + 全部守卫改写）／
   ③前端 3 个文件／④spec + 报告。
   ⚠️ 理由：`catalog.py` 与 `test_crud.py` **各自同时含两件事**
   （`read_scope` 声明与 `password_bound_at` 的 `list_exclude` / 档 2 清单），
   而 `git add` 是文件级的、`git add -p` 是交互式的（派单禁用）。
   派单的 ①「守卫」与 ②「三拍守卫」因此合并进了实际的 ②。
2. **派单说「`types.ts` 的 23 个手写 list 类型……字段集要同步」**：
   实测它们是**别名**不是手写字段集，故**类型定义一行都没改**，只改了注释里的数字（顶回 6）。
3. **派单裁定 6 说「§1.2 的 12 条已知局限表里那条……要改写成收紧后的口径」**：
   实测没有那一条，故改成「新增第 13 / 14 条 + 在第 4 条末尾补一句」，
   表从 12 条变 **14 条**（顶回 7）。

⚠️ 派单裁定 2 的「教职全读」（顶回点 ①）我**没有顶回**：实测教师端 3 个页面
（`Dashboard.vue` 读 `listEnrollments` + `listAlerts`、`StudentDetail.vue` 读
`listMiniTests` + `listStratificationResults` + `listAlerts`、`AlertQueue.vue` 读
`listAlerts` + `listEnrollments`）都要按班、按人读**全校**数据，
把教职也自过滤会让 Plan 04 的教师端逐页降级；
而把 `require_teaches_student` 扩到泛型读要在 list 端点上做一次
「教师 ↔ 班级 ↔ 学生」的 JOIN（`read_scope` 那一档今天是一次单列等值过滤）。
代价已逐字写进 spec §1.2 **第 13 条**（新增的已知局限）。

---

## ⑦ 最终验收

### ⑦.1 后端

| 项 | 基线 | 本波 | 判定 |
|---|---|---|---|
| `pytest -q` | 1333 passed | **1339 passed**, 1 warning（133.44 s） | +6（新增 7 条守卫 − 删掉 1 条 `test_exactly_two_resources_declare_read_requires_staff`） |
| `pytest -q --cov=app/domain` | 1332 passed + 1 skipped | **1338 passed, 1 skipped**（250.25 s） | +6 |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | **逐字不变** ✓ |
| 表数 | 26 | **26** | 不变 ✓ |
| 架构守卫扫描面 | 66 | **66** | 不变 ✓（一个新 `.py` 都没加） |
| `/api/` 路径模板 / 操作 | 71 / 99 | **71 / 99** | **不变** ✓ |
| GET / 匿名 GET | 60 / 44 | **60 / 16** | GET 不变、匿名 −28 |
| 挂 `security` 的操作 | 52 | **80** | +28 |
| `securitySchemes` | 3 | **3** | 仍 3 ✓（没新增第四个） |
| 全局 `security` | `None` | **`None`** | 不变 ✓ |
| 黄金用例 | 14 | **14** | 实测不变：`tests/fixtures/golden_cases.json` 的 `len(input) == len(expected) == 14`；`pytest tests/integration/test_golden_cases.py tests/db/test_models.py -q` → **66 passed** |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | 实测不变：`python -c "from tests.db.test_models import _MODELS_PUBLIC_BASELINE as B; print(len(B))"` → **33**（⚠️ 它是 `dir(models)` 的字面清单，**不是** `models.__all__` —— 后者实测是 14 项，两个数不同源，别混）；11 个非公有模型仍走子模块路径，那条守卫绿 |

新增的 7 条守卫（都在 `tests/api/test_crud.py`）：

1. `test_every_resource_declares_read_scope_explicitly`（**键在不在**，缺省值不算显式；
   并反向钉「`student_owner` 只在 `student_self` 那一档出现」）
2. `test_the_read_scope_tiers_are_pinned_to_those_seven_thirteen_and_three`
   （三档的行数与名单**字面写死**，不从 `RESOURCES` 反推）
3. `test_every_student_keyed_resource_declares_a_non_null_read_scope`
   （派单 §2 逐字要求的**遍历型**守卫：遍历 26 张表，凡含 `student_id` 列的资源
   都声明了非 `None` 的一档；并钉住 11 直接 + 2 非直接的分布与两个 `StudentOwner`
   的**声明形状**逐字）
4. `test_the_student_keyed_resources_admit_three_read_tiers`（行为面五档矩阵）
5. `test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student`（多态键红档）
6. `test_the_generic_list_and_read_one_descriptions_are_verbatim_identical`
   （从 `app.openapi()` 实读：23 个 list 与 23 个 read-one 的 `description`
   各自**只有 1 种取值** —— 钉住那两个端点分支的 docstring 没有分叉。
   ⚠️ 改前实测本就是 1 种，故本条钉的是**既有性质的保持**）
7. `test_password_bound_at_is_absent_from_both_the_read_model_and_the_list`（三拍）

删掉 1 条：`test_exactly_two_resources_declare_read_requires_staff`
（那个布尔开关被 `read_scope` 替代，两条并存就是两个所有者；
它的职责由上面第 1 + 第 2 条各钉一半）。

### ⑦.2 前端

| 项 | 基线 | 本波 |
|---|---|---|
| 路由 | 15 | **15**（`router/index.ts` 一行没改） |
| `npm run build` 退出码 | 0 | **0** |
| 产物 | CSS 61.02 kB / JS 165.70 kB（129 modules） | **逐字相同**（`index-Db3TVHCJ.css` 61.02 kB / `index-UryyTQo3.js` 165.70 kB，两个 hash 都没变） |
| `check:tokens` | 绿 | **绿**（扫描面 32 / 下界 25） |
| `check:dist` | 绿 | **绿**（`adoptFromUrl` 在产物里 0 次、在源码里存在） |
| `@ts-ignore` / `as any` | 0 | **0** |
| `smoke.mjs` 步数 | 18（0–17） | **18**（0–17） |
| `smoke.mjs` 断言 | 408（派单说「退出码 0」，**实测基线是 405 绿 + 3 红 / 退出码 1**，见顶回 8） | **490**（**487 绿 + 3 红**） |
| `smoke.mjs` 退出码 | **1**（实测基线） | **1**（同样那 3 条既有红，逐字相同） |
| 新增依赖 | 0 | **0**（前后端都是） |

⚠️ 断言数 408 → 490（**+82**）= 第 12 步新加的第 ⑥ 拍 **80** 条
（1 个 `eq` + 13 × 6 + 1 个 `eq`）+ 第 0 步「人人能登录」那一拍从 **1** 条 `eq`
变成 **3** 条 `check`（+2）。⚠️ 第 12 步本身从 22 条涨到 **102** 条、**整步全绿**。

### ⑦.3 禁区与指纹

| 项 | 实测 | 判定 |
|---|---|---|
| `git diff 5218eb4 -- backend/data` | **空** | ✓ 一个字节都没动 |
| `Test-Path backend\pe.db` | **False** | ✓ 禁区未破 |
| `backend\data\seed\` 文件数（`-Recurse`） | **0** | ✓ 恒为 0 |
| `national_standard_2014.csv` | **`D2C8E539E2FA0029`**（21 412 B，CRLF 归一化后） | ✓ 逐字不变 |
| `exercises.yaml` | **`5394B37F01DAC9AC`**（23 247 B） | ✓ 逐字不变 |
| `exercise_equivalence.yaml` | **`822CB86A5E998301`**（8 245 B） | ✓ 逐字不变 |
| `alert_rules.yaml` | **`E48E3AC82BB45BB7`**（6 037 B） | ✓ 逐字不变 |
| 18 个模板 YAML 的逐文件指纹 | `test_template_yaml_fingerprints_are_pinned` **绿** | ✓ 逐字不变（`backend/data` 下共 22 个 `.yaml` = 4 个非模板 + **18** 个模板） |

⚠️ 四个单文件指纹是用 `$env:TEMP` 的探针**独立**重算的（`read_bytes()` +
`replace(b"\r\n", b"\n")` + `sha256[:16].upper()`），不只是「测试绿了」；
探针跑完已删。⚠️ 全程**没有**跑过 `python -m app.seed.generate` /
`app.pipeline.backfill` / `app.pipeline.daily`，要数据/重启一律用
`backend\scripts\demo.ps1`（它自带两道禁区守卫，两次重灌都打印了
「禁区复核：`backend\pe.db` 不存在、`backend\data\seed\` 仍为 0 文件 ✓」）。

### ⑦.4 spec

| 项 | 改前（开工实测） | 改后 |
|---|---|---|
| 字节数 | 191 076 | **204 473** |
| 行数 | 1 526 | **1 666** |
| CRLF 计数 | 1 525 | **1 665** |
| BOM | 无 | **无** ✓ |
| sha256[:16] | `00732A13CE0BE2C1` | **`B100364DE62CBF30`** |
| 行尾一致性 | 全 CRLF（1 525 = 1 526 − 1） | **全 CRLF**（1 665 = 1 666 − 1）✓ |

⚠️ 用 python 改（`read_bytes` → `decode('utf-8')` → 替换 → 重新 CRLF 化 → `write_bytes`），
脚本里两道断言当场守住「无 BOM」与「全 CRLF」，改完再复核一次指纹。
⚠️ §13.4.4 那一节是**锚点切片**替换（不是整段字面匹配）：
第一次跑时整段匹配 `count == 0`（Read 工具输出的换行位置与文件里的不完全一致），
而脚本**在写回之前**就 assert 失败了，故 spec 当时一个字节都没被改（安全失败）。

改了四处：

* **§13.4.4** 整节改写：标题从「44 个匿名 GET + 4 个要教职身份的名册读」改成
  「**三档**」；正文含「Plan 05A 的判据问错了问题」那一段（引终审 I6 原文）、
  三档表（7 / 13 / 3 逐行名单）、2 个非直接键的实测依据、
  `weekly-class-reports` 为什么收成 `staff`、「大屏匿名可读」那句假话的更正（顶回 9）、
  连带口径表（71 / 99 / 60 / 16 / 44 / 80 / 3）、`total` 与 `items` 同一个 `WHERE`
  的实测数（840 → 14、240 → 4、32 → 1）、特例端点不在范围内 + `normalized` 那扇门、
  守卫清单（含 `anonymous == 21` → `7`）
* **§13.4 的 `rpe_token` / `password_hash` 那一段**：`password_bound_at` 从
  「**是暴露的**」改成「**也摘掉了**」，含四处缺一不可与代价
* **§1.2 第 4 条**末尾补 `password_bound_at` 摘除的影响（可批量枚举 → 可逐个探测，
  本条不撤销）
* **§1.2 新增第 13 条**（教师任教范围闸门不扩到泛型读 —— 派单要求保留的那一条）
  与**第 14 条**（`GET /api/mini-tests/normalized` 仍匿名且回学生键数据）

### ⑦.5 commit

| # | sha | 文件 | 内容 |
|---|---|---|---|
| ① | `0f94557` | 3（`crud.py` / `deps.py` / `catalog.py`），+812 / −102 | `read_scope` 三档 + `StudentOwner` + `current_reader` + `_list_page` + 23 行声明 + 第 9/10/11 道校验 |
| ② | `39eaf8f` | 7（2 个 schemas + 5 个测试），+998 / −159 | `password_bound_at` 摘列四处 + 7 条新守卫 − 1 条旧守卫 + 19 条既有守卫改写 |
| ③ | `2cd736d` | 3（`smoke.mjs` / `types.ts` / `schema.d.ts`），+372 / −98 | smoke 第 ⑥ 拍与各处身份 + `gen:api` 重跑（+247 / −72） |
| ④ | *(本 commit —— 一个报告的 sha 写不进它自己，那是自指；sha 见交回控制者的那一节)* | 2（spec + 本报告） | spec 四处改写 + 报告 |

⚠️ **不 push**（派单逐字要求）；`main` 一个 commit 都没碰。
