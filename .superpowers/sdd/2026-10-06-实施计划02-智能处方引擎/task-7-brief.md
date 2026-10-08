# Task 7 简报 — 处方生成阶段接入管道（`prescription_stage.py`）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `d498bac`，190726 B / 1024 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 7 全节（含预检更正 P7-A1..A10）**。Task 1–6 与 Task 8–9 的正文**不在本简报里**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`d498bac`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **716 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**（带 `--cov` 时 `715 passed, 1 skipped`）。
**表数基线**：**18 张**（本 Task 不建表）。
**公开面基线**：`app.domain.prescription.__all__` = **47**；`_PRESCRIPTION_PUBLIC_BASELINE` = **47**；`_MODELS_PUBLIC_BASELINE` = **33（刻意不动，Ruling 97）**。
**架构守卫扫描面基线**：**33**（pipeline 7 + db 11 + domain 15）；本 Task 新建 1 个 pipeline 模块 → **34**。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 并记进报告。**若撞上 `ImportError: DLL load failed`（Smart App Control 拦 `.pyd`），立刻停手报回控制者**，不要动系统安全设置、不要升降级依赖。

## 0.1 ⚠️ 本 Task 是全计划改动面最大的一个，也是唯一一个要改 Plan 01 已结案代码的

**新建**：`app/pipeline/prescription_stage.py` + `tests/pipeline/test_prescription_stage.py`
**改 4 个已结案文件**：
- `app/pipeline/daily.py` —— 阶段序列插 `Prescribe`、`_replay_cleanup` 的清单加两张表
- `app/pipeline/run_stratify.py` —— **`PersonInputs` 加 3 个字段**、`input_snapshot_of` 加 2 个键、`resolve_muscle_lines` 同时回填 P10
- `app/pipeline/percentile_stage.py` —— `PersonInputs` 的构造点之一（预跑占位路径）
- **`app/domain/percentile.py`** —— **新增 `lookup_p10`**（⚠️ 这是 domain，会动覆盖率分母）
**改测试**：`tests/pipeline/test_daily.py`（`PIPELINE_TABLES` 9 → 11 + docstring 的「9 张表」）
**接收 Task 6 移来的 2 条集成测试**（Step 0）

**建议分 4 次 commit**：① `lookup_p10` + `PersonInputs` 三字段 + `input_snapshot_of` 两键 + `resolve_muscle_lines`（**这一组必须一次做完，否则中间态跑不起来**）；② `prescription_stage.py` + 它的测试；③ `daily.py` 接入 + `_replay_cleanup` + Step 0 的两条集成测试；④ 收尾（`PIPELINE_TABLES` 扩表、公开面、变异取证、全量）。

## 0.2 ⚠️ 4 条 Critical（逐条照办，不要按计划原文的字面做）

- **P7-A1**：`PersonInputs` **没有身高体重** → `input_snapshot_of` 今天算不出 `bmi`。**加 `height_cm` / `weight_kg` 两个字段**（实测构造点只有 3 处：`percentile_stage.py` 的预跑占位、`run_stratify.py` 的黄金用例路径、`run_stratify.py` 的从库构造路径 —— **最后这一处能拿到 `fitness_test_result` 的行，身高体重是现成的**）。**否掉的两条路**：给 `input_snapshot_of` 加形参；让 `profile_of` 查库重算（第二个所有者）。
- **P7-A2**：黄金用例路径今天写的是 `case["snapshot_muscle_p20"]`（**硬下标**）。新增的两个字段**一律用 `case.get("height_cm")` / `case.get("weight_kg")`**（缺省 `None`；`bmi_of` 的签名实测是 `float | None → float | None`）。**不许改 `golden_cases.json`**（那是 Task 9 的文件）；Task 9 的正文已被控制者按硬规矩 #86 补上连带要求。
- **P7-A3**：`percentile.py` **没有 `lookup_p10`**（但 `PercentileRow` 有 `p10` 字段、DB 也有 `p10` 列）。**新增它，逐字照 `lookup_p20` 的口径**（同一个 `_lookup_row`、同一套「样本 < MIN_SAMPLE 返回 `None`」语义、同一段 docstring 结构）。**⚠️ 两条红线**：① **P10 绝不得进入分层判定** —— `flag_body_comp` / `evaluate` / `derive` 一律**不读**它；读进去就会改 Plan 01 已结案的标签、13 例黄金用例当场红。② **domain 覆盖率分母会变**（`percentile.py` 今天 94 stmts / 26 branch），新函数必须 100% 覆盖，含「组不存在 → `None`」与「样本不足 → `None`」两档。
- **P7-A4**：`_replay_cleanup` 的**两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97），写 `models.Prescription` 会 `AttributeError` → 必须 `from app.db.models.prescription import Prescription, WeeklyAdjustment`；② `weekly_adjustment` 有 **FK 到 `prescription`**，SQLite 跑在 `PRAGMA foreign_keys=ON` 下，**先删 `prescription` 会当场 FK 违例** → 清单顺序必须是 **`(DerivedMetrics, StratificationResult, PercentileSnapshot, WeeklyAdjustment, Prescription)`，子表先删**，代码注释写明「顺序承重」，并**有一条测试钉住它**。

## 0.3 其余 6 条（简报的预检总表里有完整实测依据）

- **P7-A5**：`PIPELINE_TABLES` **9 → 11**（加两张新表）+ `canonical_dump` docstring 里的「9 张表」同步改。
- **P7-A6**：**Plan 01 那条 canonical sha256 测试不会红**（它断言的是 `first == second`，不是与字面哈希相等；字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 0 命中）。**但扩表 + 加键之后，账本与 spec §1.3 印着的那个哈希与「行数合计 882」必须重测**，把新值写进报告（控制者会负责回填账本与 spec）。
- **P7-A7**：`assert first == second` 实测有**两处**，两处都要重跑并在报告里分别给结论。
- **P7-A8**：`muscle_line_gaps == 4` / `error_summary is None` 按**可 grep 的原文**找（`git grep -n "muscle_line_gaps == 4" -- backend/`），**不要用计划里的裸行号**（已过期）。
- **P7-A9**：`bmi_of` 的 docstring **已预写 Plan 02 的用途**，Task 1 已铺好路 —— `profile_of` **不必自己算 BMI**，只从快照读。
- **P7-A10**：控制者错误 #147（探针用正则数键漏了 `W`/`C` 两个大写键）→ 硬规矩 #89：**数键/字段/成员一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(Enum))`），**绝不用正则数源码**。你也要遵守这条。

## 0.4 Task 6 结案时按硬规矩 #86 传导过来的四件事（计划正文已写，这里点名）

1. **`prescription.microcycle_weeks`** ← `Template.microcycle_weeks`。**漏填会让 `valid_to` 无从复算**（Task 6 的触发 3 与 `valid_to` 的算式都读它）。
2. **`prescription.previous_had_overrides`** ← 生成时查上一张处方的 `teacher_overrides` 是否非空。**这是「界面提示『该生上次存在人工覆盖』」的唯一载体**，不是 `assembly_snapshot` 里的键（往快照加键会让 Task 5 钉死的 12 键 / +3 键两条守卫变红）。
3. **`weekly_adjustment.batch_id`** ← 本批的 `batch_id`；**教师手工加的调整行没有批次**，取该行所属处方当前的 `batch_id`（若处方尚未落库则取本次运行的批次），并在表注释里写明这个口径。
4. **`skipped_reasons` 必须有 `"insufficient_data"` 这个键**（Task 6 实现者报的最高优先级关切）：`evaluate_triggers` 是纯函数、没有渠道把「为什么返回空」传出来，而 Z0 闸门拦下的学生（Plan 01 实测缺省注入下 500 人有 **2** 人）会让教师端的「重新生成」按钮**无声失败**。要有一条测试钉住这 2 人落进这一格。

## 1. 执行强度（账本 Ruling 145）

**目标 1–2 轮 fix round**（Task 5 用了 1 轮、Task 6 用了 0 轮）。**但控制者预期本 Task 的评审要比前两个更细**，因为它改 Plan 01 已结案的代码。

**保留（一条不许砍）**：TDD；`app/domain/` 分支覆盖 **100%**；4 条变异（Step 2–6 那段）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01 的全部既有测试必须仍然全绿**（这是本 Task 的硬门槛 —— 你改的是已结案代码）。

**取消**：纯散文精度 → 记进报告的「待清扫」清单。**但 Critical 级一律当场修。**

## 2. 变异取证纪律（硬规矩 #83 + #89）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。
**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`。Task 5 的实现者做过一次**等长改动**（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**（sha256 已还原成功而 pytest 仍报变异行为）。**假绿更危险。**
每条变异写明：**改了哪一行 → 哪条测试的哪个断言分支变红（贴那一句 `assert`）→ 三重还原后的 sha256 与变异前逐字相同**。
⚠️ **控制者亲验过 Task 5 的变异 ②**（等长 `True` → `None`，M0 2 passed → 变异后 `1 failed`（`assert None is True`）→ sha256 `BC471A4B5161D10C` → `53C57434FD5AAEEE` → `BC471A4B5161D10C`）。**本 Task 控制者也会亲验至少一条。**

## 3. 硬约束

1. **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / **`datetime`**；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy, typing}`。⚠️ **`lookup_p10` 住在 domain**，故它也不能碰 I/O —— 照 `lookup_p20` 抄就不会错。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`）。
3. **单一所有者**：`Layer` 的所有者是 `stratify.py`；`bmi_of` 的所有者是 `indicators.py`（`run_stratify` 只是重导出）；`lookup_p20`/`lookup_p10` 的所有者是 `percentile.py`。
4. **断言两侧不得同源**：期望值字面写在测试里（硬规矩 #35）。
5. **TDD**：先写失败测试、跑红、再实现。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`，要落 CSV 就 `write_csv(ds, <临时目录>)`。⚠️ **`golden_cases.json` 也不许改**（P7-A2）。
7. **PowerShell**：`;` 分隔，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
8. **`git add` 按文件名逐个加**，不要 `git add -A`。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**

## 4. ⚠️ 若你认为本简报/计划某条决定是错的，**顶回来**

Plan 02 到目前为止实现者顶回控制者 **16 次，16 次都是对的**（最近 4 次见账本 Ruling 150，包括「派单要求把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 35 —— 照做会破坏 Ruling 97 那条有意的架构守卫、让断言两侧同源、让函数名变成谎话」）。共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 5. 报告

写进 `task-7-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它**（IDE 曾把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB）。

至少 8 节：
1. 环境与基线复现
2. **Plan 01 既有测试的回归结论**（本 Task 的硬门槛：改了 4 个已结案文件，Plan 01 的测试必须仍全绿；逐条给 `test_daily.py` 两处 `assert first == second` 的结论）
3. `PersonInputs` 的 3 个新字段 + 3 个构造点各自怎么填的（逐点说明）
4. `lookup_p10` 的实现与它与 `lookup_p20` 的**逐字对照**（哪些地方相同、哪些地方必须不同）+ 「P10 不进分层判定」的守卫测试
5. `prescription_stage.py` 的公开面 + Task 6 传导过来的 4 件事逐条落地位置
6. **canonical sha256 的新实测值**（扩表 + 加键之后）与「行数合计」的新值 —— 控制者要拿它回填账本与 spec §1.3
7. 变异取证（4 条 + M0 + M1，按第 2 节的纪律）
8. 待清扫清单 / 关切 / 没按派单做的地方（0 处也要写「0 处」）/ 最终验收（passed 数、覆盖率四格、`__all__`、扫描面、三个指纹、`git diff d498bac HEAD -- backend/data` 为空）

## 6. 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数（716 → ?）/ 覆盖率四格 / 扫描面（33 → 34）/ `PIPELINE_TABLES` 是否 11 / canonical sha256 的新值与行数合计 / Plan 01 既有测试是否全绿 / 4 条变异的结论 / Task 6 传导的 4 件事是否全部落地 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

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

## Task 7: 处方生成阶段接入管道（`prescription_stage.py`）

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `537683f`，取证脚本 `t7_probes/_t7_probe{1,2,3}.py`）

**测试基线**：`716 passed`；`app/domain/` **948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**；**18 张表**；`__all__` **47**；扫描面 **33**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P7-A1** | **Critical** | **`PersonInputs` 上没有身高体重**，故 `input_snapshot_of` 今天**算不出 `bmi` 原始值**。实测 `PersonInputs` 的 **12 个字段** = `student_id / sex / age_group / prev_age_group / curr_scores / prev_scores / curr_total / prev_total / years / body_fat_pct / muscle_mass_kg / snapshot_muscle_p20`。`bmi_of(height_cm, weight_kg)` 住在 `app/domain/indicators.py`，而 `input_snapshot_of(evaluated, result, snapshot)` 的三个参数里**没有任何一个带身高体重**。原始值只在 `fitness_test_result` 表的 `height_cm` / `weight_kg` 两列里。 | **给 `PersonInputs` 加两个字段 `height_cm: float | None` 与 `weight_kg: float | None`**，`input_snapshot_of` 里加 `"bmi": bmi_of(person.height_cm, person.weight_kg)`。**实测构造点只有 3 处**：`percentile_stage.py`（预跑占位路径）、`run_stratify.py` 的黄金用例路径、`run_stratify.py` 的从库构造路径（**这一处能拿到 `fitness_test_result` 的行，身高体重是现成的**）。**否掉另两条路**：给 `input_snapshot_of` 加参数（签名多一个只在快照里用的形参，而 `PersonInputs` 本来就是它的输入载体）；让 `profile_of` 自己查库重算（计划自己已否：第二个所有者） |
| **P7-A2** | **Critical** | **黄金用例路径用硬下标**：`run_stratify.py` 的那一处写的是 `snapshot_muscle_p20=case["snapshot_muscle_p20"]`。若照同样写法加 `height_cm=case["height_cm"]`，**现有 13 例 fixture 会当场 `KeyError`** —— 而 `golden_cases.json` 是 **Task 9** 才改的文件。 | 新增的两个字段**一律用 `case.get("height_cm")` / `case.get("weight_kg")`**（缺省 `None`；`bmi_of(None, None)` 按签名返回 `None`，实测其签名就是 `float | None`）。于是 Task 7 之后黄金用例路径的快照里 `"bmi"` 是 `None`，**直到 Task 9 给 13 例补上身高体重**。⚠️ **已按硬规矩 #86 当场把这条写进 Task 9 的正文**（否则 Task 9 的实现者只会加 `expected` 字段、不会加**输入**字段，而缺了输入，安全触发那三档在黄金用例里根本走不到） |
| **P7-A3** | **Critical** | **`percentile.py` 没有 `lookup_p10`**。实测它的公开函数只有 `lookup_p25` / `lookup_p20` / `lines_used` / `compute_snapshot` / `national_norm` / `norm_is_derivable` / `summarize_source` / `summarize_source`。**但 `PercentileRow` 有 `p10` 字段**（实测 10 个字段：`item / sex / age_group / p10 / p20 / p25 / p50 / p75 / sample_size / source`），DB 的 `percentile_snapshot` 表也有 `p10` 列——**数据在，只是没有取法**。 | **给 `app/domain/percentile.py` 新增 `lookup_p10(snapshot, sex, age_group) -> float | None`**，**逐字照 `lookup_p20` 的口径**（同一个 `_lookup_row`、同一套「样本 < MIN_SAMPLE 就返回 `None`」语义、同一段 docstring 结构）。然后：`PersonInputs` 加 `snapshot_muscle_p10` 字段、`resolve_muscle_lines` 用 `dataclasses.replace` **同时**回填 P20 与 P10、`input_snapshot_of` 加 `"snapshot_muscle_p10"` 键。⚠️ **两条红线**：① **P10 绝不得进入分层判定**（`flag_body_comp` / `evaluate` 一律不读它）——它只服务 spec §7.4 的处方安全触发；读进去就会改 Plan 01 已结案的标签，而 Plan 01 的 13 例黄金用例会当场红。② **domain 覆盖率的分母会变**（`percentile.py` 今天 94/26，加一个函数后 stmts 与 branch 都涨），新函数必须 100% 覆盖，含「组不存在 → `None`」与「样本不足 → `None`」两档 |
| **P7-A4** | **Critical** | `_replay_cleanup` 的清单实测是 `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot)`，走 `repo.delete_by_batch`。**两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97 / Task 6 的顶回 1），写 `models.Prescription` 会 `AttributeError`；② `weekly_adjustment` 有 **FK 到 `prescription`**，而 SQLite 跑在 `PRAGMA foreign_keys=ON` 下——**先删 `prescription` 会当场 FK 违例**。 | 清单写成 `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot, WeeklyAdjustment, Prescription)`——**`WeeklyAdjustment` 必须排在 `Prescription` 前面**，并在代码注释里写明「顺序承重：子表先删」。import 走 `from app.db.models.prescription import Prescription, WeeklyAdjustment`。**要有一条测试钉住这个顺序**（构造一批带调整行的处方，跑 `_replay_cleanup`，断言两张表都空且没抛 FK 错） |
| P7-A5 | Important | `PIPELINE_TABLES` 实测 **9 张**（`fitness_test_batch / fitness_test_result / body_composition / interest_survey / percentile_snapshot / derived_metrics / stratification_result / daily_sync_run / cleaning_log`），`canonical_dump` 的 docstring 逐字写着「**9 张表**的全部行」。 | **扩到 11 张**（加 `prescription` 与 `weekly_adjustment`），docstring 的「9 张」同步改。理由：那条断言是「幂等性的**强**断言」（Ruling 218），而处方是本计划新加的最大一块派生数据；不覆盖等于「重放翻倍」这个失效形态只被一条较弱的行数断言守着。⚠️ **连带**：扩表之后那个 canonical sha256 的值**真的会变** → 见 P7-A6 |
| P7-A6 | Important | 计划原文说「加键之后，**Plan 01 那条『全表 canonical sha256』测试的实测值会变**」——**这句会被读成「测试会红」，而它不会**。实测那条断言是 `assert first == second`（**两次运行相等**），不是与一个字面哈希相等；字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 **0 命中**，只出现在账本、spec §1.3 的勘误段与计划正文里。 | 改成两句：① **测试不会红**（它比的是两次运行，不是字面哈希）；② **但散文里的值会过期**——账本与 spec §1.3 印着的 `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` 与「行数合计 882」**在 P7-A5 扩表 + P7-A1/A3 加键之后都必须重测**，两处都要更新并注明是哪个 commit 改的（硬规矩 #26；Ruling 229 记过一次「一个修复改变了另一个修复的取证基线」） |
| P7-A7 | Minor | `assert first == second` 实测有**两处**（一处在 canonical sha256 那条测试里，另一处在一个更早的幂等测试里），计划只提了一处。 | 加键与扩表之后**两处都要重跑**，报告里分别给结论 |
| P7-A8 | Minor | 计划写「`tests/pipeline/test_daily.py:717-751` 已钉住」`muscle_line_gaps` 恒为 4 / `error_summary` 恒为 NULL。实测那两条断言在**别的位置**（`assert run.muscle_line_gaps == 4` 与 `assert run.error_summary is None`，且**各有两处**）。**结论是对的，裸行号是过期的。** | 按硬规矩 #78 改成可 grep 的原文片段（`git grep -n "muscle_line_gaps == 4" -- backend/`），不写裸行号 |
| P7-A9 | Minor | `bmi_of` 的 docstring **已经预写了 Plan 02 的用途**：逐字有「spec §7.4 的安全后置规则要用『BMI > 30』这个**原始值**（不是国标得分），Plan 02 的 `StudentProfile.bmi` 因此必须由 domain 自己算得出来」，并写明它原先住在 `run_stratify.py`、Task 1 迁走、`run_stratify.bmi_of` 仍重导出可用。 | 无需更正（计划的说法对）。**Task 1 已经为这一步铺好路**，`profile_of` 不必自己算 BMI，只从快照读 |
| P7-A10 | — | **控制者错误 #147**：预检探针用 `[a-z_0-9]+` 这个正则去数 `input_snapshot_of` 返回字典的键，**漏了 `W` 与 `C` 两个大写键**，数出 **24** 而实为 **26**。计划的「26 个键」与它列的 26 个名字**逐格正确**（我按函数体逐行数过一遍坐实）。 | **计划是对的，探针是错的。** → **这是硬规矩 #80 连续第 3 次被违反**（#80 立于 Ruling 147、#82 立于 P5-A10、本次是 #147），三次全是同一形状：**用一个自己没验证的查询去数一个已经写在计划里的量，然后把「我的查询没显示」讲成「计划写错了」**。→ **补硬规矩 #89：数键/数字段/数成员时，一律用 `len(dict)` / `len(dataclass.fields)` / `len(list(Enum))` 这类运行时口径，绝不用正则去数源码——正则的字符类会静默漏掉它没想到的形状（大写键、跨行元组、注释里的同名词）。** |

**扫描面**：本 Task 新建 `app/pipeline/prescription_stage.py` → pipeline 7 → **8**，扫描面 33 → **34**。⚠️ 但 `percentile.py` 加 `lookup_p10` **不新增文件**，故 domain 仍是 15。


**Files:** Create `backend/app/pipeline/prescription_stage.py`、`backend/tests/pipeline/test_prescription_stage.py`；Modify `backend/app/pipeline/daily.py`（阶段序列 + `_replay_cleanup` 的清单）、**`backend/app/pipeline/run_stratify.py`（`PersonInputs` 加 3 个字段、`input_snapshot_of` 加 2 个键、`resolve_muscle_lines` 同时回填 P10；P7-A1/A3）**、**`backend/app/pipeline/percentile_stage.py`（`PersonInputs` 的构造点之一；P7-A1）**、**`backend/app/domain/percentile.py`（新增 `lookup_p10`；P7-A3）**、`backend/tests/pipeline/test_daily.py`（**`PIPELINE_TABLES` 9 → 11** + docstring 的「9 张表」；P7-A5）

**Interfaces:**
- Consumes: Task 4–6 全部；Plan 01 的 `StratificationResult` / `DerivedMetrics` / `Student` / `repo.upsert`
- ⚠️ **import 路径（Ruling 97 / Task 6 的顶回 1）**：两张新表**刻意不进** `app.db.models` 的公有导入面，故本 Task 必须写 `from app.db.models.prescription import Prescription, WeeklyAdjustment`，**不是** `models.Prescription`。写错会让 `test_plan02_tables_stay_out_of_the_models_public_namespace` 与 `test_models_public_namespace_is_unchanged_by_the_split` 两条守卫同时失去意义。
- Produces:
  - `generate_prescriptions(session, semester_id: int, batch_id: int, as_of: dt.date, *, templates, exercises, equivalence) -> PrescriptionReport`
  - `PrescriptionReport`（frozen）：`generated: int` / `skipped: int` / `needs_review: int` / `skipped_reasons: dict[str, int]`（键是 `MatchStatus.value` 或 `"no_trigger"`）
  - `StudentProfile` 的构造：`profile_of(session, student_id, as_of) -> StudentProfile`（**这是 pipeline 层，可以读 DB**）

**决定：**
- **处方阶段跑在分层阶段之后**（`daily.py` 的 `Extract → Clean → Percentile → Derive → Stratify → **Prescribe** → Commit`）。它读**当天刚写好的** `stratification_result` 与 `derived_metrics`，不重算。
- **它在 SAVEPOINT 内**（与分层同一个原子边界）。理由：处方失败不该留下「分层写了、处方没写」的半天状态。⚠️ 但这意味着**一个学生的处方装配失败会让整批回滚**——所以 `apply_safety` / `assemble` 抛的异常必须在 `prescription_stage` 里**按学生捕获**，转成 `needs_review` + 留痕，**只有基础设施异常（DB 写失败）才让它冒泡**。这个分层要写进 docstring 并有测试。
- **`daily_sync_run.prescription_count`**（**Plan 01 就已建好的列**，实测 `daily_sync_run` 共 19 列，`prescription_count` 与 `alert_count` 都在）= `PrescriptionReport.generated`。
- **⚠️ Task 6 新增的三列必须由本 Task 填**（硬规矩 #86 的回扫结果）：
  - `prescription.microcycle_weeks`（**P6-A3**）← `Template.microcycle_weeks`。`valid_to` 的算式与 Task 6 触发 3 的判据都读它，**漏填会让 `valid_to` 无从复算**。
  - `prescription.previous_had_overrides`（**P6-A2**）← 生成时查上一张处方的 `teacher_overrides` 是否非空。**这是「界面提示『该生上次存在人工覆盖』」的唯一载体**，不是 `assembly_snapshot` 里的键。
  - `weekly_adjustment.batch_id`（**P6-A8**）← 本批的 `batch_id`。**教师手工加的调整行没有批次**，决定：取**该行所属处方当前的 `batch_id`**（若处方尚未落库则取本次运行的批次），并在表注释里写明这个口径。
- **⚠️ `skipped_reasons` 必须有 `"insufficient_data"` 这个键**（Task 6 实现者报的最高优先级关切）：`evaluate_triggers` 是纯函数、**没有任何渠道**把「为什么返回空 tuple」传出来，而 Z0 闸门拦下的学生（Plan 01 实测缺省注入下 500 人有 **2** 人）会让教师端的「重新生成」按钮**无声失败**。故 `PrescriptionReport.skipped_reasons` 的键除了 `MatchStatus.value` 与 `"no_trigger"`，**必须再有 `"insufficient_data"`**，并有一条测试钉住这 2 人落进这一格。
- **`prescription.status` 的映射（Ruling 10，计划原文没写）**：`status = "needs_review" if safety.needs_review else "active"`，且 **`needs_review` 优先于 `active`**——一张待人工复核的处方不能被学生端当成生效处方执行（spec §7.4 末段「宁可不自动，也不要自动错」）。**要有测试钉住这个优先级。**
- **幂等**：`prescription` 表的 `UniqueConstraint("student_id", "generated_on")` + `repo.upsert`，与 Plan 01 的三张派生表同构。`_replay_cleanup` 的清单要**加上 `prescription` 与 `weekly_adjustment`**（按 `batch_id` 删；**⚠️ P6-A8：`weekly_adjustment` 的 `batch_id` 列已由 Task 6 加好**，故 `repo.delete_by_batch` 对它直接可用，**不需要**新写级联删逻辑）。**⚠️⚠️ P7-A4 的两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97 / Task 6 的顶回 1），写 `models.Prescription` 会 `AttributeError`，必须 `from app.db.models.prescription import Prescription, WeeklyAdjustment`；② `weekly_adjustment` 有 **FK 到 `prescription`**，而 SQLite 跑在 `PRAGMA foreign_keys=ON` 下——**先删 `prescription` 会当场 FK 违例**。故清单的顺序是 `(DerivedMetrics, StratificationResult, PercentileSnapshot, **WeeklyAdjustment**, **Prescription**)`，**子表先删**，并在代码注释里写明「顺序承重」。要有一条测试钉住它（构造一批带调整行的处方 → 跑 `_replay_cleanup` → 断言两张表都空且没抛 FK 错）——**这一步漏了会让重放翻倍**，Plan 01 的 Ruling 32 就是为此立了一条测试（`test_rerun_same_day_does_not_wipe_percentile_snapshot`），照它的形状补一条。
- **`profile_of` 的输入来源**（**必须写清楚，这是本 Task 最容易错的地方**）：
  - `sex` / `birth` ← `Student`
  - `age` ← `indicators.age_from`？**不**，Task 5 的 `age_from` 在 `prescription/intensity.py`。`profile_of` 调它，`as_of` 传业务日期。
  - `endurance_score` ← `StratificationResult.input_snapshot["curr_scores"]` 里的 `vital_capacity` 与 `distance_run`（**Plan 01 已经把七项得分存进 `input_snapshot` 了**，这是唯一可追溯的来源；不要回去查 `fitness_test_result` 重算，那会产生第二个所有者）
  - `body_fat_pct` / `muscle_mass_kg` ← `input_snapshot` 的**顶层同名键**（控制者亲跑实测已在快照里，无需新增）
  - `bmi`（**原始值**）← **`input_snapshot` 里没有它，只有 BMI 的得分。** 控制者亲跑 `input_snapshot_of` 实测顶层 **26 个键**：`C` / `W` / `age_group` / `annual_change` / `body_comp_reasons` / `body_fat_limit` / `body_fat_pct` / `curr_scores`（含 `bmi` 的**得分**，如 `80`）/ `curr_total` / `dominant_bucket` / `hit_rules` / `label` / `muscle_mass_kg` / `national_total` / `p25_lines` / `percentile_source` / `prev_age_group` / `prev_scores` / `prev_total` / `reason` / `sex` / `snapshot_muscle_p20` / `trend` / `valid_count` / `weakness_items` / `years`。而 spec §7.4 的安全触发要的是 **`BMI > 30` 这个原始值**。

    **决定：给 `input_snapshot` 补两个键 `"bmi"`（原始值）与 `"snapshot_muscle_p10"`**，而不是让 `profile_of` 回去查 `fitness_test_result` 重算。**⚠️ P7-A1：但这两个键今天在 `input_snapshot_of` 里都算不出来**——`PersonInputs` 的 12 个字段里**没有身高体重**，而 `percentile.py` **没有 `lookup_p10`**。故本 Task 的真实改动面是：① `PersonInputs` 加 `height_cm` / `weight_kg` / `snapshot_muscle_p10` 三个字段（**3 个构造点**）；② `percentile.py` 新增 `lookup_p10`（逐字照 `lookup_p20` 的口径）；③ `resolve_muscle_lines` 同时回填 P20 与 P10；④ `input_snapshot_of` 加那两个键。**⚠️ P7-A3 的红线：P10 绝不得进入分层判定**（`flag_body_comp` / `evaluate` 一律不读它），读进去就会改 Plan 01 已结案的标签、13 例黄金用例当场红。理由：spec §4.3 的可追溯性要求「任一条结果都能离线复算」——**BMI 与 P10 是处方的判定输入，不落进快照就等于处方的可追溯性断在这一环**；而重算会产生第二个所有者（同一份身高体重在两处被算成 BMI，任一处改口径就漂移）。原始值由 Task 1 迁到 domain 的 `bmi_of(height_cm, weight_kg)` 算，输入取评估锚点那一批的 `fitness_test_result`。

    ⚠️ 这**修改 Plan 01 已结案的 `run_stratify.input_snapshot_of`**。控制者已核实它**不会**破坏 Plan 01 的幂等测试：`tests/pipeline/test_daily.py:579` 断言的是 `first == second`（两次运行相等），**不是**与一个字面哈希相等，故加键安全。改完必须重跑那条测试确认。

    ⚠️ **P7-A6 更正原文的表述**：原文写「那条测试的实测值会变」，**这会被读成「测试会红」，而它不会**——实测那条断言是 `assert first == second`（**两次运行相等**），不是与一个字面哈希相等；字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 **0 命中**，只出现在账本、spec §1.3 的勘误段与计划正文里。**正确的说法是两句**：① 测试不会红；② **但散文里的值会过期**——账本与 spec §1.3 印着的那个哈希与「行数合计 882」，在 **P7-A5 把 `PIPELINE_TABLES` 从 9 扩到 11** + 本条加两个键之后**都必须重测**，两处都要更新并注明是哪个 commit 改的（硬规矩 #26；Ruling 229 记过一次「一个修复改变了另一个修复的取证基线」）。⚠️ **P7-A7：`assert first == second` 实测有两处**（一处在 canonical sha256 那条测试里、另一处在一个更早的幂等测试里），加键与扩表之后**两处都要重跑**并在报告里分别给结论。
  - `muscle_p10` ← `percentile_snapshot` 的 `p10` 列（**Plan 01 的快照存了 p10/p20/p25/p50/p75 五档，但只有 P20 被消费过**——本 Task 是 P10 的第一个消费者，spec §7.4 的肌肉量触发条件是 **P10** 而非 P20）。按上条决定，它随 `snapshot_muscle_p10` 落进 `input_snapshot`，`profile_of` 从快照读、不查库。

    ⚠️ **肌肉量没有国标常模**：Plan 01 的处置是「样本 < 30 的组整组不产出快照行」（Ruling 121 第 4 步），故 `snapshot_muscle_p10` 会是 `None` → Task 5（5.3）的口径是**不触发 + 留痕**，两者一致。⚠️ **规模差异**：500 人下 Plan 01 实测 0/24 组触发降级，而 **60 人的测试 fixture 会触发**——写测试时别把「60 人下 P10 为 `None`」当成 bug。⚠️ **留痕的载体已经变了**（Ruling 13 + Task 1 评审 M6）：Plan 01 把它写进 `error_summary` 的自由文本，**Task 1 已直接切成 `daily_sync_run.muscle_line_gaps` 计数列**；60 人下成功运行的 `error_summary` **恒为 `NULL`**、`muscle_line_gaps` **恒为 4**（**P7-A8：按可 grep 的原文找、不要按裸行号找**——`git grep -n "muscle_line_gaps == 4" -- backend/` 与 `git grep -n "error_summary is None" -- backend/`，两条**各有两处**；原文写的 `:717-751` 已过期，但结论「60 人下恒为 4 / 恒为 NULL」是对的）。**别去断言一个恒为 NULL 的列。**

- [ ] **Step 0: 接收 Task 6 移过来的两条集成测试（P6-A1）**

放 `backend/tests/pipeline/`：
- `test_regeneration_does_not_inherit_teacher_overrides`（spec §7.5 原文：「下次自动生成时回到算法基线、不继承覆盖，但界面提示『该生上次存在人工覆盖』」）—— 生成 → 加覆盖 → 触发重生成 → 断言新处方的 `training_package` 等于**无覆盖**的基线，且 **`prescription.previous_had_overrides is True`**（**⚠️ P6-A2：不是往 `assembly_snapshot` 加键**，那会让 Task 5 钉死的 12 键 / +3 键两条守卫变红）能让界面提示。
- `test_same_day_regeneration_is_idempotent`（Review Focus 第 2 条）—— 同一天跑两次管道，`prescription` 行数不变、`training_package` 逐字段相同。

- [ ] **Step 1: 写失败测试**

- `test_prescriptions_are_generated_for_every_stratified_student`（500 人零注入下，`insufficient_data` 的 0 人 → 500 张；缺省注入下 2 人 `insufficient_data` → 498 张。**自己跑一遍确认这两个数**，硬规矩 #44）
- `test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped`（Review Focus 第 3 条）
- `test_no_trigger_means_no_new_prescription`（第二天跑，标签没变、没到期 → `generated == 0`）
- `test_a_layer_change_regenerates_and_replaces`（旧处方 `status` 变 `replaced`、`valid_to` 关账；新处方 `active`）
- `test_valid_to_is_generated_on_plus_microcycle_minus_one_day`（字面写死日期）
- `test_needs_review_when_no_equivalent_exercise`（Review Focus 第 5 条的端到端版本）
- `test_per_student_assembly_failure_does_not_roll_back_the_batch`（上面那个异常分层的测试）
- `test_rerun_same_day_does_not_duplicate_prescriptions`（幂等；照 Plan 01 `test_rerun_same_day_does_not_wipe_percentile_snapshot` 的形状）
- `test_replay_cleanup_covers_prescription_and_weekly_adjustment`
- `test_daily_sync_run_prescription_count_matches_the_report`
- `test_no_student_is_skipped_for_a_missing_bucket`（**Ruling 11**）—— 断言 `skipped_reasons` 里**没有** `"no_bucket"` 键。依据：`dominant_bucket is None` 只在 6 个短板判定项**全部** `None` 时发生（Plan01 Ruling 175 补的 `derive.py:330`），而那必然使 `valid_count == 0` → Z0 → `insufficient_data`，故**生产路径上 `NO_BUCKET ⊆ NO_LAYER`**、`498` 那个数成立。**这条测试是那个包含关系的唯一守卫**——没有它，`find_weaknesses` 的口径一变，处方数会静默少一批而没有任何断言提示。
- `test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result`（**这条守的是「不产生第二个所有者」**：变异 `profile_of` 让它去查 `fitness_test_result` 重算 → 这条要红。做法：把 `fitness_test_result` 的某一行改坏，断言 `profile_of` 的结果**不变**）

- [ ] **Step 2–6: 跑失败 → 实现 → 跑通 → 全量 → 变异验收 → Commit**

变异：① 把 `insufficient_data` 的早退删掉 → 3 条测试红；② 把 `_replay_cleanup` 的清单里 `prescription` 删掉 → 重放翻倍测试红；③ 把「按学生捕获异常」改成不捕获 → 整批回滚测试红；④ 把 `valid_to` 的 `-1 day` 删掉 → 有效期测试红。

---
