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


# 实施计划 03：智慧反馈层 + 预警 + 全系统 CRUD API

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01/02 的批处理系统变成一个**能用浏览器点起来的原型系统**——加一层 FastAPI HTTP 接口覆盖全部实体的增删改查，补齐 spec §8 的智慧反馈层（三源采集 + 三级预警 + 班级周报），并让「预警 → 减量 20% → 学生端看到更新后的训练单」这条闭环真的跑通。

**Architecture:** 模块化单体不变。新增两层：`app/api/`（FastAPI 路由 + Pydantic schema，**可以读 DB、可以碰时钟**）与 `app/domain/alerts.py`（预警规则的纯函数叶子层，与 `app/domain/` 其余模块同纪律：无 I/O、100% 分支覆盖）。**CRUD 用一个泛型工厂生成**（`app/api/crud.py` 的 `build_crud_router`），而不是给 23 个资源各写一遍路由——原型阶段「一致的行为」比「每个资源有自己的特例」更值钱。反馈三源与预警落地是**手写的特例路由**（它们有业务语义，不是 CRUD）。

**Tech Stack:** Python 3.11.1、**FastAPI 0.141.1 / Starlette 1.7.0 / Pydantic 2.13.5 / uvicorn 0.54.0 / httpx 0.28.1（全部已装，`backend/pyproject.toml` 早已声明，本计划不引入任何新依赖）**、SQLAlchemy 2.1.3、SQLite、PyYAML、pytest + pytest-cov。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md`（128 328 B / 1 093 行）—— 本计划实现 **§4.5（反馈三源 4 张表）、§4.6（`alert` / `notification`）、§4.7（`weekly_class_report`）、§8.1（三源采集）、§8.2（5 条预警规则）、§8.3（消息通知，只做 `InAppChannel`）、§8.4（`weekly_adjustment` 的 `auto` 来源）、§8.5（班级周报）、§9 的后端侧（大屏与两端页面要的数据接口）**。

**上游状态（Plan 01 + Plan 02 已交付并合入 `main`，commit `a5f16b1`）：** `807 passed`、`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**、**18 张表**、`app.domain.prescription.__all__` **51**、架构守卫扫描面 **35**（pipeline 8 + db 11 + domain 16）。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-…/progress.md`（Rulings 1–234、硬规矩 #1–#47）与 `.superpowers/sdd/2026-10-06-实施计划02-…/progress.md`（Rulings 1–158、硬规矩 #48–#94、控制者错误 158 条）。

**⚠️ 用户裁定（2026-10-08，两次）：「项目只要能运行起来的原型系统就好」「后端其实只要不出太大的 bug 就行，算法层面要求不是很高，主要是要做一个系统，类似管理型的原型系统，需要能够进行增删改查，然后加上之前的大数据算法即可」。** 本计划的每一个取舍都以这句话为最高准则：**能跑通 > 参数保真；一致的 CRUD > 每资源特例；站内消息 > 真实推送；Mock 适配器 > 真实乐跑接口。**

---

## Global Constraints

- **不引入新依赖**。`fastapi` / `uvicorn[standard]` / `httpx` 已在 `backend/pyproject.toml` 的 `dependencies` 与 `dev` 里，且实测已装（fastapi 0.141.1 / uvicorn 0.54.0 / httpx 0.28.1 / pydantic 2.13.5 / starlette 1.7.0）。**开工第一件事是复跑那条 import 冒烟并把版本记进报告**（硬规矩 #73）。
- **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / `datetime`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy, typing}`。**时间与随机数一律由调用方注入，参考表一律作为参数传入。** 守卫是 `tests/architecture/test_domain_purity.py` 与 `test_layering.py`。
- **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令必须带 `--cov-branch`：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。本计划新增的 `app/domain/alerts.py` 纳入这个口径。
- **`app/api/` 是新的层，架构守卫今天不认识它**。实测 `test_layering.py` 扫的是 `("pipeline", 7)` / `("db", 11)` / `("domain", 16)` 三个目录、下界断言是 `>=5` / `>=8` / `>=16` 之类。**Task 1 要给守卫加 `api` 这一层并定它的依赖方向**（`api` 可以 import `db` / `domain` / `pipeline` / `refdata*`，**反向一律禁止**）。⚠️ 加一层会让扫描面从 35 涨上去，**涨了要在报告里说明**。
- **Ruling 97（`models` 的公有导入面）**：`_MODELS_PUBLIC_BASELINE` 恒为 **33**，Plan 02 的四个表类（`Exercise` / `PrescriptionTemplate` / `Prescription` / `WeeklyAdjustment`）**刻意不在** `app.db.models` 的 `__all__` 里，本计划新增的 7 个表类**同样不进**。**一律走子模块路径**：`from app.db.models.feedback import ClassSession`。守卫是 `test_models_public_namespace_is_unchanged_by_the_split` 与 `test_plan02_tables_stay_out_of_the_models_public_namespace`（Task 2 要把后者扩到 7 张新表）。
- **分区穷尽守卫**：`tests/seed/test_generate.py` 的 `assert partitioned == actual`（`ORGANISATION_TABLES` 5 + `DATA_TABLES` 11 + `REFERENCE_TABLES` 2 = 18）。**7 张新表必须归进 `DATA_TABLES`**（11 → 18），否则这条红。⚠️ 同一文件的 `for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0` 要求 **seed 阶段这些表 0 行** —— 而本计划 Task 2 要给反馈表灌演示数据，**灌数据的函数不得叫 `seed_database`、不得进它的那一圈**（见 Task 2 的决定）。
- **单一所有者**：任何常量/词表/阈值只允许有一个住址。预警阈值的唯一所有者是 `backend/data/alert_rules.yaml`（spec §4.4 逐字：「`alert_rules`（预警阈值）为 `data/` 下的**静态 YAML + 版本号**，不入库……改阈值应走版本控制与评审，不应在运行时改数据库」）。**RPE 的值域 0–10 的唯一所有者是 spec §8.2**，Plan 02 已把它写进 `assembler.py` 的 docstring 与 `INTENSITY_TYPES` 的 `rpe` 档；**不要在本计划里写第三份**。
- **断言两侧不得同源**（硬规矩 #35）：期望值一律字面写在测试里。
- **`backend/data/` 的行尾纪律**：`.gitattributes` 钉了 `backend/data/*.yaml text eol=lf` 与 `backend/data/**/*.yaml text eol=lf`。新增的 `alert_rules.yaml` 落进同一条规则，**写完立刻用 `read_bytes()` 复核 CRLF 计数为 0**（硬规矩 #89 的扩写：数行尾用 `read_bytes()`，不用 `read_text()`）。**改被指纹钉住的文件要同步常量**（Plan 02 Task 9 做过一次：`EXERCISES_FINGERPRINT` `3DE598AF38631209` → `5394B37F01DAC9AC`）。
- **禁区**：`backend/pe.db`（不得存在——⚠️ **但本计划要跑 uvicorn，它会建库文件**，见 Task 1 的决定）、`backend/data/seed/`（0 文件）、三个指纹 `D2C8E539E2FA0029`（CSV）/ `5394B37F01DAC9AC`（`exercises.yaml`）/ `822CB86A5E998301`（`exercise_equivalence.yaml`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`。
- **PowerShell**：分隔用 `;`，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑一律写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文）。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **数键/字段/成员/表格行一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))` / 数换行 + 校验首尾两行），**绝不用正则数源码**（硬规矩 #89/#93）。控制者在 Plan 02 为此栽了 4 次（#139 跨行元组 / #147 大写键 / #153 `read_text()` 换行 / #155 加粗编号）。
- **落盘唯一权威是 shell**；**`git checkout` / `git switch` / `git merge` 会按 `core.autocrlf` 重写工作树**（硬规矩 #46），事后必须复核所有「按字节哈希」的断言。要还原一个改坏的文件，用 python 从 TEMP 备份写回原字节，**不用 `git checkout`**。

## Review Focus

spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。下面五类是一个真实使用者最可能撞上、而 spec **没有覆盖**的，每类都在拥有该代码的 Task 里补了测试：

1. **越权访问**：学生 A 用 `X-Student-Id: B` 的请求头去读/写学生 B 的打卡、RPE、训练单、处方。原型没有真实鉴权，但**必须有一道「身份与作用域」的闸门**，否则前端一上线就是任意读写全库。归属 Task 1（依赖注入 + 作用域校验）与 Task 5（三源采集的写入方）。
2. **打卡的时间边界**：spec §8.1 逐字「打卡窗口 = 当日 00:00–22:00。22:00 后提交仍入库但标记 `late = true`，**不计入当日完成**」。22:00:00 整点算哪边？跨时区/夏令时？服务器时钟与学生本地时钟不一致？**必须响亮地定一个口径并测边界**，因为「完成率是 RCT 关键过程指标，必须严格」（spec 原文）。归属 Task 5。
3. **预警的重复触发**：同一条 `RED_RPE_SUSTAINED` 在连续第 3、4、5 次快评都满足条件 → 会不会生成 3 条 `alert`、推 3 次「减量 20%」、把训练量连乘成 `0.8³ = 0.512`？**必须有去重口径**（同一学生 + 同一规则 + 同一「未处理」状态只有一条活跃 alert）。归属 Task 7。
4. **CRUD 的删除连带**：删一个 `semester` 会带走它下面的 `student` / `fitness_test_result` / `prescription` 吗？删一个 `prescription` 会带走它的 `weekly_adjustment` 吗？SQLite 跑在 `PRAGMA foreign_keys=ON` 下，**FK 违例是当场炸而不是静默留下孤儿行**（Plan 02 Task 7 的 P7-A4 就是这个坑：`_replay_cleanup` 必须先删子表）。泛型 CRUD 工厂必须对每个资源显式声明删除策略。归属 Task 3。
5. **`alert_rules.yaml` 被改坏**（少一个键、阈值写成字符串、规则 ID 拼错、版本号缺失）→ 必须在**加载时**响亮失败并指出是哪个键，而不是在某个学生触发预警时才炸。与 Plan 02 Review Focus 第 1 条（模板 YAML 被专家改坏）同构，照它的口径办。归属 Task 6。

---

## File Structure

**新建（生产）**

| 路径 | 职责 |
|---|---|
| `backend/app/main.py` | FastAPI 应用工厂 `create_app()` + `app = create_app()`；挂 CORS、异常处理器、全部路由；`uvicorn app.main:app` 的入口 |
| `backend/app/api/__init__.py` | 空 |
| `backend/app/api/deps.py` | `get_db()` 依赖（`Session` 生成器）、`current_student()` / `current_teacher()`（从请求头取身份）、`Page`（分页参数）、`require_scope()`（作用域闸门，Review Focus 第 1 条） |
| `backend/app/api/crud.py` | **`build_crud_router(...)` 泛型工厂**：一次生成 list/create/read/update/delete 五个端点 |
| `backend/app/api/errors.py` | 统一的错误响应形状 + `domain ValueError → 422`、`IntegrityError → 409`、`NoResultFound → 404` 的映射 |
| `backend/app/api/schemas/__init__.py` | 重导出 |
| `backend/app/api/schemas/organisation.py` | `semester` / `teacher` / `student` / `course_section` / `enrollment` 的 Pydantic 模型（`Read` / `Create` / `Update` 三件套） |
| `backend/app/api/schemas/assessment.py` | `fitness_test_batch` / `fitness_test_result` / `body_composition` / `interest_survey` |
| `backend/app/api/schemas/derived.py` | `percentile_snapshot` / `derived_metrics` / `stratification_result`（**只读**） |
| `backend/app/api/schemas/prescription.py` | `exercise` / `prescription_template` / `prescription` / `weekly_adjustment` + 教师覆盖的写入模型 |
| `backend/app/api/schemas/feedback.py` | `class_session` / `rpe_record` / `training_log` / `mini_test` |
| `backend/app/api/schemas/alerts.py` | `alert` / `notification` / `weekly_class_report` |
| `backend/app/api/routers/__init__.py` | `APIRouter` 汇总，`create_app()` 只 include 这一个 |
| `backend/app/api/routers/catalog.py` | 23 个资源的 CRUD 路由（全部由 `build_crud_router` 生成，一个列表驱动） |
| `backend/app/api/routers/feedback.py` | §8.1 三源采集的特例端点 |
| `backend/app/api/routers/prescription.py` | 教师覆盖、本周训练单、手动重生成 |
| `backend/app/api/routers/alerts.py` | 预警处理（→ 减量 20%）、通知已读 |
| `backend/app/api/routers/dashboard.py` | 教师大屏（§9.1）与学生端首页（§9.2）要的聚合读接口 |
| `backend/app/api/routers/pipeline.py` | `POST /api/pipeline/run-daily`（手动触发批处理，原型演示用） |
| `backend/app/domain/alerts.py` | **5 条预警规则的纯函数**（无 I/O，100% 分支覆盖） |
| `backend/app/refdata_alerts.py` | 加载 + 校验 `data/alert_rules.yaml`，持有 `alert_rules()` 单例（与 `refdata_prescription.py` 同口径：`load_*` 只加载不缓存，单例是另一个函数） |
| `backend/app/pipeline/alert_stage.py` | 预警求值 + 落库 + 幂等；`weekly_adjustment` 的 `auto` 来源 |
| `backend/app/pipeline/report_stage.py` | §8.5 班级周报生成 |
| `backend/app/notify.py` | `NotificationChannel` 接口 + `InAppChannel`（写 `notification` 表）+ 两个未来通道的骨架 |
| `backend/app/demo_data.py` | **反馈三源与预警的演示数据生成器**（⚠️ 不是 `seed_database`，见 Task 2） |
| `backend/data/alert_rules.yaml` | 5 条规则的阈值 + `version` |

**修改**：`backend/app/db/models/feedback.py`（475 B 空壳 → 4 张表）、`backend/app/db/models/ops.py`（+3 张表）、`backend/app/db/models/__init__.py`（子模块导入，**不改 `__all__`**）、`backend/tests/db/test_models.py`（表数 18 → 25 的**全部**命中点）、`backend/tests/seed/test_generate.py`（`DATA_TABLES` 11 → 18）、`backend/tests/architecture/test_layering.py`（加 `api` 层）、`backend/tests/fixtures/golden_cases.json`（**GC14**）、`backend/tests/integration/test_golden_cases.py`、`Document/…设计spec.md`（§14 补项）

**新建（测试）**：`backend/tests/api/`（`conftest.py` + `test_crud.py` + `test_feedback.py` + `test_alerts_api.py` + `test_dashboard.py` + `test_scope.py`）、`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`、`backend/tests/pipeline/test_alert_stage.py`、`backend/tests/pipeline/test_report_stage.py`、`backend/tests/test_notify.py`、`backend/tests/test_demo_data.py`、`backend/tests/test_main.py`

**⚠️ 本计划刻意不做**（用户裁定「能运行起来的原型系统就好」）：
- **`HttpLePaoAdapter` 的真实实现**。骨架已在（`app/adapters/http_lepao.py`，78 行，四个方法一律 `raise NotImplementedError`，docstring 逐字写明了未来实现必须满足的契约形状与「不得沿用『两个实现跑同一组契约测试』这种说法」）。**原型用 `MockLePaoAdapter` 就能跑通全链路**，而真实实现要补约 40 条行为契约测试且**接口字段今天未定**——写了也是猜测，而猜测出来的重试策略会在真实接口确定后变成需要拆掉的负担（那段 docstring 自己就是这么说的）。**留给真实对接那一期。**
- **真实消息推送**（微信订阅消息 / 短信）。spec §8.3 原文：「原型不做真实推送（需微信订阅消息资质 / 短信通道）」。**只做 `InAppChannel`**，另两个通道建骨架 + 契约测试。
- **真实鉴权**。用请求头传身份（`X-Student-Id` / `X-Teacher-Staff-No`），并在 `deps.py` 的 docstring 里明写「原型口径，上线前必须换成真实会话」。
- **性能压测**（用户 2026-10-08 裁定，Plan 02 已删）。

---

---

## Task 5: §8.1 三源采集的特例端点

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


**Files:** Create `backend/app/api/routers/feedback.py`、`backend/tests/api/test_feedback.py`；Modify **`backend/app/api/schemas/feedback.py`（⚠️ 它由 Task 3 创建，本 Task 只补特例模型，不要覆盖）**、**`backend/app/db/models/feedback.py`（P5-A1：`class_session.batch_id` 与 `training_log.batch_id` 改成可空；P5-A3：加 `TrainingLog.SOURCES` 类常量 + 一条 `_in_domain` CHECK；P5-A6：加 `ClassSession.RPE_TOKEN_LEN = 16`）**、**`backend/app/config.py`（P5-A4：新增 `TIMEZONE = "Asia/Shanghai"`）**、**`backend/app/db/repo.py`（P5-A1 的连带：`delete_by_batch` 的 docstring 要写明九张里有两张的这一列现在可空）**、`backend/tests/db/test_models.py`（**P5-A3 加 CHECK 会让「`_in_domain` 列数 = 23」那条断言红**）、`backend/app/api/routers/__init__.py`（include 新 router，**不是 `main.py`**）、**`backend/tests/pipeline/test_backfill.py`（⚠️ Ruling 12：把 `assert elapsed < 60` 放宽到 90 并如实改写 docstring）**

**Interfaces:**
- Produces:
  - `POST /api/class-sessions/{id}/open-rpe` →（教师）发起课堂快评：置 `rpe_opened=True`、生成 `rpe_token`（16 字符），返回 token
  - `POST /api/rpe-records` →（学生）提交快评。请求体 `{class_session_id, rpe, elapsed_seconds}`；**`submitted_at` 由服务端填**；`UniqueConstraint` 撞上 → **409**（一个课次只能交一次）
  - `GET /api/class-sessions/{id}/rpe-status` →（教师）已交/未交名单 + 人均 RPE + 提交耗时中位数（spec §8.1「教师端实时显示已提交/未提交名单，可现场催交」）
  - `POST /api/training-logs` →（学生）打卡。请求体 `{log_date, completed, duration_min, feeling, is_rest_day}`；**`late` 由服务端算**；同一天重复 → **409**
  - `GET /api/students/{id}/training-logs/completion-rate?semester_id=&week=` → 完成率（**只按处方训练日计**，spec §8.1 的折中方案）
  - `POST /api/mini-tests/batch` →（教师）按教学班批量录入（spec §8.1「教师确认并批量录入（按教学班列出学生逐个填）」）。请求体是一个列表；**部分失败要能报告是哪几条**（返回 `207`-风格的 `{"created": n, "failed": [{index, student_id, message}]}`，HTTP 状态仍是 `200`）
  - `GET /api/mini-tests/normalized?semester_id=&week=` → 标准化得分（spec §8.1 的算式：`深蹲得分 = 次数`、`折返得分 = 班内百分位反查`、`小测综合分 = 两项等权平均`）

**决定：**
- **⚠️ `late` 的口径（Review Focus 第 2 条）**：spec §8.1 逐字「打卡窗口 = 当日 00:00–22:00。22:00 后提交仍入库但标记 `late = true`，**不计入当日完成**」。**三个模糊点必须定死并测边界**：
  1. **22:00:00 整点算不算迟到？决定：不算**（窗口是 `[00:00, 22:00]` 闭区间，`late = submitted_at.time() > time(22, 0)`）。理由：spec 写的是「22:00 后」，而 22:00:00 不是「后」。
  2. **`log_date` 与 `submitted_at` 的日期不一致怎么办**（学生 23:50 打昨天的卡）？**决定：`late` 只看 `submitted_at` 的时刻，`log_date` 是学生在补哪一天**。但**补卡不计入完成率**——补的是过去的训练日，那一天已经过去了。⚠️ 这是工程决定，**登记 spec §14**。
  3. **时区**：**决定：一律用 `app.config` 里的 `TIMEZONE`（新增常量，缺省 `"Asia/Shanghai"`），服务端把 `datetime.now(ZoneInfo(TIMEZONE))` 转成 naive 本地时间再比较**。理由：SQLite 存的是 naive `DateTime`，混用 aware 与 naive 会 `TypeError`；而「学生本地时钟」在 H5 上不可信。**⚠️ 这条要在 docstring 里写明「原型口径：不处理跨时区学生」**。
  - **测试**：`21:59:59` 不迟、`22:00:00` 不迟、`22:00:01` 迟；补卡入库但不计入完成率；`late=True` 的行不计入完成率而 `is_rest_day=True` 的行也不计入分母。
- **⚠️ P5-A2 更正：完成率的分母 = `len(sheet.sessions)`，不是 `Template.weekly_frequency`。** 原文写「分母 = 该生当前处方在该周的训练日数（= `Template.weekly_frequency`，Plan 02 实测红 4 / 黄 3 / 绿 2）」—— **而 `TrainingPackage` 实测没有 `weekly_frequency` 字段**（只有 `template_id` / `template_version` / `weeks` / `assembly_snapshot` / `paused`），**从处方行里读不到它**。
  **改成 `len(sheet.sessions)`（`WeeklySheet.sessions`）不只是「能读到」，它比原方案更对**：`Template.weekly_frequency` 是模板的静态值，而**教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`weekly_training_sheet` 产出的 `sessions` 已经反映了覆盖后的天数** —— 用 `len(sheet.sessions)` 当分母，**教师改了周天数，完成率的分母会跟着变**，而读模板值不会。
  分子 = 那些日子里 `completed=True 且 late=False 且 is_rest_day=False` 的行数（spec §8.1 的折中方案原文：「每日都可打卡，非训练日一键『今日休息』；但**完成率只按处方训练日计算**」）。**无处方、或 `current_week` 返回 `None`（处方已到期）→ 完成率返回 `null` 而不是 `0`**（「不知道」不得讲成「0%」，Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）。
- **`elapsed_seconds`**：spec §8.1 逐字「记录**提交耗时**（指导文件要求 10 秒内完成）」。**由前端算、后端只存**（后端不知道学生什么时候打开的页面）。**可为 `null`**（前端没传）；`> 60` 不拒绝但**在 `rpe-status` 的响应里单独计数**（「疑似代填」的信号，spec §8.1 明写「**已知局限：无法防代填**」）。
- **不做扫码签到**（spec §8.1 原文：「H5 调摄像头权限复杂，且原型阶段学生已登录并绑定教学班」）。
- **`rpe_token` 的语义**：spec §4.5 有这一列（「快评口令」）。**决定：原型阶段它只是一个 16 字符的随机串，`POST /api/rpe-records` 校验它匹配**，用于挡「学生猜 `class_session_id` 乱交」。**不做过期**（原型）。⚠️ **随机串怎么生成**：`secrets.token_urlsafe(12)[:16]`。**⚠️ `secrets` 不在 domain 的 allow-list 里，但 `app/api/` 不是 domain**——API 层可以碰它。**要在 docstring 里写明「不是 `random`，因为 `random` 可预测」**。

- [ ] **Step 1–5: 写失败测试 → 实现 → 跑通 → 全量 → Commit**

---
