"""Plan 03 Task 3 预检更正（P3-B1..B8）+ 账本 Ruling 8。逐条 assert 命中次数。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
LEDGER = HERE / "progress.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    b0 = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行")


IMPORTS = """| 资源 | 表 | 模型类 | **import 路径（⚠️ P3-B1：11 个不在 `models` 的公有面上）** | 列数 | 自然键（唯一约束的列） | `JsonText` 列（`list_exclude` 的缺省值） |
|---|---|---|---|---|---|---|
| `semesters` | `semester` | `Semester` | `app.db.models`（**或** `…organisation`） | 6 | `name`（约束**无名**） | — |
| `teachers` | `teacher` | `Teacher` | `app.db.models` | 3 | `staff_no`（无名） | — |
| `students` | `student` | `Student` | `app.db.models` | 7 | `student_no`（无名） | — |
| `course-sections` | `course_section` | `CourseSection` | `app.db.models` | 6 | **⚠️ 无唯一约束** | — |
| `enrollments` | `enrollment` | `Enrollment` | `app.db.models` | 4 | `semester_id, student_id, course_section_id` | — |
| `fitness-test-batches` | `fitness_test_batch` | `FitnessTestBatch` | `app.db.models` | 6 | **⚠️ 无唯一约束** | — |
| `fitness-test-results` | `fitness_test_result` | `FitnessTestResult` | `app.db.models` | **21** | `test_batch_id, student_id` | — |
| `body-compositions` | `body_composition` | `BodyComposition` | `app.db.models` | 8 | `student_id, measured_on` | — |
| `interest-surveys` | `interest_survey` | `InterestSurvey` | `app.db.models` | 7 | `student_id, semester_id, filled_on` | `dimensions`, `raw_answers` |
| `percentile-snapshots` | `percentile_snapshot` | `PercentileSnapshot` | `app.db.models` | 14 | `semester_id, computed_on, item, sex, age_group` | — |
| `derived-metrics` | `derived_metrics` | `DerivedMetrics` | `app.db.models` | 11 | `student_id, computed_on` | `annual_change`, `weaknesses`, `body_comp_reasons` |
| `stratification-results` | `stratification_result` | `StratificationResult` | `app.db.models` | 10 | `student_id, computed_on` | `input_snapshot` |
| `exercises` | `exercise` | `Exercise` | **`app.db.models.prescription`** | 7 | `ref`（无名） | `targets` |
| `prescription-templates` | `prescription_template` | `PrescriptionTemplate` | **`app.db.models.prescription`** | 10 | `template_ref`（无名） | — |
| `prescriptions` | `prescription` | `Prescription` | **`app.db.models.prescription`** | 16 | `student_id, generated_on` | **5 个**：`training_package`, `assembly_snapshot`, `safety_substitutions`, `teacher_overrides`, `trigger_reasons` |
| `weekly-adjustments` | `weekly_adjustment` | `WeeklyAdjustment` | **`app.db.models.prescription`** | 8 | `prescription_id, week, reason, source` | — |
| `class-sessions` | `class_session` | `ClassSession` | **`app.db.models.feedback`** | 7 | `course_section_id, session_date, period` | — |
| `rpe-records` | `rpe_record` | `RpeRecord` | **`app.db.models.feedback`** | 6 | `class_session_id, student_id` | — |
| `training-logs` | `training_log` | `TrainingLog` | **`app.db.models.feedback`** | 10 | `student_id, log_date` | — |
| `mini-tests` | `mini_test` | `MiniTest` | **`app.db.models.feedback`** | 10 | `student_id, semester_id, week` | `item_combo` |
| `alerts` | `alert` | `Alert` | **`app.db.models.feedback`** | 14 | `rule_id, subject_key, semester_id, window_key` | `trigger_snapshot` |
| `notifications` | `notification` | `Notification` | **`app.db.models.feedback`** | 10 | **⚠️ 无唯一约束** | — |
| `weekly-class-reports` | `weekly_class_report` | `WeeklyClassReport` | **`app.db.models.feedback`** | 12 | `course_section_id, semester_id, week` | **5 个**：`layer_distribution`, `rpe_summary`, `checkin_rate_by_layer`, `progress_board`, `alert_summary` |

"""

PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `8d8d3b3`，取证脚本 `t3_probes/_preflight.py`）

**测试基线**：`845 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**；扫描面 **38**。

| # | 级别 | 事实（全部实测，运行时口径） | 更正 |
|---|---|---|---|
| **P3-B1** | **Critical** | **23 个资源里有 11 个的模型类不在 `app.db.models` 的公有导入面上**（Ruling 97：Plan 02 的 4 个 + Plan 03 的 7 个表类**刻意不重导出**）。实测：`exercise` / `prescription_template` / `prescription` / `weekly_adjustment` 住 `app.db.models.prescription`；`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 住 `app.db.models.feedback`。**计划 Task 3 的正文一个字都没提这件事** —— 照它的字面写 `model=models.Prescription` 会得到 **11 个 `AttributeError`**。 | **下面那张 23 行的表逐个给出 import 路径**，`RESOURCES` 照它写。**⚠️ 这与 Plan 02 的 P6-A8 / Plan 03 Task 2 的顶回 1 是同一族**：Ruling 97 这条纪律已经传导过两次，**而控制者第三次写计划时又忘了它** → 见下方硬规矩 #102 |
| **P3-B2** | **Important** | **3 个资源没有唯一约束**：`course_section`、`fitness_test_batch`、`notification`。故 `test_create_with_a_duplicate_natural_key_is_409` **对它们写不出来**，`repo.upsert(session, model, key_fields, values)` 的 `key_fields` **也没有东西可填**。 | `build_crud_router` 加一个参数 **`natural_key: tuple[str, ...] | None`**：非空 → POST 走 `repo.upsert`（撞键 → **409**）；`None` → POST 走**裸 `session.add`**（**没有 409 这一档**，因为结构上不可能撞）。**⚠️ 那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的资源写一条反向测试**（`test_a_resource_without_a_natural_key_never_returns_409`）—— 否则下一个人会以为 409 是普适的 |
| **P3-B3** | **Important** | **`JsonText` 列实测共 21 个，分布在 8 张表**（`interest_survey` 2、`derived_metrics` 3、`stratification_result` 1、`exercise` 1、`prescription` **5**、`mini_test` 1、`alert` 1、`weekly_class_report` **5**）。计划要求 `list_exclude: tuple[str, ...] = ()` 由调用方**逐个手写** —— 23 行里手抄 21 个列名，**抄漏一个就是一次全表 JSON 拉取**（Plan 02 Task 7 的性能回归正是「大 JSON 列 eager 加载」，`elapsed` 一度到 115 s）。 | **`list_exclude` 改成自动探测**：缺省 = `[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`，**并保留一个显式覆盖参数**（给「list 端点确实要返回某个小 JSON 列」的例外）。**理由：自动探测不会抄漏，而「多排除一个列」的后果（read-one 里还能拿到）远轻于「少排除一个列」（性能回归且没人看得见）。** ⚠️ 要有一条测试遍历 23 个资源、断言 **list 响应里一个 `JsonText` 列都不出现**、而 read-one 响应里全部出现 |
| **P3-B4** | **Important** | `on_delete="restrict"` 要「点名是哪张子表挡住的」，而**子表清单不在模型上**：实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。 | **`crud.py` 里写一个 `_child_tables(model) -> list[tuple[str, str]]`**（返回 `(子表名, 子表的FK列名)`），实现是遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`。**⚠️ 它必须排除 `ondelete` 为 `SET NULL` 或 `CASCADE` 的那些 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`（Task 2 的顶回 3 加的），**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己会 SET NULL）。要有一条测试钉住这个排除 |
| **P3-B5** | **Important** | 5 张表的唯一约束是**无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）。 | **409 的消息里不得引用约束名**（它是 `None`，会渲染成 `"None"`）→ 引用**列名**。**并要有一条测试断言 409 的 `message` 里含列名、不含字面 `"None"`** —— 否则前端会把 `None` 显示给教师看 |
| P3-B6 | Minor | 实测 `app/api/deps.py` 的公开面 = `Engine` / `Page` / `Student` / `current_student` / `current_teacher` / `get_db` / `require_scope`（**没有模块级大写常量**，`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 实测住在 `app/main.py`）；`app/api/errors.py` 的公开面 = `error_response(status_code, code, message, detail=None, headers=None)` 与 `register_error_handlers(app)`。 | 计划正文写「`deps.py` 的 `DB_URL_ENV_VAR`」是错的 —— **它们在 `main.py`**。**工厂不碰这两个常量**（它只拿 `Session`），故本条只是更正出处、不改设计 |
| P3-B7 | Minor | 实测 `repo.py` 的公开函数只有两个：`upsert(session, model, key_fields: Sequence[str], values: dict) -> Any` 与 `delete_by_batch(session, model, batch_id: int) -> int`。**没有 `get_or_404` 之类的读取助手。** | 工厂的 read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要为此给 `repo.py` 加新函数**（`repo.py` 是 Plan 01 的模块，加函数要同步它的公开面基线；而 `session.get` 是 SQLAlchemy 的原生 API，不需要包装） |
| P3-B8 | Minor | **`alert` 与 `notification` 的 `on_delete` 定成 `restrict` 是错的**：`alert` 是「哪个学生被标记过」的**审计记录**（RCT 的过程数据），`notification` 是**学生看到的消息历史**。`restrict` 意味着「没有子行时可以从 API 删掉」—— 而那会静默抹掉研究数据。 | **两个都改成 `forbid`（405）**。理由与 `stratification_result` 一样：**删它们的正确方式是重放（`_replay_cleanup` 按 `batch_id` 删），不是从 API 单点删。** ⚠️ 这一改让读写矩阵的三个计数变成：**可写 8 / 只读 15；`restrict` 11 / `forbid` 11 / `cascade` 1**（原为 12/10/1）。**那条遍历 `RESOURCES` 计数的测试要用新数** |

"""

patch(PLAN, [
    ("## Task 3: 泛型 CRUD 工厂 + 组织与身份 + 学期节点数据的只读/读写路由\n\n**Files:**",
     "## Task 3: 泛型 CRUD 工厂 + 组织与身份 + 学期节点数据的只读/读写路由\n" + PRE + "\n**Files:**",
     1, "P3-B 插入预检更正总表"),

    # P3-B1：23 行的 import 路径表（插在读写矩阵之前）
    ("**⚠️ S4 的裁定：23 个资源的读写矩阵逐个钉死**",
     "**⚠️ P3-B1 的裁定：23 个资源的 import 路径、自然键与 `JsonText` 列逐个钉死**（**11 个不在 `models` 的公有面上**，"
     "照 `models.X` 写会得到 11 个 `AttributeError`）：\n\n" + IMPORTS +
     "\n**⚠️ S4 的裁定：23 个资源的读写矩阵逐个钉死**",
     1, "P3-B1 插入 23 行 import 路径表"),

    # P3-B8：alert / notification 改 forbid
    ("| `alerts` | `/api/alerts` | ❌ | `restrict` | **由 `alert_stage` 生成、由 Task 7 的 `POST /api/alerts/{id}/handle` 处置**；开放 CRUD 写它会绕过 `window_key` 去重 |\n"
     "| `notifications` | `/api/notifications` | ❌ | `restrict` | **由 `InAppChannel` 生成**；「已读」走 Task 8 的 `POST /api/notifications/{id}/read` |",
     "| `alerts` | `/api/alerts` | ❌ | **`forbid`（P3-B8 更正，原为 `restrict`）** | **由 `alert_stage` 生成、由 Task 7 的 `POST /api/alerts/{id}/handle` 处置**；开放 CRUD 写它会绕过 `window_key` 去重。**改 `forbid` 的理由：它是「哪个学生被标记过」的审计记录（RCT 的过程数据），`restrict` 意味着「没有子行时可以从 API 删掉」，而那会静默抹掉研究数据** |\n"
     "| `notifications` | `/api/notifications` | ❌ | **`forbid`（P3-B8 更正，原为 `restrict`）** | **由 `InAppChannel` 生成**；「已读」走 Task 8 的 `POST /api/notifications/{id}/read`。**改 `forbid` 的理由同上：它是学生看到的消息历史** |",
     1, "P3-B8 alert/notification 改 forbid"),
    ("**合计：可写 8 个、只读 15 个；`on_delete` 是 `restrict` 12 个 / `forbid` 10 个 / `cascade` 1 个。**",
     "**合计：可写 8 个、只读 15 个；`on_delete` 是 `restrict` **11** 个 / `forbid` **11** 个 / `cascade` **1** 个**"
     "（**P3-B8 更正**：原为 12/10/1，`alert` 与 `notification` 从 `restrict` 挪到 `forbid`）。",
     1, "P3-B8 三个计数"),

    # P3-B2/B3/B4/B5：签名与决定
    ("**`on_delete: str = \"restrict\"`（取值 `\"restrict\"` / `\"cascade\"` / `\"forbid\"`；"
     "`\"forbid\"` → `DELETE` 返回 405，故不需要另一个 `deletable` 布尔）**、"
     "`list_exclude: tuple[str, ...] = ()`、`scope: ScopeFn | None = None`) -> APIRouter`",
     "**`on_delete: str = \"restrict\"`（取值 `\"restrict\"` / `\"cascade\"` / `\"forbid\"`；"
     "`\"forbid\"` → `DELETE` 返回 405，故不需要另一个 `deletable` 布尔）**、"
     "**`natural_key: tuple[str, ...] | None`（P3-B2：非空 → POST 走 `repo.upsert`、撞键 409；"
     "`None` → POST 走裸 `session.add`，结构上不可能撞键，故没有 409 这一档）**、"
     "**`list_exclude: tuple[str, ...] | None = None`（P3-B3：`None` 表示**自动探测**——"
     "`[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`；"
     "显式传元组则覆盖探测结果）**、`scope: ScopeFn | None = None`) -> APIRouter`",
     1, "P3-B2/B3 签名"),

    ("- **`PATCH` 的部分更新语义**：只改**请求体里出现的**键（用 `model_dump(exclude_unset=True)`）。",
     "- **⚠️ P3-B4：`on_delete=\"restrict\"` 要「点名是哪张子表挡住的」，而子表清单不在模型上。** "
     "实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。"
     "**`crud.py` 里写一个 `_child_tables(model) -> list[tuple[str, str]]`**（返回 `(子表名, 子表的FK列名)`），"
     "实现是遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`。"
     "**⚠️ 它必须排除 `ondelete` 为 `SET NULL` 或 `CASCADE` 的那些 FK** —— 实测 `notification.alert_id` 与 "
     "`notification.prescription_id` 都带 `ondelete=\"SET NULL\"`（Task 2 的顶回 3 加的），"
     "**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己会 SET NULL）。"
     "要有一条测试钉住这个排除。\n"
     "- **⚠️ P3-B5：5 张表的唯一约束是无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / "
     "`exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）→ "
     "**409 的消息里不得引用约束名**（它是 `None`，会渲染成字面 `\"None\"`），**引用列名**。"
     "要有一条测试断言 409 的 `message` 里含列名、**不含字面 `\"None\"`**（否则前端会把 `None` 显示给教师看）。\n"
     "- **⚠️ P3-B7：`repo.py` 只有 `upsert` 与 `delete_by_batch` 两个公开函数，没有 `get_or_404` 之类的读取助手。** "
     "read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。"
     "**不要为此给 `repo.py` 加新函数**（它是 Plan 01 的模块，加函数要同步它的公开面基线；"
     "而 `session.get` 是 SQLAlchemy 的原生 API，不需要包装）。\n"
     "- **`PATCH` 的部分更新语义**：只改**请求体里出现的**键（用 `model_dump(exclude_unset=True)`）。",
     1, "P3-B4/B5/B7 三条决定"),

    # P3-B6：deps 的常量出处
    ("- Consumes: Task 1 的 `get_db` / `Page` / `current_student` / `current_teacher` / `require_scope` / `errors` 的映射",
     "- Consumes: Task 1 的 `get_db` / `Page` / `current_student` / `current_teacher` / `require_scope` / `errors` 的映射"
     "（**⚠️ P3-B6 更正出处**：实测 `app/api/deps.py` 的公开面是 `Engine` / `Page` / `Student` / `current_student` / "
     "`current_teacher` / `get_db` / `require_scope`，**没有模块级大写常量**——`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` "
     "住在 **`app/main.py`**。**工厂不碰这两个常量**（它只拿 `Session`），故本条只是更正出处、不改设计）",
     1, "P3-B6 deps 的常量出处"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 3: 泛型 CRUD 工厂 + 23 个资源 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`8d8d3b3`（Task 2 结案，工作树干净）。**测试基线**：`845 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **38**。
**取证脚本**：`t3_probes/_preflight.py`（一份，Ruling 1 的口径；**全部运行时口径**：`Base.registry.mappers` 找模型类、`__table__.constraints` 找唯一约束、`isinstance(c.type, JsonText)` 找大 JSON 列、`__table__.foreign_keys` 找出向外键）。

#### Ruling 8 — 预检查出 1 Critical / 4 Important / 3 Minor，计划正文更正 6 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P3-B1** | **Critical** | **23 个资源里有 11 个的模型类不在 `app.db.models` 的公有导入面上**（Ruling 97）。实测：`exercise` / `prescription_template` / `prescription` / `weekly_adjustment` 住 `app.db.models.prescription`；`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 住 `app.db.models.feedback`。**计划 Task 3 的正文一个字都没提** —— 照字面写 `model=models.Prescription` 会得到 **11 个 `AttributeError`**。 | 计划正文插入一张 **23 行的表**，逐个给出「资源路径 / 表名 / 模型类 / **import 路径** / 列数 / 自然键 / `JsonText` 列」。**⚠️ 这是 Ruling 97 第三次没被传导**（前两次：Plan 02 的 P6-A8 与 Plan 03 Task 2 的 P3-A1）→ **补硬规矩 #102** |
| **P3-B2** | Important | **3 个资源没有唯一约束**：`course_section`、`fitness_test_batch`、`notification`。故 `test_create_with_a_duplicate_natural_key_is_409` **对它们写不出来**，`repo.upsert` 的 `key_fields` **也没有东西可填**。 | `build_crud_router` 加 **`natural_key: tuple[str, ...] | None`**：非空 → POST 走 `repo.upsert`（撞键 409）；`None` → POST 走**裸 `session.add`**（**结构上不可能撞键，故没有 409 这一档**）。**⚠️ 那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的写一条反向测试**（`test_a_resource_without_a_natural_key_never_returns_409`）—— 否则下一个人会以为 409 是普适的。**这是硬规矩 #92 的正面执行**（先论证破坏在结构上可达，再要求测试变红） |
| **P3-B3** | Important | **`JsonText` 列实测共 21 个、分布在 8 张表**（`interest_survey` 2、`derived_metrics` 3、`stratification_result` 1、`exercise` 1、`prescription` **5**、`mini_test` 1、`alert` 1、`weekly_class_report` **5**）。计划要求 `list_exclude` 由调用方**逐个手写** → 23 行里手抄 21 个列名，**抄漏一个就是一次全表 JSON 拉取**（Plan 02 Task 7 的性能回归正是「大 JSON 列 eager 加载」，`elapsed` 一度到 **115 s**）。 | **`list_exclude` 改成自动探测**：缺省 `None` = `[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`，保留显式覆盖参数。**理由：自动探测不会抄漏，而「多排除一列」的后果（read-one 里还能拿到）远轻于「少排除一列」（性能回归且没人看得见）。** 要有一条测试遍历 23 个资源、断言 **list 响应里一个 `JsonText` 列都不出现**、read-one 响应里全部出现 |
| **P3-B4** | Important | `on_delete="restrict"` 要「点名是哪张子表挡住的」，而**子表清单不在模型上**：实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。 | `crud.py` 里写 `_child_tables(model) -> list[tuple[str, str]]`（遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`）。**⚠️ 必须排除 `ondelete` 为 `SET NULL` / `CASCADE` 的 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`（Task 2 顶回 3 加的），**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己 SET NULL）。要有一条测试钉住这个排除 |
| **P3-B5** | Important | **5 张表的唯一约束是无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）。 | **409 的消息不得引用约束名**（它是 `None`，会渲染成字面 `"None"`）→ **引用列名**。要有一条测试断言 409 的 `message` 含列名、**不含字面 `"None"`**（否则前端会把 `None` 显示给教师看） |
| P3-B6 | Minor | `app/api/deps.py` 的公开面实测 = `Engine` / `Page` / `Student` / `current_student` / `current_teacher` / `get_db` / `require_scope`，**没有模块级大写常量**；`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 住在 **`app/main.py`**。`errors.py` = `error_response(status_code, code, message, detail=None, headers=None)` + `register_error_handlers(app)`。 | 计划正文的出处写错了，已更正。**工厂不碰这两个常量**（它只拿 `Session`），故不改设计 |
| P3-B7 | Minor | `repo.py` 的公开函数**只有两个**：`upsert(session, model, key_fields: Sequence[str], values: dict) -> Any` 与 `delete_by_batch(session, model, batch_id: int) -> int`。**没有 `get_or_404` 之类的读取助手。** | read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要为此给 `repo.py` 加新函数**（它是 Plan 01 的模块，加函数要同步公开面基线；而 `session.get` 是 SQLAlchemy 原生 API，不需要包装） |
| P3-B8 | Minor | **`alert` 与 `notification` 的 `on_delete` 定成 `restrict` 是错的**：`alert` 是「哪个学生被标记过」的**审计记录**（RCT 的过程数据），`notification` 是**学生看到的消息历史**。`restrict` 意味着「没有子行时可以从 API 删掉」—— 那会静默抹掉研究数据。 | **两个都改成 `forbid`（405）**，理由与 `stratification_result` 一样：**删它们的正确方式是重放（`_replay_cleanup` 按 `batch_id` 删），不是从 API 单点删。** ⚠️ 读写矩阵的三个计数随之变成 **可写 8 / 只读 15；`restrict` 11 / `forbid` 11 / `cascade` 1**（原为 12/10/1），**那条遍历 `RESOURCES` 计数的测试要用新数** |

**→ 补硬规矩 #102：一条纪律（如 Ruling 97 的「新表类不进 `models` 公有面」）一旦立下，就必须写进计划的 Global Constraints，而不是只写进当时那个 Task 的正文——因为后续每个 Task 的预检都要靠 Global Constraints 那一节来提醒控制者。** 依据：P3-B1 是 Ruling 97 **第三次**没被传导（前两次：Plan 02 的 P6-A8「`_replay_cleanup` 不能用 `models.Prescription`」、Plan 03 Task 2 的 P3-A1「`ops.py` 是星号导入」）。**三次都是控制者在写新 Task 时忘了它，而三次都要靠预检或实现者顶回来才发现。**
⚠️ **本计划的 Global Constraints 里其实已经写了 Ruling 97 那一条**（逐字有「**一律走子模块路径**：`from app.db.models.feedback import ClassSession`」）—— **而 Task 3 的正文没有把它落到 23 个资源上**。故 #102 的完整形态是：**写进 Global Constraints 只是第一步，每个 Task 的正文还要把它落成「本 Task 的每一处具体决定」；抽象的纪律不会自己应用到具体的清单上。**

**计划正文更正**：`_t3_preflight_patch.py`，**6 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-3-brief.md` → 派实现者。**⚠️ 本 Task 是 Plan 03 代码量最大的一个**（一个泛型工厂 + 23 个资源的声明 + 4 个 schema 模块），**控制者预期 1 轮 fix round。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
SENT = "Ruling 8 — 预检查出 1 Critical / 4 Important / 3 Minor"
assert SENT not in lt, f"{SENT!r} 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)}")
for k in ("Ruling 8", "硬规矩 #102", "P3-B1", "P3-B8", "app.db.models.feedback"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")
