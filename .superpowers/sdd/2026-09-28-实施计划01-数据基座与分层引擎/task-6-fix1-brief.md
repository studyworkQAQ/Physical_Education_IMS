# Task 6 — Fix Round 1 派单简报

分支：`feature/plan-01-data-foundation`
基线 commit：`826f72a`（工作树干净，勿 rebase、勿 reset）
本轮只落实三条裁定：**Ruling 54（档内抖动 + 表下溢出）**、**Ruling 55（核实，不重做）**、**Ruling 56（上学年用上学年年龄组查表）**。

---

## 0. 环境（务必逐条遵守，前几轮已因这些吃过 9 次亏）

- Windows + **PowerShell**。命令分隔用 `;`，**绝不用 `&&`**。**没有 heredoc**，多行脚本写成临时 `.py` 文件再 `python file.py`，或直接用编辑工具写文件。
- **没有 venv**。Python 3.11.1 在 PATH 上，直接 `python` / `pytest`。
- `bash` 不在 PATH；需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- 工作目录：仓库根 `c:\Users\whwenhao\Desktop\Physical_Education_ims`，后端在 `backend/`（`pytest` 必须在 `backend/` 下跑，`conftest.py` 与包根都在那里）。
- **写盘事故是本项目的已知风险**：编辑工具报成功、编辑器内复读也正常，但字节没落盘。因此**每一次编辑后都必须用 shell 复核**，不要只信工具返回值：
  - `Select-String -Path <file> -Pattern "<刚写进去的独特串>" -SimpleMatch`
  - 提交前 `git diff --stat` + `git status --short`，确认改的文件数与预期一致。
- 任何**你无法做到的事、或简报里你认为写错了的地方**，不要静默绕过、也不要自作主张改设计：照做你能做的部分，把问题写进报告的「关切」章节，由控制者裁定。前几轮最有价值的产出全都来自实现者上报的矛盾。

---

## 1. 先读这些（顺序）

1. `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 **Task 6 Step 3–6**（约 `:868`–`:929`），Step 4 里已含 Ruling 54/56 的正文，Step 5 里已含 Ruling 55 的正文。
2. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-report.md` —— 你自己上一轮的 12 条关切。
3. `.superpowers/sdd/.../progress.md` 的 `### Task 6` 段（`:590`–`:634`）—— Ruling 54/55/56 的裁定原文与理由。
4. `backend/app/seed/fitness.py`、`backend/app/seed/config.py`、`backend/app/seed/sections.py`。
5. `backend/app/domain/indicators.py` 的 `score_item` / `raw_from_score` / `segment_thresholds` / `age_group_of` / `_lower_is_better`。

**架构红线（Task 1 的 AST 守卫会拦，别踩）**：`app/domain/` 内禁止任何 I/O、禁止 `import random`、禁止时钟调用。本轮**不要改 `app/domain/indicators.py`**——所需的一切（`segment_thresholds`、`score_item`）已经是公开 API。`app/seed/` 内也禁止出现第二个 `default_rng` / `np.random.seed` / `import random` / `date.today`（已有源码守卫）。

---

## 2. Ruling 55 —— 只核实，不重做

上一轮你已把行政班数改成由学生数反推（`sections.py:administrative_section_count`），`tests/seed/test_generate.py:138` 已断言 `len(admin) == 14`，计划 Step 5 与 spec §10.3 也已同步勘误。控制者已核实无误。

**本轮动作**：读一遍 `administrative_section_count` 与那条断言，确认与计划 Step 5 的反推公式
`sections = max(ceil(n / section_size_max), teachers × sections_per_teacher)`
以及退化规则（人数太少以致 `[30, 38]` 不可行时退化为 `teachers × sections_per_teacher` 且不施加下限）一致。在报告里写一句「Ruling 55 已核实，无需改动」即可。**若发现不一致，上报，不要自行改。**

---

## 3. Ruling 56 —— 上学年记录按上学年年龄组查表

### 现状（缺陷）
`fitness.py:make_fitness_tests` 的记录循环里：

```python
age_group = age_group_of(person["age"])
```

这一句对**两个学年都用同一个年龄组**。`person["age"]` 是以当前学期开学日（`config.BIRTH_REFERENCE_DATE`）为参考日算出的年龄，所以上学年（`2024-2025`）该生的真实年龄是 `age - 1`。约 **45% 的学生跨 19/20 线**（`age_group_of` 的分界是 `_LOWER_GRADE_MAX_AGE = 19`），这批人的上学年记录用了偏严一档的表。

### 后果（为什么这条是承重的，不是美观问题）
趋势差值（本学年得分 − 上学年得分）带系统性偏差，而**趋势是分层规则 Y4 的唯一输入**（见 spec §6.2）。偏差会直接改变分层结果，Task 9 的 20/45/35 分布断言会因此对不上，而且对不上的原因查不出来——每一项单独看都「合法」。

### 要做的改动
在记录循环里按学期取年龄组：

```python
age_group = age_group_of(person["age"] if plan.is_current else person["age"] - 1)
```

**该 age_group 必须用于这条记录的所有查表**，包括：
- `score_item(table, ScoredItem.BMI, bmi, sex, age_group)`（BMI 正查）
- `_raw_and_score(...)`（六项反查 + 回读）
- Ruling 54(b) 的表下溢出要用的「表内最低档原始值」（见 §4.3）

`_raw_and_score` 的 memo 键已含 `age_group`，所以传不同龄组不会串味——**但要复核这一点**，别假设。

注意 `age_group_of` 对超出 18–22 的输入自然落到端点组，`age - 1` 若等于 17 也只会落到低龄组，不会 KeyError。

### 测试要求
`tests/seed/test_generate.py:271` 的 `test_generated_raw_values_roundtrip_through_the_official_table` 目前用 `age_group_of(person["age"])`（`:298`）复核每条记录。改为**按记录所属学年取龄组**（本学年 `age`，上学年 `age - 1`），并断言：对每条记录、每个计分项，
`record[f"score_{item.value}"] == score_item(table, item, record[COLUMN_BY_ITEM[item]], sex, 该记录的龄组)`。

这条测试在改动**前**必须失败（因为生成器用错了表而测试用对了表，跨 19/20 线的学生会对不上），改动**后**必须通过。**先在报告里贴出改动前的失败输出**（至少一条跨线学生的实际 vs 期望），这是本轮唯一能证明该缺陷真实存在的证据。

另加一条独立测试：`test_previous_year_records_use_the_previous_year_age_group`——从 `population` 里筛出 `age == 20` 的学生（上学年 19 岁，跨线），断言其**上学年**记录的六项得分与 `age_group_of(19)` 那张表一致、且与 `age_group_of(20)` 那张表**至少有一项不同**（若两表对某生恰好全同，换一个跨线年龄再试；必须证明测试真的能分辨两张表，否则它是个空转测试）。

---

## 4. Ruling 54 —— 原始值不得全部落在档位端点上

### 4.1 现状（缺陷）
`raw_from_score` 按 Ruling 22 返回「仍能取得该分的**最差**原始值」，即档位端点。生成器 `raws[item] = raw` 直接采用，于是数据里每一个原始值都恰好是国标表的阈值。

**控制者已实测各项目的档距与真实测量分辨率**（`segment_thresholds` 全表扫描，24 组）：

| 项目 | 最小档距 | 方向 | 表内最低档（男 大一二 / 大三四） |
|---|---|---|---|
| `vital_capacity_ml` | 男 120 ml / 女 40 ml | 越大越好 | 2300 / 2350；女 1800 / 1850 |
| `sprint_50m_s` | **0.1 s**（全部 4 组） | 越小越好 | — |
| `sit_and_reach_cm` | 男 1.0 / 女 0.8 cm | 越大越好 | 男 −1.3 / −0.8；女 2.0 / 2.5 |
| `standing_jump_cm` | 男 4 / 女 3 cm | 越大越好 | 男 183 / 185；女 126 / 127 |
| `strength_count` | **男 1 次** / 女 2 次 | 越大越好 | **男 5 / 6 次**；女 16 / 17 次 |
| `distance_run_s` | 5 s | 越小越好 | 男 197 / 195；女 198 / 196 |

**由此得出的两点结论，直接照做，不要自行放宽或收紧：**

1. **50 米跑的档距恰好是 0.1 s，而 0.1 s 正是它的真实测量分辨率**（电子计时虽有 0.01 s，但国标评分表与高校上报口径都是 0.1 s）。所以「所有 50 米成绩都落在端点上」在这一项上**与真实数据不可区分**——真实数据也必然全是 0.1 的整数倍，而表内每一个 0.1 的整数倍都是阈值。Ruling 54 原文举的这个例子是不成立的，**不要为了消除它而生成 6.73 s 这种亚分辨率值**：那会伪造出评分表根本没有的测量精度，与 spec §12「可与学校官方报表逐格对账」冲突。
2. **男生引体向上的档距是 1 次，分辨率也是 1 次**，同理无法抖动。它的真实缺陷是 §4.3 的表下截断，不是端点问题。

真正需要修的是 `vital_capacity`、`sit_and_reach`、`standing_jump`、`distance_run`、女生 `strength_count` 这五处——档距明显大于分辨率，全落在端点上一眼就是造的（例如所有肺活量都是 120 的整数倍）。

### 4.2 要做的改动（a）：档内抖动

**配置**：`SeedConfig` 增 `jitter_within_band: bool = True`（默认开）。

**测量分辨率**：在 `app/seed/fitness.py` 定义模块级常量（**不要**放进 `SeedConfig`——它是仪器口径知识，不是可调旋钮）：

```python
MEASURE_DECIMALS: dict[ScoredItem, int] = {
    ScoredItem.VITAL_CAPACITY: 0,      # 肺活量计读到 1 ml
    ScoredItem.SPRINT_50M: 1,          # 计时读到 0.1 s
    ScoredItem.SIT_AND_REACH: 1,       # 游标读到 0.1 cm
    ScoredItem.STANDING_JUMP: 0,       # 跳垫/尺读到 1 cm
    ScoredItem.PULL_UP_OR_SIT_UP: 0,   # 次数是整数
    ScoredItem.DISTANCE_RUN: 1,        # 计时读到 0.1 s
}
```

**算法（必须用整数单位做，不要用浮点乘除 + `round`）**：

设 `d = MEASURE_DECIMALS[item]`、`scale = 10 ** d`、`raw_s` 是 `raw_from_score` 返回的端点、`direction` 由 `segment_thresholds` 的相邻关系判定（`_lower_is_better` 是私有的，**不要去 import 它**；改用「阈值升序 + `score_item` 回读」或直接比较该项在 `raw_s` 与相邻阈值上的得分来判方向）。

- **越大越好**：`next_raw` = 阈值表中**严格大于** `raw_s` 的最小阈值；不存在则无抖动空间。
  整数单位区间：`lo_u = int(round(raw_s * scale))`，`hi_u = int(round(next_raw * scale)) - 1`。
  `hi_u <= lo_u` → 直接返回 `raw_s`（**不消耗随机数**）。
  否则 `u = lo_u + int(rng.integers(0, hi_u - lo_u + 1))`，返回 `u / scale`。
- **越小越好**：`prev_raw` = 阈值表中**严格小于** `raw_s` 的最大阈值；不存在则无抖动空间。
  `hi_u = int(round(raw_s * scale))`，`lo_u = int(round(prev_raw * scale)) + 1`。
  `lo_u >= hi_u` → 返回 `raw_s`（不消耗随机数）。
  否则同上抽 `u`，返回 `u / scale`。

**为什么必须走整数单位**：浮点下 `2.01 * 100 == 200.99999999999997`，`math.floor` 会得到 200 而不是 201——这正是上一轮 Ruling 49 里踩过的那个残渣。整数单位 + `int(round(...))` 把阈值换算成精确整数，抖动区间因此是闭区间上的均匀整数，**从构造上保证不会跨档**，也就不需要「抽完再回验、失败重试」这类会掩盖真缺陷的兜底逻辑。

**次数类项目自动被这套逻辑覆盖**（`d = 0`，`scale = 1`，整数单位就是次数本身），不需要单独的「向下取整」分支。Ruling 54 原文那句「次数类向下取整再回验」在整数单位方案下是多余的——**在代码注释里写明这一点**，免得后来人以为漏了。

**抖动只作用于原始值，不作用于目标分**：`_raw_and_score` 仍返回 `(端点 raw, realised score)` 并继续用 memo（记忆化的是昂贵的表扫描，抖动是每条记录一次的廉价操作，**不要把抖动放进 memo**，否则同一 `(item, sex, age_group, floor(target))` 的所有记录会拿到同一个抖动值，档内又只剩一个取值）。抖动在 `make_fitness_tests` 的记录循环里、拿到 `(raw, realised)` 之后施加。

**随机数消耗顺序**必须固定：在记录循环内按 `WEAKNESS_ITEMS` 的声明序逐项抖动，且只在「有抖动空间」时抽数。在 docstring 里注明：改 `MEASURE_DECIMALS` 会整体平移随机流，因而改变同一种子的输出——这是配置变更的预期后果，不是缺陷。

### 4.3 要做的改动（b）：表下溢出

**配置**：`SeedConfig` 增

```python
sub_floor_rate: dict[str, float] = field(
    default_factory=lambda: {"male:pull_up_or_sit_up": 0.10}
)
```

键格式 `"<sex.value>:<item.value>"`。用到的键必须在 `Sex` × `ScoredItem` 的合法组合内，**未知键响亮报错**（`ValueError`，带完整合法键清单），不要静默忽略——静默忽略等于「配了但没生效」，而这条配置的全部意义就是影响 Task 9 的分层分布。

**这是对 Ruling 54 原文的一处实质修正，照此实现，不要按原文的「按概率随机挑记录」做**：

原文写「按配置概率生成低于表内最低档的值」，字面读是**对每条记录独立掷骰子**。那样做会造出「latent_strength = +2 的壮汉一个引体向上都做不起」的记录，与本模块赖以存在的潜变量相关性直接冲突（`test_indicator_correlation_is_realistic` 断言耐力/力量得分相关 > 0.4），而且同一个人 week1 做 12 个、week8 做 0 个。

改为**按学生、按该桶潜变量排序取最低的 `rate` 比例**：

1. 对每个出现在 `sub_floor_rate` 里的 `(sex, item)` 组合，取该性别全体学生，按 `latents[sid][该 item 所属桶]`（`LATENT_BY_BUCKET[ITEM_BUCKET[item]]`，即 `strength`）**升序**排序，平手按 `student_id` 决胜；
2. 取前 `n = int(round(len(该性别学生) * rate))` 名，构成**该生的持久标记集合**（一个人一旦「做不起 5 个引体向上」，两学年六个时点都是如此）；
3. 对标记集合内的学生，该项**每条记录**的原始值改为 `int(rng.integers(0, floor_raw))`，其中 `floor_raw = int(min(segment_thresholds(table, item, sex, 该记录的 age_group)))`（男 大一二 = 5、大三四 = 6，随 Ruling 56 的龄组走）；逐条重抽次数，体现真实测量波动（0、2、1、3…）；
4. 该项的 `realised` 得分 = `score_item(table, item, 溢出值, sex, age_group)`，由 Ruling 17 的低侧夹取自动等于表内最低档分（男引体向上最低档 5 次 → **10 分**）。**不要写死 10**，一律走 `score_item`；
5. 标记集合外的学生完全不受影响，仍走 §4.2 的正常路径（该项档距 1 = 分辨率 1，实际无抖动）。

**为什么是 10%、为什么只对男生引体向上**：国标男生引体向上最低档是 5 次，而真实高校男生 0–4 次占比很高。不生成这一段会让力量维度低尾被截断 → 校内 P25 偏高 → 力量短板识别偏少 → **红色层被系统性低估** → Task 9 的 20/45/35 断言难以达标。10% 是保守值且可配，Task 9 若仍不达标会调高它。

**必须在代码注释与报告里写明的下游影响**：被标记学生的该项得分被钉死在底档，因此**该项的学年间趋势恒为 0（地板效应）**。Task 8 的趋势判定与 Task 9 的黄金用例必须容忍这一点。这条要写进报告的「前向约束」。

### 4.4 测试要求（Ruling 54）

至少新增以下几条，全部放在 `backend/tests/seed/`：

1. `test_jitter_never_crosses_a_score_band`：遍历 **6 项 × 2 性别 × 2 龄组 × 全部官方档**，每档抽 50 次抖动，断言 `score_item(抖动值) == 该档分`。这是 Ruling 54「逐档回验」要求的落地形式（回验放在测试里而不是运行时，理由见 §4.2）。
2. `test_jittered_values_respect_measure_resolution`：同上遍历，断言每个抖动值都是 `10 ** -d` 的整数倍（用整数单位判，别用浮点取模）。
3. `test_jitter_is_effective_where_the_band_is_wider_than_resolution`：对 `vital_capacity`、`sit_and_reach`、`standing_jump`、`distance_run`、女生 `strength_count` 这五处，断言同一档的 50 次抖动**至少产生 2 个不同取值**；对 `sprint_50m` 与男生 `strength_count`，断言抖动恒等于端点（**钉住 §4.1 的结论，防止后来人「顺手」把 50 米改成 0.01 s**）。
4. `test_full_dataset_raw_values_are_not_all_band_endpoints`：在 500 人配置下跑 `build_dataset`，断言 `vital_capacity_ml` 列的**不同取值个数 > 官方档位数**（即数据里出现了非阈值读数）。这是「一眼看出是造的」那个症状的端到端回归。
5. `test_jitter_can_be_disabled_by_config`：`jitter_within_band=False` 时，全部原始值恰为 `raw_from_score` 的端点（保留旧行为的开关必须是真开关，不能是装饰品）。
6. `test_sub_floor_targets_the_weakest_students_by_latent`：断言被标记的男生数 == `int(round(男生数 * 0.10))`；且**不存在**「被标记者的 `latent_strength` 高于某个未标记者」的情况（单调性——这是 §4.3 修正的核心性质）。
7. `test_sub_floor_values_are_below_the_table_floor`：被标记者的 `strength_count` 全部落在 `[0, floor_raw)` 内且为整数；其 `score_pull_up_or_sit_up` 全部等于 `score_item` 对底档的返回值；未标记者的 `strength_count` 全部 `>= floor_raw`。
8. `test_sub_floor_rate_rejects_unknown_keys`：传 `{"male:no_such_item": 0.1}` 必须 `ValueError`，且异常消息里含合法键清单。
9. `test_sub_floor_can_be_disabled`：`sub_floor_rate={}` 时无任何记录低于表内最低档。

**回归**：改动前先跑一次 `pytest -q`（应为 225 passed）记下基线；改动后全部测试（含新增）必须绿，且 `-W error` 同样全绿。

**已有测试可能需要同步调整**（调整须在报告里逐条说明理由，不得为了过测而放宽断言）：
- `test_generated_raw_values_roundtrip_through_the_official_table`（见 §3）
- `test_indicator_correlation_is_realistic`：抖动不改得分、表下溢出改得分，相关系数会变。**只允许调整断言阈值，且必须报告新的实测值**；若跌破 0.4，上报，不要私自改潜变量载荷。
- `test_same_seed_produces_identical_dataset` / CSV SHA256：输出字节必然全变，这是预期。请**重新做一遍可复现性取证**（两次独立 CLI 进程、三个 CSV 的 SHA256 前 16 位逐一相同；换 `seed=1` 三个文件全不同），并把新的哈希前 16 位写进报告。

---

## 5. 明确不要做的事

- 不改 `app/domain/indicators.py`（含不给 `_lower_is_better` 加公开别名——用 §4.2 说的办法判方向）。
- 不实现 `latent_mean` 的二分法反推（那是 Task 9，见 progress.md 关切 ④）。
- 不改 `sections.py` 的编班逻辑（Ruling 55 已核实）。
- 不放宽上一轮已接受的处置：关切 ②（`make_sections` 第四参数 `latents` 必需无缺省）、③（体脂率测试跳空 + 分母守卫）、⑥（`score_*` 列注入后不自洽，有意为之）、⑧（`generate.py` 不拆）、⑨⑩⑪⑫。
- 不动 `write_csv` 的三个文件契约、`allow_nan=False`、`make_batch_key`、日期零填充（Ruling 35/36/37/38/39）。
- 不加 `students.csv`。
- 不做本简报未要求的重构、注释补全、类型标注。

---

## 6. 交付

1. 全部改动提交为**一个** commit，message 形如：
   `fix: 档内抖动与表下溢出使原始值脱离档位端点，上学年按上学年年龄组查表`
   正文列出 Ruling 54/55/56 三条与关键实测数字。
2. 把本轮内容**追加**到 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-report.md` 末尾（新章节标题：`## Fix Round 1`），包含：
   - Ruling 56 改动前的失败输出证据（§3 要求的那一条）；
   - 新旧测试数（基线 225 → 新值）；`-W error` 结果；耗时；
   - 新的三个 CSV SHA256 前 16 位 + `seed=1` 的差异性取证；
   - 相关系数新实测值、肺活量不同取值个数、被标记男生数与其 `strength_count` 分布（0/1/2/3/4 各多少个）；
   - 逐条列出被调整的既有测试及理由；
   - **关切章节**：任何你认为简报写错了、做不到、或有更好办法的地方。上一轮 12 条关切里 3 条变成了裁定，这一轮同样欢迎。
   - **前向约束章节**：至少包含 §4.3 末尾那条地板效应，供 Task 8/9 派单使用。
3. 报告写完后用 shell 复核文件确实变长（`(Get-Item <report>).Length`），并在报告末尾附上 `git log --oneline -1` 与 `git status --short` 的输出。

**报告文件已 31 KB，追加即可，不要重写整个文件。**
