# Plan 06 Task 8 实现者报告 —— 教师对「学生键资源」的泛型读收紧到任教范围

- **分支**：`p06/teacher-scope`（从 `main` 的 `601c79a` 起，**未 push、未碰 main**）
- **commit**：`d9f43bd`（①②后端）→ `d3fcb79`（③前端）→ `f6aab9d`（③smoke + gen:api）→ 本条（④spec + 报告）
- **口径**：交付给甲方的产品级系统。用户裁定「教师账号之间**要有数据隔离**」。
- **一句话结论**：`read_scope` 加了第四档 `staff_taught`，13 个学生键资源全部改成它；
  教师会话的泛型 list 从此在 **SQL 层**加 `WHERE <学生键> IN (我本学期任教的学生)`、
  read-one 走**既有那道** `require_teaches_student` → 403；管理员全读、学生与匿名两档逐字不变。
  `mini-tests/normalized` 的跨范围洞一并关掉（响应级裁班）。
  **openapi 五格一个字节都没变**。后端 1494 → **1497** passed（+1 skipped），
  `app/domain` 覆盖率 **1268/0/376/0/100%** 一字不退，smoke 两档各 **18 步 / 520 断言 / 退出码 0**。
  **顶回 5 处**（其中 1 处 Critical），**没按派单做的 1 处**。

---

## ① 环境

| 格 | 实测 |
|---|---|
| Node / npm | **v24.19.0** / **11.17.0**（开工第一件事跑的 `node --version; python --version`） |
| Python | **3.11.1**（无 venv，`C:\Python\python.exe`） |
| FastAPI / SQLAlchemy / alembic | 0.141.1 / 2.1.3 / 1.20.0（`serve.ps1` 的 ① 那一步逐字打印过 python 与 node 两格） |
| OS / shell | Windows，PowerShell 5.1（`;` 分隔、无 `&&`；`python -c` 里嵌双引号会被吃、f-string 表达式部分不能有反斜杠 → 一律写临时文件） |
| 后端服务 | `backend\scripts\demo.ps1 -Port 8000`（跑了 3 次：改前探针 / 改后矩阵 / smoke dev 档） |
| 产品档服务 | `scripts\serve.ps1 -Port 8020`（smoke 产品档；它自己判 dist 新鲜度，实测「dist 不比 src 旧 → 跳过构建」） |
| vite dev | `localhost:5173`（**不是本波起的**，PID 3260，绑 `::1`，全程没动它） |
| 改前基线取证 | `git worktree add $env:TEMP\pe_baseline 601c79a` + `PE_DB_URL` 指到 `pe_demo.db` 的**一份拷贝**，起在 **8001**；跑完 `git worktree remove --force` + 删掉拷贝（`git worktree list` 复核只剩主树与一个**不是本波的**旧 worktree `pe-baseline-e5efe6e`） |
| 演示库 | `demo.ps1` 重灌 **3 次**（每次都是 `[7/7]` 那一屏逐字核过的行数：semester 2 / student 60 / course_section 5 / enrollment 120 / prescription 60 / weekly_adjustment 13 / class_session 8 / rpe_record 240 / training_log 840 / mini_test 180 / alert 32 / notification 19 / weekly_class_report 5） |
| 探针 | 一律放 `$env:TEMP`（`pe_probe*.py` / `pe_probe*.mjs` / `pe_accept.py` / `pe_eol.py` / `pe_fix_eol.py` / `pe_commit.py`），写完 `py_compile`，收尾整批删掉并复验 |
| 禁区 | 全程没跑 `app.seed.generate` / `backfill` / `daily`；`backend/data/**` 一个字节没动（⑦ 那节逐字复核） |

---

## ② 任教判据的实测（派单 §0 要求「先实测每个教师任教哪些班」）

### 2.1 复用的是哪个函数（**单一所有者**）

改前「任教判据」在 `app/api/deps.py` 有两个**闸门**（都是 pure gate，返回 `None` 或抛 403）：

- `require_teaches_section(session, staff_no, course_section_id)` —— 判据 `course_section.teacher_id`，**不判学期**；
- `require_teaches_student(session, staff_no, student_id, semester_id)` —— 判据
  `enrollment ⋈ course_section.teacher_id` **且两行的 `semester_id` 都等于入参那一个学期**。

⚠️ **它今天的形状不适合被 SQL 子查询直接复用**（派单 §1 逐字点名要顶回的那一格）：
它是一个「查一次 `scalar` 看有没有行」的闸门，**不交出集合**。
**本波的处置不是顶回去等裁定，而是把它抽成一份可被两处共用的语句**（改造方案，已落地）：

```python
# app/api/deps.py（新）
def taught_section_ids(teacher_id, semester_id) -> Select:   # 「我在这个学期任教哪些班」
    return select(CourseSection.id).where(
        CourseSection.teacher_id == teacher_id,
        CourseSection.semester_id == semester_id,
    )

def taught_student_ids(teacher_id, semester_id) -> Select:   # 「我在这个学期能看见哪些学生」
    return select(Enrollment.student_id).where(
        Enrollment.course_section_id.in_(taught_section_ids(teacher_id, semester_id)),
        Enrollment.semester_id == semester_id,
    )
```

`require_teaches_student` 的函数体因此从「自己拼一条 JOIN」改成
`session.scalar(taught_student_ids(...).where(Enrollment.student_id == student_id).limit(1))`
——**判据一个字没变**（守卫 `test_teaching_last_semester_does_not_grant_access_this_semester`
与它的 `/home` 那一条照旧绿），而形状从「点查」变成「点查 = 集合查询 + 一个等值条件」。

于是**三个消费者读的是同一条语句**：① `require_teaches_student`（教师侧两个特例端点的 403）；
② `crud._taught_filter`（泛型 list 的 `WHERE`）；③ `feedback.normalized_scores`（裁班）。
配套把 `_teacher_id_of` 提成公开面 `teacher_id_of`（`crud` 要「工号 → `teacher.id`」去拼子查询，
自己再写一句 `select(Teacher.id)` 就是这一格的第二个所有者），并同步了
`app/auth/sessions.py::teacher_by_login` docstring 里那一处引用。

⚠️ **「哪一个是本学年」也只有一个所有者**：`app.pipeline.percentile_stage.current_semester_of`
（优先 `is_current`、退化到「包含那一天的学期区间」、都找不到就响亮失败）。
本波在 `crud._current_semester_id(session)` 里调它、传 `dt.date.today()`
（泛型 list **没有** `as_of` 查询参数；给它加一个 = 26 个 GET 各多一个参数进 OpenAPI
而前端一个都不传，故不加，如实记）。⚠️ `api → pipeline` 是许可方向
（`test_layering.API_ALLOWED_PREFIXES` 里 Plan 03 就列进去了），
而 `app/api/routers/dashboard.py` 已经是它的消费者，故本波是**第二个**、不是新开的一格。

### 2.2 三个教师各任教哪些班 / 可见学生数（演示库、`course_section.teacher_id` + `enrollment`，从 API 与从库里两侧各测一遍，数字一致）

| 工号 | 姓名 | `role` | `teacher.id` | 任教的班（本学期 = `semester 2`，`is_current=1`） | **可见学生数** |
|---|---|---|---|---|---|
| **T0001** | 陈国华 | `teacher` | 1 | **班 1（行政班01，30 人）+ 班 3（提升班，20 人）** | **41 / 60** |
| **T0002** | 林慧敏 | `teacher` | 2 | **班 2（行政班02，30 人）+ 班 4（强化班，20 人）** | **42 / 60** |
| T0003 | 赵志刚 | **`admin`** | 3 | 班 5（拓展班，20 人） | 20（⚠️ 但**管理员越过任教范围** → 全读 60） |

- 5 个班全在 `semester 2`；`enrollment` 120 行 = 60 人 × **每人恰好 2 个班**（行政班 + 分层班），
  故「一个学生可能在多个班」在演示库上是**普遍**而不是边缘。
- **T0001 ∩ T0002 = 23 人**；只在 T0001 = **18**；只在 T0002 = **19**（41 + 42 − 23 = 60 ✓）。
  于是「教师别人班」那一档在演示库上**有 19 / 18 个真反例**，不是造出来的。
- ⚠️ **派单 §0 写的「T0001 陈国华（带班 1 与班 2）」与实测不符**：他带的是**班 1 与班 3**。
  「T0002 林慧敏不带班 1」这半句实测**成立**（她带班 2 与班 4）。
  本波一律按实测口径写守卫与文案（`AlertQueue.vue` 的「我任教的班」那一档本来就是
  按 `teacher_id == 我` 现算的，不依赖任何写死的班号）。
- ⚠️ 派单 §0 还写了「学生 `2023120001`（id 4，**在班 1**）」——实测学生 4 在**班 2 与班 4**
  （即 T0002 的班里），**不在** T0001 的范围里。这一格恰好是有用的：
  `smoke.mjs` 第 7 步本来就断言「学生 4 不在 T0001 本学期任教的班里 → 403」。

---

## ③ 四档矩阵（派单 §4 第 1 条）

### 3.1 pytest 侧：**13 个资源全做**（派单要求「至少抽 4 个」）

守卫 `tests/api/test_crud.py::test_the_student_keyed_resources_admit_four_read_tiers`：
16 个非匿名资源（13 个 `staff_taught` + 3 个 `staff`）× 两个 GET × **六档身份** = **168 发**实发请求，
逐格断**状态码 + `total` + `items` 的 id 清单**。夹具是「每表一行」，故全做的成本与抽 4 个同阶。
派单点名的 4 个（`training-logs` / `alerts` / `body-compositions` / `notifications`）
由一条 `assert {…} <= {…}` 钉住「确实在被测名单里」。

| 档 | 身份（夹具） | list | `total` | read-one |
|---|---|---|---|---|
| ① 匿名 | 无头 | **401** `unauthenticated` | — | **401** |
| ② 学生自己 | `X-Student-Id: <seeded 学生>` | 200 | **1** | **200** |
| ③ 学生别人 | `X-Student-Id: <第二个在册学生，刻意不编班>` | 200 | **0**（`items == []`） | **403** `forbidden` |
| ④ **教师自己班** | `teaching_teacher_headers` = `T2025001`（**新夹具**：`_seed_one_row_per_table` 里那位教师，真的教 `seeded["course_section"]`，而 `seeded["student"]` 就选在那个班里） | 200 | **1** | **200** |
| ⑤ **教师别人班** | `plain_teacher_headers` = `T2025901`（既有夹具：**不教任何班**） | 200 | **0**（`items == []`） | **403** `forbidden` |
| ⑥ 管理员 | `admin_headers` = `T2025900`（`role='admin'`） | 200 | **1** | **200** |

⚠️ ④⑤ 两档是**两个不同的夹具**，少任一个都会静默：只有 ④ → 「第四档整个没生效
（教职照旧全读）」是绿的；只有 ⑤ → 「第四档收成了『教师一律看不到』」是绿的
（而那会让 Plan 04 的教师端整个不可用）。
⚠️ ③⑤ 的 `total == 0` 那一格是「过滤在 **SQL 层**」的直接证据：
若实现是「拉全量再在 Python 里筛」，`total` 会是全表计数（1）。
⚠️ ⑤ 的 read-one 还点名断了 message 里带「不在教师 … 任教的」与那个工号 ——
于是「泛型读换了一份自己的判据、而它与 `require_teaches_student` 漂了」会红在这里。
⚠️ `staff` 那 3 个资源（`students` / `teachers` / `weekly-class-reports`）在本条里只断两格
（匿名 401 + 学生身份被拒，后者在请求头通道下实测是 **401** 而不是 403），
外加**两位**教师都 200 —— 那一格正是 §⑥ 顶回 2 的取证点。

### 3.2 真 HTTP 侧（演示库、**cookie 通道**、`demo.ps1` 刚重灌的库）

13 个资源 × 5 档身份的 `total`（list）；read-one 用「学生 1 的行（∈ T0001）」与「学生 2 的行（∉ T0001、∈ T0002）」两行取样：

| 资源 | 匿名 | 学生 #4 | **教师 T0001（41 人）** | 教师 T0002（42 人） | 管理员 T0003 | 全表 |
|---|---|---|---|---|---|---|
| `training-logs` | 401 | 14 | **574** | 588 | 840 | 840 |
| `rpe-records` | 401 | 4 | **164** | 168 | 240 | 240 |
| `mini-tests` | 401 | 3 | **123** | 126 | 180 | 180 |
| `body-compositions` | 401 | 4 | **164** | 168 | 240 | 240 |
| `fitness-test-results` | 401 | 4 | **164** | 168 | 240 | 240 |
| `prescriptions` | 401 | 1 | **41** | 42 | 60 | 60 |
| `enrollments` | 401 | 2 | **82** | 84 | 120 | 120 |
| `interest-surveys` | 401 | 2 | **82** | 84 | 120 | 120 |
| `derived-metrics` | 401 | 2 | **82** | 84 | 120 | 120 |
| `stratification-results` | 401 | 2 | **82** | 84 | 120 | 120 |
| `weekly-adjustments` | 401 | 0 | **9** | 8 | 13 | 13 |
| `alerts` | 401 | 1 | **21** | 23 | 32 | 32 |
| `notifications` | 401 | 1 | **12** | 15 | 19 | 19 |

read-one（真 HTTP、cookie 通道）：

| 资源 | T0001 读**学生 1**（在他班里） | T0001 读**学生 2**（不在） | T0002 读学生 2 | 管理员读学生 2 |
|---|---|---|---|---|
| 12 个直接键 + 间接键资源（`enrollments` / `fitness-test-results` / `body-compositions` / `interest-surveys` / `derived-metrics` / `stratification-results` / `prescriptions` / `weekly-adjustments` / `rpe-records` / `training-logs` / `mini-tests` / `alerts`）**逐个实测** | **200** | **403** | **200** | **200** |
| `notifications` | 演示库 19 行全部发给学生 6/9/… 一类，学生 1 与 2 都没有行 → 这一格由 pytest 的夹具行覆盖（④ 200 / ⑤ 403） | — | — | — |

⚠️ **改前基线（`601c79a`，worktree 起在 8001、库是 `pe_demo.db` 的一份拷贝）逐字对照**：

| 资源 | 改前 教师 T0001 | 改前 管理员 | 改后 教师 T0001 |
|---|---|---|---|
| `training-logs` | **841** | 841 | **574** |
| `alerts` | **32** | 32 | **21** |
| `prescriptions` | **60** | 60 | **41** |
| `enrollments` | **120** | 120 | **82** |
| `notifications` | **20** | 20 | **12** |
| `mini-tests` | **180** | 180 | **123** |
| `body-compositions` | **240** | 240 | **164** |
| `rpe-records` | **241** | 241 | **164** |
| `weekly-adjustments` | **13** | 13 | **9** |

⚠️ 改前那一列的库是**跑完一次 smoke 之后**的拷贝（故 `training-logs` 是 841 而不是 840、
`rpe-records` 241、`notifications` 20：第 6 步打了一次卡、第 5 步交了一条快评、
第 9 步处置预警推了一条站内信），改后那一列是**刚重灌**的库。
⚠️ 而对照的**判据与库的脏净无关**：改前「教师档 == 管理员档」逐格成立（= 教职全读），
改后「教师档 < 管理员档」逐格成立。
⚠️ 改前 read-one：T0001 读**学生 4**（不在他班里）的 `training-logs/43`、`prescriptions/4`、
`body-compositions/4`、`alerts/3` —— **四个各 200**；改后同一格是 **403**。

### 3.3 `total` 过滤断言（派单 §4 第 3 条）

- **pytest**：④⑤⑥ 三档逐格断 `total`（1 / 0 / 1）与 `items` 的 id 清单。
- **smoke 第 12 步 ⑦（本波新加）**：`/api/training-logs` 教师档 `total` = **574**、
  管理员档 = **841**；`/api/alerts` 教师档 = **21**、管理员档 = **32**；
  教师档每一行的 `student_id` 都在第 7 步算出来的任教名册里；
  且 `LIMIT` 作用在**已过滤**的行上（`training-logs` 那一支 `items` 满 200 ——
  若实现是先 `LIMIT 200` 再在 Python 里筛，教师档只会拿到约 137 行而 `total` 还是 840）。
  ⚠️ 管理员档是 **841** 而不是 840：第 6 步用学生 4 的头自己打过一次卡，
  而学生 4 不在 T0001 的任教范围里（第 7 步逐字断言过），故教师档仍是 **574**。
  这一对数字同时钉住「第四档生效了」与「第 6 步那次写入落在了谁身上」。
- **先实测该数**（派单要求）：`SELECT COUNT(*) FROM training_log WHERE student_id IN (T0001 的 41 人)` = **574**
  （直接从库里数）与 HTTP 的 `total` = **574** 两侧一致；全表 **840**；T0002 是 **588**。

### 3.4 定点变异（派单 §4 第 2 条：「去掉那个 IN 子查询 → 守卫红」）

| 变异 | 改法 | 结果 |
|---|---|---|
| **M1** | `crud._taught_filter` 里 `taught = taught_student_ids(...)` → `taught = select(Base.metadata.tables["enrollment"].c["student_id"])`（= 去掉「任教范围」那个条件，教师档退化成全读） | **2 条红**：`test_the_student_keyed_resources_admit_four_read_tiers`（红在 `('⑤ 教师别人班', '/api/enrollments', 1, 'total 没有跟着过滤…')`）+ `test_the_student_self_tier_still_behaves_as_staff_full_read`（红在 `staff_taught` 那个合成探针的 `total`） |
| **M2** | 去掉 `taught_section_ids` 里的 `CourseSection.semester_id == semester_id` | **0 条红** |
| **M2b** | 去掉 `taught_student_ids` 里的 `Enrollment.semester_id == semester_id` | **0 条红** |
| **M2c** | 两个 `semester_id` 条件**一起**去掉 | **2 条红**：`test_teaching_last_semester_does_not_grant_access_this_semester` 与 `…_to_the_home_page`（各 `assert 200 == 403`） |

⚠️ **M2 / M2b 各自不红是一格已知边界，如实记**（已写进 `taught_student_ids` 的行内注释）：
既有夹具造的是「**上学期**的班 + **上学期**的选课行」，两个条件各挡住一半、互相冗余，
故单独去掉任一个都被另一个兜住。`Enrollment.semester_id` 那一格**单独**承重的形状是
「一条上学期的选课行指向一个**本学期**的班」（库层面可写：两列各自都是合法外键），
而本仓今天没有那样的夹具。三次变异跑完**逐字还原**（`Grep MUTATION` 全仓 0 命中）。

### 3.5 遍历守卫同步（派单 §0 逐字点名）

`test_every_student_keyed_resource_declares_a_non_null_read_scope`
→ **改名 + 收紧**成 `test_every_student_keyed_resource_declares_a_student_scoped_read_scope`：
判据从「`read_scope is not None`」换成「`read_scope in STUDENT_SCOPED_READ_VALUES`」。
⚠️ 改前那条对第四档**不是**视而不见（`staff_taught` 也非 `None`，故它仍然绿），
但它**放过了一个更坏的档**：把一张含 `student_id` 列的表声明成 `"staff"`
（= 任何在册教师全校全读）在改前是**绿的**，而那正是本波要消灭的失效形态。
`STUDENT_SCOPED_READ_VALUES = {student_self, staff_taught}` 是「哪两档要 `student_owner`」的
唯一住址，工厂第 9 / 10 道校验、`read_guarded` 的 scheme 声明、端点分支的 `if`、
以及 `test_every_resource_declares_read_scope_explicitly` 的反向钉（`student_owner` 只在两档出现）
**全部**读它 —— 改前那 4 处逐字写的是 `== READ_SCOPE_STUDENT_SELF`。
行数分布守卫改名成 `…_seven_zero_thirteen_and_three`（**7 / 0 / 13 / 3**，字面写死）。

---

## ④ `mini-tests/normalized` 的三档范围（改前 / 改后逐字实测）

⚠️⚠️ **先说一处顶回**：派单 §2 写的处置是「学生只能请求自己 enrolled 的班（**否则 403**）/
教师只能请求自己任教的班（**否则 403**）」。实测下**那一格无对象**：
本端点的签名逐字只有 `semester_id` + `week` 两个查询参数，
**没有** `course_section_id` —— 故不存在「请求某一个班的班内百分位」这个动作，
它一次就把**全校全部**教学班都回了。于是本波改成**响应级裁班**（裁 `sections` 数组），
不是 403。派单 §2 那句「教师可以请求任意 `course_section_id` 的班内百分位」因此也不成立
（正确的说法是「教师可以**读到**任意班的班内百分位」）。

### 4.1 改前（`601c79a`，8001，同一份库拷贝）

`GET /api/mini-tests/normalized?semester_id=2&week=6`：

| 身份 | status | `sections` | `unassigned` | 首行 `squat_score` / `composite` |
|---|---|---|---|---|
| 匿名 | **401** | — | — | — |
| 学生 4 | 200 | **班 1(30) / 2(30) / 3(20) / 4(20) / 5(20) —— 全 5 个** | 0 | `null` / `null`（列级收窄在） |
| 教师 T0001 | 200 | **全 5 个** | 0 | `26` / `20.5` |
| 教师 T0002 | 200 | **全 5 个** | 0 | `26` / `20.5` |
| 管理员 T0003 | 200 | **全 5 个** | 0 | `26` / `20.5` |

即：**任何登录身份都读到全校 5 个班的逐人百分位**；学生档只有列级收窄（别人的
`squat_score` / `composite` 是 `null`），而 `shuttle_score` + `student_id` + `mini_test_id`
三格全班照给；教师档连原始值（`squat_score` = 30 秒深蹲次数）也全给。

### 4.2 改后（本分支，8000，刚重灌的库）

| 身份 | status | `sections` | `unassigned` | 首行 `squat_score` / `composite` |
|---|---|---|---|---|
| 匿名 | **401** | — | — | — |
| 学生 4 | 200 | **班 2(30 人/sc30) / 班 4(20 人/sc20)** —— 只他自己 `enrollment` 的 2 个 | 0 | `null` / `null`（列级收窄照旧） |
| 学生 5 | 200 | **班 2 / 班 4**（他也在 T0002 的两个班里） | 0 | `null` / `null` |
| 教师 T0001 | 200 | **班 1(30/sc30) / 班 3(20/sc20)** —— 只他任教的 2 个 | **0**（恒为空） | `26` / `20.5` |
| 教师 T0002 | 200 | **班 2(30/sc30) / 班 4(20/sc20)** | **0** | `39` / `52` |
| 管理员 T0003 | 200 | **全 5 个班** | 0 | `26` / `20.5` |

三档判据各自**复用既有的唯一所有者**：学生 → 端点里本来就查的那张
`sections_of`（`enrollment` 按 `semester_id` 查出来的）；教师 → `deps.taught_section_ids`
（与第四档同一条语句）；管理员 → `ReaderIdentity.is_admin`。
⚠️ **整班一起留或一起走**（不裁班里的人）：百分位是**班内**的，裁掉几个人会让留下来的人的
`shuttle_score` 与名次全都变，而响应体上看不出它被裁过 —— 那是一次静默的算式漂移。
⚠️ **列级收窄照旧保留**（行级与列级是两件不同的事）：学生档别人的 `squat_score` /
`composite` 仍然是 `null`，`shuttle_score` 照常给（`MiniTest.vue` 要它算名次）。
⚠️ **`unassigned` 对教师恒为空**：它的定义（本学期**没有任何** `enrollment` 行）与
「我任教的学生」的定义（在我任教的班里**有一条** `enrollment` 行）**必然不相交**，
故一个没编班的学生对任何教师都不在任教范围里，留给谁都是越权。
代价如实记：「把『选课记录漏了一条』摆到教师面前」这个用途只剩**管理员**能兑现
（要还给教师得先有「哪个教师管哪个院系/年级」这一格，本仓没有）—— 已登记为待清扫。

### 4.3 `MiniTest.vue` 是否真的不用改 → **实测：不用改，一行都没动**

派单 §2 的预测成立。判据（逐字读代码 + 真 DOM 取证两侧）：
`MiniTest.vue` 的 `mySections` 是 `for (const section of n.sections) { const entry =
section.entries.find(e => e.student_id === id); if (!entry) continue; … }` ——
它本来就**只挑「里面有我这一行」的班**，故裁掉别人的班对它渲染出来的东西**一个字节都不影响**；
`unassigned` 那个 computed 也只判「我在不在里面」。
它请求的是 `getNormalizedScores({ semesterId: home.semester_id, week })`，
而 `home` 来自 `GET /api/students/{id}/home`（学生自己的），故**学期与周次都是他自己的**，
不存在「请求的班学生不在其中」那一档（派单要求顶回的那一格**没触发**）。
⚠️ 而**教师页 `StudentDetail.vue` 也不用改**（同一个 `mySections` 形状）：
它读的是同一个端点，裁班之后对**他任教的班**照旧给全份 entries。
本波只改了它一处**注释**（那段举例说「学生 1 在班 1 与班 5 各有一行」，
而教师会话今天只留自己任教的班 → 在 T0001 的屏幕上只剩班 1 那一行）。
⚠️ 而**没编班的学生**那一档确实变了：改前他能看到那个班的 3 行（两格原始值 `null`），
改后 `sections == []`。前端仍然不用改：`mySections` 挑不到就不渲染，
而 `unassigned` 那一块会把「你没编班」讲出来 —— 对用户是同一屏。
守卫 `test_a_student_session_reads_the_whole_class_percentile_but_no_raw_squat_count` 的
⑤ 那一拍已按此改写（并逐字记了「前端一行不用改」的理由）。

### 4.4 新增守卫

`tests/api/test_feedback.py::test_normalized_scores_is_scoped_to_the_sections_the_reader_may_see`
（**六拍**）：自己插一位**第二个教师** `T2025002` + **第二个班** + 把原本没编班的那个人编进班 2，
于是每一档的期望侧都**非空**（一个恒空的断言没有判别力）：
① 管理员 → **2 个班**；② 教师 A → **只有班 1**；③ 教师 B → **只有班 2**
（②③ 互为红档：写成「教师一律全读」两拍一起红、写成「教师一律空」也一起红）；
④ 学生 → **只有他 `enrollment` 的那个班**；⑤ 同一个班在学生档与教师档**行数与
`scored_count` 逐字相同**（裁的是班、不是班里的人）；⑥ **点名**断言教师 B 的响应里
没有班 1 的任何一行（不靠 ①②③ 的集合差推）。

---

## ⑤ 前端改动清单

| 文件 | 改了什么 | 为什么 |
|---|---|---|
| `frontend/src/components/TeacherNav.vue` | 第 4 格从**一级**（全校 60 人）改成 **班 → 学生 两级**：两个 `<select>` + 一行范围小字（`我任教的 2 个班 / 50 人次`；管理员是 `管理员 · 全部 5 个班 / 120 人次`）；第二级空时 `disabled` 并写「这个班没有选课记录」；新增 `watch(route.params.studentId)` 让下钻进来时两级同步 | 改前它的名单来自 `GET /api/students`（`read_scope="staff"` = 教职全读，**没有**跟着收），于是它列全校 60 人、而其中 **19 个**点进去只会渲染 403 面板 —— 一个「列出来但点不开」的下拉框是一句谎话 |
| `frontend/src/views/teacher/AlertQueue.vue` | ① 页头新加一行 `<p class="t-head__scope">`「⚠️ 范围：**我本学期任教班级的学生**（不是全校）…」；② 空态标题从「alert 表是空的」改成「我这个范围里一条预警都没有」+ 第三种成因；③「归属 → 班级级」那一档的空态说明补上**第二个**理由；④ `t-block__why` 里「实测 30 行」更正成 32 行；⑤ 文件头那份「读的端点」清单从「**匿名** / 30 行全量」更正成实测口径；⑥ 新增一条 scoped `.t-head__scope` 样式（一个色值都不写死） | 「共 N 条」里的 N 从 32 变成 21，不说清的话两位教师在同一屏上会看到两个不同的 N 而无从判断谁对；改前那句「alert 表是空的」在收窄之后是**假话** |
| `frontend/src/views/teacher/StudentDetail.vue` | **只改一处注释**（`mySections` 那段举例） | 逻辑一行都不用改：它是路由驱动的（`/t/students/:studentId`），自己不带学生选择器，而它读的 3 个泛型 list 本来就在客户端按 `student_id` 过滤 |
| `frontend/scripts/smoke.mjs` | 见下 | — |
| `frontend/src/api/generated/schema.d.ts` | `npm run gen:api` 的产物（+588 / −4 行） | 两个泛型端点的 `description` 随第四档改了 → standing 验收项要求重跑 |

**「我的学生」的来源：一个新端点都没加**（派单 §3 第 1 条要求「优先复用既有特例端点」）。
⚠️ **实测 `/api/teacher/students/*` 那一族只有 2 个端点**（`weekly-sheet` 与 `home`），
两个都是**按人**的（`{student_id}` 路径参数），**没有**「我的学生」那一格 →
派单说的「优先复用」**无对象**，已顶回（§⑥ 顶回 3）。
两级名单因此由 **4 个既有端点**拼出来：`listTeachers`（工号 → `teacher.id`）/
`listCourseSections`（`teacher_id == 我` 的班）/ `listEnrollments`
（⚠️ **它自己已经收窄了**，故第二级不需要在前端再筛一次人）/ `listStudents`（学号 + 姓名）。
⚠️ **管理台不受影响**：`ResourceList.vue` 走管理员会话（`session.isAdmin`），
那一档不过滤，故它照旧是全校视图；`TeacherNav` 的第一级对管理员也列**全部**班，
于是同一个人在 `/t/*` 与 `/admin/*` 两侧看到同一份名单。
⚠️ 第一级「哪个班是我的」在前端是**展示**判据（与 `AlertQueue.vue` 的 `mySections`、
`ClassReport.vue` 的「只列我任教的」同一条，三处各写一遍是本仓既有的口径），
**授权**判据仍然只在后端 `deps.taught_section_ids`。

**文案改了几处**：**5 处**（AlertQueue 的 ①②③④⑤）+ TeacherNav 的范围小字 **1 处** = **6 处**。
⚠️ 派单 §3 说「页面文案若写了『全校』要改（先 `Grep`）」—— 实测 `frontend/src` 里
**一处「全校」都没有**（`Grep -n "全校" frontend/src` 0 命中；命中的只有
`backend/app/api/schemas/organisation.py` 与 `schema.d.ts` 的注释），
故改的是「共 N 条」那一格的**含义**说明，不是一个既有词。

**smoke needle 改了几处**：**5 处**（第 0 步那 5 个学生键资源的身份从 `'teacher'` 换成
`'admin'`，算 1 处；第 7 步那段「本拍要的是**全校**的选课关系」的注释更正 + 存
`SHARED.taughtStudents`，算 1 处；第 12 步 ⑥ 的说明文字，算 1 处；第 12 步**新加 ⑦** 一组，
算 1 处；第 13 步 normalized 那一组从 8 拍扩到 22 拍，算 1 处）。
⚠️ **按 #88 做的**：先跑全量收进来（改前实测红 **6** 条：第 0 步 5 条 + 第 12 步 1 条），
再逐格改；**判据本身一个字都没改**（第 0 步的期望值仍然是 19 / 60 / 840 / 240 / 32，
改的只是「用谁的身份数」；第 12 步 ⑥ 的判据仍然是 `status === 200`；
第 13 步列级收窄的三拍判据不变，只把**基准**从教师档换成管理员档 ——
因为教师档自己已经成了被裁的那一侧，拿它当基准会让「裁班」这件事无从对照）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 6.1 顶回（**5 处**，其中 **1 处 Critical**）

**顶回 1（⚠️ Critical）—— 第四档把「没有学生所有者的行」一并挡掉了，包括教师自己班的。**
`staff_taught` 的判据是**学生键**，故：

- **班级级预警**（`alert.student_id IS NULL` + `course_section_id` 非空）对**任何**教师不可见，
  包括它自己那个班的任课教师 —— 只有管理员读得到。`NULL IN (…)` 在 SQL 的三值逻辑下恒不成立；
  read-one 那一侧 `_owner_of_row` 给出 `NOT_STUDENT_OWNED`（`-1`）→ `require_teaches_student` 403。
- **发给教师的站内信**（`notification.recipient_kind='teacher'`）同理。

⚠️ **两者都是生产路径会产出的形状**（不是理论边缘）：
`app/pipeline/alert_stage.py:1318-1361` 逐字有一个「班级级：全量遍历本学期的教学班」的循环，
命中 `domain.alerts.evaluate_class` 的规则时写 `student_id=None, course_section_id=section_id`，
并顺带 `_notify(recipient_kind=RECIPIENT_TEACHER, recipient_id=teacher_id)`。
⚠️ **演示库上两者实测各 0 行**（唯一的班级级规则 `YELLOW_CLASS_RPE_HIGH` 的阈值是
班级 RPE 均值 > 7，实测 5 个班最高 **6.93**，差 0.07 没越线；19 条站内信全部
`recipient_kind='student'`），故既有的 1497 条测试与 `smoke.mjs` 的 520 条断言
**都看不见这一格**。
⚠️ 于是它是一格**功能回归**且**失效方向是静默的**（响应 200、只是少一行）：
教师看不到本该他处置的班级级预警，而 `AlertQueue.vue` 的「归属 → 班级级」那一档筛选
从此对教师**恒为空**。
**为什么本波没修**：修它要给 `StudentOwner` 加**第二根轴**（「没有学生所有者时按哪一列判」），
而两个资源的形状还**不同**（`alerts` 是 `course_section_id` → 该走 `require_teaches_section`；
`notifications` 是 `recipient_id` + `recipient_kind='teacher'` → 该判「recipient 是不是我」），
read-one 那一侧也要跟着分岔 —— 那是一次**设计改动**（把「学生键」扩成「行所有者有三种」），
不是一次一行改动。**处置**：① 按派单口径实现；② 用一条守卫把它**钉住**
（`test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin`，
四拍：管理员 200 + list 含它 / 任课教师 403 + list 不含它 / 两格反空转），
于是将来有人修它会**先看到那条守卫红**；③ 页面上把两个理由都写出来（AlertQueue 的空态说明）；
④ 写进 spec §1.2 第 17 条与 `crud._taught_filter` 的 docstring。
**请控制者裁定**：本波就加第二根轴，还是留到 Plan 06 Task 9 的清扫席。

**顶回 2 —— `weekly-class-reports` 确实能让教师读到别的班的 `progress_board`（派单 §1 末段点名要复核的那一格，答案是「是」）。**
它是 `read_scope="staff"`（任何在册教职全读），而泛型 **read-one 含全部 JSON 列**。
**实测取证**（演示库、T0001 的 cookie，他只任教班 1 与班 3）：
`GET /api/weekly-class-reports/{1..5}` **五个各 200**，班 2 的 `progress_board.top` 开头逐字是
`[{"student_id":48,"change_pct":188.53},{"student_id":47,"change_pct":165},{"student_id":13,"change_pct":154.71}]`，
班 4 的是 `[{"student_id":47,"change_pct":208.96},{"student_id":10,"change_pct":174.71},{"student_id":9,"change_pct":85.44}]`
—— 外加 `layer_distribution` / `completion_rate_by_layer` / `alert_summary` 三个聚合列。
⚠️ **改前改后逐字相同**（本波按派单要求没动它，基线 worktree 上同一组请求也是 5 × 200）。
⚠️ **前端页面上看不出这一格**：特例端点 `GET /api/dashboard/weekly-class-report/{id}` 有自己的
`require_teaches_section`，且 `ClassReport.vue` 的选班下拉逐字写着「只列我任教的」——
泄漏面是 **API**，不是 UI。⚠️ 而 list 那一格**不含** `progress_board`
（`JsonText` 列被 `list_exclude` 自动排掉），故只有 read-one 泄漏。
**处置**：派单逐字要求「保持 `staff` 档不动」→ **照办**，并已把取证写进
`catalog.RESOURCES` 那一行的注释与 spec §1.2 第 18 条。
**收它的方案（供裁定）**：第五档 `"staff_taught_section"` =
`WHERE course_section_id IN (我本学期任教的班)`，形状与第四档同构、判据同样复用
`deps.taught_section_ids`；⚠️ 而它**不能**复用 `StudentOwner`（那是学生键的声明），
故要么给它一个平行的 `SectionOwner`，要么把 `StudentOwner` 泛化成「行所有者声明」。
⚠️ 另一条路是**拆子表**（把 `progress_board` 拆成 `progress_board_entry`），
那样它就自动落进「含 `student_id` 列 ⇒ 必须按学生键收窄」那条遍历守卫里 ——
而拆子表本来就是安全收紧波登记的待清扫项。

**顶回 3 —— 「我的学生」选择器复用不了 `/api/teacher/students/*`（派单 §3 第 1 条的前提不成立）。**
派单写的是「**优先复用既有特例端点**（`/api/teacher/students/*` 那一族，先 `Grep` 实测它们返回什么、
有没有任教闸门）；若没有合适的，顶回来再讨论是否加端点」。
**实测**：那一族只有 **2 个**端点 —— `GET /api/teacher/students/{student_id}/weekly-sheet`
与 `GET /api/teacher/students/{student_id}/home`，两个都是**按人**的
（路径参数就是 `student_id`），响应模型是 `WeeklySheetRead` / `StudentHomeRead`，
**都不是名单**；两个都挂 `require_teaches_student`（有任教闸门）。
`dashboard.py` 那 6 个端点里也没有「我的学生」那一格
（`/api/dashboard/class/{id}` 是**按班**的一屏聚合，`ClassDashboardRead` 不含逐人名册）。
**处置**：**没有加端点**（openapi 五格因此一个字节都没变），两级名单改由 4 个既有泛型端点拼出来
（逐字清单见 §⑤）。⚠️ 代价如实记：`TeacherNav` 挂载时要发 **4 发**请求
（改前 1 发），而 4 个都是一页就够的 list（教师 3 行 / 班 5 行 / 选课 120 行 / 学生 60 行，
都在 `limit=200` 之内）。⚠️ **人数上到 100 人以上时 `enrollments` 那一页要改成翻页收集** ——
与 `AlertQueue.vue` / `Dashboard.vue` 既有的同一条待清扫（下面 6.2 第 4 条）。
**请控制者确认**：是接受「4 发拼一个选择器」，还是要一个窄端点
（`GET /api/teacher/students?semester_id=` 一类，⚠️ 那会让 openapi 五格变）。

**顶回 4 —— 派单 §2 对 `normalized` 的处置形状（「否则 403」）在实测下无对象。**
本端点**没有** `course_section_id` 这个查询参数（签名逐字只有 `semester_id` + `week`），
故不存在「请求某一个班」这个动作。派单同一段的「教师可以请求任意 `course_section_id` 的
班内百分位」也应读成「教师可以**读到**任意班的班内百分位」。
**处置**：改成**响应级裁班**（§④），并在 `normalized_scores` 的 docstring 里逐字记了这次顶回。
⚠️ 若控制者更想要 403 那一形，就得先给它加一个 `course_section_id` 查询参数
（= openapi 的参数面变一格、前端两个调用方各多传一个参数），本波**没做**。

**顶回 5 —— 派单 §0 的两处账号事实与实测不符（不影响结论，但会影响照着它写的守卫）。**
① 「教师 `T0001` 陈国华（带班 **1 与班 2**）」→ 实测带的是**班 1 与班 3**
（班 2 是 T0002 的）；② 「学生 `2023120001`（id 4，**在班 1**）」→ 实测在**班 2 与班 4**。
**处置**：一律按实测口径写守卫与文案；两处更正都写进了 §②。
⚠️ 而 ② 那一格恰好是**有用**的：`smoke.mjs` 第 7 步本来就断言
「学生 4 不在 T0001 本学期任教的班里 → 403」，故它今天仍然是那一档的真反例。

### 6.2 待清扫（**新增 4 条**，均已写进代码注释或 spec）

1. **班级级预警 / 教师站内信对教师不可见**（= 顶回 1）。修它要给 `StudentOwner` 加第二根轴。
   守卫已钉住（`test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin`）。
2. **`weekly-class-reports` 跨教师**（= 顶回 2）。修它要第五档或拆子表。
3. **`normalized` 的 `unassigned` 对教师恒为空**：要把它还给教师，得先有
   「哪个教师管哪个院系/年级」这一格（本仓没有）。已写进函数体注释 + spec §1.2 第 14 条。
4. **前端 4 处 `limit: 200` 的单页假设**（`TeacherNav.vue` 新加的那一处 + 既有的
   `AlertQueue.vue` / `Dashboard.vue` / `ClassReport.vue`）：人数上到 100 人以上要改成翻页收集。
   ⚠️ 教师档的 `enrollments` 因为**自己已经收窄了**，反而比改前更不容易溢出（82 行 vs 120 行）。
5. ⚠️ **两个 `semester_id` 条件在既有夹具上互相冗余**（M2 / M2b 各自不红，M2c 才红）：
   要分开钉就得再造一个「选课行的 `semester_id` 与班的 `semester_id` 不一致」的夹具。
   已写进 `taught_student_ids` 的行内注释。
6. ⚠️ **`gen:api` 的产物在 HEAD 上先前就漂了 3 行**（`/api/health` 那段 description 里的
   「27 张表」与那个测试名，是 Plan 06 Task 5 之后没重跑 `gen:api` 留下的）：
   本波重跑时**顺带收进来了**（不是本波改的）。⚠️ 这说明「改了会进 openapi 的 docstring
   就要重跑 `gen:api`」这条 standing 验收项在 Task 5 那一波**漏了一次**，
   而没有守卫抓得到（`smoke` 第 12 步 ⑤ 钉的是「24 个未定型响应」，不是「产物与 openapi 逐字相同」）。
   **建议**：给 `smoke` 加一拍「`schema.d.ts` 里那段 description 与 `/openapi.json` 逐字相同」，
   或把 `npm run gen:api` + `git diff --exit-code` 变成一条守卫。

### 6.3 关切（不改，如实记）

1. **教师那一档每个请求 +2 次点查**（`teacher.id` 与「本学年」）+ 1 个子查询。
   两次都是唯一索引/主键上的点查，且**只在教师会话的第四档读上**发生
   （学生与管理员两档都不调 `_current_semester_id`）。⚠️ 而 `current_reader` 的**教职那一档
   从此一律查库**（`require_staff`）—— 包括 cookie 通道，改前它刻意不查
   （「`resolve` 已经回查过 subject 行」）。改的理由是 `role` **必须新鲜**：
   `user_session.role` 是登录时冗余存的那一份，读它的话一个被降级的管理员在会话过期前
   仍然全读全校，而**写入侧**（`require_admin`）已经当场拒绝他了 —— 两侧会给出两个口径。
   代价是教职会话的每一次泛型读多一次 `teacher` 表上的索引点查。
2. **`_current_semester_id` 传的是 `date.today()`，而两个特例端点传的是 `as_of`**。
   差别只在「库里没有 `is_current` 的学期」那一档（那时 `current_semester_of` 退化到
   「包含那一天的区间」）。⚠️ 生产路径上**不可达**：演示库实测恰好一行 `is_current=1`
   （`id=2`），故第一档就命中、`today()` 根本不参与判定。⚠️ 而「找不到本学年」那一档
   `current_semester_of` 是**响亮失败**（`ValueError` → 500），改前它只影响教师侧两个特例端点，
   改后会影响 13 个资源的教师档 list —— 这是本波**新引入的一个 500 面**，如实记。
   要收它就得给泛型 list 加一个 `as_of` 查询参数（26 个 GET 各多一格进 OpenAPI，前端一个都不传）。
3. **`student_self` 那一档今天 0 行**（13 行全部改成 `staff_taught`）。
   **刻意保留**：① 它是「学生只读自己的行、**教职全读**」这个形状的唯一住址，
   删掉之后要它的人只能去改 `staff_taught`（= 把 13 行的口径一起改掉）；
   ② 工厂里那一支 `if` 与 `staff_taught` **共用**，故留着它的成本是 0 行代码。
   ⚠️ 而「它不是死代码」由一个**合成资源**守卫钉住
   （`test_the_student_self_tier_still_behaves_as_staff_full_read`，与
   `test_an_explicit_pk_alias_overrides_the_automatic_one` 同一条口径），
   「0 行」这件事由 `…_seven_zero_thirteen_and_three` 字面钉住
   （于是「有人悄悄把某一行改回 `student_self`」会红 —— 那一改会让那个资源
   对任何在册教职重新变成全校全读，失效方向是**静默地多给数据**）。
4. **教师仍然读得到全校的学生姓名与学号**（`students` / `teachers` 是 `staff` 档，本波没动）。
   这是**有意的**：教师端要「按工号与姓名显示学生与同事」，而两份名册含的是
   `birth`（学生）与 `staff_no` + `name`（教师）—— 即**绑定口令的验身材料**。
   ⚠️ 于是「数据隔离」今天隔离的是**健康档案**，不是**名册**。
   若控制者要连名册也按任教范围收，那是 `staff` 档的一次改动（第五档），
   而它会让 `TeacherNav` 的两级选择器少一个可用的名单来源（要改成从 `enrollments` 反查）。
5. **`AlertQueue.vue` 的三档计数（红/黄/绿、待处理/已处理/已忽略、学生级/班级级）今天都是
   「我这一个范围里的」**，而页面上一行小字说清了这件事。⚠️ 而「班级级」那一格对教师恒为 0
   （= 顶回 1），故它今天在教师屏上是一个恒为 0 的计数 —— 页面上已经把两个理由都写出来了。

### 6.4 没按派单做的（**1 处**）

- **派单 §7 建议 4 个 commit：① 后端第四档 …；② normalized 的三档范围 + 守卫；③ 前端 …；④ spec + 报告。**
  本波落成的 4 个 commit 是 **①②合并 / ③拆成两个 / ④**：
  `d9f43bd`（后端全部：第四档 + `normalized` 裁班 + 全部后端测试）、
  `d3fcb79`（前端 3 个 `.vue`）、`f6aab9d`（`smoke.mjs` + `gen:api` 产物）、本条（spec + 报告）。
  **理由**：派单的 ① 与 ② **无法各自自洽** —— `current_reader` 的返回类型换代
  （`int | None` → `ReaderIdentity`）与它**唯一的另一个消费者** `normalized_scores`
  必须在同一个 commit 落地，否则 ① 单独 checkout 出来跑全量后端会红 **2 条**
  （`test_feedback.py` 的那两条：`reader is not None` 对 dataclass 恒真 →
  列级收窄会误伤教职档）。⚠️ 而 `d3fcb79` 与 `f6aab9d` 之间 `smoke` 是红的
  （needle 在 `f6aab9d` 才改）—— 这一格**在派单自己建议的切法下同样存在**
  （它的 ① 也是后端先落地），属不可避免，如实记。
  ⚠️ 除此之外**逐条照派单做**：SQL 层过滤 ✓、`total` 过滤后 ✓、判据单一所有者 ✓、
  `weekly-class-reports` 不动 ✓、四档矩阵（且超出「至少抽 4 个」）✓、定点变异 ✓、
  `total` 过滤断言 ✓、遍历守卫同步 ✓、normalized 三档范围 + 守卫 ✓、
  前端两级选择 ✓、管理台不受影响 ✓、smoke needle ✓、`git add` 按文件名逐个加 ✓、
  commit 信息 python 写 UTF-8 无 BOM 临时文件 + `git commit -F` ✓、不 push ✓。

---

## ⑦ 最终验收

| 格 | 基线（`601c79a`） | 本波实测 | 判定 |
|---|---|---|---|
| 后端 pytest（带 `--cov=app.domain --cov-branch`） | 1494 passed + 1 skipped | **1497 passed + 1 skipped**（293 s） | ✅ **+3**（3 条新守卫；一条都没减） |
| 后端 pytest（不带 cov） | — | **1498 passed**（150 s） | ✅（那 1 条 skipped 是 `test_backfill` 的 trace 钩子档，只在带 `--cov` 时跳） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | ✅ 一字不退 |
| 表数（`Base.metadata`） | 28 | **28** | ✅ |
| 架构扫描面 | 71 | **71**（pipeline 10 + db 13 + domain 18 + api + auth；本波**没加模块**） | ✅ |
| 迁移链 | 3 单头 | **3 单头**（`tests/db/test_migration_chain.py` + `test_migration_baseline.py` 全绿） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✅ |
| 黄金用例 | 14 | **14**（`tests/integration` 49 条全绿） | ✅ |
| **openapi 五格** | 72 路径 / 100 操作 / 挂 security 82 / GET 61（15 匿名 + 46 挂 security）/ `securitySchemes` 3 | **72 / 100 / 82 / 61（15 + 46）/ 3** —— 逐格从 `/openapi.json` 实读 | ✅ **一个字节都没变** |
| 13 个学生键资源 26 个 GET 的 `security` | `[{"X-Student-Id":[]},{"X-Teacher-Staff-No":[]}]` | 取值种类 **1**，逐字相同 | ✅ |
| 23 个泛型 list / read-one 的 `description` | 各 1 种取值 | 各 **1** 种取值（两支 docstring 仍逐字相同，守卫绿） | ✅（内容随第四档改了 → 重跑 `gen:api`） |
| 24 个未定型响应 | 24 | **24**（smoke 第 12 步 ⑤ 三拍全绿：23 个 list + `/api/health`） | ✅ |
| `npm run gen:api` | — | 退出码 **0**，`schema.d.ts` **+588 / −4** 行（⚠️ 其中 3 行是**先前就漂了**的 `/api/health` description，见 6.2 第 6 条） | ✅ |
| `npm run build`（`vue-tsc -b && vite build`） | 退出码 0，`index-CM7Fwkho.css` / `index-eWDO9FkM.js` | 退出码 **0**，**`index-Dm5ljZoJ.css`（66.49 kB）/ `index-BHZyrjkk.js`（237.61 kB）**；两次跑哈希逐字相同 | ✅ |
| `npm run check:tokens` | 绿（35 文件） | 绿，扫描面 **35** 个文件（下界 25），「tokens.css 之外一个色值字面量都没有」 | ✅ |
| `npm run check:dist` | 绿 | 绿（`adoptFromUrl` 0 次、两个字体域名各 0 次，三条谓词都非空） | ✅ |
| 依赖清单守卫 | 一字不红 | **一字不红**（`tests/test_dependencies.py` 全绿；`package.json` 与 `pyproject.toml` 本波**一个字节没动**，新增依赖 **0**） | ✅ |
| **`smoke.mjs` dev 档** | 18 步 / 500 断言 / 退出码 0 | **18 步全绿 / 520 断言 / 0 红 / 退出码 0**（`demo.ps1 -Port 8000` + vite 5173） | ✅ **+20** |
| **`smoke.mjs` 产品档** | 18 步 / 500 断言 / 退出码 0 | **18 步全绿 / 520 断言 / 0 红 / 退出码 0**（`scripts\serve.ps1 -Port 8020`，同源单进程 + SPA fallback） | ✅ |
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | 现算自磁盘**逐字相同**（`national_standard_2014.csv` 21412 B / `exercises.yaml` 23247 B / `exercise_equivalence.yaml` 8245 B / `alert_rules.yaml` 6037 B；`raw` 与 `norm` 两栏相同 = 行尾也没动） | ✅ |
| 18 个模板指纹 | 18 | `backend/data/prescription/*.yaml` **18 个**逐个现算，与 `TEMPLATE_FINGERPRINTS` 逐字相同（`RED-END-ABN-01` `C0C61D2140A521D0` … `GRN-SPD-NOR-18` `2389C1A03E6ABBCE`） | ✅ |
| `git diff 601c79a HEAD -- backend/data` | 空 | **空**（`--stat` 与 `git status --porcelain -- backend/data` 都是空串） | ✅ |
| `backend/pe.db` | 不得存在 | **False**（不存在） | ✅ |
| `backend/data/seed/` | 0 文件 | **0 文件**（`rglob` 递归数，`demo.ps1` 的 ⑤ 那一步也每次 `throw` 复核过） | ✅ |
| `backend/data/**` 递归文件数 | 24 | **24**（4 个根下 + 18 个模板 + `README_national_standard.md` + `indicator_ranges.yaml`） | ✅ |
| 行尾 / BOM | — | 全部被改文件复核过：`git ls-files --eol` 逐行 `i/lf w/crlf`，`schema.d.ts` 是 `w/lf`（生成器原样，与改前相同），4 个 `.ps1` 一个没动。⚠️ **过程中抓到一次事故并已修**：编辑工具往 6 个 CRLF 文件里插了 **356 个裸 LF**（`crud.py` 109 / `deps.py` 90 / `feedback.py` 42 / `test_feedback.py` 109 / `test_prescription_api.py` 7 / spec 139），全部归一成 CRLF 后复验 `bare=0` | ✅ |
| spec | 265 518 B（入库 blob）/ 工作树 265 518+ | **287 894 B / 2578 行 / CRLF 2578（= LF 2578，全 CRLF）/ 无 BOM / sha256[:16] = `74cb465ca2cba17b`** | ✅（`attr/text eol=crlf` 那条钉扎生效，入库侧归一化成 LF） |
| 报告自身 | — | 见下面那一行「本报告字节数」 | ✅ |

**spec 改了哪几处**：§1.2 已知局限表的第 **13**（划掉「教师的任教范围闸门不扩到泛型读」，
改成「已收掉」+ 实测数字）与第 **14** 条（划掉「normalized 仍然匿名」，改成「已关匿名 + 已加行级裁班」），
**新增第 17 / 18 条**（= 顶回 1 / 顶回 2 的逐字取证）；
§13.4.4 的三档表改成**四档表**（7 / 0 / 13 / 3，多两列「教师会话 / 管理员」）、
`total` 与 `items` 那一段补上**四档实测对照表**（9 个资源 × 4 档身份）、
`current_reader` 的返回值换代与「openapi 五格一个字节都没变」逐字记下、
守卫清单的 3 个名字同步；**新增 §13.4.7**（本波的完整口径：判据单一所有者 / SQL 层 /
三种学生键形状 / `student_self` 为什么保留 / normalized 裁班 / 前端两处 / 两格残余局限 /
守卫清单含定点变异 3 条）；§13.9 那处「`read_scope` 三档」→「四档」。

**commit sha**：

| # | sha | 一句话 | 自洽？ |
|---|---|---|---|
| ①② | **`d9f43bd`** | `feat(api)`：第四档 `staff_taught` + `taught_section_ids`/`taught_student_ids` + `ReaderIdentity` + `_taught_filter`/`_reader_filter`/`_require_row_readable` + `normalized` 行级裁班 + 全部后端测试（8 个文件） | ✅ 后端全量 **1497 + 1** 全绿；⚠️ `smoke` 红（needle 在 ③ 才改） |
| ③ | **`d3fcb79`** | `feat(frontend)`：`TeacherNav` 班→学生两级选择器 + `AlertQueue` 范围文案 + `StudentDetail` 一处注释（3 个文件） | ✅ `npm run build` / `check:tokens` / `check:dist` 全绿；⚠️ `smoke` 仍红 |
| ③ | **`f6aab9d`** | `test(smoke)`：needle 收进第四档（判据一个字没改）+ `gen:api` 产物（2 个文件） | ✅ **两档 smoke 各 18 步 / 520 断言 / 0 红** |
| ④ | 本条 | `docs`：spec §1.2 第 13/14/17/18 条 + §13.4.4 四档表 + §13.4.7 + 实现者报告 | ✅ |

⚠️ **未 push、未碰 `main`**（`git branch --show-current` = `p06/teacher-scope`，
`main` 仍然指在 `601c79a`）。

---

**本报告字节数**：**51 449 B / 577 行 / 纯 LF / 无 BOM**（与同目录 4 份既有报告同款行尾：`task-1-2-report.md` 707 LF、`task-3-4-report.md` 636 LF、`task-5-6-report.md` 998 LF、`task-7-report.md` 762 LF，四个都实测 `crlf=0`）。⚠️ `.superpowers/**` 在 `.gitattributes` 里是 `-text`（双向零转换），故**入库 blob 的字节数必须逐字等于磁盘字节数** —— 已用 `git cat-file -s` 复核。
