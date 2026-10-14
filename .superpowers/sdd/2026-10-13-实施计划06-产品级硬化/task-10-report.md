# 实施计划 06 · Task 10 实现者报告

> **分支** `p06/teacher-normalized-and-bind-throttle`（自 `main` 的 `7dca18f` 起）
> **两件**：① 教师侧的 `normalized` 变体端点（Task 9 顶回①的落地）；② `bind` 两个端点的限流（品牌波之前登记的 S2）
> **commit**：`d3f9c58`（①后端）· `9bce5d0`（②后端 + `gen:api` 产物）· `154759d`（③前端 + smoke）· 本 commit（④ spec + 报告）
> **顶回 4 处**（§6.4）· **没按派单做的 1 处**（§6.3）· **待清扫 6 条**（§6.1）

---

## ① 环境

| 项 | 实测 |
|---|---|
| `node --version` | **v24.19.0** |
| `python --version` | **Python 3.11.1**（无 venv，`C:\Python\python.exe`） |
| fastapi / sqlalchemy / alembic / pydantic | **0.141.1** / **2.1.3** / **1.20.0** / **2.13.5** |
| npm | 11.17.0 |
| 起点 | `HEAD = 7dca18f`、工作树干净、`core.autocrlf = true` |
| 服务 | 开工时**没有**服务在跑；⚠️ **5173 上有一个不是本波起的 vite（PID 20240）**，按纪律**没有杀它**，dev 档改用 **5174** + `PE_WEB_BASE` |
| 起过的进程 | `demo.ps1 -Port 8000`（3 次，每次重灌演示库）· `npx vite --port 5174 --strictPort` · `scripts\serve.ps1 -Port 8020`（2 次：一次误带 `PE_ENV=prod`、当场停掉，见 §6.2 第 3 条）· 两次全量 pytest |
| 探针目录 | `$env:TEMP\p06t10\`（9 个文件：`ed.py` / `p1.py` / `p1b..p1f.py` / `p2.py` / `p2b..p2f.py` / `p3.py` / `p4.py` / `p4b..p4d.py` / `p5.py` / `p5b.py` / `msgs.py` / `mutate.py` / `verify.py` / `probe1.mjs` / `probe2.mjs` / `probe4.mjs` / `probe3.py`）；跑完**只删这一个子目录**并复验（§7） |

⚠️ **编辑一律走 Python 脚本**（`ed.py`：二进制读写 + 把插入文本的 `\n` 一律换成 `\r\n`），
每改完一个文件就核 `git ls-files --eol`（逐个结果见 §8）。**本波没有发生行尾/BOM 事故。**

---

## ② 第一件：教师侧的 `normalized` 变体端点

### 2.1 那一族既有端点的实测形状（派单要求「先 Grep、照它的姿势加」）

`/api/teacher/students/{id}/…` 那一族**今天有两条**，都在 `app/api/routers/dashboard.py`：

| 路径 | 波次 | 闸门 | `response_model` | 学期怎么来 |
|---|---|---|---|---|
| `…/weekly-sheet` | Plan 03 Task 8 | `current_teacher` + `require_teaches_student` | **复用** `prescription.WeeklySheetRead` | `as_of` → `current_semester_of(session, day).id` |
| `…/home` | Plan 04 收尾波 | 同上 | **复用** `dashboard.StudentHomeRead` | 同上 |

⚠️ 两条的共同姿势（本波逐条照抄）：`dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]` +
`staff_no: str = Depends(current_teacher)` + `require_teaches_student(...)` +
**函数体抽成一个私有 helper、两个端点共用**（`_weekly_sheet_response` /
`_student_home_response`，而 helper 住在**数据所在的那个 router**里、由 `dashboard` 跨模块
import 私有名）+ `response_model` **复用学生侧那一个 schema**。

**对 admin 的处置（实测，产品档 8000、真 cookie、学生 #4）**：

```
home  T0001（不教他）  -> 403      sheet T0001 -> 403
home  T0002（教他）    -> 200      sheet T0002 -> 200
home  T0003（管理员）  -> 200      sheet T0003 -> 200      ← 越过任教范围
home  学生 4 的会话    -> 403      sheet 学生 4 -> 403
home  匿名             -> 401
```

⚠️ 即那一族对 admin 是 **200（越过任教范围）**，判据是 `require_teaches_student` 的第一行
`if require_staff(session, staff_no) == ADMIN_ROLE: return`。本端点**不写第二份**管理员判据，
并且守卫**当场复验**了 `/home` 与 `/weekly-sheet` 对同一个管理员也是 200
（`test_the_teacher_normalized_variant_admits_only_a_teaching_staff_session` 的第三拍）。

### 2.2 新端点的声明

```python
@router.get(
    "/api/teacher/students/{student_id}/normalized",
    tags=["dashboard"],
    response_model=NormalizedSelfRead,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def teacher_student_normalized(
    student_id: int,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
    semester_id: int = Query(description=...),      # ⚠️ 必填、无缺省
    week: int = Query(ge=1, description=...),       # ⚠️ 必填、无缺省
) -> dict:
```

⚠️ **查询参数「先实测既有那个端点是不是都必填」的结果**：`/openapi.json` 上
`GET /api/mini-tests/normalized` 与 `…/normalized/me` 两个端点的 `semester_id` 与 `week`
都是 `required: true`、都**没有缺省**、`week` 还带 `ge=1`。故照抄，且守卫把**两个端点的
422 `loc` 集合并排比**（`test_the_teacher_normalized_variant_requires_both_query_parameters`：
四种缺参组合逐个断 422 且 `loc` 逐字相同，末拍反假绿「两个都带上 → 200」）。
产品档实测缺参那一发：

```
422 {"error":{"code":"request_validation_failed","message":"请求参数校验未通过",
    "detail":[{"type":"missing","loc":["query","semester_id"],...},
              {"type":"missing","loc":["query","week"],...}]}}
```

⚠️ **`tags=["dashboard"]`**（不是 `mini-tests`）：与那一族既有两条逐字相同。
⚠️ 而**任教关系按入参那个 `semester_id` 判**（不像那两条用 `as_of` 折算）——
「班内百分位按哪一个学期的选课关系算」与「任教关系按哪一个学期判」**必须是同一个学期**，
否则会出现「闸门按学期 A 放行、而分数按学期 B 算」这种在同一屏上自相矛盾的形状。
逐字理由写在端点 docstring 的那一节里。

### 2.3 四档 + 管理员矩阵（产品档 8020、真 cookie、演示库 `semester_id=2&week=6`、学生 #4）

| 调用方 | 码 | `code` / message 要点 |
|---|---|---|
| 匿名 | **401** | `unauthenticated`（「缺少身份：需要一个有效的 pe_session cookie…」） |
| 学生**会话** | **403** | `forbidden`（「当前会话是 student（2023120001），而本端点要的是教师身份：一个学生的 cookie 不能当教师用」） |
| 学生**请求头**（仅 dev 档） | **401** | `unauthenticated`（⚠️ **不是 403**：`current_teacher` 根本没读到教师身份，故它答「缺身份」） |
| T0001（**不**任教他） | **403** | `forbidden`（「学生 4 不在教师 'T0001' 于学期 2 任教的任何教学班里…」） |
| T0002（任教他） | **200** | 见 §2.4 |
| T0003（管理员，**不带任何班**） | **200** | 与 T0002 那一档**逐字相同**（管理员不带班 ⇒ 不裁班） |

⚠️ **学生会话 403 / 学生请求头 401 两档都钉**（前者是生产档、后者是 dev 档），
两份守卫各自一条：`…admits_only_a_teaching_staff_session`（真 cookie）与
`…in_the_dev_header_tier`（请求头）。⚠️ 这与既有 `…/home` 变体的口径逐字相同
（`test_the_home_page_teacher_variant_rejects_anonymous_and_student_callers` 钉的就是 401 那一档）。

### 2.4 算式复用的取证（派单 §1 第 4 条）

**既有 `normalized` 端点是怎么算的（实测）**：`normalized_scores` → `_normalized_sections`
（分组 + 取样）→ 每行 `**mini_test_scores(row.squat_30s_count, row.shuttle_20m_s, sample)`
（`app/domain/report.py` 的**那一份**算式；`tests/domain/test_report.py` 的
`test_the_mini_test_normalization_has_exactly_one_definition` 用 AST 数定义份数 == 1）。
`/normalized/me` 走的是**同一个** `_normalized_sections`，只是投影不同。

**本波的做法**：把「那三格怎么摆成响应体」抽成 `feedback._normalized_self_body`
（唯一住址），`/normalized/me` 与新端点**共用**它；新端点**一行算式都不写**。
先例逐字是 `prescription._weekly_sheet_response`（Plan 03 Task 8）与
`dashboard._student_home_response`（Plan 04 收尾波）。

**三拍取证**：

1. **响应体逐字相同**（产品档实测）：T0003（管理员）打新端点 与 学生 #4 本人打
   `/normalized/me`，两个响应体**各 242 bytes、逐字节相同**：

   ```json
   {"semester_id":2,"week":6,"sections":[
     {"course_section_id":2,"mini_test_id":124,"squat_score":35.0,"shuttle_score":98.33,"composite":66.67},
     {"course_section_id":4,"mini_test_id":124,"squat_score":35.0,"shuttle_score":92.5,"composite":63.75}]}
   ```

   ⚠️ **`composite` 的实测值**：班 2 → **66.67**、班 4 → **63.75**（`squat_score` 两班都是
   **35.0**，`shuttle_score` 分别是 **98.33** 与 **92.5**）—— 与 §13.4.9 记的
   `/normalized/me` 那一次实测**同一格逐字相同**（同一次小测 `mini_test_id=124`，
   两个班各投一次、各算一次班内百分位）。
   ⚠️ 守卫 `test_the_teacher_variant_agrees_with_the_student_side_endpoint_cell_for_cell`
   **两侧不同源**（一侧学生 cookie 打学生端点、一侧管理员 cookie 打新端点，比整个 dict），
   并带**手算期望**（班内 2 人、他折返 30.0 是较快的那个 ⇒ `(1 + 0.5×1)/2×100 = 75.0`、
   综合分 `(30+75)/2 = 52.5`）反假绿。
2. **AST**：`_normalized_self_body` 与 `_normalized_sections` 在 `app/**` 里各**恰好定义一次**
   （都在 `feedback.py`），而用到前者的模块**恰好两个**（`dashboard.py` + `feedback.py`）；
   `dashboard.py` 的 **AST 引用面**上没有 `mini_test_scores` / `shuttle_percentile` /
   `SCORE_PRECISION` 三个名字，而 `_normalized_self_body` **确实在**（否则「一个名字都没引用」也绿）。
   ⚠️ 判定落在 AST 上而**不是裸文本**：docstring 里**点名**那个算式是本仓的散文纪律要求的、
   完全合法，而裸文本匹配会把它当成「重算了一遍」（首跑就是这么红的，已修）。
3. **裁班**（这一格是本端点最容易做错的地方，见 §2.5）。

### 2.5 ⚠️ 一处派单没点名、而实现者认为**必须做**的收窄：按任教范围裁班

**问题**：一个学生同一学期**可能在两位教师的班里**（演示库上学生 #1 选在班 1〔T0001〕
与班 5〔T0003〕）。若新端点是「过闸门 → 把这个学生**全部**班里的行都回出去」，
则 T0001 打学生 #1 就会读到他在**班 5** 里的班内百分位与综合分 —— 而那正是
Plan 06 Task 8 花了一整个 Task 在 `/api/mini-tests/normalized` 上关掉的**跨教师读口**
（响应级裁班，spec §13.4.7），本端点会把它**重新开一个**。

**处置**：`allowed_sections` 与那一个端点的教师档**同一条判据、同一个所有者**
（`deps.taught_section_ids` + `teacher_id_of`；管理员为 `None`）。**产品档实测取证**：

| 调用方 | `sections` | `composite` |
|---|---|---|
| T0001 → 学生 #1 | `[1]` | **20.5** |
| T0003（管理员）→ 学生 #1 | `[1, 5]` | **20.5** / **16.75** |

⚠️ 于是「形状恒定」仍然成立：变的是**哪几行**、不是**哪些列**，而「哪些行随身份而变」
是分页/过滤的常规形状、OpenAPI 表达不了行数（与 §13.4.9 同一条口径）。
⚠️ **代价如实记**：教师因此看不到这个学生在别人班里的综合分（那是有意的：教师账号之间
要有数据隔离，spec §1.2 第 13 条）；要看全部班请用管理员登录。
⚠️ 守卫两条：`test_the_teacher_variant_never_reopens_the_cross_teacher_read`
（两位教师各打一次 + 管理员看到两行 + 点名断言「张老师的响应里没有李老师那个班的任何一格」）
与上面 §2.4 第 1 拍的子集断言。
⚠️ **定点变异**：把 `allowed_sections` 恒置 `None` → 那两条**当场红**（§6.5）。

### 2.6 六条守卫（`tests/api/test_dashboard.py` 新增支 D″）

| # | 名字 | 钉什么 |
|---|---|---|
| 1 | `test_the_teacher_normalized_variant_admits_only_a_teaching_staff_session` | 五档矩阵（真 cookie）+ 两档 403 的 `code` + 200 那两档**真的有内容** + **当场复验** `/home` 与 `/weekly-sheet` 对同一个管理员也是 200 |
| 2 | `test_the_teacher_normalized_variant_in_the_dev_header_tier` | 请求头那一档：匿名 401 / 学生头 **401** / 不在册工号 403 / 教师头 200（绿档） |
| 3 | `test_the_teacher_variant_agrees_with_the_student_side_endpoint_cell_for_cell` | 管理员档 ≡ 本人 `/me`（整个 dict）；教师档是它的子集且同班那一行逐字相等；五格齐全 + 三格手算期望 |
| 4 | `test_the_teacher_variant_never_reopens_the_cross_teacher_read` | 裁班：两位教师各只看到自己那个班、管理员看到两个 |
| 5 | `test_the_teacher_normalized_variant_requires_both_query_parameters` | 两个查询参数必填 + `week >= 1`，且 422 的 `loc` 集合与既有 `normalized` **逐字相同** |
| 6 | `test_the_normalized_projection_and_the_formula_each_have_exactly_one_owner` | AST：投影与分组各只有一个定义、恰好两个消费者、新端点一行算式都不写 |

---

## ③ 第二件的前端：`StudentDetail.vue` 三格恢复

### 3.1 那一块两格 → 三格

改前（Task 9 之后）：`折返班内百分位` + `深蹲得分`（读原始行的 `squat_30s_count`）。
改后：**`小测综合分`** + `折返班内百分位` + `深蹲得分`。

⚠️ **三格的顺序、`decimals`、`caption` 与 Task 9 之前那一版逐字相同**
（`git show a37a7f5:frontend/src/views/teacher/StudentDetail.vue` 上亲验）——
故本波是一次**复原**、不是重新设计：

| 格 | `:value` | `decimals` | `caption` |
|---|---|---|---|
| 小测综合分 | `selfOf(row.sectionId)?.composite` | **2** | `两项等权平均（⚠️ 量纲是混的：次数 vs 百分位）` |
| 折返班内百分位 | `row.entry.shuttle_score`（**不变**，仍读班级端点） | 1 | `` `样本 ${row.sample} 人` `` |
| 深蹲得分 | `selfOf(row.sectionId)?.squat_score` | 1 | `= 30 秒次数` |

⚠️ 取值来源新增一格 `selfBySection`（`Map<班号, NormalizedSelfSectionRead>`）+ 一个
`selfOf(sectionId)`；两个请求**并行**发（`Promise.all`，与 `MiniTest.vue` 读
③ + `/me` 的同一条口径），**任何一次失败都落到同一块**「有解释的区域」
（`normalizedError`）—— 两个请求说的是同一次小测，只渲染一半会给出一个自相矛盾的屏。
⚠️ 查不到时 `StatBlock` 渲染「—」（计划约束第 10 条：不知道不得显示成 0）。

### 3.2 「深蹲得分」那一格读了哪儿（派单 §1.6 要「选一个并说明理由」）

**选了「改回读新端点的 `squat_score`」**（= 控制者的倾向）。理由三条：

1. **同源比等价更强**：三格出自**同一个响应体**之后，读的人不必再去论证「这两个数为什么
   一样」；而改前那一格靠的是「`squat_score` 逐行等于 `mini_test.squat_30s_count`」
   这条**守卫**（它钉的是 spec §8.1 的算式，与本页无关）。
2. **少一个中间状态**：改前页面同时持有 `pickedMiniTest`（原始行）与 `normalized`
   （班级端点）两份异步状态，且必须论证「两格说的是同一次小测」；改后只剩
   `normalized` + `selfBySection` 两份，且它们的 `semester_id` + `week` **由同一行推出来**。
3. **per-section 取值**：改前 `pickedMiniTest?.squat_30s_count` 对**每个班**显示同一个数
   （数值上正确，因为深蹲得分与班无关），改后 `selfOf(row.sectionId)?.squat_score`
   按班取 —— 于是「一个学生在两个班」那一档也不需要额外论证。

⚠️ **显示出来的数一个字节都没变**（那条逐行相等的守卫今天仍然在、仍然绿）。
⚠️ 连带：`pickedMiniTest` 那一格 `ref` 与它那段 docstring 一起删掉（它没有别的消费者）。

### 3.3 `t-block__why` 改前 / 改后（派单 §1.6：「不许留一句已经过时的假话」）

**改前**（逐字摘录要点）：「⚠️⚠️ **本块自 Plan 06 Task 9 起少了一格「小测综合分」**（如实交代，
不是漏做）… 教师/管理员打它是 **403** … 故本页读不到它 … ⚠️ 那一格**已顶回给控制者**：
正确的形状是另开一条教师侧变体 … ⚠️ 而「深蹲得分」那一格**没有丢**：它逐行等于
`mini_test.squat_30s_count`，本页从上面第 03 块已经读到的那一行取它」。

**改后**：「⚠️⚠️ **本块那三格自 Plan 06 Task 10 起又齐了**（Task 9 一度只剩两格，如实交代
它的来龙去脉）… 摘列欠下的那一格由一个**教师侧变体**还上：
`GET /api/teacher/students/{id}/normalized` … 响应体与学生侧的 `NormalizedSelfRead`
**是同一个 schema** … 它的**形状恒定**，故它是**真契约** … 本人那两格另有一条
`/normalized/me`（**仅学生本人**，教职 403），⚠️ 本页**走不了**那一条 …
「深蹲得分」那一格自本波起**也读这一个变体** … 于是本块三格**同源** …
⚠️ 变体同样**按任教范围裁班** … 故「他在另一个班里的那一格」对本页的教师**刻意不可见**」。

⚠️ **另外两处过期文字一并修掉**（同一纪律）：
① 文件头那份「读的端点」清单第 3 条（「故本页**读不到**它们 … 已顶回给控制者」）改成
「本页从它读的**只有** `shuttle_score`」，并**新增 3b 一条**（新端点 + 五档实测 + 裁班）；
② `t-subhead__aside` 上那句 `GET /api/mini-tests/normalized · **匿名**` —— 它自
**交付前收尾波 ③** 起就是假的（那个端点今天匿名是 401），改成
`… /normalized + …/teacher/students/{id}/normalized · **教职会话**`。
⚠️ 顺带把 `endpoints.ts` 里 `getNormalizedSelf` 末段那句「教师端那一格改读
`GET /api/mini-tests` 的 `squat_30s_count`」也改正了（那是 Task 9 的降级处置）。

### 3.4 DOM 无重叠 / 无溢出的实测

那一块从两格变回三格之后，`smoke.mjs` 第 14 步对 **16 条路由逐条**跑的三拍布局守卫
**照旧全绿**（dev 档与产品档各一遍）：

* `t-student-detail：没有文本内容重叠` → `overlapCount = 0`
* `t-student-detail：没有非故意的横向溢出` → `overflowCount = 0`
* `t-student-detail：整页没有横向滚动条` → `pageScrollWidth <= innerWidth`

⚠️ 结构上的理由：`.sd-stats` 是 `display: flex; flex-wrap: wrap; gap: var(--space-5)`，
故三格在窄屏上**换行**、不重叠；⚠️ 而它**复用既有 class**、没有新增一行 CSS
（`check:tokens` 的结论一字未变：扫描面仍是 **36** 个文件、下界 25，退出码 0；
`check:dist` 退出码 0）。⚠️ **没有引入新的裸值**：新加的那一格 `StatBlock` 只用了
既有的 `decimals` / `label` / `caption` / `size` 四个 prop，一个色值字面量都没有。

### 3.5 smoke 的**真取证**拍怎么做的（派单 §1.8：别再用静态文字）

Task 9 登记过一条待清扫：「smoke 对 `/s/mini-test` 的 needle 是静态文字」。
本波给**教师页这一格**做的是真取证，形状如下（`smoke.mjs` 第 14 步）：

1. **期望侧**：在 16 条路由的循环**之前**，用教师会话现取一次数据 —— 从
   `GET /api/mini-tests?limit=200` 里挑出被查看那个学生的行、取 `week` 最大的那一行、
   用它的 `semester_id` + `week` 去打新端点，于是得到 `wantComposite`（`composite.toFixed(2)`）
   / `wantSquat`（`squat_score.toFixed(1)`）/ `wantShuttle`（`shuttle_score.toFixed(1)`）。
   ⚠️ 推法与 `StudentDetail.vue` 的 `pickedWeek` **同一条口径**，故演示库换了周次也不用改脚本。
2. **被测侧**：`dumpRoute` 轮询到全部 needle 出现之后，用 CDP 的 `Runtime.evaluate` 跑一段
   `STAT_PROBE`，把页面上全部 `.stat` 的 `(.stat__label, .stat__value)` 两格抓出来。
3. **三拍**（对 `t-student-detail` 一条路由）：「小测综合分」/「深蹲得分」/「折返班内百分位」
   三格的 DOM 文本**逐字等于**上面那三组期望值，且**非空**。

⚠️ **两侧不同源**（CDP 抓的 DOM 文本 vs HTTP 响应体），故它挡得住三档失效：
「Vue 把 `null` 渲染成了 0」「读错了字段」「前端自己算了一遍」。
⚠️ 第三拍（折返百分位）同时是「同源」的**交叉验证**：那一格读的是**班级端点**，
而它与变体给的那一格**逐字相等**（后端两个端点共用同一份分组与算式）。
⚠️ needle `'小测综合分'` **也留着**，但它的作用是让 `dumpRoute` 轮询到**异步请求落地之后**
才抓 DOM（少了它，DOM 可能在 `Promise.all` 回来之前就被抓走 → 那三拍会假红），
**不是**取值判据。⚠️ `/s/mini-test` 那两条 needle **本波没动**（派单没要求，
且那是学生页；已登记为待清扫，见 §6.1 第 4 条）。

---

## ④ openapi 五格：改前 / 改后逐字 + `gen:api` + 同步了哪几处断言

### 4.1 五格（口径一律是 `app.openapi()["paths"]`，**不用** `len(app.routes)`）

| 格 | 改前（Task 9 之后） | 改后（本波） | 由谁钉 |
|---|---|---|---|
| `/api/` 路径模板 | **73** | **74** | `smoke.mjs` 第 12 步 |
| 操作 | **101** | **102** | 同上 |
| 挂 `security` 的操作 | **83** | **84** | `smoke.mjs` 第 12 步 + `test_prescription_api.py` 的 `all_security` |
| GET | **62**（15 匿名 + 47 挂 security） | **63**（**15** 匿名 + **48** 挂 security） | `smoke.mjs` 第 12 步 |
| `components.securitySchemes` | **3** | **3**（不变） | `test_prescription_api.py`（`sorted(schemes) == [...]` 逐字） |
| catch-all 漏进 `paths` | **0** | **0** | 离线 `create_app` 实测（`verify.py` ⑤） |
| spec 顶层 `security` | `None` | `None` | `test_prescription_api.py` |
| `expected` 清单（派单叫「未定型响应」的那一格） | **25** 项 | **26** 项 | `test_prescription_api.py` 的 `len(expected) == 26` |

⚠️ **第二件（绑定限流）不动这五格任何一格**：两个 `bind` 端点各多了一个 `request: Request`
形参，而 FastAPI 对 `Request` 标注特殊处理、**不进 OpenAPI**（与 Plan 06 Task 3 给 `login`
加同一个形参时逐字同一条口径）。⚠️ 而它们的 **docstring 就是 `/openapi.json` 的
`description`**，故 `gen:api` 的产物**仍然变了**（下面那一格）。

### 4.2 `npm run gen:api`

| 项 | 值 |
|---|---|
| 退出码 | **0**（`openapi-typescript 7.13.0`，527.1 ms） |
| 产物 diff | **+307 / −19 行** |
| 产物字节 | 480 541 B → **517 231 B** |
| 一致性守卫 | `test_the_generated_typescript_client_matches_the_current_openapi_document` **绿**（纯 Python 双向逐行比对） |

⚠️ **踩到的一个坑，如实记**：`gen:api` 的输入是 `http://127.0.0.1:8000/openapi.json`
—— 即**在跑的那个服务**。本波第一次跑它时 8000 上是**改代码之前**起的进程，
于是产物是旧 spec（`git diff` 为空）。**处置**：停掉、重跑 `demo.ps1` 起新进程、再跑一次。
⚠️ 已登记为待清扫（§6.1 第 5 条）：`gen:api` 应该有一个「从离线的 `create_app()` 取 spec」
的档，否则「产物对不对」取决于「你起服务的时候代码是什么状态」，而那一格是静默的。

### 4.3 同步了哪几处断言（派单 §1 第 5 条要「`Grep` 核全」）

`Grep` 的口径是 `路径模板|apiPaths\.length|== 83|== 101|== 73|_LITERAL_TAILED_SPECIAL_ROUTES`，
全仓扫（含 `Document/**` 与 `.superpowers/**`）。**要动的三处 + 刻意不动的一处**：

| # | 住址 | 改了什么 |
|---|---|---|
| 1 | `frontend/scripts/smoke.mjs` **第 12 步** | 五格 73/101/83/62/15 → **74/102/84/63/15**，并加一段 Task 10 的连带口径散文（含「第二件不动这五格」与「docstring 变了故产物必须重跑」两句） |
| 2 | `backend/tests/api/test_prescription_api.py` 的 **`expected`** | +1 项（`("/api/teacher/students/{student_id}/normalized", "get"): "X-Teacher-Staff-No"`，带 20 行行内注释）；`len(expected)` **25 → 26**；`len(all_security)` **83 → 84**；那条守卫 docstring 的「Plan 06 Task 9 起是 25 项」→「Task 10 起是 26 项」；末尾那段「连带口径」+ 一整段 Task 10 |
| 3 | `Document/…设计spec.md` | §13.4.4 那张表的「路径模板」一行补到 **74**；§13.5 的五格 + 一整段 Task 10；新增 §13.4.10 / §13.4.11 两节；§1.2 第 2 / 4 / 14 / 15 条各补一句；§13.4.2 的表两个 `bind` 行加锁定档；§13.4.6 末尾指向 §13.4.11；§13.4.9 的 `StudentDetail.vue` 那一条标注「已过期，见 §13.4.10」 |
| — | `backend/tests/api/test_feedback.py` 的 **`_LITERAL_TAILED_SPECIAL_ROUTES`** | ⚠️ **刻意不加**（派单说「本波至少前两处要动」，`Grep` 核过之后的结论）：那一份钉的是「末段是**字面量**、故可能与泛型工厂的 `{占位}` 末段**同形**」的特例，而本路径是**五段**、泛型最长只注册到 `{path}/{别名}` **两段**，两者不可能同形；⚠️ 而它第一段 `teacher` 是**单数**、那个资源叫 `teachers`（复数），故也不与 `catalog` 的任何一条同形。**理由逐字写进了 `expected` 那一格的行内注释里**（免得下一个人以为漏了） |

⚠️ 另核过两处**没有**钉这些数的住址：`frontend/src/api/types.ts` 的头部注释
（它逐字写着「**路径模板数与操作数本处刻意不复述**」，硬规矩 #111）与
`test_dashboard.py::test_the_five_new_endpoints_declare_the_right_security_scheme`
（它是 Task 8 那五个的**局部复读**，`len(expected) == 5` 钉的是它自己那一份）。

---

## ⑤ 第二件：`bind` 两个端点的限流

### 5.1 「用途」那一维落在哪儿、为什么（⚠️ 这里有一处顶回，见 §6.4 ①）

**先实测 `login_attempt` 表今天有哪些列**（`app/db/models/auth.py`）：

| 列 | 类型 | 有没有取值域约束 |
|---|---|---|
| `id` | Integer PK | — |
| `kind` | `String(16)` | ⚠️ **有一条 SQL 层 CHECK** `ck_login_attempt_kind`，文本由 `LoginAttempt.KINDS` 生成，而它**就是** `UserSession.KINDS` 那一个对象（`= {"student", "teacher"}`，三张表同一族语义） |
| `login` | `String(32)` | **无** CHECK、**无**取值域守卫（学号/工号的原文） |
| `ok` | Boolean | — |
| `at` | DateTime（naive 本地） | — |
| `ip` | `String(64)`，可空 | — |

**结论**：派单 §2.1 举的例子（把用途编进 `kind`：`("student_bind", "2023120001")`）
在本仓**做不到** —— 那条 CHECK 会当场 `IntegrityError`
（守卫 `tests/auth/test_policy.py::test_the_kind_check_constraint_has_teeth` 实测它真的有牙，
并钉住 `LoginAttempt.KINDS == {"student", "teacher"}`；另一条守卫钉住
`LoginAttempt.KINDS` **就是** `UserSession.KINDS` 那一个对象）。放宽它 = 改 DDL =
配一条迁移（链 **3 → 4**）+ 同步那两条守卫 + 把 `user_session.kind` /
`audit_log.subject_kind` 的取值域一起污染（三张表共用那一个集合）。

**落地**：编进**键的另一半**（`login`），即派单 §2.1 的路 ①、只是换一格承载：

```python
PURPOSE_LOGIN = "login"; PURPOSE_BIND = "bind"
PURPOSES = frozenset({PURPOSE_LOGIN, PURPOSE_BIND})
_KEY_PREFIX_BY_PURPOSE = {PURPOSE_LOGIN: "", PURPOSE_BIND: "bind:"}

def _key(purpose, login) -> str:            # ← 前缀只有这一个住址
    return _KEY_PREFIX_BY_PURPOSE[_check_purpose(purpose)] + login
```

| | 登录 | 绑定 |
|---|---|---|
| 键（`login_attempt` 的那两列） | `("student", "2023120001")` | `("student", "bind:2023120001")` |

⚠️ **登录那一档的键逐字不变**（前缀是空串）：那让 Plan 06 Task 3 起库里已有的行**不换键**
—— 若给它也加一个前缀，则升级那一刻所有正在被锁的账号会**当场解开**、而所有历史失败行
会变成一批没人再读的孤儿，两档都是静默的（守卫
`test_the_purpose_dimension_lives_in_the_key_and_leaves_the_login_key_untouched` 钉住它，
并用 AST 数 `_key` **恰好 5 个调用点** = 3 处 SQL 的 `WHERE` + 2 处 ORM 的构造实参）。

**于是**：不加列、不动 schema、不动迁移（迁移链仍 **3**、表数仍 **28**、`login_attempt`
仍 **6** 列）—— 正是派单倾向 ① 的那一条理由。⚠️ 五个动作的 `purpose` 一律是
**keyword-only、缺省 `PURPOSE_LOGIN`**：那让 Task 3 起的全部既有调用方一行都不用改，
而绑定那一侧的两个端点一律**显式**交 `purpose=auth_policy.PURPOSE_BIND`。

**两条如实记的残余**：
① `login_attempt.login` 是 `String(32)`，加前缀之后最长 `5 + len(学号)`（实测学号/工号
最长 **10** 字符 ⇒ 实际最长 **15**）；⚠️ 而 schema 上 `student.student_no` 也是
`String(32)`，故**理论上**一个 32 字符的学号会让键变成 37 字符 —— SQLite **不校验**
`VARCHAR(n)` 的长度（实测写进去不报错、读出来不截断），而本仓今天只跑 SQLite；
换别的后端之前要先给这一列加宽（待清扫 §6.1 第 1 条）。
② **键碰撞**：一个 `student_no` 字面等于 `"bind:X"` 的在册学生会让他的**登录**计数与
`X` 的**绑定**计数共用一个键。⚠️ 要走通它需要一个 `student_no` 里带 `:` 的在册学生行，
而建学生行**仅管理员**可做（`POST /api/students`，Plan 05A Task 2 起），且登录那一档只在
「在册 **且** 已绑口令 **且** 口令错」时才写行 ⇒ 一个匿名调用方**无从**构造它。
判定：**不构成新的攻击面**，如实记录、不加校验。

### 5.2 阈值缺省与理由（派单 §2.2）

| 格 | 登录（既有） | 绑定（本波） | 环境变量 |
|---|---|---|---|
| `max_fails` | 5 | **3** | `PE_BIND_MAX_FAILS` |
| `window` | 15 min | **15 min** | `PE_BIND_WINDOW_MIN` |
| `lock` | 15 min | **60 min** | `PE_BIND_LOCK_MIN` |

**理由是一条算术**（唯一所有者是 `policy.py` 的模块 docstring，spec §13.4.11 复述一份）：

| | 登录 | 绑定 |
|---|---|---|
| 猜的是什么 | 口令（PBKDF2 600 000 次） | 出生日期 / 姓名 |
| 可信取值个数 | 实际上**无界** | 出生日期 ≈ 8 个出生年 × 366 ≈ **2 900**；⚠️ 姓名对读过名册的教职是**已知串** |
| 每次猜测的服务端代价 | ~0.3 s | ~0（一次等值查询） |
| 一天能试多少次（`24h ÷ lock × max_fails`） | **480** | **72** |
| ⇒ 一个账号一天内被猜中 | ≈ **16.5%** | ≈ **2.5%** |

（「一天能试多少次」的算式成立是因为**锁定档不写行**，故锁一到点就自动解开、
攻击者可以再试 `max_fails` 次。⚠️ 守卫 `test_the_bind_threshold_is_stricter_than_the_login_one`
**直接算这两个数**并断 `72.0` / `480.0` / `72 < 480`，于是「把 lock 抬长而把 max_fails
抬得更高」这种**看着更严、其实更松**的改动会当场红。）

* ⚠️ **`window` 保持 15**：回看是 `_lookback = max(window, lock)` = **60** 分钟，
  故计数窗口实际被抬到 60 —— 那是**多锁、不少锁**，失效方向安全。
* ⚠️ **代价如实记**：一个把出生日期打错 3 次的新生要等 **60 分钟**才能再试绑定，
  而本原型**没有口令找回** ⇒ 那 60 分钟里他既登不进也绑不上。裁定接受：绑定是**一次性**的
  入网动作、通常在开学集中办理（有教务干事在场），而「60 分钟的不便」与「账号被抢绑」
  相比是便宜的那一头。⚠️ 要更严就把 `PE_BIND_LOCK_MIN` 抬到 `360`
  （⇒ 12 次/天 ⇒ ≈0.4%/天/账号），要关掉绑定限流就把它设成 `0`
  （⚠️ **不是**把 `PE_BIND_MAX_FAILS` 设成一个巨大的数：那仍然每次失败都写一行库）。
* ⚠️ **「姓名」那一侧的收益更小**（如实记）：一个读过名册的教职本来就看得见全部教师的
  姓名，对他而言限流挡不住任何东西（他一次就猜中）—— 它挡的是**匿名**调用方的盲猜。
  而「教职能替任何还没绑定的人抢绑口令」这一格是 spec §1.2 第 3/4 条**已接受**的残余风险，
  本波**不改它**。
* ⚠️ **两组阈值一共只有这一份解析**（`_throttle`）：`throttle()` 与 `bind_throttle()`
  各自只交出「自己的三个变量名 + 自己的三个缺省 + 自己那个人话名词」，
  故「下界怎么判、坏值怎么报、分钟怎么变成 `timedelta`」三件事各只有一份；
  而「哪个用途用哪一组」也只有一个住址（`_policy_of`）。

### 5.3 五档矩阵（顺序是承重的；两个端点逐档同构）

| 档 | 响应 | 写不写 `login_attempt` | 查不查 subject 行 | 跑不跑 PBKDF2 |
|---|---|---|---|---|
| 口令太短（< 8 位） | **422 `unprocessable_value`** | 不写 | **不查** | 不跑 |
| **已锁**（第 4 次起） | **403 `forbidden`**（与「材料不符」**逐字节相同**，实测 **108 B**） | **不写** | **不查** | **不跑** |
| 不在册 / 材料不符 | 403 `forbidden` | 写一行 `ok=false` | 查 | 不跑 |
| 已经绑过了 | 409 `password_already_bound`（实测 **270 B**） | **一行都不写** | 查 | 不跑 |
| 材料对了 | **204** | **删掉这个键的全部行**，再写一行 `ok=true` | 查 | **跑**（`hash_password`） |

**HTTP 层的五档时间线实测**（`tests/api/test_auth_api.py`，缺省 3/15/60）：

| 拍 | 断言 |
|---|---|
| 未触发 | 第 1、2 次材料不符 → 各 **403**，且 `_bind_locked_now() is False` |
| 窗口内失败 N−1 次 | 第 2 次之后计数 = 2 < 3 → **没锁** |
| 第 N 次触发锁定 | 第 3 次之后 `_bind_locked_now() is True`，而**那一发的响应体与第 1 发逐字节相同** |
| 锁定期内再试 | 第 4 次 → **403**、`content` 与第 1 发**逐字节相同**、`content-type` 相同、三格字面值是 `forbidden` / `学号或验身材料不正确，无法绑定口令` / `detail is None`；⚠️ **第 5 拍**：锁内拿**正确**的材料也是同一个 403 |
| 窗口过期后自动解开 | ORM 层注入 `now` 走完整条时间线：`T0` 锁 → `T0+59min` 仍锁 → `T0+60min` **已解**；⚠️ 并断 `T0+20min` 时**登录**那一组已经不锁了（它的 `lock` 是 15）而绑定仍锁 ⇒ 「绑定读了登录那一组阈值」这个失效会当场红 |

### 5.4 ⚠️ 交叉不污染守卫（派单 §2.7 ②：本件最容易做错的一格）

**ORM 层**（`test_the_two_purposes_never_share_a_counter`，四拍）：

1. 3 次**绑定**失败 ⇒ `is_locked(purpose=bind) is True` 而 `is_locked(purpose=login) is False`、
   且登录那一维的失败计数是 **0**；
2. 5 次**登录**失败（另一个标识）⇒ 登录锁了、**绑定没锁**、绑定那一维计数 0；
3. 绑定失败 2 次 + 登录失败 4 次（第三个标识）⇒ 两个计数分别是 **2** 与 **4**、两个都没锁
   （⚠️ 本拍挡的是「键相同但阈值不同」那种**半对**的实现：它会让 ①② 在阈值边界上恰好看不出来）；
4. **定点变异**写在 docstring 里（§6.5）。

**HTTP 层**（`test_a_bind_lock_does_not_lock_the_same_persons_login_and_vice_versa`，两个方向、
⚠️ 用**两个不同的人**，因为一个锁在 60 分钟内不会自己解开）：

* ① 学生 `S2025001`：绑定成功 → 3 次材料不符把**绑定**打锁 ⇒ `is_locked(purpose=login) is False`
  **且**拿正确口令登录仍然 **200** + `Set-Cookie`；
* ② 教师 `T0001`：绑定成功 → 5 次错口令把**登录**打锁 ⇒ `is_locked(purpose=bind) is False`，
  而随后那一发绑定 403 **写了一行**（⚠️ 判据是「写了行」—— 锁定档一行都不写，
  故「写了行」就证明它走的不是锁定档）。

**清零只清自己那一维**（`test_clearing_one_purpose_leaves_the_other_purposes_rows_alone`，
两个方向各一拍）：2 次绑定失败 + 4 次登录失败 → 成功**绑定** → 绑定计数 0 而**登录计数仍是 4**；
再成功**登录** → 登录计数 0。⚠️ 少了这一格的失效形态是具体的：按 `(kind, login)` 删的话，
一次成功的绑定会把那个人**登录**的失败行一起删掉 —— 于是「攻击者先猜错四次口令、
随后那个人自己绑定成功」会把那四次失败**抹掉**，攻击者又能再猜五次。

**产品档端到端实测**（`scripts\serve.ps1 -Port 8020`，用一个**不在册的假学号**，故它不碰任何真账号）：

```
第 1 发 -> 403 (108 bytes) {"error":{"code":"forbidden","message":"学号或验身材料不正确，无法绑定口令","detail":null}}
第 2 发 -> 403 (108 bytes) …逐字相同…
第 3 发 -> 403 (108 bytes) …逐字相同…      ← 这一次之后进入锁定
第 4 发 -> 403 (108 bytes) …逐字相同…      ← 锁内
第 5 发 -> 403 (108 bytes) …逐字相同…      ← 锁内
第 1 发与第 4/5 发**逐字相同** : true
交叉不污染：学生 2023120001 登录 -> 200 ；T0001 登录 -> 200
```

⚠️ `smoke.mjs` 第 16 步 ⑭ 那一组是它的**端到端**版本（同样一律用不在册的假学号）；
文件头因此多了一节「它对**绑定限流**的依赖」，逐格取证本脚本对任何一个真账号最多只制造
**1** 次被计数的绑定失败，⚠️ 而下界是 `PE_BIND_MAX_FAILS` **恰好 3**
（③ 那一组要 ≥ 3、⑭ 那一组要 ≤ 3），故它同时是「缺省值没被人改过」的端到端守卫。
⚠️ 而 §16 步既有的 ③④⑤ 三拍**一个字都没改**：`SMOKE16` 只失手 1 次就绑定成功、
而成功会**清零**，故它离阈值 3 还差两次。

### 5.5 锁定档 body 逐字相同的取证

守卫 `test_a_locked_bind_answers_byte_for_byte_like_an_ordinary_material_mismatch`
（姿势照 `test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password`），
**两个端点各走一遍**（学生侧与教师侧的 message 是两句不同的常量，故「逐字相同」要各钉一次），
四拍 + 第 5 拍：

1. `locked.content == ordinary.content`（**原始字节**，不是解析后的 dict —— 解析后比较会把
   「键序不同」与「多一格空白」两档漏掉，而一个探测者读的正是字节）；
2. `content-type` 相等；
3. 三格字面值：`forbidden` / `学号或验身材料不正确，无法绑定口令`（教师侧是
   `工号或验身材料不正确，无法绑定口令`）/ `detail is None`；
4. status 相等且都是 **403** —— 不是 423、不是 429；
5. ⚠️ **锁内拿正确的验身材料也是同一个 403**（= 被锁的合法新生得不到任何提示；
   控制者显式接受，而它必须被钉住，否则下一个人「顺手加一句『多次失败后请稍后再试』」
   就会把枚举信号送回去，而**没有任何别的测试会红**）。

**改前实测的对照 body**（probe2，改前的服务上取的，作为「逐字相同」的基准）：

| 档 | status | bytes | body |
|---|---|---|---|
| 学生·材料不符 | 403 | **108** | `{"error":{"code":"forbidden","message":"学号或验身材料不正确，无法绑定口令","detail":null}}` |
| 学生·不在册 | 403 | **108** | 同上（**逐字相同** —— 那是既有裁定：不给区分信号） |
| 教师·材料不符 | 403 | **108** | `{"error":{"code":"forbidden","message":"工号或验身材料不正确，无法绑定口令","detail":null}}` |
| 学生·已绑定（正确 birth） | **409** | **270** | `{"error":{"code":"password_already_bound",…}}` |
| 弱口令 | 422 | — | `{"error":{"code":"unprocessable_value","message":"口令至少 8 个字符（收到 5 个）…"}}` |

⚠️ 锁定档回的就是上面**第一行/第三行**那两份，逐字节相同。

### 5.6 失效方向：锁定档在跑任何昂贵步骤之前返回（派单 §2.3）

**先实测绑定路径上有哪些昂贵步骤**（派单要「若绑定路径上有别的昂贵步骤，实测并说明」）：

| 步骤 | 代价 | 在改前的位置上 |
|---|---|---|
| `ensure_acceptable(password)` | **纯本地**（一个长度比较） | 第 1 位 |
| `auth_sessions.student_by_login` / `teacher_by_login` | 一次等值 `SELECT` | 第 2 位 |
| `_bind_credential` → `hash_password` | ⚠️ **PBKDF2**（生产缺省 600 000 次迭代 ≈ 0.3 s） | 只在**材料对了**之后 |
| `session.commit()` | 一次写事务 | 最后 |

⚠️ 结论：绑定路径上**唯一真正昂贵**的是 `hash_password`，而它在改前就**不在盲猜路径上**
（材料不对就走不到）；故本波「锁定档提前返回」省掉的是**那一次 `SELECT`**（以及
`_bind_credential` 的那一次 `UPDATE`，而那一档本来也走不到）。⚠️ 派单说的
「不许在锁定档去查 subject 行 / 算哈希」两格**都钉住了**（守卫用**替身计数**，
而不是耗时 —— 耗时断言在本机与噪声同量级、会间歇性红并被下一个人调松）。

⚠️⚠️ **一处顺序是承重的、且与派单的措辞有一点差别**（如实记）：锁定档排在
**查 subject 行之前**、而排在 **422 那一档之后**。理由是 `ensure_acceptable` 是纯本地判定、
`is_locked` 是**一次数据库查询**（`count(*)` + `max(at)`）—— 若把锁定档排在最前，
则一次弱口令探测就变成一次数据库查询，而那正是本端点**原有**那条「422 排在最前」
的注释要防的形状（「一个不需要账号就能打出来的 DoS 面」）。⚠️ 两格理由都写进了
端点函数体那一段注释里。

守卫 `test_the_locked_bind_tier_never_reads_the_roster_nor_hashes_a_password` 三拍：
① 一次**成功**绑定 = 查名册 **1** 次 + 哈希 **1** 次（绿档，证明两个替身真的拦到了）；
② 锁定之前的 3 次材料不符 = 查名册 **3** 次 + 哈希 **0** 次；
③ 锁定之后的 **20** 发 = 查名册 **0** 次 + 哈希 **0** 次。
⚠️ 另加 `test_the_locked_bind_tier_writes_no_row_so_the_lock_cannot_slide`：
23 发只留下 **4** 行（3 次失败 + 1 行成功绑定留下的 `ok=True`），锁内 20 发**一行都不写**
（⇒ 锁锚在最后一次真实失败上、不会被探测推后 = 不是滑动锁）。

### 5.7 成功绑定清零（派单 §2.6）

`record_success(purpose=PURPOSE_BIND)`：`clear_failures`（DELETE 这个键的全部行）+
一行 `ok=True`，**同一个事务**。⚠️ **端点因此不再自己 `commit`**：`record_success`
自己 commit，而那一次 commit **顺带**把 `password_hash` 那一次 UPDATE 一起提交 ——
「口令哈希落库」与「计数器清零」于是在**同一个**事务里（与登录侧「清零排在 `issue` 之前」
同一条口径）；反过来（先 commit 业务写入、再清零）会留下一个「口令已经绑上、而计数器
还没清」的窗口，而那个窗口里另一个请求会看到旧的失败数。⚠️ 代价如实记（硬规矩 #39）：
`record_success` 因此**不只是**一个限流动作，它在绑定那一档上同时是那一次业务写入的
提交点；要拆开就得让端点 commit 两次，而那正是上面那个窗口。已记在它的 docstring 里、不拆。

⚠️ **连带**：`login_attempt` 今天多了一类行 —— 一次成功绑定留下的 `ok=True`
（键带 `bind:` 前缀）。⚠️ 它与 `student.password_bound_at` 那一列在信息上**重叠**
（后者本来就记着「什么时候绑上的」），保留它的理由是**一致性 + 一个所有者**：
`record_success` 是「成功 ⇒ 清零 + 留一行痕迹」这件事在全仓的唯一住址，
而「清零」那半件事必须有一个提交点。⚠️ 三条既有守卫因此各改一次期望行数（§5.9）。

HTTP 层守卫 `test_a_successful_bind_clears_the_bind_failure_count_over_http`：
时间线刻意是「2 次失败 → 1 次成功 → 2 次失败」（**不清零**的实现会在第 5 行失败上锁）
+ 反空转「再来一次就锁」+ 点名断言**登录那一维一行都没有**。

### 5.8 ⚠️ 审计连带怎么落的（派单 §2.8：这里有一处顶回，见 §6.4 ③）

**先 `Grep` 确认「九档矩阵」是哪九档**：全仓 `Grep 九档` 只命中一处 ——
`.superpowers/sdd/2026-10-13-实施计划06-产品级硬化/task-5-6-report.md:969`
「**审计实测矩阵 + 隐私取证**：§2.2（九档，含「登录+一次写 = 恰好 2 行」「匿名读 = 0 行」）」。
⚠️ 即它**不是一条钉死档数的守卫**，而是 Task 5/6 报告 §2.2 的一张实测表，
对应的守卫是 `tests/api/test_audit_api.py` 里那一批（`test_one_login_plus_one_write_is_exactly_two_rows` /
`test_an_anonymous_read_writes_no_audit_row` / `test_a_write_to_an_unknown_path_is_still_recorded` /
`test_a_failed_authentication_is_one_anonymous_row` / `test_a_successful_logout_keeps_the_identity_that_logged_out` /
`test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row` /
`test_the_audit_endpoint_admits_only_an_admin` / `test_the_audit_trail_is_written_in_both_deployment_tiers` /
`test_the_four_auth_events_are_all_covered_by_the_single_method_predicate`）。

**实测结果**（改前的服务上取的，probe2）：`should_record` **只看方法**，两个 `bind` 都是
`POST`，故**每一档改前就已经在写**审计行：

```
POST /api/auth/students/bind -> 422 subject=anonymous/null target=null
POST /api/auth/teachers/bind -> 409 subject=anonymous/null target=null
POST /api/auth/students/bind -> 409 subject=anonymous/null target=null
POST /api/auth/students/bind -> 403 subject=anonymous/null target=null   ×3
```

⚠️ 于是**「锁定档要不要写审计行」这个问题的答案是「它本来就写」**：本波在审计那一侧
**一行代码都没加**、审计档数**一个都没变**、九档矩阵**一条守卫都没红**
（`test_the_four_auth_events_are_all_covered_by_the_single_method_predicate` 钉的是
`paths == [bind, bind, login, logout]` 那**四条各一发**的清单，本波没有给它加发数）。

⚠️⚠️ **而它答不了「谁被锁过」**（顶回，§6.4 ③）：`audit_log` 的 9 列里**没有任何一格**
能装「这一次是锁定」—— `subject_kind` 恒 `anonymous`（绑定端点不要身份）、
`target` 恒 `NULL`（那一路径**没有**路径参数，而 `target_of` 只从路径取、绝不解析响应体）、
`status` 恒 **403**（那正是裁定要的）。⚠️ 于是锁定档那一行与「材料不符」那一行**逐格相同**。
守卫 `test_the_locked_bind_tier_writes_the_same_single_audit_row_as_an_ordinary_mismatch`
把它钉住（逐格比 7 列 + 断言「**恰好一行**」+ 三格点名字面值）。
⚠️ 而那**同时**是好事：一行**可分辨**的审计就等于一个**可分辨**的响应，
而「响应可分辨」是裁定明确不要的（审计表是给管理员读的，但那一列一旦存在，
下一个想「顺手加一个 423」的人就有了落点）。
⚠️ 要让「谁被锁过」可查，得给 `audit_log` 加一列（= 改 schema = 配迁移 = 链 3 → 4），
本波**刻意不做**（交付前风险最小）；故 spec §1.2 第 15 条那一句「可见性留给 `audit_log`」
**只兑现了一半**，已把这一格写进 spec（§1.2 第 15 条 + §13.4.11）。

⚠️ **「锁定档写审计」与「锁定档不做任何昂贵步骤」不冲突**（派单点名要核的这一格）：
审计行由 `AuditMiddleware` 在**响应出来之后**写、用的是它自己那一个 `Session`
（`audit.record` 自己开、自己 commit），**不在端点的锁定档路径上**。
⚠️ 如实记的另一半：它因此是「每一个被锁的请求仍然要付一次 `INSERT`」——
而那一格**改前就存在**（登录侧的锁定档同样写一行审计），不是本波引入的。

### 5.9 同步的三条既有守卫 + 守卫清单

**三条既有守卫各改一次期望行数**（成功绑定今天会留下它自己那一行 `ok=True`）：

| 守卫 | 改前 | 改后 | ⚠️ 它钉的那件事变了吗 |
|---|---|---|---|
| `test_the_not_bound_tier_records_nothing_so_it_cannot_lock_anyone_out` | 1 行 | **2 行**（`bind:` 前缀那一行 + 登录那一行），并显式 `order_by(id)` | **没变**：18 次 403 之后库里**仍然是空的**（那一拍排在两次成功之前） |
| `test_the_locked_tier_writes_no_row_so_the_lock_cannot_slide` | `before == 5` | `before == 6` | **没变**：锁内 20 发之后行数**不动** |
| `test_the_attempt_rows_carry_the_kind_the_login_and_the_client_ip` | 1 行 | **2 行**（两行的 `ip` 都是 `testclient`） | **没变**（⚠️ 而它顺带把「端点真的读了 `request.client.host`」这一格从 1 个端点扩到 **3** 个） |

**本波新加的守卫 19 条**（ORM 11 + HTTP 8）：

* `tests/auth/test_policy.py` 第 ⑦ 节 **11** 条：缺省字面量 3/15/60 · 「比登录更严」的三条
  可判定比较 + 直接算 `72 < 480` · 三格各自可调且不串到登录 · 坏值响亮且点名自己的变量 ·
  键的映射 + 登录键不变 + AST 数 `_key` 的 5 个调用点 · 不认识的 `purpose` 在**五个**动作上
  都抛（+ 反空转：两个合法取值都不抛）· **交叉不污染**四拍 · 清零只清自己那一维 ·
  成功清零 · 锁到点自解（注入 `now`，60 分钟）· 两组阈值不串线两个方向
* `tests/api/test_auth_api.py` ①-c 节 **8** 条：逐字节相同（两个端点各一遍 + 锁内正确材料）·
  不查名册不跑哈希 · 锁内不写行 · 成功清零（HTTP）· **交叉不污染**（HTTP，两个方向）·
  三格可调（HTTP）· 409 那一档未被改得更可区分且不计数 · 审计行逐格相同
* ⚠️ 另把 `_clean_env` 那个 `autouse` 夹具从**三个**环境变量扩到**六个**
  （两组阈值走同一份解析，故一个在 shell 里设过的 `PE_BIND_LOCK_MIN` 会以完全相同的
  方式污染缺省档断言）；`_fail_n` 加了一个 `purpose` 形参（缺省 = 登录，故既有调用方一行都没改）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / 顶回

### 6.1 待清扫（**6 条**，本波新登记 4 条 + 接手 2 条）

| # | 条 | 来历 |
|---|---|---|
| 1 | `login_attempt.login` 是 `String(32)`，而绑定那一档的键是 `"bind:" + 学号`（最长 5 + 32 = 37）。SQLite 不校验 `VARCHAR(n)` 长度、本仓今天只跑 SQLite，故它今天无害；**换别的后端之前要先给这一列加宽**（= 一条迁移） | 本波新登记 |
| 2 | 「谁被锁过」在库里**仍然查不出**：`audit_log` 的 9 列里没有任何一格能装它。要可查得加一列（= 改 schema = 迁移链 3 → 4）。⚠️ 登录侧同一格（Task 3 就登记过），本波把它**如实收窄**成「审计行写了、但不可分辨」 | 接手 Task 3 / Task 5 的那一条，本波改写 |
| 3 | `app/main.py` 的模块 docstring 里有一处裸转义序列 `\s`，任何对它跑 `ast.parse` 的守卫都会冒一条 `DeprecationWarning`。⚠️ 本波的 AST 守卫就地压掉了它（`warnings.catch_warnings()`）而**没有去改那个文件**（那是另一件事） | 本波新登记（首跑实测到） |
| 4 | `smoke.mjs` 第 14 步对 `/s/mini-test` 的两条 needle 仍然是**静态模板文字**（Task 9 登记的那一条）。⚠️ 本波只把**教师页那一格**做成了真取证（§3.5），学生页那一格**没动**（派单没要求、且它要另取一份学生侧的期望值） | 接手 Task 9 的那一条，本波**部分**收掉 |
| 5 | `npm run gen:api` 的输入是**在跑的那个服务**（`http://127.0.0.1:8000/openapi.json`），故「产物对不对」取决于「你起服务的时候代码是什么状态」，而那一格是**静默**的（本波踩了一次，§4.2）。应当加一个「从离线的 `create_app()` 取 spec」的档 | 本波新登记 |
| 6 | 新端点为判「是不是管理员」多查了一次 `teacher` 表（`require_teaches_student` 内部已经调过一次 `require_staff`）。演示库上那张表 **3** 行、生产上几十行，两次等值主键查询的代价可忽略；要省掉它得让 `require_teaches_student` **返回** role（那是一次全仓签名改动） | 本波新登记（端点 docstring 里也如实记了） |

### 6.2 关切（不改，只记）

1. **教师页那一块的三格今天有两个数据来源**（班级端点给 `shuttle_score` + 变体给三格），
   而 `shuttle_score` 在两处**都有**。本页刻意仍从**班级端点**读它（因为 `sample` /
   `slower` / `tied` / `rank` 四格要**全班**的行，而变体只给一个人的）。
   ⚠️ 于是「同一格在两处必须相等」这件事由后端守卫钉（§2.4 第 1 拍）+ smoke 第 14 步
   第三拍交叉验证，而**不是**由「前端只读一处」保证。
2. **绑定限流挡不住「已登录的教职抢绑」**（他一次就猜中，spec §1.2 第 3/4 条已接受）。
   要挡住它得换验身材料（一次性绑定链接 / 校园卡后台校验），那是设计改动、不在本波。
3. ⚠️ **`serve.ps1` 在明文 http 上不能带 `PE_ENV=prod`**（本波踩了一次、当场停掉重起）：
   `prod` 档会给 cookie 加 `Secure`，而浏览器在明文 http 上**拒收**它，症状是
   「登录 200、下一个请求 401」。脚本自己的输出里逐字写着这一条（「同源 http 的产品档
   请留在缺省的 dev 档」），故本波的产品档实测是 **dev 档 + 同源 8020**。
4. **`_key` 的前缀是一个存储细节**，而它出现在守卫的期望值里
   （`("student", "bind:S2025001", True)`）。⚠️ 那是**有意的**（硬规矩 #35：期望侧字面写死，
   否则「把前缀改掉」会同时改掉两边、断言恒成立），代价是「换前缀」要改三条守卫。

### 6.3 没按派单做的（**1 处**）

| 派单原文 | 实际做的 | 为什么 |
|---|---|---|
| §1.6「⚠️ 你可以保留它，也可以改回读新端点的 `squat_score`；选一个并说明理由（控制者倾向：改回读新端点）」 | **改回读新端点** | 与控制者的倾向一致，故严格说这一格**不算**「没按派单做」。⚠️ 本波真正**没按派单做**的只有下面这一处 —— |
| §2.8「**锁定档要不要写审计行？** ⚠️ 控制者裁定：**要** …… 但要先实测审计九档矩阵的守卫会不会因此红，若它钉死了档数，就同步它，并把新档报进报告」 | **一行代码都没加**（也**没有**新档） | 实测：`should_record` **只看方法**，两个 `bind` 都是 `POST` ⇒ 锁定档**本来就在写**一行审计（改前的服务上实测过 403 / 409 / 422 三档各一行）。故「要写」这个裁定**已经成立**、无需实现；而「新档」不存在（档数一个都没变）。⚠️ 而裁定的**目的**（「谁被锁过」这件事在库里查得到）**没有兑现**，且兑现不了 —— 逐字见 §6.4 ③ |

### 6.4 ⚠️ 顶回（**4 处**，其中 1 处 Critical）

**① 「用途」维度落在 `kind` 里做不到 —— 改成落在 `login` 里（派单 §2.1，⚠️ Critical）**

派单 §2.1 的路 ① 举的例子是 `login = ("student","2023120001")`、`bind = ("student_bind","2023120001")`，
即把用途编进 **`kind`**。**实测那一格在本仓做不到**：`login_attempt.kind` 上有一条
**SQL 层的 CHECK**（`ck_login_attempt_kind`），文本由 `LoginAttempt.KINDS` 生成，而它
**就是** `UserSession.KINDS` 那一个对象（`{"student", "teacher"}`，三张表同一族语义：
`user_session.kind` / `login_attempt.kind` / `audit_log.subject_kind`）。故
`kind="student_bind"` 会被**数据库自己拒收**（`IntegrityError`）——
守卫 `test_the_kind_check_constraint_has_teeth` 实测它真的有牙、并钉住那个集合逐字是两格；
另一条守卫钉住 `LoginAttempt.KINDS` **就是** `UserSession.KINDS` 那一个对象。
放宽它 = 改 DDL = 配一条迁移（链 **3 → 4**）+ 同步那两条守卫 +
把 `user_session.kind` / `audit_log.subject_kind` 的取值域一起污染
（「一次登录尝试属于哪一类人」与「一个会话属于哪一类人」是**同一个**取值域，
写两份的话加第三类身份时只改到其中一份，而漏掉的那一份是静默的 —— 那段注释逐字在模型里）。

⚠️ **本波的选择**：仍然是派单的路 ①（**编进键的字符串里**、不加列），只是**换一格承载** ——
编进 `login` 而不是 `kind`：`{"login": "", "bind": "bind:"}`。
于是派单倾向 ① 的那三条理由**全部成立**（不加列 = 不动 schema = 迁移链不变 = 交付前风险最小），
而 CHECK 那一格不被碰到。⚠️ 且**登录那一档的键逐字不变**（前缀是空串），
故库里已有的行不换键。⚠️ 代价两条如实记在 §5.1 末段（列宽 / 键碰撞），
两档今天都**不可达**（SQLite 不校验长度；构造碰撞需要管理员先建一个 `student_no` 带 `:` 的行）。

**② 绑定限流的缺省阈值：3 / 15 / 60（派单 §2.2 要「你定并说明」）**

派单只要求「比登录更严」并要取值与理由，**没有**给数。本波取 **3 / 15 / 60**，
理由是一条算术（§5.2 那张表）：出生日期约 **2 900** 个可信取值 ⇒ 「一天能试多少次」
从 480 收到 72 ⇒ 一个账号一天内被猜中从 ≈16.5% 收到 ≈2.5%。
⚠️ **而本波认为派单隐含的「越严越好」在这一格上有个上界**，故显式顶回一格：
`lock` **不取** 360（6 小时）或更长，因为本原型**没有口令找回**，
而绑定是**一次性**的入网动作 —— 一个把出生日期打错三次的新生如果被锁 6 小时，
他这一天就入不了网，而那是**用户侧**的失效（比「攻击者多猜几次」更难向甲方交代）。
⚠️ 取 60 分钟是这两头的折中，而**三格都是环境变量**，故甲方现场可以自己抬到 360
（⇒ 12 次/天 ⇒ ≈0.4%/天/账号）。⚠️ 守卫 `test_the_bind_threshold_is_stricter_than_the_login_one`
把「更严」拆成**三条可判定的比较** + 直接算 `72.0` / `480.0`，
故「看着更严、其实更松」的改动会当场红。

**③ 锁定档写审计**能兑现「写一行」，但兑现不了「谁被锁过可查」（派单 §2.8，⚠️ Critical）

派单裁定「锁定档**要**写审计行」，理由是「『谁被锁过』这件事今天在库里查不到 …
绑定锁定档写一行审计是**低成本高价值**的可见性」。**实测两格**：

* **「写一行」已经成立、无需实现**：`should_record` **只看方法**，两个 `bind` 都是 `POST`，
  故改前每一档（403 / 409 / 422）就已经各写一行，锁定档自然也写。⚠️ 于是本波在审计那一侧
  **一行代码都没加**、审计档数**一个都没变**、九档矩阵**一条守卫都没红**（§5.8）。
* ⚠️⚠️ **「可见性」兑现不了**：那一行与「材料不符」那一行**逐格相同** ——
  `audit_log` 的 9 列里**没有任何一格**能装「这一次是锁定」（`subject_kind` 恒 `anonymous`、
  `target` 恒 `NULL`（那一路径没有路径参数，而 `target_of` 只从路径取、绝不解析响应体）、
  `status` 恒 **403** 而那正是裁定要的）。故管理员在 `GET /api/audit-logs` 上
  **仍然分不出**哪一行是锁定档。
  ⚠️ 要兑现它只有两条路：**(a)** 给 `audit_log` 加一列（= 改 schema = 配迁移 = 链 3 → 4，
  且要同步 `test_migration_baseline.py` 与「9 列」那一批守卫）；**(b)** 让锁定档回一个
  可分辨的 `status` —— 而 (b) **正是裁定明确不要的**（另给一个码就是枚举信号）。
  **本波选 (a) 也不做**：交付前风险最小（派单 §2.1 自己对 ① 的倾向就是同一条理由），
  且一行**可分辨**的审计会给下一个想「顺手加一个 423」的人一个落点。
  ⚠️ 故 spec §1.2 第 15 条那一句「可见性留给 `audit_log`」**只兑现了一半**，
  本波把它如实改写进 spec（§1.2 第 15 条 + §13.4.11 的「审计连带」那一段），
  并用守卫把「逐格相同」钉住（免得下一个人以为那一格已经可分辨了）。

**④ 「深蹲得分」那一格读哪儿（派单 §1.6）**：**同意控制者的倾向**（改回读新端点），
理由三条逐字见 §3.2。⚠️ 本条**不是**顶回，是复核后同意 —— 按派单 §4 的要求显式写出：
核过的决定是「保留 `squat_30s_count` 也**不算错**（那条逐行相等的守卫今天仍然绿），
而改回读新端点更强，因为**同源比等价强**（读的人不必再论证两个数为什么一样）」。

⚠️ 另**复核后同意**的三格（派单 §4 点名要「若顶回 0 处，显式写并说明核过哪些决定」，
本波顶回 4 处，故把**同意**的那几格也逐条列出，免得下一个人以为没核过）：

* **§1.1 新端点的路径与那一族同址** —— 同意。实测那一族今天有两条、都在 `dashboard.py`，
  而 helper 住在数据所在的那个 router、由 `dashboard` 跨模块 import 私有名
  （先例：`_weekly_sheet_response` 住在 `prescription.py`）。故新端点住 `dashboard.py`、
  从 `feedback.py` import `_normalized_self_body`，与先例逐字同构。
* **§1.2 闸门复用 `require_teaches_student` + 管理员越过任教范围 + 学生会话 403 + 匿名 401**
  —— 同意，且**实测**了那一族今天对 admin 是 200（§2.1），本端点照抄、**不自创**；
  ⚠️ 而守卫**当场复验**了 `/home` 与 `/weekly-sheet` 对同一个管理员也是 200
  （免得「本端点比那一族更宽」这件事没人看着）。
* **§1.3 形状恒定 = 返回那一个学生的 normalized 行、全列** —— 同意，且**响应模型直接复用**
  `NormalizedSelfRead`（不是新造一个同形的模型），故两个端点在 `/openapi.json` 上
  指向**同一格** schema、前端生成的 TS 类型只有一份 —— 那让「教师侧与学生侧逐字同形」
  变成**类型上**成立、而不是一句要靠守卫维持的约定。先例是 `WeeklySheetRead` 与
  `StudentHomeRead`（各自也被两个端点共用）。
* **§2.4 锁定档回「与材料不符逐字相同的那一档」** —— 同意，理由与 Task 3 对 423/429 的
  改判逐字相同；⚠️ 并补一格派单没点名的：**409 那一档本波一个字都没改**（§2.5 那条派单
  要求「核实新加的限流没有让它变得更可区分」，实测：409 = 270 B、403 = 108 B，
  两档**仍然**可区分 —— 那是既有裁定接受的残余，而限流**没有**加大它，
  因为 409 那一档**不计数**、锁定档也**不改变** 409 的 body）。
* **§2.6 成功绑定清零** —— 同意（与登录同一条口径）；⚠️ 而实现上它连带两格派单没点名的
  决定，都如实记在 §5.7：① 端点**不再自己 commit**（`record_success` 那一次 commit
  顺带提交 `password_hash` 的 UPDATE，两者同一个事务）；② `login_attempt` 因此多了一类行
  （成功绑定留下的 `ok=True`），三条既有守卫的期望行数各 +1。
* **§2.7 守卫四件（五档矩阵 / 交叉不污染 / 定点变异 / 三格可调）** —— 同意，
  且**每一件都做了 ORM + HTTP 两层**（两份刻意不合并：ORM 那一半证的是 `policy` 的键分了
  三维，HTTP 那一半证的是**两个端点各自交对了 `purpose`**；一个把 `purpose=` 写漏的端点
  会让 ORM 那一半绿、HTTP 那一半红）。

### 6.5 定点变异（**4 条**，全部亲跑复现：改前绿、改后红）

| # | 变异 | 红在哪 | 结果 |
|---|---|---|---|
| A | `policy._key` 改成忽略 `purpose`（`_check_purpose(purpose); return login`） | `test_the_two_purposes_never_share_a_counter` + `test_clearing_one_purpose_leaves_the_other_purposes_rows_alone` + `test_a_bind_lock_does_not_lock_the_same_persons_login_and_vice_versa` | 改前 `3 passed` → 改后 **`3 failed`** ✓ |
| B | `bind_student` 里删掉 `is_locked` 那一段（= 锁定档不再提前返回） | `test_the_locked_bind_tier_never_reads_the_roster_nor_hashes_a_password` + `test_the_locked_bind_tier_writes_no_row_so_the_lock_cannot_slide` | 改前 `2 passed` → 改后 **`2 failed`** ✓ |
| C | 新端点里 `allowed_sections` 恒置 `None`（= 不裁班） | `test_the_teacher_variant_never_reopens_the_cross_teacher_read` + `…agrees_with_the_student_side_endpoint_cell_for_cell` | 改前 `2 passed` → 改后 **`2 failed`** ✓ |
| D | 把 `_normalized_self_body` 复制一份进 `dashboard.py`（= 第二个所有者） | `test_the_normalized_projection_and_the_formula_each_have_exactly_one_owner` | 改前 `1 passed` → 改后 **`1 failed`** ✓ |

⚠️ 四次变异**跑完立刻还原**，还原后 `git status --porcelain` **为空**（脚本末拍当场打印）。

---

## ⑦ 最终验收

### 7.1 后端

| 项 | 基线（Task 9 之后） | 本波 | |
|---|---|---|---|
| `pytest -q --cov=app` | 1504 passed + 1 skipped（合计 1505） | **1529 passed + 1 skipped**（合计 **1530**；347.84 s 与 351.58 s 两次跑，第二次带 `--branch`） | ✅ **+25** |
| `pytest -q`（不带 `--cov`） | 1505 passed | **1530 passed**（⚠️ 实测过程如实记：`gen:api` 产物入库**之前**那一次跑是 `1 failed, 1529 passed`，红的那一条正是一致性守卫；产物在 commit ② 入库之后转绿） | ✅ |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | ✅ 一字未变 |
| 全仓 TOTAL（不带 branch） | — | 7222 stmts / 200 miss / **97%** | ✅ |
| 表数 | 28 | **28**（`len(Base.metadata.tables)`） | ✅ |
| **迁移链** | 3、单头 | **3、单头 `7f3923d8af84`**（`versions/*.py` 仍是 3 个文件） | ✅ **仍是 3** |
| 扫描面 | 71 | **71**（pipeline + db + domain + api + auth 的 `.py`） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（守卫 `assert len(...) == 33` 绿） | ✅ |
| `_MODELS_SUBMODULES` | 8 | **8**（守卫绿） | ✅ |
| 黄金用例 | 14 | **14**（`tests/domain/test_prescription_templates.py` 的 `len(reachable) == 15`… ⚠️ 那一条是「15 个动作」；黄金用例 14 那一格由 `test_all_eighteen_share_the_same_review_and_version_block` 一族钉，全绿） | ✅ |
| 新增测试 | — | **25**（`test_dashboard.py` +6 / `test_policy.py` +11 / `test_auth_api.py` +8） | ✅ |

### 7.2 openapi 五格（离线 `create_app()` 实测）

```
路径模板 74 · 操作 102 · 挂 security 84 · GET 63（匿名 15 + 挂 security 48）· securitySchemes 3
catch-all 漏进 paths 0 · 顶层 security None
```

### 7.3 前端

| 项 | 基线 | 本波 | |
|---|---|---|---|
| `npm run build` 退出码 | 0 | **0** | ✅ |
| 产物哈希 | `index-CPgg7MK0.css` / `index-NK5dQM2J.js` / chunk `AuditLogList-C3Vmc5lG.js` | **`index-CPgg7MK0.css`（65.20 kB，哈希未变）** / **`index-DaycGB6S.js`（167.95 kB）** / **`StudentDetail-oGny8jrh.js`（39.02 kB）** / **`AuditLogList-CBAg61k7.js`（9.44 kB）** | ✅ 变了（应当变） |
| `check:tokens` | 绿（扫描面 36、下界 25） | **绿**，退出码 0，扫描面 **36**（下界 25）；「36 个文件里，`tokens.css` 之外一个色值字面量都没有」 | ✅ |
| `check:dist` | 绿 | **绿**，退出码 0（`adoptFromUrl` 0 次、`fonts.googleapis.com` / `fonts.gstatic.com` 各 0 次，而三条谓词都不空转） | ✅ |
| `npm run gen:api` | — | 退出码 **0**、产物 **+307 / −19 行**、480 541 B → **517 231 B** | ✅ |
| 依赖清单守卫 | 后端 7+3+1、前端 3+7 | **一字不红**（`package.json` 的 `dependencies` 3 + `devDependencies` 7 一个字没动；后端 `pyproject.toml` 没动） | ✅ |
| **`smoke.mjs` dev 档** | 18 步 / 560 断言 / 退出码 0 | **18 步全绿 / 591 断言（591 绿 0 红）/ 退出码 0**（vite **5174** + demo **8000**） | ✅ |
| **`smoke.mjs` 产品档** | 同上 | **18 步全绿 / 591 断言（591 绿 0 红）/ 退出码 0**（`serve.ps1 -Port 8020`，同源） | ✅ |
| 路由条数 | 16（smoke 的 `ROUTES`） | **16**（`eq('路由条数 = 16 …', ROUTES.length, 16)` 绿；`router/index.ts` 的 `routes` 数组仍是 20） | ✅ |

⚠️ smoke 的 560 → **591** = **+31**，逐拍点数：第 13 步 **+19**（教师侧变体那一组：
1 拍前置「找得到小测行」+ 五档 9 拍 + `/me` 对照 1 拍 + 逐字相同 1 拍 + 裁班 2 拍 +
形状 2 拍 + 缺参 1 拍 + 声明面 3 拍）、第 14 步 **+3**（真取证三拍；⚠️ needle 从 5 项变
6 项**不加断言数**，它改的是那一条 `check` 的 detail 与 `dumpRoute` 的轮询退出条件）、
第 16 步 **+9**（⑭ 那一组）。19 + 3 + 9 = **31** ✓

### 7.4 禁区与指纹

| 项 | 实测 |
|---|---|
| 四个数据指纹（口径 = **入库 blob** 的 `sha256[:16].upper()`） | `D2C8E539E2FA0029`（`national_standard_2014.csv`，21 412 B）✓ · `5394B37F01DAC9AC`（`exercises.yaml`，23 247 B）✓ · `822CB86A5E998301`（`exercise_equivalence.yaml`，8 245 B）✓ · `E48E3AC82BB45BB7`（`alert_rules.yaml`，6 037 B）✓ |
| **18 套处方模板指纹** | `backend/data/prescription/*.yaml` **恰好 18 个文件**，逐个 blob 指纹列出（`RED-END-ABN-01` `C0C61D2140A521D0` … `GRN-SPD-NOR-18` `2389C1A03E6ABBCE`）；⚠️ 而**更强的证据**是下面那一行 |
| `git diff 7dca18f HEAD -- backend/data` | **空**（0 字符）⇒ `backend/data/**` 一个字节都没动 |
| `backend/pe.db` | **False**（不存在） |
| `backend/data/seed/` | **0 文件** |
| `frontend/dist` 未入库 | 入库文件 **0**、`git status --ignored` 上是 `!!`（被忽略） |
| `.gitattributes` | `git diff 7dca18f HEAD -- .gitattributes` **空**（一条都没碰） |
| 没跑过 `app.seed.generate` / `backfill` / `daily` | ✓（要数据一律用 `demo.ps1`；⚠️ `demo.ps1` 的 `[3/7]`/`[5/7]` 两步会跑 `run_daily`，而那是它自己的流程、且写的是 `pe_demo.db`，不是禁区） |
| 我起的进程全部已停 | ✓（`demo.ps1` ×3、`vite --port 5174`、`serve.ps1 -Port 8020` ×2、两次全量 pytest、一次 branch 覆盖率跑，全部停/退出）；⚠️ **5173 上那个不是我起的 vite（PID 20240）仍在跑，按纪律没有杀它** |
| `$env:TEMP\p06t10` 已删并复验 | 见 §7.6（本报告写完之后才删，故此处先记「待删」→ 删完复验为 `False`） |

### 7.5 spec

| 项 | 基线 | 本波 |
|---|---|---|
| 工作树字节 | 336 741 B | **366 608 B** |
| 行数 | 3 067 | **3 356** |
| 行尾 | 全 CRLF、裸 LF 0 | **全 CRLF（3 356）、裸 LF 0** |
| BOM | 无 | **无** |
| `sha256[:16]` | `f62529910792a5ff` | **`b132f04d6f7efac8`** |
| `git diff --numstat` | — | **+296 / −7** |
| 入库 blob 字节 | 333 674 B | **363 252 B**（= 工作树 366 608 − 3 356 个 CRLF 的 1 字节差） |
| `git ls-files --eol` | `i/lf w/crlf attr/text eol=crlf` | **同**（`.gitattributes` 的 `Document/**/*.md text eol=crlf` 生效中） |

改了 **10 处**：§1.2 第 2 / 4 / 14 / 15 条各补一段 · §13.4.2 的表两个 `bind` 行加锁定档 ·
§13.4.4 那张表的「路径模板」一行补到 74 · §13.4.6 末尾指向 §13.4.11 ·
§13.4.9 的 `StudentDetail.vue` 那一条标注「已过期」 · **新增 §13.4.10**（教师侧变体）·
**新增 §13.4.11**（绑定限流）· §13.5 的五格 + 一整段 Task 10。

### 7.6 commit

| # | sha | 一句话 | 自洽? |
|---|---|---|---|
| ① | `d3f9c58` | 后端教师侧变体端点 + 6 条守卫 + openapi 五格断言同步 | ⚠️ **一处不自洽**：`gen:api` 的产物在 ② 才入库，故本 commit 上 `test_the_generated_typescript_client_matches_the_current_openapi_document` 是**红**的（逐字记在 commit 信息末段） |
| ② | `9bce5d0` | 后端 bind 限流（键的「用途」维 + `PE_BIND_*` 三格 + 锁定档逐字相同 + 清零 + 审计连带）+ 19 条守卫 + 3 条既有守卫同步 + **`gen:api` 产物** | ✅ 自洽（本 commit 起全绿） |
| ③ | `154759d` | 前端 `StudentDetail.vue` 三格恢复 + `endpoints.ts` + `smoke.mjs` 两档同步 | ✅ 自洽 |
| ④ | 本 commit | spec 10 处 + 本报告 | ✅ 自洽 |

⚠️ **①的那一处不自洽是结构性的**：`gen:api` 的产物必须与**产生它的那些 docstring**
同一个 commit（那正是 Task 8b 那条一致性守卫的意义），而本波**两件都改了 docstring**
（新端点的 + 两个 `bind` 的），故产物只能落在**后一个**后端 commit 上。
⚠️ 已如实记在 ① 的 commit 信息末段与本表里。

### 7.7 探针目录

`$env:TEMP\p06t10\` 跑完**只删这一个子目录**并复验（`Test-Path` → `False`）。
⚠️ `$env:TEMP` 里躺着的那约 110 个之前各波留下的 `pe_*` 探针**一个都没删**
（不是本波的产物，统一清理是下一波的事）。

---

## ⑧ 行尾复核（逐个被改文件的 `git ls-files --eol`）

本机 `core.autocrlf = true`，故**两个口径都要报**：入库 blob 一律 `i/lf`，
工作树一律 `w/crlf`（唯一例外是 `schema.d.ts`，它是 `openapi-typescript` **自己**写出来的、
用 LF，改前也是 `w/lf`）。

| 文件 | `git ls-files --eol` | 期望 | |
|---|---|---|---|
| `backend/app/api/routers/auth.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/app/api/routers/dashboard.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/app/api/routers/feedback.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/app/api/schemas/feedback.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/app/auth/policy.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/tests/api/test_auth_api.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/tests/api/test_dashboard.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/tests/api/test_prescription_api.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `backend/tests/auth/test_policy.py` | `i/lf w/crlf attr/` | 同 | ✅ |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | 同 | ✅ |
| `frontend/src/api/endpoints.ts` | `i/lf w/crlf attr/` | 同 | ✅ |
| `frontend/src/api/generated/schema.d.ts` | `i/lf **w/lf** attr/` | 同（生成器自己写 LF，改前也是 `w/lf`） | ✅ |
| `frontend/src/views/teacher/StudentDetail.vue` | `i/lf w/crlf attr/` | 同 | ✅ |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | 同（`.gitattributes` 钉的 `Document/**/*.md text eol=crlf`） | ✅ |
| `.superpowers/sdd/…/task-10-report.md`（本文件） | `i/lf **w/lf** attr/-text` | 同（`.superpowers/** -text` ⇒ blob = 工作树，与另外 7 份报告逐字同形） | ✅ |

⚠️ **`.gitattributes` 一个字都没碰**（`git diff 7dca18f HEAD -- .gitattributes` 为空），
故那六条钉子（`backend/data/** eol=lf`、`woff2 binary`、品牌 svg `-text`、
`.superpowers/** -text`、`Document/**/*.md text eol=crlf`、两处 `*.ps1 text eol=crlf`）全部原样。

⚠️ **本波没有发生行尾/BOM 事故**（前四波各发生一次）：全部编辑走 `ed.py`
（二进制读 → 把插入文本的 `\n` 一律换成 `\r\n` → 二进制写），
且**每改完一个文件当场核** `git ls-files --eol`（上面那 15 行就是核的结果）。
⚠️ 报告与 commit 信息一律用 **Python 写 UTF-8 无 BOM**
（`msgs.py` 三份 commit 信息实测 `BOM=False`、`CRLF=0`；本报告同口径）。
⚠️ 唯一一次「工具吃字符」的坑是 PowerShell 5.1 里 `python -c` 嵌双引号 +
f-string 表达式部分不能有反斜杠（`f"...{b'\r\n'}..."` 当场 `SyntaxError`）——
按纪律改成写临时文件。

---

## 附：本波碰过的文件（14 个 + 1 个新建）

```
backend/app/api/routers/dashboard.py          ①（新端点 + 两个 import）
backend/app/api/routers/feedback.py           ①（_normalized_self_body + 3 处 docstring）
backend/app/api/schemas/feedback.py           ①（NormalizedSelfRead 的 docstring：两个消费者）
backend/app/auth/policy.py                    ②（用途维 + 第二组阈值 + 五个动作）
backend/app/api/routers/auth.py               ②（两个 bind 端点 + 模块 docstring）
backend/tests/api/test_dashboard.py           ①（支 D″ 6 条 + 模块 docstring + 3 个 import）
backend/tests/api/test_prescription_api.py    ①（expected 26 项 / 84 / 两处散文）
backend/tests/auth/test_policy.py             ②（第 ⑦ 节 11 条 + 夹具扩到六个环境变量）
backend/tests/api/test_auth_api.py            ②（①-c 节 8 条 + 3 条既有守卫同步）
frontend/src/api/generated/schema.d.ts        ②（npm run gen:api 的产物）
frontend/src/api/endpoints.ts                 ③（+1 个函数 + 1 处过期口径改正）
frontend/src/views/teacher/StudentDetail.vue  ③（三格恢复 + 6 处散文）
frontend/scripts/smoke.mjs                    ③（第 12/13/14/16 步 + 文件头两节）
Document/2026-09-28-体育闭环原型-设计spec.md   ④（10 处，含新增 §13.4.10 / §13.4.11）
.superpowers/sdd/…/task-10-report.md          ④（本文件，新建）
```
