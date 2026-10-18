# 实施计划 08 · Task 5 实现者报告（**续做**）—— 名册 `birth` 的可见面收窄

> 分支 `p08/birth-scope`。接手时 HEAD = **`48e3b9b`**（控制者打的那个 WIP 检查点，
> **2 个文件 +372 / −4**、**一个正式 commit 都没有**）。
> 本波在它上面打了 **4** 个正式 commit（sha 见 §9.14），`main` 仍是 **`d53e4dc`**、
> ⚠️ **一次都没 push**、**一次都没碰 main**、**没有 revert / cherry-pick 那个 WIP**。
>
> ⚠️ 本报告**刻意不印自己的字节数与 sha256**（不动点问题；Plan 07 Task 8 在这一族
> 连踩四次，教训在它报告的 §8.6）。

---

## ① 环境 + 接手现场 + 开工五格

### 1.1 环境（⚠️ 开工第一件事，硬规矩 #73）

| 格 | 值 |
|---|---|
| Node / Python | **v24.19.0** / **Python 3.11.1**（无 venv） |
| 仓库根 / 分支 / HEAD | `c:\Users\whwenhao\Desktop\Physical_Education_ims` / **`p08/birth-scope`** / **`48e3b9b`** |
| `main` | **`d53e4dc`**（Task 4 结案）；⚠️ 全程未动、未 push（⚠️ 接手时它已有 **6** 个 commit 待推，github 间歇性连不上，按派单由控制者重试） |
| 接手时工作树 | `git status --porcelain` **空**（干净） |
| PowerShell | 5.1（`;` 分隔、无 `&&`、⚠️ `python -c` 嵌双引号会被吃掉 ⇒ 一律写临时脚本文件） |
| 我自己的探针目录 | `%TEMP%\p08t5b\`（⚠️ 收尾删净并复验，见 §9.12） |
| 我自己起的实例 | 后端 **8041**（`PE_DB_URL` → `%TEMP%\p08t5b\pe_probe.db`，`demo_bootstrap.py` 灌的 60 人库）· dev 档后端 **8000**（`demo.ps1`）· 产品档 **8020**（`serve.ps1 -SkipBuild`）· 试用档 **8042**（`trial.ps1`，库在 `%TEMP%`）· vite **5199**（`PE_API_TARGET` 指到我自己的后端） |

### 1.2 开工五格（⚠️ 逐项亲量，**不是**抄派单）

| # | 格 | 开工实测 | 与控制者给的数对得上吗 |
|---|---|---|---|
| 1 | uvicorn（试用档服务） | PID **59760** 在，`StartTime = 2026-10-18 19:48:50` | ✅ |
| 2 | `cloudflared`（公网隧道） | PID **59472** 在，`StartTime = 2026-10-18 19:51:18` | ✅ |
| 3 | `backend/pe_trial.db` | **1 609 728 B** / sha256[:16] **`EC7EE58450A42B51`** | ✅ 字节数逐字相符（⚠️ sha 派单让我自己量，这就是量出来的值） |
| 4 | `frontend/dist` | **27** 文件 / **707 713 B**；`index.html` **2 567 B** / sha256[:16] **`141C673FD0BB4B57`**；`index-Ch2KuVNg.js`（251 917 B）+ `index-BuNW43q3.css`（66 664 B） | ✅ 五格逐字相符 |
| 5 | 本机 8030 匿名 health | **200** `{"status":"ok","tables":30,"students":60,"trial":true}` | ✅ |

⚠️ 量第 3 格时踩到一格**已知**的坑（`trial.ps1` 的 G12 注释里逐字记着它）：
`Get-FileHash` 读不出被 uvicorn 持有的 SQLite 库（`The process cannot access the file …
because it is being used by another process`）。处置：改用 Python 的 `open(path,'rb')`
（MSVCRT 的共享模式是 read/write/delete 全开），**一次就成**、没有去动那个进程。

⚠️ **全程没有杀/重启 PID 59760 与 59472**、没有 `-Reset`、没有写 `pe_trial.db`、
没有对它跑迁移、**没有对 8030 或那条公网 URL 发过任何请求**（连匿名 GET 都没发过：
第 5 格量的是 **127.0.0.1:8030**）。⚠️ 也**没有重建 `dist`**（见 §5）。
⚠️ 不是我们的进程一律没动：5173 的 vite（PID 43520）与两个 `@deepseek-ai/dsh web`
（14368 / 16404）全程在世。

### 1.3 ⚠️⚠️ 接手现场最重要的一格：**WIP 的全量 pytest 今天是红的**

派单 §1 第 2 件把「WIP 今天是红是绿」称为「本波第一个要量的事实」。**逐字实测**
（`backend/` 下 `python -m pytest -q --no-cov`，300.66 s）：

```
1 failed, 1752 passed, 1 warning in 300.66s (0:05:00)
```

红的那**一条**是架构守卫
`tests/architecture/test_docstring_references.py::test_every_docstring_reference_points_at_a_name_that_exists`，
报错原文（逐字）：

```
2 处 docstring 引用指不到真名（一个读的人按它 git grep 会得到 0 个命中，
而他会以为是自己的搜索写错了）：
    app/api/crud.py:775 → 'test_the_mask_is_a_constant_shape_that_leaks_nothing_about_the_value'
    app/api/crud.py:904 → 'test_the_masked_and_the_full_bodies_differ_in_exactly_one_cell'
```

⚠️ **这一格是好事，而且它精确地指出了本波要做什么**：前一位在 `crud.py` 的
`BIRTH_MASK` 与 `_redacted_detail` 两段 docstring 里**先写下了两条守卫的名字**
（「守卫是 `tests/api/test_birth_scope.py` 的 …」），而那个文件**一个字节都还没写**。
⇒ 那条守卫把「实现写了、测试没写」这件事**当场**报出来了，
而本波第一个 commit 就是**照它点出来的那两个名字**把文件写出来（⚠️ 名字逐字用它，
不是我另起两个 —— 否则那段 docstring 又要改一遍）。

⚠️ 顺带一格：`1752 + 1 = 1753` = 基线的 passed 数 ⇒ **WIP 没有新增任何测试**，
与派单说的「前一位没做任何测试/守卫」逐字相符。

### 1.4 WIP 那 2 个文件各做了什么（逐格读过，⚠️ 而结论一律以实测为准）

**`backend/app/api/crud.py`（+352）** —— 值级变形的**全部**机制：

| 名字 | 是什么 | 本波实测复核 |
|---|---|---|
| `BIRTH_MASK = "****-**-**"` | 掩码字面量的**唯一所有者** | ✅ 全仓 AST 扫：`app/**` 里这个串作为**字符串常量**恰好出现 **1** 次、就是这一行；名字里带 `MASK` 的**模块级全大写**赋值也恰好 1 个 |
| `Redaction(column, mask, full_for)` | 「这一列对哪几档 `role` 给完整值」的**声明**（frozen dataclass） | ✅ |
| `REDACT_ADMIN_ONLY = frozenset({ADMIN_ROLE})` | 「谁读到完整值」的缺省声明 | ✅ 实测取值就是 `{"admin"}` |
| `masked_columns_for(redactions, request)` | **判据的唯一所有者**（返回 `{}` = 读完整值） | ✅ 单元级 + HTTP 级都验过；空声明**短路**、根本不碰 `request.state` |
| `_redact_rows(rows, masks)` | list 端点那个 `items` 数组的**就地**变形 | ✅ |
| `_redacted_detail(read_model, obj, masks)` | read-one 在要变形那一档返回一个 **`JSONResponse`**（绕开 `response_model` 的校验，于是 openapi 一个字节都不改） | ✅ 机制成立：教师档 200 而 openapi 逐字未变 |
| `staff_reader_of_request(request)` / `STAFF_READER_STATE_KEY` / `_require_staff_identity` | 「这一次请求的教职身份」的唯一写入口/读出口（走 `request.state`，不是模块级全局） | ✅ 没存过就 `RuntimeError`（响亮，不折成缺省身份） |
| 工厂第 **14** / **16** / **17** 道校验 | 列名存在 / `redact` 只许挂在 `read_scope="staff"` / `mask` 非空且 `full_for ⊆ STAFF_ROLES` | ✅ 三道各有一条守卫，定点变异 M11 证明第 16 道**不是**空转 |
| 新引进的 import | `fastapi.Request` / `JSONResponse` / `ADMIN_ROLE` / `STAFF_ROLES` | ⚠️ **`API_ALLOWED_PREFIXES` 一个字都没动**（`app.api.deps` 与 `fastapi` 本来就在白名单里），层依赖守卫全绿 |

**`backend/app/api/routers/catalog.py`（+24）** —— 在 `RESOURCES` 的 **student 那一行**
声明 `redact`（+ 20 行注释）。⚠️ **全仓唯一一格值级变形声明**，实测复核成立：
23 行里恰好 **1** 行声明 `redact`、路径 `/api/students`、列 `("birth",)`、
`read_scope == "staff"`、`require_admin is True`。

⚠️ **本波改了它一处注释**（纯注释、openapi 实测逐字未变）：WIP 写的是
「`ResourceDetail.vue` / `ResourceList.vue` 的编辑表单把响应体那一行预填进
`<input type="date">`」，⚠️ 而**实测** `ResourceList.vue` 那张表**根本没有 `birth`
那一列**（六列逐字是 id / 学号 / 名称 / 性别 / 年级 / 院系，无头浏览器 DOM 取证见 §5）
⇒ 按实测收窄成「只有 `ResourceDetail.vue` 的编辑表单会预填（`id="edit-birth"`）」。
⚠️ **裁定本身一格没动**（收窄它的那一条理由只是**旁证**，主理由「管理员本来就是
omnipotent 的那一档」照旧成立）。

---

## ② ⚠️⚠️ `birth` 离开服务器的**完整清单**（本件的核心交付物）

### 2.1 怎么找的（⚠️ 三面各查一遍，不是「读代码没看见」）

派单逐字要求「**自己 `Grep` 全仓 `birth`，不要只信控制者这份清单**」。做了三面：

1. **全仓 `Grep -i birth`**：后端 **305** 处 / **54** 个文件，前端 **55** 处 / **10** 个文件。
   逐个文件读过（⚠️ 大文件一律分节 `Grep`，没有用 `Read` 打开 `crud.py` / spec / `schema.d.ts`）。
2. **契约面**：`dump_openapi.py` 进程内取那份 spec，**77** 条路径逐条列出；
   全进程 **144** 个 Pydantic 模型（沿 `BaseModel.__subclasses__()` 传递闭包）里
   含 `birth` 字段的**恰好 4 个**：`StudentBindCreate` / `StudentCreate` / `StudentRead` /
   `StudentUpdate` —— ⚠️ 其中**只有 `StudentRead` 是响应模型**。
3. **运行面**：起 8041 探针实例（`demo_bootstrap.py` 灌的 60 人库），
   以**匿名 / 学生本人 / 普通教师 T0001 / 管理员 T0003** 四档身份，
   把 openapi 里**每一个 GET**（65 条）都真打一遍，逐个响应体查
   「库里那 **60** 个真实出生日期的 ISO 串有没有出现」+「掩码串出现几次」。
   ⚠️ **期望侧取自库、被测侧取自 HTTP 响应体**（两侧不同源，硬规矩 #109）。

> ⚠️ 第一版扫描探针有个 bug（`{student_id}` 被「随便填个 1」那一步抢先替换掉了），
> 于是学生/教师两档的**按人**端点其实打的是 id=1 而不是「对他打得通的那一个」。
> **已重写并重跑**（先查出 T0001 本学期任教班里的真学生、学生档用他自己的 id），
> 下面表里的每一格都是**第二版**的结果。如实记，因为它差一点让
> 「学生读自己那一档」的结论建立在一次 403 上。

### 2.2 四档身份的扫描汇总（**65** 个 GET 全打）

| 身份 | 读到**真实** `birth` 的路 | 出现**掩码**的路 |
|---|---|---|
| 匿名 | **0** 条 | **0** 条 |
| 学生本人（`2023120001` = id 4） | **0** 条 | **0** 条 |
| **普通教师 T0001** | **0** 条 | **2** 条：`/api/students`（掩码 ×50 = 那一页 50 行）、`/api/students/{student_id}`（×1） |
| **管理员 T0003** | **2** 条：`/api/students`（×50）、`/api/students/{student_id}`（×1） | **0** 条 |

⚠️ 于是「教师换一条路就拿到完整值」这一档**在运行面上不成立**：
65 个 GET 里出现真实出生日期的**只有那 2 条**，而它们恰好就是被声明了变形的那一个资源的
两个端点；对教师，那 2 条给的是掩码。

### 2.3 逐条裁定（**16** 条；⚠️ 派单点名的两条在**第 14、15** 条）

| # | 路 | 裁定 | 理由（一句话） |
|---|---|---|---|
| 1 | `GET /api/students`（名册 list） | **掩** | 本件要收的那一条；实测教师拿到 50 个掩码、**0** 个真实值 |
| 2 | `GET /api/students/{id}`（名册 read-one） | **掩** | 同一张表的另一条路，⚠️ **与 list 共用同一个判据**（`masked_columns_for`），故「列表里掩了、点进详情没掩」在结构上不可能（守卫逐行比两份响应体，只差 `birth` 一格） |
| 3 | `POST` / `PATCH` / `DELETE /api/students{,/{id}}` 的响应体 | **不适用** | `require_admin=True` ⇒ 教师四种写法各 **403 `forbidden`**（实测），而管理员本来就读完整值 |
| 4 | `GET /api/students/{id}/home` · `…/notifications` · `…/weekly-sheet` · `…/prescriptions/current` · `…/training-logs/completion-rate` | **不适用** | 响应模型是 `StudentHomeRead` 一族，⚠️ **逐字不含 `birth`**；实测学生本人 `/api/students/4/home` → **200** 而响应体里 `birth` 这一格**根本不存在** |
| 5 | `GET /api/teacher/students/{id}/home` · `…/normalized` · `…/weekly-sheet` | **不适用** | 同上；⚠️ 教师侧那三个变体要的是姓名/学号与训练数据，不是出生日期（实测教师档 `/home` 200 而 0 个真实出生日期） |
| 6 | 教师大屏 / 班级周报 / 预警队列 / 周训练单 / 处方 / 体成分 / 体测 / 常模 / 分层 / 派生指标 / 小测（`/api/dashboard/*`、`/api/alerts`、`/api/weekly-class-reports`、`/api/prescriptions`、`/api/body-compositions`、`/api/fitness-test-results`、`/api/training-logs`、`/api/mini-tests/*`、`/api/percentile-snapshots`、`/api/stratification-results`、`/api/derived-metrics`） | **不适用** | `app/api/schemas/dashboard.py` 与其余响应模型**一个 `birth` 字段都没有**（它们带的是 `student_id` / `name`）；实测教师档这些路全部 200 而响应体里 **0** 个真实出生日期 |
| 7 | `GET /api/auth/me` · `POST /api/auth/login` | **不适用** | 响应模型是 `SessionIdentityRead` 的**六格**（`kind`/`id`/`name`/`role` + 学号或工号），**不含 `birth`**（实测两档响应体逐字都是那六格） |
| 8 | `POST /api/auth/students/bind` | **不适用**（方向相反） | `birth` 在这里是**请求体**（客户端 → 服务器）；响应是 204 或错误，不回任何库里的值 |
| 9 | `POST /api/auth/bind-with-token`（§13.26） | **不适用** | 令牌那一档的请求体**刻意不含** `birth`（`TokenBindCreate` 逐字三格） |
| 10 | `audit_log`（写审计） | **不落** | 实测 **16** 行 × **9** 列，逐行 JSON 化后查 60 个真实出生日期与掩码串 → **0** 命中；末行样例只有 `at/subject_kind/subject_id/staff_no/method/path/status/target` |
| 11 | `read_audit_log`（读审计，§13.9.1） | **不落** | 实测 **180** 行 × **9** 列，同上 → **0** 命中；⚠️ 它记的是「谁、什么时候、读了哪条路、读到了谁」（`route` = `/api/students/{student_id}`、`student_id` = 1、`target` = `'1'`），**不是**读到的内容 ⇒ 「两条审计都宣称永不落请求体」那一句，**在响应体这一侧同样成立**（本波实测补上了这一半） |
| 12 | `/openapi.json` 的 example / schema | **不落** | 实测全文里 `birth` 出现 **21** 次而**全是字段名与散文**（`"birth":{"type":"string","format":"date","title":"Birth"}` 那一类）；日期形状的字面量只有 **3** 个（`2026-10-08` / `2026-10-12` / `2026-10-13`，都是业务日示例，**不是**任何人的出生日期）；掩码串 **0** 次 |
| 13 | 错误话里的回显（422 的 `detail[].input` / `ctx`） | **不算泄漏** | 实测管理员 `PATCH {"birth":"****-**-**"}` 的 422 响应体逐字是 `{"error":{"code":"request_validation_failed",…,"input":"****-**-**","ctx":{"error":"invalid character in year"}}}` ⇒ 回显的是**调用方自己提交的那一串**，不是库里的值；⚠️ 60 个真实出生日期在 422 响应体里 **0** 命中。**裁定：不算泄漏学生数据**（它连一格库里的值都没读出来），⚠️ 而它**是**「掩码不是合法日期」那一格的响亮证据 |
| 14 | ⚠️ **`GET /api/teacher/roster`** | **不存在** | 派单把它点成「本件的命门」（「这一条不掩，本件就等于没做」）。⚠️ **实测本仓没有这个端点**：openapi 的 77 条路径里 **0** 条匹配 `roster`；全仓 `Grep '/api/export\|teacher/roster'` **0** 命中。⚠️ spec §13.15 交付须知第 4 条说的「全校 60 人名册」指的就是 **`GET /api/students`**（= 第 1、2 条），本仓从来没有第二个名册端点 |
| 15 | ⚠️ **`/api/export/...`（导出侧）** | **不存在** | 同上：openapi 里 **0** 条路径匹配 `export` / `csv` / `download`。⚠️ 派单说的「逐资源列白名单、`birth` 在列级被放行」在本仓对应的是**两件别的事**：① **`list_exclude`** —— 23 行 `RESOURCES` 里只有 **3** 行声明它，排的是 `password_hash` / `password_bound_at` / `rpe_token` 三类**凭据**列，⚠️ **`birth` 从来不在任何一行的 `list_exclude` 里**（它不是「被放行」，是「压根没被这套机制管过」）；② **`app/adapters/base.py` 的 `STUDENT_COLUMNS`** —— 那是**入站**的模拟数据源（`students.csv`）**列序契约**，由 `app/adapters/mock_lepao.py` 读、由 `app/seed/generate.py` 的 `write_csv` **离线**写（写的是 `%TEMP%` 下那份 CSV，⚠️ `backend/data/**` 一个字节都没动），⚠️ **一个字节都不经 HTTP**、不跨任何鉴权边界。**守卫**：全仓 import `STUDENT_COLUMNS` 这个名字的模块**恰好 1 个** = `app/adapters/mock_lepao.py`，HTTP 层 **0** 个 |
| 16 | 服务端的年龄计算（体测评分 / 处方强度） | **不经 HTTP** | `app/pipeline/percentile_stage.py` 的 `age_at(student.birth, current.start_date)`（第 256 行，从 `session.scalars(select(models.Student))` 拿 ORM 行）与 `app/domain/prescription/intensity.py` 的 `age_from(birth, as_of)` 都是**在服务端从 ORM 行直接读**、算完只把 `age` 往下游传 ⇒ ⚠️ 计划 §5 要求的「若某处业务上必须要完整值，那一处要留在服务端算、不把原始值发到前端」**今天已经成立**，本波**一行都没改**、也**不需要**改 |

### 2.4 ⚠️ 「将来有人真的加了第二条路」这一档不会静默

第 14、15 条今天的裁定是「不存在」，⚠️ 而「不存在」不是一个能长期依赖的答案。
故本波把它落成**三条结构守卫**（都在 `tests/api/test_birth_scope.py` 里）：

1. `test_the_students_roster_is_the_only_response_model_that_carries_a_birth`
   —— 全进程 **144** 个 Pydantic 模型逐个查：含 `birth` 字段的**恰好**是那 4 个，
   而其中**只有 `StudentRead`** 被 `RESOURCES` 当成读模型。
   ⚠️ 于是「新加一个带 `birth` 的响应模型」当场红。
2. `test_every_birth_bearing_resource_row_declares_a_redaction_covering_it`
   —— 23 行 `RESOURCES` 里**任何**读模型含 `birth` 的行，**必须**声明覆盖它的变形。
   ⚠️ 于是「新加一个含 `birth` 的资源而忘了声明变形」当场红。
3. `test_there_is_no_export_or_roster_route_and_the_csv_contract_never_crosses_http`
   —— openapi 里**不许**出现匹配 `export|roster|csv|download` 的路径，
   且 `STUDENT_COLUMNS` 的 importer 集合**恰好**是 `app/adapters/mock_lepao.py` 一个。
   ⚠️ 于是「真的加了一条导出/名册端点」当场红。

⚠️ 外加一条**运行面**的：`test_no_get_route_hands_a_real_birth_to_a_plain_teacher`
—— 以教师身份把 openapi 里**每一个 GET** 都真打一遍，任何 200 的响应体里都不许出现
库里那两个真实出生日期；⚠️ 带三格反空转（扫描面 ≥ 60 条 / 至少 8 条真的 200 /
**出现掩码的路恰好是那 2 条**），否则「一个端点都没打通」与「打通了但一个都没漏」同色。
⚠️ 定点变异 **M10**（给 `StudentHomeRead` 也加一列 `birth`）就是打这一族的：它让
上面第 1 条与「学生窄端点里没有 `birth`」那一条同时红。

---

## ③ 变形住在哪一层（单一所有者在哪、非 CRUD 端点怎么复用、有没有第二份）

### 3.1 裁定：**住在 `app/api/crud.py`，不抽独立模块**（⚠️ 顶回派单 §3 的第 ④ 条）

派单 §3 提示「若非 CRUD 的端点要复用它，住在 `crud.py` 里会造成反向依赖」。
⚠️ **实测那一格在本仓无对象**：承载 `birth` 的响应面**恰好只有 `StudentRead` 一个**
（§2.3 第 14/15 条），而它**只**被 `RESOURCES` 的 `/api/students` 那一行用
⇒ 值级变形的**唯一消费者**就是 `build_crud_router` 里那两个端点分支。
抽一个独立模块会造出「一个模块只有一个调用方、而那个调用方就在隔壁」的形状，
而 `crud.py` 今天已经是「23 个资源的泛型 CRUD 工厂 + 它的五档 `read_scope` 判据」
的住址 —— `masked_columns_for` 与 `_reader_filter` / `_require_row_readable`
是**同一族**东西（一个是行级判据的唯一所有者、一个是值级判据的唯一所有者），
分开住会让「两根轴」这件事在文件结构上看不出对应关系。
⚠️ 已在 spec §15 记为「裁定不做、不占编号」的第 ② 格。

### 3.2 单一所有者逐格（⚠️ 三格都有守卫，不是一句散文）

| 什么 | 唯一所有者 | 守卫 |
|---|---|---|
| 掩码的**字面量** | `app/api/crud.py` 的 `BIRTH_MASK` | `test_the_mask_literal_has_exactly_one_definition_in_the_production_tree`（AST 扫 `backend/app/**`：这个串作为**字符串常量**恰好 1 次、名字带 `MASK` 的模块级全大写赋值恰好 1 个；⚠️ 定点变异 M9 = 抄第二份到 `catalog.py` 模块末尾 → 只有这一条红） |
| 「谁该被掩」的**判据** | `app/api/crud.py` 的 `masked_columns_for` | `test_masked_columns_for_is_the_single_judgement_and_does_not_over_narrow`（四档：admin → `{}` / teacher → 掩 / `role is None` → **同样掩**，即失效方向是**少给** / 空声明**短路**、根本不碰 `request.state`）+ 变异 M4、M5 |
| 「哪个资源的哪一列变形」的**声明** | `catalog.py` 的 `RESOURCES`（今天 **1** 行） | `test_the_declaration_is_unique_and_the_judgement_has_a_single_owner`（23 行里恰好 1 行声明、四格取值全钉；⚠️ 并钉住**全仓只有 `catalog.py` 一个模块 import `BIRTH_MASK`** = 只有一个声明点） |

⚠️ **端点体里一句判据都没有**：list 那一支逐字是
`_redact_rows(body["items"], masked_columns_for(redact, request))`，
read-one 那一支是 `masks = masked_columns_for(redact, request)` +
`return obj if not masks else _redacted_detail(schemas.read, obj, masks)`
⇒ 两处都只**分派**、不判。

### 3.3 有没有第二份掩码逻辑

**没有。** 三面各查一遍：
① AST 扫 `backend/app/**`：`****-**-**` 作为字符串常量 **1** 处（变异 M9 证明这条守卫有牙）；
② 全仓 `Grep '\*\*\*\*-\*\*-\*\*'`：命中的其余各处**全是散文/注释/断言**
（`crud.py` 的 docstring、`catalog.py` 的注释、`test_birth_scope.py` 的期望侧字面量、
spec / README / 说明书 / 本报告），**没有第二处实现**；
③ 前端 `Grep`：`frontend/src/**` 里 **0** 处出现这个串
（⚠️ 前端**不知道**掩码长什么样，故它不可能在前端侧「补一份变形」）。

⚠️ **前端一行都没改**（`git diff d53e4dc HEAD -- frontend` **空**），
故「非 CRUD 端点怎么复用同一格判据」这一问今天**无对象**；
而它将来若有对象，§2.4 那三条结构守卫会先红。

---

## ④ 三档身份的实测取证（真 HTTP + 直接查库对账）

⚠️ 全部在 **8041** 探针实例上做（`PE_DB_URL` → `%TEMP%\p08t5b\pe_probe.db`，
`demo_bootstrap.py` 灌的 60 人库，**cookie 通道** = 生产缺省形状；
`PE_ALLOW_HEADER_IDENTITY` **未设**，故请求头身份在那一个进程上没有任何效力）。
库里的对照值：学生 id 1 = `2025060001` 周晨阳 `birth = 2006-12-07`；
60 个出生日期**各不相同**（`distinct_births = 60`）。

### 4.1 三档各读到什么

| 身份 | `GET /api/students?limit=200` | `GET /api/students/1` |
|---|---|---|
| 匿名 | **401** | **401** |
| 学生本人（id 4 的 cookie） | **403** | **403**（打自己的 id 也是 403） |
| **普通教师 T0001**（cookie） | **200**，`items[].birth` **全是 `****-**-**`**（×50），60 个真实出生日期在响应体里 **0** 命中 | **200**，`birth = "****-**-**"`，`2006-12-07` **0** 命中 |
| **管理员 T0003**（cookie） | **200**，`items[].birth` 是 **50 个各不相同的真实日期** | **200**，`birth = "2006-12-07"` |

⚠️ 请求头通道那一档（`X-Teacher-Staff-No`）由守卫
`test_a_plain_teacher_reads_the_mask_on_the_roster_and_on_the_detail` 钉住，
cookie 通道那一档由 `test_the_mask_holds_on_the_cookie_channel_too` 钉住
（⚠️ 后者**真的**走了一遍「教师绑定口令 204 → 登录 200 → 用那一份 cookie 读两条路」，
一个身份头都不发）⇒ **两档都掩**。

### 4.2 ⚠️⚠️ 「掩码 `PATCH` 回去 → 422 且库里那一行逐字未变」那一拍

派单称它「是『掩码不会被写回库』的唯一证据」。**两段都跑了**，⚠️ 第二段才是它的意义：

| 拍 | 请求 | 结果 |
|---|---|---|
| **红档** | 管理员 `PATCH /api/students/1 {"birth":"****-**-**"}` | **422** `request_validation_failed`（`date_from_datetime_parsing` / `invalid character in year`）；⚠️ 随后**直接查库**取那一行的**全部 9 列**，与请求前那份 dict **逐格相同**（`before == after` → `True`），且 `birth` 仍是 `'2006-12-07'` |
| **绿档对照** | 管理员 `PATCH /api/students/1 {"birth":"2005-01-01"}`（一个**合法**日期） | **200**；⚠️ 库里那一格**静默**变成了 `'2005-01-01'`（`changed != before` → `True`） |
| 还原 | 管理员 `PATCH … {"birth":"2006-12-07"}` | **200**；库里那一行与①前那份**逐格相同** |

⚠️⚠️ **绿档对照是本波最重要的一格实测**：它证明「掩码写回是响亮的」**不是**因为
「这个端点拒绝写入」，而是因为**掩码的字面形状不是一个合法日期**。
⇒ 派单 §3 顶回候选 ③「掩码的字面量形状（`****-**-**` vs 只给年份 vs 置空）」
**有了实测依据**：「只给年份」要落进 `StudentUpdate.birth`（`dt.date | None`）
就只能写成 `2005-01-01` 这种**日期形状**的串，而它 `PATCH` 回去是 **200 = 一次静默的
数据损坏**；「置空」则被工厂第 17 道校验挡在导入期（`""` 在 PATCH 那一侧与
「这一格没传」**同形**，`contract.ts` 的 `fromInputValue` 把空串折成 `undefined`）。
⇒ **`****-**-**` 是三个候选里唯一「写回会响亮」的形状**，本波**不顶回**这一格。

### 4.3 写入侧本来就与教师无关

`require_admin=True` ⇒ 教师 `PATCH {"birth":掩码}` / `PATCH {"grade":9}` / `DELETE` /
`POST` 四种写法**各 403 `forbidden`**（message 逐字点名「身份 'T0001' 不是管理员」），
且库里那一行逐字未变。守卫
`test_a_plain_teacher_cannot_write_the_roster_at_all`。
⇒ 「教师把掩码写回库」这条路**根本不存在**（而管理员那一档由 §4.2 的红档挡着）。

---

## ⑤ 前端影响（**逐页真跑**）+ ⚠️ 顶回：三处半假的散文

### 5.1 怎么真跑的（⚠️ 本会话没有浏览器工具，故用仓库自带的 CDP 姿势）

派单要求「起 dev 模式，用教师身份真跑一遍所有会显示学生身份行的页面」。
⚠️ **本会话的工具面上没有浏览器自动化**（`TRAE-browseruse` 那一份指南要求经
`run_mcp(integrated_code_mode, Exec)` 调用，而本会话**没有** `run_mcp` 这个工具）
⇒ 改用**仓库自己那一条零依赖的路**：`smoke.mjs` 第 14 步用的
「无头 Edge + `--remote-debugging-port=0` + Node 24 自带的全局 `WebSocket`」CDP 客户端，
照它的姿势写了两个探针脚本（`%TEMP%\p08t5b\dom.mjs` / `dom2.mjs`），
用 `Network.setCookie` 种进 `pe_session`、`Page.navigate`、`Runtime.evaluate` 取 DOM。

两档后端都跑过：**8041**（我自己的探针库）与 **dev 档 8000 + vite 5199**
（`demo.ps1 -Port 8000` + `PE_API_TARGET=http://127.0.0.1:8000 npx vite --port 5199 --strictPort`；
⚠️ 5173 那个 vite 是别人的、全程没动）。

### 5.2 逐页结论：`birth` 那一格显示成什么

| 页面 | 身份 | DOM 实测 |
|---|---|---|
| `/t/students/1`（学生详情） | **教师 T0001** | ⚠️ 掩码 ×**1**、真实出生日期 ×**0**；那一行 DOM 正文逐字是 `学号 2025060001 · 法学院 · 年级 1 · 男 · 生于 ****-**-**黄色层`（`StudentDetail.vue:638` 的 `生于 <span class="data">{{ data.me.birth }}</span>`，后面紧贴的是分层 pill） |
| `/t/dashboard` | 教师 T0001 | 掩码 ×0、真实 ×0（读名册只为 `student_id → 姓名` 那张映射） |
| `/t/report`（班级周报） | 教师 T0001 | 掩码 ×0、真实 ×0（同上） |
| `/t/alerts`（预警队列） | 教师 T0001 | 掩码 ×0、真实 ×0（同上） |
| `/admin` | 教师 T0001 | **进不去**：`location` 实测被路由守卫送到 `/t/dashboard` |
| `/admin/students` | 教师 T0001 | 同上（`/t/dashboard`） |
| `/admin/students`（列表） | **管理员 T0003** | 掩码 ×0、真实 ×0 —— ⚠️ **那张表根本没有 `birth` 那一列**：表头逐字是 `id / 学号 student_no / 名称 name / 性别 sex / 年级 grade / 院系 department / 操作`，首行 `1 · 2025060001 · 周晨阳 · male · 1 · 法学院 · 删除` |
| `/admin/students/1` + 点「✎ 编辑」 | 管理员 T0003 | 真实出生日期 ×**1**（`2006-12-07`）；`input[type=date]` 实测两格：`#identity-asof` = `2025-10-12`、**`#edit-birth` = `2006-12-07`** ⇒ ⚠️ 编辑表单预填的是**一个合法日期**，§13.27.4 那条裁定的前提成立 |
| `/s/home` · `/s/notifications` | 学生本人 | 掩码 ×0、真实 ×0（响应体里就没有那一格） |
| `/bind` | 匿名 | `#bind-birth` 是一个**空的** `input[type=date]`（用户自己填，方向相反） |

### 5.3 有没有任何前端代码**解析** `birth`

**没有。** 全仓 `Grep` 三个形状：`new Date(` 里带 `birth` → **0** 命中；
`getFullYear` → **0** 命中；`.birth` 的**取值**用法 → 只有 3 处，逐个读过：
① `views/teacher/StudentDetail.vue:638` 的插值（**只印、不解析**）；
② `api/auth.ts` 的 `bindStudent(studentNo, birth, password)`（**请求体**，客户端 → 服务器）；
③ `views/auth/Bind.vue:163` 的 `/^\d{4}-\d{2}-\d{2}$/.test(birth.value)`
—— ⚠️ 它校验的是**用户自己敲进输入框的那一串**，不是服务器发来的值。
另两处是**类型/标签**：`api/types.ts` 的 `StudentListItem = S['StudentRead']`（类型别名）
与 `present.ts:620` 的列名中文字典 `birth: '出生日期'`（管理台表头用）。
⇒ **掩码不会让任何一处算出 `NaN` 或 1970**，也没有任何一处按 `birth` 排序。

⚠️ 而「体测评分按出生日期算年龄」那一格（计划 §5 点名要实测的）**在服务端**：
`percentile_stage.age_at(student.birth, …)` 与 `intensity.age_from(birth, as_of)`
都从 ORM 行直接读（§2.3 第 16 条）⇒ **前端从来不需要那个原始值**，
「留在服务端算、不把原始值发到前端」这一格今天已经成立。

### 5.4 `dist` 是否逐字未变

**逐字未变。** 收尾实测：**27** 文件 / **707 713 B**、`index.html` **2 567 B** /
sha256[:16] **`141C673FD0BB4B57`**、`index-Ch2KuVNg.js`（251 917 B）、
`index-BuNW43q3.css`（66 664 B）—— 四格与开工时**逐字相同**，
也与派单给的基线**逐字相同**。⚠️ **一次 `npm run build` 都没跑**；
两次起产品档/试用档一律带 `-SkipBuild`（`serve.ps1` 实测印
「`-SkipBuild`：不判新鲜度，直接用现有的 dist（构建戳 10/18/2026 18:01:23）」），
`trial.ps1` 的缺省就是透传 `-SkipBuild`。
⚠️ 而 `frontend/dist/` 在 `.gitignore` 里（不入库），故这一格只能**直接量**、
不能靠 `git diff`；⚠️ `frontend/src/**` 那一侧则由 `git diff d53e4dc HEAD -- frontend`
**空**给出（⇒ 16 条路由 / `routes` 数组 20 / `schema.d.ts` / `check:tokens` /
`check:dist` 的扫描面全部按构造不变）。

### 5.5 ⚠️⚠️ 顶回：**三处甲方看得见的散文/显示会因本件变成半假**，成本对比在此

派单逐字要求「若你实测发现前端非改不可（…或某处把 `****-**-**` 直接印出来很难看），
**先顶回来给成本对比**，⚠️ 不要自己重建 `dist`」。**实测确实撞上了**，三处：

| # | 住址 | 今天写/显示的是什么 | 切换之后为什么不真 |
|---|---|---|---|
| ① | `frontend/src/views/teacher/StudentDetail.vue:638` | `生于 <span class="data">{{ data.me.birth }}</span>` | **教师**从此看见 `生于 ****-**-**`（⚠️ 不是坏、是**难看**；正确的形状是「那一格是掩码就整段不渲染」，与本页既有的 `v-if="strat"` 同一条姿势） |
| ② | `frontend/src/views/auth/Bind.vue:23-27` | 「故这一页的验身材料今天挡的是『校外的人』，而**不挡**『一个已登录的教师/管理员』」 | **普通教师**那一半不再全真（他今天读不到 `birth` 了）；对管理员仍真。⚠️ 而 `/bind` 是**学生自己**会打开的那一页 |
| ③ | `frontend/src/views/admin/ResourceIndex.vue:399-403` | 「而**任何教职**都读得到全校名册（含 `birth`）⇒ 一个已登录的教职可以替任何还没绑定的账号设一个自己知道的口令」 | 同上（⚠️ 那一段是 **Task 4** 写的、当时**全真**） |
| ④ | `backend/app/api/schemas/auth.py` 里两句 docstring（⇒ `/openapi.json` 的 `description`，`/docs` **公开可见**） | 「验身材料（`birth`）**今天仍然读得到**，只是不再匿名」/「一个能登录成教职的人**本来就读得到整份名册（含 `birth`）**」 | 同上 |

**成本对比**（派单要求的那一格）：

| 方案 | 成本 | 风险 |
|---|---|---|
| **改**（①②③④ 一起） | ① 约 1 行（加一个 `v-if`）；②③ 各改一句散文；④ 改两句 docstring → `npm run build`（`dist` 27 文件的哈希**全部**变）+ `npm run gen:api`（`schema.d.ts` 变，⚠️ 入库产物）+ 重钉 openapi 的字节数与 sha（五格不变）+ **三档 smoke 重跑**（⚠️ 第 14 步的 `needles` 里有 `'出生日期（验身材料）'` 与 `'birth'` 两条钉着 `/bind` 页，改 ② 时**不许**把它们改掉）+ 一次由**控制者排**的窗口（重建 + 重启，约 **40–60 秒**；⚠️ 本波没有迁移） | 甲方经历一次半切换态（Plan 08 Task 4 亲历过：`dist` 一落地、8030 立刻换前端而后端还是旧的 ⇒ `/admin` 撞 404 + 一条全局错误横幅） |
| **不改**（本波的选择） | 0 | 切换之后 ① **立刻可见**（教师端学生详情页印一个掩码），②③④ 是散文、在页面上多活一波。⚠️ **功能上无害**：§5.3 已实测前端没有任何一处解析 `birth` |

⚠️ **本波的处置**：**四处都不改**，全部登记进 spec §15（① ② ③ = **G21**、④ = **F11**），
并给出**明确的排法**：与**下一个本来就要重建 `dist`** 的波次一起、在**同一个窗口**里做完
（单独为本件排一次窗口 = 让甲方多经历一次半切换态）。
⚠️ **而它有一个前提必须由控制者确认**（这是本条顶回真正要控制者裁的那一格）：
**本波的重启会把 ①②③ 一起推给甲方**（① 立刻可见）⇒
**要么接受、要么把重启与四处修改排在同一个窗口**。
⚠️ 本波**没有**自己重建 `dist`、**没有**自己排窗口。

⚠️ 另：**说明书**（`Document/2026-10-15-甲方试用说明书.md`）**不在 `dist` 里**
⇒ 改它**不需要**重建产物、也**不需要**窗口，故本波**当场改掉了**三处（见 §7.4）。
⚠️ 这正是「哪些假话必须立刻修、哪些必须等窗口」的分界线：**发给甲方的产物里不许有假话**
（Plan 07 终审判过 S1 的那一族），而说明书是**随包发的文档**、不是构建产物。

---

## ⑥ 守卫与定点变异

### 6.1 守卫：**20 条**（`backend/tests/api/test_birth_scope.py`，本波新增，单文件 2.3–2.4 s）

| 组 | 条数 | 名字 / 它钉的是什么 |
|---|---|---|
| ① 教师那一档 | **2** | `test_a_plain_teacher_reads_the_mask_on_the_roster_and_on_the_detail`（两条路各三格判据：值 == 掩码字面量 / 60 个真实值的 ISO 串一个都不出现在 `response.text` / 掩码串**确实**出现，否则「那一格被整个摘掉」也能假绿）· `test_the_mask_holds_on_the_cookie_channel_too`（⚠️ 生产缺省只认 cookie，故真走一遍「教师绑定 204 → 登录 200 → 用那一份 cookie 读两条路」，一个身份头都不发） |
| ② 管理员那一档（裁定的绿档半边） | **1** | `test_an_admin_reads_the_full_value_on_both_routes`（⚠️ 硬规矩 #50：少了它，「一律掩」与「一律不掩」两个恒常实现各能让半边全绿；并钉住 `REDACT_ADMIN_ONLY == {"admin"}`） |
| ③ 学生那一档（⚠️ **顶回派单守卫 ②**） | **1** | `test_a_student_session_is_rejected_by_the_row_gate_before_any_redaction`（三格：学生打两条路 → **401** 且响应体里既无真实值也无掩码 / 学生自己的 `/api/students/{id}/home` → **200** 且 `birth` **不在** 响应体的键里） |
| ④ 两份响应体只差一格 / 掩码恒定形状 | **2** | `test_the_masked_and_the_full_bodies_differ_in_exactly_one_cell`（⚠️ WIP 的 docstring 已点名；list 与 read-one **两侧都比**、**逐行**比，键序也要相同）· `test_the_mask_is_a_constant_shape_that_leaks_nothing_about_the_value`（⚠️ WIP 的 docstring 已点名；三格 + 一格结构性事实 `Student.__table__.c.birth.nullable is False`） |
| ⑤ 掩码不是合法日期 ⇒ 写回响亮 | **2** | `test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`（**两段**：期望侧字面量 + ⚠️ **服务器实际发出的那一格**；含绿档对照「一个合法日期 PATCH 进去是 200 且真的改了库」，跑完还原）· `test_a_plain_teacher_cannot_write_the_roster_at_all`（四种写法各 403 + 库里逐字未变） |
| ⑥ 单一所有者 | **3** | `test_the_mask_literal_has_exactly_one_definition_in_the_production_tree`（AST）· `test_the_declaration_is_unique_and_the_judgement_has_a_single_owner`（23 行里恰好 1 行 + 四格取值 + **全仓只有 `catalog.py` import `BIRTH_MASK`**）· `test_masked_columns_for_is_the_single_judgement_and_does_not_over_narrow`（四档 + `staff_reader_of_request` 没存过就 `RuntimeError`） |
| ⑦ 没有第二条路 | **4** | `test_every_birth_bearing_resource_row_declares_a_redaction_covering_it` · `test_the_students_roster_is_the_only_response_model_that_carries_a_birth`（144 个模型）· `test_there_is_no_export_or_roster_route_and_the_csv_contract_never_crosses_http` · `test_no_get_route_hands_a_real_birth_to_a_plain_teacher`（**全端点扫描** + 三格反空转） |
| ⑧ 两条审计表都不落 `birth` | **1** | `test_neither_audit_table_records_a_birth_value`（⚠️ 带反空转：先断言读审计**真的记下了** `route == '/api/students'` 那一条，否则「一行都没记」与「记了但没落 birth」同色 —— 而前者恰好是把敏感读整个关掉也能全绿的那一次退化） |
| ⑨ 契约面 | **1** | `test_the_mask_never_reaches_the_contract_and_the_birth_schema_is_untouched`（掩码在整份 openapi 里 **0** 次 + `StudentRead.birth` 逐字仍是 `{"type":"string","format":"date","title":"Birth"}`；⚠️ 五格由 `smoke.mjs` 第 15 步与 `tests/test_main.py` 的 `OPENAPI_CELLS` 钉，本处刻意不抄第二份） |
| ⑩ 工厂导入期校验 | **3** | `test_the_factory_rejects_a_redaction_on_any_other_read_tier`（第 16 道；⚠️ 两档反例 `None` 与 `"student_self"`，后者必须**同时**给 `student_owner`，否则会红在**另一道**校验上、一句判别力都没有）· `test_the_factory_rejects_an_empty_mask_or_an_unknown_role_in_full_for`（第 17 道两支）· `test_the_factory_rejects_a_redaction_column_that_is_not_on_the_model`（第 14 道） |

⚠️ **派单要求的 8 格守卫逐条对账**：① 教师读名册拿不到完整 `birth` → **组 ①**（⚠️ 逐条路都有一拍：list 与 read-one 各一拍，**外加**全端点扫描那一拍覆盖其余 63 个 GET）；
② 学生读自己能拿到完整值 → **顶回**，见 §8.2 第 2 条（改成组 ③ 的**真**口径）；
③ 管理员能拿到完整值 → **组 ②**；④ 导出侧的裁定被钉住 → **组 ⑦ 第 3 条**（⚠️ 裁定是「不存在」，钉的是「将来加进来会红」）；
⑤ 掩码字面量单一所有者 → **组 ⑥ 第 1 条**（AST）；⑥ 掩码不是合法日期 → **组 ⑤**；
⑦ openapi 逐字不变 → **组 ⑨** + 既有守卫（`tests/test_main.py` 的
`test_the_trial_switch_never_touches_the_openapi_document` 与
`test_the_offline_dump_is_byte_identical_to_the_http_endpoint`，⚠️ 本波复核**仍然绿**）；
⑧ 两条审计表里不落 `birth` → **组 ⑧**。

⚠️ **两侧不同源（硬规矩 #109）逐格自查**：期望侧一律是**本文件里的字面量**
（掩码串、`"admin"` / `"teacher"` / `"staff"`、openapi 那三格 schema、两个真实出生日期），
**不从** `BIRTH_MASK` / `ADMIN_ROLE` / `READ_SCOPE_STAFF` **读回来跟自己比**；
被测侧一律**打 HTTP 并解析响应体**（或**直接查库**：`_db_row` 走裸 SQL
`text("SELECT * FROM student WHERE id = :i")`，与响应体是两个独立取法）。
⚠️ 那三个常量**仍然**被 import，但只用在「构造一个**合成**声明」与
「证明被测侧读的就是它们」两件事上（后者是 `test_the_mask_literal_…` 末拍那句
`assert BIRTH_MASK == MASK`，⚠️ 它是**跨源对账**、不是自指：一侧是被测模块的常量、
一侧是本文件的字面量）。

⚠️ **本波**有没有抓到既有守卫里的假绿：**没有发现**（`read_scope` 五档那一族与
`test_bind_token.py` 那一族逐个读过判据，期望侧都是字面量）。
⚠️ 而**本波自己的第一版守卫里有一处缺口，被定点变异抓到了**，见 §6.2 的 M3。

### 6.2 定点变异：**11 格全部变红**（派单要求 ≥ 8 格）

⚠️ 驱动脚本 `%TEMP%\p08t5b\mutate2.py`：每格 ① 二进制读原文并**存起来** →
② 精确替换（**断言命中恰好 1 次**，否则当场报错而不是改错地方）→
③ 跑 `tests/api/test_birth_scope.py` → ④ **逐字节写回原文** →
⑤ `git status --porcelain` 独立复核。
⚠️ **还原不靠 `git checkout`**：写回的是 ① 存下来的那份字节，
于是「还原是否逐字节」与 git 的状态**无关**，⑤ 那一步是**独立**的第二道复核。

| # | 变异 | 结果 | 红在哪几条 |
|---|---|---|---|
| **M1** | `REDACT_ADMIN_ONLY` → `frozenset()`（**过度收窄**：管理员也被掩） | **RED**（4 条） | `…_an_admin_reads_the_full_value_on_both_routes` · `…_masked_and_the_full_bodies_differ_in_exactly_one_cell` · `…_mask_is_a_constant_shape_…` · `…_declaration_is_unique_…` |
| **M2** | `REDACT_ADMIN_ONLY` → `frozenset(STAFF_ROLES)`（**判据反过来**：普通教师也读完整值） | **RED**（8 条） | 教师两条路 ×2（含 cookie 档）· 管理员那条 · 只差一格 · 恒定形状 · 写回响亮 · 声明唯一 · 全端点扫描 |
| **M3** | `BIRTH_MASK` → `"1900-01-01"`（掩码换成一个**合法日期**） | **RED**（8 条） | ⚠️ **含 `…_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`**（补强之后；见下） |
| **M4** | `masked_columns_for` 恒返回 `{}`（谁都不掩） | **RED**（6 条） | 教师两条路 ×2 · 只差一格 · 恒定形状 · `masked_columns_for` 那条 · 全端点扫描 |
| **M5** | `staff_reader_of_request` 的判据放宽：`role = ADMIN_ROLE`（谁都算管理员） | **RED**（6 条） | 与 M4 同一族（⚠️ 这正是派单点名的「把判据放宽到『谁都算 staff』」那一格） |
| **M6** | `catalog.py` 里把名册那条路的 `redact` 声明去掉（→ `()`） | **RED**（7 条） | 教师两条路 ×2 · 只差一格 · 恒定形状 · 声明唯一 · `every_birth_bearing_resource_row_…` · 全端点扫描 |
| **M7** | `_redact_rows` 变成空操作（**list** 那一侧不掩） | **RED**（5 条） | 教师两条路 ×2 · 只差一格 · 恒定形状 · 全端点扫描 |
| **M8** | `_redacted_detail` 变成空操作（**read-one** 那一侧不掩） | **RED**（4 条） | 教师两条路 ×2 · 只差一格 · 全端点扫描 |
| **M9** | 把掩码字面量**抄第二份**到 `catalog.py`（模块末尾加 `SECOND_BIRTH_MASK = "****-**-**"`） | **RED**（**1** 条） | ⚠️ **只有** `…_mask_literal_has_exactly_one_definition_in_the_production_tree` 红 —— 正是它该抓的那一格 |
| **M10** | 给 `StudentHomeRead` 也加一列 `birth: dt.date \| None = None`（**开出第二条路**） | **RED**（2 条） | `…_student_session_is_rejected_by_the_row_gate_…`（学生窄端点里从此有 `birth` 这一格）· `…_students_roster_is_the_only_response_model_that_carries_a_birth` |
| **M11** | 工厂第 16 道校验短路（`if False and redact and …`） | **RED**（**1** 条） | ⚠️ **只有** `…_factory_rejects_a_redaction_on_any_other_read_tier` 红 —— 证明那一道校验**不是**空转 |

**还原复核**：11 格**逐格** `逐字节还原 = True`；每格跑完 `git status --porcelain`
只剩**本波自己那个待提交的文件**（⚠️ 变异 residue **0**）；全部跑完再复绿一次
（`20 passed`）。收尾 `git status --porcelain` **空**。

### 6.3 ⚠️ 变异抓到本波自己守卫的一处缺口（如实记，**已修**）

**M3 首跑时 `test_the_mask_is_not_a_parseable_date_and_writing_it_back_is_loud`
没有红**（红的只有另外 7 条）。根因：那一拍的判据只作用在**本文件的字面量** `MASK` 上，
而 M3 改的是**被测侧**的 `BIRTH_MASK` ⇒ 「服务器发出来的掩码是不是一个合法日期、
能不能被写回库」这件事**当时没有被判**。⚠️ 而那一格恰好是派单变异 ② 逐字要求的
（「把掩码换成一个**合法日期** ⇒ ⑥ 那一拍必须红」）。

**处置**：给那一条**补第二段**，把同样两个判据作用在**服务器实际发出来的那一格**上：
`emitted = 教师 GET 详情 → json()["birth"]`；断言 ① `dt.date.fromisoformat(emitted)`
**抛 `ValueError`**（期望侧 = Python 自己的解析器）② `re.fullmatch(r"\d{4}-\d{2}-\d{2}", emitted)`
是 `None` ③ 把 `emitted` **PATCH 回去 → 422** 且 `_db_row(...) == before`
（期望侧 = 直接查库）。⚠️ **它不是自指**（硬规矩 #109）：断言的不是
「观测值 == 期望字面量」，而是「观测值**具有**那两个性质」。
补强后复跑 M3 → **8 条红、其中包含这一条**（逐字复核脚本 `%TEMP%\p08t5b\verify_m3.py`：
① 补强后 20 passed；② M3 下 `第 ⑥ 拍在红名单里？ True`；③ 还原后复绿 20 passed）。

⚠️ 这是本波**唯一**一处「守卫自己有洞」，而它是**被变异测试抓到的**、
不是被人读出来的 —— 这正是派单要求 ≥ 8 格变异的全部意义。

### 6.4 ⚠️ 变异 M9 首跑的一次**无效取证**（如实记）

M9 第一版把 `SECOND_BIRTH_MASK = "****-**-**"` 插在了 `from app.api.crud import (` 的
**括号里面** ⇒ 一次 `SyntaxError`，pytest **exit=4**（收集错误）而**不是**守卫开火。
⚠️ 那一格虽然「红」了，而它证明不了任何东西（任何语法错误都会让它红）。
**已重做**成「追加到 `catalog.py` 模块末尾」（合法语法），复跑 → **exit=1**、
红的**只有** `…_mask_literal_has_exactly_one_definition_in_the_production_tree` 一条。
⚠️ 教训：**变异必须是一次合法的代码改动**，否则「红」是空的（与硬规矩 #50 同族）。

---

## ⑦ 文档

### 7.1 spec 新节住哪儿：**§13.27**（8 个小节）

⚠️ 选择理由：照 §13.24（留存清理）/ §13.25（备份加固）/ §13.26（绑定令牌）的体例，
本计划的每个 Task 各占 §13.2x 一节，Task 5 顺位就是 **§13.27**；
⚠️ 而它**必须**插在 `## 14. 待确认事项清单` **之前**（§13 是 `## 13. 运行方式` 的子节，
插到 §14 之后会让它脱离 §13）。实测插入点是原第 8 114 行那个 `---` 之前。

| 小节 | 内容 |
|---|---|
| §13.27.1 | **两根轴**的对照表（行级可见性 vs 值级变形；各自收什么、唯一所有者在哪、口径住哪儿）+ 「刻意不合并成一个开关」的理由 + 「变形在服务端做」 |
| §13.27.2 | 三档身份的口径表（⚠️ 逐格实测）+ 「两档通道都掩」+ 「被降级的管理员下一次请求就失去完整值」（⚠️ 并写明它与 §1.2 第 7 条那一格**不同**：那一格是前端路由的判据、本格是数据的判据） |
| §13.27.3 | ⚠️⚠️ **`birth` 离开服务器的全部 16 条路 + 逐条裁定**（= 本报告 §2.3 那张表的 spec 版；含两条顶回与「将来加进来会红」的三条守卫） |
| §13.27.4 | **管理员刻意不掩**的两条理由 + **两格实测取证表**（掩码 PATCH → 422 且库里 9 列逐字未变 / 合法日期 PATCH → 200 且静默改掉）+ 「掩码的字面形状是承重的」+ 「刻意不给月-日」的算术 |
| §13.27.5 | ⚠️⚠️ **一句实话**：这一格收的只是「普通教师」那一档；三格如实记（管理员照旧 / `PE_ALLOW_SELF_BIND` 缺省仍开 ⇒ **要真的关掉抢绑必须显式设 `PE_ALLOW_SELF_BIND=0`** / 教师那一侧一格没收）；⚠️ 与 **§13.26** 交叉指过去、**不抄第二份** |
| §13.27.6 | 前端逐页真跑的结论表 + 「前端没有任何一处解析 `birth`」+ **`dist` 逐字未变** + ⚠️ **三处半假的散文**表 + 成本对比 + 裁定 |
| §13.27.7 | openapi **逐字未变**的五格 + 字节 + sha + `StudentRead.birth` 的 schema 原文；⚠️ **机制**（返回 `JSONResponse` 实例 ⇒ FastAPI 跳过 `serialize_response` ⇒ `response_model` 仍留在 openapi 上）+ 仓内先例；⚠️ 并记「迁移链仍 6 单头 / 残差 diff 仍 0 / 表数仍 30 / `RESOURCES` 仍 23 / 路由数仍 16 / 新增依赖 0」 |
| §13.27.8 | 守卫 20 条的分组 + 变异 11 格 + ⚠️ **变异抓到的那处缺口**（如实记） |

### 7.2 §1.2 第 4 条与 §13.15 第 4 条：**都改了，都只追加**

⚠️ 派单让我判断「口径要不要再改」。判断：**要改，但两处都仍然不划掉**。

* **§1.2 第 4 条**：历史原文**逐字保留**（含 Task 4 那一段追加），在末尾**再追加**一段
  ⚠️⚠️ 块：① 明写「上面那句『`birth` 今天对**全校任何教职**仍然可读』**不再全真**
  （改前它是全真的），而**新的口径**是『对**普通教师**不可读、对**管理员**仍可读』」；
  ② 三格「仍然不撤销」的理由（管理员照旧 / 开关缺省仍开 / **教师那一侧一格没收**）；
  ③ 两格如实记（16 条路的清单住址 + 三处半假散文的处置）。
* **§13.15 交付须知第 4 条**：**两格都追加**。「须知」那一格给了
  ⚠️ **「念给甲方时请照这一句念」** 的新口径（「**普通教师**今天读不到学生的出生日期了；
  **教务干事（管理员）照旧读得到**，因为管理台要能改它；⚠️ 而老路今天仍然开着…」）；
  「本波复核」那一格把 Task 4 写的 ③「关掉开关并不真的收掉本条 —— `birth` 对教职仍然可读
  ⇒ Task 5 才是收掉它的那一半」**按新口径重读**（历史原文保留），并补上本波
  **第三度实测**的六格取证 + 四格如实记（16 条路 / openapi 逐字未变 / `dist` 未重建 /
  三处半假散文）。⚠️ 取证住址那一格补了 **§13.27**。

⚠️ **划不划掉**：与 Task 4 **同一条裁定 —— 都不划**。理由逐字写进了 §15 那段账：
本波收到的是「**普通教师**读不到 `birth`」那一格，而**管理员照旧读到完整值**、
`PE_ALLOW_SELF_BIND` 的**缺省仍是 `1` = 开**、且**教师那一侧**的验身材料
（工号 + 姓名，`teachers` 那一行**没有**声明变形）**一格没收**
⇒ 抢绑今天**没有**变不可能。

### 7.3 §13.4.7：**加了那一句**（派单倾向「要」，本波照办）

在 §13.4.7 的末尾（`#### 13.4.8` 之前）加了一段引用块：**一句话 + 指向 §13.27**，
逐字要点是「本节那五档收的是『哪几**行**对谁可见』，而 Plan 08 Task 5 又立了第二根轴：
『一**行里的哪一格**对谁给完整值』；⚠️ 两根轴**刻意不合并成一个开关**，
也不要把它们读成一根 —— `students` 那一行今天**同时**是 `"staff"`（本节那张五档表
**一个字都没改**、分布仍是 7 / 0 / 13 / 1 / 2）**与**「那 60 行里 `birth` 那一格对普通教师变形」」。
⚠️ **不抄第二份**：清单、裁定、取证一律只在 §13.27。

### 7.4 §15 台账：**43 → 45 条在册 / 7 组、已划掉 14 条**（⚠️ 编号逐个现量核过、没撞号）

**开工先逐组数过一遍实物**（判据逐字照 spec 里写的那一条：`^- ~~?**[A-G]数字 ·`；
⚠️ G 组那 **9** 条划掉的**不用**行首 `~~`，故那一格照 G 组标题上
「十一件在册 + 九件已划掉」那一句核）：

| 组 | 在册 | 号 | 最大号 |
|---|---|---|---|
| A | 3 | A1 A2 A3 | A3 |
| B | 6 | B4–B9 | B9 |
| C | 5 | C1–C5 | C5 |
| D | 7 | D1–D7 | D7 |
| E | 3 | E1 E2 E3 | E3 |
| F | 8 | F1 F2 F4 F5 F6 F8 F9 F10 | F10 |
| G | **11** | G1–G6 / G13 / G16 G17 G19 G20 | G20 |
| **合计** | **43** | | |

⇒ 与账面 **43 / 7 / 14** 三个数**相符**。

**本波划掉 0 条**（理由见 §7.2）、**补 2 条**：

* **F11** —— openapi 里**两处** `description` 因本件变成半假
  （`app/api/schemas/auth.py` 的 `StudentBindCreate` docstring 里那两句），
  而改它们会让 `/openapi.json` 的**字节**变 ⇒ 与「openapi 逐字不变」那条验收口径
  **正面冲突**，故本波**刻意不改**。⚠️ 条内明写它与 **F9** 的差别：
  F9 是「本波**能**改而不改」，F11 是「本波改了就会**撞验收口径**」——
  故 F11 **必须**留到下一波，不是偷懒。⚠️ 并记了连带一格：改它们之后
  `npm run gen:api` 的产物 `schema.d.ts` 也会跟着变（docstring 进注释）。
* **G21** —— 切换之后**四处**甲方看得见的散文/显示变成半假（§5.5 那张表），
  改它们要重建 `dist` ⇒ 与 **F11** 排在**同一波**、在**同一个窗口**里做完四处；
  ⚠️ 条内逐字写了派单要求的**成本对比**（改 vs 不改）与「本波的重启会把 ①②③
  一起推给甲方 ⇒ **要么接受、要么把重启与四处修改排在同一个窗口**」那一句前提；
  ⚠️ 同一条里另记**半格**：教师那一侧的验身材料本波**刻意没收**（三条理由指回 §13.27.5）。

⚠️ **两个号都逐个核过没被占用**：F 组用到 **F10**、G 组用到 **G20**
（⚠️ Task 2 抓到过 Task 1「声称派生 B5/D6/E4 而 **B5 已被占用**、D6/E4 从未真的落进台账」那一格，
故本波**先数实物再派号**，并在收尾**又数了一遍**：F 组 **9** 条在册含 F11、
G 组 **12** 条在册含 G21、合计 **45**，与账面逐字相符）。
⚠️ 另记**三格「裁定不做、不占编号」**（掩码的形状 / 变形住在 `crud.py` /
`teachers` 那一行不声明变形），照 Task 4 那一段的同款姿势。

### 7.5 说明书：**改了**（⚠️ 判定依据 = 它是发给甲方的产物，里面不许有假话）

派单裁定「核了再定」。**核完的结论是必须改**，因为 §6 须知 ② 里有一句
**切换之后就是假话**（而 §5 那句「验身材料 = 学号 + 出生日期」今天**仍然全真**、
不用改：`/bind` 页照旧问出生日期，改的是**谁能从服务器上读到它**）。
改了**三处**，⚠️ **行数一格没涨**（就地改写，不新增行）：

| 处 | 改前 | 改后 |
|---|---|---|
| 路线二第 5 步 | 只说学生详情页有什么 | **加一句**：「⚠️（2026-10-18 起）这一页顶部那一行里『生于』后面显示的是一串星号占位符，**不是坏了**」+ 为什么 + 「用**教务干事**（`T0003`）登录去管理台的学生详情页仍然看得到完整日期」+ ⚠️ **我方已知它印得不好看、已排在下一步** |
| §6 须知 ② 正文 | 「而任何在册教职都读得到全校名册（含出生日期）」 | 「⚠️（2026-10-18 起）**学生那一侧**的出生日期对**普通教师**已经掩掉…⚠️ 而**教务干事（管理员）照旧读得到完整值**（管理台要能改它），且**教师那一侧**的绑定材料（工号 + 姓名）对任何在册教职**仍然全部可读**」 |
| §6 须知 ② 的第 ② 格 | 「关掉开关**并不等于**『出生日期不再泄漏』—— 名册上的出生日期对任何在册教职**仍然可读**，故正式部署还要一并收窄那一格（**我方已排在下一步**）」 | 「关掉开关**并不等于**『抢绑做不到了』—— …今天对**普通教师**已经掩掉（**我方已做完那一步**，不再排在下一步），⚠️ 而**管理员照旧读得到完整值**，且**教师那一侧**…仍然全部可读 ⇒ 今天收掉的是**学生那一侧的一半**」 |

⚠️ 改前那两句是**两句假话**（「仍然可读」+「已排在下一步」）—— 而它正是 Plan 07 终审
判过 **S1** 的那一族（「发给甲方的产物里不许有假话」）。
⚠️ 上限 **200** 行：改后仍是 **179** 行（`crlf` 计数）/ **35 454 B**。
⚠️ **不含内部术语**（波次编号 / 表列名 / 源码行号一个都没写；⚠️ 也**刻意不写死掩码字面量**，
写成「一串星号占位符」——多写一份字面量就是多一个所有者）；
⚠️ **不写死公网主机名**（那条隧道地址一个字符都没出现）；⚠️ **无 `&&`**。

### 7.6 README：**改了**（判断与理由）

派单让我判断。**判断：要改**，理由是 README 里 Task 4 加的那一节
（§「运维：绑定口令的两条路」）有**一句今天半假**：
「① 缺省是『开』⇒ …『一个教职替任何还没绑定的账号抢先绑口令』今天仍然做得到
（**`birth` 对全校任何教职可读**）」。
⚠️ **姿势照 Task 2/3/4**：不新开一节（本波没有新的运维旋钮），而是在**同一节**里
把「五件事如实说」扩成「**六件事**如实说」——新增第 **⑥** 件（名册出生日期对普通教师已掩掉 /
管理员照旧 / **不改契约面**（openapi 的 `StudentRead.birth` 逐字仍是 `format: date`，
改的只是值）/ ⚠️ **它收的只是「学生那一侧的一半」**），并把 ① 那半句改成
「⚠️ 而它的材料面自 2026-10-18 起**窄了一半**，见下面第 ⑥ 件」；
末尾那句指针从「spec §13.26」扩成「**§13.26**（令牌与开关）与 **§13.27**（出生日期那一格）」。
⚠️ 新账面：**14 206 B / 196 行**（改前 13 189 B / 186 行；**+1 017 B / +10 行**）。

### 7.7 `progress.md`：**不续**（照派单；Task 3/4 都没续，那是结案波的活）

---

## ⑧ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 8.1 待清扫（**2** 条，都已进 §15、不重复登记）

1. **§15 F11** —— openapi 里两处 `description` 半假（改它会撞「openapi 逐字不变」）。
2. **§15 G21** —— 切换后四处甲方看得见的散文/显示半假（改它们要重建 `dist`）。

⚠️ 两条**必须排在同一波**（G21 那一波本来就要重建产物 + 重钉 openapi 的字节与 sha）。

### 8.2 ⚠️ 顶回（**5** 处；累计 **245 → 250**）

1. **【顶回·派单第 1 件的第 3、4 条】`GET /api/teacher/roster` 与 `/api/export/...`
   在本仓一个都不存在。** 派单把这两条称为「本件的命门」（「这两条不掩，本件就等于没做」）。
   ⚠️ 实测三面都查过：openapi 的 77 条路径里 **0** 条匹配 `roster|export|csv|download`；
   全仓 `Grep` **0** 命中；`backend/app/api/routers/` 下**只有 8 个模块**
   （`alerts / audit / auth / catalog / dashboard / feedback / pipeline / prescription`），
   **没有** `export.py`、也没有 `teacher.py`。
   ⚠️ 派单说的「导出侧逐资源列白名单（20 个资源声明、11 个不声明、`birth` 在列级被放行）」
   在本仓对应的是**两件别的事**：`list_exclude`（23 行里只有 **3** 行声明，
   排的是三类**凭据**列，`birth` **从来不在**任何一行里）与
   `app/adapters/base.py` 的 `STUDENT_COLUMNS`（**入站**的模拟数据源列序契约，
   **一个字节都不经 HTTP**）。⇒ **名册只有一条 HTTP 路**（`/api/students` 的
   list + read-one），而 WIP 已经把它掩上了 ⇒ **本件不是「等于没做」**。
   ⚠️ 已把这一格落成**三条结构守卫 + 一条运行面守卫**（§2.4），
   于是「将来真的加进来」会当场红，而不是靠人记住这份清单。
2. **【顶回·派单守卫 ②】「学生读自己**能**拿到完整值」今天不成立、也不需要成立。**
   实测：学生会话打 `GET /api/students/{自己的 id}` → **401**（请求头通道）/ **403**（cookie 通道），
   被 `read_scope="staff"` 那道**行级**闸门挡在门外，**根本到不了**值级变形这一步
   （⚠️ 那是 Plan 05A Task 5 / Plan 05B 的既有口径：学生页一律走
   `/api/students/{id}/home` 那类按人收窄的窄端点，而 `StudentHomeRead` **逐字不含 `birth`**）。
   ⇒ 今天**没有任何一条路**把一个学生自己的出生日期发给他自己
   （他绑定口令时手上那一格是**他自己知道的**，不是从服务器读来的）。
   **处置**：守卫改成钉**真**口径（组 ③：学生打两条路 401 且响应体里既无真实值也无掩码 /
   学生自己的窄端点 200 而 `birth` **不在**键里），⚠️ 而不是钉一个恒假的期望。
3. **【顶回·派单变异 ⑦】「把『学生读自己』那一档也掩上」在本仓没有可变异面。**
   承第 2 条：那一档到不了变形，故「多掩它」是一件**什么也不发生**的事、无从变红。
   **处置**：用**同方向的另一根轴**替代 —— 过度收窄 = 把 `admin` 从 `full_for` 里拿掉
   （= **M1**），它让「管理员读到完整值」与「`masked_columns_for` 不过度收窄」两条同时红。
   ⚠️ 判据本身**一格没放宽**（派单逐字要求「过度收窄也是缺陷，必须红」，M1 就是那一格）。
4. **【顶回·派单 §3 第 ④ 条】变形**不**抽成独立模块、就住在 `crud.py`。**
   派单的顾虑是「若非 CRUD 的端点要复用它，住在 `crud.py` 里会造成反向依赖」。
   ⚠️ **实测那一格无对象**（承第 1 条：承载 `birth` 的响应面**恰好只有 `StudentRead`**，
   而它只被 `RESOURCES` 的 `/api/students` 那一行用）⇒ 唯一消费者就是工厂那两个端点分支。
   而 `masked_columns_for` 与 `_reader_filter` / `_require_row_readable` 是**同一族**东西
   （行级判据的唯一所有者 / 值级判据的唯一所有者），分开住会让「两根轴」在文件结构上
   看不出对应关系。⚠️ 已记为 §15「裁定不做、不占编号」的第 ② 格。
5. **【顶回·派单 §5.5 的前提】本波的重启会把三处半假的散文一起推给甲方 ⇒ 需要控制者裁定。**
   ⚠️ 这不是「要不要改前端」的问题（成本对比已给，本波的裁定是**不改**、与 F11 排在同一波），
   而是「**本波的切换窗口该不该现在就排**」：
   **只重启**（本波没有迁移 ⇒ 只需要这一步）会让教师端学生详情页**立刻**印出掩码，
   而 `/bind` 与 `/admin` 那两句散文同时变成半假；
   **要么接受**（功能无害，§5.3 已实测前端不解析 `birth`），
   **要么把「四处修改 + 重建 `dist` + `gen:api` + 重钉 openapi 字节 + 三档 smoke 重跑」
   与重启排在同一个窗口**。⚠️ 本波**没有**自己重建 `dist`、**没有**自己排窗口。

⚠️ 派单 §3 列的另外两个顶回候选，**核过之后不顶回**：
* **①「管理员不掩」这个裁定** —— **成立，不顶回**。两格实测取证都在（§4.2）：
  掩码 `PATCH` 回去 **422** 且库里 9 列逐字未变；而一个**合法**日期 `PATCH` 回去是
  **200** 且**静默**改掉那一格 ⇒ 「写回损坏可以用别的方式挡」这个假设**不成立**
  （挡它的那一层**就是**「掩码不是合法日期」，而日期形状的掩码没有这一层）。
  ⚠️ 主理由也不是「挡得住」，而是**管理员本来就是 omnipotent 的那一档**。
* **③ 掩码的字面量形状** —— **`****-**-**` 是三个候选里唯一「写回会响亮」的形状**，不顶回
  （「只给年份」→ 实测 200 = 静默数据损坏；「置空」→ 被工厂第 17 道校验挡在导入期，
  因为 `""` 与「这一格没传」在 PATCH 那一侧同形）。

### 8.3 没按派单做的（**3** 处，逐个说明）

1. **commit 数是 4 个、但切分与派单建议的不同。** 派单建议
   「① 把 WIP 带绿 + 补完每一条路的变形（含名册与导出）；② 守卫 + 定点变异；③ 文档；④ 报告」。
   ⚠️ 实测 ① 的「补完每一条路的变形」**无对象**（承 §8.2 第 1 条：没有第二条路要补），
   而 WIP 之所以红**恰恰是因为缺守卫** ⇒ 「带绿」与「守卫」是同一件事。
   故实际切分是：**①** 守卫 20 条（把 WIP 带绿）+ 两处指针注释；
   **②** 变异抓出来的那处守卫补强（+ 11 格变异取证写进 commit 信息）；
   **③** 文档（spec / README / 说明书 / 一处注释按实测收窄）；**④** 本报告。
   ⚠️ 四个 commit **各自自洽**（① 之后全量 1773 passed / 0 failed；② 之后同样；
   ③ 是纯文档 + 纯注释，openapi 实测逐字未变）。
2. **前端「逐页真跑」用的是仓库自带的 CDP 姿势，不是浏览器自动化工具。**
   ⚠️ 本会话的工具面上**没有** `run_mcp`（`TRAE-browseruse` 那一份指南的全部浏览器工具
   都要经它调用）⇒ 照 `smoke.mjs` 第 14 步那一段（无头 Edge +
   `--remote-debugging-port=0` + Node 24 自带的全局 `WebSocket`）写了两个探针脚本，
   **真浏览器、真 DOM、真 cookie**。⚠️ 另外**三档 `smoke.mjs` 全跑过**
   （它第 14 步本来就用 CDP 走完 16 条路由），故「真跑」这一格有两份独立证据。
3. **`check:dist` 的「字符数」与派单给的基线对不上（1 433 409 vs 1 422 299），
   本波判定为基线数陈旧、不是回归。** ⚠️ 证据：`check-dist.mjs` 那一格的扫描面是
   `frontend/index.html` + `walk(frontend/src)`（⚠️ **全在 `frontend/` 里**），
   而 `git diff d53e4dc HEAD -- frontend` **空**、工作树**干净**
   ⇒ 这个数在 `d53e4dc` 上**也只能是 1 433 409**，本波**结构上不可能**改动它。
   ⚠️ 如实报差异、不改判据、也不去「修正」基线数（那会是把账本改写成谎言）。

### 8.4 关切（**3** 格，都不占台账编号）

1. ⚠️ **`pe_trial.db` 被服务持有时 `Get-FileHash` 读不出来**（§1.2 第 3 格）。
   本波用 Python 的共享读绕过了。⚠️ 而 `trial.ps1` 的 G12 注释里已经逐字记着这一格
   ⇒ **不是新发现**，只是**又一波踩到**；若将来要有一条「量甲方那份库的 sha」的例行探针，
   它必须走 Python 而不是 `Get-FileHash`。
2. ⚠️ **`masked_columns_for` 的判据只有 `reader.role` 一格**，
   而 `role` 的取值域今天只有 `teacher` / `admin` 两个（`ck_teacher_role` 挡着别的值）。
   ⚠️ 若将来加了第三个 `role`（例如「教务只读」），它会**落进「不在 `full_for` 里」那一档
   = 被掩** ⇒ **失效方向是安全的（少给）**，而**不会**有守卫红。
   ⚠️ 那一格是**设计**（`Redaction.full_for` 的 docstring 逐字写着
   「不在里面的一律变形，故失效方向是少给」），本波**如实记**、不改。
3. ⚠️ **`read_scope="staff"` 那一档今天有 2 行**（`students` / `teachers`），
   而变形只声明在其中 **1** 行。⚠️ 工厂第 16 道校验只保证「声明了 `redact` 的一定是
   `staff` 档」，**不**保证「`staff` 档的都声明了 `redact`」（那会把
   `teachers` 那一行也强行拉进来，而 §13.27.5 第 3 条裁定**不收**它）⇒
   「`teachers` 那一行没有变形」这件事今天**只有散文与台账（G21）记着**，
   ⚠️ **没有守卫钉**。⚠️ 本波**刻意不加**那条守卫：它钉的是一格**刻意的不作为**，
   而派单要求的「④ 导出侧的裁定被钉住（掩或不掩都要有拍）」已由
   `test_there_is_no_export_or_roster_route_…` 与
   `test_the_declaration_is_unique_and_the_judgement_has_a_single_owner`
   （23 行里**恰好 1 行**声明）两条覆盖 ⇒ 「有人给 `teachers` 也加了变形」会红在后者上。

---

## ⑨ 最终验收

### 9.1 后端全量 `pytest`

| 拍 | 基线（`main` = `d53e4dc`） | 本波 | |
|---|---|---|---|
| 全量 `--no-cov` · **接手时**（WIP 原样） | 1753 passed | **1 failed, 1752 passed**, 1 warning in **300.66 s** | ⚠️ **红**（红的那一条逐字见 §1.3：架构守卫「docstring 引用指不到真名」，指的就是本波要写的那两条守卫） |
| 全量 `--no-cov` · **本波改完之后** | — | **1773 passed**, 1 warning in **271.38 s** | ✅ **+20 / 0 failed / 0 skipped / 0 error** |
| 全量带 `--cov --cov-branch`（三个口径各跑一遍） | 1752 + 1 skipped | **1772 passed, 1 skipped**（三个口径**三次都是这个数**） | ✅ **+20 / +1 skipped**（那 1 条 skipped 与本波无关，基线上也是它） |
| `tests/api/test_birth_scope.py` | 不存在 | **20 条**，单文件 **20 passed**（2.3–2.4 s） | ✅ |
| `tests/architecture` + 本文件 | — | **33 passed**（12.89 s） | ✅ 那条「引用指不到真名」的守卫**转绿** |

⚠️ **passed 只增不减**（计划 §8）：1753 → **1773**（**+20**）。

### 9.2 覆盖率三口径**四格**（⚠️ 每格都是本波亲跑，`--cov-branch`）

| 口径 | 基线（Stmts / Miss / Branch / BrPart） | 本波 | Cover | |
|---|---|---|---|---|
| `--cov=app/domain` | 1268 / 0 / 376 / 0 | **1268 / 0 / 376 / 0** | **100%** | ✅ **四格逐字相同**（`app/domain/**` 本波累计 **0 diff**；400.07 s） |
| `--cov=app` | 7615 / 209 / 1836 / 119 | **7 661 / 209 / 1 860 / 121** | 96% | ⚠️ **变了，如实报**（411.58 s）；差值 **+46 / 0 / +24 / +2**，见下 |
| `--cov=scripts --cov=app.static` | 1172 / 217 / 336 / 49 | **1 172 / 217 / 336 / 49** | 80% | ✅ **四格逐字相同**（385.93 s；本波对 `scripts/**` 与 `app/static.py` 的**可执行语句**一格都没改） |

⚠️ **`Cover` 列不是基线**（spec §12 有裁定），本波照旧**只把四格当基线**。

⚠️ **第二口径那 +46 的账**（如实报）：全部来自 **WIP** 给 `app/api/crud.py` 加的那批
**可执行语句**（`Redaction` dataclass、`masked_columns_for`、`_redact_rows`、
`_redacted_detail`、`staff_reader_of_request`、工厂第 14/16/17 道校验的三支、
以及两个端点分支里各一句分派）—— ⚠️ **本波自己给 `app/**` 加的可执行语句是 0**
（本波对 `crud.py` 与 `catalog.py` 的改动**全是注释**，见 §1.4 与 §9.5）。
⚠️ 而 **Miss 一格没涨**（209 → **209**）⇒ **WIP 那批新代码被本波那 20 条守卫全覆盖**；
`BrPart` 涨 **2**（119 → 121）。
本波碰过的那两个模块的**现值**（`--cov=app --cov-branch` 亲跑）：

| 模块 | Stmts / Miss / Branch / BrPart / Cover |
|---|---|
| `app\api\crud.py` | **402 / 17 / 184 / 19 / 94%** |
| `app\api\routers\catalog.py` | **17 / 0 / 2 / 0 / 100%** |

⚠️ 逐模块的**改前**值本波**没有**复跑（那要在 `main` 的 worktree 上再来一轮 7 分钟的
`--cov=app`），故这一格的账**只报到差值与现值**、不做逐模块的对账加法
（硬规矩 #39：没量的不讲成量了）—— ⚠️ 姿势与 Task 4 报告 §9.2 逐字同一条。

### 9.3 表数 / 迁移链 / 残差

| 格 | 基线 | 本波 | |
|---|---|---|---|
| 表数（`Base.metadata`） | 30 | **30** | ✅ |
| `sqlite_master`（**已迁移的磁盘库**上） | 31 | **31**（⚠️ 两份库各**只读**量过一次：`backend/pe_demo.db` 与甲方的 `backend/pe_trial.db` 都是 `sqlite_master` 表数 **31** = **30** 张业务表 + `alembic_version`，且两份的 `version_num` 都是 **`a1af54889103`**；⚠️ 内存库上 `init_db` 之后是 **30**，差的那一张就是 `alembic_version`） | ✅ |
| 迁移链 | 6 **单头** | **6 单头**，`heads == ['a1af54889103']`，顺序逐字 `53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b` → `03331a689ee4` → `a1af54889103` | ✅ |
| 模型 ↔ 迁移**残差 diff** | 0 | **0**（`compare_metadata` 亲跑） | ✅ |
| ⚠️ 本波新增迁移 | — | **0**（值级变形不动 schema） | ✅ |

⚠️ 三次起服务（`demo.ps1` 8000 / `serve.ps1` 8020 / `trial.ps1` 8042）都实测跑了
`upgrade head`，日志逐字是「Running upgrade 03331a689ee4 -> a1af54889103」为最后一条
⇒ **迁移链仍是 6 单头**、没有分叉。
⚠️⚠️ **而甲方那份 `pe_trial.db` 的 `version_num` 实测已经是 `a1af54889103`**（= 链尾）
⇒ **本波的切换窗口确实只需要一次重启、一次迁移都不需要跑**（派单要「如实确认」的那一格，
这就是确认）。⚠️ 量它用的是 `sqlite3.connect("file:…?mode=ro", uri=True)`，
**只读**、没有写它一个字节（收尾复验：字节数与 sha256[:16] 与开工时逐字相同）。

### 9.4 结构账面

| 格 | 基线 | 本波 | |
|---|---|---|---|
| 扫描面（`test_production_layers_never_import_app_seed`） | 74 | **74**（pipeline 10 + db 14 + domain 18 + api 27 + auth 5） | ✅ ⚠️ 本波**没有**新增 `app/**` 模块 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✅ |
| `_MODELS_SUBMODULES` | 8 | **8** | ✅ |
| `_NON_PUBLIC_TABLE_CLASSES` | 16 | **16**（⚠️ 它是 **4** 个模块 × 各自的类名元组，**类数合计 16**） | ✅ |
| 黄金用例 | 14 | **14**（`input` 14 / `expected` 14） | ✅ |
| `RESOURCES` | 23 | **23**（⚠️ 其中声明 `redact` 的恰好 **1** 行） | ✅ |
| router 模块 | 8 | **8** | ✅ |
| 前端路由 | 16（`routes` 数组 20） | **16 / 20**（⚠️ 由 `git diff d53e4dc HEAD -- frontend` **空**给出：`frontend/**` 一个字节都没动） | ✅ |

### 9.5 ⚠️⚠️ openapi：**逐字未变**（计划 §5 的裁定，本波实测复核）

| 格 | 基线 | 本波 | |
|---|---|---|---|
| 路径 / 操作 / 挂 security | 77 / 106 / 87 | **77 / 106 / 87** | ✅ |
| GET（匿名 + 要身份） | 65（15 + 50） | **65（15 + 50）** | ✅ |
| `securitySchemes` | 3 | **3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | ✅ |
| **字节** | 453 555 B | **453 555 B** | ✅ **逐字相同** |
| **sha256[:16]** | `5B4029FB98AC27E9` | **`5B4029FB98AC27E9`** | ✅ **逐字相同** |
| catch-all 路径 | 0 | **0** | ✅ |
| 未定型响应 | 24 | **24**（⚠️ 由 `tests/test_main.py` 的 `OPENAPI_CELLS["untyped_200"]` 字面钉住，那条守卫本波**绿**） | ✅ |
| `expected` / `crud` | 29 / 75 | **29 / 75**（⚠️ 两格都住在 `frontend/**`，而 `git diff d53e4dc HEAD -- frontend` **空** ⇒ 按构造不变；⚠️ 本波没有单独复量它们，如实记） | ✅ |
| `StudentRead.birth` 的 schema | `{"type":"string","format":"date","title":"Birth"}` | **逐字相同**（新守卫 `test_the_mask_never_reaches_the_contract_and_the_birth_schema_is_untouched` 按字面钉住） | ✅ |
| 掩码串在整份 openapi 里出现的次数 | — | **0** | ✅ |

⚠️ **两次量过**：一次在只改完 `crud.py` / `catalog.py` 注释之后（453 555 B /
`5B4029FB98AC27E9`），一次在收尾（同值）⇒ **「掩码不改 schema」这一格是真的**，
机制逐字见 spec §13.27.7（read-one 在要变形那一档返回一个 `JSONResponse` 实例，
FastAPI 的 `isinstance(raw_response, Response)` 那一支跳过 `serialize_response`）。
⚠️ 既有的两条 openapi 守卫
（`test_the_trial_switch_never_touches_the_openapi_document` 与
`test_the_offline_dump_is_byte_identical_to_the_http_endpoint`）本波**仍然绿**。

### 9.6 前端账面

| 格 | 基线 | 本波 | |
|---|---|---|---|
| `frontend/dist` | 27 文件 / 707 713 B | **27 文件 / 707 713 B** | ✅ **逐字未变**（一次 `npm run build` 都没跑） |
| `dist/index.html` | 2 567 B / `141C673FD0BB4B57` | **2 567 B / `141C673FD0BB4B57`** | ✅ |
| 主 chunk / 主 css | `index-Ch2KuVNg.js` / `index-BuNW43q3.css` | **同两个名字**（251 917 B / 66 664 B） | ✅ |
| `check:tokens` | 36（下界 25） | **36 个文件 / 下界 25 / 全绿 / 退出码 0** | ✅ |
| `check:dist` | 绿（56 文件 / 1 422 299 字符） | **绿 / 退出码 0**；产物侧 **23** 文件 / **609 607 B** + woff2 恰好 **4** 个（97 348 B）；源码侧 **56** 文件 / **1 433 409** 字符 | ✅ 绿；⚠️ 源码侧那个**字符数与派单给的基线不同**（1 433 409 vs 1 422 299），本波判定为**基线数陈旧、不是回归**，逐字证据见 §8.3 第 3 条 |
| **新增依赖** | 后端 0 / 前端 0 | **后端 0 / 前端 0**（⚠️ 七份 manifest 零 diff，见 §9.9） | ✅ |
| 依赖清单守卫 | 绿 | **绿**（`serve.ps1` ① 实测印「依赖 **7** 项运行时依赖都装着（清单**现场读自** `backend\pyproject.toml`）」；⚠️ 全量 pytest 0 红 ⇒ **一字不红**） | ✅ |

### 9.7 `smoke.mjs` 三档（⚠️ **公网档按派单没跑**）

| 档 | 怎么起的 | 步数 | 断言 | 退出码 | 基线 |
|---|---|---|---|---|---|
| **dev 档** | `backend\scripts\demo.ps1 -Port 8000`（灌一份**全新**的 `pe_demo.db`）+ `PE_API_TARGET=http://127.0.0.1:8000 npx vite --port 5199 --strictPort`；跑法 `PE_API_BASE=http://127.0.0.1:8000 PE_WEB_BASE=http://localhost:5199 npm run smoke` | **18/18 全绿** | **816 绿 / 0 红** | **0** | 816 ✅ **逐字相同** |
| **产品档** | 重灌一份干净的 `pe_demo.db` + `scripts\serve.ps1 -Port 8020 -SkipBuild`（⚠️ 同一个 uvicorn 同源发 `dist`）；`PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8020` | **18/18 全绿** | **816 绿 / 0 红** | **0** | 816 ✅ |
| **试用档** | `$env:PE_DB_URL` 指到 `%TEMP%\p08t5b\pe_trial_probe.db` + `scripts\trial.ps1 -Port 8042`（它自己灌库、自己设 `PE_TRIAL=1`、缺省透传 `-SkipBuild`）；`PE_TRIAL=1 PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8042` | **18/18 全绿** | **848 绿 / 0 红** | **0** | 848 ✅ |
| **公网档** | — | — | — | — | ⚠️ **按派单没跑**（基线 778 是 Plan 07 Task 8 时点的值） |

⚠️ **三档各用一份刚灌出来的库**（`smoke.mjs` 会写脏库，而它第 0 步就是
「你是不是忘了复原」的守卫）。⚠️ 试用档**没有**碰 `backend\pe_trial.db`、
**没有**用 8030、**没有** `-Reset`：`PE_DB_URL` 指到 `%TEMP%` 下我自己灌的那一份，
`trial.ps1` 的第 ① 步实测印「试用库的 URL 不指向禁区 ✓」。
⚠️ 三档都实测印出 `dist` 的构建戳 **10/18/2026 18:01:23**（= 开工时那一个）
⇒ **一次都没重建产物**。
⚠️ **断言数一格没涨也没跌**：本波**没有**给 `smoke.mjs` 加拍（⚠️ 那是刻意的 ——
本波的后端守卫已经把三档身份钉得更细，而 `smoke.mjs` 里**没有任何一拍**依赖
`birth` 的值：`studentNoOf()` 只取 `s.id` 与 `s.student_no`，第 16 步 ⑭ 那组
绑定限流用的是一个**不在册的假学号** `SMOKE10BIND` + 一个写死的出生日期）。

### 9.8 数据面 / 禁区

| 格 | 结果 | |
|---|---|---|
| 四个数据指纹 | `D2C8E539E2FA0029`（评分表）/ `5394B37F01DAC9AC`（动作库）/ `822CB86A5E998301`（等价表）/ `E48E3AC82BB45BB7`（预警规则）—— 四份守卫**逐个亲跑绿**（`tests/test_refdata.py` + `test_refdata_prescription.py` + `test_refdata_alerts.py` + `tests/domain/test_prescription_templates.py` 合计 **149 passed / 3.75 s**） | ✅ |
| 18 个模板指纹 | `TEMPLATE_FINGERPRINTS` 实测**恰好 18 条**，同一批 149 passed 里 | ✅ |
| `git diff d53e4dc HEAD -- backend/data` | **空** | ✅ |
| `backend/pe.db` | **不存在**（`Test-Path` → `False`；⚠️ `dump_openapi.py` 每次跑还各自前后查一次） | ✅ |
| `backend/data/seed/` | **0 文件** | ✅ |
| `backend/data/**` | **一个字节都没动**（上一行那条 diff 空即证） | ✅ |
| 禁跑的三个 CLI | `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` **一次都没跑**（灌库一律走 `demo_bootstrap.py`） | ✅ |
| `backend/backups/` 里控制者那两份 | **没删也没入库**（`backend/backups/` 在 `.gitignore` 里，实测 0 个入库文件） | ✅ |

### 9.9 gitignore / manifest

| 格 | 结果 | |
|---|---|---|
| 八处 gitignore 项 | ⚠️ 本波**逐条量了全部 29 条非注释模式**（比「八处」更宽）：`git ls-files -- <模式>` **每条都是 0 个入库文件**，合计 **0**。逐个核过实体的六处：`backend/pe.db`（磁盘 **False**）、`backend/pe_demo.db`（磁盘 True / 入库 **False**）、`backend/pe_trial.db`（磁盘 True / 入库 **False**）、`backend/backups/`（True / **False**）、`frontend/dist-pack/`（**False** / False）、`.trial/`（True / **False**） | ✅ |
| 七份 manifest + `.gitattributes` + `.gitignore` + `backend/alembic.ini` | `git diff --stat d53e4dc HEAD -- backend/pyproject.toml frontend/package.json frontend/package-lock.json .gitattributes .gitignore backend/alembic.ini` → **空**（零 diff） | ✅ |
| 本波全部改动 | `git diff --stat d53e4dc HEAD` = **6 个文件 / +1 601 / −18**（`crud.py` +355 · `catalog.py` +30 · `test_birth_scope.py` +881 新建 · spec +327 · 说明书 ±6 · README ±20） | ✅ |

### 9.10 ⚠️ 收尾五格（**逐格重量**，与开工对账）

| # | 格 | 开工 | 收尾 | |
|---|---|---|---|---|
| 1 | uvicorn PID **59760**（甲方那条 8030） | 在（`StartTime 19:48:50`） | **仍在** | ✅ 全程没杀、没重启 |
| 2 | `cloudflared` PID **59472** | 在（`StartTime 19:51:18`） | **仍在** | ✅ |
| 3 | `backend/pe_trial.db` | 1 609 728 B / `EC7EE58450A42B51` | **1 609 728 B / `EC7EE58450A42B51`** | ✅ **逐字未变**（没 `-Reset`、没写它、没对它跑迁移） |
| 4 | `frontend/dist` | 27 / 707 713 B / `index.html` 2 567 B / `141C673FD0BB4B57` | **27 / 707 713 B / 2 567 B / `141C673FD0BB4B57`** | ✅ **逐字未变** |
| 5 | 8030 匿名 health | 200 `tables:30 students:60 trial:true` | **200 `{"status":"ok","tables":30,"students":60,"trial":true}`** | ✅ |
| 5′ | ⚠️ **甲方那条公网 URL** | （派单给的活链接） | `https://translate-most-explanation-months.trycloudflare.com/api/health` → **200 `{"status":"ok","tables":30,"students":60,"trial":true}`** | ✅ **仍 200 且 `tables:30`**（⚠️ 全程只对它发过**这一个匿名 GET**，没有登录、没有写入） |

### 9.11 我自己起的进程（**收尾全部已停**）

| 进程 | 端口 | 处置 |
|---|---|---|
| uvicorn（我的探针实例，`PE_DB_URL` → `%TEMP%\p08t5b\pe_probe.db`） | 8041 | **已停** |
| `demo.ps1` 起的 uvicorn | 8000 | **已停** |
| `serve.ps1 -Port 8020 -SkipBuild` 起的 uvicorn | 8020 | **已停** |
| `trial.ps1 -Port 8042` 起的 uvicorn（库在 `%TEMP%`） | 8042 | **已停** |
| `npx vite --port 5199 --strictPort`（两次：先指 8041、后指 8000） | 5199 | **已停** |
| 无头 Edge（CDP 探针，`--user-data-dir` 在 `%TEMP%\p08t5b-cdp*`） | 随机 | **已 kill**，profile 目录已删 |

⚠️ **不是我们的一律没动**：5173 的 vite（PID **43520**）与其父 `npm run dev`（**38900**）、
两个 `@deepseek-ai/dsh web`（**14368 / 16404**）、甲方的 **59760 / 59472**、
以及 wrapper **55912** —— 收尾逐个复核仍在世。
⚠️ 也**没有删** `p07ctl` / `pe_trial_csv_41684`（8030 那个服务正在用的 `PE_CSV_DIR`）/
`pe_tunnel_8030`。

### 9.12 探针目录

`%TEMP%\p08t5b\` —— **已删并复验**（`Test-Path` → `False`）。
⚠️ 里面先后放过：`pe_probe.db`（8041 的库）、`pe_trial_probe.db`（8042 的库）、
`lepao\`（CSV）、7 个探针脚本（`oa.py` / `scan.py` / `scan2.py` / `scan3.py` /
`probe4.py` / `ledger.py` / `ledger2.py` / `ignore.py` / `eol.py` / `mutate.py` /
`mutate2.py` / `mutate9.py` / `verify_m3.py` / `tocrlf.py`）、两个 CDP 脚本
（`dom.mjs` / `dom2.mjs`）、以及各份日志（`pytest_wip.txt` / `pytest_after.txt` /
`cov.txt` / `cov2.txt` / `smoke_dev.txt` / `smoke_prod.txt` / `smoke_trial.txt` /
`scan*_out.txt` / `dom*_out.txt` / `mutate*_out.txt` / `demo8000.log` /
`serve8020.log` / `trial8042.log` / `uvicorn8041.log` / `vite5199*.log`）。
⚠️ 另外 `%TEMP%\p08t5b-cdp-*` 两个浏览器 profile 目录也已删。
⚠️ **仓库里一个探针文件都没留**（`git status --porcelain` 收尾为空）。

### 9.13 文档账面（⚠️ 两个口径都报；**双向可逆**见 §10）

| 文件 | 工作树 | 入库 blob |
|---|---|---|
| **spec**（`Document/2026-09-28-体育闭环原型-设计spec.md`） | **991 126 B / 9 580 行 / 全 CRLF / 0 裸 LF / 无 BOM / sha256[:16] `EABFB19E0E935D73`** | **981 546 B / `6E608DBE5D4B15BB`** |
| **README** | **14 206 B / 196 行 / 0 裸 LF / 无 BOM** | **14 010 B** |
| **甲方试用说明书** | **35 454 B / 179 行 / 0 裸 LF / 无 BOM**（⚠️ 上限 **200**，行数一格没涨） | **35 275 B** |

⚠️ spec 的基线是 **955 443 B / 9 265 行 / `CBCA4037B118BF81`**（blob **946 178 B /
`E63C85C4437FBF30`**）⇒ 本波 **+35 683 B / +315 行**（§13.27 新节 213 行 +
§1.2 第 4 条追加 + §13.15 第 4 条两格追加 + §13.4.7 一段 + §15 那段账与 F11/G21 两条）。
⚠️ README 基线 **13 189 B / 186 行** ⇒ **+1 017 B / +10 行**。
⚠️ 两个口径的差值**恰好等于 CRLF 行数**（spec 991 126 − 981 546 = 9 580 = 行数；
README 14 206 − 14 010 = 196；说明书 35 454 − 35 275 = 179）⇒ 按设计**不成立**
「工作树字节 == blob 字节」，⚠️ 正确判据是**双向逐字节可逆**（§10）。

### 9.14 commit（**4** 个；⚠️ 一次都没 push、一次都没碰 `main`、没有 revert / cherry-pick 那个 WIP）

| # | sha | 一句话 | 自洽吗 |
|---|---|---|---|
| — | `48e3b9b` | （接手的 WIP 检查点，控制者打的） | ⚠️ **不自洽**：全量 pytest **1 failed** |
| ① | **`d138609`** | `test: Plan 08 Task 5 守卫 20 条 —— 把 WIP 检查点 48e3b9b 带绿` | ✅ **把 WIP 带绿了**：全量 **1773 passed / 0 failed**；⚠️ 派单逐字要求「你的第一个正式 commit 要把它带绿」——**做到了** |
| ② | **`f895555`** | `test: Plan 08 Task 5 定点变异 11 格 + 一处由变异抓出来的守卫补强` | ✅ 全量仍 **1773 passed**（本 commit 只加了 20 行断言与 docstring） |
| ③ | **`52704af`** | `docs: Plan 08 Task 5 —— spec §13.27 新节 + §1.2/§13.15 第 4 条 + §13.4.7 + §15（F11/G21）+ README + 甲方说明书` | ✅ 纯文档 + 纯注释；⚠️ openapi 实测**逐字未变**（453 555 B / `5B4029FB98AC27E9`） |
| ④ | （本报告那一个） | `docs(sdd): Plan 08 Task 5 实现者报告` | ✅ 只加 `.superpowers/**` 一个文件 |

⚠️ `main` = **`d53e4dc`**，⚠️ 本分支比它多 **4** 个 commit（含那个 WIP 共 **5** 个）；
⚠️ 加上接手时已有的 6 个待推 commit，⚠️ **本波一个都没 push**（派单：控制者负责重试）。

---

## ⑩ 行尾复核（逐个被改文件，**双向可逆**判据）

⚠️ 判据（派单逐字给的）：对 `Document/**` 与 README，「工作树字节 == blob 字节」
**按设计不成立**（差值恰好 = CRLF 行数），故正确判据是**双向逐字节可逆**：
**正向** `git hash-object <file>` == `git ls-files -s` 里那个 index blob；
**反向** `git cat-file blob <index blob>` 按该文件的 `.gitattributes` 口径折算回来
== **工作树字节**。⚠️ 全程用 **Python 二进制模式**编辑（`%TEMP%\p08t5b\tocrlf.py`：
先 `CRLF→LF` 再 `LF→CRLF`，⚠️ 一次到位、不产生混合行尾），
**每改完一个文件当场核** `git ls-files --eol`。

| 文件 | `text` / `eol` 属性 | `git ls-files --eol` | 正向 | 反向 | 工作树 B | blob B | 裸 LF | BOM |
|---|---|---|---|---|---|---|---|---|
| `backend/app/api/crud.py` | unspecified | `i/lf  w/crlf` | ✅ | ✅ | 184 040 | 181 335 | **0** | 无 |
| `backend/app/api/routers/catalog.py` | unspecified | `i/lf  w/crlf` | ✅ | ✅ | 69 078 | 68 071 | **0** | 无 |
| `backend/tests/api/test_birth_scope.py` | unspecified | `i/lf  w/crlf` | ✅ | ✅ | 51 862 | 50 981 | **0** | 无 |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | `text` / `crlf` | `i/lf  w/crlf` | ✅ | ✅ | 991 126 | 981 546 | **0** | 无 |
| `Document/2026-10-15-甲方试用说明书.md` | `text` / `crlf` | `i/lf  w/crlf` | ✅ | ✅ | 35 454 | 35 275 | **0** | 无 |
| `README.md` | unspecified | `i/lf  w/crlf` | ✅ | ✅ | 14 206 | 14 010 | **0** | 无 |
| 本报告（`.superpowers/sdd/…/task-5-report.md`） | **`-text`**（零转换） | 应为 `i/lf  w/lf` | ⚠️ 见下 | ⚠️ 见下 | ⚠️ **刻意不印** | ⚠️ **刻意不印** | **0**（纯 LF） | 无 |

⚠️ **本报告自己那一行**：`.gitattributes` 第 50 行逐字是 `.superpowers/**  -text`
⇒ **双向零转换**，故它的**工作树字节 == blob 字节**（与前六行相反）。
⚠️ 而它的字节数与 sha256 **刻意不印在本文件里**（不动点问题；Plan 07 Task 8
在这一族连踩四次，教训在它报告的 §8.6）—— 那一格由**交回控制者的那段话**报出，
并在 commit 之后用同一个脚本（`%TEMP%\p08t5b\eol.py`）复验「正向 ✅ / 反向 ✅（逐字）」。
⚠️ 写入时**没有**对它跑 `tocrlf.py`（跑了就毁掉 `-text` 那一档的口径）；
提交前实测它是**纯 LF**（`crlf` 计数 **0**）、**无 BOM**，
且 `git check-attr text eol` 逐字回 `text: unset` / `eol: unspecified`
（⚠️ 它的**行数**与字节数刻意不印：那一格会随本文件自己的编辑而漂，
印上去就是一次不动点事故 —— 与上面「不印自己的 sha」同一条理由）。

⚠️ **前六行的差值都恰好等于 CRLF 行数**（184 040 − 181 335 = 2 705 = `crlf` 计数；
69 078 − 68 071 = 1 007；51 862 − 50 981 = 881；991 126 − 981 546 = 9 580；
35 454 − 35 275 = 179；14 206 − 14 010 = 196）⇒ 六个文件都是**纯 CRLF、0 裸 LF**，
⚠️ **没有一处混合行尾**（本计划此前四次行尾事故的那一族，本波一次都没犯）。

