"""新 Task 5 预检更正：13 处（P5-A1..A13），逐条 assert 命中次数。

取证脚本：t5_probes/_t5_probe{1,2,3,4}.py（全部控制者本机实跑，基线 dfa7580 / 592 passed）
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
    assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:100]!r}"
    text = text.replace(old, new)
    edits.append((label, n))


# ===================== 0. 插入预检更正总表 =====================
PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `dfa7580`，取证脚本 `t5_probes/_t5_probe{1,2,3,4}.py`）

本节是**合并后的新 Task 5** 的预检结果。合并把四节的正文压成一节，**压缩过程中没有重新核对四节各自引用的量**，于是撞出 4 条 Critical——其中 **P5-A1 与 P5-A3 与 Ruling 133 同型**（计划引用一个 YAML 里根本不存在的量）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P5-A1** | **Critical** | `Block.structure` 实测**只有两种键集、无第三种、无交集**：**时长类 78 个** `{sets, work_min, rest_min}`（例 `{sets:4, work_min:3, rest_min:2}`）、**次数类 52 个** `{rounds, reps}`（例 `{rounds:3, reps:10}`）。78 + 52 = 130 ✓。**没有任何名为 `weekly_volume` / `volume` / `base` 的键。** | 计划 5.2 第 3/4 步说的「模板基准量」**不存在**。定口径见下方 5.2 的「⚠️ P5-A1」段：时长类 `base = work_min × sets`（分钟/课）、次数类 `base = rounds × reps`（次/课）、`rest_min` **不计入量**；两种单位不可通约 → `AssembledBlock` **必须新增 `volume_unit` 字段** |
| **P5-A2** | **Critical** | 同一模板内同一 `exercise_ref` **跨 session 重复，18/18 全部如此**。全体 130 个 block 的「一周内出现次数」分布 = **`{2: 24, 3: 42, 4: 64}`**，按层是 **绿全 2 / 黄全 3 / 红全 4**，即**恒等于 `weekly_frequency`**（每个动作在一周的每一课都出现，无一例外）。 | `weekly_volume` 若只是「单次课的量」就**名不符实**（叫 weekly 却是 per-session）。定口径：**`weekly_volume = base × sessions_per_week`**，`sessions_per_week` 由装配器**实测统计**（不假设它等于 `weekly_frequency`），并**新增 `sessions_per_week` 字段**留痕 |
| **P5-A3** | **Critical** | `addons.when` 实测 = **`{body_fat_over: 12, muscle_low: 12}`**；`addons.module` = **`{resistance_priority: 12, energy_expenditure_plus_10pct: 6, energy_expenditure_plus_5min_hiit: 6}`**。分布完全规整：**绿层 6 套全部 `addons: []`**；红层 6 套 = `(body_fat_over → energy_expenditure_plus_10pct)` + `(muscle_low → resistance_priority)`；黄层 6 套 = `(body_fat_over → energy_expenditure_plus_5min_hiit)` + `(muscle_low → resistance_priority)`。 | 原计划只把 addons 挂在「体脂率异常」上，而肌肉量那一行写的是「不自动、只 warning」→ **12 个 `when: muscle_low` 的 addon 永远不会被消费，是模板里的死数据**。**更正：肌肉量 < P10 触发时追加 `when == "muscle_low"` 的 addon**——这**正是** spec §7.4「并提高抗阻模块比重」的落地方式（追加一个 `resistance_priority` 模块，**不重排任何既有结构**）。原判断「无法自动化」是错的 |
| **P5-A4** | **Critical** | `tests/architecture/test_domain_purity.py` 的 `ALLOWED_MODULES` 实测 = `{dataclasses, enum, collections, collections.abc, numpy, typing}`。**`math` 不在其中**；两份守卫里 `math` 出现 **0 次**。 | 计划 5.1 写的 `math.floor` / `math.ceil` **会让纯净性守卫变红**。**更正：不改守卫**（往 allow-list 加模块是扩大 domain 可用面的架构决策），改用 `int(x)`（向下）与 `-(-x // 1)`（向上）。⚠️ `int()` 只在**正数**上等价于 `floor` → `hr_zone` 必须**新增一条 `hrmax_bpm <= 0` 拒绝**的守卫 |
| P5-A5 | Important | `intensity.type` 实测分布 = **`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24**，而 `INTENSITY_TYPES` 有 **4** 个值 → **`rpe` 在真仓出现 0 次**。形状完全规整：`hrmax_pct` → `low`+`high`（各 24）、`onerm_pct` → `value`（24）、`none` → 三者全空（82）。 | `rpe` 那一档**不可达但必须被覆盖**（domain 分支 100%）→ 用**手工构造**的 `Intensity(type="rpe", value=13)` 测。`Intensity.value` 的语义随 `type` 变（`onerm_pct` 是百分比、`rpe` 是 6–20），写进 docstring |
| P5-A6 | Important | 实测 `0.8 * 0.9` = **`0.7200000000000001`**（IEEE754），不是 `0.72`。 | 计划要求「0.72 字面写死」→ 直接相乘的测试**会红**。定口径：`weekly_volume` 的最终值 **`round(x, 1)`**；系数本身用 `pytest.approx`。（`round` 后仍是有限 float，不触 `allow_nan=False` 的 JSON 纪律） |
| P5-A7 | Important | **原计划自相矛盾**：5.2 第 6 步说 `assembly_snapshot` 的键「字面固定 **12** 个」并列出 12 个，但同一节的决定段又要求写 `"volume_factor_fallback"`，5.3 又要求写 `"safety_skipped"`——**这两个键都不在那 12 个里**。 | 拆成两段契约：**`assemble` 产出恰好 12 个键**（字面钉死，多一个少一个都红）；**`apply_safety` 在其上追加至多 3 个键**（`safety_triggers` / `safety_skipped` / `safety_volume_factor`，字面钉死这 3 个名字）。`endurance_score is None` 时**不加**第 13 个键，改成 `volume_factor_band = "unknown"`（信息已在 band 里） |
| P5-A8 | Important | `impact_level` 有**两个住址**：`Block.impact_level`（模板 YAML）与 `ExerciseSpec.impact_level`（动作库 YAML）。Task 3 已验证 130 个 block 零不一致。 | 定口径：**装配器从 `ExerciseSpec`（动作库）取 `impact_level`，不从 `Block` 取**。理由：`exercises.yaml` 是 `impact_level` 的**源**（它是 `exercise` 表的 seed 源），模板里的是**冗余副本**；安全规则必须读源，否则「专家改了动作库、忘了改 18 套模板」会让安全替换静默失效（Global Constraint #3） |
| P5-A9 | Important | **两套不同名的触发词表**：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`）、`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。实测 YAML 的 `addons.when` 取值 = `ADDON_TRIGGERS` ✓ | `SafetyInput` 的三个输入必须**显式映射**到这两套词表。定口径：`safety.py` 里字面写死映射 `{"bmi_over_30": None, "muscle_low_p10": "muscle_low", "body_fat_abnormal": "body_fat_over"}`（BMI>30 **不追加** addon——实测模板里没有 `when: bmi_over_30` 的 addon），并各加**一条漂移测试**字面钉住两个上游词表（防上游改名后静默失配）。词表的所有者仍是 `templates.py` / `exercises.py`，`safety.py` 只**消费** |
| P5-A10 | Minor | `BODY_FAT_LIMIT` 实测**只有 `derive.py` 的一行定义**（`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`）+ 一处消费；计划 5.3 写的是「`derive.py:68-69`」，**行号口径错**，且「明写严格大于」的引文控制者未核。 | 按硬规矩 #78 改成**可 grep 的原文片段**，不写裸行号；「严格大于」的说法降级为「与 Plan 01 同口径，由实现者复核引文后写明」 |
| P5-A11 | Minor | `Sex` 实测住在 **`app/domain/indicators.py`**（`class Sex(str, Enum)`）。计划 5.2 的 `StudentProfile.sex: Sex` **没写它从哪 import**。 | 补明：`from app.domain.indicators import Sex`（**绝对导入**，与 `match.py` 引 `Layer` 同口径） |
| P5-A12 | Minor | 加载器实测有 8 个公开函数：`load_exercises(path=None)` / `exercises()` / `load_equivalence(path=None)` / `equivalence()` / `load_templates(directory=None)` / `templates()` / `sync_exercises(session)` / `sync_templates(session)`。 | 5.2/5.3 要求「吃真仓 YAML」的测试用 **`exercises()` / `templates()` / `equivalence()` 三个进程内单例**，不用 `load_*`（后者每次重解析 18 份 YAML，还各跑一遍 `yaml.compose` 建行号索引）。⚠️ 单例是**进程内共享**的，测试里**不得改写**它 |
| P5-A13 | — | **控制者错误 #139**：预检时用了一个**自己没验证过的正则**（`\\(\\s*"`）去数 `_PRESCRIPTION_PUBLIC_BASELINE` 的二元组个数，数出 **3**；而同一个文件里就有字面断言 **`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`**，且 `len(__all__) == 24` 双重坐实。 | 计划的「24 个二元组」**是对的，探针是错的**。→ **补硬规矩 #80：用一个探针去数一个已经有字面断言的量，是多此一举且必然自相矛盾——先读那条断言。** 依据：这是「把自己没验证的工具输出当事实」的第 8 次（前 7 次见硬规矩 #53/#57/#59/#60/#76/#77） |

**扫描面复核（计划 5.5 的数字，实测**正确**，无需更正）**：`app/domain` **10** 个 `.py` + `app/pipeline` **7** + `app/db` **11** = **28**；Task 5 新增 4 个 domain 模块 → domain **14** → 扫描面 **32** ✓

"""
sub("**Files:** Create `backend/app/domain/prescription/intensity.py`、`assembler.py`、`safety.py`、`override.py`",
    PRE + "**Files:** Create `backend/app/domain/prescription/intensity.py`、`assembler.py`、`safety.py`、`override.py`",
    1, "P5 插入预检更正总表")

# ===================== 1. 5.1 hr_zone 不用 math =====================
sub("- `hr_zone(hrmax_bpm: float, low_pct: float, high_pct: float) -> tuple[int, int]`："
    "低界 `math.floor`、高界 `math.ceil`（**保守方向：区间略宽比略窄安全**）。"
    "`low > high` / `low < 0` / `high > 100` → `ValueError`。",
    "- `hr_zone(hrmax_bpm: float, low_pct: float, high_pct: float) -> tuple[int, int]`："
    "低界**向下**取整、高界**向上**取整（**保守方向：区间略宽比略窄安全**）。"
    "`low > high` / `low < 0` / `high > 100` → `ValueError`；"
    "**`hrmax_bpm <= 0` → `ValueError`（P5-A4 新增）**。" + nl
    + "  ⚠️ **P5-A4：不许 `import math`**——`ALLOWED_MODULES` 实测只有 "
    "`{dataclasses, enum, collections, collections.abc, numpy, typing}`，加 `math` 会让纯净性守卫变红。"
    "用 **`int(x)`**（向下）与 **`-(-x // 1)`**（向上）。"
    "**`int()` 只在正数上等价于 `floor`**（`int(-0.5) == 0` 而 `floor(-0.5) == -1`），"
    "故上面那条 `hrmax_bpm <= 0` 的拒绝**不是可选的**——它是这个等价关系成立的前提，"
    "必须在 docstring 里写明这层因果。",
    1, "P5-A4 hr_zone 不用 math")

# ===================== 2. 5.2 AssembledBlock 加两个字段 =====================
sub("- `AssembledBlock`（frozen）：`exercise_ref` / `exercise_name` / `video_url` / `impact_level` / "
    "`intensity_text: str` / `hr_zone: tuple[int,int] | None` / `structure: dict` / `weekly_volume: float`",
    "- `AssembledBlock`（frozen）：`exercise_ref` / `exercise_name` / `video_url` / `impact_level` / "
    "`intensity_text: str` / `hr_zone: tuple[int,int] | None` / `structure: dict` / "
    "`weekly_volume: float` / **`volume_unit: str`（P5-A1 新增，∈ `{\"min\", \"reps\", \"unspecified\"}`）** / "
    "**`sessions_per_week: int`（P5-A2 新增，>= 1）**" + nl
    + "  ⚠️ **`impact_level` 从 `ExerciseSpec`（动作库）取，不从 `Block`（模板）取**（P5-A8）："
    "`exercises.yaml` 是源、模板里的是冗余副本；安全规则读副本会在「专家改了动作库、忘了改 18 套模板」时静默失效。",
    1, "P5-A1/A2/A8 AssembledBlock 字段")

# ===================== 3. 5.2 第 3 步的「模板基准量」口径 =====================
sub("| 3 周训练总量 | 模板基准量 × 个体修正系数 | 见下「三档系数」 |",
    "| 3 周训练总量 | **每课基准量 × 周内课次 × 个体修正系数** | "
    "**⚠️ P5-A1：「模板基准量」这个字段不存在**，见下方「P5-A1 的基准量口径」；"
    "个体修正系数见下方「三档系数」 |",
    1, "P5-A1 第3步表格")
sub("| 4 4 周递进 | 套用 `progression.week_deltas` | 第 N 周的 `weekly_volume` = 基准量 × 个体修正系数 × `week_deltas[N-1]`。",
    "| 4 4 周递进 | 套用 `progression.week_deltas` | 第 N 周的 `weekly_volume` = "
    "**每课基准量 × `sessions_per_week`** × 个体修正系数 × `week_deltas[N-1]`，**`round(…, 1)`**（P5-A6）。",
    1, "P5-A1/A6 第4步表格")

BASE = """
**⚠️ P5-A1 的基准量口径（`Block.structure` 里没有「量」这个字段，必须自己定，登记 spec §14 新 #36）**

实测 `structure` **只有两种键集、无第三种、无交集**（78 + 52 = 130 ✓）：

| 形状 | 个数 | 键集 | 例 | `base` 口径 | `volume_unit` |
|---|---|---|---|---|---|
| 时长类 | **78** | `{sets, work_min, rest_min}` | `{sets:4, work_min:3, rest_min:2}` | **`work_min × sets`** | `"min"` |
| 次数类 | **52** | `{rounds, reps}` | `{rounds:3, reps:10}` | **`rounds × reps`** | `"reps"` |

- **`rest_min` 不计入量**（它是恢复、不是负荷）。**理由要写进 docstring**：把休息算进训练量会让「减量 20%」同时缩短恢复时间，而对红层学生缩短恢复是危险的。
- **两种单位不可通约** → `volume_unit` 是**必需字段**，不是可选修饰。一个裸 `float` 无法回答「38.4 是分钟还是次数」，那会让 spec §4.3 的可追溯性断在这一环。
- **`structure` 既不是这两种形状之一 → 抛 `ValueError`**，**不得静默取 0**（量变 0 会让训练包看起来完全正常、而每个 block 都是空的）。Task 3 的加载器是否已经钉死了这两种形状，**实现者要复核**：若已钉死，装配器仍要抛（它可能被喂进手工构造的 `Template`），但**不重复校验键的类型**（单一所有者）。
- **`sessions_per_week` 由装配器实测统计**（数该 `exercise_ref` 在 `template.sessions` 里出现几次），**不假设它等于 `weekly_frequency`**。实测它今天恰好恒等（分布 `{2:24, 3:42, 4:64}` = 绿全 2 / 黄全 3 / 红全 4），但那是**数据的性质、不是结构的保证**——专家完全可以让某个动作只出现在 2 课里。
  → 配一条守卫测试：断言真仓 18 套模板里**每个 block 的 `sessions_per_week` 都等于该模板的 `weekly_frequency`**。**这条测试今天全绿**；它的价值是「专家改坏了会立刻变红提示」，而装配器**仍按实测统计**（正确行为，不因为测试而假设）。

**可字面写死的算例（控制者实算，`RED-END-ABN-01` 第 1 课，`weekly_frequency = 4`、`week_deltas = [1.0, 1.05, 1.1, 0.85]`）：**

| block | intensity | structure | base | ×4 | 男 20 岁、`endurance_score = 50`（档 `<60` → 0.8，性别 1.0，系数 **0.8**） |
|---|---|---|---|---|---|
| `interval_run` | `{type: hrmax_pct, low: 60, high: 70}` | `{sets:4, work_min:3, rest_min:2}` | `3×4 = 12` min/课 | **48.0 min/周** | 第 1 周 `48.0×0.8×1.00 = `**`38.4`**；第 4 周 `48.0×0.8×0.85 = 32.64 → `**`32.6`** |
| `compound_circuit` | `{type: onerm_pct, value: 70}` | `{rounds:3, reps:10}` | `3×10 = 30` reps/课 | **120.0 reps/周** | 第 1 周 **`96.0`**；第 4 周 `120.0×0.8×0.85 = 81.6 → `**`81.6`** |

`interval_run` 的心率区间：`hrmax(20) = 208 − 0.7×20 = `**`194.0`**；`hr_zone(194.0, 60, 70)` = `(int(116.4), -(-135.8 // 1))` = **`(116, 136)`**。
`compound_circuit` 的 `hr_zone` = **`None`**、`intensity_text` 含「1RM」。

⚠️ **期望值自己算、不要照抄这张表**（硬规矩 #44）。这张表是给实现者**对拍**用的：算出来不一样，先怀疑自己、再怀疑表，**两边都要写进报告**。
"""
sub("**三档系数（spec 最欠定的一步，口径自己定 + 登记 spec §14 #32）：**",
    BASE + "\n**三档系数（spec 最欠定的一步，口径自己定 + 登记 spec §14 #32）：**",
    1, "P5-A1 插入基准量口径")

# ===================== 4. 5.2 第 6 步快照键集（P5-A7） =====================
sub("| 6 快照 | 全部输入输出写入 `assembly_snapshot` | 键**字面固定 12 个**：`formula`（简化后恒 `\"tanaka\"`）/ `hrmax` / `age` / `as_of` / "
    "`endurance_score` / `volume_factor` / `volume_factor_band` / `sex_factor` / `template_id` / `template_version` / "
    "`week_deltas` / `weekly_volume_base`。",
    "| 6 快照 | 全部输入输出写入 `assembly_snapshot` | 键**字面固定 12 个**：`formula`（简化后恒 `\"tanaka\"`）/ `hrmax` / `age` / `as_of` / "
    "`endurance_score` / `volume_factor` / `volume_factor_band` / `sex_factor` / `template_id` / `template_version` / "
    "`week_deltas` / `weekly_volume_base`。**⚠️ P5-A7：这 12 个是 `assemble` 的完整契约，一个都不许多**"
    "（原文另要求的 `volume_factor_fallback` 会是第 13 个键，与本行自相矛盾 → 已删，改用 `volume_factor_band = \"unknown\"` 承载）；"
    "`apply_safety` 的追加键见 5.3。`volume_factor_band` 的值域字面固定为 `{\"low\", \"mid\", \"high\", \"unknown\"}`；"
    "`weekly_volume_base` = **未乘个体系数、未乘 `week_deltas` 的周量总和**（`float`，`round(…, 1)`）。",
    1, "P5-A7 快照 12 键")
sub("- `endurance_score is None`（两项都缺测）→ 用 `1.0`，并在 `assembly_snapshot` 里记 "
    "`\"volume_factor_fallback\": \"endurance_score_missing\"`。",
    "- `endurance_score is None`（两项都缺测）→ 用 `1.0`，并把 `volume_factor_band` 置 **`\"unknown\"`**"
    "（**P5-A7：不另加第 13 个键**——信息已在 band 里，而「12 个键」是离线复算的契约，多一个键就废了）。",
    1, "P5-A7 fallback 键（原文形态）")

# ===================== 5. 5.2 StudentProfile 的 Sex import（P5-A11） =====================
sub("- `StudentProfile`（frozen dataclass）：`student_id: int` / `sex: Sex` / `birth: dt.date`",
    "- `StudentProfile`（frozen dataclass）：`student_id: int` / `sex: Sex`"
    "（**P5-A11：`from app.domain.indicators import Sex`，绝对导入**，与 `match.py` 引 `Layer` 同口径）"
    " / `birth: dt.date`",
    1, "P5-A11 Sex 住址")

# ===================== 6. 5.2 测试清单补 P5-A1/A2/A5 =====================
sub("  - `test_assembly_snapshot_keys_are_exactly_the_pinned_set`（键集字面写死——**多一个键或少一个键都要红**，这列是离线复算的契约）",
    "  - `test_assembly_snapshot_keys_are_exactly_the_pinned_set`（键集字面写死——**多一个键或少一个键都要红**，这列是离线复算的契约）\n"
    "  - `test_volume_base_uses_the_right_formula_per_structure_shape`（**P5-A1**：时长类与次数类各一条，"
    "用上面那张算例表的字面值）\n"
    "  - `test_rest_min_is_not_counted_as_volume`（**P5-A1**：把 `rest_min` 从 2 改成 20，`weekly_volume` 必须**不变**）\n"
    "  - `test_unknown_structure_shape_is_rejected_not_zeroed`（**P5-A1**：喂一个 `{\"foo\": 1}` 的 structure → `ValueError`）\n"
    "  - `test_weekly_volume_is_base_times_sessions_per_week`（**P5-A2**：`RED-END-ABN-01` 的 `interval_run` → `48.0`）\n"
    "  - `test_every_block_appears_in_every_session_of_the_real_templates`（**P5-A2 的守卫**：真仓 18 套，"
    "每个 block 的 `sessions_per_week == template.weekly_frequency`）\n"
    "  - `test_impact_level_comes_from_the_exercise_library_not_the_template`（**P5-A8**：把模板里的 "
    "`impact_level` 改成与动作库矛盾的值 → 装配结果**仍取动作库的**）\n"
    "  - `test_rpe_intensity_renders_text_without_an_hr_zone`（**P5-A5**：手工构造 "
    "`Intensity(type=\"rpe\", value=13)`，真仓无此档）",
    1, "P5-A1/A2/A5/A8 补测试")

# ===================== 7. 5.3 肌肉量触发改成追加 addon（P5-A3） =====================
sub("| 肌肉量 < 同龄同性别 **P10** | `muscle_mass_kg is not None and muscle_p10 is not None and muscle_mass_kg < muscle_p10` | "
    "同上（系数用 `volume_reduction[\"muscle_low_p10\"]`），**并提高抗阻模块比重** |",
    "| 肌肉量 < 同龄同性别 **P10** | `muscle_mass_kg is not None and muscle_p10 is not None and muscle_mass_kg < muscle_p10` | "
    "同上（系数用 `volume_reduction[\"muscle_low_p10\"]`），**并追加 `when == \"muscle_low\"` 的 addon**"
    "（**P5-A3 更正**：这就是 spec §7.4「并提高抗阻模块比重」的落地方式） |",
    1, "P5-A3 肌肉量触发行")
sub("| 体脂率异常 | `body_fat_abnormal` | 追加**模板自己的** `addons` 中的能量消耗模块 |",
    "| 体脂率异常 | `body_fat_abnormal` | 追加**模板自己的** `when == \"body_fat_over\"` 的 addon（能量消耗模块） |",
    1, "P5-A3 体脂行")
sub("- **「提高抗阻模块比重」的口径 spec 也没给**：**不改动作**，只在 `SafetyOutcome.warnings` 里加一条 "
    "`\"muscle_low_p10: 建议提高抗阻模块比重（本原型未自动调整，需教师确认）\"`，并把处方置 `needs_review`。"
    "**理由：自动重排训练结构超出了「后置处理」的语义，而 spec §7.4 只说了「提高比重」没说怎么提。宁可不自动**"
    "（这正是 §7.4 末段的原则）。⚠️ 这一处置**尚未登记 §14**：Task 9 Step 2 复核 #28 的正文是否已覆盖它，没覆盖就追加为 **#35**。",
    "- **「提高抗阻模块比重」的口径 —— ⚠️ P5-A3 更正原决定**：原文判成「无法自动化、只加 warning、置 `needs_review`」，"
    "**这是错的**：实测 18 套模板里有 **12 个 `when: muscle_low` / `module: resistance_priority` 的 addon**"
    "（红层 6 + 黄层 6，绿层 6 套全是 `addons: []`），按原决定它们**永远不会被消费**，是模板里的死数据。"
    "**更正：肌肉量 < P10 触发时追加 `when == \"muscle_low\"` 的 addon**——追加一个 `resistance_priority` 模块"
    "**不重排任何既有结构**，因此它既落地了 spec §7.4 的「提高抗阻模块比重」，又没有越过「后置处理」的语义边界。" + nl
    + "  - `warnings` 的文本随之改成：`\"muscle_low_p10: 已追加 resistance_priority 模块；如需进一步调整抗阻比重，"
    "请用教师覆盖（OverrideKind.VOLUME_SCALE / SUBSTITUTE_EXERCISE）\"`。" + nl
    + "  - **`needs_review` 不再由这一条单独置位**——只在「找不到等价动作」时置位（Review Focus 第 5 条）。"
    "理由：既然已经自动追加了模块，就不存在「宁可不自动」的问题了。" + nl
    + "  - ⚠️ 这一处置仍**须登记 §14**：Task 9 Step 2 复核 #28 的正文是否已覆盖它，没覆盖就追加为 **#35**。",
    1, "P5-A3 更正抗阻比重的处置")

ADDON = """
**⚠️ P5-A3 的追加口径（addon 怎么变成 `AssembledBlock`，spec 完全没给，登记 §14 新 #35）**

`Addon` 实测只有两个字段：`when: str` / `module: str`（`module` 是动作库里的 ref，**Task 3 的加载器已校验过它存在**，故这里**不重复校验**——单一所有者）。**没有 `structure`、没有 `intensity`、没有 `day`。** 定口径：

| `AssembledBlock` 字段 | 追加的 addon block 取值 | 理由 |
|---|---|---|
| `exercise_ref` | `addon.module` | — |
| `exercise_name` / `video_url` / `impact_level` | 从 `exercises[addon.module]` 取 | 与主项同一来源（P5-A8） |
| `intensity_text` | `"附加模块（模板未指定强度，见 spec §14）"` | 与 Ruling 133 那一档同一措辞口径 |
| `hr_zone` | `None` | 非心率类 |
| `structure` | `{}` | 模板没给 |
| **`weekly_volume`** | **`0.0`** | **见下** |
| **`volume_unit`** | **`"unspecified"`** | **见下** |
| `sessions_per_week` | `template.weekly_frequency` | 附加模块每天都做 |

**`weekly_volume = 0.0` 是决定，不是偷懒。** 备选方案都被否掉了：
- ❌ **按 ref 名字硬编码规则**（`energy_expenditure_plus_10pct` → 周时长总量的 10%、`…_plus_5min_hiit` → `5.0 × sessions_per_week`）：这要给 3 个 module 各写一条硬编码，**专家加第 4 个 module 就静默失效**，而且把量化规则写进代码等于从 `exercises.yaml` 手里抢走所有者（Global Constraint #3）。
- ❌ **取同 session 内既有 block 的均值**：单位可能不同（时长类 vs 次数类），跨单位平均是无意义的数；且「均值」会让附加模块的量随主项漂移，教师无法预期。
- ✅ **置 `0.0` + `volume_unit = "unspecified"` + 一条 warning**：**spec 没给附加模块的量，编造一个数就是把「不知道」讲成「知道」**——这与 Plan 01 Ruling 134、以及本节已有的「没测不得讲成测了没问题」是**同一条纪律**。
  - `0.0` 对下游**零副作用**：`0.0 × 0.8 = 0.0`（减量乘法）、Task 8 的 `WeeklySheet` 缩放同理。
  - 教师可以用 `OverrideKind.VOLUME_SCALE` 给它一个量 → **这恰好是 spec §7.5 末段「教师在哪些环节最不信任算法」的一个真实数据点**。
  - warning 文本：`"addon <module> 的训练量未指定（weekly_volume = 0.0），需教师用 VOLUME_SCALE 覆盖"`。
  - **`volume_unit` 的第三档 `"unspecified"` 就是为它加的**（P5-A1 的值域已含）。

**追加到哪个 session？** 决定：**追加到每一个 session 的 `blocks` 末尾**（因为 `sessions_per_week = weekly_frequency`）。追加**不改变既有 block 的顺序**（`day` / `focus` / 主项次序全部原样），故 `test_apply_safety_does_not_mutate_its_input` 与 Task 8 的读模型都不受影响。
"""
sub("- ⚠️ **绿层 `addons: []` 与 spec §7.4 `:510` 的冲突**（Task 3 已登记）：体脂异常但模板无 addon 时，"
    "`apply_safety` **不凭空造模块**，只留一条 warning。",
    "- ⚠️ **绿层 `addons: []` 与 spec §7.4 `:510` 的冲突**（Task 3 已登记；**P5-A3 实测坐实：绿层 6 套全部 `addons: []`**）："
    "体脂异常或肌肉量偏低但模板无对应 addon 时，`apply_safety` **不凭空造模块**，只留一条 warning。\n"
    + ADDON,
    1, "P5-A3 插入 addon 追加口径")

# ===================== 8. 5.3 触发词表映射（P5-A9） =====================
sub("**决定（安全关键，一条不许砍）：**",
    "**⚠️ P5-A9 的触发词表映射（两套不同名的词表，必须显式对上）**\n\n"
    "实测：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`，也是 YAML 里 `addons.when` 的取值域）、"
    "`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。"
    "**两套名字完全不同**，而 `SafetyInput` 给的是第三套（`bmi` / `muscle_mass_kg` / `muscle_p10` / `body_fat_abnormal`）。"
    "`safety.py` 里字面写死这张映射：\n\n"
    "```python\n"
    "# 键 = 本模块的触发名，值 = (volume_reduction 的键 or None, addons.when 的键 or None)\n"
    "_TRIGGER_MAP = {\n"
    '    "bmi_over_30":       ("bmi_over_30",    None),          # 实测模板里没有 when: bmi_over_30 的 addon\n'
    '    "muscle_low_p10":    ("muscle_low_p10", "muscle_low"),\n'
    '    "body_fat_abnormal": (None,              "body_fat_over"),  # 体脂异常不下调跑量，只追加模块\n'
    "}\n"
    "```\n\n"
    "配**两条漂移测试**，各自字面钉住上游词表（防上游改名后本映射静默失配）：\n"
    "`assert ADDON_TRIGGERS == frozenset({\"body_fat_over\", \"muscle_low\"})`、"
    "`assert EQUIVALENCE_TRIGGERS == frozenset({\"bmi_over_30\", \"muscle_low_p10\"})`。\n"
    "词表的所有者仍是 `templates.py` / `exercises.py`，**`safety.py` 只消费、不定义**（Global Constraint #3）。\n\n"
    "**决定（安全关键，一条不许砍）：**",
    1, "P5-A9 插入触发词表映射")

# ===================== 9. 5.3 的 snapshot 留痕改成 3 个键（P5-A7） =====================
sub("- **`bmi is None` / `muscle_mass_kg is None` / `muscle_p10 is None` 都不触发**，且在 `assembly_snapshot` 里留痕"
    "（`\"safety_skipped\": [\"bmi_missing\"]`）。",
    "- **`bmi is None` / `muscle_mass_kg is None` / `muscle_p10 is None` 都不触发**，且在 `assembly_snapshot` 里留痕。\n"
    "  **⚠️ P5-A7：`apply_safety` 追加的键字面固定为至多 3 个**——`safety_triggers`（命中的触发名列表）、"
    "`safety_skipped`（因输入缺失而跳过的项，如 `[\"bmi_missing\"]`）、`safety_volume_factor`"
    "（跑量下调的乘积，未命中则 `1.0`）。**`assemble` 那 12 个键一个都不许改**；这 3 个是安全层的显式追加，"
    "配一条 `test_safety_appends_at_most_three_snapshot_keys`（字面写死这 3 个名字）。",
    1, "P5-A7 安全层 3 个键")

# ===================== 10. 5.3 的 BODY_FAT_LIMIT 行号（P5-A10） =====================
sub("与 Plan 01 的 P25（spec §14 #21）和体脂率阈值（`BODY_FAT_LIMIT`，`derive.py:68-69` 明写「严格大于」）**同口径**。",
    "与 Plan 01 的 P25（spec §14 #21）和体脂率阈值（`BODY_FAT_LIMIT`，住在 `app/domain/derive.py`，"
    "**按可 grep 的原文找、不要按裸行号找**；P5-A10 实测它是**一行 dict 定义**"
    "`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}` + 一处消费，原文写的「`:68-69` 明写严格大于」"
    "**行号口径错、引文控制者未核**，由实现者复核后写明）**同口径**。",
    1, "P5-A10 BODY_FAT_LIMIT 行号")

# ===================== 11. 5.3 的 0.72（P5-A6） =====================
sub("`apply_safety` 把命中触发的系数**乘到每个 block 的 `weekly_volume` 上**（两个触发都命中则相乘 = `0.72`）。",
    "`apply_safety` 把命中触发的系数**乘到每个 block 的 `weekly_volume` 上**（两个触发都命中则相乘；"
    "**⚠️ P5-A6 实测 `0.8 * 0.9 == 0.7200000000000001`，不是 `0.72`** → 乘积用 `pytest.approx`，"
    "而 `weekly_volume` 一律 **`round(x, 1)`** 后再落进 dataclass，这样它的字面值才是稳定的）。",
    1, "P5-A6 0.72 浮点")
sub("  - `test_both_triggers_multiply_the_volume_reduction`（`0.8 × 0.9 = 0.72`，字面写死）",
    "  - `test_both_triggers_multiply_the_volume_reduction`（**P5-A6**：断言系数用 `pytest.approx(0.72)`，"
    "断言某个 block 的 `weekly_volume` 用 `round` 后的**字面值**——**不要写 `== 0.72`**，实测它是 `0.7200000000000001`）",
    1, "P5-A6 测试口径")

# ===================== 12. 5.3 测试清单补 P5-A3/A9 =====================
sub("  - `test_body_fat_abnormal_appends_the_template_addon`（addon 来自**模板**，不是硬编码——`addons: []` 的绿层模板在体脂异常时**不应**凭空多出一个模块）",
    "  - `test_body_fat_abnormal_appends_the_template_addon`（addon 来自**模板**，不是硬编码——`addons: []` 的绿层模板在体脂异常时**不应**凭空多出一个模块）\n"
    "  - `test_muscle_low_p10_appends_the_resistance_priority_addon`（**P5-A3**：红层或黄层模板 + 肌肉量 < P10 → "
    "每个 session 的 blocks 末尾多一个 `resistance_priority`，且**既有 block 的顺序与值全部不变**）\n"
    "  - `test_appended_addon_has_zero_volume_and_unspecified_unit`（**P5-A3**：`weekly_volume == 0.0`、"
    "`volume_unit == \"unspecified\"`、有一条 warning 点名该 module）\n"
    "  - `test_muscle_trigger_alone_does_not_set_needs_review`（**P5-A3**：只有「找不到等价动作」才置位）\n"
    "  - `test_trigger_word_lists_have_not_drifted`（**P5-A9**：两条字面断言钉住 `ADDON_TRIGGERS` 与 `EQUIVALENCE_TRIGGERS`）\n"
    "  - `test_bmi_over_30_appends_no_addon`（**P5-A9**：实测模板里没有 `when: bmi_over_30` 的 addon，映射表那一格是 `None`）\n"
    "  - `test_safety_appends_at_most_three_snapshot_keys`（**P5-A7**）",
    1, "P5-A3/A7/A9 补测试")

# ===================== 13. 5.5 的加载器单例（P5-A12） =====================
sub("- [ ] `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → "
    "**Miss 0 / BrPart 0 / 100%**（简化版**不豁免这一条**，spec §12 是硬要求）。",
    "- [ ] `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → "
    "**Miss 0 / BrPart 0 / 100%**（简化版**不豁免这一条**，spec §12 是硬要求）。\n"
    "- [ ] **P5-A12：吃真仓 YAML 的测试用 `exercises()` / `templates()` / `equivalence()` 三个进程内单例**，"
    "**不用 `load_exercises` / `load_templates` / `load_equivalence`**（后者每次重解析 18 份 YAML，"
    "还各跑一遍 `yaml.compose` 建行号索引）。⚠️ 单例是**进程内共享**的，测试里**不得改写**它"
    "（顶层是 `MappingProxyType`、`Block.structure` 是只读视图，但「改不动」不等于「不该试」）。",
    1, "P5-A12 加载器单例")

out = text.encode("utf-8")
PLAN.write_bytes(out)
print(f"[out] bytes={len(out)} lines={text.count(nl)}")
for lab, n in edits:
    print(f"  {n}x  {lab}")
