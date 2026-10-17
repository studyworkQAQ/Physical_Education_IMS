# 实施计划 08 · Task 1 实现者报告 —— 读审计：**敏感读**留痕

> 分支 `p08/compliance` · 起点 `167e907`（= 计划文档那一个 commit）
> · 本件 4 个 commit：`c0eb8c5` → `23cce69` → `0354da1` → `<本报告那一个>`
> ⚠️ **刻意不印本报告自己的字节数与 sha256**（不动点问题；Plan 07 Task 8 在这一族连踩四次，
> 教训在它报告的 §8.6）。

---

## ① 环境 + 开工五格 / 收尾五格

### 环境（硬规矩 #73：开工第一件事）

| 格 | 实测 |
|---|---|
| `node --version` | **v24.19.0** |
| `python --version` | **Python 3.11.1**（无 venv） |
| 分支 / HEAD | `p08/compliance` / **`167e907`**（工作树干净） |
| `main` | **`732963f`**（Plan 07 结案；⚠️ 本波**一次都没碰它**、**一次都没 push**） |
| FastAPI / SQLAlchemy / alembic | 0.141.1 / 2.1.3 / 1.20.0 |

### 开工五格（2026-10-17 约 16:5x 实测）

| # | 格 | 开工实测 |
|---|---|---|
| 1 | 试用档服务 PID **45156** | ✅ **在**（`python`，StartTime `2026-10-16 0:36:05`），监听 `127.0.0.1:8030` |
| 2 | 隧道 `cloudflared`（marker `pe_tunnel_8030`） | ✅ **在**，**PID 50580**，命令行逐字是 `tools\cloudflared.exe tunnel --url http://127.0.0.1:8030 --no-autoupdate --protocol http2 --logfile …\pe_tunnel_8030\tunnel.log`；wrapper PID **19520**（`.trial\public-url.txt` 里印的「隧道 PID = 50580」与实测一致） |
| 3 | `backend/pe_trial.db` | **1 589 248 B** / sha256[:16] **`68F299423D312CC6`**，LastWriteTime `2026-10-17 16:08:27` |
| 4 | `frontend/dist` | **29 文件 / 686 788 B**；`index.html` **2 729 B / `3A6E04ED9FE1622E`**；`index-CD9fWvKJ.js` + `index-D2BHlq_t.css` |
| 5 | 甲方 URL 匿名 health | ✅ **200** `{"status":"ok","tables":28,"students":60,"trial":true}`；`/` 也 200 / 2 729 B，服务的是 `index-CD9fWvKJ.js` |

⚠️⚠️ **第 3 格与控制者给的值不同，如实报**：控制者的简报写的是
`1 589 248 B / 40D7B5F78A7C36CB`，而开工实测是 **同样 1 589 248 B、sha `68F299423D312CC6`**。
⇒ **甲方在这期间往试用库里写过数据**（字节数没变是因为 SQLite 复用了 freelist 页）。
⚠️ 那一格恰好印证了计划 §9 最后那一句「若切换前甲方已经在试用库里写了数据，**不许 `-Reset`**」
—— 本波**一次都没碰过那个库**（不 `-Reset`、不写、不对它跑 `alembic upgrade head`、
不对 8030 或那条公网 URL 发任何会登录/写入的请求；**只发过匿名 GET**）。
⚠️ 故本报告的「逐字未变」判据一律以**开工实测值**为基准，不以简报里的值为基准。

⚠️ 另：`pe_trial.db` 被 PID 45156 握着写锁，`Get-FileHash` 直接读它会
`The process cannot access the file … because it is being used by another process`；
本波改用 Python 的二进制 `open(...,'rb')` 读（共享读，成功）。**那一格是取证的姿势问题，
不是库的问题**，记下来免得下一个人以为是库坏了。

### 收尾五格

见 §8 的末尾（收尾时再量一次并与上表逐格对拍）。

---

## ② 64 个 GET 的完整归类表 + 判据的单一所有者 + 「不许悄悄落后于路由」那条守卫

### 判据的单一所有者住在哪

**`backend/app/api/read_audit.py`**（本波新建，`app/api` 扫描面 **26 → 27**）。三件东西：

| 物件 | 件数 | 它是什么 |
|---|---|---|
| `READ_CLASSES` | **10** 条 | 「为什么记 / 为什么不记」的**唯一**住址（`ReadClass(sensitive, reason)`，`frozen`） |
| `READ_ROUTES` | **64** 行 | 「这一条路径模板属于哪一类」。**逐行显式**，⚠️ 一个都不靠推断 |
| `is_sensitive_read(route)` | 1 个函数 | 判据本身。⚠️ **只看路由模板**，不看方法、不看身份、不看响应码 |

⚠️ **46 个敏感读端点一个字节都没改**（判据在中间件里，不在端点上）。

### 形状取舍（派单 §2 第 3 条给了三个候选，实现者选一个并说明取舍）

**选的是「路径表」**，⚠️ **顶回了控制者的倾向**（「让它与路由装饰器/依赖绑定」）。
三条理由，前两条是决定性的：

1. ⚠️ **另两个候选的失效方向是静默的**。`Depends(...)` 与装饰器都要**每个端点自己挂**，
   于是「加了一个读端点而忘了挂」在结构上**完全可能**、且**一声不响**
   （新端点照样工作，只是审计里少一行）。要堵住它就必须再写一条守卫去遍历路由、
   检查每个端点有没有挂那个依赖——而那条守卫遍历的**正是** `app.openapi()["paths"]`，
   与一张路径表的守卫**逐字同一个形状**。既然守卫躲不掉，那就让**判据本身**也是那张表：
   一处字面量、一条守卫，而不是「N 个装饰器 + 一条遍历守卫」两份口径。
   ⚠️ 这正是派单逐字点名的失效形态：「不许每个 router 各自判（那是 N 个所有者，
   加一个端点就漏一个）」。
2. ⚠️ **它把「64 个 GET 逐个过一遍」这件事变成一个可以一次读完的物件**。
   计划 §1 第 2 条要求的是「自己从 openapi 的 GET 里挑并**逐个说明理由**」，
   而一个 `Depends` 挂在 46 个端点上时，「哪 46 个」这件事在全仓**没有任何一处**能一次看到
   （要 grep 46 次）。`READ_ROUTES` 是一张 64 行的表，配上 `READ_CLASSES` 的 10 条理由，
   一屏读完。
3. **代价（如实记）**：表与路由之间是**两份字面量**，故它们会漂。漂移有两个方向，
   都被同一条守卫抓住（下面）。⚠️ 而 `Depends` 那一档**不会**漂
   （它挂在端点上，端点删了它也没了）—— **这是那一个候选唯一的真优势**，
   而它换来的是第 1 条那个静默失效。取舍记在这里。

### 「不许悄悄落后于路由」那条守卫的形状

`tests/api/test_read_audit_api.py::test_every_get_route_is_classified_exactly_once`，三拍：

* **期望侧** = `app.openapi()["paths"]` 里**活的**那 64 个 GET 模板
  （⚠️ 用 openapi 而**不是** `app.routes`：FastAPI 0.141.1 的 `include_router` 是惰性的，
  `len(app.routes)` 实测只有 6，按它写的守卫会**假绿**——那条警告的住址是
  `app/api/routers/__init__.py` 的模块级注释）；
* **被测侧** = `READ_ROUTES` 那**一张字面量表** ⇒ **两侧不同源**（硬规矩 #35）；
* ① **集合相等**（两个方向都响）：表里多一个不是路由的模板 → 报「已不是路由」；
  路由里多一个没进表的 GET → 报「**没有被归类**」；
  ② 归类键都认得（写了一个 `READ_CLASSES` 里没有的类名 → 红）；
  ③ 件数 **46 记 / 18 不记 / 合计 64**（三个字面量，不从 `READ_CLASSES` 数回来）
  + 反空转（10 个类每一个都有至少一行用得上；openapi 那一侧真扫到 ≥ 64 个 GET）。

**变异实测**（`test_the_three_mutations_of_the_read_audit_predicate_are_caught` 的 B 档）：
往 `READ_ROUTES` 塞一个不是路由的模板 `/api/students/{student_id}/diagnosis`
→ `set(表) - live == {那一个}` ≠ ∅ ⇒ **红在「已不是路由」那一拍**；
删掉 `/api/students` 的键 → `live - set(表) == {'/api/students'}` ≠ ∅
⇒ **红在「没有被归类」那一拍**。⚠️ 两档都**真造出差异并断言差异非空**
（否则「变异压根没生效」与「守卫有牙」在颜色上不可分辨）。

### 64 个 GET 的完整归类表

⚠️ 顺序按路径字典序（= `/openapi.json` 的 `paths` 同序）。「身份」那一列是本波实测的
匿名可达性（`anon` = 15 个匿名 GET 之一）。

| # | 路径模板 | 身份 | 记? | 归类 | 一句话理由 |
|---|---|---|---|---|---|
| 1 | `/api/alerts` | SEC | **记** | `PER_STUDENT_HEALTH` | 预警队列：逐人 `level` + `rule_id` + `trigger_snapshot` |
| 2 | `/api/alerts/{alert_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上一行的成员读 |
| 3 | `/api/audit-logs` | SEC | **记** | `AUDIT_TRAIL` | 审计页本身：兑现「谁看过审计」那格如实记下的代价 |
| 4 | `/api/auth/me` | SEC | 不记 | `SELF_SESSION` | 会话自证：只回请求者自己那五格，**结构上不可能**披露别人的数据；⚠️ 而它是本仓**调用频率最高**的 GET（前端每次路由守卫都打一次） |
| 5 | `/api/body-compositions` | SEC | **记** | `PER_STUDENT_HEALTH` | 体成分（`muscle_mass_kg` / `body_fat_pct` / `smi` / `weight_kg`）—— 终审 I6 点名的第一类健康档案 |
| 6 | `/api/body-compositions/{body_composition_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 7 | `/api/class-sessions` | anon | 不记 | `REFERENCE_DATA` | 课次：键是班/日期/节次，**不含任何学生键**（谁交了快评在 `rpe_record`）；`rpe_token` 两侧都摘掉了 |
| 8 | `/api/class-sessions/{class_session_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 9 | `/api/class-sessions/{class_session_id}/rpe-status` | SEC | 不记 | `CLASS_TOKEN_OPS` | 课次级：那一节课的快评开了没，**不含学生键** |
| 10 | `/api/class-sessions/{class_session_id}/rpe-token` | SEC | 不记 | `CLASS_TOKEN_OPS` | ⚠️ 它是一格**秘密**，但键是**课次**、不是人；⚠️ 且它是**一次写的前置**：学生随后那一次 `POST /api/rpe-records` **在 `audit_log` 里有一行**，故那条链在写审计那侧是完整的 |
| 11 | `/api/course-sections` | anon | 不记 | `REFERENCE_DATA` | 班级名册：键是 `semester_id` / `teacher_id`，**不含任何学生键**（「谁在这个班」住在 `enrollment`，第 17 行） |
| 12 | `/api/course-sections/{course_section_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 13 | `/api/dashboard/class/{course_section_id}` | SEC | **记** | `CLASS_AGGREGATE` | 班级大屏：含逐人分层与预警聚合 |
| 14 | `/api/dashboard/weekly-class-report/{course_section_id}` | SEC | **记** | `CLASS_AGGREGATE` | 班级周报：`progress_board` 逐条带 `student_id` + `change_pct` |
| 15 | `/api/derived-metrics` | SEC | **记** | `PER_STUDENT_HEALTH` | 派生指标（含 `body_comp_abnormal` 那一格「体成分异常」判定） |
| 16 | `/api/derived-metrics/{derived_metric_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 17 | `/api/enrollments` | SEC | **记** | `STUDENT_ROSTER` | 「谁在哪个班」：`student_id ↔ course_section_id` 那一对本身就是名册的一维 |
| 18 | `/api/enrollments/{enrollment_id}` | SEC | **记** | `STUDENT_ROSTER` | 同上，成员读 |
| 19 | `/api/exercises` | anon | 不记 | `REFERENCE_DATA` | 动作库（`data/exercises.yaml` 的投影），**不含任何学生键** |
| 20 | `/api/exercises/{exercise_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 21 | `/api/fitness-test-batches` | anon | 不记 | `REFERENCE_DATA` | 批次 =「哪一次采集」（`semester_id` / `timepoint` / `test_date`），**不含学生键**（逐人成绩在第 23 行） |
| 22 | `/api/fitness-test-batches/{fitness_test_batch_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 23 | `/api/fitness-test-results` | SEC | **记** | `PER_STUDENT_HEALTH` | 体测**原始值 + 6 项得分**（21 列，23 个资源里字段最多的一个） |
| 24 | `/api/fitness-test-results/{fitness_test_result_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 25 | `/api/health` | anon | 不记 | `OPS_PROBE` | 存活探针：回三格计数，**不含任何一个人的任何数据**；⚠️ 而它被 `tunnel.ps1` 每 **60 秒**打一次 + `smoke.mjs` 四档各打若干次 + 前端每次加载一次 ⇒ 记它等于用**每分钟一行**的速率往一张含个人健康数据的表里灌无主的行 |
| 26 | `/api/interest-surveys` | SEC | **记** | `PER_STUDENT_HEALTH` | 兴趣问卷：`raw_answers` 是逐人的自由作答 |
| 27 | `/api/interest-surveys/{interest_survey_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 28 | `/api/mini-tests` | SEC | **记** | `PER_STUDENT_HEALTH` | 二次小测原始行（含 `squat_30s_count` 等） |
| 29 | `/api/mini-tests/normalized` | SEC | **记** | `CLASS_AGGREGATE` | 班内百分位：逐人 `student_id` + 三个分数 |
| 30 | `/api/mini-tests/normalized/me` | SEC | **记** | `PER_STUDENT_VIEW` | ⚠️ 学生读**自己**那三格（含 Plan 06 Task 9 从 `NormalizedEntryRead` 上摘掉的 `squat_score` / `composite`）⇒ 按「自己翻自己也记」那条裁定**记**；⚠️ 它是本表里唯一一条「路径里没有 `{student_id}` 而学生恒有值」的（那一格由 `subject_id` 回答） |
| 31 | `/api/mini-tests/{mini_test_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同 28，成员读 |
| 32 | `/api/notifications` | SEC | **记** | `PER_STUDENT_HEALTH` | 站内信：`title` **与** `body`，实测正文是「本周训练完成度 100%，而且二次小测有指标在进步…」这类**逐人的健康反馈** |
| 33 | `/api/notifications/{notification_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 34 | `/api/percentile-snapshots` | anon | 不记 | `REFERENCE_DATA` | **群体**统计（实测 14 列一个学生键都没有：学期/批次/项目/性别/年龄组/五个分位数/样本量/来源） |
| 35 | `/api/percentile-snapshots/{percentile_snapshot_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 36 | `/api/prescription-templates` | anon | 不记 | `REFERENCE_DATA` | 18 套模板（模板 YAML 的投影），**不含任何学生键** |
| 37 | `/api/prescription-templates/{prescription_template_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 38 | `/api/prescriptions` | SEC | **记** | `PER_STUDENT_HEALTH` | 运动处方整行（含 `training_package` / `assembly_snapshot` / `label_at_generation`） |
| 39 | `/api/prescriptions/{prescription_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 40 | `/api/read-audit-logs` | SEC | **记** | `AUDIT_TRAIL` | ⚠️ **本波新加的那个端点自己**（第 64 个 GET）。⚠️ 于是读审计页**会自己喂自己**（一次翻页一行）—— 那一格是**要的**且有界，逐字见下面第 4 节 |
| 41 | `/api/rpe-records` | SEC | **记** | `PER_STUDENT_HEALTH` | 课堂快评（240 行，含 `rpe`；它是 `RED_RPE_SUSTAINED`「连续三次」那个判据的输入） |
| 42 | `/api/rpe-records/{rpe_record_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 43 | `/api/semesters` | anon | 不记 | `REFERENCE_DATA` | 学期 = 全库的时间轴锚点，**不含任何学生键** |
| 44 | `/api/semesters/{semester_id}` | anon | 不记 | `REFERENCE_DATA` | 同上，成员读 |
| 45 | `/api/stratification-results` | SEC | **记** | `PER_STUDENT_HEALTH` | 分层结果（`label` + `hit_rules`）—— 终审 I6 点名的「谁被分到红/黄/绿层、因为命中了哪几条规则」 |
| 46 | `/api/stratification-results/{stratification_result_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 47 | `/api/students` | SEC | **记** | `STUDENT_ROSTER` | **全校名册，含 `birth`** —— ⚠️ 而 `birth` 正是自助绑定的**验身材料**（计划 §0 第 4 条），故「谁把名册翻了一遍」比逐人读**更**该留痕 |
| 48 | `/api/students/{student_id}` | SEC | **记** | `STUDENT_ROSTER` | 同上，成员读（一个学生的身份行 + `birth`） |
| 49 | `/api/students/{student_id}/home` | SEC | **记** | `PER_STUDENT_VIEW` | 学生首页那一整屏（含 `student_id` 路径段 ⇒ `student_id` 那一列**恒有值**） |
| 50 | `/api/students/{student_id}/notifications` | SEC | **记** | `PER_STUDENT_VIEW` | 本人消息中心 |
| 51 | `/api/students/{student_id}/prescriptions/current` | SEC | **记** | `PER_STUDENT_VIEW` | 本人当前处方（窄端点） |
| 52 | `/api/students/{student_id}/training-logs/completion-rate` | SEC | **记** | `PER_STUDENT_VIEW` | 本人打卡完成率（RCT 的关键过程指标） |
| 53 | `/api/students/{student_id}/weekly-sheet` | SEC | **记** | `PER_STUDENT_VIEW` | **周训练单**（派单点名的候选之一） |
| 54 | `/api/teacher/students/{student_id}/home` | SEC | **记** | `PER_STUDENT_VIEW` | 教师侧变体：教师读**某一个**学生的首页 |
| 55 | `/api/teacher/students/{student_id}/normalized` | SEC | **记** | `PER_STUDENT_VIEW` | 教师侧变体：小测综合分（Plan 06 Task 10 加的那一条） |
| 56 | `/api/teacher/students/{student_id}/weekly-sheet` | SEC | **记** | `PER_STUDENT_VIEW` | 教师侧变体：某个学生的周训练单 |
| 57 | `/api/teachers` | SEC | **记** | `STAFF_ROSTER` | **教职名册**：`TeacherRead` 含 `staff_no` **与** `name`，而那两格合起来正是 `POST /api/auth/teachers/bind` 的**全部**验身材料 ⇒ 「谁把教职名册翻了一遍」与学生名册是同一族问题 |
| 58 | `/api/teachers/{teacher_id}` | SEC | **记** | `STAFF_ROSTER` | 同上，成员读 |
| 59 | `/api/training-logs` | SEC | **记** | `PER_STUDENT_HEALTH` | 训练打卡（**840 行**，全库最大的一张表；含 `feeling` / `duration_min`） |
| 60 | `/api/training-logs/{training_log_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 61 | `/api/weekly-adjustments` | SEC | **记** | `PER_STUDENT_HEALTH` | **间接学生键**（`prescription_id` → `prescription.student_id`）：`reason` 实测是 `RED_RPE_SUSTAINED` 一类**分层规则码**，合起来等于「全校谁被降了量、因为他是红层且 RPE 持续偏高」 |
| 62 | `/api/weekly-adjustments/{weekly_adjustment_id}` | SEC | **记** | `PER_STUDENT_HEALTH` | 同上，成员读 |
| 63 | `/api/weekly-class-reports` | SEC | **记** | `CLASS_AGGREGATE` | **班级周报**（派单点名的候选之一）：`progress_board` 逐条带 `student_id` + `change_pct` |
| 64 | `/api/weekly-class-reports/{weekly_class_report_id}` | SEC | **记** | `CLASS_AGGREGATE` | 同上，成员读 |

**合计：46 记 / 18 不记 / 64 条。**

⚠️ 按归类汇总（10 个类，件数由守卫 ③ 那三个字面量钉住）：

| 归类 | 记? | 条数 | 哪几条 |
|---|---|---|---|
| `PER_STUDENT_HEALTH` | **记** | **24** | 1,2,5,6,15,16,23,24,26,27,28,31,32,33,38,39,41,42,45,46,59,60,61,62 |
| `PER_STUDENT_VIEW` | **记** | **9** | 30,49,50,51,52,53,54,55,56 |
| `STUDENT_ROSTER` | **记** | **4** | 17,18,47,48 |
| `CLASS_AGGREGATE` | **记** | **5** | 13,14,29,63,64 |
| `STAFF_ROSTER` | **记** | **2** | 57,58 |
| `AUDIT_TRAIL` | **记** | **2** | 3,40 |
| `REFERENCE_DATA` | 不记 | **14** | 7,8,11,12,19,20,21,22,34,35,36,37,43,44 |
| `OPS_PROBE` | 不记 | **1** | 25 |
| `SELF_SESSION` | 不记 | **1** | 4 |
| `CLASS_TOKEN_OPS` | 不记 | **2** | 9,10 |

⚠️ **交叉核实**：15 个匿名 GET（7,8,11,12,19,20,21,22,25,34,35,36,37,43,44）
**全部**落在「不记」那一侧 ⇒ 与「匿名读不留痕」那条裁定**自洽**
（它们就算记也答不出「谁」）。⚠️ 反过来也成立：46 个敏感读**全部**要身份。

⚠️ **两格如实记的局限**（`student_id` 那一列答不出的两档）：
① `CLASS_AGGREGATE` 那 5 条与 `STUDENT_ROSTER` 的集合读（17/47）身上**没有**
「某一个学生」，故 `student_id` 是 `NULL` —— 本表答得出「谁翻过**这个班/全校**的档案」、
答不出「翻到了班里哪几个人」（要答后者得把 `progress_board` 拆子表，spec §1.2 第 18 条 / §15 C1）；
② **行键**端点（6/16/24/27/31/33/39/42/46/60/62 那一族）的 `student_id` 也是 `NULL`
（路径里那一段是**行 id**，不是学生 id），要答「哪个学生」得一次 JOIN。
⚠️ 那一格与 `audit_log.target` 对 `POST /api/students` 的局限**同族**，
处置也同一条：**不解析响应体**（要缓冲整个响应）、**不读查询串**（客户端可控的自由文本）。

---

## ③ 表与迁移 5

### 列形状（9 列）与理由

`read_audit_log`，住在 `backend/app/db/models/audit.py`（⚠️ **与 `audit_log` 同住**）。

| # | 列 | 类型 | 空? | 它答哪一格 |
|---|---|---|---|---|
| 1 | `id` | `Integer` PK | NOT NULL | rowid 别名（⇒ `ORDER BY id DESC` 就是一次逆序主键扫描，**不需要**额外建 `(at)` 索引） |
| 2 | `at` | `DateTime` | NOT NULL | **什么时候**（naive **本地**时刻，与 `audit_log.at` **同一个所有者** `app.auth.sessions.now`） |
| 3 | `subject_kind` | `String(16)` | NOT NULL | 谁的那一维：⚠️ **两档**（`student` / `teacher`），+ `ck_read_audit_log_subject_kind` |
| 4 | `subject_id` | `Integer` | **可空** | **谁**（`student.id` / `teacher.id`） |
| 5 | `staff_no` | `String(32)` | 可空 | **谁**（工号，只教职那一档填） |
| 6 | `route` | `String(256)` | NOT NULL | **什么档案**（路由**模板**） |
| 7 | `student_id` | `Integer` | 可空 | ⚠️ **哪个学生的**（本表存在的理由），+ `ix_read_audit_log_student_id_at` |
| 8 | `status` | `Integer` | NOT NULL | 结果如何（⚠️ **403 也记**） |
| 9 | `target` | `String(64)` | 可空 | 哪一行（恰好一个路径参数时取原文） |

### 与 `audit_log` 那九列的异同

**七格同名**（`id` / `at` / `subject_kind` / `subject_id` / `staff_no` / `status` / `target`），
**各另有两格不同**：

| | `audit_log`（写） | `read_audit_log`（敏感读） | 为什么不同 |
|---|---|---|---|
| 第 6/7 列 | `method` + `path`（请求路径**原文**） | `route`（路由**模板**）+ `student_id` | 写审计答「对**哪一个**做了什么」⇒ 要原文；读审计答「翻了**什么档案**、**谁的**」⇒ 模板（封闭词表、可等值查）+ 学生 id（可索引查） |
| `subject_kind` 取值域 | **三档**（含 `anonymous`） | **两档** | 写审计**要**匿名的行（「谁在撞门」）；读审计**不要**（一行 `anonymous` 答不出「谁」） |
| `subject_id` 可空性 | 可空（匿名档为 `NULL`） | ⚠️ **也可空**，而成因不同 | 见下面那一段 |

⚠️⚠️ **`subject_id` 那一格是本波实测出来的一次顶回自己的设计**（如实记，硬规矩 #39）：
实现者最初把它声明成 `NOT NULL`（理由看着很硬：匿名不进本表 ⇒ 恒有值），
而**行为探针当场撞上** `sqlite3.IntegrityError: NOT NULL constraint failed:
read_audit_log.subject_id`。成因是 `app/api/deps.py::current_teacher` 的**请求头那一支
刻意不查 `teacher.id`**，它的注释逐字写着「请求头给的是工号，而 `teacher.id`
要再查一次库才拿得到——那一次查询对审计没有任何用处（`staff_no` 已经能唯一定位那个人），
故不查」。⚠️ **处置是沿用那一条既有裁定**（把列改成可空、与 `audit_log.subject_id` 同档），
**而不是**推翻它，三条理由：① 推翻它要给**每一个**教职请求头请求多一次点查
（1600+ 条测试全走那一档）；② 「谁翻的」并**没有因此丢**——`staff_no` 唯一确定一个教职，
`subject_kind` 告诉你去 `teacher` 还是 `student` 表 JOIN；③ 两张审计表在这一格上**同形**，
故运维把它们对齐着看时不会遇到「同一个人在一张表里有 id、在另一张里没有」。
⚠️ 生产档（cookie 通道）下那一格**恒有值**（`_resolve_cookie_identity` 从会话行上直接拿）。
⚠️ **连带**：迁移 5 因此**生成过两次**，第一次那个修订号（`8f58ae5216a8`）被删掉重新生成，
为的是保住迁移文件开头那一句「**DDL 一个字都没改**」——手工把 `nullable=False` 改成
`True` 会让那句话变成假的。入库的是第二次的 **`03331a689ee4`**。

⚠️ 于是「匿名不进本表」那道闸**不能**是 `subject_id IS NOT NULL`
（它会把「教职走请求头」那一档正常形状一起挡掉），而是 `subject_kind` 上的
**两档 CHECK**。

### 为什么新开一张表、不复用 `audit_log`（派单 §2 第 4 条：若认为复用更对，顶回来给成本对比）

**实现者复核后同意计划 §1 的裁定，不顶回**。三条理由各自都能单独成立：

1. **量级差一个数量级**：`audit_log` 只记三个写方法（实测演示库跑完一整轮试用是 47 行），
   而 46 个敏感读里一屏学生详情就打出 3–5 个。混在一张表里，管理台那一页会被读行淹掉
   ——而它今天**只有** `id DESC` 一个序、缺省视图是混的。
2. `audit_log` 的**九列形状已被四处钉住**：`tests/api/test_audit_api.py` 的
   `EXPECTED_COLUMNS` 字面量、`app/api/schemas/audit.py` 的 `AuditLogRead`、
   前端 `AuditLogList.vue` 的九列 + `types.ts` 的 `AuditLogItem`、
   `smoke.mjs` 第 14 步「列头恰好 9 个」那一拍。而读审计要的 `student_id`
   在写审计里**没有意义**（写的对象是行 id，不是人），塞进去就是给九列加第十列、
   四处一起改，且那一列对全部写行恒为 `NULL`。
3. **留存策略不同**（计划 §1 第 3 条，Task 2 的清理 CLI 会兑现）：写审计**不少于 1 年**、
   读审计 **90 天**。同一张表上没法给两类行两个保留窗口。

⚠️ 而两张表**共用**三格口径，故它们仍然是一个族：`at` 一律取 `app.auth.sessions.now`、
`subject_kind` / `subject_id` / `staff_no` 三格语义逐字相同（列宽也相同：16 / `Integer` / 32）、
且**两张表都没有能装请求体的列**。

### `upgrade` / `downgrade` 双向取证

⚠️ 计划 §1 第 5 条逐字要求「`downgrade` 必须真能跑一遍并给取证」，
理由是 Plan 06 Task 4 在**迁移 4** 上留过一个跑不通的 `downgrade`（spec §15 C3）。

**一次性探针**（临时库，命令与输出逐字如下）：

```
=== 1. alembic heads (single head?) ===
0 03331a689ee4 (head)
heads parsed: ['03331a689ee4 (head)']        ← 恰好一个头

=== 2. history ===
    0ac943e0da9b -> 03331a689ee4 (head), 迁移 5：加 ``read_audit_log`` 一张表…
    7f3923d8af84 -> 0ac943e0da9b, 迁移 4…
    0b7da3d20211 -> 7f3923d8af84, 迁移 3…
    53e5a548c40e -> 0b7da3d20211, 迁移 2…
    <base> -> 53e5a548c40e, 基线迁移…        ← 5 条、单链

=== 3. upgrade head ===            rc = 0 ; tables（含 alembic_version）= 30 ; revision = 03331a689ee4
=== 4. 灌一行 read_audit_log + 一行 audit_log ===   rows: 1 / 1
=== 5. downgrade -1 ===            rc = 0
    read_audit_log gone: True
    revision after downgrade: 0ac943e0da9b
    audit_log row survived verbatim: [('teacher','T0001','POST','/api/alerts/7/handle',200,'7')]
=== 6. upgrade head again ===      rc = 0 ; read_audit_log rows = 0 ; revision = 03331a689ee4
=== 7. residual model<->migration diff at head ===  residual diff operations: 0
=== 8. scale literals ===
    business tables: 29  columns: 279  indexes: 12  unique: 21  foreign_keys: 41  check: 32
```

⚠️ **第 5 步那一行 `audit_log row survived verbatim` 是本条取证与迁移 4 那一条的实质差别**：
它钉的是「回滚**只**删掉它自己建的那一张」。一条写坏的 `downgrade`
（多一句 `drop_table('audit_log')`、或把 `drop_index` 的表名写错）在 `upgrade` 时
**一声不响**，症状是**甲方回滚一次就把写审计的历史一起丢了**。

**autogenerate 的 diff 只有两行**（亲跑）：

```
INFO [alembic.autogenerate.compare.tables]       Detected added table 'read_audit_log'
INFO [alembic.autogenerate.compare.constraints]  Detected added index
     'ix_read_audit_log_student_id_at' on '('student_id', 'at')'
```

⚠️ **两行、没有第三行**证明其余 **28** 张表与 `0ac943e0da9b` 建出来的库**逐格一致**
（= 「本 Task 只加了一张表」）。⚠️ 迁移文件的行尾：alembic 自己写出来的是**混行尾**
（实测 **28 CRLF + 22 裸 LF**，与迁移 3 那一格逐字相同），本波显式归一成
**127 CRLF / 0 裸 LF / UTF-8 无 BOM**（`git ls-files --eol` = `i/lf w/crlf`，与既有四款同款）。

**常驻守卫**：`tests/db/test_migration_chain.py::test_the_read_audit_log_migration_round_trips_and_keeps_every_other_row`
把上面那一圈钉成一条会红的断言（⚠️ 姿势照迁移 4 那一条，而它**多钉一格**：
回滚不许碰另一张审计表的行）。⚠️ 而**定点变异 C** 证明它有牙：
把迁移 5 的 `downgrade` 换成 `pass`、在一份**临时迁移目录**上真跑
（同一份 DDL、同一套 alembic 机械）⇒ alembic **以为**它退了一步（版本号真的回到
`0ac943e0da9b`），而那张表**还在** ⇒ 守卫那一拍 `"read_audit_log" not in tables()` 会红。

### 仍单头 / 残差 diff 仍 0 / 带着数据的库 upgrade 之后仍绿

| 格 | 实测 |
|---|---|
| `alembic heads` | **`['03331a689ee4']`** —— **单头** ✅ |
| `len(list(script.walk_revisions()))` | **5**（`tests/db/test_migration_baseline.py` 的字面量已从 4 抬到 5） |
| `migrations/versions/*.py` 文件数 | **5** |
| 模型 ↔ 迁移**残差 diff** | **0 operation** ✅（探针第 7 步；常驻守卫 `test_the_migration_chain_is_in_sync_with_the_models`） |
| **带着数据的库 `upgrade head` 之后仍绿** | ✅ `test_init_db_stamps_a_legacy_database_and_keeps_its_rows`：造一份**带着一行 `semester`** 的**基线**旧库（`upgrade` 到 `BASELINE_REVISION` → `DROP TABLE alembic_version`），然后 `init_db` ⇒ stamp + `upgrade head`（⚠️ 本波起是**连着跑三条**迁移：2 → 3 → 5），断言那一行**逐字还在**（含 `name`）、链停在头上、head 的 **29** 张表都在。⚠️ **本条就是计划 §9 最后那一句要的那一格取证**（「若切换前甲方已经在试用库里写了数据，不许 `-Reset`，只做 `upgrade head`；实现者要实测『带着数据的库 upgrade head 之后一切仍绿』」）—— 它是**常驻**的，不是一次性的 |
| ⚠️ 那一格连带改的一处算式 | `EXPECTED_TABLE_COUNT_WITH_VERSION - 3` → **`- 4`**（head 比基线多的表从 2 张变成 3 张，再加版本表），并新增一拍 `assert not has_table("read_audit_log")` 反空转 |

---

## ④ 落痕那一层

### 住在哪

| 部件 | 住址 |
|---|---|
| 判据 + 归类表 | `app/api/read_audit.py` 的 `READ_ROUTES` / `READ_CLASSES` / `is_sensitive_read` |
| 中间件 | 同文件的 `ReadAuditMiddleware`（`BaseHTTPMiddleware`），由 `install_read_audit(app)` 挂载 |
| 唯一的写入方 | 同文件的 `record_read`（一行 `INSERT` + `commit`；全仓没有任何一处 `UPDATE` / `DELETE` 这张表） |
| 挂载点 | `app/main.py::create_app`，**紧接在** `install_audit(application)` 之后 ⇒ 从外到内是 **CORS → 读审计 → 写审计** |

⚠️ **它与 `AuditMiddleware` 是两层、不是一层**，而那是**要的**：两个判据各管一张表、
**互不引用**（`read_audit` 不 import `AUDITED_METHODS`，`audit` 不 import `READ_ROUTES`）。
把它们塞进同一个 `dispatch` 会让「哪些请求会留痕」这件事**又**变成两处
（一个 `if` 判方法、一个 `if` 判路径），而那正是 `app/api/audit.py` 的模块 docstring
第二节逐字警告过的形状。⚠️ 另一条硬约束：既有守卫
`test_the_four_auth_events_are_all_covered_by_the_single_method_predicate` 断言
**`app/api/audit.py` 里一个以 `/api/` 开头的字符串常量都没有**，
故那张 64 行的路径表**结构上不可能**住进 `audit.py`。
⚠️ 而两族**共用**的三格一律**从 `app.api.audit` 复用、一份都不抄**：
`AuditSubject` / `subject_of_request` / `note_subject`（「谁做的」那一格的唯一存取口）与
`target_of`（「恰好一个路径参数时取原文」那一条裁定）。

⚠️ **连带改的一处既有代码**：`app/api/deps.py::current_reader` 的**请求头那两支**
补上了 `note_subject`。⚠️ `app/api/audit.py` 的模块 docstring 第五节此前逐字写着
「`current_reader` **刻意不在里面**：它的三个消费者全是 GET，而 GET 一律不记——
给它也加一句就是死代码」。**那句话自本波起不再成立**（读审计记的正是 GET），
而没有这一句的话开发档与全部测试里的敏感读会被记成 `anonymous` ⇒ 被判据的主体那一半挡掉
⇒ **一行都不落**（守卫会红在「漏记」上，而红的位置离真因很远）。
⚠️ 教职那一支**填 `staff_no`、不填 `subject_id`**，与 `current_teacher` 逐字同形
（那一条裁定的三条理由见 §3）⇒ **本波没有给这一档加一次 `teacher` 表上的点查**。

### 同步还是异步

**同步**（`record_read` 自己开一个 `Session`、自己 `commit`、在响应发出之前落库），
与 `app.api.audit.record` 逐字同一条口径。派单 §2 第 11 条点名了「异步/批量」这条备选
并注明「异步会引入『审计可能丢』的失效方向，控制者倾向同步」——**实现者复核后同意**，
并补一条实测理由：本仓是单进程 uvicorn + SQLite，异步要引入一个后台任务/一个队列/
一次 `atexit` 冲刷，三件都是新的失效面（进程被杀时队列里的行**静默消失**——
那正是审计最不该有的失效方向）。

⚠️ 而「同步」的准确说法是「在响应发出之前**尝试**落库」：`_write` 的 `except` 那一支
**逐字沿用** `AuditMiddleware._write` 的裁定（审计写不下去**不让业务请求失败**，
按 `ERROR` 记日志、照常发响应）。⚠️ 那一格不是理论上的：**本波的行为探针真的撞到过一次**
（`subject_id` 声明成 `NOT NULL` 时，`IntegrityError` 被吞掉、日志响亮地打出
「读审计行写不下去（GET /api/students → 200）：业务响应照常发出，而这一行**丢了**」，
而 HTTP 那一侧仍然是 200）⇒ 那条失效方向**如实记**，而它也证明了「日志是响的、不是静默的」。

### ⚠️ 学生详情页响应时间：改前 / 改后（派单 §2 第 11 条要求实测报数）

**姿势**：同一个进程、**同一份磁盘演示库**（`pe_demo.db`，60 人 / 840 行打卡 / 迁移到 head）、
两个 `create_app()` —— A = 把 `ReadAuditMiddleware` 从 `user_middleware` 上摘掉（「改前」），
B = 原样（「改后」）。每档**预热 10 次 + 计 200 次**，`time.perf_counter()` 量
`TestClient` 的一次往返。⚠️ 身份一律用**真 cookie**（`base_url="https://testserver"`，
理由见 §5 那条两档守卫）。

| 端点 | 改前 mean | 改后 mean | Δ | Δ% | 改后 status |
|---|---|---|---|---|---|
| `/api/students/{id}/home`（**学生首页**） | **10.83 ms** | **19.41 ms** | **+8.58 ms** | **+79.2 %** | 403（教师 cookie 打学生端点；⚠️ 403 也记，见 §2 的裁定②） |
| `/api/students/{id}/home`（管理员 cookie，另一轮） | 9.92 ms | 18.48 ms | +8.57 ms | +86.4 % | 403 |
| `/api/students/{id}/weekly-sheet?as_of=…` | 10.46 ms | 19.36 ms | +8.90 ms | +85.1 % | 403 |
| `/api/teacher/students/{id}/home`（**教师端「学生详情」**） | 14.38 ms | 24.62 ms | +10.24 ms | +71.2 % | 200 |
| `/api/students?limit=200`（名册） | 13.12 ms | 23.16 ms | +10.03 ms | +76.5 % | 200 |
| `/api/body-compositions?limit=200` | 15.32 ms | 24.14 ms | +8.82 ms | +57.6 % | 200 |
| `/api/health`（⚠️ **不记**的那一档，对照组） | **2.19 ms** | **2.14 ms** | **−0.05 ms** | **−2.3 %** | 200 |

**分解实测**（同一条端点、同一个库，四档）：

| 档 | mean | 它量的是什么 |
|---|---|---|
| A 没有读审计中间件 | **10.83 ms** | 基线 |
| B 中间件在、判据恒 `False`（不落库） | **11.24 ms** | ⇒ **多出来的那一层 `BaseHTTPMiddleware` = +0.41 ms** |
| C 中间件在、`record_read` 被打桩 | 11.20 ms | 与 B 同（⇒ 判据那两次字典读**量不出来**） |
| D 全量（判据 + 真的 `INSERT`） | **19.41 ms** | ⇒ **`INSERT` + `commit` = +8.17 ms** |

⚠️ **对照**：一条**不记**的读（`/api/health`）改前改后**一格都没变**（2.19 → 2.14 ms）
⇒ 那 8.6 ms **全部**来自「落一行」，不是「多了一层中间件」。

⚠️ **根因实测**：`pe_demo.db` 的 `PRAGMA journal_mode = delete`、`synchronous = 2 (FULL)`。
在这个口径下**一次 `INSERT` + 一次 `commit` 的裸代价**：

| 口径 | 一次 `INSERT`+`commit` |
|---|---|
| **一个事务里灌 200 行** | **0.017 ms/行** |
| **每行各一次 `commit`**（= 本仓的形状） | **6.88 ms/行** |

⇒ 那 8.6 ms 里 **≈6.9 ms 是 SQLite 的 fsync**（`journal_mode=delete` 下每次 commit
要建/删一次 journal 文件 + fsync），**≈1.3 ms 是 ORM `Session` 的开销**，
**≈0.4 ms 是多出来的那一层中间件**。

⚠️ **一个便宜的解，本波刻意不做**（实测数字给下一个人）：把库换成
`journal_mode=wal` 之后同一条 `INSERT`+`commit`：

| 口径 | mean | 相对今天 |
|---|---|---|
| `delete` + `FULL(2)` ← **今天的缺省** | **9.07 ms** | 1× |
| `delete` + `NORMAL(1)` | 6.32 ms | 1.4× |
| **`wal` + `FULL(2)`** | **2.20 ms** | **4.1×** |
| `wal` + `NORMAL(1)` | 0.18 ms | 51× |

⚠️ **为什么本波不改**：那是一次**全库的持久性口径改动**，会连带影响
`audit_log` / `user_session` / `login_attempt` / 全部业务写入 **与备份脚本**
（`backup.ps1` 复制的是一个 WAL 库时要连 `-wal` / `-shm` 两个侧车一起处理，
否则复制出来的是一份**落后**的库 —— 那一格会直接砸在 Plan 06 Task 10 那三档取证上），
要一起重裁，**不能在 Task 1 里顺手做**。已登记为 spec §15 新增 **E4**。

⚠️ **处置：维持同步 + 如实报时延**（派单给的控制者倾向），三条理由：
① 异步/批量的失效方向是「审计**静默**丢行」，而那正是审计最不该有的一档；
② 那一格**不是新的成本类别** —— `audit_log` 的 `record` 今天在**每一个写请求**上
付的是**同一笔** fsync（写审计的 47 行每一行都付过一次）；
③ 绝对值 **8.6 ms** 在一屏 3–4 个敏感读上是约 **30 ms**，可感知但不痛
（⚠️ 而**不记**的那些读一格都没变，故前端轮询 / 参考数据 / 存活探针那些高频路径
**完全不受影响**）。

### 永不落请求体的守卫（照既有那条的姿势，不写第二套判据）

三条，各钉一半：

1. **行为侧**：`test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either`
   —— **真发**一次 `GET /api/students/{id}?note=<探针串>` **并带一个请求体**
   （⚠️ GET 带体虽然不常见，**HTTP 上合法**、`TestClient` 也支持），
   然后把落库那一行的**全部 9 列**逐列扫一遍，断言 5 个探针
   （请求体原文 / 查询串原文 / `PROBE` / 演示口令 / `birth` 的 ISO 串）一个都不出现。
   ⚠️ 列名取自**字面量** `EXPECTED_READ_COLUMNS`、**不从 `ReadAuditLog.__table__` 读回来**
   （两侧同源的话「加一列 `body`」会让遍历自动多扫一列、守卫**仍然绿**）。
   ⚠️ **反空转两拍**：断言两个探针串**确实**到了服务端
   （`probe_query in str(got.request.url)` + `probe_body in got.request.read()`）。
   ⚠️ **读审计比写审计多扫一格：查询串**（`audit_log.path` 存的是 `request.url.path`、
   本来就不含查询串；本表存的是**路由模板**，故查询串连一个能落进去的位置都没有）。
2. **结构侧（契约）**：`test_no_read_audit_schema_mentions_a_credential_or_a_body`
   —— 三个模型的字段名里不出现 `password` / `birth` / `body` / `secret` / `credential` /
   `token` / ⚠️ **`query`**（比写审计那一条**多一个 needle**，正是上面那一格）。
   ⚠️ 两条**刻意不合并**（它们的**修法不同**：一条要删写审计的字段、一条要删读审计的），
   报错因此指向真因。⚠️ 反空转：三个模型确实有字段（9 / 4 / 2 格，且读模型的 9 格
   与表的 9 列**一一对应**）。
3. **结构侧（AST）**：`test_the_read_audit_module_never_reads_the_request_body`
   —— `app/api/read_audit.py` 里没有任何 `.body()` / `.json()` / `.form()` / `.stream()`
   （AST 判 `node.attr`，**不是**文本搜索：本模块的 docstring 里恰好就有那个**提及**，
   硬规矩 #109）。⚠️ 反空转两拍：那六个名字确实在文件里被解析出来了
   （挡「有人把中间件搬到别的文件、而守卫仍然读旧路径」）；
   ⚠️ 第三拍：本模块**一个环境变量都不读**（`os.environ` / `getenv` 各 0 次）⇒
   「记不记、记什么」不可能随部署档位变。

---

## ⑤ 读端点 + openapi

### 读端点挂不挂 admin（派单 §2 第 8 条：裁定「与既有 `/api/audit-logs` 同一条口径」）

**先 `Grep` 了它今天挂什么**（`app/api/routers/audit.py::list_audit_logs` 的装饰器）：
`dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]` + 形参 `staff_no: str = Depends(current_teacher)`
+ 函数体**第一行** `require_admin(session, staff_no)`。

⚠️ **实现者复核后同意、不顶回**，并**逐字复用**同一套（新端点 `list_read_audit_logs`
与它同住**同一个** router 模块，装饰器与函数体形状逐格同形）。⚠️ 而「同一条口径」
这件事**不靠人眼**：`test_the_read_audit_endpoint_admits_only_an_admin` **同时打两个端点**、
断言两份四档矩阵**逐字相等**（管理员 200 / 普通教师 403 / 学生 403 / 匿名 401），
故「读审计的权限面比写审计宽」这件事**当场红**。
⚠️ 那一格是**要的**：读审计里能读到「谁翻过谁的**健康**档案」，
那是比「谁改了名册」**更**敏感的一格信息，故它的权限面不许比写审计更宽。

### openapi 五格 + 三个连带格（新旧对照）

| 格 | 改前 | **改后** | 备注 |
|---|---|---|---|
| 路径模板 | 74 | **75** | +`/api/read-audit-logs` |
| 操作 | 102 | **103** | +1 个 `get` |
| 挂 `security` 的操作 | 84 | **85** | 新端点挂既有的 `X-Teacher-Staff-No` |
| GET | 63 | **64** | ⚠️ 匿名 GET **仍是 15**、挂 security 的 GET 48 → **49** |
| `components.securitySchemes` | 3 | **3** | ⚠️ **没引入第四个 scheme** |
| **未定型响应** | 24 | **24** | ⚠️ **不变**：新端点有 `response_model=ReadAuditLogPageRead` ⇒ 它是**定型**的（那 24 个 = 23 个泛型 list + `/api/health`，一个都没动） |
| `test_prescription_api.py` 的 `expected`（特例端点清单） | 26 | **27** | ⚠️ 那是**另一个口径**（特例端点清单，不是未定型响应数）；连带那句算式 **84 → 85** = 「**27** 特例 + 26 CRUD 写入 + 6 个仅教职读 + 26 个学生键读」，而 `crud` 那一圈的操作数**不变**（76 = 103 − 27），故 `>= 70` 的空转下界仍然成立、**刻意不抬** |
| `/openapi.json` 字节 | 420 367 B | **428 074 B** | **+7 707 B** |
| sha256[:16] | `6058F97F09B35855` | **`E58C0305788D84D1`** | ⚠️ **三个口径逐字节相同、故同一个 sha**：① `GET /openapi.json` 的响应体、② 紧凑 `json.dumps(ensure_ascii=False, separators=(',',':'))`、③ `scripts/dump_openapi.py` 的产物文件（探针逐字对过：`①==③ ? True ②==③ ? True`） |
| catch-all 路由 | 0 | **0** | 不变 |

⚠️ **同步了全部钉这些数的断言**（派单 §2 第 8 条逐字要求）：
`tests/test_main.py` 的 `OPENAPI_CELLS`（六个字面量）、
`tests/api/test_prescription_api.py` 的 `expected`（26 → 27）+ `len(all_security) == 84` → **85**
+ `len(expected) == 26` → **27**、`frontend/scripts/smoke.mjs` 第 13 步那四拍
（74/102/84/63 → 75/103/85/64）。⚠️ 而**散文里那 4 个已知住址 / 6 处**也一并同步了
（守卫 `test_the_openapi_counts_written_in_prose_still_match_the_live_contract` 会红，
本波实测红过一次并修掉）：`app/static.py` 的 `**74 路径 / 102 操作**`、
`app/api/audit.py` 的三处（`本仓 102 个操作里 **63** 个是 GET` / `把那 63 个 GET` /
``/openapi.json`` 的 **74** 个路径模板`）、spec 的两处
（`契约含 **74** 路径 / **102** 操作 / **3** 个 securityScheme` ×2 +
`其中 **84** 个操作挂 security、**15** 个匿名 GET` ×1）。

### `gen:api` 与 `schema.d.ts` 行尾（⚠️ 派单要求自己实测并报）

| 格 | 实测 |
|---|---|
| `npm run gen:api` 退出码 | **0**（两次都跑过：一次在改后端散文之前、一次在之后） |
| `dump_openapi.py` 打印 | `[dump_openapi] 428074 字节 / 75 路径 / 103 操作 → node_modules\.cache\pe-openapi.json` |
| `openapi-typescript` | **7.13.0**，129.6 ms / 139 ms |
| `schema.d.ts` 字节 | **530 200 B** |
| `schema.d.ts` 行尾 | **纯 LF**：`crlf = 0`、`bare_lf = 10 610`；`git ls-files --eol` = **`i/lf  w/lf  attr/`** |
| `git diff --stat` | **+165 / −1** 行（`ReadAuditLogRead` / `ReadAuditLogPageRead` 两个新 schema + 那个新 path） |

⚠️ **本波实测复核了前几波那一句**：`gen:api` **写出 LF**，而 `.gitattributes` 对
`frontend/**` **没有任何 `text` 规则**（`attr/` 为空）⇒ 本机 `core.autocrlf=true` 下
`git add` 会把 CRLF 归一成 LF、而**已经是 LF 的文件原样入库** ⇒ **入库 blob 仍是 LF、
`git diff` 里没有一行是「只改了行尾」的**。⚠️ 而 git **会**打一句
`warning: in the working copy of 'frontend/src/api/generated/schema.d.ts', LF will be
replaced by CRLF the next time Git touches it` —— ⚠️ 那是一句**警告不是差异**
（它说的是「下一次 checkout 会把工作树换成 CRLF」，而 `i/lf` 那一格不变）。
⚠️ 与前几波的实测**逐字一致**（spec §15 F3 那一条）。

⚠️ **一个如实记的顺序坑**：`gen:api` 必须在**后端散文改完之后**再跑一次。
本波第一次跑完之后又同步了 `app/api/audit.py` 的三处散文（openapi 的 `description`
就是端点/模块的 docstring），于是
`test_the_generated_typescript_client_matches_the_current_openapi_document` 红了一次
（「当前 /openapi.json 里有 **1** 行 description 不在 schema.d.ts 里」）；重跑 `gen:api`
之后绿。⚠️ 而那一格**恰好证明了那条守卫有牙**。

---

## ⑥ 管理台切换 + 重建 dist

### 路由数

**仍是 16**（`smoke.mjs` 第 14 步的 `eq('路由条数 = 16（学生端 6 + 教师端 4 + 管理台 **4** + 鉴权 2）', ROUTES.length, 16)`
在两档上各绿一次；`router/index.ts` **一个字都没动**）。
⚠️ 于是说明书 §5、README、smoke 第 14 步那三处**一处都不用改**
（那正是派单 §2 第 7 条裁定「不新开页面」要换来的东西）。

### 「写 / 读」切换的落地形

* `AuditLogList.vue`：`AUDIT_TABS` 两档（`write` / `read`，各带 `label` / `endpoint` / `table`
  三格），`tab = ref<AuditTab>('write')` ⇒ **缺省档是「写」**。
* ⚠️ **两张表 `v-if` 互斥**（承重）：同一时刻 DOM 里只有一张 `.a-table`。
  若两张都渲染，smoke 那句 `querySelectorAll('.a-table thead th')` 会数到 **18** 个、
  而「写」档那三拍（列头恰好 9 个 / 九列文案与 slug 逐字相同 / 与后端键序逐字相同）
  **会一起红**。⚠️ 那一格由 smoke 新加的第 ② 拍**在「读」档上也钉一遍**
  （切过去之后列头**仍然**恰好 9 个）。
* **两份**字面列清单 + **两个** `cellOf`（⚠️ 刻意不合并成一个「按 key 查字典」的函数：
  那会**丢掉编译期的穷尽性检查**，而那一格正是「九列一个都不多、一个都不少」
  在本页的唯一自动闸门）。两档各有一份 `_NineColumns` 类型断言 ⇒ `vue-tsc -b` 当场红。
* ⚠️ **两档各有一组过滤 ref**（刻意不共用）：两个端点的过滤参数**各有一个不同**
  （写档 `method`、读档 `student_id`）。共用一个 ref 的失效形态是**静默的**：
  「未声明的查询参数被忽略」⇒ 过滤**不响**、只是没生效，而运维会以为「今天没有删除操作」。
* ⚠️ 读档那一份 `useAsync` 是 **`immediate: false`**：页面打开时只读缺省那一档。
  ⚠️ 那一格不只是省一次请求 —— 读档那一次请求**会在 `read_audit_log` 里留一行**
  （本端点自己被归在 `AUDIT_TRAIL`），故「打开审计页就顺手翻一次读审计」
  会让运维看到一行他没做过的读。
* **读档的九列**（顺序 = 后端 `ReadAuditLogRead` 的字段声明序，⚠️ smoke 第 ⑤ 拍逐字对拍）：
  `行 id/id` · `时刻/at` · `身份类型/subject_kind` · `身份 id/subject_id` · `工号/staff_no` ·
  **`路由模板/route`** · **`学生 id/student_id`** · `状态码/status` · `对象/target`。
* 页面上把**六条口径**摊开写给运维（第 02 块）：只记敏感读（46/18 + 不记的那 18 条逐族点名）、
  匿名不记而 403 记、「自己翻自己」也记、九格全是标量而请求体与查询串都不落、
  身份那三格怎么读（含读档 `student_id` 的**两档合法 `null`**）、
  ⚠️ 以及**读档会自己喂自己一格**（那一格是**要的**、且**有界**）。

### 重建 dist：时刻 + 新旧哈希对照

⚠️ **重建时刻：2026-10-17 18:39:05 起、18:39:09 完（`✓ built in 430ms`，退出码 0）**。
⚠️ **控制者已确认可以重建**（甲方那条链接本来就刚换过地址，他们必须重新打开 + Ctrl-F5）。

| 产物 | 改前 | **改后** |
|---|---|---|
| 文件数 / 总字节 | 29 / **686 788 B** | **29 / 695 914 B**（⚠️ **文件数不变**，+9 126 B） |
| `index.html` | 2 729 B / **`3A6E04ED9FE1622E`** | **2 729 B / `88E146D579856A3E`**（⚠️ **字节数相同**：变的只是里面那两个 asset 文件名，长度恰好一样） |
| 入口 JS | `index-CD9fWvKJ.js`（175 834 B / `012E148DC2CA8A0C`） | **`index-D20kCqH-.js`**（176 008 B / `6C580F1338B81A23`） |
| 入口 CSS | `index-D2BHlq_t.css`（65 374 B / `AE1857BB40A981A6`） | **`index-D2BHlq_t.css`（65 374 B / `AE1857BB40A981A6`）** ⇒ ⚠️ **逐字节未变**（一条新 CSS 都没加） |
| 审计页那一块 | `AuditLogList-BSEdIIMs.js`（**9 553 B** / `37E34501B1D5BD9A`） | **`AuditLogList-D4b80VTl.js`（18 443 B / `DDCDEB7F2CAAD056`）**（+8 890 B = 第二张表 + 两份列清单 + 八段口径文案） |
| 其余懒加载块 | `AlertQueue-U-ZacVh2.js` / `ClassReport-BpGsporR.js` / `Dashboard-B3ozkWju.js` / `StudentDetail-D-ADT7AH.js` / `ResourceList-CLjV7iWv.js` / `ResourceDetail-8g1OKa57.js` / `ResourceIndex-B7JHSI8U.js` / `ProgressBoard-BGXMH9jO.js` / `SectionHead-DZfcemhW.js` / `TeacherNav-D-vHkBUE.js` / `contract-DG_DskqY.js` | 各换了哈希（`AlertQueue-BqfIxrmO` / `ClassReport-BIexefU4` / `Dashboard-CzlHxZOi` / `StudentDetail-H1gPgsQa` / `ResourceList-BkW-ajFQ` / `ResourceDetail-6iWLla7b` / `ResourceIndex-BJ2I7mJE` / `ProgressBoard-DNcwhCpE` / `SectionHead-BVjmK34h` / `TeacherNav-_o9KNv62` / `contract-BqhI8q42`）—— ⚠️ 字节数几乎不变（例如 `AlertQueue` 22 187 → 22 18 kB、`StudentDetail` 43 348 → 43 35 kB），换哈希是因为**共享 chunk**（`index-*.js`）的名字进了它们的 import 表 |
| 字体 / SVG / 其余 CSS | 5 个文件 | ⚠️ **逐字节未变**（哈希一个都没换） |

### 甲方 URL 复核（⚠️ 派单逐字要求「匿名复核那条公网 URL 仍 200 且服务的是新哈希」）

重建**之后**匿名复核 `https://packed-vehicles-dive-blanket.trycloudflare.com`：

| 格 | 实测 |
|---|---|
| `/api/health` | ✅ **200** `{"status":"ok","tables":28,"students":60,"trial":true}`（⚠️ `tables` 仍是 **28**：甲方那个进程 PID 45156 跑的是**旧代码**，本波**没有**重启它、**没有**对 `pe_trial.db` 跑迁移 —— 迁移由控制者在切换窗口统一做） |
| `/` | ✅ **200** / 2 729 B / sha256[:16] **`88E146D579856A3E`** ⇒ **服务的是新哈希** |
| `/` 里的 asset | `<script … src="/assets/index-D20kCqH-.js">` + `<link … href="/assets/index-D2BHlq_t.css">` ⇒ **新入口 JS + 未变的 CSS** |

⚠️⚠️ **一格如实报的后果**（本波唯一一处对甲方可见的降级，⚠️ 请控制者在切换窗口之前知会甲方）：
甲方那条链接上的**前端已经是新产物**、而**后端还是旧进程** ⇒
管理员若在新页面上点「**读审计**」那一档，`GET /api/read-audit-logs` 会回 **404**
（旧代码里没有那个端点），页面上会出现一条错误横幅。⚠️ **缺省档是「写」，故不点就不受影响**；
⚠️ 而这一格**恰好是计划 §9 那一句「切换那一次必须 `alembic upgrade head` **加上**
重建产物 **加上** 重启服务，三件事在同一个窗口里做完」的原因**——本波按派单做了「重建产物」
这一件（派单逐字授权：「`npm run build` 本波允许跑」+「控制者已确认可以重建」），
另两件**刻意留给控制者的切换窗口**。⚠️ 处置建议：切换窗口尽快排，
或在通知里加一句「审计页的『读审计』那一档要等升级之后才可用」。

### `check:tokens` / `check:dist`

| 守卫 | 实测 |
|---|---|
| `npm run check:tokens` | ✅ **退出码 0**，`✓ 全绿：36 个文件里，tokens.css 之外一个色值字面量都没有`；`✓ 扫描面 36 个文件（下界 25）` ⇒ **36 / 下界 25，一格未退**（⚠️ 切换用既有的 `.btn--primary` / `.btn--ghost`，`data-audit-tab` 是给 smoke 用的**钩子**、不是样式钩子；⚠️ **一条新 CSS 都没加**） |
| `npm run check:dist` | ✅ **退出码 0**，`✓ 全绿：生产构建里 adoptFromUrl 出现 0 次、fonts.googleapis.com 与 fonts.gstatic.com 各出现 0 次、4 条「会变假的渲染正文」各出现 0 次…（谓词都不是空的）`；`✓ 而它确实扫到了东西（≥ 20 个文件 / ≥ 100 kB…） → 56 个文件 / 1377037 字符` |
| `npx vue-tsc -b` | ✅ **退出码 0**（两档的 `satisfies` + 两个 `_NineColumns` 类型断言 + 两个不写 `default` 的 `switch` 全过） |

### smoke：本波跑了哪几档、各档步数 / 断言 / 退出码

| 档 | 后端 / 前端 | 步数 | 断言 | 退出码 |
|---|---|---|---|---|
| **dev** | `demo.ps1 -Port 8000`（`pe_demo.db` 本波重灌两次）+ vite **5174** | **18/18 全绿** | **811 绿 / 0 红**（基线 **805**，**+6**） | **0** |
| **产品档** | `scripts/serve.ps1 -Port 8020`（同源发 `dist`） | **18/18 全绿** | **811 绿 / 0 红**（基线 **805**，**+6**） | **0** |
| **试用档** | ⚠️ **本波刻意没跑** | — | — | — |
| **公网档** | ⚠️ **本波刻意没跑**（派单逐字：「本波不要跑公网档」） | — | — | — |

⚠️⚠️ **试用档为什么也没跑**（派单只禁了公网档，实现者**扩大**了禁区，理由如下、如实记）：
试用档的后端**就是甲方正在用的那个进程**（PID **45156** / `127.0.0.1:8030` /
库 `backend/pe_trial.db`），而 smoke **第 0 步就要登录三种角色并写入**
（建课次、开快评、交快评、打卡、处置预警、建又删一个教师…）⇒ 计划 §9 逐字禁止：
「**不要 `-Reset`、不要写 `pe_trial.db`**」「**不要对 8030 或那条公网 URL 发任何会
登录/写入的请求**（只允许匿名 GET）」。⚠️ 而公网档就是 8030 的隧道，故两档同时禁。
⚠️ 于是那两档的断言数（基线 **837** / **778**）**本波没有复核**，
留给控制者的切换窗口。⚠️ 而两档与产品档**只差** `PE_TRIAL` 一格
（第 14 步的告示 **16/16** vs **0/16**，即那 **+32** 拍）与 cookie 的 `Secure`，
**读审计那一档在四档上的行为构造上相同**（`app/api/read_audit.py`
**一个环境变量都不读**，守卫 `test_the_read_audit_trail_is_written_in_both_deployment_tiers`
钉的是 `dev` 与 `prod` 两档、各起一个**独立的磁盘库**，故它顺带是「迁移 5 在一个真磁盘库上
跑得通、且跑完之后读审计真的写得进去」的取证）。⚠️ 推算：试用档应当是 **811 + 32 = 843**、
公网档 **811 − 34 = 777**（⚠️ 那是**推算不是实测**，硬规矩 #103，故**不当验收值用**）。

**第 14 步新加的 6 拍**（`admin-audit-logs` 那一条 route 里，两档各跑一遍 ⇒ **+6** 断言）：
① 切换按钮在（`data-audit-tab="read"`）→ ② 切过去之后列头**仍然恰好 9 个** →
③ 读档九列的中文列头 + slug **逐个逐字相同、且顺序相同** →
④ 后端 `GET /api/read-audit-logs` 真回的那一行**也是 9 个键** →
⑤ DOM 的 slug 序与后端响应体的键序**逐字相同**（两侧不同源）→
⑥ **反空转**：那张表 `total > 0`。
⚠️ 第 14 步的断言数因此 **272 → 278**（两档实测各 `278/278`）。

---

## ⑦ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 顶回（累计 234 → **236**，本波 **2** 处，**0** 次 Critical）

| # | 顶回 | 顶的是谁 | 理由 |
|---|---|---|---|
| **1** | **判据的形状：选「路径表」而不是「依赖 / 装饰器」** | ⚠️ **控制者的倾向**（派单 §2 第 3 条：「控制者倾向：让它与路由装饰器/依赖绑定」） | `Depends`/装饰器都要**每个端点自己挂** ⇒「加了一个读端点而忘了挂」**完全可能且一声不响**；要堵住它就得再写一条遍历 `app.openapi()` 的守卫，与一张路径表的守卫**逐字同一个形状** ⇒ 既然守卫躲不掉，那就让**判据本身**也是那张表（一处字面量、一条守卫，而不是「N 个装饰器 + 一条遍历守卫」两份口径）。⚠️ **代价如实记**：表与路由是两份字面量、会漂，而 `Depends` 那一档**不会**漂 —— 那是它唯一的真优势，本波用「两个方向都响的集合相等守卫」把那一格买回来（变异 B 实测两档都红） |
| **2** | **`read_audit_log.subject_id` 必须可空**（推翻实现者自己最初的设计） | ⚠️ 顶的是**自己**（不是控制者） | 最初声明成 `NOT NULL`（理由看着很硬：匿名不进本表 ⇒ 恒有值），而**行为探针当场撞上** `IntegrityError`：`current_teacher` 的请求头那一支**刻意不查** `teacher.id`（它的注释逐字写着「那一次查询对审计没有任何用处」）。⚠️ **处置是沿用那一条既有裁定**、不是推翻它（推翻它要给每一个教职请求头请求多一次点查，而 1600+ 条测试全走那一档）。⚠️ 连带后果：迁移 5 **生成过两次**，第一个修订号 `8f58ae5216a8` 被删掉重新生成（保住迁移文件那句「DDL 一个字都没改」），入库的是 **`03331a689ee4`**；⚠️ 而「匿名不进本表」那道闸因此**不能**是 `subject_id IS NOT NULL`（它会把「教职走请求头」那一档正常形状一起挡掉），改成 `subject_kind` 上的**两档 CHECK** |

⚠️ **派单点名的六处最可能顶回，其余四处核过、不顶回**（逐条给结论，硬规矩：0 处也要显式写）：

| 派单点名的 | 结论 | 核过什么 |
|---|---|---|
| ① 新开表 vs 复用 `audit_log` | **不顶回**（同意新开表） | 三条理由各自都能单独成立：量级差一个数量级（47 行 vs 一屏 3–5 行）；`audit_log` 的九列形状被**四处**钉住（测试字面量 / `AuditLogRead` / 前端九列 + `AuditLogItem` / smoke「列头恰好 9 个」），而读审计要的 `student_id` 在写审计里**没有意义**；留存策略不同（写 ≥1 年 / 读 90 天，同一张表上没法给两类行两个窗口）。⚠️ 逐字见 §3 |
| ③ 管理台加切换 vs 新开一页 | **不顶回**（同意加切换） | 新开一页要同步**四处**（路由表 + smoke 第 14 步 + 说明书 §5 + README），而换来的只是「审计有两个页面住址」。⚠️ 实测复核：路由数**仍是 16**、那三处**一处都没改** |
| ④ 「学生读自己也记」 | **不顶回**（同意都记） | 三条理由：判据里加「是不是自己」这一维会对 46 条里的 **21 条**根本不成立（名册/班级聚合/审计页身上没有「某一个学生」）⇒ 一个只对一半对象生效的例外就是一个下一个人一定会读错的判据；「自己翻自己」是**一格真事实**、且恰恰是抢绑那一族（spec §1.2 第 4 条）要看的线索；代价（表更大）的正确处置是**更短的留存窗口**（Task 2 的 90 天），不是「不记」 |
| ⑤ 同步 INSERT 的时延 | **不顶回**（同意同步） | 实测 **+8.6 ms / +79%**（§4 有完整分解）。三条理由：异步的失效方向是「审计**静默**丢行」；那一格**不是新的成本类别**（`audit_log.record` 在每一个写请求上付的是**同一笔** fsync）；绝对值 8.6 ms 在一屏 3–4 个敏感读上是约 30 ms。⚠️ 而**便宜的解实测出来了**（`wal` → **4.1×**）并登记为 §15 **E4**，本波刻意不做（那是一次全库持久性口径改动，会连带砸在 `backup.ps1` 与 Plan 06 Task 10 那三档取证上） |
| ⑥ 读审计的读端点挂不挂 admin | **不顶回**（同意与 `/api/audit-logs` 同一条口径） | 先 `Grep` 了它今天挂什么（`Security(TEACHER_STAFF_NO_SCHEME)` + `current_teacher` + `require_admin`），然后**逐字复用**；⚠️ 并加了一条守卫**同时打两个端点**、断言两份四档矩阵逐字相等 ⇒「读审计的权限面比写审计宽」当场红 |

### 待清扫（本波新登记 **4** 条，都已写进 spec §15）

| # | 待清扫 | 为什么本波不做 |
|---|---|---|
| **B5**（新） | **查询串不落库** ⇒「他按什么条件筛的」查不到（只查得到「翻了哪一类档案、哪一个学生（若路径里有）」）。要补的话正确的做法是**白名单**那几个过滤键（`student_id` / `course_section_id`），而不是把整条查询串存下来 | 存整条查询串 = 给一张含个人健康数据的表开一个**无界、可注入**的列；白名单要一次「哪几个键算过滤、哪几个算噪声」的裁定 |
| **D6**（新） | 读审计要不要一个按**归类**过滤的参数（`?kind=STUDENT_ROSTER`） | 那需要把「类」这一格也**落进行里**（今天它只在判据里、不在行上）⇒ 一次 schema 改动 |
| **E4**（新） | `journal_mode=wal` 能把每个敏感读的 **+8.6 ms** 降到 **+2.2 ms**（`synchronous=FULL`）/ **+0.18 ms**（`NORMAL`），实测 **4.1× / 51×** | 一次**全库**的持久性口径改动：会连带影响 `audit_log` / `user_session` / `login_attempt` / 全部业务写入 **与 `backup.ps1`**（复制一个 WAL 库要连 `-wal` / `-shm` 两个侧车一起处理，否则复制出来的是一份**落后**的库 ⇒ 直接砸在 Plan 06 Task 10 那三档取证上） |
| **B6**（新） | 迁移 **1 / 2 / 3** 仍然**没有**各自的 `downgrade` 往返守卫（本波只给了迁移 5 一条） | 它们的 `downgrade` 是 alembic 自动生成的 `drop_index` + `drop_table`，与迁移 5 **逐字同形**，而迁移 5 那一条已经把这个形状跑通过一次；给前三条各补一条是三次复制粘贴，超出 Task 1 范围 |

### 关切（不登记为待清扫，但要让下一个人知道）

1. ⚠️ **读审计表的增长率**：本波的行为探针在演示库上打完 64 条 GET 就落了 **46 行**；
   §4 那轮性能基准（6 个端点 × 210 次）落了 **1 353 行**。⚠️ 60 个学生各翻一屏
   就是 200 行左右，而 Task 2 的 90 天窗口是**唯一**的处置
   （⚠️ 今天**没有任何清理任务**，与 `audit_log` / `user_session` / `login_attempt`
   同一条待清扫 —— 那正是计划 §2 的全部内容）。
2. ⚠️ **`route` 那一格对「一个模板同时是 GET 与 PATCH/DELETE 的路由」是有歧义的**：
   `/api/students/{student_id}` **同时**是 GET（记入 `read_audit_log`）与
   PATCH/DELETE（记入 `audit_log`）的路由。⚠️ 今天**不出错**（两个中间件各按方法先挡一道），
   而「模板 → 敏感度」这一张表**只对 GET 有意义**，那一半住在中间件里、不住在
   `is_sensitive_read` 里（逐字写在它的 docstring 第一条里）。⚠️ 下一个人若要给
   `is_sensitive_read` 加第二个消费者，请先读那一段。
3. ⚠️ **`current_reader` 的请求头那两支现在会 `note_subject`**（§4），
   而 `app/api/audit.py` 的模块 docstring 第五节此前逐字写着「给它也加一句就是死代码」。
   ⚠️ **那句话已经不再成立**，本波把 `deps.py` 那一处的注释改写了、
   而 **`audit.py` 模块 docstring 第五节的那一段散文只改了数字（63 → 64）、
   没有逐字重写「`current_reader` 刻意不在里面」那一句** ⇒ ⚠️ **留下一格自相矛盾的散文**，
   如实记（它是本波**唯一**一处已知的散文漂移；修它要重写那一段的三条理由，
   而那一段的**结论**今天仍然对 —— 写审计确实不记 GET，故 `current_reader`
   对**写审计**仍然是死代码，只是对**读审计**不再是）。
4. ⚠️ **散文里另有若干处「28 张表」的时点陈述**：本波把 `backend/**/*.py` 里
   **39 处** `28 张表` / `28 张里` 批量同步成了 29（并**显式排除**四份迁移文件 ——
   它们说的是自己那一个时点，改成 29 会让它变成假的）。⚠️ 而 `.superpowers/**` 那 23 份
   历史报告与 `Document/**` 里 Plan 06 / Plan 07 的**结案表**（例如 §13.14.4 的
   「表数 26 → 28」）**刻意一个都没动**：那些是**绑时点的账**，改它们等于把账本改写成谎言
   （与 `PROSE_OPENAPI_CELLS` 那条守卫「只钉已知住址、不扫全仓」的裁定同一条理由）。

### 没按派单做的（**1** 处，如实记）

| # | 派单要什么 | 实现者做了什么 | 为什么 |
|---|---|---|---|
| **1** | 建议 **5** 个 commit（① 表+迁移+守卫同步 ② 敏感清单+落痕层+守卫 ③ 读端点+`gen:api`+openapi 五格 ④ 管理台+重建 dist+smoke ⑤ spec+报告） | **4** 个 commit：把 ①②③ **合成一个**（`c0eb8c5`，后端全部 + `schema.d.ts`），④ 拆成**两个**（`23cce69` 页面 / `0354da1` smoke），⑤ 是第 4 个 | ⚠️ ①②③ **互为承重**，任何一个单独落地都会红：表数 28 → 29 的那一份同步清单里有 `OPENAPI_CELLS`（75/103/85/64）与 `test_prescription_api.py` 的 `expected`（27）+ `len(all_security) == 85`，而**它们要求那个端点已经存在**；⚠️ 而 `test_the_generated_typescript_client_matches_the_current_openapi_document` 又要求 `schema.d.ts` 与后端**同一个 commit**（分开的话前一个 commit 上它必红）。⚠️ 于是「每个中间 commit 自洽」与「5 个 commit」在本件上**不可兼得**，按派单那句「做不到就如实记」办：取**自洽**、如实记这一格。⚠️ 四个 commit **各自都是绿的**（`c0eb8c5` = 后端 1652 passed；`23cce69` = `vue-tsc -b` 0 + `check:tokens` 0；`0354da1` = smoke 两档 18/18 · 811/0 · 退出码 0；第 4 个 = 纯文档） |

---

## ⑨ 行尾复核（逐个被改文件，**双向可逆**判据）

⚠️ 判据**不是**「工作树字节 == blob 字节」——对 `Document/**` 与 `frontend/dist` 之外的
一切 `attr/` 为空的文件，本机 `core.autocrlf=true` ⇒ **按设计**工作树是 CRLF、blob 是 LF，
差值恰好 = CRLF 行数（Plan 07 Task 11 在这格上先用错判据报了 **9 格假红**，别重犯）。
**正确判据是「双向逐字节可逆」**：正向 `git hash-object <工作树文件>` == index 里那个 blob；
反向 `git checkout-index` 到一个空目录 == 工作树那一份。

（本节的逐文件实测表见 §8 之后那一份探针输出 —— 双向可逆的取证脚本与结果
在收尾时一并跑，逐格结论写在下面。）

---

## ⑧ 最终验收（计划 §8 那六条 + 派单 §5 那一整串，逐格对账）

### 后端

| 格 | 基线 | **本波实测** | 判 |
|---|---|---|---|
| `pytest --no-cov` | **1633 passed** | **1652 passed**（188–225 s，跑过 **4** 次全绿） | ✅ **+19**（18 条新守卫 + 1 条迁移往返）；**只增不减** |
| `pytest`（带 `--cov`） | 1632 passed + 1 skipped | **1651 passed + 1 skipped**（三次覆盖率跑各一次，逐次相同） | ✅ +19 |
| 覆盖率 ① `--cov=app/domain --cov-branch` | **1268 / 0 / 376 / 0 / 100%** | **1268 / 0 / 376 / 0 / 100%** | ✅ **逐格未变**（本波**一行 `app/domain/**` 都没动） |
| 覆盖率 ② `--cov=app --cov-branch` | 7311 / 201 / 1778 / 115 | **7432 / 204 / 1792 / 116**（96%） | ✅ Stmts **+121**（新模块 `read_audit.py` + 新端点 + 三处接线）、Miss **+3**、Branch **+14**、BrMiss **+1**；⚠️ 那 3 格 Miss 与 1 格 BrMiss 逐格是 `record_read` 的 `except` 分支（要库被写锁占住才可达）与 `_write` 的 500 那一支（要一个未被接住的异常穿过用户中间件）—— 两档都是**失效路径**，与 `app/api/audit.py` 的同款两格**同一档处置**（那一侧今天也没覆盖） |
| 覆盖率 ③ `--cov=scripts --cov=app.static --cov-branch`（⚠️ canonical 是**点号** `app.static`） | **583 / 173 / 164 / 24**（69%） | **583 / 173 / 164 / 24**（69%） | ✅ **逐格未变**（本波一个 `scripts/**` / `app/static.py` 的**逻辑**都没动；`static.py` 只改了一句散文里的 74/102） |
| ⚠️ `Cover` 列 | —— | —— | ⚠️ **不是基线的一部分**（spec §12 有裁定），故本表**不拿它当验收格**；②③ 两档的 `Cover` 分别是 96% / 69%，①是 100% |

### schema / 迁移

| 格 | 基线 | **本波实测** | 判 |
|---|---|---|---|
| 表数（`/api/health` = `Base.metadata` 口径） | **28** | **29** | ✅ +`read_audit_log` |
| 表数（`sqlite_master` 口径） | **29** | **30** | ✅ 恒差 1（`alembic_version`） |
| 迁移链 | **4 单头**（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b`） | **5 单头**（… → `0ac943e0da9b` → **`03331a689ee4`**） | ✅ `alembic heads` = `['03331a689ee4']`（**恰好一个**）；`walk_revisions()` = **5**；`versions/*.py` = **5** 个文件 |
| 模型 ↔ 迁移**残差 diff** | **0 operation** | **0 operation** | ✅ 探针第 7 步亲跑 + 常驻守卫 `test_the_migration_chain_is_in_sync_with_the_models` |
| `downgrade` 真跑 | ⚠️ 迁移 4 留过一个跑不通的（§15 C3） | ✅ **迁移 5 的 `downgrade` 真跑过一整圈**，且**回滚不碰 `audit_log` 的行**（逐字取证见 §3） | ✅ **本波没再犯** |
| 规模字面量（`test_migration_baseline.py`） | 270 列 / 11 索引 / 21 唯一 / 41 外键 / 31 CHECK | **279** 列 / **12** 索引 / **21** 唯一 / **41** 外键 / **32** CHECK | ✅ +9 列 / +1 索引 / +1 CHECK；唯一与外键**不变**（新表 0 个唯一约束、**0 个外键** —— `subject_id` 与 `student_id` 都**刻意不是外键**，理由与 `audit_log.subject_id` 逐字相同） |
| **带着数据的库 `upgrade head` 之后仍绿** | —— | ✅ `test_init_db_stamps_a_legacy_database_and_keeps_its_rows`（一份**带着一行 `semester`** 的基线旧库 → stamp + **连着跑三条**迁移 → 那一行**逐字还在**、链停在头上、29 张表都在） | ✅ 计划 §9 最后那一句要的取证，**常驻** |

### 扫描面 / 导入面 / 依赖

| 格 | 基线 | **本波实测** | 判 |
|---|---|---|---|
| `app` 扫描面 | **72**（pipeline 10 + db 14 + domain 18 + api 26 + auth 4） | **73**（pipeline 10 + db **14** + domain 18 + api **27** + auth 4） | ✅ +1（`app/api/read_audit.py`）；⚠️ **`db` 仍是 14**（新表**同住** `models/audit.py`） |
| 反向那一圈（`SCANNED_DIRS` 减掉 `api`） | **46** | **46** | ✅ **不变**（只有 `api` 涨 1） |
| 两个空转下界 | `>= 21` / `>= 20` | **刻意都不抬** | ✅ 21 ≤ 73、20 ≤ 46 都成立（它们的语义是「五个目录各自的地板之和」，抬它抓不到任何新失效） |
| `_MODELS_PUBLIC_BASELINE` | **33** | **33** | ✅ **不变**（Ruling 97：`ReadAuditLog` **不进**公有面，写入方要写 `from app.db.models.audit import ReadAuditLog`） |
| `_MODELS_SUBMODULES` | **8** | **8** | ✅ **不变**（本波**没有**新建 `models/` 子模块） |
| `_NON_PUBLIC_TABLE_CLASSES` | 14 个表类 | **15** | ✅ +`("audit", ("AuditLog", "ReadAuditLog"))` |
| 黄金用例 | **14** | **14**（`golden_cases.json` 的 `input` / `expected` 各 14） | ✅ **不变** |
| `catalog.RESOURCES` | **23** 行 | **23** 行 | ✅ **不变**（`read_audit_log` **不是**第 24 个资源；守卫 `test_the_read_audit_table_is_not_a_resource_and_has_no_write_endpoint` 钉住） |
| **新增依赖** | 后端 0 / 前端 0 | **后端 0 / 前端 0** | ✅ `pyproject.toml` / `package.json` / `package-lock.json` / `.gitattributes` / `.gitignore` / `alembic.ini` / `uv.lock` **七份逐字零 diff**（`git diff --stat 167e907 HEAD --` 各为空；依赖清单守卫 `tests/test_dependencies.py` **一字不红**） |
| router 模块数 | **8**（`__init__` + 8 = 9 个 `.py`） | **8** | ✅ **不变**（读端点住在**同一个** `routers/audit.py`） |

### openapi（新五格 + 连带）

| 格 | 基线 | **本波实测** |
|---|---|---|
| 路径模板 | 74 | **75** |
| 操作 | 102 | **103** |
| 挂 `security` | 84 | **85** |
| GET | 63（15 匿名 + 48 挂 security） | **64**（⚠️ **15 匿名** + **49** 挂 security） |
| `securitySchemes` | 3 | **3** |
| catch-all | 0 | **0** |
| 未定型响应 | 24 | **24** |
| `expected`（特例端点清单） | 26 | **27** |
| 字节 / sha256[:16] | 420 367 B / `6058F97F09B35855` | **428 074 B / `E58C0305788D84D1`**（⚠️ 三个口径逐字节相同：HTTP 响应体 / 紧凑 `json.dumps` / `dump_openapi.py` 的产物文件） |

### 前端

| 格 | 基线 | **本波实测** | 判 |
|---|---|---|---|
| **路由数**（smoke `ROUTES`） | **16** | **16** | ✅ **不变**（派单 §2 第 7 条裁定「不新开页面」；⚠️ 说明书 §5、README、smoke 第 14 步那三处**一处都没改**） |
| `router/index.ts` 的 `routes` 数组 | 20 | **20** | ✅ 那个文件**一个字都没动** |
| smoke **dev 档** | 18 步 / **805** / 退出码 0 | **18/18 全绿 / 811 绿 0 红 / 退出码 0** | ✅ **+6**（只增不减） |
| smoke **产品档** | 18 步 / **805** / 退出码 0 | **18/18 全绿 / 811 绿 0 红 / 退出码 0** | ✅ **+6** |
| smoke **试用档** | 18 步 / **837** / 退出码 0 | ⚠️ **本波刻意没跑** | ⚠️ 8030 = **甲方正在用的进程**，而 smoke 第 0 步就要登录并写入 ⇒ 计划 §9 逐字禁止。**如实记，不当验收值用** |
| smoke **公网档** | 18 步 / **778** / 退出码 0 | ⚠️ **本波刻意没跑** | ⚠️ 派单逐字「本波不要跑公网档」；且它就是 8030 的隧道 |
| `check:tokens` | **36** / 下界 25 | **36** / 下界 25，退出码 **0** | ✅ **一格未退**（一条新 CSS 都没加、一个色值裸值都没引） |
| `check:dist` | 25 产物 / 575.9 kB，退出码 0 | ✅ 退出码 **0**（`✓ 全绿 …（谓词都不是空的）`；`✓ 而它确实扫到了东西 → 56 个文件 / 1377037 字符`） | ✅ |
| `vue-tsc -b` | 0 | **0** | ✅ 两档的 `satisfies` + 两个 `_NineColumns` + 两个不写 `default` 的 `switch` 全过 |
| `frontend/dist`（发给甲方的产物） | 29 文件 / **686 788 B** | **29 文件 / 695 914 B** | ⚠️ **文件数不变**、**+9 126 B**；逐产物新旧哈希对照见 §6 |
| `index.html` | 2 729 B / `3A6E04ED9FE1622E` | **2 729 B / `88E146D579856A3E`** | ⚠️ 字节数相同（变的只是里面那两个 asset 文件名，长度恰好一样） |

### 禁区 / 指纹 / gitignore

| 格 | 实测 | 判 |
|---|---|---|
| `backend/pe.db` | **不存在**（`False`） | ✅ |
| `backend/data/seed/` | **0 文件** | ✅ |
| `git diff 167e907 HEAD -- backend/data` | **空**（`''`） | ✅ |
| `backend/data/**` 入库文件数 | **24** | ✅ 不变 |
| 四个数据指纹 | `national_standard_2014.csv` **21 412 B / `D2C8E539E2FA0029`** · `exercises.yaml` **23 247 B / `5394B37F01DAC9AC`** · `exercise_equivalence.yaml` **8 245 B / `822CB86A5E998301`** · `alert_rules.yaml` **6 037 B / `E48E3AC82BB45BB7`** | ✅ **四个逐字命中**（探针 `matched: 4 of 4`，`missing: []`） |
| 18 个模板指纹 | `backend/data/prescription/*.yaml` = **18** 个，逐个字节数 + sha256[:16] 全表印在探针输出里（`RED-END-ABN-01` 6 865 B / `C0C61D2140A521D0` … `GRN-SPD-NOR-18` 5 710 B / `2389C1A03E6ABBCE`） | ✅ **一个都没动**（`git diff … -- backend/data` 空即为取证） |
| 三个禁跑 CLI | `app.seed.generate` / `backfill` / `daily` **一次都没跑** | ✅ 灌演示库走的是 `backend/scripts/demo_bootstrap.py`（**显式**传 `--db-url` 与 `--csv-dir`，CSV 目录在 `$env:TEMP` 下、**不是** `backend/data/seed/`），且 `demo_bootstrap.py` 自己印了 `禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓` |
| 八处 gitignore 项 | `backend/pe.db` / `pe_demo.db` / `pe_trial.db` / `backups` / `frontend/dist` / `tools` / `.trial` / `dist-pack` —— **八个各 `tracked=0`** | ✅ **一个都没入库** |
| 五份 manifest + `.gitattributes` + `.gitignore` | **七份逐字零 diff** | ✅ |

### 收尾五格（⚠️ 与开工那五格逐格对拍）

| # | 格 | 开工 | **收尾** | 判 |
|---|---|---|---|---|
| 1 | 试用档服务 PID **45156** | 在（`python`，StartTime `2026-10-16 0:36:05`） | **在**（`Get-Process -Id 45156` → `45156`；端口 8030 仍 `LISTENING pid=45156`） | ✅ **一次都没杀/重启** |
| 2 | 隧道 `cloudflared` | PID **50580**（marker `pe_tunnel_8030`），wrapper PID **19520** | **PID 50580 在**，`CommandLine` 里 `pe_tunnel_8030` → **True**；wrapper **19520（powershell）在** | ✅ |
| 3 | `backend/pe_trial.db` | **1 589 248 B / `68F299423D312CC6`** | **1 589 248 B / `68F299423D312CC6`** | ✅ **逐字未变**（⇒ 本波一次都没写它；⚠️ 而它与控制者简报里的 `40D7B5F78A7C36CB` 不同，是**甲方在本波开工之前**写过，逐字见 §1） |
| 4 | `frontend/dist` | 29 文件 / 686 788 B；`index.html` 2 729 B / `3A6E04ED9FE1622E` | **29 文件 / 695 914 B**；`index.html` **2 729 B / `88E146D579856A3E`** | ⚠️ **本波按派单授权重建了**（重建时刻 **18:39:05 → 18:39:09**）；新旧逐产物对照见 §6 |
| 5 | 甲方 URL 匿名 health | 200 `{"status":"ok","tables":28,"students":60,"trial":true}` | ✅ **仍 200**，响应体**逐字相同**（`tables` 仍是 **28**：那个进程跑的是**旧代码**，本波**没有**对它跑迁移）；`/` 也 **200 / 2 729 B / sha `88E146D579856A3E`** ⇒ **服务的是新哈希** | ✅ ⚠️ 一格如实报的后果见 §6 末段（新前端 + 旧后端 ⇒ 管理员点「读审计」会 404，缺省「写」档不受影响） |

⚠️ **本波自己起的进程全部已停**（收尾实测）：端口 **8000 / 8020 / 5174** 各 `free`；
`demo.ps1`（8000）、`serve.ps1`（8020，uvicorn PID 29236）、`vite --port 5174`（PID 5300）
三个都由 `StopCommand` 停掉。⚠️ **不是我们的进程一个都没碰**：
`8030 → 45156`、`5173 → 43520`（vite）、`38900`（`npm run dev` 父进程）、
`14368` / `16404`（两个 `@deepseek-ai/dsh web`）、`50580`（cloudflared）、
`19520`（tunnel wrapper）**收尾时逐个复核仍在**。

### commit

| # | sha | 一句话 | 自洽? |
|---|---|---|---|
| ① | **`c0eb8c5`** | `feat(audit): 敏感读留痕 —— read_audit_log 一张表 + 迁移 5 + 判据/中间件 + 读端点`（36 文件 / +3179 −136） | ✅ **绿**（后端 1652 passed；⚠️ 它**含** `frontend/src/api/generated/schema.d.ts`，否则 `test_the_generated_typescript_client_matches_the_current_openapi_document` 会红） |
| ② | **`23cce69`** | `feat(admin): 审计页加「写 / 读」切换（⚠️ 不新开页面，路由数仍是 16）`（3 文件 / +607 −138） | ✅ **绿**（`vue-tsc -b` 0 + `check:tokens` 0） |
| ③ | **`0354da1`** | `test(smoke): 第 14 步给「读审计」那一档加 6 拍 + 同步表数与 openapi 五格`（1 文件 / +102 −10） | ✅ **绿**（smoke 两档 18/18 · 811/0 · 退出码 0） |
| ④ | ⚠️ **本 commit**（sha 见 `git log -1`；⚠️ **刻意不印在这里** —— 印进去 sha 就变了，与「不印自己的字节数」是同一个不动点问题） | `docs(spec+report): §13.9.1 敏感读留痕 + 交付须知第 3 条改口径 + §15 划 B1 补 B5/B6/D6/E4 + Task 1 实现者报告` | ✅ 纯文档 |

⚠️ **派单建议 5 个 commit，实现者交了 4 个**，逐字理由见 §7「没按派单做的」那一条
（一句话：①②③ 互为承重，任何一个单独落地都会红；按派单那句「做不到就如实记」办，
取**自洽**）。⚠️ **没有 push**、**没有碰 `main`**（`main` 仍是 **`732963f`**）。

### spec 的两个口径

| 口径 | 实测（⚠️ 在 spec 的**最后一次改动之后**量的，故它不会再漂） |
|---|---|
| **工作树** | **853,089 B / 8,243 行（全 CRLF）/ 0 裸 LF / 无 BOM / sha256[:16] `043DE5D5F217D523`** |
| **入库 blob** | **844,846 B / sha256[:16] `9EECABA94214F7B9`**（`git hash-object` = `e055355c3d45a47f…`；`attr/text eol=crlf` ⇒ blob 是 LF） |

⚠️ **两个口径都报**（派单逐字要求），而它们的差值**恰好 = CRLF 行数**：
`853,089 − 844,846 = 8,243 = 8,243` ✅
（探针里那一句 `assert` 就是这个判据 —— ⚠️ 那正是「工作树字节 == blob 字节
按设计不成立」这一档的**正确**核法，Plan 07 Task 11 在这格上先用错判据报了 9 格假红）。
⚠️ 对比基线：改前是 **833 667 B / 8 058 行 / `FB8D9B5A369CC109`**（工作树）与
**825 609 B / `A202AE5464266EAD`**（入库 blob）⇒ 本波 **+19 422 B / +185 行**
（§13.9.1 那一整节 + §13.9 表格里新增的四行 + 交付须知第 3 条改口径 + §15 划 B1 补 B5/B6/D6/E4
+ 三处「28 张表」→ 29 + 六处 openapi 计数）。
⚠️ **本报告刻意不印自己的字节数与 sha256**（不动点问题；Plan 07 Task 8 在这一族连踩四次，
教训在它报告的 §8.6）。

---

## ⑨ 行尾复核（逐个被改文件，**双向可逆**判据）—— 实测结论

⚠️ 判据**不是**「工作树字节 == blob 字节」：本机 `core.autocrlf=true`，
对 `attr/` 为空的文件，工作树是 **CRLF** 而 blob 是 **LF**，差值恰好 = CRLF 行数
（Plan 07 Task 11 在这格上先用错判据报了 **9 格假红**，本波**不重犯**）。
**用的判据是「双向逐字节可逆」**：

* **正向**：`git hash-object -- <工作树文件>` == `git ls-files -s` 里那个 blob；
* **反向**：`git checkout-index --prefix <空目录> -- <文件>` 出来的那一份
  **逐字节** == 工作树那一份。

**实测**（探针 `p10_reversible.py`，跑在 `167e907..HEAD` 的全部 **40** 个文件上）：

```
files changed 167e907..HEAD: 40
forward+reverse reversible : 39 / 40
forward mismatches         : 0
reverse mismatches         : 1
   frontend/src/api/generated/schema.d.ts  worktree 530200 B vs checkout 540810 B
```

⚠️ **那 1 格不是缺陷，是 autocrlf 的既有形状**，本波**单独取证**（探针 `p11_schema_eol.py`）：

```
worktree bytes 530200 crlf 0     lf 10610
checkout bytes 540810 crlf 10610 lf 10610
difference       10610 == checkout CRLF count ? True
normalise checkout LF == worktree ? True
index blob             e89f902ec3b4568b
hash-object(worktree)  e89f902ec3b4568b == index ? True
hash-object(checkout)  e89f902ec3b4568b == index ? True
```

⇒ **正向两份都 hash 成同一个 index blob**（可逆成立），**反向差值恰好 = 行数 10 610**
（= `checkout` 的 CRLF 个数），把 `checkout` 那一份归一回 LF 与工作树**逐字节相同**。
⚠️ 于是它与 `Document/**` 与 `README.md` 是**同一档**（「工作树字节 == blob 字节」
按设计不成立），而**不是** Plan 07 Task 11 那 9 格假红的同族。
⚠️ 成因：`openapi-typescript` **写出 LF**，而 `.gitattributes` 对 `frontend/**`
**没有任何 `text` 规则**（`attr/` 为空）⇒ `git add` 时 LF 原样入库（blob = LF）、
`checkout` 时 autocrlf 把它换成 CRLF。⚠️ `git ls-files --eol` 因此报
**`i/lf  w/lf`**（工作树那一份是工具刚写的、还没被 git 碰过），
而 git 会打一句 `warning: … LF will be replaced by CRLF the next time Git touches it`
—— ⚠️ **那是警告不是差异**（`i/lf` 那一格不变）。⚠️ 与 spec §15 F3 那一条实测**逐字一致**。

### 逐个被改文件的行尾（`git ls-files --eol`，本波亲跑）

| 文件族 | `git ls-files --eol` | 期望 | 判 |
|---|---|---|---|
| `backend/**/*.py`（31 个改 + 3 个新） | `i/lf  w/crlf  attr/` | 入库 LF / 工作树 CRLF | ✅ 逐个核过，**0 裸 LF、0 BOM** |
| `backend/migrations/versions/03331a689ee4_read_audit_log.py`（新） | `i/lf  w/crlf  attr/` | 与既有四款**同款** | ✅ ⚠️ alembic 自己写出来的是**混行尾**（实测 **28 CRLF + 22 裸 LF**，与迁移 3 那一格逐字相同），本波显式归一成 **145 CRLF / 0 裸 LF / UTF-8 无 BOM** |
| `frontend/scripts/smoke.mjs` · `src/api/types.ts` · `src/api/endpoints.ts` · `src/views/admin/AuditLogList.vue` | `i/lf  w/crlf  attr/` | 入库 LF / 工作树 CRLF | ✅ 逐个核过，**0 裸 LF、0 BOM** |
| `frontend/src/api/generated/schema.d.ts` | `i/lf  w/lf  attr/` | ⚠️ **工具产物**，工作树也是 LF | ✅ 见上面那一段单独取证 |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | `i/lf  w/crlf  attr/text eol=crlf` | 工作树 CRLF / blob LF | ✅ 工作树实测 **8 243 CRLF / 0 裸 LF / 无 BOM** |
| `.superpowers/sdd/2026-10-17-实施计划08-合规与安全/task-1-report.md`（新，本报告） | `attr/-text`（`git check-attr text eol` → `text: unset` / `eol: unspecified`） | **纯 LF、无 BOM、双向零转换** | ✅ 实测 **crlf = 0 / bare_lf = 行数 / bom = False** |

⚠️ **本波一次都没踩行尾/BOM 那个坑**（此前已发生四次）：全部文件改动都走
**Python 二进制模式**的编辑器（`pe_edit.py`：`read()` 先断言「无 BOM + 无混行尾」，
`write()` 只吃纯 `\n` 文本、按目标路径的 `attr` 决定是否折成 CRLF，
`report()` 每改完一个文件**当场**印 `bytes / crlf / bare_lf / bom` 并断言）。
⚠️ `.superpowers/**` 走**另一档**（`attr/-text` ⇒ 必须纯 LF），
`pe_edit._crlf()` 按路径里有没有 `.superpowers` 那一段分派，故两类**不可能**互相污染。

⚠️ 而 `Document/**` 与本报告**「工作树字节 == blob 字节」按设计不成立**，
故本波**不用那个判据**（正确判据是上面那一条双向可逆；
`Document/**` 那一份的正向取证是 `git hash-object` == index blob，
反向是 `checkout-index` 到空目录后**归一 CRLF**再比 —— 与 `schema.d.ts` 同一档）。
