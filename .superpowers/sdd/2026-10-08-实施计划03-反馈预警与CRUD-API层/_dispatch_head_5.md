# Task 5 简报 — §8.1 三源采集的特例端点

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 5 全节（含预检更正 P5-A1..A6）**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **910 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `909 passed, 1 skipped`）。**本 Task 不加 domain 代码，四格应逐字不变。**
**表数 25**；`_MODELS_PUBLIC_BASELINE` **33（不动）**；扫描面 **50**；**HTTP 端点 51 个在线**（`/api/` 路径模板 51、操作数 77）。
**环境**：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、FastAPI **0.141.1**、Pydantic **2.13.5**、httpx 0.28.1。**`zoneinfo` 可用**（控制者实测 `ZoneInfo("Asia/Shanghai")` 与 `datetime.now(z)` 都正常，**无 tzdata 缺失问题**）。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**
⚠️ **控制者有一个 uvicorn 进程跑在 `127.0.0.1:8000`（用 `pe_demo.db`）**。你要手工起服务的话**换一个端口**。

**⚠️⚠️ 本 Task 的第一件事不是写端点，是落地 Ruling 12 那条阈值放宽**：`backend/tests/pipeline/test_backfill.py` 的 `test_backfill_500_students_under_60_seconds` 里 **`assert elapsed < 60` 改成 `< 90`**，并按账本 Ruling 12 如实改写它的 docstring（三件事：spec §1.3 的「< 60 s」在本原型**不予验收**、保留这条断言的目的是**数量级哨兵**而非 60 s 契约、测量条件与「全量跑时机器负载会把它推过 60 s（实测 61.58 与 62.72）」）。**函数名里的 `under_60_seconds` 也要跟着改成 `under_90_seconds`**（否则函数名成为谎话）。**理由：一条会 flaky 的测试让「全量绿」这个判据失去意义，而后面 5 个 Task 的验收都要引用它。**

## 0.1 ⚠️ 本 Task 的 2 条 Critical

**P5-A1：`class_session.batch_id` 与 `training_log.batch_id` 都是 `NOT NULL` 外键指向 `daily_sync_run.id`，而本 Task 要让教师实时建课次、学生实时打卡 —— 这两种行都没有批次可指，照今天的 schema 写进去会当场 `NOT NULL constraint failed`。**
⚠️ **更麻烦的是 `repo.delete_by_batch` 的 docstring 逐字写着「`TrainingLog` 由 Task 5 接（进 `_replay_cleanup`）」** —— 即 Task 2 是按「`training_log` 是批处理产物」设计的，而 spec §8.1 说它**同时**是学生每天打卡的落点。**这张表有两个来源，而 `batch_id NOT NULL` 只容得下一个。**
**裁定：两列都改成 `nullable=True`。** 适配器/批处理写的行带 `batch_id`（`_replay_cleanup` 按批删它们）、**用户实时写的行留 `NULL`** —— 而 `delete_by_batch` 是 `WHERE batch_id = :b`，**SQL 里 `NULL = 任何值` 都不成立 → 实时行天然躲过重放，这正是我们要的**。
⚠️ **`_BATCH_OWNED_TABLES` 那条守卫不受影响**（它断言的是「**有 `batch_id` 列**的表恰好是那九张」，可空性不改变列的存在）。⚠️ 但 **`repo.delete_by_batch` 的 docstring 要同步**（硬规矩 #66）：写明九张里有两张的这一列现在是可空的、以及为什么。
⚠️ **`ClassSession` 不得接进 `_replay_cleanup`**（`repo.delete_by_batch` 的 docstring 逐字写了理由：`rpe_record.class_session_id` 是 NOT NULL 外键指向它，按批删课次会当场 FK 违例；改成 `CASCADE` 更糟——会连带删掉学生刚交的快评。**它的幂等手段是 `upsert` 按 `(course_section_id, session_date, period)`**，Task 2 已加那条唯一约束）。

**P5-A2：`TrainingPackage` 没有 `weekly_frequency` 字段** —— 实测只有 `template_id` / `template_version` / `weeks` / `assembly_snapshot` / `paused`。而计划把完成率的分母定成「= `Template.weekly_frequency`」，**从处方行里读不到它**。
**裁定：分母改成 `len(sheet.sessions)`。** ⚠️ **这不只是「能读到」，它比原方案更对**：教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`weekly_training_sheet` 产出的 `sessions` **已经反映了覆盖后的天数** → 用 `len(sheet.sessions)` 当分母，**教师改了周天数、完成率的分母会跟着变**，而读模板值不会。**无处方、或 `current_week` 返回 `None`（处方已到期）→ 完成率返回 `null` 而不是 `0`**（「不知道」不得讲成「0%」）。

## 0.2 其余 4 条（简报的预检总表里有完整实测依据）

- **P5-A3**：`training_log.source` 是 `VARCHAR(16) NOT NULL`，但 `TrainingLog` **没有 `SOURCES` 类常量、也没有对应的 CHECK**（该表今天只有 `ck_training_log_feeling`）。→ **加 `TrainingLog.SOURCES`**（至少 `{"checkin", "lepao"}`，**学生打卡的端点写 `"checkin"`**）+ 按 `feeling` 的既有做法用 `_in_domain` 加一条 CHECK。⚠️ **加 CHECK 是 schema 变更 → `test_models.py` 里「`_in_domain` 列数 = 23」那条断言会红**（硬规矩 #88：先跑全量、把红掉的相等断言逐个收进来）。
- **P5-A4**：`app/config.py` **今天没有 `TIMEZONE`**（只有 `BACKEND_DIR` / `DEFAULT_CSV_DIR` / `DEFAULT_DB_URL`）→ **新增 `TIMEZONE = "Asia/Shanghai"`**。⚠️ `DEFAULT_DB_URL` 实测逐字是 `sqlite:///…/backend/pe.db`（**禁区**），手工起服务必须显式设 `PE_DB_URL`。
- **P5-A5**：**`deps.Page` 实测是一个 FastAPI 依赖函数、不是 Pydantic 模型**（`def Page(*, limit: Annotated[int, Ge(ge=1), Le(le=200)] = 50, offset: Annotated[int, Ge(ge=0)] = 0) -> None`）。**用法是 `page: Page = Depends()`。⚠️ 不要去改 `Page` 的形状**——Task 3 的 23 个资源都在用它。
- **P5-A6**：`ClassSession` **没有任何类常量**，而 `rpe_token` 是 `VARCHAR(16)`、本 Task 要用 `secrets.token_urlsafe(12)[:16]` → **`16` 会成为两个没有出处的魔数**。**加 `ClassSession.RPE_TOKEN_LEN = 16`**，列类型与生成代码都引它。⚠️ **架构守卫不拦 `secrets`**：实测 `_is_api_allowed` 是**只针对 `app.*` 前缀**的 allow-list（`FORBIDDEN_PREFIX = "app.seed"`），标准库不受它约束 → **本 Task 不需要动守卫**。

## 0.3 你要交付什么

**Create**：`backend/app/api/routers/feedback.py`、`backend/tests/api/test_feedback.py`
**Modify**：`backend/app/api/schemas/feedback.py`（**⚠️ 它由 Task 3 创建，只补特例模型，不要覆盖**）、**`backend/app/db/models/feedback.py`**（P5-A1 两列改可空 + P5-A3 `SOURCES` 与 CHECK + P5-A6 `RPE_TOKEN_LEN`）、**`backend/app/config.py`**（P5-A4 `TIMEZONE`）、**`backend/app/db/repo.py`**（P5-A1 的 docstring 同步）、`backend/tests/db/test_models.py`（P5-A3 的连带）、`backend/app/api/routers/__init__.py`（include 新 router，**不是 `main.py`**）、**`backend/tests/pipeline/test_backfill.py`**（Ruling 12 的阈值放宽，**第一件事**）

**七个端点**（简报的 Task 5 节有完整口径）：`POST /api/class-sessions/{id}/open-rpe`、`POST /api/rpe-records`、`GET /api/class-sessions/{id}/rpe-status`、`POST /api/training-logs`、`GET /api/students/{id}/training-logs/completion-rate?semester_id=&week=`、`POST /api/mini-tests/batch`、`GET /api/mini-tests/normalized?semester_id=&week=`

**⚠️ 打卡 `late` 的三个模糊点必须定死并测边界**（Review Focus 第 2 条，简报有完整理由）：① **22:00:00 整点不算迟**（窗口是闭区间 `[00:00, 22:00]`，`late = submitted_at.time() > time(22, 0)`）；② **补卡入库但不计入完成率**（`log_date` 与 `submitted_at` 的日期不一致时）；③ **一律用 `app.config.TIMEZONE`**，服务端把 `datetime.now(ZoneInfo(TIMEZONE))` 转成 naive 本地时间再比较（SQLite 存 naive `DateTime`，混用 aware 与 naive 会 `TypeError`）。**测试：`21:59:59` 不迟、`22:00:00` 不迟、`22:00:01` 迟。**

## 0.4 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（四格应逐字不变）；单一所有者；断言两侧不同源；架构守卫全绿；**既有 910 条测试一条都不许退步**。
- **不做变异**（Ruling 1：变异只在 Task 6 要求）。**但 Task 2/3/4 的实现者都自己加了变异自证，控制者三次都采纳并鼓励。**
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。Plan 02 顶回 **25/25**，Plan 03 已顶回 **17/17**（累计 **42/42**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定。**

## 0.5 纪律

- **禁区**：`backend/pe.db`（**不得存在**）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
- **数列/字段/成员一律用运行时口径**，**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`**（#89 扩写）；**数「一个名字有几份定义」用 AST**（#89 再扩写）；**一个探针里若有两种口径，以运行时那一种为准、另一种标注为不可用**（硬规矩 #103）。
- **断言「A 等于/不等于 B」时，若任一侧经过序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99）。
- **用哨兵值代替 NULL 之前，必须先确认那一列不是外键**（硬规矩 #101）。
- **不要凭记忆构造 HTTP 请求的 payload**：先从 `/openapi.json` 读那个 schema 的 `required`（控制者本次冒烟的第一版脚本就栽在这里，账本控制者错误 #13）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件。

## 0.6 commit 与报告

**建议 3–4 个 commit**：① Ruling 12 的阈值放宽（**先做，让「全量绿」恢复可信**）；② P5-A1/A3/A6 的 schema 变更 + `TIMEZONE` + 连带断言；③ 七个端点 + 测试；④ 收尾。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-5-report.md`（**python 写**）。至少 8 节：① 环境与基线复现（含 Ruling 12 落地后的 `elapsed` 实测值）；② P5-A1/A3/A6 的 schema 变更（新旧列的 nullable、新 CHECK 名、新类常量）；③ 七个端点的路径/方法/请求响应形状；④ **`late` 的三条边界测试与完成率的分母口径**；⑤ `test_models.py` 因 P5-A3 红掉的断言有哪几条、各改成什么；⑥ 待清扫 / 关切 / **没按派单做的地方（0 处也要写）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑦ 最终验收（passed 数 910 → ?、覆盖率四格应不变、表数 25、扫描面 50 → ?、端点数 51 → ?、三个指纹、`git diff <base> HEAD -- backend/data` 为空、`pe.db` 不存在）；⑧ commit sha。

## 0.7 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格（应逐字不变）/ 扫描面与端点数的新值 / **Ruling 12 落地后的 `elapsed` 实测值** / P5-A1 两列改可空后的实测 nullable / `TrainingLog.SOURCES` 的值与新 CHECK 名 / `test_models.py` 改了几条断言 / 七个端点的路径与方法 / `late` 的三条边界测试名 / 完成率分母的实现位置 / 三个指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

---

