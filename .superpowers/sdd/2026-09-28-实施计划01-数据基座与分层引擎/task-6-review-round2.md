# Task 6 fix round 2 复审

评审范围：`3b10f5e..bed07ed`（8 文件 +1579/−119）。评审方式：只读 + 独立探针复算，未改动任何受版本控制的文件，未创建 `backend/pe.db`，未生成 `backend/data/seed/*.csv`（哈希取证写到 `%TEMP%`，用后已删）。

---

## 结论

**PASS_WITH_CONCERNS** —— C1/C2/M1/M2/M5 与 4 条被指派的 Minor **全部真修好了**（不是只让测试变绿：我用**自己从 spec §6.3 正文翻译的第三份分类器**逐人复算，500/500 一致，且从原始值正查的生产侧路径同样 500/500 一致）；新发现 **0 Critical / 1 Major / 12 Minor**，Major 与多数 Minor 落在**账本与计划文本**上而非代码上——其中「Task 9 可行池会先枯竭的是波动大」这条前向约束**实测是错的**（先枯竭的是持续下滑），且它开出的药方对该失效无效，必须在 Task 9 派单前更正。

---

## 上一轮缺陷的逐条闭环核对

### C1 `trend_label` 方向反转 —— **已修好**

我自己写了第三份 spec §6.3 实现（权重从 spec §4.2 表格手抄成 `SPEC42` 字典、总分自己写 `sum(w*s)//100`、判定表按 §6.3 表格文字逐行翻译，**既没抄 `_oracle` 也没调用 `_weighted_total`**），对 500 人逐一分类。

```
MISMATCHES (my independent oracle vs trend_label) = 0
label       n     mean  median     pos%   min   max
持续下滑      100    -8.17    -8.0    0.00%   -15    -2
波动大        75    +2.73    +3.0   82.67%    -2    +8
稳步提升      125   +14.26   +14.0  100.00%    +6   +23
稳定        200    +1.43    +1.0   77.50%    -1    +4
```

与 `progress.md:761-764` / 报告 G2 **逐格相同**。「持续下滑」100/100 全为负、「稳步提升」125/125 全为正 —— 方向彻底翻回正确一侧。

根因代码已**结构性删除**，不是只改了运算符：

```
$ git grep -nE "prev_offset|-= offsets|_trend_offsets|ITEM_TREND_JITTER_SD" -- backend
(无输出，exit=1)
```

基线 `3b10f5e:backend/app/seed/fitness.py:566` 的 `target -= offsets[student_id][item]` 与整个 `_trend_offsets` 函数都已不存在；`TrendProfile` 的字段直接改名为 `delta_target_range`（`fitness.py:220`），符号约定写进 `fitness.py:203-207` 与 spec §6.3:397 / §10.5:686。**没有留下第二个可以接反的地方。**

### C2「波动大」结构性不可达 —— **已修好**

```
-- 波动大 shape counter (ups,downs,zeros,max|d|>=10) --
Counter({(3, 3, 0, True): 75})
波动大 sex split = {'male': 28, 'female': 47}
```

75/75 恰好 3 正 3 负、0 个零、幅值达标。行序守卫**存在且有效**：`tests/seed/test_trend_oracle.py:147 test_volatile_outranks_declining`（我手算复核：Σw·curr = 1125+1275+1260+850+850+630+1260 = 7250 → 72，上学年 75，`Delta` = −3 > −5，但 3 项各降 12 ≤ −5 → 第二分支确实会触发，故行序写反时本条必红）。

我进一步量化了 500 人全覆盖那条测试对行序的分辨力：把生成器的行序改回「持续下滑优先」，**75 名波动大学生全部会被翻面**（75/75 都满足 `≥3 项 delta ≤ −5`，且无一人 `Delta ≤ −5`）——所以 `test_oracle_agrees_with_trend_label_for_all_500_students` 本身就是一条 75 人份的行序守卫，不是只靠那一条黄金用例。

**但见「规格与裁定本身的问题 (b)」：波动大的 `(3,3,0,True)` 是构造**必然**，不是独立验证的成果，而且计划为此 mandated 的校正分支可证明永不执行。**

### M1 `prev_offset` 逐项偏移 vs 总分阈值 —— **已修好**

`TREND_PROFILES` 的 `delta_target_range` 现在是**国标加权总分（0–100）**的抽样区间（`fitness.py:226-237`），注入在加权空间定标，且先扣 BMI 贡献（`fitness.py:546` `b = ITEM_WEIGHTS[BMI] * bmi_delta / 100.0`，`:672` `base = 100.0 * (delta_target - b) / w_free`）。

实测配额**精确命中**配置值：持续下滑 100/500 = **20.0%**（配置 0.20；上一轮是 46%）。

### M2 `SeedConfig` 缺 `latent_sd` —— **已修好**

```
$ git diff 3b10f5e..bed07ed -- backend/app/seed/config.py
+    latent_sd: float = 1.0
```

且**真的接进了 rng**：`fitness.py:266` `fitness = rng.normal(cfg.latent_mean, cfg.latent_sd, total)`。3 条测试（字段存在+缺省 1.0 / 经验 sd 随 σ 变且三点单调 / σ 传到三个桶潜变量）。σ 没被使用时第二条会红（`latent_sd=2.0` 的经验 sd 会是 1.0，落在 `[1.8, 2.2]` 之外）。我实跑 `latent_sd ∈ {0.5, 1.5, 2.0, 2.5}` 全部 OK。

### M3 报告 F1.2 的 1213/2376 = 51.1% —— **部分修好**

计划已更正：`Document\...实施计划01...md:934` 现在写「**334 / 2376 个上学年单元格（14.1%）**（Ruling 67 更正：此前写的 1213/2376 = 51.1% …高估 3.6 倍）」。

**但报告侧没改**，而 `progress.md:722` 明写「计划 `:887` 与报告 `:400` 的数字已更正」：

```
$ Select-String -Path task-6-report.md -Pattern '1213|51\.1%'
report:400: | 两表给出**不同**得分的 (记录, 项) 单元格 | **1213 / 2376 = 51.1%**；132 名跨线学生**人人**至少有一格能被分辨 |
report:613: 缺陷本身是真的、也依然承重（1213 个单元格两表给出不同得分、趋势被低估 0.83 分/项，见 F1.2）
```

`:400` 处**无任何作废/勘误标记**（唯一更正在 555 行之外的 `:955`）。`progress.md:801` 那条延后 Minor 列举的过期观测量清单里也没有 1213/51.1%。→ 见缺陷 Minor-11。

### M4 `backend/pe.db` 被混合 seed 污染 —— **已修好**

```
$ Test-Path .\pe.db      -> False
$ Test-Path .\data\seed  -> True
$ Get-ChildItem -Recurse .\data
  backend\data\seed               (目录，空)
  backend\data\indicator_ranges.yaml   4351
  backend\data\national_standard_2014.csv  21412
  backend\data\README_national_standard.md 10830
```

`pe.db` 不存在；`data/seed/` 是**空目录**（LastWriteTime 2026/9/30 1:33:50，即控制者删除三个过期 CSV 的时刻）——关切 5 那条哑弹已拆除。我全程未创建 `pe.db`（哈希取证走 `%TEMP%`）。

### M5 没有任何测试钉住趋势方向 —— **已修好**

三层守卫，我逐条验过其**有效性**而非存在性：

1. `test_declining_group_really_declines_and_improving_group_really_improves`：断言「持续下滑」中位数 < 0 且负占比 ≥ 95%、「稳步提升」中位数 > 0 且正占比 ≥ 95%。C1 回归会让它当场红（实测中位 −8.0 / +14.0，负占比 100% / 正占比 100%）。
2. `test_oracle_agrees_with_trend_label_for_all_500_students`：500 人全覆盖，不一致数必须为 0。
3. 10 条手算黄金用例。**我逐条手算复核了全部 10 条的算式，全部正确**，无一条是「跑一遍实现把输出当期望值」：
   - `test_volatile_outranks_declining` Σw·curr = 7250 → Delta −3，3 项 ≤ −5 → 行序可分辨 ✓
   - `test_volatile_by_three_up_three_down_with_big_swing` 7325 → −2，max|d| = 13 ✓
   - `test_declining_by_total_drop_only` 7000 → −5（恰在阈值上），`#{≤−5}` = 2 < 3 ✓
   - `test_declining_by_three_items_dropping_five_only` 7405 → −1，3 正 3 负但 max|d| = 5 < 10（同时钉住波动大需要**两个**条件）✓
   - `test_declining_by_item_branch_even_when_the_total_rises` 7505 → 0 ✓
   - `test_improving_needs_both_...` 8095 → +5（恰在阈值上）✓
   - `test_single_item_drop_of_six_blocks_improving` 8190 → +6 但 min d = −6 → 稳定 ✓
   - `test_stable_when_nothing_crosses_any_threshold` 7490 → −1 ✓
   - `test_total_rise_of_four_is_stable_not_improving` 7925 → **+4**（从下方钉住 ≥ +5 边界）✓
   - `test_one_zero_delta_makes_volatile_unreachable` 7545 → 0，**并显式断言 `deltas[DISTANCE_RUN] == 0`** 与 `max|d| == 13 >= 10`——即幅值条件成立、只有零项把分裂打破，delta=0 是真的构造出来了，不是碰巧 ✓

`test_weighted_total_is_the_floored_weighted_sum_of_seven_items` 的期望值也全是手算字面量（我复核 7500//100=75、6600//100=66、6800//100=68、**7615//100=76**（钉住 `//` 而非 `/` 或四舍五入）、六项和 85、BMI 15），不是从被测函数读回来。

### 4 条被指派的 Minor

| # | 状态 | 取证 |
|---|---|---|
| **m1** AST 守卫漏两种写法 | **已修好，但仍留一个新缺口** | 判据从「7 个精确串」改为「调用的**末段属性名**」；20 条参数化自证测试**确实**把违规源码写进 `tmp_path/fake_module.py` 再断言 `_scan(tmp_path)` 非空且指向预期 token（不是断言函数存在的空转），+1 条负对照（`Generator` 只作类型标注、`cfg.seed` 只作属性读取、`timepoint_date(...)`）断言 `_scan == []`；`_scan` 开头保留 `assert root.is_dir()`。**但 `np.random.rand/randn/normal/uniform/integers/permutation/set_state/get_state` 全部 MISSED** → Minor-1 |
| **m2** `_cell` 对 `np.float64` 写坏单元格 | **已修好（float64/integer），但 `np.floating` 仍漏** | `generate.py:362` `repr(float(value))` + `:363-364` `np.integer` 分支；自证测试走**完整落盘路径**（八个测量列换成 numpy 标量 → `inject_dirty` → `write_csv` → 读回文本断言无 `np.float64(` / `np.int64(`），不是只调一次 `_cell`。**但 `_cell(np.float32('nan'))` 原样返回、CSV 会写出 `'nan'`** → Minor-2 |
| **m3** `fitness.py:28` docstring 撒谎 | **已修好** | `git grep -n "唯一会碰磁盘" -- backend` → **0 命中**；`fitness.py:28-31` 改为「本模块自己不 open 任何文件……`app.seed` 里真正碰磁盘的是 `generate.write_csv` 与 `generate._ranges`」，与事实一致 |
| **m4** `N(0, 0.6)` 记法歧义 | **已修好（代码侧）** | `ITEM_TREND_JITTER_SD` 与那处 `rng.normal` **整体删除**（`git grep` 0 命中），改成有界零和整数抖动 `_zero_sum_jitter`（`rng.integers` 的参数是界不是尺度，无歧义）；`LATENT_LOADINGS` 注释改为「ε ~ 正态(均值 0, sd 0.6)」+ `# (载荷, 残差 sd)`。**计划 Step 3 已由控制者按 Ruling 73 改成 `sd =`**（`:876-878`）✓。但接受关切 7 的理由是错的 → 规格问题 (e) |

### 4 条延后 Minor 是否被误碰（简报 §4 末条要求不修）

全部**正确地未动**：`target_layer_dist` 仍无任何代码消费者（`git grep` 只命中 `config.py` 的字段与注释）；`test_inject_dirty_leaves_clean_records_untouched_when_all_rates_are_zero` 在 diff 里只作为**上下文行**出现（未改）；duplicate 副本放置逻辑在 `generate.py` 的 diff 里 0 命中；报告 `:400` 的过期观测量仍未就地标注。

---

## 验证过的命令与实测输出

```
$ cd backend; python -m pytest -q
280 passed in 9.39s

$ cd backend; python -m pytest -q -W error
280 passed in 10.90s          # 无 warnings summary 段

$ cd backend; python -m pytest -q tests/seed/test_fitness.py tests/seed/test_generate.py \
      -k "jitter or sub_floor or age_group or section or roundtrip or seed_database or trend_labels or correlation"
15 passed, 46 deselected in 2.90s     # Ruling 54/55/56/58 的回归全绿

$ python -m pytest tests/seed --collect-only -q          -> 75 tests collected
$ python -m pytest tests/seed/test_generate.py ...       -> 46
$ python -m pytest tests/seed/test_fitness.py ...        -> 15
$ python -m pytest tests/seed/test_trend_oracle.py ...   -> 14

$ git diff --numstat 3b10f5e..bed07ed
14  0   backend/app/domain/indicators.py
 6  0   backend/app/seed/config.py
661 89  backend/app/seed/fitness.py
 9  1   backend/app/seed/generate.py
46  1   backend/tests/domain/test_indicators.py
115 0   backend/tests/seed/test_fitness.py
195 28  backend/tests/seed/test_generate.py
533 0   backend/tests/seed/test_trend_oracle.py      # 合计 +1579 / -119 ✓

$ git diff --stat 3b10f5e..bed07ed -- backend/app/seed/{sections,population,body_comp,survey}.py
(空 → 四个文件一字未动)

$ git diff 3b10f5e..bed07ed -- backend/tests | Select-String '^-'
  → 删除行只有：1 条 import 重排（test_indicators.py）、1 条 import 展开（test_generate.py）、
    `import ast` 上移、以及旧 AST 守卫体（被抽成 _scan/_offenders_in 后**加强**）。
    无任何等号→容差、全称→存在、== → in 的放宽。

$ Test-Path .\pe.db  -> False
$ git grep -nE "classify_trend|national_total|def derive|from app.domain.derive" -- backend/app/seed
  → 4 命中，全部是 docstring 引用（fitness.py:147/152/460/761），$Test-Path backend\app\domain\derive.py -> False
```

**可复现性（两次独立 Python 进程 + seed=1）**

```
进程 A: fitness.csv 244496B 498AA3256678B01A | body_comp.csv 107745B 1234025C05843B27 | survey.csv 276193B 835A98FCC0779B51
进程 B: fitness.csv 244496B 498AA3256678B01A | body_comp.csv 107745B 1234025C05843B27 | survey.csv 276193B 835A98FCC0779B51
seed=1: fitness.csv 244632B 11A6651B4CEA9A58 | body_comp.csv 107719B 242BE5A968C10594 | survey.csv 277830B 3245D2EAFEF7FA9D
目录内恰好 3 个文件、无 students.csv
```

六个哈希与报告 G7 **逐字相同**；`seed=1` 三个全不同。另加同进程内三次 `build_dataset(SeedConfig())` 的 `fitness`/`body_comp`/`survey`/`dirty_marks` 全部 `==` 相等 → 无隐藏全局状态（`standard()` 单例、`_ranges_cache` 都不影响）。

**代码走查：两趟拆分后的随机流是否依赖 dict/set 迭代序** —— 逐处核过，**没有**：`all_ids`/`population`/`free`/`WEAKNESS_ITEMS` 都是列表或元组序；`_trend_labels` 的 `shuffled.sort(key=0/1)` 依赖 Python sort 的稳定性，组内序 = `rng.permutation` 序；`_initial_deltas` 的 `sorted(free, key=(curr[item], _ITEM_INDEX[item]))` 与 `_correction_move` 的 `sorted(free, key=(-ITEM_WEIGHTS[item], _ITEM_INDEX[item]))` 都是**全序**（`_ITEM_INDEX` 唯一）；`sub_floor_pairs` 是 set 但**只用于成员判定**、从不迭代抽数；校正循环**不消耗随机数**（故轮数不影响可复现性）。跨进程字节一致是这一走查的硬证据。

---

## 缺陷（按严重度）

### Critical

无。

### Major

#### Major-1 交给 Task 9 的前向约束把「先枯竭的可行池」认错了，且开出的药方对该失效无效

- **位置**：`progress.md:807`（前向约束 Task 9）与 `task-6-report.md:1032`（G12 #10）
- **现象**：两处都写「若把人群推高（`max curr` 普遍 > 84），**波动大可行池会先枯竭**并抛 `ValueError`……正确做法是同步调 `swing` 上限或 `trend_mix`」。实测：

```
latent_mean=-1.5 -> OK          latent_mean=+0.5 -> ValueError: pool short 持续下滑: need 100 have 88
latent_mean=-1.0 -> OK          latent_mean=+1.0 -> ValueError: pool short 持续下滑: need 100 have 37
latent_mean=-0.5 -> OK          latent_mean=+1.5 -> ValueError: pool short 波动大:   need 75 have 57
latent_mean=+0.0 -> OK          latent_mean=+2.0 -> ValueError: pool short 波动大:   need 75 have 26
```

  `波动大` 只在 μ ≥ +1.5 时才先枯竭；在 Task 9 最可能探索的小幅区间（μ = +0.5 ~ +1.0）**先枯竭的是持续下滑**，其余量只有 1.52× → 0.88×（μ=+0.5，88/100）。而 `swing` 根本不进入持续下滑的窗口计算（`_delta_target_windows:550-571` 的持续下滑分支只读 `delta_target_range` / `jitter` / `head_up`），**照这条约束调 `swing` 一点用都没有**。

  **这条约束与实现者自己报告里的数据自相矛盾**：报告 G5（`:838`）明写「**最紧的是「持续下滑」（1.50×）**，因为它的判据同时要求 `head_up` 够大**和**符号纯度」，并给出四类余量 波动大 **3.47×** / 持续下滑 **1.50×** / 稳步提升 2.58×。同一份报告的 G12 #10（`:1032`）却说「**波动大的可行池会先枯竭**」。余量最小的一类不可能后枯竭——这个矛盾在我实测的 μ 扫描里立刻显形。
- **后果**：Task 9 的实现者按这条约束调 `swing`，`ValueError` 照抛，会误判成「生成器有 bug」并可能去放宽判据——那正是这条约束自己想阻止的行为。红层规模恰恰取决于把人群推**高**还是推**低**，所以 μ > 0 是必然要试的一侧。
- **建议**：把该条改成「**持续下滑池先枯竭**（μ ≈ +0.5 时 88/100），正确做法是调 `trend_mix` 或放宽 `_delta_target_windows` 里持续下滑的 `CORRECTION_RESERVE`/`jitter` 预留；只有 μ ≥ +1.5 之后才轮到波动大，那时才该调 `swing`」。
- **置信度**：**高**（直接命令输出，四档 μ 全部实测）。

### Minor

#### Minor-1 AST 随机源守卫仍漏掉整个「numpy 遗留全局态」类写法

- **位置**：`tests/seed/test_generate.py:504-513`（`CLOCK_METHODS` / `RNG_SOURCES`）与 `_offenders_in:531-537`
- **现象**：把守卫函数直接从测试模块加载出来喂探针源码：

```
CAUGHT  | np.random.seed(0)                 | ['fitness.py:2:np.random.seed']
CAUGHT  | np.random.RandomState(0)          | ['fitness.py:2:np.random.RandomState']
MISSED  | x = np.random.rand(10)            | []
MISSED  | x = np.random.randn(10)           | []
MISSED  | x = np.random.normal(0, 1, 10)    | []
MISSED  | x = np.random.integers(0, 5, 10)  | []
MISSED  | x = np.random.uniform(0, 1, 10)   | []
MISSED  | x = np.random.permutation(10)     | []
MISSED  | np.random.set_state(np.random.get_state()) | []
```

  这些函数读的是 numpy 的**遗留全局 RandomState**，未被 `np.random.seed()` 播种时由 OS 熵自动播种 → 输出**不可复现**。守卫的判据是「末段属性名 ∈ 两个集合」，而 `rand`/`normal`/`permutation` 都不在其中。
- **后果**：`progress.md:594` 那句「把『隐藏的第二随机源』这一可复现性的经典杀手变成**结构性不可达**」是不成立的。今天 `app/seed` 里没有这类调用（`git grep -nE "np\.random\.(rand|randn|normal|uniform|integers|permutation|shuffle|choice|sample|set_state|get_state)" -- app/seed` → 0 命中），所以是**潜在**缺口而非活缺陷；但 spec §10.8 把可复现性列为硬要求，Task 9 调参时最容易顺手写 `np.random.normal(...)`。
- **建议**：加一条判据「`ast.unparse(node.func)` 以 `np.random.` / `numpy.random.` 开头且末段不是 `default_rng` → 违规」，比枚举函数名可靠；并在 `FORBIDDEN_WRITINGS` 里补 `np.random.rand(10)` / `np.random.normal(0,1,10)` 两条自证。
- **置信度**：**高**（探针直接调守卫函数，逐条输出）。

#### Minor-2 `_cell` 的 m2 修法只覆盖 `np.float64` 与 `np.integer`，`np.floating` 其余成员同时绕过标量转换**与** Ruling 39 的有限性守卫

- **位置**：`app/seed/generate.py:353-365`
- **现象**：

```
np.float64(1.5)  isinstance(float)=True   -> '1.5'            ✓
np.float64(nan)                          -> RAISED ValueError ✓
np.float32(1.5)  isinstance(float)=False  -> np.float32(1.5)  csv-would-write='1.5'
np.float32(nan)  isinstance(float)=False  -> np.float32(nan)  csv-would-write='nan'   ← 绕过守卫
np.float32(inf)  isinstance(float)=False  -> np.float32(inf)  csv-would-write='inf'   ← 绕过守卫
np.int64/int32/uint8(7)                  -> 7                 ✓
```

  `np.float64` 是 Python `float` 的子类所以进了 `isinstance(value, float)` 分支；`np.float32`/`np.float16` **不是**，于是既不进 `repr(float(...))` 也不进 `np.integer` 分支，直接 `return value` 落到 `csv.writer` 的 `str()`，且**跳过了 `math.isfinite` 检查**。
- **后果**：`generate.py:347-351` 的 docstring 说这一改「把『将来漏包一次』从运行时事故变成**结构性不可达**」——对 float32 不成立。一个 `np.float32('nan')` 会原样写成 `nan` 落盘，而 Ruling 39 的全部意义就是拦住这个字面量（适配器 `float('nan')` 与任何阈值比较恒为假、全程零报错）。Task 10 若用 dtype 指定的 numpy 数组喂 `_cell` 就会踩到。
- **建议**：把 `isinstance(value, float)` 改成 `isinstance(value, (float, np.floating))`（有限性检查随之覆盖全部浮点），`np.integer` 分支保持不变。补一条 `_cell(np.float32("nan"))` 必须 `pytest.raises(ValueError)` 的断言。
- **置信度**：**高**（直接调 `_cell` 逐类型实测）。

#### Minor-3 `_correction_move` 五条分支里有三条在整个可信配置空间内**从未执行过**，且 `direction = −1` 的那一半循环是死代码

- **位置**：`app/seed/fitness.py:720-735`
- **现象**：包裹 `_correction_move` 统计分支命中，跑 **16 个配置 × 500 人 = 8000 次构造**（`latent_mean` −2.0…+0.25 六档、`latent_sd` 0.5…2.5 四档、6 个 seed）：

```
latent_mean=-2.00  branches={'actual=稳定 w=20': 15, 'fallthrough(actual=稳步提升) w=20': 54}  directions={1: 69}
latent_mean=-1.50  branches={'fallthrough(actual=稳步提升) w=20': 50, 'actual=稳定 w=20': 17}  directions={1: 67}
latent_mean=-1.00  branches={'fallthrough(actual=稳步提升) w=20': 28, 'actual=稳定 w=20': 13}  directions={1: 41}
latent_mean=-0.50  branches={'fallthrough(actual=稳步提升) w=20': 17, 'actual=稳定 w=20':  9}  directions={1: 26}
latent_mean=+0.00  branches={'fallthrough(actual=稳步提升) w=20': 15, 'actual=稳定 w=20':  4}  directions={1: 19}
latent_mean=+0.25  branches={'actual=稳定 w=20': 9, 'fallthrough(actual=稳步提升) w=20':  7}  directions={1: 16}
latent_sd=0.5/1.5/2.0/2.5、seed=1/7/99/12345/424242/31337  → 同样只有这两条分支、directions 全是 {1: n}
```

  即：`shape-fix (actual == 波动大)`（`:721-722`）、`volatile-swing (label == 波动大)`（`:723-726`）、`actual == 持续下滑`（`:729-734`，含 `worst` 项那条特例）**0 命中**；`pick` 的 `direction = −1` **0 命中**；被推动的项权重**恒为 20**（`focus=biggest` 的两条路径因此也 0 命中）。生产配置上 19 次校正的分布是 `{'稳定': 15, '持续下滑': 4}`，全部方向 +1。
- **后果**：本轮新增的最复杂逻辑里约 15 行（含 Ruling 65 明文要求的波动大幅值校正、以及「持续下滑第二分支被误触时推 `worst` 项」这个非平凡的推理）**既没被执行过也没有测试**。Task 9 调 μ/σ 也唤不醒它们（16 个配置全试过）。缺陷不会静默产出错数据——`test_oracle_agrees_with_trend_label_for_all_500_students` 是真正的兜底——但它意味着这部分代码的正确性**从未被任何证据支持过**。
- **建议**：二选一，且要在账本里记一笔：(a) 承认波动大分支可证明不可达（见规格问题 (b)），删掉 `:723-726` 与计划 `:918` 那一段；(b) 若要保留为防御性代码，给它一条直接打 `_correction_move` 的单测——具体输入：`label="波动大"`、`curr` 六项全 84、`deltas` 三项 +1 三项 −1（幅值不足 10），断言返回的 `direction` 使 `|delta_biggest|` 增大。
- **置信度**：**高**（16 配置分支计数直接输出）；「波动大分支可证明不可达」的**证明**见规格问题 (b)，置信度高。

#### Minor-4 四条「响亮失败」守卫全部零测试覆盖

- **位置**：`fitness.py:805`（校正推不动 → RuntimeError）、`:813`（超 8 轮 → RuntimeError）、`:606`（可行池不足 → ValueError）、`:618`（余下的人里有稳定不可行者 → ValueError）
- **现象**：

```
$ git grep -nE "可行池不足|趋势校正|推不动|轮仍未达判据|CORRECTION_MAX_ROUNDS" -- backend/tests
backend/tests/seed/test_fitness.py:522:    assert captured["max_rounds"] <= fitness.CORRECTION_MAX_ROUNDS
$ git grep -nE "pytest.raises" -- backend/tests/seed
backend/tests/seed/test_fitness.py:469:        with pytest.raises(ValueError) as excinfo:   # 这是 sub_floor_rate 未知键（round 1 的）
```

  唯一相关断言是「轮数不破上限」；`test_fitness.py:505-506` 的 docstring 自己承认「『RuntimeError 次数为 0』由『测试通过』隐含」。**这些守卫不是空转的**——我用绕过可行域筛选的合成 `info` 直接打 `_settle_prev_targets`，5 个输入里 4 个抛出：

```
RAISED RuntimeError (趋势校正 8 轮仍未达判据…标签「波动大」)   波动大 with all curr=100
RAISED RuntimeError (趋势校正推不动了…标签「持续下滑」)         持续下滑 with all curr=100
RAISED RuntimeError (趋势校正推不动了…标签「稳步提升」)         稳步提升 with all curr=0
OK   rounds=0                                                稳定 with all curr=100
RAISED RuntimeError (趋势校正推不动了…标签「稳定」)             稳定 with all curr=0
```

  `ValueError` 路径同样可达（`latent_mean=+0.5` 就抛，见 Major-1）。
- **后果**：守卫今天有效，但**没有任何测试钉住它有效**。若将来有人把 `raise` 改成 `return prev_targets, rounds`（静默放行），或把 `if len(pool) < need` 改成 `pool[:need]` + 余下改标签，280 条测试仍会全绿——因为兜底的 oracle 测试只在**当次数据**上比对，而静默放行恰好会让当次数据自洽地错。Ruling 65/70 的全部意义就是「响亮失败而不是静默改标签」，这一层没有测试。
- **建议**：两条就够，都用上面已经验证过的具体输入：① `pytest.raises(RuntimeError)` 打 `_settle_prev_targets("稳定", info_with_curr_all_zero, {i: 0 for i in SIX}, ...)`；② `pytest.raises(ValueError, match="可行池不足")` 打 `build_dataset(SeedConfig(latent_mean=0.5))`（实测 88/100，必然抛）。
- **置信度**：**高**（`git grep` 双模式取证 + 合成输入实测抛出）。

#### Minor-5 `_settle_prev_targets` docstring 的「每轮至少移动 2 分 / 循环单调」对两条 `focus=biggest` 分支不成立

- **位置**：`fitness.py:764-766`（docstring）vs `:720-726`（代码）
- **现象**：docstring 写「每轮至少让 `Delta'` 朝目标移动 `w_max × 10 / 100 = 2` 分（最坏情况下被端点档削到 1 分）」。但 `:722` 与 `:726` 的 `pick(direction, biggest)` 推的是 **`|delta|` 最大**的那一项，不是权重最大的项；六项权重是 `{15, 20, 10, 10, 10, 20}`，故这两条分支每轮只移动 `w_biggest × 10/100`，**最低 1.0 分**（当 `biggest` 是 w=10 的坐位体前屈/立定跳远/引体向上时）。更强的一点：`:721-722` 的 shape-fix 分支的目标是**缩小 `|delta_biggest|`**，它对 `Delta'` 的影响方向与该生标签所需的 `Delta'` 方向**无关**，可能朝反方向走。「循环单调」因此只对 `actual == 稳定` / `actual == 持续下滑` / fallthrough 这三条净方向分支成立。
  （「被端点档削到 1 分」这半句是对的：国标顶端档距 100→95→90 是 5 分，推 `prev_target` 10 分只移动 5 分 → `Delta'` 动 `20×5/100 = 1` 分。）
- **后果**：`:764-766` 是「上限 8 轮够用」这个论断的唯一依据，而它对两条分支不成立。实测 16 个配置的最大轮数是 **3**（`latent_mean=−1.5`：`{0:448, 1:38, 2:13, 3:1}`），8 轮仍有 2.7× 余量，所以**结论侥幸正确、论证不对**。这与本项目已记录 7 次的「用一个聚合论断支撑一条硬约束」是同一类。
- **建议**：docstring 改为「净方向的三条分支每轮移动 ≥ 1 分（w=20 且非端点档时 2 分）；shape-fix 分支不保证 `Delta'` 单调，只保证 `max|delta'|` 单调下降。**有界性**由 `CORRECTION_MAX_ROUNDS` + `RuntimeError` 提供，不靠单调性」；把实测最大轮数 3（16 配置）写进去作为 8 这个上限的依据。
- **置信度**：**高**（代码行 + 权重表 + 16 配置轮数直方图）。

#### Minor-6 `_delta_target_windows` 的 docstring 引用了计划里已经不存在的公式，而计划现在写的那条公式与实现也不等价

- **位置**：`fitness.py:525-530`（docstring）、计划 `:920-925`、`progress.md:774`（Ruling 70）
- **现象**：两处不一致叠在一起。
  1. docstring 说「**约束 2 用的是 `min_i`，不是计划正文那句 `Σ_i w_i·(100 − curr_i) ≥ 100·|Delta_target|`**」——但计划在 Ruling 70 之后**已经**改成 `min_i` 形式了（`:920` 标题就是「判据是逐项最小余量，不是加权和」），加权和只作为被否决的反例出现在 `:920` 的叙述里。读者会以为实现者偏离了现行计划。
  2. 计划 `:923` 写的判据是 `min_i(100 − curr_i) ≥ |Delta_target| + 9`，实现的是 `|Delta_target − b| ≤ w_free · max(0, min_i room − jitter − CORRECTION_RESERVE) / 100`（`:558-571`）。两者**不等价**，且实现的是对的那个：均匀分配下每项承担 `100·Delta_6/w_free ≈ 1.176·Delta_6`，计划的字面式**漏了这个 1.176 的放大**、也漏了 jitter。实测分歧：某生 `head_up = 25`、`Delta_target = −18`、`b = 0` → 计划字面式 `25 ≥ 27` 为假（判不可行），实现给 `magnitude = 85×(25−3−10)/100 = 10.2` → 窗口 `(−10.2, −6)`（判可行、只是收窄了抽样区间）。反方向也有：`head_up = 40` 时两者都放行，但计划式允许抽到 `−18` 而实现允许抽满 `[−18, −6]`。
     顺带核实 Ruling 70 的反例算术：`curr = (95,95,95,95,95,20)` 的 `Σ w_i(100−curr_i) = 15×5+20×5+10×5+10×5+10×5+20×80 = 1925 ≥ 1800` ✓ **加权和判据确实放行**；而实现给 `波动大/持续下滑/稳步提升 全 None`、`稳定 = (0.0, 0.0)` → **已被筛掉** ✓。计划的字面 `min_i` 式（`5 ≥ 27`）也把它筛掉。
- **后果**：Task 9 若按计划字面式重算「把人群推高到多少会让池枯竭」，会得到与实际不同的答案（字面式偏严，会**低估**持续下滑池）。
- **建议**：把计划 `:923-925` 三行替换成实现的窗口式（或明写「判据以 `_delta_target_windows` 为准，正文只给直觉」），并把 docstring `:525-530` 那句改成「计划 Ruling 70 已改为 `min_i` 形式；实现进一步把 `100/w_free` 的均匀分配放大与 jitter/校正预留算进去，故是**收窄抽样窗口**而不是布尔筛选」。
- **置信度**：**高**（三处文本对读 + 具体数值代入）。

#### Minor-7 `max(0.0, room − jitter − CORRECTION_RESERVE)` 的钳位让 27% 的人以**零宽窗口 + 零校正预留**被放进「稳定」池

- **位置**：`fitness.py:558`
- **现象**：

```
== 零宽窗口统计 ==
  波动大:   feasible=260 zero-width=260 min_width=0.000   (设计如此，波动大不设 Delta 目标)
  持续下滑: feasible=203 zero-width=  0 min_width=1.650 median=6.750
  稳步提升: feasible=487 zero-width=  0 min_width=5.450 median=12.000
  稳定:    feasible=489 zero-width=133 min_width=0.000 median=4.000

== room − jitter − CORRECTION_RESERVE ≤ 0 的学生 ==  count=144
   sid=3  room=0 window=(0.0, 0.0) label=稳定
   sid=17 room=5 window=(0.0, 0.0) label=稳定
   sid=18 room=0 window=(0.0, 0.0) label=稳定
```

  `room ≤ 12` 时钳位到 0，`magnitude = 0`，窗口塌成一个点 `(b, b)`——`Delta_target` 被**强制**等于 BMI 贡献、**没有任何校正预留**，而 `_delta_target_windows` 的注释（`:181-183`）说预留的用途正是「筛得太松会让校正循环把 `prev_target` 推出 `[0,100]` 之后再也推不动，最终 RuntimeError」。也就是说，这 133 人是**在没有预留的情况下被放行的**，与筛选的设计意图相反。
- **后果**：今天无害。我用三组这种配置各抽 400 次 `_initial_deltas` + `_settle_prev_targets`（共 1200 次）：`RuntimeError = 0`、`max_rounds = 0`；16 个配置 × 500 人也 0 次。原因是窗口塌成点后 `base = 0`、`delta_i` 只剩 ±2 的零和抖动，落档损失不足以把 `Delta'` 推出 `(−5, +5)`。**但「可行域筛选」这个名字对 27% 的稳定池已经名不副实**，而 Task 9 一旦调 `jitter` 或 `CORRECTION_RESERVE`，这 133 人的余量是 0。
- **建议**：把 `:558` 改成「`room − jitter − CORRECTION_RESERVE < 0` → 该类对该生不可行（`None`）」，或者至少在 docstring 里写明「room 不足时窗口塌成点、`Delta_target` 退化为确定值 `b`、校正预留为 0」，并加一条断言把这个退化行为钉住（具体输入：`curr = {六项全 100}`、`bmi_delta = 0` → 断言 `windows["稳定"] == (0.0, 0.0)` 而非 `None`）。
- **置信度**：**高**（钳位是代码里明写的 `max(0.0, ...)`；133/489 与 144 都是实测；「今天无害」有 1200 次合成 + 8000 次真实构造支撑）。

#### Minor-8 报告 G11④ 的「实际 `Delta'` **一律** ≥ 名义 `Delta_target`」是全称断言，实测有 17/500 反例

- **位置**：`task-6-report.md:981`
- **现象**：我按学生逐人配对名义与实测：

```
持续下滑 n=100 nominal mean=-9.92 range=[-17.48,-6.03] realised mean=-8.17 range=[-15,-2] mean bias=+1.75
        min per-student bias=-0.08 max=+5.41  negative-bias count=2
稳步提升 n=125 nominal mean=+12.15 range=[+6.05,+17.76] realised mean=+14.26 range=[+6,+23] mean bias=+2.11
        min per-student bias=-0.34 max=+5.24  negative-bias count=5
稳定    n=200 nominal mean=+0.03 range=[-1.92,+1.98] realised mean=+1.43 range=[-1,+4] mean bias=+1.40
        min per-student bias=-0.38 max=+4.42  negative-bias count=10
```

  三项均值偏差 **+1.75 / +2.11 / +1.40 与报告逐字相同** ✓，但「一律 ≥」不成立：17/500 的 `Delta' < Delta_target`（最小 −0.38）。原因是 `prev_i ≤ prev_target ⟹ delta_i' ≥ delta_i` 只在**连续**层面成立，而 `Delta'` 是两次 `//100` 之差、`Delta_target` 是连续抽值，双次向下取整可以吃掉最多约 1 分。
- **后果**：`progress.md:800` 那条延后 Minor 写的是「系统性上偏」（均值陈述，**正确**），所以账本没错；错的是报告里的全称量词。若 Task 9 有人按「一律 ≥」推断「`Delta'` 的下界就是 `Delta_target` 的下界」，会算错持续下滑组的极值（实测 `Delta'` 最小 −15，而名义最小 −17.48 —— 这个方向恰好印证了偏差，但也说明两者不是逐点序关系）。
- **建议**：报告 `:981` 改为「**平均**上偏 +1.4~+2.1 分；逐人看有 17/500 例外（最小 −0.38），因为 `Delta'` 经两次 `//100` 而 `Delta_target` 是连续量」。
- **置信度**：**高**（逐人配对实测，序列对齐由 label 序列相等断言保证）。

#### Minor-9 `test_trend_oracle.py` 的 docstring 声称与实现「没有共享任何一处代码或常量」，但它 import 并使用了 `_weighted_total`

- **位置**：`tests/seed/test_trend_oracle.py:8-10` 与 `:30-31`（声明）vs `:23`（`from app.seed.fitness import _weighted_total`）与 `:92` / `:433`（使用）
- **现象**：`_oracle` **函数本身**确实是独立翻译（四个阈值字面写死在 `:32-41`、判定表逐行对照 spec §6.3 我核过一致），但它吃的 `total_change` 由 `_weighted_total` 算出——那是**被测实现的函数**。所以「oracle 的全部价值就在于它与被测实现没有共享任何一处代码或常量」这句是不准确的。
  **这不影响本轮结论**，两个理由：① `_weighted_total` 被 `test_weighted_total_is_the_floored_weighted_sum_of_seven_items` 用手算字面量钉死（我逐条复核过），② 我用自己的 `SPEC42` + 自己的 `//100` 重算，500/500 一致。而且这恰好回答了评审要点 B 的第三问：**生成侧与 oracle 侧的 `Delta` 口径是同一个函数，故统一是构造保证、不是运气**——实现者在 Ruling 71 里说「0 是这份数据的运气」指的是**整数口径 vs 连续口径**的分类不一致数（443/500 差值非零、0 分类不同，我复算完全一致），不是指两侧口径没统一。
- **后果**：仅文档准确性。真正的风险是若 Task 8 把 `_weighted_total` 删掉改用 `national_total`（前向约束 #1），这条 import 会断，届时必须同步改测试——`G12 #1` 已经写明了这一点 ✓。
- **建议**：把 `:30-31` 那句收窄为「**判定表的四个阈值**写死在这里、不从生成器或 Task 8 的常量导入」，并在 `:23` 的 import 旁注一句「`_weighted_total` 是与实现共享的**唯一**一处代码，由 `test_weighted_total_...` 的手算字面量独立钉住；Task 8 落地 `national_total` 后一起换掉」。
- **置信度**：**高**（直接读文件 + 我自己的独立复算）。

#### Minor-10 两条权重测试以永假的同义反复断言开头

- **位置**：`tests/domain/test_indicators.py:50`（`assert 15 + 15 + 20 + 10 + 10 + 10 + 20 == 100`）与 `:60`（`assert 15 + 20 + 10 + 10 + 10 + 20 == 85`）
- **现象**：这两行断言的是 Python 对字面量的算术，**任何代码改动都不可能让它们变红**。真正承重的是紧随其后的 `:51` / `:61`（从 `ITEM_WEIGHTS` / `WEAKNESS_ITEMS` 读回来求和）。
- **后果**：无功能后果，但本项目已经吃过一次「断言从被测常量读回来 → 完全无效」的亏（m1 的上一轮），反向的错误（断言与代码完全无关）同样会给人虚假的覆盖感。
- **建议**：删掉这两行，或把它们改成注释（`# 15+15+20+10+10+10+20 = 100`）。
- **置信度**：**高**。

#### Minor-11 本轮的「注入 ↔ 清洗一一对账」绝对计数在报告与账本里都没有新值，账本仍挂着 round-1 的 1554/1542/1572

- **位置**：`progress.md:596`（「**1554 处注入与 1542 条清洗条目**按 `(source, kind, field)` 完全一一对应」，被称为「本任务最硬的证据」）、`progress.md:655`（「注入绝对计数 1554 → **1572**」）、`task-6-report.md:578` / `:649`
- **现象**：我实测本轮：

```
default(dirty): injected=1557 cleaned=1557 equal=True   rows fitness=3000 body=3000 dropped=914 corrected=138
zero-dirty:     injected=0    cleaned=0    equal=True   rows fitness=3000 body=3000 dropped=0   corrected=0
dirty_marks total = 1565   by kind = {'missing': 1304, 'duplicate': 73, 'outlier': 172, 'unit_error': 16}
                 by source = {'fitness': 1084, 'body_comp': 473, 'survey': 8}   non-survey = 1557
```

  **一一对账仍然精确成立**（1557 == 1557）、**干净数据仍 0 条清洗条目** ✓ —— 代码没有退化。但 `progress.md:770` 声明作废的 round-1 观测量清单里只列了哈希、0.5211、1736、strength 分布，**没有 1554/1542/1572**；报告 Fix Round 2 也完全没重述这个量（`Select-String 'clean_fitness|MockLePao|一一对应|清洗条目'` 在 `:692` 之后只命中两处，都是讲 Task 8 对账测试的 `dirty_marks` 过滤写法，不是计数）。
- **后果**：账本里最新可查的注入计数是 1572（round 1），与本轮实际的 1557/1565 不符。Task 10 若拿账本数字做对账基线会差 15。
- **建议**：把 1557（非问卷）/ 1565（含问卷 8 条）/ 分类计数写进账本的本轮段，并把 1554/1542/1572 显式列入作废清单。
- **置信度**：**高**（两次独立实测 + `Select-String` 取证）。

#### Minor-12 `fitness.py` 从 596 行涨到 1168 行，`make_fitness_tests` 单函数 143 行

- **位置**：`app/seed/fitness.py`（1168 行）；`make_fitness_tests:1026-1168`（143 行）、`_settle_prev_targets:738-817`（80 行）、`_delta_target_windows:509-572`（64 行）
- **现象**：

```
baseline 3b10f5e: 596 lines
worktree bed07ed: 1168 lines     (+661 / -89)
   143 lines  make_fitness_tests   @1026
    80 lines  _settle_prev_targets  @738
    64 lines  _delta_target_windows @509
```

  `make_fitness_tests` 现在同时承担：docstring 里的随机流契约（`:1053-1066`）、七个准备步骤的调用序（`:1068-1084`）、以及三层嵌套的记录循环（`:1087-1167`）。趋势模型自己已经拆成 9 个私有函数（`_weighted_total` / `_classify` / `_zero_sum_jitter` / `_delta_target_windows` / `_trend_labels` / `_initial_deltas` / `_correction_move` / `_settle_prev_targets` / `_trend_inputs` / `_trend_prev_targets` / `_anthropometrics`），拆分是合理的。
- **后果**：`generate.py` 不拆已裁定过（不重复提），但 `fitness.py` 是本轮的新情况。具体可测性问题：`make_fitness_tests` 的记录循环里那段「表下溢出 vs 反查+抖动」的分支（`:1109-1147`）**只能整函数调用**才能覆盖，而它依赖前面 5 个准备步骤的全部输出；本轮 Minor-3/Minor-4 那些覆盖不到的分支，正是因为要打到它们就得先跑完整条 500 人流水线。
- **建议**：**不建议本轮改**（超出范围、且会平移随机流）。给 Task 9 的前向约束加一句：若 Task 9 需要在校正循环上做实验，先把 `_settle_prev_targets` 的「落档一次」抽成 `(prev_targets) -> (prev_six, deltas_now, total_change)` 的纯函数，那样 Minor-4 建议的两条守卫测试就能不跑流水线直接打。
- **置信度**：**高**（行数与 AST 函数长度实测）；「影响可测性」这半条是我的判断，置信度中。

---

## 报告数字复核表

| 报告/账本声称 | 我实测 | 一致？ |
|---|---|---|
| `pytest -q` → 280 passed | 280 passed in 9.39s | ✓ |
| `pytest -q -W error` → 280、洁净 | 280 passed in 10.90s、无 warnings 段 | ✓ |
| 基线 236 → 280（+44：4/14/20+1/1/1/3） | numstat 合计 +1579/−119 逐文件相同；collect-only：tests/seed 75、test_generate 46、test_fitness 15、test_trend_oracle 14 | ✓ |
| 持续下滑 n=100 均值 −8.17 中位 −8.0 正占比 0.00% min −15 max −2 | 100 / −8.17 / −8.0 / 0.00% / −15 / −2（sd 3.19 样本 / 3.17 总体，报告用样本 sd） | ✓ |
| 波动大 n=75 +2.73 +3.0 82.67% −2 +8 | 75 / +2.73 / +3.0 / 82.67% / −2 / +8（sd 2.44） | ✓ |
| 稳步提升 n=125 +14.26 +14.0 100.00% +6 +23 | 125 / +14.26 / +14.0 / 100.00% / +6 / +23（sd 3.94） | ✓ |
| 稳定 n=200 +1.43 +1.0 77.50% −1 +4 | 200 / +1.43 / +1.0 / 77.50% / −1 / +4（sd 1.32）；实测只用了 6 个值 `[−1,0,1,2,3,4]` | ✓ |
| G2 六项之和口径 −57.05 / +18.97 / +99.92 / +10.62 | −57.05 / +18.97 / +99.92 / +10.62（中位 −60 / +20 / +100 / +10，正占比 0% / 97.33% / 100% / 85%） | ✓ |
| oracle 500 人全覆盖不一致 **0** | 我的第三份实现：0（`score_*` 列路径）**且** 0（零注入 + 从原始值正查的生产侧路径） | ✓ |
| 波动大 75 人全是 `(3 正, 3 负, 0 零, max|d|≥10)` | `Counter({(3,3,0,True): 75})` | ✓ |
| 校正循环 19/500 触发、最大 1 轮、`{0:481, 1:19}`、RuntimeError 0 次 | `{'students': 500, 'triggered': 19, 'total_rounds': 19, 'max_rounds': 1}`、`Counter({0:481, 1:19})`、RuntimeError 0 | ✓ |
| 零注入配置下校正统计「完全相同」 | `{'students': 500, 'triggered': 19, 'total_rounds': 19, 'max_rounds': 1}` | ✓ |
| **可行池 波动大 260 / 持续下滑 150 / 稳步提升 322** | **260 / 152 / 318**（两种独立方法：忠实重放 `_trend_labels` 且标签与记录逐人相等；以及从记录的标签反推。全量可行 260/203/487/489、稳定 residual 200、稳定不可行 0 全部一致） | **✗ 两项不符** |
| 波动大池性别 男 125(45.5%) / 女 135(60.0%)；持续下滑 112(40.7%)/91(40.4%)；稳步提升 268(97.5%)/219(97.3%)；稳定 265(96.4%)/224(99.6%) | 逐字相同 | ✓ |
| 男 `max(curr)` p90=100、≤84 占 54.5%；女 p90=98、占 60.0%；波动大实到 28 男/47 女 | 100.0/54.5%、98.0/60.0%、`{'male': 28, 'female': 47}` | ✓ |
| 三个 CSV SHA256 前 16 = `498AA3256678B01A`/`1234025C05843B27`/`835A98FCC0779B51`，两次独立进程相同；`seed=1` 三个全不同 | 逐字相同（字节 244496/107745/276193；seed=1 → `11A6651B4CEA9A58`/`242BE5A968C10594`/`3245D2EAFEF7FA9D`） | ✓ |
| corr(endurance,strength) **0.4954**；(end,sf) 0.4260；(str,sf) 0.3188 | 去重到 500 人后 0.4954 / 0.4260 / 0.3188（含 5 条 duplicate 行时是 0.4985/0.4210/0.3187，报告口径是 500 人） | ✓ |
| 桶均分 67.81 / 66.56 / 68.00 | 67.81 / 66.56 / 68.00 | ✓ |
| 肺活量 **1801** 个不同取值、95.1% 脱离端点、官方阈值并集 75 | 1801 / 2852÷3000 = 95.1% / 75 | ✓ |
| 表下溢出 275 男标记 **28** 人 / 168 条 / `{0:26,1:38,2:43,3:30,4:26,5:5}` / 得分集合 {10} / 大一二 126 条·大三 四 42 条 / latent_strength −1.1447 < −1.1196 / week1 该项趋势 `{0:28}` / 28 人标签分布 持续下滑 12·稳步提升 2·稳定 14·波动大 0 | 275 / 28 / 168 / `{0:26,1:38,2:43,3:30,4:26,5:5}` / `[10]` / 126·42 / −1.1447 < −1.1196 / `{0:28}` / `{持续下滑:12, 稳步提升:2, 稳定:14}` | ✓ 全部逐字相同 |
| 跨 19/20 线 132/500 = 26.4% | 132/500 = 26.4% | ✓ |
| 口径差值非零 **443/500**、分类不一致 **0** | 443 / 0 | ✓ |
| week8 / week16 与 `trend_label` 不一致 **5.0% / 4.2%**（Ruling 75②） | 25/500 = 5.0%、21/500 = 4.2%（week1 = 0/500） | ✓ |
| G11④ 名义→实际偏差 +1.75 / +2.11 / +1.40，名义均值 −9.92 / +12.15 / +0.03，名义区间 [−17.48,−6.03] / [+6.05,+17.76] / [−1.92,+1.98] | 逐字相同 | ✓ |
| G11④「实际 `Delta'` **一律** ≥ 名义 `Delta_target`」 | **17/500 反例**（持续下滑 2、稳步提升 5、稳定 10；最小 −0.38） | **✗** |
| 关切⑦ / `progress.md:796`「按方差读会让 corr 从 0.4954 掉到 **0.46 附近**，余量仅 0.06，`corr > 0.4` 钉住它」 | 实测方差读法 corr = **0.4052**，`corr > 0.4` **仍然通过** → 钉不住 | **✗** |
| G9.4 / 关切⑦ 的中间数字 1.0440、1.1045 | 正确值是 `sqrt(0.49+0.7)` = **1.0909**；且 G9.4 那句话自相矛盾（「会超出 ±0.15 的带宽（…差 0.115，在带内）」） | **✗** |
| `progress.md:722`（Ruling 67）「计划 `:887` 与报告 `:400` 的数字已更正」 | 计划已更正（`:934`）；**报告 `:400` 仍是 1213/2376 = 51.1%，无就地作废标记** | **✗** |
| 注入 ↔ 清洗一一对应（账本 `:596` 1554/1542、`:655` 1572） | 本轮 **1557 == 1557**（含问卷共 1565）；报告与账本均未给本轮新值 | **✗ 数字过期** |
| G1 RED：309/500 不一致、持续下滑组中位 +8.0、波动大第一人 `(5 正,0 负,1 零)`、`3 failed, 11 passed` | **未独立复核**（需回到基线代码状态）；内部一致性可核：六项之和 +54.17 × (85/100 ÷ 6) ≈ +7.7 ≈ +8.0 ✓ | 未复核 |
| G12 #10 / `progress.md:807`「波动大可行池会先枯竭」 | μ=+0.5/+1.0 时先枯竭的是**持续下滑**（88/100、37/100）；波动大只在 μ ≥ +1.5 时先枯竭 | **✗** |

---

## 规格与裁定本身的问题

### (a) spec §6.3 的 `Delta` 公式仍缺 `//100`，与它自己表里的 ±5 阈值差 100 倍 —— Ruling 71 只改了计划，没改 spec

`Document\...设计spec.md:376`：

> 记 `delta_i = 本学年得分_i − 上学年得分_i`（**正 = 进步**），`Delta = Σ 全部 7 项 w_i × delta_i`（即总分变化）。

字面读，`Delta` 是**加权和**（`Σ w_i delta_i`，量级 0–8500），而紧随其后的判定表（`:383-384`）用的是 `Delta ≤ −5` / `Delta ≥ +5`。这两个阈值只在 `(Σw·curr)//100 − (Σw·prev)//100` 的 0–100 口径上有意义——Ruling 63 与 Ruling 71 也正是这么裁的。字面按 spec 实现，`Delta ≤ −5` 会被几乎所有人满足（等价于「加权和降 5 分」，即总分降 0.05 分）。

Ruling 71 修的是**计划**（`:917` 现在写明「必须是这个『先各自整除、再相减』的形式」），但：
- **spec §6.3 没有同步勘误**。§6.3 是 §14 #22/#23 交给项目负责人签字的那一份，也是 Task 8 实现 `classify_trend` 时唯一会引的规格来源。
- **计划自己内部还矛盾**：`:898` 写 `Delta = Σ 全部 7 项 w_i × delta_i / 100`（真除法、连续量），而 19 行之后的 `:917` 明写「**不是** `Σ w_i·delta_i' / 100`」。同一节里两个公式打架，且 `:898` 是被 Ruling 71 否决的那一个。

**建议**：spec `:376` 改为 `Delta = (Σ w_i × 本学年得分_i) // 100 − (Σ w_i × 上学年得分_i) // 100`（并加一句「// 是向下取整，两侧必须各自整除后再相减」）；计划 `:898` 的 `/ 100` 改成与 `:917` 一致的整数口径。**置信度：高**（三处文本直接对读；实现与测试两侧都已经是整数口径，我实测 `_classify` 在整轮生成里收到的 `total_change` 538 次全是 `int`）。

### (b) 计划 Step 4 `:918` 为「波动大」mandate 的校正逻辑，在 Ruling 70 自己的可行域判据下**可证明永不执行**

计划 `:918` 后半段：

> `波动大` 的校正目标是 `max_i |delta_i'| ≥ 10` 而不是某个 `Delta'`：……幅值 10 的负项落档后可能只剩 1 分。**必须在落档后复核，不满足就把幅值最大的那一项的 `prev_target` 再往上推一个官方档。**

**证明它不可达**（用计划 `:922` 与 `:909` 自己的判据）：设 `swing` 下限 `m₀ = 10`、上限 `m₁ = 16`，可行域要求 `min_i curr_i ≥ 16` 且 `max_i curr_i ≤ 84`、六项全自由。

1. 正号给 curr 最低的三项，`prev_target = curr − m`，`m ∈ [10,16]` → `prev_target ∈ [0, 74]`，**不被 `[0,100]` 钳位**。落档只会往下取（`prev_i ≤ prev_target`），故 `delta_i' = curr − prev_i ≥ curr − prev_target = m ≥ 10`。→ **三项正delta 落档后仍 ≥ +10**。
2. 负号给最高的三项，`prev_target = curr + m ∈ [26, 100]`，同样不被钳位。`prev_target` 是整数，国标得分序列 `100,95,90,85,80,78,…,62,60,50,40,30,20,10` 的最大档距是 10，故落档损失 `prev_target − prev_i ≤ 9`。→ `delta_i' ≤ −m + 9 ≤ −1 < 0`，**符号不变、且不会变成 0**。
3. 由 1、2：恰好 3 正 3 负（`min = 3 ≥ 3`）且 `max|delta_i'| ≥ 10` → 第 0 轮就命中 `波动大`。∎

实测完全吻合：**16 个配置 × 500 人 = 8000 次构造，`label == "波动大"` 的校正分支 0 命中，波动大组 0 人需要任何轮数**（19 次校正全部来自稳定 15 + 持续下滑 4）。

这是本任务里**同一类结构性错误的第三次**：Ruling 64a 是「判定表有一行不可达」，Ruling 72 是「生成器侧有一个子集不可达」，这一条是「为不可达的情形 mandate 了一段校正逻辑」。前两次都由控制者自己发现并写进了硬规矩 #2/#4，但规矩 #2 的作用域写的是「**手写决策表**必须逐行验证可达性」——它没有覆盖「**手写修复/校正流程**必须验证它要修的情形是否可达」。

**建议**：① 删掉计划 `:918` 那一句与 `fitness.py:723-726` 那个分支（或把代码注释成「防御性，可证明不可达，证明见 …」）；② 把硬规矩 #2 扩成「凡手写**判定表或修复流程**，必须逐行/逐分支验证可达性：为每一分支构造一个能触发它的输入，构造不出来的就是死分支」。**置信度：高**（上面是完整证明 + 8000 次实测 0 命中）。

### (c) Ruling 70 的字面判据与实现不等价，且字面判据漏了均匀分配的 `100/w_free` 放大

`progress.md:774` 与计划 `:923-925` 给的是布尔式（`持续下滑`：`min_i(100−curr_i) ≥ |Delta_target| + 9`）；实现给的是**每生的 `Delta_target` 抽样窗口**：`|Delta_target − b| ≤ w_free · max(0, min_i room − jitter − CORRECTION_RESERVE) / 100`（`fitness.py:558-571`）。

字面式的问题：均匀分配下每项承担 `100·Delta_6/w_free ≈ 1.176·Delta_6`，**比 `Delta_target` 本身大 17.6%**，字面式没算这个放大，也没算 jitter（3）与校正预留（10）——它写的 `+9` 只是落档损失。反例（`head_up = 25`、`Delta_target = −18`、`b = 0`）：字面式 `25 ≥ 27` 判不可行，实现判可行并把窗口收窄到 `(−10.2, −6)`。两个方向都会分歧。

实现是**准确的那一个**（0 次 RuntimeError / 8000 次构造），Ruling 70 的推理方向（「判据的作用域必须是逐项而不是聚合」）也完全正确——只是它给出的具体公式没有把均匀分配的放大系数代进去。

**建议**：把计划 `:923-925` 换成实现的窗口式；Ruling 70 补一句「字面的 `+9` 只覆盖落档损失，均匀分配还有 `100/w_free` 的放大与 jitter，故正确形式是收窄抽样窗口而非布尔筛选」。**置信度：高**。

### (d) 交给 Task 9 的前向约束认错可行池、开错药方（= 缺陷 Major-1）

见 Major-1。这是 Ruling 70 的 `min_i` 更正带来的**新**后果，控制者在写这条约束时用的是「`max curr ≤ 84` 对波动大最紧」的直觉，而没有实测 μ 扫描。实测：持续下滑池的余量本来就只有 1.52×（四类里最紧，报告 G5 自己也这么说），μ 一推高它先崩。**`progress.md:807` 与 `task-6-report.md:1032` 两处都要改。**

### (e) `progress.md:796` 接受关切 7 的理由是错的：`corr > 0.4` 钉不住「sd 读成方差」

账本原文：

> 真正钉住它的是既有的 `corr > 0.4`（会从 0.4954 掉到 0.46 附近，余量仅 0.06）。**控制者接受该判断，不要求补强**

我把 `LATENT_LOADINGS` 在**运行时**换成方差读法（`sd → sqrt(sd)`，未改任何源文件）重跑：

```
variance-reading corr(endurance,strength) = 0.4052  -> assertion corr>0.4 PASSES (guard does NOT catch it)
variance-reading bucket sds = {'endurance': 1.124, 'strength': 1.0559, 'speedflex': 1.1123}
```

**0.4052 > 0.4，断言照样绿。** 「余量仅 0.06」这个说法本身就意味着它通过了——一条通过的断言不构成守卫。所以「控制者接受该判断」的**结论**（不要求补强）可以成立，但**理由**不成立：现状是**没有任何东西**钉住 sd/方差的读法，只有 Ruling 73 的文档更正与 `fitness.py:69-76` 的注释。而余量只有 0.005，换一个种子它可能落到 0.4 以下——那时会是一次**假红**，指向一个不存在的缺陷。

附带：报告 G9.4/关切⑦ 的中间数字也错了两处。它写「σ=1 时三个理论值变成 1.1135 / **1.0440** / 1.0770」，strength 的正确值是 `sqrt(0.7² + 0.7) = sqrt(1.19) = ` **1.0909**（1.0440 = `sqrt(0.49+0.6)`，把 endurance 的残差 0.6 配给了 strength 的载荷 0.7）；G9.4 里又写「strength 的理论值从 0.9899 变成 **1.1045**」，第三个数字。同一句还自相矛盾：「会因 strength 的理论值…超出 ±0.15 的带宽（1.1045 vs 0.9899 差 0.115，**在带内**）」——先说超出、括号里说在带内。它的**结论**（这条测试对「方差读法」分辨力不足）是对的，我实测确认：方差读法下 endurance 1.124 / strength 1.0559 / speedflex 1.1123，与测试的期望 1.0 / 0.9899 / 1.0 各差 0.124 / 0.066 / 0.112，**全部在 ±0.15 带内**，测试确实不红。

**建议**：把 `progress.md:796` 的理由改成「实测方差读法下 corr = 0.4052，`corr > 0.4` **仍然通过**，故当前**没有**自动守卫钉住 sd 语义；防线是 Ruling 73 的文档更正 + `fitness.py:69-76` 的显式注释 + `LATENT_LOADINGS` 的 `# (载荷, 残差 sd)`。若将来要补一条真守卫，最小改法是把 `test_latent_sd_propagates_through_the_bucket_loadings` 的期望值改成 σ=2 那一组（1.7088/1.5524/1.4422）并把带宽收到 ±0.05——方差读法在 σ=2 时是 1.7776/1.6000/1.5232，差 0.069/0.076/0.081，会红」。并更正报告 G9.4 的 1.0440 / 1.1045 与那句自相矛盾的话。**置信度：高**（运行时替换实测 + 解析复算一致）。

### (f) `progress.md:766` 的可行池数字 150 / 322 复现不出来（实际 152 / 318），而该处标着「控制者已独立复核」

我用两种互相独立的方法测，都得 152 / 318：
1. 忠实重放 `_trend_labels`（同样的 `allocate_quota`、同样的 `rng.permutation`、同样的 `sort` key），并断言重放出的标签与记录里的 `trend_label` **逐人相等**（`True`）→ `pool log = [('波动大',260,75), ('持续下滑',152,100), ('稳步提升',318,125), ('稳定 residual',200,200), ('稳定 infeasible',0,0)]`。
2. 完全不重放，从**记录里的标签**反推：`#{持续下滑可行} − #{持续下滑可行 且 被标为波动大} = 203 − 51 = 152`；`487 − 169 = 318`。

两个数字都不影响任何验收判据（152 ≥ 100、318 ≥ 125，余量 1.52× / 2.54× 而非 1.50× / 2.58×），但这是账本硬规矩 #1「凡写进简报或计划的数字，必须来自本次会话里我亲自跑过的命令」的又一次落空，且是 `progress.md:813` 列举的 7 次同类错误之后的**第 8 次**。最可能的成因：探测脚本在 `_trend_labels` 加上「优先挑稳定不可行的人」那个 `sort`（`:612`）之前跑的——去掉 `sort` 会挑走另一批 75 人，从而让后两类的池各差几个人（150 = 203 − 53、322 = 487 − 165，与被挑走子集不同的预期一致）。

**建议**：把 `progress.md:766` 的 150/322 改成 152/318，并把「可行池大小依赖 `sort` 的 tie-break，须在**最终代码**上测」写进硬规矩 #1 的附注。**置信度：高**（两种方法一致 + 数据集本身由 SHA256 确认与报告逐字相同）。

### (g) 重写后的 spec §6.3 判定表：**四行全部可达，无自相矛盾**（这是好消息，我逐行验证过）

按硬规矩 #2 的方法为每行构造一个「满足该行、且不满足它上面所有行」的输入（全部来自 `test_trend_oracle.py` 的黄金用例，我手算复核过）：

| 行 | 输入 | 上面各行不满足的理由 |
|---|---|---|
| 1 波动大 | 3 项 −12 + 3 项 +10，`Delta` = −3 | 无上行 |
| 2 持续下滑（第一分支） | 2 项 ≤ −5、`Delta` = **−5** | 行 1：6 项全负 → `min(0,6) = 0 < 3` |
| 2 持续下滑（第二分支） | 3 项 −5 + 3 项 +1、`Delta` = **−1** | 行 1：3 正 3 负成立但 `max|d| = 5 < 10` |
| 3 稳步提升 | 六项各 +7、`Delta` = **+5** | 行 1：6 正 0 负；行 2：`Delta > −5` 且 `#{≤−5} = 0` |
| 4 稳定 | 5 项 +10、1 项 −6、`Delta` = **+6** | 行 3：`min delta = −6 ≤ −5` |
| 4 稳定（另一侧） | 六项各 +5、`Delta` = **+4** | 行 3：`Delta = 4 < 5` |
| §14 #23 的退化 | 3 正 2 负 1 零、`max|d| = 13` | 行 1：`min(3,2) = 2 < 3`（**delta=0 是真的构造出来了**，测试显式断言 `deltas[DISTANCE_RUN] == 0`） |

Ruling 64a 的行序更正、64b 的阈值收紧、#23 的保守读法都自洽，且 `delta_i = 0` 的退化副作用如规格所述（刻意漏判）。**§6.3 重写后没有残留的不可达行。** 唯一的规格缺口是 (a) 那条 `Delta` 公式。

---

## 值得肯定的地方（只写我验证过的）

1. **C1 是被结构性消灭的，不是被符号翻转修补的。** `git grep -E "prev_offset|-= offsets|_trend_offsets|ITEM_TREND_JITTER_SD"` → 0 命中；字段直接改名为 `delta_target_range`，与 spec 同名同向。我用自己从 spec 正文翻译的第三份分类器复算，500/500 一致，**且从原始值正查的生产侧路径（Task 8 将走的那条）同样 500/500 一致**——这意味着 Ruling 69② 的对账测试在零注入配置下会直接绿。
2. **Ruling 71 的口径统一是构造保证，不是运气。** 我用 `wrap` 拦截 `_classify` 统计实参类型：整轮生成 **538 次调用，`total_change` 全部是 `int`**；并直接验证两种口径的分歧真实存在（`_classify(d, -5)` = 持续下滑 vs `_classify(d, -4.8)` = 稳定）。生成侧与 oracle 侧共用同一个 `_weighted_total`，故两侧同口径是必然。
3. **10 条黄金用例全部真手算，没有一条是「跑一遍把输出填进去」。** 我逐条复核了 Σw·s 与 `//100`（含 7615//100 = 76 这条专门钉向下取整的），并确认 `test_one_zero_delta_makes_volatile_unreachable` 显式断言了 `deltas[DISTANCE_RUN] == 0` 与 `max|d| == 13 ≥ 10`——即它是**只**靠零项打破分裂，不是碰巧。
4. **Ruling 72 的 `len(free) == 6` 守卫是性别无关的。** 我分别用 `{male:...}`、`{female:...}`、两者同时开启三种 `sub_floor_rate` 跑：标记 28 男 / 22 女 / 50 人，`标记 ∩ 波动大` 三种情况**全为 0**。
5. **本轮最可能的新增哑弹（趋势重写把上学年原始值推出 `indicator_ranges.yaml` 区间）不存在。** 我逐列逐学年审计：8 个测量列 × 2 个学年，`outside = 0` 全部；最紧的余量是上学年 `standing_jump_cm` min = 126.0 vs yaml min = 120.0。端到端 `write_csv → MockLePaoAdapter → clean_fitness/clean_body_comp` 仍是 **1557 注入 == 1557 清洗条目**、零注入 **0 == 0**、3000/3000 行；`score_*` 诊断列与从原始值正查的得分在**全部 3000 条记录**上 0 处不一致（证明抖动确实从不跨档）。
6. **AST 守卫的 20 条自证测试是真的自证**，不是「断言守卫函数存在」：每条把违规源码写进 `tmp_path/fake_module.py` 再断言 `_scan(tmp_path)` 非空**且**至少一条 offender 指向预期 token；另有 1 条负对照断言「带种子的 `default_rng(cfg.seed)` + `Generator` 只作类型标注 + `cfg.seed` 只作属性读取 + `timepoint_date(...)`」必须 `_scan == []`。这一正一反的设计恰好堵住了「永远报警的守卫」这个反向失效模式。
7. **实现者主动上报自己写的测试分辨力不足（关切 ⑦）**，并在报告里写「这是我在本轮唯一一处明知不足而没有补强的地方」。（虽然它给的理由数字是错的——见规格问题 (e)——但**主动上报这个行为本身**是本轮最有价值的过程产出。）
8. **简报 §4「明确不要做的事」逐条遵守，我全部独立取证**：`derive.py` 不存在、`app/seed` 里 `classify_trend`/`national_total` 只有 4 处 docstring 引用；`indicators.py` 的 diff 是 `+14/−0` 纯新增 `ITEM_WEIGHTS`；`sections.py`/`population.py`/`body_comp.py`/`survey.py` **一字未动**；`fitness.py` 的 diff hunk 全部落在趋势模型区域，`jitter_raw`/`sub_floor_marks` 未被触碰；`pe.db` 不存在；`generate.py` 未拆（515 行）；4 条延后 Minor 未碰。

---

## 无法判断的事项

1. **G1 的 RED 证据**（`3 failed, 11 passed`、309/500 不一致、持续下滑组中位 +8.0、波动大第一人 `(5 正, 0 负, 1 零)`）。要复现必须把 `app/seed/fitness.py` 回退到 `3b10f5e` 并与新增的 `ITEM_WEIGHTS`/`_weighted_total` 组合，那需要 `git worktree` 或改写工作区，超出「只读评审」的边界。我只能核其**内部一致性**：六项之和口径的 +54.17 换算到 0–100 加权口径是 `54.17 × (85/100) / 6 ≈ +7.7`，与报告的 +8.0 相符；309/500 与「11 条绿（10 黄金 + 1 `_weighted_total`）」也自洽（黄金用例只打 `_oracle`，不打生成器）。**结论：可信但未独立复现。**
2. **`progress.md:766` 的 150/322 究竟是怎么测出来的。** 我给出了最可能的成因（探测脚本早于 `:612` 那个 `sort` 的加入），但没有证据——那需要实现者/控制者的探测脚本，已按其自述删除。
3. **报告 `:401-402` 的「+0.827 分/项」与「引体向上 +2.72 / 46.3%」等逐项偏差是否也与 1213 一样属于「修复后数据在反方向的度量」。** Ruling 67 只更正了 1213→334，保留了 0.83（计划 `:934` 仍写「每项趋势被系统性低估约 0.83 分」）。这两个数字出自同一次 F1.2 测量，若 1213 是错的那一侧，0.827 是否也是？需要重建基线代码才能判定，超出只读边界。
4. **`_correction_move` 的 shape-fix 分支是否**可证明**不可达。** 我证明了波动大**自己**的分支不可达（规格问题 (b)），也实测 shape-fix 在 8000 次构造里 0 命中，但没能证明「非波动大标签的学生落档后绝不会凑出 3 正 3 负 + `max|d| ≥ 10`」——`_delta_target_windows:561-569` 的符号纯度约束把初始 `delta_i` 压在 ≤ −1 / ≥ +1 / ≥ −4，而落档最多抬 9 分，理论上存在凑出 3 正 3 负的路径。这一条我只有经验证据（16 配置 0 命中），没有证明。
5. **`int(round(len(cohort) * rate))` 的银行家舍入是否是有意选择。** 实测 275 × 0.10 = 27.5 → 28（进偶），225 × 0.10 = 22.5 → **22**（进偶），两个方向相反。Ruling 58 只写「取前 `int(round(n × rate))` 名」，没规定半值方向。不在本轮范围内（`sub_floor_marks` 一字未动），仅记录。
