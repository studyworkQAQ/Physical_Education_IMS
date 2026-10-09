"""把 Task 2 的报告写进 .superpowers/sdd/.../task-2-report.md（UTF-8 无 BOM、LF）。"""
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1] / "task-2-report.md"
_UNUSED = (pathlib.Path(__file__).resolve().parents[2] / ".superpowers" / "sdd"
       / "2026-10-08-实施计划03-反馈预警与CRUD-API层" / "task-2-report.md")

REPORT = '''# Plan 03 Task 2 实现者报告 —— 反馈与预警的 7 张表 + 演示数据

**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `bcf3936`　**HEAD** `fd73788`
**工作树**：三个 commit 之后 `backend/` 下零残留（`git status` 只剩本报告与
`t2_probes/` 两类 `.superpowers/` 下的未跟踪文件，按惯例由控制者的结案 commit 收）
**结论**：845 passed（824 → +21）、`app/domain/` 覆盖率四格**逐字不变**、表数 18 → **25**、
扫描面**仍 38**、三个指纹逐字不变、`git diff bcf3936 HEAD -- backend/data` 为空、
`backend/pe.db` 不存在。**3 处顶回控制者**（其中 1 处 Critical）、**11 处没按派单做**、
**11 条待清扫**。

---

## ① 环境与基线复现

开工第一件事（硬规矩 #73）的 import 冒烟：

```
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
→ 2.1.3 0.141.1
```

**没有撞上 `ImportError: DLL load failed`**，六个包全部导入成功，故按派单继续（未停手）。

| 项 | 基线（`bcf3936`，本 Task 开工时亲跑复核） | 结案 |
|---|---|---|
| 分支 / 工作树 | `feature/plan-03-feedback-alert-crud-api` / 干净 | 同分支；三个 commit 之后 `backend/` 下**零残留**（`git status -- backend` 无输出），未跟踪文件只有 `.superpowers/` 下的本报告与 `t2_probes/` 九个脚本 |
| `python -m pytest -q` | **824 passed**（73.18 s） | **845 passed**（86.96 s） |
| `--cov=app.domain --cov-branch` 四格 | **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%** | **996 / 0 / 288 / 0 / 100%** —— 逐字不变 |
| 带 `--cov` 时的 passed | 823 passed, 1 skipped | **844 passed, 1 skipped** |
| 表数 | 18 | **25** |
| 扫描面 | 38（pipeline 8 + db 11 + domain 16 + api 3） | **38**（逐目录复算，见 ⑧） |
| `models` 公有名 | 39 = 基线 33 + 子模块 6 | **39 = 33 + 6**（逐字不变） |
| `len(models.__all__)` | 14 | **14** |

**四格为什么没变**：本 Task 一行 `app/domain/` 代码都没加、也没改（7 张表全在
`app/db/models/`，演示数据在 `app/demo_data.py`）。这是派单预期的结果，实测坐实。

**取证脚本**（8 个，全部住在**本工作区**的 `t2_probes/` 下，与控制者的
`_preflight.py` 同目录；这与 Plan 02 的 `fr2_probes/` / `fr3_probes/` /
`t3_probes/` 是同一个约定——探针**入库、可复现**，`test_models.py` 里对
`t2_probes/p01…p03` 的引用因此指向真实存在的文件。⚠️ `backend/` 下**不留**
本 Task 的任何临时文件：开工时先建在 `backend/t2_probes/`，收工时按新深度
修好每个脚本里「用 `__file__` 反推 backend」的那一行后整体搬过来，
并逐个重跑确认可用）：

| 脚本 | 作用 |
|---|---|
| `p01_sentinel_fk.py` | 最小复现「NOT NULL 外键列写 0」→ `FOREIGN KEY constraint failed`（顶回 #2 的证据） |
| `p02_baseline.py` | 行尾账 + 运行时口径的全部基线数字（表数 / JsonText / batch-owned / 外键 / `_in_domain` 列 / 公有名） |
| `p03_batch_owned.py` | AST 口径判「`_BATCH_OWNED_TABLES` 定义在哪个文件」（顶回 P3-A3 的证据） |
| `p04_step0_red.py` | Step 0 的 14 格逐格取证（收集期 ImportError 挡住了 pytest，故用它替报） |
| `p05_normalize_crlf.py` | 把改过的文件统一回纯 CRLF，并按 `read_bytes()` 复核 bareLF = 0 |
| `p07_mutation_idempotent.py` | 变异取证：去掉 `_training_logs` 的 upsert → 幂等那条测试当场红；还原后 sha256 逐字一致 |
| `p08_final_verify.py` | 终验（扫描面 / 指纹 / 禁区 / 公有面 / 7 张表逐列形状 / `weekly_adjustment` 约束） |

**行尾纪律（P3-A6）**：实测 `backend/app/` 与 `backend/tests/` 下**全部** 14 个目标文件
都是**纯 CRLF**（bareLF = 0），`core.autocrlf = true`。IDE 的编辑工具会保留原行尾，
但整文件重写（`feedback.py`）与新建文件（`demo_data.py` / `test_demo_data.py`）落的是 LF，
故每次改完都跑一遍 `p05_normalize_crlf.py` 并用 `read_bytes()` 复核 bareLF = 0。
`feedback.py`：475 B / 8 CRLF → **43 360 B / 679 CRLF / bareLF 0**。

---

## ② Step 0 的逐格落地（P3-A2 的 11 类命中点）

**commit ① `d07a252` 单独跑全量是红的**（派单要求，也是 TDD 的红那一步）：

```
4 failed, 790 passed, 1 warning, 1 error in 80.99s
ERROR tests/db/test_models.py
  ImportError: cannot import name 'Alert' from 'app.db.models.feedback'
FAILED tests/seed/test_generate.py::test_table_partition_is_exhaustive
  表分区不再穷尽。分区里已不存在的表 ['alert','class_session','mini_test',
  'notification','rpe_record','training_log','weekly_class_report']
FAILED tests/seed/test_generate.py::test_seed_database_writes_only_organisation_tables_and_is_idempotent
  KeyError: 'class_session'
FAILED tests/test_main.py::test_health_reports_the_table_count   (18 != 25)
FAILED tests/test_main.py::test_create_app_accepts_an_injected_db_url  (assert 18 == 25)
```

⚠️ **收集期 ImportError 把 `test_models.py` 的 30 条测试全挡住了**，它内部那 11 类命中点
因此一条也报不出来。改用 `p04_step0_red.py` 按运行时口径逐格取证（左列是**改完后写进
断言的新字面量**，中列是 Step 0 当时的运行时现值，右列是红因）：

| # | 命中点 | Step 0 实测现值 → 新字面量 | 在哪个文件 |
|---|---|---|---|
| ① | 函数名 `test_all_eighteen_tables_created` | → `test_all_twenty_five_tables_created` | `tests/db/test_models.py` |
| ② | `expected` 集合 | 18 个表名 → **25** 个（缺 `alert` / `class_session` / `mini_test` / `notification` / `rpe_record` / `training_log` / `weekly_class_report`） | 同上 |
| ③ | **两处** `assert len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"`（**中文消息里也有 18**） | `len(Base.metadata.tables)` = **18** → 25（消息里的「18 张表」一并改成「25 张表」） | 同上（`test_no_column_uses_builtin_sqlalchemy_json` 与 `test_only_batch_owned_tables_expose_batch_id`） |
| ④ | `assert len(Base.metadata.tables) == 18` | 18 → 25 | 同上（`test_models_public_namespace_is_unchanged_by_the_split`） |
| ⑤ | `assert len(json_text_columns) == 14` | 实测 **14** → **21**（运行时口径复算，7 个新 `JsonText` 列 = `mini_test.item_combo` + `alert.trigger_snapshot` + `weekly_class_report` 的 5 个） | 同上 |
| ⑥ | `_BATCH_OWNED_TABLES = {…}` | 实测带 `batch_id` 的表 **5** 张 → 字面量 **9** 个 | 同上 |
| ⑦ | `assert observed == _BATCH_OWNED_TABLES` | 9 个字面量 vs 5 张实到 → 集合相等红 | 同上 |
| ⑧ | 那段**逐字印着 grep 命令与「3 处本段的散文」计数**的注释 | `git grep -c "== 25"` 实测 **7** 处 = 3 真断言 + **4** 处散文（散文比 Plan 02 多一处，多的正是第 ④ 格新加的「`tests/test_main.py` 的 `tables == 25`（两处）」）→ 注释里的 6/3 改成 **7/4**，`prescription.py` 里同一处计数同步 | 两个文件 |
| ⑨ | 另一段注释提到 `len(json_text_columns) == 14` 与 `_BATCH_OWNED_TABLES` | 14 → 21、五张 → 九张 | `tests/db/test_models.py` |
| ⑩ | 注释「⚠️ Task 9 把它从 `_DERIVED_TABLES` 改名为 `_BATCH_OWNED_TABLES`」 | **原文印的是「从 `_BATCH_OWNED_TABLES` 改名为 `_BATCH_OWNED_TABLES`」**——原名被某一次全局替换吃掉了（`daily.py` 那一份仍是对的）。本 Task 按 `daily.py` 改回来并留了一句交代 | `tests/db/test_models.py` |
| ⑪ | **三处**引用那个函数名 | 改名后连带更新 **6 处**：`test_models.py` 两处注释、`models/__init__.py` 一处、`prescription.py` 两处；另外 4 处是本 Task 新写的引用（`feedback.py` / `main.py` / `test_main.py` / `api/conftest.py`），故 `prescription.py` 里那条 grep 的计数从 **6** 抬到 **11** | 7 个文件 |
| ⑫ | **两处** `assert len(_MODELS_PUBLIC_BASELINE) == 33` | **刻意不动**（P3-A1）。实测公有名仍 **39 = 33 + 6** | `tests/db/test_models.py` |

派单预检没列、本 Task 实测又查出**两处只以散文形式存在**的同类计数（已一并改，
并记进 `test_all_twenty_five_tables_created` 那段注释的新第 ⑥ 格）：

* `test_sqlite_foreign_keys_are_enforced` docstring 里的「**24** 个外键」→ 实测 **41**
  （新增 17：`class_session` 2 / `rpe_record` 2 / `training_log` 2 / `mini_test` 2 /
  `alert` 4 / `notification` 2 / `weekly_class_report` 3）；
* `test_string_column_widths_fit_their_value_domains` docstring 里的「今天 **18** 列」
  （受 `_in_domain` CHECK 约束的列）→ 实测 **23**（新增 5：`training_log.feeling`、
  `alert.level`、`alert.status`、`notification.recipient_kind`、`notification.channel`）。
  那条 `assert len(domains) >= 10` 是**下界**、按它自己 docstring 的交代刻意不抬。

**分区（`tests/seed/test_generate.py`）**：`DATA_TABLES` **11 → 18**（7 张全进这一个分区）、
`REFERENCE_TABLES` 上方那段「届时」预告按本次判定改写（Plan 03 又判过一次，
7 张全进 `DATA_TABLES`；`data/alert_rules.yaml` 是**阈值**的所有者、不投影出任何表）、
`assert REFERENCE_TABLES == ("exercise", "prescription_template")` **一字未动**。

**`tests/test_main.py`（S3 的裁定）**：`tables == 18` 两处 → **25**，docstring 里
「Plan 03 Task 2 之后要同步改成 25」那句改成过去时。

**`tests/api/test_scope.py`**：按派单「先实测」——实测**不依赖表数**（`git grep "18|tables|metadata"
-- backend/tests/api` 只命中 `conftest.py` 的两处散文），故未改；`conftest.py` 那两处
「建好了 18 张表」→ 25。

---

## ③ 7 张表的最终列清单与全部约束名（运行时口径，`p08_final_verify.py`）

全部住在 `backend/app/db/models/feedback.py`（475 B 空壳 → 43 360 B）。

### `class_session` —— **7 列** / 2 外键 / 索引 `ix_class_session_batch_id`

| 列 | 类型 | nullable | default | FK |
|---|---|---|---|---|
| `id` | Integer | NOT NULL | — | PK |
| `course_section_id` | Integer | NOT NULL | — | → `course_section.id` |
| `session_date` | Date | NOT NULL | — | |
| `period` | Integer | NOT NULL | — | |
| `rpe_opened` | Boolean | NOT NULL | `False` | |
| `rpe_token` | String(16) | NULL | — | |
| `batch_id` | Integer | NOT NULL | — | → `daily_sync_run.id` |

约束：**`uq_class_session_section_date_period`** = `(course_section_id, session_date, period)`
（⚠️ 顶回 #1 新增，计划正文没有）

### `rpe_record` —— **6 列** / 2 外键 / 无索引 / **无 `batch_id`**

`id`(PK) · `class_session_id`(NOT NULL, → `class_session.id`) · `student_id`(NOT NULL, → `student.id`) ·
`rpe`(Integer, NOT NULL) · `submitted_at`(DateTime, NOT NULL) · `elapsed_seconds`(Float, **NULL**, 无缺省)

约束：**`uq_rpe_record_session_student`** = `(class_session_id, student_id)`；
**`ck_rpe_record_rpe`** = `rpe BETWEEN 0 AND 10`
（⚠️ **全库第一处手写 CHECK**，P3-A5；文本由类常量 `RpeRecord.RPE_MIN = 0` /
`RPE_MAX = 10` 按 f-string 生成，不手写第二遍）

### `training_log` —— **10 列** / 2 外键 / 索引 `ix_training_log_batch_id`

`id`(PK) · `student_id`(NOT NULL, → `student.id`) · `log_date`(Date, NOT NULL) ·
`completed`(Boolean, NOT NULL, **无缺省**) · `duration_min`(Float, NULL) ·
`feeling`(String(16), NULL) · `is_rest_day`(Boolean, NOT NULL, `False`) ·
`late`(Boolean, NOT NULL, `False`) · `source`(String(16), NOT NULL) ·
`batch_id`(NOT NULL, → `daily_sync_run.id`)

类常量 `TrainingLog.FEELINGS = {"easy","moderate","hard"}`；
约束：**`uq_training_log_student_day`** = `(student_id, log_date)`；
**`ck_training_log_feeling`** = `feeling IN ('easy','hard','moderate')`

⚠️ spec §4.5 那一格写的是 `sync_run_id`，本表叫 `batch_id`（同一个父表；Ruling 31 的
命名口径），理由写在类的 docstring 里。

### `mini_test` —— **10 列**（⚠️ 派单预检未给数，本 Task 运行时口径实测是 **10** 不是 11）/ 2 外键 / **无 `batch_id`**

`id`(PK) · `student_id`(NOT NULL, → `student.id`) · `semester_id`(NOT NULL, → `semester.id`) ·
`week`(Integer, NOT NULL) · `item_combo`(**JsonText**, NOT NULL) ·
`squat_30s_count`(Integer, NULL) · `shuttle_20m_s`(Float, NULL) ·
`normalized_score`(Float, NULL) · `tested_on`(Date, NOT NULL) · `entered_by`(String(32), NOT NULL)

约束：**`uq_mini_test_student_semester_week`** = `(student_id, semester_id, week)`

### `alert` —— **14 列**（计划正文 13 列 + 顶回 #2 的 `subject_key`）/ 4 外键 / 索引 `ix_alert_batch_id`

| 列 | 类型 | nullable | FK |
|---|---|---|---|
| `id` | Integer | NOT NULL | PK |
| `student_id` | Integer | **NULL** | → `student.id` |
| `course_section_id` | Integer | **NULL** | → `course_section.id` |
| `semester_id` | Integer | NOT NULL | → `semester.id` |
| `subject_key` | String(24) | NOT NULL | （顶回 #2 新增） |
| `level` | String(8) | NOT NULL | |
| `rule_id` | String(32) | NOT NULL | |
| `trigger_snapshot` | JsonText | NOT NULL | |
| `triggered_at` | DateTime | NOT NULL | |
| `status` | String(8) | NOT NULL | （**无缺省**，照 `Prescription.status`） |
| `handled_action` | Text | NULL | |
| `handled_at` | DateTime | NULL | |
| `batch_id` | Integer | NOT NULL | → `daily_sync_run.id` |
| `window_key` | String(32) | NOT NULL | |

类常量 `Alert.LEVELS = {"red","yellow","green"}`、`Alert.STATUSES = {"pending","handled","ignored"}`；
约束：**`uq_alert_rule_subject_semester_window`** = `(rule_id, subject_key, semester_id, window_key)`
（⚠️ 顶回 #2：计划正文是 5 列含两个可空外键）、**`ck_alert_level`** =
`level IN ('green','red','yellow')`、**`ck_alert_status`** =
`status IN ('handled','ignored','pending')`、**`ck_alert_subject_is_exactly_one`** =
`(student_id IS NULL) <> (course_section_id IS NULL)`（顶回 #2 的连带新增）

### `notification` —— **10 列** / 2 外键（**都带 `ON DELETE SET NULL`**）/ **无 `batch_id`**

`id`(PK) · `recipient_kind`(String(8), NOT NULL) · `recipient_id`(Integer, NOT NULL,
**不是外键**：多态接收者) · `channel`(String(16), NOT NULL) · `title`(Text, NOT NULL) ·
`body`(Text, NOT NULL) · `alert_id`(Integer, NULL, → `alert.id` **ON DELETE SET NULL**) ·
`prescription_id`(Integer, NULL, → `prescription.id` **ON DELETE SET NULL**，⚠️ 顶回 #3) ·
`is_read`(Boolean, NOT NULL, `False`) · `created_at`(DateTime, NOT NULL)

类常量 `Notification.RECIPIENT_KINDS = {"student","teacher"}`、
`CHANNELS = {"in_app","wechat_subscribe","sms"}`；
约束：**`ck_notification_recipient_kind`**、**`ck_notification_channel`**

### `weekly_class_report` —— **12 列** / 3 外键 / 索引 `ix_weekly_class_report_batch_id`

`id`(PK) · `course_section_id`(NOT NULL, → `course_section.id`) · `semester_id`(NOT NULL,
→ `semester.id`) · `week`(Integer, NOT NULL) · `layer_distribution` / `rpe_summary` /
`checkin_rate_by_layer` / `progress_board` / `alert_summary`（**5 个 JsonText**，NOT NULL）·
`suggestion`(Text, NOT NULL) · `generated_at`(DateTime, NOT NULL) ·
`batch_id`(NOT NULL, → `daily_sync_run.id`)

约束：**`uq_weekly_class_report_section_semester_week`** =
`(course_section_id, semester_id, week)`

### `weekly_adjustment`（`prescription.py`，S2 的裁定）—— 8 列不变，约束 1 → **2**

`ck_weekly_adjustment_source`（既有）+
**`uq_weekly_adjustment_prescription_week_reason_source`** = `(prescription_id, week, reason, source)`
（P3-A4 实测：在此之前本表**没有任何 `UniqueConstraint`**）。
守卫是 `test_weekly_adjustment_rejects_a_duplicate_week_reason_source`：
同处方 + 同周 + 同原因 + 同来源插第二次 → `IntegrityError`；
换 `reason` / 换 `week` 都放行（同一周叠多条微调是本表的**累乘**语义，
`0.8 × 0.9 = 0.72`）。本 Task **只保证约束在、不建 upsert 路径**（写入方是 Task 7）。

### 连带口径（运行时复算）

| 量 | 基线 | 结案 |
|---|---|---|
| 表数 | 18 | **25** |
| `JsonText` 列 | 14 | **21** |
| 带 `batch_id` 的表 | 5 | **9** |
| 外键总数 | 24 | **41** |
| 受 `_in_domain` CHECK 约束的列 | 18 | **23** |
| 非词表 CHECK | 0 | **2**（`ck_rpe_record_rpe`、`ck_alert_subject_is_exactly_one`） |

---

## ④ P3-A1 的落地证据

**照办：7 张表全部在 `models/feedback.py`，`ops.py` 一个字节没改。**

```
git diff --stat bcf3936 HEAD -- backend/app/db/models/ops.py
→ （空输出，0 字节改动）
```

* `_MODELS_PUBLIC_BASELINE` **仍 33**（两处 `assert len(...) == 33` 一字未动）；
* `_MODELS_SUBMODULES` **仍六个**（`assessment` / `derived` / `feedback` / `ops` /
  `organisation` / `prescription`），并新增一条 `assert len(_MODELS_SUBMODULES) == 6`
  把「本 Task 不新增子模块」钉住；
* 实测 `models` 公有名 = **39 = 33 + 6**，即 7 个新类名**一个都没进**公有面
  （`from . import feedback, prescription` 是非星号导入，机制与 Plan 02 的
  `prescription.py` 完全相同）；
* `len(models.__all__)` **仍 14**（`__all__` 一字未动）；
* 守卫 `test_plan02_tables_stay_out_of_the_models_public_namespace` →
  **改名** `test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace`，
  表类 **2 → 11**（Plan 02 的 4 + 本计划的 7），并按子模块分组
  （`_PLAN02_AND_03_TABLE_CLASSES`），末尾加 `assert checked == 11` 反空转。
  **改名的理由**：本条守的是「**每一批**新表都按子模块引用」，名字只写一个计划会让
  下一个计划的实现者以为 Plan 03 的表由别处守（或另起第三条同型守卫），
  而三处引用它的散文（`models/__init__.py`、`pipeline/daily.py`、
  `pipeline/prescription_stage.py`）也会跟着指向一个不存在的事实。
  4 处引用全部同步。

**`feedback.py` 的 docstring 整段重写**（派单连带 (a)）：旧文那句「本模块今天刻意是空的」
与「留空而不是放占位类的理由见 `app.db.models.prescription` 的 docstring」都不再成立，
故**不是简单删掉交叉引用**，而是换成一段说明「为什么这 7 张表都住在这里」的正文，
把 P3-A1 的星号导入理由写在最显眼处（`⚠️⚠️` 两级标记 + 「别按 spec 的章节标题搬去
`ops.py`」的显式禁令 + 「唯一的『修法』（33 → 36）正是 Ruling 97 禁止的」）。
同一段理由在 `models/__init__.py` 的子模块归属表下方**再写一遍**（那一个是
「读包 docstring 的人」的入口，这一个是「读子模块的人」的入口，两处指向同一个结论）。

**⚠️ 派单连带 (a) 的一处措辞与本 Task 的处置不同**：派单 0.1 节说「重写时**保留**它指向
`prescription.py` docstring 的那句交叉引用」，同一节的括号里又说「那句现在不再适用，
要改成说明为什么这 7 张表都住在这里」。两句互相矛盾；本 Task 按**后半句**办
（旧交叉引用不再复述，改成 P3-A1 的理由），因为「留空而不是放占位类」这个命题
在文件不再为空之后已经不存在了，保留一句指向它的引用只会让读者去找一段不再适用的论证。

`ops.py` 的模块 docstring 仍写着「Plan 01 只落这两张表；`alert` / `notification`
属计划 03」——按派单要求一个字节没改，故这句话现在**读起来像是指向 `ops.py`**。
已在 `feedback.py` 与 `models/__init__.py` 两处显式纠正；残留登记为**待清扫第 1 条**。

---

## ⑤ `_BATCH_OWNED_TABLES` 的定义住址实测结论（P3-A3 更正）

**结论：它只有一份定义，`app/` 下的 8 处命中全是散文引用，不存在「生产代码常量 +
测试镜像」这个形状。** 取证 `p03_batch_owned.py`（AST 口径：只有 `ast.Assign` /
`ast.AnnAssign` 的目标名叫它才算定义，出现在字符串/注释里的一律算散文）：

```
=== 赋值（真定义）===
  tests/db/test_models.py: 定义在第 [312] 行；该文件共 9 行提到它
  合计定义处 = 1
=== 只有散文引用 ===
  app/db/models/__init__.py:      1 行，0 处赋值
  app/db/models/feedback.py:      2 行，0 处赋值
  app/db/models/prescription.py:  3 行，0 处赋值
  app/pipeline/daily.py:          2 行，0 处赋值
app/ 下的散文引用行数 = 8（派单预检说的是「四处命中」）
```

故**没有「两份必须同时改」**：改的是 `tests/db/test_models.py:312` 那一份的
**5 → 9** 个字面量（新增 `class_session` / `training_log` / `alert` /
`weekly_class_report`），以及 `app/` 下那 8 处散文里「五张」的说法。
派单预检说的「`__init__.py:8` 可能只是重导出」——实测**连重导出都不是**，
它是模块 docstring 里的一句散文。

**8 处散文各自改成了什么**：

| 文件 | 改动 |
|---|---|
| `app/db/repo.py`（`delete_by_batch` docstring） | 「全库只有**五张**表有这一列」→ **九张**并列出四张新表；新增一段「**有 `batch_id` 不等于在 `_replay_cleanup` 的清单里**」，点名 `ClassSession` **不得**进清单（硬规矩 #86 传导给 Task 8） |
| `app/pipeline/daily.py`（`_replay_cleanup` docstring） | 首行「**五张带 `batch_id` 的表**按批删」→「**清理清单里的**五张表按批删」+ 一段说明「全库带 `batch_id` 的是九张、本函数今天清的仍是五张」+ 一段 `⚠️⚠️ ClassSession 不得加进下面那份清单` 的完整理由（`rpe_record.class_session_id` 是 NOT NULL 外键，按批删课次要么当场 FK 违例、要么 CASCADE 连带删掉学生刚交的快评） |
| `app/db/models/assessment.py` | 「全库只有**五张**表允许拥有它」→ 九张 + 列出四张 |
| `app/db/models/prescription.py` | 那条 `git grep "_BATCH_OWNED_TABLES"` 指令的**范围从 `-- backend/tests/db/test_models.py` 扩到 `-- backend`**，并把 P3-A3 的更正逐字写进去（八处全是散文、定义只有一份） |
| `app/db/models/feedback.py`（新） | 模块 docstring 一整节「`batch_id`：七张表里只有四张有，这个区分是承重的」+「有 `batch_id` 不等于进 `_replay_cleanup`」 |
| `app/db/models/__init__.py` | 同步清单里的那一项 |

**`batch_id` 的 4/3 区分**（派单要求写进 docstring）：写在 `feedback.py` 的模块
docstring 里，并给了失效方向的名字——「顺手补齐」。守卫是新增的
`test_the_three_user_written_tables_have_no_batch_id`（点名 `rpe_record` / `mini_test` /
`notification` **没有** `batch_id`，同时反证另外四张**有**）。
少了它，把 `rpe_record` 加进 `_BATCH_OWNED_TABLES` 就能让既有的集合相等断言继续全绿。

---

## ⑥ `demo_data` 的口径与测试

`backend/app/demo_data.py`（24 341 B / 466 CRLF / bareLF 0）+
`backend/tests/test_demo_data.py`（21 740 B / 417 CRLF / bareLF 0）。

**签名**：`build_demo_feedback(session, *, cfg: SeedConfig, as_of: dt.date) -> DemoReport`；
`DemoReport` 是 frozen dataclass，5 个字段 = `batch_id` + 四张表的**库里实际行数**。

**口径**：

1. **不是 `seed_database` 的一段**（独立函数、独立入口）。它读的组织结构一律**从库里来**，
   `cfg` 只用到 `cfg.seed` 这一项——按 `cfg.students` 重造一遍人口就是第二个所有者，
   而且会与 `seed_database` 写出的组织结构对不上。库里没有组织结构时**响亮失败**
   （`ValueError`，消息里点名「先跑 `seed_database`」），不静默返回一个全 0 的报告。
2. **只写 4 张表**：`class_session` / `rpe_record` / `training_log` / `mini_test`。
   `alert` / `notification` / `weekly_class_report` **一行都不写**——它们是 Task 7/8/9
   三个引擎的产物，伪造它们会①占掉 `alert` 那条去重键、让 `alert_stage` 第一次真跑就
   `IntegrityError`；②让「预警 → 减量 20% → 学生端看到更新后的训练单」这条闭环的
   验收变成假象。
3. **时钟由调用方注入**：`as_of` 是唯一时间来源。⚠️ 模块里一个 `.now` / `.today` /
   `.time` 都不出现——为此专门写了 `_at(day, hour, minute, second)` 用
   `dt.datetime(...)` 构造器，**不用** `dt.datetime.combine(day, dt.time(...))`，
   因为守卫的判据是「调用的末段属性名」，而 `time` 在那份词表里是 `time.time()` 的替身。
   理由写在 `_at` 的 docstring 里。
4. **随机数只有一个入口** `np.random.default_rng(cfg.seed)`；
   随机流的消耗顺序固定（外层周次、内层教学班/学生，全部按 `id` 排序），故同种子同输出。
   两处**刻意取模而不是抽样**（`HIGH_RPE_EVERY = 10`、`LATE_EVERY = 7`）：
   抽样会让「谁被挑中」依赖随机流，于是「至少有一个学生连续 ≥ 3 次 RPE ≥ 9」
   这条断言会因为换种子而落空。
5. **幂等靠自然键 upsert**（`repo.upsert`），**不是**「先删后插」：`rpe_record` 与
   `mini_test` 是用户实时写入的表，演示生成器没有资格删它们。
   不 commit（与 `seed_database` / `repo.upsert` 同口径）。
6. **要建一条 `daily_sync_run`**：`class_session.batch_id` 与 `training_log.batch_id`
   都是 NOT NULL 外键，故 `_demo_batch` 按 `(semester_id, business_date)` upsert
   `as_of` 那一天的批次行（真实管道在同一天跑过或将要跑时，两边命中的是**同一行**）。
   `status` 显式写 `"success"`（列上缺省是 `"failed"`，Ruling 30）；计数列一律留缺省 0
   ——本模块不假装自己抽取过任何源数据。
7. **`mini_test.normalized_score` 是演示口径的近似值**（`round((深蹲次数 + max(0, 45 - 折返秒)) / 2, 2)`），
   不是 spec §8.1 那个「折返得分 = 班内百分位反查」的真算法（那是 spec §5 第 7 阶段
   Aggregate 的活）。这一点在模块 docstring、`MiniTest` 的类 docstring 与
   `_mini_tests` 的 docstring 三处都逐字声明了。

**四条测试**（派单要求的三条 + 一条）：

| 测试名 | 守什么 |
|---|---|
| `test_build_demo_feedback_is_idempotent` | 跑**三**次，`DemoReport` 逐字相同（16 / 480 / 1680 / 480），且第三次当场从库里数一遍与报告一致。四个计数**都不是 0**（反空转：否则「两次相同」只是「两次都没写」）。⚠️ `DemoReport` 的计数是**从库里数出来的**、不是自报——自报会让本条恒真 |
| `test_demo_data_never_touches_the_clock` | 源码级守卫（AST）：`app/demo_data.py` 里零个时钟调用、零个无种子 `default_rng`、零个 `import random` / `import time`、零个 numpy 全局采样。**词表从 `tests/seed/test_generate.py` import、不抄第二份**（单一所有者）。配 **4 组自证**（`dt.date.today()` / `dt.datetime.now()` / 无种子 `default_rng()` / `import time` + `np.random.seed` + `np.random.normal` + `time.time()`，逐组断言守卫报警）与 **1 组负对照**（本模块真正的合法写法必须放行） |
| `test_seed_database_still_writes_no_feedback_rows` | `seed_database` 之后 7 张新表**全 0 行**；反空转 = 同一个库上组织结构确实写进去了（120 个学生、4 + 3 个教学班）。第二段再跑一次演示生成器：4 张有行、`alert` / `notification` / `weekly_class_report` **仍是 0** |
| `test_demo_feedback_gives_the_alert_engine_something_to_fire_on`（本 Task 加的第四条） | 「演示库有 1 680 行打卡」与「演示库能让预警跑起来」是两件事。逐条对着 spec §8.2 钉原料：至少一个学生有 ≥ 3 次 RPE ≥ 9（`RED_RPE_SUSTAINED`）、≥ 3 个**偶数**周的小测（`RED_MINITEST_DROP` 要 3 个点）、未完成 + 休息日两档都在（`YELLOW_CHECKIN_GAP`）、`completed=True` 且 `late=True` 那一档存在（spec §8.1 的「练了但交得晚，不计入当日完成」）、RPE 全落在 0–10、`training_log.source` 一律是 `"demo"`。阈值一律写**字面量**（9 / 3 / 2），不读 `demo_data.HIGH_RPE_FLOOR`（硬规矩 #35） |

**变异取证**（`p07_mutation_idempotent.py`，Ruling 1 说本 Task 不做变异，
故这一条只针对「新写的守卫有没有牙」，不是对既有代码的变异扫描）：
把 `_training_logs` 的 `repo.upsert(...)` 换成裸 `session.add(...)` →

```
FAILED tests/test_demo_data.py::test_build_demo_feedback_is_idempotent
  sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError)
  UNIQUE constraint failed: training_log.student_id, training_log.log_date
returncode = 1
restored sha256 match: True      ← 按字节还原，CRLF 466 / bareLF 0
```

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### ⑦.1 顶回控制者（**3 处**）

**顶回 #1（Important）：`class_session` 必须有 `UniqueConstraint(course_section_id, session_date, period)`。**

* **哪条决定**：计划正文给 `rpe_record` / `training_log` / `mini_test` / `alert` /
  `weekly_class_report` 五张都点了唯一约束，**唯独 `class_session` 没有**。
* **为什么错**：三个理由，第三个是本 Task 现场才出现的。
  ① `repo.upsert` 是「先 select 再 update/insert」，没有 DB 兜底时两个写入方
  （Task 5 的采集端点与演示生成器）会各插一行，而下一次 upsert 的 select 撞上
  `MultipleResultsFound`——**炸在离真因很远的读侧**；
  ② 课次翻倍后「这节课的快评提交率」的分母（选课人数）对不上分子，
  而 spec §8.1 要求教师端「实时显示已提交/未提交名单」；
  ③ **`class_session` 不能进 `_replay_cleanup`**（见顶回 #2 的连带发现），
  于是它的幂等手段**只能**是 upsert——那条 UNIQUE 是它唯一的兜底。
* **替代方案**：加 `uq_class_session_section_date_period`，守卫是
  `test_class_session_rejects_a_second_session_for_the_same_section_date_and_period`
  （含「换 `period` / 换日期就是另一节课」那一档，免得约束被写成两列）。
* **代价（若我错了）**：3 行回退。风险是 Task 5 若真要「同一个班同一天同一节次两节课」
  （例如补课）会被挡住——但 `period` 正是用来区分它的，而 spec §4.5 把「节次」
  列为关键字段本身就意味着它是区分键。
* ⚠️ **反面先例已核**：`course_section` 被 `seed_database` 按 `(semester_id, name)`
  upsert 却**没有** UNIQUE。故本仓确实容得下「upsert 无 DB 兜底」这个形状。
  我仍然认为该加：`course_section` 只有一个写入方（`seed_database`），
  而 `class_session` 从 Task 5 起有两个（采集端点 + 演示生成器）。

**顶回 #2（Critical）：`alert` 的「`nullable=False` + 用 `0` 作哨兵」方案在本库跑不起来。**

* **哪条决定**：派单 §5 与计划正文的决定段逐字要求「`student_id` 与 `course_section_id`
  **都改成 `nullable=False` + 用 `0` 作哨兵**」，去重键是
  `(rule_id, student_id, course_section_id, semester_id, window_key)`。
* **为什么错**：**诊断是对的，方子撞在另一堵墙上**。这两列在计划的 Interfaces 里都是外键，
  而 `app/db/session.py` 的 `_sqlite_foreign_keys_on` 钩子挂在 `Engine` **类**上
  （Ruling 27），故 `PRAGMA foreign_keys` 对测试的内存库同样是 1；父表里没有 `id = 0`
  的行（SQLite rowid 从 1 起），于是**每一条**哨兵行都会当场
  `IntegrityError: FOREIGN KEY constraint failed`。最小复现 `p01_sentinel_fk.py` 亲跑：

  ```
  PRAGMA foreign_keys = 1
  parent ids = [1]
  RESULT: parent_id=0 被拒收 -> IntegrityError
          orig = FOREIGN KEY constraint failed
  ```

  而**照派单做的话这个失效不会被任何既有测试抓到**：本 Task 之前一张 `alert` 都没有，
  写它的是 Task 7——即缺陷会在两个 Task 之后、以「预警一条都插不进去」的形式爆出来。
* **替代方案**：两个外键列**保持可空**（完整性不丢），另加一个 NOT NULL 的
  `subject_key`（学生级 `student:<id>`、班级级 `section:<id>`）承担去重键的主语位，
  去重键改成 `(rule_id, subject_key, semester_id, window_key)`——四列全 NOT NULL，
  UNIQUE 对两种作用域**都真的生效**。并配 `ck_alert_subject_is_exactly_one`
  （`(student_id IS NULL) <> (course_section_id IS NULL)`）兜住 `subject_key` 的前提。
  **这与 `CleaningLog` 的 `student_no`（非空）+ `student_id`（可空外键）双列承载
  （Ruling 25）是同一个形状**：真的外键留可空，另配一个 NOT NULL 的伴随列去承担约束。
* **为什么不是别的方案**：
  · 「两列 NOT NULL 但**不是**外键」→ 丢掉完整性，而 Review Focus 第 4 条要的正是
  「FK 违例当场炸而不是静默留下孤儿行」；
  · 「SQLite 表达式/部分索引 `COALESCE(student_id,-1)`」→ 计划已显式否掉部分索引，
  且它是 SQLite 方言、`inspect().get_unique_constraints()` 也看不见它；
  · 「加 `scope_kind` 列」→ 计划已否掉，且它同样需要一个 NOT NULL 的主语位。
* **代价（若我错了）**：`alert` 多一列（14 而不是 13）、`subject_key` 的算式要在
  Task 6 的 `app/domain/alerts.py` 里多产出一个值（与 `window_key` 同一处、同一种
  纯函数），去重键从 5 列变 4 列。回退成本：删一列 + 改一条约束 + 改 3 条测试。
* **`subject_key` 的冗余是明写的代价**：它可由那两个外键推出。DB 层守不住
  「`subject_key` 与非空的那一列一致」（那需要把前缀词表在 SQL 里再拼一次，
  而前缀的唯一所有者是 Task 6 的 domain 侧——domain 按 Global Constraints 不得
  import `app.db`，故它拿不到模型上的常量）。这一条已登记为**关切**（⑦.2 第 7 条）。
* **哨兵方案还撞第二堵墙**：它要求两列都 NOT NULL（一列真 id、一列 0），
  于是 `ck_alert_subject_is_exactly_one` 也会拒收每一条。
  `test_alert_subject_sentinel_zero_would_violate_the_fk` 把两堵墙**分别**钉住
  （前两段的另一列保持 NULL，好让 XOR 那条 CHECK 不参与，报错只可能来自外键；
  第三段两列都非空，报的是 CHECK 的名字）。

**顶回 #3（Important）：`notification.prescription_id` 也必须带 `ondelete="SET NULL"`。**

* **哪条决定**：派单 §5 与计划正文只点了 `alert_id` 要 `SET NULL`，
  理由是「Task 8 会把 `Alert` 加进 `_replay_cleanup`」。
* **为什么不够**：`prescription` **今天就已经在** `_replay_cleanup` 的清单里
  （Plan 02 Task 7，P7-A4，`daily.py` 的清单第 5 项）。所以「重放那天删掉处方」
  不是 Task 8 才会发生的事、**是现在每天都在发生的事**。少了 `SET NULL`，
  第一条指向处方的通知一落库（Task 8 的「本周训练单已更新」正是这一类），
  下一次重放同一天就会当场炸在 `delete_by_batch(session, Prescription, …)` 上——
  而 Plan 02 的既有测试全绿，因为它们一条 `notification` 都不写。
* **替代方案**：两个可空外键都带 `ondelete="SET NULL"`。守卫是
  `test_notification_alert_id_and_prescription_id_are_set_null_on_delete`，
  它①按 **DDL 渲染**断言 `ON DELETE SET NULL` 出现**两次**
  （不读 `fk.ondelete`——那一侧与被测的列声明同源，硬规矩 #35）；
  ②删 `alert` → 通知留下、`alert_id` 变 NULL；
  ③**照 `_replay_cleanup` 的真实写法**走 `repo.delete_by_batch(session, Prescription, run.id)`
  → 通知留下、`prescription_id` 变 NULL。
* **代价（若我错了）**：断开关联的通知点不回原处方。前端应把 `prescription_id IS NULL`
  渲染成不可点的纯文本——已登记为关切。

### ⑦.2 关切（不是缺陷，是明写的代价与传导项）

1. **`ClassSession` 不得进 `_replay_cleanup`**（按硬规矩 #86 传导给 **Task 8**）。
   `rpe_record.class_session_id` 是 NOT NULL 外键指向它，而 `rpe_record` 是用户实时写入、
   重放不该删。按批删课次只有两种结局：当场 FK 违例，或改成 `CASCADE` 连带删掉学生
   刚交的快评（比 FK 违例严重得多）。它的幂等手段是 upsert，与三张源表同一档；
   它那一列 `batch_id` 只用来回答「这一行是哪一次同步写进来的」。
   `Alert` / `WeeklyClassReport` / `TrainingLog` 没有这个问题。
   **三处都写了**：`feedback.py` 模块 docstring、`repo.py` 的 `delete_by_batch`、
   `daily.py` 的 `_replay_cleanup`。
2. **Task 7 写 `weekly_adjustment` 时，`repo.upsert` 的 `key_fields` 应当就是那四列**
   （`prescription_id` / `week` / `reason` / `source`）。⚠️ `reason` 是自由文本，
   改一个标点就绕过约束，故它只是最后一道兜底、不是防重复触发的主手段。
3. **Task 6 要给 `subject_key` 与 `window_key` 定算式**（domain 侧纯函数，
   `app/domain/alerts.py`）。`subject_key` 的前缀词表（`student:` / `section:`）
   **只有那一个所有者**——`feedback.py` 刻意不声明前缀常量，测试里一律写字面量形状。
4. **Task 6 校验 `alert_rules.yaml` 时应拿 `RpeRecord.RPE_MIN` / `RPE_MAX` 当上界**：
   spec §8.2 的 `RED_RPE_SUSTAINED`（连续 ≥ 9）与 `YELLOW_CLASS_RPE_HIGH`（均值 > 7）
   都建立在 0–10 这个值域上，把 RPE 改成百分制而不同步阈值，那两条规则会**静默失效**。
   ⚠️ 但 domain 层不得 import `app.db`（Global Constraints），故这个校验只能住在
   `app/refdata_alerts.py`（加载器）里、不能在 `app/domain/alerts.py` 里。
5. **Task 5 要回来定 `training_log.source` 的值域并补 CHECK**（今天没有唯一所有者，
   演示生成器写 `"demo"`）。届时往一个已结案的 CHECK 里加值 = 重建库。
6. **Task 3 的删除策略要显式声明两档「非外键」**：`notification.recipient_id`
   （多态接收者，删学生不带走他的通知）与 `mini_test.entered_by`（工号字符串，
   删教师不带走他录的小测）。两者都是计划正文的显式选择，不是漏。
7. **`alert.subject_key` 与两个作用域列的一致性没有 DB 层守卫**（硬规矩 #39）：
   `student_id = 7` 而 `subject_key = "section:3"` 在库层面放行。
   `ck_alert_subject_is_exactly_one` 只保证「恰好一个非空」。
   那半边由 Task 6/7 的写入方负责。
8. **`notification.channel` 是 `String(16)`，最长值 `"wechat_subscribe"` 正好 16、
   余量 0**（计划正文给的宽度）。SQLite 不强制长度，故换更长的通道名不会在本仓报错、
   会在换严格后端时静默截断（Ruling 144 的形状）。列注释里已标 `⚠️`。
9. **`class_session.rpe_opened` 与 `rpe_token` 之间没有约束**：
   `rpe_opened = False` 而 `rpe_token` 非空在库层面放行。Task 5 的写入方要自己保证一致。
10. **`weekly_adjustment` 的新唯一约束把 `reason`（TEXT）放进了键**。
    SQLite 允许（BINARY collation 逐字节比），**换 MySQL 要给这一列指定前缀长度**。
11. **`backend/pe_demo.db` 是 Task 1 留下的陈旧演示库**（172 032 B、**18 张表**、
    mtime 2026-10-09 11:02，已进 `.gitignore`，本 Task 未触碰也未重建）。
    ⚠️ 下次跑 uvicorn 时 `create_all` 会补出 7 张新表，但**不会**给已存在的
    `weekly_adjustment` 补那条新唯一约束（本仓不做迁移）→ 演示库上
    「同周重复减量」那道 DB 兜底会**静默缺席**。建议删掉重建
    （删 `backend/pe_demo.db` 后按 `app/main.py` 模块 docstring 里那三行跑）。
    **本 Task 没有删它**：它是控制者 Task 1 验收时留下的产物，删别人的文件属越界。
12. **spec §14 要登记两项**：`alert.window_key`（计划已点）与 **`alert.subject_key`**
    （顶回 #2 新增，计划没有）。派单的 Modify 清单里没有 spec 文件
    （计划的 File Structure 把 `Document/…设计spec.md`（§14 补项）列为「修改」项，
    归属看起来是收尾的 Task），故本 Task 未动 spec。

### ⑦.3 没按派单做的地方（**11 处**，逐条）

1. **P3-A1 的哨兵 0 方案没做**，改成可空外键 + `subject_key`（顶回 #2）。
   连带：`alert` 的去重键从 5 列变 4 列、`alert` 从 13 列变 14 列。
2. **加了派单没有的 `ck_alert_subject_is_exactly_one`**（顶回 #2 的前提守卫）。
3. **加了派单没有的 `uq_class_session_section_date_period`**（顶回 #1）。
4. **`notification.prescription_id` 也加了 `ondelete="SET NULL"`**（顶回 #3）。
5. **P3-A3 的「改定义那一份、再改镜像，两处必须同时改」没有第二处可改**：
   实测只有一份定义（AST 取证），改的是那一份 + `app/` 下 8 处散文。
6. **`test_plan02_tables_stay_out_...` 改名为 `test_plan02_and_plan03_tables_stay_out_...`**
   （派单让我自己判断）。连带 4 处散文引用同步，其中 2 处在 Plan 02 已结案的生产文件里
   （`pipeline/daily.py`、`pipeline/prescription_stage.py`，只改注释）。
7. **`mini_test` 的列数是 10 不是 11**：派单没给这个数，但计划的 Interfaces 列了
   10 个字段（含 `id`），运行时口径实测 **10**。`_PLAN03_TABLE_SHAPE` 里第一版按 11 写、
   被自己的形状测试当场抓出来（这正是那条测试的价值）。
8. **多改了 6 个派单没列的文件**（全是散文同步，硬规矩 #66）：
   `app/db/models/_shared.py`（21 个 JsonText 列 + 「六个表模块都要用它」）、
   `app/db/models/assessment.py`、`app/db/repo.py`、`app/pipeline/daily.py`、
   `app/pipeline/prescription_stage.py`、`app/main.py`、`tests/api/conftest.py`。
   ⚠️ 其中 `prescription.py` 与 `_shared.py` 的「三处同一事实」（14 → 21）是
   `prescription.py` 自己的 docstring 逐字要求的，不改就是留下一处已知漂移。
9. **`tests/api/test_scope.py` 未改**：派单说「若它的夹具依赖表数则同步；先实测」——
   实测不依赖（只有 `conftest.py` 的两处散文）。
10. **`DemoReport` 的字段形状是本 Task 自定的**（派单只给了函数签名）：
    `batch_id` + 四个**从库里数出来的**行数。刻意不报「本函数写了几行」，
    否则幂等那条断言恒真。
11. **`demo_data` 多写了一条测试**（派单说「至少」三条）：
    `test_demo_feedback_gives_the_alert_engine_something_to_fire_on`。
    理由：`build_demo_feedback` 存在的唯一理由是喂 Task 7 的规则，
    而「行数 > 0」证明不了这件事（480 行全是 RPE = 5 的小测一样能过）。
    ⚠️ 派单 §0.6 说「不做变异（Ruling 1）」——本 Task 只对**自己新写的守卫**做了
    一次变异取证（`p07`），没有对既有代码做变异扫描。

**另外按派单要求做、但派单没点明的两处小修**：
`tests/db/test_models.py` 里那句「Task 9 把它从 `_BATCH_OWNED_TABLES` 改名为
`_BATCH_OWNED_TABLES`」（自指错字，原名被某次全局替换吃掉了）按 `daily.py`
里仍正确的那一份改回 `_DERIVED_TABLES`，并留了一句交代；
`_in_domain_columns()` 里那句「不是取值域约束（本库今天没有这类 CHECK）」
此前是**死代码注释**，现在有两条这类 CHECK，已逐条写明。

### ⑦.4 待清扫（**11 条**）

1. `app/db/models/ops.py` 模块 docstring 仍写「Plan 01 只落这两张表；`alert` /
   `notification` 属计划 03」——派单要求 `ops.py` 一个字节不改，故未动。
   现在读起来像是指向 `ops.py`。`feedback.py` 与 `models/__init__.py` 两处已显式纠正。
   建议改成「`alert` / `notification` 由 Plan 03 Task 2 建在 `:mod:`.feedback``（P3-A1）」。
2. `app/db/session.py` **三处**「15 张表」（模块 docstring、`Base` 的 docstring、
   `init_db` 里的注释）——Plan 02 结案时就已过期（当时 18），本 Task 之后是 25。
   属既有待清扫，不在派单清单里，故未动。
3. `app/db/repo.py` 的 `upsert` docstring「对 **14** 个模型通用」——同样是 Plan 02
   就过期的数（今天 25）。
4. `backend/pe_demo.db` 陈旧（18 张表），建议删掉重建（详见 ⑦.2 第 11 条）。
5. `training_log.source` 没有值域所有者，Task 5 落地时补 CHECK（⑦.2 第 5 条）。
6. `notification.channel` 的 `String(16)` 余量为 0（⑦.2 第 8 条）。
7. `alert.subject_key` 与两个作用域列的一致性无 DB 层守卫（⑦.2 第 7 条）。
8. `class_session.rpe_opened` ↔ `rpe_token` 无约束绑定（⑦.2 第 9 条）。
9. `notification.recipient_id` / `mini_test.entered_by` 不是外键，
   Task 3 的删除策略要显式声明这两档（⑦.2 第 6 条）。
10. `weekly_adjustment` 的唯一约束把 TEXT 列 `reason` 放进了键，换 MySQL 要指定前缀长度
    （⑦.2 第 10 条）。
11. spec §14 要登记 `alert.window_key` 与 `alert.subject_key` 两项（⑦.2 第 12 条），
    归属看起来是计划里负责改 spec 的那个 Task。

---

## ⑧ 最终验收

```
$ cd backend; python -m pytest -q
845 passed, 1 warning in 86.96s                       ← 824 → 845（+21）

$ python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing
Name      Stmts   Miss Branch BrPart  Cover   Missing
TOTAL       996      0    288      0   100%           ← 四格逐字不变
844 passed, 1 skipped, 1 warning in 192.72s
```

| 验收项 | 结果 |
|---|---|
| passed 数 | **824 → 845**（+17 在 `tests/db/test_models.py`：`def test_` 30 → 47；+4 在 `tests/test_demo_data.py`） |
| 覆盖率四格 | **996 / 0 / 288 / 0 / 100%** —— 逐字不变（本 Task 不加 `app/domain/` 代码） |
| 表数 | **18 → 25** |
| 扫描面 | **仍 38**（`p08` 逐目录复算：pipeline 8 + db 11 + domain 16 + api 3；本 Task 在 `app/api/` 下**零新增文件**，新增的 `app/demo_data.py` 是 `app/` 根下的模块、不在 `SCANNED_DIRS` 任何一项里，与 `app/main.py` / `app/refdata.py` / `app/notify.py` 同档） |
| `len(json_text_columns)` | **14 → 21** |
| `_BATCH_OWNED_TABLES` | **5 → 9**；定义住址实测 = **`tests/db/test_models.py:312`，仅此一份** |
| `DATA_TABLES` | **11 → 18** |
| `_MODELS_PUBLIC_BASELINE` | **仍 33**（两处断言一字未动）；实测公有名 39 = 33 + 6 |
| `_MODELS_SUBMODULES` | **仍六个** |
| `ops.py` | **`git diff bcf3936 HEAD -- backend/app/db/models/ops.py` 输出为空**（0 字节改动） |
| 三个指纹 | `D2C8E539E2FA0029`（`national_standard_2014.csv`，21 412 B）/ `5394B37F01DAC9AC`（`exercises.yaml`，23 247 B）/ `822CB86A5E998301`（`exercise_equivalence.yaml`，8 245 B）—— **逐字不变**（sha256 前 16 位大写、行尾归一化为 LF 后算，与 `tests/test_refdata.py` 同口径） |
| `git diff bcf3936 HEAD -- backend/data` | **输出为空**（`backend/data/**` 一个字节没动；`data/seed/` 仍是 **0 个文件**） |
| `backend/pe.db` | **不存在**（`pe.db` / `pe.db-journal` / `pe.db-wal` 三个都不存在）。全程未跑 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`，未跑 uvicorn，未设过 `PE_DB_URL` 之外的任何库路径；测试一律 `sqlite://` 内存库 |

### commit 清单

| sha | 一句话 |
|---|---|
| **`d07a252`** | Step 0：表数 18→25 的全部命中点先改测试（**刻意红**：4 failed / 790 passed / 1 collection error，红因逐条见 ②） |
| **`78fa495`** | 7 张表（全在 `models/feedback.py`）+ `weekly_adjustment` 的唯一约束 + 全部散文同步 → **841 passed** |
| **`fd73788`** | `app/demo_data.py` + `tests/test_demo_data.py`（4 条）→ **845 passed** |

`git add` 一律按文件名逐个加（未用 `-A`）；commit 信息一律 python 写 UTF-8 **无 BOM**
临时文件 + `git commit -F`（三个都亲验 `BOM False`）；**未 push、未切分支、未碰 main**。
'''

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(REPORT.replace("\r\n", "\n").encode("utf-8"))
raw = OUT.read_bytes()
print("path:", OUT)
print("bytes =", len(raw), "| lines =", raw.count(b"\n"), "| BOM =", raw[:3] == bytes([0xEF, 0xBB, 0xBF]))
print("CRLF =", raw.count(b"\r\n"), "(.gitattributes 把 .superpowers/** 钉成 LF，应为 0)")
print("first line:", raw.decode("utf-8").splitlines()[0])
print("last line :", raw.decode("utf-8").splitlines()[-1][:70])
