# Task 8 简报 — 「本周训练单」读模型（`weekly.py`，spec §8.4）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit 见 `git log --oneline -1`，211199 B / 1061 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 8 全节（含预检更正 P8-A1..A8）**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`197147f`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **750 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**（带 `--cov` 时 `749 passed, 1 skipped`）。
**表数 18**（`prescription` **16 列**、`weekly_adjustment` **8 列**）；`app.domain.prescription.__all__` = **47**；`_MODELS_PUBLIC_BASELINE` = **33（刻意不动，Ruling 97）**；扫描面 **34**（pipeline 8 + db 11 + domain 15）→ 本 Task 后 **35**（domain 16）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

**本 Task 是 Plan 02 里最小的一个**：新建 1 个 domain 模块（`weekly.py`）+ 1 个 pipeline 函数（`weekly_factors_of`）。**控制者预期 0–1 轮 fix round。**

## 0.1 你要交付什么

**新建**：
- `backend/app/domain/prescription/weekly.py` —— `current_week` / `weekly_training_sheet` / `WeeklySheet` / `WeeklyFactor`
- `backend/tests/domain/test_prescription_weekly.py`

**修改**：
- `backend/app/pipeline/prescription_stage.py` —— 加 `weekly_factors_of(session, prescription_id) -> list[WeeklyFactor]`
- `backend/tests/pipeline/test_prescription_stage.py` —— 加它的测试（**直接插 `WeeklyAdjustment` 行**喂它）+ `WeeklyAdjustment.SOURCES` 的漂移测试
- `backend/app/domain/prescription/__init__.py` —— 重导出新公开名
- `backend/tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE` **47 → 新值**，并同步那里的 `assert len(...)` 与 `_OWNED_MODULES`（⚠️ Task 5/6 的实现者发现同文件里**有两句 `assert len`**、且 `_OWNED_MODULES` 也要跟着加 `weekly`，**三处都要改**）

## 0.2 ⚠️ 2 条 Critical（逐条照办）

- **P8-A1**：`AssembledBlock` 今天是 **10 个字段**（实测：`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone / structure / weekly_volume / volume_unit / sessions_per_week`）。计划原文只说「缩放只作用于 `weekly_volume`，不改 `hr_zone`」，**对另外 8 个字段一字未提**。口径收紧成：**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。⚠️ **`sessions_per_week` 被缩会让「一周做几次」随减量变化**（语义错误）。测试用 `dataclasses.replace` 做对照、断言「除 `weekly_volume` 外全等」。⚠️ **`WeeklySheet` 刻意不提供跨单位的周总量汇总字段**（`volume_unit` 值域实测 `{min, reps, unspecified}`，相加就是 Task 5 F1-1 那个「混合量纲 float」错误）—— **这条要写进 docstring，否则 Plan 03 的前端会自己把 `min` 和 `reps` 加起来。**
- **P8-A2**：`volume_unit` 的第三档 **`"unspecified"`** 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档 `weekly_volume` 恒为 **`0.0`**；而 `apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里** → `weekly_training_sheet` **一定会吃到它**，而计划对这一档只字未提。**照原样带出、不特殊处理**（`0.0 × factor = 0.0`），但**必须有一条吃真仓的测试**：红层模板 + 体脂异常触发 → 装配出一个含 addon 的包 → 断言那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`。

## 0.3 其余 6 条（简报的预检总表里有完整实测依据）

- **P8-A3**：`WeeklySheet` **加一个 `paused: bool` 字段**（从 `pkg.paused` 直接抄），`paused=True` 时 `sessions` **原样保留**。**不要抛 `ValueError`**（读模型的职责是投影、不是校验）。「暂停」与「本周量为 0」是两件不同的事，`paused` 字段就是为了不让前端把两者静默合并。
- **P8-A4**：`weekly_factors_of` **今天不存在**（`prescription_stage.py` 里 0 命中），`weekly_adjustment` 表**今天 0 行**。**照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**喂它，docstring 按硬规矩 #39 写明「今天没有生产调用方，Plan 03 的 API 层才会调」。⚠️ **排序必须显式**：`created_at` 是 `DateTime NOT NULL 无缺省` → **`ORDER BY created_at, id`**（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等），并**有一条测试钉住这个 tie-breaker**（构造两行 `created_at` 相同、`id` 不同的调整）。
- **P8-A5**：`WeeklyFactor.source` 的值域有**两个住址**（DB 的 `ck_weekly_adjustment_source` ∈ `{auto, teacher}`，与 domain 的裸 `str`）。**domain 侧不另立词表**，但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {"auto", "teacher"}` —— **放 pipeline 层的测试里**（domain 不能 import ORM）。
- **P8-A6**：`factor` 的 `(0, 2]` 与 DB 列没有 CHECK 是**两层守卫、不是重复**。DB 那一层**刻意不加**（`(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界）。**把这个理由写进 `weekly.py` 的 docstring。**
- **P8-A7**：Task 6 的 `triggers.py` 实测用 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，domain 不能 import `datetime`）。`current_week` 用**同一口径**：`week = (as_of - generated_on).days // 7 + 1`。⚠️ **`.days // 7` 对负数向下取整**（`-1 // 7 == -1`）→ **必须先判 `.days < 0` 再算**，配一条 `as_of == generated_on - 1 day → None` 的测试（**不是 0、不是 1**）。⚠️ **另配一条跨模块一致性测试**：「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」在到期日那一格**同真** —— **这是两个模块口径不漂的唯一守卫。**
- **P8-A8**：「缩放不动 `hr_zone`」那条测试**必须用红层模板**（如 `RED-END-ABN-01`）。实测 `hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**（Ruling 133：130 个 block 里 82 个是 `type: none`），**用黄层绿层写是恒真式（假绿）**。

## 0.4 控制者实测的三套真仓装配数据（供你对拍，**期望值仍要自己算**，硬规矩 #44）

`as_of = 2026-10-08`、男 20 岁、`endurance_score = 70`（→ 档 `mid` → `1.0`）、性别男（`1.0`）：

| 模板 | `weeks` | `sessions/周` | `volume_unit` | 第 1 周各 block 的 `weekly_volume` | `delta` |
|---|---|---|---|---|---|
| `RED-END-ABN-01` | 4 | `[4,4,4,4]` | `{min, reps}` | 8 个 block = `[48.0 min, 120.0 reps] × 4` | `[1.0, 1.05, 1.1, 0.85]` |
| `YEL-END-NOR-08` | 4 | `[3,3,3,3]` | `{min}` | 6 个 block 全是 `36.0 min` | 同上 |
| `GRN-END-NOR-14` | 4 | `[2,2,2,2]` | `{min}` | 4 个 block 全是 `24.0 min` | 同上 |

三套的 `paused` 都是 `False`。`weekly_training_sheet(pkg, 1, [])` 应当返回 `factor == 1.0` 且 `sessions` 与骨架逐字段相同。

## 1. 执行强度（账本 Ruling 145）

**目标 0–1 轮 fix round**（Task 6 用了 0 轮、Task 5 与 Task 7 各 1 轮）。
**保留**：TDD；`app/domain/` 分支覆盖 **100%**；变异（**2 条即可**：① 把「缩放也作用于 `hr_zone`」→ 那条测试红；② 把 `factor` 的 `(0, 2]` 上界删掉 → 越界拒绝测试红）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01 与 Task 5/6/7 的全部既有测试仍全绿**。
**取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**

## 2. 变异取证纪律（硬规矩 #83）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`，Task 5 的实现者做过一次等长改动（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**。**假绿更危险。**

## 3. 硬约束

1. **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / **`datetime`**；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy, typing}`。⚠️ **`weekly.py` 要用日期减法** —— 照 `triggers.py` 的做法（`.days`），**不要 import `datetime`**；类型标注照 `intensity.py` / `override.py` 的既有做法（实测 `app/domain/` 下 `from __future__` 与 `TYPE_CHECKING` 各 **0** 命中，用的是**前向引用字符串标注**如 `birth: "dt.date"`）。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`）。
3. **单一所有者**：`source` 的值域所有者是 `WeeklyAdjustment.SOURCES`（DB 侧），domain 只消费 + 漂移测试。
4. **断言两侧不得同源**：期望值字面写在测试里（硬规矩 #35）。
5. **TDD**：先写失败测试、跑红、再实现。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/**` 与 `golden_cases.json` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
7. **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
8. **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
9. **数键/字段/成员一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))`），**绝不用正则数源码**（硬规矩 #89）。**数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（通用换行会把 `\r\n` 翻成 `\n`，硬规矩 #89 的扩写）。

## 4. ⚠️ 若你认为简报/计划某条决定是错的，**顶回来**

Plan 02 到目前为止实现者顶回控制者 **21 次，21 次都是对的**。最近 5 次（账本 Ruling 152）包括：「计划要求换处方时关账 `valid_to` —— 那会让 `valid_to` 不再是该行自身数据的纯函数、违反 spec §4.3」、「**派单声称控制者已经改了计划正文的 4 处，实测 0/4 在树上**」、「派单预设了一条根本不存在的守卫」。
共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 5. 报告

写进 `task-8-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它**。

至少 7 节：① 环境与基线复现；② `weekly.py` 的公开面与四个对象的字段（运行时口径）；③ `weekly_factors_of` 的排序口径与 tie-breaker 测试；④ 变异取证（2 条 + M0 + M1）；⑤ 待清扫清单 / 关切 / 没按派单做的地方（0 处也要写「0 处」）；⑥ 最终验收（passed 数 750 → ?、覆盖率四格、`__all__` 47 → ?、`_PRESCRIPTION_PUBLIC_BASELINE`、扫描面 34 → 35、表数 18、三个指纹、`git diff 197147f HEAD -- backend/data` 为空、`golden_cases.json` 未改）；⑦ commit sha。

## 6. 交回控制者

最终回复里给出（**简洁**）：commit sha 与说明 / passed 数 / 覆盖率四格 / `__all__` 与 `_PRESCRIPTION_PUBLIC_BASELINE` 的新值 / 扫描面 / `WeeklySheet` 与 `WeeklyFactor` 的最终字段清单（运行时口径）/ 2 条变异的结论 / P8-A1..A8 八条逐条的落地位置 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

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

## Task 8: 「本周训练单」读模型（spec §8.4）

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `197147f`，取证脚本 `t8_probes/_t8_probe1.py`）

**测试基线**：`750 passed`；`app/domain/` **951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**；**18 张表**（`prescription` **16 列**、`weekly_adjustment` **8 列**）；`__all__` **47**；扫描面 **34**。

| # | 级别 | 事实（全部实测，运行时口径，硬规矩 #89） | 更正 |
|---|---|---|---|
| **P8-A1** | **Critical** | 计划说「缩放只作用于 `weekly_volume`，不改 `hr_zone`」，但 **`AssembledBlock` 今天是 10 个字段**（`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone / structure / weekly_volume / volume_unit / sessions_per_week`）——其中 `volume_unit` 与 `sessions_per_week` 是 **Task 5 fix round 1 之后才有的**，计划 Task 8 的正文**完全没提它们**。 | 口径收紧成：缩放时**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。⚠️ `sessions_per_week` 是**骨架的结构属性、不是量**，缩它会让「一周做几次」随减量变化，那是语义错误。⚠️ `WeeklySheet` **刻意不提供跨单位的周总量汇总字段**（`volume_unit` 实测值域 = `{min, reps, unspecified}`，把它们相加就是 Task 5 的 F1-1 那个「混合量纲 float」错误）——**这条要写进 docstring，否则 Plan 03 的前端会自己把 `min` 和 `reps` 加起来**。测试：用 `dataclasses.replace` 做对照，断言「除 `weekly_volume` 外全等」 |
| **P8-A2** | **Critical** | `volume_unit` 的第三档 **`"unspecified"`** 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档的 `weekly_volume` 恒为 **`0.0`**。`apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里**，故 `weekly_training_sheet` 一定会吃到它——而**计划对这一档只字未提**。 | **照原样带出、不特殊处理**（`0.0 × factor = 0.0`，无副作用）。**但必须有一条测试吃真仓**：红层模板 + 体脂异常触发 → 装配出一个含 addon 的包 → 断言 `WeeklySheet` 里那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`。**理由与本节最后一条（`auto` 来源）是同一条纪律**：不给它测试，Plan 03 就会撞上一个「结构上支持、逻辑上没测过」的路径 |
| P8-A3 | Important | `TrainingPackage` 实测有 **`paused: bool = False`** 字段（Task 5 的 5.4 由 `OverrideKind.PAUSE` 置位），而 `weekly_training_sheet` 吃到 `paused=True` 的包该返回什么，**计划完全没定**。 | **`WeeklySheet` 加一个 `paused: bool` 字段**（从 `pkg.paused` 直接抄），且 `paused=True` 时 **`sessions` 原样保留**——与 Task 5 的 5.4 决定逐字一致（「暂停是可撤销的，删掉 `weeks` 就不可逆了」）。**否掉「抛 `ValueError`」那个方案**：读模型的职责是**投影**、不是校验；抛异常会让「暂停」这件事在 API 层变成一个错误分支而不是一份可渲染的数据。**⚠️「暂停」与「本周量为 0」是两件不同的事**（前者是可撤销的状态、后者是调整结果），`paused` 字段的存在就是为了不让前端把两者静默合并 |
| P8-A4 | Important | `weekly_factors_of` 实测**今天不存在**（`prescription_stage.py` 里 0 命中，它的公开函数是 `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions` + 5 个私有）。而 `weekly_adjustment` 表**今天 0 行**：`auto` 来源是 Plan 03、`teacher` 来源要等 Plan 03 的 CRUD API。**故本 Task 的这个函数在生产路径上没有调用方、在库里没有数据。** | **照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**来喂它（不靠管道产出），docstring 按硬规矩 #39 写明「今天没有生产调用方，Plan 03 的 API 层才会调」。⚠️ **排序必须显式**：计划说「`reasons` / `sources` 按 `week` 内的创建顺序全部保留」，而 `created_at` 是 `DateTime NOT NULL 无缺省` → 用 **`ORDER BY created_at, id`**（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等——**这正是 Task 5 的 5.4 里「多条覆盖同一目标由列表顺序决定」的同一条理由**）。要有一条测试钉住这个 tie-breaker |
| P8-A5 | Important | `WeeklyFactor.source` 的值域在**两个住址**：DB 侧 `weekly_adjustment.source VARCHAR(8)` + CHECK `ck_weekly_adjustment_source` ∈ `{auto, teacher}`（Task 6 用 `_in_domain` + 类常量 `SOURCES`）；domain 侧计划写的是裸 `str`。 | **domain 侧不另立词表**（`WeeklyFactor.source` 保持 `str`），但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {"auto", "teacher"}`——**放 pipeline 层的测试里**，因为 **domain 不能 import ORM**。与 Task 5 的 P5-A9（`ADDON_TRIGGERS` / `EQUIVALENCE_TRIGGERS` 两套词表）是同一条纪律 |
| P8-A6 | Minor | `factor` 的合法区间 `(0, 2]` 由 `WeeklyFactor.__post_init__` 校验，而 DB 的 `weekly_adjustment.factor` 列**没有对应的 CHECK**。 | **这是两层守卫、不是重复**：domain 的值对象与 DB 的列各有各的失守方式（前者挡「教师端传了 0」，后者挡「有人绕过 domain 直接写库」——而今天 DB 那一层**刻意不加**，因为 `(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界）。**把这个理由写进 `weekly.py` 的 docstring**，否则下一个人会以为其中一个是冗余的 |
| P8-A7 | Minor | Task 6 的 `triggers.py` 实测用的是 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，因为 domain 不能 import `datetime`）。计划的 `current_week` 边界写的是 `+ 27 days → 4`、`+ 28 days → None`。 | **`current_week` 必须用同一个口径**，否则两处会漂：`week = (as_of - generated_on).days // 7 + 1`，`week > microcycle_weeks → None`。⚠️ **`.days // 7` 对负数向下取整**（`-1 // 7 == -1`），故 `as_of < generated_on` 时 `week` 会是 **0 或负**——**必须先判 `.days < 0` 再算**，并配一条测试钉住 `as_of == generated_on - 1 day → None`（**不是 0、不是 1**）。**另配一条跨模块一致性测试**：对同一组 `(generated_on, as_of, microcycle_weeks)`，断言「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」在到期日那一格**同真**。**这条是两个模块口径不漂的唯一守卫** |
| P8-A8 | Minor | 实测三层的 `volume_unit` 分布 = **红 `{min, reps}` / 黄 `{min}` / 绿 `{min}`**；而 `hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**（Task 5 的 Ruling 133：130 个 block 里 82 个是 `intensity: {type: none}`）。 | 计划要求的「缩放不动 `hr_zone`」那条测试**必须用红层模板**（如 `RED-END-ABN-01`）。**用黄层或绿层写会全绿、但什么也没测**——那两层所有 block 的 `hr_zone` 本来就是 `None`，「不动它」是恒真式（假绿） |

**扫描面**：本 Task 新建 `app/domain/prescription/weekly.py` → domain 15 → **16**，扫描面 **34 → 35**。


**Files:** Create `backend/app/domain/prescription/weekly.py`、`backend/tests/domain/test_prescription_weekly.py`

**Interfaces:**
- Produces:
  - `current_week(generated_on: dt.date, as_of: dt.date, microcycle_weeks: int) -> int | None`（1-based；`as_of` 早于 `generated_on` 或超出微周期 → `None`）
  - `weekly_training_sheet(pkg: TrainingPackage, week: int, adjustments: Sequence[WeeklyFactor]) -> WeeklySheet`
  - `WeeklySheet`（frozen）：`week: int` / `factor: float` / `reasons: tuple[str, ...]` / `sources: tuple[str, ...]` / `sessions: tuple[AssembledSession, ...]`（**已按 `factor` 缩放**） / **`paused: bool`（P8-A3 新增，从 `pkg.paused` 直接抄）**
    ⚠️ **P8-A1：「已按 `factor` 缩放」的精确口径** —— `AssembledBlock` 今天是 **10 个字段**，缩放时**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。**`sessions_per_week` 是骨架的结构属性、不是量**，缩它会让「一周做几次」随减量变化。**`WeeklySheet` 刻意不提供跨单位的周总量汇总字段**（`volume_unit` 实测值域 `{min, reps, unspecified}`，相加就是 Task 5 的 F1-1 那个「混合量纲 float」错误）——写进 docstring，否则 Plan 03 的前端会自己加。
  - `WeeklyFactor`（frozen）：`week: int` / `factor: float` / `reason: str` / `source: str`（`"auto"` | `"teacher"`）
  - `app.pipeline.prescription_stage.weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`（ORM 行 → 纯值对象的转换，放 pipeline 层）
  - ⚠️ **ORM 行的 import 路径同 Task 7**：`from app.db.models.prescription import WeeklyAdjustment`（Ruling 97：它**不在** `app.db.models` 的公有导入面上）

⚠️ **命名决定（避免与 ORM 撞名）**：domain 侧的值对象叫 **`WeeklyFactor`**，Task 6 建的 ORM 表类叫 **`WeeklyAdjustment`**（表名 `weekly_adjustment`，spec §4.4 的字面）。两者是同一份数据的两种形态，但**不得同名**——否则 docstring 里写「`WeeklyAdjustment` 的 `source`」时说不清指 ORM 行还是值对象。**domain 不认识 ORM**，转换只发生在 pipeline 层。

**spec §8.4 原文**：「学生端『本周训练单』 = 骨架第 N 周 × 本周调整系数」；「预警触发的『减量 20%』落成一条 `weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，可追溯、可回滚」。

**决定：**
- **同一周有多条调整时，系数相乘还是取最后一条？决定：相乘**，且 `reasons` / `sources` 按 `week` 内的创建顺序全部保留。理由：spec 说「可追溯、可回滚」——取最后一条会让前一条**消失**，而相乘能让每一条都留在乘积里且各自可撤销。⚠️ 这是工程决定，登记 spec §14。
- **`factor` 的合法区间**：`(0, 2]`。`0` 或负数意味着「本周不训练」，那应该走 Task 5（5.4）的 `PAUSE` 覆盖而不是调整系数——**两个机制不得混用**，`__post_init__` 校验并抛 `ValueError`。上界 `2.0` 是防手误（`factor=20` 会把训练量放大 20 倍）。
- **缩放只作用于 `weekly_volume`，不改 `hr_zone`**。理由：心率区间是**强度**、不是**量**；把两者一起缩会让「减量」变成「降强度」，而 spec §8.4 明写「微调改的是**本周训练量**」。**这条要写成测试**，因为它是本 Task 最容易被实现错的地方。**⚠️ P8-A8：这条测试必须用红层模板**（如 `RED-END-ABN-01`）——实测 `hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**，黄层绿层全是 `None`，用它们写「不动 `hr_zone`」是**恒真式（假绿）**。**⚠️ P8-A1：测试要用 `dataclasses.replace` 做对照，断言「除 `weekly_volume` 外 9 个字段全等」**，而不只是断言 `hr_zone` 没变。
- **`current_week` 的边界**：`as_of == generated_on` → `1`；`as_of == generated_on + 27 days` → `4`；`+ 28 days` → `None`（已到期，该换处方了，与 Task 6 的触发 3 同一口径 `>=`）。**三个边界都要字面写死日期测试。**
  **⚠️ P8-A7 的实现口径**：Task 6 的 `triggers.py` 实测用的是 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，因为 domain 不能 import `datetime`）。**`current_week` 必须用同一个口径**：`week = (as_of - generated_on).days // 7 + 1`，`week > microcycle_weeks → None`。**⚠️ `.days // 7` 对负数向下取整**（`-1 // 7 == -1`），故 `as_of < generated_on` 时 `week` 会是 **0 或负** —— **必须先判 `.days < 0` 再算**，并配一条测试钉住 `as_of == generated_on - 1 day → None`（**不是 0、不是 1**）。
  **⚠️ 另配一条跨模块一致性测试**：对同一组 `(generated_on, as_of, microcycle_weeks)`，断言「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」在**到期日那一格同真**。**这条是两个模块口径不漂的唯一守卫** —— 没有它，任一处把 `7` 改成别的数、或把 `>=` 改成 `>`，学生端就会看到一张已经过期却仍在渲染的训练单。
- **`auto` 来源本计划不产出**（Plan 03 的预警落地）——但 `WeeklyFactor.source` 的取值域要包含它，且 `weekly.py` 要能正确处理（否则 Plan 03 会撞上一个「结构上支持、逻辑上没测过」的路径）。**用直接构造的 `WeeklyFactor(source="auto")` 测它。**
- **⚠️ P8-A5：`source` 的值域有两个住址**（DB 侧 `ck_weekly_adjustment_source` ∈ `{auto, teacher}`，由 Task 6 的 `_in_domain` + 类常量 `SOURCES` 生成；domain 侧是裸 `str`）。**domain 侧不另立词表**，但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {"auto", "teacher"}` —— **放 pipeline 层的测试里**，因为 **domain 不能 import ORM**。
- **⚠️ P8-A2：`volume_unit == "unspecified"` 那一档要有测试。** 它是 Task 5 的 P5-A3 为 **addon block** 加的，那一档的 `weekly_volume` 恒为 `0.0`，而 `apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里** → `weekly_training_sheet` 一定会吃到它。**照原样带出、不特殊处理**（`0.0 × factor = 0.0`），但要吃真仓测一次：红层模板 + 体脂异常触发 → 断言那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`。**与上一条（`auto` 来源）是同一条纪律。**
- **⚠️ P8-A3：`paused` 的语义。** `WeeklySheet` 带一个 `paused: bool`（从 `pkg.paused` 直接抄），`paused=True` 时 **`sessions` 原样保留**——与 Task 5 的 5.4 决定逐字一致（「暂停是可撤销的，删掉 `weeks` 就不可逆了」）。**否掉「抛 `ValueError`」那个方案**：读模型的职责是**投影**、不是校验。**⚠️「暂停」与「本周量为 0」是两件不同的事**（前者是可撤销的状态、后者是调整结果），`paused` 字段的存在就是为了不让前端把两者静默合并。配一条测试：`paused=True` 的包 → `sheet.paused is True` 且 `sessions` 与骨架逐字段相同。
- **⚠️ P8-A6：`factor` 的 `(0, 2]` 与 DB 列没有 CHECK 是两层守卫、不是重复。** domain 的值对象挡「教师端传了 0」，DB 的列**刻意不加** CHECK——因为 `(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界。**把这个理由写进 `weekly.py` 的 docstring**，否则下一个人会以为其中一个是冗余的。
- **⚠️ P8-A4：`weekly_factors_of` 今天在生产路径上没有调用方、`weekly_adjustment` 表 0 行**（`auto` 来源是 Plan 03、`teacher` 来源要等 Plan 03 的 CRUD API）。**照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**喂它，docstring 按硬规矩 #39 写明「今天没有生产调用方」。**⚠️ 排序必须显式**：`created_at` 是 `DateTime NOT NULL 无缺省`，故用 **`ORDER BY created_at, id`**（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等——**这正是 Task 5 的 5.4 里「多条覆盖同一目标由列表顺序决定」的同一条理由**）。要有一条测试钉住这个 tie-breaker。

- [ ] **Step 1–5: 写失败测试 → 实现 → 跑通 → 变异 → Commit**

测试至少：`current_week` 的 **6** 个边界（**P8-A7 加了 `as_of == generated_on - 1 day → None` 那一格**）、**`current_week` ↔ `MICROCYCLE_EXPIRED` 的跨模块一致性**（P8-A7）、多调整相乘、`factor` 越界拒绝（`0` / `-0.1` / `2.0` / `2.1` 四格）、缩放不动 `hr_zone` **且其余 9 个字段全等**（P8-A1/A8，**用红层模板**）、`reasons`/`sources` 顺序保留、`auto` 与 `teacher` 混合、**`volume_unit == "unspecified"` 的 addon block**（P8-A2）、**`paused=True`**（P8-A3）、空调整列表 → `factor == 1.0` 且 `sessions` 与骨架逐字段相同。
放 pipeline 层的：`weekly_factors_of` 的**直接插行**测试（P8-A4，含 `created_at` 相同、`id` 不同的 tie-breaker 那一格）、`WeeklyAdjustment.SOURCES` 的漂移测试（P8-A5）。

---
