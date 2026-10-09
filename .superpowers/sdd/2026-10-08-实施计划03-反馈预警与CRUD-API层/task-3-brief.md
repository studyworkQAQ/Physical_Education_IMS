# Task 3 简报 — 泛型 CRUD 工厂 + 23 个资源

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 3 全节（含预检更正 P3-B1..B8 与那张 23 行的 import 路径表）**。

## 0. 派单说明（控制者写，不在计划正文里）

**这是 Plan 03 代码量最大的一个 Task**：一个泛型工厂 + 23 个资源的声明 + 4 个 schema 模块。**控制者预期 1 轮 fix round。**

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **845 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `844 passed, 1 skipped`）。**本 Task 不加 domain 代码，四格应逐字不变。**
**表数 25**（本 Task 不建表）；`_MODELS_PUBLIC_BASELINE` **33（不动）**；扫描面 **38** → 本 Task 建 `app/api/crud.py` + `app/api/schemas/*.py` + `app/api/routers/*.py`，**会涨**（涨到几要写进报告；⚠️ Task 1 已把守卫的下界一次性抬到 18，故**你不需要改下界断言**，只需在报告里说明新值）。
**环境**：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、FastAPI **0.141.1**、Starlette 1.7.0、Pydantic **2.13.5**、uvicorn 0.54.0、httpx 0.28.1。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

**Task 1/2 已交付、你要用的东西**：
- `app/main.py`：`create_app(*, db_url=None)`、**`DB_URL_ENV_VAR = 'PE_DB_URL'`**、**`DEMO_DB_URL`**（⚠️ 这两个常量住在 `main.py`，**不在 `deps.py`**）、`register_error_handlers(application)` 已被调用、`app = create_app()` 在模块末尾
- `app/api/deps.py`：`get_db(request: Request) -> Iterator[Session]`、`current_student(x_student_id: int | None = Header(None)) -> int`、`current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str`、`require_scope(session, student_id: int, requester_id: int) -> None`、`Page(BaseModel)`（`limit: int = 50 [Ge(1), Le(200)]`、`offset: int = 0 [Ge(0)]`）
- `app/api/errors.py`：`error_response(status_code, code, message, detail=None, headers=None) -> JSONResponse`、`register_error_handlers(app) -> None`（**已注册 6 个处理器**：`ValueError`→422 / `IntegrityError`→409 / `NoResultFound`→404 / `HTTPException` / `RequestValidationError` / 其余→500 且不泄漏堆栈；统一形状 `{"error": {"code","message","detail"}}`）
- `tests/api/conftest.py`：`app` / `engine` / `client` 三个夹具（内存库 + `StaticPool`）
- ⚠️ **`app/config.py` 的 `DEFAULT_DB_URL` 实测是 `sqlite:///…/backend/pe.db`（禁区）**，手工跑脚本必须显式设 `PE_DB_URL`
- ⚠️ **Task 2 的待清扫第 2 条**：`backend/pe_demo.db` 是陈旧的（18 张表），**控制者已删掉**；若你手工起 uvicorn，它会按 25 张表重建

## 0.1 ⚠️ 本 Task 的 1 条 Critical（照办，不要按计划原文的字面写 import）

**P3-B1：23 个资源里有 11 个的模型类不在 `app.db.models` 的公有导入面上**（Ruling 97：Plan 02 的 4 个 + Plan 03 的 7 个表类**刻意不重导出**）。实测：
- `exercise` / `prescription_template` / `prescription` / `weekly_adjustment` → **`from app.db.models.prescription import …`**
- `class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` → **`from app.db.models.feedback import …`**
- 其余 12 个（`semester` / `teacher` / `student` / `course_section` / `enrollment` / `fitness_test_batch` / `fitness_test_result` / `body_composition` / `interest_survey` / `percentile_snapshot` / `derived_metrics` / `stratification_result`）→ `app.db.models` 或各自的 `organisation` / `assessment` / `derived` 子模块都行

**照 `models.Prescription` 写会得到 11 个 `AttributeError`。** 简报的 Task 3 节里有一张 **23 行的表**，逐个给出「资源路径 / 表名 / 模型类 / **import 路径** / 列数 / 自然键（唯一约束的列） / `JsonText` 列」—— **`RESOURCES` 照它写，不要自己推。**

⚠️ **这条纪律已经三次没被传导**（Plan 02 的 P6-A8、Plan 03 Task 2 的 P3-A1、本次），故已立**硬规矩 #102**。**你若在别处又撞到「计划说 `models.X` 而 X 不在公有面上」，一律按子模块路径写并在报告里点名。**

## 0.2 其余 7 条（简报的预检总表里有完整实测依据）

- **P3-B2**：**3 个资源没有唯一约束**（`course_section`、`fitness_test_batch`、`notification`）→ `build_crud_router` 加 **`natural_key: tuple[str, ...] | None`**：非空 → POST 走 `repo.upsert`（撞键 409）；`None` → POST 走**裸 `session.add`**（**结构上不可能撞键，故没有 409 这一档**）。**那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的写一条反向测试**（`test_a_resource_without_a_natural_key_never_returns_409`）。
- **P3-B3**：`JsonText` 列实测 **21 个、分布在 8 张表**（`prescription` 与 `weekly_class_report` **各 5 个**）。**`list_exclude` 改成自动探测**（缺省 `None` = 该模型的全部 `JsonText` 列名），保留显式覆盖参数。**要有一条测试遍历 23 个资源、断言 list 响应里一个 `JsonText` 列都不出现、read-one 响应里全部出现。**
- **P3-B4**：`_child_tables(model)` 要遍历 `Base.metadata.tables` 找入向外键，**且必须排除 `ondelete` 为 `SET NULL` / `CASCADE` 的 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`，**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**。要有一条测试钉住这个排除。
- **P3-B5**：**5 张表的唯一约束是无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，`UniqueConstraint.name is None`）→ **409 的消息引用列名、不引用约束名**。要有一条测试断言消息里含列名、**不含字面 `"None"`**。
- **P3-B6**：`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 住在 **`app/main.py`**，不在 `deps.py`（计划正文的出处已更正）。**工厂不碰这两个常量。**
- **P3-B7**：`repo.py` **只有 `upsert` 与 `delete_by_batch` 两个公开函数**，没有 `get_or_404`。read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要给 `repo.py` 加新函数。**
- **P3-B8**：`alert` 与 `notification` 的 `on_delete` **改成 `forbid`**（不是 `restrict`）——它们是 RCT 的审计记录与学生的消息历史，`restrict` 意味着「没有子行时可以从 API 删掉」，那会静默抹掉研究数据。**读写矩阵的三个计数随之变成：可写 8 / 只读 15；`restrict` 11 / `forbid` 11 / `cascade` 1**，那条遍历 `RESOURCES` 计数的测试要用新数。

## 0.3 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（四格应逐字不变）；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01/02 与本计划 Task 1/2 的 845 条既有测试一条都不许退步**。
- **不做变异**（Ruling 1：变异只在 Task 6 要求）。**但 Task 2 的实现者自己加了一条变异自证「新守卫有牙」，控制者采纳并鼓励**——你若能廉价地自证某条新守卫不是恒绿的，就做了并写进报告。
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。Plan 02 的实现者顶回控制者 **25 次、25 次都对**，Plan 03 已顶回 **6 次、6 次都对**（累计 **31/31**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定。**

## 0.4 纪律

- **分支** `feature/plan-03-feedback-alert-crud-api`。**不要 push、不要切分支、不要碰 main。**
- **禁区**：`backend/pe.db`（**不得存在**）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **数列/字段/成员一律用运行时口径**，**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`**（#89 扩写）；**数「一个名字有几份定义」用 AST，不用文本命中数**（#89 再扩写，Plan 03 控制者错误 #6）。
- **断言「A 等于/不等于 B」时，若任一侧经过序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99）。
- **用哨兵值代替 NULL 之前，必须先确认那一列不是外键**（硬规矩 #101，Task 2 的顶回 1）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件。

## 0.5 commit 与报告

**建议 3–4 个 commit**：① `crud.py` 工厂 + 它的测试（用 `semester` 与 `stratification_result` 两个资源跑通五端点）；② 4 个 schema 模块；③ `catalog.py` 的 23 行 `RESOURCES` + 遍历型测试；④ 收尾（全量 + 覆盖率 + 扫描面）。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-3-report.md`（**python 写**）。至少 8 节：① 环境与基线复现；② `build_crud_router` 的最终签名与 `CrudSchemas` 的字段；③ **`RESOURCES` 的 23 行逐个落地情况**（每行给：路径 / 模型类 / import 路径 / `natural_key` / `writable` / `on_delete` / `list_exclude`）；④ `_child_tables` 的实现与「排除 SET NULL/CASCADE」那条测试；⑤ 三个计数（可写 8 / 只读 15；restrict 11 / forbid 11 / cascade 1）的实测复核；⑥ 待清扫 / 关切 / **没按派单做的地方（0 处也要写）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑦ 最终验收（passed 数 845 → ?、覆盖率四格应不变、表数 25、扫描面 38 → ?、三个指纹、`git diff <base> HEAD -- backend/data` 为空、`pe.db` 不存在）；⑧ commit sha。

## 0.6 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格（应逐字不变）/ 扫描面 38 → ? / `build_crud_router` 的最终签名 / 23 个资源是否全部落地（几个可写、几个只读、restrict/forbid/cascade 各几个）/ 11 个子模块 import 是否全部走对 / `_child_tables` 排除 SET NULL 的那条测试名 / 409 消息不含字面 `"None"` 的那条测试名 / `list_exclude` 自动探测的那条遍历测试名 / 三个指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

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

## Task 3: 泛型 CRUD 工厂 + 组织与身份 + 学期节点数据的只读/读写路由

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `8d8d3b3`，取证脚本 `t3_probes/_preflight.py`）

**测试基线**：`845 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**；扫描面 **38**。

| # | 级别 | 事实（全部实测，运行时口径） | 更正 |
|---|---|---|---|
| **P3-B1** | **Critical** | **23 个资源里有 11 个的模型类不在 `app.db.models` 的公有导入面上**（Ruling 97：Plan 02 的 4 个 + Plan 03 的 7 个表类**刻意不重导出**）。实测：`exercise` / `prescription_template` / `prescription` / `weekly_adjustment` 住 `app.db.models.prescription`；`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 住 `app.db.models.feedback`。**计划 Task 3 的正文一个字都没提这件事** —— 照它的字面写 `model=models.Prescription` 会得到 **11 个 `AttributeError`**。 | **下面那张 23 行的表逐个给出 import 路径**，`RESOURCES` 照它写。**⚠️ 这与 Plan 02 的 P6-A8 / Plan 03 Task 2 的顶回 1 是同一族**：Ruling 97 这条纪律已经传导过两次，**而控制者第三次写计划时又忘了它** → 见下方硬规矩 #102 |
| **P3-B2** | **Important** | **3 个资源没有唯一约束**：`course_section`、`fitness_test_batch`、`notification`。故 `test_create_with_a_duplicate_natural_key_is_409` **对它们写不出来**，`repo.upsert(session, model, key_fields, values)` 的 `key_fields` **也没有东西可填**。 | `build_crud_router` 加一个参数 **`natural_key: tuple[str, ...] | None`**：非空 → POST 走 `repo.upsert`（撞键 → **409**）；`None` → POST 走**裸 `session.add`**（**没有 409 这一档**，因为结构上不可能撞）。**⚠️ 那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的资源写一条反向测试**（`test_a_resource_without_a_natural_key_never_returns_409`）—— 否则下一个人会以为 409 是普适的 |
| **P3-B3** | **Important** | **`JsonText` 列实测共 21 个，分布在 8 张表**（`interest_survey` 2、`derived_metrics` 3、`stratification_result` 1、`exercise` 1、`prescription` **5**、`mini_test` 1、`alert` 1、`weekly_class_report` **5**）。计划要求 `list_exclude: tuple[str, ...] = ()` 由调用方**逐个手写** —— 23 行里手抄 21 个列名，**抄漏一个就是一次全表 JSON 拉取**（Plan 02 Task 7 的性能回归正是「大 JSON 列 eager 加载」，`elapsed` 一度到 115 s）。 | **`list_exclude` 改成自动探测**：缺省 = `[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`，**并保留一个显式覆盖参数**（给「list 端点确实要返回某个小 JSON 列」的例外）。**理由：自动探测不会抄漏，而「多排除一个列」的后果（read-one 里还能拿到）远轻于「少排除一个列」（性能回归且没人看得见）。** ⚠️ 要有一条测试遍历 23 个资源、断言 **list 响应里一个 `JsonText` 列都不出现**、而 read-one 响应里全部出现 |
| **P3-B4** | **Important** | `on_delete="restrict"` 要「点名是哪张子表挡住的」，而**子表清单不在模型上**：实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。 | **`crud.py` 里写一个 `_child_tables(model) -> list[tuple[str, str]]`**（返回 `(子表名, 子表的FK列名)`），实现是遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`。**⚠️ 它必须排除 `ondelete` 为 `SET NULL` 或 `CASCADE` 的那些 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`（Task 2 的顶回 3 加的），**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己会 SET NULL）。要有一条测试钉住这个排除 |
| **P3-B5** | **Important** | 5 张表的唯一约束是**无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）。 | **409 的消息里不得引用约束名**（它是 `None`，会渲染成 `"None"`）→ 引用**列名**。**并要有一条测试断言 409 的 `message` 里含列名、不含字面 `"None"`** —— 否则前端会把 `None` 显示给教师看 |
| P3-B6 | Minor | 实测 `app/api/deps.py` 的公开面 = `Engine` / `Page` / `Student` / `current_student` / `current_teacher` / `get_db` / `require_scope`（**没有模块级大写常量**，`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 实测住在 `app/main.py`）；`app/api/errors.py` 的公开面 = `error_response(status_code, code, message, detail=None, headers=None)` 与 `register_error_handlers(app)`。 | 计划正文写「`deps.py` 的 `DB_URL_ENV_VAR`」是错的 —— **它们在 `main.py`**。**工厂不碰这两个常量**（它只拿 `Session`），故本条只是更正出处、不改设计 |
| P3-B7 | Minor | 实测 `repo.py` 的公开函数只有两个：`upsert(session, model, key_fields: Sequence[str], values: dict) -> Any` 与 `delete_by_batch(session, model, batch_id: int) -> int`。**没有 `get_or_404` 之类的读取助手。** | 工厂的 read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要为此给 `repo.py` 加新函数**（`repo.py` 是 Plan 01 的模块，加函数要同步它的公开面基线；而 `session.get` 是 SQLAlchemy 的原生 API，不需要包装） |
| P3-B8 | Minor | **`alert` 与 `notification` 的 `on_delete` 定成 `restrict` 是错的**：`alert` 是「哪个学生被标记过」的**审计记录**（RCT 的过程数据），`notification` 是**学生看到的消息历史**。`restrict` 意味着「没有子行时可以从 API 删掉」—— 而那会静默抹掉研究数据。 | **两个都改成 `forbid`（405）**。理由与 `stratification_result` 一样：**删它们的正确方式是重放（`_replay_cleanup` 按 `batch_id` 删），不是从 API 单点删。** ⚠️ 这一改让读写矩阵的三个计数变成：**可写 8 / 只读 15；`restrict` 11 / `forbid` 11 / `cascade` 1**（原为 12/10/1）。**那条遍历 `RESOURCES` 计数的测试要用新数** |


**Files:** Create `backend/app/api/crud.py`、`backend/app/api/schemas/{__init__,organisation,assessment,derived,prescription}.py`、`backend/app/api/routers/{__init__,catalog}.py`、`backend/tests/api/test_crud.py`

**Interfaces:**
- Consumes: Task 1 的 `get_db` / `Page` / `current_student` / `current_teacher` / `require_scope` / `errors` 的映射（**⚠️ P3-B6 更正出处**：实测 `app/api/deps.py` 的公开面是 `Engine` / `Page` / `Student` / `current_student` / `current_teacher` / `get_db` / `require_scope`，**没有模块级大写常量**——`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 住在 **`app/main.py`**。**工厂不碰这两个常量**（它只拿 `Session`），故本条只是更正出处、不改设计）
- Produces:
  - `build_crud_router(*, model, schemas: CrudSchemas, path: str, tags: list[str], pk: str = "id", order_by: str = "id", readable: bool = True, writable: bool = True, **`on_delete: str = "restrict"`（取值 `"restrict"` / `"cascade"` / `"forbid"`；`"forbid"` → `DELETE` 返回 405，故不需要另一个 `deletable` 布尔）**、**`natural_key: tuple[str, ...] | None`（P3-B2：非空 → POST 走 `repo.upsert`、撞键 409；`None` → POST 走裸 `session.add`，结构上不可能撞键，故没有 409 这一档）**、**`list_exclude: tuple[str, ...] | None = None`（P3-B3：`None` 表示**自动探测**——`[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`；显式传元组则覆盖探测结果）**、`scope: ScopeFn | None = None`) -> APIRouter`
  - `CrudSchemas`（frozen dataclass）：`read: type[BaseModel]` / `create: type[BaseModel] | None` / `update: type[BaseModel] | None`
  - `ScopeFn = Callable[[Session, Any, int | None, str | None], None]`（拿到 ORM 行与两个身份，不匹配就抛 `HTTPException(403)`）
  - 五个端点：`GET {path}`（分页 + 排序，返回 `{"items": [...], "total": int, "limit": int, "offset": int}`）、`POST {path}`（`201` + `Location` 头）、`GET {path}/{pk}`、`PATCH {path}/{pk}`（**部分更新**，只改传了的字段）、`DELETE {path}/{pk}`（`204`）
  - `catalog.py` 的 **`RESOURCES` 列表**：23 个资源，每个是一行 `build_crud_router(...)` 的调用参数

**决定：**
- **为什么用泛型工厂而不是 23 个手写路由**：用户裁定「能运行起来的原型系统就好」+「需要能够进行增删改查」。手写 23 套会产生 23 份**互相不一致**的分页/错误/校验行为，而前端（Plan 04）要为每一种不一致写一个特例。**一致的行为是原型的资产，不是它的负债。** 特例（三源采集、教师覆盖、预警处理、大屏聚合）**不走工厂**，单独手写。
- **`on_delete` 的三种取值（Review Focus 第 4 条）**：
  - `"restrict"`（**缺省**）：有子行就 **409**，消息里点名是哪张子表、几行。**这是缺省**，因为静默级联删会带走不可复现的历史（`prescription` 被删 → `weekly_adjustment` 与 `alert` 的关联消失，而 spec §4.3 的可追溯性要求「历史行指向的东西还在」）。
  - `"cascade"`：显式声明后才级联。**只给两处用**：`class_session` → `rpe_record`（课次取消，快评记录无意义）、`prescription` → `weekly_adjustment`（处方作废，微调记录随之作废）。⚠️ **Plan 02 的 P7-A4 已经踩过这个坑**：SQLite 在 `PRAGMA foreign_keys=ON` 下**先删父表会当场 FK 违例**，故级联必须**子表先删**。
  - `"forbid"`：**根本不许删**（`semester` / `student` / `fitness_test_result` / `stratification_result` / `prescription` 之外的派生数据）→ **405**。理由：这些是**批处理产物**，删它们的正确方式是重放（`_replay_cleanup` 按 `batch_id` 删），而不是从 API 单点删。
  - **23 个资源逐个声明 `on_delete`，并在 `RESOURCES` 列表的注释里写明理由**。⚠️ 要有一条测试遍历 `RESOURCES`，断言「每个资源都显式写了 `on_delete`」（缺省值不算显式）—— 否则加第 24 个资源时会静默落到 `restrict`。
- **只读资源**：**15 个**（见下面 S4 的读写矩阵）——`percentile_snapshot` / `derived_metrics` / `stratification_result` / `weekly_class_report` 四个是批处理产物，`fitness_test_result` 是乐跑投影，`exercise` / `prescription_template` 是参考数据的投影，`prescription` / `weekly_adjustment` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` 七个**有专门的特例写入口**（Task 4/5/7/8），故一律 `writable=False`。`exercise` / `prescription_template` 两个是**参考数据**，**`writable=False`、`on_delete="forbid"`（只读）**。理由：spec §4.4 逐字写着「`exercise_equivalence`（动作等价映射）与 `alert_rules`（预警阈值）为 `data/` 下的**静态 YAML + 版本号**，不入库……**这是体育专家维护的知识资产而非业务数据，改阈值应走版本控制与评审，不应在运行时改数据库**」，而 `exercise` 与 `prescription_template` 两张表是那两个 YAML 的**投影**（Plan 02 的 `sync_exercises` / `sync_templates`）——**开放 API 写它们会让「YAML 是唯一所有者」这句话变成假的**，因为下一次 sync 会把 API 的改动静默覆盖掉。**教师端要改动作库或模板的审校状态，请改 YAML 走版本控制。**⚠️ 这也顺手解决了 Plan 02 留给 Plan 03 的第 8 条（`sync_*` 没有生产调用方）：**由 `POST /api/pipeline/run-daily` 调一次 `sync_exercises` + `sync_templates`（两者都幂等）**，于是「YAML → 表」这条投影有了生产入口，而反向的「表 → YAML」刻意不存在。
- **`prescription` 的写口径**：`writable=True` **但只允许改 `status` 与 `teacher_overrides` 两列**（教师覆盖走 Task 4 的特例端点；直接 PATCH 整行会让 `training_package` 与 `assembly_snapshot` 失去一致性）。**决定：`prescription` 走 `writable=False`，教师覆盖与状态变更全部走 Task 4 的特例端点。** 这比「允许 PATCH 但只挑两列」简单，而原型不需要那个灵活度。
- **分页上界 200**：`limit > 200` → **422**。理由：`fitness_test_result` 有 21 列 × 上万行，不设上界会让一次 `GET` 拖垮内存（Plan 02 Task 7 的性能回归就是两处全表扫描 + 大 JSON 列 eager 加载造成的，`elapsed` 一度到 115 s）。**大 JSON 列（`training_package` / `assembly_snapshot` / `input_snapshot`）在 list 端点里默认不返回**，只在 `GET {path}/{pk}` 里返回 —— 用一个 `list_exclude: tuple[str, ...]` 参数声明。
- **⚠️ P3-B4：`on_delete="restrict"` 要「点名是哪张子表挡住的」，而子表清单不在模型上。** 实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。**`crud.py` 里写一个 `_child_tables(model) -> list[tuple[str, str]]`**（返回 `(子表名, 子表的FK列名)`），实现是遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`。**⚠️ 它必须排除 `ondelete` 为 `SET NULL` 或 `CASCADE` 的那些 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`（Task 2 的顶回 3 加的），**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己会 SET NULL）。要有一条测试钉住这个排除。
- **⚠️ P3-B5：5 张表的唯一约束是无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）→ **409 的消息里不得引用约束名**（它是 `None`，会渲染成字面 `"None"`），**引用列名**。要有一条测试断言 409 的 `message` 里含列名、**不含字面 `"None"`**（否则前端会把 `None` 显示给教师看）。
- **⚠️ P3-B7：`repo.py` 只有 `upsert` 与 `delete_by_batch` 两个公开函数，没有 `get_or_404` 之类的读取助手。** read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要为此给 `repo.py` 加新函数**（它是 Plan 01 的模块，加函数要同步它的公开面基线；而 `session.get` 是 SQLAlchemy 的原生 API，不需要包装）。
- **`PATCH` 的部分更新语义**：只改**请求体里出现的**键（用 `model_dump(exclude_unset=True)`）。**`null` 与「没传」必须可区分**——`training_log.duration_min` 可以从 `12.0` 改成 `null`（缺测），而「没传 `duration_min`」不该把它清掉。
- **不做的事**：不做软删除、不做审计日志、不做 ETag / `If-Match`、不做批量端点（除 Task 5 的 `mini_test` 批量录入，那是 spec §8.1 明写的）。

- [ ] **Step 1: 写失败测试**（`tests/api/test_crud.py`）

用 `semester`（最简单的可写资源）与 `stratification_result`（只读资源）各跑一遍五端点：
- `test_list_returns_items_total_limit_offset` / `test_limit_over_200_is_422` / `test_offset_beyond_total_returns_empty_items`
- `test_create_returns_201_with_a_location_header` / `test_create_with_a_duplicate_natural_key_is_409`
- `test_read_one_returns_the_row` / `test_read_a_missing_pk_is_404`
- `test_patch_changes_only_the_keys_present`（**Review Focus：`null` 与「没传」可区分**）
- `test_delete_returns_204_and_the_row_is_gone`
- `test_a_readonly_resource_rejects_post_patch_delete_with_405`
- `test_list_omits_the_big_json_columns_but_read_one_includes_them`
- `test_every_resource_declares_on_delete_explicitly`（遍历 `RESOURCES`）
- `test_on_delete_restrict_names_the_blocking_child_table`（409 的消息里有子表名与行数）
- `test_on_delete_cascade_deletes_children_first`（**P7-A4 的同一条纪律**：`class_session` 删掉后 `rpe_record` 也空，且没抛 FK 错）
- `test_a_domain_value_error_becomes_422_with_its_message` / `test_an_integrity_error_becomes_409` / `test_an_unhandled_error_becomes_500_without_a_stack_trace`

- [ ] **Step 2–6: 跑失败 → 实现工厂 → 填 `RESOURCES` 的 23 行 → 跑通 → 全量 → Commit**

⚠️ **23 个资源的名字与路径逐字钉死**（Plan 04 的前端要照着它写），**全部挂在 `/api/` 下**（如 `/api/course-sections`）。**连字符不是下划线**（URL 惯例），但 schema 的字段名保持**下划线**（与 DB 列名一致）—— ⚠️ 这个对照要写进 `crud.py` 的 docstring。

**⚠️ P3-B1 的裁定：23 个资源的 import 路径、自然键与 `JsonText` 列逐个钉死**（**11 个不在 `models` 的公有面上**，照 `models.X` 写会得到 11 个 `AttributeError`）：

| 资源 | 表 | 模型类 | **import 路径（⚠️ P3-B1：11 个不在 `models` 的公有面上）** | 列数 | 自然键（唯一约束的列） | `JsonText` 列（`list_exclude` 的缺省值） |
|---|---|---|---|---|---|---|
| `semesters` | `semester` | `Semester` | `app.db.models`（**或** `…organisation`） | 6 | `name`（约束**无名**） | — |
| `teachers` | `teacher` | `Teacher` | `app.db.models` | 3 | `staff_no`（无名） | — |
| `students` | `student` | `Student` | `app.db.models` | 7 | `student_no`（无名） | — |
| `course-sections` | `course_section` | `CourseSection` | `app.db.models` | 6 | **⚠️ 无唯一约束** | — |
| `enrollments` | `enrollment` | `Enrollment` | `app.db.models` | 4 | `semester_id, student_id, course_section_id` | — |
| `fitness-test-batches` | `fitness_test_batch` | `FitnessTestBatch` | `app.db.models` | 6 | **⚠️ 无唯一约束** | — |
| `fitness-test-results` | `fitness_test_result` | `FitnessTestResult` | `app.db.models` | **21** | `test_batch_id, student_id` | — |
| `body-compositions` | `body_composition` | `BodyComposition` | `app.db.models` | 8 | `student_id, measured_on` | — |
| `interest-surveys` | `interest_survey` | `InterestSurvey` | `app.db.models` | 7 | `student_id, semester_id, filled_on` | `dimensions`, `raw_answers` |
| `percentile-snapshots` | `percentile_snapshot` | `PercentileSnapshot` | `app.db.models` | 14 | `semester_id, computed_on, item, sex, age_group` | — |
| `derived-metrics` | `derived_metrics` | `DerivedMetrics` | `app.db.models` | 11 | `student_id, computed_on` | `annual_change`, `weaknesses`, `body_comp_reasons` |
| `stratification-results` | `stratification_result` | `StratificationResult` | `app.db.models` | 10 | `student_id, computed_on` | `input_snapshot` |
| `exercises` | `exercise` | `Exercise` | **`app.db.models.prescription`** | 7 | `ref`（无名） | `targets` |
| `prescription-templates` | `prescription_template` | `PrescriptionTemplate` | **`app.db.models.prescription`** | 10 | `template_ref`（无名） | — |
| `prescriptions` | `prescription` | `Prescription` | **`app.db.models.prescription`** | 16 | `student_id, generated_on` | **5 个**：`training_package`, `assembly_snapshot`, `safety_substitutions`, `teacher_overrides`, `trigger_reasons` |
| `weekly-adjustments` | `weekly_adjustment` | `WeeklyAdjustment` | **`app.db.models.prescription`** | 8 | `prescription_id, week, reason, source` | — |
| `class-sessions` | `class_session` | `ClassSession` | **`app.db.models.feedback`** | 7 | `course_section_id, session_date, period` | — |
| `rpe-records` | `rpe_record` | `RpeRecord` | **`app.db.models.feedback`** | 6 | `class_session_id, student_id` | — |
| `training-logs` | `training_log` | `TrainingLog` | **`app.db.models.feedback`** | 10 | `student_id, log_date` | — |
| `mini-tests` | `mini_test` | `MiniTest` | **`app.db.models.feedback`** | 10 | `student_id, semester_id, week` | `item_combo` |
| `alerts` | `alert` | `Alert` | **`app.db.models.feedback`** | 14 | `rule_id, subject_key, semester_id, window_key` | `trigger_snapshot` |
| `notifications` | `notification` | `Notification` | **`app.db.models.feedback`** | 10 | **⚠️ 无唯一约束** | — |
| `weekly-class-reports` | `weekly_class_report` | `WeeklyClassReport` | **`app.db.models.feedback`** | 12 | `course_section_id, semester_id, week` | **5 个**：`layer_distribution`, `rpe_summary`, `checkin_rate_by_layer`, `progress_board`, `alert_summary` |


**⚠️ S4 的裁定：23 个资源的读写矩阵逐个钉死**（原正文只给了「只读资源是哪四个」，而同一个 `POST` 路径会被泛型 CRUD 与 Task 5/7 的特例端点**同时注册**——FastAPI 按 `include_router` 的顺序取先匹配的，于是哪一个生效变成一个没人看得见的耦合）：

| 资源 | 路径 | `writable` | `on_delete` | 为什么 |
|---|---|---|---|---|
| `semesters` | `/api/semesters` | ✅ | `forbid` | 全库的时间轴锚点，删它没有安全语义 |
| `teachers` | `/api/teachers` | ✅ | `restrict` | 有 `course_section.teacher_id` 子行 |
| `students` | `/api/students` | ✅ | `restrict` | 有大量子行；**删一个学生要走学籍流程，不是 API 单点删** |
| `course-sections` | `/api/course-sections` | ✅ | `restrict` | 有 `enrollment` 子行 |
| `enrollments` | `/api/enrollments` | ✅ | `restrict` | 关联行，无子行但删它会让名单悄悄少人 |
| `fitness-test-batches` | `/api/fitness-test-batches` | ✅ | `restrict` | 有 `fitness_test_result` 子行 |
| `fitness-test-results` | `/api/fitness-test-results` | ❌ | `forbid` | **乐跑投影 + 批处理输入**，改它等于改原始数据 |
| `body-compositions` | `/api/body-compositions` | ✅ | `restrict` | InBody 是人工录入的，教师要能改错 |
| `interest-surveys` | `/api/interest-surveys` | ✅ | `restrict` | 同上 |
| `percentile-snapshots` | `/api/percentile-snapshots` | ❌ | `forbid` | **批处理产物**，删它的正确方式是重放 |
| `derived-metrics` | `/api/derived-metrics` | ❌ | `forbid` | 同上 |
| `stratification-results` | `/api/stratification-results` | ❌ | `forbid` | 同上；**spec §4.3 的可追溯性核心** |
| `exercises` | `/api/exercises` | ❌ | `forbid` | **参考数据**：`exercises.yaml` 是唯一所有者，表是投影（见上面那条决定） |
| `prescription-templates` | `/api/prescription-templates` | ❌ | `forbid` | 同上（18 套 YAML 是唯一所有者） |
| `prescriptions` | `/api/prescriptions` | ❌ | `restrict` | **教师覆盖与状态变更走 Task 4 的特例端点**；直接 PATCH 整行会让 `training_package` 与 `assembly_snapshot` 失去一致性 |
| `weekly-adjustments` | `/api/weekly-adjustments` | ❌ | `restrict` | **`auto` 来源由 Task 7 的 `alert_stage` 写、`teacher` 来源由 Task 4 的覆盖端点写**；开放 CRUD 写它会绕过 `WeeklyFactor` 的 `(0, 2]` 校验（Plan 02 留给 Plan 03 的第 4 条） |
| `class-sessions` | `/api/class-sessions` | ✅ | **`cascade`** | 教师建课次、取消课次；**课次取消则 `rpe_record` 无意义**（`cascade` 两处之一） |
| `rpe-records` | `/api/rpe-records` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/rpe-records`**（要校验 `rpe_token`、服务端填 `submitted_at`） |
| `training-logs` | `/api/training-logs` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/training-logs`**（`late` 必须服务端算——它是「完成率是 RCT 关键过程指标，必须严格」的那一半） |
| `mini-tests` | `/api/mini-tests` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/mini-tests/batch`**（标准化得分要班内百分位反查，客户端算不出来） |
| `alerts` | `/api/alerts` | ❌ | **`forbid`（P3-B8 更正，原为 `restrict`）** | **由 `alert_stage` 生成、由 Task 7 的 `POST /api/alerts/{id}/handle` 处置**；开放 CRUD 写它会绕过 `window_key` 去重。**改 `forbid` 的理由：它是「哪个学生被标记过」的审计记录（RCT 的过程数据），`restrict` 意味着「没有子行时可以从 API 删掉」，而那会静默抹掉研究数据** |
| `notifications` | `/api/notifications` | ❌ | **`forbid`（P3-B8 更正，原为 `restrict`）** | **由 `InAppChannel` 生成**；「已读」走 Task 8 的 `POST /api/notifications/{id}/read`。**改 `forbid` 的理由同上：它是学生看到的消息历史** |
| `weekly-class-reports` | `/api/weekly-class-reports` | ❌ | `forbid` | **批处理产物**（Task 8） |

**合计：可写 8 个、只读 15 个；`on_delete` 是 `restrict` **11** 个 / `forbid` **11** 个 / `cascade` **1** 个**（**P3-B8 更正**：原为 12/10/1，`alert` 与 `notification` 从 `restrict` 挪到 `forbid`）。⚠️ **另一处 `cascade`**：`prescriptions` → `weekly_adjustment`（处方作废则微调记录随之作废），但 `prescriptions` 的 `on_delete` 是 `restrict`（不许从 API 删处方）→ **那个 `cascade` 由 Task 4 的「处方被替换」路径内部使用，不经过 `DELETE` 端点**。故 `build_crud_router` 的 `on_delete="cascade"` **只有 `class-sessions` 一个用户**。
⚠️ **这三个数字（8 / 15、12 / 10 / 1）要有一条测试钉住**（遍历 `RESOURCES` 计数），否则加第 24 个资源时会静默改变比例而没人知道。**数字自己数、不要照抄本行**（硬规矩 #44/#89）。

---
