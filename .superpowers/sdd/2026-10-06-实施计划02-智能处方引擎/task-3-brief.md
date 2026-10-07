# Task 3 简报 — 18 套模板 YAML + `prescription_template` 表 + 加载器

> 抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit `71538c4`（控制者用 python 从**已提交**状态抽，抽前验过工作树干净、blob 与工作树内容一致 —— 硬规矩 #48）。
> 内容 = 计划头部（**Global Constraints 10 条** / **Review Focus 5 条** / **File Structure**） + **Task 3 全节**。
> ⚠️ Task 3 全节里的 `P3-A1 … P3-D4` 标记是**控制者预检的更正与裁定**，完整依据在账本 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的 `### Task 3: 18 套模板 — 预检扫描（Pre-flight，控制者亲跑）` 一节。**以更正后的正文为准**；正文里凡写「原文……」的都是已被作废的旧说法。
> ⚠️ 本简报有 **2 处 Critical**：**P3-A1**（不许新建 `app/seed/prescription.py`、不许改 `seed_database`，改用 `refdata_prescription.sync_templates(session)`）与 **P3-D2**（**必须改 `.gitattributes`**，加 `backend/data/**/*.yaml text eol=lf`——现有规则不覆盖子目录，`git check-attr` 已亲验）。
> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（约 806 KB）；**#48–#75 在 Plan 02 账本**（上面那个 progress.md，约 265 KB）。**Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用**（已知勘误）。

# 实施计划 02：智能处方引擎

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01 产出的红黄绿分层结果，按「层 × 主导短板 × 体成分」装配成可复现、可审校、可被教师覆盖的 4 周运动处方，并接进每日批处理管道。

**Architecture:** `app/domain/prescription/` 是无 I/O 的纯函数叶子层（匹配、强度换算、装配、安全后置、覆盖、触发判定），模板与动作等价映射是 `backend/data/` 下带版本号的静态 YAML（体育专家可独立审校），`app/pipeline/prescription_stage.py` 负责落库与幂等。处方**不每天重发**——只有 spec §5.2 的五个触发条件之一成立时才生成，而分层重算仍然每天跑。

**Tech Stack:** Python 3.11.1、SQLAlchemy 2.1、SQLite（`PRAGMA foreign_keys=ON`）、PyYAML、pytest + pytest-cov。不引入新依赖。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md` —— 本计划实现 **§4.4（处方数据模型）、§5.2（五个触发条件）、§7.1–7.5（智能处方层全部）、§8.4（骨架 + 周微调两层拆分）、§11.2（B 类算法降级）、§1.3（单人处方 p95 < 3 秒）、§12（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）**。

**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的十条见 Global Constraints。

---

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
2. **同一个学生在同一天被两次触发**（管道重跑、或教师手动请求与自动触发撞上）→ 必须产出一条处方而不是两条，且第二次是幂等的 no-op 或明确的 `replaced`。归属 Task 9。
3. **学生当天没有分层结果**（`valid_count < 4` → `insufficient_data`，Z0 闸门拦下）→ **不得生成处方**，且必须留下可交代的痕迹（不是静默跳过）。Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 9。
4. **年龄缺失或异常**（`Student.birth` 为空、或算出年龄 ≤ 0 / ≥ 100）→ Tanaka 公式会给出荒谬的 HRmax（如 `208 − 0.7×0 = 208`），进而给出危险的目标心率区间。必须响亮拒绝或降级到 `needs_review`，**不得静默装配**。归属 Task 5。
5. **安全规则命中但 `exercise_equivalence.yaml` 里找不到等价动作**（spec §7.4 明写「不静默跳过」）→ 处方状态置 `needs_review`、写 `warning` 日志、教师端标记「需人工复核」。这是 spec 唯一一处显式要求「宁可不自动，也不要自动错」的地方，必须有测试钉住**它没有被静默跳过**。归属 Task 7。

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
| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（Tanaka / 220−age 可切换） |
| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配 |
| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换 |
| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加 |
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

## Task 3: 18 套模板 YAML + `prescription_template` 表 + 加载器

**Files:**
- Create: `backend/data/prescription/*.yaml`（18 个）
- Modify: `backend/app/refdata_prescription.py`（加模板加载部分 + **`sync_templates(session)`**，见 P3-A1）、`backend/app/db/models/prescription.py`（加 `PrescriptionTemplate`）、`backend/app/domain/prescription/templates.py`、`backend/app/domain/prescription/__init__.py`（公开面）、`backend/tests/domain/test_prescription_templates.py`（**⚠️ P3-A2：这个文件已经存在**，Task 2 建的，11 248 B / 153 行 / 4 条测试，故是 **Modify 不是 Create**）、`backend/tests/test_refdata_prescription.py`、`backend/tests/db/test_models.py`、`backend/tests/seed/test_generate.py`
- ⛔ **不要新建 `backend/app/seed/prescription.py`、不要改 `seed_database`（P3-A1，Critical）**。原文的 Create 清单里有它，而它与 **Global Constraint #10（`app/seed/` 自 Plan 01 结案后重新冻结）** 直接冲突，并会撞 `tests/seed/test_generate.py:491` 的 `test_seed_database_writes_only_organisation_tables_and_is_idempotent`（`:519` 的 `assert count == 0, f"{table} 不该由 seed_database 写入"`）与 `app/seed/generate.py:10` 的 docstring「**只**写组织结构五张表」。**这正是 Task 2 预检 P2-A1 已经裁过一次的同一个缺陷，控制者当时只改了 Task 2 的 Step 5、没有把裁定传导到 Task 3**（账本 Ruling 128 / 控制者错误 #124）。**裁定：照 Task 2 的先例，灌数据函数放 `app/refdata_prescription.py`，命名 `sync_templates(session) -> int`**（幂等 upsert、返回行数），与 `sync_exercises` 并列。理由同 P2-A1：`prescription_template` 是**参考数据**（体育专家维护的知识资产的投影），不是 `app/seed/` 造的仿真人口数据。
- Modify: `backend/app/domain/prescription/templates.py`（**Modify 不是 Create** —— Task 2 已建它并放了 `ImpactLevel`，见 Task 2 的 P2-B1 裁定；本 Task 往里加 `Template` / `Session` / `Block` / `Intensity` / `Addon` / `WeaknessBucket` / `BodyCompState` / `ReviewStatus`）、`backend/tests/db/test_models.py`（表数 15 → 16，⚠️ `== 15` 同样有 **3 处** + 函数名 `test_all_fifteen_tables_created` 要跟着改，见 Task 2 的 P2-A6）、`backend/tests/seed/test_generate.py`（`REFERENCE_TABLES` 加 `prescription_template`，见 Task 2 的 P2-A1。⚠️ **P3-A6：`:496` 的 `REFERENCE_TABLES = ("exercise",)` 被 `:542` 的 `assert REFERENCE_TABLES == ("exercise",)` 字面钉住**，改一处必须改两处；而 `:527-538` 那道「三分区恰好穷尽 `Base.metadata`」的守卫会自动要求新表被认领）
- ⛔ **必须改 `.gitattributes`（P3-D2，Critical；原文说「不需要改」是假的）**

  原文写「同 P2-A7：`backend/data/*.yaml text eol=lf` 已经覆盖 `backend/data/prescription/*.yaml`，本 Task 只需确认」。**控制者亲跑 `git check-attr` 推翻它**：

  ```
  $ git check-attr text eol -- backend/data/exercises.yaml
  backend/data/exercises.yaml: text: set
  backend/data/exercises.yaml: eol: lf
  $ git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml
  backend/data/prescription/RED-END-ABN-01.yaml: text: unspecified
  backend/data/prescription/RED-END-ABN-01.yaml: eol: unspecified
  ```

  **gitattributes 的 `*` 不跨 `/`**，所以 `.gitattributes:14` 的 `backend/data/*.yaml` **只匹配 `data/` 根下的 `.yaml`，不匹配 `data/prescription/` 子目录**。

  **后果**：`core.autocrlf=true` 下，那 18 个模板 YAML 检出时会变成 CRLF，而「归一化后 sha256[:16]」的指纹虽然本身不受影响（`test_refdata_prescription.py:83-84` 与 Task 3 要新写的指纹测试都先 `replace(b"\r\n", b"\n")`），**但工作树字节会随平台配置漂移**——**这正是 Plan 01 的国标评分表事故的原型**（硬规矩 #46/#47：21412 字节 LF ↔ 21915 字节 CRLF，`git checkout` 一次就让指纹测试变红）。而且 Task 3 的 YAML 里会有大量中文注释，CRLF/LF 混用还会让「按字节比对」的取证全部失真。

  **裁定**：在 `.gitattributes` 的 `backend/data/*.md` 那一条之后加一行

  ```
  backend/data/**/*.yaml text eol=lf
  ```

  （`**` 跨目录；已有的 `backend/data/*.yaml` 可以留着，两条不冲突，**后写的优先**故 `**` 那条要放在后面）。加完必须亲验：
  `git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml` 要返回 `text: set` / `eol: lf`；18 个文件落地后再跑 `git ls-files --eol -- backend/data/` 确认每一行都是 `i/lf w/lf attr/text eol=lf`。

  ⚠️ **这是本计划里第二次「以为不用改 `.gitattributes`」**（P2-A7 那次是把「已有规则」错列进 Modify，方向相反但同属「没有亲验属性覆盖范围」）。**→ 补进硬规矩 #61 的适用范围：`.gitattributes` / `.gitignore` 这类「规则文件」的覆盖面，必须用 `git check-attr` / `git check-ignore` 对**具体的目标路径**亲验，不能靠读规则文本推断。**

**Interfaces:**
- Consumes: Task 2 的 `load_exercises()`、`ImpactLevel`
- Produces:
  - `app.domain.prescription.templates.Layer(str, Enum)` —— **不要新建**，复用 `app.domain.stratify.Layer`（控制者实跑其成员：`RED="red"` / `YELLOW="yellow"` / `GREEN="green"` / `INSUFFICIENT="insufficient_data"`，与这里写的一致）。⚠️ **P3-D4：从 `app/domain/prescription/templates.py` 引它，绝对导入是 `from app.domain.stratify import Layer`，相对导入是 `from ..stratify import Layer`（`level == 2`）**。两者在守卫下等价，但**选相对导入会让 Task 1 fix round 5 埋的那一格绿档（`("indicators", 2, ("app","domain","prescription"), "X", "GREEN")`）从「前瞻」变成「真仓形状」**（账本 Ruling 104 记的就是「今天还没有任何 level==2 的真仓相对导入」）。**控制者不裁定选哪个**——Task 2 的实现者选了绝对导入，理由是既有 4 个 domain 模块全部用绝对串、而 Ruling 96 的精神是「照抄既有分层」；**本 Task 若沿用绝对导入，请保持一致，不要出现「一半绝对一半相对」**。选了就说明理由。⚠️ 模板维度只有前三个，`insufficient_data` **不是**合法模板层，匹配器必须拒绝它。
  - `WeaknessBucket(str, Enum)`：`ENDURANCE = "endurance"` / `STRENGTH = "strength"` / `SPEED_FLEXIBILITY = "speed_flexibility"`。**取值必须与 `app.domain.indicators.ITEM_BUCKET` 的值逐字相同**，且要有一条漂移测试钉住（`{b.value for b in WeaknessBucket} == set(ITEM_BUCKET.values()) - {None}`）。
  - `BodyCompState(str, Enum)`：`NORMAL = "normal"` / `ABNORMAL = "abnormal"`
  - `ReviewStatus(str, Enum)`：`PENDING = "pending"` / `APPROVED = "approved"`
  - `@dataclass(frozen=True) Template`：`template_id` / `version` / `layer` / `weakness` / `body_comp` / `reachable` / `review_status` / `reviewer` / `reviewed_at` / `microcycle_weeks` / `weekly_frequency` / `sessions: tuple[Session, ...]` / `week_deltas: tuple[float, ...]` / `addons: tuple[Addon, ...]`
  - `@dataclass(frozen=True) Session`：`day: int` / `focus: str` / `blocks: tuple[Block, ...]`
  - `@dataclass(frozen=True) Block`：`exercise_ref` / `impact_level` / `intensity: Intensity` / `structure: dict`
  - `@dataclass(frozen=True) Intensity`：`type: str`（`hrmax_pct` | `onerm_pct` | `rpe` | `none`）/ `low: float | None` / `high: float | None` / `value: float | None`
  - `@dataclass(frozen=True) Addon`：`when: str`（`body_fat_over` | `muscle_low`）/ `module: str`
  - `app.refdata_prescription.load_templates() -> dict[str, Template]`（键是 `template_id`）

**决定（用户已裁定）**：18 套**全部 `review.status: approved`**，`reviewer: "原型自审（占位）"`、`reviewed_at` 用一个固定的 ISO 日期（**不要用 `date.today()`**，那会让 YAML 每次生成都变、指纹测试天天红）。同时在 spec §14 补一项：「18 套模板的审校状态在原型阶段全部标记为 `approved` + 占位审校人，**须由邹红老师实际审校后替换**」。

⚠️ **这一项已经有编号了，不要新造（P3-A3）**：`d40f36c` 重排 §14 之后，Task 12 Step 3 的清单（计划 `:688`）里 **#29 就是「18 套模板的审校状态（占位 approved，须专家实际审校）」**。**裁定：本 Task 直接把 #29 写进 spec §14**（按 P2-A3 立的原则：「值在哪一刻被写死就在哪一刻登记」），**并把 Task 12 Step 3 的清单从 6 项减到 5 项**（`#30` 视频源 / `#32` 个体修正系数 / `#33` 触发 4 口径 / `#34` 同周多调整 / 以及 #31 若本 Task 也一并写了就再减一项）。**总数仍是 `27 + 1(#28, T2) + 2(#29/#31, T3) + 4(T12) = 34`**，与「计划完成后的状态」那段的「27 → 34」一致。**⚠️ 这是 §14 编号第二次差点撞车**（第一次是 Task 2 的 #28，账本 Ruling 92）——所以动 §14 之前必须先读计划 `:688` 的现有分配。

**「拒绝生成」路径怎么测**（这是 **Task 4** 的关键，本 Task 只做前半）：不能靠「所有模板都 approved 所以测不到」。

⚠️ **P3-A8：原文这一段整体是 Task 4 的活，被错放进了 Task 3**——「匹配器」（`match.py`）是 Task 4 才建的（计划 `## Task 4: 模板匹配器（match.py）`），Task 3 没有匹配器可喂。**裁定：拆开。**
- **归 Task 3**：`Template` 是 frozen dataclass、可以直接构造 → **本 Task 要证明「构造一个 `review_status=PENDING` 的 `Template` 是可能的」**（即 dataclass 不在构造期做校验、`pending` 是合法枚举值），这样 Task 4 才有东西可喂。写成一条单元测试即可。
- **归 Task 4**：变异测试（把一套改成 `pending` → 匹配器必须拒绝）与「直接构造 `PENDING` 实例喂给匹配器」的那条单元测试。**已记进 Task 4 的预检清单。**

- [ ] **Step 1: 写失败测试**

`test_prescription_templates.py`：
- `test_exactly_eighteen_templates_cover_the_full_matrix` —— 键集**字面写死** 18 个 `template_id`，并断言 `{(t.layer, t.weakness, t.body_comp) for t in …}` 恰为 3×3×2 的**全笛卡尔积**（18 个，无重复无缺）。
- `test_three_green_abnormal_templates_are_marked_unreachable` —— spec §7.1 明写 `(green, *, abnormal)` 3 套**当前不可达**（§6.2 决策表下绿色层必然 `NOT C`），**保留为预留位、标记 `reachable: false`、不参与匹配**。字面写死这 3 个 id。
- `test_the_other_fifteen_are_reachable`
- `test_weekly_frequency_follows_the_guidance_document` —— spec §7.2:465 的注释「红 4 / 黄 3 / 绿 2（指导文件原文）」。字面写死 `{red: 4, yellow: 3, green: 2}`，逐套核对。
- `test_week_deltas_length_equals_microcycle_weeks` —— spec §7.2:479 的 `[1.00, 1.05, 1.10, 0.85]` 是 4 项、`microcycle_weeks: 4`，**第 4 周减量（超量恢复）**。断言长度相等，且**最后一项 < 1.0**（减量），且前面各项 ≥ 1.0。
- `test_every_exercise_ref_exists_in_the_exercise_library`（Review Focus 第 1 条）
- `test_every_block_impact_level_matches_the_exercise_library` —— 模板里写的 `impact_level` 必须与动作库里那个动作的 `impact_level` 一致。**两个所有者会漂移**，这条测试就是漂移守卫；若你判断应该只保留一个所有者（模板不写、从动作库取），**报为关切并说明**，不要擅自改 spec §7.2 的骨架。
- `test_template_yaml_fingerprints_are_pinned` —— 18 个文件各自的 sha256[:16]，**归一化后哈希**（同 Task 2）。或改为「18 个文件按 id 排序后拼接再哈希」，一个值；**你选一种并说明理由**（逐个钉更精确但改一个模板要改一行测试；拼接钉更省事但报错不指向具体文件）。
- `test_loader_rejects_a_broken_template` —— 参数化 6 种坏形状：缺 `template_id`、`week_deltas` 长度与 `microcycle_weeks` 不符、`exercise_ref` 不存在、`layer` 是 `insufficient_data`、`weekly_frequency` 与层不符、`review.status` 是第三种值。**每种都必须在加载时响亮失败并指出文件名**（不是 `KeyError`）。

- [ ] **Step 2–5: 跑失败 → 写 18 套 YAML → 跑通**

**⚠️ spec 空洞（本 Task 最大的不确定性，必读）**：spec §7.2:487 只给出了**两个桶**的层级参数：

> 红层每周 4 天、**耐力短板** 60–70% HRmax 间歇跑、**力量短板** 70% 1RM 复合循环、体脂超标追加 10% 能量消耗模块；黄层每周 3 天、**耐力短板**持续跑+台阶训练、**力量短板**自重+弹力带抗阻、体脂偏高附加 5min HIIT；绿层每周 2 天、兴趣球类/定向越野/功能性训练 + 可选挑战任务。

**`speed_flexibility`（速度柔韧）桶在指导文件的转述里没有任何参数**，而它占 3 层 × 1 桶 × 2 体成分 = **6 套模板**。绿层的 3 套可以用「兴趣球类/定向越野/功能性训练」覆盖（spec 没按桶区分绿层），但**红层与黄层的 speed_flexibility 各 2 套（共 4 套）没有源值**。

处置：
1. **不要编造运动生理学参数**。红/黄层的 speed_flexibility 模板用**该层已给出的强度区间**（红 60–70% HRmax、黄层按耐力那套的量）配**速度柔韧类的动作**（50 米跑冲刺间歇、动态拉伸、折返跑、坐位体前屈专项），并在每个 YAML 里加一行注释：`# ⚠️ 强度参数借用同层的耐力短板配置：指导文件未给出速度柔韧桶的层级参数（spec §7.2:487 的空洞），见 spec §14 第 N 项`。
2. **给 spec §14 补一项**：「红/黄层 × speed_flexibility × 体成分 共 4 套模板的强度与结构参数，指导文件未给出，本设计借用同层耐力短板的配置 + 速度柔韧类动作。**须由体育专家给出该桶的实际参数**」。
3. **给 spec §7.2 加勘误**，指明这个空洞（照 Plan 01 的勘误格式：原文 + 更正 + 理由 + Ruling/§14 编号）。⚠️ **P3-A9：这一项与 Task 12 Step 3 的「spec 勘误」重叠**（计划 `:682`）。**裁定：归本 Task**——因为写这 4 套模板的人正是撞见这个空洞的人，隔 9 个 Task 再回来补勘误只会让 YAML 注释里的「见 spec §14 第 N 项」长期指向一个不存在的条目。**Task 12 Step 3 的清单相应减一项。**

 addons（spec §7.2:480-484）：`body_fat_over → energy_expenditure_plus_10pct`（红层 +10% 能量消耗）、`muscle_low → resistance_priority`。黄层是「体脂偏高附加 5min HIIT」→ `energy_expenditure_plus_5min_hiit`。

⚠️ **这个 ref 今天不在动作库里（P3-A4）**：控制者实跑 `exercises.yaml` 的 23 个键，有 `hiit`、有 `energy_expenditure_plus_10pct`、**没有 `energy_expenditure_plus_5min_hiit`**。**裁定：本 Task 往 `exercises.yaml` 追加它**（计划 `:183` 明确授权 Task 3 追加 ref：「若 T3 需要一个 T2 没建的 ref，T3 可以往 `exercises.yaml` 追加（同时更新 T2 的指纹常量），并在报告里列出追加了哪些、为什么」）。理由：与 `energy_expenditure_plus_10pct` 同构（都是「体成分异常时追加的能量消耗模块」，不是主项动作），**不要复用 `hiit`**——`hiit` 是一个有自己 `impact_level` 的主项动作，把「附加 5min HIIT」与「HIIT 主项」混成一个 ref 会让 Task 7 的安全后置无法区分二者。**连带（Task 2 实现者已写下的「Task 3 追加 ref 的 5 项连带清单」，见 `task-2-report.md`）**：追加后必须同步 `test_refdata_prescription.py:69` 的 `EXERCISES_FINGERPRINT`（当前值 `63033BBD7F68CC1F`，归一化 sha256[:16]、大写），并保持该文件 **CRLF = 0**。**绿层的 addon 指导文件没提** → 绿层模板 `addons: []`，并在 YAML 注释里写明「指导文件未给绿层附加模块」。

**每套模板的 `sessions` 天数 = `weekly_frequency`**（红 4 / 黄 3 / 绿 2），`day` 从 1 递增。每个 `session` 至少 1 个 `block`，红/黄层建议 2 个（主项 + 辅项），绿层 1–2 个。

⚠️⚠️ **本 Task 会撞红四处「字面钉死」的基线断言，原文一个字都没提（P3-A6，控制者实跑定位）**：
1. `tests/test_refdata_prescription.py:858` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**7 个名字**）+ `:917` 的 `assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 7` —— 往 `prescription/__init__.py` 的 `__all__` 加 `Template` 一类名字，这两处都会红。
2. `tests/test_refdata_prescription.py:951-952` 有**两条负向断言**：`assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE + ["Template"]` 与 `!= _PRESCRIPTION_PUBLIC_BASELINE[:-1]`。**第一条字面点到了 `"Template"`** —— 它是 Task 2 fr2 为了证明「基线不是当前值减一」而写的反面对照。本 Task 真的加了 `Template` 之后，**这条断言的用意要重新想**（它想挡的是「把基线写成当前 `__all__` 再去掉一个」，而不是「永远不许有 `Template`」）。**改法由你定，但要在报告里说明你的理由。**
3. `tests/domain/test_prescription_templates.py:152` 的 `assert templates.__all__ == ["ImpactLevel"]` —— 往 `templates.py` 加 8 个 dataclass 并同步它的 `__all__`，这条会红。⚠️ 同文件 `:149` 已经写了警告：「Task 3 往 `templates.py` 加模板 dataclass 时，**两份 `__all__` 要一起改**」。
4. `tests/seed/test_generate.py:542` 的 `assert REFERENCE_TABLES == ("exercise",)`。

**四处都是硬规矩 #35 的正确产物（字面写死、不从被测对象反推），所以它们红是「基线该更新了」而不是「守卫太紧」。但更新时必须保持「字面写死」这个性质**——尤其 `_PRESCRIPTION_PUBLIC_BASELINE`：更新后的新基线仍然必须是**字面清单**，不能改成 `list(prescription_pkg.__all__)`（那就两侧同源了）。
**另**：`test_templates_module_still_reexports_impact_level`（Task 2 fr2 加的）是 `templates.py` 那 2 条语句进 domain 覆盖率的**唯一途径**（账本 Ruling 103 / 硬规矩 #67：删掉它 → `Miss 2`、覆盖率跌破 100%、而 `pytest` 退出码仍是 0）。**本 Task 往 `templates.py` 加了 8 个 dataclass 之后，那个「唯一途径」的脆弱性会自然消失**（新 dataclass 会被别的测试导入），**但那条守卫不许删**——它守的是 re-export 本身。

- [ ] **Step 6: `prescription_template` 表 + seed + 全量测试**

ORM 按 spec §4.4：`id` / `layer`（`String(8)` + CHECK ∈ `{red,yellow,green}`，**不含 `insufficient_data`**）

⚠️ **P3-A10：`reachable` 不在 spec §4.4 `:238` 的字段清单里**（原文只有「id、层、主导短板、体成分（共 18 行）、YAML 路径、版本、`review.status` ∈ {`pending`, `approved`}、审校人、审校时间」）。它的依据是 **spec §7.1 `:447`**：「生成器对这 3 套标记 `reachable: false`，不参与匹配」。**故这是一列超出 §4.4 的增补，要在 §7.2 勘误（P3-A9 那一条）里一并交代**，不要让它看起来像是 §4.4 的原文。/ `weakness`（`String(20)` + CHECK ∈ 三桶，`speed_flexibility` 是 17 字符）/ `body_comp`（`String(8)` + CHECK ∈ `{normal,abnormal}`）/ `template_ref`（`String(32)`，指向 YAML 的 `template_id`，unique）/ `version`（`String(8)`）/ `review_status`（`String(8)` + CHECK ∈ `{pending,approved}`）/ `reviewer`（`String(64)`，nullable）/ `reviewed_at`（`Date`，nullable）/ `reachable`（`Boolean`）。

⚠️ 上面给的宽度是控制者按词表算的，**你自己复核一遍**（硬规矩 #44：派单里的数字默认不可信）。控制者实算：`layer` 最长 `yellow` = 6 ≤ 8 ✓、`weakness` 最长 `speed_flexibility` = **17** ≤ 20 ✓、`body_comp` 最长 `abnormal` = 8 ≤ 8 ✓（**恰好塞满，零余量**）、`review_status` 最长 `approved` = 8 ≤ 8 ✓（**同样零余量**）、`version` 最长 `1.0` = 3 ≤ 8 ✓。

⚠️ **但那道遍历测试只覆盖一部分列（P3-A5，与 Task 2 的 P2-A5 同型）**：`tests/db/test_models.py:331-378` 的 `_in_domain_columns()` 是自描述的（遍历 `Base.metadata`、用正则从 `_in_domain` 生成的 `column IN (...)` CHECK 文本反解），**只看得见带 `_in_domain` CHECK 的列**。本表 6 个 `String(n)` 列里，`layer` / `weakness` / `body_comp` / `review_status` **会有** CHECK（自动被覆盖），而 **`template_ref` 与 `version` 没有封闭取值域、不会有 CHECK → 完全不被覆盖**。→ 这两个要在 `test_prescription_templates.py` 里另写断言（从 18 套 YAML 读出实际最长值、与该列 `.type.length` 比）。

⚠️ **`template_ref` 的宽度取决于 `template_id` 的命名，而 spec 已经给了格式**：spec §7.2 `:454` 的 YAML 骨架第一行是 **`template_id: RED-END-ABN-01`**（`<层3>-<桶3>-<体成分3>-<序号2>`，大写、连字符、**14 字符**）。**裁定：照 spec 这个格式命名 18 个 id**，则 `String(32)` 有 18 字符余量、绰绰有余。若另起 snake_case 命名（如 `yellow_speed_flexibility_normal` = **31** 字符）就会逼近上限、且与 spec 的字面骨架不符。

⚠️ spec §4.4 说 `prescription_template` 有「YAML 路径」列。**决定用 `template_ref`（逻辑 id）而不是文件路径**——路径会随目录结构变，而 `template_id` 是 YAML 内容的一部分、已被指纹钉住。若你不同意，报为关切。

- [ ] **Step 7: 变异验收 + Commit**

① 把某套模板的 `review.status` 改成 `pending` → **加载器仍应成功加载、且把它如实读成 `ReviewStatus.PENDING`**（`review_status` 是数据不是校验）。⚠️ **P3-A7：原文接着写「但 Task 4 的匹配器必须拒绝它（本 Task 先只验加载）」——那半句让这条变异在本 Task 内没有任何可观测后果，因此它不是一条变异测试**（硬规矩 #65：一条变异判据必须指明「哪个断言分支」会开火）。**改成可观测的版本**：变异后必须有一条断言变红，那条断言钉的是「加载器**如实保留** `review_status`，不静默把 `pending` 当成 `approved`」——建议直接写一条 `test_loader_preserves_a_pending_review_status_verbatim`，用一份 `tmp_path` 下的合成 YAML（**不动那 18 个被指纹钉住的文件**）；**「匹配器拒绝 pending」整条归 Task 4**（spec §7.2 `:451` 原文：「`review.status != approved` 的模板拒绝用于生成」）。② 删掉一个 `exercise_ref` 对应的动作 → 引用存在性测试红；③ 把 `week_deltas` 改成 3 项 → 长度测试红；④ 把某套红层的 `weekly_frequency` 改成 3 → 指导文件参数测试红；⑤ 把一套 `(green, *, abnormal)` 的 `reachable` 改成 `true` → 不可达标记测试红。

---
