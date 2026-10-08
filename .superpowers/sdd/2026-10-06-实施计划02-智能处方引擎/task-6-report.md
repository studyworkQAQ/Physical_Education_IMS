# Task 6 报告 — `prescription` / `weekly_adjustment` 两张表 + 五触发条件（`triggers.py`）

**实现者**：Task 6 sub-agent
**代码基线**：`3a5bd40`（分支 `feature/plan-02-prescription-engine`）
**结案 HEAD**：`0f559e9`
**三个 commit**：`6bf47f6`（Step 0 + 两张表）→ `3eff251`（`triggers.py` + 27 条测试）→ `0f559e9`（公开面 43 → 47 + 变异取证）
**fix round 数**：**0**（一次跑通，未返工）

---

## 1. 环境与基线复现

### 1.1 开工第一件事（硬规矩 #73）

```
cd backend; python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"
→ 2.1.3
```

**没有撞上 `ImportError: DLL load failed`**（Windows Smart App Control 未拦 `.pyd`），
故按派单继续，未动系统安全设置、未升降级任何依赖。

| 项 | 实测 |
|---|---|
| Python | 3.11.1-final-0（无 venv） |
| SQLAlchemy | **2.1.3** |
| 平台 | win32 |
| pytest 基线（开工前亲跑） | `python -m pytest -q -p no:cacheprovider` → **679 passed in 58.99s** |
| git 基线 | `3a5bd40`，工作树除 `.superpowers/` 下两个未跟踪的简报文件外干净 |
| 分支 | `feature/plan-02-prescription-engine`（**全程未切分支、未 push、未碰 main**） |

### 1.2 结案时的验收数字（第 7 节有完整表）

`716 passed in 61.23s`；带 `--cov=app.domain --cov-branch` 是
`948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%`，`715 passed, 1 skipped in 139.44s`
（那 1 个 skip 是 `test_backfill.py` 既有的墙钟断言，与基线同一个）。

---

## 2. Step 0 的九格逐格落地（P6-A5 / P6-A4）

**全部按可 grep 的原文找，一个裸行号都没用**（硬规矩 #76/#78）。

| # | 文件 | 找到的原文 | 改成 | 落地 |
|---|---|---|---|---|
| 1 | `tests/db/test_models.py` | `def test_all_sixteen_tables_created(session):` | `def test_all_eighteen_tables_created(session):` | 是 |
| 2 | 同上（**两处**） | `assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"` | `== 18` + 中文消息里的「16 张表」→「18 张表」 | 是（两处都改） |
| 3 | 同上 | `assert len(Base.metadata.tables) == 16` | `== 18` | 是 |
| 4 | 同上 | 那段逐字印着 grep 命令的注释：`git grep -n "== 16" -- …` 现命中 **6** 处 = **3** 真断言 + **3** 处本段散文 | grep 串改 `"== 18"`、引出的两条断言原文跟着改；**改完自己重跑 grep 核实：`git grep -c "== 18" -- backend/tests/db/test_models.py` → `6`**（3 真 + 3 散文，结构未变） | 是 |
| 5 | 同上 + `app/db/models/__init__.py` + `app/db/models/prescription.py`（**两处**） | `test_all_sixteen_tables_created` 这个**函数名** | `test_all_eighteen_tables_created`；**重跑 `git grep -c "test_all_eighteen_tables_created" -- backend` → `__init__.py` 1 + `prescription.py` 2 + `test_models.py` 3 = 6**，与 `prescription.py` docstring 里更新后的「现命中 **6** 处」逐字相符（`test_models.py` 的 3 = `def` 行 + 两处注释引用；派单说的是「一处注释引用」，实测是两处，因为本 Task 新增的那条守卫的 docstring 也引了它）。**另跑 `git grep -c "sixteen" -- backend` → 0 命中** | 是 |
| 6 | 同上 | `assert len(_MODELS_PUBLIC_BASELINE) == 33` + 清单本身 → **35**，加 `"Prescription"` 与 `"WeeklyAdjustment"` | **顶回，没做**。基线**仍是 33**、清单一个字没加、`models/__init__.py` **不重导出**这两个类。理由见第 6.2 节「关切 ①」 | **否（刻意）** |
| 7 | `tests/seed/test_generate.py` | `DATA_TABLES = (…9 个…)` | 加 `"prescription"` 与 `"weekly_adjustment"` → **11 个** | 是 |
| 8 | 同上 | `REFERENCE_TABLES` 上方那段「那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区，要按「谁灌它」判」的预告注释 | 改掉：写明「届时」已到、判的结果是 `DATA_TABLES`、判据是「谁灌它」（Task 7 的 `prescription_stage.py` 按学生逐日写 = 管道产物；`exercise` / `prescription_template` 由 YAML 投影 = 参考数据）；并把「归错分区的后果是哪条守卫红」写清 | 是 |
| 9 | 同上 | `assert REFERENCE_TABLES == ("exercise", "prescription_template")` | **不动** | 是（未动） |

`_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**未动** —— 两张表进已有的
`models/prescription.py`，不新增子模块。

### 2.1 派单的九格之外，实测**又撞出两格**（不改就红）

这两格是 Step 0 清单漏的，`prescription.py` 的模块 docstring 里已把它们补进
「加表时要同步改什么」的清单，并给了可 grep 的命令：

| # | 文件 | 找到的原文 | 改成 | 为什么必须改 |
|---|---|---|---|---|
| **10** | `tests/db/test_models.py` | `assert len(json_text_columns) == 9, json_text_columns` | `== 14` | `prescription` 一张表就带来 **5** 个 `JsonText` 列（`training_package` / `assembly_snapshot` / `safety_substitutions` / `teacher_overrides` / `trigger_reasons`），9 + 5 = **14**。这条断言是那条守卫的**反空转牙口**，不改当场红。同一个「9」还住在**另外两处**（硬规矩 #66）：`app/db/models/_shared.py` 的 `JsonText` docstring（「全库九个 JSON 形态的列 …… `len(json_text_columns) == 9` 钉住」）与 `app/db/models/__init__.py` 的约定 3（「九个列，无一例外」）—— **三处都改成了 14** |
| **11** | `tests/db/test_models.py` | `_DERIVED_TABLES = {"derived_metrics", "stratification_result", "percentile_snapshot"}` | 加 `"prescription"` 与 `"weekly_adjustment"` → **五张** | `test_only_derived_tables_expose_batch_id` 按**集合相等**判「谁有 `batch_id` 列」（`assert observed == _DERIVED_TABLES`）。P6-A8 要求两张新表都带 `batch_id`，于是这条**必红**。它还逐表断言每一列真的指向 `daily_sync_run`，故扩容后那五列的 FK 目标也一并被钉住 |

**连带更新的四处散文**（同一个事实「全库只有三张表有 `batch_id`」被本次改动证伪，
硬规矩 #66；前三个文件都不在派单的 Files 段里，见第 6.3 节）：

* `app/db/repo.py::delete_by_batch` 的 docstring —— 两处（「全库只有三张派生表 …… 才有这一列」
  与「故本函数可安全传入的只有上面那三张派生表」），改成五张，并写明
  「**今天** `daily.py` 的 `_replay_cleanup` 只清 Plan 01 那三张，Task 7 会把两张处方表接进来，
  且删的顺序承重（必须先删子表 `weekly_adjustment`）」；
* `app/db/models/assessment.py::FitnessTestResult` 的 docstring —— 一处（「只有三张派生表才
  允许拥有它」）；
* `tests/db/test_models.py` 的四处按数写死的散文：`test_no_column_uses_builtin_sqlalchemy_json`
  的「遍历 16 张表」→ 18、`test_models_public_namespace_is_unchanged_by_the_split` 的
  「16 张表一个不少」→ 18、`test_string_column_widths_fit_their_value_domains` 的
  「今天 **15** 列」→ **17**（清单里补上 `prescription.status` 与 `weekly_adjustment.source`）、
  `test_sqlite_foreign_keys_are_enforced` 的「schema 里 20 个外键」→ **24**（取法与逐项归因
  写在那条 docstring 里，Task 6 亲跑：
  `sum(len(c.foreign_keys) for t in Base.metadata.tables.values() for c in t.columns)`）。

`app/pipeline/daily.py`（3 处）与 `app/pipeline/backfill.py`（1 处）的「三张派生表」
**刻意没改**：那几处说的是 `_replay_cleanup` **今天实际删哪些表**，而本 Task 没有改
`_replay_cleanup`，故它们**今天仍然为真**。改它们才是造假。已进第 6.1 节待清扫清单，归 Task 7。

### 2.2 Step 0 之后先跑一遍（预期的红）

Step 0 只改测试基线、还没建表时，`test_all_eighteen_tables_created` 一类会红在
「表数不符」上——这是**预期的红**。实际操作上我把 Step 0 与两张表放在同一个 commit
（`6bf47f6`）里落地，中途跑的是
`python -m pytest tests/db tests/seed tests/architecture tests/test_refdata_prescription.py -q -p no:cacheprovider`
→ 第一次 **1 failed, 139 passed**，红的是
`test_same_day_second_prescription_for_one_student_is_rejected`，原因是**我自己的断言写错了**
（我以为 SQLite 的 UNIQUE 报错会带约束名，实测它印的是列名：
`UNIQUE constraint failed: prescription.student_id, prescription.generated_on`；
带 `ck_*` 名字的是 CHECK 那一档）。已改成按实测文本断言，并另从 DDL 反查约束名
（`inspect(conn).get_unique_constraints("prescription")`）把 `uq_prescription_student_day`
钉住。改完 **232 passed**。

---

## 3. 两张表的最终列清单

取法：Task 6 亲跑的探针脚本（`create_engine("sqlite:///:memory:")` + `init_db` +
`inspect`，跑完即删、未入库），逐列印 `c.name` / `c.type` / `c.nullable`。

### 3.1 `prescription`（**15 列**）

| # | 列名 | 类型（反射口径） | 可空 | 备注 |
|---|---|---|---|---|
| 1 | `id` | INTEGER | NOT NULL | PK |
| 2 | `student_id` | INTEGER | NOT NULL | FK → `student.id` |
| 3 | `generated_on` | DATE | NOT NULL | 与 `student_id` 组成唯一约束 |
| 4 | `batch_id` | INTEGER | NOT NULL | FK → `daily_sync_run.id`，`index=True`（`ix_prescription_batch_id`） |
| 5 | `template_ref` | VARCHAR(32) | NOT NULL | **P6-A7**：不叫 `template_id`，与 `prescription_template.template_ref` 同名 |
| 6 | `microcycle_weeks` | INTEGER | NOT NULL | **P6-A3 新增**：`prescription_template` 表里没有它，生成当时从 `Template.microcycle_weeks` 快照下来 |
| 7 | `training_package` | TEXT（`JsonText`） | NOT NULL | |
| 8 | `assembly_snapshot` | TEXT（`JsonText`） | NOT NULL | 契约是「恰好 12 键 / `apply_safety` 至多追加 3 键」，**未动** |
| 9 | `safety_substitutions` | TEXT（`JsonText`） | NOT NULL | |
| 10 | `teacher_overrides` | TEXT（`JsonText`） | NOT NULL | 取代计划里那张**不存在**的 `prescription_override` 表 |
| 11 | `previous_had_overrides` | BOOLEAN | NOT NULL，`default=False` | **P6-A2 新增**：取代「往 `assembly_snapshot` 加第 16 个键」的原方案 |
| 12 | `status` | VARCHAR(16) | NOT NULL，**无缺省** | CHECK `ck_prescription_status` |
| 13 | `valid_from` | DATE | NOT NULL | |
| 14 | `valid_to` | DATE | **NULL** | 与 Plan 01 的 `stratification_result.valid_to`（恒 NULL）处置相反，「为什么两者不同」逐字写在 `Prescription` 的 docstring 里 |
| 15 | `trigger_reasons` | TEXT（`JsonText`） | NOT NULL | **列表**，全部命中者，按 spec 编号序 |

表级约束：

* `UniqueConstraint("student_id", "generated_on", name="uq_prescription_student_day")`
  —— Review Focus 第 2 条的**机制**侧（同一天被两次触发只生成一张处方）；
* `_in_domain("status", Prescription.STATUSES, "ck_prescription_status")`，
  `STATUSES = {"active", "replaced", "archived", "needs_review"}`（类常量，P6-A9），
  生成的约束文本实测逐字为
  `status IN ('active', 'archived', 'needs_review', 'replaced')`（字典序）。

### 3.2 `weekly_adjustment`（**8 列**）

| # | 列名 | 类型 | 可空 | 备注 |
|---|---|---|---|---|
| 1 | `id` | INTEGER | NOT NULL | PK |
| 2 | `prescription_id` | INTEGER | NOT NULL | FK → `prescription.id`（**不声明 `relationship`**，本包统一约定） |
| 3 | `batch_id` | INTEGER | NOT NULL | **P6-A8 新增**：FK → `daily_sync_run.id`，`index=True`（`ix_weekly_adjustment_batch_id`） |
| 4 | `week` | INTEGER | NOT NULL | 1-based；**不加 CHECK**（上界是那张处方自己的 `microcycle_weeks`，写死就是把「4 周」硬编码进 DDL） |
| 5 | `factor` | FLOAT | NOT NULL | 乘法语义（`0.8` = 减量 20%）；**不加取值范围 CHECK**（口径要体育专家给，spec §14 待登记） |
| 6 | `reason` | TEXT | NOT NULL | 自由文本，照 `cleaning_log.reason` 的既有口径用 `Text` |
| 7 | `source` | VARCHAR(8) | NOT NULL | CHECK `ck_weekly_adjustment_source` |
| 8 | `created_at` | DATETIME | NOT NULL，**无缺省** | 时钟由调用方注入（Global Constraint #1）；不用 Python 侧也不用 `server_default` |

表级约束：`_in_domain("source", WeeklyAdjustment.SOURCES, "ck_weekly_adjustment_source")`，
`SOURCES = {"auto", "teacher"}`（类常量，P6-A9），生成的约束文本实测逐字为
`source IN ('auto', 'teacher')`。`"auto"` 今天**没有任何生产写入方**（spec §8.4 的
「预警触发减量 20%」留给 Plan 03），现在就进值域是因为届时往一个已结案的 CHECK 里加值
等于重建库（本仓不做迁移）。

### 3.3 P6-A2 / A3 / A8 三列的位置

| 更正 | 列 | 在 |
|---|---|---|
| **P6-A2** | `prescription.previous_had_overrides`（BOOLEAN NOT NULL default False） | `prescription` 第 11 列 |
| **P6-A3** | `prescription.microcycle_weeks`（INTEGER NOT NULL） | `prescription` 第 6 列 |
| **P6-A8** | `weekly_adjustment.batch_id`（INTEGER NOT NULL, FK `daily_sync_run.id`, index） | `weekly_adjustment` 第 3 列 |

**`prescription_template` 一列未加、一字未改**（P6-A3 明写「刻意不给它加列」）；
本 Task 新增的
`test_prescription_microcycle_weeks_is_snapshotted_on_the_row_not_on_the_template`
把这件事钉成守卫：`assert len(PrescriptionTemplate.__table__.c) == 10`。

### 3.4 为两张表新增的 10 条 DB 测试（`tests/db/test_models.py`）

派单只说「改六处」，但 `Prescription` / `WeeklyAdjustment` 的 docstring 里凡写下
「守卫是 ……」就必须真的有那条守卫（硬规矩 #39），故新增：

1. `test_plan02_tables_stay_out_of_the_models_public_namespace`（顶回第 6 格后**替代**它的守卫，见 6.2 关切 ①）
2. `test_prescription_template_ref_is_the_same_name_as_the_template_table_column`（P6-A7）
3. `test_prescription_template_ref_column_is_as_wide_as_the_template_table_one`（硬规矩 #18 的补位：无 CHECK 的列自己钉列宽，两列各自对**字面量 32** 断言）
4. `test_prescription_status_is_required_and_its_check_rejects_unknown_values`
5. `test_weekly_adjustment_source_check_rejects_unknown_values`
6. `test_prescription_microcycle_weeks_is_snapshotted_on_the_row_not_on_the_template`（P6-A3）
7. `test_prescription_previous_had_overrides_is_a_column_not_a_snapshot_key`（P6-A2）
8. `test_same_day_second_prescription_for_one_student_is_rejected`（Review Focus 第 2 条）
9. `test_delete_by_batch_reaches_both_new_tables`（**P6-A8 的前提当场验**：把「有这一列」升级成「按它删真的能删掉」，并钉住「先删子表」这个承重顺序）
10. `test_prescription_valid_from_is_required_and_valid_to_is_not`

---

## 4. `triggers.py` 的公开面与五条触发的实现口径

### 4.1 公开面（**恰好 4 个公有顶层定义**）

`TriggerReason` / `LastPrescription` / `TriggerInput` / `evaluate_triggers`。
唯一的模块级常量 `_DAYS_PER_WEEK = 7` **带前导下划线**，故不被
`tests/test_refdata_prescription.py::_public_top_level_definitions`（AST 口径）数到——
多一个公有顶层定义，那条穷尽守卫（支 5）当场红。

四处同步扩容（`43 → 47`）：

| 住址 | 改动 |
|---|---|
| `app/domain/prescription/__init__.py` | `from .triggers import (LastPrescription, TriggerInput, TriggerReason, evaluate_triggers)` + `__all__` 追加同名 4 项（带一段说明声明序口径的注释） |
| `tests/test_refdata_prescription.py::_PRESCRIPTION_PUBLIC_BASELINE` | 追加 4 个二元组，所有者一律 `"app.domain.prescription.triggers"` |
| 同上，**两处** `assert len(...) == 43` | → **47**（`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 47` 与 `assert len(set(names)) == 47`；Task 5 的实现者踩过「只改一处」的坑） |
| 同上，`_OWNED_MODULES` | 七个 → **八个**模块（加 `"app.domain.prescription.triggers"`） |

`app.domain.prescription.__all__` 的实测长度：**43 → 47**。

### 4.2 五条判据的实现口径

| # | 触发 | 实现（`triggers.py` 里的字面） | 口径要点 |
|---|---|---|---|
| **0** | （不是五条之一）Z0 早退 | `if inp.current_label == Layer.INSUFFICIENT.value: return ()` | **函数第一句**、无条件、`teacher_requested=True` 也不例外。**P6-A6：用 `Layer.INSUFFICIENT.value`，全模块不出现第二份 `"insufficient_data"` 字面串**；`from app.domain.stratify import Layer` 是**绝对导入**（与 `match.py` 同口径） |
| 1 | 首次产生分层结果 | `if last is None: hits.append(FIRST_STRATIFICATION)` | 触发 2/3/4 都住进 `else` 那一支：不是省事，而是「没有上一张时那三条无从判起」的口径本身 |
| 2 | 分层标签发生变化 | `if inp.current_label != last.label_at_generation:` | 比**生成当时**的标签 |
| 3 | 微周期到期 | `if (inp.as_of - last.generated_on).days >= last.microcycle_weeks * _DAYS_PER_WEEK:` | `>=` 不是 `>`；周数从上一张处方取，**不硬编码 4** |
| 4 | 数据刷新 | `if inp.latest_assessment_date is not None and inp.latest_assessment_date > last.generated_on:` | **严格晚于**；`None` 短路 |
| 5 | 教师手动请求 | `if inp.teacher_requested: hits.append(TEACHER_REQUESTED)` | 无条件成立，但**排在 tuple 最后** |

**返回 `tuple(hits)`**（全部命中者，不是第一个）；顺序 == `TriggerReason` 声明序 ==
spec §5.2 编号序。**空时返回 `()` 而不是 `None`**，与第 0 条早退同型，故调用方只需一条读法。

三个刻意**不进判据**的字段，各有一条测试把它钉成期望行为：

* `current_template_id` —— 携带但不读（`test_current_template_id_is_not_a_trigger_criterion`）；
* `LastPrescription.template_id` —— 同上；
* `LastPrescription.status` —— `needs_review` **不**抑制触发 3（否则一张有安全问题的处方
  永远挂着不换），`archived` **不**被当作「没有上一张」（否则学期归档后重新开学变成一次
  静默的首次生成）。守卫是
  `test_first_stratification_does_not_fire_when_there_is_a_last_prescription` 与
  `test_microcycle_expiry_still_fires_for_a_replaced_or_needs_review_prescription`。

### 4.3 `dt.date` / `timedelta` 的类型标注：**实测到的既有做法是哪一种**

派单第 6 节第 1 条要求「先去看 `match.py` / `assembler.py` / `templates.py` 今天是怎么写
`dt.date` 类型标注的，照抄那个既有做法，并在报告里写明实测到的是哪一种」。

**实测结论：是「前向引用字符串标注 + 运行时 duck typing 只读属性」，不是
`from __future__ import annotations` + `TYPE_CHECKING`。**

取证（在基线 `3a5bd40` 上跑
`git grep -n "^from __future__|TYPE_CHECKING|dt\.date" -- backend/app/domain`）：

* `app/domain/` 下 **14 个 `.py` 里 `from __future__` 命中 0 处、`TYPE_CHECKING` 命中 0 处**；
* `intensity.py`：`def age_from(birth: "dt.date", as_of: "dt.date") -> int:`，模块 docstring
  逐字写着「**本模块不 import `datetime`** …… 标注写成**前向引用字符串** `"dt.date"`」；
* `assembler.py`：`birth: "dt.date"`、`as_of: "dt.date"`，docstring 写「运行时只读它们的
  `year` / `month` / `day` / `isoformat`」，并写明**代价**是
  `typing.get_type_hints(assemble)` 会抛 `NameError`；
* `override.py`：`applied_at: "dt.datetime"`，docstring 写「运行时本模块**一个属性都不读它**」；
* `templates.py`：干脆把 `Template.reviewed_at` 做成 `str | None`（ISO 串），
  docstring 写「`datetime` 不在 allow-list 里 …… 这不是偷懒」；
* `match.py`：**一个日期字段都没有**（它的三个维度是层 / 桶 / 体成分）。

`triggers.py` 两半都照抄：标注一律 `"dt.date"` / `"dt.date | None"` 前向引用字符串，
**模块里没有任何 `import datetime`**（`ALLOWED_MODULES` 实测 =
`{dataclasses, enum, collections, collections.abc, numpy, typing}`，`datetime` 不在其中）。

**但既有做法只覆盖了「标注」这一半，覆盖不到触发 3 的运行时算术**——
计划判据表写的算式是 `as_of - last_prescription.generated_on >= timedelta(weeks=microcycle_weeks)`，
而 **`timedelta` 同样 import 不到**，且既有四个模块**没有一个需要在运行时构造日期/时间对象**
（它们只**读**属性）。这一格派单没给答案（它只说「照抄既有做法」），故按同一条纪律外推：

**处置：不构造 `timedelta`，只读减法结果的 `.days`。**
`date - date` 的结果**自己就是**一个带 `.days` 的对象，于是判据写成
`(inp.as_of - last.generated_on).days >= last.microcycle_weeks * _DAYS_PER_WEEK`
——这与 `assembler.py` 读 `as_of.isoformat()`、`intensity.py` 读 `birth.year` 是**同一条**
「只读注入对象的属性、不新建日期对象」的纪律，没有发明新东西。

**等价性**：对 `datetime.date` 操作数，`date - date` 恒为整数天的 `timedelta`，而
`timedelta(weeks=W) == timedelta(days=7*W)`，故
`a - b >= timedelta(weeks=W)` 与 `(a - b).days >= 7*W` **逐格等价**。

**为什么不接受「把 `datetime` 加进 `ALLOWED_MODULES`」这个看起来更省事的选项**：
`assembler.py` 的 docstring 已经为同一件事表过态——「往 allow-list 加模块是**扩大 domain
可用面**的架构决策，不是一个 Task 能顺手做的（与 `datetime` / `math` 同一条纪律）」。
一旦放行 `datetime`，`FORBIDDEN_CALLS` 那条守卫就从「domain 根本拿不到时钟」退化成
「只挡 `datetime.now()` 这一种写法」，而 `test_domain_has_no_clock_or_file_access` 的
docstring 亲跑取证过 **7 种绕过写法**（`__import__` / `eval` / `getattr` / 别名 …）。不划算。

**守卫**：`test_evaluate_triggers_only_needs_subtraction_and_greater_than_on_dates`
把一个只实现 `__sub__`（返回带 `.days` 的对象）与 `__gt__` 的替身喂进去，三格断言照过。
它把「只需要这两个方法」这个**最小契约**钉住，于是「偷偷补一句 `from datetime import
timedelta`」这条退路被堵死（架构守卫会红，但那条红的原因与本契约隔了一层）。

**守不住什么**（已写进 `triggers.py` 的 docstring）：这个等价只在操作数是 `date` 时成立。
谁传 `datetime.datetime` 进来，`a - b` 会带 `seconds`，而 `.days` 对**负**差值向下取整
（`timedelta(days=-1, seconds=1).days == -1`）。契约是 `date`，故不为此加防御。

### 4.4 27 条测试的分布

| 组 | 条数 | 代表 |
|---|---|---|
| 契约（成员 / 字段 / frozen / `str` 混入 / 漂移） | 4 | `test_trigger_reason_has_exactly_the_five_spec_triggers_in_spec_order`、`test_insufficient_label_value_is_pinned_verbatim`（P6-A6 的漂移测试） |
| 第 0 条早退 | 2 | `test_insufficient_data_label_never_triggers`（**48 格穷举** = 有没有上一张 2 × 上一张标签 3 × 到期 2 × 新采集 2 × 教师 2；含「其余四条全部成立」那一格的空转守卫） |
| 触发 1 | 2 | `test_first_stratification_triggers_only_once` |
| 触发 2 | 4 | `test_layer_change_compares_against_the_label_at_generation`（黄→红→黄三天） |
| 触发 3 | 3 | `test_microcycle_expiry_is_inclusive_on_day_28`、`test_microcycle_weeks_comes_from_the_previous_template_not_a_hardcoded_four` |
| 触发 4 | 4 | `test_assessment_on_or_before_the_generation_day_does_not_trigger`（`==` 那一格刻意不触发） |
| 触发 5 | 2 | `test_teacher_request_triggers_alone` |
| 组合与顺序 | 3 | `test_the_returned_order_is_the_declaration_order_not_the_evaluation_order`（上一条的**反面对照**，硬规矩 #50） |
| 纯函数 / 无 I/O | 3 | `test_evaluate_triggers_is_deterministic`（**Step 6b**）、duck typing 那条 |

派单 Step 1 点名的 10 条测试**全部落地**，且各有一条以上的边界/反面对照陪衬。

**Step 6 的两条集成测试按 P6-A1 整体移到 Task 7，本 Task 只做 Step 6b**。
`backend/tests/pipeline/` 下**没有**新增任何文件。

---

## 5. 变异取证（3 条 + M0 + M-EQ，硬规矩 #83 / #65）

### 5.1 取证纪律（每一步都做了）

变异脚本（临时文件 `t6_mutation.py`，放在仓库根、跑完即删、未 `git add`）里：

* 每次改文件**之前与之后**都 `shutil.rmtree(__pycache__, ignore_errors=True)`，
  并且额外扫一遍 `BACKEND.rglob("__pycache__")` 全清；
* 子进程的 `env` 里设 `PYTHONDONTWRITEBYTECODE=1`；
* pytest 一律带 `-p no:cacheprovider`；
* 变异方式是**在内存里对原始字节做 `str.replace` 后整体 `write_bytes`**，
  锚点原文先 `assert src.count(old) == 1`（命中不是 1 次就当场停），
  故不存在「改错地方」或「改了不止一处」；
* 还原是 `TARGET.write_bytes(ORIG)`（`ORIG` 是脚本开头读的原始字节），
  随后**三重还原验证**：① sha256 逐字相同、② 目标测试文件复跑全绿、③ **全量** 716 条复跑全绿。

**为什么这么小心**：Task 5 的实现者做过一次等长改动（47 字符 → 47 字符）且四步在同一秒内
完成 → CPython 按 `(mtime 截断到秒, size)` 判失效、加载了陈旧字节码、产出**假红**。
本次四条变异的字节数分别是 22197 / 22269 / 22268 / 22234，**没有一条与原始的 22270 等长**，
且每次前后都清了 `__pycache__`，故不存在那档风险。

### 5.2 基线

```
sha256(backend/app/domain/prescription/triggers.py) = a771dc8470bda8e5b7587660173c39c700f22daabc902babb1c6ee0ed15f85a3
bytes = 22270
```

结案后复算（`Get-FileHash … -Algorithm SHA256`）**逐字相同**，即三次变异全部还原干净。

### 5.3 M0（不变异，全绿对照）

`rc=0`，`27 passed in 0.16s`。**M0 不绿则后面所有的红都不可信**，故脚本里写成 `assert rc == 0`。

### 5.4 M1 —— 删掉 `Layer.INSUFFICIENT.value` 的早退（Step 7 的 ①）

**改了哪一行**：整段删掉 `evaluate_triggers` 的第 0 条（3 行 → 0 行）

```python
    if inp.current_label == Layer.INSUFFICIENT.value:
        return ()

```

变异后 `sha256 = 3fcf8abe9c50ac1bb0688afbe8854ce7200c6e872d4f0c6799c54c46b5770fc7`（22197 B）。

**哪条测试的哪个断言分支变红**：
`tests/domain/test_prescription_triggers.py::test_insufficient_data_label_never_triggers`
——48 格穷举循环里那一句

```python
        assert evaluate_triggers(case) == (), (
            f"insufficient_data 的学生不该生成处方（Review Focus 第 3 条）：{case}"
        )
```

**开火的是第一格**：`has_last=False` × `label="red"` × `expired=False` × `assessment=None` ×
`teacher=False` 那一格，`current_label="insufficient_data"` 而 `last is None` → 早退没了就走
触发 1 → 返回 `(FIRST_STRATIFICATION,)`。pytest 印的原文（截断形态）：

```
E           assert (<TriggerReas...tification'>,) == ()
```

即「实际侧多出一个 `TriggerReason.FIRST_STRATIFICATION`，期望侧是空 tuple」。
**这正是 Review Focus 第 3 条要防的失效**：Z0 闸门拦下的学生拿到了一张处方。

全文件 `3 failed, 24 passed`（`rc=1`）——另外两条红的是
`test_no_last_prescription_and_insufficient_label_returns_empty` 与
`test_the_insufficient_early_return_reads_the_enum_not_a_second_literal`，
即「早退」这件事有**三处**守卫，删掉一处三处一起响。

**三重还原**：`sha256 = a771dc84…f85a3`，**与变异前逐字相同 = True**；
目标文件 `27 passed`；全量 `716 passed in 64.98s`。

### 5.5 M2 —— 触发 3 的 `>=` 改成 `>`（Step 7 的 ②）

**改了哪一行**：

```python
-        if elapsed_days >= last.microcycle_weeks * _DAYS_PER_WEEK:
+        if elapsed_days > last.microcycle_weeks * _DAYS_PER_WEEK:
```

变异后 `sha256 = e9b950114c8ec8817bd3e44a0112c00291547ba5bd2e9178baa187dee856e481`（22269 B）。

**哪条测试的哪个断言分支变红**：
`test_microcycle_expiry_is_inclusive_on_day_28` 的这一句（第 28 天当天那一格）

```python
    assert evaluate_triggers(_inp(as_of=_DAY_28, last=_last(weeks=4))) == (
        TriggerReason.MICROCYCLE_EXPIRED,
    )
```

`_DAY_28 = 2026-03-30`、`_GENERATED_ON = 2026-03-02` → `elapsed_days == 28`、
`weeks * 7 == 28`，`28 > 28` 为假 → 返回 `()`。pytest 印的原文：

```
E       AssertionError: assert () == (<TriggerReas...le_expired'>,)
```

即「实际侧空了，期望侧那一个 `MICROCYCLE_EXPIRED` 没了」。**开的正是 `>=` 与 `>` 的
边界那一支**，不是别的原因。同一条测试里紧邻的
`assert evaluate_triggers(_inp(as_of=_DAY_27, last=_last(weeks=4))) == ()`（第 27 天）
**保持绿**——这证明红的原因是边界那一格，而不是整条判据被删。

全文件 `6 failed, 21 passed`（`rc=1`）：另外 5 条红的是所有「恰好落在第 N×7 天」的格子
（`test_microcycle_weeks_comes_from_the_previous_template_not_a_hardcoded_four` 的第 14 天、
`test_microcycle_expiry_still_fires_for_a_replaced_or_needs_review_prescription` 的四个 status、
以及两条组合测试）；而「超过到期日很多」的格子（`2026-04-15`、`2026-04-13`）**保持绿**，
再次说明红的是边界而不是判据整体。

**三重还原**：`sha256 = a771dc84…f85a3`，**逐字相同 = True**；目标文件 `27 passed`；
全量 `716 passed in 64.80s`。

### 5.6 M3 —— 触发 2 改成比模板 id（Step 7 的 ③，**与派单字面有偏离，见下**）

**改了哪一行**：

```python
-        if inp.current_label != last.label_at_generation:
+        if inp.current_template_id != last.template_id:
```

变异后 `sha256 = a87b1f8c65b20b2b8feb961b0413faa63cd509c23fd1a1864120ce5443a7b894`（22268 B）。

**哪条测试的哪个断言分支变红**：
`test_layer_change_compares_against_the_label_at_generation` 的**第三天（D3）那一句**

```python
    # D3：回到黄，而库里那张**仍是 P1**（红那天的生成被拒）→ 不触发
    assert evaluate_triggers(
        _inp(as_of=dt.date(2026, 3, 4), label="yellow",
             template_id="YEL-STR-NOR-01", last=p1)
    ) == ()
```

`p1.template_id == "YEL-END-NOR-01"`，D3 的 `current_template_id == "YEL-STR-NOR-01"`
→ 变异后 `!=` 成立 → 返回 `(LAYER_CHANGED,)`。pytest 印的原文：

```
E       AssertionError: assert (<TriggerReas...er_changed'>,) == ()
```

即「实际侧多出一个 `LAYER_CHANGED`，期望侧是空 tuple」——**「黄→红→黄」第三天又触发一次**，
正是简报判据表点名的失效形态。

**同一条测试的 D1 与 D2 两句保持绿**（D1 走 `last is None` 那一支，D2 的
`current_template_id="RED-END-NOR-01"` 与 `p1.template_id="YEL-END-NOR-01"` 本来就不等），
故红的**只有** D3 那一格，指向性精确。

全文件 `5 failed, 22 passed`（`rc=1`）：另外 4 条红的是
`test_current_template_id_is_not_a_trigger_criterion`（那条**专门**为这个方向写的守卫，
它把「只改 `current_template_id`、其余不动，结果必须逐字不变」钉成期望行为）、
`test_layer_change_fires_when_the_label_differs_from_the_one_at_generation`
（三对合法层各一格，模板 id 相同时变异后一律不触发）与两条组合测试。

**三重还原**：`sha256 = a771dc84…f85a3`，**逐字相同 = True**；目标文件 `27 passed`；
全量 `716 passed in 67.31s`。

#### 与派单字面的偏离（必须交代）

派单 Step 7 的 ③ 写的是「触发 2 改成比较**「上一次运行的标签」**而不是 `label_at_generation`」。
**这个变异在钉死的契约里不可表达**：

* 「上一次运行的标签」= 上一个业务日那次**分层重算**产出的标签，它住在
  `stratification_result` 表里、**每天一行**；
* 而 `TriggerInput` 的六个字段是派单 Interfaces / Produces **逐字**给的
  （`as_of` / `current_label` / `current_template_id` / `last_prescription` /
  `latest_assessment_date` / `teacher_requested`），`LastPrescription` 的五个字段同样是
  逐字给的（`generated_on` / `template_id` / `label_at_generation` / `microcycle_weeks` / `status`）；
* **两份契约里都没有「上一次运行的标签」这个字段**。而那个字段的**缺席正是设计本身**——
  简报判据表说「比较的是生成当时的标签，不是上一次运行的标签」，
  实现层面把后者**根本不传进来**，就是最彻底的办法。

故取**最近的可表达变异**：把触发 2 的右操作数从 `last.label_at_generation` 换成
`last.template_id`（左操作数相应换成 `inp.current_template_id`）。它是同一族失效
（「触发 2 比错了参照物」），而且是一个**真实可能被写出来的误读**
（「该换模板了就该换处方」），并且**同一条「黄→红→黄」测试抓得住它**（上面已实测开火）。
另外**专门为这个方向补了一条守卫** `test_current_template_id_is_not_a_trigger_criterion`，
把「`current_template_id` 被携带但不被读」钉成期望行为——派单的测试清单里没有这一条。

**代价**：这一条变异证明的是「触发 2 不比模板 id」，**不是**「触发 2 不比上一次运行的标签」。
后者由**契约本身**保证（那个字段不存在），并由
`test_the_two_value_objects_are_frozen_and_carry_the_pinned_fields`
（逐字钉住两个值对象的字段名与顺序）间接守住：谁想比「上一次运行的标签」，
得先往 `TriggerInput` 加一个字段，那条测试当场红。已记进第 6.2 节关切 ③。

### 5.7 M-EQ —— 语义等价改写（**尺子不得恒红**的反面对照）

**改了哪一行**：把触发 3 的两行折成一行（语义逐格相同）

```python
-        elapsed_days = (inp.as_of - last.generated_on).days
-        if elapsed_days >= last.microcycle_weeks * _DAYS_PER_WEEK:
+        if (inp.as_of - last.generated_on).days >= last.microcycle_weeks * _DAYS_PER_WEEK:
```

变异后 `sha256 = f652fd70d9f903c6f9c20c938a458a12b7e1daaeb060fd6fd3c3d6384785e564`（22234 B）。

**结果：`rc=0`，`27 passed in 0.17s`——全绿。**

这一条与 M0 互补：M0 证明「不改东西时尺子是绿的」，M-EQ 证明「改了东西但**语义没变**时
尺子**仍然**是绿的」，于是上面三条红**不是**因为「这个文件一动就红」。

**三重还原**：`sha256 = a771dc84…f85a3`，**逐字相同 = True**；目标文件 `27 passed`；
全量 `716 passed in 74.49s`。

### 5.8 变异小结

| 变异 | 改动 | 目标测试 | 开火的断言 | 全文件 | 还原后 sha256 相同 | 还原后全量 |
|---|---|---|---|---|---|---|
| M0 | 无 | — | — | 27 passed | — | 716 passed |
| M1 | 删掉 Z0 早退（3 行） | `test_insufficient_data_label_never_triggers` | `assert evaluate_triggers(case) == ()` | 3 failed / 24 passed | 是 | 716 passed |
| M2 | 触发 3 `>=` → `>` | `test_microcycle_expiry_is_inclusive_on_day_28` | `assert evaluate_triggers(_inp(as_of=_DAY_28, last=_last(weeks=4))) == (MICROCYCLE_EXPIRED,)` | 6 failed / 21 passed | 是 | 716 passed |
| M3 | 触发 2 比 `template_id` | `test_layer_change_compares_against_the_label_at_generation` | D3 那一句 `assert evaluate_triggers(...) == ()` | 5 failed / 22 passed | 是 | 716 passed |
| M-EQ | 两行折一行（语义等价） | — | 无（必须全绿） | 27 passed | 是 | 716 passed |

---

## 6. 待清扫清单 + 关切

### 6.1 待清扫清单（**8 条**，按 Ruling 145 不单独返工）

| # | 项 | 归属 | 为什么今天不动 |
|---|---|---|---|
| 1 | `_DERIVED_TABLES` 这个常量名在含 `prescription` / `weekly_adjustment` 之后**名不副实**（它俩不是「派生指标」，是管道产物）。改名要连带改 `app/db/repo.py` 与 `app/db/models/assessment.py` 里引用这个说法的散文 | Task 7 | 已在常量上方写了 12 行注释说明这件事，并点名了改名要连带改哪两处；Task 7 接 `_replay_cleanup` 时正好一并做 |
| 2 | `app/pipeline/daily.py`（3 处）与 `app/pipeline/backfill.py`（1 处）的「三张派生表」散文 | Task 7 | **今天仍然为真**：`_replay_cleanup` 实际只删那三张。Task 7 把两张处方表接进去时才变成假话 |
| 3 | `tests/db/test_repo.py` 的文件头写「九条 `ck_*` 取值域约束」，而同一文件下方写「十条」，今天全库实测是 **17** 条 | Task 7/9 | 那两个数是历史遗留（Task 6 之前就不自洽），且那个 `parametrize` 清单是显式列举、加 CHECK 不会让它红 |
| 4 | `app/db/models/__init__.py` 的「小节划分」RST 简单表：`.prescription` 那一行改成了三行续行，而列宽标记（`====`）没跟着加宽，渲染会溢出 | Task 9 | 本仓没有 docutils/Sphinx 构建，不影响任何测试；改它要重排整张表 |
| 5 | `Prescription.valid_from` 今天恒等于 `generated_on`（Task 7 才可能让它们分开），故「两列语义不同」的口径虽已写进注释，**今天没有测试能区分它们** | Task 7/8 | 现在写测试只能钉「两列都存在」，那是空话；等 Task 8 的读模型落地再补 |
| 6 | `weekly_adjustment.factor` 没有取值范围 CHECK，故 `factor = 0` 或负数在库层面**放行**、今天无人拦 | Plan 03 | 合理区间要体育专家给（spec §14 待登记）；今天写一个 `0.5..1.5` 就是凭空造口径。已在 docstring 里写明「Plan 03 的教师端表单必须自己拦」 |
| 7 | spec §14 待登记两项：① 触发 4 的「任何新采集都算刷新，不限 week16」是**工程决定**；② `factor` 的合理区间 | Task 9 | 计划明写「归 Task 9 登记」 |
| 8 | `typing.get_type_hints(evaluate_triggers)` 会抛 `NameError`（前向引用字符串 `"dt.date"` 的既有代价，与 `intensity` / `assembler` / `override` 同） | Plan 03 | 不是缺陷、是既有纪律的代价；但 Plan 03 若上 FastAPI / pydantic（要对模型做 `get_type_hints`）必须显式处置 |

### 6.2 关切（我认为派单/计划错了的地方，按优先级排）

#### ① **顶回派单 Step 0 的第 6 格（Critical，已按我的判断实现）**

**哪条决定**：派单第 2 节「修改 `backend/app/db/models/__init__.py` —— 重导出两个新类」
+ Step 0 第 6 格「`_MODELS_PUBLIC_BASELINE` **33 → 35**，加 `"Prescription"` 与
`"WeeklyAdjustment"`（按字母序插）」+ 第 12 节要求报告里给「`_MODELS_PUBLIC_BASELINE` 的新值」。
三处口径一致，故不是笔误。

**为什么错**：它与账本 **Ruling 97** 直接冲突，而那条裁定**有一条活着的守卫测试**，
其 docstring 逐字把「基线被更新成含新名字」列为**它要防的失效形态**：

> `tests/test_refdata_prescription.py::test_prescription_template_is_not_in_the_models_public_namespace`
> 「……那条按 33 个名字的**集合相等**判，本条按「具体的两个名字不在里面」判，故
> **那条被改坏（例如基线被更新成含新名字）时本条仍然红**。」

`app/db/models/__init__.py` 里也逐字写着同一条纪律（Task 2 与 Task 3 各守过一次）：

> 「Plan 02 新加的表类……**刻意不进** `__all__`、也没有 `from .prescription import *`：
> `test_models_public_namespace_is_unchanged_by_the_split` 钉的是**拆包之前**（基线
> `e26347f`）实测的 33 个公有名，往那份基线里加 Plan 02 的新名字等于把「拆包没改导入面」
> 偷换成「拆包后的现状」，**两侧就同源了（硬规矩 #35）**。」

三条具体后果：

1. **那条测试的函数名会变成谎话**：`…is_unchanged_by_the_split` 判的将是
   「拆包**改了**导入面，且恰好改出这两个名字」；
2. **硬规矩 #35 被破坏**：基线从「拆包前实测的字面清单」变成「拆包后的现状」，
   两侧同源，漏导出与多导出一起漂；
3. **与 Task 2/3 不一致**：`Exercise` 与 `PrescriptionTemplate` 都在导入面**之外**，
   而 `Prescription` / `WeeklyAdjustment` 在**之内** —— 同一个包、同一类东西、两套规矩，
   而 `tests/test_refdata_prescription.py` 那条守卫只查前两个名字，**不会红**，
   于是这个不一致会静默留下来。

**我的替代方案（已实现）**：

* `_MODELS_PUBLIC_BASELINE` **仍是 33**，一个字没加；
* `models/__init__.py` **不重导出**这两个类（`from . import feedback, prescription` 那一句
  已经把两张表注册进 `Base.metadata`，不需要别的）；
* 新增守卫 `tests/db/test_models.py::test_plan02_tables_stay_out_of_the_models_public_namespace`：
  逐名断言 `"Prescription"` / `"WeeklyAdjustment"` 既不在 `M.__all__` 里、也不是 `M` 的属性，
  同时断言 `hasattr(M.prescription, name)`（表类**必须**存在）与
  `{"prescription", "weekly_adjustment"} <= set(Base.metadata.tables)`（表**必须**注册）；
  并再钉一次 `len(_MODELS_PUBLIC_BASELINE) == 33`；
* 在 `models/__init__.py` 里把这次顶回**逐字写进注释**（含「Task 7 的写入方请写
  `from app.db.models.prescription import Prescription, WeeklyAdjustment`」），
  免得 Task 7 的实现者「顺手补一句 `from .prescription import *` 而自以为在修一个漏掉的导出」
  ——那正是 Ruling 97 那条守卫 docstring 点名的失效形状。

**若控制者仍要按派单字面做，改动是**（两版都成立，我实现了我认为对的那一版）：

```python
# app/db/models/__init__.py，在 `from . import feedback, prescription` 之后加
from .prescription import Prescription, WeeklyAdjustment  # noqa: F401

# tests/db/test_models.py
assert len(_MODELS_PUBLIC_BASELINE) == 35          # 33 → 35
# 清单里按字母序插两个：…"PercentileSnapshot", "Prescription", "Semester"…
#                        …"UniqueConstraint", "WeeklyAdjustment", "dt"…
# 并删掉我新增的 test_plan02_tables_stay_out_of_the_models_public_namespace
# 并改写 test_prescription_template_is_not_in_the_models_public_namespace 的 docstring
#（它逐字把「基线被更新成含新名字」列为要防的失效，照字面做之后那句就是假话）
```

**代价**：`test_models_public_namespace_is_unchanged_by_the_split` 的语义与函数名一起作废，
Ruling 97 的守卫要改写，且 Plan 02 的四张表在导入面上分裂成两套规矩。

#### ② **Step 0 的九格清单漏了两格，且漏的是「一定会红」的那两格（Important）**

派单第 4 节把 Step 0 称作「本 Task 最容易踩的坑」并给了九格，但
`assert len(json_text_columns) == 9` 与 `_DERIVED_TABLES` 都不在里面。
两者都是**按集合/条数相等**判的硬断言，加表必红（第 2.1 节）。

**根因**：这两格与派单列出的六格不是同一类——六格是「表数 16 这一个事实的多处副本」，
两格是「**别的**事实（JsonText 列数、谁有 batch_id）被同一个改动连带证伪」。
`prescription.py` 的模块 docstring 里那份「加表时要同步改什么」的清单**同样只有前一类**，
故我已把后一类补进去，并各给一条可 grep 的命令
（`git grep -n "json_text_columns" -- backend/tests/db/test_models.py` 与
`git grep -n "_DERIVED_TABLES" -- backend/tests/db/test_models.py`）。
**建议**：Task 7/8/9 若再加表，直接跑那四条 grep，不要照任何清单。

#### ③ **变异 ③ 的字面要求在钉死的契约里不可表达（Important）**

详见第 5.6 节末。摘要：「上一次运行的标签」这个量在 `TriggerInput` / `LastPrescription`
的十字段契约里**没有对应物**，而那个缺席正是设计本身。我取了最近的可表达变异
（比 `template_id`）并**另补一条专门的守卫**。
**建议**：Step 7 的变异清单在派单前应先核一遍「这个量在契约里存在吗」——
与 P6-A1 是**同一根因的第 3 次**（派单让实现者做一件当场做不到的事；账本 Ruling 103、
硬规矩 #75、P6-A12 补的 #86 都在说这件事）。

#### ④ **触发 3 的 `timedelta` 在 domain 里构造不出来，派单只给了一半答案（Important）**

派单第 6 节第 1 条说「`triggers.py` 要用 `timedelta`……照抄既有做法」，
但既有做法（前向引用字符串标注）**只覆盖标注、覆盖不到运行时算术**，
而那四个模块恰好**都不需要在运行时构造日期对象**。详见第 4.3 节。
我的处置（只读减法结果的 `.days`）是既有纪律的直接外推，且配了 duck typing 守卫。
**建议**：把「domain 里怎么算日期差」写进账本作为一条正式裁定，
Task 8 的 `weekly.py`（「本周训练单 = 骨架第 N 周 × 系数」）大概率也要算日期。

#### ⑤ **spec §5.2 有一个真实的空洞：模板变了但标签没变（Important）**

同一层里主导短板（`W`）或体成分（`C`）翻了，标签不变而该练的模板变了，
**五条触发一条都不成立**，而 `current_template_id` 刻意不是判据（spec 只有五条，
加第六条是改 spec）。今天它由**触发 4** 兜住：`W` / `C` 的变化必然伴随一次新采集
→ `latest_assessment_date` 前进 → 触发 4 成立。
**但这个兜底依赖触发 4 的工程口径**（「任何新采集都算刷新，不限 week16」）；
若将来把触发 4 收窄成 spec 字面的「学期末 / week16」，这个空洞就会真的漏人
（学生练着一套针对另一个短板的处方，最长漏一个学期）。
已写进 `triggers.py` 的模块 docstring，并建议连同触发 4 的口径一起登记 spec §14（归 Task 9）。

#### ⑥ **最高优先级关切（简报 Step 1 点名要报）：`insufficient_data` 早退会让教师端「重新生成」按钮无声失败**

我**同意**这个决定（数据不足时产出处方是把「不知道」讲成「知道」，与 Z0 同构），
但派单/计划对它的**代价**只写了半句。完整的账是：

* Plan 01 实测缺省注入下 500 人有 **2 人**落这一档（Plan 01 的数字，本 Task 未复跑）；
* 对这 2 人，教师点「重新生成」→ `evaluate_triggers` 返回 `()` → Task 7 不生成 →
  **UI 上什么都没有发生**；
* `evaluate_triggers` 是纯函数、返回空 tuple，它**没有任何渠道**把「为什么是空」传出去
  （返回值里没有 reason，而 `MatchOutcome` 那种「六种 status 一律留痕」的设计在这里没有对应物）。

**建议给 Task 7 的硬性要求**（本 Task 做不到，因为 `prescription_stage.py` 那时才建）：
① 求值前先看 `current_label`，是 `insufficient_data` 就**不要**把它当成「今天没触发」，
而是走一条独立的留痕路径（`daily_sync_run` 的一个计数列，或一条 `warning` 日志，
或教师端的一个显式提示「该生有效项不足 4 项，本日不生成处方」——文案可直接复用
`stratify._REASON` 的 Z0 那一句，`match.py` 已有先例）；
② 教师端的手动请求路径要能把这个原因**回给前端**，不能只返回 200 + 空结果。
**若不做的后果**：教师会反复点、反复没反应，最后判定「系统坏了」——
而这恰好是最需要人工介入的那 2 个学生。

#### ⑦ 两个我自己做的决定（计划没写，报出来备核）

* **`prescription.status` 刻意没有默认值**（与 `daily_sync_run.status` 的
  `default="failed"` 相反）。理由：那一列在 INSERT 时还不知道结局、默认值取保守侧；
  而 `status` 在 INSERT 那一刻**已经知道**了，给一个 `default="active"` 会让「忘了写」
  静默变成「这张处方是好的」，而 spec §7.4 恰恰要求安全规则命中却找不到等价动作时落成
  `needs_review`、**不得静默跳过**（Review Focus 第 5 条）。守卫是
  `test_prescription_status_is_required_and_its_check_rejects_unknown_values`
  （断言 `column.default is None` 且漏传当场 `IntegrityError`）。
* **两个值对象的类声明序是 `LastPrescription` 先于 `TriggerInput`**，而简报
  Interfaces / Produces 那一行列的是 `TriggerInput` 在前。理由：本包既有口径是
  「声明序照模块里的书写序」且「值对象自底向上」（见 `__init__.py` 里 Task 5 的 5.2
  那一条注释），而被嵌套的 `LastPrescription` 应当在引用它的 `TriggerInput` 之前。
  **字段名与字段顺序照简报逐字**，守卫是
  `test_the_two_value_objects_are_frozen_and_carry_the_pinned_fields`。
  类声明序本身不被任何断言钉住。

### 6.3 我**没按派单做**的地方（**5 处**，逐处显式列出）

| # | 派单要求 | 我做的 | 依据 |
|---|---|---|---|
| 1 | Step 0 第 6 格：`_MODELS_PUBLIC_BASELINE` 33 → 35、`models/__init__.py` 重导出两个新类 | **都没做**：基线仍 33、不重导出，改为新增一条守卫 | 关切 ①（与 Ruling 97 冲突，那条守卫的 docstring 逐字把这个动作列为要防的失效） |
| 2 | Step 7 变异 ③：「触发 2 改成比较『上一次运行的标签』」 | 改成比较 `current_template_id != last.template_id`，并**另补一条**守卫 `test_current_template_id_is_not_a_trigger_criterion` | 关切 ③（字面要求的那个量在钉死的契约里不存在） |
| 3 | 计划判据表：触发 3 = `as_of - generated_on >= timedelta(weeks=microcycle_weeks)` | `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（对 `date` 操作数逐格等价） | 关切 ④（domain import 不到 `datetime`，`timedelta` 构造不出来；既有做法只覆盖标注） |
| 4 | 第 2 节的「修改」清单只有 6 个文件 | 实际改了 **9 个**：多出的 3 个是 `app/db/models/_shared.py`、`app/db/repo.py`、`app/db/models/assessment.py`，**全是散文**（「九个 JsonText 列」→ 14、「三张派生表」→ 五张） | 硬规矩 #66：一个事实变了要 grep 出全部同类陈述逐个更新。这三处都被本次改动**证伪**（不是「精度不够」，是「现在是假话」），故按 Ruling 145 的例外条款当场修，不进待清扫 |
| 5 | 派单只要求 `tests/db/test_models.py` 改**六处** | 另**新增 10 条测试**（第 3.4 节） | `Prescription` / `WeeklyAdjustment` 的 docstring 里凡写「守卫是 ……」就必须真的有那条守卫（硬规矩 #39）；其中 3 条是 P6-A2/A3/A8 三条更正**唯一**的可执行判据 |

**Step 6 只做 6b 不算偏离**——那是派单自己按 P6-A1 要求的。

---

## 7. 最终验收

### 7.1 数字对照

| 项 | 基线（`3a5bd40`） | 结案（`0f559e9`） | 命令 |
|---|---|---|---|
| `pytest -q` | 679 passed | **716 passed in 61.23s**（+37） | `cd backend; python -m pytest -q -p no:cacheprovider` |
| 覆盖率四格 | 905 stmts / Miss 0 / 262 branch / BrPart 0 / **100%** | **948 / 0 / 274 / 0 / 100%** | 同上 + `--cov=app.domain --cov-branch --cov-report=term-missing` |
| 带 `--cov` 的 passed | 678 passed, 1 skipped | **715 passed, 1 skipped in 139.44s** | 同上 |
| `triggers.py` 自己的四格 | — | **42 stmts / Miss 0 / 12 branch / BrPart 0 / 100%** | 同上 |
| 表数 | 16 | **18** | `test_all_eighteen_tables_created` |
| `app.domain.prescription.__all__` | 43 | **47** | `test_prescription_public_namespace_is_pinned_verbatim` |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 43 | **47**（两处 `assert len(...)` 都改了） | 同上 |
| `_OWNED_MODULES` | 七个模块 | **八个模块** | 同上（支 5） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33（刻意未动，见关切 ①）** | `test_models_public_namespace_is_unchanged_by_the_split` + 新增那条 |
| `models.__all__` | 14 | **14（未动）** | 同上 |
| 架构守卫扫描面 | 32（pipeline 7 + db 11 + domain 14） | **33（pipeline 7 + db 11 + domain 15）** | Task 6 亲跑：`{d: len(list(pathlib.Path('app',d).rglob('*.py'))) for d in ('pipeline','db','domain')}` |
| `JsonText` 列数 | 9 | **14** | `test_no_column_uses_builtin_sqlalchemy_json` |
| 带 `batch_id` 的表 | 3 | **5** | `test_only_derived_tables_expose_batch_id` |
| `_in_domain` CHECK 列数 | 15 | **17** | `test_string_column_widths_fit_their_value_domains` |
| schema 外键数 | 20 | **24** | 第 2.1 节那条 `sum(len(c.foreign_keys) …)` |
| `backend/data/` 文件数 | 23 | **23（一个字节未动）** | 见 7.2 |

三条架构守卫全绿：`test_domain_imports_stay_within_the_allow_list`（`triggers.py` 只 import
`dataclasses` / `enum` / `app.domain.stratify`）、
`test_domain_has_no_clock_or_file_access`、`test_domain_has_no_filesystem_access`
（⚠️ 第三条是**子串**匹配，故 `triggers.py` 全文——含 docstring——一个
`FORBIDDEN_IO` 子串都没有：无 `Path(`、无 `__file__`、无 `import os`、无 `.read_text`、
无 `json.load`）。`tests/architecture` 亲跑 **4 + 4 = 8 passed**。

### 7.2 三个禁区（逐字复核，Task 6 亲跑）

指纹口径：`sha256(裸字节.replace(b"\r\n", b"\n"))[:16].upper()`（照 `tests/test_refdata.py`
的 `STANDARD_FINGERPRINT`，先归一化行尾再哈希，因为 `core.autocrlf` 在 Git for Windows 上
缺省为 `true`）。

| 文件 | 钉住值 | 结案实测 | 逐字相同 |
|---|---|---|---|
| `backend/data/national_standard_2014.csv` | `D2C8E539E2FA0029` | `D2C8E539E2FA0029`（21412 B） | **是** |
| `backend/data/exercises.yaml` | `3DE598AF38631209` | `3DE598AF38631209`（22739 B） | **是** |
| `backend/data/exercise_equivalence.yaml` | `822CB86A5E998301` | `822CB86A5E998301`（8245 B） | **是** |

* `git diff --stat 3a5bd40 HEAD -- backend/data` → **空输出**（一个字节未动）；
* `backend/data/` 下 **23 个文件**，与基线同数（18 份模板 YAML + `exercises.yaml` +
  `exercise_equivalence.yaml` + `indicator_ranges.yaml` + `national_standard_2014.csv` +
  `README_national_standard.md`）；
* `backend/data/seed/` → **存在，0 个文件**；
* `backend/pe.db` → **不存在**（`Test-Path` → `False`）；
* **全程没有跑** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`；
* `backend/` 下 `__pycache__` 目录数 → **0**（变异取证脚本每轮前后都清，结案复核也是 0）；
* 临时文件（`backend/t6_probe.py`、`t6_mutation.py`、`t6_mutation.log`、`t6_finalize.py`、
  `t6_r{1,2,3}.md`）**全部已删**，`git status --short` 里除了 `.superpowers/` 下那两个
  开工前就未跟踪的简报文件外**干净**。

### 7.3 三个 commit

| sha | 说明 | 变更量 |
|---|---|---|
| `6bf47f6` | `feat: Plan02 Task6 的 Step 0 + 两张表 —— prescription / weekly_adjustment，16 → 18 张表` | 7 files, +728 / −87 |
| `3eff251` | `feat: Plan02 Task6 的 triggers.py —— spec §5.2 五触发条件求值，27 条测试全绿` | 2 files, +1014 |
| `0f559e9` | `feat: Plan02 Task6 的收尾 —— 公开面 43 → 47，全量 716 passed` | 2 files, +63 / −15 |

合计 `git diff --stat 3a5bd40 HEAD`：**11 files changed, 1805 insertions(+), 102 deletions(-)**。
commit 信息一律用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`；
`git add` 一律**按文件名逐个加**（未用 `-A` / `.`）；**未 push、未切分支、未碰 main**。

⚠️ `git add` 时 git 报了两条 `LF will be replaced by CRLF the next time Git touches it`
（`triggers.py` 与新测试文件）。这是本仓 `core.autocrlf=true` 的既有行为、对所有 `.py` 都成立，
**index/HEAD 里的 blob 是 LF**；`.gitattributes` 只把 `backend/data/` 钉成 `eol=lf`。
后果：若将来重新检出，`triggers.py` 的**工作树字节**会从 LF 变 CRLF，
第 5.2 节那个 sha256 就不再是工作树哈希（它仍逐字对应 HEAD 的 blob 内容）。
这与硬规矩 #46 说的是同一件事，非本 Task 引入。

### 7.4 硬约束逐条自检

| 约束 | 结论 |
|---|---|
| `app/domain/` 无任何 I/O（allow-list + 三条守卫） | **满足**：`triggers.py` 只 import `dataclasses` / `enum` / `app.domain.stratify`；无 `datetime` / `math` / `types` / `json` / `os` / `sys` / `pathlib`；无 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。时间与「教师点没点」全部由 `TriggerInput` 注入 |
| `app/domain/` 分支覆盖 100% | **满足**：`Miss 0 / BrPart 0`（`triggers.py` 42/0/12/0） |
| 单一所有者（`Layer` 归 `stratify.py`） | **满足**：只消费 `Layer.INSUFFICIENT.value`，配一条漂移测试字面钉住该值 |
| 断言两侧不同源（硬规矩 #35） | **满足**：五个 `.value`、48 格穷举的期望、日期字面量、CHECK 文本、列宽 32 / 14、`uq_*` 约束名全部**字面写在测试里**；唯一刻意同源的是那条漂移测试，其「同源」正是它的职责（已在 docstring 里写明） |
| TDD 先红后绿 | **满足**：先落一个只 `return ()` 的桩 → `13 failed, 14 passed`，红的全是断言不符（不是 `ModuleNotFoundError`）→ 再实现 → 27 passed |
| 禁区 | **满足**：见 7.2 |
| PowerShell / 写文件一律走 python / commit 用 `-F` | **满足**：报告与 3 条 commit 信息全部由 python `write_bytes` 落盘；未用 `Add-Content`；未用 heredoc；未在 `python -c` 里嵌双引号（复杂逻辑一律写临时 `.py`） |
| `git add` 按文件名逐个加 | **满足** |
