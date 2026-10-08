"""账本追加：Task 6 预检节（Ruling 149 + 硬规矩 #86）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

### Task 6: `prescription` / `weekly_adjustment` 表 + 五触发条件 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`55874a6`（Task 5 结案，工作树干净）。
**测试基线**：`679 passed`；`app/domain/` **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**；**16 张表**；`__all__` **43**；扫描面 **32**。
**取证脚本**：`t6_probes/_t6_probe1.py`（DB 层既有形状 + 计划的每条断言）与 `_t6_probe2.py`（分区守卫的行数断言口径 + `_MODELS_PUBLIC_BASELINE` 全文），两份均入库。

#### Ruling 149 — 预检查出 3 Critical / 5 Important / 3 Minor / 1 控制者自查，计划正文更正 10 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P6-A1** | **Critical** | **Task 6 的 Step 6 那两条集成测试在本 Task 写不出来。** 它们要求「生成 → 加覆盖 → 触发**重生成**」与「同一天跑两次**管道**」，而 `app/pipeline/prescription_stage.py` 是 **Task 7** 才建的；Task 6 只有两张表 + `triggers.py`（纯函数、不落库）。 | **Step 6 整体移到 Task 7**（已在 Task 7 补成 Step 0，两条测试原文照搬）。Task 6 只留 `test_evaluate_triggers_is_deterministic` 那条纯函数测试（改编号为 Step 6b）。⚠️ 与 **Ruling 103 同型**（派单让实现者做一件当场做不到的事；那次的后果是覆盖率静默跌破 100% 而 pytest 退出码仍是 0） |
| **P6-A2** | **Critical** | Step 6 要求「在 `assembly_snapshot` 里加 `"previous_had_overrides": true`」，**与 Task 5 刚钉死的键集契约直接冲突**：`assemble` 恰好 **12** 个键（`test_assembly_snapshot_keys_are_exactly_the_pinned_set`，多一键少一键都红）、`apply_safety` 追加**至多 3** 个（`test_safety_appends_at_most_three_snapshot_keys`）。加第 16 个键会让**两条守卫变红**。 | **不往 `assembly_snapshot` 加键。** 改成 `prescription` 表自己的列 **`previous_had_overrides: Mapped[bool]`**（`Boolean, nullable=False, default=False`）。理由：它是**关于上一张处方的事实**，不属于「这一张处方的装配输入输出」，放进 `assembly_snapshot` 是**范畴错误**（那一列的契约是「离线复算本张处方」）。⚠️ **这条契约是控制者自己在 Ruling 148 里裁定的，却没传导到 Task 6** → 见 P6-A12 |
| **P6-A3** | **Critical** | **`microcycle_weeks` 无处可取。** 实测 `prescription_template` 的 **10 列** = `id / layer / weakness / body_comp / template_ref / version / review_status / reviewer / reviewed_at / reachable`——**没有 `microcycle_weeks`，也没有 `weekly_frequency`**。而触发 3 的判据与 `valid_to` 的算式都要它，且计划明写「从**上一张处方的模板**取，不硬编码 4」。 | **给 `prescription` 表加一列 `microcycle_weeks: Mapped[int]`**（生成时从 `Template.microcycle_weeks` 快照下来）。理由：处方要能**离线复算** `valid_to` 与触发 3，而模板将来会改版（`version` 会变），把周期快照在处方行上才符合 spec §4.3 的可追溯性。**⚠️ 刻意不给 `prescription_template` 加列**——教师端展示模板周期是 **Plan 03 CRUD 层**的活；今天加会让 Task 6 回头改 Task 3 已结案的表 + `sync_templates` + `_MODELS_PUBLIC_BASELINE` |
| P6-A4 | Important | 分区穷尽守卫实测口径（`tests/seed/test_generate.py`）：`assert partitioned == actual`（**新表必须归进三个分区之一，否则这条红**）、三分区互不相交（用「三张清单长度之和 == 并集大小」查）、`assert REFERENCE_TABLES == ("exercise", "prescription_template")`（**字面钉住**）、`for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0`（**seed 阶段必须 0 行**）、`for table in ORGANISATION_TABLES: assert count > 0`。且该文件注释里**已经预告过这个决定**：「⚠️ 那两张是**业务数据**，届时它们该进 `DATA_TABLES` 还是本分区」。 | `prescription` 与 `weekly_adjustment` **都归 `DATA_TABLES`**（9 → **11**）。这与「seed 阶段 0 行」天然相容（处方是管道产物，不由 `seed_database` 写）。`REFERENCE_TABLES` 那条字面断言**不动**。**且必须同时改掉那段预告注释**——「届时」到了 |
| P6-A5 | Important | `test_models.py` 要改的**远不止「表数 16 → 18」**。实测命中点：① 函数名 `test_all_sixteen_tables_created`；② **两处** `assert len(tables) == 16, "守卫的覆盖面必须先被确认是这 16 张表"`（**中文消息里也有「16 张表」**）；③ `assert len(Base.metadata.tables) == 16`；④ 一段注释里**逐字印着 grep 命令**与「**3** 处本段的散文」的计数；⑤ 另一处注释引用了那个**函数名**；⑥ `assert len(_MODELS_PUBLIC_BASELINE) == 33`（清单实测 33 个名字，含 `Any/Base/Boolean/CheckConstraint/Date/DateTime/Float/ForeignKey/Integer/Iterable/JsonText/Mapped/String/Text/TypeDecorator/UniqueConstraint/dt/json/mapped_column` 等非表名）。 | 六处**全部列进新增的 Step 0**（一张表，逐格给「要找的原文 → 改成什么」）。`_MODELS_PUBLIC_BASELINE` **33 → 35**（加 `Prescription` / `WeeklyAdjustment`，**按字母序插**，清单今天是排序的）。⚠️ `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）**不动**——两张表进已有的 `models/prescription.py` |
| P6-A6 | Important | 实测 `Layer` 成员 = `[('RED','red'), ('YELLOW','yellow'), ('GREEN','green'), ('INSUFFICIENT','insufficient_data')]`，`INSUFFICIENT = "insufficient_data"` 住在 `app/domain/stratify.py`。 | `triggers.py` **不得硬编码 `"insufficient_data"` 字面串**，用 `Layer.INSUFFICIENT.value`（单一所有者，Global Constraint #3）+ 一条漂移测试字面钉住该值。import 走**绝对导入** `from app.domain.stratify import Layer`（与 `match.py` 同口径；同包兄弟才走 level 1） |
| P6-A7 | Important | 逻辑 id 的列名**两套**：`prescription_template` 的列叫 **`template_ref`**（Task 3 按 spec §4.4 勘误定的），计划 Task 6 写 `prescription` 表的列叫 `template_id`。 | DB 列统一用 **`template_ref`**。**domain 侧不动**（`Template.template_id` / `LastPrescription.template_id` 保持，spec §7.2 的字面）。**⚠️「domain 叫 `template_id`、DB 列叫 `template_ref`」这个对照必须写进 docstring**，否则 Task 7 的实现者会以为是两个东西 |
| P6-A8 | Important | `weekly_adjustment` **没有 `batch_id` 列**，而计划 Task 7 写着「`_replay_cleanup` 的清单要加上 `prescription` 与 `weekly_adjustment`（**按 `batch_id` 删**）」。实测 `repo.delete_by_batch(session, model, batch_id)` 要求模型有 `batch_id`。 | **Task 6 就给 `weekly_adjustment` 加 `batch_id` 列**（外键到 `daily_sync_run`）。理由：① `delete_by_batch` 是既有的、被测试覆盖的路径，改用级联删要新写逻辑 + 新配测试；② 「按批删」是本仓一致的幂等手段；③ 一列的成本远低于一段新逻辑。⚠️ **必须在 Task 6 就加**——Task 7 才发现就要回头改一张已结案的表（硬规矩 #11）。Task 7 那句话已同步更正 |
| P6-A9 | Minor | `prescription.status` 值域 `{active, replaced, archived, needs_review}`，最长 `needs_review` = **12**，`String(16)` 够；`weekly_adjustment.source` 值域 `{auto, teacher}`，最长 `teacher` = **7**，`String(8)` 够。 | 无需更正。**但两个 CHECK 一律用 `_shared.py` 的 `_in_domain(column, allowed, name)`**（不要手写 `CheckConstraint`），值域作为**类常量**声明（与 `Exercise.IMPACT_LEVELS` / `PrescriptionTemplate.LAYERS` 同口径） |
| P6-A10 | Minor | 实测 `daily_sync_run` **19 列**，`prescription_count` 与 `alert_count` **都已存在**（Plan 01 就建好了）。 | 无需更正（计划 Task 7 的说法对）。**Task 6 不写这两列的值**，Task 7 才写 `prescription_count` |
| P6-A11 | Minor | 计划的 `**Files:**` 行**漏了 `tests/seed/test_generate.py`** —— 而 P6-A4 那条分区穷尽守卫**一定会红**。 | `**Files:**` 行补上它（`DATA_TABLES` 9 → 11 + 改预告注释）。**同时补 `app/db/models/__init__.py`**（要重导出两个新类） |
| P6-A12 | — | **控制者自查**：P6-A1 / P6-A2 两条都是「**Task 5 结案改变了 Task 6 的前提**」而控制者没有传导——P6-A2 撞的正是 Task 5 fix round 1 刚钉死的键集契约，**而那条契约是控制者自己在 Ruling 148 里裁定的**。 | → **补硬规矩 #86：每个 Task 结案时，必须扫一遍后续所有 Task 的正文，找出「被本次结案改变的前提」并当场更正。** 依据：这与硬规矩 #75（P2-A1 的裁定没传导到 Task 3，同一缺陷原封不动重演）是**同一根因的第 2 次**，而 #75 只覆盖了「预检裁定」这一半，没覆盖「结案产出」 |

**计划正文更正**：`_t6_preflight_patch.py`，**10 处替换全部命中 1 次**（硬规矩 #79：逐条 `assert 命中次数`，脚本打印的命中清单本身即取证）。计划 **159 715 B / 938 行 → 173 442 B / 989 行**（纯 CRLF、无 BOM）。

**按硬规矩 #86 立刻回扫 Task 7/8/9 的正文**，本轮已顺手更正 2 处（Task 7 的 `_replay_cleanup` 那句 + Task 7 新增 Step 0 接收两条集成测试）。**剩余待 Task 7 预检时复核**：Task 7 的 `profile_of` 要不要填 `microcycle_weeks` 与 `previous_had_overrides` 两个新列（P6-A3 / P6-A2 的连带），以及 `input_snapshot` 补键那一段是否仍成立。

**下一步**：抽 `task-6-brief.md` → 派实现者。**按 Ruling 145，目标 1–2 轮。**
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
assert "Ruling 149" not in t, "Ruling 149 已存在"
t2 = t.rstrip("\r\n") + BODY
P.write_bytes(t2.encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 149", "硬规矩 #86", "P6-A1", "P6-A12", "previous_had_overrides", "microcycle_weeks"):
    print(f"  {k}: {c.count(k)}")
