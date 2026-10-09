# Task 2 简报 — 反馈与预警的 7 张表 + 演示数据

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 2 全节（含预检更正 P3-A1..A6）**。Task 1 与 Task 3–9 的正文不在本简报里。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **824 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `823 passed, 1 skipped`）。**本 Task 不加 domain 代码，故四格应逐字不变**；若变了要说明为什么。
**表数基线**：**18 张**（本 Task 后 **25 张**）。
**扫描面基线**：**38**（pipeline 8 + db 11 + domain 16 + api 3）。**本 Task 不新增 `.py` 文件到 `app/api/`**（只改 `app/db/models/feedback.py`），故扫描面应**不变**；但 `tests/` 会多文件，那不计入扫描面。
**Task 1 已交付的东西（你要用）**：`app/main.py` 的 `create_app(*, db_url=None)`、`app/api/deps.py` 的 `get_db(request)` / `current_student` / `current_teacher` / `require_scope` / `Page`、`app/api/errors.py`、`tests/api/conftest.py` 的 `app`/`engine`/`client` 三个夹具、环境变量 **`PE_DB_URL`**（`DB_URL_ENV_VAR`）与 **`DEMO_DB_URL`**（指向 `backend/pe_demo.db`，已被 `.gitignore` 挡住）。
⚠️ **`app/config.py` 的 `DEFAULT_DB_URL` 实测逐字是 `sqlite:///…/backend/pe.db`** —— 那是**禁区**。**任何手工跑脚本都要显式设 `PE_DB_URL`**，不要让它落到缺省。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、FastAPI 0.141.1、Starlette 1.7.0、Pydantic 2.13.5、uvicorn 0.54.0、httpx 0.28.1、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

## 0.1 ⚠️ 本 Task 的 1 条 Critical（照办，不要按计划原文的模块归属做）

**P3-A1：7 张表全部放 `models/feedback.py`，`ops.py` 一张都不加。**

计划原文（未更正前）说「`alert` / `notification` / `weekly_class_report` → `models/ops.py`（spec §4.6 的标题逐字是『预警与运维』）」。**照做会当场撞红 Ruling 97 那条守卫**：实测 `models/__init__.py` 对 **`ops.py` 是 `from .ops import *`（星号导入）**，而对 `feedback.py` 与 `prescription.py` 是 **`from . import feedback, prescription`（非星号）**。放进 `ops.py` 的三个类名会**自动进入 `models` 的公有命名空间** → `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` 红，而**唯一的「修法」是把基线从 33 抬到 36——那正是 Plan 02 的实现者顶回过、控制者采纳过的那条禁令**（Plan 02 账本 Ruling 150 的顶回 1）。

**全放 `feedback.py` 的三个理由**：① 它走**非星号**导入，7 个类名**自动**留在公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7）全部属 Plan 03，由它填充**」；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。

**⚠️ 连带三件事**：
- (a) `feedback.py` 那段「**本模块今天刻意是空的**」的 docstring **必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表），**重写时保留它指向 `prescription.py` docstring 的那句交叉引用**（「留空而不是放占位类的理由见 `app.db.models.prescription` 的 docstring」——那句现在不再适用，要改成说明**为什么这 7 张表都住在这里**，并把 P3-A1 的星号导入理由写进去，否则下一个人会按 spec 的章节标题把它们搬去 `ops.py`、然后撞红守卫）。
- (b) **`_MODELS_SUBMODULES`（六个子模块）与 `_MODELS_PUBLIC_BASELINE`（33）都不动。**
- (c) `test_plan02_tables_stay_out_of_the_models_public_namespace` 要**扩到 11 个表类**（Plan 02 的 4 个 + 本计划的 7 个）。**函数名里的 `plan02` 要不要改成 `plan02_and_03`，你自己判断并在报告里说明理由。**

## 0.2 其余 5 条（简报的预检总表里有完整实测依据）

- **P3-A2**：`test_models.py` 的命中点是**约 11 类**，不是计划原先抄来的「六处 + 两处」（那是 Plan 02 Task 6 的数）。**新值**：表数 **25**、`len(json_text_columns)` **14 → 21**（7 个新 `JsonText` 列 = `mini_test.item_combo` + `alert.trigger_snapshot` + `weekly_class_report` 的 5 个）、`_BATCH_OWNED_TABLES` **5 → 9**、函数名 `eighteen → twenty_five`、两处 `assert len(tables) == 18` 的**中文消息里也有「18 张表」**、一段注释逐字印着 grep 命令与「**3** 处本段的散文」的计数、**三处**引用那个函数名。⚠️ **`assert len(_MODELS_PUBLIC_BASELINE) == 33` 有两处，刻意不动**（P3-A1）。**按硬规矩 #88：改完跑一次全量、把红掉的相等断言逐个收进来，不要只 grep 那个数。**
- **P3-A3**：**`_BATCH_OWNED_TABLES` 不只住在测试里** —— 实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像**。**先实测它到底定义在哪个文件**（`__init__.py` 那一处可能只是重导出），**改定义那一份、再改镜像，两处必须同时改**，否则 `assert observed == _BATCH_OWNED_TABLES` 会红在一个看不懂的地方。
- **P3-A4**：`weekly_adjustment` 今天**没有任何 `UniqueConstraint`**（实测约束 = `ck_weekly_adjustment_source` + 2 个 FK（`prescription_id`、`batch_id`）+ `ix_weekly_adjustment_batch_id` 非唯一索引；8 列 = `id / prescription_id / batch_id / week / factor / reason / source / created_at`）。故 S2 那条 `UniqueConstraint("prescription_id", "week", "reason", "source")` 是**全新**的。**要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError`** —— 这是 Review Focus 第 3 条（重复触发不得把系数连乘成 `0.8³ = 0.512`）的 **DB 层那一半**（应用层那一半是 Task 7 的 `window_key`）。⚠️ **本 Task 只需保证约束在、不必建 upsert 路径**（Plan 02 的 `weekly_factors_of` 是只读的；**Task 7 才会写这张表**）。
- **P3-A5**：`_in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint` 实测**只吃字符串词表**，而 `ops.py` 里**没有整数区间的先例** → `rpe BETWEEN 0 AND 10` 是**本计划第一处手写 CHECK**。**必须在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10`**，否则测试里的 `0` 与 `10` 是两个没有出处的魔数（而 spec §8.2 的 `RED_RPE_SUSTAINED`（连续 ≥ 9）与 `YELLOW_CLASS_RPE_HIGH`（均值 > 7）两个阈值都建立在这个值域上）。
- **P3-A6**：`feedback.py` 实测 `read_bytes()` **475 B**、`read_text().encode("utf-8")` **467 B** —— **差 8 字节 = 8 个 CRLF，即这个文件在磁盘上是 CRLF**。`backend/app/` 下的 `.py` **混用 CRLF 与 LF**（`.gitattributes` 只钉了 `backend/data/**` 与 `.superpowers/**`，`app/` 走 `core.autocrlf=true`）。**改它时要保持原有行尾**（用 `read_bytes()` 量、用 `newline=""` 写），否则一次编辑会把 8 行行尾全改掉、让 `git diff` 看起来整文件重写。

## 0.3 你要交付什么

**Modify**：
- `backend/app/db/models/feedback.py` —— **475 B 空壳 → 7 张表**（`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report`），列定义逐字照简报 Task 2 节的 Interfaces（它们逐格对得上 spec §4.5 / §4.6 / §4.7）
- `backend/app/db/models/__init__.py` —— **⚠️ P3-A3：`_BATCH_OWNED_TABLES` 的生产代码那一份可能住在这里，先实测**；`__all__` **不改**
- `backend/app/db/models/prescription.py` —— **S2 的裁定：给 `weekly_adjustment` 加那条唯一约束**（不推给 Task 7）
- `backend/tests/db/test_models.py` —— P3-A2 的约 11 类命中点
- `backend/tests/seed/test_generate.py` —— `DATA_TABLES` **11 → 18**（7 张全进这一个分区）+ 改掉 `REFERENCE_TABLES` 上方那段「届时」预告注释；`assert REFERENCE_TABLES == ("exercise", "prescription_template")` **不动**
- `backend/tests/test_main.py` —— **S3 的裁定：Task 1 那条 `tables == 18` 会在本 Task 变红**，改成 25
- `backend/tests/api/test_scope.py`（若它的夹具依赖表数则同步；**先实测**）

**Create**：`backend/app/demo_data.py`、`backend/tests/test_demo_data.py`

**⚠️ 分区守卫的口径（P3-A2 之外最容易踩的一条）**：`tests/seed/test_generate.py` 有 `assert partitioned == actual`（**7 张新表必须归进三个分区之一，否则这条红**）、三分区互不相交（用「三张清单长度之和 == 并集大小」查）、`for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0`（**seed 阶段必须 0 行**）、`for table in ORGANISATION_TABLES: assert count > 0`。**7 张全归 `DATA_TABLES` 与「seed 阶段 0 行」天然相容**（它们是管道产物或用户实时写入，都不由 `seed_database` 写）。

**⚠️ 演示数据不得由 `seed_database` 产出**：`demo_data.build_demo_feedback(session, *, cfg, as_of)` 是**独立函数、独立入口**，`tests/seed/test_generate.py` 的那一圈碰不到它。**这与 Plan 02 的 P3-A1 是同一条纪律**（`sync_exercises` / `sync_templates` 不许接进 `seed_database`）。**要有一条测试钉住它**：`test_seed_database_still_writes_no_feedback_rows`（`seed_database` 之后 7 张新表全 0 行）。

## 0.4 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（本 Task 四格应逐字不变）；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01/02 与本计划 Task 1 的 824 条既有测试一条都不许退步**。
- **不做变异**（Ruling 1：变异只在 Task 6 的预警阈值要求）。
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。**若你认为本简报/计划某条决定是错的，一定要顶回来**——Plan 02 的实现者顶回控制者 **25 次、25 次都是对的**，Plan 03 Task 1 又顶回 **3 次、3 次都是对的**（累计 **28/28**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。** 顶回时不要静默偏离，写进报告的「关切」节：哪条决定、为什么错、你的替代方案、代价。
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定**——28/28 的命中率意味着「0 处顶回」更可能是简报太粗而你没读出来，而不是计划真的对。

## 0.5 纪律

- **分支** `feature/plan-03-feedback-alert-crud-api`。**不要 push、不要切分支、不要碰 main。**
- **禁区**：`backend/pe.db`（**不得存在**；`DEFAULT_DB_URL` 就指向它，故手工跑脚本必须显式设 `PE_DB_URL`）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **数键/字段/成员/列数一律用运行时口径**（`len(list(SomeModel.__table__.columns))` / `len(Base.metadata.tables)`），**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（#89 的扩写，P3-A6 就是它的一次现身）。
- **断言「A 等于/不等于 B」时，若任一侧经过了序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99；Task 1 的实现者自查出过一处 `str(engine.url)` 把盘符 `:` 编码成 `%3A` 导致断言恒真的假绿）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件（IDE 曾把陈旧且截断的缓存写回磁盘；Plan 02 永久丢了约 107 KB，昨天又截断了两份报告靠 git 才救回）。

## 0.6 commit 与报告

**建议 3 个 commit**：① Step 0（`test_models.py` 的 11 类命中点 + `test_generate.py` 的分区 + `test_main.py` 的表数）—— **这一步跑完全量应该是红的**（表还没建），红的原因要逐条记进报告；② 7 张表 + `_BATCH_OWNED_TABLES` 两份 + `weekly_adjustment` 的唯一约束 → 全量转绿；③ `demo_data` + 它的测试。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-2-report.md`（**python 写**）。至少 8 节：① 环境与基线复现；② Step 0 的逐格落地（P3-A2 的 11 类，每格给「找到的原文 → 改成什么 → 在哪个文件」）；③ **7 张表的最终列清单**（逐列名字 + 类型 + nullable + default，运行时口径）与全部约束名；④ **P3-A1 的落地证据**（`feedback.py` 的新 docstring、`ops.py` 一个字节没改、`_MODELS_PUBLIC_BASELINE` 仍 33、`_MODELS_SUBMODULES` 仍六个、那条守卫扩到 11 个表类）；⑤ `_BATCH_OWNED_TABLES` 的**定义住址实测结论**与你改的两份；⑥ `demo_data` 的口径与三条测试；⑦ 待清扫 / 关切 / **没按派单做的地方（0 处也要写「0 处」）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑧ 最终验收（passed 数 824 → ?、覆盖率四格应不变、表数 18 → 25、扫描面应仍 38、三个指纹、`git diff <base> HEAD -- backend/data` 为空、`pe.db` 不存在）+ commit sha。

## 0.7 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格（应逐字不变）/ 表数 18 → 25 / `json_text_columns` 14 → ? / `_BATCH_OWNED_TABLES` 5 → ? 与它的定义住址 / `DATA_TABLES` 11 → ? / `_MODELS_PUBLIC_BASELINE` 是否仍 33 / 扫描面是否仍 38 / 7 张表的列数各是几 / `weekly_adjustment` 的新唯一约束名 / `demo_data` 的三条测试名 / 三个指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

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

## Task 2: 反馈与预警的 7 张表 + 演示数据

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `a44968f`，取证脚本 `t2_probes/_preflight.py`）

**测试基线**：`824 passed`；`app/domain/` **996/0/288/0/100%**；**18 张表**；扫描面 **38**（pipeline 8 + db 11 + domain 16 + api 3）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P3-A1** | **Critical** | **`models/__init__.py` 对 `ops.py` 是 `from .ops import *`（星号导入，实测在该文件的 import 段），而对 `feedback.py` 与 `prescription.py` 是 `from . import feedback, prescription`（非星号）。** 故把 `alert` / `notification` / `weekly_class_report` 三张表放进 `ops.py`，会让 `Alert` / `Notification` / `WeeklyClassReport` **三个类名自动进入 `models` 的公有命名空间** → `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` **当场红**，且**唯一的「修法」是把基线从 33 抬到 36——而那正是 Ruling 97 逐字禁止的**（「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了」）。 | **7 张表全部放进 `models/feedback.py`，`ops.py` 一张都不加。** 三个理由：① `feedback.py` 走的是**非星号**导入，7 个类名**自动**留在包的公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7`）全部属 Plan 03，由它填充**」，即 Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。**⚠️ `feedback.py` 那段「本模块今天刻意是空的」的 docstring 必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表）。 |
| **P3-A2** | **Important** | **`test_models.py` 的命中点比计划正文说的多得多**（计划说「六处」，那是抄 Plan 02 Task 6 的数）。实测（按可 grep 的原文，不用裸行号）：① 函数名 `test_all_eighteen_tables_created`；② **两处** `assert len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"`（**中文消息里也有 18**）；③ `assert len(Base.metadata.tables) == 18`；④ `assert len(json_text_columns) == 14`；⑤ `_BATCH_OWNED_TABLES = {…}` 那五张；⑥ 一段 docstring 逐字写着「有 `batch_id` 列的表**恰好**是 `_BATCH_OWNED_TABLES` 那**五张**」；⑦ `assert observed == _BATCH_OWNED_TABLES`；⑧ **一段注释逐字印着 grep 命令与「3 处本段的散文」的计数**；⑨ 另一段注释提到 `len(json_text_columns) == 14` 与 `_BATCH_OWNED_TABLES`；⑩ 一处注释「⚠️ Task 9 把它从 `_DERIVED_TABLES` 改名为 `_BATCH_OWNED_TABLES`」；⑪ **三处**引用 `test_all_eighteen_tables_created` 这个**函数名**；⑫ **两处** `assert len(_MODELS_PUBLIC_BASELINE) == 33`（**这个不动**，见 P3-A1）。 | **合计约 11 类命中点（不含 ⑫ 那两处刻意不动的）**，全部列进 Step 0 的表。⚠️ **这正是硬规矩 #88 要防的形状**：计划抄了上一个 Task 的「六处」，而实际是 11 类。**改完必须跑一次全量、把红掉的相等断言逐个收进来**，不要只 grep 那个数。新值：表数 **25**、`json_text_columns` **14 → 21**（7 个新 `JsonText` 列：`mini_test.item_combo`、`alert.trigger_snapshot`、`weekly_class_report` 的 5 个）、`_BATCH_OWNED_TABLES` **5 → 9**、函数名 `eighteen → twenty_five`。 |
| **P3-A3** | **Important** | **`_BATCH_OWNED_TABLES` 不只住在测试里**：实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像。** | **改的是生产代码那一份**（`app/db/models/__init__.py` 或 `prescription.py`——**先实测它到底定义在哪个文件**，`__init__.py:8` 可能只是重导出），测试那一份跟着改。⚠️ **两处必须同时改**，否则 `assert observed == _BATCH_OWNED_TABLES` 会红在一个看不懂的地方。**并要按硬规矩 #86 回扫 Task 7/8**：`_replay_cleanup` 的清单在 `daily.py`，它读的就是这个常量。 |
| **P3-A4** | **Important** | `weekly_adjustment` 今天的约束实测 = `ck_weekly_adjustment_source`（CHECK）+ 2 个 FK（`prescription_id`、`batch_id`）+ `ix_weekly_adjustment_batch_id`（非唯一索引）。**没有任何 `UniqueConstraint`。** 8 列 = `id / prescription_id / batch_id / week / factor / reason / source / created_at`。 | S2 那条 `UniqueConstraint("prescription_id", "week", "reason", "source")` 是**全新**的。⚠️ **加了它之后 `repo.upsert` 对这张表的 key_fields 口径要复核**（Plan 02 的 `weekly_factors_of` 是只读的，故今天没有 upsert 路径；Task 7 会写它）。**并要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError`**——这是 Review Focus 第 3 条（重复触发不得把系数连乘成 `0.512`）的 DB 层那一半。 |
| P3-A5 | Minor | `_in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint` ✓、`JsonText(TypeDecorator)` ✓、`DailySyncRun` 实测 **19 列**含 `alert_count` 与 `prescription_count` ✓、`DailySyncRun.STATUSES = {'success','partial','failed'}`、`CleaningLog.KINDS` 4 个值——**值域一律是类常量 + `_in_domain`**，与计划正文一致。 | 无需更正。**但 `rpe_record.rpe` 的 `BETWEEN 0 AND 10` 是整数区间不是词表**，`_in_domain` 不适用 → 计划正文已写明这一条**手写 `CheckConstraint`**，实测 `ops.py` 里也没有整数区间的先例，故这是本计划第一处手写 CHECK，**要在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10` 供测试引用**（否则测试里的 `0` 与 `10` 就是两个没有出处的魔数）。 |
| P3-A6 | Minor | **控制者自查**：计划正文写 `models/feedback.py` 是「**475 B** 的空壳」，实测 `read_bytes()` 是 **475 B**、而 `read_text().encode("utf-8")` 是 **467 B** —— **差 8 字节 = 8 个 CRLF**，即**这个文件在磁盘上是 CRLF**。 | 数字本身没错（`475 B` 是磁盘字节数），**但口径要写明**：`backend/app/` 下的 `.py` 文件**混用 CRLF 与 LF**（`.gitattributes` 只钉了 `backend/data/**` 与 `.superpowers/**`，`app/` 走 `core.autocrlf=true`）。**改这个文件时要保持它原有的行尾**（用 `read_bytes()` 量、用 `newline=""` 写），否则一次编辑会把 8 行行尾全改掉、让 `git diff` 看起来整文件重写。 |


**Files:** Modify `backend/app/db/models/feedback.py`（**475 B 空壳 → 7 张表**，⚠️ P3-A1：`ops.py` **一张都不加**）、`backend/app/db/models/__init__.py`（**⚠️ P3-A3：`_BATCH_OWNED_TABLES` 的生产代码那一份可能住在这里，先实测**；`__all__` 不改）、`backend/tests/db/test_models.py`、`backend/tests/seed/test_generate.py`、**`backend/app/db/models/prescription.py`（给 `weekly_adjustment` 加一条唯一约束，见 S2 的裁定）**、**`backend/tests/test_main.py`（Task 1 那条 `tables == 18` 会在本 Task 变红，见 S3 的裁定）**；Create `backend/app/demo_data.py`、`backend/tests/test_demo_data.py`

**Interfaces:**
- Produces（**列定义逐字照 spec §4.5 / §4.6 / §4.7**，类型与约束照 Plan 02 的既有口径：值域一律 `_shared._in_domain(column, allowed, name)` + **类常量**，不手写 `CheckConstraint`）：
  - `ClassSession`（表 `class_session`）：`id` / `course_section_id` FK / `session_date: Date` / `period: int`（节次）/ `rpe_opened: Boolean, nullable=False, default=False`（是否已发起课堂快评）/ `rpe_token: str | None`（快评口令，`String(16)`）/ `batch_id` FK→`daily_sync_run`
  - `RpeRecord`（`rpe_record`）：`id` / `class_session_id` FK / `student_id` FK / `rpe: int` + CHECK ∈ `0..10`（**⚠️ 用 `_in_domain` 不合适——它是整数区间不是词表**（P3-A5 实测坐实：`_in_domain(column, allowed: Iterable[str], name)` 只吃字符串词表，而 `ops.py` 里也**没有整数区间的先例**，故这是本计划第一处手写 CHECK），故这一条**手写 `CheckConstraint("rpe BETWEEN 0 AND 10", name="ck_rpe_record_rpe")`**，并在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10` 供测试引用（**否则测试里的 `0` 与 `10` 就是两个没有出处的魔数**，而 spec §8.2 的 `RED_RPE_SUSTAINED`（连续 ≥ 9）与 `YELLOW_CLASS_RPE_HIGH`（均值 > 7）两个阈值都建立在这个值域上））/ `submitted_at: DateTime` / `elapsed_seconds: Float | None`（**提交耗时秒**，spec §8.1 逐字「指导文件要求 10 秒内完成」）+ `UniqueConstraint("class_session_id", "student_id")`
  - `TrainingLog`（`training_log`）：`id` / `student_id` FK / `log_date: Date` / `completed: Boolean` / `duration_min: Float | None` / `feeling: str | None` + CHECK ∈ `{easy, moderate, hard}` / `is_rest_day: Boolean, nullable=False, default=False`（是否休息日打卡）/ `late: Boolean, nullable=False, default=False` / `source: String(16)` / `batch_id` FK + `UniqueConstraint("student_id", "log_date")`
  - `MiniTest`（`mini_test`）：`id` / `student_id` FK / `semester_id` FK / `week: int` / `item_combo: JsonText`（测试项组合）/ `squat_30s_count: int | None` / `shuttle_20m_s: float | None` / `normalized_score: float | None` / `tested_on: Date` / `entered_by: str`（录入教师）+ `UniqueConstraint("student_id", "semester_id", "week")`
  - `Alert`（`alert`）：`id` / `student_id: int | None` FK / `course_section_id: int | None` FK（**班级级预警用它**，spec §4.6 逐字「student_id（班级级预警为 course_section_id）」）/ `level: String(8)` + CHECK ∈ `{red, yellow, green}` / `rule_id: String(32)` / `trigger_snapshot: JsonText`（**触发数据快照**）/ `triggered_at: DateTime` / `status: String(8)` + CHECK ∈ `{pending, handled, ignored}` / `handled_action: str | None` / `handled_at: DateTime | None` / `batch_id` FK / **`semester_id: int` FK（去重键的一部分）** / **`window_key: String(32)`（触发窗口标识，见下面「去重口径」的决定；⚠️ 这一列 spec §4.6 没有，是本计划的工程决定 → 登记 spec §14 #38）** + `UniqueConstraint("rule_id", "student_id", "course_section_id", "semester_id", "window_key")`
  - `Notification`（`notification`）：`id` / `recipient_kind: String(8)` + CHECK ∈ `{student, teacher}` / `recipient_id: int` / `channel: String(16)` + CHECK ∈ `{in_app, wechat_subscribe, sms}` / `title: str` / `body: str` / `alert_id: int | None` FK（**`ondelete="SET NULL"`**，理由见 Task 8 的决定：`notification` 不带 `batch_id`、不进 `_replay_cleanup`，而 `alert` 进——重放删掉 alert 时不能让通知行炸 FK）/ `prescription_id: int | None` FK / `is_read: Boolean, nullable=False, default=False` / `created_at: DateTime`
  - `WeeklyClassReport`（`weekly_class_report`）：`id` / `course_section_id` FK / `semester_id` FK / `week: int` / `layer_distribution: JsonText`（分层分布及环比流动）/ `rpe_summary: JsonText`（人均 RPE 与上周对比）/ `checkin_rate_by_layer: JsonText` / `progress_board: JsonText`（进步榜/退步名单）/ `alert_summary: JsonText` / `suggestion: str`（**算法建议**）/ `generated_at: DateTime` / `batch_id` FK + `UniqueConstraint("course_section_id", "semester_id", "week")`
  - `demo_data.build_demo_feedback(session, *, cfg, as_of) -> DemoReport`（**演示数据**：给已有的 500 人造若干课次、RPE、打卡、小测，让 Plan 04 的前端有东西可显示）

**决定：**
- **⚠️ P3-A1 更正：7 张表全部放 `models/feedback.py`，`ops.py` 一张都不加。** 原文这里说「`alert` / `notification` / `weekly_class_report` → `models/ops.py`（spec §4.6 的标题逐字是『**预警与运维**』）」——**照做会当场撞红 Ruling 97 那条守卫**：实测 `models/__init__.py` 对 `ops.py` 是 **`from .ops import *`（星号导入）**，而对 `feedback.py` 与 `prescription.py` 是 **`from . import feedback, prescription`（非星号）**。故放进 `ops.py` 的三个类名会**自动进入 `models` 的公有命名空间**，让 `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` 红，而**唯一的「修法」是把基线从 33 抬到 36——那正是 Ruling 97 逐字禁止的**（「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了」；Plan 02 的实现者顶回过控制者一次同样的指令，控制者采纳了，见 Plan 02 账本 Ruling 150 的顶回 1）。
  **全放 `feedback.py` 的三个理由**：① 它走**非星号**导入，7 个类名**自动**留在包的公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7）全部属 Plan 03，由它填充**」，即 Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。
  **⚠️ 连带三件事**：(a) `feedback.py` 那段「**本模块今天刻意是空的**」的 docstring **必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表），重写时**保留它指向 `prescription.py` docstring 的那句交叉引用**；(b) **`_MODELS_SUBMODULES` 与 `_MODELS_PUBLIC_BASELINE` 都不动**（仍是六个子模块 / 33 个名字）；(c) `test_plan02_tables_stay_out_of_the_models_public_namespace` 那条守卫**要扩到 11 个表类**（Plan 02 的 4 个 + 本计划的 7 个），**函数名里的 `plan02` 要不要改成 `plan02_and_03` 由实现者判断并说明理由**。
- **`models/feedback.py` 今天是一个 475 B 的空壳**，它的模块 docstring 是「这里为什么没有表」的唯一交代 → **加表时必须把那段 docstring 改掉**（否则它会说「这里没有表」而文件里有 4 张）。
- **分区归属**：7 张全部进 **`DATA_TABLES`**（11 → **18**）。⚠️ 但那一条守卫要求 `DATA_TABLES + REFERENCE_TABLES` 在 `seed_database` 之后 **0 行** → **演示数据不得由 `seed_database` 产出**（这正是 P3-A1 在 Plan 02 立过的同一条纪律：`sync_exercises` / `sync_templates` 不许接进 `seed_database`）。`demo_data.build_demo_feedback` 是**独立函数、独立入口**，`tests/seed/test_generate.py` 的那一圈碰不到它。
- **⚠️ P3-A2 更正：`test_models.py` 的命中点是约 11 类，不是「六处 + 两处」**（那是 Plan 02 Task 6 的数，抄过来就错了）。**按硬规矩 #88：先跑一次全量、把红掉的相等断言逐个收进来，不要只 grep 那个数。** 实测清单见预检总表的 P3-A2 那一格。本 Task 至少要有：函数名 `test_all_eighteen_tables_created` → `twenty_five`、**两处** `assert len(tables) == 18` 及其**中文消息里的「18 张表」**、`assert len(Base.metadata.tables) == 18`、那段**逐字印着 grep 命令与「N 处散文」计数**的注释、另一处引用**函数名**的注释、`len(json_text_columns)` 的相等断言（Plan 02 Task 6 之后是 **14**；7 张新表里有 **7 个 `JsonText` 列** —— `mini_test.item_combo`、`alert.trigger_snapshot`、`weekly_class_report` 的 5 个（`layer_distribution` / `rpe_summary` / `checkin_rate_by_layer` / `progress_board` / `alert_summary`），故新值应是 **21**。⚠️ **自己用运行时口径数一遍再写进断言**，不要照抄这个数——控制者在 Plan 02 为此栽过 4 次）、**⚠️ P3-A3：`_BATCH_OWNED_TABLES` 不只住在测试里**——实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像；先实测它到底定义在哪个文件（`__init__.py` 那一处可能只是重导出），改定义那一份、再改镜像，两处必须同时改。** `_BATCH_OWNED_TABLES`（Plan 02 Task 9 把 `_DERIVED_TABLES` 改成了这个名字；**带 `batch_id` 的表**要从 **5 张扩到 9 张**——既有 5 张是 `derived_metrics` / `stratification_result` / `percentile_snapshot` / `prescription` / `weekly_adjustment`，本计划新增 4 张带 `batch_id` 的是 `class_session` / `training_log` / `alert` / `weekly_class_report`；**`rpe_record` / `mini_test` / `notification` 三张刻意不带**，理由见下面那条决定。⚠️ **这个数自己用运行时口径数一遍再写进断言**，不要照抄本行）、`_MODELS_PUBLIC_BASELINE`（**仍是 33，不动**，Ruling 97）、`test_plan02_tables_stay_out_of_the_models_public_namespace`（**扩到 11 个表类**：Plan 02 的 4 个 + 本计划的 7 个，函数名里的 `plan02` 要不要改成 `plan02_and_03` 由实现者判断并说明）。
- **⚠️ `alert` 的去重口径（Review Focus 第 3 条）**：不能简单加 `UniqueConstraint("rule_id", "student_id")` —— 那会让「上学期处理过、这学期又触发」插不进去。**决定：唯一约束是 `("rule_id", "student_id", "course_section_id", "semester_id", "window_key")`**（五个列都已在上面的字段清单里），其中 `window_key` 是**触发窗口的标识**（`RED_RPE_SUSTAINED` 用「第 3 次快评的 `class_session_id`」、`RED_MINITEST_DROP` 用「第 3 个小测的 `mini_test.id`」、`YELLOW_CHECKIN_GAP` 用「中断结束日的 ISO 串」、`YELLOW_CLASS_RPE_HIGH` 用「`semester_id:week`」、`GREEN_MASTERY` 用「`semester_id:week`」）。**这样「同一次触发只有一条 alert」由 DB 保证，而「下一轮再触发」是一条新行。** ⚠️ 这一列 spec 没有，是本计划的工程决定 → **登记 spec §14**。
  - ⚠️ `student_id` 与 `course_section_id` **都可空**，而 SQLite 的 UNIQUE 对 NULL 是「NULL ≠ NULL」（多行 NULL 不冲突）→ **约束对班级级预警失效**。**决定：两列都改成 `nullable=False` + 用 `0` 作哨兵**（学生级预警 `course_section_id = 0`、班级级预警 `student_id = 0`），并在列注释与 docstring 里写明这个哨兵语义。**否掉「加一个 `scope_kind` 列 + 部分索引」的方案**：SQLite 的部分索引支持有限，而哨兵 `0` 与 `repo.upsert` 的既有口径相容。
- **⚠️ S2 的裁定：`weekly_adjustment` 的那条唯一约束在本 Task 加，不推给 Task 7。** Task 7 需要 `UniqueConstraint("prescription_id", "week", "reason", "source")` 来防「同一周重复触发把系数连乘成 `0.8³ = 0.512`」（Review Focus 第 3 条），而那张表是 **Plan 02 Task 6 建的**。**schema 变更一律归本 Task**（本计划唯一的建表 Task），理由见账本 S2：schema 变更分散在两个 Task 会让「表数」与「约束清单」两个断言的改动点跨 Task，而 Plan 02 的 P6-A5 已经证明「一个数散落在多处」是最容易漏改的形状。⚠️ 加完要跑一次全量、把红掉的相等断言逐个收进来（硬规矩 #88）。**⚠️ P3-A4：`weekly_adjustment` 今天没有任何 `UniqueConstraint`**（实测约束 = `ck_weekly_adjustment_source` + 2 个 FK + `ix_weekly_adjustment_batch_id` 非唯一索引），故这一条是**全新**的。**要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError`** —— 这是 Review Focus 第 3 条（重复触发不得把系数连乘成 `0.8³ = 0.512`）的 **DB 层那一半**（应用层那一半是 Task 7 的 `window_key`）。⚠️ 加完之后 `repo.upsert` 对这张表的 `key_fields` 口径要复核（Plan 02 的 `weekly_factors_of` 是只读的、今天没有 upsert 路径；**Task 7 才会写它**，故本 Task 只需保证约束在、不必建 upsert 路径）。
- **`batch_id`**：`class_session` / `training_log` / `alert` / `weekly_class_report` 四张带 `batch_id`（FK→`daily_sync_run`），因为它们是批处理产物、要能被 `_replay_cleanup` 按批删。`rpe_record` / `mini_test` / `notification` **不带**——它们是**用户实时写入**的，重放不该删掉学生刚交的作业。⚠️ **这个区分要写进 docstring**，否则下一个人会给全部 7 张加 `batch_id`。

- [ ] **Step 1: 写失败测试** → [ ] **Step 2: 跑失败** → [ ] **Step 3: 建 7 张表** → [ ] **Step 4: 改 `test_models.py` 与 `test_generate.py` 的全部命中点** → [ ] **Step 5: 全量跑通（表数 25）** → [ ] **Step 6: `demo_data` + 它的测试** → [ ] **Step 7: Commit**

`demo_data` 的测试至少：`test_build_demo_feedback_is_idempotent`（跑两次行数不变）、`test_demo_data_never_touches_the_clock`（`as_of` 由调用方注入；源码级检查，照 `tests/seed/test_generate.py` 的 `test_generators_thread_the_callers_rng_and_never_touch_the_clock` 的形状）、`test_seed_database_still_writes_no_feedback_rows`（**这条守的是上面那个分区决定**：`seed_database` 之后 7 张新表全 0 行）。

---
