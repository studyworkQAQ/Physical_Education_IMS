"""F1-3：计划正文同步（硬规矩 #84 / #66 / #79）。

亲验结论：控制者说自己本轮改了 4 处，**实测 0/4 在树上**（`git status` 对
`Document/2026-10-06-实施计划02-智能处方引擎.md` 无改动，基线 fd6a427）。故本脚本
把那 4 处 + 2 处连带（硬规矩 #66：一个事实变了要 grep 出全部同类陈述）+ Task 9 那一处
一次改完。每处 assert 命中 1 次。计划文件是 CRLF。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
src = P.read_text(encoding="utf-8")

PAIRS: list[tuple[str, str]] = []

# ---------------------------------------------------------------------------
# 更正 ③：Task 6 的 prescription 表定义要加 label_at_generation
# ---------------------------------------------------------------------------
PAIRS.append((
    "`valid_from: Date` / `valid_to: Date | None` / `trigger_reasons: JsonText` / `batch_id`"
    "（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构，供 `_replay_cleanup` 按批删）。",

    "`valid_from: Date` / `valid_to: Date | None` / `trigger_reasons: JsonText` / `batch_id`"
    "（外键到 `daily_sync_run`，与 Plan 01 的三张派生表同构，供 `_replay_cleanup` 按批删）/ "
    "**`label_at_generation: String(20), nullable=False` + CHECK（Task 7 fix round 1 的 F1-1 追加；"
    "控制者错误 #148）**。⚠️ **本行的字段清单在 Task 6 结案时是 15 列、"
    "fix round 1 之后是 16 列**：`LastPrescription` 的五个字段里 `generated_on` / `template_id`（→ DB 的 "
    "`template_ref`）/ `microcycle_weeks` / `status` 四个都有列，**只有 `label_at_generation` "
    "没有住址**，而触发 2 的判据逐字是 `current_label != last_prescription.label_at_generation`。"
    "#148 的形状是：Task 6 预检时逐个核了 `microcycle_weeks` 有没有住址（那是 P6-A3 那条 "
    "Critical），**却没把 `LastPrescription` 的字段逐个对到列上**，只查了触发 3 需要的那一个。"
    "理由与 P6-A3 **完全同构**：处方要能**离线复算**触发判定，就把判定输入**快照在处方行上**。"
    "**列宽与 CHECK 都与 `stratification_result.label` 同口径**（`String(20)`；实测那一列就是 "
    "`String(20)` + `_in_domain(\"label\", LABELS, \"ck_stratification_result_label\")`，最长者 "
    "`insufficient_data` 是 17 字符），且 CHECK 的值域**直接引 `StratificationResult.LABELS`**、"
    "**不在 `Prescription` 上另立第二份词表**（单一所有者）。不加它的代价：`prescription_stage` "
    "只能按 `(student_id, computed_on == generated_on)` 去 `outerjoin` 回读同一天的分层行，"
    "三个失效形态是 ① `_replay_cleanup` 按 `batch_id` 删分层行 → 重放之后 join 返 `NULL` → "
    "触发 2 **静默不成立**；② 那是一个**跨表的隐式契约**、无任何守卫钉住；③ 触发判定依赖"
    "另一张表的行还在不在，与 spec §4.3「任一条结果都能离线复算」相反。",
))

# ---------------------------------------------------------------------------
# 更正 ①：顶回 ①（控制者错误 #149）—— valid_to 不关账（Task 6 决定那一条）
# ---------------------------------------------------------------------------
PAIRS.append((
    "**换处方时把上一张置 `replaced` 并关账 `valid_to`**——这与 Plan 01 的决定不矛盾"
    "（分层结果是每日快照、无处方那样的自然有效期），但**必须在一处写明为什么两者不同**，"
    "否则下一个人会以为其中一个是 bug。",

    "**换处方时把上一张置 `replaced`，但不改写它的 `valid_to`**"
    "（⚠️ **fix round 1 更正**：本行原写「并关账 `valid_to`」。Task 7 的实现者顶回、"
    "控制者采纳 = **控制者错误 #149**）——「哪一张现在生效」由 `status` **单点**决定，"
    "不靠日期区间。三条理由：① 追溯性关账会让 `valid_to` **不再是该行自身数据的纯函数**"
    "（它变成「下一张处方什么时候生成」的函数），直接违反 spec §4.3「任一条结果都能离线复算」；"
    "② 触发 1/2/4/5 可以在自然到期**之前**就换处方（例如第 5 天分层标签变了），此时关账会把一个"
    "**已经写进库的值**回溯改掉，而重放的批次顺序不同就会改出不同的值；③ 与 Plan 01 "
    "`stratification_result.valid_to` 恒 NULL 是同一条裁定（「不跨批改写」）。"
    "于是两张处方的有效期**可以重叠**。⚠️ 这与 Plan 01 的决定**仍然不矛盾**"
    "（分层结果是每日快照、无处方那样的自然有效期，故本表的 `valid_from` / `valid_to` "
    "要真的填），但**必须在一处写明为什么两者不同**，否则下一个人会以为其中一个是 bug。",
))

# ---------------------------------------------------------------------------
# 更正 ④ 的连带（硬规矩 #66）：Interfaces 那一句只写了两类键
# ---------------------------------------------------------------------------
PAIRS.append((
    "`skipped_reasons: dict[str, int]`（键是 `MatchStatus.value` 或 `\"no_trigger\"`）",

    "`skipped_reasons: dict[str, int]`（键是 `MatchStatus.value` / `\"no_trigger\"` / "
    "`\"insufficient_data\"` / **`\"assembly_error\"`**；⚠️ **fix round 1 更正**：本行原只写"
    "前两类，四类键的取舍见下面「决定」里 `skipped_reasons` 那一条）",
))

# ---------------------------------------------------------------------------
# 更正 ③ 的连带（硬规矩 #66）：「Task 6 新增的三列必须由本 Task 填」
# ---------------------------------------------------------------------------
PAIRS.append((
    "- **⚠️ Task 6 新增的三列必须由本 Task 填**（硬规矩 #86 的回扫结果）：",

    "- **⚠️ Task 6 新增的三列 + fix round 1 追加的一列必须由本 Task 填**"
    "（硬规矩 #86 的回扫结果）：",
))
PAIRS.append((
    "  - `weekly_adjustment.batch_id`（**P6-A8**）← 本批的 `batch_id`。",

    "  - `prescription.label_at_generation`（**fix round 1 的 F1-1**，控制者错误 #148）← "
    "**当天刚写好的** `stratification_result.label`（就在本循环手上的 `result` 里，"
    "**不需要额外查询**）。它是触发 2 判据的**唯一输入**，故 `_last_prescription_of` "
    "从这一列读、**不再 `outerjoin` 回读分层表**。\n"
    "  - `weekly_adjustment.batch_id`（**P6-A8**）← 本批的 `batch_id`。",
))

# ---------------------------------------------------------------------------
# 更正 ④：顶回 ②（skipped_reasons 的第四个键）+ 顶回 ③（不落 needs_review 的行）
# ---------------------------------------------------------------------------
PAIRS.append((
    "**必须再有 `\"insufficient_data\"`**，并有一条测试钉住这 2 人落进这一格。",

    "**必须再有 `\"insufficient_data\"`**，并有一条测试钉住这 2 人落进这一格。\n"
    "  ⚠️ **fix round 1 更正（第四个键 `\"assembly_error\"`）**：Task 7 的实现者顶回、"
    "控制者采纳——上面这三类键（`MatchStatus.value` / `\"no_trigger\"` / "
    "`\"insufficient_data\"`）里**确实没有一格能装下「触发成立了但装配炸了」的人**，"
    "而不装就意味着这批学生在报表里**凭空消失**。故 `skipped_reasons` 是**四个**键。\n"
    "  ⚠️ **fix round 1 追加（顶回 ③，控制者采纳）**：装配失败**不落 "
    "`status=\"needs_review\"` 的行**——那一行必须带 `training_package`，写 `{}` 是"
    "**一个看起来正常的谎**（学生端会渲染出一份空训练单）。「转成 needs_review」落在"
    "**报表的那一格计数**（`PrescriptionReport.needs_review`）+ `skipped_reasons["
    "\"assembly_error\"]` + 一条 `warning` 日志（带学号 / 模板 id / 异常类型与消息）上，"
    "三者都能交代「谁、哪套模板、为什么」。",
))

# ---------------------------------------------------------------------------
# 更正 ① 的第二处：Task 7 Step 1 那条测试的描述 + F1-1 的新测试
# ---------------------------------------------------------------------------
PAIRS.append((
    "- `test_a_layer_change_regenerates_and_replaces`（旧处方 `status` 变 `replaced`、"
    "`valid_to` 关账；新处方 `active`）",

    "- `test_a_layer_change_regenerates_and_replaces`（旧处方 `status` 变 `replaced`、"
    "**`valid_to` 不改写**；新处方 `active`。⚠️ **fix round 1 更正**：原写「`valid_to` 关账」，"
    "见上面 Task 6「决定」那一条 = **控制者错误 #149**）\n"
    "- **`test_trigger_2_survives_the_deletion_of_that_days_stratification_row`"
    "（fix round 1 的 F1-1 追加）** —— 生成一张处方 → **删掉那一天的 `stratification_result` "
    "行** → 换一个标签跑第二天 → 断言触发 2 **仍然成立**（`layer_changed` 在 "
    "`trigger_reasons` 里）。**加列之前必须红**（`outerjoin` 读不到 → `ValueError`）、"
    "**加列之后必须绿**；这是 F1-1 **唯一的可执行判据**。⚠️ 它**取代**了 Task 7 首轮的 "
    "`test_a_prescription_whose_stratification_row_is_gone_fails_loudly`：同一个数据形状，"
    "断言的是**相反**的结论——原先那条钉的 `ValueError` 分支在加了 `label_at_generation` "
    "之后**结构上不可达**（本列 NOT NULL、无缺省），故那条守卫已删。",
))

# ---------------------------------------------------------------------------
# 更正 ②：变异 ② 的判据（控制者错误 #150）
# ---------------------------------------------------------------------------
PAIRS.append((
    "② 把 `_replay_cleanup` 的清单里 `prescription` 删掉 → 重放翻倍测试红；",

    "② 把 `_replay_cleanup` 的清单里 `prescription` 删掉 → "
    "**`test_replay_cleanup_covers_prescription_and_weekly_adjustment` 当场红**"
    "（⚠️ **fix round 1 更正 = 控制者错误 #150**：原文预测的是「重放翻倍测试红」，"
    "而那个失效形态**在结构上不可达**——`prescription` 上有 "
    "`UniqueConstraint(\"student_id\", \"generated_on\")` + `repo.upsert`，翻倍根本写不进去；"
    "实际开火的是清单那条**直接守卫**。教训与硬规矩 #65 同源：写变异判据之前要先问"
    "「这个失效形态在结构上可达吗」）；",
))
PAIRS.append((
    "④ 把 `valid_to` 的 `-1 day` 删掉 → 有效期测试红。",

    "④ 把 `valid_to` 的 `-1 day` 删掉 → 有效期测试红；"
    "**⑤（fix round 1 追加）把 `_last_prescription_of` 改回 `outerjoin` 读 "
    "`stratification_result.label` → "
    "`test_trigger_2_survives_the_deletion_of_that_days_stratification_row` 当场红**。",
))

# ---------------------------------------------------------------------------
# Task 9：13 例的 expected 要不要断言 label_at_generation（实现者的判断：要，附边界）
# ---------------------------------------------------------------------------
PAIRS.append((
    "追加 `expected` 字段：`template_id`、`match_status`、"
    "`weeks[0].sessions[0].blocks[0].exercise_ref`",

    "追加 `expected` 字段：`template_id`、`match_status`、"
    "**`label_at_generation`（fix round 1 的 F1-1 追加，取舍见下面那条 ⚠️）**、"
    "`weeks[0].sessions[0].blocks[0].exercise_ref`",
))
PAIRS.append((
    "⚠️ **GC09 的脆性会传导**：",

    "⚠️ **`label_at_generation` 要不要进 13 例的 `expected`？决定：要**"
    "（fix round 1 交回控制者、控制者倾向「要」，Task 7 的实现者**同意并给出边界**）。"
    "它是 `prescription.label_at_generation` 那一列——触发 2 判据的**唯一输入**、"
    "F1-1 新加——而 Task 9 是**最后一个能钉住它的地方**。⚠️ 但必须写清它钉得住什么、"
    "钉不住什么，否则就是一条看起来强、其实弱的守卫（硬规矩 #39 的反面）：\n"
    "* **钉得住**：处方行上那一列填的是**当天分层结果的那一个标签**，且与黄金用例里已逐条"
    "人读确认的 `expected.label` **逐字相等**（两侧不同源：一侧是 fixture 的字面量、"
    "一侧是库里的列）。抓的是「填错了来源」——填成 `dominant_bucket`、填成昨天的标签、"
    "或压根忘了填（NOT NULL 会在写侧炸，但 fixture 侧的相等断言才把「填的是哪一个」钉住）。\n"
    "* **钉不住**：**触发 2 本身**——黄金用例是**单日**的，而触发 2 要两天。故本条**不是** "
    "Task 7 那条 `test_trigger_2_survives_the_deletion_of_that_days_stratification_row` 的替代，"
    "两条**并列**。\n"
    "* ⚠️ **`insufficient_data` 那一例没有处方**（Z0 闸门），故 13 例里只有 **12** 例能断言它"
    "（与 `template_id` / `needs_review` 同一档处置）。\n"
    "* ⚠️ 对**已匹配**的处方，`label_at_generation` 与 `template_ref` 的前三字符"
    "（`RED` / `YEL` / `GRN`）**恒等**——匹配器就是按 `Layer(label)` 选模板的。故它与 "
    "`template_id` **不是两份独立的证据**；它多出来的那一份价值是「与 `expected.label` 这个"
    "**已人读的字面量**同源比对」，而不是「多一个字段」。**别把它写成两条互相印证的守卫。**\n"
    "\n"
    "⚠️ **GC09 的脆性会传导**：",
))

for old, new in PAIRS:
    n = src.count(old)
    assert n == 1, f"命中 {n} 次（应为 1）：{old[:60]!r}"
    src = src.replace(old, new)

P.write_text(src, encoding="utf-8", newline="\r\n")
b = P.read_bytes()
after = P.read_text(encoding="utf-8")
print(f"OK {len(PAIRS)} 处替换  ->  {len(b)} B / {after.count(chr(10))} 行  "
      f"CRLF={b.count(bytes([13, 10]))} LF={b.count(bytes([10]))}")
for probe in ("valid_to` 关账", "重放翻倍测试红", "label_at_generation", "assembly_error",
              "控制者错误 #148", "控制者错误 #149", "控制者错误 #150",
              "from app.db.models.prescription import WeeklyAdjustment"):
    print(f"   {probe!r:52s} 命中 {after.count(probe)}")
