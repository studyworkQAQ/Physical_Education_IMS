"""Plan 03 Task 5 预检更正（P5-A1..A6）+ 账本 Ruling 13。逐条 assert 命中次数。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
LEDGER = HERE / "progress.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    b0 = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `fcbb00e`，取证脚本 `t5_probes/_preflight.py` 与 `_preflight2.py`）

**测试基线**：`910 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**；扫描面 **50**；**51 个端点在线**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P5-A1** | **Critical** | **`class_session.batch_id` 与 `training_log.batch_id` 都是 `NOT NULL` 的外键指向 `daily_sync_run.id`**，而本 Task 要让**教师实时建课次、学生实时打卡** —— **这两种行都没有批次可指**，照今天的 schema 写进去会当场 `NOT NULL constraint failed`。⚠️ **更麻烦的是 `repo.delete_by_batch` 的 docstring 逐字写着「`TrainingLog` 由 Task 5 接（进 `_replay_cleanup`）」** —— 即 Task 2 是按「`training_log` 是批处理产物」设计的，而 spec §8.1 说它**同时**是学生每天打卡的落点。**这张表有两个来源，而 `batch_id NOT NULL` 只容得下一个。** | **两列都改成 `nullable=True`**：**适配器/批处理写的行带 `batch_id`**（`_replay_cleanup` 按批删它们）、**用户实时写的行留 `NULL`**（`delete_by_batch` 是 `WHERE batch_id = :b`，**NULL 不等于任何值 → 实时行天然躲过重放**，这正是我们要的）。⚠️ **`_BATCH_OWNED_TABLES` 那条守卫不受影响**（它断言的是「**有 `batch_id` 列**的表恰好是那九张」，可空性不改变列的存在）。⚠️ 但 **`repo.delete_by_batch` 的 docstring 要同步**（硬规矩 #66）：写明九张里有两张的这一列现在是可空的、以及为什么 |
| **P5-A2** | **Critical** | **`TrainingPackage` 没有 `weekly_frequency` 字段** —— 实测字段只有 `template_id` / `template_version` / `weeks` / `assembly_snapshot` / `paused`。而本 Task 的「完成率只按处方训练日计算」（spec §8.1 的折中方案）把分母定成「= `Template.weekly_frequency`」—— **从处方行里读不到它**。 | **分母改成 `len(sheet.sessions)`**（`WeeklySheet.sessions` 实测存在）。**⚠️ 这个改法不只是「能读到」，它比原方案更对**：`Template.weekly_frequency` 是模板的静态值，而 **教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`weekly_training_sheet` 产出的 `sessions` 已经反映了覆盖后的天数** —— 用 `len(sheet.sessions)` 当分母，**教师改了周天数，完成率的分母会跟着变**，而读模板值不会。**无处方或 `current_week` 返回 `None` → 完成率返回 `null` 而不是 `0`**（「不知道」不得讲成「0%」） |
| **P5-A3** | **Important** | **`training_log.source` 是 `VARCHAR(16) NOT NULL`，但 `TrainingLog` 没有 `SOURCES` 类常量、也没有对应的 CHECK 约束**（实测该表只有 `ck_training_log_feeling` 一条 CHECK）。而 P5-A1 说明这张表**有两个来源**（适配器 / 学生打卡）—— **值域没有单一所有者**。 | **加类常量 `TrainingLog.SOURCES`**（至少 `{"checkin", "lepao"}` 两个值；**学生打卡的端点写 `"checkin"`**），并按 `feeling` 的既有做法**用 `_in_domain` 加一条 CHECK**。⚠️ **加 CHECK 是 schema 变更**，故 `test_models.py` 里「`_in_domain` 列数」那条断言会红（实测 Task 2 之后是 **23**）→ **按硬规矩 #88 先跑全量、把红掉的相等断言逐个收进来** |
| **P5-A4** | **Important** | **`app/config.py` 今天没有 `TIMEZONE`**（实测只有 `BACKEND_DIR` / `DEFAULT_CSV_DIR` / `DEFAULT_DB_URL` 三个常量）。**`zoneinfo` 可用** ✅（实测 `ZoneInfo("Asia/Shanghai")` 与 `datetime.now(z)` 都正常，无 tzdata 缺失问题）。 | 本 Task **新增 `app/config.py` 的 `TIMEZONE = "Asia/Shanghai"`**（计划正文已写了这条决定，只是没核实它今天不存在）。⚠️ **`DEFAULT_DB_URL` 实测逐字是 `sqlite:///…/backend/pe.db`** —— **禁区**，本 Task 若要手工起服务必须显式设 `PE_DB_URL` |
| **P5-A5** | **Important** | **`deps.Page` 实测是一个函数，不是 Pydantic 模型**：`def Page(*, limit: Annotated[int, Ge(ge=1), Le(le=200)] = 50, offset: Annotated[int, Ge(ge=0)] = 0) -> None`（即 FastAPI 的依赖函数 + `Annotated` 约束）。**计划正文（Task 1 的 Interfaces）写的是 `Page(BaseModel)`** —— 那句是错的（Task 1 的实现者选了依赖函数，因为查询参数用 `Annotated` 比 Pydantic 模型更自然）。 | **本 Task 照实测的形状用**：`page: Page = Depends()`。**⚠️ 不要去改 `Page`**（Task 3 的 23 个资源都在用它，改形状会连带 47 个端点）。**并把 Task 1 的 Interfaces 那句更正掉**（它是本计划里的一处事实错误，见下方更正） |
| P5-A6 | Minor | `ClassSession` **没有任何类常量**（实测 `[]`），而 `rpe_token` 是 `VARCHAR(16)`、本 Task 要用 `secrets.token_urlsafe(12)[:16]` 生成它 —— **`16` 会成为两个没有出处的魔数**（一个在列类型里、一个在生成代码里）。 | **加类常量 `ClassSession.RPE_TOKEN_LEN = 16`**，列类型与生成代码都引它。**⚠️ 架构守卫不拦 `secrets`**：实测 `_is_api_allowed` 是**只针对 `app.*` 前缀**的 allow-list（`FORBIDDEN_PREFIX = "app.seed"`），**标准库不受它约束** —— 且 Task 1 已把 `app.refdata_alerts`（Task 6 才建）与 `app.adapters`（Task 9 才用）**预先列进 allow-list**，docstring 逐字写明了理由，故**本 Task 不需要动守卫** |

**⚠️ 顺带核实到的两件好事**（不用改，但值得记）：
1. **Task 1 的守卫 allow-list 已经预留给 Task 6 与 Task 9**：实测 `_API_ALLOWED_PREFIXES` 里有 `app.refdata_alerts`（**今天还不存在**，Task 6 才建）与 `app.adapters`（Task 9 的 `POST /api/pipeline/run-daily` 要它，因为 `daily.run_daily` 的第四个参数是适配器实例、而 `build_adapter` 住在 `app.adapters.factory`）。docstring 逐字写着「allow-list 里列一个尚不存在的模块是安全的（它是许可、不是断言），而列在这里正是为了兑现『后面 8 个 Task 不再动本文件』」。**S6 那条裁定被完整兑现了。**
2. **`repo.delete_by_batch` 的 docstring 已经把 Task 5/8 的活写清楚了**：「`Alert` 与 `WeeklyClassReport` 由 Task 8 接进清单，`TrainingLog` 由 Task 5 接，而 **`ClassSession` 不得接**——`rpe_record.class_session_id` 是 NOT NULL 的外键指向它，按批删课次会当场 FK 违例（改成 `CASCADE` 更糟：会连带删掉学生刚交的快评），它的幂等手段是 `upsert` 按 `(course_section_id, session_date, period)` 更新」。**本 Task 照它办。**

"""

patch(PLAN, [
    ("## Task 5: §8.1 三源采集的特例端点\n\n**Files:**",
     "## Task 5: §8.1 三源采集的特例端点\n" + PRE + "\n**Files:**",
     1, "P5 插入预检更正总表"),

    # P5-A1/A3：Files 行加上 schema 变更与 config
    ("**Files:** Create `backend/app/api/routers/feedback.py`、`backend/app/api/schemas/feedback.py`（补特例模型）、"
     "`backend/tests/api/test_feedback.py`",
     "**Files:** Create `backend/app/api/routers/feedback.py`、`backend/tests/api/test_feedback.py`；"
     "Modify **`backend/app/api/schemas/feedback.py`（⚠️ 它由 Task 3 创建，本 Task 只补特例模型，不要覆盖）**、"
     "**`backend/app/db/models/feedback.py`（P5-A1：`class_session.batch_id` 与 `training_log.batch_id` 改成可空；"
     "P5-A3：加 `TrainingLog.SOURCES` 类常量 + 一条 `_in_domain` CHECK；P5-A6：加 `ClassSession.RPE_TOKEN_LEN = 16`）**、"
     "**`backend/app/config.py`（P5-A4：新增 `TIMEZONE = \"Asia/Shanghai\"`）**、"
     "**`backend/app/db/repo.py`（P5-A1 的连带：`delete_by_batch` 的 docstring 要写明九张里有两张的这一列现在可空）**、"
     "`backend/tests/db/test_models.py`（**P5-A3 加 CHECK 会让「`_in_domain` 列数 = 23」那条断言红**）、"
     "`backend/app/api/routers/__init__.py`（include 新 router，**不是 `main.py`**）、"
     "**`backend/tests/pipeline/test_backfill.py`（⚠️ Ruling 12：把 `assert elapsed < 60` 放宽到 90 并如实改写 docstring）**",
     1, "P5-A1/A3/A4 Files 行 + Ruling 12"),

    # P5-A2：完成率的分母
    ("- **完成率的分母（spec §8.1 的折中方案）**：「每日都可打卡，非训练日一键『今日休息』；但**完成率只按处方训练日计算**」。"
     "→ 分母 = 该生**当前处方**在该周的训练日数（= `Template.weekly_frequency`，Plan 02 实测红 4 / 黄 3 / 绿 2），"
     "分子 = 那些日子里 `completed=True 且 late=False 且 is_rest_day=False` 的行数。"
     "**无处方 → 完成率返回 `null` 而不是 `0`**（「不知道」不得讲成「0%」，Plan 01 Ruling 134 的同一条纪律）。",
     "- **⚠️ P5-A2 更正：完成率的分母 = `len(sheet.sessions)`，不是 `Template.weekly_frequency`。** "
     "原文写「分母 = 该生当前处方在该周的训练日数（= `Template.weekly_frequency`，Plan 02 实测红 4 / 黄 3 / 绿 2）」—— "
     "**而 `TrainingPackage` 实测没有 `weekly_frequency` 字段**（只有 `template_id` / `template_version` / `weeks` / "
     "`assembly_snapshot` / `paused`），**从处方行里读不到它**。\n"
     "  **改成 `len(sheet.sessions)`（`WeeklySheet.sessions`）不只是「能读到」，它比原方案更对**："
     "`Template.weekly_frequency` 是模板的静态值，而**教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，"
     "`weekly_training_sheet` 产出的 `sessions` 已经反映了覆盖后的天数** —— 用 `len(sheet.sessions)` 当分母，"
     "**教师改了周天数，完成率的分母会跟着变**，而读模板值不会。\n"
     "  分子 = 那些日子里 `completed=True 且 late=False 且 is_rest_day=False` 的行数（spec §8.1 的折中方案原文："
     "「每日都可打卡，非训练日一键『今日休息』；但**完成率只按处方训练日计算**」）。"
     "**无处方、或 `current_week` 返回 `None`（处方已到期）→ 完成率返回 `null` 而不是 `0`**"
     "（「不知道」不得讲成「0%」，Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）。",
     1, "P5-A2 完成率的分母"),

    # P5-A5：Page 是函数不是模型（更正 Task 1 的 Interfaces）
    ("  - `Page`（`limit: int = 50`（上界 200）、`offset: int = 0`）",
     "  - `Page`（`limit: int = 50`（上界 200）、`offset: int = 0`）"
     "**⚠️ P5-A5 更正：`Page` 实测是一个 FastAPI 依赖函数、不是 Pydantic 模型** —— "
     "`def Page(*, limit: Annotated[int, Ge(ge=1), Le(le=200)] = 50, offset: Annotated[int, Ge(ge=0)] = 0) -> None`。"
     "上面那句 `(BaseModel)` 的说法是错的（Task 1 的实现者选了依赖函数，因为查询参数用 `Annotated` 比 Pydantic 模型更自然）。"
     "**用法是 `page: Page = Depends()`。⚠️ 不要去改 `Page` 的形状**——Task 3 的 23 个资源都在用它，"
     "改形状会连带 47 个端点。",
     1, "P5-A5 Page 是函数不是模型"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### 插曲：用户报 `net::ERR_ABORTED http://127.0.0.1:8000/docs`

**诊断（控制者亲跑）：不是后端的问题。** uvicorn 的访问日志逐字是：
```
GET /docs           HTTP/1.1" 200 OK      ← 六次，全部 200
GET /openapi.json   HTTP/1.1" 200 OK
GET /%40vite/client HTTP/1.1" 404 Not Found   ← 问题在这
```
`/%40vite/client` 解码就是 **`/@vite/client`——Vite 的 HMR 客户端脚本**。**trae-preview 那个面板是为 Vite dev server 设计的**，它会往它加载的任何页面里注入 `<script src="/@vite/client">`；我们的服务是 uvicorn 不是 Vite，这个请求必然 404，于是面板**中止了整个导航**并报 `ERR_ABORTED`。控制者自己用 httpx 打 `/docs` 也是 200。
**处置**：告知用户**在普通浏览器标签页里打开**，不要用预览面板。**Plan 04 的前端是 Vite，那时预览面板就能正常用了** → 已按硬规矩 #86 记进 Plan 04 的约束。
**⚠️ 这条值得记的理由**：`ERR_ABORTED` 看起来像服务端故障，而**证据（访问日志里 `/docs` 是 200、404 的是另一个路径）指向客户端注入**。与 Plan 02 的 P7-A4（`IntegrityError` 看起来像数据坏了，实际是删除顺序）同族：**报错的位置不是原因的位置。**

---

### Task 5: §8.1 三源采集的特例端点 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`fcbb00e`。**测试基线**：`910 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **50**；**51 个端点在线**。
**取证脚本**：`t5_probes/_preflight.py` 与 `t5_probes/_preflight2.py`（两份，因为第一份的输出被管道截断在第 4 节；**⚠️ 这违反 Ruling 1 的「每个 Task 只做一份探针」，但两份是同一份的两个半场、不是两次扫描**）。

#### Ruling 13 — 预检查出 2 Critical / 3 Important / 1 Minor，计划正文更正 4 处

**P5-A1（Critical）：`class_session.batch_id` 与 `training_log.batch_id` 都是 `NOT NULL` 外键指向 `daily_sync_run.id`，而本 Task 要让教师实时建课次、学生实时打卡 —— 这两种行都没有批次可指，照今天的 schema 写进去会当场 `NOT NULL constraint failed`。**
⚠️ **更麻烦的是 `repo.delete_by_batch` 的 docstring 逐字写着「`TrainingLog` 由 Task 5 接（进 `_replay_cleanup`）」** —— 即 **Task 2 是按「`training_log` 是批处理产物」设计的，而 spec §8.1 说它同时是学生每天打卡的落点**。**这张表有两个来源，而 `batch_id NOT NULL` 只容得下一个。**
**裁定：两列都改成 `nullable=True`。** 适配器/批处理写的行带 `batch_id`（`_replay_cleanup` 按批删它们）、**用户实时写的行留 `NULL`** —— 而 `delete_by_batch` 是 `WHERE batch_id = :b`，**SQL 里 `NULL = 任何值` 都不成立 → 实时行天然躲过重放，这正是我们要的**（spec §8.1 的打卡是学生的作业，重放不该删掉它）。
⚠️ **`_BATCH_OWNED_TABLES` 那条守卫不受影响**（它断言的是「**有 `batch_id` 列**的表恰好是那九张」，可空性不改变列的存在）。⚠️ 但 `repo.delete_by_batch` 的 docstring 要同步（硬规矩 #66）。
**→ 控制者错误 #16**：Task 2 的字段清单里，`batch_id` 的「带 / 不带」是按**「这张表是不是批处理产物」**二分决定的（四张带、三张不带），而**真实情况是「这张表的行有没有批次来源」——`training_log` 两个来源都有，二分法容不下它**。**这与 Plan 02 的控制者错误 #5（把「枚举分桶的 6 个结果」当成「分层判定的 3 个结果」）同型：用一个二分/三分类去套一个实际上有更多档的东西。**
**→ 补硬规矩 #106：给一张表定「带不带某个归属列」时，先列出这张表的全部写入来源；只要有两个以上的来源、而其中至少一个没有那个归属，那一列就必须可空。** 依据：P5-A1 / 控制者错误 #16。

**P5-A2（Critical）：`TrainingPackage` 没有 `weekly_frequency` 字段** —— 实测字段只有 `template_id` / `template_version` / `weeks` / `assembly_snapshot` / `paused`。而计划把完成率的分母定成「= `Template.weekly_frequency`」，**从处方行里读不到它**。
**裁定：分母改成 `len(sheet.sessions)`。** ⚠️ **这个改法不只是「能读到」，它比原方案更对**：`Template.weekly_frequency` 是模板的静态值，而**教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`weekly_training_sheet` 产出的 `sessions` 已经反映了覆盖后的天数** —— 用 `len(sheet.sessions)` 当分母，**教师改了周天数，完成率的分母会跟着变**，而读模板值不会。**无处方、或 `current_week` 返回 `None`（处方已到期）→ 完成率返回 `null` 而不是 `0`。**
**→ 控制者错误 #17**：写「分母 = `Template.weekly_frequency`」时**没有核实它在 API 层能不能读到** —— 它是 domain 的 `Template` 的字段，而端点手上只有 `Prescription` 行与它的 `training_package` JSON。**这与 Plan 02 的控制者错误 #148 同型**（「只核了 `LastPrescription.microcycle_weeks` 有没有住址，没把 5 个字段逐个对到列上」）—— **都是「在一个层里引用另一个层的字段，没核那一层手上有没有它」**。

**P5-A3（Important）：`training_log.source` 是 `VARCHAR(16) NOT NULL`，但 `TrainingLog` 没有 `SOURCES` 类常量、也没有对应的 CHECK**（实测该表只有 `ck_training_log_feeling` 一条）。而 P5-A1 说明这张表有两个来源 —— **值域没有单一所有者**。裁定：加 `TrainingLog.SOURCES`（至少 `{"checkin", "lepao"}`，**学生打卡的端点写 `"checkin"`**）+ 按 `feeling` 的既有做法用 `_in_domain` 加一条 CHECK。⚠️ **加 CHECK 是 schema 变更 → `test_models.py` 里「`_in_domain` 列数 = 23」那条断言会红**（硬规矩 #88）。

**P5-A4（Important）：`app/config.py` 今天没有 `TIMEZONE`**（实测只有 `BACKEND_DIR` / `DEFAULT_CSV_DIR` / `DEFAULT_DB_URL`）。**`zoneinfo` 可用** ✅（实测 `ZoneInfo("Asia/Shanghai")` 与 `datetime.now(z)` 都正常，**无 tzdata 缺失问题**）。本 Task 新增 `TIMEZONE = "Asia/Shanghai"`。⚠️ **`DEFAULT_DB_URL` 实测逐字是 `sqlite:///…/backend/pe.db`（禁区）**。

**P5-A5（Important）：`deps.Page` 实测是一个 FastAPI 依赖函数、不是 Pydantic 模型** —— `def Page(*, limit: Annotated[int, Ge(ge=1), Le(le=200)] = 50, offset: Annotated[int, Ge(ge=0)] = 0) -> None`。**计划 Task 1 的 Interfaces 写的 `Page(BaseModel)` 是错的**（Task 1 的实现者选了依赖函数，因为查询参数用 `Annotated` 更自然）。**本 Task 照实测的形状用 `page: Page = Depends()`，不要去改 `Page`**（Task 3 的 23 个资源都在用它）。**→ 控制者错误 #18：计划的 Interfaces 一节写了一个与实现不符的类型**，而 Task 3 的实现者照实测的形状用了、没有顶回来（因为它没有理由去核 Task 1 的 Interfaces 那一句）——**这正是「Interfaces 一节是后续 Task 的唯一契约来源」这句话的代价：它一旦写错，后面每个 Task 都要靠自己实测才能发现。**

**P5-A6（Minor）：`ClassSession` 没有任何类常量**，而 `rpe_token` 是 `VARCHAR(16)`、本 Task 要用 `secrets.token_urlsafe(12)[:16]` → **`16` 会成为两个没有出处的魔数**。裁定：加 `ClassSession.RPE_TOKEN_LEN = 16`，列类型与生成代码都引它。
**⚠️ 顺带核实到架构守卫不拦 `secrets`**：实测 `_is_api_allowed` 是**只针对 `app.*` 前缀**的 allow-list（`FORBIDDEN_PREFIX = "app.seed"`），**标准库不受它约束**。

**⚠️ 两件核实到的好事**（不用改，但值得记，因为它们说明前序 Task 的实现者做得比派单要求的更远）：
1. **Task 1 的守卫 allow-list 已经预留给 Task 6 与 Task 9**：`_API_ALLOWED_PREFIXES` 里有 `app.refdata_alerts`（**今天还不存在**，Task 6 才建）与 `app.adapters`（Task 9 的 `POST /api/pipeline/run-daily` 要它，因为 `daily.run_daily` 的第四个参数是适配器实例、而 `build_adapter` 住在 `app.adapters.factory`）。docstring 逐字写着「allow-list 里列一个尚不存在的模块是安全的（它是许可、不是断言），而列在这里正是为了兑现『后面 8 个 Task 不再动本文件』」。**S6 那条裁定被完整兑现了。**
2. **`repo.delete_by_batch` 的 docstring 已经把 Task 5/8 的活写清楚了**：「`Alert` 与 `WeeklyClassReport` 由 Task 8 接进清单，`TrainingLog` 由 Task 5 接，而 **`ClassSession` 不得接**——`rpe_record.class_session_id` 是 NOT NULL 的外键指向它，按批删课次会当场 FK 违例（改成 `CASCADE` 更糟：会连带删掉学生刚交的快评），它的幂等手段是 `upsert` 按 `(course_section_id, session_date, period)` 更新」。**本 Task 照它办。**

**计划正文更正**：`_t5_preflight_patch.py`，**4 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-5-brief.md` → 派实现者。**⚠️ 本 Task 的第一件事是落地 Ruling 12 那条阈值放宽**（`assert elapsed < 60` → `< 90` + docstring 如实改写），因为「全量绿」这个判据要先恢复可信。
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
SENT = "Ruling 13 — 预检查出 2 Critical / 3 Important / 1 Minor"
assert SENT not in lt, f"{SENT!r} 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)}")
for k in ("Ruling 13", "硬规矩 #106", "控制者错误 #16", "控制者错误 #18", "P5-A1", "ERR_ABORTED"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")
