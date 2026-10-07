# Task 2 简报 — 动作库（`exercise` 表 + `exercises.yaml` + `exercise_equivalence.yaml`）

> 抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit `fb5bddb`（控制者用 python 从**已提交**状态抽，抽取前验过工作树干净、blob 与工作树内容一致 —— 硬规矩 #48）。
> 内容 = 计划头部（含 **Global Constraints 10 条** / **Review Focus 5 条** / **File Structure**） + **Task 2 全节**。
> ⚠️ Task 2 全节里的 `P2-A1 … P2-C2` 标记是**控制者预检的更正与裁定**，**它们的完整依据在账本** `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的 `### Task 2: 动作库 — 预检扫描（Pre-flight，控制者亲跑）` 一节。**以更正后的正文为准**，正文里凡写「原文……」的都是已被作废的旧说法。
> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`；**#48–#64 在 Plan 02 账本**（本计划的那份）。**Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用**（已知勘误）。

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
| `backend/app/domain/prescription/templates.py` | 模板的**数据结构**（`@dataclass(frozen=True)`）与维度词表；**不读盘** |
| `backend/app/domain/prescription/match.py` | 层 × 主导短板 × 体成分 → 模板（含 `reachable` 与 `review.status` 判定） |
| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（Tanaka / 220−age 可切换） |
| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配 |
| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换 |
| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加 |
| `backend/app/domain/prescription/triggers.py` | spec §5.2 的五触发条件求值 |
| `backend/app/domain/prescription/weekly.py` | spec §8.4 的「本周训练单 = 骨架第 N 周 × 系数」 |
| `backend/app/refdata_prescription.py` | 加载 18 套模板 YAML 与 `exercise_equivalence.yaml`，**校验后**交给 domain（domain 不读盘） |
| `backend/app/pipeline/prescription_stage.py` | 落库、幂等、`prescription_count` 计数 |
| `backend/data/prescription/*.yaml` | 18 套模板，一套一文件，体育专家可独立审校 |
| `backend/data/exercise_equivalence.yaml` | 低冲击等价动作映射 + **版本号** |
| `backend/data/exercises.yaml` | 动作库的**源**（`exercise` 表由它 seed，理由见 Task 2） |

**新建（测试）**：`backend/tests/domain/test_prescription_{templates,match,intensity,assembler,safety,override,triggers,weekly}.py`、`backend/tests/test_refdata_prescription.py`、`backend/tests/pipeline/test_prescription_stage.py`、`backend/tests/architecture/test_layering.py`

**修改**：`backend/app/db/models.py`（Task 1 拆包 + 4 张新表 + `daily_sync_run` 两列 + 索引）、`backend/app/pipeline/daily.py`（接入处方阶段）、`backend/app/pipeline/{daily,backfill}.py`（改用 `app.config` 与适配器工厂）、`backend/tests/integration/test_golden_cases.py`（黄金用例延伸到训练包）、`Document/…设计spec.md`（§14 补 4 项、§7.2 补 speed_flexibility 空洞的勘误）

**`models.py` 拆包**（终审 C 组第 23 项）：Plan 02 加 4 张表、Plan 03 还要加 7 张，届时约 25 张 / 70 KB。Task 1 把 `models.py` 拆成 `models/{organisation,assessment,derived,prescription,feedback,ops}.py` + `models/__init__.py` 重导出，**保持 `from app.db import models` 与 `models.X` 的既有写法不变**（`test_all_fourteen_tables_created` 的 `==` 断言同步改成「按 Plan 递增的期望值」，Ruling 28 的意图不变）。

---

---

## Task 2: 动作库（`exercise` 表 + `exercises.yaml` + `exercise_equivalence.yaml`）

**Files:**
- Create: `backend/data/exercises.yaml`、`backend/data/exercise_equivalence.yaml`、`backend/app/refdata_prescription.py`、`backend/app/domain/prescription/__init__.py`、`backend/app/domain/prescription/templates.py`（**本 Task 只放 `ImpactLevel`**）、`backend/tests/test_refdata_prescription.py`、`backend/tests/domain/test_prescription_templates.py`
- Modify: `backend/app/db/models/prescription.py`（加 `Exercise` **+ 更正模块 docstring，见 P2-A10**）、`backend/tests/db/test_models.py`（表数 14 → 15、函数名 `test_all_fourteen_tables_created` → `test_all_fifteen_tables_created`，**`== 14` 共 3 处，见 P2-A6**）、`backend/tests/seed/test_generate.py`（补分区穷尽守卫，见 P2-A1）
- **不需要改 `.gitattributes`**（P2-A7：`.gitattributes:14` 已有 `backend/data/*.yaml text eol=lf`，Plan 01 加的；Step 4 只需**确认**新文件落进这条规则，不是 Modify）

⚠️ **`templates.py` 的所有权（P2-B1）**：原文 Task 3 的 Files 写 **Create** `backend/app/domain/prescription/templates.py`，而本 Task 的 Interfaces 又要产出 `app.domain.prescription.templates.ImpactLevel` —— 两个 Task 都「建」同一个文件。**裁定：本 Task 建 `app/domain/prescription/{__init__,templates}.py`，`templates.py` 本 Task 只放 `ImpactLevel`（File Structure `:51` 说它是「模板的数据结构与维度词表；不读盘」，`ImpactLevel` 正是维度词表）；Task 3 对它是 Modify 不是 Create。** 另：`app/domain/prescription/__init__.py`（File Structure `:50` 「公开面重导出」）**原文没有任何 Task 的 Files 段提到要建**，而没有它包不成立 —— 归本 Task。

**Interfaces:**
- Produces:
  - `app.domain.prescription.templates.ImpactLevel(str, Enum)`：`HIGH = "high"` / `MEDIUM = "medium"` / `LOW = "low"`（spec §4.4 的 `exercise.impact_level` 取值域）
  - `app.refdata_prescription.load_exercises() -> dict[str, ExerciseSpec]`（键是 `exercise_ref`，单例缓存，`MappingProxyType` 只读，形状照 `app/refdata.py` 的 **`load_standard()` + `standard()` 这一对**）（P2-A9：实测 `load_standard(path=None)` 只负责加载、**不缓存**，单例是**另一个函数** `standard()`（`app/refdata.py:194`，`global _standard_cache`）；原文只点了前者）
  - `app.refdata_prescription.load_equivalence() -> EquivalenceTable`，`EquivalenceTable.version: str` 与 `.lookup(ref: str, impact_ceiling: ImpactLevel) -> str | None`
  - `ExerciseSpec`：`ref` / `name` / `video_url` / `impact_level` / `targets`（`frozenset[str]`，取值域 = `frozenset(v for v in ITEM_BUCKET.values() if v is not None)`，即 `{"endurance", "strength", "speed_flexibility"}` 三个桶名。⚠️ **P2-A4：不能写成 `set(ITEM_BUCKET.values())`** —— 实测它有 **4** 个值、含 `None`（`ITEM_BUCKET[ScoredItem.BMI] is None`，因为 BMI 天然不属于任何短板桶），那样会把 `None` 放进取值域、让一个空 `targets` 悄悄合法）/ `equipment`

**决定（用户已裁定）**：动作库按 **18 套模板实际引用的 `exercise_ref`** 建，预估 20–30 个；**视频 URL 用可识别的占位符** `https://example.invalid/exercise/<ref>`（`.invalid` 是 RFC 2606 保留 TLD，**保证不可解析**，因此不会被误当成真链接），并在 spec §14 登记「须提供真实视频源」。**不编造真实链接。**

- [ ] **Step 1: 先写模板，再反推动作清单**

⚠️ **不要从 Task 3 的 YAML 反推动作清单**（Ruling 6 更正原文——原文让 T2 先写 T3 的模板，那是让 T2 做 T3 的活、构成循环）。**本 Task 从 spec §7.2:487 点名的动作 + 18 格矩阵的结构推出动作库**：间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、功能性训练、HIIT、两个 addon 模块，再补速度柔韧类 4 个（50 米冲刺间歇、动态拉伸、折返跑、坐位体前屈专项）。
**Task 3 写 YAML 时只能引用本 Task 已建的 ref**；若 T3 需要一个 T2 没建的 ref，**T3 可以往 `exercises.yaml` 追加**（同时更新 T2 的指纹常量），并在报告里列出追加了哪些、为什么。这比「T2 猜 T3 要什么」诚实。

`exercise_ref` 的**唯一所有者是 `exercises.yaml` 的键集**；模板加载器（Task 3）必须校验「每个 `exercise_ref` 都在动作库里」，违例**在加载时**响亮失败并指出是哪个模板文件哪一行（Review Focus 第 1 条）。

⚠️ **`impact_level` 同样是单一所有者（P2-B2，Global Constraint #3）**：spec §7.2 的模板 YAML 字面形状里**每个 block 自带 `impact_level`**（spec `:470-471` `- exercise_ref: interval_run` / `impact_level: high`），而 `exercises.yaml` 的每个动作**也有** `impact_level` —— 同一个值两处存放。原文只声明了 `exercise_ref` 的所有权、没说 `impact_level`。**裁定：`exercises.yaml` 是 `impact_level` 的唯一所有者**；模板 YAML 里可以照 spec 的字面形状写，但 **Task 3 的加载器必须校验「block 的 `impact_level` == 动作库里的值」，不一致就在加载时响亮失败**（与 `exercise_ref` 的处置同构）。本 Task 要在 `ExerciseSpec.impact_level` 的 docstring 里写明自己是所有者、以及谁负责校验。

- [ ] **Step 2: 写失败测试**

`backend/tests/test_refdata_prescription.py`：
- `test_exercises_yaml_fingerprint_is_pinned` —— sha256[:16] 字面钉住。**⚠️ 必须按 Plan 01 的事故教训写**：`hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n"))`，**先归一化再哈希**（Ruling 231：裸字节哈希会随 `core.autocrlf` 变，新克隆必红）。
- `test_every_exercise_has_a_valid_impact_level_and_targets` —— 取值域来自 `ImpactLevel` 与 `ITEM_BUCKET` 的三个桶名（**不从被测 YAML 读回**）。
- `test_equivalence_table_only_maps_to_existing_exercises` —— 等价映射的目标必须都在动作库里（否则安全替换会产出一个不存在的动作）。
- `test_equivalence_never_maps_to_a_higher_impact_level` —— **这是安全属性的核心**：`impact_level` 的序是 `high > medium > low`，映射只能持平或下降。字面写死序关系。
- `test_equivalence_table_has_a_version` —— `version` 非空字符串（spec §7.4 要求把**映射表版本号**写进 `safety_substitutions`）。
- `test_every_high_impact_exercise_has_a_low_substitute` —— 每个 `high` 动作都必须有 `low` 等价物（⚠️ **P2-C2：原文的测试名是 `test_every_impact_level_...`，与它自己的描述不符** —— 名字说「每个 impact level」、描述只要求 `high`。**按描述，名字改掉。** 理由：spec §7.4 `:508-509` 的两个触发（BMI > 30 / 肌肉量 < P10）都只替换 `impact_level: high` 的动作，要求 `medium` 也备一个 `low` 等价物是**过紧的守卫**（硬规矩 #50 的反面：它会为永不发生的场景写断言）），否则 BMI > 30 的安全规则会命中但无解（→ Review Focus 第 5 条的 `needs_review` 路径会被无谓触发）。

- [ ] **Step 3: 跑测试确认失败 → 实现 → 跑通**

`exercises.yaml` 的每个条目：`name`（中文动作名）、`video_url`（占位符）、`impact_level`、`targets`（桶名列表）、`equipment`（如 `none` / `band` / `step` / `ball`）。**spec §7.2 与 §7.2:487 已给出这些动作**：间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、功能性训练、HIIT、能量消耗模块、抗阻优先模块。以此为骨架，按 18 套模板的实际需要补足。

`exercise_equivalence.yaml`：顶层 `version: "1.0"`，然后 `mappings: [{from: <ref>, to: <ref>, max_impact: low, when: bmi_over_30 | muscle_low_p10}]`。**每个 `high` 冲击动作至少要有一个 `low` 等价物**（Step 2 的最后一条测试钉住）。

⚠️ **`volume_reduction` 也在本 Task 写进这个文件**（Ruling 7）：顶层 `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}`，并补一条测试**字面钉住这两个系数**。

⚠️⚠️ **这两个系数在 spec 里没有出处（P2-A3，必须在 YAML 注释与 spec §14 双双登记）**：控制者亲扫 spec 全文，§7.4 `:508` 只写「跑量**按映射表下调**」、**没给任何数**；`:509`（肌肉量 < P10）写「同上」。spec 里唯一出现的 `系数 0.8` 在 `:604`，那是**预警触发的「减量 20%」**（`weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，属 **Plan 03** 的活），与 §7.4 的安全后置跑量下调是**两个不同机制**；`0.9` 在 spec 里**根本没有对应物**。**把 `:604` 的 0.8 借来当 §7.4 的系数，正是控制者错误 #40（Plan01 Ruling 164）那个「借自本仓另一处真实机制、因而通过了所有人直觉审查」的形态。** 处置：① 两个系数按「**本设计的默认规定，无 spec 出处**」写进 `exercise_equivalence.yaml` 的注释；② **本 Task 就往 spec §14 追加一项**（不等 Task 12），因为值在这一刻被写死；③ Task 7 消费时不得把它们当成 spec 条文引用。Task 7 只**消费**、不改这个文件——否则 T7 会让 T2 的指纹测试变红，而「计划中途改自己被指纹钉住的文件」等于让指纹退化成变更记录而不是闸门。

- [ ] **Step 4: `.gitattributes` 与建表**

`.gitattributes` 已有 `backend/data/*.yaml text eol=lf`（Plan 01 加的）——**确认新文件落进这条规则**（`git ls-files --eol -- backend/data/` 应显示 `i/lf w/lf attr/text eol=lf`）。

`Exercise` ORM：`ref: str`（`String(48)`，unique）、`name: str`（`String(64)`）、`video_url: str`（`String(256)`）、`impact_level: str`（`String(8)` + CHECK ∈ `{high, medium, low}`）、`targets: JsonText`、`equipment: str`（`String(32)`）。

⚠️ **列宽必须容得下取值域里最长的值**（硬规矩 #18）。⚠️ **但 Plan 01 那道遍历测试只覆盖一部分列（P2-A5）**：`tests/db/test_models.py:316-394` 的 `_in_domain_columns()` 是**自描述的**（遍历 `Base.metadata`、用正则从 `_in_domain` 生成的 `column IN (...)` CHECK 文本反解出「列 → 允许值集合」，`:312-315` 明写「Plan 02/03 新加的表与列自动被覆盖」）—— 但它**只看得见带 `_in_domain` CHECK 的列**。`Exercise` 的 5 个 `String(n)` 列里**只有 `impact_level` 会有 CHECK**，`ref` / `name` / `video_url` / `equipment` 的取值域不是封闭集合、不会有 `_in_domain` 约束，**因此完全不被那道测试覆盖**。→ 这四个必须在 `test_refdata_prescription.py` 里另写断言（从 `exercises.yaml` 读出实际最长值、与该列 `.type.length` 比），原文「必须过 Plan 01 的列宽遍历测试」会让实现者以为不用自己写。`impact_level` 的 `medium` 是 6、`high` 是 4、`low` 是 3 → `String(8)` 够。`ref` 的最长值**你自己数**（`compound_circuit` 是 16，但你可能起更长的名字）。

⚠️ `test_all_fourteen_tables_created` 用的是 `==`（**Plan 01** 的 Ruling 28：防提前建表。⚠️ 注意 Plan 02 账本里也有一个 Ruling 28，讲的是 `_absolute` 的相对导入档位，**不是同一条**）。本 Task 加第 15 张 → **同步改断言**，并在注释里写明「Plan 02 逐 Task 递增，不得一次性写到 18」。

⚠️ **改动面比原文说的大（P2-A6）**：原文说「同步改**那条**断言」，控制者亲扫 `tests/db/test_models.py`，`== 14` 出现在 **3 处**（`:163`、`:228`、`:472`），另有**函数名本身** `test_all_fourteen_tables_created`（`:24`）含「fourteen」→ 要一起改成 `fifteen`。**并且 `backend/app/db/models/prescription.py:11` 的模块 docstring 按名字引用了这个测试**（`tests/db/test_models.py::test_all_fourteen_tables_created`），改名会让那处引用过期 —— 本 Task 正好要改那个文件（见 P2-A10），一并更新。

- [ ] **Step 5: seed 动作库 + 跑全量 + 变异验收 + Commit**

`exercise` 表由 `exercises.yaml` 灌数据（不是手工插）——理由：**YAML 是专家维护的知识资产，DB 行是它的投影**，两个所有者会漂移。

⚠️⚠️ **原文的 seed 入口方案作废（P2-A1，Critical：与 Global Constraint #10 及两道既有守卫冲突）**。原文写「seed 入口放 `app/seed/prescription.py`（新建），由 `seed_database` 调用」，而：
1. **Global Constraint #10 明写「`app/seed/` 自 Plan 01 结案后重新冻结（Task 1 的依赖迁移会动它一次，见 Task 1 的解冻范围，之后不再动）」** —— 本 Task 不在那个解冻范围里。
2. `seed_database`（实测在 `app/seed/generate.py:382`，**函数是存在的**）的 docstring `:10` 明写它「**只**写组织结构五张表（semester / teacher / student / course_section / enrollment）」，而 `tests/seed/test_generate.py:491` 的 `test_seed_database_writes_only_organisation_tables_and_is_idempotent` 用 `:519` 的 `assert count == 0, f"{table} 不该由 seed_database 写入"` **把这句话变成了守卫**。
3. `test_generate.py:483-488` 的 `ORGANISATION_TABLES`（5 个）+ `DATA_TABLES`（9 个）**恰好穷尽当前 14 张表**（控制者亲验 `Base.metadata.tables` = 14、逐名相符）。这是一个**没人写下来的隐性不变量**：加第 15 张表，它就不再穷尽，而 `exercise` 会静默落在分区之外——`seed_database` 越界写它也不会红。

**裁定（改方案，不改立意）**：
- **不新建 `app/seed/prescription.py`、不改 `seed_database`。** 灌数据函数放 **`app/refdata_prescription.py`**（它已经是 `exercises.yaml` 的加载者，天然是唯一所有者），命名 `sync_exercises(session) -> int`（幂等 upsert、返回写入行数）。
- 理由：① 守住 Global Constraint #10；② 不碰那两道「只写组织结构」的守卫，`test_generate.py:483-488` 的 5+9 分区原样不动；③ **`exercise` 是参考数据、不是仿真人口数据**，与 `app/seed/` 的职责（造仿真人群）本就不同类，它的同类是 `app/refdata.py`。
- **但要补一道分区穷尽守卫**（新增，`tests/seed/test_generate.py`）：断言 `set(ORGANISATION_TABLES) | set(DATA_TABLES) | REFERENCE_TABLES == set(Base.metadata.tables)`，其中 `REFERENCE_TABLES` 本 Task 是 `("exercise",)`、Task 3 加 `prescription_template`、Task 9 加 `prescription` 与 `weekly_adjustment`。**这样第 3 点那个隐性不变量就变成显式守卫**，而 `seed_database` 越界写任何一张参考表/数据表都会红。
- ⚠️ 顺带更正原文的**类比**（P2-A2）：原文说「理由与 Plan 01 的评分表同构：YAML 是专家维护的知识资产，**DB 行是它的投影**」——**这个类比是假的**。控制者亲验 `Base.metadata.tables` 的 14 个名字，**国标评分表根本没有投影成 DB 表**：它由 `app/refdata.py` 的 `load_standard()` / `standard()` 从 CSV 读进内存，全程不入库。「DB 行是它的投影」这半句是**借自本仓另一处真实机制**（`app/seed/` 确实把仿真数据投影成 DB 行）而套到了一个不成立的对象上 —— 与控制者错误 #40 同型。
- ⚠️ **禁区纪律**：验证 `sync_exercises` 只能在测试的 session fixture 里做（内存库或 `tmp_path`），**不得跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写 `backend/data/seed/` 与 `backend/pe.db` 两个禁区）。

变异：① 把某个 `high` 动作的等价物改成另一个 `high` → 「不升冲击」测试必须红；② 把一个 `exercise_ref` 从 `exercises.yaml` 删掉 → **本 Task 只有指纹测试会红**（⚠️ **P2-C1：原文还要求「模板引用存在性」测试变红，但那个测试是 Task 3 才建的，在本 Task 里按字面不可满足** —— 这是控制者错误 #46/#47 那个形态：派一条做不到的验收判据。那半留给 Task 3）；③ 删掉 `version` → 版本测试必须红。

---
