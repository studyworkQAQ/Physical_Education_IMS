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

亲验：`ITEM_BUCKET` 的 distinct values 是 **4 个**：`{'endurance', 'speed_flexibility', 'strength', None}`——`ITEM_BUCKET[ScoredItem.BMI] is None`（BMI 天然不属于任何短板桶，Plan 01 Ruling 19 的口径）。计划原文说「三个桶名」在**语义上对**，但照字面写 `set(...values())` 会把 `None` 放进取值域、让一个空 `targets` 悄悄合法。→ 明确写成 `frozenset(v for v in ITEM_BUCKET.values() if v is not None)`。

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














