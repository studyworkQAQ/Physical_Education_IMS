# Task 1 简报 — FastAPI 骨架 + 依赖注入 + 作用域闸门

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 1 全节**。Task 2–9 的正文不在本简报里。

## 0. 派单说明（控制者写，不在计划正文里）

**这是 Plan 03 的第一个 Task，也是整个项目第一次有 HTTP 层**——Plan 01/02 交付的是一个批处理系统（`python -m app.pipeline.daily`），今天 `backend/app/api/` 目录**不存在**、`app/main.py` **不存在**。你这个 Task 做完，`uvicorn app.main:app` 就能起得来、`/api/health` 与 `/docs` 就能打开。后面 8 个 Task 全部建在你这一层上。

**代码基线**：`5b4a10c`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **807 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `806 passed, 1 skipped`）。
**表数基线**：**18 张**（本 Task 不建表；Task 2 之后是 25）。
**架构守卫扫描面基线**：**35**（pipeline 8 + db 11 + domain 16）。**本 Task 要给它加 `api` 这一层**，故扫描面会涨——**涨了多少要在报告里写明**（S6 的裁定：下界断言由本 Task 一次性抬到位，后面 8 个 Task 不再动它）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、**FastAPI 0.141.1 / Starlette 1.7.0 / Pydantic 2.13.5 / uvicorn 0.54.0 / httpx 0.28.1（全部已装，`pyproject.toml` 早已声明，本 Task 不引入任何新依赖）**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。

⚠️ **开工第一件事（硬规矩 #73）**：跑
`python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"`
把版本记进报告。**若撞上 `ImportError: DLL load failed`（Windows Smart App Control 拦 `.pyd`），立刻停手、在报告里写明、结束任务交回控制者** —— 不要动系统安全设置、不要升降级依赖。（Plan 02 撞过一次，文件一个字节都没变也被拦，最后是换 SQLAlchemy 补丁版本解决的。）

## 0.1 ⚠️ 本 Task 的三个坑（控制者预检时查出，逐条照办）

1. **`pe.db` 禁区 vs「要真的把服务跑起来」**：Global Constraints 写着 `backend/pe.db` **不得存在**（Plan 01 立它是因为 `app.seed.generate` 会写它、而那份数据不可复现）。**但 Step 4 要你手工起一次 uvicorn。** 决定：**测试一律用内存库**（`sqlite://` + `StaticPool`，`conftest.py` 提供）；**手工演示用 `backend/pe_demo.db`**（新文件名，**要加进 `.gitignore`**）。**`pe.db` 仍然是禁区**——起 uvicorn 时**必须显式传 `db_url`**，不能让它落到 `DEFAULT_DB_URL`（那大概率就是 `pe.db`）。⚠️ **跑完 Step 4 之后立刻用 python 核实 `backend/pe.db` 仍不存在**，并把结论写进报告。这条是本 Task 最容易破的禁区。
2. **架构守卫今天不认识 `api` 这一层**：`test_layering.py` 扫的是 `("pipeline", 7)` / `("db", 11)` / `("domain", 16)` 三个目录、有一批下界断言（`>=5` / `>=8` / `>=16` / `len(real_py) >=40` 之类）。**加一层会让这些下界与「扫描面」的实测值同时变**。⚠️ **按硬规矩 #88：改完跑一次全量、把红掉的相等断言逐个收进来**，不要只 grep 那个数——Plan 02 Task 6 的教训是「漏的两格不是『表数这一个事实的副本』，而是『别的事实被同一改动证伪』」。
3. **`api` 层的依赖方向要显式定死**：`api` 可以 import `db` / `domain` / `pipeline` / `refdata*` / `config` / `notify`；**反向一律禁止**（`domain` 与 `db` 都不许 import `api`）。⚠️ **`domain` 的纯净性守卫会不会因为多了 `api` 这一层而误判？** 先实测：`test_domain_purity.py` 与 `test_layering.py` 各自怎么发现「哪些目录属于哪一层」的，**照它既有的机制加**，不要另发明一套。

## 0.2 执行强度（账本 Ruling 1）

**目标 0–1 轮 fix round。**
- **保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 100%（本 Task 不加 domain 代码，故四格应保持 **996 / 288**，若变了要说明为什么）；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01/02 的 807 条既有测试一条都不许退步**。
- **不做变异**（Ruling 1 的裁定：变异只在 Task 6 的预警阈值要求）。
- **取消**：纯散文精度 → 记进报告的「待清扫」清单，不返工。**但 Critical 级（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修。**

## 0.3 纪律

- **分支** `feature/plan-03-feedback-alert-crud-api`。**不要 push、不要切分支、不要碰 main。**
- **PowerShell**：`;` 分隔，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文）。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **`git add` 按文件名逐个加**，不要 `git add -A` / `git add .`。
- **禁区**：`backend/pe.db`（不得存在，见 0.1 第 1 条）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- **数键/字段/成员/目录里的文件数一律用运行时口径**（`len(...)`），**绝不用正则数源码**；**数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（Python 通用换行会把 `\r\n` 翻成 `\n`）。硬规矩 #89/#93。
- **⚠️ 不要用编辑器工具反复改 `.superpowers/` 下的文件**（IDE 曾把陈旧且截断的缓存写回磁盘，Plan 02 永久丢了约 107 KB；就在昨天它又截断了 `task-3-report.md` 与 `task-4-report.md`，靠 git 才救回来）。**报告一律用 python 写。**

## 0.4 ⚠️ 若你认为简报/计划某条决定是错的，**顶回来**

Plan 02 里实现者顶回控制者 **25 次，25 次都是对的**。最关键的几次：「派单要求把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 35 —— 照做会破坏一条有意的架构守卫、让断言两侧同源、让函数名变成谎话」、「派单要求的那条 tie-breaker 测试在 SQLite 上**结构上不可能变红**（`INTEGER PRIMARY KEY` = rowid 别名），照字面写只会得到一条恒绿的假守卫」、「派单声称控制者已经改了计划正文的 4 处，实测 0/4 在树上」。
共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 0.5 报告

写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-1-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加）。

至少 7 节：① 环境与基线复现（含 import 冒烟的版本）；② `create_app` / `get_db` / `current_student` / `current_teacher` / `require_scope` / `Page` 的最终签名（运行时口径，`inspect.signature`）；③ **架构守卫加 `api` 层的做法**（你实测到它今天怎么发现目录与层的、你照哪一套机制加的、下界断言抬到了什么值、扫描面从 35 变成几）；④ Step 4 的手工冒烟（起 uvicorn 的命令、`/api/health` 的响应原文、**跑完复核 `backend/pe.db` 仍不存在**）；⑤ 最终验收（passed 数 807 → ?、覆盖率四格、表数 18、三个指纹、`git diff 5b4a10c HEAD -- backend/data` 为空）；⑥ 待清扫清单 / 关切 / **没按派单做的地方（0 处也要写「0 处」）**；⑦ commit sha。

## 0.6 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格 / 扫描面 35 → ? 与下界断言的新值 / `create_app` 的签名 / `/api/health` 的响应原文 / `pe.db` 是否仍不存在 / 作用域闸门的三条测试名字 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

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

## Task 1: FastAPI 骨架 + 依赖注入 + 作用域闸门

**Files:** Create `backend/app/main.py`、`backend/app/api/{__init__,deps,errors}.py`、`backend/tests/api/conftest.py`、`backend/tests/test_main.py`、`backend/tests/api/test_scope.py`；Modify `backend/tests/architecture/test_layering.py`（加 `api` 层）

**Interfaces:**
- Produces:
  - `create_app(*, db_url: str | None = None) -> FastAPI`（`db_url` 缺省时取 `app.config.DEFAULT_DB_URL`；**测试注入内存库**）
  - `get_db() -> Iterator[Session]`（FastAPI 依赖；`yield` 一个 `Session`，退出时 `close()`；**不 commit**——提交由端点自己掌握，与 `repo.upsert` 的「flush 但不 commit」同口径）
  - `current_student(x_student_id: int | None = Header(None)) -> int`、`current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str`（缺头 → `401`）
  - `require_scope(session, student_id: int, requester_id: int) -> None`（**Review Focus 第 1 条**：不匹配 → `403`）
  - `Page`（`limit: int = 50`（上界 200）、`offset: int = 0`）
  - `GET /api/health` → `{"status": "ok", "tables": <int>, "students": <int>}`
- ⚠️ **`api` 层的依赖方向**：`api` 可以 import `db` / `domain` / `pipeline` / `refdata*` / `config` / `notify`；**反向一律禁止**（`domain` 与 `db` 都不许 import `api`）。这条要写进 `test_layering.py` 并与既有三层同口径。

**决定：**
- **⚠️ `pe.db` 禁区与「要跑 uvicorn」的冲突**：Global Constraints 写着 `backend/pe.db` 不得存在（Plan 01/02 立它是因为 `app.seed.generate` 会写它、而那份数据不可复现）。**但本计划要真的把服务跑起来。** 决定：**测试一律用内存库**（`sqlite://` + `StaticPool`，`conftest.py` 提供）；**手工演示用 `backend/pe_demo.db`**（新文件名，**不进禁区清单、但进 `.gitignore`**）。**`pe.db` 仍然是禁区**——它的语义是「`seed.generate` 写出来的那份不可复现的库」，与本计划的演示库不是一回事。⚠️ 这条要在 `.gitignore` 与 `pe_demo.db` 的生成脚本里都写明，否则下一个人会以为禁区被破了。
- **CORS**：`allow_origins=["*"]`（原型；Plan 04 的 Vite dev server 在 `localhost:5173`）。**在 `create_app` 的 docstring 里明写这是原型口径、上线前要收紧。**
- **异常映射**（`errors.py`）：domain 与加载器抛的 `ValueError` → **422**（含消息原文，因为它们逐字写明了「哪个键、哪个文件、期望什么」）；`sqlalchemy.exc.IntegrityError` → **409**；`NoResultFound` → **404**；其余 → **500 且不泄漏堆栈**（原型也要有这一条，否则前端拿到的是 HTML 错误页）。**统一响应形状** `{"error": {"code": str, "message": str, "detail": Any | None}}`。
- **不做的事**：不做 OpenAPI 的 tag 分组美化、不做响应模型的 `exclude_none`、不做速率限制、不做请求日志中间件。**原型阶段这些都是噪音。**

- [ ] **Step 1: 写失败测试**

`tests/api/conftest.py` 提供 `client` fixture（`TestClient(create_app(db_url="sqlite://"))`，内存库 + `StaticPool`，并在 fixture 里 `Base.metadata.create_all`）。`tests/test_main.py`：
- `test_health_reports_the_table_count`（断言 `tables == 18`，**字面写死**；Task 2 之后会变 25，那时同步改）
- `test_create_app_accepts_an_injected_db_url`（不碰 `DEFAULT_DB_URL`）
- `test_openapi_schema_is_generable`（`client.get("/openapi.json").status_code == 200`，且 `paths` 里有 `/api/health`）—— **这条是「系统能跑起来」的最小可执行判据**

`tests/api/test_scope.py`（Review Focus 第 1 条）：
- `test_missing_identity_header_is_401`
- `test_a_student_cannot_read_another_students_row`（造两个学生，用 A 的头请求 B → `403`）
- `test_require_scope_is_a_pure_gate`（直接调 `require_scope`，匹配时不抛、不匹配时抛 `HTTPException(403)`）

- [ ] **Step 2: 跑失败 → 实现 → 跑通**

`pytest -q tests/test_main.py tests/api/test_scope.py` 先红（模块不存在），实现后全绿。**再跑一次全量确认 807 不退步。**

- [ ] **Step 3: 给架构守卫加 `api` 层**

`test_layering.py` 的扫描目录清单加 `"api"`，并加一条方向断言：`app/api/**` 里的 import 可以指向 `app.db` / `app.domain` / `app.pipeline` / `app.refdata*` / `app.config` / `app.notify`，**而 `app/domain/**` 与 `app/db/**` 里出现 `app.api` 一律红**。⚠️ **按硬规矩 #88：改完跑一次全量，把所有红掉的相等断言逐个收进来**（扫描面的下界、`_py_files` 的目录存在性守卫等）。

- [ ] **Step 4: 手工冒烟 + Commit**

`cd backend; python -m uvicorn app.main:app --port 8000`（**非阻塞起、拿到 URL、`curl` 一次 `/api/health`、然后停掉**），把响应原文贴进报告。⚠️ 用 `pe_demo.db` 或内存库，**不要让它建 `pe.db`**。

---
