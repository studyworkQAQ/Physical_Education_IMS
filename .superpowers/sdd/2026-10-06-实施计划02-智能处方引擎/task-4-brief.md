# Task 4 简报 — 模板匹配器（`match.py`）

> 抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit `8631744`（控制者用 python 从**已提交**状态抽，抽前验过工作树干净、blob 与工作树内容一致 —— 硬规矩 #48）。
> 内容 = 计划头部（**Global Constraints 10 条** / **Review Focus 5 条** / **File Structure**） + **Task 4 全节**。
> ⚠️ Task 4 全节里的 `P4-A1 … P4-A7` 标记是**控制者预检的更正与裁定**，完整依据在账本 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的 `### Task 4: 模板匹配器 — 预检扫描（Pre-flight，控制者亲跑）` 一节。**以更正后的正文为准**；正文里凡写「原文……」的都是已被作废的旧说法。
> ⚠️ **本 Task 最重要的两条裁定**：**P4-A3**（完整优先级链 `NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`，32 格穷举的 8/6/3/15 只在这条链下成立）与 **P4-A2**（读 `template.reachable` **字段**、不调 `is_reachable` 函数）。
> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（约 806 KB）；**#48–#76 在 Plan 02 账本**（上面那个 progress.md，约 296 KB）。**Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用**（已知勘误）。

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

## Task 4: 模板匹配器（`match.py`）

**Files:**
- Create: `backend/app/domain/prescription/match.py`、`backend/tests/domain/test_prescription_match.py`
- Modify（⚠️ **P4-A6：原文一个字都没提，但本 Task 必然要动**）：
  - `backend/app/domain/prescription/__init__.py` —— 公开面重导出 `MatchInput` / `MatchOutcome` / `MatchStatus` / `match_template`（`__all__` 从 **20** 个名字扩到 20+N）
  - `backend/tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE`（今天是 **20 个 `(名字, 所有者模块)` 二元组**）与它的 `assert len(...) == 20`（可 grep 原文：`基线是 20 个名字，抄漏了就当场红`）**两处都要改**；**新基线仍必须是字面清单**，不得改成 `list(pkg.__all__)`（硬规矩 #35）。更新模式照 Task 3 的 Ruling 136-1
  - `backend/tests/architecture/test_domain_purity.py` 与 `test_layering.py` —— **三处已过期/写错的陈述**（控制者亲扫定位，按可 grep 的原文找）：
    ① `# Task 2 会新建 app/domain/prescription/ 子包（今天不存在）` —— **子包自 Task 2 起就存在、Task 3 已填满**；
    ② `但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写` —— **`match.py` 是 Task 4 的，不是 Task 3 的**；
    ③ `# Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py` —— 那一格矩阵是 **Task 1 fix round 5** 为 **Task 4** 的形状埋的，归属写错了两处。
    另：全仓相对导入的计数今天是 **16**（全部 `level == 1`），`match.py` 若写相对导入会变 17；架构守卫的扫描面今天是 **27**（pipeline 7 + db 11 + domain 9），加 `match.py` 后是 **28**——**这些数散在两份守卫的 docstring 里多处，改前先 grep（硬规矩 #66）**
  - **本 Task 还要接手 Task 3 转来的 4 项**（账本 Ruling 134-1，都在这两个架构守卫文件与 `tests/domain/` 下）：① `cases` 矩阵换成「扫真仓每个 `.py` 逐个对拍 `resolve_name`」（Ruling 56/66，可一次性解决 Ruling 54/56/67 三条）；② `_package_of` 的断言换成「扫真仓每个 `.py` 与 `py.relative_to(BACKEND).parent.parts` 对拍」（C-fr4-1）；③ `EquivalenceTable.lookup()` 的分支测试搬到新建的 `tests/domain/test_prescription_exercises.py`（Ruling 107-1：它今天住在 `tests/test_refdata_prescription.py`，失效形态是「删那两条测试、`pytest` 退出码仍 0、只有 `BrPart` 变红」）；④ `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺「本条之前」这个时点（Ruling 127-5）。
    **⚠️ ①②③ 会让 passed 数变化，属预期，逐条说明。若你判断某一项该推到 Task 5，报为关切并说明理由——不要为了「符合派单」而硬做。**

**Interfaces:**
- Consumes: Task 3 的 `Template` / `WeaknessBucket` / `BodyCompState` / **`ReviewStatus`**（`NOT_APPROVED` 要用，控制者实跑其成员 = `PENDING="pending"` / `APPROVED="approved"`）/ **`is_reachable`**（见 P4-A2）；Plan 01 的 `app.domain.stratify.Layer`（⚠️ **P4-A1：原文漏了 `ReviewStatus` 与 `is_reachable` 两个**——前者是 `NOT_APPROVED` 的判据来源，后者是 `reachable` 规则的**唯一所有者**，而它的 docstring 里明写「**两处消费**：① 加载器…；② **Task 4 的匹配器按它排除预留位**」。另注：Task 3 已把 `Layer` **re-export** 进 `templates`，故 `from .templates import Layer` 与 `from app.domain.stratify import Layer` 都可用；**唯一所有者是 `app.domain.stratify`，选哪条路径要在 docstring 里说明**）
- Produces:
  - `MatchInput`（frozen dataclass）：`layer: Layer` / `dominant_bucket: str | None` / `body_comp_abnormal: bool`
  - `MatchOutcome`（frozen dataclass）：`template: Template | None` / `status: MatchStatus` / `reason: str`
  - `MatchStatus(str, Enum)`：`MATCHED` / `NO_LAYER`（`insufficient_data`，Z0 闸门拦下）/ `NO_BUCKET`（`dominant_bucket is None`）/ `UNREACHABLE`（命中 `(green,*,abnormal)` 预留位）/ `NOT_APPROVED`（`review_status != approved`）/ `NO_TEMPLATE`（矩阵里缺这一格）
  - `match_template(inp: MatchInput, templates: Mapping[str, Template]) -> MatchOutcome`

**决定**：
- **`dominant_bucket is None` 是合法状态**，不是错误：Plan 01 的 `find_weaknesses` 在 6 项全缺测时返回 `dominant_bucket = None`（⚠️ **P4-A5：原文引的 `derive.py:330` 是**空行**。**控制者实跑定位的真实位置**：字段声明 `dominant_bucket: str | None` 在 `derive.py:129`（`WeaknessResult` 的字段）、口径说明在 `:320` 起的 docstring、赋值处 `dominant_bucket=dominant` 在 `:371`；「按声明序取先出现者」的 `_BUCKET_ORDER` 在 `:77`、消费在 `:352`/`:356`。**原文说的「Ruling 175 补的测试」控制者没有核**（那是 Plan 01 账本里的裁定号，本轮没去查）——**实现者若要引用它，自己核一遍**（硬规矩 #52/#61）。**按可 grep 的原文找：`git grep -n "dominant_bucket" -- backend/app/domain/derive.py`**）。此时**不得生成处方**，`status = NO_BUCKET`，`reason` 要能让教师看懂（「6 个短板判定项全部缺测，无法确定主导短板」）。
- **`layer == Layer.INSUFFICIENT` → `NO_LAYER`**，理由同上（Review Focus 第 3 条）。`reason` 要复用 Plan 01 `stratify.explain()` 的 Z0 文案口径，不要另造一套说法。**（P4-A7：控制者实跑取到确切原文，免得实现者自己造第二套）**`app/domain/stratify.py` 的 `_REASON` 映射里，`RuleId.Z0` 对应的是 f-string **`f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`**；`explain()` 在 `:326`，其 Z0 分支的说明是「`Z0` 路径单独成句：它没有颜色可报，要说的是「为什么没有分层结果」以及下一步」。**`NO_LAYER` 的 `reason` 应当与这条同源**——要么直接复用 `_REASON[RuleId.Z0]`（import 它），要么逐字引用并注明出处；**不要另写一句意思相近的话**（那就是第二个所有者）。
- **`UNREACHABLE` 与 `NOT_APPROVED` 都要留痕**，不能静默返回 `None`。spec §11.2 对 `NOT_APPROVED` 的要求是「拒绝生成，返回『模板待审校』，教师端提示」——所以 `reason` 的措辞要能直接上教师端。
- **`match_template` 不做 I/O、不读盘**：`templates` 由调用方注入（domain 纯净性）。

- [ ] **Step 1: 写失败测试**

穷举 **4 层 × 4 桶（3 个真桶 + `None`）× 2 体成分 = 32 个组合**，对每个组合断言 `status` 与（若 `MATCHED`）`template.template_id`。**期望表字面写在测试里**（硬规矩 #35），不从 `templates` 反推。其中：
- `insufficient_data` 层的 8 个组合 → 全部 `NO_LAYER`
- `dominant_bucket is None` 的 6 个组合（3 层 × 2 体成分）→ 全部 `NO_BUCKET`
- `(green, *, abnormal)` 3 个 → `UNREACHABLE`
- 其余 15 个 → `MATCHED`，且 `template_id` 逐个字面写死

另加：
- `test_match_rejects_an_unapproved_template` —— 直接构造 `review_status=ReviewStatus.PENDING` 的 `Template`（frozen dataclass 可直接构造，**不必改 YAML**）→ `NOT_APPROVED`，且 `reason` 含「待审校」。
- `test_match_rejects_a_missing_matrix_cell` —— 从注入的 `templates` 里删掉一格 → `NO_TEMPLATE`，`reason` 指出缺哪一格。**这守的是「YAML 少了一个文件」不会被当成「这个学生不该有处方」。**
- `test_match_is_deterministic_under_dict_ordering` —— 把 `templates` 的插入顺序打乱（`dict(reversed(list(...)))`），结果必须逐字相同。Plan 01 的 Ruling 100 就是为此把 `_BUCKET_ORDER` 做成声明序的。

- [ ] **Step 2–5: 跑失败 → 实现 → 跑通 → 变异验收**

实现要点：匹配键是 `(layer.value, dominant_bucket, "abnormal" if body_comp_abnormal else "normal")`。

⚠️ **P4-A3：完整的优先级链原文没有给出，而 32 格穷举的期望表完全依赖它。** 原文只说了相邻的一对（`reachable` 先于 `review_status`）。**控制者按 `:386-389` 的分类实算过 32 格**，得到 `{NO_LAYER: 8, NO_BUCKET: 6, UNREACHABLE: 3, MATCHED: 15}`（**与原文的 8/6/3/15 逐字相符**），而这个分类**只在下面这条链下成立**：

```
NO_LAYER  →  NO_BUCKET  →  NO_TEMPLATE  →  UNREACHABLE  →  NOT_APPROVED  →  MATCHED
```

**承重的两处**：
- **`NO_BUCKET` 必须先于 `UNREACHABLE`**：`(green, None, abnormal)` 这一格同时满足「桶为空」与「绿层+异常」，**原文的 6 个 `NO_BUCKET` 里包含它**，所以它必须判 `NO_BUCKET`。若顺序反过来，分类会变成 `{NO_LAYER:8, NO_BUCKET:4, UNREACHABLE:5, MATCHED:15}`——**总数仍是 32，穷举测试仍会「通过」某个版本，但期望表就换了**。这是「顺序承重」最隐蔽的形态：错了也不会让计数对不上。
- **`NO_TEMPLATE` 必须先于 `UNREACHABLE`/`NOT_APPROVED`**：查不到模板就没有 `reachable` / `review_status` 可读。
- `UNREACHABLE` 先于 `NOT_APPROVED`（原文已给）：一套既不可达又未审校的模板报 `UNREACHABLE`（**规格事实**）而不是 `NOT_APPROVED`（**流程状态**）。

**把整条链与这三处理由写进 `match_template` 的 docstring**，并在穷举测试里**按链的顺序组织期望表**（读者能从表的排列看出顺序是被测的）。

⚠️ **P4-A2：「先查 `reachable`」有歧义——查的是 `Template.reachable` 这个**字段**，还是调 `is_reachable(...)` 这个**函数**？** 控制者实跑：`is_reachable` 的函数体是 `return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)`，它的 docstring 自称「``reachable`` 的**唯一所有者**」，并说加载器用它校验 YAML 里写的 `reachable` 与维度组合不矛盾（矛盾就在加载时响亮失败）。

**裁定：`match.py` 读**字段** `template.reachable`，不调 `is_reachable`。** 理由：① `is_reachable` 是**规则的**唯一所有者，而**数据的**唯一所有者是 YAML 的 `reachable` 字段，加载器已经强制两者一致——匹配器再算一遍就是**第三个住址**（违反 Global Constraint #3）；② `match_template` 是**消费者**，它吃的是「已经过校验的 `Template`」，重新推导会掩盖「加载器没校验」这个真故障；③ 读字段让 `test_match_rejects_an_unapproved_template` 那类**直接构造 `Template` 实例**的测试（`:392`）行为可预测——构造时写什么 `reachable` 就是什么。
**但 `match.py` 的 docstring 必须写明**：规则的所有者是 :func:`app.domain.prescription.templates.is_reachable`，本函数只消费加载器已校验过的字段；**若有人绕过加载器手工构造了一个 `reachable` 与维度矛盾的 `Template`，本函数不会发现**（硬规矩 #39：写清守不住什么）。

变异：① 把 `reachable` 检查删掉 → **3 个 `UNREACHABLE` 组合会全部变成 `MATCHED`**，穷举测试必须红（⚠️ **P4-A4：原文写「变成 `NOT_APPROVED` 或 `MATCHED`」——18 套模板今天**全部** `review.status: approved`（控制者实跑：`review.status` 的 distinct 值只有 `approved` 一个），故删掉 `reachable` 检查后**只可能是 `MATCHED`，不可能是 `NOT_APPROVED`**。按硬规矩 #65，变异判据要写明**哪个断言分支**开火：这里是穷举测试里那 3 格的 `status` 期望值）；② 把 `review_status` 检查删掉 → `test_match_rejects_an_unapproved_template` 必须红；③ 把 `Layer.INSUFFICIENT` 的分支删掉 → 8 个 `NO_LAYER` 组合必须红。

- [ ] **Step 6: Commit**

---
