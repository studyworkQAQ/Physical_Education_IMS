"""Plan 03 开工前的计划冲突扫描（SDD 技能要求的 Setup 步骤）：
逐对任务核「共享文件 / 共享接口」，逐个任务核「自己的正文是否自洽」。
输出是一张表 + 每条的裁定，写进账本；承重的 7 条同时更正计划正文。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
LEDGER = HERE / "progress.md"
edits = []

# ============ 1. 账本：首行改成技能要求的身份行 + 追加扫描表 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
nl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(nl)}")

OLD_FIRST = "# 实施计划 03：智慧反馈层 + 预警 + 全系统 CRUD API —— 执行账本"
NEW_FIRST = ("# SDD ledger — plan: Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md\n"
             "\n"
             "# 实施计划 03：智慧反馈层 + 预警 + 全系统 CRUD API —— 执行账本")
assert lt.startswith(OLD_FIRST), "账本首行不是预期的那一句"
lt = NEW_FIRST + lt[len(OLD_FIRST):]

SCAN = """

---

## 开工前的计划冲突扫描（SDD 技能的 Setup 步骤；控制者亲跑于 `5b4a10c`）

**方法**：技能要求「一张表，不是一个结论」——**每一对共享文件或接口的任务一行**（一方产出什么 vs 另一方消费什么、查出什么），**每个任务一行**（它自己的正文是否自洽：它指定的测试 vs 它指定的代码、它创建的文件 vs 它后面又改的文件）。

### A. 任务对之间的冲突（共享文件 / 共享接口）

| # | 任务对 | 共享的东西 | 查出什么 | 裁定 |
|---|---|---|---|---|
| **S1** | **T7 ↔ T8** | `app/api/routers/alerts.py` | **顺序反了**：T7 的 Files 写「**Modify** `alerts.py`（**Task 8 建**，这里只加『处理预警』端点）」，而 T8 的 Files 写「**Create** `api/routers/{dashboard,alerts}.py`。**T7 跑在 T8 之前**，它要改一个还不存在的文件 | **T7 创建 `alerts.py`**（含 `POST /api/alerts/{id}/handle`），**T8 只创建 `dashboard.py`**、并把 `alerts.py` 从它的 Create 清单里挪到 Modify（若它需要加端点）。**这是 Plan 02 控制者错误 #151 的同型**（说要改一个不存在的东西）——**已更正两处正文** |
| **S2** | **T2 ↔ T7** | `weekly_adjustment` 表 + `tests/db/test_models.py` | T7 要给 `weekly_adjustment` 加 `UniqueConstraint("prescription_id", "week", "reason", "source")`（防「同一周重复触发把系数连乘成 `0.8³ = 0.512`」），而**那张表是 Plan 02 Task 6 建的、`test_models.py` 的断言由 T2 统一改**。两个 Task 都要动同一张表的 schema 与同一份测试 | **把这条唯一约束挪进 T2**（它是 schema 变更，而 T2 是本计划唯一的建表 Task）。**理由**：schema 变更分散在两个 Task 会让「表数 18 → 25」与「约束清单」两个断言的改动点跨 Task，而 Plan 02 的 P6-A5 已经证明「一个数散落在多处」是最容易漏改的形状。**已更正两处正文** |
| **S3** | **T1 ↔ T2** | `tests/test_main.py` | T1 的 `test_health_reports_the_table_count` 断言 `tables == 18`（**字面写死**），而 T2 建成 7 张表后是 **25** → **T1 的测试会在 T2 当场变红**。计划正文只写了一句「Task 2 之后会变 25，那时同步改」，**但 T2 的 Files 清单里没有 `tests/test_main.py`** | **`tests/test_main.py` 加进 T2 的 Files（Modify）**。⚠️ 这正是硬规矩 #88 要防的形状（「列同步清单时，除了搜那个数本身，还要跑一次全量测试、把红掉的相等断言逐个收进来」）——**已更正 T2 的 Files 行** |
| **S4** | **T3 ↔ T5** | `POST /api/rpe-records`、`POST /api/training-logs`、`mini-tests` 的写入 | **同一张表两个写入口**：T3 的泛型 CRUD 会给 `rpe-records` / `training-logs` / `mini-tests` 各生成一个 `POST`，而 T5 又手写了 `POST /api/rpe-records`（带口令校验 + 服务端填 `submitted_at`）与 `POST /api/training-logs`（服务端算 `late`）与 `POST /api/mini-tests/batch`。**两条路由会撞**（FastAPI 按注册序取先匹配的，于是哪一个生效取决于 `include_router` 的顺序——一个没人看得见的耦合） | **`RESOURCES` 里这三个资源一律 `writable=False`（只读）**，写入**只走 T5 的特例端点**。理由：那三个特例端点各有一条**服务端才能算**的字段（`submitted_at` / `late` / 标准化得分），走泛型 CRUD 会让客户端能随便填——**而 `late` 是「完成率是 RCT 关键过程指标，必须严格」（spec §8.1 原文）的那一半**。**同理 `alerts` 也是 `writable=False`**（写入走 T7 的 handle 端点与 `alert_stage`）。**已更正 T3 的正文并给出 23 个资源的完整读写矩阵** |
| **S5** | **T6 ↔ T8** | `data/alert_rules.yaml` + 它的指纹常量 | T8 要往 `alert_rules.yaml` 加一个 `screen:` 段（大屏的两个阈值 + 班级周报「算法建议」的三个字符串与两个阈值），而 **T6 给这个文件加了一条 sha256 指纹测试**（照 `exercises.yaml` 的口径）→ **T8 改文件就必须同步那个常量**，而 T8 的正文一个字没提 | **T8 的 Files 加 `backend/data/alert_rules.yaml` 与 `backend/tests/test_refdata_alerts.py`（指纹常量）**，并按 Plan 02 Task 9 的 P9-A3 六步程序做（先算新指纹 → 改文件 → **用 `read_bytes()` 复核 CRLF 仍为 0** → 改常量 → 跑指纹测试 → 另两个指纹必须逐字不变）。**已更正 T8 的正文** |
| **S6** | **T1 ↔ T6** | `tests/architecture/test_layering.py` / `test_domain_purity.py` | T1 给守卫**加 `api` 这一层**（扫描面 35 → 43 左右），T6 给 domain **加一个模块**（`alerts.py`）。两个 Task 都改这两份守卫，且**都会动同一批下界断言**（`>=5` / `>=8` / `>=16` / `len(real_py) >=40`） | **不算冲突，但要写明口径**：T1 加层时把下界一次性抬到位（含 `api`），T6 只加一个 domain 模块、**不再动下界**（domain 16 → 17 仍满足 T1 抬过的下界）。**T6 的正文已加一句提醒**，免得它以为「扫描面涨了要说明」是要改断言 |
| **S7** | **T3 ↔ T4** | `app/api/schemas/prescription.py` | T3 的 Files 写 **Create** 它，T4 的 Files 写「Create …（**补特例模型**）」—— **T4 是 Modify 不是 Create** | **T4 的 Files 改成 Modify**。措辞问题，不影响行为，但「Create 一个已存在的文件」会让实现者犹豫要不要覆盖 |
| **S8** | **T7 ↔ T8** | `app/pipeline/daily.py` | T7 改它（阶段序列插 `Alert` + 写 `alert_count` + `_replay_cleanup` 加 `Alert`），T8 也改它（插 `Report` 阶段 + 周日判据 + `_replay_cleanup` 加 `WeeklyClassReport`）。**顺序 T7 → T8，不冲突**，但 T8 的实现者要看到 T7 改后的形状 | **不算冲突**（严格串行）。**T8 的正文已加一句**：`_replay_cleanup` 的清单在 T7 之后是 7 张（含 `Alert`），T8 加 `WeeklyClassReport` 后是 8 张，**且子表先删的纪律仍适用**（`notification.alert_id` 带 `ondelete="SET NULL"`，故 `notification` 不进清单、也不会因删 `alert` 而炸 FK） |

### B. 每个任务的自洽性（它指定的测试 vs 它指定的代码）

| 任务 | 自洽吗 | 查出什么 |
|---|---|---|
| T1 | ⚠️ 一处 | `test_health_reports_the_table_count` 断言 `tables == 18`，**而 T1 自己不建表**——它断言的是 Plan 02 的终态。这条今天为真，但它是**一个会在下一个 Task 变红的字面断言**，而 T1 的正文没说自己造了这个债 → 见 **S3** |
| T2 | ⚠️ 两处 | ① Files 缺 `tests/test_main.py`（S3）；② `weekly_adjustment` 的唯一约束被推给 T7（S2）。**其余自洽**：7 张表的字段清单与 spec §4.5/§4.6/§4.7 逐格对得上，`batch_id` 的「4 张带 / 3 张不带」与 `_BATCH_OWNED_TABLES` 的 5 → 9 一致 |
| T3 | ⚠️ 两处 | ① `RESOURCES` 的 23 个资源**没有逐个声明 `writable` / `on_delete`**（正文只给了三档 `on_delete` 的语义与「只读资源是哪四个」，而 S4 又要把三个反馈资源与 `alerts` 也变成只读）→ **已补一张 23 行的完整读写矩阵**；② `schemas/prescription.py` 与 T4 的归属（S7） |
| T4 | ✅ | 六条「必须传导的 Plan 02 结论」逐条都能在 Plan 02 的账本里找到出处（P8-A3 / P8-A1 / P5-A3 / `OverrideRecord.reason` / `old_value`–`new_value` 是 `str` / P6-A2）。**`previous_had_overrides` 那一列实测存在**（Plan 02 Task 7 fr1 加的） |
| T5 | ✅ | 打卡 `late` 的三个模糊点各有一条决定与一条边界测试；完成率的分子分母口径明确（分母 = `Template.weekly_frequency`，**无处方返回 `null` 不是 `0`**）；`elapsed_seconds` 可为 `null`；`rpe_token` 用 `secrets` 而不是 `random`（并说明了理由） |
| T6 | ✅ | 5 条规则的判据逐条引了 spec §8.2 的原文与那张「四项均待确认」的口径表；`window_key` 的五种取值逐个给了算式；`GREEN_MASTERY` 的 `improve_pct` **明确写了它由谁消费**（Task 7 算 `mini_test_improved` 时），不会被当成死配置 |
| T7 | ⚠️ 一处 | Files 说 Modify `alerts.py` 而它还不存在（S1） |
| T8 | ⚠️ 一处 | 要改 `alert_rules.yaml` 却没说要同步指纹常量（S5） |
| T9 | ✅ | GC14 的三条边界都写明了（不改既有 13 例 / `muscle_low_p10` 仍不可达且**刻意留下并写明** / 例数 13 → 14 会让所有硬编码 13 的地方过期，按硬规矩 #88 先跑全量再收清单）；端到端冒烟的 8 步逐条给了断言点 |

### C. 裁定汇总

**8 条任务对冲突里，4 条是真冲突（S1/S2/S3/S4）、2 条是措辞（S5 的 Files 缺项算半条真冲突、S7）、2 条只是需要写明口径（S6/S8）。全部 8 条已更正计划正文。**

**⚠️ 元观察**：这 8 条里 **S1 与 S3 是同一族**——「一个 Task 说要改另一个 Task 才创建的东西」，而 Plan 02 的控制者错误 #151（派单声称「控制者已经改了 4 处」而实测 0/4 在树上）与 P6-A1（Task 6 的 Step 6 要在 Task 7 才建的管道上跑集成测试）也是这一族。**这是第 3 次。**
**→ 补硬规矩 #96：写「Modify X」之前，先确认 X 在那一刻已经存在；若它由后面的 Task 创建，就把创建挪到前面那个 Task，或把修改挪到后面。判据是 `git ls-files` 或本计划前序 Task 的 Create 清单，不是记忆。** 依据：S1 / S3 / Plan 02 的 #151 与 P6-A1。

**⚠️ 另一族**：S2 与 S5 都是「**一个改动会让另一个 Task 钉住的字面值过期**」（表的唯一约束、YAML 的指纹）。Plan 02 的 P6-A5（表数散落在六处）与 P9-A3（改 `exercises.yaml` 要同步指纹常量）是同一族。
**→ 补硬规矩 #97：任何「新增/修改一个被字面断言钉住的东西」的 Task，它的 Files 清单必须包含那份断言所在的文件——即使那个 Task 一行代码都不改那份文件。** 依据：S2 / S3 / S5 / P6-A5 / P9-A3。

**扫描后计划的 Files 清单变化**：T2 +2 个文件（`tests/test_main.py`、`weekly_adjustment` 的约束）、T4 的 Create → Modify、T7 +1 个 Create（`api/routers/alerts.py`）、T8 -1 个 Create（`alerts.py` 改 Modify）+2 个 Modify（`alert_rules.yaml`、`test_refdata_alerts.py`）。

**下一步**：抽 `task-1-brief.md` → 派实现者。**⚠️ 本 harness 的 Task 工具没有 model 参数**，故技能「Model Selection」那一节要求的「显式指定模型」在这里做不到——记录在案，不假装做了。
"""

if nl != "\n":
    SCAN = SCAN.replace("\r\n", "\n").replace("\n", nl)
assert "开工前的计划冲突扫描" not in lt
lt = lt.rstrip("\r\n") + SCAN
LEDGER.write_bytes(lt.encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
print(f"  首行 = {c.split(chr(10))[0][:80]!r}")
for k in ("硬规矩 #96", "硬规矩 #97", "S1", "S8"):
    print(f"  {k}: {c.count(k)}")


# ============ 2. 计划正文：更正承重的 7 条 ============
raw = PLAN.read_bytes()
t = raw.decode("utf-8")
pnl = "\r\n" if "\r\n" in t else "\n"
print(f"\n[plan before] bytes={len(raw)} lines={t.count(pnl)} nl={'CRLF' if pnl != chr(10) else 'LF'}")


def sub(old, new, count, label):
    global t
    if pnl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", pnl)
        new = new.replace("\r\n", "\n").replace("\n", pnl)
    n = t.count(old)
    assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
    t = t.replace(old, new)
    edits.append((label, n))


# --- S3：T2 的 Files 补 tests/test_main.py；S2：weekly_adjustment 的约束挪进 T2 ---
sub("Modify `backend/app/db/models/feedback.py`（475 B 空壳 → 4 张表）、`backend/app/db/models/ops.py`（+3 张表）、"
    "`backend/app/db/models/__init__.py`（导入子模块，**不改 `__all__`**）、`backend/tests/db/test_models.py`、"
    "`backend/tests/seed/test_generate.py`；Create `backend/app/demo_data.py`、`backend/tests/test_demo_data.py`",
    "Modify `backend/app/db/models/feedback.py`（475 B 空壳 → 4 张表）、`backend/app/db/models/ops.py`（+3 张表）、"
    "`backend/app/db/models/__init__.py`（导入子模块，**不改 `__all__`**）、`backend/tests/db/test_models.py`、"
    "`backend/tests/seed/test_generate.py`、"
    "**`backend/app/db/models/prescription.py`（给 `weekly_adjustment` 加一条唯一约束，见 S2 的裁定）**、"
    "**`backend/tests/test_main.py`（Task 1 那条 `tables == 18` 会在本 Task 变红，见 S3 的裁定）**；"
    "Create `backend/app/demo_data.py`、`backend/tests/test_demo_data.py`",
    1, "S2/S3 T2 的 Files 行")

sub("- **`batch_id`**：`class_session` / `training_log` / `alert` / `weekly_class_report` 四张带 `batch_id`",
    "- **⚠️ S2 的裁定：`weekly_adjustment` 的那条唯一约束在本 Task 加，不推给 Task 7。** "
    "Task 7 需要 `UniqueConstraint(\"prescription_id\", \"week\", \"reason\", \"source\")` 来防"
    "「同一周重复触发把系数连乘成 `0.8³ = 0.512`」（Review Focus 第 3 条），而那张表是 **Plan 02 Task 6 建的**。"
    "**schema 变更一律归本 Task**（本计划唯一的建表 Task），理由见账本 S2：schema 变更分散在两个 Task 会让"
    "「表数」与「约束清单」两个断言的改动点跨 Task，而 Plan 02 的 P6-A5 已经证明「一个数散落在多处」是最容易漏改的形状。"
    "⚠️ 加完要跑一次全量、把红掉的相等断言逐个收进来（硬规矩 #88）。\n"
    "- **`batch_id`**：`class_session` / `training_log` / `alert` / `weekly_class_report` 四张带 `batch_id`",
    1, "S2 约束挪进 T2")

# --- S4：T3 的 23 个资源逐个声明读写 ---
sub("⚠️ **23 个资源的名字与路径逐字钉死**（Plan 04 的前端要照着它写）：`semesters` / `teachers` / `students` / "
    "`course-sections` / `enrollments` / `fitness-test-batches` / `fitness-test-results` / `body-compositions` / "
    "`interest-surveys` / `percentile-snapshots` / `derived-metrics` / `stratification-results` / `exercises` / "
    "`prescription-templates` / `prescriptions` / `weekly-adjustments` / `class-sessions` / `rpe-records` / "
    "`training-logs` / `mini-tests` / `alerts` / `notifications` / `weekly-class-reports`。**全部挂在 `/api/` 下**"
    "（如 `/api/course-sections`）。**连字符不是下划线**（URL 惯例），但 schema 的字段名保持**下划线**"
    "（与 DB 列名一致）—— ⚠️ 这个对照要写进 `crud.py` 的 docstring。",
    "⚠️ **23 个资源的名字与路径逐字钉死**（Plan 04 的前端要照着它写），**全部挂在 `/api/` 下**（如 `/api/course-sections`）。"
    "**连字符不是下划线**（URL 惯例），但 schema 的字段名保持**下划线**（与 DB 列名一致）—— "
    "⚠️ 这个对照要写进 `crud.py` 的 docstring。\n\n"
    "**⚠️ S4 的裁定：23 个资源的读写矩阵逐个钉死**（原正文只给了「只读资源是哪四个」，"
    "而同一个 `POST` 路径会被泛型 CRUD 与 Task 5/7 的特例端点**同时注册**——FastAPI 按 `include_router` 的顺序取先匹配的，"
    "于是哪一个生效变成一个没人看得见的耦合）：\n\n"
    "| 资源 | 路径 | `writable` | `on_delete` | 为什么 |\n"
    "|---|---|---|---|---|\n"
    "| `semesters` | `/api/semesters` | ✅ | `forbid` | 全库的时间轴锚点，删它没有安全语义 |\n"
    "| `teachers` | `/api/teachers` | ✅ | `restrict` | 有 `course_section.teacher_id` 子行 |\n"
    "| `students` | `/api/students` | ✅ | `restrict` | 有大量子行；**删一个学生要走学籍流程，不是 API 单点删** |\n"
    "| `course-sections` | `/api/course-sections` | ✅ | `restrict` | 有 `enrollment` 子行 |\n"
    "| `enrollments` | `/api/enrollments` | ✅ | `restrict` | 关联行，无子行但删它会让名单悄悄少人 |\n"
    "| `fitness-test-batches` | `/api/fitness-test-batches` | ✅ | `restrict` | 有 `fitness_test_result` 子行 |\n"
    "| `fitness-test-results` | `/api/fitness-test-results` | ❌ | `forbid` | **乐跑投影 + 批处理输入**，改它等于改原始数据 |\n"
    "| `body-compositions` | `/api/body-compositions` | ✅ | `restrict` | InBody 是人工录入的，教师要能改错 |\n"
    "| `interest-surveys` | `/api/interest-surveys` | ✅ | `restrict` | 同上 |\n"
    "| `percentile-snapshots` | `/api/percentile-snapshots` | ❌ | `forbid` | **批处理产物**，删它的正确方式是重放 |\n"
    "| `derived-metrics` | `/api/derived-metrics` | ❌ | `forbid` | 同上 |\n"
    "| `stratification-results` | `/api/stratification-results` | ❌ | `forbid` | 同上；**spec §4.3 的可追溯性核心** |\n"
    "| `exercises` | `/api/exercises` | ❌ | `forbid` | **参考数据**：`exercises.yaml` 是唯一所有者，表是投影（见上面那条决定） |\n"
    "| `prescription-templates` | `/api/prescription-templates` | ❌ | `forbid` | 同上（18 套 YAML 是唯一所有者） |\n"
    "| `prescriptions` | `/api/prescriptions` | ❌ | `restrict` | **教师覆盖与状态变更走 Task 4 的特例端点**；直接 PATCH 整行会让 `training_package` 与 `assembly_snapshot` 失去一致性 |\n"
    "| `weekly-adjustments` | `/api/weekly-adjustments` | ❌ | `restrict` | **`auto` 来源由 Task 7 的 `alert_stage` 写、`teacher` 来源由 Task 4 的覆盖端点写**；开放 CRUD 写它会绕过 `WeeklyFactor` 的 `(0, 2]` 校验（Plan 02 留给 Plan 03 的第 4 条） |\n"
    "| `class-sessions` | `/api/class-sessions` | ✅ | **`cascade`** | 教师建课次、取消课次；**课次取消则 `rpe_record` 无意义**（`cascade` 两处之一） |\n"
    "| `rpe-records` | `/api/rpe-records` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/rpe-records`**（要校验 `rpe_token`、服务端填 `submitted_at`） |\n"
    "| `training-logs` | `/api/training-logs` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/training-logs`**（`late` 必须服务端算——它是「完成率是 RCT 关键过程指标，必须严格」的那一半） |\n"
    "| `mini-tests` | `/api/mini-tests` | ❌ | `restrict` | **写入只走 Task 5 的 `POST /api/mini-tests/batch`**（标准化得分要班内百分位反查，客户端算不出来） |\n"
    "| `alerts` | `/api/alerts` | ❌ | `restrict` | **由 `alert_stage` 生成、由 Task 7 的 `POST /api/alerts/{id}/handle` 处置**；开放 CRUD 写它会绕过 `window_key` 去重 |\n"
    "| `notifications` | `/api/notifications` | ❌ | `restrict` | **由 `InAppChannel` 生成**；「已读」走 Task 8 的 `POST /api/notifications/{id}/read` |\n"
    "| `weekly-class-reports` | `/api/weekly-class-reports` | ❌ | `forbid` | **批处理产物**（Task 8） |\n\n"
    "**合计：可写 8 个、只读 15 个；`on_delete` 是 `restrict` 12 个 / `forbid` 10 个 / `cascade` 1 个。**"
    "⚠️ **另一处 `cascade`**：`prescriptions` → `weekly_adjustment`（处方作废则微调记录随之作废），"
    "但 `prescriptions` 的 `on_delete` 是 `restrict`（不许从 API 删处方）→ **那个 `cascade` 由 Task 4 的"
    "「处方被替换」路径内部使用，不经过 `DELETE` 端点**。故 `build_crud_router` 的 `on_delete=\"cascade\"` "
    "**只有 `class-sessions` 一个用户**。\n"
    "⚠️ **这三个数字（8 / 15、12 / 10 / 1）要有一条测试钉住**（遍历 `RESOURCES` 计数），"
    "否则加第 24 个资源时会静默改变比例而没人知道。**数字自己数、不要照抄本行**（硬规矩 #44/#89）。",
    1, "S4 23 个资源的读写矩阵")

# --- S4 连带：只读资源那一句要与矩阵一致 ---
sub("- **只读资源**：`percentile_snapshot` / `derived_metrics` / `stratification_result` / `weekly_class_report` "
    "四个是 `writable=False, deletable=False`（批处理产物）。",
    "- **只读资源**：**15 个**（见下面 S4 的读写矩阵）——`percentile_snapshot` / `derived_metrics` / "
    "`stratification_result` / `weekly_class_report` 四个是批处理产物，`fitness_test_result` 是乐跑投影，"
    "`exercise` / `prescription_template` 是参考数据的投影，"
    "`prescription` / `weekly_adjustment` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` "
    "七个**有专门的特例写入口**（Task 4/5/7/8），故一律 `writable=False`。",
    1, "S4 只读资源那一句")

# --- S1：T7 创建 alerts.py，T8 改它 ---
sub("**Files:** Create `backend/app/pipeline/alert_stage.py`、`backend/app/notify.py`、"
    "`backend/tests/pipeline/test_alert_stage.py`、`backend/tests/test_notify.py`；"
    "Modify `backend/app/api/routers/alerts.py`（Task 8 建，这里只加「处理预警」端点）",
    "**Files:** Create `backend/app/pipeline/alert_stage.py`、`backend/app/notify.py`、"
    "**`backend/app/api/routers/alerts.py`（⚠️ S1 的裁定：本 Task 创建它，不是 Task 8——"
    "原正文写「Task 8 建，这里只加端点」，而本 Task 跑在 Task 8 之前，改一个还不存在的文件）**、"
    "`backend/tests/pipeline/test_alert_stage.py`、`backend/tests/test_notify.py`、`backend/tests/api/test_alerts_api.py`；"
    "Modify `backend/app/api/routers/__init__.py`（include 新路由）、`backend/app/pipeline/daily.py`"
    "（阶段序列插 `Alert` + 写 `alert_count` + `_replay_cleanup` 加 `Alert`）、"
    "**`backend/app/db/models/prescription.py`（若 Task 2 漏了那条唯一约束才动；正常情况下 Task 2 已加好，见 S2）**",
    1, "S1 T7 的 Files")
sub("**Files:** Create `backend/app/pipeline/report_stage.py`、`backend/app/api/routers/{dashboard,alerts}.py`、"
    "`backend/tests/pipeline/test_report_stage.py`、`backend/tests/api/test_dashboard.py`",
    "**Files:** Create `backend/app/pipeline/report_stage.py`、`backend/app/api/routers/dashboard.py`、"
    "`backend/tests/pipeline/test_report_stage.py`、`backend/tests/api/test_dashboard.py`；"
    "Modify **`backend/app/api/routers/alerts.py`（⚠️ S1：它由 Task 7 创建，本 Task 只加端点）**、"
    "`backend/app/api/routers/__init__.py`、`backend/app/pipeline/daily.py`（插 `Report` 阶段 + 周日判据 + "
    "`_replay_cleanup` 加 `WeeklyClassReport`）、"
    "**`backend/data/alert_rules.yaml` 与 `backend/tests/test_refdata_alerts.py`（⚠️ S5：加 `screen:` 段会改掉 "
    "Task 6 钉的 sha256 指纹，常量要同步，按 Plan 02 的 P9-A3 六步程序做）**",
    1, "S1/S5 T8 的 Files")

# --- S6：T6 不再动守卫下界 ---
sub("**Files:** Create `backend/data/alert_rules.yaml`、`backend/app/domain/alerts.py`、`backend/app/refdata_alerts.py`、"
    "`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`；"
    "Modify `backend/tests/architecture/*`（domain 多一个模块）",
    "**Files:** Create `backend/data/alert_rules.yaml`、`backend/app/domain/alerts.py`、`backend/app/refdata_alerts.py`、"
    "`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`；"
    "Modify `backend/tests/architecture/*`（domain 多一个模块 → 扫描面 +1）"
    "**⚠️ S6 的裁定：下界断言由 Task 1 一次性抬到位（含 `api` 那一层），本 Task 只加一个 domain 模块、"
    "不再动下界**（domain 16 → 17 仍满足 Task 1 抬过的下界）。故本 Task 的「扫描面涨了要说明」只是**报告里写一句**，"
    "不是改断言。",
    1, "S6 T6 的守卫口径")

# --- S7：T4 的 Create → Modify ---
sub("**Files:** Create `backend/app/api/routers/prescription.py`、`backend/app/api/schemas/prescription.py`（补特例模型）、"
    "`backend/tests/api/test_prescription_api.py`",
    "**Files:** Create `backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`；"
    "Modify **`backend/app/api/schemas/prescription.py`（⚠️ S7：它由 Task 3 创建，本 Task 只补特例模型，"
    "原正文写「Create」会让人犹豫要不要覆盖）**、`backend/app/api/routers/__init__.py`",
    1, "S7 T4 的 Files")

# --- S8：T8 的 _replay_cleanup 口径 ---
sub("- **报告生成的时机**：spec §8.5 逐字「**每周日**批处理生成」。",
    "- **⚠️ S8 的口径（`_replay_cleanup` 在本 Task 之后的形状）**：Task 7 已把它从 5 张扩到 **7 张**"
    "（加 `Alert`；`prescription` 与 `weekly_adjustment` 是 Plan 02 Task 7 加的），本 Task 加 `WeeklyClassReport` 后是 **8 张**。"
    "**子表先删的纪律仍适用**（Plan 02 的 P7-A4：SQLite 跑在 `PRAGMA foreign_keys=ON` 下，先删父表会当场 FK 违例）；"
    "而 **`notification` 不进这个清单**（它不带 `batch_id`，是用户实时写入的），"
    "它的 `alert_id` 带 `ondelete=\"SET NULL\"`（Task 2 已定），故删 `alert` 不会让通知行炸 FK。\n"
    "- **报告生成的时机**：spec §8.5 逐字「**每周日**批处理生成」。",
    1, "S8 T8 的 _replay_cleanup 口径")

out = t.encode("utf-8")
PLAN.write_bytes(out)
c2 = PLAN.read_bytes().decode("utf-8")
print(f"[plan after]  bytes={len(out)} lines={c2.count(pnl)}")
for lab, n in edits:
    print(f"  {n}x  {lab}")
print("\n--- 反向复核：8 条是否真的落地 ---")
for good in ("S1 的裁定", "S2 的裁定", "S3 的裁定", "S4 的裁定", "S5：加 `screen:`", "S6 的裁定", "S7：它由 Task 3 创建",
             "S8 的口径", "可写 8 个、只读 15 个"):
    print(f"  {good!r:30s} 命中 {c2.count(good)}   <- 应 >= 1")
for bad in ("Task 8 建，这里只加「处理预警」端点", "四个是 `writable=False, deletable=False`"):
    print(f"  {bad!r:30s} 命中 {c2.count(bad)}   <- 应为 0")
