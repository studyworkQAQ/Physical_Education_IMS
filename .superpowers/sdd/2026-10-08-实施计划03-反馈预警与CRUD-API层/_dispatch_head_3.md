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

