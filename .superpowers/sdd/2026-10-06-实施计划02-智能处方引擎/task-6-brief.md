# Task 6 简报 — `prescription` / `weekly_adjustment` 两张表 + 五触发条件（`triggers.py`）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `3a5bd40`，173442 B / 990 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 6 全节（含预检更正 P6-A1..A12）**。Task 1–5 与 Task 7–9 的正文**不在本简报里**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`3a5bd40`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **679 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**（带 `--cov` 时是 `678 passed, 1 skipped`，那 1 个 skip 是 `test_backfill.py` 既有的墙钟断言）。
**表数基线**：**16 张**（本 Task 后 **18 张**）。
**公开面基线**：`app.domain.prescription.__all__` = **43**；`_PRESCRIPTION_PUBLIC_BASELINE` = **43** 个二元组；`_MODELS_PUBLIC_BASELINE` = **33** 个名字（本 Task 后 **35**）。
**架构守卫扫描面基线**：**32**（pipeline 7 + db 11 + domain 14）；本 Task 加 1 个 domain 模块 → **33**。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`（Windows Smart App Control 拦 `.pyd`），立刻停手报给控制者**，不要动系统安全设置、不要升降级依赖。

**⚠️ 本 Task 有 3 条 Critical 级预检更正，全部是「计划原文要求的东西今天做不到 / 与已结案的 Task 5 冲突」：**
- **P6-A1**：**Step 6 的两条集成测试写不出来**（`prescription_stage.py` 是 Task 7 才建的）。**已整体移到 Task 7**，你只做 Step 6b 那条纯函数确定性测试。
- **P6-A2**：**不要往 `assembly_snapshot` 加 `"previous_had_overrides"` 键**——Task 5 刚钉死「`assemble` 恰好 12 键、`apply_safety` 至多追加 3 键」两条守卫，加第 16 个键会让它们变红。改成 `prescription` 表的 **Boolean 列**。
- **P6-A3**：`prescription_template` 表里**没有 `microcycle_weeks`**（实测 10 列），而触发 3 与 `valid_to` 都要它 → **给 `prescription` 表加一列快照下来**。**刻意不给 `prescription_template` 加列。**

**⚠️ 本 Task 最容易踩的坑是 P6-A5**：`test_models.py` 里钉住表数的地方**有六处**（含函数名 `sixteen`、两处断言的**中文消息**里也写着「16 张表」、一段注释里**逐字印着的 grep 命令与计数**），漏一处就红。计划的新增 **Step 0** 给了一张「要找的原文 → 改成什么」的表，**照它逐格做**。

## 1. 执行强度（账本 Ruling 145，用户 2026-10-08 裁定）

**目标：1–2 轮 fix round**（Task 5 用了 1 轮）。

**保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（`Miss 0 / BrPart 0`）；3 条变异（见 Step 7）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿。

**取消（不要为这些返工）**：纯散文精度 → 记进报告的「**待清扫**」清单。**但 Critical 级问题（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修。**

**⚠️ 若你认为本简报/计划某条决定是错的，顶回来。** Plan 02 到目前为止实现者顶回控制者 **12 次，12 次都是对的**（最近 6 次见账本 Ruling 148）。共同点：控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。**你在代码现场，你的判断优先。** 顶回时不要静默偏离，写进报告的「关切」节。

## 2. 变异取证的纪律（硬规矩 #83，Task 5 实测撞过）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + 设 `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。
**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`。Task 5 的实现者做过一次**等长改动**（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**（sha256 已还原成功而 pytest 仍报变异行为）。**假绿更危险**：它会让你以为一条守卫还在工作。
每条变异要写明：**改了哪一行 → 哪条测试的哪个断言分支变红（贴那一句 `assert`）→ 三重还原后的 sha256 与变异前逐字相同**。

## 3. 报告要求

写进 `task-6-report.md`。⚠️ **这个文件在 `.superpowers/` 下，必须用 python 写**（`write_bytes` 一次性写，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它** —— IDE 曾把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB。

报告至少 7 节：
1. **环境与基线复现**（SQLAlchemy 版本、开工前 `pytest -q` 的结果）
2. **Step 0 的九格逐格落地**（P6-A5 那张表：每格给「找到的原文 → 改成什么 → 在哪个文件」）
3. **两张表的最终列清单**（逐列给名字与类型，含 P6-A2/A3/A8 新增的三列）+ `_in_domain` 的两个 CHECK 的名字
4. **`triggers.py` 的公开面与五条触发的实现口径**（含 P6-A6 的 `Layer.INSUFFICIENT.value`）
5. **变异取证**（3 条 + M0 + M1，按第 2 节的纪律）
6. **待清扫清单** + **关切**（你认为计划错了的地方、你**没按派单做**的地方，0 处也要写「0 处」）
7. **最终验收**：passed 数（679 → ?）、覆盖率四格、`__all__`（43 → ?）、`_MODELS_PUBLIC_BASELINE`（33 → ?）、表数（16 → 18）、扫描面（32 → 33）、三个禁区指纹、`git diff -- backend/data` 为空

## 4. 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格 / 表数 / `__all__` 与 `_MODELS_PUBLIC_BASELINE` 的新值 / 扫描面 / 3 条变异的结论 / Step 0 九格是否全部落地 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

---


# 实施计划 02：智能处方引擎

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01 产出的红黄绿分层结果，按「层 × 主导短板 × 体成分」装配成可复现、可审校、可被教师覆盖的 4 周运动处方，并接进每日批处理管道。

**Architecture:** `app/domain/prescription/` 是无 I/O 的纯函数叶子层（匹配、强度换算、装配、安全后置、覆盖、触发判定），模板与动作等价映射是 `backend/data/` 下带版本号的静态 YAML（体育专家可独立审校），`app/pipeline/prescription_stage.py` 负责落库与幂等。处方**不每天重发**——只有 spec §5.2 的五个触发条件之一成立时才生成，而分层重算仍然每天跑。

**Tech Stack:** Python 3.11.1、SQLAlchemy 2.1、SQLite（`PRAGMA foreign_keys=ON`）、PyYAML、pytest + pytest-cov。不引入新依赖。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md` —— 本计划实现 **§4.4（处方数据模型）、§5.2（五个触发条件）、§7.1–7.5（智能处方层全部）、§8.4（骨架 + 周微调两层拆分）、§11.2（B 类算法降级）、§12（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）**。

**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的十条见 Global Constraints。

---

---

## ⚠️ Task 重编号对照表（2026-10-08 用户裁定后）

用户裁定「后端算法层面要求不是很高，够产出合理的 4 周训练包即可」，故原 Task 5/6/7/8 合并、原 Task 12 砍掉性能压测。本计划从 **12 个 Task 变成 9 个**：

| 原编号 | 新编号 | 处置 |
|---|---|---|
| Task 1–4 | Task 1–4 | 不变（**已全部结案**，HEAD `dfa7580`，592 passed） |
| Task 5 `intensity.py` | **Task 5 的 5.1** | 合并；砍掉 FOX 公式与 `HrmaxFormula` 枚举 |
| Task 6 `assembler.py` | **Task 5 的 5.2** | 合并；砍掉三档系数的 10 组穷举矩阵 |
| Task 7 `safety.py` | **Task 5 的 5.3** | 合并；**安全关键的决定一条没砍** |
| Task 8 `override.py` | **Task 5 的 5.4** | 合并；砍掉五种 kind 的穷举边界 |
| Task 9 两张表 + 五触发 | **Task 6** | 保留，原文不动 |
| Task 10 接入管道 | **Task 7** | 保留，原文不动 |
| Task 11 本周训练单读模型 | **Task 8** | 保留，原文不动 |
| Task 12 黄金用例 + 性能 + 勘误 | **Task 9** | 保留，**删掉 p95 性能压测**（Step 2） |

**⚠️ 已结案的 Task 1–4 正文里的交叉引用未逐条重写**（用户同日裁定「砍文档精度」）。读那四节时若撞到 `Task 5`–`Task 12` 的字样，一律按上表折算；其中「**Task 7 只需写入 `prescription_count`**」（Task 1 节）、「若你判断某一项该推到 Task 5」（Task 4 节）、以及 Task 2/3 节里指向 `safety.py` 与 §14 清单的四处已就地更正；**其余保持原样、按上表折算**。

**同日裁定的执行强度调整**（记进账本作为正式裁定）：**保留** TDD、`app/domain/` 分支覆盖 100%、安全关键路径的变异测试、每个 Task 一轮评审、控制者预检扫描；**取消**「纯散文精度导致的 fix round」（注释里某个数字与实测不符不再单独开一轮，攒到 Task 9 一次性清扫）与「控制者对每个数字的独立复跑」。目标：每个 Task 从 3–6 轮往返降到 **1–2 轮**。

## Global Constraints

- **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(`；不得出现 `read_csv` / `read_text` / `Path(` / `__file__` / `json.load` / `os.listdir` / `import os`。**时间与随机数一律由调用方注入**，参考表一律由 `app/refdata.py` 加载后**作为参数传入**。守卫是 `tests/architecture/test_domain_purity.py`（Task 1 会把它从 deny-list 改成 allow-list）。
- **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令**必须带 `--cov-branch`**：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。
- **单一所有者**：任何常量/词表/权重只允许有一个住址。Plan 01 为此立过 6 条裁定（Ruling 35/36/63/152/156/190）。本计划新增的 `ITEM_BUCKET` 消费、模板维度词表、`impact_level` 词表、`exercise_ref` 词表都必须指向唯一所有者，且**各有一条漂移测试**。
- **断言两侧不得同源**（硬规矩 #35）：期望值一律**字面写在测试里**，不从被测常量读回来跟自己比。Plan 01 因此吃过三次亏（Ruling 166/186/216-M3）。
- **散文必须带口径**（硬规矩 #19/#20/#25/#29/#36/#39/#43）：注释与 docstring 里出现的每个数字都要能指到产生它的那条命令；每个因果机制都要附 `文件:行 + 引文`；尺寸/时长/速率必须带单位与进制、带 n 与区间；**不得印未经多样本验证的概率模型**；凡写下测量条件，必须同时写「哪条测试会在它失效时变红」，写不出来就标「历史实测，不被守卫」。
- **行号一律取 shell 口径**（硬规矩 #30/#37）：`Read` 工具的行号在本仓**不可靠，且不是一个可以补偿的固定偏移**——Plan 02 Task 1 fix round 4 实测偏移 **0 / −1 / −2 在不同区段并存**，且**同一行内容两次调用分别被标 449 和 450**（对自己都不自洽），报出的文件总行数也偏小（`task-1-report.md` 在 fix round 4 落笔当时：`Read` 报 1031 行、实为 2616 个 LF 行；**该文件持续增长，这是一时点样本、不是稳定量**）。此前已四次误导，故一律不用。行号引用绑定 commit。
- **PowerShell**：分隔用 `;`，不支持 `&&`/`||`；**没有 heredoc**；**反引号会被吃掉**；`python -c` 里字符串一律用单引号，需要双引号就写临时 `.py`（放 `$env:TEMP`）。**所有写文件走 python**（`Add-Content` 静默写坏中文）。commit 信息用 python 写 UTF-8 临时文件 + `git commit -F`。
- **落盘唯一权威是 shell**；**`git checkout` / `git switch` / `git merge` 会按 `core.autocrlf` 重写工作树**（硬规矩 #46），事后必须复核所有「按字节哈希」的断言。`backend/data/` 已由 `.gitattributes` 钉为 `eol=lf`，**本计划新增的 YAML 必须落进同一条规则**。
- **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/national_standard_2014.csv`（sha256[:16] 恒为 `D2C8E539E2FA0029`，由指纹测试守卫）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`，要落 CSV 就 `write_csv(ds, <临时目录>)`。
- **`app/seed/` 自 Plan 01 结案后重新冻结**（Task 1 的依赖迁移会动它一次，见 Task 1 的解冻范围，之后不再动）。

## Review Focus

spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。下面五类输入/状态是 spec **没有覆盖**、而一个真实使用者最可能撞上的，每类都在拥有该代码的 Task 里补了测试：

1. **模板 YAML 被专家改坏**（少一个键、`week_deltas` 长度与 `microcycle_weeks` 不符、`exercise_ref` 指向不存在的动作、`reachable: true` 但维度组合不可达）→ 必须在**加载时**响亮失败并指出是哪个文件哪一行，而不是在装配到某个学生时才炸。归属 Task 3。
2. **同一个学生在同一天被两次触发**（管道重跑、或教师手动请求与自动触发撞上）→ 必须产出一条处方而不是两条，且第二次是幂等的 no-op 或明确的 `replaced`。归属 Task 6。
3. **学生当天没有分层结果**（`valid_count < 4` → `insufficient_data`，Z0 闸门拦下）→ **不得生成处方**，且必须留下可交代的痕迹（不是静默跳过）。Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 6。
4. **年龄缺失或异常**（`Student.birth` 为空、或算出年龄 ≤ 0 / ≥ 100）→ Tanaka 公式会给出荒谬的 HRmax（如 `208 − 0.7×0 = 208`），进而给出危险的目标心率区间。必须响亮拒绝或降级到 `needs_review`，**不得静默装配**。归属 Task 5（5.1）。
5. **安全规则命中但 `exercise_equivalence.yaml` 里找不到等价动作**（spec §7.4 明写「不静默跳过」）→ 处方状态置 `needs_review`、写 `warning` 日志、教师端标记「需人工复核」。这是 spec 唯一一处显式要求「宁可不自动，也不要自动错」的地方，必须有测试钉住**它没有被静默跳过**。归属 Task 5（5.3）。

---

## File Structure

**新建（生产）**

| 路径 | 职责 |
|---|---|
| `backend/app/config.py` | `DEFAULT_DB_URL` / `DEFAULT_CSV_DIR` 的唯一所有者（从 `app/seed/generate.py` 迁入，Task 1） |
| `backend/app/adapters/factory.py` | `build_adapter(kind, **kw) -> DataSourceAdapter`，CLI 与将来的 FastAPI 依赖注入共同消费（Task 1） |
| `backend/app/domain/prescription/__init__.py` | 公开面重导出 |
| `backend/app/domain/prescription/exercises.py` | **动作库的值对象**：`ImpactLevel` / `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable`；**不读盘**（Ruling 96：与 `app/domain/tables.py` 的 `StandardTable` 同构——值类型住 domain、加载器住 domain 外、加载器 import 值类型） |
| `backend/app/domain/prescription/templates.py` | 模板的**数据结构**（`@dataclass(frozen=True)`）与维度词表；**不读盘**（`ImpactLevel` 自 Ruling 96 起住在 `exercises.py`，本模块按 domain 内部依赖方向 import 或 re-export） |
| `backend/app/domain/prescription/match.py` | 层 × 主导短板 × 体成分 → 模板（含 `reachable` 与 `review.status` 判定） |
| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（**简化版只实现 Tanaka**，见 Task 5 的 5.1） |
| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配（Task 5 的 5.2） |
| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换（Task 5 的 5.3） |
| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加（Task 5 的 5.4） |
| `backend/app/domain/prescription/triggers.py` | spec §5.2 的五触发条件求值 |
| `backend/app/domain/prescription/weekly.py` | spec §8.4 的「本周训练单 = 骨架第 N 周 × 系数」 |
| `backend/app/refdata_prescription.py` | 加载 **`exercises.yaml`（Task 2）**、18 套模板 YAML（Task 3）与 `exercise_equivalence.yaml`，**校验后**交给 domain（domain 不读盘）；并持有 `sync_exercises(session)`（Ruling 89/P2-A1：不接进 `app/seed/`） |
| `backend/app/pipeline/prescription_stage.py` | 落库、幂等、`prescription_count` 计数 |
| `backend/data/prescription/*.yaml` | 18 套模板，一套一文件，体育专家可独立审校 |
| `backend/data/exercise_equivalence.yaml` | 低冲击等价动作映射 + **版本号** |
| `backend/data/exercises.yaml` | 动作库的**源**（`exercise` 表由它 seed，理由见 Task 2） |

**新建（测试）**：`backend/tests/domain/test_prescription_{templates,match,intensity,assembler,safety,override,triggers,weekly}.py`、`backend/tests/test_refdata_prescription.py`、`backend/tests/pipeline/test_prescription_stage.py`、`backend/tests/architecture/test_layering.py`

**修改**：`backend/app/db/models.py`（Task 1 拆包 + 4 张新表 + `daily_sync_run` 两列 + 索引）、`backend/app/pipeline/daily.py`（接入处方阶段）、`backend/app/pipeline/{daily,backfill}.py`（改用 `app.config` 与适配器工厂）、`backend/tests/integration/test_golden_cases.py`（黄金用例延伸到训练包）、`Document/…设计spec.md`（§14 补 4 项、§7.2 补 speed_flexibility 空洞的勘误）

**`models.py` 拆包**（终审 C 组第 23 项）：Plan 02 加 4 张表、Plan 03 还要加 7 张，届时约 25 张 / 70 KB。Task 1 把 `models.py` 拆成 `models/{organisation,assessment,derived,prescription,feedback,ops}.py` + `models/__init__.py` 重导出，**保持 `from app.db import models` 与 `models.X` 的既有写法不变**（`test_all_fourteen_tables_created` 的 `==` 断言同步改成「按 Plan 递增的期望值」，Ruling 28 的意图不变）。

---

---

## Task 6: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `55874a6`，取证脚本 `t6_probes/_t6_probe{1,2}.py`）

**测试基线**：`679 passed`；`app/domain/` **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**；**16 张表**；`__all__` **43**；扫描面 **32**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P6-A1** | **Critical** | **Step 6 的两条集成测试在本 Task 写不出来。** 它们要求「生成 → 加覆盖 → 触发**重生成**」与「同一天跑两次**管道**」，而 `app/pipeline/prescription_stage.py` 是 **Task 7** 才建的；Task 6 只建两张表 + `triggers.py`（**纯函数**，不落库）。实测 `app/pipeline/` 下今天**没有**任何处方生成阶段。 | **Step 6 整体移到 Task 7**（那里才有管道可跑）。Task 6 只保留「`evaluate_triggers` 对同一输入是确定的」那条**纯函数**测试。⚠️ 与 Ruling 103 同型：派单让实现者做一件当场做不到的事 |
| **P6-A2** | **Critical** | Step 6 要求「在 `assembly_snapshot` 里加 `"previous_had_overrides": true`」，**与 Task 5 刚钉死的键集契约直接冲突**：`assemble` 产出**恰好 12 个键**（`test_assembly_snapshot_keys_are_exactly_the_pinned_set`，多一键少一键都红）、`apply_safety` **追加至多 3 个**（`test_safety_appends_at_most_three_snapshot_keys`）。加第 16 个键会让**两条守卫变红**。 | **不往 `assembly_snapshot` 加键。** 改成 `prescription` 表**自己的一个列** `previous_had_overrides: Mapped[bool]`（`Boolean, nullable=False, default=False`）。理由：它是**关于上一张处方的事实**，不属于「这一张处方的装配输入输出」，放进 `assembly_snapshot` 是**范畴错误**（那一列的契约是「离线复算本张处方」） |
| **P6-A3** | **Critical** | **`microcycle_weeks` 无处可取。** 实测 `prescription_template` 的 **10 列**是 `id / layer / weakness / body_comp / template_ref / version / review_status / reviewer / reviewed_at / reachable`——**没有 `microcycle_weeks`，也没有 `weekly_frequency`**。而触发 3 的判据与 `valid_to` 的算式都要它，且计划明写「从**上一张处方的模板**取，不硬编码 4」。 | **给 `prescription` 表加一列 `microcycle_weeks: Mapped[int]`**（生成时从 `Template.microcycle_weeks` 快照下来）。理由：处方要能**离线复算** `valid_to` 与触发 3，而模板将来会改版（`version` 会变），把周期快照在处方行上才符合 spec §4.3 的可追溯性。**⚠️ 刻意不给 `prescription_template` 加列**——教师端要展示模板周期是 **Plan 03 的 CRUD 层**的活，届时再加；今天加会让 Task 6 回头改 Task 3 已结案的表 + `sync_templates` + `_MODELS_PUBLIC_BASELINE` |
| P6-A4 | Important | 分区穷尽守卫的实测口径（`tests/seed/test_generate.py`）：`assert partitioned == actual`（**新表必须归进三个分区之一，否则这条红**）、三分区互不相交、`assert REFERENCE_TABLES == ("exercise", "prescription_template")`（**字面钉住，不动**）、`for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0`（**seed 阶段必须 0 行**）。且该文件注释里**已经预告过这个决定**：「⚠️ 那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区」。 | `prescription` 与 `weekly_adjustment` **都归 `DATA_TABLES`**（9 → **11**）。这与「seed 阶段 0 行」的断言天然相容（处方是管道产物，不由 `seed_database` 写）。**且必须同时改掉那段预告注释**——「届时」到了 |
| P6-A5 | Important | `test_models.py` 要改的**远不止「表数 16 → 18」**。实测命中点：① 函数名 `test_all_sixteen_tables_created`；② **两处** `assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"`（**中文消息里也有「16 张表」**）；③ `assert len(Base.metadata.tables) == 16`；④ 一段注释里**逐字印着 grep 命令**与「**3** 处本段的散文」的计数；⑤ 另一处注释引用了那个**函数名**；⑥ `assert len(_MODELS_PUBLIC_BASELINE) == 33`。 | 六处**全部列出**（见下方 Step 1 的清单）。`_MODELS_PUBLIC_BASELINE` **33 → 35**（加 `Prescription` 与 `WeeklyAdjustment` 两个类名）。⚠️ `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**不动**——两张表进已有的 `models/prescription.py`，不新增子模块 |
| P6-A6 | Important | 实测 `Layer` 成员 = `[('RED','red'), ('YELLOW','yellow'), ('GREEN','green'), ('INSUFFICIENT','insufficient_data')]`，`INSUFFICIENT = "insufficient_data"` 住在 `app/domain/stratify.py`。 | `triggers.py` **不得硬编码 `"insufficient_data"` 字面串**，要用 `Layer.INSUFFICIENT.value`（单一所有者，Global Constraint #3），并配一条漂移测试。⚠️ import 走**绝对导入** `from app.domain.stratify import Layer`（与 `match.py` 同口径；同包兄弟才走 level 1 相对导入） |
| P6-A7 | Important | 逻辑 id 的列名**两套**：`prescription_template` 的列叫 **`template_ref`**（Task 3 按 spec §4.4 勘误定的），而计划 Task 6 写 `prescription` 表的列叫 `template_id`。 | DB 列统一用 **`template_ref`**（与 `prescription_template.template_ref` 同名，FK 关系一目了然）。**domain 侧不动**：`Template.template_id` 与 `LastPrescription.template_id` 保持 `template_id`（spec §7.2 的字面）。**⚠️ 这个「domain 叫 `template_id`、DB 列叫 `template_ref`」的对照必须写进 docstring**，否则 Task 7 的实现者会以为是两个东西 |
| P6-A8 | Important | `weekly_adjustment` **没有 `batch_id` 列**，而计划 Task 7 写着「`_replay_cleanup` 的清单要加上 `prescription` 与 `weekly_adjustment`（**按 `batch_id` 删**）」。实测 `repo.delete_by_batch(session, model, batch_id)` 要求模型有 `batch_id`。 | **Task 6 就给 `weekly_adjustment` 加 `batch_id` 列**（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构）。理由：① `delete_by_batch` 是既有的、被测试覆盖的路径，改用级联删要新写一段逻辑 + 新配测试；② 「按批删」是本仓一致的幂等手段；③ 一列的成本远低于一段新逻辑。⚠️ **必须在 Task 6 就加**——Task 7 才发现就要回头改一张已结案的表（硬规矩 #11 的教训） |
| P6-A9 | Minor | `prescription.status` 的 CHECK 值域 `{active, replaced, archived, needs_review}` 4 个值，最长 `needs_review` = **12** 字符，`String(16)` 够。`weekly_adjustment.source` 值域 `{auto, teacher}`，最长 `teacher` = **7**，`String(8)` 够。 | 无需更正，**但两个 CHECK 都要用 `_shared.py` 的既有 `_in_domain(column, allowed, name)` helper**（不要手写 `CheckConstraint`），且值域集合要作为**类常量**声明（与 `Exercise.IMPACT_LEVELS` / `PrescriptionTemplate.LAYERS` 同口径） |
| P6-A10 | Minor | 实测 `daily_sync_run` **19 列**，`prescription_count` 与 `alert_count` **都已存在**（Plan 01 就建好了）。 | 无需更正（计划 Task 7 的说法对）。**Task 6 不写这两列的值**，Task 7 才写 `prescription_count` |
| P6-A11 | Minor | 计划的 `**Files:**` 行只列了 `triggers.py` / 测试 / `models/prescription.py` / `test_models.py`，**漏了 `tests/seed/test_generate.py`** —— 而 P6-A4 那条分区穷尽守卫**一定会红**。 | `**Files:**` 行补上 `backend/tests/seed/test_generate.py`（`DATA_TABLES` 9 → 11 + 改那段预告注释） |
| P6-A12 | — | **控制者自查**：本 Task 的 12 条里 **P6-A1 / P6-A2 两条是「Task 5 结案改变了 Task 6 的前提」而控制者没有传导**——P6-A2 撞的正是 Task 5 fix round 1 刚钉死的键集契约，而那条契约是**控制者自己在 Ruling 148 里裁定的**。 | → **补硬规矩 #86：每个 Task 结案时，必须扫一遍后续所有 Task 的正文，找出「被本次结案改变的前提」并当场更正。** 依据：这与硬规矩 #75（P2-A1 的裁定没传导到 Task 3，同一缺陷原封不动重演）是**同一根因的第 2 次**，而 #75 只覆盖了「预检裁定」这一半，没覆盖「结案产出」 |


**Files:** Create `backend/app/domain/prescription/triggers.py`、`backend/tests/domain/test_prescription_triggers.py`；Modify `backend/app/db/models/prescription.py`（加两张表）、`backend/app/db/models/__init__.py`（重导出两个新类）、`backend/tests/db/test_models.py`（**六处**，见 P6-A5 的清单）、**`backend/tests/seed/test_generate.py`（`DATA_TABLES` 9 → 11 + 改那段预告注释，P6-A4 / P6-A11）**

**Interfaces:**
- Produces:
  - `TriggerReason(str, Enum)`：`FIRST_STRATIFICATION` / `LAYER_CHANGED` / `MICROCYCLE_EXPIRED` / `SEMESTER_DATA_REFRESHED` / `TEACHER_REQUESTED`（spec §5.2 的五条，**顺序即 spec 的编号**）
  - `TriggerInput`（frozen）：`as_of: dt.date` / `current_label: str` / `current_template_id: str | None` / `last_prescription: LastPrescription | None` / `latest_assessment_date: dt.date | None` / `teacher_requested: bool`
  - `LastPrescription`（frozen）：`generated_on: dt.date` / `template_id: str` / `label_at_generation: str` / `microcycle_weeks: int` / `status: str`
  - `evaluate_triggers(inp: TriggerInput) -> tuple[TriggerReason, ...]`（**返回全部命中的**，不是第一个——落库时全部写进 `prescription.trigger_reasons`，教师端要能看到「为什么今天换了处方」）

**spec §5.2 五条的精确口径（每条都要有测试）：**

| # | 触发 | 判据 | 决定 |
|---|---|---|---|
| 1 | 学生首次产生分层结果 | `last_prescription is None` 且 `current_label != Layer.INSUFFICIENT.value`（**P6-A6：不得硬编码字面串**） | **`insufficient_data` 不算「产生了分层结果」**（Review Focus 第 3 条）。Z0 闸门拦下的学生**不得生成处方** |
| 2 | 分层标签发生变化 | `last_prescription is not None and current_label != last_prescription.label_at_generation` | 比较的是**生成当时**的标签，不是上一次运行的标签——否则「黄→红→黄」会在第三天又触发一次 |
| 3 | 当前处方 4 周到期 | `as_of - last_prescription.generated_on >= timedelta(weeks=microcycle_weeks)` | `microcycle_weeks` 从**上一张处方的模板**取，不硬编码 4（模板可以是别的周期）。**`>=` 不是 `>`**：第 28 天当天就该换 |
| 4 | 学期末体测/体成分数据刷新 | `latest_assessment_date` 晚于 `last_prescription.generated_on`，且该日期是 `week16` 那一批 | ⚠️ **「学期末」的口径 spec 没给**。决定：`latest_assessment_date > last_prescription.generated_on` 即触发（**任何**新采集都算刷新，不限 week16）。理由：week8 的二次采集同样改变了判定输入，而「只在 week16 触发」会让 10 月的数据变化拖到 12 月才反映到处方上。**这是工程决定，须登记 spec §14** |
| 5 | 教师手动请求 | `teacher_requested` | 无条件触发，**且优先级最高**（教师点了就要生成，即使其余四条都不成立） |

**决定：**
- **`current_label == Layer.INSUFFICIENT.value`（实测该值就是 `"insufficient_data"`）→ 返回空 tuple**，无论其余条件是否成立。**⚠️ P6-A6：用 `Layer.INSUFFICIENT.value`，不要在 `triggers.py` 里写第二份字面串**（单一所有者，Global Constraint #3）；import 走**绝对导入** `from app.domain.stratify import Layer`（与 `match.py` 同口径），并配一条漂移测试字面钉住 `Layer.INSUFFICIENT.value == "insufficient_data"`。**这一条要放在函数最前面**，并且是 Review Focus 第 3 条的落点。理由与 Plan 01 的 Z0 闸门同构：数据不足时产出任何结果都是把「不知道」讲成「知道」。
- **同一天被两次触发只生成一张处方**（Review Focus 第 2 条）：这不是 `triggers.py` 的职责（它是纯函数），而是 Task 7 的落库幂等——`prescription` 表加 `UniqueConstraint("student_id", "generated_on")`。**但 `triggers.py` 要有一条测试证明它对同一输入是确定的**（同输入 → 同输出，无随机、无时钟）。
- **`prescription` 表**按 spec §4.4 **+ 三处预检更正**：`id` / `student_id` / `generated_on: Date` / **`template_ref: String(32)`（P6-A7：不叫 `template_id`，与 `prescription_template.template_ref` 同名）** / **`microcycle_weeks: Integer`（P6-A3 新增：`prescription_template` 表里没有它，触发 3 与 `valid_to` 都要用它，故快照在处方行上）** / `training_package: JsonText` / `assembly_snapshot: JsonText` / `safety_substitutions: JsonText` / `teacher_overrides: JsonText` / **`previous_had_overrides: Boolean, nullable=False, default=False`（P6-A2 新增：取代往 `assembly_snapshot` 加第 16 个键的那个方案）** / `status: String(16)` + CHECK ∈ `{active, replaced, archived, needs_review}` / `valid_from: Date` / `valid_to: Date | None` / `trigger_reasons: JsonText` / `batch_id`（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构，供 `_replay_cleanup` 按批删）。**⚠️ P6-A9：两个 CHECK 一律用 `_shared.py` 的 `_in_domain(column, allowed, name)`，值域作为类常量声明（与 `Exercise.IMPACT_LEVELS` / `PrescriptionTemplate.LAYERS` 同口径），不要手写 `CheckConstraint`。**
- **`valid_to` 的处理与 Plan 01 相反**：Plan 01 的 `stratification_result.valid_to` 恒 NULL（刻意不关账，否则重放要跨批改写）。**`prescription.valid_to` 要真的填**：`= generated_on + timedelta(weeks=microcycle_weeks) - timedelta(days=1)`，因为「当前生效的处方」是 Plan 02 的核心查询，而处方**天然有有效期**（4 周微周期）。**换处方时把上一张置 `replaced` 并关账 `valid_to`**——这与 Plan 01 的决定不矛盾（分层结果是每日快照、无处方那样的自然有效期），但**必须在一处写明为什么两者不同**，否则下一个人会以为其中一个是 bug。
- **`weekly_adjustment` 表**按 spec §4.4 + §8.4：`id` / `prescription_id` / `week: int`（1-based）/ `factor: Float` / `reason: str` / `source: String(8)` + CHECK ∈ `{auto, teacher}`（P6-A9：同样走 `_in_domain`）/ `created_at: DateTime` / **`batch_id`（P6-A8 新增：外键到 `daily_sync_run`。计划 Task 7 写着「`_replay_cleanup` 按 `batch_id` 删 `weekly_adjustment`」，而 `repo.delete_by_batch` 要求模型有这一列——不加就要在 Task 7 新写一段级联删逻辑并新配测试。⚠️ 必须在 Task 6 就加，否则 Task 7 要回头改一张已结案的表，硬规矩 #11）**。**本 Task 只建表 + 教师路径**；`auto` 来源（预警触发减量 20%）留给 Plan 03，在表注释里写明。

- [ ] **Step 0: 先改「表数」的六处 + 分区的一处（P6-A5 / P6-A4）**

按 Ruling 145，这类「一个数散落在多处」的改动**先一次改完再写测试**，否则测试会红在莫名其妙的地方。**全部按可 grep 的原文找、不要按裸行号找（硬规矩 #76/#78）**：

| 文件 | 要找的原文 | 改成 |
|---|---|---|
| `tests/db/test_models.py` | `def test_all_sixteen_tables_created` | `def test_all_eighteen_tables_created` |
| 同上 | `assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"`（**两处**，中文消息里也有「16 张表」） | `== 18` + 「18 张表」 |
| 同上 | `assert len(Base.metadata.tables) == 16` | `== 18` |
| 同上 | 那段**逐字印着 grep 命令**与「**3** 处本段的散文」的注释 | 计数跟着改（改完自己再 grep 一次核实） |
| 同上 | 另一处引用 `test_all_sixteen_tables_created` 这个**函数名**的注释 | 跟着改函数名 |
| 同上 | `assert len(_MODELS_PUBLIC_BASELINE) == 33` + 那个清单本身 | **35**，清单加 `"Prescription"` 与 `"WeeklyAdjustment"`（**按字母序插进去**，清单今天是排序的） |
| `tests/seed/test_generate.py` | `DATA_TABLES = (…9 个…)` | 加 `"prescription"` 与 `"weekly_adjustment"` → **11 个** |
| 同上 | `REFERENCE_TABLES` 上方那段「⚠️ 那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区」的预告注释 | **改掉**——「届时」到了，写明归 `DATA_TABLES` 与理由 |
| 同上 | `assert REFERENCE_TABLES == ("exercise", "prescription_template")` | **不动**（字面钉住，两张新表不进参考数据分区） |

⚠️ `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**不动**——两张表进已有的 `models/prescription.py`，不新增子模块。

- [ ] **Step 1: 写失败测试**

穷举触发矩阵。五条触发 × {成立, 不成立, 边界} + 组合，至少 20 条。重点：
- `test_insufficient_data_label_never_triggers`（**即使 `teacher_requested=True`**——这条要想清楚：教师手动请求一个数据不足的学生，应该生成吗？**决定：不生成**，返回空 tuple，但 `evaluate_triggers` 的调用方要把这件事留痕。理由同上：数据不足时产出处方是把「不知道」讲成「知道」。**若你不同意这个决定，报为最高优先级关切**，因为它会让教师端「重新生成」按钮对这类学生无声失败）
- `test_first_stratification_triggers_only_once`
- `test_layer_change_compares_against_the_label_at_generation`（构造「黄→红→黄」三天，断言第三天**不**触发）
- `test_microcycle_expiry_is_inclusive_on_day_28`（`>=` 边界，字面写死日期）
- `test_microcycle_weeks_comes_from_the_previous_template_not_a_hardcoded_four`（构造一个 `microcycle_weeks=2` 的上一张处方，断言第 14 天触发）
- `test_assessment_refresh_triggers`（触发 4 的工程口径）
- `test_teacher_request_triggers_alone`
- `test_multiple_triggers_all_reported_in_spec_order`（返回 tuple 的顺序 = `TriggerReason` 的声明序 = spec §5.2 的编号序）
- `test_evaluate_triggers_is_deterministic`（同输入两次，结果逐字相同）
- `test_no_last_prescription_and_insufficient_label_returns_empty`

- [ ] **Step 2–5: 跑失败 → 实现 → 跑通**

- [ ] **Step 6: ~~集成测试~~ —— ⚠️ P6-A1：整体移到 Task 7**

> 原文这里要求在 `backend/tests/pipeline/` 写两条集成测试（`test_regeneration_does_not_inherit_teacher_overrides` 与 `test_same_day_regeneration_is_idempotent`）。**它们在本 Task 写不出来**：两条都要「跑管道 / 触发重生成」，而 `app/pipeline/prescription_stage.py` 是 **Task 7** 才建的；Task 6 只有两张表 + `triggers.py`（纯函数、不落库）。
> **两条测试原文照搬到 Task 7 的 Step 6**（那里已经补进去了）。
> ⚠️ 其中第一条原本还要求「在 `assembly_snapshot` 里加 `"previous_had_overrides": true`」——**这个方案已被 P6-A2 否掉**（会让 Task 5 钉死的 12 键 / +3 键两条守卫变红），改成 `prescription.previous_had_overrides` 这个**独立的 Boolean 列**。

- [ ] **Step 6b: 本 Task 唯一保留的确定性测试**

`test_evaluate_triggers_is_deterministic`（同输入两次，结果逐字相同，无随机、无时钟）——这条是**纯函数**测试，在本 Task 就能写，且是 Global Constraint「时间与随机数一律由调用方注入」的落点。

- [ ] **Step 7: 变异验收 + Commit**

变异（**只做 3 条**，Ruling 145）：① 把 `Layer.INSUFFICIENT.value` 的早退删掉 → Review Focus 第 3 条的测试红；② 触发 3 的 `>=` 改成 `>` → 第 28 天边界测试红；③ 触发 2 改成比较「上一次运行的标签」而不是 `label_at_generation` → 「黄→红→黄」那条测试红。**每条按硬规矩 #65 写明哪个断言分支开火，并按 M0/M1 双对照取证；跑测试前按硬规矩 #83 清 `__pycache__` 并设 `PYTHONDONTWRITEBYTECODE=1`。**

---
