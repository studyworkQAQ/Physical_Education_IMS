# Task 4 简报 — 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 4 全节（含预检更正 P4-A1..A7）**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **876 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `875 passed, 1 skipped`）。**本 Task 不加 domain 代码，四格应逐字不变。**
**表数 25**（`prescription` **16 列**）；`_MODELS_PUBLIC_BASELINE` **33（不动）**；扫描面 **49**；**HTTP 端点 47 个在线**。
**环境**：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、FastAPI **0.141.1**、Pydantic **2.13.5**、httpx 0.28.1。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

**⚠️ 控制者已经起过真实服务并用 httpx 打了一整圈 CRUD**（取证脚本 `t3_probes/_live_smoke.py`），全部符合预期：`POST` → 201 + `Location`、撞自然键 → 409 且消息点名键列、`PATCH` 部分更新且 `null` 与「没传」可区分、`forbid` → 405、只读资源 → 405、错误形状统一。**你不需要重跑这一圈**，但**你加的端点要符合同一套约定**（统一错误形状、`Location` 头、分页形状）。

**⚠️ 用户 2026-10-08 的原话是「要确保后端和前端能够对接的上」** —— 本 Task 的 P4-A5 与 P4-A6 两条就是这句话的落点，**不是可选的美化**。

## 0.1 ⚠️ 本 Task 的 1 条 Critical

**P4-A1：`WeeklySheet` 不能直接 JSON 化。** 控制者实测 `json.dumps(dataclasses.asdict(sheet))` 抛 **`TypeError: cannot pickle 'mappingproxy' object`**（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它）。**带不带 `default=str` 都失败**——`default` 只在「未知类型」时被调用，而 `asdict` 在**到达 json 之前**就炸了。

**处置**：不许用 `dataclasses.asdict`。**Plan 02 已经解决过同一个问题**——`app.pipeline.prescription_stage.training_package_payload(pkg) -> dict`（**已在 `__all__` 里**，实测签名就是这一个参数）就是「`TrainingPackage` → 可 JSON 的 dict」的投影，它已经处理了只读映射、三层嵌套与 `hr_zone` 的元组→列表。
**你要做的**：把它的 **block 级投影提成一个模块级函数**（如 `_block_payload(block) -> dict`），**weekly-sheet 与 training-package 两处共用**。
⚠️ **是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，**前端在学生端看到的 block 与教师端看到的就不是同一个形状了**。
⚠️ **要有一条测试钉住「weekly-sheet 里的 block 与 `training_package_payload` 里的 block 逐字段同形」**（同一个包、同一周，比对两边的 block dict）——**这条是两个投影不漂移的唯一守卫**。

## 0.2 其余 6 条（简报的预检总表里有完整实测依据）

- **P4-A2**：**`weekly_factors_of` 已经存在**（Plan 02 Task 8 交付），实测签名 `weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，在 `prescription_stage.__all__` 里。`WeeklyFactor` 的 4 个字段 = `week:int / factor:float / reason:str / source:str`。**直接调用，不要重写。**
- **P4-A3**：**`OverrideRecord` 的 7 个字段全部无缺省**（`kind` / `target` / `old_value` / `new_value` / `reason` / `teacher_staff_no` / `applied_at`）。**请求模型必须是 5 字段的另一个 Pydantic 类**，`teacher_staff_no` 从身份头填、`applied_at` 从服务端时钟填（**让客户端传等于让它能冒充别的教师、还能伪造时间**）。`OverrideKind` 的 5 个值实测 = `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`（**下划线不是连字符**）→ **值域直接引 `OverrideKind`，不要在 schema 里抄第二份字符串**。⚠️ **调 `apply_overrides` 必须传 `exercises=`**（实测签名 `apply_overrides(pkg, records, *, exercises)`，关键字必填）—— 否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL，那是 Plan 02 顶回 2 逐字说的「**一个看起来正常的谎**」。
- **P4-A4**：`prescription.teacher_overrides` 是 **`TEXT NOT NULL`** 的 `JsonText` → 「追加一条覆盖」= **读 JSON 列表 → append → 写回**，不是 INSERT；空列表写 `[]` 不写 `NULL`。**顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）→ **不要按 `applied_at` 重排序**。
- **P4-A5（对接缺口 1）**：实测 `openapi()["components"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、47 个路径里**声明过的 header 参数为空**。**把 `X-Student-Id` / `X-Teacher-Staff-No` 注册成 OpenAPI 的 `apiKey` securityScheme**（`in: header`），需要它们的端点挂 `dependencies=[Security(...)]`。**不注册的后果：Swagger UI 上没有地方能填、生成的 TS 客户端也不知道要发** → 前端一接就撞 401 且不知道为什么。
- **P4-A6（对接缺口 3）**：实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**。**给 `build_crud_router` 加 `pk_alias: str | None = None`**：`None` → 自动取**资源路径的单数 + 下划线**（`semesters`→`semester_id`、`course-sections`→`course_section_id`、`fitness-test-results`→`fitness_test_result_id`），显式传则覆盖。**纯 OpenAPI 层的改名，不动 DB、不动路由匹配。** ⚠️ **23 个 detail 路径的 URL 模板会变，Task 3 那条遍历型守卫测试要跟着改。**
- **P4-A7（对接缺口 2，本 Task 不修、只记录）**：CORS 是 `allow_origins=["*"]` 且**没有 `allow_credentials`**（浏览器规范禁止两者并存）。**Plan 04 的前端不得用 cookie / `fetch(..., {credentials:'include'})`**，身份只能走请求头。控制者已把这条写进计划的「计划边界说明」。

## 0.3 你要交付什么

**Create**：`backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`
**Modify**：`backend/app/api/schemas/prescription.py`（**⚠️ 它由 Task 3 创建，本 Task 只补特例模型，不要覆盖**）、`backend/app/api/routers/__init__.py`（**⚠️ 新 router 挂这里，不是 `main.py`**——`main.py` 的注释逐字写着「只 include 这**一个**汇总路由：Task 5/7/8/9 各加一个 router 时改的是 `app/api/routers/__init__.py`，不是本文件（本文件压着 `pe.db` 禁区那条纪律）」）、**`backend/app/api/crud.py`（P4-A6：加 `pk_alias`）**、**`backend/app/api/deps.py`（P4-A5：securityScheme）**、**`backend/app/pipeline/prescription_stage.py`（P4-A1：提取 block 级投影）**、`backend/tests/api/test_crud.py`（P4-A6 的连带）

**四个端点**（简报的 Task 4 节有完整口径）：
- `GET /api/students/{student_id}/prescriptions/current`
- `GET /api/students/{student_id}/weekly-sheet?as_of=YYYY-MM-DD`
- `POST /api/prescriptions/{id}/overrides`
- `POST /api/prescriptions/{id}/regenerate`

**⚠️ 必须传导的 Plan 02 结论（简报的 Task 4 节逐条列了 6 条，这里点最容易漏的 3 条）**：
1. **`paused=True` 时 `sessions` 原样保留**（P8-A3）→ 前端靠 `paused` 字段决定渲染什么，**不要在后端把 `sessions` 清空**。「暂停」与「本周量为 0」是两件不同的事。
2. **`WeeklySheet` 刻意不提供跨单位的周总量汇总**（P8-A1）→ **API 也不要加**。`volume_unit` 值域 `{min, reps, unspecified}`，相加就是 Plan 02 Task 5 的 F1-1 那个「混合量纲 float」错误。**前端要显示总量就自己按单位分组显示。**
3. **`previous_had_overrides` 是「界面提示『该生上次存在人工覆盖』」的唯一载体**（P6-A2），**不是 `assembly_snapshot` 里的键**（往快照加键会让 Plan 02 钉死的「12 键 / +3 键」两条守卫变红）。**`POST .../regenerate` 的响应里要带这一列**，否则前端提示不出来。

## 0.4 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（四格应逐字不变）；单一所有者；断言两侧不同源；架构守卫全绿；**既有 876 条测试一条都不许退步**。
- **不做变异**（Ruling 1：变异只在 Task 6 要求）。**但 Task 2 与 Task 3 的实现者都自己加了变异自证「新守卫有牙」，控制者两次都采纳并鼓励**——你若能廉价自证某条新守卫不是恒绿的，就做了并写进报告。
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。Plan 02 顶回 **25/25**，Plan 03 已顶回 **14/14**（累计 **39/39**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定。**

## 0.5 纪律

- **禁区**：`backend/pe.db`（**不得存在**；`DEFAULT_DB_URL` 就指向它，手工起服务必须显式设 `PE_DB_URL`）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- ⚠️ **控制者现在有一个 uvicorn 进程跑在 `127.0.0.1:8000`（用 `pe_demo.db`）**。你要手工起服务的话**换一个端口**，别撞。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
- **数列/字段/成员一律用运行时口径**，**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`**（#89 扩写）；**数「一个名字有几份定义」用 AST**（#89 再扩写）；**一个探针里若有两种口径能回答同一个问题，以运行时那一种为准、另一种标注为不可用**（硬规矩 #103）。
- **断言「A 等于/不等于 B」时，若任一侧经过序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99）。
- **不要凭记忆构造 HTTP 请求的 payload**：先从 `/openapi.json` 读那个 schema 的 `required`（硬规矩 #89 的同族；控制者本次冒烟的第一版脚本就栽在这里，见账本控制者错误 #13）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件。

## 0.6 commit 与报告

**建议 3 个 commit**：① P4-A1 的投影提取 + P4-A6 的 `pk_alias` + P4-A5 的 securityScheme（三条都是「改既有代码」，先做完并让 876 条仍全绿）；② 四个特例端点 + 它们的测试；③ 收尾（全量 + 覆盖率 + 扫描面）。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-4-report.md`（**python 写**）。至少 8 节：① 环境与基线复现；② **P4-A1 的提取**（新函数名、两处调用点、那条「逐字段同形」的测试名）；③ **P4-A5/A6 的落地证据**（`/openapi.json` 里 `securitySchemes` 的内容、23 个 detail 路径的参数名 distinct 从 `['pk_value']` 变成什么）；④ 四个端点的最终路径/方法/请求响应形状；⑤ Plan 02 传导的 6 条逐条落地位置；⑥ 待清扫 / 关切 / **没按派单做的地方（0 处也要写）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑦ 最终验收（passed 数 876 → ?、覆盖率四格应不变、表数 25、扫描面 49 → ?、端点数 47 → ?、三个指纹、`git diff <base> HEAD -- backend/data` 为空、`pe.db` 不存在）；⑧ commit sha。

## 0.7 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格（应逐字不变）/ 扫描面与端点数的新值 / **P4-A1 提取出的函数名与那条同形测试的名字** / **`securitySchemes` 的最终内容** / **23 个 detail 路径参数名的新 distinct** / 四个端点的路径与方法 / Plan 02 传导的 6 条是否全部落地 / 三个指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

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

## Task 4: 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `e2a0803` + 一次**真实 HTTP 冒烟**，取证脚本 `t4_probes/_preflight.py` 与 `t3_probes/_live_smoke.py`）

**测试基线**：`876 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**（`prescription` **16 列**）；扫描面 **49**；**47 个 HTTP 端点已在线**（控制者起了 uvicorn、用 httpx 打了一整圈真实 CRUD）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P4-A1** | **Critical** | **`WeeklySheet` 不能直接 JSON 化**：`json.dumps(dataclasses.asdict(sheet))` 抛 **`TypeError: cannot pickle 'mappingproxy' object`**（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它）。**带不带 `default=str` 都失败**——`default` 只在「未知类型」时被调用，而 `asdict` 在**到达 json 之前**就炸了。 | **不许用 `dataclasses.asdict`。** ⚠️ **Plan 02 已经解决过同一个问题**：`app.pipeline.prescription_stage.training_package_payload(pkg) -> dict` 就是「`TrainingPackage` → 可 JSON 的 dict」的投影，且它已经在 `prescription_stage.__all__` 里。**Task 4 的 weekly-sheet 投影必须建立在它之上（单一所有者），不得另写一份平行的投影。** 具体口径见下方「P4-A1 的落地口径」 |
| **P4-A2** | Important | **`weekly_factors_of` 已经存在**（Plan 02 Task 8 交付）：实测签名 `weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，且在 `prescription_stage.__all__` 里。`WeeklyFactor` 的 4 个字段 = `week:int / factor:float / reason:str / source:str`。 | 计划 Task 8 说要「加 `weekly_factors_of`」是**过期的**（那是 Plan 02 的活，已交付）。**Task 4 直接调用它**，Task 8 只消费。**⚠️ 硬规矩 #91：派单里提到的每一条既有能力，先 `git grep` / `inspect.signature` 核实它存在** |
| **P4-A3** | Important | **`OverrideRecord` 的 7 个字段全部无缺省**：`kind: OverrideKind` / `target: str \| None` / `old_value: str` / `new_value: str` / `reason: str` / `teacher_staff_no: str` / `applied_at: dt.datetime`。`OverrideKind` 的 5 个值实测 = `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`（**下划线，不是连字符**）。`apply_overrides(pkg, records, *, exercises)` —— **`exercises` 是关键字必填**（Plan 02 的顶回 2）。 | **API 的请求模型必须是 5 个字段的另一个 Pydantic 类**（`kind` / `target` / `old_value` / `new_value` / `reason`），**`teacher_staff_no` 从身份头填、`applied_at` 从服务端时钟填**。⚠️ `kind` 的值域**直接引 `OverrideKind`**（`Literal` 或 Pydantic 的 enum 支持），**不要在 schema 里抄第二份字符串**（单一所有者）。⚠️ 调 `apply_overrides` 时**必须传 `exercises=`**，否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL —— 那是 Plan 02 顶回 2 逐字说的「一个看起来正常的谎」 |
| **P4-A4** | Important | `prescription` 实测 **16 列**，其中 `teacher_overrides` 是 **`TEXT NOT NULL`**（`JsonText`），`label_at_generation VARCHAR(20) NOT NULL` 也在（Plan 02 Task 7 fr1 加的）。 | 「追加一条覆盖」= **读 JSON 列表 → append → 写回**，而**不是** INSERT。**⚠️ 列是 NOT NULL**，故空列表要写成 `[]` 而不是 `NULL`。**顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）→ **不要按 `applied_at` 重排序** |
| **P4-A5** | Important | **前后端对接缺口 1**：实测 `openapi()["components"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、47 个路径里**声明过的 header 参数为空**。而 `X-Student-Id` / `X-Teacher-Staff-No` 是全部学生侧端点的必需头。 | **本 Task 建第一个 `scope` 端点时，把这两个头注册成 OpenAPI 的 `apiKey` securityScheme**（`in: header`），并在需要它们的端点上挂 `dependencies=[Security(...)]`。**理由：不注册的话 Swagger UI 上没有地方能填它们、生成的 TS 客户端也不知道要发** —— 前端一接就撞 401 且不知道为什么。**⚠️ 用户 2026-10-08 明确要求「要确保后端和前端能够对接的上」，这一条是它的落点** |
| **P4-A6** | Important | **前后端对接缺口 3**：实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**（`/api/semesters/{pk_value}`）。而 `build_crud_router` 的签名里**只有 `pk: str = 'id'`（DB 列名），没有给 OpenAPI 路径参数另起名的口子**。 | **给 `build_crud_router` 加一个 `pk_alias: str | None = None`**：`None` → 自动取**资源路径的单数 + 下划线**（`semesters` → `semester_id`、`course-sections` → `course_section_id`、`fitness-test-results` → `fitness_test_result_id`），显式传则覆盖。**理由：生成的 TS 客户端里到处是 `pkValue` 而不是 `semesterId`，前端读起来很难受；而这个改名是纯 OpenAPI 层的，不动 DB、不动路由匹配。** ⚠️ **改完 23 个 detail 路径的 URL 模板会变**（`{pk_value}` → `{semester_id}` 等），**那条遍历型守卫测试要跟着改** |
| **P4-A7** | Minor | **前后端对接缺口 2**：实测 CORS 是 `allow_origins=["*"]` / `allow_methods=["*"]` / `allow_headers=["*"]`，**没有 `allow_credentials`** → 预检响应里 `access-control-allow-credentials` 为 `None`。（`main.py` 的 docstring 已明写「上线前两者都要收紧」✓） | **这是浏览器规范的硬约束**（`allow_origins=["*"]` 与 `allow_credentials=True` 不能并存），原型阶段**不修**。**但必须写进 Plan 04 的约束**：**前端不得用 cookie / `fetch(..., {credentials:'include'})`，身份只能走请求头。** 已按硬规矩 #86 记进本计划的「计划边界说明」 |

**P4-A1 的落地口径**：
- `weekly-sheet` 端点返回的 JSON 形状 = `{"week": int, "factor": float, "reasons": [str], "sources": [str], "paused": bool, "sessions": [...]}`，其中 `sessions` 的每个 block **必须是 `training_package_payload` 产出的同一个形状**（含 `volume_unit` 与 `sessions_per_week`）。
- **做法**：先看 `training_package_payload(pkg)` 今天怎么把 `TrainingPackage` 投影成 dict（它已经处理了 `structure` 那个只读映射、`weeks`/`sessions`/`blocks` 三层、以及 `hr_zone` 的元组→列表）。**weekly-sheet 的投影 = 复用它的 block 级投影 + 换掉最外层**（`TrainingPackage` 的 `weeks` 换成 `WeeklySheet` 的 `week`/`factor`/`reasons`/`sources`/`paused`）。
- **若 `training_package_payload` 的 block 级投影是一个内嵌的私有函数**（很可能，因为它要递归三层），**把它提出来成一个模块级的 `_block_payload(block) -> dict`**，两处共用。⚠️ **这是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，前端在学生端看到的 block 与教师端看到的就不是同一个形状了。
- **要有一条测试钉住「weekly-sheet 里的 block 与 training_package_payload 里的 block 逐字段同形」**（用同一个包、同一周，比对两边的 block dict）。**这条测试是「两个投影不漂移」的唯一守卫。**


**Files:** Create `backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`；Modify **`backend/app/api/schemas/prescription.py`（⚠️ S7：它由 Task 3 创建，本 Task 只补特例模型）**、`backend/app/api/routers/__init__.py`（**⚠️ 新 router 挂这里，不是 `main.py`**——`main.py` 的注释逐字写着「只 include 这**一个**汇总路由：Task 5/7/8/9 各加一个 router 时改的是 `app/api/routers/__init__.py`，不是本文件（本文件压着 `pe.db` 禁区那条纪律）」）、**`backend/app/api/crud.py`（P4-A6：加 `pk_alias` 参数）**、**`backend/app/api/deps.py`（P4-A5：两个身份头注册成 OpenAPI 的 `apiKey` securityScheme）**、**`backend/app/pipeline/prescription_stage.py`（P4-A1：把 block 级投影提成模块级函数，供两处共用）**、`backend/tests/api/test_crud.py`（**P4-A6 改完 23 个 detail 路径的 URL 模板会变，遍历型守卫要跟着改**）

**Interfaces:**
- Consumes: Task 1 的身份依赖、Task 3 的 `errors` 映射；Plan 02 的 `app.domain.prescription.{override, weekly}`、`app.pipeline.prescription_stage`
- Produces:
  - `GET /api/students/{student_id}/prescriptions/current` → 当前生效的那一张（`status ∈ {active, needs_review}` 且 `valid_to` 未过；没有 → `404` 且 `code == "no_active_prescription"`）
  - `GET /api/students/{student_id}/weekly-sheet?as_of=YYYY-MM-DD` → **spec §8.4 的「本周训练单」**：调 `prescription_stage.weekly_factors_of`（**⚠️ P4-A2：它已经存在，Plan 02 Task 8 交付的，实测签名 `weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，直接调用、不要重写**）+ `weekly.weekly_training_sheet`，返回 `WeeklySheet` 的 JSON 投影（`week` / `factor` / `reasons` / `sources` / `paused` / `sessions[].blocks[]`，**每个 block 带 `volume_unit`**）。**⚠️⚠️ P4-A1（Critical）：不许用 `dataclasses.asdict`** —— 实测它抛 `TypeError: cannot pickle 'mappingproxy' object`（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它），**带不带 `default=str` 都失败**（`default` 只在「未知类型」时被调用，而 `asdict` 在到达 json 之前就炸了）。**必须复用 Plan 02 已有的 `prescription_stage.training_package_payload(pkg) -> dict`**（它已经处理了只读映射、三层嵌套与 `hr_zone` 的元组→列表）：把它的 **block 级投影提成一个模块级函数**（如 `_block_payload(block) -> dict`），weekly-sheet 与 training-package 两处共用。**⚠️ 是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，前端在学生端看到的 block 与教师端看到的就不是同一个形状了。**要有一条测试钉住「weekly-sheet 里的 block 与 `training_package_payload` 里的 block 逐字段同形」**（同一个包、同一周，比对两边的 block dict）——**这条是两个投影不漂移的唯一守卫**
  - `POST /api/prescriptions/{id}/overrides` → 教师覆盖。**⚠️ P4-A3：请求体不能是 `OverrideRecord` 本身** —— 实测它的 **7 个字段全部无缺省**（`kind` / `target` / `old_value` / `new_value` / `reason` / `teacher_staff_no` / `applied_at`），而**后两个必须由服务端填**（身份头 + 时钟），让客户端传等于让它能冒充别的教师、还能伪造时间。故**请求模型是一个 5 字段的 Pydantic 类**（`kind` / `target` / `old_value` / `new_value` / `reason`），端点补齐后两个再构造 `OverrideRecord`。⚠️ `kind` 的值域**直接引 `OverrideKind`**（实测 5 个值是 `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`，**下划线不是连字符**），**不要在 schema 里抄第二份字符串**（单一所有者）。落进 `prescription.teacher_overrides`（**⚠️ P4-A4：这一列是 `TEXT NOT NULL` 的 `JsonText`**，故「追加一条覆盖」= **读 JSON 列表 → append → 写回**，不是 INSERT；空列表要写 `[]` 不是 `NULL`；**顺序承重**——Plan 02 的 5.4 定的是「多条覆盖同一目标由**列表顺序**决定、后者胜」，**不要按 `applied_at` 重排序**），并返回覆盖后的 `TrainingPackage` 投影。**⚠️ 调 `apply_overrides` 必须传 `exercises=`**（实测签名 `apply_overrides(pkg, records, *, exercises)`，关键字必填）—— 否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL，那是 Plan 02 顶回 2 逐字说的「一个看起来正常的谎」
  - `POST /api/prescriptions/{id}/regenerate` → 手动重生成（`teacher_requested=True`，走 Plan 02 的 `evaluate_triggers` 触发 5）
- **⚠️ 必须传导的 Plan 02 结论**：
  1. **`weekly_training_sheet` 的 `paused=True` 时 `sessions` 原样保留**（P8-A3）→ 前端要靠 `paused` 字段决定渲染什么，**不要在后端把 `sessions` 清空**。「暂停」与「本周量为 0」是两件不同的事。
  2. **`WeeklySheet` 刻意不提供跨单位的周总量汇总**（P8-A1）→ **API 也不要加**。`volume_unit` 实测值域 `{min, reps, unspecified}`，把它们相加就是 Plan 02 Task 5 的 F1-1 那个「混合量纲 float」错误。**前端要显示总量就自己按单位分组显示。**
  3. **`volume_unit == "unspecified"` 的 block 的 `weekly_volume` 恒为 `0.0`**（P5-A3：附加模块的量 spec 没给，本原型置 0 并交由教师用 `VOLUME_SCALE` 覆盖）→ **API 要把这条一并返回**，前端才能提示「这个附加模块的量待教师指定」。
  4. **`OverrideRecord.reason` 不得为空**（Plan 02 的 `__post_init__` 已校验）→ domain 抛 `ValueError` → `errors.py` 映射成 **422**，消息原文就是「一条没有理由的覆盖对研究毫无价值」那一段。**不要在 API 层再校验一遍**（第二个所有者）。
  5. **`old_value` / `new_value` 一律 `str`**（Plan 02 已定）→ Pydantic 模型也用 `str`，**不要用联合类型**。
  6. **覆盖不继承**（spec §7.5 原文 + Plan 02 Task 7 的 `test_regeneration_does_not_inherit_teacher_overrides`）→ `POST .../regenerate` 之后新处方的 `teacher_overrides` 是空的，而 **`previous_had_overrides` 是 `True`**（P6-A2：这一列就是「界面提示『该生上次存在人工覆盖』」的唯一载体）。**API 的响应里要带这一列**，否则前端提示不出来。

**决定：**
- **⚠️ P4-A5（前后端对接缺口 1）：把两个身份头注册成 OpenAPI 的 `apiKey` securityScheme。** 实测今天的 `openapi()["components"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、47 个路径里**声明过的 header 参数为空** —— 而 `X-Student-Id` / `X-Teacher-Staff-No` 是全部学生侧端点的必需头。**不注册的后果：Swagger UI 上没有地方能填它们、生成的 TS 客户端也不知道要发**，前端一接就撞 401 且不知道为什么。**⚠️ 用户 2026-10-08 明确要求「要确保后端和前端能够对接的上」，这一条是它的落点。**
- **⚠️ P4-A6（前后端对接缺口 3）：给 `build_crud_router` 加 `pk_alias: str | None = None`。** 实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**（`/api/semesters/{pk_value}`），而签名里只有 `pk: str = 'id'`（DB 列名）、**没有给 OpenAPI 路径参数另起名的口子**。`None` → 自动取**资源路径的单数 + 下划线**（`semesters` → `semester_id`、`course-sections` → `course_section_id`、`fitness-test-results` → `fitness_test_result_id`），显式传则覆盖。**理由：生成的 TS 客户端里到处是 `pkValue` 而不是 `semesterId`**；而这个改名是**纯 OpenAPI 层的**，不动 DB、不动路由匹配。**⚠️ 改完 23 个 detail 路径的 URL 模板会变，Task 3 那条遍历型守卫测试要跟着改。**
- **⚠️ P4-A7（前后端对接缺口 2，本 Task 不修、只记录）**：CORS 是 `allow_origins=["*"]` 且**没有 `allow_credentials`**（浏览器规范禁止两者并存）。**故 Plan 04 的前端不得用 cookie / `fetch(..., {credentials:'include'})`，身份只能走请求头。** 已写进本计划的「计划边界说明」。
- **`as_of` 由查询参数传，缺省取服务端当天**。理由：`weekly.current_week` 与 `evaluate_triggers` 都要求 `as_of` 由调用方注入（domain 不碰时钟），而 API 层是**可以**碰时钟的那一层。**但缺省取当天会让测试不可复现** → `conftest.py` 提供一个 `as_of` 覆盖（环境变量 `PE_AS_OF`），测试一律显式传。
- **`POST .../overrides` 是「追加」不是「替换」**：`teacher_overrides` 是一个 JSON 列表，新记录 append 到末尾。**顺序承重**（Plan 02 的 5.4 决定「多条覆盖同一目标由**列表顺序**决定、后者胜」，因为 `applied_at` 可能相同）。⚠️ **不要按 `applied_at` 重排序**。
- **`POST .../regenerate` 的幂等**：同一天重复点 → Plan 02 的 `UniqueConstraint("student_id", "generated_on")` + `repo.upsert` 保证只有一张。**API 返回 `200` 与那一张**（不是 `409`）—— 教师点两次「重新生成」不该看到报错。

- [ ] **Step 1–5: 写失败测试 → 实现 → 跑通 → 全量 → Commit**

测试至少：`test_current_prescription_is_404_when_there_is_none`、`test_weekly_sheet_carries_volume_unit_per_block`、`test_weekly_sheet_reports_paused_and_keeps_the_sessions`、`test_the_sheet_has_no_cross_unit_total_field`（**断言响应 JSON 里没有一个把 min 与 reps 加在一起的键**）、`test_an_unspecified_addon_block_comes_back_with_zero_volume`、`test_an_empty_override_reason_is_422_with_the_domain_message`、`test_overrides_append_and_the_list_order_decides`、`test_regenerate_clears_overrides_and_sets_previous_had_overrides`、`test_regenerating_twice_on_the_same_day_returns_200_and_one_row`、`test_a_student_cannot_read_another_students_weekly_sheet`（Review Focus 第 1 条）。

---
