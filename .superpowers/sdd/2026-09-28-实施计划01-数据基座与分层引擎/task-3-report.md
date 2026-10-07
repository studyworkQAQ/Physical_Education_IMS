# Task 3 报告：数据模型与 Repository（14 张表）

- **Status:** DONE_WITH_CONCERNS
- **Commit:** `7f12b74` `feat: 建立 14 张表的数据模型与 Repository，业务日期唯一约束保障幂等`
- **Branch:** `feature/plan-01-data-foundation`（base `ec7cf4f`）
- **测试:** 32 → **37 passed**（新增 5，既有 32 一条未改、单独复跑仍 32 passed）；`-W error` 下同样 37 passed，输出洁净
- **工作树:** `git diff HEAD --stat` 为空；仅 4 个新文件，无任何既有文件被修改

---

## 1. 实现了什么

### 1.1 `backend/app/db/session.py`（40 行）

| 产出 | 说明 |
|---|---|
| `class Base(DeclarativeBase)` | 14 张表的唯一声明基类，`Base.metadata` 即建表唯一真相 |
| `engine(url="sqlite:///pe.db") -> Engine` | 引擎工厂，薄封装 `create_engine` |
| `Session` | **直接就是 `sqlalchemy.orm.Session` 类本身**（`from sqlalchemy.orm import Session` 再导出），不是绑定引擎的 `sessionmaker` 实例 |
| `init_db(eng) -> None` | `Base.metadata.create_all(eng)`；`models` 在**函数体内**才 import，避免与 `models → session` 的导入环 |

`Session` 选类而非 `sessionmaker` 的理由：brief 的测试逐字写 `Session(eng)`，`sqlalchemy.orm.Session.__init__` 的首位参数就是 `bind`，故 `Session(eng)` 天然成立；同时调用方自带引擎，测试跑内存库、CLI 跑磁盘库共用同一份代码，导入期不必把 URL 钉死。

`init_db` 可重复调用（`create_all` 对已存在的表跳过），已实测连续两次调用不炸、表数仍为 14。

### 1.2 `backend/app/db/models.py`（489 行）

14 张表，字段严格按 spec §4.1–§4.3、§4.6，全部 SQLAlchemy 2.x 声明式（`Mapped[...]` + `mapped_column(...)`，无 1.x 的裸 `Column`）。**不声明任何 `relationship`**：管道按 `batch_id` 批量读写，显式 `select` 比懒加载可预测，也不会在 Session 关闭后触发延迟查询。

三条贯穿全表的约定写在模块 docstring 里：

1. **缺测就是 `NULL`，绝不是 0**（Ruling 21）——8 项原始测量与 7 项国标得分全部可空。
2. **枚举取值域两处设防**——类常量集合 + SQL 层 `CheckConstraint`，且**约束文本由模块级私有助手 `_in_domain(column, allowed, name)` 从类常量生成**，不是手写第二遍；取值按字典序排序使 DDL 文本稳定。手写两遍迟早漂移，而漂移是静默的。
3. **JSON 形态的列一律用 `JsonText`**（见 §2）。

七组枚举列（每组都是「类常量 `set` + `CheckConstraint`」）：

| 表.列 | 类常量 | 约束名 |
|---|---|---|
| `course_section.grouping_mode` | `GROUPING_MODES` | `ck_course_section_grouping_mode` |
| `fitness_test_batch.timepoint` | `TIMEPOINTS` | `ck_fitness_test_batch_timepoint` |
| `stratification_result.label` | `LABELS` | `ck_stratification_result_label` |
| `stratification_result.percentile_source` | `PERCENTILE_SOURCES` | `ck_stratification_result_percentile_source` |
| `percentile_snapshot.source` | `SOURCES` | `ck_percentile_snapshot_source` |
| `daily_sync_run.status` | `STATUSES` | `ck_daily_sync_run_status` |
| `cleaning_log.kind` | `KINDS` | `ck_cleaning_log_kind` |
| `student.sex` / `percentile_snapshot.sex` | `Student.SEXES`（后者复用同一常量） | `ck_student_sex` / `ck_percentile_snapshot_sex` |

三个 brief 测试断言的常量都声明为**普通 `set`**（非 `frozenset`），测试用 `==` 比对集合字面量。

**三条承重结构要求，逐条落地并已实测：**

1. `DailySyncRun.__table_args__` 含 `UniqueConstraint("semester_id", "business_date", name="uq_daily_sync_run_semester_business_date")`。brief 的 `test_daily_sync_run_business_date_is_unique` 通过；另在临时探针里对**已提交**的行重复插入，同样被数据库拒收。
2. `DerivedMetrics.batch_id` 与 `StratificationResult.batch_id` 均为 `ForeignKey("daily_sync_run.id")`，且各带 `index=True`（`delete_by_batch` 是本任务交付的 API，Task 11 有 500 人 × 112 天 < 60 秒的硬预算，不给它建索引等于让每次重放全表扫）。实测索引名 `ix_derived_metrics_batch_id` / `ix_stratification_result_batch_id` 确已建出。
3. `StratificationResult.hit_rules` 是 `Mapped[str]`（`String(128)`），**不是关系**。语义同时写进类 docstring 与列的 `comment=`：「逗号分隔的规则 ID 序列；最后一项为命中者，前缀是已评估但未命中的规则」，并说明保留前缀是为回答「这个学生为什么不是红色层」（spec §4.3 可追溯性）与供 `explain()` 生成文案；`insufficient_data` 时为空串（与 Task 9 的 `hit_rules == ()` 对应）。实测存 `"R1,R2,Y1"` 读回原样。

### 1.3 `backend/app/db/repo.py`（50 行）

只有两个函数，对 14 个模型通用，不针对任何一张表特化：

- `upsert(session, model, key_fields: Sequence[str], values: dict) -> Any` — 按 `key_fields` 逐条 `where` 查出实例；查到则只更新**非键**字段并返回，查不到则 `model(**values)` + `session.add` 并返回。**不 commit 也不 flush**：事务边界留给调用方，Task 10 的「整批失败回滚」才成立。`values` 缺任一 `key_fields` 直接 `KeyError`——那是调用方传错键的程序缺陷，若退化成「查不到」就会静默插入重复行。
- `delete_by_batch(session, model, batch_id: int) -> int` — `session.execute(delete(model).where(model.batch_id == batch_id))`，返回 `result.rowcount`。

没有加缓存、批量优化或仓储类层次（YAGNI，Task 10 若需要会自己说）。

---

## 2. JSON 列的决策与理由（本任务最重要的一处判断）

**决策：8 个 JSON 形态的列全部用一个自定义的 `JsonText(TypeDecorator)`，`impl = Text`、`cache_ok = True`，bind 时 `json.dumps(value, ensure_ascii=False)`、result 时 `json.loads(value)`；`None` 存 SQL `NULL` 而不是 `'null'` 文本。**

涉及的 8 列：`interest_survey.dimensions`、`interest_survey.raw_answers`、`derived_metrics.annual_change`、`derived_metrics.weaknesses`、`derived_metrics.body_comp_reasons`、`stratification_result.input_snapshot`、`cleaning_log.original_value`、`cleaning_log.processed_value`。

### 2.1 为什么不用 SQLAlchemy 自带的 `JSON` 类型（实测证据）

我先按 `JSON` 实现，跑通了 dict/list 往返，随后对**标量**取值做了聚焦探针，发现真实缺陷。`CREATE TABLE` 渲染为 `original_value JSON`，而 SQLite 的亲和性规则里 `JSON` 落到 **NUMERIC** 亲和性——凡「看起来像数字」的值会被就地转成原生数值，不再是 JSON 文本。原始输出：

```
RAW_STORED [('float_0.0', 'integer', '0'), ('float_65.5', 'real', '65.5'),
            ('int_3', 'integer', '3'), ('str_numeric', 'text', '\'"65.0"\''), ...]
float_0.0      -> int    0          # ← 传进去的是 Python float 0.0
```

即 `original_value = 0.0` 存成 SQLite `integer 0`，**读回来是 Python `int 0`，浮点被降成整型**。对 `cleaning_log` 这种存标量的审计列，这是实打实的失真：「原值 65.0 kg」会被记成「原值 65」，而审计记录的全部价值就在于原值不被改写（spec §4.6：「必须能交代每一条被剔除或修正的数据」）。dict/list 列不受影响（JSON 对象/数组不是「看起来像数字」，仍存为 TEXT），所以这个坑只在标量列上出现——**恰好是 `cleaning_log` 那两列**，而 Task 5 的 `CleaningEntry.original/processed` 类型标注正是 `object`。

### 2.2 改成 `JsonText` 后的实测

```
CREATE TABLE cleaning_log ( ... original_value TEXT, processed_value TEXT, ... )
RAW_STORED [('float_0.0','text',"'0.0'"), ('float_65.5','text',"'65.5'"),
            ('int_3','text',"'3'"), ('str_numeric','text','\"65.0\"'),
            ('str_text','text','"缺测"'), ('none','null','NULL'),
            ('bool_true','text',"'true'"), ('list','text',"'[1, 2]'"),
            ('dict','text','{"k": 1.5}')]
读回类型: float 0.0 / float 65.5 / int 3 / str '65.0' / str '缺测' / NoneType None
          / bool True / list [1, 2] / dict {'k': 1.5}
```

`0.0` 读回 `float 0.0`（类型保真），`None` 存 SQL `NULL` 读回 `NoneType`（不是字符串 `"None"`——那是审计记录里最难被发现的一类谎报），字符串 `"65.0"` 保持字符串（不被当成数字）。`ensure_ascii=False` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。

**为什么统一用在全部 8 列，而不是只给那两列用**：一套落法就没有「这一列要不要自己 `json.dumps`」的不对称，那种不对称正是会被忘掉、且忘掉后静默出错的地方。调用方（Task 10）拿到手的直接是与 domain 值对象同构的 `dict`/`list`（`DerivedResult.annual_change: dict[str, float]`），不必各自再约定序列化格式。

`cache_ok = True` 是**必需**的：`TypeDecorator` 子类若不声明它，SQLAlchemy 会对每条用到该列的语句发 `SAWarning`（无法生成缓存键），在 `-W error` 下直接变成失败。已声明并实测无警告。

代价（登记为关切）：`JsonText` 底层是 TEXT，将来若迁到 PostgreSQL，不会自动用上原生 `jsonb`，数据库侧无法直接做 JSON 路径查询。本项目是 SQLite 原型，且没有任何查询需求落在 JSON 内部，故接受。

---

## 3. TDD 证据

### 3.1 RED

```
$ cd backend; python -m pytest tests/db -v
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
collecting ... collected 0 items / 1 error
=================================== ERRORS ====================================
__________________ ERROR collecting tests/db/test_models.py ___________________
tests\db\test_models.py:6: in <module>
    from app.db.session import init_db, Session
E   ModuleNotFoundError: No module named 'app.db.session'
=========================== short test summary info ===========================
ERROR tests/db/test_models.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 1.65s ===============================
```

**为什么这是预期的失败**：brief Step 2 逐字预测 `FAIL — ModuleNotFoundError: app.db.session`。此时 `backend/app/db/` 下只有一个 0 字节的 `__init__.py`（Task 1 留下的空包标记），`session.py` 尚不存在，故在**收集阶段**就 ImportError，5 个测试一个也跑不起来。失败原因正是「实现不存在」，不是测试自身写错——这是有效的红。

### 3.2 GREEN

```
$ cd backend; python -m pytest tests/db -v
collected 5 items

tests/db/test_models.py::test_all_fourteen_tables_created PASSED         [ 20%]
tests/db/test_models.py::test_daily_sync_run_business_date_is_unique PASSED [ 40%]
tests/db/test_models.py::test_stratification_label_domain PASSED         [ 60%]
tests/db/test_models.py::test_grouping_mode_domain PASSED                [ 80%]
tests/db/test_models.py::test_timepoint_domain PASSED                    [100%]

============================== 5 passed in 0.29s ==============================
```

与 brief Step 4 的 `PASS，5 passed` 一致。测试文件**逐字照抄 brief**，未改一个字。

### 3.3 全量

```
$ cd backend; python -m pytest -q -W error
.....................................                                    [100%]
37 passed in 0.31s

$ cd backend; python -m pytest tests/architecture tests/domain tests/test_refdata.py -q
................................                                         [100%]
32 passed in 0.08s      # 既有 32 条单独复跑，仍全绿
```

32 → 37，只增不减；`-W error` 下无 SQLAlchemy 弃用警告、无 `SAWarning`。

### 3.4 额外取证（临时探针，已删除、未入库）

brief 的 5 条测试**不覆盖 `repo.py`**，也不覆盖 `CheckConstraint` 是否真在库层生效。为了不把未验证的代码交出去，我另写了一个临时脚本（`$env:TEMP` 下，提交前已 `Remove-Item` 删除，工作树无残留），实测结论：

- **表数恰好 14**，表名与 brief 的集合逐一相符，无多余表（`prescription` / `exercise` / `weekly_adjustment` / `class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 一个都没建）。
- **DDL 落地情况**（读 `sqlite_master`）：`cleaning_log / course_section / daily_sync_run / fitness_test_batch / percentile_snapshot / stratification_result / student` 带 `CHECK`；`daily_sync_run / enrollment / semester / student / teacher` 带 `UNIQUE`。
- **8 类脏值全部被数据库自身拒收**（不靠 Python 侧校验，`IntegrityError`）：`label='crimson'`、`percentile_source='city'`、`grouping_mode='mixed'`、`status='ok'`、`sex='unknown'`、`percentile_snapshot.source='city'`、`cleaning_log.kind='whatever'`、`timepoint='week3'`；外加 `daily_sync_run` 同学期同业务日期重复插入。**UPDATE 路径同样被 CHECK 拦住**（不只是 INSERT）。
- **`repo.upsert`**：改已存在的行时行数 1 → 1、主键不变、非键字段被更新（`name` 改为「张三丰」、`grade` 1 → 2）；插新行时正常返回新实例；**复合自然键**（`["semester_id", "business_date"]`）也能正确命中已有行且不新增；`values` 缺键字段时抛 `KeyError('student_no')`。
- **`repo.delete_by_batch`**：`derived_metrics` 删 2 行、`stratification_result` 删 1 行，**另一批（`run2`）的行完好留下**（`left ['2025-09-16']`）；不存在的 `batch_id` 返回 0 而不抛。
- `engine()` 工厂 + `init_db` 对磁盘库连续调用两次不炸，表数仍 14。

---

## 4. 变更文件

```
7f12b74 feat: 建立 14 张表的数据模型与 Repository，业务日期唯一约束保障幂等
 backend/app/db/models.py        | 489 ++++++++++++++++++++++++++++++++++++++++
 backend/app/db/repo.py          |  50 ++++
 backend/app/db/session.py       |  40 ++++
 backend/tests/db/test_models.py |  43 ++++
 4 files changed, 622 insertions(+)
```

`backend/app/db/__init__.py` **保持 0 字节未动**（blob 仍为 `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`），与 Task 1 评审建立的「六个空 `__init__.py`」不变量一致。未新增 `conftest.py`、未新增 `tests/__init__.py`、未新增 Alembic / 迁移脚本 / 种子数据。`backend/data/` 与 `tests/architecture/test_domain_purity.py` 未被触碰。

**落盘复核**（前三轮曾把编辑丢在未保存缓冲区，故逐项独立验证）：`git hash-object` 记录四个文件的 blob（`models.py` = `3070000a…`）；`git diff HEAD --stat` 为空证明磁盘 = 提交；`ast.parse` 磁盘文件得到 15 个 `ClassDef`（`JsonText` + 14 个模型）；两个探针脚本 import 的是磁盘代码，行为与源码逐条对应。

---

## 5. 自审

| 检查项 | 结论 |
|---|---|
| 14 张表、且只有这 14 张 | ✅ 探针读 `inspect().get_table_names()` 得 14，逐一比对相符；Plan 02/03 的 10 张表一张未建 |
| spec §4.1–§4.3 / §4.6 的字段全部在场 | ✅ 逐表逐字段对照 spec 表格核过，见 §6.1 的字段清单 |
| 三条承重结构要求 | ✅ 唯一约束 / 两张派生表的 `batch_id` / `hit_rules` 为逗号分隔 `str`，均已实测（§1.2、§3.4） |
| 每个枚举列都有类常量 + `CheckConstraint` | ✅ 7 组 + `sex` 共 9 条约束；约束文本由 `_in_domain` 从类常量生成，两者不可能漂移；8 类脏值实测被库层拒收 |
| `init_db` 真建出 14 张 | ✅ brief 的 `inspect(session.get_bind()).get_table_names()` 断言通过 |
| 既有 32 条测试未被改动、仍通过 | ✅ 单独复跑 32 passed；`git status` 显示无既有文件被修改 |
| 无 extras | ✅ 只有 4 个新文件；无 Alembic、无迁移、无种子数据、无 `conftest.py`、无 `tests/__init__.py` |
| 输出洁净（含 `-W error`） | ✅ 37 passed，零警告 |
| 注释与 docstring 中文 | ✅ 全中文 |

**一处对派单指令的偏离，主动交代**：派单说「不要读整个计划文件或 spec，brief 是自足的」。但 brief 的 Step 3 原文是「**字段清单严格按 spec §4.1–§4.3、§4.6**」——brief 把字段清单**显式外包给了 spec**，它在这件事上并不自足。凭 14 个类名去猜字段，正是派单里警告的「不要在别人要依赖的 schema 上瞎猜」。故我做了**定向读取**而非通读：spec 第 154–263 行（§4.0–§4.7，约 110 行）、计划里 Task 10/11 的测试块与 Task 4/6/7/8 的 Interfaces 块（用 Grep 定位后按行区间读）。目的是让列名与下游消费者对齐，例如 `percentile_snapshot.item`（而非 `indicator`）与 Task 7 的 `PercentileRow.item` 一一对应、`filled_on`/`total_score`/`dimensions`/`raw_answers` 与 Task 4 的 `RawSurveyRecord` 对齐、`kind` 与 Task 5 的 `CleaningEntry.kind` 同域、`score_<ScoredItem.value>` 让管道可用 `getattr(row, f"score_{item.value}")` 取分而不必再维护映射表。未读 spec 其余章节，未读计划的任务叙述。

---

## 6. 我自行决定并需要控制者知晓的判断

### 6.1 可空性原则（贯穿全表，spec 未逐列标注 NOT NULL）

**业务身份键与算法直接消费的字段 NOT NULL；来自外部源系统、可能整列缺失的描述性字段可空；一切体测/体成分读数与得分可空**（缺测是第一类公民，Ruling 21 明令不得填 0）。

据此可空的列有：`student.department`、`course_section.schedule_text`、`fitness_test_batch.source` / `.academic_year`、`fitness_test_result` 的全部 8 项测量 + 7 项得分 + `total_score` + `national_grade`、`body_composition` 的 5 个测量列、`daily_sync_run.started_at` / `.finished_at` / `.error_summary`、`stratification_result.valid_to`（仍生效时无止日）、`cleaning_log.original_value` / `.processed_value`（缺失被剔除时处理后值本就是 `None`）。

`daily_sync_run` 的全部计数列用 `default=0` 而非可空：运行记录常在跑完之前就已入库（要先拿到 `id` 当 `batch_id` 用），此时计数是「还没数」而不是「未知」，0 比 NULL 诚实，下游求和也不必处处防 `None`。这也是 brief 那条唯一约束测试能通过的前提——它只传 `semester_id` / `business_date` / `status` 三个字段。

### 6.2 `insufficient_count`（超出 spec §4.6 字面的一列）

spec §4.6 只写「红黄绿分布计数」。但标签域是**四个**值，Task 10 的 `distribution` 也是四个键。少一列，「本日没分层的人」就会在运维记录里凭空消失——而 `valid_count < 4` 不分层是 spec §11.1 的硬规则，这个人数恰恰是研究要报告的。故补 `insufficient_count`，与其他三个计数列同构（`default=0`）。

### 6.3 `prescription_count` / `alert_count`（保留但不建对应的表）

spec §4.6 把「处方生成数、预警触发数」列在 `daily_sync_run` 的字段里，故按 brief「字段清单严格按 §4.6」保留这两个计数列（`default=0`），但**不**提前建 `prescription` / `alert` 表——它们属计划 02/03，现在建会逼出一次迁移。列上已加中文注释说明由后续计划写入。

### 6.4 `Student.SEXES`（超出派单枚举清单的一组常量 + 约束）

派单点名了 5 个枚举列，但自审清单问的是「**每个**枚举列是否都有类常量 + `CheckConstraint`」。`sex` 是货真价实的闭域（`male` / `female`），且写错的后果是静默的：百分位按「同性别 × 同龄组」分组，一个 typo 会让该学生落进错误分组或直接没有分组，全程不报错——这正是 Ruling 20 惩罚过的那类失效。故给 `student.sex` 与 `percentile_snapshot.sex` 都加了约束，后者复用 `Student.SEXES` 同一常量。

**没有** import `app.domain.indicators.Sex`：Task 3 的 Interfaces 写的是「Consumes: 无」，db 层不为一个二元集合引入跨层依赖。代价是两处需人工同步，已登记为关切 3。

### 6.5 `index=True` 只加在两个 `batch_id` 上

`delete_by_batch` 是本任务的交付物，Task 11 有 500 人 × 112 天 < 60 秒的硬预算且明令「禁止通过削减数据规模达标」。除此之外没有加任何索引（YAGNI）。

### 6.6 自然键唯一约束

`semester.name`（CLI `--semester 2025-2026-1` 与幂等键的查找键）、`teacher.staff_no`（工号）、`student.student_no`（学号）各加 `unique=True`，`enrollment` 加 `(semester_id, student_id, course_section_id)` 三元唯一约束（spec §4.1 用 `×` 表示这层关系）。这些是 `repo.upsert` 能成立的前提：没有唯一约束，upsert 的「查到就改」退化成「查不到就插重复行」，而重复行不会报错。

### 6.7 字段命名（spec 用中文列名，需落到英文列名）

`staff_no`(工号)、`student_no`(学号)、`department`(院系)、`grade`(年级)、`schedule_text`(上课时间)、`academic_year`(学年)、`measured_on`(测量日期)、`smi`(骨骼肌指数)、`device`(设备)、`filled_on`(填写日期)、`total_score`(总分)、`computed_on`(计算日)、`item`(指标)、`sample_size`(样本量)、`annual_change`(各指标年均变化率)、`trend`(趋势标签)、`weaknesses`(短板列表)、`weakness_count`(短板数量 W)、`valid_count`、`body_comp_abnormal`(C)、`body_comp_reasons`(C 的原因)、`hit_rules`、`input_snapshot`(输入快照)、`valid_from`/`valid_to`(生效起止)、`business_date`(业务日期)、`sync_run_id`、`original_value`/`processed_value`(原值/处理后值)、`error_summary`(错误摘要)、`dropped_count`/`corrected_count`(清洗剔除数/修正数)、`extracted_fitness`/`extracted_body_comp`/`extracted_survey`(各源抽取条数)。

`body_comp_reasons` 用复数并落为 JSON 列表：Task 8 的 `BodyCompFlag.reasons` 是 `tuple[str, ...]`（Ruling 7 扩展过），存单条字符串会逼 Task 10 自己拼接，而拼接分隔符又是一处会漂移的口径。

---

## 7. 关切（Concerns）

**关切 1（交付层面）— `models.py` 489 行，超过派单给的「约 400 行」阈值。**
按派单要求**不自行拆分**，如实上报。需说明的是：14 个声明式模型本身约占 300 行，其余是中文 docstring 与注释（派单与 spec Global Constraints 都要求中文注释，且本任务的每个判断都需要在代码里留下理由，否则口径只存在于实现者脑中——这正是 Task 2 关切 1 的条件所禁止的）。若控制者认为应拆，自然的切法是按 spec 分节拆成 `models/organization.py`（§4.1）、`models/term_data.py`（§4.2）、`models/derived.py`（§4.3）、`models/ops.py`（§4.6），但这会让 `from app.db import models as M` 变成需要一个聚合 `__init__`，而 brief 的测试与 Task 10/11 的测试都逐字写 `from app.db import models as M`——聚合层必须保证 14 个类都从 `app.db.models` 可见。**建议不拆**，但决定权在控制者。

**关切 2（前向，交给 Task 10）— 源数据三张表没有 `batch_id`，也没有唯一约束，重放会静默翻倍。**
`derived_metrics` 与 `stratification_result` 靠 `batch_id` + `delete_by_batch` 做幂等，这条链是完整的。但 `fitness_test_result` / `body_composition` / `interest_survey` 三张**源数据表**按 spec §4.2 既没有 `batch_id`，我也没有自行加唯一约束（不在 spec 字段清单内，且计划预检把 T3 的契约核为「一致 ✓」，我不想单方面改动一个已被核对过的契约）。后果：Task 10 重跑同一业务日期时，若对这三张表用「直接 insert」而不是 `repo.upsert`，行会翻倍，而 `test_rerun_same_business_date_is_idempotent` **抓不到**——它只数 `DerivedMetrics` / `StratificationResult` / `CleaningLog` 三张表。翻倍后的体测记录会进入百分位计算，`test_percentile_snapshot_materialized_not_recomputed` 也只断言快照行数不增、不断言样本量不变，同样可能漏过。
**建议 Task 10 派单显式写明**：这三张表必须用 `repo.upsert`，自然键分别为 `("batch_id", "student_id")`、`("student_id", "measured_on")`、`("student_id", "semester_id", "filled_on")`；或由控制者裁定现在补三条唯一约束（改动小，但会超出 spec §4.2 的字面清单）。**若判断错**：不补约束的代价是演示库里出现重复体测记录，且无异常、无日志。

**关切 3（前向，交给 Task 10）— `cleaning_log.student_id` 是外键，而 Task 5 的 `CleaningEntry` 带的是 `student_no: str`。**
spec §4.6 写的是 `student_id`，故落为 `ForeignKey("student.id") NOT NULL`。Task 10 必须先把 `student_no` 解析成 `student_id`。**若某条脏记录的 `student_no` 在学生表里查不到**（重复记录被剔除时尤其可能），插入会因外键失败——Task 10 必须显式决定是跳过该条审计记录还是让整批失败，不能让它变成未处理的 `IntegrityError`。跳过会让审计记录缺条目（spec §4.6 的初衷受损），失败会让一条孤儿记录阻断整日管道。建议派单里给个明确口径。

**关切 4（可维护性）— `Student.SEXES` 与 `app/domain/indicators.py` 的 `Sex` 枚举是两份字面量。**
见 §6.4，为守住 Task 3「Consumes: 无」而没有 import。域只有 `male` / `female` 两个值、且由国标决定，漂移概率极低；但一旦漂移，是 db 层拒收 domain 层的合法值，会在 Task 10 第一次写入时炸出来（不是静默失效），故可接受。**若判断错**：改成 import `Sex` 并 `{s.value for s in Sex}` 生成常量，一行的事。

**关切 5（交付层面）— `repo.py` 没有随本任务入库的测试。**
brief 把测试文件钉死为 5 条（Step 4 期望 `5 passed`），我逐字照抄、未加一条，因此 `upsert` 与 `delete_by_batch` 在**提交内容里没有测试覆盖**。我用临时探针做了 §3.4 列出的那些验证（含复合键、缺键抛错、跨批不误删、空批返回 0），但探针不入库，这些验证无法被回归。这两个函数是 Task 10 全部写入路径的地基。**建议**：要么由控制者裁定在 Task 3 追加 2–3 条测试（则 Step 4 的期望数需从 5 上调），要么在 Task 10 的派单里明确要求它的测试覆盖 upsert 的「改而不增」与 `delete_by_batch` 的「只删本批」。

**关切 6（前向，交给 Task 6）— `student.grade` 与 `student.birth` 需要从 `make_population` 的 `age` 折算。**
brief 的 Interfaces 明确要求 `Student.grade: int` 与 `Student.birth: date`（均 NOT NULL），而计划里 Task 6 的 population 记录只暴露了 `student_id` / `sex` / `age`（`test_population_size_and_sex_ratio` 断言 `18 <= p["age"] <= 22`）。`seed_database` 因此必须做两次折算：`age → birth`（需要一个基准日，建议取学期 `start_date`，否则同一份 seed 在不同基准日下产出不同的 `birth`，会破坏 Task 6 的「同 seed 字节级一致」）与 `age → grade`（须与 Task 2 的 `age_group_of` 的 19/20 分界保持一致，否则「大一、大二」的学生会被记成 grade 3）。这两处都不在 Task 3 的可控范围内，登记以免 Task 6 各自发挥。

---

## 8. 建议登记进账本的条目

- `Task 3: minor (deferred): JsonText 底层是 TEXT，迁到 PostgreSQL 不会自动用原生 jsonb，数据库侧无法做 JSON 路径查询。本项目是 SQLite 原型且无该查询需求，故接受`
- `Task 3: minor (deferred): Student.SEXES 与 domain.indicators.Sex 是两份字面量（为守住 Task 3「Consumes: 无」未 import）；漂移会在 Task 10 首次写入时炸出，非静默`
- **前向约束（必须写进 Task 10 派单）**：源数据三张表无 `batch_id` 无唯一约束，必须用 `repo.upsert`，自然键见关切 2；`cleaning_log.student_id` 是外键而 `CleaningEntry.student_no` 是字符串，孤儿学号的处置口径需明确（关切 3）。
- **前向约束（必须写进 Task 6 派单）**：`age → birth` 的基准日必须固定（建议学期 `start_date`），`age → grade` 的分界必须与 `age_group_of` 的 19/20 一致（关切 6）。

---

## 9. 修复轮：Ruling 24 / 25 / 26（第二轮，接 §1–§8，前八节原样保留）

- **Status:** DONE
- **Commit:** `d4a602b` `fix: 源数据表补业务唯一约束堵住重跑翻倍，cleaning_log 支持孤儿学号，repo 补测试`（base `9c1c6e5`，分支 `feature/plan-01-data-foundation`）
- **测试:** 37 → **48 passed**（新增 11 条，全部在新文件 `backend/tests/db/test_repo.py`）；`pytest -q` 与 `pytest -q -W error` 均 **48 passed**，输出洁净、零警告
- **变更文件:** `backend/app/db/models.py`（+42 −1，489 → 530 行）、新增 `backend/tests/db/test_repo.py`（422 行 / 11 条测试）。`repo.py`、`test_models.py`、`app/domain/`、`app/refdata.py`、`backend/data/`、架构测试、`pyproject.toml`、`.gitignore` **一个字节都没动**；未引入 Alembic / 迁移 / Plan 02·03 的表；未拆 `models.py`

### 9.0 先做「是否已存在」核查（派单警告过本轮之前有重复执行）

Step 0 复核结果：

```
$ git log --oneline -3
9c1c6e5 docs: Ruling 24-26 堵住幂等性漏洞并固化 JsonText 约定
7f12b74 feat: 建立 14 张表的数据模型与 Repository，业务日期唯一约束保障幂等
ec7cf4f docs: Task 2 收口，同步前向约束到计划与 spec

$ git status --short        # 空
$ git branch --show-current
feature/plan-01-data-foundation

$ cd backend; C:\Python\python.exe -m pytest -q
.....................................                                    [100%]
37 passed in 0.31s          # 与派单预期的 37 一致
```

逐条核对 `7f12b74` 的产物后确认，**三条裁定在起点都不存在，本轮没有「已实现故跳过」的项**：

| 裁定 | 起点状态（读磁盘代码得出） | 结论 |
|---|---|---|
| Ruling 24 | `FitnessTestResult` / `BodyComposition` / `InterestSurvey` 三个类**根本没有 `__table_args__`**，既无 `daily_sync_run` 批号也无任何唯一约束 | 不存在，需实现 |
| Ruling 25 | `CleaningLog.student_id` 是 `Mapped[int]` + `ForeignKey("student.id")` 非空，**无 `student_no` 列** | 不存在，需实现 |
| Ruling 26 | `tests/db/` 下只有 `test_models.py`（5 条），**无 `test_repo.py`** | 不存在，需实现 |

派单指出的「brief 已过期」也核对过：`.superpowers/sdd/.../task-3-brief.md` 把测试钉死为 5 条，与计划 Task 3 Interfaces 块里 Ruling 26 的「**两者必须有真实测试覆盖**」冲突。本轮**以计划为准**，新增独立测试文件而不去改 brief 钉死的那 5 条。

### 9.1 Ruling 24 —— 三张源数据表的业务唯一约束

**改了什么**：`backend/app/db/models.py` 里三个类各补一个显式命名的 `UniqueConstraint`，并在紧邻处写清「为什么这条键是幂等的唯一防线」。

| 表 | 约束名 | 键列 |
|---|---|---|
| `fitness_test_result` | `uq_fitness_result_batch_student` | `(batch_id, student_id)` |
| `body_composition` | `uq_body_composition_student_measured_on` | `(student_id, measured_on)` |
| `interest_survey` | `uq_interest_survey_student_semester_filled_on` | `(student_id, semester_id, filled_on)` |

`FitnessTestResult.batch_id` 指向 `fitness_test_batch`（week1/week8/week16 的测试事件）、**与 `daily_sync_run` 无关**这一点，已写进该表约束上方的注释——它正是「本表不能靠 `delete_by_batch` 按批清理、只能靠业务键」的原因，也是三张源表与两张派生表幂等机制的分界所在。

**修复前的失效已实测复现**（临时探针 `pe_probe_double.py`，写在 `$env:TEMP`、已删除、未入库）：把同一批数据连写两次，三张表**全部静默翻倍、无任何异常**——

```
重放第 1 次后行数: {'fitness_test_result': 1, 'body_composition': 1, 'interest_survey': 1}
重放第 2 次后行数: {'fitness_test_result': 2, 'body_composition': 2, 'interest_survey': 2}
```

RED（测试先行；失败原因正是「约束不存在」而非测试写错）：

```
$ cd backend; C:\Python\python.exe -m pytest tests/db/test_repo.py -q
FAILED ...::test_source_table_unique_constraint_rejects_duplicate[body_composition] - Failed: DID NOT RAISE IntegrityError
FAILED ...::test_source_table_unique_constraint_rejects_duplicate[fitness_test_result] - Failed: DID NOT RAISE IntegrityError
FAILED ...::test_source_table_unique_constraint_rejects_duplicate[interest_survey] - Failed: DID NOT RAISE IntegrityError
5 failed, 6 passed in 0.49s
```

`DID NOT RAISE` 就是「重复行被照单全收」的直接证据，与上面的 1 → 2 行互相印证。

**修复后的真实 `IntegrityError` 原文**（临时探针 `pe_probe_evidence.py`，已删除、未入库）：

```
--- fitness_test_result ---
orig: UNIQUE constraint failed: fitness_test_result.batch_id, fitness_test_result.student_id
--- body_composition ---
orig: UNIQUE constraint failed: body_composition.student_id, body_composition.measured_on
--- interest_survey ---
orig: UNIQUE constraint failed: interest_survey.student_id, interest_survey.semester_id, interest_survey.filled_on
```

**一处必须如实上报的事实：SQLite 的 UNIQUE 报错只列「表.列」，不带约束名。** 派单给显式 `name=` 的理由是「让 SQLite/SQLAlchemy 的报错可诊断」——这个理由在 SQLite 上只兑现了一半：诊断信息来自列名，不是约束名。显式命名仍然该留，但理由要换成下面这四条更实在的：

1. DDL 里可指名道姓引用（实测读 `sqlite_master`）：
   ```
   CONSTRAINT uq_fitness_result_batch_student UNIQUE (batch_id, student_id),
   CONSTRAINT uq_body_composition_student_measured_on UNIQUE (student_id, measured_on),
   CONSTRAINT uq_interest_survey_student_semester_filled_on UNIQUE (student_id, semester_id, filled_on),
   ```
2. SQLAlchemy 反射拿得到名字，测试因此能同时断言「名字 + 键列组合」两件事；
3. 将来若真上迁移（本轮明令不引入 Alembic），`op.drop_constraint(name)` 需要稳定名字——SQLite 的匿名约束叫 `sqlite_autoindex_*`，无法可靠引用；
4. PostgreSQL 的报错**会**带约束名，命名在那里直接兑现派单的原意。

**覆盖测试**：`test_source_table_unique_constraint_rejects_duplicate[fitness_test_result|body_composition|interest_survey]`（参数化 3 条，即派单要求 7）。每条都：先插一条合法行 → 再插一条**同业务键但非键读数不同**的行（`height_cm` 172.5 → 999.0、`body_fat_pct` 18.5 → 99.0、`total_score` 3.6 → 1.0）→ 断言 `IntegrityError`，且报错文本逐列包含 `表名.列名`，且 DDL 与反射结果里都查得到那条命名约束、键列组合与列序逐一相符。

改**非键**字段是刻意的：只有「同键但读数不同」也被拒收，才证明拦住翻倍的是业务键，而不是碰巧整行相同。

### 9.2 Ruling 25 —— `CleaningLog` 的学号双列

**改了什么**：

```python
student_no: Mapped[str] = mapped_column(String(32))  # 原始学号，不做 strip / 补零
student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))  # 解析得到才填
```

`student_no` 非空、宽度 `String(32)` 与 `Student.student_no` 一致；`student_id` 由非空外键改为**可空**外键（仍指向 `student.id`）。裁定要求的理由写进了类 docstring：学号解析不出来的记录**本身就是最该留痕的数据质量问题**，做成非空外键会把最该被看见的那一类问题挡在库外，而 spec §4.6「必须能交代每一条被剔除或修正的数据」恰恰在这一类上失守；同时点明 Task 5 的 `CleaningEntry.student_no` 是 `str`，双列让清洗结果不必先解析成功才落库。

**实测证据**（临时探针 `pe_probe_evidence.py`，已删除）——孤儿学号落库、`commit()`、`expire_all()` 后从库里读回：

```
student_id           = None | is None: True
student_no           = '02025001001 '
type(student_no)     = str
逐字节相同            = True | len = 12
original_value       = None | type = NoneType
列可空性             = {'student_no': False, 'student_id': True}
```

用的学号是 `"02025001001 "`（前导零 + 尾随空格，`student` 表里查无此人）：前导零证明没被数字化、尾随空格证明没被 `strip`，`len == 12` 与写入时一致。

RED 侧的失败原因同样指向「列不存在」，不是测试写错：

```
FAILED ...::test_cleaning_log_keeps_orphan_student_no - KeyError: 'student_no'
FAILED ...::test_json_text_keeps_float_and_none - TypeError: 'student_no' is an invalid keyword argument for CleaningLog
```

**覆盖测试**：`test_cleaning_log_keeps_orphan_student_no`（派单要求 8）——先断言列的可空性（`student_no.nullable is False`、`student_id.nullable is True`），再同批写入「孤儿学号 + `student_id=None`」与「正常学号 + `student_id` 已解析」两行，`expire_all()` 后读回、逐字节比对学号、断言 `type(...) is str`、并断言两种情形并存。

**顺带交代（未改生产代码）**：`repo.upsert` 在 `key_fields` 写了模型没有的列时，现状是 `getattr` 抛

```
AttributeError: type object 'Student' has no attribute 'student_noo'
```

同时点名了模型与写错的字段，已经可诊断，故**没有**为它另加一层自定义异常（超出本轮范围，且现状比多一层包装更少代码）。派单要求 4 的测试把这个行为钉住了，另外还断言「炸在查询之前、库里不留半行」。

### 9.3 Ruling 26 —— `repo.py` 的真实测试（外加 `JsonText` 的首个覆盖）

**改了什么**：新增 `backend/tests/db/test_repo.py`（422 行 / 11 条测试）。`app/db/repo.py` **未改一个字节**（blob 仍 `da867f7`）——本轮是补上欠它的覆盖，不是改它。

| # | 测试 | 对应派单要求 |
|---|---|---|
| 1 | `test_upsert_inserts_when_no_row_matches` | 要求 1：无匹配行时插入 |
| 2 | `test_upsert_updates_existing_row_without_duplicating` | 要求 2：有匹配行时更新且不重复（行数仍 1、主键不变、非键字段被改、返回同一实例） |
| 3 | `test_upsert_handles_composite_key` | 要求 3：复合键，用的正是 `FitnessTestResult` 的 `(batch_id, student_id)`；并断言「换 `student_id` 即另一条键、必须新增」，否则 week1 与 week8 会互相覆盖 |
| 4 | `test_upsert_raises_when_key_field_is_not_a_column` | 要求 4：`key_fields` 写了不存在的列 → `AttributeError`，报错须点名模型与字段，且不留半行 |
| 5 | `test_delete_by_batch_deletes_only_the_matching_batch` | 要求 5：只删本批；另一 `batch_id` 的行完好（断言返回 1、存活行的 `batch_id` 恰为另一批） |
| 6 | `test_delete_by_batch_on_absent_batch_returns_zero` | 要求 6：不存在的批次返回 0、不误删；整表为空也返回 0 不抛 |
| 7–9 | `test_source_table_unique_constraint_rejects_duplicate[三表]` | 要求 7：Ruling 24 的三条约束各一条参数化测试 |
| 10 | `test_cleaning_log_keeps_orphan_student_no` | 要求 8：Ruling 25 的孤儿学号 |
| 11 | `test_json_text_keeps_float_and_none` | 附加要求：`JsonText` 的首个覆盖 |

如实说明：6 条 `repo` 测试在写下的当下就是绿的（`upsert` / `delete_by_batch` 已存在），它们**不可能先红**——按 TDD 的说法这属于「给既有代码补测试」，价值在于把 §3.4 那些被删掉的探针变成可回归的断言。三条约束测试与两条 `CleaningLog` 测试则**先红后绿**，红的原因逐条列在 9.1 / 9.2。

**`JsonText` 的前后对照**（临时探针 `pe_probe_t3fix.py` 里的抛弃型内存模型，已删除、未入库：两个类各一列，一列用 SQLAlchemy 自带 `JSON`、一列用 `JsonText`，写同样四个值 → `commit()` → 读回）：

```
DDL            [('INTEGER', 'id'), ('JSON', 'v')]     # 自带 JSON 渲染成 JSON 列类型 → NUMERIC 亲和性
BUILTIN_JSON   [(0, 'int'), (65.5, 'float'), (3, 'int'), (None, 'NoneType')]
JSONTEXT       [(0.0, 'float'), (65.5, 'float'), (3, 'int'), (None, 'NoneType')]
```

即传进去的 `0.0`：自带 `JSON` 读回 **`int 0`**（`type()` = `int`，浮点被 SQLite 的 NUMERIC 亲和性降成整型），`JsonText` 读回 **`float 0.0`**（`type()` = `float`）。`None` 两者读回都是 `NoneType`，但 `JsonText` 落的是 SQL `NULL` 而不是 `'null'` 文本。§2.1 当初的结论至此有了可回归的断言。

**覆盖测试**：`test_json_text_keeps_float_and_none` 断言 `type(row.original_value) is float`、值为 `0.0`、`processed_value is None`，并反射断言 `cleaning_log.original_value` / `processed_value` 的列类型是 `TEXT`（不是 `JSON`）——把「底层必须是 TEXT」这条决策本身也钉住了。

### 9.4 既有 5 条模型测试：**未改一字，也未削弱任何断言**

`backend/tests/db/test_models.py` 的 blob 在提交前后均为 `8fa0594`，`git diff` 为空，5 条原样通过。原因是这三处改动碰不到它们的断言面：

- `test_all_fourteen_tables_created` 用的是 `>=`（表名集合的**超集**断言），新增表级约束不改变表名集合，表数仍为 14；
- `test_daily_sync_run_business_date_is_unique` 只涉及 `daily_sync_run`，该表本轮未动；
- 三条域常量测试只断言类常量集合，与约束、列可空性无关。

**没有任何断言为了让测试通过而被放宽。**

### 9.5 命令与输出（原文）

RED（测试写完、模型未改时）：

```
$ cd backend; C:\Python\python.exe -m pytest tests/db/test_repo.py -q
FAILED tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[body_composition] - Failed: DID NOT RAISE IntegrityError
FAILED tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[fitness_test_result] - Failed: DID NOT RAISE IntegrityError
FAILED tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[interest_survey] - Failed: DID NOT RAISE IntegrityError
FAILED tests/db/test_repo.py::test_cleaning_log_keeps_orphan_student_no - KeyError: 'student_no'
FAILED tests/db/test_repo.py::test_json_text_keeps_float_and_none - TypeError: 'student_no' is an invalid keyword argument for CleaningLog
5 failed, 6 passed in 0.49s
```

坦白一处过程失误：**第一次** RED 跑出来的 3 条约束测试是 `TypeError: got multiple values for keyword argument 'height_cm'`——那是我测试里行构造器的写法错误（基值与覆盖值撞键），属于「测试自身写错」的**无效红**。改成命名构造器 + 字典合并后重跑，才得到上面这份「失败原因正是功能缺失」的有效红。

GREEN（改完模型后）：

```
$ cd backend; C:\Python\python.exe -m pytest tests/db -v
collected 16 items

tests/db/test_models.py::test_all_fourteen_tables_created PASSED         [  6%]
tests/db/test_models.py::test_daily_sync_run_business_date_is_unique PASSED [ 12%]
tests/db/test_models.py::test_stratification_label_domain PASSED         [ 18%]
tests/db/test_models.py::test_grouping_mode_domain PASSED                [ 25%]
tests/db/test_models.py::test_timepoint_domain PASSED                    [ 31%]
tests/db/test_repo.py::test_upsert_inserts_when_no_row_matches PASSED    [ 37%]
tests/db/test_repo.py::test_upsert_updates_existing_row_without_duplicating PASSED [ 43%]
tests/db/test_repo.py::test_upsert_handles_composite_key PASSED          [ 50%]
tests/db/test_repo.py::test_upsert_raises_when_key_field_is_not_a_column PASSED [ 56%]
tests/db/test_repo.py::test_delete_by_batch_deletes_only_the_matching_batch PASSED [ 62%]
tests/db/test_repo.py::test_delete_by_batch_on_absent_batch_returns_zero PASSED [ 68%]
tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[body_composition] PASSED [ 75%]
tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[fitness_test_result] PASSED [ 81%]
tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[interest_survey] PASSED [ 87%]
tests/db/test_repo.py::test_cleaning_log_keeps_orphan_student_no PASSED  [ 93%]
tests/db/test_repo.py::test_json_text_keeps_float_and_none PASSED        [100%]

============================= 16 passed in 0.34s ==============================

$ cd backend; C:\Python\python.exe -m pytest -q
................................................                         [100%]
48 passed in 0.40s

$ cd backend; C:\Python\python.exe -m pytest -q -W error
................................................                         [100%]
48 passed in 0.39s
```

提交（中文信息按派单要求走 BOM-less UTF-8 临时文件 + `git commit -F`，实测 `BOM=False`）：

```
$ git add backend/app/db/models.py backend/tests/db/test_repo.py
$ git commit -F "$env:TEMP\pe_commit_msg.txt"
[feature/plan-01-data-foundation d4a602b] fix: 源数据表补业务唯一约束堵住重跑翻倍，cleaning_log 支持孤儿学号，repo 补测试
 2 files changed, 464 insertions(+), 1 deletion(-)
 create mode 100644 backend/tests/db/test_repo.py

$ git status --short        # 提交后为空，工作树干净
```

### 9.6 落盘复核（前三轮丢过编辑，故逐项独立验证）

| 文件 | 提交后 blob（`git hash-object`） | 独立复核 |
|---|---|---|
| `backend/app/db/models.py` | `591c575`（起点 `3070000`） | 重读磁盘：530 行、无 BOM、纯 LF、最长行 87 列、`ast.parse` 得 15 个 `ClassDef`（`JsonText` + 14 个模型） |
| `backend/tests/db/test_repo.py` | `b81a141`（新增） | 重读磁盘：422 行、无 BOM、纯 LF、最长行 92 列 |
| `backend/tests/db/test_models.py` | `8fa0594`（**与起点同一 blob**） | 未改 |
| `backend/app/db/repo.py` | `da867f7`（**与起点同一 blob**） | 未改 |

约束名、键列与可空性是**从磁盘上的代码 import 后反射出来的**（探针 `pe_probe_verify.py`），不是照着我写下的文本念的：

```
FitnessTestResult -> [('uq_fitness_result_batch_student', ['batch_id', 'student_id'])]
BodyComposition -> [('uq_body_composition_student_measured_on', ['student_id', 'measured_on'])]
InterestSurvey -> [('uq_interest_survey_student_semester_filled_on', ['student_id', 'semester_id', 'filled_on'])]
CleaningLog -> [('student_no', 'VARCHAR(32)', 'nullable=False'), ('student_id', 'INTEGER', 'nullable=True')]
CleaningLog.student_id FK -> ['student.id']
```

四个临时探针（`pe_probe_t3fix.py` / `pe_probe_double.py` / `pe_probe_evidence.py` / `pe_probe_verify.py`）与提交信息临时文件都写在 `$env:TEMP`，用完 `Remove-Item` 并复核 `Get-ChildItem "$env:TEMP\pe_probe_*.py"` 计数为 0；工作树无残留。

### 9.7 本轮的关切

**关切 A（交付层面）— `models.py` 从 489 行长到 530 行。** 控制者已裁定 489 行可接受且**明令不拆**，本轮遵守未拆；但新增的 41 行里有 12 行是解释「为什么这条键是幂等唯一防线」的中文注释，故如实上报行数变化，是否精简注释由控制者判断。最长行 87 列，未超过文件原有风格。

**关切 B（前向，交给 Task 10）— 约束只保证「不会静默翻倍」，不保证「Task 10 写得对」。** 三张源表现在会**抛 `IntegrityError`** 而不是默默翻倍：Task 10 若对源表走裸 `insert`，重放会从「静默错」变成「显式炸」。这是进步（错误可见），但 Task 10 的派单仍必须写明这三张表走 `repo.upsert`，自然键与本轮落地的三条约束逐字对应：`("batch_id", "student_id")` / `("student_id", "measured_on")` / `("student_id", "semester_id", "filled_on")`。计划里 Task 10 Step 1 的 `_counts` 已扩到六表（含 `FitnessTestResult` / `BodyComposition` / `InterestSurvey`），`test_rerun_same_business_date_is_idempotent` 现在既有计数断言、也有库层约束兜底——原 §7 关切 2 担心的「假保证」两头都堵上了。

**关切 C（前向，交给 Task 5/10）— `CleaningLog.student_no` 不做任何规范化。** 逐字节照抄是有意的（审计要能对上原始 CSV），代价是同一个人的脏数据可能因空格 / 前导零差异而分裂成 `student_id IS NULL` 与 `student_id = <id>` 两类，按 `student_id` 聚合审计记录时会漏掉前者。归一化（`strip` / 去前导零）应由 Task 5 的清洗层负责并在 `reason` 里交代，db 层不代劳。**若判断错**：将来要按学号做全量审计对账时，得同时按 `student_no` 归一后再 group。

**关切 D（前向，交给 Task 6/10）— 构造 `CleaningLog` 现在必须传 `student_no`。** 该列非空，漏传会直接 `IntegrityError`（不是静默 NULL）。原 §7 关切 6 的 `age → birth` / `age → grade` 折算要求不变。

### 9.8 建议追加登记进账本的条目

- `Task 3 (fix round): minor (deferred): SQLite 的 UNIQUE 报错只列「表.列」、不带约束名；显式命名的收益在 DDL / 反射 / 将来迁移 / PostgreSQL 上，不在 SQLite 的报错文本里`
- `Task 3 (fix round): minor (deferred): cleaning_log.student_no 逐字节照抄不归一化；同学号可能因空格或前导零差异分裂成 student_id 为 NULL 与已解析两类，归一化归 Task 5`
- **前向约束（Task 10 派单必须写明）**：三张源表走 `repo.upsert`，自然键见关切 B；构造 `CleaningLog` 必须传 `student_no`（关切 D）。
- 原 §7 的**关切 2 / 3 / 5 已由本轮关闭**（分别对应 Ruling 24 / 25 / 26）；关切 1（行数）延续为本轮关切 A；关切 4（`Student.SEXES` 与 `domain.indicators.Sex` 两份字面量）与关切 6（`age → birth` / `age → grade`）**仍开放**。

---

## 10. 修复轮 2：Ruling 27 / 28 / 29 / 30 + Minor 2 / 3 / 4 / 5 / 7（第三轮，接 §1–§9，前九节原样保留）

- **Status:** DONE_WITH_CONCERNS
- **Commit:** `8e21464` `fix: 开启 SQLite 外键强制并补齐约束回归保护，percentile_snapshot 加幂等键`（base `9f65b0b`，分支 `feature/plan-01-data-foundation`）
- **测试:** 48 → **66 passed**（新增 18 条：`test_models.py` 5 条、`test_repo.py` 13 条）；`pytest -q` 与 `pytest -q -W error` 均 **66 passed**，输出洁净、零警告
- **变更文件:** 5 个，`+582 −28`。`app/domain/`、`app/refdata.py`、`backend/data/`、架构测试、`pyproject.toml`、`.gitignore` **一个字节都没动**；未建 Plan 02/03 的表；未引入 Alembic；未拆 `models.py`（530 → 556 行，仍是 14 个声明式模型 + `JsonText`，`ast` 数出 15 个 `ClassDef`）
- **10 项全部落地，无「已存在故跳过」的项**

### 10.0 Step 0 定向复核（派单警告过此前有重复执行）

```
$ git log --oneline -3
9f65b0b docs: Ruling 27-30 补上 SQLite 外键强制与 percentile_snapshot 幂等防线
d4a602b fix: 源数据表补业务唯一约束堵住重跑翻倍，cleaning_log 支持孤儿学号，repo 补测试
9c1c6e5 docs: Ruling 24-26 堵住幂等性漏洞并固化 JsonText 约定

$ git status --short            # 空
$ git branch --show-current     # feature/plan-01-data-foundation

$ cd backend; C:\Python\python.exe -m pytest -q
................................................                         [100%]
48 passed in 0.40s              # 与派单预期一致
```

逐条核对起点磁盘代码，**10 项在起点全都不存在**：

| 项 | 起点状态（读磁盘得出） |
|---|---|
| 1 | `session.py` 只 import `create_engine` / `Engine` / `DeclarativeBase` / `Session`，**没有 `event`**、没有任何 connect 钩子 |
| 2 | `test_models.py:22` 是 `>= expected` |
| 3 | `PercentileSnapshot` 的列里**没有 `batch_id`**，`__table_args__` 只有两条 `_in_domain` |
| 4 | `status: Mapped[str] = mapped_column(String(8))`，**无 default** |
| 5 | 无任何测试 import `app.domain.indicators` |
| 6 | 无任何测试触发 `ck_*`；`test_repo.py` 只覆盖三条 `uq_*` |
| 7 | `delete_by_batch` 函数体只有 `execute` + `return rowcount` 两行，**无 flush** |
| 8 | `upsert` docstring 未提 PATCH 语义，也未提 id 需 flush |
| 9 | 无测试对 `CleaningLog` 调 `delete_by_batch` |
| 10 | 无测试遍历 `Base.metadata` 查列类型 |

已按计划为准读取 `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 第 372–399 行的 Task 3 Interfaces 块（Ruling 24/25/26/27/28/29/30 逐字在内）。**brief 与计划冲突处一律按计划**：本轮据此改动了 brief 钉死的 `test_models.py`（见 §10.2）。

### 10.1 Item 1（Ruling 27）—— SQLite 外键强制

**改了什么**：`backend/app/db/session.py` 加 `from sqlalchemy import create_engine, event`，并在模块顶层、**`Engine` 类**上注册 connect 钩子：

```python
@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys_on(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

按派单要求挂在**类**上而不是 `engine()` 的返回值上：两个测试文件都是自己 `create_engine(...)` 再交给 `init_db`，挂在工厂返回值上一条测试路径也覆盖不到。也没有为「将来可能接非 SQLite 后端」缩小注册目标（派单明令：真要防，分支加在监听器内部）——这条 deferred 注记写进了 docstring，并按新报告要求登记为**关切 A**。

**前后对照实测**（同一支探针脚本，中间只改了 `session.py`；探针写在 `$env:TEMP`、已删、未入库）：

```
加钩子之前：
schema 里的 ForeignKey 总数 = 19
PRAGMA foreign_keys = 0
孤儿 batch_id=999999 插入：未被拒收，derived_metrics 行数 = 1

加钩子之后：
schema 里的 ForeignKey 总数 = 19
PRAGMA foreign_keys = 1
孤儿 batch_id 插入被拒: IntegrityError | FOREIGN KEY constraint failed
```

**PRAGMA 0 → 1，孤儿 `batch_id` 从「照单全收 1 行」变成 `IntegrityError`。** 「之前」那一半是**临时摘掉 `@event.listens_for` 那一行**跑出来的，摘掉的那次没有提交（§10.11 用 `git hash-object` 前后比对证明还原是字节级的）。`exc.orig` 原文就是 `FOREIGN KEY constraint failed`——SQLite 的外键报错不像 CHECK 那样带约束名，也不像 UNIQUE 那样带列名，这一点如实记录。

（`ForeignKey` 总数在加钩子时是 19，Ruling 29 给 `percentile_snapshot` 补 `batch_id` 后变成 **20**；`session.py` 与 `test_models.py` 的文案已按 20 写。）

**全量回归：没有任何既有测试被外键强制打破，因此没有重排过任何插入顺序。**

加钩子之后、写任何新测试之前，先单独跑了一次全套：

```
$ cd backend; C:\Python\python.exe -m pytest -q
................................................                         [100%]
48 passed in 0.41s          # 48 → 48，一条未红
```

**需要重排插入顺序的既有测试：0 条。** 原因是这两个测试文件从一开始就照真实父子关系建行——`test_repo.py` 的种子先 `semester`/`teacher` 再 `section`/`students`/`fitness_batch`/`sync_run`，`test_models.py` 的唯一约束测试先 `Semester` 再 `DailySyncRun`；加上 SQLAlchemy 的 unit-of-work 本身按表依赖排序 INSERT。派单预警的「先写子行后写父行」在这个代码库里并不存在。

**覆盖测试**（`tests/db/test_models.py`，2 条）：

- `test_sqlite_foreign_keys_are_enforced`：`session.execute(text("PRAGMA foreign_keys")).scalar() == 1`。会话由夹具按测试一贯方式产生（`create_engine` + `init_db` + `Session(eng)`），故这条断言验的正是挂在**类**上的钩子。
- `test_orphan_batch_id_is_rejected`：`DerivedMetrics(batch_id=999_999)`（`daily_sync_run` 里查无此行）→ `IntegrityError`，且文本含 `FOREIGN KEY constraint failed`。

附带一条（Ruling 29 新加的列也得真受外键管，否则它只是一个长得像外键的整数列）：`test_repo.py::test_percentile_snapshot_orphan_batch_id_is_rejected`。

### 10.2 Item 2（Ruling 28）—— 表数量测试改 `==`

`test_models.py` 的 `>= expected` 改为 `== expected`，并把原本写在函数体里的 `from sqlalchemy import inspect` 提到模块顶部（新测试也要用它）。**这是该文件相对 brief 逐字文本的第一处改动**，由控制者裁定覆盖：「第一批只建 14 张表」是真实的范围边界，`>=` 抓不到有人提前把 Plan 02/03 的表建进来，而提前建表会逼出一次本该不存在的迁移。理由写成了代码注释。

**有牙实测**：临时在 `models.py` 的 `class CleaningLog` 之前插入一张计划 03 的 `alert` 表 →
```
Item2  建出第 15 张表（计划 03 的 alert）
    -> 变红 ✓ | 1 failed, 9 deselected in 0.36s | 已还原=True
```
`>=` 对这个变异完全无感（15 ⊇ 14），`==` 当场抓住。

### 10.3 Item 3（Ruling 29）—— `percentile_snapshot` 的幂等防线

**改了什么**（`models.py` 的 `PercentileSnapshot`）：

```python
batch_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"), index=True)
...
UniqueConstraint("semester_id", "computed_on", "item", "sex", "age_group",
                 name="uq_percentile_snapshot_group_day"),
```

与 `derived_metrics` 同一模式：非空外键 + `index=True`（`delete_by_batch` 现在也够得着这张表，Task 11 有 500 人 × 112 天 < 60 秒的硬预算且明令不得靠削减数据规模达标）。类 docstring 补了「纪律会被下一次重构悄悄改掉，约束不会」。

**反射复核**（从磁盘代码 import 后反射出来的，不是照着写下的文本念）：

```
percentile_snapshot unique = [('uq_percentile_snapshot_group_day',
    ['semester_id', 'computed_on', 'item', 'sex', 'age_group'])]
percentile_snapshot fk     = [(['semester_id'], 'semester'), (['batch_id'], 'daily_sync_run')]
percentile_snapshot index  = ['ix_percentile_snapshot_batch_id']
batch_id nullable/index    = False True
```

**报错原文**（同组同日重放翻倍）：
```
同组同日第二行: IntegrityError | UNIQUE constraint failed: percentile_snapshot.semester_id,
  percentile_snapshot.computed_on, percentile_snapshot.item, percentile_snapshot.sex,
  percentile_snapshot.age_group
孤儿 batch_id  : IntegrityError | FOREIGN KEY constraint failed
```

**唯一键不含 `source` 是否够用——核对过 Task 7 的语义才下的结论，不是猜的**：计划里 `compute_snapshot` 的分组键是 `(sex, age_group, item)`，对**每个分组只产出一行**；样本 < `MIN_SAMPLE`(30) 时是**整组降级**为 `source="national"`（`test_snapshot_falls_back_to_national_when_sample_below_30` 断言 `len(snap) == 1`），不是 school 与 national 并存两行。故五列键恰好定位一行，`source` 不必进键。这一条写进了类 docstring。

**覆盖测试**：`test_percentile_snapshot_group_day_is_unique`，沿用 `test_repo.py` 既有的取证模式——先读 `sqlite_master` 断言约束名出现在 DDL、再反射断言键列与列序逐一相符，另加 `batch_id` 的外键指向、`index=True` 与索引名；然后插一行合法行，再插一行**同键但非键读数不同**（`p25` 7.1→9.9、`p50` 7.6→10.5、`sample_size` 42→84、`source` school→national）→ `IntegrityError`，且报错逐列点名。改非键读数是刻意的：只有「同键但数值不同」也被拒，才证明拦住翻倍的是业务键而不是碰巧整行相同。

**有牙实测**：临时摘掉那条 `UniqueConstraint` → `变红 ✓ | 1 failed, 23 deselected`。

### 10.4 Item 4（Ruling 30）—— `DailySyncRun.status` 的默认值

**改了什么**：`status: Mapped[str] = mapped_column(String(8), default="failed")`，并在紧邻处写清为什么取 `failed`：崩溃被记成失败只是难看，被记成成功则是**谎报一次并没有发生的完整运行**，而下游看 status 决定要不要重跑，谎报成功会让这一天永远不再重跑。

**实测**：`Ruling 30 默认 status = 'failed'`；反射 `status default = failed`、`status nullable = False`。

**覆盖测试**：`test_daily_sync_run_status_defaults_to_failed` —— 断言列非空且 `default.arg == "failed"`；再落一行**只给 `semester_id` / `business_date`、不传 status** 的运行记录（正是「跑完之前就入库拿 id 当 batch_id」那个场景），`expire_all()` 后 `session.get(...)` 读回 `"failed"`；并追加一行显式 `status="success"` 读回 `"success"`，确认默认值不会盖掉真实结局。

**有牙实测**：临时摘掉 `default="failed"` → `变红 ✓ | 1 failed, 9 deselected`。

### 10.5 Item 5 —— `Student.SEXES` ↔ `domain.indicators.Sex`

**覆盖测试**：`test_models.py::test_student_sexes_match_domain_sex_enum` —— `assert {s.value for s in Sex} == M.Student.SEXES`，`Sex` 在模块顶部从 `app.domain.indicators` import。顺带钉住 `percentile_snapshot.sex` 复用同一常量后的 DDL 文本恰为 `sex IN ('female', 'male')`。

架构测试（`tests/architecture`）仍全绿——按派单的说法，纯度约束管的是 `app/domain/` 自己的导入，不管谁 import 它；且 import 发生在 `tests/db/`，`app/db/models.py` **仍然没有**引入跨层依赖，Task 3 的「Consumes: 无」在生产代码里守住了。

**有牙实测**：临时把 `SEXES` 改成 `{"male","female","other"}` → `变红 ✓ | 1 failed, 9 deselected`。

**原 §7 关切 4 由此关闭**：当时写的「若判断错：改成 import `Sex`，一行的事」——本轮选了更松耦合的那条路（测试钉住，而不是让 `app/db` 依赖 `app/domain`），漂移现在会在 CI 里立刻变红，不再是「Task 10 首次写入时才炸」。

### 10.6 Item 6（Minor 2）—— 九条 `ck_*` 的参数化覆盖

**只加测试，`models.py` 的九条约束一个字节未动。**

`test_repo.py::test_check_constraint_rejects_dirty_value`，参数化 **9 条**（派单要求「至少 8 条」，我把第九条 `ck_percentile_snapshot_sex` 一并覆盖，这样「九条约束零覆盖」这句话才真的被关掉）。反射出的约束清单与之逐一对上：

```
ck_* 约束 9 条 = ['ck_cleaning_log_kind', 'ck_course_section_grouping_mode',
 'ck_daily_sync_run_status', 'ck_fitness_test_batch_timepoint',
 'ck_percentile_snapshot_sex', 'ck_percentile_snapshot_source',
 'ck_stratification_result_label', 'ck_stratification_result_percentile_source',
 'ck_student_sex']
```

每条测试做四件事：

1. 先断言**脏值确实不在类常量里**（`assert dirty not in spec["allowed"]`）——否则这条测试自己没有牙；
2. 读 `sqlite_master` 断言**约束名出现在 DDL 里**（派单要求：将来有人删掉一条约束要能 loudly 失败）；再反射 `get_check_constraints` 断言约束名可查、`sqltext` 以 `"<column> IN ("` 开头（约束落在正确的列上）、且类常量里**每一个值**都出现在约束文本里（取值域由类常量生成，逐值核对，防止两边漂移）；
3. **先插一行合法值并 flush**——否则「脏值被拒」证明不了什么，也可能只是整张表都插不进去；
4. 再插脏行 → `IntegrityError`，断言文本含 `CHECK constraint failed` **且含约束名**（必须是取值域拦的，不是别的约束顺手拦的）。

**一处与 §9.1 结论相反的新事实，值得单独说**：第一轮记录过「SQLite 的 UNIQUE 报错只列表.列、不带约束名」。**CHECK 不是这样**——SQLite 的 CHECK 报错**带约束名**，所以显式命名在 SQLite 上对 CHECK 是直接兑现的，不必等 PostgreSQL。九条报错原文（探针 `exc.orig`）：

```
student.sex:                             IntegrityError | CHECK constraint failed: ck_student_sex
course_section.grouping_mode:            IntegrityError | CHECK constraint failed: ck_course_section_grouping_mode
fitness_test_batch.timepoint:            IntegrityError | CHECK constraint failed: ck_fitness_test_batch_timepoint
daily_sync_run.status:                   IntegrityError | CHECK constraint failed: ck_daily_sync_run_status
cleaning_log.kind:                       IntegrityError | CHECK constraint failed: ck_cleaning_log_kind
percentile_snapshot.source:              IntegrityError | CHECK constraint failed: ck_percentile_snapshot_source
percentile_snapshot.sex:                 IntegrityError | CHECK constraint failed: ck_percentile_snapshot_sex
stratification_result.label:             IntegrityError | CHECK constraint failed: ck_stratification_result_label
stratification_result.percentile_source: IntegrityError | CHECK constraint failed: ck_stratification_result_percentile_source
```

对应的脏值分别是 `unknown` / `mixed` / `week3` / `ok` / `whatever` / `city` / `unknown` / `crimson` / `city`——九条全部被数据库自己拒收，逐条点名。

**三项的脏值额外改动了一个自然键列**，这不是省事而是必须：`percentile_snapshot.source` / `daily_sync_run.status` / `student.sex` 所在的三张表带唯一约束，若脏行与刚插入的合法行同键，SQLite 会**先报 UNIQUE**，测到的就不是取值域了。测试文件里对此写了注释说明。

**有牙实测**：临时把 `CleaningLog.__table_args__` 改成 `()` →
```
Item6  摘掉 ck_cleaning_log_kind
    -> 变红 ✓ | 1 failed, 8 passed, 15 deselected in 0.45s | 已还原=True
```
注意是 **1 failed / 8 passed**：只有 `cleaning_log.kind` 那一条红，其余八条照绿——证明参数化的粒度是逐约束的，不是一条大测试糊在一起。这也正是派单点出的失效模式（「删掉任一 `_in_domain(...)`，全套 48 条照样全绿」）现在被逐条堵上。

### 10.7 Item 7（Minor 3）—— `delete_by_batch` 先 flush

**改了什么**：函数体第一行加 `session.flush()`，docstring 说明理由。**行为改动只有这一行。**

**一处必须如实上报的实测结果：这个 bug 只在 `autoflush=False` 的会话上复现。** 派单描述的机制（「新行躲过删除、随后被 autoflush 插进去」）在**默认会话**下不成立——`Session.execute` 自己就会先 autoflush，所以缺这行也照样删得掉。实测四象限（同一支探针，同一批数据：库里 1 条已提交的旧行 + 1 条 `upsert` 出来待落库的新行）：

```
A 默认会话·无显式flush:      rowcount=2  提交后残留=0   ← SQLAlchemy 替我们 flush 了
B 默认会话·有显式flush:      rowcount=2  提交后残留=0
C 关闭autoflush·无显式flush: rowcount=1  提交后残留=1   ← bug 在这里复现
D 关闭autoflush·有显式flush: rowcount=2  提交后残留=0
E repo.delete_by_batch(autoflush=False) -> 返回2 提交后残留=0
```

**行数前后对照：删除前库里 1 行（旧行）→ 删除并提交后 0 行**；不加 flush 则是 `rowcount=1`、**残留 1 行**（C）。

所以这行 flush 的价值不是「修一个默认配置下就会犯的错」，而是**让 `delete_by_batch` 的契约不依赖调用方的 autoflush 设置**：靠 `Session.execute` 的隐式 autoflush 是依赖 SQLAlchemy 的实现细节，`Session(eng, autoflush=False)`（批量管道里为性能常见）一来就失效，而失效方式是「静默少删 + 静默多留」，正是最难查的那一类。这一条如实登记为**关切 B**，也写进了夹具的 docstring。

**覆盖测试**：`test_delete_by_batch_flushes_pending_rows_first`，跑在新加的 `quiet_session` / `quiet_seeded` 夹具上（`Session(eng, autoflush=False)`）。**必须关掉 autoflush 这条测试才有牙**——用默认夹具的话，删掉那行 flush 测试照样绿，等于没测。测试先提交一条旧行，再用 `repo.upsert` 造一条**待落库**的新行，并先断言此刻库里只有 1 行（证明新行确实还没落库，测试的前提成立），然后 `delete_by_batch` + `commit`，断言返回 2、残留 0。

**有牙实测**：临时摘掉 `session.flush()` → `变红 ✓ | 1 failed, 23 deselected`。

为复用种子数据，`seeded` 夹具的函数体抽成了模块级 `_seed(session)`，并给返回字典**新增** `teacher_id`（Item 6 的 `_course_section` 构造器要它）。**既有 11 条测试的断言面一字未改**，`seeded` 仍返回原来的全部键；`_seed` 的 docstring 顺手更正了一句现在已过期的话（原文「SQLite 默认不开外键强制」——Ruling 27 之后已开，故改成「父行必须先落库再插子行，顺序颠倒会直接 FOREIGN KEY constraint failed」）。

### 10.8 Item 8（Minor 4 / 5）—— `upsert` 的两条契约写进 docstring

**只改 docstring，`upsert` 的行为一个字节没动**（函数体仍是 `select` → `scalar` → 有则 `setattr` 非键字段、无则 `model(**values)` + `session.add`）。补的两段：

1. **更新分支是 PATCH 语义，不是 PUT**：只有出现在 `values` 里的键会被写回，没给的列一律保持库中原值。后果写明——重放同一业务日期时，若本轮抽取少了上一轮填过的某一列（源系统整列缺失、或某个分支没走到），旧值会**静默存活**，读起来像是「这一轮也算出了这个值」。故 **Task 10 每次调用都必须传该表的完整列集合**，让「本轮没算出来」表现为显式写入 `None`，而不是表现为「沿用上一轮」。也写明了本函数刻意不做「补全缺失键」的猜测：猜不出调用方到底是漏传还是有意不改。
2. **插入分支返回的实例，`id` 在 flush 之前是 `None`**：Task 10 要拿它当 `batch_id`，而 `derived_metrics.batch_id` / `stratification_result.batch_id` 都是 NOT NULL，故忘了 flush 会在写派生行时炸出来、不会静默落 NULL——但契约仍写在这里，免得靠炸来发现。

顺带把 `delete_by_batch` 的 docstring 从「两张表」更正为「三张表」（Ruling 29 之后 `percentile_snapshot` 也带 `batch_id`），否则文档与 schema 不一致。

这两条都登记为**关切 D / E**（前向约束，Task 10 派单需写明）。

### 10.9 Item 9（Minor 7）—— 无 `batch_id` 列的模型必须炸

**覆盖测试**：`test_delete_by_batch_on_model_without_batch_id_raises`，用 `CleaningLog`（它的列叫 `sync_run_id`）：

```
delete_by_batch(CleaningLog): AttributeError | type object 'CleaningLog' has no attribute 'batch_id'
```

断言报错同时点名**模型**（`CleaningLog`）与**缺失的列**（`batch_id`），且库里不留任何副作用（`_count(...) == 0`）。

**顺带在 docstring 里补了一条同源但更危险的坑**（登记为**关切 C**）：`fitness_test_result` **也有** `batch_id`，但它指向 `fitness_test_batch`（week1/week8/week16 的测试事件），**不是** `daily_sync_run`。拿一个 `sync_run_id` 去调 `delete_by_batch(session, M.FitnessTestResult, ...)`，两边都是合法整数、外键也管不着（**Ruling 27 的钩子在这里帮不上忙**），只会按数值巧合删掉不相干的学生成绩且**不报错**。`AttributeError` 挡住的是「列名记错」，挡不住「列名对了语义错了」。可安全传入的只有 `DerivedMetrics` / `StratificationResult` / `PercentileSnapshot` 三张表——这句话已写进 docstring。

### 10.10 Item 10 —— `JsonText` 约定的结构守卫

**覆盖测试**：`test_models.py::test_no_column_uses_builtin_sqlalchemy_json`，遍历 `Base.metadata` 里 14 张表的每一列，断言没有任何一列的类型是 `sqlalchemy.JSON`。助手 `_is_builtin_json` 同时检查 `TypeDecorator.impl`，所以「包一层 `TypeDecorator` 但底层仍是 `JSON`」也逃不掉。

守卫自己也得有牙，故另加两条自检：`len(Base.metadata.tables) == 14`（覆盖面确实是这 14 张），以及**恰好 8 列是 `JsonText`** 且 `cleaning_log.original_value` 在其中（证明遍历不是空跑，八个 JSON 形态的列真的被走到了）。行为侧仍由 §9.3 的 `test_json_text_keeps_float_and_none` 覆盖，两者互补：一条看行为、一条看结构。

**有牙实测**：临时把 `cleaning_log.original_value` 从 `JsonText` 换回自带 `JSON` → `变红 ✓ | 1 failed, 9 deselected`。

### 10.11 命令、输出与落盘复核

**有牙验证的做法**：一支临时驱动脚本（`$env:TEMP\pe_probe_teeth.py`，已删）逐条「读原文 → 断言锚点匹配 → 写变异 → 跑目标测试 → `finally` 还原 → 断言还原后与原文逐字节相同」。锚点不匹配就直接 assert 失败，避免「变异没生效却报告说测试有牙」。**8 条变异全部变红，8 次还原全部 `已还原=True`**：

```
Item1  摘掉 Engine 类上的 connect 钩子          -> 变红 ✓ | 2 failed, 8 deselected
Item2  建出第 15 张表（计划 03 的 alert）        -> 变红 ✓ | 1 failed, 9 deselected
Item3  摘掉 uq_percentile_snapshot_group_day    -> 变红 ✓ | 1 failed, 23 deselected
Item4  摘掉 status 的 default="failed"          -> 变红 ✓ | 1 failed, 9 deselected
Item5  让 Student.SEXES 与 domain 的 Sex 漂移    -> 变红 ✓ | 1 failed, 9 deselected
Item6  摘掉 ck_cleaning_log_kind                -> 变红 ✓ | 1 failed, 8 passed, 15 deselected
Item7  摘掉 delete_by_batch 开头的 flush         -> 变红 ✓ | 1 failed, 23 deselected
Item10 把 cleaning_log.original_value 换回 JSON  -> 变红 ✓ | 1 failed, 9 deselected
=== 全部还原后跑全量 === exit=0 | 66 passed in 0.55s
```

变异前后 `git hash-object` 逐一比对，三个生产文件 blob 完全一致（`bea7e79` / `1f2392f` / `3bdb841`），证明还原是字节级的、没有把任何变异带进提交。（Item9 未做变异：它的断言面就是 `AttributeError` 本身，把 `model.batch_id` 改成 `getattr(..., None)` 才会让它变绿，那已经是换实现而非拆防线。）

**最终命令与输出（原文）**：

```
$ cd backend; C:\Python\python.exe -m pytest -q
..................................................................       [100%]
66 passed in 0.54s

$ cd backend; C:\Python\python.exe -m pytest -q -W error
..................................................................       [100%]
66 passed in 0.55s

$ cd backend; C:\Python\python.exe -m pytest tests/db -v
============================= 34 passed in 0.47s ==============================
   # test_models.py 10 条（原 5 + 新 5）、test_repo.py 24 条（原 11 + 新 13）

$ cd backend; C:\Python\python.exe -m pytest -q      # 提交后从已提交状态复跑
66 passed in 0.53s
```

**落盘复核**（前四轮丢过编辑，故逐项独立验证——不信任编辑工具的返回值）：

```
app/db/session.py            bytes=  3363 BOM=False CRLF=False lines=  66 maxlen= 81 ClassDef=1
app/db/models.py             bytes= 27815 BOM=False CRLF=False lines= 556 maxlen= 87 ClassDef=15
app/db/repo.py               bytes=  4654 BOM=False CRLF=False lines=  80 maxlen= 86 ClassDef=0
tests/db/test_models.py      bytes=  8628 BOM=False CRLF=False lines= 174 maxlen= 88 ClassDef=0
tests/db/test_repo.py        bytes= 30883 BOM=False CRLF=False lines= 763 maxlen= 97 ClassDef=0
```

五个文件全部无 BOM、纯 LF、`ast.parse` 通过；`models.py` 数出 15 个 `ClassDef`（`JsonText` + 14 个模型，与 §9.6 一致，未多未少）。上面的字节数、行数与全部反射结果都是**从磁盘文件重新读出 / 重新 import 后测出来的**，不是照着写下的文本念的。三处「19 → 20 个外键」的文案改动与 `delete_by_batch` 的坑位补注，都在编辑后用 Grep 回读磁盘确认过。

提交（中文信息走 BOM-less UTF-8 临时文件 + `git commit -F`，实测 `BOM=False bytes=2181`，用后 `Remove-Item`）：

```
$ git add backend/app/db/session.py backend/app/db/models.py backend/app/db/repo.py `
          backend/tests/db/test_models.py backend/tests/db/test_repo.py
$ git commit -F "$env:TEMP\pe_commit_msg2.txt"
[feature/plan-01-data-foundation 8e21464] fix: 开启 SQLite 外键强制并补齐约束回归保护，percentile_snapshot 加幂等键
 5 files changed, 582 insertions(+), 28 deletions(-)

$ git status --short          # 提交后为空，工作树干净
$ git log -1 --format=%s      # 中文标题回读正常，未乱码
```

提交后 blob：`session.py` = `c709c54`、`models.py` = `1f2392f`、`repo.py` = `873844c`、`test_models.py` = `eaace7b`、`test_repo.py` = `3224a72`。四支临时探针（`pe_probe_fk_before.py` / `pe_probe_flush.py` / `pe_probe_checks.py` / `pe_probe_ruling29.py` / `pe_probe_teeth.py` / `pe_probe_verify2.py` / `pe_probe_final.py`）与提交信息临时文件都写在 `$env:TEMP`，用完 `Remove-Item` 并复核计数为 0；工作树无残留。本报告文件在 `.superpowers/` 下，**不被 git 跟踪**（`git ls-files --error-unmatch` 报 pathspec 不匹配），故不在提交里。

### 10.12 变更文件

```
8e21464 fix: 开启 SQLite 外键强制并补齐约束回归保护，percentile_snapshot 加幂等键
 backend/app/db/models.py        |  28 ++-
 backend/app/db/repo.py          |  36 +++-
 backend/app/db/session.py       |  30 +++-
 backend/tests/db/test_models.py | 139 ++++++++++++++-
 backend/tests/db/test_repo.py   | 377 ++++++++++++++++++++++++++++++++++++++--
 5 files changed, 582 insertions(+), 28 deletions(-)
```

生产代码的净增量很小：`session.py` +30（钩子 + 说明其必要性的 docstring）、`models.py` +28（`batch_id` 列、唯一约束、`default="failed"` 与三段理由注释）、`repo.py` +36（**1 行行为改动**即 `session.flush()`，其余 35 行全是 docstring：两条 upsert 契约、flush 的理由、`AttributeError`、`fitness_test_result.batch_id` 的坑、两张表→三张表的更正）。其余 516 行全是测试。

`backend/app/db/__init__.py` 仍为 0 字节未动；未新增 `conftest.py` / `tests/__init__.py` / Alembic / 迁移脚本 / 种子数据；`backend/data/`（已核验的国标 CSV）一个值未改。

### 10.13 关切（Concerns）

按派单的新报告要求，**凡是写进代码注释 / docstring / 测试夹具说明里的 caveat，一律在此登记**，不让它只活在代码里。

**关切 A（deferred，写在 `session.py` 的钩子 docstring 里）— 外键钩子注册在 `Engine` 类上，对本进程内每一个引擎无条件生效。**
本项目只用 SQLite，故接受；但将来若真接非 SQLite 后端（如 PostgreSQL），`PRAGMA foreign_keys=ON` 会在每次 connect 时抛错。**处置口径已写死在 docstring 里**：分支要加在监听器**内部**（按 DBAPI 连接类型判断），**不能靠缩小注册目标**来解决——缩小到 `engine()` 的返回值就会把 `create_engine` + `init_db` 的测试路径全部漏掉，正是 Ruling 27 要防的失效。**若判断错**：接非 SQLite 后端那天会在第一次 connect 就炸，不是静默失效，故可接受。

**关切 B（如实更正派单对失效机制的描述）— Item 7 的 flush 只在 `autoflush=False` 的会话上承重。**
派单说的机制是「新行躲过删除、随后被 autoflush 插进去」；实测在**默认会话**下 `Session.execute` 自己就会先 autoflush，缺这行也删得掉（§10.7 象限 A）。真正会漏删的是 `Session(eng, autoflush=False)`（象限 C：`rowcount=1`、残留 1 行）。这行 flush 的价值因此是**让 `delete_by_batch` 的契约不依赖调用方的 autoflush 设置**——靠隐式 autoflush 是依赖 SQLAlchemy 的实现细节。测试特意跑在 `autoflush=False` 夹具上，否则删掉 flush 它照样绿（没有牙）。**若判断错**：如果控制者认为「默认会话下本来就没事」即等于不需要这行，那 §10.7 的测试与这行代码可以一并撤掉；但那样 `delete_by_batch` 的正确性就交给了调用方的会话配置。

**关切 C（前向，交给 Task 10；写在 `delete_by_batch` 的 docstring 里）— `FitnessTestResult` 也有 `batch_id`，但语义不同，误传会静默删错行。**
`fitness_test_result.batch_id` 指向 `fitness_test_batch`（week1/week8/week16 的测试事件），不是 `daily_sync_run`。拿 `sync_run_id` 去调 `delete_by_batch(session, M.FitnessTestResult, ...)`：两边都是合法整数、外键管不着（**Ruling 27 的钩子在这里帮不上忙**）、列名对得上所以 `AttributeError` 也不抛，只会按数值巧合删掉不相干的学生成绩且**不报错**。可安全传入的只有 `DerivedMetrics` / `StratificationResult` / `PercentileSnapshot`。**建议 Task 10 派单显式写明这三张表的名字**；也可以裁定把 `delete_by_batch` 改成只接受这三张表（白名单）或改名为 `delete_by_sync_run`，但那超出本轮范围，未自行做。

**关切 D（前向，交给 Task 10；写在 `upsert` 的 docstring 里）— 更新分支是 PATCH 语义，本轮抽取缺失的列会静默沿用上一轮的旧值。**
Task 10 **每次调用都必须传该表的完整列集合**，让「本轮没算出来」表现为显式写入 `None`。否则重放后读到的是上一轮的旧值，且看起来像本轮算出来的——这类失真不会报错。

**关切 E（前向，交给 Task 10；写在 `upsert` 的 docstring 里）— 插入分支返回的实例 `id` 在 flush 之前是 `None`。**
Task 10 要拿这个 `id` 当 `batch_id`。忘了 flush 会在写派生行时因 NOT NULL 炸出来（不会静默落 NULL），但契约已写明，免得靠炸来发现。

**关切 F（前向，交给 Task 10；Ruling 29 的直接后果）— `percentile_snapshot.batch_id` 是 NOT NULL 外键，物化快照前必须先有 `daily_sync_run` 行。**
Task 10 若先算快照再建运行记录（或想复用「上一次运行的快照」而不带批号），插入会直接 `IntegrityError`。同时它现在也是 `delete_by_batch` 的合法目标，重放清理清单要从两张表扩到三张——计划里 Task 10 的 `_counts` 与幂等测试是否已含 `PercentileSnapshot`，请在派单时核对（本轮未改计划文件，超出范围）。

**关切 G（交付层面，延续 §9.7 关切 A）— `models.py` 从 530 行长到 556 行。**
控制者已裁定 530 行可接受且明令不拆，本轮遵守未拆。新增 26 行里只有 4 行是结构（`batch_id` 列 + 唯一约束），其余是解释 Ruling 29 / 30 理由的中文注释与 docstring。最长行 87 列，未超文件原有风格。`test_repo.py` 从 422 行长到 763 行（+341，其中 9 条参数化用例的数据表约占 100 行）——它现在是本任务最大的文件，若控制者认为该按主题拆（`test_constraints.py` / `test_repo.py`），本轮未自行拆。

**仍开放的前轮关切**：§7 关切 6 与 §9.7 关切 C / D（`age → birth` / `age → grade` 的折算口径、`cleaning_log.student_no` 不归一化、构造 `CleaningLog` 必须传 `student_no`）本轮未触及，原样开放。**已关闭**：§7 关切 4（由 Item 5 的测试关闭，见 §10.5）。

### 10.14 建议追加登记进账本的条目

- `Task 3 (fix round 2): minor (deferred): 外键钩子注册在 Engine 类上，对进程内每个引擎无条件生效；接非 SQLite 后端时分支必须加在监听器内部，不得缩小注册目标（关切 A）`
- `Task 3 (fix round 2): minor: delete_by_batch 的 flush 只在 autoflush=False 的会话上承重；默认会话下 Session.execute 自带 autoflush（关切 B）`
- `Task 3 (fix round 2): minor (deferred): SQLite 的 CHECK 报错带约束名（与 UNIQUE 不同，后者只列表.列）；显式命名的诊断收益在 SQLite 上对 CHECK 即已兑现`
- **前向约束（必须写进 Task 10 派单）**：① `delete_by_batch` 只可对 `DerivedMetrics` / `StratificationResult` / `PercentileSnapshot` 使用，`FitnessTestResult.batch_id` 语义不同（关切 C）；② `upsert` 是 PATCH 语义，必须传完整列集合（关切 D）；③ `upsert` 插入分支的 `id` 需 flush 后才有值（关切 E）；④ 物化 `percentile_snapshot` 前必须先有 `daily_sync_run` 行，且重放清理清单扩为三张表（关切 F）。

---

## 11. 修复轮 3：Ruling 31 —— `FitnessTestResult.batch_id` 改名 `test_batch_id`（第四轮，接 §1–§10，前十节原样保留）

- **Status:** DONE_WITH_CONCERNS
- **Commit:** `8db0887` `refactor: FitnessTestResult.batch_id 改名 test_batch_id，把静默删源数据变成响亮报错`（base `b81b4ac`，分支 `feature/plan-01-data-foundation`）
- **测试:** 66 → **69 passed**（新增 3 条，既有 66 条**一条未删、断言面未削弱**）；`pytest -q` 与 `pytest -q -W error` 均 **69 passed**，输出洁净、零警告
- **变更文件:** 4 个，`+143 −24`。`app/db/models.py`（+28 −8 行文本，556 → 568 行）、`app/db/repo.py`（**只改 docstring，行为一个字节未动**，80 → 90 行）、`tests/db/test_models.py`（174 → 234 行）、`tests/db/test_repo.py`（763 → 800 行）。`app/domain/`、`app/refdata.py`、`backend/data/`、架构测试、`pyproject.toml`、`.gitignore`、`Document/` **一个字节都没动**；未拆 `models.py` / `test_repo.py`；未引入 Alembic / 迁移（库为空，由 `init_db` 重建）

### 11.0 Step 0 定向复核

```
$ git log --oneline -3
b81b4ac docs: Ruling 31 用命名区分可批删表，堵住静默删除源体测数据的陷阱
8e21464 fix: 开启 SQLite 外键强制并补齐约束回归保护，percentile_snapshot 加幂等键
9f65b0b docs: Ruling 27-30 补上 SQLite 外键强制与 percentile_snapshot 幂等防线

$ git status --short            # 空
$ git branch --show-current     # feature/plan-01-data-foundation

$ cd backend; C:\Python\python.exe -m pytest -q
..................................................................       [100%]
66 passed in 0.55s              # 与派单预期一致
```

**改名尚未发生**（`models.py:235` 仍是 `batch_id: Mapped[int] = mapped_column(ForeignKey("fitness_test_batch.id"))`），故本轮不是「已实现故跳过」。起点 blob：`models.py` = `1f2392f`、`repo.py` = `873844c`、`test_repo.py` = `3224a72`、`test_models.py` = `eaace7b`（与 §10.11 逐一相符）。

已按计划为准读取 `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 第 400 行（Ruling 31 的逐字文本）与 `Document/2026-09-28-体育闭环原型-设计spec.md` §4.2 第 183/187/189 行（命名规则已由 `b81b4ac` 写入）。**brief 已过期**这一点与派单一致：`.superpowers/sdd/.../task-3-brief.md` 仍写 `batch_id`，本轮一律按计划。

### 11.1 `backend/` 全树的 `batch_id` 清点（改前先分类，改后逐条复核）

Grep 全树共 **53 行**命中（含注释与文档字符串）。按归属分类后，**只有 5 处属于 `FitnessTestResult`，全部改名**；其余 48 处一律未动：

| 归属 | 命中处（起点行号） | 处置 |
|---|---|---|
| **`FitnessTestResult`（本轮改名）** | `models.py:235`（列 + FK）、`models.py:261`（约束上方注释）、`models.py:269`（`UniqueConstraint` 的列名）、`test_repo.py:203/205`（复合键 upsert）、`test_repo.py:333`（`_fitness_result` 构造器）、`test_repo.py:369`（`_SOURCE_TABLES` 键列） | **改为 `test_batch_id`** |
| `DerivedMetrics` | `models.py:385/395`、`test_models.py:63/64/74`、`test_repo.py:124/129/140/142/267/300` | **未动**（`batch_id` = FK to `daily_sync_run`，正是裁定要保留的语义） |
| `StratificationResult` | `models.py:429`、`test_repo.py:618` | **未动** |
| `PercentileSnapshot` | `models.py:336/337/354`、`test_repo.py:514/536/553/559/560/561/583/584/585` | **未动** |
| `DailySyncRun` / `delete_by_batch` 的形参 | `models.py:461/465/498`、`repo.py:55/56/60/69/72/79`、`session.py:25/30` | **未动**（`repo.py:79` 的 `model.batch_id` 是本函数的工作机制本身） |
| `test_repo.py` 的种子字典键 `fitness_batch_id` | `109/205/333/341/347/370` | **未动**——它是测试内部的字典键、不是列名；见**关切 E** |
| `BodyComposition` 的注释「本表没有 batch_id」 | `models.py:288` | **未动**（改名后仍成立：本表两个名字都没有） |

### 11.2 改名前的失效已实测复现（临时探针，`$env:TEMP`，已删）

派单描述的机制不是纸面推演。探针造出裁定点名的那个数值巧合（3 个体测批次 id = 1/2/3，3 次同步运行 id = 1/2/3，每批一条真实源体测成绩），然后拿 `runs[0].id`（= `sync_run_id` 1）去调 `delete_by_batch(session, M.FitnessTestResult, 1)`：

```
体测批次 id      = [1, 2, 3]
同步运行 id      = [1, 2, 3]
调用前源体测行数 = 3
FitnessTestResult 有 batch_id 属性 = True
>>> 没有任何异常；delete_by_batch 返回 = 1
>>> 调用后源体测行数 = 2 （静默删除源数据）
>>> 存活行的批号 = [2, 3]
```

**3 → 2 行、返回 1、无异常**：一行真实源体测成绩被静默删掉，且外键（Ruling 27 的钩子已开）与 `AttributeError` 都没有拦它——每个值各自合法，属性也存在。这正是裁定说的「删源数据比删派生行严重」：派生行重算就回来了，源体测数据删了就是删了。

### 11.3 RED（测试先行，5 条失败的原因全是「改名还没做」）

```
$ cd backend; C:\Python\python.exe -m pytest -q
FAILED tests/db/test_models.py::test_fitness_test_result_has_no_batch_id_attribute - AssertionError: assert not True
 +  where True = hasattr(<class 'app.db.models.FitnessTestResult'>, 'batch_id')
FAILED tests/db/test_models.py::test_only_derived_tables_expose_batch_id - AssertionError: batch_id 专指 daily_sync_run 的外键，实到 ['derived_metrics', 'fitness_test_result', 'percentile_snapshot', 'stratification_result']
  Extra items in the left set:
  'fitness_test_result'
FAILED tests/db/test_repo.py::test_upsert_handles_composite_key - AttributeError: type object 'FitnessTestResult' has no attribute 'test_batch_id'
FAILED tests/db/test_repo.py::test_delete_by_batch_rejects_fitness_test_result - TypeError: 'test_batch_id' is an invalid keyword argument for FitnessTestResult
FAILED tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[fitness_test_result] - AssertionError: 约束必须显式命名，DDL 里要能指名道姓地引用
assert 'uq_fitness_result_test_batch_student' in 'CREATE TABLE fitness_test_result (\n\tid INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, ...
5 failed, 64 passed in 0.78s
```

第 2 条的失败文本顺带给出了**改名前**的派生表集合：`['derived_metrics', 'fitness_test_result', 'percentile_snapshot', 'stratification_result']`——多出来的那一项就是本裁定要摘掉的。这也证明了新测试**有牙**：不需要另做变异，RED 就是变异（把名字改回去）的结果。

### 11.4 GREEN —— 改了什么

**`models.py`（`FitnessTestResult`）**：

```python
    # 体测批次（week1/week8/week16 的测试事件），不是 daily_sync_run，故不叫 batch_id
    test_batch_id: Mapped[int] = mapped_column(ForeignKey("fitness_test_batch.id"))
    ...
    __table_args__ = (
        UniqueConstraint(
            "test_batch_id", "student_id", name="uq_fitness_result_test_batch_student"
        ),
    )
```

外键目标字符串**未变**（仍是 `fitness_test_batch.id`）——改名只换名字、不换语义。约束名**选择改名**为 `uq_fitness_result_test_batch_student`（裁定允许二选一）：DDL 里留一个 `..._batch_student` 的约束名，等于在刚刚清掉「batch 一词歧义」的那张表里又把歧义写回去，而约束名是将来迁移脚本与 PostgreSQL 报错唯一能指名道姓引用的东西（§9.1 已记录 SQLite 的 UNIQUE 报错只列「表.列」）。

**起点这一列没有 `comment=`**（全库只有 `stratification_result.hit_rules` 用了 `comment=`），且 SQLite 不渲染 `COMMENT`，故派单里「the column `comment=`」这一项在起点是空的：命名规则写进了**类 docstring 的新段落**与**紧邻列的中文行注释**，未新增 `comment=`。见**关切 D**。

起点这一列也**没有** `index=True`，故「any index」一项同样无可改；未新增索引（`delete_by_batch` 的性能预算针对派生表，本表不是它的合法目标；且 `UniqueConstraint` 在 SQLite 下本就建出 `sqlite_autoindex_*`，按 `(test_batch_id, student_id)` 前缀查找已被覆盖）。见**关切 F**。

**`repo.py`（只改 docstring，`delete_by_batch` 的函数体 `session.flush()` + `execute(...)` 两行一个字节未动）**：按派单要求补上命名规则的定义，并把 round 2 那段现在已经**过期**的告诫（原文「**但列名对了不等于语义对了**：`fitness_test_result` 也有 `batch_id`……只会按数值巧合删掉不相干的学生成绩且不报错」）替换成本裁定的结论。留着那段话会让文档描述一个已不存在的 schema。新增的首段：

> ``batch_id`` 在本项目里**专指「指向 ``daily_sync_run`` 的外键」**，也就是本函数可据以删除的归属键；全库只有三张派生表（``DerivedMetrics`` / ``StratificationResult`` / ``PercentileSnapshot``）才有这一列（Ruling 31，由 ``test_only_derived_tables_expose_batch_id`` 钉住）。指向别的父表的键一律用可区分的名字：``fitness_test_result.test_batch_id`` 指体测批次、``cleaning_log.sync_run_id`` 指同步运行。

末段改为「对 `FitnessTestResult` 而言这个报错是**刻意设计**的（Ruling 31）」，并把 §11.2 的实测数字（3 → 2 行、返回 1、无异常）写了进去。

### 11.5 新增 / 更新的测试（3 新 + 3 更新，无一条被削弱）

| 测试 | 文件 | 内容 |
|---|---|---|
| **新** `test_fitness_test_result_has_no_batch_id_attribute` | `test_models.py` | `not hasattr(M.FitnessTestResult, "batch_id")` + `hasattr(..., "test_batch_id")`；另断言该列外键仍指向 `fitness_test_batch.id`（防「顺手把 FK 改指 `daily_sync_run`」这种更糟的修法） |
| **新** `test_only_derived_tables_expose_batch_id` | `test_models.py` | 遍历 `Base.metadata`，有 `batch_id` 列的表**恰好**等于三张派生表；先断言 `len(tables) == 14` 让守卫不空跑，再逐表断言这三列的 FK 目标是 `daily_sync_run.id` |
| **新** `test_delete_by_batch_rejects_fitness_test_result` | `test_repo.py` | `repo.delete_by_batch(session, M.FitnessTestResult, seeded["sync_run_id"])` 必须抛 `AttributeError`，报错须点名模型与列，且**源体测行数仍为 1**；开头先断言 `seeded["fitness_batch_id"] == seeded["sync_run_id"]`（数值巧合是本测试的前提，种子里两者都是 1） |
| 更新 `test_upsert_handles_composite_key` | `test_repo.py` | 复合键 `["test_batch_id", "student_id"]`；断言面（1 行不翻倍、主键不变、换 `student_id` 必须新增）原样保留 |
| 更新 `test_source_table_unique_constraint_rejects_duplicate[fitness_test_result]` | `test_repo.py` | 约束名与键列按新名更新；**仍断言 `IntegrityError`**、仍断言 DDL 里查得到约束名、仍断言报错逐列点名、仍是「同键但非键读数不同」（`height_cm` 172.5 → 999.0） |
| 更新 `test_delete_by_batch_on_model_without_batch_id_raises` | `test_repo.py` | 只改 docstring 的一句事实描述：原文「三张带 `batch_id` 的表里就它不叫 `batch_id`」在改名后不准确，改为「四张指向 `daily_sync_run` 的表里，就它的列不叫 `batch_id`」（`cleaning_log` / 三张派生表都指向 `daily_sync_run`）。断言一个未改 |

**一处自决判断，主动交代**：派单对 test 4 的要求是「断言有 `batch_id` 列的表恰好是那三张」。我**额外**加了「这三列的 FK 必须真指向 `daily_sync_run`」——理由是只钉列名的话，「名字对了语义错了」（一张新表叫 `batch_id` 却指向别的父表）仍会溜过去，而那正是 Ruling 31 要防的失效类型。这超出了裁定的字面文本，若控制者认为该只留集合断言，删掉那 4 行即可。

### 11.6 验证（不靠断言，全部实测）

**test 3 的 `AttributeError` 原文**（探针从磁盘代码 import 后跑出的，不是照文本念的）：

```
体测批次 id = [1, 2, 3] | 同步运行 id = [1, 2, 3]
调用前源体测行数 = 3
抛出 AttributeError，原文 = "type object 'FitnessTestResult' has no attribute 'batch_id'"
调用后源体测行数 = 3 （应与调用前相同）
```

同一支探针、同一个场景，§11.2 是 `3 → 2 行、返回 1、无异常`，本轮是 `3 → 3 行 + AttributeError`。报错文本同时点名了模型（`FitnessTestResult`）与缺失的列（`batch_id`），与既有 `CleaningLog` 那条测试的口径一致。

**test 4 实际观察到的派生表集合**：

```
observed = ['derived_metrics', 'percentile_snapshot', 'stratification_result']
FitnessTestResult 有 batch_id 属性 = False
FitnessTestResult 有 test_batch_id = True
```

**DDL 取证**（`SELECT sql FROM sqlite_master WHERE name = 'fitness_test_result'`，节选头尾）：

```sql
CREATE TABLE fitness_test_result (
        id INTEGER NOT NULL,
        test_batch_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        ...
        PRIMARY KEY (id),
        CONSTRAINT uq_fitness_result_test_batch_student UNIQUE (test_batch_id, student_id),
        FOREIGN KEY(test_batch_id) REFERENCES fitness_test_batch (id),
        FOREIGN KEY(student_id) REFERENCES student (id)
)
```

列与唯一约束**都**用 `test_batch_id`；反射同样确认：`[{'name': 'uq_fitness_result_test_batch_student', 'column_names': ['test_batch_id', 'student_id']}]`、`fk = constrained_columns ['test_batch_id'] → fitness_test_batch.id`。

**测试计数**：

```
$ cd backend; C:\Python\python.exe -m pytest -q
.....................................................................    [100%]
69 passed in 0.52s

$ cd backend; C:\Python\python.exe -m pytest -q -W error
.....................................................................    [100%]
69 passed in 0.50s

$ cd backend; C:\Python\python.exe -m pytest <三条新测试 + fitness 那条约束测试> -v
tests/db/test_models.py::test_fitness_test_result_has_no_batch_id_attribute PASSED [ 25%]
tests/db/test_models.py::test_only_derived_tables_expose_batch_id PASSED [ 50%]
tests/db/test_repo.py::test_delete_by_batch_rejects_fitness_test_result PASSED [ 75%]
tests/db/test_repo.py::test_source_table_unique_constraint_rejects_duplicate[fitness_test_result] PASSED [100%]
============================== 4 passed in 0.23s ==============================

$ cd backend; C:\Python\python.exe -m pytest -q      # 提交后从已提交状态复跑
69 passed in 0.51s
```

**66 → 69，只增不减；`-W error` 洁净。**

### 11.7 落盘复核（前四轮丢过编辑，故逐项从 shell 独立验证，不信任编辑工具的返回值）

```
app/db/models.py           bytes= 28982 BOM=False CRLF=False lines= 568 maxlen= 87 ClassDef=15 top-level-def=1
app/db/repo.py             bytes=  5444 BOM=False CRLF=False lines=  90 maxlen= 86 ClassDef=0  top-level-def=2
tests/db/test_models.py    bytes= 11952 BOM=False CRLF=False lines= 234 maxlen= 90 ClassDef=0  top-level-def=14
tests/db/test_repo.py      bytes= 32923 BOM=False CRLF=False lines= 800 maxlen= 97 ClassDef=0  top-level-def=33
```

四个文件全部无 BOM、纯 LF、`ast.parse` 通过；`models.py` 仍是 15 个 `ClassDef`（`JsonText` + 14 个模型，未多未少）。§11.1 的清点表、§11.6 的反射结果与 DDL 都是**改完后重新从磁盘读出 / 重新 import 后测出来的**。

提交后 blob：`models.py` = `dd517a0`、`repo.py` = `855c167`、`test_models.py` = `bb15859`、`test_repo.py` = `9d6f2be`；`git status --short` 与 `git diff HEAD --stat` 均为空（磁盘 = 提交）。提交信息走 BOM-less UTF-8 临时文件 + `git commit -F`（实测 `BOM=False bytes=1872`），用后 `Remove-Item`。三支临时探针（`pe_probe_r31.py` / `pe_probe_r31_verify.py` / `pe_probe_disk.py`）都写在 `$env:TEMP`、未入库。本报告文件在 `.superpowers/` 下，不被 git 跟踪，故不在提交里。

### 11.8 关切（Concerns）

按报告要求，**凡是写进代码注释 / docstring / 测试说明里的 caveat，一律在此登记**。

**关切 A（前向，交给 Task 10；写在 `repo.py` 与 `models.py` 的 docstring 里）— `batch_id` 现在是全库受约束的词汇，Task 10 写 `FitnessTestResult` 必须用 `test_batch_id`。**
自然键随之变为 `("test_batch_id", "student_id")`（原 §9.7 关切 B 与 §10.13 关切 C 里写的 `("batch_id", "student_id")` 已过期）。Task 10 若沿用旧列名，会在第一次写入时抛 `TypeError: 'batch_id' is an invalid keyword argument for FitnessTestResult`（响亮，不是静默），但派单文本最好先改过来。

**关切 B（文档不一致，超出本轮范围故未改）— 计划文件第 389 行仍与 Ruling 31 冲突。**
`Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 第 389 行（Ruling 24 的 bullet）逐字写着 `FitnessTestResult`：`UniqueConstraint("batch_id", "student_id")`，而同一个 Interfaces 块的第 400 行（Ruling 31）要求该列叫 `test_batch_id`；spec §4.2 第 183 行已更新为新名。派单指明「计划为准」，而计划内部此处自相矛盾——我按**后写的 Ruling 31**（也是 spec 与派单的一致口径）执行。文档不在本轮可改范围内，故如实上报，建议控制者把第 389 行同步为 `UniqueConstraint("test_batch_id", "student_id")`，否则后续实现者读到的是旧列名。

**关切 C（已关闭）— 原 §10.13 关切 C 由本轮关闭。**
round 2 登记的「`FitnessTestResult` 也有 `batch_id`、语义不同、误传会静默删错行」这一条前向风险，已由改名从**机制**上消除（不再是「靠 Task 10 派单写明纪律」）。`repo.py` docstring 里那段同源的告诫也已随之删除并替换——留着它会描述一个不存在的 schema。原建议的「白名单 / 改名 `delete_by_sync_run`」本轮**未做**（超出范围），如控制者仍想要白名单，需另开一轮。

**关切 D（如实上报一处派单与起点的落差）— 该列起点没有 `comment=`，本轮也未新增。**
派单要求改名覆盖「the column `comment=`」，但 `FitnessTestResult` 的那一列在起点没有 `comment=`（全库只有 `hit_rules` 用了它），且 SQLite 不把 `COMMENT` 渲染进 DDL，加了也不会在 §11.6 的建表文本里出现。命名规则因此写在**类 docstring 的新段落**与**列旁的中文行注释**里。若控制者的原意是「必须有一列级 `comment=`」，请裁定，一行的事（但需同时接受它在 SQLite 上不可见）。

**关切 E（测试词汇，未改）— `test_repo.py` 种子字典的键仍叫 `fitness_batch_id`。**
它是 `_seed()` 返回的字典键、不是 ORM 列名，Ruling 31 管的是列；改它会波及 6 处引用而与安全性无关，故按最小改动保留。**若判断错**：若控制者认为「测试里也不许出现 `*batch_id` 指体测批次」，改成 `fitness_test_batch_id` 即可，纯机械替换。

**关切 F（自决，未加索引）— `test_batch_id` 没有 `index=True`（起点也没有）。**
派单的「any index」一项在起点无可改对象。未新增的理由：`delete_by_batch` 的性能预算（Task 11，500 人 × 112 天）只针对三张派生表，本表不是它的合法目标；且 `UniqueConstraint` 在 SQLite 下自带 `sqlite_autoindex_*`，按 `(test_batch_id, student_id)` 前缀的查找已被覆盖。**若判断错**：将来若有「按体测批次批量读成绩」的热路径（Task 10 的 Extract 阶段很可能就是这样读的），单独给 `test_batch_id` 加索引是一行的事。

**关切 G（交付层面，延续 §9.7 关切 A / §10.13 关切 G）— 行数继续增长。**
`models.py` 556 → 568（+12，其中 11 行是解释 Ruling 31 的中文 docstring，1 行是列旁注释；结构改动只有列名与约束名两行）、`test_repo.py` 763 → 800（+37，其中 33 行是新测试与 docstring）、`test_models.py` 174 → 234（+60，两条新测试及其 docstring）。控制者已裁定两个文件都**不拆**，本轮遵守。最长行：`models.py` 87（未变）、`repo.py` 86（未变）、`test_models.py` 90、`test_repo.py` 97（未变）。

**仍开放的前轮关切**：§7 关切 6（`age → birth` / `age → grade` 折算）、§9.7 关切 C / D（`cleaning_log.student_no` 不归一化、构造 `CleaningLog` 必须传 `student_no`）、§10.13 关切 A / B / D / E / F（Engine 类上的钩子、flush 只在 `autoflush=False` 下承重、`upsert` 的 PATCH 语义与 `id` 需 flush、`percentile_snapshot.batch_id` NOT NULL）本轮均未触及，原样开放。§10.13 关切 C 关闭（见本轮关切 C）。

### 11.9 建议追加登记进账本的条目

- `Task 3 (fix round 3): Ruling 31 已落地——fitness_test_result 的外键叫 test_batch_id，唯一约束叫 uq_fitness_result_test_batch_student；batch_id 一词在全库专指 daily_sync_run 的外键，只有三张派生表有（由 test_only_derived_tables_expose_batch_id 机器化钉住）`
- `Task 3 (fix round 3): minor (deferred): test_batch_id 无 index=True（唯一约束在 SQLite 下自带 autoindex）；若 Extract 阶段出现按体测批次批量读的热路径再补（关切 F）`
- **文档待修（不在本轮范围）**：计划第 389 行的 Ruling 24 bullet 仍写 `UniqueConstraint("batch_id", "student_id")`，与第 400 行的 Ruling 31 及 spec §4.2 冲突，建议同步（关切 B）。
- **前向约束（必须写进 Task 10 派单）**：`FitnessTestResult` 的自然键是 `("test_batch_id", "student_id")`，构造它必须用 `test_batch_id=`；`delete_by_batch` 的合法目标仍只有三张派生表（关切 A）。原 §10.14 的 ②③④ 条不变。



