"""Task 8 预检更正（P8-A1..A8）+ 账本 Ruling 153。逐条 assert 命中次数（硬规矩 #79）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
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
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行 "
          f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `197147f`，取证脚本 `t8_probes/_t8_probe1.py`）

**测试基线**：`750 passed`；`app/domain/` **951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**；**18 张表**（`prescription` **16 列**、`weekly_adjustment` **8 列**）；`__all__` **47**；扫描面 **34**。

| # | 级别 | 事实（全部实测，运行时口径，硬规矩 #89） | 更正 |
|---|---|---|---|
| **P8-A1** | **Critical** | 计划说「缩放只作用于 `weekly_volume`，不改 `hr_zone`」，但 **`AssembledBlock` 今天是 10 个字段**（`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone / structure / weekly_volume / volume_unit / sessions_per_week`）——其中 `volume_unit` 与 `sessions_per_week` 是 **Task 5 fix round 1 之后才有的**，计划 Task 8 的正文**完全没提它们**。 | 口径收紧成：缩放时**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。⚠️ `sessions_per_week` 是**骨架的结构属性、不是量**，缩它会让「一周做几次」随减量变化，那是语义错误。⚠️ `WeeklySheet` **刻意不提供跨单位的周总量汇总字段**（`volume_unit` 实测值域 = `{min, reps, unspecified}`，把它们相加就是 Task 5 的 F1-1 那个「混合量纲 float」错误）——**这条要写进 docstring，否则 Plan 03 的前端会自己把 `min` 和 `reps` 加起来**。测试：用 `dataclasses.replace` 做对照，断言「除 `weekly_volume` 外全等」 |
| **P8-A2** | **Critical** | `volume_unit` 的第三档 **`"unspecified"`** 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档的 `weekly_volume` 恒为 **`0.0`**。`apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里**，故 `weekly_training_sheet` 一定会吃到它——而**计划对这一档只字未提**。 | **照原样带出、不特殊处理**（`0.0 × factor = 0.0`，无副作用）。**但必须有一条测试吃真仓**：红层模板 + 体脂异常触发 → 装配出一个含 addon 的包 → 断言 `WeeklySheet` 里那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`。**理由与本节最后一条（`auto` 来源）是同一条纪律**：不给它测试，Plan 03 就会撞上一个「结构上支持、逻辑上没测过」的路径 |
| P8-A3 | Important | `TrainingPackage` 实测有 **`paused: bool = False`** 字段（Task 5 的 5.4 由 `OverrideKind.PAUSE` 置位），而 `weekly_training_sheet` 吃到 `paused=True` 的包该返回什么，**计划完全没定**。 | **`WeeklySheet` 加一个 `paused: bool` 字段**（从 `pkg.paused` 直接抄），且 `paused=True` 时 **`sessions` 原样保留**——与 Task 5 的 5.4 决定逐字一致（「暂停是可撤销的，删掉 `weeks` 就不可逆了」）。**否掉「抛 `ValueError`」那个方案**：读模型的职责是**投影**、不是校验；抛异常会让「暂停」这件事在 API 层变成一个错误分支而不是一份可渲染的数据。**⚠️「暂停」与「本周量为 0」是两件不同的事**（前者是可撤销的状态、后者是调整结果），`paused` 字段的存在就是为了不让前端把两者静默合并 |
| P8-A4 | Important | `weekly_factors_of` 实测**今天不存在**（`prescription_stage.py` 里 0 命中，它的公开函数是 `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions` + 5 个私有）。而 `weekly_adjustment` 表**今天 0 行**：`auto` 来源是 Plan 03、`teacher` 来源要等 Plan 03 的 CRUD API。**故本 Task 的这个函数在生产路径上没有调用方、在库里没有数据。** | **照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**来喂它（不靠管道产出），docstring 按硬规矩 #39 写明「今天没有生产调用方，Plan 03 的 API 层才会调」。⚠️ **排序必须显式**：计划说「`reasons` / `sources` 按 `week` 内的创建顺序全部保留」，而 `created_at` 是 `DateTime NOT NULL 无缺省` → 用 **`ORDER BY created_at, id`**（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等——**这正是 Task 5 的 5.4 里「多条覆盖同一目标由列表顺序决定」的同一条理由**）。要有一条测试钉住这个 tie-breaker |
| P8-A5 | Important | `WeeklyFactor.source` 的值域在**两个住址**：DB 侧 `weekly_adjustment.source VARCHAR(8)` + CHECK `ck_weekly_adjustment_source` ∈ `{auto, teacher}`（Task 6 用 `_in_domain` + 类常量 `SOURCES`）；domain 侧计划写的是裸 `str`。 | **domain 侧不另立词表**（`WeeklyFactor.source` 保持 `str`），但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {"auto", "teacher"}`——**放 pipeline 层的测试里**，因为 **domain 不能 import ORM**。与 Task 5 的 P5-A9（`ADDON_TRIGGERS` / `EQUIVALENCE_TRIGGERS` 两套词表）是同一条纪律 |
| P8-A6 | Minor | `factor` 的合法区间 `(0, 2]` 由 `WeeklyFactor.__post_init__` 校验，而 DB 的 `weekly_adjustment.factor` 列**没有对应的 CHECK**。 | **这是两层守卫、不是重复**：domain 的值对象与 DB 的列各有各的失守方式（前者挡「教师端传了 0」，后者挡「有人绕过 domain 直接写库」——而今天 DB 那一层**刻意不加**，因为 `(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界）。**把这个理由写进 `weekly.py` 的 docstring**，否则下一个人会以为其中一个是冗余的 |
| P8-A7 | Minor | Task 6 的 `triggers.py` 实测用的是 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，因为 domain 不能 import `datetime`）。计划的 `current_week` 边界写的是 `+ 27 days → 4`、`+ 28 days → None`。 | **`current_week` 必须用同一个口径**，否则两处会漂：`week = (as_of - generated_on).days // 7 + 1`，`week > microcycle_weeks → None`。⚠️ **`.days // 7` 对负数向下取整**（`-1 // 7 == -1`），故 `as_of < generated_on` 时 `week` 会是 **0 或负**——**必须先判 `.days < 0` 再算**，并配一条测试钉住 `as_of == generated_on - 1 day → None`（**不是 0、不是 1**）。**另配一条跨模块一致性测试**：对同一组 `(generated_on, as_of, microcycle_weeks)`，断言「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」在到期日那一格**同真**。**这条是两个模块口径不漂的唯一守卫** |
| P8-A8 | Minor | 实测三层的 `volume_unit` 分布 = **红 `{min, reps}` / 黄 `{min}` / 绿 `{min}`**；而 `hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**（Task 5 的 Ruling 133：130 个 block 里 82 个是 `intensity: {type: none}`）。 | 计划要求的「缩放不动 `hr_zone`」那条测试**必须用红层模板**（如 `RED-END-ABN-01`）。**用黄层或绿层写会全绿、但什么也没测**——那两层所有 block 的 `hr_zone` 本来就是 `None`，「不动它」是恒真式（假绿） |

**扫描面**：本 Task 新建 `app/domain/prescription/weekly.py` → domain 15 → **16**，扫描面 **34 → 35**。

"""

patch(PLAN, [
    ("## Task 8: 「本周训练单」读模型（spec §8.4）\n\n**Files:**",
     "## Task 8: 「本周训练单」读模型（spec §8.4）\n" + PRE + "\n**Files:**",
     1, "P8 插入预检更正总表"),

    # WeeklySheet 加 paused + 缩放口径（P8-A1/A3）
    ("  - `WeeklySheet`（frozen）：`week: int` / `factor: float` / `reasons: tuple[str, ...]` / "
     "`sources: tuple[str, ...]` / `sessions: tuple[AssembledSession, ...]`（**已按 `factor` 缩放**）",
     "  - `WeeklySheet`（frozen）：`week: int` / `factor: float` / `reasons: tuple[str, ...]` / "
     "`sources: tuple[str, ...]` / `sessions: tuple[AssembledSession, ...]`（**已按 `factor` 缩放**） / "
     "**`paused: bool`（P8-A3 新增，从 `pkg.paused` 直接抄）**\n"
     "    ⚠️ **P8-A1：「已按 `factor` 缩放」的精确口径** —— `AssembledBlock` 今天是 **10 个字段**，"
     "缩放时**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。"
     "**`sessions_per_week` 是骨架的结构属性、不是量**，缩它会让「一周做几次」随减量变化。"
     "**`WeeklySheet` 刻意不提供跨单位的周总量汇总字段**（`volume_unit` 实测值域 `{min, reps, unspecified}`，"
     "相加就是 Task 5 的 F1-1 那个「混合量纲 float」错误）——写进 docstring，否则 Plan 03 的前端会自己加。",
     1, "P8-A1/A3 WeeklySheet"),

    # 缩放那条决定（P8-A1/A8）
    ("- **缩放只作用于 `weekly_volume`，不改 `hr_zone`**。理由：心率区间是**强度**、不是**量**；"
     "把两者一起缩会让「减量」变成「降强度」，而 spec §8.4 明写「微调改的是**本周训练量**」。"
     "**这条要写成测试**，因为它是本 Task 最容易被实现错的地方。",
     "- **缩放只作用于 `weekly_volume`，不改 `hr_zone`**。理由：心率区间是**强度**、不是**量**；"
     "把两者一起缩会让「减量」变成「降强度」，而 spec §8.4 明写「微调改的是**本周训练量**」。"
     "**这条要写成测试**，因为它是本 Task 最容易被实现错的地方。"
     "**⚠️ P8-A8：这条测试必须用红层模板**（如 `RED-END-ABN-01`）——实测 `hr_zone` **只有红层的 "
     "`hrmax_pct` block 非 `None`**，黄层绿层全是 `None`，用它们写「不动 `hr_zone`」是**恒真式（假绿）**。"
     "**⚠️ P8-A1：测试要用 `dataclasses.replace` 做对照，断言「除 `weekly_volume` 外 9 个字段全等」**，"
     "而不只是断言 `hr_zone` 没变。",
     1, "P8-A1/A8 缩放决定"),

    # current_week 的口径（P8-A7）
    ("- **`current_week` 的边界**：`as_of == generated_on` → `1`；`as_of == generated_on + 27 days` → `4`；"
     "`+ 28 days` → `None`（已到期，该换处方了，与 Task 6 的触发 3 同一口径 `>=`）。"
     "**三个边界都要字面写死日期测试。**",
     "- **`current_week` 的边界**：`as_of == generated_on` → `1`；`as_of == generated_on + 27 days` → `4`；"
     "`+ 28 days` → `None`（已到期，该换处方了，与 Task 6 的触发 3 同一口径 `>=`）。"
     "**三个边界都要字面写死日期测试。**\n"
     "  **⚠️ P8-A7 的实现口径**：Task 6 的 `triggers.py` 实测用的是 "
     "`(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，"
     "因为 domain 不能 import `datetime`）。**`current_week` 必须用同一个口径**："
     "`week = (as_of - generated_on).days // 7 + 1`，`week > microcycle_weeks → None`。"
     "**⚠️ `.days // 7` 对负数向下取整**（`-1 // 7 == -1`），故 `as_of < generated_on` 时 `week` 会是 "
     "**0 或负** —— **必须先判 `.days < 0` 再算**，并配一条测试钉住 "
     "`as_of == generated_on - 1 day → None`（**不是 0、不是 1**）。\n"
     "  **⚠️ 另配一条跨模块一致性测试**：对同一组 `(generated_on, as_of, microcycle_weeks)`，"
     "断言「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」"
     "在**到期日那一格同真**。**这条是两个模块口径不漂的唯一守卫** —— 没有它，"
     "任一处把 `7` 改成别的数、或把 `>=` 改成 `>`，学生端就会看到一张已经过期却仍在渲染的训练单。",
     1, "P8-A7 current_week"),

    # auto 来源那条后面补 addon 与 paused 的测试要求（P8-A2/A3）
    ("- **`auto` 来源本计划不产出**（Plan 03 的预警落地）——但 `WeeklyFactor.source` 的取值域要包含它，"
     "且 `weekly.py` 要能正确处理（否则 Plan 03 会撞上一个「结构上支持、逻辑上没测过」的路径）。"
     "**用直接构造的 `WeeklyFactor(source=\"auto\")` 测它。**",
     "- **`auto` 来源本计划不产出**（Plan 03 的预警落地）——但 `WeeklyFactor.source` 的取值域要包含它，"
     "且 `weekly.py` 要能正确处理（否则 Plan 03 会撞上一个「结构上支持、逻辑上没测过」的路径）。"
     "**用直接构造的 `WeeklyFactor(source=\"auto\")` 测它。**\n"
     "- **⚠️ P8-A5：`source` 的值域有两个住址**（DB 侧 `ck_weekly_adjustment_source` ∈ `{auto, teacher}`，"
     "由 Task 6 的 `_in_domain` + 类常量 `SOURCES` 生成；domain 侧是裸 `str`）。"
     "**domain 侧不另立词表**，但**要有一条漂移测试**字面钉住 "
     "`WeeklyAdjustment.SOURCES == {\"auto\", \"teacher\"}` —— **放 pipeline 层的测试里**，"
     "因为 **domain 不能 import ORM**。\n"
     "- **⚠️ P8-A2：`volume_unit == \"unspecified\"` 那一档要有测试。** 它是 Task 5 的 P5-A3 为 "
     "**addon block** 加的，那一档的 `weekly_volume` 恒为 `0.0`，而 `apply_safety` 追加的 addon "
     "**已经在 `TrainingPackage.weeks` 里** → `weekly_training_sheet` 一定会吃到它。"
     "**照原样带出、不特殊处理**（`0.0 × factor = 0.0`），但要吃真仓测一次："
     "红层模板 + 体脂异常触发 → 断言那个 addon block 的 `weekly_volume == 0.0` 且 "
     "`volume_unit == \"unspecified\"`。**与上一条（`auto` 来源）是同一条纪律。**\n"
     "- **⚠️ P8-A3：`paused` 的语义。** `WeeklySheet` 带一个 `paused: bool`（从 `pkg.paused` 直接抄），"
     "`paused=True` 时 **`sessions` 原样保留**——与 Task 5 的 5.4 决定逐字一致"
     "（「暂停是可撤销的，删掉 `weeks` 就不可逆了」）。**否掉「抛 `ValueError`」那个方案**："
     "读模型的职责是**投影**、不是校验。**⚠️「暂停」与「本周量为 0」是两件不同的事**"
     "（前者是可撤销的状态、后者是调整结果），`paused` 字段的存在就是为了不让前端把两者静默合并。"
     "配一条测试：`paused=True` 的包 → `sheet.paused is True` 且 `sessions` 与骨架逐字段相同。\n"
     "- **⚠️ P8-A6：`factor` 的 `(0, 2]` 与 DB 列没有 CHECK 是两层守卫、不是重复。** "
     "domain 的值对象挡「教师端传了 0」，DB 的列**刻意不加** CHECK——因为 `(0, 2]` 是**读模型的语义**、"
     "不是数据的形状，Plan 03 可能要放宽上界。**把这个理由写进 `weekly.py` 的 docstring**，"
     "否则下一个人会以为其中一个是冗余的。\n"
     "- **⚠️ P8-A4：`weekly_factors_of` 今天在生产路径上没有调用方、`weekly_adjustment` 表 0 行**"
     "（`auto` 来源是 Plan 03、`teacher` 来源要等 Plan 03 的 CRUD API）。"
     "**照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**喂它，"
     "docstring 按硬规矩 #39 写明「今天没有生产调用方」。"
     "**⚠️ 排序必须显式**：`created_at` 是 `DateTime NOT NULL 无缺省`，故用 **`ORDER BY created_at, id`**"
     "（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等——**这正是 Task 5 的 5.4 里"
     "「多条覆盖同一目标由列表顺序决定」的同一条理由**）。要有一条测试钉住这个 tie-breaker。",
     1, "P8-A2/A3/A4/A5/A6 补决定"),

    # 测试清单
    ("测试至少：`current_week` 的 5 个边界、多调整相乘、`factor` 越界拒绝、缩放不动 `hr_zone`、"
     "`reasons`/`sources` 顺序保留、`auto` 与 `teacher` 混合、空调整列表 → `factor == 1.0` 且 `sessions` 与骨架逐字段相同。",
     "测试至少：`current_week` 的 **6** 个边界（**P8-A7 加了 `as_of == generated_on - 1 day → None` 那一格**）、"
     "**`current_week` ↔ `MICROCYCLE_EXPIRED` 的跨模块一致性**（P8-A7）、多调整相乘、`factor` 越界拒绝"
     "（`0` / `-0.1` / `2.0` / `2.1` 四格）、缩放不动 `hr_zone` **且其余 9 个字段全等**（P8-A1/A8，**用红层模板**）、"
     "`reasons`/`sources` 顺序保留、`auto` 与 `teacher` 混合、"
     "**`volume_unit == \"unspecified\"` 的 addon block**（P8-A2）、**`paused=True`**（P8-A3）、"
     "空调整列表 → `factor == 1.0` 且 `sessions` 与骨架逐字段相同。\n"
     "放 pipeline 层的：`weekly_factors_of` 的**直接插行**测试（P8-A4，含 `created_at` 相同、`id` 不同的 tie-breaker 那一格）、"
     "`WeeklyAdjustment.SOURCES` 的漂移测试（P8-A5）。",
     1, "P8 测试清单"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 8: 「本周训练单」读模型 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`197147f`（Task 7 结案，工作树干净）。**测试基线**：`750 passed`；domain **951/0/274/0/100%**；**18 张表**（`prescription` 16 列、`weekly_adjustment` 8 列）；`__all__` **47**；扫描面 **34**。
**取证脚本**：`t8_probes/_t8_probe1.py`（全部用运行时口径：`dataclasses.fields(...)` / `__table__.columns` / 真仓装配，**不用正则数源码**，硬规矩 #89）。

#### Ruling 153 — 预检查出 2 Critical / 3 Important / 3 Minor，计划正文更正 6 处

**本 Task 是 Plan 02 里最小的一个（一个新 domain 模块 + 一个 pipeline 函数），但预检仍查出 2 条 Critical。** 根因与 Task 5 的合并节相同：**Task 8 的正文是在 Task 5 之前写的，而 Task 5 的 fix round 1 改变了 `AssembledBlock` 的字段集**（`volume_unit` / `sessions_per_week` 两个字段是那一轮才加的），Task 8 的正文对此**完全无感**。

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P8-A1** | **Critical** | **`AssembledBlock` 今天是 10 个字段**（`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone / structure / weekly_volume / volume_unit / sessions_per_week`），而计划 Task 8 只说「缩放只作用于 `weekly_volume`，不改 `hr_zone`」—— **对另外 8 个字段一字未提**，其中 `sessions_per_week` 被缩会让「一周做几次」随减量变化（语义错误）。 | 口径收紧成「**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**」；测试用 `dataclasses.replace` 做对照、断言「除 `weekly_volume` 外全等」。⚠️ 并写明 **`WeeklySheet` 刻意不提供跨单位的周总量汇总字段**（`volume_unit` 值域 `{min, reps, unspecified}`，相加就是 Task 5 F1-1 那个「混合量纲 float」错误）——**不写进 docstring，Plan 03 的前端会自己把 `min` 和 `reps` 加起来** |
| **P8-A2** | **Critical** | `volume_unit` 的第三档 **`"unspecified"`** 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档 `weekly_volume` 恒为 **`0.0`**；而 `apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里** → `weekly_training_sheet` **一定会吃到它**。**计划对这一档只字未提。** | 照原样带出、不特殊处理（`0.0 × factor = 0.0`），但**必须有一条吃真仓的测试**（红层模板 + 体脂异常触发 → 断言那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`）。**与计划自己给 `auto` 来源立的那条纪律同构**：不给它测试，Plan 03 就会撞上一个「结构上支持、逻辑上没测过」的路径 |
| P8-A3 | Important | `TrainingPackage` 实测有 **`paused: bool = False`**，而 `weekly_training_sheet` 吃到 `paused=True` 的包该返回什么，**计划完全没定**。 | **`WeeklySheet` 加 `paused: bool` 字段**（从 `pkg.paused` 直接抄），`paused=True` 时 `sessions` **原样保留**（与 Task 5 的 5.4 决定逐字一致）。**否掉「抛 `ValueError`」**：读模型的职责是**投影**不是校验。**「暂停」与「本周量为 0」是两件不同的事**，`paused` 字段就是为了不让前端把两者静默合并 |
| P8-A4 | Important | `weekly_factors_of` 实测**今天不存在**（`prescription_stage.py` 里 0 命中；它的公开函数是 `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions` + 5 个私有）。`weekly_adjustment` 表**今天 0 行**（`auto` 来源是 Plan 03、`teacher` 来源要等 Plan 03 的 CRUD API）。 | **照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试直接插 `WeeklyAdjustment` 行喂它，docstring 按硬规矩 #39 写明「今天没有生产调用方」。⚠️ **排序必须显式**：`created_at` 是 `DateTime NOT NULL 无缺省` → **`ORDER BY created_at, id`**（`id` 作 tie-breaker，同一秒批量插入时 `created_at` 相等——**与 Task 5 的 5.4「多条覆盖由列表顺序决定」同一条理由**），并有一条测试钉住它 |
| P8-A5 | Important | `WeeklyFactor.source` 的值域有**两个住址**：DB 侧 `ck_weekly_adjustment_source` ∈ `{auto, teacher}`（Task 6 的 `_in_domain` + 类常量 `SOURCES`）；domain 侧是裸 `str`。 | domain 侧**不另立词表**，但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {"auto", "teacher"}`，**放 pipeline 层**（domain 不能 import ORM）。与 Task 5 的 P5-A9 同一条纪律 |
| P8-A6 | Minor | `factor` 的 `(0, 2]` 由 `__post_init__` 校验，而 DB 的 `weekly_adjustment.factor` 列**没有 CHECK**。 | **两层守卫、不是重复**。DB 那一层**刻意不加**：`(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界。理由写进 `weekly.py` 的 docstring |
| P8-A7 | Minor | Task 6 的 `triggers.py` 实测用 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，domain 不能 import `datetime`）。 | `current_week` 用**同一口径**：`week = (as_of - generated_on).days // 7 + 1`。⚠️ **`.days // 7` 对负数向下取整**（`-1 // 7 == -1`）→ **必须先判 `.days < 0` 再算**，配一条 `as_of == generated_on - 1 day → None` 的测试（**不是 0、不是 1**）。**另配一条跨模块一致性测试**：「`current_week` 返回 `None`」与「`MICROCYCLE_EXPIRED` 成立」在到期日那一格**同真**——**这是两个模块口径不漂的唯一守卫** |
| P8-A8 | Minor | 实测三层 `volume_unit` 分布 = **红 `{min, reps}` / 黄 `{min}` / 绿 `{min}`**；`hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**（Ruling 133：130 个 block 里 82 个是 `type: none`）。 | 「缩放不动 `hr_zone`」那条测试**必须用红层模板**（`RED-END-ABN-01`）。**用黄层绿层写是恒真式（假绿）**——那两层所有 block 的 `hr_zone` 本来就是 `None` |

**实测的三套真仓装配数据**（给实现者对拍用，`as_of = 2026-10-08`、男 20 岁、`endurance_score = 70` → 档 `mid` → `1.0`、性别 `1.0`）：
- `RED-END-ABN-01`：`weeks=4`、`sessions/周 = [4,4,4,4]`、`volume_unit = {min, reps}`、第 1 周 8 个 block 的量 = `[48.0 min, 120.0 reps] × 4`、`delta = [1.0, 1.05, 1.1, 0.85]`
- `YEL-END-NOR-08`：`sessions/周 = [3,3,3,3]`、`volume_unit = {min}`、第 1 周 6 个 block 全是 `36.0 min`
- `GRN-END-NOR-14`：`sessions/周 = [2,2,2,2]`、`volume_unit = {min}`、第 1 周 4 个 block 全是 `24.0 min`
- 三套的 `paused` 都是 `False`

**扫描面**：新建 `app/domain/prescription/weekly.py` → domain 15 → **16**，扫描面 **34 → 35**。

**计划正文更正**：`_t8_preflight_patch.py`，**6 处替换全部命中 1 次**（硬规矩 #79）。

**⚠️ 硬规矩 #86 的回扫**（本 Task 结案时要扫 Task 9）：Task 9 的黄金用例要断言 `weekly_volume`（第 1 周）——**而 `weekly_volume` 自 Task 5 起带 `volume_unit`**，故 Task 9 的 `expected` 里**必须连单位一起钉**（`{"weekly_volume": 38.4, "volume_unit": "min"}`），只钉那个 float 会漏掉「单位串了」这个失效形态。

**下一步**：抽 `task-8-brief.md` → 派实现者。**按 Ruling 145，目标 1–2 轮；本 Task 小，控制者预期 0–1 轮。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 153" not in lt, "Ruling 153 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)} "
      f"CRLF={c2.count(chr(13)+chr(10))} LF={c2.count(chr(10))}")
for k in ("Ruling 153", "P8-A1", "P8-A8", "unspecified", "RED-END-ABN-01"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")
