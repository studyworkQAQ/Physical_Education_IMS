# Task 10 报告：每日批处理编排与幂等重放

**状态：DONE_WITH_CONCERNS**
**commit：`31d8f3a`**（分支 `feature/plan-01-data-foundation`，基线 `47f000c`，单个 commit，工作树干净）
**测试数：396 → 416 passed / 0 error**（`pytest -q` 不带 flag 也能跑；`-W error` 洁净）

> 简报与计划都写「396 → 398」。实测 416，差额逐条列在**关切 1**——398 只算了 Task 9 那 2 条集成测试转绿，漏了 `test_daily.py` 自己的 9 条与 Step 0 各小节必需的新测试。

---

## 1. Step 0 七个小节的逐条落地证据

### 0.1 `models.py` 的 `hit_rules` docstring（Ruling 130/132/125）——**DONE**

改的文件与行：`backend/app/db/models.py`，`StratificationResult` 的类 docstring（原 `:421-427`，现 `:430-448`）。

| 旧文 | 新文 |
|---|---|
| 「**7 条规则**命中即停」 | 「**Z0 闸门 + 7 条分层规则**自上而下求值、命中即停」 |
| 「`insufficient_data` 时**为空串**」 | 「`insufficient_data` 时 `hit_rules` **恰为 `"Z0"`**，任何路径都至少有一项」+ 明写 `explain()` 按 `hit_rules[-1]` 取文案、空串会 `IndexError`（Task 9 已用变异实证） |
| （无） | 新增 Ruling 132 的前缀语义整段：Z0 命中 → `("Z0",)` 只有这一项；Z0 未命中 → 已评估的 7 条分层规则序列、最后一项即命中者、**不含 Z0** |

**实测行为**（读生产状态：跑完 `run_daily` 之后直接查 `stratification_result`）：

- 60 人整批（`D = 2025-09-15`）落库的 `hit_rules` 全部取值与人数：
  `"R1"`×6、`"R1,R2"`×1、`"R1,R2,Y1"`×14、`"R1,R2,Y1,Y2"`×7、`"R1,R2,Y1,Y2,Y3"`×7、
  `"R1,R2,Y1,Y2,Y3,Y4"`×1、`"R1,R2,Y1,Y2,Y3,Y4,G1"`×24、`"Z0"`×60（该库先跑过一次
  `D = 2024-09-01` 的空批，故 Z0 那 60 行是早于本批的另一日）。
- **Z0 行的 `hit_rules` 恰为 `"Z0"`、零空串**：`sorted({r.hit_rules for r in rows if r.label == "insufficient_data"}) == ["Z0"]`。
- 拆开后 `[-1]` 可取且能构造成 `RuleId`：`RuleId("Z0".split(",")[-1]).value == "Z0"`（`explain()` 正是这么取的）。
- **最长取值实测 20 字符**（`"R1,R2,Y1,Y2,Y3,Y4,G1"` = 7 个两字符 ID + 6 个逗号），列宽 `String(128)` 充裕。计划写的「实测最长 23 字符」是把 Z0 算进了前缀，与 Ruling 132 矛盾——见**关切 3**，我按 20 写进 docstring。

### 0.2 肌肉量 P20 的生产者（Ruling 102 + 121，阻塞项）——**DONE**

四步全部落地：

1. **不动 `ScoredItem`**。在 `backend/app/domain/percentile.py` 新增 `SnapshotMetric`（函数式 `Enum(..., type=str)`，成员表**从 `ScoredItem` 派生**而不是手抄第二份 7 行清单，再并上 `EXTRA_METRICS = ("muscle_mass_kg",)`）。`PercentileRow.item` 的类型与 `compute_snapshot` 的分组键 `groups: dict[tuple[Sex, str, SnapshotMetric], list[float]]` 都改用它。ORM 无需改（`percentile_snapshot.item` 已是 `String(32)`）。
   - 跨枚举相等实测成立（`SnapshotMetric` 是 `str` 混入）：`SnapshotMetric.SPRINT_50M == ScoredItem.SPRINT_50M` → `True`，`SnapshotMetric("bmi") == ScoredItem.BMI` → `True`，故 `lookup_p25` 的 `==` 比较一行都没改，调用方传哪一种枚举都命中同一行。
   - `[m.value for m in SnapshotMetric]` 实测 = `['bmi', 'vital_capacity', 'sprint_50m', 'sit_and_reach', 'standing_jump', 'pull_up_or_sit_up', 'distance_run', 'muscle_mass_kg']`。
2. **同步改入口校验**：`compute_snapshot` 里的 `_validated_member(ScoredItem, row["item"], ...)` → `_validated_member(SnapshotMetric, ...)`。不改的话肌肉量行在入口就被拒（Task 8 实现者的关切 D 预警过）。
3. **给 `percentile_snapshot.item` 补 `_in_domain` CHECK**：`models.py` 新增类常量 `PercentileSnapshot.ITEMS`（8 个值）+ `_in_domain("item", ITEMS, "ck_percentile_snapshot_item")`。取值域与 `SnapshotMetric` 的一致性由新增测试 `tests/db/test_models.py::test_percentile_snapshot_item_domain_matches_snapshot_metric` 钉住（与 `Student.SEXES` ↔ `Sex` 同一条处置：db 层不 import domain，靠漂移测试）。脏值拒收由 `tests/db/test_repo.py` 的 `_CHECK_CONSTRAINTS` 新条目 `percentile_snapshot.item`（脏值 `body_fat_pct`）覆盖——那条参数化测试从九条变十条。
4. **肌肉量无常模可降级**：`compute_snapshot` 里 `len(group) < MIN_SAMPLE and item.value in EXTRA_METRICS` → `continue`（整组不产出行）；`national_norm` 入口加了显式 `ValueError` 守卫（否则退化成 `segment_thresholds` 的 `KeyError`，消息只有那个三元组，看不出「肌肉量根本没有常模」这个真因）。**没有新增第三个 `reasons` token**（Ruling 97① 冻结 vocabulary）；留痕走 `DailySyncRun.error_summary` 的「缺线组数」——见**关切 9**。

**两条口径按裁定实现**：

- **样本单位是学生**：`run_stratify.cohort_snapshot` 对每人**最多产出一行**肌肉量样本，取该生 `<= business_date` 的最新一条体成分（`percentile_stage._latest_body_comp` 按 `measured_on` 升序遍历、后写覆盖）。
- **喂清洗后的值**：内存路径 `_from_dataset` 先过 `clean_body_comp`；DB 路径读的是 `body_composition` 表，而那张表只由 `_load_sources` 经 `clean_body_comp` 之后写入。

**肌肉量 P20 四组实测值与四组样本量**（读生产状态：500 人**零注入**、`D = 2025-09-15`、跑完 `run_daily` 之后直接查 `percentile_snapshot WHERE item = 'muscle_mass_kg'`）：

| 组 | P20 (kg) | sample_size | source |
|---|---|---|---|
| `male\|大一、大二` | **33.20** | **156** | school |
| `male\|大三、大四` | **33.56** | **119** | school |
| `female\|大一、大二` | **23.70** | **119** | school |
| `female\|大三、大四` | **23.60** | **106** | school |

四个值与计划 0.2 / `golden_cases.json` 的 `muscle_p20_by_group` **逐字相同**（33.20 / 33.56 / 23.70 / 23.60）。四个 sample_size 之和 = 500 ✓（每人恰好一行）。

**两种口径的差异实测**（对照 Ruling 121「差 0.2 kg 就足以翻十几个人的 C」）：把同一次运行后的 `body_composition` 表**重新聚合**成「测量行级」（每人 4 条 `<= D` 的记录都当独立样本，这一段是**我重新推导的输入**、不是生产状态，故只作对照）：`male|大一、大二` **33.00**（n=624）、`male|大三、大四` **33.50**（n=476）、`female|大一、大二` **23.10**（n=476）、`female|大三、大四` **23.10**（n=424）。男生两组各差 0.20 / 0.06 kg，女生两组各差 0.60 / 0.50 kg。计划写的「测量行级 male 33.10 / 33.40」与我实测的 33.00 / 33.50 不同，推测是聚合的记录集合不同（我用的是全部 `<= D` 的 4 个时点）——**学生级那四个值是生产状态、可复现；测量行级那一组是重新推导的，只用来证明「口径确实会改数值」**。

**缺省注入下的四组**（同一套生产路径，`SeedConfig(students=500)` 缺省 dirty）：`male` **33.14**（n=143）/ **33.44**（n=115）、`female` **23.70**（n=112）/ **23.60**（n=102）；四组之和 472 < 500，差额 28 人在「最新那条 `<= D` 的体成分」上 `muscle_mass_kg` 是 `None`，故 `cohort_snapshot` 不为他们入样。`None` 只可能来自缺测注入：`clean_body_comp` 的另外三支都保留值（越界是夹取到边界、量纲是归一、重复是整行替换成活下来的那一行），这是从 `clean.py` 的代码读出来的推论、不是又一次测量。

**60 人（测试 fixture 那一组）**：四个组的肌肉量样本都 < 30 → **0 行肌肉量快照**，`snapshot` 共 28 行（7 个计分项 × 4 组，全部 `source = "national"`），`DailySyncRun.error_summary` 实测写下「注意（非错误）：4 个 (性别 × 年级组) 组没有肌肉量 P20 判定线……」。

### 0.3 `percentile_source` 的生产者（Ruling 120/137，阻塞项）——**DONE**

- `app/domain/percentile.py` 新增 `lines_used(curr, snapshot, sex, age_group) -> list[PercentileRow]`（判据与 `find_weaknesses` 逐字同构：只遍历 6 个短板判定项，且要求「有得分」**且**「该组有快照行」）与 `summarize_source(rows) -> str`。三条口径全部由「用过哪些行」这一个输入决定：`sources == set()` → `"none"`；否则 `"national" if "national" in sources else "school"`（任一项降级即 national）。
- `models.py`：`PERCENTILE_SOURCES` 从 `{"school","national"}` 扩成 `{"school","national","none"}`，`ck_stratification_result_percentile_source` 由 `_in_domain` 从类常量生成、自动跟上（实测 DDL = `percentile_source IN ('national', 'none', 'school')`）。列宽 `String(8)` 够（最长 `"national"` = 8）。
- 生产者接线：`run_stratify.percentile_source_of`，`daily.py` 落库时调用；`input_snapshot` 里也存了一份 `percentile_source`。
- **两处一致性有测试**：`lines_used` 的行数恒等于 `find_weaknesses(...).valid_count`（新增 `test_lines_used_count_equals_valid_count`，抽掉一组判定线后两边同时 −1）；`summarize_source` 的值域恒 ⊆ `PERCENTILE_SOURCES`（新增 `test_percentile_source_domain_covers_the_producer_codomain`）。

**实测取值分布**（读生产状态）：

| 场景 | `percentile_source` 分布 |
|---|---|
| 500 人零注入、`D=2025-09-15` | `school` × 500 |
| 500 人缺省注入、`D=2025-09-15` | `school` × 500 |
| 60 人缺省注入、`D=2025-09-15` | `national` × 60（四个组样本都 < 30 → 全部走国标兜底） |
| 60 人、`D=2024-09-01`（早于任何采集日，整批无数据） | **`none` × 60** |
| 500 人缺省注入里那 2 个 Z0 学生 | `valid_count = 3` → **`school`**（Ruling 137 第二条：用过 1–3 行按实际用过的行汇总，不是 `none`） |

**`"none"` 确实出现过**，且只在 `valid_count = 0` 时出现（`D = 2024-09-01` 那一批：60 人全部 `insufficient_data`、`hit_rules = "Z0"`、`snapshot` 0 行、七元组 `(60, 60, 0, 0, 0, 0, 0)`、`status = "success"`）。

### 0.4 `stratify.py` 的 `reason` 措辞（Ruling 134）——**DONE**

`backend/app/domain/stratify.py` 的 `_REASON`（现 `:168-179`）：

- `RuleId.Y3`：`"短板 ≥2 项且体成分正常"` → **`"短板 ≥2 项且体成分未判为异常"`**
- `RuleId.G1`：`"无短板且体成分正常"` → **`"无短板且体成分未判为异常"`**
- `RuleId.Y2`（`"无短板但体成分异常"`）与 `RuleId.R1`（`"短板 ≥2 项且体成分异常"`）**不含「正常」表述，未改**。
- 同时补了一段注释说明理由（`C = False` 在 Ruling 97③ 下包含「数据缺失所以无从判定」，短文案进日志与教师大屏列表，比长文案更自信地说「正常」是危险的）。

**只改字符串常量，逻辑一行未动**（`git diff --stat` 显示 `stratify.py` 只有 11 行变化，全在注释与那两行字面量上）。

**「同步更新断言 `reason` 全文的测试」→ 实际零处需要改**：`tests/domain/test_stratify.py` **一字未改**（`git diff` 该文件为空），因为 18 条测试里没有一条断言 `reason` 全文——它们断言的是 `label` / `hit_rules` / `explain()` 里的子串（`"体脂率"`、`"22.4"`、`"20%"`、`"28%"`、`"女"`、`"数据不足"`），没有一个含「体成分正常」。全仓 grep `体成分正常` 现在只剩 `golden_cases.json` 的四处 `expected[].reason` ——见**关切 5**。

### 0.5 补 Ruling 110 那条测试（形态 6）——**已存在，零改动**

`tests/domain/test_derive.py::test_derive_rejects_prev_total_with_a_missing_prev_value` **已经在仓里**（`:602-618`，属基线 396 条之一），而且已经按硬规矩 #15 指明了是哪一道守卫：

```python
prev = seven(70); prev[I.BMI] = None
assert national_total(prev) is None                     # 前提：总分合法地不可得
with pytest.raises(ValueError) as exc:
    derive(seven(80), prev, national_total(seven(80)), 70, 1.0, ...)
assert "同真同假" in str(exc.value)
```

它的注释里已经写明「形态 6 现在被**两道**守卫拦下——Ruling 106 的 None-ness 对称校验，与 Ruling 118-M1 的值校验……只断言 ValueError 的话，砍掉任一道另一道仍会拦住，本条就**不可伪证**（空转）。断言消息把它钉在 None-ness 那一支上」。单跑实测 PASS。详见**关切 2**。

### 0.6 `business_date` 与 `since` 分家 + week1-vs-week1（Ruling 140）——**DONE**

`backend/app/pipeline/extract.py` 的模块 docstring 逐条写了裁定与被否决的读法；`percentile_stage.assessment_anchor` / `run_stratify.YEAR_STEP` 各写了同一口径。

- **`since = 上一次成功运行的 business_date`**（`previous_watermark`：`status == "success"` 且 `business_date < 本批`，取最大者；查不到 → `None` = 全量）。**不按 `semester_id` 过滤**（水位线是数据源的属性，契约里 `fetch_*` 也没有学期参数）。**同日重跑时那一天自己的运行记录不算水位线**（`< D` 为假），故两次运行拿到逐字相同的 `since` → 抽到同一批记录 → 幂等；`status = "failed"` 的运行也不推进水位线。
- **取回后本地按 `<= business_date` 过滤**（`_not_later_than`，两侧都是 `date` 对象，不用字符串字典序）。**晚于 `business_date` 的记录一律不进本批。**
- **趋势对比取每学年的 `week1`、`years = 1.0`**（`assessment_anchor` 只选 `timepoint == "week1"` 的批次、降序取头两个；`cohort_from_db` 的 `years` 恒为 `YEAR_STEP = 1.0`，无历史时也是 1.0 而不是 0，Ruling 123）。被否决的读法（「两条最新记录」→ `years ≈ 0.71` → Ruling 114 的年均口径把趋势放大 1.4 倍、且与 `trend_label` 永不可比）写进了 `run_stratify.YEAR_STEP` 的注释。

**实测**（读生产状态，60 人缺省注入）：

| 量 | 实测 |
|---|---|
| 首日 `extract(since)` | `since = None`（全量） |
| `D = 2025-09-15` 的 `extracted_fitness` | **2000**（500 人组）/ 240（60 人组）= 人数 × **4** 个时点，即上学年 `2024-09-02 / 2024-10-21 / 2024-12-16` + 本学年 `2025-09-01`；**不是** ×6（那会把 `2025-10-20 / 2025-12-15` 这两个晚于 `D` 的时点放进来） |
| `D = 2025-09-16` 的 `since` | **`"2025-09-15"`** |
| `D = 2025-09-16` 的抽取条数 | `(0, 0, 0)` → 百分位阶段跳过、快照行数不变（28）、`computed_on` 仍只有 `2025-09-15` |
| `input_snapshot["years"]` 的全部取值 | `{1.0}` |
| 趋势分布 vs 生成器配额（60 人**零注入**） | **逐人相同**（60/60），分布 `{持续下滑:12, 波动大:9, 稳步提升:15, 稳定:24}` = `allocate_quota(trend_mix, 60)` |

**白得的那条端到端交叉验证成立**：500 人零注入跑完管道后，`derived_metrics.trend` 的分布 = **`{持续下滑:100, 波动大:75, 稳定:200, 稳步提升:125}`**，与生成器真值 `trend_label` 的配额**逐类相等**（详见 §4）。

### 0.7 其余 12 条前向约束——**逐条 DONE**

| # | 约束 | 落地位置与实测 |
|---|---|---|
| 1 | `derive` 是 11 参数、`age_group` 在第 9 位 | `run_stratify.evaluate` **全部按关键字传参**（不按位置），`PersonInputs` 的字段顺序与 `derive` 的参数顺序一一对应并在 docstring 里点名第 9 位 |
| 2 | 上学年用 `age_group_of(age - 1)` | DB 路径：`daily._load_sources` 按 `age_group_of(age_at(birth, 本学年开学日) - years_back)` 正查得分（`years_back` = 本学年开学年 − 该批次所属学期开学年）；内存路径：`_from_golden_cases` / `_from_dataset` 用 `prev_age_group = age_group_of(age - 1)`。`age_at` 与 `population.birth_date` 严格互逆（实测 60 人零注入趋势逐人对账 60/60，龄组错一个就对不上） |
| 3 | 无历史时 `years` 传 **1.0 不是 0** | `cohort_from_db` / `_from_dataset` 的 `years` 恒为 `YEAR_STEP = 1.0`；实测 `input_snapshot["years"]` 全部取值 = `{1.0}` |
| 4 | 不得自行算总分 | `national_total` 是唯一入口：落库 `total_score` 用它（`daily._load_sources`），内存路径的 `curr_total` / `prev_total` 也用它；DB 路径的 `derive` 输入取**落库的** `total_score`，于是 Ruling 118-M1 的值校验真的在对账「落库总分」与「落库七项得分」，不是空转 |
| 5 | 快照不需预筛 | `evaluate` 把整张快照（500 人时 32 行）原样传给 `derive`，由 `find_weaknesses` → `lookup_p25` 三元过滤 |
| 6 | 喂 `compute_snapshot` 的必须清洗后、每 `(学生, 项目)` 一行 | `cohort_snapshot` 逐人逐项最多一行；`score is None` 的行**不传进去**（`if score is None: continue`）；肌肉量每人最多一行。清洗由 `clean_fitness` / `clean_body_comp` 完成（内存路径显式调，DB 路径经 `_load_sources`） |
| 7 | 去重键 `(student_no, batch_key)` / `(student_no, measured_on)` | 不自己实现去重，一律交给 Task 5 的清洗层；落库幂等键与之一致：`FitnessTestResult` 用 `("test_batch_id", "student_id")`、`BodyComposition` 用 `("student_id", "measured_on")`、`InterestSurvey` 用 `("student_id", "semester_id", "filled_on")` |
| 8 | 历史缺测走 `INSUFFICIENT` 是合法状态 | 无任何前置特判：`cohort_from_db` 遍历 **`student` 表的每一个人**（不是「本批抽到记录的人」），无 curr 记录 → `empty_scores()`（七键全 `None`）→ `valid_count = 0` → Z0；无 prev 记录 → `prev_scores = None`。实测 500 人缺省注入下 2 人走 Z0、209 人趋势 `INSUFFICIENT`，全部正常落库 |
| 9 | 补一例 `muscle_low` 黄金用例 | `golden_cases.json` 新增 **GC13**（男 19 岁、体脂率 16.0% < 20% 阈值故第一支不成立、肌肉量 30.0 kg < 该组 P20 33.2 kg 故第二支成立 → `C=True`、`reasons=("muscle_low",)`、W=0 → **Y2 黄**、`hit_rules = ["R1","R2","Y1","Y2"]`）。与 GC11 逐项相同、只改体成分两列（GC11 体脂率恰在 20.0% 阈值上 → `C=False` → 绿），配对钉住「肌肉量单独就能把一个人从绿升黄」。13 人仍全部 < `MIN_SAMPLE=30`，故 P25 判定线不受影响（全走 `national_norm`，其值只依赖 `(item, sex, age_group)` 与注入的评分表，与样本量无关）；**GC01–GC12 的 `expected` 与 `input` 逐字未改**（§8 有取证）。集成测试实测 PASS |
| 10 | green 只剩 0.4 点余量时先怀疑 P20 口径 | 未放宽容差。`test_target_layer_distribution_within_tolerance` 实测 PASS，跑的是**有线**那一组（内存路径 500 人缺省注入：red 19.0 / yellow 46.6 / green **34.0** / insufficient 0.4，green 距下界 30% 有 4.0 点余量）；而 Ruling 128 那组「有线 22.0/47.6/30.4」我在**零注入**下逐字复现（§5） |
| 11 | `age_group` 非法组名会 `ValueError` | 只传 `age_group_of(...)` 的产物，取值恒在 `AGE_GROUPS` 内；实测 `input_snapshot["age_group"]` 只有 `"大一、大二"` / `"大三、大四"` 两种 |
| 12 | `snapshot_muscle_p20` 由快照查得 | `run_stratify.resolve_muscle_lines` 是**唯一**回填口（内存路径与 DB 路径共用），内部调 `lookup_p20`；黄金用例路径按夹具的自述用手工给定值（13 人 < 30，肌肉量组不产出行，查表只会得 `None`，而 GC13 要测的正是「有这条线时 `C` 成立」） |

---

## 2. Step 2 的 RED 输出（逐字）

```
$ cd backend ; python -m pytest tests/pipeline/test_daily.py -v --continue-on-collection-errors
=================================== ERRORS ===================================
________________ ERROR collecting tests/pipeline/test_daily.py _________________
ImportError while importing test module '...\backend\tests\pipeline\test_daily.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\pipeline\test_daily.py:24: in <module>
    from app.pipeline.daily import run_daily
E   ModuleNotFoundError: No module named 'app.pipeline.daily'
=========================== short test summary info ===========================
ERROR tests/pipeline/test_daily.py
============================== 1 error in 0.38s ===============================
```

（落测试文件时先量过：`tests/pipeline/test_daily.py` 6969 bytes、9 个 `def test_`。）

基线也复量过（`git rev-parse HEAD` = `47f000cca489924734878bd77bf1a6f7671f7053`，工作树干净）：

```
$ python -m pytest -q --continue-on-collection-errors
396 passed, 1 error in 12.32s
ERROR tests/integration/test_golden_cases.py
E   ModuleNotFoundError: No module named 'app.pipeline.run_stratify'
```

**Step 0 落地后、`run_stratify` 之前**的中间态也量过一次（这是 0.2 强制改既有断言的那一次实测）：

```
1 failed, 395 passed, 1 error in 10.89s
FAILED tests/domain/test_percentile.py::test_compute_snapshot_rejects_an_unknown_sex_or_item_with_the_row_index
  - Failed: DID NOT RAISE ValueError
  bad_item[7]["item"] = "muscle_mass_kg"     ← 落地 0.2 后它已是合法 SnapshotMetric
```
处置见**关切 6**。

---

## 3. Step 5 的 GREEN 输出（逐字）

```
$ cd backend ; python -m pytest tests/pipeline/test_daily.py -q
..........                                                               [100%]
10 passed in 9.97s
```

**是 10 条不是计划写的 9 条**：Step 1 的 9 条逐字照抄（断言一字未改），另加 1 条 `test_trend_matches_the_generator_oracle_on_week1_anchors`。理由与实测依据见**关切 7**（变异 ③ 在计划的 9 条下不会让任何断言变红）。

Task 9 那 2 条集成测试转绿：

```
$ python -m pytest tests/integration/test_golden_cases.py -v
tests/integration/test_golden_cases.py::test_golden_cases_match_expected_labels PASSED [ 50%]
tests/integration/test_golden_cases.py::test_target_layer_distribution_within_tolerance PASSED [100%]
============================== 2 passed in 1.02s ==============================
```

---

## 4. Step 6 的全量输出（逐字）

**不带 flag**（收集错误已消失）：

```
$ cd backend ; python -m pytest -q
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 52%]
........................................................................ [ 69%]
........................................................................ [ 86%]
........................................................                [100%]
416 passed in 21.12s
```

**`-W error`**：

```
$ python -m pytest -q -W error
416 passed in 24.94s
```

**0 error / 0 warning / 0 failed。** 396 → **416**（+20），逐条归属：

| 来源 | 条数 |
|---|---|
| `tests/pipeline/test_daily.py`（Step 1 的 9 条） | 9 |
| `tests/pipeline/test_daily.py`（本 Task 补的趋势真值对账，关切 7） | 1 |
| `tests/integration/test_golden_cases.py`（Task 9 的 2 条由 ImportError 转绿） | 2 |
| `tests/domain/test_percentile.py`（0.2 三条 + 0.3 两条） | 5 |
| `tests/db/test_models.py`（0.2 取值域漂移 + 0.3 值域覆盖生产者值域） | 2 |
| `tests/db/test_repo.py`（`_CHECK_CONSTRAINTS` 新增 `percentile_snapshot.item` 一个参数化条目） | 1 |
| **合计** | **20** |

---

## 5. 幂等取证（同业务日期重跑两次）

**500 人零注入、`D = 2025-09-15`、连跑两次**（读生产状态：`_counts()` 的七元组 = `DerivedMetrics / StratificationResult / CleaningLog / FitnessTestResult / BodyComposition / InterestSurvey / PercentileSnapshot`）：

```
first  = (500, 500, 0, 2000, 2000, 1000, 32)
second = (500, 500, 0, 2000, 2000, 1000, 32)
identical = True
daily_sync_run 行数 = 1        （两次的 run.id 都是 1，即 upsert 命中同一行）
```

**逐字相同** ✓。三张派生表 500/500/32、三张源表 2000/2000/1000（= 500 人 × 4 个 `<= D` 的时点 / × 4 / × 2 份问卷）、`CleaningLog` 0（零注入 ⇒ 无剔除无修正）。

其余幂等证据：

- 测试层：`test_rerun_same_business_date_is_idempotent`（七元组 + `DailySyncRun` 行数 == 1）、`test_labels_are_reproducible_across_reruns`（`(student_id, label)` 集合逐人相同）、`test_rerun_same_day_does_not_wipe_percentile_snapshot`（Ruling 32）全部 PASS。
- 次日：`D = 2025-09-16` 时 `since = "2025-09-15"`、抽取 `(0,0,0)`、快照行数 28 不变、`computed_on` 仍只有 `2025-09-15`、`daily_sync_run` 3 行、`stratification_result` 180 行（60 × 3 日）、第二日 `status = "success"`。
- 失败回滚：`test_failure_rolls_back_whole_batch` PASS（monkeypatch `app.pipeline.daily.stratify` 抛 `RuntimeError` → 异常原样重抛、七元组全 0）。

---

## 6. 端到端趋势分布

**500 人零注入、`D = 2025-09-15`、跑完 `run_daily` 之后查 `derived_metrics.trend`**（读生产状态）：

```
{持续下滑: 100, 波动大: 75, 稳定: 200, 稳步提升: 125}
```

生成器真值（同一批 `build_dataset` 输出里 `trend_label` 的配额）：

```
{持续下滑: 100, 波动大: 75, 稳定: 200, 稳步提升: 125}
```

**逐类相等 ✓，且 `insufficient_data` 0 人**（零注入 ⇒ 两侧七项都齐 ⇒ 总分可比）。这正是 Ruling 140 说的「白得一条端到端交叉验证」，它同时证明了三件事：锚点选对了（week1-vs-week1）、`years = 1.0` 对了、龄组按学年折算对了（Ruling 56，错一个就会查到另一张评分表、差值带系统性偏差）。

**60 人零注入**（第 10 条测试用的那一组）同样逐人对账：60/60 相同、分布 `{持续下滑:12, 波动大:9, 稳步提升:15, 稳定:24}` = `allocate_quota(trend_mix, 60)`。

**缺省注入下这条等式不成立，且不该成立**（500 人实测）：`{insufficient_data: 209, 稳定: 120, 稳步提升: 71, 持续下滑: 60, 波动大: 40}`。209 人是 4% 缺测注入让两学年 week1 的七项里至少一项为 `None` → `national_total` 为 `None` → 趋势 `INSUFFICIENT`（Ruling 99/106 的合法状态，`annual_change = {}`）。故第 10 条测试用**独立的零注入 fixture**（`CLEAN_CFG` + `clean_env`），断言的才是口径而不是注入。

---

## 7. 分层分布

| 场景 | red | yellow | green | insufficient | 对照 |
|---|---|---|---|---|---|
| **500 人零注入、管道**（读 `stratification_result`） | 110 人 = **22.0%** | 238 人 = **47.6%** | 152 人 = **30.4%** | 0 人 = 0% | **与 Ruling 128 的「有线 22.0 / 47.6 / 30.4」逐字相同** ✓ |
| 500 人缺省注入、管道 | 95 = **19.0%** | 233 = **46.6%** | 170 = **34.0%** | 2 = **0.4%** | `test_target_layer_distribution_within_tolerance` 的容差是 20/45/35 ±5%，四档全部在内；green 余量 4.0 点 |
| 500 人缺省注入、**内存** `stratify_dataset(ds)` | **19.0%** | **46.6%** | **34.0%** | **0.4%** | **与上一行逐字相同** ⇒ DB 路径与内存路径是同一套算法（§10 的第 3 条证据） |
| 60 人缺省注入、管道 | 7 | 29 | 24 | 0 | 测试 fixture 那一组 |
| 60 人零注入、管道 | 8 | 30 | 22 | 0 | 第 10 条测试那一组 |
| 60 人、`D=2024-09-01`（整批无数据） | 0 | 0 | 0 | **60 = 100%** | 全员 Z0，`percentile_source = "none"` |

Ruling 128 的「无线 20.2 / 44.2 / 35.6」这一组我没有复现（那需要在 `derive` 里硬传 `snapshot_muscle_p20 = None`，属于对生产代码的临时改动）；**有线那一组逐字复现**，而这正是 0.2 落地之后系统实际所处的那一侧，也是 `test_target_layer_distribution_within_tolerance` 的 docstring 明写「本测试用 `stratify_dataset`，故它跑的是**有线**的那一组」的那一侧。

---

## 8. `percentile_source` 的实际取值分布

见 §1 的 0.3 表格。汇总：

- `"school"`：500 人两组（零注入 500/500、缺省注入 500/500）——四个组的 6 个短板判定项样本都 ≥ 30。
- `"national"`：60 人缺省注入 60/60——四个组样本都 < 30，全部走 `national_norm` 兜底。
- **`"none"`：出现过**，60 人 `D = 2024-09-01`（早于任何采集日）60/60，全部 `valid_count = 0`。
- **混用降级**：本数据集里没有出现「同一人的 6 条判定线一部分 school、一部分 national」的情形（样本量按组一致，要么全 ≥30 要么全 <30），故 `"national"` 全部来自「六项齐降级」。这条口径由单元测试 `test_summarize_source_covers_the_three_rulings` 直接喂混合行覆盖（`summarize_source(school[:5] + national[:1]) == "national"`）。
- `valid_count ∈ {1,2,3}` 那一支实测到过：500 人缺省注入里那 2 个 Z0 学生 `valid_count = 3` → `"school"`（不是 `"none"`），与 Ruling 137 第二条一致。

---

## 9. 三次变异验证与三重还原证据

三次变异**全部让测试变红，没有一次空转**。但变异 ③ 需要我补的第 10 条测试才抓得到——在计划 Step 1 的 9 条下它是空转的，这是本轮最重要的发现，见**关切 7**。

### 变异 ①：重放清理清单从三张表减到两张（去掉 `PercentileSnapshot`）

改 `daily._replay_cleanup` 的元组，删掉 `models.PercentileSnapshot,` 一行。

**结果：3 条测试变红**（`3 failed, 7 passed in 9.27s`），全部是同一个响亮失败：

```
FAILED test_rerun_same_business_date_is_idempotent
FAILED test_labels_are_reproducible_across_reruns
FAILED test_rerun_same_day_does_not_wipe_percentile_snapshot      ← Ruling 32 的守卫
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed:
  percentile_snapshot.semester_id, percentile_snapshot.computed_on,
  percentile_snapshot.item, percentile_snapshot.sex, percentile_snapshot.age_group
[parameters: (1, '2025-09-15', 1, 'bmi', 'female', '大一、大二', 60.0, 60.0, 60.0, 60.0, 60.0, 15, 'national')]
```

**过程中发现并修掉的一处设计缺陷（值得单记）**：我最初把「是否重算快照」实现成「源数据是否比上一次物化更新」（按日期比较）。在那一版下，同日重跑会判定「不必重算」，于是**删不删当日快照都看不出任何差别——变异 ① 不会让任何测试变红，Ruling 32 的守卫是空转的**。更要紧的是它自己带一条静默路径：源系统补传一条 `tested_on <= business_date` 的记录后重跑同一天，源表经 `repo.upsert` 更新了，快照却因为「数据日期没变」而留在上一轮，P25 与它要判定的得分不再是同一批人算的，全程不报错。改成计划 Step 3 的字面判据（「本批抽到了新体测/体成分数据」，读 `daily_sync_run.extracted_fitness / extracted_body_comp`）之后，清理清单里的 `PercentileSnapshot` 才是承重的，漏删立刻 `IntegrityError`。两版判据的取舍已写进 `percentile_stage.needs_recompute` 的 docstring（含被否决那一版的后果）。

### 变异 ②：`extract` 不做 `<= business_date` 过滤

三个列表推导式换成 `list(adapter.fetch_*(since))`。

**结果：1 条测试变红**（`1 failed, 9 passed in 9.79s`）：

```
FAILED test_percentile_snapshot_materialized_not_recomputed
    run_daily(session, sem, D, ad)            # D = 2025-09-15
    run_daily(session, sem, "2025-09-16", ad) # 无新体测数据
>   assert n1 == n2 and n1 > 0
E   assert (28 == 56)
```

机制：不过滤 ⇒ 首日就把 `2025-10-20` / `2025-12-15` 两个未来时点写进了源表；次日 `since = 2025-09-15` 又把它们抽回来 ⇒ `extracted_fitness > 0` ⇒ 判定「有新数据」⇒ 再物化一批 `computed_on = 2025-09-16` 的快照 ⇒ 行数翻倍。**但抓的是间接后果**，直接后果（未来数据进了本批、`extracted_fitness` 从 2000 变 3000）没有任何断言看着——见**关切 8**。

### 变异 ③：趋势对比改成「两条最新记录」

`assessment_anchor` 去掉 `timepoint == "week1"` 过滤，`cohort_from_db` 的 `years` 改成 `(curr_date - prev_date).days / 365.25`。在 `D = 2025-09-15` 下 prev 于是从上学年 week1(2024-09-02) 变成上学年 week16(2024-12-16)、`years` 从 1.0 变成 259/365.25 ≈ **0.709**（与计划预估的 ≈0.71 一致）。

**结果：1 条测试变红**（`1 failed, 9 passed`），红的正是我补的第 10 条：

```
FAILED test_trend_matches_the_generator_oracle_on_week1_anchors
  assert got == truth, [...]
  -     '2022100004': '稳定',
  +     '2022100004': '稳步提升',
  （逐人字典对比，多处不符）
```

年均口径 `Delta / years` 把趋势放大约 1.41 倍，「稳定」被推过 `+5` 线变成「稳步提升」。**在计划 Step 1 的 9 条测试下，这次变异不会让任何断言变红**（我按同一份变异跑过：锚点仍是 week1 时 `curr` 不变，`test_daily.py` 的 9 条没有一条读 `trend` 或 `years`）。

### 三重还原证据（三次变异各自还原后统一取证）

1. **标记双路 0 命中**（ASCII 模式，`Select-String` 与 python 读字节计数交叉验证，两条路径结论一致）：

   | 标记 | python 字节计数 | `Select-String` |
   |---|---|---|
   | `_years`（变异 ③）in `percentile_stage.py` | **0** | 0 命中 |
   | `list(adapter.fetch`（变异 ②）in `extract.py` | **0** | 0 命中 |
   | `models.PercentileSnapshot,`（变异 ① 的还原标志）in `daily.py` | **1** | 1 命中（`daily.py:218`） |
   | `timepoint == `（week1 过滤回来了）in `percentile_stage.py` | **1** | — |
   | `years=YEAR_STEP`（还原标志）in `percentile_stage.py` | **1** | — |
   | `_not_later_than(record`（过滤回来了）in `extract.py` | **4**（1 def + 3 调用点） | — |

2. **`git diff --stat`**：三次变异全部还原后，`git status --short` 只剩本 Task 该改的 12 个文件；`git diff --stat` 对 `app/pipeline/{daily,extract,percentile_stage}.py` **无输出**（它们是新增文件，变异与还原都发生在未提交的工作树里，还原后内容与提交前逐字一致，由第 3 条的重跑证明）。

3. **重跑全量**：`python -m pytest -q` → **416 passed in 26.23s**；`python -m pytest -q -W error` → **416 passed in 28.31s**。与变异前的 416 逐字相同。

（按项目纪律，还原**没有用 `git checkout`**——它会把 LF 转 CRLF，SHA256 跨 checkout 不可比。）

---

## 10. `git diff --stat 47f000c..HEAD`

```
 backend/app/db/models.py                 |  56 ++-
 backend/app/domain/percentile.py         | 218 +++++++++--
 backend/app/domain/stratify.py           |  11 +-
 backend/app/pipeline/daily.py            | 564 +++++++++++++++++++++++++++++
 backend/app/pipeline/extract.py          | 135 +++++++
 backend/app/pipeline/percentile_stage.py | 367 +++++++++++++++++++
 backend/app/pipeline/run_stratify.py     | 597 +++++++++++++++++++++++++++++++
 backend/tests/db/test_models.py          |  69 +++-
 backend/tests/db/test_repo.py            |  15 +-
 backend/tests/domain/test_percentile.py  | 116 +++++-
 backend/tests/fixtures/golden_cases.json |  57 ++-
 backend/tests/pipeline/test_daily.py     | 190 ++++++++++
 12 files changed, 2354 insertions(+), 41 deletions(-)
```

**`-- backend/app/seed/ backend/data/` 为空**（两条独立取证）：

```
$ git diff --stat 47f000c..HEAD -- backend/app/seed/ backend/data/
（无输出）
$ git diff --name-only 47f000c..HEAD -- backend/app/seed/ backend/data/ | Measure-Object
Count = 0
```

另：`Test-Path backend/pe.db` → **False**（从未创建）；`backend/data/seed/` 的文件数 → **0**（保持空）。Task 6 的三个 CSV 哈希因此不可能作废——`app/seed/` 一个字节都没动。

---

## 11. 既有 396 条断言未改的证明

逐文件列出 `git diff -U0` 里**所有被删掉的行**（`^-`，排除 `---` 文件头）：

| 文件 | 被删的行 | 性质 |
|---|---|---|
| `tests/domain/test_percentile.py` | `    MIN_SAMPLE, PERCENTILES, compute_snapshot, lookup_p25, national_norm,` | import 行（扩成两行 + 新增 `find_weaknesses`），非断言 |
| | `    bad_item[7]["item"] = "muscle_mass_kg"            # Ruling 102：库里存得下、算不出来` | **0.2 强制**：肌肉量成了合法 `SnapshotMetric`，改成 `"body_fat_pct"`（仍非法） |
| | `    assert "muscle_mass_kg" in str(exc.value)` | 同上，改成 `assert "body_fat_pct" in str(exc.value)` |
| `tests/db/test_models.py` | `from app.domain.indicators import Sex` | import 行，非断言 |
| `tests/db/test_repo.py` | `# 九条 ck_* 取值域约束（Minor 2）` | 分节注释 → 「十条」 |
| | `    """九条 ``ck_*`` 逐条验证：…` / `    此前这九条约束在提交内容里**零覆盖**…` | docstring 措辞，非断言 |
| `tests/fixtures/golden_cases.json` | `_meta.purpose` / `_meta.expected_from` / `_meta.input_schema.snapshot_muscle_p20` / `_meta.percentile_note` 四行 | 全是 `_meta` 说明文字（「12 个」→「13 个」、以及「仓内没有 P20 生产者」这句在 0.2 之后成了假话）。**`input` 与 `expected` 的 GC01–GC12 一个字都没删** |
| `tests/domain/test_stratify.py` | **（无任何被删的行——该文件 `git diff` 为空）** | 0.4 授权改的「断言 `reason` 全文的用例」实际不存在 |
| `tests/domain/test_derive.py` | **（无任何被删的行——该文件 `git diff` 为空）** | 0.5 那条测试已在仓里 |
| `tests/integration/test_golden_cases.py` | **（无任何被删的行——该文件 `git diff` 为空）** | Task 9 的断言逐字未改 |

即：**唯一被改动的既有断言是 `test_compute_snapshot_rejects_an_unknown_sex_or_item_with_the_row_index` 里那两行**，而它是 0.2「同步改 `_validated_member(ScoredItem, …)` 入口校验」的直接、不可避免的后果（改前实测 `DID NOT RAISE ValueError`）。改后该测试的三条断言（`"scores[7]" in msg`、`"item" in msg`、offending 值 in msg）形状与牙口都不变，只是把例子换成一个**仍然非法**的指标名。

`golden_cases.json` 的 GC01–GC12 未改，另有一路结构化取证（`git show 47f000c:` 的旧版 vs 现版，用 python `json.load` 对比）：`old input == new input[:12]`、`old expected == new expected[:12]`，`_meta` 里变化的键恰为 `purpose` / `expected_from` / `input_schema` / `percentile_note` 四个。

---

## 12. 关切

> 每条都附可复现的测量方法，并标明读的是**生产代码的中间/最终状态**还是**我自己重新推导的输入**（硬规矩 #6）。

**关切 1（控制者的数字错了）：测试数不是 396 → 398，而是 396 → 416。**
简报与计划 Step 6 都写 398。398 = 396 + Task 9 的 2 条集成测试，**漏了 `test_daily.py` 自己的 9 条**，也漏了 Step 0 各小节必需的新测试（0.2 的三条 + 0.3 的两条 + 两个新取值域各一条漂移/覆盖测试 + 一条新 CHECK 的参数化条目 = 8 条），再加我补的第 10 条 = 20 条。
*复现*：`cd backend ; python -m pytest -q` → `416 passed`；`python -m pytest tests/pipeline/test_daily.py tests/domain/test_percentile.py tests/db/test_models.py "tests/db/test_repo.py::test_check_constraint_rejects_dirty_value" tests/integration -q --co` 数收集到的条数。*读的是生产状态*。

**关切 2（Step 0.5 已经在仓里，控制者的信息是陈旧的）：** `test_derive_rejects_prev_total_with_a_missing_prev_value` 已存在于 `tests/domain/test_derive.py:602-618`，是基线 396 条之一，而且**已经**按硬规矩 #15 断言了消息特征子串（`assert "同真同假" in str(exc.value)`），注释里也已写明「形态 6 现在被两道守卫拦下……只断言 ValueError 的话，砍掉任一道另一道仍会拦住，本条就不可伪证（空转）」。我**零改动**。
*复现*：`python -m pytest tests/domain/test_derive.py::test_derive_rejects_prev_total_with_a_missing_prev_value -q` → `1 passed`；`git diff 47f000c..HEAD -- backend/tests/domain/test_derive.py` → 无输出。*读的是生产状态*。

**关切 3（计划的数字错了）：`hit_rules` 最长是 20 字符，不是计划写的 23。**
计划 Step 0.1 写「实测最长 23 字符」。23 = `"Z0,R1,R2,Y1,Y2,Y3,Y4,G1"`（8 个 ID + 7 个逗号），那是**把 Z0 算进前缀**的结果，与同一句里的 Ruling 132（「Z0 未命中 → 已评估的 7 条分层规则序列、**不含 Z0**」）自相矛盾。真实最长是 `"R1,R2,Y1,Y2,Y3,Y4,G1"` = 7×2 + 6 = **20**。我按 20 写进 `models.py` 的 docstring。
*复现*：`python -c "print(len('R1,R2,Y1,Y2,Y3,Y4,G1'))"` → 20；或跑完 60 人整批后 `select max(length(hit_rules)) from stratification_result` → 20（实测 `max_hit_rules_len = 20`，列宽 128）。*读的是生产状态*。

**关切 4（真实的潜在缺陷，未改）：`derived_metrics.trend` 是 `String(16)`，而 `Trend.INSUFFICIENT.value` 是 17 字符。**
SQLite 不强制列宽，故 17 个字符**静默存进去了**（实测 500 人缺省注入下有 **209 行** `trend = "insufficient_data"`，`max(length(trend)) = 17`，逐字读回）。换到严格长度的后端（MySQL / PostgreSQL 的 `VARCHAR(16)`）会截断或报错，而截断后的 `"insufficient_dat"` 不再等于任何 `Trend` 的值 → 下游 `Trend(row.trend)` 当场 `ValueError`。同一张表的 `stratification_result.label` 是 `String(20)`，装得下同样 17 字符的 `"insufficient_data"`——两列装的是同一个 `Trend` 值域，宽度却不一致。
**未改**：这一列不在 Step 0 的授权范围内（0.1 只授权改同文件 `:421-427` 的 docstring）。修法是把 `String(16)` 改成 `String(20)`，一行。
*复现*：`python -c "from app.db import models as M; from app.domain.derive import Trend; print(M.DerivedMetrics.__table__.c.trend.type.length, len(Trend.INSUFFICIENT.value))"` → `16 17`；或跑一遍 500 人缺省注入后 `select max(length(trend)), count(*) from derived_metrics where trend='insufficient_data'` → `17, 209`。*读的是生产状态*。

**关切 5（0.4 的连带后果，未改）：`golden_cases.json` 里 GC06/GC07/GC09/GC11 四条 `expected[].reason` 现在与生产不一致。**
它们仍写 `"短板 ≥2 项且体成分正常"` / `"无短板且体成分正常"`，而 0.4 之后生产给的是「……体成分**未判为异常**」。集成测试不断言 `reason`（只断言 `label`/`W`/`C`/`valid_count`/`dominant_bucket`/`hit_rules`），故全绿；但该夹具 `_meta.expected_from` 自述「expected 的每个值都由生产代码算出，不是手抄」，这四行现在是陈旧的，将来谁把 `reason` 加进断言就会红一次并误判成生产回归。
**未改**：0.4 只授权改 `stratify.py` 的字符串常量与「断言 `reason` 全文的测试」，夹具的 `expected` 不在其中，而简报又明写「不要改 fixture 期望值」。请裁定：是把这四行同步过来，还是在 `_meta` 里加一句「`reason` 列以 Ruling 134 之前的措辞留存、不参与断言」。
*复现*：`python -c "import json,pathlib; d=json.loads(pathlib.Path('tests/fixtures/golden_cases.json').read_text(encoding='utf-8')); from app.domain.stratify import _REASON, RuleId; print([ (e['student_id'], e['reason'], _REASON[RuleId(e['hit_rules'][-1])]) for e in d['expected'] if e['reason'] != _REASON[RuleId(e['hit_rules'][-1])] ])"` → 打印出 GC06/GC07/GC09/GC11 四条。*读的是生产状态（`_REASON`）与夹具字面量的对比*。

**关切 6（0.2 强制改了一条既有断言）：** `tests/domain/test_percentile.py::test_compute_snapshot_rejects_an_unknown_sex_or_item_with_the_row_index` 原本拿 `"muscle_mass_kg"` 当「非法 item」的例子，注释还写着「Ruling 102：库里存得下、算不出来」。落地 0.2 之后它成了**合法**值，该测试实测 `Failed: DID NOT RAISE ValueError`（`1 failed, 395 passed, 1 error`）。已把例子换成 `"body_fat_pct"`（体脂率走固定阈值、不进快照，仍非法），三条断言的形状与牙口不变，并就地写了注释说明为什么换。这是「同步改入口校验」的直接后果，不是放宽容差；但它确实动了既有的 396 条里的一条，故单列。
*复现*：把 `percentile.py` 的 `_validated_member(SnapshotMetric, …)` 改回 `_validated_member(ScoredItem, …)`，该测试立刻 `DID NOT RAISE`（我实测过这个中间态）。*读的是生产状态*。

**关切 7（最重要的一条：计划 Step 1 的 9 条测试守不住 Ruling 140，我补了第 10 条）：**
变异 ③（趋势对比改成「两条最新记录」、`years` 变成 ≈0.709）在**计划给的 9 条测试下不会让任何断言变红**——那 9 条没有一条读 `derived_metrics.trend`、`input_snapshot["years"]` 或趋势分布。而 Ruling 140 自己说这条口径是「最容易猜错的一处」，并且明写它「白得一条端到端交叉验证」。一条口径没有任何守卫，就是空转。
**处置**：补 `test_trend_matches_the_generator_oracle_on_week1_anchors`（第 10 条）。它用**独立的零注入 fixture**（`CLEAN_CFG` / `clean_env`，同样落在 `tmp_path` 的独立 sqlite 文件上），三条断言：① 60 人的 `derived_metrics.trend` 与生成器写进每条体测记录的 `trend_label` 真值**逐人相同**（`got == truth`，失败消息直接打印不符的人）；② 分布**恰好**等于 `allocate_quota(trend_mix, 60)` = `{持续下滑:12, 波动大:9, 稳步提升:15, 稳定:24}`（不是容差）；③ `input_snapshot["years"]` 的全部取值 == `{1.0}`。
补完之后变异 ③ 实测变红（§9）。**代价是 Step 5 从「9 passed」变成「10 passed」**，与计划字面不符，请裁定是否接受。
*为什么必须零注入*：缺省注入下 4% 缺测会让 `national_total` 变 `None` → 趋势 `INSUFFICIENT`（对不了账），0.5% 越界会把某一项夹到底档、真的改掉那个人的趋势（实测 500 人缺省注入下趋势分布是 `{insufficient_data:209, 稳定:120, 稳步提升:71, 持续下滑:60, 波动大:40}`，与配额无从比较）。用缺省注入写这条断言，测到的是注入而不是口径。
*复现*：`python -m pytest tests/pipeline/test_daily.py::test_trend_matches_the_generator_oracle_on_week1_anchors -q` → `1 passed`；再按 §9 变异 ③ 改两行 → `1 failed`。*读的是生产状态*。

**关切 8（变异 ② 只被间接抓住）：** 去掉 `<= business_date` 过滤后，唯一变红的是 `test_percentile_snapshot_materialized_not_recomputed`（`assert 28 == 56`，抓的是「次日快照翻倍」这个**间接**后果）。**直接**后果——`extracted_fitness` 从 2000 变成 3000、`2025-10-20` / `2025-12-15` 两个未来时点进了本批——没有任何断言看着，因为计划 Step 1 的 `test_run_daily_populates_all_stages` 只写 `assert fitness > 0`。建议把它收紧成 `fitness == 240`（60 人 × 4 个 `<= D` 的时点）、`bodycomp == 240`、`survey == 120`，这样「时间旅行」就有了直接守卫。**未改**（计划的断言我逐字照抄）。
*复现*：按 §9 变异 ②，然后 `select count(*) from fitness_test_result` → 360（= 60 × 6 个时点）而不是 240。*读的是生产状态*。

**关切 9（0.2 第 4 步要求的留痕没有合适的列）：** 「缺线组数」被写进了 `DailySyncRun.error_summary`，因为那是本表**唯一**的自由文本列，而 0.2 明写「留痕靠 Task 10 在 `DailySyncRun` 的摘要里计一条缺线组数」且「不要新增第三个 `reasons` token」。列名与内容因此不符：Task 11 的 CLI 若把 `error_summary` 当失败原因打印，会在一次 `status = "success"` 的运行上说出一段看似报错的话。我加了前缀「注意（非错误）：」并**只在 gaps > 0 时写**（`status = "failed"` 时那一列写的是真异常，两者不会同时出现，因为失败路径整批回滚后由 `_record_failure` 重写这一列）。实测 60 人组写下的是「注意（非错误）：4 个 (性别 × 年级组) 组没有肌肉量 P20 判定线……」，500 人组是 `null`（四组样本都 ≥ 30，gaps = 0）。建议 Plan 02 给本表加一个 `summary` 列或把这一列改名。
*复现*：跑一遍 60 人整批后 `select status, error_summary from daily_sync_run`。*读的是生产状态*。

**关切 10（Task 11 会踩的一个坑，已实测）：`run_daily` 返回的 ORM 实例在会话关闭后 detached。**
`run_daily` 成功路径末尾 `session.commit()`，之后实例的全部属性都 expire 了；调用方一旦退出 `with Session(...)`，再读 `run.status` 就抛 `DetachedInstanceError: Instance <DailySyncRun ...> is not bound to a Session`。我在探针里实测到了这个异常（第一次跑探针就是在这里炸的）。Task 11 的 CLI 必须**在 Session 还开着的时候**把要打印的字段读出来（或 `session.expunge(run)` / 重新查一次）。已写进 §13 的前向约束。
*复现*：`with Session(eng) as s: run = run_daily(...)` 然后在 `with` 外面 `print(run.status)`。*读的是生产状态*。

**关切 11（对计划字面措辞的一处有意偏离）：原子边界用 SAVEPOINT 而不是裸 `session.rollback()`。**
计划 Step 3 写「未捕获异常 → `session.rollback()` 并写 `status="failed"` 的独立小事务记录」。这两件事在本项目的 fixture 与 Task 11 的 backfill 下**不能同时成立**：`seed_database` 只 flush 不 commit，故调用方在进入 `run_daily` 时手里常有**尚未提交**的组织结构；裸 `session.rollback()` 会把它一并撤销，于是紧接着写「失败运行记录」时 `daily_sync_run.semester_id` 指向的 `semester` 行已经不存在，而 `PRAGMA foreign_keys=ON`（Ruling 27 的钩子）当场 `FOREIGN KEY constraint failed` —— **错误处理器自己炸了、真因被盖掉**，`test_failure_rolls_back_whole_batch` 的 `pytest.raises(RuntimeError)` 也会变成一个 `IntegrityError`。
**处置**：整批包在 `with session.begin_nested():` 里（SAVEPOINT）。异常时只回滚到 savepoint，调用方的待提交内容原样保留，失败记录因此总写得进去；对调用方而言语义不变（本批要么全在、要么全不在），`test_failure_rolls_back_whole_batch` 的 `assert _counts(session) == (0,)*7` 实测成立。另外 `_record_failure` 自己包了一层 try：留痕失败时回滚它自己并**吞掉**，让调用方的 `raise` 把真因抛出去——一个把 `RuntimeError("boom")` 换成 `IntegrityError` 的错误处理器等于把唯一的线索删了。
*复现*：把 `with session.begin_nested():` 去掉、在 `except` 里改成 `session.rollback()`，然后跑 `test_failure_rolls_back_whole_batch` → 报的是 `IntegrityError: FOREIGN KEY constraint failed` 而不是 `RuntimeError: boom`。*读的是生产状态（我实测过这个中间态才改的设计）*。

**关切 12（设计取舍，需要 Task 11/Plan 02 知道）：`stratification_result.valid_to` 恒为 `NULL`。**
我**刻意不去关闭上一日的行**：那会让重放必须同时改写上一批的行，破坏「同一业务日期重跑只动本批」这条幂等边界（`_counts()` 的七元组会跨批变化）。「哪一条现在生效」由 `computed_on` 最大者唯一确定，实测同一学生跨 3 个业务日期会有 3 行、`valid_to` 全 `NULL`、`valid_from` 分别是三个日期。**后果**：Plan 02/03 若按 `WHERE valid_to IS NULL` 查「当前生效的分层」，会得到该学生的全部历史行。要么按 `computed_on` 取最大，要么在 Plan 02 里补一个「关账」步骤。
*复现*：连跑 `D = 2024-09-01 / 2025-09-15 / 2025-09-16` 后 `select count(*), count(valid_to) from stratification_result` → `180, 0`。*读的是生产状态*。

**关切 13（spec 缺口，未自造口径）：`fitness_test_result.national_grade` 恒写 `None`。**
spec §4.2 列了「总分、国标等级」，`models.py` 也有这一列（`String(16)`，可空），但**spec 与全仓都没有给出「总分 → 优秀/良好/及格/不及格」的阈值**（全仓 grep `national_grade|优秀|良好|及格|不及格` 只命中 `models.py:271` 的列声明与 `data/README_national_standard.md` 里一句无关的话）。自己填一套就是凭空造第二个口径，而它会出现在学生端与报表上。按 `repo.upsert` 的 PATCH 语义，我**显式传 `None`**（不是省略），让「本轮没算出来」表现为显式写入而不是「沿用上一轮」。请裁定阈值口径（国标 2014 的通行分档是 90+ 优秀 / 80–89.9 良好 / 60–79.9 及格 / <60 不及格，但这需要写进 spec 才能落地）。
*复现*：`Grep 'national_grade|优秀|良好|及格|不及格'` 全仓 → 2 处命中，都不是阈值口径；跑完整批后 `select count(national_grade) from fitness_test_result` → `0`。*读的是生产状态*。

**关切 14（分层方向的依赖，未动已结案模块）：`app/pipeline/run_stratify.py` 有两处 `pipeline → seed` 依赖。**
`from app.seed.fitness import COLUMN_BY_ITEM`（计分项 → 原始值列名的映射）与 `from app.seed.generate import RANGES_FILENAME`（区间表文件名）。两处都是为了**不重抄第二份字面量**：那张映射无法从名字推导（`pull_up_or_sit_up` 对应的是 `strength_count`），抄错的后果是某一项恒为 `None`、该桶短板静默消失；文件名抄错的后果是 `load_ranges` 读到另一个文件、而它的键集合校验只在**它读到的那个文件**上生效。但依赖方向与 spec §3.3 的分层习惯相反（`seed` 是数据生成器）。它们**正确的家**分别是 `app/adapters/base.py`（CSV 契约的所有者，已经住着八个契约常量）与 `app/pipeline/clean.py`（`load_ranges` 的所有者），两者都是已结案模块，故未动。已确认无导入环：`app.seed.generate → app.pipeline.clean`，而 `clean` 不 import `run_stratify`；`app.seed.fitness` 不 import `generate`。
*复现*：`python -c "import app.pipeline.daily, app.seed.generate; print('ok')"` → `ok`（两种导入顺序都试过）。*读的是生产状态*。

**关切 15（签名的必然后果）：`stratify_dataset(dict)` 没有 `business_date`，内存路径的锚点恒取「数据集里最新的 week1」。**
DB 路径按真实 `business_date` 取「最新体成分 `<= D`」，内存路径恒停在 week1。在计划钉住的 `D = 2025-09-15` 上两者**逐字相同**（实测：500 人缺省注入下分层分布内存 `19.0/46.6/34.0/0.4` == 管道 `19.0/46.6/34.0/0.4`，四档全部相同），但 `D` 更晚时（例如回填到 `2025-12-20`，那时最新体成分是 week16）两者会分道。签名是计划 Interfaces 钉住的（`stratify_dataset(payload: dict | list)`），故**未加参数**；已写进 `_from_dataset` 的 docstring。若 Task 11 的回填要用内存路径复算某一天的结果，需要给它开一个 `as_of` 参数。
*复现*：见上面那两组实测数字（同一次运行里分别走 `stratify_dataset(ds)` 与 `run_daily` 后查库）。*读的是生产状态*。

**关切 16（性能，留给 Task 11）：三处会在 500 人 × 112 天回放上放大的开销。**
① `cohort_from_db` 每次运行被调用**两遍**（`run_percentile` 里一遍、`_stratify_and_persist` 里一遍），因为 `run_percentile` 的签名钉死为 `(session, business_date, batch_id)`，无法把已读出的队列传进去；② `_latest_body_comp` 是 `select(BodyComposition).where(measured_on <= as_of)` 的**全表扫 + Python 侧归约**，而回放时这张表会长到 500 × 6 × …（本批只写 `<= D` 的 4 个时点，112 天累计约 33 万行）；③ 每条源记录一次 `repo.upsert`（即一次 SELECT），500 人单日约 5000 次。实测 500 人**单日**整批 `started_at → finished_at` = **2.16 s**（零注入，`17:25:51.858144 → 17:25:54.022025`）；线性外推 112 天约 4 分钟。Task 11 的性能步若要压，①③ 可以合并成一次批量读 + 批量写，② 应改成 SQL 侧的分组聚合。
*复现*：`select started_at, finished_at from daily_sync_run` → `2026-09-30 17:25:51.858144` / `2026-09-30 17:25:54.022025`。*读的是生产状态*。

---

## 13. 前向约束（Task 11 必读）

**`run_daily` 的签名与返回值**

```python
def run_daily(session: Session, semester_id: int, business_date: str,
              adapter: DataSourceAdapter) -> models.DailySyncRun
```

- `business_date` 是**零填充 ISO 串** `"YYYY-MM-DD"`；其他形状立刻 `ValueError`（`extract.parse_business_date`），不静默退化。
- `semester_id` 是**运行记录与百分位快照的归属**（幂等键 `(semester_id, business_date)` 的一半），**不是数据的归属**：`fitness_test_batch.semester_id` 与 `interest_survey.semester_id` 由记录自己的日期落在哪个学期区间决定（`daily._semester_of`，查不到就 `ValueError`）。**用 `--semester 2025-2026-1` 重放一个 2024 年的业务日期是完全合法的**，两者本来就不必相等。计划的测试正是这么用的（`session.scalar(select(M.Semester)).id` 取到的是 id=1 = `2024-2025-1`，而 `D = 2025-09-15`）。
- 返回的是 **ORM 实例，且已 commit ⇒ 属性全部 expire**。**必须在 Session 还开着的时候把要打印的字段读出来**，否则 `DetachedInstanceError`（关切 10，已实测）。
- **`run_daily` 自己 commit**（成功路径末尾）。调用方不需要、也不应该再 commit 一次；但**调用方在 `run_daily` 之前的待提交内容会一并被提交**（这是 commit 的必然结果）。回填脚本应当先 `seed_database(...) ; session.commit()` 再进循环。

**事务边界与失败时的 `status` / 已提交内容**

- 整批包在一个 **SAVEPOINT**（`session.begin_nested()`）里：`Extract → Clean → 写源表 → Percentile → Derive → Stratify → 更新计数` 要么全在、要么全不在。关切 11 有为什么不用裸 `session.rollback()` 的实测理由。
- 未捕获异常 ⇒ **本批全部撤销**（三张派生表 + 三张源表 + `cleaning_log` + 本批对 `daily_sync_run` 计数列的更新，全部回到本批开始前的样子），然后 `_record_failure` 用**独立小事务**把 `status = "failed"`、`error_summary = f"{type(exc).__name__}: {exc}"`、`finished_at` 写进那一行并 commit，最后**原样重抛**（不吞异常）。
- 失败之后库里**唯一**留下的东西就是那一行 `status = "failed"` 的 `daily_sync_run`（以及调用方自己之前提交过的内容）。**水位线不会推进**：`previous_watermark` 只认 `status = "success"`，故重跑会重新全量抽取那一段。
- `status` 的三值：`"success"`（整批跑完、每条记录都归到了人头上）/ `"partial"`（整批跑完，但有记录因**学号解析不到 `student` 表**而被整条跳过，已逐条写进 `cleaning_log`，`kind = "missing_dropped"`、`field = "student_no"`、`student_id = NULL`）/ `"failed"`。CLI 应当把 `partial` 与 `success` 分开显示——重跑修不好一个建档缺失的学号。
- **`error_summary` 在 `status != "failed"` 时也可能非空**：它承载「缺线组数」的留痕（关切 9），前缀是「注意（非错误）：」。CLI 不要无条件把它当失败原因打印。

**幂等与重放**

- 幂等键是 `(semester_id, business_date)`，`repo.upsert` + `session.flush()` 取回 `id`（三张派生表的 `batch_id` 都是 NOT NULL 外键，忘了 flush 会在写派生行时炸）。
- 重放清理 = **三张派生表按 `batch_id` 删**（`DerivedMetrics` / `StratificationResult` / `PercentileSnapshot`）+ **`CleaningLog` 按 `sync_run_id` 删**。**三张源表不删**，一律 `repo.upsert` 按业务唯一约束幂等。**不要对 `FitnessTestResult` / `CleaningLog` 调 `delete_by_batch`**（`AttributeError`，Ruling 31 刻意设计）。
- **清理清单里不能少 `PercentileSnapshot`**：百分位阶段的判据是「本批抽到了新体测/体成分」（`needs_recompute` 读 `daily_sync_run.extracted_fitness / extracted_body_comp`），同日重跑必然重算，漏删就 `IntegrityError: UNIQUE constraint failed`（变异 ① 实测）。
- **`run.extracted_fitness / extracted_body_comp / extracted_survey` 必须在调 `run_percentile` 之前写上并 flush**——`needs_recompute` 读的就是这两列。顺序写反会让首日也跳过物化（快照恒空、全员 Z0），而六个阶段的计数看起来全都正常。

**百分位快照**

- 只在「本批抽到了新体测/体成分」时物化；跳过时 `run_percentile` 返回 `0`，判定线由 `load_snapshot` 复用**上一次** `computed_on <= business_date` 的物化结果（spec §4.0：禁止实时计算）。
- 要复算任意一天的分层，只能走 `run_daily`（它会读回库里的快照）；**不要**用 `stratify_dataset` 去复算某一天（关切 15：它没有 `business_date`）。

**CLI 需要哪些参数**

- 必需：`--semester`（学期名或 id；注意它是**运行记录**的归属，见上）、`--date`（业务日期，`YYYY-MM-DD`）、数据源目录（`MockLePaoAdapter(seed_dir)`，即 Task 6 `write_csv` 的输出目录）、数据库 URL。
- 建议：`--students / --weeks / --seed`（Task 6 的 CLI 已有同一组，`seed_database` 要用）；`--out-csv` 不要缺省落到 `backend/data/seed/`（Ruling 68：那个目录必须保持空）。
- 打印时**在 Session 内**取字段（关切 10）；`partial` 与 `failed` 要能区分；`error_summary` 要先看 `status` 再决定怎么渲染（关切 9）。
- 性能：单日 500 人约 2.2 s，112 天线性外推约 4 分钟；要压先看关切 16 的三处。

**其他**

- `derived_metrics.trend` 会写入 17 字符的 `"insufficient_data"`，而列宽声明是 `String(16)`（关切 4）。SQLite 上无害，迁移到严格长度的后端之前必须先改列宽。
- `stratification_result.valid_to` 恒为 `NULL`（关切 12）：查「当前生效的分层」要按 `computed_on` 取最大，不能按 `valid_to IS NULL`。
- `fitness_test_result.national_grade` 恒为 `NULL`（关切 13）。
- `body_composition.weight_kg` 与 `device` 恒为 `NULL`：适配器契约（`RawBodyCompRecord`）里没有这两列。按 `repo.upsert` 的 PATCH 语义**显式写 `None`**，不是省略。

---

## 14. 临时探针清理

三个探针脚本（`_probe_task10.py` / `_probe2_task10.py` / `_probe3_task10.py`）与六个输出文件（`_probe{,2,3}_out.json`、`_probe{,2,3}_err.txt`）全部删除，逐个 `Test-Path` 复核 **False**（九个全 False）。另有一个中途用于对比夹具旧版的 `_old_golden.json` 也已 `Remove-Item` 并复核 `Test-Path` → False。

```
_probe_task10.py -> False      _probe_out.json  -> False      _probe_err.txt  -> False
_probe2_task10.py -> False     _probe2_out.json -> False      _probe2_err.txt -> False
_probe3_task10.py -> False     _probe3_out.json -> False      _probe3_err.txt -> False
pe.db -> False                 data/seed 文件数 -> 0
```

探针全部读**生产代码跑完之后的库状态**（`run_daily` → 直接查表）；唯一重新推导的输入是 §1 的 0.2 里「测量行级 P20」那一组对照数字，已在原文明写标注。

`git status --short`（提交后）：**空**。
`git log --oneline -1`：`31d8f3a feat: 每日批处理编排，整批单事务、按业务日期幂等重放、百分位快照按需物化`

---

## 15. 收尾取证（逐字）

```
$ git log --oneline -1
31d8f3a feat: 每日批处理编排，整批单事务、按业务日期幂等重放、百分位快照按需物化

$ git status --short
（无输出）

$ git status --short | Measure-Object | Select-Object Count
Count
-----
    0
```

本报告文件自身在 `.superpowers/` 下，而根 `.gitignore:10` 把 `.superpowers/` 整个忽略（`git check-ignore -v` 实测命中），故它不进 commit——与 Task 1–9 的报告一致。本 Task 的 commit `31d8f3a` **只含 12 个 backend 文件**（§10 的 `git diff --stat`）。

关切 4 / 5 / 14 的三条复现命令已逐条实跑确认：

```
$ python -c "from app.db import models as M; from app.domain.derive import Trend; print(M.DerivedMetrics.__table__.c.trend.type.length, len(Trend.INSUFFICIENT.value))"
16 17

$ python -c "import json,pathlib; d=json.loads(pathlib.Path('tests/fixtures/golden_cases.json').read_text(encoding='utf-8')); from app.domain.stratify import _REASON, RuleId; print([e['student_id'] for e in d['expected'] if e['reason'] != _REASON[RuleId(e['hit_rules'][-1])]])"
['GC06', 'GC07', 'GC09', 'GC11']

$ python -c "import app.pipeline.daily, app.seed.generate; print('import both ok')"
import both ok
```
