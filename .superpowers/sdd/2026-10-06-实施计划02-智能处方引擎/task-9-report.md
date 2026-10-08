# Plan 02 Task 9 实现者报告 —— 黄金用例延伸到训练包 + spec 勘误 + 9 条待清扫

**分支** `feature/plan-02-prescription-engine`　**基线** `88d7575`　**HEAD** `61078c4`
**4 个 commit**：`e7a01d2` / `7a18852` / `874b9f2` / `61078c4`　**未 push**
**测试** 793 → **807 passed**　**`app/domain/` 覆盖率** 996 stmts / Miss **0** / 288 branch / BrPart **0** / **100%**（未变）

---

## ① 环境与基线复现

**开工第一件事（硬规矩 #73）**：

```
$ python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__, pandas.__version__, numpy.__version__, yaml.__version__)"
2.1.3 3.0.6 2.4.6 6.0.3
```

**没有撞上 `ImportError: DLL load failed`**（Smart App Control 未拦 `.pyd`），故未触发「立刻停手交回控制者」那一档。Python 3.11.1、**无 venv**，与派单逐字一致。

| 项 | 派单给的基线 | 我实测（开工时） | 我实测（结案时） |
|---|---|---|---|
| 分支 / 基线 commit / 工作树 | `feature/plan-02-prescription-engine` / `88d7575` / 干净 | 逐字相符 | HEAD `61078c4`，`git status --porcelain` 空 |
| `python -m pytest -q` | 793 passed | **793 passed** in 113.63 s | **807 passed** in 84.98 s |
| `--cov=app.domain --cov-branch` | 996 / 0 / 288 / 0 / 100%，792 passed + 1 skipped | —（开工未跑 cov） | **996 / 0 / 288 / 0 / 100%**，806 passed + 1 skipped |
| 表数 / `prescription` 列 / `weekly_adjustment` 列 | 18 / 16 / 8 | — | **18 / 16 / 8** |
| `app.domain.prescription.__all__` | 51 | — | **51** |
| `_MODELS_PUBLIC_BASELINE` | 33（刻意不动，Ruling 97） | — | **未触碰**（`app.db.models.__all__` 实测 14，那个 33 是测试侧的基线常量，本 Task 一个字节没动） |
| 扫描面（`app/{pipeline,db,domain}` 的 `.py`） | 35 | — | **35** |
| 三个指纹 | CSV `D2C8E539E2FA0029` / exercises `3DE598AF38631209` / equivalence `822CB86A5E998301` | 逐字相符 | 见第 ④ 节 |

**+14 条测试的来源**：`test_golden_case_input_and_expected_align_one_to_one_by_student_id`（1）+ `test_golden_cases_reach_the_training_package`（13 例参数化）。`test_golden_case_path_defaults_the_three_new_inputs_to_none` 是**改名 + 换契约**，条数不变。

**取证脚本**（全部在 `$env:TEMP\t9\`，不入库）：`t9_patch.py`（字节安全的替换工具，逐文件保住既有行尾约定）、`t9_probe1.py`（13 例走完整条链路到训练包，逐例打印实测值）、`t9_probe2/3/4.py`（RST 表列宽）、`t9_probe5.py`（spec 的裸行号与 §14 行计数）、`t9_probe6.py`（收尾验收）、`t9_mutate4.py` / `t9_mutate_sex.py`（两条变异）。

⚠️ **本仓的工作树行尾是逐文件不同的**（`git ls-files --eol` 实测：`golden_cases.json` / spec / `run_stratify.py` / `daily.py` / `backfill.py` / `repo.py` / `test_repo.py` / `test_backfill.py` / `test_golden_cases.py` / `test_refdata_prescription.py` / `models/prescription.py` 都是 `i/lf w/crlf`，而 `assembler.py` / `weekly.py` / `test_prescription_stage.py` / `backend/data/*.yaml` 是 `i/lf w/lf`）。故**所有写文件都走 python**：读 `read_bytes()` → 折成 LF → 替换（每处 `old` 必须**恰好命中一次**，0 次或 >1 次当场 `SystemExit`）→ 按该文件既有约定折回 → `write_bytes()`。混合行尾一律拒绝动手。

---

## ② 13 例的新 `expected` 字段逐例列表 + 我怎么人读确认的（本 Task 的核心交付）

### ②.1 期望值的取法

照计划 Step 1 的原文：「跑一次生产、把输出粘进 fixture，然后**逐条人读确认**每个数字是对的……**不要 blindly 固化**」。

* **跑生产**：`t9_probe1.py` 走 `_from_golden_cases → evaluate → stratify → input_snapshot_of → match_template → _profile_of → assemble → apply_safety`，与 `prescription_stage.generate_prescriptions` 的**算法部分**同构；逐例打印 12 个格子 + 装配快照里的 `endurance_score` / `volume_factor_band` / `volume_factor` / `sex_factor` / `hrmax` / `week_deltas` / `safety_triggers` / `safety_skipped` / block 数 / warnings。
* **粘进 fixture**：`t9_e3_fixture.py`。**先做一次全文 round-trip 自证**——`json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n" == text` 必须成立，否则「我只加了 12 个键」会静默变成「我重排了整个夹具」，而那 13 例的 `note` 与 `explain` 是 Plan 01 逐条人读确认过的。实测成立。
* **⚠️ `expected` 是 list 不是 dict**：新键**逐例按 `student_id` 查表**写入（脚本里 `VALUES[sid]`），**不按位置**；且脚本自带前置自证——`label_at_generation` 必须与该例**已人读确认**的 `label` 逐字相等、`template_id[:3]` 必须与 `_LAYER3[label]` 相符，任一不符当场 `AssertionError`。故「加错一格 → 13 例集体张冠李戴」这个失效形态在写入侧就被挡住了；读取侧另有 `test_golden_case_input_and_expected_align_one_to_one_by_student_id`（P9-A4 要求的守卫）。

### ②.2 逐例列表（12 个新键）

`spw` = `sessions_per_week`；`base` = 每课基准量（§14 #36 的口径）；`delta` = `week_deltas[0]`，18 套模板一律 `1.0`；`vf` = 最终个体修正系数。

| sid | 性别/age | `bmi`（手算） | C | 主导桶 | `match_status` | `template_id` | `label_at_generation` | block0 `exercise_ref` | `endurance` → 档 | `vf` | base × spw × vf × delta | `weekly_volume` | `volume_unit` | `hr_zone`（手算） | `needs_review` | subs | `safety_triggers` | `safety_skipped` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GC01 | 男 19 | 78/1.75² = 25.469… → **25.5** | T | endurance | matched | RED-END-ABN-01 | red | interval_run | 30.0 → low | 0.8×1.0 = **0.8** | 12 × 4 × 0.8 × 1.0 = **38.4** | 38.4 | min | 194.7×60/100 = 116.82 → **116**；×70/100 = 136.29 → ceil **137** | false | 0 | body_fat_abnormal | muscle_p10_missing |
| GC02 | 男 21 | 62/1.80² = 19.135… → **19.1** | F | endurance | matched | RED-END-NOR-02 | red | interval_run | 30.0 → low | 0.8 | 12 × 4 × 0.8 = **38.4** | 38.4 | min | 193.3×0.6 = 115.98 → **115**；×0.7 = 135.31 → ceil **136** | false | 0 | （空） | muscle_p10_missing |
| GC03 | 女 19 | 52/1.63² = 19.572… → **19.6** | F | strength | matched | YEL-STR-NOR-10 | yellow | bodyweight_resistance | 60.0 → mid | 1.0×0.9 = **0.9** | 30 × 3 × 0.9 = **81.0** | 81.0 | reps | null（黄层 `intensity: none`） | false | 0 | （空） | muscle_p10_missing |
| GC04 | 男 19 | 76/1.72² = 25.683… → **25.7** | T | strength | matched | YEL-STR-ABN-09 | yellow | bodyweight_resistance | 50.0 → low | 0.8 | 30 × 3 × 0.8 = **72.0** | 72.0 | reps | null | false | 0 | body_fat_abnormal | muscle_p10_missing |
| GC05 | 女 21 | 62/1.60² = 24.219 → **24.2** | T | endurance | matched | YEL-END-ABN-07 | yellow | steady_run | 60.0 → mid | 0.9 | 12 × 3 × 0.9 = **32.4** | 32.4 | min | null | false | 0 | body_fat_abnormal | muscle_p10_missing |
| GC06 | 男 19 | 60/1.78² = 18.937… → **18.9** | F | strength | matched | YEL-STR-NOR-10 | yellow | bodyweight_resistance | 50.0 → low | 0.8 | 30 × 3 × 0.8 = **72.0** | 72.0 | reps | null | false | 0 | （空） | muscle_p10_missing |
| GC07 | 男 19 | 63/1.76² = 20.341… → **20.3** | F | endurance | matched | YEL-END-NOR-08 | yellow | steady_run | 30.0 → low | 0.8 | 12 × 3 × 0.8 = **28.8** | 28.8 | min | null | false | 0 | （空） | muscle_p10_missing |
| GC08 | 男 19 | 66/1.74² = 21.799… → **21.8** | F | endurance | matched | YEL-END-NOR-08 | yellow | steady_run | 50.0 → low | 0.8 | 12 × 3 × 0.8 = **28.8** | 28.8 | min | null | false | 0 | （空） | muscle_p10_missing |
| GC09 | 男 19 | 65/1.73² = 21.718… → **21.7** | F | endurance | matched | GRN-END-NOR-14 | green | orienteering | 40.0 → low | 0.8 | 12 × 2 × 0.8 = **19.2** | 19.2 | min | null | false | 0 | （空） | muscle_p10_missing |
| **GC10** | 女 19 | 55/1.65² = 20.202… → **20.2** | F | endurance | **no_layer** | **null** | **null** | **null** | — | — | — | **null** | **null** | **null** | **null** | **null** | **null** |
| GC11 | 男 19 | 70/1.79² = 21.842… → **21.8** | F | endurance | matched | GRN-END-NOR-14 | green | orienteering | 60.0 → mid | 1.0×1.0 = **1.0** | 12 × 2 × 1.0 = **24.0** | 24.0 | min | null | false | 0 | （空） | muscle_p10_missing |
| GC12 | 女 19 | 58/1.62² = 22.100… → **22.1** | T | endurance | matched | YEL-END-ABN-07 | yellow | steady_run | 60.0 → mid | 0.9 | 12 × 3 × 0.9 = **32.4** | 32.4 | min | null | false | 0 | body_fat_abnormal | muscle_p10_missing |
| GC13 | 男 19 | 70/1.79² = 21.842… → **21.8** | T | endurance | matched | YEL-END-ABN-07 | yellow | steady_run | 60.0 → mid | 1.0 | 12 × 3 × 1.0 = **36.0** | 36.0 | min | null | false | 0 | body_fat_abnormal | muscle_p10_missing |

**13 例里 12 例有处方、1 例（GC10）断言「无处方」**：`valid_count = 3 < 4` → Z0 闸门 → `Layer.INSUFFICIENT` → `match_template` 返回 `NO_LAYER`（Review Focus 第 3 条：不得生成处方，且必须留下可交代的痕迹——留痕的载体就是 `match_status` 本身，六种 status 没有一种静默返回 `None`）。GC10 的其余 10 个键一律 `null`，`bmi` 仍有值（`20.2`，它来自 `input_snapshot`，与有没有处方无关）。

### ②.3 我怎么人读确认的（逐类给判据，不是「我看了一遍」）

**A. `bmi`（13 例）** —— 探针**同时**打印了生产值与手算值 `round(w / (h/100)**2, 1)`，13/13 `agree=True`；我又对着 `input[i]["curr"]` 的 `height_cm` / `weight_kg` 逐例重列了算式（见上表第 3 列）。⚠️ 两侧不同源：手算那一侧是我自己写的 `round(w / (h / 100) ** 2, 1)`，**刻意不调 `bmi_of`**（硬规矩 #35，与 `tests/domain/test_derive.py` 那个 oracle 同一条纪律）。

**B. `template_id`（12 例）** —— 两个独立判据交叉：① 匹配键 `(层, 主导短板, C)` 三元与 `expected` 里**已人读确认**的 `label` / `dominant_bucket` / `C` 逐例对得上；② id 的形状 `<层3>-<桶3>-<体成分3>-<序号2>` 与 **spec §7.2 勘误 ⑥** 定下的枚举序（层 红→黄→绿 × 短板 耐力→力量→速度柔韧 × 体成分 **异常→正常**，全局序号 01–18）逐格对得上：RED 段 01–06、YEL 段 07–12、GRN 段 13–18，`git ls-files -- backend/data/prescription` 列出的 18 个文件名与之逐字相同。

**C. `weekly_volume`（12 例）** —— 计划特别点名「它依赖 Task 5（5.2）那个『spec 没给口径』的三档系数，人读时要确认**档位选对了**」。逐例核了四层：
1. **`endurance_score`**：耐力桶两项（`vital_capacity` / `distance_run`）国标得分的均值。探针打印的值（30 / 30 / 60 / 50 / 60 / 50 / 30 / 50 / 40 / — / 60 / 60 / 60）与我从 `curr` 的两项得分手算的一致。
2. **档位**：`< 60 → low(0.8)`、`[60, 80) → mid(1.0)`、`>= 80 → high(1.2)`。13 例里没有一例 ≥ 80，故 high 档**在黄金用例里不可达**（如实记进关切）。60.0 恰好落 mid（半开区间 `[60, 80)`），这一点逐例确认过 —— 若阈值写成闭区间「60–79」，`GC11`/`GC13` 的 `vf` 会从 1.0 变成 0.8，`weekly_volume` 从 24.0/36.0 变成 19.2/28.8。
3. **性别系数**：GC03 / GC05 / GC12 是女性 → 0.9，其余 9 例男性 → 1.0；与 `input[i]["sex"]` 逐例对上。`round(0.8 × 0.9, 2) = 0.72` 这一档 13 例里没有（低档 ∩ 女性为空），故 `round` 的承重性在黄金用例里不可见 —— 也记进关切。
4. **`sessions_per_week` 与 `base`**：`spw` 红 4 / 黄 3 / 绿 2（P5-A2 的实测分布），逐例与该例模板的层对上；`base` 只有两种 —— `interval_run` / `steady_run` / `orienteering` 是时长类 `{sets: 4, work_min: 3, rest_min: 2}` → `3 × 4 = 12`，`bodyweight_resistance` 是次数类 `{rounds: 3, reps: 10}` → `3 × 10 = 30`；**`rest_min` 不计入量**（§14 #36）。`delta` 一律 `week_deltas[0] = 1.0`（探针打印的 `deltas=[1.0, 1.05, 1.1, 0.85]` 18 套一致）。四者相乘再 `round(…, 1)`，12/12 与探针输出逐字相同。

**D. `hr_zone`（2 例非 null）** —— 只有红层的 GC01 / GC02：`hrmax = 208 − 0.7 × age`（GC01 age 19 → 194.7、GC02 age 21 → 193.3，两个都是精确 float），模板给 60–70% HRmax，**低界向下取整、高界向上取整**（保守方向）→ `[116, 137]` 与 `[115, 136]`。⚠️ 与 `intensity.py` docstring 里那个 `hr_zone(194.0, 60, 70) == (116, 136)` 的例子**不矛盾**：那是 age 20 的 194.0，这里两例的 age 是 19 与 21。其余 10 例是 `null` 而**不是遗漏** —— Ruling 133：真仓 130 个 block 里 82 个是 `intensity: {type: none}`（**绿层与黄层全部**），spec §7.2 只给了红层的强度数值（§7.2 勘误 ②、§14 #29）。

**E. `needs_review` / `safety_substitution_count`（12 例）** —— 全为 `false` / `0`，**且我能说清它为什么必然是 0**：`apply_safety` 只有在 `equivalence_triggers` 非空时才会进「HIGH 冲击 → 查等价表」那一支，而 `equivalence_triggers` 只由 `bmi_over_30` 与 `muscle_low_p10` 填充；13 例的 `bmi` 最大只有 **25.7**（< 30）、`muscle_p10` 恒 `None`，故等价表**根本没被查过**，`needs_review` 结构上无从置位。这不是「跑出来是 0 就抄个 0」，而是「判据不成立 → 必然 0」。

**F. `safety_triggers` / `safety_skipped`（12 例）** —— `body_fat_abnormal` 命中的 5 例（GC01 / GC04 / GC05 / GC12 / GC13）与该夹具里**已逐条人读确认**的 `C = true` 的 5 例**逐例完全吻合**，其余 7 例为空；`safety_skipped` 恒为 `["muscle_p10_missing"]`（`muscle_mass_kg` 13 例都有值 → 不出 `muscle_mass_missing`；`bmi` 13 例都有值 → **不出 `bmi_missing`，这正是 P9-A1 的效果**，改前恒为 `["bmi_missing", "muscle_p10_missing"]`）。

**G. `label_at_generation`（12 例）** —— 与 `expected[i]["label"]` 逐字相等，且 `template_id[:3]` 与 `_LAYER3[label]` 相符（写入脚本的前置断言）。⚠️ 按计划的告诫，**没有**把它写成两条互相印证的守卫：它与 `template_id` 不是两份独立证据（匹配器就是按 `Layer(label)` 选模板的），它多出来的那一份价值只是「与 `expected.label` 这个**已人读的字面量**同源比对」。

### ②.4 自证变异：证明这份「粘出来的」fixture 不是恒绿

派单不要求新变异，但这类 fixture 最大的风险正是恒绿，故额外跑了一条**只影响训练包、不影响分层标签**的生产变异：

| 变异 | 结果 |
|---|---|
| `assembler._SEX_FACTOR` 女性 `0.9 → 1.0` | `tests/integration/test_golden_cases.py` **3 failed / 15 passed**：红的恰好是 **GC03 / GC05 / GC12**（女性 ∩ mid 档；`week1_block0_weekly_volume` 应变 81.0→90.0 / 32.4→36.0 / 32.4→36.0，按 `base × spw × 1.0` 手算），而 `test_golden_cases_match_expected_labels` 与三条 500 人分布测试**全绿** |

即：① 新测试**不是恒绿**；② 它守的确实是「训练包」那一环、**没有越界去守标签**（这正是 P9-A4「不合并成一条」要的分离性）。按硬规矩 #83 的 `.pyc` 纪律做（前后 `shutil.rmtree(__pycache__)`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`），还原后复核 `OLD=1 NEW=0`、56 passed。

---

## ③ P9-A1：`_from_golden_cases` 的改动与那条守卫的契约变化

**改动**（`backend/app/pipeline/run_stratify.py`，唯一一处生产逻辑改动）：

```python
curr = case["curr"]                       # ← 新增一行，score_raw 也改吃这个局部名
curr_scores = score_raw(curr, sex, age_group, table)
...
height_cm=curr.get("height_cm"),          # 原为 case.get("height_cm")
weight_kg=curr.get("weight_kg"),          # 原为 case.get("weight_kg")
snapshot_muscle_p10=case.get("snapshot_muscle_p10"),   # 未变，仍是 None
```

**没有给夹具加顶层副本**，理由逐字照 P9-A1：身高体重的唯一住址是 `input[i]["curr"]`（与 `["prev"]`），夹具 `_meta.bmi` 逐字写着「**BMI 不在 input 里**：它由身高体重合成」；而 `score_raw` 合成 BMI **得分**读的也正是同一份 `raw`（`bmi_of(raw.get("height_cm"), raw.get("weight_kg"))`），故快照里的**原始值** BMI 与 `curr_scores["bmi"]` 的**得分**不可能来自两次不同的测量。加顶层副本 = 第二个住址（Global Constraint #3），漂移时两处静默对不上、同一例的输入自相矛盾。

**`.get()` 而不是硬下标**：`curr` 的 8 列都可能是 `null`（GC10 就有 3 项缺测），缺测时 `bmi` 为 `None` —— **绝不当 0**（Ruling 21：一个 `bmi = 0` 的快照会让「0 > 30」为假，学生静默躲过复核）。

**守卫的契约变化**（它不是「被删掉的守卫」）：

| | 改前 | 改后 |
|---|---|---|
| 名字 | `test_golden_case_path_defaults_the_three_new_inputs_to_none` | `test_golden_case_path_reads_height_and_weight_from_curr_and_leaves_p10_none` |
| `person.height_cm` / `weight_kg` | `is None` | `== 175.0` / `== 78.0`（来自 `curr`） |
| `person.snapshot_muscle_p10` | `is None` | **仍是 `is None`** |
| `snapshot["bmi"]` | `is None` | `== 25.5`（**手算的字面值**：`78.0 / 1.75² = 25.469387…` → `round(…, 1)`；不从 `bmi_of` 读回来跟自己比） |
| `snapshot["snapshot_muscle_p10"]` | `is None` | **仍是 `is None`** |
| 前置断言 | `assert absent not in case`（「夹具形状变了的话本条要重写」） | 保留，措辞改成「夹具顶层**刻意**不给这三键：住址是 `curr`」——谁把顶层副本加回来，本条当场红 |

**RED → GREEN 已亲验**：改 `_from_golden_cases` **之前**先改测试，跑出来是 `AssertionError: assert None == 175.0`（`person.height_cm`）；改完 `tests/pipeline/test_prescription_stage.py` **36 passed**。

⚠️ **`snapshot_muscle_p10` 为什么必须仍是 `None`，而且钉住它有额外价值**：13 人 < `MIN_SAMPLE = 30`、肌肉量组按 Ruling 121 第 4 步不产出行，而黄金用例路径**刻意不调** `resolve_muscle_lines`（P20 用夹具手工给定的值）。钉住它的第二个理由写在测试 docstring 里：防下一个人以为「忘了回填 P10」而顺手给黄金用例路径接上 `resolve_muscle_lines` —— 那会让 13 例的 **P20 也一起被 `None` 覆盖**（查表查不到），GC13 要测的「有这条线时 `C` 成立」当场失效。

**连带更新**：`_from_golden_cases` 里那段 P7-A2 的注释整段重写（它此前逐字写着「直到 Task 9 给 13 例补上顶层身高体重」，那正是被 P9-A1 撤回的做法），并点名两条新守卫。`PersonInputs` 的 docstring 未动（它对这三个字段的描述与来源无关，仍为真）。

---

## ④ P9-A3：指纹程序六步的逐步取证

⚠️ **这是 Plan 02 第一次动一个被指纹钉住的 `backend/data/` 文件**（前 8 个 Task 一个字节都没动过）。

| 步 | 动作 | 取证 |
|---|---|---|
| **0** | **备份原字节到 TEMP**（`$env:TEMP\t9\exercises.yaml.orig`） | 22739 bytes，备份自身指纹 `3DE598AF38631209`（与工作树一致，即备份成功）。⚠️ **还原一律用 python 从备份 `write_bytes` 写回，不用 `git checkout`**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70） |
| **1** | 记下改前指纹 | `exercises.yaml` = **`3DE598AF38631209`**，`crlf = 0`（与派单给的基线逐字相同） |
| **2** | 改 YAML（只改头注释里那 8 行） | `t9_patch.apply` 报 `eol=lf edits=1 bytes 22739 -> 23247`（`old` 恰好命中 1 次，0 次或 >1 次会当场 `SystemExit`） |
| **3** | **立刻用 `read_bytes()` 复核行尾** | `bytes=23247  crlf=0  lf=368` → **CRLF 计数仍为 0** ✅。`git ls-files --eol -- backend/data` 全部 23 个文件仍逐行 `i/lf w/lf attr/text eol=lf`（写成 CRLF 会让指纹与这条双双对不上） |
| **4** | 算新指纹 + 改常量 | 新指纹 `sha256(read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()` = **`5394B37F01DAC9AC`**；`tests/test_refdata_prescription.py` 的 `EXERCISES_FINGERPRINT` 同步，并在常量注释里补了「Task 9 又更新过一次」那一段（含「改的是注释、不是数据」与六步程序本身） |
| **5** | 跑指纹测试 | `tests/test_refdata_prescription.py` + `tests/test_refdata.py` **72 passed**（含 `test_exercises_yaml_fingerprint_is_pinned` / `test_equivalence_yaml_fingerprint_is_pinned` / `STANDARD_FINGERPRINT` 那条） |
| **6** | 复核另两个指纹**逐字不变** | 见下表 |

| 文件 | 改前 | 改后 | 判定 |
|---|---|---|---|
| `national_standard_2014.csv` | `D2C8E539E2FA0029` | **`D2C8E539E2FA0029`** | **逐字不变** ✅ |
| `exercises.yaml` | `3DE598AF38631209` | **`5394B37F01DAC9AC`** | 变了（预期）；`crlf = 0` ✅ |
| `exercise_equivalence.yaml` | `822CB86A5E998301` | **`822CB86A5E998301`** | **逐字不变** ✅ |

`git diff --stat -- backend/data` = **只有 `exercises.yaml`（12 insertions / 8 deletions）**；`git status --porcelain -- backend/data` 只有 ` M backend/data/exercises.yaml`。18 套模板 YAML 与 CSV 一个字节都没动 ✅。

**改了什么**：头注释里那 8 行「⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项（`volume_reduction` 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里……」——Task 9 一旦把 #30 写进 §14，那句话就成了假的。改成「✅ **已登记进 spec §14 第 30 项**」，并**留下编号几经易手的取证链**（`3ea27cc` 时是 #29 → `d40f36c` 把 #28 让给 `volume_reduction`、清单整体前移一位变成 #30 → Task 9 实测 §14 当时是「1–29 与 31 共 30 行、最大 31、#30 是空洞」，写入后 = 37 行 / 最大 37 / 无空洞），同时把控制者错误 #155 的成因与「数表格行一律用数换行 + 校验首尾两行」写进去。文件中部 `:124` 那句「已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项」**实测仍为真**（`volume_reduction` 确实登记在 #28），故未动。

⚠️ **改的是注释、不是数据**：24 个 `exercise_ref`、它们的五个键、`impact_level` 与 `video_url` 一个字节都没动，故 `exercise` 表的投影（`sync_exercises`）与装配出来的训练包逐字不变 —— 这一点由 807 passed 与第 ② 节那 12 例训练包期望值**仍然全绿**坐实。

---

## ⑤ spec 的勘误各处与 §14 七项

⚠️ **这是 Plan 02 第一次改 spec 正文**（前 8 个 Task 只改计划与账本），故每一处都按 Plan 01 的勘误格式：**原文 + 更正 + 理由 + Ruling/§14 编号**。spec 从 98755 → **128328 bytes**（`i/lf w/crlf`，工作树纯 CRLF 保住）。

### ⑤.1 五处勘误（逐处）

| 处 | 原文 | 更正 | 理由 | 编号 |
|---|---|---|---|---|
| **§1.3 canonical sha256** | `:45` 印 `fe0a44e052c7946b…` 与「行数合计 **882**」 | 追加一张两行表：**9 张**（Plan 01 的 `PIPELINE_TABLES`）= `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`、**882 行未变**；**11 张**（Task 7 之后）= `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`、**942** 行 = 882 + 60 处方 + 0 调整 | 9 张那一组变的原因**不是扩表**（`prescription` 不在那 9 张里），而是 `c5599db` 给 `input_snapshot` 加了 `"bmi"` 与 `"snapshot_muscle_p10"` 两个键；11 张那一组是 `c7f2edb` 扩表 + `f0623b3` 加列。**⚠️ `:45`「行数合计 882」对这 9 张仍然为真**，过期的是「9 张就是管道全部覆盖面」这个隐含前提（第 5 行原文「管道写的 9 张表」今天是 **11** 张） | P7-A6 / 账本 Ruling 152 |
| **§1.3 历史记录** | `:46` 终审 B 报的 886 行 / sha `2ef85d79…` / 基线 `728325a` / `percentile_snapshot` 28 行 → Ruling 214 → 24 行 → 886 → 882 | **一字未动**，新值**追加**在它后面，并在新段落开头显式写明「上面那段历史记录一字未动」 | 它是「**一个修复改变了另一个修复的取证基线**」的因果链，删掉就丢了 | Ruling 229 |
| **§1.3「两个值不被守卫」** | （原文没有这句） | 明写：这两个 sha **都不被任何守卫钉住** —— `test_rerunning_the_same_business_date_reproduces_every_table` 断言的是 `assert first == second`（两次**独立执行**之间的关系），不是与字面哈希相等 | 否则下一个人会以为改代码会让某条测试变红、白找一轮「哪条该红却没红」 | 硬规矩 #35/#39 |
| **§1.3 两条性能验收** | 第 1 行「单人处方生成 p95 < 3 秒 / API 性能测试断言」、第 2 行「500 人批量管道回放 < 60 秒 / 集成测试断言」 | 新增一段勘误：第 1 行**本计划从未测量过**、且连测量对象都不存在（`api/` 层要到 Plan 03）→ 应读作「**未测量，待 Plan 03**」；第 2 行**仍被守卫**但余量已从 3.2× 掉到 **2.03×**（Plan 01 `17.98–18.92 s` n=5 → Task 7 之后 `28.86 / 29.05 / 29.59 s` n=3），且它抓不到「慢但没超 60 s」 | 用户 2026-10-08 裁定删掉性能压测；计划原文要求「勘误要写明『未测量』，**不得**写成『已达标』」 | 用户裁定 + 硬规矩 #42 |
| **§4.4 `prescription_template`** | `:238`「id、层、主导短板、体成分（共 18 行）、**YAML 路径**、版本、`review.status`…」 | 那一列落的是 **`template_ref`（逻辑 id，形如 `RED-END-ABN-01`）**，18 个 YAML 的**路径不入库**；另交代 `reachable`（§7.2 勘误 ③）、`prescription.microcycle_weeks`（P6-A3）、`prescription.previous_had_overrides`（P6-A2）、`weekly_adjustment.batch_id`（P6-A8 + P7-A4 的子表先删） | 路径是**部署期事实**、`template_ref` 是**领域事实**；存路径会让「搬个目录 → 历史处方指向不存在的文件」，而 §1.3 的可追溯与 §4.3 都建立在「历史行指向的东西还在」之上。反查无损（加载器有「`template_id` 与文件名一致」的守卫）。⚠️ 同一串字符在 ORM 边界换名字（P6-A7） | 无新编号（「字面与实现不一致」，不是需要裁决的空洞）；§7.2 勘误 ③ 末尾预告过本条「留给 Task 12」 |
| **§4.6 `daily_sync_run`** | `:260` 的字段清单**没有 `muscle_line_gaps`**，且有「错误摘要」 | 增补 `muscle_line_gaps`（`Integer`，NOT NULL，缺省 0）= 缺肌肉量 P20 判定线的 (性别 × 年级组) 组数；`error_summary` 自 Plan 02 起**只承载真错误**，成功运行恒 `NULL` | ⚠️ **spec 全文并没有要求这一列** —— 它是 §6.3② 那条判定线「**可能根本不存在**」这个事实要求的留痕（Ruling 121 第 4 步：样本 < 30 整组不产出行，而肌肉量**没有国标常模可降级**）。「没有线」与「有线但没人低于它」在 `C` 上是两件事，后者能从 `stratification_result` 数出来、前者数不出来。此前写成自由文本塞进 `error_summary` 有两个毛病：列名与内容不符（明写「非错误」却住在 error_summary 里）、且是文本（大屏要排序就得把中文句子解析回整数） | 无新编号；Plan 02 Task 1 落地 / 终审 C 组第 24 项 / 账本 Ruling 13 |
| **§7.3 步骤 3** | `:532`「模板基准量 × 个体修正系数（按性别 + **当前耐力国标得分**分三档）」 | ① 「耐力国标得分」= `vital_capacity` 与 `distance_run` 两项国标得分的**算术均值**（只有一项时取那一项、不取半值；两项都无 → `None` → 系数 `1.0` + 档名 `unknown`，**连性别修正也不做**）；② 「模板基准量」在 `Block.structure` 里**没有对应字段**；③ 乘数还漏了两项，落地的算式是 `base × sessions_per_week × 个体修正系数 × week_deltas[N−1]`，`round(…, 1)` | ① `ITEM_BUCKET` 把这两项归 `endurance` 桶，取均值与 `find_weaknesses` 判主导桶是同一个合成方式（Ruling 100），两处口径一致才不会「主导短板是耐力、而修正系数按另一套耐力分算」；均值的**唯一所有者**是 `_endurance_score`。③ `weekly_volume` 是**周量**，同一 ref 一周内跨课重复（真仓 18/18），故必须乘 `spw`；`spw` 由装配器**实测统计**、不假设等于 `weekly_frequency`。⚠️ Task 8 的读模型**不摊**（P8-A1） | ① → **§14 #32**；② → **§14 #36**（与 #31 是同一空洞的两面，互相引用、不合并）；③ 无新编号 |

**复核 §7.2 的 6 条勘误（Task 3 写的）仍然成立，未改一字**：① `speed_flexibility` 桶 4 套红/黄模板确实存在（`RED-SPD-ABN-05` / `RED-SPD-NOR-06` / `YEL-SPD-ABN-11` / `YEL-SPD-NOR-12`，`git ls-files` 可见）；② 黄层与绿层全部 `intensity: none`（`assembler.py` 的 Ruling 133 那段实测 82/130，且第 ② 节 12 例里 10 例的 `hr_zone` 为 `null` 正是它的下游证据）；③ `reachable` 在模板与表里都有（`match_template` 读字段）；④ 绿层 6 套 `addons: []`（`safety.py` 那条 warning 的措辞逐字引用了它，且第 ② 节 12 例里没有绿层命中 `body_fat_abnormal`，故这一档在黄金用例里不可达）；⑤ `version: "1.0"` / `reviewed_at: "2026-10-06"` 带引号（加载成功且 `Template.version` 是 `str`）；⑥ `template_id` 的全局序号 01–18 与枚举序 —— 第 ② 节 B 项用它逐格验过 12 个 template_id。

### ⑤.2 §14 追加的 7 项

**起点 → 终点**（口径：**数换行 + 校验首尾两行的内容**，`t9_probe5.py`；⚠️ **不用正则抽编号**，那正是 #155 的形状）：

| | 行数 | 编号 | 首行 | 末行 |
|---|---|---|---|---|
| 改前 | **30** | 1–29 与 31（**#30 是空洞**），最大 **31** | `\| 1 \| 18 套模板的维度拆分是否为「3 层 × 3 主导短板 × 2 体成分」…` | `\| **31** \| **红/黄层 × speed_flexibility × 体成分 共 4 套模板的强度与结构参数**…` |
| 改后 | **37** | **1–37 连续、无空洞**，最大 **37** | 同上（未动） | `\| **37** \| **§5.2 的真实空洞：五个触发条件都只看分层标签…**` |

`numbers` 实测输出逐字是 `['1', '2', …, '29', '30', '31', '32', '33', '34', '35', '36', '37']`，`count = 37`、`max = 37`。**我实测到的数与 P9-A2 的更正逐字相符**（30 → 37、最大 31 → 37），故**没有第三个数**、无需顶回。

| # | 事项 | 归属 |
|---|---|---|
| **30** | 动作库的视频源：`exercises.yaml` 的 `video_url` 一律是 RFC 2606 占位符（`.invalid` 保留 TLD、DNS 保证不可解析，**不编造真实链接**） | 填补空洞；Task 2 已在 YAML 头注释预告（见第 ④ 节） |
| **32** | §7.3 步骤 3 的个体修正系数：三档阈值 `< 60 → 0.8` / `[60, 80) → 1.0` / `>= 80 → 1.2`（半开无缝无叠）+ 性别系数男 1.0 / 女 0.9 + `round(…, 2)` 承重 + `None → 1.0`/`unknown` | 计划 Task 12 Step 3 原清单 |
| **33** | §5.2 触发 4「学期末数据刷新」的口径：**任何新采集即触发，不限 week16** | 同上；⚠️ 必须与 #37 绑在一起裁决 |
| **34** | §8.4 同周多调整的合成方式：**相乘** + `reasons`/`sources` 按 `ORDER BY created_at, id` 全保留 + 相乘顺序决定浮点尾数 | 同上 |
| **35** | addon 的训练量口径（`weekly_volume = 0.0` + `"unspecified"` + warning，交教师 `VOLUME_SCALE` 覆盖）**并含「提高抗阻比重」的处置**（不自动、只提示）+ 绿层 `addons: []` 时不凭空造模块 | P5-A3；⚠️ 同时结掉了 #28 末尾那个条件项（#28 只交代了 `0.9` 这个系数、没交代「提高比重」怎么落地，故按 #28 自己写的判据本项成立） |
| **36** | `weekly_volume` 的基准量口径：130 个 block 只有两种键集（78 + 52）、时长类 `work_min × sets`、次数类 `rounds × reps`、**`rest_min` 不计入量**、两种之外 `ValueError` 不静默取 0 | P5-A1；⚠️ 与 #31 是同一空洞的两面 |
| **37** | §5.2 的真实空洞：五个触发都只看**标签**，而匹配还吃 `dominant_bucket`（W）与体成分状态（C）、这两个每天重算 → 「标签不变但 W/C 变了」这一类学生五条一条都不成立，今天全靠 #33 的宽口径兜住 | Task 6 关切 2；⚠️ 与 #33 绑定、不分成两项 |

**「刻意的空洞」那段说明整段改写**（空洞被填了，说明就成了假的）。改写后的那段同时留下三件事：① 三批写入的归属（#28 Task 2 / #29+#31 Task 3 / #30+#32–#37 Task 9）；② **「27 → 34」两个数都错**的成因（`34 = 27 + 1 + 2 + 4`，而最后一格实际是 **7** 项）；③ **#155 的成因**（探针用 `^\|\s*(\d+)\s*\|` 只匹配到未加粗的 1–17，而 18–31 写作 `| **18** |`），并把「数表格行一律用数换行 + 校验首尾两行、不要用正则抽编号」写进 spec 当反面教材。

**7 项照 18–31 的加粗格式写**（`| **30** | …`），理由与派单里控制者的倾向一致并写进了 spec：从 18 起那一批全部是**实现期撞见的空洞**（写代码 / 写 YAML 的人发现 spec 没给口径、当场登记），加粗让它们在一张 37 行的表里一眼可辨；本 Task 追加的 7 项同属这一类，故不照 1–17 的不加粗格式。

---

## ⑥ 9 条待清扫的逐条结论

| # | 内容 | 结论 | 改在哪 / 为什么不用改 |
|---|---|---|---|
| **1** | `assembler.py`「Task 8 的读模型要自己决定怎么摊」 | **改了**（⚠️ 唯一一处改 domain 代码） | `AssembledBlock.weekly_volume` 的注释：改成「Task 8 的读模型的决定是**不摊**（P8-A1）：缩放只是 `weekly_volume × factor`，`sessions_per_week` 是骨架的结构属性、不参与缩放，故 `weekly_training_sheet` 产出的每一课里那个数仍是**周量**」，并写明原句「指向一个与它相反的决定，会让下一个人以为学生端看到的是单课量」。改完重跑覆盖率：**996 / 0 / 288 / 0 / 100% 未变**（注释不影响 stmts/branch，但要坐实） |
| **2** | `_DERIVED_TABLES` 这个常量名 | **改了**（改名，不是只改注释） | `tests/db/test_models.py`：`_DERIVED_TABLES` → **`_BATCH_OWNED_TABLES`**（判据是 `batch_id` 那一列 = `delete_by_batch` 的合法目标，而不是「谁算出来的」）。**连带改名的散文引用共 9 处**（`test_models.py` 6 / `models/prescription.py` 2 / `models/__init__.py` 1，含那条 `git grep -n "_DERIVED_TABLES"` 指令 —— 不改它就成了假的）。⚠️ 我**多做了一步**：守卫函数名 `test_only_derived_tables_expose_batch_id` → `test_only_batch_owned_tables_expose_batch_id`（5 处引用同步），并把 `daily._replay_cleanup` docstring 首行的「五张**派生表**」改成「五张带 `batch_id` 的表」。理由：只改常量名会留下一个名字与它守卫的常量不一致的测试函数，那是同一条缺陷的第二个住址。⚠️ `.superpowers/` 下的账本与历史报告里的旧名**一个字节都没动**（历史记录不追改）。`app/db/repo.py` 与 `models/assessment.py` 里写的是「Plan 01 的三张派生表」这个**说法**、不是常量名，它对 Plan 01 仍为真，故不动 |
| **3** | `daily.py` / `backfill.py` 散文里的「三张派生表」 | **改了**（3 处） | ① `daily.py` 的 `# 必须 flush 取回 id：… 而三张派生表的 batch_id 都是 NOT NULL 外键` → 「**五张**带 batch_id 的表（Plan 01 的三张 + Task 6 的两张）」；② `daily._replay_cleanup` docstring 首行「五张**派生表**」→「五张带 `batch_id` 的表」，并把正文那句现在时的「清理清单**是**三张表」改成过去时「**在 Plan 01 结案时是**三张表」（它与它自己下面那段「Task 7 扩到五张」自相矛盾）；③ `backfill.py` 的「回放开头按 batch_id 删三张派生表」→ 删**五张**，逐个列出模型元组、写明**子表先删**（P7-A4），**并删掉 `daily.py:552-553` / `daily.py:249-254` 两个已推移的裸行号**（硬规矩 #61：复用历史输出里的行号等同手写），改成「按可 grep 的原文找」 |
| **4** | `test_repo.py` 的「九条 `ck_*`」 | **改了** | 模块 docstring 第 8 条：「九条」→「**十**条」，并写明它与**本文件自己**的两处（`:635` 那节标题 `# 十条 ck_* 取值域约束（Minor 2；第十条 percentile_snapshot.item 由 Ruling 121 补）`、`test_check_constraint_rejects_dirty_value` 的 docstring「十条 `ck_*` 逐条验证」）**自相矛盾** —— Ruling 121 补第十条时改了那两处、漏了本行。另补：本文件这十条是 **Plan 01 的那一批、不是全库**；全库今天共 **18** 条 `ck_*`（**运行时口径**：遍历 `Base.metadata` 数名字以 `ck_` 开头的 `CheckConstraint`，命令逐字写进注释；**不用正则数源码**），Plan 02 加的 8 条 = `exercise` 1（Task 2）+ `prescription_template` 4（Task 3）+ `prescription` 2 与 `weekly_adjustment` 1（Task 6/7），后三条由 `tests/db/test_models.py` 逐条点名钉住、`ck_weekly_adjustment_source` 另有 `tests/pipeline/test_prescription_stage.py` 的词表漂移守卫（P8-A5） |
| **5** | RST 表的列宽 | **改了 2 张、量出另 5 张但没改**（见下） | **改了**：`app/db/models/prescription.py` 里两张**管道式**表 —— `Exercise` 表第一列 38 → **42**（`| **``impact_level``** ∈ {high, medium, low} |` 那一格显示宽度 42，溢出 4 列并把第二列挤成 16）、`Prescription` 表第二列 26 → **29**（`` ``valid_from`` / ``valid_to`` `` 是 29）。用脚本按显示宽度（CJK 计 2）重算列宽并重新补齐，**只动空格、一个可见字符都没改**（`git diff --stat` = 20 insertions / 20 deletions），改完复扫该文件 **findings = 0**。<br>**没改的 5 张（三段式、带折行单元格）**：`override.py`（4 列，第 30 行整行显示宽 108 vs 边框 101）、`safety.py`（末列需 30、实给 21）、`templates.py`、`refdata_prescription.py`（2 处）、`test_prescription_templates.py`（6 行）。**理由**：这 5 张的单元格**跨行折行**，重新补齐必须先决定「折行的那几行属于哪一列」，脚本化会有搞乱归属的风险，手工重排则是 5 张表 × 每张十几行的纯排版工作；其中 3 张在 `app/domain/` 下（改它们要重跑覆盖率与架构守卫）。对一条**纯排版**的待清扫项，收益/风险不划算。**已如实量出并记录**（探针 ②/④ 的判据与前三版的失效原因都写在脚本 docstring 里：① 按空白切单元格 → 带空格的单元格被切成多段（假报）；② `strip()` 之后量不到右侧补齐（漏报）；③ 按显示列切分后再量补齐过的切片宽度 → 恒等于列宽，是**恒绿的假守卫**；④ 管道式表被 `is_border` 漏检，因为 `strip("|")` 只去掉首尾、中间的 `|` 被当成一段非 `=` 的内容） |
| **6** | `valid_from` 没有区分测试 | **改了（加注释、不加测试）** | `models/prescription.py` 的 `valid_from` 列注释补两段：① 「今天恒等于 `generated_on`」这条**是被守卫的**（`tests/pipeline/test_prescription_stage.py` 的 `assert {row.valid_from for row in rows} == {AS_OF}` 与紧邻的 `{row.generated_on} == {AS_OF}` 并列，把 `valid_from` 写成别的日期会当场红）；② **而「两者不相等」那一档今天在生产上不可达，故不存在一条能*区分*它俩的测试** —— 全仓唯一写入点是 `generate_prescriptions` 的那个字典，两行用的是**同一个** `as_of`；要写区分测试就得先造一个让它们不等的调用方，那是 Plan 03 教师端的事（spec §8.4「周一之前先生成、下周一才生效」，也就是这条注释已有的那句出处）。**故处置是把这件事写进注释、不加一条恒绿的假守卫**（与 Ruling 154 同一条形状：结构上不可能变红的断言只是噪音） |
| **7** | `weekly_adjustment.factor` 无范围 CHECK | **⚠️ 刻意不做（P8-A6）** | **不加 CHECK。** 理由已复核确认写在 `weekly.py` 的 **3 处** docstring/注释里：① 模块 docstring 第 3 节标题就是「`factor` 的合法区间是 `(0, 2]`，而 DB 那一列**刻意没有** CHECK（P8-A6）—— **这是两层守卫、不是重复**，两者的失守方式不同」；② `_FACTOR_*` 两个常量的注释（「`(0, 2]` 是**读模型的语义**、不是**数据的形状**，Plan 03 可能要放宽上界，届时改的是这两个常量、而不是一次重建库」）；③ `WeeklyFactor.__post_init__` 的 docstring 与它抛的 `ValueError` 消息本身（「⚠️ DB 的 `weekly_adjustment.factor` 列刻意没有对应的 CHECK，理由见 weekly.py 模块 docstring 第 3 节（P8-A6：两层守卫、不是重复）」）。另在 `prescription_stage.weekly_factors_of` 的 docstring 里还有一处（「一条脏行会让本函数抛 `ValueError`……这是期望行为，但要知道它是读侧抛的」）。**四处都已在，本 Task 一个字节没改、也没加 CHECK** |
| **8** | `repo.delete_by_batch` docstring「今天 `_replay_cleanup` 只清三张」 | **改了** | `app/db/repo.py`：改成「`_replay_cleanup` **今天清的就是上面这五张**」，并把「Task 7 **会**把两张处方表接进那份清单」这句对**已完成动作**的预告删掉、同时写明它的危害（读它的人会以为处方表今天不在清理清单里、进而以为重放会让 `weekly_adjustment` 翻倍）。「子表先删 + `PRAGMA foreign_keys=ON`」那半句保留并挂上 P7-A4 |
| **9** | `test_backfill.py` docstring 开头印着 Plan 01 的 `17.98–18.92 s（3.2–3.3× 余量）` 且无时间限定词 | **改了** | `test_backfill_500_students_under_60_seconds` 的 docstring **最前面**加一段 `⚠️⚠️`：「本段这两个区间是 **Plan 01** 的口径（『fix round 3』= Plan 01 的 fix round 3，量的是**接入处方阶段之前**的回放）；Task 7 之后的实测在**本 docstring 下面**那一段：`28.86 / 29.05 / 29.59 s`（n=3），最小余量 **2.03×** —— 即余量从 3.2× 掉到刚过硬规矩 #42 的 2× 线」，并把原句里的「fix round 3」改成「**Plan 01** fix round 3」。⚠️ 下面那段的实测值与测量条件**一字未动**（它是 Task 7 的取证，改它等于毁证据）；本条修的是**顺序**问题（先读到过期值），不是数值问题 |

---

## ⑦ 变异复跑 + 最终验收

### ⑦.1 变异 ④（Task 7 的那一条）：删掉 `valid_to_of` 的 `- 1 day`

按硬规矩 #83 的 `.pyc` 纪律：跑变异**前后**都 `shutil.rmtree(__pycache__, ignore_errors=True)`（实测清了 16 个目录）、`PYTHONDONTWRITEBYTECODE=1`、pytest 加 `-p no:cacheprovider`。**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`，Task 5 的实现者做过一次等长改动且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**；**假绿更危险**。

| 阶段 | 命令 | 结果 |
|---|---|---|
| 变异前 | `t9_mutate4.py mutate`（**先备份原字节到 TEMP**） | `written eol=lf crlf=0`，anchor 恰好命中 1 次 |
| 变异中 | `pytest -q --tb=no tests/pipeline/test_prescription_stage.py tests/db/test_models.py tests/integration/test_golden_cases.py` | **4 failed / 80 passed** —— `test_valid_to_is_generated_on_plus_microcycle_minus_one_day`（`2026-03-30 != 2026-03-29`）、`test_prescriptions_are_generated_for_every_stratified_student`、`test_a_layer_change_regenerates_and_replaces`、`test_regeneration_does_not_inherit_teacher_overrides`（三条都是 `2025-10-13 != 2025-10-12`） |
| 还原 | `t9_mutate4.py restore`（**从 TEMP 备份 `write_bytes`，未使用 `git checkout`**，硬规矩 #46/#70） | 复核：原句恰好 1 处、含 `- dt.timedelta(days=1)`；`git diff -- backend/app/pipeline/prescription_stage.py` **为空**（字节级复原） |
| 还原后 | `pytest -q tests/integration/test_golden_cases.py tests/domain/test_prescription_assembler.py tests/architecture` | **56 passed**（并复核 `git diff -- backend/app/domain/prescription/assembler.py` 只剩第 ⑥ 节第 1 条那处注释改动、`prescription_stage.py` 的 diff 为空） |

**结论：尺子没被 fixture 改动弄钝。** 4 条红全在 `test_prescription_stage.py`，与 Task 7 结案时的形状一致；⚠️ **`test_golden_cases.py` 的 18 条在变异下全绿是预期的、不是漏网** —— 黄金用例夹具**不含 `valid_to`**（计划 Step 1 的字段清单里也没有它），而本 Task 新加的那条测试守的是「模板 → 训练包」那一环，`valid_to` 是**落库**那一环的字段、只在有库的路径上存在。这一点如实记录，不把它讲成「黄金用例也守住了 valid_to」。

**另跑了第 ②.4 节那条自证变异**（`_SEX_FACTOR` 女性 0.9 → 1.0）：3 failed / 15 passed，红的恰好是 GC03 / GC05 / GC12，标签测试与分布测试全绿 —— 证明新 fixture 不是恒绿、且没有越界去守标签。

### ⑦.2 最终验收

| 项 | 基线 | 结案 | 判定 |
|---|---|---|---|
| `python -m pytest -q` | 793 passed | **807 passed** in 84.98 s | ✅ +14 |
| `--cov=app.domain --cov-branch --cov-report=term-missing` | 996 / 0 / 288 / 0 / 100%（792 passed, 1 skipped） | **996 / 0 / 288 / 0 / 100%**（806 passed, 1 skipped） | ✅ 四格逐字未变 |
| `tests/architecture` | 全绿 | **全绿**（4 passed） | ✅ |
| 扫描面 | 35 | **35** | ✅ 本 Task 不新增文件 |
| 表数 / `prescription` 列 / `weekly_adjustment` 列 | 18 / 16 / 8 | **18 / 16 / 8** | ✅ |
| `app.domain.prescription.__all__` | 51 | **51** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33（Ruling 97 刻意不动） | **未触碰** | ✅ |
| `git diff -- backend/data` | — | **只含 `exercises.yaml`**（12+/8−） | ✅ |
| `backend/pe.db` | 不得存在 | **不存在** | ✅ |
| `backend/data/seed/` | 0 文件 | **0 文件** | ✅ |
| `git ls-files --eol -- backend/data` | 全 `i/lf w/lf attr/text eol=lf` | **23 个文件全部仍 `i/lf w/lf attr/text eol=lf`** | ✅ |
| `git status --porcelain` | — | **空**（4 个 commit 之后） | ✅ |
| 三个指纹 | 见第 ④ 节 | CSV / equivalence **逐字不变**，exercises `3DE598AF38631209` → `5394B37F01DAC9AC` | ✅ |
| `golden_cases.json` | 27346 bytes / 680 LF / 纯 CRLF | **43571 bytes / 892 LF / 纯 CRLF**，`json.loads` 通过、`input` 与 `expected` 各 **13** 例、`expected[0]` **23** 键（11 + 12）、`_meta` **11** 键（8 + 3） | ✅ 不被指纹钉住（复核：`tests/` 下无任何断言比对它的 sha256） |
| spec | 98755 bytes / 1013 LF / 纯 CRLF | **128328 bytes / 1092 LF / 纯 CRLF** | ✅ §14 = **37 行 / 最大编号 37 / 无空洞** |

**§1.3 那两个 canonical sha256 我没有重测**：派单说「你不必自己重测」，且本 Task 唯一的生产逻辑改动（`_from_golden_cases`）走的是**黄金用例路径**（`payload` 是 `list`），而那两个值来自 **60 人夹具路径**（`build_dataset` → `_from_dataset` → `daily.run_daily`），两条路径在 `stratify_dataset` 的第一个 `isinstance` 就分岔、此后不共用任何一行。故理论上不影响，未重测。⚠️ 若控制者认为需要坐实，复跑命令是 `tests/pipeline/test_daily.py` 的那条 `test_rerunning_the_same_business_date_reproduces_every_table`（它断言 `first == second`，**不会**因为这两个值而红 —— 这一点我已写进 spec 的勘误里）。

**墙钟数量级哨兵**：全量 `pytest -q` 从 113.63 s 降到 **84.98 s**（同一台机器、都不带 `--cov`）；带 `--cov` 是 171.19 s。相对 Plan 01 的 28.4–34.0 s 与 Task 7 的 28.86–29.59 s（那是 `run_backfill` 那一段的 `elapsed`，与本处的整套件墙钟不是一个量）**没有数量级恶化**。⚠️ 本处两个数**不被任何测试守卫**，只是量级哨兵。

---

## ⑧ commit、关切、没按派单做的地方

### ⑧.1 4 个 commit

| sha | 一句话 | 文件 |
|---|---|---|
| **`e7a01d2`** | P9-A1：`_from_golden_cases` 的身高体重改从 `case["curr"]` 读，13 例的 `bmi` 不再恒为 `None`；Task 7 那条守卫改名 + 换契约 | `run_stratify.py`、`test_prescription_stage.py`（2 files，61+/26−） |
| **`7a18852`** | Step 1：13 例黄金用例延伸到「模板 → 训练包」—— `expected` 每例 +12 键、`_meta` +3 节、新加 2 条测试；既有那条标签测试一字未动 | `golden_cases.json`、`test_golden_cases.py`（2 files，459+/21−） |
| **`874b9f2`** | P9-A3：`exercises.yaml` 头注释那句「尚未登记进 spec §14」改成「已登记为 #30」+ 编号易手取证链；`EXERCISES_FINGERPRINT` 同步 | `exercises.yaml`、`test_refdata_prescription.py`（2 files，27+/9−） |
| **`61078c4`** | Step 2 + Step 4：spec 五处勘误、§14 补 7 项（30 → 37 行 / 无空洞）、9 条待清扫一次清完（含 `_DERIVED_TABLES` 改名与 2 张 RST 表列宽） | spec + 9 个代码/测试文件（10 files，196+/55−） |

`git add` 一律**按文件名逐个加**；commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`；**未 push**、**未切分支**、**未碰 main**。

### ⑧.2 关切（含顶回控制者的地方）

**⚠️ 顶回 1（Critical 级，P9-A1 的验收点实测为 0）——「spec §7.4 的三档安全触发第一次在黄金用例里真的可达」这句只对一档成立。**

* **哪条决定**：派单 §3 的 P9-A1 末尾与 §11 第 5 项，逐字是「这条改动让 13 例的 `input_snapshot` 从『`bmi` 全 `None`』变成『各有其值』→ **spec §7.4 的三档安全触发第一次在黄金用例里真的可达**，而本 Task 要断言的 `needs_review` / `safety_substitutions` 从此**不再恒为假绿**」，并把「`needs_review` / `safety_substitutions` 在几例里**真的非空**」列为 P9-A1 的**验收点**。
* **实测**：`needs_review` 非空 = **0 例**、`safety_substitutions` 非空 = **0 例**。三档逐一：① `body_fat_abnormal` **命中 5 例**（GC01/GC04/GC05/GC12/GC13）—— 但它读的是 `snapshot["C"]`，**在 P9-A1 之前也已可达**，不是 P9-A1 带来的；② `bmi_over_30` 从「结构上不可求值」变成「**可求值但不命中**」—— 13 例的 `bmi` 全落在 **[18.9, 25.7]**，最大是 GC04 的 25.7，**没有一例 > 30**，故 `equivalence_triggers` 恒空、等价表**根本没被查过**、`needs_review` 结构上无从置位；③ `muscle_low_p10` **仍结构上不可达**（`muscle_p10` 恒 `None`，这一档 P9-A1 明写保持不变）。
* **为什么错**：把「分支可求值」讲成了「触发会命中」。前者是真的（`safety_skipped` 从 `["bmi_missing", "muscle_p10_missing"]` 变成 `["muscle_p10_missing"]`，这是可测的、我已逐例钉进 fixture），后者是假的。
* **我的替代方案**：**不改 GC 的身高体重**。要让 ① ② 真的命中，就得把某例 `curr` 的体重抬到让 BMI > 30（例如 GC04 从 76 kg 抬到 90 kg）—— 那是**改 Plan 01 已逐条人读确认的输入**，而派单只授权改 `expected` 与 `_meta`（P9-A1 的修法逐字是「改成让 `_from_golden_cases` 从 `case["curr"]` 读这两个值」，那句被 ⛔ 撤回的段落里的「或直接给每例一组能让 BMI 落在想要的档位上的身高体重」也在撤回范围内）。我改为：把 `safety_triggers` / `safety_skipped` 逐例钉进 fixture（于是「`bmi_missing` 不再出现」这件 P9-A1 的**真实**效果有了守卫），并在夹具 `_meta.caveats_training_package` ② 与新测试的 docstring 里**逐字写明**这两档在 13 例里不可达、它们的行为守卫在 `tests/domain/test_prescription_safety.py`。
* **代价**：黄金用例仍然**不能**替代 `test_prescription_safety.py` 去守「找不到等价动作 → `needs_review` + 原样保留 + warning」这条 Review Focus 第 5 条；spec §12 的「延伸到训练包」在安全后置那一环是**弱覆盖**。若控制者认为这一环必须在黄金用例里真的命中，最小改法是**只改 GC05 一例的 `curr.weight_kg`**（她是女性、`C = True`、黄层耐力，BMI 24.2 → 抬到 30 以上需要 ≈ 77.5 kg；⚠️ 会连带改掉她的 `score_bmi` → `national_total`，但 `find_weaknesses` 只遍历 6 个短板项、`C` 只看体成分，故 `label` / `W` / `C` / `valid_count` / `dominant_bucket` / `trend` / `explain` **理论上全不变** —— 需要一次实测坐实，且 `curr` 与 `prev` 要同改以保持 `Δbmi = 0`）。我**没有做**，因为那是改输入、不是改期望值，超出授权。

**⚠️ 顶回 2（Minor，P9-A2 的措辞）——「`fe0a44e0…` 与『行数合计 882』**两处都已过期**」只对一处成立。**

* 派单 §5 与计划 `:286` 都写「今天印的是 `fe0a44e0…` 与『行数合计 **882**』，**两处都已过期**」，而同一张表里 9 张那一行的「行数合计」列逐字写着「**882（未变）**」—— 自相矛盾。
* **实测**：882 对**那 9 张表**仍然为真（`c5599db` 只改 `input_snapshot` 的**列内容**、不改行数）；真正过期的是「9 张表就是管道的全部覆盖面」这个**隐含前提**（第 5 行原文「管道写的 **9** 张表」今天是 **11** 张）。
* **处置**：勘误里两处都写清了 —— sha 明确标为「过期 → 新值」，882 明确标为「**对这 9 张仍然为真**，过期的是覆盖面」。没有照字面把 882 讲成错数（那会让下一个人以为行数变了、去查一个不存在的行数回归）。
* **代价**：无。

**其余关切（不阻塞，逐条如实记录）**：

1. **`high` 档（`endurance_score >= 80` → 1.2）与 `round` 的承重档（低档 ∩ 女性 → `0.8 × 0.9`）在 13 例里都不可达。** 13 例的 `endurance_score` 全落在 [30, 60]，故 `weekly_volume` 只覆盖了 `0.8` / `0.9` / `1.0` 三个系数。这两档由 `tests/domain/test_prescription_assembler.py` 的 `_BANDS_MALE` / `_BAND_EDGES` 守（字面写死），黄金用例不重复。
2. **`MatchStatus` 六种里 13 例只覆盖两种**（`matched` 12 / `no_layer` 1）；`no_bucket` / `no_template` / `unreachable` / `not_approved` 由 `tests/domain/test_prescription_match.py` 的 32 格穷举守。已写进夹具 `_meta.expected_schema.match_status`。
3. **五触发在黄金用例里不求值**（单日夹具没有 `last_prescription`、也没有采集日）。故 `label_at_generation` 钉的是「那一列填的是**当天**分层结果的那一个标签」，**不是**触发 2；两条守卫并列、不是替代（计划原文的告诫，已逐字写进 fixture 与测试 docstring）。
4. **`golden_packages` fixture 触两个私有名**（`run_stratify._from_golden_cases`、`prescription_stage._profile_of`）。这是刻意的：要复用的正是「映射只有一个所有者」这件事本身，在测试里重抄一遍 `_profile_of` 反而会造成第二个住址（`endurance_score` 的均值口径与 `bmi` 的读取口径）。测试触私有名是本仓既有惯例（同文件顶部那段 `_REASON` 的说明、`tests/architecture/test_domain_purity.py` 的 AST 内省）。
5. **`StudentProfile.birth` 由 `age` 反推**（夹具只给 `age`）：`dt.date(_AS_OF.year - age, _AS_OF.month, _AS_OF.day)`，`age_from` 的 `(月, 日)` 元组比较在生日当天**不**减岁，故它精确给回 `age`、装配器第 1 步的一致性闸门过得了。⚠️ 代价：`_AS_OF` 若被改成 2 月 29 日一类日期会炸，而 13 例的 `age` 全在 [19, 21]、`_AS_OF = 2025-09-15`，今天不可达。
6. **RST 表列宽只修了 2 张**（第 ⑥ 节第 5 条），另 5 张量出来了但没改，理由与探针的四版演进（含一版**恒绿的假守卫**）都记在那一格与 `t9_probe2/4.py` 的 docstring 里。若控制者要求一次清完，那是一个独立的纯排版 Task。
7. **commit ① 与 commit ② 之间有一个短暂的悬空引用**：`run_stratify.py` 的新注释点名了 `test_golden_cases_reach_the_training_package`，而它到 commit ② 才存在。同一个 Task 内的两个 commit，未拆开处理（拆开会让 P9-A1 的 RED→GREEN 取证跨越两个 commit）。
8. **`_meta` 里没有发现别的过期数字**（P9-A6 要求的复核）：`percentile_note` 的「24 行」由本 Task 的探针复跑坐实（`snapshot rows = 24`）；`muscle_p20_by_group` 的四个值（33.2 / 33.56 / 23.7 / 23.6）与 `test_golden_cases.py` docstring 里那组实测逐字相同；`input_schema.body_comp` 引的「spec §14 #16」仍指向「骨骼肌指数是否参与体成分异常判定」✅。**故 P9-A6 的处置是「复核后无需更正」**，只做了 P9-A5 的 5 处 Task 编号消歧（`_meta` 3 处 + GC13 `note` 2 处，后者超出派单列的 3 处，见下）。

### ⑧.3 没按派单做的地方

**共 3 处，逐条列明（0 处也要写「0 处」，故这里如实写 3 处）：**

1. **没有让 `needs_review` / `safety_substitutions` 在任何一例里非空**（派单 §11 第 5 项把它列为 P9-A1 的验收点）。理由与替代方案见**顶回 1**。
2. **多做了一步**：P9-A5 只列了 `_meta` 里的 **3 处**陈旧 Task 编号，我**同时改了 GC13 `note` 里的 2 处**（「Task 10 Step 0.7 补的一例」、「若 Task 10 传 snapshot_muscle_p20=None」）与 1 处「（Task 9 关切 6）」→「（**Plan 01 的** Task 9 关切 6）」，以及 `test_golden_cases.py` 导入行末尾那句 `# Task 10 提供` → `# Plan 01 的 Task 10 提供`。理由：与 P9-A5 是**同一条缺陷的另外几个住址**，只改 `_meta` 会让读 GC13 note 的人得到完全一样的错误印象；派单 §6 也写明本 Task 就是那一次「一次性清扫」。
3. **多做了一步**：待清扫第 2 条只要求处理 `_DERIVED_TABLES` 这个**常量名**，我**同时改了守卫函数名** `test_only_derived_tables_expose_batch_id` → `test_only_batch_owned_tables_expose_batch_id`（5 处引用同步）与 `daily._replay_cleanup` docstring 首行的「五张**派生表**」措辞。理由：只改常量名会留下一个名字与它守卫的常量不一致的测试函数 —— 那是同一条缺陷的第二个住址，而第 2 条的要害正是「名字里的『派生』不再准确」。

**其余一律照派单做**：三条 Critical 逐条照 P9-A1/A2/A3 的**更正**办、没有照计划原文的字面办；§14 追加 7 项、编号 30 → 37、空洞说明整段改写、7 项照 18–31 的加粗格式；`exercises.yaml` 按六步程序办、另两个指纹逐字不变；spec 五处勘误按 Plan 01 的格式（原文 + 更正 + 理由 + 编号）；§1.3 的历史记录一字未动、新值追加在它后面；第 7 条**刻意不做**并引 P8-A6；未 push、未切分支、未碰 main、未跑 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`；`backend/data/` 只动了 `exercises.yaml`。
