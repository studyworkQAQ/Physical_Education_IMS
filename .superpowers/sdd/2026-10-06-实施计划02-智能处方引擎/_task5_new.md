## Task 5: 处方装配（简化版）—— `intensity.py` + `assembler.py` + `safety.py` + `override.py`

> **本节是原 Task 5/6/7/8 四节的合并（用户裁定，2026-10-08）。** 裁定原文：「后端其实只要不出太大的 bug 就行，后端算法层面要求不是很高……够产出合理的 4 周训练包即可，不追求参数保真度」。
>
> **合并砍掉了什么**：① `HrmaxFormula` 枚举与 FOX 公式（只留 Tanaka；`hrmax` 只有一个生产调用点，将来要加公式不破坏任何契约）；② 三档系数的 10 组参数化穷举（改成「每个分支至少一条」）；③ 闰年生日与 `age_from` ↔ Plan 01 龄组的漂移测试（周岁算法与 Plan 01 `age_group_of` 的上游同源，漂移风险由 Task 7 的端到端测试兜住）；④ 装配器与覆盖的独立变异轮次（只保留**安全关键**的 4 条变异，见 Step 4）；⑤ 原 Task 6 的 `formula` 形参（简化后恒为 Tanaka，快照里的 `"formula"` 键恒为 `"tanaka"`）。
>
> **合并没有砍掉什么（硬要求，一条都不许少）**：① `app/domain/` 分支覆盖 **100%**（spec §12，简化版不豁免）；② 安全规则的严格比较符 + 「没测不得讲成测了没问题」+ 「找不到等价动作不得静默跳过」（Review Focus 第 5 条）；③ `assembly_snapshot` 的键集字面钉死（spec §4.3 可追溯性的处方侧落点）；④ 年龄异常响亮拒绝（Review Focus 第 4 条）；⑤ 覆盖不改模板、`reason` 非空。
>
> **执行强度按用户同日裁定「保正确性、砍文档精度」**：本 Task 目标是 **1–2 轮 fix round**，不是 3–6 轮。散文里的数字若与实测有出入，**记进报告的「待清扫」清单、不单独开一轮**（控制者在结案时一次性清扫）。

**Files:** Create `backend/app/domain/prescription/intensity.py`、`assembler.py`、`safety.py`、`override.py` + `backend/tests/domain/test_prescription_{intensity,assembler,safety,override}.py`；Modify `backend/app/domain/prescription/__init__.py`（公开面重导出）、`backend/tests/test_refdata_prescription.py`（`_PRESCRIPTION_PUBLIC_BASELINE` 24 → 新值）

---

### 5.1 `intensity.py` —— HRmax 与目标心率区间

**Produces:**
- `hrmax(age: float, measured: float | None = None) -> float`：`measured is not None` 时校验 `60 <= measured <= 220`（越界抛 `ValueError`）后直接返回；否则 Tanaka `208 − 0.7 × age`。`age <= 0 or age >= 100` → 抛 `ValueError`，**消息里含实际收到的年龄**（排障用）。
- `hr_zone(hrmax_bpm: float, low_pct: float, high_pct: float) -> tuple[int, int]`：低界 `math.floor`、高界 `math.ceil`（**保守方向：区间略宽比略窄安全**）。`low > high` / `low < 0` / `high > 100` → `ValueError`。
- `age_from(birth: dt.date, as_of: dt.date) -> int`：**周岁**（生日未过则减 1），不是「年份相减」。`as_of` 由调用方注入，domain 不碰时钟。

**决定：**
- **`hrmax` 不返回 `None`、不静默夹取**（Review Focus 第 4 条）。理由：Tanaka 在 `age = 0` 时给 208 bpm，那是一个**看起来完全正常**的数字，会被装配成一个危险的目标心率区间。**静默产出荒谬值比崩溃危险。**
- **`measured` 参数不被任何生产路径调用**：Plan 01/02 **没有任何心率数据**（`fitness_test_result` 的 8 个原始列里没有心率）。按硬规矩 #39 在 docstring 里写明「为将来的穿戴设备留口，今天只有测试调它」。
- **不实现 FOX 公式**（简化）。spec §14 #14 已把「Tanaka 还是 `220 − 年龄`」列为待确认事项；本 Task 只落 Tanaka，将来切换只改 `intensity.py` 一处，**不需要为此今天就抽象出一个枚举**。

---

### 5.2 `assembler.py` —— spec §7.3 的六步

**Consumes:** Task 3 的 `Template` / `Block` / `Intensity`、5.1 的三个函数、Plan 01 的 `app.domain.indicators.ITEM_BUCKET`

**Produces:**
- `StudentProfile`（frozen dataclass）：`student_id: int` / `sex: Sex` / `birth: dt.date` / `age: int` / `endurance_score: float | None` / `bmi: float | None` / `body_fat_pct: float | None` / `muscle_mass_kg: float | None` / `muscle_p10: float | None` / `measured_hrmax: float | None`
- `AssembledBlock`（frozen）：`exercise_ref` / `exercise_name` / `video_url` / `impact_level` / `intensity_text: str` / `hr_zone: tuple[int,int] | None` / `structure: dict` / `weekly_volume: float`
- `AssembledSession`（frozen）：`day` / `focus` / `blocks: tuple[AssembledBlock, ...]`
- `AssembledWeek`（frozen）：`week: int`（1-based）/ `delta: float` / `sessions: tuple[AssembledSession, ...]`
- `TrainingPackage`（frozen）：`template_id` / `template_version` / `weeks: tuple[AssembledWeek, ...]` / `assembly_snapshot: dict` / **`paused: bool = False`**
  （`paused` 由 5.4 的 `OverrideKind.PAUSE` 置位，但**字段在本节就定义**——否则 5.4 要回头改一个已定稿的产出类型，那是 Plan 01 吃过 6 次的亏：改了 Interfaces 却没改照抄它的 Step，硬规矩 #11。装配器一律产出 `paused=False`。）
- `assemble(profile: StudentProfile, template: Template, as_of: dt.date, *, exercises: Mapping[str, ExerciseSpec]) -> TrainingPackage`

**六步口径：**

| 步 | 口径 | 决定 |
|---|---|---|
| 1 HRmax | 优先实测，无则 Tanaka | `profile.measured_hrmax` 非空则用它，否则 `hrmax(profile.age)`。**`profile.age` 由调用方从 `birth` 与 `as_of` 算好传入**（不让装配器自己碰日期，避免两个所有者）；但装配器要**校验** `age == age_from(birth, as_of)`，不一致抛 `ValueError`——这是一个廉价的一致性闸门，能挡住「调用方用了错误的 `as_of`」 |
| 2 目标心率区间 | 模板给百分比 → 个体绝对 bpm | 只对 `intensity.type == "hrmax_pct"` 的 block 算；`onerm_pct` / `rpe` / `none` 的 `hr_zone` 是 `None`，`intensity_text` 渲染对应文字（如「70% 1RM」）。**不要给非心率类动作硬塞一个心率区间** |
| 3 周训练总量 | 模板基准量 × 个体修正系数 | 见下「三档系数」 |
| 4 4 周递进 | 套用 `progression.week_deltas` | 第 N 周的 `weekly_volume` = 基准量 × 个体修正系数 × `week_deltas[N-1]`。**`len(week_deltas) != microcycle_weeks` 在加载时已被 Task 3 拒绝**，装配器不重复校验，但仍要抛 `ValueError`（它可能被喂进一个手工构造的 `Template`），并有一条测试钉住它不是静默截断 |
| 5 动作视频 URL | 从 `exercises` 注入的映射取 | 装配器**不读 DB**（domain 纯净性），`exercises` 由调用方注入。`exercise_ref` 不在映射里 → 抛 `ValueError`（Task 3 的加载校验是第一道，这是第二道；**两道都要有**） |
| 6 快照 | 全部输入输出写入 `assembly_snapshot` | 键**字面固定 12 个**：`formula`（简化后恒 `"tanaka"`）/ `hrmax` / `age` / `as_of` / `endurance_score` / `volume_factor` / `volume_factor_band` / `sex_factor` / `template_id` / `template_version` / `week_deltas` / `weekly_volume_base`。**这一列是 spec §4.3 可追溯性在处方侧的落点**——有了它，任一条处方都能离线复算。加一条测试：同一 `profile` + 同一 `template` + 同一 `as_of` 装配两次，`assembly_snapshot` **逐字段相同**（`as_of` 是 `date` 不是 `datetime`，故不含执行时刻） |

**三档系数（spec 最欠定的一步，口径自己定 + 登记 spec §14 #32）：**
- `endurance_score` = `vital_capacity` 与 `distance_run` 两项国标得分的**算术均值**（`float`，因为 `ITEM_BUCKET` 把这两项归 endurance 桶）。两项里只有一项有值时**取那一项、不取半值**；两项都无值时为 `None`。
- 档位：**`< 60` → `0.8`、`[60, 80)` → `1.0`、`>= 80` → `1.2`**（**半开、无缝无叠**——Ruling 9 更正原文的「`60–79`」：`endurance_score` 是两项得分的 float 均值，`79.5` 会落在 `(79, 80)` 的缝里，而 500 人里可能只有个位数、分布断言完全测不出来）。
- 性别修正：男 `1.0` / 女 `0.9`。**最终系数 = 档位系数 × 性别系数**，四舍五入到 2 位。
- `endurance_score is None`（两项都缺测）→ 用 `1.0`，并在 `assembly_snapshot` 里记 `"volume_factor_fallback": "endurance_score_missing"`。
- ⚠️ 这套阈值**指导文件没给**。必须在 spec §14 补一项（#32，归 Task 9），并在 `assembler.py` 的 docstring 里明写「本表是工程约定，不是运动生理学结论，须由体育专家确认」。

**⚠️⚠️ Ruling 133 —— 本 Task 的头号约束**（Task 3 实现者发现、控制者独立实算坐实）：18 套模板的 **130 个 block 里有 82 个是 `intensity: {type: none}`**；按层统计 `intensity.type` 是 **绿 `{none}` / 黄 `{none}` / 红 `{hrmax_pct, none, onerm_pct}`**。spec §7.2 `:487` **只给了红层的强度数值**（60–70% HRmax、70% 1RM），黄层绿层只有动作名。推论：

- **「模板没给强度」是常态、不是例外。** `intensity_text` 必须有一档**显式**渲染它（决定：`"模板未指定强度（spec §7.2 只给了红层数值，见 spec §14）"`），**不得**回落到 `hrmax_pct` 的默认值、**不得**留空字符串。
- 这 82 个 block 的 `hr_zone` 一律 `None`。
- **必须有一条测试直接吃真仓 YAML**（不是手工构造的 `Template`）：加载一个黄层模板 + 一个绿层模板，`assemble` 成功、所有 block 的 `hr_zone is None`、所有 `intensity_text` 非空。**这条测试是「简化版装配器真能跑通 18 套模板」的唯一守卫。**
- 只有红层的 `hrmax_pct` block 会走心率换算路径 → **心率相关的测试必须用红层模板或手工构造的 `hrmax_pct` block**。用黄层写会全绿、但什么也没测（假绿）。

**Step 1: 写失败测试（`intensity` + `assembler`）**

- [ ] `intensity`（约 8 条）：Tanaka 字面值（`hrmax(20) == 194.0`、`hrmax(18) == 195.4`、`hrmax(25) == 190.5`——**期望值自己算，不要照抄派单**，硬规矩 #44）/ `age <= 0` 与 `age >= 100` 拒绝且消息含年龄 / `measured` 优先 / `measured` 越界拒绝 / `hr_zone` 保守取整（**字面写死**，并构造一个能暴露取整方向的例子）/ `hr_zone` 非法百分比拒绝（`low > high`、`low < 0`、`high > 100`）/ `age_from` 周岁（生日当天与生日前一天各一条）。

- [ ] `assembler`（约 13 条，**每个分支至少一条，不做穷举矩阵**）：
  - `test_hrmax_uses_tanaka_when_no_measured_value` / `test_hrmax_prefers_the_measured_value`
  - `test_hrmax_inconsistent_age_is_rejected`（第 1 步的一致性闸门）
  - `test_hr_zone_only_for_hrmax_pct_blocks`（`onerm_pct` 的 block `hr_zone is None` 且 `intensity_text` 含「1RM」）
  - `test_intensity_none_blocks_get_an_explicit_text_and_no_hr_zone`（**Ruling 133 那条吃真仓 YAML 的测试**）
  - `test_volume_factor_three_bands` —— 三档各一条 + **一组**边界（`59.9/60.0` 或 `79.9/80.0`，字面写死系数）
  - `test_volume_factor_falls_back_when_endurance_score_missing`
  - `test_four_week_progression_applies_week_deltas_in_order`（第 4 周的量必须**小于**第 1 周，`week_deltas` 末项 0.85）
  - `test_every_block_carries_a_video_url_from_the_exercise_library`
  - `test_unknown_exercise_ref_is_rejected_at_assembly_time`
  - `test_week_deltas_length_mismatch_is_rejected_not_silently_truncated`
  - `test_assembly_snapshot_is_reproducible`（第 6 步）
  - `test_assembly_snapshot_keys_are_exactly_the_pinned_set`（键集字面写死——**多一个键或少一个键都要红**，这列是离线复算的契约）

**Step 2: 跑失败 → 实现 → 跑通**

- [ ] 先跑一遍确认新测试全红（且红的原因是「模块不存在 / 断言不符」，不是 import 错误之外的意外）
- [ ] 实现 `intensity.py` 与 `assembler.py`，跑到新测试全绿
- [ ] 全量 `pytest -q` 不退步（基线 **592 passed**，`dfa7580`）

---

### 5.3 `safety.py` —— spec §7.4 的三触发

**Consumes:** 5.2 的 `TrainingPackage` / `AssembledBlock`、Task 2 的 `EquivalenceTable` / `ImpactLevel`

**Produces:**
- `SafetyInput`（frozen）：`bmi: float | None` / `muscle_mass_kg: float | None` / `muscle_p10: float | None` / `body_fat_abnormal: bool`
- `Substitution`（frozen）：`week` / `day` / `original_ref` / `substitute_ref` / `trigger: str` / `equivalence_version: str`
- `SafetyOutcome`（frozen）：`package: TrainingPackage` / `substitutions: tuple[Substitution, ...]` / `needs_review: bool` / `warnings: tuple[str, ...]`
- `apply_safety(pkg: TrainingPackage, inp: SafetyInput, eq: EquivalenceTable) -> SafetyOutcome`

| 触发 | 条件 | 动作 |
|---|---|---|
| BMI > 30 | `inp.bmi is not None and inp.bmi > 30` | ① 跑量乘 `volume_reduction["bmi_over_30"]`；② 所有 `impact_level == HIGH` 的动作 → 查 `exercise_equivalence.yaml` 换低冲击等价动作 |
| 肌肉量 < 同龄同性别 **P10** | `muscle_mass_kg is not None and muscle_p10 is not None and muscle_mass_kg < muscle_p10` | 同上（系数用 `volume_reduction["muscle_low_p10"]`），**并提高抗阻模块比重** |
| 体脂率异常 | `body_fat_abnormal` | 追加**模板自己的** `addons` 中的能量消耗模块 |

**决定（安全关键，一条不许砍）：**
- **比较符一律严格 `<` / `>`**，与 Plan 01 的 P25（spec §14 #21）和体脂率阈值（`BODY_FAT_LIMIT`，`derive.py:68-69` 明写「严格大于」）**同口径**。每条都要有**恰在边界上**的测试（`bmi == 30.0` 不触发、`muscle_mass == muscle_p10` 不触发）。
- **`bmi is None` / `muscle_mass_kg is None` / `muscle_p10 is None` 都不触发**，且在 `assembly_snapshot` 里留痕（`"safety_skipped": ["bmi_missing"]`）。**这是 Plan 01 Ruling 134 的同一条纪律**：「没测」不得被讲成「测了且没问题」——安全规则静默跳过比不跳过危险。
- **「跑量按映射表下调」的口径 spec 没给**：系数来自 Task 2 已落地的 `exercise_equivalence.yaml` 顶层 `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}`，`apply_safety` 把命中触发的系数**乘到每个 block 的 `weekly_volume` 上**（两个触发都命中则相乘 = `0.72`）。⚠️ **这两个系数指导文件没给**，已登记 spec §14 **#28**（Task 2 落地时按 P2-A3「值在哪一刻被写死就在哪一刻登记」原则追加）。`safety.py` 的 docstring 里明写「工程约定，须专家确认」。
- **「提高抗阻模块比重」的口径 spec 也没给**：**不改动作**，只在 `SafetyOutcome.warnings` 里加一条 `"muscle_low_p10: 建议提高抗阻模块比重（本原型未自动调整，需教师确认）"`，并把处方置 `needs_review`。**理由：自动重排训练结构超出了「后置处理」的语义，而 spec §7.4 只说了「提高比重」没说怎么提。宁可不自动**（这正是 §7.4 末段的原则）。⚠️ 这一处置**尚未登记 §14**：Task 9 Step 2 复核 #28 的正文是否已覆盖它，没覆盖就追加为 **#35**。
- **找不到等价动作 → 不静默跳过**（Review Focus 第 5 条，spec §7.4 末段原文）：`needs_review = True`，`warnings` 里写明「哪个动作、哪个触发、映射表版本」，**该 block 原样保留**（不删除、不替换）。**「原样保留」是决定**：删掉动作会让训练量静默缩水，而保留 + `needs_review` 让教师看见。
- **`apply_safety` 是纯函数**：不改传入的 `TrainingPackage`（frozen dataclass，用 `dataclasses.replace` 产出新的）。加一条测试证明入参未被修改。
- **优先级高于模板定义**（spec §7.4 原文）：加一条测试——模板里写 `impact_level: high` 的动作，在 BMI > 30 时**必须**被换掉，即使模板「明确要」它。
- ⚠️ **已知不对称（Task 3 记录，本 Task 不修，只在报告里复述）**：`hiit`（`impact_level: high`、等价表里**有**映射）与 `energy_expenditure_plus_5min_hiit`（`medium`、**无**映射）→ BMI>30 的黄层学生会「主项被换掉、追加模块原样保留」。这是**数据面的事实**，不是代码缺陷。
- ⚠️ **绿层 `addons: []` 与 spec §7.4 `:510` 的冲突**（Task 3 已登记）：体脂异常但模板无 addon 时，`apply_safety` **不凭空造模块**，只留一条 warning。

**Step 3a: 写失败测试（`safety`，约 12 条）→ 实现 → 跑通**

- [ ] 三个触发 × {命中, 不命中, 恰在边界, 输入缺失} = 12 条起步，另加：
  - `test_missing_equivalent_sets_needs_review_and_keeps_the_block`（Review Focus 第 5 条）
  - `test_substitution_records_carry_the_equivalence_version`（spec §7.4 明写要记「映射表版本号」）
  - `test_safety_overrides_the_template`（优先级）
  - `test_apply_safety_does_not_mutate_its_input`
  - `test_body_fat_abnormal_appends_the_template_addon`（addon 来自**模板**，不是硬编码——`addons: []` 的绿层模板在体脂异常时**不应**凭空多出一个模块）
  - `test_both_triggers_multiply_the_volume_reduction`（`0.8 × 0.9 = 0.72`，字面写死）

---

### 5.4 `override.py` —— spec §7.5 的五种教师覆盖

**Produces:**
- `OverrideKind(str, Enum)`：`WEEKLY_FREQUENCY` / `SUBSTITUTE_EXERCISE` / `INTENSITY_STEP` / `VOLUME_SCALE` / `PAUSE`（spec §7.5 的五种：周训练天数、替换单个动作、调整强度档位、整体降量/加量、暂停处方）
- `OverrideRecord`（frozen）：`kind` / `target: str | None`（周次或 `exercise_ref`）/ `old_value: str` / `new_value: str` / `reason: str` / `teacher_staff_no: str` / `applied_at: dt.datetime`
- `apply_overrides(pkg: TrainingPackage, records: Sequence[OverrideRecord]) -> TrainingPackage`
- `summarize_overrides(records) -> dict[str, int]`（按 `kind` 计数，供 spec §7.5 末段「学期末回答教师在哪些环节最不信任算法」）

**决定：**
- **覆盖不修改模板**（spec §7.5 原文）：`apply_overrides` 只作用于 `TrainingPackage`，且是纯函数。加一条测试证明模板对象未被修改。
- **下次自动生成回到算法基线、不继承覆盖**（spec §7.5 原文）：这不是 `override.py` 的职责，而是 **Task 6** 的触发逻辑——生成时**不读**上一张处方的 override 记录。集成测试放 Task 6 的 Step 6。
- **`applied_at` 由调用方注入**（domain 不碰时钟）。
- **`PAUSE` 的语义**：**原样保留 `weeks`、把 5.2 已定义的 `paused` 置 `True`**——因为「暂停」是可撤销的，删掉 `weeks` 就不可逆了。
- **`reason` 不得为空**：`OverrideRecord.__post_init__` 校验 `reason.strip()` 非空。理由：spec §7.5 末段说这些记录是研究数据（「教师在哪些环节最不信任算法」），一条没有理由的覆盖对研究毫无价值。**这与 Plan 01 给 `WeaknessResult` 加 `count == len(items)` 不变量是同一个手法。**
- **`old_value` / `new_value` 是 `str`**（不是各自类型的联合）：它们要落进 `prescription.teacher_overrides` 这个 JSON 列，异构类型会让 JSON 结构不稳定。**用 `str` 并在 docstring 里写明每种 `kind` 的取值约定**（如 `VOLUME_SCALE` 是 `"0.8"`、`SUBSTITUTE_EXERCISE` 是动作 ref）。
- **多条覆盖同一目标 → 由列表顺序决定，后者胜**（不用 `applied_at`：同一秒批量操作时它相等，而调用方持有真实顺序）。加一条测试钉住这个决定。

**Step 3b: 写失败测试（`override`，约 8 条）→ 实现 → 跑通**

- [ ] 五种 `kind` 各一条（命中即可，**不做穷举边界**），另加：`test_override_does_not_mutate_the_template` / `test_override_records_are_applied_in_order` / `test_empty_reason_is_rejected` / `test_pause_keeps_the_weeks_and_sets_the_flag` / `test_summarize_overrides_counts_by_kind`（期望 dict 字面写死）/ `test_substitute_exercise_rejects_an_unknown_ref`

---

### 5.5 收尾

**Step 4: 变异验收（只做安全关键的 4 条）**

- [ ] ① `bmi > 30` → `>= 30` → 边界测试红；② 删掉「找不到等价动作 → `needs_review`」→ Review Focus 第 5 条的测试红；③ 删掉 `age <= 0` 的守卫 → 拒绝测试红；④ 把 `hr_zone` 的取整方向反过来 → 保守取整测试红。
- [ ] **每条变异按硬规矩 #65 写明「哪个断言分支开火」，并按 M0/M1 双对照取证**（M0：不变异时全绿；M1：语义等价改写后仍全绿——证明尺子不恒红）。变异后**三重还原**（还原代码、重跑、确认 sha256 与变异前一致）。

**Step 5: 公开面 + 全量 + 覆盖率 + Commit**

- [ ] `__init__.py` 重导出四个模块的公开名；`_PRESCRIPTION_PUBLIC_BASELINE` 从 24 个 `(名字, 所有者模块)` 二元组扩到新值（**新值自己数并字面写死**，同时改同文件里那句 `assert len(...) == 24`）。
- [ ] `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → **Miss 0 / BrPart 0 / 100%**（简化版**不豁免这一条**，spec §12 是硬要求）。
- [ ] `tests/architecture` 两份守卫全绿。⚠️ 新增 4 个 domain 模块会让扫描面从 **28** 涨到 **32**（pipeline 7 + db 11 + domain 14）；**涨了要在报告里说明**，别让人以为是守卫失效。
- [ ] 全量 `pytest -q` 的 passed 数**自己数**（基线 592，硬规矩 #44：期望值不得照抄派单）。
- [ ] Commit（信息用 python 写 UTF-8 临时文件 + `git commit -F`）。
