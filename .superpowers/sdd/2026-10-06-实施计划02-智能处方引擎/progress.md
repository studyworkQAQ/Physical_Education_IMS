# SDD ledger — plan: Document/2026-10-06-实施计划02-智能处方引擎.md

分支 `feature/plan-02-prescription-engine`，基线 `e26347f`（计划文档 commit，其父是 Plan 01 的 `1355541`）。
上游：Plan 01 已结案并合入 `main`（`1355541`），`453 passed / 0 failed`、`app/domain/` 分支覆盖 100%。
Plan 01 的账本在 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩）——**那份账本的硬规矩全部适用于本计划**，本账本的编号从 Ruling 1 重新开始，引用 Plan 01 的裁定一律写全「Plan01 Ruling N」。

## 预检扫描（Pre-flight，commit `1355541` 上亲测）

### A. 计划文本里需要更正的事实（行号绑定 commit，硬规矩 #37）

| 计划写的 | 实测（`git grep -n`，基线 `1355541`） | 处置 |
|---|---|---|
| `daily.py:621` 的 `from app.seed.generate import …` | **`daily.py:689`** | 行号过期（Plan 01 的 Task 11 给 `daily.py` 加了 `main()`）。派单里写 `git grep -n "from app.seed" -- backend/app/pipeline` 让实现者自己取 |
| `run_stratify.py:48-49` | **一致** ✓ | — |
| `backfill.py:234` | **一致** ✓ | — |
| `session.py:53` 的 `def engine(url: str = "sqlite:///pe.db")` | **一致** ✓ | — |
| 「`MockLePaoAdapter(DEFAULT_CSV_DIR)` 硬编码两处」 | **`backfill.py:268`、`daily.py:712`** ✓ 两处 | — |
| Task 1 的 allow-list 写 `collections.abc` | AST 的**顶层名**是 `collections`（`from collections.abc import X` 的 `node.module.split('.')[0]` == `collections`） | **Ruling 3**：allow-list 按**完整 module 串**匹配，不按顶层名 |
| Task 1 Step 2 的 Expected 写「allow-list 守卫报 `numpy` 之外的漏网」 | domain 今天只 import `dataclasses` / `enum` / `collections.abc` / `numpy` / `app.domain.*`（AST 亲扫 6 个文件全部 import 逐条列出） | **Ruling 4**：allow-list 守卫**一上来就是绿的**，它是回归守卫不是修复；Step 2 的 Expected 要拆成「依赖方向守卫 FAIL（4 处 offender）+ allow-list 守卫 PASS（回归守卫）」 |

**domain 的 import 全貌（AST 亲扫，这是 allow-list 的实测依据）**：
```
derive.py       dataclasses, enum, app.domain.indicators, app.domain.percentile
indicators.py   enum, app.domain.tables
percentile.py   collections.abc, dataclasses, enum, numpy, app.domain.indicators, app.domain.tables
stratify.py     collections.abc, dataclasses, enum, app.domain.derive, app.domain.indicators
tables.py       collections.abc, dataclasses
__init__.py     （无 import）
```
**domain 不 import `app.refdata`**（Plan01 Ruling 15 已把参考表改成参数注入）。故 allow-list 可以是**紧的**：`{dataclasses, enum, collections, numpy, typing}` + `app.domain` / `app.domain.*`。
⚠️ 终审 A 曾说「domain 经两跳依赖 `app.refdata`」——**AST 实测不成立**，那是 `percentile.py:16-18` 的 docstring 自陈（说的是「参考表由 refdata 加载后注入」这件事），不是 import。allow-list 落地后 `import app.refdata` 会被抓，这是**新增的拦截力**，不是既有缺陷。

### B. 共享文件 / 接口的任务对

| 任务对 | 共享物 | 发现 | 裁定 |
|---|---|---|---|
| T1 ↔ T2/T3/T9 | `app/db/models/prescription.py` | T1 的 Files 列了要创建它，但 T1 **没有任何表要放进去**（4 张新表分属 T2/T3/T9） | **Ruling 5**：T1 创建全部六个模块，Plan 01 的 14 张表按 spec §4 小节分配；`prescription.py` 与 `feedback.py` **只放模块 docstring**（写明「Plan 02 的 Task 2/3/9 填」「Plan 03 填」），不放空类。`models/__init__.py` 用 `from .organisation import *` 之类重导出，**并加一条测试断言 `models.__all__`（或 `dir(models)` 里的类名集合）与拆包前逐字相同**——这是「导入面不变」的唯一可执行判据 |
| T2 ↔ T3 | `exercise_ref` 词表 | T2 Step 1 说「先写出 T3 的 18 套模板的 `exercise_ref` 集合」——**这是让 T2 做 T3 的活**，循环 | **Ruling 6**：T2 从 **spec §7.2:487 点名的动作** + 18 格矩阵的结构推出动作库（间歇跑/复合循环/持续跑/台阶训练/自重抗阻/弹力带抗阻/兴趣球类/定向越野/功能性训练/HIIT/两个 addon 模块 + 速度柔韧类 4 个），**不读 T3 的 YAML**。T3 写 YAML 时只能引用 T2 已建的 ref；**若 T3 需要一个 T2 没建的 ref，T3 可以往 `exercises.yaml` 追加**（同时更新 T2 的指纹测试常量），并在报告里列出追加了哪些、为什么。这比「T2 猜 T3 要什么」诚实 |
| T2 ↔ T7 | `exercise_equivalence.yaml` 的 `volume_reduction` | T7 的决定要往这个文件加顶层 `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}`，而 T2 的指纹测试钉住了该文件 → **T7 会让 T2 的测试变红** | **Ruling 7**：`volume_reduction` **在 T2 就写进 YAML**，T2 补一条测试钉住两个系数（字面值）。T7 只**消费**、不改文件。理由：一个计划中途改自己被指纹钉住的文件，等于让指纹测试失去意义（每次改动都要同步改常量，指纹就变成了变更记录而不是闸门） |
| T6 ↔ T8 | `TrainingPackage.paused` | 计划已修正：字段在 T6 定义、T8 只置位 | ✓ 无需裁定（写计划时自查已修） |
| T9 ↔ T11 | `weekly_adjustment` 表 vs `WeeklyFactor` 值对象 | 计划已修正：ORM 叫 `WeeklyAdjustment`、domain 叫 `WeeklyFactor`，转换函数在 pipeline | ✓ 但**转换函数住在 `prescription_stage.py`，那是 T10 创建的文件** → T11 修改 T10 的产出。串行无冲突，派单里要告诉 T11 这一点 |
| T10 ↔ T1 | `daily.py` | T1 改 `_fitness_batch` 的 upsert（摘掉 `test_date`），T10 在 `daily.py` 插入处方阶段 | 串行，无冲突。但 **T10 的派单必须带上 T1 对 `daily.py` 的改动摘要**，否则 T10 可能把 `test_date` 加回去 |
| T12 ↔ T4/T6/T7 | 黄金用例的 `template_id` / `hr_zone` / `weekly_volume` / `needs_review` | 一致 | ✓ |

### C. 各任务自身文本自洽性

| 任务 | 发现 | 裁定 |
|---|---|---|
| T3 Step 1 | 测试名 `test_exactly_eighteen_templates covering_the_full_matrix` **含空格**，不是合法 Python 标识符 | **Ruling 8**：改为 `test_exactly_eighteen_templates_cover_the_full_matrix`。这是计划里唯一的语法级错误 |
| T6 Step 3 | 三档写「`< 60` → 0.8、`60–79` → 1.0、`>= 80` → 1.2」，而 `endurance_score` 是**两项得分的算术均值（float）**，`79.5` **落在缝里** | **Ruling 9**：档位改为 `< 60` / `[60, 80)` / `>= 80`（半开区间，无缝无叠）。Step 1 的参数化边界值相应改成 `59.9 / 60.0 / 79.9 / 80.0`，**并加一个 `79.5`** 钉住半开上界 |
| T9 ↔ T7 | T7 产出 `SafetyOutcome.needs_review: bool`，T9 的 `prescription.status` 取值域含 `needs_review`，但**没有任何一处写明两者怎么对应** | **Ruling 10**：T10 落库时 `status = "needs_review" if safety.needs_review else "active"`。且 **`needs_review` 优先于 `active`**——一张待人工复核的处方不能被学生端当成生效处方执行。T10 要有测试钉住它 |
| T10 Step 1 | 「缺省注入下 2 人 `insufficient_data` → 498 张」隐含假设 `NO_BUCKET` 不会额外减少张数 | **Ruling 11**：`dominant_bucket is None` 只在 6 个短板判定项**全部** `None` 时发生（Plan01 Ruling 175 补的 `derive.py:330` 那条），而那必然使 `valid_count == 0` → Z0 → `insufficient_data`。故**生产路径上 `NO_BUCKET ⊆ NO_LAYER`**，498 这个数成立。**但要加一条测试断言 `skipped_reasons` 里没有 `"no_bucket"` 键**——这条测试就是上述包含关系的守卫，若哪天 `find_weaknesses` 的口径变了它会红 |
| T12 Step 3 | 标题写「本计划累计 **6** 项」，正文列了 §14 **#28–#34 共 7 项** | **Ruling 12**：是 **7 项**，§14 从 27 → **34**（与「计划完成后的状态」那段一致，那里写对了） |
| T1 Step 4 第 4 项 | 「保留 `error_summary` 的既有写法一个 Task 周期，两处同时写……或者你判断直接切更干净」——**留了个开放选择** | **Ruling 13**：**直接切**，不双写。理由：`error_summary` 的「注意（非错误）：…」文本**零消费者**（Plan 01 的终审 B 亲验过 `git grep`，只有写入处），双写会留下两个所有者、正是本计划 Global Constraints 第一条要消灭的东西。切完在 `daily_sync_run.error_summary` 的列注释里写明「自 Plan 02 起只承载真错误；缺线组数改由 `muscle_line_gaps` 计数列承载」 |
| T5 | `hrmax(age, formula=..., measured=None)` 的 `measured` 参数**无生产调用方** | **Ruling 14**：接受，但按硬规矩 #39 必须在 docstring 里标注「Plan 01/02 无实测心率来源，此参数为 Plan 03 的穿戴设备留口，**当前只有测试调用**」。**YAGNI 的反面考量**：spec §7.3 步骤 1 明写「优先用实测值」，不留这个口子就是对 spec 的静默偏离；留了但标注清楚，比删掉更诚实 |

### D. Global Constraints 与任务的冲突

| 冲突 | 裁定 |
|---|---|
| Global Constraints 说「`app/seed/` 重新冻结（Task 1 的依赖迁移会动它一次）」，而 T2 Step 5 要**新建** `app/seed/prescription.py`、T3 Step 6 也要它 | **Ruling 15**：冻结的含义是「**不改既有文件的逻辑**」，不是「不新增文件」。T1 对 `app/seed/{generate,fitness}.py` 的改动限于**删掉被迁走的常量 + 改 import**（`ast.dump` 剥 docstring 后应当**不等价**，因为删了定义——所以 T1 不能用 AST 等价当闸门，要用「`git diff` 里 `app/seed/` 的改动行只有 import 与被删的常量定义」当闸门）。T2/T3 新增 `app/seed/prescription.py` 是**新文件**，不触碰冻结。**把这条写进 T1/T2/T3 的派单** |
| Plan01 硬规矩 #42 说「墙钟数字只能作为带 n 与区间的实测记录，不得作为断言，除非它守的是一个数量级」，而 T12 Step 2 要断言 `p95 < 3.0` | **不冲突**：spec §1.3 的 `< 3 秒` 就是「数量级」型要求（3 s 对一个纯计算装配是 100× 量级的余量）。T12 Step 2 已要求先量 p95、若余量 < 2× 就改写成「记录 + 更松的数量级断言」。**派单里要把这个判断阈值再强调一次** |

---

## Rulings（预检裁决，执行前生效）

**Ruling 1 — Task 1 的 `models.py` 拆包，导入面不变的可执行判据是「类名集合逐字相同」。**
计划只说「保持 `from app.db import models` 与 `models.X` 的既有写法不变」，那是散文、不可执行。裁定：拆包前先 `sorted(n for n in dir(models) if not n.startswith('_'))` 取一份基线，拆包后断言**逐字相同**（含 `Base`、`JsonText`、`_in_domain` 若被导出）。**若判断错**：拆包漏导出一个类，某个 `models.X` 在运行时才 `AttributeError`——而这正是「导入面不变」这条要求要防的事。

**Ruling 2 — Task 1 的 `app/seed/` 闸门不是 AST 等价。**
删掉 `COLUMN_BY_ITEM` / `RANGES_FILENAME` 的定义会改变 AST，故 Plan 01 那套「剥 docstring 比 `ast.dump`」在这里**必然 False**、不能当闸门。裁定：T1 对 `app/seed/` 的闸门是「`git diff -- backend/app/seed/` 的改动行**只有** import 语句与被删的常量定义，无任何逻辑行」，实现者要逐行贴出这个 diff 并分类。**若判断错**：迁移过程中顺手改了生成器逻辑，而 500 人的分布断言可能恰好不敏感（Plan 01 的 Ruling 216-M2 证明过四个趋势阈值改坏了 428 条全绿）。

**Ruling 3 — allow-list 按完整 module 串匹配，不按顶层名。**
计划写的 `collections.abc` 作为**顶层名**永不匹配（AST 的顶层名是 `collections`）。裁定：允许集合 = `{"dataclasses", "enum", "collections", "collections.abc", "numpy", "typing"}` 逐串比对 `node.module`，加上 `node.module == "app.domain" or node.module.startswith("app.domain.")`。`collections` 与 `collections.abc` **都列**：前者覆盖 `import collections`，后者覆盖 `from collections.abc import …` 的完整串。**若判断错**：只列顶层名会让 `from collections import OrderedDict` 与 `from collections.abc import Iterable` 无法区分，allow-list 就退化成一个过宽的白名单。

**Ruling 4 — Task 1 Step 2 的 Expected 拆成两半。**
依赖方向守卫 **FAIL**（4 处 offender：`run_stratify.py:48`、`:49`、`daily.py:689`、`backfill.py:234`）；allow-list 守卫 **PASS**（domain 今天的 import 全在白名单内，AST 亲扫为证）。计划原文写「allow-list 守卫报 `numpy` 之外的漏网」是**猜的**，实测没有漏网。**它是回归守卫、不是修复**——这件事要在测试的 docstring 里写明，否则下一个人会以为它一直是绿的所以没用（Plan01 Ruling 157 的教训：一条守卫的价值不在于它今天红不红）。

**Ruling 5 — `models/prescription.py` 与 `models/feedback.py` 在 Task 1 只放模块 docstring。**
见预检表 B。docstring 要写明「本模块由 Plan 02 的 Task 2/3/9（prescription）与 Plan 03（feedback）填充」，避免下一个人以为它是遗漏。

**Ruling 6 — 动作库由 spec §7.2:487 点名的动作 + 18 格矩阵推出，不由 T3 的 YAML 反推。**
见预检表 B。T3 可追加 ref，但必须同步更新 T2 的指纹常量并在报告里列出。

**Ruling 7 — `volume_reduction` 在 Task 2 就写进 `exercise_equivalence.yaml`。**
见预检表 B。T2 补一条测试字面钉住 `{bmi_over_30: 0.8, muscle_low_p10: 0.9}`；T7 只消费。**若判断错**：这两个系数是工程约定（spec 没给），提前写进 T2 意味着 T7 若发现要改就得动 T2 的文件与指纹——但改指纹本来就是「知识资产变更需被显式承认」的应有代价，不构成反对理由。

**Ruling 8 — 测试名 `test_exactly_eighteen_templates covering_the_full_matrix` → `test_exactly_eighteen_templates_cover_the_full_matrix`。**

**Ruling 9 — 个体修正系数的三档是 `< 60` / `[60, 80)` / `>= 80`，半开、无缝无叠。**
计划原文的「`60–79`」与「`>= 80`」之间漏了 `(79, 80)`，而 `endurance_score` 是 float 均值，`79.5` 完全可能。**若判断错**：落在缝里的学生要么 `KeyError` 要么被静默归到某一档，而 500 人里可能只有个位数、分布断言完全测不出来。参数化边界值改为 `59.9 / 60.0 / 79.5 / 79.9 / 80.0`。

**Ruling 10 — `prescription.status = "needs_review" if safety.needs_review else "active"`，且 `needs_review` 优先。**
见预检表 C。理由：spec §7.4 末段的原则是「宁可不自动，也不要自动错」，一张待复核的处方若被标成 `active`，学生端会直接照它训练。

**Ruling 11 — 生产路径上 `NO_BUCKET ⊆ NO_LAYER`，故 498 这个数成立；但必须加一条测试断言 `skipped_reasons` 无 `"no_bucket"` 键。**
见预检表 C。这条测试是那个包含关系的**唯一守卫**——没有它，`find_weaknesses` 的口径一变，处方数会静默少一批而没有任何断言提示。

**Ruling 12 — spec §14 补 7 项（#28–#34），不是 6 项。**

**Ruling 13 — `muscle_line_gaps` 直接切，不与 `error_summary` 双写。**
见预检表 C。`error_summary` 的那段文本零消费者（Plan 01 终审 B 亲验），双写等于造第二个所有者。

**Ruling 14 — `hrmax` 的 `measured` 参数保留但标注「当前只有测试调用」。**
见预检表 C。这是对 spec §7.3 步骤 1「优先用实测值」的诚实处置：不留口子是静默偏离 spec，留了不标注是留一个没人知道是死代码的参数。

**Ruling 15 — 「`app/seed/` 冻结」的含义是不改既有文件的逻辑，不是不新增文件。**
见预检表 D。T2/T3 新建 `app/seed/prescription.py` 合法；T1 改 `app/seed/{generate,fitness}.py` 限于 import 与被删常量。

---

## 任务进度

### Task 1: 架构债清偿

实现者报告 **DONE_WITH_CONCERNS**，commit `1df5e8a`（一个 commit 在 `e26347f` 之上，未 push、未合并）。14 条关切，其中 **3 条证明计划文本有事实错误**。

**控制者独立复验（全部自己跑，不采信报告）**：
```
git log --oneline -2                       1df5e8a / e26347f
git status --short                         （空）
pytest -q                                  478 passed / 0 failed   (54.11 s)
pytest -q --cov=app.domain --cov-branch    TOTAL 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%
                                           477 passed, 1 skipped   (113.46 s)
```
基线 453 → **478**（+25），`app/domain/` 从 392 stmts / 112 branch 增到 **399 / 114**（`COLUMN_BY_ITEM`、`bmi_of`、`CLEANING_FIELDS` 迁入 domain），**覆盖率仍 100%**——即迁进来的行是带着测试进来的。

**Ruling 16（实现者最高优先级关切，接受；控制者第 61 次错误）— 计划 Step 4 第 1 项要的两条具名 `Index(student_id, computed_on)` 是冗余的，不建。**

控制者亲验 `backend/app/db/models/derived.py`：
```
UC: "student_id", "computed_on", name="uq_derived_metrics_student_day"
UC: "student_id", "computed_on", name="uq_stratification_result_student_day"
Index( count: 0
```
**Plan01 Ruling 212 的 `UniqueConstraint` 已经在**，SQLite 会为它建 `sqlite_autoindex_*`、**前导列序与计划要的具名索引完全相同**，规划器本来就在用。实现者的 A/B 实测（56000 行、n=300）：加具名索引后中位墙钟 **0.2708 → 0.2941 ms（无加速，两组区间完全重叠）**、`.db` **+25.23%**（计划写的代价是「+2.7%」）。

**控制者的错误链**：终审 B 的 M2 实测「单人查询 57.9 ms → 0.2 ms、258×、+2.7% 体积」——那是在**加唯一约束之前**的 schema 上量的。而同一份终审报告的 C1 又建议加 `UniqueConstraint("student_id","computed_on")`，**C1 的修复把 M2 的收益全吃了**。控制者把两条都抄进计划，**没有检查它们互相抵消**。这与 Ruling 172（#44，把一个情境的测量搬到另一个情境）同型，只是这次搬的是**同一份报告里的两个不同 schema 状态**。

实现者的替代处置**强于计划要求**：不建冗余索引，改成一条守 `EXPLAIN QUERY PLAN` 的测试——它同时挡住「删了约束没补索引」与「索引列序不对」两件事，而具名索引本身什么都不挡。**接受。**

**裁定**：计划 Step 4 第 1 项作废，改写为「`UniqueConstraint` 已由 Plan01 Ruling 212 提供同列序的 `sqlite_autoindex`，**不再加具名索引**；守卫改为断言 `EXPLAIN QUERY PLAN` 走索引」。并把终审 B 的 258×/+2.7% 那组数字**连同它的 schema 前提**一起记进账本，避免下一个人再抄一次。

**Ruling 17（实现者关切，接受；控制者第 62 次错误）— `prescription_count` / `alert_count` 在 Plan 01 就已建好，计划说「Plan 01 没建」是错的。**

控制者亲跑 `git grep -n "prescription_count\|alert_count" e26347f -- backend/app/db/`：
```
e26347f:backend/app/db/models.py:614:    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
e26347f:backend/app/db/models.py:615:    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数
```
**两列在基线上就存在。** 控制者写计划时依据的是 Plan 01 某轮亲读的 `DailySyncRun` 列清单（那次读到 `insufficient_count` 就截断了，`grep -A 22` 的窗口不够长），**没有重新数一遍**——正是硬规矩 #27 要防的「用截断的输出代表全集」。

**裁定**：计划 Step 4 第 3 项作废（两列已在）；Task 10 的简报要写明「`prescription_count` 列已存在、只需写入」，`alert_count` 仍是 Plan 03 的（本计划不写值）。

**Ruling 18（实现者关切，接受；控制者第 63 次错误）— `CLEANING_FIELDS` 的公式漏了 5 个测量列。**

计划给的公式是「`COLUMN_BY_ITEM` 的值 ∪ `{"student_no"}` ∪ `WHOLE_RECORD`」。`COLUMN_BY_ITEM` 是 **7 个计分项 → 列名**，而清洗层实际会写进 `cleaning_log.field` 的是 **8 个原始测量列**（身高、体重 + 6 个测试项；BMI 是派生的、不是测量列，所以 `COLUMN_BY_ITEM` 的 7 个值里 `bmi` 不对应任何原始列，而 `height_cm`/`weight_kg` 两个都对不上它）。实现者按**生产侧全部 9 处 `field=` 写入点全量枚举**得出 **13 个值**。

落地在 `app/domain/indicators.py:154`，且 `:117-119` 的注释交代了「为什么 `WHOLE_RECORD` 也迁进 domain」（它是那一列取值域的成员；若 `CLEANING_FIELDS` 定义时不引用它、而是自己再写一个字面量 `"*"`，就又是第二个所有者）。`app/pipeline/clean.py:42` 重导出它。

**裁定**：接受实现者的 13 值口径。计划的公式作废。**这是「列清单必须来自显式定义的全量读取、不得由推断」（硬规矩 #27）的第四次落空**——前三次是控制者用样本行类型推、用过滤后的 grep 推、用截断的 `grep -A` 推，这次是用**语义推理**推（「7 个计分项对应 7 个列」）。**把 #27 扩写**：全量读取的含义包括「按**生产写入点**枚举」，不是「按概念推导」。

**Ruling 19（实现者关切 C1，接受；控制者第 64 次错误 —— 派单前没验工作树）— 开工时工作树是脏的，脏的是计划文档本身，方向是丢信息。**

实现者报告：开工前 `Document/2026-10-06-实施计划02-智能处方引擎.md` 有 **14+/23− 的未提交改动**，方向是**丢掉信息**，而 `task-1-brief.md` 是从这份陈旧副本抽的。它的处置：**先无损保全**（副本 + patch 落进 gitignore 的 sdd 目录）**再还原到 HEAD**，三重取证（`git status` 空 / 行尾归一后与 HEAD 逐字节相同、sha256[:16] 两侧都是 `43dd8e91269b199c` / `git apply --check` exit 0），撤销命令写进报告。

**控制者复核根因**：控制者在写完计划后调用了 `NotifyUser` 请用户审阅，IDE 里那份文件是**编辑工具四次静默失败之前的陈旧缓冲区**（控制者当时已用 python 复核确认磁盘是新的、并据此提交）。用户批准时 IDE 把陈旧缓冲区回写到了磁盘。**所以脏改动的内容正是控制者那四处修正的逆向。**

**控制者已复核还原是完整的**：亲跑确认计划文档现在含全部 6 处修正标记（`bmi_of(height_cm` ×2、`snapshot_muscle_p10` ×3、`WeeklyFactor` ×6、`endurance_score: float | None` ×1、`paused: bool = False` ×2、`命名决定（避免与 ORM 撞名）` ×1），83545 字节，与提交时一致。**没有信息丢失。**

**补硬规矩 #48：派单前必须 ① 验 `git status --short` 为空；② 验简报是从已提交状态抽的**——做法是把简报里的几个关键串与 `git show HEAD:<path>` 的输出比对，或直接 `git stash list` + `git diff` 双查。**若工作树脏，先查明是谁改的、保全、再还原，然后才抽简报。** 本条是「工具/磁盘分歧」家族的第 19–44 次（实现者另报告：**编辑工具对报告文件连续 26 次报成功而磁盘未写**，它靠「列全部 `##` 标题」这个显式全量读取才发现，最后改用 python 逐处 `assert` 出现次数恰为 1 才写盘）。

**Ruling 20（实现者的 5 条判断，逐条追认）**
- **`WHOLE_RECORD` 迁进 domain**：追认。理由见 Ruling 18（它是 `cleaning_log.field` 取值域的成员，留在 `clean.py` 会让 `CLEANING_FIELDS` 要么反向依赖 pipeline、要么重抄一个字面量）。实现者报告已确认**无导入环**。
- **新增 `models/_shared.py`**：追认。拆包后 `JsonText` / `_in_domain` 需要一个不属于任何业务分组的住址，放 `__init__.py` 会让「重导出」与「定义」混在一个文件里。
- **`refdata.DATA_DIR` 改从 `config.BACKEND_DIR` 推导**：追认。`DEFAULT_DB_URL`/`DEFAULT_CSV_DIR`/`DATA_DIR` 三者都是「backend 目录下的某个路径」，`BACKEND_DIR` 是它们的共同所有者；此前 `refdata.py` 自己算了一遍 `Path(__file__).parents[N]`，是第二个所有者。
- **Step 1「同文件再加三条」的读法**：追认实现者的读法（三条 allow-list 相关守卫与依赖方向守卫同住 `test_layering.py`），计划原文有歧义。
- **动了两个 Files 块之外的测试 import**：追认。`models.py` 拆包必然让所有 `from app.db import models` 之外的直接导入（如 `from app.db.models import X`）需要复核；这是拆包的固有波及面，计划的 Files 块列不全。

**Ruling 21（实现者关切 C11，接受其取证方法）— 回放墙钟比 Plan 01 记录高 2–3 s，与本 Task 无关。**

实现者用 **`git worktree`** 在 `e26347f` 上亲测（不动主工作树）：BASE 20.48 / 20.85 s vs HEAD 20.89 / 21.18 s，差 **+0.37 s 小于两组各自的组内极差** ⇒ 不是本 Task 造成的，本机基线本来就是这个水平；`elapsed < 60` 余量 **2.83×**，不 flaky（符合硬规矩 #42 的 2× 线）。worktree 已 remove + prune。

**这是本项目第一次用 `git worktree` 做跨 commit 的性能对照**，比 Plan 01 那种「在同一工作树上改来改去」干净得多（后者正是 `autocrlf` 事故的温床）。**采纳为标准做法**，补进硬规矩 #42 的附注：**跨 commit 比较墙钟一律用 `git worktree`，不在主工作树上反复 checkout。**

**Ruling 22（实现者关切 C12，未改，控制者裁定）— 它指出的那处 Plan 01 产出的口径问题，本计划不改。**

实现者说这是「Plan 01 产出、口径决定权在你」，并在报告里给了现成替换文本。**裁定：转 Plan 03 处理，本计划不动。** 理由：Plan 01 已结案并合入 `main`，为一个口径措辞去改已合入的代码，会让 `main` 与 Plan 02 分支之间产生一个纯文档差异，而 Plan 02 的 Task 10 本来就要改 `daily.py`——**届时一并处理，成本更低、diff 更内聚**。替换文本留在报告里，Task 10 的派单要带上它。

---

**Task 1 的控制者错误小结**：本 Task 控制者错 **4 次**（#61 索引冗余、#62 两列已存在、#63 `CLEANING_FIELDS` 公式、#64 派单前没验工作树），实现者错 **0 次**，且实现者**主动发现并正确处置了一个控制者造成的工作树污染**。

**Plan 02 累计：控制者 4 次、实现者 0 次。**（Plan 01 全程：控制者 60、实现者 1、评审者 2。）

Task 1: 实现完成，派发任务评审（BASE `e26347f` → HEAD `1df5e8a`）。


#### Task 1 任务评审 — 控制者复核

评审者判定：**规格符合性 ✅ / 任务质量 Approved / Critical 0 / Important 4 / Minor 7**。评审结束时仓库状态自证干净（`git status --short` 0 行、HEAD 仍 `1df5e8a`、`pe.db` 不存在、`data/seed/` 0 文件、评分表 21412 B / `D2C8E539E2FA0029`、`git diff e26347f..1df5e8a --stat -- backend/data/ .gitattributes` 空、临时脚本全在 `$env:TEMP`）。

**评审独立复验了 7 条守卫、全部有牙**（4 条做变异、3 条做合成树端到端），并用**独立进程 dump `Base.metadata`** 证明拆包在 ORM 元数据层面逐结构相同：
```
tables base/head: 14 14      table name sets equal: True
=== 结构差异（BASE e26347f -> HEAD 1df5e8a）===
  daily_sync_run.col_order:      … 'insufficient_count', +'muscle_line_gaps', 'prescription_count', …
  daily_sync_run.muscle_line_gaps:  BASE=None  HEAD={'default':'0','nullable':False,'type':'Integer()'}
  fitness_test_result.col_order:    … 'student_id', +'tested_on', 'height_cm', …
  fitness_test_result.tested_on:    BASE=None  HEAD={'default':None,'nullable':False,'type':'Date()'}
total diff entries: 4
```
**只有 4 条差异、全是那两个计划要的新列；约束与索引零差异**——这同时反证了 Ruling 16（没偷偷加具名 `Index`）与「拆包没弄丢任何 `UniqueConstraint` / `CheckConstraint` / `ForeignKey`」。

**控制者对评审的关键取证做了独立复核（不采信转述）**：
- **Ruling 1 的导入面基线不是自指**：评审把 `git show e26347f:backend/app/db/models.py` 落到 `$env:TEMP` **真跑了一遍**，得 `dir()` 计数 **33**、与测试里的字面基线**列表相等（含顺序）**；右侧用 `observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)`，而 `_MODELS_PUBLIC_BASELINE` 是写死的字面量，另有两道防吞断言。**不是自指。**
- **Ruling 16 的守卫不是空转**：评审在进程内摘掉两条 `UniqueConstraint` → 该测试变红（`SCAN stratification_result` + `USE TEMP B-TREE FOR ORDER BY`），未变异时是 `SEARCH … USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)`。**控制者亲验 `models/derived.py` 的三条 UC 与 `Index( count: 0` 与此一致。**
- **Ruling 18 的 13 个值**：评审独立推导 `RawFitnessRecord` 8 个测量列 ∪ `RawBodyCompRecord` 3 个 ∪ `{student_no}` ∪ `WHOLE_RECORD` = **13**，并列出计划原公式漏的正是 `height_cm`/`weight_kg`/`muscle_mass_kg`/`body_fat_pct`/`smi`。**与控制者的复核逐字相同。**

**Ruling 23（评审 I1，接受为 Important，进 fix round 1）— 两条架构守卫对 `level >= 2` 的相对导入无条件放行，而 docstring 给的理由是错的。**

`test_domain_purity.py:97-100` 与 `test_layering.py:73-74,81-82` 都写「相对导入只可能落在（同一个）包内，故恒合法/一律跳过」。评审实测：这句对 `level == 1` 成立、对 `level >= 2` **不成立**——`app/domain/x.py` 里 `from ..seed import generate` 的 `node.level == 2` 解析到 `app.seed.generate`；**而拆包把 `app/db` 的模块深度加了一层，正好让 `from ...seed import generate`（level 3）从「不可达」变成「可达」**。评审用合成树端到端验证：`from .. import pipeline`、`from ..seed import generate`（domain 与 pipeline 两处）、`from ...seed`（db）**四种写法三条守卫全绿**；同时给出反例证明「不是守卫整体空转」（函数体内的 `from app.seed.fitness import …` 变红、空目录触发空转守卫变红、`import app.seedling` 正确不误报）。

**今天没有 offender**（评审亲查：全仓相对导入只有 `app/db/models/` 包内的 level-1）。但 **Ruling 3 的立意是「allow-list 把举证责任反过来，没被显式允许的一律不行」，而 `if level: return True` 恰好是「有一类写法一律允许」，与立意相反**；两处 docstring 还给了错理由，下一个人不会去查。这与终审 A 那 14/14 绕过是同一形状。

裁定：`_is_allowed` 把 level 折算成绝对串再走白名单（`level == 1` → 当前包、`level == 2` → `app`、`level >= 3` → 直接判 offender），`test_layering.py:81` 同法；两处 docstring 的「只可能落在包内」改成实测口径。各约 5 行。

**Ruling 24（评审 I2，接受为 Important）— `test_domain_purity.py:196-201` 虚报了守卫能力：AST 版本追不到别名化的时钟/文件调用，而它举的例子连自己的前提都不满足。**

原文「但 `now = datetime.now` 再 `now()` 就撞不上了，而 AST 侧只要 `now` 的赋值来源是一次 `ast.Call` 就能顺着 `_dotted` 追到」。评审实测两点都错：① `_dotted`（`:162-176`）只把**调用表达式自身**还原成点号串，**代码里没有任何赋值追踪**；② `now = datetime.now` 的赋值来源是 `ast.Attribute` 不是 `ast.Call`。评审的合成树实测 **`_f = open; _f('x')` 三道守卫全绿**（`open` 是内置名不需 import 故 allow-list 帮不上，`FORBIDDEN_IO` 里没有裸 `open` 故子串守卫也帮不上）。

同一次跑里**正向复验了确实修好的部分**：散文里提 `datetime.now()` / `open(` 不再误报、`reopen()` 与 `open_ended()` 不被误抓（`.` 边界替代 `\b` 正则）、`builtins.open()` **被抓住**。

裁定：把 `:199-201` 改成实测口径——AST 侧的真实收益是「散文不再误报」+「`builtins.open` 这类点号形态天然覆盖」+「`.` 边界替代 `\b`」，并**按项目惯例补一句「别名间接（`_f = open`）不被守卫」**。**这是硬规矩 #39 的直接适用**：写下守卫能力时必须写明它守不住什么，否则下一个人会以为已经堵住了。

**Ruling 25（评审 I3，接受为 Important）— `test_domain_purity.py:110-113` 关于旧 deny-list 的历史陈述与基线源码相反，且与本 commit 自己的信息、实现者报告 §5 互相矛盾。**

原文说旧守卫「确实拦得住 `from os import listdir`」。评审把基线守卫 `git show e26347f:…/test_domain_purity.py` 落盘、重定向 `DOMAIN` 到合成树后亲跑：基线 `FORBIDDEN` = `['fastapi','httpx','pydantic_settings','random','requests','sqlalchemy']`——**没有 `os`**；`from os import listdir` / `import numpy.random` / `import app.refdata` 三种写法在基线上**三条守卫全绿**（`from os import listdir` 里没有子串 `import os`，是 `os import`；也没有 `os.listdir`）。

**三处口径互相矛盾**：实现者报告 §5 写「旧的 deny-list 同样抓不到（`FORBIDDEN` 集合里没有 `os`）」✓、commit `1df5e8a` 的信息写「新增的拦截力是 `import app.refdata` 与 `from os import listdir` 这类**旧 deny-list 抓不到**的写法」✓、**只有落进代码的那句 docstring 是反的**。

裁定：改成实测口径（旧 `FORBIDDEN` 6 项、无 `os`；三种写法在基线上三条全绿）。**这条 docstring 是「为什么从 deny-list 换成 allow-list」的唯一在库论证**——写反了会让下一个人以为 allow-list 只是风格改动，从而在「要不要为 `numpy.linalg` 放宽白名单」这类决定上失去依据。

**Ruling 26（评审 I4，接受为 Important）— `min` 折叠的语义论证方向写反了：用开始日是让批次**更早**被判为可用，不是「宁可晚一点」。**

`daily.py:201-203` 与 `test_daily.py:642-644`（同一句话两处）写「用**开始日**是保守侧（宁可晚一点认它可用，也不要提前）」。评审实测反例：`assessment_anchor` 的判据是 `test_date <= as_of`（`percentile_stage.py:133`），`test_date` **越小**满足的 `as_of` **越多**。同一个批次 5 条成绩横跨 `09-01…09-05`、只改 `test_date` 一个值：`min` 侧从 `as_of = 09-01` 就被选中，`max` 侧要等到 `09-05`。**min = 提前，不是延后。**

**代码选择本身是对的**（`min` 可交换可结合、任意顺序任意次重放收敛——这才是真理由；配合 Step 4 新加的 `tested_on <= as_of` 逐行截断，「批次提前可用 + 只看见已测的那部分人」是自洽的）。但**被写进 docstring 的那条因果是反的，而它是这个设计决定的两条理由之一**——下一个人若照它推理会得出「应该改成 max 才保守」，那会把 Step 5 的修复推翻。

裁定：两处都改成实测口径。**这是 Ruling 210（编造的因果机制）的同一类缺陷，第 5 次出现**；也是硬规矩 #29（因果陈述必须附代码行 + 引文）与 #23 加强版（归因必须构造反例）的又一次适用——评审正是构造了反例才发现的。

**Ruling 27（评审 Minor 的逐条处置）**
- **M1 接受，进 fix round**：`app/config.py:35-36` 说 `DEFAULT_CSV_DIR` 是 `MockLePaoAdapter` 的「缺省 `seed_dir`」，而那个参数**没有缺省值**（`mock_lepao.py:428` 是必填位置参数，基线与 HEAD 都一样；缺省值是**工厂**给的，`factory.py:50`）。照它写 `MockLePaoAdapter()` 会 `TypeError`（响亮、不静默）。改成指向 `build_adapter`。
- **M2 接受，进 fix round**：`daily.py:209`（「实测数字见任务报告」）与 `test_layering.py:114`（命令带省略号 + 「见任务报告」）把出处指向**不入库**的文件（`.gitignore:10` 的 `.superpowers/`，`git ls-files .superpowers` 计数 0），指针解析不到任何东西，违反 Global Constraints「每个数字都要能指到产生它的那条命令」。评审替它复核了两个数字**都成立**（`git ls-tree -r --name-only` 数 `.py`：基线 `pipeline 7 / db 4 / domain 6 = 17` ✓ 与 docstring 逐字一致；HEAD `7 / 11 / 6 = 24`，下界 8 仍宽松）。改成写全命令 + 引账本 Ruling 编号，或标「历史实测，不被守卫」。
  ⚠️ 评审顺带发现 `app/db/models/organisation.py:69` 也有一处「已登记在任务报告的关切里」，**那是 Plan 01 原文搬运、非本 Task 引入**（`git show e26347f:backend/app/db/models.py` 命中）。**转延后 Minor**，不在本轮改（它是 Plan 01 的遗产，改它会让 Task 1 的 diff 扩散到无关文件）。
- **M3 接受，进 fix round**：`tests/db/test_models.py:589-604` 的 A/B 实测块口径齐全（0.2708/0.2941 ms、5 423 104/6 791 168 B、n=300、区间）但**缺「不被守卫」标签**，且复现脚本不在库里也没被点名 → **从仓库无法复现**。同一个 commit 里 `_shared.py:43-44` 恰好演示了正确写法。评审已复核算术全部成立（1.086 / +1 368 064 B / +25.23% / 56000）。补一句「以上四个数不被守卫（复现脚本不在库内），本测试守的是查询计划与两条唯一约束的列序」。
- **M4 接受（账本更正）**：实现者报告 §Step 1 的算术错了——拆包后 `.py` 总数是 **24**（`pipeline 7 / db 11 / domain 6`），不是报告写的 21。评审亲跑 `git ls-tree` 复核。**只在报告里、不在在库代码里**，且不影响「下界取 8」这个决定。**账本按 24 记。**
- **M5 接受现状，不改**：Step 4 第 1 项尾巴那句「并给 CLI 加一句提示」未做（交代只落在 `session.py:82-89` 等三处 docstring）。影响低：`create_all` 不补列，旧 `pe.db` 上的失效形态是响亮的 `OperationalError: no such column: fitness_test_result.tested_on`，不是静默错值；且 `pe.db` 不入库。**转延后 Minor**（若 Plan 03 真的部署到有人手工留 `pe.db` 的环境，再给两个 CLI 的 `ArgumentParser(epilog=…)` 加一句）。
- **M6 已由控制者更正计划正文**：计划 Task 10 那段「Plan 01 的 `error_summary` 留痕在 60 人下恒非空」被 Ruling 13 的直接切变成假的（现在 60 人下成功运行的 `error_summary` 恒 NULL、`muscle_line_gaps` 恒 4，`test_daily.py:717-751` 已钉住）。**若不改，Task 7/10 的简报会继承这句假话、让写测试的人去断言一个恒为 NULL 的列。**
- **M7 接受为可选，本轮做**：`app/config.py` 的三个值没有**非同源**测试（`test_factory.py:32` 的 `assert adapter.seed_dir == DEFAULT_CSV_DIR` 两侧同源于 `app.config`，正是硬规矩 #35 的形状）。评审已给出缓解与修法：`BACKEND_DIR` 错了会变红（`refdata.DATA_DIR = BACKEND_DIR / "data"` 被 `test_refdata.py:82-83`/`:187` 钉住），裸奔的只剩 `"data"/"seed"` 后缀与 `pe.db` 文件名。补 `assert DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() == "data/seed"` 与 `assert DEFAULT_DB_URL.endswith("/backend/pe.db")`（字面写死后缀）。**成本低、且这是本计划 Global Constraints 第 4 条的直接适用，故本轮做而不是延后。**

**控制者已做的计划正文更正（14 处，python 落盘 + shell 复核：12 个 Task 标题、CRLF 691、裸 LF 0、无乱码）**：Ruling 16 索引作废、Ruling 17 两列已存在、Ruling 13 直接切、Ruling 18 `CLEANING_FIELDS` 公式、Ruling 8 测试名含空格、Ruling 9 三档半开 + 边界值、Ruling 10 `status` 映射、Ruling 11 `NO_BUCKET` 守卫、Ruling 12 §14 七项、Ruling 7 `volume_reduction` 前移、Ruling 6 动作库来源、Ruling 1/2/5 拆包判据、评审 M6 的 `error_summary`。

**补硬规矩 #49：预检扫描必须核「计划里对既有代码的每一项断言」，而不只是核计划内部自洽。** 本 Task 的三处计划事实错误（索引冗余、两列已存在、`CLEANING_FIELDS` 公式）**全都是「计划断言既有代码是某个样子、而它不是」**——预检扫描表 B/C 查的是任务之间与任务内部的矛盾，**没有一栏查「计划 vs 既有代码」**。判据：计划里凡出现「X 没建 / X 住在 Y / X 的值是 N」这类关于既有代码的陈述，预检时必须 `git grep` 或跑一次确认，**不得从记忆或从别人的报告转写**。

**转延后 Minor（Task 1）**
- `Task 1: minor (deferred): app/db/models/organisation.py:69 的「已登记在任务报告的关切里」指向不入库的文件（Plan 01 原文搬运，非本 Task 引入）——评审 M2 附带发现`
- `Task 1: minor (deferred): 两个 CLI 的 argparse 没有「schema 改了要重建库」的提示（评审 M5）；失效形态是响亮的 OperationalError，影响低`

Task 1: fix round 1/5 派发中（评审 I1–I4 + Minor M1/M2/M3/M7，共 8 项，**全部是散文与守卫口径、零生产语义改动**），基线 `1df5e8a`、478 passed。


#### Task 1 fix round 1 — 控制者复核（commit `6a2938f`，478 → **479 passed**）

控制者独立复验：`git log --oneline -2` = `6a2938f` 一个 commit 在 `ad1d190` 之上；`git status --short` 空；`git diff ad1d190..HEAD --stat` = **7 文件 +371/−48**；`-- backend/app/seed/ backend/data/ .gitattributes` **为空**；`pytest -q` = **479 passed / 0 failed**（54.28 s）、`-W error` = **479 passed / 0 error**（54.47 s）。实现者报的 `app/domain` 分支覆盖 **399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%** 与基线逐字相同（本轮不动 domain）。

**八项全部落地**，其中 **I1 的实现有意偏离了控制者的裁定，而偏离是对的**。

**Ruling 28（实现者对 I1 的偏离，接受；控制者第 65 次错误）— 控制者给的「level 2 → `app`、level 3 → offender」常数档会让 Task 2 当场假红。**

裁定原文（Ruling 23）要求按 level 常数分档。实现者指出：**Task 2 会在 `app/domain/prescription/` 下建子包**，那里 `from ..indicators import X` 的 `level == 2` 解析到 `app.domain.indicators`——**完全合法**，但常数档会把它判成「level 2 → `app`」，而 `app` 不在 domain 的 allow-list 里 → **假红**。

实现者的替代做法：**按源文件的真实包深度折算绝对串**（新增 `_package_of` + `_absolute` 两个辅助），上溯出 `app` 或更浅的直接判 offender。**对今天扁平的 `app/domain/` 判定与常数档逐字相同**，对 Task 2 的子包则正确。

合成树验收（实现者亲跑，11 例）：**改前 5/11 → 改后 11/11**，派单点名的四种绕过（`from .. import pipeline`、`from ..seed import generate` 在 domain 与 pipeline 两处、`from ...seed` 在 db）全部对号变红，而 `app/db/models/` 包内的 **12 条 level-1 相对导入仍然绿**。

**控制者第 65 次错误的形态**：写裁定时**只对着当前的目录形状推理，没有对着计划的下一步推理**。这与 Ruling 192（把「预跑+跳过」归纳成「乱序」）方向相反——那次是把具体条件归纳得太宽，这次是把裁定写得太死。**两者同源：都没有构造反例。** 硬规矩 #23 加强版要求「构造一个同样满足归因但结果不同的场景」，这里应当推广为：**写任何守卫规则前，构造一个「合法但形状不同」的输入，确认它不会被误判**（本项目已有三次：Ruling 166 的过滤 grep、Ruling 216-M3 的读回常量、本条的 level 常数档）。

**补硬规矩 #50：设计一条守卫（allow-list / 词表 / 阈值 / 判据）时，必须同时构造 ① 一个应当变红的输入 ② 一个应当保持绿的合法输入，两者都跑。** 只做 ① 会得到一条过紧的守卫（假红），只做 ② 会得到一条空转的守卫（假绿）。**并且 ② 要取自计划的下一个 Task，不只是当前代码。**

**Ruling 29（实现者关切 C-fr1-1，接受）— Ruling 16 里「中位数还慢 8.6%」这个**方向**不可复现，只有「无可测加速」与「+25.23% 体积」成立。**

实现者本轮又跑了 2 次那个 A/B 复现脚本（加上上一轮共 **4 次**）：`.db` 字节数与查询计划**逐字复现**，但墙钟中位比 **B/A = 1.086 / 0.944 / 1.019 / 0.989——跨过 1.0**。所以「加具名索引后中位数还慢 8.6%」是**单次测量的噪声**，不是方向。

**这与硬规矩 #42 完全一致**（墙钟数字只能作为带 n 与区间的实测记录）：控制者在 Ruling 16 里转写实现者的单次 A/B 时，把「n=1 的 1.086」写成了一个方向性结论。**裁定：账本 Ruling 16 的那半句作废**，成立的只有两条：① 无可测加速（4 次 B/A 跨 1.0，区间 0.944–1.086）；② `.db` **+25.23%**（4 次逐字复现，`5 423 104 → 6 791 168 B`）。**实现者已把诚实版本写进在库的 `tests/db/test_models.py:611-616`**（这正是硬规矩 #39 要求的处置：不被守卫的数字要标明不被守卫、且写区间不写点值）。

**Ruling 30（实现者关切 C-fr1-2，接受）— Ruling 21 的「+0.37 s 小于两组各自的组内极差」对 HEAD 那组不成立。**

Ruling 21 记的是 BASE 20.48/20.85 s（极差 0.37）、HEAD 20.89/21.18 s（极差 **0.29**）。差值 +0.37 s **大于** HEAD 那组的极差 0.29，故「小于两组各自的组内极差」这句话对 HEAD 不成立。**n=2 根本不足以支撑「小于组内极差」这类比较**——这又是硬规矩 #42 的适用面。

裁定：Ruling 21 的结论**不变**（回放墙钟比 Plan 01 记录高的那 2–3 s 不是 Task 1 造成的，`elapsed < 60` 余量 2.83× 不 flaky），但**论证要降级**为「n=2 的两组区间重叠、差值在跑次噪声量级，故不能归因于本 Task；要严格归因需要 n≥5」。**实现者已把 `daily.py` 里那句改成 n=2 能支持的最强表述**，处置正确。

**Ruling 31（实现者关切 C-fr1-3，接受；控制者第 66 次错误）— 派单说 `DEFAULT_DB_URL` 在 `tests/` 下「零命中」，实测是 2 条命中 / 0 条断言。**

评审原文是「`DEFAULT_DB_URL` 在 `tests/` 下零命中」，控制者原样转写进派单。**「零命中」与「有命中但没有断言」是两件不同的事**——前者意味着没人碰它，后者意味着有人引用了它但没守它。实现者实测是后者。**这与 Ruling 191（把 MiB 当 MB）同型：转写时改变了陈述的口径。** 裁定：账本按实测口径记；评审 M7 的结论（三个值缺非同源守卫）**不受影响**，已落地为 `tests/test_config.py`。

**Ruling 32（实现者主动披露的两处超范围改动，追认）**
`test_domain_purity.py` 有两处超出八项范围的最小更正：① `_dotted` 的「那不是漏洞」这句对 `open` 不成立；② 模块 docstring 补一句 fix round 1 说明。**追认**——两处都是为了让 I2 要求的「写明守不住什么」在**同一个文件内不自相矛盾**，不改任何判定。这与 Ruling 20（追认 `test_backfill.py:82` 的同类改动）同一先例：**同一缺陷类的就近修正是应当的，分两次改才是浪费。**

**Ruling 33（实现者关切 C-fr1-6，转延后 Minor）**
`_package_of` / `_absolute` 在两个架构守卫里各一份（**12 行重复**）。实现者留了记号未抽公共模块。**裁定：转延后 Minor，本计划内不抽。** 理由：① 两个守卫的判定语义**故意不同**（domain 是 allow-list、pipeline/db 是「不得依赖 `app.seed`」），抽公共模块会把两种语义耦在一起；② `tests/architecture/` 只有两个文件，重复的维护成本极低；③ 抽公共模块会引入一个「测试助手模块」，而它自己没有守卫。**若 Plan 03 再加第三个架构守卫，届时再抽。**

**Ruling 34（实现者关切 C-fr1-5，记录）— 编辑工具把 3 个文件整体重写成裸 LF，实现者按字节归一化回 CRLF。**

**Ruling 34a（实现者关切 C-fr1-4，补处置 —— 原账本漏了这一条，见 Ruling 70）— 「`Read` 工具行号系统性少 1」这个归纳不成立。**

**本条在 fix round 1 复审时就该写下，却既没修也没记延后，静默消失了三轮**，直到收尾评审 grep `C-fr1-` 才发现零命中（控制者错误 #86 / Ruling 70）。**正确版本**：`Read` 的偏移**不是固定值**——fix round 4 实测 **0 / −1 / −2 在不同区段并存**，且**同一行内容两次调用分别被标 449 和 450**（对自己都不自洽）；收尾评审另抽验 `progress.md:444-453` 偏移为 **0**。**结论（一律取 shell 口径，硬规矩 #30）不变，而理由更硬：这不是一个可以补偿的固定偏移。** 已落进计划正文（Ruling 64 → commit `ef48d33`；时点绑定 → Ruling 75）。

blob 不变、`git diff --numstat` 逐字相同，故**对提交内容无影响**。这是「工具/磁盘分歧」家族的第 45–47 次（上一轮报告文件连续 26 次）。**补进硬规矩 #46 的附注**：凡编辑工具重写了整个文件，必须复核行尾（`python` 读字节数 `

` 与裸 `
`），因为 `core.autocrlf=true` 下裸 LF 的工作树文件会让 `git status` 显示为已修改、或在下次 checkout 时被静默转换。

---

**转延后 Minor（Task 1 fix round 1 新增）**
- `Task 1: minor (deferred): _package_of / _absolute 在两个架构守卫里各一份（12 行重复），语义故意不同故本计划内不抽；Plan 03 若加第三个守卫再抽（Ruling 33）`

**Task 1 的控制者错误小结（含 fix round 1）**：#61 索引冗余、#62 两列已存在、#63 `CLEANING_FIELDS` 公式、#64 派单前没验工作树、**#65 level 常数档会让 Task 2 假红**、**#66「零命中」口径错**。共 **6 次**，实现者 **0 次**，评审者 **0 次**（评审的 4 条 Important 全部成立且有可复现证据）。

**Plan 02 累计：控制者 6 次、实现者 0 次、评审者 0 次。**

Task 1: fix round 1/5 完成（8 项全部落地），派发**范围内复审**（FIX_BASE `ad1d190` → HEAD `6a2938f`）。


#### Task 1 fix round 1 — 范围内复审（复审者亲跑，控制者采信其证据）

**判定：8 条 finding 全部 ADDRESSED / 0 NOT ADDRESSED；但 fix diff 里新引入 4 条 Important + 5 条 Minor。**

复审的取证密度超出派单要求，其中三项值得单独记：
- **M3 的复现脚本它没有采信「实现者说跑过」**，而是**用 AST 从 docstring 的字面块里把脚本原样抽出来**（`ast.get_docstring(fn, clean=False)` + dedent）落到 `$env:TEMP` 再跑——这是「复现脚本写进 docstring」这个处置的**真正验收方式**：能被机器抽出来跑，才算「从仓库可复现」。跑通了，`exit = 0`，确定性量全部逐字复现（`5 423 104` / `6 791 168` / `+1 368 064 B` / `+25.23%` / `56000` 行 / 两条 `EXPLAIN QUERY PLAN`）。**并给出了第 5 个独立样本 `B/A = 0.989`**，再次反证 Ruling 29 那个「慢 8.6%」的方向。
- **Ruling 28 的反事实它自己实现了**：把控制者原裁定的常数档（`level==2 → "app"`、`level>=3 → offender`）写出来与 HEAD 的 `_absolute` 并排判 7 种形状，实测常数档在 Task 2 的形状上造出 **3 条假红**，HEAD 的深度折算 **7/7 正确**。**这坐实了实现者的偏离是对的、控制者的裁定是错的。**
- **零生产语义改动它自己验了一遍**（不用实现者的脚本）：剥 docstring 后 `ast.dump` 比较，`config.py` / `daily.py` / `test_models.py` / `test_daily.py` 四个 **True**，两个架构守卫 **False**（预期例外），`test_config.py` 是新文件；对照组 3 个真语义变异全部 caught、自比对照 True（尺子不是恒 False）。

**Ruling 35（复审 Important #1，接受，进 fix round 2）— 新 `_absolute()` 的负数切片：`level ≥ 包深+2` 时返回假绿，与本 diff 自己刚写的政策相反。**

`test_domain_purity.py:135` 与 `test_layering.py:92` 都是 `anchor = package[: len(package) - (level - 1)]`。当 `level - 1 > len(package)` 时切片末端为**负**，Python 从尾部切、得到非空 anchor，于是本该返回 `None`（→ offender）的一档被折成一个**更浅的错误绝对串**。复审端到端实证：
```
[layering] app/db/models/probe.py  from .....seed import generate  pkg=app.db.models  folded=app.db.seed  -> GREEN
[purity  ] app/domain/probe.py     from ....domain import tables   pkg=app.domain     folded=app.domain   -> GREEN
importlib 自己：resolve_name('.....seed.generate','app.db.models') -> ImportError: attempted relative import beyond top-level package
```
对拍矩阵 80 格里 **8 格 DIFF 全在这一档**（`level ≤ 包深+1` 的 72 格与 `resolve_name` 逐字相同）。

**为什么是 Important 而不是 Minor**：本 diff 在 `test_domain_purity.py:128-131` 与 `test_layering.py:86-88` **新写**的政策正是「返回 `None` 的那一档同样判 offender、**不是「不管」**：静态守卫不拦的话『写一句永远跑不到的 import』也能让本测试全绿」。这个 bug 恰好为更高 level 的「永远跑不到的 import」开了免费通行，而 `purity` 那一例还落在白名单前缀 `app.domain.` 内、是真绿。**实际风险≈0**（没人写 4–5 个点，Python 运行期就 `ValueError`），但它与自己刚写的理由直接矛盾。修法一行：切片前判 `if level - 1 > len(package): return None`。

**Ruling 36（复审 Important #2，接受）— `_absolute()` 只看 `node.module`、不看 `node.names`：`from .. import seed` 在 layering 侧仍假绿。**

`from .. import seed` 的 AST 是 `ImportFrom(module=None, level=2, names=[alias('seed')])`，`_absolute("", 2, ("app","pipeline"))` 折成 `"app"`、`_is_forbidden("app")` 为假 → GREEN，而真实目标是 `app.seed`。复审实测三种形状（`app/pipeline`、`app/db`、`app/db/models`）全部假绿，而 `from ..seed import generate` 正确变红。

**不是回归**（`ad1d190` 上 `if node.level: continue` 把全部相对导入跳过，同样绿），故 I1 仍判 ADDRESSED。但 `test_layering.py:101-104` 是**本 diff 新写**的「相对导入不再一律跳过」，而这一类写法仍在跳过范围内——**硬规矩 #50 的「① 一个应当变红的输入」对这一档没做到**。`purity` 侧不受影响（`"app"` 不在白名单 → 自然变红，复审已实测）。修法：`module` 为空时把 `node.names[0].name` 接上去（或对 `names` 逐个折算）。

**Ruling 37（复审 Important #3，接受）— 两个 docstring 里的 `resolve_name` 例子是假的（把模块名当包名传）。**

`test_domain_purity.py:117-118` 写 `resolve_name("..seed.generate", "app.domain.ind") == "app.seed.generate"`，`test_layering.py:84-85` 写 `resolve_name("...seed.generate", "app.db.models.organisation") == "app.seed.generate"`。复审亲跑：
```
resolve_name('..seed.generate', 'app.domain.ind')             = 'app.domain.seed.generate'   -> MISMATCH
resolve_name('...seed.generate','app.db.models.organisation') = 'app.db.seed.generate'       -> MISMATCH
resolve_name('..seed.generate', 'app.domain')                 = 'app.seed.generate'          -> MATCH
resolve_name('...seed.generate','app.db.models')              = 'app.seed.generate'          -> MATCH
```
`resolve_name` 第二个参数是 `__package__`（**包名**）。**代码是对的**（`_package_of` 返回的正是包），错的只是举例。判 Important 的理由：**这两句是 `_package_of` 的规格说明**——谁按例子去「对齐」代码（让 `_package_of` 返回 `("app","domain","ind")`），`app/domain/x.py` 里的 `from ..seed import generate` 就会折成 `app.domain.seed` → 命中 `app.domain.` 前缀 → **假绿、守卫当场失效**。改成 `"app.domain"` / `"app.db.models"` 即可。

**这是硬规矩 #29 的又一次适用**：一个「看起来是引文」的例子，如果没有跑过，就是编造的机制的另一种形态——它比散文更可信，因为它长得像可执行的断言。**补进 #29 的适用范围：docstring 里凡是形如 `f(x) == y` 的举例，必须是真跑过的输出，或明确标注为「示意，未实跑」。**

**Ruling 38（复审 Important #4，接受为 Important，不按「基线遗留」降级）— `__import__("datetime").datetime.now()` 绕过全部三条 domain 守卫，而本 diff 的 `+` 行声称「拿到这些对象的唯一途径是 import」。**

`test_domain_purity.py:247-248`（本 diff 的 `+` 行）：「对 `datetime` / `time` / `builtins` 那不是漏洞：**拿到这些对象的唯一途径是 import**，而 import 已经被 allow-list 挡在门外」。复审亲跑：
```
__import__("datetime").datetime.now()                    G1 GREEN  G2 GREEN  G3 GREEN
__import__("os").listdir(".")                            G1 GREEN  G2 GREEN  G3 GREEN
__import__("builtins").open("x")                         G1 GREEN  G2 GREEN  G3 GREEN
getattr(__import__("datetime"), "datetime").now()        G1 GREEN  G2 GREEN  G3 GREEN
import datetime as dt | dt.datetime.now()  ←对照          G1 RED    G2 RED    G3 GREEN
```
`__import__` 是**内置名**，G1 只看 `ast.Import` / `ast.ImportFrom`，故拦不住。

**provenance 诚实标注**：这半句在 `ad1d190` 就存在（评审包的 `-` 行可见），本 diff 把它**收窄**了（为 `open` 补了缺口）。复审按「它是 `+` 行」报 Important、把降级与否交给控制者。

**裁定：按 Important 处理，不降级。** 理由：① 它出现在 `+` 行里，本轮就是来消灭这类虚报的（I2/I3 同类），留着它等于本轮只修了一半；② 修法只是散文——把「唯一途径是 import」改成实测口径，并把 `__import__` / `eval` / `getattr(x, "now")()` / `table[0]()` 这一族**一并写进「不被守卫」清单**（复审的「范围外观察」指出这一族同样三条全绿、且是基线遗留）。**按硬规矩 #39，写下守卫能力时必须写明它守不住什么——这一族的清单比那句错误的保证有用得多。**

**Ruling 39（复审 5 条 in-diff Minor 的处置）**
1. **`test_layering.py:172`「仍剩 13…17 个 .py」上界写错** → **修**。实测 24−7(pipeline)=17、24−11(db)=13、**24−6(domain)=18**，正确区间 **13…18**。
2. **`test_models.py:600` 仍留「中位数还慢了 8.6%」且无就地标记**（撤回在 13 行之下的 `:613`）→ **修**：就地补「（此方向不可复现，见下方 ⚠️）」，并把 `:595-596` 表头那两个点值的标签改成「单次采样，方向不可复现」。**只读到 `:600` 的人会引一个已被本文件撤回的数**——这正是 Ruling 29 要消灭的形态。
3. **`test_domain_purity.py:197-199` 的主语与结论不匹配** → **修**：主语写的是 `app/domain/sub/x.py`，但「`from ..seed import generate` 解析到 `app.seed.generate` → offender」在**该文件深度下是假的**（复审实测 `app/domain/sub/probe.py` 里它折成 `app.domain.seed`、守卫 GREEN；要折到 `app.seed` 得是扁平的 `app/domain/x.py`）。**这句正好在 Ruling 28 的论证段里**，补主语。
4. **`daily.py:226`「组内极差 0.38 s」与同行给出的 20.48 / 20.85 推不出（= 0.37）** → **修**。实现者在 C-fr1-2 自己指出过「应是未舍入值」，但仍把 0.38 写进了代码。**要么写未舍入值并注明、要么写 0.37**；两者都不写就是留一个算不出来的数。同段 `:227` 的 0.29 与 21.18−20.89 一致 ✓。
5. **`test_domain_purity.py:155-156` 把基线 `:13` 的单行 `FORBIDDEN` 排成两行的 `::` 字面块**（六项与顺序都对、只是折行）→ **不修，转延后 Minor**。它读起来像逐字引文而非原格式，但没有事实错误；改它纯属排版 churn。

**Ruling 40（复审「范围外观察」的处置）**
- `app/db/models/organisation.py:69` 指向不入库的「任务报告」→ 已在 Ruling 27 转延后 Minor，**维持**。
- `_package_of` / `_absolute` 在两个守卫里各一份（12 行重复）→ Ruling 33 已裁本计划内不抽，**维持**。⚠️ 但 Ruling 35/36 的两个 bug **在两份里各有一份**，修的时候**两处都要修**——这正是重复的代价，本轮亲身验证了 Ruling 33 那个「维护成本极低」的判断偏乐观。**把这条记进 Ruling 33 的更正。**
- `eval("…")` / `getattr(x,"now")()` / `table[0]()` 同样绕过三条 domain 守卫 → **并入 Ruling 38 的「不被守卫」清单**。
- `test_backfill.py` 的 `elapsed < 60` 只在超 60 s 时才红、退化到 25 s 照样绿 → **不修**。这是硬规矩 #42 的自觉结果（墙钟断言只守数量级），`daily.py:229-231` 已自陈。
- `test_config.py:30` 把 `backend` 目录名钉进断言、仓库改名会红 → **不修**。这是 M7 要求的「非同源」的必然代价：字面写死后缀就意味着钉住后缀。

---

**转延后 Minor（Task 1 fix round 1 复审新增）**
- `Task 1: minor (deferred): test_domain_purity.py:155-156 把基线单行 FORBIDDEN 排成两行的 :: 字面块，读起来像逐字引文（Ruling 39-5，纯排版）`
- `Task 1: minor (deferred): _package_of/_absolute 的两份重复已在本轮亲身付出代价（Ruling 35/36 的 bug 各有一份）——Ruling 33 的「维护成本极低」判断偏乐观，Plan 03 若加第三个架构守卫必须抽公共模块`

**补硬规矩 #51：修一个「两份重复的守卫」里的 bug 时，必须 grep 出全部份数并逐份修，且在报告里列出份数。** 依据：Ruling 35/36 的两个 bug 在 `test_domain_purity.py` 与 `test_layering.py` 各有一份，任何一份漏修都会留下一条假绿的守卫，而**两条守卫的名字不同、没人会想到它们是同一段逻辑**。

**补硬规矩 #52：docstring 里形如 `f(x) == y` 的举例必须是真跑过的输出，或明确标注「示意，未实跑」。** 依据：Ruling 37——一个假的 `resolve_name` 例子是 `_package_of` 的规格说明，谁按它「对齐」代码就会把守卫改成假绿。它比散文更危险，因为它长得像可执行的断言。

Task 1: fix round 1/5 完成（8 项 ADDRESSED，复审新报 4 Important + 5 Minor），fix round 2/5 派发中（Ruling 35/36/37/38 + Minor 1–4），基线 `6a2938f`、479 passed。

#### 派单前预检（控制者亲跑，修正自己刚写进账本的一条）

**Ruling 41（控制者错误 #67，Critical 级形态：差点变成一条不可满足的验收判据）— Ruling 36 里「三种形状全部假绿」是错的，第三种形状的判定其实是对的。**

我把复审的原话照抄进了账本，没有自己跑一遍。控制者亲跑 `importlib.util.resolve_name` 与 HEAD 的 `_absolute` 对拍（脚本 `.superpowers/sdd/_probe.py`，跑完删除；`FORBIDDEN_PREFIX = "app.seed"`、判据是 `== prefix or startswith(prefix + ".")`）：

| 形状 | `resolve_name` 的正确答案 | HEAD 的 `_absolute` 折算 | HEAD 判定 | 修后判定 |
| --- | --- | --- | --- | --- |
| `from .. import seed` @ `app/pipeline` | `app.seed` | `app` | GREEN ← **假绿** | **RED** |
| `from .. import seed` @ `app/db` | `app.seed` | `app` | GREEN ← **假绿** | **RED** |
| `from .. import seed` @ `app/db/models` | `app.db.seed` | `app.db` | GREEN ← **判定正确、折算错** | GREEN（折算修正为 `app.db.seed`） |
| `from .. import seed` @ `app/domain` | `app.seed` | `app` | purity 侧 `app` 不在白名单 → 已 RED | RED |
| `from .....seed import generate` @ `app/db/models` | `ImportError: attempted relative import beyond top-level package` | `app.db.seed` | GREEN ← **假绿** | **RED**（`_absolute` 返回 `None`） |
| `from ....domain import tables` @ `app/domain` | 同上 `ImportError` | `app.domain` | GREEN ← **假绿**（命中白名单前缀 `app.domain.`） | **RED** |

第三行是关键：`app/db/models` 的深度是 3，`from .. import seed` 上溯一层到 `app.db`，**它本来就不指向 `app.seed`**，所以「绿」是正确判定，只是折算出的字符串错了（`app.db` 而非 `app.db.seed`）。

**为什么这条是 Critical 级形态而不是笔误**：我正要把它写成派单里的验收判据「三种形状都必须变红」——那是一条**按字面不可满足**的判据，实现者要么造假、要么白跑一轮回来问。**这与控制者错误 #46/#47（Plan 01 Ruling 184，8 条变异里 2 条按字面不可满足）是同一个错误类型的第二次发生**，而且这次它已经写进了账本、离派单只有一步。

**根因**：复审给出的是一句归纳（「三种形状全部假绿」），我采信了归纳而没有采信它底下的原始数据——**而归纳恰恰是最容易在边界样本上出错的那一层**。补进硬规矩 #44 的适用范围：

**硬规矩 #44 扩写：转写评审者/实现者的结论时，若该结论将被用作验收判据（「必须变红」「必须等于 N」），控制者必须亲跑一遍把判据落到具体输入上；只转写归纳、不转写数据，就是控制者错误 #67 的形态。**

**派单时因此把 Ruling 36 的验收判据改成**：`app/pipeline` 与 `app/db` 两例必须变红；`app/db/models` 一例必须**保持绿但折算串变成 `app.db.seed`**（用直接调用 `_absolute` 断言返回值，而不是靠守卫颜色）；并要求实现者在报告里写明这个区别，**不得把三例都写成「变红」**。

**另一项预检发现（并入 Ruling 38 的落点）**：`test_domain_purity.py:286-293` 已经有一张 G1/G2/G3 三列的探针实测表（`_f = open; _f('x')`、`reopen()`、`open_ended()`、docstring 提及、`open('x')`、`builtins.open`、`dt.datetime.now()` 七行）。Ruling 38 要求的「不被守卫」清单**应当作为新行加进这张表**（并由实现者亲跑填色），而不是另起一段散文——表是这份 docstring 里唯一被读者当成实测数据看的部分。

**第三项预检发现（并入 Ruling 36 的实现约束）**：`_imported_modules:127` 是 `yield node.lineno, _absolute(node.module or "", node.level, package)`，**一个 `ImportFrom` 节点只 yield 一条**。而 `from .. import seed, pipeline` 导入的是**两个**模块，故修 Ruling 36 时不能只改 `_absolute` 的返回值：`module` 为空时必须**对 `node.names` 逐个 yield**（或让 `_absolute` 返回序列）。派单里把这条写成显式要求，并给出 `from .. import seed, pipeline` @ `app/pipeline` 必须 yield 出 `app.seed` 与 `app.pipeline` 两条、前者判红的验收。

Task 1: fix round 2/5 派发（Ruling 35/36/37/38 + Minor 1–4，判据已按 Ruling 41 校正），基线 `6a2938f`、479 passed。

#### Task 1 fix round 2 — 控制者亲验（commit `1fa9941`，479 passed 不变）

**判定：8 项全部 ADDRESSED；控制者独立复跑了全部关键判据，不接受报告为证据。**

亲验清单（全部本机实跑）：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 479 passed | `cd backend; python -m pytest -q` | **479 passed in 53.80s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%** ✓；`478 passed, 1 skipped` 的那 1 条 skip 是 `test_backfill.py:182` 的 trace-hook 自觉跳过（Plan 01 硬规矩 #42 的既有行为，非回归）✓ |
| Ruling 35 | 直接调两份 `_absolute`：`("seed", 5, ("app","db","models"), "generate")` 与 `("domain", 4, ("app","domain"), "tables")` | **两份都返回 `None`** ✓；`resolve_name` 对同一输入抛 `ImportError` ✓ |
| Ruling 36 | 7 个形状直接调两份 `_absolute`，与 `resolve_name` 对拍 | **7/7 相符、两份互相一致**：`app.seed` / `app.seed` / `app.db.seed` / `app.seed` / `None` / `None` / `app.seed.generate` ✓ |
| Ruling 36 的多名展开 | 读两份 `_imported_modules` 的 AST | purity 侧 yield 四元组、layering 侧对每个 alias 各调一次 `_absolute`，`from .. import seed, pipeline` 两侧都出两条 ✓ |
| Ruling 36 的真仓形状 | AST 扫 `app/db/models/__init__.py` | `:74` 确为 `from . import feedback, prescription  # noqa: F401`，AST `level=1 module=None names=['feedback','prescription']` ✓（实现者印进 docstring 的那句为真） |
| Ruling 37 | grep 两处 `resolve_name` 举例 + 自己实跑四个值 | 已改成包名，且**把错的版本作为带标注的反例保留**（比我要求的更好）；四个实跑值与 docstring 逐字相符 ✓ |
| Ruling 38 | 自己搭合成树、重定向 `BACKEND` **和** `DOMAIN`，14 行探针 + 1 行干净对照全部重跑 | **14/14 行颜色逐字复现**，对照行 GREEN/GREEN/GREEN（尺子不是恒 RED）✓；`FORBIDDEN_IO` 子串命中 `0` vs `2` 亦复现 ✓ |
| Minor 1 | grep `test_layering.py` | `:216` 已改成「13…18（24 − 11(db) = 13、24 − 7(pipeline) = 17、…）」✓ |
| Minor 2 | `git diff` | 表头标签改为「单次墙钟中位 (ms，单次采样、方向不可复现)」、`:600` 就地补 ⚠️ 并指向下方「复跑」段，**两个点值一个没删** ✓ |
| Minor 3 | grep | `:241`「**扁平的** `app/domain/x.py`（包深 2）」与 `:244`「`app/domain/sub/x.py`（包深 3）」主语与结论已同深度 ✓ |
| Minor 4 | `git diff` | `:226` 改为「组内极差 20.85 − 20.48 = 0.37 s；两个样本各自只记到百分位，故极差也只能给到这个精度」——**写出算式**，比我给的两个选项都好 ✓ |
| 硬规矩 #51（两份都改） | AST 抽两份 `_absolute`，剥 docstring 后逐语句 `ast.dump` 比 | args 都是 `['module','level','package','name']`、各 1 个默认值、各 6 条语句、**identical(excl docstring) = True** ✓ |
| 硬规矩 #32（零生产语义） | 剥 docstring 后 `ast.dump` 比基线 | `daily.py` **SAME**、`test_models.py` **SAME**、两个守卫 **DIFF**（预期例外）✓ |
| 断言未被改 | AST 抽两个守卫文件里 `test_*` 的全部 `assert` 逐字比 | purity 3 条 + layering 2 条 = **5 条，逐字相同** ✓ |
| 收工自证 | `git status --short` / `pe.db` / `data/seed/` / `fr2_probes` | 0 行；`pe.db` 不存在；`data/seed/` 0 文件；`fr2_probes/` 11 个脚本在 `.superpowers/`（`.gitignore:10`）内 ✓ |

**实现者报的 4 条「控制者错误」，我逐条核实：3 条成立、1 条不成立。**

**Ruling 42（控制者错误 #68，接受）— `_is_allowed("app.domain")` 命中的是**相等**那一支，不是「白名单前缀 `app.domain.`」。**

亲验：`ALLOWED_PACKAGE = 'app.domain'`；`'app.domain' == ALLOWED_PACKAGE` → **True**；`'app.domain'.startswith('app.domain.')` → **False**。我在派单里写「命中白名单前缀 `app.domain.` 变成真绿」——**结论（真绿）对、机制错**。同一句错话也在我自己写的账本 Ruling 35 里，以及**已被实现者照抄进 `test_domain_purity.py:167`**（它自己在 C-fr2-2 主动披露了这一点）。

**grep 全仓确认只有这一处错**：`test_domain_purity.py` 里「命中白名单前缀 `app.domain.`」共 3 处，`:139` 与 `:246` 说的是 `app.domain.seed.generate`（`startswith('app.domain.')` 为 True，**正确**），只有 `:167` 说的是折算出的**精确串** `app.domain`（走相等支，**错误**）。→ **进 fix round 3**。

**Ruling 43（控制者错误 #69，接受）— Minor 2 的行号我写错了。**

派单写「`:594-596` 表头那两个点值」。亲验：`:594` 是表头标签行、`:595` 是 `=====` 框线、两个点值 **0.2708 / 0.2941 在 `:596` / `:597`**。实现者按标签改、一个数没删，结果正确。→ 无需返工，记错误。

**Ruling 44（控制者错误 #70，接受，本轮最重的一条）— 「硬规矩 #48–#52 散在最后三节」是错的，照字面读会漏掉 #50。**

亲验账本行号：**#48 在 `:172`、#49 在 `:265`、#50 在 `:290`**，而最后三节从 **`:333`** 起（`#### Task 1 fix round 1 — 范围内复审`）、`#51` 在 `:409`、`#52` 在 `:411`，全文 448 行。也就是说**五条里只有两条在「最后三节」内**。

**为什么这条最重**：**#50 正是本轮红/绿双输入验收表的依据**（「设计一条守卫时必须同时构造 ① 一个应当变红的输入 ② 一个应当保持绿的合法输入」）。派单让人「只读最后三节」，等于把本轮最该读的那条规矩指到了阅读范围之外——实现者是自己多读了才发现的。**这与 #67 是同一类型（转写位置/归纳而没核原始数据），但后果更直接：它会让实现者按错的规矩干活。**

**Ruling 45（实现者第 4 条不成立，不接受为控制者错误）**

它说「Ruling 35 第一例『折成 `app.db.seed`』缺前提，只对 `module="seed"` 成立；`from .....seed.generate import X` 会折成 `app.db.seed.generate`」。**我核了：派单给的是完整字面形状 `from .....seed import generate`**，其 AST 就是 `module="seed"`，故「折成 `app.db.seed`」对该输入**精确正确**（我 V8 亲跑复核过）。它自己也在报告里写「判据仍可满足、我按字面跑通了」。

**裁定：这是一条有价值的「表述健壮性」建议，但不是事实错误，不计入控制者错误。** 理由要写明：**把不成立的指控也一并认下来，和把成立的指控辩掉，是同一种失职**——账本上的错误计数是要用来找模式的，掺水就找不到了。它自己第一版探针把两种形状弄混，说明**这个字面形状容易被误读**，故采纳其建议的**做法**：fix round 3 的回归测试直接以 AST 形状为参数（`(module, level, package, name)` 四元组），不再用「`from …` 的字面写法」当唯一标识。

**Ruling 46（C-fr2-4，接受，进 fix round 3）— 本轮修掉的两个 bug 在仓库里没有回归测试：谁删掉 `if level - 1 > len(package): return None`，479 条全绿。**

这是**硬规矩 #50 的欠账**：我给了红/绿双输入的**验收**，但那是合成树上的一次性取证，**没有沉淀成仓库里的断言**。Plan 01 花 11 个 Task 把「0 红变异」从 12 个清到 0 个，本轮却在两个新守卫点上重开了同一个口子。

**授权新增测试**（会让 479 变化，这是预期的、须在报告里逐条列明）：
- 在 `test_domain_purity.py` 与 `test_layering.py` **各加一条**（硬规矩 #51：两份 `_absolute`，就要两份回归测试）
- **判据不要抄表**：直接对 `importlib.util.resolve_name` 断言——`_absolute(module, level, package, name)` 必须等于 `resolve_name("."*level + (module or name), ".".join(package))`，而 `resolve_name` 抛异常的那一档必须返回 `None`。这样测试锚在 **Python 自己的语义**上，不是锚在我给的某一张表上。
- 矩阵至少覆盖：Ruling 35 的两个越界形状、Ruling 36 的四个 `module` 为空形状、`level == 0` 的绝对导入、`level == 1` 的包内导入（合法绿）、`from ..seed import generate` @ `app/pipeline`（真 offender）
- **变异验收（两份都要做）**：① 删掉 `if level - 1 > len(package): return None` → 新测试必须变红；② 把 `tail = module or name` 改回 `tail = module` → 新测试必须变红；③ 三重还原取证，并在报告里给出还原后的 `git status` 与 HEAD

**Ruling 47（C-fr2-3，不接受，转延后 Minor）— 不给 `FORBIDDEN_IO` 加 `__import__(`。**

理由：G3 是**子串**守卫，往子串 deny-list 里加内置名正是终审 A 的 M7 刚刚把 G2 迁出来的那场军备竞赛；代价（domain 里连一个正常的 `getattr(obj, "name", default)` 都写不了）实现者自己已经写在 `test_domain_purity.py:401-403`。**按硬规矩 #39，写清能力边界比堵一个绕过更有价值**，本轮已做到。→ 延后 Minor。

**补硬规矩 #53：合成树 / harness 探针必须带一条「已知 GREEN」的对照行；对照组变异必须在 AST 上确认它真的改了代码。**

依据是我**本轮自己犯的两次**（都在亲验阶段，没污染任何裁定，但都差点让我误判）：
- **#71**：第一版 harness 只重定向了 `DOMAIN`、没重定向 `BACKEND`，于是 `_package_of` 的 `relative_to(BACKEND)` 抛 `ValueError`，**14 行探针全部 RED**——包括 `__import__` 那 7 行。如果没有那条 `VALUE = 1` 的干净对照行也一起 RED，我就会把它当成「实现者的表是假的」写进裁定。**是对照行把假 RED 暴露出来的。**
- **#72**：第一版「3 个真语义变异」里**2 个是无效变异**——`elapsed < 60` 在 `daily.py` 里**只出现在 docstring**（真正的断言在 `test_backfill.py`），剥掉 docstring 后自然判相等；`    business_date = ` 这个字符串**在文件里根本不存在**，`replace` 没匹配上、`mutated == src`。结果 `caught=False` 看起来像尺子坏了。**改成在 AST 上直接改一个 `ast.Constant` 的 int 值之后，(c) docstring-only 变异判相等、(d) 语义变异 caught，两向都成立。**

**这与控制者错误 #36/#39（Plan 01）是同一族**：#36 是把「复合变异下的 1 条红」当成「1 条守卫」，#39 是用第一行样本推列清单而那一行恰好是 `None`。**共同点是「尺子本身没被验过」。**

**转延后 Minor（fix round 2 新增）**
- `Task 1: minor (deferred): FORBIDDEN_IO 不含 __import__( ，G3 子串守卫可被内置名绕过（Ruling 47，代价已印在 test_domain_purity.py:401-403）`
- `Task 1: minor (deferred): test_models.py:593-598 那张表的 ==== 框线宽度与新表头不再对齐（在 docstring 字面块内，不影响渲染，纯排版）`

**控制者错误计数（Plan 02 Task 1）**：#61–#66（预检 + 实现 + 评审三轮）、#67（Ruling 41）、**#68/#69/#70（本轮 Ruling 42/43/44）、#71/#72（本轮亲验阶段，硬规矩 #53 的依据）** = **12 次**。Plan 01 为 60 次，**合计 72 次**。实现者 1 次（Plan01 Ruling 80）、评审者 2 次（终审 B 的 T5-b、终审 C 的 2901 分母）、**本轮复审者 1 次（Ruling 36 的「三种形状全部假绿」，已由 Ruling 41 更正）**。

Task 1: fix round 2/5 完成并亲验（8/8 ADDRESSED，479 passed 不变，domain 100% 维持），fix round 3/5 派发中（Ruling 42 的一处机制错话 + Ruling 46 的两份回归测试），基线 `1fa9941`。

#### Task 1 fix round 3 — 控制者亲验（commit `be0f1af`，479 → **481 passed**）

**判定：两项全部 ADDRESSED；变异验收由控制者独立重跑，不采信实现者的表。**

亲验清单：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 改动面 | `git diff --name-only 1fa9941 be0f1af` | 只有两个守卫文件；`-- backend/app` 命中 **0** ✓；`228 insertions / 1 deletion`，那 1 处 deletion 就是 Ruling 42 的 `:167` 那一行 ✓ |
| 481 passed | `cd backend; python -m pytest -q` | **481 passed in 53.80s** ✓（479 + 2 条新测试，与预期逐字相符） |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **399 / Miss 0 / 114 / BrPart 0 / 100%** ✓；`480 passed, 1 skipped` ✓ |
| Ruling 42 | 读 `:167-172` | 已改成「`_is_allowed` 的第一支正是 `module == ALLOWED_PACKAGE`——**命中的是「相等」这一支，不是 `startswith(ALLOWED_PACKAGE + ".")` 那一支**」，并把两个实跑值印在旁边（与控制者 V1 亲跑逐字相符）✓；grep 确认另外两处「白名单前缀 `app.domain.`」（`:139` / `:360`，说的是 `app.domain.seed.generate`，本来就对）**未被误伤** ✓ |
| Ruling 46 判据锚 | 读新测试源码 | **一个折算结果都没写死**：每格现场调 `resolve_name("."*level + (module or name), ".".join(package))`，抛 `ImportError` 的那档期望 `None`；11 格矩阵（我给的是 9 个形状，它另加 2 格），并**同时断言折算串与红/绿判定两件事** ✓ |
| 红绿双档（硬规矩 #50） | 读矩阵 | **layering 侧** 红档 8 格 + 绿档 3 格（`level == 1` 包内导入 ×2、`app.db.seed` ×1）；**purity 侧** 红档 9 格 + 绿档 2 格（`app.db.seed` 在白名单外 → RED）。**（时点绑定：这是 `be0f1af` 上的 11 格矩阵；fix round 5 各加一格 Task 2 形状后，`7b84599` 上是 purity RED 9 / GREEN 3、layering RED 8 / GREEN 4 —— Ruling 87。）**⚠️ 此处原写「红档 8 + 绿档 3」而**未标主语**，违反同一轮立起来的硬规矩 #56（控制者错误 #84、Ruling 73、硬规矩 #58）✓ |
| 两份独立（硬规矩 #51） | 控制者亲跑变异，见下表 | ✓ |
| 守不住什么（硬规矩 #39） | 读 docstring | 明写三条：`_package_of` 不在守卫范围（`package` 入参是手写的）、不扫真仓故 `FORBIDDEN_PREFIX` 取值不被它看着、矩阵有限 ✓ |

**控制者独立变异验收**（脚本 `.superpowers/sdd/_mut.py`，跑完删除；每次变异都在**剥 docstring 后的 `ast.dump`** 上确认「真的改了代码」，每次按**字节**还原并核 sha256，全程未用 `git checkout`/`git restore`；只跑那两条新测试）：

| 相位 | 结果 | 判读 |
| --- | --- | --- |
| **M0** 不变异（对照） | `2 passed` | 基线绿 ✓ |
| **M1** 语义等价改写 `package[: len(package) - (level - 1)]` → `package[: len(package) - level + 1]`（对照） | `2 passed` | **尺子不恒红** ✓ |
| **①** 删掉越界守卫 —— 只改 `test_layering.py` | `1 failed, 1 passed` | layering 红、**purity 仍绿** ✓ |
| **①** 删掉越界守卫 —— 只改 `test_domain_purity.py` | `1 failed, 1 passed` | purity 红、**layering 仍绿** ✓ |
| **②** `tail = module or name` → `tail = module` —— 只改 `test_layering.py` | `1 failed, 1 passed` | 同上 ✓ |
| **②** 同上 —— 只改 `test_domain_purity.py` | `1 failed, 1 passed` | 同上 ✓ |
| 收工 | sha256 全部还原 `True`、`git status --short` = `''`、HEAD = `be0f1af` | ✓ |

「只变异一份、另一份保持绿」是硬规矩 #51 的**正面证据**：两份 `_absolute` 互相独立，所以必须两份回归测试。**Ruling 46 指出的那个口子已被真正堵上**——实现者另在基线 `1fa9941` 上亲跑确认过「两份都删掉越界守卫 → 479 passed、退出码 0」，即那个口子在改前是真的。

**实现者报的 4 条，我逐条核实：3 条成立（含它自己判为「歧义不计入」的那条），1 条是它自己的预期错、已自纠。**

**Ruling 49（控制者错误 #73，接受）— 派单说「`task-1-brief.md` — Global Constraints 9 条」，实为 10 条。**

亲数：brief 与 `Document/` 计划文档同一节都是 **10 条**顶层 bullet。→ 连带查出**计划正文自己的一处不一致**，见 Ruling 53。

**Ruling 50（控制者错误 #74，接受）— 派单说「矩阵至少覆盖这 7 类」，而我实际枚举的是 5 个 bullet / 9 个具体形状。**

`1(level 0) + 1(level 1) + 1(offender) + 4(module 空) + 2(越界) = 9 个形状、5 组`。`7` 与 5、9 都不符；唯一说得通的读法是「前四个 bullet 的形状数 `1+1+1+4 = 7`」——**即我漏数了第五个 bullet 的 2 个越界形状，而那 2 个恰恰是 Ruling 35 的主角、也是变异 ① 唯一的抓手**。

**这与控制者错误 #67（Ruling 41）是同一形态：把一个清单的计数写错，而漏掉的正好是最要紧的那几项。** 因为派单写的是「至少」，判据仍可满足，实现者覆盖了全部 9 格 + 自选 2 格 = 11 格，未受影响。

**Ruling 51（控制者错误 #75，接受 —— 实现者判为「歧义、按 Ruling 45 口径不计入」，我不同意它的宽大）— 派单给两个文件指定了同一张矩阵，却写了一个只在一个文件里成立的判定。**

派单原文：「`("", 2, ("app","db","models"), "seed")` → `app.db.seed`（**判定仍绿**，折算串才是重点）」。亲验：`layering` 侧 `_is_forbidden("app.db.seed")` = False → **GREEN** ✓；`purity` 侧 `_is_allowed("app.db.seed")` = False（既不在 `ALLOWED_MODULES`、也不以 `app.domain` 开头）→ **RED**。**同一格在两个文件里判定相反**，而派单没标主语。

**为什么我不接受「不计入」**：Ruling 45 立的原则是「把不成立的指控认下来和把成立的指控辩掉是同一种失职」——**那条原则对控制者自己同样适用**。实现者对我宽大，不等于我就该对自己宽大；账本上的计数是用来找模式的，而这一条的模式很清楚：**我在 Ruling 41 里刚刚亲跑出这张红/绿表、并且专门更正过「三种形状全部假绿」，一轮之后又在派单里把同一件事写成不分文件的单值。** 这是复发，不是笔误。

实现者的处置是对的：两份矩阵的期望颜色列**不相同**，并在两个 docstring 里都写明了理由（`test_layering.py` 那段：「**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份回归测试的期望颜色列不相同，这不是抄错」）。

**Ruling 52（实现者自己的预期错，已由它自纠；记实现者错误 #2）**

它开工前判断「控制者给的公式 `resolve_name("."*level + …)` 对 `level == 0` 会抛异常、判据不可满足」，实测不成立：3.11.1 的 `resolve_name` 第一行是 `if not name.startswith('.'): return name`，故 level 0 档逐字相符、不需要特例。**它自己跑了一遍就纠正了，没有拿这个当成拒做理由**——这是硬规矩 #52 想要的行为。记入实现者错误计数（Plan01 Ruling 80 那次为 #1）。

**另记两处实现者的正面行为**（不是裁定，是要保留的做法）：
- 它第一版 commit `e647459` 里在新测试 docstring 写了「见任务报告 fix round 3」——**指针指向不入库的文件**，正是 Ruling 27 / 评审 M2 要消灭的形态。它自查后 `--amend` 成「写全复现命令 + 贴实跑的断言原文」。**这是本项目第一次由实现者自己抓出并修掉这一类错误。**
- 它记录了一个坑：`git show HEAD:<path>` 给的是 blob 的 **LF** 版本（`core.autocrlf=true`），与工作树的 CRLF 版差值恰等于 CRLF 行数（purity blob 36103 B vs 工作树 36666 B、差 563）。**拿它做「按字节还原」的判据必须先归一化。** 这是硬规矩 #46/#47 的一个新侧面，控制者亲验时也用了「按字节还原 + sha256」而不是 `git checkout`，两者相符。

**Ruling 53（计划正文缺陷，控制者自己改 —— `Document/` 对实现者是禁区）**

`Document/2026-10-06-实施计划02-智能处方引擎.md:13` 原写「本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划**最要命的六条**见 Global Constraints」，而该节实有 **10 条** bullet（控制者亲数）。这是 `e26347f` 就带进来的缺陷，`ad1d190` 那轮更正 14 处时**没有查到**（那轮查的是「计划对既有代码的断言」，没查「计划对自身章节的计数」）。已改为「十条」，并保持原行尾（CRLF 数不变）。

**→ 补硬规矩 #54：更正计划正文时，除了核「计划对既有代码的断言」，还要核「计划对自身结构的计数」（几条约束、几个 Task、几个 Step、几张表）。** 依据：Ruling 49/50/53 三条都是计数错，其中 #53 在库里躺了两轮没人查。**计数是最容易被读者当成事实、又最容易被作者随口写下的东西。**

**Ruling 54（C-fr3-1，接受，进 fix round 4）— `_package_of` 仍然没有回归测试，而它是两条守卫共同的假绿入口。**

新测试的 `package` 入参是**手写的四元组**，故 `_package_of` 被改坏时它照样全绿。而这正是 Ruling 37 那个攻击面：谁按错的举例去「对齐」`_package_of`（让它返回**模块路径**而不是**包**），`app/db/models/x.py` 里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed` 开头 → **守卫假绿、而全部 481 条测试仍然通过**。

实现者已按硬规矩 #39 把它写进两个 docstring 的「守不住什么」段——**写清边界是对的，但这一条边界太便宜就能推掉**：`_package_of` 是纯路径运算（`py.relative_to(BACKEND).with_suffix("").parts[:-1]`，不碰文件系统），断言它只要几行，且**可以塞进已有的那条新测试里、不改变 passed 数**。→ **进 fix round 4**。

**Ruling 55（C-fr3-2，接受，进 fix round 4）— `test_domain_purity.py` 模块 docstring 说「三条守卫」，而文件里现在有 4 个 `test_*`。**

新增那条是**辅助函数的单元测试**、不是第四条架构守卫，所以「三条守卫」在语义上不算错；但**读者会去数 `test_*` 的个数**，数出 4 就会怀疑 docstring。一句话交代清楚即可。

**Ruling 56（C-fr3-3，不接受本轮做，转 Task 2）— 11 格矩阵是手写的，形状不会自动跟进。**

实现者建议 Task 2 落地后评估改成「扫真仓所有 `ImportFrom` 逐个对拍 `resolve_name`」，那会顺带解决 Ruling 54。**方向正确、但本轮不做**：Task 2 会新建 `app/domain/prescription/` 子包，届时 `level == 2` 的**合法**相对导入开始真实出现，正是把矩阵换成全仓扫描的最佳时机（那时才有足够的真实形状可扫）。→ 记进 Task 2 的预检清单。

**Ruling 57（`import importlib.util` 写在函数体内，维持不动）**

实现者问是否该按惯例挪到模块顶部。**裁定：维持。** 理由：本轮的改动面被钉死在「新增这一条测试函数」之内，正是为了让「除新增函数外与基线逐字相同」这个自证可以用 AST 逐顶层单元比对一步做完；挪到模块级会动 `<module-level>`，自证口径要跟着放宽，而收益只是风格。`importlib.util` 是标准库、导入成本可忽略。**但它须在 docstring 里写明这是为了改动面自证而做的取舍**（实现者已经写了：「模块级 import 会改动本文件的 `<module-level>`，而本轮的改动面被钉死在『新增这一条测试函数』之内」）✓。

**控制者错误计数（Plan 02 Task 1）**：#61–#66（预检/实现/评审）、#67（Ruling 41）、#68–#72（fix round 2 及其亲验）、**#73/#74/#75（本轮 Ruling 49/50/51）** = **15 次**。Plan 01 为 60 次，**合计 75 次**。实现者 **2** 次（Plan01 Ruling 80、本轮 Ruling 52，两次都自纠）。评审者 2 次。复审者 1 次（Ruling 36 的「三种形状全部假绿」，已由 Ruling 41 更正）。

Task 1: fix round 3/5 完成并亲验（2/2 ADDRESSED，481 passed，domain 100%，控制者独立跑完 6 相位变异），fix round 4/5 派发中（Ruling 54 的 `_package_of` 回归断言 + Ruling 55 的「三条守卫」计数），基线 `be0f1af`、481 passed。

> **编号勘误（Ruling 58）**：本账本的裁定编号在 **47 → 49** 之间**跳过了 48**，即 **`Ruling 48` 号未使用**。fix round 4 的派单因此写错成「读 Ruling 48–57」。**编号 48 永久留空，不得回填**（回填会让已提交的报告与账本对不上）。

#### Task 1 fix round 4 — 控制者亲验（commit `6784d57`，**481 passed 不变**）

**判定：两项全部 ADDRESSED；变异验收由控制者独立重跑（「5 相位」：M0 / M1 / 只改 layering / 只改 purity / 两份都改。⚠️ 此处原写「8 相位」，那是「实现者」报告里的数字，被控制者抄来描述自己的运行——控制者错误 #83、Ruling 72、硬规矩 #60），不采信实现者的表。**实现者报出 6 条控制者错误，逐条核实后 6 条全部成立。**

亲验清单：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 改动面 | `git diff --name-only 73313f7 6784d57` / `-- backend/app` | 只有两个守卫文件；`backend/app/**` 命中 **0** ✓；`131 insertions / 14 deletions` |
| 481 passed | `cd backend; python -m pytest -q` | **481 passed in 104.58s** ✓（**passed 数与基线逐字相同**，本轮未新增测试函数，符合派单要求） |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **399 / Miss 0 / 114 / BrPart 0 / 100%** ✓；`480 passed, 1 skipped` ✓ |
| Ruling 55 | grep 计数陈述 | 已改（实现者另报 `test_layering.py` 无同类问题） |
| Ruling 54 断言 | 读新断言段 + 独立变异，见下表 | ✓ |

**控制者独立变异验收**（脚本 `.superpowers/sdd/_mut.py`，跑完删除；每次变异在**剥 docstring 后的 `ast.dump`** 上确认真的改了代码；按**字节**还原并核 sha256；全程未用 `git checkout`/`git restore`；只跑那两条测试）：

| 相位 | 结果 | 判读 |
| --- | --- | --- |
| **M0** 不变异（对照） | `2 passed` | 基线绿 ✓ |
| **M1** 语义等价改写 `parts[:-1]` → `tuple(list(parts)[: len(parts) - 1])`（对照） | `2 passed` | **尺子不恒红** ✓ |
| `parts[:-1]` → `parts`，**只改 `test_layering.py`** | `1 failed, 1 passed` | layering 红、**purity 仍绿** ✓ |
| `parts[:-1]` → `parts`，**只改 `test_domain_purity.py`** | `1 failed, 1 passed` | purity 红、**layering 仍绿** ✓ |
| 两份都改 | `2 failed` | ✓ |
| 收工 | sha256 全部还原 `True`、`git status --short` = `''`、HEAD = `6784d57` | ✓ |

**Ruling 54 指出的口子已堵上。** 实现者另在**基线 `be0f1af`** 上亲跑确认「两份都变异 → 全量 481 passed、退出码 0」，即改前那个口子是真的（与 Ruling 46 的取证方式一致）。

---

**实现者报的 6 条控制者错误，我逐条亲验，6 条全部成立。这是本项目单轮被抓最多的一次。**

**Ruling 59（控制者错误 #76）— 派单让人读「Ruling 48–57」，而账本里没有 Ruling 48。**

亲验：grep 全账本，`Ruling 47` 在 `:505`、`Ruling 49` 在 `:558`，**中间没有 48**。`Ruling 48` 在整个 sdd 目录里只有 1 处命中，是 **Plan 01 账本**的。根因：我在写 fix round 3 那节时，上一条是 Ruling 47，我却从 49 起编（大概是被「#48 = 硬规矩 #48」串了号）。→ 已加编号勘误（Ruling 58），**48 永久留空**。

**Ruling 60（控制者错误 #77）— 派单说「`package` 入参是手写的四元组」，实测没有四元组。**

亲验（AST 抽 `cases`）：两个文件各 **11 行 × 5 元**（`(module, level, package, name, 期望颜色)`）；`package` 自身的长度分布 purity `{2: 9, 3: 2}`、layering `{2: 7, 3: 4}`。**「四元组」两个读法都不成立**：整行是 5 元，`package` 是 2 或 3 元。根因：我把「`_absolute` 有 4 个入参」写成了「`package` 是四元组」。

**Ruling 61（控制者错误 #78，⚠️ Ruling 51 的同型复发）— 我又把一个只在 layering 成立的后果写给了两个文件。**

派单原文：「谁按错的举例去『对齐』`_package_of`……`app/db/models/x.py` 里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed` 开头 → **守卫假绿**」。亲验：

```
layering  _is_forbidden('app.db.seed') = False  -> GREEN（假绿）  ✓ 后果成立
purity    _is_allowed('app.db.seed')   = False  -> RED            ✗ 后果不成立
purity    DOMAIN = .../backend/app/domain       -> 根本不扫 app/db
layering  SCANNED_DIRS = ('pipeline', 'db', 'domain')
```

**这是 Ruling 51（控制者错误 #75）的完全同型复发，中间只隔一轮。** 而 Ruling 51 那一条我写得非常重（「这是复发，不是笔误」），并且**实现者在两个 docstring 里都写明了「两份的期望颜色列不相同，这不是抄错」**——也就是说，**正确的区分就印在我刚读过的文件里，我在下一轮派单时又把它们合回了一句**。

**→ 升级为硬规矩 #56（见下）。两轮内同型复发，就不该再靠「下次注意」。**

**Ruling 62（控制者错误 #79）— 派单让人在 Plan 02 账本里 grep 硬规矩 #30，那里 0 命中。**

亲验：#30 是 **Plan 01** 立的规矩，Plan 02 账本只在别处引用、没有定义行；有定义行的是 #32(`:467`)、#35(`:261`)、#39、#42、#48–#54。**与 Ruling 44（控制者错误 #70：把 #50 指到阅读范围之外）同型**——都是「把读者指向一个东西不在的地方」。**→ 并入硬规矩 #55。**

**Ruling 63（控制者错误 #80，⚠️ 这条错在账本里，是我上一轮的裁定）— Ruling 42 判定「`:139` 是正确的」不成立。**

Ruling 42 里我写：「`:139` 与 `:246` 说的是 `app.domain.seed.generate`，`startswith` 确实为 True，是正确的——不要动它们」。亲验：

```
_absolute("seed", 2, ("app","domain","ind"), "generate")  = 'app.domain.seed'          ← 两份都是这个
resolve_name("..seed.generate", "app.domain.ind")         = 'app.domain.seed.generate'
```

`_absolute` **只折 `module`**；`generate` 住在 `node.names` 里、只有 `module` 为空时才接上去（这正是 Ruling 36 的修法）。所以老 `:139` 那句「就会**折成** `app.domain.seed.generate`」是错的，应为 `app.domain.seed`。

**我的错在哪**：我只核了「`app.domain.seed.generate` 这个串是否命中 `app.domain.` 前缀」（是），**没有核「`_absolute` 对这个输入是否真产出这个串」**（不是）。**这与控制者错误 #67 是同一形态：核了推论、没核推论的输入。**

**关键在动词**（实现者的区分，我采纳）：老 `:139` 用「**折成**」→ 错；老 `:246`（今 `:422`）用「**解析到**」→ 对（`resolve_name("..seed.generate", "app.domain.sub")` 实跑就是 `app.domain.seed.generate`）。**结论（假绿）在两种读法下都成立**，因为 `app.domain.seed` 同样以 `app.domain.` 开头——所以这不是一个会造成错误行为的 bug，但它是**印在一份自称是「规格说明」的 docstring 里的错值**，而那份 docstring 的全部价值就在于精确。

实现者已就近更正 `:142-145`（写明「**不是** `app.domain.seed.generate`：`generate` 住在 `node.names`」并贴了两个实跑值），控制者亲验其内容正确。

**→ 补硬规矩 #57（见下）。**

**Ruling 64（控制者错误 #81）— 「`Read` 工具行号系统性少 1」的量级写错了。**

实现者实测：偏移 **0**（`progress.md:172`/`:300`、`test_domain_purity.py`）与 **−1**（`progress.md:446`/`:450`/`:588`）**并存**，`test_layering.py` 两个区段是 **−2**；且**同一行内容两次调用分别被标 449 和 450**（python 说 450）→ **`Read` 对自己都不自洽**。另 `Read` 报 `task-1-report.md` 只有 1031 行（实为 2616 LF 行）。

**「系统性少 1」暗示一个可以补偿的固定偏移，而实测是不可预测的**——所以结论（**一律取 shell 口径**，硬规矩 #30）不但成立、而且**理由比原来更硬**。这句话同时印在 `task-1-brief.md` 第 6 条与 `Document/2026-10-06-实施计划02-智能处方引擎.md:24`，两处都是控制者写的、都在实现者的禁区里。→ **控制者自己改计划正文**（同 Ruling 53 的处置）。

**Ruling 65（实现者判为「不计入」的 2 条，控制者同意不计入）**
- 派单 §3 用「**若**模块 docstring 算在 `<module-level>` 里」限定了，它只报实测答案（答：不算，因为尺子对 `ast.Module` 也剥 docstring）→ 不是错误。
- M1 对照的例子 `tuple(list(parts)[: len(parts) - 1])` 是**片段**、需先绑 `parts` 局部名，派单用「**例如**」限定过 → 不是错误。

**按 Ruling 45/51 的口径：不成立的指控不该认，成立的不该辩。这 2 条确实不成立。**

---

**补硬规矩 #55：引用裁定/硬规矩编号（尤其是区间）之前，必须 grep 确认区间内每个编号都真实存在于所指向的那份文件里。** 依据：Ruling 59（引用了不存在的 Ruling 48）、Ruling 62（把 Plan 01 的硬规矩 #30 指到 Plan 02 账本里）。**与 Ruling 44 同型：把读者指向一个东西不在的地方，比不给指引更糟——它会让人以为自己漏读了。**

**补硬规矩 #56：描述两个「相似但不同」的守卫（purity 的 allow-list / layering 的 deny-prefix，或任何一对）时，任何判定、颜色、后果都必须标主语；不得用一句话覆盖两者。** 依据：Ruling 51（控制者错误 #75）与 Ruling 61（#78）**两轮内同型复发**，而正确的区分当时就印在实现者刚写的 docstring 里。**复发即升级：这类错误不能靠「下次注意」，只能靠「每句都标主语」这个机械动作。**

**补硬规矩 #57：核一条 docstring 里的举例时，必须核「被测函数对这个输入是否真产出这个值」，不能只核「这个值是否满足后面那句结论」。** 依据：Ruling 63（控制者错误 #80）——`app.domain.seed.generate` 确实命中 `app.domain.` 前缀，但 `_absolute` 根本不产出它。**与控制者错误 #67 同型：核了推论、没核推论的输入。**

**Ruling 66（C-fr4-1 / C-fr4-3 / 编辑工具，处置）**
- **C-fr4-1**（`_package_of` 断言仍是手写 4 格，Task 2 建子包后没人会被提醒加行）→ **并入 Ruling 56，转 Task 2 预检清单**。采纳实现者的具体建议：**若 Task 2 不做全仓 `ImportFrom` 扫描，至少把 `_package_of` 的断言换成「扫真仓每个 `.py`，与 `py.relative_to(BACKEND).parent.parts` 对拍」**——那是非同源的、且深度自动跟进。
- **C-fr4-3**（同一段 50 行断言写了两份、只有 4 行不同；Plan 03 若加第三个守卫将变成 4 段 × 3 份 = 12 处同步）→ **不推翻 Ruling 33**，但**把这条量化记进 Plan 03 的预检清单**：Ruling 33 说的「维护成本极低」在 Plan 02 内已被 Ruling 35/36（bug 各两份）、Ruling 54（断言各两份）、本轮（50 行 ×2）三次证明**偏乐观**。
- **编辑工具静默失败 9 次**（工具/磁盘分歧家族第 **48–56** 次）→ **新形态，必须记**：8 次 `SearchReplace` 报 success **并打印了正确的 diff**、磁盘 0 生效；1 次整文件 `Write` 报 success **并把新内容用 `cat -n` 全篇回显**、磁盘仍是旧内容（sha256 未变）。**此前记录的形态是「报成功但不回显」，本轮证明它会连 diff 和整篇回显一起伪造。** 实现者的处置（守卫文件只用 python 按字节写 + 落盘闸门：13 个新串全命中 / 6 个旧串 0 残留）是对的，**写进硬规矩 #48 的适用范围**：落盘闸门必须同时查「新串在」和「旧串不在」，只查其一会漏。

**控制者错误计数（Plan 02 Task 1）**：#61–#66（预检/实现/评审）、#67（R41）、#68–#72（fr2 及其亲验）、#73–#75（fr3）、**#76–#81（fr4，Ruling 59–64）** = **21 次**。Plan 01 为 60 次，**合计 81 次**。实现者 **2** 次（均自纠）。评审者 2 次。复审者 1 次。

**Task 1 结案状态**：fix round 4/5 完成并亲验（2/2 ADDRESSED、481 passed 不变、domain 100% 维持、控制者独立跑完 5 相位变异）。**尚未做全链路收尾评审**（`e26347f` → `6784d57`），派发中。

#### Task 1 收尾评审（fix 链 `ad1d190..6784d57`）— 控制者复核

**评审者结论：Approved with findings；Critical 0 / Important 2 / Minor 6；另报控制者错误 8 条（6 成立 / 1 歧义 / 1 不成立）。控制者亲验其最承重的 5 条，全部成立。**

评审包：`task-1-fixchain-review-package.md`（1308 行 / 90750 B，控制者用 python subprocess 生成）。评审报告：`task-1-fixchain-review.md`（64812 B / 865 LF 行，sha256[:16] `9e5c0efde5cbecb8`）。

**评审者的取证方式值得单独记**（这是本项目第一次评审者把控制者的 harness 陷阱写成可复现的对照）：
- 它**在两个历史基线上复跑到「改前口子是真的」**：`1fa9941` 上两份都删越界守卫 → 479 passed rc 0；`be0f1af` 上两份都改 `parts[:-1]` → `parts` → 481 passed rc 0。**即 Ruling 46/54 声称的漏洞被独立坐实，不是靠采信账本。**
- 它**自己搭合成树重跑了那张 14 行 × 3 列的探针表**（42 格，0 处不符），并且**主动补上了派单里漏掉的两项**（`BACKEND` 重定向 + 树里 ≥5 个 `.py`），补正前 14 行连同对照行全 RED——**它独立撞上了控制者错误 #71 的原型，并把它变成了 finding（Important #2）**。
- 它**不用实现者的 43 个探针脚本**，另写 13 个独立复现全部关键结论。
- 11 个变异相位全部在 `$env:TEMP` 的 backend 副本上做，**主工作树零写入**；两个守卫文件 sha256 前后逐字相同（`440f7167610df187` / `50d776680defc25e`）。

**控制者亲验（不采信评审报告）**：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| Important #1 前半 | AST 解析 `from ..indicators import X` + 调 `_package_of` / `_absolute` / `_is_allowed` | **`level=2`、`module='indicators'`**；`_package_of(app/domain/prescription/match.py)` = `('app','domain','prescription')`；折算 `'app.domain.indicators'`、`_is_allowed` = True、与 `resolve_name('..indicators','app.domain.prescription')` 相符。**故 `:232`「正是 `level == 1` 这一档」错（实为 level 2），而结论（放行/GREEN）对** ✓ |
| Important #1 后半 | AST 抽 purity 的 `cases` 矩阵逐格打印 | **`(包深3, level2, GREEN)` = 0 格**；11 格里 GREEN 只有 2 格、都在包深 2 / level 1。**硬规矩 #50 的「绿档取自下一个 Task」在 purity 侧只是名义满足** ✓ |
| Important #2 | 读 `:523-525` + 自己上一轮的亲历 | 配方确实漏了 `BACKEND` 重定向与「≥5 个 `.py`」；控制者错误 #71 就是照字面做而全 RED 的 ✓ |
| CE-1 | `git diff --name-status ad1d190 6784d57` | **8 个文件**，含生产代码 `backend/app/config.py`（+10/−1）、**新建** `backend/tests/test_config.py`（30 行）、`backend/tests/pipeline/test_daily.py`（+9/−4）；`daily.py` 是 **+28/−4**、`test_models.py` **+95/−4**。派单只列了 4 个 ✓ |
| CE-2 | grep「相位」 | `:610` 说 round 3 是 6 相位（**对**，控制者的表确有 6 行）、`:616` 说 round 4 是「8 相位」而**同节 `:630` 的表只有 5 行**、`:718` 又说「5 相位」✓ |
| CE-3 | grep「红档/绿档」+ AST 数两份矩阵 | `:538`「红档 8 格 + 绿档 3 格」**没标主语**；亲验 purity 是 **RED 9 / GREEN 2**、layering 是 **RED 8 / GREEN 3**——`:538` 说的是 layering ✓ |
| CE-5 | grep `C-fr1-` | `C-fr1-1/2/3/5/6` 各有处置（Ruling 29/30/31/34/33），**`C-fr1-4` 零命中** ✓ |

---

**Ruling 67（评审 Important #1，接受，进 fix round 5）— `test_domain_purity.py:230-232` 把 Task 2 的形状说成 `level == 1`，实为 `level == 2`；且 purity 矩阵里没有那一格绿档。**

原文：「**绿档同时在场**（硬规矩 #50…）：`level == 1` 的包内导入折成 `app.domain.tables`，必须仍被 `_is_allowed` 放行——Task 2 起 `app/domain/prescription/` 子包里的 `from ..indicators import X` 正是这一档。」

亲验：`from ..indicators import X` 的 AST 是 **`level=2`**（`app/domain/prescription/match.py` 的 `__package__` 是 `app.domain.prescription`，两个点才到 `app.domain`）。**结论对、档位错**——与 Ruling 42/63 完全同型（结论成立，中间的机制/值不成立）。

**更要紧的是后半**：purity 的 11 格矩阵里 **`(包深3, level2, GREEN)` 是 0 格**，也就是说**「Task 2 那个形状在 purity 侧是绿的」这件事，仓库里没有任何断言看着**。硬规矩 #50 要求「② 一个应当保持绿的合法输入」，而这一格恰恰是**下一个 Task 第一天就会写出来的合法导入**。

**修法（两条都要）**：① 把 `level == 1` 改成 `level == 2` 并写清为什么（包深 3 → 两个点到 `app.domain`）；② **往 purity 的 `cases` 里加一格** `("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")`，并在注释里写明这是 Task 2 的形状。**layering 侧同形状是 GREEN 还是 RED 要先实跑再写**（`_is_forbidden('app.domain.indicators')` 显然为 False → GREEN，但按硬规矩 #56 **必须标主语**，不许一句覆盖两边）。

**Ruling 68（评审 Important #2，接受，进 fix round 5）— `test_domain_purity.py:523-525` 印的合成树配方不可照做。**

漏了两项：**`BACKEND` 也要重定向**（`_package_of` 里是 `py.relative_to(BACKEND)`，只改 `DOMAIN` 会抛 `ValueError`）、**树里要有 ≥5 个 `.py`**（`_assert_not_empty` 的空转守卫）。照字面做的结果是**14 行连同干净对照行全 RED**——这正是控制者错误 #71 的现场。

**为什么判 Important 而不是 Minor**：这段是印在源码里的**复现配方**，它的价值全在「能被照做」。一个照做就得到全红的配方，比没有配方更糟：它会让下一个人以为守卫坏了，或者以为那张 14 行的表是假的。**评审者补正后 42 格全部复现、0 处不符**，所以表本身是对的，坏的只是配方。

**修法**：把两项补进配方，并**加一句「必须先跑一行已知 GREEN 的干净对照，否则全红不可解释」**（硬规矩 #53 的正面表述）。`test_layering.py:145` 已经把 `BACKEND` 写进配方了——**两份不一致，以完整的那份为准对齐**。

**Ruling 69（评审 6 条 Minor 的处置）**
1. `purity:209`/`layering:197`「两个 bug」下面列 **3** 个 bullet、同段又说「三条」「三种」→ **修**（与 Ruling 55 同类：计数与实际不符）。
2. `purity:210`/`layering:198`「479 条全绿」**无 commit 绑定**；评审者在 HEAD 上照字面跑得到 `2 failed, 479 passed`（因为现在有 481 条）→ **修**：绑到 `be0f1af^`（或写「fix round 2 之前」）。同文件 `:360` 故意不写死数字，是正确样板。
3. fix 链新增散文里「本轮」**11 处只有 1 处绑轮次**（`test_models.py:612` 是仓内正确样板）→ **修**：全部绑成「fix round N」。理由：这个文件已经被四轮改过，「本轮」在读者手里是**歧义指代**。
4. `test_models.py:612-613`「两条查询计划**逐字复现**」，实测 detail 前还有 `SEARCH stratification_result `，表里 `:596-597` 只印了尾部 → **修**：改成「尾部逐字复现（表里只印了 `USING COVERING INDEX …` 那一段）」或补全。**「逐字」是个强断言，不能用在截断过的引文上。**
5. `daily.py:226/:228` 两个「均值」是**截断值**（`21.035` 的 `round()` 是 `21.04`），标签未写舍入口径 → **修**：标「截断到百分位」。`+0.37 s / +1.8% / 2.83×` 评审者核过全部自洽，不用动。
6. `purity:146`「**守卫当场假绿**」缺主语（layering 对应句 `:93` 写的是「**本守卫**」）→ **修**（硬规矩 #56）。评审者已实跑两份结论都为真，故不是事实错误、只是主语纪律。

**Ruling 70（CE-5 的补处置）— `C-fr1-4` 在账本里从来没有处置行。**

`C-fr1-1/2/3/5/6` 分别对应 Ruling 29/30/31/34/33，**`C-fr1-4` grep 零命中**。它就是「`Read` 工具行号系统性少 1」那条归纳——而评审者抽验 `progress.md:444-453` 的偏移是 **0**，fix round 4 的实现者又量出 0 / −1 / −2 并存。**所以它当时就该被判「归纳不成立」**，却既没修也没记延后，**静默消失了三轮**。

**这正是我在评审派单 §B 里点名要评审者去找的形态（「有没有哪条 finding 在后续轮次里被悄悄丢掉」），而它就在我的账本里。** → **补处置：`C-fr1-4` 判「归纳不成立」，其正确版本已由 Ruling 64 落进计划正文（`ef48d33`）。**

**Ruling 71（CE-1，控制者错误 #82，本轮最重）— 派单说 fix 链改了 4 个文件，实为 8 个，含生产代码与一个新建测试文件；而我生成的评审包里有一节标题写着「生产代码命中（**必须为空**）」，底下就印着两行。**

亲验 `git diff --name-status ad1d190 6784d57`：

```
M  Document/2026-10-06-实施计划02-智能处方引擎.md          1/1
M  backend/app/config.py                                  10/1     ← 生产代码
M  backend/app/pipeline/daily.py                          28/4     ← 不是「仅 :226 一处」
M  backend/tests/architecture/test_domain_purity.py      403/29
M  backend/tests/architecture/test_layering.py           287/12
M  backend/tests/db/test_models.py                        95/4
M  backend/tests/pipeline/test_daily.py                    9/4     ← 派单未列
A  backend/tests/test_config.py                           30/0     ← 新建，派单未列
```

**根因有两层，第二层更严重**：
1. 我把「round 2–4 改的文件」当成了「整个 fix 链改的文件」——round 1（`6a2938f`）动过 `config.py` / `test_daily.py` 并新建了 `test_config.py`。
2. **我写评审包生成脚本时，给一节起标题叫「生产代码命中（必须为空）」，然后没有看它的输出就发出了派单。** 它印的是 `backend/app/config.py` 与 `backend/app/pipeline/daily.py` 两行。**这是「写下一个断言、不验证它」的第 4 次发生**（#67 核推论不核输入、#80 同类、#83 见下）。

**改动本身是被授权的**（`config.py` 与 `test_daily.py` 是 Ruling 27-M1/M7 的产物，`test_config.py` 是 Ruling 26 要求的非同源断言），所以**这是转述错误、不是实现者越界**。评审者的判法（「包自洽、派单转述不自洽」）准确。

**→ 补硬规矩 #59：生成任何带断言性标题的产物（「必须为空」「应当只有 N 项」「与基线逐字相同」）之后，必须亲眼看一遍它的实际输出，才能把它交给别人。** 依据：CE-1 / 控制者错误 #82。

**Ruling 72（CE-2，控制者错误 #83）— 账本 `:616` 写「控制者独立重跑（8 相位）」，而同一节 `:630` 的表只有 5 行、`:718` 自己也写「5 相位」。**

「8 相位」是**实现者报告里的数字**（它跑了 M0/M1/①/②/M4/M5/M6 等）。我把它抄来描述**我自己**的运行。**这与 Plan 01 的控制者错误 #37（Ruling 158：把别人的 grep 结果写成「控制者亲跑」）是同一形态的第二次发生**——那次我把它定为「最严重的新形态：把二手证据洗成一手证据」。

**→ 已就地更正为 5 相位（见下）。并补硬规矩 #60：凡是写「控制者亲跑 / 亲验」的地方，数字与清单必须来自控制者自己的那次运行；引用实现者或评审者的运行结果时必须写明是谁跑的。** 依据：#37（Plan01）与 #83（本轮）两次同型。

**Ruling 73（CE-3，控制者错误 #84，⚠️ 硬规矩 #56 在立它的同一轮被违反）— 账本 `:538`「红档 8 格 + 绿档 3 格」没标主语。**

亲验：purity 是 **RED 9 / GREEN 2**、layering 是 **RED 8 / GREEN 3**，`:538` 说的是 layering。**而硬规矩 #56（「描述两个相似但不同的守卫时，任何判定、颜色、后果都必须标主语」）正是我在同一轮（fix round 4 的账本节）里立起来的**，立它的依据是 Ruling 51/61 两轮内同型复发。**立完当场又犯。**

**→ 补硬规矩 #58：新立一条硬规矩时，必须回头把「本轮已经写下的内容」按新规矩重查一遍——立规矩的那一轮，恰恰是它最可能被违反的一轮（因为规矩是从这一轮的错误里长出来的，而这一轮的其余文字是在意识到错误之前写的）。** 依据：CE-3 / 控制者错误 #84（#56 当轮违反）、CE-8 / #88（#55 当轮违反）。

**Ruling 74（CE-8，控制者错误 #85，⚠️ 硬规矩 #55 在派单里被引用的同一句话里被违反）— 派单让评审者在 Plan 02 账本里读 19 条硬规矩的定义行，那里只有 #48–#57 共 10 条。**

`#19/#29/#30/#32/#35/#39/#42/#43/#44/#46/#47` 的定义行都在 **Plan 01 账本**里。**而 Ruling 62（控制者错误 #79）就是同一件事**（让人在 Plan 02 账本 grep #30，0 命中），我为它立了**硬规矩 #55**（「引用编号前必须 grep 确认它存在于所指向的那份文件里」），**并在同一份派单里要求评审者去读 #55**。

**→ 这是 #55 与 #56 双双「当轮违反」，故 Ruling 73 立的 #58 不是事后总结、是本轮的第二次实证。** 修法：往后的派单一律写明「Plan 01 的硬规矩 #1–#47 在 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`；Plan 02 的 #48 起在本账本」。

**Ruling 75（CE-4 / CE-6 / CE-7 的处置）**
- **CE-4（#86，成立）**：计划正文 `:24` 印了「`task-1-report.md` … 实为 2616 个 LF 行」，评审时该文件已是 **3298 行**。**2616 在落笔当时为真**（round-4 那节正从第 2618 行起），但**印进入库文件且未绑时点**就成了会过期的量。→ **控制者已自己改**（绑成「fix round 4 落笔当时」并明写「该文件持续增长，这是一时点样本、不是稳定量」）。**这与硬规矩 #19「凡写下测量条件，必须同时写哪条测试会在它失效时变红；写不出来就标『历史实测，不被守卫』」是同一条纪律，只是对象从代码散文换到了计划正文。**
- **CE-6（#87，歧义但接受）**：commit `6a2938f` 写「4 条 Important **散文**错误 + …相对导入放行」，而 I1 是守卫口径不是散文（散文只有 I2–I4 三条）；`1fa9941` 写「**4 处**散文错误」，而账本派单清单是 R37/R38 + Minor 1–4 = **6 处**（按 Ruling 计是 2 处）。**「4」与两种数法都不符。** commit message 不可改写（已推送的历史不改），故**只记账本、不改历史**。
- **CE-7（不成立，正面确认）**：评审包本身无错——「1308 行 / 90750 B」逐字相符，包内 `## git diff -U10` 那 1251 行与 `git diff -U10 ad1d190..6784d57` 实跑输出**逐行相等**。**评审者主动做了一次「对控制者产物的正面确认」，这在本项目是第一次**，值得保留为做法。

**Ruling 76（评审者 7 条「不可复核项」的处置）**
① `daily.py:226-228` 四个整学期回放墙钟样本（脚本不在库内、需建 worktree）→ **接受为不可复核**；算术部分评审者已核自洽，且源码已标「历史实测，不被守卫」✓
② `test_models.py:596-597` 墙钟中位与 min…max → **接受**；评审者另给两个独立样本 `B/A = 1.040` 与 `4.054`，**支持**源码那句自我撤回（方向不可复现）
③ `test_models.py:614` 四次 B/A 序列 → **接受为历史样本**
④ 计划正文 `:24` 的 Read 偏移「0/−1/−2 并存」「同一行两次标 449/450」→ 评审者只抽验到偏移 **0**。**处置：保留原陈述但它是实现者的实测、不是控制者的**，故按计划正文口径应标来源。→ **并入 Ruling 75 的 CE-4 修法，已在 `:24` 写明是 fix round 4 的实测。**
⑤ `purity:392` 终审 A 的「14 种写法」→ 源码已诚实标注「本轮没有逐条复跑」✓ **符合硬规矩 #39，不动**
⑥ 实现者 fr2/fr3/fr4 的 43 个探针脚本 → 评审者用自己另写的 13 个独立复现，**不依赖** ✓
⑦ A/B 对照的数据同一性 → **接受为不可复核**

---

**本轮更正（控制者自己改，不经实现者）**
- 账本 `:616`「8 相位」→「**5 相位**」（Ruling 72）
- 账本 `:538`「红档 8 格 + 绿档 3 格」→ 补主语（Ruling 73）
- 账本补 `C-fr1-4` 的处置行（Ruling 70）
- 计划正文 `:24` 的 2616 行绑时点（Ruling 75 / CE-4，commit 见下）

**转延后 Minor（收尾评审新增）**
- `Task 1: minor (deferred): 评审 CE-6 —— commit 6a2938f/1fa9941 的 message 里「4 条散文错误」与实际清单不符（Ruling 75，已推送历史不改）`
- `Task 1: minor (deferred): _package_of 的断言仍是手写 4 格；Task 2 若不做全仓 ImportFrom 扫描，至少换成「扫真仓每个 .py 与 py.relative_to(BACKEND).parent.parts 对拍」（Ruling 66 / C-fr4-1）`
- `Task 1: minor (deferred): 同一段 50 行断言在两个守卫文件里各一份、只有 4 行不同；Plan 03 若加第三个守卫将变成 4 段 × 3 份 = 12 处同步（C-fr4-3，Ruling 33 的三个理由仍成立但该量化记入 Plan 03 预检）`

**控制者错误计数（Plan 02 Task 1）**：#61–#66、#67、#68–#72、#73–#75、#76–#81、**#82–#88（本轮 Ruling 71/72/73/74/75 的 CE-1/2/3/4/6/8 + CE-5 的账本漏处置）** = **28 次**。Plan 01 为 60 次，**合计 88 次**。实现者 2 次（均自纠）。评审者 2 次（均在 Plan 01 终审）。复审者 1 次。**本次收尾评审者 0 次，并主动做了 1 次对控制者产物的正面确认。**

**补硬规矩 #58 / #59 / #60**（定义见 Ruling 73 / 71 / 72）。

Task 1: 收尾评审完成（Approved with findings，0 Critical / 2 Important / 6 Minor），控制者亲验其 5 条最承重项全部成立；**fix round 5/5（最后一轮）派发中**（Ruling 67/68 + Minor 1–6），基线 `6784d57`、481 passed。

#### Task 1 fix round 5 — 控制者亲验（commit `7b84599`，**481 passed 不变**）→ **Task 1 结案**

**判定：2 条 Important + 6 条 Minor 中，7 条完全落地、1 条（Minor 3）被派单自己的禁区挡住 10/11；控制者亲跑变异对，独立坐实「新加那一格是承重的」。**

亲验清单：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 改动面 | `git diff --name-status d00533c 7b84599` | 4 个文件；`-- backend/app` **只有 `daily.py`** ✓；`daily.py` 的 diff 逐行看过，**纯散文、代码 0 字节改动** ✓ |
| 481 passed | `cd backend; python -m pytest -q` | **481 passed in 54.73s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **399 / Miss 0 / 114 / BrPart 0 / 100%**、`480 passed, 1 skipped` ✓ |
| Minor 5 的两个截断值 | 自己跑 `round()` | `round(20.665, 2)` = **20.66**、`round(21.035, 2)` = **21.04** ✓ —— 实现者印进 `daily.py:226/:228` 的「真值 20.665，`round(_,2)` 同为 20.66」与「真值 21.035，`round(_,2)` 会给 21.04」**两个都对** |
| Ruling 67-② 的格数 | AST 抽两份 `cases` 逐格数 | **purity 12 格：RED 9 / GREEN 3**；**layering 12 格：RED 8 / GREEN 4**；两份各命中新格 1 次 ✓ |

**控制者独立变异对**（脚本 `.superpowers/sdd/_mut.py`，跑完删除；每次变异在剥 docstring 的 `ast.dump` 上确认真的改了代码；按字节还原 + 核 sha256）：

| 相位 | 结果 | 判读 |
| --- | --- | --- |
| **M0** 不变异 | `2 passed` | 基线绿 ✓ |
| **M5** 定向变异（只折错「level 2 + 包深 3 + `module` 与 `name` 都非空」这一档），两份都改，**保留新格** | `2 failed` | 新格抓住了 ✓ |
| **M6** = M5 但**删掉新格** | **`2 passed`** | **改前 11 格矩阵下这个变异完全静默 → 新加那一格是承重的** ✓ |
| **M7** = M5 但只改 purity | `1 failed, 1 passed` | 两份独立 ✓ |
| 收工 | sha256 全部还原 `True`、`git status --short` = `''`、HEAD = `7b84599` | ✓ |

**M5→M6 这一对是本轮最要紧的证据**，控制者独立复现，不采信实现者的表。它证明 Ruling 67-② 加的那一格**不是装饰**：`_absolute` 在「Task 2 第一天就会写出来的那个合法导入形状」上折错时，**只有这一格会红**。

---

**Ruling 79（CE-fr5-3，控制者错误 #90，成立 —— 派单内部自相矛盾）— Minor 3 要求「全部绑轮次」，§3 禁区又写「`daily.py` 只许动 Minor 5 那两个散文标签」，`daily.py:206` 不能同时满足。**

实现者的处置**完全正确**：服从禁区、未动、在报告里给出待打的一行补丁并请裁定。**这正是派单里第 10 条要求的行为**（「发现任何一条验收判据按字面不可满足，停下来写明并给出实测证据，不要为了符合派单而造假或空跑」）。

**控制者裁定并自己执行**：授权该处改动。亲跑 `git log --oneline -S"本轮亲跑：内存库" -- backend/app/pipeline/daily.py` → **`6a2938f`**，即那句话出自 **fix round 1**。已改成「（Plan 02 Task 1 fix round 1 亲跑，commit `6a2938f`：内存库，…）」。**不开第 6 轮**（SDD 上限 5 轮，且这是纯散文绑定，控制者自己动手比派一轮更省）。

**亲验剩余量**：`git diff ad1d190 7b84599 -- backend` 的新增行里含「本轮」的只剩 **2 处**，其中 `test_models.py` 那处已绑成「本轮（Plan 02 Task 1 fix round 1）」（仓内正确样板），`daily.py:206` 这处由控制者补完 → **Minor 3 结案 11/11**。

**Ruling 80（CE-fr5-1，控制者错误 #89，成立，⚠️「把读者指向东西不在的地方」第 4 次发生）— 派单 §1 指的 `review_probes/` 路径不存在，且与 §0 自相矛盾。**

亲验：`.superpowers/sdd/review_probes/` **存在、28 个文件**；`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/review_probes/` **不存在**。而**同一份派单的 §0 写的是前者、§1 写的是后者**——自相矛盾。数量「15 个」也是错的（那是评审者返回消息里的数，控制者转写时既没核也没标来源，**同时违反硬规矩 #60**）。

**后果**：实现者找不到它，自己另写了 12 个探针，做完才撞见。**这是浪费，不是错误结论——但它是同型的第 4 次**：Ruling 44（#70，把硬规矩 #50 指到阅读范围外）、Ruling 62（#79，让人在 Plan 02 账本 grep Plan 01 的 #30）、Ruling 74（#85，让人在 Plan 02 账本读 19 条只存在 10 条的规矩）、本轮（#89）。

**→ 补硬规矩 #61：派单里出现的每一个路径、每一个文件名、每一个数量，必须在发出前用 shell 亲验存在性与实际值；从别人（实现者/评审者）返回消息里转写来的数量必须标来源。** 依据：#89 与硬规矩 #55 已立而四度复发——**#55 只覆盖「编号」，#61 把它扩到「一切指代」**。

**Ruling 81（CE-fr5-2，控制者错误 #91，成立）— 派单说「本轮」11 处只有 1 处绑轮次，实测是 12 处出现 / 1 处已绑 / **11 处未绑**。**

「11 处只有 1 处绑」这个读法把 11 当成了总数。**这个数字是从评审者报告 M-3 的标题转写来的，而评审报告 M-3 的标题与它自己正文的表（4+4+1+3 = 12）就自相矛盾**——控制者既没核评审者的表、也没自己 grep。**与 #83（Ruling 72：把实现者的「8 相位」抄成自己的）同型：转写别人的数字而不核。**

**Ruling 82（CE-fr5-4，控制者错误 #92，成立）— 派单说「前两个**才是** fix round 2 修的 bug，第三个是同一条 Ruling 36 的另一半」，而第三处同样落在 `1fa9941` 里。**

实现者用剥 docstring 的 AST 比 `1fa9941^` → `1fa9941` 证明「一名多条展开」（`_imported_modules`）与前两个 bug **在同一个 commit 里落地**。**「才是」这个词把第三个排除在 round 2 之外，是假的。** 派单同时写了「由你按实际语义定」，实现者据此写成「两个 bug（Ruling 35 / 36）/ 三条变异」并说明了 `2 ≠ 3` 的理由——**结果是对的，但那是靠实现者顶住了派单的错误措辞，不是靠派单**。

**Ruling 83（CE-fr5-6，接受为口径限定，不计错误）— 「`Ruling 48` 号未使用」应读作「没有定义行」。**

实现者的限定准确：正则能匹到 `48`（Ruling 59 的正文与编号勘误行在**谈论**这个空号），但标题级扫描确认 `**Ruling 47（` 在 `:509`、`**Ruling 49（` 在 `:562`、中间没有 `**Ruling 48（`。**账本勘误行的措辞（「编号在 47 → 49 之间跳过了 48，即 Ruling 48 号未使用」）本身已经说清了是编号层面的空缺，不改。**

**Ruling 84（CE-fr5-5 / 7 / 8 / 9 不成立，控制者同意 —— 其中 3 条是对控制者产物的正面确认）**

实现者主动核了控制者的四项产出并确认无误：① Ruling 67 里控制者自我标注「这是推算不是实跑」**符合硬规矩 #60**、且推算本身成立；② 两份账本体积 `805520 B` / `122548 B` ≈ 派单写的 806 KB / 123 KB（十进制）逐字相符；③ 三个 doc commit 的改动面各只有 `Document/…md` 一个文件、代码基线取 `6784d57` 正确；④ 派单 §1「#19–#47 在 Plan 01、#48–#60 在 Plan 02」**抽查 18 个编号全部相符**——**这正是 Ruling 74 要求的修法，本轮做到了**。

**这是本项目连续第二次由下游对控制者产物做正面确认**（上一次是收尾评审者的 CE-7）。**保留为做法：每轮实现者/评审者都应抽验控制者给出的路径、数量、基线，无论对错都要报。**

**Ruling 85（控制者错误 #93，本轮亲验阶段自己犯的，⚠️ harness 假信号的第三次）— 控制者把变异探针与覆盖率套件并行派发，覆盖率那次跑到了变异中途的文件，报出 `2 failed, 478 passed, 1 skipped`。**

失败的断言原文正是 M5 定向变异的特征串（`"'app.domain'，而 resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'"`）。**若没有重跑，控制者就会把一条假失败记成实现者的 regression。** 串行重跑后：`git status --short` 空、HEAD `7b84599`、**`480 passed, 1 skipped`、domain 100%**。

**这是「harness/流程产物差点变成假 finding」的第三次**：#71（只重定向 `DOMAIN` 没重定向 `BACKEND` → 14 行全 RED）、#72（3 个对照变异里 2 个无效 → `caught=False` 看着像尺子坏了）、本轮 #93（并行竞态 → 2 条假失败）。

**→ 补硬规矩 #62：变异探针与任何测试运行必须串行；不得与别的命令并行派发。任何一次「意外的红」都必须先排除 harness/竞态/工作树状态，再当成 finding。** 依据：#71 / #72 / #93。

**Ruling 86（实现者错误 #3）— 报告说探针留在 `.superpowers\sdd\2026-10-06-…\fr5_probes\`「与 fr2/fr3/fr4_probes 同规格」，实测 `fr5_probes` 在 `.superpowers\sdd\` 顶层，而 fr2/fr3/fr4 在工作区目录里。**

亲验：`.superpowers/sdd/` 下有 `fr5_probes` 与 `review_probes` 两个目录；`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/` 下有 `fr2_probes(11)` / `fr3_probes(11)` / `fr4_probes(21)`。**「同规格」不成立。** 两者都在 `.gitignore:10` 的 `.superpowers/` 内，**无入库风险**，故只记不改。

**Ruling 87（实现者关切 #2，接受）— 账本 Ruling 73 / CE-3 那两个矩阵颜色计数在加格后已过时。**

亲验（加格后）：**purity RED 9 / GREEN 3**（原记 9/2）、**layering RED 8 / GREEN 4**（原记 8/3）。→ **已在 Ruling 73 那行就地补时点绑定**（见本轮更正）。**这印证了硬规矩 #19 的必要性：任何写进账本的实测值都要绑 commit，否则下一轮就过时。**

**Ruling 88（实现者关切 #3/#4，处置）**
- **#3**（`cases` 矩阵仍是手写的；Task 2 建 `app/domain/prescription/` 后按 Ruling 66 换成「扫真仓每个 `.py` 与 `resolve_name` 对拍」可一次性解决 Ruling 54/56/67 三条）→ **采纳，写进 Task 2 预检清单的第一项**。这是本轮最有价值的前瞻建议：**它把三条分散的裁定收敛成一个结构性修法**。
- **#4**（两份 `test_absolute_folding_matches_resolve_name` 现在 purity 81 行 / layering 83 行，其中 11 行只差一个模块名）→ **不推翻 Ruling 33**，但把量化再记一次：Ruling 33 的「维护成本极低」在 Plan 02 内已被 **四次**证明偏乐观（Ruling 35/36 的 bug 各两份、Ruling 54 的断言各两份、round 4 的 50 行 ×2、本轮的 81/83 行 ×2）。**Plan 03 若加第三个架构守卫，必须先抽公共模块**——这条从「建议」升级为 **Plan 03 的硬前置**。

---

**本轮更正（控制者自己改，不经实现者）**
- `backend/app/pipeline/daily.py:206`「本轮亲跑」→「Plan 02 Task 1 fix round 1 亲跑，commit `6a2938f`」（Ruling 79；`daily.py` 代码 0 字节改动，纯 docstring）
- 账本 Ruling 73 那一行的矩阵颜色计数补时点绑定（Ruling 87）

**补硬规矩 #61 / #62**（定义见 Ruling 80 / 85）。

---

## ✅ Task 1 结案（架构债清偿）

**commit 链**：`1df5e8a`（主体）→ `ad1d190`（计划正文更正 14 处）→ `6a2938f`（fr1）→ `1fa9941`（fr2）→ `be0f1af`（fr3）→ `6784d57`（fr4）→ `7b84599`（fr5）+ 控制者的 4 个 doc commit（`73313f7` / `ef48d33` / `d00533c` / 本轮）。

**测试**：Plan 01 终态 **453** → Task 1 主体 **478** → fr2 **479** → fr3 **481** → fr4/fr5 **481 不变**。
**覆盖**：`app/domain/` **399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%**（Plan 01 终态是 392/112）。
**fix round**：**5/5，用满**。每轮都以控制者亲验结束，fr2/fr3/fr4/fr5 的变异验收全部由控制者独立重跑。

**Task 1 全程的评审/复审共发现**：任务评审 0 Critical / 4 Important / 7 Minor；fr1 复审新报 4 Important / 5 Minor；fr2–fr5 由控制者亲验新报 2 Important（收尾评审）+ 若干 Minor。**Critical 始终为 0**——架构债清偿没有引入行为缺陷，全部问题都是「印在源码里的陈述与实测不符」这一类。

**控制者错误**：Task 1 共 **28 + 5 = 33 次**（#61–#93），Plan 01 为 60 次，**合计 93 次**。实现者 **3** 次（均自纠或无入库风险）。评审者 2 次（均在 Plan 01 终审）。复审者 1 次。收尾评审者 **0** 次。

**新增硬规矩**：#48–#62（Plan 02 账本），其中本轮新增 **#58**（立新规矩的当轮必须回查本轮已写内容）、**#59**（带断言性标题的产物必须亲眼看输出才能交出去）、**#60**（「控制者亲跑」的数字必须来自控制者自己那次运行）、**#61**（派单里的路径/文件名/数量发出前必须 shell 亲验）、**#62**（变异探针与测试运行必须串行）。

**⚠️ 一个必须带进 Task 2 的观察**：#58 与 #61 都是从「**立了规矩的当轮就违反它**」长出来的——#56 在立它的那一轮被违反（Ruling 73）、#55 在引用它的那份派单里被违反（Ruling 74）、#60 在立它的下一轮被违反（Ruling 81）。**规矩的数量已经不是瓶颈，执行才是。** Task 2 的派单发出前，控制者要按 #55/#59/#61 逐条自查一遍，并把自查结果写进派单末尾。

Task 1 结案。Task 2（动作库：`exercise` 表 + `exercises.yaml` + `exercise_equivalence.yaml`）预检中，基线 `7b84599` + 控制者的 `daily.py:206` 散文绑定、481 passed。

---

### Task 2: 动作库 — 预检扫描（Pre-flight，控制者亲跑）

**基线**：`e09e5f6`（= `7b84599` + 控制者的 `daily.py:206` 散文绑定），481 passed，`app/domain/` 399/114/100%。
**方法**：按硬规矩 #49，逐条核「计划对既有代码与 spec 的每一项断言」，不只核计划内部自洽。全部证据来自控制者本机 shell 实跑（脚本 `.superpowers/sdd/_pf2*.py`，跑完删除）。

#### A. 计划文本需更正的事实（**10 处，其中 2 处 Critical**）

**P2-A1（Critical，已更正计划）— Step 5 的 seed 入口方案与 Global Constraint #10 及两道既有守卫直接冲突。**

原文：「seed 入口放 `app/seed/prescription.py`（新建），由 `seed_database` 调用」。亲验三条冲突：
1. **Global Constraint #10 原文**：「`app/seed/` 自 Plan 01 结案后重新冻结（Task 1 的依赖迁移会动它一次，见 Task 1 的解冻范围，**之后不再动**）」——Task 2 不在解冻范围内。
2. `seed_database` **确实存在**（`app/seed/generate.py:382`，`def seed_database(session: Session, cfg: SeedConfig) -> None`），而它的 docstring `:10` 明写「**只**写组织结构五张表」；`tests/seed/test_generate.py:491` 的 `test_seed_database_writes_only_organisation_tables_and_is_idempotent` 用 `:519` 的 `assert count == 0, f"{table} 不该由 seed_database 写入"` 把这句话变成了守卫。
3. `test_generate.py:483-488` 的 `ORGANISATION_TABLES`（5）+ `DATA_TABLES`（9）**恰好穷尽当前 14 张表**（亲验 `Base.metadata.tables` = 14，逐名相符：`body_composition` / `cleaning_log` / `course_section` / `daily_sync_run` / `derived_metrics` / `enrollment` / `fitness_test_batch` / `fitness_test_result` / `interest_survey` / `percentile_snapshot` / `semester` / `stratification_result` / `student` / `teacher`）。**这是一个没人写下来的隐性不变量**：加第 15 张表它就不再穷尽，而新表会静默落在分区之外——`seed_database` 越界写它也不会红。

**裁定**：不新建 `app/seed/prescription.py`、不改 `seed_database`；灌数据函数放 `app/refdata_prescription.py`，命名 `sync_exercises(session) -> int`（幂等 upsert、返回行数）。**并新增一道分区穷尽守卫**：`set(ORGANISATION_TABLES) | set(DATA_TABLES) | REFERENCE_TABLES == set(Base.metadata.tables)`，`REFERENCE_TABLES` 逐 Task 递增（T2 `exercise`；T3 `prescription_template`；T9 `prescription` + `weekly_adjustment`）。理由与完整原文已写进计划 Step 5。

**P2-A2（Critical，已更正计划）— Step 5 的类比「理由与 Plan 01 的评分表同构：DB 行是它的投影」是假的。**

亲验 14 张表的名字：**国标评分表根本没有投影成 DB 表**，它由 `app/refdata.py` 的 `load_standard()` / `standard()` 从 CSV 读进内存、全程不入库。「DB 行是它的投影」这半句是**借自本仓另一处真实机制**（`app/seed/` 确实把仿真数据投影成 DB 行）而套到了一个不成立的对象上。

**⚠️ 这与控制者错误 #40（Plan01 Ruling 164：编造「配额按列分摊后有取整」，实际借自趋势标签真在用的 `allocate_quota`）是完全同型的第二次发生**，而且这次它写进了**计划正文**、会被抽进简报、会被实现者当成事实照做。→ 见硬规矩 #63。

**P2-A3（Important，已更正计划）— `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}` 两个系数在 spec 里没有出处。**

亲扫 spec 全文：§7.4 `:508` 只写「跑量**按映射表下调**」、**没给任何数**；`:509`（肌肉量 < P10）写「同上」。spec 里唯一出现的 `系数 0.8` 在 `:604`——那是**预警触发的「减量 20%」**（`weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，属 **Plan 03**），与 §7.4 的安全后置跑量下调是**两个不同机制**；`0.9` 在 spec 里**根本没有对应物**。

**这又是 P2-A2 那个「借自另一处真实机制」的形态**（0.8 借自 `:604`）。**裁定**：① 两个系数按「本设计的默认规定，无 spec 出处」写进 YAML 注释；② **本 Task 就往 spec §14 追加一项**（不等 Task 12），因为值在这一刻被写死；③ Task 7 消费时不得把它们当 spec 条文引用。
**附带发现（口径差异，需在 Task 7 留意）**：spec §7.4 用**肌肉量 < P10**，而 §4.2/`:384` 的体成分异常判定 `C` 用**肌肉量 < P20**。**两个阈值不同、分属两个机制**，不得混用。

**P2-A4（Important，已更正计划）— `targets` 的取值域不能写成 `set(ITEM_BUCKET.values())`。**

亲验：`ITEM_BUCKET` 的 distinct values 是 **4 个**：`{'endurance', 'speed_flexibility', 'strength', None}`——`ITEM_BUCKET[ScoredItem.BMI] is None`（BMI 天然不属于任何短板桶。⚠️ **出处勘误（Ruling 121 / 控制者错误 #115；本行原先误标为「Ruling 124」，而 Ruling 124 讲的是 `.gitattributes` 的注释，见 :1526 —— 又一次引错裁定号，硬规矩 #55 的同类）**：本行原写「Plan 01 Ruling 19 的口径」，**错了**——Plan01 Ruling 19 是「`raw_from_score` 对非单调序列抛 `ValueError`」；该口径实际在 **Plan01 账本 `:133`（Ruling 17 关切 1）**，另见 **spec §4.2 `:210` 表行「否 / 不入桶」与 `:220`「短板判定项 = 6 个（排除 BMI）」**。**这个错引用已从账本传播进 2 份源码**（`exercises.py:76`、`test_refdata_prescription.py:198`），由 Task 2 fix round 3 清掉）。计划原文说「三个桶名」在**语义上对**，但照字面写 `set(...values())` 会把 `None` 放进取值域、让一个空 `targets` 悄悄合法。→ 明确写成 `frozenset(v for v in ITEM_BUCKET.values() if v is not None)`。

**P2-A5（Important，已更正计划）— 「列宽必须过 Plan 01 的列宽遍历测试」是过度承诺：那道测试只覆盖带 `_in_domain` CHECK 的列。**

亲验 `tests/db/test_models.py:312-394`：`_in_domain_columns()` **是自描述的**（遍历 `Base.metadata`、用正则 `_IN_DOMAIN_SQL` 从 `_in_domain` 生成的 `column IN (...)` 文本反解「列 → 允许值集合」），`:312-315` 明写「Plan 02/03 新加的表与列自动被覆盖，不必回来手抄第二张清单」。**但它只看得见带 `_in_domain` CHECK 的列**：`Exercise` 的 5 个 `String(n)` 列里只有 `impact_level` 会有 CHECK，`ref` / `name` / `video_url` / `equipment` 的取值域不是封闭集合、**完全不被覆盖**。→ 这四个必须在 `test_refdata_prescription.py` 里另写断言。

**P2-A6（Important，已更正计划）— 「同步改那条断言」低估了改动面：`== 14` 有 3 处，函数名也含「fourteen」，且有一处跨文件引用。**

亲验 `tests/db/test_models.py`：`assert len(tables) == 14` 在 **`:163`、`:228`**，`assert len(Base.metadata.tables) == 14` 在 **`:472`**；函数名 `test_all_fourteen_tables_created` 在 **`:24`**。**并且 `backend/app/db/models/prescription.py:11` 的模块 docstring 按名字引用了这个测试**（`tests/db/test_models.py::test_all_fourteen_tables_created`）——改名会让那处引用过期，而本 Task 正好要改那个文件（见 P2-A10）。

**P2-A7（Minor，已更正计划）— Files 段把 `.gitattributes` 列为 Modify，而 Step 4 自己说它「已有」。**

亲验 `.gitattributes:14` = `backend/data/*.yaml  text eol=lf`（Plan 01 加的，`:13-15` 三条：`*.csv` / `*.yaml` / `*.md`）。→ **不需要 Modify，只需确认**。Task 3 的 Files 段有同一个毛病，一并更正。

**P2-A8（Minor，已更正计划）— `backend/app/refdata_prescription.py` 被列在 Modify 下却写着「新建」。**

File Structure `:59` 也把它列为「**新建**（生产）」。→ 归 Create。

**P2-A9（Minor，已更正计划）— 「形状照 `app/refdata.py` 的 `load_standard`」把两个函数说成了一个。**

亲验：`load_standard(path: pathlib.Path | None = None) -> StandardTable` 在 `:122`，**只负责加载、不缓存**；进程内单例是**另一个函数** `standard()` 在 `:194`（`global _standard_cache`，`if _standard_cache is None: _standard_cache = load_standard()`）。`MappingProxyType` 确实在该文件里 ✓。→ 改成「照 `load_standard()` + `standard()` 这一对」。

**P2-A10（Important，**未更正计划、改由 Task 2 修生产源码**）— `backend/app/db/models/prescription.py` 的模块 docstring（Task 1 写的）有 4 处错。**

该文件今天 16 行、只有 docstring（Plan02 Ruling 5 的刻意留空）。亲验其内容与计划全文/spec 对不上：

| 行 | 原文 | 实测 |
| --- | --- | --- |
| `:5` | 「`prescription` / `prescription_template` / **`training_package`** 由 **Task 2/3** 建」 | **`training_package` 不是表**，是 `prescription` 的一个 **JsonText 列**（计划 `:524`）；spec 全文 0 命中该名字作为表 |
| `:5` | 「`prescription` … 由 Task 2/3 建」 | `prescription` 由 **Task 9** 建（计划 `:500`/`:502`） |
| `:7` | 「**`prescription_override`**（教师覆盖）… 由 **Task 9** 建」 | **计划全文没有这张表**：Task 8 的 Files（`:469`）只建 `override.py` + 测试；`:678` 的 18 张表清单是「Plan 01 的 14 + `exercise` / `prescription_template` / `prescription` / `weekly_adjustment`」，**没有 `prescription_override`** |
| 全文 | —— | **完全没提 `exercise`**，而 Task 2 正要往这个文件加它；也没提 4 张表的正确归属（T2 `exercise` / T3 `prescription_template` / T9 `prescription` + `weekly_adjustment`） |

**⚠️ 这段 docstring 熬过了 Task 1 的任务评审 + 5 轮 fix + 收尾评审。** 根因：那六轮的注意力全部集中在两个架构守卫文件与 `test_models.py` / `daily.py` 的散文上，**没人把「Task 1 新写的那两个占位模块 docstring」当成需要核对的对象**——而它们恰恰是**对未来的断言**，最容易与计划漂移。→ 见硬规矩 #64。

#### B. 任务对之间的冲突（共享文件）

**P2-B1（已更正计划）— `templates.py` 被 Task 2 与 Task 3 双双「Create」，且 `app/domain/prescription/__init__.py` 没有任何 Task 认领。**

亲验：`app/domain/prescription/` **今天不存在**（`app/domain` 下只有 `__init__.py` / `derive.py` / `indicators.py` / `percentile.py` / `stratify.py` / `tables.py`）。Task 2 的 Interfaces 要产出 `app.domain.prescription.templates.ImpactLevel`，Task 3 的 Files 写 **Create** `templates.py`；File Structure `:50` 列了 `app/domain/prescription/__init__.py`「公开面重导出」但**没有任何 Task 的 Files 段提到要建它**，而没有它包不成立。

**裁定**：Task 2 建 `app/domain/prescription/{__init__,templates}.py`，`templates.py` 本 Task **只放 `ImpactLevel`**（File Structure `:51` 说它是「模板的数据结构与维度词表；不读盘」，`ImpactLevel` 正是维度词表）；**Task 3 对它是 Modify 不是 Create**（已同步更正 Task 3 的 Files 段）。

**⚠️ 连带影响（已在 Task 1 fix round 5 埋好守卫）**：建出 `app/domain/prescription/` 后，包深从 2 变 3，`from ..indicators import X` **会是** **`level == 2`**（亲验 AST：`level=2 module='indicators'`；`_package_of(app/domain/prescription/match.py)` = `('app','domain','prescription')`；折算 `'app.domain.indicators'`、`_is_allowed` = True、与 `resolve_name('..indicators','app.domain.prescription')` 相符）。**fix round 5 加进两份矩阵的那一格绿档（Ruling 67-②）正是这个形状**，且控制者已用 M5/M6 变异对证明它是承重的。
> **勘误（控制者错误 #109 / Ruling 104）**：本段原写「Task 2 落地后这一格从『前瞻』变成『真仓形状』」——**不成立**。控制者亲扫 HEAD `c21767d` 的全仓相对导入（15 条），`app/domain/prescription/` 下的 **2 条都是 `level == 1`**（`__init__.py:19` `from .exercises import …`、`templates.py:37` `from .exercises import ImpactLevel`），**没有任何 `level == 2`**。Task 2 的实现者刻意选了**绝对导入** `from app.domain.indicators import ITEM_BUCKET`，理由是既有 4 个 domain 模块全部用绝对串、而 Ruling 96 的精神是「照抄既有分层、不要另创一种」——**这个选择是对的**。所以那一格**仍然是前瞻**，它守的是「将来有人在 `app/domain/prescription/` 里写 `from ..indicators import X`」这一档，而这一档今天在真仓里还不存在。

**P2-B2（已更正计划）— `impact_level` 有两个所有者，违反 Global Constraint #3。**

亲验 spec §7.2 的模板 YAML 字面形状：`:470-471` `- exercise_ref: interval_run` / `impact_level: high      # 供安全后置处理识别`；`:474-475` `- exercise_ref: compound_circuit` / `impact_level: medium`。**即模板 YAML 里每个 block 自带 `impact_level`，而 `exercises.yaml` 的每个动作也有 `impact_level`**。计划 `:185` 只声明了 `exercise_ref` 的唯一所有者、**没说 `impact_level`**。

**裁定**：`exercises.yaml` 是 `impact_level` 的**唯一所有者**；模板 YAML 可以照 spec 的字面形状写，但 **Task 3 的加载器必须校验「block 的 `impact_level` == 动作库里的值」，不一致就在加载时响亮失败**（与 `exercise_ref` 的处置同构）。Task 2 要在 `ExerciseSpec.impact_level` 的 docstring 里写明自己是所有者、谁负责校验。

**P2-B3（已并入 P2-B1 的更正）— `refdata_prescription.py` 被 Task 2 与 Task 3 先后写入。**

File Structure `:59` 说它「加载 18 套模板 YAML 与 `exercise_equivalence.yaml`」——**漏了 `exercises.yaml`**（Task 2 的活）。→ Task 2 建它时就把模块 docstring 写成「本模块分两段：动作库与等价表（Task 2）/ 18 套模板（Task 3）」，避免 Task 3 重写。

#### C. 各任务自身自洽性

**P2-C1（已更正计划）— Step 5 的变异 ② 有一半按字面不可满足。**

原文：「② 把一个 `exercise_ref` 从 `exercises.yaml` 删掉 → 指纹测试与**「模板引用存在性」测试（Task 3 建）**必须红」。**那个测试 Task 3 才建**，在 Task 2 里不存在。→ **这正是控制者错误 #46/#47（Plan01 Ruling 184：8 条变异里 2 条按字面不可满足）的形态，而它躺在计划里两轮没被发现。** 裁定：Task 2 只验指纹测试变红，那半留给 Task 3。

**P2-C2（已更正计划）— Step 2 的一个测试名与它自己的描述不符。**

`test_every_impact_level_has_at_least_one_low_substitute` —— 名字说「每个 impact level」、描述只要求「每个 `high` 动作都必须有 `low` 等价物」。**按描述、名字改成 `test_every_high_impact_exercise_has_a_low_substitute`**。理由：spec §7.4 `:508-509` 的两个触发都只替换 `impact_level: high`，要求 `medium` 也备 `low` 等价物是**过紧的守卫**（硬规矩 #50 的反面）。

**P2-C3（核对通过，无需更正）— `when: bmi_over_30 | muscle_low_p10` 与 spec §7.4 一致。**

spec §7.4 的三个触发是 BMI > 30 / 肌肉量 < P10 / 体脂率异常；前两个走「跑量下调 + high→low 等价替换」，第三个走「追加模板 `addons` 中的能量消耗模块」（`:510`）——**不走等价表**。故 `when` 只有两个取值是对的 ✓。`version` 的要求也核实了：spec `:512`「每次替换记录：原动作、新动作、触发条件、**映射表版本号**，写入 `prescription.safety_substitutions`」✓；`needs_review` 路径核实于 spec `:514` ✓。
**列定义核实于 spec §4.4 `:239`**：「`exercise` | id、动作名、视频二维码 URL、**`impact_level`** ∈ {`high`, `medium`, `low`}、目标素质、器械需求」→ 与计划 `:209` 的 6 列一一对应 ✓。`compound_circuit` 是 16 字符 ✓、`interval_run` 是 12 ✓。

#### D. Global Constraints 冲突

- **D1 = P2-A1**（`app/seed/` 冻结 vs Step 5）——已裁定。
- **D2**：禁区「`backend/data/seed/`（0 文件）」与本 Task **无冲突** ✓——`exercises.yaml` / `exercise_equivalence.yaml` 放 `backend/data/` **根**，不是 `data/seed/`。
- **D3**：禁区「**不要跑** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`」——验证 `sync_exercises` **只能在测试的 session fixture 里做**（内存库或 `tmp_path`），不得跑 CLI。已写进计划 Step 5 与派单。
- **D4**：Global Constraint #1「`app/domain/` 无任何 I/O」——`templates.py` 放 `ImpactLevel`（`str, Enum`）**不读盘** ✓，与 File Structure `:51`「不读盘」一致。建包后**两条架构守卫的扫描面会自动扩大**（`SCANNED_DIRS` 含 `domain`、`_py_files` 用 `rglob`），亲验 `test_layering.py:172` 的空转守卫下界是 8、实测 24 → 加 2 个文件变 26，**不会红** ✓；`test_domain_purity.py` 的 `>= 5` 空转守卫同理 ✓。

#### 预检小结

**10 处计划文本更正 + 3 处任务对冲突裁定 + 2 处自洽性更正 + 1 处生产源码 docstring 缺陷（P2-A10，交 Task 2 修）**。其中 **2 处 Critical**（P2-A1 seed 方案违反冻结约束并撞两道守卫；P2-A2 类比是假的），**且两处 Critical 都属同一个形态：把一个机制从本仓另一处真实存在的地方借过来、套到不成立的对象上**——即控制者错误 #40 的第二次发生。

**补硬规矩 #63：计划正文里任何「与 X 同构 / 照 X 的形状 / 理由与 X 相同」的类比，必须在预检时把 X 亲验一遍；类比是最容易借来一个真实机制、套到不成立对象上的句式。** 依据：P2-A2（评分表并没有投影成 DB 表）、P2-A3（0.8 借自 Plan 03 的预警减量）。

**补硬规矩 #64：「对未来的断言」（占位模块的 docstring、计划里写的「由 Task N 建」、File Structure 表）必须与计划逐 Task 交叉核对一次；它们最容易与计划漂移，而每一轮 fix 的注意力都在当下改动的文件上。** 依据：P2-A10——`app/db/models/prescription.py` 的 4 处错熬过了 Task 1 的任务评审 + 5 轮 fix + 收尾评审。

**控制者错误计数**：P2-A2 / P2-A3 是**计划编写期**（`e26347f`）写下的，本轮才查出 → 记 **#94 / #95**。P2-A1（seed 方案违反自己写的 Global Constraint #10）记 **#96**。P2-A4/A5/A6/A7/A8/A9 是转述既有代码时的不准 → 合并记 **#97**（一次预检不足，六处同源）。P2-C1（不可满足的验收判据，#46/#47 的第三次发生）记 **#98**。**Plan 02 累计 33 + 5 = 38 次，Plan 01 60 次，合计 98 次。**

Task 2: 预检完成（10 处计划更正已落盘、3 处冲突已裁定、2 条新硬规矩 #63/#64），派发中，基线 `e09e5f6`、481 passed。

#### Task 2 实现 — 控制者亲验（commit `3ea27cc`，481 → **528 passed**，14 → **15 张表**）

**判定：Task 2 交付合格；实现者报出 5 条成立 + 1 条歧义 + 1 条工具层的控制者错误，控制者逐条亲验后全部采信。另有 3 条关切需裁定（Ruling 96–98），其中 1 条是架构问题、进 Task 2 fix round 1。**

亲验清单（全部控制者本机实跑）：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 528 passed | `cd backend; python -m pytest -q` | **528 passed in 85.02s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **406 stmts / Miss 0 / 114 branch / BrPart 0 / 100%**、`527 passed, 1 skipped` ✓；新增 `prescription/__init__.py` 2 stmts + `templates.py` 5 stmts = **+7**，399+7=406 ✓；branch 仍 114（Enum 无分支）✓ |
| 表数 | `len(Base.metadata.tables)` | **15**，`'exercise' in tables` = True ✓ |
| 改动面 | `git diff --name-status fb5bddb 3ea27cc` | 15 个文件（7 A / 8 M）、`2004 insertions / 41 deletions`；其中 **4 个是派单未列的纯散文文件**（`db/session.py`、`db/models/__init__.py`、`db/models/_shared.py`、`refdata.py`），见 Ruling 91 ✓ |
| YAML 行尾 | 读字节 | `exercises.yaml` 13358 B / **CRLF 0**；`exercise_equivalence.yaml` 7841 B / **CRLF 0** —— `.gitattributes:14` 生效 ✓ |
| 指纹 | 自己算归一化 sha256[:16] | `A6A000F58815FCBB` / `0FFB881574AC04F3`，**与测试里钉的两个常量逐字相符** ✓；且 `test_refdata_prescription.py:83-84` 确实是 `path.read_bytes().replace(b"\r\n", b"\n")` **先归一化再哈希**（Plan 01 autocrlf 事故的教训被正确继承）✓ |
| 列宽（P2-A5 要求自写的 4 条） | 自己从 YAML 量最长值 | `ref` **29**（`energy_expenditure_plus_10pct`）≤ 48 ✓；`name` **12** ≤ 64 ✓；`video_url` **62** ≤ 256 ✓；`equipment` **13** ≤ 32 ✓ |
| `targets` 取值域（P2-A4） | 自己聚合全部条目的 `targets` | **恰好 `{endurance, speed_flexibility, strength}` 三个、无 `None`** ✓ |
| 视频 URL（不编造真链接） | 逐条比 | **23/23** 都是 `https://example.invalid/exercise/<ref>`、且与自己的 ref 一一对应 ✓ |
| 等价表安全属性 | 自己按 `low<medium<high` 逐条判 | **10 条映射：升档 0、超 `max_impact` 0、from/to 不存在 0**；`when` 分布 `bmi_over_30` 5 / `muscle_low_p10` 5 ✓；`version = '1.0'` ✓；`volume_reduction = {bmi_over_30: 0.8, muscle_low_p10: 0.9}` ✓ |
| 每个 high 有 low 等价物 | 自己算 | **high 动作 5 个、有 low 等价物的 5 个、缺 0** ✓ |
| 动作数 / 冲击分布 | 自己数 | **23 个**（计划预估 20–30 ✓）；`high` 5 / `medium` 10 / `low` 8 ✓ |

**控制者独立变异验收**（脚本 `.superpowers/sdd/_mut.py`，跑完删除；按整块删除顶层键、每次在 YAML 解析结果上确认「真的少了一个动作」、按字节还原并核 sha256）：

| 变异 | 结果 | 判读 |
| --- | --- | --- |
| **A** 删掉 `steady_run`（**不在任何映射里**） | **`1 failed, 527 passed`**，唯一红是 `test_exercises_yaml_fingerprint_is_pinned` | **精确复现实现者报的 1/528** ✓ |
| **B** 删掉 `bodyweight_resistance`（**在映射里**） | **`4 failed, 524 passed`**：指纹 + `test_equivalence_table_only_maps_to_existing_exercises` + `test_equivalence_never_maps_to_a_higher_impact_level` + `test_every_high_impact_exercise_has_a_low_substitute` | **三条跨文件守卫都有牙** ✓ |
| 收工 | sha256 还原 `True`、`git status --short` = `''`、HEAD = `3ea27cc` | ✓ |

**B 比 A 更有信息量**（4 红 vs 1 红），而实现者做的是 A。→ 见 Ruling 95 / 硬规矩 #65。
**动作库与映射表的耦合度**（控制者亲数）：23 个动作里 **9 个出现在映射里**（`bodyweight_resistance` / `brisk_walking` / `functional_training` / `hiit` / `interval_run` / `plyometric_jump` / `shuttle_run` / `sprint_50m_intervals` / `stationary_cycling`），**14 个不在**。

---

**Ruling 89（实现者错误报告 #1，成立，控制者错误 #99）— P2-A6 漏了一处必然要改的断言：`test_models.py:180` 的 `len(json_text_columns) == 8`。**

控制者亲验 diff：`assert len(json_text_columns) == 8` → `== 9`，并新增 `assert "exercise.targets" in json_text_columns`；连带 3 处「八个 JSON 形态的列」散文改成「九个」。**`Exercise.targets` 必须用 `JsonText`（P2 计划 `:209` 就是这么规定的），所以这个 8 必然变 9。**

**为什么漏了**：P2-A6 我是用 `grep '== 14'` 找的，只盯着「表数」这一个量。**而加一张表会改变的不止表数**——还会改变「JsonText 列数」「有 `_in_domain` CHECK 的列数」（实现者也一并把 `test_models.py` 里「今天恰好 10 列」改成了「**11** 列」）。**这三处都是「对当前 schema 的计数断言」，同一个动作会同时让它们过期。**

**更值得记的是它为什么没在第一时间暴露**：实现者报告说它当时**没红**，因为被前面那条 `== 14` 挡住没执行到——**同一测试函数里的前一条断言先失败了**。这正是 Plan 01 立「offender 一次性报全」那条规矩时担心的形态（`test_layering.py:142-143`：「逐处 assert 的话第一个红会盖住后面的」），只是这次发生在**跨轮次**：改完第一条，第二条才浮出来。→ 见硬规矩 #66。

**Ruling 90（实现者错误报告 #2，成立，控制者错误 #100）— P2-A10 只查了一个文件的 docstring，没做同类扫描；加一张表让另外 6 处散文变假。**

控制者亲验 diff，实现者修的 6 处（**全部是派单没要求的**）：
- `app/db/models/__init__.py:1`「14 张表的 ORM 模型（字段清单严格按 spec **§4.1–§4.3**、§4.6）」→「15 张表…**§4.1–§4.4**、§4.6」——⚠️ **连小节范围都漏了 §4.4**，而 `exercise` 正是 §4.4 的表
- 同文件 `:34`「JSON 形态的列一律用 `JsonText`（**八个**列，无一例外）」→「九个」
- 同文件「`:mod:`.prescription`  §4.4 处方（**今天为空**，Plan 02 Task 2/3/9 填）」→「**1 张**：Task 2 的 `exercise`；Task 3/9 再加 3 张」
- 同文件 `:72-73`「**两个**今天为空的小节也要被导入」→ 重写为「`feedback` 今天仍为空…`prescription` 的导入自 Plan 02 Task 2 起是**承重的**：`Exercise` 只有在**本模块被 import 之后**才注册进 `Base.metadata`，漏掉它 `exercise` 表就不存在，`test_all_fifteen_tables_created` 当场红」
- `app/db/session.py` 三处「14 张表」→「15 张表」（`:4` / `:46` / `:91`，其中 `:91` 是 `from app.db import models  # noqa: F401  仅为把 14 张表注册进 Base.metadata`）
- `app/db/models/_shared.py:4-6`「四个表模块」、`app/refdata.py:7-9`「文件名与目录的唯一所有者」

**根因**：硬规矩 #64 是我在**本轮预检时刚立的**，原文写的是「**『对未来的断言』**（占位模块的 docstring、计划里写的『由 Task N 建』、File Structure 表）必须与计划逐 Task 交叉核对」。**而这 6 处是「对现在的断言」**——它们陈述的是「今天有几张表 / 几个 JSON 列 / 哪几个模块为空」，**加一张表就让它们变假**，但 #64 按字面覆盖不到。

**→ 补硬规矩 #66：既覆盖「对未来的断言」（硬规矩 #64：由 Task N 建、将要加几张表），也覆盖「对当前状态的计数断言」（今天 N 张表 / N 个 JSON 列 / N 个模块为空 / §X–§Y / N 个公有名）与「类型标注」（它也是一种断言，见 Ruling 94）。改任何一处 schema，必须 grep 出全部同类计数并逐个更新——这与硬规矩 #51（两份重复的守卫要逐份修）是同一条纪律，只是对象从「代码副本」换成「陈述副本」。**

**Ruling 91（处置：接受这 4 个文件进 Task 2 的改动面，不算越界）**

派单 §2 的文件清单没列 `db/session.py` / `db/models/__init__.py` / `db/models/_shared.py` / `refdata.py`，实现者改了它们并在报告 §1.4 逐条交代理由。**裁定：接受。** 理由：① 全部是**纯散文**（控制者亲验 diff，无一行代码改动）；② 不改就会留下 6 处假陈述，而这正是本计划 Global Constraint #5 与硬规矩 #19 要消灭的东西；③ **派单没列它们本身就是控制者错误 #100 的后果**，不能反过来用它去禁止实现者做对的事。**「派单未列」不等于「禁区」——禁区是显式列出来的（派单 §3）。**

**Ruling 92（实现者错误报告 #3，成立，控制者错误 #101）— spec §14 编号冲突：派单让 Task 2 追加 #28，而计划 `:685` 已把 #28 预留给 Task 12。**

控制者亲验计划 `:681/:683/:685/:703`：
- `:681`「Step 3: spec 勘误与 §14 补项（本计划累计 **7 项，#28–#34**）」
- `:685`「**#28** 18 套模板的审校状态；**#29** 动作库的视频源；**#30** speed_flexibility 参数；**#31** 个体修正系数；**#32** **§7.4 的跑量下调系数**与「提高抗阻比重」的处置；**#33** 触发 4 口径；**#34** 同周多调整合成」
- `:703`「spec §14 从 27 项扩到 **34 项**」

**而 Task 2 刚追加的 #28 正是「§7.4 的跑量下调系数」——与原 #32 同一主题。** 根因：P2-A3 裁定「值在哪一刻被写死就在哪一刻登记」是对的，但**我在写那条裁定时没有去查计划后面是否已经给这个主题预留了编号**。这与硬规矩 #55（引用编号前先 grep 确认）**是同一条纪律的正面适用**——而 #55 是我在 Task 1 fix round 4 立的，本轮又违反了。

**裁定与更正（控制者已自己改计划正文）**：#28 归 Task 2（既成事实，且它的登记时点更对）；Task 12 的清单整体前移一位并**删掉重复的原 #32**：原 #28→**#29**、#29→**#30**、#30→**#31**、#31→**#32**、~~#32~~ 删除、#33→**#33**、#34→**#34**。**7 − 1 = 6 项**，而 §14 总数仍是 `27 + 1 + 6 = **34**`，与 `:703` **恰好一致**（那个数字本来就对，只是分配方式变了）。原 #32 里**「提高抗阻比重」的处置尚未登记**，故并进 #28 的影响面格交代，由 Task 7 落地时确认；若没覆盖，Task 7 追加为 **#35**。

**Ruling 93（实现者错误报告 #4，成立，控制者错误 #102）— 派单与简报对 §14 的授权互相冲突。**

简报（计划 `:181`）要求 Task 2「在 spec §14 登记『须提供真实视频源』」，而派单 §2 只授权追加**一项**、且主题固定为 `volume_reduction`。**两条不可同时满足。** 实现者的处置（只追加 #28，视频源写进 YAML 头注释 + 报告 §7-5，并指出计划 `:685` 的 #29 已预留此题）**是正确的**。

**裁定**：视频源的 §14 登记**归 Task 12**（重排后是 **#30**），Task 2 的 YAML 头注释作为过渡记录已足够。**计划 `:181` 已更正**为「这项登记由 Task 12 Step 3 统一做，见那里的 #30；Task 2 只写进 YAML 头注释，不单独占编号」。
**根因与 Ruling 92 同源**：我在派单里现编了一个授权范围，而没有去核简报/计划里已经存在的编号分配。**这是「派单与简报不一致」的第一次发生**，而派单是我写的、简报是我抽的——**同一个人写的两份文档互相矛盾，说明我发出前没有把它们对读过一遍**。→ 并入硬规矩 #58（发出前回查自己已写的内容）的适用范围：**回查对象包括「派单 vs 简报 vs 计划」三者之间的一致性，不只是派单内部。**

**Ruling 94（实现者错误报告 #5，成立，控制者错误 #103）— 计划 `:177` 的 `load_exercises() -> dict[str, ExerciseSpec]` 与同一句里的「`MappingProxyType` 只读」自相矛盾。**

`isinstance(MappingProxyType({}), dict)` 是 **`False`**（`mappingproxy` 不是 `dict` 的子类，它是只读**视图**）。实现者改成 `Mapping[...]`，与 `StandardTable.segments` 的既有口径一致。**裁定：接受。** 这是控制者在 `e26347f` 写计划时的笔误，Task 2 预检**也没查出来**——因为我核的是「`load_standard` 的形状」（P2-A9），没有核「返回类型标注与只读容器是否相容」。**类型标注也是一种断言**，→ 并入硬规矩 #66 的适用范围。

**Ruling 95（实现者歧义 #6，成立，控制者错误 #104 + #105）— 两条变异判据都不够强。**

**#104（判据归因错）**：派单说「① 把某个 `high` 动作的等价物改成另一个 `high` → 『不升冲击』测试必须红」。实现者亲验：`high → high` 是**持平**，「序」那一条判据**不开火**；那条测试红在**同一测试的另一支**（`max_impact` 一致性），报错文本里没有「升了冲击」。**并且真实表里所有 `from` 都是 `high`、所有 `to` 都是 `low`（控制者亲验：`from` 的 impact 分布 = `{high}`、`to` = `{low}`），故「序」支在真实数据上结构性不可达。** 实现者自己加做了 ①′（把 from/to 写反造一个 `low → high`）才证明那一支不是死代码——**这一步是它自己想到要做的，派单没要求**。

**#105（判据没指定最强的变异对象）**：派单说「② 把一个 `exercise_ref` 从 `exercises.yaml` 删掉」，**没说删哪一个**。实现者删了 `challenge_task`（`medium`、不在任何映射里）得到 1 红；**控制者亲跑对照：删一个在映射里的（`bodyweight_resistance`）得到 4 红**——三条跨文件守卫全都开火。**同一个判据，变异对象选得不同，信息量差 4 倍。**

**→ 补硬规矩 #65：一条变异验收判据必须 ① 指明「哪个断言分支」会开火（不是笼统地说「哪条测试会红」——一条测试里可以有多支），② 指明**最强的那个变异对象**（能让最多守卫开火的那个），③ 若某一支在真实数据上结构性不可达，必须另造一个合成输入证明它不是死代码。** 依据：#104 / #105。

**Ruling 96（实现者关切 #1，接受为架构缺陷，进 Task 2 fix round 1）— 三个值对象住在 `refdata_prescription.py`，domain 拿不到类型标注。**

P2-B1 裁定 `templates.py` 本 Task 只放 `ImpactLevel`，于是 `ExerciseSpec` / `EquivalenceTable` 一类值对象被放进了 `app/refdata_prescription.py`。而 `test_domain_purity.py` 的 allow-list **不放行 domain → 非 `app.domain` 的 import**，所以 **Task 7 的 `app/domain/prescription/safety.py` 无法 import 这三个类型**——而 spec §7.4 的等价替换恰恰要拿 `EquivalenceTable.lookup()`。

**裁定：搬进 domain，新建 `app/domain/prescription/exercises.py`。** 依据是**本仓已有的同构先例**（控制者亲验）：`StandardTable` 这个值对象住在 **`app/domain/tables.py`**（5 stmts、无 I/O），而读盘的加载器 `load_standard()` / `standard()` 住在 **`app/refdata.py`**，`refdata.py:**29**` 写的是 `from app.domain.tables import StandardTable`。**（勘误：本行原写 `:21`，那是 docstring 里的一句中文；控制者错误 #106 / Ruling 101。）****即「值类型在 domain、加载器在 domain 外、加载器 import 值类型」——这正是本仓既有的分层，`refdata_prescription.py` 应当照抄而不是另创一种。**
连带：① File Structure 要加 `backend/app/domain/prescription/exercises.py` 一行（第 9 个 domain 模块）；② `app/domain/prescription/__init__.py` 的公开面重导出要带上它们；③ **`ImpactLevel` 也应一并搬过去**（它是 `ExerciseSpec.impact_level` 的类型，留在 `templates.py` 会造成 `exercises.py → templates.py` 的包内依赖，而这两个概念并无从属关系）——但 `templates.py` 的维度词表里 Task 3 还要用 `ImpactLevel`，故**由 `templates.py` 从 `exercises.py` re-export 或直接 import**，由实现者按 domain 内部的依赖方向定，并在报告里说明理由。
**为什么不放进 `templates.py`**：File Structure `:51` 说它是「模板的**数据结构**与维度词表」，而 `ExerciseSpec` 是**动作库**的数据结构、不是模板的；Task 3 还要往里加 8 个 dataclass，混进来会变成杂物间。

**Ruling 97（实现者关切 #2，接受其决定）— `Exercise` 刻意不进 `models` 的公有导入面。**

实现者不加 `from .prescription import *`、不把 `Exercise` 放进 `__all__`。理由（控制者亲验其 diff 里的注释，成立）：`test_models_public_namespace_is_unchanged_by_the_split` 钉的是**拆包之前**（基线 `e26347f`）实测的 **33 个**公有名，**往那份基线里加 Plan 02 的新名字，等于把「拆包没改导入面」偷换成「拆包后的现状」，两侧就同源了（硬规矩 #35）**。代价：调用方必须写 `from app.db.models.prescription import Exercise`。

**裁定：接受，并把这个约定写进 Task 3 / Task 9 的预检清单**——它们会撞同一个决定点（`PrescriptionTemplate` / `Prescription` / `WeeklyAdjustment` 同样不进公有面）。**这是硬规矩 #35 的一个正面应用：为了保住「非同源」，宁可让调用方多写一层子模块路径。**

**Ruling 98（实现者关切 #3，接受为预期状态）— `sync_exercises` 今天没有生产调用方，真实库里 `exercise` 表是空的。**

P2-A1 禁止接进 `seed_database`，而接进管道是 Task 9/10 的活。**裁定：这是预期状态，不是缺陷。** 但**必须写进 Task 10 的预检清单第一项**：`prescription_stage.py` 落地时要确认 `exercise` 表已被灌数据（否则 spec §7.3 步骤 5「从 `exercise` 表取 URL 填入」会取到空）。**并加一条要求：Task 10 必须有一条测试覆盖「`exercise` 表为空时装配器/管道的行为」**——今天这个状态恰好是那个测试的天然输入。

**Ruling 99（实现者其余关切的处置）**
- `load_equivalence` 刻意不做跨文件校验（否则变异 ② 的判据不成立）→ **接受**。跨文件不变量由 `test_equivalence_table_only_maps_to_existing_exercises` 这条**测试**守着（控制者变异 B 亲验它会红），不需要加载器重复守。**这与 spec `:514` 的「运行时找不到等价动作 → `needs_review`」是两件事**：前者是 CI 期的表完整性，后者是运行期的查表落空。
- `equipment` 词表没有唯一所有者也没有测试 → **接受，转延后 Minor**。理由与实现者一致：现在钉住它等于**造出第二个所有者**（YAML 里的实际取值 + 测试里的字面清单）。**等 Task 3 的模板开始引用 `equipment` 时，所有权自然会落到 `exercises.yaml`，那时再钉。**
- 变异 ③ 红 **9 条**而非 1 条 → **接受**，这是「加载时响亮失败」的设计后果（删掉 `version` 会让加载器抛错，所有依赖它的测试连带报错）。**不是「一条守卫」的问题**：控制者提醒——按 Plan 01 控制者错误 #36 的教训，「N 条红」不等于「N 条守卫」，报告里应写明这 9 条里**有几条是独立的判据**。实现者的报告已写明「另 8 条因加载时响亮失败连带报错」✓。
- 基线覆盖率只做了算术交叉核对（406−7=399、branch 114 未增）**未独立复跑** → **控制者已代为复跑**（见上表：399/114 → 406/114、100%）✓。
- 它提前写下的「Task 3 追加 ref 时的 5 项连带清单」→ **采纳，转进 Task 3 的预检清单**。

**Ruling 100（工具层，实现者报告 #7）— `SearchReplace` 本轮又静默失败 3 次，且新形态是「连 diff 回显一起伪造」。**

实现者报告：`models/__init__.py` 落盘多一个前导空格、diff 回显缩进与落盘不符、**报告抬头两次编辑连 diff 一起伪造**（sha256 与编辑前逐字节相同 `a916bf29775ba0d9`，靠「新串命中数 = 0」查出）。另亲历一次 **PowerShell 吃掉反引号导致验证脚本自己假报「0 命中」**。

**这是工具/磁盘分歧家族的第 57–59 次**（此前 56 次）。**控制者本轮也中过一次**：预检时用 `Grep` 查 `review_probes` 的路径，得到「0 命中」，而实际是路径写错——**「0 命中」既可能是「真的没有」也可能是「查错了地方」，两者必须区分**。

**→ 采纳实现者的建议，把硬规矩 #48 的落盘闸门口径升级为：① 双向串查（新串命中数 ≥1 **且** 旧串残留数 = 0）；② 对缩进/空白敏感的改动另加 `repr()` 或 sha256 抽查；③ 任何「0 命中」的验证结论，必须先用一个已知存在的串验证查询本身有效（对照组），否则不得写成结论。** 第 ③ 条是硬规矩 #53（harness 必须带已知 GREEN 的对照行）在「查询」这个动作上的推广。

**控制者错误计数**：Task 1 共 33 次（#61–#93），Task 2 预检 5 次（#94–#98），**Task 2 实现轮 7 次（#99–#105）** = **Plan 02 累计 45 次**；Plan 01 60 次，**合计 105 次**。实现者 3 次（均自纠）。评审者 2 次。复审者 1 次。收尾评审者 0 次。

**补硬规矩 #65 / #66**（定义见 Ruling 95 / 89+90）。**#48 的落盘闸门口径升级**见 Ruling 100。

Task 2: 实现完成并亲验（528 passed、15 张表、domain 406/114/100%、变异 A/B 双版本亲跑），**fix round 1/5 派发中**（Ruling 96 的架构搬迁：三个值对象 + `ImpactLevel` 搬进 `app/domain/prescription/exercises.py`），基线 `3ea27cc`。

#### Task 2 fix round 1 — 控制者亲验（commit `c21767d`，**528 passed 不变**，domain 406/114 → **441/120**，仍 100%）

**判定：Ruling 96 的搬迁完整落地；实现者报出 8 条（4 条成立的控制者错误 + 1 条不成立 + 1 条歧义判成立 + 2 条非本轮造成），控制者亲验后全部采信，其中 CE-4 是它顶回了控制者的一条判据、且它是对的。**

亲验清单（全部控制者本机实跑）：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 改动面 | `git diff --name-status 4386ee2 c21767d` | **7 个文件 = 1 A + 6 M**；`-- backend/data Document` 命中 **0** ✓（两个 YAML 的指纹因此不可能变） |
| 528 passed | `cd backend; python -m pytest -q` | **528 passed in 82.73s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **441 / Miss 0 / 120 / BrPart 0 / 100%**、`527 passed, 1 skipped` ✓ |
| 覆盖率增量的算术 | 逐模块读 coverage 表 | `exercises.py` **38 stmts / 6 branch**、`templates.py` **5 → 2 stmts**、`prescription/__init__.py` **2 stmts**；`406 + 38 + 2 − 5 = 441` ✓、`114 + 6 = 120` ✓ —— **实现者的解释逐项对得上** |
| 搬过去的对象 | AST 扫 `exercises.py`（200 行）的顶层 | **恰好 7 个**：`ImpactLevel` / `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable` / `TARGET_DOMAIN` / `EQUIVALENCE_TRIGGERS` / `IMPACT_RANK` —— 与 Ruling 96 的裁定清单逐字相符 ✓ |
| domain 纯净性 | AST 扫 `exercises.py` 的 import 面 | 只有 `collections.abc.Mapping` / `dataclasses.dataclass` / `enum.Enum` / `app.domain.indicators.ITEM_BUCKET` —— **4 个全在 allow-list 内** ✓；**allow-list 一个都没加** ✓ |
| 架构守卫扫描面 | 自己数 `.py` | `app/pipeline` **7** + `app/db` **11** + `app/domain` **9** = **27** ✓（实现者报 26 → 27 相符）；`app/domain/prescription/` **3 个** ✓ |

**Ruling 101（CE-1，成立，控制者错误 #106）— 派单与账本都把 `from app.domain.tables import StandardTable` 的行号写成 `app/refdata.py:21`，实际在 `:29`。**

亲验：`:21` 是 docstring 里的一句中文（「让 `app/refdata.py` 承担一份处方侧的知识。」），`:29` 才是那条 import。**先例本身成立**（`StandardTable` 住 domain、加载器住 domain 外、加载器 import 值类型），错的只是行号。**而这个错行号同时出现在派单 §2.2 与本账本 Ruling 96 里——我写了两遍，两遍都错，且都没核。** 违反硬规矩 #61（引用路径/数量前 shell 亲验），而 #61 是 **3 轮前**立的。→ 账本已就地勘误。

**Ruling 102（CE-2，成立，控制者错误 #107，⚠️ 硬规矩 #58 第 3 次当轮违反）— 派单判据 3 说「`app/domain/` 从 6 个 `.py` 变 7 个」，实测是 8 → 9；且与我自己写的 Ruling 96「第 9 个 domain 模块」自相矛盾。**

亲验：`app/domain` 下 9 个 `.py` = `__init__` / `derive` / `indicators` / `percentile` / `stratify` / `tables` / `prescription/{__init__,exercises,templates}`。**6 是 Task 2 之前的数**（Task 2 主体已加了 `prescription/{__init__,templates}.py` 两个），我在写判据时用了过期状态。**更要紧的是：同一轮我写的账本 Ruling 96 说的是「第 9 个 domain 模块」——即正确答案就在我自己三轮前写的文字里，而派单与之矛盾。** 硬规矩 #58（立新规矩/写新裁定时回查自己已写的内容）**第 3 次当轮违反**（前两次：#56 在 Ruling 73、#55 在 Ruling 74）。

**Ruling 103（CE-4，成立，控制者错误 #108，⚠️ 本轮最重的一条）— 派单 §2.3 让实现者改 `tests/domain/test_prescription_templates.py` 的 import 路径，照做会让 domain 覆盖率跌破 100% 而 `pytest` 退出码仍是 0。**

实现者顶回了这一条，理由（控制者亲验成立）：`__init__.py` 改成从 `exercises` 重导出之后，**`templates.py` 就只剩这一个导入方**（亲验：全仓只有 `tests/domain/test_prescription_templates.py:37` 从 `templates` 导入）。把这条 import 也改指 `exercises`，`templates.py` 就**没有任何导入方** → 它那 2 条语句（`from .exercises import ImpactLevel` + `__all__ = [...]`）永远不执行 → **`Miss 2`、覆盖率跌破 100%，而没有任何一条测试会红**（`pytest` 退出码 0）。

亲验 coverage 表：`app\domain\prescription\templates.py  **2** 0 0 0 100%` —— **那 2 条语句进覆盖率统计的唯一途径就是那一句 import。**

**为什么这条最重**：它不是一条「不可满足」的判据（那类我已犯过 #46/#47/#105），而是一条**看起来完全合理、照做会静默破坏一个不变量**的指令。Global Constraint #2 要求 domain 分支覆盖 100%，而破坏它的方式**不会让任何测试变红**——只有 `--cov` 的 `Miss` 列会变。**「退出码 0 但不变量已破」是本仓最难发现的一类退化。**

实现者的处置正确：`tests/domain/test_prescription_templates.py` 的 import **保留**指向 `templates`，只重写 docstring 说明理由；`tests/test_refdata_prescription.py` 改成指向所有者 `exercises`。**附带收益（它自己指出的）**：那一句 import 现在**是**「`templates.py` 的 re-export 与 `__all__` 还在」的事实守卫。

**→ 补硬规矩 #67：任何「把 X 的唯一消费者改成消费 Y」的指令，发出前必须查 X 的覆盖率是否依赖那个消费者；domain 的 100% 覆盖不变量可以被一次纯 import 改动静默破坏，而 `pytest` 退出码仍是 0。** 依据：CE-4 / 控制者错误 #108。

**Ruling 104（CE-8，成立，控制者错误 #109）— 账本 P2-B1 说「Task 2 落地后那一格从『前瞻』变成『真仓形状』」，不成立。**

亲扫 HEAD `c21767d` 的全仓相对导入：`app/domain/prescription/` 下的 **2 条都是 `level == 1`**，**没有任何 `level == 2`**。实现者刻意选了绝对导入（`from app.domain.indicators import ITEM_BUCKET`），理由是既有 4 个 domain 模块全部用绝对串、Ruling 96 的精神是「照抄既有分层」——**这个选择是对的，我采纳**。所以 Task 1 fix round 5 加的那一格绿档**仍然是前瞻**。→ 账本已就地勘误。

**Ruling 105（CE-3 / CE-5，不成立为控制者错误）**
- **CE-3**：它一度以为账本「`tables.py` = 5 stmts」错了，自己量清后确认**账本对**——5 是 **coverage 口径**（`[7,8,11,12,27]`，含装饰器行、不含 docstring），AST 顶层节点只有 4 个。**这正是硬规矩 #57 的正面示范：先核「这个数是不是我要的那个口径」，再判对错。** 不计错误。
- **CE-5**：派单说的 6 个 allow-list 模块串是对的；错的是**前任实现者**写的 `refdata_prescription.py:25`「只放行 …与 **5** 个标准库模块」与 `templates.py:14-15` 漏列裸 `collections`。本轮已按 6 个逐个列名改正 ✓。**记实现者错误，不记控制者错误。**

**Ruling 106（CE-6 / CE-7，成立但非本轮造成 → 并入已计的控制者错误 #100，不新计数；另记实现者错误 #4）— 两处过期计数与一处过期行号，都是 Task 2 主体没做硬规矩 #66 的同类扫描留下的。**

- **CE-6**：两份守卫 docstring 都说「全仓相对导入 **12** 条、全部落在 `app.db.models` 包内」。控制者亲扫 `backend/app`：**15 条** = `app/db/models` **13** 条 + `app/domain/prescription` **2** 条（`__init__.py:19`、`templates.py:37`）。⚠️ **实现者报的是 14 条**——**更正（Ruling 113 / CE-12，控制者错误 #113）**：本句原写「它也错了、它漏数了 `templates.py:37`，即它在更正一个过期计数时又写下了一个新的过期计数（记实现者错误 #4）」，**这个归因是错的、那一条实现者错误也撤销**。fix round 2 的实现者在 `6a2938f` / `7b84599` / `3ea27cc` / `c21767d` 四个 rev 上用 `git ls-tree` + `git show` 重算（**没有 checkout**，符合 autocrlf 纪律），得到 **12 / 12 / 14 / 15**——**即「14 条」在它测量当时的 `3ea27cc` 上完全正确**（`app/db/models` 13 条 + `prescription/__init__.py:10` 的 `from .templates import ImpactLevel`，与它报告里写的那一条逐字对得上）；第 15 条（`templates.py:37`）是**它自己那一轮 fix round 1 新造的 re-export**。**故正确的归因是「增量预测错」而不是「数错」**——两者的预防动作不同：前者要求「新增一条相对导入时回来更新计数」（正是硬规矩 #66），后者只要求数得更仔细。控制者把「与我当前 HEAD 上的实测不符」直接当成「它数错了」，**没有核它测量时的那个 rev**——这是控制者错误 #113，也是硬规矩 #57 的又一次适用（核一个陈述时要核**它对哪个输入成立**，不能只核它对不对）。**「全部落在 `app.db.models` 包内」这半句也不再成立。**
- **CE-7**：两份守卫 docstring 都引 `app/db/models/__init__.py:74` 的 `from . import feedback, prescription`，亲验实际在 **`:82`**（`:74` 今天是 `from .derived import *`）。是 Task 2 按 Ruling 90 改该文件 docstring 时把行号推走的。
- 两者都**不在 Ruling 96 的因果链上**，实现者据此判断「报告不改、留给专门的散文修正轮」——**这个判断正确**（硬规矩 #32 的改动面纪律：一轮只做一件事，改动面才可自证）。→ **进 fix round 2。**

**Ruling 107（实现者 4 条关切的处置）**
1. **`lookup()` 的分支覆盖住在 domain 测试目录之外**（全在 `tests/test_refdata_prescription.py:416-448` 与 `:700-727`）；失效形态是「删那两条测试，`pytest` 退出码仍 0，只有 `BrPart` 变红」→ **接受为已知边界**（它已在两处 docstring 写明，符合硬规矩 #39）。**转 Task 3 预检清单**：建 `tests/domain/test_prescription_exercises.py` 时把 `lookup()` 的分支测试搬/复制过去。
2. **`IMPACT_RANK` 是公开 API 但没有直接钉秩值的测试**（只被两条间接守卫看着，M-B 证明它们够用）→ **进 fix round 2**：补一条**字面写死** `{HIGH: 0, MEDIUM: 1, LOW: 2}` 的断言（硬规矩 #35：**不得从 `ImpactLevel` 派生**）。
3. **`templates.py` 今天只有 re-export、且生产码 0 处消费**；下一个人可能当残留删掉 → 覆盖率跌破 100% 而无测试变红 → **进 fix round 2**：补一条守卫钉住 `templates.__all__ == ["ImpactLevel"]` 且 `templates.ImpactLevel is exercises.ImpactLevel`。**这条守卫同时把 Ruling 103 那个「静默破坏」的口子堵上。**
4. **`prescription/__init__.py` 的 `__all__`（7 个名字）没有测试钉住**（`db/models` 那边有 `_MODELS_PUBLIC_BASELINE`）→ **进 fix round 2**：补一条字面钉住 7 个名字的断言（同样不得从模块反推，硬规矩 #35）。

**Ruling 108（变异验收，控制者采信其证据并复核口径）**

实现者跑了 M-A / M-B / M0 / M1 四相位：
- **M-A**（`lookup` 的 `>=` → `>`）：`2 failed, 526 passed`，红在 `test_refdata_prescription.py:433` 与 `:727`——「上限与 `max_impact` **持平**时也必须命中」那一支
- **M-B**（`IMPACT_RANK` 的 `HIGH:0 ↔ LOW:2` 对调）：`1 failed, 527 passed`，红在 `:434`——「上限**高于** `max_impact` 时必须命中」那一支
- **两个变异打的是不同断言分支**，符合硬规矩 #65（本轮新立）的第 ① 项 ✓
- **M0** 528 passed + 441/0/120/0/100%；**M1**（dict 字面量 → 等价 `enumerate` 推导式，AST 真变、运行时值不变）仍 528 passed + 同覆盖 → **尺子不恒红** ✓
- 每次变异在剥 docstring 的 `ast.dump` 上确认真的改了代码、按字节还原核 sha256 = `1FC9AA42A6B93BF5`、**串行跑**（硬规矩 #62）✓

**它还回答了派单 §4 里控制者自陈「算不准」的那个问题**：`@dataclass` 生成的 `__init__` / `__repr__` / `__eq__` **不计入** coverage（`co_filename` 是 `<string>`）；**装饰器行单独计入**；**docstring 的 `Expr` 不计入**——这三条口径决定了 `exercises.py` 的 38 与 `templates.py` 的 −3。**控制者亲验 441 = 406 + 38 + 2 − 5 成立，故采信这套口径。**

**Ruling 109（实现者自报的 4 条自己的错误，记录）**
行数 off-by-one、`_IMPACT_RANK` 少算 `templates.py` 那 1 处、变异锚点没考虑 CRLF（被 `assert` 拦下、没有静默空跑）、**用 `read_text()` 量行尾得到假观测「CRLF 0」**（被 `assert` 拦下，实测 CRLF 624）。**四条全部自纠，且其中两条是被它自己写的 `assert` 拦住的**——这正是硬规矩 #53 的「harness 必须自带对照/闸门」在起作用。**最后一条的结论要记下来：凡报字节数/行尾/行数，必须用 `read_bytes()`，不能用 `read_text()`**（后者会做换行翻译，量不到 CRLF）。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 预检 5 次（#94–#98）、Task 2 实现轮 7 次（#99–#105）、**Task 2 fix round 1 共 4 次（#106–#109，Ruling 101/102/103/104）** = **Plan 02 累计 49 次**；Plan 01 60 次，**合计 109 次**。
**实现者 3 次**（Plan01 Ruling 80、Task1 Ruling 52、Task2 的 `dict` vs `Mapping` 归 CE-5）——**3 次全部自纠或被自己的 assert 拦下**。⚠️ 本行原写「4 次」并把 fix round 1 实现者的「14 条」算作第 4 次，**已由 Ruling 113 / CE-12 撤销**（那个数在它测量的 `3ea27cc` 上是对的）。评审者 2 次。复审者 1 次。收尾评审者 0 次。

**补硬规矩 #67**（定义见 Ruling 103）。

**⚠️ 一个必须写下来的模式观察**：硬规矩 #55（引用编号前 grep）、#56（判定标主语）、#58（立新规矩的当轮回查）、#61（引用路径/数量前亲验）**全部是在 Task 1 的后三轮里立的，而全部在立完之后的一到三轮内被我违反**（#56→Ruling 73、#55→Ruling 74、#58→Ruling 102、#61→Ruling 101）。**四条规矩、四次当轮或次轮违反。** 这说明：**问题不在「有没有规矩」，而在「发出前有没有一道机械的自查动作」**。Ruling 84 那个「派单末尾附控制者自查清单」是唯一一次奏效的做法——**本轮派单也附了，而它仍然漏掉了 CE-1 的行号与 CE-2 的文件数**，因为自查清单本身也是我手写的、没有跑过。**→ Task 3 起，派单末尾的自查清单必须由一个脚本生成（把清单里的每个路径/行号/数量都实际 stat/grep 一遍再打印），不许手写。**

Task 2: fix round 1/5 完成并亲验（528 passed 不变、domain 441/120/100%、7 个对象搬进 domain、allow-list 未放宽），**fix round 2/5 派发中**（Ruling 106 的 CE-6/CE-7 散文修正 + Ruling 107 的三条新守卫），基线 `c21767d`。

#### Task 2 fix round 2 — 控制者亲验（commit `966eae0`，528 → **531 passed**）

**判定：三项散文修正 + 三条新守卫全部落地；实现者报出 8 条（5 条成立的控制者错误 + 3 条不成立），控制者亲验后全部采信。另发生了一起数据丢失事故（Ruling 116）。**

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 改动面 | `git diff --name-status c21767d 966eae0` | **4 个 M、全在 `backend/tests/`**；`-- backend/app backend/data Document` 命中 **0** ✓（**本轮生产码一个字节没动**，与 Ruling 107 的「只改 docstring/注释 + 加测试」相符） |
| 531 passed | `cd backend; python -m pytest -q` | **531 passed in 55.89s** ✓（528 + 3 条新测试） |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **441 / Miss 0 / 120 / BrPart 0 / 100%**、`530 passed, 1 skipped` ✓（stmts 未变，符合预期：新测试不引入新的 domain 语句） |
| 三条新守卫存在 | grep `def <name>` | `test_impact_rank_values_are_pinned_verbatim` / `test_prescription_public_namespace_is_pinned_verbatim`（`tests/test_refdata_prescription.py`）+ `test_templates_module_still_reexports_impact_level`（`tests/domain/test_prescription_templates.py`）✓ |
| CE-6 的 5 行 6 次 | grep「12 条」 | purity 残留 **1** 次、layering 残留 **2** 次——**全部是绑定了 rev 的历史值**（`6a2938f` / `7b84599` 上是 12），当前值已写成「在 `c21767d` 上实测 **15** 条 = `app/db/models` **13** + `app/domain/prescription` **2**」✓ |
| 「全部落在 `app.db.models` 包内」 | 读 layering `:262` | 已限定为「**只对那 13 条成立**、对全仓不成立」✓ |
| 硬规矩 #56（标主语） | 读 layering `:265` | 已写「**本绿档的主语是「`app/db/models` 包内那批」**：12 条与 13 条两个时点…」✓ |
| CE-7 的 3 处过期数字 | grep | `__init__.py:74` **0 残留**、输出串 `__init__.py 74 1 None` **0 残留**（两份都清）✓ |
| 禁区 | 亲跑 | CSV `21412 B` / `D2C8E539E2FA0029` / CRLF 0；`exercises.yaml` `13358 B` / `A6A000F58815FCBB` / CRLF 0；`exercise_equivalence.yaml` `7841 B` / `0FFB881574AC04F3` / CRLF 0；`pe.db` 不存在；`data/seed` 0 文件 ✓ |

**Ruling 110（CE-9，成立，控制者错误 #110）— 派单说「12 条」有 **5 处**，实为 **5 行 / 6 次**（`test_layering.py:239` 一行含 2 次）。**

按 5 处修会漏 1 处。**根因**：控制者的自查脚本 `_sc.py` 用「逐行打印命中行」的方式输出，**我数的是行数、不是次数**。硬规矩 #51 要求「grep 出全部份数并逐份修，且在报告里列出份数」——**「份数」的口径本身要写清是行还是次**。实现者按 6 次处理，正确。

**Ruling 111（CE-10，成立，控制者错误 #111）— 派单标题说「`:74` 有 2 处」，正文「另：」里又点了第 3 处（输出串 `app/db/models/__init__.py 74 1 None` 里的 `74`）。**

**过期数字共 3 处，不是 2 处。** 根因与 #110 同源：**我在一处用「文件:行」的形态 grep、在另一处用叙述补充，两个口径没有合并成一个数**。**→ 并入硬规矩 #66：grep 同类计数时，要把「同一个事实的不同表述形态」（`文件:行`、命令输出串、散文里的裸数字）都算进去，并在报告里给出**形态清单**而不只是一个数。**

**Ruling 112（CE-11，成立，控制者错误 #112，⚠️ 本轮最实质的一条）— 派单 §2.3(c) 自相矛盾：既要「纯字面钉住 `__all__`」，又要求它能在「往 `exercises.py` 加了新对象却忘了重导出」时变红。**

**那种场景下 `__all__` 一个字都没变，纯字面断言恒绿。** 实现者的变异 **M-C3**（在 `exercises.py` 加一个公有定义、不重导出）实测证实：**只有它另加的那一支红**。它加的是 **AST 穷尽支**（读 `exercises.__file__`、AST 抽出全部不带下划线的顶层定义、与 `__all__` 比对），**并且刻意不用 `dir(pkg)`**——因为实测 `dir()` 会多出 `exercises` 这个子模块属性、且随导入顺序漂移（**这是硬规矩 #35「两侧不得同源」的一个正确应用：`dir()` 会包含 re-export 进来的名字，用它做实际侧就等于自己跟自己比**）。

**这与控制者错误 #108（CE-4，Ruling 103）是同一族**：我给出一条「看起来完备」的判据，而它在某个具体场景下**结构性地不可能开火**。**→ 并入硬规矩 #65 的第 ① 项**：说「这条守卫会在 X 时变红」之前，必须**真的构造 X 并跑一遍**（不是推演）。我这次是推演的。

**Ruling 113（CE-12，歧义 → 判成立，控制者错误 #113）— 账本 Ruling 106 把前任的「实测 14 条」归因为「它数错了」，实际是「增量预测错」。**

fix round 2 的实现者在 `6a2938f` / `7b84599` / `3ea27cc` / `c21767d` 四个 rev 上用 `git ls-tree` + `git show` 重算（**没有 checkout**，符合 autocrlf 纪律），得到 **12 / 12 / 14 / 15**。**即「14 条」在它测量当时的 `3ea27cc` 上完全正确**（13 + `prescription/__init__.py:10` 的 `from .templates import ImpactLevel`），第 15 条（`templates.py:37`）是**它自己那一轮 fix round 1 新造的**。

**两种归因的预防动作不同**：「数错」要求数得更仔细；「增量预测错」要求**新增一条相对导入时回来更新计数**——后者才是真问题，而它指向的正是硬规矩 #66。**控制者把「与我当前 HEAD 上的实测不符」直接当成「它错了」，没有核它测量时的那个 rev。** 这是硬规矩 #57 的又一次适用（核一个陈述要核**它对哪个输入成立**）。→ 账本 Ruling 106 那一句已就地更正。

**Ruling 114（CE-13，成立，控制者错误 #114，轻微）— 我建议把历史值绑到 `be0f1af`，而那两句散文自己绑的是 fix round 1 / fix round 5 = `6a2938f` / `7b84599`。**

`be0f1af` 是 Task 1 的 **fix round 3**。**轮次与 commit 的对应关系我没核就写了。** 实现者按散文自己绑的轮次处理（`6a2938f` / `7b84599`），正确。

**Ruling 115（CE-14 / CE-15 / CE-16，不成立，控制者同意）**
- **CE-14**：`git show` 的 LF 口径（不归一化则 44 个文件全 DIFF）与 `Read` 行号不可靠——**两条都实测成立**，派单是对的。实现者注明「这条救了我」。
- **CE-15**：stmts 未微增，**441 逐格与 fix round 1 相同** ✓
- **CE-16**：派单说「另一处命中是散文」——在 `from …templates import` 这个模式下成立（2 处 = 1 真 + 1 散文）；把模式松成 `prescription.templates` 才是 3 处。**派单的模式与结论一致，不成立。**

**Ruling 116（⚠️ 数据丢失事故，控制者记录 + 已抢救）— 两份实现者报告在本轮进行中被外部进程截断。**

**事实（fix round 2 实现者发现并报告，控制者亲验）**：
- `task-1-report.md`：约 **16:44:35** 从 **295 011 B / 3906 LF** 掉到 **77 837 B / 1031 LF**，`## 9` 与 `## fix round 1`–`## fix round 5` **六个节全部消失**
- `task-2-report.md`：**同一秒（16:44:35）**从 **117 694 B / 972 LF** 掉到 **62 640 B / 617 LF**，丢了 `## fix round 1` 节
- **不是实现者做的**：它本轮写盘只碰 4 个 `backend/tests/` 文件与 `$env:TEMP\r2v\`；`.superpowers/` 被 `.gitignore:10` 忽略；它没跑过 checkout / restore / switch / merge / clean

**根因（高度怀疑，未证实）**：两个文件被截断后的行数**精确等于 `Read` 工具此前报过的行数**（1031 / 617；账本 Ruling 64 记的 `task-1-report.md` 也是 **1031**）。即 **IDE 的文件视图层把它那份「只含前 N 行」的缓存写回了磁盘**。控制者另发现一条**加强证据**：被截断的版本与 TEMP 备份在**第 580 行的措辞也不同**（截断版写「与工作树那份陈旧副本**一致**」、备份写「与工作树那一侧一致」）——**说明写回的是「陈旧」缓存，不只是「短」缓存**。

**抢救结果（控制者亲做，脚本 `.superpowers/sdd/_rec.py`）**：
- **`task-1-report.md` 已还原到 243 343 B / 3298 LF / 15 个 `##` 节**（源：`$env:TEMP\pe_fr5_report_backup.md`，Task 1 fix round 5 的实现者在**追加前**做的字节备份，sha256[:16] `ADAD2D0AB59EB81D`）。**recover 了 `## 9` 与 `## fix round 1`–`## fix round 4`**。加上事故说明后 **245 229 B**。
- **仍然丢失、无法恢复**：`task-1-report.md` 的 `## fix round 5`（约 51 668 B）与 `task-2-report.md` 的 `## fix round 1`（约 55 054 B）。全 `$env:TEMP` 扫描（91 个候选文件）**没有任何副本**——Task 2 fix round 1 的实现者**没有**像 Task 1 fr5 的实现者那样先做字节备份。
- **技术结论无损**：这两节的全部裁定与关键取证已由控制者逐条转录进本账本的 `#### Task 1 fix round 5 — 控制者亲验`（Ruling 79–88，含 6 相位变异表）与 `#### Task 2 fix round 1 — 控制者亲验`（Ruling 101–109，含覆盖率增量算术、7 个搬迁对象、allow-list 未放宽、M-A/M-B/M0/M1 四相位）。**丢的是实现者自己的详细过程记录。**
- 另：fix round 2 的实现者把它当时还能读到的 `task-2-report.md` 的 `:900`–`:972` 原文（含 CE-6 / CE-7 / §7 的 2/3/4/5/7 条，**正是本轮派单的依据**）**逐字转录进了 fr2.11 附录**，那是唯一残留的原文。
- **取证物**：被截断的版本原样另存为 `task-1-report.TRUNCATED-20261007-174217.md`（77 837 B，未删）；`$env:TEMP\r2v\task-2-report.TRUNCATED-snapshot.md`（62 640 B，fix round 2 实现者存的）。
- **已建全树快照**：`.superpowers/_snapshots/20261007-174217/` = **96 个文件 / 4 416 480 B**（含 Plan 01 与 Plan 02 两份账本、全部简报/报告/评审包）。快照目录同样在 `.gitignore` 的 `.superpowers/` 内，故 `git status --short` 仍为空 ✓。**快照文件不会被 IDE 打开，因此不受「缓存写回」影响。**
- 两份报告的顶部各插入了一段事故说明（**只加不删**）。

**→ 补硬规矩 #68：`.superpowers/` 下的账本、报告、评审包在每次追加前必须先做字节备份**（`$env:TEMP` 或 `.superpowers/_snapshots/`），并在报告里记下备份路径与 sha256[:16]。**依据**：Task 1 fr5 的实现者做了备份 → 那一轮之前的全部内容被救回；Task 2 fr1 的实现者没做 → 那一节永久丢失。**同一起事故里，做了备份的和没做备份的结果天差地别。**

**→ 补硬规矩 #69：`Read` 工具在本仓不只是「行号不可靠」，而是「可能会把它那份陈旧且截断的缓存写回磁盘、造成不可逆数据丢失」。** 因此：① **不得用 `Read` 打开 `.superpowers/` 下的大文件**（账本 190 KB、报告 245 KB、评审包 250 KB）；② 凡引用这些文件的内容，一律用 python `read_bytes()` 取；③ **`Read` 报出的行数不得当成文件的真实行数**（Ruling 64 已记它偏小，本轮证实那个「偏小的数」正是被写回磁盘的截断长度）。**这把硬规矩 #30（行号取 shell 口径）从「精度问题」升级为「数据安全问题」。**

**⚠️ 一个需要用户裁定的结构性问题**：`.superpowers/` 被 `.gitignore:10` 忽略，**整个 SDD 审计链（190 KB 账本 + 245 KB 报告 + 250 KB 评审包 + Plan 01 的 806 KB 账本）没有任何版本控制保护**。本次事故一次就 destroy 了约 107 KB，只因一个实现者恰好做了 TEMP 备份才救回 165 KB。**是否把 `.superpowers/` 纳入版本控制，是用户的决定**（它体积大、变更频繁、且含大量过程性内容；但它是这个项目唯一的行为规范与错误模式的记录）。

**Ruling 117（实现者关切 1/4 的裁定）**
- **关切 1**：`test_layering.py:318` 那条**代码注释**「真仓 `app/db/models/` 就是这一档」现在不完整（`app/domain/prescription` 也有 2 条这一档）。它没改，理由是「它是逐格主语的注释、不含计数，全仓口径住在已改的 docstring 里」。**裁定：接受不改。** 理由成立——那条注释的主语本来就是 `app/db/models/`（硬规矩 #56 已满足），而全仓计数已由 docstring 承担。**两处都改反而会让同一条信息有两个所有者。**
- **关切 4**：全仓相对导入的计数**至今没有任何测试看着**（它的 M1b 实证：把 `templates.py` 的相对导入改成绝对导入，计数 15 → 14 而 **531 passed 全绿**）。它问要不要加一条**下界/形状**断言。**裁定：Task 2 不加，转 Task 3 预检清单。** 理由：① 那些数字是**散文里的历史实测**，已按硬规矩 #19 标了 rev 与时点，本来就是「不被守卫」的那一类；② 加一条等值断言会让**每一次合法的导入风格变化都变红**（M1b 就是语义等价改写），那是过紧的守卫（硬规矩 #50 的反面）；③ 若要加，只能加**形状断言**（「`app/domain/prescription/` 下的相对导入必须折算后仍以 `app.domain.` 开头」），而那**已经被 `test_domain_purity.py` 的 allow-list 守卫覆盖**——所以真正缺的不是断言，是「散文里的计数会过期」这件事本身，而它的解法是**少写裸计数、多写可 grep 的原文**（本轮 CE-7 的修法建议）。
- **关切 2/3/5/6**（(c) 的支 5 对 Task 3 是刻意紧约束 / Task 3 搬迁清单 4 项 / Task 7 直接用 `IMPACT_RANK` 别造第四份秩序声明 / 它自己本轮 5 个错全部自纠）→ **全部采纳，转进 Task 3 与 Task 7 的预检清单**。特别是它自纠的两条要记：**① 把未实跑的推断写进 docstring**（「删 `templates.py` → Miss 2」，实跑证明是**收集期 ImportError、退出码 2**，不是 Miss 2）——**这是硬规矩 #29/#52 的又一次适用，而且它自己抓出来了**；**② 写了一个会被自己的散文改变的 grep 计数**（报 3、实测 9，因为正则的 `.` 把文件名也匹配了）。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 预检 5 次（#94–#98）、Task 2 实现轮 7 次（#99–#105）、Task 2 fr1 4 次（#106–#109）、**Task 2 fr2 5 次（#110–#114，Ruling 110/111/112/113/114）** = **Plan 02 累计 54 次**；Plan 01 60 次，**合计 114 次**。
**实现者 4 次**（Plan01 Ruling 80、Task1 Ruling 52、Task2 的 `dict` vs `Mapping`、Task2 fr2 自纠的 2 条合并计 1 次）——**全部自纠或被自己的 assert 拦下**。评审者 2 次。复审者 1 次。收尾评审者 0 次。

**补硬规矩 #68 / #69**（定义见 Ruling 116）。**#65 / #66 的适用范围已按 Ruling 112 / 110+111 扩写。**

Task 2: fix round 2/5 完成并亲验（**531 passed**、domain 441/120/100%、4 个测试文件、生产码 0 字节改动），**尚未做 Task 2 收尾评审**。⚠️ 同期发生数据丢失事故（Ruling 116），已抢救回 165 KB、永久丢失约 107 KB（技术结论无损）。基线 `966eae0`。

#### Ruling 118（用户裁定）— SDD 审计链纳入版本控制；Task 3–12 照当前强度自动推进

控制者用 `AskUserQuestion` 提了两个问题，用户的裁定：
1. **`.superpowers/`（账本 / 报告 / 评审包）→ 「纳入 git 版本控制」**（三选一里的推荐项）。另两个选项是「只提交账本、报告仍忽略」与「保持忽略、只强化备份纪律」。
2. **Task 3–12 的推进节奏 → 「照当前强度自动推进」**。即每个 Task 走完整循环（预检扫描 → 派实现者 → 控制者亲验含独立变异 → fix round 到收敛 → 收尾评审），**不降低文档精度要求**、每个 Task 结案后不必等用户确认。

**落地（控制者已做，commit `8e6a38f` + `.gitattributes` 那一笔）**：

- **根 `.gitignore`**：删掉裸规则 `.superpowers/`，改成只忽略 `.superpowers/_snapshots/`（全树冗余备份——git 已经承担这个角色，再入库等于同一份内容存两遍）。`__pycache__/` 由既有的全局规则覆盖。**原注释「本流程的临时产物（台账、任务简报、评审包），永不入库」已随之作废**——它现在是**永久产物**。
- **⚠️ 发现了第二层忽略规则**：`.superpowers/sdd/.gitignore` 的内容是**一行 `*`**（2 字节），即「忽略本目录下的一切」。**它导致 `git add -A --dry-run .superpowers` 报 0 个文件**——控制者先改了根 `.gitignore`、以为完事，是这条 dry-run 的 0 才把第二层暴露出来（`git check-ignore -v` 指认 `.superpowers/sdd/.gitignore:1:*`）。**这是硬规矩 #59 的正面回报：写完断言性的改动必须亲眼看它的实际输出，而不是推演。**
- **该文件删不掉**：`Path.unlink()` 抛 **`PermissionError: [WinError 32] 另一个程序正在使用此文件`**。改成纯注释（等效于不忽略任何东西）才成功。**→ 这是「IDE 正持有 `.superpowers/` 下文件句柄」的直接证据，与 Ruling 116 的根因推断（IDE 把它那份陈旧且截断的缓存写回磁盘）互相印证。**
- **入库 164 个文件 / 约 4.9 MB**：Plan 01 与 Plan 02 两份账本、全部任务简报、实现者报告、评审包、以及各轮取证探针（`fr2_probes` 11 / `fr3_probes` 11 / `fr4_probes` 21 / `fr5_probes` 39 / `review_probes` 28）。**亲核：0 个 `_snapshots`、0 个 `.pyc`/`__pycache__`。** commit `8e6a38f`，`166 files changed, 61768 insertions(+), 2 deletions(-)`。
- **同时入库了抢救结果**：`task-1-report.md` 78 KB / 10 节 → **245 KB / 15 节**，以及两份报告顶部的事故说明与被截断版本的取证物 `task-1-report.TRUNCATED-20261007-174217.md`。

**→ 补硬规矩 #70：`.gitattributes` 把 `.superpowers/**` 钉成 `text eol=lf`。** 依据：这些文件里**大量引用自己的字节数与 sha256**（报告顶部的「245 229 B / `292F6251FD45AE8E`」、账本里的「117 694 B / 972 LF」），而 `core.autocrlf=true` 下一次 `checkout` / `merge` 就会把 LF 重写成 CRLF，**于是文件里印着的每一个字节数当场变假**——而这类假数字正是本仓花了 114 次控制者错误才学会去核的东西。与 `backend/data/` 的处置同一条理由（Plan 01 的 autocrlf 事故、硬规矩 #46/#47）。**亲验生效**：`git check-attr text eol` 返回 `text: set / eol: lf`。

**→ 硬规矩 #68 修订**：原文要求「每次追加前先做字节备份到 `$env:TEMP` 或 `.superpowers/_snapshots/`」。**现在 git 是主要保护**，故修订为：
1. **每轮（预检 / 实现 / fix round / 评审）结束时，`.superpowers/` 的改动必须与代码改动一起 commit**（可以分开两个 commit，但都要在当轮结束前落库）。这是主要防线。
2. **轮内**（一次追加之前）仍要做字节备份——因为一轮之内可能有多次追加，而 git 只能恢复到上一个 commit。备份路径与 sha256[:16] 记进报告。
3. `.superpowers/_snapshots/` 仍然忽略（git 已替代它）。

**Task 1 的 fr5 实现者做了 (2)、Task 2 的 fr1 实现者没做**——那正是 165 KB 被救回、107 KB 永久丢失的分界。**从本轮起 (1) 也生效，故同类事故不再可能整节丢失。**

Task 2: fix round 2/5 完成并亲验（**531 passed**、domain 441/120/100%、生产码 0 字节改动）；审计链已入库（`8e6a38f` + `.gitattributes`）。**下一步：Task 2 收尾评审**（`fb5bddb..HEAD` 的代码链），然后 Task 3。基线 `966eae0`（代码）/ `8e6a38f`（含审计链）。

**Ruling 118 的落地补记（`.gitattributes` 走了三步才对，过程本身值得记）**

1. **第一步（`23325de`）钉 `.superpowers/** text eol=lf`** —— 照抄 `backend/data/` 的处置。`git check-attr` 确认 `text: set / eol: lf` ✓，**但 `git ls-files --eol` 立刻报 `i/lf  w/crlf  attr/text eol=lf`**：index 是 LF、工作树是 CRLF。**`eol=lf` 只规定「以后检出成 LF」，对已经是 CRLF 的工作树没有任何追溯力**，于是两者长期不一致，而下一次 `checkout` 会把 **164 个文件全部重写**——届时这些文件内部引用的每一个字节数与 sha256 都会变假。**硬规矩 #70 想防的事，被它自己的第一版实现方式制造了出来。**
2. **根因（亲测）**：这些文件的行尾**本来就是混合的**——`progress.md` 纯 CRLF（1415/1415）、`task-1-report.md` 纯 LF（3325，因为它由 `$env:TEMP` 的备份还原、而备份是 LF）、`task-2-report.md` **MIXED**（CRLF 946 + 裸 LF 23，因为 fix round 2 的实现者把 LF 内容追加进了一个 CRLF 文件）。**一个统一的 `eol=` 值不可能同时匹配三者。**
3. **第二步（`23388c7`）改成 `-text`**（双向零转换）：blob 与工作树逐字节相同、且与 `core.autocrlf` 无关，每个文件保持它现在的行尾。**这与 `backend/data/` 用 `text eol=lf` 不矛盾**——那几个文件本来就是 LF，钉 `eol=lf` 是零成本的保证；审计链不是。
4. **但 `-text` 不会追溯修正 index**：`git add` 认为文件没变（stat 缓存），index 里仍是第一步存下的 LF blob，终验 `git show :<path>` 与工作树**不相同**（`progress.md` 210084 vs 211499）。
5. **第三步（`7c5aff8`）`git add --renormalize`** 按 `-text` 重存工作树原始字节。**终验通过**：

```
progress.md         i/crlf  w/crlf  attr/-text   HEAD-blob == 工作树 ✓  sha16=A327D60E37C92021
task-1-report.md    i/lf    w/lf    attr/-text   HEAD-blob == 工作树 ✓  sha16=292F6251FD45AE8E
task-2-report.md    i/mixed w/mixed attr/-text   HEAD-blob == 工作树 ✓  sha16=6F1851079C3F6031
```

**→ 硬规矩 #70 修订：`.gitattributes` 对 `.superpowers/**` 用 `-text`，不是 `text eol=lf`；并且改完属性必须 ① `git add --renormalize`、② 用 `git ls-files --eol` 确认 `i/` 与 `w/` 一致、③ 用 `git show :<path>` 与工作树做字节比对。只做 ①（甚至只做 `check-attr`）都不算完成——`check-attr` 只证明「规则写对了」，不证明「index 里的字节对了」。**

**这也是硬规矩 #59 的又一次正面回报**：第一步之后我本来可以直接走人（`check-attr` 显示规则生效了），是 `ls-files --eol` 那个 `i/lf w/crlf` 把问题暴露出来的。**「属性写对了」与「字节对了」是两件事。**

**→ 补硬规矩 #71：一个文件集合的行尾如果是混合的，就不能用统一的 `eol=` 属性去「修」它——那只会制造 index 与工作树的长期不一致。要么逐文件统一到同一个行尾再钉 `eol=`，要么用 `-text` 保持现状。** 依据：Ruling 118 落地补记第 1–3 步。

Task 2: fix round 2/5 完成并亲验（**531 passed**、domain 441/120/100%、生产码 0 字节改动）；审计链已入库且字节自洽（`8e6a38f` → `23325de` → `23388c7` → `7c5aff8`）。**下一步：Task 2 收尾评审**，然后 Task 3。代码基线 `966eae0`、含审计链基线 `7c5aff8`。

#### Task 2 收尾评审（`fb5bddb..966eae0`）— 控制者复核

**评审者结论：Approved with findings；Critical 0 / Important 7 / Minor 10；另报控制者错误 8 条（7 成立 / 1 歧义）。**
评审报告：`task-2-review.md`（91 077 B / 776 LF / sha256[:16] `5462B40B5A7FC024`）；评审包：`task-2-review-package.md`（210 927 B / 3229 行）。均已入库（commit `1191170`）。

**行为面全部合格**（评审者独立复核）：数据实算正确、spec §4.4 六项一一对应、23 个视频 URL **全是 `.invalid` 占位符**、P2-A1…D4 与 Ruling 96/97 逐条落地、**allow-list 在四个 rev 上零放宽**、`app/seed/` 与 `.gitattributes` 零字节改动、10 条映射不升冲击档、5 个 `high` 动作全有 `low` 等价物。

**7 条 Important 全是「印在源码里的陈述与实测不符」**（本项目的主要错误类，Task 1 收尾评审同一位置查出 2 条，本轮 7 条）：
1. `exercises.py:50` + `test_prescription_templates.py:63`：「SQLite 会把枚举按 `str()` 存成 `"ImpactLevel.HIGH"`（**19 字符**，撑破 `String(8)`）」——实测 `len(str(ImpactLevel.HIGH)) == **16**`，且裸 `sqlite3` 绑定该枚举落库是 `'high'`（`typeof=text`、`length()=4`）。**机制不成立**（生产路径写的还是 `.value`）。
2. `exercises.py:58-59` + `test_refdata_prescription.py:85-86`/`:308-309`：「改坏**任何一份**都会让 `test_equivalence_never_maps_to_a_higher_impact_level` 红」——AST 实测该测试函数体内 `IMPACT_RANK` **0 命中**，只用测试侧的 `IMPACT_DESCENDING`；**改坏生产侧秩它恒绿**。同文件 `exercises.py:94-96` 写的是正确版「之一会红」——**同一个文件里两种说法**。
3. `exercise_equivalence.yaml:33`：「8 个 low 动作里的 **5** 个被用到」——实测被用到的 `to` 是 **4** 个，而它自己列出的名字也正好 4 个（**与自己列的清单矛盾**）。
4. `test_models.py:35-36` + `app/db/models/prescription.py:21`：印的 `:163`/`:228`/`:472` 是 `fb5bddb` 上 `== 14` 的位置，Task 2 自己把它们推到了 **`:169`/`:236`/`:494`**，两处散文都没跟——**与 fr2 刚修完的 CE-7 同型，一轮之内复发**。
5. `exercises.py:76` + `test_refdata_prescription.py:198`：「BMI 不归任何短板桶，**Plan01 Ruling 19** 的口径」——Plan01 Ruling 19 是「`raw_from_score` 对非单调序列抛 `ValueError`」；该口径实际在 Plan01 账本 `:133`（Ruling 17 关切 1）。**源头是账本 P2-A4 自己写错，已从账本传播进 2 份源码**（→ 控制者错误 #115 / Ruling 121）。
6. `exercises.yaml:22`：「计划 Task 12 已把『动作库的视频源』预留为 **#29**」——`d40f36c` 重排后是 **#30**。⚠️ 改它要同步 `EXERCISES_FINGERPRINT`。
7. `spec:933`（§14 第 28 项的「影响面」格）：「**编号冲突待 Task 12 处理**…整体后移为 **#29–#35** 并删掉重复的一条」——冲突已由 `d40f36c` 处理完，实际结果是 **#29–#34 共 6 项**；**照 spec 那句执行会凭空造出一个 #35**。

**Minor 10 条**（`:func:` 指向不存在的测试名 / 「四个函数」而公有函数是 5 个 / 「与 `upsert` 同一口径」而 `repo.py:39` 明写 upsert 既不 commit 也不 flush / 12 项全归给 spec `:487` 而 2 项实在 `:482`/`:484` / 「那条守卫只遍历 `DATA_TABLES`」而 `:567` 是 `DATA_TABLES + REFERENCE_TABLES` / 两个生理学数值（2–3 倍、1.2 倍体重）无出处且未标「不被守卫」/ 「今天有两份」而 fr2 之后有三处 / `hiit` 的节标题写「绿层」而它自己的注释写「黄层」/ 「没有任何一条断言依赖 `challenge_task`」而 `test_refdata_prescription.py:449` 硬编码了它 / 折行点）。

**评审者复跑了 4 组变异**（串行、跑前跑后 sha256 一致），其中 **MB4 相位 2 完全复现了 Ruling 103 / 硬规矩 #67 那个「静默退化」**：把两处 import 都改指 `exercises` 并去掉 fr2 那条守卫后，`templates.py` 从 `2 0 0 0 100%` 变成 **`2 2 0 0 0%  Missing 37-39`**，而 **`pytest` 退出码仍是 0**。它还用 `coverage.results.Numbers(441, miss=2, br=120)` 独立算出 `pc_covered=99.6434 → '99'`，**算术与格式双双成立**。**这是 fr2 那条守卫承重的实证。**

**Ruling 119（评审者报的控制者错误，控制者逐条亲验）**
- **CE-1 / CE-2 / CE-3（#110–#112 之后的新三条，记 #116/#117/#118）— 派单 §3-A 的三个行数全是错的**：`refdata_prescription.py`「约 **507** 行」（`3ea27cc` 是 507，`c21767d` 之后是 **406**——我用了搬迁前的值）；`__init__.py`「**12** 行」（12 是 `3ea27cc` 值，HEAD 是 **37**；**同一个三元组混了两个 rev**）；`test_refdata_prescription.py`「约 **1050** 行」（逐 rev 实测 722 / 727 / **921** / 921，**1050 在任何 rev 上都对不上——这不是过期值，是无出处的数**）。**三条都正中硬规矩 #61**（引用数量前 shell 亲验），而 #61 是 6 轮前立的。
- **CE-4 / CE-5（记 #119）— 评审包有一节标题写着「禁区命中（三者都必须为空）」，而它自己底下就印着 `backend/data` 的 2 条命中**（两个新 YAML）。标题与内容直接矛盾，而那正是评审者据以判禁区的一段；三段之间还缺换行、`(none)` 与下一个小标题粘成一行。**这是硬规矩 #59 的原型复发**（控制者错误 #82：写一个断言性标题、不看它的输出就交出去）。**实质禁区未被侵犯**（P2-D2 已裁定 YAML 放 `data/` 根无冲突，禁区是 `data/**seed**/`；`data/seed/` 0 文件、CSV 指纹相符、`data/` 里既有 3 个文件 name-status 0 命中）——**是口径取错，不是越界**。
- **CE-6（记 #120）— 账本 P2-D4 引 `test_layering.py:172` 说那是空转守卫的下界，实测该 assert 在预检基线 `e09e5f6` 上是 `:436`（HEAD `:466`），`:172` 是 `for alias in node.names:`**。**内容全对**（下界 8、扫描面 7/11/9=27 评审者实跑守卫自己的 `_py_files` 复核相符），只有行号错。
- **CE-7（记 #121）— 账本 P2-A4 把「BMI 不归任何短板桶」的出处写成 Plan01 Ruling 19，实为 Plan01 账本 `:133`（Ruling 17 关切 1）**。**这一条已从账本传播进 2 份源码**（= Important 5），是本轮唯一一条**控制者的账本错误变成了生产源码里的错误引用**的记录。
- **CE-8（歧义，不计）**：派单说 `prescription.py:11` 那处按名字的引用——`:11` 是 `fb5bddb` 的位置（评审者 `git show` 核过、逐字相符），HEAD 上已落到 `:17` 且**已正确更新为 `test_all_fifteen_tables_created`**。**裁定已落地，派单的行号是未标注的历史值。**
- **评审者另做了 12 项正面确认**（评审包 210 927 B / 3229 行逐字相符、三份文档尺寸、`brief` 28 004 B 逐字节、「五笔不动 `backend/`」、481→528 的 **+47**、406/114→441/120 的增量算术、528→531、「Ruling 48 号未使用」、硬规矩 #1–#47 在 Plan01 / #48–#71 在 Plan02 逐条找到定义行、计划 `:182` 的速度柔韧 4 项、删 `steady_run` 1 红 / 删 `bodyweight_resistance` 4 红），并抽验账本 Ruling 89/90/101/104/106/113/116 的 8 项裁定**全部与其独立复核一致**（含 `_snapshots/20261007-174217` = 96 文件 / 4 416 480 B、TRUNCATED 取证物 = 77 837 B / 1031 LF）。**这是连续第三次下游对控制者产物做正面确认**（Ruling 84/100 已把它保留为做法）。
- **它另指出派单 §0「收工时 `git status --short` 必须 0 行」按字面不可满足**（交接时就已有 1 行未跟踪的评审包，而 read-only 评审者不得 commit）——**成立**，控制者已代为提交（`1191170`）。这与硬规矩 #68 修订版第 (1) 条一致：每轮结束要把 `.superpowers/` 一起 commit。

**Ruling 120（12 条不可复核项的处置）**
其中**第 ② 条最要紧**：`531 passed` 与 domain `441/Miss 0/120/BrPart 0/100%` **是本轮唯一没被评审者独立验证的验收判据**——原因见 Ruling 121（环境已坏）。**控制者在环境坏之前亲跑过两次**（fix round 2 的验证：`531 passed in 55.89s`、`441 / Miss 0 / 120 / BrPart 0 / 100%`、`530 passed, 1 skipped`），故这两条**由控制者的实跑背书**，不算未验证。其余 11 条（历史墙钟、DB 层 `IntegrityError`/幂等、未复跑的 8 个变异相位、两个生理学数值等）接受为不可复核。

---

### ⛔ Ruling 121 — 环境级阻塞：Windows Smart App Control 拦掉了 SQLAlchemy 的一个 `.pyd`，全量测试已跑不起来

**发现者**：Task 2 收尾评审者（它没有绕过、也没有伪造绿，而是停下来报告——**这是正确的处置**）。**控制者已独立复现。**

**症状**：
```
$ cd backend; python -m pytest -q
ERROR tests/pipeline/test_daily.py
ERROR tests/test_refdata_prescription.py
…  Interrupted: 12 errors during collection
12 errors in 2.16s

ImportError: DLL load failed while importing _cache_key_cy: 应用程序控制策略已阻止此文件。
  File "…\sqlalchemy\sql\base.py", line 49, in <module>  from .cache_key import HasCacheKey
  File "…\sqlalchemy\sql\cache_key.py", line 29, in <module>  from . import _cache_key_cy
```

**控制者的诊断（全部本机实跑）**：
1. **Smart App Control 处于 Enforce 模式**：`HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState = **1**`（0=Off / 1=Enforce / 2=Evaluation）。评审者另在 `CodeIntegrity/Operational` 事件日志里取到 `Id 3077 / 3033 / 3118 (Smart App Control Block)`，正文是「`python.exe` attempted to load `…\sqlalchemy\sql\_cache_key_cy.cp311-win_amd64.pyd` that did not meet the Enterprise signing level requirements」。
2. **只有一个文件被拦**：逐个 import 那 8 个 `.pyd` 所属模块，`sql._util_cy` / `util._collections_cy` / `util._immutabledict_cy` **OK**；`sql._cache_key_cy` **BLOCK**；4 个 `engine.*_cy` 报 BLOCK 只是因为 import 它们会先经过 `sqlalchemy/__init__.py` → `cache_key.py`。**即单一故障点 = `sql/_cache_key_cy.cp311-win_amd64.pyd`（108 544 B，sha256[:16] `B1A005B464DFC87E`）。**
3. **没有代码级绕过**：`cache_key.py:29-31` 是**无条件**的三行 `from . import _cache_key_cy` / `from ._cache_key_cy import CacheConst` / `… import CacheTraverseTarget`，**没有 try/except、没有纯 Python 回退**。所以删掉或改名那个 `.pyd` 只会把 `ImportError` 变成 `ModuleNotFoundError`。
4. **不是文件损坏**：8 个 `.pyd` 的 mtime 全是 `2026-09-28 18:00:17`、一个字节没变（评审者核）；复制到 `$env:TEMP` 后**仍被拒**（评审者核）→ **策略是按内容/签名判的，不是按路径**。
5. 环境：SQLAlchemy **2.1.1**（`sqlalchemy-2.1.1.dist-info`）、Python **3.11.1**、pip 22.3.1、**无 venv**（装在 `C:\Python\Lib\site-packages`）。

**⚠️ 时间线**：**本会话内控制者成功跑过全量三次**——Task 2 fr2 亲验 `531 passed in 55.89s` 与 `441/Miss 0/120/BrPart 0/100%`（`530 passed, 1 skipped`），以及更早的 `528` / `481`。**阻塞是在那之后、收尾评审期间才出现的**，即 Smart App Control 的判定在本会话中途发生了变化（云端信誉评估可以这样翻转）。

**影响**：
- **Task 2 无法做 fix round 3**（7 条 Important + 10 条 Minor 全是散文修正，改完必须验「531 passed 一字不变」，而现在跑不了）
- **Task 3–12 全部无法开工**（每个 Task 的验收都要求全量测试 + domain 覆盖率）
- 已经跑不动的还包括：任何 DB 层验证、`sync_exercises` 的幂等验证、变异验收

**代码状态是安全的**：HEAD `1191170`、工作树干净、Task 2 的三轮全部已提交；**Task 2 的行为面在环境坏之前已由控制者与评审者双向验证过**。审计链已入库（Ruling 118），故不会再因 IDE 缓存写回而丢失。

**解除阻塞的选项（都需要用户动手，控制者无权也不应代做）**：
1. **关闭 Smart App Control**：设置 → 隐私和安全性 → Windows 安全中心 → 应用和浏览器控制 → 智能应用控制设置 → 关闭。⚠️ **Windows 11 上这是单向的**：关掉之后除非重置/重装系统，否则无法再打开。
2. **换一个 SQLAlchemy 补丁版本**（不同的 `.pyd` 构建 → 不同哈希 → 可能过信誉评估）。本仓按 2.1 API 写，**只能在 2.1.x 内换**；换 2.0.x 有破坏风险。这是**唯一可能可逆**的选项，值得先试。
3. **企业 WDAC 策略给该文件加白名单**——Smart App Control 官方**不支持用户级排除项**，通常需要域管理员，多数环境不可行。
4. **新建 venv 重装**——同一个 wheel 的字节相同、哈希相同，**大概率同样被拦**（第 4 点的诊断已表明是按内容判的）。

**→ 补硬规矩 #72：跑测试之前先确认「测试真的能跑」——`python -c "import sqlalchemy"` 这类一行冒烟检查，比事后从 12 条收集错误里反推根因快得多。** 依据：Ruling 121。收尾评审者做了正确的事（停下来报告、不绕过、不伪造绿），**这个处置本身要保留为规矩：环境坏了就停下报告，绝不为了「交差」去改 site-packages、装别的版本、或塞 stub——那会让「我跑出来的绿」与被评审的代码脱钩。**

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 预检 5 次（#94–#98）、Task 2 实现轮 7 次（#99–#105）、fr1 4 次（#106–#109）、fr2 5 次（#110–#114）、**收尾评审 6 次（#115–#121，其中 #115 是 P2-A4 的出处错、#116–#118 是派单的三个行数、#119 是评审包的断言性标题、#120 是账本 P2-D4 的行号、#121 是账本 P2-A4 的传播）** = **Plan 02 累计 60 次**；Plan 01 60 次，**合计 120 次**。
（⚠️ 编号说明：Ruling 119 里 CE-1/2/3 记 #116/#117/#118、CE-4/5 记 #119、CE-6 记 #120、CE-7 记 #121；而 Important 5 那条账本出处错记 **#115**。故本轮新增 **#115–#121 共 7 条**，Plan 02 累计 **33+5+7+4+5+7 = 61**、总 **121**。上面那行「60 / 120」是控制者算错的版本，**以本行为准：Plan 02 累计 61 次、合计 121 次**——这正是硬规矩 #66 说的「计数要逐个核」，控制者在写自己错误计数的时候又算错了一次。）

Task 2: 收尾评审完成（**Approved with findings**，0 Critical / 7 Important / 10 Minor），评审产物已入库（`1191170`）。**⛔ 因 Ruling 121 的环境阻塞，Task 2 的 fix round 3 与 Task 3 全部暂停，等用户解除 Smart App Control 的拦截。** 代码基线 `966eae0`、含审计链基线 `1191170`。

#### Task 2 fix round 3 — 控制者亲验（commit `c29bc69`，**531 passed 不变**）→ **Task 2 结案**

**判定：7 条 Important + 10 条 Minor 全部落地；实现者另报出控制者错误 2 条（均成立）与评审者错误 2 条（均成立）。控制者亲验其全部承重项。**

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 531 passed | `cd backend; python -m pytest -q` | **531 passed in 56.16s** ✓（与基线一字不差，本轮不增删测试函数） |
| 改动面 | `git diff --name-status 2df6825 c29bc69` | 11 个文件、`856 insertions / 50 deletions` ✓ |
| **YAML 只改注释** | `git diff -U0 -- backend/data` 后逐行分类 | **`+54 / −10`，非注释的 `+` = 0、非注释的 `−` = 0** ✓ —— **数据行一个字节没动** |
| YAML 数据不变量 | 自己 `yaml.safe_load` 实算 | 动作 **23** ✓、映射 **10** ✓、`version` **`'1.0'`** ✓、`volume_reduction` **`{bmi_over_30: 0.8, muscle_low_p10: 0.9}`** ✓、升档 **0** ✓、悬空 ref **0** ✓、5 个 `high` 全有 `low` 等价物 ✓、URL 全是 `.invalid` 占位符 ✓、**distinct `to` = 4**（正是 I3 要改的那个数）✓ |
| 三个指纹 | 自己算归一化 sha256[:16] | CSV **`21412 B / CRLF 0 / D2C8E539E2FA0029`**（**一个字节未动**）✓；`exercises.yaml` **`17609 B / CRLF 0 / 63033BBD7F68CC1F`**；`exercise_equivalence.yaml` **`8245 B / CRLF 0 / 822CB86A5E998301`** ✓ |
| 指纹常量联动 | 读 `test_refdata_prescription.py` | `:69` `EXERCISES_FINGERPRINT = "63033BBD7F68CC1F"`、`:72` `EQUIVALENCE_FINGERPRINT = "822CB86A5E998301"`，**与磁盘实算值逐字相同** ✓；**三个旧值（`A6A000F58815FCBB` / `0FFB881574AC04F3` / 中间值 `AA2BE3D26D1B3B1E`）全仓 0 残留** ✓ |
| spec 只改一格 | `git diff --numstat -- Document` + `-U0` 的 hunk 头 | **`1 insertion / 1 deletion`、hunk `@@ -933 +933 @@`** ✓；文件仍 **974 行 / 974 CRLF / 纯 CRLF** ✓ |

**Ruling 123（CE-fr3-1，成立，控制者错误 #122）— 派单 §2.3 说两个指纹常量在 `test_refdata_prescription.py:53` / `:56`，实测在 `:69` / `:72`。**

亲验：`:53` 是 `from app.domain.prescription.exercises import (`、`:56` 是 `    IMPACT_RANK,` —— 那是 fr1 搬迁之后新增的 import 块。**`:53`/`:56` 是 `3ea27cc`（Task 2 主体）上的位置**，`966eae0`（fr2）往上加了内容把它们推到了 `:69`/`:72`。

**根因值得单独记**：这两个行号**不是我这轮现查的，是我从三轮前自己那次亲验的输出里直接抄下来的**（当时的输出确实印着 `53| EXERCISES_FINGERPRINT = "A6A000F58815FCBB"`）。**而 `task-2-review.md`（我让实现者读的第一份必读文件）里写的是正确的 `:69`/`:72`——我在派单里与自己指定要读的那份文档互相矛盾。** 这是硬规矩 #61 的正靶心，也是控制者错误 #116–#118（收尾评审 CE-1/2/3，三个文件行数全错）的**同型第四次**。
**→ 硬规矩 #61 扩写：复用「历史输出里的行号」等同于手写行号——必须重查。派单里每一个 `文件:行` 都要在**发出前的那一次**脚本运行里现取。**

**Ruling 124（CE-fr3-2，成立，控制者错误 #123）— `.gitattributes` 的注释说「`task-2-report.md` 与 `progress.md` 纯 CRLF」，而 `task-2-report.md` 是 MIXED。**

亲验（Ruling 118 落地补记第 2 步）：`progress.md` 纯 CRLF ✓、`task-1-report.md` 纯 LF ✓、**`task-2-report.md` MIXED（CRLF 946 + 裸 LF 23）**。**即账本记的是对的、`.gitattributes` 的注释是错的，两者自相矛盾**——而它们是我在同一轮里先后写的。`-text` 属性本身无需改（它正是要保持各文件现状）。**另：`task-2-brief.md` 也是 MIXED（150 CRLF + 9 裸 LF），注释里没提。**

**Ruling 125（评审者的两条错误，实现者查出，控制者采信）**
- **RE-fr3-1（成立，Minor）**：`task-2-review.md:257` 说「`repr()` 是 **27**」，实测 `len(repr(ImpactLevel.HIGH))` = **26**。**不影响 I1 成立**（`str()` 16 / `repr()` 26 / `.value` 4，三个都给不出散文里那个 19）。→ 记**评审者错误 #3**（前两次在 Plan 01 终审）。
- **RE-fr3-2（finding 成立、建议措辞不成立）**：Minor 4 的建议「`:487` 与两个 addon 模块名（`:482`/`:484`）合计点名的 12 项」**会把「能量消耗模块」数两次**（`:487` 的散文里已经点了它）。实现者没照抄，改用精确算术落地（「散文 12 项 − 可选挑战任务 + 抗阻优先模块（`addons`）= 本文件 12 项」）。**→ 记评审者错误 #4，并记一条做法：评审者的「建议修法」与「finding」要分开对待——finding 要核，建议只是建议。**

**Ruling 126（实现者的两处「不照字面办」，控制者裁定都对）**
- **I2 的统一口径**：派单说「统一成 `exercises.py:94-96` 那个说法」，但那句**为真而不完整**（漏了 fr2 新增的那条守卫）。实现者把三处统一成**同一个完整的两支清单**，并给出回退办法。**裁定：接受。** 这正是硬规矩 #66 要求的（同类陈述逐个更新，而不是把一个不完整的版本复制到三处）。
- **主动收紧「更正说明」的写法**：它发现自己在 8 处「更正说明」里**逐字引用了被撤销的原句**，于是 `git grep "改坏任何"` / `"Ruling 19"` / `":163"` 这类**串查复核会照样命中**，硬规矩 #48 的「旧串残留 = 0」闸门**判不出来**。故加做第二趟（11 处）把复述改成描述式，只保留 2 处必要的复述。
  **裁定：接受，并升级为硬规矩。**
  **→ 补硬规矩 #74：写「更正说明」时不得逐字复述被撤销的原句（除非那一句正是要显式否定的对象，例如 spec §14 第 28 项的「#29–#35」）。** 依据：**逐字复述会让「旧串残留 = 0」这个落盘闸门失效**——闸门查的是串，而更正说明里留着同一个串，于是「改了」与「没改」在闸门眼里一模一样。这是硬规矩 #48 与 #52 之间的一个盲区，本轮由实现者自己发现。

**Ruling 127（实现者 7 条关切的处置）**
1. **fr3 取证脚本放在 `$env:TEMP\sdd_fr3\`（仓库外）**，因为仓库里的 `fr3_probes/` 名字已被 Task 1 占用 → **控制者已代为入库**：34 个文件里去掉 `__pycache__` 与 `backup/`（127 KB 的旧报告快照，已无价值）后，**22 个脚本拷进 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t2fr3_probes/`**。**命名约定记下：Task N 的 fix round M 的探针目录叫 `t{N}fr{M}_probes`**，避免与 Task 1 的 `fr{M}_probes` 撞名。
2. **账本 P2-A4 的错引用仍在**（按派单归控制者改）→ **已改**（见本轮更正）。**实现者的理由成立且要紧：Task 3 的模板加载器同样要处理 `targets` 取值域，不先勘误账本会是第三次传播。**
3. **`.gitattributes` 注释与账本矛盾** → 见 Ruling 124，**已改**。
4. **I7 改后那一格仍引计划行号**（只做到绑 commit `2df6825`）→ **接受**。理由成立：那一格是给项目负责人看的清单，写成四条 `git grep` 可读性太差；**且它同时在格子里写了那四处的逐字原文片段，行号过期仍找得到**——这正是 fr2 对 CE-7 定的修法（先给可 grep 的原文、再给绑定 commit 的行号）。→ 转 Task 12 的清单：落地时换成可 grep 描述。
5. **一处报而未改**：`test_impact_rank_values_are_pinned_verbatim` 的 docstring「今天看着它的本来只有**两条间接**守卫」缺「本条之前」这个时点（当前是三条）→ **转 Task 3 的散文清扫清单**（与 Minor 同源，评审者没点、本轮没授权）。
6. **报告落盘自证**（备份 127 827 B / sha `6F1851079C3F6031`，追加后 196 317 B，三道回读核对全绿：前缀关系 / 双向串查含「查询本身有效」的对照 / 加法自洽 `196317 == 127827 + 68490`、`1582 == 946 + 636`、`23 == 23 + 0`）→ **这是硬规矩 #68 修订版第 2 条的标准执行样例，保留为做法。**
7. **`exercises.yaml` 与 `exercise_equivalence.yaml` 的注释体量涨了不少**（13358 → 17609 B、7841 → 8245 B）→ **接受**。这两个文件是「体育专家可独立审校」的知识资产（File Structure `:63`），注释里写清每个动作的出处、每个系数的无出处声明、每个数值的工程约定属性，**正是硬规矩 #19 要的东西**。**但指纹跟着变了**，故 Task 3 若追加 ref，必须同步 `EXERCISES_FINGERPRINT`——这条已在实现者上一轮写的「Task 3 追加 ref 的 5 项连带清单」里。

---

## ✅ Task 2 结案（动作库）

**commit 链**：`3ea27cc`（主体，481 → 528）→ `c21767d`（fr1，Ruling 96 的架构搬迁）→ `966eae0`（fr2，Ruling 106/107 的散文修正 + 3 条新守卫，528 → 531）→ `c29bc69`（fr3，收尾评审的 7 Important + 10 Minor）+ 控制者的 7 个 doc/chore commit（`fb5bddb` 预检更正 / `d40f36c` §14 重排 / `4386ee2` File Structure / `8e6a38f`+`23325de`+`23388c7`+`7c5aff8` 审计链入库 / `1191170`+`31c9212`+`2df6825` 账本）。

**交付**：`exercise` 表（第 15 张）、`exercises.yaml`（**23 个动作**）、`exercise_equivalence.yaml`（**10 条映射** + `version "1.0"` + `volume_reduction`）、`app/domain/prescription/{__init__,templates,exercises}.py`、`app/refdata_prescription.py`（`load_exercises` / `exercises` / `load_equivalence` / `equivalence` / **`sync_exercises`**）、`tests/test_refdata_prescription.py`、`tests/domain/test_prescription_templates.py`、spec §14 第 **28** 项。

**测试**：Task 1 结案 **481** → Task 2 主体 **528** → fr2 **531** → fr3 **531 不变**。
**覆盖**：`app/domain/` **441 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**（Task 1 结案是 399/114）。
**表数**：14 → **15**。
**fix round**：**3/5**（未用满）。**Critical 始终 0**——收尾评审的 7 条 Important 全部是「印在源码里的陈述与实测不符」，**没有一条是行为缺陷**。

**安全属性（控制者与评审者双向独立验证）**：10 条映射**升档 0 / 超 `max_impact` 0 / 悬空 ref 0**；**5 个 `high` 动作全部有 `low` 等价物**；23 个视频 URL **全是 `.invalid` 占位符**、无编造真链接；`volume_reduction` 的两个系数**在 spec 里无出处**这一事实已同时登记在 YAML 注释与 spec §14 第 28 项。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 预检 5 次（#94–#98）、Task 2 实现轮 7 次（#99–#105）、fr1 4 次（#106–#109）、fr2 5 次（#110–#114）、收尾评审 7 次（#115–#121）、**fr3 2 次（#122/#123，Ruling 123/124）** = **Plan 02 累计 63 次**；Plan 01 60 次，**合计 123 次**。
**实现者 3 次**（Plan01 Ruling 80、Task1 Ruling 52、Task2 的 `dict` vs `Mapping`）——**全部自纠**；另 Task 2 fr2/fr3 各有一批自纠（fr2 5 条、fr3 若干），其中两条是被它们自己写的 `assert` 拦下的。
**评审者 4 次**（Plan 01 终审 2 次 + 本轮 RE-fr3-1/RE-fr3-2）。**复审者 1 次**。**Task 2 收尾评审者 0 次**（但它的 2 条错误由 fr3 的实现者查出）。

**新增硬规矩**：#72（跑测试前先冒烟）、#73（每轮记下依赖版本）、**#74（更正说明不得逐字复述被撤销的原句，否则落盘闸门失效）**。**#61 扩写**（复用历史输出里的行号等同手写，必须重查）。

**⚠️ 带进 Task 3 的清单**（累积）：① `cases` 矩阵换成「扫真仓每个 `.py` 与 `resolve_name` 对拍」（Ruling 56 / 66，可一次性解决 Ruling 54/56/67）② `_package_of` 的断言换成扫真仓与 `py.relative_to(BACKEND).parent.parts` 对拍（C-fr4-1）③ `lookup()` 的分支测试搬到 `tests/domain/test_prescription_exercises.py`（Ruling 107-1）④ `templates.py` 是 **Modify 不是 Create**（P2-B1）⑤ `impact_level` 的所有者是 `exercises.yaml`，**模板加载器必须校验 block 的 `impact_level` 与动作库一致**（P2-B2）⑥ Task 3 追加 ref 要同步 `EXERCISES_FINGERPRINT` ⑦ `prescription/__init__.py` 与 `templates.py` 的 `__all__` 是两份、必须一起改 ⑧ `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点（Ruling 127-5）⑨ Plan 02 新表**不进 `models` 公有导入面**（Ruling 97）⑩ 若 `match.py` 写 `level == 2` 相对导入，全仓计数 15 → 16、level 分布变 `{1:15, 2:1}`，fr2 改过的那几段散文要再更新。

Task 2 结案。**下一步：Task 3（18 套模板 YAML + `prescription_template` 表 + 加载器）预检。** 代码基线 `c29bc69`、SQLAlchemy **2.1.3**、**531 passed**、domain **441/120/100%**、**15 张表**。

---

### Task 3: 18 套模板 — 预检扫描（Pre-flight，控制者亲跑）

**基线**：`436926a`（代码基线 `c29bc69`），531 passed，domain 441/120/100%，15 张表，SQLAlchemy 2.1.3。
**方法**：硬规矩 #49——逐条核计划对既有代码与 spec 的每一项断言。全部证据来自控制者本机 shell 实跑（脚本 `.superpowers/sdd/_pf3.py`，跑完删除）。

#### A. 计划文本需更正的事实（**11 处已落盘，其中 1 处 Critical**）

**P3-A1（Critical，已更正）— Task 3 的 Create 清单里有 `backend/app/seed/prescription.py` 的模板 seed，与 Global Constraint #10 及两道既有守卫直接冲突。**

**这与 Task 2 的 P2-A1 是同一个缺陷**——控制者在 Task 2 预检时查出来并裁了（改用 `refdata_prescription.sync_exercises`），**却没有把裁定传导到 Task 3**。亲验：`app/seed/prescription.py` 今天不存在 ✓、`app/seed/` 仍是那 8 个文件、`tests/seed/test_generate.py:483/484/496` 的三分区是 `ORGANISATION_TABLES`(5) + `DATA_TABLES`(9) + `REFERENCE_TABLES`("exercise",)，`:519` 的 `assert count == 0` 守卫仍在。→ **裁定：照 Task 2 的先例，用 `refdata_prescription.sync_templates(session) -> int`。**

**⚠️ 这条是本轮最该记的**：P2-A1 的裁定写在账本里、也写进了计划 Task 2 的 Step 5，**而 Task 3 的 Files 段是 `e26347f` 就写好的、预检 Task 2 时我读到过它却没往下想一个 Task**。**→ 补硬规矩 #75：预检某个 Task 时，凡裁定改变了「一类做法」（而不是某一处文字），必须 grep 计划全文，把同一类做法在**后续所有 Task** 里的出现处一并更正。** 依据：P3-A1（`app/seed/` 那一条在 Task 2 与 Task 3 各出现一次，我只改了一处）。这与硬规矩 #51（两份重复的守卫逐份修）、#66（同类计数逐个更新）是同一条纪律的第三个变体：**对象从「代码副本」「陈述副本」扩到「计划里的做法副本」**。

**P3-A2（Important，已更正）— Create 清单里的 `backend/tests/domain/test_prescription_templates.py` 已经存在**（Task 2 建的：11 248 B / 153 行 / 4 条测试），故是 **Modify**。

**P3-A3（Important，已更正）— `:266` 与 `:293` 都说「在 spec §14 补一项」，而这两项的编号 `d40f36c` 已经分配掉了**：**#29 = 模板审校状态**、**#31 = speed_flexibility 参数空洞**（都在计划 `:688` 的 Task 12 清单里）。**这是 §14 编号第二次差点撞车**（第一次是 Task 2 的 #28，账本 Ruling 92）。→ 裁定：**Task 3 直接写 #29 与 #31**（按 P2-A3 的「值在哪一刻被写死就在哪一刻登记」），**Task 12 Step 3 的清单从 6 项减到 4 项**（`#30 / #32 / #33 / #34`）。总数仍是 `27 + 1(T2) + 2(T3) + 4(T12) = **34**`，与「计划完成后的状态」那段一致。**控制者已同步更正 Task 12 的 `:682` 与 `:688`**（硬规矩 #75：一个事实出现在两处就要改两处）。

**P3-A4（Important，已更正）— 黄层 addon 的 `energy_expenditure_plus_5min_hiit` 不在动作库里。**

亲跑 `exercises.yaml` 的 23 个键：有 `hiit`、有 `energy_expenditure_plus_10pct`、**没有 `energy_expenditure_plus_5min_hiit`**。→ 裁定：**Task 3 追加它**（计划 `:183` 明确授权），**不要复用 `hiit`**——`hiit` 是有自己 `impact_level` 的**主项动作**，而「附加 5min HIIT」是**体成分异常时追加的模块**；混成一个 ref 会让 Task 7 的安全后置无法区分二者。连带：同步 `test_refdata_prescription.py:69` 的 `EXERCISES_FINGERPRINT`（当前 `63033BBD7F68CC1F`）、保持 CRLF = 0。

**P3-A5（Important，已更正）— 「每个 `String(n)` 都要过 Plan 01 的列宽遍历测试」是 P2-A5 的同型过度承诺。**

亲验 `test_models.py:331-378`：`_in_domain_columns()` 自描述、但**只看得见带 `_in_domain` CHECK 的列**。`prescription_template` 的 6 个 `String(n)` 列里 `layer` / `weakness` / `body_comp` / `review_status` 有 CHECK（自动覆盖），**`template_ref` 与 `version` 没有 → 完全不被覆盖**，要另写断言。
**控制者实算的宽度余量**：`layer` 6/8 ✓、`weakness` **17**/20 ✓、`body_comp` **8/8（零余量）**、`review_status` **8/8（零余量）**、`version` 3/8 ✓。**两个零余量的列值得在注释里点明**——将来往词表里加一个更长的值就会静默截断（硬规矩 #18 的原话是「严格长度的后端会静默截断」）。
**另：`template_ref` 的宽度取决于 `template_id` 的命名，而 spec §7.2 `:454` 已经给了格式**——YAML 骨架第一行是 **`template_id: RED-END-ABN-01`**（`<层3>-<桶3>-<体成分3>-<序号2>`，**14 字符**）。→ 裁定照 spec 这个格式，则 `String(32)` 余量 18 字符；若另起 snake_case（`yellow_speed_flexibility_normal` = **31** 字符）就逼近上限、且与 spec 的字面骨架不符。

**P3-A6（Important，已更正）— 本 Task 会撞红四处「字面钉死」的基线断言，计划一个字都没提。**

控制者实跑定位（这是 Task 3 开工第一天就会撞上的四条红）：
1. `tests/test_refdata_prescription.py:858` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**7 个名字**）+ `:917` 的 `assert len(...) == 7`
2. `tests/test_refdata_prescription.py:951-952` 的**两条负向断言**，其中第一条**字面点到 `"Template"`**：`assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE + ["Template"]`。**它是 Task 2 fr2 为证明「基线不是当前值减一」而写的反面对照**；本 Task 真的加了 `Template` 之后，**这条断言的用意要重新想**（它想挡的是「把基线写成当前 `__all__` 再去掉一个」，不是「永远不许有 `Template`」）。
3. `tests/domain/test_prescription_templates.py:152` 的 `assert templates.__all__ == ["ImpactLevel"]`（同文件 `:149` 已写了警告「两份 `__all__` 要一起改」）
4. `tests/seed/test_generate.py:542` 的 `assert REFERENCE_TABLES == ("exercise",)`（而 `:496` 是定义处，**改一处必须改两处**）

**四处都是硬规矩 #35 的正确产物**（字面写死、不从被测对象反推），所以它们红意味着「基线该更新了」而不是「守卫太紧」。**但更新时必须保持「字面写死」这个性质**——尤其 `_PRESCRIPTION_PUBLIC_BASELINE`：新基线仍必须是字面清单，不能改成 `list(prescription_pkg.__all__)`（那就两侧同源了）。
**另**：`test_templates_module_still_reexports_impact_level` 是 `templates.py` 那 2 条语句进 domain 覆盖率的**唯一途径**（Ruling 103 / 硬规矩 #67：删掉它 → `Miss 2`、覆盖率跌破 100%、`pytest` 退出码仍 0）。本 Task 加了 8 个 dataclass 后那个脆弱性会自然消失，**但那条守卫不许删**——它守的是 re-export 本身。

**P3-A7（Important，已更正）— Step 7 的变异 ①「把 `review.status` 改成 `pending`」在本 Task 内没有任何可观测后果，因此不是变异测试。**

原文自己就写了「加载器仍应成功加载」「本 Task 先只验加载，匹配在 Task 4 验」——**即变异前后行为完全相同**。**这是硬规矩 #65 的正靶心**（一条变异判据必须指明「哪个断言分支」会开火）。→ 改成可观测的版本：变异后必须有一条断言变红，钉的是「加载器**如实保留** `review_status`、不静默把 `pending` 当 `approved`」；建议用 `tmp_path` 下的**合成 YAML**（不动那 18 个被指纹钉住的文件）。**「匹配器拒绝 pending」整条归 Task 4**（spec §7.2 `:451` 原文：「`review.status != approved` 的模板拒绝用于生成」）。

**P3-A8（Minor，已更正）— `:268` 那整段「喂给匹配器」是 Task 4 的活，被错放进了 Task 3。**

匹配器（`match.py`）是 Task 4 才建的。→ **拆开**：归 Task 3 的是「证明构造一个 `review_status=PENDING` 的 `Template` 是**可能的**」（frozen dataclass 不在构造期校验、`pending` 是合法枚举值），这样 Task 4 才有东西可喂；归 Task 4 的是变异测试与那条单元测试。**已记进 Task 4 的预检清单。**

**P3-A9（Minor，已更正）— `:294`「给 spec §7.2 加勘误」与 Task 12 Step 3 的「spec 勘误」重叠。** → 裁定归 **Task 3**：写这 4 套模板的人正是撞见空洞的人，隔 9 个 Task 再补勘误会让 YAML 注释里的「见 spec §14 第 N 项」长期指向一个不存在的条目。**Task 12 Step 3 的清单相应减一项。**

**P3-A10（Minor，已更正）— `reachable` 不在 spec §4.4 `:238` 的字段清单里。**

亲验 spec `:238` 原文：「`prescription_template` | id、层、主导短板、体成分（共 18 行）、**YAML 路径**、版本、`review.status` ∈ {`pending`, `approved`}、审校人、审校时间」——**没有 `reachable`**。它的依据是 **spec §7.1 `:447`**：「生成器对这 3 套标记 `reachable: false`，不参与匹配」。→ 这是一列**超出 §4.4 的增补**，要在 P3-A9 那条 §7.2 勘误里一并交代，不要让它看起来像 §4.4 的原文。
**顺带核实 `:306` 的断言为真**：spec §4.4 确实说的是「**YAML 路径**」，而计划决定用 `template_ref`（逻辑 id）——**这个偏离是有意的、且理由成立**（路径会随目录结构变，`template_id` 是 YAML 内容的一部分、已被指纹钉住）。

**P3-A11（核对通过，无需更正）**
- `:255`「复用 `app.domain.stratify.Layer`」→ 实跑其成员 `RED="red"` / `YELLOW="yellow"` / `GREEN="green"` / `INSUFFICIENT="insufficient_data"`，**与计划写的一致** ✓
- `:256` 的漂移测试公式 `{b.value for b in WeaknessBucket} == set(ITEM_BUCKET.values()) - {None}` → **正确**（`ITEM_BUCKET` 的 distinct values 是 4 个含 `None`，减掉才是 3 个桶名；这正是 P2-A4 的口径）✓。且这是**跨所有者对账**（`WeaknessBucket` 与 `ITEM_BUCKET` 是两个独立声明者），**不违反硬规矩 #35** ✓
- `:273`「键集字面写死 18 个 `template_id`」✓、`:280` 指纹方案留给实现者选并说明理由 ✓、`:279` 的 `impact_level` 漂移守卫 ✓（与 P2-B2 的裁定一致：`exercises.yaml` 是所有者，模板里照 spec 字面形状写、由加载器校验一致）
- `:285-287` 引的 spec §7.2:487 **逐字相符** ✓（控制者实读 spec `:487`）
- spec §7.1 `:441-447` 确认 `3×3×2=18`、`(green,*,abnormal)` 3 套不可达、标 `reachable: false` 不参与匹配 ✓
- spec §7.2 `:465` 的「红 4 / 黄 3 / 绿 2（指导文件原文）」、`:479` 的 `[1.00, 1.05, 1.10, 0.85]`、`:480-484` 的 addons → **行号与内容逐字相符** ✓
- `:249`「`== 15` 同样有 **3 处**」→ 实跑在 `:169` / `:236` / `:494` ✓（函数名 `test_all_fifteen_tables_created` 在 `:24`，`:492` 另有一处注释引用）

#### B. 任务对之间的冲突

**P3-B1** — `templates.py` 是 **Modify** ✓（`4386ee2` 已更正过 File Structure 与 Task 3 的 Files 段）。但 **fr2 那条守卫钉住了 `templates.__all__ == ["ImpactLevel"]`** → 已并入 P3-A6 第 3 项。
**P3-B2** — `refdata_prescription.py` 本 Task 加「模板加载部分」+ `sync_templates`。Task 2 已按 P2-B3 把模块 docstring 写成「本模块分两段」，**本 Task 是第二段落地**，不要重写整个 docstring、只补模板那一段。
**P3-B3** — `prescription/__init__.py` 的公开面本 Task 会从 7 个名字扩到 7+N 个 → 已并入 P3-A6 第 1/2 项。**⚠️ 两份 `__all__`（`__init__.py` 与 `templates.py`）必须一起改**，这句话 Task 2 已经写在那两个文件的 docstring 里了。

#### C. 各任务自身自洽性

**P3-C1** — Step 7 的变异 ②「删掉一个 `exercise_ref` 对应的动作 → 引用存在性测试红」：⚠️ **动作库被指纹钉住**，删一个动作会让 `EXERCISES_FINGERPRINT` 也红。控制者在 Task 2 亲跑过这个变异（删 `bodyweight_resistance` → **4 红**，含 `test_equivalence_table_only_maps_to_existing_exercises` 等三条跨文件守卫）。**故这条变异在本 Task 会得到「引用存在性测试红 + 指纹测试红 + 可能还有等价表守卫红」，不止一条**——**报告里要指明哪一条是这条变异的目标判据**（硬规矩 #65 第 ① 项：不要笼统说「哪条测试红」）。
**P3-C2** — `:298`「每套模板的 `sessions` 天数 = `weekly_frequency`」与 `:273` 的全笛卡尔积断言 + `:276` 的 `{red:4, yellow:3, green:2}` 三者一起，**18 套的 `sessions` 总数是 `3×2×4 + 3×2×3 + 3×2×2 = 24+18+12 = 54`**（控制者算的，**实现者要自己复核**）。这是一个可以一次性验掉「18 套都写全了」的强不变量，建议加进测试。
**P3-C3** — spec §7.2 的 YAML 骨架里 `review:` 与 `progression:` 是**嵌套块**（`:460-463` 与 `:478-479`），而计划的 `Template` dataclass 把它们**摊平**成 `review_status` / `reviewer` / `reviewed_at` / `week_deltas`。**加载器必须做这个摊平**，而 `:281` 的 6 种坏形状里没有「嵌套块缺失」这一种 → 建议加第 7 种。

#### D. Global Constraints 冲突

- **D1 = P3-A1**（`app/seed/` 冻结）——已裁定。
- **D2 → 升级为 Critical，已更正计划（P3-D2）**：`backend/data/prescription/*.yaml` 是新目录，而 `.gitattributes:14` 的 `backend/data/*.yaml` **只匹配 `data/` 根、不匹配子目录**（gitattributes 的 `*` 不跨 `/`）。**控制者原先写「这一句需要实现者亲验」（因为那个目录还不存在），但随后用一条假想路径 `backend/data/prescription/RED-END-ABN-01.yaml` 亲跑了 `git check-attr`——`check-attr` 不要求文件存在**：

```
$ git check-attr text eol -- backend/data/exercises.yaml
  backend/data/exercises.yaml: text: set      eol: lf
$ git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml
  …/prescription/RED-END-ABN-01.yaml: text: unspecified   eol: unspecified
```

**故计划 `:250` 那句「不需要改 `.gitattributes`（同 P2-A7：已经覆盖）」是假的**，必须加 `backend/data/**/*.yaml text eol=lf`。**后果是 Plan 01 国标评分表事故的原型**（硬规矩 #46/#47：`core.autocrlf=true` 下一次 checkout 就让工作树字节漂移、指纹测试变红），而 Task 3 的 18 个 YAML 会有大量中文注释，行尾混用还会让「按字节比对」的取证全部失真。

**⚠️ 方法论上值得记的一点**：控制者第一反应是「目录不存在，验不了，交给实现者」——**这是错的**。`git check-attr` / `git check-ignore` 都是对**路径模式**求值、不要求文件存在，所以「还不存在的路径」照样能亲验。**「验不了」在绝大多数情况下是「没想到怎么验」。**
**→ 补进硬规矩 #61 的适用范围：规则文件（`.gitattributes` / `.gitignore`）的覆盖面，必须用 `git check-attr` / `git check-ignore` 对具体目标路径亲验，不能靠读规则文本推断；且「目标路径还不存在」不是不验的理由。**
- **D3**：禁区四项不变；**18 个 YAML 一旦写下并被指纹钉住，Task 4–12 就都不许再改它们**（改了要同步指纹）——与 Task 2 的 `exercises.yaml` 同一条纪律。
- **D4（P3-D4，已更正）**：`templates.py` 引 `Layer` 与 `ImpactLevel` 时，**绝对导入 vs 相对导入的选择会影响 Task 1 fr5 埋的那一格绿档是否从「前瞻」变成「真仓形状」**（账本 Ruling 104）。控制者不裁定选哪个，但要求**保持一致、不要一半绝对一半相对**，并说明理由。

#### 预检小结

**12 处计划更正已落盘（P3-A1…A11 + P3-D2 + P3-D4），其中 2 处 Critical**：**P3-A1**（`app/seed/prescription.py`，与 Task 2 的 P2-A1 同型、控制者没把裁定传导过来）与 **P3-D2**（`.gitattributes` 不覆盖 `data/prescription/` 子目录，照原文做会重演 Plan 01 的指纹事故）；**5 处 Important**（A2/A3/A4/A5/A6/A7）。

**⚠️ 一个必须写下来的模式**：P3-A1 与 P3-A5 分别是 **P2-A1 与 P2-A5 的同型复发**——两条都是我在 Task 2 预检时查出来、裁了、写进了账本与 Task 2 的正文，**而 Task 3 的正文里同一个缺陷原封不动地躺着**。**根因是预检只看当前 Task**，而计划的 12 个 Task 是 `e26347f` 一次写成的、共享同一批错误假设。→ **补硬规矩 #75（定义见 P3-A1）；并且从 Task 3 起，预检必须多做一步：把本轮裁定「改变了某类做法」的部分，grep 计划全文找同类出现处。**

**控制者错误计数**：本轮预检查出的都是**计划编写期（`e26347f`）就存在的缺陷**，与 Task 2 预检的 P2-A1…A10 同源，故合并记 **#124**（一次预检不足，覆盖 12 处，**含 P3-D2 这条 Critical**——它是 `e26347f` 写计划时就没验过 `.gitattributes` 的覆盖面，而在 Task 2 预检写 P2-A7 时**又错过一次**：那一轮我亲验了 `backend/data/*.yaml` 存在、就顺手写下「已经覆盖 `backend/data/prescription/*.yaml`」，**把「规则存在」当成了「规则覆盖」**）；**P3-A1 单独记 #125**——因为它不是「写计划时没想到」，而是「**想到了、裁了、写在账本里，却没传导到下一个 Task**」，这是一个新的失效模式（→ 硬规矩 #75）。**Plan 02 累计 65 次，Plan 01 60 次，合计 125 次。**

Task 3: 预检完成（11 处计划更正已落盘 + Task 12 的 §14 清单已同步、1 处 Critical、2 条新硬规矩 #75），派发中。代码基线 `c29bc69`、531 passed、15 张表、domain 441/120/100%。

#### Task 3 实现 — 控制者亲验（commit `4af83bc` + `ab075d3`，531 → **581 passed**，15 → **16 张表**）

**判定：Task 3 交付合格；两处 Critical 裁定（P3-A1 / P3-D2）都被正确执行；实现者另查出计划与 spec 的一个更大空洞（Ruling 133），并抓出控制者 4 条错误。**

亲验清单（全部控制者本机实跑，脚本 `.superpowers/sdd/_w.py`，跑完删除）：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 581 passed | `cd backend; python -m pytest -q` | **581 passed in 64.03s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**、`580 passed, 1 skipped` ✓；`templates.py` **58 stmts / 0 branch**、`prescription/__init__.py` **4 stmts**（441 + 56 + 2 = 499 ✓，**branch +0**） |
| 表数 | `len(Base.metadata.tables)` | **16**，`prescription_template` 在 ✓ |
| 改动面 | `git diff --name-status c29bc69 ab075d3` | **14 M + 74 A**；**`-- backend/app/seed`、`-- national_standard_2014.csv`、`-- backend/data/seed` 命中 0** ✓（**P3-A1 的裁定被执行：`app/seed/` 一个字没动**）；`exercises.py` 与 `exercise_equivalence.yaml` **0 命中、逐字未改** ✓ |
| 18 个 YAML | 逐个读字节 | **18 个文件、CRLF 全部 = 0**、合计 **123 848 B** ✓ |
| **P3-D2 生效** | `git ls-files --eol -- backend/data/` + `git check-attr` | **23 行全部 `i/lf w/lf attr/text eol=lf`**（不合形状 **0** 行）；`check-attr` 对 `backend/data/prescription/RED-END-ABN-01.yaml` 返回 **`text: set` / `eol: lf`**（改前是 `unspecified`）✓ |
| 指纹联动 | 自己算归一化 sha256[:16] | `exercises.yaml` **22 739 B / CRLF 0 / `3DE598AF38631209`**，与 `test_refdata_prescription.py` 里的 `EXERCISES_FINGERPRINT` **逐字相同** ✓；`exercise_equivalence.yaml` 仍是 **8245 B / CRLF 0 / `822CB86A5E998301`** ✓；CSV 仍是 **21412 B / `D2C8E539E2FA0029`** ✓ |
| ref 数与列宽 | 自己 `yaml.safe_load` | **24 个 ref**（23+1）；最长 `energy_expenditure_plus_5min_hiit` = **33** ≤ `String(48)` ✓ |
| 18 格全笛卡尔积 | 自己聚合 | 18 个 id 全唯一；`{(layer, weakness, body_comp)}` **== 3×3×2 的完整笛卡尔积** ✓ |
| `weekly_frequency` | 自己按层聚合 | **red {4} / yellow {3} / green {2}** ✓（spec §7.2 `:465` 的指导文件原文） |
| `sessions` 总数 | 自己数 | **54**（red 24 / yellow 18 / green 12）—— **控制者预检算的 54 成立** ✓ |
| 3 套不可达 | 自己筛 | `GRN-END-ABN-13` / `GRN-SPD-ABN-17` / `GRN-STR-ABN-15`，**恰为 `(green, *, abnormal)`** ✓；三套各有 **2 个 session**（**内容齐全**，符合实现者对 spec §7.1 `:447`②「模板位已就绪」的解读）✓ |
| `week_deltas` / `microcycle_weeks` | 自己聚合 | distinct 只有 **`(1.0, 1.05, 1.1, 0.85)`**、`microcycle_weeks` 全是 **4** ✓（spec `:479`） |
| 审校三元组 | 自己聚合 | `review.status` 全 **`approved`**、`reviewer` 全 **`原型自审（占位）`**、`reviewed_at` 全 **`2026-10-06`**（**固定日期，不是 `date.today()`**）✓ |
| `version` 的类型陷阱 | 自己查 `type()` | 全 18 套的 `version` 都是 **`str`**（不是 float）✓ —— 实现者在 §7.2 勘误里点了这个 PyYAML 陷阱（`1.0` 不加引号会被解析成 float），**已正确规避** |
| 引用完整性 | 自己比 | 模板引用的 **18 个 `exercise_ref` 全部在动作库里**（悬空 0）✓ |
| **P2-B2 的双所有者守卫** | 自己逐 block 比 | **130 个 block 的 `impact_level` 与动作库逐条一致，不一致 0** ✓ |
| addons | 自己聚合 | red 有 `body_fat_over → energy_expenditure_plus_10pct` 与 `muscle_low → resistance_priority`；yellow 有 `body_fat_over → energy_expenditure_plus_5min_hiit` 与 `muscle_low → resistance_priority`；**green 全空** ✓（与 P3 预检的裁定一致） |

**Ruling 129（CE-1，成立，控制者错误 #126，⚠️ 复用历史行号第 5 次）— 派单 §5 给的 `test_models.py:169/:236/:494` 与 `:492` 是 `966eae0` 上的位置，代码基线 `c29bc69` 上实测是 `:176/:243/:501` 与 `:499`。**

控制者亲跑三个 rev 复核：

```
966eae0 (750 行)：:24 函数名 | :169 / :236 / :494 三处 == 15 | :492 注释引用
c29bc69 (757 行)：:24 函数名 | :176 / :243 / :501 三处 == 15 | :499 注释引用
HEAD    (774 行)：:24 test_all_sixteen_tables_created | :184 / :253 / :518 三处 == 16 | :516 注释引用
```

**「3 处」这个数是对的，三个行号全错。** 账本 P3-A11 还把它记成「核对通过 ✓」——**因为我只核了「有几处」，没核「在哪几行」**（硬规矩 #57 的形态：核了推论没核输入）。

**⚠️ 最刺眼的一点**：Task 2 fix round 3 已经在 `test_models.py:36-41` 写下了「**按可 grep 的原文找，不要按裸行号找**：`git grep -n "== 15" -- backend/tests/db/test_models.py`」这段注释——**防我这个错误的守卫，就印在我引用的那个文件里，而我在派单里照样给了裸行号**。这是硬规矩 #61 扩写（Ruling 123）之后的**第一次再犯**。
**→ 补硬规矩 #76：派单里不许出现裸行号；需要指位置时一律给「可 grep 的原文片段 + `git grep` 命令」，行号只能作为绑定 rev 的辅助信息且必须标注 rev。** 依据：CE-7（fr2）→ Ruling 123（fr3-1）→ 本轮 CE-1，**同一个失效形态连续三轮**。

**Ruling 130（CE-3，成立，控制者错误 #127）— P3-A9 裁定「§7.2 勘误归 Task 3、Task 12 清单减一项」，但计划 `:741` 的 Task 12 清单里「§7.2 加勘误」原封不动地留着。**

亲验：`§7.2 加勘误` 在计划里出现在 Task 3 的 `:328`（P3-A9 的裁定）**与 Task 12 的 `:741`** 两处。**同一件事两处归属**——这正是硬规矩 #75（裁定改变了「一类做法」时要 grep 计划全文找同类）与 #66（同类陈述逐个更新）要防的形态，**而 #75 是我在写 P3-A1 的裁定时刚立的，同一轮就违反了**（第 4 次「立规矩的当轮违反」，前三次：#56→Ruling 73、#55→Ruling 74、#58→Ruling 102）。**已改**（并把空洞范围一并更正，见 Ruling 133）。

**Ruling 131（CE-2 / CE-4，成立，控制者错误 #128 / #129）**
- **CE-2（Minor）**：派单说「Task 3 追加 ref 的 5 项连带清单」在 `task-2-report.md` 的 `## fix round 3` 节，实测在 **`:639-640`（主体报告 §7 第 9 项）**，fr3 从 `:971` 起。**指向了错的位置**（硬规矩 #55/#61 的同类，第 5 次）。
- **CE-4（Minor，方法论）**：派单 §5 的「待改文件」表**一行里混了两个口径而没标注**——`bytes` 与 `CRLF` 是**工作树**值、`行` 与 `sha16` 是 **blob（LF）** 值。实现者逐行核出「工作树 bytes == blob bytes + CRLF 行数」12 行全部成立、12 个 sha 全部匹配 blob。**表头写的是「read_bytes 口径」，而按 `read_bytes()` 直接哈希得到的是另一个值**（如 `refdata_prescription.py` 实为 `97CD375BF47B7089`，表里给的 `EE0279B00D4AFB1B` 是归一化后的）。**→ 补进硬规矩 #70：报 sha256 时必须写明是「裸字节」还是「行尾归一化后」，同一张表里不许混用两种口径而不标注。**

**Ruling 132（CE-5 / CE-6 / CE-7 / CE-8 的处置）**
- **CE-5（不成立）**：派单说「3 套 unreachable 要不要有完整 `sessions`，控制者没法替你定」——实现者指出 **spec §7.1 `:447`② 已经给了答案**（「分层规则未来若调整…**模板位已就绪**」，空壳不是就绪）。**它是对的、我那句是多余的推诿**；控制者的倾向与它一致，故结果无差。**不计控制者错误**（派单同时给了倾向与理由，没有造成误动作），但**记下这个形态：把一个 spec 已回答的问题包装成「留给实现者定」，是把预检没做完的代价转嫁下去。**
- **CE-6（不成立，正面确认）**：基线测试态、依赖版本、12 行字节数、`.gitattributes` 四条规则、`check-attr` 改前输出、`Layer` / `ITEM_BUCKET` / 动作库 23 键、`SCANNED_DIRS` 27、`git diff c29bc69..ddccba8 -- backend` 为空 —— **逐项实测相符**。
- **CE-7（歧义，不计）**：简报「202 行」在 LF 口径下成立（`split('
')` 口径 203）。**这是行尾口径的又一个侧面**，并入 Ruling 131 的 CE-4。
- **CE-8（歧义，不计）**：派单说加「8 个 dataclass」，实现者实加 **12 个公有顶层定义**（另加 `TEMPLATE_LAYERS` / `INTENSITY_TYPES` / `ADDON_TRIGGERS` 三个词表与 `is_reachable` 一个纯函数），故公开面 **7 → 20**。**四个新增的必要性它逐条给了理由**（词表是「合法取值」的唯一所有者、`is_reachable` 是 §7.1 `:445` 那条规则的唯一所有者）——**控制者采纳，且认为这比派单的「8 个」更好**：把 `reachable` 的判定规则做成一个纯函数，比让 18 个 YAML 各自写死布尔值更符合硬规矩 #3（单一所有者）。**派单说「8 个」是照抄计划 `:259-263` 的清单，没有算上词表与规则函数。**

**Ruling 133（实现者的新发现，控制者独立实算坐实，⚠️ 比计划已知的空洞大得多）— 整个黄层与绿层都没有任何强度数值。**

计划 `:285-289` 只把 `speed_flexibility` 桶（红/黄各 2 套 = 4 套）当成空洞，并给了处置「红/黄层的 speed_flexibility 模板用**该层已给出的强度区间**（红 60–70% HRmax、**黄层按耐力那套的量**）」。

**控制者独立实算 18 套 YAML 的 130 个 block**：
```
intensity.type distinct = ['hrmax_pct', 'none', 'onerm_pct']
按层 = { green: ['none'],  yellow: ['none'],  red: ['hrmax_pct', 'none', 'onerm_pct'] }
130 个 block 里 type == 'none' 的 = 82
```
**即黄层与绿层的全部 block 都没有强度数值**，而不只是 speed_flexibility 那 4 套。亲读 spec §7.2 `:487` 确认根因：它只给了**红层**的 `60–70% HRmax` 与 `70% 1RM`；**黄层**写的是「持续跑+台阶训练」「自重+弹力带抗阻」（**只有动作名**）、**绿层**写的是「兴趣球类/定向越野/功能性训练」（同样只有动作名）。

**→ 计划那句「黄层按耐力那套的量」引用的是一个不存在的量。** 这是 **P2-A2 / P2-A3 那个「借自本仓（或 spec）另一处真实机制」形态的第三次发生**，而前两次都在 Task 2 预检时被查出来了——**这一处藏在 Task 3 的 Step 2-5 正文里，预检时我核了 `:487` 的引文逐字相符（P3-A11），却没核「黄层按耐力那套的量」这半句是否有出处**。核了引文、没核基于引文的推论，**又是硬规矩 #57 的形态**。

**处置**：实现者的做法**正确**——12 套写 `{type: none}`、**不编造运动生理学参数**（Global Constraint 与计划 `:292` 的第 1 条都是这个意思），并把这个空洞写进 spec §7.2 的 6 条勘误之一。控制者已把计划 `:741` 一并更正（原文只说「指明 `speed_flexibility` 桶的参数空洞」，**范围被低估**）。**⚠️ 这直接影响 Task 5 与 Task 6**：`intensity.py` 的 HRmax 换算与 `assembler.py` 的第 2 步「模板给百分比 → 装配为个体绝对 bpm 区间」**对 82 个 block 无输入可用**，两个 Task 都必须显式处理 `type: none`（渲染成文字建议而不是绝对区间）。**已记进 Task 5 / Task 6 的预检清单第一项。**

**Ruling 134（实现者 9 条关切的裁定）**
1. **「带进 Task 3 的清单」10 项只做了 5 项，①②③⑧ 没做**（要改 `tests/architecture/*` 或新建 `tests/domain/test_prescription_exercises.py`，超出简报 Task 3 的 Files 段授权）→ **裁定：转 Task 4 预检清单**。理由：Task 4 建 `match.py`（domain 下又一个新模块），会**再次改变架构守卫的扫描面与相对导入计数**，那正是把 `cases` 矩阵换成「扫真仓逐个对拍 `resolve_name`」、把 `_package_of` 断言换成「扫真仓与 `parent.parts` 对拍」的最佳时机（Ruling 56 / 66 已这么裁过）。**⑧（`test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点）也一并归 Task 4。**
2. **`hiit` 没有任何模板引用、但等价表有它 2 条映射（删不得）** → **接受为预期**。亲验：动作库 24 个 ref 里**没被任何模板 block 引用的有 6 个**——`brisk_walking` / `stationary_cycling`（都是等价表的**替换目标**）、`energy_expenditure_plus_10pct` / `energy_expenditure_plus_5min_hiit` / `resistance_priority`（都是 **addon 模块**，走 `addons` 不走 `blocks`）、`hiit`（等价表里出现）。**即「不被模板引用」不等于「没人用」**，这 6 个各有各的消费方。**但 `hiit` 的消费方只有等价表**，若 Task 7 落地后发现它既不是任何替换的目标也不是任何来源，就该删——**记进 Task 7 预检清单**。
3. **绿层 `addons: []` 让 spec §7.4 `:510`（体脂率异常 → 追加能量消耗模块）对绿层无模块可追加** → **接受为已知边界**，实现者**没有自行占 §14 编号**（正确，它只被授权 #29/#31）。**裁定：归 Task 7 登记**——`safety.py` 实现 §7.4 的三个触发时，「绿层 + 体脂率异常」这一格会真实出现（绿层的 `C` 判定为假，但 §7.4 的第三个触发是「体脂率异常」而不是 `C`，两者不等价），**那时才知道它是「无动作」还是「需要新模块」**。
4. **`hiit`(high, 有映射) 与 `energy_expenditure_plus_5min_hiit`(medium, 无映射) 的不对称** → BMI > 30 的黄层学生会「主项被换掉、追加模块原样保留」。**裁定：归 Task 7 预检裁一次**（那是 `safety.py` 的语义决定，不是动作库的）。**这条是本轮最有价值的前瞻发现之一。**
5. **`structure` 的键没有 spec 条文定义语义，而 Task 6 必须认得那五个键** → 已登记进 #31 的影响面 ✓。**记进 Task 6 预检清单。**
6. **18 套里同一套每一天 `focus`/`blocks` 完全相同**（指导文件没按周内第几天给参数）→ **接受**，改它就得编造。已并入 #29 ✓。
7. **`Intensity` 的 `rpe` 档今天无真数据用例**（18 套的 `intensity.type` 只有 `hrmax_pct` / `onerm_pct` / `none`）→ **接受**。`rpe` 是 spec §7.2 与 Task 5/6 要用的档（RPE 是 §8.2 课堂快评的量），**今天没有模板用它不是缺陷**；但**它是一个「枚举成员无消费者」的状态，Task 5 落地时必须让它有用例**，否则 domain 覆盖率虽然不受影响（枚举成员不产生 branch），却留了一个永不执行的取值。
8. **账本 P2-A4 的错引用号仍在 `progress.md:999`** → **不成立**：控制者已在 Task 2 fr3 那轮就地勘误（`:999` 现在带「⚠️ 出处勘误」段）。**但该勘误自己引错了裁定号**（写「Ruling 124」，实际是 Ruling 121）——**实现者 grep 到的正是那段勘误里被复述的旧号**。**这恰好是硬规矩 #74 说的形态：更正说明里逐字复述了被撤销的原句，于是串查会命中、让人以为错误还在。** 控制者已把裁定号改对，并按 #74 把复述改成描述式。
9. **`test_domain_purity.py:369-371` 与 `test_layering.py:386-388` 的「子包今天不存在」注释已过期**（`app/domain/prescription/` 从 Task 2 起就存在了；用例本身正确）→ **成立，转 Task 4 预检清单**（与第 1 项同一批，都要动 `tests/architecture/*`）。

**Ruling 135（实现者自纠 6 条，记录）**
两处 grep 计数是**预测的**（实为 6/5 而不是 7/4）；**编辑工具对报告文件「报成功而磁盘未写」并回显了 diff**（文件与备份逐字节相同才查出来）→ 改 python 字节级重写 + 双向串查。**这是工具/磁盘分歧家族的第 60 次**，也是「连 diff 一起伪造」这个形态的第二次。另 4 条见报告 §9.3。**6 条全部自纠，其中 2 条被它自己写的断言/闸门拦下**——硬规矩 #53 与 #48 的升级版正在起作用。

**Ruling 136（实现者对四处钉死基线的处置，控制者裁定都接受）**
1. `_PRESCRIPTION_PUBLIC_BASELINE` 从「7 个裸名字」改成「**20 个 `(名字, 所有者模块)` 二元组**」+ `len == 20`。理由（成立）：公开面现在横跨三个所有者模块（`exercises` / `templates` / 包本身），**硬编码单一模块会对新名字全部取到 `None`**；改成二元组后仍是**字面清单**（没有从被测对象反推，硬规矩 #35 守住）。
2. `:951` 那条负向断言的哨兵从 `+ ["Template"]` 换成 `"__NOT_IN_THE_PUBLIC_FACE__"`。理由（成立，且这正是派单要求它「重新想用意并说明」的那一条）：**`Template` 真的进入公开面之后，`baseline + ["Template"]` 退化成「多一个已有名字」，守的东西悄悄换了**；换成一个永不在公开面的哨兵串，才继续守「基线不是当前值加一」。
3. `templates.__all__` 的字面清单从 1 个扩到 **14 个**，**守卫本身没删** ✓（硬规矩 #67 的要求）。
4. `REFERENCE_TABLES` 的**定义（`:496`）与钉死断言（`:542`）两处同步**改成 `("exercise", "prescription_template")` ✓（P3-A6 第 4 项）。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 共 23 次（#94–#123 中的 Task 2 部分）、**Task 3 预检 2 次（#124 = P3-A1 的裁定未传导、#125 = P3-D2 的 `.gitattributes` 覆盖面没验）+ Task 3 实现轮 4 次（#126 CE-1 行号 / #127 CE-3 重复归属 / #128 CE-2 指错位置 / #129 CE-4 口径混用）+ Ruling 133 那处「黄层按耐力那套的量」无出处（#130）+ 账本 `:999` 引错裁定号（#131）** = **Plan 02 累计 71 次**；Plan 01 60 次，**合计 131 次**。
**实现者 3 次**（全部自纠）。**评审者 4 次**。**复审者 1 次**。

**补硬规矩 #76（派单不许出现裸行号）与 #70 的扩写（sha256 必须标明裸字节还是归一化）**，定义见 Ruling 129 / 131。

---

## ✅ Task 3 结案（18 套模板 + `prescription_template` 表 + 加载器）

**commit**：`4af83bc`（主体，53 个条目）+ `ab075d3`（报告补 commit 后证据）。
**测试**：Task 2 结案 **531** → Task 3 **581 passed**（+50）。
**覆盖**：`app/domain/` **499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**（Task 2 结案是 441/120；**stmts +58、branch +0**）。
**表数**：15 → **16**。
**fix round**：**0/5**（一次通过，没有 fix round）——这是 Plan 02 迄今唯一一轮零 fix 的 Task。
**Critical**：**0**。两处 Critical 都在**预检**阶段被控制者自己查出并改掉（P3-A1 / P3-D2），**没有进到实现**。

**交付**：18 个模板 YAML（`backend/data/prescription/`，123 848 B，CRLF 全 0）、`prescription_template` 表、`templates.py` 的 12 个公有定义、`load_templates()` / `templates()` / `sync_templates(session)`、`tests/domain/test_prescription_templates.py` 从 4 条扩到 **42 条**、`.gitattributes` 加 `backend/data/**/*.yaml text eol=lf`、`exercises.yaml` 追加 `energy_expenditure_plus_5min_hiit`（24 个 ref，指纹 `3DE598AF38631209`）、spec §14 追加 **#29 / #31**、spec §7.2 加 **6 条勘误**。

**⚠️ 带进 Task 4 的清单**：① `cases` 矩阵换成扫真仓对拍 `resolve_name`（Ruling 56/66）② `_package_of` 断言换成扫真仓对拍 `parent.parts`（C-fr4-1）③ `lookup()` 的分支测试搬到 `tests/domain/test_prescription_exercises.py`（Ruling 107-1）④ `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点（Ruling 134-1）⑤ 两份架构守卫的「子包今天不存在」注释已过期（Ruling 134-9）⑥ `match.py` 若写 `level == 2` 相对导入，全仓计数与 level 分布要更新（Task 2 fr2 改过的那几段散文）⑦ **`match.py` 必须拒绝 `Layer.INSUFFICIENT`**（计划 `:255`）与 **`review_status != approved` 的模板**（spec §7.2 `:451`），且 Task 3 已把「构造一个 `PENDING` 的 `Template` 是可能的」证好了（P3-A8）⑧ 4 处钉死基线的更新模式（Ruling 136）可复用。
**⚠️ 带进 Task 5 / 6 的清单（Ruling 133，最要紧）**：**82 个 block 的 `intensity.type == 'none'`**，`intensity.py` 与 `assembler.py` 必须显式处理「模板没给强度」这一档（渲染文字建议，不换算绝对区间）；`structure` 的五个键没有 spec 语义（Task 6 要认得它们）；`Intensity.rpe` 今天无消费者，Task 5 要给它用例。
**⚠️ 带进 Task 7 的清单**：`hiit`(high, 有映射) 与 `energy_expenditure_plus_5min_hiit`(medium, 无映射) 的不对称；绿层 `addons: []` 与 spec §7.4 `:510` 的冲突（并登记 §14）；`hiit` 是否真有消费方。

Task 3 结案。**下一步：Task 4（模板匹配器 `match.py`）预检。** 代码基线 `ab075d3`、**581 passed**、**16 张表**、domain **499/120/100%**、SQLAlchemy 2.1.3。

---

### Task 4: 模板匹配器 — 预检扫描（Pre-flight，控制者亲跑）

**基线**：`a5bdebe`（代码基线 `ab075d3`），581 passed，domain 499/120/100%，16 张表，SQLAlchemy 2.1.3。
**方法**：硬规矩 #49 + #76（**本轮起派单里不许出现裸行号，一律给可 grep 的原文**）。全部证据来自控制者本机 shell 实跑（脚本 `.superpowers/sdd/_pf4.py`，跑完删除）。

#### A. 计划文本需更正的事实（**6 处已落盘**）

**P4-A6（Important，已更正）— Task 4 的 Files 段只列了 2 个新建文件，而本 Task 必然要动另外 4 处。**

原文：「**Files:** Create `backend/app/domain/prescription/match.py`、`backend/tests/domain/test_prescription_match.py`」。**漏掉的**：
1. `app/domain/prescription/__init__.py` —— 公开面要重导出 `MatchInput` / `MatchOutcome` / `MatchStatus` / `match_template`，`__all__` 从 **20** 扩到 20+N
2. `tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE`（控制者实跑：今天是 **20 个 `(名字, 所有者模块)` 二元组**，`assert len(...) == 20` 的报错文案是「基线是 20 个名字，抄漏了就当场红」）**两处都要改**
3. `tests/architecture/test_domain_purity.py` 与 `test_layering.py` —— **三处已过期/写错的陈述**（见下）
4. **Task 3 转来的 4 项**（账本 Ruling 134-1）

**三处过期/写错的陈述（控制者亲扫定位，按可 grep 的原文给）**：
- `# Task 2 会新建 app/domain/prescription/ 子包（今天不存在）` —— **子包自 Task 2 起就存在、Task 3 已填满 12 个公有定义**
- `但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写` —— **`match.py` 是 Task 4 的，不是 Task 3 的**
- `# Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py` —— 那一格矩阵是 **Task 1 fix round 5** 为 **Task 4** 的形状埋的，**归属写错了两处**（既不是 Task 2 加的、也不是 Task 2 的形状）

**⚠️ 这三处正是 Task 3 实现者报的关切 ⑨**（它说「用例本身正确，那两个文件不在授权面」）——**它是对的，而控制者在 Ruling 134-9 里把它转给了 Task 4，所以本轮必须真的授权**。

**另有两组会变的计数**（散在两份守卫的 docstring 里多处，改前先 grep，硬规矩 #66）：全仓相对导入今天 **16 条**（全部 `level == 1`）；架构守卫扫描面今天 **27**（pipeline 7 + db 11 + domain **9**），加 `match.py` 后是 **28**（domain 变 10）。

**P4-A1（Important，已更正）— Consumes 清单漏了 `ReviewStatus` 与 `is_reachable`。**

亲跑 `app.domain.prescription.__all__` = **20 个名字**、`templates.__all__` = **14 个**，两者都含 `ReviewStatus`（成员 `PENDING="pending"` / `APPROVED="approved"`）与 `is_reachable`。原文只列了 `Template` / `WeaknessBucket` / `BodyCompState` / `Layer`。**`ReviewStatus` 是 `NOT_APPROVED` 的判据来源，`is_reachable` 是 `reachable` 规则的唯一所有者**——而后者的 docstring 里明写「**两处消费**：① 加载器用它校验 YAML…；② **Task 4 的匹配器按它排除预留位**」。**即 Task 3 已经为 Task 4 设计好了接口，而计划的 Consumes 清单不知道这件事。**
**附带核实**：Task 3 已把 `Layer` **re-export** 进 `templates`（`templates.__all__` 里有它），故 `from .templates import Layer` 与 `from app.domain.stratify import Layer` 都可用；**唯一所有者是 `app.domain.stratify`**，选哪条路径要在 docstring 里说明。

**P4-A2（Important，已更正）— 「先查 `reachable`」有歧义：查字段还是调函数？**

亲跑 `is_reachable` 的函数体：`return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)`，其 docstring 自称「``reachable`` 的**唯一所有者**」，并说加载器用它校验 YAML 写的 `reachable` 与维度组合不矛盾（矛盾就在加载时响亮失败）。

**裁定：`match.py` 读**字段** `template.reachable`，不调 `is_reachable`。** 理由：① `is_reachable` 是**规则的**唯一所有者、YAML 的 `reachable` 字段是**数据的**唯一所有者，**加载器已强制两者一致**——匹配器再算一遍就是**第三个住址**（违反 Global Constraint #3）；② `match_template` 是消费者，吃的是「已过校验的 `Template`」，重新推导会**掩盖「加载器没校验」这个真故障**；③ 读字段让 `:392` 那类**直接构造 `Template` 实例**的测试行为可预测。
**但 `match.py` 的 docstring 必须写明**（硬规矩 #39）：规则的所有者是 `is_reachable`，本函数只消费加载器已校验过的字段；**若有人绕过加载器手工构造了一个 `reachable` 与维度矛盾的 `Template`，本函数不会发现**。

**P4-A3（Important，已更正）— 完整的优先级链原文没有给出，而 32 格穷举的期望表完全依赖它。**

原文只说了相邻的一对（`reachable` 先于 `review_status`）。**控制者按 `:386-389` 的分类独立实算 32 格**：

```
NO_LAYER 8 / NO_BUCKET 6 / UNREACHABLE 3 / MATCHED 15  —— 与原文的 8/6/3/15 逐字相符
```

而这个分类**只在下面这条链下成立**：`NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`。

**承重的两处**：
- **`NO_BUCKET` 必须先于 `UNREACHABLE`**：`(green, None, abnormal)` 这一格同时满足「桶为空」与「绿层+异常」，**原文的 6 个 `NO_BUCKET` 里包含它**。若顺序反过来，分类变成 `{NO_LAYER:8, NO_BUCKET:5, UNREACHABLE:4, MATCHED:15}`——**总数仍是 32**。**这是「顺序承重」最隐蔽的形态：错了也不会让计数对不上**，只有一个一个格子看期望表才发现。
- **`NO_TEMPLATE` 必须先于 `UNREACHABLE`/`NOT_APPROVED`**：查不到模板就没有 `reachable` / `review_status` 可读。

**P4-A4（Minor，已更正）— 变异 ① 的后果写错了一半。**

原文：「把 `reachable` 检查删掉 → 3 个 `UNREACHABLE` 组合会变成 `NOT_APPROVED` **或** `MATCHED`」。亲跑 18 套 YAML：`review.status` 的 distinct 值**只有 `approved` 一个**，故**只可能是 `MATCHED`，不可能是 `NOT_APPROVED`**。**按硬规矩 #65，变异判据要写明哪个断言分支开火**——这里是穷举测试里那 3 格的 `status` 期望值。

**P4-A5（Important，已更正）— `:378` 引的 `derive.py:330` 是**空行**。**

亲跑定位：字段声明 `dominant_bucket: str | None` 在 `derive.py:129`（`WeaknessResult` 的字段）、口径说明在 `:320` 起的 docstring、赋值处 `dominant_bucket=dominant` 在 `:371`；`_BUCKET_ORDER` 在 `:77`、消费在 `:352`/`:356`。
**「Ruling 175 补的测试」控制者没有核**（那是 Plan 01 账本里的裁定号，本轮没去查）——**已在更正里明写「实现者若要引用它，自己核一遍」**，而不是把一个未核的引用留给下游。
**⚠️ 这是硬规矩 #76（派单不许出现裸行号）立完之后，控制者第一次在预检里主动把裸行号换成「可 grep 的原文 + `git grep` 命令」**：更正文本给的是 `git grep -n "dominant_bucket" -- backend/app/domain/derive.py`。

**P4-A7（Minor，已更正）— 「复用 `stratify.explain()` 的 Z0 文案口径」没有给出确切原文，实现者会自己造第二套。**

亲跑取到：`app/domain/stratify.py` 的 `_REASON` 映射里 `RuleId.Z0` 对应 f-string **`f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`**；`explain()` 在 `:326`，其 Z0 分支说明是「`Z0` 路径单独成句：它没有颜色可报，要说的是「为什么没有分层结果」以及下一步」。→ **`NO_LAYER` 的 `reason` 应当与这条同源**：要么 import `_REASON[RuleId.Z0]`，要么逐字引用并注明出处；**不要另写一句意思相近的话**（那就是第二个所有者，违反 Global Constraint #3）。

#### B. 核对通过、无需更正（控制者实跑）

- **`:385-389` 的 32 格算术**：4 层 × 4 桶（3 真桶 + `None`）× 2 体成分 = **32** ✓；四类 **8/6/3/15** 逐字相符、且**互斥**（控制者按优先级链独立分类后求和 = 32）✓
- **`:394` 的 `_BUCKET_ORDER` 与 Ruling 100**：`derive.py:77` 定义、`:352`/`:356` 消费、`:76` 的注释逐字写着「故 dominant_bucket 不依赖 dict 的哈希顺序（**Ruling 100**）」、`:323` 的 docstring 写「声明序取先出现者」→ **计划的引用为真** ✓
- **`:380` 的 spec §11.2 引文**：spec `:859` 逐字是「模板 `review.status != approved` | 拒绝生成，返回「模板待审校」，教师端提示」→ **相符** ✓（同一张表 `:860` 是安全替换的 `needs_review`，`:861` 是新生无历史体测）
- **`:392` 的「frozen dataclass 可直接构造、不必改 YAML」**：Task 3 已按 P3-A8 证好（`Template` 是 frozen dataclass、构造期不校验）✓
- **`:381` 的「不做 I/O、不读盘」**：由 `test_domain_purity.py` 的 allow-list 机器可查地钉住 ✓；`match.py` 需要 import 的只有 `dataclasses` / `typing` / `collections.abc` + `app.domain.*`，**全在 allow-list 内**
- **架构守卫的矩阵已经预埋了 `match.py` 这一格**：`test_domain_purity.py` 的 `cases` 里有 `("app/domain/prescription/match.py", ("app","domain","prescription"), …)`，且 docstring 明写「`level == 2` 的**跨子包**导入也必须仍被 `_is_allowed` 放行（矩阵第 9 行）……`app/domain/prescription/match.py` 里的 `from ..indicators import X` 就是这一档」→ **Task 1 fix round 5 埋的那一格绿档，到本 Task 才真的从「前瞻」变成「真仓形状」**（前提是 `match.py` 选相对导入；账本 Ruling 104 记的今天全仓 16 条相对导入**全是 `level == 1`**，故仍是前瞻）

#### C. Global Constraints 冲突

- **C1**：`match.py` 进 `app/domain/prescription/` → **domain 纯净性守卫的扫描面自动扩大**（`SCANNED_DIRS` 27 → 28、`app/domain` 9 → 10）。亲验两份守卫的空转守卫下界（`>= 8` 与 `>= 5`）**都不会红** ✓
- **C2**：禁区四项不变。本 Task **不碰** `backend/data/`（18 个 YAML 已被指纹钉住，改了要同步 18 个指纹）、**不碰** `app/seed/`、**不碰** `.gitattributes`
- **C3**：domain 覆盖率 **100% 必须维持**。⚠️ `match.py` 有一条 6 分支的优先级链，**每一支都要有测试走到**（`BrPart 0`）；而 32 格穷举**天然覆盖全部分支**——这也是为什么穷举表要字面写死而不是从 `templates` 反推（硬规矩 #35）

#### 预检小结

**6 处计划更正已落盘（P4-A1…A7，无 Critical）**，其中 **5 处 Important**（A1 Consumes 漏两项 / A2 `reachable` 读法歧义 / A3 优先级链缺失 / A5 `derive.py:330` 是空行 / A6 Files 段漏 4 处）+ **2 处 Minor**（A4 变异后果 / A7 Z0 文案未给原文）。

**⚠️ 一个值得记的正面观察**：本轮预检**没有查出 Critical**，而 Task 2 与 Task 3 各有 2 处。原因不是运气——**Task 4 的计划正文只有 41 行、且不碰数据文件与 schema**（对比 Task 2 的 55 行 + 两个 YAML + 一张表、Task 3 的 69 行 + 18 个 YAML + 一张表 + spec 两处）。**即：计划文本越长、触碰的既有资产越多，预检查出的缺陷就越多。** 这条对 Task 9（两张表 + 五触发条件）与 Task 10（接入管道）是预警——那两个 Task 的正文都很长。

**控制者错误计数**：本轮预检查出的 6 处都是**计划编写期（`e26347f`）就存在的缺陷**，与 Task 2/3 预检的 P2-A*/P3-A* 同源，故合并记 **#132**（一次预检不足，覆盖 6 处）。**Plan 02 累计 72 次，Plan 01 60 次，合计 132 次。**
**⚠️ 但 P4-A5 要单独说一句**：它是**控制者在预检里第一次主动把裸行号换成可 grep 的原文**（硬规矩 #76 立完之后的第一次执行），而它查出的正是「计划引的行号是空行」。**#76 立刻产生了回报。**

Task 4: 预检完成（6 处计划更正已落盘、无 Critical、0 条新硬规矩），派发中。代码基线 `ab075d3`、581 passed、16 张表、domain 499/120/100%。

#### Task 4 实现 — 控制者亲验（commit `fe5e6dd` + `9697426`，581 → **592 passed**）→ **Task 4 结案**

**判定：Task 4 交付合格、零 fix round（连续第二个 Task 一次通过）；实现者报出 7 条控制者错误，控制者亲验后 6 条成立、1 条是「有意偏离派单」并裁定接受。另实现者报出 1 条自己的工具事故。**

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 592 passed | `cd backend; python -m pytest -q` | **592 passed in 64.21s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **541 stmts / Miss 0 / 132 branch / BrPart 0 / 100%**、`591 passed, 1 skipped` ✓（499 → 541 = `match.py` **+41 stmts**；120 → 132 = **+12 branch**，正是那条 6 段优先级链的 6 个判定点 × 2 arc） |
| 表数 | — | **16**（本 Task 不建表）✓ |
| 禁区 | `git diff --name-only ab075d3 9697426 -- backend/data backend/app/seed .gitattributes` | **全部 0 命中** ✓（`Document/` 那 1 处命中是控制者自己的 `8631744`，落在这个 diff 区间内，**不是实现者改的**） |
| 32 格分类 | 采信其报告 + 控制者独立算过期望 | **`{NO_LAYER:8, NO_BUCKET:6, UNREACHABLE:3, MATCHED:15}`**，sum 32 ✓，与 P4-A3 的链逐格相符 |
| 扫描面 | 自己数 `.py` | **28**（pipeline 7 + db 11 + domain **10**）✓ 与派单预测一致 |
| 相对导入 | 自己 AST 扫 | **18 条，全部 `level == 1`** ✓ —— **派单预测的 17 是错的**（见 Ruling 138） |

**Ruling 137（CE-1，成立，控制者错误 #133，⚠️ 把先例说反了）— 派单说「`app/domain/percentile.py` 里有一处先例是『触私有名』」，实测恰恰相反。**

实现者 `git grep "触私有名" -- backend` 只命中**两个测试文件**；而 `app/domain/percentile.py` 里有两处**明确写着相反的纪律**（「纯函数，只用公开 API…**不** import 私有名」、「不去 import 私有名 `app.domain.indicators._lower_is_better`」）。**即：生产码的先例是「不触私有名」，测试码的先例才是「触私有名并注明理由」。**

**控制者把两者的归属弄反了**，而这直接影响 P4-A7 那条裁定的执行方式（`NO_LAYER` 的 `reason` 要不要 import `stratify._REASON`）。实现者的处置正确：**生产码持文案副本、测试侧触私有名做漂移守卫**——这恰好符合两个先例各自的口径。
**根因**：控制者在 Task 1 期间读过 `tests/domain/test_percentile.py` 里那条 `# 触私有名：本条要比较的正是它` 的注释，**把「在哪个文件读到过」记成了「哪个文件这么做」**。→ **并入硬规矩 #63（类比/先例必须亲验被类比的对象）**：引用先例时要验**那个文件自己**怎么说，不能凭「记得在某处见过」。

**Ruling 138（CE-2，成立，控制者错误 #134）— 派单预测「`match.py` 若写相对导入，全仓计数变 17」，实测是 18。**

控制者亲跑复核：`match.py` 的 `from .templates import (…)` **+1**，而 **P4-A6 第 1 项自己要求的** `prescription/__init__.py` 那句 `from .match import (…)` 又 **+1** → 16 + 2 = **18**。**派单的两个分支预测（「不变仍 16」与「变 17」）都少算了一条**，而少算的那条正是同一份派单在另一处要求的改动。
**→ 这是硬规矩 #66 的形态（改一处要 grep 出全部同类），只是对象是「我自己派单内部的两处要求」**：一处要求改 `__init__.py`、另一处预测相对导入计数，**两者没有对读过**。并入硬规矩 #58（发出前回查自己已写的内容）的适用范围：**回查要覆盖「派单内部各处之间的算术一致性」，不只是路径与数量。**

**Ruling 139（CE-3，成立，控制者错误 #135）— P4-A3 预测顺序对调后是 `{8, NO_BUCKET:4, UNREACHABLE:5, 15}`，实测是 `{8, 5, 4, 15}`——两个数写反了。**

控制者独立重算：把 `UNREACHABLE` 提到 `NO_BUCKET` 之前后，`UNREACHABLE` = `green × 4 个桶 × abnormal` = **4**；`NO_BUCKET` = `red×2 + yellow×2 + green×None×normal` = **5**。**故 P4-A3 里那两个数确实写反了**（承重结论「总数仍是 32、所以计数对不上证明不了顺序对」**不受影响**，反而更强：连分类互换都保持总数不变）。
**⚠️ 这条错误在 3 处同源**（计划正文的 P4-A3 块、账本的 P4-A3 段、派单 §2 的转述），**已由控制者一并更正**（硬规矩 #66）。
**根因**：控制者算「反过来会怎样」时，**把 `UNREACHABLE` 的格数当成了「绿层×3 个真桶×异常 = 3」再加 1**，而正确的算法是「绿层×**4 个桶（含 `None`）**×异常 = 4」——**`None` 桶在这一档也要算进去，因为顺序对调后它先被 `UNREACHABLE` 吃掉**。**即：算反事实的时候，必须把「反事实改变了哪些格的归属」逐格重走一遍，不能在原分类上做加减。**

**Ruling 140（CE-4，成立，控制者错误 #136，⚠️ 本轮最严重的一条）— 硬规矩 #76 执行得不彻底，而且简报里的裸行号全部指向「更正前」的计划文本。**

实现者实测：简报里裸行号是 **10 处**（不是派单 §3 说的 7 处），其中 **9 处是「当前有效的定位」**（不是被撤销的旧说法）。**更严重的是**：它们**全部指向 `a5bdebe`（更正前）的计划文本**，而简报自称抽取自 `8631744`——因为 `8631744` 往 Task 4 节**插入了 6 个更正块、把该节下推了 11 行**（Task 5 的标题从 769 变 798）。**故按简报给的行号去翻计划会翻错行。**
**附带**：Task 3 结案清单第 ⑦ 项引的「计划 `:255`」在 `a5bdebe` 与 `8631744` **两个 rev 上都是空行**。

**根因值得单独记**：**更正计划正文这个动作本身，会让被更正那一节内部的所有行号引用失效。** 我在写 P4-A1…A7 的时候，注意力全在「新写的更正对不对」，**没有想到「我插进去的 40 多行会把它下面（和它内部）的 `:NNN` 全部推走」**。这是硬规矩 #66（改一处要 grep 全部同类）的一个**新形态**：同类项不只是「同一个事实的多个副本」，还包括**「同一次编辑影响到的所有位置引用」**。

**→ 补硬规矩 #77：更正计划/spec 正文时，若插入或删除了行，必须 grep 该文件内全部 `` `:NNN` `` 形态的引用并逐个核对是否被推移；或者按 #76 一律把它们换成可 grep 的原文。** 依据：CE-4。**并且：简报必须在计划正文**最后一次**更正之后再抽**——本轮的时序是对的（`8631744` 更正 → `3473dc6` 抽简报），**但简报里带进来的 Task 4 节文本本身就含有指向 `a5bdebe` 的行号**，抽取动作无法修复已经写错的引用。

**Ruling 141（CE-5 / CE-6，成立，控制者错误 #137 / #138）**
- **CE-5**：派单说 Task 3 转来的「①②③ 会让 passed 数变化」——实测**三项都不改变 passed 数**（①② 改的是既有测试的内部实现、③ 是「搬」不是「复制」故净 0）。**+11 全部来自新建的 11 条 `test_prescription_match.py`。** 控制者写这句时**没有区分「改测试的实现」与「加测试」**。
- **CE-6**：派单说三处过期陈述「两份守卫都要查」，实测**第 ② 处只在 `test_domain_purity.py` 一份里**（`git grep "这一层子包已经建出" -- backend/tests` 只命中 1 处），故总共改了 **5 处**而不是 6 处。**实现者按硬规矩 #51 先 grep 出份数再改，并在报告里列了份数**——这正是 #51 要求的做法，**而派单给的「两份」是没有 grep 过的假设**。

**Ruling 142（CE-7，实现者有意偏离派单字面，控制者裁定：接受，且认为偏离是对的）**

派单（转述 Ruling 56/66）要求把 `_absolute` 的 `cases` 矩阵**换成**「扫真仓每个 `.py` 逐个对拍 `resolve_name`」。实现者做成了**超集**：12 格手写矩阵**保留** + 新增扫真仓对拍。

**它的理由（控制者亲验成立）**：真仓今天 **0 条 `level >= 2` 的相对导入、0 个越界档、0 个 offender**（控制者亲跑：18 条全是 `level == 1`），**这三类形状只有手写矩阵能提供**。删掉矩阵会让 Ruling 35/46 修掉的那个假绿**复活**——即「删掉 `if level - 1 > len(package): return None`，全量测试仍然全绿、退出码 0」。
**并且它指出 Ruling 56 自己的前提已被推翻**：Ruling 56 说的是「Task 2 建了 `app/domain/prescription/` 之后按 Ruling 66 换成扫真仓」，而**建了子包 ≠ 出现了 `level == 2` 的相对导入**（账本 Ruling 104 已实测：Task 2/3 都用绝对导入，那一格绿档**仍是前瞻**）。

**裁定：接受超集，不要求回退。** 并更正 Ruling 56：**「换成扫真仓」的前提不是「子包建出来了」，而是「真仓里出现了 `level >= 2` 的相对导入」**；在那之前，**手写矩阵是唯一的红档来源，必须保留**。→ 这条更正写进 Task 5+ 的预检清单。
**⚠️ 这是本项目第 4 次实现者顶回控制者的裁定并且是对的**（前三次：Task 1 fr1 的 I1、Task 2 的 `dict` vs `Mapping`、Task 2 fr2 的 CE-4）。**四次的共同点是：控制者的裁定对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。**

**Ruling 143（实现者 7 条关切的裁定）**
1. **CE-7 的偏离** → 见 Ruling 142，**接受**。
2. **`test_impact_rank_values_are_pinned_verbatim` 与 `test_prescription_public_namespace_is_pinned_verbatim` 仍在 domain 测试目录之外** → **接受现状，不搬**。它的理由成立：Ruling 134-1③ 只授权搬 `EquivalenceTable.lookup()` 的**分支测试**（因为那是 domain 覆盖率的 `BrPart` 来源），而这两条守的是**常量与包公开面**，尤其后者「守的是整个包」、搬进 `test_prescription_exercises.py` 名不副实。**但「domain 覆盖率的一部分由 `tests/` 根下的测试守着」这个事实必须在两处 docstring 里写明**（它已写）——**失效形态是「删那两条测试、`pytest` 退出码仍 0、只有覆盖率数字变」**，与 Ruling 103 同型。
3. **`NO_BUCKET` 在生产路径上恒被 `NO_LAYER` 先拦下**（`dominant_bucket is None` 意味着 6 项全缺测 → `valid_count < 4` → Z0 命中 → `Layer.INSUFFICIENT`）→ **接受，记进 Task 9 预检清单**：`prescription_stage.py` 落地时要复核 `NO_BUCKET` 是否成了**死代码**。**⚠️ 但今天不许删它**：① 它是 `MatchInput` 的合法状态之一，`match_template` 是纯函数、调用方可以传任何组合；② 32 格穷举里有 6 格是它；③ **「生产路径不可达」与「不可达」是两件事**——Z0 的判据是 `valid_count < 4`，而 `dominant_bucket is None` 的判据是「6 项全缺测」，**两者今天等价，但那是 `derive.py` 的实现事实、不是 `match.py` 的契约**。
4. **`NO_TEMPLATE` 这一档在 spec §11.2 的降级表里没有行**（教师端措辞无出处）→ **接受，归 Task 12 登记 §14**（实现者**没有自行占编号**，正确——§14 的编号分配已由 `d40f36c` 与 Task 3 定死，见 Ruling 92/121）。**⚠️ 这条比看起来重要**：`NO_TEMPLATE` 意味着「18 个 YAML 少了一个文件」，而加载器**已经在加载时拦这一类**（`test_loader_rejects_a_broken_template`），所以 `NO_TEMPLATE` 在正常路径上**也不可达**——它是**纵深防御**（注入的 `templates` 映射与加载器不是同一个来源时才可能命中）。**Task 12 登记 §14 时要把这个「纵深」属性写清楚**，否则会被当成一个真实的降级场景。
5. **`MatchStatus` 的 6 个 `(name, value)` 已被字面钉住**（Task 9 落库依赖它）→ ✓ **正面确认**，这正是 Task 9 需要的前置。
6. **3 个新 `.py` 的工作树是 LF、既有惯例是 `w/crlf`** → **接受**。blob 相同、无守卫受影响、仓内已有 3 个同类先例。**根因**：`backend/app/**` 与 `backend/tests/**` **没有 `.gitattributes` 规则**，故 `core.autocrlf=true` 只在 **checkout 时**转 CRLF；用 python `write_bytes` 新建的文件是 LF，要等下一次 checkout 才会变。**这不影响任何断言**（源码文件没有字节数/指纹断言），故不修。**但记进账本：若将来给 `backend/**` 加行尾规则，必须先 `git add --renormalize`（硬规矩 #70 的三步）。**
7. **变异 ④ 的实现方式**（在它的代码结构里「对调」不能靠交换两个 `if`，改用「提前插入 `is_reachable` 口径的判定」）→ **认可**。控制者亲验其结果：分类变 `{8, 5, 4, 15}`、总数仍 32、只有承重格不符 → **3 failed**，**这正是 P4-A3 要的那个「唯一能证明顺序被测住」的变异**。

**Ruling 144（实现者的工具事故，记录）— 编辑工具对报告文件的 3 次 `SearchReplace` 全部「报成功并回显了看起来正确的 diff」而磁盘逐字未写**（sha256 前后同为 `A673C075FC056050`）。

**这是工具/磁盘分歧家族的第 61–63 次、「连 diff 一起伪造」形态的第 3 次。** 被它自己的落盘闸门抓出，改 python 字节级重写修复，并**把闸门扩到本轮全部 8 个被编辑文件**（新串 ≥1 / 旧串 = 0 / 控制探针 ≥1 / `ast.parse` 通过）→ ALL OK。**另有四路独立证据交叉验证**（`git diff --numstat`、`--collect-only` 条数、运行时 `len(__all__) == 24`、592 passed）。
**→ 这个「四路交叉」的做法要保留为标准**：当编辑工具不可信时，**唯一可靠的证据是「多个互相独立的通道给出同一个结论」**，而不是任何单一通道的回显。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 共 23 次（#94–#123 的 Task 2 部分）、Task 3 共 7 次（#124–#131）、**Task 4 共 6 次（#133–#138，Ruling 137/138/139/140/141×2）** = **Plan 02 累计 78 次**；Plan 01 60 次，**合计 138 次**。
（⚠️ #132 是 Task 4 预检那一次「预检不足覆盖 6 处」的合并计数，已在上一节记过；本节从 #133 起。）
**实现者 3 次**（全部自纠）。**评审者 4 次**。**复审者 1 次**。

**补硬规矩 #77**（更正计划/spec 正文会推移该节内部的行号引用，必须 grep 全部 `` `:NNN` `` 逐个核对或一律换成可 grep 的原文），定义见 Ruling 140。

---

## ✅ Task 4 结案（模板匹配器）

**commit**：`fe5e6dd`（主体）+ `9697426`（报告回填 commit 后证据）。
**测试**：Task 3 结案 **581** → Task 4 **592 passed**（+11，全部来自新建的 `test_prescription_match.py`）。
**覆盖**：`app/domain/` **541 stmts / Miss 0 / 132 branch / BrPart 0 / 100%**（Task 3 结案是 499/120；**+42 stmts / +12 branch**，`match.py` 独占 41 stmts / 12 branch）。
**表数**：**16**（本 Task 不建表）。
**fix round**：**0/5**（一次通过，**连续第二个 Task 零 fix round**）。**Critical：0。**

**交付**：`app/domain/prescription/match.py`（18 589 B / 287 行）——`MatchStatus`（6 档）/ `MatchInput` / `MatchOutcome` / `match_template`，**6 段优先级链 `NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`**；`tests/domain/test_prescription_match.py`（11 条，含 **32 格穷举**）；`tests/domain/test_prescription_exercises.py`（`lookup()` 的分支测试从 `tests/` 根搬进 domain 目录）；公开面 **20 → 24**；两份架构守卫改成**扫真仓对拍**（`_absolute` vs `resolve_name`、`_package_of` vs `parent.parts`）并保留 12 格手写矩阵作为红档来源（Ruling 142）。

**⚠️ 带进 Task 5 的清单**：① Ruling 56 的前提已更正——「换成扫真仓」的条件是**真仓出现 `level >= 2` 的相对导入**，不是「子包建出来了」；在那之前手写矩阵必须保留 ② `Intensity.rpe` 今天无消费者（Task 3 关切 ⑦），Task 5 要给它用例 ③ **Ruling 133 的头号影响面**：18 套模板的 130 个 block 里 **82 个是 `intensity: {type: none}`**，`intensity.py` 必须显式处理「模板没给强度」这一档 ④ 若 Task 5 新增 domain 模块，扫描面 28 → 29、`_PRESCRIPTION_PUBLIC_BASELINE` 24 → 24+N、相对导入计数与 `__all__` 都要同步 ⑤ 三处「当前有效但会随编辑推移」的引用一律用可 grep 的原文（硬规矩 #76/#77）。
**⚠️ 带进 Task 9 的清单**：① `NO_BUCKET` 在生产路径上恒被 `NO_LAYER` 先拦下，落库时要复核它是否死代码（**但今天不许删**，理由见 Ruling 143-3）② `MatchStatus` 的 6 个 `(name, value)` 已被字面钉住，落库直接用 ③ `prescription` / `weekly_adjustment` 两张表要同步 `REFERENCE_TABLES` 与 `test_models.py` 的三处 `==` 与函数名英文数词。
**⚠️ 带进 Task 12 的清单**：`NO_TEMPLATE` 在 spec §11.2 的降级表里没有行，教师端措辞无出处 → 登记 §14，**并写明它是纵深防御、正常路径不可达**（Ruling 143-4）。

Task 4 结案。**下一步：Task 5（HRmax 与目标心率区间 `intensity.py`）预检。** 代码基线 `9697426`、**592 passed**、**16 张表**、domain **541/132/100%**、SQLAlchemy 2.1.3。






### ✅ Ruling 122 — 环境阻塞已解除（用户裁定：换 SQLAlchemy 补丁版本）

**用户裁定**：三个选项里选「**先试换 SQLAlchemy 补丁版本**」（另两个是「关闭 Smart App Control」——Windows 11 上单向不可逆、「跳过测试先做散文修正」）。**结果：一次成功，不需要动系统安全设置。**

**处置与亲验（全部控制者本机实跑）**：

1. **可选版本**：`pip index versions sqlalchemy` → 2.1.x 有 **2.1.3**（LATEST）/ 2.1.2 / 2.1.1（INSTALLED）/ 2.1.0。**PyPI 可达**（本会话早前 github.com:443 曾三次不可达，PyPI 不受影响）。
2. **先建回滚点**：`pip download sqlalchemy==2.1.1 --no-deps --only-binary :all: -d $env:TEMP\sarollback` → `Successfully downloaded`。**先下载再卸载**，否则失败就没有退路。
3. **安装**：`pip install --no-deps "sqlalchemy==2.1.3"` → `Successfully uninstalled SQLAlchemy-2.1.1` / `Successfully installed sqlalchemy-2.1.3`。**用 `--no-deps`**：只换 SQLAlchemy 本体，不动其它包（避免一次改多个变量、事后分不清是谁修好的）。
4. **冒烟（硬规矩 #72）**：`import sqlalchemy` → **OK，version = 2.1.3**；逐个 import 三个 `.pyd` 所属模块 → `sql._cache_key_cy` **OK**、`engine._result_cy` **OK**、`util._collections_cy` **OK**。**原来那一个故障点已经能加载。**
5. **为什么换版本有效**（亲验字节）：8 个 `.pyd` **全部换成了新构建**，哈希逐个不同；其中 `sql/_cache_key_cy.cp311-win_amd64.pyd` **尺寸仍是 108 544 B（一模一样）而 sha256[:16] 从 `B1A005B464DFC87E` 变成 `62C18CCD38308791`**。**即：同一段源码重新编译出字节不同的产物 → SAC 的信誉评估按哈希查、查不到旧的拦截记录 → 放行。** 这也**反证了 Ruling 121 的诊断第 4 点**（「策略按内容/签名判，不按路径」）：尺寸相同而哈希不同就足以改变判定。
6. **回归验证**：
   - `cd backend; python -m pytest -q` → **531 passed in 59.68s**（与 2.1.1 上的 531 **一字不差**）
   - `--cov=app/domain --cov-branch --cov-report=term-missing` → **441 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**、`530 passed, 1 skipped`（与 2.1.1 上逐格相同）
   - **故 2.1.1 → 2.1.3 对本仓零影响**，Task 2 的验收判据全部仍然成立。
7. **依赖声明无需改**：`backend/pyproject.toml:8` 写的是 `"sqlalchemy>=2.0"`（松约束），2.1.3 满足。**全仓没有 `requirements.txt` / 锁文件**，故没有第二处要同步。

**⚠️ 一个必须记下来的脆弱性**：本仓**没有依赖锁文件**，且**没有 venv**（装在 `C:\Python\Lib\site-packages`）。这意味着：① 任何一次 `pip install` 都可能悄悄换掉版本，而 531 这个数字是绑在版本上的；② **SAC 的判定可以随云端信誉变化而翻转**——2.1.1 的 `.pyd` 从 2026-09-28 装好起正常工作了 9 天，本会话中途才被拦，**文件一个字节都没变**。**同类事故会再发生。**

**→ 补硬规矩 #73：每轮开工前先跑一次 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 冒烟，并把版本记进报告的「环境与基线复现」节。** 依据：Ruling 121/122——**531 passed 这个数字只有在「哪个 SQLAlchemy 版本上跑的」已知时才有意义**，而此前四轮报告都没记版本。
**→ 转延后 Minor（Plan 02 级别，非 Task 2）**：考虑加一个锁文件（`requirements.txt` 或 `uv.lock`），把「531 passed」绑定到确切的依赖版本上。**这是 Plan 02 全分支终审该裁的事，不在单个 Task 的范围内。**

**Task 2 状态**：收尾评审完成（Approved with findings，0 Critical / 7 Important / 10 Minor），环境阻塞已解除，**fix round 3 派发中**。代码基线 `966eae0`、含审计链基线 `31c9212`、SQLAlchemy **2.1.3**、**531 passed**、domain **441/120/100%**。

---

### ✅ Ruling 145 — 执行强度调整（用户裁定 2026-10-08：「保正确性、砍文档精度」）

**触发**：用户在批准继续推进时给出方向性裁定，原文：

> 「后端其实只要不出太大的 bug 就行，后端算法层面要求不是很高，主要是要做一个系统，类似管理型的原型系统，需要能够进行增删改查，然后加上之前的大数据算法即可，在进行前端页面后尽量保持简洁，功能齐全，与后端能够对齐。」

**控制者对现状的核对（本机实跑，`dfa7580`）**：
- `Document/` 下只有 spec（98 755 B）、计划 01（223 017 B）、计划 02（124 005 B）、指导文件 `.doc`（1 203 712 B）。**计划 03 与计划 04 都不存在。**
- **`frontend/` 目录不存在**（`Get-ChildItem` 无此项）。
- **`backend/app/api/` 目录不存在**——后端现有模块只有 `adapters/ config.py db/ domain/ pipeline/ refdata.py refdata_prescription.py seed/`。**整个系统今天没有任何 HTTP 层。**
- 也就是说：用户说的「开始实施计划 03」指向一个还没写的计划，而「增删改查」需要的 API 层一行都还没有。

**三问三答（AskUserQuestion，用户全选推荐项）**：
1. 计划 02 剩下的 8 个 Task 怎么办 → **「精简合并后做完」**
2. 计划 03 的范围 → **「反馈 + 预警 + 全系统 CRUD API 层」**（前端留给计划 04）
3. 严格度 → **「保正确性、砍文档精度」**

**裁定内容 —— 保留项（一条不许砍）**：
- **TDD**：先写失败测试，再实现。
- **`app/domain/` 分支覆盖 100%**（spec §12 硬要求）。验收命令仍必须带 `--cov-branch`，`Miss 0 / BrPart 0`。
- **安全关键路径的变异测试**：分层判定（Plan 01 已结案）、安全替换（本计划 5.3）、预警阈值（计划 03）。含 M0/M1 双对照与三重还原取证。
- **每个 Task 一轮评审**（评审者独立于实现者）。
- **控制者预检扫描**（派单前亲跑，抓计划文本里的事实错误）。

**裁定内容 —— 取消项**：
- **「纯散文精度导致的 fix round」取消**：注释/docstring/计划正文里某个数字与实测不符，**不再单独开一轮 fix round**；实现者记进报告的「待清扫」清单，控制者在计划收尾（Task 9）一次性清扫。
  - 依据：Plan 02 的 Task 1 用了 **5 轮**（上限）、Task 2 用了 **3 轮**，其中相当比例的往返是「账本里写了 8 相位而实测 5 行」「指纹常量的行号抄了三轮前自己的输出」这类**纯散文错误**——控制者错误累计 **138 次**（Plan 01 60 + Plan 02 78），实现者只有 3 次（全部自纠）。往返成本几乎全部花在文档自洽上，没有花在代码正确性上。
- **「控制者对每个数字的独立复跑」取消**：控制者仍要亲验**承重结论**（不变量、变异是否真红、覆盖率、指纹），但不再逐个复算实现者报出的每一个计数。
  - 保留的例外：**任何会被写进验收判据的数字**（passed 数、表数、公开面大小、覆盖率四格）仍由控制者亲跑，因为硬规矩 #44 的教训是「照抄派单的期望值」会让判据变成自证。

**目标**：每个 Task 从 **3–6 轮**往返降到 **1–2 轮**。fix round 上限仍是 5，但预期不再触顶。

**⚠️ 本裁定不改变的东西**（防止被读成「质量可以松」）：
- Critical 级问题（会让生产代码错、会让守卫假绿、会让数据不可追溯）**一律当场修**，不进「待清扫」清单。
- 「待清扫」清单只收**散文与实测的偏差**，不收代码缺陷。
- domain 纯净性守卫、单一所有者、断言两侧不同源、指纹测试——**全部照旧**。

---

### ✅ Ruling 146 — 计划 02 重构：12 个 Task 变成 9 个（用户裁定「精简合并后做完」）

**处置**：控制者用两个 python 脚本（`.superpowers/sdd/…/_restructure.py`、`_restructure2.py`）改计划正文，**每处替换都 assert 命中次数**，命中数不符即抛异常不写盘。

**第一轮 39 处替换，全部命中 1 次**（脚本逐条打印）。计划从 **124 005 B / 797 行** 变成 **128 798 B / 822 行**（CRLF，无 BOM，行尾未变）。**第二轮 6 处**清扫已结案 Task 1–4 正文里的陈旧编号 → **129 092 B / 822 行**。

**重编号对照**：

| 原编号 | 新编号 | 处置 |
|---|---|---|
| Task 1–4 | Task 1–4 | 不变（已全部结案） |
| Task 5 `intensity.py` | **Task 5 的 5.1** | 合并 |
| Task 6 `assembler.py` | **Task 5 的 5.2** | 合并 |
| Task 7 `safety.py` | **Task 5 的 5.3** | 合并 |
| Task 8 `override.py` | **Task 5 的 5.4** | 合并 |
| Task 9 两张表 + 五触发 | **Task 6** | 原文不动 |
| Task 10 接入管道 | **Task 7** | 原文不动 |
| Task 11 本周训练单读模型 | **Task 8** | 原文不动 |
| Task 12 黄金用例 + 性能 + 勘误 | **Task 9** | **删掉 p95 性能压测（原 Step 2）**，Step 3/4 顺延为 2/3 |

**新 Task 5 砍掉了什么**（合并节的引言里逐条写明）：
1. `HrmaxFormula` 枚举与 FOX 公式——只留 Tanaka。理由：`hrmax` 只有一个生产调用点，将来要换公式改一处即可，**今天不需要为它抽象出一个枚举**；spec §14 #14 本来就把「Tanaka 还是 `220 − 年龄`」列为待确认事项。
2. 原 Task 6 的 `formula` 形参（快照里的 `"formula"` 键恒为 `"tanaka"`，**键保留**，否则离线复算的契约会缺一环）。
3. 三档系数的 10 组参数化穷举（`59.9/60.0/79.5/79.9/80.0` × 男女）→ 改成「三档各一条 + **一组**边界」。
4. 闰年生日测试、`age_from` ↔ Plan 01 龄组的漂移测试。
5. 装配器与覆盖的独立变异轮次 → 只保留 **4 条安全关键变异**（`>= 30`、删 `needs_review`、删 `age <= 0` 守卫、取整方向反转）。
6. 五种 `OverrideKind` 的穷举边界 → 每种一条。

**新 Task 5 没砍什么**（写进合并节引言的「硬要求，一条都不许少」）：
1. `app/domain/` 分支覆盖 **100%**（简化版不豁免，spec §12）。
2. 安全规则的严格比较符 + 「没测不得讲成测了没问题」+ 「找不到等价动作不得静默跳过」（Review Focus 第 5 条）。
3. `assembly_snapshot` 的 12 个键字面钉死（spec §4.3 可追溯性在处方侧的落点）。
4. 年龄异常响亮拒绝（Review Focus 第 4 条）。
5. 覆盖不改模板、`reason` 非空。

**⚠️ Ruling 133 被提升为新 Task 5 的「头号约束」**，写进 5.2 的独立段落并配一条**吃真仓 YAML**的测试要求。原文的发现是：18 套模板的 **130 个 block 里有 82 个是 `intensity: {type: none}`**，按层是 **绿 `{none}` / 黄 `{none}` / 红 `{hrmax_pct, none, onerm_pct}`**。三条推论被写死进计划：
- 「模板没给强度」是**常态不是例外**，`intensity_text` 必须有一档显式渲染它，**不得**回落到 `hrmax_pct` 默认值、**不得**留空字符串。
- 这 82 个 block 的 `hr_zone` 一律 `None`。
- **心率相关的测试必须用红层模板或手工构造的 `hrmax_pct` block**——用黄层写会全绿、但什么也没测（假绿）。

**同时更正的连锁项**：
- 头部 `**Spec:**` 行删掉「§1.3（单人处方 p95 < 3 秒）」——本计划不再验收它。
- File Structure 表里 `intensity.py` 的描述从「Tanaka / 220−age 可切换」改成「**简化版只实现 Tanaka**」；另三个模块标注归属小节（5.2/5.3/5.4）。
- 计划头部插入「**⚠️ Task 重编号对照表**」一节（含 Ruling 145 的强度调整摘要），位置在 `## Global Constraints` 之前。
- `## 计划完成后的状态`：模块数从「新增 8 个模块」改成「新增 **9 个实质模块**（逐个列名）+ 包 `__init__.py`」；p95 与整学期回放两条改成「**不做压测**，只留数量级哨兵」。
- `## 计划边界说明`：**CRUD API 层从 Plan 04 移到 Plan 03**（用户裁定 2）；依赖顺序按新编号重写，并加一行进度（Task 1–4 已结案，`dfa7580`，592 passed，domain 541/132/100%，16 张表，SQLAlchemy 2.1.3）。
- Review Focus 第 2/3 条归属 `Task 9` → `Task 6`；第 4 条 → `Task 5（5.1）`；第 5 条 → `Task 5（5.3）`。
- 已结案 Task 1–4 正文里 6 处会误导人的陈旧编号就地更正（Task 2 节 4 处、Task 3 节 2 处），**其余按对照表折算**（Ruling 145 的「砍文档精度」）。
- 对照表脚注里原本写的裸行号 `:130` / `:378` **被删掉**，改成可 grep 的原文片段。依据：硬规矩 #76/#77——插入 22 行的对照表已经让那两个行号失效，而控制者在 Plan 02 里已经因为「复用历史行号」栽过 5 次（Ruling 129）、「派单裸行号指向更正前文本」栽过 1 次（Ruling 140）。

**→ 补硬规矩 #78：改计划正文时，任何插入/删除行的编辑都会让其后所有裸行号失效。因此（a）计划正文里不写裸行号，改指可 grep 的原文片段；（b）若必须引用行号，绑定 commit 且在该次编辑**之后**重新实测。** 依据：Ruling 129 / 140 / 146——同一根因第 7 次。

**→ 补硬规矩 #79：批量改文档一律走 python 脚本 + 逐条 `assert 命中次数`，不用编辑器逐处手改。** 依据：本次 45 处替换（39 + 6）全部一次命中，脚本打印的命中清单本身就是取证；而手改 45 处无法自证漏改。这也顺带满足硬规矩 #70（落盘唯一权威是 shell）——脚本写完立即 `read_bytes` 复核字节数与行尾。

**Task 5 状态**：计划已重构，**尚未派单**。下一步：新 Task 5 的预检扫描 → 抽简报 → 派实现者。

---

### Task 5（合并后）: 处方装配（简化版） — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`dfa7580`（工作树干净）→ 计划重构提交 `3dd36d2`。
**测试基线**：`cd backend; python -m pytest -q` → **592 passed in 61.84s**（控制者本机实跑，与 Task 4 结案时一字不差）。
**取证脚本**：`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t5_probes/_t5_probe{1,2,3,4}.py`（四份全部入库）。

**⚠️ 这次预检比前四次都严重：4 条 Critical。**根因是**合并本身**——把四节正文压成一节时，控制者重写了散文、**没有重新核对四节各自引用的量**。而其中两条（P5-A1 / P5-A3）与 **Ruling 133 同型**：计划引用一个 YAML 里根本不存在的量。

#### Ruling 147 — 预检查出 4 Critical / 5 Important / 3 Minor / 1 控制者错误，计划正文更正 21 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P5-A1** | **Critical** | `Block.structure` **只有两种键集、无第三种、无交集**：时长类 **78** 个 `{sets, work_min, rest_min}`、次数类 **52** 个 `{rounds, reps}`（78+52=130 ✓）。**没有 `weekly_volume` / `volume` / `base` 任何一个键。** | 计划 5.2 第 3/4 步的「模板基准量」**不存在**。定口径：时长类 `base = work_min × sets`、次数类 `base = rounds × reps`、**`rest_min` 不计入量**；两种单位不可通约 → `AssembledBlock` **新增 `volume_unit` 字段**（`"min"` / `"reps"` / `"unspecified"`）；未知 shape → `ValueError`，**不得静默取 0**。登记 spec §14 新 **#36** |
| **P5-A2** | **Critical** | 同一模板内同一 `exercise_ref` **跨 session 重复，18/18 全部如此**。130 个 block 的「一周内出现次数」= **`{2:24, 3:42, 4:64}`**，按层 **绿全 2 / 黄全 3 / 红全 4** = 恒等于 `weekly_frequency`。 | `weekly_volume` 若只是「单次课的量」就**名不符实**。定口径：**`weekly_volume = base × sessions_per_week`**，`sessions_per_week` 由装配器**实测统计**（不假设等于 `weekly_frequency`），**新增 `sessions_per_week` 字段**留痕；另配一条守卫测试断言真仓里两者恒等（今天全绿，专家改坏会变红） |
| **P5-A3** | **Critical** | `addons.when` = **`{body_fat_over:12, muscle_low:12}`**；`module` = **`{resistance_priority:12, energy_expenditure_plus_10pct:6, energy_expenditure_plus_5min_hiit:6}`**。**绿层 6 套全部 `addons: []`**；红层 = `(body_fat_over → energy_expenditure_plus_10pct)` + `(muscle_low → resistance_priority)`；黄层 = `(body_fat_over → energy_expenditure_plus_5min_hiit)` + `(muscle_low → resistance_priority)`。 | **原计划判「提高抗阻比重无法自动化、只加 warning、置 needs_review」是错的**：那会让 12 个 `when: muscle_low` 的 addon **永远不被消费**（模板里的死数据）。**更正：肌肉量 < P10 触发时追加该 addon**——追加一个模块**不重排既有结构**，既落地 spec §7.4 又不越「后置处理」的语义边界。`needs_review` **不再由它单独置位**。**addon 的量口径 = `weekly_volume 0.0` + `volume_unit "unspecified"` + 一条 warning**（否掉两个备选：按 ref 名字硬编码规则会让专家加第 4 个 module 时静默失效并抢走 `exercises.yaml` 的所有者；取同 session 均值会跨单位平均）。登记 spec §14 新 **#35** |
| **P5-A4** | **Critical** | `test_domain_purity.py` 的 `ALLOWED_MODULES` = `{dataclasses, enum, collections, collections.abc, numpy, typing}`。**`math` 不在其中**；两份守卫里 `math` 出现 **0 次**。 | 计划 5.1 写的 `math.floor` / `math.ceil` **会让纯净性守卫变红**。**不改守卫**（往 allow-list 加模块是扩大 domain 可用面的架构决策），改用 `int(x)` 与 `-(-x // 1)`。⚠️ `int()` 只在**正数**上等价于 `floor` → `hr_zone` **必须新增 `hrmax_bpm <= 0` 拒绝**，且 docstring 要写明这层因果 |
| P5-A5 | Important | `intensity.type` = **`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24**，而 `INTENSITY_TYPES` 有 **4** 个值 → **`rpe` 真仓 0 次**。形状规整：`hrmax_pct`→`low`+`high`、`onerm_pct`→`value`、`none`→全空。 | `rpe` 档不可达但**必须被覆盖**（domain 分支 100%）→ 手工构造 `Intensity(type="rpe", value=13)` 测。`Intensity.value` 的语义随 `type` 变，写进 docstring |
| P5-A6 | Important | 实测 `0.8 * 0.9` = **`0.7200000000000001`**。 | 计划要求「0.72 字面写死」→ 直接相乘的测试**会红**。定口径：`weekly_volume` 一律 **`round(x, 1)`**；系数本身用 `pytest.approx` |
| P5-A7 | Important | **原计划自相矛盾**：5.2 说 `assembly_snapshot`「键字面固定 **12** 个」并列出 12 个，但同节决定段要求写 `"volume_factor_fallback"`、5.3 又要求写 `"safety_skipped"`——**两个都不在那 12 个里**。 | 拆成两段契约：**`assemble` 恰好 12 个键**；**`apply_safety` 追加至多 3 个**（`safety_triggers` / `safety_skipped` / `safety_volume_factor`，字面钉死）。`endurance_score is None` → `volume_factor_band = "unknown"`，**不加第 13 个键** |
| P5-A8 | Important | `impact_level` **两个住址**：`Block.impact_level`（模板）与 `ExerciseSpec.impact_level`（动作库）。Task 3 已验证 130 个 block 零不一致。 | 定口径：**装配器从 `ExerciseSpec` 取，不从 `Block` 取**。`exercises.yaml` 是**源**、模板里的是冗余副本；读副本会在「专家改了动作库、忘了改 18 套模板」时让安全替换静默失效（Global Constraint #3） |
| P5-A9 | Important | **两套不同名的触发词表**：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`）、`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。YAML 的 `addons.when` 取值 = `ADDON_TRIGGERS` ✓ | `safety.py` 里字面写死 `_TRIGGER_MAP`（键 = 本模块触发名，值 = `(volume_reduction 键 or None, addons.when 键 or None)`），并各加**一条漂移测试**钉住两个上游词表。词表所有者仍是上游两模块，`safety.py` **只消费** |
| P5-A10 | Minor | `BODY_FAT_LIMIT` 实测是 `derive.py` 里**一行 dict 定义** + 一处消费；计划写「`derive.py:68-69` 明写严格大于」——**行号口径错、引文控制者未核**。 | 按硬规矩 #78 改成可 grep 的原文片段，「严格大于」降级为「由实现者复核引文后写明」 |
| P5-A11 | Minor | `Sex` 住在 **`app/domain/indicators.py`**（`class Sex(str, Enum)`），计划 5.2 的 `StudentProfile.sex: Sex` 没写 import 来源。 | 补明 `from app.domain.indicators import Sex`（**绝对导入**，与 `match.py` 引 `Layer` 同口径） |
| P5-A12 | Minor | 加载器实测 8 个公开函数：`load_exercises/exercises/load_equivalence/equivalence/load_templates/templates/sync_exercises/sync_templates`。 | 吃真仓 YAML 的测试用**三个进程内单例**，不用 `load_*`（后者每次重解析 18 份 YAML，还各跑一遍 `yaml.compose` 建行号索引）；单例**进程内共享，不得改写** |
| P5-A13 | — | **控制者错误 #139**：用一个**自己没验证过的正则**（`\(\s*"`）去数 `_PRESCRIPTION_PUBLIC_BASELINE` 的二元组个数，数出 **3**；而同文件里就有 **`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`**，且 `len(__all__) == 24` 双重坐实。 | 计划的「24 个二元组」**是对的，探针是错的**（跨行元组没被单行正则匹配到）。→ **补硬规矩 #80** |

**扫描面复核（计划 5.5 的数字，实测正确、无需更正）**：`app/domain` **10** 个 `.py` + `app/pipeline` **7** + `app/db` **11** = **28**；Task 5 新增 4 个 → domain **14** → 扫描面 **32** ✓

**→ 补硬规矩 #80：用一个探针去数一个已经有字面断言的量，是多此一举且必然自相矛盾——先读那条断言。** 依据：P5-A13 / 控制者错误 #139，这是「把自己没验证的工具输出当事实」的第 8 次（前 7 次见硬规矩 #53/#57/#59/#60/#76/#77）。

**→ 补硬规矩 #81：合并或重写计划正文时，被合并的每一节所引用的「量」（字段名、YAML 键、常量值）必须在合并后重新实测一遍，不得沿用原文。** 依据：P5-A1 / P5-A2 / P5-A3 —— 合并这个动作本身产出了 3 条 Critical，而四节原文分开写时这 3 条**都不存在**（原文各自都指着自己那一节的量）。**压缩散文会静默丢掉「这个量在哪」的上下文。**

**给实现者的可字面写死算例**（控制者实算，`RED-END-ABN-01` 第 1 课，`weekly_frequency = 4`、`week_deltas = [1.0, 1.05, 1.1, 0.85]`，男 20 岁、`endurance_score = 50` → 档 `<60` → `0.8`，性别 `1.0`，系数 **0.8**）：

| block | intensity | structure | base | weekly_volume | 第 1 周 | 第 4 周 |
|---|---|---|---|---|---|---|
| `interval_run` | `{hrmax_pct, low 60, high 70}` | `{sets:4, work_min:3, rest_min:2}` | `3×4 = 12` min/课 | **48.0 min** | **38.4** | `48×0.8×0.85 = 32.64` → **32.6** |
| `compound_circuit` | `{onerm_pct, value 70}` | `{rounds:3, reps:10}` | `3×10 = 30` reps/课 | **120.0 reps** | **96.0** | `120×0.8×0.85 = 81.6` → **81.6** |

`hrmax(20) = 208 − 0.7×20 = ` **194.0**；`hr_zone(194.0, 60, 70)` = `(int(116.4), -(-135.8 // 1))` = **`(116, 136)`**。
`compound_circuit` 的 `hr_zone` = **`None`**、`intensity_text` 含「1RM」。

**计划正文更正**：`_t5_preflight_patch.py`，**21 处替换全部命中 1 次**（脚本逐条打印命中清单即取证，硬规矩 #79）。计划 **129 092 B / 822 行 → 151 467 B / 937 行**（CRLF 未变，无 BOM）。

**下一步**：抽 `task-5-brief.md` → 派实现者。**按 Ruling 145，目标 1–2 轮 fix round。**
---

### Task 5（合并后）: fix round 1 —— 控制者裁定入账（实现者代笔，Ruling 编号留给结案时统一分配）

**代码基线**：`fc8f5a8`（Task 5 的 5.5 收尾，全量 672 passed）→ 本轮 `fix` 一个 commit + `docs` 一个 commit。
**本节的主语**（硬规矩 #56）：下面 5 条裁定全部是**控制者在 fix round 1 派单里下的**，实现者只负责落地与代笔入账；两条新硬规矩（#82 / #83）与一条控制者错误（#140）同理。

#### 一、控制者错误 #140 —— P5-A10 的「更正」本身是错的，整格撤回

**事实（控制者亲跑坐实）**：`backend/app/domain/derive.py` 里 `BODY_FAT_LIMIT` 的定义行**上一行**逐字就是注释「体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，**严格大于**。」，定义行逐字是 `BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`。

**故原计划写的「`derive.py:68-69` 明写严格大于」行号与引文双双正确。**控制者的探针只 grep 了**标识符** `BODY_FAT_LIMIT`、没 grep **注释行**，于是把「我的探针没显示它」讲成了「它不存在」。

**→ 控制者错误 #140**，与同一个 commit（`c8e26b8`）里刚立下的**硬规矩 #80 同型**，这是第 **9** 次「把自己没验证的工具输出当事实」（前 8 次见硬规矩 #53/#57/#59/#60/#76/#77/#80）。

**→ 补硬规矩 #82：探针「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，才允许把「没查到」讲成「不存在」。**

**依据**：账本 Ruling 147 的 **P5-A13**（用一个自己没验证过的正则去数一个已经有字面断言的量，数出 3 而真值是 24）与本次的 **P5-A10** 是**同一根因的两次发作**，而硬规矩 #80 只覆盖了「已有字面断言」那一半——**「探针 0 命中」这一半它管不到**：0 命中看起来像「事实」，而它同样可能是「查询本身无效」。自证的办法只有一步：拿一个**已知存在**的串跑同一条查询，看它是否命中。

**落地**：计划正文 P5-A10 那一格的「更正」列已整格重写为「**撤回**」（补丁脚本 `_t5_fr1_plan_patch.py` 的 E1），5.3 正文里被 P5-A10 改坏的 `BODY_FAT_LIMIT` 描述已恢复成**可核的原文引用**（E2，保留「按可 grep 的原文找、不要按裸行号找」这半句——硬规矩 #78 仍成立），并删掉「原文行号口径错、引文控制者未核」那段自我指控。
⚠️ 表格里 P5-A10 的**事实列**一个字没动（派单只要求重写「更正」列），改由紧邻的「更正」列以「**撤回**」开头整格反驳；已在实现者报告里显式列出请控制者裁定。

#### 二、硬规矩 #83 —— `.pyc` 陈旧失效是**取证陷阱**，不是一般的 flaky

**→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证，必须在跑测试前 `shutil.rmtree(__pycache__, ignore_errors=True)` 并设 `PYTHONDONTWRITEBYTECODE=1`；**等长改动 + 同一秒**会让 CPython 的 `(mtime 截断到秒, size)` 失效判据不触发，于是加载陈旧字节码、产出假红或假绿。**

**依据（Task 5 的 5.5 变异 ④ 实测经过）**：那一条变异打的是 `app/domain/prescription/intensity.py` 里 `hr_zone` 的取整方向（`int(-(-high_bpm // 1))` ↔ 反向写法）。四步是「量基线 → 打变异 → 跑红 → 还原再跑绿」，而**还原后重跑出现了假红**：文件的 sha256 **已经还原成功**（逐字节相同），pytest 却仍然报变异行为。机制是 CPython 的 `.pyc` 失效判据只有两项——**源文件 mtime 截断到秒** 与 **源文件 size**；而那一行的新旧两个写法**恰好等长（都是 47 字符）**，四步又在**同一秒**内完成，于是 `(mtime, size)` 二元组一字未变 → `.pyc` 被判定为仍然有效 → 加载的是**变异版的字节码**。

**已修**：变异脚本改成每次跑测试前 `shutil.rmtree(<模块所在包>/__pycache__, ignore_errors=True)`，并在子进程环境里设 `PYTHONDONTWRITEBYTECODE=1`（不再产出新的 `.pyc`），六次变异全部按新脚本重跑。⚠️ 本轮 fix round 1 的三次取证（`import types` 的纯净性探针、`.pyc` 无关的 YAML 重算、commit 前的全量）也一律带这两项。

**它为什么比一般的 flaky 更危险**（这一条是硬规矩 #83 的立意，不是修饰）：

* **假红**会让人**怀疑一个正确的还原**——于是开始「再还原一次」「再跑一次」，  而真因（陈旧字节码）从来不在被怀疑的清单里；更坏的是有人为了让它变绿而**再改一次代码**，  于是工作树与 index 悄悄分叉。
* **假绿**更坏：它让人以为**一条守卫还在工作**。变异取证的整个价值就是「M1 必须红」，  一次假绿等于把「这条守卫有牙」这个结论建立在一个**没被真正执行过的文件**上——  而这恰好是硬规矩 #50/#53 要挡的那一类「尺子恒绿」。
* 它的触发条件是**两个都很常见的巧合**（等长改动、同一秒完成），  而不是罕见的时序竞争，故**会复发**：任何「语义等价改写」型的变异  （正是硬规矩 #65 的 M1 对照要求的形状）**天然等长**。

#### 三、控制者采纳实现者的两处签名扩参（Plan 02 实现者第 **5**、**6** 次顶回成立）

| # | 落地签名 | 顶回的理由（控制者已认） |
|---|---|---|
| 5 | `apply_safety(pkg, inp, eq, *, template, exercises)` | `TrainingPackage` 里**没有** `addons` / `weekly_frequency`，故 P5-A3 要求的「追加**模板自己的** addon」、addon 的 `exercise_name` / `video_url` / `impact_level`「从 `exercises[addon.module]` 取」、`sessions_per_week = template.weekly_frequency` **一件都给不出来**；替身的 `name` / `url` / `impact_level` 同样只能从 `ExerciseSpec` 取（P5-A8：读**源**、不读模板里的冗余副本）。 |
| 6 | `apply_overrides(pkg, records, *, exercises)` | `SUBSTITUTE_EXERCISE` 若只换 `exercise_ref`，那个 block 会**留着旧动作的视频 URL 与中文名**——学生扫码看到的是被换掉的那个动作，那是「**一个看起来正常的谎**」。 |

**新增的两个形参一律 keyword-only**，口径照 `assemble` 的 `*, exercises`；三个位置参数与计划原文逐字一致。计划正文 5.3 / 5.4 的 `Produces` 两行与 5.3 的 `Consumes` 已同步（补丁脚本的 E5 / E10a / E10b）。

#### 四、本轮另两条 Critical 裁定（F1-1 / F1-2）

| # | 级别 | 裁定 | 落地 |
|---|---|---|---|
| **F1-1** | **Critical** | `assembly_snapshot["weekly_volume_base"]` 原先是**混合量纲**的裸 `float`：`RED-END-ABN-01` 那一格是 `168.0` = `48.0 min + 120.0 reps`，**一个把分钟和次数加在一起的数没有意义**，而它要落进 `prescription.assembly_snapshot` 这个 JSON 列、并在 Plan 03/04 被前端读出来展示，与 P5-A1 自己立的「两种单位不可通约」互相打脸。→ **改成按单位分列的 `Mapping[str, float]`，键数仍然是 12（不动键集契约）**。**实现者上一轮的异议成立、控制者采纳其替代方案。** | 键 = 实际出现过的 `volume_unit`、值 = 该单位下的周量之和 `round(…, 1)`；`RED-END-ABN-01` 逐字面 = `{"min": 48.0, "reps": 120.0}`。**键集不写死**（18 套亲扫 `{("min",): 10, ("reps",): 6, ("min", "reps"): 2}`，`"unspecified"` 0 次）。只读性：`types` **不在** `ALLOWED_MODULES` 里（亲跑：插一句 `import types` → 守卫报 `assembler.py:148: types`），而 `MappingProxyType` 又**不是** JSON 可序列化的（亲跑 `TypeError: Object of type mappingproxy is not JSON serializable`）→ 落地是**屏蔽了全部 8 个 mutator 的私有 `dict` 子类** `_ReadOnlyVolumeBase`，两条约束唯一的交集。新增 6 条守卫（分列字面值 / 键集 / 8 个 mutator / copy+deepcopy+pickle / 12 键 JSON 化 / 15 键 JSON 化）。 |
| **F1-2** | **Critical** | `rpe` 的值域原先写成 Borg 经典的那一套标度，**错了**：spec 全篇的 RPE 都是 **0–10**，四处逐字可 grep（`rpe_record` 表字段「RPE 0–10」、§8.2 小标题「课堂端 RPE（0–10 主观疲劳）」、`RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」、`YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」、大屏异常名单「RPE > 8」）。**这是跨计划契约**：Plan 03 的实现者若把「9 分」读成那套标度的中高档，阈值语义整个错位。 | 值域改 **0–10** 并把出处逐字引进 docstring（硬规矩 #78：不写裸行号）；手工构造的测试值从 `13`（在该标度上非法）改成 `7`，断言的 `intensity_text` 随之改成 `"RPE 7"`；**新增**一道 `[0, 10]` 的运行时拒绝（与 `hr_zone` 的 `0 <= low <= high <= 100` 对称；加载器只校字段形状不校值域；`rpe` 在 18 套模板里出现 **0** 次，故可证明不会让任何真仓模板炸），守卫是 `test_rpe_value_outside_zero_to_ten_is_rejected`（`-0.1` / `0.0` / `10.0` / `10.1`）。 |

#### 五、本轮的验收数字（实现者亲跑）

* 全量：`cd backend; python -m pytest -q` → **679 passed**（基线 672）；带 `--cov=app.domain --cov-branch` → **678 passed, 1 skipped**。⚠️ **差的那 1 个是 `tests/pipeline/test_backfill.py` 里既有的墙钟断言**：它按硬规矩 #42 在 `sys.gettrace()` 非空时**主动跳**，而 `pytest-cov` 正是靠 `sys.settrace()` 实现的。两个数指的是同一套测试，**没有丢测试**（已写进计划 5.5，补丁脚本的 E6）。
* 覆盖率四格：**905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**（基线 888 / 0 / 260 / 0 / 100%；+17 stmts、+2 branch 全部来自 F1-1 的只读映射与 F1-2 的值域拒绝）。spec §12 的硬要求仍满足。
* 公开面 `__all__` = **43**（`_ReadOnlyVolumeBase` 是**私有**的，故 43 → 43；`_PRESCRIPTION_PUBLIC_BASELINE` 与它的两句 `assert … == 43` 一个字没动）。
* 扫描面 = **32**（domain 14 + pipeline 7 + db 11）。
* 三个禁区指纹逐字不变：`D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`；`backend/pe.db` 不存在；`backend/data/seed/` 0 文件；`backend/data/` 一个字节没动。

**下一步**：控制者复核本轮 → Task 5 结案 → 抽 Task 6 简报。
