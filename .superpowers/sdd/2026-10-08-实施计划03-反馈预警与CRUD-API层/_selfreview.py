"""计划 03 自审更正（writing-plans 的 Self-Review 第 2/3/5 项）：6 处。逐条 assert 命中次数。"""
from pathlib import Path

P = Path(__file__).resolve().parents[3] / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
raw = P.read_bytes()
t = raw.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[in] bytes={len(raw)} lines={t.count(nl)} nl={'CRLF' if nl != chr(10) else 'LF'}")
edits = []


def sub(old, new, count, label):
    global t
    if nl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", nl)
        new = new.replace("\r\n", "\n").replace("\n", nl)
    n = t.count(old)
    assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
    t = t.replace(old, new)
    edits.append((label, n))


# --- 1. `deletable: bool` 与 `deletable="forbid"` 类型冲突（Self-Review 第 3 项）---
sub("readable: bool = True, writable: bool = True, deletable: bool = True, on_delete: str = \"restrict\", "
    "scope: ScopeFn | None = None) -> APIRouter`",
    "readable: bool = True, writable: bool = True, "
    "**`on_delete: str = \"restrict\"`（取值 `\"restrict\"` / `\"cascade\"` / `\"forbid\"`；"
    "`\"forbid\"` → `DELETE` 返回 405，故不需要另一个 `deletable` 布尔）**、"
    "`list_exclude: tuple[str, ...] = ()`、`scope: ScopeFn | None = None`) -> APIRouter`",
    1, "1. build_crud_router 的签名（去掉与 on_delete 冲突的 deletable）")

# --- 2. Task 3 的 exercises / prescription-templates 与尾部那段自相矛盾 ---
sub("`exercise` / `prescription_template` 两个是**参考数据**，`writable=True`（教师/管理员要能改动作库与模板的审校状态）"
    "但 `deletable=\"forbid\"`（Plan 02 的 `sync_*` docstring 逐字写着「它不删除 YAML 里已经不存在的行……"
    "真要下线一套模板是一次需要人工确认的迁移」）。",
    "`exercise` / `prescription_template` 两个是**参考数据**，**`writable=False`、`on_delete=\"forbid\"`（只读）**。"
    "理由：spec §4.4 逐字写着「`exercise_equivalence`（动作等价映射）与 `alert_rules`（预警阈值）为 `data/` 下的"
    "**静态 YAML + 版本号**，不入库……**这是体育专家维护的知识资产而非业务数据，改阈值应走版本控制与评审，"
    "不应在运行时改数据库**」，而 `exercise` 与 `prescription_template` 两张表是那两个 YAML 的**投影**"
    "（Plan 02 的 `sync_exercises` / `sync_templates`）——**开放 API 写它们会让「YAML 是唯一所有者」这句话变成假的**，"
    "因为下一次 sync 会把 API 的改动静默覆盖掉。**教师端要改动作库或模板的审校状态，请改 YAML 走版本控制。**"
    "⚠️ 这也顺手解决了 Plan 02 留给 Plan 03 的第 8 条（`sync_*` 没有生产调用方）：**由 "
    "`POST /api/pipeline/run-daily` 调一次 `sync_exercises` + `sync_templates`（两者都幂等）**，"
    "于是「YAML → 表」这条投影有了生产入口，而反向的「表 → YAML」刻意不存在。",
    1, "2. exercises / prescription-templates 改为只读（消除与尾部的自相矛盾）")
sub("**这条推翻了 Task 3 里「`writable=True`」的说法，以本条为准。** / `HttpLePaoAdapter`",
    "**（Task 3 的正文已按这一条写定：两个资源 `writable=False`，`sync_*` 由 `run-daily` 调用。）** / `HttpLePaoAdapter`",
    1, "2b. 尾部那句「推翻 Task 3」改成「已写定」")

# --- 3. Alert 表缺 semester_id 与 window_key 两列（Self-Review 第 3 项：后面用了、前面没定义）---
sub("`handled_action: str | None` / `handled_at: DateTime | None` / `batch_id` FK + "
    "**`UniqueConstraint(\"rule_id\", \"student_id\", \"course_section_id\", \"status\")` 的一部分**（见下面「去重口径」的决定）",
    "`handled_action: str | None` / `handled_at: DateTime | None` / `batch_id` FK / "
    "**`semester_id: int` FK（去重键的一部分）** / **`window_key: String(32)`（触发窗口标识，见下面「去重口径」的决定；"
    "⚠️ 这一列 spec §4.6 没有，是本计划的工程决定 → 登记 spec §14 #38）** + "
    "`UniqueConstraint(\"rule_id\", \"student_id\", \"course_section_id\", \"semester_id\", \"window_key\")`",
    1, "3. Alert 补 semester_id 与 window_key 两列")
sub("**决定：唯一约束是 `(\"rule_id\", \"student_id\", \"course_section_id\", \"semester_id\", \"window_key\")`**，"
    "其中 `window_key: String(32)` 是**触发窗口的标识**",
    "**决定：唯一约束是 `(\"rule_id\", \"student_id\", \"course_section_id\", \"semester_id\", \"window_key\")`**"
    "（五个列都已在上面的字段清单里），其中 `window_key` 是**触发窗口的标识**",
    1, "3b. 去重口径那段指回字段清单")

# --- 4. Notification.alert_id 的 ondelete 直接在 Task 2 定，不留「回改」 ---
sub("/ `alert_id: int | None` FK / `prescription_id: int | None` FK /",
    "/ `alert_id: int | None` FK（**`ondelete=\"SET NULL\"`**，理由见 Task 8 的决定：`notification` 不带 `batch_id`、"
    "不进 `_replay_cleanup`，而 `alert` 进——重放删掉 alert 时不能让通知行炸 FK）/ `prescription_id: int | None` FK /",
    1, "4. Notification.alert_id 的 ondelete 在 Task 2 就定")
sub("→ **决定：`notification.alert_id` 的 FK 加 `ondelete=\"SET NULL\"`**，并在 Task 2 建表时就写好。"
    "**⚠️ 这一条要回改 Task 2**（按硬规矩 #84 在这里点名：Task 2 的 `Notification.alert_id` 必须带 `ondelete=\"SET NULL\"`）。",
    "→ **决定：`notification.alert_id` 的 FK 带 `ondelete=\"SET NULL\"`**（**已写进 Task 2 的字段清单**，不留「回改」——"
    "Plan 02 的控制者错误 #151 就是「说要改而没落笔」）。",
    1, "4b. 去掉「回改 Task 2」那句")

# --- 5. _BATCH_OWNED_TABLES 是 5 → 9，不是 10（Self-Review 第 5 项：数错了）---
sub("`_BATCH_OWNED_TABLES`（Plan 02 Task 9 把 `_DERIVED_TABLES` 改成了这个名字；**带 `batch_id` 的表**要从 5 张扩到 **10 张**）",
    "`_BATCH_OWNED_TABLES`（Plan 02 Task 9 把 `_DERIVED_TABLES` 改成了这个名字；**带 `batch_id` 的表**要从 **5 张扩到 9 张**"
    "——既有 5 张是 `derived_metrics` / `stratification_result` / `percentile_snapshot` / `prescription` / `weekly_adjustment`，"
    "本计划新增 4 张带 `batch_id` 的是 `class_session` / `training_log` / `alert` / `weekly_class_report`；"
    "**`rpe_record` / `mini_test` / `notification` 三张刻意不带**，理由见下面那条决定。"
    "⚠️ **这个数自己用运行时口径数一遍再写进断言**，不要照抄本行）",
    1, "5. _BATCH_OWNED_TABLES 5 → 9")

# --- 6. 新增的 JsonText 列是 7 个，不是 9 个 ---
sub("`len(json_text_columns)` 的相等断言（7 张新表里有 **9 个 `JsonText` 列**：`mini_test.item_combo` + `alert.trigger_snapshot` + "
    "`weekly_class_report` 的 5 个 + …**自己数，用运行时口径**）",
    "`len(json_text_columns)` 的相等断言（Plan 02 Task 6 之后是 **14**；7 张新表里有 **7 个 `JsonText` 列** —— "
    "`mini_test.item_combo`、`alert.trigger_snapshot`、`weekly_class_report` 的 5 个"
    "（`layer_distribution` / `rpe_summary` / `checkin_rate_by_layer` / `progress_board` / `alert_summary`），"
    "故新值应是 **21**。⚠️ **自己用运行时口径数一遍再写进断言**，不要照抄这个数——控制者在 Plan 02 为此栽过 4 次）",
    1, "6. JsonText 列数 9 → 7（合计 21）")

out = t.encode("utf-8")
P.write_bytes(out)
c = P.read_bytes().decode("utf-8")
print(f"[out] bytes={len(out)} lines={c.count(nl)} CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for lab, n in edits:
    print(f"  {n}x  {lab}")
print("\n--- 复核：6 处矛盾是否真的消失了 ---")
for bad, why in (('deletable: bool', "与 on_delete 冲突的旧签名"),
                 ('deletable="forbid"', "旧写法"),
                 ("`writable=True`（教师/管理员", "旧的参考数据可写说法"),
                 ("这条推翻了 Task 3", "自相矛盾的那句"),
                 ("这一条要回改 Task 2", "「说要改而没落笔」的形状"),
                 ("从 5 张扩到 **10 张**", "数错的那个数"),
                 ("有 **9 个 `JsonText` 列**", "数错的那个数")):
    print(f"  {bad!r:34s} 命中 {c.count(bad)}   <- 应为 0（{why}）")
for good in ('on_delete: str = "restrict"', "writable=False`、`on_delete=\"forbid\"", "window_key: String(32)",
             'ondelete="SET NULL"', "5 张扩到 9 张", "新值应是 **21**"):
    print(f"  {good!r:34s} 命中 {c.count(good)}   <- 应 >= 1")
