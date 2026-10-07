# Task 5 报告：清洗管道与 cleaning_log

- 分支：`feature/plan-01-data-foundation`
- 提交：`3f1b2c5` feat: 实现清洗管道，缺失值不填零、异常值修正、量纲启发式识别并全程留痕
- 前序 HEAD：`b932a1d`（工作区提交前后均干净）
- 测试：**188 passed**（原 176 条全部未改动、仍通过；本任务新增 12 条）
- 状态：**DONE_WITH_CONCERNS**（实现完成且全绿，但有 4 项需要控制方裁定的口径，见「关注点」）

---

## 1. 实现了什么

### 1.1 `backend/data/indicator_ranges.yaml`（专家维护的知识资产，已入库）

11 个测量字段，每字段一个**四键映射**：`min` / `max` / `non_positive_is_missing` / `zero_allowed`。
区间与 `non_positive_is_missing` 取值逐字来自 brief Step 3 的表格：

| 字段 | 区间 | non_positive_is_missing | zero_allowed |
|---|---|---|---|
| height_cm | [140, 220] | true | false |
| weight_kg | [35, 150] | true | false |
| vital_capacity_ml | [800, 9000] | true | false |
| sprint_50m_s | [5.0, 15.0] | true | false |
| sit_and_reach_cm | [−15, 40] | **false** | true |
| standing_jump_cm | [120, 400] | true | false |
| strength_count | [0, 60] | **false** | true |
| distance_run_s | [150, 900] | true | false |
| muscle_mass_kg | [20, 90] | true | false |
| body_fat_pct | [3, 60] | true | false |
| smi | [4, 15] | true | false |

文件头注释写明了 Ruling 21 的完整推理链（含 `score_item` 低侧夹取实测 100 分）、为什么不能
在 `score_item` 里一刀切拒绝 `<= 0`、以及日期列/学号/batch_key 为何不在本表内。

### 1.2 `backend/app/pipeline/clean.py`

对外接口全部按 brief 的 Interfaces 段落实现，签名逐字一致：

- `FieldRange`（`@dataclass(frozen=True)`，四属性）
- `CleaningEntry`（`@dataclass`，六字段：`student_no` / `field` / `original_value` /
  `processed_value` / `kind` / `reason`）——字段名与 ORM `CleaningLog` 的列名逐字对齐
  （Ruling 46）。实测 `{CleaningEntry 字段} ⊆ {CleaningLog 表列名}` 为 True，Task 10 可按名落库。
- `CleanResult`（`fitness` / `body_comp` / `entries` / `dropped` / `corrected`）
- `load_ranges(path) -> dict[str, FieldRange]`（Ruling 45 更正后的返回类型）
- `clean_fitness(records, ranges) -> CleanResult`
- `clean_body_comp(records, ranges) -> CleanResult`
- `normalize_height(cm) -> tuple[float | None, CleaningEntry | None]`（**单参数**，Ruling 45）

处置规则（优先级从上到下）：

1. `None` → 保留 `None`，记 `missing_dropped`。**绝不填 0。**
2. 缺测占位（见下）→ 转 `None`，记 `missing_dropped`。
3. 越界 → 夹取到最近的区间边界，记 `outlier_corrected`，**整条记录保留**。
4. 其余原样通过，不产生条目。

「缺测占位」判据（`_placeholder_reason`，只看 `value <= 0`）：

- `non_positive_is_missing=true` → `<= 0` 一律是占位（Ruling 21 的核心）。
- `value == 0` 且 `zero_allowed=false` → 占位。
- `value < 0` 且 `min >= 0` → 占位：下界为 0 的计数字段上负数不可能出现，只能来自「未测」
  哨兵；夹取到 0 会**伪造**一条「该生一个也做不起」的真实成绩。
- 否则（`min < 0` 的字段收到区间内负值，如坐位体前屈 −1.3）→ 合法真实值，原样保留。

其它实现要点：

- `kind` 的四个取值定义为模块常量，`CleaningEntry.__post_init__` 用 `CleaningLog.KINDS`
  校验（**从模型读取，不重抄字符串**），拼错会在构造点立刻 `ValueError`，而不是等到 Task 10
  落库被 CHECK 约束拒绝。
- `load_ranges` 校验键集合与「两个原始记录数据类的测量字段」**完全相等**（多一个/少一个都
  抛带文件路径与 offending 键名的 `ValueError`）；测量字段清单由 `dataclasses.fields()`
  推导，排除 `_IDENTITY_FIELDS = {student_no, batch_key, tested_on, measured_on}`，不手抄
  第二份真相。另校验四键齐全、布尔类型、数值类型（先排除 `bool`，因为 `isinstance(True, int)`
  为真，否则 `min: true` 会被当成 1 静默通过）、`min <= max`、以及
  `non_positive_is_missing=true` 与 `zero_allowed=true` 的自相矛盾组合。
- **先去重、再清洗**（顺序有意）：若先清洗再去重，被丢弃那条重复行产生的修正条目会留在
  审计里，描述的却是一条没进结果的记录——审计指向不存在的数据比没有审计更糟。
- 去重键 `(student_no, batch_key)`，保留输入顺序中**靠后**的一条，就地替换原位置（不打乱
  批次内顺序），记 `duplicate_removed`。
- 日期列（`tested_on` / `measured_on`）与身份列原样透传，清洗层不做任何处理（Ruling 41）。
- `clean_fitness` 只填 `fitness`、`clean_body_comp` 只填 `body_comp`，另一个列表为空。
- 无数据库访问、无评分调用、无分层逻辑；唯一的 db 侧依赖是 `from app.db.models import
  CleaningLog`（只取 `KINDS` 常量）。已核对 `app/db/session.py` 的 `engine()` 是工厂函数，
  import 期不建引擎、不碰磁盘。依赖方向 `pipeline → db` 与 base.py 声明的分层一致。

---

## 2. 钉死的 `dropped` / `corrected` / `duplicate_removed` 口径

计划只声明了 `CleanResult.dropped` / `corrected` 两个计数字段而没给定义，现按控制方裁定实现，
并由 `test_dropped_and_corrected_counters_exclude_duplicate_removed` 钉住三条：

- `dropped` = `entries` 中 `kind == "missing_dropped"` 的条数
- `corrected` = `entries` 中 `kind in {"outlier_corrected", "unit_normalized"}` 的条数
- `duplicate_removed` 出现在 `entries` 里，但**两个计数都不进**——被去掉的是一整条重复行，
  活下来的那一行完好无损，既没丢值也没改值

测试构造：`[rec(), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)]`
（同键，第二条覆盖第一条），断言四种 kind 各出现一次、`dropped == 1`、`corrected == 2`、
`len(r.fitness) == 1`。若把 `duplicate_removed` 误计入任一边，`dropped` 会变 2 或 `corrected`
会变 3，测试即失败。

口径写在 `clean.py` 的 `_CORRECTED_KINDS` 常量注释与 `CleanResult` docstring 两处。

---

## 3. TDD 证据

### RED

```
PS backend> python -m pytest tests/pipeline/test_clean.py -q
=================================== ERRORS ====================================
________________ ERROR collecting tests/pipeline/test_clean.py ________________
ImportError while importing test module '...\backend\tests\pipeline\test_clean.py'.
tests\pipeline\test_clean.py:12: in <module>
    from app.pipeline.clean import clean_fitness, clean_body_comp, normalize_height, load_ranges
E   ModuleNotFoundError: No module named 'app.pipeline.clean'
=========================== short test summary info ===========================
ERROR tests/pipeline/test_clean.py
!!!!!!!!!!!!!!!!!!! Interrupted:1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.16s
```

**为什么是这个失败**：与 brief Step 2 的预期逐字一致——测试文件第 12 行 import 尚未存在的
`app.pipeline.clean`，收集期即失败。模块级 `RANGES = load_ranges(...)` 位于 import 之后，
故失败点是 `ModuleNotFoundError` 而不是 `FileNotFoundError`（YAML 当时也还不存在）。

中途还捕获到一次**真实的实现缺陷**（不是测试问题）：`_placeholder_reason` 初版把
`if not fr.zero_allowed` 写成了无条件分支，导致所有 `non_positive_is_missing=true` 字段上的
**正值**（如 `distance_run_s=240.0`）也被判成缺测。5 条测试失败暴露了它，已改为先
`if value > 0: return None` 再分支。

### GREEN

```
PS backend> python -m pytest tests/pipeline/test_clean.py -v
tests/pipeline/test_clean.py::test_unit_error_height_in_meters_normalized PASSED
tests/pipeline/test_clean.py::test_outlier_corrected_and_logged PASSED
tests/pipeline/test_clean.py::test_body_fat_out_of_range_logged PASSED
tests/pipeline/test_clean.py::test_duplicate_record_removed_keeping_newer PASSED
tests/pipeline/test_clean.py::test_missing_field_produces_missing_dropped_entry_not_zero PASSED
tests/pipeline/test_clean.py::test_zero_filled_time_field_becomes_missing_not_outlier_corrected PASSED
tests/pipeline/test_clean.py::test_zero_strength_count_is_a_real_value_not_missing PASSED
tests/pipeline/test_clean.py::test_negative_strength_count_is_missing PASSED
tests/pipeline/test_clean.py::test_negative_sit_and_reach_is_a_real_value PASSED
tests/pipeline/test_clean.py::test_clean_record_passes_through_untouched PASSED
tests/pipeline/test_clean.py::test_dropped_and_corrected_counters_exclude_duplicate_removed PASSED
tests/pipeline/test_clean.py::test_load_ranges_rejects_unknown_or_omitted_field PASSED
12 passed in 0.24s
```

全量与 `-W error`：

```
PS backend> python -m pytest -q            → 188 passed in 0.85s
PS backend> python -m pytest -q -W error   → 188 passed in 0.80s
```

输出干净（无 warning、无 skip、无 xfail）。基线 `176 passed` 已在本任务开工前先跑过并记录。

### 行为核对（临时脚本，已删除，未入库）

用真实运行输出核对关键行为，其中最重要的一条是**反事实验证**：

```
=== sprint_50m_s = 0.0 / distance_run_s = 0.0 ===
  cleaned sprint_50m_s = None        cleaned distance_run_s = None
  dropped/corrected = 2 / 0
  [missing_dropped] sprint_50m_s: 0.0 -> None
  [missing_dropped] distance_run_s: 0.0 -> None
  反事实：score_item(SPRINT_50M, 0.0) = 100 | score_item(SPRINT_50M, 下界 5.0) = 100
          | score_item(DISTANCE_RUN, 0.0) = 100

=== strength_count ===
  0.0  -> 0.0，entries = []，dropped = 0        （合法真实值，一条痕都不留）
  -1.0 -> None，[missing_dropped] strength_count

=== sit_and_reach_cm ===
  -1.3  -> -1.3（保留，无条目）     -20.0 -> -15.0（outlier_corrected）

=== 越界夹取保留整条记录 ===
  记录数 = 1；height 175.0 / weight 65.0 / vital None / sprint 5.0 / sit 12.0 /
  jump 230.0 / strength 10.0 / distance 240.0；身份列 S1 | 2025-2026|week1 | 2025-09-04 原样

=== 去重 ===
  保留 tested_on = 2025-09-06（靠后那条），sprint = 7.1；dropped = 0，corrected = 0

=== normalize_height 边界 ===
  None->(None,None)  0.0->(0.0,None)  -1.0->(-1.0,None)  1.75->(175.0, unit_normalized)
  2.9->(290.0, unit_normalized)  3.0->(3.0,None)  175.0->(175.0,None)  250.0->(250.0,None)
  height_cm=0.0 走完整清洗 -> None + missing_dropped（通用规则由 clean_fitness 施加，不在本函数内）

=== 覆盖与对齐 ===
  ranges 键集合 == 测量列集合（8 + 3 = 11）：True
  CleaningEntry 六字段全部是 CleaningLog 的列名：True
  CleaningLog.KINDS == 本模块四个 kind 常量：True
```

反事实那一行是本任务的价值证明：`0.0` 与被夹取后的下界 `5.0` **都拿 100 分**，所以
「修正为区间下界」这条看似合理的处置与直接放行 0 一样致命，只有转 `None` 才安全。

---

## 4. 改动的文件

| 文件 | 状态 | 行数 |
|---|---|---|
| `backend/app/pipeline/clean.py` | 新增 | 429 |
| `backend/data/indicator_ranges.yaml` | 新增 | 95 |
| `backend/tests/pipeline/test_clean.py` | 新增 | 134 |

`3 files changed, 658 insertions(+)`，无既有文件被修改（前 176 条测试的源码与 fixture 一字未动）。
三个文件均为 UTF-8 **无 BOM**、LF 换行（已用 `[System.IO.File]::ReadAllBytes` 逐字节核对）。
未新增 `conftest.py`、未新增 `tests/__init__.py`（与既有测试目录一致）、未引入 linter、
未建 venv、未触碰 `national_standard_2014.csv` 与 `app/domain/`。

**写盘核验**：每次编辑后都用 shell 确认字节落盘——`git status --short`、`git hash-object`
（三文件哈希 `d16b007…` / `e44311e…` / `da7fbb6…`）、`Select-String` 定位改动行号
（`399: if value > 0:`、`410: if fr.zero_allowed:`、`416: if fr.min >= 0:`）、
`git diff --cached --stat`，以及最终由 pytest 的实际断言结果反证。

---

## 5. 自查结果

| 自查项 | 结果 |
|---|---|
| 每个测量字段都有 FieldRange 条目，且无条目指向不存在的字段 | ✅ `set(RANGES) == 测量列集合` 实测 True（8+3=11）；`load_ranges` 双向校验，另有测试钉住 |
| `strength_count = 0` 产生**零条目** | ✅ `entries == []`，`dropped == 0` |
| `sprint_50m_s = 0.0` 产生 `missing_dropped` 而非 `outlier_corrected` | ✅ 值为 `None`，kind 为 `missing_dropped`；缺测判定优先于越界判定 |
| `sit_and_reach_cm = -1.3` 原样保留且无任何条目 | ✅ |
| `strength_count = -1.0` 转 `None` | ✅ 走 `min >= 0` 的负值哨兵分支，不是夹取到 0 |
| 越界修正保留记录与其余字段 | ✅ 实测 8 列中只有越界那一列变化，身份列原样 |
| 日期列完全未被清洗触碰 | ✅ `tested_on` / `measured_on` 在 `_IDENTITY_FIELDS` 内，不进 ranges、不进 `_clean_measure`，实测原样透传 |
| `dropped`/`corrected`/`duplicate_removed` 口径有测试钉住 | ✅ `test_dropped_and_corrected_counters_exclude_duplicate_removed` |
| 每条 `reason` 都是中文且具体 | ✅ 六类理由均含字段名、原值、区间、以及「为什么这么处置」；无笼统的「数据异常」；已移除误写进 reason 的 markdown `**`（它会原样落进 DB 的 Text 列） |
| 前 176 条测试未被改动且仍通过 | ✅ 188 − 12 = 176；`git status` 显示无既有文件被修改 |
| 输出干净，`-W error` 下也干净 | ✅ 两次均 188 passed，无 warning/skip |
| 无越界职责：无 DB 访问、无评分、无 conftest、无 `tests/__init__.py`、无 linter | ✅ 唯一 db 依赖是取 `CleaningLog.KINDS` 常量（控制方明确要求），import 期无副作用 |

---

## 6. 关注点（需要控制方裁定 / 已知取舍）

按报告要求，凡写进代码注释、docstring 的 caveat 全部在此列出。

**C1（需要裁定）空学号记录未做判定与留痕。** `app/adapters/base.py` 的 `RawFitnessRecord`
docstring 明确写着：`student_no` 空单元格原样透传为 `""`，「由 **Task 5 的清洗层**判定并留痕
——缺学号的记录本身就是最该被看见的数据质量问题」。但 Task 5 的 brief 对此**只字未提**，
且 `CleaningLog.KINDS` 的四个取值没有一个能忠实表达「这条记录的学号是空的」：
`missing_dropped` 会错误地推进 `dropped` 计数并暗示值被丢弃（而我们既不会丢记录、也不会把
学号置空）。这直接决定「哪些学生会被算进队列」，属于任务书里明令「不要猜」的类别，故**未实现**，
在此上报请裁定：(a) 保留记录 + 新增一个 kind？(b) 整条记录剔除 + 记 `missing_dropped`
（`field="student_no"`）？(c) 交给 Task 10 在解析 `student_id` 时一并处理？

**C2（需要裁定）`clean_body_comp` 不去重。** brief 只给了体测的去重键
`(student_no, batch_key)`，控制方的任务书也写「for fitness」。体成分表的唯一约束是
`(student_id, measured_on)`，重复行会在 Task 10 落库时撞 `IntegrityError`。但「同日两次测量
取后一条还是取均值」是测量学口径不是实现口径，故未自行发明，docstring 已注明并在此上报。
若裁定为「取后一条」，实现可直接复用体测那段（约 15 行）。

**C3（自行定义，已钉测试）记录级条目的 `field` 取 `"*"`。** `duplicate_removed` 不对应任何
单列，而 `CleaningLog.field` 非空。取 `"*"`（`String(32)`、无 CHECK 约束，能原样落库，审计
界面里一眼可辨「不是某一列的问题」）；`original_value` / `processed_value` 分别放被丢弃行与
保留行的 `tested_on`，让审计能看出哪一条活了下来。这是 brief 未定义的第三处口径，若控制方
另有偏好（如 `""` 或 `"__record__"`）请示下。

**C4（已知取舍）`_placeholder_reason` 的 `value == 0 and not zero_allowed` 分支在当前 YAML
下不可达。** 因为所有 `non_positive_is_missing=true` 的字段其 `zero_allowed=false`，会被前一个
分支先接住。保留它是为了让 `zero_allowed` 成为一个**独立有意义**的配置旋钮（「0 非法但负值
合法」是逻辑上自洽的配置），而不是 `non_positive_is_missing` 的简单取反。若控制方认为这是
多余分支，删掉它同时应把 `zero_allowed` 从 YAML 与 `FieldRange` 中一并移除，否则该属性将
无人读取。

**C5（与 brief 字面的偏差）YAML 每字段带 4 个键，brief Step 3 的示例映射只写了 3 个。**
brief 的 Interfaces 段落要求 `FieldRange` 有 `zero_allowed` 属性，Step 3 的散文与示例
`{min: …, max: …, non_positive_is_missing: …}` 却没提它。选择**在 YAML 中显式写出**
`zero_allowed` 而不是由 `load_ranges` 按 `not non_positive_is_missing` 推导，理由：这是一份
交给体育测量学专家维护的知识资产，「引体向上 0 次是真实值」应该写在专家看得见的地方，而不是
藏在加载器的推导规则里（推导规则本身就是第二处真相）。作为补偿，`load_ranges` 会拒绝
`non_positive_is_missing: true` + `zero_allowed: true` 的自相矛盾组合。

**C6（测试条数偏差）新增 12 条而非 10 条，总数 188 而非 186。** brief Step 1 的十条逐字保留、
一字未削弱；额外两条分别是控制方明确要求的计数口径测试，以及 `load_ranges` 字段名校验测试
（控制方要求「raise a clear error」，未测的守卫等于没有守卫）。故「186」应是裁定追加测试之前
的旧算术。

**C7（低风险，仅记录）`normalize_height` 不对 ×100 的结果做舍入。** `1.68 * 100` 在 IEEE 754
下是 `168.00000000000003`。身高不是国标计分项（只喂 BMI 计算），1e−14 的相对误差对 BMI 与
后续评分无影响，故按 brief 原样返回乘积、不引入 brief 未要求的舍入。若将来身高进入某个按
精确阈值比较的查表路径，需要重新评估。

**C8（接口取舍）`load_ranges(path)` 无默认路径。** 严格按 brief 的签名实现，因此 Task 10 需要
自己构造 `backend/data/indicator_ranges.yaml` 的路径。项目里 `refdata.load_standard` 的既有
惯例是 `path: pathlib.Path | None = None` + 模块级 `DATA_DIR` 常量；若希望统一，可给
`load_ranges` 加同样的默认值（不影响现有调用点）。

---

## 7. 修复轮 1（Ruling 47 / 48 / 49 / 50）

- 起点 HEAD：`3e041cd`（`docs: Ruling 47-50 补齐清洗层的记录级处置口径`），工作区干净
- 修复前基线：`pytest -q` → **188 passed**（已实测复核）
- 修复后：`pytest -q` → **192 passed**；`pytest -q -W error` → **192 passed**（无 warning/skip）
- `tests/pipeline/test_clean.py`：**16 passed** = 原 12 条 + 新增 4 条，与计划 Step 5 的预期条数逐字一致
- 改动文件仅两个：`backend/app/pipeline/clean.py`（+121/−14 行区间内）、`backend/tests/pipeline/test_clean.py`（+104/−2）
- 开工前先核对了「是否已被前一轮做过」：`Select-String` 显示 `_WHOLE_RECORD` 仍是私有名、`clean_body_comp` 仍无去重、`normalize_height` 仍是 `cm * 100`、无空学号处置——**四项全部未实现**，故四项都做了，无跳过项

### 7.1 Ruling 47（C1）空学号整条剔除

**改了什么**：新增私有 helper `_unattributable_entry(student_no) -> CleaningEntry | None`，
`clean_fitness` 与 `clean_body_comp` 的主循环开头各调用一次，命中即 `entries.append(...)` + `continue`
（记录不进入 `survivors`，因而不做量纲/缺测/越界处理，也不参与去重）。条目形状：
`kind="missing_dropped"`、`field="student_no"`、`original_value=` 收到的原始字符串、`processed_value=None`。
**未新增第五个 kind**（`CleaningLog.KINDS` 与 Task 3 的 `ck_cleaning_log_kind` 一字未动）。

**顺序是有意的**：空学号必须在去重**之前**剔除。若让它进去重键，所有空学号记录会在
`("", batch_key)` 上互相碰撞，把两个不同学生的数据当成重复合并掉，还记下一条描述不存在事实的
`duplicate_removed`。这条理由写进了 `clean_fitness` 的 docstring。

**取证**（临时脚本 `$env:TEMP\t5_evidence.py`，跑完即 `Remove-Item`，未入库）：

```
=== Ruling 47：空学号 → 整条剔除 ===
  [体测] 输入学号 '' + 'S2' → 结果学号 ['S2']，dropped=1，corrected=0，entries=1
         kind=missing_dropped field=student_no student_no='' original_value='' processed_value=None
         reason=student_no 为空或全空白（原始值 ''），整条记录无法归属到任何学生，已整条剔除：
                既不入库，也不参与队列、分层与处方的任何计算。请与字段级缺测区分——那种情形
                整条记录仍在结果里、只有该列为空，而这里被丢弃的是整条记录本身
  [体成分] 同输入 → 结果学号 ['S2']，dropped=1，kind=missing_dropped，original_value=''，processed_value=None
  [体测] 输入学号 '   ' + 'S2' → 结果学号 ['S2']，dropped=1，corrected=0，entries=1
         kind=missing_dropped field=student_no student_no='   ' original_value='   ' processed_value=None
  [体成分] 同输入 → 结果学号 ['S2']，dropped=1，kind=missing_dropped，original_value='   '，processed_value=None

=== 对照：字段级缺测（记录仍在，只有该列为空） ===
  结果记录数=1，vital_capacity_ml=None
  reason=vital_capacity_ml 在原始记录中为空（未测、仪器无读数或导入时丢失），按缺测处理保留空值；
         绝不填 0——0 会被 score_item 当成真实成绩夹取计分
```

`""` 与 `"   "` 在 `original_value` 上可区分（`''` vs `'   '`），`reason` 里也用 `{student_no!r}`
原样带出。最后那段「对照」是裁定要求的可区分性证明：字段级缺测的 reason 说「保留空值」且
记录数仍是 1，记录级剔除的 reason 说「整条记录…已整条剔除」且记录从结果里消失。

**覆盖测试**：`test_blank_student_no_drops_the_whole_record_with_an_attributable_reason`
（对 `""` 与 `"   "` 两种输入 × 体测/体成分两条路径，断言：结果里只剩 `S2`、恰好一条
`missing_dropped` 且 `field == "student_no"`、`original_value` 等于原始串、`processed_value is None`、
`reason` 同时含「整条记录」与「无法归属」、`dropped == 1`）。

### 7.2 Ruling 48（C2）`clean_body_comp` 去重

**改了什么**：`clean_body_comp` 现在与 `clean_fitness` 同构——`survivors` + `position_of` 就地替换，
去重键 `(student_no, measured_on)`，**保留输入顺序中靠后的一行**，记 `duplicate_removed`
（`field=WHOLE_RECORD`，两个值列放被丢弃行与保留行的 `measured_on`）。**没有任何求均值的代码路径。**
原 docstring 里「不去重、交由后续任务裁定」那段已删除，替换为 Ruling 48 的口径与理由。

**取证**：

```
=== Ruling 48：体成分去重（保留后者，绝不取均值） ===
  输入行1 = RawBodyCompRecord(student_no='S1', measured_on='2025-09-01', muscle_mass_kg=45.0, body_fat_pct=22.0, smi=7.0)
  输入行2 = RawBodyCompRecord(student_no='S1', measured_on='2025-09-01', muscle_mass_kg=47.0, body_fat_pct=26.0, smi=7.6)
  结果行数=1，存活行=RawBodyCompRecord(student_no='S1', measured_on='2025-09-01', muscle_mass_kg=47.0, body_fat_pct=26.0, smi=7.6)
  存活 body_fat_pct=26.0；两值均值=24.0；存活值 == 均值 ? False；存活值 == 后行值 ? True
  条目 kind=duplicate_removed field='*' original_value='2025-09-01' processed_value='2025-09-01'；dropped=0 corrected=0
  reason=学号 S1 在测量日 2025-09-01 上出现多条体成分记录，保留输入顺序中靠后的一条、丢弃靠前的一条；
         绝不取均值——两条测量的平均值是一个从未被测量过的数，而「复测/更正以最后一次为准」是可解释的口径。
         不去重会让落库变成 (student_id, measured_on) 唯一约束下的静默覆盖，无痕可查
```

**「不是均值」这一条被单独证伪过**：`存活值 == 均值 ? False`（26.0 ≠ 24.0），且 `存活值 == 后行值 ? True`。
`dropped` / `corrected` 都仍是 0——与 §2 钉住的口径一致（`duplicate_removed` 两个计数都不进）。

**覆盖测试**：`test_body_comp_deduplicates_keeping_later_row_and_never_the_average`
（断言：结果只剩一行、`body_fat_pct == 26.0`、`body_fat_pct != (22.0 + 26.0) / 2`、
`muscle_mass_kg`/`smi` 也取后行值、恰好一条 `duplicate_removed`、`field == WHOLE_RECORD`、
两个值列分别是两行的 `measured_on`、`dropped == 0 and corrected == 0`）。

### 7.3 Ruling 49（C7）`normalize_height` 舍入到 1 位小数

**改了什么**：`normalized = cm * 100` → `normalized = round(cm * 100, 1)`（一行）。条目的
`processed_value` 与 `reason` 里的数值随之都是舍入后的值。docstring 补了 Ruling 49 的理由。

**取证（含一处与裁定文字不符的实测事实）**：

```
=== Ruling 49：normalize_height 舍入到 1 位小数 ===
  1.68 m  → 未舍入 168.0；                 舍入后 168.0；v == round(v, 1) ? True；条目 processed_value=168.0
  2.01 m  → 未舍入 200.99999999999997；    舍入后 201.0；v == round(v, 1) ? True；条目 processed_value=201.0
  1.417 m → 未舍入 141.70000000000002；    舍入后 141.7；v == round(v, 1) ? True；条目 processed_value=141.7
```

裁定文字说「`1.68` 目前变成 `168.00000000000003`」——**在本机 CPython 下不成立**：
`1.68 * 100 == 168.0`（`1.68 / 0.01` 与 `1.68 * 10 * 10` 同样是 `168.0`）。残渣现象本身是真的，
只是触发值不同：`2.01 * 100 == 200.99999999999997`、`1.417 * 100 == 141.70000000000002`。
按 `i/100`（两位小数）扫描 1.40–2.20 m 命中 6 个（2.01 / 2.03 / 2.05 / 2.07 / 2.18 / 2.2），
按 `i/1000`（三位小数）扫描同区间命中 194 个。舍入照裁定实现，理由不变（0.1 cm 就是实测精度，
且身高经 BMI 进 Ruling 18 的档位查表）。

**覆盖测试**：`test_normalize_height_rounds_to_a_tenth_of_a_cm`。裁定点名的两条断言
（`normalize_height(1.68) == 168.0`、`v == round(v, 1)`）**在改动前就是绿的**——因为 1.68 本来
无残渣，钉不住 `round`。故测试同时断言 `2.01 → 201.0` 与 `1.417 → 141.7`：先断言
`2.01 * 100 != 201.0 and 1.417 * 100 != 141.7`（残渣确实存在），再断言舍入后的返回值。
RED 证据（实现前）：`assert 200.99999999999997 == 201.0` 失败；GREEN 后该条通过。

### 7.4 Ruling 50（C3）`WHOLE_RECORD` 导出常量

**改了什么**：`_WHOLE_RECORD` → `WHOLE_RECORD`（去掉下划线即导出），两个调用点
（`clean_fitness` 与新增的 `clean_body_comp`）都引用常量。`duplicate_removed` 的两个值列继续放
被丢弃行与保留行的日期。

**取证**（shell grep，非编辑器复读）：

```
PS backend> Select-String -Path app\pipeline\clean.py -SimpleMatch -Pattern '"*"'
app\pipeline\clean.py:61:WHOLE_RECORD = "*"

PS backend> Select-String -Path app\pipeline\clean.py -SimpleMatch -Pattern "'*'"
（无输出）

PS backend> Select-String -Path app\pipeline\clean.py -Pattern 'WHOLE_RECORD'
28: 测量的平均值是一个从未被测量过的数。去重条目的 ``field`` 写 :data:`WHOLE_RECORD`（它不对应
61: WHOLE_RECORD = "*"
301: field=WHOLE_RECORD,
372: field=WHOLE_RECORD,

PS backend> Select-String -Path app\pipeline\clean.py -CaseSensitive -Pattern '_WHOLE_RECORD'
（无输出，旧私有名无残留）
```

即：字面量 `"*"` 在 `clean.py` 中**只出现一次**，就在常量定义行（第 61 行）；注释里也已把
原来带引号的 `"*"` 改写成「星号」，避免 grep 出现第二个命中点。测试文件里 `"*"` 只出现在
`assert WHOLE_RECORD == "*"` 这一处——那正是「钉住常量取值」的断言本身。

**取证**（运行期）：

```
=== Ruling 50：WHOLE_RECORD 导出常量 ===
  WHOLE_RECORD='*'
  体测 duplicate_removed：field='*' original_value='2025-09-04' processed_value='2025-09-06'
  体成分 duplicate_removed：field='*'
```

**覆盖测试**：`test_whole_record_constant_is_exported_and_pins_record_level_entries`
（`WHOLE_RECORD == "*"`；体测两行 `tested_on` 不同 → 条目的 `field == WHOLE_RECORD`、
两个值列恰为 `("2025-09-04", "2025-09-06")`，即能看出是哪两条撞了）。

### 7.5 TDD 顺序与命令输出

严格 RED → GREEN，每步都用 shell 跑过：

1. 先写 4 条测试 + 改 import → `pytest tests/pipeline/test_clean.py -q` →
   `ImportError: cannot import name 'WHOLE_RECORD' from 'app.pipeline.clean'`，
   `1 error in 0.40s`（RED 第一轮：常量尚未导出）
2. 只做 Ruling 50 的重命名 → 同命令 → `3 failed, 13 passed in 0.41s`，三条各自因正确的原因失败：
   `assert ['', 'S2'] == ['S2']`（空学号未剔除）、`assert 2 == 1`（体成分未去重）、
   `assert 200.99999999999997 == 201.0`（未舍入）
3. 实现 Ruling 49 → `pytest -q -k normalize_height_rounds` → `1 passed, 15 deselected`
4. 实现 Ruling 47 + 48 → `pytest tests/pipeline/test_clean.py -q` → `16 passed in 0.28s`
5. 全量：

```
PS backend> C:\Python\python.exe -m pytest -q
192 passed in 0.84s
PS backend> C:\Python\python.exe -m pytest -q -W error
192 passed in 0.81s
```

188 → **192**（+4），`-W error` 下同样 192 passed，输出无 warning / skip / xfail。
既有 188 条一字未改（`git diff --stat` 只列出 `clean.py` 与 `test_clean.py`；`test_clean.py`
的改动是 import 块换成多行形式 + 文件末尾追加，原 12 条测试体未动）。

### 7.6 写盘核验

每次编辑后都用 shell 确认字节落盘，未依赖编辑器复读：`git diff --stat`
（`clean.py 121 ++++…`、`test_clean.py 104 ++++…`，`2 files changed, 211 insertions(+), 14 deletions(-)`）、
`Select-String` 定位关键行（`61: WHOLE_RECORD = "*"`、`241: normalized = round(cm * 100, 1)`、
`301/372: field=WHOLE_RECORD,`）、以及逐字节核对编码：

```
app\pipeline\clean.py        bytes=26960 BOM=False 含CRLF=False
tests\pipeline\test_clean.py bytes=11308 BOM=False 含CRLF=False
```

两文件仍为 UTF-8 **无 BOM** + LF，与 §4 记录的原始状态一致。

### 7.7 控制方判定「不改」的三项

C4（`zero_allowed=False` 分支在当前 YAML 下不可达）、C5（YAML 每字段 4 键）、
C8（`load_ranges(path)` 无默认路径）本轮**一字未动**：`_placeholder_reason`、
`indicator_ranges.yaml`、`load_ranges` 签名均未出现在 diff 中。

### 7.8 本轮关注点

按报告要求，凡写进代码注释 / docstring / 测试注释的 caveat 全部在此列出：

**F1（与裁定文字不符的实测事实，已写进 `normalize_height` docstring 与测试注释）
`1.68 * 100` 在本机 CPython 下等于 `168.0`，没有 `168.00000000000003` 这个残渣。**
裁定与计划 Step 4 举的都是这个例子。残渣现象真实存在，但触发值是别的：实测
`2.01 * 100 == 200.99999999999997`、`1.417 * 100 == 141.70000000000002`；两位小数扫描
1.40–2.20 m 命中 6 个，三位小数命中 194 个。舍入已照裁定实现（`round(cm * 100, 1)`），
结论与理由都不变；只是**若将来有人拿 1.68 当回归样本，它钉不住 `round`**——所以测试里
额外用 2.01 / 1.417 作载荷，这一点在测试注释里写明了。

**F2（记录级条目的可诊断性在体成分路径上打折，已写进 `clean_body_comp` docstring）
体成分的 `duplicate_removed` 条目里，`original_value` 与 `processed_value` 必然是同一个日期。**
因为 `measured_on` 本身就是去重键的一半。裁定要求「两个值列放被丢弃行与保留行的日期，
这样能看出是哪两条撞了」——在体测路径上成立（键是 `batch_key`，两行的 `tested_on` 可以不同，
实测 `('2025-09-04', '2025-09-06')`），在体成分路径上这两列只能告诉你「哪一天撞了」。
未自行发明别的填法（例如塞 `body_fat_pct`），因为那会偏离裁定文字；要定位具体两行，
得回源 CSV 按学号 + 日期查。

**F3（计划内部两处文字冲突，按更具体的 Ruling 47 实现）空学号条目的 `field` 取
`"student_no"`，不是 `WHOLE_RECORD`。** 计划第 708 行（Ruling 47）明写 `field = "student_no"`，
本轮任务书也逐字重复了这一点，且要求测试断言 `field == "student_no"`；但计划第 714 行
（Ruling 50）写「`duplicate_removed` 与空学号剔除都是记录级而非字段级，`field` **统一**取
`WHOLE_RECORD`」。两处不一致。按「更具体的裁定优先」实现为 `field="student_no"`——语义上也更对：
缺的确实是这一列，`field` 列本来就是指明「哪一列出了问题」的。若控制方本意是空学号也写 `*`，
改动是一行 + 一条断言，请明示。

**F4（未做，属 Task 10 职责）空学号条目落库时 `student_id` 仍为 `NULL`。**
`CleaningLog.student_no` 是 `String(32)` NOT NULL，空串与 `"   "` 都能原样落库（Ruling 25 的
双列设计正是为此），但这类条目的 `student_id` 永远解析不出来。这不是本轮的改动范围，
只是提醒 Task 10：`cleaning_log` 里会出现一批 `student_no` 为空白串的行，报表若按
`student_id` 分组统计「数据质量问题分布」，这批无主条目会落到 NULL 组里。

**F5（保留的既有取舍，本轮未动）** §6 的 C4 / C5 / C8 由控制方判定不改，本轮一字未动；
C6 的算术在本轮后更新为：`test_clean.py` 16 条 = brief 的 10 条 + 控制方追加的 2 条 +
Ruling 47/48/49/50 的 4 条，与计划 Step 5 预期的「16 passed」逐字相符；全量 192 = 原 176 + 16。

---

## 8. 修复轮 2（Ruling 51 / 52 + M1–M4、M6、M8）

- 起点 HEAD：`67a20fd`（`docs: Ruling 52 要求 Task 6 的 duplicate 注入逐字复制整行`），分支
  `feature/plan-01-data-foundation`，工作区干净
- 修复前基线：`cd backend; pytest -q` → **192 passed in 0.85s**（已实测复核）
- 修复后：`pytest -q` → **201 passed**；`pytest -q -W error` → **201 passed**（无 warning / skip / xfail）
- `tests/pipeline/test_clean.py`：16 → **25 passed**（+9：Ruling 51 专项 1 条、M1 学号回填 1 条、
  M3 参数化守卫 7 个用例）
- 改动文件仅两个：`backend/app/pipeline/clean.py`（+117/−67）、`backend/tests/pipeline/test_clean.py`（+133/−8）
- **开工前核对「是否已被前几轮做过」**：`Select-String` 显示 `clean.py:211` 只有
  `non_positive_is_missing`+`zero_allowed` 的矛盾检查、没有 `min > 0` 检查；两处去重块仍是
  复制粘贴的两份（`:286-313` / `:357-384`）；体成分 reason 仍写着「复测/更正以最后一次为准」；
  `KNOWN_MEASURE_FIELDS` 仍是导出名；测试里 `test_outlier_corrected_and_logged` 只有 3 条断言、
  counters 测试的被丢弃行是干净的 `rec()`、`unit_normalized` 只断言 kind 存在、`_parse_range`
  的四道守卫零测试——**八项全部未做，故八项都做了，无跳过项**。

### 8.0 评审点名「不得破坏」的不变量：改后逐条复核

用临时脚本 `$env:TEMP\t5r2_invariants.py`（跑完即 `Remove-Item`，未入库）在**全部修复完成后**
复核，输出原文：

```
=== 1. 缺测检测严格先于越界夹取（承重不变量） ===
  sprint_50m_s = 0.0  →  None，kind = missing_dropped
  dropped=1 corrected=0（必须是 1 / 0）
  反事实：score_item(SPRINT_50M, 0.0) = 100 | score_item(SPRINT_50M, 下界 5.0) = 100 | score_item(SPRINT_50M, None) = None
  → 0.0 与 5.0 都是 100 分，所以「夹到下界」与「放行 0」同样致命

=== 2. strength_count = -1 转 None（不夹到 0） ===
  strength_count = -1.0 → None，kind = missing_dropped
  strength_count = 0.0  → 0.0，entries = []（合法真实值，零留痕）

=== 3. 「哪一行胜出」= 输入顺序靠后，与日期无关（未改） ===
  输入 = [tested_on=2025-09-06(sprint 7.1), tested_on=2025-09-04(sprint 8.8)]
  胜出 = tested_on=2025-09-04, sprint=8.8（输入顺序靠后那条，日期反而更早）
  结果行数 = 1

=== 4. 绝不取均值 ===
  存活 body_fat_pct = 26.0；两值均值 = 24.0；存活值 == 均值 ? False；== 后行值 ? True

=== 5. 无法归属的记录在去重之前被剔除 ===
  两条空学号 → 结果行数 = 0，kinds = ['missing_dropped', 'missing_dropped']，fields = ['student_no', 'student_no']
  有没有 duplicate_removed ? False（必须是 False）

=== 6. kind 常量取自 CleaningLog.KINDS；字段清单仍由 dataclasses.fields() 推导 ===
  CleaningLog.KINDS = ['duplicate_removed', 'missing_dropped', 'outlier_corrected', 'unit_normalized']
  模块四个常量 ⊆ KINDS ? True
  体测测量列 8 + 体成分 3 = 私有并集 11；== ranges 键集合 ? True
  模块还有没有导出的 KNOWN_MEASURE_FIELDS ? False（必须是 False）
```

`_clean_measure` 的三段顺序在最终文件里的行号（`Select-String` 取证，非编辑器复读）：

```
494: if value is None:
508: reason = _placeholder_reason(field, value, fr)
520: if value < fr.min or value > fr.max:
```

即 **None → 占位/缺测 → 夹取**，与修复前逐字同序（原来是 `:444 / :458 / :470`，行号只因上方
新增内容而后移）。第 3 项是「哪一行胜出」未被改动的直接证据：喂入
`[tested_on=2025-09-06, tested_on=2025-09-04]`，胜出的是**输入顺序靠后**而**日期更早**的那条。

### 8.1 Item 1（Important，Ruling 51）`load_ranges` 拒绝 `zero_allowed: true` + `min > 0`

**改了什么**：`_parse_range` 在既有的矛盾检查之后新增 4 行守卫（`clean.py:239-243`）：

```python
if raw["zero_allowed"] and raw["min"] > 0:
    raise ValueError(
        f"{path} 的 {name} 配置自相矛盾: zero_allowed 为 true 时 min 必须 <= 0，"
        f"否则 0 会被夹取到 {raw['min']}——对「越小越好」的项等于把缺测占位送成满分"
    )
```

同时把这条不变量写进 `FieldRange` 的 docstring（`:94-95`）与 `load_ranges` 的 docstring
（`:162-163`，与既有的布尔类型说明并列）。守卫上方 8 行注释记录了实测过的连锁后果。

**反事实取证（这是本项的全部价值所在）**：临时脚本 `$env:TEMP\t5r2_item1_counterfactual.py`
把仓库自带的 `indicator_ranges.yaml` 复制一份、只把 `sprint_50m_s` 改成
`{min: 5.0, max: 15.0, non_positive_is_missing: false, zero_allowed: true}`，写进 `$env:TEMP`，
**在加守卫之前**跑一次：

```
坏配置文件: C:\Users\whwenhao\AppData\Local\Temp\t5r2_bad_ranges.yaml
  sprint_50m_s = {min: 5.0, max: 15.0, non_positive_is_missing: false, zero_allowed: true}

=== load_ranges(坏配置) ===
  被接受！FieldRange = FieldRange(min=5.0, max=15.0, non_positive_is_missing=False, zero_allowed=True)

=== clean_fitness(sprint_50m_s = 0.0) ===
  清洗后 sprint_50m_s = 5.0   （缺测占位 0.0 变成了区间下界）
  条目: [('outlier_corrected', 'sprint_50m_s', 0.0, 5.0)]
  dropped=0 corrected=1

=== score_item 后果 ===
  score_item(SPRINT_50M, 0.0)          = 100
  score_item(SPRINT_50M, 5.0)   = 100
  score_item(SPRINT_50M, None)         = None
```

**加上守卫之后**，同一个脚本、同一份坏配置：

```
=== load_ranges(坏配置) ===
  ValueError（已被拒绝）: C:\Users\whwenhao\AppData\Local\Temp\t5r2_bad_ranges.yaml 的 sprint_50m_s
  配置自相矛盾: zero_allowed 为 true 时 min 必须 <= 0，否则 0 会被夹取到 5.0——对「越小越好」的项
  等于把缺测占位送成满分
```

链条完整闭合：一次 YAML 手误 → `0.0` 被放行 → 夹成 `5.0` → 记 `outlier_corrected`（看起来像
「已妥善处理」）→ `score_item` 给 100 分；而唯一安全的处置 `None` 让 `score_item` 返回 `None`。

**RED 取证（守卫被临时禁用时新测试确实变红）**：把守卫条件改成 `if False and ...` 后

```
PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q -k "zero_allowed or malformed"
FAILED ...::test_load_ranges_rejects_zero_allowed_true_with_positive_min - Failed: DID NOT RAISE ValueError
FAILED ...::test_load_ranges_rejects_malformed_field_configuration[sprint_50m_s-override6-...] - Failed: DID NOT RAISE ValueError
2 failed, 6 passed, 17 deselected in 0.42s
```

其余 6 个参数化用例仍绿，说明失败的正是这一道守卫。随后 `Copy-Item` 从备份还原，
`Select-String -Pattern '临时变异'` 计数为 **0**，`if raw["zero_allowed"] and raw["min"] > 0:`
回到 `:239`。

**现有 11 个字段全部满足新约束**（`git diff` 未触及 YAML，`pytest` 全绿即为证；测试里另有
显式断言 `[name for name, fr in RANGES.items() if fr.zero_allowed and fr.min > 0] == []`）：
`zero_allowed: true` 的只有 `sit_and_reach_cm`（min −15）与 `strength_count`（min 0）。

**覆盖测试**：`test_load_ranges_rejects_zero_allowed_true_with_positive_min`（专项，断言报错
**指名文件 + 指名 `sprint_50m_s` + 说明后果**「5.0」「满分」，并对照仓库自带 YAML 依旧加载成功）
+ `test_load_ranges_rejects_malformed_field_configuration` 的第 7 个参数。

### 8.2 Item 2（Ruling 52）统一去重 `reason` 措辞

**改了什么**：体成分 `reason` 删掉「而「复测/更正以最后一次为准」是可解释的口径」，只留
「保留输入顺序中靠后的一条、丢弃靠前的一条；绝不取均值——两条测量的平均值是一个从未被测量过
的数。」体测 `reason` **一字未改**（它本来就只如实印出两个 `tested_on`，不声称「取最新」）。
`clean_body_comp` 的 docstring 里同一句口径也一并更正为 Ruling 52 的说法（`:361-364`）。
**没有改任何一行决定「哪一行胜出」的代码**（见 §8.0 第 3 项取证）。

**取证**（`$env:TEMP\t5r2_invariants.py` 第 7 节，运行时原文）：

```
=== 7. Item 2：两条去重 reason 的运行时原文 ===
  [体测] field='*' original='2025-09-04' processed='2025-09-06'
         reason=学号 S1 在批次 2025-2026|week1 上出现多条体测记录，保留输入顺序中靠后的一条
                （tested_on=2025-09-06），丢弃靠前的一条（tested_on=2025-09-04）；
                同批次重复通常来自增量水位线未推进或源系统重传
  [体成分] field='*' original='2025-09-01' processed='2025-09-01'
           reason=学号 S1 在测量日 2025-09-01 上出现多条体成分记录，保留输入顺序中靠后的一条、
                  丢弃靠前的一条；绝不取均值——两条测量的平均值是一个从未被测量过的数。
                  不去重会让落库变成 (student_id, measured_on) 唯一约束下的静默覆盖，无痕可查
  两条都含「输入顺序中靠后的一条」? True
  还有没有「复测/更正以最后一次为准」? False（必须是 False）
  WHOLE_RECORD = '*'
```

shell 复核（`Select-String -Path app\pipeline\clean.py -Pattern '复测/更正以最后一次为准'`）
**零命中**；`-Pattern '输入顺序中靠后'` 命中 6 处（模块 docstring `:27`、`clean_fitness`
docstring `:303`、体测 reason `:322`、`clean_body_comp` docstring `:357`、体成分 reason `:381`、
`_dedup` docstring `:427`），措辞已全部统一。

**覆盖测试**：既有的 `test_duplicate_record_removed_keeping_newer`、
`test_whole_record_constant_is_exported_and_pins_record_level_entries`、
`test_body_comp_deduplicates_keeping_later_row_and_never_the_average` 三条一字未改、仍全绿
（它们钉的是行为不是文案，故措辞更正不会让它们假绿）；`clean_body_comp` docstring 的更正由
§8.0 的运行时取证覆盖。

### 8.3 Item 3（M1）`unit_normalized` 条目的学号回填有测试了

**改了什么**：只加测试，实现未动（`clean.py:336` 的
`entries.append(replace(unit_entry, student_no=record.student_no))` 保持原样）。

**RED 取证（回填失效时，只有新测试变红）**：把那一行临时改成 `entries.append(unit_entry)`：

```
PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q -k "backfilled or counters_exclude or unit_error_height"
E       AssertionError: assert '' == 'S7'
FAILED ...::test_unit_normalized_entry_gets_the_records_student_no_backfilled - AssertionError: assert '' == 'S7'
1 failed, 2 passed, 22 deselected in 0.35s
```

`2 passed` 正是评审指出的缺口：`test_unit_error_height_in_meters_normalized`（只调单参数的
`normalize_height`，本来就期望空学号）与 `test_dropped_and_corrected_counters_exclude_duplicate_removed`
（只断言 `unit_normalized` 这个 kind 存在）在回填彻底失效时**照样全绿**。还原后哈希与备份逐字相同
（`A7FFB161F3E65CB27A47B47E4C40E2572ABD59081EF64D1A99F16394A0CC9365`，两侧一致）。

**覆盖测试**：`test_unit_normalized_entry_gets_the_records_student_no_backfilled` —— 先断言
`normalize_height(1.75)` 单参数返回的条目 `student_no == ""`（钉住「回填是必需的」这个前提），
再断言经 `clean_fitness` 后该条目 `student_no == "S7"`、`field == "height_cm"`、两个值列为
`(1.75, 175.0)`，最后断言 `{e.student_no for e in r.entries} == {"S7"}`（同一条记录产出的
所有条目都不得出现「一条有名、一条无主」）。

### 8.4 Item 4（M2）「越界修正不丢记录」被钉死

**改了什么**：`test_outlier_corrected_and_logged` 原有 3 条断言**一字未削**，其后追加
`len(r.fitness) == 1`、存活值 `== 5.0 == RANGES["sprint_50m_s"].min`、
`survivor == replace(rec(), sprint_50m_s=5.0)`（一条断言同时覆盖其余七个测量列与三个身份列）、
`r.dropped == 0`、以及条目三元组 `[("sprint_50m_s", 3.2, 5.0)]`。测试文件为此新增
`from dataclasses import replace`。

**RED 取证（真的会丢整行时，只有新断言变红）**：把 `clean_fitness` 临时改成「产出过
`outlier_corrected` 就 `continue`、不 append」：

```
PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q -k "outlier_corrected_and_logged"
>       assert len(r.fitness) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = len([])
E        +    where [] = CleanResult(fitness=[], body_comp=[], entries=[CleaningEntry(student_no='S1',
             field='sprint_50m_s', original_value=3.2 ... reason='sprint_50m_s=3.2 超出该指标的合理区间
             [5.0, 15.0]，夹取到最近的区间边界 5.0；只修正这一列，该生本条记录的其余有效项原样保留')],
             dropped=0, corrected=1).fitness
1 failed, 24 deselected in 0.35s
```

注意失败现场自证了评审的论点：`corrected=1` 与条目的 kind/field **全都还是对的**（原有 3 条断言
在 `len(r.fitness)` 之前求值，全部通过），审计条目甚至还在声称「该生本条记录的其余有效项原样
保留」，而该生已经从队列里消失了。还原后哈希与备份一致。

**覆盖测试**：`test_outlier_corrected_and_logged`（加强版）。

### 8.5 Item 5（M3）`_parse_range` 的五道守卫全部有测试

**改了什么**：只加测试，`_parse_range` 的四道既有守卫未动（第五道是 §8.1 新增的）。
测试走 `load_ranges` 全路径而非直接调私有函数：新增 helper `_mutated_ranges(tmp_path, field,
override)`，用 `yaml.safe_load` 读仓库自带的真实 YAML、只覆盖一个字段的一个键、`safe_dump`
到 `tmp_path`，因此键集合校验与字段级校验串在同一条真实加载链上。测试文件为此新增
`import yaml` 与模块级 `RANGES_PATH`（`RANGES = load_ranges(RANGES_PATH)`，加载结果不变）。

7 个参数化用例：

| # | 字段 | 覆盖 | 期望报错片段 |
|---|---|---|---|
| 1 | `height_cm` | `min: 250` > `max: 220` | 区间上下界颠倒 |
| 2 | `height_cm` | `non_positive_is_missing: 1`（int 不是 bool） | 应为布尔值 |
| 3 | `height_cm` | `zero_allowed: "false"`（字符串不是 bool） | 应为布尔值 |
| 4 | `height_cm` | `min: true`（bool 冒充数值） | 应为数值 |
| 5 | `weight_kg` | `max: "150"`（字符串冒充数值） | 应为数值 |
| 6 | `sprint_50m_s` | `non_positive_is_missing` 与 `zero_allowed` 同真 | non_positive_is_missing 为 true |
| 7 | `sprint_50m_s` | `zero_allowed: true` + `min: 5.0`（Ruling 51） | zero_allowed 为 true 时 min 必须 <= 0 |

三条断言对每个用例都成立：期望片段在报错里、**字段名在报错里**、**文件路径在报错里**。

**RED 取证（`min: true` 静默通过正是这套守卫存在的理由）**：把
`if isinstance(value, bool) or not isinstance(value, (int, float)):` 临时改成
`if not isinstance(value, (int, float)):`：

```
PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q -k "malformed"
FAILED ...::test_load_ranges_rejects_malformed_field_configuration[height_cm-override3-应为数值] - Failed: DID NOT RAISE ValueError
1 failed, 6 passed, 18 deselected in 0.46s

PS backend> C:\Python\python.exe -c "... load_ranges(把 height_cm.min 改成 True 的临时 YAML) ..."
min: true 被解析成 -> FieldRange(min=1.0, max=220.0, non_positive_is_missing=True, zero_allowed=False)
```

即：少了 `bool` 排除，`min: true` 静默变成 **1.0**——身高下界从 140 cm 变成 1 cm，任何地方
都不报错。7 个用例中恰好只有第 4 个变红，说明每个用例钉的是各自那道守卫。还原后
`Select-String -Pattern '临时变异'` 计数 **0**、哈希与备份一致。

**覆盖测试**：`test_load_ranges_rejects_malformed_field_configuration`（7 个参数化用例）。
既有的 `test_load_ranges_rejects_unknown_or_omitted_field`（字段名多写/漏写）一字未改。

### 8.6 Item 6（M4）「去重先于清洗」现在有能失败的测试

**改了什么**：`test_dropped_and_corrected_counters_exclude_duplicate_removed` 的输入由
`[rec(), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)]` 改为
`[rec(sprint_50m_s=0.0), rec(height_cm=1.75, vital_capacity_ml=None, sprint_50m_s=3.2)]`
——**被丢弃那一行弄脏**。原有 4 条断言一字未削、取值也不变（`dropped == 1`、`corrected == 2`、
四种 kind 各一、`len(r.fitness) == 1`），另加两条：`all(e.original_value != 0.0 for e in r.entries)`
（被丢弃行的脏值不得在任何条目里留下痕迹）与 `r.fitness[0].sprint_50m_s == 5.0`（存活行的值是
夹取来的 5.0，不是被丢弃那行转出来的 `None`）。实现未动。

**RED 取证（顺序反过来时新测试变红、旧断言全绿）**：把 `clean_fitness` 临时改成「先清洗全部
输入、再对清洗结果去重」，然后用 `$env:TEMP\t5r2_item6_mutation.py` 对同一份实现分别跑
「旧版输入（干净的 `rec()`）」与「新版输入（弄脏）」：

```
########## 变异态：clean_fitness 先清洗再去重 ##########
=== 旧版：被丢弃行是干净的 rec() ===
  kinds = ['duplicate_removed', 'missing_dropped', 'outlier_corrected', 'unit_normalized']
  dropped=1 corrected=2 len(fitness)=1
  [PASS] len(r.fitness) == 1     [PASS] kinds == 四种各一
  [PASS] r.dropped == 1          [PASS] r.corrected == 2
  → 旧断言整体: 全绿（钉不住顺序）

=== 新版：被丢弃行弄脏 rec(sprint_50m_s=0.0) ===
  kinds = ['duplicate_removed', 'missing_dropped', 'missing_dropped', 'outlier_corrected', 'unit_normalized']
  dropped=2 corrected=2 len(fitness)=1
  [PASS] len(r.fitness) == 1     [FAIL] kinds == 四种各一
  [FAIL] r.dropped == 1          [PASS] r.corrected == 2
  → 旧断言整体: 变红（钉住了顺序）
```

pytest 侧同一次变异：

```
PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q -k "counters_exclude"
FAILED ...::test_dropped_and_corrected_counters_exclude_duplicate_removed - AssertionError:
  At index 2 diff: 'missing_dropped' != 'outlier_corrected'
  Left contains one more item: 'unit_normalized'
1 failed, 24 deselected in 0.34s
```

还原后同一脚本两种输入都回到 `dropped=1 corrected=2`、四种 kind 各一——被丢弃那行的 `0.0`
在正确顺序下**从未进入清洗**，一条痕迹都不留。这正是 docstring 里那句「审计于是指向不存在的
数据，比没有审计更糟」的可执行版本。

**覆盖测试**：`test_dropped_and_corrected_counters_exclude_duplicate_removed`（加强版）。

### 8.7 Item 7（M6）抽出 `_dedup`

**改了什么**：新增私有 `_dedup(records, key_of, entry_of) -> tuple[list[_RecordT], list[CleaningEntry]]`
（`clean.py:403-449`），把 `clean_fitness` 与 `clean_body_comp` 里各 ~28 行、近乎逐字重复的
「剔除无法归属 → 去重 → 就地替换」合成一份。两处调用点各自只注入三样差异：去重键第二列
（`batch_key` / `measured_on`）、条目两个值列取哪个日期、`reason` 文字。
`entry_of(discarded, kept)` 的参数序在 docstring 里写死为「被丢弃行在前、保留行在后」。
类型上引入受约束的 `_RecordT = TypeVar("_RecordT", RawFitnessRecord, RawBodyCompRecord)`
（`clean.py:44`）与 `from collections.abc import Callable`，返回类型跟着入参走而不是退化成 `Any`。

**两条 reason 的文本逐字保留**（体测完全未改；体成分只按 §8.2 删掉那半句口径），
`field=WHOLE_RECORD`、两个值列的取值、`survivors[position] = record` 的就地替换语义、
「空学号先于去重」的判定顺序全部照搬，**没有任何行为变化**。

**取证（抽取前后测试数完全相同）**：

```
# 抽取前（Item 1 + Item 8 已落地、_dedup 尚未抽出）
PS backend> C:\Python\python.exe -m pytest -q
192 passed in 0.85s
PS backend> git diff --stat
 backend/app/pipeline/clean.py | 20 +++++++++++++++++++-
 1 file changed, 19 insertions(+), 1 deletion(-)

# 抽出 _dedup + 统一措辞之后（尚未新增任何测试）
PS backend> C:\Python\python.exe -m pytest -q
192 passed in 0.85s
PS backend> git diff --stat
 backend/app/pipeline/clean.py | 184 +++++++++++++++++++++++++++---------------
 1 file changed, 117 insertions(+), 67 deletions(-)
```

**192 → 192，测试数一字未变、全绿**：既有的 16 条 `test_clean.py` 测试（含钉住去重行为的
3 条）在抽取前后都通过，说明这是纯重构。净 −67/+117 行里，减少的是两份重复逻辑，
增加的是 `_dedup` 的 docstring（把「为什么抽出来」「两条顺序为什么承重」「靠后指输入顺序
而非日期」写清楚）与两个调用点的 lambda。

`Select-String -Pattern '_dedup'` 复核最终只有 1 个定义 + 2 个调用点：

```
43:  # 列），用受约束的 TypeVar 让 :func:`_dedup` 的返回类型跟着入参走，而不是退化成 Any。
311: survivors, entries = _dedup(
370: survivors, entries = _dedup(
403: def _dedup(
```

**覆盖测试**：不新增测试（纯重构）。既有 3 条去重测试 + §8.6 加强后的 counters 测试
+ §8.0 第 3/4/5 项运行时取证共同覆盖两条路径。

### 8.8 Item 8（M8）可见性一致

**改了什么**：`KNOWN_MEASURE_FIELDS` → `_KNOWN_MEASURE_FIELDS`（`clean.py:79`），唯一引用点
`load_ranges` 内同步改名（`:179`）。上方 5 行注释写明理由：它只被 `load_ranges` 用于键集合
校验、外部无消费方，故与同为加载期内部细节的 `_RANGE_KEYS` 保持一致的可见性；
`FITNESS_MEASURE_FIELDS` / `BODY_COMP_MEASURE_FIELDS` **保持导出**（Task 10 落库与架构测试
都可能要这份「哪些列是测量列」的清单）。

**取证**：

```
PS backend> Select-String -Path app\pipeline\clean.py,tests\pipeline\test_clean.py -Pattern 'KNOWN_MEASURE_FIELDS'
clean.py:79: _KNOWN_MEASURE_FIELDS: frozenset[str] = (
clean.py:179: known = _KNOWN_MEASURE_FIELDS

# 运行时复核（§8.0 第 6 节）
  体测测量列 8 + 体成分 3 = 私有并集 11；== ranges 键集合 ? True
  模块还有没有导出的 KNOWN_MEASURE_FIELDS ? False（必须是 False）
```

全仓 grep 确认改名前也只有 `clean.py` 内部 3 处引用（`:74`、`:75`、`:169`），无外部消费方；
架构测试 `tests/architecture/test_domain_purity.py` 只扫 `app/domain/`，与本项无关，未受影响。

**覆盖测试**：无需新增（改名不改行为）。全量 201 passed 即为证；另有 §8.1 测试里的
`len(RANGES) == 11` 与 §8.0 的 `set(RANGES) == set(_KNOWN_MEASURE_FIELDS)` 运行时核对。

### 8.9 控制方判定「不改」的两项

**M7**（NaN 穿过 `sit_and_reach_cm`）与 **M9**（§7.6 的行号与逐文件插入数不一致）本轮
**一字未动**：`_clean_measure` / `_placeholder_reason` 未新增任何有限性检查，本报告 §7.6
原文未回填修正。

### 8.10 命令与输出汇总

```
PS> git log --oneline -3
67a20fd docs: Ruling 52 要求 Task 6 的 duplicate 注入逐字复制整行
325c332 docs: Ruling 50 更正 field 取值分类，消除与 Ruling 47 的文本冲突
79daed8 fix: 清洗层补齐记录级处置——空学号整条剔除、体成分去重、身高舍入
PS> git status --short
（空，工作区干净）

PS backend> C:\Python\python.exe -m pytest -q                        # 修复前基线
192 passed in 0.85s

PS backend> C:\Python\python.exe -m pytest tests/pipeline/test_clean.py -q
25 passed in 0.38s                                                   # 16 → 25

PS backend> C:\Python\python.exe -m pytest -q
201 passed in 0.92s
PS backend> C:\Python\python.exe -m pytest -q -W error
201 passed in 0.92s
PS backend> C:\Python\python.exe -m pytest -q                        # 全部变异还原后复跑
201 passed in 0.92s
PS backend> C:\Python\python.exe -m pytest -q -W error
201 passed in 0.88s

PS backend> git diff --stat
 backend/app/pipeline/clean.py        | 184 ++++++++++++++++++++++-------------
 backend/tests/pipeline/test_clean.py | 141 +++++++++++++++++++++++++--
 2 files changed, 250 insertions(+), 75 deletions(-)
```

**192 → 201（+9）**，`-W error` 下同样 201 passed，输出无 warning / skip / xfail。
既有 192 条中只有 2 条被改动（§8.4、§8.6，均为**追加断言**，原断言一字未削、期望值未变），
其余 190 条一字未动。

### 8.11 写盘核验

每次编辑后都用 shell 确认字节落盘，未依赖编辑器复读：`git diff --stat`（逐次记录于上文）、
`Select-String` 定位改动行（`79: _KNOWN_MEASURE_FIELDS`、`239: if raw["zero_allowed"] and
raw["min"] > 0:`、`311/370: survivors, entries = _dedup(`、`403: def _dedup(`、
`494/508/520` 三段顺序），以及每次变异还原后的 `Get-FileHash` 比对
（`A7FFB161F3E65CB27A47B47E4C40E2572ABD59081EF64D1A99F16394A0CC9365`，工作区文件与 `$env:TEMP`
备份逐字相同）+ `Select-String -Pattern '临时变异'` 计数 **0**。逐字节核对编码：

```
app\pipeline\clean.py        bytes=31096 BOM=False 含CRLF=False
tests\pipeline\test_clean.py bytes=19312 BOM=False 含CRLF=False
```

两文件仍为 UTF-8 **无 BOM** + LF，与 §4 / §7.6 记录的状态一致。三个临时脚本
（`t5r2_item1_counterfactual.py`、`t5r2_item6_mutation.py`、`t5r2_invariants.py`）与两份备份
全部写在 `$env:TEMP`，跑完 `Remove-Item`，未进入仓库。

### 8.12 本轮关注点

按报告要求，凡写进代码注释 / docstring / 测试注释的 caveat 全部在此列出：

**R1（写在 `_dedup` docstring 里）「去重先于字段级清洗」这条顺序不由 `_dedup` 自己保证，
而由调用方保证。** `_dedup` 只负责「无法归属的先剔除、然后去重」；「清洗发生在 `_dedup`
返回之后」是两个调用方的结构决定的。抽取把这段逻辑集中了，但也把这个不变量从「写在同一个
函数体里、一眼可见」变成了「跨函数的调用顺序约定」。目前的保障是 §8.6 那条能真正失败的测试
（顺序一反，`dropped` 与 kinds 同时变红）；若将来有人在 `_dedup` 内部加清洗，那条测试会拦住。

**R2（写在 `_dedup` 与 `clean_body_comp` docstring 里）「靠后」是输入顺序而非日期，体测路径上
胜出行的 `tested_on` 可能更早。** 这不是本轮引入的，是 Ruling 52 要求把措辞说准之后必须在
文档里写明的事实。§8.0 第 3 项已实测：`[2025-09-06, 2025-09-04]` 胜出的是 `2025-09-04`。
控制方已另行裁定 Task 6 的 `duplicate` 注入逐字复制整行，故原型数据里不会出现两行日期不同；
但**真实乐跑数据没有这个保证**，`cleaning_log` 的读者需要能从 `reason` 里看出这一点。

**R3（写在 `_KNOWN_MEASURE_FIELDS` 注释里）导出面的取舍：** 并集转私有，
`FITNESS_MEASURE_FIELDS` / `BODY_COMP_MEASURE_FIELDS` 保持导出。若 Task 10 或架构测试其实
需要「全部测量列」这一份并集，把它改回导出名是一行改动——但那时它就是**有消费方的**导出，
与现在不同。

**R4（写在 §8.1 守卫上方注释与测试注释里）`min: true` 会被静默解析成 `1.0`**，这是实测结果
（`FieldRange(min=1.0, max=220.0, ...)`），不是推测。整套类型守卫的存在理由就是它；
参数化用例 #4 钉住。

**R5（未做，超出本轮范围）`backend/data/indicator_ranges.yaml` 的头注释没有同步 Ruling 51。**
该文件 `:7-8` 目前只写了「`non_positive_is_missing` 为 true 时 `zero_allowed` 必须为 false，
两处矛盾 `load_ranges` 会响亮报错」，没有提新增的第二条约束（`zero_allowed` 为 true 时
`min` 必须 <= 0）。本轮任务书说明八项改动全部落在两个文件里，故未触碰 YAML；但这份文件的
读者正是体育测量学专家本人，**他们看不到 `clean.py` 里的守卫**。建议控制方裁定是否追加一行
头注释（例如在 `:8` 之后加「`zero_allowed` 为 true 时 `min` 必须 <= 0，否则 0 会被夹到 `min`，
对越小越好的项等于送满分；两处矛盾 `load_ranges` 都会响亮报错」）。这是纯文档改动，
不影响任何测试。

**R6（文档冗余，未处理）`clean_fitness` 的 docstring 与 `_dedup` 的 docstring 现在都解释了
「空学号先于去重」与「先去重再清洗」。** 抽取时有意保留了公共函数 docstring 的原文（评审已
核对其正确，不想在重构里顺手改写已验证的内容），代价是同一段理由有两份。若控制方偏好单一
出处，可把 `clean_fitness` docstring 的那两段压成一句「记录级处置见 `_dedup`」。

**R7（测试文件 docstring 已写明）两处与计划 Step 1 原文的偏差**：
`test_outlier_corrected_and_logged` 与 `test_dropped_and_corrected_counters_exclude_duplicate_removed`
不再是 Step 1 的逐字副本——前者追加了 5 条断言，后者的输入被改脏并追加 2 条断言。两处都是
**加断言而非削断言**，原断言的期望值一字未变（§8.4 / §8.6 已逐条列出）。计划 Step 5 的
「16 passed」预期在本轮后应更新为 **25 passed** = 原 16 + Ruling 51 专项 1 + M1 学号回填 1 +
M3 参数化守卫 7；全量 201 = 原 176 + 25。

**R8（口径不变，仅重申）** §2 的 `dropped` / `corrected` / `duplicate_removed` 三口径本轮
一字未动；§6 的 C4 / C5 / C8 由控制方判定不改，本轮同样未动（`_placeholder_reason` 的分支
结构、YAML 的四键形状、`load_ranges(path)` 的无默认路径签名均未出现在 diff 的行为改动里）。
§7.8 的 F1–F5 全部保持原状，其中 F2（体成分 `duplicate_removed` 的两个值列必然是同一天）
在 `_dedup` 抽取后依旧成立，`clean_body_comp` docstring 里的那段「注」原样保留。

