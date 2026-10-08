"""账本追加：新 Task 5 的预检节（Ruling 147 + 硬规矩 #80）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

### Task 5（合并后）: 处方装配（简化版） — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`dfa7580`（工作树干净）→ 计划重构提交 `3dd36d2`。
**测试基线**：`cd backend; python -m pytest -q` → **592 passed in 61.84s**（控制者本机实跑，与 Task 4 结案时一字不差）。
**取证脚本**：`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t5_probes/_t5_probe{1,2,3,4}.py`（四份全部入库）。

**⚠️ 这次预检比前四次都严重：4 条 Critical。**根因是**合并本身**——把四节正文压成一节时，控制者重写了散文、**没有重新核对四节各自引用的量**。而其中两条（P5-A1 / P5-A3）与 **Ruling 133 同型**：计划引用一个 YAML 里根本不存在的量。

#### Ruling 147 — 预检查出 4 Critical / 5 Important / 3 Minor / 1 控制者错误，计划正文更正 21 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P5-A1** | **Critical** | `Block.structure` **只有两种键集、无第三种、无交集**：时长类 **78** 个 `{sets, work_min, rest_min}`、次数类 **52** 个 `{rounds, reps}`（78+52=130 ✓）。**没有 `weekly_volume` / `volume` / `base` 任何一个键。** | 计划 5.2 第 3/4 步的「模板基准量」**不存在**。定口径：时长类 `base = work_min × sets`、次数类 `base = rounds × reps`、**`rest_min` 不计入量**；两种单位不可通约 → `AssembledBlock` **新增 `volume_unit` 字段**（`"min"` / `"reps"` / `"unspecified"`）；未知 shape → `ValueError`，**不得静默取 0**。登记 spec §14 新 **#36** |
| **P5-A2** | **Critical** | 同一模板内同一 `exercise_ref` **跨 session 重复，18/18 全部如此**。130 个 block 的「一周内出现次数」= **`{2:24, 3:42, 4:64}`**，按层 **绿全 2 / 黄全 3 / 红全 4** = 恒等于 `weekly_frequency`。 | `weekly_volume` 若只是「单次课的量」就**名不符实**。定口径：**`weekly_volume = base × sessions_per_week`**，`sessions_per_week` 由装配器**实测统计**（不假设等于 `weekly_frequency`），**新增 `sessions_per_week` 字段**留痕；另配一条守卫测试断言真仓里两者恒等（今天全绿，专家改坏会变红） |
| **P5-A3** | **Critical** | `addons.when` = **`{body_fat_over:12, muscle_low:12}`**；`module` = **`{resistance_priority:12, energy_expenditure_plus_10pct:6, energy_expenditure_plus_5min_hiit:6}`**。**绿层 6 套全部 `addons: []`**；红层 = `(body_fat_over → energy_expenditure_plus_10pct)` + `(muscle_low → resistance_priority)`；黄层 = `(body_fat_over → energy_expenditure_plus_5min_hiit)` + `(muscle_low → resistance_priority)`。 | **原计划判「提高抗阻比重无法自动化、只加 warning、置 needs_review」是错的**：那会让 12 个 `when: muscle_low` 的 addon **永远不被消费**（模板里的死数据）。**更正：肌肉量 < P10 触发时追加该 addon**——追加一个模块**不重排既有结构**，既落地 spec §7.4 又不越「后置处理」的语义边界。`needs_review` **不再由它单独置位**。**addon 的量口径 = `weekly_volume 0.0` + `volume_unit "unspecified"` + 一条 warning**（否掉两个备选：按 ref 名字硬编码规则会让专家加第 4 个 module 时静默失效并抢走 `exercises.yaml` 的所有者；取同 session 均值会跨单位平均）。登记 spec §14 新 **#35** |
| **P5-A4** | **Critical** | `test_domain_purity.py` 的 `ALLOWED_MODULES` = `{dataclasses, enum, collections, collections.abc, numpy, typing}`。**`math` 不在其中**；两份守卫里 `math` 出现 **0 次**。 | 计划 5.1 写的 `math.floor` / `math.ceil` **会让纯净性守卫变红**。**不改守卫**（往 allow-list 加模块是扩大 domain 可用面的架构决策），改用 `int(x)` 与 `-(-x // 1)`。⚠️ `int()` 只在**正数**上等价于 `floor` → `hr_zone` **必须新增 `hrmax_bpm <= 0` 拒绝**，且 docstring 要写明这层因果 |
| P5-A5 | Important | `intensity.type` = **`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24**，而 `INTENSITY_TYPES` 有 **4** 个值 → **`rpe` 真仓 0 次**。形状规整：`hrmax_pct`→`low`+`high`、`onerm_pct`→`value`、`none`→全空。 | `rpe` 档不可达但**必须被覆盖**（domain 分支 100%）→ 手工构造 `Intensity(type="rpe", value=13)` 测。`Intensity.value` 的语义随 `type` 变，写进 docstring |
| P5-A6 | Important | 实测 `0.8 * 0.9` = **`0.7200000000000001`**。 | 计划要求「0.72 字面写死」→ 直接相乘的测试**会红**。定口径：`weekly_volume` 一律 **`round(x, 1)`**；系数本身用 `pytest.approx` |
| P5-A7 | Important | **原计划自相矛盾**：5.2 说 `assembly_snapshot`「键字面固定 **12** 个」并列出 12 个，但同节决定段要求写 `"volume_factor_fallback"`、5.3 又要求写 `"safety_skipped"`——**两个都不在那 12 个里**。 | 拆成两段契约：**`assemble` 恰好 12 个键**；**`apply_safety` 追加至多 3 个**（`safety_triggers` / `safety_skipped` / `safety_volume_factor`，字面钉死）。`endurance_score is None` → `volume_factor_band = "unknown"`，**不加第 13 个键** |
| P5-A8 | Important | `impact_level` **两个住址**：`Block.impact_level`（模板）与 `ExerciseSpec.impact_level`（动作库）。Task 3 已验证 130 个 block 零不一致。 | 定口径：**装配器从 `ExerciseSpec` 取，不从 `Block` 取**。`exercises.yaml` 是**源**、模板里的是冗余副本；读副本会在「专家改了动作库、忘了改 18 套模板」时让安全替换静默失效（Global Constraint #3） |
| P5-A9 | Important | **两套不同名的触发词表**：`ADDON_TRIGGERS = {body_fat_over, muscle_low}`（所有者 `templates.py`）、`EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}`（所有者 `exercises.py`，也是 `volume_reduction` 的键）。YAML 的 `addons.when` 取值 = `ADDON_TRIGGERS` ✓ | `safety.py` 里字面写死 `_TRIGGER_MAP`（键 = 本模块触发名，值 = `(volume_reduction 键 or None, addons.when 键 or None)`），并各加**一条漂移测试**钉住两个上游词表。词表所有者仍是上游两模块，`safety.py` **只消费** |
| P5-A10 | Minor | `BODY_FAT_LIMIT` 实测是 `derive.py` 里**一行 dict 定义** + 一处消费；计划写「`derive.py:68-69` 明写严格大于」——**行号口径错、引文控制者未核**。 | 按硬规矩 #78 改成可 grep 的原文片段，「严格大于」降级为「由实现者复核引文后写明」 |
| P5-A11 | Minor | `Sex` 住在 **`app/domain/indicators.py`**（`class Sex(str, Enum)`），计划 5.2 的 `StudentProfile.sex: Sex` 没写 import 来源。 | 补明 `from app.domain.indicators import Sex`（**绝对导入**，与 `match.py` 引 `Layer` 同口径） |
| P5-A12 | Minor | 加载器实测 8 个公开函数：`load_exercises/exercises/load_equivalence/equivalence/load_templates/templates/sync_exercises/sync_templates`。 | 吃真仓 YAML 的测试用**三个进程内单例**，不用 `load_*`（后者每次重解析 18 份 YAML，还各跑一遍 `yaml.compose` 建行号索引）；单例**进程内共享，不得改写** |
| P5-A13 | — | **控制者错误 #139**：用一个**自己没验证过的正则**（`\\(\\s*"`）去数 `_PRESCRIPTION_PUBLIC_BASELINE` 的二元组个数，数出 **3**；而同文件里就有 **`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`**，且 `len(__all__) == 24` 双重坐实。 | 计划的「24 个二元组」**是对的，探针是错的**（跨行元组没被单行正则匹配到）。→ **补硬规矩 #80** |

**扫描面复核（计划 5.5 的数字，实测正确、无需更正）**：`app/domain` **10** 个 `.py` + `app/pipeline` **7** + `app/db` **11** = **28**；Task 5 新增 4 个 → domain **14** → 扫描面 **32** ✓

**→ 补硬规矩 #80：用一个探针去数一个已经有字面断言的量，是多此一举且必然自相矛盾——先读那条断言。** 依据：P5-A13 / 控制者错误 #139，这是「把自己没验证的工具输出当事实」的第 8 次（前 7 次见硬规矩 #53/#57/#59/#60/#76/#77）。

**→ 补硬规矩 #81：合并或重写计划正文时，被合并的每一节所引用的「量」（字段名、YAML 键、常量值）必须在合并后重新实测一遍，不得沿用原文。** 依据：P5-A1 / P5-A2 / P5-A3 —— 合并这个动作本身产出了 3 条 Critical，而四节原文分开写时这 3 条**都不存在**（原文各自都指着自己那一节的量）。**压缩散文会静默丢掉「这个量在哪」的上下文。**

**给实现者的可字面写死算例**（控制者实算，`RED-END-ABN-01` 第 1 课，`weekly_frequency = 4`、`week_deltas = [1.0, 1.05, 1.1, 0.85]`，男 20 岁、`endurance_score = 50` → 档 `<60` → `0.8`，性别 `1.0`，系数 **0.8**）：

| block | intensity | structure | base | weekly_volume | 第 1 周 | 第 4 周 |
|---|---|---|---|---|---|---|
| `interval_run` | `{hrmax_pct, low 60, high 70}` | `{sets:4, work_min:3, rest_min:2}` | `3×4 = 12` min/课 | **48.0 min** | **38.4** | `48×0.8×0.85 = 32.64` → **32.6** |
| `compound_circuit` | `{onerm_pct, value 70}` | `{rounds:3, reps:10}` | `3×10 = 30` reps/课 | **120.0 reps** | **96.0** | `120×0.8×0.85 = 81.6` → **81.6** |

`hrmax(20) = 208 − 0.7×20 = ` **194.0**；`hr_zone(194.0, 60, 70)` = `(int(116.4), -(-135.8 // 1))` = **`(116, 136)`**。
`compound_circuit` 的 `hr_zone` = **`None`**、`intensity_text` 含「1RM」。

**计划正文更正**：`_t5_preflight_patch.py`，**21 处替换全部命中 1 次**（脚本逐条打印命中清单即取证，硬规矩 #79）。计划 **129 092 B / 822 行 → 151 467 B / 937 行**（CRLF 未变，无 BOM）。

**下一步**：抽 `task-5-brief.md` → 派实现者。**按 Ruling 145，目标 1–2 轮 fix round。**
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)

assert "Ruling 147" not in t, "Ruling 147 已存在"
t2 = t.rstrip("\r\n") + BODY
out = t2.encode("utf-8")
P.write_bytes(out)

chk = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(out)} lines={chk.count(nl)}")
print(f"[verify] Ruling 147={chk.count('Ruling 147')} 硬规矩 #80={chk.count('硬规矩 #80')} "
      f"#81={chk.count('硬规矩 #81')} P5-A1={chk.count('P5-A1')} P5-A13={chk.count('P5-A13')}")
print(f"[verify] crlf={chk.count(chr(13)+chr(10))} lf={chk.count(chr(10))} (相等即纯 CRLF)")
