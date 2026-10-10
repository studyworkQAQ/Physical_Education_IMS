"""Task 9 落地脚本 09：写 task-9-report.md（python 写、UTF-8；行尾用 CRLF 与本目录既有报告一致）。

⚠️ 不用编辑器工具反复改 .superpowers/ 下的文件（派单第 7 节）。
⚠️ 写完后自己复核字节数与行数（.superpowers/** 在 .gitattributes 里是 `-text`，
即双向零转换，故这里写什么行尾就存什么行尾）。
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE.parent / "task-9-report.md"

CRLF_BYTES = b"\r\n"

# 报告正文分成若干块，逐块 append，避免一个巨大的字符串字面量
BLOCKS: list[str] = []

BLOCKS.append("""# Plan 03 Task 9 实现者报告 —— GC14 + 端到端冒烟 + demo.ps1 + spec 勘误

**分支** `feature/plan-03-feedback-alert-crud-api`　**基线 commit** `cf9ad7a`　**未 push、未碰 main**
**5 个 commit**：`db3eec0`（GC14）→ `491c4e7`（端到端冒烟 + run-daily 端点）→ `de95ef6`（progress_board 填充口径 + 标准化得分单一所有者）→ `ec6a65f`（demo.ps1）→ `9c0b1e9`（spec 勘误 + 19 条待清扫）

**一句话结论**：四个交付物全部落地，全量 **1244 passed**（1225 → +19），domain 覆盖率四格 **1268 / Miss 0 / 376 / BrPart 0 / 100%**，黄金用例 **13 → 14**，端点 **62 → 63**，扫描面 **58 → 60**，表数仍 **25**，五个指纹逐字不变，`backend/data/` **一个字节未动**，`backend/pe.db` **不存在**。**顶回控制者 6 处**、**没按派单做的地方 1 处**（都在第 ⑦ 节逐条给了理由）。

---

## ① 环境与基线复现

**硬规矩 #73 的 import 冒烟**（开工第一件事，在 `backend/` 下亲跑）：

```
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(...)"
→ 2.1.3 0.141.1 0.54.0 0.28.1 2.13.5 6.0.3
python --version → Python 3.11.1
```

SQLAlchemy **2.1.3** / FastAPI **0.141.1** / uvicorn **0.54.0** / httpx **0.28.1** / Pydantic **2.13.5** / PyYAML **6.0.3** / Python **3.11.1**，**无 venv**，与派单第 2 节逐字一致。**没有撞上 `ImportError: DLL load failed`。**

**git 状态**：分支 `feature/plan-03-feedback-alert-crud-api`、HEAD = `cf9ad7a`、工作树只多一个未入库的 `task-9-brief.md`（派单本身）。

**测试基线**（两次都亲跑）：

| 命令 | 基线（`cf9ad7a`） | Task 9 结案 |
|---|---|---|
| `python -m pytest -q` | **1225 passed** in 135.99 s | **1244 passed** |
| `… --cov=app.domain --cov-branch --cov-report=term-missing` | **1224 passed, 1 skipped**；`TOTAL 1259 / 0 / 376 / 0 / 100%` | **1243 passed, 1 skipped**；`TOTAL **1268** / **0** / **376** / **0** / **100%**` |

⚠️ 带 `--cov` 时少一条 passed、多一条 skipped 是**既有现象**（基线也是如此），不是本 Task 引入的。

**domain 逐模块**（改前 → 改后，只有 `report.py` 变）：`app/domain/report.py` **112 → 121** stmts、branch 仍 **40**、Miss **0**、BrPart **0**；其余 17 个模块逐格不变。⚠️ 派单预告「这一条会让 `app/domain/report.py` 的 stmts/branch 涨」，实测 **stmts 涨了 9、branch 一格没涨**——coverage.py 不把条件表达式（`A if c else B`）算成分支弧，故 `mini_test_scores` 里那四个三元式与一个 `or` 都只贡献 stmts。⚠️ **这不代表那几档没被测**：支 I 的 12 条测试逐档给了字面期望值（深蹲缺测 / 折返缺测 / 两项都缺 / 两项都在，四档各一条），且 M4/M5 两条变异各红了 8 条与 3 条（第 ③ 节）。

**其余基线量**（全部运行时口径，探针 `t9_probes/p01_baseline.py` 与 `p13_final_acceptance.py`）：

| 量 | 基线 | 结案 | 口径 |
|---|---|---|---|
| 表数 | 25 | **25** | `len(Base.metadata.tables)` |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（不动） | AST 数 `tests/db/test_models.py` 里那个 list 的元素个数 |
| 架构守卫扫描面 | 58 | **60** | `_py_files` 的同款 `rglob("*.py")`：pipeline 10 + db 11 + domain 18 + **api 19 → 21** |
| `/api/` 路径模板 | 62 | **63** | `app.openapi()["paths"]` |
| 操作数 | 90 | **91** | 同上，按 5 个方法过滤 |
| 挂 `security` 的操作 | 17 | **18** | 同上 |
| `len(app.routes)` | 6 | 6 | ⚠️ **不可用**：FastAPI 0.141.1 的 `include_router` 是惰性的（折叠成一个 `_IncludedRouter`），只数得出 4 个内置 Route + `/api/health` + 那一个折叠节点。硬规矩 #103：两种口径都是运行时的，采**完整**的那一种、把另一种标注为不可用 |
| 黄金用例 | 13 | **14** | `len(json["input"])` |

⚠️ **控制者的 uvicorn 进程跑在 `127.0.0.1:8000`**，故本 Task 的真机取证一律用 **8010**（`demo.ps1` 的缺省端口也定成 8010，理由写进了它的 `.PARAMETER Port` 文档），两次都没有撞。

---

## ② GC14：输入 / 期望输出 / 它覆盖的那一档 / 新指纹 / 硬编码「13」的连带清单

### 它覆盖的是哪一档

**spec §7.4 三档安全触发里的「BMI > 30」（触发 1）**。改前 13 例的 `bmi` 全落在 `[18.9, 25.7]`，触发 1「可求值但不命中」，于是 `needs_review` 与 `safety_substitution_count` 在黄金用例里**恒为 false / 0**——安全后置那一环只被 `tests/domain/test_prescription_safety.py` 的**合成输入**守着，没有一个「逐条人读确认过」的真实用例走到底。

⚠️ **它落在决策表已覆盖的 R1 行上**（与 GC01 同一行）：本例的用途是把**安全后置**那一环打通，**不是**补一行决策表。这一点写进了夹具的 `_meta.purpose`（免得下一个人以为 §6.2 的八行里有一行此前是空的）。

⚠️ **`muscle_low_p10` 那一档仍不可达，刻意留下**：黄金用例路径（`run_stratify._from_golden_cases`）**刻意不调** `resolve_muscle_lines`，而 14 人 < `MIN_SAMPLE = 30` → 肌肉量组不产出行 → P10 恒 `None` → 判据 `muscle_mass_kg < muscle_p10` 永不成立。**要让它可达就得把样本量抬到 30 人以上，那会改掉 `_meta.percentile_note` 的「24 行」与全部 14 例 P25 判定线的整个前提**（校内百分位取代国标常模兜底，14 例的 label / W / C / dominant_bucket 都要重算并重新逐条人读确认），故 Plan 02 Task 9 与 Plan 03 Task 9 两轮都决定不做。⚠️ 同理 **`needs_review = True` 那一档在 14 例里也仍不可达**（等价表 v1.0 给全部 5 个 high 动作都备了 low 替身，10 条映射，一格都查不到空）。两者的行为守卫都在 `tests/domain/test_prescription_safety.py`。**这一段逐字写进了夹具的 `_meta.caveats_training_package` ②**（硬规矩 #39：刻意留下的空白必须写下来）。

### 输入（**只新增一例，既有 13 例的输入一个字节未动**）

6 个短板判定项的原始值由**生产** `raw_from_score` 按目标得分反查，并当场用 `score_item` 正查复核精确往返（探针 `p04_gc14_build.py` 里的 `assert back == TARGET[...]`）：

```json
{
  "student_id": "GC14", "sex": "male", "age": 19, "years": 1.0,
  "snapshot_muscle_p20": 33.2,
  "body_comp": {"body_fat_pct": 28.0, "muscle_mass_kg": 45.0, "smi": null},
  "curr": {"height_cm": 175.0, "weight_kg": 95.0, "vital_capacity_ml": 3700.0,
           "sprint_50m_s": 9.5, "sit_and_reach_cm": 3.7, "standing_jump_cm": 228.0,
           "strength_count": 10.0, "distance_run_s": 292.0},
  "prev": <与 curr 逐字相同>
}
```

设计意图逐项可复核：

| 目标 | 取法 | 实测 |
|---|---|---|
| `bmi > 30` | 175.0 cm / 95.0 kg | `95 / 1.75² = 31.0204…` → `round(…, 1) = **31.0**` |
| `C = True` 且只由体脂率那一支 | 体脂率 28.0% > 男生 20%；肌肉量 45.0 kg **高于**本组 P20 33.2 | `body_comp_reasons = ["body_fat_high"]` |
| `W = 2` 且**主导桶是 speed_flexibility** | 50 米跑 40 分 < P25 **50**、坐位体前屈 60 分 < P25 **62**；其余 4 项取 GC13 的那一组（全 ≥ P25） | `W=2`、`dominant_bucket="speed_flexibility"`——⚠️ **13 例里没有一例的主导桶是它** |
| 落到一套**含 high 动作**的模板 | 上面三条 → R1 → 红 + speed + abnormal | `RED-SPD-ABN-05`（48 个 block，其中 **32** 个 high） |
| 趋势「稳定」 | `prev == curr` | `annual_change` 六项全 `0.0`、`trend="稳定"` |
| 不改 `_meta.percentile_note` 的「24 行」 | (male, 大一、大二) 是**已存在**的组 | 快照仍 **24 行**；只有那 6 行的 `sample_size` 从 **8 → 9**，`p10/p20/p25/p50/p75` 与 `source` **逐格不变**（探针 `p07_meta_facts.py` 把两侧的 24 行逐格对拍，`differing rows: NONE`） |

### 期望输出（23 个键，与既有 13 例**同键同序**；`assert list(GC14_EXPECTED) == list(expected[0])` 当场校过）

```
label=red  W=2  C=True  valid_count=6  dominant_bucket=speed_flexibility  trend=稳定
hit_rules=["R1"]  reason="短板 ≥2 项且体成分异常"
explain="红色层 ← 短板 ≥2 项且体成分异常（规则 R1）。依据：你的 50 米跑、坐位体前屈 在校内同龄男生中低于 P25（6 个有效项里 2 项短板）；体脂率 28% 超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。"
bmi=31.0  match_status=matched  template_id=RED-SPD-ABN-05  label_at_generation=red
week1_block0_exercise_ref="stationary_cycling"   ← **替身**，不是原 ref sprint_50m_intervals
week1_block0_hr_zone=[116, 137]  week1_block0_weekly_volume=38.4  week1_block0_volume_unit="min"
needs_review=false  safety_substitution_count=32
safety_triggers=["bmi_over_30", "body_fat_abnormal"]   ← **14 例里唯一同时命中两个触发的**
safety_skipped=["muscle_p10_missing"]
```

### 逐条人读确认（取法 = 跑一次生产、粘进夹具、然后手算复核；探针 `p05_gc14_handcheck.py`）

* **`week1_block0_weekly_volume = 38.4`** = block base（`work_min 3 × sets 4 = 12`，`rest_min 2` **不计入量**，§14 #36）× `sessions_per_week 4` × 个体修正 `1.0`（`volume_factor_band="mid"`）× `week_deltas[0] 1.0` = **48.0**，再 × `safety_volume_factor 0.8` = **38.4**。（`assembly_snapshot["weekly_volume_base"]` 是**按单位汇总**的 `{'min': 144.0}`，不是 block 级的 base，两者不是一个量——这一点在探针里当场撞到并改正。）
* **`week1_block0_hr_zone = [116, 137]`** = `[floor(194.7 × 0.60), ceil(194.7 × 0.70)]` = `[floor(116.82), ceil(136.29)]`，而 `194.7 = 208 − 0.7 × 19`（Tanaka，§14 #14）。⚠️ 替身**继承原动作的剂量**（`hr_zone` / `intensity_text` / `structure` / `volume_unit` / `sessions_per_week` 全原样，只换冲击等级），故这一格与替换前逐字相同——模板 block0 的 `intensity` 实测是 `Intensity(type='hrmax_pct', low=60.0, high=70.0)`。
* **`template_id = RED-SPD-ABN-05`** 按 (红层, `speed_flexibility`, `C=True`) 三元与 §7.2 勘误 ⑥ 的命名规则对过（`<层3>-<桶3>-<体成分3>-<序号2>`）。
* **`safety_substitution_count = 32`** = 该模板装配出的 48 个 block 里的 32 个 high（`sprint_50m_intervals → stationary_cycling`、`shuttle_run → brisk_walking`，等价表 v1.0）；探针 `p02_gc14_design.py` 逐套模板扫过 18 套，`RED-SPD-*` 两套的 high 数都是 32，且**全部 18 套的 high ref 都有 low 替身**（`unmapped=[]`），故 `needs_review` 结构上不可能为真。
* **`safety_triggers` 的序**：`_TRIGGER_MAP` 的迭代序把 `bmi_over_30` 排在 `body_fat_abnormal` 前面。
* **`safety_skipped = ["muscle_p10_missing"]`**：与既有 13 例逐字相同（`bmi_missing` 不出现正是 P9-A1 的效果）。
* **`warnings` 只有 1 条**（addon `energy_expenditure_plus_10pct` 的训练量未指定），与 32 条替换**不是一对一**——`Substitution` 是逐 block 实例的审计数据、`warnings` 按 ref 去重，两者不是一个量级（这一点也写进了 `_meta.expected_schema.safety_substitution_count`）。

### 既有 13 例**零影响**的取证

探针 `p04_gc14_build.py` 的第 ④ 段把 14 人一起跑一遍生产链路，逐例对拍既有 13 例的 `bmi` / `match_status` / `template_id`：**13/13 全部 `SAME`**。落盘脚本 `w01_write_gc14.py` 另有一道**字节级**断言：`reloaded["input"][:13] == original["input"]` 与 `reloaded["expected"][:13] == original["expected"]`（两侧不同源：左边读回磁盘、右边是改前内存里的原件），以及 `_meta` 的三处键集与 `muscle_p20_by_group` 逐格不变。

### `golden_cases.json` 的新指纹

⚠️ **先纠正派单第 7 节的一处事实**：这份文件住在 **`backend/tests/fixtures/golden_cases.json`**，**不是** `backend/data/golden_cases.json`（`Glob **/golden_cases.json` 全仓只命中前者）。⚠️ 而且它**没有任何指纹常量钉住**——全仓 5 组指纹是国标 CSV / `exercises.yaml` / `exercise_equivalence.yaml` / `alert_rules.yaml` / 18 套模板 YAML，一个都不在它上面。故 Plan 02 Task 9 的 P9-A3「六步程序」里**第 4 步（改常量）与第 5 步（跑指纹测试）对这份文件不存在**；我按剩下的四步照办，并**补做了那两步的等价物**（下面给出两个 sha256 供后续对账）：

| 步骤 | 做了什么 | 取证 |
|---|---|---|
| 1 先算新指纹 | 改前先算两个 sha256 | as-is `A08B6AE9A463BBA3`、CRLF→LF `E0E2DABA0FE97344`（探针 `p06_json_roundtrip.py`） |
| 2 改文件 | **不用编辑器**：先实测 `json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\\n"` 与 LF 归一化后的原文**逐字相等**，于是「load → 改 dict → dump」不会顺手动到别处；`_meta` 的 24 处改写一律**精确串替换 + 断言恰好命中一次**（脚本 `w01_write_gc14.py`） | 脚本 24 处全 ✓，任何一处抄错都会 `AssertionError` 而不是静默漏改 |
| 3 用 `read_bytes()` 复核 CRLF | 改后 **CRLF = 959 / bare LF = 0**（改前 892 / 0，行数 892 → 959） | 同上脚本的末段断言 |
| 4 改常量 | **不适用**（这份文件没有指纹常量） | — |
| 5 跑指纹测试 | **不适用**；改跑等价物：全量 1226 passed（当时）+ 变异自证 3/3 | 第 ② 节末 |
| 6 另四个指纹逐字不变 | 结案时**五个**全部复核 | 第 ⑧ 节 |

**新指纹**：`51 619 B / 959 行`，sha256[:16] **as-is `39FC9C29D9106C47`**、**CRLF→LF `9FB1C619F896D418`**。
⚠️ 工作树行尾是 CRLF、index 是 LF（`git ls-files --eol` 实测 `i/lf w/crlf attr/`，`.gitattributes` **不覆盖** `backend/tests/**`），`core.autocrlf=true`，故写 CRLF 与写 LF 得到**同一个 blob**；选 CRLF 是为了与文件既有的 892 行逐一致、不制造混合行尾。

### 硬编码「13」的连带清单（硬规矩 #88：先跑一次全量、把红掉的相等断言逐个收进来）

**做法**：先把断言从 `== 13` 改成 `== 14`、**亲眼看它红**（`AssertionError: assert 13 == 14`），再写夹具转绿。然后跑**全量**，看还有哪一处相等断言变红。

**结果：全量 1225 → 1226 passed，红的只有那一个测试函数里的 3 条相等断言，没有第二处。**

| 位置 | 改法 |
|---|---|
| `tests/integration/test_golden_cases.py::test_golden_case_input_and_expected_align_one_to_one_by_student_id` | `len(input) == 13`、`len(expected) == 13`、`len(set(_CASE_IDS)) == 13` → 三处 **14** |
| 同文件的参数化 `test_golden_cases_reach_the_training_package` | **不用改**：它按 `_CASE_IDS` 参数化，13 → 14 个 case 自动跟上（那正是「+1 条 passed」的来源） |

⚠️ **这与 Plan 02 Task 6 的教训相反**：那一轮「漏的两格不是『表数这一个事实的副本』，而是**别的事实被同一改动证伪**」。本轮实测**没有那一类**——加一例黄金用例不改表数、不改扫描面、不改端点数、不改任何分布断言（`test_target_layer_distribution_within_tolerance` 跑的是 500 人 `build_dataset`，与夹具无关）。**但我不据此断言「下次也不会有」**，故把「先跑全量」这一步照做了。

**散文里的「13 例 / 13 人」另清了 28 处（7 个文件）**，纪律是「**只改当前事实、不动历史陈述**」，一律字节级替换 + 断言恰好命中一次（脚本 `w02_thirteen_fallout.py`），改完逐文件用 `read_bytes()` 复核行尾种类不变（7 个文件全是 w/crlf、bare LF 仍为 0）：

* 改了：`tests/integration/test_golden_cases.py`（12 处）、`app/pipeline/run_stratify.py`（5）、`app/domain/percentile.py`（2）、`tests/domain/test_percentile.py`（1）、`tests/domain/test_stratify.py`（2）、`tests/pipeline/test_prescription_stage.py`（6）
* **刻意不动**（绑时点的历史陈述，改了就变假）：`run_stratify.py` 的「代价是 13 例的 `"bmi"` 全 `None`」（Task 7 时点）、`test_prescription_stage.py` 的「13 例夹具的**顶层没有**它们」与「三档安全触发在 13 例里**一档都走不到**」（同为 Task 7 时点）。`test_golden_cases.py` 那句「本轮逐条复核的结论：13 例全部为真」改成**显式绑时点**（「Plan 02 Task 9 那一轮……当时的 13 例」）而不是把 13 抹成 14。
* 夹具 `_meta` 里另有 **24 处**（`purpose` / `expected_from` / `expected_schema` 的 8 个键 / `training_package_provenance` / `caveats_training_package` 的 ②③ / `input_schema` 的 2 个键 / `bmi` / `percentile_note` 的 3 处），随 commit ① 一起落。

### GC14 的变异自证（3/3 killed，探针 `p08_gc14_mutations.py`）

Ruling 1 说本 Task 不要求变异，但 Task 2/3/4/5/7/8 六个实现者都自己做了、控制者六次都采纳，故照做。**三条都打在夹具上、跑完从字节备份还原并复核 sha256**（`39FC9C29D9106C47` 逐字相同），不用 `git checkout`：

| 变异 | 结果 | 红的断言 |
|---|---|---|
| **M1** `expected[13]["safety_substitution_count"]` 32 → 0 | **KILLED** | `safety_substitution_count: 期望 0 / 实际 32` |
| **M2** `expected[13]["week1_block0_exercise_ref"]` `stationary_cycling` → `sprint_50m_intervals`（即改回**替换前**的 ref） | **KILLED** | `week1_block0_exercise_ref: 期望 'sprint_50m_intervals' / 实际 'stationary_cycling'` |
| **M3** `input[13]["curr"]["weight_kg"]` 95.0 → 78.0（bmi 31.0 → 25.5，触发 1 不再命中） | **KILLED** | `explain` 全文比对红（年均变化 `+0.0` → `+3.0`，因为 `prev` 仍是 95.0） |

⚠️ M2 是三条里最要紧的：它证明「blocks[0] 是**替身**」这一格真的被钉住——没有它，谁把 `apply_safety` 的替换分支改坏（例如 `ImpactLevel.HIGH` 写成 `MEDIUM`），14 例的 `week1_block0_exercise_ref` 会集体退回原 ref 而**没有任何断言变红**。

---
""")

BLOCKS.append("""## ③ 端到端冒烟：8 步逐步断言点 + 它走真实 HTTP 的证据

**文件** `backend/tests/api/test_end_to_end.py`（**5 条**测试），主测试是
`test_the_whole_loop_runs_over_real_http`——**一条测试走完八步**，任何一步断了它就红。

### 它走的是真实 HTTP（证据）

* **客户端**：`fastapi.testclient.TestClient`（`tests/api/conftest.py` 的 `client` 夹具），它内部是 **httpx** 的 `ASGITransport`，**基址恒为 `http://testserver`**。
* **因此被 exercised 的是一整条**：路由匹配 → 依赖注入（`get_db` / `current_student` / `current_teacher`）→ 身份与作用域闸门（`require_scope` / `require_teacher`）→ 请求体校验（Pydantic）→ 端点体 → `response_model` 序列化 → 错误处理器（`app/api/errors.py` 的六个 handler）。直接调 `run_daily` / `evaluate_alerts` 的版本住在 `tests/pipeline/test_daily.py` 与 `tests/pipeline/test_alert_stage.py`，**两处并列、不合并**。
* **身份请求头是承重的**：②⑦ 用 `X-Student-Id`、①③⑥ 用 `X-Teacher-Staff-No`、⑤⑧ 走不带 `security` 的泛型读端点。把 `require_scope` 改坏，本文件红在 ②（403），而 `tests/api/test_scope.py` 红在它自己的矩阵上——两条判据不同、不重复。
* ⚠️ **另有一份「真 TCP」的证据**：第 ⑤ 节的 `demo.ps1` 真机取证走的是**真的 uvicorn 工作进程 + 真的磁盘 SQLite 文件**（`http://127.0.0.1:8010`），探针 `p12_live_server_evidence.py`。两份证据互补：`TestClient` 那一份在 CI 里跑、证明代码接得上；真机那一份证明「一条命令能把系统跑起来」。

### 八步与逐步断言点

| 步 | HTTP 往返 | 断言点（全部字面写在测试里，两侧不同源） |
|---|---|---|
| **①** | `POST /api/pipeline/run-daily` `{"business_date":"2025-09-15"}` + 教师头 | 200；`status=="success"`；`semester_id` == **按名字**从库里查出来的 `2025-2026-1` 那个 id（Ruling 173 的同一条纪律：不带 `order_by` 的 `scalar` 会取到先插入的上学年）；`business_date`；`csv_dir` == tmp 目录（**数据源留痕**：读的确实是那三份 CSV，不是恒为空的缺省目录）；`extracted_fitness > 0`；`prescription_count == 60`；四个分层计数之和 `== 60`；**`alert_count == 0`**（三源还空着——这一格是 ④ 那句 `== 2` 的**对照**，少了它「预警阶段压根没跑」与「跑了但没触发」在 ④ 上同形） |
| **②** | `GET /api/students/{id}/prescriptions/current?as_of=…` + 学生头 | 200；`student_id`；`status=="active"`；`generated_on`。⚠️ **并带一格越权对照**（Review Focus 第 1 条）：换一个 `X-Student-Id` 读同一个人 → **403**，`error.code=="forbidden"`。少了它，「200」与「任何 id 都 200」在颜色上无法区分 |
| **③** | `POST /api/class-sessions`×3 → `POST …/open-rpe`×3 → `POST /api/rpe-records`×3（`rpe=9`） | 建课次 201；`open-rpe` 200 + `rpe_opened is True` + `already_open is False` + `len(rpe_token) == 16`（与 `ClassSession.RPE_TOKEN_LEN` 由第 5 条测试钉在一起）；三个口令**各不相同**；交快评 **201 + `Location`**、`student_id` 由服务端从头填、`rpe == 9`。⚠️ **并带一格口令对照**：拿第一节课的口令去交第二节 → **403 `invalid_rpe_token`**（⚠️ 是 403 不是 409：四道闸门按「从便宜到贵」排，口令那一道在**插入之前**），且库里**仍是 3 条**快评、`class_session_id` 集合与三次响应的 id 逐个相等 |
| **④** | `POST /api/pipeline/run-daily`（**同一天 = 重放**） | 200；`status=="success"`；**`daily_sync_run_id` 与 ① 逐字相同**（幂等键 `(semester_id, business_date)` 命中同一行，而 `_replay_cleanup` 已按 `batch_id` 删掉上一批的七张表重算）；`prescription_count` 仍是 60（**重放不该翻倍**）；**`alert_count == 2`** |
| **⑤** | `GET /api/alerts?limit=200` | 200；`total == 2`；`rule_id=="RED_RPE_SUSTAINED"` 的**恰好 1 条**（四列唯一约束 `(rule_id, subject_key, semester_id, window_key)` 的去重口径）；`student_id`；`level=="red"`；`status=="pending"`；`semester_id`；**`window_key == f"rpe{第三节课的 id}"`**（期望侧用 ③ 的响应**现拼**、与被测侧不同源——这一格是 Review Focus 第 3 条的落点：键锚在**凑满 streak 那一次**，不是最后一次）；`subject_key == f"student:{id}"`；另一条是 `YELLOW_CLASS_RPE_HIGH` 且落在**这个教学班**上 |
| **⑥** | `POST /api/alerts/{id}/handle?as_of=…` `{"action":"reduce_20pct"}` + 教师头 | 200；`alert.status=="handled"`；`handled_action=="reduce_20pct"`；⚠️⚠️ **`adjustment is None`**——管道在 ④ 已经**自动**写过一条 `weekly_adjustment(source="auto", factor=0.8)`，故教师这一次点击**撞上唯一约束、没有第二次减量**。少了这一格，「教师点两次 = 0.8 × 0.8 = 0.64」这个失效在真实链路上就没人看着（⑦ 的 `factor == 0.8` 只钉了结果、钉不住「没有新写一行」）；`notification` **非空**、`title=="本周训练量已减 20%"`、`recipient_kind=="student"`、`recipient_id` 是那个学生（⚠️ 消息**照发**：教师点了就该告知学生，哪怕调整是几天前写的） |
| **⑦** | `GET /api/students/{id}/weekly-sheet?as_of=…` + 学生头 | 200；`week == 1`；**`factor == 0.8` 而不是 `0.64`**；`reasons == ["RED_RPE_SUSTAINED"]`；`sources == ["auto"]`；`paused is False`；`sessions` 非空；⚠️ **且 block 的 `weekly_volume == ② 读到的骨架 × 0.8`**（`pytest.approx(abs=0.05)`）——两侧是**两个不同的投影**（`weekly_sheet_payload` vs `training_package_payload`），故这一格钉的是「减量真的落到了学生看到的量上」，不是「两个键都在」 |
| **⑧** | `GET /api/notifications?limit=200` | 200；那个学生**恰好 1 条**（两条 `RED_*` 规则里只有被教师处置的那一次推送）；`title`；**`alert_id` 指回 ⑤ 那一条**；`prescription_id` 与 ② 读到的逐字相同；`is_read is False`（§9.2 的红点）；`total == 2`（学生 1 + 教师 1，教师那一条是班级级预警的「课堂 RPE 均值偏高」） |

### 数据从哪来（以及**绝不碰**哪两个禁区）

* 组织结构：`seed_database(session, SeedConfig(students=60, weeks=16, seed=20250828))`——与 `tests/pipeline/test_daily.py` 的 `CFG` **同一组参数**，故两个文件的数字可以直接对读。
* 体测数据：`write_csv(build_dataset(CFG), tmp_path/"lepao")`，由 `MockLePaoAdapter` 在 ①④ 里**真的抽取**进来（走 `app.adapters.factory.build_adapter`，不手搓适配器）。
* 库：`tests/api/conftest.py` 的内存 SQLite（`sqlite://` + `StaticPool`）。
* CSV 目录经 **`PE_CSV_DIR` 环境变量**告诉服务进程（`monkeypatch.setenv`），**不是** `app.config.DEFAULT_CSV_DIR`。
* ⚠️ 跑完**不留任何磁盘文件**（`tmp_path` 由 pytest 回收），`backend/pe.db` 与 `backend/data/seed/` 一个字节都不动。
* ⚠️ 业务日期刻意取 **2025-09-15（周一）**，故周报阶段一次都不跑（`is_report_day` 只在 `weekday()==6` 为真，探针 09 实测 `weekly_class_report` 行数 = 0）。挪到周日会让 ① 的 `extracted_*` 与 ④ 的 `alert_count` 全部变值（水位线与「本周」都跟着挪）。周报那一环由 `tests/pipeline/test_report_stage.py` 与 `tests/api/test_dashboard.py` 守。

### 「挑哪个学生」是一次真的查询、不是硬编码的 id

`_pick_student_with_a_section` 三张表 join（`prescription` × `enrollment` × `course_section`）+ `ORDER BY student_id, course_section_id` + `LIMIT 1`。三条理由都写进了它的 docstring：① `seed_database` 的学生 id **不是** 1..60 连号、`student_no` 也不按 id 升序，写死一个 id 会让本文件在生成器改一次编班顺序之后红在一个看不懂的地方；② 一个学生可以同时在**两个**班里（60 人 → 120 行 `enrollment`），故 `ORDER BY` 的第二格是承重的；③ **必须 join `course_section` 并限定 `semester_id`**（硬规矩 #114：「曾经成立」与「现在成立」是两个判据）——少这一格会挑到一个「在上学年的班里」的学生，③ 建的课次于是落在上学年那个班上，而 `alert_stage._rpe_rows` 按 `CourseSection.semester_id == semester_id` 过滤时**一条都读不到**，⑤ 查不到预警，而报错信息完全指不出真因。

### 另外 4 条测试

| 测试 | 它钉的是 |
|---|---|
| `test_the_run_daily_result_covers_every_daily_sync_run_column` | `RunDailyResult` 的 `model_fields` == `DailySyncRun.__table__.columns`（`id` → `daily_sync_run_id`）+ `csv_dir`；**两侧不同源**（一侧 ORM、一侧 Pydantic），故给 `daily_sync_run` 加一列而忘了投影会当场红。另钉 `len(columns) == 19` |
| `test_run_daily_is_registered_with_the_documented_method_and_security` | 路径 / **只有 POST**（没有 GET：一次批处理不是一个可读的资源）/ `security == [{"X-Teacher-Staff-No": []}]` / `tags == ["pipeline"]`。被测侧用 `app.openapi()["paths"]` |
| `test_the_csv_dir_comes_from_the_environment_and_not_from_the_request` | 请求模型的字段集**恰好** `{business_date, semester_id}`，6 个候选名（`csv_dir` / `adapter` / `adapter_kind` / `kind` / `base_url` / `token`）一个都不在；`CSV_DIR_ENV_VAR == "PE_CSV_DIR"`；未设 / 设成空串都退回 `DEFAULT_CSV_DIR`；设了就用它。⚠️ 判据是**字段集**而不是「多传会 422」：Pydantic 缺省 `extra="ignore"`，「多传会被静默丢掉」本身**不是**防线 |
| `test_the_class_session_model_exposes_the_token_length_the_loop_asserts` | 把 ③ 里那个字面量 `16` 与它的所有者 `ClassSession.RPE_TOKEN_LEN` 钉在一起，于是「专家把口令长度改成 32」时红的那一条会说清是口令长度变了、而不是让端到端测试红在一个看不懂的地方 |

### ⚠️ 顶回简报一处：`GET /api/alerts?rule_id=…` 这个筛选**今天不存在**

简报的第 ⑤ 步逐字写的是 `GET /api/alerts?rule_id=RED_RPE_SUSTAINED`（有一条）。而**泛型 CRUD 工厂的 list 端点只有分页、没有任何筛选**（`app/api/crud.py` 的 `list_rows` 签名是 `page: Page = Depends()`，只有 `limit` / `offset`；FastAPI 会**静默忽略**未知的查询参数）。三条候选处置：

1. 给 `build_crud_router` 加一套通用筛选机制 —— **否**：它动 23 个资源，而 `tests/api/test_crud.py` 有一批钉死的计数与读写矩阵断言，一次改动面远超本 Task；
2. 在 `routers/alerts.py` 里另写一个特例 `GET /api/alerts` —— **否**：它会**吞掉**泛型工厂为 `alerts` 注册的那个 list（同形、特例在前），于是 `test_crud.py` 的读写矩阵当场红，而「一个资源的 list 有两个实现」正是本仓最反对的形状；
3. **采**：测试打 `GET /api/alerts?limit=200`，在客户端按 `rule_id` 过滤后断言**恰好 1 条**，并同时断言 `total == 2` 与另一条是 `YELLOW_CLASS_RPE_HIGH`。

⚠️ 处置 3 其实是**更强**的断言：它不只说「有一条 RED_RPE_SUSTAINED」，还说「整库这一批只有 2 条预警、另一条是班级级的那一条」。⚠️ 而「教师端要按 `rule_id` / `status` / `level` 筛选预警队列」是一条**真实的能力缺口**，已登记进第 ⑦ 节的待清扫并移交 Plan 04。

### 变异自证（3/3 killed，探针 `p10_e2e_mutations.py`）

三条各打一个**层间接缝**（那正是本文件声称要证明的东西）：

| 变异（打在**生产代码**上） | 断的接缝 | 结果 |
|---|---|---|
| **M1** 删掉 `api_router.include_router(pipeline_router)` 那一行 | api → pipeline | **KILLED**（① 得 404 `{"error":{"code":"not_found",…}}`；另一条 OpenAPI 面测试也红） |
| **M2** `alert_stage.AUTO_REDUCTION_FACTOR` `0.8` → `0.85` | pipeline(alert) → api(处方侧读) | **KILLED**（⑦ 报 `factor 应当是 0.8（减 20%），实际 0.85`） |
| **M3** `alerts.py` 推送标题「本周训练量已减 20%」→「…25%」 | api(alerts) → notify → 学生端 | **KILLED**（⑥ 报标题不符） |

三个文件跑完从字节备份还原，sha256[:16] 逐个复核逐字相同（`B668425290F429B7` / `C8DC575EAA7C8419` / `870C7973A7F78148`），行尾种类不变（三个都是 w/lf）。

⚠️ **一处对派单纪律的偏离，如实报**：TDD 要求「先写失败的测试、亲眼看它红」。GC14 那一条我照做了（先改 `== 13` → `== 14`，亲眼看到 `assert 13 == 14` 红，再写夹具转绿）。而**端到端这一条我把端点与测试一起写了**——因为 `POST /api/pipeline/run-daily` 在本 Task 之前**根本不存在**，测试先写的话红的是「路由不存在」而不是「逻辑不对」，那一格红的信息量与 M1 变异完全重复。故我用 **M1 变异**当作它的 RED 证据（删掉 include 那一行 → ① 404 → 红），这与「先写测试看它红」证明的是同一件事：**这条测试真的能抓到「API 层没接上」**。

---
""")

BLOCKS.append("""## ④ `progress_board` 的填充口径 + 标准化得分的新住址

### 裁定与它的落地

**控制者的裁定**：让 `report_stage` 在生成周报时把标准化得分**算出来**填进 `progress_board`，而不是让前端去调 `GET /api/mini-tests/normalized`。**理由**：周报是快照，而快照里的量应该在生成时就算好——让读侧现算等于把「哪一周的进步榜」这个口径交给了客户端。

**它修掉的缺陷是真的**：改前 `class_snapshot` 读的是 `mini_test.normalized_score` 那一列，而那一列的**唯一写入方是 `app.demo_data.build_demo_feedback`**（写的是演示口径的近似值），生产路径上（教师经 `POST /api/mini-tests/batch` 录入）**恒为 `NULL`** → `progress_board` 全员 `unmeasured` → **进步榜在真实数据下一整块是空的**。
**真机取证**（第 ⑤ 节）：改后 `GET /api/dashboard/weekly-class-report/1?week=6&as_of=2025-10-12` 的 `progress_board` 是
`{"top_n": 10, "top": [{"student_id": 10, "change_pct": 235.88}, {"student_id": 36, "change_pct": 88.72}, {"student_id": 35, "change_pct": 79.41}, …]}` ——**非空**。

### 新住址：`app/domain/report.py`（**不写第二份**）

派单逐字要求「不要写第二份，把它提到一个两层都能 import 的住址（`app/domain/` 或 `app/pipeline/`）」。**选 `domain`**，两条理由：① `pipeline` 反向 import `api` 被架构守卫禁止，而 `api → domain` 与 `pipeline → domain` 都是许可方向；② 它**是纯函数**（无 I/O、无时钟、样本由入参给），而 domain 正是纯函数的住址（先例：Plan 03 Task 7 把 `training_days_of` 从 `feedback.py` 提到 `app.pipeline.prescription_stage`，同为「第二个消费者出现了，故提到两层都够得着的住址」）。

⚠️ **不新造一个只有一个函数的 domain 模块**：spec §5 的第 7 阶段 `Aggregate`（「聚合 RPE / 打卡 / 二次小测，**计算标准化得分**」）**今天没有自己的模块**，它的「聚合」那一半就是 `app/domain/report.py` + `app/pipeline/report_stage.py` 做的事，故「计算标准化得分」那一半也住在那里。这一节写进了 `report.py` 的模块 docstring（新增一节「为什么 §8.1 的算式住在『§8.5 的模块』里」）。

三个新名字（`__all__` 从 26 → 29，仍按大小写不敏感的字母序插）：

| 名字 | 是什么 |
|---|---|
| `SCORE_PRECISION = 2` | 此前是 `app.api.routers.feedback.SCORE_PRECISION`；那个 `56.665` 浮点坑的说明随它一起搬 |
| `shuttle_percentile(seconds, sample) -> float` | **班内百分位反查**，返回**未 round** 的裸值。此前是 `feedback._shuttle_percentile`。原 docstring 的全部内容（并列取中点、`n = 1` 给 50.0 及其可达性、空样本刻意不兜底）逐字保留，另加一段「为什么搬家」与一段 Plan 04 移交 |
| `mini_test_scores(squat_30s_count, shuttle_20m_s, sample) -> dict` | 三格 `{squat_score, shuttle_score, composite}`，即 spec §8.1 的三行算式 |

**两个消费者**：`app/api/routers/feedback.py::normalized_scores`（删掉 `_shuttle_percentile` 与 `SCORE_PRECISION`，`__all__` 9 → 8，`collections.abc.Sequence` 那个 import 一并消失）与 `app/pipeline/report_stage.py::_composite_of`（新增）。**算式一字未改**，端点响应三格的键序也逐字相同（`**mini_test_scores(...)` 的展开序就是那一份的书写序）。

### `class_snapshot` 的填充口径（三个决定，各有一条理由）

1. **样本按「本教学班 × 该行所属周次」取**，不是一律用报表周：一个学生的最近两次小测可以落在**不同的周**（他缺测过一周），而 spec 逐字是「**该教学班内**折返秒数的百分位反查」——「班内」是空间维度、没说时间维度，故取**同一周**的全班样本才是「那一次测评时他相对谁」。用整个学期的样本会把「第 2 周他排第 3」算成「本学期他排第 11」。落地是 `class_snapshot` 里多一个 `by_week: dict[week, list[MiniTest]]`，`_composite_of(row, by_week[row.week])`。
2. **缺测的行不进样本**：`sample = [r.shuttle_20m_s for r in week_rows if r.shuttle_20m_s is not None]`。一个「没测」的人若被当成「最慢的那个」，会把全班的百分位一起往下拽（所有人都变好）。⚠️ 于是 `row.shuttle_20m_s is not None` 时样本必非空（至少含它自己），`shuttle_percentile` 那个「空样本 → `ZeroDivisionError`、刻意不兜底」的契约不会在这一侧被踩到。
3. **只取三格里的 `composite`**：进步榜要的是一个**可排序的单一量**，而 `squat_score` / `shuttle_score` 在周报里没有位置（`weekly_class_report` 只有 5 个 `JsonText` 列 + 1 个 `Text` 列）。教师要看三格的分解，走那个端点（它是**实时**的），不走周报快照。

⚠️ **`mini_test.normalized_score` 那一列仍然不回写**：让一个 `GET` 有副作用本仓不接受，而让批处理去 UPDATE 一张**教师手工录入**的表会把「教师录的是什么」与「系统算出来的是什么」混在同一列上（`mini_test` 是 RCT 的过程数据，它的 `on_delete="forbid"` 就是为这件事）。算出来的分只落进 `weekly_class_report.progress_board` 那个 `JsonText` 列——它本来就是「一份快照」。

⚠️ **代价（硬规矩 #39，已登记并移交 Plan 04）**：那一列今天仍有**两个读者**（`alert_stage._mini_test_improved` 与 `_student_signals`，`GREEN_MASTERY` 的三个指标之一），它们读的是**列里的值**（demo_data 写的演示近似值），而进步榜读的是**算出来的值**——**两者可以不同**。要统一就得让 `alert_stage` 也现算，而它按学生分组、拿不到「班」这个维度，先要裁决「一个学生在两个班时按哪个班算」，故不在本 Task 顺手做。这一段同时写在 `app/domain/report.py`（模块 docstring 的「三个两套并存 ③」+ `progress_board` 的 docstring 首段）、`app/pipeline/report_stage.py`（模块 docstring 末节 + `_composite_of`）、`app/api/routers/feedback.py`（模块 docstring 的「刻意不做」第 3 条）、`app/db/models/feedback.py`（`MiniTest` 的类 docstring）与 spec §8.1 的勘误里。

### AST 守卫：定义份数 == 1（照 Task 7 的形状）

`tests/domain/test_report.py::test_the_mini_test_normalization_has_exactly_one_definition`：扫 `backend/app/**/*.py`，数 `tree.body` 里名字落在 `("shuttle_percentile", "_shuttle_percentile", "mini_test_scores", "_mini_test_scores")` 的 `FunctionDef` / `AsyncFunctionDef`，断言**恰好 2 份、且都在 `app/domain/report.py`**（`shuttle_percentile` 与 `mini_test_scores` 各一份）。
⚠️ 形状逐字照 `tests/pipeline/test_alert_stage.py::test_training_days_of_has_exactly_one_definition`（同为「一个私有函数因为第二个消费者出现而搬家，搬家之后**旧的那一份必须真的消失**」）。
⚠️ **它守不住什么**（写进了 docstring）：它数的是**函数名**，故谁把算式**内联**进 `report_stage` 或某个 router（不再是一个有名字的函数）本条不红。那一档由两条兜：`app/domain/` 的 **100% 分支覆盖**（内联进 pipeline/api 的那一份不在覆盖率口径里，于是它没有测试），以及 `test_the_api_layer_and_the_report_stage_give_the_same_composite`（一侧调 domain、一侧调 `_composite_of`，断言两个综合分相等且都等于手算的 `56.67`）。
⚠️ **M7 变异证明了它有牙**：往 `report_stage.py` 塞第二份 `def shuttle_percentile(...)` → 本条红，报 `应当只有 2 份定义…实到 3: [('app/domain/report.py','shuttle_percentile',599), ('app/domain/report.py','mini_test_scores',654), ('app/pipeline/report_stage.py','shuttle_percentile',243)]`。

### 支 I 的 12 条测试与 4 条变异

**12 条**（`tests/domain/test_report.py` 新增「支 I」，`__all__` 的三个新名字都进了 import 清单）：算式三格的字面值（样本 `[10,10,12,13,14,15]` / 本人 `10.0` → 百分位 `83.3333…`、深蹲 30 → **综合分 56.67**）；**56.67 而不是 56.66**（先把百分位 round 成 83.33 再平均得 `(30+83.33)/2 = 56.665`，而 CPython 的 `round(56.665, 2) == 56.66`——两条测试互为正反面，其中一条把那个坑写成一个可执行的事实）；并列取中点（三人同秒 → 同一个 50.0）；`n = 1` → 50.0（并写明 Plan 04 应在 `scored_count == 1` 时显示「无排名」）；空样本 → `ZeroDivisionError`（刻意不兜底：兜一个 `0.0` 会把「算错了」静默变成「这个学生最差」，而 0.0 是一个**合法的**百分位值）；三档缺测 → 对应的格子是 `None` 而不是 0（把 `None` 当 0 会让综合分变成「另一项的一半」，而它会直接掉进 `progress_board` 的**退步名单**，教师于是去找一个其实没退步的学生谈话）；`squat_score` 一律 `float`（那一列是 `Integer`，而 `composite` 可能是 `x.5`）；AST 守卫；两个消费者同值。

**+1 条管道侧**（`tests/pipeline/test_report_stage.py::test_a_missing_measurement_makes_the_student_unmeasured_not_zero`）：这一档在 Task 9 之前**结构上不可达**（那时直接读列、而 `_mini` 助手给的是非空综合分），改成「生成时算」之后它变成真实可达的一档（教师只录了深蹲、折返那一格空着）。⚠️ 它同时钉住「缺测的行不进百分位样本」：若把「没测」当成「最慢的那个」塞进样本，学生 1 的百分位会从 `50.0` 变成 `100.0`、综合分从 `66.0` 变成 `91.0` → `+10.0%` 变 `+51.67%`，本条当场红。

**改动的既有测试**：两个 `_mini` 助手从「给综合分」改成「给**原始测量值**」（`tests/pipeline/test_report_stage.py` 与 `tests/api/test_dashboard.py` 各一份，共 10 个调用点）。两处各持一份 `SHUTTLE_TIED = 30.0` 的**字面量**（不互相 import、也不 import 被测模块）：全班的折返秒数一律相同 → 所有人**并列** → 班内百分位一律 `50.0` → `composite = (深蹲次数 + 50) / 2`，于是每个调用点的期望综合分都能**口算**对上（70 → 60.0、82 → 66.0、58 → 54.0、90 → 70.0、130 → 90.0），而 `normalized_score` 一律留 `NULL`（那正是「这一列在生产路径上没人写」的真实形状）。

**4 条变异，4/4 killed**（探针 `p11_progress_board_mutations.py`，两个文件跑完从字节备份还原、sha256[:16] 逐字复核相同：`08CB210F2131E0E9` / `A140FD725ABDDC2B`）：

| 变异 | 结果 |
|---|---|
| **M4** `shuttle_percentile` 的 `0.5 * tied` → `0.0 * tied`（即改成「严格小于」口径） | **KILLED**（8 条红） |
| **M5** `mini_test_scores` 的 composite 改成先 round 百分位再平均（`56.67` → `56.66`） | **KILLED**（3 条红） |
| **M6** `_composite_of` 改回读 `row.normalized_score` 那一列 | **KILLED**（3 条红）← **最要紧的一条**：它正是本次裁定要修的那个缺陷，红说明那两条进步榜测试**不是哑弹**（`_mini` 助手已不再给那一列喂值） |
| **M7** 往 `report_stage.py` 塞第二份 `shuttle_percentile` 定义 | **KILLED**（AST 守卫报 `3 != 2`） |

### ⚠️ 顺带修了一处散文里的假数（Critical，当场修）

`tests/pipeline/test_report_stage.py::test_a_mini_test_in_a_future_week_is_not_read` 的 docstring 此前印「不夹上界的话，本条会算出 `60 → 90 = +50%`」——**那个数对不上任何一条路径**：取的是 `rows[-2:]`（最后两行），故被读到的是第 **2** 与第 **3** 周，即 `66.0 → 90.0 = +36.36%`。按实测改写，并在 docstring 里写明「此前印的那个数是假的、以及它假在哪」。

---
""")

BLOCKS.append("""## ⑤ `demo.ps1`：全文要点 + 一次真机跑的取证

**两个新文件**：`backend/scripts/demo.ps1`（PowerShell 5.1 入口，171 行 / 9 750 B，UTF-8 **带 BOM** + CRLF）与 `backend/scripts/demo_bootstrap.py`（数据准备那一半，5 步 + 复核）。
⚠️ `backend/scripts/` **不在** `test_layering.SCANNED_DIRS`（pipeline / db / domain / api）里，故架构守卫不把这两个文件当生产层——它们是开发期工具，与 `app/seed/` 同一档。⚠️ 但 `test_absolute_folding_matches_resolve_name` 的「扫真仓」那一段会对 `backend/**/*.py` 逐个 AST 解析，故 `demo_bootstrap.py` **必须能被 parse**（`python -m py_compile` 过），且它一条相对导入都没有。

**一条命令**：

```powershell
powershell -ExecutionPolicy Bypass -File backend\\scripts\\demo.ps1              # 灌 pe_demo.db + 在 :8010 起 uvicorn（前台，Ctrl-C 停）
powershell -ExecutionPolicy Bypass -File backend\\scripts\\demo.ps1 -DryRun      # 只灌一个临时库、跑完删掉、backend/ 下不留任何文件、不起服务（给 CI）
```

### 三条纪律逐条落地

1. **第一步删旧库**（连 `-journal` / `-wal` / `-shm` 四个后缀一起删，删不掉就 `throw`）。理由：`init_db` 走 `Base.metadata.create_all`，对**已存在的表原样跳过**——一个旧库不会报错、也不会补上新增的 NOT NULL 列，端点会在离真因很远的地方 500（Plan 03 Task 2 撞过一次，那次是 `training_log.submitted_at`）。⚠️ **「删文件」留在 shell 里、不在 bootstrap 里**：只有 shell 知道用户想删哪个文件，而 bootstrap 收到的是一个 URL，它无权替用户决定「这个文件可以删」。
2. **显式设 `PE_DB_URL` 到 `pe_demo.db`**，而那个值是从 `app.main.DEMO_DB_URL` **读出来的**（`python -c "from app.main import DEMO_DB_URL; from sqlalchemy.engine import make_url; print(DEMO_DB_URL); print(make_url(DEMO_DB_URL).database)"`），**不在脚本里敲第二遍路径**（那是第二个所有者）。⚠️ 剥路径用 `make_url` 而不是字符串替换：Windows 的盘号里就有一个冒号，手工 `-replace '^sqlite:///',''` 在 UNC 路径（`sqlite:////server/share/x.db`）上会错。⚠️ 不设它 → `_resolve_db_url` 落到 `DEFAULT_DB_URL` = **`backend/pe.db`（禁区）**。`PE_CSV_DIR` 同理（它是 `POST /api/pipeline/run-daily` 的数据源覆盖口）。
3. **一条 `python -m …` 都没有**。`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` 三个 CLI 的 `main()` 各自把缺省值写死在**两个禁区**上。故 bootstrap 一律 **import 函数 + 显式传路径**，并自带**两道前置守卫**（`--csv-dir` 撞上 `backend/data/seed` 或 `--db-url` 以 `pe.db` 结尾都当场 `SystemExit`）；`demo.ps1` 在灌完数据之后**再复核一次**两个禁区，不符就 `throw`。CSV 也落在 `$env:TEMP`，故 `backend/` 下唯一新增的文件是 gitignore 里的 `pe_demo.db`。

### ⚠️ `demo.ps1` 是 UTF-8 **带 BOM**，与 commit 信息刻意相反

开发机的 shell 是 **Windows PowerShell 5.1**，它读一个**没有 BOM** 的 `.ps1` 时按系统 ANSI 代码页（简体中文机器上是 GBK/936）解码，而本文件里有大量中文注释与中文字符串——UTF-8 的字节按 GBK 解出来是乱码。⚠️ **而这个失效是静默的**：乱码只落在字符串字面量里，脚本照跑、只是 `Write-Host` 打出一堆问号。PowerShell 7+ 缺省按 UTF-8 读、不需要 BOM，但本仓的开发机是 5.1。⚠️ 与 commit 信息（要求 UTF-8 **无** BOM）相反：两个消费者的解码规则不同——git 把 BOM 当成消息正文的头三个字节，PowerShell 把它当成编码声明。**真机取证**：`-DryRun` 那一次的全部中文（含「禁区复核：… ✓」与那句 11 条预警的中文说明）逐字正确打印。
⚠️ 脚本里**一个反引号都没有**：需要同时出现 `$Base` 插值与 JSON 的双引号那几行，一律用**单引号串 + 拼接**（单引号串不插值、也不需要转义 `"`）。

### ⚠️ 顶回简报一处：不用 `run_backfill`

简报 Task 9「决定」第 3 条要 demo.ps1 走「③ `build_dataset` + **`run_backfill`**（灌一学期的体测数据）」，而派单第 7 节逐字要求「`demo.ps1` 里也不要有它们（`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`）」。**采派单**：一次 `run_daily` 就把九个阶段全走完（Extract → Clean → Percentile → Derive → Stratify → Prescribe → Alert → Report → Commit），60 人实测约 3 秒；而 `run_backfill` 的语义是「把一学期的每个业务日都跑一遍」（16 周 × 5 个业务日），分钟级，且演示不需要它。
⚠️ **代价（硬规矩 #39，已写进 bootstrap 的模块 docstring）**：演示库里 `stratification_result` / `derived_metrics` 只有**一天**的行，故「周环比流动」（`app.domain.report.layer_flow`）恒为 `has_previous = False`（上一周一次批处理都没跑），教师大屏的流动那一块是空的。要它非空就得回放至少两个周日——那是 `run_backfill` 的活，留给需要它的人手工跑。

### ⚠️ 业务日期取 `2025-10-12`（学期第 6 周的**周日**）：两个下界都是实测撞出来的

* **必须是周日**：`report_stage.is_report_day` 只在 `weekday() == 6` 为真；取周一的话 `weekly_class_report` 一行都没有、`GET /api/dashboard/weekly-class-report/{id}` 永远 404，演示少一整块。
* **不能太早**（第一次试 `2025-09-14` = 第 2 周的周日，实测**一条预警都不触发**、`alert = 0`，脚本自己的复核当场 `exit 1`）：`demo_data._class_sessions_and_rpe` 对 `session_date < semester.start_date` 的周**跳过**，于是 4 个教学周只剩 2 个 → 每个学生 2 条快评 → `RED_RPE_SUSTAINED`（要连续 3 次）永不成立；而 `_mini_tests` 取「最近的偶数周」，第 2 周只有 1 个偶数周 → `RED_MINITEST_DROP`（要 3 个数据点）也永不成立。第 6 周同时满足两条：4 个教学周（10-12 / 10-05 / 09-28 / 09-21）全在学期区间内、偶数周有 6 / 4 / 2 三个。两个下界的推导逐字写在 `DEMO_AS_OF` 的注释里。

### 一次真机跑的取证

**(a) `-DryRun` 那一次**（`exit=0`，`backend/` 下不留文件）：

```
== 体育闭环原型系统 · 演示 ==
   backend = C:\\Users\\whwenhao\\Desktop\\Physical_Education_ims\\backend
   DEMO_DB_URL = sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe_demo.db
   -DryRun：库与 CSV 都落在 C:\\Users\\whwenhao\\AppData\\Local\\Temp\\pe_demo_dryrun_22688（跑完删掉，backend/ 下不留文件）
[1/5] write_csv(build_dataset(60 人 / 16 周 / seed=20250828)) -> …\\pe_demo_dryrun_22688\\lepao
[3/5] build_demo_feedback(as_of=2025-10-12)  batch_id=1 class_session=8 rpe_record=240 training_log=840 mini_test=180
[4/5] run_daily(2025-10-12)  status=success 抽取 242/242/121 剔除 112 修正 17
       分层 红/黄/绿/数据不足 = 7/29/24/0  肌肉量缺线组 4   处方 60 张  预警 11 条
   禁区复核：backend\\pe.db 不存在、backend\\data\\seed\\ 仍为 0 文件 ✓
   -DryRun 收尾：…\\pe_demo_dryrun_22688 已删掉
```

**(b) 真起服务那一次**（`-Port 8010`）：删旧库 → 灌数据（同上，`weekly_class_report = 5`、`weekly_adjustment = 11`、预警按规则 `{'RED_MINITEST_DROP': 5, 'RED_RPE_SUSTAINED': 6}`）→ 禁区复核 ✓ → uvicorn：

```
INFO:     Started server process [65380]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8010 (Press CTRL+C to quit)
```

**(c) `/api/health` 的响应原文**（探针 `p12_live_server_evidence.py`，`urllib` 直打真 TCP）：

```
GET /api/health -> HTTP 200
{"status":"ok","tables":25,"students":60}
```

**(d) 在真机上把闭环点了一遍**（每一步都是真 HTTP、真磁盘 SQLite 文件）：

| 往返 | 结果 |
|---|---|
| `GET /openapi.json` | 路径模板 **63**（`/api/` 下 63）、操作 **91**、挂 `security` 的 **18**；`/api/pipeline/run-daily` 在列 |
| `GET /api/alerts?limit=50` | `total=11`；`id=1` 是 `RED_RPE_SUSTAINED` / `red` / `student_id=1` / `pending` / `window_key='rpe3'` |
| `GET /api/students/1/weekly-sheet?as_of=2025-10-12`（处置**前**） | `week=1 factor=0.8 reasons=['RED_RPE_SUSTAINED'] sources=['auto'] paused=False` |
| 同一个 URL 换 `X-Student-Id: 2` | **HTTP 403** `{"error":{"code":"forbidden","message":"学生 2 无权访问学生 1 的数据","detail":null}}` |
| `POST /api/alerts/1/handle?as_of=2025-10-12` `{"action":"reduce_20pct"}` + `X-Teacher-Staff-No: T0001` | `alert.status=handled`、`handled_action='reduce_20pct'`、**`adjustment=None`**（管道已自动减过 → 撞唯一约束、没有第二次减量）、`notification id=1 title='本周训练量已减 20%' → student:1` |
| `GET weekly-sheet`（处置**后**） | `factor` 仍是 **0.8 而不是 0.64** |
| `GET /api/notifications?limit=50` | `total=1`、`is_read=False`、`alert_id=1`、`prescription_id=1` |
| `POST /api/notifications/1/read` | `is_read=true`（响应体逐字回给，含 `body`：「老师看过你的预警（RED_RPE_SUSTAINED）之后，把本周的训练量减了 20%。…」） |
| `GET /api/dashboard/weekly-class-report/1?week=6&as_of=2025-10-12` | HTTP 200；12 个键；**`progress_board` 非空**（`top`: student 10 `+235.88%` / 36 `+88.72%` / 35 `+79.41%` / 41 `+73.44%` / 30 `+62.14%` …）；`suggestion="维持当前强度"` |
| `POST /api/pipeline/run-daily` `{"business_date":"2025-10-12"}` + 教师头 | HTTP 200；`status=success`、`daily_sync_run_id=1`（**幂等键命中同一行**）、`prescription_count=60`、`alert_count=11`、`csv_dir=C:/Users/…/Temp/pe_demo_csv_65252` |

**(e) 跑完 `pe.db` 仍不存在**：`backend/pe.db 存在 = False`、`backend/data/seed/ 文件 = []`（脚本自己复核一遍、探针再独立复核一遍，两个独立工具，硬规矩 #109）。`backend/pe_demo.db` 存在（gitignore 内，`.gitignore:38` 实测）。

### ⚠️ 真机上撞到的一条**演示口径的已知不一致**（已写进脚本输出 + 登记为关切）

`run_daily` 注入给 `alert_stage` / `report_stage` 的 `now` 是**真实时钟**（`daily.py` 里那个局部变量），而 `as_of` 是 `2025-10-12`。于是 `alert.triggered_at` 落在「今天」，而 `class_snapshot` 夹 alert 的窗口是 `[报表周周一, 水位线 + 1 天)` = `2025-10-06 .. 2025-10-13`——两者不相交，故演示库的 `weekly_class_report.alert_summary` **恒为 9 个 0**（真机实测确认），教师大屏的「本周预警汇总」那一块是空的。
⚠️ **生产上 `as_of == 今天`，故这一档不可达**；它只在**重放一个历史业务日**时出现，而演示恰恰必须重放（数据集是 `seed=20250828` 的固定一学期，学期区间 `2025-09-01..2025-12-22`，今天的日期落在它之外）。修法是让 `run_daily` 的 `now` 也可注入（与 `as_of` 同源），那是一次签名变更、会连带 Task 7/8 两条「同一个 `now`」的断言，不在本 Task 范围。**已写进 `demo_bootstrap.py` 的一处注释与一行输出**（免得演示的人以为大屏坏了），并移交 Plan 04。

---
""")

def main() -> int:
    text = "".join(BLOCKS)
    raw = text.replace("\n", "\r\n").encode("utf-8")
    TARGET.write_bytes(raw)
    after = TARGET.read_bytes()
    crlf = after.count(b"\r\n")
    bare = after.count(b"\n") - crlf
    lines = crlf + bare + (0 if after.endswith(CRLF_BYTES) else 1)
    print(f"写出 {TARGET}")
    print(f"  bytes={len(after)} lines={lines} CRLF={crlf} bare LF={bare}")
    print(f"  sha256[:16]={hashlib.sha256(after).hexdigest()[:16].upper()}")
    assert after.startswith("# Plan 03 Task 9 实现者报告".encode("utf-8"))
    assert not after.startswith(b"\xef\xbb\xbf"), "报告不要 BOM"
    return 0


if __name__ == "__main__":
    sys.exit(main())
