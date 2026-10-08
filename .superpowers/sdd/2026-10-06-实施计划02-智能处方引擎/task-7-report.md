# Task 7 报告 — 处方生成阶段接入管道（`prescription_stage.py`）

> 实现者报告。代码基线 `d498bac`，分支 `feature/plan-02-prescription-engine`，**未 push**。
> 本 Task 共 **6 个 commit**、改动 **10 个文件**（新建 2 + 改 8），全量 **716 → 749 passed**。
> 所有数字都是本轮亲跑；探针脚本在 `%TEMP%/t7_probes/`（不入库），逐条命令写在下面。

---

## 0. 摘要（控制者只看这一段也够）

| 项 | 基线 | 本 Task 之后 |
|---|---|---|
| `python -m pytest -q` | 716 passed | **749 passed**（+33） |
| `--cov=app.domain --cov-branch` | 715 passed / 1 skipped | **748 passed / 1 skipped** |
| domain 覆盖率四格 | 948 / Miss 0 / 274 / BrPart 0 / 100% | **951 / Miss 0 / 274 / BrPart 0 / 100%** |
| 表数 | 18 | **18**（本 Task 不建表） |
| 架构守卫扫描面 | 33（pipeline 7 + db 11 + domain 15） | **34**（pipeline **8** + db 11 + domain 15） |
| `PIPELINE_TABLES` | 9 | **11** |
| `app.domain.prescription.__all__` | 47 | **47**（本 Task 不新增 domain 处方侧名字） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 47 | **47**（未动） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（刻意未动，Ruling 97） |
| `PersonInputs` 字段数 | 12 | **15** |
| `input_snapshot` 顶层键数 | 26 | **28** |
| 整学期回放（500 人 ×112 业务日） | 28.4–34.0 s | **28.85 s**（缺省注入）/ **28.81 s**（零注入） |
| 三个禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **逐字不变** |

**6 个 commit**：

| sha | 一句话 |
|---|---|
| `c5599db` | `lookup_p10` + `PersonInputs` 三字段 + `input_snapshot` 两键 + `resolve_muscle_lines` 同时回填 P10/P20 |
| `a5fd7db` | `prescription_stage.py` + `daily.py` 插 Prescribe 阶段 + `_replay_cleanup` 扩到五张表（子表先删） |
| `c7f2edb` | `PIPELINE_TABLES` 9 → 11 + canonical sha256 重测（P7-A5/A6/A7） |
| `08db233` | 补两条 Z0 守卫，把变异 ① 从「1 条红」补齐到计划预期的「3 条红」 |
| `ca265ab` | 散文连带：「六个阶段」→ 七个（硬规矩 #66） |
| `fd6a427` | 更正自己刚写下的一处假数字（把「趋势的 insufficient 34 人」误当成「分层标签的」） |

**四条 Critical（P7-A1..A4）全部照办**，逐条落地位置见第 3–5 节。
**顶回控制者 3 处**（第 8.3 节），**没按派单字面做的 5 处**（第 8.4 节），**待清扫 6 条**（第 8.1 节）。

---

## 1. 环境与基线复现

### 1.1 硬规矩 #73 的第一步

```
python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__); ..."
  sqlalchemy 2.1.3
  pandas     3.0.6
  numpy      2.4.6
  yaml       6.0.3
```

**没有 `ImportError: DLL load failed`**，Smart App Control 没有拦 `.pyd`，故按计划继续，
没有动系统安全设置、没有升降级任何依赖。Python **3.11.1**、**无 venv**（解释器在 `C:/Python`）。

### 1.2 git 基线

```
git rev-parse --abbrev-ref HEAD   -> feature/plan-02-prescription-engine
git log --oneline -1              -> d498bac docs: Plan02 Task 7 预检 …（Ruling 151）
git status --short                -> 只有 .superpowers/ 下两个未跟踪的简报文件
```

工作树的 `backend/` 干净。全程**没有切分支、没有 push、没有碰 main**。

### 1.3 测试与覆盖率基线

```
cd backend; python -m pytest -q          -> 716 passed in 64.23s        与简报逐字一致
```

覆盖率基线（948 / 0 / 274 / 0）**开工时没有单独复跑**：`--cov` 那一次要 2.5 分钟，
而 commit ① 之后必须立刻复跑它（`lookup_p10` 动了 domain 的分母）。故实测的第一次
覆盖率是 commit ① 之后的：

```
percentile.py 单文件：94 stmts -> 97 stmts（+3：def 行 / row = / return）
                      26 branch -> 26 branch（**不变**）
                      Miss 0 / BrPart 0 / 100%
全 domain：           948 -> 951 stmts，274 branch 不变，Miss 0 / BrPart 0 / 100%
```

**branch 26 不变**是可解释的、不是漏测：`lookup_p10` 与 `lookup_p20` 同形，都是
「一行赋值 + 一个**条件表达式**」，而 coverage 的 branch 分析只统计**语句级分支**
（`if` / `while` / 推导式的隐含跳转），`a if c else b` 不产生分支弧。故 +3 stmts / +0 branch
正是「逐字照 `lookup_p20` 抄」的**可验证后果**——若 branch 也涨了，说明抄的时候多写了一个 `if`。

### 1.4 其它基线（一律运行时口径，硬规矩 #89）

```
len(Base.metadata.tables)                                  -> 18
sum(len(list(Path('app',d).rglob('*.py'))) for d in …)      -> 33 = {pipeline 7, db 11, domain 15}
len(app.domain.prescription.__all__)                       -> 47
len(dataclasses.fields(PersonInputs))                      -> 12
len(input_snapshot_of(…))                                  -> 26
```

四个数与简报的预检逐格一致（含 P7-A10 更正后的 **26**，不是控制者错误 #147 那个 24）。
**本 Task 全程没有用正则数过任何键/字段/成员。**

---

## 2. Plan 01 既有测试的回归结论（本 Task 的硬门槛）

改了 **4 个 Plan 01 已结案的生产文件**（`percentile.py` / `run_stratify.py` /
`percentile_stage.py` / `daily.py`）+ **1 个已结案的测试文件**（`test_daily.py`），
故这一节是本 Task 最重要的一节。

### 2.1 结论：**Plan 01 的全部既有测试仍然全绿，一条断言都没有被放宽**

```
cd backend; python -m pytest -q -p no:cacheprovider
  -> 749 passed in 79.00s                （基线 716；+33 条全是本 Task 新写的）
cd backend; python -m pytest -q --cov=app.domain --cov-branch
  -> 748 passed, 1 skipped in 155.45s    （skip 的是 test_backfill 的墙钟那条，它检测到
                                          coverage 的 trace 钩子后按 Ruling 172 自跳）
```

**716 条既有测试里 0 条变红、0 条被删、0 条断言被改弱。** 唯一的既有断言改动是
`test_daily.py` 的 `PIPELINE_TABLES` 从 9 项扩到 11 项（P7-A5，那是**加强**不是放宽），
以及 `canonical_dump` docstring 里的「9 张表」→「11 张表」。

### 2.2 逐文件

| 文件 | 结果 | 说明 |
|---|---|---|
| `tests/pipeline/test_daily.py` | **20 passed** | 一条没少。改了 `PIPELINE_TABLES`（9→11）与 3 处 docstring |
| `tests/pipeline/test_percentile_stage.py` | 全绿 | `cohort_from_db` 的构造点补了三个字段，行为不变 |
| `tests/pipeline/test_backfill.py` | 全绿 | **本 Task 唯一一次真的撞线**，见 2.4 |
| `tests/integration/test_golden_cases.py` | 全绿 | 13 例逐字不变（P7-A2 的处置生效） |
| `tests/domain/*` | 全绿 | `test_percentile.py` +3 条新测试；其余一个字没改 |
| `tests/db/test_models.py` | 全绿 | 18 张表、`_MODELS_PUBLIC_BASELINE` 33、`json_text_columns` 14 全部未动 |
| `tests/architecture/*` | 全绿 | domain allow-list 未被触碰；扫描面 33 → 34 自动扩大 |
| `tests/test_refdata_prescription.py` | 全绿 | `_PRESCRIPTION_PUBLIC_BASELINE` 47 未动 |
| `tests/seed/*` | 全绿 | seed 阶段 `prescription` / `weekly_adjustment` 仍是 0 行 |

### 2.3 P7-A7：两处 `assert first == second` 的分别结论

`git grep -n "assert first == second"` 实测命中 **5** 处，其中
`tests/pipeline/test_daily.py` 里正是简报说的**两处**（另三处在
`test_prescription_assembler.py` / `test_prescription_triggers.py`，与本 Task 无关）：

**① `tests/pipeline/test_daily.py:131` — `test_rerun_same_business_date_is_idempotent`**

```python
run_daily(session, sem, D, ad); first = _counts(session)
run_daily(session, sem, D, ad); second = _counts(session)
assert first == second
```

**结论：绿。** 它比的是 `_counts()` 那个**七元组**（`DerivedMetrics` /
`StratificationResult` / `CleaningLog` / `FitnessTestResult` / `BodyComposition` /
`InterestSurvey` / `PercentileSnapshot` 的行数），处方**不在其中**，故加键与扩表都不影响它。
**代价如实记录**（硬规矩 #39）：这一条**不覆盖处方的幂等**——它从来没有覆盖过，
只是本 Task 之后「七元组」与「管道写的 11 张表」之间的缺口变大了。处方侧的同形状守卫是
本 Task 新写的两条：`test_rerun_same_day_does_not_duplicate_prescriptions`（行数）与
`test_same_day_regeneration_is_idempotent`（`training_package` 逐字段）。

**② `tests/pipeline/test_daily.py:606` — `test_rerunning_the_same_business_date_reproduces_every_table`**

```python
assert rows_first == rows_second, (rows_first, rows_second)
assert sum(rows_first.values()) > 0
assert first == second, "同一业务日期重跑后全表 canonical sha256 不同"
```

**结论：绿，而且它现在比的是 11 张表。** 两次运行的 sha256 逐字相同：

```
05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816   （两遍都是它）
行数合计 942 == 942
```

**这就坐实了 P7-A6**：那条断言比的是「两次运行相等」，不是与一个字面哈希相等，
故 P7-A1/A3 加两个键 + P7-A5 扩两张表**都不会让它红**。字面哈希
`fe0a44e052c7946b…` 在 `backend/` 下**0 命中**（本轮复核仍然 0 命中），
它只活在账本、spec §1.3 与计划正文里 —— 过期的是散文，不是测试。

### 2.4 唯一一次撞线：`test_backfill_500_students_under_60_seconds`（已修，本 Task 最大的发现）

接入处方阶段之后，那一条**当场红了**：

```
FAILED tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds
  - AssertionError: 115.08476930006873   assert 115.08476930006873 < 60
```

而 Plan 01 的基线是 **28.4–34.0 s**（余量 1.8–2.1×）。逐段定位（cProfile + 分段计时，
探针 `%TEMP%/t7_probes/probe3.py`、`probe4.py`、`probe5.py`）：

| 观察 | 数 |
|---|---|
| 一个**轻日**（不生成处方）的 `generate_prescriptions` | 0.110 s / 全天 0.492 s（cProfile 口径） |
| 一个**重日**（498 张处方）的 `generate_prescriptions` | 0.801 s（cProfile 口径） |
| 整学期回放里真正生成处方的天数 | **5** 天（09-01 / 09-29 / 10-20 / 11-17 / 12-15，恰好 28 天间隔） |

5 个重日 ×0.8 s + 107 个轻日 ×0.11 s ≈ 16 s（cProfile 口径，真实约一半）——**这解释不了
+80 s**。真因是两处 **全表扫描 + 大 JSON 列的 eager 加载**，它们随学期推进**线性变坏**：

1. **主查询按 `computed_on` 单列过滤**。`stratification_result` 上只有
   `(student_id, computed_on)` 一条唯一索引，**以 `student_id` 打头**，故按
   `computed_on` 单列过滤**用不上它** → 全表扫描。那张表到学期末有 **56 000** 行
   （500 × 112），每行还带一个约 **2 KB** 的 `input_snapshot`。112 天 × 平均 28 000 行
   ≈ **310 万行**的表扫描。
   → **改成同时按 `batch_id` 过滤**（那一列 `index=True`），`computed_on` 保留以守住契约。
2. **上一张处方的预取整行加载 ORM 对象**。`Prescription` 有 **5** 个 `JsonText` 列，
   其中 `training_package` 是 4 周 ×4 课 ×3 block 的嵌套字典（约 500 个键值对）。
   逐人逐日把它 `json.loads` 出来一遍 = 500 × 112 ≈ **56 000** 次大 JSON 解析，
   而本阶段**一个字节都不读它**。
   → **`load_only(...)` 把 4 个大列延迟加载**（只留 `student_id` / `generated_on` /
   `template_ref` / `microcycle_weeks` / `status` / `teacher_overrides`）；
   同时把「取上一张处方」与「取它生成当天的标签」**合并成一条连接查询**
   （标签那一侧原来按 `computed_on IN (days)` 过滤，同样是全表扫描）。

两处一起修完：

```
整学期回放（500 人 ×112 业务日）
  修之前  52.89 s（一次亲跑量到 115 s，即上面那条红）
  修之后  28.85 s（缺省注入） / 28.81 s（零注入）
  Plan 01 基线 28.4–34.0 s   →  余量 60 / 28.85 = 2.08×
```

**即处方阶段对整学期回放的净增成本已经落进 Plan 01 基线的噪声带里**（2490 / 2500 张
处方两个量级都是）。

**但仍要报为关切**（第 8.2 节关切 2）：余量 **2.08×** 只是刚过硬规矩 #42 的 2× 线，
而本轮**同一个夹具量到过 52.89 s 与 115 s**（组内极差 2.2×）。那意味着这条断言在本机
仍然是 flaky 的（与 Ruling 172/178 当年记的形状同源）。本 Task **没有**去改那个 60 s
（它是 Plan 01 已结案的断言，改它需要控制者裁定），只是把自己的成本压回基线。

### 2.5 黄金用例（P7-A2 的验收）

`golden_cases.json` **一个字节都没改**
（`git diff d498bac HEAD -- backend/tests/fixtures/golden_cases.json` 输出为空）。
13 例的 `label` / `W` / `C` / `valid_count` / `hit_rules` / `explain` 全文逐字不变。

黄金用例路径的三个新字段一律 `case.get(...)`，故 13 例的快照里 `"bmi"` 与
`"snapshot_muscle_p10"` 是 **`None`**（P7-A2 的预期结果），**直到 Task 9 给 13 例补上
顶层身高体重**。守卫：`test_golden_case_path_defaults_the_three_new_inputs_to_none`
用一份**手工构造、刻意缺这三键**的用例钉住「缺键不炸、退化成 `None`」，
故 Task 9 补上之后它**仍然绿**（它断言的是行为，不是夹具的形状）。

---

## 3. `PersonInputs` 的 3 个新字段 + 3 个构造点（P7-A1 / P7-A2）

### 3.1 字段

`PersonInputs` **12 → 15**（`len(dataclasses.fields(PersonInputs))` 运行时口径）。
三个新字段**追加在第 13–15 位**：

```python
    snapshot_muscle_p20: float | None
    # --- 以下三个是 Plan 02 Task 7 加的，derive 一个都不读（见 docstring）---
    height_cm: float | None
    weight_kg: float | None
    snapshot_muscle_p10: float | None
```

**为什么追加在末尾**：前 12 个字段与 `derive` 的 11 个参数一一对应（Plan 01 的既有契约，
`evaluate` 按关键字展开正是为了它）。插在中间会让那句 docstring 变成谎话；追加在末尾
则「前 12 个仍是 `derive` 的参数序」逐字成立，且有断言钉住
（`names[:12] == _PINNED_PERSON_FIELDS[:12]`）。

**三个字段一律没有缺省值**（`field.default is dataclasses.MISSING`），与既有的
`snapshot_muscle_p20` 同口径。给缺省的后果是「漏改一个构造点」静默退化成 `None`
——那一整条路径的 `"bmi"` / `"snapshot_muscle_p10"` 会恒为 `None`、spec §7.4 的安全触发
**永不成立**，而全链路不报错。守卫：
`test_person_inputs_gains_exactly_the_three_prescription_fields` 断言三者都在
「无缺省」那个集合里。
这与 P7-A2 的「缺省 `None`」**不冲突**：那说的是 `case.get("height_cm")` 的缺省，
不是 dataclass 字段的缺省。

### 3.2 三个构造点逐点（P7-A1 实测的 3 处，本轮复核仍然恰好 3 处）

**① `app/pipeline/percentile_stage.py::cohort_from_db`（DB 路径 —— P7-A1 点名的
「能拿到 `fitness_test_result` 的行，身高体重是现成的」那一处）**

```python
height_cm=None if curr_row is None else curr_row.height_cm,
weight_kg=None if curr_row is None else curr_row.weight_kg,
snapshot_muscle_p10=None,
```

`curr_row` 来自 `_results_of(...)`，**已经被 `tested_on <= as_of` 截断过**
（Plan 02 Task 1 的 M1），故身高体重不可能来自未来的测量。
`snapshot_muscle_p10` 与既有的 `snapshot_muscle_p20` 一样是**占位 `None`**：
快照此刻还不存在，两者由 `resolve_muscle_lines` 在物化/读回之后**一次回填两档**。

**② `app/pipeline/run_stratify.py::_from_golden_cases`（黄金用例路径 —— P7-A2）**

```python
snapshot_muscle_p20=case["snapshot_muscle_p20"],   # 既有那行，硬下标，**保持不动**
height_cm=case.get("height_cm"),
weight_kg=case.get("weight_kg"),
snapshot_muscle_p10=case.get("snapshot_muscle_p10"),
```

新增的三个**一律 `.get()`**。注意夹具里 `curr` / `prev` 子映射**是**有
`height_cm` / `weight_kg` 的（那是算 BMI **得分**用的原始测量），但**顶层没有** ——
`.get()` 取的是顶层，故 13 例的 `"bmi"` 是 `None`。这是 P7-A2 逐字预期的结果。

**③ `app/pipeline/run_stratify.py::_from_dataset`（内存路径）**

```python
height_cm=None if curr is None else curr.height_cm,
weight_kg=None if curr is None else curr.weight_kg,
snapshot_muscle_p10=None,   # 占位：同上，由 resolve_muscle_lines 回填
```

`curr` 是**清洗后**的 `RawFitnessRecord`（评估锚点那一批 = 最新的 `week1`），
与 `score_raw(record_dict(curr), ...)` 合成 BMI **得分**用的是**同一行**。
故快照里 `"bmi"`（原始值）与 `curr_scores["bmi"]`（得分）不可能来自两次不同的测量 ——
这一点是「单一所有者」在这两个键上的具体形状。

### 3.3 `input_snapshot_of` 26 → 28 键

```python
"bmi": bmi_of(person.height_cm, person.weight_kg),     # 原始值，spec §7.4 的「BMI > 30」
"snapshot_muscle_p10": person.snapshot_muscle_p10,     # spec §7.4 的「肌肉量 < P10」
```

* `bmi_of` 的所有者是 `app/domain/indicators.py`，`run_stratify` 只是**重导出**它
  （P7-A9：它的 docstring 在 Task 1 就预写了 Plan 02 的这个用途，逐字有
  「Plan 02 的 `StudentProfile.bmi` 因此必须由 domain 自己算得出来」）。
  **`profile_of` 因此不必自己算 BMI**，只从快照读 —— 计划的那条决定照办。
* 28 个键**逐字钉死**在测试侧的 `_PINNED_SNAPSHOT_KEYS`（排序后比），
  且断言用 `len(got) == 28` 运行时口径（硬规矩 #89）。
* **`"bmi"` 与 `curr_scores["bmi"]` 并存不冲突**：前者是 kg/m² 的原始值，后者是国标**得分**。
  测试里专门有一句 `assert got["curr_scores"]["bmi"] is None`（那个人的 BMI 得分是缺测的），
  同时 `got["bmi"] == 21.8`（`172.5 cm / 65.0 kg`，字面写死）—— 两格互不掩盖。
* 缺测时 `"bmi"` 是 `None`，**绝不当 0**（Ruling 21）：一个 `bmi = 0` 的快照会让
  「0 > 30」为假，学生**静默**躲过 BMI 那一档复核。守卫
  `test_input_snapshot_bmi_is_none_when_height_or_weight_is_missing`（三档：缺身高 /
  缺体重 / 两个都缺）。

### 3.4 `resolve_muscle_lines` 一次回填两档

```python
return [
    replace(
        person,
        snapshot_muscle_p20=lookup_p20(snapshot, person.sex, person.age_group),
        snapshot_muscle_p10=lookup_p10(snapshot, person.sex, person.age_group),
    )
    for person in persons
]
```

**「同时」是承重的**：只回填 P20 的话，`snapshot_muscle_p10` 在 DB 路径上恒为 `None`、
spec §7.4 的肌肉量安全触发**永不成立**，而全链路不报错（`apply_safety` 对 `None` 的处置
是「不触发 + 在 `safety_skipped` 里留痕」，看起来完全合法）。
守卫 `test_resolve_muscle_lines_backfills_p20_and_p10_together` 三段：
① 两档都回填且**值不同**（P10 = 25.5 / P20 = 30.0，抄串列会给出同一个数）；
② 查不到时两档**一起**保持 `None`；③ 入参那份一个字没动（`replace` 产出新对象）。

---

## 4. `lookup_p10` 与 `lookup_p20` 的逐字对照（P7-A3）

### 4.1 实现

`app/domain/percentile.py`，紧跟在 `lookup_p20` 之后：

```python
def lookup_p10(
    snapshot: list[PercentileRow],
    sex: Sex,
    age_group: str,
) -> float | None:
    # docstring 见文件（约 30 行，结构照 lookup_p20）
    row = _lookup_row(snapshot, SnapshotMetric(MUSCLE_MASS), sex, age_group)
    return None if row is None else row.p10
```

### 4.2 逐字对照

**完全相同的 6 处**：

| 项 | 两者 |
|---|---|
| 签名 | `(snapshot, sex, age_group)`，返回 `float` 或 `None`，**都没有 `item` 形参**（指标固定为 `MUSCLE_MASS`；「一个只有一个合法取值的参数是撒谎」） |
| 查行 | 同一个 `_lookup_row(snapshot, SnapshotMetric(MUSCLE_MASS), sex, age_group)` |
| 返回式 | `return None if row is None else row.pXX`（同一个条件表达式形状） |
| `None` 语义 | 该组肌肉量样本 < `MIN_SAMPLE` 时 `compute_snapshot` 不产出行（Ruling 121 第 4 步），故 `None`；与 `lookup_p25` 同构；**缺测不当最坏值**（Ruling 21） |
| 量纲提醒 | 肌肉量行的分位是 **kg 读数**而不是 0–100 的得分，与 `muscle_mass_kg` 同量纲、可直接比较 |
| import 面 | **一个新 import 都没有**（domain 的 allow-list 未被触碰；`percentile.py` 的 import 块一个字没改） |

**必须不同的 2 处**：

| 项 | `lookup_p20` | `lookup_p10` |
|---|---|---|
| 取的列 | `row.p20` | `row.p10` |
| 消费者 | `derive.flag_body_comp` 的 `snapshot_muscle_p20`（spec §6.3②，→ **分层标签**） | `safety.SafetyInput.muscle_p10`（spec §7.4，→ **`needs_review`**） |

docstring 的结构也照抄（口径 → 消费者 → `None` 的语义 → 量纲），只是「消费者」那一段
换成 P10 的，并**在 domain 侧就写明那条红线**（下一个读 `percentile.py` 的人不必先去读
Task 7 的简报才知道「P10 不进分层」）。

### 4.3 覆盖率（Global Constraint #2）

```
app\domain\percentile.py    97 stmts / Miss 0 / 26 branch / BrPart 0 / 100%
                              （基线 94 / 0 / 26 / 0 / 100%）
```

**新函数 100% 覆盖，两档 `None` 各有测试**（简报 P7-A3 点名的要求）：

| 档 | 测试 | 构造 |
|---|---|---|
| 有值 | `test_lookup_p10_reads_the_p10_column_of_the_muscle_row` | 30 个等距样本 `30.0 … 35.8` → P10 = **30.58**（字面写死；`np.percentile(method="linear")` 的下标 `0.10 × 29 = 2.9`，`x[2] + 0.9 × (x[3] − x[2]) = 30.4 + 0.18`，独立手算；`approx(abs=1e-9)` 只兜二进制浮点的末位，实测原值是 `30.580000000000002`） |
| **组不存在** | `test_lookup_p10_returns_none_when_the_group_is_absent` | 快照里只有 **female** 那一行；查 male 得 `None`、查 female + 另一个年级组也得 `None`、查 female + 本组**不为** `None`（三档一起，防空转） |
| **样本不足** | `test_lookup_p10_returns_none_when_the_muscle_sample_is_below_min` | `MIN_SAMPLE - 1 = 29` 个样本 → `compute_snapshot` 返回 `[]` → `None` |

同一条测试里还钉住：`lookup_p10(...) < lookup_p20(...)`（若实现抄成了 `row.p20`，
这一句与字面值那一句一起红），以及「传裸字符串 `"male"` 与传 `Sex.MALE` 命中同一行」。

### 4.4 红线：「P10 不进分层判定」的守卫

**守卫的名字**（派单第 9 条要的那个）：

```
tests/pipeline/test_prescription_stage.py
  :: test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict
```

它钉四件事：

1. **三档 P10 下分层结论逐字相同**：`snapshot_muscle_p10` 取 `24.0 / 50.0 / 999.0`
   （刻意跨过本人的肌肉量 `50.0 kg`：低于 / 恰等 / 远高于），
   `run_stratify.result_dict` 的 10 个键（`label` / `hit_rules` / `W` / `C` /
   `valid_count` / `dominant_bucket` / `trend` / `percentile_source` / `explain` /
   `student_id`）**三遍逐字相等**。
2. **反空转**：`baseline["label"] != "insufficient_data"`（全员 Z0 的话三档恒等是假的）。
3. **快照里唯一变的那一格就是它自己**：
   `[key for key in snap_a if snap_a[key] != snap_b[key]] == ["snapshot_muscle_p10"]`
   —— 可追溯性没有连带失真。
4. **反面对照（防假绿）**：把 `snapshot_muscle_p20` 抬到 `60.0`（> 本人的 `50.0 kg`）
   **必须**让 `C` 翻真、`explain` 里出现「肌肉量低于同龄同性别 P20」、且整个结论
   不等于 `baseline`。没有这一段，一次「把所有分位输入都拔掉」的改动能让上面三档全部
   恒等而骗过本条 —— **假绿比假红更危险**（硬规矩 #83 的原话）。

**静态那一半由 Plan 01 既有的守卫承担**，本 Task 没有重写它：
`tests/domain/test_derive.py::test_smi_is_not_an_input_at_all` 逐字钉住

```python
assert params == ["body_fat_pct", "muscle_mass_kg", "sex", "snapshot_muscle_p20"]
```

即 `flag_body_comp` 的签名里**只有 P20 一个分位形参**。谁把 P10 接进去，
那一条与本条一起红。`evaluate` 也不传它（它按关键字展开 `derive` 的 11 个参数，
而 `derive` 没有那个形参）。

**实现时踩到的一个坑，记在这里免得下一个人再踩**（它是一次**假绿**）：
最初的写法是「对每个 P10 取值构造一个 `PersonInputs`、再过一遍 `resolve_muscle_lines`」——
而回填会**按快照把 P10 覆盖回 25.5**，三档取值塌成同一个数，断言恒等、测试全绿、
什么都守不住。第一遍跑的时候它就是这样绿的（同一条测试的另一段先红了才把这件事暴露出来）。
改成「先回填一次拿到 `resolved`，再用 `dataclasses.replace` **只**换 P10」，
并把这条注释写进测试。

---

## 5. `prescription_stage.py` 的公开面 + Task 6 传导的四件事

### 5.1 公开面（`__all__` 共 **10** 个，运行时口径 `len(prescription_stage.__all__)`）

| 名字 | 形状 |
|---|---|
| `generate_prescriptions` | `(session, semester_id: int, batch_id: int, as_of: dt.date, *, templates, exercises, equivalence) -> PrescriptionReport`（**签名照简报 Interfaces / Produces 逐字**） |
| `PrescriptionReport` | `@dataclass(frozen=True)`：`generated: int` / `skipped: int` / `needs_review: int` / `skipped_reasons: dict[str, int]` |
| `profile_of` | `(session, student_id: int, as_of: dt.date) -> StudentProfile`（**pipeline 层，可以读 DB**） |
| `valid_to_of` | `(generated_on: dt.date, microcycle_weeks: int) -> dt.date` |
| `active_or_needs_review` | `(needs_review: bool) -> str` |
| `training_package_payload` | `(pkg: TrainingPackage) -> dict` |
| `INSUFFICIENT_DATA` | `= Layer.INSUFFICIENT.value`（**读枚举、不写第二份字面串**，Global Constraint #3） |
| `NO_TRIGGER` | `"no_trigger"` |
| `ASSEMBLY_ERROR` | `"assembly_error"`（见 8.3 顶回 3） |
| `REPLACED` | `"replaced"` |

私有 6 个：`_previous_prescriptions` / `_last_prescription_of` / `_latest_assessment` /
`_require_batch_in_semester` / `_profile_of` / `_endurance_score`（+ `_ENDURANCE_ITEMS` /
`logger`）。

**`skipped_reasons` 是稀疏字典**（只出现计数 > 0 的键）。这是刻意的：若六个 `MatchStatus`
一律以 0 入字典，`assert "no_bucket" not in report.skipped_reasons`（Ruling 11 的唯一守卫）
就会**恒假**，而它要钉的正是「生产路径上 `NO_BUCKET ⊆ NO_LAYER`、故这一格永远为 0」。

**单一所有者逐条对账**（Global Constraint #3）：

| 常量/词表 | 所有者 | 本模块怎么拿 |
|---|---|---|
| `Layer` | `app/domain/stratify.py` | `from app.domain.stratify import Layer`，`INSUFFICIENT_DATA = Layer.INSUFFICIENT.value` |
| `bmi_of` | `app/domain/indicators.py` | **不在本模块用**：`run_stratify.input_snapshot_of` 用它算好，本模块只从快照读 `"bmi"` |
| `lookup_p10` / `lookup_p20` | `app/domain/percentile.py` | **不在本模块用**：`resolve_muscle_lines` 回填好，本模块只从快照读 `"snapshot_muscle_p10"` |
| `ADDON_TRIGGERS` | `app/domain/prescription/templates.py` | 不碰（`apply_safety` 内部消费） |
| `EQUIVALENCE_TRIGGERS` / `volume_reduction` | `exercises.py` / `exercise_equivalence.yaml` | 不碰（`apply_safety` 内部消费）；测试里注入空映射表时字面写了那两个键名（测试侧字面量，两侧不同源） |
| 「耐力桶是哪两项」 | `app/domain/indicators.py` 的 `ITEM_BUCKET` | `_ENDURANCE_ITEMS = tuple(item for item in ScoredItem if ITEM_BUCKET[item] == WeaknessBucket.ENDURANCE.value)` —— **派生、不手抄**；桶名那一份取自 `WeaknessBucket`，`"endurance"` 的字面串不在本模块出现第二次 |
| 「一周 7 天」 | `app/domain/prescription/triggers.py` 的 `_DAYS_PER_WEEK` | `valid_to_of` 用 `dt.timedelta(weeks=…)`，**不写 `* 7`** |

### 5.2 Task 6 传导的四件事逐条落地位置

**① `prescription.microcycle_weeks` ← `Template.microcycle_weeks`（P6-A3）——是**

* 落地位置：`generate_prescriptions` 的 upsert 值字典里那一行（行内注释点名 P6-A3）。
* 两个消费者都读它：
  * `valid_to_of(as_of, template.microcycle_weeks)`（生成当时）；
  * `LastPrescription.microcycle_weeks=row.microcycle_weeks`（**从处方行取，不读今天的模板**
    ——模板会改版，而触发 3 要判的是「**上一张**处方的周期到了没有」）。
* 守卫：`test_prescriptions_are_generated_for_every_stratified_student` 断言
  `{row.microcycle_weeks} == {4}` 且 `{row.valid_to} == {2025-10-12}`；
  `test_valid_to_is_generated_on_plus_microcycle_minus_one_day` 另用 `microcycle_weeks=2`
  钉住「不硬编码 4」；变异 ④ 打的就是它（4 条红）。
* 「漏填会让 `valid_to` 无从复算」这一条：`valid_to` **不是**从 `microcycle_weeks` 反推的
  （它由 `valid_to_of` 在生成当时算好落库），故漏填 `microcycle_weeks` 不会让**已落库**的
  `valid_to` 错，但会让**离线复算**（spec §4.3：「一张 2026-03 生成的处方必须能在 2027 年
  复算出它当时的 `valid_to`」）与**触发 3**（它读的是上一张的 `microcycle_weeks`）双双失效。
  两条都由上面那三个断言看着。

**② `prescription.previous_had_overrides` ← 上一张的 `teacher_overrides` 是否非空（P6-A2）——是**

* 落地位置：同一份 upsert 值字典：
  `bool(previous is not None and previous.teacher_overrides)`。
* **`assembly_snapshot` 一个键都没加**：落库前是 `dict(safety.package.assembly_snapshot)`，
  仍是 **15** 个键（Task 5 钉死的 12 + 3）。两条键集守卫（`test_assembly_snapshot_keys_are_exactly_the_pinned_set`
  与 5.3 那条「至多 +3 键」）一个字没动、也没变红。
* 守卫：`test_regeneration_does_not_inherit_teacher_overrides`（Step 0 移过来的第 1 条）
  同时断言 `new.previous_had_overrides is True`、`new.teacher_overrides == []`、
  `new.training_package == 覆盖之前那一份`、`len(new.assembly_snapshot) == 15`、
  且快照里**没有任何含 `"override"` 的键**。
* 首次生成没有「上一张」→ `False`（不是 `NULL`）；60 人端到端那条断言
  `{row.previous_had_overrides} == {False}` 钉住它。

**③ `weekly_adjustment.batch_id` 的口径（P6-A8）——是（以「口径 + 删除路径」的形式落地）**

* 口径写在**两处、同一句话**（传导要求「在表注释里写明」）：
  * `app/pipeline/prescription_stage.py` 模块 docstring 的第 5 节；
  * `app/db/models/prescription.py` 里 `WeeklyAdjustment.batch_id` 那一列的注释。
  两处都是：管道生成的调整行带**本批**的 `batch_id`；**教师手工加的调整行没有批次**，
  取**该行所属处方当前的 `batch_id`**（处方尚未落库时取本次运行的批次）。
* ⚠️ **本阶段不写这张表**（`source="teacher"` 归 Plan 03 教师端、`"auto"` 归 Plan 03 预警侧），
  故落地形态是**口径 + 删除路径**：`daily._replay_cleanup` 按 `batch_id` 删它，
  且**排在 `Prescription` 前面**（P7-A4）。这一点在模块 docstring 里如实写明（硬规矩 #39）。
* **代价也写明**（两处同一句）：教师手工加的调整行因此继承处方的 `batch_id`，
  而 `_replay_cleanup` 按 `batch_id` 整批删 —— 于是**重放那一天会连带删掉教师当天的手工微调**。
  这与「重放同一天的处方会丢掉 `teacher_overrides`」是同一条代价的两个面。
  本仓不做迁移、也没有「人工数据豁免于重放」的机制，故**没有擅自加一个**；登记为关切 3。
* 守卫：`test_replay_cleanup_covers_prescription_and_weekly_adjustment` +
  反证 `test_deleting_prescription_before_weekly_adjustment_really_violates_the_fk`。

**④ `skipped_reasons` 有 `"insufficient_data"` 这个键 —— 是**

* 落地位置：`INSUFFICIENT_DATA = Layer.INSUFFICIENT.value`（模块级常量）+
  循环里**排在 `match_template` 之前**的那一段早退（`_skip(INSUFFICIENT_DATA)`）。
* ⚠️ **必须排在匹配之前**：`match_template` 对 `Layer.INSUFFICIENT` 返回 `NO_LAYER`，
  于是「Z0」与「矩阵里缺这一格」会塌成同一个键。两者给教师的处置完全不同
  （「补齐体测数据就有处方」 vs 「18 套模板缺这一格，找专家」）。
  守卫 `test_the_z0_gate_is_checked_before_the_matcher_is_consulted`
  monkeypatch `match_template` 记录被咨询过的层，断言它**只**看见 `"red"`。
* 留痕三处：① `skipped_reasons["insufficient_data"]` 的计数；② 逐人一条 `debug` 日志；
  ③ **每批一条 `warning`**（点名人数、点名 Z0 闸门、指出逐人清单查
  `stratification_result.label`）。
* 守卫三条（变异 ① 打的正是它们，**3 条全红**）：
  `test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped`、
  `test_the_z0_gate_is_checked_before_the_matcher_is_consulted`、
  `test_no_bucket_and_no_layer_never_appear_even_with_a_z0_student`。
* ⚠️ **计划点名的「500 人里那 2 人」本轮亲跑复现了**（探针 `probe3.py` / `probe7.py`，
  整学期 112 业务日回放）：

  ```
  配置                 每天 Z0 人数   每天处方张数   全季处方总数   insufficient_data 的分层行合计
  -------------------  -----------  -------------  ------------  ---------------------------
  500 人 / 缺省注入         2            498           2490              224 = 2 × 112
  500 人 / 零注入           0            500           2500                0
  ```

  **498 / 500 与计划 Step 1 的两个数逐字对上。** 触发原因的分布（缺省注入）：
  `microcycle_expired` 996、`first_stratification` 498、
  `(microcycle_expired, semester_data_refreshed)` 360、`semester_data_refreshed` 351、
  `(layer_changed, semester_data_refreshed)` 147、
  `(layer_changed, microcycle_expired, semester_data_refreshed)` 138；
  处方生成日恰好 **5** 天（09-01 / 09-29 / 10-20 / 11-17 / 12-15，28 天间隔），
  期末 `status` 分布 `{replaced: 2000, active: 500}`（零注入）——每人恰好一张 `active`。
  ⚠️ **这四个数不进测试网**（跑一次 500 人的整条管道约 29 s，加两条会让套件翻倍，
  而 `test_backfill.py` 已经有一条 500 人的墙钟测试）；它们是**历史实测、不被守卫**，
  复现命令是 `probe3.py` / `probe7.py`。测试网里守这一档的是 `bare` 夹具那三条。

### 5.3 异常分层与 `status` 映射（简报「决定」第 2、5 条）

**异常分层**写进了模块 docstring 的一整节（「异常分层：按学生捕获，只有基础设施异常才冒泡」），
分界线就是那段 `try` 的位置：

* `try` **里**只有两个纯函数：`assemble(...)` 与 `apply_safety(...)`。它们能抛的只有
  「这一个学生的输入有问题」（年龄荒谬 → `hrmax` 的 `ValueError`；`structure` 键集不认识；
  `exercise_ref` 不在动作库里；`week_deltas` 与 `microcycle_weeks` 不符）。
  处置：`needs_review += 1`、`skipped_reasons["assembly_error"] += 1`、一条 `warning`
  日志（点名学号 / 模板 id / 异常类型与消息）、`continue`。**不写处方行**（见 8.3 顶回 3）。
* `try` **外**是全部 DB 读写：`_previous_prescriptions` / `_require_batch_in_semester` /
  `repo.upsert` / `session.flush`。故 `IntegrityError` / `OperationalError` 照样冒泡到
  `run_daily` 的 SAVEPOINT，由它回滚整批并写 `status="failed"` 的运行记录。
* 守卫：`test_per_student_assembly_failure_does_not_roll_back_the_batch`
  （monkeypatch `prescription_stage.assemble` 让它只对 `student_id` 最小的那个人抛
  `ValueError`）。它断言**五件事**：`run.status == "success"`；
  `StratificationResult` / `PercentileSnapshot` / `DerivedMetrics` **都还在**
  （60 / >0 / 60 行 —— 这是「没回滚」的直接证据，只看处方行数会被「整批回滚 → 处方也是 0 行」
  骗过）；其余 **59** 人照常拿到处方、那一个人没有；报表里
  `needs_review == 1` 且 `skipped_reasons == {"assembly_error": 1}`；
  有一条 `warning` 点名学号与 `ValueError`。变异 ③ 打的就是它。

**`status` 映射**由 `active_or_needs_review(needs_review)` 单点持有：
`"needs_review" if needs_review else "active"`，**`needs_review` 优先于 `active`**。
做成一个有名字的函数而不是在落库那一行写三元表达式，是为了让「优先级」这件事可以被单独钉住。
两条守卫：
* 单元：`test_needs_review_wins_over_active_in_the_status_mapping`
  （`active_or_needs_review(True) == "needs_review"`、`(False) == "active"`、
  `True` 那一档 `!= "active"`、且两个返回值都在 `Prescription.STATUSES` 里 ——
  最后这一句钉住「映射产出的字符串真的落得进那一列」，不是一个 CHECK 会拒收的第四态）。
* 端到端：`test_needs_review_when_no_equivalent_exercise`（Review Focus 第 5 条）——
  装配**成功**了、安全触发也命中了、等价表里**找不到替身**，于是
  `row.status == "needs_review"` 且 `!= "active"`；`safety_substitutions == []`；
  那个高冲击 block **原样保留**（`interval_run` 在 4 周 ×4 课里出现 **16** 次，一次都没被删）；
  `assembly_snapshot["safety_triggers"]` 含 `"bmi_over_30"`；
  **且写了一条 `warning` 日志点名那个动作**（spec §7.4「不静默跳过」）。
  构造方式：注入一份 `mappings=()` 的空等价表（真表 v1.0 有 **10** 条映射，
  故这一档在生产数据上不可达）。
  **带反证**：`test_a_matching_equivalence_table_yields_an_active_prescription`
  用同一份输入配上**真**等价表 → `active`、`16` 条替换记录、`interval_run` 一个不剩、
  每条记录都带 `equivalence_version == "1.0"`。没有这一条，上一档会被一个
  「凡是安全触发就一律 needs_review」的实现骗过。

### 5.4 幂等与重放（P7-A4）

`daily._replay_cleanup` 的清单 **3 → 5 张**，顺序承重：

```python
for model in (
    models.DerivedMetrics,
    models.StratificationResult,
    models.PercentileSnapshot,
    # 顺序承重：子表先删（weekly_adjustment.prescription_id -> prescription.id，
    # 而 PRAGMA foreign_keys=ON 真的在强制它）。倒过来当场 FK 违例，见 docstring。
    WeeklyAdjustment,
    Prescription,
):
    repo.delete_by_batch(session, model, batch_id)
```

* **import 走 `from app.db.models.prescription import Prescription, WeeklyAdjustment`**
  （`daily.py` 与 `prescription_stage.py` 两处都是），**不是** `models.Prescription`。
  写错会当场 `AttributeError`，而那两条守卫
  （`test_plan02_tables_stay_out_of_the_models_public_namespace` 与
  `test_models_public_namespace_is_unchanged_by_the_split`）也就同时失去意义。
  两处 import 上方都有 4 行注释说明这件事。
* **正证**：`test_replay_cleanup_covers_prescription_and_weekly_adjustment` ——
  构造一批带调整行的处方 → 跑 `daily._replay_cleanup` → 断言两张表都空、
  Plan 01 那三张也照旧被清、**且没抛 FK 错**。
* **反证**：`test_deleting_prescription_before_weekly_adjustment_really_violates_the_fk` ——
  同一份夹具，直接 `repo.delete_by_batch(session, Prescription, batch)`（即倒过来的顺序）
  → `pytest.raises(IntegrityError)`，且消息里含 `"FOREIGN KEY constraint failed"`。
  没有这一条，正证会被一个「反正两张表都空了」的实现骗过（例如先手工
  `DELETE FROM weekly_adjustment` 再删处方：顺序对但绕过了清单），
  或者被一个「关掉外键强制」的改动骗过。**这一条把「顺序承重」这句话变成了可执行的证据。**
* 幂等：`UniqueConstraint("student_id", "generated_on")` + `repo.upsert`。
  守卫 `test_rerun_same_day_does_not_duplicate_prescriptions`（60 → 60，且
  `(student_id, generated_on)` 两两不同）与 `test_same_day_regeneration_is_idempotent`
  （Step 0 第 2 条：`training_package` 逐字段相同，失败消息能指出是哪一个学生）。

### 5.5 `profile_of` 的输入来源（简报点名「本 Task 最容易错的地方」）

`_profile_of(student, snapshot, as_of)` 是**唯一的映射所有者**（纯函数、不查库），
`profile_of(session, student_id, as_of)` 是它的「带两次查询」外壳。逐格对照简报：

| 字段 | 简报要求的来源 | 实现 |
|---|---|---|
| `sex` / `birth` | `Student` | `Sex(student.sex)` / `student.birth` |
| `age` | `prescription/intensity.age_from`，`as_of` 传业务日期 | `age_from(student.birth, as_of)` |
| `endurance_score` | `input_snapshot["curr_scores"]` 里的 `vital_capacity` 与 `distance_run` | `_endurance_score(snapshot["curr_scores"])`，两项从 `ITEM_BUCKET` **派生**；均值口径照 `assembler.py` 的模块 docstring（两项都有 → 均值；只有一项 → **取那一项、不取半值**；都无 → `None`） |
| `body_fat_pct` / `muscle_mass_kg` | `input_snapshot` 的顶层同名键 | 逐字照读 |
| `bmi`（**原始值**） | `input_snapshot` **没有它** → 本 Task 补键 | `snapshot["bmi"]`（Task 7 新加的那一格，由 `bmi_of` 在 `input_snapshot_of` 里算） |
| `muscle_p10` | `percentile_snapshot` 的 `p10` 列 → 随 `snapshot_muscle_p10` 落进快照 | `snapshot["snapshot_muscle_p10"]`（`resolve_muscle_lines` 经 `lookup_p10` 回填） |
| `measured_hrmax` | — | 恒 `None`（Plan 01/02 没有任何心率数据） |

**一个键都不回查 `fitness_test_result` 重算。** 守卫是
`test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result`：
跑完管道后把那个人**所有**体测行的 `height_cm` / `weight_kg` / `total_score` /
七项 `score_*` 全改成别的值，然后断言 `profile_of(...)` 的结果 `== before`
（`StudentProfile` 是 frozen dataclass，`==` 逐字段）。
变异「让 `profile_of` 去查 `fitness_test_result` 重算」→ 本条当场红。

⚠️ **批处理循环不调 `profile_of`**（这一点在它的 docstring 里如实写明，硬规矩 #39）：
`generate_prescriptions` 已经把 `Student` 与 `StratificationResult` 两行握在手里，
逐人再查两次是 500 人 ×2 次纯浪费。`profile_of` 的调用方是**单个学生**的入口
（Plan 03 教师端的「给这一个学生重新生成」）与本模块的测试。**映射只有一个所有者**
（`_profile_of`），故两者不可能给出不同的 `StudentProfile`。

### 5.6 本 Task 新写的测试清单（30 条，`tests/pipeline/test_prescription_stage.py`）

A 节（P7-A1/A2/A3，6 条）：`test_person_inputs_gains_exactly_the_three_prescription_fields`、
`test_input_snapshot_gains_the_raw_bmi_and_the_p10_line`、
`test_input_snapshot_bmi_is_none_when_height_or_weight_is_missing`、
`test_resolve_muscle_lines_backfills_p20_and_p10_together`、
`test_snapshot_muscle_p10_does_not_enter_the_stratification_verdict`、
`test_golden_case_path_defaults_the_three_new_inputs_to_none`

B 节（24 条）：`test_valid_to_is_generated_on_plus_microcycle_minus_one_day`、
`test_needs_review_wins_over_active_in_the_status_mapping`、
`test_training_package_payload_survives_a_json_round_trip`、
`test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped`、
`test_the_z0_gate_is_checked_before_the_matcher_is_consulted`、
`test_no_bucket_and_no_layer_never_appear_even_with_a_z0_student`、
`test_no_student_is_skipped_for_a_missing_bucket`、
`test_prescriptions_are_generated_for_every_stratified_student`、
`test_report_counts_add_up_to_every_stratified_student`、
`test_daily_sync_run_prescription_count_matches_the_report`、
`test_no_trigger_means_no_new_prescription`、
`test_rerun_same_day_does_not_duplicate_prescriptions`、
`test_replay_cleanup_covers_prescription_and_weekly_adjustment`、
`test_deleting_prescription_before_weekly_adjustment_really_violates_the_fk`、
`test_a_layer_change_regenerates_and_replaces`、
`test_regeneration_does_not_inherit_teacher_overrides`（**Step 0 第 1 条**）、
`test_same_day_regeneration_is_idempotent`（**Step 0 第 2 条**）、
`test_needs_review_when_no_equivalent_exercise`、
`test_a_matching_equivalence_table_yields_an_active_prescription`、
`test_per_student_assembly_failure_does_not_roll_back_the_batch`、
`test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result`、
`test_a_prescription_whose_stratification_row_is_gone_fails_loudly`、
`test_profile_of_fails_loudly_without_a_stratification_row`、
`test_a_batch_from_another_semester_is_rejected_loudly`

加 `tests/domain/test_percentile.py` 的 3 条（第 4.3 节），合计 **+33 条**。

计划 Step 1 的 12 条**全部有对应实现**（名字逐字沿用了计划给的 11 个，
只有 `test_rerun_same_day_does_not_duplicate_prescriptions` 与 Step 0 的两条按计划原文命名）。

---

## 6. canonical sha256 的新实测值与「行数合计」（控制者要回填账本与 spec §1.3）

**夹具**：`tests/pipeline/test_daily.py` 的 `CFG`（**60 人** / `seed=20250828` / **缺省注入**）
+ `D = "2025-09-15"` + `SEMESTER_NAME = "2025-2026-1"`，
`canonical_dump` 函数**逐字复用测试里那一份**（含 `NON_DETERMINISTIC_COLUMNS` 剔除
`daily_sync_run.started_at` / `finished_at` 两列），`sort_keys=True` +
`separators=(",", ":")` + `ensure_ascii=False` + `default=str`。
探针 `%TEMP%/t7_probes/probe6.py`，n=1，本轮亲跑。

| 表集合 | sha256 | 行数合计 |
|---|---|---|
| **9 张（Plan 01 的清单）** | `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952` | **882** |
| **11 张（Task 7 之后的清单）** | `05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816` | **942** |

**两个哈希都在同一业务日期的两次运行之间逐字相同**（`first == second` 成立，各跑两遍）。

11 张的逐表行数：

```
fitness_test_batch      4       percentile_snapshot     24      cleaning_log         133
fitness_test_result   240       derived_metrics         60      prescription          60
body_composition      240       stratification_result   60      weekly_adjustment      0
interest_survey       120       daily_sync_run           1
                                                              合计                 942
```

### 6.1 三个必须交代清楚的点

1. **942 = 882 + 60 + 0**：多出来的 60 行是处方（60 人首日全部触发 1），
   `weekly_adjustment` 是 0 行（本阶段不写它，见 5.2 ③）。
2. **「行数合计 882」这个数被本轮独立复现了**：把 `PIPELINE_TABLES` 临时换回 Plan 01
   那 9 张跑一遍，行数合计**恰好是 882**。故账本与 spec §1.3 里那个 882 与本夹具是同一个
   （60 人 / `seed=20250828` / 缺省注入 / `D = 2025-09-15`），回填时请**连测量条件一起写**
   （硬规矩 #20：尺寸/计数必须带 n 与条件）。
3. ⚠️ **9 张那一行的哈希也变了**（`fe0a44e052c7946b…` → `1f043f2a72153720…`），
   而**不是**因为扩表 —— 是因为 `run_stratify.input_snapshot_of` 加了 `"bmi"` 与
   `"snapshot_muscle_p10"` 两个键（P7-A1 / P7-A3），而 `stratification_result` 在那 9 张里。
   即：**两个哈希都要更新，但成因不同**（一个因加键、一个因加键 + 扩表）。
   这正是 Ruling 229 记过的形状（「一个修复改变了另一个修复的取证基线」），
   故两处都要注明是 `c5599db`（加键）与 `c7f2edb`（扩表）改的。

### 6.2 这四个值都不被守卫

`test_rerunning_the_same_business_date_reproduces_every_table` **刻意不断言字面哈希**
（钉死它就变成另一条同源断言，硬规矩 #35）。上面两个哈希与两个行数合计已经写进那条测试的
docstring（commit `c7f2edb`），标注为「一次取证记录，不被守卫」。

---

## 7. 变异取证（4 条 + M0 + M1，硬规矩 #83）

**纪律**：驱动脚本 `%TEMP%/t7_probes/mutate.py`，每一次变异前后都
① `shutil.rmtree(__pycache__, ignore_errors=True)`（递归扫 `backend/`）、
② `PYTHONDONTWRITEBYTECODE=1`（`os.environ`，传给子进程）、
③ pytest 加 `-p no:cacheprovider`。
锚点用「在文件里恰好命中 1 次」校验（`text.count(old) != 1` 就拒绝变异），
还原用**变异前读出的原始 bytes 写回**（不是 `git checkout`，避开 `core.autocrlf` 重写工作树
——硬规矩 #46），sha256 取前 16 位十六进制、大写。

被变异的两个文件的**变异前** sha256[:16]：
`app/pipeline/prescription_stage.py` = **`DB37A0915AF4878D`**、
`app/pipeline/daily.py` = **`30D0B023FDC551AE`**。

### M0（不变异，全绿对照）

```
python mutate.py <backend> M0
  === M0：不变异，全绿对照 ===
  [pycache removed: 16 dirs] exit=0 :: 50 passed in 22.43s
```

选择集是 `tests/pipeline/test_prescription_stage.py`（30 条）+ `tests/pipeline/test_daily.py`
（20 条）= **50 passed**。

### M1（语义等价改写，仍须全绿）

改写 `_latest_assessment` 的函数体：

```python
# 原
present = [day for day in dates if day is not None]
return max(present) if present else None
# 改成
return max((day for day in dates if day is not None), default=None)
```

两者逐格等价（`max(..., default=None)` 对空可迭代对象返回 `None`，与「先物化成 list 再判空」
在结果与副作用上都相同；`dates` 是 `*args` 的 tuple，只遍历一次）。

```
sha256[:16] 变异前 = DB37A0915AF4878D
sha256[:16] 变异后 = 546A721210798F94  (changed=True)
  [pycache removed: 0 dirs] exit=0 :: 30 passed in 8.11s        ← 仍全绿（正确）
sha256[:16] 还原后 = DB37A0915AF4878D
三重还原逐字相同: True
  [pycache removed: 0 dirs] exit=0 :: 30 passed in 7.99s
```

### 变异 ①：把 `insufficient_data` 的早退删掉

**改了哪一行**：`app/pipeline/prescription_stage.py`，`generate_prescriptions` 循环里的
`if label == INSUFFICIENT_DATA:` → `if False and label == INSUFFICIENT_DATA:`
（整个早退块变成死代码，与删掉它逐格等价）。

```
sha256[:16] 变异前 = DB37A0915AF4878D
sha256[:16] 变异后 = 7F7E17B5AA8524A6  (changed=True)
  exit=1 :: 3 failed, 27 passed in 8.32s
sha256[:16] 还原后 = DB37A0915AF4878D      三重还原逐字相同: True
  还原后复跑 exit=0 :: 30 passed in 7.99s
```

**哪 3 条测试的哪个断言分支变红**（与计划预期的「3 条」逐字对上）：

| 测试 | 变红的那一句 `assert` |
|---|---|
| `test_insufficient_data_students_get_no_prescription_and_are_counted_in_skipped` | `assert report.skipped_reasons == {"insufficient_data": 1}` → `AssertionError: assert {'no_layer': 1} == {'insufficient_data': 1}` |
| `test_the_z0_gate_is_checked_before_the_matcher_is_consulted` | `assert consulted == ["red"]` → `AssertionError: 匹配器看到了 insufficient_data：Z0 的早退没有排在匹配之前，实际被咨询的层是 ['red', 'insufficient_data']` |
| `test_no_bucket_and_no_layer_never_appear_even_with_a_z0_student` | `assert report.skipped_reasons == {"insufficient_data": 1}` → `AssertionError: assert {'no_layer': 1} == {'insufficient_data': 1}` |

⚠️ **本条变异第一轮只红 1 条**（只有上表第 1 条）。查下来是**守卫面真的有洞**、不是变异打歪：
① Ruling 11 那条守卫（`test_no_student_is_skipped_for_a_missing_bucket`）跑的是 60 人种子
夹具，而它在 `D = 2025-09-15` 上**一个 Z0 学生都没有**（实测 `{yellow 29, green 24, red 7}`），
故它压根守不到「Z0 早退把 `NO_LAYER` 一起吃掉」这一格；② 没有任何一条钉住
「Z0 是在**匹配之前**被分出来的」。补了两条（commit `08db233`，上表第 2、3 条），
复跑得到 **3 failed** —— 与计划逐字一致。

### 变异 ②：把 `_replay_cleanup` 的清单里 `prescription` 删掉

**改了哪一行**：`app/pipeline/daily.py`，那个 `for model in (...)` 元组里删掉
`Prescription,` 一行（`WeeklyAdjustment,` 保留）。

```
sha256[:16] 变异前 = 30D0B023FDC551AE
sha256[:16] 变异后 = B9F37EFE7F04D7D6  (changed=True)
  exit=1 :: 1 failed, 29 passed in 8.21s
sha256[:16] 还原后 = 30D0B023FDC551AE      三重还原逐字相同: True
  还原后复跑 exit=0 :: 30 passed in 8.14s
```

**变红的那一条与那一句**：

| 测试 | 变红的那一句 `assert` |
|---|---|
| `test_replay_cleanup_covers_prescription_and_weekly_adjustment` | `assert _count(session, Prescription) == 0` → `AssertionError: assert 1 == 0` |

⚠️ **这里要更正计划的一句预期**（计划写的是「重放翻倍测试红」）：
`test_rerun_same_day_does_not_duplicate_prescriptions`（那条「重放翻倍」测试）**保持绿色**。
机制是实测的：`prescription` 上有 `UniqueConstraint("student_id", "generated_on")`，
而落库走 `repo.upsert` —— 不删旧行时第二次运行会**命中同一行并 PATCH 它**，
行数与内容都不变（`batch_id` 也相同，因为同一业务日期 → 同一行 `daily_sync_run`）。
故对 `prescription` 而言，「重放翻倍」这个失效形态**在结构上不可达**；
真正会翻倍的是 `weekly_adjustment`（**没有任何唯一约束**，多一批 `factor=0.8`
就把那一周的量再打八折，且全程不报错）。
**结论：清单里那两项的守卫必须直接钉清单本身**（`_count(...) == 0`），
不能指望「翻倍」这个下游症状——这正是本 Task 把正证与反证都写成的原因。

### 变异 ③：把「按学生捕获异常」改成不捕获

**改了哪一行**：`app/pipeline/prescription_stage.py`，
`except Exception as exc:  # noqa: BLE001` → `except ZeroDivisionError as exc:  # noqa: BLE001`
（一个永不匹配的异常类 = 不捕获；`try` 块的形状与缩进一个字没动，故这是一次外科级改动）。

```
sha256[:16] 变异前 = DB37A0915AF4878D
sha256[:16] 变异后 = ECC1C12055D9B6E3  (changed=True)
  exit=1 :: 1 failed, 29 passed in 8.28s
sha256[:16] 还原后 = DB37A0915AF4878D      三重还原逐字相同: True
  还原后复跑 exit=0 :: 30 passed in 8.08s
```

**变红的那一条与那一句**：

| 测试 | 变红的分支 |
|---|---|
| `test_per_student_assembly_failure_does_not_roll_back_the_batch` | 不是某一句 `assert` 失败，而是 `run_daily(...)` 那一行**直接把异常抛出来**：`ValueError: 装配炸了（测试注入）` —— 即异常逃出了按学生的 `try`、冒泡到 `run_daily`、被 SAVEPOINT 回滚整批后原样重抛。**这正是本条要抓的失效形态**（一个学生的装配失败掀掉一整天的批处理），而失败方式（异常穿透而不是断言不等）本身就证明了「捕获」是唯一挡住它的东西。 |

### 变异 ④：把 `valid_to` 的 `-1 day` 删掉

**改了哪一行**：`app/pipeline/prescription_stage.py`，`valid_to_of` 的返回式
`return generated_on + dt.timedelta(weeks=microcycle_weeks) - dt.timedelta(days=1)`
→ `return generated_on + dt.timedelta(weeks=microcycle_weeks)`。

```
sha256[:16] 变异前 = DB37A0915AF4878D
sha256[:16] 变异后 = BD1AA49944EB4B3C  (changed=True)
  exit=1 :: 4 failed, 26 passed in 8.40s
sha256[:16] 还原后 = DB37A0915AF4878D      三重还原逐字相同: True
  还原后复跑 exit=0 :: 30 passed in 8.08s
```

**哪 4 条测试的哪个断言分支变红**：

| 测试 | 变红的那一句 `assert` |
|---|---|
| `test_valid_to_is_generated_on_plus_microcycle_minus_one_day` | `assert valid_to_of(dt.date(2026, 3, 2), 4) == dt.date(2026, 3, 29)` → `AssertionError: assert datetime.date(2026, 3, 30) == datetime.date(2026, 3, 29)` |
| `test_prescriptions_are_generated_for_every_stratified_student` | `assert {row.valid_to for row in rows} == {VALID_TO_FROM_D}` → `assert {datetime.date(2025, 10, 13)} == {datetime.date(2025, 10, 12)}` |
| `test_a_layer_change_regenerates_and_replaces` | `assert rows[AS_OF].valid_to == VALID_TO_FROM_D` → `assert datetime.date(2025, 10, 13) == datetime.date(2025, 10, 12)` |
| `test_regeneration_does_not_inherit_teacher_overrides` | `assert rows[AS_OF].valid_to == VALID_TO_FROM_D` → `assert datetime.date(2025, 10, 13) == datetime.date(2025, 10, 12)` |

**即「差一天」这件事在 4 个独立的观测面上都被钉住**：纯函数口径（字面日期）、
60 人端到端、手工构造的换处方、以及 Step 0 那条重生成。第 1 条还额外钉住
`(valid_to - generated_on).days == 27`（闭区间：`generated_on` 自己算第 1 天），
与 `Prescription.valid_to` 列注释里「`2026-03-02` → `2026-03-29`，那正是第 28 天」逐字对得上。

### 7.1 变异取证小结

| 编号 | 对象文件 | sha256[:16] 前 → 中 → 后 | 结果 | 三重还原 |
|---|---|---|---|---|
| M0 | — | — | 50 passed | — |
| M1 | `prescription_stage.py` | `DB37A0915AF4878D` → `546A721210798F94` → `DB37A0915AF4878D` | 30 passed（语义等价，**应绿**） | 逐字相同 |
| ① | `prescription_stage.py` | `DB37A0915AF4878D` → `7F7E17B5AA8524A6` → `DB37A0915AF4878D` | **3 failed** / 27 passed | 逐字相同 |
| ② | `daily.py` | `30D0B023FDC551AE` → `B9F37EFE7F04D7D6` → `30D0B023FDC551AE` | **1 failed** / 29 passed | 逐字相同 |
| ③ | `prescription_stage.py` | `DB37A0915AF4878D` → `ECC1C12055D9B6E3` → `DB37A0915AF4878D` | **1 failed** / 29 passed | 逐字相同 |
| ④ | `prescription_stage.py` | `DB37A0915AF4878D` → `BD1AA49944EB4B3C` → `DB37A0915AF4878D` | **4 failed** / 26 passed | 逐字相同 |

⚠️ 变异 ①③④M1 四次都打在同一个文件上，**变异前的 sha256 四次都是 `DB37A0915AF4878D`**
——这本身就是一次交叉校验：若哪一次还原失败，后一次的「变异前」就会是另一个值。
每次还原后都**复跑了一遍**确认绿（不是只看 sha256）。

⚠️ 一个纪律细节：`[pycache removed: 0 dirs]` 说明**变异期间没有任何 `.pyc` 被写出来**
（`PYTHONDONTWRITEBYTECODE=1` 生效），故 Task 5 那次「等长改动 + 同一秒内四步 → 加载陈旧
字节码 → 假红」的形状在本轮**结构上不可达**（M0 那次显示 16 个 `__pycache__` 目录被清掉，
是开工前遗留的）。

---

## 8. 待清扫 / 关切 / 顶回 / 没按派单做的地方 / 最终验收

### 8.1 待清扫清单（纯散文精度，按 Ruling 145 攒到 Task 9；**没有 Critical**）

1. `app/db/session.py` **3 处**「15 张表」（模块 docstring 第 4 行、`Base` 的 docstring、
   `init_db` 里的行内注释）—— 实际 **18** 张。**Task 6 建表时就已过期**，不是本 Task 造成的。
2. `app/db/repo.py:20`「对 14 个模型通用」—— 实际 18 张表。同为 Task 6 遗留。
   ⚠️ 同一个文件的 `delete_by_batch` docstring 里「全库只有**五**张表有这一列（Ruling 31）」
   与「**今天** `_replay_cleanup` 只清 Plan 01 那三张派生表；Task 7 会把两张处方表接进那份
   清单」—— 后半句**已被本 Task 落地**，故那句「今天」现在过期了（清单是五张）。
   这一条建议 Task 9 顺手改，它是**本 Task 造成的**过期。
3. `tests/pipeline/test_daily.py` 里两处「六个阶段」（`test_run_daily_populates_all_stages`
   的分组说明、跨学期那条的 docstring）——**刻意没改**：那两句描述的是**那两条测试实际
   断言了什么**（`_counts` 的七元组不含处方），改成「七个」反而会让它们声称自己没有做的事。
   若要改，正确做法是给 `test_run_daily_populates_all_stages` 补一句处方计数断言，
   而那与本文件的职责划分（见它新加的模块 docstring 那一段）冲突。留给控制者裁定。
4. `app/domain/percentile.py` 模块 docstring 里的「Task 10」（旧编号）与
   `app/pipeline/run_stratify.py` 里的「Task 9 / Task 10 / Task 8」字样 ——
   计划的「Task 重编号对照表」明写「已结案的 Task 1–4 正文里的交叉引用未逐条重写……
   按上表折算」，故这些是**已知且被裁定过的**，不建议单独开一轮。
5. `app/pipeline/run_stratify.py` 模块 docstring 的「`payload` 的两种形状」那一段
   仍只提 `snapshot_muscle_p20` **手工给定**，没提本 Task 新加的三个 `.get()` 字段。
   函数级 docstring（`_from_golden_cases`）里已经写全了，故这是模块级摘要的滞后。
6. 本 Task 新写的 `prescription_stage.py` 里，`profile_of` 的 docstring 引用
   `tests/pipeline/test_backfill.py` 的 `elapsed < 60` 作为「逐人查两次的代价」的守卫 ——
   而批级预取优化之后，循环里已经**没有**逐人查询了，那一句现在只适用于 `profile_of`
   自己（单个学生的入口）。措辞不算错（它说的就是 `profile_of`），但可以更明确。

### 8.2 关切（按优先级）

**关切 1（最高）：`prescription` 表没有 `label_at_generation` 列，触发 2 的比较对象只能回读 `stratification_result`。**

* 事实：`LastPrescription.label_at_generation` 是触发 2 的**唯一**比较对象。
  `prescription` 表**没有** `label` 列（Task 6 建表时就没加，实测 14 列），
  `assembly_snapshot` 那 **15** 个键里也**没有**它（Task 5 用两条键集守卫钉死了那份契约，
  而 P6-A2 已经为 `previous_had_overrides` 明确否掉过「往快照加键」这个方案）。
* 实现：`_previous_prescriptions` 用 `outerjoin` 从**同一天**的 `stratification_result`
  取标签；取不到就 `raise ValueError`（守卫
  `test_a_prescription_whose_stratification_row_is_gone_fails_loudly`）。
* 为什么这是关切而不是「已经解决了」：两张表由同一批次在同一 SAVEPOINT 里写，故正常情况下
  那一行必然在。但它**不受任何约束保护**——人工清理、或撞上 Plan 01 Ruling 212 那个
  跨学期重放的形状，都会让它消失，届时**整批**回滚（这是刻意的：静默拿今天的标签去比
  会让触发 2 变成一个每天都可能开火、或永远不开火的假判据）。
* **彻底修它要给 `prescription` 加一列**，那是改一张 Task 6 已结案的表
  （硬规矩 #11；本仓不做迁移 = 重建库）。**不擅自做，交回控制者裁定。**
* 代价（若维持现状）：多一条 `outerjoin`（已实测：与 `batch_id` 索引过滤一起，
  整学期回放 28.85 s，落进基线噪声带）。

**关切 2：`test_backfill_500_students_under_60_seconds` 的余量只剩 2.08×，且本机极差 2.2×。**

* 事实：本 Task 接入处方阶段后那一条**红过一次**（`elapsed = 115.08`）。定位到两处
  全表扫描 + 大 JSON 列 eager 加载，修完回到 **28.85 s**（缺省注入）/ **28.81 s**（零注入），
  余量 `60 / 28.85 = 2.08×`。
* 但**同一个夹具本轮量到过 52.89 s 与 115 s**（前者是修之前、后者是修之前的另一次跑），
  即本机的墙钟极差本来就大。Ruling 172 当年就为此给这条断言加过
  「检测到 trace 钩子就 skip」的豁免；不带 `--cov` 时它仍然被断言。
* **本 Task 没有改那个 60 s**（Plan 01 已结案的断言）。建议控制者：要么承认 2.08× 够用
  （它刚过硬规矩 #42 的 2× 线），要么把这条也改成「带任何全局钩子/在 CI 上就 skip」。
* **哪条测试会在它失效时变红**：就是它自己。⚠️ 而它**抓不到「慢但没超 60 s」**：
  处方阶段若再退化 2×（到 ~58 s）它照样绿。故 28.85 s 这个数是**历史实测、不被守卫**。

**关切 3：按 `batch_id` 整批删会连带删掉教师当天的人工数据。**

* 事实：`_replay_cleanup` 按 `batch_id` 删 `prescription` 与 `weekly_adjustment`。
  而 P6-A8 的口径是「教师手工加的调整行取**所属处方当前的 `batch_id`**」，
  `teacher_overrides` 也长在处方行上。
* 后果：**重放那一天会把教师当天的覆盖与手工微调一起删掉**，且没有任何提示。
* 这不是本 Task 引入的缺陷（它是「重放 = 删本批 + 重写」这个既有策略的必然推论，
  Plan 01 的三张派生表同构，只是那三张不含人工输入）。**处方是本仓第一张含人工输入的派生表**，
  于是这条代价第一次变得要紧。
* 处置：**没有擅自加「人工数据豁免于重放」的机制**（那会牵动 `_replay_cleanup` 的语义、
  `test_rerunning_the_same_business_date_reproduces_every_table` 的口径、以及 spec §1.3 的
  可复现性承诺）。已在 `prescription_stage.py` 与 `daily.py` 的 `_replay_cleanup`
  两处 docstring 里如实写明，并登记到这里。**建议 Plan 03（教师端）落地前先裁定。**

**关切 4：`PrescriptionReport.skipped_reasons` 今天不落库。**

* 事实：`daily_sync_run` 只有 `prescription_count` 一列（Plan 01 建的），
  故 `skipped` / `needs_review` / `skipped_reasons` 三个值只活在返回值与日志里。
* 后果：教师端的「重新生成」按钮对 Z0 学生无声失败时，**运维只能翻日志**。
  Task 6 传导的第 4 件事要求「必须留下可交代的痕迹」——本 Task 给的是
  「报表对象 + 每批一条 `warning` 日志 + `stratification_result.label`」三处，
  但**没有一处是库里可查的计数**。
* 处置：**没有给 `daily_sync_run` 加列**（那是 Plan 01 已结案的表，且 spec §4.6 的列清单里
  没有它）。CLI 现在会打一行「处方：本日生成 N 张」。若控制者认为需要落库，
  正确的形状是加一列 `prescription_skipped_count` 或一个 `prescription_skipped_reasons`
  的 `JsonText` 列 —— 交回裁定。

**关切 5：触发 5（教师手动请求）在管道侧恒 `False`，且它今天没有任何写入方。**

* `generate_prescriptions` 的签名（简报钉死）里没有 `teacher_requested`，故循环里
  逐字写 `teacher_requested=False` 并附注释说明理由（管道若替教师点这个按钮，
  就等于每天给全员重发处方）。
* Plan 03 的教师端要触发它时，**需要给本函数加一个形参**（或另开一个单学生入口，
  那时 `profile_of` 就是现成的第一块积木）。这一点已写在 `profile_of` 的 docstring 里。
* ⚠️ 故 spec §5.2 的第 5 条今天**端到端不可达**（domain 侧由
  `tests/domain/test_prescription_triggers.py` 的 48 格穷举守着，管道侧没有）。
  这是**如实记录**，不是遗漏。

### 8.3 顶回控制者的地方（3 处）

**顶回 1：计划 Step 1 那句「旧处方 `status` 变 `replaced`、`valid_to` 关账」——「关账」这半句是错的，没有照做。**

* **哪条决定**：`test_a_layer_change_regenerates_and_replaces`（旧处方 `status` 变 `replaced`、
  **`valid_to` 关账**；新处方 `active`）。
* **为什么错**（三条，逐条可核）：
  1. **与 Task 6 已结案的代码直接冲突**：`app/db/models/prescription.py` 里
     `Prescription.valid_to` 那一列的注释逐字写着「换处方时把上一张置 `replaced`，
     **不改写**它的 `valid_to`」。控制者的预检 P7-A4 正是引用这个文件裁定 import 路径的，
     故它是本 Task 的**权威输入**，而计划 Step 1 那句是愿景文档的措辞。
  2. **改写它就废掉 spec §4.3 的可追溯性**：同一列注释还写着「一张 2026-03 生成的处方
     必须能在 2027 年离线复算出它当时的 `valid_to`」。`valid_to` 是
     `generated_on + microcycle_weeks` 的**纯函数**；一旦按「换处方那天」改写，
     它就不再可复算，而「离线复算」正是本计划反复强调的那条硬要求。
  3. **Plan 01 有过同一条裁定**：`daily._stratify_and_persist` 里
     `stratification_result.valid_to=None` 的注释逐字是「**刻意不去关闭上一日的行**：
     ……把旧行的 `valid_to` 写成本日会让重放必须同时改写上一批的行——那会破坏
     『同一业务日期重跑只动本批』这条幂等边界」。处方侧改写上一张的 `valid_to`
     是**同一个形状**。
* **替代方案（已实现）**：`previous.status = REPLACED`，`valid_to` **不动**。
  「哪一张现在生效」由 `status` 唯一确定，不靠日期区间 —— 而 `Prescription.STATUSES`
  里那四个值（`active` / `replaced` / `archived` / `needs_review`）存在的意义正是这个。
  测试断言 `rows[AS_OF].valid_to == VALID_TO_FROM_D`（**不改写**）+
  `rows[AS_OF].status == "replaced"` + `rows[d2].status == "active"`。
* **代价**：两张处方的有效期**可以重叠**（红层处方 09-15..10-12 与黄层处方
  09-22..10-19）。任何「按日期区间查当前处方」的读侧**必须**同时过滤
  `status == 'active'`。这一句已写进 `Prescription.valid_to` 的列注释（本 Task 更新）
  与 `prescription_stage.py` 的行内注释。
* **同时更正了 Task 6 那句注释的适用范围**：它原来的括注是「（它本来就到期了）」，
  那只在**触发 3** 驱动的换处方上成立；触发 2（分层标签变化）驱动的换处方发生在
  旧处方**还没到期**的时候。已就地补写（commit `a5fd7db`）。
* **另一种读法**：「`valid_to` 关账」也可以读成「旧处方的有效期到此**结算完毕**（不再续）」
  而不是「把 `valid_to` 这一列改写」。若控制者取的是后一种读法，那本实现**已经满足**，
  这一条顶回自动消失。

**顶回 2：`skipped_reasons` 加了第四个键 `"assembly_error"`（计划只列了 `MatchStatus.value` 与 `"no_trigger"`，加上传导的 `"insufficient_data"` 是三类）。**

* **哪条决定**：`PrescriptionReport.skipped_reasons`（键是 `MatchStatus.value` 或
  `"no_trigger"`）+ 传导来的 `"insufficient_data"`。
* **为什么必须加**：简报「决定」第 2 条要求「`assemble` / `apply_safety` 抛的异常必须
  **按学生捕获**，转成 `needs_review` + **留痕**」。而那个学生**没有**处方行、
  也**没有**匹配失败，故他既不属于任何 `MatchStatus`、也不属于 `"no_trigger"`
  （触发是成立了的）、更不属于 `"insufficient_data"`（他的数据够）。
  **三类键里没有任何一格能装下他** —— 而不装的话，「留痕」就只剩一条日志，
  `generated + skipped == 分层行数` 这条恒等式也会破。
* **替代方案（已实现）**：`ASSEMBLY_ERROR = "assembly_error"`，这一档**同时**计入
  `skipped` 与 `needs_review`（故两个计数不是互斥的两半，`needs_review` 可以大于
  `generated` —— 这一点写进了 `PrescriptionReport` 的 docstring）。
* **代价**：`skipped_reasons` 的键域从「6 个 `MatchStatus` + 2」变成「+ 3」。
  任何按键域穷举的读侧要知道这一格。已写进 `ASSEMBLY_ERROR` 的常量注释与
  `PrescriptionReport` 的 docstring。
* **另一个被否掉的方案**：把装配失败塞进 `"no_trigger"`（键域不变）—— 那是**撒谎**：
  触发明明成立了，是生成失败了；教师看到 `"no_trigger"` 会以为「今天不该换处方」，
  而正确的处置是「去看那条 warning 日志、修那个学生的数据或那套模板」。

**顶回 3：装配失败**不**落一张 `status = "needs_review"` 的行，「转成 needs_review」落在报表的那一格上。**

* **哪条决定**：简报「决定」第 2 条的字面是「转成 `needs_review` + 留痕」。
* **为什么不落行**：一张 `prescription` 行必须带 `training_package`
  （`Mapped[dict]`，NOT NULL）。装配已经失败了，**没有任何包可写**；
  写一个 `{}` 进去就是**撒谎**——它声称「有一张待复核的训练包」，而教师打开来是空的、
  也无从改（`OverrideKind` 的五种覆盖全部作用在一个**存在的**训练包上）。
  而 `status = "needs_review"` 的语义（Task 5 的 P5-A3）是**明确的**：
  「安全规则命中却找不到等价动作，训练包已经装好了、只是里面有一个 block 原样保留」。
  把「装配炸了」混进同一格会让教师端那一个队列里出现两种性质完全不同的东西。
* **替代方案（已实现）**：`PrescriptionReport.needs_review` 的语义**扩写成两个来源之和**
  （① 落库为 `needs_review` 的张数；② 装配失败因而没有行的学生数），
  并逐字写进 `PrescriptionReport` 的 docstring 与模块 docstring 的「异常分层」第 1 档；
  同时 `skipped_reasons["assembly_error"]` 计数、一条 `warning` 日志点名学号/模板/异常。
* **代价**：`needs_review` 不再是「`status = 'needs_review'` 的行数」的同义词。
  故 `test_daily_sync_run_prescription_count_matches_the_report` 只对
  `prescription_count == generated` 做三方对账（计数列 / 报表 / 表行数），
  **没有**把 `needs_review` 与表里的 `status` 计数强行划等号；
  而 `test_needs_review_when_no_equivalent_exercise` 单独钉住
  「安全那一档 `report.needs_review == 1` 且 `row.status == 'needs_review'`」、
  `test_per_student_assembly_failure_does_not_roll_back_the_batch` 单独钉住
  「装配那一档 `report.needs_review == 1` 且**没有**行」。两条各钉一个来源，不会互相掩盖。

### 8.4 没按派单做的地方（**5 处**）

1. **建议的 4 次 commit 变成了 6 次，且 ②③ 合并**。派单建议「② `prescription_stage.py` +
   它的测试；③ `daily.py` 接入 + `_replay_cleanup` + Step 0 的两条集成测试」。
   实际做不到：B 节的 24 条测试里有 **9 条**要经 `run_daily` 跑整条管道
   （60 人端到端的计数、幂等、次日无触发、装配失败不回滚、`profile_of` 的单一所有者、
   Step 0 的两条），`daily.py` 不接上它们连收集都过不去；而 `_replay_cleanup` 的两条
   （正证 + 反证）又直接调 `daily._replay_cleanup`。故 ②③ 合成 `a5fd7db` 一个 commit，
   另外多出 `08db233`（变异 ① 的守卫补强）、`ca265ab`（散文连带）、`fd6a427`
   （更正自己写下的假数字）三个。
2. **计划 Step 1 的「`valid_to` 关账」没照做** —— 见 8.3 顶回 1。
3. **计划 Step 2–6 的变异 ② 预期「重放翻倍测试红」，实测红的是清单那条直接守卫** ——
   见第 7 节变异 ②。`test_rerun_same_day_does_not_duplicate_prescriptions` 保持绿色，
   因为 `UniqueConstraint` + `repo.upsert` 让「翻倍」这个症状在 `prescription` 上
   结构不可达（它对 `weekly_adjustment` 才成立，而那张表今天没有生产写入方）。
4. **计划 Step 1 的「500 人零注入 → 500 张 / 缺省注入 → 498 张」两个数没有进测试网**。
   两个数**本轮都亲跑复现了**（`500` / `498`，见 5.2 ④），但跑一次 500 人的整条管道约 29 s，
   加两条会让套件翻倍，而 `test_backfill.py` 已经有一条 500 人的墙钟测试。
   故它们记进本报告与 `test_prescriptions_are_generated_for_every_stratified_student` 的
   docstring，标注为**历史实测、不被守卫**；测试网里守这一档的是 `bare` 夹具的三条
   （含一条四档标签各一人的）。
5. **`assemble` 抛异常时不落 `needs_review` 行** —— 见 8.3 顶回 3。

（另外：派单第 2 节说「改 4 个已结案文件」，实际改了 **5 个** ——
多出的一个是 `app/db/models/prescription.py`，改的是 **3 段注释、0 行逻辑**：
Task 6 传导的第 3 件事逐字要求「在表注释里写明这个口径」，另两处是
「Task 7 已落地」的现状更新（硬规矩 #66）与顶回 1 那句 `valid_to` 注释的适用范围更正。）

### 8.5 最终验收

```
cd backend; python -m pytest -q -p no:cacheprovider
  749 passed in 79.00s
cd backend; python -m pytest -q -p no:cacheprovider --cov=app.domain --cov-branch --cov-report=term-missing
  748 passed, 1 skipped in 155.45s
  TOTAL   951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%
cd backend; python -m pytest tests/pipeline tests/architecture -q
  91 passed
```

| 验收项 | 值 |
|---|---|
| passed | **749**（基线 716，+33） |
| 覆盖率四格 | **951 / Miss 0 / 274 / BrPart 0 / 100%** |
| `app.domain.prescription.__all__` | **47**（未变） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | **47**（未变） |
| `_MODELS_PUBLIC_BASELINE` | **33**（刻意未变，Ruling 97） |
| 架构守卫扫描面 | **34** = pipeline **8** + db 11 + domain 15 |
| 表数 | **18**（未变） |
| `PIPELINE_TABLES` | **11** |
| `PersonInputs` 字段 | **15** |
| `input_snapshot` 键 | **28** |
| `prescription_stage.__all__` | **10** |

**禁区**（本轮亲跑，全部逐字不变）：

```
backend/pe.db 存在？                     False
backend/data/seed/ 里的文件数             0
backend/data/national_standard_2014.csv   21412 B   sha256[:16] = D2C8E539E2FA0029
backend/data/exercises.yaml               22739 B   sha256[:16] = 3DE598AF38631209
backend/data/exercise_equivalence.yaml     8245 B   sha256[:16] = 822CB86A5E998301

git diff --stat d498bac HEAD -- backend/data                          -> （空）
git diff --stat d498bac HEAD -- backend/tests/fixtures/golden_cases.json -> （空）
git status --short -- backend                                          -> （空）
```

**全程没有跑过** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`；
要数据集一律在 python 里 `build_dataset(cfg)` + `write_csv(ds, <临时目录>)`
（探针与测试夹具都是这个形状，落在 `%TEMP%` 与 pytest 的 `tmp_path` 里）。

**改动的 10 个文件**（`git diff --stat d498bac HEAD`，合计 2579 insertions / 38 deletions）：

```
backend/app/db/models/prescription.py             |   40 +-   （3 段注释，0 行逻辑）
backend/app/domain/percentile.py                  |   42 +    （lookup_p10 + docstring）
backend/app/pipeline/backfill.py                  |    3 +-   （「六个阶段」→ 七个）
backend/app/pipeline/daily.py                     |   89 +-   （Prescribe 阶段 + _replay_cleanup）
backend/app/pipeline/percentile_stage.py          |   20 +-   （构造点补三字段）
backend/app/pipeline/prescription_stage.py        |  866 +    （新建）
backend/app/pipeline/run_stratify.py              |  111 +-   （三字段 + 两键 + 回填两档）
backend/tests/domain/test_percentile.py           |   57 +-   （+3 条）
backend/tests/pipeline/test_daily.py              |   44 +-   （PIPELINE_TABLES 9→11 + 4 处 docstring）
backend/tests/pipeline/test_prescription_stage.py | 1345 +    （新建，30 条）
```


---

## Task 7 fix round 1

基线 `fd6a427`，分支 `feature/plan-02-prescription-engine`（未 push、未切分支、未碰 main）。
本轮修 3 项（1 Critical / 2 Important），**2 个 commit**：

| commit | 内容 |
|---|---|
| `f0623b3` | **F1-1** 加列 + 填值 + 改读法 + 那条新测试；**F1-2** 的 docstring 实测与测量条件；`test_daily.py` 的 canonical 取证表 |
| **（本 commit）** | **F1-3** 计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告。⚠️ 一个 commit **印不出自己的 sha**（本报告就在这个 commit 里），故它 = `git log --oneline -2` 的第 1 条 = 本轮交回控制者的第 2 个 sha |

改动面（`git diff --stat fd6a427 f0623b3`）：**6 个文件、280 insertions / 104 deletions**，
全在 `backend/`；`backend/data/` **零改动**。

### 1. F1-1（Critical）：`prescription` 补 `label_at_generation` 列

#### 1.1 实测先行（硬规矩 #89，全部运行时口径）

派单要求「`stratification_result.label` 那一列今天用的是什么长度，先实测再决定，与它保持一致」。实测：

| 量 | 实测值 | 出处 |
|---|---|---|
| `stratification_result.label` 的类型与长度 | **`String(20)`**，`nullable=False`（由 `Mapped[str]` 推出） | `StratificationResult.__table__.c.label` |
| 它有没有 CHECK | **有** | `_in_domain("label", LABELS, "ck_stratification_result_label")` |
| 那条 CHECK 的文本 | `label IN ('green', 'insufficient_data', 'red', 'yellow')` | 运行时 `str(sqltext)` |
| 值域的所有者 | `StratificationResult.LABELS`（类常量，**四个**值） | 同上 |
| 最长值 | `insufficient_data` = **17** 字符 | `max(len(v) for v in LABELS)` |
| 旁证 | `derived_metrics.trend` 也是 `String(20)`，它的列注释逐字写着「取 20 与 `stratification_result.label` 对齐：两列存的是同一族 17 字符的值」（Ruling 144） | `app/db/models/derived.py` |

→ **新列与它逐字同口径**：

```python
label_at_generation: Mapped[str] = mapped_column(String(20), nullable=False)
```

（派单给的字面形状逐字照写，含显式 `nullable=False`。）

**CHECK 也加了**，因为派单的条件成立（「除非 `stratification_result.label` 也有」——它有），
并按「照抄它的写法与约束名命名风格」：

```python
_in_domain(
    "label_at_generation",
    StratificationResult.LABELS,
    "ck_prescription_label_at_generation",
),
```

⚠️ **一处按派单的「单一所有者」要求做的取舍，值得单独交代**：值域**没有**在
`Prescription` 上另立第二份类常量，而是**直接引 `StratificationResult.LABELS`**
（`prescription.py` 因此新增 `from .derived import StratificationResult`；`derived.py`
自己也是这么引 `organisation.Student` 的，`derived` 不 import 本模块，**无环**）。
实测 `hasattr(Prescription, "LABELS") is False`。
对照 `PrescriptionTemplate.LAYERS`（那里**收窄成三个**、确实另立了一份常量）：那是必要的，
因为模板的 `layer` 真可能被人写成 `insufficient_data`、需要 DB 拒收；而**本列的写入方只有
管道**，且 Z0 闸门在 `upsert` 之前就 `continue`，故收窄没有收益、只多一个所有者。
于是值域**含** `insufficient_data` 而生产上写不进那一档 —— 这一句已写进列注释，
免得下一个人以为它是漏网的脏值。

**新列的运行时实测**：`String(20)` / `nullable=False` / `default=None` /
CHECK = `label_at_generation IN ('green', 'insufficient_data', 'red', 'yellow')`。
`prescription` 的 CHECK 从 **1** 条变 **2** 条（`ck_prescription_label_at_generation` +
`ck_prescription_status`）。

#### 1.2 `prescription` 的新列数

**15 → 16**（`len(list(Prescription.__table__.columns))`，运行时口径）。逐字：

```
['id', 'student_id', 'generated_on', 'batch_id', 'template_ref', 'microcycle_weeks',
 'label_at_generation', 'training_package', 'assembly_snapshot', 'safety_substitutions',
 'teacher_overrides', 'previous_had_overrides', 'status', 'valid_from', 'valid_to',
 'trigger_reasons']
```

新列插在 `microcycle_weeks` 之后 —— 三个「生成当时的快照」
（`template_ref` / `microcycle_weeks` / `label_at_generation`）挨在一起。
⚠️ 列序不影响 canonical sha256（`json.dumps(..., sort_keys=True)`）。

⚠️ **派单说要同步改 `test_models.py` 里「钉住 `prescription` 列数」的断言 —— 实测没有那条断言**，
见第 8 节顶回 ②。

#### 1.3 那条新测试的名字与「改前红 / 改后绿」两次实测

**名字**：
`tests/pipeline/test_prescription_stage.py::test_trigger_2_survives_the_deletion_of_that_days_stratification_row`
（放在 **B5 节「换处方：触发 2 与 `replaced`」**，因为它的主题是触发 2）。
数据形状：`red`(D1 = `2025-09-15`) 生成一张处方 → **删掉 D1 那一天的
`stratification_result` 行**（并断言 `_count(...) == 0`，坐实「真的删掉了」）→
`yellow`(D2 = `2025-09-22`) 跑第二天。

**改之前（红，逐字，`python -m pytest -q tests/pipeline/test_prescription_stage.py -k trigger_2_survives -p no:cacheprovider`）**：

```
    pair = (<app.db.models.prescription.Prescription object at 0x00000118C6EC4110>, None)
        row, label = pair
        if label is None:
>           raise ValueError(
E           ValueError: 学生 1 在 2025-09-15 没有分层结果，而他当天有一张处方（id=1）：触发 2 要比的是「生成当时的标签」，没有它就只能静默拿今天的标签去比，而那会让触发 2 变成一个每天都可能开火（或永远不开火）的假判据。两张表本该由同一批次在同一个 SAVEPOINT 里写

app\pipeline\prescription_stage.py:551: ValueError
=========================== short test summary info ===========================
FAILED tests/pipeline/test_prescription_stage.py::test_trigger_2_survives_the_deletion_of_that_days_stratification_row - ValueError: 学生 1 在 2025-09-15 没有分层结果，而他当天有一张处方（id=1）：触发 2 要比的是「生成当时的标签」，没有它就只能静默拿今天的标签去比，而那会让触发 2 变成一个每天都可能开火（或永远不开火）的假判据。两张表本该由同一批次在同一个 SAVEPOINT 里写
1 failed, 30 deselected in 0.72s
```

⚠️ 红的**机制正是派单预测的那一个**：`outerjoin` 读不到 → `label is None`。
（`30 deselected` 是**删掉旧守卫之前**的数；删掉之后是 `29 deselected`。）

**改之后（绿，同一条命令）**：

```
.                                                                        [100%]
1 passed, 29 deselected in 0.72s
```

断言的是（全部字面写死，硬规矩 #35）：`second.generated == 1`、
`rows[d2].trigger_reasons == ["layer_changed"]`（即 `TriggerReason.LAYER_CHANGED.value`
在里面，且**只有**它 —— D2 距 D1 整 7 天 < 4×7，触发 3 不成立；`bare` 夹具没有采集行，
触发 4 对 `None` 短路；触发 5 在管道侧恒 `False`）、
`rows[d2].label_at_generation == "yellow"`、`rows[AS_OF].label_at_generation == "red"`、
`rows[AS_OF].status == "replaced"`、`rows[d2].status == "active"`。

#### 1.4 本轮唯一一处**删**测试（把理由写全）

删掉的是首轮的
`tests/pipeline/test_prescription_stage.py::test_a_prescription_whose_stratification_row_is_gone_fails_loudly`。

* 它钉的是「触发 2 的比较对象查不到 → `_last_prescription_of` 响亮抛 `ValueError`」。
* 那个失效形态的**前提**是「标签只能 `outerjoin` 回读同一天的 `stratification_result`」。
  F1-1 之后标签是处方行自己的一个 **NOT NULL、无缺省**的列 → **前提消失** →
  那个 `ValueError` 分支**结构上不可达**（与硬规矩 #39「不可达的分支不留」一致）。
* 取代它的新测试用的是**同一个数据形状**，断言的是**相反**的结论：触发 2 **仍然成立**、
  整批不回滚。这不是「削弱守卫」，而是把守卫从「失败要响」升级成「根本不该失败」。
* 删掉之后「不许为空」这件事**没有失去守卫**：它搬到了
  `tests/db/test_models.py::test_prescription_label_at_generation_shares_its_domain_with_the_label_column`
  （漏传 → `IntegrityError`，消息里含 `prescription.label_at_generation`；
  写 `"blue"` → `IntegrityError`，消息里含 `ck_prescription_label_at_generation`）。
* 原地留了一段**注释**交代这次取代（不留下一个「为什么这里少了一条测试」的谜）。

#### 1.5 实现侧的三处改动

1. `generate_prescriptions` 的 upsert 值字典加 `"label_at_generation": label` ——
   `label` 就是本循环手上 `result.label`（当天刚写好的 `stratification_result.label`），
   **零额外查询**，与派单的要求逐字一致。
2. `_previous_prescriptions`：**删掉那个 `outerjoin`**，签名从
   `-> dict[int, tuple[Prescription, str | None]]` 变成 `-> dict[int, Prescription]`，
   `load_only(...)` 从 6 个小列变 **7** 个（多留 `label_at_generation`）。
   AST 复核：该函数里 `ast.Attribute` 的名字集合**已无 `outerjoin`**、
   源码里也已无 `StratificationResult`（`join` 仍在 —— 那是与 `latest` 分组子查询的连接，
   是「取每人最新一张」的机制，不是跨表回读）。
   ⚠️ 顺带少一张表的连接：整学期回放（500 人 ×112 业务日）不再逐日碰
   `stratification_result`（那张表学期末 56 000 行、每行约 2 KB 的 `input_snapshot`）。
3. `_last_prescription_of(row)`：读 `row.label_at_generation`，删掉 `ValueError` 分支。
   它因此变成一个**纯映射**、不再碰库，也就不再属于模块 docstring「异常分层」的第 2 档
   （那一档的清单已同步改掉，见 1.6）。

#### 1.6 变异取证（硬规矩 #83）

前后 `shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` +
`-p no:cacheprovider`，跑完立刻还原（还原后复核：文件 **50 298 B**、`String(20)` 命中 1、
`String(16)` 命中 0）：

| 变异 | 红了哪几条 | 结论 |
|---|---|---|
| 新列 `String(20)` → `String(16)`（17 字符的 `insufficient_data` 塞不下） | `test_string_column_widths_fit_their_value_domains`（Plan 01 那道**遍历**测试）+ `test_prescription_label_at_generation_shares_its_domain_with_the_label_column` → **`2 failed, 58 passed`** | 新列**自动被那道遍历测试覆盖**（它带 CHECK，故 `_in_domain_columns()` 反解得出值域）—— 与 `Exercise.ref` / `template_ref` 那几列「没有 CHECK → 不被覆盖 → 要另找地方钉」（P2-A5 / P3-A5）**不同档** |
| 还原 | `60 passed` | — |

⚠️ **计划正文的「变异 ⑤」不需要另跑**：我在计划里补的那条
（「把 `_last_prescription_of` 改回 `outerjoin` 读 `stratification_result.label` →
新测试当场红」）**就是 1.3 那次改前红的实测状态**，取证已在手，不必再制造一次。

### 2. F1-1 的连带：canonical sha256 的新值

派单点名要这两个值（控制者要拿它回填账本与 spec §1.3）。`canonical_dump` **逐字复用**
`tests/pipeline/test_daily.py` 的那一个（import 它，不复制第二份），夹具形状逐字复刻
`test_rerunning_the_same_business_date_reproduces_every_table`（`CFG`：60 人 /
`seed=20250828` / 缺省注入，`D = 2025-09-15`），**两遍 `run_daily`**，n=1：

| 表集合 | sha256 | 行数合计 | 与首轮相比 |
|---|---|---|---|
| **9 张**（Plan 01） | `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952` | **882** | **逐字未变** |
| **11 张**（Task 7） | `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df` | **942** | **变了**（首轮是 `05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816`） |

两个哈希都在**两遍运行之间逐字相同**（探针里 `assert (h_first, rows_first) == (h_second, rows_second)`，
两档各断言一次）。

**9 张为什么没变**：本轮只动 `prescription` 一张表（加一列），而它**不在**那 9 张里
（9 张 = `fitness_test_batch / fitness_test_result / body_composition / interest_survey /
percentile_snapshot / derived_metrics / stratification_result / daily_sync_run / cleaning_log`）。
这是一次**有意义的交叉验证**：它坐实了 F1-1 没有顺手改到 Plan 01 的任何一张表。
**11 张为什么变了**：`prescription` 的每行多了一个键（`sort_keys=True` 之后字节串不同）。
**行数合计不变**（942 = 882 + 60 张处方 + 0 条周微调）—— 加的是**列**不是**行**。

逐表行数（11 张，本轮实测）：

```
fitness_test_batch           4      derived_metrics             60
fitness_test_result        240      stratification_result       60
body_composition           240      daily_sync_run               1
interest_survey            120      cleaning_log               133
percentile_snapshot         24      prescription                60
                                    weekly_adjustment            0
```

`prescription.label_at_generation` 的实测分布 = `{'green': 24, 'red': 7, 'yellow': 29}`
（合计 60）—— 与 `prescription_stage.py` 模块 docstring 里那句「60 人夹具在
`D = 2025-09-15` 上的标签分布 `{yellow: 29, green: 24, red: 7}`」**逐字复现**，
即新列填的确实是当天的分层标签、且 0 个 `insufficient_data`（Z0 那一档在 60 人夹具下是 0 人）。

⚠️ **这四个值都不被守卫**（那条测试刻意只断言 `first == second`，硬规矩 #35），
它们是一次取证记录。`test_daily.py` 的 docstring 取证表已按此更新（并把「过期两次」
抬成「过期三次」，逐个列出三次成因）。

### 3. F1-2：`test_backfill_500_students_under_60_seconds` 的余量

#### 3.1 三次**不带** `--cov`（派单点名的命令）

`python -m pytest -q tests/pipeline/test_backfill.py -k under_60`（加 `-p no:cacheprovider --durations=1`），
三次都 **`1 passed, 6 deselected`**：

| # | `--durations` 的 `replay` setup 墙钟 | 整条命令墙钟 |
|---|---|---|
| 1 | `30.10s setup` | `1 passed, 6 deselected in 30.65s` |
| 2 | `30.65s setup` | `1 passed, 6 deselected in 31.00s` |
| 3 | `30.59s setup` | `1 passed, 6 deselected in 31.13s` |

⚠️ **setup 墙钟 ≠ 被断言的那个 `elapsed`**：`replay` 这个 module 级 fixture 的 setup
= `seed_database`（约 0.4 s）+ `run_backfill`（= `elapsed`）。派单要的是**三个 `elapsed`
值逐字**，而那条测试**不打印**它（它只在 skip 消息里打印，而 skip 只在有 trace 钩子时发生），
故另写探针**逐字复刻 `replay` 的 fixture 体**（同 `CFG` 500 人 / `seed=20250828`、
同 `START..END`、同「本地 SQLite 文件」而非 `:memory:`、同 `time.perf_counter` 夹住
`run_backfill` 那一段），并在探针开头 `assert sys.gettrace() is None`：

| # | `elapsed`（逐字） | 余量 `60 / elapsed` |
|---|---|---|
| 1 | **28.86 s** | 2.08× |
| 2 | **29.05 s** | 2.07× |
| 3 | **29.59 s** | **2.03×** |

**最小余量 = `60 / 29.59` = 2.03×**。（本轮先跑过一次同样的 n=3，得到
`min = 28.61 / max = 29.06`（其中第 3 次逐字 `29.00 s`）、最小余量 **2.06×**；
两次 n=3 合计 6 个样本，**最坏值就是 29.59 s / 2.03×**，故报告以它为准。）

#### 3.2 一次**带** `--cov`

`python -m pytest -q tests/pipeline/test_backfill.py -k under_60 -p no:cacheprovider
--cov=app.domain --cov-branch -rs --durations=1`：

```
59.09s setup    tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds
SKIPPED [1] tests\pipeline\test_backfill.py:182: 检测到 trace 钩子（coverage / debugger）：本次量到的回放墙钟是 57.25 s，而 spec §1.3 的「< 60 秒」指的是**生产墙钟**。…
1 skipped, 6 deselected in 59.91s
```

* `elapsed` = **57.25 s**（逐字取自 skip 消息，那正是断言会看到的那一个量）→ 余量
  **`60 / 57.25` = 1.05×**，**远低于** 2× 线。
* **`sys.gettrace()` 钩子今天仍在、仍生效**（派单点名要核的这件事）：
  `git grep -n "gettrace" -- backend/tests/` → **1 命中**，
  `backend/tests/pipeline/test_backfill.py:181`（`if sys.gettrace() is not None:`，
  skip 出自 `:182`）。Plan 01 的 Ruling 228 那次教训（带 `--cov` 时余量 0.95×）
  **今天以 1.05× 复现**，而它被这个钩子如实挡住 —— 钩子不是装饰。

#### 3.3 处置（派单 F1-2 第 3 条）

最小余量 **2.03× < 2.5×**，故**没有放宽断言**（放宽等于取消守卫），改为把两处优化的
实测前后值 + 测量条件写进那条测试的 docstring（硬规矩 #42 要求写下测量条件）：

```
接入处方阶段、未优化          52.89 s（另一次亲跑量到 115.08 s → 本条当场红）
两处优化之后（缺省注入）      28.85 s   → 余量 2.08×
两处优化之后（零注入）        28.81 s
fix round 1 复测（n=3）       28.86 / 29.05 / 29.59 s → 最小余量 2.03×
fix round 1 带 --cov（n=1）   57.25 s → 余量 1.05×，被 gettrace 钩子如实 skip
```

两处优化（都在 `prescription_stage.py`）：**①** 主查询**同时**按 `batch_id` 过滤
（那一列 `index=True`）—— 只按 `computed_on` 单列过滤用不上 `(student_id, computed_on)`
那条唯一索引（它以 `student_id` 打头）→ 全表扫描，而 `stratification_result` 到学期末
56 000 行 × 约 2 KB 的 `input_snapshot`，112 天累计约 310 万行扫描；
**②** 上一张处方的预取用 `load_only(...)` 把 4 个大 `JsonText` 列延迟加载
（`training_package` 是 4 周 ×4 课 ×3 block 的嵌套字典，逐人逐日 eager 加载 ≈ 56 000 次
大 JSON 解析，而本阶段一个字节都不读它）。

测量条件（已逐字写进 docstring）：Windows 10（10.0.26200）/ AMD64 /
Intel64 Family 6 Model 197 / 16 核，CPython 3.11.1、SQLAlchemy 2.1.3、SQLite 3.39.4、
pytest 9.1.1、coverage 7.16.2；**本地 SQLite 文件**（非 `:memory:`）；
`elapsed` 只夹 `run_backfill`，**不含** `build_dataset` / `write_csv` / `seed_database`；
n=3 独立干净跑、不带 `--cov`、无 trace 钩子；带 `--cov` 那一行是 n=1 且必然被 skip。

⚠️ **仍然报为关切**（与首轮关切 2 同一条，数字按本轮更新）：余量 **2.03×** 只是刚过
硬规矩 #42 的 2× 线，而**本机墙钟极差本来就大**（同一个夹具在优化前量到过 52.89 s 与
115.08 s）；且它**抓不到「慢但没超 60 s」**—— 处方阶段若再退化 2×（到约 58 s）本条照样绿。
F1-1 删掉的那次跨表连接是**往好的方向**动（少一张表的连接），本轮 6 个样本
28.61–29.59 s 与首轮的 28.85 s 在同一个噪声带里，**看不出可归因于 F1-1 的位移**。

### 4. F1-3：计划正文的同步（硬规矩 #84）

#### 4.1 ⚠️ 复核结论：控制者说自己本轮改了 4 处，**实测 0 / 4 在树上**

改前取证（探针 `t7_probes/_t7f1_plan_precheck.py`，在 `HEAD = fd6a427` 上）：

```
=== 改前：计划正文实测命中次数 ===
  更正① Task7 Step1 的『valid_to 关账』               1     ← 未改（应 0）
  更正① Task6 决定的『并关账 valid_to』                1     ← 未改（应 0）
  更正② 变异②的『重放翻倍测试红』                      1     ← 未改（应 0）
  更正③ 表定义里有没有 label_at_generation             5     ← 5 处全是**别处**的引用，表定义那一行没有
  更正④ skipped_reasons 的 assembly_error             0     ← 未改（应 ≥1）
  补① Task8 的 WeeklyAdjustment import 路径           1     ← **在**（无需改）
  补① Task8 的 weekly_factors_of                      1     ← **在**（无需改）

git status --porcelain -- Document/2026-10-06-实施计划02-智能处方引擎.md
  -> ''  (空 = 相对 HEAD 未改动)
  HEAD = fd6a427
  文件 190726 B / 1023 行
```

`git status` 对那个文件**为空**、且 4 处原文**逐字仍在** → 那 4 处更正**一处都没落笔**。
（更正③ 的 5 处命中全在别处：`LastPrescription` 的字段清单、触发 2 的判据表、
Task 6 的测试名 `test_layer_change_compares_against_the_label_at_generation`、
§14 补项 #37 —— **`prescription` 表定义那一行没有它**。）

#### 4.2 逐处结论 + 我改了什么（共 **11** 处替换 + 1 处计数连带）

| # | 派单点名的那一处 | 复核结论 | 我做的更正 |
|---|---|---|---|
| ① | Task 7 Step 1「旧处方 `status` 变 `replaced`、**`valid_to` 关账**」 | **错**（未改） | 改成「**`valid_to` 不改写**」+ 标出**控制者错误 #149** + 指回 Task 6 那一条；并把 F1-1 的新测试写进 Step 1 的清单（含「加列之前必须红、之后必须绿」与「它取代了哪一条」） |
| ①′ | **同一事实在 Task 6「决定」里还有一处**：「**换处方时把上一张置 `replaced` 并关账 `valid_to`**」（硬规矩 #66：一个事实变了要 grep 出全部同类陈述） | **错**（未改，且派单没点这一处） | 改成「置 `replaced`，但**不改写**它的 `valid_to`」+ 三条理由（`valid_to` 必须是该行自身数据的纯函数 / 触发 1/2/4/5 会在自然到期前换处方，回溯改写会随重放批次顺序改出不同的值 / 与 Plan 01 `stratification_result.valid_to` 恒 NULL 同一条裁定）+ 保留「与 Plan 01 不矛盾」那半句 |
| ② | Task 7 变异 ②「把 `_replay_cleanup` 的清单里 `prescription` 删掉 → **重放翻倍测试红**」 | **错**（未改） | 改成「→ **`test_replay_cleanup_covers_prescription_and_weekly_adjustment` 当场红**」+ 标出**控制者错误 #150**（那个失效形态**在结构上不可达**：唯一约束 + `repo.upsert`，翻倍写不进去）+ 一句教训（与硬规矩 #65 同源：写变异判据之前先问「这个失效形态在结构上可达吗」）；并**追加变异 ⑤**（改回 `outerjoin` → 新测试红） |
| ③ | Task 6「决定」里 `prescription` 表的字段清单 | **错**（未改） | 清单末尾加 **`label_at_generation: String(20), nullable=False` + CHECK**，并写明：15 → **16** 列、#148 的形状、与 P6-A3 同构的理由、列宽与 CHECK 与 `stratification_result.label` 同口径、值域**引 `StratificationResult.LABELS`**（单一所有者）、不加它的三个失效形态 |
| ④ | Task 7「决定」里 `skipped_reasons` 的键 | **错**（未改） | 补第四个键 **`"assembly_error"`** + 理由（三类键里没一格能装下「触发成立了但装配炸了」的人，不装就等于让这批学生在报表里凭空消失）+ **顶回 ③**（装配失败**不落** `status="needs_review"` 的行，`training_package = {}` 是一个看起来正常的谎；「转 needs_review」落在报表计数 + `skipped_reasons` + `warning` 日志上） |
| ④′ | **同一事实在 Interfaces 那一行还有一处**：`skipped_reasons: dict[str, int]`（键是 `MatchStatus.value` 或 `"no_trigger"`） | **本来就漏**（连 `"insufficient_data"` 都没写） | 改成四类键都列出 + 指回「决定」那一条 |
| ③′ | **同一事实在 Task 7「⚠️ Task 6 新增的三列必须由本 Task 填」还有一处** | **未改** | 标题改成「三列 + fix round 1 追加的一列」，并在 `previous_had_overrides` 之后插一条 `prescription.label_at_generation` 的填法（来源 = 当天刚写好的 `stratification_result.label`，**不需要额外查询**；`_last_prescription_of` 从这一列读、不再 `outerjoin`） |
| 计数 | Task 6「决定」与 `models/prescription.py` 的类 docstring 各有一处「spec §4.4 **+ 三处预检更正**」 | 加了一列 → 计数过期（硬规矩 #66） | 两处都改成「+ 三处预检更正 **+ fix round 1 的一处追加**（F1-1，控制者错误 #148）」 |
| 补① | **Task 8** 的 `weekly_factors_of(session, prescription_id)` 那条 import 路径 | **✅ 在，无需改** | 逐字复核：`⚠️ **ORM 行的 import 路径同 Task 7**：` `from app.db.models.prescription import WeeklyAdjustment` `（Ruling 97：它**不在** `app.db.models` 的公有导入面上）` —— 命中 1 处，且 `weekly_factors_of` 也命中 1 处 |
| 补② | **Task 9** 的 13 例要不要断言 `label_at_generation` | 见下面 4.3 | 已写进 Task 9 Step 1 |

#### 4.3 Task 9 的判断：**同意「要」，但要写清它钉得住什么、钉不住什么**

派单要我给判断，控制者倾向「要」。**我同意**，理由是控制者那一条：它是触发 2 的
**唯一判据**，而 Task 9 是最后一个能钉住它的地方。⚠️ 但**无保留地同意会立一条看起来强、
其实弱的守卫**（硬规矩 #39 的反面），故写进 Task 9 正文的版本带四条边界：

* **钉得住**：处方行上那一列填的是**当天分层结果的那一个标签**，且与黄金用例里已逐条
  人读确认的 `expected.label` **逐字相等**（两侧不同源：一侧是 fixture 的字面量、
  一侧是库里的列）。抓的是「填错了来源」—— 填成 `dominant_bucket`、填成昨天的标签。
* **钉不住**：**触发 2 本身** —— 黄金用例是**单日**的，而触发 2 要两天。故它**不是**
  `test_trigger_2_survives_the_deletion_of_that_days_stratification_row` 的替代，两条**并列**。
* ⚠️ `insufficient_data` 那一例**没有处方**（Z0 闸门），故 13 例里只有 **12** 例能断言它。
* ⚠️ **它与 `template_id` 不是两份独立的证据**：对**已匹配**的处方，`label_at_generation`
  与 `template_ref` 的前三字符（`RED` / `YEL` / `GRN`）**恒等** —— 匹配器就是按
  `Layer(label)` 选模板的。它多出来的那一份价值是「与 `expected.label` 这个**已人读的
  字面量**同源比对」，而不是「多一个字段」。**别把它写成两条互相印证的守卫。**

### 5. 最终验收

| 项 | 首轮（`fd6a427`） | **fix round 1（`f0623b3` + docs）** |
|---|---|---|
| 全量 passed（**不带** `--cov`） | 749 | **750** |
| 全量（**带** `--cov=app.domain --cov-branch`） | 748 passed, 1 skipped | **749 passed, 1 skipped** |
| `app/domain` 覆盖率 | 951 / Miss 0 / 274 / BrPart 0 / 100% | **951 / Miss 0 / 274 / BrPart 0 / 100%**（逐字未变；本轮不新增 domain 代码，`triggers.py` 一个字没动） |
| `prescription` 列数 | 15 | **16** |
| 全库表数 | 18 | **18** |
| `PIPELINE_TABLES` | 11 张 | **11 张** |
| `app.domain.prescription.__all__` | 47 | **47** |
| 扫描面 | 34（domain 15 + pipeline 8 + db 11） | **34（15 + 8 + 11）** |
| `models` 公有导入面 | 33，四个 Plan02 表类都不在里面 | **33**，`Exercise` / `PrescriptionTemplate` / `Prescription` / `WeeklyAdjustment` **仍都不在里面**（Ruling 97 未被破坏；本轮新增的 `from .derived import StratificationResult` 在**子模块**里，不经 `import *` 进包面） |
| `PersonInputs` 字段数 | 15 | **15** |
| `lookup_p10` / `lookup_p20` 签名 | 逐字相同 | **逐字相同**（本轮未动 `percentile.py`） |
| `_replay_cleanup` 清单顺序 | `(DerivedMetrics, StratificationResult, PercentileSnapshot, WeeklyAdjustment, Prescription)` | **逐字未变**（AST 口径复核，子表先删，P7-A4 仍在） |
| `prescription_stage.py` | 50 675 B / 866 行 | **50 707 B / 860 行**（删掉那个 `ValueError` 分支与 `outerjoin`，加上新列的注释与填值） |
| `prescription_stage.py` 公开面 | `PrescriptionReport` / `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions` | **逐字未变**（AST 口径） |
| 三个禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **逐字不变**（21 412 B / 22 739 B / 8 245 B） |
| `golden_cases.json` | 27 346 B / sha16 `8C787701EA70EF90` | **未改**（27 346 B / sha16 `8C787701EA70EF90`） |
| `backend/pe.db` | 不存在 | **不存在** |
| `backend/data/seed/` | 0 文件 | **0 文件** |
| `git diff fd6a427 HEAD -- backend/data` | — | **空** |

Plan 01 的全部既有测试仍全绿（750 里含它们；带 `--cov` 时那 1 skipped 就是 F1-2 那条）。

### 6. 2 个 commit 的 sha

* **`f0623b3`** —— `fix: Plan02 Task7 fix round 1 F1-1 —— prescription 加 label_at_generation 列（控制者错误 #148）`
  （6 个文件：`app/db/models/prescription.py`、`app/pipeline/prescription_stage.py`、
  `tests/db/test_models.py`、`tests/pipeline/test_prescription_stage.py`、
  `tests/pipeline/test_daily.py`、`tests/pipeline/test_backfill.py`）
* **（本 commit，sha 印不出来）** —— `docs:` F1-3 的计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告。⚠️ 一个 commit 无法在自己的内容里印出自己的 sha；它 = `git log --oneline -2` 的第 1 条，也已在本轮交回控制者的最终回复里逐字给出

### 7. 我没按本派单做的地方（**4 处，全是「多做了」，没有「少做」）**

1. **多加了一条 schema 守卫**：派单说 F1-1 的那条测试是「本项**唯一**的可执行判据」。
   我另加了
   `tests/db/test_models.py::test_prescription_label_at_generation_shares_its_domain_with_the_label_column`。
   理由：那两条测试的**主语不同**（硬规矩 #56）—— 新测试守的是**行为**
   （删掉分层行后触发 2 仍成立），这条守的是 **schema**（同宽 / 同值域 / NOT NULL 无缺省 /
   两条 CHECK 的值域部分逐字相同 / 漏传与脏值各炸一次）。而且 Task 6 的每一列都有这样一条
   （`status` / `template_ref` / `microcycle_weeks` / `previous_had_overrides` / `valid_to`），
   不加就是这一列独缺。变异实证它有牙（1.6）。
2. **多跑了一次变异**（1.6 的 `String(20)` → `String(16)`）：派单本轮没要求变异，
   但它顺带证明了「新列**自动**被 Plan 01 那道列宽遍历测试覆盖」这件事 —— 那正是
   P2-A5 / P3-A5 两次踩过的坑（没有 CHECK 的列不被覆盖），值得一次实证。
3. **改了计划正文里派单没点名的 4 处**（表 4.2 的 ①′ / ④′ / ③′ / 计数）：
   都是硬规矩 #66 的连带（同一个事实的另一处陈述）。**没有**改任何与本轮无关的散文。
4. **改了 `prescription_stage.py` 模块 docstring 里两处失效引用**
   （`_current_prescriptions` / `_labels_at` —— 这两个函数今天都不存在，是首轮留下的假名字）：
   它们就在「异常分层」第 2 档那一句里，而那一句因为 `_last_prescription_of` 变成纯映射
   **必须**改（它不再属于「基础设施异常」那一侧），故顺手把同一句里的两个假名字改对。
   ⚠️ 严格说这是纯散文精度问题（Ruling 145 允许记进待清扫不返工），但它与必须改的那半句
   **在同一行**，留着就是一个我自己刚写下的假名字（硬规矩 #19）。

**少做的地方：0 处。** 派单的 F1-1 / F1-2 / F1-3 三项要求逐条都做了；
F1-2 第 4 条（「若最小余量 < 2.0× 就停下来报回控制者」）**未触发**（2.03× > 2.0×），
故按第 3 条走（写进 docstring），没有停下来。

### 8. 我认为本派单错了的地方（顶回 —— 前 19 次全对，这是第 20、21 次）

**顶回 ①：派单说「控制者本轮已经改了计划正文的 4 处」—— 实测 0 / 4 在树上。**

* 证据（4.1 那份改前取证）：`git status --porcelain -- Document/…md` **为空**
  （相对 `HEAD = fd6a427` 一个字节都没动），而 4 处原文**逐字仍在**
  （`` `valid_to` 关账`` 1 命中、``并关账 `valid_to` `` 1 命中、`重放翻倍测试红` 1 命中、
  `assembly_error` **0** 命中）。
* 这不是「改错了」，是**没落笔**。形状与硬规矩 #19（假数字）同族：**把「我打算改」
  讲成「我已经改」**，而派单还据此给我派了一件「复核」的活 —— 复核一个不存在的改动，
  最可能的结局是我照着派单的口述**以为**它们对了、于是一个字都不查。
  → 建议记为**控制者错误 #151**。
* 我按硬规矩 #84 自己改了（11 处替换 + 1 处计数连带），逐处见 4.2。

**顶回 ②：派单预设 `test_models.py` 里有一条「钉住 `prescription` 列数」的断言 —— 实测没有。**

* 派单原文：「⚠️ `test_models.py` 里若有钉住 `prescription` 列数的断言（Task 6 加过
  `len(...columns) == 15` 之类的守卫），**同步改**。」
* 实测：`git grep -nE "__table__\.c\) ==|columns\)\) ==|len\(.*\.columns\) ==" -- backend/tests`
  **只命中 1 处**，是 `assert len(PrescriptionTemplate.__table__.c) == 10, "Task 3 结案时是 10 列，本 Task 不动它"`
  —— 那是 **Task 3 给另一张表**加的，本轮不动它。`Prescription` **从来没有**列数守卫。
* 这与**控制者错误 #150 是同一个形状**：派单预设了一个**结构上不存在**的东西
  （#150 预设了一个结构上不可达的失效形态，本条预设了一条不存在的断言）。
  → 建议记为**控制者错误 #152**，并考虑把硬规矩 #65 的扩写从「变异判据」推广到
  「**派单里提到的每一条既有守卫，都要先 `git grep` 核实它存在**」。
* ⚠️ **我刻意没有去新加一条「`prescription` 是 16 列」的守卫**：纯计数守卫抓不到任何
  失效形态（少一列会由 NOT NULL 违例 / 1.3 那条新测试 / canonical sha256 三条里的
  至少一条抓到），而它会给 Plan 03 每次加列都添一次「改一个数字」的活。
  派单是**条件句**（「若有…同步改」），条件为假 → 不动，故这不算偏离；
  **若控制者要它，请明说**，我下一轮加。

### 9. 待清扫（纯散文精度，本轮按 Ruling 145 不返工）—— **3 条**

1. **`models/prescription.py` 的模块 docstring 只有「加**表**」的同步清单，没有「加**列**」的。**
   本轮实测加一列要动 **3** 处：`tests/db/test_models.py` 的 `_in_domain_columns()` docstring
   里那个「今天 **N** 列」的计数（带 CHECK 的列才进那份计数）、同文件的
   `_prescription_fields()`（NOT NULL 且无缺省的列一律要显式给值）、以及
   `tests/pipeline/test_daily.py` 的 canonical sha256 取证值（**只有**加进
   `PIPELINE_TABLES` 那 11 张表的列才会触发它，而这一点今天没有任何文字交代）。
   那段清单的开头写着「⚠️ **Plan 03 再加表时，下面这套同步动作要重跑一遍**」——
   Plan 03 大概率也要**加列**（教师端 CRUD），故建议补一小节「加列时」。
2. **`_previous_prescriptions` docstring 第 2 条里那句「不延迟时整学期回放多花约 `30 s`
   （`52.89 s` vs 基线 `28.4–34.0 s`）」自相矛盾**：它自己括注的两个数算出来是
   **约 24 s**（52.89 − 28.85），不是 30 s。首轮写的时候那个「30 s」大概是
   `load_only` **单独**一项的贡献（另一项是 `batch_id` 索引过滤），但正文没这么说，
   读起来就是一个与自己括注对不上的数（硬规矩 #19 的形状）。本轮未改（纯散文，
   且改它需要重跑一次「只加 `load_only`、不加 `batch_id` 过滤」的对照，不值一轮的时间）。
3. **`test_backfill.py` 那条测试 docstring 的**开头**两句仍然印着 Plan 01 的值、且没有时间限定词**：
   「**两种读法都达标**（Ruling 172）：整学期 112 天 **17.98–18.92 s**（3.2–3.3× 余量…)」
   —— 那是**接入处方阶段之前**的量，今天是 28.86–29.59 s。本轮补的那一段（3.3）
   **在它下面**，且开头就写了「⚠️⚠️ 上面那张表是 Plan 01 的口径」，故**信息不缺、
   但顺序上先读到过期值**。建议下一轮把那一句加上「Plan 01 结案时」的限定词
   （本轮没改：它是 Plan 01 的取证记录，改它等于改写别人的实测，而加限定词又要连带
   改 `replay` fixture docstring 里的同一组数，超出本轮范围）。
