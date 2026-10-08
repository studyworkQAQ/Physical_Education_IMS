"""Task 6 预检更正：12 处（P6-A1..A12），逐条 assert 命中次数（硬规矩 #79）。

取证：t6_probes/_t6_probe1.py 与 _t6_probe2.py（控制者本机实跑，基线 55874a6 / 679 passed）
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
raw = PLAN.read_bytes()
text = raw.decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
print(f"[in] bytes={len(raw)} lines={text.count(nl)}")
edits = []


def sub(old, new, count, label):
    global text
    if nl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", nl)
        new = new.replace("\r\n", "\n").replace("\n", nl)
    n = text.count(old)
    assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
    text = text.replace(old, new)
    edits.append((label, n))


# ============ 0. 插入预检更正总表 ============
PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `55874a6`，取证脚本 `t6_probes/_t6_probe{1,2}.py`）

**测试基线**：`679 passed`；`app/domain/` **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**；**16 张表**；`__all__` **43**；扫描面 **32**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P6-A1** | **Critical** | **Step 6 的两条集成测试在本 Task 写不出来。** 它们要求「生成 → 加覆盖 → 触发**重生成**」与「同一天跑两次**管道**」，而 `app/pipeline/prescription_stage.py` 是 **Task 7** 才建的；Task 6 只建两张表 + `triggers.py`（**纯函数**，不落库）。实测 `app/pipeline/` 下今天**没有**任何处方生成阶段。 | **Step 6 整体移到 Task 7**（那里才有管道可跑）。Task 6 只保留「`evaluate_triggers` 对同一输入是确定的」那条**纯函数**测试。⚠️ 与 Ruling 103 同型：派单让实现者做一件当场做不到的事 |
| **P6-A2** | **Critical** | Step 6 要求「在 `assembly_snapshot` 里加 `"previous_had_overrides": true`」，**与 Task 5 刚钉死的键集契约直接冲突**：`assemble` 产出**恰好 12 个键**（`test_assembly_snapshot_keys_are_exactly_the_pinned_set`，多一键少一键都红）、`apply_safety` **追加至多 3 个**（`test_safety_appends_at_most_three_snapshot_keys`）。加第 16 个键会让**两条守卫变红**。 | **不往 `assembly_snapshot` 加键。** 改成 `prescription` 表**自己的一个列** `previous_had_overrides: Mapped[bool]`（`Boolean, nullable=False, default=False`）。理由：它是**关于上一张处方的事实**，不属于「这一张处方的装配输入输出」，放进 `assembly_snapshot` 是**范畴错误**（那一列的契约是「离线复算本张处方」） |
| **P6-A3** | **Critical** | **`microcycle_weeks` 无处可取。** 实测 `prescription_template` 的 **10 列**是 `id / layer / weakness / body_comp / template_ref / version / review_status / reviewer / reviewed_at / reachable`——**没有 `microcycle_weeks`，也没有 `weekly_frequency`**。而触发 3 的判据与 `valid_to` 的算式都要它，且计划明写「从**上一张处方的模板**取，不硬编码 4」。 | **给 `prescription` 表加一列 `microcycle_weeks: Mapped[int]`**（生成时从 `Template.microcycle_weeks` 快照下来）。理由：处方要能**离线复算** `valid_to` 与触发 3，而模板将来会改版（`version` 会变），把周期快照在处方行上才符合 spec §4.3 的可追溯性。**⚠️ 刻意不给 `prescription_template` 加列**——教师端要展示模板周期是 **Plan 03 的 CRUD 层**的活，届时再加；今天加会让 Task 6 回头改 Task 3 已结案的表 + `sync_templates` + `_MODELS_PUBLIC_BASELINE` |
| P6-A4 | Important | 分区穷尽守卫的实测口径（`tests/seed/test_generate.py`）：`assert partitioned == actual`（**新表必须归进三个分区之一，否则这条红**）、三分区互不相交、`assert REFERENCE_TABLES == ("exercise", "prescription_template")`（**字面钉住，不动**）、`for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0`（**seed 阶段必须 0 行**）。且该文件注释里**已经预告过这个决定**：「⚠️ 那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区」。 | `prescription` 与 `weekly_adjustment` **都归 `DATA_TABLES`**（9 → **11**）。这与「seed 阶段 0 行」的断言天然相容（处方是管道产物，不由 `seed_database` 写）。**且必须同时改掉那段预告注释**——「届时」到了 |
| P6-A5 | Important | `test_models.py` 要改的**远不止「表数 16 → 18」**。实测命中点：① 函数名 `test_all_sixteen_tables_created`；② **两处** `assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"`（**中文消息里也有「16 张表」**）；③ `assert len(Base.metadata.tables) == 16`；④ 一段注释里**逐字印着 grep 命令**与「**3** 处本段的散文」的计数；⑤ 另一处注释引用了那个**函数名**；⑥ `assert len(_MODELS_PUBLIC_BASELINE) == 33`。 | 六处**全部列出**（见下方 Step 1 的清单）。`_MODELS_PUBLIC_BASELINE` **33 → 35**（加 `Prescription` 与 `WeeklyAdjustment` 两个类名）。⚠️ `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**不动**——两张表进已有的 `models/prescription.py`，不新增子模块 |
| P6-A6 | Important | 实测 `Layer` 成员 = `[('RED','red'), ('YELLOW','yellow'), ('GREEN','green'), ('INSUFFICIENT','insufficient_data')]`，`INSUFFICIENT = "insufficient_data"` 住在 `app/domain/stratify.py`。 | `triggers.py` **不得硬编码 `"insufficient_data"` 字面串**，要用 `Layer.INSUFFICIENT.value`（单一所有者，Global Constraint #3），并配一条漂移测试。⚠️ import 走**绝对导入** `from app.domain.stratify import Layer`（与 `match.py` 同口径；同包兄弟才走 level 1 相对导入） |
| P6-A7 | Important | 逻辑 id 的列名**两套**：`prescription_template` 的列叫 **`template_ref`**（Task 3 按 spec §4.4 勘误定的），而计划 Task 6 写 `prescription` 表的列叫 `template_id`。 | DB 列统一用 **`template_ref`**（与 `prescription_template.template_ref` 同名，FK 关系一目了然）。**domain 侧不动**：`Template.template_id` 与 `LastPrescription.template_id` 保持 `template_id`（spec §7.2 的字面）。**⚠️ 这个「domain 叫 `template_id`、DB 列叫 `template_ref`」的对照必须写进 docstring**，否则 Task 7 的实现者会以为是两个东西 |
| P6-A8 | Important | `weekly_adjustment` **没有 `batch_id` 列**，而计划 Task 7 写着「`_replay_cleanup` 的清单要加上 `prescription` 与 `weekly_adjustment`（**按 `batch_id` 删**）」。实测 `repo.delete_by_batch(session, model, batch_id)` 要求模型有 `batch_id`。 | **Task 6 就给 `weekly_adjustment` 加 `batch_id` 列**（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构）。理由：① `delete_by_batch` 是既有的、被测试覆盖的路径，改用级联删要新写一段逻辑 + 新配测试；② 「按批删」是本仓一致的幂等手段；③ 一列的成本远低于一段新逻辑。⚠️ **必须在 Task 6 就加**——Task 7 才发现就要回头改一张已结案的表（硬规矩 #11 的教训） |
| P6-A9 | Minor | `prescription.status` 的 CHECK 值域 `{active, replaced, archived, needs_review}` 4 个值，最长 `needs_review` = **12** 字符，`String(16)` 够。`weekly_adjustment.source` 值域 `{auto, teacher}`，最长 `teacher` = **7**，`String(8)` 够。 | 无需更正，**但两个 CHECK 都要用 `_shared.py` 的既有 `_in_domain(column, allowed, name)` helper**（不要手写 `CheckConstraint`），且值域集合要作为**类常量**声明（与 `Exercise.IMPACT_LEVELS` / `PrescriptionTemplate.LAYERS` 同口径） |
| P6-A10 | Minor | 实测 `daily_sync_run` **19 列**，`prescription_count` 与 `alert_count` **都已存在**（Plan 01 就建好了）。 | 无需更正（计划 Task 7 的说法对）。**Task 6 不写这两列的值**，Task 7 才写 `prescription_count` |
| P6-A11 | Minor | 计划的 `**Files:**` 行只列了 `triggers.py` / 测试 / `models/prescription.py` / `test_models.py`，**漏了 `tests/seed/test_generate.py`** —— 而 P6-A4 那条分区穷尽守卫**一定会红**。 | `**Files:**` 行补上 `backend/tests/seed/test_generate.py`（`DATA_TABLES` 9 → 11 + 改那段预告注释） |
| P6-A12 | — | **控制者自查**：本 Task 的 12 条里 **P6-A1 / P6-A2 两条是「Task 5 结案改变了 Task 6 的前提」而控制者没有传导**——P6-A2 撞的正是 Task 5 fix round 1 刚钉死的键集契约，而那条契约是**控制者自己在 Ruling 148 里裁定的**。 | → **补硬规矩 #86：每个 Task 结案时，必须扫一遍后续所有 Task 的正文，找出「被本次结案改变的前提」并当场更正。** 依据：这与硬规矩 #75（P2-A1 的裁定没传导到 Task 3，同一缺陷原封不动重演）是**同一根因的第 2 次**，而 #75 只覆盖了「预检裁定」这一半，没覆盖「结案产出」 |

"""
sub("## Task 6: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）\n\n**Files:**",
    "## Task 6: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）\n"
    + PRE + "\n**Files:**",
    1, "P6 插入预检更正总表")

# ============ 1. Files 行（P6-A11） ============
sub("**Files:** Create `backend/app/domain/prescription/triggers.py`、`backend/tests/domain/test_prescription_triggers.py`；"
    "Modify `backend/app/db/models/prescription.py`（加两张表）、`backend/tests/db/test_models.py`（表数 16 → 18）",
    "**Files:** Create `backend/app/domain/prescription/triggers.py`、`backend/tests/domain/test_prescription_triggers.py`；"
    "Modify `backend/app/db/models/prescription.py`（加两张表）、`backend/app/db/models/__init__.py`（重导出两个新类）、"
    "`backend/tests/db/test_models.py`（**六处**，见 P6-A5 的清单）、"
    "**`backend/tests/seed/test_generate.py`（`DATA_TABLES` 9 → 11 + 改那段预告注释，P6-A4 / P6-A11）**",
    1, "P6-A11 Files 行")

# ============ 2. 触发 1 的字面串（P6-A6） ============
sub("| 1 | 学生首次产生分层结果 | `last_prescription is None` 且 `current_label != \"insufficient_data\"` |",
    "| 1 | 学生首次产生分层结果 | `last_prescription is None` 且 `current_label != Layer.INSUFFICIENT.value`"
    "（**P6-A6：不得硬编码字面串**） |",
    1, "P6-A6 触发1")
sub("- **`current_label == \"insufficient_data\"` → 返回空 tuple**，无论其余条件是否成立。",
    "- **`current_label == Layer.INSUFFICIENT.value`（实测该值就是 `\"insufficient_data\"`）→ 返回空 tuple**，"
    "无论其余条件是否成立。**⚠️ P6-A6：用 `Layer.INSUFFICIENT.value`，不要在 `triggers.py` 里写第二份字面串**"
    "（单一所有者，Global Constraint #3）；import 走**绝对导入** `from app.domain.stratify import Layer`"
    "（与 `match.py` 同口径），并配一条漂移测试字面钉住 `Layer.INSUFFICIENT.value == \"insufficient_data\"`。",
    1, "P6-A6 决定段")

# ============ 3. prescription 表定义（P6-A2 / A3 / A7 / A8） ============
sub("- **`prescription` 表**按 spec §4.4：`id` / `student_id` / `generated_on: Date` / `template_id: str` / "
    "`training_package: JsonText` / `assembly_snapshot: JsonText` / `safety_substitutions: JsonText` / "
    "`teacher_overrides: JsonText` / `status: String(16)` + CHECK ∈ `{active, replaced, archived, needs_review}` / "
    "`valid_from: Date` / `valid_to: Date | None` / `trigger_reasons: JsonText` / "
    "`batch_id`（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构，供 `_replay_cleanup` 按批删）。",
    "- **`prescription` 表**按 spec §4.4 **+ 三处预检更正**：`id` / `student_id` / `generated_on: Date` / "
    "**`template_ref: String(32)`（P6-A7：不叫 `template_id`，与 `prescription_template.template_ref` 同名）** / "
    "**`microcycle_weeks: Integer`（P6-A3 新增：`prescription_template` 表里没有它，触发 3 与 `valid_to` 都要用它，"
    "故快照在处方行上）** / `training_package: JsonText` / `assembly_snapshot: JsonText` / "
    "`safety_substitutions: JsonText` / `teacher_overrides: JsonText` / "
    "**`previous_had_overrides: Boolean, nullable=False, default=False`（P6-A2 新增：取代往 `assembly_snapshot` "
    "加第 16 个键的那个方案）** / `status: String(16)` + CHECK ∈ `{active, replaced, archived, needs_review}` / "
    "`valid_from: Date` / `valid_to: Date | None` / `trigger_reasons: JsonText` / "
    "`batch_id`（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构，供 `_replay_cleanup` 按批删）。"
    "**⚠️ P6-A9：两个 CHECK 一律用 `_shared.py` 的 `_in_domain(column, allowed, name)`，值域作为类常量声明"
    "（与 `Exercise.IMPACT_LEVELS` / `PrescriptionTemplate.LAYERS` 同口径），不要手写 `CheckConstraint`。**",
    1, "P6-A2/A3/A7/A9 prescription 表")

sub("- **`weekly_adjustment` 表**按 spec §4.4 + §8.4：`id` / `prescription_id` / `week: int`（1-based）/ "
    "`factor: Float` / `reason: str` / `source: String(8)` + CHECK ∈ `{auto, teacher}` / `created_at: DateTime`。"
    "**本 Task 只建表 + 教师路径**；`auto` 来源（预警触发减量 20%）留给 Plan 03，在表注释里写明。",
    "- **`weekly_adjustment` 表**按 spec §4.4 + §8.4：`id` / `prescription_id` / `week: int`（1-based）/ "
    "`factor: Float` / `reason: str` / `source: String(8)` + CHECK ∈ `{auto, teacher}`（P6-A9：同样走 `_in_domain`）/ "
    "`created_at: DateTime` / **`batch_id`（P6-A8 新增：外键到 `daily_sync_run`。计划 Task 7 写着「`_replay_cleanup` "
    "按 `batch_id` 删 `weekly_adjustment`」，而 `repo.delete_by_batch` 要求模型有这一列——不加就要在 Task 7 新写一段"
    "级联删逻辑并新配测试。⚠️ 必须在 Task 6 就加，否则 Task 7 要回头改一张已结案的表，硬规矩 #11）**。"
    "**本 Task 只建表 + 教师路径**；`auto` 来源（预警触发减量 20%）留给 Plan 03，在表注释里写明。",
    1, "P6-A8/A9 weekly_adjustment 表")

# ============ 4. Step 1 补 test_models.py 六处清单（P6-A5） ============
sub("- [ ] **Step 1: 写失败测试**\n\n穷举触发矩阵。五条触发 × {成立, 不成立, 边界} + 组合，至少 20 条。重点：",
    "- [ ] **Step 0: 先改「表数」的六处 + 分区的一处（P6-A5 / P6-A4）**\n\n"
    "按 Ruling 145，这类「一个数散落在多处」的改动**先一次改完再写测试**，否则测试会红在莫名其妙的地方。"
    "**全部按可 grep 的原文找、不要按裸行号找（硬规矩 #76/#78）**：\n\n"
    "| 文件 | 要找的原文 | 改成 |\n"
    "|---|---|---|\n"
    "| `tests/db/test_models.py` | `def test_all_sixteen_tables_created` | `def test_all_eighteen_tables_created` |\n"
    "| 同上 | `assert len(tables) == 16, \"守卫的覆盖面必须先被确认是这 16 张表\"`（**两处**，中文消息里也有「16 张表」） | `== 18` + 「18 张表」 |\n"
    "| 同上 | `assert len(Base.metadata.tables) == 16` | `== 18` |\n"
    "| 同上 | 那段**逐字印着 grep 命令**与「**3** 处本段的散文」的注释 | 计数跟着改（改完自己再 grep 一次核实） |\n"
    "| 同上 | 另一处引用 `test_all_sixteen_tables_created` 这个**函数名**的注释 | 跟着改函数名 |\n"
    "| 同上 | `assert len(_MODELS_PUBLIC_BASELINE) == 33` + 那个清单本身 | **35**，清单加 `\"Prescription\"` 与 `\"WeeklyAdjustment\"`（**按字母序插进去**，清单今天是排序的） |\n"
    "| `tests/seed/test_generate.py` | `DATA_TABLES = (…9 个…)` | 加 `\"prescription\"` 与 `\"weekly_adjustment\"` → **11 个** |\n"
    "| 同上 | `REFERENCE_TABLES` 上方那段「⚠️ 那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区」的预告注释 | **改掉**——「届时」到了，写明归 `DATA_TABLES` 与理由 |\n"
    "| 同上 | `assert REFERENCE_TABLES == (\"exercise\", \"prescription_template\")` | **不动**（字面钉住，两张新表不进参考数据分区） |\n\n"
    "⚠️ `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**不动**——两张表进已有的 `models/prescription.py`，不新增子模块。\n\n"
    "- [ ] **Step 1: 写失败测试**\n\n穷举触发矩阵。五条触发 × {成立, 不成立, 边界} + 组合，至少 20 条。重点：",
    1, "P6-A5 插入 Step 0")

# ============ 5. Step 6 移到 Task 7（P6-A1 / P6-A2） ============
sub("- [ ] **Step 2–5: 跑失败 → 实现 → 跑通**\n- [ ] **Step 6: 集成测试 —— 覆盖不继承 + 同日幂等**\n\n"
    "放 `backend/tests/pipeline/`（跨 Task）：\n"
    "- `test_regeneration_does_not_inherit_teacher_overrides`（spec §7.5 原文：「下次自动生成时回到算法基线、不继承覆盖，"
    "但界面提示『该生上次存在人工覆盖』」）—— 生成 → 加覆盖 → 触发重生成 → 断言新处方的 `training_package` 等于**无覆盖**的基线，"
    "且新处方的某个字段（决定：`prescription.teacher_overrides` 保持空，另在 `assembly_snapshot` 里加 "
    "`\"previous_had_overrides\": true`）**能让界面提示**。\n"
    "- `test_same_day_regeneration_is_idempotent`（Review Focus 第 2 条）—— 同一天跑两次管道，`prescription` 行数不变、"
    "`training_package` 逐字段相同。\n\n"
    "- [ ] **Step 7: 变异验收 + Commit**",
    "- [ ] **Step 2–5: 跑失败 → 实现 → 跑通**\n\n"
    "- [ ] **Step 6: ~~集成测试~~ —— ⚠️ P6-A1：整体移到 Task 7**\n\n"
    "> 原文这里要求在 `backend/tests/pipeline/` 写两条集成测试（`test_regeneration_does_not_inherit_teacher_overrides` "
    "与 `test_same_day_regeneration_is_idempotent`）。**它们在本 Task 写不出来**：两条都要「跑管道 / 触发重生成」，"
    "而 `app/pipeline/prescription_stage.py` 是 **Task 7** 才建的；Task 6 只有两张表 + `triggers.py`（纯函数、不落库）。\n"
    "> **两条测试原文照搬到 Task 7 的 Step 6**（那里已经补进去了）。\n"
    "> ⚠️ 其中第一条原本还要求「在 `assembly_snapshot` 里加 `\"previous_had_overrides\": true`」——**这个方案已被 "
    "P6-A2 否掉**（会让 Task 5 钉死的 12 键 / +3 键两条守卫变红），改成 `prescription.previous_had_overrides` 这个"
    "**独立的 Boolean 列**。\n\n"
    "- [ ] **Step 6b: 本 Task 唯一保留的确定性测试**\n\n"
    "`test_evaluate_triggers_is_deterministic`（同输入两次，结果逐字相同，无随机、无时钟）——这条是**纯函数**测试，"
    "在本 Task 就能写，且是 Global Constraint「时间与随机数一律由调用方注入」的落点。\n\n"
    "- [ ] **Step 7: 变异验收 + Commit**\n\n"
    "变异（**只做 3 条**，Ruling 145）：① 把 `Layer.INSUFFICIENT.value` 的早退删掉 → Review Focus 第 3 条的测试红；"
    "② 触发 3 的 `>=` 改成 `>` → 第 28 天边界测试红；③ 触发 2 改成比较「上一次运行的标签」而不是 `label_at_generation` "
    "→ 「黄→红→黄」那条测试红。**每条按硬规矩 #65 写明哪个断言分支开火，并按 M0/M1 双对照取证；"
    "跑测试前按硬规矩 #83 清 `__pycache__` 并设 `PYTHONDONTWRITEBYTECODE=1`。**",
    1, "P6-A1/A2 Step 6 移走")

# ============ 6. Task 7 接收 Step 6 + 更正 _replay_cleanup 那句（P6-A1/A8） ============
sub("- **幂等**：`prescription` 表的 `UniqueConstraint(\"student_id\", \"generated_on\")` + `repo.upsert`，"
    "与 Plan 01 的三张派生表同构。`_replay_cleanup` 的清单要**加上 `prescription` 与 `weekly_adjustment`**（按 `batch_id` 删）",
    "- **幂等**：`prescription` 表的 `UniqueConstraint(\"student_id\", \"generated_on\")` + `repo.upsert`，"
    "与 Plan 01 的三张派生表同构。`_replay_cleanup` 的清单要**加上 `prescription` 与 `weekly_adjustment`**"
    "（按 `batch_id` 删；**⚠️ P6-A8：`weekly_adjustment` 的 `batch_id` 列已由 Task 6 加好**，"
    "故 `repo.delete_by_batch` 对它直接可用，**不需要**新写级联删逻辑）",
    1, "P6-A8 Task 7 的 _replay_cleanup")

sub("- [ ] **Step 1: 写失败测试**\n\n"
    "- `test_prescriptions_are_generated_for_every_stratified_student`",
    "- [ ] **Step 0: 接收 Task 6 移过来的两条集成测试（P6-A1）**\n\n"
    "放 `backend/tests/pipeline/`：\n"
    "- `test_regeneration_does_not_inherit_teacher_overrides`（spec §7.5 原文：「下次自动生成时回到算法基线、不继承覆盖，"
    "但界面提示『该生上次存在人工覆盖』」）—— 生成 → 加覆盖 → 触发重生成 → 断言新处方的 `training_package` 等于"
    "**无覆盖**的基线，且 **`prescription.previous_had_overrides is True`**（**⚠️ P6-A2：不是往 `assembly_snapshot` "
    "加键**，那会让 Task 5 钉死的 12 键 / +3 键两条守卫变红）能让界面提示。\n"
    "- `test_same_day_regeneration_is_idempotent`（Review Focus 第 2 条）—— 同一天跑两次管道，`prescription` 行数不变、"
    "`training_package` 逐字段相同。\n\n"
    "- [ ] **Step 1: 写失败测试**\n\n"
    "- `test_prescriptions_are_generated_for_every_stratified_student`",
    1, "P6-A1 Task 7 接收 Step 6")

out = text.encode("utf-8")
PLAN.write_bytes(out)
print(f"[out] bytes={len(out)} lines={text.count(nl)} "
      f"CRLF={text.count(chr(13)+chr(10))} LF={text.count(chr(10))}")
for lab, n in edits:
    print(f"  {n}x  {lab}")
