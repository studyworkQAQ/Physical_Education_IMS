# 实施计划 02：智能处方引擎

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01 产出的红黄绿分层结果，按「层 × 主导短板 × 体成分」装配成可复现、可审校、可被教师覆盖的 4 周运动处方，并接进每日批处理管道。

**Architecture:** `app/domain/prescription/` 是无 I/O 的纯函数叶子层（匹配、强度换算、装配、安全后置、覆盖、触发判定），模板与动作等价映射是 `backend/data/` 下带版本号的静态 YAML（体育专家可独立审校），`app/pipeline/prescription_stage.py` 负责落库与幂等。处方**不每天重发**——只有 spec §5.2 的五个触发条件之一成立时才生成，而分层重算仍然每天跑。

**Tech Stack:** Python 3.11.1、SQLAlchemy 2.1、SQLite（`PRAGMA foreign_keys=ON`）、PyYAML、pytest + pytest-cov。不引入新依赖。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md` —— 本计划实现 **§4.4（处方数据模型）、§5.2（五个触发条件）、§7.1–7.5（智能处方层全部）、§8.4（骨架 + 周微调两层拆分）、§11.2（B 类算法降级）、§1.3（单人处方 p95 < 3 秒）、§12（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）**。

**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的六条见 Global Constraints。

---

## Global Constraints

- **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(`；不得出现 `read_csv` / `read_text` / `Path(` / `__file__` / `json.load` / `os.listdir` / `import os`。**时间与随机数一律由调用方注入**，参考表一律由 `app/refdata.py` 加载后**作为参数传入**。守卫是 `tests/architecture/test_domain_purity.py`（Task 1 会把它从 deny-list 改成 allow-list）。
- **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令**必须带 `--cov-branch`**：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。
- **单一所有者**：任何常量/词表/权重只允许有一个住址。Plan 01 为此立过 6 条裁定（Ruling 35/36/63/152/156/190）。本计划新增的 `ITEM_BUCKET` 消费、模板维度词表、`impact_level` 词表、`exercise_ref` 词表都必须指向唯一所有者，且**各有一条漂移测试**。
- **断言两侧不得同源**（硬规矩 #35）：期望值一律**字面写在测试里**，不从被测常量读回来跟自己比。Plan 01 因此吃过三次亏（Ruling 166/186/216-M3）。
- **散文必须带口径**（硬规矩 #19/#20/#25/#29/#36/#39/#43）：注释与 docstring 里出现的每个数字都要能指到产生它的那条命令；每个因果机制都要附 `文件:行 + 引文`；尺寸/时长/速率必须带单位与进制、带 n 与区间；**不得印未经多样本验证的概率模型**；凡写下测量条件，必须同时写「哪条测试会在它失效时变红」，写不出来就标「历史实测，不被守卫」。
- **行号一律取 shell 口径**（硬规矩 #30/#37）：`Read` 工具的行号在本仓部分区段**系统性少 1**，已四次误导。行号引用绑定 commit。
- **PowerShell**：分隔用 `;`，不支持 `&&`/`||`；**没有 heredoc**；**反引号会被吃掉**；`python -c` 里字符串一律用单引号，需要双引号就写临时 `.py`（放 `$env:TEMP`）。**所有写文件走 python**（`Add-Content` 静默写坏中文）。commit 信息用 python 写 UTF-8 临时文件 + `git commit -F`。
- **落盘唯一权威是 shell**；**`git checkout` / `git switch` / `git merge` 会按 `core.autocrlf` 重写工作树**（硬规矩 #46），事后必须复核所有「按字节哈希」的断言。`backend/data/` 已由 `.gitattributes` 钉为 `eol=lf`，**本计划新增的 YAML 必须落进同一条规则**。
- **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/national_standard_2014.csv`（sha256[:16] 恒为 `D2C8E539E2FA0029`，由指纹测试守卫）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`，要落 CSV 就 `write_csv(ds, <临时目录>)`。
- **`app/seed/` 自 Plan 01 结案后重新冻结**（Task 1 的依赖迁移会动它一次，见 Task 1 的解冻范围，之后不再动）。

## Review Focus

spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。下面五类输入/状态是 spec **没有覆盖**、而一个真实使用者最可能撞上的，每类都在拥有该代码的 Task 里补了测试：

1. **模板 YAML 被专家改坏**（少一个键、`week_deltas` 长度与 `microcycle_weeks` 不符、`exercise_ref` 指向不存在的动作、`reachable: true` 但维度组合不可达）→ 必须在**加载时**响亮失败并指出是哪个文件哪一行，而不是在装配到某个学生时才炸。归属 Task 3。
2. **同一个学生在同一天被两次触发**（管道重跑、或教师手动请求与自动触发撞上）→ 必须产出一条处方而不是两条，且第二次是幂等的 no-op 或明确的 `replaced`。归属 Task 9。
3. **学生当天没有分层结果**（`valid_count < 4` → `insufficient_data`，Z0 闸门拦下）→ **不得生成处方**，且必须留下可交代的痕迹（不是静默跳过）。Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 9。
4. **年龄缺失或异常**（`Student.birth` 为空、或算出年龄 ≤ 0 / ≥ 100）→ Tanaka 公式会给出荒谬的 HRmax（如 `208 − 0.7×0 = 208`），进而给出危险的目标心率区间。必须响亮拒绝或降级到 `needs_review`，**不得静默装配**。归属 Task 5。
5. **安全规则命中但 `exercise_equivalence.yaml` 里找不到等价动作**（spec §7.4 明写「不静默跳过」）→ 处方状态置 `needs_review`、写 `warning` 日志、教师端标记「需人工复核」。这是 spec 唯一一处显式要求「宁可不自动，也不要自动错」的地方，必须有测试钉住**它没有被静默跳过**。归属 Task 7。

---

---

## Task 1: 架构债清偿（终审 C 组 11 项，在写任何新代码之前做完）

**Files:**
- Create: `backend/app/config.py`、`backend/app/adapters/factory.py`、`backend/app/db/models/{__init__,organisation,assessment,derived,prescription,feedback,ops}.py`、`backend/tests/architecture/test_layering.py`
- Modify: `backend/app/db/models.py`（删除，改为包）、`backend/app/pipeline/{run_stratify,daily,backfill,percentile_stage}.py`、`backend/app/seed/{generate,fitness}.py`、`backend/app/db/session.py:53`、`backend/app/refdata.py`、`backend/tests/db/test_models.py`
- Delete: `backend/app/db/models.py`（内容迁入包）

**Interfaces:**
- Consumes: Plan 01 全部
- Produces:
  - `app.config.DEFAULT_DB_URL: str`、`app.config.DEFAULT_CSV_DIR: pathlib.Path`、`app.config.BACKEND_DIR: pathlib.Path`
  - `app.adapters.factory.build_adapter(kind: str = "mock", *, csv_dir: pathlib.Path | None = None, base_url: str | None = None, token: str | None = None) -> DataSourceAdapter`
  - `app.db.models` 仍是**同一个导入面**（`from app.db import models; models.Student` 不变）
  - `app.domain.indicators.COLUMN_BY_ITEM: dict[ScoredItem, str]`（从 `app/seed/fitness.py` 迁入）
  - `app.domain.indicators.bmi_of(height_cm: float | None, weight_kg: float | None) -> float | None`（**从 `app/pipeline/run_stratify.py:178` 迁入**——它是身高体重的纯函数，住在 pipeline 层是错的层；`run_stratify` 改为从 domain 重导出，保持既有导入面）
  - `app.domain.indicators.CLEANING_FIELDS: frozenset[str]`（`cleaning_log.field` 的词表唯一所有者 = `COLUMN_BY_ITEM` 的值 ∪ `{"student_no"}` ∪ `WHOLE_RECORD`）
  - `app.refdata.RANGES_FILENAME: str`（从 `app/seed/generate.py` 迁入）

- [ ] **Step 1: 写失败测试 —— 依赖方向守卫**

`backend/tests/architecture/test_layering.py`：AST 扫 `app/pipeline/` 与 `app/db/` 下全部 `.py` 的 `Import` / `ImportFrom`（**`ast.walk` 天然覆盖函数内导入**），断言 `node.module` 不以 `app.seed` 开头。offender 一次性报全（`assert offenders == []`）。**空转守卫**：`assert len(scanned) >= 8`。

同文件再加三条（终审 A 的 M7）：把 `test_domain_purity.py` 的 import 守卫从 deny-list 改成 **allow-list**（`app.domain.*` + `collections.abc` / `dataclasses` / `enum` / `typing` / `numpy`），时钟与 `open` 改用 **AST 节点匹配**（解析 `ast.Call` 的 `func`）而不是子串，并加 `assert len(scanned) >= 5` 堵掉空目录空转。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend; python -m pytest tests/architecture -q`
Expected: FAIL —— 依赖方向守卫报 4 处 offender（`run_stratify.py:48-49`、`daily.py:621`、`backfill.py:234`，行号以 `git grep -n "from app.seed" -- backend/app/pipeline` 为准）；allow-list 守卫报 `numpy` 之外的漏网（若当前 domain 只 import `numpy`，则 allow-list 那条应当**直接绿**——那也是有效信息，说明 deny-list 今天恰好没漏，报告里写明）。

- [ ] **Step 3: 迁移四个常量，建 `app/config.py` 与适配器工厂**

按 Interfaces 块迁移。**`COLUMN_BY_ITEM` 迁到 `app/domain/indicators.py`**（不是终审 B 备选方案里的 `adapters/base.py`）——理由：迁到 adapters 会让 `base.py` 新增 `from app.domain.indicators import ScoredItem`，打破它现有「import 面只有 `re`/`abc`/`collections.abc`/`dataclasses`」的性质；而 domain 是叶子、谁都能依赖它，且它已经拥有 `ScoredItem` 与 `WEAKNESS_ITEMS`。**同时解决 Ruling 156**：`cleaning_log.field` 的词表从此有了单一所有者，把它接进 `tests/db/test_models.py` 的列宽遍历测试（硬规矩 #18）。

`app/db/session.py:53` 的 `def engine(url: str = "sqlite:///pe.db")` **删掉缺省值**（改成必填）——它是 `DEFAULT_DB_URL` 的第二个所有者，而且正是 Ruling 190 要消除的「CWD 相对路径」形状。今天它是死代码（6 个调用点全部显式传 URL），但它是活陷阱。

`daily.py` / `backfill.py` 的 `MockLePaoAdapter(DEFAULT_CSV_DIR)` 硬编码改走 `build_adapter(...)`——终审 B 指出：换实现现在要改**两处生产代码**，与 `http_lepao.py:10-11` 承诺的「改动只落在本文件」不符。

- [ ] **Step 4: `models.py` 拆包 + 索引 + `fitness_test_result.tested_on` + `daily_sync_run` 两列**

拆包按 spec §4 的小节分组（见 File Structure）。**`from app.db import models` 的导入面必须逐字不变**——用 `models/__init__.py` 重导出全部类与 `Base`。

同时做四件 schema 改动：
1. `Index("ix_stratification_result_student_computed", "student_id", "computed_on")` 与 `derived_metrics` 同名索引。终审 B 实测：单人「当前分层」查询 **57.9 ms → 0.2 ms（258×）**，代价 **+2.7% 文件体积**。⚠️ `init_db` 用 `create_all`，**对已存在的表不补索引**——在 `session.py` 的 docstring 里写明，并给 CLI 加一句提示或一个 `--recreate` 说明。
2. `fitness_test_result.tested_on: Mapped[dt.date]`（终审 B 的 M1）。源记录本来就带这个字段，而 `fitness_test_batch.test_date` 是**一个批次一个值**，所以 `cohort_from_db` 无法按日期截断 → 重跑一个更早的业务日期会读到未来数据（终审实测 12/60 人 label 不同）。加列后 `percentile_stage._results_of` 加 `.where(FitnessTestResult.tested_on <= as_of)`。
3. `daily_sync_run.prescription_count: Mapped[int]`（default 0）与 `.alert_count: Mapped[int]`（default 0）——**spec §4.6 明确列了「处方生成数、预警触发数」两列，Plan 01 没建**。`alert_count` 本计划只建列不写值（Plan 03 落地），并在列注释里写明。
4. `daily_sync_run.muscle_line_gaps: Mapped[int]`（default 0），替代现在写进 `error_summary` 的「注意（非错误）：N 个组没有肌肉量 P20 判定线」自由文本（终审 C 组第 24 项）。**保留 `error_summary` 的既有写法一个 Task 周期**，两处同时写，等 Plan 03 确认没有消费者只读文本再删——或者你判断直接切更干净，那就直接切并在报告里说明。

⚠️ 第 2 项是**破坏性 schema 改动**：`fitness_test_result` 现有 3000 行（500 人 × 6 个采集日）没有 `tested_on`。`init_db` 的 `create_all` 不会给已存在的表加列，所以**任何已有的 `pe.db` 都必须重建**。本仓不入库 `pe.db`，故实际影响为零，但要在 `models.py` 的模块 docstring 里写明「本仓不做迁移，schema 改动 = 重建库」，避免 Plan 03 的人以为有 Alembic。

- [ ] **Step 5: `_fitness_batch` 的 upsert 摘掉 `test_date`**

终审 B 的 M3：`daily.py` 把 `test_date` 放进了**每一条**记录的 upsert 值，而 `repo.upsert` 是 PATCH 语义 → `fitness_test_batch.test_date` 随抽取窗口漂移（同一份 CSV、同一个最终业务日期，只改执行顺序就得到 09-01 / 09-05 / 09-08 三个值）。改成**插入时用首条记录的值、更新时不动**，或带 `min(现有值, 本条值)`。

⚠️ 终审 B 诚实标注了：它**构造了反例但没能演示 anchor 真的翻转**（重跑更早那天时 `_load_sources` 又把 `test_date` PATCH 回去了），所以这条是 Major 不是 Critical。**修它的理由不是「它今天会错」，而是「Step 4 加了 `tested_on` 之后 `test_date` 的唯一职责就是 `assessment_anchor` 的排序键，而一个随执行顺序漂移的排序键是不可接受的」。**

- [ ] **Step 6: 跑全量测试**

Run: `cd backend; python -m pytest -q`
Expected: PASS。**期望数自己数**（`--collect-only -q` 末行），不要照抄——Plan 01 有 9 次「期望数与实列数不符」，全部因为照抄。基线 453，本 Task 会加约 6–10 条（依赖守卫 1、allow-list 守卫 3 改写、列宽遍历扩展、索引存在性、`tested_on` 截断、`test_date` 不漂移、`COLUMN_BY_ITEM` 漂移）。

再跑 `--cov=app.domain --cov-branch`：仍须 **Miss 0 / BrPart 0 / 100%**（`COLUMN_BY_ITEM` 进 domain 后它的新行必须被覆盖）。

- [ ] **Step 7: 变异验收**

1. 把 `run_stratify.py` 的 `from app.domain.indicators import COLUMN_BY_ITEM` 改回 `from app.seed.fitness import …` → 依赖守卫必须红。
2. 在 `app/domain/` 任一文件加 `from os import listdir` → allow-list 守卫必须红（**这是终审 A 实测能绕过旧 deny-list 的 14 种写法之一**）。
3. 把 `_results_of` 的 `.where(tested_on <= as_of)` 删掉 → 新增的截断测试必须红。
4. 把 `test_date` 加回 upsert 值 → 「不漂移」测试必须红。

按硬规矩 #22 报告**变异集**（单独还是叠加）与**变红的测试函数条数**。

- [ ] **Step 8: Commit**

```
git add -A backend/app backend/tests .gitattributes
git commit -F <临时文件>   # 中文，说明清偿了终审 C 组哪几项
```

---

