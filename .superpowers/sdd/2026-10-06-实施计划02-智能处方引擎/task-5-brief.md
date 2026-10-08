# Task 5 简报 — 处方装配（简化版）：`intensity.py` + `assembler.py` + `safety.py` + `override.py`

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `c8e26b8`，151467 B / 938 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 5 全节（含预检更正 P5-A1..A13）**。Task 1–4 与 Task 6–9 的正文**不在本简报里**（它们已结案或还没轮到）。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`c8e26b8`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **592 passed**（控制者本机实跑，61.84 s）。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **541 stmts / Miss 0 / 132 branch / BrPart 0 / 100%**。
**表数基线**：**16 张**。
**公开面基线**：`app.domain.prescription.__all__` = **24** 个名字；`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`。
**架构守卫扫描面基线**：**28**（pipeline 7 + db 11 + domain 10）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 冒烟，把版本记进报告的「环境与基线复现」节。**Windows Smart App Control 曾在会话中途拦掉 SQLAlchemy 的一个 `.pyd`（文件一个字节都没变），全量测试跑不起来**（账本 Ruling 121/122）。若撞上，**立刻停手报给控制者**，不要自己动系统安全设置。

**⚠️ 本 Task 是四个原 Task（5/6/7/8）的合并，工作量比前面任何一个 Task 都大。** 建议按 5.1 → 5.2 → 5.3 → 5.4 → 5.5 的顺序**分五次 commit**（每节一次），不要攒成一个大 commit。

**⚠️ 本节有 4 条 Critical 级预检更正（P5-A1 ~ P5-A4），全部是「计划原文引用了一个不存在的东西」：**
- **P5-A1**：`Block.structure` 里**没有**「周训练总量」这个字段。实测只有两种键集（时长类 78 个 `{sets, work_min, rest_min}`、次数类 52 个 `{rounds, reps}`）。基准量口径见 5.2 的「⚠️ P5-A1 的基准量口径」段。
- **P5-A2**：同一 `exercise_ref` 在一周内**跨 session 重复，18/18 全部如此**。`weekly_volume = base × sessions_per_week`，不是 `base`。
- **P5-A3**：`when: muscle_low` 的 12 个 addon **必须被消费**（原计划判「无法自动化」是错的）。addon 的量口径 = `weekly_volume 0.0` + `volume_unit "unspecified"` + 一条 warning。
- **P5-A4**：**不许 `import math`**（`ALLOWED_MODULES` 不放行）。用 `int(x)` 与 `-(-x // 1)`，并给 `hr_zone` 加 `hrmax_bpm <= 0` 的拒绝。

**⚠️ Ruling 133（本 Task 的头号约束）**：18 套模板的 130 个 block 里 **82 个是 `intensity: {type: none}`**，按层是 **绿 `{none}` / 黄 `{none}` / 红 `{hrmax_pct, none, onerm_pct}`**。**「模板没给强度」是常态不是例外**；心率相关的测试**必须用红层模板或手工构造的 `hrmax_pct` block**，用黄层写会全绿但什么也没测（假绿）。

## 1. 执行强度（账本 Ruling 145，用户 2026-10-08 裁定）

**目标：1–2 轮 fix round**（不是前面几个 Task 的 3–6 轮）。

**保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（`Miss 0 / BrPart 0`）；4 条安全关键变异（见 5.5 的 Step 4）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源（期望值**字面写在测试里**）；domain 纯净性守卫全绿。

**取消（不要为这些返工）**：纯散文精度。**注释/docstring 里某个数字与实测不符，不要单独返工一轮**——记进报告的「**待清扫**」清单，控制者在 Task 9 一次性清扫。**但 Critical 级问题（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修，不进清单。**

**⚠️ 若你认为本节某条决定是错的，顶回来。** Plan 02 到目前为止实现者顶回控制者的裁定 **4 次，4 次都是对的**（Ruling 67 / dict-vs-Mapping / CE-4 / CE-7）。共同点是：控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。**你在代码现场，你的判断优先。**

## 2. 报告要求

写进 `task-5-report.md`（**⚠️ 不要用编辑器打开 `.superpowers/` 下的大文件**——IDE 曾把陈旧且截断的缓存写回磁盘，永久丢了约 107 KB。一律用 python 追加写）：
1. **环境与基线复现**：SQLAlchemy 版本、开工前的 `pytest -q` 结果。
2. **逐节交付**（5.1 / 5.2 / 5.3 / 5.4 / 5.5）：每节的 commit sha、新增测试数、全量 passed 数、domain 覆盖率四格。
3. **变异取证**：4 条变异逐条给「改了哪一行 → 哪条测试的哪个断言分支变红 → 三重还原后的 sha256」，外加 M0（不变异全绿）与 M1（语义等价改写仍全绿）。
4. **待清扫清单**：散文与实测的偏差（Ruling 145）。
5. **关切**：你认为计划错了的地方、以及你**没按派单做**的地方（**必须显式列出并说明理由**，不要静默偏离）。
6. **公开面变化**：`__all__` 从 24 变成几，`_PRESCRIPTION_PUBLIC_BASELINE` 的新值与那句 `assert len(...) == N` 是否同步改了。
7. **扫描面变化**：28 → 32（domain 10 → 14），并说明架构守卫是否需要改。

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

## Task 5: 处方装配（简化版）—— `intensity.py` + `assembler.py` + `safety.py` + `override.py`

> **本节是原 Task 5/6/7/8 四节的合并（用户裁定，2026-10-08）。** 裁定原文：「后端其实只要不出太大的 bug 就行，后端算法层面要求不是很高……够产出合理的 4 周训练包即可，不追求参数保真度」。
>
> **合并砍掉了什么**：① `HrmaxFormula` 枚举与 FOX 公式（只留 Tanaka；`hrmax` 只有一个生产调用点，将来要加公式不破坏任何契约）；② 三档系数的 10 组参数化穷举（改成「每个分支至少一条」）；③ 闰年生日与 `age_from` ↔ Plan 01 龄组的漂移测试（周岁算法与 Plan 01 `age_group_of` 的上游同源，漂移风险由 Task 7 的端到端测试兜住）；④ 装配器与覆盖的独立变异轮次（只保留**安全关键**的 4 条变异，见 Step 4）；⑤ 原 Task 6 的 `formula` 形参（简化后恒为 Tanaka，快照里的 `"formula"` 键恒为 `"tanaka"`）。
>
> **合并没有砍掉什么（硬要求，一条都不许少）**：① `app/domain/` 分支覆盖 **100%**（spec §12，简化版不豁免）；② 安全规则的严格比较符 + 「没测不得讲成测了没问题」+ 「找不到等价动作不得静默跳过」（Review Focus 第 5 条）；③ `assembly_snapshot` 的键集字面钉死（spec §4.3 可追溯性的处方侧落点）；④ 年龄异常响亮拒绝（Review Focus 第 4 条）；⑤ 覆盖不改模板、`reason` 非空。
>
> **执行强度按用户同日裁定「保正确性、砍文档精度」**：本 Task 目标是 **1–2 轮 fix round**，不是 3–6 轮。散文里的数字若与实测有出入，**记进报告的「待清扫」清单、不单独开一轮**（控制者在结案时一次性清扫）。


### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `dfa7580`，取证脚本 `t5_probes/_t5_probe{1,2,3,4}.py`）

本节是**合并后的新 Task 5** 的预检结果。合并把四节的正文压成一节，**压缩过程中没有重新核对四节各自引用的量**，于是撞出 4 条 Critical——其中 **P5-A1 与 P5-A3 与 Ruling 133 同型**（计划引用一个 YAML 里根本不存在的量）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P5-A1** | **Critical** | `Block.structure` 实测**只有两种键集、无第三种、无交集**：**时长类 78 个** `{sets, work_min, rest_min}`（例 `{sets:4, work_min:3, rest_min:2}`）、**次数类 52 个** `{rounds, reps}`（例 `{rounds:3, reps:10}`）。78 + 52 = 130 ✓。**没有任何名为 `weekly_volume` / `volume` / `base` 的键。** | 计划 5.2 第 3/4 步说的「模板基准量」**不存在**。定口径见下方 5.2 的「⚠️ P5-A1」段：时长类 `base = work_min × sets`（分钟/课）、次数类 `base = rounds × reps`（次/课）、`rest_min` **不计入量**；两种单位不可通约 → `AssembledBlock` **必须新增 `volume_unit` 字段** |
| **P5-A2** | **Critical** | 同一模板内同一 `exercise_ref` **跨 session 重复，18/18 全部如此**。全体 130 个 block 的「一周内出现次数」分布 = **`{2: 24, 3: 42, 4: 64}`**，按层是 **绿全 2 / 黄全 3 / 红全 4**，即**恒等于 `weekly_frequency`**（每个动作在一周的每一课都出现，无一例外）。 | `weekly_volume` 若只是「单次课的量」就**名不符实**（叫 weekly 却是 per-session）。定口径：**`weekly_volume = base × sessions_per_week`**，`sessions_per_week` 由装配器**实测统计**（不假设它等于 `weekly_frequency`），并**新增 `sessions_per_week` 字段**留痕 |
| **P5-A3** | **Critical** | `addons.when` 实测 = **`{body_fat_over: 12, muscle_low: 12}`**；`addons.module` = **`{resistance_priority: 12, energy_expenditure_plus_10pct: 6, energy_expenditure_plus_5min_hiit: 6}`**。分布完全规整：**绿层 6 套全部 `addons: []`**；红层 6 套 = `(body_fat_over → energy_expenditure_plus_10pct)` + `(muscle_low → resistance_priority)`；黄层 6 套 = `(body_fat_over → energy_expenditure_plus_5min_hiit)` + `(muscle_low → resistance_priority)`。 | 原计划只把 addons 挂在「体脂率异常」上，而肌肉量那一行写的是「不自动、只 warning」→ **12 个 `when: muscle_low` 的 addon 永远不会被消费，是模板里的死数据**。**更正：肌肉量 < P10 触发时追加 `when == "muscle_low"` 的 addon**——这**正是** spec §7.4「并提高抗阻模块比重」的落地方式（追加一个 `resistance_priority` 模块，**不重排任何既有结构**）。原判断「无法自动化」是错的 |
| **P5-A4** | **Critical** | `tests/architecture/test_domain_purity.py` 的 `ALLOWED_MODULES` 实测 = `{dataclasses, enum, collections, collections.abc, numpy, typing}`。**`math` 不在其中**；两份守卫里 `math` 出现 **0 次**。 | 计划 5.1 写的 `math.floor` / `math.ceil` **会让纯净性守卫变红**。**更正：不改守卫**（往 allow-list 加模块是扩大 domain 可用面的架构决策），改用 `int(x)`（向下）与 `-(-x // 1)`（向上）。⚠️ `int()` 只在**正数**上等价于 `floor` → `hr_zone` 必须**新增一条 `hrmax_bpm <= 0` 拒绝**的守卫 |
| P5-A5 | Important | `intensity.type` 实测分布 = **`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24**，而 `INTENSITY_TYPES` 有 **4** 个值 → **`rpe` 在真仓出现 0 次**。形状完全规整：`hrmax_pct` → `low`+`high`（各 24）、`onerm_pct` → `value`（24）、`none` → 三者全空（82）。 | `rpe` 那一档**不可达但必须被覆盖**（domain 分支 100%）→ 用**手工构造**的 `Intensity(type="rpe", value=13)` 测。`Intensity.value` 的语义随 `type` 变（`onerm_pct` 是百分比、`rpe` 是 6–20），写进 docstring |
| P5-A6 | Important | 实测 `0.8 * 0.9` = **`0.7200000000000001`**（IEEE754），不是 `0.72`。 | 计划要求「0.72 字面写死」→ 直接相乘的测试**会红**。定口径：`weekly_volume` 的最终值 **`round(x, 1)`**；系数本身用 `pytest.approx`。（`round` 后仍是有限 float，不触 `allow_nan=False` 的 JSON 纪律） |
| P5-A7 | Important | **原计划自相矛盾**：5.2 第 6 步说 `assembly_snapshot` 的键「字面固定 **12** 个」并列出 12 个，但同一节的决定段又要求写 `"volume_factor_fallback"`，5.3 又要求写 `"safety_skipped"`——**这两个键都不在那 12 个里**。 | 拆成两段契约：**`assemble` 产出恰好 12 个键**（字面钉死，多一个少一个都红）；**`apply_safety` 在其上追加至多 3 个键**（`safety_triggers` / `safety_skipped` / `safety_volume_factor`，字面钉死这 3 个名字）。`endurance_score is None` 时**不加**第 13 个键，改成 `volume_factor_band = "unknown"`（信息已在 band 里） |
| P5-A8 | Important | `impact_level` 有**两个住址**：`Block.impact_level`（模板 YAML）与 `ExerciseSpec.impact_level`（动作库 YAML）。Task 3 已验证 130 个 block 零不一致。 | 定口径：**装配器从 `ExerciseSpec`（动作库）取 `impact_level`，不从 `Block` 取**。理由：`exercises.yaml` 是 `impact_level` 的**源**（它是 `exercise` 表的 seed 源），模板里的是**冗余副本**；安全规则必须读源，否则「专家改了动作库、忘了改 18 套模板」会让安全替换静默失效（Global Constraint #3） |
| P5-A9 | Important | **两套不同名的触发词表**：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`）、`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。实测 YAML 的 `addons.when` 取值 = `ADDON_TRIGGERS` ✓ | `SafetyInput` 的三个输入必须**显式映射**到这两套词表。定口径：`safety.py` 里字面写死映射 `{"bmi_over_30": None, "muscle_low_p10": "muscle_low", "body_fat_abnormal": "body_fat_over"}`（BMI>30 **不追加** addon——实测模板里没有 `when: bmi_over_30` 的 addon），并各加**一条漂移测试**字面钉住两个上游词表（防上游改名后静默失配）。词表的所有者仍是 `templates.py` / `exercises.py`，`safety.py` 只**消费** |
| P5-A10 | Minor | `BODY_FAT_LIMIT` 实测**只有 `derive.py` 的一行定义**（`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`）+ 一处消费；计划 5.3 写的是「`derive.py:68-69`」，**行号口径错**，且「明写严格大于」的引文控制者未核。 | 按硬规矩 #78 改成**可 grep 的原文片段**，不写裸行号；「严格大于」的说法降级为「与 Plan 01 同口径，由实现者复核引文后写明」 |
| P5-A11 | Minor | `Sex` 实测住在 **`app/domain/indicators.py`**（`class Sex(str, Enum)`）。计划 5.2 的 `StudentProfile.sex: Sex` **没写它从哪 import**。 | 补明：`from app.domain.indicators import Sex`（**绝对导入**，与 `match.py` 引 `Layer` 同口径） |
| P5-A12 | Minor | 加载器实测有 8 个公开函数：`load_exercises(path=None)` / `exercises()` / `load_equivalence(path=None)` / `equivalence()` / `load_templates(directory=None)` / `templates()` / `sync_exercises(session)` / `sync_templates(session)`。 | 5.2/5.3 要求「吃真仓 YAML」的测试用 **`exercises()` / `templates()` / `equivalence()` 三个进程内单例**，不用 `load_*`（后者每次重解析 18 份 YAML，还各跑一遍 `yaml.compose` 建行号索引）。⚠️ 单例是**进程内共享**的，测试里**不得改写**它 |
| P5-A13 | — | **控制者错误 #139**：预检时用了一个**自己没验证过的正则**（`\(\s*"`）去数 `_PRESCRIPTION_PUBLIC_BASELINE` 的二元组个数，数出 **3**；而同一个文件里就有字面断言 **`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`**，且 `len(__all__) == 24` 双重坐实。 | 计划的「24 个二元组」**是对的，探针是错的**。→ **补硬规矩 #80：用一个探针去数一个已经有字面断言的量，是多此一举且必然自相矛盾——先读那条断言。** 依据：这是「把自己没验证的工具输出当事实」的第 8 次（前 7 次见硬规矩 #53/#57/#59/#60/#76/#77） |

**扫描面复核（计划 5.5 的数字，实测**正确**，无需更正）**：`app/domain` **10** 个 `.py` + `app/pipeline` **7** + `app/db` **11** = **28**；Task 5 新增 4 个 domain 模块 → domain **14** → 扫描面 **32** ✓

**Files:** Create `backend/app/domain/prescription/intensity.py`、`assembler.py`、`safety.py`、`override.py` + `backend/tests/domain/test_prescription_{intensity,assembler,safety,override}.py`；Modify `backend/app/domain/prescription/__init__.py`（公开面重导出）、`backend/tests/test_refdata_prescription.py`（`_PRESCRIPTION_PUBLIC_BASELINE` 24 → 新值）

---

### 5.1 `intensity.py` —— HRmax 与目标心率区间

**Produces:**
- `hrmax(age: float, measured: float | None = None) -> float`：`measured is not None` 时校验 `60 <= measured <= 220`（越界抛 `ValueError`）后直接返回；否则 Tanaka `208 − 0.7 × age`。`age <= 0 or age >= 100` → 抛 `ValueError`，**消息里含实际收到的年龄**（排障用）。
- `hr_zone(hrmax_bpm: float, low_pct: float, high_pct: float) -> tuple[int, int]`：低界**向下**取整、高界**向上**取整（**保守方向：区间略宽比略窄安全**）。`low > high` / `low < 0` / `high > 100` → `ValueError`；**`hrmax_bpm <= 0` → `ValueError`（P5-A4 新增）**。
  ⚠️ **P5-A4：不许 `import math`**——`ALLOWED_MODULES` 实测只有 `{dataclasses, enum, collections, collections.abc, numpy, typing}`，加 `math` 会让纯净性守卫变红。用 **`int(x)`**（向下）与 **`-(-x // 1)`**（向上）。**`int()` 只在正数上等价于 `floor`**（`int(-0.5) == 0` 而 `floor(-0.5) == -1`），故上面那条 `hrmax_bpm <= 0` 的拒绝**不是可选的**——它是这个等价关系成立的前提，必须在 docstring 里写明这层因果。
- `age_from(birth: dt.date, as_of: dt.date) -> int`：**周岁**（生日未过则减 1），不是「年份相减」。`as_of` 由调用方注入，domain 不碰时钟。

**决定：**
- **`hrmax` 不返回 `None`、不静默夹取**（Review Focus 第 4 条）。理由：Tanaka 在 `age = 0` 时给 208 bpm，那是一个**看起来完全正常**的数字，会被装配成一个危险的目标心率区间。**静默产出荒谬值比崩溃危险。**
- **`measured` 参数不被任何生产路径调用**：Plan 01/02 **没有任何心率数据**（`fitness_test_result` 的 8 个原始列里没有心率）。按硬规矩 #39 在 docstring 里写明「为将来的穿戴设备留口，今天只有测试调它」。
- **不实现 FOX 公式**（简化）。spec §14 #14 已把「Tanaka 还是 `220 − 年龄`」列为待确认事项；本 Task 只落 Tanaka，将来切换只改 `intensity.py` 一处，**不需要为此今天就抽象出一个枚举**。

---

### 5.2 `assembler.py` —— spec §7.3 的六步

**Consumes:** Task 3 的 `Template` / `Block` / `Intensity`、5.1 的三个函数、Plan 01 的 `app.domain.indicators.ITEM_BUCKET`

**Produces:**
- `StudentProfile`（frozen dataclass）：`student_id: int` / `sex: Sex`（**P5-A11：`from app.domain.indicators import Sex`，绝对导入**，与 `match.py` 引 `Layer` 同口径） / `birth: dt.date` / `age: int` / `endurance_score: float | None` / `bmi: float | None` / `body_fat_pct: float | None` / `muscle_mass_kg: float | None` / `muscle_p10: float | None` / `measured_hrmax: float | None`
- `AssembledBlock`（frozen）：`exercise_ref` / `exercise_name` / `video_url` / `impact_level` / `intensity_text: str` / `hr_zone: tuple[int,int] | None` / `structure: dict` / `weekly_volume: float` / **`volume_unit: str`（P5-A1 新增，∈ `{"min", "reps", "unspecified"}`）** / **`sessions_per_week: int`（P5-A2 新增，>= 1）**
  ⚠️ **`impact_level` 从 `ExerciseSpec`（动作库）取，不从 `Block`（模板）取**（P5-A8）：`exercises.yaml` 是源、模板里的是冗余副本；安全规则读副本会在「专家改了动作库、忘了改 18 套模板」时静默失效。
- `AssembledSession`（frozen）：`day` / `focus` / `blocks: tuple[AssembledBlock, ...]`
- `AssembledWeek`（frozen）：`week: int`（1-based）/ `delta: float` / `sessions: tuple[AssembledSession, ...]`
- `TrainingPackage`（frozen）：`template_id` / `template_version` / `weeks: tuple[AssembledWeek, ...]` / `assembly_snapshot: dict` / **`paused: bool = False`**
  （`paused` 由 5.4 的 `OverrideKind.PAUSE` 置位，但**字段在本节就定义**——否则 5.4 要回头改一个已定稿的产出类型，那是 Plan 01 吃过 6 次的亏：改了 Interfaces 却没改照抄它的 Step，硬规矩 #11。装配器一律产出 `paused=False`。）
- `assemble(profile: StudentProfile, template: Template, as_of: dt.date, *, exercises: Mapping[str, ExerciseSpec]) -> TrainingPackage`

**六步口径：**

| 步 | 口径 | 决定 |
|---|---|---|
| 1 HRmax | 优先实测，无则 Tanaka | `profile.measured_hrmax` 非空则用它，否则 `hrmax(profile.age)`。**`profile.age` 由调用方从 `birth` 与 `as_of` 算好传入**（不让装配器自己碰日期，避免两个所有者）；但装配器要**校验** `age == age_from(birth, as_of)`，不一致抛 `ValueError`——这是一个廉价的一致性闸门，能挡住「调用方用了错误的 `as_of`」 |
| 2 目标心率区间 | 模板给百分比 → 个体绝对 bpm | 只对 `intensity.type == "hrmax_pct"` 的 block 算；`onerm_pct` / `rpe` / `none` 的 `hr_zone` 是 `None`，`intensity_text` 渲染对应文字（如「70% 1RM」）。**不要给非心率类动作硬塞一个心率区间** |
| 3 周训练总量 | **每课基准量 × 周内课次 × 个体修正系数** | **⚠️ P5-A1：「模板基准量」这个字段不存在**，见下方「P5-A1 的基准量口径」；个体修正系数见下方「三档系数」 |
| 4 4 周递进 | 套用 `progression.week_deltas` | 第 N 周的 `weekly_volume` = **每课基准量 × `sessions_per_week`** × 个体修正系数 × `week_deltas[N-1]`，**`round(…, 1)`**（P5-A6）。**`len(week_deltas) != microcycle_weeks` 在加载时已被 Task 3 拒绝**，装配器不重复校验，但仍要抛 `ValueError`（它可能被喂进一个手工构造的 `Template`），并有一条测试钉住它不是静默截断 |
| 5 动作视频 URL | 从 `exercises` 注入的映射取 | 装配器**不读 DB**（domain 纯净性），`exercises` 由调用方注入。`exercise_ref` 不在映射里 → 抛 `ValueError`（Task 3 的加载校验是第一道，这是第二道；**两道都要有**） |
| 6 快照 | 全部输入输出写入 `assembly_snapshot` | 键**字面固定 12 个**：`formula`（简化后恒 `"tanaka"`）/ `hrmax` / `age` / `as_of` / `endurance_score` / `volume_factor` / `volume_factor_band` / `sex_factor` / `template_id` / `template_version` / `week_deltas` / `weekly_volume_base`。**⚠️ P5-A7：这 12 个是 `assemble` 的完整契约，一个都不许多**（原文另要求的 `volume_factor_fallback` 会是第 13 个键，与本行自相矛盾 → 已删，改用 `volume_factor_band = "unknown"` 承载）；`apply_safety` 的追加键见 5.3。`volume_factor_band` 的值域字面固定为 `{"low", "mid", "high", "unknown"}`；`weekly_volume_base` = **未乘个体系数、未乘 `week_deltas` 的周量总和**（`float`，`round(…, 1)`）。**这一列是 spec §4.3 可追溯性在处方侧的落点**——有了它，任一条处方都能离线复算。加一条测试：同一 `profile` + 同一 `template` + 同一 `as_of` 装配两次，`assembly_snapshot` **逐字段相同**（`as_of` 是 `date` 不是 `datetime`，故不含执行时刻） |


**⚠️ P5-A1 的基准量口径（`Block.structure` 里没有「量」这个字段，必须自己定，登记 spec §14 新 #36）**

实测 `structure` **只有两种键集、无第三种、无交集**（78 + 52 = 130 ✓）：

| 形状 | 个数 | 键集 | 例 | `base` 口径 | `volume_unit` |
|---|---|---|---|---|---|
| 时长类 | **78** | `{sets, work_min, rest_min}` | `{sets:4, work_min:3, rest_min:2}` | **`work_min × sets`** | `"min"` |
| 次数类 | **52** | `{rounds, reps}` | `{rounds:3, reps:10}` | **`rounds × reps`** | `"reps"` |

- **`rest_min` 不计入量**（它是恢复、不是负荷）。**理由要写进 docstring**：把休息算进训练量会让「减量 20%」同时缩短恢复时间，而对红层学生缩短恢复是危险的。
- **两种单位不可通约** → `volume_unit` 是**必需字段**，不是可选修饰。一个裸 `float` 无法回答「38.4 是分钟还是次数」，那会让 spec §4.3 的可追溯性断在这一环。
- **`structure` 既不是这两种形状之一 → 抛 `ValueError`**，**不得静默取 0**（量变 0 会让训练包看起来完全正常、而每个 block 都是空的）。Task 3 的加载器是否已经钉死了这两种形状，**实现者要复核**：若已钉死，装配器仍要抛（它可能被喂进手工构造的 `Template`），但**不重复校验键的类型**（单一所有者）。
- **`sessions_per_week` 由装配器实测统计**（数该 `exercise_ref` 在 `template.sessions` 里出现几次），**不假设它等于 `weekly_frequency`**。实测它今天恰好恒等（分布 `{2:24, 3:42, 4:64}` = 绿全 2 / 黄全 3 / 红全 4），但那是**数据的性质、不是结构的保证**——专家完全可以让某个动作只出现在 2 课里。
  → 配一条守卫测试：断言真仓 18 套模板里**每个 block 的 `sessions_per_week` 都等于该模板的 `weekly_frequency`**。**这条测试今天全绿**；它的价值是「专家改坏了会立刻变红提示」，而装配器**仍按实测统计**（正确行为，不因为测试而假设）。

**可字面写死的算例（控制者实算，`RED-END-ABN-01` 第 1 课，`weekly_frequency = 4`、`week_deltas = [1.0, 1.05, 1.1, 0.85]`）：**

| block | intensity | structure | base | ×4 | 男 20 岁、`endurance_score = 50`（档 `<60` → 0.8，性别 1.0，系数 **0.8**） |
|---|---|---|---|---|---|
| `interval_run` | `{type: hrmax_pct, low: 60, high: 70}` | `{sets:4, work_min:3, rest_min:2}` | `3×4 = 12` min/课 | **48.0 min/周** | 第 1 周 `48.0×0.8×1.00 = `**`38.4`**；第 4 周 `48.0×0.8×0.85 = 32.64 → `**`32.6`** |
| `compound_circuit` | `{type: onerm_pct, value: 70}` | `{rounds:3, reps:10}` | `3×10 = 30` reps/课 | **120.0 reps/周** | 第 1 周 **`96.0`**；第 4 周 `120.0×0.8×0.85 = 81.6 → `**`81.6`** |

`interval_run` 的心率区间：`hrmax(20) = 208 − 0.7×20 = `**`194.0`**；`hr_zone(194.0, 60, 70)` = `(int(116.4), -(-135.8 // 1))` = **`(116, 136)`**。
`compound_circuit` 的 `hr_zone` = **`None`**、`intensity_text` 含「1RM」。

⚠️ **期望值自己算、不要照抄这张表**（硬规矩 #44）。这张表是给实现者**对拍**用的：算出来不一样，先怀疑自己、再怀疑表，**两边都要写进报告**。

**三档系数（spec 最欠定的一步，口径自己定 + 登记 spec §14 #32）：**
- `endurance_score` = `vital_capacity` 与 `distance_run` 两项国标得分的**算术均值**（`float`，因为 `ITEM_BUCKET` 把这两项归 endurance 桶）。两项里只有一项有值时**取那一项、不取半值**；两项都无值时为 `None`。
- 档位：**`< 60` → `0.8`、`[60, 80)` → `1.0`、`>= 80` → `1.2`**（**半开、无缝无叠**——Ruling 9 更正原文的「`60–79`」：`endurance_score` 是两项得分的 float 均值，`79.5` 会落在 `(79, 80)` 的缝里，而 500 人里可能只有个位数、分布断言完全测不出来）。
- 性别修正：男 `1.0` / 女 `0.9`。**最终系数 = 档位系数 × 性别系数**，四舍五入到 2 位。
- `endurance_score is None`（两项都缺测）→ 用 `1.0`，并把 `volume_factor_band` 置 **`"unknown"`**（**P5-A7：不另加第 13 个键**——信息已在 band 里，而「12 个键」是离线复算的契约，多一个键就废了）。
- ⚠️ 这套阈值**指导文件没给**。必须在 spec §14 补一项（#32，归 Task 9），并在 `assembler.py` 的 docstring 里明写「本表是工程约定，不是运动生理学结论，须由体育专家确认」。

**⚠️⚠️ Ruling 133 —— 本 Task 的头号约束**（Task 3 实现者发现、控制者独立实算坐实）：18 套模板的 **130 个 block 里有 82 个是 `intensity: {type: none}`**；按层统计 `intensity.type` 是 **绿 `{none}` / 黄 `{none}` / 红 `{hrmax_pct, none, onerm_pct}`**。spec §7.2 `:487` **只给了红层的强度数值**（60–70% HRmax、70% 1RM），黄层绿层只有动作名。推论：

- **「模板没给强度」是常态、不是例外。** `intensity_text` 必须有一档**显式**渲染它（决定：`"模板未指定强度（spec §7.2 只给了红层数值，见 spec §14）"`），**不得**回落到 `hrmax_pct` 的默认值、**不得**留空字符串。
- 这 82 个 block 的 `hr_zone` 一律 `None`。
- **必须有一条测试直接吃真仓 YAML**（不是手工构造的 `Template`）：加载一个黄层模板 + 一个绿层模板，`assemble` 成功、所有 block 的 `hr_zone is None`、所有 `intensity_text` 非空。**这条测试是「简化版装配器真能跑通 18 套模板」的唯一守卫。**
- 只有红层的 `hrmax_pct` block 会走心率换算路径 → **心率相关的测试必须用红层模板或手工构造的 `hrmax_pct` block**。用黄层写会全绿、但什么也没测（假绿）。

**Step 1: 写失败测试（`intensity` + `assembler`）**

- [ ] `intensity`（约 8 条）：Tanaka 字面值（`hrmax(20) == 194.0`、`hrmax(18) == 195.4`、`hrmax(25) == 190.5`——**期望值自己算，不要照抄派单**，硬规矩 #44）/ `age <= 0` 与 `age >= 100` 拒绝且消息含年龄 / `measured` 优先 / `measured` 越界拒绝 / `hr_zone` 保守取整（**字面写死**，并构造一个能暴露取整方向的例子）/ `hr_zone` 非法百分比拒绝（`low > high`、`low < 0`、`high > 100`）/ `age_from` 周岁（生日当天与生日前一天各一条）。

- [ ] `assembler`（约 13 条，**每个分支至少一条，不做穷举矩阵**）：
  - `test_hrmax_uses_tanaka_when_no_measured_value` / `test_hrmax_prefers_the_measured_value`
  - `test_hrmax_inconsistent_age_is_rejected`（第 1 步的一致性闸门）
  - `test_hr_zone_only_for_hrmax_pct_blocks`（`onerm_pct` 的 block `hr_zone is None` 且 `intensity_text` 含「1RM」）
  - `test_intensity_none_blocks_get_an_explicit_text_and_no_hr_zone`（**Ruling 133 那条吃真仓 YAML 的测试**）
  - `test_volume_factor_three_bands` —— 三档各一条 + **一组**边界（`59.9/60.0` 或 `79.9/80.0`，字面写死系数）
  - `test_volume_factor_falls_back_when_endurance_score_missing`
  - `test_four_week_progression_applies_week_deltas_in_order`（第 4 周的量必须**小于**第 1 周，`week_deltas` 末项 0.85）
  - `test_every_block_carries_a_video_url_from_the_exercise_library`
  - `test_unknown_exercise_ref_is_rejected_at_assembly_time`
  - `test_week_deltas_length_mismatch_is_rejected_not_silently_truncated`
  - `test_assembly_snapshot_is_reproducible`（第 6 步）
  - `test_assembly_snapshot_keys_are_exactly_the_pinned_set`（键集字面写死——**多一个键或少一个键都要红**，这列是离线复算的契约）
  - `test_volume_base_uses_the_right_formula_per_structure_shape`（**P5-A1**：时长类与次数类各一条，用上面那张算例表的字面值）
  - `test_rest_min_is_not_counted_as_volume`（**P5-A1**：把 `rest_min` 从 2 改成 20，`weekly_volume` 必须**不变**）
  - `test_unknown_structure_shape_is_rejected_not_zeroed`（**P5-A1**：喂一个 `{"foo": 1}` 的 structure → `ValueError`）
  - `test_weekly_volume_is_base_times_sessions_per_week`（**P5-A2**：`RED-END-ABN-01` 的 `interval_run` → `48.0`）
  - `test_every_block_appears_in_every_session_of_the_real_templates`（**P5-A2 的守卫**：真仓 18 套，每个 block 的 `sessions_per_week == template.weekly_frequency`）
  - `test_impact_level_comes_from_the_exercise_library_not_the_template`（**P5-A8**：把模板里的 `impact_level` 改成与动作库矛盾的值 → 装配结果**仍取动作库的**）
  - `test_rpe_intensity_renders_text_without_an_hr_zone`（**P5-A5**：手工构造 `Intensity(type="rpe", value=13)`，真仓无此档）

**Step 2: 跑失败 → 实现 → 跑通**

- [ ] 先跑一遍确认新测试全红（且红的原因是「模块不存在 / 断言不符」，不是 import 错误之外的意外）
- [ ] 实现 `intensity.py` 与 `assembler.py`，跑到新测试全绿
- [ ] 全量 `pytest -q` 不退步（基线 **592 passed**，`dfa7580`）

---

### 5.3 `safety.py` —— spec §7.4 的三触发

**Consumes:** 5.2 的 `TrainingPackage` / `AssembledBlock`、Task 2 的 `EquivalenceTable` / `ImpactLevel`

**Produces:**
- `SafetyInput`（frozen）：`bmi: float | None` / `muscle_mass_kg: float | None` / `muscle_p10: float | None` / `body_fat_abnormal: bool`
- `Substitution`（frozen）：`week` / `day` / `original_ref` / `substitute_ref` / `trigger: str` / `equivalence_version: str`
- `SafetyOutcome`（frozen）：`package: TrainingPackage` / `substitutions: tuple[Substitution, ...]` / `needs_review: bool` / `warnings: tuple[str, ...]`
- `apply_safety(pkg: TrainingPackage, inp: SafetyInput, eq: EquivalenceTable) -> SafetyOutcome`

| 触发 | 条件 | 动作 |
|---|---|---|
| BMI > 30 | `inp.bmi is not None and inp.bmi > 30` | ① 跑量乘 `volume_reduction["bmi_over_30"]`；② 所有 `impact_level == HIGH` 的动作 → 查 `exercise_equivalence.yaml` 换低冲击等价动作 |
| 肌肉量 < 同龄同性别 **P10** | `muscle_mass_kg is not None and muscle_p10 is not None and muscle_mass_kg < muscle_p10` | 同上（系数用 `volume_reduction["muscle_low_p10"]`），**并追加 `when == "muscle_low"` 的 addon**（**P5-A3 更正**：这就是 spec §7.4「并提高抗阻模块比重」的落地方式） |
| 体脂率异常 | `body_fat_abnormal` | 追加**模板自己的** `when == "body_fat_over"` 的 addon（能量消耗模块） |

**⚠️ P5-A9 的触发词表映射（两套不同名的词表，必须显式对上）**

实测：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`，也是 YAML 里 `addons.when` 的取值域）、`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。**两套名字完全不同**，而 `SafetyInput` 给的是第三套（`bmi` / `muscle_mass_kg` / `muscle_p10` / `body_fat_abnormal`）。`safety.py` 里字面写死这张映射：

```python
# 键 = 本模块的触发名，值 = (volume_reduction 的键 or None, addons.when 的键 or None)
_TRIGGER_MAP = {
    "bmi_over_30":       ("bmi_over_30",    None),          # 实测模板里没有 when: bmi_over_30 的 addon
    "muscle_low_p10":    ("muscle_low_p10", "muscle_low"),
    "body_fat_abnormal": (None,              "body_fat_over"),  # 体脂异常不下调跑量，只追加模块
}
```

配**两条漂移测试**，各自字面钉住上游词表（防上游改名后本映射静默失配）：
`assert ADDON_TRIGGERS == frozenset({"body_fat_over", "muscle_low"})`、`assert EQUIVALENCE_TRIGGERS == frozenset({"bmi_over_30", "muscle_low_p10"})`。
词表的所有者仍是 `templates.py` / `exercises.py`，**`safety.py` 只消费、不定义**（Global Constraint #3）。

**决定（安全关键，一条不许砍）：**
- **比较符一律严格 `<` / `>`**，与 Plan 01 的 P25（spec §14 #21）和体脂率阈值（`BODY_FAT_LIMIT`，住在 `app/domain/derive.py`，**按可 grep 的原文找、不要按裸行号找**；P5-A10 实测它是**一行 dict 定义**`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}` + 一处消费，原文写的「`:68-69` 明写严格大于」**行号口径错、引文控制者未核**，由实现者复核后写明）**同口径**。每条都要有**恰在边界上**的测试（`bmi == 30.0` 不触发、`muscle_mass == muscle_p10` 不触发）。
- **`bmi is None` / `muscle_mass_kg is None` / `muscle_p10 is None` 都不触发**，且在 `assembly_snapshot` 里留痕。
  **⚠️ P5-A7：`apply_safety` 追加的键字面固定为至多 3 个**——`safety_triggers`（命中的触发名列表）、`safety_skipped`（因输入缺失而跳过的项，如 `["bmi_missing"]`）、`safety_volume_factor`（跑量下调的乘积，未命中则 `1.0`）。**`assemble` 那 12 个键一个都不许改**；这 3 个是安全层的显式追加，配一条 `test_safety_appends_at_most_three_snapshot_keys`（字面写死这 3 个名字）。**这是 Plan 01 Ruling 134 的同一条纪律**：「没测」不得被讲成「测了且没问题」——安全规则静默跳过比不跳过危险。
- **「跑量按映射表下调」的口径 spec 没给**：系数来自 Task 2 已落地的 `exercise_equivalence.yaml` 顶层 `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}`，`apply_safety` 把命中触发的系数**乘到每个 block 的 `weekly_volume` 上**（两个触发都命中则相乘；**⚠️ P5-A6 实测 `0.8 * 0.9 == 0.7200000000000001`，不是 `0.72`** → 乘积用 `pytest.approx`，而 `weekly_volume` 一律 **`round(x, 1)`** 后再落进 dataclass，这样它的字面值才是稳定的）。⚠️ **这两个系数指导文件没给**，已登记 spec §14 **#28**（Task 2 落地时按 P2-A3「值在哪一刻被写死就在哪一刻登记」原则追加）。`safety.py` 的 docstring 里明写「工程约定，须专家确认」。
- **「提高抗阻模块比重」的口径 —— ⚠️ P5-A3 更正原决定**：原文判成「无法自动化、只加 warning、置 `needs_review`」，**这是错的**：实测 18 套模板里有 **12 个 `when: muscle_low` / `module: resistance_priority` 的 addon**（红层 6 + 黄层 6，绿层 6 套全是 `addons: []`），按原决定它们**永远不会被消费**，是模板里的死数据。**更正：肌肉量 < P10 触发时追加 `when == "muscle_low"` 的 addon**——追加一个 `resistance_priority` 模块**不重排任何既有结构**，因此它既落地了 spec §7.4 的「提高抗阻模块比重」，又没有越过「后置处理」的语义边界。
  - `warnings` 的文本随之改成：`"muscle_low_p10: 已追加 resistance_priority 模块；如需进一步调整抗阻比重，请用教师覆盖（OverrideKind.VOLUME_SCALE / SUBSTITUTE_EXERCISE）"`。
  - **`needs_review` 不再由这一条单独置位**——只在「找不到等价动作」时置位（Review Focus 第 5 条）。理由：既然已经自动追加了模块，就不存在「宁可不自动」的问题了。
  - ⚠️ 这一处置仍**须登记 §14**：Task 9 Step 2 复核 #28 的正文是否已覆盖它，没覆盖就追加为 **#35**。
- **找不到等价动作 → 不静默跳过**（Review Focus 第 5 条，spec §7.4 末段原文）：`needs_review = True`，`warnings` 里写明「哪个动作、哪个触发、映射表版本」，**该 block 原样保留**（不删除、不替换）。**「原样保留」是决定**：删掉动作会让训练量静默缩水，而保留 + `needs_review` 让教师看见。
- **`apply_safety` 是纯函数**：不改传入的 `TrainingPackage`（frozen dataclass，用 `dataclasses.replace` 产出新的）。加一条测试证明入参未被修改。
- **优先级高于模板定义**（spec §7.4 原文）：加一条测试——模板里写 `impact_level: high` 的动作，在 BMI > 30 时**必须**被换掉，即使模板「明确要」它。
- ⚠️ **已知不对称（Task 3 记录，本 Task 不修，只在报告里复述）**：`hiit`（`impact_level: high`、等价表里**有**映射）与 `energy_expenditure_plus_5min_hiit`（`medium`、**无**映射）→ BMI>30 的黄层学生会「主项被换掉、追加模块原样保留」。这是**数据面的事实**，不是代码缺陷。
- ⚠️ **绿层 `addons: []` 与 spec §7.4 `:510` 的冲突**（Task 3 已登记；**P5-A3 实测坐实：绿层 6 套全部 `addons: []`**）：体脂异常或肌肉量偏低但模板无对应 addon 时，`apply_safety` **不凭空造模块**，只留一条 warning。

**⚠️ P5-A3 的追加口径（addon 怎么变成 `AssembledBlock`，spec 完全没给，登记 §14 新 #35）**

`Addon` 实测只有两个字段：`when: str` / `module: str`（`module` 是动作库里的 ref，**Task 3 的加载器已校验过它存在**，故这里**不重复校验**——单一所有者）。**没有 `structure`、没有 `intensity`、没有 `day`。** 定口径：

| `AssembledBlock` 字段 | 追加的 addon block 取值 | 理由 |
|---|---|---|
| `exercise_ref` | `addon.module` | — |
| `exercise_name` / `video_url` / `impact_level` | 从 `exercises[addon.module]` 取 | 与主项同一来源（P5-A8） |
| `intensity_text` | `"附加模块（模板未指定强度，见 spec §14）"` | 与 Ruling 133 那一档同一措辞口径 |
| `hr_zone` | `None` | 非心率类 |
| `structure` | `{}` | 模板没给 |
| **`weekly_volume`** | **`0.0`** | **见下** |
| **`volume_unit`** | **`"unspecified"`** | **见下** |
| `sessions_per_week` | `template.weekly_frequency` | 附加模块每天都做 |

**`weekly_volume = 0.0` 是决定，不是偷懒。** 备选方案都被否掉了：
- ❌ **按 ref 名字硬编码规则**（`energy_expenditure_plus_10pct` → 周时长总量的 10%、`…_plus_5min_hiit` → `5.0 × sessions_per_week`）：这要给 3 个 module 各写一条硬编码，**专家加第 4 个 module 就静默失效**，而且把量化规则写进代码等于从 `exercises.yaml` 手里抢走所有者（Global Constraint #3）。
- ❌ **取同 session 内既有 block 的均值**：单位可能不同（时长类 vs 次数类），跨单位平均是无意义的数；且「均值」会让附加模块的量随主项漂移，教师无法预期。
- ✅ **置 `0.0` + `volume_unit = "unspecified"` + 一条 warning**：**spec 没给附加模块的量，编造一个数就是把「不知道」讲成「知道」**——这与 Plan 01 Ruling 134、以及本节已有的「没测不得讲成测了没问题」是**同一条纪律**。
  - `0.0` 对下游**零副作用**：`0.0 × 0.8 = 0.0`（减量乘法）、Task 8 的 `WeeklySheet` 缩放同理。
  - 教师可以用 `OverrideKind.VOLUME_SCALE` 给它一个量 → **这恰好是 spec §7.5 末段「教师在哪些环节最不信任算法」的一个真实数据点**。
  - warning 文本：`"addon <module> 的训练量未指定（weekly_volume = 0.0），需教师用 VOLUME_SCALE 覆盖"`。
  - **`volume_unit` 的第三档 `"unspecified"` 就是为它加的**（P5-A1 的值域已含）。

**追加到哪个 session？** 决定：**追加到每一个 session 的 `blocks` 末尾**（因为 `sessions_per_week = weekly_frequency`）。追加**不改变既有 block 的顺序**（`day` / `focus` / 主项次序全部原样），故 `test_apply_safety_does_not_mutate_its_input` 与 Task 8 的读模型都不受影响。


**Step 3a: 写失败测试（`safety`，约 12 条）→ 实现 → 跑通**

- [ ] 三个触发 × {命中, 不命中, 恰在边界, 输入缺失} = 12 条起步，另加：
  - `test_missing_equivalent_sets_needs_review_and_keeps_the_block`（Review Focus 第 5 条）
  - `test_substitution_records_carry_the_equivalence_version`（spec §7.4 明写要记「映射表版本号」）
  - `test_safety_overrides_the_template`（优先级）
  - `test_apply_safety_does_not_mutate_its_input`
  - `test_body_fat_abnormal_appends_the_template_addon`（addon 来自**模板**，不是硬编码——`addons: []` 的绿层模板在体脂异常时**不应**凭空多出一个模块）
  - `test_muscle_low_p10_appends_the_resistance_priority_addon`（**P5-A3**：红层或黄层模板 + 肌肉量 < P10 → 每个 session 的 blocks 末尾多一个 `resistance_priority`，且**既有 block 的顺序与值全部不变**）
  - `test_appended_addon_has_zero_volume_and_unspecified_unit`（**P5-A3**：`weekly_volume == 0.0`、`volume_unit == "unspecified"`、有一条 warning 点名该 module）
  - `test_muscle_trigger_alone_does_not_set_needs_review`（**P5-A3**：只有「找不到等价动作」才置位）
  - `test_trigger_word_lists_have_not_drifted`（**P5-A9**：两条字面断言钉住 `ADDON_TRIGGERS` 与 `EQUIVALENCE_TRIGGERS`）
  - `test_bmi_over_30_appends_no_addon`（**P5-A9**：实测模板里没有 `when: bmi_over_30` 的 addon，映射表那一格是 `None`）
  - `test_safety_appends_at_most_three_snapshot_keys`（**P5-A7**）
  - `test_both_triggers_multiply_the_volume_reduction`（**P5-A6**：断言系数用 `pytest.approx(0.72)`，断言某个 block 的 `weekly_volume` 用 `round` 后的**字面值**——**不要写 `== 0.72`**，实测它是 `0.7200000000000001`）

---

### 5.4 `override.py` —— spec §7.5 的五种教师覆盖

**Produces:**
- `OverrideKind(str, Enum)`：`WEEKLY_FREQUENCY` / `SUBSTITUTE_EXERCISE` / `INTENSITY_STEP` / `VOLUME_SCALE` / `PAUSE`（spec §7.5 的五种：周训练天数、替换单个动作、调整强度档位、整体降量/加量、暂停处方）
- `OverrideRecord`（frozen）：`kind` / `target: str | None`（周次或 `exercise_ref`）/ `old_value: str` / `new_value: str` / `reason: str` / `teacher_staff_no: str` / `applied_at: dt.datetime`
- `apply_overrides(pkg: TrainingPackage, records: Sequence[OverrideRecord]) -> TrainingPackage`
- `summarize_overrides(records) -> dict[str, int]`（按 `kind` 计数，供 spec §7.5 末段「学期末回答教师在哪些环节最不信任算法」）

**决定：**
- **覆盖不修改模板**（spec §7.5 原文）：`apply_overrides` 只作用于 `TrainingPackage`，且是纯函数。加一条测试证明模板对象未被修改。
- **下次自动生成回到算法基线、不继承覆盖**（spec §7.5 原文）：这不是 `override.py` 的职责，而是 **Task 6** 的触发逻辑——生成时**不读**上一张处方的 override 记录。集成测试放 Task 6 的 Step 6。
- **`applied_at` 由调用方注入**（domain 不碰时钟）。
- **`PAUSE` 的语义**：**原样保留 `weeks`、把 5.2 已定义的 `paused` 置 `True`**——因为「暂停」是可撤销的，删掉 `weeks` 就不可逆了。
- **`reason` 不得为空**：`OverrideRecord.__post_init__` 校验 `reason.strip()` 非空。理由：spec §7.5 末段说这些记录是研究数据（「教师在哪些环节最不信任算法」），一条没有理由的覆盖对研究毫无价值。**这与 Plan 01 给 `WeaknessResult` 加 `count == len(items)` 不变量是同一个手法。**
- **`old_value` / `new_value` 是 `str`**（不是各自类型的联合）：它们要落进 `prescription.teacher_overrides` 这个 JSON 列，异构类型会让 JSON 结构不稳定。**用 `str` 并在 docstring 里写明每种 `kind` 的取值约定**（如 `VOLUME_SCALE` 是 `"0.8"`、`SUBSTITUTE_EXERCISE` 是动作 ref）。
- **多条覆盖同一目标 → 由列表顺序决定，后者胜**（不用 `applied_at`：同一秒批量操作时它相等，而调用方持有真实顺序）。加一条测试钉住这个决定。

**Step 3b: 写失败测试（`override`，约 8 条）→ 实现 → 跑通**

- [ ] 五种 `kind` 各一条（命中即可，**不做穷举边界**），另加：`test_override_does_not_mutate_the_template` / `test_override_records_are_applied_in_order` / `test_empty_reason_is_rejected` / `test_pause_keeps_the_weeks_and_sets_the_flag` / `test_summarize_overrides_counts_by_kind`（期望 dict 字面写死）/ `test_substitute_exercise_rejects_an_unknown_ref`

---

### 5.5 收尾

**Step 4: 变异验收（只做安全关键的 4 条）**

- [ ] ① `bmi > 30` → `>= 30` → 边界测试红；② 删掉「找不到等价动作 → `needs_review`」→ Review Focus 第 5 条的测试红；③ 删掉 `age <= 0` 的守卫 → 拒绝测试红；④ 把 `hr_zone` 的取整方向反过来 → 保守取整测试红。
- [ ] **每条变异按硬规矩 #65 写明「哪个断言分支开火」，并按 M0/M1 双对照取证**（M0：不变异时全绿；M1：语义等价改写后仍全绿——证明尺子不恒红）。变异后**三重还原**（还原代码、重跑、确认 sha256 与变异前一致）。

**Step 5: 公开面 + 全量 + 覆盖率 + Commit**

- [ ] `__init__.py` 重导出四个模块的公开名；`_PRESCRIPTION_PUBLIC_BASELINE` 从 24 个 `(名字, 所有者模块)` 二元组扩到新值（**新值自己数并字面写死**，同时改同文件里那句 `assert len(...) == 24`）。
- [ ] `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → **Miss 0 / BrPart 0 / 100%**（简化版**不豁免这一条**，spec §12 是硬要求）。
- [ ] **P5-A12：吃真仓 YAML 的测试用 `exercises()` / `templates()` / `equivalence()` 三个进程内单例**，**不用 `load_exercises` / `load_templates` / `load_equivalence`**（后者每次重解析 18 份 YAML，还各跑一遍 `yaml.compose` 建行号索引）。⚠️ 单例是**进程内共享**的，测试里**不得改写**它（顶层是 `MappingProxyType`、`Block.structure` 是只读视图，但「改不动」不等于「不该试」）。
- [ ] `tests/architecture` 两份守卫全绿。⚠️ 新增 4 个 domain 模块会让扫描面从 **28** 涨到 **32**（pipeline 7 + db 11 + domain 14）；**涨了要在报告里说明**，别让人以为是守卫失效。
- [ ] 全量 `pytest -q` 的 passed 数**自己数**（基线 592，硬规矩 #44：期望值不得照抄派单）。
- [ ] Commit（信息用 python 写 UTF-8 临时文件 + `git commit -F`）。

---
