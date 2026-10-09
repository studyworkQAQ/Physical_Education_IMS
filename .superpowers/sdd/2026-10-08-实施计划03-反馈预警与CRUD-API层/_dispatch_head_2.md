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

